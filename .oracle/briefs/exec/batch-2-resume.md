# EXECUTOR RESUME BRIEF — BATCH 2 (A4): render-prep expansion

Your previous run was killed by a launcher timeout after finishing only PART of the batch. Re-read the original brief `.oracle/briefs/exec/batch-2-deepseek.md` (frozen acceptance, plugin law, North Star, commit rules).

CURRENT STATE (verified by oracle):
- DONE (untracked, not committed): astrid/core/timeline/expand_shots.py (T5 pure function) + tests/core/timeline/test_expand_shots.py
- NOT DONE: T6 (managed render hook in invocation.py:_prepare_managed_render_inputs + managed_timeline.py, expand between resolve and validate), T7 (CLI `timelines show` derived expanded counts in astrid/packs/timeline/cli.py), and the T6 managed-render hook test (tests/packs/rendering/test_managed_timeline_render.py or sibling).
- Cleanup: delete astrid/core/timeline/expand_shots.py.backup (agent artifact).
- Protected: remotion/*, remotion/public/* (never touch). B1's ffmpeg files (astrid/packs/rendering/backends/ffmpeg/*) are B1's — do not touch. scripts/build_storyboard.py is B3's (committed) — do not touch.
- B3's commit 4128b598 may import expand_shots.py in tests — if its import breaks, that's B3's concern; do NOT modify B3's files.

YOUR JOB (finish the batch):
1. Re-read the original brief; verify expand_shots.py matches T5 acceptance (offset/clamp/drop, nested/missing params fail closed, registry union, memory-only).
2. Implement T6 (hook) and T7 (CLI show) exactly per the brief.
3. Add/extend the T6 managed-render hook test.
4. Run: `PYENV_VERSION=3.11.11 python3 -m pytest tests/core/timeline/test_expand_shots.py tests/packs/rendering/test_managed_timeline_render.py -x -q` (+ files you added). Fix failures until green.
5. Confirm `git diff HEAD --stat` shows NO changes to remotion/*, astrid/packs/shots/*, scripts/*.
6. Commit: `git add -- <exact paths>` then `git commit -m "megado B2: render-prep shot expansion (A4)"`. NEVER `git add -A`/`.`/`-am`; never stage .oracle, remotion, or B1/B3 files.

Report: what was added, final test pass counts, commit sha.
