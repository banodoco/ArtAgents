# Megado Batch 6 — Documentation, packaging, and full delivery gate

You are the EXECUTOR (DeepSeek V4 Flash). Work in `/Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle` (branch `oracle-run-threejs`). Execute ONLY the tasks below. Do NOT broaden scope. Do NOT edit anything under `astrid/core/`. The oracle gates the result.

Environment: `PYENV_VERSION=3.11.11` for Python/pytest/make; Node 20 on normal PATH for the CI-parity npm pass (match CI — do NOT use nvm v24 here unless a gate requires it; CI pins node 20). Prior checkpoint SHA for this batch: 8723ca05.

## Goal

Finish the epic: document `rendering.threejs` + `rendering.threejs-hybrid`, prove packaging (wheel contains the new manifests/packages), run the FULL repository CI gate, apply the two small oracle notes from checkpoints 3 and 5, and leave zero core edits + a clean diff.

## Oracle notes to fold in (small, explicit)

1. **Checkpoint 3 note** — dead code in `astrid/packs/rendering/backends/threejs/run.py`: the oracle flagged an unused `_effective_registry_state` binding (~35 lines: a bound helper never called) and a dead `_clip_end`. Remove ONLY confirmed-dead code (unused bindings/functions that nothing imports). Verify by grep that nothing references them (including tests).
2. **Checkpoint 5 note** — `test_threejs_hybrid.py::test_threejs_hybrid_mixed_real_render` does not assert the finalizer fragment in the sidecar. Add: `payload["backend_fragments"]["rendering.ffmpeg-finalizer"]` exists (check its actual shape first — it may be a renderer fragment or a top-level finalizer key; assert what the service actually emits for the pinned finalizer). Also: the offline test mutates global `npm config` — leave it but ensure it restores in `finally` (verify it does).

## Tasks

### T6.1 — Docs
Add `docs/reference/threejs-renderer.md` documenting:
- What it is: `rendering.threejs` renders background/plain-text Astrid timelines as three.js WebGL scenes captured through the existing Remotion project (`@remotion/three`, `<ThreeCanvas>`, ANGLE, shared remotion lock, H.264/AAC MP4, `audio_ownership: rendered`).
- Installation: the four exact npm deps in remotion/ (@remotion/three@4.0.455, @react-three/fiber@8.18.0, three@0.185.1, @types/three@0.185.4) + lockfile; Chrome Headless Shell; ANGLE.
- Direct use: `render(..., backend="rendering.threejs")` + the exact accepted/rejected support matrix (text fields, empty/background OK; rejects media/audio/effects/transitions/opacity/unknown params/passthrough-none ownership/non-empty backend_config in v1).
- Hybrid: `render(..., backend="rendering.threejs-hybrid")` — text regions → threejs, everything else → remotion, pinned `rendering.ffmpeg-finalizer`; temporal concat only, no spatial compositing.
- Provenance identity: engine threejs, fragment rendering.threejs, capture_host remotion.
- Explicit v1 exclusions: media textures, GLTF/custom meshes/shaders/lights/cameras/fonts, scene/animation DSL, alpha compositing, arbitrary composition IDs.
- Follow the existing docs style (see docs/reference/render-adapter.md, sdk.md).

### T6.2 — Docs/convention gates
Do NOT modify broader skills, STAGE.md, README, changelog, generic-code audit, package-data tests, or CLI tests UNLESS a failing repository convention proves an exact omission. If a gate fails due to the new backend, make the SMALLEST assertion/documentation correction and retain the failure evidence for the oracle.

### T6.3 — Node 20 CI-parity
With Node 20 on normal PATH (NOT nvm v24), from remotion/: `npm ci` (installs from the committed lockfile — must succeed without mutation), `npm run typecheck`, `npm run bundle` — all exit 0. Record the node version.

### T6.4 — Rendering suites
`PYENV_VERSION=3.11.11 python -m pytest -q tests/core/rendering tests/packs/rendering` — resolve ONLY regressions caused by this feature (the pre-existing env-dependent skips are fine; do not chase pre-existing failures unrelated to threejs — note them with evidence).

### T6.5 — Wheel
`PYENV_VERSION=3.11.11 make wheel PY=python` (runs scripts/smoke_wheel_install.sh). Confirm the wheel contains `backends/threejs/{__init__.py,run.py,renderer.yaml}` and `planners/threejs_hybrid/{__init__.py,run.py,planner.yaml}` (inspect the wheel contents — unzip -l or the script's output). Save the wheel manifest evidence to `.oracle/findings/wheel-manifest.txt`.

### T6.6 — Full CI gate
`PYENV_VERSION=3.11.11 make ci PY=python` — the full mirror (check: structure/doctor/ruff/mypy/cycles/remotion-typecheck/renderer-parity; editable; wheel; ci-mirror pytest+coverage). It must pass. If a gate fails due to the new backend, fix the SMALLEST thing and re-run that gate (then full ci). Preserve evidence of any fix.

### T6.7 — Zero core edits + clean diff
`git diff --name-only 8723ca05..HEAD -- astrid/core/` AND `git diff --name-only <run-base b1c5f53c>..HEAD -- astrid/core/` both print NOTHING. `git status --short` has no node_modules/browser cache/bundle/dist/video/PNG/extracted-frame/diagnostic artifacts (build/ and node_modules/ must stay gitignored — verify).

### T6.8 — Final commit
Commit `megado: batch 6 — docs, packaging, full CI gate`.

## Acceptance (oracle checks)
- threejs-renderer.md documents the exact matrix + exclusions; style matches.
- npm ci + typecheck + bundle pass on Node 20 from the committed lockfile.
- tests/core/rendering + tests/packs/rendering pass (only pre-existing skips/failures with evidence).
- Wheel contains both manifests + packages (evidence).
- make ci passes end-to-end.
- Dead code removed (checkpoint-3 note); finalizer fragment asserted in mixed test (checkpoint-5 note); offline test restores npm config.
- ZERO astrid/core changes across the entire epic; clean diff.

## Protocol
Report <500 words: docs added, Node-20 gate results, suite counts, wheel manifest evidence, make ci result, the two oracle-note fixes, final git status + both astrid/core diffs. Evidence-first.
