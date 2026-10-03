from __future__ import annotations

from typing import Any


class LiveXFaceApiError(Exception):
    """Raised when the LiveXFace server returns an error response."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        request_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        # Machine-readable context when the API sends it, e.g. faceCount and
        # faces for MULTIPLE_FACES.
        self.details = details

    def __repr__(self) -> str:
        return f"LiveXFaceApiError(code={self.code!r}, status_code={self.status_code}, message={str(self)!r})"


class LiveXFaceNetworkError(Exception):
    """Raised when a network-level error occurs (timeout, connection refused, etc.)."""

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def __repr__(self) -> str:
        return f"LiveXFaceNetworkError(message={str(self)!r})"
