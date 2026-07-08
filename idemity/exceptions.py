class IdemityApiError(Exception):
    """Raised when the Idemity server returns an error response."""

    def __init__(self, code: str, message: str, status_code: int, request_id: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.request_id = request_id

    def __repr__(self) -> str:
        return f"IdemityApiError(code={self.code!r}, status_code={self.status_code}, message={str(self)!r})"


class IdemityNetworkError(Exception):
    """Raised when a network-level error occurs (timeout, connection refused, etc.)."""

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause

    def __repr__(self) -> str:
        return f"IdemityNetworkError(message={str(self)!r})"
