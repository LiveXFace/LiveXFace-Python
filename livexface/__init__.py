"""LiveXFace Python SDK — Face Recognition as a Service."""

from .client import LiveXFace, new_idempotency_key
from .exceptions import LiveXFaceApiError, LiveXFaceNetworkError
from .types import (
    Face,
    VerifyResult,
    FaceMatch,
    IdentifyResult,
    LivenessResult,
    LivenessChallenge,
    ActiveLivenessResult,
    BatchResponse,
    BatchDeleteResponse,
    FaceAttributes,
    AttributesResult,
    BatchJobResult,
    BatchJob,
)

__version__ = "0.1.0"
# The API contract (`info.version` of /openapi.json) this release is validated against.
CONTRACT_VERSION = "1.0.0"
__all__ = [
    "CONTRACT_VERSION",
    "LiveXFace",
    "new_idempotency_key",
    "LiveXFaceApiError",
    "LiveXFaceNetworkError",
    "Face",
    "VerifyResult",
    "FaceMatch",
    "IdentifyResult",
    "LivenessResult",
    "LivenessChallenge",
    "ActiveLivenessResult",
    "BatchResponse",
    "BatchDeleteResponse",
    "FaceAttributes",
    "AttributesResult",
    "BatchJobResult",
    "BatchJob",
]
