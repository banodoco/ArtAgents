# Megado Batch 3 — Add the thin Three renderer and direct-render tests

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle` (branch `oracle-run-threejs`). Execute ONLY the tasks below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. Do NOT run the full test suite or formatters/linters. The oracle gates the result.

Environment: `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` (Node 24) for npm/remotion; `PYENV_VERSION=3.11.11` for Python/pytest. Previous batches: 99e6d24c (deps + WebGL proof), 963060ee (ThreeTimelineComposition). Prior checkpoint SHA for this batch: 963060ee (or `git log --oneline -1` for the latest batch-2 commit). remotion/ has node_modules with @remotion/three + three; remotion.config.ts has ANGLE; Chrome Headless Shell populated; `npx remotion still` and full renders work.

## Goal

Add `rendering.threejs` — a thin Python backend that renders Astrid timelines through the `ThreeTimelineComposition` we built, with its OWN identity/provenance (never claims `rendering.remotion`), reusing Remotion's execution helper + shared lock. ZERO `astrid/core/` edits.

## Reference — READ THESE FIRST

1. `astrid/packs/rendering/backends/remotion/run.py` — the backend you're wrapping:
   - `_execute_remotion(timeline_path, assets_path, staged_video, *, provenance_out_path, project_dir, composition_id, theme_path, min_free_gb)` → `_ExecutionDetails` (acquires the shared remotion lock itself).
   - `_render_provenance_payload(out_path, *, engine, timeline_path, assets_path, project_dir, composition_id, theme_path, active_theme, registry_state, stage_summary, ...)` — note `engine` is a parameter.
   - `_serialize_timeline`, `_effective_registry_state`, `_load_registry_mapping`, `_canonical_profile` (from profile.py), `_input_path`, `_duration_frames`.
   - `_settings_from_request` reads ONLY `request.backend_config["rendering.remotion"]` — do NOT reuse it; parse the `rendering.threejs` namespace yourself.
   - `_protocol_render` (lines ~1063-1160) is the shape to mirror: support → settings → timeline/assets paths → empty-assets temp if none → canonical profile → **90kHz timescale fix** (`replace(declared_profile, time_base=(1, 90000))`) → **AAC fields fix** (audio_codec aac, 48000, stereo) → `_execute_remotion` → `os.replace(staged, output)` → provenance (engine param) → VideoArtifact.from_file → RenderResult with backend_fragments.
2. `astrid/packs/rendering/backends/ffmpeg/run.py:59` — precedent: `from ...backends.remotion import run as remotion_backend`, then call its private helpers. Import at module top is side-effect-free.
3. `tests/fixtures/renderer_packs/hyperframes/render.py` — the third-party pack pattern for support/render protocol + result emission (simpler than remotion; good for the eligibility checks).
4. `tests/packs/rendering/test_hyperframes_backend.py` — the test pattern: `_require_hyperframes_environment`-style skip, discovery assertions, honest support, real render + ffprobe + sidecar.
5. `astrid/packs/rendering/pack.yaml` — where you register the renderer.
6. `tests/packs/rendering/test_builtin_registration.py` + `tests/core/rendering/test_freeze.py` — exact-surface tests you may need to extend.

## Tasks

### T3.1 — Manifests
`astrid/packs/rendering/backends/threejs/__init__.py` (empty) and `renderer.yaml`:
```yaml
schema_version: 1
id: rendering.threejs
name: Three.js Timeline Renderer
version: 1.0.0
protocol_version: 1
command: [python3, backends/threejs/run.py]
operations: [support, render]
capabilities:
  clip_types: [text]
  track_types: [visual]
  supports_full_timeline: true
  supports_windows: false
  output_profiles: [video/mp4]
  audio_ownership: [rendered]
  features: {webgl: true, textured_text_planes: true, background_only: true, deterministic_frame_clock: true, capture_host: remotion, media_textures: false, effects: false, transitions: false}
required_permissions: [project_files, subprocess]
required_binaries: [node, npx, ffprobe]
timeout_seconds: 600
```
ALL `features` values bool/string (frozen contract — no lists).

### T3.2 — [XHARD] `astrid/packs/rendering/backends/threejs/run.py`
`BACKEND_ID = "rendering.threejs"`, `BACKEND_VERSION = "1.0.0"`, `THREE_COMPOSITION_ID = "ThreeTimelineComposition"`, `THREE_VERSION = "0.185.1"`.

Pure helpers:
- `_canvas(timeline)` / `_clip_end` / text eligibility: text clips only, no effects/transition/opacity!=1/audio tracks/audible clips, supported text fields = the exact 11 (text.content/fontSize/color/align/bold; params.anchor/offsetX/offsetY/textShadow/maxWidth/weight). Reject media/hold/effect-layer/unknown clip types, unsupported params, audio tracks, effects, transitions, animation, opacity!=1. Stable clip-specific reasons (`clip[<i>] <reason>`).
- Background/empty acceptance: empty timeline OK (smoke).

Own config parse (mirror `_settings_from_request` shape but read `request.backend_config.get("rendering.threejs", {})`; reject unknown keys; support project_dir/theme_path/min_free_gb overrides; reject non-empty backend_config in v1 if the plan says so — the plan says "Reject non-empty backend_config" for render; keep it small).

Protocol entry points `support(request, *, workspace) -> SupportReport` and `_protocol_render(request, *, workspace) -> RenderResult` (or `render`), mirroring remotion's shape:
- Support: validate request schema, window must be None (host-sliced), check node/npx/ffprobe/remotion project/three/R3F presence, return `backend="rendering.threejs"`, `backend_version=BACKEND_VERSION`, bool/string features only.
- Render: re-validate (don't trust support), `request.window` must be None, build props via `_serialize_timeline`, empty-assets temp if no registry, `_canonical_profile`, apply the 90kHz time_base fix + AAC fields fix (Remotion muxes at 90kHz with enforced AAC — same as remotion backend), call `_execute_remotion` with `composition_id=THREE_COMPOSITION_ID`, `os.replace`, provenance with `engine="threejs"`, `VideoArtifact.from_file`, `RenderResult` with:
```json
{"rendering.threejs": {"renderer": "threejs", "renderer_version": "1.0.0", "three_version": "0.185.1", "capture_host": "remotion", "composition": "ThreeTimelineComposition", "legacy_v1": <provenance>}}
```
- `main()` argparse: verb (render|support), `--request`, `--result` (same protocol as hyperframes/remotion backends: read request JSON, write result JSON).

Identity invariants (TEST these):
- Every support `backend` is `rendering.threejs`; `support_decision.backend == renderer.id`; no surface claims `rendering.remotion`.

### T3.3 — [XHARD] Reuse seam
Import only the side-effect-free helpers: `_execute_remotion`, `_render_provenance_payload`, `_serialize_timeline`, `_load_registry_mapping`, `_effective_registry_state`, `_input_path`, `_duration_frames`, `_canonical_profile` (or profile.py's resolve_render_profile). Do NOT reuse remotion's `support`, `_protocol_render`, `_settings_from_request`, or its backend fragment. The shared remotion lock is acquired inside `_execute_remotion` — do not add a second lock.

### T3.4 — Register
Add `- backends/threejs/renderer.yaml` to `astrid/packs/rendering/pack.yaml` `extensions.rendering.renderers`.

### T3.5 — [XHARD] Tests `tests/packs/rendering/test_threejs_backend.py`
Follow `test_hyperframes_backend.py` patterns. Cover:
- Static manifest discovery (registry finds `rendering.threejs`, command `python3 backends/threejs/run.py`, required_binaries).
- Support: empty/background-only OK; exact text fields OK; reject media/hold/effect-layer/unknown clips, effects, transitions, opacity!=1, unsupported params, audio tracks/audible clips, passthrough/none ownership — each with stable clip-specific reasons.
- `window != None` rejected (render + support).
- Protocol failure results valid.
- `support_decision.backend == rendering.threejs`; fragment key `rendering.threejs`; `engine: threejs` in retained v1 payload.
- Own-namespace config: unknown key rejected; other backends' config ignored.
- Environment preflight skip pattern (node>=22? no — remotion needs node>=16/20; check node + npx + ffprobe + remotion project + three/r3f node_modules; skip only when genuinely missing; NEVER turn a render failure into a skip).
- Real render (skip only for missing env): empty timeline → 1-frame valid MP4; text timeline → h264, yuv420p, AAC, correct width/height/fps/duration, non-uniform frame, checksum, sidecar fields (routing.resolved_backend = rendering.threejs, segments_v2[].renderer.id, backend_fragments.rendering.threejs, audio_ownership = rendered, engine threejs).

### T3.6 — Update exact-surface tests ONLY IF they fail
`test_builtin_registration.py` (renderer list) + `test_freeze.py` (exact surfaces). Run them; extend only the specific assertions that fail. Do NOT touch test_generic_code_audit.py, test_package_data.py, CLI tests pre-emptively.

### T3.7 — Verification + commit
- Run: `PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/rendering/test_threejs_backend.py tests/packs/rendering/test_builtin_registration.py tests/core/rendering/test_freeze.py tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py tests/packs/rendering/test_remotion_locking.py`
- `git diff --name-only 963060ee..HEAD -- astrid/core/` → empty.
- Commit `megado: batch 3 — rendering.threejs backend + tests`.

## Acceptance (oracle checks)
- Manifests registered; zero core edits.
- Backend renders a real text timeline through ThreeTimelineComposition with correct identity/provenance (engine threejs).
- Support honest with clip-specific reasons; window=None enforced; own namespace only.
- Reuses _execute_remotion + shared lock; no second lock/capture stack.
- Tests pass; only proven exact-surface updates.

## Protocol
Report <400 words: files created, the support/render flow, test counts, real-render ffprobe + sidecar evidence, final git status + astrid/core diff. Evidence-first.
