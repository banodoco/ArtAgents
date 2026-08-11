# Explore: local HTTP serving and Remotion lifecycle

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. In `astrid/packs/rendering/executors/render/run.py`, locate
   `_RangeHTTPRequestHandler`, `_server_root_for` (or equivalent), and the
   asset URL resolution path:
   - How is the server root chosen (common parent of assets)?
   - How are Range requests handled? Is the server restricted to the chosen
     root (path traversal guards)?
   - How is the port chosen (fixed port? bind to 0?) — is there a race?
   - How is the server started/stopped relative to the render subprocess?
     Thread joined? What leaks if a failure happens before the try/finally?
2. The Remotion invocation path: props creation (JSON file? merged theme?),
   element registry generation (`scripts/gen_effect_registry.py` — does it
   mutate shared generated files? locking? atomicity?), effect asset staging
   (where staged, cleanup), subprocess invocation (process group? timeout?
   env sanitization?), and the zero-exit-with-no-output case (is it treated
   as success?).
3. Whether fixed props/staging paths collide across concurrent renders (find
   the path construction).
4. Existing tests covering serving/registry/staging:
   `tests/packs/rendering/test_render_remotion_registry.py`,
   `test_url_pipeline_smoke.py`, `test_asset_cache.py` — summarize what each
   asserts.

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts
- Unknowns
- Risks (server leaks, bind races, registry races, path collisions, silent
  failures)
- Suggested approach
