# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0]

Validated against API contract 2.0.0.

### BREAKING

- `faces.active_liveness` no longer returns a liveness token: the API's
  stateless check stopped issuing them. `ActiveLivenessResult.liveness_token`
  and `ActiveLivenessResult.liveness_token_expires_at` are removed.

  Migration: create a session, show its challenges, complete it with the frames,
  then enrol with the token it returns.

  ```python
  session = client.faces.create_liveness_session(collection_id)
  # show session.challenges in order, capture frames while they are performed
  result = client.faces.complete_liveness_session(collection_id, session.session_id, frames, mirrored=True)
  if result.liveness_token:
      client.faces.register(collection_id, image, external_id, liveness_token=result.liveness_token)
  ```

### Added

- `faces.create_liveness_session(collection_id)` returns a `LivenessSession`
  (`session_id`, `challenges`: `blink` / `turn_left` / `turn_right` in order,
  `expires_at`).
- `faces.complete_liveness_session(collection_id, session_id, frames, mirrored=False)`
  returns a `LivenessSessionResult`: the active-liveness fields, `steps`
  (`LivenessStep`: `type`, `passed`) and, when it passed, `liveness_token` and
  `liveness_token_expires_at`. It is retried on a 429 only, never on a network
  error or a 5xx, because a session is judged once.
- Error code `LIVENESS_SESSION_INVALID` (422), raised as `LiveXFaceApiError`,
  when a session is unknown, expired, already submitted or bound to another
  collection.

### Changed

- Pinned API contract 2.0.0 (`contract/openapi-2.0.0.json`,
  `livexface.CONTRACT_VERSION`).
