# Oracle Batch 5 — test assertions (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: 8723ca05 (vs previous checkpoint af907878)
Do not edit any files. Report verified facts only. Cite file:line.

## Tasks

1. `git show 8723ca05 --stat` and list every path + +/-.

2. Read the NEW/CHANGED test functions in:
   - `tests/core/rendering/test_threejs_hybrid.py` (mixed real render)
   - `tests/packs/rendering/test_remotion_backend.py` (ANGLE remotion identity)
   - `tests/packs/rendering/test_threejs_backend.py` (lock + offline)

3. T5.1 mixed timeline — is it genuinely mixed?
   - Must have a real text clip AND a real media clip (not two text clips).
   - Media must be an actual media asset (ffmpeg lavfi / silent mp4 / registry), not a mock clip type.
   - Render must go through public service with planner `rendering.threejs-hybrid` and finalizer `rendering.ffmpeg-finalizer`.
   - Skip only for genuinely missing env (node/npx/ffprobe/webgl/packages), NEVER ordinary render failure.

4. T5.2 ffprobe — do assertions genuinely prove:
   - h264 codec
   - yuv420p (or 420 family — cite exact assertion; `"420p" in pix_fmt` is OK)
   - AAC audio
   - dimensions 320x180
   - fps / time_base
   - authoritative frame count (nb_read_frames or equivalent, not just duration*fps)
   - duration
   - deterministic checksum (two renders or sidecar hash vs file)
   - non-uniform content (frame A md5 != frame B md5, text vs media)
   Flag any assertion that can pass vacuously (e.g. `assert segments` with no exact windows; `in` on empty; skipped if probe fails).

5. T5.3 sidecar — confirm EXACT assertions for:
   - planner == rendering.threejs-hybrid
   - finalizer == rendering.ffmpeg-finalizer
   - segments_v2 exact windows AND renderer ids (must be exact tuples, not just "len==2")
   - support_decision.backend == renderer.id on BOTH segments
   - fragments contain threejs, remotion, ffmpeg-finalizer
   - threejs legacy_v1.engine == threejs
   - audio_ownership rendered
   Flag if any of these is missing or only loosely checked.

6. T5.4 remotion regression:
   - Does it ACTUALLY call the public render path with backend rendering.remotion (not mock, not threejs)?
   - Does it prove identity is remotion (engine, fragment, threejs ABSENT)?
   - Is it a real render (ffprobe) under global ANGLE, not a still or monkeypatched execute?

7. T5.5 lock test:
   - Is `threejs._execute_remotion is remotion_backend._execute_remotion` asserted?
   - Multiprocess spawn with a REAL lock hold (not just importing FileLock)?
   - Concurrent remotion actually BLOCKS until threejs releases?
   - Exactly ONE *.lock file?
   - Deterministic (no sleep-and-hope without assertion)?
   Flag if it is a fake (e.g. both run sequentially in one process, or lock path never acquired).

8. T5.6 offline:
   - Does it set `npm config set offline true` (or equivalent) around a REAL threejs render?
   - Restored afterwards?
   - Is success-under-offline a meaningful "no fetch" proof, or does the test never invoke npm/npx?

9. List every pytest.skip / skipif in the new functions. FAIL if ordinary render failure becomes skip.

10. Do NOT re-run the mixed real render (host already ran 98 passed / 2 skipped). You MAY run collection only:
    `PYENV_VERSION=3.11.11 python -m pytest --collect-only -q tests/core/rendering/test_threejs_hybrid.py tests/packs/rendering/test_threejs_backend.py tests/packs/rendering/test_remotion_backend.py`
    if cheap. Do not spend more than 30s on pytest.

## Output (<400 words)

```
VERDICT: PASS | FAIL
FILES: <paths +/->
MIXED_TIMELINE: genuine-text+media | fake
PLANNER_FINALIZER: hybrid+ffmpeg-finalizer | <gap>
FFPROBE: h264 yuv420-family AAC 320x180 frames=24 duration checksum nonuniform | <gap>
SIDECAR: exact-windows+ids+support+fragments+engine+ownership | <gap>
VACUOUS: none | <which assertions>
REMOTION_REG: real-render remotion-identity threejs-absent | <gap>
LOCK: identity+real-hold+blocks+one-file | <gap>
OFFLINE: npm-offline+real-render+restored | <gap>
SKIPS: <each with condition>
SKIP_POLICY: honest | converts-failure-to-skip
ISSUES: none | numbered list of checkpoint-failing problems only
```
