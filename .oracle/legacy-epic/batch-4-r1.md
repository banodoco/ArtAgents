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

codex
The Megado checkpoint protocol calls for a binary oracle review. I’m also delegating an independent pass over the seven cited regressions while I verify the service/facade changes and targeted tests locally.
2026-08-12T15:16:41.543189Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:16:41.543369Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:16:41.543387Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git diff --stat a72729db..98f4edea && sed -n '1,240p' .oracle/checkins/batch-4.md && rg -n \"Batch 4|batch 4|rendering\" .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 302ms:
?? .oracle/checkins/batch-4-r1.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
98f4edeac9a188c79a0aa53f2e78a119ed1812bc
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-4.md                        | 9091 ++++++++++++++++++++
 astrid/core/rendering/service.py                   |   80 +-
 .../rendering/executors/render/legacy_engine.py    |  392 +
 astrid/packs/rendering/executors/render/run.py     |  386 +-
 .../packs/rendering/planners/legacy_hybrid/run.py  |   16 +-
 tests/core/rendering/test_service.py               |  238 +-
 .../test_legacy_renderer_characterization.py       |   69 +-
 .../rendering/test_render_remotion_registry.py     |   13 +-
 8 files changed, 9857 insertions(+), 428 deletions(-)
Reading additional input from stdin...
2026-08-12T14:29:18.092351Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:18.093453Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:18.093463Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ff660-a736-7951-a3c4-45f054fe6cc7
--------
user
# Megado Checkpoint — Batch 4

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
Previous head C4-batch3-done (9bf9db88). Batch 4 committed as `a72729db`.
Incremental diff: `git diff C4-batch3-done..a72729db`.

## What Batch 4 was supposed to deliver (tasklist)

1. `RenderService` (core, `astrid/core/rendering/service.py`) with the FROZEN
   selection order: legacy translation → alias → override → winner →
   eligibility → support → invoke/validate → audio/finalize → publish.
   - `ffmpeg` → strict `rendering.ffmpeg`; `remotion` → characterized legacy
     policy (FFmpeg for eligible media/audio-specialized timelines else
     remotion, with auto-routing warning); `hybrid` → `rendering.legacy_hybrid`
     planner (NEVER a renderer id); qualified ids strict.
   - One video + one committed sidecar per success; failures clean temps.
2. Neutral facade (`astrid/packs/rendering/executors/render/run.py` delegates
   to `_default_service().render(...)`; `executor.yaml` neutral selector +
   namespaced config + `output_name` input with validation;
   `_normalize_render_command_compat` removed).
3. Additive provenance v2: routing lineage (requested engine → resolved
   backend + auto-route reason), all v1 projections preserved, core/backend
   fragment ownership, lock-aware cleanup, one sidecar per success.
4. `rendering.legacy_hybrid` planner port
   (`astrid/packs/rendering/planners/legacy_hybrid/`, planner.yaml + run.py):
   integer half-open `[start_frame,end_frame)` windows, transition/handle
   preservation, support-based assignment, explicit finalizer
   (`rendering.ffmpeg-finalizer`), non-recursive dispatch, aligned segment
   provenance.
5. Routing/hybrid matrix: strict/legacy selectors, alias/override/trust,
   output-name rejection + hype.mp4 sentinel, every built-in path (remotion,
   ffmpeg, optimized ffmpeg, audio-reactive, hybrid single + multi) → exactly
   one video + one sidecar, raw mixed-plan (deterministic fixture executes),
   audio control matrix, failure cleanup, attachments, crash recovery.

## Evidence

- `pytest -q tests/core/rendering/`: 367 passed.
- Full consolidated acceptance: 977 passed, 2 skipped, 1 failed
  (pre-existing env-dependent model-trends fixture test, documented in
  `.oracle/baseline.md`, unchanged).
- `tests/packs/rendering/test_builtin_registration.py` now asserts
  `rendering.legacy_hybrid` in the static planner registry (no backend import
  during inspection).
- Facade tests assert delegation to the service seam (`selector` passthrough),
  not backend internals.

## Verdict

Binary `PASS` or issues. On PASS, Batch 5 (caller migration + semantic
parity + M1 freeze) begins. Say exactly `PASS` if clean.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` checkpoint workflow and delegating independent diff review per the repository instructions. I’ll return exactly `PASS` only if the incremental change is clean.
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
12:- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
16:- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.
20:- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
23:- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
24:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
45:- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
56:- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
73:## Batch 4 — Generic routing, provenance, and hybrid planning
80:- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
90:- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
112:- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
114:- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
117:- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
128:- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
130:- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
136:- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
138:- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
140:- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
141:- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.
162:- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
164:- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
165:- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
177:- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.

exec
/bin/zsh -lc 'tail -n 260 .oracle/checkins/batch-4.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
temporal window; V1 does not combine overlapping renderer layers.

## Finalization

`FinalizeRequest` contains `schema_version: 1`, the complete `plan`, an ordered
`artifacts` array, neutral `output_name`, selected finalizer configuration,
and metadata. Artifacts correspond one-for-one with plan segments. A finalizer
returns the same `RenderResult` shape as a renderer. Empty plans are not sent
to finalizers. Before invocation, the host rejects any attachment name reused
by two segment artifacts. After invocation, it verifies that the final video's
attachment map contains the unchanged union of all input attachments;
additional globally unique finalizer-created attachments are permitted.

Final assembly is explicit even when it is a one-segment pass-through.
Finalizers probe every input and compare it with the plan profile. Compatible
segments may stream-copy. Otherwise the finalizer normalizes dimensions,
rational FPS/time base, container, video codec/profile/level, pixel format,
audio codec/sample rate/channel layout, and audio presence. Every performed
normalization is appended to `normalization`. The finalizer preserves
attachments it does not understand. The first built-in finalizer uses FFmpeg;
its one canonical qualified ID is `rendering.ffmpeg-finalizer`. FFmpeg is not
part of the generic contract.

## Structured errors

   520	        return Path(published)
   521	
   522	    def _select(
   523	        self,
   524	        request: RenderRequest,
   525	        *,
   526	        policy: _SelectionPolicy,
   527	        workspace: Path,
   528	    ) -> _ResolvedCapability:
   529	        registry: RendererRegistry | PlannerRegistry = (
   530	            self.renderers if policy.kind == "renderer" else self.planners
   531	        )
   532	        rejected: list[dict[str, Any]] = []
   533	        for index, target in enumerate(policy.targets):
   534	            try:
   535	                candidate, evidence = self._resolve_candidate(
   536	                    registry,
   537	                    target,
   538	                    kind=policy.kind,
   539	                )
   540	                report = self._support(
   541	                    candidate,
   542	                    request=request,
   543	                    workspace=workspace,
   544	                    registry=registry,
   545	                )
   546	            except RendererException as exc:
   547	                if not policy.auto_route or index == len(policy.targets) - 1:
   548	                    raise
   549	                if exc.error.kind not in {"unsupported", "binary_missing"}:
   550	                    raise
   551	                rejected.append(exc.error.to_dict())
   552	                continue
   553	            if not report.supported:
   554	                rejected.append(report.to_dict())
   555	                if policy.auto_route and index < len(policy.targets) - 1:
   556	                    continue
   557	                self._unsupported_report(report, registry=registry)
   558	            if policy.auto_route and index == 0:
   559	                warnings.warn(
   560	                    f"legacy selector {policy.requested!r} auto-routed this supported "
   561	                    f"timeline to {candidate.id}; select a qualified renderer "
   562	                    "id for strict routing",
   563	                    LegacyRenderRoutingWarning,
   564	                    stacklevel=4,
   565	                )
   566	            return _ResolvedCapability(candidate, evidence, report)
   567	
   568	        alternatives = self._alternatives(registry)
   569	        raise_unsupported_error(
   570	            backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
   571	            message=f"no renderer supports legacy selector {policy.requested!r}",
   572	            recovery_command=self._recovery_for(alternatives),
   573	            details={"attempts": rejected, "alternatives": alternatives},
   574	        )
   575	
   139	def _routing_record(
   140	    legacy_engine: str,
   141	    plan: RenderPlan,
   142	    resolved_policy: Mapping[str, Any],
   143	) -> dict[str, Any]:
   144	    """Derive selected-policy lineage and visible legacy translation.
   145	
   146	    The service's legacy ``remotion`` policy tries the qualified FFmpeg route
   147	    first and emits a warning when that supported route wins.  The plan pins
   148	    the selected renderer but cannot by itself explain why its legacy
   149	    ``engine`` projection still says ``remotion``.  Record that explanation
   150	    additively while leaving the frozen nested resolution records authoritative
   151	    for aliases, overrides, trust, manifests, and support decisions.
   152	    """
   153	
   154	    renderer_ids = list(resolved_policy["renderers"])
   155	    resolved_backend = renderer_ids[0] if len(renderer_ids) == 1 else None
   156	    auto_routed = (
   157	        legacy_engine == "remotion"
   158	        and len(plan.segments) == 1
   159	        and _resolution_request_id(plan.segments[0]) == "rendering.ffmpeg"
   160	    )
   161	    auto_route_reason = None
   162	    if auto_routed:
   163	        auto_route_reason = (
   164	            "legacy selector 'remotion' auto-routed the supported request to "
   165	            f"{plan.segments[0].renderer.id}"
   166	        )
   167	    return {
   168	        "requested_engine": legacy_engine,
   169	        "requested_policy": plan.requested_policy,
   170	        "resolved_policy": dict(resolved_policy),
   171	        "resolved_backend": resolved_backend,
   172	        "resolved_backends": renderer_ids,
   173	        "auto_route": auto_routed,
   174	        "auto_route_reason": auto_route_reason,
   175	        "segment_reasons": dict(plan.reasons),
   176	    }
   177	
   178	
   350	        profile=profile,
   351	        audio=audio,
   352	    )
   353	
   354	
   355	def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
   356	    if not timeline_path.exists():
   357	        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
   358	    if not assets_path.exists():
   359	        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
   360	    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   361	    canonical_profile = resolve_render_profile(
   362	        timeline_data,
   363	        timeline.load_registry(assets_path),
   364	        theme=remotion_kwargs.get("theme_path"),
   365	        themes_root=REPO_ROOT / "themes",
   366	    )
   367	    segments = _hybrid_segments(
   368	        timeline_data,
   369	        fps=Fraction(*canonical_profile.fps_rational),
   370	    )
   371	    if (
   372	        canonical_profile.fps_rational[1] == 1
   373	        and len(segments) == 1
   374	        and segments[0]["engine"] == "ffmpeg"
   375	    ):
   376	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
   377	
   378	    publication_out = out_path  # unresolved: publication symlink-guards it
   379	    resolved_out = out_path.resolve()
   380	    resolved_out.parent.mkdir(parents=True, exist_ok=True)
   381	    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
   382	        tmp_dir = Path(tmp)
   383	        segment_paths: list[Path] = []
   384	        segment_provenance: list[dict[str, Any]] = []
   385	        for index, segment in enumerate(segments):
   386	            engine = str(segment["engine"])
   387	            start = float(segment["from"])
   388	            end = float(segment["to"])
   389	            segment_dir = tmp_dir / f"{index:04d}-{engine}"
   390	            segment_dir.mkdir(parents=True, exist_ok=True)
   391	            segment_timeline_path = segment_dir / "timeline.json"
   392	            segment_out_path = segment_dir / "segment.mp4"
   393	            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
   394	            if canonical_profile.fps_rational[1] != 1:
   395	                # Both extracted legacy renderers accept an integer canvas
   396	                # rate.  Render the window at the nearest rate, then let the
   397	                # finalizer normalize to the exact canonical rational rate.
   398	                render_rate = max(
   399	                    1,
   400	                    round(Fraction(*canonical_profile.fps_rational)),
   401	                )
   402	                overrides = dict(segment_timeline.get("theme_overrides", {}))
   403	                visual = dict(overrides.get("visual", {}))
   404	                canvas = dict(visual.get("canvas", {}))
   405	                canvas["fps"] = render_rate
   406	                visual["canvas"] = canvas
   407	                overrides["visual"] = visual
   408	                segment_timeline["theme_overrides"] = overrides
   409	            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
   410	            if engine == "ffmpeg":
   411	                _render_ffmpeg_media(
   412	                    segment_timeline_path,
   413	                    assets_path,
   414	                    segment_out_path,
   415	                    _previous_outputs=(),
   416	                )
   417	            else:
   418	                render(
   419	                    segment_timeline_path,
   420	                    assets_path,
   421	                    segment_out_path,
   422	                    engine="remotion",
   423	                    **remotion_kwargs,
   424	                )
   425	                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
   426	                if sidecar_path.exists():
   427	                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
   428	            segment_paths.append(segment_out_path)
   429	        staged_video = tmp_dir / "final" / out_path.name
   430	        staged_video.parent.mkdir(parents=True, exist_ok=True)
   568	    validate_output_name(out_path.name)
   569	    previous_outputs = (
   570	        ()
   571	        if keep_previous_renders
   572	        else _previous_render_outputs_for_timeline(out_path, timeline_path)
   573	    )
   574	    config = _legacy_backend_config(
   575	        project_dir=project_dir,
   576	        composition_id=composition_id,
   577	        theme_path=theme_path,
   578	        min_free_gb=min_free_gb,
   579	    )
   580	    for key, value in (backend_config or {}).items():
   581	        if value is not None:
   582	            config[str(key)] = dict(value)
   583	    return _default_service().render(
   584	        timeline_path,
   585	        assets_path,

collab: Wait
collab: Wait
codex
Issues:

- HIGH — [service.py:1265](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1265) bypasses the explicit finalizer for every single-segment plan. Normalizable profile mismatches fail, and audio completion runs prematurely at line 1219.

- HIGH — Hybrid alias/override routing is broken. The resolver returns the resolved backend, but [legacy_hybrid/run.py:758](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/planners/legacy_hybrid/run.py:758) compares it with the unresolved configured ID. Valid aliases and overrides are rejected or skipped.

- HIGH — Hybrid renderer/finalizer alias and override lineage is discarded when the service re-resolves emitted target IDs and replaces the planner’s resolution records at [service.py:1169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1169) and [service.py:1235](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1235).

- HIGH — Legacy `remotion` fallback provenance drops the rejected FFmpeg attempt. Rejection evidence accumulated at [service.py:532](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:532) is discarded when Remotion succeeds, so the sidecar lacks complete routing/support lineage.

- MEDIUM — The facade remains concrete and recursive: it imports backend implementations and retains `_render_hybrid()` with backend branching and recursive rendering at [run.py:355](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:355), contrary to the required neutral facade.

- MEDIUM — Explicit backend configuration replaces legacy settings rather than overlaying them at [run.py:580](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:580), silently dropping project/theme/composition values.

- MEDIUM — Conflicting `engine` and `backend` inputs silently prefer `backend` at [run.py:645](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:645), bypassing the service’s conflict validation.

- MEDIUM — The claimed every-built-in-path matrix uses `FakeTransport`; optimized/audio-reactive settings are not exercised by real backends, and hybrid uses a fixture renderer at [test_service.py:1462](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1462).
tokens used
279,659
Issues:

- HIGH — [service.py:1265](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1265) bypasses the explicit finalizer for every single-segment plan. Normalizable profile mismatches fail, and audio completion runs prematurely at line 1219.

- HIGH — Hybrid alias/override routing is broken. The resolver returns the resolved backend, but [legacy_hybrid/run.py:758](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/planners/legacy_hybrid/run.py:758) compares it with the unresolved configured ID. Valid aliases and overrides are rejected or skipped.

- HIGH — Hybrid renderer/finalizer alias and override lineage is discarded when the service re-resolves emitted target IDs and replaces the planner’s resolution records at [service.py:1169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1169) and [service.py:1235](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1235).

- HIGH — Legacy `remotion` fallback provenance drops the rejected FFmpeg attempt. Rejection evidence accumulated at [service.py:532](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:532) is discarded when Remotion succeeds, so the sidecar lacks complete routing/support lineage.

- MEDIUM — The facade remains concrete and recursive: it imports backend implementations and retains `_render_hybrid()` with backend branching and recursive rendering at [run.py:355](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:355), contrary to the required neutral facade.

- MEDIUM — Explicit backend configuration replaces legacy settings rather than overlaying them at [run.py:580](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:580), silently dropping project/theme/composition values.

- MEDIUM — Conflicting `engine` and `backend` inputs silently prefer `backend` at [run.py:645](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:645), bypassing the service’s conflict validation.

- MEDIUM — The claimed every-built-in-path matrix uses `FakeTransport`; optimized/audio-reactive settings are not exercised by real backends, and hybrid uses a fixture renderer at [test_service.py:1462](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1462).

exec
/bin/zsh -lc 'git diff --unified=100 a72729db..98f4edea -- astrid/core/rendering/service.py astrid/packs/rendering/planners/legacy_hybrid/run.py astrid/packs/rendering/executors/render/run.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/service.py b/astrid/core/rendering/service.py
index e2665b17..c3114927 100644
--- a/astrid/core/rendering/service.py
+++ b/astrid/core/rendering/service.py
@@ -1,196 +1,197 @@
 """Backend-neutral orchestration for one committed timeline render.
 
 ``RenderService`` is the only core component that understands the legacy
 renderer selector spellings.  Everything after that compatibility boundary is
 resolved through the rendering registries and invoked through protocol v1.
 Backends write private artifacts in an invocation workspace; the service
 validates them and performs exactly one locked publication at the end.
 """
 
 from __future__ import annotations
 
 import hashlib
 import json
 import math
 import re
 import warnings
 from collections.abc import Callable, Iterable, Mapping, Sequence
-from dataclasses import dataclass, replace
+from dataclasses import dataclass, field, replace
 from fractions import Fraction
 from pathlib import Path
 from tempfile import TemporaryDirectory
 from typing import Any, Literal
 
 from astrid.core.foundation.atomic_io import write_json_atomic
 from astrid.core.foundation.hash import sha256_file
 
 from .artifacts import validate_render_result
 from .contracts import (
     SCHEMA_VERSION,
     AudioOwnership,
     FinalizeRequest,
     FinalizerResolution,
     FrameWindow,
     PlannerResolution,
     RenderPlan,
     RenderRequest,
     RenderResult,
     RendererResolution,
     RenderSegment,
     SupportReport,
     compute_request_digest,
 )
 from .errors import (
     RendererException,
     raise_internal_error,
     raise_invalid_artifact_error,
     raise_protocol_error,
     raise_renderer_error,
     raise_unsupported_error,
 )
 from .provenance import assemble_provenance_v2
 from .publication import publish_render_result
 from .registry import (
     FinalizerRegistry,
     PlannerRegistry,
     RendererRegistry,
     RenderingCandidate,
     RenderingRegistryError,
     load_default_registries,
 )
 from .transport import CommandTransport
 
 
 _QUALIFIED_ID_RE = re.compile(
     r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$"
 )
 _CORE_BACKEND_ID = "astrid.core"
 _DIRECT_PLANNER_ID = "astrid.direct"
 _DIRECT_PLANNER_DIGEST = hashlib.sha256(b"astrid.direct/v1").hexdigest()
 _DIRECT_FINALIZER_ID = "astrid.direct-finalizer"
 _DIRECT_FINALIZER_DIGEST = hashlib.sha256(
     b"astrid.direct-finalizer/v1"
 ).hexdigest()
 
 CapabilityKind = Literal["renderer", "planner", "finalizer"]
 StageObserver = Callable[[str, Mapping[str, Any]], None]
 AudioCompleter = Callable[..., RenderResult]
 
 
 class LegacyRenderRoutingWarning(UserWarning):
     """A legacy selector selected a different qualified backend."""
 
 
 @dataclass(frozen=True)
 class _SelectionPolicy:
     requested: str
     kind: Literal["renderer", "planner"]
     targets: tuple[str, ...]
     auto_route: bool = False
 
 
 @dataclass(frozen=True)
 class _ResolvedCapability:
     candidate: RenderingCandidate[Any]
     evidence: dict[str, Any]
     support: SupportReport
+    rejected: list[dict[str, Any]] = field(default_factory=list)
 
 
 def _translate_legacy_selector(selector: str | None) -> _SelectionPolicy:
     """Translate the three historical names, and no other short names.
 
     The ordered pair for legacy ``remotion`` is its characterized compatibility
     policy: request-sensitive FFmpeg support gets the first opportunity, then
     Remotion.  Qualified selectors contain no fallback and are therefore
     strict (normal registry aliases and overrides still apply).
     """
 
     if selector is None:
         selector = "remotion"
     if selector == "ffmpeg":
         return _SelectionPolicy(selector, "renderer", ("rendering.ffmpeg",))
     if selector == "remotion":
         return _SelectionPolicy(
             selector,
             "renderer",
             ("rendering.ffmpeg", "rendering.remotion"),
             auto_route=True,
         )
     if selector == "hybrid":
         return _SelectionPolicy(
             selector,
             "planner",
             ("rendering.legacy_hybrid",),
         )
     if isinstance(selector, str) and _QUALIFIED_ID_RE.fullmatch(selector):
         return _SelectionPolicy(selector, "renderer", (selector,))
     raise_unsupported_error(
         backend=_CORE_BACKEND_ID,
         message=f"unknown renderer selector {selector!r}",
         recovery_command=(
             "select a qualified renderer id or one of the legacy selectors: "
             "remotion, ffmpeg, hybrid"
         ),
         details={
             "selector": selector if isinstance(selector, str) else repr(selector),
             "legacy_selectors": ["remotion", "ffmpeg", "hybrid"],
         },
     )
 
 
 class RenderService:
     """Resolve, invoke, validate, finalize, and publish one timeline render.
 
     Registries and lifecycle functions are injectable so callers can embed the
     service without importing backend code, and so the orchestration order can
     be tested without spawning media tools.
     """
 
     def __init__(
         self,
         renderer_registry: RendererRegistry | None = None,
         planner_registry: PlannerRegistry | None = None,
         finalizer_registry: FinalizerRegistry | None = None,
         *,
         registries: tuple[
             RendererRegistry, PlannerRegistry, FinalizerRegistry
         ]
         | None = None,
         project_root: str | Path | None = None,
         extra_pack_roots: tuple[str, ...] = (),
         include_installed: bool = True,
         transport: Any | None = None,
         transport_factory: Callable[[str], Any] = CommandTransport,
         validator: Callable[..., RenderResult] = validate_render_result,
         publisher: Callable[..., Path] = publish_render_result,
         provenance_builder: Callable[..., dict[str, Any]] = assemble_provenance_v2,
         audio_completer: AudioCompleter | None = None,
         stage_observer: StageObserver | None = None,
         finalizer_id: str | None = None,
     ) -> None:
         supplied = (
             renderer_registry,
             planner_registry,
             finalizer_registry,
         )
         if registries is not None and any(item is not None for item in supplied):
             raise ValueError(
                 "pass either registries= or individual rendering registries, not both"
             )
         if registries is None:
             if all(item is None for item in supplied):
                 registries = load_default_registries(
                     project_root,
                     extra_pack_roots=extra_pack_roots,
                     include_installed=include_installed,
                 )
             elif any(item is None for item in supplied):
                 raise ValueError("all three rendering registries must be supplied together")
             else:
                 registries = supplied  # type: ignore[assignment]
         self.renderers, self.planners, self.finalizers = registries
         self.renderer_registry = self.renderers
         self.planner_registry = self.planners
         self.finalizer_registry = self.finalizers
         self._transport = transport
         self._transport_factory = transport_factory
@@ -466,201 +467,206 @@ class RenderService:
                 backend=selected.candidate.id,
             )
             if final_result.video.profile != plan.profile or (
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
-            return _ResolvedCapability(candidate, evidence, report)
+            return _ResolvedCapability(
+                candidate,
+                evidence,
+                report,
+                rejected=list(rejected),
+            )
 
         alternatives = self._alternatives(registry)
         raise_unsupported_error(
             backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
             message=f"no renderer supports legacy selector {policy.requested!r}",
             recovery_command=self._recovery_for(alternatives),
             details={"attempts": rejected, "alternatives": alternatives},
         )
 
     def _resolve_candidate(
         self,
         registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
         requested_id: str,
         *,
         kind: CapabilityKind,
         observe: bool = True,
     ) -> tuple[RenderingCandidate[Any], dict[str, Any]]:
         try:
             candidate = registry.get(requested_id)
             evidence = registry.resolve_evidence(requested_id)
         except RenderingRegistryError as exc:
             evidence: dict[str, Any] = {}
             try:
                 evidence = registry.resolve_evidence(requested_id)
             except RenderingRegistryError:
                 evidence = dict(exc.details)
             if observe:
                 self._observe_resolution(requested_id, evidence, candidate=None)
             alternatives = self._alternatives(registry)
             details = {
                 "registry_error": exc.to_dict(),
                 "alternatives": alternatives,
             }
             raise_unsupported_error(
                 backend=(
                     requested_id
                     if _QUALIFIED_ID_RE.fullmatch(requested_id)
                     else _CORE_BACKEND_ID
                 ),
                 message=str(exc),
                 recovery_command=self._recovery_for(alternatives),
                 details=details,
             )
         if observe:
             self._observe_resolution(requested_id, evidence, candidate=candidate)
         if (
             evidence.get("resolved_id") != candidate.id
             or evidence.get("manifest_digest") != candidate.manifest_digest
             or evidence.get("priority_index", evidence.get("priority"))
             != candidate.priority_index
         ):
             raise_internal_error(
                 backend=_CORE_BACKEND_ID,
                 message=(
                     f"{kind} registry changed while resolving {requested_id!r}"
                 ),
                 recovery_command="retry after renderer registry updates have completed",
                 details={
                     "requested_id": requested_id,
                     "candidate": candidate.to_dict(),
                     "resolution_evidence": evidence,
                 },
             )
         if not candidate.execution_eligible:
             alternatives = self._alternatives(registry)
             raise_unsupported_error(
                 backend=candidate.id,
                 message=f"{kind} {candidate.id!r} is not execution-eligible",
                 recovery_command=self._recovery_for(alternatives),
                 details={
                     "eligibility": candidate.eligibility.to_dict(),
                     "alternatives": alternatives,
                 },
             )
         return candidate, evidence
 
     def _observe_resolution(
         self,
         requested_id: str,
         evidence: Mapping[str, Any],
         *,
         candidate: RenderingCandidate[Any] | None,
     ) -> None:
         alias_chain = list(evidence.get("alias_chain") or [])
         self._observe(
             "alias",
             requested_id=requested_id,
             canonical_id=evidence.get("canonical_id", requested_id),
             alias_chain=alias_chain,
         )
         self._observe(
             "override",
             requested_id=requested_id,
             override=evidence.get("override"),
         )
         self._observe(
             "winner",
             requested_id=requested_id,
             resolved_id=(
                 candidate.id if candidate is not None else evidence.get("resolved_id")
@@ -1075,299 +1081,342 @@ class RenderService:
             return cls._timeline_number(clip["to"], "clip.to")
         return clip_start
 
     @staticmethod
     def _timeline_number(value: Any, label: str) -> Fraction:
         if isinstance(value, bool) or not isinstance(value, (int, float)):
             raise TypeError(f"{label} must be a finite number")
         if not math.isfinite(float(value)):
             raise ValueError(f"{label} must be finite")
         return Fraction(str(value))
 
     @staticmethod
     def _validate_segment_duration(
         result: RenderResult,
         *,
         segment: RenderSegment,
         canonical_profile: Any,
         backend: str,
     ) -> None:
         RenderService._validate_planned_duration(
             result,
             planned_frames=segment.window.duration_frames,
             canonical_profile=canonical_profile,
             backend=backend,
             label="renderer artifact",
         )
 
     @staticmethod
     def _validate_planned_duration(
         result: RenderResult,
         *,
         planned_frames: int,
         canonical_profile: Any,
         backend: str,
         label: str,
     ) -> None:
         artifact_seconds = Fraction(
             result.video.duration_frames, 1
         ) / Fraction(*result.video.profile.fps_rational)
         canonical_fps = Fraction(*canonical_profile.fps_rational)
         planned_seconds = Fraction(planned_frames, 1) / canonical_fps
         delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
         if delta_frames <= canonical_profile.duration_tolerance:
             return
         raise_invalid_artifact_error(
             backend=backend,
             message=f"{label} duration does not match its planned frame window",
             recovery_command="rerender the exact planned segment window and retry",
             details={
                 "planned_duration_frames": planned_frames,
                 "artifact_duration_frames": result.video.duration_frames,
                 "canonical_delta_frames": [
                     delta_frames.numerator,
                     delta_frames.denominator,
                 ],
                 "tolerance_frames": canonical_profile.duration_tolerance,
             },
         )
 
     def _execute_planner(
         self,
         request: RenderRequest,
         *,
         policy: _SelectionPolicy,
         selected: _ResolvedCapability,
         workspace: Path,
     ) -> tuple[
         RenderPlan,
         list[RenderResult],
         tuple[RenderingCandidate[Any], dict[str, Any]],
     ]:
         planner_request = request.for_backend(selected.candidate.id)
         self._observe("invoke", backend=selected.candidate.id, verb="plan")
         response = self._run_command(
             selected.candidate,
             "plan",
             planner_request,
             workspace=workspace,
         )
         if not isinstance(response, RenderPlan):
             raise_protocol_error(
                 backend=selected.candidate.id,
                 message="plan operation did not return a RenderPlan",
                 details={"received_type": type(response).__name__},
             )
         # The registry selection is authoritative.  A planner response may
         # still carry the pre-alias/pre-override identity it was asked to
         # replace (notably during compatibility routing); normalize that
         # self-description to the selected candidate and its complete
         # resolution evidence below.
         planner_resolution = self._planner_resolution(selected)
         normalized_segments: list[RenderSegment] = []
         segment_results: list[RenderResult] = []
         input_hashes = self._input_hashes(request)
         for index, segment in enumerate(response.segments):
             candidate, evidence = self._resolve_candidate(
                 self.renderers,
                 segment.renderer.id,
                 kind="renderer",
             )
+            # The planner already resolved aliases/overrides itself and
+            # recorded that lineage on the segment.  Re-resolving the emitted
+            # id from scratch would discard the alias chain, so merge: the
+            # service's resolution is authoritative for identity/trust while
+            # the planner's recorded lineage survives when present.
+            planner_renderer = segment.renderer
             native_request = replace(
                 request,
                 window=segment.window,
                 output_name=f"segment-{index:04d}.mp4",
             )
             segment_request, materialized_hashes = self._segment_request(
                 native_request,
                 candidate=candidate,
                 segment=segment,
                 index=index,
                 workspace=workspace,
             )
             report = self._support(
                 candidate,
                 request=segment_request,
                 workspace=workspace,
                 registry=self.renderers,
             )
             if not report.supported:
                 self._unsupported_report(report, registry=self.renderers)
             resolved = _ResolvedCapability(candidate, evidence, report)
+            merged_renderer = replace(
+                planner_renderer,
+                id=candidate.id,
+                source_pack=self._source_pack(candidate, evidence),
+                manifest_digest=candidate.manifest_digest,
+                trust_eligibility=candidate.eligibility.to_dict(),
+                alias_chain=(
+                    planner_renderer.alias_chain
+                    or list(evidence.get("alias_chain") or [])
+                ),
+                override=planner_renderer.override or evidence.get("override"),
+                support_decision=report,
+            )
             normalized_segment = replace(
                 segment,
-                renderer=self._renderer_resolution(resolved),
+                renderer=merged_renderer,
                 input_hashes={
                     **segment.input_hashes,
                     **input_hashes,
                     **materialized_hashes,
                 },
             )
             normalized_segments.append(normalized_segment)
             result = self._invoke_renderer(
                 segment_request,
                 selected=resolved,
                 workspace=workspace,
                 output_name=segment_request.output_name,
                 # Segment renderers may emit a profile that the registered
                 # finalizer must normalize.  The artifact is first validated
                 # against its own declaration; a one-segment exact match is
                 # checked against the plan in _finish_plan, while every
                 # mismatch and every multi-segment plan goes through the
                 # pinned finalizer.
                 expected_profile=None,
             )
             completed = self.complete_audio(
                 result,
                 request=segment_request,
                 plan=response,
                 workspace=workspace,
                 backend=candidate.id,
-                defer_to_finalizer=len(response.segments) > 1,
+                # The plan pins an explicit finalizer; segment audio is
+                # deferred to it (single- and multi-segment alike) so a
+                # normalizable profile/audio mismatch cannot fail the segment
+                # before the finalizer can normalize it.
+                defer_to_finalizer=response.finalizer.id != _DIRECT_FINALIZER_ID,
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
-        finalizer_resolution = self._finalizer_resolution(
-            finalizer,
-            finalizer_evidence,
-            support=None,
+        finalizer_resolution = replace(
+            response.finalizer,
+            id=finalizer.id,
+            source_pack=self._source_pack(finalizer, finalizer_evidence),
+            manifest_digest=finalizer.manifest_digest,
+            trust_eligibility=finalizer.eligibility.to_dict(),
+            alias_chain=(
+                response.finalizer.alias_chain
+                or list(finalizer_evidence.get("alias_chain") or [])
+            ),
+            override=response.finalizer.override or finalizer_evidence.get("override"),
+            # The planner's finalizer support_decision names its pre-alias
+            # identity; _finish_plan re-evaluates support for the resolved
+            # finalizer and records the authoritative decision.
+            support_decision=None,
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
-        if len(segment_results) == 1:
+        candidate, evidence = pinned_finalizer
+        if candidate.id == _DIRECT_FINALIZER_ID:
+            # No executable finalizer pinned: the segment must already match
+            # the canonical plan profile exactly.
+            if len(segment_results) != 1:
+                raise_internal_error(
+                    backend=_CORE_BACKEND_ID,
+                    message="direct finalizer received multiple segments",
+                    recovery_command="select a planner that pins an executable finalizer",
+                    details={"segment_count": len(segment_results)},
+                )
             result = self._validator(
                 segment_results[0],
                 expected_profile=plan.profile,
                 workspace_root=workspace,
             )
             return result, plan
 
-        candidate, evidence = pinned_finalizer
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
         finalizer_resolution = self._finalizer_resolution(
             candidate,
             evidence,
             support=report,
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
@@ -1434,249 +1483,258 @@ class RenderService:
         if self._audio_completer is None:
             if result.audio_ownership is AudioOwnership.PASSTHROUGH:
                 raise_unsupported_error(
                     backend=backend,
                     message=(
                         "renderer requested passthrough audio but no host audio "
                         "completer is configured"
                     ),
                     recovery_command=(
                         "configure an audio completer or select a renderer that "
                         "returns rendered audio"
                     ),
                     details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
                 )
             return result
         completed = self._audio_completer(
             result,
             request=request,
             plan=plan,
             workspace=workspace,
         )
         if not isinstance(completed, RenderResult):
             raise_protocol_error(
                 backend=_CORE_BACKEND_ID,
                 message="audio completer did not return a RenderResult",
                 details={"received_type": type(completed).__name__},
             )
         if (
             completed.audio_ownership is AudioOwnership.PASSTHROUGH
             or (
                 result.audio_ownership is AudioOwnership.PASSTHROUGH
                 and completed.audio_ownership is not AudioOwnership.RENDERED
             )
         ):
             raise_invalid_artifact_error(
                 backend=backend,
                 message="host audio completer left passthrough audio incomplete",
                 recovery_command="return a completed rendered-audio result",
                 details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
             )
         missing_attachments = sorted(
             set(result.attachments) - set(completed.attachments)
         )
         changed_attachments = sorted(
             name
             for name, attachment in result.attachments.items()
             if name in completed.attachments
             and completed.attachments[name] != attachment
         )
         if missing_attachments or changed_attachments:
             raise_invalid_artifact_error(
                 backend=backend,
                 message="host audio completion did not preserve renderer attachments",
                 recovery_command="preserve every named attachment while completing audio",
                 details={
                     "missing": missing_attachments,
                     "changed": changed_attachments,
                 },
             )
         original_profile = result.video.profile.to_dict()
         completed_profile = completed.video.profile.to_dict()
         audio_fields = {
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout",
         }
         changed_video_fields = sorted(
             key
             for key, value in original_profile.items()
             if key not in audio_fields and completed_profile.get(key) != value
         )
         if (
             changed_video_fields
             or completed.video.duration_frames != result.video.duration_frames
         ):
             raise_invalid_artifact_error(
                 backend=backend,
                 message="host audio completion changed the renderer's video contract",
                 recovery_command="complete audio without changing video profile or duration",
                 details={
                     "changed_profile_fields": changed_video_fields,
                     "before_duration_frames": result.video.duration_frames,
                     "after_duration_frames": completed.video.duration_frames,
                 },
             )
         return self._validator(
             completed,
             expected_profile=completed.video.profile,
             workspace_root=workspace,
         )
 
     def _direct_plan(
         self,
         request: RenderRequest,
         *,
         selected: _ResolvedCapability,
         result: RenderResult,
         requested_policy: str,
     ) -> RenderPlan:
         finalizer_resolution = self._direct_finalizer_resolution()
+        reasons: dict[str, str] = {"0": "direct renderer selection"}
+        if selected.rejected:
+            # A legacy auto-route selector rejects earlier candidates before
+            # the winning backend succeeds; record that rejection evidence so
+            # provenance explains why this backend rendered the timeline.
+            reasons["0"] = (
+                "direct renderer selection; rejected candidates: "
+                + json.dumps(selected.rejected, sort_keys=True)
+            )
         if request.window is not None:
             if request.window.fps_rational != result.video.profile.fps_rational:
                 raise_invalid_artifact_error(
                     backend=selected.candidate.id,
                     message="renderer artifact FPS does not match the requested frame window",
                     recovery_command="render the requested window at its declared rational FPS",
                     details={
                         "window_fps": list(request.window.fps_rational),
                         "artifact_fps": list(result.video.profile.fps_rational),
                     },
                 )
             segment_window = request.window
             total_frames = request.window.end_frame
             plan_window = request.window
             self._validate_planned_duration(
                 result,
                 planned_frames=request.window.duration_frames,
                 canonical_profile=result.video.profile,
                 backend=selected.candidate.id,
                 label="renderer artifact",
             )
         else:
             segment_window = FrameWindow(
                 start_frame=0,
                 end_frame=result.video.duration_frames,
                 fps_rational=result.video.profile.fps_rational,
             )
             total_frames = result.video.duration_frames
             plan_window = None
         segment = RenderSegment(
             window=segment_window,
             renderer=self._renderer_resolution(selected),
             input_hashes=self._input_hashes(request),
         )
         return RenderPlan(
             schema_version=SCHEMA_VERSION,
             request_digest=compute_request_digest(request.to_dict()),
             requested_policy=requested_policy,
             planner=PlannerResolution(
                 id=_DIRECT_PLANNER_ID,
                 source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
                 manifest_digest=_DIRECT_PLANNER_DIGEST,
                 trust_eligibility={"eligible": True, "reason": "core direct plan"},
             ),
             segments=[segment],
             finalizer=finalizer_resolution,
             profile=result.video.profile,
             total_frames=total_frames,
-            reasons={"0": "direct renderer selection"},
+            reasons=reasons,
             window=plan_window,
         )
 
     def _direct_finalizer_resolution(self) -> FinalizerResolution:
         if self.finalizer_id is not None:
             candidate, evidence = self._resolve_candidate(
                 self.finalizers,
                 self.finalizer_id,
                 kind="finalizer",
                 observe=False,
             )
             return self._finalizer_resolution(candidate, evidence, support=None)
         return FinalizerResolution(
             id=_DIRECT_FINALIZER_ID,
             source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
             manifest_digest=_DIRECT_FINALIZER_DIGEST,
             trust_eligibility={"eligible": True, "reason": "core direct pass-through"},
         )
 
     @staticmethod
     def _source_pack(
         candidate: RenderingCandidate[Any], evidence: Mapping[str, Any]
     ) -> dict[str, Any]:
         source = {
             "id": candidate.pack_id,
             "source_kind": candidate.source_kind,
             "root": str(candidate.pack_root),
             "priority_index": candidate.priority_index,
         }
         revision = candidate.eligibility.active_revision
         if revision is not None:
             source["active_revision"] = revision
         manifest_path = evidence.get("manifest_path")
         if isinstance(manifest_path, str):
             source["manifest_path"] = manifest_path
         return source
 
     def _renderer_resolution(
         self, selected: _ResolvedCapability
     ) -> RendererResolution:
         candidate = selected.candidate
         evidence = selected.evidence
         return RendererResolution(
             id=candidate.id,
             source_pack=self._source_pack(candidate, evidence),
             manifest_digest=candidate.manifest_digest,
             alias_chain=list(evidence.get("alias_chain") or []),
             override=evidence.get("override"),
             support_decision=selected.support,
             trust_eligibility=candidate.eligibility.to_dict(),
         )
 
     def _planner_resolution(
         self, selected: _ResolvedCapability
     ) -> PlannerResolution:
         candidate = selected.candidate
         evidence = selected.evidence
         return PlannerResolution(
             id=candidate.id,
             source_pack=self._source_pack(candidate, evidence),
             manifest_digest=candidate.manifest_digest,
             trust_eligibility=candidate.eligibility.to_dict(),
             alias_chain=list(evidence.get("alias_chain") or []),
             override=evidence.get("override"),
             support_decision=selected.support,
         )
 
     def _finalizer_resolution(
         self,
         candidate: RenderingCandidate[Any],
         evidence: Mapping[str, Any],
         *,
         support: SupportReport | None,
     ) -> FinalizerResolution:
         return FinalizerResolution(
             id=candidate.id,
             source_pack=self._source_pack(candidate, evidence),
             manifest_digest=candidate.manifest_digest,
             trust_eligibility=candidate.eligibility.to_dict(),
             alias_chain=list(evidence.get("alias_chain") or []),
             override=evidence.get("override"),
             support_decision=support,
         )
 
     def _run_command(
         self,
         candidate: RenderingCandidate[Any],
         verb: str,
         payload: Any,
         *,
         workspace: Path,
         required_binaries: Sequence[str] | None = None,
     ) -> Any:
         token = hashlib.sha256(
             f"{candidate.id}:{verb}:{len(list(workspace.iterdir()))}".encode()
         ).hexdigest()[:12]
         request_path = workspace / f"{token}-{verb}-request.json"
         result_path = workspace / f"{token}-{verb}-result.json"
         write_json_atomic(request_path, payload.to_dict())
         transport = (
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
old mode 100644
new mode 100755
index 59b0515e..bee39a44
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -1,684 +1,330 @@
 #!/usr/bin/env python3
 
 from __future__ import annotations
 
 from astrid.core.pack.entrypoint import guard_canonical_entrypoint
 
 guard_canonical_entrypoint('rendering.render')
 
 
 import argparse
 import ast
 import json
 import os
 import sys
-from contextvars import ContextVar
-from fractions import Fraction
 from pathlib import Path
 from tempfile import TemporaryDirectory
 from typing import Any, Mapping, Sequence
 
 from astrid.core import timeline
-from astrid.core.audit import AuditContext
 from astrid.core.foundation.paths import REPO_ROOT
-from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
-from astrid.core.rendering.profile import resolve_render_profile
-from astrid.core.rendering.publication import publish_render_result
 from astrid.core.rendering.service import RenderService
-from astrid.packs.rendering.backends.ffmpeg import command as ffmpeg_command
-from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_backend
-from astrid.packs.rendering.backends.remotion import run as remotion_backend
-from astrid.packs.rendering.executors.render import audio_reactive_colour
-from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
-from astrid.packs.rendering.planners.legacy_hybrid.run import (
-    _complex_clip_windows,
-    _hybrid_segments,
-)
-
-
-# Compatibility exports for callers that historically imported these private
-# helpers from the facade.  Their implementation now lives with the backend.
-_RangeHTTPRequestHandler = remotion_backend._RangeHTTPRequestHandler
-_validate_project_dir = remotion_backend._validate_project_dir
-_serialize_timeline = remotion_backend._serialize_timeline
-_resolve_theme_path = remotion_backend._resolve_theme_path
-_theme_for_props = remotion_backend._theme_for_props
-_theme_slug_for_render_default = remotion_backend._theme_slug_for_render_default
-_resolved_theme_for_render = remotion_backend._resolved_theme_for_render
-_timeline_composition_src = remotion_backend._timeline_composition_src
-_registry_output_paths = remotion_backend._registry_output_paths
-_registry_outputs_exist = remotion_backend._registry_outputs_exist
-_active_theme_pointer_current = remotion_backend._active_theme_pointer_current
-_effective_registry_state = remotion_backend._effective_registry_state
-_read_registry_state = remotion_backend._read_registry_state
-_write_registry_state = remotion_backend._write_registry_state
-_regenerate_element_registries = remotion_backend._regenerate_element_registries
-_render_asset_stage_hash = remotion_backend._render_asset_stage_hash
-_effect_registry_for_assets = remotion_backend._effect_registry_for_assets
-_effect_id_for_clip = remotion_backend._effect_id_for_clip
-_source_pack_id = remotion_backend._source_pack_id
-_inject_clip_asset_params = remotion_backend._inject_clip_asset_params
-_stage_effect_assets_for_timeline = remotion_backend._stage_effect_assets_for_timeline
-_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
-_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
-_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
-_render_provenance_payload = remotion_backend._render_provenance_payload
-_write_render_provenance = remotion_backend._write_render_provenance
-_timeline_canvas = ffmpeg_command.timeline_canvas
-_clip_duration_seconds = ffmpeg_command.clip_duration_seconds
-
 
 # The Hype pipeline's default output file name.  The executor manifest exposes
 # an ``output_name`` input defaulting to this sentinel; non-default names are
 # validated (plain file name, ``.mp4`` extension) and flow through the same
 # placeholder expansion and declared-output resolution as the default.
 DEFAULT_OUTPUT_NAME = "hype.mp4"
 
-_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
-    "render_publication_previous_outputs",
-    default=(),
-)
-_HYBRID_FINALIZER_PROFILE: ContextVar[RenderProfile | None] = ContextVar(
-    "hybrid_finalizer_profile",
-    default=None,
-)
-
 _SERVICE: RenderService | None = None
 
 
 def _default_service() -> RenderService:
     """Build (once) the backend-neutral service the facade delegates to.
 
     Legacy engine translation, renderer/planner selection, invocation,
     validation, audio completion, finalization, and publication all happen
     inside :class:`RenderService`.  The facade is a thin adapter: it maps the
     legacy argument surface onto the service call and returns the published
     output path.
     """
     global _SERVICE
     if _SERVICE is None:
         _SERVICE = RenderService()
     return _SERVICE
 
 
 def validate_output_name(name: str) -> str:
     """Validate an ``output_name``: a plain ``.mp4`` file name.
 
     Rejects empty names, path separators (``/`` and ``\\``), directory
     traversal (``.``, ``..``, or any ``..``-prefixed component), absolute
     paths, and anything that does not end in ``.mp4``.  The Hype default
     ``hype.mp4`` validates unchanged.
     """
     text = str(name)
     if text == "":
         raise ValueError("output_name must not be empty")
     if text in {".", ".."} or text.startswith(".."):
         raise ValueError(
             f"output_name must not traverse directories, got {name!r}"
         )
     if "/" in text or "\\" in text or text.startswith(os.sep):
         raise ValueError(
             f"output_name must be a plain file name without path separators, got {name!r}"
         )
     if Path(text).name != text:
         raise ValueError(
             f"output_name must be a plain file name, got {name!r}"
         )
     if not text.endswith(".mp4"):
         raise ValueError(
             f"output_name must end with .mp4, got {name!r}"
         )
     return text
 
 
 def _legacy_backend_config(
     *,
     project_dir: Path | None,
     composition_id: str,
     theme_path: Path | None,
     min_free_gb: float | None,
 ) -> dict[str, dict[str, Any]]:
     """Map the legacy render kwargs onto namespaced backend configuration.
 
     The facade remains backend-neutral: it only knows the qualified ids that
     correspond to the historical selector spellings and scopes each legacy
     value under the backend that understands it.  The service forwards each
     candidate only its own namespace.
     """
     config: dict[str, dict[str, Any]] = {}
     remotion: dict[str, Any] = {}
     if project_dir is not None:
         remotion["project_dir"] = str(project_dir)
     if composition_id is not None:
         remotion["composition_id"] = composition_id
     if theme_path is not None:
         remotion["theme_path"] = str(theme_path)
     if min_free_gb is not None:
         remotion["min_free_gb"] = min_free_gb
     if remotion:
         config["rendering.remotion"] = remotion
     hybrid: dict[str, Any] = {}
     if theme_path is not None:
         hybrid["theme_path"] = str(theme_path)
     if hybrid:
         config["rendering.legacy_hybrid"] = hybrid
     return config
 
 
 def _parse_backend_config(value: str | None) -> dict[str, dict[str, Any]]:
     """Parse the ``--backend-config`` CLI payload (JSON or Python literal)."""
     if value is None or value == "":
         return {}
     text = str(value).strip()
     try:
         parsed = json.loads(text)
     except json.JSONDecodeError:
         try:
             parsed = ast.literal_eval(text)
         except (ValueError, SyntaxError) as exc:
             raise ValueError(
                 f"--backend-config must be a JSON object keyed by qualified "
                 f"backend id, got {value!r}"
             ) from exc
     if not isinstance(parsed, dict):
         raise ValueError(
             f"--backend-config must be a JSON object keyed by qualified backend id"
         )
     return {str(key): dict(item) for key, item in parsed.items() if item is not None}
 
 
-def _swap_from_dump(clip: dict) -> dict:
-    out = dict(clip)
-    if "from_" in out:
-        out["from"] = out.pop("from_")
-    return out
-
-
 def _write_empty_asset_registry(path: Path) -> None:
     path.parent.mkdir(parents=True, exist_ok=True)
     timeline.save_registry({"assets": {}}, path)
 
 
-def _clip_timeline_end_seconds(clip: dict) -> float:
-    start = float(clip.get("at", 0) or 0)
-    if clip.get("clipType") == "media":
-        return start + _clip_duration_seconds(clip)
-    hold = clip.get("hold")
-    if isinstance(hold, (int, float)):
-        return start + max(0.0, float(hold))
-    if isinstance(clip.get("to"), (int, float)):
-        return float(clip["to"])
-    return start
-
-
-def _timeline_duration_seconds(timeline_data: dict) -> float:
-    metadata = timeline_data.get("metadata", {})
-    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
-    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
-        explicit = metadata.get("expected_duration_seconds")
-    if isinstance(explicit, (int, float)):
-        return float(explicit)
-    return max((_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0)
-
-
-def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
-    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
-    instant = (
-        seconds
-        if isinstance(seconds, Fraction)
-        else Fraction(seconds).limit_denominator(1_000_000)
-    )
-    frames = instant * rate
-    if mode == "floor":
-        frame = frames.numerator // frames.denominator
-    elif mode == "ceil":
-        frame = -(-frames.numerator // frames.denominator)
-    else:
-        frame = round(frames)
-    return float(Fraction(frame, 1) / rate)
-
-
-def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
-    clip_start = float(clip.get("at", 0) or 0)
-    clip_end = _clip_timeline_end_seconds(clip)
-    return clip_start < end and clip_end > start
-
-
-def _window_clip(clip: dict, start: float, end: float) -> dict | None:
-    if not _clip_overlaps(clip, start, end):
-        return None
-    clip_start = float(clip.get("at", 0) or 0)
-    visible_start = max(clip_start, start)
-    visible_end = min(_clip_timeline_end_seconds(clip), end)
-    if visible_end <= visible_start:
-        return None
-
-    out = dict(clip)
-    out["at"] = visible_start - start
-    out["id"] = f"{clip.get('id', 'clip')}_{start:.3f}_{end:.3f}".replace(".", "_")
-    if clip.get("clipType") == "media":
-        speed = float(clip.get("speed", 1) or 1)
-        source_from = float(clip.get("from", 0) or 0) + ((visible_start - clip_start) * speed)
-        out["from"] = source_from
-        out["to"] = source_from + ((visible_end - visible_start) * speed)
-    elif isinstance(clip.get("hold"), (int, float)):
-        out["hold"] = visible_end - visible_start
-    return out
-
-
-def _window_timeline_data(timeline_data: dict, start: float, end: float, *, media_only: bool) -> dict:
-    clips: list[dict] = []
-    for clip in timeline_data.get("clips", []):
-        if media_only and clip.get("clipType") != "media":
-            continue
-        windowed = _window_clip(clip, start, end)
-        if windowed is not None:
-            clips.append(windowed)
-    used_tracks = {clip.get("track") for clip in clips}
-    tracks = [track for track in timeline_data.get("tracks", []) if track.get("id") in used_tracks]
-    out = dict(timeline_data)
-    out["tracks"] = tracks
-    out["clips"] = clips
-    out["metadata"] = {
-        **dict(timeline_data.get("metadata", {})),
-        "source_window_start_seconds": start,
-        "source_window_end_seconds": end,
-        "duration_seconds": end - start,
-    }
-    return out
-
-
-_validate_ffmpeg_media_timeline = (
-    ffmpeg_command.validate_ffmpeg_media_timeline
-)
-
-
-def _render_ffmpeg_media_to_path(
-    timeline_path: Path,
-    assets_path: Path,
-    out_path: Path,
-) -> Path:
-    return ffmpeg_backend._render_ffmpeg_media_to_path(
-        timeline_path,
-        assets_path,
-        out_path,
-    )
-
-
-def _render_ffmpeg_media(
-    timeline_path: Path,
-    assets_path: Path,
-    out_path: Path,
-    *,
-    _previous_outputs: Sequence[Path] | None = None,
-) -> Path:
-    return ffmpeg_backend.render(
-        timeline_path,
-        assets_path,
-        out_path,
-        previous_outputs=(
-            _PUBLICATION_PREVIOUS_OUTPUTS.get()
-            if _previous_outputs is None
-            else _previous_outputs
-        ),
-        _render_to_path=_render_ffmpeg_media_to_path,
-    )
-
-
-def _can_render_with_ffmpeg_media(
-    timeline_path: Path,
-    assets_path: Path,
-) -> bool:
-    return ffmpeg_backend.can_render_with_ffmpeg_media(
-        timeline_path,
-        assets_path,
-    )
-
-
-def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
-    profile = _HYBRID_FINALIZER_PROFILE.get()
-    audio = None
-    if profile is not None:
-        audio = (
-            AudioOwnership.RENDERED
-            if profile.has_audio
-            else AudioOwnership.NONE
-        )
-    ffmpeg_finalizer.concat_segment_files(
-        segment_paths,
-        out_path,
-        profile=profile,
-        audio=audio,
-    )
-
-
-def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
-    if not timeline_path.exists():
-        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
-    if not assets_path.exists():
-        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
-    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
-    canonical_profile = resolve_render_profile(
-        timeline_data,
-        timeline.load_registry(assets_path),
-        theme=remotion_kwargs.get("theme_path"),
-        themes_root=REPO_ROOT / "themes",
-    )
-    segments = _hybrid_segments(
-        timeline_data,
-        fps=Fraction(*canonical_profile.fps_rational),
-    )
-    if (
-        canonical_profile.fps_rational[1] == 1
-        and len(segments) == 1
-        and segments[0]["engine"] == "ffmpeg"
-    ):
-        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
-
-    publication_out = out_path  # unresolved: publication symlink-guards it
-    resolved_out = out_path.resolve()
-    resolved_out.parent.mkdir(parents=True, exist_ok=True)
-    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
-        tmp_dir = Path(tmp)
-        segment_paths: list[Path] = []
-        segment_provenance: list[dict[str, Any]] = []
-        for index, segment in enumerate(segments):
-            engine = str(segment["engine"])
-            start = float(segment["from"])
-            end = float(segment["to"])
-            segment_dir = tmp_dir / f"{index:04d}-{engine}"
-            segment_dir.mkdir(parents=True, exist_ok=True)
-            segment_timeline_path = segment_dir / "timeline.json"
-            segment_out_path = segment_dir / "segment.mp4"
-            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
-            if canonical_profile.fps_rational[1] != 1:
-                # Both extracted legacy renderers accept an integer canvas
-                # rate.  Render the window at the nearest rate, then let the
-                # finalizer normalize to the exact canonical rational rate.
-                render_rate = max(
-                    1,
-                    round(Fraction(*canonical_profile.fps_rational)),
-                )
-                overrides = dict(segment_timeline.get("theme_overrides", {}))
-                visual = dict(overrides.get("visual", {}))
-                canvas = dict(visual.get("canvas", {}))
-                canvas["fps"] = render_rate
-                visual["canvas"] = canvas
-                overrides["visual"] = visual
-                segment_timeline["theme_overrides"] = overrides
-            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
-            if engine == "ffmpeg":
-                _render_ffmpeg_media(
-                    segment_timeline_path,
-                    assets_path,
-                    segment_out_path,
-                    _previous_outputs=(),
-                )
-            else:
-                render(
-                    segment_timeline_path,
-                    assets_path,
-                    segment_out_path,
-                    engine="remotion",
-                    **remotion_kwargs,
-                )
-                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
-                if sidecar_path.exists():
-                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
-            segment_paths.append(segment_out_path)
-        staged_video = tmp_dir / "final" / out_path.name
-        staged_video.parent.mkdir(parents=True, exist_ok=True)
-        profile_token = _HYBRID_FINALIZER_PROFILE.set(canonical_profile)
-        try:
-            _concat_segments(segment_paths, staged_video)
-        finally:
-            _HYBRID_FINALIZER_PROFILE.reset(profile_token)
-        provenance = _render_provenance_payload(
-            out_path,
-            engine="hybrid",
-            timeline_path=timeline_path,
-            assets_path=assets_path,
-            project_dir=Path(remotion_kwargs.get("project_dir") or (REPO_ROOT / "remotion")),
-            composition_id=str(remotion_kwargs.get("composition_id") or "TimelineComposition"),
-            theme_path=remotion_kwargs.get("theme_path"),
-            active_theme=None,
-            registry_state=_effective_registry_state(remotion_kwargs.get("theme_path")),
-            stage_summary={"root": None, "effects": []},
-            segments=segments,
-            segment_provenance=segment_provenance,
-        )
-        output = publish_render_result(
-            staged_video,
-            provenance,
-            out_path=out_path,
-            sidecar_path=_render_provenance_sidecar_path(out_path),
-            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
-        )
-
-    audit = AuditContext.from_env()
-    if audit is not None:
-        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid")
-        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_hybrid")
-        render_id = audit.register_asset(
-            kind="render",
-            path=out_path,
-            label="Rendered video",
-            parents=[timeline_id, assets_id],
-            stage="render_hybrid",
-            metadata={"engine": "hybrid", "segments": segments},
-        )
-        audit.register_node(
-            stage="render_hybrid",
-            label="Render hybrid timeline",
-            parents=[timeline_id, assets_id],
-            outputs=[render_id],
-            metadata={"engine": "hybrid", "segments": segments},
-        )
-    return output
-
-
 def _previous_render_outputs_for_timeline(
     out_path: Path,
     timeline_path: Path,
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
 
 
-def _audio_reactive_ffmpeg_element(
-    theme_path: Path | None,
-) -> Any | None:
-    return ffmpeg_backend._audio_reactive_ffmpeg_element(theme_path)
-
-
-def _render_audio_reactive_colour_if_supported(
-    timeline_path: Path,
-    assets_path: Path,
-    out_path: Path,
-    *,
-    project_dir: Path | None,
-    composition_id: str,
-    theme_path: Path | None,
-) -> Path | None:
-    return ffmpeg_backend.render_audio_reactive_colour_if_supported(
-        timeline_path,
-        assets_path,
-        out_path,
-        project_dir=project_dir,
-        composition_id=composition_id,
-        theme_path=theme_path,
-        previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
-        element_resolver=_audio_reactive_ffmpeg_element,
-    )
-
-
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
-        if value is not None:
+        if value is None:
+            continue
+        existing = config.get(str(key))
+        if existing is None:
             config[str(key)] = dict(value)
+        else:
+            # Explicit caller configuration overlays, never replaces, the
+            # legacy-derived settings so project/theme/composition values
+            # survive a partial --backend-config payload.
+            overlaid = dict(existing)
+            overlaid.update({k: v for k, v in value.items() if v is not None})
+            config[str(key)] = overlaid
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
         default="remotion",
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
+        if args.backend is not None and args.engine != "remotion":
+            raise ValueError(
+                f"--engine {args.engine!r} and --backend {args.backend!r} "
+                "conflict; supply exactly one selector"
+            )
         selector = args.backend if args.backend is not None else args.engine
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
diff --git a/astrid/packs/rendering/planners/legacy_hybrid/run.py b/astrid/packs/rendering/planners/legacy_hybrid/run.py
index 081566ff..5d12ec21 100644
--- a/astrid/packs/rendering/planners/legacy_hybrid/run.py
+++ b/astrid/packs/rendering/planners/legacy_hybrid/run.py
@@ -658,202 +658,214 @@ class _CommandSupportResolver:
             required_binaries=(),
             timeout=candidate.manifest.timeout_seconds,
         )
         if not isinstance(response, SupportReport):
             raise TypeError(f"{candidate.id} support did not return a SupportReport")
         return response
 
 
 def plan(
     request: RenderRequest,
     *,
     workspace: Path,
     support_resolver: SupportResolver | None = None,
     registries: tuple[RendererRegistry, FinalizerRegistry] | None = None,
 ) -> RenderPlan:
     report = support(request, workspace=workspace)
     if not report.supported:
         raise_unsupported_error(
             backend=BACKEND_ID,
             message="legacy hybrid planner does not support this request",
             recovery_command="resolve the reported timeline constraints and retry",
             details={"reasons": report.reasons},
         )
     timeline_path, timeline, assets_path, assets = _load_inputs(request, workspace)
     config = _planner_config(request)
     theme = config.get("theme_path", config.get("theme"))
     profile = resolve_render_profile(
         timeline,
         assets,
         theme=theme,
         themes_root=config.get("themes_root", REPO_ROOT / "themes"),
         audio_ownership=request.audio,
     )
     fps = Fraction(*profile.fps_rational)
     total_frames, raw_segments = _segment_kinds(timeline, fps)
 
     renderer_registry: RendererRegistry | None
     finalizer_registry: FinalizerRegistry | None
     if registries is None and support_resolver is None:
         raw_extra_roots = config.get("extra_pack_roots", ())
         if isinstance(raw_extra_roots, (str, bytes)) or not isinstance(
             raw_extra_roots, Sequence
         ):
             raise TypeError("extra_pack_roots must be an array of paths")
         extra_roots = tuple(str(item) for item in raw_extra_roots)
         renderer_registry, _planners, finalizer_registry = load_default_registries(
             REPO_ROOT,
             extra_pack_roots=extra_roots,
         )
     elif registries is None:
         renderer_registry = None
         finalizer_registry = None
     else:
         renderer_registry, finalizer_registry = registries
     if support_resolver is None:
         if renderer_registry is None:
             raise RuntimeError("renderer registry is required for command support resolution")
         support_resolver = _CommandSupportResolver(
             renderer_registry,
             workspace=workspace,
         )
 
     candidates = _candidate_lists(config)
     if request.window is not None:
         target_start = request.window.start_frame
         target_end = request.window.end_frame
         raw_segments = [
             (max(start, target_start), min(end, target_end), kind)
             for start, end, kind in raw_segments
             if min(end, target_end) > max(start, target_start)
         ]
     segments: list[RenderSegment] = []
     reasons: dict[str, str] = {}
     for index, (start, end, kind) in enumerate(raw_segments):
         window = FrameWindow(
             start_frame=start,
             end_frame=end,
             fps_rational=profile.fps_rational,
         )
         segment_timeline = _window_timeline(timeline, window)
         segment_request = replace(
             request,
             timeline_path=str(timeline_path),
             assets_registry_path=None if assets_path is None else str(assets_path),
             output_name=f"segment-{index:04d}.mp4",
             window=window,
         )
         attempts: list[str] = []
         selected_id: str | None = None
         selected_report: SupportReport | None = None
         for renderer_id in candidates[kind]:
             try:
                 candidate_report = support_resolver(
                     renderer_id,
                     segment_request,
                     segment_timeline,
                 )
             except Exception as exc:
                 attempts.append(f"{renderer_id}: {exc}")
                 continue
-            if candidate_report.backend != renderer_id:
-                attempts.append(f"{renderer_id}: support report named {candidate_report.backend}")
+            # The support resolver already resolved the requested id through
+            # the registry; a configured alias or override therefore names a
+            # different canonical id than the raw candidate list entry.  Match
+            # on the resolved candidate id, never the raw spelling.
+            resolved_id = renderer_id
+            if renderer_registry is not None:
+                try:
+                    resolved_id = renderer_registry.get(renderer_id).id
+                except Exception:
+                    resolved_id = renderer_id
+            if candidate_report.backend != resolved_id:
+                attempts.append(
+                    f"{renderer_id}: support report named {candidate_report.backend}"
+                )
                 continue
             if candidate_report.supported:
                 selected_id = renderer_id
                 selected_report = candidate_report
                 break
             attempts.append(
                 f"{renderer_id}: " + "; ".join(candidate_report.reasons)
             )
         if selected_id is None or selected_report is None:
             raise_unsupported_error(
                 backend=BACKEND_ID,
                 message=f"no renderer supports planned {kind} window [{start},{end})",
                 recovery_command="install or configure a renderer supporting the reported window",
                 details={"window": [start, end], "attempts": attempts},
             )
         segments.append(
             RenderSegment(
                 window=window,
                 renderer=_renderer_resolution(
                     selected_id,
                     selected_report,
                     registry=renderer_registry,
                 ),
                 input_hashes={
                     "timeline": sha256_file(timeline_path),
                     **(
                         {"assets_registry": sha256_file(assets_path)}
                         if assets_path is not None
                         else {}
                     ),
                 },
             )
         )
         reasons[str(index)] = (
             f"{kind} legacy window assigned to {selected_id} by supported report"
         )
 
     return RenderPlan(
         schema_version=SCHEMA_VERSION,
         request_digest=compute_request_digest(request.to_dict()),
         requested_policy="hybrid",
         planner=_planner_resolution(report),
         segments=segments,
         finalizer=_finalizer_resolution(finalizer_registry),
         profile=profile,
         total_frames=total_frames,
         reasons=reasons,
         window=request.window,
     )
 
 
 def _load_request(path: Path) -> RenderRequest:
     payload = json.loads(path.read_text(encoding="utf-8"))
     if not isinstance(payload, Mapping):
         raise TypeError("render request must contain a JSON object")
     return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)
 
 
 def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
     if isinstance(exc, RendererException):
         error_kind = exc.error.kind
         message = exc.error.message
         recovery = exc.error.recovery_command
         details = exc.error.details
     else:
         error_kind = kind
         message = str(exc) or type(exc).__name__
         recovery = None
         details = {"error_type": type(exc).__name__}
     write_json_atomic(
         result_path,
         make_renderer_error(
             error_kind,
             backend=BACKEND_ID,
             message=message,
             recovery_command=recovery,
             details=details,
         ).to_dict(),
     )
 
 
 def main(argv: Sequence[str] | None = None) -> int:
     parser = argparse.ArgumentParser()
     parser.add_argument("verb", choices=("plan", "support"))
     parser.add_argument("--request", type=Path, required=True)
     parser.add_argument("--result", type=Path, required=True)
     args = parser.parse_args(argv)
     try:
         request_path = args.request.resolve(strict=True)
         result_path = args.result.resolve()
         if request_path == result_path:
             raise ValueError("--request and --result must be different paths")
         request = _load_request(request_path)
     except (OSError, ValueError, TypeError, json.JSONDecodeError, RendererException) as exc:
         _write_failure(args.result.resolve(), exc, kind="protocol")
         return 0
     try:
         workspace = request_path.parent
         response: RenderPlan | SupportReport
         if args.verb == "support":

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '40,90p;500,590p;1120,1325p' && nl -ba astrid/packs/rendering/planners/legacy_hybrid/run.py | sed -n '620,820p' && nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 165ms:
    40	    SupportReport,
    41	    compute_request_digest,
    42	)
    43	from .errors import (
    44	    RendererException,
    45	    raise_internal_error,
    46	    raise_invalid_artifact_error,
    47	    raise_protocol_error,
    48	    raise_renderer_error,
    49	    raise_unsupported_error,
    50	)
    51	from .provenance import assemble_provenance_v2
    52	from .publication import publish_render_result
    53	from .registry import (
    54	    FinalizerRegistry,
    55	    PlannerRegistry,
    56	    RendererRegistry,
    57	    RenderingCandidate,
    58	    RenderingRegistryError,
    59	    load_default_registries,
    60	)
    61	from .transport import CommandTransport
    62	
    63	
    64	_QUALIFIED_ID_RE = re.compile(
    65	    r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$"
    66	)
    67	_CORE_BACKEND_ID = "astrid.core"
    68	_DIRECT_PLANNER_ID = "astrid.direct"
    69	_DIRECT_PLANNER_DIGEST = hashlib.sha256(b"astrid.direct/v1").hexdigest()
    70	_DIRECT_FINALIZER_ID = "astrid.direct-finalizer"
    71	_DIRECT_FINALIZER_DIGEST = hashlib.sha256(
    72	    b"astrid.direct-finalizer/v1"
    73	).hexdigest()
    74	
    75	CapabilityKind = Literal["renderer", "planner", "finalizer"]
    76	StageObserver = Callable[[str, Mapping[str, Any]], None]
    77	AudioCompleter = Callable[..., RenderResult]
    78	
    79	
    80	class LegacyRenderRoutingWarning(UserWarning):
    81	    """A legacy selector selected a different qualified backend."""
    82	
    83	
    84	@dataclass(frozen=True)
    85	class _SelectionPolicy:
    86	    requested: str
    87	    kind: Literal["renderer", "planner"]
    88	    targets: tuple[str, ...]
    89	    auto_route: bool = False
    90	
   500	            audio_ownership=final_result.audio_ownership,
   501	            normalization=final_result.normalization,
   502	            attachments=final_result.attachments,
   503	            backend_fragments=fragments,
   504	            v1_compatibility=compatibility,
   505	        )
   506	        self._observe(
   507	            "publish",
   508	            backend=(
   509	                plan.planner.id if policy.kind == "planner" else selected.candidate.id
   510	            ),
   511	            output=str(out_path),
   512	            sidecar=str(sidecar_path),
   513	        )
   514	        published = self._publisher(
   515	            source_video,
   516	            provenance,
   517	            out_path=out_path,
   518	            sidecar_path=sidecar_path,
   519	            previous_outputs=previous_outputs,
   520	        )
   521	        return Path(published)
   522	
   523	    def _select(
   524	        self,
   525	        request: RenderRequest,
   526	        *,
   527	        policy: _SelectionPolicy,
   528	        workspace: Path,
   529	    ) -> _ResolvedCapability:
   530	        registry: RendererRegistry | PlannerRegistry = (
   531	            self.renderers if policy.kind == "renderer" else self.planners
   532	        )
   533	        rejected: list[dict[str, Any]] = []
   534	        for index, target in enumerate(policy.targets):
   535	            try:
   536	                candidate, evidence = self._resolve_candidate(
   537	                    registry,
   538	                    target,
   539	                    kind=policy.kind,
   540	                )
   541	                report = self._support(
   542	                    candidate,
   543	                    request=request,
   544	                    workspace=workspace,
   545	                    registry=registry,
   546	                )
   547	            except RendererException as exc:
   548	                if not policy.auto_route or index == len(policy.targets) - 1:
   549	                    raise
   550	                if exc.error.kind not in {"unsupported", "binary_missing"}:
   551	                    raise
   552	                rejected.append(exc.error.to_dict())
   553	                continue
   554	            if not report.supported:
   555	                rejected.append(report.to_dict())
   556	                if policy.auto_route and index < len(policy.targets) - 1:
   557	                    continue
   558	                self._unsupported_report(report, registry=registry)
   559	            if policy.auto_route and index == 0:
   560	                warnings.warn(
   561	                    f"legacy selector {policy.requested!r} auto-routed this supported "
   562	                    f"timeline to {candidate.id}; select a qualified renderer "
   563	                    "id for strict routing",
   564	                    LegacyRenderRoutingWarning,
   565	                    stacklevel=4,
   566	                )
   567	            return _ResolvedCapability(
   568	                candidate,
   569	                evidence,
   570	                report,
   571	                rejected=list(rejected),
   572	            )
   573	
   574	        alternatives = self._alternatives(registry)
   575	        raise_unsupported_error(
   576	            backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
   577	            message=f"no renderer supports legacy selector {policy.requested!r}",
   578	            recovery_command=self._recovery_for(alternatives),
   579	            details={"attempts": rejected, "alternatives": alternatives},
   580	        )
   581	
   582	    def _resolve_candidate(
   583	        self,
   584	        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
   585	        requested_id: str,
   586	        *,
   587	        kind: CapabilityKind,
   588	        observe: bool = True,
   589	    ) -> tuple[RenderingCandidate[Any], dict[str, Any]]:
   590	        try:
  1120	        canonical_fps = Fraction(*canonical_profile.fps_rational)
  1121	        planned_seconds = Fraction(planned_frames, 1) / canonical_fps
  1122	        delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
  1123	        if delta_frames <= canonical_profile.duration_tolerance:
  1124	            return
  1125	        raise_invalid_artifact_error(
  1126	            backend=backend,
  1127	            message=f"{label} duration does not match its planned frame window",
  1128	            recovery_command="rerender the exact planned segment window and retry",
  1129	            details={
  1130	                "planned_duration_frames": planned_frames,
  1131	                "artifact_duration_frames": result.video.duration_frames,
  1132	                "canonical_delta_frames": [
  1133	                    delta_frames.numerator,
  1134	                    delta_frames.denominator,
  1135	                ],
  1136	                "tolerance_frames": canonical_profile.duration_tolerance,
  1137	            },
  1138	        )
  1139	
  1140	    def _execute_planner(
  1141	        self,
  1142	        request: RenderRequest,
  1143	        *,
  1144	        policy: _SelectionPolicy,
  1145	        selected: _ResolvedCapability,
  1146	        workspace: Path,
  1147	    ) -> tuple[
  1148	        RenderPlan,
  1149	        list[RenderResult],
  1150	        tuple[RenderingCandidate[Any], dict[str, Any]],
  1151	    ]:
  1152	        planner_request = request.for_backend(selected.candidate.id)
  1153	        self._observe("invoke", backend=selected.candidate.id, verb="plan")
  1154	        response = self._run_command(
  1155	            selected.candidate,
  1156	            "plan",
  1157	            planner_request,
  1158	            workspace=workspace,
  1159	        )
  1160	        if not isinstance(response, RenderPlan):
  1161	            raise_protocol_error(
  1162	                backend=selected.candidate.id,
  1163	                message="plan operation did not return a RenderPlan",
  1164	                details={"received_type": type(response).__name__},
  1165	            )
  1166	        # The registry selection is authoritative.  A planner response may
  1167	        # still carry the pre-alias/pre-override identity it was asked to
  1168	        # replace (notably during compatibility routing); normalize that
  1169	        # self-description to the selected candidate and its complete
  1170	        # resolution evidence below.
  1171	        planner_resolution = self._planner_resolution(selected)
  1172	        normalized_segments: list[RenderSegment] = []
  1173	        segment_results: list[RenderResult] = []
  1174	        input_hashes = self._input_hashes(request)
  1175	        for index, segment in enumerate(response.segments):
  1176	            candidate, evidence = self._resolve_candidate(
  1177	                self.renderers,
  1178	                segment.renderer.id,
  1179	                kind="renderer",
  1180	            )
  1181	            # The planner already resolved aliases/overrides itself and
  1182	            # recorded that lineage on the segment.  Re-resolving the emitted
  1183	            # id from scratch would discard the alias chain, so merge: the
  1184	            # service's resolution is authoritative for identity/trust while
  1185	            # the planner's recorded lineage survives when present.
  1186	            planner_renderer = segment.renderer
  1187	            native_request = replace(
  1188	                request,
  1189	                window=segment.window,
  1190	                output_name=f"segment-{index:04d}.mp4",
  1191	            )
  1192	            segment_request, materialized_hashes = self._segment_request(
  1193	                native_request,
  1194	                candidate=candidate,
  1195	                segment=segment,
  1196	                index=index,
  1197	                workspace=workspace,
  1198	            )
  1199	            report = self._support(
  1200	                candidate,
  1201	                request=segment_request,
  1202	                workspace=workspace,
  1203	                registry=self.renderers,
  1204	            )
  1205	            if not report.supported:
  1206	                self._unsupported_report(report, registry=self.renderers)
  1207	            resolved = _ResolvedCapability(candidate, evidence, report)
  1208	            merged_renderer = replace(
  1209	                planner_renderer,
  1210	                id=candidate.id,
  1211	                source_pack=self._source_pack(candidate, evidence),
  1212	                manifest_digest=candidate.manifest_digest,
  1213	                trust_eligibility=candidate.eligibility.to_dict(),
  1214	                alias_chain=(
  1215	                    planner_renderer.alias_chain
  1216	                    or list(evidence.get("alias_chain") or [])
  1217	                ),
  1218	                override=planner_renderer.override or evidence.get("override"),
  1219	                support_decision=report,
  1220	            )
  1221	            normalized_segment = replace(
  1222	                segment,
  1223	                renderer=merged_renderer,
  1224	                input_hashes={
  1225	                    **segment.input_hashes,
  1226	                    **input_hashes,
  1227	                    **materialized_hashes,
  1228	                },
  1229	            )
  1230	            normalized_segments.append(normalized_segment)
  1231	            result = self._invoke_renderer(
  1232	                segment_request,
  1233	                selected=resolved,
  1234	                workspace=workspace,
  1235	                output_name=segment_request.output_name,
  1236	                # Segment renderers may emit a profile that the registered
  1237	                # finalizer must normalize.  The artifact is first validated
  1238	                # against its own declaration; a one-segment exact match is
  1239	                # checked against the plan in _finish_plan, while every
  1240	                # mismatch and every multi-segment plan goes through the
  1241	                # pinned finalizer.
  1242	                expected_profile=None,
  1243	            )
  1244	            completed = self.complete_audio(
  1245	                result,
  1246	                request=segment_request,
  1247	                plan=response,
  1248	                workspace=workspace,
  1249	                backend=candidate.id,
  1250	                # The plan pins an explicit finalizer; segment audio is
  1251	                # deferred to it (single- and multi-segment alike) so a
  1252	                # normalizable profile/audio mismatch cannot fail the segment
  1253	                # before the finalizer can normalize it.
  1254	                defer_to_finalizer=response.finalizer.id != _DIRECT_FINALIZER_ID,
  1255	            )
  1256	            self._validate_segment_duration(
  1257	                completed,
  1258	                segment=segment,
  1259	                canonical_profile=response.profile,
  1260	                backend=candidate.id,
  1261	            )
  1262	            segment_results.append(completed)
  1263	
  1264	        finalizer, finalizer_evidence = self._resolve_candidate(
  1265	            self.finalizers,
  1266	            response.finalizer.id,
  1267	            kind="finalizer",
  1268	            observe=False,
  1269	        )
  1270	        finalizer_resolution = replace(
  1271	            response.finalizer,
  1272	            id=finalizer.id,
  1273	            source_pack=self._source_pack(finalizer, finalizer_evidence),
  1274	            manifest_digest=finalizer.manifest_digest,
  1275	            trust_eligibility=finalizer.eligibility.to_dict(),
  1276	            alias_chain=(
  1277	                response.finalizer.alias_chain
  1278	                or list(finalizer_evidence.get("alias_chain") or [])
  1279	            ),
  1280	            override=response.finalizer.override or finalizer_evidence.get("override"),
  1281	            # The planner's finalizer support_decision names its pre-alias
  1282	            # identity; _finish_plan re-evaluates support for the resolved
  1283	            # finalizer and records the authoritative decision.
  1284	            support_decision=None,
  1285	        )
  1286	        plan = replace(
  1287	            response,
  1288	            request_digest=compute_request_digest(request.to_dict()),
  1289	            requested_policy=policy.requested,
  1290	            planner=planner_resolution,
  1291	            segments=normalized_segments,
  1292	            finalizer=finalizer_resolution,
  1293	        )
  1294	        return plan, segment_results, (finalizer, finalizer_evidence)
  1295	
  1296	    def _finish_plan(
  1297	        self,
  1298	        request: RenderRequest,
  1299	        *,
  1300	        plan: RenderPlan,
  1301	        segment_results: list[RenderResult],
  1302	        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
  1303	        workspace: Path,
  1304	    ) -> tuple[RenderResult, RenderPlan]:
  1305	        candidate, evidence = pinned_finalizer
  1306	        if candidate.id == _DIRECT_FINALIZER_ID:
  1307	            # No executable finalizer pinned: the segment must already match
  1308	            # the canonical plan profile exactly.
  1309	            if len(segment_results) != 1:
  1310	                raise_internal_error(
  1311	                    backend=_CORE_BACKEND_ID,
  1312	                    message="direct finalizer received multiple segments",
  1313	                    recovery_command="select a planner that pins an executable finalizer",
  1314	                    details={"segment_count": len(segment_results)},
  1315	                )
  1316	            result = self._validator(
  1317	                segment_results[0],
  1318	                expected_profile=plan.profile,
  1319	                workspace_root=workspace,
  1320	            )
  1321	            return result, plan
  1322	
  1323	        ownerships = {item.audio_ownership for item in segment_results}
  1324	        if ownerships == {AudioOwnership.PASSTHROUGH}:
  1325	            requested_audio = AudioOwnership.PASSTHROUGH
   620	        candidate = self.registry.get(renderer_id)
   621	        evidence = self.registry.resolve_evidence(renderer_id)
   622	        del evidence
   623	        projected = request.for_backend(candidate.id)
   624	        if candidate.manifest.capabilities.get("supports_windows") is False:
   625	            if projected.window is None:
   626	                raise ValueError("planned renderer support requires a frame window")
   627	            path = self.workspace / "planner-support" / f"{self.counter:04d}-timeline.json"
   628	            self.counter += 1
   629	            write_json_atomic(path, timeline)
   630	            projected = replace(projected, timeline_path=str(path), window=None)
   631	        if "support" not in candidate.manifest.operations:
   632	            supports = candidate.manifest.capabilities.get(
   633	                "supports_windows" if projected.window is not None else "supports_full_timeline"
   634	            ) is True
   635	            return SupportReport(
   636	                schema_version=SCHEMA_VERSION,
   637	                supported=supports,
   638	                reasons=[] if supports else ["renderer lacks static support for this window"],
   639	                features={
   640	                    str(key): value
   641	                    for key, value in candidate.manifest.capabilities.get("features", {}).items()
   642	                    if isinstance(value, (bool, str))
   643	                },
   644	                alternatives=[],
   645	                backend=candidate.id,
   646	                backend_version=candidate.manifest.version,
   647	            )
   648	        request_path = self.workspace / "planner-support" / f"{self.counter:04d}-request.json"
   649	        result_path = self.workspace / "planner-support" / f"{self.counter:04d}-result.json"
   650	        self.counter += 1
   651	        write_json_atomic(request_path, projected.to_dict())
   652	        response = CommandTransport(candidate.id).run(
   653	            "support",
   654	            candidate.manifest.command,
   655	            request_path=request_path,
   656	            result_path=result_path,
   657	            cwd=candidate.pack_root,
   658	            required_binaries=(),
   659	            timeout=candidate.manifest.timeout_seconds,
   660	        )
   661	        if not isinstance(response, SupportReport):
   662	            raise TypeError(f"{candidate.id} support did not return a SupportReport")
   663	        return response
   664	
   665	
   666	def plan(
   667	    request: RenderRequest,
   668	    *,
   669	    workspace: Path,
   670	    support_resolver: SupportResolver | None = None,
   671	    registries: tuple[RendererRegistry, FinalizerRegistry] | None = None,
   672	) -> RenderPlan:
   673	    report = support(request, workspace=workspace)
   674	    if not report.supported:
   675	        raise_unsupported_error(
   676	            backend=BACKEND_ID,
   677	            message="legacy hybrid planner does not support this request",
   678	            recovery_command="resolve the reported timeline constraints and retry",
   679	            details={"reasons": report.reasons},
   680	        )
   681	    timeline_path, timeline, assets_path, assets = _load_inputs(request, workspace)
   682	    config = _planner_config(request)
   683	    theme = config.get("theme_path", config.get("theme"))
   684	    profile = resolve_render_profile(
   685	        timeline,
   686	        assets,
   687	        theme=theme,
   688	        themes_root=config.get("themes_root", REPO_ROOT / "themes"),
   689	        audio_ownership=request.audio,
   690	    )
   691	    fps = Fraction(*profile.fps_rational)
   692	    total_frames, raw_segments = _segment_kinds(timeline, fps)
   693	
   694	    renderer_registry: RendererRegistry | None
   695	    finalizer_registry: FinalizerRegistry | None
   696	    if registries is None and support_resolver is None:
   697	        raw_extra_roots = config.get("extra_pack_roots", ())
   698	        if isinstance(raw_extra_roots, (str, bytes)) or not isinstance(
   699	            raw_extra_roots, Sequence
   700	        ):
   701	            raise TypeError("extra_pack_roots must be an array of paths")
   702	        extra_roots = tuple(str(item) for item in raw_extra_roots)
   703	        renderer_registry, _planners, finalizer_registry = load_default_registries(
   704	            REPO_ROOT,
   705	            extra_pack_roots=extra_roots,
   706	        )
   707	    elif registries is None:
   708	        renderer_registry = None
   709	        finalizer_registry = None
   710	    else:
   711	        renderer_registry, finalizer_registry = registries
   712	    if support_resolver is None:
   713	        if renderer_registry is None:
   714	            raise RuntimeError("renderer registry is required for command support resolution")
   715	        support_resolver = _CommandSupportResolver(
   716	            renderer_registry,
   717	            workspace=workspace,
   718	        )
   719	
   720	    candidates = _candidate_lists(config)
   721	    if request.window is not None:
   722	        target_start = request.window.start_frame
   723	        target_end = request.window.end_frame
   724	        raw_segments = [
   725	            (max(start, target_start), min(end, target_end), kind)
   726	            for start, end, kind in raw_segments
   727	            if min(end, target_end) > max(start, target_start)
   728	        ]
   729	    segments: list[RenderSegment] = []
   730	    reasons: dict[str, str] = {}
   731	    for index, (start, end, kind) in enumerate(raw_segments):
   732	        window = FrameWindow(
   733	            start_frame=start,
   734	            end_frame=end,
   735	            fps_rational=profile.fps_rational,
   736	        )
   737	        segment_timeline = _window_timeline(timeline, window)
   738	        segment_request = replace(
   739	            request,
   740	            timeline_path=str(timeline_path),
   741	            assets_registry_path=None if assets_path is None else str(assets_path),
   742	            output_name=f"segment-{index:04d}.mp4",
   743	            window=window,
   744	        )
   745	        attempts: list[str] = []
   746	        selected_id: str | None = None
   747	        selected_report: SupportReport | None = None
   748	        for renderer_id in candidates[kind]:
   749	            try:
   750	                candidate_report = support_resolver(
   751	                    renderer_id,
   752	                    segment_request,
   753	                    segment_timeline,
   754	                )
   755	            except Exception as exc:
   756	                attempts.append(f"{renderer_id}: {exc}")
   757	                continue
   758	            # The support resolver already resolved the requested id through
   759	            # the registry; a configured alias or override therefore names a
   760	            # different canonical id than the raw candidate list entry.  Match
   761	            # on the resolved candidate id, never the raw spelling.
   762	            resolved_id = renderer_id
   763	            if renderer_registry is not None:
   764	                try:
   765	                    resolved_id = renderer_registry.get(renderer_id).id
   766	                except Exception:
   767	                    resolved_id = renderer_id
   768	            if candidate_report.backend != resolved_id:
   769	                attempts.append(
   770	                    f"{renderer_id}: support report named {candidate_report.backend}"
   771	                )
   772	                continue
   773	            if candidate_report.supported:
   774	                selected_id = renderer_id
   775	                selected_report = candidate_report
   776	                break
   777	            attempts.append(
   778	                f"{renderer_id}: " + "; ".join(candidate_report.reasons)
   779	            )
   780	        if selected_id is None or selected_report is None:
   781	            raise_unsupported_error(
   782	                backend=BACKEND_ID,
   783	                message=f"no renderer supports planned {kind} window [{start},{end})",
   784	                recovery_command="install or configure a renderer supporting the reported window",
   785	                details={"window": [start, end], "attempts": attempts},
   786	            )
   787	        segments.append(
   788	            RenderSegment(
   789	                window=window,
   790	                renderer=_renderer_resolution(
   791	                    selected_id,
   792	                    selected_report,
   793	                    registry=renderer_registry,
   794	                ),
   795	                input_hashes={
   796	                    "timeline": sha256_file(timeline_path),
   797	                    **(
   798	                        {"assets_registry": sha256_file(assets_path)}
   799	                        if assets_path is not None
   800	                        else {}
   801	                    ),
   802	                },
   803	            )
   804	        )
   805	        reasons[str(index)] = (
   806	            f"{kind} legacy window assigned to {selected_id} by supported report"
   807	        )
   808	
   809	    return RenderPlan(
   810	        schema_version=SCHEMA_VERSION,
   811	        request_digest=compute_request_digest(request.to_dict()),
   812	        requested_policy="hybrid",
   813	        planner=_planner_resolution(report),
   814	        segments=segments,
   815	        finalizer=_finalizer_resolution(finalizer_registry),
   816	        profile=profile,
   817	        total_frames=total_frames,
   818	        reasons=reasons,
   819	        window=request.window,
   820	    )
     1	#!/usr/bin/env python3
     2	
     3	from __future__ import annotations
     4	
     5	from astrid.core.pack.entrypoint import guard_canonical_entrypoint
     6	
     7	guard_canonical_entrypoint('rendering.render')
     8	
     9	
    10	import argparse
    11	import ast
    12	import json
    13	import os
    14	import sys
    15	from pathlib import Path
    16	from tempfile import TemporaryDirectory
    17	from typing import Any, Mapping, Sequence
    18	
    19	from astrid.core import timeline
    20	from astrid.core.foundation.paths import REPO_ROOT
    21	from astrid.core.rendering.service import RenderService
    22	
    23	# The Hype pipeline's default output file name.  The executor manifest exposes
    24	# an ``output_name`` input defaulting to this sentinel; non-default names are
    25	# validated (plain file name, ``.mp4`` extension) and flow through the same
    26	# placeholder expansion and declared-output resolution as the default.
    27	DEFAULT_OUTPUT_NAME = "hype.mp4"
    28	
    29	_SERVICE: RenderService | None = None
    30	
    31	
    32	def _default_service() -> RenderService:
    33	    """Build (once) the backend-neutral service the facade delegates to.
    34	
    35	    Legacy engine translation, renderer/planner selection, invocation,
    36	    validation, audio completion, finalization, and publication all happen
    37	    inside :class:`RenderService`.  The facade is a thin adapter: it maps the
    38	    legacy argument surface onto the service call and returns the published
    39	    output path.
    40	    """
    41	    global _SERVICE
    42	    if _SERVICE is None:
    43	        _SERVICE = RenderService()
    44	    return _SERVICE
    45	
    46	
    47	def validate_output_name(name: str) -> str:
    48	    """Validate an ``output_name``: a plain ``.mp4`` file name.
    49	
    50	    Rejects empty names, path separators (``/`` and ``\\``), directory
    51	    traversal (``.``, ``..``, or any ``..``-prefixed component), absolute
    52	    paths, and anything that does not end in ``.mp4``.  The Hype default
    53	    ``hype.mp4`` validates unchanged.
    54	    """
    55	    text = str(name)
    56	    if text == "":
    57	        raise ValueError("output_name must not be empty")
    58	    if text in {".", ".."} or text.startswith(".."):
    59	        raise ValueError(
    60	            f"output_name must not traverse directories, got {name!r}"
    61	        )
    62	    if "/" in text or "\\" in text or text.startswith(os.sep):
    63	        raise ValueError(
    64	            f"output_name must be a plain file name without path separators, got {name!r}"
    65	        )
    66	    if Path(text).name != text:
    67	        raise ValueError(
    68	            f"output_name must be a plain file name, got {name!r}"
    69	        )
    70	    if not text.endswith(".mp4"):
    71	        raise ValueError(
    72	            f"output_name must end with .mp4, got {name!r}"
    73	        )
    74	    return text
    75	
    76	
    77	def _legacy_backend_config(
    78	    *,
    79	    project_dir: Path | None,
    80	    composition_id: str,
    81	    theme_path: Path | None,
    82	    min_free_gb: float | None,
    83	) -> dict[str, dict[str, Any]]:
    84	    """Map the legacy render kwargs onto namespaced backend configuration.
    85	
    86	    The facade remains backend-neutral: it only knows the qualified ids that
    87	    correspond to the historical selector spellings and scopes each legacy
    88	    value under the backend that understands it.  The service forwards each
    89	    candidate only its own namespace.
    90	    """
    91	    config: dict[str, dict[str, Any]] = {}
    92	    remotion: dict[str, Any] = {}
    93	    if project_dir is not None:
    94	        remotion["project_dir"] = str(project_dir)
    95	    if composition_id is not None:
    96	        remotion["composition_id"] = composition_id
    97	    if theme_path is not None:
    98	        remotion["theme_path"] = str(theme_path)
    99	    if min_free_gb is not None:
   100	        remotion["min_free_gb"] = min_free_gb
   101	    if remotion:
   102	        config["rendering.remotion"] = remotion
   103	    hybrid: dict[str, Any] = {}
   104	    if theme_path is not None:
   105	        hybrid["theme_path"] = str(theme_path)
   106	    if hybrid:
   107	        config["rendering.legacy_hybrid"] = hybrid
   108	    return config
   109	
   110	
   111	def _parse_backend_config(value: str | None) -> dict[str, dict[str, Any]]:
   112	    """Parse the ``--backend-config`` CLI payload (JSON or Python literal)."""
   113	    if value is None or value == "":
   114	        return {}
   115	    text = str(value).strip()
   116	    try:
   117	        parsed = json.loads(text)
   118	    except json.JSONDecodeError:
   119	        try:
   120	            parsed = ast.literal_eval(text)
   121	        except (ValueError, SyntaxError) as exc:
   122	            raise ValueError(
   123	                f"--backend-config must be a JSON object keyed by qualified "
   124	                f"backend id, got {value!r}"
   125	            ) from exc
   126	    if not isinstance(parsed, dict):
   127	        raise ValueError(
   128	            f"--backend-config must be a JSON object keyed by qualified backend id"
   129	        )
   130	    return {str(key): dict(item) for key, item in parsed.items() if item is not None}
   131	
   132	
   133	def _write_empty_asset_registry(path: Path) -> None:
   134	    path.parent.mkdir(parents=True, exist_ok=True)
   135	    timeline.save_registry({"assets": {}}, path)
   136	
   137	
   138	def _previous_render_outputs_for_timeline(
   139	    out_path: Path,
   140	    timeline_path: Path,
   141	) -> tuple[Path, ...]:
   142	    """Discover legacy sibling outputs; publication validates before deleting.
   143	
   144	    The timeline argument remains part of the helper boundary for compatibility
   145	    with the legacy cleanup call site.  Filtering now happens under each
   146	    candidate's publication lock using the committed sidecar.
   147	    """
   148	
   149	    out_path = out_path.resolve()
   150	    if out_path.name != "hype.mp4":
   151	        return ()
   152	    run_dir = out_path.parent
   153	    runs_dir = run_dir.parent
   154	    if runs_dir.name != "runs" or not runs_dir.is_dir():
   155	        return ()
   156	    candidates: list[Path] = []
   157	    for candidate_run_dir in runs_dir.iterdir():
   158	        if not candidate_run_dir.is_dir() or candidate_run_dir == run_dir:
   159	            continue
   160	        candidates.append(candidate_run_dir / out_path.name)
   161	    return tuple(candidates)
   162	
   163	
   164	def _parse_bool_arg(value: str | bool | None) -> bool:
   165	    if value is None:
   166	        return True
   167	    if isinstance(value, bool):
   168	        return value
   169	    normalized = value.strip().lower()
   170	    if normalized in {"1", "true", "yes", "y", "on"}:
   171	        return True
   172	    if normalized in {"0", "false", "no", "n", "off"}:
   173	        return False
   174	    raise argparse.ArgumentTypeError(f"expected boolean value, got {value!r}")
   175	
   176	
   177	def render(
   178	    timeline_path: Path,
   179	    assets_path: Path,
   180	    out_path: Path,
   181	    *,
   182	    engine: str = "remotion",
   183	    project_dir: Path | None = None,
   184	    composition_id: str = "TimelineComposition",
   185	    theme_path: Path | None = None,
   186	    min_free_gb: float | None = None,
   187	    keep_previous_renders: bool = False,
   188	    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
   189	) -> Path:
   190	    """Render through :class:`RenderService` and publish one locked pair.
   191	
   192	    The facade keeps the historical public signature and capability id.  All
   193	    dispatch (legacy engine translation, renderer/planner selection, support,
   194	    invocation, validation, audio completion, finalization, publication)
   195	    happens in the service; the facade only adapts the legacy argument surface
   196	    and the caller-selected output name.
   197	    """
   198	    out_path = Path(out_path)
   199	    validate_output_name(out_path.name)
   200	    previous_outputs = (
   201	        ()
   202	        if keep_previous_renders
   203	        else _previous_render_outputs_for_timeline(out_path, timeline_path)
   204	    )
   205	    config = _legacy_backend_config(
   206	        project_dir=project_dir,
   207	        composition_id=composition_id,
   208	        theme_path=theme_path,
   209	        min_free_gb=min_free_gb,
   210	    )
   211	    for key, value in (backend_config or {}).items():
   212	        if value is None:
   213	            continue
   214	        existing = config.get(str(key))
   215	        if existing is None:
   216	            config[str(key)] = dict(value)
   217	        else:
   218	            # Explicit caller configuration overlays, never replaces, the
   219	            # legacy-derived settings so project/theme/composition values
   220	            # survive a partial --backend-config payload.
   221	            overlaid = dict(existing)
   222	            overlaid.update({k: v for k, v in value.items() if v is not None})
   223	            config[str(key)] = overlaid
   224	    return _default_service().render(
   225	        timeline_path,
   226	        assets_path,
   227	        out_path,
   228	        selector=engine,
   229	        backend_config=config,
   230	        previous_outputs=previous_outputs,
   231	    )
   232	
   233	
   234	def main(argv: Sequence[str] | None = None) -> int:
   235	    parser = argparse.ArgumentParser()
   236	    parser.add_argument("--timeline", type=Path, required=True)
   237	    parser.add_argument("--assets", type=Path)
   238	    parser.add_argument("--out", type=Path, required=True)
   239	    parser.add_argument(
   240	        "--engine",
   241	        default="remotion",
   242	        help="Legacy selector (remotion, ffmpeg, hybrid) or a qualified renderer id.",
   243	    )
   244	    parser.add_argument(
   245	        "--backend",
   246	        default=None,
   247	        help="Neutral alias for --engine: legacy selector or qualified backend id.",
   248	    )
   249	    parser.add_argument(
   250	        "--backend-config",
   251	        default=None,
   252	        help="JSON object keyed by qualified backend id with per-backend configuration.",
   253	    )
   254	    parser.add_argument(
   255	        "--output-name",
   256	        default=None,
   257	        help="Output file name (default hype.mp4); plain .mp4 file name only.",
   258	    )
   259	    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
   260	    parser.add_argument("--composition", default="TimelineComposition")

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '234,360p' && rg -n \"engine.*backend|backend.*engine|conflict|explicit backend|backend_config|alias_chain|override|rejected|single.segment|single_segment|real_ffmpeg|real_hybrid\" tests/core/rendering/test_service.py tests/packs/rendering tests/core/rendering/test_legacy_hybrid.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 7ms:
tests/packs/rendering/test_legacy_renderer_characterization.py:35:        "theme_overrides": {
tests/packs/rendering/test_legacy_renderer_characterization.py:95:        "theme_overrides": {
tests/packs/rendering/test_legacy_renderer_characterization.py:183:    assert call_kwargs["backend_config"]["rendering.remotion"] == {
tests/packs/rendering/test_legacy_renderer_characterization.py:212:    assert call_kwargs["backend_config"]["rendering.legacy_hybrid"] == {
tests/packs/rendering/test_legacy_renderer_characterization.py:215:    assert call_kwargs["backend_config"]["rendering.remotion"] == {
tests/packs/rendering/test_legacy_renderer_characterization.py:260:def test_unknown_engine_rejected(tmp_path: Path) -> None:
tests/packs/rendering/test_legacy_renderer_characterization.py:557:        "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
tests/packs/rendering/test_legacy_renderer_characterization.py:582:def test_transition_duration_seconds_overrides_default() -> None:
tests/packs/rendering/test_legacy_renderer_characterization.py:621:        "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
tests/packs/rendering/test_legacy_renderer_characterization.py:648:        "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
tests/packs/rendering/test_legacy_renderer_characterization.py:689:    assert "--engine" in help_text  # the only backend selection surface
tests/packs/rendering/test_builtin_registration.py:50:                "theme_overrides": {
tests/packs/rendering/test_builtin_registration.py:105:        backend_config={backend: backend_settings or {}},
tests/packs/rendering/test_builtin_registration.py:193:def test_real_ffmpeg_render_through_registered_backend(tmp_path: Path) -> None:
tests/packs/rendering/test_render_facade.py:61:    assert call_kwargs["backend_config"]["rendering.remotion"] == {
tests/packs/rendering/test_render_facade.py:81:def test_render_maps_legacy_kwargs_into_namespaced_backend_config(
tests/packs/rendering/test_render_facade.py:98:    config = fake_service.calls[0][1]["backend_config"]
tests/packs/rendering/test_render_facade.py:110:def test_render_merges_explicit_backend_config_after_legacy_kwargs(
tests/packs/rendering/test_render_facade.py:121:        backend_config={
tests/packs/rendering/test_render_facade.py:123:                "theme_path": str(tmp_path / "override.json"),
tests/packs/rendering/test_render_facade.py:130:    config = fake_service.calls[0][1]["backend_config"]
tests/packs/rendering/test_render_facade.py:131:    assert config["rendering.remotion"]["theme_path"] == str(tmp_path / "override.json")
tests/packs/rendering/test_ffmpeg_finalizer.py:95:        alias_chain=[],
tests/packs/rendering/test_ffmpeg_finalizer.py:96:        override=None,
tests/packs/rendering/test_ffmpeg_finalizer.py:200:        backend_config={ffmpeg_finalizer.BACKEND_ID: {"faststart": True}},
tests/packs/rendering/test_ffmpeg_finalizer.py:395:def test_duration_error_is_rejected_before_any_assembly_command(
tests/packs/rendering/test_ffmpeg_finalizer.py:424:def test_missing_video_and_rendered_audio_are_rejected() -> None:
tests/packs/rendering/test_ffmpeg_finalizer.py:676:def test_real_ffmpeg_normalizes_rational_profile_and_emits_valid_media(
tests/packs/rendering/test_ffmpeg_finalizer.py:741:        backend_config={ffmpeg_finalizer.BACKEND_ID: {"faststart": True}},
tests/packs/rendering/test_ffmpeg_support.py:71:        "theme_overrides": {
tests/packs/rendering/test_ffmpeg_support.py:136:        backend_config={ffmpeg.BACKEND_ID: {}},
tests/packs/rendering/test_ffmpeg_support.py:496:        "theme_overrides": {
tests/packs/rendering/test_ffmpeg_support.py:627:def test_pinned_video_profile_and_level_are_rejected_as_unguaranteed(
tests/packs/rendering/test_audio_reactive_colour.py:21:        "theme_overrides": {
tests/packs/rendering/test_audio_reactive_colour.py:161:def test_real_ffmpeg_render_has_exact_marker_frames_and_audio(tmp_path: Path) -> None:
tests/packs/rendering/test_ffmpeg_backend.py:65:        "theme_overrides": {
tests/packs/rendering/test_ffmpeg_backend.py:127:        backend_config={ffmpeg.BACKEND_ID: {}},
tests/packs/rendering/test_ffmpeg_backend.py:259:    request_payload["backend_config"] = {}
tests/packs/rendering/test_ffmpeg_backend.py:435:def test_facade_engine_ffmpeg_delegates_to_backend_seam(tmp_path: Path) -> None:
tests/packs/rendering/test_remotion_backend.py:86:        backend_config={

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_service.py | sed -n '500,750p;1450,1585p;1960,2105p' && nl -ba tests/packs/rendering/test_render_facade.py | sed -n '1,190p' && rg -n \"conflict; supply|both.*engine|--backend\" tests/packs/rendering/test_render_facade.py tests/packs/rendering/test_legacy_renderer_characterization.py tests/core/rendering/test_output_name.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
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
   561	
   562	
   563	def test_legacy_ffmpeg_is_strict(tmp_path: Path) -> None:
   564	    transport = FakeTransport()
   565	    service = _service(tmp_path, transport)
   566	
   567	    service.render_request(
   568	        _request(tmp_path),
   569	        selector="ffmpeg",
   570	        out_path=tmp_path / "legacy-ffmpeg.mp4",
   571	    )
   572	
   573	    assert transport.calls == [
   574	        ("support", "rendering.ffmpeg"),
   575	        ("render", "rendering.ffmpeg"),
   576	    ]
   577	
   578	
   579	def test_hybrid_selects_planner_and_executes_its_segment(tmp_path: Path) -> None:
   580	    transport = FakeTransport()
   581	    transport.plan = _plan("fixture.window")
   582	    service = _service(
   583	        tmp_path,
   584	        transport,
   585	        renderer_ids=("fixture.window",),
   586	        planner_ids=("rendering.legacy_hybrid",),
   587	    )
   588	
   589	    service.render_request(
   590	        _request(tmp_path),
   591	        selector="hybrid",
   592	        out_path=tmp_path / "hybrid.mp4",
   593	    )
   594	
   595	    assert transport.calls[:2] == [
   596	        ("support", "rendering.legacy_hybrid"),
   597	        ("plan", "rendering.legacy_hybrid"),
   598	    ]
   599	    assert ("render", "fixture.window") in transport.calls
   600	    # The plan pins the ffmpeg finalizer; even a single-segment hybrid plan
   601	    # runs it (profile/audio normalization is the finalizer's contract).
   602	    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
   603	
   604	
   605	def test_planned_window_is_materialized_for_full_timeline_renderer(
   606	    tmp_path: Path,
   607	) -> None:
   608	    transport = FakeTransport()
   609	    transport.plan = _plan("fixture.full")
   610	    renderers = RendererRegistry(
   611	        [
   612	            _candidate(
   613	                tmp_path,
   614	                "fixture.full",
   615	                "renderer",
   616	                capabilities={
   617	                    "supports_full_timeline": True,
   618	                    "supports_windows": False,
   619	                },
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
  1450	    with pytest.raises(ValueError, match=r"\.mp4"):
  1451	        validate_output_name("out.mov")
  1452	
  1453	
  1454	def test_hype_mp4_default_output_name_is_preserved(tmp_path: Path) -> None:
  1455	    transport = FakeTransport()
  1456	    service = _service(tmp_path, transport)
  1457	    output = tmp_path / "published" / "hype.mp4"
  1458	    request = replace(_request(tmp_path), output_name="hype.mp4")
  1459	
  1460	    service.render_request(
  1461	        request, selector="rendering.ffmpeg", out_path=output
  1462	    )
  1463	
  1464	    render_payloads = [
  1465	        payload
  1466	        for verb, backend, payload in transport.payloads
  1467	        if verb == "render" and backend == "rendering.ffmpeg"
  1468	    ]
  1469	    assert len(render_payloads) == 1
  1470	    assert render_payloads[0]["output_name"] == "hype.mp4"
  1471	    payload = _sidecar(output)
  1472	    assert payload["output"] == str(output.resolve())
  1473	    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
  1474	
  1475	
  1476	@pytest.mark.parametrize(
  1477	    (
  1478	        "selector",
  1479	        "plan_segments",
  1480	        "backend_config",
  1481	        "expect_finalize",
  1482	        "expected_engine",
  1483	    ),
  1484	    [
  1485	        ("rendering.remotion", None, {}, False, "rendering.remotion"),
  1486	        ("rendering.ffmpeg", None, {}, False, "rendering.ffmpeg"),
  1487	        (
  1488	            "rendering.ffmpeg",
  1489	            None,
  1490	            {"rendering.ffmpeg": {"mode": "optimized", "stream_copy": True}},
  1491	            False,
  1492	            "rendering.ffmpeg",
  1493	        ),
  1494	        (
  1495	            "rendering.ffmpeg",
  1496	            None,
  1497	            {"rendering.ffmpeg": {"audio_reactive": True}},
  1498	            False,
  1499	            "rendering.ffmpeg",
  1500	        ),
  1501	        ("hybrid", (10,), {}, True, "hybrid"),
  1502	        ("hybrid", (5, 5), {}, True, "hybrid"),
  1503	    ],
  1504	    ids=[
  1505	        "remotion",
  1506	        "ffmpeg",
  1507	        "ffmpeg-optimized",
  1508	        "ffmpeg-audio-reactive",
  1509	        "hybrid-single-segment",
  1510	        "hybrid-multi-segment",
  1511	    ],
  1512	)
  1513	def test_builtin_paths_commit_exactly_one_video_and_sidecar(
  1514	    tmp_path: Path,
  1515	    selector: str,
  1516	    plan_segments: tuple[int, ...] | None,
  1517	    backend_config: dict[str, dict[str, Any]],
  1518	    expect_finalize: bool,
  1519	    expected_engine: str,
  1520	) -> None:
  1521	    transport = FakeTransport()
  1522	    if plan_segments is not None:
  1523	        transport.plan = _plan("fixture.window", segment_frames=plan_segments)
  1524	        service = _service(
  1525	            tmp_path,
  1526	            transport,
  1527	            renderer_ids=("fixture.window",),
  1528	            planner_ids=("rendering.legacy_hybrid",),
  1529	        )
  1530	    else:
  1531	        service = _service(tmp_path, transport)
  1532	    output = tmp_path / "builtin.mp4"
  1533	    request = replace(_request(tmp_path), backend_config=backend_config)
  1534	
  1535	    service.render_request(request, selector=selector, out_path=output)
  1536	
  1537	    assert output.is_file()
  1538	    sidecars = list(tmp_path.glob("*.provenance.json"))
  1539	    assert sidecars == [Path(f"{output}.provenance.json")]
  1540	    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
  1541	    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
  1542	    assert payload["output"] == str(output.resolve())
  1543	    assert payload["routing"]["requested_engine"] == expected_engine
  1544	    assert payload["routing"]["auto_route"] is False
  1545	    assert payload["audio_ownership"] == "none"
  1546	    for _verb, backend, payload_data in transport.payloads:
  1547	        if backend in backend_config:
  1548	            assert payload_data["backend_config"][backend] == backend_config[backend]
  1549	    if expect_finalize:
  1550	        assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
  1551	    else:
  1552	        assert not any(verb == "finalize" for verb, _backend in transport.calls)
  1553	    assert not list(tmp_path.glob(".*.render-service-*"))
  1554	
  1555	
  1556	def test_raw_mixed_plan_routes_windows_and_aligns_segment_provenance(
  1557	    tmp_path: Path,
  1558	) -> None:
  1559	    transport = FakeTransport()
  1560	    request = _mixed_plan(
  1561	        tmp_path,
  1562	        transport,
  1563	        config={
  1564	            "simple_renderers": ["raw_command.renderer"],
  1565	            "complex_renderers": ["rendering.remotion"],
  1566	        },
  1567	    )
  1568	    service = _mixed_service(tmp_path, transport)
  1569	    output = tmp_path / "mixed.mp4"
  1570	
  1571	    service.render_request(request, selector="hybrid", out_path=output)
  1572	
  1573	    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
  1574	    assert render_calls == [
  1575	        "raw_command.renderer",
  1576	        "rendering.remotion",
  1577	        "raw_command.renderer",
  1578	    ]
  1579	    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
  1580	    payload = _sidecar(output)
  1581	    segments = payload["segments_v2"]
  1582	    assert [segment["renderer"]["id"] for segment in segments] == [
  1583	        "raw_command.renderer",
  1584	        "rendering.remotion",
  1585	        "raw_command.renderer",
  1960	            "-y",
  1961	            "-f",
  1962	            "lavfi",
  1963	            "-i",
  1964	            "sine=frequency=440:sample_rate=48000:duration=0.5",
  1965	            "-c:a",
  1966	            "aac",
  1967	            "-b:a",
  1968	            "128k",
  1969	            str(audio_path),
  1970	        ],
  1971	        check=True,
  1972	        capture_output=True,
  1973	        text=True,
  1974	    )
  1975	    muxed = timeline_path.parent / "muxed.mp4"
  1976	    subprocess.run(
  1977	        [
  1978	            "ffmpeg",
  1979	            "-hide_banner",
  1980	            "-loglevel",
  1981	            "error",
  1982	            "-y",
  1983	            "-i",
  1984	            str(source),
  1985	            "-i",
  1986	            str(audio_path),
  1987	            "-c:v",
  1988	            "copy",
  1989	            "-c:a",
  1990	            "aac",
  1991	            "-shortest",
  1992	            str(muxed),
  1993	        ],
  1994	        check=True,
  1995	        capture_output=True,
  1996	        text=True,
  1997	    )
  1998	    muxed.replace(source)
  1999	
  2000	
  2001	@pytest.mark.parametrize(
  2002	    "media_kind",
  2003	    ["plain", "audio"],
  2004	    ids=["nominal", "with-audio"],
  2005	)
  2006	def test_real_ffmpeg_renders_through_generic_service(
  2007	    tmp_path: Path,
  2008	    media_kind: str,
  2009	) -> None:
  2010	    """The service drives the real FFmpeg backend end to end: one video and
  2011	    one committed sidecar through the real CommandTransport (no fake
  2012	    transport), including the whole-media optimized path when the source
  2013	    probe supports it."""
  2014	    _require_ffmpeg()
  2015	    timeline_path, assets_path = _real_media_inputs(tmp_path)
  2016	    if media_kind == "audio":
  2017	        _add_audio_track(timeline_path)
  2018	    service = _real_service(tmp_path)
  2019	    output = tmp_path / "real-ffmpeg.mp4"
  2020	
  2021	    service.render_request(
  2022	        replace(
  2023	            _request(tmp_path),
  2024	            timeline_path=str(timeline_path),
  2025	            assets_registry_path=str(assets_path),
  2026	        ),
  2027	        selector="rendering.ffmpeg",
  2028	        out_path=output,
  2029	    )
  2030	
  2031	    assert output.is_file()
  2032	    assert output.stat().st_size > 0
  2033	    sidecars = list(tmp_path.glob("*.provenance.json"))
  2034	    assert sidecars == [Path(f"{output}.provenance.json")]
  2035	    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
  2036	    assert payload["output"] == str(output.resolve())
  2037	    assert payload["routing"]["requested_engine"] == "rendering.ffmpeg"
  2038	
  2039	
  2040	def test_real_hybrid_plans_assigns_ffmpeg_and_finalizes_through_service(
  2041	    tmp_path: Path,
  2042	) -> None:
  2043	    """Real hybrid planning: the media-only timeline routes every window to
  2044	    the real FFmpeg backend and the real ffmpeg finalizer concatenates."""
  2045	    _require_ffmpeg()
  2046	    timeline_path, assets_path = _real_media_inputs(tmp_path)
  2047	    service = _real_service(tmp_path)
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
     1	"""Facade-boundary tests for ``rendering.render`` after the T4.2 rework.
     2	
     3	The facade keeps its public ``render(...)`` signature and the
     4	``rendering.render`` capability id, but delegates all dispatch to
     5	:class:`RenderService`: legacy engine translation, renderer/planner selection,
     6	support, invocation, validation, and publication.  These tests pin the
     7	facade's delegation surface without spawning any media tool.
     8	"""
     9	
    10	from __future__ import annotations
    11	
    12	from pathlib import Path
    13	
    14	import pytest
    15	
    16	from astrid.packs.rendering.executors.render import run as render_run
    17	
    18	
    19	class _FakeService:
    20	    def __init__(self, sentinel: Path | None = None) -> None:
    21	        self.sentinel = sentinel
    22	        self.calls: list[tuple[tuple, dict]] = []
    23	
    24	    def render(self, *args, **kwargs) -> Path:
    25	        self.calls.append((args, kwargs))
    26	        if self.sentinel is not None:
    27	            return self.sentinel
    28	        raise AssertionError("unexpected service render call")
    29	
    30	
    31	@pytest.fixture
    32	def fake_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _FakeService:
    33	    fake = _FakeService(tmp_path / "sentinel.mp4")
    34	    monkeypatch.setattr(render_run, "_default_service", lambda: fake)
    35	    return fake
    36	
    37	
    38	def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    39	    timeline = tmp_path / "hype.timeline.json"
    40	    assets = tmp_path / "hype.assets.json"
    41	    out = tmp_path / "out" / "hype.mp4"
    42	    timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
    43	    assets.write_text('{"assets": {}}', encoding="utf-8")
    44	    return timeline, assets, out
    45	
    46	
    47	def test_render_delegates_to_service_with_default_selector(fake_service: _FakeService, tmp_path: Path) -> None:
    48	    timeline, assets, out = _inputs(tmp_path)
    49	    sentinel = tmp_path / "sentinel.mp4"
    50	    fake_service.sentinel = sentinel
    51	
    52	    result = render_run.render(timeline, assets, out)
    53	
    54	    assert result == sentinel
    55	    assert len(fake_service.calls) == 1
    56	    (call_args, call_kwargs) = fake_service.calls[0]
    57	    assert call_args == (timeline, assets, out)
    58	    assert call_kwargs["selector"] == "remotion"
    59	    assert call_kwargs["previous_outputs"] == ()
    60	    # Legacy kwargs map onto namespaced backend config.
    61	    assert call_kwargs["backend_config"]["rendering.remotion"] == {
    62	        "composition_id": "TimelineComposition"
    63	    }
    64	
    65	
    66	@pytest.mark.parametrize(
    67	    "engine",
    68	    ["remotion", "ffmpeg", "hybrid", "rendering.remotion", "rendering.ffmpeg"],
    69	)
    70	def test_render_forwards_legacy_and_qualified_selectors(
    71	    fake_service: _FakeService, tmp_path: Path, engine: str
    72	) -> None:
    73	    timeline, assets, out = _inputs(tmp_path)
    74	
    75	    render_run.render(timeline, assets, out, engine=engine)
    76	
    77	    assert len(fake_service.calls) == 1
    78	    assert fake_service.calls[0][1]["selector"] == engine
    79	
    80	
    81	def test_render_maps_legacy_kwargs_into_namespaced_backend_config(
    82	    fake_service: _FakeService, tmp_path: Path
    83	) -> None:
    84	    timeline, assets, out = _inputs(tmp_path)
    85	
    86	    render_run.render(
    87	        timeline,
    88	        assets,
    89	        out,
    90	        engine="hybrid",
    91	        project_dir=tmp_path / "remotion",
    92	        composition_id="CustomComposition",
    93	        theme_path=tmp_path / "theme.json",
    94	        min_free_gb=2.0,
    95	    )
    96	
    97	    assert len(fake_service.calls) == 1
    98	    config = fake_service.calls[0][1]["backend_config"]
    99	    assert config["rendering.remotion"] == {
   100	        "project_dir": str(tmp_path / "remotion"),
   101	        "composition_id": "CustomComposition",
   102	        "theme_path": str(tmp_path / "theme.json"),
   103	        "min_free_gb": 2.0,
   104	    }
   105	    assert config["rendering.legacy_hybrid"] == {
   106	        "theme_path": str(tmp_path / "theme.json")
   107	    }
   108	
   109	
   110	def test_render_merges_explicit_backend_config_after_legacy_kwargs(
   111	    fake_service: _FakeService, tmp_path: Path
   112	) -> None:
   113	    timeline, assets, out = _inputs(tmp_path)
   114	
   115	    render_run.render(
   116	        timeline,
   117	        assets,
   118	        out,
   119	        engine="rendering.remotion",
   120	        theme_path=tmp_path / "theme.json",
   121	        backend_config={
   122	            "rendering.remotion": {
   123	                "theme_path": str(tmp_path / "override.json"),
   124	                "min_free_gb": 9.5,
   125	            }
   126	        },
   127	    )
   128	
   129	    assert len(fake_service.calls) == 1
   130	    config = fake_service.calls[0][1]["backend_config"]
   131	    assert config["rendering.remotion"]["theme_path"] == str(tmp_path / "override.json")
   132	    assert config["rendering.remotion"]["min_free_gb"] == 9.5
   133	
   134	
   135	def test_render_passes_previous_outputs_when_preserving(fake_service: _FakeService, tmp_path: Path) -> None:
   136	    timeline, assets, out = _inputs(tmp_path)
   137	
   138	    render_run.render(timeline, assets, out, keep_previous_renders=True)
   139	
   140	    assert len(fake_service.calls) == 1
   141	    assert fake_service.calls[0][1]["previous_outputs"] == ()
   142	
   143	
   144	def test_render_validates_output_name_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
   145	    timeline, assets, _out = _inputs(tmp_path)
   146	    bad_out = tmp_path / "out" / "video.mov"
   147	
   148	    with pytest.raises(ValueError, match=r"\.mp4"):
   149	        render_run.render(timeline, assets, bad_out)
   150	
   151	
   152	def test_main_accepts_output_name_and_forward_parses_any_order(
   153	    fake_service: _FakeService, tmp_path: Path, capsys: pytest.CaptureFixture[str]
   154	) -> None:
   155	    timeline, assets, out = _inputs(tmp_path)
   156	    out = tmp_path / "out" / "iteration.mp4"
   157	    fake_service.sentinel = out
   158	
   159	    result = render_run.main(
   160	        [
   161	            "--out",
   162	            str(out),
   163	            "--output-name",
   164	            "iteration.mp4",
   165	            "--timeline",
   166	            str(timeline),
   167	            "--assets",
   168	            str(assets),
   169	            "--engine",
   170	            "rendering.ffmpeg",
   171	        ]
   172	    )
   173	
   174	    assert result == 0
   175	    assert capsys.readouterr().out.strip() == str(out)
   176	    assert len(fake_service.calls) == 1
   177	    assert fake_service.calls[0][1]["selector"] == "rendering.ffmpeg"
   178	
   179	
   180	def test_main_rejects_traversal_output_name(
   181	    tmp_path: Path, capsys: pytest.CaptureFixture[str]
   182	) -> None:
   183	    timeline, assets, _out = _inputs(tmp_path)
   184	
   185	    result = render_run.main(
   186	        [
   187	            "--timeline",
   188	            str(timeline),
   189	            "--assets",
   190	            str(assets),

exec
/bin/zsh -lc "nl -ba tests/packs/rendering/test_render_facade.py | sed -n '180,330p' && git diff --unified=40 a72729db..98f4edea -- tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering/test_render_remotion_registry.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   180	def test_main_rejects_traversal_output_name(
   181	    tmp_path: Path, capsys: pytest.CaptureFixture[str]
   182	) -> None:
   183	    timeline, assets, _out = _inputs(tmp_path)
   184	
   185	    result = render_run.main(
   186	        [
   187	            "--timeline",
   188	            str(timeline),
   189	            "--assets",
   190	            str(assets),
   191	            "--out",
   192	            str(tmp_path / "out" / "hype.mp4"),
   193	            "--output-name",
   194	            "../evil.mp4",
   195	        ]
   196	    )
   197	
   198	    assert result == 1
   199	    assert "traverse" in capsys.readouterr().err
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/packs/rendering/test_legacy_renderer_characterization.py b/tests/packs/rendering/test_legacy_renderer_characterization.py
index 8fe6c19f..55433138 100644
--- a/tests/packs/rendering/test_legacy_renderer_characterization.py
+++ b/tests/packs/rendering/test_legacy_renderer_characterization.py
@@ -1,61 +1,62 @@
 """Characterization tests for the legacy monolith render path (T1.1).
 
 These tests pin today's behavior of
 ``astrid/packs/rendering/executors/render/run.py`` so the later backend
 extraction can be proven behavior-preserving. They never spawn a real render
 (no ``npx remotion``, no ``ffmpeg``): engine routing, eligibility, provenance,
 and duration math are exercised through the public helpers with heavy
 dependencies mocked out.
 
 Baseline recorded in ``.oracle/baseline.md`` (dirty-tree snapshot 6b2ff1a).
 """
 
 from __future__ import annotations
 
 import json
 from pathlib import Path
 from unittest.mock import patch
 
 import pytest
 
 from astrid.packs.rendering.executors.render import audio_reactive_colour
+from astrid.packs.rendering.executors.render import legacy_engine
 from astrid.packs.rendering.executors.render import run as render_run
 
 
 # ---------------------------------------------------------------------------
 # fixture builders (plain dicts, no subprocesses)
 # ---------------------------------------------------------------------------
 
 
 def _media_only_timeline() -> dict:
     """A timeline the ffmpeg engine can fully service."""
     return {
         "theme": "banodoco-default",
         "theme_overrides": {
             "visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}
         },
         "tracks": [
             {"id": "v", "kind": "visual", "label": "Video"},
             {"id": "a", "kind": "audio", "label": "Audio"},
         ],
         "clips": [
             {
                 "id": "clip_a",
                 "at": 0,
                 "track": "v",
                 "clipType": "media",
                 "asset": "main",
                 "from": 0,
                 "to": 2,
                 "speed": 1,
                 "volume": 0,
             },
             {
                 "id": "clip_b",
                 "at": 0,
                 "track": "a",
                 "clipType": "media",
                 "asset": "main",
                 "from": 0,
                 "to": 2,
                 "speed": 1,
@@ -257,432 +258,432 @@ def test_engine_remotion_complex_timeline_still_delegates(tmp_path: Path, monkey
 
 
 def test_unknown_engine_rejected(tmp_path: Path) -> None:
     """Legacy translation lives in the service: an unknown selector is a
     structured unsupported error, not a facade ValueError."""
     from astrid.core.rendering.errors import RendererUnsupportedError
 
     timeline_path = _write_timeline(tmp_path, _media_only_timeline())
     assets_path = _write_assets(tmp_path)
     out_path = tmp_path / "out" / "hype.mp4"
 
     with pytest.raises(RendererUnsupportedError, match="unknown renderer selector"):
         render_run.render(timeline_path, assets_path, out_path, engine="imovie")
 
 
 def test_engine_selection_does_not_short_circuit_in_facade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
     """The audio-reactive specialization is service-side support evidence; the
     facade forwards every engine spelling without branching."""
     timeline_path = _write_timeline(tmp_path, _media_only_timeline())
     assets_path = _write_assets(tmp_path)
     out_path = tmp_path / "out" / "hype.mp4"
     sentinel = tmp_path / "audio_reactive.mp4"
     fake = _patch_service(monkeypatch, sentinel)
 
     result = render_run.render(timeline_path, assets_path, out_path, engine="hybrid")
 
     assert result == sentinel
     assert len(fake.calls) == 1
     assert fake.calls[0][1]["selector"] == "hybrid"
 
 
 # ---------------------------------------------------------------------------
 # nominal-Remotion auto-FFmpeg eligibility
 # ---------------------------------------------------------------------------
 
 
 def test_can_render_with_ffmpeg_media_accepts_media_only_timeline(tmp_path: Path) -> None:
     timeline_path = _write_timeline(tmp_path, _media_only_timeline())
     assets_path = _write_assets(tmp_path)
 
-    assert render_run._can_render_with_ffmpeg_media(timeline_path, assets_path) is True
+    assert legacy_engine._can_render_with_ffmpeg_media(timeline_path, assets_path) is True
 
 
 def test_can_render_with_ffmpeg_media_rejects_text_card_timeline(tmp_path: Path) -> None:
     timeline_path = _write_timeline(tmp_path, _text_card_timeline())
     assets_path = _write_assets(tmp_path)
 
-    assert render_run._can_render_with_ffmpeg_media(timeline_path, assets_path) is False
+    assert legacy_engine._can_render_with_ffmpeg_media(timeline_path, assets_path) is False
 
 
 # ---------------------------------------------------------------------------
 # audio-reactive early selection
 # ---------------------------------------------------------------------------
 
 
 def test_audio_reactive_specialization_contract_check(tmp_path: Path) -> None:
     """match_and_validate is the entry predicate: a valid 2-clip timeline yields a spec."""
     audio_path = tmp_path / "tone.wav"
     audio_path.write_bytes(b"placeholder")
     registry = {
         "assets": {
             "audio": {
                 "file": str(audio_path),
                 "type": "audio/wav",
                 "duration": 0.5,
             }
         }
     }
 
     spec = audio_reactive_colour.match_and_validate(
         _audio_reactive_timeline(), registry, tmp_path / "hype.assets.json"
     )
 
     assert spec is not None
     assert spec.fps == 30
     assert spec.total_frames == 15  # hold 0.5s * 30fps
     assert len(spec.marker_sha256) == 64
 
 
 def test_audio_reactive_selection_precedes_engine_dispatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
     """The specialization is service-side; the facade never short-circuits.
 
     Superseded by ``test_engine_selection_does_not_short_circuit_in_facade``;
     kept as a named placeholder so the audio-reactive section stays greppable.
     """
     timeline_path = _write_timeline(tmp_path, _media_only_timeline())
     assets_path = _write_assets(tmp_path)
     out_path = tmp_path / "out" / "hype.mp4"
     sentinel = tmp_path / "audio_reactive.mp4"
     fake = _patch_service(monkeypatch, sentinel)
     with patch.object(
-        render_run, "_render_audio_reactive_colour_if_supported", return_value=sentinel
-    ) as specialized, patch.object(render_run, "_render_hybrid") as hybrid:
+        legacy_engine, "_render_audio_reactive_colour_if_supported", return_value=sentinel
+    ) as specialized, patch.object(legacy_engine, "_render_hybrid") as hybrid:
         result = render_run.render(timeline_path, assets_path, out_path, engine="hybrid")
 
     # The facade forwards to the service; the specialization helper is not
     # consulted by render() anymore.
     assert result == sentinel
     assert len(fake.calls) == 1
     specialized.assert_not_called()
     hybrid.assert_not_called()
 
 
 def test_audio_reactive_shape_gate_rejects_non_two_clip_timeline(tmp_path: Path) -> None:
     """3 clips -> None before any element/registry work."""
     data = _media_only_timeline()
     data["clips"].append({"id": "extra", "at": 0, "track": "v", "clipType": "text-card", "hold": 0.5})
     timeline_path = _write_timeline(tmp_path, data)
     assets_path = _write_assets(tmp_path)
     out_path = tmp_path / "out" / "hype.mp4"
 
-    with patch.object(render_run, "_audio_reactive_ffmpeg_element") as element:
-        result = render_run._render_audio_reactive_colour_if_supported(
+    with patch.object(legacy_engine, "_audio_reactive_ffmpeg_element") as element:
+        result = legacy_engine._render_audio_reactive_colour_if_supported(
             timeline_path,
             assets_path,
             out_path,
             project_dir=None,
             composition_id="TimelineComposition",
             theme_path=None,
         )
 
     assert result is None
     element.assert_not_called()
 
 
 # ---------------------------------------------------------------------------
 # v1 provenance keys
 # ---------------------------------------------------------------------------
 
 
 def test_render_provenance_v1_key_set(tmp_path: Path) -> None:
     out_path = tmp_path / "hype.mp4"
     timeline_path = tmp_path / "hype.timeline.json"
     assets_path = tmp_path / "hype.assets.json"
     timeline_path.write_text("{}", encoding="utf-8")
     assets_path.write_text("{}", encoding="utf-8")
 
-    with patch.object(render_run, "_active_pack_order_for_provenance", return_value=[]):
-        sidecar = render_run._write_render_provenance(
+    with patch.object(legacy_engine, "_active_pack_order_for_provenance", return_value=[]):
+        sidecar = legacy_engine._write_render_provenance(
             out_path,
             engine="remotion",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=tmp_path / "remotion",
             composition_id="TimelineComposition",
             theme_path=None,
             active_theme=None,
             registry_state={"hash": "abc123"},
             stage_summary={"root": None, "effects": []},
         )
 
     payload = json.loads(sidecar.read_text(encoding="utf-8"))
     assert set(payload) == {
         "schema_version",
         "engine",
         "output",
         "timeline",
         "assets_registry",
         "project_dir",
         "composition_id",
         "active_pack_order",
         "active_theme",
         "registry_hash",
         "registry_state",
         "resolved_effect_ids",
         "resolved_effects",
         "source_pack_ids",
         "element_roots",
         "staged_asset_ids",
         "staged_asset_root",
     }
     assert payload["schema_version"] == 1
     assert payload["engine"] == "remotion"
     assert payload["registry_hash"] == "abc123"
     assert payload["active_theme"] == {"id": "banodoco-default", "path": None}
 
 
 def test_render_provenance_hybrid_adds_segment_keys(tmp_path: Path) -> None:
     out_path = tmp_path / "hype.mp4"
     timeline_path = tmp_path / "hype.timeline.json"
     assets_path = tmp_path / "hype.assets.json"
     timeline_path.write_text("{}", encoding="utf-8")
     assets_path.write_text("{}", encoding="utf-8")
     segments = [{"engine": "ffmpeg", "from": 0.0, "to": 1.0}]
     segment_provenance = [{"engine": "remotion", "output": "/tmp/seg.mp4"}]
 
-    with patch.object(render_run, "_active_pack_order_for_provenance", return_value=[]):
-        sidecar = render_run._write_render_provenance(
+    with patch.object(legacy_engine, "_active_pack_order_for_provenance", return_value=[]):
+        sidecar = legacy_engine._write_render_provenance(
             out_path,
             engine="hybrid",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=tmp_path / "remotion",
             composition_id="TimelineComposition",
             theme_path=None,
             active_theme=None,
             registry_state={"hash": "x"},
             stage_summary={"root": None, "effects": []},
             segments=segments,
             segment_provenance=segment_provenance,
         )
 
     payload = json.loads(sidecar.read_text(encoding="utf-8"))
     assert payload["segments"] == segments
     assert payload["segment_provenance"] == segment_provenance
 
 
 # ---------------------------------------------------------------------------
 # transition units (pure math, no subprocess)
 # ---------------------------------------------------------------------------
 
 
 def test_timeline_duration_prefers_explicit_metadata() -> None:
     data = _media_only_timeline()
     data["metadata"] = {"duration_seconds": 12.5}
-    assert render_run._timeline_duration_seconds(data) == 12.5
+    assert legacy_engine._timeline_duration_seconds(data) == 12.5
 
 
 def test_timeline_duration_falls_back_to_expected_duration_seconds() -> None:
     data = _media_only_timeline()
     data["metadata"] = {"expected_duration_seconds": 7.25}
-    assert render_run._timeline_duration_seconds(data) == 7.25
+    assert legacy_engine._timeline_duration_seconds(data) == 7.25
 
 
 def test_timeline_duration_computed_from_clips_when_no_metadata() -> None:
-    assert render_run._timeline_duration_seconds(_media_only_timeline()) == 2.0
+    assert legacy_engine._timeline_duration_seconds(_media_only_timeline()) == 2.0
 
 
 def test_clip_duration_and_timeline_end_math() -> None:
     media_clip = {"at": 1.0, "from": 10.0, "to": 16.0, "speed": 2.0, "clipType": "media"}
-    assert render_run._clip_duration_seconds(media_clip) == 3.0
-    assert render_run._clip_timeline_end_seconds(media_clip) == 4.0
+    assert legacy_engine._clip_duration_seconds(media_clip) == 3.0
+    assert legacy_engine._clip_timeline_end_seconds(media_clip) == 4.0
 
     hold_clip = {"at": 2.0, "clipType": "text-card", "hold": 1.5}
-    assert render_run._clip_timeline_end_seconds(hold_clip) == 3.5
+    assert legacy_engine._clip_timeline_end_seconds(hold_clip) == 3.5
 
     to_clip = {"at": 0.0, "clipType": "text-card", "to": 5.0}
-    assert render_run._clip_timeline_end_seconds(to_clip) == 5.0
+    assert legacy_engine._clip_timeline_end_seconds(to_clip) == 5.0
 
 
 def test_round_frame_time_modes() -> None:
     fps = 30
-    assert render_run._round_frame_time(0.0167, fps, mode="floor") == 0.0
-    assert render_run._round_frame_time(0.0167, fps, mode="ceil") == pytest.approx(1 / fps)
-    assert render_run._round_frame_time(0.0167, fps, mode="round") == pytest.approx(1 / fps)
-    assert render_run._round_frame_time(1 / fps, fps, mode="floor") == pytest.approx(1 / fps)
-    assert render_run._round_frame_time(1 / fps, fps, mode="ceil") == pytest.approx(1 / fps)
+    assert legacy_engine._round_frame_time(0.0167, fps, mode="floor") == 0.0
+    assert legacy_engine._round_frame_time(0.0167, fps, mode="ceil") == pytest.approx(1 / fps)
+    assert legacy_engine._round_frame_time(0.0167, fps, mode="round") == pytest.approx(1 / fps)
+    assert legacy_engine._round_frame_time(1 / fps, fps, mode="floor") == pytest.approx(1 / fps)
+    assert legacy_engine._round_frame_time(1 / fps, fps, mode="ceil") == pytest.approx(1 / fps)
 
 
 def test_hybrid_segments_media_only_is_single_ffmpeg_segment() -> None:
-    segments = render_run._hybrid_segments(_media_only_timeline())
+    segments = legacy_engine._hybrid_segments(_media_only_timeline())
     assert segments == [{"engine": "ffmpeg", "from": 0.0, "to": 2.0}]
 
 
 def test_hybrid_segments_effect_clip_marks_remotion_window() -> None:
-    segments = render_run._hybrid_segments(_effect_clip_timeline())
+    segments = legacy_engine._hybrid_segments(_effect_clip_timeline())
     assert segments == [{"engine": "remotion", "from": 0.0, "to": 2.0}]
 
 
 # ---------------------------------------------------------------------------
 # real transitions in _complex_clip_windows (default duration, precedence,
 # handle padding, rounding)
 # ---------------------------------------------------------------------------
 
 
 def _two_media_clips_timeline(transition: dict | None) -> dict:
     """Two back-to-back media clips on one visual track (fps 30).
 
     clip_a spans [0, 2]; clip_b starts at 2.0 and spans [2, 4]. The timeline
     duration (no metadata) is 4.0. clip_a optionally carries *transition*.
     """
     clips = [
         {
             "id": "clip_a",
             "at": 0,
             "track": "v",
             "clipType": "media",
             "asset": "main",
             "from": 0,
             "to": 2,
             "speed": 1,
             "volume": 0,
         },
         {
             "id": "clip_b",
             "at": 2,
             "track": "v",
             "clipType": "media",
             "asset": "main",
             "from": 0,
             "to": 2,
             "speed": 1,
             "volume": 0,
         },
     ]
     if transition is not None:
         clips[0]["transition"] = transition
     return {
         "theme": "banodoco-default",
         "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
         "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
         "clips": clips,
     }
 
 
 def test_transition_default_duration_is_8_frames() -> None:
     """A transition dict without duration keys defaults to 8 frames / fps.
 
     For clip_a ending at 2.0 with the next clip at 2.0: window is
     (2.0 - 8/30 - 0.25, 2.0 + 8/30 + 0.25) floor/ceil-rounded to frames.
     """
-    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"type": "crossfade"}), 30)
+    windows = legacy_engine._complex_clip_windows(_two_media_clips_timeline({"type": "crossfade"}), 30)
     assert windows == [
         (pytest.approx(44 / 30), pytest.approx(76 / 30)),
     ]
 
 
 def test_transition_default_duration_scales_with_fps() -> None:
-    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"type": "crossfade"}), 24)
+    windows = legacy_engine._complex_clip_windows(_two_media_clips_timeline({"type": "crossfade"}), 24)
     assert windows == [
         (pytest.approx(34 / 24), pytest.approx(62 / 24)),
     ]
 
 
 def test_transition_duration_seconds_overrides_default() -> None:
-    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"duration": 0.5}), 30)
+    windows = legacy_engine._complex_clip_windows(_two_media_clips_timeline({"duration": 0.5}), 30)
     assert windows == [
         (pytest.approx(37 / 30), pytest.approx(83 / 30)),
     ]
 
 
 def test_transition_duration_frames_divide_by_fps() -> None:
-    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"durationFrames": 12}), 30)
+    windows = legacy_engine._complex_clip_windows(_two_media_clips_timeline({"durationFrames": 12}), 30)
     assert windows == [
         (pytest.approx(40 / 30), pytest.approx(80 / 30)),
     ]
 
 
 def test_transition_duration_seconds_take_precedence_over_duration_frames() -> None:
-    windows = render_run._complex_clip_windows(
+    windows = legacy_engine._complex_clip_windows(
         _two_media_clips_timeline({"duration": 0.5, "durationFrames": 12}), 30
     )
     assert windows == [
         (pytest.approx(37 / 30), pytest.approx(83 / 30)),
     ]
 
 
 def test_transition_handle_padding_and_frame_rounding_without_transition() -> None:
     """An effect clip (no transition) is padded by handle_seconds=0.25 and the
     window is frame-rounded (floor start, ceil end)."""
     data = _two_media_clips_timeline(None)
     data["clips"][0]["effects"] = [{"id": "zoom"}]
-    windows = render_run._complex_clip_windows(data, 30)
+    windows = legacy_engine._complex_clip_windows(data, 30)
     # clip_a [0, 2] padded -> (max(0, 0-0.25), min(4, 2+0.25)) = (0, 2.25)
     # rounded -> frames 0 and ceil(2.25*30)=68.
     assert windows == [(0.0, pytest.approx(68 / 30))]
 
 
 def test_transition_handle_padding_rounds_off_frame_boundaries() -> None:
     """A clip starting mid-frame pads to non-frame-aligned edges that are then
     rounded: at=0.5 hold=1.0 -> (0.5-0.25, 1.5+0.25) = (0.25, 1.75) -> frames 7/53."""
     data = {
         "theme": "banodoco-default",
         "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
         "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
         "clips": [
             {"id": "card", "at": 0.5, "track": "v", "clipType": "text-card", "hold": 1.0},
             {"id": "media", "at": 0, "track": "v", "clipType": "media", "asset": "main", "from": 0, "to": 4, "speed": 1, "volume": 0},
         ],
     }
-    windows = render_run._complex_clip_windows(data, 30)
+    windows = legacy_engine._complex_clip_windows(data, 30)
     assert windows == [(pytest.approx(7 / 30), pytest.approx(53 / 30))]
 
 
 def test_transition_takes_precedence_over_effect_window() -> None:
     """A media clip with BOTH effects and a transition uses the transition
     window (centered on the boundary), not the effect's padded clip window."""
     data = _two_media_clips_timeline({"duration": 0.5})
     data["clips"][0]["effects"] = [{"id": "zoom"}]
-    windows = render_run._complex_clip_windows(data, 30)
+    windows = legacy_engine._complex_clip_windows(data, 30)
     assert windows == [
         (pytest.approx(37 / 30), pytest.approx(83 / 30)),
     ]
 
 
 def test_transition_ignored_for_non_media_clip() -> None:
     """'transition' is only honored on media clips: a text-card carrying a
     transition dict still gets the plain padded clip window."""
     data = {
         "theme": "banodoco-default",
         "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
         "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
         "clips": [
             {"id": "card", "at": 0.5, "track": "v", "clipType": "text-card", "hold": 1.0, "transition": {"duration": 0.5}},
             {"id": "media", "at": 0, "track": "v", "clipType": "media", "asset": "main", "from": 0, "to": 4, "speed": 1, "volume": 0},
         ],
     }
-    windows = render_run._complex_clip_windows(data, 30)
+    windows = legacy_engine._complex_clip_windows(data, 30)
     assert windows == [(pytest.approx(7 / 30), pytest.approx(53 / 30))]
 
 
 def test_transition_longer_than_clip_clamps_to_timeline_bounds() -> None:
     """A transition longer than the clip's lead-in clamps the window start to
     0 and the end to the timeline duration (with rounding)."""
-    windows = render_run._complex_clip_windows(_two_media_clips_timeline({"duration": 3.0}), 30)
+    windows = legacy_engine._complex_clip_windows(_two_media_clips_timeline({"duration": 3.0}), 30)
     assert windows == [(0.0, pytest.approx(4.0))]
 
 
 # ---------------------------------------------------------------------------
 # standalone vs attached run ownership
 # ---------------------------------------------------------------------------
 
 
 def test_run_module_never_prepares_project_run() -> None:
     """run.py is standalone: it must not create a project run.json."""
     source = Path(render_run.__file__).read_text(encoding="utf-8")
     assert "prepare_project_run" not in source
     assert "run.json" not in source
     assert not hasattr(render_run, "prepare_project_run")
 
 
 def test_main_parser_has_no_project_binding_flags(capsys: pytest.CaptureFixture[str]) -> None:
     with pytest.raises(SystemExit) as excinfo:
         render_run.main(["--help"])
     assert excinfo.value.code == 0
     help_text = capsys.readouterr().out
     # "--project-dir" is the Remotion project directory, NOT a managed-binding
     # flag; "--project " (trailing space) would be the binding flag.
     assert "--project " not in help_text
     assert "--timeline-slug" not in help_text
     assert "--project-dir" in help_text
     assert "--engine" in help_text  # the only backend selection surface
diff --git a/tests/packs/rendering/test_render_remotion_registry.py b/tests/packs/rendering/test_render_remotion_registry.py
index 00fe36f2..360b6e23 100644
--- a/tests/packs/rendering/test_render_remotion_registry.py
+++ b/tests/packs/rendering/test_render_remotion_registry.py
@@ -1,52 +1,53 @@
 from __future__ import annotations
 
 import json
 import shutil
 import subprocess
 import tempfile
 import unittest
 from pathlib import Path
 from unittest import mock
 
 from astrid.core import timeline
 from astrid.packs.rendering.backends.remotion import run as render_remotion
+from astrid.packs.rendering.executors.render import legacy_engine
 from astrid.packs.rendering.executors.render import run as render_facade
 
 ROOT = Path(__file__).resolve().parents[3]
 LOCAL_EFFECT_SMOKE_FIXTURE = ROOT / "tests" / "fixtures" / "local_effect_smoke"
 
 
 def _write_fake_remotion_output(command: list[str]) -> Path:
     output = Path(command[command.index("--output") + 1])
     output.parent.mkdir(parents=True, exist_ok=True)
     output.write_bytes(b"fake-remotion-video")
     return output
 
 
 class RenderRemotionRegistryGenerationTest(unittest.TestCase):
     def _write_empty_render_inputs(self, tmp: Path) -> tuple[Path, Path, Path]:
         timeline_path = tmp / "hype.timeline.json"
         assets_path = tmp / "hype.assets.json"
         out_path = tmp / "hype.mp4"
         timeline.save_timeline(
             {
                 "theme": "banodoco-default",
                 "tracks": [{"id": "v1", "kind": "visual", "label": "Generated"}],
                 "clips": [],
             },
             timeline_path,
         )
         timeline.save_registry({"assets": {}}, assets_path)
         return timeline_path, assets_path, out_path
 
     def _write_fake_remotion_project(self, tmp: Path) -> tuple[Path, Path]:
         project_dir = tmp / "remotion"
         banodoco_root = project_dir / "node_modules" / "@banodoco"
         composition_src = banodoco_root / "timeline-composition" / "typescript" / "src"
         composition_src.mkdir(parents=True)
         # _validate_project_dir requires all three @banodoco adapter packages
         # (see docs/reference/render-adapter.md).  Create stub directories for the other two.
         (banodoco_root / "timeline-schema").mkdir(parents=True)
         (banodoco_root / "timeline-theme-2rp").mkdir(parents=True)
         (project_dir / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
         return project_dir, composition_src
@@ -126,109 +127,109 @@ class RenderRemotionRegistryGenerationTest(unittest.TestCase):
                     out_path,
                     project_dir=project_dir,
                     composition_id="TimelineComposition",
                     theme_path=None,
                 )
             provenance = json.loads(
                 render_remotion._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
             )
 
         self.assertEqual(result, out_path.resolve())
         self.assertEqual(registry_project_roots, [project_root.resolve()])
         self.assertIn("fixture-smoke-effect", discovered_effect_ids)
         self.assertNotIn("model-trends", discovered_effect_ids)
         self.assertEqual(len(props_payloads), 1)
         clip = props_payloads[0]["timeline"]["clips"][0]
         self.assertEqual(clip["clipType"], "fixture-smoke-effect")
         self.assertEqual(clip["params"]["label"], "Fixture smoke")
         self.assertTrue(clip["params"]["__astridAssets"]["badge"].startswith("astrid-effects/"))
         self.assertEqual(len(staged_asset_paths_seen), 2)
         for staged_asset_path in staged_asset_paths_seen:
             self.assertFalse(staged_asset_path.exists(), "render should clean fixture-staged assets")
         self.assertFalse((project_root / "astrid" / "packs" / "local" / "elements" / "effects" / "model-trends").exists())
         self.assertEqual(provenance["resolved_effect_ids"], ["fixture-smoke-effect"])
         self.assertEqual(provenance["source_pack_ids"], ["local"])
         self.assertEqual(provenance["staged_asset_ids"], ["badge", "palette"])
         self.assertIn("local", [pack["id"] for pack in provenance["active_pack_order"]])
 
     def test_hybrid_render_writes_final_sidecar_with_remotion_segment_provenance(self) -> None:
         with tempfile.TemporaryDirectory(prefix="render-hybrid-provenance-") as tmp_text:
             tmp = Path(tmp_text)
             timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
             remotion_segment_payload = {
                 "schema_version": 1,
                 "engine": "remotion",
                 "output": "segment.mp4",
                 "resolved_effect_ids": ["sparkle"],
             }
 
             def fake_render(timeline_arg, assets_arg, out_arg, **kwargs):
                 Path(out_arg).write_text("segment", encoding="utf-8")
-                render_facade._render_provenance_sidecar_path(Path(out_arg)).write_text(
+                legacy_engine._render_provenance_sidecar_path(Path(out_arg)).write_text(
                     json.dumps(remotion_segment_payload) + "\n",
                     encoding="utf-8",
                 )
                 return Path(out_arg)
 
             def fake_concat(segment_paths, final_out):
                 final_out.write_text("hybrid", encoding="utf-8")
 
             with (
                 mock.patch.object(
-                    render_facade,
+                    legacy_engine,
                     "_hybrid_segments",
                     return_value=[{"engine": "remotion", "from": 0.0, "to": 1.0}],
                 ),
                 mock.patch.object(render_facade, "render", side_effect=fake_render),
-                mock.patch.object(render_facade, "_concat_segments", side_effect=fake_concat),
-                mock.patch.object(render_facade, "_effective_registry_state", return_value={"hash": "registry-hash"}),
+                mock.patch.object(legacy_engine, "_concat_segments", side_effect=fake_concat),
+                mock.patch.object(legacy_engine, "_effective_registry_state", return_value={"hash": "registry-hash"}),
             ):
-                result = render_facade._render_hybrid(
+                result = legacy_engine._render_hybrid(
                     timeline_path,
                     assets_path,
                     out_path,
                     project_dir=tmp / "remotion",
                     composition_id="TimelineComposition",
                     theme_path=None,
                 )
             provenance = json.loads(
-                render_facade._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
+                legacy_engine._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
             )
 
         self.assertEqual(result, out_path.resolve())
         self.assertEqual(provenance["engine"], "hybrid")
         self.assertEqual(provenance["registry_hash"], "registry-hash")
         self.assertEqual(provenance["segments"], [{"engine": "remotion", "from": 0.0, "to": 1.0}])
         self.assertEqual(provenance["segment_provenance"], [remotion_segment_payload])
 
     def test_main_synthesizes_empty_asset_registry_when_assets_are_absent(self) -> None:
         with tempfile.TemporaryDirectory(prefix="render-main-assets-") as tmp_text:
             tmp = Path(tmp_text)
             timeline_path, _assets_path, out_path = self._write_empty_render_inputs(tmp)
             seen: dict[str, object] = {}
 
             def fake_render(timeline_arg, assets_arg, out_arg, **kwargs):
                 assets_arg = Path(assets_arg)
                 seen["timeline"] = timeline_arg
                 seen["assets"] = assets_arg
                 seen["assets_payload"] = json.loads(assets_arg.read_text(encoding="utf-8"))
                 seen["out"] = out_arg
                 seen["kwargs"] = kwargs
                 return out_arg
 
             with mock.patch.object(render_facade, "render", side_effect=fake_render):
                 result = render_facade.main(
                     [
                         "--timeline",
                         str(timeline_path),
                         "--out",
                         str(out_path),
                     ]
                 )
 
         self.assertEqual(result, 0)
         self.assertEqual(seen["timeline"], timeline_path)
         self.assertEqual(seen["assets_payload"], {"assets": {}})
         self.assertEqual(seen["out"], out_path)
         self.assertFalse(Path(seen["assets"]).exists())
 
 if __name__ == "__main__":

exec
/bin/zsh -lc "sed -n '1,460p' astrid/packs/rendering/executors/render/legacy_engine.py && git show a72729db:astrid/packs/rendering/executors/render/run.py | sed -n '1,460p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
#!/usr/bin/env python3

"""Legacy rendering engine (characterized behavior).

Everything in this module is the historical monolith's render pipeline,
preserved verbatim so characterization tests can lock the legacy behavior
that the :mod:`RenderService <astrid.core.rendering.service>` now reproduces
through registered backends, planners, and finalizers.  The facade
(``run.py``) is a neutral adapter and MUST NOT import or dispatch through
this module; production callers use the service.

The legacy engine retains the private backend aliases it historically
re-exported so characterization fixtures can drive the old paths exactly.
"""

from __future__ import annotations

from contextvars import ContextVar
from fractions import Fraction
from json import dumps as _json_dumps
from json import loads as _json_loads
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from astrid.core import timeline
from astrid.core.audit import AuditContext
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.packs.rendering.backends.ffmpeg import command as ffmpeg_command
from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_backend
from astrid.packs.rendering.backends.remotion import run as remotion_backend
from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _complex_clip_windows,
    _hybrid_segments,
)

# Compatibility exports for callers that historically imported these private
# helpers from the facade.  Their implementation now lives with the backend.
_RangeHTTPRequestHandler = remotion_backend._RangeHTTPRequestHandler
_validate_project_dir = remotion_backend._validate_project_dir
_serialize_timeline = remotion_backend._serialize_timeline
_resolve_theme_path = remotion_backend._resolve_theme_path
_theme_for_props = remotion_backend._theme_for_props
_theme_slug_for_render_default = remotion_backend._theme_slug_for_render_default
_resolved_theme_for_render = remotion_backend._resolved_theme_for_render
_timeline_composition_src = remotion_backend._timeline_composition_src
_registry_output_paths = remotion_backend._registry_output_paths
_registry_outputs_exist = remotion_backend._registry_outputs_exist
_active_theme_pointer_current = remotion_backend._active_theme_pointer_current
_effective_registry_state = remotion_backend._effective_registry_state
_read_registry_state = remotion_backend._read_registry_state
_write_registry_state = remotion_backend._write_registry_state
_regenerate_element_registries = remotion_backend._regenerate_element_registries
_render_asset_stage_hash = remotion_backend._render_asset_stage_hash
_effect_registry_for_assets = remotion_backend._effect_registry_for_assets
_effect_id_for_clip = remotion_backend._effect_id_for_clip
_source_pack_id = remotion_backend._source_pack_id
_inject_clip_asset_params = remotion_backend._inject_clip_asset_params
_stage_effect_assets_for_timeline = remotion_backend._stage_effect_assets_for_timeline
_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
_render_provenance_payload = remotion_backend._render_provenance_payload
_write_render_provenance = remotion_backend._write_render_provenance
_timeline_canvas = ffmpeg_command.timeline_canvas
_clip_duration_seconds = ffmpeg_command.clip_duration_seconds

_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
    "render_publication_previous_outputs",
    default=(),
)
_HYBRID_FINALIZER_PROFILE: ContextVar[RenderProfile | None] = ContextVar(
    "hybrid_finalizer_profile",
    default=None,
)


def _swap_from_dump(clip: dict) -> dict:
    out = dict(clip)
    if "from_" in out:
        out["from"] = out.pop("from_")
    return out


def _clip_timeline_end_seconds(clip: dict) -> float:
    start = float(clip.get("at", 0) or 0)
    if clip.get("clipType") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)):
        return start + max(0.0, float(hold))
    if isinstance(clip.get("to"), (int, float)):
        return float(clip["to"])
    return start


def _timeline_duration_seconds(timeline_data: dict) -> float:
    metadata = timeline_data.get("metadata", {})
    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
        explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    return max((_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0)


def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
    instant = (
        seconds
        if isinstance(seconds, Fraction)
        else Fraction(seconds).limit_denominator(1_000_000)
    )
    frames = instant * rate
    if mode == "floor":
        frame = frames.numerator // frames.denominator
    elif mode == "ceil":
        frame = -(-frames.numerator // frames.denominator)
    else:
        frame = round(frames)
    return float(Fraction(frame, 1) / rate)


def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
    clip_start = float(clip.get("at", 0) or 0)
    clip_end = _clip_timeline_end_seconds(clip)
    return clip_start < end and clip_end > start


def _window_clip(clip: dict, start: float, end: float) -> dict | None:
    if not _clip_overlaps(clip, start, end):
        return None
    clip_start = float(clip.get("at", 0) or 0)
    visible_start = max(clip_start, start)
    visible_end = min(_clip_timeline_end_seconds(clip), end)
    if visible_end <= visible_start:
        return None

    out = dict(clip)
    out["at"] = visible_start - start
    out["id"] = f"{clip.get('id', 'clip')}_{start:.3f}_{end:.3f}".replace(".", "_")
    if clip.get("clipType") == "media":
        speed = float(clip.get("speed", 1) or 1)
        source_from = float(clip.get("from", 0) or 0) + ((visible_start - clip_start) * speed)
        out["from"] = source_from
        out["to"] = source_from + ((visible_end - visible_start) * speed)
    elif isinstance(clip.get("hold"), (int, float)):
        out["hold"] = visible_end - visible_start
    return out


def _window_timeline_data(timeline_data: dict, start: float, end: float, *, media_only: bool) -> dict:
    clips: list[dict] = []
    for clip in timeline_data.get("clips", []):
        if media_only and clip.get("clipType") != "media":
            continue
        windowed = _window_clip(clip, start, end)
        if windowed is not None:
            clips.append(windowed)
    used_tracks = {clip.get("track") for clip in clips}
    tracks = [track for track in timeline_data.get("tracks", []) if track.get("id") in used_tracks]
    out = dict(timeline_data)
    out["tracks"] = tracks
    out["clips"] = clips
    out["metadata"] = {
        **dict(timeline_data.get("metadata", {})),
        "source_window_start_seconds": start,
        "source_window_end_seconds": end,
        "duration_seconds": end - start,
    }
    return out


_validate_ffmpeg_media_timeline = (
    ffmpeg_command.validate_ffmpeg_media_timeline
)


def _render_ffmpeg_media_to_path(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
) -> Path:
    return ffmpeg_backend._render_ffmpeg_media_to_path(
        timeline_path,
        assets_path,
        out_path,
    )


def _render_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    _previous_outputs: Sequence[Path] | None = None,
) -> Path:
    return ffmpeg_backend.render(
        timeline_path,
        assets_path,
        out_path,
        previous_outputs=(
            _PUBLICATION_PREVIOUS_OUTPUTS.get()
            if _previous_outputs is None
            else _previous_outputs
        ),
        _render_to_path=_render_ffmpeg_media_to_path,
    )


def _can_render_with_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
) -> bool:
    return ffmpeg_backend.can_render_with_ffmpeg_media(
        timeline_path,
        assets_path,
    )


def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
    profile = _HYBRID_FINALIZER_PROFILE.get()
    audio = None
    if profile is not None:
        audio = (
            AudioOwnership.RENDERED
            if profile.has_audio
            else AudioOwnership.NONE
        )
    ffmpeg_finalizer.concat_segment_files(
        segment_paths,
        out_path,
        profile=profile,
        audio=audio,
    )


def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = _json_loads(timeline_path.read_text(encoding="utf-8"))
    canonical_profile = resolve_render_profile(
        timeline_data,
        timeline.load_registry(assets_path),
        theme=remotion_kwargs.get("theme_path"),
        themes_root=REPO_ROOT / "themes",
    )
    segments = _hybrid_segments(
        timeline_data,
        fps=Fraction(*canonical_profile.fps_rational),
    )
    if (
        canonical_profile.fps_rational[1] == 1
        and len(segments) == 1
        and segments[0]["engine"] == "ffmpeg"
    ):
        return _render_ffmpeg_media(timeline_path, assets_path, out_path)

    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
        tmp_dir = Path(tmp)
        segment_paths: list[Path] = []
        segment_provenance: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            engine = str(segment["engine"])
            start = float(segment["from"])
            end = float(segment["to"])
            segment_dir = tmp_dir / f"{index:04d}-{engine}"
            segment_dir.mkdir(parents=True, exist_ok=True)
            segment_timeline_path = segment_dir / "timeline.json"
            segment_out_path = segment_dir / "segment.mp4"
            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
            if canonical_profile.fps_rational[1] != 1:
                # Both extracted legacy renderers accept an integer canvas
                # rate.  Render the window at the nearest rate, then let the
                # finalizer normalize to the exact canonical rational rate.
                render_rate = max(
                    1,
                    round(Fraction(*canonical_profile.fps_rational)),
                )
                overrides = dict(segment_timeline.get("theme_overrides", {}))
                visual = dict(overrides.get("visual", {}))
                canvas = dict(visual.get("canvas", {}))
                canvas["fps"] = render_rate
                visual["canvas"] = canvas
                overrides["visual"] = visual
                segment_timeline["theme_overrides"] = overrides
            segment_timeline_path.write_text(_json_dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
            if engine == "ffmpeg":
                _render_ffmpeg_media(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    _previous_outputs=(),
                )
            else:
                from .run import render  # facade delegates to the service

                render(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    engine="remotion",
                    **remotion_kwargs,
                )
            sidecar_path = _render_provenance_sidecar_path(segment_out_path)
            if sidecar_path.exists():
                segment_provenance.append(_json_loads(sidecar_path.read_text(encoding="utf-8")))
            segment_paths.append(segment_out_path)
        staged_video = tmp_dir / "final" / out_path.name
        staged_video.parent.mkdir(parents=True, exist_ok=True)
        profile_token = _HYBRID_FINALIZER_PROFILE.set(canonical_profile)
        try:
            _concat_segments(segment_paths, staged_video)
        finally:
            _HYBRID_FINALIZER_PROFILE.reset(profile_token)
        provenance = _render_provenance_payload(
            out_path,
            engine="hybrid",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=Path(remotion_kwargs.get("project_dir") or (REPO_ROOT / "remotion")),
            composition_id=str(remotion_kwargs.get("composition_id") or "TimelineComposition"),
            theme_path=remotion_kwargs.get("theme_path"),
            active_theme=None,
            registry_state=_effective_registry_state(remotion_kwargs.get("theme_path")),
            stage_summary={"root": None, "effects": []},
            segments=segments,
            segment_provenance=segment_provenance,
        )
        output = publish_render_result(
            staged_video,
            provenance,
            out_path=out_path,
            sidecar_path=_render_provenance_sidecar_path(out_path),
            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        )

    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid")
        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_hybrid")
        render_id = audit.register_asset(
            kind="render",
            path=out_path,
            label="Rendered video",
            parents=[timeline_id, assets_id],
            stage="render_hybrid",
            metadata={"engine": "hybrid", "segments": segments},
        )
        audit.register_node(
            stage="render_hybrid",
            label="Render hybrid timeline",
            parents=[timeline_id, assets_id],
            outputs=[render_id],
            metadata={"engine": "hybrid", "segments": segments},
        )
    return output


def _audio_reactive_ffmpeg_element(
    theme_path: Path | None,
) -> Any | None:
    return ffmpeg_backend._audio_reactive_ffmpeg_element(theme_path)


def _render_audio_reactive_colour_if_supported(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
) -> Path | None:
    return ffmpeg_backend.render_audio_reactive_colour_if_supported(
        timeline_path,
        assets_path,
        out_path,
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        element_resolver=_audio_reactive_ffmpeg_element,
    )
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
#!/usr/bin/env python3

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('rendering.render')


import argparse
import ast
import json
import os
import sys
from contextvars import ContextVar
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from astrid.core import timeline
from astrid.core.audit import AuditContext
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.core.rendering.service import RenderService
from astrid.packs.rendering.backends.ffmpeg import command as ffmpeg_command
from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_backend
from astrid.packs.rendering.backends.remotion import run as remotion_backend
from astrid.packs.rendering.executors.render import audio_reactive_colour
from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _complex_clip_windows,
    _hybrid_segments,
)


# Compatibility exports for callers that historically imported these private
# helpers from the facade.  Their implementation now lives with the backend.
_RangeHTTPRequestHandler = remotion_backend._RangeHTTPRequestHandler
_validate_project_dir = remotion_backend._validate_project_dir
_serialize_timeline = remotion_backend._serialize_timeline
_resolve_theme_path = remotion_backend._resolve_theme_path
_theme_for_props = remotion_backend._theme_for_props
_theme_slug_for_render_default = remotion_backend._theme_slug_for_render_default
_resolved_theme_for_render = remotion_backend._resolved_theme_for_render
_timeline_composition_src = remotion_backend._timeline_composition_src
_registry_output_paths = remotion_backend._registry_output_paths
_registry_outputs_exist = remotion_backend._registry_outputs_exist
_active_theme_pointer_current = remotion_backend._active_theme_pointer_current
_effective_registry_state = remotion_backend._effective_registry_state
_read_registry_state = remotion_backend._read_registry_state
_write_registry_state = remotion_backend._write_registry_state
_regenerate_element_registries = remotion_backend._regenerate_element_registries
_render_asset_stage_hash = remotion_backend._render_asset_stage_hash
_effect_registry_for_assets = remotion_backend._effect_registry_for_assets
_effect_id_for_clip = remotion_backend._effect_id_for_clip
_source_pack_id = remotion_backend._source_pack_id
_inject_clip_asset_params = remotion_backend._inject_clip_asset_params
_stage_effect_assets_for_timeline = remotion_backend._stage_effect_assets_for_timeline
_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
_render_provenance_payload = remotion_backend._render_provenance_payload
_write_render_provenance = remotion_backend._write_render_provenance
_timeline_canvas = ffmpeg_command.timeline_canvas
_clip_duration_seconds = ffmpeg_command.clip_duration_seconds


# The Hype pipeline's default output file name.  The executor manifest exposes
# an ``output_name`` input defaulting to this sentinel; non-default names are
# validated (plain file name, ``.mp4`` extension) and flow through the same
# placeholder expansion and declared-output resolution as the default.
DEFAULT_OUTPUT_NAME = "hype.mp4"

_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
    "render_publication_previous_outputs",
    default=(),
)
_HYBRID_FINALIZER_PROFILE: ContextVar[RenderProfile | None] = ContextVar(
    "hybrid_finalizer_profile",
    default=None,
)

_SERVICE: RenderService | None = None


def _default_service() -> RenderService:
    """Build (once) the backend-neutral service the facade delegates to.

    Legacy engine translation, renderer/planner selection, invocation,
    validation, audio completion, finalization, and publication all happen
    inside :class:`RenderService`.  The facade is a thin adapter: it maps the
    legacy argument surface onto the service call and returns the published
    output path.
    """
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RenderService()
    return _SERVICE


def validate_output_name(name: str) -> str:
    """Validate an ``output_name``: a plain ``.mp4`` file name.

    Rejects empty names, path separators (``/`` and ``\\``), directory
    traversal (``.``, ``..``, or any ``..``-prefixed component), absolute
    paths, and anything that does not end in ``.mp4``.  The Hype default
    ``hype.mp4`` validates unchanged.
    """
    text = str(name)
    if text == "":
        raise ValueError("output_name must not be empty")
    if text in {".", ".."} or text.startswith(".."):
        raise ValueError(
            f"output_name must not traverse directories, got {name!r}"
        )
    if "/" in text or "\\" in text or text.startswith(os.sep):
        raise ValueError(
            f"output_name must be a plain file name without path separators, got {name!r}"
        )
    if Path(text).name != text:
        raise ValueError(
            f"output_name must be a plain file name, got {name!r}"
        )
    if not text.endswith(".mp4"):
        raise ValueError(
            f"output_name must end with .mp4, got {name!r}"
        )
    return text


def _legacy_backend_config(
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> dict[str, dict[str, Any]]:
    """Map the legacy render kwargs onto namespaced backend configuration.

    The facade remains backend-neutral: it only knows the qualified ids that
    correspond to the historical selector spellings and scopes each legacy
    value under the backend that understands it.  The service forwards each
    candidate only its own namespace.
    """
    config: dict[str, dict[str, Any]] = {}
    remotion: dict[str, Any] = {}
    if project_dir is not None:
        remotion["project_dir"] = str(project_dir)
    if composition_id is not None:
        remotion["composition_id"] = composition_id
    if theme_path is not None:
        remotion["theme_path"] = str(theme_path)
    if min_free_gb is not None:
        remotion["min_free_gb"] = min_free_gb
    if remotion:
        config["rendering.remotion"] = remotion
    hybrid: dict[str, Any] = {}
    if theme_path is not None:
        hybrid["theme_path"] = str(theme_path)
    if hybrid:
        config["rendering.legacy_hybrid"] = hybrid
    return config


def _parse_backend_config(value: str | None) -> dict[str, dict[str, Any]]:
    """Parse the ``--backend-config`` CLI payload (JSON or Python literal)."""
    if value is None or value == "":
        return {}
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(
                f"--backend-config must be a JSON object keyed by qualified "
                f"backend id, got {value!r}"
            ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"--backend-config must be a JSON object keyed by qualified backend id"
        )
    return {str(key): dict(item) for key, item in parsed.items() if item is not None}


def _swap_from_dump(clip: dict) -> dict:
    out = dict(clip)
    if "from_" in out:
        out["from"] = out.pop("from_")
    return out


def _write_empty_asset_registry(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timeline.save_registry({"assets": {}}, path)


def _clip_timeline_end_seconds(clip: dict) -> float:
    start = float(clip.get("at", 0) or 0)
    if clip.get("clipType") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)):
        return start + max(0.0, float(hold))
    if isinstance(clip.get("to"), (int, float)):
        return float(clip["to"])
    return start


def _timeline_duration_seconds(timeline_data: dict) -> float:
    metadata = timeline_data.get("metadata", {})
    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
        explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    return max((_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0)


def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
    instant = (
        seconds
        if isinstance(seconds, Fraction)
        else Fraction(seconds).limit_denominator(1_000_000)
    )
    frames = instant * rate
    if mode == "floor":
        frame = frames.numerator // frames.denominator
    elif mode == "ceil":
        frame = -(-frames.numerator // frames.denominator)
    else:
        frame = round(frames)
    return float(Fraction(frame, 1) / rate)


def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
    clip_start = float(clip.get("at", 0) or 0)
    clip_end = _clip_timeline_end_seconds(clip)
    return clip_start < end and clip_end > start


def _window_clip(clip: dict, start: float, end: float) -> dict | None:
    if not _clip_overlaps(clip, start, end):
        return None
    clip_start = float(clip.get("at", 0) or 0)
    visible_start = max(clip_start, start)
    visible_end = min(_clip_timeline_end_seconds(clip), end)
    if visible_end <= visible_start:
        return None

    out = dict(clip)
    out["at"] = visible_start - start
    out["id"] = f"{clip.get('id', 'clip')}_{start:.3f}_{end:.3f}".replace(".", "_")
    if clip.get("clipType") == "media":
        speed = float(clip.get("speed", 1) or 1)
        source_from = float(clip.get("from", 0) or 0) + ((visible_start - clip_start) * speed)
        out["from"] = source_from
        out["to"] = source_from + ((visible_end - visible_start) * speed)
    elif isinstance(clip.get("hold"), (int, float)):
        out["hold"] = visible_end - visible_start
    return out


def _window_timeline_data(timeline_data: dict, start: float, end: float, *, media_only: bool) -> dict:
    clips: list[dict] = []
    for clip in timeline_data.get("clips", []):
        if media_only and clip.get("clipType") != "media":
            continue
        windowed = _window_clip(clip, start, end)
        if windowed is not None:
            clips.append(windowed)
    used_tracks = {clip.get("track") for clip in clips}
    tracks = [track for track in timeline_data.get("tracks", []) if track.get("id") in used_tracks]
    out = dict(timeline_data)
    out["tracks"] = tracks
    out["clips"] = clips
    out["metadata"] = {
        **dict(timeline_data.get("metadata", {})),
        "source_window_start_seconds": start,
        "source_window_end_seconds": end,
        "duration_seconds": end - start,
    }
    return out


_validate_ffmpeg_media_timeline = (
    ffmpeg_command.validate_ffmpeg_media_timeline
)


def _render_ffmpeg_media_to_path(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
) -> Path:
    return ffmpeg_backend._render_ffmpeg_media_to_path(
        timeline_path,
        assets_path,
        out_path,
    )


def _render_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    _previous_outputs: Sequence[Path] | None = None,
) -> Path:
    return ffmpeg_backend.render(
        timeline_path,
        assets_path,
        out_path,
        previous_outputs=(
            _PUBLICATION_PREVIOUS_OUTPUTS.get()
            if _previous_outputs is None
            else _previous_outputs
        ),
        _render_to_path=_render_ffmpeg_media_to_path,
    )


def _can_render_with_ffmpeg_media(
    timeline_path: Path,
    assets_path: Path,
) -> bool:
    return ffmpeg_backend.can_render_with_ffmpeg_media(
        timeline_path,
        assets_path,
    )


def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
    profile = _HYBRID_FINALIZER_PROFILE.get()
    audio = None
    if profile is not None:
        audio = (
            AudioOwnership.RENDERED
            if profile.has_audio
            else AudioOwnership.NONE
        )
    ffmpeg_finalizer.concat_segment_files(
        segment_paths,
        out_path,
        profile=profile,
        audio=audio,
    )


def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    canonical_profile = resolve_render_profile(
        timeline_data,
        timeline.load_registry(assets_path),
        theme=remotion_kwargs.get("theme_path"),
        themes_root=REPO_ROOT / "themes",
    )
    segments = _hybrid_segments(
        timeline_data,
        fps=Fraction(*canonical_profile.fps_rational),
    )
    if (
        canonical_profile.fps_rational[1] == 1
        and len(segments) == 1
        and segments[0]["engine"] == "ffmpeg"
    ):
        return _render_ffmpeg_media(timeline_path, assets_path, out_path)

    publication_out = out_path  # unresolved: publication symlink-guards it
    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
        tmp_dir = Path(tmp)
        segment_paths: list[Path] = []
        segment_provenance: list[dict[str, Any]] = []
        for index, segment in enumerate(segments):
            engine = str(segment["engine"])
            start = float(segment["from"])
            end = float(segment["to"])
            segment_dir = tmp_dir / f"{index:04d}-{engine}"
            segment_dir.mkdir(parents=True, exist_ok=True)
            segment_timeline_path = segment_dir / "timeline.json"
            segment_out_path = segment_dir / "segment.mp4"
            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
            if canonical_profile.fps_rational[1] != 1:
                # Both extracted legacy renderers accept an integer canvas
                # rate.  Render the window at the nearest rate, then let the
                # finalizer normalize to the exact canonical rational rate.
                render_rate = max(
                    1,
                    round(Fraction(*canonical_profile.fps_rational)),
                )
                overrides = dict(segment_timeline.get("theme_overrides", {}))
                visual = dict(overrides.get("visual", {}))
                canvas = dict(visual.get("canvas", {}))
                canvas["fps"] = render_rate
                visual["canvas"] = canvas
                overrides["visual"] = visual
                segment_timeline["theme_overrides"] = overrides
            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
            if engine == "ffmpeg":
                _render_ffmpeg_media(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    _previous_outputs=(),
                )
            else:
                render(
                    segment_timeline_path,
                    assets_path,
                    segment_out_path,
                    engine="remotion",
                    **remotion_kwargs,
                )
                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
                if sidecar_path.exists():
                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
            segment_paths.append(segment_out_path)
        staged_video = tmp_dir / "final" / out_path.name
        staged_video.parent.mkdir(parents=True, exist_ok=True)
        profile_token = _HYBRID_FINALIZER_PROFILE.set(canonical_profile)
        try:
            _concat_segments(segment_paths, staged_video)
        finally:
            _HYBRID_FINALIZER_PROFILE.reset(profile_token)
        provenance = _render_provenance_payload(
            out_path,
            engine="hybrid",
            timeline_path=timeline_path,
            assets_path=assets_path,
            project_dir=Path(remotion_kwargs.get("project_dir") or (REPO_ROOT / "remotion")),
            composition_id=str(remotion_kwargs.get("composition_id") or "TimelineComposition"),
            theme_path=remotion_kwargs.get("theme_path"),
            active_theme=None,
            registry_state=_effective_registry_state(remotion_kwargs.get("theme_path")),
            stage_summary={"root": None, "effects": []},
            segments=segments,
            segment_provenance=segment_provenance,
        )
        output = publish_render_result(
            staged_video,
            provenance,
            out_path=out_path,
            sidecar_path=_render_provenance_sidecar_path(out_path),
            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        )

    audit = AuditContext.from_env()
    if audit is not None:
        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid")

exec
/bin/zsh -lc "rg -n \"def _renderer_resolution|def _finalizer_resolution|alias_chain|override\" astrid/packs/rendering/planners/legacy_hybrid/run.py | head -40 && nl -ba astrid/packs/rendering/planners/legacy_hybrid/run.py | sed -n '500,625p' && rg -n \"def _renderer_resolution|def _finalizer_resolution|_direct_plan\" astrid/core/rendering/service.py && nl -ba astrid/core/rendering/service.py | sed -n '800,955p;1296,1415p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
537:def _renderer_resolution(
548:            alias_chain=[],
549:            override=None,
559:        alias_chain=list(evidence.get("alias_chain") or []),
560:        override=evidence.get("override"),
566:def _finalizer_resolution(registry: FinalizerRegistry | None) -> FinalizerResolution:
572:            alias_chain=[],
573:            override=None,
583:        alias_chain=list(evidence.get("alias_chain") or []),
584:        override=evidence.get("override"),
597:        alias_chain=[],
598:        override=None,
759:            # the registry; a configured alias or override therefore names a
   500	        clip["id"] = f"{raw_clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
   501	        clip["at"] = float(visible_start - start)
   502	        if raw_clip.get("clipType", "media") == "media":
   503	            speed = _number(raw_clip.get("speed", 1), "clip.speed")
   504	            source_from = _number(raw_clip.get("from", 0), "clip.from")
   505	            source_from += (visible_start - clip_start) * speed
   506	            clip["from"] = float(source_from)
   507	            clip["to"] = float(source_from + (visible_end - visible_start) * speed)
   508	        elif isinstance(raw_clip.get("hold"), (int, float)):
   509	            clip["hold"] = float(visible_end - visible_start)
   510	        clips.append(clip)
   511	    used_tracks = {clip.get("track") for clip in clips}
   512	    result = dict(timeline)
   513	    result["clips"] = clips
   514	    result["tracks"] = [
   515	        dict(track)
   516	        for track in timeline.get("tracks", [])
   517	        if isinstance(track, Mapping) and track.get("id") in used_tracks
   518	    ]
   519	    metadata = timeline.get("metadata")
   520	    result["metadata"] = {
   521	        **(dict(metadata) if isinstance(metadata, Mapping) else {}),
   522	        "source_window_start_seconds": float(start),
   523	        "source_window_end_seconds": float(end),
   524	        "duration_seconds": float(end - start),
   525	    }
   526	    return result
   527	
   528	
   529	def _source_pack(candidate: RenderingCandidate[Any]) -> dict[str, Any]:
   530	    return {
   531	        "id": candidate.pack_id,
   532	        "source_kind": candidate.source_kind,
   533	        "pack_root": str(candidate.pack_root),
   534	    }
   535	
   536	
   537	def _renderer_resolution(
   538	    renderer_id: str,
   539	    report: SupportReport,
   540	    *,
   541	    registry: RendererRegistry | None,
   542	) -> RendererResolution:
   543	    if registry is None:
   544	        return RendererResolution(
   545	            id=renderer_id,
   546	            source_pack={"id": renderer_id.split(".", 1)[0]},
   547	            manifest_digest=_ZERO_DIGEST,
   548	            alias_chain=[],
   549	            override=None,
   550	            support_decision=report,
   551	            trust_eligibility={"eligible": True, "method": "injected-support"},
   552	        )
   553	    candidate = registry.get(renderer_id)
   554	    evidence = registry.resolve_evidence(renderer_id)
   555	    return RendererResolution(
   556	        id=candidate.id,
   557	        source_pack=_source_pack(candidate),
   558	        manifest_digest=candidate.manifest_digest,
   559	        alias_chain=list(evidence.get("alias_chain") or []),
   560	        override=evidence.get("override"),
   561	        support_decision=report,
   562	        trust_eligibility=candidate.eligibility.to_dict(),
   563	    )
   564	
   565	
   566	def _finalizer_resolution(registry: FinalizerRegistry | None) -> FinalizerResolution:
   567	    if registry is None:
   568	        return FinalizerResolution(
   569	            id=FINALIZER_ID,
   570	            source_pack={"id": "rendering"},
   571	            manifest_digest=_ZERO_DIGEST,
   572	            alias_chain=[],
   573	            override=None,
   574	            trust_eligibility={"eligible": True},
   575	            support_decision=None,
   576	        )
   577	    candidate = registry.get(FINALIZER_ID)
   578	    evidence = registry.resolve_evidence(FINALIZER_ID)
   579	    return FinalizerResolution(
   580	        id=candidate.id,
   581	        source_pack=_source_pack(candidate),
   582	        manifest_digest=candidate.manifest_digest,
   583	        alias_chain=list(evidence.get("alias_chain") or []),
   584	        override=evidence.get("override"),
   585	        trust_eligibility=candidate.eligibility.to_dict(),
   586	        support_decision=None,
   587	    )
   588	
   589	
   590	def _planner_resolution(report: SupportReport) -> PlannerResolution:
   591	    manifest = Path(__file__).with_name("planner.yaml")
   592	    return PlannerResolution(
   593	        id=BACKEND_ID,
   594	        source_pack={"id": "rendering", "source_kind": "source"},
   595	        manifest_digest=sha256_file(manifest) if manifest.is_file() else _ZERO_DIGEST,
   596	        trust_eligibility={"eligible": True, "method": "source-tree"},
   597	        alias_chain=[],
   598	        override=None,
   599	        support_decision=report,
   600	    )
   601	
   602	
   603	class _CommandSupportResolver:
   604	    def __init__(
   605	        self,
   606	        registry: RendererRegistry,
   607	        *,
   608	        workspace: Path,
   609	    ) -> None:
   610	        self.registry = registry
   611	        self.workspace = workspace
   612	        self.counter = 0
   613	
   614	    def __call__(
   615	        self,
   616	        renderer_id: str,
   617	        request: RenderRequest,
   618	        timeline: Mapping[str, Any],
   619	    ) -> SupportReport:
   620	        candidate = self.registry.get(renderer_id)
   621	        evidence = self.registry.resolve_evidence(renderer_id)
   622	        del evidence
   623	        projected = request.for_backend(candidate.id)
   624	        if candidate.manifest.capabilities.get("supports_windows") is False:
   625	            if projected.window is None:
456:            plan = self._direct_plan(
477:                plan = self._direct_plan(
1574:    def _direct_plan(
1678:    def _renderer_resolution(
1708:    def _finalizer_resolution(
   800	                elif request.audio.value not in ownership:
   801	                    reasons.append(
   802	                        f"audio ownership {request.audio.value!r} is not statically supported"
   803	                    )
   804	            if capabilities.get("preserves_attachments") is not True:
   805	                reasons.append("finalizer does not declare attachment preservation")
   806	        alternatives = self._alternatives(registry, exclude=candidate.id) if reasons else []
   807	        return SupportReport(
   808	            schema_version=SCHEMA_VERSION,
   809	            supported=not reasons,
   810	            reasons=reasons,
   811	            features={
   812	                str(key): value
   813	                for key, value in capabilities.get("features", {}).items()
   814	                if isinstance(value, (bool, str))
   815	            },
   816	            alternatives=alternatives,
   817	            backend=candidate.id,
   818	            backend_version=candidate.manifest.version,
   819	        )
   820	
   821	    @staticmethod
   822	    def _static_timeline_reasons(
   823	        capabilities: Mapping[str, Any], request: RenderRequest
   824	    ) -> list[str]:
   825	        """Compare coarse renderer declarations with the concrete timeline.
   826	
   827	        A renderer without a ``support`` verb has only its manifest as
   828	        evidence, so omitted declarations are unknown and therefore fail
   829	        closed when the request actually exercises them.
   830	        """
   831	
   832	        try:
   833	            payload = json.loads(Path(request.timeline_path).read_text(encoding="utf-8"))
   834	            if not isinstance(payload, Mapping):
   835	                raise TypeError("timeline must contain a JSON object")
   836	            raw_clips = payload.get("clips", [])
   837	            raw_tracks = payload.get("tracks", [])
   838	            if not isinstance(raw_clips, list) or not isinstance(raw_tracks, list):
   839	                raise TypeError("timeline clips and tracks must be arrays")
   840	            clip_types = {
   841	                str(item.get("clipType", "media"))
   842	                for item in raw_clips
   843	                if isinstance(item, Mapping)
   844	            }
   845	            track_types = {
   846	                str(item.get("kind"))
   847	                for item in raw_tracks
   848	                if isinstance(item, Mapping) and item.get("kind") is not None
   849	            }
   850	        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
   851	            return [f"timeline cannot be evaluated against static support: {exc}"]
   852	
   853	        reasons: list[str] = []
   854	        declared_clips = capabilities.get("clip_types")
   855	        if clip_types:
   856	            if not isinstance(declared_clips, list):
   857	                reasons.append("renderer does not declare static clip types")
   858	            else:
   859	                missing = sorted(clip_types - set(declared_clips))
   860	                if missing:
   861	                    reasons.append(
   862	                        "timeline uses statically unsupported clip types: "
   863	                        + ", ".join(missing)
   864	                    )
   865	        declared_tracks = capabilities.get("track_types")
   866	        if track_types:
   867	            if not isinstance(declared_tracks, list):
   868	                reasons.append("renderer does not declare static track types")
   869	            else:
   870	                missing = sorted(track_types - set(declared_tracks))
   871	                if missing:
   872	                    reasons.append(
   873	                        "timeline uses statically unsupported track types: "
   874	                        + ", ".join(missing)
   875	                    )
   876	        return reasons
   877	
   878	    def _unsupported_report(
   879	        self,
   880	        report: SupportReport,
   881	        *,
   882	        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
   883	    ) -> None:
   884	        alternatives = list(report.alternatives) or self._alternatives(
   885	            registry, exclude=report.backend
   886	        )
   887	        raise_unsupported_error(
   888	            backend=report.backend,
   889	            message=f"{report.backend} does not support this render request",
   890	            recovery_command=self._recovery_for(alternatives),
   891	            details={
   892	                "reasons": list(report.reasons),
   893	                "features": dict(report.features),
   894	                "alternatives": alternatives,
   895	            },
   896	        )
   897	
   898	    def _invoke_renderer(
   899	        self,
   900	        request: RenderRequest,
   901	        *,
   902	        selected: _ResolvedCapability,
   903	        workspace: Path,
   904	        output_name: str,
   905	        expected_profile: Any,
   906	    ) -> RenderResult:
   907	        backend_request = replace(request, output_name=output_name).for_backend(
   908	            selected.candidate.id
   909	        )
   910	        self._observe("invoke", backend=selected.candidate.id, verb="render")
   911	        response = self._run_command(
   912	            selected.candidate,
   913	            "render",
   914	            backend_request,
   915	            workspace=workspace,
   916	        )
   917	        if not isinstance(response, RenderResult):
   918	            raise_protocol_error(
   919	                backend=selected.candidate.id,
   920	                message="render operation did not return a RenderResult",
   921	                details={"received_type": type(response).__name__},
   922	            )
   923	        # A null request profile deliberately leaves the backend's output
   924	        # profile open (the DTO contract permits this).  Validation still
   925	        # recomputes hashes, probes the media, and checks the probe against the
   926	        # declared profile.  Planned renders are subsequently checked or
   927	        # normalized against their canonical plan profile in _finish_plan.
   928	        expected = expected_profile or response.video.profile
   929	        self._observe("validate", backend=selected.candidate.id)
   930	        return self._validator(
   931	            response,
   932	            expected_profile=expected,
   933	            workspace_root=workspace,
   934	        )
   935	
   936	    def _segment_request(
   937	        self,
   938	        request: RenderRequest,
   939	        *,
   940	        candidate: RenderingCandidate[Any],
   941	        segment: RenderSegment,
   942	        index: int,
   943	        workspace: Path,
   944	    ) -> tuple[RenderRequest, dict[str, str]]:
   945	        """Adapt a planned window for full-timeline-only renderers.
   946	
   947	        Window-aware third-party renderers receive the canonical ``window``
   948	        field unchanged.  A renderer that explicitly declares
   949	        ``supports_windows: false`` receives an invocation-private sliced
   950	        timeline and a null window, preserving the behavior of Astrid's
   951	        existing full-timeline backends without teaching the service any
   952	        concrete backend identities.
   953	        """
   954	
   955	        if candidate.manifest.capabilities.get("supports_windows") is not False:
  1296	    def _finish_plan(
  1297	        self,
  1298	        request: RenderRequest,
  1299	        *,
  1300	        plan: RenderPlan,
  1301	        segment_results: list[RenderResult],
  1302	        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
  1303	        workspace: Path,
  1304	    ) -> tuple[RenderResult, RenderPlan]:
  1305	        candidate, evidence = pinned_finalizer
  1306	        if candidate.id == _DIRECT_FINALIZER_ID:
  1307	            # No executable finalizer pinned: the segment must already match
  1308	            # the canonical plan profile exactly.
  1309	            if len(segment_results) != 1:
  1310	                raise_internal_error(
  1311	                    backend=_CORE_BACKEND_ID,
  1312	                    message="direct finalizer received multiple segments",
  1313	                    recovery_command="select a planner that pins an executable finalizer",
  1314	                    details={"segment_count": len(segment_results)},
  1315	                )
  1316	            result = self._validator(
  1317	                segment_results[0],
  1318	                expected_profile=plan.profile,
  1319	                workspace_root=workspace,
  1320	            )
  1321	            return result, plan
  1322	
  1323	        ownerships = {item.audio_ownership for item in segment_results}
  1324	        if ownerships == {AudioOwnership.PASSTHROUGH}:
  1325	            requested_audio = AudioOwnership.PASSTHROUGH
  1326	        elif plan.profile.has_audio:
  1327	            requested_audio = AudioOwnership.RENDERED
  1328	        else:
  1329	            requested_audio = AudioOwnership.NONE
  1330	        support_audio = (
  1331	            None
  1332	            if requested_audio is AudioOwnership.PASSTHROUGH
  1333	            and plan.profile.has_audio
  1334	            else requested_audio
  1335	        )
  1336	        support_request = RenderRequest(
  1337	            schema_version=SCHEMA_VERSION,
  1338	            timeline_path=request.timeline_path,
  1339	            assets_registry_path=request.assets_registry_path,
  1340	            output_name=request.output_name,
  1341	            audio=support_audio,
  1342	            profile=plan.profile,
  1343	            backend_config=request.backend_config,
  1344	            metadata=request.metadata,
  1345	        )
  1346	        report = self._support(
  1347	            candidate,
  1348	            request=support_request,
  1349	            workspace=workspace,
  1350	            registry=self.finalizers,
  1351	        )
  1352	        if not report.supported:
  1353	            self._unsupported_report(report, registry=self.finalizers)
  1354	        finalizer_resolution = self._finalizer_resolution(
  1355	            candidate,
  1356	            evidence,
  1357	            support=report,
  1358	        )
  1359	        plan = replace(plan, finalizer=finalizer_resolution)
  1360	        finalize_request = FinalizeRequest(
  1361	            schema_version=SCHEMA_VERSION,
  1362	            plan=plan,
  1363	            artifacts=[item.video for item in segment_results],
  1364	            output_name=request.output_name,
  1365	            backend_config={
  1366	                candidate.id: dict(request.backend_config.get(candidate.id, {}))
  1367	            }
  1368	            if candidate.id in request.backend_config
  1369	            else {},
  1370	            metadata=request.metadata,
  1371	        )
  1372	        self._observe("finalize", backend=candidate.id)
  1373	        response = self._run_command(
  1374	            candidate,
  1375	            "finalize",
  1376	            finalize_request,
  1377	            workspace=workspace,
  1378	        )
  1379	        if not isinstance(response, RenderResult):
  1380	            raise_protocol_error(
  1381	                backend=candidate.id,
  1382	                message="finalize operation did not return a RenderResult",
  1383	                details={"received_type": type(response).__name__},
  1384	            )
  1385	        try:
  1386	            response = finalize_request.validate_final_result(response)
  1387	        except (TypeError, ValueError) as exc:
  1388	            raise_invalid_artifact_error(
  1389	                backend=candidate.id,
  1390	                message=f"finalizer returned an invalid result: {exc}",
  1391	                recovery_command="rerun finalization in a fresh invocation workspace",
  1392	                details={"error_type": type(exc).__name__},
  1393	            )
  1394	        self._observe("validate", backend=candidate.id)
  1395	        validated = self._validator(
  1396	            response,
  1397	            expected_profile=plan.profile,
  1398	            workspace_root=workspace,
  1399	        )
  1400	        self._validate_planned_duration(
  1401	            validated,
  1402	            planned_frames=(
  1403	                plan.window.duration_frames
  1404	                if plan.window is not None
  1405	                else plan.total_frames
  1406	            ),
  1407	            canonical_profile=plan.profile,
  1408	            backend=candidate.id,
  1409	            label="finalized artifact",
  1410	        )
  1411	        completed = self.complete_audio(
  1412	            validated,
  1413	            request=request,
  1414	            plan=plan,
  1415	            workspace=workspace,

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '1410,1745p' && git diff --unified=20 a72729db..98f4edea -- tests/core/rendering/test_service.py | sed -n '1,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 41ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_service.py b/tests/core/rendering/test_service.py
index a0fd6e2a..c1c327b6 100644
--- a/tests/core/rendering/test_service.py
+++ b/tests/core/rendering/test_service.py
@@ -1,24 +1,25 @@
 from __future__ import annotations
 
 import hashlib
 import json
+import shutil
 import subprocess
 import sys
 from dataclasses import replace
 from pathlib import Path
 from typing import Any
 
 import pytest
 
 from astrid.core.pack.alias_resolver import AliasResolver
 from astrid.core.pack.override import OverrideStore
 from astrid.core.rendering.contracts import (
     SCHEMA_VERSION,
     Attachment,
     AudioOwnership,
     FinalizerManifest,
     FinalizerResolution,
     FrameWindow,
     PlannerManifest,
     PlannerResolution,
     RenderPlan,
@@ -28,40 +29,41 @@ from astrid.core.rendering.contracts import (
     RendererManifest,
     RendererResolution,
     RenderSegment,
     SupportReport,
     VideoArtifact,
 )
 from astrid.core.rendering.errors import (
     RendererInternalError,
     RendererInvalidArtifactError,
     RendererProtocolError,
     RendererUnsupportedError,
     raise_internal_error,
 )
 from astrid.packs.rendering.planners.legacy_hybrid import run as legacy_hybrid
 from astrid.core.rendering.registry import (
     ExecutionEligibility,
     FinalizerRegistry,
     PlannerRegistry,
     RendererRegistry,
     RenderingCandidate,
+    load_default_registries,
 )
 from astrid.core.rendering.publication import publish_render_result
 from astrid.core.rendering.service import (
     LegacyRenderRoutingWarning,
     RenderService,
 )
 
 
 def _digest(value: str) -> str:
     return hashlib.sha256(value.encode()).hexdigest()
 
 
 def _profile(*, audio: bool = False) -> RenderProfile:
     return RenderProfile(
         width=160,
         height=90,
         fps_rational=(10, 1),
         time_base=(1, 10240),
         container="mp4",
         video_codec="h264",
@@ -534,80 +536,87 @@ def test_legacy_remotion_falls_back_when_ffmpeg_declines_support(
 ) -> None:
     transport = FakeTransport()
     transport.support["rendering.ffmpeg"] = _support(
         "rendering.ffmpeg",
         supported=False,
         alternatives=["rendering.remotion"],
     )
     service = _service(tmp_path, transport)
 
     service.render_request(
         _request(tmp_path),
         selector="remotion",
         out_path=tmp_path / "legacy-remotion-fallback.mp4",
     )
 
     assert transport.calls == [
         ("support", "rendering.ffmpeg"),
         ("support", "rendering.remotion"),
         ("render", "rendering.remotion"),
     ]
+    payload = _sidecar(tmp_path / "legacy-remotion-fallback.mp4")
+    routing = payload["routing"]
+    reason = routing["segment_reasons"]["0"]
+    assert "rendering.ffmpeg" in reason
+    assert "rejected" in reason
 
 
 def test_legacy_ffmpeg_is_strict(tmp_path: Path) -> None:
     transport = FakeTransport()
     service = _service(tmp_path, transport)
 
     service.render_request(
         _request(tmp_path),
         selector="ffmpeg",
         out_path=tmp_path / "legacy-ffmpeg.mp4",
     )
 
     assert transport.calls == [
         ("support", "rendering.ffmpeg"),
         ("render", "rendering.ffmpeg"),
     ]
 
 
 def test_hybrid_selects_planner_and_executes_its_segment(tmp_path: Path) -> None:
     transport = FakeTransport()
     transport.plan = _plan("fixture.window")
     service = _service(
         tmp_path,
         transport,
         renderer_ids=("fixture.window",),
         planner_ids=("rendering.legacy_hybrid",),
     )
 
     service.render_request(
         _request(tmp_path),
         selector="hybrid",
         out_path=tmp_path / "hybrid.mp4",
     )
 
     assert transport.calls[:2] == [
         ("support", "rendering.legacy_hybrid"),
         ("plan", "rendering.legacy_hybrid"),
     ]
     assert ("render", "fixture.window") in transport.calls
-    assert ("finalize", "rendering.ffmpeg-finalizer") not in transport.calls
+    # The plan pins the ffmpeg finalizer; even a single-segment hybrid plan
+    # runs it (profile/audio normalization is the finalizer's contract).
+    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
 
 
 def test_planned_window_is_materialized_for_full_timeline_renderer(
     tmp_path: Path,
 ) -> None:
     transport = FakeTransport()
     transport.plan = _plan("fixture.full")
     renderers = RendererRegistry(
         [
             _candidate(
                 tmp_path,
                 "fixture.full",
                 "renderer",
                 capabilities={
                     "supports_full_timeline": True,
                     "supports_windows": False,
                 },
             )
         ]
     )
@@ -1004,42 +1013,44 @@ def _hybrid_timeline(*, fps: int = 24) -> dict[str, Any]:
                 "volume": 0,
             },
             {
                 "id": "title",
                 "at": 2,
                 "track": "v",
                 "clipType": "text-card",
                 "hold": 1,
             },
         ],
     }
 
 
 def _hybrid_request(
     tmp_path: Path,
     timeline: dict[str, Any],
     *,
     config: dict[str, Any] | None = None,
     audio: AudioOwnership | None = None,
 ) -> RenderRequest:
-    timeline_path = tmp_path / "timeline.json"
-    assets_path = tmp_path / "assets.json"
+    root = tmp_path / "media"
+    root.mkdir(exist_ok=True)
+    timeline_path = root / "timeline.json"
+    assets_path = root / "assets.json"
     timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
     assets_path.write_text(json.dumps({"assets": {}}), encoding="utf-8")
     return RenderRequest(
         schema_version=SCHEMA_VERSION,
         timeline_path=str(timeline_path),
         assets_registry_path=str(assets_path),
         output_name="video.mp4",
         audio=audio,
         backend_config=(
             {} if config is None else {"rendering.legacy_hybrid": config}
         ),
     )
 
 
 def _planner_support_resolver(
     accepted: set[str] | None = None,
 ):
     supported = (
         {"raw_command.renderer", "rendering.remotion", "rendering.ffmpeg"}
         if accepted is None
@@ -1215,40 +1226,42 @@ class _RawFixtureTransport(FakeTransport):
             True,
             True,
         ),
         (
             "ffmpeg",
             False,
             [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
             "ffmpeg",
             "rendering.ffmpeg",
             False,
             False,
         ),
         (
             "hybrid",
             True,
             [
                 ("support", "rendering.legacy_hybrid"),
                 ("plan", "rendering.legacy_hybrid"),
                 ("support", "fixture.window"),
                 ("render", "fixture.window"),
+                ("support", "rendering.ffmpeg-finalizer"),
+                ("finalize", "rendering.ffmpeg-finalizer"),
             ],
             "hybrid",
             "fixture.window",
             False,
             False,
         ),
     ],
     ids=[
         "qualified-remotion",
         "qualified-ffmpeg",
         "legacy-remotion",
         "default-remotion",
         "legacy-ffmpeg",
         "hybrid",
     ],
 )
 def test_selector_routing_matrix(
     tmp_path: Path,
     selector: str | None,
     hybrid_plan: bool,
@@ -1265,41 +1278,42 @@ def test_selector_routing_matrix(
             tmp_path,
             transport,
             renderer_ids=("fixture.window",),
             planner_ids=("rendering.legacy_hybrid",),
         )
     else:
         service = _service(tmp_path, transport)
     output = tmp_path / "routing.mp4"
 
     if warning:
         with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
             service.render_request(
                 _request(tmp_path), selector=selector, out_path=output
             )
     else:
         service.render_request(
             _request(tmp_path), selector=selector, out_path=output
         )
 
     assert transport.calls == expected_calls
-    assert not any(verb == "finalize" for verb, _backend in transport.calls)
+    if selector != "hybrid":
+        assert not any(verb == "finalize" for verb, _backend in transport.calls)
     payload = _sidecar(output)
     routing = payload["routing"]
     assert routing["requested_engine"] == expected_engine
     assert routing["requested_policy"] == expected_engine
     assert routing["resolved_backend"] == expected_backend
     assert routing["resolved_backends"] == [expected_backend]
     assert routing["auto_route"] is auto_route
     assert payload["requested_policy"] == expected_engine
 
 
 def test_trust_denied_higher_priority_candidate_never_wins(
     tmp_path: Path,
 ) -> None:
     renderers = RendererRegistry(
         [
             _candidate(
                 tmp_path,
                 "contested.renderer",
                 "renderer",
                 eligible=False,
@@ -1467,41 +1481,41 @@ def test_hype_mp4_default_output_name_is_preserved(tmp_path: Path) -> None:
         "expect_finalize",
         "expected_engine",
     ),
     [
         ("rendering.remotion", None, {}, False, "rendering.remotion"),
         ("rendering.ffmpeg", None, {}, False, "rendering.ffmpeg"),
         (
             "rendering.ffmpeg",
             None,
             {"rendering.ffmpeg": {"mode": "optimized", "stream_copy": True}},
             False,
             "rendering.ffmpeg",
         ),
         (
             "rendering.ffmpeg",
             None,
             {"rendering.ffmpeg": {"audio_reactive": True}},
             False,
             "rendering.ffmpeg",
         ),
-        ("hybrid", (10,), {}, False, "hybrid"),
+        ("hybrid", (10,), {}, True, "hybrid"),
         ("hybrid", (5, 5), {}, True, "hybrid"),
     ],
     ids=[
         "remotion",
         "ffmpeg",
         "ffmpeg-optimized",
         "ffmpeg-audio-reactive",
         "hybrid-single-segment",
         "hybrid-multi-segment",
     ],
 )
 def test_builtin_paths_commit_exactly_one_video_and_sidecar(
     tmp_path: Path,
     selector: str,
     plan_segments: tuple[int, ...] | None,
     backend_config: dict[str, dict[str, Any]],
     expect_finalize: bool,
     expected_engine: str,
 ) -> None:
     transport = FakeTransport()
@@ -1667,40 +1681,43 @@ def test_audio_ownership_matrix_across_backends(
     def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
         return replace(
             result,
             video=replace(
                 result.video,
                 profile=_profile(audio=True),
                 audio=AudioOwnership.RENDERED,
             ),
             audio_ownership=AudioOwnership.RENDERED,
         )
 
     if plan_segments is not None:
         transport.plan = _plan("fixture.window", segment_frames=plan_segments)
         service = _service(
             tmp_path,
             transport,
             renderer_ids=("fixture.window",),
             planner_ids=("rendering.legacy_hybrid",),
             audio_completer=audio_completer if completer else None,
         )
+        # A pinned planner finalizer completes audio for hybrid plans; the
+        # fixture finalizer must honor the ownership the request asked for.
+        transport.finalize_ownership = ownership
     else:
         service = _service(
             tmp_path,
             transport,
             audio_completer=audio_completer if completer else None,
         )
     output = tmp_path / f"audio-{ownership.value}.mp4"
 
     service.render_request(
         replace(_request(tmp_path), audio=ownership),
         selector=selector,
         out_path=output,
     )
 
     payload = _sidecar(output)
     assert payload["audio_ownership"] == expected.value
     assert payload["routing"]["requested_engine"] == (
         "hybrid" if plan_segments is not None else selector
     )
 
@@ -1821,20 +1838,231 @@ def test_audio_completer_dropping_attachments_is_rejected(tmp_path: Path) -> Non
                 profile=_profile(audio=True),
                 audio=AudioOwnership.RENDERED,
                 attachments={},
             ),
             audio_ownership=AudioOwnership.RENDERED,
         )
 
     service = _service(tmp_path, transport, audio_completer=bad_completer)
     output = tmp_path / "dropped-attachments.mp4"
 
     with pytest.raises(RendererInvalidArtifactError, match="attachments"):
         service.render_request(
             replace(_request(tmp_path), audio=AudioOwnership.PASSTHROUGH),
             selector="rendering.ffmpeg",
             out_path=output,
         )
 
     assert not output.exists()
     assert not list(tmp_path.glob("*.provenance.json"))
     assert not list(tmp_path.glob(".*.render-service-*"))
+
+
+# ---------------------------------------------------------------------------
+# Real-backend integration through the generic service (issue-8 coverage)
+# ---------------------------------------------------------------------------
+
+
+def _require_ffmpeg() -> None:
+    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
+        pytest.skip("real FFmpeg smoke dependency is unavailable")
+
+
+def _real_service(tmp_path: Path) -> RenderService:
+    renderers, planners, finalizers = load_default_registries(
+        tmp_path, include_installed=False
+    )
+    return RenderService(registries=(renderers, planners, finalizers))
+
+
+def _real_media_inputs(tmp_path: Path) -> tuple[Path, Path]:
+    root = tmp_path / "media"
+    root.mkdir(exist_ok=True)
+    source = root / "source.mp4"
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
+            "color=c=blue:s=160x90:r=10:d=0.5",
+            "-c:v",
+            "libx264",
+            "-pix_fmt",
+            "yuv420p",
+            "-an",
+            str(source),
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
+                    "visual": {"canvas": {"width": 160, "height": 90, "fps": 10}}
+                },
+                "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
+                "clips": [
+                    {
+                        "id": "source",
+                        "at": 0,
+                        "track": "v",
+                        "clipType": "media",
+                        "asset": "source",
+                        "from": 0,
+                        "to": 0.5,
+                        "speed": 1,
+                        "volume": 0,
+                    }
+                ],
+            }
+        ),
+        encoding="utf-8",
+    )
+    assets_path.write_text(
+        json.dumps(
+            {
+                "assets": {
+                    "source": {
+                        "file": source.name,
+                        "type": "video/mp4",
+                        "duration": 0.5,
+                        "resolution": "160x90",
+                        "fps": 10,
+                    }
+                }
+            }
+        ),
+        encoding="utf-8",
+    )
+    return timeline_path, assets_path
+
+
+def _add_audio_track(timeline_path: Path) -> None:
+    """Mux an AAC track into the media source so the whole-media path with
+    audio (the canonical 48 kHz contract) is exercised end to end."""
+    source = timeline_path.parent / "source.mp4"
+    audio_path = source.with_suffix(".aac")
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
+            "-c:a",
+            "aac",
+            "-b:a",
+            "128k",
+            str(audio_path),
+        ],
+        check=True,
+        capture_output=True,
+        text=True,
+    )

exec
/bin/zsh -lc "rg -n \"planner.*alias|planned.*alias|segment.*alias|finalizer.*alias|lineage|fake-finalizer|winner-finalizer\" tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py && nl -ba tests/core/rendering/test_service.py | sed -n '750,920p;1280,1435p;1580,1735p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
exec
/bin/zsh -lc "rg -n \"alias_chain|FinalizerResolution|RendererResolution|OverrideStore\" tests/core/rendering/test_service.py | tail -80 && git diff --unified=0 a72729db..98f4edea -- tests/core/rendering/test_service.py | rg '"'^'"\\+.*(alias|override|lineage|finalizer)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
15:from astrid.core.pack.override import OverrideStore
21:    FinalizerResolution,
30:    RendererResolution,
165:def _renderer_resolution(backend: str) -> RendererResolution:
166:    return RendererResolution(
170:        alias_chain=[],
189:) -> FinalizerResolution:
190:    return FinalizerResolution(
692:    overrides = OverrideStore(tmp_path / "override-project")
715:    assert resolution["alias_chain"] == ["acme.alias", "acme.original"]
1360:    overrides = OverrideStore(tmp_path / "override-project")
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
+    # The plan pins the ffmpeg finalizer; even a single-segment hybrid plan
+    # runs it (profile/audio normalization is the finalizer's contract).
+    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
+                ("support", "rendering.ffmpeg-finalizer"),
+                ("finalize", "rendering.ffmpeg-finalizer"),
+        # A pinned planner finalizer completes audio for hybrid plans; the
+        # fixture finalizer must honor the ownership the request asked for.
+    renderers, planners, finalizers = load_default_registries(
+    return RenderService(registries=(renderers, planners, finalizers))
+                "theme_overrides": {
+    the real FFmpeg backend and the real ffmpeg finalizer concatenates."""
+    assert resolved["finalizer"] == "rendering.ffmpeg-finalizer"

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '300,515p' && rg -n \"finalizer_id\" tests/core/rendering/test_service.py astrid/core/rendering/service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   371	                details={"error_type": type(exc).__name__},
   372	            )
   373	
   374	    @staticmethod
   375	    def _one_selector(
   376	        selector: str | None,
   377	        engine: str | None,
   378	        backend: str | None,
   379	    ) -> str | None:
   380	        supplied = [item for item in (selector, engine, backend) if item is not None]
   381	        if not supplied:
   382	            return None
   383	        if len(set(supplied)) != 1:
   384	            raise_protocol_error(
   385	                backend=_CORE_BACKEND_ID,
   386	                message="selector, engine, and backend disagree",
   387	                recovery_command="supply one renderer selector spelling and retry",
   388	                details={"selectors": supplied},
   389	            )
   390	        return supplied[0]
   391	
   392	    @staticmethod
   393	    def _absolute_input_paths(request: RenderRequest) -> RenderRequest:
   394	        timeline = Path(request.timeline_path).expanduser()
   395	        assets = (
   396	            None
   397	            if request.assets_registry_path is None
   398	            else Path(request.assets_registry_path).expanduser()
   399	        )
   400	        return replace(
   401	            request,
   402	            timeline_path=str(timeline.resolve(strict=False)),
   403	            assets_registry_path=(
   404	                None if assets is None else str(assets.resolve(strict=False))
   405	            ),
   406	        )
   407	
   408	    def _render_in_workspace(
   409	        self,
   410	        request: RenderRequest,
   411	        *,
   412	        policy: _SelectionPolicy,
   413	        workspace: Path,
   414	        out_path: Path,
   415	        sidecar_path: Path,
   416	        previous_outputs: tuple[object, ...],
   417	        v1_compatibility: Mapping[str, Any] | None,
   418	    ) -> Path:
   419	        selected = self._select(request, policy=policy, workspace=workspace)
   420	        if policy.kind == "planner":
   421	            plan, segment_results, pinned_finalizer = self._execute_planner(
   422	                request,
   423	                policy=policy,
   424	                selected=selected,
   425	                workspace=workspace,
   426	            )
   427	            if not segment_results:
   428	                raise_unsupported_error(
   429	                    backend=selected.candidate.id,
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
   491	        )
   492	        fragments = self._merge_backend_fragments(fragment_results)
   493	        provenance = self._provenance_builder(
   494	            engine=policy.requested,
   495	            output=out_path,
   496	            timeline=request.timeline_path,
   497	            assets_registry=request.assets_registry_path,
   498	            plan=plan,
   499	            artifact_profiles=artifact_lineage,
   500	            audio_ownership=final_result.audio_ownership,
   501	            normalization=final_result.normalization,
   502	            attachments=final_result.attachments,
   503	            backend_fragments=fragments,
   504	            v1_compatibility=compatibility,
   505	        )
   506	        self._observe(
   507	            "publish",
   508	            backend=(
   509	                plan.planner.id if policy.kind == "planner" else selected.candidate.id
   510	            ),
   511	            output=str(out_path),
   512	            sidecar=str(sidecar_path),
   513	        )
   514	        published = self._publisher(
   515	            source_video,
astrid/core/rendering/service.py:170:        finalizer_id: str | None = None,
astrid/core/rendering/service.py:207:        self.finalizer_id = finalizer_id
astrid/core/rendering/service.py:1645:        if self.finalizer_id is not None:
astrid/core/rendering/service.py:1648:                self.finalizer_id,

codex
The main fixes are present, but two edge cases need confirmation: finalizer lineage after the final support pass, and whether an explicitly supplied default-valued `--engine remotion` is distinguishable from omission when `--backend` is also present. I’m checking those against the actual DTO/provenance flow now.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/packs/rendering/test_render_facade.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 1017ms:
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
/bin/zsh -lc "nl -ba tests/packs/rendering/test_audio_reactive_colour.py | sed -n '130,225p' && rg -n \"audio_reactive|audio-reactive|match_and_validate|specialization\" astrid/packs/rendering/backends/ffmpeg tests/core/rendering/test_service.py | head -100 && nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   130	
   131	
   132	@pytest.mark.parametrize("engine", ["remotion", "ffmpeg", "hybrid"])
   133	def test_render_dispatches_compact_effect_to_ffmpeg_specialization(
   134	    tmp_path: Path, engine: str, monkeypatch: pytest.MonkeyPatch
   135	) -> None:
   136	    timeline_path, assets_path, _audio_path = _write_inputs(tmp_path)
   137	    out_path = tmp_path / engine / "hype.mp4"
   138	
   139	    class _FakeService:
   140	        def render(self, *args, **kwargs) -> Path:
   141	            return out_path.resolve()
   142	
   143	    monkeypatch.setattr(render_run, "_default_service", lambda: _FakeService())
   144	
   145	    with patch.object(audio_reactive_colour, "render") as mocked:
   146	        output = render_run.render(
   147	            timeline_path,
   148	            assets_path,
   149	            out_path,
   150	            engine=engine,
   151	            keep_previous_renders=True,
   152	        )
   153	
   154	    # Dispatch is delegated to RenderService; the audio-reactive specialization
   155	    # is service-side support evidence, so the facade never invokes it.
   156	    assert output == out_path.resolve()
   157	    mocked.assert_not_called()
   158	
   159	
   160	@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg and ffprobe are required")
   161	def test_real_ffmpeg_render_has_exact_marker_frames_and_audio(tmp_path: Path) -> None:
   162	    audio_path = tmp_path / "tone.wav"
   163	    subprocess.run(
   164	        [
   165	            "ffmpeg",
   166	            "-hide_banner",
   167	            "-y",
   168	            "-f",
   169	            "lavfi",
   170	            "-i",
   171	            "sine=frequency=440:sample_rate=44100:duration=0.5",
   172	            str(audio_path),
   173	        ],
   174	        check=True,
   175	        capture_output=True,
   176	        text=True,
   177	    )
   178	    spec = audio_reactive_colour.match_and_validate(
   179	        _timeline(), _registry(audio_path), tmp_path / "hype.assets.json"
   180	    )
   181	    assert spec is not None
   182	    out_path = audio_reactive_colour.render(spec, tmp_path / "render.mp4")
   183	
   184	    raw = subprocess.run(
   185	        [
   186	            "ffmpeg",
   187	            "-v",
   188	            "error",
   189	            "-i",
   190	            str(out_path),
   191	            "-vf",
   192	            "crop=2:2:320:180,scale=1:1,format=rgb24",
   193	            "-f",
   194	            "rawvideo",
   195	            "-",
   196	        ],
   197	        check=True,
   198	        capture_output=True,
   199	    ).stdout
   200	    pixels = [raw[index : index + 3] for index in range(0, len(raw), 3)]
   201	    changed = [
   202	        index
   203	        for index in range(1, len(pixels))
   204	        if pixels[index] != pixels[index - 1]
   205	    ]
   206	    assert len(pixels) == 24
   207	    assert changed == [3, 8, 17]
   208	
   209	    streams = json.loads(
   210	        subprocess.run(
   211	            [
   212	                "ffprobe",
   213	                "-v",
   214	                "error",
   215	                "-show_entries",
   216	                "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
   217	                "-of",
   218	                "json",
   219	                str(out_path),
   220	            ],
   221	            check=True,
   222	            capture_output=True,
   223	            text=True,
   224	        ).stdout
   225	    )["streams"]
tests/core/rendering/test_service.py:1497:            {"rendering.ffmpeg": {"audio_reactive": True}},
tests/core/rendering/test_service.py:1508:        "ffmpeg-audio-reactive",
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:1:"""FFmpeg specialization for the audio-reactive-colour timeline element."""
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:14:EFFECT_ID = "audio-reactive-colour"
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:15:ADAPTER_ID = "audio-reactive-colour/v1"
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:94:            f"{EFFECT_ID} FFmpeg specialization requires a local audio asset"
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:107:def match_and_validate(
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:250:    # Import locally because the support module also imports this specialization
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:391:        prefix="astrid-audio-reactive-colour-", dir=str(out_path.parent)
astrid/packs/rendering/backends/ffmpeg/support.py:27:from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
astrid/packs/rendering/backends/ffmpeg/support.py:247:    allow_audio_reactive: bool = True,
astrid/packs/rendering/backends/ffmpeg/support.py:307:        if clip_type == audio_reactive_colour.EFFECT_ID:
astrid/packs/rendering/backends/ffmpeg/support.py:309:            if not allow_audio_reactive:
astrid/packs/rendering/backends/ffmpeg/support.py:322:                "audio-reactive-colour specialization requires exactly one effect clip"
astrid/packs/rendering/backends/ffmpeg/support.py:733:        and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
astrid/packs/rendering/backends/ffmpeg/support.py:736:    specialization = False
astrid/packs/rendering/backends/ffmpeg/support.py:739:            spec = audio_reactive_colour.match_and_validate(
astrid/packs/rendering/backends/ffmpeg/support.py:745:            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
astrid/packs/rendering/backends/ffmpeg/support.py:747:            specialization = spec is not None
astrid/packs/rendering/backends/ffmpeg/support.py:755:        "media_only": not specialization,
astrid/packs/rendering/backends/ffmpeg/support.py:759:        "audio_reactive_colour": specialization,
astrid/packs/rendering/backends/ffmpeg/support.py:765:    if specialization:
astrid/packs/rendering/backends/ffmpeg/support.py:766:        features["specialization"] = audio_reactive_colour.ADAPTER_ID
astrid/packs/rendering/backends/ffmpeg/command.py:84:        allow_audio_reactive=False,
astrid/packs/rendering/backends/ffmpeg/run.py:46:from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
astrid/packs/rendering/backends/ffmpeg/run.py:285:            "audio_reactive_colour": False,
astrid/packs/rendering/backends/ffmpeg/run.py:297:def _audio_reactive_ffmpeg_element(
astrid/packs/rendering/backends/ffmpeg/run.py:301:    element = effects.get(audio_reactive_colour.EFFECT_ID)
astrid/packs/rendering/backends/ffmpeg/run.py:305:        != audio_reactive_colour.ADAPTER_ID
astrid/packs/rendering/backends/ffmpeg/run.py:311:def render_audio_reactive_colour_if_supported(
astrid/packs/rendering/backends/ffmpeg/run.py:322:    """Preserve the facade's early audio-reactive FFmpeg specialization."""
astrid/packs/rendering/backends/ffmpeg/run.py:331:            and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
astrid/packs/rendering/backends/ffmpeg/run.py:337:    resolve_element = _audio_reactive_ffmpeg_element
astrid/packs/rendering/backends/ffmpeg/run.py:344:    spec = audio_reactive_colour.match_and_validate(
astrid/packs/rendering/backends/ffmpeg/run.py:378:        rendered_video = audio_reactive_colour.render(spec, staged_video)
astrid/packs/rendering/backends/ffmpeg/run.py:393:        provenance["ffmpeg_specialization"] = audio_reactive_colour.ADAPTER_ID
astrid/packs/rendering/backends/ffmpeg/run.py:394:        provenance["audio_reactive_colour"] = {
astrid/packs/rendering/backends/ffmpeg/run.py:424:            stage="render_ffmpeg_audio_reactive_colour",
astrid/packs/rendering/backends/ffmpeg/run.py:430:            stage="render_ffmpeg_audio_reactive_colour",
astrid/packs/rendering/backends/ffmpeg/run.py:435:            label="Rendered audio-reactive colour video",
astrid/packs/rendering/backends/ffmpeg/run.py:437:            stage="render_ffmpeg_audio_reactive_colour",
astrid/packs/rendering/backends/ffmpeg/run.py:440:                "specialization": audio_reactive_colour.ADAPTER_ID,
astrid/packs/rendering/backends/ffmpeg/run.py:446:            stage="render_ffmpeg_audio_reactive_colour",
astrid/packs/rendering/backends/ffmpeg/run.py:447:            label="Render audio-reactive colour timeline with FFmpeg",
astrid/packs/rendering/backends/ffmpeg/run.py:452:                "specialization": audio_reactive_colour.ADAPTER_ID,
astrid/packs/rendering/backends/ffmpeg/run.py:542:    specialization_spec: audio_reactive_colour.AudioReactiveColourSpec | None = None
astrid/packs/rendering/backends/ffmpeg/run.py:543:    if report.features.get("audio_reactive_colour") is True:
astrid/packs/rendering/backends/ffmpeg/run.py:546:        specialization_spec = audio_reactive_colour.match_and_validate(
astrid/packs/rendering/backends/ffmpeg/run.py:551:        if specialization_spec is None:
astrid/packs/rendering/backends/ffmpeg/run.py:553:                "audio-reactive support evidence did not produce a specialization spec"
astrid/packs/rendering/backends/ffmpeg/run.py:561:        if specialization_spec is not None:
astrid/packs/rendering/backends/ffmpeg/run.py:562:            audio_reactive_colour.render(specialization_spec, output_path)
astrid/packs/rendering/backends/ffmpeg/run.py:597:        if specialization_spec is not None:
astrid/packs/rendering/backends/ffmpeg/run.py:604:                for event in specialization_spec.events
astrid/packs/rendering/backends/ffmpeg/run.py:606:            specialization_fragment = {
astrid/packs/rendering/backends/ffmpeg/run.py:607:                "id": audio_reactive_colour.ADAPTER_ID,
astrid/packs/rendering/backends/ffmpeg/run.py:609:                "event_count": len(specialization_spec.events),
astrid/packs/rendering/backends/ffmpeg/run.py:610:                "frame_count": specialization_spec.total_frames,
astrid/packs/rendering/backends/ffmpeg/run.py:611:                "fps": specialization_spec.fps,
astrid/packs/rendering/backends/ffmpeg/run.py:612:                "marker_sha256": specialization_spec.marker_sha256,
astrid/packs/rendering/backends/ffmpeg/run.py:614:            fragment["specialization"] = specialization_fragment
astrid/packs/rendering/backends/ffmpeg/run.py:615:            provenance_v1["ffmpeg_specialization"] = (
astrid/packs/rendering/backends/ffmpeg/run.py:616:                audio_reactive_colour.ADAPTER_ID
astrid/packs/rendering/backends/ffmpeg/run.py:618:            provenance_v1["audio_reactive_colour"] = {
astrid/packs/rendering/backends/ffmpeg/run.py:620:                for key, value in specialization_fragment.items()
astrid/packs/rendering/backends/ffmpeg/run.py:734:    "render_audio_reactive_colour_if_supported",
     1	"""Fail-closed, request-sensitive support evidence for ``rendering.ffmpeg``.
     2	
     3	This module is deliberately read-only.  It validates a decoded timeline and
     4	asset registry, probes every referenced local source, and reports every reason
     5	the FFmpeg renderer cannot preserve the requested semantics.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import math
    11	import shutil
    12	from collections.abc import Callable, Mapping
    13	from dataclasses import dataclass
    14	from fractions import Fraction
    15	from pathlib import Path
    16	
    17	from astrid.core.rendering.profile import _mp4_time_base
    18	from typing import Any
    19	
    20	from astrid.core.media import MediaProbe, ffprobe_metadata_strict
    21	from astrid.core.rendering.contracts import (
    22	    AudioOwnership,
    23	    RenderRequest,
    24	    SCHEMA_VERSION,
    25	    SupportReport,
    26	)
    27	from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
    28	
    29	
    30	BACKEND_ID = "rendering.ffmpeg"
    31	BACKEND_VERSION = "1.0.0"
    32	ALTERNATIVE_BACKENDS = ("rendering.remotion",)
    33	
    34	_TRACK_KINDS = frozenset({"visual", "audio"})
    35	_POSITION_KEYS = frozenset({"x", "y", "width", "height"})
    36	_CROP_KEYS = frozenset({"cropTop", "cropBottom", "cropLeft", "cropRight"})
    37	_EFFECT_KEYS = frozenset({"effects", "entrance", "exit", "continuous", "keyframes"})
    38	_TIMELINE_EPSILON_SECONDS = 1e-9
    39	_SOURCE_BOUND_TOLERANCE_SECONDS = 0.001
    40	
    41	
    42	Probe = Callable[[str | Path], MediaProbe]
    43	BinaryResolver = Callable[[str], str | None]
    44	
    45	
    46	@dataclass(frozen=True)
    47	class _ClipRange:
    48	    clip: Mapping[str, Any]
    49	    at: float
    50	    source_from: float
    51	    source_to: float
    52	
    53	    @property
    54	    def duration(self) -> float:
    55	        return self.source_to - self.source_from
    56	
    57	    @property
    58	    def end(self) -> float:
    59	        return self.at + self.duration
    60	
    61	
    62	def _number(value: Any, label: str) -> float:
    63	    if isinstance(value, bool) or not isinstance(value, (int, float)):
    64	        raise ValueError(f"{label} must be a finite number")
    65	    result = float(value)
    66	    if not math.isfinite(result):
    67	        raise ValueError(f"{label} must be a finite number")
    68	    return result
    69	
    70	
    71	def _gain(value: Any, label: str, *, default: float = 1.0) -> float:
    72	    resolved = default if value is None else _number(value, label)
    73	    if not 0.0 <= resolved <= 1.0:
    74	        raise ValueError(f"{label} must be between 0 and 1")
    75	    return resolved
    76	
    77	
    78	def effective_gain(track: Mapping[str, Any], clip: Mapping[str, Any]) -> float:
    79	    """Return the exact timeline gain for one media clip.
    80	
    81	    Track mute is authoritative; otherwise track and clip gains multiply.  A
    82	    missing gain means unity, while malformed or out-of-range values are
    83	    rejected instead of clamped.
    84	    """
    85	
    86	    muted = track.get("muted", False)
    87	    if not isinstance(muted, bool):
    88	        raise ValueError(f"Track {track.get('id')!r} muted must be a boolean")
    89	    track_gain = _gain(
    90	        track.get("volume"),
    91	        f"Track {track.get('id')!r} volume",
    92	    )
    93	    clip_gain = _gain(
    94	        clip.get("volume"),
    95	        f"Clip {clip.get('id')!r} volume",
    96	    )
    97	    return 0.0 if muted else track_gain * clip_gain
    98	
    99	
   100	def _clip_range(clip: Mapping[str, Any]) -> _ClipRange:
   101	    clip_id = clip.get("id")
   102	    at = _number(clip.get("at", 0), f"Clip {clip_id!r} at")
   103	    source_from = _number(
   104	        clip.get("from", 0),
   105	        f"Clip {clip_id!r} from",
   106	    )
   107	    if "to" not in clip:
   108	        raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
   109	    source_to = _number(clip.get("to"), f"Clip {clip_id!r} to")
   110	    if at < 0:
   111	        raise ValueError(f"Clip {clip_id!r} has a negative timeline frame bound")
   112	    if source_from < 0 or source_to <= source_from:
   113	        raise ValueError(
   114	            f"Clip {clip_id!r} must have positive source bounds with to > from"
   115	        )
   116	    return _ClipRange(
   117	        clip=clip,
   118	        at=at,
   119	        source_from=source_from,
   120	        source_to=source_to,
   121	    )
   122	
   123	
   124	def _is_default(value: Any, default: Any) -> bool:
   125	    return value is None or value == default
   126	
   127	
   128	def _nonempty(value: Any) -> bool:
   129	    return value not in (None, False, "", (), [], {})
   130	
   131	
   132	def _validate_track_semantics(track: Mapping[str, Any]) -> list[str]:
   133	    reasons: list[str] = []
   134	    track_id = track.get("id")
   135	    try:
   136	        effective_gain(track, {})
   137	    except ValueError as exc:
   138	        reasons.append(str(exc))
   139	    if not _is_default(track.get("scale"), 1) or not _is_default(
   140	        track.get("fit"), "contain"
   141	    ) or not _is_default(track.get("blendMode"), "normal"):
   142	        reasons.append(
   143	            f"Track {track_id!r} uses unsupported visual transform semantics"
   144	        )
   145	    opacity = track.get("opacity")
   146	    if opacity is not None:
   147	        try:
   148	            if _number(opacity, f"Track {track_id!r} opacity") != 1.0:
   149	                reasons.append(
   150	                    f"Track {track_id!r} uses unsupported non-default opacity"
   151	                )
   152	        except ValueError as exc:
   153	            reasons.append(str(exc))
   154	    return reasons
   155	
   156	
   157	def _validate_clip_semantics(
   158	    clip: Mapping[str, Any],
   159	    track: Mapping[str, Any],
   160	) -> list[str]:
   161	    reasons: list[str] = []
   162	    clip_id = clip.get("id")
   163	    if "muted" in clip:
   164	        reasons.append(
   165	            f"Clip {clip_id!r} uses unsupported clip-level muted; use volume: 0"
   166	        )
   167	    try:
   168	        speed = _number(clip.get("speed", 1), f"Clip {clip_id!r} speed")
   169	        if speed != 1.0:
   170	            reasons.append(
   171	                f"Clip {clip_id!r} uses unsupported speed {speed}; rendering.ffmpeg requires 1.0"
   172	            )
   173	    except ValueError as exc:
   174	        reasons.append(str(exc))
   175	
   176	    positioned = sorted(key for key in _POSITION_KEYS if key in clip)
   177	    if positioned:
   178	        reasons.append(
   179	            f"Clip {clip_id!r} uses unsupported transforms: {', '.join(positioned)}"
   180	        )
   181	    cropped = sorted(
   182	        key
   183	        for key in _CROP_KEYS
   184	        if key in clip and not _is_default(clip.get(key), 0)
   185	    )
   186	    if cropped:
   187	        reasons.append(
   188	            f"Clip {clip_id!r} uses unsupported crop: {', '.join(cropped)}"
   189	        )
   190	    effects = sorted(
   191	        key for key in _EFFECT_KEYS if key in clip and _nonempty(clip.get(key))
   192	    )
   193	    if effects:
   194	        reasons.append(
   195	            f"Clip {clip_id!r} uses unsupported effects: {', '.join(effects)}"
   196	        )
   197	    if _nonempty(clip.get("transition")):
   198	        reasons.append(f"Clip {clip_id!r} uses an unsupported transition")
   199	    opacity = clip.get("opacity")
   200	    if opacity is not None:
   201	        try:
   202	            if _number(opacity, f"Clip {clip_id!r} opacity") != 1.0:
   203	                reasons.append(
   204	                    f"Clip {clip_id!r} uses unsupported non-default opacity"
   205	                )
   206	        except ValueError as exc:
   207	            reasons.append(str(exc))
   208	
   209	    params = clip.get("params")
   210	    if params is not None and not isinstance(params, Mapping):
   211	        reasons.append(f"Clip {clip_id!r} params must be an object")
   212	    elif isinstance(params, Mapping):
   213	        fades = [
   214	            name
   215	            for name in ("fadeIn", "fadeOut")
   216	            if name in params and _nonempty(params.get(name))
   217	        ]
   218	        if fades:
   219	            reasons.append(
   220	                f"Clip {clip_id!r} uses unsupported audio fades: {', '.join(fades)}"
   221	            )
   222	        other_params = sorted(set(params) - {"fadeIn", "fadeOut"})
   223	        if other_params and clip.get("clipType") == "media":
   224	            reasons.append(
   225	                f"Clip {clip_id!r} uses unsupported media params: {', '.join(other_params)}"
   226	            )
   227	
   228	    if clip.get("clipType") == "media":
   229	        if _nonempty(clip.get("hold")):
   230	            reasons.append(
   231	                f"Clip {clip_id!r} uses unsupported media hold semantics"
   232	            )
   233	        try:
   234	            _clip_range(clip)
   235	        except ValueError as exc:
   236	            reasons.append(str(exc))
   237	        try:
   238	            effective_gain(track, clip)
   239	        except ValueError as exc:
   240	            reasons.append(str(exc))

exec
/bin/zsh -lc "git diff --check a72729db..98f4edea && git diff --name-status a72729db..98f4edea && python - <<'PY'
import ast
from pathlib import Path
for p in [
 Path('astrid/core/rendering/service.py'),
 Path('astrid/packs/rendering/executors/render/run.py'),
 Path('astrid/packs/rendering/executors/render/legacy_engine.py'),
 Path('astrid/packs/rendering/planners/legacy_hybrid/run.py'),
]:
    ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    print('AST OK', p)
PY" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 159ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-4.md:4129: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:4130: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:4164: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:4165: trailing whitespace.
+ 
.oracle/checkins/batch-4.md:5308: trailing whitespace.
+   366	
.oracle/checkins/batch-4.md:5309: trailing whitespace.
+   367	
.oracle/checkins/batch-4.md:5324: trailing whitespace.
+   809	
.oracle/checkins/batch-4.md:5325: trailing whitespace.
+   810	
.oracle/checkins/batch-4.md:5331: trailing whitespace.
+   816	
.oracle/checkins/batch-4.md:5332: trailing whitespace.
+   817	
.oracle/checkins/batch-4.md:8231: trailing whitespace.
+  1234	
.oracle/checkins/batch-4.md:8252: trailing whitespace.
+  1255	
.oracle/checkins/batch-4.md:8269: trailing whitespace.
+  1272	
.oracle/checkins/batch-4.md:8286: trailing whitespace.
+   602	
.oracle/checkins/batch-4.md:8297: trailing whitespace.
+   613	
.oracle/checkins/batch-4.md:8348: trailing whitespace.
+   664	
.oracle/checkins/batch-4.md:8349: trailing whitespace.
+   665	
.oracle/checkins/batch-4.md:8417: trailing whitespace.
+   591	
.oracle/checkins/batch-4.md:8418: trailing whitespace.
+   592	
.oracle/checkins/batch-4.md:8858: trailing whitespace.
+   521	
.oracle/checkins/batch-4.md:8904: trailing whitespace.
+   567	
.oracle/checkins/batch-4.md:8912: trailing whitespace.
+   575	
.oracle/checkins/batch-4.md:8919: trailing whitespace.
+   145	
.oracle/checkins/batch-4.md:8927: trailing whitespace.
+   153	
.oracle/checkins/batch-4.md:8951: trailing whitespace.
+   177	
.oracle/checkins/batch-4.md:8952: trailing whitespace.
+   178	
.oracle/checkins/batch-4.md:8956: trailing whitespace.
+   353	
.oracle/checkins/batch-4.md:8957: trailing whitespace.
+   354	
.oracle/checkins/batch-4.md:8980: trailing whitespace.
+   377	

exec
/bin/zsh -lc "python - <<'PY'
import ast
from pathlib import Path
for p in [Path('astrid/core/rendering/service.py'), Path('astrid/packs/rendering/executors/render/run.py'), Path('astrid/packs/rendering/executors/render/legacy_engine.py'), Path('astrid/packs/rendering/planners/legacy_hybrid/run.py')]:
    ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
    print('AST OK', p)
PY

git diff --numstat a72729db..98f4edea -- . ':(exclude).oracle/checkins/batch-4.md'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
zsh:1: can't create temp file for here document: operation not permitted
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
69	11	astrid/core/rendering/service.py
392	0	astrid/packs/rendering/executors/render/legacy_engine.py
16	370	astrid/packs/rendering/executors/render/run.py
14	2	astrid/packs/rendering/planners/legacy_hybrid/run.py
233	5	tests/core/rendering/test_service.py
35	34	tests/packs/rendering/test_legacy_renderer_characterization.py
7	6	tests/packs/rendering/test_render_remotion_registry.py

collab: Wait
collab: Wait
exec
/bin/zsh -lc "rg -n \"whole_media|optimized|stream_copy|volume.*0|has_audio\" astrid/packs/rendering/backends/ffmpeg/support.py astrid/packs/rendering/backends/ffmpeg/run.py astrid/packs/rendering/backends/ffmpeg/command.py | head -160 && nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '540,805p' && nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '500,635p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/ffmpeg/command.py:34:    stream_copy_allowed: bool = False
astrid/packs/rendering/backends/ffmpeg/command.py:257:            inputs.stream_copy_allowed
astrid/packs/rendering/backends/ffmpeg/command.py:337:def _has_audio_clips(timeline_data: Mapping[str, Any]) -> bool:
astrid/packs/rendering/backends/ffmpeg/command.py:408:    has_audio = _has_audio_clips(inputs.timeline_data)
astrid/packs/rendering/backends/ffmpeg/command.py:421:        *(["-map", "[aout]"] if has_audio else []),
astrid/packs/rendering/backends/ffmpeg/command.py:431:            if has_audio
astrid/packs/rendering/backends/ffmpeg/command.py:464:        stream_copy_allowed = (
astrid/packs/rendering/backends/ffmpeg/command.py:465:            report.supported and bool(report.features.get("stream_copy"))
astrid/packs/rendering/backends/ffmpeg/command.py:468:        stream_copy_allowed = False
astrid/packs/rendering/backends/ffmpeg/command.py:469:    inputs = replace(inputs, stream_copy_allowed=stream_copy_allowed)
astrid/packs/rendering/backends/ffmpeg/command.py:481:    stream_copy_allowed: bool = False,
astrid/packs/rendering/backends/ffmpeg/command.py:496:            stream_copy_allowed=stream_copy_allowed,
astrid/packs/rendering/backends/ffmpeg/run.py:121:        stream_copy_allowed=bool(report.features.get("stream_copy")),
astrid/packs/rendering/backends/ffmpeg/run.py:286:            "whole_media": False,
astrid/packs/rendering/backends/ffmpeg/run.py:287:            "whole_media_optimization": False,
astrid/packs/rendering/backends/ffmpeg/run.py:288:            "stream_copy": False,
astrid/packs/rendering/backends/ffmpeg/run.py:470:    if ownership is AudioOwnership.RENDERED and not probe.has_audio_stream:
astrid/packs/rendering/backends/ffmpeg/run.py:474:    if ownership is not AudioOwnership.RENDERED and probe.has_audio_stream:
astrid/packs/rendering/backends/ffmpeg/support.py:165:            f"Clip {clip_id!r} uses unsupported clip-level muted; use volume: 0"
astrid/packs/rendering/backends/ffmpeg/support.py:424:    has_audio_clips: bool,
astrid/packs/rendering/backends/ffmpeg/support.py:426:    natural = AudioOwnership.RENDERED if has_audio_clips else AudioOwnership.NONE
astrid/packs/rendering/backends/ffmpeg/support.py:429:    if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
astrid/packs/rendering/backends/ffmpeg/support.py:435:    if request.profile is not None and request.profile.has_audio != (
astrid/packs/rendering/backends/ffmpeg/support.py:444:def _whole_media_optimization(
astrid/packs/rendering/backends/ffmpeg/support.py:564:    if profile.has_audio:
astrid/packs/rendering/backends/ffmpeg/support.py:665:        has_audio_clips=bool(audio_clips),
astrid/packs/rendering/backends/ffmpeg/support.py:703:        if kind == "audio" and not media_probe.has_audio_stream:
astrid/packs/rendering/backends/ffmpeg/support.py:707:        if kind == "visual" and media_probe.has_audio_stream:
astrid/packs/rendering/backends/ffmpeg/support.py:749:    whole_media = not reactive and _whole_media_optimization(
astrid/packs/rendering/backends/ffmpeg/support.py:760:        "whole_media": whole_media,
astrid/packs/rendering/backends/ffmpeg/support.py:761:        "whole_media_optimization": whole_media,
astrid/packs/rendering/backends/ffmpeg/support.py:762:        "stream_copy": whole_media,
   540	        if field in ("fps", "time_base"):
   541	            equal = _rational_equal(requested, produced)
   542	        else:
   543	            equal = requested == produced
   544	        if not equal:
   545	            reasons.append(
   546	                f"requested profile {field}={requested!r} is not produced by "
   547	                f"rendering.ffmpeg (produces {produced!r})"
   548	            )
   549	    # The command does NOT pin video_profile/video_level (libx264 picks the
   550	    # encoder default; stream-copy preserves whatever the source has). A
   551	    # request pinning them cannot be guaranteed at support time, so fail
   552	    # closed rather than report success and fail strict post-render
   553	    # validation.
   554	    for field, requested in (
   555	        ("video_profile", profile.video_profile),
   556	        ("video_level", profile.video_level),
   557	    ):
   558	        if requested is not None:
   559	            reasons.append(
   560	                f"requested profile {field}={requested!r} cannot be guaranteed "
   561	                f"by rendering.ffmpeg (encoder default or stream-copy preserves "
   562	                f"source values; omit {field} to use defaults)"
   563	            )
   564	    if profile.has_audio:
   565	        for field, requested, produced in (
   566	            ("audio_sample_rate", profile.audio_sample_rate, 48000),
   567	            ("audio_channel_layout", profile.audio_channel_layout, "stereo"),
   568	            ("audio_codec", profile.audio_codec, "aac"),
   569	        ):
   570	            if requested is not None and requested != produced:
   571	                reasons.append(
   572	                    f"requested profile {field}={requested!r} is not produced by "
   573	                    f"rendering.ffmpeg (produces {produced!r})"
   574	                )
   575	    return reasons
   576	
   577	
   578	def _fps_int(fps_rational: tuple[int, int] | None) -> int | None:
   579	    if fps_rational is None:
   580	        return None
   581	    num, den = fps_rational
   582	    return num // den if den and num % den == 0 else None
   583	
   584	
   585	def _rational_equal(a: Any, b: Any) -> bool:
   586	    try:
   587	        return Fraction(*a) == Fraction(*b)
   588	    except (TypeError, ValueError, ZeroDivisionError):
   589	        return False
   590	
   591	
   592	def _canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
   593	    overrides = timeline_data.get("theme_overrides")
   594	    visual = overrides.get("visual") if isinstance(overrides, Mapping) else None
   595	    canvas = visual.get("canvas") if isinstance(visual, Mapping) else None
   596	    canvas = canvas if isinstance(canvas, Mapping) else {}
   597	    values: list[int] = []
   598	    for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
   599	        value = canvas.get(key, default)
   600	        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
   601	            raise ValueError(f"Canvas {key} must be a positive integer")
   602	        values.append(value)
   603	    return values[0], values[1], values[2]
   604	
   605	
   606	def support(
   607	    request: RenderRequest,
   608	    timeline_data: Mapping[str, Any],
   609	    assets: Mapping[str, Any],
   610	    *,
   611	    probe: Probe | None = None,
   612	    which: BinaryResolver | None = None,
   613	) -> SupportReport:
   614	    """Return strict support evidence for one already-decoded request."""
   615	
   616	    reasons: list[str] = []
   617	    probe_media = probe or ffprobe_metadata_strict
   618	    resolve_binary = which or shutil.which
   619	    binary_available: dict[str, bool] = {}
   620	    for binary in ("ffmpeg", "ffprobe"):
   621	        available = resolve_binary(binary) is not None
   622	        binary_available[binary] = available
   623	        if not available:
   624	            reasons.append(f"required binary is unavailable: {binary}")
   625	
   626	    if request.window is not None:
   627	        reasons.append(
   628	            "rendering.ffmpeg accepts complete timelines, not native frame windows"
   629	        )
   630	    config = request.backend_config.get(BACKEND_ID, {})
   631	    if config:
   632	        reasons.append(
   633	            "rendering.ffmpeg does not accept backend-specific configuration"
   634	        )
   635	    if request.assets_registry_path is None:
   636	        reasons.append("rendering.ffmpeg requires an assets registry")
   637	    try:
   638	        _canvas(timeline_data)
   639	    except ValueError as exc:
   640	        reasons.append(str(exc))
   641	    reasons.extend(structural_reasons(timeline_data))
   642	
   643	    table = _assets_table(assets)
   644	    if table is None:
   645	        reasons.append("assets registry must contain an assets object")
   646	        table = {}
   647	    assets_path = _registry_path(request)
   648	    tracks = {
   649	        track.get("id"): track
   650	        for track in timeline_data.get("tracks", [])
   651	        if isinstance(track, Mapping)
   652	    }
   653	    media_clips = [
   654	        clip
   655	        for clip in timeline_data.get("clips", [])
   656	        if isinstance(clip, Mapping) and clip.get("clipType") == "media"
   657	    ]
   658	    audio_clips = [
   659	        clip
   660	        for clip in media_clips
   661	        if tracks.get(clip.get("track"), {}).get("kind") == "audio"
   662	    ]
   663	    ownership, ownership_reasons = _requested_ownership(
   664	        request,
   665	        has_audio_clips=bool(audio_clips),
   666	    )
   667	    reasons.extend(ownership_reasons)
   668	
   669	    probes: dict[str, MediaProbe] = {}
   670	    for clip in media_clips:
   671	        clip_id = clip.get("id")
   672	        asset_id = clip.get("asset")
   673	        if not isinstance(asset_id, str) or not asset_id:
   674	            reasons.append(f"Clip {clip_id!r} has no asset")
   675	            continue
   676	        entry = table.get(asset_id)
   677	        if not isinstance(entry, Mapping):
   678	            reasons.append(f"Clip {clip_id!r} references missing asset {asset_id!r}")
   679	            continue
   680	        try:
   681	            path = _asset_path(entry, asset_id=asset_id, assets_path=assets_path)
   682	        except (ValueError, FileNotFoundError) as exc:
   683	            reasons.append(str(exc))
   684	            continue
   685	        if asset_id not in probes and binary_available["ffprobe"]:
   686	            try:
   687	                probed = probe_media(path)
   688	                if not isinstance(probed, MediaProbe):
   689	                    raise TypeError("probe did not return MediaProbe")
   690	                probes[asset_id] = probed
   691	            except Exception as exc:
   692	                reasons.append(f"Asset {asset_id!r} cannot be probed: {exc}")
   693	
   694	        media_probe = probes.get(asset_id)
   695	        if media_probe is None:
   696	            continue
   697	        track = tracks.get(clip.get("track"), {})
   698	        kind = track.get("kind")
   699	        if kind == "visual" and not media_probe.has_video_stream:
   700	            reasons.append(
   701	                f"Visual clip {clip_id!r} source {asset_id!r} has no video stream"
   702	            )
   703	        if kind == "audio" and not media_probe.has_audio_stream:
   704	            reasons.append(
   705	                f"Audio clip {clip_id!r} source {asset_id!r} has no audio stream"
   706	            )
   707	        if kind == "visual" and media_probe.has_audio_stream:
   708	            try:
   709	                gain = effective_gain(track, clip)
   710	            except ValueError:
   711	                gain = 0.0
   712	            if gain != 0.0:
   713	                reasons.append(
   714	                    f"Visual clip {clip_id!r} requests embedded audio that rendering.ffmpeg would discard"
   715	                )
   716	        try:
   717	            bounds = _clip_range(clip)
   718	        except ValueError:
   719	            continue
   720	        source_duration = _probe_duration(media_probe)
   721	        if source_duration is None:
   722	            reasons.append(
   723	                f"Asset {asset_id!r} has no probed duration for source-bound validation"
   724	            )
   725	        elif bounds.source_to > source_duration + _SOURCE_BOUND_TOLERANCE_SECONDS:
   726	            reasons.append(
   727	                f"Clip {clip_id!r} source bound {bounds.source_to:.6f} exceeds "
   728	                f"asset {asset_id!r} duration {source_duration:.6f}"
   729	            )
   730	
   731	    reactive = any(
   732	        isinstance(clip, Mapping)
   733	        and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
   734	        for clip in timeline_data.get("clips", [])
   735	    )
   736	    specialization = False
   737	    if reactive:
   738	        try:
   739	            spec = audio_reactive_colour.match_and_validate(
   740	                dict(timeline_data),
   741	                dict(assets),
   742	                assets_path,
   743	            )
   744	        except Exception as exc:
   745	            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
   746	        else:
   747	            specialization = spec is not None
   748	
   749	    whole_media = not reactive and _whole_media_optimization(
   750	        timeline_data,
   751	        assets,
   752	        probes,
   753	    )
   754	    features: dict[str, bool | str] = {
   755	        "media_only": not specialization,
   756	        "full_timeline": True,
   757	        "windows": False,
   758	        "sequential_audio": True,
   759	        "audio_reactive_colour": specialization,
   760	        "whole_media": whole_media,
   761	        "whole_media_optimization": whole_media,
   762	        "stream_copy": whole_media,
   763	        "audio_ownership": ownership.value,
   764	    }
   765	    if specialization:
   766	        features["specialization"] = audio_reactive_colour.ADAPTER_ID
   767	
   768	    reasons.extend(_profile_support_reasons(request, timeline_data))
   769	
   770	    reasons = _dedupe(reasons)
   771	    return SupportReport(
   772	        schema_version=SCHEMA_VERSION,
   773	        supported=not reasons,
   774	        reasons=reasons,
   775	        features=features,
   776	        alternatives=list(ALTERNATIVE_BACKENDS) if reasons else [],
   777	        backend=BACKEND_ID,
   778	        backend_version=BACKEND_VERSION,
   779	    )
   780	
   781	
   782	__all__ = [
   783	    "ALTERNATIVE_BACKENDS",
   784	    "BACKEND_ID",
   785	    "BACKEND_VERSION",
   786	    "effective_gain",
   787	    "structural_reasons",
   788	    "support",
   789	]
   500	            if ownership is AudioOwnership.RENDERED
   501	            else None
   502	        ),
   503	        audio_channel_layout=(
   504	            _required(audio_layout, "audio channel layout")
   505	            if ownership is AudioOwnership.RENDERED
   506	            else None
   507	        ),
   508	        duration_tolerance=1,
   509	    )
   510	
   511	
   512	def _duration_frames(probe: MediaProbe, profile: RenderProfile) -> int:
   513	    if probe.duration_rational is not None:
   514	        duration = Fraction(*probe.duration_rational)
   515	    elif probe.duration_seconds is not None:
   516	        duration = Fraction(str(probe.duration_seconds))
   517	    else:
   518	        raise RuntimeError("ffprobe did not report a video duration")
   519	    frames = duration * Fraction(*profile.fps_rational)
   520	    return max(1, int(frames + Fraction(1, 2)))
   521	
   522	
   523	def _protocol_render(
   524	    request: RenderRequest,
   525	    *,
   526	    workspace: Path,
   527	) -> RenderResult:
   528	    report = support(request, workspace=workspace)
   529	    if not report.supported:
   530	        raise_unsupported_error(
   531	            backend=BACKEND_ID,
   532	            message="FFmpeg does not support this render request",
   533	            recovery_command="resolve the reported support reasons and retry",
   534	            details={"reasons": report.reasons, "features": report.features},
   535	        )
   536	
   537	    ownership = AudioOwnership(str(report.features["audio_ownership"]))
   538	    timeline_path = _input_path(request.timeline_path, workspace)
   539	    if request.assets_registry_path is None:
   540	        raise ValueError("rendering.ffmpeg requires an assets registry")
   541	    assets_path = _input_path(request.assets_registry_path, workspace)
   542	    specialization_spec: audio_reactive_colour.AudioReactiveColourSpec | None = None
   543	    if report.features.get("audio_reactive_colour") is True:
   544	        timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   545	        registry = timeline.load_registry(assets_path)
   546	        specialization_spec = audio_reactive_colour.match_and_validate(
   547	            timeline_data,
   548	            registry,
   549	            assets_path,
   550	        )
   551	        if specialization_spec is None:
   552	            raise RuntimeError(
   553	                "audio-reactive support evidence did not produce a specialization spec"
   554	            )
   555	
   556	    outputs_dir = workspace / "outputs"
   557	    output_path = outputs_dir / request.output_name
   558	    outputs_dir.mkdir(parents=True, exist_ok=True)
   559	    output_path.unlink(missing_ok=True)
   560	    try:
   561	        if specialization_spec is not None:
   562	            audio_reactive_colour.render(specialization_spec, output_path)
   563	        else:
   564	            subprocess.run(build_render_command(request, workspace), check=True)
   565	        try:
   566	            probe = ffprobe_metadata_strict(output_path)
   567	            probed_profile = _profile_from_probe(probe, ownership)
   568	        except (MediaProbeError, RuntimeError) as exc:
   569	            raise_invalid_artifact_error(
   570	                backend=BACKEND_ID,
   571	                message=f"FFmpeg output could not be validated: {exc}",
   572	                recovery_command=(
   573	                    "rerun rendering.ffmpeg in a fresh invocation workspace"
   574	                ),
   575	                details={"error_type": type(exc).__name__},
   576	            )
   577	        declared_profile = request.profile or probed_profile
   578	        duration_frames = _duration_frames(probe, declared_profile)
   579	        provenance_v1 = remotion_backend._render_provenance_payload(
   580	            output_path,
   581	            engine="ffmpeg",
   582	            timeline_path=timeline_path,
   583	            assets_path=assets_path,
   584	            project_dir=REPO_ROOT / "remotion",
   585	            composition_id="TimelineComposition",
   586	            theme_path=None,
   587	            active_theme=None,
   588	            registry_state=remotion_backend._effective_registry_state(None),
   589	            stage_summary={"root": None, "effects": []},
   590	        )
   591	        fragment: dict[str, Any] = {
   592	            "renderer": "ffmpeg",
   593	            "renderer_version": BACKEND_VERSION,
   594	            "support_evidence": report.features,
   595	            "legacy_v1": provenance_v1,
   596	        }
   597	        if specialization_spec is not None:
   598	            markers = [
   599	                {
   600	                    "frame": event.frame,
   601	                    "color": event.color,
   602	                    "id": event.event_id,
   603	                }
   604	                for event in specialization_spec.events
   605	            ]
   606	            specialization_fragment = {
   607	                "id": audio_reactive_colour.ADAPTER_ID,
   608	                "markers": markers,
   609	                "event_count": len(specialization_spec.events),
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

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '400,540p' && nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '220,290p;440,480p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   400	    if not isinstance(file_value, str) or not file_value:
   401	        raise ValueError(f"Asset {asset_id!r} has no local source file")
   402	    path = Path(file_value).expanduser()
   403	    if not path.is_absolute():
   404	        path = (assets_path.parent / path).resolve()
   405	    else:
   406	        path = path.resolve()
   407	    if not path.is_file():
   408	        raise FileNotFoundError(f"Asset {asset_id!r} source is missing: {path}")
   409	    return path
   410	
   411	
   412	def _probe_duration(probe: MediaProbe) -> float | None:
   413	    if probe.duration_seconds is not None:
   414	        return float(probe.duration_seconds)
   415	    if probe.duration_rational is not None:
   416	        numerator, denominator = probe.duration_rational
   417	        return numerator / denominator
   418	    return None
   419	
   420	
   421	def _requested_ownership(
   422	    request: RenderRequest,
   423	    *,
   424	    has_audio_clips: bool,
   425	) -> tuple[AudioOwnership, list[str]]:
   426	    natural = AudioOwnership.RENDERED if has_audio_clips else AudioOwnership.NONE
   427	    ownership = natural
   428	    reasons: list[str] = []
   429	    if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
   430	        ownership = AudioOwnership.PASSTHROUGH
   431	    elif request.audio is not None and request.audio is not natural:
   432	        reasons.append(
   433	            f"audio={request.audio.value!r} is incompatible with timeline audio ownership {natural.value!r}"
   434	        )
   435	    if request.profile is not None and request.profile.has_audio != (
   436	        ownership is AudioOwnership.RENDERED
   437	    ):
   438	        reasons.append(
   439	            "requested profile audio fields do not match rendering.ffmpeg audio ownership"
   440	        )
   441	    return ownership, reasons
   442	
   443	
   444	def _whole_media_optimization(
   445	    timeline_data: Mapping[str, Any],
   446	    assets: Mapping[str, Any],
   447	    probes: Mapping[str, MediaProbe],
   448	) -> bool:
   449	    tracks = {
   450	        track.get("id"): track
   451	        for track in timeline_data.get("tracks", [])
   452	        if isinstance(track, Mapping)
   453	    }
   454	    visual = [
   455	        clip
   456	        for clip in timeline_data.get("clips", [])
   457	        if isinstance(clip, Mapping)
   458	        and clip.get("clipType") == "media"
   459	        and tracks.get(clip.get("track"), {}).get("kind") == "visual"
   460	    ]
   461	    table = _assets_table(assets)
   462	    if len(visual) != 1 or table is None:
   463	        return False
   464	    clip = visual[0]
   465	    entry = table.get(clip.get("asset"))
   466	    if not isinstance(entry, Mapping):
   467	        return False
   468	    media_probe = probes.get(str(clip.get("asset")))
   469	    if media_probe is None or not media_probe.has_video_stream:
   470	        return False
   471	    try:
   472	        bounds = _clip_range(clip)
   473	        width, height, fps = _canvas(timeline_data)
   474	        duration = _number(entry.get("duration"), "asset duration")
   475	        source_fps = _number(entry.get("fps"), "asset fps")
   476	    except ValueError:
   477	        return False
   478	    probed_duration = _probe_duration(media_probe)
   479	    probed_fps = media_probe.fps
   480	    if probed_fps is None and media_probe.fps_rational is not None:
   481	        numerator, denominator = media_probe.fps_rational
   482	        probed_fps = numerator / denominator
   483	    # Frame-accurate tolerance: at most ONE frame of drift is acceptable
   484	    # (half a frame each way), so extra trailing frames at high FPS cannot
   485	    # slip through a coarse 50 ms window.
   486	    frame_tolerance = 0.5 / fps if fps > 0 else 0.0
   487	    return (
   488	        bounds.at == 0
   489	        and bounds.source_from == 0
   490	        and abs(bounds.duration - duration) < frame_tolerance
   491	        and entry.get("resolution") == f"{width}x{height}"
   492	        and abs(source_fps - fps) < 1e-6
   493	        and probed_duration is not None
   494	        and abs(bounds.duration - probed_duration) < frame_tolerance
   495	        and media_probe.width == width
   496	        and media_probe.height == height
   497	        and probed_fps is not None
   498	        and abs(probed_fps - fps) < 1e-6
   499	        and (media_probe.video_codec or "") == "h264"
   500	        and (media_probe.pixel_format or "") == "yuv420p"
   501	        and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
   502	    )
   503	
   504	
   505	def _probe_time_base_matches(
   506	    probe: MediaProbe, expected: tuple[int, int]
   507	) -> bool:
   508	    """The probed stream time base must equal the canonical MP4 timescale."""
   509	    if probe.time_base is None:
   510	        return False
   511	    return Fraction(*probe.time_base) == Fraction(*expected)
   512	
   513	
   514	def _profile_support_reasons(
   515	    request: RenderRequest, timeline_data: Mapping[str, Any]
   516	) -> list[str]:
   517	    """Fail closed when the requested profile deviates from what the FFmpeg
   518	    backend actually produces (canvas dims/fps, codecs, pixel format, and
   519	    canonical audio rate/layout)."""
   520	    profile = request.profile
   521	    if profile is None:
   522	        return []
   523	    reasons: list[str] = []
   524	    try:
   525	        width, height, fps = _canvas(timeline_data)
   526	    except ValueError:
   527	        return reasons  # canvas failure already reported elsewhere
   528	    checks = (
   529	        ("width", profile.width, width),
   530	        ("height", profile.height, height),
   531	        ("fps", profile.fps_rational, (fps, 1)),
   532	        ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
   533	        ("container", profile.container, "mp4"),
   534	        ("video_codec", profile.video_codec, "h264"),
   535	        ("pixel_format", profile.pixel_format, "yuv420p"),
   536	    )
   537	    for field, requested, produced in checks:
   538	        if requested is None:
   539	            continue
   540	        if field in ("fps", "time_base"):
   220	    if len(video_clips) == 1:
   221	        clip = video_clips[0]
   222	        asset_key = str(clip["asset"])
   223	        entry = registry["assets"][asset_key]
   224	        source_duration = entry.get("duration")
   225	        source_resolution = entry.get("resolution")
   226	        source_fps = entry.get("fps")
   227	        start = float(clip.get("from", 0) or 0)
   228	        end = float(clip.get("to", start) or start)
   229	        at = float(clip.get("at", 0) or 0)
   230	        full_duration = (
   231	            isinstance(source_duration, (int, float))
   232	            and abs((end - start) - float(source_duration)) < 0.05
   233	        )
   234	        same_resolution = source_resolution == f"{width}x{height}"
   235	        same_fps = (
   236	            isinstance(source_fps, (int, float))
   237	            and not isinstance(source_fps, bool)
   238	            and math.isfinite(float(source_fps))
   239	            and abs(float(source_fps) - fps) < 1e-6
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
