"""Serupa Python SDK — Face Recognition as a Service."""

from .client import Serupa
from .exceptions import SerupaApiError, SerupaNetworkError
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
    "Serupa",
    "SerupaApiError",
    "SerupaNetworkError",
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
