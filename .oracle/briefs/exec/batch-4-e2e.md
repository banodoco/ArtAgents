# B4 EXECUTOR BRIEF — e2e storyboard→shots→ffmpeg render (A6)

You are the normal-pool executor (DeepSeek V4 Flash). B1 (ffmpeg), B2 (expansion), B3 (compiler --shots) are DONE and PASSED. Now prove the end-to-end pipeline per the frozen agent goal.

STATE:
- scripts/build_storyboard.py: has --shots flag (default off, flat emitter default)
- astrid/core/timeline/expand_shots.py: expand_shot_clips (pure, memory-only)
- ffmpeg backend: stills+text+overlay+fade live (no Remotion)
- storyboards/astrid-intro.storyboard.json: the 25-section intro

TASKS:
T13 — Compile with --shots on the intro into a TEMP/SANDBOX project (NEVER the real astrid-intro table):
  ASTRID_PROJECTS_ROOT=<sandbox> python3 scripts/build_storyboard.py compile --story storyboards/astrid-intro.storyboard.json --project astrid-intro --shots --out <sandbox>/compiled
  Verify: 25 shots / 50 items / 25 sub-timelines created; parent timeline has 26 clips (25 shot + 1 brand wordmark); registry 50 assets.
T14 — Save parent to kernel timeline 'main' in the sandbox, then render via ffmpeg:
  astrid timelines save main --project astrid-intro --config <parent>.json --registry <assets>.json
  ASTRID_PROJECTS_ROOT=<sandbox> astrid timelines render main --project astrid-intro --backend rendering.ffmpeg --output-name shot-pipeline.mp4
  Verify exit 0; NO remotion/chrome/webpack in the path; duration ≈177±3s (ffprobe).
T15 — Extract 3 frames (open / idea1_vc / cta_agents section windows) → captions visible (pixel-diff or visual).
T16 — Write .oracle/evidence/final-matrix.md mapping every done criterion (AG1-AG6) → command/path/result; copy the mp4 to .oracle/evidence/shot-pipeline.mp4.

CONSTRAINTS:
- Repository remains the only writer: use ShotsService/TimelinesService via SDK/CLI, never raw SQL.
- Idempotency: run the compile TWICE → same 25 shots / 25 timeline rows, no duplicates on second run.
- Plugin law: no shots→timeline import/FK (already satisfied — verify nothing you add breaks it).
- NEVER modify: remotion/*, astrid/packs/shots/*, astrid/core/*, astrid/sdk/*, astrid/packs/rendering/backends/ffmpeg/*, scripts/build_storyboard.py.
- Sandbox only: ASTRID_PROJECTS_ROOT must point to a temp dir. Do NOT touch the real astrid-intro-projects store.
- DO NOT COMMIT: this is evidence collection. Leave the sandbox + evidence in the working tree; the oracle commits.

Report: exact commands run, counts (shots/items/timelines/clips/assets), ffprobe duration, frame evidence, idempotency result, evidence matrix path.
