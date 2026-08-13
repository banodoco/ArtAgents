# Plan: three.js as a pluggable Astrid timeline renderer

## Outcome

Add two built-in rendering extensions:

- `rendering.threejs`: directly renders background-only and plain-text visual timelines.
- `rendering.threejs-hybrid`: opt-in planner routing eligible text windows to Three, all other windows to `rendering.remotion`, and finalizing through `rendering.ffmpeg-finalizer`.

Three remains hosted inside the existing `remotion/` project:

1. `ThreeTimelineComposition` renders through `@remotion/three`.
2. `<ThreeCanvas>` supplies deterministic frame synchronization and render gating.
3. Remotion’s Chromium path captures and encodes H.264/AAC MP4.
4. A thin Python backend reuses Remotion’s execution helper and lock while owning its renderer identity, support report, provenance, and backend fragment.

No production changes under `astrid/core/`. The transport already executes pack-root-relative command argv verbatim, so registration requires only `pack.yaml` plus the new pack files. Do not add launcher routing, another capture stack, another lock, or another Node project.

## Narrow v1 scope

The direct renderer supports:

- Empty/background-only timelines, clamped to at least one frame for generic renderer smoke.
- Plain `text` clips on visual tracks.
- Canvas width, height, and FPS from `theme_overrides.visual.canvas`, following existing Remotion/profile fallback behavior.
- Timeline duration and clip visibility driven solely by frame and FPS.
- Background color from the already merged theme passed in Remotion props.
- Text fields matching the established mapping exactly:
  - `text.content`
  - `text.fontSize`
  - `text.color`
  - `text.align`
  - `text.bold`
  - `params.anchor`
  - `params.offsetX`
  - `params.offsetY`
  - `params.textShadow`
  - `params.maxWidth`
  - `params.weight`
- Text drawn on an offscreen browser 2D canvas and uploaded as a Three `CanvasTexture`.
- Static textured planes laid out in pixel coordinates through an orthographic camera.
- H.264/yuv420p MP4 with enforced AAC.
- Explicit `audio_ownership: rendered`.

The renderer rejects, with stable clip-specific reasons:

- Media, hold, effect-layer, unknown, or custom clip types.
- Audio tracks and audible clips.
- Effects, transitions, animation declarations, or opacity other than `1`.
- Unsupported text or parameter fields.
- Requests for passthrough or no-audio ownership.
- Arbitrary models, meshes, shaders, post-processing, lights, cameras, fonts, or scene configuration.

Do not add decorative Y rotation, depth drift, or another animation language. Static textured planes are sufficient to prove Three owns the pixels.

## Exact dependencies

Install inside `remotion/` and commit its lockfile:

- `@remotion/three@4.0.455`
- `@react-three/fiber@8.18.0`
- `three@0.185.1`
- `@types/three@0.185.4`

Constraints:

- Never install `@remotion/three@latest`; `4.0.509` does not match Remotion `4.0.455`.
- R3F is a required peer even when raw Three objects are mounted through `<primitive>`.
- Do not use R3F v9; it requires React 19.
- Run `npm install` in `remotion/`; commit `remotion/package-lock.json` at lockfile version 3.
- The current `@types/react@19.2.14` may conflict with React 18/R3F 8. If typechecking exposes that conflict, align `@types/react` and `@types/react-dom` to the React 18 major; do not otherwise churn the type stack.
- CI’s Node 20 is sufficient.
- Three, `@remotion/three`, R3F, and `@types/three` are MIT licensed. Remotion’s existing company-license handling is unchanged.

## Files

### New production files

- `astrid/packs/rendering/backends/threejs/__init__.py`
- `astrid/packs/rendering/backends/threejs/renderer.yaml`
- `astrid/packs/rendering/backends/threejs/run.py`
- `astrid/packs/rendering/planners/threejs_hybrid/__init__.py`
- `astrid/packs/rendering/planners/threejs_hybrid/planner.yaml`
- `astrid/packs/rendering/planners/threejs_hybrid/run.py`
- `remotion/src/ThreeTimelineComposition.tsx`
- `docs/reference/threejs-renderer.md`

Do not create `model.py`. Keep the small timing and eligibility functions in `backends/threejs/run.py`; the planner may import those pure helpers. Existing Python precedent already permits side-effect-free imports between rendering backends.

### Existing production files to modify

- `astrid/packs/rendering/pack.yaml`
- `remotion/src/Root.tsx`
- `remotion/remotion.config.ts`
- `remotion/package.json`
- `remotion/package-lock.json`

Only update broader skill, stage, README, changelog, or adapter documentation if an existing repository convention or failing documentation test proves it necessary.

### Tests

Add:

- `tests/packs/rendering/test_threejs_backend.py`
- `tests/core/rendering/test_threejs_hybrid.py`

Update known exact-surface assertions:

- `tests/core/rendering/test_freeze.py`
- `tests/packs/rendering/test_builtin_registration.py`

Do not edit these pre-emptively:

- `tests/core/rendering/test_generic_code_audit.py`: its scan excludes concrete backend/planner directories, so `threejs` must not be added to its vocabulary.
- `tests/core/rendering/test_package_data.py`
- CLI tests

The existing recursive packaging rules should already include the new Python and YAML files. Change packaging or CLI tests only if verification demonstrates an actual omission.

## Manifests and registration

Register these paths in `astrid/packs/rendering/pack.yaml`:

```yaml
extensions:
  rendering:
    renderers:
      - backends/remotion/renderer.yaml
      - backends/ffmpeg/renderer.yaml
      - backends/threejs/renderer.yaml
    planners:
      - planners/legacy_hybrid/planner.yaml
      - planners/threejs_hybrid/planner.yaml
```

The renderer command must be pack-root-relative:

```yaml
schema_version: 1
id: rendering.threejs
name: Three.js Timeline Renderer
version: 1.0.0
protocol_version: 1
command:
  - python3
  - backends/threejs/run.py
operations:
  - support
  - render
```

The planner follows the same rule:

```yaml
schema_version: 1
id: rendering.threejs-hybrid
name: Three.js and Remotion Hybrid Planner
version: 1.0.0
protocol_version: 1
command:
  - python3
  - planners/threejs_hybrid/run.py
operations:
  - support
  - plan
```

Keep the capability declarations honest:

- Three supports full timelines, not renderer windows.
- The host materializes planner windows and calls the renderer with `window=None`.
- Three advertises only `text` clips, visual tracks, MP4, and rendered audio.
- The planner advertises integer-frame tiling, conservative fallback, an explicit finalizer, and non-recursive dispatch.

## Thin backend implementation

`backends/threejs/run.py` owns:

- `BACKEND_ID = "rendering.threejs"`
- Support and render protocol entry points.
- Direct-timeline eligibility and clip timing helpers.
- Parsing only the `rendering.threejs` configuration namespace.
- Three-specific environment checks.
- Three-specific `RenderResult` construction and failure serialization.

It may reuse these side-effect-free private Remotion helpers:

- `_execute_remotion`
- `_render_provenance_payload`
- `_serialize_timeline`
- Narrow theme/registry helpers required by `_execute_remotion`

It must not reuse:

- Remotion’s `support`
- `_protocol_render`
- `_settings_from_request`
- Remotion’s backend fragment

Those surfaces hardcode `rendering.remotion` or read only its configuration namespace.

The Three backend should:

1. Load and validate the request.
2. Reject a non-`None` renderer window.
3. Validate the exact text-only support boundary.
4. Check Node, npx, ffprobe, the Remotion project, and installed Three/R3F packages.
5. Resolve the canonical render profile using existing profile logic.
6. Invoke `_execute_remotion` with:
   - `composition_id="ThreeTimelineComposition"`
   - the normal Remotion project
   - the existing global Remotion lock
7. Probe the output and return a protocol-valid artifact.
8. Produce its own fragment:

```json
{
  "rendering.threejs": {
    "renderer": "threejs",
    "renderer_version": "1.0.0",
    "three_version": "0.185.1",
    "capture_host": "remotion",
    "composition": "ThreeTimelineComposition",
    "legacy_v1": {}
  }
}
```

The legacy provenance payload must be generated with `engine="threejs"`.

Identity is invariant, not a post-hoc cosmetic rewrite:

- Every Three `SupportReport.backend` is `rendering.threejs`.
- Every renderer resolution has `id="rendering.threejs"`.
- `support_decision.backend == renderer.id`.
- No Three result or fragment claims to be `rendering.remotion`.

Configuration should remain small. Read only the Three namespace and ignore other backend namespaces carried for hybrid rendering. Permit only operational settings already needed in practice, such as project/theme/free-space overrides. Do not expose arbitrary composition selection: the Three renderer always invokes `ThreeTimelineComposition`.

## Three composition

Add this composition to `Root.tsx`:

```tsx
<Composition id="ThreeTimelineComposition" ... />
```

Its metadata calculation must:

- Reuse the existing canvas-selection behavior.
- Use the same timeline duration authority as the current composition.
- Clamp `durationInFrames` to at least `1`.

`ThreeTimelineComposition.tsx` should:

- Accept the same serialized timeline/assets/theme props shape.
- Render through `<ThreeCanvas>`.
- Rely on `ThreeCanvas`’s existing delay-render and per-frame R3F synchronization.
- Use an orthographic camera whose coordinates map directly to output pixels.
- Resolve anchors, offsets, maximum width, alignment, weight, shadow, and color with the established text mapping.
- Create and dispose canvas textures, materials, and geometry normally.
- Use deterministic Z ordering to preserve Astrid’s visual track order.
- Show clips only over their frame interval.
- Render the resolved background even with no clips.
- Avoid `useFrame`, `requestAnimationFrame`, wall-clock time, randomness, network fonts, Drei, and custom render gating.

## WebGL configuration and proof

Set globally in `remotion/remotion.config.ts`:

```ts
Config.setChromiumOpenGlRenderer('angle');
```

Do not attempt raw Chromium flags; Remotion’s `ChromiumOptions` exposes only the supported `gl` selector.

Remotion uses its bundled, project-cached Chrome Headless Shell. Do not depend on system Chrome or Playwright’s cache.

After dependency installation:

1. Inspect `node_modules/@remotion/renderer` for the `unsafe-swiftshader` mapping used by Remotion `4.0.455`.
2. Do not assume main-branch behavior exists in this pinned release until verified.
3. Render a 160×90 frame-zero Three still using ANGLE.
4. Treat WebGL context creation failure as the meaningful environmental failure.
5. Do not add another capture loop or browser implementation if `<ThreeCanvas>` already synchronizes correctly.

## Timeline and duration mapping

Use the existing schema as-is:

- Clip fields include `id`, `at`, `track`, `clipType`, `hold`, `asset`, `from`, `to`, `speed`, `volume`, `opacity`, `params`, `text`, `transition`, and `effects`.
- Media end: `at + (to - from) / speed`.
- Text end: `at + hold`.
- Planner total frames: `ceil(timeline_duration * fps)`.
- Direct empty rendering clamps only composition output to one frame; it does not change canonical non-empty duration semantics.

Do not invent `x`, `y`, `width`, or `height` support for v1 without schema evidence.

## Hybrid planner

The planner is opt-in:

- Direct `rendering.threejs` means the whole materialized timeline must satisfy Three’s support contract.
- `rendering.threejs-hybrid` delegates eligible occupied regions to Three and everything else to Remotion.
- The planner performs temporal concatenation only—never spatial compositing or alpha overlays.

Algorithm:

1. Resolve the canonical profile through `resolve_render_profile`, including the requested audio ownership.
2. Use its FPS and MP4 time base. Integer FPS timescales repeatedly double the FPS numerator until at least `10000`; NTSC-style rates retain their already-large numerator.
3. Calculate `total_frames = ceil(duration * fps)`.
4. For ordinary occupancy, calculate clip starts and ends with `round(seconds * fps)` and ensure a positive-duration clip occupies at least one frame.
5. Merge strictly overlapping occupied intervals into connected components.
6. Mark a component Three-eligible only if every participating clip satisfies the direct Three text contract.
7. Any ineligible participant makes the entire connected component Remotion.
8. Preserve the characterized legacy complex-media predicate for fallback handling:
   - effects
   - transitions
   - non-base visual track
   - opacity other than `1`
   - audio fades
9. Give complex Remotion regions the characterized quarter-second handle, capped at the next occupied window and the timeline boundary.
10. Route uncovered gaps to Remotion.
11. Extend the final window to authoritative `total_frames`.
12. Coalesce adjacent windows only when they use the same renderer and doing so preserves exact coverage.
13. Assert exact half-open tiling with no gaps, overlaps, zero-length segments, or recursive planner IDs.
14. Resolve real renderer support for each segment. Never fabricate a support report, and require its backend to match the resolved renderer ID.
15. Pin `rendering.ffmpeg-finalizer`.
16. Let the finalizer normalize actual segment output to the plan’s canonical profile.

The planner may reject an empty timeline because it cannot construct meaningful nonempty tiling. The direct renderer must still accept the empty generic smoke timeline.

Audio ownership remains explicit throughout:

- Three returns `rendered`.
- Remotion returns `rendered`.
- The finalizer continues to accept `rendered`, `passthrough`, and `none` from arbitrary valid segment renderers.
- This feature need only test Three’s truthful ownership and combined-plan normalization; do not duplicate the finalizer’s existing full ownership matrix.

## Test plan

### Backend unit and protocol tests

Cover:

- Static manifest discovery without importing or executing backend code.
- Empty/background-only support and one-frame smoke.
- Accepted exact text fields.
- Rejection of every unsupported clip and feature class.
- Stable, clip-specific support reasons.
- Own-namespace configuration parsing.
- `window=None` requirement.
- `SupportReport.backend == rendering.threejs`.
- Valid protocol failure results.
- Explicit rendered audio ownership.
- Backend fragment and legacy provenance identity.
- Use of `ThreeTimelineComposition`.
- Reuse of the shared Remotion lock rather than a separate lock.

### Real Three render

Follow the existing environment-preflight pattern:

- Skip for genuinely missing binaries, packages, or unavailable WebGL context.
- Do not convert ordinary render failures into skips.
- Render a tiny text timeline.
- Probe codec, dimensions, FPS, frame count, duration, pixel format, AAC, and checksum.
- Extract a frame and prove it is not uniformly the background color.
- Inspect the published sidecar for:
  - `routing.resolved_backend`
  - `segments_v2[].renderer.id`
  - segment window
  - `backend_fragments.rendering.threejs`
  - `audio_ownership`
  - `engine: threejs` in the retained v1 payload

### Planner tests

Cover exact windows for:

- Text-only.
- All-Remotion fallback.
- Text → media → text.
- Text overlapping media.
- Effects and transitions.
- Non-base complex media.
- Audio fades.
- Gaps and tail coverage.
- Non-integer clip times.
- Quarter-second handles capped at the next occupied region.
- Adjacent equivalent-window coalescing.
- Empty-timeline rejection.
- Exact support-decision identity.
- No gaps, overlaps, zero-length segments, or recursive planner IDs.

Add one combined real render through Three, Remotion, and the FFmpeg finalizer. Assert the full sidecar routing policy, each renderer ID/window, final normalization, and final frame count.

### Regression and packaging

Run:

- Typechecking and bundling for `remotion/`.
- New backend and planner tests.
- Existing Remotion backend tests.
- Existing FFmpeg finalizer tests.
- Renderer concurrency/lock regression tests.
- Exact built-in registration/freeze tests.
- Wheel build and content inspection.
- Complete rendering suite.
- Repository-standard CI.

Verify that:

- The renderer and planner manifests ship in the wheel.
- No production file under `astrid/core/` changed.
- Ordinary Remotion rendering still works under global ANGLE configuration.
- Concurrent Remotion and Three renders remain serialized by the one shared lock.
- Runtime rendering requires no package download.
- `node_modules`, Remotion browser caches, rendered videos, and diagnostic images are not committed.

## Ordered implementation tasklist

1. **Freeze the simplified boundary.**
   - Keep the Remotion-hosted Three architecture, text-only scope, independent identity, hybrid planner, and zero core edits.
   - Remove `model.py`, decorative motion, perspective-camera math, speculative fallbacks, and broad configuration.

2. **Install and validate exact dependencies.**
   - Pin the four exact Three-related packages.
   - Run `npm install` in `remotion/` and commit lockfile v3.
   - Align React type majors only if typechecking demonstrates the mismatch.
   - Run typecheck and bundle checks.

3. **Prove WebGL before adapter work.**
   - Configure ANGLE globally.
   - Inspect the pinned Remotion renderer’s SwiftShader flag mapping.
   - Render one 160×90 Three still and confirm a valid WebGL frame.

4. **Implement the composition.**
   - Add `ThreeTimelineComposition.tsx`.
   - Implement static canvas-texture text, orthographic pixel layout, exact fields, frame visibility, background, ordering, cleanup, and one-frame empty clamp.
   - Register `ThreeTimelineComposition` in `Root.tsx`.

5. **Implement and register the thin renderer.**
   - Add the manifest and pack-root-relative command.
   - Register it in `pack.yaml`.
   - Implement honest support and render shells.
   - Call `_execute_remotion` with the fixed Three composition.
   - Build Three-owned support, result, fragment, and provenance data.

6. **Test the renderer.**
   - Add unit/protocol coverage.
   - Prove empty smoke.
   - Add one real render with ffprobe and full sidecar assertions.

7. **Implement the hybrid planner.**
   - Add its manifest, direct command, and registration.
   - Reuse the small Three eligibility helpers.
   - Implement established duration, occupancy, fallback-handle, gap/tail, profile, support-resolution, and exact-tiling rules.

8. **Test combined planning and rendering.**
   - Add exact-window planner tests.
   - Render one mixed Three/Remotion plan through the FFmpeg finalizer.
   - Verify normalized output and complete routing provenance.

9. **Update only proven exact-surface breakages.**
   - Extend freeze assertions.
   - Extend built-in static registration and planner equality assertions.
   - Leave generic-code audit, CLI, and package-data tests unchanged unless a failure proves otherwise.

10. **Document and verify delivery.**
    - Add one concise renderer reference with install, direct/hybrid usage, exact support matrix, ANGLE requirement, capture-host explanation, and exclusions.
    - Build and inspect the wheel.
    - Run focused suites, existing rendering regressions, and full CI.
    - Confirm no core edits or generated artifacts were committed.

## Explicit non-goals

- Puppeteer or native OpenGL capture.
- Raw-frame piping.
- Another browser, encoder, Node project, or lock.
- Media/video textures.
- GLTF or arbitrary Three scene descriptions.
- Custom shaders, cameras, lights, or post-processing.
- Alpha/layer compositing across renderers.
- User-defined composition IDs.
- A public Three scene or animation DSL.
- Memory benchmarking or speculative future-media investigation.
- Broad Remotion/backend refactoring.

## Definition of done

The work is complete when:

- `rendering.threejs` is statically discoverable as a trusted built-in renderer.
- An empty timeline produces a valid one-frame artifact.
- A plain-text timeline produces a verified Three-rendered MP4 through the shared Remotion/Chromium path.
- Unsupported requests receive honest, stable reasons.
- All support decisions, renderer resolutions, fragments, and provenance consistently identify `rendering.threejs`.
- `rendering.threejs-hybrid` produces exact Three/Remotion windows and pins the FFmpeg finalizer.
- Combined output has the canonical frame count/profile and complete routing provenance.
- Existing Remotion behavior and shared locking remain correct.
- Packaging and full CI pass.
- No production files under `astrid/core/` change.
tokens used
101,685
# Plan: three.js as a pluggable Astrid timeline renderer

## Outcome

Add two built-in rendering extensions:

- `rendering.threejs`: directly renders background-only and plain-text visual timelines.
- `rendering.threejs-hybrid`: opt-in planner routing eligible text windows to Three, all other windows to `rendering.remotion`, and finalizing through `rendering.ffmpeg-finalizer`.

Three remains hosted inside the existing `remotion/` project:

1. `ThreeTimelineComposition` renders through `@remotion/three`.
2. `<ThreeCanvas>` supplies deterministic frame synchronization and render gating.
3. Remotion’s Chromium path captures and encodes H.264/AAC MP4.
4. A thin Python backend reuses Remotion’s execution helper and lock while owning its renderer identity, support report, provenance, and backend fragment.

No production changes under `astrid/core/`. The transport already executes pack-root-relative command argv verbatim, so registration requires only `pack.yaml` plus the new pack files. Do not add launcher routing, another capture stack, another lock, or another Node project.

## Narrow v1 scope

The direct renderer supports:

- Empty/background-only timelines, clamped to at least one frame for generic renderer smoke.
- Plain `text` clips on visual tracks.
- Canvas width, height, and FPS from `theme_overrides.visual.canvas`, following existing Remotion/profile fallback behavior.
- Timeline duration and clip visibility driven solely by frame and FPS.
- Background color from the already merged theme passed in Remotion props.
- Text fields matching the established mapping exactly:
  - `text.content`
  - `text.fontSize`
  - `text.color`
  - `text.align`
  - `text.bold`
  - `params.anchor`
  - `params.offsetX`
  - `params.offsetY`
  - `params.textShadow`
  - `params.maxWidth`
  - `params.weight`
- Text drawn on an offscreen browser 2D canvas and uploaded as a Three `CanvasTexture`.
- Static textured planes laid out in pixel coordinates through an orthographic camera.
- H.264/yuv420p MP4 with enforced AAC.
- Explicit `audio_ownership: rendered`.

The renderer rejects, with stable clip-specific reasons:

- Media, hold, effect-layer, unknown, or custom clip types.
- Audio tracks and audible clips.
- Effects, transitions, animation declarations, or opacity other than `1`.
- Unsupported text or parameter fields.
- Requests for passthrough or no-audio ownership.
- Arbitrary models, meshes, shaders, post-processing, lights, cameras, fonts, or scene configuration.

Do not add decorative Y rotation, depth drift, or another animation language. Static textured planes are sufficient to prove Three owns the pixels.

## Exact dependencies

Install inside `remotion/` and commit its lockfile:

- `@remotion/three@4.0.455`
- `@react-three/fiber@8.18.0`
- `three@0.185.1`
- `@types/three@0.185.4`

Constraints:

- Never install `@remotion/three@latest`; `4.0.509` does not match Remotion `4.0.455`.
- R3F is a required peer even when raw Three objects are mounted through `<primitive>`.
- Do not use R3F v9; it requires React 19.
- Run `npm install` in `remotion/`; commit `remotion/package-lock.json` at lockfile version 3.
- The current `@types/react@19.2.14` may conflict with React 18/R3F 8. If typechecking exposes that conflict, align `@types/react` and `@types/react-dom` to the React 18 major; do not otherwise churn the type stack.
- CI’s Node 20 is sufficient.
- Three, `@remotion/three`, R3F, and `@types/three` are MIT licensed. Remotion’s existing company-license handling is unchanged.

## Files

### New production files

- `astrid/packs/rendering/backends/threejs/__init__.py`
- `astrid/packs/rendering/backends/threejs/renderer.yaml`
- `astrid/packs/rendering/backends/threejs/run.py`
- `astrid/packs/rendering/planners/threejs_hybrid/__init__.py`
- `astrid/packs/rendering/planners/threejs_hybrid/planner.yaml`
- `astrid/packs/rendering/planners/threejs_hybrid/run.py`
- `remotion/src/ThreeTimelineComposition.tsx`
- `docs/reference/threejs-renderer.md`

Do not create `model.py`. Keep the small timing and eligibility functions in `backends/threejs/run.py`; the planner may import those pure helpers. Existing Python precedent already permits side-effect-free imports between rendering backends.

### Existing production files to modify

- `astrid/packs/rendering/pack.yaml`
- `remotion/src/Root.tsx`
- `remotion/remotion.config.ts`
- `remotion/package.json`
- `remotion/package-lock.json`

Only update broader skill, stage, README, changelog, or adapter documentation if an existing repository convention or failing documentation test proves it necessary.

### Tests

Add:

- `tests/packs/rendering/test_threejs_backend.py`
- `tests/core/rendering/test_threejs_hybrid.py`

Update known exact-surface assertions:

- `tests/core/rendering/test_freeze.py`
- `tests/packs/rendering/test_builtin_registration.py`

Do not edit these pre-emptively:

- `tests/core/rendering/test_generic_code_audit.py`: its scan excludes concrete backend/planner directories, so `threejs` must not be added to its vocabulary.
- `tests/core/rendering/test_package_data.py`
- CLI tests

The existing recursive packaging rules should already include the new Python and YAML files. Change packaging or CLI tests only if verification demonstrates an actual omission.

## Manifests and registration

Register these paths in `astrid/packs/rendering/pack.yaml`:

```yaml
extensions:
  rendering:
    renderers:
      - backends/remotion/renderer.yaml
      - backends/ffmpeg/renderer.yaml
      - backends/threejs/renderer.yaml
    planners:
      - planners/legacy_hybrid/planner.yaml
      - planners/threejs_hybrid/planner.yaml
```

The renderer command must be pack-root-relative:

```yaml
schema_version: 1
id: rendering.threejs
name: Three.js Timeline Renderer
version: 1.0.0
protocol_version: 1
command:
  - python3
  - backends/threejs/run.py
operations:
  - support
  - render
```

The planner follows the same rule:

```yaml
schema_version: 1
id: rendering.threejs-hybrid
name: Three.js and Remotion Hybrid Planner
version: 1.0.0
protocol_version: 1
command:
  - python3
  - planners/threejs_hybrid/run.py
operations:
  - support
  - plan
```

Keep the capability declarations honest:

- Three supports full timelines, not renderer windows.
- The host materializes planner windows and calls the renderer with `window=None`.
- Three advertises only `text` clips, visual tracks, MP4, and rendered audio.
- The planner advertises integer-frame tiling, conservative fallback, an explicit finalizer, and non-recursive dispatch.

## Thin backend implementation

`backends/threejs/run.py` owns:

- `BACKEND_ID = "rendering.threejs"`
- Support and render protocol entry points.
- Direct-timeline eligibility and clip timing helpers.
- Parsing only the `rendering.threejs` configuration namespace.
- Three-specific environment checks.
- Three-specific `RenderResult` construction and failure serialization.

It may reuse these side-effect-free private Remotion helpers:

- `_execute_remotion`
- `_render_provenance_payload`
- `_serialize_timeline`
- Narrow theme/registry helpers required by `_execute_remotion`

It must not reuse:

- Remotion’s `support`
- `_protocol_render`
- `_settings_from_request`
- Remotion’s backend fragment

Those surfaces hardcode `rendering.remotion` or read only its configuration namespace.

The Three backend should:

1. Load and validate the request.
2. Reject a non-`None` renderer window.
3. Validate the exact text-only support boundary.
4. Check Node, npx, ffprobe, the Remotion project, and installed Three/R3F packages.
5. Resolve the canonical render profile using existing profile logic.
6. Invoke `_execute_remotion` with:
   - `composition_id="ThreeTimelineComposition"`
   - the normal Remotion project
   - the existing global Remotion lock
7. Probe the output and return a protocol-valid artifact.
8. Produce its own fragment:

```json
{
  "rendering.threejs": {
    "renderer": "threejs",
    "renderer_version": "1.0.0",
    "three_version": "0.185.1",
    "capture_host": "remotion",
    "composition": "ThreeTimelineComposition",
    "legacy_v1": {}
  }
}
```

The legacy provenance payload must be generated with `engine="threejs"`.

Identity is invariant, not a post-hoc cosmetic rewrite:

- Every Three `SupportReport.backend` is `rendering.threejs`.
- Every renderer resolution has `id="rendering.threejs"`.
- `support_decision.backend == renderer.id`.
- No Three result or fragment claims to be `rendering.remotion`.

Configuration should remain small. Read only the Three namespace and ignore other backend namespaces carried for hybrid rendering. Permit only operational settings already needed in practice, such as project/theme/free-space overrides. Do not expose arbitrary composition selection: the Three renderer always invokes `ThreeTimelineComposition`.

## Three composition

Add this composition to `Root.tsx`:

```tsx
<Composition id="ThreeTimelineComposition" ... />
```

Its metadata calculation must:

- Reuse the existing canvas-selection behavior.
- Use the same timeline duration authority as the current composition.
- Clamp `durationInFrames` to at least `1`.

`ThreeTimelineComposition.tsx` should:

- Accept the same serialized timeline/assets/theme props shape.
- Render through `<ThreeCanvas>`.
- Rely on `ThreeCanvas`’s existing delay-render and per-frame R3F synchronization.
- Use an orthographic camera whose coordinates map directly to output pixels.
- Resolve anchors, offsets, maximum width, alignment, weight, shadow, and color with the established text mapping.
- Create and dispose canvas textures, materials, and geometry normally.
- Use deterministic Z ordering to preserve Astrid’s visual track order.
- Show clips only over their frame interval.
- Render the resolved background even with no clips.
- Avoid `useFrame`, `requestAnimationFrame`, wall-clock time, randomness, network fonts, Drei, and custom render gating.

## WebGL configuration and proof

Set globally in `remotion/remotion.config.ts`:

```ts
Config.setChromiumOpenGlRenderer('angle');
```

Do not attempt raw Chromium flags; Remotion’s `ChromiumOptions` exposes only the supported `gl` selector.

Remotion uses its bundled, project-cached Chrome Headless Shell. Do not depend on system Chrome or Playwright’s cache.

After dependency installation:

1. Inspect `node_modules/@remotion/renderer` for the `unsafe-swiftshader` mapping used by Remotion `4.0.455`.
2. Do not assume main-branch behavior exists in this pinned release until verified.
3. Render a 160×90 frame-zero Three still using ANGLE.
4. Treat WebGL context creation failure as the meaningful environmental failure.
5. Do not add another capture loop or browser implementation if `<ThreeCanvas>` already synchronizes correctly.

## Timeline and duration mapping

Use the existing schema as-is:

- Clip fields include `id`, `at`, `track`, `clipType`, `hold`, `asset`, `from`, `to`, `speed`, `volume`, `opacity`, `params`, `text`, `transition`, and `effects`.
- Media end: `at + (to - from) / speed`.
- Text end: `at + hold`.
- Planner total frames: `ceil(timeline_duration * fps)`.
- Direct empty rendering clamps only composition output to one frame; it does not change canonical non-empty duration semantics.

Do not invent `x`, `y`, `width`, or `height` support for v1 without schema evidence.

## Hybrid planner

The planner is opt-in:

- Direct `rendering.threejs` means the whole materialized timeline must satisfy Three’s support contract.
- `rendering.threejs-hybrid` delegates eligible occupied regions to Three and everything else to Remotion.
- The planner performs temporal concatenation only—never spatial compositing or alpha overlays.

Algorithm:

1. Resolve the canonical profile through `resolve_render_profile`, including the requested audio ownership.
2. Use its FPS and MP4 time base. Integer FPS timescales repeatedly double the FPS numerator until at least `10000`; NTSC-style rates retain their already-large numerator.
3. Calculate `total_frames = ceil(duration * fps)`.
4. For ordinary occupancy, calculate clip starts and ends with `round(seconds * fps)` and ensure a positive-duration clip occupies at least one frame.
5. Merge strictly overlapping occupied intervals into connected components.
6. Mark a component Three-eligible only if every participating clip satisfies the direct Three text contract.
7. Any ineligible participant makes the entire connected component Remotion.
8. Preserve the characterized legacy complex-media predicate for fallback handling:
   - effects
   - transitions
   - non-base visual track
   - opacity other than `1`
   - audio fades
9. Give complex Remotion regions the characterized quarter-second handle, capped at the next occupied window and the timeline boundary.
10. Route uncovered gaps to Remotion.
11. Extend the final window to authoritative `total_frames`.
12. Coalesce adjacent windows only when they use the same renderer and doing so preserves exact coverage.
13. Assert exact half-open tiling with no gaps, overlaps, zero-length segments, or recursive planner IDs.
14. Resolve real renderer support for each segment. Never fabricate a support report, and require its backend to match the resolved renderer ID.
15. Pin `rendering.ffmpeg-finalizer`.
16. Let the finalizer normalize actual segment output to the plan’s canonical profile.

The planner may reject an empty timeline because it cannot construct meaningful nonempty tiling. The direct renderer must still accept the empty generic smoke timeline.

Audio ownership remains explicit throughout:

- Three returns `rendered`.
- Remotion returns `rendered`.
- The finalizer continues to accept `rendered`, `passthrough`, and `none` from arbitrary valid segment renderers.
- This feature need only test Three’s truthful ownership and combined-plan normalization; do not duplicate the finalizer’s existing full ownership matrix.

## Test plan

### Backend unit and protocol tests

Cover:

- Static manifest discovery without importing or executing backend code.
- Empty/background-only support and one-frame smoke.
- Accepted exact text fields.
- Rejection of every unsupported clip and feature class.
- Stable, clip-specific support reasons.
- Own-namespace configuration parsing.
- `window=None` requirement.
- `SupportReport.backend == rendering.threejs`.
- Valid protocol failure results.
- Explicit rendered audio ownership.
- Backend fragment and legacy provenance identity.
- Use of `ThreeTimelineComposition`.
- Reuse of the shared Remotion lock rather than a separate lock.

### Real Three render

Follow the existing environment-preflight pattern:

- Skip for genuinely missing binaries, packages, or unavailable WebGL context.
- Do not convert ordinary render failures into skips.
- Render a tiny text timeline.
- Probe codec, dimensions, FPS, frame count, duration, pixel format, AAC, and checksum.
- Extract a frame and prove it is not uniformly the background color.
- Inspect the published sidecar for:
  - `routing.resolved_backend`
  - `segments_v2[].renderer.id`
  - segment window
  - `backend_fragments.rendering.threejs`
  - `audio_ownership`
  - `engine: threejs` in the retained v1 payload

### Planner tests

Cover exact windows for:

- Text-only.
- All-Remotion fallback.
- Text → media → text.
- Text overlapping media.
- Effects and transitions.
- Non-base complex media.
- Audio fades.
- Gaps and tail coverage.
- Non-integer clip times.
- Quarter-second handles capped at the next occupied region.
- Adjacent equivalent-window coalescing.
- Empty-timeline rejection.
- Exact support-decision identity.
- No gaps, overlaps, zero-length segments, or recursive planner IDs.

Add one combined real render through Three, Remotion, and the FFmpeg finalizer. Assert the full sidecar routing policy, each renderer ID/window, final normalization, and final frame count.

### Regression and packaging

Run:

- Typechecking and bundling for `remotion/`.
- New backend and planner tests.
- Existing Remotion backend tests.
- Existing FFmpeg finalizer tests.
- Renderer concurrency/lock regression tests.
- Exact built-in registration/freeze tests.
- Wheel build and content inspection.
- Complete rendering suite.
- Repository-standard CI.

Verify that:

- The renderer and planner manifests ship in the wheel.
- No production file under `astrid/core/` changed.
- Ordinary Remotion rendering still works under global ANGLE configuration.
- Concurrent Remotion and Three renders remain serialized by the one shared lock.
- Runtime rendering requires no package download.
- `node_modules`, Remotion browser caches, rendered videos, and diagnostic images are not committed.

## Ordered implementation tasklist

1. **Freeze the simplified boundary.**
   - Keep the Remotion-hosted Three architecture, text-only scope, independent identity, hybrid planner, and zero core edits.
   - Remove `model.py`, decorative motion, perspective-camera math, speculative fallbacks, and broad configuration.

2. **Install and validate exact dependencies.**
   - Pin the four exact Three-related packages.
   - Run `npm install` in `remotion/` and commit lockfile v3.
   - Align React type majors only if typechecking demonstrates the mismatch.
   - Run typecheck and bundle checks.

3. **Prove WebGL before adapter work.**
   - Configure ANGLE globally.
   - Inspect the pinned Remotion renderer’s SwiftShader flag mapping.
   - Render one 160×90 Three still and confirm a valid WebGL frame.

4. **Implement the composition.**
   - Add `ThreeTimelineComposition.tsx`.
   - Implement static canvas-texture text, orthographic pixel layout, exact fields, frame visibility, background, ordering, cleanup, and one-frame empty clamp.
   - Register `ThreeTimelineComposition` in `Root.tsx`.

5. **Implement and register the thin renderer.**
   - Add the manifest and pack-root-relative command.
   - Register it in `pack.yaml`.
   - Implement honest support and render shells.
   - Call `_execute_remotion` with the fixed Three composition.
   - Build Three-owned support, result, fragment, and provenance data.

6. **Test the renderer.**
   - Add unit/protocol coverage.
   - Prove empty smoke.
   - Add one real render with ffprobe and full sidecar assertions.

7. **Implement the hybrid planner.**
   - Add its manifest, direct command, and registration.
   - Reuse the small Three eligibility helpers.
   - Implement established duration, occupancy, fallback-handle, gap/tail, profile, support-resolution, and exact-tiling rules.

8. **Test combined planning and rendering.**
   - Add exact-window planner tests.
   - Render one mixed Three/Remotion plan through the FFmpeg finalizer.
   - Verify normalized output and complete routing provenance.

9. **Update only proven exact-surface breakages.**
   - Extend freeze assertions.
   - Extend built-in static registration and planner equality assertions.
   - Leave generic-code audit, CLI, and package-data tests unchanged unless a failure proves otherwise.

10. **Document and verify delivery.**
    - Add one concise renderer reference with install, direct/hybrid usage, exact support matrix, ANGLE requirement, capture-host explanation, and exclusions.
    - Build and inspect the wheel.
    - Run focused suites, existing rendering regressions, and full CI.
    - Confirm no core edits or generated artifacts were committed.

## Explicit non-goals

- Puppeteer or native OpenGL capture.
- Raw-frame piping.
- Another browser, encoder, Node project, or lock.
- Media/video textures.
- GLTF or arbitrary Three scene descriptions.
- Custom shaders, cameras, lights, or post-processing.
- Alpha/layer compositing across renderers.
- User-defined composition IDs.
- A public Three scene or animation DSL.
- Memory benchmarking or speculative future-media investigation.
- Broad Remotion/backend refactoring.

## Definition of done

The work is complete when:

- `rendering.threejs` is statically discoverable as a trusted built-in renderer.
- An empty timeline produces a valid one-frame artifact.
- A plain-text timeline produces a verified Three-rendered MP4 through the shared Remotion/Chromium path.
- Unsupported requests receive honest, stable reasons.
- All support decisions, renderer resolutions, fragments, and provenance consistently identify `rendering.threejs`.
- `rendering.threejs-hybrid` produces exact Three/Remotion windows and pins the FFmpeg finalizer.
- Combined output has the canonical frame count/profile and complete routing provenance.
- Existing Remotion behavior and shared locking remain correct.
- Packaging and full CI pass.
- No production files under `astrid/core/` change.