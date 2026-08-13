# Task T3.1 — Extract `rendering.remotion` backend [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 3 of "Pluggable Timeline Renderers". Batches 1-2 froze the contracts
(`astrid/core/rendering/contracts.py`), transport (`transport.py`), assets
(`assets.py`), profiles/artifacts (`profile.py`, `artifacts.py`), and
publication (`publication.py`). The current render monolith
(`astrid/packs/rendering/executors/render/run.py`) contains ALL Remotion
logic: theme resolution, timeline serialization, element-registry
generation, effect asset staging, props creation, subprocess invocation, and
backend provenance. Your job: extract the Remotion backend into
`astrid/packs/rendering/backends/remotion/` with a `renderer.yaml` manifest
and a raw-command adapter, registered as `rendering.remotion`. Behavior must
be IDENTICAL — this is extraction, not redesign.

## Change

1. Create `astrid/packs/rendering/backends/remotion/`:
   - `__init__.py`, `run.py` (the raw-command adapter implementing the frozen
     protocol: reads `--request`, writes `--result`; the result is a
     `RenderResult`-shaped JSON with the video artifact, profile, sha256,
     audio ownership, backend fragments), and `renderer.yaml` (id
     `rendering.remotion`, protocol_version 1, command `[python3, run.py]`,
     operations `[render, support]`, capabilities, required_permissions).
   - Move the Remotion helpers from run.py here (theme resolution, timeline
     serialization, element-registry generation, effect asset staging, props
     creation, subprocess invocation, cleanup, Remotion provenance
     fragments). Reuse `astrid/core/rendering/assets.py` for asset serving
     (InvocationAssetServer) instead of the old broad-root server.
   - The `support` verb answers request-sensitive support (what the current
     code allows Remotion to render).
2. Register in `astrid/packs/rendering/pack.yaml`:
   `extensions.rendering.renderers: [backends/remotion/renderer.yaml]`.
3. Keep `astrid/packs/rendering/executors/render/run.py` a thin facade that
   still works for `engine=remotion` (Batch 4 switches to the generic
   RenderService; for NOW the facade may call the backend module directly or
   through `CommandTransport` — pick the path that preserves current
   behavior and tests).
4. Relocate private-helper tests: move Remotion-specific tests from
   `test_render_remotion_registry.py`, `test_url_pipeline_smoke.py`, and
   Hype render tests beside the extracted module
   (`tests/packs/rendering/test_remotion_backend.py`,
   `test_remotion_render_contract.py`), keeping a thin facade contract suite.
5. Preserve: `TimelineComposition` usage, merged themes, props,
   registry state/hashes, source-pack and effect lineage, effect staging,
   sanitized environment, cleanup, output validation, and the exact
   provenance fields (v1 + the audio-reactive specialization additions).

## Acceptance

- `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py` passes.
- `pytest -q tests/packs/rendering/test_render_remotion_registry.py` (relocated cases) passes or documents the SAME 2 pre-existing env-dependent failures.
- `pytest -q tests/packs/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, or `test_contracts.py`. Preserve all existing
work. Report: files created/moved, test results, how the facade now invokes
Remotion.
