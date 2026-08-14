# Oracle Batch 4 — algorithm, identity, manifests (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Branch: oracle-run-threejs
Previous checkpoint: fdf6dfae
Batch 4 commit: af907878

Do not edit any files. Report verified facts only. Cite commands and file:line.

## Tasks

1. Run `git show af907878 --stat` and `git diff --name-only fdf6dfae..af907878`. List every path and +/- counts.

2. Run `git diff --name-only fdf6dfae..af907878 -- astrid/core/` — must be empty.

3. Flag any PNG, still, video, fixture, node_modules, chrome cache, remotion/build, remotion/out, generated media, or runtime cache in the commit. Allowed production files: planners/threejs_hybrid/{__init__.py,planner.yaml,run.py}, pack.yaml +1, tests/core/rendering/test_threejs_hybrid.py, tests/core/rendering/test_freeze.py, tests/packs/rendering/test_builtin_registration.py. .oracle artifacts are allowed.

4. Read `astrid/packs/rendering/planners/threejs_hybrid/run.py` in full. Verify the frozen algorithm:
   - BACKEND_ID == "rendering.threejs-hybrid"; THREE_ID == "rendering.threejs"; REMOTION_ID == "rendering.remotion"; FINALIZER_ID == "rendering.ffmpeg-finalizer"
   - canonical profile via resolve_render_profile
   - `_mp4_time_base`: integer fps doubles numerator until >= 10000; NTSC retains large numerator. Compute expected: fps 24 → [1, 12288], fps 30 → [1, 15360]
   - total_frames = ceil(duration * fps)
   - clip frames: start=round(at*fps), end=round(clip_end*fps), min 1 frame for positive duration
   - merge STRICTLY overlapping intervals into connected components
   - component Three-eligible iff EVERY clip is plain text (backend contract)
   - ANY ineligible participant → WHOLE component Remotion (never split)
   - quarter-second Remotion handle capped at next occupied + total_frames/boundary
   - gaps → Remotion; last window extends to total_frames
   - coalesce adjacent same-renderer windows when coverage stays exact
   - assert exact half-open tiling [0, total_frames): no gaps, overlaps, zero-length, recursive planner ids
   - REAL support evidence: registry.get + resolve_evidence; require support_decision.backend == renderer.id; NEVER fabricate
   - pin rendering.ffmpeg-finalizer
   - empty timeline: planner support REJECTS
   - window=None (planner receives full timeline)

5. Eligibility reuse (CRITICAL elegance + correctness):
   - Does run.py IMPORT the three.js backend's pure eligibility helpers, or DUPLICATE them?
   - Cite the import line or the duplicated function(s) with line numbers.
   - Tasklist T4.3: "use the backend’s pure text eligibility helpers". Duplicate = issue.

6. Read `planner.yaml` and `__init__.py`. Frozen:
   - id rendering.threejs-hybrid, protocol/version 1
   - command [python3, planners/threejs_hybrid/run.py]
   - operations [support, plan] only
   - features bool/string only (NO lists)
   - declare integer-frame tiling, conservative fallback, explicit finalizer, non-recursive dispatch

7. Confirm pack.yaml registers `planners/threejs_hybrid/planner.yaml`. Confirm test_freeze.py / test_builtin_registration.py only changed planner surfaces.

8. Run `git status --short` and `git ls-files '*.png' '*.mp4' '*.webm'`. Flag committed artifacts.

## Output (<400 words)

```
VERDICT: PASS | FAIL
FILES: <list with +/- >
ASTRID_CORE: empty | <paths>
ARTIFACTS: none | <paths>
IDENTITY: planner=rendering.threejs-hybrid, three=rendering.threejs, remotion=rendering.remotion, finalizer=rendering.ffmpeg-finalizer | <gap>
TIMESCALES: 24=[1,12288] 30=[1,15360] NTSC=retain | <gap + cite>
TOTAL_FRAMES: ceil(duration*fps) | <gap>
CLIP_FRAMES: round * min1 | <gap>
OCCUPANCY: strictly-overlapping merge | <gap>
ELIGIBILITY: imports backend helpers at <file:line> | DUPLICATES at <file:line>
COMPONENT_RULE: any-ineligible → whole Remotion | <gap>
HANDLES: 1/4s capped next-occupied+boundary | <gap>
GAPS_TAIL: remotion + last→total_frames | <gap>
COALESCE: adjacent same-renderer | <gap>
TILING_ASSERT: exact half-open | <gap>
SUPPORT_EVIDENCE: registry.get + resolve_evidence + backend==id | fabricated | <gap>
EMPTY: planner support rejects | <gap>
PLANNER_YAML: ok | <gap>
PACK_FREEZE: planner surface only | <gap>
ISSUES: none | numbered list
```
