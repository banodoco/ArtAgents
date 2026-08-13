# Three.js Renderer — `rendering.threejs` and `rendering.threejs-hybrid`

**Status**: active (epic: three.js rendering, 2026-08-13)
**Scope**: The `rendering.threejs` renderer — a thin backend that renders
background/plain-text Astrid timelines as three.js WebGL scenes captured
through the existing Remotion project — and the opt-in
`rendering.threejs-hybrid` planner that routes plain-text regions to
Three.js and everything else to Remotion. It does **not** describe the
ordinary `rendering.remotion` backend (see
[render-adapter.md](render-adapter.md)).

## What it is

`rendering.threejs` renders complete Astrid timelines whose visual content
is plain text (or nothing but a background) as three.js WebGL scenes. The
scene is captured by the same Remotion machinery that powers
`rendering.remotion`:

- The composition is `ThreeTimelineComposition` in `remotion/`
  (`remotion/src/ThreeTimelineComposition.tsx`), rendered through
  `<ThreeCanvas>` from `@remotion/three` with a deterministic frame clock
  (`frameloop="never"` + `state.advance()` once per frame, synced to
  `useCurrentFrame()` — no wall-clock sources).
- Text clips are drawn into an offscreen 2D canvas and uploaded as
  `THREE.CanvasTexture` planes on an orthographic pixel-space camera; the
  scene background is a plain color even with zero clips.
- Rendering runs headless through Remotion's bundled Chrome Headless Shell
  with the project-wide ANGLE configuration
  (`Config.setChromiumOpenGlRenderer('angle')` in
  `remotion/remotion.config.ts`).
- The backend reuses the Remotion backend's execution helper
  (`_execute_remotion`), so it shares the **same Remotion render lock** —
  one lock file, never a second capture stack.
- Output is an H.264/AAC MP4 with the same always-muxed AAC track as
  Remotion: `audio_ownership` is always `rendered`.

The renderer has its **own identity and provenance**: `engine="threejs"`,
fragment `rendering.threejs`, `capture_host="remotion"`. It never claims to
be `rendering.remotion`.

## Installation

`rendering.threejs` needs no Python dependencies beyond the Astrid wheel.
The render runtime lives in the existing `remotion/` project:

1. **The four exact npm dependencies** are pinned in
   `remotion/package.json` and the committed `package-lock.json`:

   | Package | Version |
   |---|---|
   | `@remotion/three` | `4.0.455` |
   | `@react-three/fiber` | `8.18.0` |
   | `three` | `0.185.1` |
   | `@types/three` | `0.185.4` |

   Install from the lockfile (no package.json/lockfile mutation):

   ```bash
   cd remotion
   npm ci
   ```

2. **Chrome Headless Shell** — `@remotion/renderer` downloads its bundled
   Chrome Headless Shell into `remotion/node_modules/.remotion/`. Do not
   depend on system Chrome or Playwright caches.

3. **ANGLE** — `remotion/remotion.config.ts` sets
   `Config.setChromiumOpenGlRenderer('angle');`. This is a project-wide
   setting shared by both backends; the Three.js composition needs WebGL
   in headless Chromium.

The backend fails closed: `support`/render report missing
`node_modules/`, missing `three` / `@remotion/three` /
`@react-three/fiber` packages, and missing `node` / `npx` / `ffprobe`
binaries before any render is attempted.

## Direct use

```python
from astrid.sdk.rendering import render

published = render(
    timeline_path="timeline.json",
    assets_registry_path=None,
    out_path="out.mp4",
    backend="rendering.threejs",
)
```

`render(..., backend="rendering.threejs")` accepts complete timelines only
(no native frame windows) and takes **no backend_config in v1** — any
non-empty `rendering.threejs` own-namespace config is rejected.

### Accepted (v1 support matrix)

| Input | Verdict |
|---|---|
| Empty timeline (background only) | Accepted — canvas + background color |
| Text clips on visual tracks | Accepted |
| `text` fields: `content`, `fontSize`, `color`, `align`, `bold` | Accepted — exact set |
| `params` fields: `anchor`, `offsetX`, `offsetY`, `textShadow`, `maxWidth`, `weight` | Accepted — exact set |
| Canvas `width`/`height`/`fps` (positive integers) | Required |
| `audio` | Must be `rendered` (output always carries a muxed AAC track) |

### Rejected

| Input | Verdict |
|---|---|
| Media clips (any `clipType` other than `text`) | Rejected |
| Audio tracks, or text clips carrying volume > 0 | Rejected (visual-only in v1) |
| Effects, transitions, animation | Rejected in v1 |
| `opacity` != 1 | Rejected in v1 |
| Unknown `text` fields or unknown `params` | Rejected |
| Unknown `rendering.threejs` backend_config keys | Rejected; any non-empty config on render | 
| Native frame windows | Rejected — complete timelines only |
| `audio` other than `rendered` (e.g. passthrough) | Rejected |
| Non-canonical profile | Rejected — 90 kHz declared timescale, always-muxed AAC, same as Remotion |

## Hybrid use

```python
from astrid.sdk.rendering import render

published = render(
    timeline_path="timeline.json",
    assets_registry_path="assets.json",
    out_path="mixed.mp4",
    backend="rendering.threejs-hybrid",
    audio="rendered",
)
```

`render(..., backend="rendering.threejs-hybrid")` is an opt-in planner that
splits the timeline into integer-frame windows:

- **Plain-text temporal regions → `rendering.threejs`** (exactly the
  accepted matrix above).
- **Everything else → `rendering.remotion`** — media clips, effects,
  transitions, opacity, non-base visual tracks, audio fades, and gaps.
  Overlapping text/media regions merge into one Remotion window (no
  sub-frame splits; conservative occupancy tiling).
- **`rendering.ffmpeg-finalizer` is pinned** as the finalizer: all segment
  MP4s are normalized to the canonical profile and concatenated into ONE
  output file. **Temporal concat only — there is no spatial compositing.**
- Empty timelines are rejected by the hybrid planner (unlike the direct
  backend, which accepts background-only).

The planner is non-recursive, never dispatches a planner id as a segment
renderer, and every segment carries real registry evidence (manifest
digests, source pack ids, trust eligibility) — never fabricated support
decisions.

## Provenance identity

For a direct `rendering.threejs` render the sidecar reports:

- `engine` / `legacy_v1.engine` → `threejs`
- backend fragment `rendering.threejs` with `renderer: "threejs"`,
  `three_version`, `capture_host: "remotion"`, and
  `composition: "ThreeTimelineComposition"`
- `audio_ownership` → `rendered`

For a hybrid render the sidecar additionally reports the planner
(`rendering.threejs-hybrid`), the pinned finalizer
(`rendering.ffmpeg-finalizer`), exact `segments_v2` windows with renderer
ids and support decisions, and backend fragments for every segment renderer
**plus** a `rendering.ffmpeg-finalizer` fragment (`finalizer_kind`,
`finalizer_version`, `segment_count`, `stream_copied_segments`,
`normalized_segments`, `audio_mode`).

## Explicit v1 exclusions

`rendering.threejs` deliberately does **not** support, in v1:

- Media textures (video/image clips as `THREE.Texture`).
- GLTF models, custom meshes, shaders, lights, cameras, or network fonts —
  materials are `MeshBasicMaterial` (unlit, texture-only), fonts are a
  fixed generic sans-serif stack.
- A scene/animation DSL — there is no scene-graph or animation API; the
  serialized Astrid timeline is the only input.
- Alpha compositing — output is opaque H.264/AAC MP4.
- Arbitrary composition IDs — the backend is fixed to
  `ThreeTimelineComposition`; it cannot target other Remotion compositions.
- Effects, transitions, opacity, and audio content (see the support matrix
  above); the hybrid planner routes those to `rendering.remotion` instead.

## Related Documents

- [render-adapter.md](render-adapter.md) — The Remotion adapter install and publishability decision record
- [sdk.md](sdk.md#rendering-sdk) — Public rendering SDK (`render`, `support`)
- [render-backend-v1.md](../contracts/render-backend-v1.md) — Protocol-v1 pluggable renderer contract
- [env-vars.md](env-vars.md) — Canonical `ASTRID_*` reference
- `remotion/src/ThreeTimelineComposition.tsx` — The Three.js composition contract
- `remotion/remotion.config.ts` — ANGLE configuration
- `astrid/packs/rendering/backends/threejs/run.py` — Backend implementation
- `astrid/packs/rendering/planners/threejs_hybrid/run.py` — Hybrid planner implementation
