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


def test_search_parses_skips_and_typed_profile_mismatch(mocker: Any) -> None:
    client = LiveXFace(api_key="lxf_test", base_url="http://api.test/api/v1")
    ok = MagicMock(status_code=200, ok=True)
    ok.json.return_value = {"success": True, "data": {"matches": [], "queryTimeMs": 7, "collectionsSearched": 1, "skippedCollections": [{"id": "c2", "name": "Legacy", "reason": "embedding_profile_mismatch"}]}}
    request = mocker.patch.object(client._session, "request", return_value=ok)
    result = client.faces.search(b"img", collection_ids=["c1", "c2"])
    assert result.skipped_collections[0].reason == "embedding_profile_mismatch"
    assert request.call_args.kwargs["data"]["collection_ids"] == "c1,c2"

    conflict = MagicMock(status_code=409, ok=False)
    conflict.json.return_value = {"success": False, "error": {"code": "EMBEDDING_PROFILE_MISMATCH", "message": "no compatible collections"}}
    request.return_value = conflict
    with pytest.raises(LiveXFaceApiError) as exc:
        client.faces.search(b"img")
    assert exc.value.status_code == 409
    assert exc.value.code == "EMBEDDING_PROFILE_MISMATCH"
