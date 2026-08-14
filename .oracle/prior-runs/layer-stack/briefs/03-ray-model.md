Explore in depth: how "Ray" handles video layering and compositing — the user explicitly asked how Ray does it, as a reference for Astrid's generalized layer/stack model.

Context: Astrid is a video-timeline renderer (Python + Remotion/hyperframes/three.js backends). We're designing a generalized way to stack renderers as layers (transparent or not) and composite them. The user asked "how does Ray handle it?" — research Ray thoroughly.

NOTE ON IDENTITY: "Ray" is ambiguous. Investigate candidates and identify which is most relevant to VIDEO RENDERING / COMPOSITING / TIMELINE EDITING:
1. **Ray.so** — https://www.ray.so — screenshot tool? Not video. Rule out or confirm.
2. **Ray video editing** — search for a video editor or compositor called "Ray": possibly a Mac video editor, an open-source NLE (non-linear editor), a JS/TS video library, or a compositing engine. Try queries: "Ray video editor", "Ray compositing engine", "Ray NLE open source", "Ray video rendering library github", "Ray timeline layers blend modes".
3. **Ray framework / language** — there's "Ray" (Elixir distributed computing), "Ray" (Python distributed ML — ray.io, the ML orchestration framework). Unlikely relevant to video compositing, but note if it has any media/rendering relevance.
4. **Ray as a 3D/WebGL scene library** — search "ray renderer three.js" / "ray webgl video".
5. **Any video compositing system the user might mean** — if you find a strong match, dig deep into HOW it models: layers/tracks, z-order, blend modes, alpha/transparency, background, nested compositions, and how it splits rendering across engines (if at all).

For the identified Ray (or the best candidate if multiple):
1. **The layer model**: how does Ray represent visual layers/tracks? Explicit z-index? Array order? Grouping/nesting?
2. **Blend modes + opacity**: which blend modes does it support (normal/multiply/screen/overlay/etc)? Per-layer opacity? How are they applied (GPU shader? CPU compositor? ffmpeg filtergraph?)
3. **Alpha/transparency**: how does Ray handle transparent layers — per-pixel alpha, straight vs premultiplied, transparent video codecs (WebM/ProRes)?
4. **Compositing architecture**: is it a single compositor pass over all layers, or per-layer render then merge? Does it let different ENGINES/backends render different layers (like Astrid wants to do)?
5. **Timeline ↔ compositor relationship**: how does the timeline/track model map to the compositing graph?
6. **The generalized takeaway**: what does Ray's design suggest Astrid should adopt (and what to avoid)?

Report <400 words. Cite sources (URLs). If you cannot identify a confident "Ray" video system, say so explicitly, report the best 1-2 candidates with their actual models, and give the generalized compositing lessons anyway.
