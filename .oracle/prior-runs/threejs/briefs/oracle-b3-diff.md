# Oracle Batch 3 — verify commit fdf6dfae (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Branch: oracle-run-threejs
Previous checkpoint: 963060ee
Batch 3 commit: fdf6dfae

Do not edit any files. Report verified facts only. Cite commands and file:line.

## Tasks

1. Run `git show fdf6dfae --stat` and `git show fdf6dfae --name-only`. List every path and +/- line counts.

2. Run `git diff --name-only 963060ee..fdf6dfae -- astrid/core/` — must be empty.

3. Run `git diff --name-only 963060ee..fdf6dfae`. Flag any PNG, still, video, fixture, node_modules, chrome cache, remotion/build, remotion/out, generated media, or runtime cache. Allowed production files: astrid/packs/rendering/backends/threejs/{__init__.py,renderer.yaml,run.py}, astrid/packs/rendering/pack.yaml (+1), tests/core/rendering/test_freeze.py (+1), tests/packs/rendering/test_threejs_backend.py (new). .oracle artifacts are allowed.

4. Read astrid/packs/rendering/backends/threejs/run.py in full. Verify:
   - BACKEND_ID == "rendering.threejs"
   - composition_id is a fixed constant ThreeTimelineComposition (never caller-selected)
   - THREE_VERSION == "0.185.1"
   - support() returns backend=BACKEND_ID; support_decision.backend == rendering.threejs
   - fragment key is rendering.threejs; renderer/version threejs/1.0.0; capture_host remotion; composition ThreeTimelineComposition; legacy_v1 retained
   - provenance via _render_provenance_payload(engine="threejs")
   - NO Three surface claims rendering.remotion as its identity (capture_host=remotion is OK)
   - window=None enforced in BOTH support AND render
   - own-namespace config: parse only backend_config["rendering.threejs"]; ignore other namespaces
   - no caller-selected composition IDs
   - eligibility = background-only OR exact 11-field plain-text visual timelines
   - rejections with stable clip-specific reasons for: media/hold/effect/unknown/custom clips, audio tracks or audible clips, effects, transitions, animation declarations, opacity != 1, unsupported text/param fields, passthrough/none ownership, non-None window
   - reuses ONLY these remotion helpers (import or bind): _execute_remotion, _serialize_timeline, _render_provenance_payload, narrow theme/registry helpers
   - does NOT reuse remotion support, _protocol_render, _settings_from_request, remotion backend fragment
   - shared lock via _execute_remotion only (no second lock, no FileLock, no threading.Lock around remotion)
   - _execute_remotion called with composition_id=ThreeTimelineComposition

5. Read astrid/packs/rendering/backends/threejs/renderer.yaml. Frozen contract:
   - features values must be bool or string (NO lists)
   - command pack-root-relative: [python3, backends/threejs/run.py]
   - audio_ownership [rendered]
   - supports_windows false
   - id rendering.threejs, protocol/version 1
   - only support/render operations
   - honest text/visual/MP4/rendered-audio capabilities

6. Read pack.yaml registration (the one-line add) and tests/core/rendering/test_freeze.py +1. Confirm the freeze change is the renderer surface (rendering.threejs in the expected renderer list), not something else.

7. Run `git status --short` and `git ls-files '*.png' '*.mp4' '*.webm' '**/node_modules/**' 'remotion/out/**' 'remotion/build/**'`. Flag committed artifacts in this commit.

## Output (<350 words)

```
VERDICT: PASS | FAIL
FILES: <list with +/- >
ASTRID_CORE: empty | <paths>
ARTIFACTS: none | <paths>
IDENTITY: backend=rendering.threejs, engine=threejs, fragment=rendering.threejs, composition=ThreeTimelineComposition | <gap>
WINDOW: None in support+render | <gap>
NAMESPACE: own rendering.threejs only | <gap>
ELIGIBILITY: bg-only + exact-11 text | <gap>
HELPERS_REUSED: <list>
HELPERS_FORBIDDEN_USED: none | <list with file:line>
SECOND_LOCK: none | <cite>
RENDERER_YAML: ok | <gap>
PACK_FREEZE: renderer surface | <gap>
ISSUES: none | numbered list
```
