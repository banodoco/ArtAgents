# Task T6.3 — Implement `RenderContext` [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T6.2 (public SDK) runs first and defines `astrid/sdk/rendering.py`; add
`RenderContext` to that module (or a sibling) once it exists.

## Context

Batch 6 of "Pluggable Timeline Renderers". Your job: `RenderContext` — the
convenience facade a third-party renderer author gets so their `render.py`
can allocate paths, serve assets, run sanitized subprocesses, emit redacted
logs, check permissions, probe media, hash inputs, complete audio, carry
attachments, and clean up — while the docs make clear it is NOT an OS
sandbox.

## Change

1. `astrid/sdk/rendering.py::RenderContext` (or `astrid/sdk/context.py` if
   cleaner, re-exported from the SDK):
   - allocated output/workspace paths (validated workspace-relative);
   - asset descriptor path/URL access (resolve registry entries to
     absolute files or the invocation asset server URL);
   - permission checks (reject paths outside the workspace unless
     explicitly allowed);
   - sanitized subprocess runner (env scrubbing, bounded output capture,
     timeout, no shell when avoidable);
   - redacted logs/progress (scrub secrets/registry tokens);
   - interruption state (check a cooperative cancel flag; raise the frozen
     interrupted error kind);
   - probing (`ffprobe_metadata_strict` wrapper), hashing (`sha256_file`),
     audio completion (call the core `complete_audio` helper),
     attachments (named byte payloads validated by the frozen contract),
     and cleanup (context-manager `__enter__`/`__exit__` that removes
     temp artifacts, crash-safe).
   - Module + class docstrings MUST state: "RenderContext is not an OS
     sandbox; it enforces workspace conventions, not process isolation."
2. Reuse core primitives: `assets` materializer, `publication`,
   `transport` env helpers, `media` probe, `foundation.hash`, the frozen
   attachment/audio contracts. No new security boundary claims.
3. Add `tests/test_sdk_render_context.py`:
   - paths allocated inside workspace; outside rejected;
   - asset descriptor resolves to absolute file and to server URL;
   - subprocess env scrubbed; timeout enforced; no-shell default;
   - logs redact a secret token;
   - interruption flag raises the frozen error;
   - probe/hash/audio-completion/attachments round-trip;
   - `__exit__` cleans temp dirs even on exception (crash-safe).

## Acceptance

- `pytest -q tests/test_sdk_render_context.py` passes.
- `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py` still passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, or the facade. Preserve all existing
work. Report: files changed, test results, the RenderContext API.
