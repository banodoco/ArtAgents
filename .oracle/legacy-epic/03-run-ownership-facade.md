# Explore: run ownership and facade command compatibility

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. `astrid/core/contracts/capability_runner.py` and
   `astrid/core/execution/executor/runner.py`: how an executor run is created
   (project run ledger, run id, output dir). When `rendering.render` is
   invoked, what run artifacts exist? If a render backend were invoked as a
   subprocess command (not a nested executor), would it create a nested
   project run? Trace the exact code path.
2. `astrid/core/project/run.py`: how runs are recorded. Confirm that calling a
   subprocess directly (e.g. `subprocess.run([...])`) from inside an executor
   does NOT create a project run.
3. `astrid/packs/rendering/executors/render/run.py` and `executor.yaml`: the
   current facade inputs (timeline, assets_registry, theme, engine, out...)
   and outputs. How is `--engine` validated (list the allowed values and
   where)? How does `runner.py::_normalize_render_command_compat` reorder
   theme args (find that function and describe the shim)?
4. `astrid/core/pack/entrypoint.py` (or wherever `guard_canonical_entrypoint`
   lives): what it rejects and why direct-module invocation of run.py would
   trip it.

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts
- Unknowns
- Risks (e.g. nested runs, stale argv ordering, direct-module bypass)
- Suggested approach
