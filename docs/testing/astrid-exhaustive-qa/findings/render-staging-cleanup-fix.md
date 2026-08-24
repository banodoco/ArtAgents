# Render staging cleanup and duplicate pack-root fix

Date: 2026-08-23  
Mode: live end-user SDK/CLI proof first, followed by narrow regression coverage.

## Live reproduction before the fix

Using a fresh disposable projects root, a successful project-scoped
`sdk.invoke("rendering.render", kind="executor", ...)` reached terminal
success and returned durable managed-media artifact paths, but left its exact
kernel staging transaction under `.astrid/media/.staging`. A subsequent
`python3 -m astrid doctor --json` reported:

`1 orphaned staging director(ies) under .../.astrid/media/.staging`

The failed render path already cleaned synchronously, but this was verified
again with an unresolved animation request. The defect was therefore the
successful completion path: materialization had finished, but the execution
quarantine was never removed.

## Changes

- `astrid/sdk/invocation.py`
  - After a completed kernel task has materialized every output, removes only
    that invocation's generated staging transaction.
  - Leaves staging untouched for a stale/non-completed completion so an active
    or competing worker's workspace cannot be removed; startup GC remains the
    crash-recovery path.
  - Keeps returned output locators on durable managed SHA paths. If an
    executor's primary output is `manifest.json`, `InvocationResult.manifest_path`
    now also points at its durable managed locator instead of a deleted staging
    path.
- `astrid/core/task_executor/service.py`
  - Promoted the exact-path, symlink-safe best-effort removal primitive to
    `ExecutionService.cleanup_staging`; the existing private failure helper is
    retained as a compatibility alias.
- `astrid/core/pack/discovery.py`
  - Canonical external roots are scanned once. If the same root is supplied by
    SDK `extra_pack_roots` and `ASTRID_PACKS_PATH`, explicit `extra` provenance
    wins and the duplicate `env` entry is suppressed.
- `tests/packs/test_pack_discovery_metadata.py`
  - Added one narrow regression check for duplicate canonical external roots.

## Fresh live proof after the fix

Disposable root: `/tmp/astrid-staging-proof-qBYbYz`.

- Successful empty-timeline managed render: run
  `613b83565d61e6ce22694b6c7f`, `ok=true`.
  - Primary durable artifact:
    `/tmp/astrid-staging-proof-qBYbYz/.astrid/media/sha256/c0/96/c096f16bc6a571ba980a9613fef5e667ebbac5cec8035ec67f6da693a54d68e5`
  - Provenance durable artifact:
    `/tmp/astrid-staging-proof-qBYbYz/.astrid/media/sha256/88/17/8817ca4d58da727ce5a356a2d9d7cb4a8e404b9ffc70dada7bf8398b0ee7fe88`
  - Both paths existed after invocation returned; no staging directories
    remained.
- Failed unresolved-element render: run `93c308522a0995730ee5822698`,
  `ok=false`, typed `CapabilityRuntimeError` with the actionable message
  `timeline uses unregistered animation 'missing-external-animation'`.
  It returned no outputs and left no staging directory.
- `doctor --json` after both journeys returned `ok: true`; `media_paths` was
  required/`ok` with managed locators resolving and no orphan warning.
- Duplicate-root discovery set both `ASTRID_PACKS_PATH` and
  `extra_pack_roots` to the exact same canonical fixture root. Three external
  packs were reported with `source_kind: "extra"` and zero with
  `source_kind: "env"`, proving one discovery/provenance entry per pack.

## Narrow automated check

`pytest -q tests/packs/test_pack_discovery_metadata.py -k 'same_canonical_external_root or env_layer'`

Result: **3 passed**, 12 deselected.

