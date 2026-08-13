# Task T2.5 — Resolve profiles and validate artifacts [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 2 of "Pluggable Timeline Renderers". The frozen contracts
(`astrid/core/rendering/contracts.py`) define `RenderProfile` (dimensions,
rational FPS/time base, codecs, pixel format, audio rate/layout, duration
tolerance), `VideoArtifact`, `Attachment`, `AudioOwnership`. The finalizer
(Batch 3) and service (Batch 4) will consume these. Your job:
`resolve_render_profile` (canonical profile from the merged theme/timeline
canvas) and `validate_render_result` (strict artifact validation before
finalization).

## Change

1. `astrid/core/rendering/profile.py`:
   - `resolve_render_profile(timeline, assets, theme...)` — resolve the
     canonical profile from the merged theme/timeline canvas (width, height,
     rational FPS, time base, codecs, pixel format, audio rate/layout,
     duration tolerance). Read how the render monolith derives canvas today
     (run.py theme resolution + timeline model; see also
     `.oracle/findings/05-hybrid-planner-canvas.txt`) and how Remotion gets
     it (merged theme). The profile MUST match what Remotion renders.
   - Rational FPS as `(num, den)` — no float drift.
2. Extend `astrid/core/media.py` probing (add fields if missing): codec,
   pixel format, time base, audio codec/sample rate/channel layout, duration,
   FPS, dimensions. Keep existing callers working.
3. `astrid/core/rendering/artifacts.py`:
   - `validate_render_result(result, *, expected_profile, workspace_root)`:
     reject missing/empty output, escaped paths (traversal, absolute,
     symlink escape), hash mismatch (recompute sha256 vs declared),
     profile-incompatible outputs (wrong dimensions/FPS/codecs/audio),
     duration-invalid (outside tolerance), audio-ownership-invalid (declared
     `rendered` but no audio stream; declared `none` but has audio —
     use the strict probe), invalid attachment paths/kinds/hashes.
   - PRESERVE valid named attachments (they pass through untouched).
   - Return structured `RendererError`s (use the frozen error kinds) with
     recovery guidance.
4. Add `tests/core/rendering/test_profile.py` and
   `tests/core/rendering/test_artifacts.py` covering every rejection case
   above plus the happy path. Extend `tests/core/util/test_media.py` for the
   new probe fields (or add `tests/core/rendering/test_media_probe.py`).

## Acceptance

- `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py` passes (or your media test file).
- `pytest -q tests/core/rendering` has no NEW failures.
- Existing media.py consumers (`tests/core/util/test_media.py`, cut probe
  tests) still pass.

Run ONLY those commands. Do NOT run the full suite, formatters, or linters.
Do NOT touch `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py` (T2.4), or `asset_cache.py` (T2.3). Preserve all existing work.
Report: files changed, test results, the probe fields added.
