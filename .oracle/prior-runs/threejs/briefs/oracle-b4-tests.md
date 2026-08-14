# Oracle Batch 4 — tests + exact-window coverage (research only)

Repo: /Users/peteromalley/Documents/reigh-workspace/Astrid-threejs-oracle
Commit: af907878
Do not edit any files. Report verified facts only. Cite file:line.

## Tasks

1. Read `tests/core/rendering/test_threejs_hybrid.py` in full.

2. List every test function name. Confirm exact-window assertions exist for EVERY characterized case:
   - text-only → one Three segment [0, total)
   - all-Remotion (media / effects / transitions / audible)
   - text → media → text → Three, Remotion, Three
   - text overlapping media → whole component Remotion (never split)
   - effects, transitions, non-base visual track, opacity != 1, audio fades → Remotion
   - gaps → Remotion
   - tail extends to total_frames
   - non-integer clip times → round(seconds*fps)
   - quarter-second handles capped at next occupied + timeline boundary
   - adjacent same-renderer coalescing
   - empty timeline → planner support REJECTS (NOT accept)
   - exact tiling: no gaps/overlaps/zero-length/recursive planner ids
   - support-decision identity: support_decision.backend == renderer.id; real evidence
   - canonical timescales/profile (24 → [1,12288], 30 → [1,15360])
   - pinned rendering.ffmpeg-finalizer
   - minimum positive occupancy (1 frame for positive-duration clips)

3. Confirm the empty-timeline distinction:
   - planner support REJECTS empty
   - direct rendering.threejs renderer still ACCEPTS empty (smoke) — cite test_threejs_backend.py, do not re-run real renders
   - This distinction MUST exist.

4. Confirm test_freeze.py / test_builtin_registration.py only updated planner surfaces that now fail. Read the actual diffs:
   `git show af907878 -- tests/core/rendering/test_freeze.py tests/packs/rendering/test_builtin_registration.py`

5. Run the checkpoint suite (unit tests only; no new real mixed renders — those are Batch 5):
   ```
   PYENV_VERSION=3.11.11 python -m pytest -q \
     tests/core/rendering/test_threejs_hybrid.py \
     tests/packs/rendering/test_threejs_backend.py \
     tests/packs/rendering/test_builtin_registration.py \
     tests/core/rendering/test_freeze.py \
     tests/core/rendering/test_legacy_hybrid.py \
     tests/packs/rendering/test_ffmpeg_finalizer.py
   ```
   Report pass/fail counts. If test_threejs_backend real-render tests would take long, you MAY still run the full six-file suite — host already reported 96 passed. Re-run at least test_threejs_hybrid.py + freeze + builtin + legacy_hybrid + ffmpeg_finalizer. If you skip the backend real-render file, say so.

6. Optionally, if cheap, import `_window_plan` / equivalent and confirm host probes:
   - text-only 24fps 1s → [(0,24,'THREE')]
   - text-media-text → [(0,12,'THREE'),(12,24,'REM'),(24,36,'THREE')]
   - text-overlap-media → [(0,24,'REM')]
   - gap (text 0-0.3s, text 0.8-1.1s) total=27 → [(0,7,'THREE'),(7,19,'REM'),(19,26,'THREE'),(26,27,'REM')]

## Output (<400 words)

```
VERDICT: PASS | FAIL
TESTS: <count> functions: <names>
COVERAGE_GAPS: none | <missing cases with expected windows>
EMPTY_DISTINCTION: planner-rejects + renderer-accepts | <gap>
TILING: asserted | <gap>
SUPPORT_IDENTITY: asserted | <gap>
TIMESCALES: asserted 24/30 | <gap>
FINALIZER: pinned ffmpeg-finalizer asserted | <gap>
FREEZE_REG: planner-surface-only | <gap>
PYTEST: <N passed, N failed, N skipped> command=<...>
WINDOW_PROBES: match-host | <mismatch>
ISSUES: none | numbered list
```
