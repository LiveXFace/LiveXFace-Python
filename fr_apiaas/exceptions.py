class FRApiError(Exception):
    """Raised when the FR-APIaaS server returns an error response."""

    def __init__(self, code: str, message: str, status_code: int, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.request_id = request_id

    def __repr__(self) -> str:
        return f"FRApiError(code={self.code!r}, status_code={self.status_code}, message={str(self)!r})"


class FRNetworkError(Exception):
    """Raised when a network-level error occurs (timeout, connection refused, etc.)."""

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def __repr__(self) -> str:
        return f"FRNetworkError(message={str(self)!r})"
