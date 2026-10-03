"""Typed API errors expose the error's details."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from livexface import LiveXFace
from livexface.exceptions import LiveXFaceApiError


def test_api_error_exposes_details(mocker: Any) -> None:
    client = LiveXFace(api_key="lxf_test", base_url="http://api.test/api/v1")
    r = MagicMock()
    r.status_code = 422
    r.ok = False
    r.json.return_value = {
        "success": False,
        "requestId": "r-1",
        "error": {"code": "MULTIPLE_FACES", "message": "multiple faces detected", "details": {"faceCount": 2, "faces": []}},
    }
    mocker.patch.object(client._session, "request", return_value=r)

    with pytest.raises(LiveXFaceApiError) as exc:
        client.faces.register("col", b"img", external_id="a")

    assert exc.value.code == "MULTIPLE_FACES"
    assert exc.value.details == {"faceCount": 2, "faces": []}
    assert exc.value.request_id == "r-1"
