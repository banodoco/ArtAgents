# Render project/profile fix — live proof

Date: 2026-08-23 (Europe/Berlin)

## Outcome

The project-scoped `sdk.invoke("rendering.render", project=...)` path now
works for a supported Remotion profile and records the rendered MP4 and
provenance sidecar as kernel task outputs. A timeline that declares
`output.resolution: "640x360"` is rejected during renderer support, before
artifact creation, because the current Remotion compositor produces its
theme canvas (1920x1080 by default). The error names the supported canvas
configuration instead of silently publishing a 1920x1080 file.

## Changes

- Imported and called the sanctioned
  `astrid.core.project.ownership.require_project_owned_artifact` boundary in
  executor dispatch, passing the bound projects root. Project-owned timeline
  and asset inputs no longer fail with an internal `NameError`.
- Added Remotion support-time checks for legacy timeline `output.resolution`
  and `output.fps` hints that do not match the actual compositor canvas/profile.
  The request is rejected before `npx remotion render` and before publication.
- Preserved kernel handler failures in `InvocationResult.error` with
  `CapabilityRuntimeError` / `runtime` typing. Internal render invocations
  retain structured support reasons, including the requested and supported
  profile.
- Returned ordered kernel media IDs and staged artifact labels/paths on a
  successful invocation. Only a real `manifest.json` is exposed as
  `manifest_path`; MP4 output is no longer parsed as JSON.
- Excluded transient publication `.lock` files from the universal output
  collection, so the kernel stores the MP4 and provenance sidecar only.

## Live verification

Disposable root: `/tmp/astrid-render-fix-hTqj9r` (created solely for this
probe; it is not a repository artifact).

The same two-second `HELLO ASTRID` text timeline was invoked through the
project-scoped SDK path.

### Unsupported declared profile

With `output.resolution: "640x360"`, invocation run
`1147156aabbabdafec17036eac` failed before artifact creation. The primary
`InvocationResult.error` was:

```text
rendering.remotion does not support this render request: timeline requests output resolution '640x360', but Remotion produces 1920x1080; set theme_overrides.visual.canvas.width/height to that supported canvas or remove the output resolution hint
```

The run was terminal `failed`; no MP4 or provenance sidecar was present in
the project or media staging tree.

### Supported project render

With the declaration changed to `1920x1080`, run
`9dbfd2e11d0aea2db6a580a155` completed successfully. Its kernel task was
`d325895da5390df9643ed716ef`; the returned ordered outputs were:

- `title-render-1920d.mp4`, role `result`, media ID
  `01m0qr9x4bbkc4p0ss0tv59srj`;
- `title-render-1920d.mp4.provenance.json`, role `output`, media ID
  `01m0qrecr86x5w8b04w021vh6b`.

The task completion event and `media show --project title-render` both expose
the managed media locations. The MP4 content hash is
`26a29ee6d2da50402a3a00e0642ea82b24d9fe5ac8ca86133431620ebb019f3f`; the
provenance sidecar is stored as JSON media with its own content hash.

`ffprobe` on the managed MP4 reported H.264, 1920x1080, 30/1 fps, 60 frames,
AAC audio, 2.048 seconds, and 97,477 bytes. A frame extracted at one second
visually showed centered white `HELLO ASTRID` on a dark background.

## Regression checks

- `pytest -q tests/packs/rendering/test_remotion_backend.py tests/v10/test_task_executor.py`
  — 53 passed.
- `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_service.py tests/core/test_project_ownership.py tests/test_sdk_public_surface.py`
  — passed.
- Python compilation of all changed runtime modules — passed.

