Explore in depth: the exact recipe for capturing three.js (WebGL) rendered frames to video on macOS arm64, headlessly, without a display.

Investigate and report VERIFIED facts with file/command evidence:

1. **three.js headless WebGL**: Does `three` npm package (latest, e.g. 0.16x-0.17x) render in headless Chromium (puppeteer-core) with WebGL via SwiftShader? Known working pattern: `new WebGLRenderer({canvas, antialias: true, preserveDrawingBuffer: true})` + `renderer.domElement` → `canvas.toDataURL('image/png')` per frame, or `webglcontextlost` handling, or `preserveDrawingBuffer` requirement for capture. Confirm preserveDrawingBuffer is needed for frame capture.
2. **Per-frame capture**: puppeteer `page.screenshot` vs in-page canvas capture (offscreen canvas → blob → node). Which is deterministic? Frame timing: how to advance a three.js scene exactly N frames at fps without drift (requestAnimationFrame vs manual render + clock).
3. **Headless Chromium availability**: is a chromium binary already available on this machine (puppeteer cache, hyperframes bundled chrome, remotion's chrome)? Paths. `npx hyperframes browser` or `@puppeteer/browsers` install. Evidence via `find` on ~/.cache/puppeteer, ~/Library/Caches, /Applications.
4. **Node offscreen GL alternatives** (only if headless chrome is problematic): `gl` (headless-gl), `glfw`, node-canvas WebGL, three.js + `offscreencanvas` in node 24. Honest maturity assessment — do these work with three r16x on node 24 arm64? (Check npm metadata, READMEs, known issues.)
5. **Muxing frames to mp4**: ffmpeg from PNG frames vs piping raw RGBA to ffmpeg stdin (`-f rawvideo`). Frame rate + timescale conventions (Astrid rule: mp4 timescale = double fps until >= 10000, e.g. 24->12288).
6. **WebM/VP9 alpha**: if frames have transparency (three.js alpha:true), can we emit webm with alpha for overlay compositing later? `--format webm` exists in hyperframes; for a raw three.js pipeline, VP9 alpha via ffmpeg (`-c:v libvpx-vp9 -pix_fmt yuva420p`)? Feasibility note only.

Rank findings by relevance to building a minimal honest three.js->mp4 render backend. <300 words. Evidence with exact paths/versions.
