"""Tests for active liveness, liveness sessions and liveness-token enrolment."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from livexface import ActiveLivenessResult, LiveXFace, LiveXFaceApiError, LivenessSessionResult

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


def test_active_liveness_sends_frames_and_has_no_token(client: LiveXFace, mocker: Any) -> None:
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
    assert not hasattr(result, "liveness_token")
    assert not hasattr(result, "liveness_token_expires_at")
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
    assert result.blink.passed is False
    assert result.head_turn.passed is None
    assert result.head_turn.available is False


def test_create_liveness_session_returns_challenges(client: LiveXFace, mocker: Any) -> None:
    data = {
        "sessionId": "lvs_1",
        "challenges": [{"type": "turn_left"}, {"type": "blink"}, {"type": "turn_right"}],
        "expiresAt": "2026-09-28T10:01:00Z",
    }
    req = mocker.patch.object(client._session, "request", return_value=_resp(data, 201))

    session = client.faces.create_liveness_session("c1")

    assert req.call_args.args == ("POST", f"{BASE}/collections/c1/liveness-sessions")
    assert "files" not in req.call_args.kwargs and "data" not in req.call_args.kwargs
    assert "headers" not in req.call_args.kwargs  # no idempotency key
    assert session.session_id == "lvs_1"
    assert session.challenges == ["turn_left", "blink", "turn_right"]
    assert session.expires_at == "2026-09-28T10:01:00Z"


SESSION_PASSED = {
    "isLive": True,
    "overallScore": 0.95,
    "framesAnalyzed": 25,
    "framesWithFace": 25,
    "challenges": {
        "blink": {"passed": True, "available": True},
        "headTurn": {"passed": True, "available": True},
        "passiveAntispoof": {"passed": True, "available": True},
    },
    "steps": [{"type": "turn_left", "passed": True}, {"type": "blink", "passed": True}],
    "livenessToken": "tok_abc",
    "livenessTokenExpiresAt": "2026-09-28T10:05:00Z",
}


@pytest.mark.parametrize(("mirrored", "sent"), [(True, "true"), (False, "false")])
def test_complete_liveness_session_sends_frames_and_mirrored_and_parses_token(
    client: LiveXFace, mocker: Any, mirrored: bool, sent: str
) -> None:
    req = mocker.patch.object(client._session, "request", return_value=_resp(SESSION_PASSED))

    result = client.faces.complete_liveness_session("c1", "lvs_1", [b"img%d" % i for i in range(6)], mirrored=mirrored)

    assert req.call_args.args == ("POST", f"{BASE}/collections/c1/liveness-sessions/lvs_1")
    files = req.call_args.kwargs["files"]
    assert list(files) == [f"frame_{i}" for i in range(6)]
    assert files["frame_3"][1] == b"img3"
    assert req.call_args.kwargs["data"] == {"mirrored": sent}
    assert "headers" not in req.call_args.kwargs  # no idempotency key
    assert isinstance(result, LivenessSessionResult)
    assert result.is_live is True
    assert result.blink.passed is True
    assert [(s.type, s.passed) for s in result.steps] == [("turn_left", True), ("blink", True)]
    assert result.liveness_token == "tok_abc"
    assert result.liveness_token_expires_at == "2026-09-28T10:05:00Z"


def test_complete_liveness_session_defaults_to_not_mirrored(client: LiveXFace, mocker: Any) -> None:
    req = mocker.patch.object(client._session, "request", return_value=_resp(SESSION_PASSED))

    client.faces.complete_liveness_session("c1", "lvs_1", [b"x"] * 5)

    assert req.call_args.kwargs["data"] == {"mirrored": "false"}


def test_failed_liveness_session_has_no_token(client: LiveXFace, mocker: Any) -> None:
    data = {
        **SESSION_PASSED,
        "isLive": False,
        "steps": [{"type": "turn_left", "passed": False}, {"type": "blink", "passed": True}],
    }
    del data["livenessToken"], data["livenessTokenExpiresAt"]
    mocker.patch.object(client._session, "request", return_value=_resp(data))

    result = client.faces.complete_liveness_session("c1", "lvs_1", [b"x"] * 5)

    assert result.is_live is False
    assert result.steps[0].passed is False
    assert result.liveness_token is None
    assert result.liveness_token_expires_at is None


def test_invalid_liveness_session_raises_typed_error(client: LiveXFace, mocker: Any) -> None:
    r = MagicMock()
    r.status_code = 422
    r.ok = False
    r.json.return_value = {
        "success": False,
        "requestId": "r-9",
        "error": {"code": "LIVENESS_SESSION_INVALID", "message": "liveness session is invalid or expired"},
    }
    mocker.patch.object(client._session, "request", return_value=r)

    with pytest.raises(LiveXFaceApiError) as exc:
        client.faces.complete_liveness_session("c1", "lvs_gone", [b"x"] * 5)

    assert exc.value.code == "LIVENESS_SESSION_INVALID"
    assert exc.value.status_code == 422
    assert exc.value.request_id == "r-9"


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
