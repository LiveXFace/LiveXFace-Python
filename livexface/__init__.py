"""LiveXFace Python SDK — Face Recognition as a Service."""

from .client import LiveXFace
from .exceptions import LiveXFaceApiError, LiveXFaceNetworkError
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
    "LiveXFace",
    "LiveXFaceApiError",
    "LiveXFaceNetworkError",
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
