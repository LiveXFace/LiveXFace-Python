"""Typed dataclasses for LiveXFace API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
class CrossCollectionSearchMatch(FaceMatch):
    collection_id: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CrossCollectionSearchMatch":
        return cls(
            face_id=d.get("faceId", ""),
            external_id=d.get("externalId", ""),
            confidence=float(d.get("confidence", 0.0)),
            metadata=d.get("metadata"),
            collection_id=d.get("collectionId", ""),
        )


@dataclass
class SkippedCollection:
    id: str
    name: str
    reason: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SkippedCollection":
        return cls(
            id=d.get("id", ""),
            name=d.get("name", ""),
            reason=d.get("reason", ""),
        )


@dataclass
class CrossCollectionSearchResult:
    matches: list[CrossCollectionSearchMatch]
    query_time_ms: int
    collections_searched: int
    skipped_collections: list[SkippedCollection]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CrossCollectionSearchResult":
        return cls(
            matches=[CrossCollectionSearchMatch.from_dict(m) for m in d.get("matches", [])],
            query_time_ms=d.get("queryTimeMs", 0),
            collections_searched=d.get("collectionsSearched", 0),
            skipped_collections=[
                SkippedCollection.from_dict(c) for c in d.get("skippedCollections", [])
            ],
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
class LivenessChallenge:
    """One challenge of an active liveness check (blink, head turn, passive
    anti-spoof).

    ``passed`` is None when the challenge could not be evaluated. Metric keys
    beyond ``passed`` and ``available`` vary per challenge and are kept as-is
    in ``details``.
    """

    passed: bool | None
    available: bool
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LivenessChallenge":
        passed = d.get("passed")
        return cls(
            passed=None if passed is None else bool(passed),
            available=bool(d.get("available", False)),
            details={k: v for k, v in d.items() if k not in ("passed", "available")},
        )


@dataclass
class ActiveLivenessResult:
    """Result of a stateless active (multi-frame) liveness check.

    A verdict only: it carries no liveness token. To enrol into a collection
    that requires liveness, complete a liveness session instead.
    """

    is_live: bool
    overall_score: float
    frames_analyzed: int
    frames_with_face: int
    blink: LivenessChallenge
    head_turn: LivenessChallenge
    passive_antispoof: LivenessChallenge

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActiveLivenessResult":
        ch = d.get("challenges") or {}
        return cls(
            is_live=bool(d.get("isLive", False)),
            overall_score=float(d.get("overallScore", 0.0)),
            frames_analyzed=int(d.get("framesAnalyzed", 0)),
            frames_with_face=int(d.get("framesWithFace", 0)),
            blink=LivenessChallenge.from_dict(ch.get("blink") or {}),
            head_turn=LivenessChallenge.from_dict(ch.get("headTurn") or {}),
            passive_antispoof=LivenessChallenge.from_dict(ch.get("passiveAntispoof") or {}),
        )


@dataclass
class LivenessSession:
    """A liveness session: the steps the person must perform, in order.

    Each entry of ``challenges`` is ``blink``, ``turn_left`` or ``turn_right``
    (the person's own left and right). Submit the frames with
    :meth:`~livexface.client.FacesResource.complete_liveness_session` before
    ``expires_at`` (RFC 3339).
    """

    session_id: str
    challenges: list[str]
    expires_at: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LivenessSession":
        return cls(
            session_id=d["sessionId"],
            challenges=[c.get("type", "") for c in d.get("challenges") or []],
            expires_at=d.get("expiresAt", ""),
        )


@dataclass
class LivenessStep:
    """One step of a completed liveness session and whether it was performed."""

    type: str
    passed: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LivenessStep":
        return cls(type=d.get("type", ""), passed=bool(d.get("passed", False)))


@dataclass
class LivenessSessionResult(ActiveLivenessResult):
    """Result of completing a liveness session: the active check's fields plus
    ``steps``, the session's challenges in order.

    ``liveness_token`` and ``liveness_token_expires_at`` (RFC 3339) are set only
    when the session passed.
    """

    steps: list[LivenessStep] = field(default_factory=list)
    liveness_token: str | None = None
    liveness_token_expires_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LivenessSessionResult":
        return cls(
            **vars(ActiveLivenessResult.from_dict(d)),
            steps=[LivenessStep.from_dict(s) for s in d.get("steps") or []],
            liveness_token=d.get("livenessToken") or None,
            liveness_token_expires_at=d.get("livenessTokenExpiresAt") or None,
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
