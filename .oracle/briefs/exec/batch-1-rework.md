# EXECUTOR REWORK BRIEF — BATCH 1 ATTEMPT 1 (A5 ffmpeg)

Your first attempt committed e3c13deb with a BROKEN tree: tests/packs/rendering/test_ffmpeg_support.py fails COLLECTION with SyntaxError at line 75 (')def _media_timeline(...)'). The frozen original brief is .oracle/briefs/exec/batch-1-deepseek.md — re-read it. The full rework tasklist is .oracle/rework/batch-1-attempt-1.md.

FIX:
1. Make the whole file parse: python3 -c "import ast; ast.parse(open('tests/packs/rendering/test_ffmpeg_support.py').read())" must be clean.
2. python3 -m pytest tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py -q → ALL PASS. T4 live-encode must run within the 120s per-test timeout (shrink fixture if needed; don't delete).
3. Keep scope: only the ffmpeg backend + its tests. NEVER remotion/*, astrid/packs/shots/*, scripts/*, astrid/packs/timeline/cli.py, astrid/sdk/invocation.py, astrid/core/timeline/*.
4. Commit: git add -- <exact files> && git commit -m "megado B1 rework: fix test syntax + green ffmpeg suite (A5)". Never -A/./-am.

Report: what was wrong, full pass counts, commit sha.
