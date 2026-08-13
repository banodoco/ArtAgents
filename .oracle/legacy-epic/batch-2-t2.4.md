# Task T2.4 — Invocation-scoped asset materialization [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 2 of "Pluggable Timeline Renderers". T2.1 (transport) and T2.3 (asset
cache) are done before you. The current render monolith
(`astrid/packs/rendering/executors/render/run.py`) has asset classification
(`_classify_assets`), a broad-root HTTP server (`_RangeHTTPRequestHandler`,
`_server_root_for`), and URL resolution. Your job: replace those with a
contained, invocation-scoped asset service. Exploration findings
(`.oracle/findings/07-serving-remotion-lifecycle.txt`) documented the current
risks: over-broad server root, TOCTOU port race, thread not joined, fixed
props/staging paths.

## Change

Add `astrid/core/rendering/assets.py`:

- `AssetMaterializer`:
  - classify each asset descriptor: local path, cached URL, or already-remote
    URL (reuse the cache primitives moved to `asset_cache.py` by T2.3);
  - materialize LOCAL copies into an invocation-scoped staging dir via
    hardlink-or-copy (fall back to copy when hardlink fails); remote/cached
    assets downloaded into the staging dir through the shared cache;
  - preserve already-remote URLs as-is (no download);
  - deterministic cleanup on success and failure (context manager or
    explicit `close()`).
- `InvocationAssetServer`:
  - serves ONLY the invocation staging dir from `127.0.0.1` on port `0`
    (bind-once via socket so no TOCTOU);
  - Range request support (single `bytes=` range → 206, invalid → 416);
  - CORS not needed (same-origin local) but must not be `*`;
  - always shuts down, closes, AND joins its thread (no leak);
  - produces per-asset `local_url` values for the render request.
- Replace in `astrid/packs/rendering/executors/render/run.py` (ONLY the
  asset-classification/serving parts — leave the render dispatch intact):
  `_classify_assets`, `_server_root_for`, `_pick_free_port`, and the inline
  handler, so renders use the new service with the same observable behavior
  for local files and URLs.
- Add `tests/core/rendering/test_assets.py`:
  - local path asset → staged copy + local_url serves correct bytes;
  - cached URL asset → staged + Range resume;
  - already-remote URL → preserved, no download;
  - cross-project/traversal paths rejected;
  - server binds to 127.0.0.1 on port 0 (assert port != 0, host is
    loopback);
  - Range: valid single range → 206 + Content-Range; invalid → 416;
  - server thread joined on close (no lingering threads);
  - cleanup removes staging dir on success AND failure;
  - concurrent renders get distinct staging dirs / URLs.

## Acceptance

- `pytest -q tests/core/rendering/test_assets.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.
- `pytest -q tests/test_url_pipeline_smoke.py tests/test_asset_cache.py` still
  passes (behavior preserved for existing paths).

Run ONLY those commands. Do NOT run the full suite, formatters, or linters.
Do NOT touch `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`
(T2.1), or `asset_cache.py` (T2.3) — reuse them. Preserve all existing work.
Report: files changed, test results, the serving design.
