# Task T2.2 — Add the raw protocol fixture pack (DeepSeek Flash)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. You
MAY edit files (file, web, terminal toolsets). Python:
`PYENV_VERSION=3.11.11`.

## Context

Batch 2 of "Pluggable Timeline Renderers". T2.1 (an agent in parallel or just
finished) added `astrid/core/rendering/transport.py::CommandTransport` and
`tests/core/rendering/test_transport.py`. The frozen wire protocol (from
`docs/contracts/render-backend-v1.md` and the T2.1 brief):

```text
<command> render|support|plan|finalize --request <abs.json> --result <abs.json>
```

Your job: a committed RAW-COMMAND fixture renderer that implements this
protocol WITHOUT importing Astrid's SDK — a plain Python script reading JSON
from `--request` and writing JSON to `--result`. It must produce a
deterministic ~2-second video from GENERATED media (no committed MP4s, no SDK
imports).

## Change

1. Create `tests/fixtures/renderer_packs/raw_command/`:
   - `pack.yaml` — a valid trusted source pack (`id: raw_command`,
     permissions `subprocess` + `project_files` with reasons, an
     `extensions.rendering.renderers` entry pointing at `renderer.yaml`,
     alias `raw_command.legacy → raw_command.renderer` if useful).
   - `renderer.yaml` — manifest: `id: raw_command.renderer`,
     `protocol_version: 1`, `command: [python3, backend.py]`,
     `operations: [render, support]`, `capabilities` (clip_types, track_types,
     features incl `media`, full-timeline support), `required_permissions:
     [subprocess, project_files]`.
   - `backend.py` — the raw implementation: parse argv (`render` or
     `support`), read `--request` JSON, and:
     - `support`: write a `SupportReport`-shaped result (`{schema_version: 1,
       supported: true, reasons: [], features: {media: true, audio_mode:
       rendered}, alternatives: [], backend: "raw_command.renderer",
       backend_version: "1.0.0"}`).
     - `render`: generate a deterministic video WITHOUT ffmpeg if possible
       (write a tiny valid MP4 or use a pure-Python container; simplest:
       generate a solid-color frame sequence via a minimal MP4 writer, or
       shell out to ffmpeg ONLY if available and fall back gracefully). The
       result must be a `RenderResult`-shaped JSON
       (`{schema_version: 1, video: {path, profile, sha256, duration_frames,
       audio, attachments}, audio_ownership, backend_fragments: {...}}`)
       with the actual sha256 of the produced file. Duration ~2 seconds at
       the request's profile FPS (e.g. 48 frames @ 24fps). Keep output
       CONTAINED in the request's workspace (use the request's `output_name`
       or a path under the current dir).
     - The script must NOT import `astrid` — pure stdlib + optional ffmpeg.
   - `tests/fixtures/renderer_packs/raw_command/requests/` — versioned
     request JSONs: `render.json` (minimal timeline, profile 1920x1080
     @24fps, audio rendered), `support.json`.
2. Add `tests/core/rendering/test_raw_command_fixture.py`:
   - assert discovery/static inspection of the fixture pack (no code import);
   - run the `render` verb through `CommandTransport` with a temp workspace
     and assert: exit success, result parses as `RenderResult`, video file
     exists with matching sha256, duration frames match the request;
   - run `support` and assert the `SupportReport` shape;
   - assert NO `run.json` is created anywhere (the fixture must not touch
     Astrid's ledger);
   - assert the fixture works from an explicit extra pack root and (if
     feasible without network) a trusted install (mirror the discovery
     fixture patterns from `tests/core/rendering/test_registry_matrix.py`).
3. If `tests/packs/test_git_pack_install.py` exists and is cheap, ensure your
   fixture doesn't break it; otherwise skip it (it needs network).

## Acceptance

- `pytest -q tests/core/rendering/test_raw_command_fixture.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT touch `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py` (T2.1
owns it — if you find a transport defect, note it in your report), or
`tests/core/rendering/test_contracts.py`. Do NOT commit binary MP4 files.
Preserve all existing work. Report: files created, test results, how you
generated the video.
