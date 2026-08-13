# Task T4.1 — Generic RenderService [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". Batches 1-3 froze the contracts,
transport, asset materialization, profile/artifact validation, publication,
and the Remotion/FFmpeg backends + FFmpeg finalizer. Your job: the generic
`RenderService` that ties them together with the frozen selection order.

## Change

Add `astrid/core/rendering/service.py::RenderService`:

1. Selection order (FROZEN): legacy translation → alias → override → winner →
   eligibility → support → invoke/validate → audio/finalize → publish.
2. Use the registries from Batch 1 (`RendererRegistry`, `PlannerRegistry`,
   `FinalizerRegistry`, `load_default_registries`) for resolution.
3. Legacy translation (the ONLY place that knows short names):
   - `ffmpeg` → strict `rendering.ffmpeg`;
   - `remotion` → characterized legacy policy (FFmpeg for eligible
     media/audio-specialized timelines via the Remotion backend's support,
     else `rendering.remotion`) with an auto-routing warning;
   - `hybrid` → `rendering.legacy_hybrid` planner (NEVER a renderer id);
   - qualified ids are strict.
4. Invoke the selected backend through `CommandTransport` (or in-process
   adapter — pick behavior-preserving), validate the artifact with
   `validate_render_result`, apply host audio completion (render
   passthrough/none handling), run the finalizer when the plan has multiple
   segments, publish via `publish_render_result`, and emit ONE provenance
   sidecar per success.
5. Every successful path → exactly one video + one committed sidecar.
6. Failures → structured `RendererError`s with recovery guidance; cleanup
   temporary artifacts.
7. Add `tests/core/rendering/test_service.py`:
   - full render through `rendering.remotion` (mock the backend, assert the
     service order via spies);
   - strict `rendering.ffmpeg`;
   - legacy `remotion` auto-route (media-only → ffmpeg) with warning;
   - legacy `ffmpeg` strict;
   - `hybrid` selects the planner;
   - unsupported backend → structured error with alternatives;
   - alias/override resolution affecting the winner;
   - eligibility denial;
   - audio completion (passthrough/none);
   - finalizer path (multi-segment);
   - failure cleanup (no temp leftovers);
   - exactly one sidecar per success.

## Acceptance

- `pytest -q tests/core/rendering/test_service.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, `provenance.py` (T4.3 owns it), the backend
modules, or Batch-1 frozen files. Preserve all existing work. Report: files
changed, test results, the selection-order implementation.
