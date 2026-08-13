# Explore: provenance consumers and sidecar lifecycle

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. In `astrid/packs/rendering/executors/render/run.py`, find every function
   that writes or reads the `<output>.provenance.json` sidecar. Describe the
   current provenance schema fields (engine, timeline, assets, pack order,
   theme, registry hash, effect ids, staged assets, hybrid segments...). Quote
   the dict construction with line numbers.
2. `_delete_previous_render_outputs_for_timeline` — how it matches previous
   runs (reads sidecar `timeline` field), what it deletes, and whether it is
   atomic. This is the current "previous-output cleanup" reader.
3. Who ELSE consumes the provenance sidecar? Search the repo
   (`grep -rn "provenance" --include=*.py astrid tests` and any JSON consumers):
   hybrid ingestion, iteration finalization
   (`astrid/packs/video_editing/orchestrators/iteration_video/`), `editorial.validate`,
   tests. For each consumer, note which fields it reads (so a v2 schema can
   keep compatibility projections).
4. Which renders currently produce NO sidecar (plain ffmpeg? audio-reactive?
   hybrid ffmpeg-only path?). Verify by reading the code paths.

## Report format

Ranked findings with file:line evidence. Max 300 words. End with:
- Verified facts (field list + consumers)
- Unknowns
- Risks for provenance v2 migration
- Suggested approach
