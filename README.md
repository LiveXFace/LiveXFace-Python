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

Validated against API contract 2.0.0 (`/openapi.json` `info.version`). The test suite calls every client method against the contract committed in `contract/` and fails if a method, path or required field is not in it; to move to a new contract, copy the release asset `openapi-<version>.json` into `contract/`, then update `CONTRACT_VERSION` and `livexface.CONTRACT_VERSION`.

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

## Liveness Sessions and Enrolment

A collection can require a liveness check before a face is enrolled. The
token for that comes from a liveness session: the server picks the steps the
person must perform, in order, and the frames must show them.

1. Create a session. `challenges` lists the steps: `blink`, `turn_left` or
   `turn_right` (the person's own left and right). Submit before `expires_at`
   (60 seconds by default).
2. Show each prompt and capture 5 to 50 frames, in order, while the person
   performs them.
3. Complete the session with the frames. Pass `mirrored=True` when they are
   horizontally mirrored, as a selfie preview is.
4. If it passed, register with its `liveness_token`: single-use, valid for 5
   minutes, and bound to the collection.

```python
session = client.faces.create_liveness_session("collection-uuid")
prompts = {"blink": "Blink", "turn_left": "Turn your head to your left", "turn_right": "Turn your head to your right"}
for step in session.challenges:
    print(prompts[step])  # show the prompt, keep capturing frames

frames = [open(f"frame_{i}.jpg", "rb") for i in range(25)]
result = client.faces.complete_liveness_session("collection-uuid", session.session_id, frames, mirrored=True)
print(f"Live: {result.is_live}, Steps: {[(s.type, s.passed) for s in result.steps]}")

if result.liveness_token:
    face = client.faces.register(
        collection_id="collection-uuid",
        image=open("photo.jpg", "rb"),
        external_id="user_123",
        liveness_token=result.liveness_token,
    )
```

A session is judged once. Any submission except one with fewer than 5 frames
(400 `IMAGE_REQUIRED`, the session is kept) uses it up, so
`complete_liveness_session` is never retried on a network error or a 5xx;
create a new session instead. Completing fails with `LIVENESS_SESSION_INVALID`
(422) when the session is unknown, expired, already submitted or bound to
another collection, and with `SERVICE_BUSY` (503) when the engine is
saturated; create a new session for either.

`active_liveness(collection_id, frames)` still checks frames for a blink, a
head turn and passive anti-spoofing, but it returns a verdict only and no
token.

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

`LiveXFaceApiError` carries `status_code`, `code`, the message (`str(e)`),
`request_id`, `details` (a dict, or `None`) and `retry_after`: the seconds from
the response's `Retry-After` header on a 429 or 503, or `None` when it had none.

## Idempotent Requests

`register`, `batch_register` and `batch_register_async` accept an
`idempotency_key`, sent as the `Idempotency-Key` header. The API remembers the
answer to a keyed request for 24 hours: sending the same request with the same
key again returns that stored answer, with the header `Idempotent-Replayed: true`,
instead of enrolling the faces a second time. So a call that timed out or lost
its connection can be repeated without creating duplicates.

- The same key with a different request is answered 422 `IDEMPOTENCY_KEY_MISMATCH`.
- The same key while the first request is still running is answered 409 `IDEMPOTENCY_KEY_IN_USE`.
- 429 and 5xx answers are not remembered, so a retry with the same key runs the request again.
- Other 4xx answers are remembered: after fixing the request, send it with a new key.

`new_idempotency_key()` returns a random key (a UUID v4).

## Production Retries

Retries are off by default. `max_retries` turns them on (the number of attempts
after the first): a 429 or 503 is retried after its `Retry-After`, capped at
`max_retry_delay`, or after an exponential backoff with jitter when it gives
none. A network error or another 5xx is retried only for reads, deletions and
calls that carry an idempotency key; other 4xx are never retried. Enrolment and
batch calls send one key on every attempt, generating it when you give none.
`complete_liveness_session` is retried on a 429 only, since a session is
judged once.

```python
from livexface import LiveXFace, LiveXFaceApiError, new_idempotency_key

client = LiveXFace(api_key="lxf_live_xxxx", max_retries=3)

key = new_idempotency_key()  # store it with your record to retry safely later
try:
    face = client.faces.register("collection-uuid", open("alice.jpg", "rb"), "user_123", idempotency_key=key)
except LiveXFaceApiError as e:
    print(f"[{e.code}] {e.status_code}: {e} (request {e.request_id}, retry after {e.retry_after}s)")
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
| `max_retries` | `0`                         | Retries after the first attempt; 0 turns retries off |
| `max_retry_delay` | `60`                    | Longest wait between attempts, in seconds |
