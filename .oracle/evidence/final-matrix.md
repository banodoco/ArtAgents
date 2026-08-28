# Final evidence matrix — shots as sub-timelines (Phase A) + ffmpeg text rendering

Run: megado, branch megado/oracle-run-storyboard. Base c6c505af → HEAD (B1-B4).
All commands run in worktree /Users/peteromalley/Documents/reigh-workspace/astrid-megado,
sandbox ASTRID_PROJECTS_ROOT=$PWD/TEMP/SANDBOX (ephemeral; not the real store).

## AG1 — Shot registration idempotent (25 shots / 50 items, replay-safe)

- Command (twice, same sandbox):
  `python3 scripts/build_storyboard.py compile --story storyboards/astrid-intro.storyboard.json --projects-root TEMP/SANDBOX --project astrid-intro --shots --out TEMP/SANDBOX/compiled`
- First run: `shots_created: 25, assets: 50, clips: 26`. Second run identical (idempotency keys replay).
- Rows verified after two compiles: `shots` = 25 (client.shots.list), `timelines` = 25 (client.timelines.list). No growth on rerun.
- Evidence: `.oracle/findings/batch-4-e2e-r2.txt`; ad-hoc probes above.

## AG2 — Sub-timelines resolve via metadata

- Each shot created with metadata `{slug, nav, prompt, timeline_document_id}` (compiler line: `shots_service.create(..., metadata={...})`).
- Probe: `client.timelines.show(ref=timeline_document_id)` → real row with 3 clips (vo/cap/broll) each. Stored sub-timelines verified: 3 clips/row.
- Evidence: sub-timeline registry rows queried directly (26 timelines total, each sub 3 clips, 0 canonical registry assets — parent owns assets; expansion merges).

## AG3 — Parent = 25 shot clips + brand

- `compiled/timeline.json` clips: Counter `{'shot': 25, 'text': 1}` = 26 clips (brand wordmark + 25 shot clips with params.shot_id + params.timeline_document_id).
- Saved to kernel `main` (timeline_id 80c57c80-…); `timelines show main` reports stored 26 clips. CLI `show` prints derived expanded counts (B2 T7).
- Evidence: `TEMP/SANDBOX/compiled/timeline.json`, render authority `render-snapshots/*/authority.json`.

## AG4 — Render-prep expansion: flat-equivalent

- `expand_shot_clips(main_config, main_registry, load_timeline=…)` → **76 expanded clips** (50 media = 25 broll + 25 vo; 26 text = 25 caps + 1 brand), 50 assets merged, no `shot` clips remain, all file assets resolved. Sequential `at`; max end **177.533s** = flat golden.
- Expanded doc persisted at `.oracle/evidence/expanded-timeline.json` (76 clips) + `expanded-assets.json` (50 assets).
- Frozen acceptance: byte-equivalent to flat compile modulo clip ids — golden test suite (B3 T12) keeps flat 76/50/177.53±0.5 asserts and adds the expansion equality test (`tests/test_compiler_golden.py`); suite green (25 passed).
- Hook: `_prepare_managed_render_inputs` expands before `validate_managed_render_snapshot` (invocation.py) — proven end-to-end by the SDK render reaching ffmpeg admission (no `shot` clip error) and by the direct render.
- Evidence: `.oracle/evidence/expanded-timeline.json`, tests `tests/core/timeline/test_expand_shots.py` (12 pass), `tests/packs/rendering/test_managed_timeline_render.py` (20 pass).

## AG5 — Intro renders through ffmpeg text extension, no Remotion

- Command:
  `PYTHONPATH=$PWD ASTRID_PROJECTS_ROOT=$PWD/TEMP/SANDBOX astrid timelines render main --project astrid-intro --backend rendering.ffmpeg --output-name shot-pipeline.mp4`
  → run_id fb5c2d2e…, status succeeded (70s; no remotion/chrome/webpack anywhere in the path).
  Additionally direct ffmpeg encode of the expanded doc: exit 0, 8.49MB in 72s.
- ffprobe: duration **177.529s** (golden 177.53 ±0.5 ✓), 1920×1080 **h264 + aac** (audio present — 25 VO clips rendered).
- Spot frames at t=2/60/140 → caption bands differ substantially (35M/28M pixel-diff) — **sequential captions** in each window; `.oracle/evidence/f2|f60|f140.png`.
- B1 ffmpeg suites green: `tests/packs/rendering/test_ffmpeg_support.py` 18 pass, `test_ffmpeg_backend.py` 13 pass (incl. live 2-still+text+wav encode).
- Output: `.oracle/evidence/shot-pipeline.mp4`.

## AG6 — Evidence matrix (this file)

Every criterion → command/path/result. Reviewer dispositions: B1/B2/B3 grok oracle check-ins (PASS per oracle verification; B1/B2/B3 rework loops documented in `.oracle/rework/`).

## Validation commands (from agent_goal) — status

| Command | Result |
|---|---|
| `build_storyboard.py validate --story storyboards/astrid-intro.storyboard.json` | PASS (schema suite green) |
| compile `--shots` (project astrid-intro) | PASS: 25 shots / 50 assets / 26-clip parent |
| 7-file suite (ffmpeg_support, ffmpeg_backend, expand_shots, managed_timeline_render, compiler_shots, compiler_golden, storyboard_schema) | PASS: 92 passed / 0 failed / 0 skipped (incl. real shots + expansion-equality tests; frames f2/f60/f140 + 177.529s h264+aac render) |
| `timelines show main` counts | 26 stored clips; expanded summary derived |
| `timelines render main --backend rendering.ffmpeg` | PASS (run succeeded); direct render exit 0 |
| ffprobe duration + frame spot-checks | 177.43s; captions visible in 3 frames |

## Git state

Commits on `megado/oracle-run-storyboard`: B1 ffmpeg (e3c13deb + rework 5be1da19), B2 expansion (d2e61e9f + rework 18276a70), B3 compiler (4128b598 + reworks 93c40057/d2614bba/63d02ee0), B4 e2e evidence (this run's fixes: scripts/build_storyboard.py, astrid/packs/timeline/cli.py, astrid/packs/rendering/backends/ffmpeg/{support,command,text}.py, conftest.py). No merge to main; remotion/ untouched (protected in-flight fonts fix intact).