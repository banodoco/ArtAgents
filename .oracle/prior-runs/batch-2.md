# Megado Batch 2 — Implement the Three composition

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle` (branch `oracle-run-threejs`). Execute ONLY the tasks below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. Do NOT run the full test suite. Do NOT run formatters/linters. The oracle gates the result.

Environment: `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` (Node 24) for npm/remotion; `PYENV_VERSION=3.11.11` for Python/Pillow. Previous batch (99e6d24c) installed @remotion/three@4.0.455, @react-three/fiber@8.18.0, three@0.185.1, @types/three@0.185.4; remotion.config.ts has `Config.setChromiumOpenGlRenderer('angle')`. node_modules/.remotion/chrome-headless-shell is manually populated (VERSION 149.0.7790.0) — `npx remotion still` works.

Context: This batch builds `ThreeTimelineComposition.tsx` — the Remotion composition that renders an Astrid timeline as a three.js scene. It receives the SAME serialized timeline/assets/theme props shape the existing TimelineComposition uses. The Astrid Python adapter (next batch) will invoke it with composition id `ThreeTimelineComposition`.

## Reference material — read these FIRST
- `remotion/src/Root.tsx` — existing composition registration + canvas/duration authority. Reuse its props shape and metadata logic.
- `remotion/src/` — the existing timeline composition (external @banodoco/timeline-composition; check how the serialized timeline is consumed — the props passed to the composition, the timeline JSON shape: theme, theme_overrides.visual.canvas{width,height,fps}, theme_overrides.visual.background, tracks[{id,kind,label}], clips[{id,at,track,clipType,hold,text/params,...}]).
- `node_modules/@remotion/three` — the `<ThreeCanvas>` API (props, frameloop behavior; it syncs via useCurrentFrame + delayRender — do NOT fight it).
- `tests/fixtures/renderer_packs/hyperframes/render.py` — the established text-param mapping (fontSize/color/align/weight/textShadow/maxWidth/anchor/offsetX/offsetY) as CSS; you're porting the same fields to a canvas 2D context.

## Tasks

### T2.1 — [XHARD] `remotion/src/ThreeTimelineComposition.tsx`
A composition that:
- Accepts the same serialized timeline/assets/theme props shape as the existing composition (check Root.tsx for what's passed).
- Renders through `<ThreeCanvas>`.
- Uses an ORTHOGRAPHIC camera whose world units map directly to output pixels (left=0, right=width, top=0, bottom=height, near/far sensible; camera at z positive looking at z=0 plane).
- Renders the resolved background color as the scene background (priority: theme_overrides.visual.background → merged theme visual.color.bg → black). Must show even with no clips.
- For each text clip visible at the current frame: draw the text to an offscreen 2D canvas (browser document.createElement('canvas')) styled with the mapped text params, upload as THREE.CanvasTexture on a PlaneGeometry positioned at pixel coordinates (anchor/offsetX/offsetY/maxWidth respected).
- Deterministic Z ordering: Astrid visual tracks paint in reversed array order (later track = on top) — assign z = -trackIndex or similar so later tracks are nearer the camera.
- Clip visibility from Remotion frame/FPS only: visible when frame/fps in [at, at+hold). NO useFrame, NO requestAnimationFrame, NO wall-clock, NO randomness, NO network fonts (fixed generic sans-serif stack), NO Drei, NO decorative rotation/motion, NO lights/shaders/post-processing/custom cameras.
- Dispose textures/materials/geometry on unmount.
- Map ONLY these text fields: text.content, text.fontSize, text.color, text.align, text.bold, params.anchor, params.offsetX, params.offsetY, params.textShadow, params.maxWidth, params.weight. Ignore everything else.

### T2.2 — Registration in `remotion/src/Root.tsx`
Register `<Composition id="ThreeTimelineComposition" ...>` reusing the existing canvas-selection + timeline-duration authority; clamp `durationInFrames` to at least 1 (empty timeline = 1 frame).

### T2.3 — Prove it with disposable stills (do NOT commit fixtures/outputs)
1. Background-only timeline fixture (canvas 160x90, background #1a2e3f or similar): `npx remotion still` at frame 0 → Pillow: 160x90, ALL pixels = the background color (or near, within tolerance).
2. Text timeline fixture (a text clip "HELLO" at 0..1s, 160x90): still at frame 0 → Pillow: 160x90, contains pixels that are NOT the background color (text visible); still at frame PAST the clip's end (e.g. frame 60 if clip ends at 1s@24fps) → text NOT visible (background only) — proving frame visibility.
3. Save the Pillow assertions to `.oracle/findings/threejs-composition-proof.txt`.
4. Remove disposable fixtures/outputs before checkpoint; revert any temporary Root.tsx registration additions if you used them (keep only the permanent ThreeTimelineComposition registration).

### T2.4 — typecheck + bundle
`npm run typecheck` and `npm run bundle` from remotion/ — both exit 0.

### T2.5 — Zero-core-edit + cleanliness
`git diff --name-only <previous-checkpoint-sha>..HEAD -- astrid/core/` — must print NOTHING (previous checkpoint SHA = 99e6d24c, or ask git log for the latest batch-1 commit). `git status --short` clean of fixtures, stills, PNGs, bundles.

## Acceptance (oracle checks)
- ThreeTimelineComposition.tsx exists with the exact scope above (read it: orthographic pixel-space, CanvasTexture text, deterministic Z, frame-only visibility, disposal, background even with no clips, exact field set).
- Registered in Root.tsx with durationInFrames clamp >= 1.
- Proof file has: background-only = uniform bg; text visible at frame 0; text absent past clip end.
- typecheck + bundle green.
- No astrid/core/ changes; no fixtures/stills committed.

## Protocol
- Commit as `megado: batch 2 — ThreeTimelineComposition`.
- Report <400 words: what you built (composition structure), the proof command outputs (Pillow numbers), typecheck/bundle exit codes, final git status + astrid/core diff. Evidence-first.
