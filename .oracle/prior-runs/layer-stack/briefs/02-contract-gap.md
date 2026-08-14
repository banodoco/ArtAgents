Explore in depth: the renderer CONTRACT's gap — exactly what the pipeline does with the timeline's 2D layering when it renders, and precisely which contract pieces must change to support layer-stacking.

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan (branch layer-plan, HEAD dc296c3e).

Context: The timeline schema has tracks with blendMode/opacity/z-order (see brief 01). The renderer contract (FrameWindow, RenderSegment, planners, finalizer) appears to be time-only. We need the EXACT contract surface to change for a generalized layer model.

Investigate and report VERIFIED facts with file:line evidence:

1. **FrameWindow** (astrid/core/rendering/contracts.py ~388): fields — start_frame, end_frame, fps_rational, source_range, speed. Time-only? Any layer concept? What validation runs (start>=0, end>start)?
2. **RenderSegment** (~1306): window + renderer + input_hashes. Docstring says "one complete temporal window assigned to one qualified backend". No layer/z/blend fields. What does the plan validator enforce about segments (exact tiling, no overlap — find `segments[N] overlaps or is out of order` and the `_assert_exact_tiling`-style checks in contracts.py + planners)?
3. **RenderPlan** (~): the full plan shape — planner, segments, finalizer, profile, total_frames, reasons, window. Where would layer metadata attach (segment-level layer spec vs plan-level layer registry)?
4. **The finalizer contract**: `rendering.ffmpeg-finalizer` (astrid/packs/rendering/finalizers/ffmpeg/run.py) — the `finalize` verb, `_preflight_segments`, concat-only (`build_concat_command`). Does it assume segments are non-overlapping time-slices (concat order = time order)? What would an OVERLAY mode need (ffmpeg filtergraph with [0:v][1:v]overlay)? Is there any alpha handling?
5. **Host-slicing**: `RenderService._window_timeline` / `_window_clip` (astrid/core/rendering/service.py) — when a renderer gets a window (supports_windows: false), how are tracks materialized? Does the materialized window timeline carry ALL tracks (so a renderer could know its layer) or just the clips in the window?
6. **The planner surface**: legacy_hybrid + threejs_hybrid — how they build segments (hardcoded renderer pairings), and whether ANY planner emits overlapping windows. The plan validator's `segments tile exactly` — where exactly (contracts.py RenderPlan.__post_init__?) and what it would take to relax to "per-layer tiling".
7. **alpha capability**: do any renderer.yaml manifests declare anything about transparency/alpha? (grep alpha/transparent in backends/*/renderer.yaml, finalizers). The SupportReport features constraint: boolean/string only.
8. **The frozen contract tests**: tests/core/rendering/ — which tests lock "no overlapping segments" (test_plan validation, test_contracts)? Changing the contract will break which exact tests?

Rank findings by relevance to "the minimal contract change to support per-layer stacking". <350 words. Evidence with file:line. End with a crisp 'contract-change surface' list.
