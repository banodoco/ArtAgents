# Task T6.4 — Shared raw/SDK conformance fixtures

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.
T6.2 (public SDK) may be running in parallel; if `astrid/sdk/rendering.py`
does not exist yet, build the raw side first and add the SDK side after.

## Context

Batch 6 of "Pluggable Timeline Renderers". Your job: shared conformance
fixtures under `tests/fixtures/renderer_packs/sdk/` that prove a raw-command
backend and an SDK backend produce SEMANTICALLY IDENTICAL wire fields for
the same request, using ONE conformance harness.

## Change

1. `tests/fixtures/renderer_packs/sdk/` — a pack with:
   - `pack.yaml`, `renderer.yaml` (id `sdk.renderer`, commands invoking a
     shared runner),
   - `render.py` (raw-command implementation) AND an `sdk_render.py`
     (SDK implementation via `astrid.sdk.rendering.renderer_main`), both
     thin wrappers over the SAME logic so the comparison is meaningful.
2. Cases (each a fixture request):
   - minimal render (media-only timeline);
   - request-sensitive support (supported only for a specific window/audio
     combination);
   - passthrough audio;
   - no-audio (visual-only);
   - attachment (named byte payload);
   - intentional failure (invalid output → structured error).
3. `tests/core/rendering/test_conformance.py` — ONE harness that runs each
   case through BOTH the raw and the SDK backend and asserts the emitted
   result/support JSON fields are semantically identical (same keys, same
   normalized values; paths may differ by workspace but hashes/profile
   values must match).
4. The harness uses `CommandTransport` for both, exactly like production.

## Acceptance

- `pytest -q tests/core/rendering/test_conformance.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.
- Wire parity for all six cases.

Run ONLY those commands. Do NOT modify `service.py`, `provenance.py`, the
backends, `contracts.py`, schemas, the facade, or `astrid/sdk/rendering.py`
(that's T6.2's file — coordinate via the shared contract below). Preserve
all existing work. Report: files changed, test results, the parity matrix.

## Contract (shared)

`astrid/sdk/rendering.py` exports `renderer_main(argv=None) -> int` reading
`--request <path> --result <path>` (same as raw backends) and writing the
same `RenderResult`/`SupportReport` JSON. The SDK `render.py` calls it.
