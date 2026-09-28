"""Tests for active liveness and liveness-token enrolment."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from livexface import ActiveLivenessResult, LiveXFace

BASE = "http://api.test/api/v1"


def _resp(data: Any, status: int = 200) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.ok = status < 400
    r.json.return_value = {"success": True, "data": data}
    return r


FACE = {"id": "f1", "collectionId": "c1", "externalId": "u1", "createdAt": "2026-09-28T00:00:00Z"}


@pytest.fixture
def client() -> LiveXFace:
    return LiveXFace(api_key="lxf_test", base_url=BASE)


def test_active_liveness_sends_frames_and_parses_token(client: LiveXFace, mocker: Any) -> None:
    data = {
        "isLive": True,
        "overallScore": 0.93,
        "framesAnalyzed": 6,
        "framesWithFace": 6,
        "challenges": {
            "blink": {"passed": True, "available": True, "blinkCount": 2},
            "headTurn": {"passed": True, "available": True, "yawRange": 31.5},
            "passiveAntispoof": {"passed": True, "available": True, "score": 0.97},
        },
        "livenessToken": "tok_abc",
        "livenessTokenExpiresAt": "2026-09-28T10:05:00Z",
    }
    req = mocker.patch.object(client._session, "request", return_value=_resp(data))

    result = client.faces.active_liveness("c1", [b"img%d" % i for i in range(6)])

    method, url = req.call_args.args
    assert method == "POST"
    assert url == f"{BASE}/collections/c1/active-liveness"
    files = req.call_args.kwargs["files"]
    assert list(files) == [f"frame_{i}" for i in range(6)]
    assert files["frame_3"][1] == b"img3"
    assert isinstance(result, ActiveLivenessResult)
    assert result.is_live is True
    assert result.liveness_token == "tok_abc"
    assert result.liveness_token_expires_at == "2026-09-28T10:05:00Z"
    assert result.blink.passed is True
    assert result.blink.details == {"blinkCount": 2}
    assert result.head_turn.details["yawRange"] == 31.5


def test_active_liveness_failed_has_no_token(client: LiveXFace, mocker: Any) -> None:
    data = {
        "isLive": False,
        "overallScore": 0.2,
        "framesAnalyzed": 5,
        "framesWithFace": 5,
        "challenges": {
            "blink": {"passed": False, "available": True},
            "headTurn": {"passed": None, "available": False},
            "passiveAntispoof": {"passed": True, "available": True},
        },
    }
    mocker.patch.object(client._session, "request", return_value=_resp(data))

    result = client.faces.active_liveness("c1", [b"x"] * 5)

    assert result.is_live is False
    assert result.liveness_token is None
    assert result.liveness_token_expires_at is None
    assert result.blink.passed is False
    assert result.head_turn.passed is None
    assert result.head_turn.available is False


def test_register_sends_liveness_token_when_given(client: LiveXFace, mocker: Any) -> None:
    req = mocker.patch.object(client._session, "request", return_value=_resp(FACE))

    client.faces.register("c1", b"img", "u1", liveness_token="tok_abc")
    assert req.call_args.kwargs["data"]["liveness_token"] == "tok_abc"

    client.faces.register("c1", b"img", "u1")
    assert "liveness_token" not in req.call_args.kwargs["data"]


@pytest.mark.parametrize(
    ("method", "path", "data"),
    [
        ("batch_register", "/faces/batch", {"succeeded": 2, "failed": 0, "results": []}),
        (
            "batch_register_async",
            "/faces/batch-async",
            {"id": "j1", "status": "queued"},
        ),
    ],
)
def test_batch_entries_serialize_liveness_token(
    client: LiveXFace, mocker: Any, method: str, path: str, data: dict[str, Any]
) -> None:
    req = mocker.patch.object(client._session, "request", return_value=_resp(data))

    getattr(client.faces, method)("c1", [
        {"external_id": "u1", "image": b"a", "liveness_token": "tok_1"},
        {"external_id": "u2", "image": b"b"},
    ])

    assert req.call_args.args[1] == f"{BASE}/collections/c1{path}"
    entries = json.loads(req.call_args.kwargs["data"]["entries"])
    assert entries[0] == {"externalId": "u1", "metadata": {}, "livenessToken": "tok_1"}
    assert entries[1] == {"externalId": "u2", "metadata": {}}
