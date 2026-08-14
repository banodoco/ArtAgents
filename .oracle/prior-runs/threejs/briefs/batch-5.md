# Megado Batch 5 — Prove mixed rendering and regressions

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle` (branch `oracle-run-threejs`). Execute ONLY the tasks below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. Do NOT run the full test suite or formatters/linters. The oracle gates the result.

Environment: `PYENV_VERSION=3.11.11`; `PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"` (Node 24) for anything npm/remotion (the mixed render needs node + chrome). Prior checkpoint SHA for this batch: af907878 (`git log --oneline -1` gives the latest). remotion/ has node_modules + Chrome Headless Shell; ANGLE configured; `npx remotion still` and full renders work (verified in batches 1-3).

## Goal

Prove the whole pipeline end-to-end: a MIXED timeline where `rendering.threejs-hybrid` routes text → threejs and media → remotion, finalized by `rendering.ffmpeg-finalizer` into ONE mp4 — plus regressions: ordinary remotion still works under global ANGLE, threejs+remotion serialize through the shared lock, runtime renders work offline.

## Reference — READ THESE FIRST

1. `tests/packs/rendering/test_hyperframes_backend.py::test_hyperframes_remotion_combined_render` (line ~504) — the EXACT model: `_source_video` helper (ffmpeg lavfi color source), `real-assets.json` registry, `render(timeline_path, assets_registry_path, out_path, backend="<planner>", audio="rendered", backend_config, extra_pack_roots=...)`, then ffprobe + sidecar assertions (routing.resolved_policy.planner/finalizer, segments_v2[].renderer.id + window).
2. `tests/packs/rendering/test_threejs_backend.py` — `_missing_environment` skip helper, real-render patterns (ffprobe codec/pix_fmt/frames/duration, non-uniform frame via Pillow or md5 comparison, sidecar fields).
3. `tests/core/rendering/test_threejs_hybrid.py` — planner exact-window tests; add the mixed real render here per the tasklist.
4. `tests/packs/rendering/test_remotion_locking.py` — the shared-lock pattern (remotion_lock.REMOTION_LOCK_PATH monkeypatch, remotion_render_lock_held()).
5. `astrid/sdk/rendering.py` — `render()` signature. For the mixed render use `backend="rendering.threejs-hybrid"`, `audio="rendered"`, `backend_config={"rendering.remotion": {}, "rendering.threejs": {}}` (or just {} — check what the backends require; threejs rejects non-empty backend_config in v1 per the plan, so pass {} or only what's needed).

## Tasks

### T5.1 — Mixed real render (in test_threejs_hybrid.py)
Add one real mixed timeline: a text clip [0, 0.5s) (→ Three) followed by a silent media clip [0.5, 1.0s) (→ Remotion), 320x180@24fps, through `rendering.threejs-hybrid` + `rendering.ffmpeg-finalizer`. Follow the hyperframes combined test's asset setup (ffmpeg lavfi source.mp4 + real-assets.json). Skip ONLY for genuinely missing env (reuse the threejs backend's `_missing_environment` or a combined check); NEVER turn a render failure into a skip.

### T5.2 — Mixed output assertions
ffprobe the final mp4: H.264, yuv420p, AAC, 320x180, fps 24, frame count = 24 (1.0s), duration ~1.0s, deterministic checksum; extract a frame and prove non-uniform content (frame 0 = text visible; or at least one frame has >1 distinct color). Save evidence to `.oracle/findings/mixed-render-proof.txt`.

### T5.3 — Mixed sidecar assertions
Inspect the provenance sidecar: `routing.resolved_policy.planner == "rendering.threejs-hybrid"`, `finalizer == "rendering.ffmpeg-finalizer"`, `segments_v2` = exactly [(rendering.threejs, 0, 12), (rendering.remotion, 12, 24)] (adjust for actual rounding — verify with the planner's output first), each segment's support_decision.backend matches, backend_fragments contains BOTH rendering.threejs and rendering.remotion, audio_ownership rendered, retained engine: threejs in the threejs fragment's legacy_v1.

### T5.4 — Ordinary Remotion regression under ANGLE
A real `rendering.remotion` render (full timeline, no planner) still succeeds and its sidecar says `rendering.remotion` (NOT threejs). Add to test_remotion_backend.py ONLY if no existing real-render test covers ANGLE-on; otherwise add a small focused test in test_threejs_backend.py or test_remotion_backend.py that renders via remotion and asserts identity. (The global remotion.config.ts ANGLE change must not break ordinary remotion.)

### T5.5 — Shared-lock concurrency
A test proving simultaneous threejs + remotion renders serialize through the ONE remotion lock (no second lock). Follow test_remotion_locking.py patterns: monkeypatch the lock path, assert remotion_lock_held() during both, or run two renders concurrently (threads) and assert no registry-tearing (both succeed with correct outputs). Keep it deterministic and fast. Add to tests/packs/rendering/test_threejs_backend.py.

### T5.6 — Offline runtime render
After everything is installed, run one real direct threejs render (and/or the mixed one) with npm offline (`npm config set offline true` locally or `--offline` env) and prove no package download occurs. Evidence: the render succeeds with offline mode; note any error that indicates a network attempt. Restore npm config after.

### T5.7 — Regression suite
`PYENV_VERSION=3.11.11 python -m pytest -q tests/packs/rendering/test_threejs_backend.py tests/core/rendering/test_threejs_hybrid.py tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_finalizer.py`

### T5.8 — Cleanliness
`git diff --name-only af907878..HEAD -- astrid/core/` → empty. `git status --short` clean of videos/PNGs/frames/caches (proof PNGs in /tmp or .oracle/findings text only). Commit `megado: batch 5 — mixed Three/Remotion render + regressions`.

## Acceptance (oracle checks)
- One real mixed render → single mp4 with correct codecs/frames/identity; sidecar shows both renderers + pinned finalizer.
- Ordinary remotion still works under ANGLE (identity intact).
- Shared lock serializes threejs+remotion; no second lock.
- Offline render proves no network.
- All regression tests pass; zero core edits; no artifacts.

## Protocol
Report <400 words: the mixed timeline + windows, ffprobe + sidecar evidence, remotion regression result, concurrency test design, offline proof, test counts, final git status + astrid/core diff. Evidence-first.
