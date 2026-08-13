# Task T2.3 — Extract the reusable asset cache (DeepSeek Flash)

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. You
MAY edit files (file, web, terminal toolsets). Python:
`PYENV_VERSION=3.11.11`.

## Context

Batch 2 of "Pluggable Timeline Renderers". The reusable asset-cache
primitives currently live in
`astrid/packs/training/executors/asset_cache/run.py`. The render path also
depends on them. Your job: move the reusable cache logic into
`astrid/core/rendering/asset_cache.py` and keep the training executor as a
compatible CLI wrapper. This is extraction ONLY — no behavior change, no
reformatting of unrelated code.

## Change

1. Read `astrid/packs/training/executors/asset_cache/run.py` fully and
   `astrid/packs/rendering/executors/render/run.py` (the parts that use the
   cache, e.g. `_classify_assets`/URL caching) plus
   `tests/test_asset_cache.py` and `tests/test_url_pipeline_smoke.py` (the
   tests that must keep passing).
2. Create `astrid/core/rendering/asset_cache.py` with the REUSABLE
   primitives (cache dir layout, URL/hash keys, download/resume/drift
   metadata, file locking — mirror the `_lock_for`/filelock pattern currently
   in the training executor; `EphemeralSession` cleanup semantics if
   applicable). Keep the same behavior and the same public helper names where
   tests depend on them.
3. Rewrite `astrid/packs/training/executors/asset_cache/run.py` as a thin
   CLI wrapper that imports and calls the core module (compatible
   command-line interface, same outputs). Update its imports.
4. Update the render path (`astrid/packs/rendering/executors/render/run.py`)
   ONLY to import the cache helpers from the new core location if it currently
   imports them from the training pack — do NOT refactor the render monolith
   otherwise (Batch 3+ extracts backends).
5. `tests/test_asset_cache.py` and `tests/test_url_pipeline_smoke.py` must
   pass unchanged (or with only import-path updates if they import from the
   training executor directly — prefer keeping them green by re-exporting
   from the wrapper if that's the compatible path).

## Acceptance

- `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py` passes.
- `pytest -q tests/packs/training` (asset_cache tests) passes.
- The training executor CLI still works: `python -m
  astrid.packs.training.executors.asset_cache.run --help` exits 0.

Run ONLY those commands. Do NOT run the full suite, formatters, or linters.
Do NOT touch `astrid/core/rendering/contracts.py`, `schemas/`,
`docs/contracts/`, or `tests/core/rendering/` (other agents own those). Do
NOT refactor the render monolith beyond import updates. Preserve all existing
work. Report: files changed, test results, the exact API you moved.
