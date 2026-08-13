# Task T5.5 — Replace the empty renderer parity gate [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 5 of "Pluggable Timeline Renderers". The current
`tests/packs/test_renderer_parity.py` is a placeholder/empty gate. Your job:
repository-owned semantic timeline/assets/theme fixtures, a rewritten parity
suite that actually renders through the REAL Remotion, FFmpeg, hybrid, and
raw fixture backends, reusing generated black/silence media and existing
goldens, with real FFmpeg and Remotion typecheck wired as blocking gates.

## Change

1. Populate repository-owned fixtures under `tests/fixtures/` (or a
   `tests/packs/parity_fixtures/` tree):
   - semantic timeline variants: media-only, effect clip, text card,
     audio-reactive colour, transition windows, empty timeline (must FAIL);
   - asset registries referencing generated black video + silence audio;
   - theme overrides matching the built-in default theme.
2. Generate tiny media (black `libx264` video, silent AAC audio) with ffmpeg
   at test setup; NEVER commit binary MP4s.
3. Rewrite `tests/packs/test_renderer_parity.py` (keep the `renderer_parity`
   marker) to cover the semantic parity matrix:
   - Remotion; FFmpeg; nominal-Remotion→FFmpeg auto-route; all-FFmpeg
     hybrid; mixed hybrid; raw renderer (deterministic fixture from Batch
     2); audio controls (rendered/passthrough/none); invalid artifacts
     rejected; failures clean up; standalone vs attached ownership;
     default (`hype.mp4`) and non-default output names.
   - The suite must FAIL on empty fixtures (no environment self-skip), run a
     real FFmpeg render (skip only when ffmpeg binary is absent), and
     treat Remotion typecheck as blocking when the remotion node_modules are
     installed (npm install is gitignored but present in this checkout).
4. Wire real FFmpeg + `cd remotion && npm run typecheck` into blocking CI
   lanes (`make check`, `make ci`, and the GitHub workflow if present).

## Acceptance

- `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py` passes.
- `pytest -q tests/packs/test_renderer_parity.py` (unmarked run) passes or
  skips only on missing ffmpeg.
- `pytest -q tests/packs` has no NEW failures outside the pre-existing
  model-trends env fixture.

Run ONLY those commands. Do NOT run the full suite, formatters, linters
beyond what is listed. Do NOT modify `service.py`, `provenance.py`, the
facade, the backends, `contracts.py`, or `schemas/`. Preserve all existing
work. Report: files changed, test results, the parity matrix coverage.
