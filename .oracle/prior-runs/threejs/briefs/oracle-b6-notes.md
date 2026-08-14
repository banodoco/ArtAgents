# Oracle Batch 6 — dead-code + finalizer assertion + BLE001 (research)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: fc0c3cee vs previous 8723ca05. Do not edit any files.

Inspect the production + test code changes that fold in checkpoint-3/5 notes and the ruff BLE001 narrowing.

## Commands to run

```bash
git show fc0c3cee -- astrid/packs/rendering/backends/threejs/run.py \
  astrid/packs/rendering/planners/threejs_hybrid/run.py \
  tests/core/rendering/test_threejs_hybrid.py \
  tests/packs/rendering/test_threejs_backend.py \
  tests/core/rendering/test_production_callers.py
```

Then grep:

```bash
rg -n "_effective_registry_state|_clip_end" astrid/packs/rendering tests
rg -n "except Exception|except:" astrid/packs/rendering/backends/threejs/run.py \
  astrid/packs/rendering/planners/threejs_hybrid/run.py
rg -n "ffmpeg-finalizer|backend_fragments" tests/core/rendering/test_threejs_hybrid.py
```

Read the current except sites and the new assertion in context.

## Check 1 — dead-code removal (checkpoint 3)

- `_effective_registry_state` binding and `_clip_end` must be gone.
- Confirm nothing still calls them (including tests).
- Confirm remaining registry/theme/timing helpers still work the same (no behavior change: only unused bindings removed).
- If a still-used helper was deleted, FAIL.

## Check 2 — finalizer fragment assertion (checkpoint 5)

- `test_threejs_hybrid_mixed_real_render` must assert the actual sidecar shape for the pinned finalizer.
- Confirm it asserts what the service emits (`payload["backend_fragments"]["rendering.ffmpeg-finalizer"]` or the real key).
- Confirm it is not vacuous (not just `assert True` / membership of an always-present parent).
- Confirm the offline npm test still restores config in `finally`.

## Check 3 — BLE001 narrowing

Host says 6 blind `except Exception`/`except:` in our files were narrowed to `OSError`/`ValueError`/`TypeError`/`json.JSONDecodeError`/`RendererException`/`RenderingRegistryError`.

For EACH narrowed site:
- What was caught before?
- What is caught now?
- Could a still-expected exception (e.g. KeyError, AttributeError, RuntimeError, subprocess errors, FileNotFoundError-as-OSError) now leak?
- FileNotFoundError is an OSError subclass — OK if they catch OSError.
- RendererException / RenderingRegistryError: confirm those types are imported and actually raised at those sites.

`test_production_callers` allowlist: confirm it only adds the planner's cross-backend pure-helper imports (F821), not a blanket exemption.

## Output (<300 words)

```
DEAD_CODE: PASS | FAIL
  removed: <what>
  still_referenced: none | <cite>
  behavior_change: none | <what>
FINALIZER_ASSERT: PASS | FAIL
  assertion: <file:line + exact check>
  matches_emitted_shape: yes | no <why>
  offline_finally: yes | no
BLE001: PASS | FAIL
  sites: <file:line old→new>
  lost_catch: none | <site + exception that now leaks and matters>
  imports_ok: yes | no
ALLOWLIST: justified | overbroad <why>
ISSUES: none | numbered checkpoint-failing problems only
NOTES: non-blocking
```

Take a position. Cite file:line. Do not hedge.
