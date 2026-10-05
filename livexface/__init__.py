"""LiveXFace Python SDK — Face Recognition as a Service."""

from .client import LiveXFace, new_idempotency_key
from .exceptions import LiveXFaceApiError, LiveXFaceNetworkError
from .types import (
    Face,
    VerifyResult,
    FaceMatch,
    IdentifyResult,
    CrossCollectionSearchMatch,
    CrossCollectionSearchResult,
    SkippedCollection,
    LivenessResult,
    LivenessChallenge,
    ActiveLivenessResult,
    LivenessSession,
    LivenessStep,
    LivenessSessionResult,
    BatchResponse,
    BatchDeleteResponse,
    FaceAttributes,
    AttributesResult,
    BatchJobResult,
    BatchJob,
)

__version__ = "1.0.0"
# The API contract (`info.version` of /openapi.json) this release is validated against.
CONTRACT_VERSION = "2.0.0"
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
    "CrossCollectionSearchMatch",
    "CrossCollectionSearchResult",
    "SkippedCollection",
    "LivenessResult",
    "LivenessChallenge",
    "ActiveLivenessResult",
    "LivenessSession",
    "LivenessStep",
    "LivenessSessionResult",
    "BatchResponse",
    "BatchDeleteResponse",
    "FaceAttributes",
    "AttributesResult",
    "BatchJobResult",
    "BatchJob",
]
