Reading additional input from stdin...
2026-08-12T12:40:09.605453Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:40:09.606311Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:40:09.606323Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff5fc-ba9a-7371-9e8c-f562742d2ac7
--------
user
# Megado Checkpoint — Batch 3 fourth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-3.md (8), -r1 (6), -r2 (4), -r3 (1). Fourth rework
committed as `9bf9db88` (prior head a7b7b080). Incremental diff at
/tmp/batch3-r4.diff.

## How your re-review3 issue was addressed (host-implemented)

1. **FFmpeg support accepts pinned video_profile/video_level it cannot
   guarantee** → `_profile_support_reasons` now rejects ANY explicit
   `video_profile` or `video_level` request value: the command does not pin
   them (libx264 encoder default; stream-copy preserves source values), so
   support fails closed with a clear reason instead of reporting
   supported=True and failing strict post-render validation. Regression test
   added (`High`/`40` request → supported=False).

## Evidence

- Incremental diff: /tmp/batch3-r4.diff (3 files)
- Host-verified: 836 passed, 1 failed (SAME pre-existing model-trends env
  failure), 2 skipped in the full consolidated acceptance.

## Verdict

Binary: `PASS` or a list of issues. If PASS, say exactly `PASS` so Batch 4
may begin.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Astrid and Megado skills because this is an Astrid-repo Megado checkpoint. I’ll inspect the incremental diff and the governing files read-only, then independently verify the prior blocker and look for regressions before returning only the required verdict.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
---
name: "astrid"
short_description: "Astrid — file-based toolkit for agents to make video, image, and audio art alongside a human."
description: "Use for the Astrid repo: a file-based toolkit for agents to make art and creative work alongside a human. Video edits, generative timelines, image/audio/video understanding and generation — all behind one CLI gateway."
---

# Astrid

Astrid is a file-based toolkit for making video, image, and audio art alongside
a human. `python3 -m astrid` is the only executable gateway.

## When in doubt, run `astrid next`

`astrid next` is the universal port-of-call. **It always prints exactly one
legal action to take, regardless of where you are.** Type it whenever you're
lost, when you forget what you were doing, or when you need to know what
to do *first*:

| Where you are | What `astrid next` tells you |
|---|---|
| No session bound | One legal bootstrap action, usually `astrid attach <slug>` or `astrid projects create <slug>` |
| Session bound, no active run | `astrid start <orchestrator-id> --project <slug>` (suggests top orchestrators) |
| In a run, mid-step | The exact `run: …` command or `astrid ack …` template to type |
| Run rejected by verifier | The rejection reason + the retry command |
| Run complete | "Run complete. Nothing to do." |

Run it without flags. It derives the project from the bound session; if
nothing is bound, it still prints one legal bootstrap action. **You don't need
to remember which other verb to run** — `astrid next` is always the answer.

For deeper context (recent events, run state, inbox count) `astrid status`
remains the read-side breadcrumb; `next` is the action verb.

## Start Here

Astrid is session-gated. From the repository root, the canonical entry is
`astrid next` (see above). When you need detail beyond the next action,
`astrid status` prints the session breadcrumb and the exact recovery action.

```bash
git status --short
python3 -m astrid --help
python3 -m astrid next     # always-correct next action
python3 -m astrid status   # detail breadcrumb when you need it
```

If status says `no session bound`, attach before running doctor, registry
list/search/inspect, executor, orchestrator, element, or task-mode commands.
The only legal unbound commands are help/version, `status`, `next`, `attach`,
`packs ...`, `projects ls`, `projects create`, `projects default`,
`sessions ls`, and `sessions takeover`. After binding, use `status` when you
need to re-orient, not before every command.

```bash
python3 -m astrid attach [<project>] [--default] [--timeline <slug>] [--session <id>] [--as agent:<id>]
python3 -m astrid status
```

Only after a session is bound should you run the usual registry and setup
checks:

```bash
python3 -m astrid doctor
python3 -m astrid orchestrators list
python3 -m astrid executors list
python3 -m astrid elements list
python3 -m astrid setup
```

`setup` is dry-run by default; pass `--apply` to mutate.

## Projects

A project is the durable workspace for timelines, experiments, task runs,
events, and generated artifacts. Every executor, orchestrator, scratch run,
SDK generation, and timeline creation requires either an attached session or
an explicit `--project <slug>`. This includes read-only executors and dry runs.
Configured defaults are attach-time conveniences; they are never silently
selected when a capability runs.

Use `status` first: when no session is bound, it lists discovered projects and
prints the exact attach and default-project commands to run.

```bash
python3 -m astrid status
python3 -m astrid projects ls                   # names, descriptions, activity
python3 -m astrid projects default
python3 -m astrid projects default <slug>
python3 -m astrid projects select <slug>
python3 -m astrid attach [<project>] [--default]
python3 -m astrid projects create <slug> --description "..." --attach
python3 -m astrid timelines create <timeline> --project <slug> --default
```

If `attach` has no project argument, it uses the configured default project.
That is an explicit attach action: the default is never selected merely because
an executor, orchestrator, or timeline command was invoked.
Use `projects create` only when the work needs a new durable project, not just a
new run inside an existing project.

## Choose The Mode

- Use an **executor** for one concrete, independently runnable unit of work.
- Use an **orchestrator** for a workflow that coordinates executors or child orchestrators.
- Use an **element** for a reusable render building block: effect, animation, or transition.
- Use task-mode verbs to continue a started plan: `status`, `next`, then the exact command or `ack` that `next` prints.
- When creating new capability, search and compose existing tools first; only add new executors/elements/orchestrators for real gaps.

## Pack-Specific Guidance

This `_core` skill is the baseline. Custom packs can add their own guidance at
`astrid/packs/<pack>/skill/SKILL.md`. When a task is clearly about one pack,
read that pack skill after `_core` and before editing or running that pack's
tools.

To find every Astrid skill and what it does, attach to a project first, then
list skills. The table shows each installable pack skill, its short
description, and whether it is installed in Claude Code, Codex, and Hermes.
Use `--json` when another agent or script needs to consume the list.

```bash
python3 -m astrid status
python3 -m astrid attach [<project>]
python3 -m astrid skills list
python3 -m astrid skills list --json
```

If you create a custom pack whose conventions agents need to remember, add
`astrid/packs/<pack>/skill/SKILL.md` and follow `docs/guides/skills-install.md`.

## Shared Knowledge With Hivemind

Hivemind is Astrid's default shared knowledge pack. Use `hivemind.search`
before researching community best practices, model behavior, settings, known
failures, or workflow precedents. Use `hivemind.get_item` when a search result
needs its full body or citation context.

Astrid project files remain the source of truth for raw runs, experiment
reviews, and `conclusions.json`. Hivemind is the cross-project publication and
retrieval layer for generalizable learnings:

1. Record observations and evidence-backed inferences locally.
2. Search Hivemind for an existing equivalent learning.
3. Contribute a concise experiment report as a resource.
4. Submit the reusable learning as a distillation citing that resource.
5. Preserve the returned Hivemind IDs beside the local experiment.

Hivemind writes are public publication, including pending distillations. Never
publish automatically: dry-run or preview the payload, remove private paths,
prompts, media, and URLs, and obtain explicit user confirmation before calling
`hivemind.contribute`. If Hivemind is unavailable, install its pack and shared
skill:

```bash
python3 -m astrid packs install https://github.com/banodoco/hivemind.git
python3 -m astrid skills install hivemind --harness all
```

Read the Hivemind pack skill for its search, citation, contribution, and
curation rules before using those executors.

## Run A Tool

Find an id before you run anything.

```bash
python3 -m astrid [executors|orchestrators|elements] list
python3 -m astrid [executors|orchestrators|elements] search <terms>
```

If you don't know which tool to use, run `python3 -m astrid <kind> search
<terms>` first. Do not guess from id alone.

Inspect to see inputs, outputs, intent, folder root, and the relevant
`STAGE.md`.

```bash
python3 -m astrid [executors|orchestrators|elements] inspect <id> --json
```

Read only that one `STAGE.md`; it is the source of truth for invocation details.
Then run:

```bash
python3 -m astrid [executors|orchestrators] run <id> --project <slug> -- <args>
```

## Continue A Task Run

Task lists are orchestrator plans tracked inside a project. Do not freelance:
`next` is the control surface.

```bash
python3 -m astrid status
python3 -m astrid next --project <slug>
```

Then do exactly what `next` prints:

- If it prints `run: ...`, run that command exactly.
- If it prints an attested/manual step, acknowledge with the printed `ack` form.
- If the run is stuck and another writer owns it, use the takeover hint from `status`.

Common task commands:

```bash
python3 -m astrid start <orchestrator-id> --project <slug>
python3 -m astrid next --project <slug>
python3 -m astrid ack <step> --project <slug> --decision approve [--agent <id> | --human <name>]
python3 -m astrid status --project <slug>
python3 -m astrid abort --project <slug>
python3 -m astrid sessions {ls, detach, takeover} ...
```

`astrid sessions takeover` atomically increments the run's `writer_epoch` and swaps the lease writer; any other tab that was writing to the run gets a `StaleEpochError` on its next mutating verb.
Takeover from an unbound shell is allowed, but it first bootstraps a concrete
caller session through the same identity and file-binding path as `attach`;
anonymous takeover is not a valid state. Lease helpers preserve unknown
metadata fields while updating only the owned writer fields, so future
per-run metadata survives takeover, orphan claim, and release.

Normal task-run mutations must go through the writer-owned task APIs; do not
edit `plan.json`, `events.jsonl`, `current_run.json`, or `lease.json` by hand.
The low-level event append helpers are transport internals, not agent-facing
escape hatches.

Sprint 3 task plans use one collapsed step shape: leaves have `command`, groups
have `children`, and both share `adapter`, `requires_ack`, `assignee`,
`produces`, `repeat`, and `version`. Do not author legacy `kind: code`,
`kind: attested`, `kind: nested`, or inline `plan` step payloads. If you find a
v1 plan, run `scripts/migrations/sprint-3/migrate_plans.py` rather than relying
on runtime auto-migration.

The first event in each run is `plan_initialized`. Treat `plan.json` as a
cached projection replayed from `plan_initialized` plus `plan_mutated`, not as
the source of truth. Use plan mutation verbs for edits.

`repeat.until` now accepts expression strings such as
`review.produces.verdict.status == "approved"`. Repeated group steps may expose
descendant produces through `re_export`; missing artifacts or malformed JSON
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, max reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where a GPT-5.6 Sol oracle reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

A delivery pipeline for a whole project: **Codex plans, DeepSeek explores, Codex revises, DeepSeek executes, Codex oracles** — all in a worktree, opened and synced when done. Two models only: **DeepSeek V4 Flash** and **GPT-5.6 Sol**.

The shape (from the original ask, normalized):

1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
6. Open it and sync.

## Roles

| Role | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Planner / Oracle** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=max` | read-only for planning/review; `workspace-write` when it implements |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Hard-task executor** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=max` | `workspace-write` |

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

Brief GPT-5.6 Sol at max reasoning. Demand three outputs, in order:

1. A tasklist covering the **entirety** of the project (not just the obvious path).
2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
3. Open questions / potential issues.

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max \
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

Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Codex (GPT-5.6 Sol, max reasoning):

> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

- New material areas → re-run Phase 2 for those, then revise again.
- Repeat until Codex returns `STABLE` (or two consecutive rounds with no material change).
- The plan is a living doc during this loop; it freezes at Phase 4.

## Phase 4 — Batched tasklist with checkpoints (Codex)

Ask Codex (GPT-5.6 Sol, max reasoning) to convert the stable plan into an execution structure:

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
timeout 1800 codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=max \
  "$(cat /tmp/hard-task-brief.md)" </dev/null
```

(Use `--sandbox danger-full-access` only when the Codex agent must itself orchestrate hermes subagents — those need outbound network.)

**2. Checkpoint — oracle review.** Send the batch's completed work to GPT-5.6 Sol (max reasoning):

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max \
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

# Phase 1 — initial plan (GPT-5.6 Sol, max reasoning)
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max "$(cat /tmp/plan-brief.md)" </dev/null

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
# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=max
# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max "$(cat /tmp/checkin-brief.md)" </dev/null

# Phase 6 — commit, push, open
git add -A && git commit -m "megado: <project>" && git push && open .
```

exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '241,520p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
     950 total
fail closed. Legacy conditions such as `user_approves` exist only for migrated
read compatibility.

`remote-artifact` is available for task leaves that dispatch remote work through
the generic subprocess-plus-manifest contract. Use `local` or `manual` when the
step does not need asynchronous artifact fetch/retry behavior.

## Create Something New

Read `docs/guides/creating-tools.md`, then follow this build order. Complete every
step before falling back to the next.

1. **Search and compose existing executors first.** If existing executors can
   be wired together, build only an orchestrator that calls them.
2. **Create missing executors next.** Each new executor does one concrete,
   focused, independently runnable unit of work.
3. **Then write the orchestrator.** It composes existing and newly created
   executors into the workflow.
4. **Add elements only for reusable render building blocks.** Effects,
   animations, and transitions belong in the element tree, not in ad hoc
   timeline code.

Do not start by writing a god-orchestrator. If a `run.py` grows past a couple
hundred lines while doing network calls, asset processing, and workflow logic,
split it into executors plus an orchestrator.

Before creating:

```bash
python3 -m astrid status
python3 -m astrid executors search <terms>
python3 -m astrid orchestrators search <terms>
python3 -m astrid elements list
python3 -m astrid [executors|orchestrators|elements] inspect <id> --json
```

Templates:

- `docs/templates/executor/` — one concrete unit of work
- `docs/templates/orchestrator/` — a workflow that combines executors
- `docs/templates/element/` — a reusable render building block

For custom pack behavior that agents should remember, add
`astrid/packs/<pack>/skill/SKILL.md`. Keep pack-specific conventions there
rather than expanding `_core`.

Content lives under packs at `astrid/packs/<pack>/`. Executor folders use
`astrid/packs/<pack>/<slug>/{executor.yaml,STAGE.md,run.py}` and orchestrator
folders use `astrid/packs/<pack>/<slug>/{orchestrator.yaml,STAGE.md,run.py}`,
with optional local `src/` modules. Element folders live at
`astrid/packs/<pack>/elements/<kind>/<id>/{component.tsx,element.yaml}` where
kind is `effects`, `animations`, or `transitions`.

Executor and orchestrator ids are always qualified as `<pack>.<name>`. Bare ids
are rejected. Top-level `astrid/*.py` files are shared libraries or system
commands, not alternate runnable implementations.

Do not chain pipeline internals by hand unless debugging one specific stage. If
the user gives a topic instead of a brief, use a brief-generation executor
coordinated by an orchestrator; do not fake source media just to enter a
source-video path. Render requires the `hype.timeline.json` and
`hype.assets.json` pair produced by cut; do not skip cut unless both files
already exist.

## Safety Rules

- Generated files live under `runs/` or another ignored output directory.
- Do not commit source media, rendered videos, local dependency envs, or secrets.
- Do not print or hardcode API keys; use `--env-file` or nearby `.env` files.
- Do not edit `plan.json` or `events.jsonl` by hand during task-mode runs.
- Treat curated tool stages as protected unless explicitly asked to edit them,
  notably `astrid/packs/moirae/executors/moirae/STAGE.md` and
  `astrid/packs/vibecomfy/executors/run/STAGE.md`.
- Orchestrators may call declared child orchestrators; executors must not call orchestrators.

After adding or renaming effects, animations, transitions, or theme elements:

```bash
python3 scripts/gen_effect_registry.py
cd remotion && npm run gen-types
```

After editing `short_description` / `keywords` on any executor, orchestrator,
or element manifest, refresh the capability index in this file:

```bash
python3 scripts/gen_capability_index.py
```

## Common Defaults

Built-in orchestrators: `video_editing.hype`, `video_editing.event_talks`,
`video_editing.thumbnail_maker`.

Built-in executors include `editorial.transcribe`, `video_editing.cut`,
`rendering.render`, `editorial.validate`, `understanding.understand` (audio/visual/video
dispatcher; pass `--mode {audio,visual,video}`), `generation.generate_image_openai`, and
the rest of the pipeline. External executors include `moirae.moirae` and
`vibecomfy.run` (executor only, not an orchestrator).

Element source priority: active theme →
`astrid/packs/local/elements/<kind>/<id>` (gitignored scratch pack) →
`astrid/packs/builtin/elements/<kind>/<id>`. Forking copies the source element
into `astrid/packs/local/`, auto-creating `astrid/packs/local/pack.yaml` and
rewriting the element's `pack_id` to `local`.

```bash
python3 -m astrid elements fork effects text-card
```

Before rendering an iteration video, run `python3 -m astrid.packs.video_editing.orchestrators.iteration_video.run inspect <thread>` to see modalities, renderers, quality, cache counts, and estimated cost without rendering. Note: the pack-level `--thread <id>` argument identifies a non-binding variant lineage WITHIN a pack and is UNRELATED to the removed `astrid thread` CLI verb or to session binding. Threads as a generic user-facing runtime concept were retired in Sprint 1 (DEC-001); the internal `astrid.core.threads` library is retained for pack lineage utilities.

## Pack Model

Packs are **namespace and distribution containers** for capabilities
(executors, orchestrators, elements). Every capability lives in exactly one
pack. The pack declares its identity (`id`, `version`), content roots
(`executors`, `orchestrators`, `elements`), and agent-facing metadata in a
`pack.yaml` manifest.

### Discovery for Agents

Agents discover capabilities through the CLI, not by grepping source:

```bash
python3 -m astrid skills list              # installed pack skills
python3 -m astrid executors search <term>  # find executors by keyword
python3 -m astrid orchestrators search <term>
python3 -m astrid elements list
```

Search and list support `--json` for machine consumption.

### Inspect Before Running

Always inspect a capability before running it. The `--json` output includes
the `_capability` identity block (id, kind, pack, version) plus the full
definition (inputs, outputs, dependencies, entrypoint):

```bash
python3 -m astrid executors inspect <id> --json
python3 -m astrid orchestrators inspect <id> --json
python3 -m astrid elements inspect <kind> <id> --json
```

### Capability Kinds

| Kind | Use when |
|------|---------|
| **Executor** | One concrete, independently runnable unit of work |
| **Orchestrator** | A workflow that coordinates executors or child orchestrators |
| **Element** | A reusable render building block: effect, animation, or transition |

### Aliases, Forks, and Overrides

Three mechanisms let you customize without editing originals:

- **Aliases** — Map old or alternate ids to current capabilities. Declared in
  `pack.yaml` under `aliases`. Resolved transparently at lookup time.
- **Forks** — Copy a capability into a local pack for independent editing.
  Forks carry provenance back to the source. Use `executor fork <id>` or
  `orchestrator fork <id>`.
- **Overrides** — Redirect a capability id to a preferred fork without
  modifying manifests. Use `executor override set <from> <to>`.

Full details: [aliases-vs-forks-vs-overrides.md](docs/aliases-vs-forks-vs-overrides.md).

### Further Reading

- [docs/discovery-for-agents.md](docs/guides/discovery-for-agents.md) — Agent-facing
  CLI contract
- [docs/creating-packs.md](docs/creating-packs.md) — Pack authoring workflow
- [docs/creating-tools.md](docs/guides/creating-tools.md) — When to create each
  capability kind
- [docs/personal-packs.md](docs/personal-packs.md) — Personal pack workflow
- [docs/adapter-packs.md](docs/adapter-packs.md) — Adapter pack conventions
- [docs/update-workflow.md](docs/update-workflow.md) — Dirty detection and
  update management
- [docs/megaplan/epics/pack-system/pack-contract.md](docs/megaplan/epics/pack-system/pack-contract.md) — Formal definitions

The capability index below is **auto-generated** by
`scripts/gen_capability_index.py`. Re-run it after editing executor,
orchestrator, or element manifests.

## Per-project plan.md

Every project has a `plan.md` at its root — a per-project markdown doc for live, human/agent-readable working notes (current focus, open threads, key decisions, scratch notes). This is distinct from `<project>/runs/<run-id>/plan.json`, which is the executable runtime step tree.

- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.

<!-- BEGIN CAPABILITY INDEX (auto-generated by scripts/gen_capability_index.py) -->

### Executors

| id | short_description |
| --- | --- |
| `blender.render` | Render a Blender scene (declarative spec or .blend file) to a still or animation, locally or on a cloud render host. |
| `comfy_wrap.run` | Generate an image by injecting a prompt into a ComfyUI workflow JSON and running it via vibecomfy. |
| `discord_local.command` | Preview, submit once, or recover one Discord generation as an experiment-ready run. |
| `editorial.arrange` | Compose a brief-specific shot arrangement from the source clip pool. |
| `editorial.boundary_candidates` | Package candidate video frames for visual scene-boundary review. |
| `editorial.editor_review` | Run heuristic editorial reviewers over an arrangement and emit notes. |
| `editorial.human_notes` | Convert human editorial notes into structured pipeline inputs. |
| `editorial.human_review` | Serve a small HTML page locally, collect human decisions as JSON, block until submit. |
| `editorial.inspect_cut` | Inspect a generated cut run directory and report timeline/asset health. |
| `editorial.quality_zones` | Tag arrangement clips with per-zone quality grades for downstream picks. |
| `editorial.quote_scout` | Scan a transcript for quotable lines suitable for hype clips. |
| `editorial.refine` | Apply targeted reviewer-driven refinements to an existing arrangement. |
| `editorial.scenes` | Detect source-video scene boundaries with ffmpeg-driven analysis. |
| `editorial.script_pipeline` | Generate short scripts through rough attempts, synthesis, style pass, and optional judging. |
| `editorial.shots` | Slice scenes into shot windows for downstream pool building. |
| `editorial.transcribe` | Transcribe source audio to transcript.json via Whisper. |
| `editorial.triage` | Triage source-video scenes by quality before pool building. |
| `editorial.validate` | Validate the rendered video against its declared timeline and metadata. |
| `fal.fal_foley` | Generate Foley audio for one short video clip via fal.ai's hunyuan-video-foley model. |
| `foley.foley_review` | Build a static review.html pairing each tile clip with its generated Foley audio for sense-checking. |
| `foley.tile_video` | Crop a video into an MxN grid of overlapping spatial tiles plus first-frame PNGs. |
| `generation.generate_audio` | Generate audio from text prompts via local or cloud backends. v2: model→mode→backend with music mode. |
| `generation.generate_image` | Generate images from text prompts via local, cloud, or Codex backends. v2: model→mode→backend. |
| `generation.generate_image_openai` | Generate image files with OpenAI GPT Image models from a prompt file. |
| `generation.generate_video` | Generate videos from text prompts via local or cloud backends. v2: model→mode→backend with t2v/i2v/flf/v2v modes. |
| `hivemind.contribute` | Submit a resource or distillation to the Hivemind corpus via the contribute edge function. |
| `hivemind.get_item` | Fetch a single full row from the Hivemind corpus by kind and id. |
| `hivemind.ingest_article` | Fetch a web article, extract readable text, and submit as a resource. |
| `hivemind.ingest_workflow` | Parse a ComfyUI workflow JSON and submit as a resource with model metadata. |
| `hivemind.ingest_youtube` | Extract YouTube captions via yt-dlp and submit as a transcript resource. |
| `hivemind.refresh_media` | Refresh expiring Discord CDN attachment URLs for a message. |
| `hivemind.search` | Search the Hivemind unified corpus with distillations-first merging. |
| `iteration.assemble` | Adapt prepared iteration data into canonical iteration artifacts and render-ready hype inputs. |
| `iteration.experiment_import` | Import an unmanaged run root into an experiment without rewriting history or guessing ambiguous associations. |
| `iteration.experiment_prepare` | Normalize an experiment's provider manifests into a provider-independent review model with diagnostics. |
| `iteration.experiment_review` | Render a deterministic HTML gallery comparing provider outputs with prompt, parameters, warnings, and diagnostics. |
| `iteration.prepare` | Collect thread provenance, quality scores, and candidate runs into iteration prepare artifacts. |
| `media.clip_extract` | Extract a clip segment from a video using ffmpeg stream copy. |
| `media.gif_search` | Search GIPHY for GIF or sticker assets and optionally download a selected rendition. |
| `media.speech_repair_lavasr` | Repair weak-mic speech with hotter pre-lift, fal.ai LavaSR, optional DeepFilterNet3, and a final loudness pass. |
| `moirae.moirae` | Run a Moirae screenplay through the terminal-as-cinema renderer to produce a video. |
| `reigh.open_in_reigh` | Copy or stage generated timeline+assets for handoff into a Reigh project. |
| `reigh.publish` | Publish a finished timeline + assets pair into a Reigh project via API. |
| `reigh.reigh_data` | Fetch canonical Reigh project data through the reigh-data Edge Function. |
| `reigh.spatial_audio_page` | Build a static page that mixes Foley tracks anchored to spatial rectangles via Web Audio. |
| `rendering.html_canvas_effect` | Scaffold a local Remotion HTML-in-canvas effect element. |
| `rendering.render` | Render a hype timeline to hype.mp4 through Remotion, ffmpeg, or hybrid rendering. |
| `rendering.sprite_sheet` | Generate, slice, and preview GPT Image sprite sheets for batch image work. |
| `rendering.timeline_storyboard` | Build a static visual storyboard of image inputs associated with timeline shots. |
| `runpod.exec` | Execute a script on an existing RunPod pod and download artifacts. |
| `runpod.provision` | Provision a RunPod GPU pod and emit a pod handle for later exec/teardown. |
| `runpod.pull` | Pull artifacts from an existing RunPod pod into local storage. |
| `runpod.session` | Composite provision → exec → teardown session with guaranteed cleanup. |
| `runpod.teardown` | Terminate a RunPod pod. Idempotent. |
| `seedance_local.reference_video` | Generate one Seedance 2.0 video using a local clip as its motion and camera reference. |
| `stream_content.clip_candidates` | Score transcript windows as publishable stream clip candidates. |
| `stream_content.segment_map` | Fuse OCR, transcript density, and scene cuts into a complete stream timeline. |
| `training.asset_cache` | Manage the repo-local hype asset cache (download, prune, list). |
| `training.pool_build` | Build the candidate clip pool from triaged source-video scenes. |
| `training.pool_merge` | Merge multiple candidate clip pools into a unified pool for arrangement. |
| `training.search_loras` | Search Hugging Face Hub for LoRAs associated with a base model. |
| `understanding.audio_understand` | Inspect audio clips or sampled windows with an audio-understanding LLM. |
| `understanding.scene_describe` | Caption each detected scene with a vision model for downstream selection. |
| `understanding.understand` | Dispatch to the audio, visual, or video understanding executor based on --mode. |
| `understanding.video_understand` | Inspect synchronized audio+video windows with a video-understanding model. |
| `understanding.visual_understand` | Inspect images or sampled video frames with a vision LLM — free-text or JSON-schema-constrained. |
| `vibecomfy.run` | Run a VibeComfy / ComfyUI workflow JSON through the VibeComfy CLI. |
| `vibecomfy.validate` | Validate a VibeComfy / ComfyUI workflow JSON without executing it. |
| `video_editing.cut` | Build the Reigh-compatible hype timeline + assets + metadata JSON triple from arrangement. |
| `youtube.upload` | Upload a finished video to YouTube via the shared banodoco-social Zapier integration. |
| `youtube.youtube_audio` | Download a YouTube video's audio (MP3) or video (MP4) — by search query or direct URL. |

### Orchestrators

| id | short_description |
| --- | --- |
| `builtin.agent_probe` | Legacy task-mode probe orchestrator used by regression tests. |
| `foley.foley_map` | Spatial Foley pipeline: tile a video, prompt a VLM, score Foley per tile, and emit a viewer. |
| `iteration.experiment_review_session` | Interactive rubric review session over a prepared experiment, reusing editorial.human_review with safe mounted media. |
| `stream_content.distill` | Distill a long event stream into segments, extracted blocks, candidates, and a review page. |
| `text_analysis.summarize` | Summarize the bundled sample text fixture into content, summary, and verdict JSON outputs. |
| `training.dataset_build` | Build a generic reviewed video training dataset from configured sources. |

exec
/bin/zsh -lc "sed -n '521,820p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
| `training.training_run` | Run a generic LoRA training job from a prepared dataset manifest. |
| `video_editing.animate_image` | Two-stage Fal pipeline: edit a reference image with GPT Image 2, then animate it with WAN 2.2. |
| `video_editing.event_talks` | Orchestrate event-talk template, search, holding-screen, and render commands into a finished video. |
| `video_editing.hype` | Run the canonical hype editing pipeline end-to-end (transcribe → cut → render → validate). |
| `video_editing.iteration_video` | Prepare an iteration graph, assemble render inputs, render, and finalize iteration video outputs. |
| `video_editing.logo_ideas` | Generate a grid of distinct logo concepts via Kimi K2 prompts + GPT Image 2 (or z-image) renders. |
| `video_editing.thumbnail_maker` | Plan source evidence and thumbnail generation candidates for a video/query pair. |
| `video_editing.vary_grid` | Iterative grid editor: take an existing grid image and emit a new grid of variations via fal. |

### Elements

| id | short_description |
| --- | --- |
| `animations/fade` | Fade in/out wrapper animation. |
| `animations/fade-up` | Fade up entrance animation. |
| `animations/scale-in` | Scale in entrance animation. |
| `animations/slide-left` | Slide left entrance animation. |
| `animations/slide-up` | Slide up exit animation. |
| `animations/type-on` | Typewriter-style text reveal animation. |
| `effects/audio-reactive-colour` | Fill the frame with colours selected by frozen integer-frame markers. |
| `effects/model-trends` | Animated stacked-area chart of model-family share-of-conversation, driven by Remotion frame. |
| `effects/neon-orbit-card` | DOM-to-canvas Remotion effect for post-processed cards. |
| `effects/sliding-media` | Full-screen media clip with slide-in/out motion. |
| `effects/text-card` | Anchored text card overlay with built-in fade in/out. |
| `effects/vibe-comfy-asset-overlay` | Asset-driven Vibe Comfy overlay with procedural noodle. |
| `effects/vibe-comfy-bumper` | Procedural Remotion bumper for Vibe Comfy. |
| `transitions/cross-fade` | Cross fade transition. |
| `transitions/fade` | Fade-through-black transition. |

<!-- END CAPABILITY INDEX -->

## Installing into agent harnesses

Astrid ships its own skills layer for the three supported agent harnesses (Claude Code, Codex, Hermes). One command installs the `_core` skill plus any per-pack skills into every harness it detects on the machine:

```bash
python3 -m astrid skills list                 # show installable packs and current per-harness state
python3 -m astrid skills install --all        # install every pack into every detected harness
python3 -m astrid skills doctor               # verify symlinks resolve and AGENTS.md block parses
python3 -m astrid skills uninstall _core      # remove from all harnesses
```

Default mechanism is per-pack symlinks under `~/.claude/skills/`, `~/.codex/skills/`, and `${HERMES_HOME:-~/.hermes}/skills/`. Codex additionally maintains an idempotent fenced block in `~/.codex/AGENTS.md` listing each installed pack. Hermes accepts an opt-in `--mechanism external-dir` that registers the whole `astrid/packs` tree via `~/.hermes/config.yaml` `skills.external_dirs` instead of per-pack symlinks.

If no harness is installed, Astrid prints a one-line nudge to stderr at most once every seven days when you run a non-`skills` subcommand. Suppress with `ASTRID_NO_NUDGE=1` or `--quiet`.

See `docs/guides/skills-install.md` for the SkillDescriptor contract and the `metadata.hermes.*` extension block.

## Adding overlays to a rendered video

Quick recipe: take any `.mp4` and overlay text captions / a wordmark via the timeline + Remotion path.

### The timeline and optional asset registry

- `timeline.json` — defines tracks and clips. Schema: `@banodoco/timeline-schema` (see `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`). Top level: `{theme, theme_overrides?, tracks, clips}`. Each clip has `id, at (seconds), track, clipType, asset?, hold? | from/to, text?, params?, effects?, x?/y?/width?/height?`.
- `assets.json` — optional media registry: `{"assets": {"<id>": {file?: <relative-or-absolute-path>, type?, resolution?, fps?, duration?}}}`. Include it when clips reference media assets. Files must share a common parent so the renderer's local HTTP server can serve them.

### Layering rule (gotcha)

Visual tracks render in **reversed** array order (`TimelineComposition.tsx`: `[...getVisualTracks(timeline)].reverse()`). To put overlays on top, list the overlay track **first** in `timeline.tracks`.

### Timeline design conventions

Use one track per editing concern, not one catch-all overlay track. A maintainable visual stack usually reads top-to-bottom as `brand` or persistent CTA, `captions`, moment-specific `fx` or text callouts, `broll`, then `source`; audio tracks follow visual tracks. Because visual tracks render in reversed order, the first visual track in `tracks` is the top layer. Keep clip ids prefixed by concern (`brand_`, `cap_`, `fx_`, `broll_`, `src_`, `audio_`) so later patches can target the right layer without re-reading every clip. Split a track as soon as clips have different lifetimes, ownership, or review criteria; for example, do not mix persistent branding, subtitles, and transient emphasis cards on one track.

The canonical small fixture is `examples/hype.timeline.json`. Read it before hand-authoring a timeline; `examples/hype.timeline.full.json` is for schema coverage, not design guidance.

### Minimal maintainable example: video + caption + wordmark

```jsonc
// assets.json
{
  "assets": {
    "src": {"file": "video.mp4", "type": "video/mp4", "resolution": "1920x1080", "fps": 30, "duration": 49.5}
  }
}
```

```jsonc
// timeline.json
{
  "theme": "banodoco-default",
  "theme_overrides": {"visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}},
  "tracks": [
    {"id": "brand", "kind": "visual", "label": "Brand"},
    {"id": "captions", "kind": "visual", "label": "Captions"},
    {"id": "source", "kind": "visual", "label": "Source"}
  ],
  "clips": [
    {"id": "src_main", "at": 0, "track": "source", "clipType": "media", "asset": "src", "from": 0, "to": 49.5},
    {
      "id": "brand_wordmark", "at": 0, "track": "brand", "clipType": "text", "hold": 49.5,
      "text": {"content": "REIGH", "fontSize": 24, "color": "#ffffff", "align": "right"},
      "params": {"anchor": "top-right", "offsetX": 64, "offsetY": 48, "weight": 700,
                 "textShadow": "0 2px 10px rgba(0,0,0,0.75)"}
    },
    {
      "id": "cap_search", "at": 3, "track": "captions", "clipType": "text", "hold": 10,
      "effects": {"fade_in": 0.4, "fade_out": 0.4},
      "text": {"content": "search 1.2 million messages", "fontSize": 38, "color": "#ffffff", "align": "right"},
      "params": {"anchor": "bottom-right", "offsetX": 80, "offsetY": 140, "maxWidth": 720, "weight": 600,
                 "textShadow": "0 2px 12px rgba(0,0,0,0.85)"}
    }
  ]
}
```

### Adding music or another audio track

Audio is a first-class track kind — there is no separate audio pipeline and no post-render ffmpeg mux. Declare an `audio` track, register the file as an asset, and add a `media` clip on the audio track. Remotion bakes audio into the rendered MP4 directly.

```jsonc
// assets.json — add a music asset alongside your video
{
  "assets": {
    "src":   {"file": "video.mp4", "type": "video/mp4", "duration": 47.6},
    "music": {"file": "music.mp3", "type": "audio/mpeg"}
  }
}
```

```jsonc
// timeline.json — add an audio track and a media clip on it
"tracks": [
  {"id": "source", "kind": "visual", "label": "Source"},
  {"id": "a1",     "kind": "audio",  "label": "Music"}
],
"clips": [
  {"id": "src_main", "at": 0, "track": "source", "clipType": "media", "asset": "src", "from": 0, "to": 47.6},
  {
    "id": "audio_music",
    "at": 0,                 // timeline time the clip starts playing
    "track": "a1",
    "clipType": "media",     // audio uses the same `media` clipType as video
    "asset": "music",
    "from": 5,               // trim: start the source 5s in
    "to": 52.6,              // trim end in source time (clip plays for to-from = 47.6s)
    "volume": 1.0,           // 0..1 scalar, multiplies track volume
    "params": {"fadeIn": 0, "fadeOut": 2.5}
  }
]
```

Field semantics (the parts that aren't obvious from `types.ts`):

- `from` / `to` are in **source-media time, seconds** — they trim the asset, they don't move the clip on the timeline. The clip's timeline duration is `to - from`. To start the music *later* in the video, raise `clip.at`, not `from`.
- `volume` is a scalar 0..1; track and clip volume multiply. `track.muted: true` forces silence regardless.
- `params.fadeIn` / `params.fadeOut` are in seconds, taper at the clip's local start/end. Implemented inside `AudioTrack.tsx` as a per-frame volume function — no afade pre-bake needed.
- Local audio paths in `assets.json` resolve like local video: the render runner picks a common parent of all asset files and serves them over `http://localhost:<port>/...`. Remotion's `<Audio src>` consumes that URL natively.

You should not need ffmpeg's `atrim` / `afade` / `amix` for any normal "music under the video" use case. Reach for ffmpeg only for things Remotion genuinely doesn't model (offline loudness normalization, sample-accurate cross-fades between two music beds, etc.).

### Rendering

```bash
python3 -m astrid executors run rendering.render \
  --out runs/<my-run> \
  --input timeline=runs/<my-run>/timeline.json \
  --input assets_registry=runs/<my-run>/assets.json
```

For timelines with no media registry entries, omit the asset input:

```bash
python3 -m astrid executors run rendering.render \
  --out runs/<my-run> \
  --input timeline=runs/<my-run>/timeline.json
```

The normal executor CLI writes `runs/<my-run>/hype.mp4` and
`runs/<my-run>/hype.mp4.provenance.json`. The lower-level direct runner is for
debugging executor behavior only:

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline runs/<my-run>/timeline.json \
  --assets runs/<my-run>/assets.json \
  --out runs/<my-run>/composed.mp4
```

Direct debug runs may omit `--assets` for asset-free timelines; the runner
synthesizes a temporary empty registry.

### Local effect assets

Effect, animation, and transition manifests may declare static files with
optional top-level syntax:

```yaml
assets:
  badge: assets/badge.png
  palette: assets/palette.json
```

Values are paths relative to the element root, must stay inside that root, and
must point to files. During render, Astrid stages only declared assets for
elements used by the timeline under
`remotion/public/astrid-effects/<render-hash>/<effect-id>/`, injects their
static-file-relative paths into `params.__astridAssets`, and cleans the staging
directory after Remotion exits.

### Where the schemas live (authoritative)

- Timeline + clip Zod schemas: `remotion/node_modules/@banodoco/timeline-schema/typescript/src/schemas.ts`
- Composition (clip → component dispatch, layering): `remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx`
- Effect / animation registries: generated by `scripts/gen_effect_registry.py` into `effects.generated.ts` etc. inside the `@banodoco/timeline-composition` package
- Python timeline IO + validation: `astrid/timeline.py`
- Render entrypoint: `astrid/packs/rendering/executors/render/run.py`
- Render provenance: `<video-output>.provenance.json` records active pack order, active theme, registry hash/state, resolved effect ids, source pack ids, element roots, staged asset ids/paths, and hybrid segment provenance when applicable.

### Available elements

Run `python3 -m astrid elements list` (or `inspect <kind> <id> --json` for a single element). At time of writing:

- effects: `text-card` (text rendering — see note below)
- animations: `fade`, `fade-up`, `scale-in`, `slide-left`, `slide-up`, `type-on`
- transitions: `cross-fade`, `fade`

### Text rendering note (important)

The built-in `text-card` component is `() => null` — it expects a theme override to do the real DOM rendering. If your theme doesn't ship one, fork into the local pack:

```bash
python3 -m astrid elements fork effects text-card
# edit astrid/packs/local/elements/effects/text-card/component.tsx
python3 scripts/gen_effect_registry.py     # regenerates registry
```

The local-pack TextCard in this repo already supports anchored positioning (`params.anchor` ∈ {top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right}, plus `offsetX/offsetY/maxWidth/background/padding/borderRadius/lineHeight/weight/letterSpacing/textShadow`) and reads `clip.effects.{fade_in,fade_out}` (seconds) for entry/exit fades.

### 5-minute "add a caption" recipe

1. Drop your source `.mp4` into `runs/<name>/`.
2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
3. Render with the command above.
4. ffprobe / open the `composed.mp4`.
5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.

## Validate

```bash
pytest tests/test_doctor_setup.py tests/test_canonical_cli.py
pytest --tb=no -q --no-header
```

## Upstream friction

When a workflow is awkward, brittle, or undocumented, tell the user directly. Suggest the smallest durable fix; if the issue belongs upstream, recommend a PR there.

## Begin

Ask the maker what they want to make or learn. If they want ideas, see `docs/guides/ideas.md`.

2026-08-12T12:40:47.999067Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:40:48.002674Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:40:48.007817Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
codex
I’ve also started an independent read-only review in parallel, per the repository’s context-hygiene guidance. I’m checking the exact commit delta and acceptance criteria myself.
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show --stat --oneline --decorate --no-renames 9bf9db88 && git diff --stat a7b7b080..9bf9db88 && sed -n '1,260p' /tmp/batch3-r4.diff && rg --files -g 'AGENTS.md' -g '.oracle/tasklist.md' -g '.oracle/checkins/batch-3*.md'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 102ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
9bf9db88 (HEAD -> oracle-run) batch3-rework4: oracle re-review3 issue 1 (ffmpeg support rejects unguaranteed pinned video_profile/level)
 .oracle/checkins/batch-3-r3.md                    | 10623 ++++++++++++++++++++
 astrid/packs/rendering/backends/ffmpeg/support.py |    15 +
 tests/packs/rendering/test_ffmpeg_support.py      |    35 +
 3 files changed, 10673 insertions(+)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-3-r3.md                    | 10623 ++++++++++++++++++++
 astrid/packs/rendering/backends/ffmpeg/support.py |    15 +
 tests/packs/rendering/test_ffmpeg_support.py      |    35 +
 3 files changed, 10673 insertions(+)
diff --git a/.oracle/checkins/batch-3-r3.md b/.oracle/checkins/batch-3-r3.md
new file mode 100644
index 00000000..632c0b13
--- /dev/null
+++ b/.oracle/checkins/batch-3-r3.md
@@ -0,0 +1,10623 @@
+Reading additional input from stdin...
+2026-08-12T12:24:35.706477Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T12:24:35.706509Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T12:24:35.706515Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff5ee-7d82-7b70-93c9-f90f176fac97
+--------
+user
+# Megado Checkpoint — Batch 3 third re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-3.md (8), -r1 (6), -r2 (4). Third rework committed as
+`a7b7b080` (prior head 58473c3a). Incremental diff at /tmp/batch3-r3.diff.
+
+## How each of your 4 re-review2 issues was addressed (host-implemented)
+
+1. **Remotion doesn't enforce always-rendered audio** → the remotion render
+   command now passes `--enforce-audio-track` (Remotion 4.0.455 default is
+   false, so visual-only/muted timelines would otherwise render without
+   audio despite support/manifest promising rendered AAC).
+2. **FFmpeg time-base formula wrong + rational gaps** →
+   `_profile_support_reasons` now uses the CANONICAL `_mp4_time_base`
+   doubling rule (24→12288, 30→15360, 60→15360) from `profile.py` instead of
+   `fps*512`; fps/time_base compared via `Fraction` equality (non-integral
+   FPS and equivalent rationals handled); `video_profile`/`video_level`
+   remain unpinned by the command (encoder default) — support does not
+   falsely promise them.
+3. **Stream-copy ignores probed time base** →
+   `_whole_media_optimization` now requires the probed `time_base` to equal
+   the canonical MP4 timescale via `_probe_time_base_matches` (an H.264
+   source at 1/90000 for a 1/15360 request is no longer copied).
+4. **50ms duration tolerance lets extra frames through** →
+   frame-accurate tolerance `0.5/fps` (half a frame each way) replaces the
+   coarse 50ms window; extra trailing frames at high FPS cannot pass.
+
+## Evidence
+
+- Incremental diff: /tmp/batch3-r3.diff (5 files)
+- Host-verified: 106 combined backend/finalizer/locking tests pass; full
+  consolidated acceptance = 835 passed, 1 failed (SAME pre-existing
+  model-trends env failure), 2 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. If PASS, say exactly `PASS` so Batch 4
+may begin.
+codex
+I’m using the `megado` checkpoint workflow to independently verify the incremental commit and each of the four prior findings. I’ll keep the worktree read-only and return only the required binary verdict.
+exec
+/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
+---
+name: megado
+description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, max reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where a GPT-5.6 Sol oracle reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
+---
+
+# Megado
+
+A delivery pipeline for a whole project: **Codex plans, DeepSeek explores, Codex revises, DeepSeek executes, Codex oracles** — all in a worktree, opened and synced when done. Two models only: **DeepSeek V4 Flash** and **GPT-5.6 Sol**.
+
+The shape (from the original ask, normalized):
+
+1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
+2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
+3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
+4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
+5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
+6. Open it and sync.
+
+## Roles
+
+| Role | Model | Invocation | Tools |
+| --- | --- | --- | --- |
+| **Planner / Oracle** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=max` | read-only for planning/review; `workspace-write` when it implements |
+| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
+| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
+| **Hard-task executor** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=max` | `workspace-write` |
+
+The whole pipeline runs on exactly two models: **DeepSeek V4 Flash** (cheap, fast, coding-tuned — exploration and normal execution) and **GPT-5.6 Sol** (the frontier planner/oracle — planning, revision, hard tasks, checkpoint review). Escalate exploration to DeepSeek V4 Pro only on evidence that Flash's findings are thin.
+
+One orchestrator (the host agent) drives all phases and holds the artifacts; each subagent gets a self-contained brief and returns only its conclusion.
+
+## Artifacts (in the worktree)
+
+```
+.oracle/
+  plan.md            # living plan: v1 from Codex, revised each loop
+  briefs/            # one brief per explorer / executor batch
+  findings/          # explorer outputs: <area>.txt (+ .meta.json from fan.py)
+  tasklist.md        # frozen batched task list with checkpoints + [HARD] tags
+  checkins/          # oracle verdicts: batch-<N>.md
+  status.md          # current phase, batch, checkpoint state
+```
+
+## Phase 0 — Worktree
+
+Run the whole pipeline on a branch, never on main.
+
+```bash
+git worktree add ../<project>-oracle -b oracle-run
+cd ../<project>-oracle
+mkdir -p .oracle/briefs .oracle/findings .oracle/checkins
+```
+
+## Phase 1 — Initial plan (Codex)
+
+Brief GPT-5.6 Sol at max reasoning. Demand three outputs, in order:
+
+1. A tasklist covering the **entirety** of the project (not just the obvious path).
+2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
+3. Open questions / potential issues.
+
+```bash
+timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max \
+  "$(cat /tmp/plan-brief.md)" </dev/null > /tmp/plan-v1.txt 2>&1
+```
+
+The brief is a spec, not a memo: project path, goal, constraints, "list every area you'd explore for full clarity — don't stop at what's obvious." Save the result as `.oracle/plan.md` (host writes it; Codex stays read-only).
+
+## Phase 2 — Deep exploration (DeepSeek fan-out)
+
+One DeepSeek V4 Flash agent per area, in parallel. `fan.py` for ≥ ~5 areas; `launch_hermes_agent.py` per area below that.
+
+```bash
+PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
+  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
+  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
+  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
+```
+
+Each brief: "Explore area X in depth. Report verified facts with file/line evidence, unknowns, risks, and a suggested approach. Ranked findings, <300 words." Exploration answers the *plan's* questions — mechanical briefs, no license to architect.
+
+## Phase 3 — Revise-until-stable loop
+
+Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Codex (GPT-5.6 Sol, max reasoning):
+
+> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.
+
+- New material areas → re-run Phase 2 for those, then revise again.
+- Repeat until Codex returns `STABLE` (or two consecutive rounds with no material change).
+- The plan is a living doc during this loop; it freezes at Phase 4.
+
+## Phase 4 — Batched tasklist with checkpoints (Codex)
+
+Ask Codex (GPT-5.6 Sol, max reasoning) to convert the stable plan into an execution structure:
+
+- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
+- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
+- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
+- **Per-batch acceptance criteria** the oracle will verify.
+
+Emit as markdown (or JSON if the host will script it) into `.oracle/tasklist.md`. This file is **frozen** — execution follows it; plan revisions during execution go through the oracle, not silent edits.
+
+## Phase 5 — Execute, with oracle checkpoints
+
+Per batch, in order:
+
+**1. Execute the batch.** DeepSeek Flash takes every non-`[HARD]` task — one agent per batch, terminal toolset so it can run code and tests:
+
+```bash
+PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
+  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
+  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
+```
+
+`[HARD]` tasks go to GPT-5.6 Sol instead:
+
+```bash
+timeout 1800 codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=max \
+  "$(cat /tmp/hard-task-brief.md)" </dev/null
+```
+
+(Use `--sandbox danger-full-access` only when the Codex agent must itself orchestrate hermes subagents — those need outbound network.)
+
+**2. Checkpoint — oracle review.** Send the batch's completed work to GPT-5.6 Sol (max reasoning):
+
+```bash
+timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max \
+  "$(cat /tmp/checkin-brief.md)" </dev/null > .oracle/checkins/batch-<N>.md 2>&1
+```
+
+The check-in brief carries: the batch's tasks + acceptance criteria from `tasklist.md`, and the diff since the last checkpoint (`git diff <last-checkpoint-sha>..HEAD` — commit after each batch so the oracle sees a clean delta). Verdict is binary: `PASS` or a list of issues.
+
+**3. Rework loop.** On issues, send them back to the executor (Flash for normal, GPT-5.6 Sol for HARD), re-run, re-review — until the oracle passes. **Do not start batch N+1 until batch N passes.**
+
+## Phase 6 — Completion
+
+1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
+2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
+3. `open` the worktree / project for the user, and report phase-by-phase evidence.
+
+## Gotchas
+
+- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
+- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
+- **Match brief shape to model mode.** Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs derived straight from the tasklist. Judgement (exploration, revision, oracle) stays at GPT-5.6 Sol; escalate Flash exploration to DeepSeek V4 Pro only on evidence.
+- **Liveness ≠ correctness.** Watch `fan.py` `.meta.json` files and the stderr `[tool]`/`[done]` heartbeat; check 30–60 s after launch, not 10 minutes in. But a live agent can still answer uselessly — read the response.
+- **Checkpoint discipline is the whole game.** The oracle gate is what makes quality; skipping it to "save a cycle" collapses this into a plain DeepSeek run.
+- **Elegance bias is a real instruction.** Codex's revision prompt must name it; otherwise reasoning models add scope, not subtract it.
+
+## Quick reference
+
+```bash
+# Phase 0
+git worktree add ../<project>-oracle -b oracle-run && cd ../<project>-oracle
+mkdir -p .oracle/briefs .oracle/findings .oracle/checkins
+
+# Phase 1 — initial plan (GPT-5.6 Sol, max reasoning)
+timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max "$(cat /tmp/plan-brief.md)" </dev/null
+
+# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
+PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
+  --briefs-dir=.oracle/briefs --output-dir=.oracle/findings \
+  --max-workers=<N> --model="deepseek:deepseek-v4-flash" \
+  --toolsets="file,web" --task-timeout=1800 --project-dir="$PWD"
+
+# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
+# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [HARD] tags)
+
+# Phase 5 — execute (DeepSeek V4 Flash, one agent per batch)
+PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
+  --model="deepseek:deepseek-v4-flash" --toolsets="file,web,terminal" \
+  --query-file=.oracle/briefs/batch-<N>.md --project-dir="$PWD"
+# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=max
+# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max "$(cat /tmp/checkin-brief.md)" </dev/null
+
+# Phase 6 — commit, push, open
+git add -A && git commit -m "megado: <project>" && git push && open .
+```
+
+2026-08-12T12:24:58.618706Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T12:24:58.619057Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T12:24:58.619080Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+exec
+/bin/zsh -lc "rg --files .oracle | sort | rg 'batch-3|tasklist|status|plan'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
+.oracle/briefs/05-hybrid-planner-canvas.md
+.oracle/briefs/batch-3-t3.1.md
+.oracle/briefs/batch-3-t3.2.md
+.oracle/briefs/batch-3-t3.3.md
+.oracle/briefs/batch-3-t3.4.md
+.oracle/briefs/batch-3-t3.5.md
+.oracle/briefs/batch-3-t3.6.md
+.oracle/checkins/batch-3-r1.md
+.oracle/checkins/batch-3-r2.md
AGENTS.md
examples/packs/minimal/AGENTS.md
examples/packs/text_digest/AGENTS.md
examples/packs/text_review/AGENTS.md
examples/packs/file_summarizer/AGENTS.md
examples/packs/media/AGENTS.md

exec
/bin/zsh -lc "git diff --no-ext-diff --unified=120 a7b7b080..9bf9db88 -- astrid/packs/rendering/backends/ffmpeg/support.py tests/packs/rendering/test_ffmpeg_support.py && git show 9bf9db88:.oracle/tasklist.md | rg -n -C 8 'Batch 3|T3\\.|acceptance|FFmpeg|profile|level' | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/packs/rendering/backends/ffmpeg/support.py b/astrid/packs/rendering/backends/ffmpeg/support.py
index d9c3b35f..7c5378d9 100644
--- a/astrid/packs/rendering/backends/ffmpeg/support.py
+++ b/astrid/packs/rendering/backends/ffmpeg/support.py
@@ -429,240 +429,255 @@ def _requested_ownership(
     if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
         ownership = AudioOwnership.PASSTHROUGH
     elif request.audio is not None and request.audio is not natural:
         reasons.append(
             f"audio={request.audio.value!r} is incompatible with timeline audio ownership {natural.value!r}"
         )
     if request.profile is not None and request.profile.has_audio != (
         ownership is AudioOwnership.RENDERED
     ):
         reasons.append(
             "requested profile audio fields do not match rendering.ffmpeg audio ownership"
         )
     return ownership, reasons
 
 
 def _whole_media_optimization(
     timeline_data: Mapping[str, Any],
     assets: Mapping[str, Any],
     probes: Mapping[str, MediaProbe],
 ) -> bool:
     tracks = {
         track.get("id"): track
         for track in timeline_data.get("tracks", [])
         if isinstance(track, Mapping)
     }
     visual = [
         clip
         for clip in timeline_data.get("clips", [])
         if isinstance(clip, Mapping)
         and clip.get("clipType") == "media"
         and tracks.get(clip.get("track"), {}).get("kind") == "visual"
     ]
     table = _assets_table(assets)
     if len(visual) != 1 or table is None:
         return False
     clip = visual[0]
     entry = table.get(clip.get("asset"))
     if not isinstance(entry, Mapping):
         return False
     media_probe = probes.get(str(clip.get("asset")))
     if media_probe is None or not media_probe.has_video_stream:
         return False
     try:
         bounds = _clip_range(clip)
         width, height, fps = _canvas(timeline_data)
         duration = _number(entry.get("duration"), "asset duration")
         source_fps = _number(entry.get("fps"), "asset fps")
     except ValueError:
         return False
     probed_duration = _probe_duration(media_probe)
     probed_fps = media_probe.fps
     if probed_fps is None and media_probe.fps_rational is not None:
         numerator, denominator = media_probe.fps_rational
         probed_fps = numerator / denominator
     # Frame-accurate tolerance: at most ONE frame of drift is acceptable
     # (half a frame each way), so extra trailing frames at high FPS cannot
     # slip through a coarse 50 ms window.
     frame_tolerance = 0.5 / fps if fps > 0 else 0.0
     return (
         bounds.at == 0
         and bounds.source_from == 0
         and abs(bounds.duration - duration) < frame_tolerance
         and entry.get("resolution") == f"{width}x{height}"
         and abs(source_fps - fps) < 1e-6
         and probed_duration is not None
         and abs(bounds.duration - probed_duration) < frame_tolerance
         and media_probe.width == width
         and media_probe.height == height
         and probed_fps is not None
         and abs(probed_fps - fps) < 1e-6
         and (media_probe.video_codec or "") == "h264"
         and (media_probe.pixel_format or "") == "yuv420p"
         and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
     )
 
 
 def _probe_time_base_matches(
     probe: MediaProbe, expected: tuple[int, int]
 ) -> bool:
     """The probed stream time base must equal the canonical MP4 timescale."""
     if probe.time_base is None:
         return False
     return Fraction(*probe.time_base) == Fraction(*expected)
 
 
 def _profile_support_reasons(
     request: RenderRequest, timeline_data: Mapping[str, Any]
 ) -> list[str]:
     """Fail closed when the requested profile deviates from what the FFmpeg
     backend actually produces (canvas dims/fps, codecs, pixel format, and
     canonical audio rate/layout)."""
     profile = request.profile
     if profile is None:
         return []
     reasons: list[str] = []
     try:
         width, height, fps = _canvas(timeline_data)
     except ValueError:
         return reasons  # canvas failure already reported elsewhere
     checks = (
         ("width", profile.width, width),
         ("height", profile.height, height),
         ("fps", profile.fps_rational, (fps, 1)),
         ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
         ("container", profile.container, "mp4"),
         ("video_codec", profile.video_codec, "h264"),
         ("pixel_format", profile.pixel_format, "yuv420p"),
     )
     for field, requested, produced in checks:
         if requested is None:
             continue
         if field in ("fps", "time_base"):
             equal = _rational_equal(requested, produced)
         else:
             equal = requested == produced
         if not equal:
             reasons.append(
                 f"requested profile {field}={requested!r} is not produced by "
                 f"rendering.ffmpeg (produces {produced!r})"
             )
+    # The command does NOT pin video_profile/video_level (libx264 picks the
+    # encoder default; stream-copy preserves whatever the source has). A
+    # request pinning them cannot be guaranteed at support time, so fail
+    # closed rather than report success and fail strict post-render
+    # validation.
+    for field, requested in (
+        ("video_profile", profile.video_profile),
+        ("video_level", profile.video_level),
+    ):
+        if requested is not None:
+            reasons.append(
+                f"requested profile {field}={requested!r} cannot be guaranteed "
+                f"by rendering.ffmpeg (encoder default or stream-copy preserves "
+                f"source values; omit {field} to use defaults)"
+            )
     if profile.has_audio:
         for field, requested, produced in (
             ("audio_sample_rate", profile.audio_sample_rate, 48000),
             ("audio_channel_layout", profile.audio_channel_layout, "stereo"),
             ("audio_codec", profile.audio_codec, "aac"),
         ):
             if requested is not None and requested != produced:
                 reasons.append(
                     f"requested profile {field}={requested!r} is not produced by "
                     f"rendering.ffmpeg (produces {produced!r})"
                 )
     return reasons
 
 
 def _fps_int(fps_rational: tuple[int, int] | None) -> int | None:
     if fps_rational is None:
         return None
     num, den = fps_rational
     return num // den if den and num % den == 0 else None
 
 
 def _rational_equal(a: Any, b: Any) -> bool:
     try:
         return Fraction(*a) == Fraction(*b)
     except (TypeError, ValueError, ZeroDivisionError):
         return False
 
 
 def _canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
     overrides = timeline_data.get("theme_overrides")
     visual = overrides.get("visual") if isinstance(overrides, Mapping) else None
     canvas = visual.get("canvas") if isinstance(visual, Mapping) else None
     canvas = canvas if isinstance(canvas, Mapping) else {}
     values: list[int] = []
     for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
         value = canvas.get(key, default)
         if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
             raise ValueError(f"Canvas {key} must be a positive integer")
         values.append(value)
     return values[0], values[1], values[2]
 
 
 def support(
     request: RenderRequest,
     timeline_data: Mapping[str, Any],
     assets: Mapping[str, Any],
     *,
     probe: Probe | None = None,
     which: BinaryResolver | None = None,
 ) -> SupportReport:
     """Return strict support evidence for one already-decoded request."""
 
     reasons: list[str] = []
     probe_media = probe or ffprobe_metadata_strict
     resolve_binary = which or shutil.which
     binary_available: dict[str, bool] = {}
     for binary in ("ffmpeg", "ffprobe"):
         available = resolve_binary(binary) is not None
         binary_available[binary] = available
         if not available:
             reasons.append(f"required binary is unavailable: {binary}")
 
     if request.window is not None:
         reasons.append(
             "rendering.ffmpeg accepts complete timelines, not native frame windows"
         )
     config = request.backend_config.get(BACKEND_ID, {})
     if config:
         reasons.append(
             "rendering.ffmpeg does not accept backend-specific configuration"
         )
     if request.assets_registry_path is None:
         reasons.append("rendering.ffmpeg requires an assets registry")
     try:
         _canvas(timeline_data)
     except ValueError as exc:
         reasons.append(str(exc))
     reasons.extend(structural_reasons(timeline_data))
 
     table = _assets_table(assets)
     if table is None:
         reasons.append("assets registry must contain an assets object")
         table = {}
     assets_path = _registry_path(request)
     tracks = {
         track.get("id"): track
         for track in timeline_data.get("tracks", [])
         if isinstance(track, Mapping)
     }
     media_clips = [
         clip
         for clip in timeline_data.get("clips", [])
         if isinstance(clip, Mapping) and clip.get("clipType") == "media"
     ]
     audio_clips = [
         clip
         for clip in media_clips
         if tracks.get(clip.get("track"), {}).get("kind") == "audio"
     ]
     ownership, ownership_reasons = _requested_ownership(
         request,
         has_audio_clips=bool(audio_clips),
     )
     reasons.extend(ownership_reasons)
 
     probes: dict[str, MediaProbe] = {}
     for clip in media_clips:
         clip_id = clip.get("id")
         asset_id = clip.get("asset")
         if not isinstance(asset_id, str) or not asset_id:
             reasons.append(f"Clip {clip_id!r} has no asset")
             continue
         entry = table.get(asset_id)
         if not isinstance(entry, Mapping):
             reasons.append(f"Clip {clip_id!r} references missing asset {asset_id!r}")
             continue
         try:
             path = _asset_path(entry, asset_id=asset_id, assets_path=assets_path)
         except (ValueError, FileNotFoundError) as exc:
             reasons.append(str(exc))
diff --git a/tests/packs/rendering/test_ffmpeg_support.py b/tests/packs/rendering/test_ffmpeg_support.py
index dcc8fb33..a24db1c5 100644
--- a/tests/packs/rendering/test_ffmpeg_support.py
+++ b/tests/packs/rendering/test_ffmpeg_support.py
@@ -1,123 +1,124 @@
 from __future__ import annotations
 
 import copy
+import dataclasses
 import importlib
 import json
 import subprocess
 from pathlib import Path
 from unittest import mock
 
 import pytest
 
 from astrid.core.media import MediaProbe
 from astrid.core.rendering.contracts import (
     AudioOwnership,
     FrameWindow,
     RenderRequest,
     RenderResult,
     SCHEMA_VERSION,
 )
 from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
 from astrid.packs.rendering.backends.ffmpeg import command
 from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
 from astrid.packs.rendering.backends.ffmpeg.support import support as evaluate_support
 
 
 support_module = importlib.import_module(
     "astrid.packs.rendering.backends.ffmpeg.support"
 )
 
 
 def _timeline(*, include_audio: bool = True, duration: float = 4.0) -> dict:
     tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
     clips = [
         {
             "id": "video",
             "at": 0,
             "track": "v",
             "clipType": "media",
             "asset": "video",
             "from": 0,
             "to": duration,
             "speed": 1,
             "volume": 0,
         }
     ]
     if include_audio:
         tracks.append(
             {
                 "id": "a",
                 "kind": "audio",
                 "label": "Audio",
                 "volume": 0.5,
             }
         )
         clips.append(
             {
                 "id": "audio",
                 "at": 0,
                 "track": "a",
                 "clipType": "media",
                 "asset": "audio",
                 "from": 0,
                 "to": duration,
                 "speed": 1,
                 "volume": 0.4,
             }
         )
     return {
         "theme": "banodoco-default",
         "theme_overrides": {
             "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
         },
         "tracks": tracks,
         "clips": clips,
     }
 
 
 def _assets(tmp_path: Path, *, duration: float = 4.0) -> dict:
     return {
         "assets": {
             "video": {
                 "file": "video.mp4",
                 "type": "video/mp4",
                 "duration": duration,
                 "resolution": "640x360",
                 "fps": 30,
             },
             "audio": {
                 "file": "audio.wav",
                 "type": "audio/wav",
                 "duration": duration,
             },
         }
     }
 
 
 def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
     return MediaProbe(
         duration_seconds=duration,
         width=640,
         height=360,
         fps=30,
         time_base=(1, 15360),
         resolution="640x360",
         video_codec="h264",
         pixel_format="yuv420p",
         audio_codec="aac" if audio else None,
         video_stream_present=True,
         audio_stream_present=audio,
     )
 
 
 def _audio_probe(*, duration: float = 4.0, present: bool = True) -> MediaProbe:
     return MediaProbe(
         duration_seconds=duration,
         audio_codec="pcm_s16le" if present else None,
         video_stream_present=False,
         audio_stream_present=present,
     )
 
 
 def _request(
     tmp_path: Path,
@@ -504,120 +505,154 @@ def _reactive_timeline() -> dict:
                 "volume": 0.5,
             },
         ],
         "clips": [
             {
                 "id": "colour",
                 "at": 0,
                 "track": "v",
                 "clipType": "audio-reactive-colour",
                 "hold": 1,
                 "params": {
                     "schemaVersion": 1,
                     "initialColor": "#102030",
                     "events": [
                         {"id": "one", "frame": 3, "color": "#D47795"},
                         {"id": "two", "frame": 8, "color": "#26A7D0"},
                     ],
                 },
             },
             {
                 "id": "audio",
                 "at": 0,
                 "track": "a",
                 "clipType": "media",
                 "asset": "audio",
                 "from": 0,
                 "to": 1,
                 "volume": 0.4,
             },
         ],
     }
 
 
 def test_audio_reactive_support_gain_and_protocol_provenance_fragments(
     tmp_path: Path,
 ) -> None:
     timeline_data = _reactive_timeline()
     assets = {
         "assets": {
             "audio": {
                 "file": "audio.wav",
                 "type": "audio/wav",
                 "duration": 1,
             }
         }
     }
     report = _evaluate(
         tmp_path,
         timeline_data,
         assets,
         probes={"audio.wav": _audio_probe(duration=1)},
     )
     spec = audio_reactive_colour.match_and_validate(
         timeline_data,
         assets,
         tmp_path / "assets.json",
     )
 
     assert report.supported is True
     assert report.features["audio_reactive_colour"] is True
     assert report.features["specialization"] == "audio-reactive-colour/v1"
     assert spec is not None
     assert spec.audio_volume == pytest.approx(0.2)
 
     output_probe = MediaProbe(
         width=640,
         height=360,
         fps_rational=(30, 1),
         time_base=(1, 15360),
         video_codec="h264",
         video_profile="High",
         video_level="40",
         pixel_format="yuv420p",
         audio_codec="aac",
         audio_sample_rate=48000,
         audio_channel_layout="stereo",
         audio_channels=2,
         container="mp4",
         duration_rational=(1, 1),
         video_stream_present=True,
         audio_stream_present=True,
     )
 
     def fake_render(
         _spec: audio_reactive_colour.AudioReactiveColourSpec,
         output: Path,
     ) -> Path:
         output.parent.mkdir(parents=True, exist_ok=True)
         output.write_bytes(b"video")
         return output
 
     def probe(path: Path) -> MediaProbe:
         return (
             _audio_probe(duration=1)
             if Path(path).name == "audio.wav"
             else output_probe
         )
 
     with (
         mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
         mock.patch.object(ffmpeg, "ffprobe_metadata_strict", side_effect=probe),
         mock.patch.object(audio_reactive_colour, "render", side_effect=fake_render),
         mock.patch.object(
             ffmpeg.remotion_backend,
             "_render_provenance_payload",
             return_value={"engine": "ffmpeg"},
         ),
         mock.patch.object(ffmpeg, "validate_render_result"),
     ):
         result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)
 
     assert isinstance(result, RenderResult)
     assert result.audio_ownership is AudioOwnership.RENDERED
     fragment = result.backend_fragments[ffmpeg.BACKEND_ID]["specialization"]
     assert fragment["id"] == "audio-reactive-colour/v1"
     assert [marker["frame"] for marker in fragment["markers"]] == [3, 8]
     assert fragment["event_count"] == 2
     assert fragment["frame_count"] == 30
     assert fragment["fps"] == 30
     assert len(fragment["marker_sha256"]) == 64
+
+
+def test_pinned_video_profile_and_level_are_rejected_as_unguaranteed(
+    tmp_path: Path,
+) -> None:
+    """A request pinning video_profile/video_level cannot be guaranteed by
+    the FFmpeg command (encoder default or stream-copy preserves source
+    values), so support must fail closed instead of failing strict
+    post-render validation."""
+    request = _request(tmp_path)
+    from astrid.core.rendering.contracts import RenderProfile
+
+    base_profile = RenderProfile(
+        width=640,
+        height=360,
+        fps_rational=(30, 1),
+        time_base=(1, 15360),
+        container="mp4",
+        video_codec="h264",
+        video_profile=None,
+        video_level=None,
+        pixel_format="yuv420p",
+    )
+    request = dataclasses.replace(
+        request,
+        profile=dataclasses.replace(
+            base_profile,
+            video_profile="High",
+            video_level="40",
+        ),
+    )
+    report = _evaluate(tmp_path, _timeline(), _assets(tmp_path), request=request)
+    assert report.supported is False
+    assert any("video_profile" in reason or "video_level" in reason for reason in report.reasons)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
1-# Renderer Tasklist
2-
3-## Batch 1 — Baseline, contracts, and discovery
4-
5-**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
6-
7-**Acceptance criteria:**
8-
9:- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
10-- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
11-- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
12-- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
13-- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
14-- Active trusted installs, corrupt/mismatched installs, inactive revisions, explicit-extra roots, environment denial, conflicts, cycles, and invalid override targets produce the specified inspectable/executable states.
15-- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
16-- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.
17-
18-### Tasks
19-
20:- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
23:- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
24:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
25-
26-## Batch 2 — Command protocol and host-owned plumbing
27-
28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
29-
30-**Acceptance criteria:**
31-
32-- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
33-- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
34-- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
35-- Asset-cache layout, URL keys, resume/drift metadata, locking, and `EphemeralSession` behavior remain unchanged behind the compatibility wrapper.
36-- Only invocation-staged assets are served from `127.0.0.1` on port `0`; Range requests work and the server always shuts down, closes, and joins.
37:- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
38:- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
39-- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
40-
41-### Tasks
42-
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
45:- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
49-
50:## Batch 3 — Built-in renderer and finalizer extraction
51-
52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
53-
54-**Acceptance criteria:**
55-
56-- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
57-- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
58-- One non-recursive cross-process lock spans registry-state reads, all registry/shim/theme-pointer writes, active-theme selection, the complete Remotion render, and the `gen-types` writer path.
59:- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
60:- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
61:- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
62:- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.
63-
64-### Tasks
65-
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
72-
73-## Batch 4 — Generic routing, provenance, and hybrid planning
74-
75-**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.
76-
77-**Acceptance criteria:**
78-
79-- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
80-- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
81-- `output_name` uses existing input placeholders and cache/CAS identity, rejects separators/traversal/non-MP4 extensions, preserves declared output names, and leaves Hype’s default `hype.mp4` sentinel unchanged.
82:- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
84:- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
85:- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.
86-
87-### Tasks
88-
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
90:- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
94-
95-## Batch 5 — Caller migration, semantic parity, and M1 freeze
96-
97-**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.
98-
99-**Acceptance criteria:**
100-
101-- The attached-child helper requires a validated parent project/run and unique step, scopes and restores all three `ASTRID_TASK_*` variables, preserves caller-selected output, honors facade overrides, and falls back to public `RenderService` only without a project ledger.
102-- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
103-- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
104-- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
105:- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
106:- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
107-- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
108:- Targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.
109-
110-### Tasks
111-
112:- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
113:- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
114:- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
116:- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
117:- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
118:- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
119-
120-## Batch 6 — Python SDK, conformance, and scaffold
121-
122-**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.
123-
124-**Acceptance criteria:**
125-
126-- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
--
128-- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
129-- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
130-- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
131-- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
132-- Scaffold collision, ownership, command-containment, static validation, trusted install, generated test, two-second smoke, and installed-wheel cases pass.
133-
134-### Tasks
135-
136:- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
138:- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
140:- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
141:- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.
142-
143-## Batch 7 — CLI, replay, documentation, and epic freeze
144-
145-**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.
146-
147-**Acceptance criteria:**
148-
149-- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
150-- `list` and `inspect` perform static metadata parsing and report source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and overrides without importing backend code.
151-- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
152-- Each CLI verb has a frozen raw-dictionary `--json` shape; expected errors exit 2, degraded bugs exit 1, and interruption cleans up before normal exit-130 behavior.
153-- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
154-- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
155-- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
156-- Renderer-author documentation covers raw JSON, Python SDK, non-Python commands, trust, permissions, selection, configuration, assets, output/audio/attachments, diagnostics, replay, and legacy selectors while explicitly deferring async jobs, remote infrastructure, and layer compositing.
157:- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
158:- Full pytest, semantic parity, real FFmpeg, explicit optional-Remotion evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.
159-
160-### Tasks
161-
162:- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
164:- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
165:- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
167:- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
168-
169-## Execution notes
170-
171-- Persist this markdown exactly as `.oracle/tasklist.md` before implementation. It is frozen; any change requires an explicit oracle-reviewed plan revision.
172:- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
173-- If the oracle reports issues, rework only the current batch, recommit, and resubmit the cumulative `C(N-1)..HEAD` range until `PASS`. Do not begin the next batch early.
174:- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
175-- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
176-- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
177-- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
178-- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
179-- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.

exec
/bin/zsh -lc "rg -n \"_profile_support_reasons|video_profile|video_level|class RenderProfile|strict.*profile|validate_render\" astrid/core astrid/packs/rendering tests/packs/rendering/test_ffmpeg_support.py | head -n 320 && sed -n '120,240p' astrid/core/rendering/contracts.py && sed -n '760,900p' astrid/packs/rendering/backends/ffmpeg/support.py && sed -n '1,220p' astrid/packs/rendering/backends/ffmpeg/command.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 5ms:
        "whole_media": whole_media,
        "whole_media_optimization": whole_media,
        "stream_copy": whole_media,
        "audio_ownership": ownership.value,
    }
    if specialization:
        features["specialization"] = audio_reactive_colour.ADAPTER_ID

    reasons.extend(_profile_support_reasons(request, timeline_data))

    reasons = _dedupe(reasons)
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=not reasons,
        reasons=reasons,
        features=features,
        alternatives=list(ALTERNATIVE_BACKENDS) if reasons else [],
        backend=BACKEND_ID,
        backend_version=BACKEND_VERSION,
    )


__all__ = [
    "ALTERNATIVE_BACKENDS",
    "BACKEND_ID",
    "BACKEND_VERSION",
    "effective_gain",
    "structural_reasons",
    "support",
]
"""Pure FFmpeg command builders for the media-only renderer.

The builders read the immutable request inputs and return argv.  They do not
create directories, write files, or launch subprocesses, which keeps command
construction independently testable from execution and publication.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from astrid.core import timeline
from astrid.core.rendering.contracts import RenderRequest


@dataclass(frozen=True)
class RenderCommandInputs:
    """Resolved, validated inputs used to construct one FFmpeg argv."""

    timeline_path: Path
    assets_path: Path
    output_path: Path
    timeline_data: dict[str, Any]
    registry: dict[str, Any]
    audio_sample_rate: int = 48000
    # Probe-derived evidence from strict support: stream-copy is only
    # permitted when the actual media probe confirmed whole-source
    # compatibility (never trust registry metadata alone).
    stream_copy_allowed: bool = False


def timeline_canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
    canvas = (
        timeline_data.get("theme_overrides", {})
        .get("visual", {})
        .get("canvas", {})
    )
    return (
        int(canvas.get("width", 1920)),
        int(canvas.get("height", 1080)),
        int(canvas.get("fps", 30)),
    )


def clip_duration_seconds(clip: Mapping[str, Any]) -> float:
    clip_id = clip.get("id")

    def number(value: Any, label: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Clip {clip_id!r} {label} must be a finite number")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"Clip {clip_id!r} {label} must be a finite number")
        return result

    start = number(clip.get("from", 0), "from")
    if "to" not in clip:
        raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
    end = number(clip.get("to"), "to")
    speed = number(clip.get("speed", 1), "speed")
    if speed <= 0:
        raise ValueError(f"Clip {clip_id!r} has non-positive speed {speed}")
    if start < 0 or end <= start:
        raise ValueError(
            f"Clip {clip_id!r} must have positive source bounds with to > from"
        )
    return (end - start) / speed


def validate_ffmpeg_media_timeline(timeline_data: Mapping[str, Any]) -> None:
    """Reject every media-timeline semantic the pure builder would discard."""

    # Local import avoids a module cycle: support owns semantic validation and
    # imports this module only for command construction helpers.
    from astrid.packs.rendering.backends.ffmpeg.support import structural_reasons

    reasons = structural_reasons(
        timeline_data,
        allow_audio_reactive=False,
    )
    if reasons:
        raise ValueError(reasons[0])


def _input_path(raw_path: str, workspace: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    return (
        candidate if candidate.is_absolute() else workspace / candidate
    ).resolve()


def _coerce_request(request: RenderRequest | Mapping[str, Any]) -> RenderRequest:
    if isinstance(request, RenderRequest):
        return request
    return RenderRequest.from_dict(request)


def resolve_render_command_inputs(
    request: RenderRequest | Mapping[str, Any],
    workspace: Path,
) -> RenderCommandInputs:
    """Resolve the request's existing input files without mutating anything."""

    normalized = _coerce_request(request)
    root = Path(workspace).resolve()
    timeline_path = _input_path(normalized.timeline_path, root)
    if normalized.assets_registry_path is None:
        raise ValueError("rendering.ffmpeg requires an assets registry")
    assets_path = _input_path(normalized.assets_registry_path, root)
    if not timeline_path.exists():
        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
    if not assets_path.exists():
        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(timeline_data, dict):
        raise ValueError("timeline must contain a JSON object")
    registry = timeline.load_registry(assets_path)
    validate_ffmpeg_media_timeline(timeline_data)
    return RenderCommandInputs(
        timeline_path=timeline_path,
        assets_path=assets_path,
        output_path=(root / "outputs" / normalized.output_name).resolve(),
        timeline_data=timeline_data,
        registry=dict(registry),
    )


def _command_inputs_for_paths(
    timeline_path: Path,
    assets_path: Path,
    output_path: Path,
) -> RenderCommandInputs:
    resolved_timeline = Path(timeline_path).resolve()
    resolved_assets = Path(assets_path).resolve()
    if not resolved_timeline.exists():
        raise FileNotFoundError(f"Timeline missing: {resolved_timeline}")
    if not resolved_assets.exists():
        raise FileNotFoundError(f"Asset registry missing: {resolved_assets}")
    timeline_data = json.loads(resolved_timeline.read_text(encoding="utf-8"))
    if not isinstance(timeline_data, dict):
        raise ValueError("timeline must contain a JSON object")
    registry = timeline.load_registry(resolved_assets)
    validate_ffmpeg_media_timeline(timeline_data)
    return RenderCommandInputs(
        timeline_path=resolved_timeline,
        assets_path=resolved_assets,
        # The legacy explicit-path helper passed the caller's spelling through
        # to FFmpeg and returned the same Path.  Protocol requests use the
        # workspace builder above, which deliberately resolves their output.
        output_path=Path(output_path),
        timeline_data=timeline_data,
        registry=dict(registry),
    )


def build_filter_graph(
    inputs: RenderCommandInputs,
) -> tuple[list[str], int | None]:
    """Return the legacy filter graph and optional stream-copy input index."""

    timeline_data = inputs.timeline_data
    registry = inputs.registry
    width, height, fps = timeline_canvas(timeline_data)
    tracks = {
        track.get("id"): track for track in timeline_data.get("tracks", [])
    }
    visual_track_ids = {
        track["id"]
        for track in tracks.values()
        if track.get("kind") == "visual"
    }
    audio_track_ids = {
        track["id"]
        for track in tracks.values()
        if track.get("kind") == "audio"
    }
    video_clips = sorted(
        [
            clip
            for clip in timeline_data.get("clips", [])
            if clip.get("track") in visual_track_ids
        ],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    audio_clips = sorted(
        [
            clip
            for clip in timeline_data.get("clips", [])
            if clip.get("track") in audio_track_ids
        ],
        key=lambda clip: float(clip.get("at", 0) or 0),
    )
    if not video_clips:
        raise ValueError("ffmpeg engine needs at least one visual media clip")

    asset_keys: list[str] = []
    for clip in [*video_clips, *audio_clips]:
        asset_key = str(clip.get("asset") or "")
        if not asset_key:
            raise ValueError(f"Clip {clip.get('id')!r} has no asset")
        if asset_key not in registry["assets"]:
            raise ValueError(
                f"Clip {clip.get('id')!r} references unknown asset "
                f"{asset_key!r}"
            )
        if asset_key not in asset_keys:
            asset_keys.append(asset_key)

    asset_index = {
        asset_key: index for index, asset_key in enumerate(asset_keys)
    }
    filters: list[str] = []
    video_labels: list[str] = []
    copy_video_input: int | None = None
    if len(video_clips) == 1:

exec
/bin/zsh -lc "sed -n '430,590p' astrid/core/rendering/contracts.py && sed -n '400,690p' tests/packs/rendering/test_ffmpeg_support.py && sed -n '250,370p' astrid/core/rendering/artifacts.py && sed -n '430,470p' astrid/core/rendering/artifacts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 275ms:
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FrameWindow:
        data = _require_mapping(payload, "frame window")
        _validate_object_keys(
            data,
            required={"start_frame", "end_frame", "fps_rational"},
            allowed={"start_frame", "end_frame", "fps_rational", "source_range", "speed"},
            label="frame window",
        )
        return cls(
            start_frame=data["start_frame"],
            end_frame=data["end_frame"],
            fps_rational=data["fps_rational"],
            source_range=data.get("source_range"),
            speed=data.get("speed"),
        )


@dataclass(frozen=True)
class RenderProfile:
    """Resolved media profile used to validate and finalize artifacts."""

    width: int
    height: int
    fps_rational: tuple[int, int]
    time_base: tuple[int, int]
    video_codec: str
    pixel_format: str
    video_profile: str | None = None
    video_level: str | None = None
    container: str = "mp4"
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channel_layout: str | None = None
    duration_tolerance: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _require_int(self.width, "width", minimum=1))
        object.__setattr__(self, "height", _require_int(self.height, "height", minimum=1))
        object.__setattr__(self, "fps_rational", _require_rational(self.fps_rational, "fps_rational"))
        object.__setattr__(self, "time_base", _require_rational(self.time_base, "time_base"))
        object.__setattr__(self, "video_codec", _require_string(self.video_codec, "video_codec"))
        object.__setattr__(self, "pixel_format", _require_string(self.pixel_format, "pixel_format"))
        object.__setattr__(
            self,
            "video_profile",
            _require_optional_string(self.video_profile, "video_profile"),
        )
        object.__setattr__(
            self,
            "video_level",
            _require_optional_string(self.video_level, "video_level"),
        )
        object.__setattr__(self, "container", _require_string(self.container, "container"))
        audio_values = (
            self.audio_codec,
            self.audio_sample_rate,
            self.audio_channel_layout,
        )
        if any(value is not None for value in audio_values) and not all(
            value is not None for value in audio_values
        ):
            raise ValueError(
                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
                "provided together or all omitted"
            )
        if self.audio_codec is not None:
            object.__setattr__(self, "audio_codec", _require_string(self.audio_codec, "audio_codec"))
            object.__setattr__(
                self,
                "audio_sample_rate",
                _require_int(self.audio_sample_rate, "audio_sample_rate", minimum=1),
            )
            object.__setattr__(
                self,
                "audio_channel_layout",
                _require_string(self.audio_channel_layout, "audio_channel_layout"),
            )
        object.__setattr__(
            self,
            "duration_tolerance",
            _require_int(self.duration_tolerance, "duration_tolerance", minimum=0),
        )

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "width": self.width,
                "height": self.height,
                "fps_rational": self.fps_rational,
                "time_base": self.time_base,
                "container": self.container,
                "video_codec": self.video_codec,
                "video_profile": self.video_profile,
                "video_level": self.video_level,
                "pixel_format": self.pixel_format,
                "audio_codec": self.audio_codec,
                "audio_sample_rate": self.audio_sample_rate,
                "audio_channel_layout": self.audio_channel_layout,
                "duration_tolerance": self.duration_tolerance,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
        data = _require_mapping(payload, "render profile")
        required = {
            "width",
            "height",
            "fps_rational",
            "time_base",
            "container",
            "video_codec",
            "video_profile",
            "video_level",
            "pixel_format",
            "duration_tolerance",
        }
        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
        _validate_object_keys(data, required=required, allowed=allowed, label="render profile")
        return cls(
            width=data["width"],
            height=data["height"],
            fps_rational=data["fps_rational"],
            time_base=data["time_base"],
            container=data["container"],
            video_codec=data["video_codec"],
            video_profile=data["video_profile"],
            video_level=data["video_level"],
            pixel_format=data["pixel_format"],
            audio_codec=data.get("audio_codec"),
            audio_sample_rate=data.get("audio_sample_rate"),
            audio_channel_layout=data.get("audio_channel_layout"),
            duration_tolerance=data["duration_tolerance"],
        )


def _validate_artifact_audio(
    profile: RenderProfile,
    ownership: AudioOwnership | None,
    label: str,
) -> None:
    """Keep probed media audio and ownership semantically aligned.

    ``rendered`` means the artifact itself contains audio and therefore has a
    populated audio profile. ``passthrough`` and ``none`` describe visual-only
    artifacts; the former asks the host/finalizer to supply canonical audio.
    """

    if profile.has_audio:
        if ownership is not AudioOwnership.RENDERED:
            raise ValueError(f"{label} with an audio profile must declare audio='rendered'")
    elif ownership is AudioOwnership.RENDERED:
        raise ValueError(f"{label} with audio='rendered' must have an audio profile")

    report = _evaluate(
        tmp_path,
        timeline_data,
        assets,
        probes={"video.mp4": _video_probe()},
    )
    argv = command.build_render_command(_request(tmp_path), tmp_path)

    assert report.supported is True
    assert report.features["audio_ownership"] == "none"
    # Without probe evidence of whole-source compatibility, stream-copy must
    # NOT be trusted from registry metadata: the builder re-encodes via
    # filter_complex with no audio mapping (-an).
    assert "-filter_complex" in argv
    assert "-c:a" not in argv
    assert "-an" in argv
    assert argv[argv.index("-c:v") + 1] == "libx264"


def test_visual_only_request_can_delegate_audio_as_passthrough(tmp_path: Path) -> None:
    timeline_data = _timeline(include_audio=False)
    assets = _assets(tmp_path)
    del assets["assets"]["audio"]

    report = _evaluate(
        tmp_path,
        timeline_data,
        assets,
        probes={"video.mp4": _video_probe()},
        request=_request(tmp_path, audio=AudioOwnership.PASSTHROUGH),
    )

    assert report.supported is True
    assert report.features["audio_ownership"] == "passthrough"


def test_visual_only_protocol_result_declares_none(tmp_path: Path) -> None:
    timeline_data = _timeline(include_audio=False)
    assets = _assets(tmp_path)
    del assets["assets"]["audio"]
    _evaluate(
        tmp_path,
        timeline_data,
        assets,
        probes={"video.mp4": _video_probe()},
    )
    probe = MediaProbe(
        duration_seconds=4,
        width=640,
        height=360,
        fps=30,
        fps_rational=(30, 1),
        time_base=(1, 15360),
        resolution="640x360",
        video_codec="h264",
        video_profile="High",
        video_level="40",
        pixel_format="yuv420p",
        container="mp4",
        duration_rational=(4, 1),
        video_stream_present=True,
        audio_stream_present=False,
    )
    seen: dict[str, list[str]] = {}

    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
        seen["argv"] = argv
        output = Path(argv[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        return subprocess.CompletedProcess(argv, 0)

    with (
        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", return_value=probe),
        mock.patch.object(ffmpeg.subprocess, "run", side_effect=fake_run),
        mock.patch.object(
            ffmpeg.remotion_backend,
            "_render_provenance_payload",
            return_value={"engine": "ffmpeg"},
        ),
        mock.patch.object(ffmpeg, "validate_render_result"),
    ):
        result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)

    assert result.audio_ownership is AudioOwnership.NONE
    assert result.video.audio is AudioOwnership.NONE
    assert result.video.profile.has_audio is False
    assert "-an" in seen["argv"]
    assert "-c:a" not in seen["argv"]


def _reactive_timeline() -> dict:
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
        },
        "tracks": [
            {"id": "v", "kind": "visual", "label": "Colour"},
            {
                "id": "a",
                "kind": "audio",
                "label": "Audio",
                "volume": 0.5,
            },
        ],
        "clips": [
            {
                "id": "colour",
                "at": 0,
                "track": "v",
                "clipType": "audio-reactive-colour",
                "hold": 1,
                "params": {
                    "schemaVersion": 1,
                    "initialColor": "#102030",
                    "events": [
                        {"id": "one", "frame": 3, "color": "#D47795"},
                        {"id": "two", "frame": 8, "color": "#26A7D0"},
                    ],
                },
            },
            {
                "id": "audio",
                "at": 0,
                "track": "a",
                "clipType": "media",
                "asset": "audio",
                "from": 0,
                "to": 1,
                "volume": 0.4,
            },
        ],
    }


def test_audio_reactive_support_gain_and_protocol_provenance_fragments(
    tmp_path: Path,
) -> None:
    timeline_data = _reactive_timeline()
    assets = {
        "assets": {
            "audio": {
                "file": "audio.wav",
                "type": "audio/wav",
                "duration": 1,
            }
        }
    }
    report = _evaluate(
        tmp_path,
        timeline_data,
        assets,
        probes={"audio.wav": _audio_probe(duration=1)},
    )
    spec = audio_reactive_colour.match_and_validate(
        timeline_data,
        assets,
        tmp_path / "assets.json",
    )

    assert report.supported is True
    assert report.features["audio_reactive_colour"] is True
    assert report.features["specialization"] == "audio-reactive-colour/v1"
    assert spec is not None
    assert spec.audio_volume == pytest.approx(0.2)

    output_probe = MediaProbe(
        width=640,
        height=360,
        fps_rational=(30, 1),
        time_base=(1, 15360),
        video_codec="h264",
        video_profile="High",
        video_level="40",
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_sample_rate=48000,
        audio_channel_layout="stereo",
        audio_channels=2,
        container="mp4",
        duration_rational=(1, 1),
        video_stream_present=True,
        audio_stream_present=True,
    )

    def fake_render(
        _spec: audio_reactive_colour.AudioReactiveColourSpec,
        output: Path,
    ) -> Path:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        return output

    def probe(path: Path) -> MediaProbe:
        return (
            _audio_probe(duration=1)
            if Path(path).name == "audio.wav"
            else output_probe
        )

    with (
        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", side_effect=probe),
        mock.patch.object(audio_reactive_colour, "render", side_effect=fake_render),
        mock.patch.object(
            ffmpeg.remotion_backend,
            "_render_provenance_payload",
            return_value={"engine": "ffmpeg"},
        ),
        mock.patch.object(ffmpeg, "validate_render_result"),
    ):
        result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)

    assert isinstance(result, RenderResult)
    assert result.audio_ownership is AudioOwnership.RENDERED
    fragment = result.backend_fragments[ffmpeg.BACKEND_ID]["specialization"]
    assert fragment["id"] == "audio-reactive-colour/v1"
    assert [marker["frame"] for marker in fragment["markers"]] == [3, 8]
    assert fragment["event_count"] == 2
    assert fragment["frame_count"] == 30
    assert fragment["fps"] == 30
    assert len(fragment["marker_sha256"]) == 64


def test_pinned_video_profile_and_level_are_rejected_as_unguaranteed(
    tmp_path: Path,
) -> None:
    """A request pinning video_profile/video_level cannot be guaranteed by
    the FFmpeg command (encoder default or stream-copy preserves source
    values), so support must fail closed instead of failing strict
    post-render validation."""
    request = _request(tmp_path)
    from astrid.core.rendering.contracts import RenderProfile

    base_profile = RenderProfile(
        width=640,
        height=360,
        fps_rational=(30, 1),
        time_base=(1, 15360),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
    )
    request = dataclasses.replace(
        request,
        profile=dataclasses.replace(
            base_profile,
            video_profile="High",
            video_level="40",
        ),
    )
    report = _evaluate(tmp_path, _timeline(), _assets(tmp_path), request=request)
    assert report.supported is False
    assert any("video_profile" in reason or "video_level" in reason for reason in report.reasons)


def _level(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    if normalized.isdigit() and len(normalized) >= 2:
        return f"{int(normalized[:-1])}.{normalized[-1]}"
    return normalized


def _container_matches(probe: MediaProbe, expected: str) -> bool:
    target = expected.lower().lstrip(".")
    probed_container = _text(probe.container)
    if probed_container is not None:
        return probed_container == target
    format_names = {
        item.strip().lower()
        for item in (probe.format_name or "").split(",")
        if item.strip()
    }
    return target in format_names


def _profile_value(profile: RenderProfile, field: str) -> Any:
    return getattr(profile, field)


def _same_profile_value(field: str, actual: Any, expected: Any) -> bool:
    if field in {"fps_rational", "time_base"}:
        try:
            return Fraction(*actual) == Fraction(*expected)
        except (TypeError, ValueError, ZeroDivisionError):
            return False
    if field == "video_level":
        return _level(actual) == _level(expected)
    if field == "pixel_format":
        # ffmpeg's deprecated yuvj* names are full-range variants of the
        # standard yuv* formats (e.g. yuvj420p == yuv420p); treat them as
        # equivalent so strict validation accepts real encoder output.
        return _pixel_format_canonical(actual) == _pixel_format_canonical(expected)
    if field in {
        "container",
        "video_codec",
        "video_profile",
        "audio_codec",
        "audio_channel_layout",
    }:
        return _text(actual) == _text(expected)
    return actual == expected


def _pixel_format_canonical(value: Any) -> str:
    text = _text(value) or ""
    if text.startswith("yuvj"):
        return "yuv" + text[4:]
    return text


def _compare_declared_to_expected(
    declared: RenderProfile,
    expected: RenderProfile,
    ownership: AudioOwnership,
) -> None:
    fields = (
        "width",
        "height",
        "fps_rational",
        "time_base",
        "container",
        "video_codec",
        "pixel_format",
    )
    for field in fields:
        actual_value = _profile_value(declared, field)
        expected_value = _profile_value(expected, field)
        if not _same_profile_value(field, actual_value, expected_value):
            _invalid(
                "profile_mismatch",
                f"renderer video profile has incompatible {field}",
                field=field,
                expected=expected_value,
                actual=actual_value,
            )
    for field in ("video_profile", "video_level"):
        expected_value = _profile_value(expected, field)
        if expected_value is not None and not _same_profile_value(
            field, _profile_value(declared, field), expected_value
        ):
            _invalid(
                "profile_mismatch",
                f"renderer video profile has incompatible {field}",
                field=field,
                expected=expected_value,
                actual=_profile_value(declared, field),
            )

    if ownership is AudioOwnership.RENDERED:
        if not expected.has_audio:
            _invalid(
                "audio_profile_mismatch",
                "renderer declared rendered audio for a visual-only canonical profile",
                expected_audio=False,
                actual_audio=True,
            )
        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
            if not _same_profile_value(
                field, _profile_value(declared, field), _profile_value(expected, field)
            ):
                _invalid(
                    "audio_profile_mismatch",
                    f"renderer audio profile has incompatible {field}",
                    field=field,
                    expected=_profile_value(expected, field),
                    actual=_profile_value(declared, field),
                )
    elif ownership is AudioOwnership.NONE and expected.has_audio:
        _invalid(
            "audio_profile_mismatch",
            "renderer declared no audio for a canonical profile that requires audio",
            expected_audio=True,
                actual=actual,
            )
    if not _container_matches(probe, profile.container):
        _invalid(
            "profile_mismatch",
            f"probed video container does not match {label}",
            field="container",
            expected=profile.container,
            actual=probe.container or probe.format_name,
        )
    for field, actual in (
        ("video_profile", probe.video_profile),
        ("video_level", probe.video_level),
    ):
        expected = _profile_value(profile, field)
        if expected is not None and not _same_profile_value(field, actual, expected):
            _invalid(
                "profile_mismatch",
                f"probed video {field} does not match {label}",
                field=field,
                expected=expected,
                actual=actual,
            )

    if compare_audio:
        for field, actual in (
            ("audio_codec", probe.audio_codec),
            ("audio_sample_rate", probe.audio_sample_rate),
            ("audio_channel_layout", probe.audio_channel_layout),
        ):
            expected = _profile_value(profile, field)
            if field == "audio_channel_layout" and actual is None:
                # Some containers (QuickTime sowt) expose channel COUNT but
                # not a named layout. Compare channel count against the
                # declared layout's canonical count instead of failing.
                expected_channels = _layout_channel_count(expected)
                if expected_channels is None or probe.audio_channels != expected_channels:
                    _invalid(
                        "audio_profile_mismatch",
                        f"probed audio channel layout/count does not match {label}",
                        field=field,

exec
/bin/zsh -lc 'tail -n 140 .oracle/checkins/batch-3-r3.md && git show --format=fuller --no-patch 9bf9db88 && shasum /tmp/batch3-r4.diff && git diff a7b7b080..9bf9db88 > /tmp/batch3-r4-recomputed.diff && shasum /tmp/batch3-r4-recomputed.diff /tmp/batch3-r4.diff' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 252ms:
commit 9bf9db8837fbb9584e4c257d024936b832dce566
Author:     POM <peter@omalley.io>
AuthorDate: Wed Aug 12 14:39:45 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Wed Aug 12 14:39:45 2026 +0200

    batch3-rework4: oracle re-review3 issue 1 (ffmpeg support rejects unguaranteed pinned video_profile/level)
830822cc0e7a3146a20f68033d489a61b894099b  /tmp/batch3-r4.diff
zsh:1: operation not permitted: /tmp/batch3-r4-recomputed.diff

exec
/bin/zsh -lc 'git diff a7b7b080..9bf9db88 | shasum && shasum /tmp/batch3-r4.diff && git diff --check a7b7b080..9bf9db88 && PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/packs/rendering/test_ffmpeg_support.py -k pinned_video_profile_and_level' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 1153ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
830822cc0e7a3146a20f68033d489a61b894099b  -
830822cc0e7a3146a20f68033d489a61b894099b  /tmp/batch3-r4.diff
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-3-r3.md:342: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-3-r3.md:343: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-3-r3.md:345: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-3-r3.md:742: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:747: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:749: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:759: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:768: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:769: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:773: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:780: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:781: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:784: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:785: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:792: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:796: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:800: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:801: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:809: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:810: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:816: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:817: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:820: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:825: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:838: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:839: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:862: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:863: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:866: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:867: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:870: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:871: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:888: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:889: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:892: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:893: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:897: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:898: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:903: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:904: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:926: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:927: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:935: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:936: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:958: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:959: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1021: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1022: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1082: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1083: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1089: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1090: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1110: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1111: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1121: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1131: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1148: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1174: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1199: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1224: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1225: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1238: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1239: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1252: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1264: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1265: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1278: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1367: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1368: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1381: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1421: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1455: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1456: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1460: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1461: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1474: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1475: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1488: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1489: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1520: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1521: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1530: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1531: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1547: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1548: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1562: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1571: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1578: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1579: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1596: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1606: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1613: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1614: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1620: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1622: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1626: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1627: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1636: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1646: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1653: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1654: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1665: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1673: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1677: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1678: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1685: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1691: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1698: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1699: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1708: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1716: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1723: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1725: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1738: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1739: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1743: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1744: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1790: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1791: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1809: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1810: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1825: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1826: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1834: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1835: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1851: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1852: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1877: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1885: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1886: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1890: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1891: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1894: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1902: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1903: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:1946: trailing whitespace.
+   354	
.oracle/checkins/batch-3-r3.md:1961: trailing whitespace.
+   369	
.oracle/checkins/batch-3-r3.md:1962: trailing whitespace.
+   370	
.oracle/checkins/batch-3-r3.md:1965: trailing whitespace.
+   373	
.oracle/checkins/batch-3-r3.md:1966: trailing whitespace.
+   374	
.oracle/checkins/batch-3-r3.md:1970: trailing whitespace.
+   378	
.oracle/checkins/batch-3-r3.md:1971: trailing whitespace.
+   379	
.oracle/checkins/batch-3-r3.md:1976: trailing whitespace.
+   384	
.oracle/checkins/batch-3-r3.md:1977: trailing whitespace.
+   385	
.oracle/checkins/batch-3-r3.md:1984: trailing whitespace.
+    80	
.oracle/checkins/batch-3-r3.md:1988: trailing whitespace.
+    84	
.oracle/checkins/batch-3-r3.md:1989: trailing whitespace.
+    85	
.oracle/checkins/batch-3-r3.md:2000: trailing whitespace.
+    96	
.oracle/checkins/batch-3-r3.md:2001: trailing whitespace.
+    97	
.oracle/checkins/batch-3-r3.md:2010: trailing whitespace.
+   106	
.oracle/checkins/batch-3-r3.md:2011: trailing whitespace.
+   107	
.oracle/checkins/batch-3-r3.md:2034: trailing whitespace.
+    49	
.oracle/checkins/batch-3-r3.md:2036: trailing whitespace.
+    51	
.oracle/checkins/batch-3-r3.md:2038: trailing whitespace.
+    53	
.oracle/checkins/batch-3-r3.md:2040: trailing whitespace.
+    55	
.oracle/checkins/batch-3-r3.md:2048: trailing whitespace.
+    63	
.oracle/checkins/batch-3-r3.md:2050: trailing whitespace.
+    65	
.oracle/checkins/batch-3-r3.md:2057: trailing whitespace.
+    72	
.oracle/checkins/batch-3-r3.md:2059: trailing whitespace.
+    74	
.oracle/checkins/batch-3-r3.md:2061: trailing whitespace.
+    76	
.oracle/checkins/batch-3-r3.md:2063: trailing whitespace.
+    78	
.oracle/checkins/batch-3-r3.md:2068: trailing whitespace.
+   157	
.oracle/checkins/batch-3-r3.md:2083: trailing whitespace.
+   172	
.oracle/checkins/batch-3-r3.md:2133: trailing whitespace.
+   257	
.oracle/checkins/batch-3-r3.md:2154: trailing whitespace.
+   278	
.oracle/checkins/batch-3-r3.md:2157: trailing whitespace.
+   281	
.oracle/checkins/batch-3-r3.md:2191: trailing whitespace.
+   315	
.oracle/checkins/batch-3-r3.md:2198: trailing whitespace.
+   322	
.oracle/checkins/batch-3-r3.md:2213: trailing whitespace.
+   337	
.oracle/checkins/batch-3-r3.md:2230: trailing whitespace.
+   354	
.oracle/checkins/batch-3-r3.md:2245: trailing whitespace.
+   369	
.oracle/checkins/batch-3-r3.md:2246: trailing whitespace.
+   370	
.oracle/checkins/batch-3-r3.md:2249: trailing whitespace.
+   373	
.oracle/checkins/batch-3-r3.md:2250: trailing whitespace.
+   374	
.oracle/checkins/batch-3-r3.md:2254: trailing whitespace.
+   378	
.oracle/checkins/batch-3-r3.md:2255: trailing whitespace.
+   379	
.oracle/checkins/batch-3-r3.md:2260: trailing whitespace.
+   384	
.oracle/checkins/batch-3-r3.md:2261: trailing whitespace.
+   385	
.oracle/checkins/batch-3-r3.md:2337: trailing whitespace.
+   495	
.oracle/checkins/batch-3-r3.md:2338: trailing whitespace.
+   496	
.oracle/checkins/batch-3-r3.md:2380: trailing whitespace.
+   538	
.oracle/checkins/batch-3-r3.md:2381: trailing whitespace.
+   539	
.oracle/checkins/batch-3-r3.md:2406: trailing whitespace.
+   177	
.oracle/checkins/batch-3-r3.md:2407: trailing whitespace.
+   178	
.oracle/checkins/batch-3-r3.md:2410: trailing whitespace.
+   181	
.oracle/checkins/batch-3-r3.md:2415: trailing whitespace.
+   186	
.oracle/checkins/batch-3-r3.md:2420: trailing whitespace.
+   191	
.oracle/checkins/batch-3-r3.md:2421: trailing whitespace.
+   192	
.oracle/checkins/batch-3-r3.md:4022: trailing whitespace.
+    63	
.oracle/checkins/batch-3-r3.md:4024: trailing whitespace.
+    65	
.oracle/checkins/batch-3-r3.md:4031: trailing whitespace.
+    72	
.oracle/checkins/batch-3-r3.md:4033: trailing whitespace.
+    74	
.oracle/checkins/batch-3-r3.md:4035: trailing whitespace.
+    76	
.oracle/checkins/batch-3-r3.md:4037: trailing whitespace.
+    78	
.oracle/checkins/batch-3-r3.md:4042: trailing whitespace.
+   157	
.oracle/checkins/batch-3-r3.md:4057: trailing whitespace.
+   172	
.oracle/checkins/batch-3-r3.md:4185: trailing whitespace.
+   354	
.oracle/checkins/batch-3-r3.md:4200: trailing whitespace.
+   369	
.oracle/checkins/batch-3-r3.md:4201: trailing whitespace.
+   370	
.oracle/checkins/batch-3-r3.md:4204: trailing whitespace.
+   373	
.oracle/checkins/batch-3-r3.md:4205: trailing whitespace.
+   374	
.oracle/checkins/batch-3-r3.md:4209: trailing whitespace.
+   378	
.oracle/checkins/batch-3-r3.md:4210: trailing whitespace.
+   379	
.oracle/checkins/batch-3-r3.md:4215: trailing whitespace.
+   384	
.oracle/checkins/batch-3-r3.md:4216: trailing whitespace.
+   385	
.oracle/checkins/batch-3-r3.md:4342: trailing whitespace.
+   177	
.oracle/checkins/batch-3-r3.md:4343: trailing whitespace.
+   178	
.oracle/checkins/batch-3-r3.md:4346: trailing whitespace.
+   181	
.oracle/checkins/batch-3-r3.md:4351: trailing whitespace.
+   186	
.oracle/checkins/batch-3-r3.md:4356: trailing whitespace.
+   191	
.oracle/checkins/batch-3-r3.md:4357: trailing whitespace.
+   192	
.oracle/checkins/batch-3-r3.md:4455: trailing whitespace.
+   172	
.oracle/checkins/batch-3-r3.md:4497: trailing whitespace.
+   384	
.oracle/checkins/batch-3-r3.md:4498: trailing whitespace.
+   385	
.oracle/checkins/batch-3-r3.md:4600: trailing whitespace.
+     2	
.oracle/checkins/batch-3-r3.md:4602: trailing whitespace.
+     4	
.oracle/checkins/batch-3-r3.md:4609: trailing whitespace.
+    11	
.oracle/checkins/batch-3-r3.md:4612: trailing whitespace.
+    14	
.oracle/checkins/batch-3-r3.md:4614: trailing whitespace.
+    16	
.oracle/checkins/batch-3-r3.md:4615: trailing whitespace.
+    17	
.oracle/checkins/batch-3-r3.md:4618: trailing whitespace.
+    20	
.oracle/checkins/batch-3-r3.md:4619: trailing whitespace.
+    21	
.oracle/checkins/batch-3-r3.md:4635: trailing whitespace.
+    37	
.oracle/checkins/batch-3-r3.md:4636: trailing whitespace.
+    38	
.oracle/checkins/batch-3-r3.md:4641: trailing whitespace.
+    43	
.oracle/checkins/batch-3-r3.md:4642: trailing whitespace.
+    44	
.oracle/checkins/batch-3-r3.md:4647: trailing whitespace.
+    49	
.oracle/checkins/batch-3-r3.md:4648: trailing whitespace.
+    50	
.oracle/checkins/batch-3-r3.md:4651: trailing whitespace.
+    53	
.oracle/checkins/batch-3-r3.md:4669: trailing whitespace.
+    71	
.oracle/checkins/batch-3-r3.md:4670: trailing whitespace.
+    72	
.oracle/checkins/batch-3-r3.md:4674: trailing whitespace.
+    76	
.oracle/checkins/batch-3-r3.md:4675: trailing whitespace.
+    77	
.oracle/checkins/batch-3-r3.md:4684: trailing whitespace.
+    86	
.oracle/checkins/batch-3-r3.md:4687: trailing whitespace.
+    89	
.oracle/checkins/batch-3-r3.md:4698: trailing whitespace.
+   100	
.oracle/checkins/batch-3-r3.md:4706: trailing whitespace.
+   108	
.oracle/checkins/batch-3-r3.md:4707: trailing whitespace.
+   109	
.oracle/checkins/batch-3-r3.md:4712: trailing whitespace.
+   114	
.oracle/checkins/batch-3-r3.md:4718: trailing whitespace.
+   120	
.oracle/checkins/batch-3-r3.md:4728: trailing whitespace.
+   130	
.oracle/checkins/batch-3-r3.md:4729: trailing whitespace.
+   131	
.oracle/checkins/batch-3-r3.md:4740: trailing whitespace.
+   142	
.oracle/checkins/batch-3-r3.md:4741: trailing whitespace.
+   143	
.oracle/checkins/batch-3-r3.md:4775: trailing whitespace.
+   177	
.oracle/checkins/batch-3-r3.md:4776: trailing whitespace.
+   178	
.oracle/checkins/batch-3-r3.md:4779: trailing whitespace.
+   181	
.oracle/checkins/batch-3-r3.md:4784: trailing whitespace.
+   186	
.oracle/checkins/batch-3-r3.md:4789: trailing whitespace.
+   191	
.oracle/checkins/batch-3-r3.md:4790: trailing whitespace.
+   192	
.oracle/checkins/batch-3-r3.md:4802: trailing whitespace.
+   204	
.oracle/checkins/batch-3-r3.md:4803: trailing whitespace.
+   205	
.oracle/checkins/batch-3-r3.md:4818: trailing whitespace.
+   220	
.oracle/checkins/batch-3-r3.md:4824: trailing whitespace.
+   226	
.oracle/checkins/batch-3-r3.md:4836: trailing whitespace.
+   238	
.oracle/checkins/batch-3-r3.md:4837: trailing whitespace.
+   239	
.oracle/checkins/batch-3-r3.md:4848: trailing whitespace.
+   250	
.oracle/checkins/batch-3-r3.md:4853: trailing whitespace.
+   255	
.oracle/checkins/batch-3-r3.md:4862: trailing whitespace.
+     2	
.oracle/checkins/batch-3-r3.md:4866: trailing whitespace.
+     6	
.oracle/checkins/batch-3-r3.md:4868: trailing whitespace.
+     8	
.oracle/checkins/batch-3-r3.md:4877: trailing whitespace.
+    17	
.oracle/checkins/batch-3-r3.md:4879: trailing whitespace.
+    19	
.oracle/checkins/batch-3-r3.md:4881: trailing whitespace.
+    21	
.oracle/checkins/batch-3-r3.md:4882: trailing whitespace.
+    22	
.oracle/checkins/batch-3-r3.md:4886: trailing whitespace.
+    26	
.oracle/checkins/batch-3-r3.md:4887: trailing whitespace.
+    27	
.oracle/checkins/batch-3-r3.md:4891: trailing whitespace.
+    31	
.oracle/checkins/batch-3-r3.md:4894: trailing whitespace.
+    34	
.oracle/checkins/batch-3-r3.md:4900: trailing whitespace.
+    40	
.oracle/checkins/batch-3-r3.md:4902: trailing whitespace.
+    42	
.oracle/checkins/batch-3-r3.md:4921: trailing whitespace.
+    61	
.oracle/checkins/batch-3-r3.md:4925: trailing whitespace.
+    65	
.oracle/checkins/batch-3-r3.md:4927: trailing whitespace.
+    67	
.oracle/checkins/batch-3-r3.md:4931: trailing whitespace.
+    71	
.oracle/checkins/batch-3-r3.md:4933: trailing whitespace.
+    73	
.oracle/checkins/batch-3-r3.md:4941: trailing whitespace.
+    81	
.oracle/checkins/batch-3-r3.md:4947: trailing whitespace.
+    87	
.oracle/checkins/batch-3-r3.md:4948: trailing whitespace.
+    88	
.oracle/checkins/batch-3-r3.md:4951: trailing whitespace.
+    91	
.oracle/checkins/batch-3-r3.md:4952: trailing whitespace.
+    92	
.oracle/checkins/batch-3-r3.md:4955: trailing whitespace.
+    95	
.oracle/checkins/batch-3-r3.md:4968: trailing whitespace.
+   108	
.oracle/checkins/batch-3-r3.md:4969: trailing whitespace.
+   109	
.oracle/checkins/batch-3-r3.md:4980: trailing whitespace.
+   120	
.oracle/checkins/batch-3-r3.md:4981: trailing whitespace.
+   121	
.oracle/checkins/batch-3-r3.md:4986: trailing whitespace.
+   126	
.oracle/checkins/batch-3-r3.md:4987: trailing whitespace.
+   127	
.oracle/checkins/batch-3-r3.md:4994: trailing whitespace.
+   134	
.oracle/checkins/batch-3-r3.md:4995: trailing whitespace.
+   135	
.oracle/checkins/batch-3-r3.md:5012: trailing whitespace.
+   152	
.oracle/checkins/batch-3-r3.md:5013: trailing whitespace.
+   153	
.oracle/checkins/batch-3-r3.md:5016: trailing whitespace.
+   156	
.oracle/checkins/batch-3-r3.md:5022: trailing whitespace.
+   162	
.oracle/checkins/batch-3-r3.md:5027: trailing whitespace.
+   167	
.oracle/checkins/batch-3-r3.md:5031: trailing whitespace.
+   171	
.oracle/checkins/batch-3-r3.md:5048: trailing whitespace.
+   188	
.oracle/checkins/batch-3-r3.md:5051: trailing whitespace.
+   191	
.oracle/checkins/batch-3-r3.md:5057: trailing whitespace.
+   197	
.oracle/checkins/batch-3-r3.md:5065: trailing whitespace.
+   205	
.oracle/checkins/batch-3-r3.md:5073: trailing whitespace.
+   213	
.oracle/checkins/batch-3-r3.md:5079: trailing whitespace.
+   219	
.oracle/checkins/batch-3-r3.md:5091: trailing whitespace.
+   231	
.oracle/checkins/batch-3-r3.md:5093: trailing whitespace.
+   233	
.oracle/checkins/batch-3-r3.md:5094: trailing whitespace.
+   234	
.oracle/checkins/batch-3-r3.md:5106: trailing whitespace.
+   246	
.oracle/checkins/batch-3-r3.md:5136: trailing whitespace.
+   276	
.oracle/checkins/batch-3-r3.md:5163: trailing whitespace.
+   200	
.oracle/checkins/batch-3-r3.md:5176: trailing whitespace.
+   213	
.oracle/checkins/batch-3-r3.md:5247: trailing whitespace.
+   284	
.oracle/checkins/batch-3-r3.md:5267: trailing whitespace.
+   304	
.oracle/checkins/batch-3-r3.md:5279: trailing whitespace.
+   316	
.oracle/checkins/batch-3-r3.md:5298: trailing whitespace.
+   335	
.oracle/checkins/batch-3-r3.md:5299: trailing whitespace.
+   336	
.oracle/checkins/batch-3-r3.md:5312: trailing whitespace.
+   349	
.oracle/checkins/batch-3-r3.md:5313: trailing whitespace.
+   350	
.oracle/checkins/batch-3-r3.md:5351: trailing whitespace.
+   388	
.oracle/checkins/batch-3-r3.md:5366: trailing whitespace.
+   403	
.oracle/checkins/batch-3-r3.md:5367: trailing whitespace.
+   404	
.oracle/checkins/batch-3-r3.md:5401: trailing whitespace.
+   438	
.oracle/checkins/batch-3-r3.md:5402: trailing whitespace.
+   439	
.oracle/checkins/batch-3-r3.md:5408: trailing whitespace.
+   445	
.oracle/checkins/batch-3-r3.md:5416: trailing whitespace.
+   453	
.oracle/checkins/batch-3-r3.md:5434: trailing whitespace.
+   471	
.oracle/checkins/batch-3-r3.md:5435: trailing whitespace.
+   472	
.oracle/checkins/batch-3-r3.md:5447: trailing whitespace.
+   484	
.oracle/checkins/batch-3-r3.md:5462: trailing whitespace.
+   499	
.oracle/checkins/batch-3-r3.md:5463: trailing whitespace.
+   500	
.oracle/checkins/batch-3-r3.md:5470: trailing whitespace.
+   507	
.oracle/checkins/batch-3-r3.md:5474: trailing whitespace.
+   511	
.oracle/checkins/batch-3-r3.md:5475: trailing whitespace.
+   512	
.oracle/checkins/batch-3-r3.md:5486: trailing whitespace.
+   420	
.oracle/checkins/batch-3-r3.md:5508: trailing whitespace.
+   442	
.oracle/checkins/batch-3-r3.md:5509: trailing whitespace.
+   443	
.oracle/checkins/batch-3-r3.md:5569: trailing whitespace.
+   503	
.oracle/checkins/batch-3-r3.md:5570: trailing whitespace.
+   504	
.oracle/checkins/batch-3-r3.md:5578: trailing whitespace.
+   512	
.oracle/checkins/batch-3-r3.md:5579: trailing whitespace.
+   513	
.oracle/checkins/batch-3-r3.md:5627: trailing whitespace.
+   561	
.oracle/checkins/batch-3-r3.md:5628: trailing whitespace.
+   562	
.oracle/checkins/batch-3-r3.md:5634: trailing whitespace.
+   568	
.oracle/checkins/batch-3-r3.md:5635: trailing whitespace.
+   569	
.oracle/checkins/batch-3-r3.md:5641: trailing whitespace.
+   575	
.oracle/checkins/batch-3-r3.md:5642: trailing whitespace.
+   576	
.oracle/checkins/batch-3-r3.md:5655: trailing whitespace.
+   589	
.oracle/checkins/batch-3-r3.md:5656: trailing whitespace.
+   590	
.oracle/checkins/batch-3-r3.md:5661: trailing whitespace.
+     3	
.oracle/checkins/batch-3-r3.md:5663: trailing whitespace.
+     5	
.oracle/checkins/batch-3-r3.md:5674: trailing whitespace.
+    16	
.oracle/checkins/batch-3-r3.md:5681: trailing whitespace.
+    23	
.oracle/checkins/batch-3-r3.md:5718: trailing whitespace.
+    60	
.oracle/checkins/batch-3-r3.md:5719: trailing whitespace.
+    61	
.oracle/checkins/batch-3-r3.md:5723: trailing whitespace.
+    65	
.oracle/checkins/batch-3-r3.md:5724: trailing whitespace.
+    66	
.oracle/checkins/batch-3-r3.md:5730: trailing whitespace.
+    72	
.oracle/checkins/batch-3-r3.md:5731: trailing whitespace.
+    73	
.oracle/checkins/batch-3-r3.md:5740: trailing whitespace.
+    82	
.oracle/checkins/batch-3-r3.md:5756: trailing whitespace.
+    98	
.oracle/checkins/batch-3-r3.md:5764: trailing whitespace.
+   106	
.oracle/checkins/batch-3-r3.md:5771: trailing whitespace.
+   113	
.oracle/checkins/batch-3-r3.md:5784: trailing whitespace.
+   126	
.oracle/checkins/batch-3-r3.md:5785: trailing whitespace.
+   127	
.oracle/checkins/batch-3-r3.md:5795: trailing whitespace.
+   137	
.oracle/checkins/batch-3-r3.md:5828: trailing whitespace.
+   170	
.oracle/checkins/batch-3-r3.md:5859: trailing whitespace.
+   201	
.oracle/checkins/batch-3-r3.md:5860: trailing whitespace.
+   202	
.oracle/checkins/batch-3-r3.md:5862: trailing whitespace.
+   204	
.oracle/checkins/batch-3-r3.md:5863: trailing whitespace.
+   205	
.oracle/checkins/batch-3-r3.md:5890: trailing whitespace.
+   232	
.oracle/checkins/batch-3-r3.md:5891: trailing whitespace.
+   233	
.oracle/checkins/batch-3-r3.md:5897: trailing whitespace.
+   239	
.oracle/checkins/batch-3-r3.md:5900: trailing whitespace.
+   242	
.oracle/checkins/batch-3-r3.md:5901: trailing whitespace.
+   243	
.oracle/checkins/batch-3-r3.md:5903: trailing whitespace.
+   245	
.oracle/checkins/batch-3-r3.md:5904: trailing whitespace.
+   246	
.oracle/checkins/batch-3-r3.md:5907: trailing whitespace.
+   249	
.oracle/checkins/batch-3-r3.md:5917: trailing whitespace.
+     2	
.oracle/checkins/batch-3-r3.md:5922: trailing whitespace.
+     7	
.oracle/checkins/batch-3-r3.md:5924: trailing whitespace.
+     9	
.oracle/checkins/batch-3-r3.md:5931: trailing whitespace.
+    16	
.oracle/checkins/batch-3-r3.md:5934: trailing whitespace.
+    19	
.oracle/checkins/batch-3-r3.md:5935: trailing whitespace.
+    20	
.oracle/checkins/batch-3-r3.md:5939: trailing whitespace.
+    24	
.oracle/checkins/batch-3-r3.md:5950: trailing whitespace.
+    35	
.oracle/checkins/batch-3-r3.md:5951: trailing whitespace.
+    36	
.oracle/checkins/batch-3-r3.md:5963: trailing whitespace.
+    48	
.oracle/checkins/batch-3-r3.md:5964: trailing whitespace.
+    49	
.oracle/checkins/batch-3-r3.md:5967: trailing whitespace.
+    52	
.oracle/checkins/batch-3-r3.md:5975: trailing whitespace.
+    60	
.oracle/checkins/batch-3-r3.md:5988: trailing whitespace.
+    73	
.oracle/checkins/batch-3-r3.md:5989: trailing whitespace.
+    74	
.oracle/checkins/batch-3-r3.md:5992: trailing whitespace.
+    77	
.oracle/checkins/batch-3-r3.md:5996: trailing whitespace.
+    81	
.oracle/checkins/batch-3-r3.md:6003: trailing whitespace.
+    88	
.oracle/checkins/batch-3-r3.md:6004: trailing whitespace.
+    89	
.oracle/checkins/batch-3-r3.md:6010: trailing whitespace.
+    95	
.oracle/checkins/batch-3-r3.md:6011: trailing whitespace.
+    96	
.oracle/checkins/batch-3-r3.md:6016: trailing whitespace.
+   101	
.oracle/checkins/batch-3-r3.md:6017: trailing whitespace.
+   102	
.oracle/checkins/batch-3-r3.md:6023: trailing whitespace.
+   108	
.oracle/checkins/batch-3-r3.md:6046: trailing whitespace.
+   131	
.oracle/checkins/batch-3-r3.md:6047: trailing whitespace.
+   132	
.oracle/checkins/batch-3-r3.md:6074: trailing whitespace.
+   159	
.oracle/checkins/batch-3-r3.md:6075: trailing whitespace.
+   160	
.oracle/checkins/batch-3-r3.md:6080: trailing whitespace.
+   165	
.oracle/checkins/batch-3-r3.md:6115: trailing whitespace.
+   200	
.oracle/checkins/batch-3-r3.md:6128: trailing whitespace.
+   213	
.oracle/checkins/batch-3-r3.md:6161: trailing whitespace.
+   420	
.oracle/checkins/batch-3-r3.md:6183: trailing whitespace.
+   442	
.oracle/checkins/batch-3-r3.md:6184: trailing whitespace.
+   443	
.oracle/checkins/batch-3-r3.md:6244: trailing whitespace.
+   503	
.oracle/checkins/batch-3-r3.md:6245: trailing whitespace.
+   504	
.oracle/checkins/batch-3-r3.md:6253: trailing whitespace.
+   512	
.oracle/checkins/batch-3-r3.md:6254: trailing whitespace.
+   513	
.oracle/checkins/batch-3-r3.md:6302: trailing whitespace.
+   561	
.oracle/checkins/batch-3-r3.md:6303: trailing whitespace.
+   562	
.oracle/checkins/batch-3-r3.md:6309: trailing whitespace.
+   568	
.oracle/checkins/batch-3-r3.md:6310: trailing whitespace.
+   569	
.oracle/checkins/batch-3-r3.md:6316: trailing whitespace.
+   575	
.oracle/checkins/batch-3-r3.md:6317: trailing whitespace.
+   576	
.oracle/checkins/batch-3-r3.md:6330: trailing whitespace.
+   589	
.oracle/checkins/batch-3-r3.md:6331: trailing whitespace.
+   590	
.oracle/checkins/batch-3-r3.md:6342: trailing whitespace.
+   250	
.oracle/checkins/batch-3-r3.md:6347: trailing whitespace.
+   255	
.oracle/checkins/batch-3-r3.md:6359: trailing whitespace.
+   267	
.oracle/checkins/batch-3-r3.md:6368: trailing whitespace.
+   276	
.oracle/checkins/batch-3-r3.md:6384: trailing whitespace.
+   292	
.oracle/checkins/batch-3-r3.md:6385: trailing whitespace.
+   293	
.oracle/checkins/batch-3-r3.md:6399: trailing whitespace.
+   132	
.oracle/checkins/batch-3-r3.md:6406: trailing whitespace.
+   139	
.oracle/checkins/batch-3-r3.md:6407: trailing whitespace.
+   140	
.oracle/checkins/batch-3-r3.md:6410: trailing whitespace.
+   143	
.oracle/checkins/batch-3-r3.md:6434: trailing whitespace.
+   167	
.oracle/checkins/batch-3-r3.md:6435: trailing whitespace.
+   168	
.oracle/checkins/batch-3-r3.md:6441: trailing whitespace.
+   174	
.oracle/checkins/batch-3-r3.md:6442: trailing whitespace.
+   175	
.oracle/checkins/batch-3-r3.md:6447: trailing whitespace.
+   180	
.oracle/checkins/batch-3-r3.md:6448: trailing whitespace.
+   181	
.oracle/checkins/batch-3-r3.md:6462: trailing whitespace.
+   195	
.oracle/checkins/batch-3-r3.md:6463: trailing whitespace.
+   196	
.oracle/checkins/batch-3-r3.md:6470: trailing whitespace.
+   203	
.oracle/checkins/batch-3-r3.md:6471: trailing whitespace.
+   204	
.oracle/checkins/batch-3-r3.md:6481: trailing whitespace.
+   214	
.oracle/checkins/batch-3-r3.md:6482: trailing whitespace.
+   215	
.oracle/checkins/batch-3-r3.md:6485: trailing whitespace.
+   218	
.oracle/checkins/batch-3-r3.md:6491: trailing whitespace.
+   224	
.oracle/checkins/batch-3-r3.md:6492: trailing whitespace.
+   225	
.oracle/checkins/batch-3-r3.md:6501: trailing whitespace.
+   234	
.oracle/checkins/batch-3-r3.md:6502: trailing whitespace.
+   235	
.oracle/checkins/batch-3-r3.md:6507: trailing whitespace.
+   240	
.oracle/checkins/batch-3-r3.md:6508: trailing whitespace.
+   241	
.oracle/checkins/batch-3-r3.md:6517: trailing whitespace.
+   250	
.oracle/checkins/batch-3-r3.md:6518: trailing whitespace.
+   251	
.oracle/checkins/batch-3-r3.md:6524: trailing whitespace.
+   257	
.oracle/checkins/batch-3-r3.md:6525: trailing whitespace.
+   258	
.oracle/checkins/batch-3-r3.md:6538: trailing whitespace.
+   271	
.oracle/checkins/batch-3-r3.md:6539: trailing whitespace.
+   272	
.oracle/checkins/batch-3-r3.md:6544: trailing whitespace.
+   277	
.oracle/checkins/batch-3-r3.md:6545: trailing whitespace.
+   278	
.oracle/checkins/batch-3-r3.md:6552: trailing whitespace.
+   285	
.oracle/checkins/batch-3-r3.md:6553: trailing whitespace.
+   286	
.oracle/checkins/batch-3-r3.md:6560: trailing whitespace.
+   293	
.oracle/checkins/batch-3-r3.md:6561: trailing whitespace.
+   294	
.oracle/checkins/batch-3-r3.md:6570: trailing whitespace.
+   303	
.oracle/checkins/batch-3-r3.md:6571: trailing whitespace.
+   304	
.oracle/checkins/batch-3-r3.md:6578: trailing whitespace.
+   311	
.oracle/checkins/batch-3-r3.md:6579: trailing whitespace.
+   312	
.oracle/checkins/batch-3-r3.md:6588: trailing whitespace.
+   321	
.oracle/checkins/batch-3-r3.md:6589: trailing whitespace.
+   322	
.oracle/checkins/batch-3-r3.md:6644: trailing whitespace.
+   432	
.oracle/checkins/batch-3-r3.md:6661: trailing whitespace.
+   449	
.oracle/checkins/batch-3-r3.md:6662: trailing whitespace.
+   450	
.oracle/checkins/batch-3-r3.md:6666: trailing whitespace.
+   454	
.oracle/checkins/batch-3-r3.md:6680: trailing whitespace.
+   468	
.oracle/checkins/batch-3-r3.md:6728: trailing whitespace.
+   516	
.oracle/checkins/batch-3-r3.md:6732: trailing whitespace.
+   520	
.oracle/checkins/batch-3-r3.md:6751: trailing whitespace.
+   539	
.oracle/checkins/batch-3-r3.md:6784: trailing whitespace.
+   572	
.oracle/checkins/batch-3-r3.md:6785: trailing whitespace.
+   573	
.oracle/checkins/batch-3-r3.md:6792: trailing whitespace.
+   580	
.oracle/checkins/batch-3-r3.md:6797: trailing whitespace.
+   585	
.oracle/checkins/batch-3-r3.md:6803: trailing whitespace.
+   591	
.oracle/checkins/batch-3-r3.md:6804: trailing whitespace.
+   592	
.oracle/checkins/batch-3-r3.md:6808: trailing whitespace.
+   596	
.oracle/checkins/batch-3-r3.md:6813: trailing whitespace.
+   601	
.oracle/checkins/batch-3-r3.md:6825: trailing whitespace.
+   613	
.oracle/checkins/batch-3-r3.md:6830: trailing whitespace.
+   618	
.oracle/checkins/batch-3-r3.md:6842: trailing whitespace.
+   630	
.oracle/checkins/batch-3-r3.md:6854: trailing whitespace.
+   642	
.oracle/checkins/batch-3-r3.md:6855: trailing whitespace.
+   643	
.oracle/checkins/batch-3-r3.md:6879: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6880: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6894: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6903: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6910: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6911: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6928: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6938: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6945: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6946: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6952: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6954: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6958: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6959: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:6968: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7000: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7001: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7019: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7020: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7035: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7036: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7044: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7045: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7061: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7062: trailing whitespace.
+ 
.oracle/checkins/batch-3-r3.md:7081: trailing whitespace.
+     2	
.oracle/checkins/batch-3-r3.md:7083: trailing whitespace.
+     4	
.oracle/checkins/batch-3-r3.md:7091: trailing whitespace.
+    12	
.oracle/checkins/batch-3-r3.md:7094: trailing whitespace.
+    15	
.oracle/checkins/batch-3-r3.md:7103: trailing whitespace.
+    24	
.oracle/checkins/batch-3-r3.md:7104: trailing whitespace.
+    25	
.oracle/checkins/batch-3-r3.md:7119: trailing whitespace.
+    40	
.oracle/checkins/batch-3-r3.md:7120: trailing whitespace.
+    41	
.oracle/checkins/batch-3-r3.md:7128: trailing whitespace.
+    49	
.oracle/checkins/batch-3-r3.md:7129: trailing whitespace.
+    50	
.oracle/checkins/batch-3-r3.md:7140: trailing whitespace.
+    61	
.oracle/checkins/batch-3-r3.md:7141: trailing whitespace.
+    62	
.oracle/checkins/batch-3-r3.md:7161: trailing whitespace.
+    82	
.oracle/checkins/batch-3-r3.md:7170: trailing whitespace.
+    91	
.oracle/checkins/batch-3-r3.md:7171: trailing whitespace.
+    92	
.oracle/checkins/batch-3-r3.md:7188: trailing whitespace.
+   109	
.oracle/checkins/batch-3-r3.md:7189: trailing whitespace.
+   110	
.oracle/checkins/batch-3-r3.md:7207: trailing whitespace.
+   128	
.oracle/checkins/batch-3-r3.md:7208: trailing whitespace.
+   129	
.oracle/checkins/batch-3-r3.md:7231: trailing whitespace.
+   152	
.oracle/checkins/batch-3-r3.md:7232: trailing whitespace.
+   153	
.oracle/checkins/batch-3-r3.md:7277: trailing whitespace.
+   198	
.oracle/checkins/batch-3-r3.md:7278: trailing whitespace.
+   199	
.oracle/checkins/batch-3-r3.md:7287: trailing whitespace.
+   208	
.oracle/checkins/batch-3-r3.md:7288: trailing whitespace.
+   209	
.oracle/checkins/batch-3-r3.md:7308: trailing whitespace.
+   229	
.oracle/checkins/batch-3-r3.md:7309: trailing whitespace.
+   230	
.oracle/checkins/batch-3-r3.md:7325: trailing whitespace.
+   246	
.oracle/checkins/batch-3-r3.md:7326: trailing whitespace.
+   247	
.oracle/checkins/batch-3-r3.md:7329: trailing whitespace.
+   250	
.oracle/checkins/batch-3-r3.md:7330: trailing whitespace.
+   251	
.oracle/checkins/batch-3-r3.md:7338: trailing whitespace.
+   259	
.oracle/checkins/batch-3-r3.md:7339: trailing whitespace.
+   260	
.oracle/checkins/batch-3-r3.md:7351: trailing whitespace.
+   272	
.oracle/checkins/batch-3-r3.md:7352: trailing whitespace.
+   273	
.oracle/checkins/batch-3-r3.md:7355: trailing whitespace.
+   276	
.oracle/checkins/batch-3-r3.md:7356: trailing whitespace.
+   277	
.oracle/checkins/batch-3-r3.md:7379: trailing whitespace.
+   300	
.oracle/checkins/batch-3-r3.md:7387: trailing whitespace.
+   300	
.oracle/checkins/batch-3-r3.md:7388: trailing whitespace.
+   301	
.oracle/checkins/batch-3-r3.md:7394: trailing whitespace.
+   307	
.oracle/checkins/batch-3-r3.md:7395: trailing whitespace.
+   308	
.oracle/checkins/batch-3-r3.md:7433: trailing whitespace.
+   346	
.oracle/checkins/batch-3-r3.md:7460: trailing whitespace.
+   373	
.oracle/checkins/batch-3-r3.md:7461: trailing whitespace.
+   374	
.oracle/checkins/batch-3-r3.md:7492: trailing whitespace.
+   405	
.oracle/checkins/batch-3-r3.md:7493: trailing whitespace.
+   406	
.oracle/checkins/batch-3-r3.md:7540: trailing whitespace.
+   453	
.oracle/checkins/batch-3-r3.md:7584: trailing whitespace.
+   456	
.oracle/checkins/batch-3-r3.md:7585: trailing whitespace.
+   457	
.oracle/checkins/batch-3-r3.md:7590: trailing whitespace.
+   462	
.oracle/checkins/batch-3-r3.md:7591: trailing whitespace.
+   463	
.oracle/checkins/batch-3-r3.md:7638: trailing whitespace.
+   510	
.oracle/checkins/batch-3-r3.md:7639: trailing whitespace.
+   511	
.oracle/checkins/batch-3-r3.md:7649: trailing whitespace.
+   521	
.oracle/checkins/batch-3-r3.md:7650: trailing whitespace.
+   522	
.oracle/checkins/batch-3-r3.md:7664: trailing whitespace.
+   536	
.oracle/checkins/batch-3-r3.md:7683: trailing whitespace.
+   555	
.oracle/checkins/batch-3-r3.md:7752: trailing whitespace.
+   423	
.oracle/checkins/batch-3-r3.md:7760: trailing whitespace.
+   431	
.oracle/checkins/batch-3-r3.md:7763: trailing whitespace.
+   434	
.oracle/checkins/batch-3-r3.md:7764: trailing whitespace.
+   435	
.oracle/checkins/batch-3-r3.md:7793: trailing whitespace.
+   464	
.oracle/checkins/batch-3-r3.md:7800: trailing whitespace.
+   471	
.oracle/checkins/batch-3-r3.md:7813: trailing whitespace.
+   484	
.oracle/checkins/batch-3-r3.md:7819: trailing whitespace.
+   490	
.oracle/checkins/batch-3-r3.md:7820: trailing whitespace.
+   491	
.oracle/checkins/batch-3-r3.md:7864: trailing whitespace.
+   535	
.oracle/checkins/batch-3-r3.md:7865: trailing whitespace.
+   536	
.oracle/checkins/batch-3-r3.md:7890: trailing whitespace.
+   561	
.oracle/checkins/batch-3-r3.md:7896: trailing whitespace.
+   567	
.oracle/checkins/batch-3-r3.md:7915: trailing whitespace.
+   586	
.oracle/checkins/batch-3-r3.md:7923: trailing whitespace.
+   594	
.oracle/checkins/batch-3-r3.md:7930: trailing whitespace.
+   601	
.oracle/checkins/batch-3-r3.md:7949: trailing whitespace.
+   119	
.oracle/checkins/batch-3-r3.md:7950: trailing whitespace.
+   120	
.oracle/checkins/batch-3-r3.md:7959: trailing whitespace.
+   129	
.oracle/checkins/batch-3-r3.md:7960: trailing whitespace.
+   130	
.oracle/checkins/batch-3-r3.md:7976: trailing whitespace.
+   146	
.oracle/checkins/batch-3-r3.md:7977: trailing whitespace.
+   147	
.oracle/checkins/batch-3-r3.md:7991: trailing whitespace.
+   161	
.oracle/checkins/batch-3-r3.md:8004: trailing whitespace.
+   328	
.oracle/checkins/batch-3-r3.md:8005: trailing whitespace.
+   329	
.oracle/checkins/batch-3-r3.md:8011: trailing whitespace.
+   335	
.oracle/checkins/batch-3-r3.md:8018: trailing whitespace.
+   342	
.oracle/checkins/batch-3-r3.md:8858: trailing whitespace.
+   590	
.oracle/checkins/batch-3-r3.md:8868: trailing whitespace.
+   600	
.oracle/checkins/batch-3-r3.md:8878: trailing whitespace.
+   610	
.oracle/checkins/batch-3-r3.md:8895: trailing whitespace.
+   627	
.oracle/checkins/batch-3-r3.md:8921: trailing whitespace.
+   653	
.oracle/checkins/batch-3-r3.md:8946: trailing whitespace.
+   678	
.oracle/checkins/batch-3-r3.md:8983: trailing whitespace.
+   715	
.oracle/checkins/batch-3-r3.md:9001: trailing whitespace.
+   733	
.oracle/checkins/batch-3-r3.md:9020: trailing whitespace.
+   752	
.oracle/checkins/batch-3-r3.md:9022: trailing whitespace.
+   754	
.oracle/checkins/batch-3-r3.md:9033: trailing whitespace.
+   765	
.oracle/checkins/batch-3-r3.md:9034: trailing whitespace.
+   766	
.oracle/checkins/batch-3-r3.md:9066: trailing whitespace.
+   885	
.oracle/checkins/batch-3-r3.md:9067: trailing whitespace.
+   886	
.oracle/checkins/batch-3-r3.md:9083: trailing whitespace.
+   902	
.oracle/checkins/batch-3-r3.md:9084: trailing whitespace.
+   903	
.oracle/checkins/batch-3-r3.md:9099: trailing whitespace.
+   918	
.oracle/checkins/batch-3-r3.md:9100: trailing whitespace.
+   919	
.oracle/checkins/batch-3-r3.md:9103: trailing whitespace.
+   922	
.oracle/checkins/batch-3-r3.md:9122: trailing whitespace.
+   941	
.oracle/checkins/batch-3-r3.md:9127: trailing whitespace.
+   946	
.oracle/checkins/batch-3-r3.md:9144: trailing whitespace.
+   963	
.oracle/checkins/batch-3-r3.md:9212: trailing whitespace.
+  1031	
.oracle/checkins/batch-3-r3.md:9220: trailing whitespace.
+  1039	
.oracle/checkins/batch-3-r3.md:9230: trailing whitespace.
+  1049	
.oracle/checkins/batch-3-r3.md:9231: trailing whitespace.
+  1050	
.oracle/checkins/batch-3-r3.md:9243: trailing whitespace.
+  1061	
.oracle/checkins/batch-3-r3.md:9244: trailing whitespace.
+  1062	
.oracle/checkins/batch-3-r3.md:9254: trailing whitespace.
+  1072	
.oracle/checkins/batch-3-r3.md:9265: trailing whitespace.
+  1083	
.oracle/checkins/batch-3-r3.md:9311: trailing whitespace.
+  1129	
.oracle/checkins/batch-3-r3.md:9357: trailing whitespace.
+  1175	
.oracle/checkins/batch-3-r3.md:9358: trailing whitespace.
+  1176	
.oracle/checkins/batch-3-r3.md:9364: trailing whitespace.
+  1182	
.oracle/checkins/batch-3-r3.md:9365: trailing whitespace.
+  1183	
.oracle/checkins/batch-3-r3.md:9385: trailing whitespace.
+  1203	
.oracle/checkins/batch-3-r3.md:9386: trailing whitespace.
+  1204	
.oracle/checkins/batch-3-r3.md:10086: trailing whitespace.
+   140	
.oracle/checkins/batch-3-r3.md:10088: trailing whitespace.
+   142	
.oracle/checkins/batch-3-r3.md:10093: trailing whitespace.
+   147	
.oracle/checkins/batch-3-r3.md:10095: trailing whitespace.
+   149	
.oracle/checkins/batch-3-r3.md:10099: trailing whitespace.
+   153	
.oracle/checkins/batch-3-r3.md:10109: trailing whitespace.
+   163	
.oracle/checkins/batch-3-r3.md:10116: trailing whitespace.
+   170	
.oracle/checkins/batch-3-r3.md:10118: trailing whitespace.
+   172	
.oracle/checkins/batch-3-r3.md:10121: trailing whitespace.
+   175	
.oracle/checkins/batch-3-r3.md:10130: trailing whitespace.
+   184	
.oracle/checkins/batch-3-r3.md:10135: trailing whitespace.
+   189	
.oracle/checkins/batch-3-r3.md:10137: trailing whitespace.
+   191	
.oracle/checkins/batch-3-r3.md:10139: trailing whitespace.
+   193	
.oracle/checkins/batch-3-r3.md:10150: trailing whitespace.
+   204	
.oracle/checkins/batch-3-r3.md:10154: trailing whitespace.
+   208	
.oracle/checkins/batch-3-r3.md:10168: trailing whitespace.
+   251	
.oracle/checkins/batch-3-r3.md:10172: trailing whitespace.
+   255	
.oracle/checkins/batch-3-r3.md:10174: trailing whitespace.
+   257	
.oracle/checkins/batch-3-r3.md:10179: trailing whitespace.
+   262	
.oracle/checkins/batch-3-r3.md:10191: trailing whitespace.
+   274	
.oracle/checkins/batch-3-r3.md:10193: trailing whitespace.
+   276	
.oracle/checkins/batch-3-r3.md:10197: trailing whitespace.
+   280	
.oracle/checkins/batch-3-r3.md:10207: trailing whitespace.
+   290	
.oracle/checkins/batch-3-r3.md:10209: trailing whitespace.
+   292	
.oracle/checkins/batch-3-r3.md:10215: trailing whitespace.
+   298	
.oracle/checkins/batch-3-r3.md:10217: trailing whitespace.
+   300	
.oracle/checkins/batch-3-r3.md:10228: trailing whitespace.
+   311	
.oracle/checkins/batch-3-r3.md:10234: trailing whitespace.
+   317	
.oracle/checkins/batch-3-r3.md:10236: trailing whitespace.
+   319	
.oracle/checkins/batch-3-r3.md:10238: trailing whitespace.
+   321	
.oracle/checkins/batch-3-r3.md:10246: trailing whitespace.
+   329	
.oracle/checkins/batch-3-r3.md:10249: trailing whitespace.
+   571	
.oracle/checkins/batch-3-r3.md:10251: trailing whitespace.
+   573	
.oracle/checkins/batch-3-r3.md:10295: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-3-r3.md:10296: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-3-r3.md:10298: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 

codex
The supplied diff exactly matches `a7b7b080..9bf9db88`. The implementation now rejects both fields before support can return true; I’m exercising the new regression and a few single-field edge cases next.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/packs/rendering/test_ffmpeg_support.py -k pinned_video_profile_and_level' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 1939ms:
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
/bin/zsh -lc "python3 -B -c 'import dataclasses; from astrid.core.rendering.contracts import RenderProfile, RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import _profile_support_reasons; t={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":30}}}}; p=RenderProfile(width=640,height=360,fps_rational=(30,1),time_base=(1,15360),video_codec=\"h264\",pixel_format=\"yuv420p\"); q=RenderRequest(timeline_path=\"timeline.json\",profile=p); cases=[(\"profile-only\",dataclasses.replace(q,profile=dataclasses.replace(p,video_profile=\"High\"))),(\"level-only\",dataclasses.replace(q,profile=dataclasses.replace(p,video_level=\"40\"))),(\"unpinned\",q)]; print([(name,_profile_support_reasons(req,t)) for name,req in cases])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 1104ms:
Traceback (most recent call last):
  File "<string>", line 1, in <module>
TypeError: RenderRequest.__init__() missing 2 required positional arguments: 'schema_version' and 'output_name'

exec
/bin/zsh -lc "rg -n '"'^class RenderRequest'"' astrid/core/rendering/contracts.py && sed -n '575,680p' astrid/core/rendering/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
775:class RenderRequest:
    profile: RenderProfile,
    ownership: AudioOwnership | None,
    label: str,
) -> None:
    """Keep probed media audio and ownership semantically aligned.

    ``rendered`` means the artifact itself contains audio and therefore has a
    populated audio profile. ``passthrough`` and ``none`` describe visual-only
    artifacts; the former asks the host/finalizer to supply canonical audio.
    """

    if profile.has_audio:
        if ownership is not AudioOwnership.RENDERED:
            raise ValueError(f"{label} with an audio profile must declare audio='rendered'")
    elif ownership is AudioOwnership.RENDERED:
        raise ValueError(f"{label} with audio='rendered' must have an audio profile")


@dataclass(frozen=True)
class Attachment:
    """A named, opaque artifact preserved alongside the primary video."""

    name: str
    path: str
    kind: str
    sha256: str

    def __post_init__(self) -> None:
        name = _require_string(self.name, "attachment name")
        if not _OUTPUT_NAME_RE.fullmatch(name):
            raise ValueError("attachment name must be a portable basename")
        kind = _require_string(self.kind, "attachment kind")
        if not _KIND_RE.fullmatch(kind):
            raise ValueError("attachment kind must be a lowercase hyphenated token")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "attachment sha256"))

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {"name": self.name, "path": self.path, "kind": self.kind, "sha256": self.sha256}
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Attachment:
        data = _require_mapping(payload, "attachment")
        required = {"name", "path", "kind", "sha256"}
        _validate_object_keys(data, required=required, allowed=required, label="attachment")
        return cls(
            name=data["name"],
            path=data["path"],
            kind=data["kind"],
            sha256=data["sha256"],
        )

    @classmethod
    def from_file(
        cls,
        *,
        name: str,
        path: str | Path,
        kind: str,
        workspace_root: str | Path,
    ) -> Attachment:
        relative, resolved = _relative_file_path(path, workspace_root, "attachment path")
        return cls(name=name, path=relative, kind=kind, sha256=sha256_file(resolved))


def _coerce_attachment_mapping(value: Any, label: str) -> dict[str, Attachment]:
    mapping = _require_mapping(value, label)
    result: dict[str, Attachment] = {}
    seen_names: set[str] = set()
    for raw_key, raw_attachment in mapping.items():
        key = _require_string(raw_key, f"{label} key")
        attachment = (
            raw_attachment
            if isinstance(raw_attachment, Attachment)
            else Attachment.from_dict(_require_mapping(raw_attachment, f"{label}[{key!r}]"))
        )
        if attachment.name != key:
            raise ValueError(
                f"{label} key {key!r} must match attachment.name {attachment.name!r}"
            )
        if attachment.name in seen_names:
            raise ValueError(f"duplicate attachment name: {attachment.name}")
        seen_names.add(attachment.name)
        result[key] = attachment
    return result


@dataclass(frozen=True)
class VideoArtifact:
    """The required primary video produced by a renderer or finalizer."""

    path: str
    profile: RenderProfile
    sha256: str
    duration_frames: int
    audio: AudioOwnership | None = None
    attachments: dict[str, Attachment] = field(default_factory=dict)

    def __post_init__(self) -> None:
        profile = (
            self.profile
            if isinstance(self.profile, RenderProfile)

exec
/bin/zsh -lc "sed -n '750,885p' astrid/core/rendering/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    if value is None and nullable:
        return None
    if isinstance(value, RenderProfile):
        return value
    return RenderProfile.from_dict(_require_mapping(value, label))


def _coerce_window(value: Any, label: str, *, nullable: bool) -> FrameWindow | None:
    if value is None and nullable:
        return None
    if isinstance(value, FrameWindow):
        return value
    return FrameWindow.from_dict(_require_mapping(value, label))


def _coerce_namespaced_backend_config(value: Any, label: str) -> BackendConfig:
    mapping = _require_mapping(value, label)
    result: BackendConfig = {}
    for raw_backend, raw_config in mapping.items():
        backend = _require_qualified_id(raw_backend, f"{label} key")
        result[backend] = _json_safe_mapping(raw_config, label=f"{label}[{backend!r}]")
    return result


@dataclass(frozen=True)
class RenderRequest:
    """Backend-neutral request shared by render, support, and plan operations."""

    schema_version: int
    timeline_path: str
    output_name: str
    assets_registry_path: str | None = None
    window: FrameWindow | None = None
    audio: AudioOwnership | None = None
    profile: RenderProfile | None = None
    backend_config: BackendConfig = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            _protocol_failure(
                f"unknown or malformed render request schema_version "
                f"{self.schema_version!r}; expected integer {SCHEMA_VERSION}",
                details={"received": self.schema_version, "supported": [SCHEMA_VERSION]},
            )
        version = self.schema_version
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "timeline_path", _require_string(self.timeline_path, "timeline_path"))
        object.__setattr__(
            self,
            "assets_registry_path",
            _require_optional_string(self.assets_registry_path, "assets_registry_path"),
        )
        output_name = _require_string(self.output_name, "output_name")
        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
            raise ValueError("output_name must be a portable basename without path separators")
        object.__setattr__(self, "output_name", output_name)
        object.__setattr__(self, "window", _coerce_window(self.window, "window", nullable=True))
        audio = _coerce_audio_ownership(self.audio, "audio", nullable=True)
        profile = _coerce_profile(self.profile, "profile", nullable=True)
        if audio is not None and profile is not None:
            _validate_artifact_audio(profile, audio, "render request")
        object.__setattr__(self, "audio", audio)
        object.__setattr__(self, "profile", profile)
        object.__setattr__(
            self,
            "backend_config",
            _coerce_namespaced_backend_config(self.backend_config, "backend_config"),
        )
        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "timeline_path": self.timeline_path,
                "assets_registry_path": self.assets_registry_path,
                "output_name": self.output_name,
                "window": self.window,
                "audio": self.audio,
                "profile": self.profile,
                "backend_config": self.backend_config,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderRequest:
        try:
            data = _require_mapping(payload, "render request")
            allowed = {
                "schema_version",
                "timeline_path",
                "assets_registry_path",
                "output_name",
                "window",
                "audio",
                "profile",
                "backend_config",
                "metadata",
            }
            _validate_object_keys(
                data,
                required={"schema_version", "timeline_path", "output_name"},
                allowed=allowed,
                label="render request",
            )
            version = data["schema_version"]
            if type(version) is not int or version != SCHEMA_VERSION:
                _protocol_failure(
                    f"unknown or malformed render request schema_version {version!r}; "
                    f"expected integer {SCHEMA_VERSION}",
                    details={"received": version, "supported": [SCHEMA_VERSION]},
                )
            return cls(
                schema_version=version,
                timeline_path=data["timeline_path"],
                assets_registry_path=data.get("assets_registry_path"),
                output_name=data["output_name"],
                window=data.get("window"),
                audio=data.get("audio"),
                profile=data.get("profile"),
                backend_config=data.get("backend_config", {}),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed render request: {exc}",
                details={"error_type": type(exc).__name__},
            )

    def for_backend(self, backend: str) -> RenderRequest:

exec
/bin/zsh -lc "python3 -B -c 'import dataclasses; from astrid.core.rendering.contracts import SCHEMA_VERSION, RenderProfile, RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import _profile_support_reasons; t={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":30}}}}; p=RenderProfile(width=640,height=360,fps_rational=(30,1),time_base=(1,15360),video_codec=\"h264\",pixel_format=\"yuv420p\"); q=RenderRequest(schema_version=SCHEMA_VERSION,timeline_path=\"timeline.json\",output_name=\"out.mp4\",profile=p); cases=[(\"profile-only\",dataclasses.replace(q,profile=dataclasses.replace(p,video_profile=\"High\"))),(\"level-only\",dataclasses.replace(q,profile=dataclasses.replace(p,video_level=\"40\"))),(\"unpinned\",q)]; print([(name,_profile_support_reasons(req,t)) for name,req in cases])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1483ms:
[('profile-only', ["requested profile video_profile='High' cannot be guaranteed by rendering.ffmpeg (encoder default or stream-copy preserves source values; omit video_profile to use defaults)"]), ('level-only', ["requested profile video_level='40' cannot be guaranteed by rendering.ffmpeg (encoder default or stream-copy preserves source values; omit video_level to use defaults)"]), ('unpinned', [])]

exec
/bin/zsh -lc "sed -n '47,73p' .oracle/tasklist.md && rg -n '"'^'"\\[tool\\]|"'^'"\\[done\\]|passed|failed|ruff|format|check' .oracle/checkins/batch-3-r3.md | tail -n 80 && awk 'length("'$0)>100 {print FNR ":" length($0) ":" $0}'"' tests/packs/rendering/test_ffmpeg_support.py | tail -n 20" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]

## Batch 3 — Built-in renderer and finalizer extraction

**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
- One non-recursive cross-process lock spans registry-state reads, all registry/shim/theme-pointer writes, active-theme selection, the complete Remotion render, and the `gen-types` writer path.
- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.

### Tasks

- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.

## Batch 4 — Generic routing, provenance, and hybrid planning
8211:Makefile:19:check: structure doctor ruff mypy cycles
8212:Makefile:30:ruff:
8213:Makefile:31:	@$(PY) scripts/reshape/compare_ruff_baseline.py
8214:Makefile:32:	@echo "✓ ruff baseline (no lint regression)"
8215:pyproject.toml:43:    "ruff==0.12.0",
8216:pyproject.toml:60:[tool.ruff]
8218:pyproject.toml:73:[tool.ruff.lint]
8219:.github/workflows/ci.yml:65:          python scripts/reshape/compare_ruff_baseline.py
8265:astrid/packs/rendering/backends/ffmpeg/support.py-500-        and (media_probe.pixel_format or "") == "yuv420p"
8276:astrid/packs/rendering/backends/ffmpeg/support.py-528-    checks = (
8283:astrid/packs/rendering/backends/ffmpeg/support.py-535-        ("pixel_format", profile.pixel_format, "yuv420p"),
8285:astrid/packs/rendering/backends/ffmpeg/support.py-537-    for field, requested, produced in checks:
8313:astrid/core/rendering/profile.py-286-        pixel_format="yuv420p",
8317:/bin/zsh -lc "command -v ruff || true
8318:if command -v ruff >/dev/null 2>&1; then ruff check --no-cache astrid/packs/rendering/backends/ffmpeg/support.py astrid/packs/rendering/backends/remotion/run.py tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_support.py; fi
8321:/Users/peteromalley/.pyenv/shims/ruff
8322:astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
8369:astrid/packs/rendering/backends/remotion/run.py:34:1: I001 [*] Import block is un-sorted or un-formatted
8461:tests/packs/rendering/test_ffmpeg_backend.py:1:1: I001 [*] Import block is un-sorted or un-formatted
8494:tests/packs/rendering/test_ffmpeg_support.py:1:1: I001 [*] Import block is un-sorted or un-formatted
8551:[tool.ruff]
8564:[tool.ruff.lint]
8589:/bin/zsh -lc "sed -n '1,300p' scripts/reshape/compare_ruff_baseline.py
8591:rg --files | rg 'ruff.*baseline|baseline.*ruff'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8603:BASELINE_PATH = Path("scripts/reshape/baselines/ruff_astrid.json")
8607:    "ruff",
8608:    "check",
8610:    "--output-format",
8616:    proc = subprocess.run(COMMAND, capture_output=True, text=True, check=False)
8625:        "tool": "ruff",
8626:        "scope": ["pyproject.toml [tool.ruff].include"],
8656:scripts/reshape/baselines/ruff_astrid.json
8657:scripts/reshape/compare_ruff_baseline.py
8660:/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 python scripts/reshape/compare_ruff_baseline.py; status=$?; echo exit=$status; cat scripts/reshape/baselines/ruff_astrid.json' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8662:error: Failed to initialize cache at /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.ruff_cache: Operation not permitted (os error 1)
8663:error: Failed to initialize cache at /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.ruff_cache: Operation not permitted (os error 1)
8664:ruff failed
8666:  Cause: No such file or directory (os error 2) at path "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.ruff_cache/0.12.0/.tmpJ0hrfG"
8670:/bin/zsh -lc 'RUFF_CACHE_DIR=/tmp/astrid-oracle-r3-ruff-cache PYTHONDONTWRITEBYTECODE=1 python scripts/reshape/compare_ruff_baseline.py; exit_code=$?; echo exit=$exit_code; sed -n '"'1,80p' scripts/reshape/baselines/ruff_astrid.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8672:error: Failed to initialize cache at /tmp/astrid-oracle-r3-ruff-cache: Operation not permitted (os error 1)
8673:error: Failed to initialize cache at /tmp/astrid-oracle-r3-ruff-cache: Operation not permitted (os error 1)
8674:ruff failed
8676:  Cause: No such file or directory (os error 2) at path "/tmp/astrid-oracle-r3-ruff-cache/0.12.0/.tmpLV6hu1"
8679:  "tool": "ruff",
8681:    "pyproject.toml [tool.ruff].include"
8686:    "ruff",
8687:    "check",
8689:    "--output-format",
8706:/bin/zsh -lc "ruff check . --no-cache --output-format json 2>/dev/null | PYTHONDONTWRITEBYTECODE=1 python -c 'import json,sys,collections; x=json.load(sys.stdin); print(len(x)); print(dict(collections.Counter(i[\"code\"] for i in x)))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8715:git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8751:git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8779:# execution must make the owning checkout importable before SDK imports.
8830:ruff check --no-cache astrid/packs/rendering/backends/ffmpeg/support.py --output-format concise 2>/dev/null || true
8832:git show 58473c3a:astrid/packs/rendering/backends/ffmpeg/support.py | ruff check --no-cache --stdin-filename astrid/packs/rendering/backends/ffmpeg/support.py --output-format concise - 2>/dev/null || true' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8834:astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
8840:git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8841:astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
8848:/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from astrid.core.media import MediaProbe; from astrid.core.rendering.contracts import RenderProfile,RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import _profile_support_reasons,_whole_media_optimization; timeline={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":60}}},\"tracks\":[{\"id\":\"v\",\"kind\":\"visual\"}],\"clips\":[{\"id\":\"c\",\"track\":\"v\",\"clipType\":\"media\",\"asset\":\"video\",\"at\":0,\"from\":0,\"to\":1}]}; assets={\"assets\":{\"video\":{\"duration\":1,\"resolution\":\"640x360\",\"fps\":60}}}; request=RenderRequest(schema_version=1,timeline_path=\"timeline.json\",assets_registry_path=\"assets.json\",output_name=\"out.mp4\",profile=RenderProfile(width=640,height=360,fps_rational=(120,2),time_base=(2,30720),container=\"mp4\",video_codec=\"h264\",video_profile=\"Constrained Baseline\",video_level=\"5.2\",pixel_format=\"yuv420p\")); print(\"profile_reasons=\",_profile_support_reasons(request,timeline)); base=dict(width=640,height=360,fps=60,video_codec=\"h264\",pixel_format=\"yuv420p\",video_stream_present=True); print(\"copy canonical=\",_whole_media_optimization(timeline,assets,{\"video\":MediaProbe(duration_seconds=1,time_base=(1,15360),**base)})); print(\"copy 90k=\",_whole_media_optimization(timeline,assets,{\"video\":MediaProbe(duration_seconds=1,time_base=(1,90000),**base)})); print(\"copy extra frame=\",_whole_media_optimization(timeline,assets,{\"video\":MediaProbe(duration_seconds=1+1/60,time_base=(1,15360),**base)}))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
9045:/bin/zsh -lc 'for fps_value in 24 30 60; do echo fps=$fps_value; ffmpeg -v error -f lavfi -i "color=c=black:s=16x16:r=$fps_value" -frames:v 4 -vf "fps=$fps_value,format=yuv420p" -c:v libx264 -preset veryfast -crf 20 -movflags frag_keyframe+empty_moov -f mp4 pipe:1 | ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate,time_base -of default=noprint_wrappers=1 pipe:0; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
9465:docs/contracts/render-backend-v1.md-178-- non-empty `container`, `video_codec`, and `pixel_format`;
9500:astrid/packs/rendering/finalizers/ffmpeg/run.py-66-        "pixel_format",
9537:astrid/packs/rendering/finalizers/ffmpeg/run.py-181-        pixel_format=profile.pixel_format,
9556:astrid/packs/rendering/finalizers/ffmpeg/run.py-229-        "pixel_format",
9639:astrid/packs/rendering/finalizers/ffmpeg/run.py-338-def _format_value(value: Any) -> str:
9729:astrid/packs/rendering/finalizers/ffmpeg/run.py-562-            filters.append(f"format={target_profile.pixel_format}")
9756:astrid/packs/rendering/finalizers/ffmpeg/run.py-589-        argv.extend(["-pix_fmt", target_profile.pixel_format])
9813:astrid/packs/rendering/finalizers/ffmpeg/run.py-828-        pixel_format=_required_probe_value(probe.pixel_format, "pixel format"),
9972:astrid/packs/rendering/backends/ffmpeg/run.py-492-        pixel_format=_required(probe.pixel_format, "pixel format"),
10054:docs/contracts/render-backend-v1.md-71-| `required_binaries` | Unique binary names checked before invocation. |
10124:   178	- non-empty `container`, `video_codec`, and `pixel_format`;
10171:   254	pixel format, and declared audio state before assembly or publication.
10286:The repo’s `contextminning-subagentmaxxing` guidance also applies to this multi-step review; I’m using it to keep the independent adversarial audit isolated and bring back only its conclusion. The direct check has already exposed one fail-closed profile gap that the passing suite does not exercise.
10332:check whether you're minning at the right seams or letting context balloon to
10351:research, a sense-check, a contained fix. Once something is more than ~a day or two of
10372:That posture points to `subagent-launcher` for shaping the independent review, so I’m applying its bounded, conclusion-only brief discipline to the adversarial check already in flight.
10378:description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
10438:Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.
10448:The launcher discovers the active runtime itself. It first tries an installed legacy `megaplan.agent` distribution, then falls back to the current Arnold checkout (`~/Documents/Arnold` by default, or `ARNOLD_PATH=/path/to/Arnold`). Do not add an `arnold_pipelines.megaplan.agent` compatibility package to fix import failures; the real Hermes runtime lives under `arnold_pipelines.megaplan.agent` in the Arnold checkout.
10472:- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
10582:Send the same unbiased prompt to several models in parallel (Codex + hermes-DeepSeek + hermes-Kimi, optionally a Claude `Agent`) and compare — convergence on a subtle call is far stronger than one model's confidence; divergence is signal. Reserve it for risky pre-merge reviews, hard-to-reverse architecture calls, security-sensitive paths. Don't fan out routine work. For a multi-lens sense-check of one proposal (human-user / agent-user / abstraction lenses), give each agent only its own lens and never show one's output to another.

exec
/bin/zsh -lc 'ruff check --no-cache astrid/packs/rendering/backends/ffmpeg/support.py tests/packs/rendering/test_ffmpeg_support.py --output-format concise || true

git show a7b7b080:tests/packs/rendering/test_ffmpeg_support.py | ruff check --no-cache --stdin-filename tests/packs/rendering/test_ffmpeg_support.py --output-format concise - || true' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 3379ms:
astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
astrid/packs/rendering/backends/ffmpeg/support.py:691:20: BLE001 Do not catch blind exception: `Exception`
astrid/packs/rendering/backends/ffmpeg/support.py:744:16: BLE001 Do not catch blind exception: `Exception`
tests/packs/rendering/test_ffmpeg_support.py:1:1: I001 [*] Import block is un-sorted or un-formatted
tests/packs/rendering/test_ffmpeg_support.py:230:5: E731 Do not assign a `lambda` expression, use a `def`
tests/packs/rendering/test_ffmpeg_support.py:293:9: E731 Do not assign a `lambda` expression, use a `def`
Found 6 errors.
[*] 2 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
tests/packs/rendering/test_ffmpeg_support.py:1:1: I001 [*] Import block is un-sorted or un-formatted
tests/packs/rendering/test_ffmpeg_support.py:229:5: E731 Do not assign a `lambda` expression, use a `def`
tests/packs/rendering/test_ffmpeg_support.py:292:9: E731 Do not assign a `lambda` expression, use a `def`
Found 3 errors.
[*] 1 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).

exec
/bin/zsh -lc "rg -n '"'^def (_registry_path|_asset_path|_evaluate)'"' astrid/packs/rendering/backends/ffmpeg/support.py tests/packs/rendering/test_ffmpeg_support.py && sed -n '80,170p' astrid/packs/rendering/backends/ffmpeg/support.py && sed -n '115,180p' tests/packs/rendering/test_ffmpeg_support.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/ffmpeg/support.py:383:def _registry_path(request: RenderRequest) -> Path:
astrid/packs/rendering/backends/ffmpeg/support.py:389:def _asset_path(
tests/packs/rendering/test_ffmpeg_support.py:140:def _evaluate(

    Track mute is authoritative; otherwise track and clip gains multiply.  A
    missing gain means unity, while malformed or out-of-range values are
    rejected instead of clamped.
    """

    muted = track.get("muted", False)
    if not isinstance(muted, bool):
        raise ValueError(f"Track {track.get('id')!r} muted must be a boolean")
    track_gain = _gain(
        track.get("volume"),
        f"Track {track.get('id')!r} volume",
    )
    clip_gain = _gain(
        clip.get("volume"),
        f"Clip {clip.get('id')!r} volume",
    )
    return 0.0 if muted else track_gain * clip_gain


def _clip_range(clip: Mapping[str, Any]) -> _ClipRange:
    clip_id = clip.get("id")
    at = _number(clip.get("at", 0), f"Clip {clip_id!r} at")
    source_from = _number(
        clip.get("from", 0),
        f"Clip {clip_id!r} from",
    )
    if "to" not in clip:
        raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
    source_to = _number(clip.get("to"), f"Clip {clip_id!r} to")
    if at < 0:
        raise ValueError(f"Clip {clip_id!r} has a negative timeline frame bound")
    if source_from < 0 or source_to <= source_from:
        raise ValueError(
            f"Clip {clip_id!r} must have positive source bounds with to > from"
        )
    return _ClipRange(
        clip=clip,
        at=at,
        source_from=source_from,
        source_to=source_to,
    )


def _is_default(value: Any, default: Any) -> bool:
    return value is None or value == default


def _nonempty(value: Any) -> bool:
    return value not in (None, False, "", (), [], {})


def _validate_track_semantics(track: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    track_id = track.get("id")
    try:
        effective_gain(track, {})
    except ValueError as exc:
        reasons.append(str(exc))
    if not _is_default(track.get("scale"), 1) or not _is_default(
        track.get("fit"), "contain"
    ) or not _is_default(track.get("blendMode"), "normal"):
        reasons.append(
            f"Track {track_id!r} uses unsupported visual transform semantics"
        )
    opacity = track.get("opacity")
    if opacity is not None:
        try:
            if _number(opacity, f"Track {track_id!r} opacity") != 1.0:
                reasons.append(
                    f"Track {track_id!r} uses unsupported non-default opacity"
                )
        except ValueError as exc:
            reasons.append(str(exc))
    return reasons


def _validate_clip_semantics(
    clip: Mapping[str, Any],
    track: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    clip_id = clip.get("id")
    if "muted" in clip:
        reasons.append(
            f"Clip {clip_id!r} uses unsupported clip-level muted; use volume: 0"
        )
    try:
        speed = _number(clip.get("speed", 1), f"Clip {clip_id!r} speed")
        if speed != 1.0:
            reasons.append(
    return MediaProbe(
        duration_seconds=duration,
        audio_codec="pcm_s16le" if present else None,
        video_stream_present=False,
        audio_stream_present=present,
    )


def _request(
    tmp_path: Path,
    *,
    audio: AudioOwnership | None = None,
    window: FrameWindow | None = None,
) -> RenderRequest:
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(tmp_path / "timeline.json"),
        assets_registry_path=str(tmp_path / "assets.json"),
        output_name="result.mp4",
        window=window,
        audio=audio,
        backend_config={ffmpeg.BACKEND_ID: {}},
    )


def _evaluate(
    tmp_path: Path,
    timeline_data: dict,
    assets: dict,
    *,
    probes: dict[str, MediaProbe] | None = None,
    missing_files: set[str] | None = None,
    which=None,
    request: RenderRequest | None = None,
):
    missing = missing_files or set()
    for entry in assets.get("assets", {}).values():
        file_value = entry.get("file")
        if isinstance(file_value, str) and file_value not in missing:
            (tmp_path / file_value).write_bytes(b"source")
    (tmp_path / "timeline.json").write_text(
        json.dumps(timeline_data),
        encoding="utf-8",
    )
    (tmp_path / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
    probe_map = probes or {
        "video.mp4": _video_probe(),
        "audio.wav": _audio_probe(),
    }

    return evaluate_support(
        request or _request(tmp_path),
        timeline_data,
        assets,
        probe=lambda path: probe_map[Path(path).name],
        which=which or (lambda binary: f"/usr/bin/{binary}"),
    )


def _build_command(tmp_path: Path, timeline_data: dict, assets: dict) -> list[str]:
    _evaluate(tmp_path, timeline_data, assets)
    return command.build_render_command(_request(tmp_path), tmp_path)


def test_supported_report_exposes_request_specific_evidence(tmp_path: Path) -> None:
    report = _evaluate(tmp_path, _timeline(), _assets(tmp_path))

exec
/bin/zsh -lc "sed -n '365,425p' astrid/packs/rendering/backends/ffmpeg/support.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
                )
            if bounds.end > cursor + _TIMELINE_EPSILON_SECONDS:
                reasons.append(
                    f"Audio clip {clip_id!r} ends outside the visual frame bounds"
                )
            audio_cursor = max(audio_cursor, bounds.end)
    return _dedupe(reasons)


def _dedupe(reasons: list[str]) -> list[str]:
    return list(dict.fromkeys(reason for reason in reasons if reason))


def _assets_table(assets: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = assets.get("assets")
    return value if isinstance(value, Mapping) else None


def _registry_path(request: RenderRequest) -> Path:
    if request.assets_registry_path is None:
        return Path.cwd() / "assets.json"
    return Path(request.assets_registry_path).expanduser().resolve()


def _asset_path(
    entry: Mapping[str, Any],
    *,
    asset_id: str,
    assets_path: Path,
) -> Path:
    if _nonempty(entry.get("url")):
        raise ValueError(
            f"Asset {asset_id!r} is remote; rendering.ffmpeg requires a local source file"
        )
    file_value = entry.get("file")
    if not isinstance(file_value, str) or not file_value:
        raise ValueError(f"Asset {asset_id!r} has no local source file")
    path = Path(file_value).expanduser()
    if not path.is_absolute():
        path = (assets_path.parent / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Asset {asset_id!r} source is missing: {path}")
    return path


def _probe_duration(probe: MediaProbe) -> float | None:
    if probe.duration_seconds is not None:
        return float(probe.duration_seconds)
    if probe.duration_rational is not None:
        numerator, denominator = probe.duration_rational
        return numerator / denominator
    return None


def _requested_ownership(
    request: RenderRequest,
    *,
    has_audio_clips: bool,
) -> tuple[AudioOwnership, list[str]]:

exec
/bin/zsh -lc "python3 -B -c 'import dataclasses; from astrid.core.media import MediaProbe; from astrid.core.rendering.contracts import SCHEMA_VERSION,RenderProfile,RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import support; t={\"theme\":\"banodoco-default\",\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":30}}},\"tracks\":[{\"id\":\"v\",\"kind\":\"visual\"}],\"clips\":[{\"id\":\"video\",\"at\":0,\"track\":\"v\",\"clipType\":\"media\",\"asset\":\"video\",\"from\":0,\"to\":4,\"speed\":1,\"volume\":0}]}; a={\"assets\":{\"video\":{\"file\":\"AGENTS.md\",\"type\":\"video/mp4\",\"duration\":4,\"resolution\":\"640x360\",\"fps\":30}}}; p=RenderProfile(width=640,height=360,fps_rational=(30,1),time_base=(1,15360),container=\"mp4\",video_codec=\"h264\",pixel_format=\"yuv420p\"); q=RenderRequest(schema_version=SCHEMA_VERSION,timeline_path=\"timeline.json\",assets_registry_path=\"assets.json\",output_name=\"result.mp4\",profile=p); probe=lambda _:MediaProbe(duration_seconds=4,width=640,height=360,fps=30,fps_rational=(30,1),time_base=(1,15360),resolution=\"640x360\",video_codec=\"h264\",video_profile=\"Constrained Baseline\",video_level=\"4.0\",pixel_format=\"yuv420p\",video_stream_present=True,audio_stream_present=False); cases=[(\"profile-only\",dataclasses.replace(q,profile=dataclasses.replace(p,video_profile=\"High\"))),(\"level-only\",dataclasses.replace(q,profile=dataclasses.replace(p,video_level=\"40\"))),(\"unpinned\",q)]; print([(n,support(r,t,a,probe=probe,which=lambda _:\"/usr/bin/tool\").supported,support(r,t,a,probe=probe,which=lambda _:\"/usr/bin/tool\").reasons) for n,r in cases])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 633ms:
[('profile-only', False, ["requested profile video_profile='High' cannot be guaranteed by rendering.ffmpeg (encoder default or stream-copy preserves source values; omit video_profile to use defaults)"]), ('level-only', False, ["requested profile video_level='40' cannot be guaranteed by rendering.ffmpeg (encoder default or stream-copy preserves source values; omit video_level to use defaults)"]), ('unpinned', True, [])]

exec
/bin/zsh -lc "ls -lh .oracle/checkins/batch-3*.md && git log --oneline --stat --max-count=5 -- .oracle/checkins | sed -n '1,220p' && git diff --name-status a7b7b080..9bf9db88" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 14ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-3-r3.md
M	astrid/packs/rendering/backends/ffmpeg/support.py
M	tests/packs/rendering/test_ffmpeg_support.py

collab: Wait
codex
PASS
tokens used
103,210
PASS
