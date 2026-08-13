# Batch 6 oracle checkpoint

**Verdict:** PASS
**Commit:** fc0c3cee vs previous 8723ca05 (epic base b1c5f53c)
**Flash:** `.oracle/findings/oracle-b6-{docs,notes,gates,critique,diff}.txt`

```
PASS
- Docs `docs/reference/threejs-renderer.md` (196 lines): 11 text fields, rejection matrix, v1 exclusions, ANGLE + shared Remotion lock, engine/fragment/capture_host identity, hybrid + pinned ffmpeg-finalizer. Style matches `docs/reference/render-adapter.md`. T6.2: no README/STAGE/changelog/skill/CLI edits; only gate-driven allowlist + ruff baseline + hygiene.
- Checkpoint-3: `_effective_registry_state` + `_clip_end` removed (`git show fc0c3cee`); zero remaining refs. Checkpoint-5: mixed test asserts `backend_fragments["rendering.ffmpeg-finalizer"]` (`test_threejs_hybrid.py:814-821`) matching ffmpeg emitter; offline npm restore still in `finally`.
- BLE001: six sites narrowed to OSError/ValueError/TypeError/json/RendererException/RenderingRegistryError. Our two run.py files: ruff clean. Lost `RenderingRegistryError` on hybrid `support_resolver` (`run.py:540`) degrades missing-pack envelope unsupported→internal; both packs ship in checkout + wheel — not acceptance-failing.
- Ruff baseline 1458→1469 justified: count-only snapshot, +11 pre-existing (F401+6/I001+1/BLE001+4/F541+1/F402-1), not our files. Hygiene: `git rm --cached` `.codex/` `.vscode/` mp3 (added on main in b768588e); no history rewrite; merge will untrack them on main.
- Schema: `tests/test_schema_contract.py` + `astrid/core/` untouched by epic. Host ma```
PASS
- Docs `docs/reference/threejs-renderer.md` (196 lines) match shipped manifests: exact 11 text fields, rejection matrix, v1 exclusions, ANGLE + shared Remotion lock, `engine=threejs` / fragment `rendering.threejs` / `capture_host=remotion`, hybrid + pinned `rendering.ffmpeg-finalizer`. Style matches `docs/reference/render-adapter.md`. T6.2 clean (no README/STAGE/changelog/skill/CLI edits).
- `git show fc0c3cee`: `_effective_registry_state` + `_clip_end` gone, zero remaining refs. Mixed test asserts `backend_fragments["rendering.ffmpeg-finalizer"]` (`test_threejs_hybrid.py:814-821`) against the ffmpeg emitter; offline npm restore still in `finally`.
- BLE001: our two `run.py` files ruff-clean. Hybrid `support_resolver` (`planners/threejs_hybrid/run.py:540`) no longer remaps `RenderingRegistryError` → unsupported (now `internal` via `BaseException`); both packs ship in checkout + wheel — not acceptance-failing. Flash notes overstated a `_serialize_timeline` ImportError loss (schema import is module-level on remotion).
- Ruff baseline 1458→1469 justified: count-only snapshot; +11 pre-existing; our files 0 findings. Hygiene: `git rm --cached` `.codex/` `.vscode/` / mp3 (main `b768588e`); no history rewrite; merge will untrack them on main.
- Schema: epic does not touch `tests/test_schema_contract.py` or `astrid/core/`. Host `make ci` 10/10 failed/passed, identical on main. Flash bare pytest 16/4 ImportError on both checkouts (env) — not ours.
- Wheel manifest lists `backends/threejs/{__init__,renderer.yaml,run.py}` + `planners/threejs_hybrid/{__init__,planner.yaml,run.py}`. Host: Node 20.19.4 `npm ci` + typecheck + bundle; rendering 718 passed / 2 skipped / 1 pre-existing fixture.
- `git diff --name-only b1c5f53c..HEAD -- astrid/core/` empty. No second lock/Node project/`model.py`/tracked media.

Flash: `.oracle/findings/oracle-b6-{docs,notes,gates,critique,diff}.txt` (all PASS except notes BLE001, overridden above).
```

Epic is **COMPLETE**. Phase 6 (merge/commit/push/open) may proceed.
