# Rework tasklist — final oracle findings (F1-F3)

Verdict: FAIL (grok 4.6, /tmp/final-review.txt). North Star aligned; product claims incomplete.

## F1 — Expansion drops VO clips (audio silent)
- `expand_shot_clips` uses `sub_hold = clip.get("hold", 0)`; VO clips are `{from,to}` (no hold) → `new_end <= parent_at` drops them. Expanded doc: 51 clips, 0 `vo_*`, no audio track; ffprobe: video-only (no aac). Intro is SILENT.
- Fix: sub-clip duration = `hold` OR `to-from` (whichever the clip carries); KEEP audio clips in expansion (offset at, preserve from/to); do not zero/drop audio. Re-render; ffprobe must show h264+aac; duration 177±3s.
- Files: astrid/core/timeline/expand_shots.py + tests/core/timeline/test_expand_shots.py.

## F2 — Parent shot graph not a 177s composition (all at=0, shared 15.051 hold)
- Compiler sets every shot clip `at=0, hold=15.051`; expansion offsets sub-clips by parent.at=0 → all captions fire in first ~15s; ffmpeg concat makes 177s only by input order.
- Fix: place each shot clip at the SECTION START (accumulated offset from prior sections' durations) with per-section `hold` (= section duration + GAP). Expansion then emits sequential `at` matching the flat compile. Captions render in their own windows.
- Files: scripts/build_storyboard.py (parent-graph loop: compute section offsets), tests/test_compiler_shots.py (assert sequential at).

## F3 — AG4 expansion-golden + shots tests are skips; 51 ≠ 76
- `tests/test_compiler_shots.py` = `pytest.skip("Parent emitter (--shots) not yet implemented")` (the 1 skipped). `tests/test_compiler_golden.py` has NO expand test; still asserts flat 76.
- Fix: implement REAL `tests/test_compiler_shots.py` (temp-project: compile --shots → 25 shots/50 items/25 timelines; parent 26 clips with sequential at; expand == flat 76 modulo clip ids). Unskip. Keep golden 76 asserts; add the expansion-equality test.
- Evidence: `.oracle/findings/batch-4-e2e-r2.txt` cited lock-failure — update matrix pointers to the REAL final runs (direct render 177.43s + run_id fb5c2d2e).

## Acceptance (re-gate)
1. `python3 -m pytest tests/core/timeline/test_expand_shots.py tests/packs/rendering/test_managed_timeline_render.py -q` → all pass; expansion KEEPS vo clips (audio), offsets sequential.
2. `python3 -m pytest tests/test_compiler_shots.py tests/test_compiler_golden.py tests/test_storyboard_schema.py -q` → all pass, NO skips; expansion-equality test proves expand(parent) == flat 76 modulo clip ids.
3. Re-render expanded doc (direct ffmpeg + SDK render): ffprobe shows **h264+aac**, duration 177±3s; captions visible at t=2/60/140 with SEQUENTIAL text (different captions, not just slide brightness).
4. Update `.oracle/evidence/final-matrix.md` pointers + new audio-bearing render into evidence.
5. Fresh independent review (grok) against FULL criteria.

Scope: only expand_shots.py, scripts/build_storyboard.py (parent graph), the two test files, evidence. Never remotion/*, astrid/packs/shots/*, ffmpeg backend (B1 green), astrid/packs/timeline/cli.py (green).