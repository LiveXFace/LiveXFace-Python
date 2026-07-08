"""Idemity Python SDK — Face Recognition as a Service."""

from .client import Idemity
from .exceptions import IdemityApiError, IdemityNetworkError
from .types import (
    FaceCollection,
    Face,
    VerifyResult,
    FaceMatch,
    IdentifyResult,
    LivenessResult,
    BatchResponse,
    BatchDeleteResponse,
    FaceAttributes,
    AttributesResult,
    BatchJobResult,
    BatchJob,
)

__version__ = "0.1.0"
__all__ = [
    "Idemity",
    "IdemityApiError",
    "IdemityNetworkError",
    "FaceCollection",
    "Face",
    "VerifyResult",
    "FaceMatch",
    "IdentifyResult",
    "LivenessResult",
    "BatchResponse",
    "BatchDeleteResponse",
    "FaceAttributes",
    "AttributesResult",
    "BatchJobResult",
    "BatchJob",
]
