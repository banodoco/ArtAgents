# Explore: Remotion registry generation lock boundary

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

The plan serializes Remotion renders around shared generated sources (element
registries + active-theme pointer) with a file lock. Verify the lock boundary
is complete: every mutation of shared generated state must happen under the
same lock for the whole V1 render.

1. `scripts/gen_effect_registry.py`: what shared files does it write
   (package `*.generated.ts` files, 5-extension shim families,
   `_active_theme` symlink)? Quote the file-writing section. Does it ever
   mutate state OUTSIDE the generated files (e.g. `node_modules` caches,
   `.astrid-registry-state.json`)?
2. `astrid/packs/rendering/executors/render/run.py`:
   - `_regenerate_element_registries` (or equivalent): when does it run the
     subprocess, what does it read to decide regeneration
     (`.astrid-registry-state.json`?), and is the check-then-act race as
     described?
   - Where in the render lifecycle does registry generation happen relative
     to the HTTP server start and the Remotion subprocess? Quote the order.
   - Does anything else mutate `remotion/src/` or the generated TS during a
     render (props writes, staging under `remotion/public/astrid-effects/`)?
     If yes, are those under the same lock today?
3. The `filelock` usage in `astrid/packs/training/executors/asset_cache/run.py`
   (the repo's only concurrency-lock test): quote the pattern so the registry
   lock can mirror it.
4. Does `npm run gen-types` or any other script also regenerate these files
   outside the render path? Where else could a concurrent writer come from?

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts (complete mutation inventory)
- Unknowns
- Risks (mutations outside the lock)
- Suggested approach (the exact lock scope needed for V1)
