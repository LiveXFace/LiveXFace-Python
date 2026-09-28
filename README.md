<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/logo-white.svg">
    <img src="docs/brand/logo.svg" alt="LiveXFace" width="220">
  </picture>
</p>

# livexface

Official Python SDK for [LiveXFace](https://github.com/livexface/livexface-python) — Face Recognition as a Service.

## Installation

```bash
pip install livexface
```

## Quick Start

```python
from livexface import LiveXFace

client = LiveXFace(
    api_key="lxf_live_xxxxxxxxxxxx",
    base_url="https://your-instance/api/v1",  # optional
)

# Register a face
face = client.faces.register(
    collection_id="collection-uuid",
    image=open("photo.jpg", "rb"),
    external_id="user_123",
    metadata={"name": "John Doe", "department": "Engineering"},
)
print("Registered face:", face.id)

# Identify (1:N search)
result = client.faces.identify(
    collection_id="collection-uuid",
    image=open("query.jpg", "rb"),
    top_k=3,
)
for match in result.matches:
    print(f"{match.external_id}: {match.confidence:.1%}")

# Verify (1:1 comparison)
verify = client.faces.verify(
    collection_id="collection-uuid",
    image=open("query.jpg", "rb"),
    face_id=face.id,
)
print(f"Match: {verify.match}, Confidence: {verify.confidence:.3f}, Threshold: {verify.threshold_used}")

# Liveness detection
liveness = client.faces.liveness(
    collection_id="collection-uuid",
    image=open("query.jpg", "rb"),
)
print(f"Live: {liveness.is_live}, Score: {liveness.liveness_score:.3f}")
```

## Active Liveness and Enrolment

A collection can require a liveness check before a face is enrolled. Run an
active check over 5 to 50 frames captured in order (the user blinks and turns
their head), then pass the token it returns when you register. The token is
single-use, valid for 5 minutes, and bound to the collection.

```python
frames = [open(f"frame_{i}.jpg", "rb") for i in range(10)]
check = client.faces.active_liveness("collection-uuid", frames)
print(f"Live: {check.is_live}, Blink: {check.blink.passed}, Head turn: {check.head_turn.passed}")

if check.liveness_token:
    face = client.faces.register(
        collection_id="collection-uuid",
        image=open("photo.jpg", "rb"),
        external_id="user_123",
        liveness_token=check.liveness_token,
    )
```

Batch items accept a `liveness_token` key too. Enrolment fails with
`LIVENESS_TOKEN_REQUIRED` (400) when the collection requires a token and none
was sent, `LIVENESS_TOKEN_INVALID` (422) when it is expired, used or for
another collection, and `LIVENESS_FACE_MISMATCH` (422) when the enrolled face
is not the one that passed the check.

## Collections

Collections are created and managed in the LiveXFace dashboard, not through
the API, so the client has no methods for them. Create one there and pass its
ID to the calls above.

## Batch Operations

```python
# Batch register (up to 20 faces)
batch = client.faces.batch_register("collection-uuid", [
    {"external_id": "user_1", "image": open("user1.jpg", "rb")},
    {"external_id": "user_2", "image": open("user2.jpg", "rb"), "metadata": {"role": "admin"}},
])
print(f"Succeeded: {batch.succeeded}, Failed: {batch.failed}")

# Batch delete
result = client.faces.batch_delete("collection-uuid", ["face-id-1", "face-id-2"])
```

## Error Handling

```python
from livexface import LiveXFaceApiError, LiveXFaceNetworkError

try:
    result = client.faces.identify(collection_id="col-id", image=image_bytes)
except LiveXFaceApiError as e:
    print(f"API error [{e.code}] {e.status_code}: {e}")
except LiveXFaceNetworkError as e:
    print(f"Network error: {e}")
```

## Image Input Types

The SDK accepts images as:
- `bytes` — raw image bytes
- `str` or `pathlib.Path` — file path
- File-like object — any object with a `.read()` method (e.g., `open("photo.jpg", "rb")`)

## Configuration

| Parameter  | Default                        | Description                      |
| ---------- | ------------------------------ | -------------------------------- |
| `api_key`  | **required**                   | Your API key (`lxf_live_xxx`)     |
| `base_url` | `http://localhost:8080/api/v1` | Base URL of the LiveXFace server |
| `timeout`  | `30`                           | Request timeout in seconds       |
