"""FR-APIaaS Python SDK — Face Recognition as a Service."""

from .client import FRClient
from .exceptions import FRApiError, FRNetworkError
from .types import (
    FaceCollection,
    Face,
    VerifyResult,
    FaceMatch,
    IdentifyResult,
    LivenessResult,
    BatchResponse,
    BatchDeleteResponse,
)

__version__ = "0.1.0"
__all__ = [
    "FRClient",
    "FRApiError",
    "FRNetworkError",
    "FaceCollection",
    "Face",
    "VerifyResult",
    "FaceMatch",
    "IdentifyResult",
    "LivenessResult",
    "BatchResponse",
    "BatchDeleteResponse",
]
