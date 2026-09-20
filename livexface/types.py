"""Typed dataclasses for LiveXFace API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FaceCollection:
    id: str
    organization_id: str
    name: str
    face_count: int
    created_at: str
    updated_at: str
    description: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FaceCollection":
        return cls(
            id=d["id"],
            organization_id=d["organizationId"],
            name=d["name"],
            face_count=d.get("faceCount", 0),
            created_at=d["createdAt"],
            updated_at=d["updatedAt"],
            description=d.get("description", ""),
        )


@dataclass
class Face:
    id: str
    collection_id: str
    external_id: str
    metadata: dict[str, Any]
    image_url: str
    created_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Face":
        return cls(
            id=d["id"],
            collection_id=d["collectionId"],
            external_id=d.get("externalId", ""),
            metadata=d.get("metadata", {}),
            image_url=d.get("imageUrl", ""),
            created_at=d["createdAt"],
            updated_at=d.get("updatedAt", d["createdAt"]),
        )


@dataclass
class VerifyResult:
    match: bool
    confidence: float
    threshold_used: float
    face_id: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "VerifyResult":
        return cls(
            match=d["match"],
            confidence=d["confidence"],
            threshold_used=d["thresholdUsed"],
            face_id=d.get("faceId"),
        )


@dataclass
class FaceMatch:
    """One result from an identify call.

    The API returns a flat match — id, external id and confidence — not a
    nested face object. This class used to read d["face"] and d["similarity"],
    neither of which the endpoint has ever sent, so every identify call raised
    KeyError.
    """

    face_id: str
    external_id: str
    confidence: float
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FaceMatch":
        return cls(
            face_id=d.get("faceId", ""),
            external_id=d.get("externalId", ""),
            confidence=float(d.get("confidence", 0.0)),
            metadata=d.get("metadata"),
        )


@dataclass
class IdentifyResult:
    matches: list[FaceMatch]
    query_time_ms: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IdentifyResult":
        return cls(
            matches=[FaceMatch.from_dict(m) for m in d.get("matches", [])],
            query_time_ms=d.get("queryTimeMs", 0),
        )


@dataclass
class LivenessResult:
    """Result of a passive liveness check.

    Mirrors what the endpoint actually sends. The previous version required a
    `confidence` and a `spoof_score`, neither of which appears in the response,
    so every liveness call raised KeyError.
    """

    is_live: bool
    liveness_score: float
    face_detected: bool = False
    face_count: int = 0

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LivenessResult":
        return cls(
            is_live=bool(d.get("isLive", False)),
            liveness_score=float(d.get("livenessScore", 0.0)),
            face_detected=bool(d.get("faceDetected", False)),
            face_count=int(d.get("faceCount", 0)),
        )


@dataclass
class BatchFaceResult:
    external_id: str
    face: Face | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchFaceResult":
        return cls(
            external_id=d["externalId"],
            face=Face.from_dict(d["face"]) if d.get("face") else None,
            error=d.get("error"),
        )


@dataclass
class BatchResponse:
    succeeded: int
    failed: int
    results: list[BatchFaceResult] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchResponse":
        return cls(
            succeeded=d["succeeded"],
            failed=d["failed"],
            results=[BatchFaceResult.from_dict(r) for r in d.get("results", [])],
        )


@dataclass
class BatchDeleteResult:
    face_id: str
    error: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchDeleteResult":
        return cls(face_id=d["faceId"], error=d.get("error"))


@dataclass
class BatchDeleteResponse:
    succeeded: int
    failed: int
    results: list[BatchDeleteResult] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchDeleteResponse":
        return cls(
            succeeded=d["succeeded"],
            failed=d["failed"],
            results=[BatchDeleteResult.from_dict(r) for r in d.get("results", [])],
        )

@dataclass
class FaceAttributes:
    """Attributes of one detected face (age, gender, emotion, glasses, mask, pose)."""

    age: int
    gender: str
    det_score: float
    bbox: dict[str, int]
    landmarks_5pt: list[list[float]] | None = None
    landmarks_106: list[list[float]] | None = None
    head_pose: dict[str, float] | None = None
    emotion: dict[str, Any] | None = None
    glasses: dict[str, Any] | None = None
    mask: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FaceAttributes":
        return cls(
            age=d.get("age", 0),
            gender=d.get("gender", ""),
            det_score=d.get("detScore", 0.0),
            bbox=d.get("bbox", {}),
            landmarks_5pt=d.get("landmarks5pt"),
            landmarks_106=d.get("landmarks106"),
            head_pose=d.get("headPose"),
            emotion=d.get("emotion"),
            glasses=d.get("glasses"),
            mask=d.get("mask"),
        )


@dataclass
class AttributesResult:
    face_detected: bool
    face_count: int
    faces: list[FaceAttributes] = field(default_factory=list)
    primary: FaceAttributes | None = None
    image_size: dict[str, int] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AttributesResult":
        return cls(
            face_detected=d.get("faceDetected", False),
            face_count=d.get("faceCount", 0),
            faces=[FaceAttributes.from_dict(f) for f in d.get("faces", [])],
            primary=FaceAttributes.from_dict(d["primary"]) if d.get("primary") else None,
            image_size=d.get("imageSize"),
        )


@dataclass
class BatchJobResult:
    index: int
    external_id: str
    face_id: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchJobResult":
        return cls(
            index=d.get("index", 0),
            external_id=d.get("externalId", ""),
            face_id=d.get("faceId"),
            error=d.get("error"),
        )


@dataclass
class BatchJob:
    """An asynchronous batch registration job. Status: queued|processing|done|failed."""

    id: str
    collection_id: str
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    created_at: str
    updated_at: str
    results: list[BatchJobResult] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchJob":
        return cls(
            id=d["id"],
            collection_id=d.get("collectionId", ""),
            status=d.get("status", ""),
            total=d.get("total", 0),
            processed=d.get("processed", 0),
            succeeded=d.get("succeeded", 0),
            failed=d.get("failed", 0),
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
            results=[BatchJobResult.from_dict(r) for r in d.get("results") or []],
        )
