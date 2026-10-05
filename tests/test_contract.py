"""Every client method against the pinned API contract: its HTTP method and
path must be in contract/openapi-<CONTRACT_VERSION>.json, and it must send the
fields the contract marks required. Requests go to a local HTTP server so the
wire format (multipart field names, JSON keys, query) is what gets checked."""

from __future__ import annotations

import inspect
import json
import re
import threading
from collections.abc import Iterator
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

import livexface
from livexface import LiveXFace

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "CONTRACT_VERSION").read_text().strip()
CONTRACT: dict[str, Any] = json.loads((ROOT / "contract" / f"openapi-{VERSION}.json").read_text())
PREFIX = CONTRACT["servers"][0]["url"]  # contract paths are relative to it

FACE = {"id": "f1", "collectionId": "c1", "externalId": "u1", "createdAt": "2026-09-28T00:00:00Z"}
# One reply that every result type can parse.
DATA = {**FACE, "match": True, "confidence": 0.9, "thresholdUsed": 0.5, "succeeded": 1, "failed": 0, "status": "queued"}
IMG = b"img"
ITEMS = [
    {"external_id": "u1", "image": IMG, "metadata": {"k": "v"}, "liveness_token": "lt"},
    {"external_id": "u2", "image": IMG},
]
NO_CONTENT = None  # the server answers 204

# Every public client method: (args, kwargs, reply data). Optional arguments
# that add fields are passed so those fields are checked too.
CALLS: dict[str, tuple[tuple[Any, ...], dict[str, Any], Any]] = {
    "faces.register": (
        ("c1", IMG, "u1"),
        {"metadata": {"k": "v"}, "liveness_token": "lt", "idempotency_key": "key-1"},
        DATA,
    ),
    "faces.list": (("c1",), {"limit": 5, "offset": 10}, {"faces": [FACE], "total": 1}),
    "faces.get": (("c1", "f1"), {}, DATA),
    "faces.get_by_external_id": (("c1", "u1"), {}, [FACE]),
    "faces.delete": (("c1", "f1"), {}, NO_CONTENT),
    "faces.verify": (("c1", IMG, "f1"), {"threshold": 0.5}, DATA),
    "faces.identify": (("c1", IMG), {"top_k": 3, "threshold": 0.5}, DATA),
    "faces.search": ((IMG,), {"collection_ids": ["c1", "c2"], "top_k": 3, "threshold": 0.5}, DATA),
    "faces.liveness": (("c1", IMG), {}, DATA),
    "faces.active_liveness": (("c1", [IMG] * 5), {}, DATA),
    "faces.create_liveness_session": (
        ("c1",),
        {},
        {"sessionId": "lvs_1", "challenges": [{"type": "blink"}], "expiresAt": "2026-09-28T00:01:00Z"},
    ),
    "faces.complete_liveness_session": (("c1", "lvs_1", [IMG] * 5), {"mirrored": True}, DATA),
    "faces.compare": ((IMG, IMG), {"threshold": 0.5}, DATA),
    "faces.batch_register": (("c1", ITEMS), {"idempotency_key": "key-2"}, DATA),
    "faces.batch_delete": (("c1", ["f1", "f2"]), {}, DATA),
    "faces.attributes": (("c1", IMG), {}, DATA),
    "faces.batch_register_async": (("c1", ITEMS), {"idempotency_key": "key-3"}, DATA),
    "faces.get_batch_job": (("c1", "j1"), {}, DATA),
}


class Captured:
    def __init__(self, method: str, path: str, content_type: str, fields: set[str], headers: set[str]) -> None:
        self.method = method
        self.path = path
        self.content_type = content_type
        self.fields = fields
        self.headers = headers


def _body_fields(full_type: str, body: bytes) -> set[str]:
    """Multipart field names or top-level JSON keys of a request body."""
    content_type = full_type.split(";")[0].strip()
    if content_type == "multipart/form-data":
        # The multipart parser needs the boundary from the Content-Type header.
        msg = BytesParser().parsebytes(b"Content-Type: " + full_type.encode() + b"\r\n\r\n" + body)
        names = (part.get_param("name", header="content-disposition") for part in msg.walk())
        return {str(name) for name in names if name}
    if content_type == "application/json":
        data = json.loads(body)
        return set(data) if isinstance(data, dict) else set()
    return set()


class FakeAPI:
    """Records each request and answers with ``reply`` (204 when it is None)."""

    def __init__(self) -> None:
        self.reply: Any = None
        self.requests: list[Captured] = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                full_type = self.headers.get("Content-Type") or ""
                content_type = full_type.split(";")[0].strip()
                url = urlsplit(self.path)
                fields = set(parse_qs(url.query, keep_blank_values=True)) | _body_fields(full_type, body)
                api.requests.append(
                    Captured(self.command, url.path, content_type, fields, {k.lower() for k in self.headers})
                )
                if api.reply is NO_CONTENT:
                    self.send_response(204)
                    self.end_headers()
                    return
                raw = json.dumps({"success": True, "data": api.reply}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}{PREFIX}"


@pytest.fixture(scope="module")
def api() -> Iterator[FakeAPI]:
    fake = FakeAPI()
    t = threading.Thread(target=fake.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


def _template_regex(template: str) -> str:
    return "/".join("[^/]+" if seg.startswith("{") else re.escape(seg) for seg in template.split("/"))


def _schema(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if ref:
        node: Any = CONTRACT
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
        return dict(node)
    return schema


def _normalize(field: str) -> str:
    # The contract documents repeated file fields by their first name only.
    field = re.sub(r"\[\d+\]$", "[0]", field)
    return re.sub(r"^frame_\d+$", "frame_0", field)


def _check(req: Captured) -> None:
    where = f"{req.method} {req.path}"
    assert req.path.startswith(PREFIX + "/"), f"{where}: not under the contract's server URL {PREFIX}"
    path = req.path[len(PREFIX):]
    method = req.method.lower()
    # A literal segment beats a {param} one, as in the API's router.
    candidates = sorted(
        (t for t, ops in CONTRACT["paths"].items() if method in ops and re.fullmatch(_template_regex(t), path)),
        key=lambda t: t.count("{"),
    )
    assert candidates, f"{where}: no {req.method} operation in contract {VERSION} matches path {path}"
    template = candidates[0]
    op = CONTRACT["paths"][template][method]

    required: set[str] = set()
    for param in op.get("parameters", []):
        param = _schema(param)
        if param.get("required") and param["in"] == "query":
            required.add(param["name"])
        if param.get("required") and param["in"] == "header":
            assert param["name"].lower() in req.headers, f"{where}: required header {param['name']} not sent"
    body = op.get("requestBody")
    if body and (body.get("required") or req.content_type):
        content = body["content"]
        assert req.content_type in content, (
            f"{where}: sent {req.content_type or 'no body'}, contract {VERSION} {template} takes {sorted(content)}"
        )
        required |= set(_schema(content[req.content_type]["schema"]).get("required", []))

    sent = {_normalize(f) for f in req.fields}
    missing = sorted(required - sent)
    assert not missing, f"{where}: contract {VERSION} {req.method} {template} requires {missing}, sent {sorted(sent)}"


def test_contract_version_matches_pinned_contract() -> None:
    assert livexface.CONTRACT_VERSION == VERSION == CONTRACT["info"]["version"]


@pytest.mark.parametrize("name", sorted(CALLS))
def test_method_is_in_contract(api: FakeAPI, name: str) -> None:
    args, kwargs, reply = CALLS[name]
    resource, method = name.split(".")
    client = LiveXFace(api_key="lxf_test", base_url=api.base_url)
    api.reply = reply
    api.requests.clear()

    getattr(getattr(client, resource), method)(*args, **kwargs)

    assert len(api.requests) == 1, f"{name} made {len(api.requests)} requests"
    _check(api.requests[0])


def test_every_public_method_is_checked() -> None:
    client = LiveXFace(api_key="lxf_test")
    public = {
        f"{attr}.{name}"
        for attr, resource in vars(client).items()
        if type(resource).__module__ == "livexface.client"
        for name, _ in inspect.getmembers(type(resource), inspect.isfunction)
        if not name.startswith("_")
    }
    assert public, "found no resource classes on the client"
    assert not public - set(CALLS), f"public methods missing from the contract check: {sorted(public - set(CALLS))}"
    assert not set(CALLS) - public, f"CALLS names methods that no longer exist: {sorted(set(CALLS) - public)}"
