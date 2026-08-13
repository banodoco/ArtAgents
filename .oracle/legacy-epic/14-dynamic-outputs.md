# Explore: dynamic output names and declared-output consumers

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

The revised plan wants iteration renders to target `iteration.mp4` directly
(so provenance isn't orphaned by a post-render rename). That requires
understanding how executor declared outputs are resolved and consumed.

1. `astrid/core/execution/executor/runner.py`:
   - `resolve_declared_output_paths` (or equivalent): how are an executor
     manifest's declared `outputs` resolved relative to run root? Does the
     path template support dynamic names like `{output_name}` or is it fixed
     filename only? Quote the code.
   - After a successful run, what reads `result.outputs` — how do cache
     hits, pipeline propagation, and artifact collection use the declared
     output paths? (grep consumers of `result.outputs` /
     `"outputs"` in `core/execution`, `core/integrations`).
2. `astrid/packs/rendering/executors/render/executor.yaml`: quote the outputs
   section (what filename does it declare: `hype.mp4`?). If a caller wanted
   `iteration.mp4`, what would need to change?
3. `astrid/core/integrations/arnold/step_adapter.py`: how does Arnold collect
   executor outputs — does it depend on the declared filename matching the
   produced file? Would a dynamic output name break it?
4. `astrid/core/execution/orchestrator/pipeline.py` (or wherever step
   produces propagate): how are an executor step's outputs propagated to
   downstream steps (by declared name? by directory scan?). Would an output
   named other than `hype.mp4` break the hype pipeline?

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts (exact resolution + consumers of declared outputs)
- Unknowns
- Risks (dynamic output name breaking cache/pipeline/Arnold)
- Suggested approach (safe way to render directly to iteration.mp4)
