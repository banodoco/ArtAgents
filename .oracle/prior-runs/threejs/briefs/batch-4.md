# Megado Batch 4 — Implement and unit-test the hybrid planner

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle` (branch `oracle-run-threejs`). Execute ONLY the tasks below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. Do NOT run the full test suite or formatters/linters. The oracle gates the result.

Environment: `PYENV_VERSION=3.11.11` for Python/pytest; `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` only if you need node (this batch is pure Python). Prior checkpoint SHA for this batch: fdf6dfae (`git log --oneline -1` gives the latest).

## Goal

Add `rendering.threejs-hybrid` — an opt-in planner that routes plain-text temporal regions to `rendering.threejs` and everything else (media, effects, transitions, audible audio, overlaps, gaps) to `rendering.remotion`, pinning `rendering.ffmpeg-finalizer`. Pure Python. ZERO `astrid/core/` edits.

## Reference — READ THESE FIRST

1. `astrid/packs/rendering/planners/legacy_hybrid/run.py` — the planner you mirror:
   - `_HANDLE_SECONDS = Fraction(1, 4)` (:62), `_ceil` (:90), `_number`, `_timeline_duration`, `_clip_timeline_end` (media: at + (to-from)/speed; text: at + hold).
   - `_complex_frame_windows` (:159) — occupancy with quarter-second handles, transition-aware, floored/ceiled frame windows, gap/tail handling.
   - `_segment_kinds` (:267) — total_frames = ceil(duration*fps); cursor tiling; complex windows → complex segments, gaps → simple; tail extends to total_frames.
   - `support()` (:~440) and `plan()` (:~450) — support reasons + RenderPlan construction: profile via resolve_render_profile, window enforcement (planner receives a full timeline, window=None; if request.window is not None the planner... check), segments with `renderer` (id, source_pack, manifest_digest, alias_chain, override, support_decision, trust_eligibility) + `window` (start_frame, end_frame, fps_rational) + `input_hashes`, finalizer pinned, total_frames, reasons.
   - `_segment_renderer()`-style helper (:538) building the renderer block for a qualified id, resolving real support evidence via the registry (`registry.get(id)`, `registry.resolve_evidence(id)`).
   - `main()` — verb plan|support, --request/--result, `_load_request` (RenderRequest.from_dict(payload).for_backend(BACKEND_ID)), `_write_failure`, write_json_atomic(response.to_dict()).
2. `astrid/packs/rendering/backends/threejs/run.py` — import its PURE eligibility helpers for the Three text contract (the exact 11 fields, no effects/transition/opacity, empty/background OK). Import ONLY pure functions, never the render path.
3. `astrid/packs/rendering/backends/remotion/run.py` — if you need `_load_registry_mapping`/profile helpers, import those; but prefer importing from threejs/run.py or legacy_hybrid/run.py to keep the coupling minimal.
4. `tests/core/rendering/test_legacy_hybrid.py` — the test patterns for planner exact-window assertions (how it builds timelines and asserts segments). Mirror it in test_threejs_hybrid.py.
5. `astrid/packs/rendering/pack.yaml` — register the planner.

## The planner algorithm (frozen in .oracle/plan.md + tasklist)

1. Resolve canonical profile via `resolve_render_profile(timeline, themes_root=...)` incl. requested audio ownership; derive MP4 timescale (integer fps: double numerator until >= 10000; NTSC keep large numerator).
2. `total_frames = ceil(timeline_duration * fps)`; empty timeline → planner SUPPORT REJECTS (cannot tile meaningfully; the DIRECT renderer still accepts empty for smoke).
3. Clip frame ranges: start = round(at * fps), end = round(clip_end * fps) with at least 1 frame for positive duration (media: at + (to-from)/speed; text: at + hold).
4. Merge STRICTLY overlapping intervals into connected components.
5. Component Three-eligible iff EVERY participating clip satisfies the Three text contract (via threejs/run.py eligibility).
6. ANY ineligible participant → the WHOLE component goes to Remotion (never split an overlap; no spatial compositing in v1).
7. Complex/Remotion regions get the legacy quarter-second handle, capped at the next occupied window and total_frames.
8. Gaps → Remotion; last window extends to total_frames.
9. Coalesce adjacent windows with the same renderer when coverage stays exact.
10. Assert exact half-open tiling [0, total_frames): no gaps, no overlaps, no zero-length segments, no recursive planner ids.
11. Resolve REAL renderer support for each segment (registry.get + resolve_evidence); require support_decision.backend == renderer.id; NEVER fabricate.
12. Pin `rendering.ffmpeg-finalizer`.

Eligibility predicate (shared with the backend): clipType text, no effects/transition, opacity in (None, 1), track kind visual, no audio track, and only the 11 text fields. Reuse the backend's function — do not duplicate.

## Tasks

### T4.1 — Manifests
`astrid/packs/rendering/planners/threejs_hybrid/__init__.py` + `planner.yaml`:
```yaml
schema_version: 1
id: rendering.threejs-hybrid
name: Three.js and Remotion Hybrid Planner
version: 1.0.0
protocol_version: 1
command: [python3, planners/threejs_hybrid/run.py]
operations: [support, plan]
capabilities:
  policies: [threejs_remotion]
  supports_fallback: true
  features: {integer_frame_windows: true, conservative_occupancy_tiling: true, explicit_finalizer: true, non_recursive_dispatch: true}
required_permissions: [project_files, subprocess]
```

### T4.2 — [XHARD] `astrid/packs/rendering/planners/threejs_hybrid/run.py`
`BACKEND_ID = "rendering.threejs-hybrid"`, `THREE_ID = "rendering.threejs"`, `REMOTION_ID = "rendering.remotion"`, `FINALIZER_ID = "rendering.ffmpeg-finalizer"`. Implement the algorithm above with pure helpers (profile/timescale, clip frames, occupancy merge, eligibility classification, handle capping, gap/tail, coalescing, tiling assert). `support()` (structural reasons; empty reject) and `plan()` (RenderPlan with exact segments, real support evidence, pinned finalizer). Mirror legacy_hybrid's `main()` + `_load_request` + `_write_failure`.

### T4.3 — Register
Add `- planners/threejs_hybrid/planner.yaml` to `astrid/packs/rendering/pack.yaml` `extensions.rendering.planners`.

### T4.4 — [XHARD] Tests `tests/core/rendering/test_threejs_hybrid.py`
Mirror test_legacy_hybrid.py. Exact-window assertions for:
- Text-only timeline → one Three segment [0, total).
- All-Remotion fallback (media anywhere → whole component Remotion).
- Text → media → text → Three, Remotion, Three.
- Text overlapping media → merged component → Remotion.
- Effects / transitions / non-base visual track / opacity != 1 / audio fades → Remotion.
- Gaps → Remotion; tail extends to total_frames.
- Non-integer clip times → round(seconds*fps) frames.
- Quarter-second handles capped at next occupied region + timeline boundary.
- Adjacent same-renderer coalescing.
- Empty timeline → support REJECTS.
- Exact tiling: no gaps/overlaps/zero-length/recursive planner ids (assert every segment window).
- Support-decision identity: each segment's renderer support_decision.backend matches its renderer id; real support evidence (not fabricated).
- Canonical timescale (fps 24 → [1, 12288]; fps 30 → [1, 15360]).

### T4.5 — Verification
Run:
`PYENV_VERSION=3.11.11 python -m pytest -q tests/core/rendering/test_threejs_hybrid.py tests/packs/rendering/test_threejs_backend.py tests/packs/rendering/test_builtin_registration.py tests/core/rendering/test_freeze.py tests/core/rendering/test_legacy_hybrid.py tests/packs/rendering/test_ffmpeg_finalizer.py`
- `git diff --name-only fdf6dfae..HEAD -- astrid/core/` → empty.
- Commit `megado: batch 4 — rendering.threejs-hybrid planner + tests`.

## Acceptance (oracle checks)
- Planner registered; zero core edits.
- Exact windows for every characterized case (text→Three, everything else→Remotion, overlaps never split, handles capped, gaps/tail correct, coalescing exact).
- Real support evidence per segment; support_decision.backend == renderer.id.
- Pinned ffmpeg-finalizer; exact half-open tiling; empty rejected.
- Tests pass; only proven exact-surface updates.

## Protocol
Report <400 words: files, the classification rules implemented, exact-window test evidence, test counts, final git status + astrid/core diff. Evidence-first.
