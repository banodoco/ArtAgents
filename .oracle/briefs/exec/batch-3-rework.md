# EXECUTOR REWORK BRIEF — BATCH 3 ATTEMPT 1 (A1-A3 compiler projection)

Your first attempt committed 4128b598 with 3 RED golden tests. The frozen original brief is .oracle/briefs/exec/batch-3-deepseek.md — re-read it. The full rework tasklist is .oracle/rework/batch-3-attempt-1.md.

FAILURES (oracle-verified):
1. AttributeError: 'Namespace' object has no attribute 'shots' in 2 CLI tests — --shots was never added to build_parser. Wire it (default OFF; flat stays default).
2. test_golden_parity_counts_and_timing — generation provenance: flat default compiles generation as DICT {generator, prompt} but golden expects STRING. The DEFAULT flat compile must be byte-compatible with the pre-existing golden (76/50/177.53 asserts kept). Fix the compiler (or the canonical shape) so flat output matches the frozen golden; do NOT weaken the golden test.

ACCEPTANCE:
- python3 -m pytest tests/test_compiler_shots.py tests/test_compiler_golden.py tests/test_storyboard_schema.py -q → ALL PASS (keep 22 previous golden passes + your shots suite).
- Scope: only scripts/build_storyboard.py + tests/*. NEVER remotion/*, astrid/packs/*, astrid/core/*, astrid/sdk/*, astrid/packs/rendering/backends/ffmpeg/*.
- Commit: git add -- <exact files> && git commit -m "megado B3 rework: wire --shots flag + flat generation parity (A1-A3)". Never -A/./-am.

Report: what was wrong, full pass counts, commit sha.
