# EXECUTOR BRIEF E2 — storyboard→timeline compiler + golden parity test

Worktree: /Users/peteromalley/Documents/reigh-workspace/Astrid-megado (branch megado/oracle-run-storyboard). Build on E1 (loader exists at astrid/core/storyboard/loader.py with load_storyboard/validate_storyboard).

## Deliverables
1. `scripts/build_storyboard.py` CLI:
   - `compile --story <path> [--vo-align <plan.json>]` → writes `build/timeline/{timeline.json,assets.json}` sidecars + `resolution_report` dict dumped to stdout
   - `--render [name]` thin passthrough to SDK invoke timelines render
   - flags use argparse; story path may be relative; output dir default `<story dir>/../timeline`
2. Compiler core semantics:
   - Read sections in order. For each section:
     - ACTIVE image variant (index) → import managed: from astrid.sdk.media MediaService.import_file(path, project=…) OR fallback direct file reference if import fails? NO — always import via sdk (projects root from env ASTRID_PROJECTS_ROOT)
     - VO audio wav → same import path → registry entry {file:CAS, content_sha256, origin:{prompt,generator}}
     - Emit EXACTLY 3 clips per section onto 4 tracks matching this structure (broll/captions/a1/brand):
       a) broll media clip using image asset key f"img_{slug}", hold=dur+GAP(0.35), at=vo start time from plan (--vo-align) else cumulative hold times
       b) caption text clip VERBATIM vo text, fontSize 30, weight 500, anchor bottom-center offsetY 56, maxWidth 1500, fades 0.2/0.2
       c) a1 audio media clip asset f"vo_{slug}" from:0 to:dur at=start
   - Brand wordmark clip inserted once at head: ASTRID top-right hold total
   - registry assets entries for each referenced import incl content_sha256 returned by sdk
3. Golden parity test `tests/test_compiler_golden.py`:
   - Uses the committed intro storyboard fixture (build/fixtures/storyboard-intro.json if present, else tests/fixtures/storyboard-minimal.json duplicated to 25 sections programmatically)
   - Asserts counts: 25 image imports, 25 audio imports (50 assets), 76 clips (25×3+1 brand), total duration ≥177s ±0.5 tolerance vs plan sum if plan available; runs compile WITHOUT actually invoking kernel sdk by monkeypatching import path with temp files (no paid/network)
4. Commit everything to branch megado/oracle-run-storyboard.

## Constraints
- Do NOT touch kernel DB directly in unit test (monkeypatch)
- Reuse astrid.core.storyboard.loader.load_storyboard
- Manage resolution_report mapping slug→{variants resolved} persisted ONLY to stdout/build artifacts — never into storyboard json

## Acceptance
`PYENV_VERSION=3.11.11 pytest tests/test_compiler_golden.py -q` green; running CLI `python scripts/build_storyboard.py compile --story <fixture> --out ./out` produces build/timeline files.
