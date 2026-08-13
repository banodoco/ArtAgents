# Explore: error envelopes, asset cache boundary, and executor output enforcement

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. Error envelopes:
   - `astrid/core/contracts/errors.py` and `astrid/core/contracts/exec_error.py`:
     the structured error types and symbolic codes available (list them).
   - Exit-code conventions: where exit 2 (expected failure) vs 1 (bug) vs 130
     (interrupt) are decided for executor runs — find the code that maps
     errors → exit codes.
   - How subprocess failures are wrapped today (`astrid/core/subprocess_env.py`,
     any `run_subprocess` helper): stderr capture, nonzero exit, missing
     binary.
2. Asset cache boundary:
   - `astrid/packs/training/executors/asset_cache/run.py`: what it does
     (download/prune/list), which primitives it owns (cache dir layout, hash
     keys, URL fetch), and whether the render path imports it
     (`grep -rn "asset_cache" astrid/packs/rendering`).
   - Where the render path's own asset caching lives in run.py (common-root
     handling, local vs URL classification).
3. Executor output enforcement:
   - `astrid/core/execution/executor/runner.py::resolve_declared_output_paths`
     (or equivalent): what it does when a declared output is missing after a
     successful run — ignore? error? Quote it. The plan claims the runner
     currently ignores missing declared outputs; verify.
4. Atomic IO + hashing helpers in `astrid/core/foundation/` (atomic_io,
   hash): names and signatures so new code can reuse them.

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts
- Unknowns
- Risks for backend error mapping and asset rehoming
- Suggested approach
