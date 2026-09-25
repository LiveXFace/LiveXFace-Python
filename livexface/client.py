"""Main client for the LiveXFace Python SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, IO, Union

import requests
from requests import Response

from .exceptions import LiveXFaceApiError, LiveXFaceNetworkError
from .types import (
    Face,
    VerifyResult,
    IdentifyResult,
    LivenessResult,
    BatchResponse,
    BatchDeleteResponse,
    AttributesResult,
    BatchJob,
)

DEFAULT_BASE_URL = "http://localhost:8080/api/v1"
DEFAULT_TIMEOUT = 30

ImageInput = Union[bytes, str, Path, IO[bytes]]


def _to_bytes_tuple(src: ImageInput, filename: str = "image.jpg") -> tuple[str, bytes, str]:
    """Convert an image source to a (filename, bytes, content_type) tuple for requests."""
    if isinstance(src, bytes):
        return filename, src, "image/jpeg"
    if isinstance(src, (str, Path)):
        p = Path(src)
        data = p.read_bytes()
        suffix = p.suffix.lstrip(".") or "jpeg"
        return p.name, data, f"image/{suffix}"
    # file-like object
    return filename, src.read(), "image/jpeg"


class LiveXFace:
    """
    Main client for the LiveXFace recognition API.

    All face operations use API key authentication scoped to a specific
    collection. Collections themselves are created and managed in the
    dashboard; the API has no endpoints for that, so neither does this client.

    Example::

        from livexface import LiveXFace

        client = LiveXFace(api_key="lxf_live_xxxx")

        result = client.faces.identify(
            collection_id="...",
            image=open("face.jpg", "rb"),
            top_k=3,
        )
        for match in result.matches:
            print(match.external_id, match.confidence)
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": api_key})

        self.faces = FacesResource(self)

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{endpoint}"
        try:
            resp: Response = self._session.request(
                method, url, timeout=self.timeout, **kwargs
            )
        except requests.exceptions.Timeout as exc:
            raise LiveXFaceNetworkError(f"Request timed out after {self.timeout}s", exc) from exc
        except requests.exceptions.ConnectionError as exc:
            raise LiveXFaceNetworkError(f"Connection failed: {exc}", exc) from exc

        # A delete answers 204 with no body. Parsing it used to raise
        # PARSE_ERROR, so every successful delete looked like a failure.
        if resp.status_code == 204:
            return None

        try:
            parsed: dict[str, Any] = resp.json()
        except ValueError as exc:
            # An unknown route answers with a plain-text 404, not the JSON
            # envelope; report the HTTP status rather than a parse failure.
            if not resp.ok:
                raise LiveXFaceApiError(
                    f"HTTP_{resp.status_code}", f"Request failed with HTTP {resp.status_code}", resp.status_code
                ) from exc
            raise LiveXFaceApiError("PARSE_ERROR", "Failed to parse response body", resp.status_code) from exc

        if not parsed.get("success") or not resp.ok:
            err = parsed.get("error") or {}
            raise LiveXFaceApiError(
                code=err.get("code", "UNKNOWN_ERROR"),
                message=err.get("message", "An unknown error occurred"),
                status_code=resp.status_code,
                request_id=parsed.get("requestId"),
            )

        return parsed.get("data")


class FacesResource:
    """Face enrollment and recognition operations."""

    def __init__(self, client: LiveXFace) -> None:
        self._c = client

    def register(
        self,
        collection_id: str,
        image: ImageInput,
        external_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> Face:
        """Register a face in a collection."""
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        data: dict[str, str] = {"external_id": external_id}
        if metadata:
            data["metadata"] = json.dumps(metadata)
        resp = self._c._request("POST", f"/collections/{collection_id}/faces", files=files, data=data)
        return Face.from_dict(resp)

    def list(
        self,
        collection_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Face], int]:
        """List faces in a collection. Returns (faces, total)."""
        resp = self._c._request(
            "GET",
            f"/collections/{collection_id}/faces",
            params={"limit": limit, "offset": offset},
        )
        faces = [Face.from_dict(f) for f in (resp.get("faces") or [])]
        total = resp.get("total", len(faces))
        return faces, total

    def get(self, collection_id: str, face_id: str) -> Face:
        """Get a face by ID."""
        resp = self._c._request("GET", f"/collections/{collection_id}/faces/{face_id}")
        return Face.from_dict(resp)

    def get_by_external_id(self, collection_id: str, external_id: str) -> Face:
        """Get a face by external ID. Returns the first match.

        This used to call /faces/by-external-id/{id}, a route the API does not
        have, so it always failed. The list endpoint filters by external ID,
        and answers with a bare list when it does.
        """
        resp = self._c._request(
            "GET", f"/collections/{collection_id}/faces", params={"external_id": external_id}
        )
        items = resp if isinstance(resp, list) else []
        if not items:
            raise LiveXFaceApiError("FACE_NOT_FOUND", f'No face found with external_id "{external_id}"', 404)
        return Face.from_dict(items[0])

    def delete(self, collection_id: str, face_id: str) -> None:
        """Delete a face from a collection."""
        self._c._request("DELETE", f"/collections/{collection_id}/faces/{face_id}")

    def verify(
        self,
        collection_id: str,
        image: ImageInput,
        face_id: str,
        threshold: float | None = None,
    ) -> VerifyResult:
        """
        1:1 Verify — compare a query image against a stored face.

        :param face_id: ID of the stored face to compare against.
        :param threshold: Similarity threshold (0–1). Defaults to server-side value.
        """
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        data: dict[str, str] = {"face_id": face_id}
        if threshold is not None:
            data["threshold"] = str(threshold)
        resp = self._c._request(
            "POST", f"/collections/{collection_id}/verify", files=files, data=data
        )
        return VerifyResult.from_dict(resp)

    def identify(
        self,
        collection_id: str,
        image: ImageInput,
        top_k: int = 5,
        threshold: float | None = None,
    ) -> IdentifyResult:
        """
        1:N Identify — search a collection for the best matching faces.

        Identify does not check liveness; call :meth:`liveness` for that. (A
        ``live`` flag used to be offered here and documented as running
        liveness detection. The API ignores it.)

        :param top_k: Number of top matches to return (max 100).
        :param threshold: Minimum similarity to include in results.
        """
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        data: dict[str, str] = {"top_k": str(top_k)}
        if threshold is not None:
            data["threshold"] = str(threshold)
        resp = self._c._request(
            "POST", f"/collections/{collection_id}/identify", files=files, data=data
        )
        return IdentifyResult.from_dict(resp)

    def liveness(self, collection_id: str, image: ImageInput) -> LivenessResult:
        """Passive liveness detection — check whether the face in the image is live."""
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        resp = self._c._request(
            "POST", f"/collections/{collection_id}/liveness", files=files
        )
        return LivenessResult.from_dict(resp)

    def compare(
        self,
        image1: ImageInput,
        image2: ImageInput,
        threshold: float | None = None,
    ) -> VerifyResult:
        """Face comparison — compare two images without enrolling into a collection."""
        f1n, f1b, f1t = _to_bytes_tuple(image1, "image1.jpg")
        f2n, f2b, f2t = _to_bytes_tuple(image2, "image2.jpg")
        files = {
            "image1": (f1n, f1b, f1t),
            "image2": (f2n, f2b, f2t),
        }
        data: dict[str, str] = {}
        if threshold is not None:
            data["threshold"] = str(threshold)
        resp = self._c._request("POST", "/compare", files=files, data=data)
        return VerifyResult.from_dict(resp)

    def batch_register(
        self,
        collection_id: str,
        items: list[dict[str, Any]],
    ) -> BatchResponse:
        """
        Batch register up to 20 faces in a single request.

        Each item must have ``image`` (ImageInput) and ``external_id`` (str).
        Optional ``metadata`` dict is also supported.

        Example::

            client.faces.batch_register("col_id", [
                {"external_id": "user_1", "image": open("user1.jpg", "rb")},
                {"external_id": "user_2", "image": open("user2.jpg", "rb"), "metadata": {"name": "Alice"}},
            ])
        """
        files: dict[str, Any] = {}
        entries = []
        for i, item in enumerate(items):
            fname, fbytes, ftype = _to_bytes_tuple(item["image"])
            files[f"images[{i}]"] = (fname, fbytes, ftype)
            entries.append({
                "externalId": item["external_id"],
                "metadata": item.get("metadata", {}),
            })
        resp = self._c._request(
            "POST",
            f"/collections/{collection_id}/faces/batch",
            files=files,
            data={"entries": json.dumps(entries)},
        )
        return BatchResponse.from_dict(resp)

    def batch_delete(self, collection_id: str, face_ids: list[str]) -> BatchDeleteResponse:
        """Batch delete up to 100 faces by their IDs."""
        resp = self._c._request(
            "DELETE",
            f"/collections/{collection_id}/faces/batch",
            json={"faceIds": face_ids},
        )
        return BatchDeleteResponse.from_dict(resp)

    def attributes(self, collection_id: str, image: ImageInput) -> AttributesResult:
        """Detect face attributes (age, gender, emotion, glasses, mask, head
        pose, landmarks) for all faces in an image. No face is enrolled."""
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        resp = self._c._request(
            "POST", f"/collections/{collection_id}/attributes", files=files
        )
        return AttributesResult.from_dict(resp)

    def batch_register_async(
        self,
        collection_id: str,
        items: list[dict[str, Any]],
    ) -> BatchJob:
        """
        Submit up to 100 faces for asynchronous registration. Returns a job
        immediately; poll :meth:`get_batch_job` until ``status`` is ``done``
        or ``failed``.

        Each item must have ``image`` (ImageInput) and ``external_id`` (str).
        Optional ``metadata`` dict is also supported.
        """
        files: dict[str, Any] = {}
        entries = []
        for i, item in enumerate(items):
            fname, fbytes, ftype = _to_bytes_tuple(item["image"])
            files[f"images[{i}]"] = (fname, fbytes, ftype)
            entries.append({
                "externalId": item["external_id"],
                "metadata": item.get("metadata", {}),
            })
        resp = self._c._request(
            "POST",
            f"/collections/{collection_id}/faces/batch-async",
            files=files,
            data={"entries": json.dumps(entries)},
        )
        return BatchJob.from_dict(resp)

    def get_batch_job(self, collection_id: str, job_id: str) -> BatchJob:
        """Fetch the status (and per-image results) of an async batch job."""
        resp = self._c._request(
            "GET", f"/collections/{collection_id}/batch/{job_id}"
        )
        return BatchJob.from_dict(resp)
