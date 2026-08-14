Explore in depth: the Astrid timeline schema's LAYERING model — what the schema already supports for stacking/compositing that the renderer contract ignores.

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan (branch layer-plan, HEAD dc296c3e).

Context: Astrid renders video timelines. The timeline schema appears to encode a full 2D layering model (visual tracks stack in z, with blend modes + opacity), but the renderer contract collapses it to 1D time-slices. We need the exact schema semantics to design a generalized "stack renderers in layers" capability.

Investigate and report VERIFIED facts with file:line evidence:

1. **TrackDefinition** (astrid/core/timeline/banodoco_schema.py ~174-187): every field — `id`, `kind` (TrackKind = visual|audio), `label`, `scale`, `fit` (TrackFit = cover|contain|manual), `opacity`, `volume`, `muted`, `blendMode` (TrackBlendMode = normal|multiply|screen|overlay|darken|lighten|soft-light|hard-light), `app`. What does each mean for compositing?
2. **Z-order semantics**: how is a visual track's paint order determined? (The rendering backends' comments say "Astrid visual tracks paint in reversed array order (later = on top)" — verify in remotion/run.py, threejs/run.py, hyperframes/render.py, and any schema/loader code.) Is z-index implicit in array order, or is there an explicit field?
3. **Clip-level layering**: ClipDefinition fields — `opacity` per clip, `params`, `text`, `entrance`/`exit` (ClipEntrance/ClipExit with type/duration/intensity/params). Is there per-clip blendMode or only per-track? What does clip opacity mean for a layer?
4. **Blend mode semantics**: TrackBlendMode lists 8 modes — do the backends actually IMPLEMENT them (grep multiply/screen/overlay/darken/lighten in remotion/run.py, the timeline-composition package, threejs/run.py, hyperframes/render.py)? Or are they schema-declared but never consumed? Where would they be consumed in a compositor?
5. **How tracks flow through rendering**: trace how the service/planner sees tracks — does a segment know WHICH tracks it owns? (RenderSegment has window + renderer only; the window's materialized timeline has tracks.) When the service host-slices a window (`_window_timeline`), does it filter tracks? (service.py — check whether _window_timeline includes ALL tracks or just used ones.)
6. **Audio tracks**: how do audio tracks coexist with visual layering — are they a separate "layer" the compositor must not touch?
7. **What the schema does NOT have**: is there any explicit zIndex/layer/order field beyond array order? Any per-track transparency flag? Any "background track" concept (the canvas/theme background vs a track)?

Rank findings by relevance to "design a generalized layer/stack model where renderers composite in space". <350 words. Evidence with file:line. End with a crisp 'schema layering facts' list.
