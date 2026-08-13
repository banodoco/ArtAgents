# Task T3.6 — Register and smoke the built-ins [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 3 of "Pluggable Timeline Renderers". T3.1-T3.5 created the Remotion
backend, FFmpeg backend, and FFmpeg finalizer modules + manifests. Your job:
finalize the registrations in `astrid/packs/rendering/pack.yaml`, prove
static discovery/registration of all three built-ins, run a REAL FFmpeg
render and a real Remotion smoke through the new backends, and verify
Remotion typecheck. This closes Batch 3.

## Change

1. Update `astrid/packs/rendering/pack.yaml`: `extensions.rendering` with
   `renderers: [backends/remotion/renderer.yaml, backends/ffmpeg/renderer.yaml]`
   and `finalizers: [finalizers/ffmpeg/finalizer.yaml]`. Ensure the
   manifests pass `validate_pack` and static inspection (no code import).
2. Add `tests/packs/rendering/test_builtin_registration.py`:
   - `validate_pack` on the rendering pack passes;
   - all three built-ins discoverable via the registry (qualified ids
     `rendering.remotion`, `rendering.ffmpeg`,
     `rendering.ffmpeg-finalizer`);
   - inspection is static (no backend code imported);
   - required binaries reported (node/npx for remotion, ffmpeg for the
     others) with explicit optional-dependency skip reasons.
3. Smoke tests:
   - a REAL FFmpeg render through the new backend produces a valid video
     (use a tiny generated timeline; ffmpeg IS available — assert it runs);
   - a Remotion render smoke if Remotion/node available (skip with a precise
     reason otherwise — Remotion typecheck below is the blocking gate);
   - assert cleanup (no leftover staging, no leaked server).
4. Remotion typecheck: `cd remotion && npm run typecheck` must PASS (blocking
   gate; do not skip).
5. Keep `pytest -q tests/packs/rendering tests/packs/test_audio_render.py`
   green.

## Acceptance

- `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` passes (same 2 pre-existing env failures only).
- `cd remotion && npm run typecheck` passes.
- Real FFmpeg render smoke passes.
- The three built-ins are statically registered and inspectable.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, the backend/finalizer modules (T3.1-T3.5 own
them), or Batch-1 frozen files. Preserve all existing work. Report: files
changed, test results, typecheck result, the smoke evidence.
