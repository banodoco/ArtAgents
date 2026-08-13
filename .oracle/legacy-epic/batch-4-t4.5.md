# Task T4.5 — Lock the routing and hybrid matrix

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". T4.1 (service), T4.3
(provenance), T4.4 (hybrid planner) are done before you. Your job: the
comprehensive routing/hybrid matrix that locks the whole batch.

## Change

Add the matrix cases to the EXISTING test files (extend
`tests/core/rendering/test_service.py`, `test_legacy_hybrid.py`,
`test_provenance.py` — do not create parallel suites):

1. Selectors: strict qualified `rendering.remotion`, `rendering.ffmpeg`;
   legacy `remotion` (auto-route media-only with warning), legacy `ffmpeg`
   (strict), `hybrid` (planner).
2. Alias/override: an alias and an override both affect the resolved winner;
   a trust-denied candidate never wins.
3. Unsupported backend → structured error with alternatives.
4. Output-name: separator/traversal/non-mp4 rejection; default hype.mp4
   preserved.
5. Every built-in path (remotion, ffmpeg, optimized ffmpeg, audio-reactive,
   hybrid, single-segment) → exactly one video + one committed sidecar with
   valid provenance.
6. Raw mixed-plan: the deterministic raw fixture (Batch 2) renders one
   window, a built-in renders another, the finalizer concatenates; segment
   provenance aligned.
7. Audio control: rendered/passthrough/none across backends.
8. Failure cleanup: no temp leftovers; sidecar never committed on failure.
9. Attachments preserved through validation/finalization/provenance.
10. Crash recovery: incomplete pair never treated as committed.

## Acceptance

- `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `service.py`,
`provenance.py`, the planners/backends/finalizer, or Batch-1 frozen files
(tests only). Preserve all existing work. Report: files changed, test
results, the matrix coverage.
