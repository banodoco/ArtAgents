# Explore: canonical canvas/FPS and hybrid planner internals

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

1. In `astrid/packs/rendering/executors/render/run.py`, locate the hybrid
   planner: `_complex_clip_windows` (or equivalent), `_hybrid_segments`, and
   any handle/segment math. Describe exactly:
   - how complex windows are detected (which clip features trigger a window);
   - how segment boundaries are computed (frames? seconds? rounding?);
   - how canvas width/height/FPS are resolved for planning (does it read the
     theme? timeline? hardcoded?);
   - what happens with speed changes, overlapping audio, transitions, and
     opacity.
   Quote the relevant code with line numbers.
2. How the canonical canvas/FPS is derived for REMOTION: theme resolution
   (`astrid/core/theme.py` load_theme), `theme_overrides`, the timeline model
   (`astrid/core/timeline/model.py`), and `remotion/src/Root.tsx` (the actual
   composition default). Does hybrid planning use the same merged-theme canvas
   as Remotion? If not, show the divergence.
3. `_concat_segments` — the current concatenation: hardcoded fps=30? H.264/AAC
   stereo 44.1kHz? re-encode always? no probe? quote it.

## Report format

Ranked findings with file:line evidence. Max 350 words. End with:
- Verified facts
- Unknowns
- Risks for porting hybrid into a generic planner/dispatcher
- Suggested approach
