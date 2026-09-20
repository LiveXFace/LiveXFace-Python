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
    threshold=0.45,
)
for match in result.matches:
    print(f"{match.face.external_id}: {match.similarity:.1%}")

# Verify (1:1 comparison)
verify = client.faces.verify(
    collection_id="collection-uuid",
    image=open("query.jpg", "rb"),
    face_id=face.id,
)
print(f"Match: {verify.match}, Confidence: {verify.confidence:.3f}")

# Liveness detection
liveness = client.faces.liveness(
    collection_id="collection-uuid",
    image=open("query.jpg", "rb"),
)
print(f"Live: {liveness.is_live}, Spoof score: {liveness.spoof_score:.3f}")
```

## Collections

```python
# List collections
collections = client.collections.list()

# Create a collection
collection = client.collections.create(
    name="employees",
    description="Employee face database",
)

# Delete a collection
client.collections.delete(collection.id)
```

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
