Explore in depth: ALPHA / TRANSPARENCY mechanics — can each Astrid renderer backend actually output transparent (alpha) video, and what does it take? This is the load-bearing capability for "stack renderers as layers, transparent or not".

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-layer-plan (branch layer-plan). Local evidence in the repo + node_modules. Web for docs.

Investigate and report VERIFIED facts with file:line + command evidence:

1. **hyperframes** (local: tests/fixtures/renderer_packs/hyperframes/render.py + node_modules hyperframes package): the CLI help showed `--format webm/mov/png-sequence` with "(MOV/WebM render with transparency; png-sequence writes RGBA frames)". Verify: what exact flag combination produces transparent output? Does the adapter's composition need a transparent background (currently it writes a full-bleed bg div — see render.py `_compose_html`)? What codec (VP9?) and does the engine support it headless?
2. **Remotion** (local: remotion/ node_modules + web docs remotion.dev): does Remotion render transparent video? Search for `transparent` / `alpha` / `--codec=vp8/vp9` / `imageFormat=png` in @remotion/renderer types + remotion.dev/docs. What's the exact API (Config.setOutputFormat? --codec? --pixel-format=yuva420p?) and does it work with the ANGLE/headless setup this repo uses?
3. **three.js** (local: remotion/src/ThreeTimelineComposition.tsx): the WebGLRenderer currently renders a solid `<color attach="background">`. To output alpha: `renderer alpha:true` + no background color + `preserveDrawingBuffer`? In the @remotion/three <ThreeCanvas> context, what's needed? Would the Remotion transparent-output path (from #2) carry the WebGL alpha through?
4. **ffmpeg** (local + web): generating a transparent segment — `-c:v libvpx-vp9 -pix_fmt yuva420p` (webm alpha), or PNG sequence with alpha, or ProRes 4444 (mov). For a compositor that overlays segments: what input formats does ffmpeg's `overlay` need (straight vs premultiplied alpha, yuva420p)? The `format=auto` option?
5. **The compositor consumer**: for the proposed `rendering.ffmpeg-compositor`, what does it need from a transparent segment (codec/container/pix_fmt) and how does `overlay` handle different resolutions (scale first?) and different fps?
6. **Reality check**: which of the 4 engines can ACTUALLY produce transparent segments today with the repo's current setup (node 24, ANGLE chrome, ffmpeg present)? Rank: ready now / needs flag / needs adapter change / not possible.

Report <400 words. Evidence with file:line + commands. End with 'alpha capability by engine' table.
