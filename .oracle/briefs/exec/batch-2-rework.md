# EXECUTOR REWORK BRIEF — BATCH 2 ATTEMPT 1 (A4 render-prep expansion)

Your first attempt committed d2e61e9f with RED tests. The oracle gate found concrete failures. The full rework tasklist is `.oracle/rework/batch-2-attempt-1.md` — READ IT (it has the exact failures + evidence). The frozen original brief is `.oracle/briefs/exec/batch-2-deepseek.md` (design, plugin law, acceptance).

FAILURES TO FIX (oracle-verified):
1. `tests/core/timeline/test_expand_shots.py::test_nested_shot_raises_error` — DID NOT RAISE. `expand_shot_clips` must fail closed on nested `shot` clips inside a sub-document (raise with "nested shot" message). Fix implementation + make the test use a REAL nested sub-doc.
2. `tests/packs/rendering/test_managed_timeline_render.py` — 11 failures:
   - 9 × `NameError: name 'expand_shot_clips' is not defined` — fix the import/export alignment.
   - 2 × `sqlite3.OperationalError: unable to open database file` — hook opens a NEW connection; FROZEN DESIGN REQUIRES REUSING THE SNAPSHOT RESOLVER'S CONNECTION (no second sqlite3.connect). File-mode renders must NEVER expand / never touch a DB.
3. CLI show (T7): same loader/connection discipline (memory-only; no second connection).

ACCEPTANCE (all must pass):
- `PYENV_VERSION=3.11.11 python3 -m pytest tests/core/timeline/test_expand_shots.py -q` → all pass
- `PYENV_VERSION=3.11.11 python3 -m pytest tests/packs/rendering/test_managed_timeline_render.py -q` → all pass (do not delete unrelated tests)
- Plugin law: no shots import, no FK, no writes to stored doc. Scope: only astrid/core/timeline/expand_shots.py, astrid/sdk/invocation.py, astrid/packs/timeline/cli.py, the two test files. NEVER touch remotion/*, astrid/packs/shots/*, scripts/build_storyboard.py, astrid/packs/rendering/backends/ffmpeg/*.
- Commit: `git add -- <exact files>` + `git commit -m "megado B2 rework: fix expand hook integration + nested fail-closed (A4)"`. Never `-A`/`.`/`-am`.

Report: fix for each failure, full test pass counts for BOTH suites, commit sha.
