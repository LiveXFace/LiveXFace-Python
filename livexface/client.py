"""Main client for the LiveXFace Python SDK."""

from __future__ import annotations

import builtins
import json
import random
import time
import uuid
from pathlib import Path
from typing import Any, Callable, IO, Sequence, Union

import requests
from requests import Response

from .exceptions import LiveXFaceApiError, LiveXFaceNetworkError
from .types import (
    Face,
    VerifyResult,
    IdentifyResult,
    CrossCollectionSearchResult,
    LivenessResult,
    ActiveLivenessResult,
    LivenessSession,
    LivenessSessionResult,
    BatchResponse,
    BatchDeleteResponse,
    AttributesResult,
    BatchJob,
)

DEFAULT_BASE_URL = "http://localhost:8080/api/v1"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRY_DELAY = 60.0

ImageInput = Union[bytes, str, Path, IO[bytes]]

# Repeating these is harmless, so a network error or a 5xx may be retried.
_SAFE_METHODS = frozenset({"GET", "PATCH", "DELETE"})


def new_idempotency_key() -> str:
    """Return a random key (UUID v4) for the ``idempotency_key`` argument."""
    return str(uuid.uuid4())


def _retry_after(resp: Response) -> int | None:
    value = resp.headers.get("Retry-After")
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    return None


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


def _frame_files(frames: Sequence[ImageInput]) -> dict[str, Any]:
    return {f"frame_{i}": _to_bytes_tuple(frame, f"frame_{i}.jpg") for i, frame in enumerate(frames)}


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
        max_retries: int = 0,
        max_retry_delay: float = DEFAULT_MAX_RETRY_DELAY,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """
        :param max_retries: Retries after the first attempt; 0 (the default)
            turns retries off. A 429 or 503 is retried after its
            ``Retry-After`` (or an exponential backoff with jitter); a network
            error or another 5xx only for GET, PATCH and DELETE calls and for
            calls that carry an idempotency key. Other 4xx are never retried.
            :meth:`FacesResource.complete_liveness_session` is retried on a
            429 only: a session is judged once.
        :param max_retry_delay: Upper bound, in seconds, of one wait between
            attempts.
        :param sleep: Called with the delay before each retry; tests replace it.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self._sleep = sleep
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": api_key})

        self.faces = FacesResource(self)

    def _request(
        self,
        method: str,
        endpoint: str,
        idempotency_key: str | None = None,
        single_use: bool = False,
        **kwargs: Any,
    ) -> Any:
        """:param single_use: The request uses up a server-side resource once it
        reaches the handler, whatever the outcome (a liveness session), so only
        a 429, which is rejected before that, is retried."""
        if idempotency_key:
            kwargs["headers"] = {"Idempotency-Key": idempotency_key}
        # A keyed request is safe to repeat: the API replays the first answer.
        safe = method in _SAFE_METHODS or bool(idempotency_key)
        busy = (429,) if single_use else (429, 503)
        attempt = 0
        while True:
            try:
                return self._send(method, endpoint, **kwargs)
            except LiveXFaceApiError as exc:
                retryable = exc.status_code in busy or (exc.status_code >= 500 and safe)
                if not retryable or attempt >= self.max_retries:
                    raise
                wait: float | None = exc.retry_after
            except LiveXFaceNetworkError:
                if not safe or attempt >= self.max_retries:
                    raise
                wait = None
            if wait is None:
                wait = random.uniform(0, 0.5 * 2**attempt)
            self._sleep(min(wait, self.max_retry_delay))
            attempt += 1

    def _send(self, method: str, endpoint: str, **kwargs: Any) -> Any:
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
                    f"HTTP_{resp.status_code}",
                    f"Request failed with HTTP {resp.status_code}",
                    resp.status_code,
                    retry_after=_retry_after(resp),
                ) from exc
            raise LiveXFaceApiError("PARSE_ERROR", "Failed to parse response body", resp.status_code) from exc

        if not parsed.get("success") or not resp.ok:
            err = parsed.get("error") or {}
            raise LiveXFaceApiError(
                code=err.get("code", "UNKNOWN_ERROR"),
                message=err.get("message", "An unknown error occurred"),
                status_code=resp.status_code,
                request_id=parsed.get("requestId"),
                details=err.get("details"),
                retry_after=_retry_after(resp),
            )

        return parsed.get("data")


class FacesResource:
    """Face enrollment and recognition operations."""

    def __init__(self, client: LiveXFace) -> None:
        self._c = client

    def _key(self, idempotency_key: str | None) -> str | None:
        # With retries on, every attempt of one call must carry the same key,
        # so a call without one gets its own.
        if idempotency_key is None and self._c.max_retries > 0:
            return new_idempotency_key()
        return idempotency_key

    def register(
        self,
        collection_id: str,
        image: ImageInput,
        external_id: str,
        metadata: dict[str, Any] | None = None,
        liveness_token: str | None = None,
        idempotency_key: str | None = None,
    ) -> Face:
        """Register a face in a collection.

        :param liveness_token: Token from a passed liveness session (see
            :meth:`complete_liveness_session`). Required when the collection requires liveness on enrolment;
            single-use, valid for 5 minutes, and bound to the collection.
        :param idempotency_key: Sent as ``Idempotency-Key``; repeating the call
            with the same key within 24 hours replays the first answer instead
            of enrolling again. See :func:`new_idempotency_key`.
        """
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        data: dict[str, str] = {"external_id": external_id}
        if metadata:
            data["metadata"] = json.dumps(metadata)
        if liveness_token:
            data["liveness_token"] = liveness_token
        resp = self._c._request(
            "POST",
            f"/collections/{collection_id}/faces",
            idempotency_key=self._key(idempotency_key),
            files=files,
            data=data,
        )
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

    def search(
        self,
        image: ImageInput,
        collection_ids: Sequence[str] | None = None,
        top_k: int = 5,
        threshold: float | None = None,
    ) -> CrossCollectionSearchResult:
        """Search for matching faces across multiple or all collections."""
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        data: dict[str, str] = {"top_k": str(top_k)}
        if collection_ids:
            data["collection_ids"] = ",".join(collection_ids)
        if threshold is not None:
            data["threshold"] = str(threshold)
        resp = self._c._request("POST", "/search", files=files, data=data)
        return CrossCollectionSearchResult.from_dict(resp)

    def liveness(self, collection_id: str, image: ImageInput) -> LivenessResult:
        """Passive liveness detection — check whether the face in the image is live."""
        fname, fbytes, ftype = _to_bytes_tuple(image)
        files = {"image": (fname, fbytes, ftype)}
        resp = self._c._request(
            "POST", f"/collections/{collection_id}/liveness", files=files
        )
        return LivenessResult.from_dict(resp)

    def active_liveness(
        self,
        collection_id: str,
        frames: Sequence[ImageInput],
    ) -> ActiveLivenessResult:
        """
        Active liveness — check a sequence of frames for a blink, a head turn
        and passive anti-spoofing.

        Send 5 to 50 frames (JPEG/PNG) captured in order. This stateless check
        returns a verdict only and issues no liveness token; to enrol into a
        collection that requires liveness, use :meth:`create_liveness_session`
        and :meth:`complete_liveness_session`.
        """
        resp = self._c._request(
            "POST", f"/collections/{collection_id}/active-liveness", files=_frame_files(frames)
        )
        return ActiveLivenessResult.from_dict(resp)

    def create_liveness_session(self, collection_id: str) -> LivenessSession:
        """
        Start a liveness session bound to this collection. The server picks the
        steps the person must perform, in order (``blink``, ``turn_left``,
        ``turn_right``; the person's own left and right). Show them, capture
        frames while they are performed, and submit the frames with
        :meth:`complete_liveness_session` before ``expires_at``.
        """
        resp = self._c._request("POST", f"/collections/{collection_id}/liveness-sessions")
        return LivenessSession.from_dict(resp)

    def complete_liveness_session(
        self,
        collection_id: str,
        session_id: str,
        frames: Sequence[ImageInput],
        mirrored: bool = False,
    ) -> LivenessSessionResult:
        """
        Submit 5 to 50 frames (JPEG/PNG), captured in order, for a liveness
        session. A session is judged once: any submission except one with
        fewer than 5 frames uses it up, so this call is never retried on a
        network error or a 5xx. When the session passes, the result carries a
        ``liveness_token`` to pass to :meth:`register` or a batch entry:
        single-use, valid for 5 minutes, and bound to this collection.

        :param mirrored: True when the frames are horizontally mirrored, as a
            selfie preview is.

        Raises :class:`LiveXFaceApiError` with code ``LIVENESS_SESSION_INVALID``
        (422) when the session is unknown, expired, already submitted or bound
        to another collection; create a new session then.
        """
        resp = self._c._request(
            "POST",
            f"/collections/{collection_id}/liveness-sessions/{session_id}",
            single_use=True,
            files=_frame_files(frames),
            data={"mirrored": "true" if mirrored else "false"},
        )
        return LivenessSessionResult.from_dict(resp)

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
        items: builtins.list[dict[str, Any]],
        idempotency_key: str | None = None,
    ) -> BatchResponse:
        """
        Batch register up to 20 faces in a single request.

        Each item must have ``image`` (ImageInput) and ``external_id`` (str).
        Optional ``metadata`` dict and ``liveness_token`` (str, from
        :meth:`complete_liveness_session`) are also supported. ``idempotency_key`` works
        as in :meth:`register`.

        Example::

            client.faces.batch_register("col_id", [
                {"external_id": "user_1", "image": open("user1.jpg", "rb")},
                {"external_id": "user_2", "image": open("user2.jpg", "rb"), "metadata": {"name": "Alice"}},
            ])
        """
        files: dict[str, Any] = {}
        entries: builtins.list[dict[str, Any]] = []
        for i, item in enumerate(items):
            fname, fbytes, ftype = _to_bytes_tuple(item["image"])
            files[f"images[{i}]"] = (fname, fbytes, ftype)
            entry: dict[str, Any] = {
                "externalId": item["external_id"],
                "metadata": item.get("metadata", {}),
            }
            if item.get("liveness_token"):
                entry["livenessToken"] = item["liveness_token"]
            entries.append(entry)
        resp = self._c._request(
            "POST",
            f"/collections/{collection_id}/faces/batch",
            idempotency_key=self._key(idempotency_key),
            files=files,
            data={"entries": json.dumps(entries)},
        )
        return BatchResponse.from_dict(resp)

    def batch_delete(self, collection_id: str, face_ids: builtins.list[str]) -> BatchDeleteResponse:
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
        items: builtins.list[dict[str, Any]],
        idempotency_key: str | None = None,
    ) -> BatchJob:
        """
        Submit up to 100 faces for asynchronous registration. Returns a job
        immediately; poll :meth:`get_batch_job` until ``status`` is ``done``
        or ``failed``.

        Each item must have ``image`` (ImageInput) and ``external_id`` (str).
        Optional ``metadata`` dict and ``liveness_token`` (str, from
        :meth:`complete_liveness_session`) are also supported. ``idempotency_key`` works
        as in :meth:`register`.
        """
        files: dict[str, Any] = {}
        entries: builtins.list[dict[str, Any]] = []
        for i, item in enumerate(items):
            fname, fbytes, ftype = _to_bytes_tuple(item["image"])
            files[f"images[{i}]"] = (fname, fbytes, ftype)
            entry: dict[str, Any] = {
                "externalId": item["external_id"],
                "metadata": item.get("metadata", {}),
            }
            if item.get("liveness_token"):
                entry["livenessToken"] = item["liveness_token"]
            entries.append(entry)
        resp = self._c._request(
            "POST",
            f"/collections/{collection_id}/faces/batch-async",
            idempotency_key=self._key(idempotency_key),
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
