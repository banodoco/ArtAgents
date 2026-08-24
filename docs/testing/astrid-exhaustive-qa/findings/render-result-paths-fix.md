# Render result paths and profile propagation — live proof

Date: 2026-08-23 (Europe/Berlin)

## Outcome

The project-scoped `rendering.render` path now formally exposes `profile` as a
declared JSON input, parses and validates it into the shared `RenderRequest`,
and forwards it through `RenderService` to backend support/render. The prior
timeline `output.resolution` hint rejection was removed: 640×360 is a valid
live render when the timeline canvas/profile requests 640×360. Explicit
profiles remain backend-validated.

Successful `InvocationResult.outputs.artifacts[*].path` values now point at
the durable managed SHA-256 media tree, never at `.staging`. Each artifact also
returns its media ID, content hash, current label, and the caller's
`requested_output_name`. The internal render sidecar rewrites both its
top-level and nested legacy provenance output locator to the same durable MP4
path before materialization.

## Live project-scoped verification

Disposable root: `/private/tmp/astrid-render-result-fix-MGKkqB`.

The public CLI created project `title-render`; the public SDK then invoked
`sdk.invoke("rendering.render", kind="executor", project="title-render", ...)`
with a project-owned timeline/assets pair and a complete `RenderProfile`.

### 640×360

- Requested name: `fifth.mp4`
- MP4 media ID: `01m0qskypbx44cttkv5mcp1x4d`
- MP4 SHA-256: `362298bc127938bc56ae20af8351a02d9882c9deb3ee3df478a29bfa88c725bc`
- Durable MP4: `/private/tmp/astrid-render-result-fix-MGKkqB/.astrid/media/sha256/36/22/362298bc127938bc56ae20af8351a02d9882c9deb3ee3df478a29bfa88c725bc`
- Provenance media ID: `01m0qt3dhp1nr2wgabsrcy6hen`
- Provenance SHA-256: `9943856bd3be20f20ab39b0bde5cb7f00b0a55a8238e424a95e331070c854dfe`
- Durable provenance: `/private/tmp/astrid-render-result-fix-MGKkqB/.astrid/media/sha256/99/43/9943856bd3be20f20ab39b0bde5cb7f00b0a55a8238e424a95e331070c854dfe`
- `ffprobe`: H.264, `640x360`, `30/1`, 1800 frames; AAC audio present.
- Invocation evidence label: `fifth.mp4`; provenance label: `fifth.mp4.provenance.json`.

### 1920×1080

- Requested name: `second1920.mp4`
- MP4 media ID: `01m0qsqvgrtrpyyh1q6yrjbpv6`
- MP4 SHA-256: `7044d6ae59e5c4147c8f47c6efc4d545b9f57ecb7416bf649453d1f5014ead65`
- Durable MP4: `/private/tmp/astrid-render-result-fix-MGKkqB/.astrid/media/sha256/70/44/7044d6ae59e5c4147c8f47c6efc4d545b9f57ecb7416bf649453d1f5014ead65`
- Provenance media ID: `01m0qt12mnvfmg4tx5efwk1n5j`
- Provenance SHA-256: `f60cd816e4c684f5555dc6a2e787d4b3eac4d69d44dd3aea2aa2287420562707`
- Durable provenance: `/private/tmp/astrid-render-result-fix-MGKkqB/.astrid/media/sha256/f6/0c/f60cd816e4c684f5555dc6a2e787d4b3eac4d69d44dd3aea2aa2287420562707`
- `ffprobe`: H.264, `1920x1080`, `30/1`, 1800 frames; AAC audio present.
- Invocation evidence label: `second1920.mp4`; provenance label: `second1920.mp4.provenance.json`.

Both managed provenance files have matching top-level and nested
`rendering.remotion` legacy output locators equal to the managed MP4 path, and
contain zero `.staging` references. The 640×360 reruns deduped to one MP4
media identity while preserving each requested current name (`first.mp4`,
`second.mp4`, `third.mp4`, `fourth.mp4`, `fifth.mp4`) in invocation evidence;
the sidecars remained separate because their provenance names/content differ.

## Narrow implementation guards

- `executor.yaml` declares `profile` and maps it to `--profile`.
- The executor parses JSON or Python-literal wire mappings and lets
  `RenderRequest` perform strict profile-shape validation.
- `RenderService.render` accepts the profile on its path-pair compatibility
  form and includes it in the frozen request.
- Project invocation evidence uses `managed_media_path(projects_root,
  digest)` for every materialized output.
- Internal provenance locator rewriting is additive and guarded by
  `ASTRID_INTERNAL_INVOCATION=1`; direct non-kernel renders retain their
  existing workspace provenance behavior.

## Verification

- Live project-scoped renders at both 640×360 and 1920×1080 completed with
  `ok: true`.
- `ffprobe` independently verified both managed MP4s.
- `media show` verified both managed locations, IDs, hashes, and current
  project ownership.
- `python3 -m compileall -q` passed for all changed runtime modules.
- Broad suites were intentionally not rerun; existing focused render tests
  include two unrelated pre-existing expectations that still assume the old
  CLI exception behavior and the old false 640×360 rejection.
