# Explore: runtime callsites — every direct render import

Project root: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only exploration. Do NOT edit files.

## What to establish

Find EVERY place that imports, spawns, or references the concrete render
module `astrid.packs.rendering.executors.render.run` (or its old alias
`render_executor`) and every place that invokes `rendering.render`:

1. `grep -rn "executors.render" --include=*.py astrid tests` and
   `grep -rn "render_executor\|render\.run\|render\.py" --include=*.py astrid/packs tests` —
   list every hit with file:line and one line on what it does.
2. For each:
   - `astrid/packs/video_editing/orchestrators/iteration_video/run.py` —
     how it imports and calls render, and how it renames hype.mp4 → iteration.mp4
     (does the provenance sidecar get renamed? stale `output` field?).
   - `astrid/packs/video_editing/executors/cut/run.py` (around line 367) —
     the alleged `from ..render.run` import of a nonexistent sibling module;
     verify whether it exists and whether it's a real bug.
   - `astrid/packs/video_editing/executors/cut/resume.py` (around 163) — same.
   - `astrid/packs/video_editing/orchestrators/hype/steps.py` — `executor_argv("render.py")`
     direct-module spawning; describe the helper and where it lives.
   - `astrid/packs/editorial/executors/human_notes/run.py` — `_step_argv("render.py")`.
   - `tools/render_and_check.py` — how it invokes rendering.
   - `astrid/packs/video_editing/orchestrators/hype/plan_template.py` — the
     canonical `rendering.render` invocation (already canonical?).
   - Any test that monkeypatches `render_executor.render` or imports the
     module: `grep -rn "render_executor\|rendering.executors.render" tests`.
3. `cut --renderer` flag: where declared (executor.yaml), what values it
   accepts, whether it is passed through to rendering. Quote the code.
4. How `executor_argv()` / `_step_argv()` resolve module → argv, and the
   global caching claim (overrides stale).

## Report format

A complete inventory table: file:line | what it does | canonical or bypass.
Max 400 words plus the table. End with:
- Verified facts
- Unknowns
- Risks for migration (bypasses that would escape the abstraction)
- Suggested approach
