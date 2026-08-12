# Task T3.3 — Extract the FFmpeg backend and pure builders [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 3 of "Pluggable Timeline Renderers". T3.1/T3.2 (before you) extracted
the Remotion backend. The render monolith
(`astrid/packs/rendering/executors/render/run.py`) still contains the FFmpeg
media rendering (`_render_ffmpeg_media`, `_validate_ffmpeg_media_timeline`)
and the audio-reactive specialization (`audio_reactive_colour.py`). Your
job: extract the FFmpeg backend into
`astrid/packs/rendering/backends/ffmpeg/` with pure, unit-testable command
builders, a `renderer.yaml` manifest registered as `rendering.ffmpeg`, and a
raw-command adapter. Behavior-preserving extraction — do NOT change routing
semantics yet (T3.4 makes support strict).

## Change

1. Create `astrid/packs/rendering/backends/ffmpeg/`:
   - `__init__.py`, `run.py` (raw-command adapter: reads `--request`, writes
     `--result` RenderResult JSON), `renderer.yaml` (id `rendering.ffmpeg`,
     protocol_version 1, command `[python3, run.py]`, operations
     `[render, support]`, capabilities, required_permissions), and
     `command.py` (PURE builders: `build_render_command(request, workspace)`
     returning argv; mirror the `audio_reactive_colour.build_*` pattern).
   - Move `_render_ffmpeg_media` logic and `audio_reactive_colour.py` here
     (keep `audio_reactive_colour` as a module within the backend; the old
     file becomes a thin re-export if anything imports it).
   - The `support` verb mirrors the current acceptance behavior (T3.4 makes
     it strict — for now reproduce current `_can_render_with_ffmpeg_media`
     semantics).
   - Audio ownership: return explicit `rendered|passthrough|none` in the
     result (the media path renders audio; visual-only semantics come in
     T3.4).
2. Register `rendering.ffmpeg` in `astrid/packs/rendering/pack.yaml`.
3. Keep the facade (`run.py`) working for `engine=ffmpeg` (direct module
   call or CommandTransport — pick behavior-preserving path).
4. Relocate FFmpeg tests to `tests/packs/rendering/test_ffmpeg_backend.py`;
   keep `test_audio_reactive_colour.py` passing (re-export as needed).

## Acceptance

- `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py` passes.
- `pytest -q tests/packs/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, `backends/remotion/` (T3.1/T3.2 own it), or
Batch-1 frozen files. Preserve all existing work. Report: files created,
test results, the pure-builder API.
