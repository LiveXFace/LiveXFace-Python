"""Idempotency keys, typed errors with Retry-After, and opt-in retries,
against a local HTTP server so headers and dropped connections are real."""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from livexface import LiveXFace, LiveXFaceApiError, LiveXFaceNetworkError, new_idempotency_key

FACE = {"id": "f1", "collectionId": "c1", "externalId": "u1", "createdAt": "2026-09-28T00:00:00Z"}
DROP = "drop"  # close the socket without answering


def _ok(status: int, data: Any, headers: dict[str, str] | None = None) -> tuple[int, dict[str, Any], dict[str, str]]:
    return status, {"success": True, "data": data}, headers or {}


def _err(
    status: int, code: str, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, Any], dict[str, str]]:
    body = {"success": False, "error": {"code": code, "message": code.lower()}, "requestId": "req-1"}
    return status, body, headers or {}


class FakeAPI:
    """Answers each request with the next scripted reply and records its headers."""

    def __init__(self) -> None:
        self.replies: list[Any] = []
        self.requests: list[dict[str, str]] = []
        api = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                api.requests.append(dict(self.headers))
                reply = api.replies.pop(0)
                if reply == DROP:
                    self.close_connection = True
                    return
                status, body, headers = reply
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(raw)

            do_GET = do_POST = do_DELETE = _handle

            def log_message(self, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}/api/v1"

    def keys(self) -> list[str | None]:
        return [h.get("Idempotency-Key") for h in self.requests]


@pytest.fixture
def api() -> Iterator[FakeAPI]:
    fake = FakeAPI()
    t = threading.Thread(target=fake.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    t.start()
    yield fake
    fake.server.shutdown()
    fake.server.server_close()


def _client(api: FakeAPI, sleeps: list[float], max_retries: int = 0) -> LiveXFace:
    return LiveXFace(api_key="lxf_test", base_url=api.base_url, max_retries=max_retries, sleep=sleeps.append)


def test_rate_limited_error_exposes_retry_after_without_retrying(api: FakeAPI) -> None:
    api.replies = [_err(429, "RATE_LIMIT_EXCEEDED", {"Retry-After": "12"})]
    sleeps: list[float] = []

    with pytest.raises(LiveXFaceApiError) as exc:
        _client(api, sleeps).faces.identify("c1", b"img")

    assert exc.value.status_code == 429
    assert exc.value.code == "RATE_LIMIT_EXCEEDED"
    assert exc.value.request_id == "req-1"
    assert exc.value.retry_after == 12
    assert len(api.requests) == 1
    assert sleeps == []


def test_busy_engine_is_retried_after_retry_after_with_same_key(api: FakeAPI) -> None:
    api.replies = [_err(503, "SERVICE_BUSY", {"Retry-After": "5"}), _ok(201, FACE)]
    sleeps: list[float] = []

    face = _client(api, sleeps, max_retries=2).faces.register("c1", b"img", "u1")

    assert face.id == "f1"
    keys = api.keys()
    assert len(keys) == 2
    assert keys[0] and keys[0] == keys[1]
    assert sleeps == [5]


def test_dropped_enrolment_is_retried_and_replayed(api: FakeAPI) -> None:
    api.replies = [DROP, _ok(201, FACE, {"Idempotent-Replayed": "true"})]
    sleeps: list[float] = []

    face = _client(api, sleeps, max_retries=1).faces.register("c1", b"img", "u1")

    assert face.id == "f1"
    keys = api.keys()
    assert len(keys) == 2
    assert keys[0] and keys[0] == keys[1]
    assert len(sleeps) == 1 and 0 <= sleeps[0] <= 0.5


def test_validation_error_is_not_retried(api: FakeAPI) -> None:
    api.replies = [_err(422, "NO_FACE_DETECTED")]

    with pytest.raises(LiveXFaceApiError) as exc:
        _client(api, [], max_retries=3).faces.register("c1", b"img", "u1")

    assert exc.value.code == "NO_FACE_DETECTED"
    assert len(api.requests) == 1


@pytest.mark.parametrize(
    ("method", "reply"),
    [
        ("register", _ok(201, FACE)),
        ("batch_register", _ok(200, {"succeeded": 1, "failed": 0, "results": []})),
        ("batch_register_async", _ok(202, {"id": "j1", "status": "queued"})),
    ],
)
def test_caller_key_is_sent_and_no_key_sends_no_header(api: FakeAPI, method: str, reply: Any) -> None:
    api.replies = [reply, reply]
    client = _client(api, [])
    call = getattr(client.faces, method)
    args: tuple[Any, ...] = ("c1", b"img", "u1") if method == "register" else ("c1", [{"external_id": "u1", "image": b"a"}])

    call(*args, idempotency_key="key-123")
    call(*args)

    assert api.keys() == ["key-123", None]


def test_new_idempotency_key_returns_distinct_uuid4() -> None:
    a, b = new_idempotency_key(), new_idempotency_key()
    assert a != b
    assert uuid.UUID(a).version == 4 and uuid.UUID(b).version == 4


@pytest.mark.parametrize("first", [DROP, _err(500, "INTERNAL_ERROR")])
def test_unkeyed_post_is_not_retried_on_network_error_or_500(api: FakeAPI, first: Any) -> None:
    api.replies = [first, _ok(200, {"matches": []})]

    with pytest.raises((LiveXFaceNetworkError, LiveXFaceApiError)):
        _client(api, [], max_retries=3).faces.identify("c1", b"img")

    assert len(api.requests) == 1


def test_unkeyed_post_is_retried_on_503(api: FakeAPI) -> None:
    api.replies = [_err(503, "SERVICE_BUSY"), _ok(200, {"matches": []})]
    sleeps: list[float] = []

    _client(api, sleeps, max_retries=1).faces.identify("c1", b"img")

    assert len(api.requests) == 2
    assert len(sleeps) == 1 and 0 <= sleeps[0] <= 0.5
    assert api.keys() == [None, None]


def test_retries_stop_at_max_and_cap_the_delay(api: FakeAPI) -> None:
    api.replies = [_err(503, "SERVICE_BUSY", {"Retry-After": "120"})] * 3
    sleeps: list[float] = []

    with pytest.raises(LiveXFaceApiError) as exc:
        _client(api, sleeps, max_retries=2).faces.get("c1", "f1")

    assert exc.value.status_code == 503
    assert len(api.requests) == 3
    assert sleeps == [60, 60]
