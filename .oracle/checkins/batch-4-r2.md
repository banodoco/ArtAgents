Reading additional input from stdin...
2026-08-12T15:25:05.594031Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:25:05.594070Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:25:05.594075Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ff693-bda9-75d3-a450-e539731e6833
--------
user
# Megado Checkpoint — Batch 4 second re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
Prior verdict batch-4-r1.md listed 4 issues (2 HIGH, 2 MEDIUM). All host-fixed.
Rework committed as `907423f2` (prior head 98f4edea). Incremental diff:
`git diff 98f4edea..907423f2`.

## How each issue was addressed

1. **HIGH — finalizer alias/override lineage discarded in `_finish_plan`** →
   `_finish_plan` now merges the plan's existing finalizer
   `alias_chain`/`override` into the rebuilt resolution (keeping the 
   service's authoritative support decision) instead of rebuilding from
   canonical evidence alone.
2. **HIGH — `RenderService(finalizer_id=...)` pins an executable finalizer
   but the direct branch never invokes it** → the direct-render branch now
   defers audio completion when the plan pins a real finalizer and routes
   through `_finish_plan` (resolving the pinned finalizer and running it)
   exactly like planner-produced plans; the direct-marker path still
   validates directly.
3. **MEDIUM — `--engine remotion --backend ffmpeg` conflict not detected** →
   `--engine` argparse default changed from `"remotion"` to `None`; explicit
   presence is tracked, so supplying BOTH raises a conflict error, and an
   absent engine still resolves to the `remotion` default. Two new facade
   tests: conflict rejected; default resolves to remotion.
4. **MEDIUM — real-service audio-reactive coverage absent** → added
   `test_real_ffmpeg_audio_reactive_through_generic_service`: a real
   two-clip audio-reactive timeline (effect clip + real AAC source) rendered
   through the real service and strict FFmpeg backend; asserts one video +
   one sidecar with `audio_ownership == rendered`.

## Evidence

- `pytest -q tests/core/rendering/ tests/packs/rendering/test_render_facade.py
  tests/packs/rendering/test_legacy_renderer_characterization.py
  tests/packs/rendering/test_render_remotion_registry.py` → 420 passed,
  1 failed (pre-existing model-trends env fixture).
- Real-backend coverage now: nominal FFmpeg, with-audio whole-media FFmpeg,
  audio-reactive FFmpeg, and hybrid (all through the real service +
  CommandTransport).

## Verdict

Binary `PASS` or issues. On PASS, Batch 5 (caller migration + semantic
parity + M1 freeze) begins. Say exactly `PASS` if clean.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` skill because this is an explicit Megado checkpoint re-review. I’ll inspect the skill instructions, the incremental diff, and the affected tests, then return exactly `PASS` if no material issue remains.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, high reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where a GPT-5.6 Sol oracle reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

A delivery pipeline for a whole project: **Codex plans, DeepSeek explores, Codex revises, DeepSeek executes, Codex oracles** — all in a worktree, opened and synced when done. Two models only: **DeepSeek V4 Flash** and **GPT-5.6 Sol**.

The shape (from the original ask, normalized):

1. In a worktree, Codex (GPT-5.6 Sol, high reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at high reasoning produces this structure.
5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
6. Open it and sync.

## Roles

| Role | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Planner / Oracle** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | read-only for planning/review; `workspace-write` when it implements |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Hard-task executor** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | `workspace-write` |

The whole pipeline runs on exactly two models: **DeepSeek V4 Flash** (cheap, fast, coding-tuned — exploration and normal execution) and **GPT-5.6 Sol** (the frontier planner/oracle — planning, revision, hard tasks, checkpoint review). Escalate exploration to DeepSeek V4 Pro only on evidence that Flash's findings are thin.

One orchestrator (the host agent) drives all phases and holds the artifacts; each subagent gets a self-contained brief and returns only its conclusion.

## Artifacts (in the worktree)

```
.oracle/
  plan.md            # living plan: v1 from Codex, revised each loop
  briefs/            # one brief per explorer / executor batch
  findings/          # explorer outputs: <area>.txt (+ .meta.json from fan.py)
  tasklist.md        # frozen batched task list with checkpoints + [HARD] tags
  checkins/          # oracle verdicts: batch-<N>.md
  status.md          # current phase, batch, checkpoint state
```

## Phase 0 — Worktree

Run the whole pipeline on a branch, never on main.

```bash
git worktree add ../<project>-oracle -b oracle-run
cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins
```

## Phase 1 — Initial plan (Codex)

Brief GPT-5.6 Sol at high reasoning. Demand three outputs, in order:

1. A tasklist covering the **entirety** of the project (not just the obvious path).
2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
3. Open questions / potential issues.

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/plan-brief.md)" </dev/null > /tmp/plan-v1.txt 2>&1
```

The brief is a spec, not a memo: project path, goal, constraints, "list every area you'd explore for full clarity — don't stop at what's obvious." Save the result as `.oracle/plan.md` (host writes it; Codex stays read-only).

## Phase 2 — Deep exploration (DeepSeek fan-out)

One DeepSeek V4 Flash agent per area, in parallel. `fan.py` for ≥ ~5 areas; `launch_hermes_agent.py` per area below that.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
```

Each brief: "Explore area X in depth. Report verified facts with file/line evidence, unknowns, risks, and a suggested approach. Ranked findings, <300 words." Exploration answers the *plan's* questions — mechanical briefs, no license to architect.

## Phase 3 — Revise-until-stable loop

Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Codex (GPT-5.6 Sol, high reasoning):

> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

- New material areas → re-run Phase 2 for those, then revise again.
- Repeat until Codex returns `STABLE` (or two consecutive rounds with no material change).
- The plan is a living doc during this loop; it freezes at Phase 4.

## Phase 4 — Batched tasklist with checkpoints (Codex)

Ask Codex (GPT-5.6 Sol, high reasoning) to convert the stable plan into an execution structure:

- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
- **Per-batch acceptance criteria** the oracle will verify.

Emit as markdown (or JSON if the host will script it) into `.oracle/tasklist.md`. This file is **frozen** — execution follows it; plan revisions during execution go through the oracle, not silent edits.

## Phase 5 — Execute, with oracle checkpoints

Per batch, in order:

**1. Execute the batch.** DeepSeek Flash takes every non-`[HARD]` task — one agent per batch, terminal toolset so it can run code and tests:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
```

`[HARD]` tasks go to GPT-5.6 Sol instead:

```bash
timeout 1800 codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/hard-task-brief.md)" </dev/null
```

(Use `--sandbox danger-full-access` only when the Codex agent must itself orchestrate hermes subagents — those need outbound network.)

**2. Checkpoint — oracle review.** Send the batch's completed work to GPT-5.6 Sol (high reasoning):

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/checkin-brief.md)" </dev/null > .oracle/checkins/batch-<N>.md 2>&1
```

The check-in brief carries: the batch's tasks + acceptance criteria from `tasklist.md`, and the diff since the last checkpoint (`git diff <last-checkpoint-sha>..HEAD` — commit after each batch so the oracle sees a clean delta). Verdict is binary: `PASS` or a list of issues.

**3. Rework loop.** On issues, send them back to the executor (Flash for normal, GPT-5.6 Sol for HARD), re-run, re-review — until the oracle passes. **Do not start batch N+1 until batch N passes.**

## Phase 6 — Completion

1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
3. `open` the worktree / project for the user, and report phase-by-phase evidence.

## Gotchas

- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
- **Match brief shape to model mode.** Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs derived straight from the tasklist. Judgement (exploration, revision, oracle) stays at GPT-5.6 Sol; escalate Flash exploration to DeepSeek V4 Pro only on evidence.
- **Liveness ≠ correctness.** Watch `fan.py` `.meta.json` files and the stderr `[tool]`/`[done]` heartbeat; check 30–60 s after launch, not 10 minutes in. But a live agent can still answer uselessly — read the response.
- **Checkpoint discipline is the whole game.** The oracle gate is what makes quality; skipping it to "save a cycle" collapses this into a plain DeepSeek run.
- **Elegance bias is a real instruction.** Codex's revision prompt must name it; otherwise reasoning models add scope, not subtract it.

## Quick reference

```bash
# Phase 0
git worktree add ../<project>-oracle -b oracle-run && cd ../<project>-oracle
mkdir -p .oracle/briefs .oracle/findings .oracle/checkins

# Phase 1 — initial plan (GPT-5.6 Sol, high reasoning)
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/plan-brief.md)" </dev/null

# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"

# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [HARD] tags)

# Phase 5 — execute (DeepSeek V4 Flash, one agent per batch)
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high
# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/checkin-brief.md)" </dev/null

# Phase 6 — commit, push, open
git add -A && git commit -m "megado: <project>" && git push && open .
```

exec
/bin/zsh -lc "git status --short && git log --oneline -5 && git diff --stat 98f4edea..907423f2 && git diff --name-only 98f4edea..907423f2 && find .oracle/checkins -maxdepth 1 -type f -name 'batch-4-r1.md' -print" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 133ms:
?? .oracle/checkins/batch-4-r2.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
907423f2 batch4-rework2: oracle re-review1 issues 1-4 (finalizer lineage through _finish_plan, direct-render finalizer invocation, explicit engine/backend conflict detection, real-service audio-reactive coverage)
98f4edea batch4-rework1: oracle issues 1-7 (finalizer for single-segment plans, planner alias/override routing, lineage preservation, rejected-candidate provenance, neutral facade extraction, config overlay, engine/backend conflict, real-backend integration tests)
a72729db batch4: generic RenderService, neutral facade, provenance v2 routing, legacy_hybrid planner, routing/hybrid matrix
9bf9db88 batch3-rework4: oracle re-review3 issue 1 (ffmpeg support rejects unguaranteed pinned video_profile/level)
a7b7b080 batch3-rework3: oracle re-review2 issues 1-4 (remotion --enforce-audio-track, canonical MP4 time-base rule + rational-aware ffmpeg support, stream-copy time-base gate, frame-accurate whole-source tolerance)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-4-r1.md                 | 8418 ++++++++++++++++++++++++
 astrid/core/rendering/service.py               |   40 +-
 astrid/packs/rendering/executors/render/run.py |   10 +-
 tests/core/rendering/test_service.py           |  113 +
 tests/packs/rendering/test_render_facade.py    |   46 +
 5 files changed, 8619 insertions(+), 8 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-4-r1.md
astrid/core/rendering/service.py
astrid/packs/rendering/executors/render/run.py
tests/core/rendering/test_service.py
tests/packs/rendering/test_render_facade.py
.oracle/checkins/batch-4-r1.md

exec
/bin/zsh -lc 'rg -n "''^(#|##|###|Verdict|PASS|HIGH|MEDIUM|LOW|[0-9]+'"\\.)\" .oracle/checkins/batch-4-r1.md | tail -100 && git diff --unified=100 98f4edea..907423f2 -- astrid/core/rendering/service.py astrid/packs/rendering/executors/render/run.py tests/core/rendering/test_service.py tests/packs/rendering/test_render_facade.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
17:# Megado Checkpoint — Batch 4 first re-review
24:## How each issue was addressed
26:1. **HIGH — single-segment plans bypass the explicit finalizer; audio
34:2. **HIGH — hybrid alias/override routing broken** →
38:3. **HIGH — alias/override lineage discarded on re-resolution** → the service
43:4. **HIGH — legacy remotion fallback drops rejected FFmpeg attempt** →
48:5. **MEDIUM — facade remains concrete and recursive** → extracted the legacy
54:6. **MEDIUM — explicit backend config replaces legacy settings** → the
57:7. **MEDIUM — engine/backend conflict silently prefers backend** → `main()`
59:8. **MEDIUM — matrix uses FakeTransport only** → added real-backend
66:## Evidence
74:## Verdict
89:# Megado
95:1. In a worktree, Codex (GPT-5.6 Sol, high reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
96:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
97:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
98:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at high reasoning produces this structure.
99:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
100:6. Open it and sync.
102:## Roles
115:## Artifacts (in the worktree)
127:## Phase 0 — Worktree
137:## Phase 1 — Initial plan (Codex)
141:1. A tasklist covering the **entirety** of the project (not just the obvious path).
142:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
143:3. Open questions / potential issues.
152:## Phase 2 — Deep exploration (DeepSeek fan-out)
165:## Phase 3 — Revise-until-stable loop
175:## Phase 4 — Batched tasklist with checkpoints (Codex)
186:## Phase 5 — Execute, with oracle checkpoints
218:## Phase 6 — Completion
220:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
221:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
222:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
224:## Gotchas
233:## Quick reference
236:# Phase 0
240:# Phase 1 — initial plan (GPT-5.6 Sol, high reasoning)
243:# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
249:# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
250:# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [HARD] tags)
252:# Phase 5 — execute (DeepSeek V4 Flash, one agent per batch)
256:# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high
257:# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/checkin-brief.md)" </dev/null
259:# Phase 6 — commit, push, open
300:# Megado Checkpoint — Batch 4
306:## What Batch 4 was supposed to deliver (tasklist)
308:1. `RenderService` (core, `astrid/core/rendering/service.py`) with the FROZEN
316:2. Neutral facade (`astrid/packs/rendering/executors/render/run.py` delegates
320:3. Additive provenance v2: routing lineage (requested engine → resolved
323:4. `rendering.legacy_hybrid` planner port
329:5. Routing/hybrid matrix: strict/legacy selectors, alias/override/trust,
335:## Evidence
347:## Verdict
362:# Megado
368:1. In a worktree, Codex (GPT-5.6 Sol, high reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
369:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
370:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
371:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at high reasoning produces this structure.
372:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
373:6. Open it and sync.
375:## Roles
388:## Artifacts (in the worktree)
400:## Phase 0 — Worktree
410:## Phase 1 — Initial plan (Codex)
414:1. A tasklist covering the **entirety** of the project (not just the obvious path).
415:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
416:3. Open questions / potential issues.
425:## Phase 2 — Deep exploration (DeepSeek fan-out)
438:## Phase 3 — Revise-until-stable loop
448:## Phase 4 — Batched tasklist with checkpoints (Codex)
459:## Phase 5 — Execute, with oracle checkpoints
491:## Phase 6 — Completion
493:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
494:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
495:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
497:## Gotchas
506:## Quick reference
509:# Phase 0
513:# Phase 1 — initial plan (GPT-5.6 Sol, high reasoning)
516:# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
522:# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
523:# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [HARD] tags)
575:## Finalization
596:## Structured errors
5072:#!/usr/bin/env python3
5112:# Compatibility exports for callers that historically imported these private
5113:# helpers from the facade.  Their implementation now lives with the backend.
5465:#!/usr/bin/env python3
5503:# Compatibility exports for callers that historically imported these private
5504:# helpers from the facade.  Their implementation now lives with the backend.
5535:# The Hype pipeline's default output file name.  The executor manifest exposes
5536:# an ``output_name`` input defaulting to this sentinel; non-default names are
5537:# validated (plain file name, ``.mp4`` extension) and flow through the same
5538:# placeholder expansion and declared-output resolution as the default.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/service.py b/astrid/core/rendering/service.py
index c3114927..4386e980 100644
--- a/astrid/core/rendering/service.py
+++ b/astrid/core/rendering/service.py
@@ -368,202 +368,224 @@ class RenderService:
                 backend=_CORE_BACKEND_ID,
                 message=f"render service failed: {exc or type(exc).__name__}",
                 recovery_command="retry the render in a fresh invocation workspace",
                 details={"error_type": type(exc).__name__},
             )
 
     @staticmethod
     def _one_selector(
         selector: str | None,
         engine: str | None,
         backend: str | None,
     ) -> str | None:
         supplied = [item for item in (selector, engine, backend) if item is not None]
         if not supplied:
             return None
         if len(set(supplied)) != 1:
             raise_protocol_error(
                 backend=_CORE_BACKEND_ID,
                 message="selector, engine, and backend disagree",
                 recovery_command="supply one renderer selector spelling and retry",
                 details={"selectors": supplied},
             )
         return supplied[0]
 
     @staticmethod
     def _absolute_input_paths(request: RenderRequest) -> RenderRequest:
         timeline = Path(request.timeline_path).expanduser()
         assets = (
             None
             if request.assets_registry_path is None
             else Path(request.assets_registry_path).expanduser()
         )
         return replace(
             request,
             timeline_path=str(timeline.resolve(strict=False)),
             assets_registry_path=(
                 None if assets is None else str(assets.resolve(strict=False))
             ),
         )
 
     def _render_in_workspace(
         self,
         request: RenderRequest,
         *,
         policy: _SelectionPolicy,
         workspace: Path,
         out_path: Path,
         sidecar_path: Path,
         previous_outputs: tuple[object, ...],
         v1_compatibility: Mapping[str, Any] | None,
     ) -> Path:
         selected = self._select(request, policy=policy, workspace=workspace)
         if policy.kind == "planner":
             plan, segment_results, pinned_finalizer = self._execute_planner(
                 request,
                 policy=policy,
                 selected=selected,
                 workspace=workspace,
             )
             if not segment_results:
                 raise_unsupported_error(
                     backend=selected.candidate.id,
                     message="render planner produced no video segments",
                     recovery_command="use a non-empty timeline or select a direct renderer",
                     details={"total_frames": plan.total_frames},
                 )
             final_result, plan = self._finish_plan(
                 request,
                 plan=plan,
                 segment_results=segment_results,
                 pinned_finalizer=pinned_finalizer,
                 workspace=workspace,
             )
             artifact_lineage = [item.video for item in segment_results]
             compatibility_results = segment_results
             fragment_results = (
                 segment_results
                 if len(segment_results) == 1
                 else [*segment_results, final_result]
             )
         else:
             final_result = self._invoke_renderer(
                 request,
                 selected=selected,
                 workspace=workspace,
                 output_name=request.output_name,
                 expected_profile=request.profile,
             )
             plan = self._direct_plan(
                 request,
                 selected=selected,
                 result=final_result,
                 requested_policy=policy.requested,
             )
             final_result = self.complete_audio(
                 final_result,
                 request=request,
                 plan=plan,
                 workspace=workspace,
                 backend=selected.candidate.id,
+                # The direct plan may pin an executable finalizer; defer
+                # completion to it so a normalizable profile/audio mismatch
+                # is normalized before publication.
+                defer_to_finalizer=(
+                    plan.finalizer.id != _DIRECT_FINALIZER_ID
+                ),
             )
-            if final_result.video.profile != plan.profile or (
+            if plan.finalizer.id != _DIRECT_FINALIZER_ID:
+                # An embedding host pinned a registered finalizer for direct
+                # renders; honor it exactly like planner-produced plans.
+                finalizer, finalizer_evidence = self._resolve_candidate(
+                    self.finalizers,
+                    plan.finalizer.id,
+                    kind="finalizer",
+                    observe=False,
+                )
+                final_result, plan = self._finish_plan(
+                    request,
+                    plan=plan,
+                    segment_results=[final_result],
+                    pinned_finalizer=(finalizer, finalizer_evidence),
+                    workspace=workspace,
+                )
+            elif final_result.video.profile != plan.profile or (
                 final_result.video.duration_frames
                 != (
                     plan.window.duration_frames
                     if plan.window is not None
                     else plan.total_frames
                 )
             ):
                 plan = self._direct_plan(
                     request,
                     selected=selected,
                     result=final_result,
                     requested_policy=policy.requested,
             )
             artifact_lineage = [final_result.video]
             compatibility_results = [final_result]
             fragment_results = [final_result]
 
         source_video = self._artifact_path(final_result, workspace)
         compatibility = self._v1_compatibility(
             compatibility_results,
             supplied=v1_compatibility,
         )
         fragments = self._merge_backend_fragments(fragment_results)
         provenance = self._provenance_builder(
             engine=policy.requested,
             output=out_path,
             timeline=request.timeline_path,
             assets_registry=request.assets_registry_path,
             plan=plan,
             artifact_profiles=artifact_lineage,
             audio_ownership=final_result.audio_ownership,
             normalization=final_result.normalization,
             attachments=final_result.attachments,
             backend_fragments=fragments,
             v1_compatibility=compatibility,
         )
         self._observe(
             "publish",
             backend=(
                 plan.planner.id if policy.kind == "planner" else selected.candidate.id
             ),
             output=str(out_path),
             sidecar=str(sidecar_path),
         )
         published = self._publisher(
             source_video,
             provenance,
             out_path=out_path,
             sidecar_path=sidecar_path,
             previous_outputs=previous_outputs,
         )
         return Path(published)
 
     def _select(
         self,
         request: RenderRequest,
         *,
         policy: _SelectionPolicy,
         workspace: Path,
     ) -> _ResolvedCapability:
         registry: RendererRegistry | PlannerRegistry = (
             self.renderers if policy.kind == "renderer" else self.planners
         )
         rejected: list[dict[str, Any]] = []
         for index, target in enumerate(policy.targets):
             try:
                 candidate, evidence = self._resolve_candidate(
                     registry,
                     target,
                     kind=policy.kind,
                 )
                 report = self._support(
                     candidate,
                     request=request,
                     workspace=workspace,
                     registry=registry,
                 )
             except RendererException as exc:
                 if not policy.auto_route or index == len(policy.targets) - 1:
                     raise
                 if exc.error.kind not in {"unsupported", "binary_missing"}:
                     raise
                 rejected.append(exc.error.to_dict())
                 continue
             if not report.supported:
                 rejected.append(report.to_dict())
                 if policy.auto_route and index < len(policy.targets) - 1:
                     continue
                 self._unsupported_report(report, registry=registry)
             if policy.auto_route and index == 0:
                 warnings.warn(
                     f"legacy selector {policy.requested!r} auto-routed this supported "
                     f"timeline to {candidate.id}; select a qualified renderer "
                     "id for strict routing",
                     LegacyRenderRoutingWarning,
                     stacklevel=4,
                 )
             return _ResolvedCapability(
                 candidate,
                 evidence,
@@ -1254,204 +1276,212 @@ class RenderService:
                 defer_to_finalizer=response.finalizer.id != _DIRECT_FINALIZER_ID,
             )
             self._validate_segment_duration(
                 completed,
                 segment=segment,
                 canonical_profile=response.profile,
                 backend=candidate.id,
             )
             segment_results.append(completed)
 
         finalizer, finalizer_evidence = self._resolve_candidate(
             self.finalizers,
             response.finalizer.id,
             kind="finalizer",
             observe=False,
         )
         finalizer_resolution = replace(
             response.finalizer,
             id=finalizer.id,
             source_pack=self._source_pack(finalizer, finalizer_evidence),
             manifest_digest=finalizer.manifest_digest,
             trust_eligibility=finalizer.eligibility.to_dict(),
             alias_chain=(
                 response.finalizer.alias_chain
                 or list(finalizer_evidence.get("alias_chain") or [])
             ),
             override=response.finalizer.override or finalizer_evidence.get("override"),
             # The planner's finalizer support_decision names its pre-alias
             # identity; _finish_plan re-evaluates support for the resolved
             # finalizer and records the authoritative decision.
             support_decision=None,
         )
         plan = replace(
             response,
             request_digest=compute_request_digest(request.to_dict()),
             requested_policy=policy.requested,
             planner=planner_resolution,
             segments=normalized_segments,
             finalizer=finalizer_resolution,
         )
         return plan, segment_results, (finalizer, finalizer_evidence)
 
     def _finish_plan(
         self,
         request: RenderRequest,
         *,
         plan: RenderPlan,
         segment_results: list[RenderResult],
         pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
         workspace: Path,
     ) -> tuple[RenderResult, RenderPlan]:
         candidate, evidence = pinned_finalizer
         if candidate.id == _DIRECT_FINALIZER_ID:
             # No executable finalizer pinned: the segment must already match
             # the canonical plan profile exactly.
             if len(segment_results) != 1:
                 raise_internal_error(
                     backend=_CORE_BACKEND_ID,
                     message="direct finalizer received multiple segments",
                     recovery_command="select a planner that pins an executable finalizer",
                     details={"segment_count": len(segment_results)},
                 )
             result = self._validator(
                 segment_results[0],
                 expected_profile=plan.profile,
                 workspace_root=workspace,
             )
             return result, plan
 
         ownerships = {item.audio_ownership for item in segment_results}
         if ownerships == {AudioOwnership.PASSTHROUGH}:
             requested_audio = AudioOwnership.PASSTHROUGH
         elif plan.profile.has_audio:
             requested_audio = AudioOwnership.RENDERED
         else:
             requested_audio = AudioOwnership.NONE
         support_audio = (
             None
             if requested_audio is AudioOwnership.PASSTHROUGH
             and plan.profile.has_audio
             else requested_audio
         )
         support_request = RenderRequest(
             schema_version=SCHEMA_VERSION,
             timeline_path=request.timeline_path,
             assets_registry_path=request.assets_registry_path,
             output_name=request.output_name,
             audio=support_audio,
             profile=plan.profile,
             backend_config=request.backend_config,
             metadata=request.metadata,
         )
         report = self._support(
             candidate,
             request=support_request,
             workspace=workspace,
             registry=self.finalizers,
         )
         if not report.supported:
             self._unsupported_report(report, registry=self.finalizers)
-        finalizer_resolution = self._finalizer_resolution(
-            candidate,
-            evidence,
-            support=report,
+        prior_finalizer = plan.finalizer
+        finalizer_resolution = replace(
+            self._finalizer_resolution(
+                candidate,
+                evidence,
+                support=report,
+            ),
+            alias_chain=(
+                prior_finalizer.alias_chain
+                or list(evidence.get("alias_chain") or [])
+            ),
+            override=prior_finalizer.override or evidence.get("override"),
         )
         plan = replace(plan, finalizer=finalizer_resolution)
         finalize_request = FinalizeRequest(
             schema_version=SCHEMA_VERSION,
             plan=plan,
             artifacts=[item.video for item in segment_results],
             output_name=request.output_name,
             backend_config={
                 candidate.id: dict(request.backend_config.get(candidate.id, {}))
             }
             if candidate.id in request.backend_config
             else {},
             metadata=request.metadata,
         )
         self._observe("finalize", backend=candidate.id)
         response = self._run_command(
             candidate,
             "finalize",
             finalize_request,
             workspace=workspace,
         )
         if not isinstance(response, RenderResult):
             raise_protocol_error(
                 backend=candidate.id,
                 message="finalize operation did not return a RenderResult",
                 details={"received_type": type(response).__name__},
             )
         try:
             response = finalize_request.validate_final_result(response)
         except (TypeError, ValueError) as exc:
             raise_invalid_artifact_error(
                 backend=candidate.id,
                 message=f"finalizer returned an invalid result: {exc}",
                 recovery_command="rerun finalization in a fresh invocation workspace",
                 details={"error_type": type(exc).__name__},
             )
         self._observe("validate", backend=candidate.id)
         validated = self._validator(
             response,
             expected_profile=plan.profile,
             workspace_root=workspace,
         )
         self._validate_planned_duration(
             validated,
             planned_frames=(
                 plan.window.duration_frames
                 if plan.window is not None
                 else plan.total_frames
             ),
             canonical_profile=plan.profile,
             backend=candidate.id,
             label="finalized artifact",
         )
         completed = self.complete_audio(
             validated,
             request=request,
             plan=plan,
             workspace=workspace,
             backend=candidate.id,
         )
         self._validate_planned_duration(
             completed,
             planned_frames=(
                 plan.window.duration_frames
                 if plan.window is not None
                 else plan.total_frames
             ),
             canonical_profile=plan.profile,
             backend=candidate.id,
             label="audio-completed artifact",
         )
         return completed, plan
 
     def complete_audio(
         self,
         result: RenderResult,
         *,
         request: RenderRequest,
         plan: RenderPlan,
         workspace: Path,
         backend: str = _CORE_BACKEND_ID,
         defer_to_finalizer: bool = False,
     ) -> RenderResult:
         """Apply host-owned completion semantics after renderer validation.
 
         ``rendered`` is already complete. ``none`` is an intentional
         visual-only result, while ``passthrough`` must be completed by the
         embedding host before publication.  A configured completer may also
         apply an optional compatibility policy to ``none`` without requiring
         arbitrary renderers to synthesize silence.
         """
 
         self._observe("audio", ownership=result.audio_ownership.value)
         if result.audio_ownership is AudioOwnership.RENDERED:
             return result
         if result.video.profile.has_audio:
             raise_invalid_artifact_error(
                 backend=backend,
                 message=(
                     f"audio_ownership={result.audio_ownership.value!r} requires "
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index bee39a44..e04e3b37 100755
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -141,190 +141,194 @@ def _previous_render_outputs_for_timeline(
 ) -> tuple[Path, ...]:
     """Discover legacy sibling outputs; publication validates before deleting.
 
     The timeline argument remains part of the helper boundary for compatibility
     with the legacy cleanup call site.  Filtering now happens under each
     candidate's publication lock using the committed sidecar.
     """
 
     out_path = out_path.resolve()
     if out_path.name != "hype.mp4":
         return ()
     run_dir = out_path.parent
     runs_dir = run_dir.parent
     if runs_dir.name != "runs" or not runs_dir.is_dir():
         return ()
     candidates: list[Path] = []
     for candidate_run_dir in runs_dir.iterdir():
         if not candidate_run_dir.is_dir() or candidate_run_dir == run_dir:
             continue
         candidates.append(candidate_run_dir / out_path.name)
     return tuple(candidates)
 
 
 def _parse_bool_arg(value: str | bool | None) -> bool:
     if value is None:
         return True
     if isinstance(value, bool):
         return value
     normalized = value.strip().lower()
     if normalized in {"1", "true", "yes", "y", "on"}:
         return True
     if normalized in {"0", "false", "no", "n", "off"}:
         return False
     raise argparse.ArgumentTypeError(f"expected boolean value, got {value!r}")
 
 
 def render(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     engine: str = "remotion",
     project_dir: Path | None = None,
     composition_id: str = "TimelineComposition",
     theme_path: Path | None = None,
     min_free_gb: float | None = None,
     keep_previous_renders: bool = False,
     backend_config: Mapping[str, Mapping[str, Any]] | None = None,
 ) -> Path:
     """Render through :class:`RenderService` and publish one locked pair.
 
     The facade keeps the historical public signature and capability id.  All
     dispatch (legacy engine translation, renderer/planner selection, support,
     invocation, validation, audio completion, finalization, publication)
     happens in the service; the facade only adapts the legacy argument surface
     and the caller-selected output name.
     """
     out_path = Path(out_path)
     validate_output_name(out_path.name)
     previous_outputs = (
         ()
         if keep_previous_renders
         else _previous_render_outputs_for_timeline(out_path, timeline_path)
     )
     config = _legacy_backend_config(
         project_dir=project_dir,
         composition_id=composition_id,
         theme_path=theme_path,
         min_free_gb=min_free_gb,
     )
     for key, value in (backend_config or {}).items():
         if value is None:
             continue
         existing = config.get(str(key))
         if existing is None:
             config[str(key)] = dict(value)
         else:
             # Explicit caller configuration overlays, never replaces, the
             # legacy-derived settings so project/theme/composition values
             # survive a partial --backend-config payload.
             overlaid = dict(existing)
             overlaid.update({k: v for k, v in value.items() if v is not None})
             config[str(key)] = overlaid
     return _default_service().render(
         timeline_path,
         assets_path,
         out_path,
         selector=engine,
         backend_config=config,
         previous_outputs=previous_outputs,
     )
 
 
 def main(argv: Sequence[str] | None = None) -> int:
     parser = argparse.ArgumentParser()
     parser.add_argument("--timeline", type=Path, required=True)
     parser.add_argument("--assets", type=Path)
     parser.add_argument("--out", type=Path, required=True)
     parser.add_argument(
         "--engine",
-        default="remotion",
+        default=None,
         help="Legacy selector (remotion, ffmpeg, hybrid) or a qualified renderer id.",
     )
     parser.add_argument(
         "--backend",
         default=None,
         help="Neutral alias for --engine: legacy selector or qualified backend id.",
     )
     parser.add_argument(
         "--backend-config",
         default=None,
         help="JSON object keyed by qualified backend id with per-backend configuration.",
     )
     parser.add_argument(
         "--output-name",
         default=None,
         help="Output file name (default hype.mp4); plain .mp4 file name only.",
     )
     parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
     parser.add_argument("--composition", default="TimelineComposition")
     parser.add_argument("--min-free-gb", type=float, default=None, help="Abort before rendering unless this much free disk is available near --out.")
     parser.add_argument(
         "--keep-previous-renders",
         nargs="?",
         const=True,
         default=False,
         type=_parse_bool_arg,
         help="Preserve previous sibling hype.mp4 outputs for the same timeline.",
     )
     parser.add_argument(
         "--theme",
         type=Path,
         default=REPO_ROOT / "themes" / "banodoco-default" / "theme.json",
     )
     args = parser.parse_args(argv)
     try:
         if args.output_name is not None:
             validate_output_name(args.output_name)
             if Path(args.out).name != args.output_name:
                 raise ValueError(
                     f"--out basename {Path(args.out).name!r} does not match "
                     f"--output-name {args.output_name!r}"
                 )
         else:
             validate_output_name(Path(args.out).name)
-        if args.backend is not None and args.engine != "remotion":
+        if args.backend is not None and args.engine is not None:
             raise ValueError(
                 f"--engine {args.engine!r} and --backend {args.backend!r} "
                 "conflict; supply exactly one selector"
             )
-        selector = args.backend if args.backend is not None else args.engine
+        selector = (
+            args.backend
+            if args.backend is not None
+            else (args.engine if args.engine is not None else "remotion")
+        )
         config = _parse_backend_config(args.backend_config)
         if args.assets is None:
             with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
                 assets_path = Path(tmp_text) / "hype.assets.json"
                 _write_empty_asset_registry(assets_path)
                 output = render(
                     args.timeline,
                     assets_path,
                     args.out,
                     engine=selector,
                     project_dir=args.project_dir,
                     composition_id=args.composition,
                     theme_path=args.theme,
                     min_free_gb=args.min_free_gb,
                     keep_previous_renders=args.keep_previous_renders,
                     backend_config=config,
                 )
         else:
             output = render(
                 args.timeline,
                 args.assets,
                 args.out,
                 engine=selector,
                 project_dir=args.project_dir,
                 composition_id=args.composition,
                 theme_path=args.theme,
                 min_free_gb=args.min_free_gb,
                 keep_previous_renders=args.keep_previous_renders,
                 backend_config=config,
             )
     except Exception as exc:  # pragma: no cover - CLI path
         print(str(exc), file=sys.stderr)
         return 1
     print(output)
     return 0
 
 
 if __name__ == "__main__":
     raise SystemExit(main())
diff --git a/tests/core/rendering/test_service.py b/tests/core/rendering/test_service.py
index c1c327b6..67c15345 100644
--- a/tests/core/rendering/test_service.py
+++ b/tests/core/rendering/test_service.py
@@ -1969,100 +1969,213 @@ def _add_audio_track(timeline_path: Path) -> None:
             str(audio_path),
         ],
         check=True,
         capture_output=True,
         text=True,
     )
     muxed = timeline_path.parent / "muxed.mp4"
     subprocess.run(
         [
             "ffmpeg",
             "-hide_banner",
             "-loglevel",
             "error",
             "-y",
             "-i",
             str(source),
             "-i",
             str(audio_path),
             "-c:v",
             "copy",
             "-c:a",
             "aac",
             "-shortest",
             str(muxed),
         ],
         check=True,
         capture_output=True,
         text=True,
     )
     muxed.replace(source)
 
 
 @pytest.mark.parametrize(
     "media_kind",
     ["plain", "audio"],
     ids=["nominal", "with-audio"],
 )
 def test_real_ffmpeg_renders_through_generic_service(
     tmp_path: Path,
     media_kind: str,
 ) -> None:
     """The service drives the real FFmpeg backend end to end: one video and
     one committed sidecar through the real CommandTransport (no fake
     transport), including the whole-media optimized path when the source
     probe supports it."""
     _require_ffmpeg()
     timeline_path, assets_path = _real_media_inputs(tmp_path)
     if media_kind == "audio":
         _add_audio_track(timeline_path)
     service = _real_service(tmp_path)
     output = tmp_path / "real-ffmpeg.mp4"
 
     service.render_request(
         replace(
             _request(tmp_path),
             timeline_path=str(timeline_path),
             assets_registry_path=str(assets_path),
         ),
         selector="rendering.ffmpeg",
         out_path=output,
     )
 
     assert output.is_file()
     assert output.stat().st_size > 0
     sidecars = list(tmp_path.glob("*.provenance.json"))
     assert sidecars == [Path(f"{output}.provenance.json")]
     payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
     assert payload["output"] == str(output.resolve())
     assert payload["routing"]["requested_engine"] == "rendering.ffmpeg"
 
 
 def test_real_hybrid_plans_assigns_ffmpeg_and_finalizes_through_service(
     tmp_path: Path,
 ) -> None:
     """Real hybrid planning: the media-only timeline routes every window to
     the real FFmpeg backend and the real ffmpeg finalizer concatenates."""
     _require_ffmpeg()
     timeline_path, assets_path = _real_media_inputs(tmp_path)
     service = _real_service(tmp_path)
     output = tmp_path / "real-hybrid.mp4"
 
     service.render_request(
         replace(
             _request(tmp_path),
             timeline_path=str(timeline_path),
             assets_registry_path=str(assets_path),
         ),
         selector="hybrid",
         out_path=output,
     )
 
     assert output.is_file()
     assert output.stat().st_size > 0
     sidecars = list(tmp_path.glob("*.provenance.json"))
     assert sidecars == [Path(f"{output}.provenance.json")]
     payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
     assert payload["routing"]["requested_engine"] == "hybrid"
     resolved = payload["routing"]["resolved_policy"]
     assert resolved["planner"] == "rendering.legacy_hybrid"
     assert resolved["finalizer"] == "rendering.ffmpeg-finalizer"
+
+
+def _real_audio_reactive_inputs(tmp_path: Path) -> tuple[Path, Path]:
+    """A two-clip timeline the strict FFmpeg backend renders through its
+    audio-reactive colour specialization (real AAC audio source)."""
+    root = tmp_path / "reactive"
+    root.mkdir(exist_ok=True)
+    audio_path = root / "tone.wav"
+    subprocess.run(
+        [
+            "ffmpeg",
+            "-hide_banner",
+            "-loglevel",
+            "error",
+            "-y",
+            "-f",
+            "lavfi",
+            "-i",
+            "sine=frequency=440:sample_rate=48000:duration=0.5",
+            str(audio_path),
+        ],
+        check=True,
+        capture_output=True,
+        text=True,
+    )
+    timeline_path = root / "timeline.json"
+    assets_path = root / "assets.json"
+    timeline_path.write_text(
+        json.dumps(
+            {
+                "theme": "banodoco-default",
+                "theme_overrides": {
+                    "visual": {"canvas": {"width": 640, "height": 360, "fps": 48}}
+                },
+                "tracks": [
+                    {"id": "colour", "kind": "visual", "label": "Colour"},
+                    {"id": "audio", "kind": "audio", "label": "Audio"},
+                ],
+                "clips": [
+                    {
+                        "id": "colour_map",
+                        "at": 0,
+                        "track": "colour",
+                        "clipType": "audio-reactive-colour",
+                        "hold": 0.5,
+                        "params": {
+                            "schemaVersion": 1,
+                            "initialColor": "#102030",
+                            "events": [
+                                {"id": "a", "frame": 3, "color": "#D47795"},
+                                {"id": "b", "frame": 8, "color": "#26A7D0"},
+                                {"id": "c", "frame": 17, "color": "#B59432"},
+                            ],
+                        },
+                    },
+                    {
+                        "id": "source_audio",
+                        "at": 0,
+                        "track": "audio",
+                        "clipType": "media",
+                        "asset": "audio",
+                        "from": 0,
+                        "to": 0.5,
+                    },
+                ],
+            }
+        ),
+        encoding="utf-8",
+    )
+    assets_path.write_text(
+        json.dumps(
+            {
+                "assets": {
+                    "audio": {
+                        "file": str(audio_path),
+                        "type": "audio/wav",
+                        "duration": 0.5,
+                    }
+                }
+            }
+        ),
+        encoding="utf-8",
+    )
+    return timeline_path, assets_path
+
+
+def test_real_ffmpeg_audio_reactive_through_generic_service(
+    tmp_path: Path,
+) -> None:
+    """The service drives the real FFmpeg backend through its audio-reactive
+    colour specialization end to end (no fake transport)."""
+    _require_ffmpeg()
+    timeline_path, assets_path = _real_audio_reactive_inputs(tmp_path)
+    service = _real_service(tmp_path)
+    output = tmp_path / "real-reactive.mp4"
+
+    service.render_request(
+        replace(
+            _request(tmp_path),
+            timeline_path=str(timeline_path),
+            assets_registry_path=str(assets_path),
+        ),
+        selector="rendering.ffmpeg",
+        out_path=output,
+    )
+
+    assert output.is_file()
+    assert output.stat().st_size > 0
+    sidecars = list(tmp_path.glob("*.provenance.json"))
+    assert sidecars == [Path(f"{output}.provenance.json")]
+    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
+    assert payload["routing"]["requested_engine"] == "rendering.ffmpeg"
+    assert payload["audio_ownership"] == "rendered"
diff --git a/tests/packs/rendering/test_render_facade.py b/tests/packs/rendering/test_render_facade.py
index 82048837..270574df 100644
--- a/tests/packs/rendering/test_render_facade.py
+++ b/tests/packs/rendering/test_render_facade.py
@@ -100,100 +100,146 @@ def test_render_maps_legacy_kwargs_into_namespaced_backend_config(
         "project_dir": str(tmp_path / "remotion"),
         "composition_id": "CustomComposition",
         "theme_path": str(tmp_path / "theme.json"),
         "min_free_gb": 2.0,
     }
     assert config["rendering.legacy_hybrid"] == {
         "theme_path": str(tmp_path / "theme.json")
     }
 
 
 def test_render_merges_explicit_backend_config_after_legacy_kwargs(
     fake_service: _FakeService, tmp_path: Path
 ) -> None:
     timeline, assets, out = _inputs(tmp_path)
 
     render_run.render(
         timeline,
         assets,
         out,
         engine="rendering.remotion",
         theme_path=tmp_path / "theme.json",
         backend_config={
             "rendering.remotion": {
                 "theme_path": str(tmp_path / "override.json"),
                 "min_free_gb": 9.5,
             }
         },
     )
 
     assert len(fake_service.calls) == 1
     config = fake_service.calls[0][1]["backend_config"]
     assert config["rendering.remotion"]["theme_path"] == str(tmp_path / "override.json")
     assert config["rendering.remotion"]["min_free_gb"] == 9.5
 
 
 def test_render_passes_previous_outputs_when_preserving(fake_service: _FakeService, tmp_path: Path) -> None:
     timeline, assets, out = _inputs(tmp_path)
 
     render_run.render(timeline, assets, out, keep_previous_renders=True)
 
     assert len(fake_service.calls) == 1
     assert fake_service.calls[0][1]["previous_outputs"] == ()
 
 
 def test_render_validates_output_name_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
     timeline, assets, _out = _inputs(tmp_path)
     bad_out = tmp_path / "out" / "video.mov"
 
     with pytest.raises(ValueError, match=r"\.mp4"):
         render_run.render(timeline, assets, bad_out)
 
 
 def test_main_accepts_output_name_and_forward_parses_any_order(
     fake_service: _FakeService, tmp_path: Path, capsys: pytest.CaptureFixture[str]
 ) -> None:
     timeline, assets, out = _inputs(tmp_path)
     out = tmp_path / "out" / "iteration.mp4"
     fake_service.sentinel = out
 
     result = render_run.main(
         [
             "--out",
             str(out),
             "--output-name",
             "iteration.mp4",
             "--timeline",
             str(timeline),
             "--assets",
             str(assets),
             "--engine",
             "rendering.ffmpeg",
         ]
     )
 
     assert result == 0
     assert capsys.readouterr().out.strip() == str(out)
     assert len(fake_service.calls) == 1
     assert fake_service.calls[0][1]["selector"] == "rendering.ffmpeg"
 
 
 def test_main_rejects_traversal_output_name(
     tmp_path: Path, capsys: pytest.CaptureFixture[str]
 ) -> None:
     timeline, assets, _out = _inputs(tmp_path)
 
     result = render_run.main(
         [
             "--timeline",
             str(timeline),
             "--assets",
             str(assets),
             "--out",
             str(tmp_path / "out" / "hype.mp4"),
             "--output-name",
             "../evil.mp4",
         ]
     )
 
     assert result == 1
     assert "traverse" in capsys.readouterr().err
+
+
+def test_main_rejects_conflicting_engine_and_backend(
+    tmp_path: Path, capsys: pytest.CaptureFixture[str]
+) -> None:
+    timeline, assets, _out = _inputs(tmp_path)
+
+    result = render_run.main(
+        [
+            "--timeline",
+            str(timeline),
+            "--assets",
+            str(assets),
+            "--out",
+            str(tmp_path / "out" / "hype.mp4"),
+            "--engine",
+            "remotion",
+            "--backend",
+            "ffmpeg",
+        ]
+    )
+
+    assert result == 1
+    assert "conflict" in capsys.readouterr().err
+
+
+def test_main_engine_defaults_to_remotion_when_absent(
+    tmp_path: Path, fake_service: _FakeService
+) -> None:
+    timeline, assets, out = _inputs(tmp_path)
+    fake_service.sentinel = out
+
+    result = render_run.main(
+        [
+            "--timeline",
+            str(timeline),
+            "--assets",
+            str(assets),
+            "--out",
+            str(out),
+        ]
+    )
+
+    assert result == 0
+    assert len(fake_service.calls) == 1
+    assert fake_service.calls[0][1]["selector"] == "remotion"

exec
/bin/zsh -lc "sed -n '1,88p' .oracle/checkins/batch-4-r1.md && git diff --unified=80 98f4edea..907423f2 -- astrid/core/rendering/service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
Reading additional input from stdin...
2026-08-12T15:16:19.934505Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:16:19.936128Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:16:19.936165Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ff68b-adb4-7670-9c64-c5c6ce3df14c
--------
user
# Megado Checkpoint — Batch 4 first re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
Prior verdict batch-4.md listed 7 issues (4 HIGH, 3 MEDIUM). All host-fixed.
Batch 4 rework committed as `98f4edea` (prior head a72729db). Incremental diff:
`git diff a72729db..98f4edea`.

## How each issue was addressed

1. **HIGH — single-segment plans bypass the explicit finalizer; audio
   completes prematurely** → `_execute_planner` now defers segment audio to
   the plan's finalizer whenever the plan pins a real finalizer
   (`response.finalizer.id != astrid.direct-finalizer`), and `_finish_plan`
   runs the pinned finalizer for single-segment plans too (the direct-marker
   shortcut is restricted to the actual no-op direct finalizer). Matrix tests
   updated: hybrid single-segment now finalizes and the fake finalizer honors
   the requested audio ownership.
2. **HIGH — hybrid alias/override routing broken** →
   `astrid/packs/rendering/planners/legacy_hybrid/run.py` now resolves each
   candidate id through the renderer registry before comparing against the
   support report's backend, so valid aliases/overrides are accepted.
3. **HIGH — alias/override lineage discarded on re-resolution** → the service
   now MERGES the planner's recorded `alias_chain`/`override` into its
   authoritative re-resolution (renderer and finalizer), keeping lineage
   while refreshing id/source/manifest/trust from the registry. Per-segment
   `support_decision` comes from the service's own report.
4. **HIGH — legacy remotion fallback drops rejected FFmpeg attempt** →
   `_ResolvedCapability` carries the `rejected` attempts; `_direct_plan`
   records them in the segment reason string, surfaced via
   `routing.segment_reasons` in the sidecar. Regression test asserts the
   rejected FFmpeg evidence appears.
5. **MEDIUM — facade remains concrete and recursive** → extracted the legacy
   engine (hybrid renderer, ffmpeg media shims, window math, provenance v1
   writers, backend aliases) into
   `astrid/packs/rendering/executors/render/legacy_engine.py`; the facade
   `run.py` is now a neutral adapter (render/main/validation/config only).
   Characterization + registry tests point at `legacy_engine`.
6. **MEDIUM — explicit backend config replaces legacy settings** → the
   facade now overlays caller `backend_config` onto the legacy-derived
   per-backend config (per-key, None values skipped) instead of replacing.
7. **MEDIUM — engine/backend conflict silently prefers backend** → `main()`
   raises a ValueError when both `--engine` and `--backend` are supplied.
8. **MEDIUM — matrix uses FakeTransport only** → added real-backend
   integration tests in `tests/core/rendering/test_service.py`:
   `test_real_ffmpeg_renders_through_generic_service` (nominal + with-audio
   whole-media optimized path, real CommandTransport) and
   `test_real_hybrid_plans_assigns_ffmpeg_and_finalizes_through_service`
   (real FFmpeg segment + real ffmpeg finalizer).

## Evidence

- `pytest -q tests/core/rendering/ tests/packs/rendering/ tests/packs/hype
  tests/packs/iteration tests/packs/editorial` → 735 passed, 3 skipped,
  1 failed (pre-existing model-trends env fixture, unchanged baseline).
- All 7 prior issues re-checked against their cited lines; each line now
  behaves per the verdict.

## Verdict

Binary `PASS` or issues. On PASS, Batch 5 (caller migration + semantic
parity + M1 freeze) begins. Say exactly `PASS` if clean.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Megado skill for this checkpoint and will inspect only the committed incremental diff and relevant tests, keeping the worktree unchanged.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, high reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where a GPT-5.6 Sol oracle reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/service.py b/astrid/core/rendering/service.py
index c3114927..4386e980 100644
--- a/astrid/core/rendering/service.py
+++ b/astrid/core/rendering/service.py
@@ -388,162 +388,184 @@ class RenderService:
                 details={"selectors": supplied},
             )
         return supplied[0]
 
     @staticmethod
     def _absolute_input_paths(request: RenderRequest) -> RenderRequest:
         timeline = Path(request.timeline_path).expanduser()
         assets = (
             None
             if request.assets_registry_path is None
             else Path(request.assets_registry_path).expanduser()
         )
         return replace(
             request,
             timeline_path=str(timeline.resolve(strict=False)),
             assets_registry_path=(
                 None if assets is None else str(assets.resolve(strict=False))
             ),
         )
 
     def _render_in_workspace(
         self,
         request: RenderRequest,
         *,
         policy: _SelectionPolicy,
         workspace: Path,
         out_path: Path,
         sidecar_path: Path,
         previous_outputs: tuple[object, ...],
         v1_compatibility: Mapping[str, Any] | None,
     ) -> Path:
         selected = self._select(request, policy=policy, workspace=workspace)
         if policy.kind == "planner":
             plan, segment_results, pinned_finalizer = self._execute_planner(
                 request,
                 policy=policy,
                 selected=selected,
                 workspace=workspace,
             )
             if not segment_results:
                 raise_unsupported_error(
                     backend=selected.candidate.id,
                     message="render planner produced no video segments",
                     recovery_command="use a non-empty timeline or select a direct renderer",
                     details={"total_frames": plan.total_frames},
                 )
             final_result, plan = self._finish_plan(
                 request,
                 plan=plan,
                 segment_results=segment_results,
                 pinned_finalizer=pinned_finalizer,
                 workspace=workspace,
             )
             artifact_lineage = [item.video for item in segment_results]
             compatibility_results = segment_results
             fragment_results = (
                 segment_results
                 if len(segment_results) == 1
                 else [*segment_results, final_result]
             )
         else:
             final_result = self._invoke_renderer(
                 request,
                 selected=selected,
                 workspace=workspace,
                 output_name=request.output_name,
                 expected_profile=request.profile,
             )
             plan = self._direct_plan(
                 request,
                 selected=selected,
                 result=final_result,
                 requested_policy=policy.requested,
             )
             final_result = self.complete_audio(
                 final_result,
                 request=request,
                 plan=plan,
                 workspace=workspace,
                 backend=selected.candidate.id,
+                # The direct plan may pin an executable finalizer; defer
+                # completion to it so a normalizable profile/audio mismatch
+                # is normalized before publication.
+                defer_to_finalizer=(
+                    plan.finalizer.id != _DIRECT_FINALIZER_ID
+                ),
             )
-            if final_result.video.profile != plan.profile or (
+            if plan.finalizer.id != _DIRECT_FINALIZER_ID:
+                # An embedding host pinned a registered finalizer for direct
+                # renders; honor it exactly like planner-produced plans.
+                finalizer, finalizer_evidence = self._resolve_candidate(
+                    self.finalizers,
+                    plan.finalizer.id,
+                    kind="finalizer",
+                    observe=False,
+                )
+                final_result, plan = self._finish_plan(
+                    request,
+                    plan=plan,
+                    segment_results=[final_result],
+                    pinned_finalizer=(finalizer, finalizer_evidence),
+                    workspace=workspace,
+                )
+            elif final_result.video.profile != plan.profile or (
                 final_result.video.duration_frames
                 != (
                     plan.window.duration_frames
                     if plan.window is not None
                     else plan.total_frames
                 )
             ):
                 plan = self._direct_plan(
                     request,
                     selected=selected,
                     result=final_result,
                     requested_policy=policy.requested,
             )
             artifact_lineage = [final_result.video]
             compatibility_results = [final_result]
             fragment_results = [final_result]
 
         source_video = self._artifact_path(final_result, workspace)
         compatibility = self._v1_compatibility(
             compatibility_results,
             supplied=v1_compatibility,
         )
         fragments = self._merge_backend_fragments(fragment_results)
         provenance = self._provenance_builder(
             engine=policy.requested,
             output=out_path,
             timeline=request.timeline_path,
             assets_registry=request.assets_registry_path,
             plan=plan,
             artifact_profiles=artifact_lineage,
             audio_ownership=final_result.audio_ownership,
             normalization=final_result.normalization,
             attachments=final_result.attachments,
             backend_fragments=fragments,
             v1_compatibility=compatibility,
         )
         self._observe(
             "publish",
             backend=(
                 plan.planner.id if policy.kind == "planner" else selected.candidate.id
             ),
             output=str(out_path),
             sidecar=str(sidecar_path),
         )
         published = self._publisher(
             source_video,
             provenance,
             out_path=out_path,
             sidecar_path=sidecar_path,
             previous_outputs=previous_outputs,
         )
         return Path(published)
 
     def _select(
         self,
         request: RenderRequest,
         *,
         policy: _SelectionPolicy,
         workspace: Path,
     ) -> _ResolvedCapability:
         registry: RendererRegistry | PlannerRegistry = (
             self.renderers if policy.kind == "renderer" else self.planners
         )
         rejected: list[dict[str, Any]] = []
         for index, target in enumerate(policy.targets):
             try:
                 candidate, evidence = self._resolve_candidate(
                     registry,
                     target,
                     kind=policy.kind,
                 )
                 report = self._support(
                     candidate,
                     request=request,
                     workspace=workspace,
                     registry=registry,
                 )
             except RendererException as exc:
                 if not policy.auto_route or index == len(policy.targets) - 1:
                     raise
@@ -1274,164 +1296,172 @@ class RenderService:
             manifest_digest=finalizer.manifest_digest,
             trust_eligibility=finalizer.eligibility.to_dict(),
             alias_chain=(
                 response.finalizer.alias_chain
                 or list(finalizer_evidence.get("alias_chain") or [])
             ),
             override=response.finalizer.override or finalizer_evidence.get("override"),
             # The planner's finalizer support_decision names its pre-alias
             # identity; _finish_plan re-evaluates support for the resolved
             # finalizer and records the authoritative decision.
             support_decision=None,
         )
         plan = replace(
             response,
             request_digest=compute_request_digest(request.to_dict()),
             requested_policy=policy.requested,
             planner=planner_resolution,
             segments=normalized_segments,
             finalizer=finalizer_resolution,
         )
         return plan, segment_results, (finalizer, finalizer_evidence)
 
     def _finish_plan(
         self,
         request: RenderRequest,
         *,
         plan: RenderPlan,
         segment_results: list[RenderResult],
         pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
         workspace: Path,
     ) -> tuple[RenderResult, RenderPlan]:
         candidate, evidence = pinned_finalizer
         if candidate.id == _DIRECT_FINALIZER_ID:
             # No executable finalizer pinned: the segment must already match
             # the canonical plan profile exactly.
             if len(segment_results) != 1:
                 raise_internal_error(
                     backend=_CORE_BACKEND_ID,
                     message="direct finalizer received multiple segments",
                     recovery_command="select a planner that pins an executable finalizer",
                     details={"segment_count": len(segment_results)},
                 )
             result = self._validator(
                 segment_results[0],
                 expected_profile=plan.profile,
                 workspace_root=workspace,
             )
             return result, plan
 
         ownerships = {item.audio_ownership for item in segment_results}
         if ownerships == {AudioOwnership.PASSTHROUGH}:
             requested_audio = AudioOwnership.PASSTHROUGH
         elif plan.profile.has_audio:
             requested_audio = AudioOwnership.RENDERED
         else:
             requested_audio = AudioOwnership.NONE
         support_audio = (
             None
             if requested_audio is AudioOwnership.PASSTHROUGH
             and plan.profile.has_audio
             else requested_audio
         )
         support_request = RenderRequest(
             schema_version=SCHEMA_VERSION,
             timeline_path=request.timeline_path,
             assets_registry_path=request.assets_registry_path,
             output_name=request.output_name,
             audio=support_audio,
             profile=plan.profile,
             backend_config=request.backend_config,
             metadata=request.metadata,
         )
         report = self._support(
             candidate,
             request=support_request,
             workspace=workspace,
             registry=self.finalizers,
         )
         if not report.supported:
             self._unsupported_report(report, registry=self.finalizers)
-        finalizer_resolution = self._finalizer_resolution(
-            candidate,
-            evidence,
-            support=report,
+        prior_finalizer = plan.finalizer
+        finalizer_resolution = replace(
+            self._finalizer_resolution(
+                candidate,
+                evidence,
+                support=report,
+            ),
+            alias_chain=(
+                prior_finalizer.alias_chain
+                or list(evidence.get("alias_chain") or [])
+            ),
+            override=prior_finalizer.override or evidence.get("override"),
         )
         plan = replace(plan, finalizer=finalizer_resolution)
         finalize_request = FinalizeRequest(
             schema_version=SCHEMA_VERSION,
             plan=plan,
             artifacts=[item.video for item in segment_results],
             output_name=request.output_name,
             backend_config={
                 candidate.id: dict(request.backend_config.get(candidate.id, {}))
             }
             if candidate.id in request.backend_config
             else {},
             metadata=request.metadata,
         )
         self._observe("finalize", backend=candidate.id)
         response = self._run_command(
             candidate,
             "finalize",
             finalize_request,
             workspace=workspace,
         )
         if not isinstance(response, RenderResult):
             raise_protocol_error(
                 backend=candidate.id,
                 message="finalize operation did not return a RenderResult",
                 details={"received_type": type(response).__name__},
             )
         try:
             response = finalize_request.validate_final_result(response)
         except (TypeError, ValueError) as exc:
             raise_invalid_artifact_error(
                 backend=candidate.id,
                 message=f"finalizer returned an invalid result: {exc}",
                 recovery_command="rerun finalization in a fresh invocation workspace",
                 details={"error_type": type(exc).__name__},
             )
         self._observe("validate", backend=candidate.id)
         validated = self._validator(
             response,
             expected_profile=plan.profile,
             workspace_root=workspace,
         )
         self._validate_planned_duration(
             validated,
             planned_frames=(
                 plan.window.duration_frames
                 if plan.window is not None
                 else plan.total_frames
             ),
             canonical_profile=plan.profile,
             backend=candidate.id,
             label="finalized artifact",
         )
         completed = self.complete_audio(
             validated,
             request=request,
             plan=plan,
             workspace=workspace,
             backend=candidate.id,
         )
         self._validate_planned_duration(
             completed,
             planned_frames=(
                 plan.window.duration_frames
                 if plan.window is not None
                 else plan.total_frames
             ),
             canonical_profile=plan.profile,
             backend=candidate.id,
             label="audio-completed artifact",
         )
         return completed, plan
 
     def complete_audio(
         self,
         result: RenderResult,
         *,
         request: RenderRequest,
         plan: RenderPlan,
         workspace: Path,

exec
/bin/zsh -lc 'rg -n "finalizer alias|direct branch|audio-reactive|engine.*backend|HIGH|MEDIUM" .oracle/checkins/batch-4-r1.md | tail -80' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
20:Prior verdict batch-4.md listed 7 issues (4 HIGH, 3 MEDIUM). All host-fixed.
26:1. **HIGH — single-segment plans bypass the explicit finalizer; audio
34:2. **HIGH — hybrid alias/override routing broken** →
38:3. **HIGH — alias/override lineage discarded on re-resolution** → the service
43:4. **HIGH — legacy remotion fallback drops rejected FFmpeg attempt** →
48:5. **MEDIUM — facade remains concrete and recursive** → extracted the legacy
54:6. **MEDIUM — explicit backend config replaces legacy settings** → the
57:7. **MEDIUM — engine/backend conflict silently prefers backend** → `main()`
58:   raises a ValueError when both `--engine` and `--backend` are supplied.
59:8. **MEDIUM — matrix uses FakeTransport only** → added real-backend
331:   ffmpeg, optimized ffmpeg, audio-reactive, hybrid single + multi) → exactly
525:16:- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.
799:- HIGH — [service.py:1265](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1265) bypasses the explicit finalizer for every single-segment plan. Normalizable profile mismatches fail, and audio completion runs prematurely at line 1219.
801:- HIGH — Hybrid alias/override routing is broken. The resolver returns the resolved backend, but [legacy_hybrid/run.py:758](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/planners/legacy_hybrid/run.py:758) compares it with the unresolved configured ID. Valid aliases and overrides are rejected or skipped.
803:- HIGH — Hybrid renderer/finalizer alias and override lineage is discarded when the service re-resolves emitted target IDs and replaces the planner’s resolution records at [service.py:1169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1169) and [service.py:1235](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1235).
805:- HIGH — Legacy `remotion` fallback provenance drops the rejected FFmpeg attempt. Rejection evidence accumulated at [service.py:532](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:532) is discarded when Remotion succeeds, so the sidecar lacks complete routing/support lineage.
807:- MEDIUM — The facade remains concrete and recursive: it imports backend implementations and retains `_render_hybrid()` with backend branching and recursive rendering at [run.py:355](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:355), contrary to the required neutral facade.
809:- MEDIUM — Explicit backend configuration replaces legacy settings rather than overlaying them at [run.py:580](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:580), silently dropping project/theme/composition values.
811:- MEDIUM — Conflicting `engine` and `backend` inputs silently prefer `backend` at [run.py:645](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:645), bypassing the service’s conflict validation.
813:- MEDIUM — The claimed every-built-in-path matrix uses `FakeTransport`; optimized/audio-reactive settings are not exercised by real backends, and hybrid uses a fixture renderer at [test_service.py:1462](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1462).
818:- HIGH — [service.py:1265](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1265) bypasses the explicit finalizer for every single-segment plan. Normalizable profile mismatches fail, and audio completion runs prematurely at line 1219.
820:- HIGH — Hybrid alias/override routing is broken. The resolver returns the resolved backend, but [legacy_hybrid/run.py:758](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/planners/legacy_hybrid/run.py:758) compares it with the unresolved configured ID. Valid aliases and overrides are rejected or skipped.
822:- HIGH — Hybrid renderer/finalizer alias and override lineage is discarded when the service re-resolves emitted target IDs and replaces the planner’s resolution records at [service.py:1169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1169) and [service.py:1235](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1235).
824:- HIGH — Legacy `remotion` fallback provenance drops the rejected FFmpeg attempt. Rejection evidence accumulated at [service.py:532](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:532) is discarded when Remotion succeeds, so the sidecar lacks complete routing/support lineage.
826:- MEDIUM — The facade remains concrete and recursive: it imports backend implementations and retains `_render_hybrid()` with backend branching and recursive rendering at [run.py:355](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:355), contrary to the required neutral facade.
828:- MEDIUM — Explicit backend configuration replaces legacy settings rather than overlaying them at [run.py:580](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:580), silently dropping project/theme/composition values.
830:- MEDIUM — Conflicting `engine` and `backend` inputs silently prefer `backend` at [run.py:645](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:645), bypassing the service’s conflict validation.
832:- MEDIUM — The claimed every-built-in-path matrix uses `FakeTransport`; optimized/audio-reactive settings are not exercised by real backends, and hybrid uses a fixture renderer at [test_service.py:1462](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1462).
2483:         help="Neutral alias for --engine: legacy selector or qualified backend id.",
2524:+                f"--engine {args.engine!r} and --backend {args.backend!r} "
3587:   247	        help="Neutral alias for --engine: legacy selector or qualified backend id.",
3603:/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '234,360p' && rg -n \"engine.*backend|backend.*engine|conflict|explicit backend|backend_config|alias_chain|override|rejected|single.segment|single_segment|real_ffmpeg|real_hybrid\" tests/core/rendering/test_service.py tests/packs/rendering tests/core/rendering/test_legacy_hybrid.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
3615:tests/packs/rendering/test_legacy_renderer_characterization.py:689:    assert "--engine" in help_text  # the only backend selection surface
3643:tests/packs/rendering/test_ffmpeg_backend.py:435:def test_facade_engine_ffmpeg_delegates_to_backend_seam(tmp_path: Path) -> None:
3647:/bin/zsh -lc "nl -ba tests/core/rendering/test_service.py | sed -n '500,750p;1450,1585p;1960,2105p' && nl -ba tests/packs/rendering/test_render_facade.py | sed -n '1,190p' && rg -n \"conflict; supply|both.*engine|--backend\" tests/packs/rendering/test_render_facade.py tests/packs/rendering/test_legacy_renderer_characterization.py tests/core/rendering/test_output_name.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
3958:  1508	        "ffmpeg-audio-reactive",
4444:     """The audio-reactive specialization is service-side support evidence; the
4481: # audio-reactive early selection
4513:     kept as a named placeholder so the audio-reactive section stays greppable.
4893:     assert "--engine" in help_text  # the only backend selection surface
5083:The legacy engine retains the private backend aliases it historically
6678:         "ffmpeg-audio-reactive",
6989:   380	        supplied = [item for item in (selector, engine, backend) if item is not None]
6995:   386	                message="selector, engine, and backend disagree",
7131:The main fixes are present, but two edge cases need confirmation: finalizer lineage after the final support pass, and whether an explicitly supplied default-valued `--engine remotion` is distinguishable from omission when `--backend` is also present. I’m checking those against the actual DTO/provenance flow now.
7212:/bin/zsh -lc "nl -ba tests/packs/rendering/test_audio_reactive_colour.py | sed -n '130,225p' && rg -n \"audio_reactive|audio-reactive|match_and_validate|specialization\" astrid/packs/rendering/backends/ffmpeg tests/core/rendering/test_service.py | head -100 && nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
7238:   154	    # Dispatch is delegated to RenderService; the audio-reactive specialization
7311:tests/core/rendering/test_service.py:1508:        "ffmpeg-audio-reactive",
7312:astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:1:"""FFmpeg specialization for the audio-reactive-colour timeline element."""
7313:astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:14:EFFECT_ID = "audio-reactive-colour"
7314:astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:15:ADAPTER_ID = "audio-reactive-colour/v1"
7318:astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:391:        prefix="astrid-audio-reactive-colour-", dir=str(out_path.parent)
7323:astrid/packs/rendering/backends/ffmpeg/support.py:322:                "audio-reactive-colour specialization requires exactly one effect clip"
7327:astrid/packs/rendering/backends/ffmpeg/support.py:745:            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
7340:astrid/packs/rendering/backends/ffmpeg/run.py:322:    """Preserve the facade's early audio-reactive FFmpeg specialization."""
7349:astrid/packs/rendering/backends/ffmpeg/run.py:435:            label="Rendered audio-reactive colour video",
7353:astrid/packs/rendering/backends/ffmpeg/run.py:447:            label="Render audio-reactive colour timeline with FFmpeg",
7359:astrid/packs/rendering/backends/ffmpeg/run.py:553:                "audio-reactive support evidence did not produce a specialization spec"
7954:   745	            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
8052:   553	                "audio-reactive support evidence did not produce a specialization spec"
8401:- HIGH — Finalizer alias/override lineage is merged at [service.py:1270](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1270), then discarded when `_finish_plan()` rebuilds the resolution from canonical evidence at [service.py:1354](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1354).
8403:- HIGH — `RenderService(finalizer_id=...)` pins an executable finalizer for direct renders at [service.py:1644](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1644), but the direct branch never invokes `_finish_plan()` or that finalizer ([service.py:448](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:448)).
8405:- MEDIUM — Conflicting explicit `--engine remotion --backend ffmpeg` is still accepted because `remotion` is also the argparse default and explicit presence is not tracked ([run.py:286](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:286)).
8407:- MEDIUM — Real-service audio-reactive coverage remains absent. The audio-reactive matrix case still uses `FakeTransport` ([test_service.py:1492](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1492)); the new real tests cover ordinary/whole-media FFmpeg and hybrid only.
8412:- HIGH — Finalizer alias/override lineage is merged at [service.py:1270](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1270), then discarded when `_finish_plan()` rebuilds the resolution from canonical evidence at [service.py:1354](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1354).
8414:- HIGH — `RenderService(finalizer_id=...)` pins an executable finalizer for direct renders at [service.py:1644](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1644), but the direct branch never invokes `_finish_plan()` or that finalizer ([service.py:448](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:448)).
8416:- MEDIUM — Conflicting explicit `--engine remotion --backend ffmpeg` is still accepted because `remotion` is also the argparse default and explicit presence is not tracked ([run.py:286](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:286)).
8418:- MEDIUM — Real-service audio-reactive coverage remains absent. The audio-reactive matrix case still uses `FakeTransport` ([test_service.py:1492](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1492)); the new real tests cover ordinary/whole-media FFmpeg and hybrid only.

codex
The four reported gaps are visibly addressed in the intended locations. I’m now tracing the direct-finalizer path end to end—plan construction, support request, finalizer invocation, artifact lineage, and provenance—to catch regressions not covered by the new assertions.
exec
/bin/zsh -lc "rg -n \"def __init__|finalizer_id|def _direct_plan|def _finalizer_resolution|def complete_audio|artifact_profiles|class RenderPlan|class FinalizerResolution|class RenderResult|FinalizeRequest\" astrid/core/rendering/service.py astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py tests/core/rendering/test_service.py | head -200 && nl -ba astrid/core/rendering/service.py | sed -n '150,370p;1240,1425p;1425,1715p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 226ms:
astrid/core/rendering/provenance.py:192:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:198:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:206:                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
astrid/core/rendering/provenance.py:212:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:223:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:233:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:264:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:269:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:278:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:282:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:404:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:462:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:463:            artifact_profiles,
astrid/core/rendering/contracts.py:74:        "artifact_profiles",
astrid/core/rendering/contracts.py:1199:class FinalizerResolution:
astrid/core/rendering/contracts.py:1361:class RenderPlan:
astrid/core/rendering/contracts.py:1530:class RenderResult:
astrid/core/rendering/contracts.py:1705:class FinalizeRequest:
astrid/core/rendering/contracts.py:1813:    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
astrid/core/rendering/contracts.py:2189:    "FinalizeRequest",
astrid/core/rendering/service.py:31:    FinalizeRequest,
astrid/core/rendering/service.py:150:    def __init__(
astrid/core/rendering/service.py:170:        finalizer_id: str | None = None,
astrid/core/rendering/service.py:207:        self.finalizer_id = finalizer_id
astrid/core/rendering/service.py:521:            artifact_profiles=artifact_lineage,
astrid/core/rendering/service.py:1390:        finalize_request = FinalizeRequest(
astrid/core/rendering/service.py:1461:    def complete_audio(
astrid/core/rendering/service.py:1604:    def _direct_plan(
astrid/core/rendering/service.py:1675:        if self.finalizer_id is not None:
astrid/core/rendering/service.py:1678:                self.finalizer_id,
astrid/core/rendering/service.py:1738:    def _finalizer_resolution(
tests/core/rendering/test_service.py:187:def _finalizer_resolution(
tests/core/rendering/test_service.py:252:    def __init__(self) -> None:
tests/core/rendering/test_service.py:1133:    def __init__(self, pack_root: Path = RAW_FIXTURE_PACK_ROOT) -> None:
tests/core/rendering/test_service.py:1791:    assert len(payload["artifact_profiles"]) == 1
tests/core/rendering/test_service.py:1792:    assert set(payload["artifact_profiles"][0]["attachments"]) == {
tests/core/rendering/test_service.py:1824:    assert len(payload["artifact_profiles"]) == 2
tests/core/rendering/test_service.py:1825:    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
tests/core/rendering/test_service.py:1826:    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}
   150	    def __init__(
   151	        self,
   152	        renderer_registry: RendererRegistry | None = None,
   153	        planner_registry: PlannerRegistry | None = None,
   154	        finalizer_registry: FinalizerRegistry | None = None,
   155	        *,
   156	        registries: tuple[
   157	            RendererRegistry, PlannerRegistry, FinalizerRegistry
   158	        ]
   159	        | None = None,
   160	        project_root: str | Path | None = None,
   161	        extra_pack_roots: tuple[str, ...] = (),
   162	        include_installed: bool = True,
   163	        transport: Any | None = None,
   164	        transport_factory: Callable[[str], Any] = CommandTransport,
   165	        validator: Callable[..., RenderResult] = validate_render_result,
   166	        publisher: Callable[..., Path] = publish_render_result,
   167	        provenance_builder: Callable[..., dict[str, Any]] = assemble_provenance_v2,
   168	        audio_completer: AudioCompleter | None = None,
   169	        stage_observer: StageObserver | None = None,
   170	        finalizer_id: str | None = None,
   171	    ) -> None:
   172	        supplied = (
   173	            renderer_registry,
   174	            planner_registry,
   175	            finalizer_registry,
   176	        )
   177	        if registries is not None and any(item is not None for item in supplied):
   178	            raise ValueError(
   179	                "pass either registries= or individual rendering registries, not both"
   180	            )
   181	        if registries is None:
   182	            if all(item is None for item in supplied):
   183	                registries = load_default_registries(
   184	                    project_root,
   185	                    extra_pack_roots=extra_pack_roots,
   186	                    include_installed=include_installed,
   187	                )
   188	            elif any(item is None for item in supplied):
   189	                raise ValueError("all three rendering registries must be supplied together")
   190	            else:
   191	                registries = supplied  # type: ignore[assignment]
   192	        self.renderers, self.planners, self.finalizers = registries
   193	        self.renderer_registry = self.renderers
   194	        self.planner_registry = self.planners
   195	        self.finalizer_registry = self.finalizers
   196	        self._transport = transport
   197	        self._transport_factory = transport_factory
   198	        self._validator = validator
   199	        self._publisher = publisher
   200	        self._provenance_builder = provenance_builder
   201	        self._audio_completer = audio_completer
   202	        self._stage_observer = stage_observer
   203	        # Direct renders need no executable finalizer.  An embedding host may
   204	        # nevertheless request a registered finalizer identity for direct-plan
   205	        # provenance; otherwise a core no-op resolution is recorded.  Planned
   206	        # renders always use the finalizer pinned by their RenderPlan.
   207	        self.finalizer_id = finalizer_id
   208	
   209	    def render(
   210	        self,
   211	        request: RenderRequest | Mapping[str, Any] | str | Path,
   212	        assets_path: str | Path | None = None,
   213	        out_path: str | Path | None = None,
   214	        *,
   215	        selector: str | None = None,
   216	        engine: str | None = None,
   217	        backend: str | None = None,
   218	        output_path: str | Path | None = None,
   219	        sidecar_path: str | Path | None = None,
   220	        backend_config: Mapping[str, Mapping[str, Any]] | None = None,
   221	        audio: AudioOwnership | str | None = None,
   222	        metadata: Mapping[str, str] | None = None,
   223	        previous_outputs: Iterable[object] = (),
   224	        v1_compatibility: Mapping[str, Any] | None = None,
   225	    ) -> Path:
   226	        """Render either a wire request or a timeline/assets path pair.
   227	
   228	        For a wire request, the second positional argument may be the output
   229	        path.  The path-pair form is a compatibility convenience used by the
   230	        facade while it migrates to constructing :class:`RenderRequest`
   231	        directly.
   232	        """
   233	
   234	        selected = self._one_selector(selector, engine, backend)
   235	        destination = output_path or out_path
   236	        if isinstance(request, (RenderRequest, Mapping)):
   237	            if destination is None and assets_path is not None:
   238	                destination = assets_path
   239	                assets_path = None
   240	            parsed = (
   241	                request
   242	                if isinstance(request, RenderRequest)
   243	                else RenderRequest.from_dict(request)
   244	            )
   245	        else:
   246	            if destination is None:
   247	                raise_protocol_error(
   248	                    backend=_CORE_BACKEND_ID,
   249	                    message="out_path/output_path is required",
   250	                    recovery_command="supply one output path and retry",
   251	                )
   252	            destination_path = Path(destination)
   253	            parsed = RenderRequest.from_dict(
   254	                {
   255	                    "schema_version": SCHEMA_VERSION,
   256	                    "timeline_path": str(Path(request).expanduser().resolve()),
   257	                    "assets_registry_path": (
   258	                        None
   259	                        if assets_path is None
   260	                        else str(Path(assets_path).expanduser().resolve())
   261	                    ),
   262	                    "output_name": destination_path.name,
   263	                    "window": None,
   264	                    "audio": (
   265	                        audio.value if isinstance(audio, AudioOwnership) else audio
   266	                    ),
   267	                    "profile": None,
   268	                    "backend_config": {
   269	                        str(key): dict(value)
   270	                        for key, value in (backend_config or {}).items()
   271	                    },
   272	                    "metadata": dict(metadata or {}),
   273	                }
   274	            )
   275	        if destination is None:
   276	            raise_protocol_error(
   277	                backend=_CORE_BACKEND_ID,
   278	                message="out_path/output_path is required",
   279	                recovery_command="supply one output path and retry",
   280	            )
   281	        return self.render_request(
   282	            parsed,
   283	            selector=selected,
   284	            out_path=destination,
   285	            sidecar_path=sidecar_path,
   286	            previous_outputs=previous_outputs,
   287	            v1_compatibility=v1_compatibility,
   288	        )
   289	
   290	    def render_request(
   291	        self,
   292	        request: RenderRequest | Mapping[str, Any],
   293	        *,
   294	        selector: str | None = None,
   295	        out_path: str | Path,
   296	        sidecar_path: str | Path | None = None,
   297	        previous_outputs: Iterable[object] = (),
   298	        v1_compatibility: Mapping[str, Any] | None = None,
   299	    ) -> Path:
   300	        """Execute the frozen selection lifecycle for one protocol request."""
   301	
   302	        try:
   303	            parsed = (
   304	                request
   305	                if isinstance(request, RenderRequest)
   306	                else RenderRequest.from_dict(request)
   307	            )
   308	            localized = self._absolute_input_paths(parsed)
   309	            # Keep the caller's absolute-but-unresolved spellings for the
   310	            # publication layer's symlink guard.  The private workspace uses
   311	            # the resolved parent so its final move stays on the destination
   312	            # filesystem.
   313	            output = Path(out_path).expanduser().absolute()
   314	            sidecar = Path(
   315	                sidecar_path or f"{output}.provenance.json"
   316	            ).expanduser().absolute()
   317	            if sidecar == output:
   318	                raise_protocol_error(
   319	                    backend=_CORE_BACKEND_ID,
   320	                    message="video and provenance sidecar paths must be different",
   321	                    recovery_command="choose a distinct .provenance.json sidecar path",
   322	                    details={"path": str(output)},
   323	                )
   324	            policy = _translate_legacy_selector(selector)
   325	            self._observe(
   326	                "legacy_translation",
   327	                requested=selector,
   328	                kind=policy.kind,
   329	                targets=list(policy.targets),
   330	                auto_route=policy.auto_route,
   331	            )
   332	            workspace_parent = output.resolve(strict=False).parent
   333	            workspace_parent.mkdir(parents=True, exist_ok=True)
   334	            with TemporaryDirectory(
   335	                prefix=f".{output.name}.render-service-",
   336	                dir=str(workspace_parent),
   337	            ) as workspace_text:
   338	                return self._render_in_workspace(
   339	                    localized,
   340	                    policy=policy,
   341	                    workspace=Path(workspace_text),
   342	                    out_path=output,
   343	                    sidecar_path=sidecar,
   344	                    previous_outputs=tuple(previous_outputs),
   345	                    v1_compatibility=v1_compatibility,
   346	                )
   347	        except RendererException as exc:
   348	            if exc.error.recovery_command is None:
   349	                raise_renderer_error(
   350	                    replace(
   351	                        exc.error,
   352	                        recovery_command=self._default_error_recovery(
   353	                            exc.error.kind
   354	                        ),
   355	                    )
   356	                )
   357	            raise
   358	        except (KeyboardInterrupt, SystemExit):
   359	            raise
   360	        except (TypeError, ValueError) as exc:
   361	            raise_protocol_error(
   362	                backend=_CORE_BACKEND_ID,
   363	                message=f"render service received invalid data: {exc}",
   364	                details={"error_type": type(exc).__name__},
   365	            )
   366	        except BaseException as exc:
   367	            raise_internal_error(
   368	                backend=_CORE_BACKEND_ID,
   369	                message=f"render service failed: {exc or type(exc).__name__}",
   370	                recovery_command="retry the render in a fresh invocation workspace",
  1240	                override=planner_renderer.override or evidence.get("override"),
  1241	                support_decision=report,
  1242	            )
  1243	            normalized_segment = replace(
  1244	                segment,
  1245	                renderer=merged_renderer,
  1246	                input_hashes={
  1247	                    **segment.input_hashes,
  1248	                    **input_hashes,
  1249	                    **materialized_hashes,
  1250	                },
  1251	            )
  1252	            normalized_segments.append(normalized_segment)
  1253	            result = self._invoke_renderer(
  1254	                segment_request,
  1255	                selected=resolved,
  1256	                workspace=workspace,
  1257	                output_name=segment_request.output_name,
  1258	                # Segment renderers may emit a profile that the registered
  1259	                # finalizer must normalize.  The artifact is first validated
  1260	                # against its own declaration; a one-segment exact match is
  1261	                # checked against the plan in _finish_plan, while every
  1262	                # mismatch and every multi-segment plan goes through the
  1263	                # pinned finalizer.
  1264	                expected_profile=None,
  1265	            )
  1266	            completed = self.complete_audio(
  1267	                result,
  1268	                request=segment_request,
  1269	                plan=response,
  1270	                workspace=workspace,
  1271	                backend=candidate.id,
  1272	                # The plan pins an explicit finalizer; segment audio is
  1273	                # deferred to it (single- and multi-segment alike) so a
  1274	                # normalizable profile/audio mismatch cannot fail the segment
  1275	                # before the finalizer can normalize it.
  1276	                defer_to_finalizer=response.finalizer.id != _DIRECT_FINALIZER_ID,
  1277	            )
  1278	            self._validate_segment_duration(
  1279	                completed,
  1280	                segment=segment,
  1281	                canonical_profile=response.profile,
  1282	                backend=candidate.id,
  1283	            )
  1284	            segment_results.append(completed)
  1285	
  1286	        finalizer, finalizer_evidence = self._resolve_candidate(
  1287	            self.finalizers,
  1288	            response.finalizer.id,
  1289	            kind="finalizer",
  1290	            observe=False,
  1291	        )
  1292	        finalizer_resolution = replace(
  1293	            response.finalizer,
  1294	            id=finalizer.id,
  1295	            source_pack=self._source_pack(finalizer, finalizer_evidence),
  1296	            manifest_digest=finalizer.manifest_digest,
  1297	            trust_eligibility=finalizer.eligibility.to_dict(),
  1298	            alias_chain=(
  1299	                response.finalizer.alias_chain
  1300	                or list(finalizer_evidence.get("alias_chain") or [])
  1301	            ),
  1302	            override=response.finalizer.override or finalizer_evidence.get("override"),
  1303	            # The planner's finalizer support_decision names its pre-alias
  1304	            # identity; _finish_plan re-evaluates support for the resolved
  1305	            # finalizer and records the authoritative decision.
  1306	            support_decision=None,
  1307	        )
  1308	        plan = replace(
  1309	            response,
  1310	            request_digest=compute_request_digest(request.to_dict()),
  1311	            requested_policy=policy.requested,
  1312	            planner=planner_resolution,
  1313	            segments=normalized_segments,
  1314	            finalizer=finalizer_resolution,
  1315	        )
  1316	        return plan, segment_results, (finalizer, finalizer_evidence)
  1317	
  1318	    def _finish_plan(
  1319	        self,
  1320	        request: RenderRequest,
  1321	        *,
  1322	        plan: RenderPlan,
  1323	        segment_results: list[RenderResult],
  1324	        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
  1325	        workspace: Path,
  1326	    ) -> tuple[RenderResult, RenderPlan]:
  1327	        candidate, evidence = pinned_finalizer
  1328	        if candidate.id == _DIRECT_FINALIZER_ID:
  1329	            # No executable finalizer pinned: the segment must already match
  1330	            # the canonical plan profile exactly.
  1331	            if len(segment_results) != 1:
  1332	                raise_internal_error(
  1333	                    backend=_CORE_BACKEND_ID,
  1334	                    message="direct finalizer received multiple segments",
  1335	                    recovery_command="select a planner that pins an executable finalizer",
  1336	                    details={"segment_count": len(segment_results)},
  1337	                )
  1338	            result = self._validator(
  1339	                segment_results[0],
  1340	                expected_profile=plan.profile,
  1341	                workspace_root=workspace,
  1342	            )
  1343	            return result, plan
  1344	
  1345	        ownerships = {item.audio_ownership for item in segment_results}
  1346	        if ownerships == {AudioOwnership.PASSTHROUGH}:
  1347	            requested_audio = AudioOwnership.PASSTHROUGH
  1348	        elif plan.profile.has_audio:
  1349	            requested_audio = AudioOwnership.RENDERED
  1350	        else:
  1351	            requested_audio = AudioOwnership.NONE
  1352	        support_audio = (
  1353	            None
  1354	            if requested_audio is AudioOwnership.PASSTHROUGH
  1355	            and plan.profile.has_audio
  1356	            else requested_audio
  1357	        )
  1358	        support_request = RenderRequest(
  1359	            schema_version=SCHEMA_VERSION,
  1360	            timeline_path=request.timeline_path,
  1361	            assets_registry_path=request.assets_registry_path,
  1362	            output_name=request.output_name,
  1363	            audio=support_audio,
  1364	            profile=plan.profile,
  1365	            backend_config=request.backend_config,
  1366	            metadata=request.metadata,
  1367	        )
  1368	        report = self._support(
  1369	            candidate,
  1370	            request=support_request,
  1371	            workspace=workspace,
  1372	            registry=self.finalizers,
  1373	        )
  1374	        if not report.supported:
  1375	            self._unsupported_report(report, registry=self.finalizers)
  1376	        prior_finalizer = plan.finalizer
  1377	        finalizer_resolution = replace(
  1378	            self._finalizer_resolution(
  1379	                candidate,
  1380	                evidence,
  1381	                support=report,
  1382	            ),
  1383	            alias_chain=(
  1384	                prior_finalizer.alias_chain
  1385	                or list(evidence.get("alias_chain") or [])
  1386	            ),
  1387	            override=prior_finalizer.override or evidence.get("override"),
  1388	        )
  1389	        plan = replace(plan, finalizer=finalizer_resolution)
  1390	        finalize_request = FinalizeRequest(
  1391	            schema_version=SCHEMA_VERSION,
  1392	            plan=plan,
  1393	            artifacts=[item.video for item in segment_results],
  1394	            output_name=request.output_name,
  1395	            backend_config={
  1396	                candidate.id: dict(request.backend_config.get(candidate.id, {}))
  1397	            }
  1398	            if candidate.id in request.backend_config
  1399	            else {},
  1400	            metadata=request.metadata,
  1401	        )
  1402	        self._observe("finalize", backend=candidate.id)
  1403	        response = self._run_command(
  1404	            candidate,
  1405	            "finalize",
  1406	            finalize_request,
  1407	            workspace=workspace,
  1408	        )
  1409	        if not isinstance(response, RenderResult):
  1410	            raise_protocol_error(
  1411	                backend=candidate.id,
  1412	                message="finalize operation did not return a RenderResult",
  1413	                details={"received_type": type(response).__name__},
  1414	            )
  1415	        try:
  1416	            response = finalize_request.validate_final_result(response)
  1417	        except (TypeError, ValueError) as exc:
  1418	            raise_invalid_artifact_error(
  1419	                backend=candidate.id,
  1420	                message=f"finalizer returned an invalid result: {exc}",
  1421	                recovery_command="rerun finalization in a fresh invocation workspace",
  1422	                details={"error_type": type(exc).__name__},
  1423	            )
  1424	        self._observe("validate", backend=candidate.id)
  1425	        validated = self._validator(
  1425	        validated = self._validator(
  1426	            response,
  1427	            expected_profile=plan.profile,
  1428	            workspace_root=workspace,
  1429	        )
  1430	        self._validate_planned_duration(
  1431	            validated,
  1432	            planned_frames=(
  1433	                plan.window.duration_frames
  1434	                if plan.window is not None
  1435	                else plan.total_frames
  1436	            ),
  1437	            canonical_profile=plan.profile,
  1438	            backend=candidate.id,
  1439	            label="finalized artifact",
  1440	        )
  1441	        completed = self.complete_audio(
  1442	            validated,
  1443	            request=request,
  1444	            plan=plan,
  1445	            workspace=workspace,
  1446	            backend=candidate.id,
  1447	        )
  1448	        self._validate_planned_duration(
  1449	            completed,
  1450	            planned_frames=(
  1451	                plan.window.duration_frames
  1452	                if plan.window is not None
  1453	                else plan.total_frames
  1454	            ),
  1455	            canonical_profile=plan.profile,
  1456	            backend=candidate.id,
  1457	            label="audio-completed artifact",
  1458	        )
  1459	        return completed, plan
  1460	
  1461	    def complete_audio(
  1462	        self,
  1463	        result: RenderResult,
  1464	        *,
  1465	        request: RenderRequest,
  1466	        plan: RenderPlan,
  1467	        workspace: Path,
  1468	        backend: str = _CORE_BACKEND_ID,
  1469	        defer_to_finalizer: bool = False,
  1470	    ) -> RenderResult:
  1471	        """Apply host-owned completion semantics after renderer validation.
  1472	
  1473	        ``rendered`` is already complete. ``none`` is an intentional
  1474	        visual-only result, while ``passthrough`` must be completed by the
  1475	        embedding host before publication.  A configured completer may also
  1476	        apply an optional compatibility policy to ``none`` without requiring
  1477	        arbitrary renderers to synthesize silence.
  1478	        """
  1479	
  1480	        self._observe("audio", ownership=result.audio_ownership.value)
  1481	        if result.audio_ownership is AudioOwnership.RENDERED:
  1482	            return result
  1483	        if result.video.profile.has_audio:
  1484	            raise_invalid_artifact_error(
  1485	                backend=backend,
  1486	                message=(
  1487	                    f"audio_ownership={result.audio_ownership.value!r} requires "
  1488	                    "a visual-only renderer artifact"
  1489	                ),
  1490	                recovery_command="rerender with an audio/profile pair that agrees",
  1491	            )
  1492	        if defer_to_finalizer:
  1493	            # A registered finalizer owns cross-segment compatibility: it may
  1494	            # synthesize silence for NONE segments or preserve a uniform set
  1495	            # of PASSTHROUGH segments.  Completion, if still necessary, runs
  1496	            # once on the finalized result below.
  1497	            return result
  1498	        if (
  1499	            result.audio_ownership is AudioOwnership.NONE
  1500	            and (
  1501	                plan.profile.has_audio
  1502	                or (
  1503	                    request.profile is not None
  1504	                    and request.profile.has_audio
  1505	                )
  1506	            )
  1507	        ):
  1508	            raise_invalid_artifact_error(
  1509	                backend=backend,
  1510	                message="audio_ownership='none' cannot satisfy a requested audio profile",
  1511	                recovery_command="request passthrough/rendered audio or a visual-only profile",
  1512	            )
  1513	        if self._audio_completer is None:
  1514	            if result.audio_ownership is AudioOwnership.PASSTHROUGH:
  1515	                raise_unsupported_error(
  1516	                    backend=backend,
  1517	                    message=(
  1518	                        "renderer requested passthrough audio but no host audio "
  1519	                        "completer is configured"
  1520	                    ),
  1521	                    recovery_command=(
  1522	                        "configure an audio completer or select a renderer that "
  1523	                        "returns rendered audio"
  1524	                    ),
  1525	                    details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
  1526	                )
  1527	            return result
  1528	        completed = self._audio_completer(
  1529	            result,
  1530	            request=request,
  1531	            plan=plan,
  1532	            workspace=workspace,
  1533	        )
  1534	        if not isinstance(completed, RenderResult):
  1535	            raise_protocol_error(
  1536	                backend=_CORE_BACKEND_ID,
  1537	                message="audio completer did not return a RenderResult",
  1538	                details={"received_type": type(completed).__name__},
  1539	            )
  1540	        if (
  1541	            completed.audio_ownership is AudioOwnership.PASSTHROUGH
  1542	            or (
  1543	                result.audio_ownership is AudioOwnership.PASSTHROUGH
  1544	                and completed.audio_ownership is not AudioOwnership.RENDERED
  1545	            )
  1546	        ):
  1547	            raise_invalid_artifact_error(
  1548	                backend=backend,
  1549	                message="host audio completer left passthrough audio incomplete",
  1550	                recovery_command="return a completed rendered-audio result",
  1551	                details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
  1552	            )
  1553	        missing_attachments = sorted(
  1554	            set(result.attachments) - set(completed.attachments)
  1555	        )
  1556	        changed_attachments = sorted(
  1557	            name
  1558	            for name, attachment in result.attachments.items()
  1559	            if name in completed.attachments
  1560	            and completed.attachments[name] != attachment
  1561	        )
  1562	        if missing_attachments or changed_attachments:
  1563	            raise_invalid_artifact_error(
  1564	                backend=backend,
  1565	                message="host audio completion did not preserve renderer attachments",
  1566	                recovery_command="preserve every named attachment while completing audio",
  1567	                details={
  1568	                    "missing": missing_attachments,
  1569	                    "changed": changed_attachments,
  1570	                },
  1571	            )
  1572	        original_profile = result.video.profile.to_dict()
  1573	        completed_profile = completed.video.profile.to_dict()
  1574	        audio_fields = {
  1575	            "audio_codec",
  1576	            "audio_sample_rate",
  1577	            "audio_channel_layout",
  1578	        }
  1579	        changed_video_fields = sorted(
  1580	            key
  1581	            for key, value in original_profile.items()
  1582	            if key not in audio_fields and completed_profile.get(key) != value
  1583	        )
  1584	        if (
  1585	            changed_video_fields
  1586	            or completed.video.duration_frames != result.video.duration_frames
  1587	        ):
  1588	            raise_invalid_artifact_error(
  1589	                backend=backend,
  1590	                message="host audio completion changed the renderer's video contract",
  1591	                recovery_command="complete audio without changing video profile or duration",
  1592	                details={
  1593	                    "changed_profile_fields": changed_video_fields,
  1594	                    "before_duration_frames": result.video.duration_frames,
  1595	                    "after_duration_frames": completed.video.duration_frames,
  1596	                },
  1597	            )
  1598	        return self._validator(
  1599	            completed,
  1600	            expected_profile=completed.video.profile,
  1601	            workspace_root=workspace,
  1602	        )
  1603	
  1604	    def _direct_plan(
  1605	        self,
  1606	        request: RenderRequest,
  1607	        *,
  1608	        selected: _ResolvedCapability,
  1609	        result: RenderResult,
  1610	        requested_policy: str,
  1611	    ) -> RenderPlan:
  1612	        finalizer_resolution = self._direct_finalizer_resolution()
  1613	        reasons: dict[str, str] = {"0": "direct renderer selection"}
  1614	        if selected.rejected:
  1615	            # A legacy auto-route selector rejects earlier candidates before
  1616	            # the winning backend succeeds; record that rejection evidence so
  1617	            # provenance explains why this backend rendered the timeline.
  1618	            reasons["0"] = (
  1619	                "direct renderer selection; rejected candidates: "
  1620	                + json.dumps(selected.rejected, sort_keys=True)
  1621	            )
  1622	        if request.window is not None:
  1623	            if request.window.fps_rational != result.video.profile.fps_rational:
  1624	                raise_invalid_artifact_error(
  1625	                    backend=selected.candidate.id,
  1626	                    message="renderer artifact FPS does not match the requested frame window",
  1627	                    recovery_command="render the requested window at its declared rational FPS",
  1628	                    details={
  1629	                        "window_fps": list(request.window.fps_rational),
  1630	                        "artifact_fps": list(result.video.profile.fps_rational),
  1631	                    },
  1632	                )
  1633	            segment_window = request.window
  1634	            total_frames = request.window.end_frame
  1635	            plan_window = request.window
  1636	            self._validate_planned_duration(
  1637	                result,
  1638	                planned_frames=request.window.duration_frames,
  1639	                canonical_profile=result.video.profile,
  1640	                backend=selected.candidate.id,
  1641	                label="renderer artifact",
  1642	            )
  1643	        else:
  1644	            segment_window = FrameWindow(
  1645	                start_frame=0,
  1646	                end_frame=result.video.duration_frames,
  1647	                fps_rational=result.video.profile.fps_rational,
  1648	            )
  1649	            total_frames = result.video.duration_frames
  1650	            plan_window = None
  1651	        segment = RenderSegment(
  1652	            window=segment_window,
  1653	            renderer=self._renderer_resolution(selected),
  1654	            input_hashes=self._input_hashes(request),
  1655	        )
  1656	        return RenderPlan(
  1657	            schema_version=SCHEMA_VERSION,
  1658	            request_digest=compute_request_digest(request.to_dict()),
  1659	            requested_policy=requested_policy,
  1660	            planner=PlannerResolution(
  1661	                id=_DIRECT_PLANNER_ID,
  1662	                source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
  1663	                manifest_digest=_DIRECT_PLANNER_DIGEST,
  1664	                trust_eligibility={"eligible": True, "reason": "core direct plan"},
  1665	            ),
  1666	            segments=[segment],
  1667	            finalizer=finalizer_resolution,
  1668	            profile=result.video.profile,
  1669	            total_frames=total_frames,
  1670	            reasons=reasons,
  1671	            window=plan_window,
  1672	        )
  1673	
  1674	    def _direct_finalizer_resolution(self) -> FinalizerResolution:
  1675	        if self.finalizer_id is not None:
  1676	            candidate, evidence = self._resolve_candidate(
  1677	                self.finalizers,
  1678	                self.finalizer_id,
  1679	                kind="finalizer",
  1680	                observe=False,
  1681	            )
  1682	            return self._finalizer_resolution(candidate, evidence, support=None)
  1683	        return FinalizerResolution(
  1684	            id=_DIRECT_FINALIZER_ID,
  1685	            source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
  1686	            manifest_digest=_DIRECT_FINALIZER_DIGEST,
  1687	            trust_eligibility={"eligible": True, "reason": "core direct pass-through"},
  1688	        )
  1689	
  1690	    @staticmethod
  1691	    def _source_pack(
  1692	        candidate: RenderingCandidate[Any], evidence: Mapping[str, Any]
  1693	    ) -> dict[str, Any]:
  1694	        source = {
  1695	            "id": candidate.pack_id,
  1696	            "source_kind": candidate.source_kind,
  1697	            "root": str(candidate.pack_root),
  1698	            "priority_index": candidate.priority_index,
  1699	        }
  1700	        revision = candidate.eligibility.active_revision
  1701	        if revision is not None:
  1702	            source["active_revision"] = revision
  1703	        manifest_path = evidence.get("manifest_path")
  1704	        if isinstance(manifest_path, str):
  1705	            source["manifest_path"] = manifest_path
  1706	        return source
  1707	
  1708	    def _renderer_resolution(
  1709	        self, selected: _ResolvedCapability
  1710	    ) -> RendererResolution:
  1711	        candidate = selected.candidate
  1712	        evidence = selected.evidence
  1713	        return RendererResolution(
  1714	            id=candidate.id,
  1715	            source_pack=self._source_pack(candidate, evidence),

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '180,290p;390,480p' && nl -ba astrid/core/rendering/contracts.py | sed -n '1190,1455p;1530,1605p;1700,1825p' && rg -n \"finalizer_id|direct.*finalizer|alias_chain|override\" tests/core/rendering/test_service.py | head -100" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1148ms:
   180	    lineage: Mapping[str, Any],
   181	    seen: set[str],
   182	) -> None:
   183	    """Reject attachment names repeated across segment artifacts."""
   184	    for name in (lineage.get("attachments") or {}):
   185	        if name in seen:
   186	            raise ValueError(
   187	                f"duplicate attachment name {name!r} across segment artifacts"
   188	            )
   189	        seen.add(name)
   190	
   191	
   192	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
   193	    if value is None:
   194	        value = {}
   195	    if isinstance(value, Mapping):
   196	        if segments and len(segments) > 1:
   197	            raise TypeError(
   198	                "mapping-form artifact_profiles is unordered; use sequence form "
   199	                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
   200	            )
   201	        result: dict[str, Any] = {}
   202	        seen_attachment_names: set[str] = set()
   203	        for key, profile in value.items():
   204	            if not isinstance(key, str):
   205	                raise TypeError(
   206	                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
   207	                )
   208	            path = _require_workspace_relative_path(key, "artifact key")
   209	            if isinstance(profile, VideoArtifact):
   210	                if path != profile.path:
   211	                    raise ValueError(
   212	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
   213	                        f"{profile.path!r}"
   214	                    )
   215	                profile = VideoArtifact.from_dict(
   216	                    _json_safe_mapping(profile.to_dict(), label="artifact")
   217	                )
   218	                lineage = _artifact_lineage(profile)
   219	            elif isinstance(profile, Mapping):
   220	                lineage = _artifact_lineage_from_mapping(profile, key=path)
   221	            else:
   222	                raise TypeError(
   223	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   224	                    "hashed lineage record {profile, sha256, attachments}; "
   225	                    "profile-only entries carry no output hash"
   226	                )
   227	            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
   228	            result[path] = lineage
   229	        # A positive plan must record exactly one hashed artifact per segment.
   230	        if segments:
   231	            if len(result) != len(segments):
   232	                raise ValueError(
   233	                    f"artifact_profiles must record exactly one hashed lineage entry "
   234	                    f"per segment: expected {len(segments)}, got {len(result)}"
   235	                )
   236	        return result
   237	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   238	        lineage: list[dict[str, Any]] = []
   239	        seen_paths: set[str] = set()
   240	        seen_attachment_names: set[str] = set()
   241	        for raw_profile in value:
   242	            if isinstance(raw_profile, VideoArtifact):
   243	                # Reconstruct through the DTO so mutation cannot smuggle
   244	                # invalid paths, profiles, or attachments past validation.
   245	                profile = VideoArtifact.from_dict(
   246	                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
   247	                )
   248	                path = profile.path
   249	                record = _artifact_lineage(profile)
   250	            elif isinstance(raw_profile, Mapping):
   251	                # Already-emitted lineage record: re-validate and re-key by
   252	                # its (validated) path so emitted provenance round-trips.
   253	                raw_path = raw_profile.get("path")
   254	                if not isinstance(raw_path, str) or not raw_path.strip(_ECMA_WHITESPACE):
   255	                    raise ValueError(
   256	                        "emitted lineage record must carry a non-empty string path"
   257	                    )
   258	                record = _artifact_lineage_from_mapping(
   259	                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
   260	                )
   261	                path = record["path"]
   262	            else:
   263	                raise TypeError(
   264	                    "sequence artifact_profiles entries must be VideoArtifacts "
   265	                    "or emitted lineage records"
   266	                )
   267	            if path in seen_paths:
   268	                raise ValueError(
   269	                    f"artifact_profiles sequence contains duplicate path "
   270	                    f"{path!r}"
   271	                )
   272	            seen_paths.add(path)
   273	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   274	            lineage.append(record)
   275	        if segments:
   276	            if len(lineage) != len(segments):
   277	                raise ValueError(
   278	                    f"artifact_profiles must record exactly one hashed lineage entry "
   279	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   280	                )
   281	        return lineage
   282	    raise TypeError("artifact_profiles must be an object or array")
   283	
   284	
   285	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   286	    raw_keys = set(raw)
   287	    allowed = {"profile", "sha256", "attachments", "path"}
   288	    unknown = sorted(raw_keys - allowed)
   289	    if unknown:
   290	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   390	        raise ValueError(
   391	            "v1 compatibility projection is missing always-emitted fields: "
   392	            + ", ".join(missing)
   393	        )
   394	    return compatibility
   395	
   396	
   397	def assemble_provenance_v2(
   398	    *,
   399	    engine: str,
   400	    output: str | Path,
   401	    timeline: str | Path,
   402	    assets_registry: str | Path | None,
   403	    plan: RenderPlan | Mapping[str, Any],
   404	    artifact_profiles: Any = None,
   405	    audio_ownership: AudioOwnership | str | None = None,
   406	    normalization: Sequence[str] = (),
   407	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   408	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   409	    v1_compatibility: Mapping[str, Any] | None = None,
   410	) -> dict[str, Any]:
   411	    """Assemble additive provenance v2 with protected ownership boundaries.
   412	
   413	    ``engine`` is intentionally the legacy request projection. Routing and
   414	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   415	    hybrid invocation cannot collapse multiple renderer identities. Optional
   416	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   417	    any v2 core field.
   418	    """
   419	
   420	    legacy_engine = _require_string(engine, "engine")
   421	    output_path = _require_string(str(output), "output")
   422	    timeline_path = _require_string(str(timeline), "timeline")
   423	    assets_path = None if assets_registry is None else _require_string(
   424	        str(assets_registry), "assets_registry"
   425	    )
   426	    normalized_plan = (
   427	        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
   428	        if isinstance(plan, RenderPlan)
   429	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   430	    )
   431	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   432	    legacy_segments = [
   433	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   434	    ]
   435	    normalized_normalization = [
   436	        _require_string(item, f"normalization[{index}]")
   437	        for index, item in enumerate(normalization)
   438	    ]
   439	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   440	    resolved_policy = _resolved_policy(normalized_plan)
   441	
   442	    payload: dict[str, Any] = {
   443	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   444	        "engine": legacy_engine,
   445	        "output": output_path,
   446	        "timeline": timeline_path,
   447	        "assets_registry": assets_path,
   448	        "request_digest": normalized_plan.request_digest,
   449	        "requested_policy": normalized_plan.requested_policy,
   450	        "resolved_policy": resolved_policy,
   451	        "routing": _routing_record(
   452	            legacy_engine,
   453	            normalized_plan,
   454	            resolved_policy,
   455	        ),
   456	        "planner": normalized_plan.planner.to_dict(),
   457	        # V1-compatible segment projection: flat {engine, from, to} entries,
   458	        # exactly the shape legacy consumers read from `segments`.
   459	        "segments": legacy_segments,
   460	        # Additive normalized v2 segment records; never overwrite v1 fields.
   461	        "segments_v2": normalized_segments,
   462	        "artifact_profiles": _normalize_artifact_profiles(
   463	            artifact_profiles,
   464	            segments=normalized_plan.segments,
   465	        ),
   466	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   467	        "normalization": normalized_normalization,
   468	        "finalizer": normalized_plan.finalizer.to_dict(),
   469	        "attachments": _normalize_attachments(attachments),
   470	        "backend_fragments": validate_backend_fragments(backend_fragments),
   471	    }
   472	    payload.update(compatibility)
   473	    return _json_safe_mapping(payload, label="provenance")
   474	
   475	
   476	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   477	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   478	
   479	    return assemble_provenance_v2(**kwargs)
   480	
  1190	            manifest_digest=data["manifest_digest"],
  1191	            alias_chain=data["alias_chain"],
  1192	            override=data["override"],
  1193	            support_decision=SupportReport.from_dict(data["support_decision"]),
  1194	            trust_eligibility=data["trust_eligibility"],
  1195	        )
  1196	
  1197	
  1198	@dataclass(frozen=True)
  1199	class FinalizerResolution:
  1200	    """Resolved finalizer identity pinned for standalone finalization."""
  1201	
  1202	    id: str
  1203	    source_pack: dict[str, Any]
  1204	    manifest_digest: str
  1205	    alias_chain: list[str] = field(default_factory=list)
  1206	    override: dict[str, Any] | None = None
  1207	    trust_eligibility: dict[str, Any] = field(default_factory=dict)
  1208	    support_decision: SupportReport | None = None
  1209	
  1210	    def __post_init__(self) -> None:
  1211	        object.__setattr__(self, "id", _require_qualified_id(self.id, "finalizer id"))
  1212	        object.__setattr__(
  1213	            self,
  1214	            "source_pack",
  1215	            _json_safe_mapping(self.source_pack, label="finalizer source_pack"),
  1216	        )
  1217	        object.__setattr__(
  1218	            self,
  1219	            "manifest_digest",
  1220	            _require_sha256(self.manifest_digest, "finalizer manifest_digest"),
  1221	        )
  1222	        object.__setattr__(
  1223	            self,
  1224	            "trust_eligibility",
  1225	            _json_safe_mapping(
  1226	                self.trust_eligibility,
  1227	                label="finalizer trust_eligibility",
  1228	            ),
  1229	        )
  1230	        object.__setattr__(
  1231	            self,
  1232	            "alias_chain",
  1233	            [
  1234	                _require_string(item, f"finalizer alias_chain[{index}]")
  1235	                for index, item in enumerate(_require_string_list(self.alias_chain, "finalizer alias_chain"))
  1236	            ],
  1237	        )
  1238	        if self.override is not None:
  1239	            object.__setattr__(
  1240	                self,
  1241	                "override",
  1242	                _require_override(
  1243	                    self.override,
  1244	                    capability_id=self.id,
  1245	                    label="finalizer override",
  1246	                ),
  1247	            )
  1248	        if self.support_decision is not None:
  1249	            support = (
  1250	                self.support_decision
  1251	                if isinstance(self.support_decision, SupportReport)
  1252	                else SupportReport.from_dict(
  1253	                    _require_mapping(
  1254	                        self.support_decision, "finalizer support_decision"
  1255	                    )
  1256	                )
  1257	            )
  1258	            if support.backend != self.id:
  1259	                raise ValueError("finalizer support_decision.backend must match finalizer id")
  1260	            object.__setattr__(self, "support_decision", support)
  1261	
  1262	    def to_dict(self) -> dict[str, Any]:
  1263	        return _json_safe_mapping(
  1264	            {
  1265	                "id": self.id,
  1266	                "source_pack": self.source_pack,
  1267	                "manifest_digest": self.manifest_digest,
  1268	                "alias_chain": list(self.alias_chain),
  1269	                "override": self.override,
  1270	                "trust_eligibility": self.trust_eligibility,
  1271	                "support_decision": self.support_decision,
  1272	            }
  1273	        )
  1274	
  1275	    @classmethod
  1276	    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizerResolution:
  1277	        data = _require_mapping(payload, "finalizer resolution")
  1278	        required = {
  1279	            "id",
  1280	            "source_pack",
  1281	            "manifest_digest",
  1282	            "alias_chain",
  1283	            "override",
  1284	            "trust_eligibility",
  1285	            "support_decision",
  1286	        }
  1287	        _validate_object_keys(data, required=required, allowed=required, label="finalizer resolution")
  1288	        return cls(
  1289	            id=data["id"],
  1290	            source_pack=data["source_pack"],
  1291	            manifest_digest=data["manifest_digest"],
  1292	            alias_chain=data["alias_chain"],
  1293	            override=data["override"],
  1294	            trust_eligibility=data["trust_eligibility"],
  1295	            support_decision=data["support_decision"],
  1296	        )
  1297	
  1298	
  1299	def _normalize_requested_policy(value: Any, label: str = "requested_policy") -> str | dict[str, Any]:
  1300	    if isinstance(value, str):
  1301	        return _require_string(value, label)
  1302	    return _json_safe_mapping(value, label=label)
  1303	
  1304	
  1305	@dataclass(frozen=True)
  1306	class RenderSegment:
  1307	    """One complete temporal window assigned to one qualified backend."""
  1308	
  1309	    window: FrameWindow
  1310	    renderer: RendererResolution
  1311	    input_hashes: dict[str, str] = field(default_factory=dict)
  1312	
  1313	    def __post_init__(self) -> None:
  1314	        object.__setattr__(self, "window", _coerce_window(self.window, "segment window", nullable=False))
  1315	        renderer = (
  1316	            self.renderer
  1317	            if isinstance(self.renderer, RendererResolution)
  1318	            else RendererResolution.from_dict(_require_mapping(self.renderer, "segment renderer"))
  1319	        )
  1320	        object.__setattr__(self, "renderer", renderer)
  1321	        object.__setattr__(
  1322	            self,
  1323	            "input_hashes",
  1324	            _require_hash_mapping(self.input_hashes, "segment input_hashes"),
  1325	        )
  1326	
  1327	    @property
  1328	    def backend(self) -> str:
  1329	        """Compatibility accessor; ``renderer.id`` is authoritative."""
  1330	
  1331	        return self.renderer.id
  1332	
  1333	    @property
  1334	    def support(self) -> SupportReport:
  1335	        """Compatibility accessor; ``renderer.support_decision`` is authoritative."""
  1336	
  1337	        return self.renderer.support_decision
  1338	
  1339	    def to_dict(self) -> dict[str, Any]:
  1340	        return _json_safe_mapping(
  1341	            {
  1342	                "window": self.window,
  1343	                "renderer": self.renderer,
  1344	                "input_hashes": self.input_hashes,
  1345	            }
  1346	        )
  1347	
  1348	    @classmethod
  1349	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderSegment:
  1350	        data = _require_mapping(payload, "render segment")
  1351	        required = {"window", "renderer", "input_hashes"}
  1352	        _validate_object_keys(data, required=required, allowed=required, label="render segment")
  1353	        return cls(
  1354	            window=FrameWindow.from_dict(data["window"]),
  1355	            renderer=RendererResolution.from_dict(data["renderer"]),
  1356	            input_hashes=data["input_hashes"],
  1357	        )
  1358	
  1359	
  1360	@dataclass(frozen=True)
  1361	class RenderPlan:
  1362	    """A deterministic temporal plan plus its explicit finalizer."""
  1363	
  1364	    schema_version: int
  1365	    request_digest: str
  1366	    requested_policy: str | dict[str, Any]
  1367	    planner: PlannerResolution
  1368	    segments: list[RenderSegment]
  1369	    finalizer: FinalizerResolution
  1370	    profile: RenderProfile
  1371	    total_frames: int
  1372	    reasons: dict[str, str]
  1373	    window: FrameWindow | None = None
  1374	
  1375	    def __post_init__(self) -> None:
  1376	        object.__setattr__(
  1377	            self,
  1378	            "schema_version",
  1379	            _require_schema_version(self.schema_version, "render plan"),
  1380	        )
  1381	        object.__setattr__(
  1382	            self,
  1383	            "request_digest",
  1384	            _require_sha256(self.request_digest, "request_digest"),
  1385	        )
  1386	        object.__setattr__(
  1387	            self,
  1388	            "requested_policy",
  1389	            _normalize_requested_policy(self.requested_policy),
  1390	        )
  1391	        planner = (
  1392	            self.planner
  1393	            if isinstance(self.planner, PlannerResolution)
  1394	            else PlannerResolution.from_dict(_require_mapping(self.planner, "planner"))
  1395	        )
  1396	        object.__setattr__(self, "planner", planner)
  1397	        if isinstance(self.segments, (str, bytes)) or not isinstance(self.segments, Sequence):
  1398	            raise TypeError("segments must be an array")
  1399	        segments = [
  1400	            item
  1401	            if isinstance(item, RenderSegment)
  1402	            else RenderSegment.from_dict(_require_mapping(item, f"segments[{index}]"))
  1403	            for index, item in enumerate(self.segments)
  1404	        ]
  1405	        object.__setattr__(self, "segments", segments)
  1406	        finalizer = (
  1407	            self.finalizer
  1408	            if isinstance(self.finalizer, FinalizerResolution)
  1409	            else FinalizerResolution.from_dict(_require_mapping(self.finalizer, "finalizer"))
  1410	        )
  1411	        object.__setattr__(self, "finalizer", finalizer)
  1412	        profile = _coerce_profile(self.profile, "plan profile", nullable=False)
  1413	        object.__setattr__(self, "profile", profile)
  1414	        total_frames = _require_int(self.total_frames, "total_frames", minimum=0)
  1415	        object.__setattr__(self, "total_frames", total_frames)
  1416	        window = _coerce_window(self.window, "plan window", nullable=True)
  1417	        object.__setattr__(self, "window", window)
  1418	        if window is not None:
  1419	            if window.fps_rational != profile.fps_rational:
  1420	                raise ValueError("plan window FPS must exactly match the canonical profile FPS")
  1421	            if window.end_frame > total_frames:
  1422	                raise ValueError("plan window must not extend beyond total_frames")
  1423	        if total_frames == 0:
  1424	            if window is not None or segments:
  1425	                raise ValueError("a zero-frame plan must have no window or segments")
  1426	        else:
  1427	            if not segments:
  1428	                raise ValueError("a positive-frame plan must contain at least one segment")
  1429	            target_start = window.start_frame if window is not None else 0
  1430	            target_end = window.end_frame if window is not None else total_frames
  1431	            expected_start = target_start
  1432	            for index, segment in enumerate(segments):
  1433	                if segment.window.fps_rational != profile.fps_rational:
  1434	                    raise ValueError(
  1435	                        f"segments[{index}] FPS must exactly match the canonical profile FPS"
  1436	                    )
  1437	                actual_start = segment.window.start_frame
  1438	                if actual_start != expected_start:
  1439	                    relation = "overlaps or is out of order" if actual_start < expected_start else "leaves a gap"
  1440	                    raise ValueError(f"segments[{index}] {relation} at frame {expected_start}")
  1441	                if segment.window.end_frame > target_end:
  1442	                    raise ValueError(f"segments[{index}] extends beyond the plan target window")
  1443	                expected_start = segment.window.end_frame
  1444	            if expected_start != target_end:
  1445	                raise ValueError("plan segments leave a trailing gap")
  1446	        reasons = _require_string_mapping(self.reasons, "reasons")
  1447	        expected_reason_keys = {str(index) for index in range(len(segments))}
  1448	        if set(reasons) != expected_reason_keys:
  1449	            raise ValueError(
  1450	                "plan reasons must contain exactly one entry per segment, keyed by zero-based index"
  1451	            )
  1452	        object.__setattr__(self, "reasons", reasons)
  1453	
  1454	    def to_dict(self) -> dict[str, Any]:
  1455	        return _json_safe_mapping(
  1530	class RenderResult:
  1531	    """Successful renderer/finalizer result written to the authoritative path."""
  1532	
  1533	    schema_version: int
  1534	    video: VideoArtifact
  1535	    audio_ownership: AudioOwnership
  1536	    backend_fragments: dict[str, dict[str, Any]] = field(default_factory=dict)
  1537	    normalization: list[str] = field(default_factory=list)
  1538	    logs: list[str] = field(default_factory=list)
  1539	    metadata: dict[str, str] = field(default_factory=dict)
  1540	
  1541	    def __post_init__(self) -> None:
  1542	        version = _require_schema_version(self.schema_version, "render result")
  1543	        video = (
  1544	            self.video
  1545	            if isinstance(self.video, VideoArtifact)
  1546	            else VideoArtifact.from_dict(_require_mapping(self.video, "video"))
  1547	        )
  1548	        ownership = _coerce_audio_ownership(
  1549	            self.audio_ownership,
  1550	            "audio_ownership",
  1551	            nullable=False,
  1552	        )
  1553	        if video.audio is None or video.audio != ownership:
  1554	            raise ValueError("video.audio must be present and match result audio_ownership")
  1555	        object.__setattr__(self, "schema_version", version)
  1556	        object.__setattr__(self, "video", video)
  1557	        object.__setattr__(self, "backend_fragments", _validate_backend_fragments(self.backend_fragments))
  1558	        object.__setattr__(self, "audio_ownership", ownership)
  1559	        object.__setattr__(
  1560	            self,
  1561	            "normalization",
  1562	            _require_string_list(self.normalization, "normalization"),
  1563	        )
  1564	        object.__setattr__(self, "logs", _require_string_list(self.logs, "logs"))
  1565	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
  1566	
  1567	    @property
  1568	    def attachments(self) -> dict[str, Attachment]:
  1569	        """The sole authoritative attachment map, owned by the primary video."""
  1570	
  1571	        return self.video.attachments
  1572	
  1573	    def to_dict(self) -> dict[str, Any]:
  1574	        return _json_safe_mapping(
  1575	            {
  1576	                "schema_version": self.schema_version,
  1577	                "video": self.video,
  1578	                "backend_fragments": self.backend_fragments,
  1579	                "audio_ownership": self.audio_ownership,
  1580	                "normalization": self.normalization,
  1581	                "logs": self.logs,
  1582	                "metadata": self.metadata,
  1583	            }
  1584	        )
  1585	
  1586	    @classmethod
  1587	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderResult:
  1588	        try:
  1589	            data = _require_mapping(payload, "render result")
  1590	            allowed = set(RENDER_RESULT_CORE_KEYS)
  1591	            _validate_object_keys(
  1592	                data,
  1593	                required={"schema_version", "video", "audio_ownership"},
  1594	                allowed=allowed,
  1595	                label="render result",
  1596	            )
  1597	            version = _require_schema_version(data["schema_version"], "render result")
  1598	            return cls(
  1599	                schema_version=version,
  1600	                video=VideoArtifact.from_dict(data["video"]),
  1601	                audio_ownership=data["audio_ownership"],
  1602	                backend_fragments=data.get("backend_fragments", {}),
  1603	                normalization=data.get("normalization", []),
  1604	                logs=data.get("logs", []),
  1605	                metadata=data.get("metadata", {}),
  1700	                details={"error_type": type(exc).__name__},
  1701	            )
  1702	
  1703	
  1704	@dataclass(frozen=True)
  1705	class FinalizeRequest:
  1706	    """Wire request consumed by the ``finalize`` operation."""
  1707	
  1708	    schema_version: int
  1709	    plan: RenderPlan
  1710	    artifacts: list[VideoArtifact]
  1711	    output_name: str
  1712	    backend_config: BackendConfig = field(default_factory=dict)
  1713	    metadata: dict[str, str] = field(default_factory=dict)
  1714	
  1715	    def __post_init__(self) -> None:
  1716	        version = _require_schema_version(self.schema_version, "finalize request")
  1717	        plan = (
  1718	            self.plan
  1719	            if isinstance(self.plan, RenderPlan)
  1720	            else RenderPlan.from_dict(_require_mapping(self.plan, "plan"))
  1721	        )
  1722	        if isinstance(self.artifacts, (str, bytes)) or not isinstance(self.artifacts, Sequence):
  1723	            raise TypeError("artifacts must be an array")
  1724	        artifacts = [
  1725	            artifact
  1726	            if isinstance(artifact, VideoArtifact)
  1727	            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
  1728	            for index, artifact in enumerate(self.artifacts)
  1729	        ]
  1730	        if len(artifacts) != len(plan.segments):
  1731	            raise ValueError("finalize artifacts must correspond one-for-one with plan segments")
  1732	        if plan.total_frames == 0:
  1733	            raise ValueError("an empty render plan must not be finalized")
  1734	        attachment_names: set[str] = set()
  1735	        for index, artifact in enumerate(artifacts):
  1736	            duplicates = sorted(attachment_names & set(artifact.attachments))
  1737	            if duplicates:
  1738	                raise ValueError(
  1739	                    "duplicate attachment names across segment artifacts at "
  1740	                    f"artifacts[{index}]: {', '.join(duplicates)}"
  1741	                )
  1742	            attachment_names.update(artifact.attachments)
  1743	        output_name = _require_string(self.output_name, "output_name")
  1744	        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
  1745	            raise ValueError("output_name must be a portable basename without path separators")
  1746	        object.__setattr__(self, "schema_version", version)
  1747	        object.__setattr__(self, "plan", plan)
  1748	        object.__setattr__(self, "artifacts", artifacts)
  1749	        object.__setattr__(self, "output_name", output_name)
  1750	        backend_config = _coerce_namespaced_backend_config(
  1751	            self.backend_config,
  1752	            "backend_config",
  1753	        )
  1754	        unexpected_config = sorted(set(backend_config) - {plan.finalizer.id})
  1755	        if unexpected_config:
  1756	            raise ValueError(
  1757	                "finalize backend_config may contain only the selected finalizer namespace "
  1758	                f"{plan.finalizer.id!r}"
  1759	            )
  1760	        object.__setattr__(self, "backend_config", backend_config)
  1761	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
  1762	
  1763	    @property
  1764	    def expected_attachments(self) -> dict[str, Attachment]:
  1765	        """Return the globally unique attachments a finalizer must preserve."""
  1766	
  1767	        return {
  1768	            name: attachment
  1769	            for artifact in self.artifacts
  1770	            for name, attachment in artifact.attachments.items()
  1771	        }
  1772	
  1773	    def validate_final_result(
  1774	        self,
  1775	        result: RenderResult | Mapping[str, Any],
  1776	    ) -> RenderResult:
  1777	        """Validate attachment preservation on a standalone finalizer response.
  1778	
  1779	        Finalizers may add new attachments, but every input attachment must be
  1780	        present under the same name with the exact same descriptor and digest.
  1781	        """
  1782	
  1783	        final_result = (
  1784	            result
  1785	            if isinstance(result, RenderResult)
  1786	            else RenderResult.from_dict(_require_mapping(result, "final result"))
  1787	        )
  1788	        missing = sorted(set(self.expected_attachments) - set(final_result.attachments))
  1789	        if missing:
  1790	            raise ValueError("finalizer dropped attachments: " + ", ".join(missing))
  1791	        changed = sorted(
  1792	            name
  1793	            for name, expected in self.expected_attachments.items()
  1794	            if final_result.attachments[name] != expected
  1795	        )
  1796	        if changed:
  1797	            raise ValueError("finalizer changed attachments: " + ", ".join(changed))
  1798	        return final_result
  1799	
  1800	    def to_dict(self) -> dict[str, Any]:
  1801	        return _json_safe_mapping(
  1802	            {
  1803	                "schema_version": self.schema_version,
  1804	                "plan": self.plan,
  1805	                "artifacts": self.artifacts,
  1806	                "output_name": self.output_name,
  1807	                "backend_config": self.backend_config,
  1808	                "metadata": self.metadata,
  1809	            }
  1810	        )
  1811	
  1812	    @classmethod
  1813	    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
  1814	        try:
  1815	            data = _require_mapping(payload, "finalize request")
  1816	            allowed = {
  1817	                "schema_version",
  1818	                "plan",
  1819	                "artifacts",
  1820	                "output_name",
  1821	                "backend_config",
  1822	                "metadata",
  1823	            }
  1824	            _validate_object_keys(
  1825	                data,
15:from astrid.core.pack.override import OverrideStore
170:        alias_chain=[],
171:        override=None,
460:        "override",
491:def test_direct_renderer_does_not_require_an_executable_finalizer(
689:def test_alias_then_override_changes_resolved_winner(tmp_path: Path) -> None:
692:    overrides = OverrideStore(tmp_path / "override-project")
693:    overrides.set_override("renderer", "acme.original", "acme.winner")
697:        override_store=overrides,
715:    assert resolution["alias_chain"] == ["acme.alias", "acme.original"]
716:    assert resolution["override"] == {
996:        "theme_overrides": {
1355:def test_alias_and_override_to_trust_denied_only_target_is_structured(
1360:    overrides = OverrideStore(tmp_path / "override-project")
1361:    overrides.set_override("renderer", "acme.original", "acme.denied")
1365:        override_store=overrides,
1909:                "theme_overrides": {
2100:                "theme_overrides": {

exec
/bin/zsh -lc "git diff --unified=20 98f4edea..907423f2 -- tests/core/rendering/test_service.py | sed -n '1,260p' && nl -ba tests/core/rendering/test_service.py | sed -n '430,560p;620,780p;1680,1850p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1194ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_service.py b/tests/core/rendering/test_service.py
index c1c327b6..67c15345 100644
--- a/tests/core/rendering/test_service.py
+++ b/tests/core/rendering/test_service.py
@@ -2049,20 +2049,133 @@ def test_real_hybrid_plans_assigns_ffmpeg_and_finalizes_through_service(
 
     service.render_request(
         replace(
             _request(tmp_path),
             timeline_path=str(timeline_path),
             assets_registry_path=str(assets_path),
         ),
         selector="hybrid",
         out_path=output,
     )
 
     assert output.is_file()
     assert output.stat().st_size > 0
     sidecars = list(tmp_path.glob("*.provenance.json"))
     assert sidecars == [Path(f"{output}.provenance.json")]
     payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
     assert payload["routing"]["requested_engine"] == "hybrid"
     resolved = payload["routing"]["resolved_policy"]
     assert resolved["planner"] == "rendering.legacy_hybrid"
     assert resolved["finalizer"] == "rendering.ffmpeg-finalizer"
+
+
+def _real_audio_reactive_inputs(tmp_path: Path) -> tuple[Path, Path]:
+    """A two-clip timeline the strict FFmpeg backend renders through its
+    audio-reactive colour specialization (real AAC audio source)."""
+    root = tmp_path / "reactive"
+    root.mkdir(exist_ok=True)
+    audio_path = root / "tone.wav"
+    subprocess.run(
+        [
+            "ffmpeg",
+            "-hide_banner",
+            "-loglevel",
+            "error",
+            "-y",
+            "-f",
+            "lavfi",
+            "-i",
+            "sine=frequency=440:sample_rate=48000:duration=0.5",
+            str(audio_path),
+        ],
+        check=True,
+        capture_output=True,
+        text=True,
+    )
+    timeline_path = root / "timeline.json"
+    assets_path = root / "assets.json"
+    timeline_path.write_text(
+        json.dumps(
+            {
+                "theme": "banodoco-default",
+                "theme_overrides": {
+                    "visual": {"canvas": {"width": 640, "height": 360, "fps": 48}}
+                },
+                "tracks": [
+                    {"id": "colour", "kind": "visual", "label": "Colour"},
+                    {"id": "audio", "kind": "audio", "label": "Audio"},
+                ],
+                "clips": [
+                    {
+                        "id": "colour_map",
+                        "at": 0,
+                        "track": "colour",
+                        "clipType": "audio-reactive-colour",
+                        "hold": 0.5,
+                        "params": {
+                            "schemaVersion": 1,
+                            "initialColor": "#102030",
+                            "events": [
+                                {"id": "a", "frame": 3, "color": "#D47795"},
+                                {"id": "b", "frame": 8, "color": "#26A7D0"},
+                                {"id": "c", "frame": 17, "color": "#B59432"},
+                            ],
+                        },
+                    },
+                    {
+                        "id": "source_audio",
+                        "at": 0,
+                        "track": "audio",
+                        "clipType": "media",
+                        "asset": "audio",
+                        "from": 0,
+                        "to": 0.5,
+                    },
+                ],
+            }
+        ),
+        encoding="utf-8",
+    )
+    assets_path.write_text(
+        json.dumps(
+            {
+                "assets": {
+                    "audio": {
+                        "file": str(audio_path),
+                        "type": "audio/wav",
+                        "duration": 0.5,
+                    }
+                }
+            }
+        ),
+        encoding="utf-8",
+    )
+    return timeline_path, assets_path
+
+
+def test_real_ffmpeg_audio_reactive_through_generic_service(
+    tmp_path: Path,
+) -> None:
+    """The service drives the real FFmpeg backend through its audio-reactive
+    colour specialization end to end (no fake transport)."""
+    _require_ffmpeg()
+    timeline_path, assets_path = _real_audio_reactive_inputs(tmp_path)
+    service = _real_service(tmp_path)
+    output = tmp_path / "real-reactive.mp4"
+
+    service.render_request(
+        replace(
+            _request(tmp_path),
+            timeline_path=str(timeline_path),
+            assets_registry_path=str(assets_path),
+        ),
+        selector="rendering.ffmpeg",
+        out_path=output,
+    )
+
+    assert output.is_file()
+    assert output.stat().st_size > 0
+    sidecars = list(tmp_path.glob("*.provenance.json"))
+    assert sidecars == [Path(f"{output}.provenance.json")]
+    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
+    assert payload["routing"]["requested_engine"] == "rendering.ffmpeg"
+    assert payload["audio_ownership"] == "rendered"
   430	        calls.append("validator")
   431	        return result
   432	
   433	    def publish(*args: Any, **kwargs: Any) -> Path:
   434	        calls.append("publisher")
   435	        return publish_render_result(*args, **kwargs)
   436	
   437	    service = _service(
   438	        tmp_path,
   439	        transport,
   440	        stage_observer=lambda stage, _details: calls.append(stage),
   441	        validator=validate,
   442	        publisher=publish,
   443	    )
   444	    output = tmp_path / "published" / "video.mp4"
   445	
   446	    result = service.render_request(
   447	        _request(tmp_path),
   448	        selector="rendering.remotion",
   449	        out_path=output,
   450	    )
   451	
   452	    assert result == output
   453	    assert transport.calls == [
   454	        ("support", "rendering.remotion"),
   455	        ("render", "rendering.remotion"),
   456	    ]
   457	    assert calls == [
   458	        "legacy_translation",
   459	        "alias",
   460	        "override",
   461	        "winner",
   462	        "eligibility",
   463	        "support",
   464	        "invoke",
   465	        "validate",
   466	        "validator",
   467	        "audio",
   468	        "publish",
   469	        "publisher",
   470	    ]
   471	    assert output.is_file()
   472	    assert Path(f"{output}.provenance.json").is_file()
   473	
   474	
   475	def test_qualified_ffmpeg_is_strict(tmp_path: Path) -> None:
   476	    transport = FakeTransport()
   477	    service = _service(tmp_path, transport)
   478	
   479	    service.render_request(
   480	        _request(tmp_path),
   481	        selector="rendering.ffmpeg",
   482	        out_path=tmp_path / "strict.mp4",
   483	    )
   484	
   485	    assert transport.calls == [
   486	        ("support", "rendering.ffmpeg"),
   487	        ("render", "rendering.ffmpeg"),
   488	    ]
   489	
   490	
   491	def test_direct_renderer_does_not_require_an_executable_finalizer(
   492	    tmp_path: Path,
   493	) -> None:
   494	    transport = FakeTransport()
   495	    renderers = RendererRegistry(
   496	        [_candidate(tmp_path, "fixture.direct", "renderer")]
   497	    )
   498	    service = RenderService(
   499	        registries=(renderers, PlannerRegistry(), FinalizerRegistry()),
   500	        transport=transport,
   501	        validator=lambda result, **_kwargs: result,
   502	    )
   503	
   504	    output = service.render_request(
   505	        _request(tmp_path),
   506	        selector="fixture.direct",
   507	        out_path=tmp_path / "direct.mp4",
   508	    )
   509	
   510	    assert output.is_file()
   511	    assert transport.calls == [
   512	        ("support", "fixture.direct"),
   513	        ("render", "fixture.direct"),
   514	    ]
   515	
   516	
   517	def test_legacy_remotion_auto_routes_supported_media_to_ffmpeg_with_warning(
   518	    tmp_path: Path,
   519	) -> None:
   520	    transport = FakeTransport()
   521	    service = _service(tmp_path, transport)
   522	
   523	    with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
   524	        service.render_request(
   525	            _request(tmp_path),
   526	            selector="remotion",
   527	            out_path=tmp_path / "legacy-remotion.mp4",
   528	        )
   529	
   530	    assert ("render", "rendering.ffmpeg") in transport.calls
   531	    assert ("render", "rendering.remotion") not in transport.calls
   532	
   533	
   534	def test_legacy_remotion_falls_back_when_ffmpeg_declines_support(
   535	    tmp_path: Path,
   536	) -> None:
   537	    transport = FakeTransport()
   538	    transport.support["rendering.ffmpeg"] = _support(
   539	        "rendering.ffmpeg",
   540	        supported=False,
   541	        alternatives=["rendering.remotion"],
   542	    )
   543	    service = _service(tmp_path, transport)
   544	
   545	    service.render_request(
   546	        _request(tmp_path),
   547	        selector="remotion",
   548	        out_path=tmp_path / "legacy-remotion-fallback.mp4",
   549	    )
   550	
   551	    assert transport.calls == [
   552	        ("support", "rendering.ffmpeg"),
   553	        ("support", "rendering.remotion"),
   554	        ("render", "rendering.remotion"),
   555	    ]
   556	    payload = _sidecar(tmp_path / "legacy-remotion-fallback.mp4")
   557	    routing = payload["routing"]
   558	    reason = routing["segment_reasons"]["0"]
   559	    assert "rendering.ffmpeg" in reason
   560	    assert "rejected" in reason
   620	            )
   621	        ]
   622	    )
   623	    planners = PlannerRegistry(
   624	        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
   625	    )
   626	    finalizers = FinalizerRegistry(
   627	        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
   628	    )
   629	    service = RenderService(
   630	        registries=(renderers, planners, finalizers),
   631	        transport=transport,
   632	        validator=lambda result, **_kwargs: result,
   633	    )
   634	    output = tmp_path / "materialized-window.mp4"
   635	    request = _request(tmp_path)
   636	
   637	    service.render_request(request, selector="hybrid", out_path=output)
   638	
   639	    renderer_payloads = [
   640	        payload
   641	        for verb, backend, payload in transport.payloads
   642	        if backend == "fixture.full" and verb in {"support", "render"}
   643	    ]
   644	    assert len(renderer_payloads) == 2
   645	    assert all(payload["window"] is None for payload in renderer_payloads)
   646	    assert all(
   647	        payload["timeline_path"] != request.timeline_path
   648	        for payload in renderer_payloads
   649	    )
   650	    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
   651	    assert "materialized_timeline" in sidecar["segments_v2"][0]["input_hashes"]
   652	
   653	
   654	def test_planned_segment_duration_mismatch_is_rejected(tmp_path: Path) -> None:
   655	    transport = FakeTransport()
   656	    transport.plan = _plan("fixture.window")
   657	    transport.render_frames["fixture.window"] = 3
   658	    service = _service(
   659	        tmp_path,
   660	        transport,
   661	        renderer_ids=("fixture.window",),
   662	        planner_ids=("rendering.legacy_hybrid",),
   663	    )
   664	    output = tmp_path / "wrong-duration.mp4"
   665	
   666	    with pytest.raises(RendererInvalidArtifactError, match="planned frame window"):
   667	        service.render_request(_request(tmp_path), selector="hybrid", out_path=output)
   668	
   669	    assert not output.exists()
   670	    assert not list(tmp_path.glob(".wrong-duration.mp4.render-service-*"))
   671	
   672	
   673	def test_unknown_backend_is_structured_and_lists_alternatives(tmp_path: Path) -> None:
   674	    transport = FakeTransport()
   675	    service = _service(tmp_path, transport)
   676	
   677	    with pytest.raises(RendererUnsupportedError) as caught:
   678	        service.render_request(
   679	            _request(tmp_path),
   680	            selector="missing.renderer",
   681	            out_path=tmp_path / "missing.mp4",
   682	        )
   683	
   684	    assert caught.value.error.kind == "unsupported"
   685	    assert "rendering.remotion" in caught.value.error.details["alternatives"]
   686	    assert caught.value.error.recovery_command
   687	
   688	
   689	def test_alias_then_override_changes_resolved_winner(tmp_path: Path) -> None:
   690	    alias = AliasResolver()
   691	    alias.register_alias("acme.alias", "acme.original")
   692	    overrides = OverrideStore(tmp_path / "override-project")
   693	    overrides.set_override("renderer", "acme.original", "acme.winner")
   694	    renderers = RendererRegistry(
   695	        [_candidate(tmp_path, "acme.winner", "renderer")],
   696	        alias_resolver=alias,
   697	        override_store=overrides,
   698	    )
   699	    transport = FakeTransport()
   700	    service = _service(
   701	        tmp_path,
   702	        transport,
   703	        renderer_ids=(),
   704	        renderer_registry=renderers,
   705	    )
   706	    output = tmp_path / "alias.mp4"
   707	
   708	    service.render_request(
   709	        _request(tmp_path), selector="acme.alias", out_path=output
   710	    )
   711	
   712	    assert ("render", "acme.winner") in transport.calls
   713	    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
   714	    resolution = sidecar["segments_v2"][0]["renderer"]
   715	    assert resolution["alias_chain"] == ["acme.alias", "acme.original"]
   716	    assert resolution["override"] == {
   717	        "from": "acme.original",
   718	        "to": "acme.winner",
   719	    }
   720	
   721	
   722	def test_execution_ineligible_candidate_is_denied(tmp_path: Path) -> None:
   723	    renderers = RendererRegistry(
   724	        [_candidate(tmp_path, "denied.renderer", "renderer", eligible=False)]
   725	    )
   726	    transport = FakeTransport()
   727	    service = _service(
   728	        tmp_path,
   729	        transport,
   730	        renderer_ids=(),
   731	        renderer_registry=renderers,
   732	    )
   733	
   734	    with pytest.raises(RendererUnsupportedError) as caught:
   735	        service.render_request(
   736	            _request(tmp_path),
   737	            selector="denied.renderer",
   738	            out_path=tmp_path / "denied.mp4",
   739	        )
   740	
   741	    registry_error = caught.value.error.details["registry_error"]
   742	    assert registry_error["code"] == "execution_ineligible"
   743	    assert transport.calls == []
   744	
   745	
   746	def test_unsupported_support_report_is_structured_with_reported_alternative(
   747	    tmp_path: Path,
   748	) -> None:
   749	    transport = FakeTransport()
   750	    transport.support["rendering.ffmpeg"] = _support(
   751	        "rendering.ffmpeg",
   752	        supported=False,
   753	        alternatives=["rendering.remotion"],
   754	    )
   755	    service = _service(tmp_path, transport)
   756	
   757	    with pytest.raises(RendererUnsupportedError) as caught:
   758	        service.render_request(
   759	            _request(tmp_path),
   760	            selector="rendering.ffmpeg",
   761	            out_path=tmp_path / "unsupported.mp4",
   762	        )
   763	
   764	    assert caught.value.error.details["alternatives"] == ["rendering.remotion"]
   765	    assert caught.value.error.details["reasons"] == [
   766	        "fixture timeline is unsupported"
   767	    ]
   768	
   769	
   770	def test_renderer_without_support_operation_fails_closed_on_missing_hints(
   771	    tmp_path: Path,
   772	) -> None:
   773	    renderers = RendererRegistry(
   774	        [
   775	            _candidate(
   776	                tmp_path,
   777	                "fixture.static",
   778	                "renderer",
   779	                operations=("render",),
   780	                capabilities={},
  1680	
  1681	    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
  1682	        return replace(
  1683	            result,
  1684	            video=replace(
  1685	                result.video,
  1686	                profile=_profile(audio=True),
  1687	                audio=AudioOwnership.RENDERED,
  1688	            ),
  1689	            audio_ownership=AudioOwnership.RENDERED,
  1690	        )
  1691	
  1692	    if plan_segments is not None:
  1693	        transport.plan = _plan("fixture.window", segment_frames=plan_segments)
  1694	        service = _service(
  1695	            tmp_path,
  1696	            transport,
  1697	            renderer_ids=("fixture.window",),
  1698	            planner_ids=("rendering.legacy_hybrid",),
  1699	            audio_completer=audio_completer if completer else None,
  1700	        )
  1701	        # A pinned planner finalizer completes audio for hybrid plans; the
  1702	        # fixture finalizer must honor the ownership the request asked for.
  1703	        transport.finalize_ownership = ownership
  1704	    else:
  1705	        service = _service(
  1706	            tmp_path,
  1707	            transport,
  1708	            audio_completer=audio_completer if completer else None,
  1709	        )
  1710	    output = tmp_path / f"audio-{ownership.value}.mp4"
  1711	
  1712	    service.render_request(
  1713	        replace(_request(tmp_path), audio=ownership),
  1714	        selector=selector,
  1715	        out_path=output,
  1716	    )
  1717	
  1718	    payload = _sidecar(output)
  1719	    assert payload["audio_ownership"] == expected.value
  1720	    assert payload["routing"]["requested_engine"] == (
  1721	        "hybrid" if plan_segments is not None else selector
  1722	    )
  1723	
  1724	
  1725	def test_finalizer_failure_removes_workspace_and_commits_nothing(
  1726	    tmp_path: Path,
  1727	) -> None:
  1728	    transport = FakeTransport()
  1729	    transport.fail_finalize = "rendering.ffmpeg-finalizer"
  1730	    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
  1731	    service = _service(
  1732	        tmp_path,
  1733	        transport,
  1734	        renderer_ids=("fixture.window",),
  1735	        planner_ids=("rendering.legacy_hybrid",),
  1736	    )
  1737	    output = tmp_path / "failed-finalize.mp4"
  1738	
  1739	    with pytest.raises(RendererInternalError):
  1740	        service.render_request(
  1741	            _request(tmp_path), selector="hybrid", out_path=output
  1742	        )
  1743	
  1744	    assert not output.exists()
  1745	    assert not list(tmp_path.glob("*.provenance.json"))
  1746	    assert not list(tmp_path.glob(".*.render-service-*"))
  1747	
  1748	
  1749	def test_support_failure_removes_workspace_and_commits_nothing(
  1750	    tmp_path: Path,
  1751	) -> None:
  1752	    transport = FakeTransport()
  1753	    transport.fail_support = "rendering.ffmpeg"
  1754	    service = _service(tmp_path, transport)
  1755	    output = tmp_path / "failed-support.mp4"
  1756	
  1757	    with pytest.raises(RendererInternalError):
  1758	        service.render_request(
  1759	            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
  1760	        )
  1761	
  1762	    assert not output.exists()
  1763	    assert not list(tmp_path.glob("*.provenance.json"))
  1764	    assert not list(tmp_path.glob(".*.render-service-*"))
  1765	
  1766	
  1767	def test_renderer_attachments_survive_validation_into_committed_provenance(
  1768	    tmp_path: Path,
  1769	) -> None:
  1770	    transport = FakeTransport()
  1771	    transport.render_attachments["rendering.ffmpeg"] = {
  1772	        "storyboard.png": b"png-bytes",
  1773	        "captions.srt": b"srt-bytes",
  1774	    }
  1775	    service = _service(tmp_path, transport)
  1776	    output = tmp_path / "attachments.mp4"
  1777	
  1778	    service.render_request(
  1779	        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
  1780	    )
  1781	
  1782	    payload = _sidecar(output)
  1783	    assert set(payload["attachments"]) == {"storyboard.png", "captions.srt"}
  1784	    assert payload["attachments"]["storyboard.png"]["sha256"] == hashlib.sha256(
  1785	        b"png-bytes"
  1786	    ).hexdigest()
  1787	    assert payload["attachments"]["storyboard.png"]["kind"] == "fixture"
  1788	    assert payload["attachments"]["storyboard.png"]["path"].endswith(
  1789	        "storyboard.png"
  1790	    )
  1791	    assert len(payload["artifact_profiles"]) == 1
  1792	    assert set(payload["artifact_profiles"][0]["attachments"]) == {
  1793	        "storyboard.png",
  1794	        "captions.srt",
  1795	    }
  1796	
  1797	
  1798	def test_finalizer_preserves_segment_attachments_and_adds_its_own(
  1799	    tmp_path: Path,
  1800	) -> None:
  1801	    transport = FakeTransport()
  1802	    transport.render_attachments["fixture.window"] = [
  1803	        {"segment-a.txt": b"first-segment"},
  1804	        {"segment-b.txt": b"second-segment"},
  1805	    ]
  1806	    transport.finalize_attachments = {"final-note.txt": b"final"}
  1807	    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
  1808	    service = _service(
  1809	        tmp_path,
  1810	        transport,
  1811	        renderer_ids=("fixture.window",),
  1812	        planner_ids=("rendering.legacy_hybrid",),
  1813	    )
  1814	    output = tmp_path / "finalized-attachments.mp4"
  1815	
  1816	    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)
  1817	
  1818	    payload = _sidecar(output)
  1819	    assert set(payload["attachments"]) == {
  1820	        "segment-a.txt",
  1821	        "segment-b.txt",
  1822	        "final-note.txt",
  1823	    }
  1824	    assert len(payload["artifact_profiles"]) == 2
  1825	    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
  1826	    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}
  1827	
  1828	
  1829	def test_audio_completer_dropping_attachments_is_rejected(tmp_path: Path) -> None:
  1830	    transport = FakeTransport()
  1831	    transport.render_attachments["rendering.ffmpeg"] = {"must-survive.txt": b"x"}
  1832	
  1833	    def bad_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
  1834	        return replace(
  1835	            result,
  1836	            video=replace(
  1837	                result.video,
  1838	                profile=_profile(audio=True),
  1839	                audio=AudioOwnership.RENDERED,
  1840	                attachments={},
  1841	            ),
  1842	            audio_ownership=AudioOwnership.RENDERED,
  1843	        )
  1844	
  1845	    service = _service(tmp_path, transport, audio_completer=bad_completer)
  1846	    output = tmp_path / "dropped-attachments.mp4"
  1847	
  1848	    with pytest.raises(RendererInvalidArtifactError, match="attachments"):
  1849	        service.render_request(
  1850	            replace(_request(tmp_path), audio=AudioOwnership.PASSTHROUGH),

exec
/bin/zsh -lc "rg -n \"Batch 4|artifact_profiles|finalizer|direct\" .oracle/tasklist.md .oracle/plan.md | head -200 && sed -n '280,360p' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 614ms:
.oracle/tasklist.md:13:- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
.oracle/tasklist.md:22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
.oracle/tasklist.md:50:## Batch 3 — Built-in renderer and finalizer extraction
.oracle/tasklist.md:52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
.oracle/tasklist.md:56:- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
.oracle/tasklist.md:61:- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
.oracle/tasklist.md:70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
.oracle/tasklist.md:73:## Batch 4 — Generic routing, provenance, and hybrid planning
.oracle/tasklist.md:92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
.oracle/tasklist.md:102:- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
.oracle/tasklist.md:103:- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
.oracle/tasklist.md:141:- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.
.oracle/tasklist.md:151:- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
.oracle/tasklist.md:162:- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
.oracle/tasklist.md:166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
.oracle/plan.md:7:4. **Registry semantics:** build renderer/planner/finalizer registries over `CapabilityRegistry`, `AliasResolver`, and `OverrideStore`. Winner order comes directly from `DiscoveredPack.priority_index`; do not reinterpret executor `metadata["priority"]`. Only execution-eligible candidates enter the executable registry, so an ineligible higher-precedence candidate cannot shadow trusted code.
.oracle/plan.md:9:5. **Aliases and overrides:** extend pack-schema and normalizer alias-kind allowlists for `renderer`, `planner`, and `finalizer`, while keeping bare legacy names programmatic. Resolution is alias → canonical ID → override target → registry winner. Wire `OverrideStore` during default registry construction rather than CLI-only post-attachment.
.oracle/plan.md:14:   - use an attached/auto-resolved request when retaining the caller’s output directory;
.oracle/plan.md:19:   Encapsulate this in one small helper over existing task/executor primitives so callers do not hand-roll environment state. Legacy unbound callers and unbound renderer smoke tests use the public `RenderService` directly. Backend commands remain leaf subprocesses and never create `run.json`.
.oracle/plan.md:79:    - renderer, planner, and finalizer descriptors;
.oracle/plan.md:85:    - structured protocol/backend/artifact/finalizer failures;
.oracle/plan.md:89:  - Require one primary video. Preserve uniquely named, contained attachments without requiring the default finalizer to understand them.
.oracle/plan.md:111:  - Extend `PACK_ALIAS_KINDS`, `PackAliasKind`, `pack.json`, and alias extraction for `renderer`, `planner`, and `finalizer`.
.oracle/plan.md:112:  - Build registries directly from `discover_pack_metadata()` so every entry retains `source_kind` and `priority_index`.
.oracle/plan.md:147:  - Serve only invocation-staged assets from `127.0.0.1`; bind the server directly to port `0`, retain Range support, start inside the managed context, and always shut down, close, and join it.
.oracle/plan.md:149:  - Add one canonical resolved render profile using the same merged theme/timeline canvas consumed by Remotion. Planner, backend requests, and finalizer all receive that profile.
.oracle/plan.md:200:- [ ] **M1-07 — Extract `rendering.ffmpeg-finalizer`**
.oracle/plan.md:202:  - Move `_concat_segments()` behind the finalizer contract.
.oracle/plan.md:222:  - Add backend-neutral planner, fallback, finalizer, and configuration inputs.
.oracle/plan.md:235:    - resolved renderer/planner/finalizer;
.oracle/plan.md:269:  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
.oracle/plan.md:288:  | `video_editing/orchestrators/iteration_video/plan_template.py` | Replace the direct module command with a task-attached canonical `rendering.render` invocation, passing `output_name=iteration.mp4`. |
.oracle/plan.md:292:  | `editorial/executors/human_notes/run.py` | Replace its direct-module render command with attached facade invocation when possible, otherwise the public service. |
.oracle/plan.md:298:  - Keep direct imports only where tests exercise extracted implementation units.
.oracle/plan.md:299:  - Prove facade executor overrides affect attached facade paths. Prove renderer/planner/finalizer overrides affect both facade and public-service paths.
.oracle/plan.md:334:  - Remove or label stale direct-module commands and correct `HypeComposition` to `TimelineComposition`.
.oracle/plan.md:380:  - Point `extensions.rendering.renderers` directly at the root manifest.
.oracle/plan.md:385:  - Gate: create, static validate, generated test, trusted install, and two-second smoke render pass in a fresh directory and installed wheel.
.oracle/plan.md:401:  - `smoke` calls `RenderService` directly with a temporary output. Do not call `run_executor(project=None)`, auto-attach to the current project, or introduce a general no-project executor mode.
.oracle/plan.md:419:  - Keep support probing and custom finalizers in separate advanced sections.
.oracle/plan.md:423:  - Extend documentation-command verification and remove stale direct-module paths.

exec
/bin/zsh -lc "sed -n '73,100p' .oracle/tasklist.md && sed -n '210,280p' .oracle/plan.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 163ms:
## Batch 4 — Generic routing, provenance, and hybrid planning

**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
- `output_name` uses existing input placeholders and cache/CAS identity, rejects separators/traversal/non-MP4 extensions, preserves declared output names, and leaves Hype’s default `hype.mp4` sentinel unchanged.
- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.

### Tasks

- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.

## Batch 5 — Caller migration, semantic parity, and M1 freeze

**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- [ ] **M1-08 — Add generic routing, flexible facade output, and provenance v2**

  - Implement `RenderService`:
    1. translate the legacy selector;
    2. resolve its alias;
    3. apply the override;
    4. select the registry winner;
    5. verify execution eligibility;
    6. obtain static/request-sensitive support;
    7. invoke and validate;
    8. complete audio/finalize when required;
    9. publish video and sidecar.
  - Add backend-neutral planner, fallback, finalizer, and configuration inputs.
  - Allow qualified IDs through `engine`; replace fixed argparse choices with validation against legacy names or qualified IDs.
  - Add `output_name` as an ordinary executor input with default `hype.mp4`:
    - reject separators, traversal, and invalid extensions;
    - use existing input-placeholder expansion for `{out}/{output_name}` and `{out}/{output_name}.provenance.json`;
    - keep declared output names `video` and `provenance` stable;
    - rely on the existing inclusion of inputs in cache/CAS identity;
    - add no new dynamic-output or dynamic-sentinel subsystem.
  - Keep Hype’s real pipeline sentinel as `hype.mp4`, since Hype uses the default. Test non-default names through declared output resolution, pipeline propagation, and Arnold collection.
  - Make `render/run.py` a thin facade adapter.
  - Characterize the current argument-order shim, make facade parsing order-independent, then delete `_normalize_render_command_compat` if the compatibility test proves it unnecessary.
  - Emit provenance v2 with:
    - requested legacy selector/policy;
    - resolved renderer/planner/finalizer;
    - source pack/kind/revision and derived trust method;
    - alias and override evidence;
    - manifest and request digests;
    - support decision and alternatives;
    - input and artifact hashes/profiles;
    - audio ownership/completion;
    - normalization and attachments;
    - backend-owned fragments.
  - Preserve all currently emitted optional v1 keys where applicable:
    `engine`, `output`, `timeline`, `assets_registry`, `project_dir`,
    `composition_id`, `active_pack_order`, `active_theme`, `registry_hash`,
    `registry_state`, `resolved_effect_ids`, `resolved_effects`,
    `source_pack_ids`, `element_roots`, `staged_asset_ids`,
    `staged_asset_root`, `segments`, `segment_provenance`,
    `ffmpeg_specialization`, and `audio_reactive_colour`.
  - Ensure plain FFmpeg, FFmpeg fast paths, audio-reactive, Remotion, and single-segment hybrid produce exactly one sidecar.
  - Make previous-output cleanup lock-aware and conservative around corrupt/orphaned pairs; never delete unrelated output solely because a sidecar is unreadable.
  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.

- [ ] **M1-09 — Port hybrid to a generic planner/dispatcher**

  - Extract legacy complexity/window planning as `rendering.legacy_hybrid`.
  - Resolve canvas/FPS once from the canonical merged theme/timeline profile.
  - Represent every segment as integer half-open frames.
  - Preserve characterized transition `duration`/`durationFrames` and handle behavior.
  - Retain effects, transitions, overlays, opacity, and fades while closing fatal gaps:
    - speed changes;
    - overlapping audio;
    - unsupported non-media clips;
    - strict-FFmpeg-invalid visual gaps/overlaps;
    - controls rejected by the selected renderer’s support report.
  - Permit FFmpeg track mute/volume after M1-06 proves exact support; fades continue to route away from FFmpeg.
  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
  - Remove recursive calls to `render()`. The dispatcher invokes plan entries only through `RenderService`.
  - Add a deterministic mixed plan using the raw fixture renderer for one window and a built-in renderer for another.
  - Preserve legacy `segments` and nested `segment_provenance` projections while adding normalized v2 segment records, including FFmpeg segments.
  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.

- [ ] **M1-10 — Migrate every production caller and remove stale resolution**

  - Add one small attached-child invocation helper over existing executor/task primitives. It must:
    - require a validated parent project/run ID and unique step ID;
    - preserve the caller-selected output when requested;
    - scope and restore all environment changes;

exec
/bin/zsh -lc "rg -n \"finalizer_id\\s*=|finalizer-id|artifact_profiles\" tests astrid | head -250 && git show 98f4edea:astrid/core/rendering/service.py | nl -ba | sed -n '430,490p;1600,1695p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 214ms:
tests/core/rendering/test_contracts.py:568:        "artifact_profiles": [
tests/core/rendering/test_contracts.py:702:        artifact_profiles=[
tests/core/rendering/test_contracts.py:775:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:782:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:836:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:842:            artifact_profiles={
tests/core/rendering/test_contracts.py:850:            artifact_profiles={
tests/core/rendering/test_contracts.py:862:            artifact_profiles={
tests/core/rendering/test_contracts.py:877:            artifact_profiles=[
tests/core/rendering/test_contracts.py:891:            artifact_profiles={
tests/core/rendering/test_contracts.py:905:            artifact_profiles={
tests/core/rendering/test_contracts.py:921:            artifact_profiles={
tests/core/rendering/test_contracts.py:942:            artifact_profiles=[
tests/core/rendering/test_contracts.py:979:            artifact_profiles=[
tests/core/rendering/test_contracts.py:991:            artifact_profiles={
tests/core/rendering/test_contracts.py:1004:            artifact_profiles={123: {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:1010:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:1017:        artifact_profiles=[
tests/core/rendering/test_contracts.py:1035:        artifact_profiles=first["artifact_profiles"],
tests/core/rendering/test_contracts.py:1037:    assert second["artifact_profiles"] == first["artifact_profiles"]
tests/core/rendering/test_contracts.py:1044:            artifact_profiles=[
tests/core/rendering/test_contracts.py:1062:            artifact_profiles=[mutated],
tests/core/rendering/test_contracts.py:1070:            artifact_profiles=[],
tests/core/rendering/test_service.py:1791:    assert len(payload["artifact_profiles"]) == 1
tests/core/rendering/test_service.py:1792:    assert set(payload["artifact_profiles"][0]["attachments"]) == {
tests/core/rendering/test_service.py:1824:    assert len(payload["artifact_profiles"]) == 2
tests/core/rendering/test_service.py:1825:    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
tests/core/rendering/test_service.py:1826:    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}
tests/core/rendering/test_provenance.py:197:    assert len(payload["artifact_profiles"]) == 2
tests/core/rendering/test_provenance.py:198:    for artifact in payload["artifact_profiles"]:
tests/core/rendering/test_provenance.py:512:    assert committed["artifact_profiles"] == payload["artifact_profiles"]
tests/packs/rendering/test_ffmpeg_finalizer.py:171:    artifact_profiles: list[RenderProfile] | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py:178:    artifact_profiles = artifact_profiles or [canonical]
tests/packs/rendering/test_ffmpeg_finalizer.py:182:        for profile in artifact_profiles
tests/packs/rendering/test_ffmpeg_finalizer.py:193:        for index, profile in enumerate(artifact_profiles)
tests/packs/rendering/test_ffmpeg_finalizer.py:339:        artifact_profiles=[canonical, incompatible],
tests/packs/rendering/test_ffmpeg_finalizer.py:403:        artifact_profiles=[source],
tests/packs/rendering/test_ffmpeg_finalizer.py:458:        artifact_profiles=[
tests/packs/rendering/test_ffmpeg_finalizer.py:486:        artifact_profiles=[
tests/packs/rendering/test_ffmpeg_finalizer.py:526:        artifact_profiles=[source],
tests/packs/rendering/test_ffmpeg_finalizer.py:553:        artifact_profiles=[canonical, _profile(audio=False)],
astrid/core/rendering/provenance.py:192:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:198:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:206:                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
astrid/core/rendering/provenance.py:212:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:223:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:233:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:264:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:269:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:278:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:282:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:404:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:462:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:463:            artifact_profiles,
astrid/core/rendering/contracts.py:74:        "artifact_profiles",
astrid/core/rendering/service.py:207:        self.finalizer_id = finalizer_id
astrid/core/rendering/service.py:521:            artifact_profiles=artifact_lineage,
astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   430	                    message="render planner produced no video segments",
   431	                    recovery_command="use a non-empty timeline or select a direct renderer",
   432	                    details={"total_frames": plan.total_frames},
   433	                )
   434	            final_result, plan = self._finish_plan(
   435	                request,
   436	                plan=plan,
   437	                segment_results=segment_results,
   438	                pinned_finalizer=pinned_finalizer,
   439	                workspace=workspace,
   440	            )
   441	            artifact_lineage = [item.video for item in segment_results]
   442	            compatibility_results = segment_results
   443	            fragment_results = (
   444	                segment_results
   445	                if len(segment_results) == 1
   446	                else [*segment_results, final_result]
   447	            )
   448	        else:
   449	            final_result = self._invoke_renderer(
   450	                request,
   451	                selected=selected,
   452	                workspace=workspace,
   453	                output_name=request.output_name,
   454	                expected_profile=request.profile,
   455	            )
   456	            plan = self._direct_plan(
   457	                request,
   458	                selected=selected,
   459	                result=final_result,
   460	                requested_policy=policy.requested,
   461	            )
   462	            final_result = self.complete_audio(
   463	                final_result,
   464	                request=request,
   465	                plan=plan,
   466	                workspace=workspace,
   467	                backend=selected.candidate.id,
   468	            )
   469	            if final_result.video.profile != plan.profile or (
   470	                final_result.video.duration_frames
   471	                != (
   472	                    plan.window.duration_frames
   473	                    if plan.window is not None
   474	                    else plan.total_frames
   475	                )
   476	            ):
   477	                plan = self._direct_plan(
   478	                    request,
   479	                    selected=selected,
   480	                    result=final_result,
   481	                    requested_policy=policy.requested,
   482	            )
   483	            artifact_lineage = [final_result.video]
   484	            compatibility_results = [final_result]
   485	            fragment_results = [final_result]
   486	
   487	        source_video = self._artifact_path(final_result, workspace)
   488	        compatibility = self._v1_compatibility(
   489	            compatibility_results,
   490	            supplied=v1_compatibility,
  1600	                        "artifact_fps": list(result.video.profile.fps_rational),
  1601	                    },
  1602	                )
  1603	            segment_window = request.window
  1604	            total_frames = request.window.end_frame
  1605	            plan_window = request.window
  1606	            self._validate_planned_duration(
  1607	                result,
  1608	                planned_frames=request.window.duration_frames,
  1609	                canonical_profile=result.video.profile,
  1610	                backend=selected.candidate.id,
  1611	                label="renderer artifact",
  1612	            )
  1613	        else:
  1614	            segment_window = FrameWindow(
  1615	                start_frame=0,
  1616	                end_frame=result.video.duration_frames,
  1617	                fps_rational=result.video.profile.fps_rational,
  1618	            )
  1619	            total_frames = result.video.duration_frames
  1620	            plan_window = None
  1621	        segment = RenderSegment(
  1622	            window=segment_window,
  1623	            renderer=self._renderer_resolution(selected),
  1624	            input_hashes=self._input_hashes(request),
  1625	        )
  1626	        return RenderPlan(
  1627	            schema_version=SCHEMA_VERSION,
  1628	            request_digest=compute_request_digest(request.to_dict()),
  1629	            requested_policy=requested_policy,
  1630	            planner=PlannerResolution(
  1631	                id=_DIRECT_PLANNER_ID,
  1632	                source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
  1633	                manifest_digest=_DIRECT_PLANNER_DIGEST,
  1634	                trust_eligibility={"eligible": True, "reason": "core direct plan"},
  1635	            ),
  1636	            segments=[segment],
  1637	            finalizer=finalizer_resolution,
  1638	            profile=result.video.profile,
  1639	            total_frames=total_frames,
  1640	            reasons=reasons,
  1641	            window=plan_window,
  1642	        )
  1643	
  1644	    def _direct_finalizer_resolution(self) -> FinalizerResolution:
  1645	        if self.finalizer_id is not None:
  1646	            candidate, evidence = self._resolve_candidate(
  1647	                self.finalizers,
  1648	                self.finalizer_id,
  1649	                kind="finalizer",
  1650	                observe=False,
  1651	            )
  1652	            return self._finalizer_resolution(candidate, evidence, support=None)
  1653	        return FinalizerResolution(
  1654	            id=_DIRECT_FINALIZER_ID,
  1655	            source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
  1656	            manifest_digest=_DIRECT_FINALIZER_DIGEST,
  1657	            trust_eligibility={"eligible": True, "reason": "core direct pass-through"},
  1658	        )
  1659	
  1660	    @staticmethod
  1661	    def _source_pack(
  1662	        candidate: RenderingCandidate[Any], evidence: Mapping[str, Any]
  1663	    ) -> dict[str, Any]:
  1664	        source = {
  1665	            "id": candidate.pack_id,
  1666	            "source_kind": candidate.source_kind,
  1667	            "root": str(candidate.pack_root),
  1668	            "priority_index": candidate.priority_index,
  1669	        }
  1670	        revision = candidate.eligibility.active_revision
  1671	        if revision is not None:
  1672	            source["active_revision"] = revision
  1673	        manifest_path = evidence.get("manifest_path")
  1674	        if isinstance(manifest_path, str):
  1675	            source["manifest_path"] = manifest_path
  1676	        return source
  1677	
  1678	    def _renderer_resolution(
  1679	        self, selected: _ResolvedCapability
  1680	    ) -> RendererResolution:
  1681	        candidate = selected.candidate
  1682	        evidence = selected.evidence
  1683	        return RendererResolution(
  1684	            id=candidate.id,
  1685	            source_pack=self._source_pack(candidate, evidence),
  1686	            manifest_digest=candidate.manifest_digest,
  1687	            alias_chain=list(evidence.get("alias_chain") or []),
  1688	            override=evidence.get("override"),
  1689	            support_decision=selected.support,
  1690	            trust_eligibility=candidate.eligibility.to_dict(),
  1691	        )
  1692	
  1693	    def _planner_resolution(
  1694	        self, selected: _ResolvedCapability
  1695	    ) -> PlannerResolution:

exec
/bin/zsh -lc "rg -n \"backend_fragments|RenderResult\\(\" astrid/packs/rendering/finalizers/ffmpeg/run.py astrid/packs/rendering/backends/ffmpeg/run.py | head -100 && nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '520,700p' && nl -ba astrid/core/rendering/service.py | sed -n '1020,1145p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/ffmpeg/run.py:630:        result = RenderResult(
astrid/packs/rendering/backends/ffmpeg/run.py:634:            backend_fragments={
astrid/packs/rendering/finalizers/ffmpeg/run.py:1082:        segment_result = RenderResult(
astrid/packs/rendering/finalizers/ffmpeg/run.py:1351:        result = RenderResult(
astrid/packs/rendering/finalizers/ffmpeg/run.py:1355:            backend_fragments={
   520	        "ffmpeg",
   521	        "-hide_banner",
   522	        "-y",
   523	        "-i",
   524	        str(segment.path),
   525	    ]
   526	    if synthesize_audio:
   527	        assert target_profile.audio_sample_rate is not None
   528	        assert target_profile.audio_channel_layout is not None
   529	        argv.extend(
   530	            [
   531	                "-f",
   532	                "lavfi",
   533	                "-i",
   534	                (
   535	                    "anullsrc="
   536	                    f"sample_rate={target_profile.audio_sample_rate}:"
   537	                    f"channel_layout={target_profile.audio_channel_layout}"
   538	                ),
   539	            ]
   540	        )
   541	    argv.extend(["-map", "0:v:0"])
   542	    if video_transcode:
   543	        filters = ["setpts=PTS-STARTPTS"]
   544	        if fields & {"width", "height"}:
   545	            filters.extend(
   546	                [
   547	                    (
   548	                        f"scale={target_profile.width}:{target_profile.height}:"
   549	                        "force_original_aspect_ratio=decrease"
   550	                    ),
   551	                    (
   552	                        f"pad={target_profile.width}:{target_profile.height}:"
   553	                        "(ow-iw)/2:(oh-ih)/2"
   554	                    ),
   555	                ]
   556	            )
   557	        if "fps_rational" in fields:
   558	            filters.append(f"fps={fps}")
   559	        if "time_base" in fields:
   560	            filters.append(f"settb=expr={time_base}")
   561	        if "pixel_format" in fields:
   562	            filters.append(f"format={target_profile.pixel_format}")
   563	        argv.extend(["-vf", ",".join(filters)])
   564	        encoder = _video_encoder(target_profile.video_codec)
   565	        argv.extend(["-c:v", encoder, "-r:v", fps, "-fps_mode", "cfr"])
   566	        if encoder in {"libx264", "libx265"}:
   567	            argv.extend(["-preset", "veryfast", "-crf", "20"])
   568	        if target_profile.video_profile is not None:
   569	            argv.extend(
   570	                [
   571	                    "-profile:v",
   572	                    _encoder_profile(
   573	                        target_profile.video_codec,
   574	                        target_profile.video_profile,
   575	                    ),
   576	                ]
   577	            )
   578	        if target_profile.video_level is not None:
   579	            argv.extend(
   580	                [
   581	                    "-level:v",
   582	                    _level(
   583	                        target_profile.video_level,
   584	                        codec=target_profile.video_codec,
   585	                    )
   586	                    or target_profile.video_level,
   587	                ]
   588	            )
   589	        argv.extend(["-pix_fmt", target_profile.pixel_format])
   590	    else:
   591	        argv.extend(["-c:v", "copy"])
   592	
   593	    if target_profile.has_audio:
   594	        assert target_profile.audio_codec is not None
   595	        assert target_profile.audio_sample_rate is not None
   596	        assert target_profile.audio_channel_layout is not None
   597	        argv.extend(["-map", "1:a:0" if synthesize_audio else "0:a:0"])
   598	        if audio_transcode:
   599	            audio_filter = (
   600	                "asetpts=PTS-STARTPTS,"
   601	                f"aformat=sample_rates={target_profile.audio_sample_rate}:"
   602	                f"channel_layouts={target_profile.audio_channel_layout}"
   603	            )
   604	            argv.extend(
   605	                [
   606	                    "-af",
   607	                    audio_filter,
   608	                    "-c:a",
   609	                    _audio_encoder(target_profile.audio_codec),
   610	                ]
   611	            )
   612	        else:
   613	            argv.extend(["-c:a", "copy"])
   614	    else:
   615	        argv.append("-an")
   616	
   617	    if synthesize_audio:
   618	        argv.append("-shortest")
   619	
   620	    argv.extend(
   621	        [
   622	            "-video_track_timescale",
   623	            str(_mp4_timescale(target_profile)),
   624	        ]
   625	    )
   626	    if faststart:
   627	        argv.extend(["-movflags", "+faststart"])
   628	    argv.extend(["-f", "mp4", str(output_path)])
   629	    return argv
   630	
   631	
   632	def build_concat_command(
   633	    list_path: Path,
   634	    output_path: Path,
   635	    *,
   636	    target_profile: RenderProfile,
   637	    faststart: bool,
   638	) -> list[str]:
   639	    """Build the final concat-demuxer stream-copy command."""
   640	
   641	    argv = [
   642	        "ffmpeg",
   643	        "-hide_banner",
   644	        "-y",
   645	        "-f",
   646	        "concat",
   647	        "-safe",
   648	        "0",
   649	        "-i",
   650	        str(list_path),
   651	        "-map",
   652	        "0:v:0",
   653	    ]
   654	    if target_profile.has_audio:
   655	        argv.extend(["-map", "0:a:0"])
   656	    else:
   657	        argv.append("-an")
   658	    argv.extend(
   659	        [
   660	            "-c",
   661	            "copy",
   662	            "-video_track_timescale",
   663	            str(_mp4_timescale(target_profile)),
   664	        ]
   665	    )
   666	    if faststart:
   667	        argv.extend(["-movflags", "+faststart"])
   668	    argv.extend(["-f", "mp4", str(output_path)])
   669	    return argv
   670	
   671	
   672	def _concat_file_line(path: Path) -> str:
   673	    # FFmpeg's concat demuxer uses shell-like single-quote escaping even though
   674	    # the command itself is never run through a shell.
   675	    resolved = str(path.resolve())
   676	    if "\n" in resolved or "\r" in resolved:
   677	        raise ValueError("FFmpeg concat input paths must not contain CR or LF")
   678	    escaped = resolved.replace("'", "'\\''")
   679	    return f"file '{escaped}'"
   680	
   681	
   682	def _run_checked(runner: Runner, argv: list[str]) -> None:
   683	    runner(argv, check=True)
   684	
   685	
   686	def _assemble_prepared_segments(
   687	    segments: Sequence[_PreparedSegment],
   688	    output_path: Path,
   689	    *,
   690	    target_profile: RenderProfile,
   691	    faststart: bool,
   692	    runner: Runner,
   693	) -> list[str]:
   694	    """Normalize incompatible segments and atomically assemble the output."""
   695	
   696	    if not segments:
   697	        raise ValueError("at least one segment is required for finalization")
   698	    _validate_target_profile(target_profile)
   699	    output_path = output_path.absolute()
   700	    output_path.parent.mkdir(parents=True, exist_ok=True)
  1020	        clips: list[dict[str, Any]] = []
  1021	        for raw_clip in raw_clips:
  1022	            if not isinstance(raw_clip, Mapping):
  1023	                raise TypeError("timeline clips must contain objects")
  1024	            clipped = cls._window_clip(raw_clip, start=start, end=end, window=window)
  1025	            if clipped is not None:
  1026	                clips.append(clipped)
  1027	        used_tracks = {clip.get("track") for clip in clips}
  1028	        tracks = [
  1029	            dict(track)
  1030	            for track in raw_tracks
  1031	            if isinstance(track, Mapping) and track.get("id") in used_tracks
  1032	        ]
  1033	        metadata = timeline_data.get("metadata", {})
  1034	        if not isinstance(metadata, Mapping):
  1035	            metadata = {}
  1036	        result = dict(timeline_data)
  1037	        result["tracks"] = tracks
  1038	        result["clips"] = clips
  1039	        result["metadata"] = {
  1040	            **dict(metadata),
  1041	            "source_window_start_seconds": float(start),
  1042	            "source_window_end_seconds": float(end),
  1043	            "duration_seconds": float(end - start),
  1044	        }
  1045	        return result
  1046	
  1047	    @classmethod
  1048	    def _window_clip(
  1049	        cls,
  1050	        clip: Mapping[str, Any],
  1051	        *,
  1052	        start: Fraction,
  1053	        end: Fraction,
  1054	        window: FrameWindow,
  1055	    ) -> dict[str, Any] | None:
  1056	        clip_start = cls._timeline_number(clip.get("at", 0), "clip.at")
  1057	        clip_end = cls._clip_end(clip, clip_start=clip_start)
  1058	        visible_start = max(clip_start, start)
  1059	        visible_end = min(clip_end, end)
  1060	        if visible_end <= visible_start:
  1061	            return None
  1062	
  1063	        result = dict(clip)
  1064	        result["at"] = float(visible_start - start)
  1065	        result["id"] = (
  1066	            f"{clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
  1067	        )
  1068	        if clip.get("clipType", "media") == "media":
  1069	            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
  1070	            if speed <= 0:
  1071	                raise ValueError("clip.speed must be positive")
  1072	            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
  1073	            source_from += (visible_start - clip_start) * speed
  1074	            result["from"] = float(source_from)
  1075	            result["to"] = float(
  1076	                source_from + (visible_end - visible_start) * speed
  1077	            )
  1078	        elif isinstance(clip.get("hold"), (int, float)) and not isinstance(
  1079	            clip.get("hold"), bool
  1080	        ):
  1081	            result["hold"] = float(visible_end - visible_start)
  1082	        return result
  1083	
  1084	    @classmethod
  1085	    def _clip_end(
  1086	        cls, clip: Mapping[str, Any], *, clip_start: Fraction
  1087	    ) -> Fraction:
  1088	        if clip.get("clipType", "media") == "media":
  1089	            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
  1090	            if "to" not in clip:
  1091	                raise ValueError("media clip must declare a source to bound")
  1092	            source_to = cls._timeline_number(clip["to"], "clip.to")
  1093	            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
  1094	            if source_from < 0 or source_to <= source_from or speed <= 0:
  1095	                raise ValueError("media clip must have positive bounds and speed")
  1096	            return clip_start + (source_to - source_from) / speed
  1097	        hold = clip.get("hold")
  1098	        if isinstance(hold, (int, float)) and not isinstance(hold, bool):
  1099	            return clip_start + max(Fraction(0), cls._timeline_number(hold, "clip.hold"))
  1100	        if isinstance(clip.get("to"), (int, float)) and not isinstance(
  1101	            clip.get("to"), bool
  1102	        ):
  1103	            return cls._timeline_number(clip["to"], "clip.to")
  1104	        return clip_start
  1105	
  1106	    @staticmethod
  1107	    def _timeline_number(value: Any, label: str) -> Fraction:
  1108	        if isinstance(value, bool) or not isinstance(value, (int, float)):
  1109	            raise TypeError(f"{label} must be a finite number")
  1110	        if not math.isfinite(float(value)):
  1111	            raise ValueError(f"{label} must be finite")
  1112	        return Fraction(str(value))
  1113	
  1114	    @staticmethod
  1115	    def _validate_segment_duration(
  1116	        result: RenderResult,
  1117	        *,
  1118	        segment: RenderSegment,
  1119	        canonical_profile: Any,
  1120	        backend: str,
  1121	    ) -> None:
  1122	        RenderService._validate_planned_duration(
  1123	            result,
  1124	            planned_frames=segment.window.duration_frames,
  1125	            canonical_profile=canonical_profile,
  1126	            backend=backend,
  1127	            label="renderer artifact",
  1128	        )
  1129	
  1130	    @staticmethod
  1131	    def _validate_planned_duration(
  1132	        result: RenderResult,
  1133	        *,
  1134	        planned_frames: int,
  1135	        canonical_profile: Any,
  1136	        backend: str,
  1137	        label: str,
  1138	    ) -> None:
  1139	        artifact_seconds = Fraction(
  1140	            result.video.duration_frames, 1
  1141	        ) / Fraction(*result.video.profile.fps_rational)
  1142	        canonical_fps = Fraction(*canonical_profile.fps_rational)
  1143	        planned_seconds = Fraction(planned_frames, 1) / canonical_fps
  1144	        delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
  1145	        if delta_frames <= canonical_profile.duration_tolerance:

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '1310,1385p' && nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '610,655p' && rg -n \"def _v1_compatibility|def _merge_backend_fragments\" astrid/core/rendering/service.py && nl -ba astrid/core/rendering/service.py | sed -n '1760,1870p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1310	                )
  1311	            effective_profile = _probe_normalized_segments(
  1312	                normalized_prepared,
  1313	                target_profile=assembly_profile,
  1314	            )
  1315	            for segment in prepared:
  1316	                if not _profile_differences(segment.profile, assembly_profile):
  1317	                    continue
  1318	                existing = set(normalization)
  1319	                for difference in _profile_differences(
  1320	                    segment.profile,
  1321	                    effective_profile,
  1322	                ):
  1323	                    record = _normalization_record(segment.index, difference)
  1324	                    if record not in existing:
  1325	                        normalization.append(record)
  1326	                        existing.add(record)
  1327	            normalized_prepared = [
  1328	                replace(segment, profile=effective_profile)
  1329	                for segment in normalized_prepared
  1330	            ]
  1331	            # The prepared list now has a uniform canonical profile, so this
  1332	            # call performs only the concat-demuxer stream-copy assembly.
  1333	            assembly_started = True
  1334	            extra_normalization = _assemble_prepared_segments(
  1335	                normalized_prepared,
  1336	                output_path,
  1337	                target_profile=effective_profile,
  1338	                faststart=faststart,
  1339	                runner=execute,
  1340	            )
  1341	            published = True
  1342	            normalization.extend(extra_normalization)
  1343	        video = VideoArtifact.from_file(
  1344	            path=output_path,
  1345	            workspace_root=workspace,
  1346	            profile=effective_profile,
  1347	            duration_frames=total_frames,
  1348	            audio=ownership,
  1349	            attachments=request.expected_attachments,
  1350	        )
  1351	        result = RenderResult(
  1352	            schema_version=SCHEMA_VERSION,
  1353	            video=video,
  1354	            audio_ownership=ownership,
  1355	            backend_fragments={
  1356	                BACKEND_ID: {
  1357	                    "finalizer_kind": "ffmpeg",
  1358	                    "finalizer_version": BACKEND_VERSION,
  1359	                    "segment_count": len(prepared),
  1360	                    "stream_copied_segments": [
  1361	                        segment.index
  1362	                        for segment in prepared
  1363	                        if not _profile_differences(segment.profile, assembly_profile)
  1364	                    ],
  1365	                    "normalized_segments": [
  1366	                        segment.index
  1367	                        for segment in prepared
  1368	                        if _profile_differences(segment.profile, assembly_profile)
  1369	                    ],
  1370	                    "audio_mode": ownership.value,
  1371	                }
  1372	            },
  1373	            normalization=normalization,
  1374	            logs=[],
  1375	            metadata=request.metadata,
  1376	        )
  1377	        request.validate_final_result(result)
  1378	        validate_render_result(
  1379	            result,
  1380	            expected_profile=request.plan.profile,
  1381	            workspace_root=workspace,
  1382	        )
  1383	        return result
  1384	    except BaseException:
  1385	        if assembly_started:
   610	                "frame_count": specialization_spec.total_frames,
   611	                "fps": specialization_spec.fps,
   612	                "marker_sha256": specialization_spec.marker_sha256,
   613	            }
   614	            fragment["specialization"] = specialization_fragment
   615	            provenance_v1["ffmpeg_specialization"] = (
   616	                audio_reactive_colour.ADAPTER_ID
   617	            )
   618	            provenance_v1["audio_reactive_colour"] = {
   619	                key: value
   620	                for key, value in specialization_fragment.items()
   621	                if key != "id"
   622	            }
   623	        video = VideoArtifact.from_file(
   624	            path=output_path,
   625	            workspace_root=workspace,
   626	            profile=declared_profile,
   627	            duration_frames=duration_frames,
   628	            audio=ownership,
   629	        )
   630	        result = RenderResult(
   631	            schema_version=SCHEMA_VERSION,
   632	            video=video,
   633	            audio_ownership=ownership,
   634	            backend_fragments={
   635	                BACKEND_ID: fragment
   636	            },
   637	            normalization=[],
   638	            logs=[],
   639	            metadata=request.metadata,
   640	        )
   641	        validate_render_result(
   642	            result,
   643	            expected_profile=declared_profile,
   644	            workspace_root=workspace,
   645	        )
   646	        return result
   647	    except BaseException:
   648	        output_path.unlink(missing_ok=True)
   649	        raise
   650	
   651	
   652	def _load_request(path: Path) -> RenderRequest:
   653	    payload = json.loads(path.read_text(encoding="utf-8"))
   654	    if not isinstance(payload, Mapping):
   655	        raise TypeError("render request must contain a JSON object")
1816:    def _merge_backend_fragments(
1836:    def _v1_compatibility(
  1760	        *,
  1761	        workspace: Path,
  1762	        required_binaries: Sequence[str] | None = None,
  1763	    ) -> Any:
  1764	        token = hashlib.sha256(
  1765	            f"{candidate.id}:{verb}:{len(list(workspace.iterdir()))}".encode()
  1766	        ).hexdigest()[:12]
  1767	        request_path = workspace / f"{token}-{verb}-request.json"
  1768	        result_path = workspace / f"{token}-{verb}-result.json"
  1769	        write_json_atomic(request_path, payload.to_dict())
  1770	        transport = (
  1771	            self._transport
  1772	            if self._transport is not None
  1773	            else self._transport_factory(candidate.id)
  1774	        )
  1775	        return transport.run(
  1776	            verb,
  1777	            candidate.manifest.command,
  1778	            backend=candidate.id,
  1779	            request_path=request_path,
  1780	            result_path=result_path,
  1781	            cwd=candidate.pack_root,
  1782	            timeout=candidate.manifest.timeout_seconds,
  1783	            required_binaries=(
  1784	                candidate.manifest.required_binaries
  1785	                if required_binaries is None
  1786	                else required_binaries
  1787	            ),
  1788	        )
  1789	
  1790	    @staticmethod
  1791	    def _artifact_path(result: RenderResult, workspace: Path) -> Path:
  1792	        candidate = (workspace / result.video.path).resolve(strict=False)
  1793	        try:
  1794	            candidate.relative_to(workspace.resolve())
  1795	        except ValueError:
  1796	            raise_invalid_artifact_error(
  1797	                backend=_CORE_BACKEND_ID,
  1798	                message="validated renderer artifact escaped its invocation workspace",
  1799	                recovery_command="rerun the renderer with a contained output path",
  1800	                details={"path": result.video.path},
  1801	            )
  1802	        return candidate
  1803	
  1804	    @staticmethod
  1805	    def _input_hashes(request: RenderRequest) -> dict[str, str]:
  1806	        paths: dict[str, Path] = {"timeline": Path(request.timeline_path)}
  1807	        if request.assets_registry_path is not None:
  1808	            paths["assets_registry"] = Path(request.assets_registry_path)
  1809	        return {
  1810	            name: sha256_file(path)
  1811	            for name, path in paths.items()
  1812	            if path.is_file()
  1813	        }
  1814	
  1815	    @staticmethod
  1816	    def _merge_backend_fragments(
  1817	        results: Sequence[RenderResult],
  1818	    ) -> dict[str, dict[str, Any]]:
  1819	        merged: dict[str, dict[str, Any]] = {}
  1820	        for result in results:
  1821	            for namespace, fragment in result.backend_fragments.items():
  1822	                current = merged.get(namespace)
  1823	                if current is None:
  1824	                    merged[namespace] = dict(fragment)
  1825	                elif current != fragment:
  1826	                    records = current.get("service_fragment_sequence")
  1827	                    if isinstance(records, list):
  1828	                        records.append(dict(fragment))
  1829	                    else:
  1830	                        merged[namespace] = {
  1831	                            "service_fragment_sequence": [current, dict(fragment)]
  1832	                        }
  1833	        return merged
  1834	
  1835	    @staticmethod
  1836	    def _v1_compatibility(
  1837	        results: Sequence[RenderResult],
  1838	        *,
  1839	        supplied: Mapping[str, Any] | None,
  1840	    ) -> dict[str, Any]:
  1841	        compatibility: dict[str, Any] = {
  1842	            "project_dir": None,
  1843	            "composition_id": "TimelineComposition",
  1844	            "active_pack_order": [],
  1845	            "active_theme": None,
  1846	            "registry_hash": None,
  1847	            "registry_state": {},
  1848	            "resolved_effect_ids": [],
  1849	            "resolved_effects": [],
  1850	            "source_pack_ids": [],
  1851	            "element_roots": [],
  1852	            "staged_asset_ids": [],
  1853	            "staged_asset_root": None,
  1854	        }
  1855	        segment_provenance: list[dict[str, Any]] = []
  1856	        for result in results:
  1857	            for fragment in result.backend_fragments.values():
  1858	                legacy = fragment.get("legacy_v1")
  1859	                if not isinstance(legacy, Mapping):
  1860	                    continue
  1861	                segment_provenance.append(dict(legacy))
  1862	                for key in compatibility:
  1863	                    if key in legacy:
  1864	                        compatibility[key] = legacy[key]
  1865	                for key in (
  1866	                    "ffmpeg_specialization",
  1867	                    "audio_reactive_colour",
  1868	                ):
  1869	                    if key in legacy:
  1870	                        compatibility[key] = legacy[key]

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/test_service.py tests/packs/rendering/test_render_facade.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 1558ms:
Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/bin/pytest", line 6, in <module>
    sys.exit(console_main())
             ^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
           ^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1186, in pytest_cmdline_parse
    self.parse(args)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1556, in parse
    self.hook.pytest_load_initial_conftests(
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 628, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 127, in _sanitize_params
    dir = gettempdir()
          ^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 316, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 309, in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle']

exec
/bin/zsh -lc "sed -n '8300,8425p' .oracle/checkins/batch-4-r1.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   240	        )
   241	        no_visual_adjustments = not any(
   242	            key in clip
   243	            for key in (
   244	                "x",
   245	                "y",
   246	                "width",
   247	                "height",
   248	                "cropTop",
   249	                "cropBottom",
   250	                "cropLeft",
   251	                "cropRight",
   252	                "effects",
   253	                "transition",
   254	            )
   255	        )
   256	        if (
   257	            inputs.stream_copy_allowed
   258	            and at == 0
   259	            and start == 0
   260	            and full_duration
   261	            and same_resolution
   262	            and same_fps
   263	            and no_visual_adjustments
   264	        ):
   265	            copy_video_input = asset_index[asset_key]
   266	    if copy_video_input is None:
   267	        for index, clip in enumerate(video_clips):
   268	            inp = asset_index[str(clip["asset"])]
   269	            start = float(clip.get("from", 0) or 0)
   270	            end = float(clip.get("to", start) or start)
   271	            label = f"v{index}"
   272	            filters.append(
   273	                f"[{inp}:v]trim=start={start:.6f}:end={end:.6f},"
   274	                "setpts=PTS-STARTPTS,"
   275	                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
   276	                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
   277	                f"fps={fps},format=yuv420p[{label}]"
   278	            )
   279	            video_labels.append(f"[{label}]")
   280	        filters.append(
   281	            "".join(video_labels)
   282	            + f"concat=n={len(video_labels)}:v=1:a=0[vout]"
   283	        )
   284	
   285	    audio_labels: list[str] = []
   286	    cursor = 0.0
   287	    audio_index = 0
   288	    for clip in audio_clips:
   289	        at = float(clip.get("at", 0))
   290	        if at > cursor + 1e-9:
   440	def build_render_command(
   441	    request: RenderRequest | Mapping[str, Any],
   442	    workspace: Path,
   443	) -> list[str]:
   444	    """Build FFmpeg argv for ``workspace/outputs/<request.output_name>``.
   445	
   446	    Stream-copy is permitted only when strict support's probe evidence says
   447	    the whole source is compatible (never trust registry metadata alone).
   448	    """
   449	    inputs = resolve_render_command_inputs(request, workspace)
   450	    try:
   451	        from astrid.core.rendering.contracts import RenderRequest
   452	        from astrid.packs.rendering.backends.ffmpeg.support import support
   453	
   454	        normalized_request = (
   455	            request
   456	            if isinstance(request, RenderRequest)
   457	            else RenderRequest.from_dict(request)
   458	        )
   459	        report = support(
   460	            normalized_request,
   461	            inputs.timeline_data,
   462	            inputs.registry,
   463	        )
   464	        stream_copy_allowed = (
   465	            report.supported and bool(report.features.get("stream_copy"))
   466	        )
   467	    except Exception:
   468	        stream_copy_allowed = False
   469	    inputs = replace(inputs, stream_copy_allowed=stream_copy_allowed)
   470	    return build_render_command_from_inputs(inputs)
   471	
   472	
   473	def build_render_command_from_data(
   474	    timeline_path: Path,
   475	    assets_path: Path,
   476	    output_path: Path,
   477	    timeline_data: Mapping[str, Any],
   478	    registry: Mapping[str, Any],
   479	    *,
   480	    audio_sample_rate: int = 48000,

collab: Wait
collab: Wait
codex
The review has confirmed that the finalizer lineage is preserved only temporarily: the subsequent support-resolution step reconstructs the finalizer record from canonical-ID evidence and drops the planner’s alias/override history. The CLI conflict check likewise misses the explicit-default case; I’m finishing the independent cross-check before issuing the binary verdict.
collab: Wait
codex
Issues:

- HIGH — Finalizer alias/override lineage is merged at [service.py:1270](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1270), then discarded when `_finish_plan()` rebuilds the resolution from canonical evidence at [service.py:1354](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1354).

- HIGH — `RenderService(finalizer_id=...)` pins an executable finalizer for direct renders at [service.py:1644](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1644), but the direct branch never invokes `_finish_plan()` or that finalizer ([service.py:448](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:448)).

- MEDIUM — Conflicting explicit `--engine remotion --backend ffmpeg` is still accepted because `remotion` is also the argparse default and explicit presence is not tracked ([run.py:286](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:286)).

- MEDIUM — Real-service audio-reactive coverage remains absent. The audio-reactive matrix case still uses `FakeTransport` ([test_service.py:1492](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1492)); the new real tests cover ordinary/whole-media FFmpeg and hybrid only.
tokens used
235,195
Issues:

- HIGH — Finalizer alias/override lineage is merged at [service.py:1270](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1270), then discarded when `_finish_plan()` rebuilds the resolution from canonical evidence at [service.py:1354](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1354).

- HIGH — `RenderService(finalizer_id=...)` pins an executable finalizer for direct renders at [service.py:1644](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1644), but the direct branch never invokes `_finish_plan()` or that finalizer ([service.py:448](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:448)).

- MEDIUM — Conflicting explicit `--engine remotion --backend ffmpeg` is still accepted because `remotion` is also the argparse default and explicit presence is not tracked ([run.py:286](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:286)).

- MEDIUM — Real-service audio-reactive coverage remains absent. The audio-reactive matrix case still uses `FakeTransport` ([test_service.py:1492](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1492)); the new real tests cover ordinary/whole-media FFmpeg and hybrid only.

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '448,525p' && nl -ba astrid/core/rendering/service.py | sed -n '1318,1405p' && nl -ba tests/core/rendering/test_service.py | sed -n '2048,2175p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   448	        else:
   449	            final_result = self._invoke_renderer(
   450	                request,
   451	                selected=selected,
   452	                workspace=workspace,
   453	                output_name=request.output_name,
   454	                expected_profile=request.profile,
   455	            )
   456	            plan = self._direct_plan(
   457	                request,
   458	                selected=selected,
   459	                result=final_result,
   460	                requested_policy=policy.requested,
   461	            )
   462	            final_result = self.complete_audio(
   463	                final_result,
   464	                request=request,
   465	                plan=plan,
   466	                workspace=workspace,
   467	                backend=selected.candidate.id,
   468	                # The direct plan may pin an executable finalizer; defer
   469	                # completion to it so a normalizable profile/audio mismatch
   470	                # is normalized before publication.
   471	                defer_to_finalizer=(
   472	                    plan.finalizer.id != _DIRECT_FINALIZER_ID
   473	                ),
   474	            )
   475	            if plan.finalizer.id != _DIRECT_FINALIZER_ID:
   476	                # An embedding host pinned a registered finalizer for direct
   477	                # renders; honor it exactly like planner-produced plans.
   478	                finalizer, finalizer_evidence = self._resolve_candidate(
   479	                    self.finalizers,
   480	                    plan.finalizer.id,
   481	                    kind="finalizer",
   482	                    observe=False,
   483	                )
   484	                final_result, plan = self._finish_plan(
   485	                    request,
   486	                    plan=plan,
   487	                    segment_results=[final_result],
   488	                    pinned_finalizer=(finalizer, finalizer_evidence),
   489	                    workspace=workspace,
   490	                )
   491	            elif final_result.video.profile != plan.profile or (
   492	                final_result.video.duration_frames
   493	                != (
   494	                    plan.window.duration_frames
   495	                    if plan.window is not None
   496	                    else plan.total_frames
   497	                )
   498	            ):
   499	                plan = self._direct_plan(
   500	                    request,
   501	                    selected=selected,
   502	                    result=final_result,
   503	                    requested_policy=policy.requested,
   504	            )
   505	            artifact_lineage = [final_result.video]
   506	            compatibility_results = [final_result]
   507	            fragment_results = [final_result]
   508	
   509	        source_video = self._artifact_path(final_result, workspace)
   510	        compatibility = self._v1_compatibility(
   511	            compatibility_results,
   512	            supplied=v1_compatibility,
   513	        )
   514	        fragments = self._merge_backend_fragments(fragment_results)
   515	        provenance = self._provenance_builder(
   516	            engine=policy.requested,
   517	            output=out_path,
   518	            timeline=request.timeline_path,
   519	            assets_registry=request.assets_registry_path,
   520	            plan=plan,
   521	            artifact_profiles=artifact_lineage,
   522	            audio_ownership=final_result.audio_ownership,
   523	            normalization=final_result.normalization,
   524	            attachments=final_result.attachments,
   525	            backend_fragments=fragments,
  1318	    def _finish_plan(
  1319	        self,
  1320	        request: RenderRequest,
  1321	        *,
  1322	        plan: RenderPlan,
  1323	        segment_results: list[RenderResult],
  1324	        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
  1325	        workspace: Path,
  1326	    ) -> tuple[RenderResult, RenderPlan]:
  1327	        candidate, evidence = pinned_finalizer
  1328	        if candidate.id == _DIRECT_FINALIZER_ID:
  1329	            # No executable finalizer pinned: the segment must already match
  1330	            # the canonical plan profile exactly.
  1331	            if len(segment_results) != 1:
  1332	                raise_internal_error(
  1333	                    backend=_CORE_BACKEND_ID,
  1334	                    message="direct finalizer received multiple segments",
  1335	                    recovery_command="select a planner that pins an executable finalizer",
  1336	                    details={"segment_count": len(segment_results)},
  1337	                )
  1338	            result = self._validator(
  1339	                segment_results[0],
  1340	                expected_profile=plan.profile,
  1341	                workspace_root=workspace,
  1342	            )
  1343	            return result, plan
  1344	
  1345	        ownerships = {item.audio_ownership for item in segment_results}
  1346	        if ownerships == {AudioOwnership.PASSTHROUGH}:
  1347	            requested_audio = AudioOwnership.PASSTHROUGH
  1348	        elif plan.profile.has_audio:
  1349	            requested_audio = AudioOwnership.RENDERED
  1350	        else:
  1351	            requested_audio = AudioOwnership.NONE
  1352	        support_audio = (
  1353	            None
  1354	            if requested_audio is AudioOwnership.PASSTHROUGH
  1355	            and plan.profile.has_audio
  1356	            else requested_audio
  1357	        )
  1358	        support_request = RenderRequest(
  1359	            schema_version=SCHEMA_VERSION,
  1360	            timeline_path=request.timeline_path,
  1361	            assets_registry_path=request.assets_registry_path,
  1362	            output_name=request.output_name,
  1363	            audio=support_audio,
  1364	            profile=plan.profile,
  1365	            backend_config=request.backend_config,
  1366	            metadata=request.metadata,
  1367	        )
  1368	        report = self._support(
  1369	            candidate,
  1370	            request=support_request,
  1371	            workspace=workspace,
  1372	            registry=self.finalizers,
  1373	        )
  1374	        if not report.supported:
  1375	            self._unsupported_report(report, registry=self.finalizers)
  1376	        prior_finalizer = plan.finalizer
  1377	        finalizer_resolution = replace(
  1378	            self._finalizer_resolution(
  1379	                candidate,
  1380	                evidence,
  1381	                support=report,
  1382	            ),
  1383	            alias_chain=(
  1384	                prior_finalizer.alias_chain
  1385	                or list(evidence.get("alias_chain") or [])
  1386	            ),
  1387	            override=prior_finalizer.override or evidence.get("override"),
  1388	        )
  1389	        plan = replace(plan, finalizer=finalizer_resolution)
  1390	        finalize_request = FinalizeRequest(
  1391	            schema_version=SCHEMA_VERSION,
  1392	            plan=plan,
  1393	            artifacts=[item.video for item in segment_results],
  1394	            output_name=request.output_name,
  1395	            backend_config={
  1396	                candidate.id: dict(request.backend_config.get(candidate.id, {}))
  1397	            }
  1398	            if candidate.id in request.backend_config
  1399	            else {},
  1400	            metadata=request.metadata,
  1401	        )
  1402	        self._observe("finalize", backend=candidate.id)
  1403	        response = self._run_command(
  1404	            candidate,
  1405	            "finalize",
  2048	    output = tmp_path / "real-hybrid.mp4"
  2049	
  2050	    service.render_request(
  2051	        replace(
  2052	            _request(tmp_path),
  2053	            timeline_path=str(timeline_path),
  2054	            assets_registry_path=str(assets_path),
  2055	        ),
  2056	        selector="hybrid",
  2057	        out_path=output,
  2058	    )
  2059	
  2060	    assert output.is_file()
  2061	    assert output.stat().st_size > 0
  2062	    sidecars = list(tmp_path.glob("*.provenance.json"))
  2063	    assert sidecars == [Path(f"{output}.provenance.json")]
  2064	    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
  2065	    assert payload["routing"]["requested_engine"] == "hybrid"
  2066	    resolved = payload["routing"]["resolved_policy"]
  2067	    assert resolved["planner"] == "rendering.legacy_hybrid"
  2068	    assert resolved["finalizer"] == "rendering.ffmpeg-finalizer"
  2069	
  2070	
  2071	def _real_audio_reactive_inputs(tmp_path: Path) -> tuple[Path, Path]:
  2072	    """A two-clip timeline the strict FFmpeg backend renders through its
  2073	    audio-reactive colour specialization (real AAC audio source)."""
  2074	    root = tmp_path / "reactive"
  2075	    root.mkdir(exist_ok=True)
  2076	    audio_path = root / "tone.wav"
  2077	    subprocess.run(
  2078	        [
  2079	            "ffmpeg",
  2080	            "-hide_banner",
  2081	            "-loglevel",
  2082	            "error",
  2083	            "-y",
  2084	            "-f",
  2085	            "lavfi",
  2086	            "-i",
  2087	            "sine=frequency=440:sample_rate=48000:duration=0.5",
  2088	            str(audio_path),
  2089	        ],
  2090	        check=True,
  2091	        capture_output=True,
  2092	        text=True,
  2093	    )
  2094	    timeline_path = root / "timeline.json"
  2095	    assets_path = root / "assets.json"
  2096	    timeline_path.write_text(
  2097	        json.dumps(
  2098	            {
  2099	                "theme": "banodoco-default",
  2100	                "theme_overrides": {
  2101	                    "visual": {"canvas": {"width": 640, "height": 360, "fps": 48}}
  2102	                },
  2103	                "tracks": [
  2104	                    {"id": "colour", "kind": "visual", "label": "Colour"},
  2105	                    {"id": "audio", "kind": "audio", "label": "Audio"},
  2106	                ],
  2107	                "clips": [
  2108	                    {
  2109	                        "id": "colour_map",
  2110	                        "at": 0,
  2111	                        "track": "colour",
  2112	                        "clipType": "audio-reactive-colour",
  2113	                        "hold": 0.5,
  2114	                        "params": {
  2115	                            "schemaVersion": 1,
  2116	                            "initialColor": "#102030",
  2117	                            "events": [
  2118	                                {"id": "a", "frame": 3, "color": "#D47795"},
  2119	                                {"id": "b", "frame": 8, "color": "#26A7D0"},
  2120	                                {"id": "c", "frame": 17, "color": "#B59432"},
  2121	                            ],
  2122	                        },
  2123	                    },
  2124	                    {
  2125	                        "id": "source_audio",
  2126	                        "at": 0,
  2127	                        "track": "audio",
  2128	                        "clipType": "media",
  2129	                        "asset": "audio",
  2130	                        "from": 0,
  2131	                        "to": 0.5,
  2132	                    },
  2133	                ],
  2134	            }
  2135	        ),
  2136	        encoding="utf-8",
  2137	    )
  2138	    assets_path.write_text(
  2139	        json.dumps(
  2140	            {
  2141	                "assets": {
  2142	                    "audio": {
  2143	                        "file": str(audio_path),
  2144	                        "type": "audio/wav",
  2145	                        "duration": 0.5,
  2146	                    }
  2147	                }
  2148	            }
  2149	        ),
  2150	        encoding="utf-8",
  2151	    )
  2152	    return timeline_path, assets_path
  2153	
  2154	
  2155	def test_real_ffmpeg_audio_reactive_through_generic_service(
  2156	    tmp_path: Path,
  2157	) -> None:
  2158	    """The service drives the real FFmpeg backend through its audio-reactive
  2159	    colour specialization end to end (no fake transport)."""
  2160	    _require_ffmpeg()
  2161	    timeline_path, assets_path = _real_audio_reactive_inputs(tmp_path)
  2162	    service = _real_service(tmp_path)
  2163	    output = tmp_path / "real-reactive.mp4"
  2164	
  2165	    service.render_request(
  2166	        replace(
  2167	            _request(tmp_path),
  2168	            timeline_path=str(timeline_path),
  2169	            assets_registry_path=str(assets_path),
  2170	        ),
  2171	        selector="rendering.ffmpeg",
  2172	        out_path=output,
  2173	    )
  2174	
  2175	    assert output.is_file()

codex
Issues:

- HIGH — Executable-finalizer provenance is inconsistent. The direct path overwrites the renderer result, then records only the finalizer artifact/fragments at [service.py:505](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:505), losing renderer artifact lineage, backend fragments, and v1 compatibility data. Conversely, single-segment planner finalization records only the renderer fragments at [service.py:443](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:443), omitting the executed finalizer fragment. Preserve the segment result separately and merge both results’ fragments.
tokens used
92,886
Issues:

- HIGH — Executable-finalizer provenance is inconsistent. The direct path overwrites the renderer result, then records only the finalizer artifact/fragments at [service.py:505](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:505), losing renderer artifact lineage, backend fragments, and v1 compatibility data. Conversely, single-segment planner finalization records only the renderer fragments at [service.py:443](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:443), omitting the executed finalizer fragment. Preserve the segment result separately and merge both results’ fragments.
