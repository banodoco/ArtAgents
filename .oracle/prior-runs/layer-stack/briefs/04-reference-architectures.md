Explore in depth: compositing REFERENCE ARCHITECTURES — how mature video systems model layered compositing, as design input for Astrid's generalized layer/stack model.

Repo context: Astrid renders timelines via pluggable renderer backends (Remotion React/JSX, hyperframes HTML, three.js WebGL, ffmpeg native). Currently ONE renderer composites each time-window internally (React z-index, CSS z-index, WebGL Z, ffmpeg filtergraph). We want to let DIFFERENT renderers own DIFFERENT layers of the SAME time window and composite the results — transparent or not. Design input needed from established systems.

Investigate and report VERIFIED facts with citations (URLs + local file evidence where relevant):

1. **Remotion's own compositing** (local: remotion/ project + @remotion/*): how does TimelineComposition stack tracks? (AbsoluteFill? z-index? order?) Does Remotion support alpha/transparent renders (`--codec` vp8/vp9 webm with alpha, or `transparent` option)? How does @remotion/three's ThreeCanvas composite with other React elements?
2. **ffmpeg filtergraph compositing** (local: astrid/packs/rendering/finalizers/ffmpeg/run.py): the concat model vs `overlay` filter — `[0:v][1:v]overlay=...:format=auto`, blend filters (`blend=all_mode=multiply`), `format=yuva420p` for alpha. What does a generic N-layer composite filtergraph look like (chained overlays in z-order, per-layer opacity via `format=rgba` + `colorchannelmixer` or `overlay` alpha, per-layer blend mode via `blend`)? Cite ffmpeg docs or the finalizer's existing filter usage.
3. **HTML/CSS compositing** (local: hyperframes/render.py): how hyperframes stacks `.clip` sections (z-index, data-track-index, data-layout-allow-overlap) — CSS `mix-blend-mode` exists; does the adapter use it? What would `mix-blend-mode` + opacity give for free?
4. **After Effects-style layer model** (web): AE's layer stack (bottom-to-top order, blend modes incl. 8-10 standard, track mattes/alpha, opacity, nesting). What's the canonical NLE/compositor layer semantics Astrid should mirror?
5. **NLEs**: DaVinci Resolve / Premiere track model — video tracks stack top-to-bottom, opacity/blend per clip+track, alpha from codecs. Key semantics worth copying.
6. **WebGL/canvas compositing** (local: threejs composition): how three.js composites its own planes (renderOrder, transparent sort) — and how a whole transparent WebGL layer would merge with another engine's output.
7. **The generalized pattern**: what do ALL these systems share? (bottom-to-top z-order, per-layer opacity + blend mode, alpha channel, background layer, a final composite pass). What's the minimal vocabulary Astrid needs: layer {z_index, blend_mode, opacity, alpha} + compositor pass + background?

Report <400 words. Citations (URLs + file:line). End with 'the shared layer vocabulary' list Astrid should adopt.
