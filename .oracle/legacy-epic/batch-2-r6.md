Reading additional input from stdin...
2026-08-12T07:35:02.876335Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:02.876357Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:02.876361Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff4e5-6730-7702-a28f-8ca006db4995
--------
user
# Megado Checkpoint — Batch 2 sixth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-2.md (6), -r1 (5), -r2 (6), -r3 (5), -r4 (5), -r5 (2).
Sixth rework committed as `3df2b858` (prior head 3557792f). Incremental diff
at /tmp/batch2-r6.diff.

## How each of your 2 re-review5 issues was addressed (host-implemented)

1. **support discards audio mismatch when profile is null** →
   - The audio-ownership check now triggers the unsupported result regardless
     of whether `profile` is present: `audio="none"` with `profile=null`
     returns supported:false. New test covers it.
2. **layout channel-count lookup lacks whitespace-strip** →
   - `_layout_channel_count` now `.strip().lower()` — `" Stereo "` maps to
     2 channels like the normal profile normalization.

## Evidence

- Incremental diff: /tmp/batch2-r6.diff (4 files)
- Host-verified: 77 combined (transport/fixture/publication/artifacts/media)
  pass; full consolidated acceptance = 747 passed, 2 failed (SAME 2
  pre-existing env failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. If PASS, say exactly `PASS`.
codex
I’m applying the Astrid, Megado, and context-minimization instructions because this is an Astrid Megado checkpoint. I’ll keep the review read-only, inspect the incremental commit and targeted tests, and return only the required verdict.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/megado/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
    1025 total
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
---
name: contextminning-subagentmaxxing
description: >
  Keep the main-thread context as lean as possible while working. Two moves: (1)
  context minning — after each turn, look for a natural break-off point to condense,
  save state to markdown, and compact - write .md docs to make sure you don't lose 
  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
  a subagent (especially the DeepSeek/Kimi agents via subagent-launcher) should research,
  validate, or execute it so the verbose work never lands in your context. Use on 
  any long, multi-step, or research-heavy task.
---

# Context Minning & Subagent Maxxing

The goal of this skill is singular: **keep the actual work in the main thread's
context as small as possible.** Long contexts get slow, expensive, and forgetful.
Every turn, the most useful tokens should be present and the rest should be
elsewhere — in a file, in a summary, or in a subagent that already finished.

It runs as two continuous moves — a posture, not a one-time cleanup. This file is the
philosophy and the high level; each move has a standalone skill with the mechanics,
syntax, and anti-patterns. **Invoke those for the how.**

---

## Move 1 — Context minning: condense at the seams

When a chunk of work becomes *done and durable* — a plan spec'd out, a bug
root-caused, a long read distilled to one answer — the path to that conclusion is dead
weight. At those seams: **write the conclusion to a durable artifact, then compact from
there.** Prefer landing real work as a megaplan asset (plan file or ticket) over a loose
note, so what you shed becomes trackable work rather than vanishing.

The discipline is *write it down first* — you can only safely forget what you can
re-read. And don't over-do it: compact at seams, never on a timer; a slightly long
context costs less than a lost decision.

→ **`minimize-context`** for the seam catalogue, the `/compact` · `/clear` · `/context`
mechanics, megaplan-asset detail, and the over-minning failure mode.

→ **`context-usage`** to *see* the context filling: a turn-by-turn token-growth chart
read from the session transcript, with every compaction boundary marked. Use it to
check whether you're minning at the right seams or letting context balloon to
auto-compaction. (`/context` is the live snapshot; `context-usage` is the trajectory.)

## Move 2 — Subagent maxxing: do the work elsewhere

**Default to doing work in a subagent, not the thread.** Flip the question from "should
a subagent do this?" to "is there any reason this *can't*?" Its tool calls, file reads,
and reasoning stay in *its* context; only the conclusion returns to you. **Execution is
the headline case** — implementing, investigating, building is where byproduct piles up,
so it's the first thing to hand off, not the last. Be willing to launch **many**, even
in parallel, until you have clarity — that's cheaper than carrying the trail inline.

Two principles carry most of the value: spend the subagent on the *byproduct-heavy*
part and ask it to **return the conclusion, not the trail**; and **use the cheapest
model that can do the job** (cheap scan-work → reasoning → frontier only for real
complexity), preparing the context well enough that a cheaper tier can win. Don't
dispatch if you already have the answer.

**Match the venue to the scale.** A one-shot subagent dispatch is for ad-hoc work —
research, a sense-check, a contained fix. Once something is more than ~a day or two of
work it's a *deliverable*: run it as a **megaplan** (itself launched in a subagent) and
use **`megaplan-decision`** to size the tier/robustness/depth. Past ~2 weeks → an epic.

→ **`subagent-launcher`** for the pathways, the cost-escalation ladder with model
identifiers, and how to shape a self-contained subagent prompt.

---

## The loop, in one line

Every turn: *Did I just hit a seam? → write it down, compact. Am I about to do real
work? → hand it to a subagent.* Keep the main thread holding only what the next
decision needs.

exec
/bin/zsh -lc "sed -n '261,560p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '561,820p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The context-minimization guidance calls for delegating byproduct-heavy validation, so I’m using the subagent-launcher guidance to obtain independent semantic and regression checks while I inspect the patch directly. No files will be changed.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,360p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
---
name: subagent-launcher
description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
---

# Subagent launcher (multi-model)

Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.

Three pathways:

| Pathway | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Hermes agentic** *(default)* | DeepSeek V4 (Pro/Flash), Kimi K2.7, Zhipu GLM, … | `launch_hermes_agent.py` — or `fan.py` to run N in one process | `file`, `web`, optional `terminal` |
| **Codex** | GPT-5.5 | `codex exec` (CLI) | sandboxed workspace |
| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |

**Default to the hermes agentic pathway, and to DeepSeek within it** — different model family, cheap, tool-using. Reach for Codex or Claude only when you specifically want their strengths.

> **⚠️ Network sandbox warning for Codex subagents**
> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Hermes agents (DeepSeek/Kimi/MiMo/GLM/OpenRouter) need outbound network to reach their provider APIs, so **launching them from inside a `codex exec` subagent will fail**. The launcher itself is fine; it fails only because the parent process has no network.
>
> **Workarounds:**
> 1. Launch the hermes subagent directly from a normal shell or Bash tool.
> 2. If you need a **Codex subagent to orchestrate hermes subagents**, run the
>    outer Codex command with `--sandbox danger-full-access` and seal stdin with
>    `</dev/null`, for example:
>
>    ```bash
>    timeout 3600 codex exec --sandbox danger-full-access \
>      -c model_reasoning_effort=high \
>      "$(cat /tmp/brief.md)" </dev/null
>    ```
>
>    `read-only` and `workspace-write` both disable outbound network for the
>    Codex subprocess; only `danger-full-access` allows nested Hermes provider
>    API calls from inside `codex exec`. Tell Codex explicitly to use
>    `launch_hermes_agent.py` or `fan.py`, and to spend its own context budget
>    by delegating broad searches, file mapping, and independent reviews to
>    DeepSeek/Kimi subagents wherever practical.
>
> This network restriction does not affect Codex or Claude subagents.

## Picking a pathway

- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
- **Already have the answer?** → don't dispatch. Subagents aren't free.

## Use the cheapest subagent that can do the job

Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.

1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.

Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.

Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.

---

## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default

A real tool-using agent in a non-Claude model's voice, far lighter than a `megaplan` run. It wraps megaplan's `AIAgent` primitive as a standalone CLI: the agent reads files, searches the codebase, fetches URLs, and (with `terminal`) runs commands — single-turn, no plan state or critique loop. For a pure-chat opinion with no repo access, run the same command with `--toolsets=""`.

The launcher discovers the active runtime itself. It first tries an installed legacy `megaplan.agent` distribution, then falls back to the current Arnold checkout (`~/Documents/Arnold` by default, or `ARNOLD_PATH=/path/to/Arnold`). Do not add an `arnold_pipelines.megaplan.agent` compatibility package to fix import failures; the real Hermes runtime lives under `arnold_pipelines.megaplan.agent` in the Arnold checkout.

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --toolsets="file,web" \
  --query-file=/tmp/brief.md \
  --max-tokens=65536 \
  --project-dir="$PWD"
# Final response → stdout; tool progress/timings → stderr.
```

Key flags:

- **`--model`** (default `deepseek:deepseek-v4-pro`). Prefix convention from the megaplan key pool:
  - `fast`, `mimo`, `mimo-fast` → `mimo:mimo-v2.5-pro-ultraspeed` (very fast MiMo path; requires `MIMO_API_KEY`)
  - `deepseek:deepseek-v4-pro` (default) / `deepseek:deepseek-v4-flash` (faster, non-reasoning) → DeepSeek API
  - `kimi:kimi-k2.7-code` → Kimi coding API (requires `KIMI_API_KEY` or `MOONSHOT_API_KEY`)
  - `zhipu:glm-5.2` / `zhipu:glm-4.6` → Zhipu GLM API (requires `ZHIPU_API_KEY`)
  - `google:gemini-…`, `minimax:MiniMax-M2`, … — see `megaplan/runtime/key_pool.py:resolve_model`
- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.

Output is **freeform text** — if you want JSON, ask for it in the prompt and parse defensively; for an *enforced* schema, use megaplan, not this pathway.

### Fan out N at once — `fan.py`

`launch_hermes_agent.py` is one subprocess per call; each re-imports the Arnold/Hermes runtime. For **≥ ~5 parallel agents or programmatic batches**, `fan.py` runs N `AIAgent`s in one process (imports once, ~5–15× less RAM). Same flags, plus a briefs directory and per-task output:

```bash
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
  --briefs-dir=/tmp/briefs --output-dir=/tmp/results \
  --max-workers=5 --model="deepseek:deepseek-v4-pro" \
  --toolsets="file,web" --max-tokens=65536 --task-timeout=1800 --project-dir="$PWD"
# Or positional brief paths instead of --briefs-dir.
# Per-brief models: --model-map="fast:scan-*.md,pro:verdict-*.md"
```

Each brief `<stem>.md` yields `<stem>.txt` (response), `<stem>.meta.json` (status/timing/tool_calls), and an aggregate `_report.json`. Kill a running fan from another shell: `fan_kill.py --output-dir=… [--hard]`. Default `--task-timeout=1800` (30 min — forensic work with ≥10 tool calls routinely exceeds 10 min; the old 600s default would silently SIGKILL agents mid-investigation). Bump higher for very heavy briefs (e.g. `--task-timeout=3600` for cross-file audits). Add `--isolation=processes` if you need to SIGKILL one task without touching the rest. Below ~5 parallel, just launch `launch_hermes_agent.py` N times in parallel Bash calls — simpler.

### Use `megaplan` instead when you need

multi-phase orchestration (plan → critique → revise → execute → gate → review), schema-enforced output, persistent plan state / approval gates, or the megaplan sandbox. See *Multi-phase delegation* below.

### Liveness

The script logs `[tool]` / `[done]` to stderr every 1–5 s while alive and ends with `[launch_hermes_agent] done in N.Ns`. No new tool lines for minutes = wedged. For `fan.py`, watch `.meta.json` files appearing under `--output-dir`.

---

## 2. Codex (GPT-5.5)

`codex exec` from Bash (the `/codex:*` plugin wraps the same call).

```bash
codex exec --sandbox read-only "$(cat /tmp/prompt.md)" </dev/null > /tmp/out.txt 2>&1
```

- `--sandbox read-only | workspace-write | danger-full-access` — analysis / let it edit files / full shell.
- `-c model_reasoning_effort=low|medium|high` — `medium` default.
- `codex exec review [--pr <n>]` for PR review; `codex apply` to apply its last diff.
- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).

## 3. Claude (Opus/Sonnet/Haiku)

Use the Claude CLI launcher when you need an explicit model selector from any
host, including Codex sessions where the platform `spawn_agent` tool does not
expose a model field:

```bash
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus \
  --query-file=/tmp/brief.md \
  --project-dir="$PWD" \
  --tools="Read,Grep,Glob" \
  --timeout=1800
```

`--model` accepts Claude Code aliases such as `opus` / `sonnet` / `haiku` or a
full model name such as `claude-opus-4-8`. The launcher invokes
`claude --print --model <model>` with `--project-dir` as the subprocess cwd and
prints the final answer to stdout while diagnostics go to stderr. It leaves
Claude Code's default tool policy alone unless you pass `--tools`; use
`--permission-mode` deliberately. It adds `--no-session-persistence` by default
so one-off subagents do not clutter Claude history; pass `--keep-session` when
you want resumability.

When you are already inside Claude Code and the `Agent` tool is available,
you can still dispatch through it — cleanly-scoped, no memory of the outer
conversation, so the prompt must be self-contained. Subagent types:
`general-purpose` (full tools), `Explore` (fast read-only search), `Plan`
(architect, no code), `claude-code-guide`, `code-reviewer`.

```
Agent({ description: "…", subagent_type: "general-purpose",
        prompt: "<self-contained brief: working dir, files, what to return, length cap>" })
```

Prefer Claude over Codex when you want the *same family* of judgement isolated from this thread (keeping the main context clean), or specifically want Opus judgement. For genuinely different model-family judgement, prefer Codex, DeepSeek, or Kimi.

---

## Multi-phase delegation (when a single-turn agent isn't enough)

When DeepSeek/Kimi need a full plan-execute-review cycle across many files, route through megaplan:

```bash
PYENV_VERSION=3.11.11 megaplan init --project-dir "$PWD" \
  --profile all-deepseek-pro-direct --robustness light "<task>"
# Kimi: --profile all-open
```

`--robustness light` is a fast single pass; drop it for the full workflow (default `full`). The **`megaplan-decision`** skill covers the profile / robustness / depth dials.

## Writing the prompt (any pathway)

The receiving model has **zero context** from your conversation. Brief it like a smart colleague who just walked in:

**Is your brief a spec or a memo?** A spec lists inputs and outputs (do X at line Y, then Z). A memo explains context and asks for judgement. Reasoning models will treat any memo as license to architect — even if the underlying ask was 5 mechanical edits. If the work is mechanical, strip the rationale; the "why" belongs in the commit message, not the brief.

- Working directory and **exact** file paths (not "the relevant files").
- Goal + why it matters; what you've already ruled out.
- Output shape and a length cap ("ranked list, < 300 words").
- For adversarial / second-opinion work, tell it to take a position and not hedge — otherwise it hedges.
- Anti-pattern: the options menu. "Pick whichever of A/B/C fits" reliably invites a reasoning model to optimize across the options and often produce a fourth one you didn't ask for. One ask, one solution path. Save options menus for genuine judgement calls — and when you do use them, route the work to a non-reasoning model that can't optimize past them.

Don't dispatch what you already know, and don't re-ask what you've answered — add a twist (rank these, find the flaw, argue the other side) or skip it.

## Judge / jury for high-stakes calls

Send the same unbiased prompt to several models in parallel (Codex + hermes-DeepSeek + hermes-Kimi, optionally a Claude `Agent`) and compare — convergence on a subtle call is far stronger than one model's confidence; divergence is signal. Reserve it for risky pre-merge reviews, hard-to-reverse architecture calls, security-sensitive paths. Don't fan out routine work. For a multi-lens sense-check of one proposal (human-user / agent-user / abstraction lenses), give each agent only its own lens and never show one's output to another.

## Detecting hangs

Check liveness **30–60 s after launch**, not 10 minutes in.

- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.

**Liveness ≠ correctness.** A subagent can stream for 10 minutes and still answer uselessly — read the response; there's no shortcut.

## Quick reference

```bash
# 1. Hermes agentic (default) — DeepSeek/Kimi/Zhipu GLM with tools
PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="deepseek:deepseek-v4-pro" --toolsets="file,web" \
  --query-file=/tmp/brief.md --max-tokens=65536 --project-dir="$PWD"
# Very fast: --model=fast   Flash: --model="deepseek:deepseek-v4-flash"   Kimi: --model="kimi:kimi-k2.7-code"   GLM: --model="zhipu:glm-5.2"
# Pure chat: --toolsets=""    Fan N≥5: fan.py --briefs-dir=… --output-dir=… --max-workers=5 --task-timeout=1800

# 2. Codex — always seal stdin with </dev/null, allow 30 min
timeout 1800 codex exec --sandbox read-only "<prompt>" </dev/null              # analysis
timeout 1800 codex exec --sandbox workspace-write "<prompt>" </dev/null        # implementer
timeout 1800 codex exec --sandbox danger-full-access "<prompt>" </dev/null     # orchestrates hermes subagents (network required)
codex exec review --pr 123

# 3. Claude — explicit Opus selector via Claude CLI
python ~/.claude/skills/subagent-launcher/launch_claude_agent.py \
  --model=opus --query-file=/tmp/prompt.md --project-dir="$PWD"

# Multi-phase: megaplan init --profile all-deepseek-pro-direct --robustness light "<task>"
```

2026-08-12T07:35:46.521741Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:46.521764Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:46.521767Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:51.391554Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:51.391620Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:35:51.391626Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short --branch && git rev-parse HEAD && git show --no-ext-diff --stat --oneline --decorate --no-renames 3df2b858 && git diff --no-ext-diff --check 3557792f 3df2b858 && sed -n '1,260p' /tmp/batch2-r6.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## oracle-run
?? .oracle/checkins/batch-2-r6.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3df2b858bae0ee6ede9e001745df63c4adbaa56a
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3df2b858 (HEAD -> oracle-run) batch2-rework6: oracle re-review5 issues 1-2 (support rejects audio!=rendered regardless of profile presence, layout channel-count whitespace-strip)
 .oracle/checkins/batch-2-r5.md                     | 7661 ++++++++++++++++++++
 astrid/core/rendering/artifacts.py                 |    2 +-
 tests/core/rendering/test_raw_command_fixture.py   |   31 +
 .../fixtures/renderer_packs/raw_command/backend.py |   34 +-
 4 files changed, 7710 insertions(+), 18 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r5.md:533: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:537: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:539: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:548: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:550: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:552: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:553: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:557: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:558: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:562: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:565: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:571: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:573: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:593: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:597: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:599: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:603: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:605: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:613: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:619: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:620: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:623: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:624: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:627: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:640: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:641: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:652: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:653: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:658: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:659: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:666: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:667: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:684: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:685: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:688: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:709: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:710: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:757: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:788: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:789: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:800: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:801: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:824: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:849: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:850: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:877: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:878: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:906: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:911: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:913: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:922: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:925: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:927: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:932: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:935: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:936: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:940: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:941: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:944: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:948: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:963: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:970: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:973: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:976: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:977: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:980: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:985: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:986: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:989: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:990: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:993: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:994: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:997: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1032: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1033: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1041: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1042: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1068: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1069: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1076: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1081: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1124: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1125: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1132: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1134: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1135: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1151: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1152: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1195: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1208: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1209: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1216: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1217: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1234: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1235: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1252: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1253: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1266: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1267: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1272: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1287: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1297: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1301: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1348: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1351: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1354: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1355: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1360: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1377: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1378: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1404: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1405: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1416: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1417: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1468: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1478: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1482: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1483: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1494: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1497: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1501: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1510: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1514: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1518: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1522: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1526: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1527: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1531: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1532: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1535: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1536: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1549: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1550: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1570: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1571: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1632: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1633: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1647: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1656: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1659: trailing whitespace.
+ 
.oracle/checkins/batch-2-r5.md:1713: trailing whitespace.
+returncode 0 size 29360 stderr 
.oracle/checkins/batch-2-r5.md:7312: trailing whitespace.
+   441	
.oracle/checkins/batch-2-r5.md:7313: trailing whitespace.
+   442	
.oracle/checkins/batch-2-r5.md:7374: trailing whitespace.
+   442	
.oracle/checkins/batch-2-r5.md:7405: trailing whitespace.
+   473	
.oracle/checkins/batch-2-r5.md:7406: trailing whitespace.
+   474	
.oracle/checkins/batch-2-r5.md:7416: trailing whitespace.
+   484	
.oracle/checkins/batch-2-r5.md:7417: trailing whitespace.
+   485	
.oracle/checkins/batch-2-r5.md:7436: trailing whitespace.
+   480	
.oracle/checkins/batch-2-r5.md:7446: trailing whitespace.
+   490	
.oracle/checkins/batch-2-r5.md:7450: trailing whitespace.
+   494	
.oracle/checkins/batch-2-r5.md:7494: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r5.md:7495: trailing whitespace.
+    27	
.oracle/checkins/batch-2-r5.md:7499: trailing whitespace.
+    31	
.oracle/checkins/batch-2-r5.md:7502: trailing whitespace.
+    34	
.oracle/checkins/batch-2-r5.md:7508: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r5.md:7510: trailing whitespace.
+    42	
.oracle/checkins/batch-2-r5.md:7529: trailing whitespace.
+    61	
.oracle/checkins/batch-2-r5.md:7533: trailing whitespace.
+    65	
.oracle/checkins/batch-2-r5.md:7535: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r5.md:7536: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r5.md:7539: trailing whitespace.
+    93	
.oracle/checkins/batch-2-r5.md:7568: trailing whitespace.
+   122	
.oracle/checkins/batch-2-r5.md:7569: trailing whitespace.
+   123	
.oracle/checkins/batch-2-r5.md:7577: trailing whitespace.
+   131	
.oracle/checkins/batch-2-r5.md:7578: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r5.md:7604: trailing whitespace.
+   158	
.oracle/checkins/batch-2-r5.md:7605: trailing whitespace.
+   159	
.oracle/checkins/batch-2-r5.md:7612: trailing whitespace.
+   166	
.oracle/checkins/batch-2-r5.md:7617: trailing whitespace.
+   171	

exec
/bin/zsh -lc 'git diff --no-ext-diff --no-renames --unified=100 3557792f 3df2b858 -- astrid/core/rendering/artifacts.py tests/core/rendering/test_raw_command_fixture.py tests/fixtures/renderer_packs/raw_command/backend.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/artifacts.py b/astrid/core/rendering/artifacts.py
index 736bd7a5..e4a11bdd 100644
--- a/astrid/core/rendering/artifacts.py
+++ b/astrid/core/rendering/artifacts.py
@@ -383,201 +383,201 @@ def _probe_required_video(probe: MediaProbe) -> None:
         _invalid(
             "incomplete_probe",
             "ffprobe returned incomplete primary-video metadata",
             missing=missing,
         )
     if type(probe.width) is not int or probe.width <= 0:
         _invalid("incomplete_probe", "ffprobe returned invalid video width", actual=probe.width)
     if type(probe.height) is not int or probe.height <= 0:
         _invalid("incomplete_probe", "ffprobe returned invalid video height", actual=probe.height)
     _rational(probe.fps_rational, label="video FPS")
     _rational(probe.time_base, label="video time base")
 
 
 def _compare_probe_to_profile(
     probe: MediaProbe,
     profile: RenderProfile,
     *,
     label: str,
     compare_audio: bool,
 ) -> None:
     actual_values: dict[str, Any] = {
         "width": probe.width,
         "height": probe.height,
         "fps_rational": probe.fps_rational,
         "time_base": probe.time_base,
         "video_codec": probe.video_codec,
         "pixel_format": probe.pixel_format,
     }
     for field, actual in actual_values.items():
         expected = _profile_value(profile, field)
         if not _same_profile_value(field, actual, expected):
             _invalid(
                 "profile_mismatch",
                 f"probed video {field} does not match {label}",
                 field=field,
                 expected=expected,
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
                         expected=expected,
                         actual=actual,
                         probed_channels=probe.audio_channels,
                     )
                 continue
             if not _same_profile_value(field, actual, expected):
                 _invalid(
                     "audio_profile_mismatch",
                     f"probed audio {field} does not match {label}",
                     field=field,
                     expected=expected,
                     actual=actual,
                 )
 
 
 def _layout_channel_count(layout: str | None) -> int | None:
     return {
         "mono": 1,
         "stereo": 2,
         "5.1": 6,
         "5.1(side)": 6,
         "7.1": 8,
         "7.1(wide)": 8,
-    }.get((layout or "").lower())
+    }.get((layout or "").strip().lower())
 
 
 def _validate_audio(
     probe: MediaProbe,
     *,
     ownership: AudioOwnership,
     declared: RenderProfile,
     expected: RenderProfile,
 ) -> None:
     has_audio = probe.has_audio_stream
     if has_audio:
         missing = [
             field
             for field in ("audio_codec", "audio_sample_rate")
             if getattr(probe, field) is None
         ]
         if probe.audio_channel_layout is None and probe.audio_channels is None:
             missing.append("audio_channel_layout/audio_channels")
         if missing:
             _invalid(
                 "incomplete_probe",
                 "ffprobe returned an audio stream with incomplete metadata",
                 missing=missing,
             )
 
     if ownership is AudioOwnership.RENDERED and not has_audio:
         _invalid(
             "audio_ownership_mismatch",
             "renderer declared audio_ownership='rendered' but the video has no audio stream",
             declared_ownership=ownership.value,
             actual_audio_stream=False,
         )
     if ownership in {AudioOwnership.NONE, AudioOwnership.PASSTHROUGH} and has_audio:
         _invalid(
             "audio_ownership_mismatch",
             f"renderer declared audio_ownership={ownership.value!r} but the video has an audio stream",
             declared_ownership=ownership.value,
             actual_audio_stream=True,
         )
     if declared.has_audio != has_audio:
         _invalid(
             "audio_profile_mismatch",
             "declared artifact audio profile does not match probed stream presence",
             declared_audio=declared.has_audio,
             actual_audio_stream=has_audio,
         )
     if has_audio:
         _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=True)
         _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=True)
 
 
 def _duration_fraction(probe: MediaProbe) -> Fraction:
     if probe.duration_rational is not None:
         try:
             duration = Fraction(*probe.duration_rational)
         except (TypeError, ValueError, ZeroDivisionError):
             _invalid(
                 "incomplete_probe",
                 "ffprobe returned an invalid rational duration",
                 actual=probe.duration_rational,
             )
     else:
         seconds = probe.duration_seconds
         if seconds is None or not math.isfinite(seconds):
             _invalid(
                 "incomplete_probe",
                 "ffprobe returned an invalid duration",
                 actual=seconds,
             )
         duration = Fraction(str(seconds))
     if duration < 0:
         _invalid(
             "incomplete_probe",
             "ffprobe returned a negative duration",
             actual=float(duration),
         )
     return duration
 
 
 def _validate_duration(
     probe: MediaProbe,
     *,
     duration_frames: Any,
     expected: RenderProfile,
 ) -> None:
     if type(duration_frames) is not int or duration_frames <= 0:
         _invalid(
             "invalid_duration",
             "video artifact duration_frames must be a positive integer",
             declared_duration_frames=duration_frames,
         )
     fps = Fraction(*expected.fps_rational)
     actual_frames = _duration_fraction(probe) * fps
     delta = abs(actual_frames - duration_frames)
     if delta > expected.duration_tolerance:
         _invalid(
             "duration_mismatch",
             "probed video duration is outside the canonical frame tolerance",
             declared_duration_frames=duration_frames,
             actual_duration_frames=float(actual_frames),
diff --git a/tests/core/rendering/test_raw_command_fixture.py b/tests/core/rendering/test_raw_command_fixture.py
index 7e44fd39..e1cd02c0 100644
--- a/tests/core/rendering/test_raw_command_fixture.py
+++ b/tests/core/rendering/test_raw_command_fixture.py
@@ -206,200 +206,231 @@ def test_fixture_pack_validates_and_inspects_without_importing_backend(
     _copy_pack(source_root)
     modules_before = set(sys.modules)
     with (
         mock.patch.object(
             importlib,
             "import_module",
             side_effect=AssertionError("backend import"),
         ),
         mock.patch.object(
             subprocess,
             "Popen",
             side_effect=AssertionError("backend execution"),
         ),
         _load_with_source(tmp_path / "project", source_root) as (renderers, _, _),
     ):
 
         candidate = renderers.get(BACKEND_ID)
         assert candidate.id == BACKEND_ID
         assert candidate.source_kind == "source"
         assert candidate.execution_eligible is True
         assert candidate.manifest.name == "Raw Command Fixture Renderer"
         assert candidate.manifest.protocol_version == 1
         assert candidate.manifest.operations == ("render", "support")
         assert candidate.manifest.command == ("python3", "backend.py")
         assert candidate.manifest.required_permissions == ("subprocess", "project_files")
 
         caps = candidate.manifest.capabilities
         assert "media" in caps["clip_types"]
         assert {"visual", "audio"} <= set(caps["track_types"])
         assert caps["features"] == {
             "media": True,
             "audio_mode": "rendered",
             "deterministic": True,
         }
         assert caps["supports_full_timeline"] is True
         assert caps["supports_windows"] is True
         assert caps["output_profiles"] == ["video/mp4"]
         assert caps["audio_ownership"] == ["rendered"]
 
         # Trusted source-pack alias resolves to the canonical renderer.
         alias = renderers.get(ALIAS_ID)
         assert alias.id == BACKEND_ID
         assert alias.execution_eligible is True
 
         evidence = renderers.resolve_evidence(ALIAS_ID)
         assert evidence["resolved_id"] == BACKEND_ID
         assert evidence["alias_chain"] == [ALIAS_ID, BACKEND_ID]
         assert evidence["eligible"] is True
 
         assert len(renderers.candidates(eligible=True)) == 1
 
     modules_after = set(sys.modules)
     new_modules = modules_after - modules_before
     source_str = str(source_root.resolve())
     for name in new_modules:
         module = sys.modules.get(name)
         module_file = getattr(module, "__file__", None)
         assert module_file is None or not str(Path(module_file).resolve()).startswith(
             source_str
         ), f"module {name!r} is backed by the fixture pack: {module_file}"
 
 
 # ---------------------------------------------------------------------------
 # Protocol verbs through CommandTransport
 # ---------------------------------------------------------------------------
 
 
 def test_render_verb_via_command_transport(tmp_path: Path) -> None:
     workspace = tmp_path / "workspace"
     transport, result, _ = _run_transport(workspace, PACK_ROOT, verb="render")
 
     _assert_clean_render(result, workspace)
     assert transport.last_logs == {"stdout": "", "stderr": ""}
 
     # The fixture output must pass STRICT artifact validation against the
     # request profile (dimensions, FPS, codecs, pixel format, audio).
     from astrid.core.rendering.artifacts import validate_render_result
     from astrid.core.rendering.contracts import RenderRequest
 
     request = json.loads(
         (PACK_ROOT / "requests" / "render.json").read_text(encoding="utf-8")
     )
     parsed_request = RenderRequest.from_dict(request)
     video_abs = workspace / result.video.path
     validate_render_result(
         result,
         expected_profile=parsed_request.profile,
         workspace_root=workspace,
     )
     assert video_abs.is_file()
 
     # Determinism: a second invocation produces byte-identical media.
     second_workspace = tmp_path / "workspace-2"
     _, second_result, _ = _run_transport(second_workspace, PACK_ROOT, verb="render")
     first_bytes = (workspace / result.video.path).read_bytes()
     second_bytes = (second_workspace / second_result.video.path).read_bytes()
     assert first_bytes == second_bytes
     assert result.video.sha256 == second_result.video.sha256
 
 
+def test_support_rejects_audio_none_even_with_null_profile(tmp_path: Path) -> None:
+    """A request for audio='none' with profile=null is unsupported: the
+    renderer always produces rendered PCM stereo audio."""
+    workspace = tmp_path / "workspace"
+    workspace.mkdir(parents=True, exist_ok=True)
+    request_path = workspace / "request.json"
+    request_path.write_text(
+        json.dumps(
+            {
+                "schema_version": 1,
+                "output_name": "raw_command.mp4",
+                "audio": "none",
+                "profile": None,
+            }
+        ),
+        encoding="utf-8",
+    )
+    result_path = workspace / "result.json"
+    transport = CommandTransport(BACKEND_ID, termination_grace=0.15)
+    report = transport.run(
+        "support",
+        [sys.executable, "backend.py"],
+        request_path=request_path,
+        result_path=result_path,
+        cwd=PACK_ROOT,
+        timeout=30,
+    )
+    assert report.supported is False
+    assert report.features == {"media": False, "audio_mode": "none"}
+
+
 def test_support_verb_via_command_transport(tmp_path: Path) -> None:
     workspace = tmp_path / "workspace"
     _, report, _ = _run_transport(workspace, PACK_ROOT, verb="support", request_name="support.json")
 
     assert isinstance(report, SupportReport)
     assert report.schema_version == 1
     assert report.supported is True
     assert report.reasons == []
     assert report.features == {"media": True, "audio_mode": "rendered"}
     assert report.alternatives == []
     assert report.backend == BACKEND_ID
     assert report.backend_version == "1.0.0"
 
 
 def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
     _run_transport(tmp_path / "workspace-render", PACK_ROOT, verb="render")
     _run_transport(
         tmp_path / "workspace-support",
         PACK_ROOT,
         verb="support",
         request_name="support.json",
     )
 
     for root in (tmp_path, PACK_ROOT):
         assert list(root.rglob("run.json")) == [], f"run.json found under {root}"
 
 
 # ---------------------------------------------------------------------------
 # Extra pack root and trusted install resolution
 # ---------------------------------------------------------------------------
 
 
 def test_fixture_works_from_explicit_extra_pack_root(tmp_path: Path) -> None:
     extra_root = tmp_path / "extra"
     extra_pack = _copy_pack(extra_root)
     empty_source = tmp_path / "empty-source"
     empty_source.mkdir()
 
     with (
         mock.patch.object(
             rendering_registry_module,
             "discover_packs",
             side_effect=_scanner(empty_source),
         ),
         mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
     ):
         renderers, _, _ = load_default_registries(
             tmp_path / "project",
             extra_pack_roots=(str(extra_root),),
             include_installed=False,
         )
 
     candidate = renderers.get(BACKEND_ID)
     assert candidate.source_kind == "extra"
     assert candidate.execution_eligible is True
 
     _, result, workspace = _run_transport(tmp_path / "workspace-extra", extra_pack, verb="render")
     _assert_clean_render(result, workspace)
 
 
 def test_fixture_works_from_trusted_install(tmp_path: Path) -> None:
     astrid_home = tmp_path / "astrid-home"
     empty_source = tmp_path / "empty-source"
     empty_source.mkdir()
     revision = _stage_installed_fixture(astrid_home)
 
     with (
         mock.patch.dict(
             os.environ,
             {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
             clear=False,
         ),
         mock.patch.object(
             rendering_registry_module,
             "discover_packs",
             side_effect=_scanner(empty_source),
         ),
     ):
         renderers, _, _ = load_default_registries(tmp_path / "project", include_installed=True)
 
     candidate = renderers.get(BACKEND_ID)
     assert candidate.source_kind == "installed"
     assert candidate.execution_eligible is True
 
     alias = renderers.get(ALIAS_ID)
     assert alias.id == BACKEND_ID
     assert alias.source_kind == "installed"
     assert alias.execution_eligible is True
 
     _, result, workspace = _run_transport(tmp_path / "workspace-installed", revision, verb="render")
     _assert_clean_render(result, workspace)
 
     _, support, _ = _run_transport(
         tmp_path / "workspace-installed-support",
         revision,
         verb="support",
         request_name="support.json",
     )
     assert isinstance(support, SupportReport)
     assert support.backend == BACKEND_ID
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 04dc16b1..f628ad48 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -372,217 +372,217 @@ def _build_mp4(frames: int) -> bytes:
 
     video_stbl, audio_stbl = _sample_tables(
         video_frames=frames,
         video_sizes=video_sizes,
         video_chunk_offset=video_chunk_offset,
         audio_bytes=audio_bytes,
         audio_samples=audio_samples,
         audio_chunk_offset=audio_chunk_offset,
     )
 
     vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
     smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
     dinf = _dinf()
 
     minf_v = _box(b"minf", vmhd + dinf + video_stbl)
     mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
     trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)
 
     minf_a = _box(b"minf", smhd + dinf + audio_stbl)
     mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, audio_samples) + _hdlr(b"soun", b"SoundHandler") + minf_a)
     trak_a = _box(b"trak", _tkhd(2, audio_samples, 0x0100, 0, 0) + mdia_a)
 
     moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME) + trak_v + trak_a)
     mdat = _box(b"mdat", video_chunk + audio_bytes)
     return ftyp + mdat + moov
 
 
 # ---------------------------------------------------------------------------
 # Protocol verbs
 # ---------------------------------------------------------------------------
 
 
 def _write_json(path: Path, payload: dict) -> None:
     path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
 
 
 def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
     _write_json(
         result_path,
         {
             "schema_version": 1,
             "kind": kind,
             "backend": BACKEND_ID,
             "message": message,
             "recovery_command": None,
             "details": details,
         },
     )
 
 
 def _validate_request(request: dict) -> None:
     version = request.get("schema_version")
     if not isinstance(version, int) or isinstance(version, bool) or version != 1:
         raise ValueError(
             f"unsupported request schema_version {version!r}; expected 1"
         )
     output_name = request.get("output_name")
     if not isinstance(output_name, str) or output_name in (".", ".."):
         raise ValueError("output_name must be a non-empty portable basename")
     if not _OUTPUT_NAME_RE.fullmatch(output_name):
         raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
     window = request.get("window")
     if window is not None and not isinstance(window, dict):
         raise ValueError("window must be an object or null")
     if isinstance(window, dict):
         end = window.get("end_frame")
         start = window.get("start_frame", 0)
         if not isinstance(end, int) or not isinstance(start, int) or end <= start:
             raise ValueError("window must satisfy 0 <= start_frame < end_frame")
 
 
 def _support(request: dict, result_path: Path) -> int:
     mismatches: list[str] = []
     # The renderer ALWAYS produces rendered PCM stereo audio; a request for
     # no audio or passthrough contradicts the fixed output.
     requested_audio = request.get("audio")
     if requested_audio not in (None, "rendered"):
         mismatches.append(f"audio={requested_audio!r} (fixed 'rendered')")
     profile = request.get("profile")
     if isinstance(profile, dict):
         # The renderer emits a fixed profile; ANY deviation is unsupported
         # (fail closed on every field, not just codecs/dimensions).
         expected = {
             "width": WIDTH,
             "height": HEIGHT,
             "fps_rational": list(FPS_RATIONAL),
             "time_base": list(TIME_BASE),
             "container": CONTAINER,
             "video_codec": VIDEO_CODEC,
             "video_profile": None,
             "video_level": None,
             "pixel_format": PIXEL_FORMAT,
             "audio_codec": AUDIO_CODEC,
             "audio_sample_rate": AUDIO_SAMPLE_RATE,
             "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
         }
         for field, fixed in expected.items():
             requested = profile.get(field)
             if requested is not None and requested != fixed:
                 mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
-        if mismatches:
-            _write_json(
-                result_path,
-                {
-                    "schema_version": 1,
-                    "supported": False,
-                    "reasons": [
-                        "profile not produced by " + BACKEND_ID + ": "
-                        + "; ".join(mismatches)
-                    ],
-                    "features": {"media": False, "audio_mode": "none"},
-                    "alternatives": [],
-                    "backend": BACKEND_ID,
-                    "backend_version": "1.0.0",
-                },
-            )
-            return 0
+    if mismatches:
+        _write_json(
+            result_path,
+            {
+                "schema_version": 1,
+                "supported": False,
+                "reasons": [
+                    "profile not produced by " + BACKEND_ID + ": "
+                    + "; ".join(mismatches)
+                ],
+                "features": {"media": False, "audio_mode": "none"},
+                "alternatives": [],
+                "backend": BACKEND_ID,
+                "backend_version": "1.0.0",
+            },
+        )
+        return 0
     _write_json(
         result_path,
         {
             "schema_version": 1,
             "supported": True,
             "reasons": [],
             "features": {"media": True, "audio_mode": "rendered"},
             "alternatives": [],
             "backend": BACKEND_ID,
             "backend_version": BACKEND_VERSION,
         },
     )
     return 0
 
 
 def _render(request: dict, result_path: Path, request_path: Path) -> int:
     try:
         _validate_request(request)
         window = request.get("window")
         profile = request.get("profile") or {}
         if isinstance(window, dict):
             start = int(window.get("start_frame", 0))
             end = int(window["end_frame"])
         else:
             start, end = 0, 48
         frames = end - start
         if frames <= 0:
             raise ValueError("window must span at least one frame")
 
         output_name = request["output_name"]
         # The invocation workspace is the directory holding the request file;
         # keep every generated artifact contained there.
         workspace = request_path.resolve().parent
         out_dir = workspace / "outputs"
         out_dir.mkdir(parents=True, exist_ok=True)
         video_rel = f"outputs/{output_name}"
         video_path = out_dir / output_name
 
         media = _build_mp4(frames)
         video_path.write_bytes(media)
 
         probed_profile = {
             "width": WIDTH,
             "height": HEIGHT,
             "fps_rational": list(FPS_RATIONAL),
             "time_base": list(TIME_BASE),
             "container": CONTAINER,
             "video_codec": VIDEO_CODEC,
             "video_profile": None,
             "video_level": None,
             "pixel_format": PIXEL_FORMAT,
             "audio_codec": AUDIO_CODEC,
             "audio_sample_rate": AUDIO_SAMPLE_RATE,
             "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
             "duration_tolerance": int(profile.get("duration_tolerance", 1)),
         }
         result = {
             "schema_version": 1,
             "video": {
                 "path": video_rel,
                 "profile": probed_profile,
                 "sha256": hashlib.sha256(media).hexdigest(),
                 "duration_frames": frames,
                 "audio": "rendered",
                 "attachments": {},
             },
             "backend_fragments": {
                 BACKEND_ID: {
                     "renderer": "raw_command",
                     "media": "generated",
                     "audio_mode": "rendered",
                     "deterministic": True,
                 }
             },
             "audio_ownership": "rendered",
             "normalization": [],
             "logs": [],
             "metadata": {},
         }
         _write_json(result_path, result)
         return 0
     except ValueError as exc:
         _write_error(result_path, "protocol", str(exc), {"error_type": "ValueError"})
         return 0
     except Exception as exc:  # pragma: no cover - unexpected failure path
         _write_error(
             result_path,
             "internal",
             f"raw_command renderer failed: {exc}",
             {"error_type": type(exc).__name__},
         )
         return 0
 
 
 def main(argv: list[str]) -> int:
     parser = argparse.ArgumentParser(
         prog="backend.py",
         description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
     )
     parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))

exec
/bin/zsh -lc 'rg -n -C 5 "support discards|profile is null|layout channel-count|whitespace-strip|audio mismatch|_layout_channel_count" .oracle/checkins/batch-2-r5.md /tmp/batch2-r6.diff .oracle/tasklist.md 2>/dev/null | head -n 240' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
/tmp/batch2-r6.diff-36-+     kill → wait).
/tmp/batch2-r6.diff-37-+2. **support returns supported:true for audio="none"** →
/tmp/batch2-r6.diff-38-+   - `_support` now rejects any request `audio` other than `rendered` (the
/tmp/batch2-r6.diff-39-+     renderer always emits PCM stereo) with a structured unsupported result.
/tmp/batch2-r6.diff-40-+3. **Channels-only fallback bypasses layout normalization** →
/tmp/batch2-r6.diff:41:+   - `_layout_channel_count` lowercases the declared layout before lookup, so
/tmp/batch2-r6.diff-42-+     `"Stereo"` and `"stereo"` both map to 2 channels.
/tmp/batch2-r6.diff-43-+4. **Symlink exemption overbroad** →
/tmp/batch2-r6.diff-44-+   - Exemption now applies ONLY to root-level `/tmp|/var|/etc` →
/tmp/batch2-r6.diff-45-+     `/private/<name>` macOS redirects; any other symlink component (named
/tmp/batch2-r6.diff-46-+     tmp/var/etc elsewhere, or resolving under /private/ from a non-root
--
/tmp/batch2-r6.diff-254-+git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
/tmp/batch2-r6.diff-255-+?? .oracle/checkins/batch-2-r5.md
/tmp/batch2-r6.diff-256-+git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
/tmp/batch2-r6.diff-257-+3557792f931f224c5f8aea2611c901d0f16baa0f
/tmp/batch2-r6.diff-258-+git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
/tmp/batch2-r6.diff:259:+3557792f (HEAD -> oracle-run) batch2-rework5: oracle re-review4 issues 1-5 (OSError-safe drain + guaranteed direct-child reap, support rejects audio!=rendered, layout channel-count normalization, tight root-only macOS symlink exemption, committed-read guard before resolve)
/tmp/batch2-r6.diff-260-+ .oracle/checkins/batch-2-r4.md                     | 20120 +++++++++++++++++++
/tmp/batch2-r6.diff-261-+ astrid/core/media.py                               |     3 +-
/tmp/batch2-r6.diff-262-+ astrid/core/rendering/artifacts.py                 |     2 +-
/tmp/batch2-r6.diff-263-+ astrid/core/rendering/publication.py               |    23 +-
/tmp/batch2-r6.diff-264-+ astrid/core/rendering/transport.py                 |    13 +-
--
/tmp/batch2-r6.diff-770-+             expected = _profile_value(profile, field)
/tmp/batch2-r6.diff-771-+             if field == "audio_channel_layout" and actual is None:
/tmp/batch2-r6.diff-772-+                 # Some containers (QuickTime sowt) expose channel COUNT but
/tmp/batch2-r6.diff-773-+                 # not a named layout. Compare channel count against the
/tmp/batch2-r6.diff-774-+                 # declared layout's canonical count instead of failing.
/tmp/batch2-r6.diff:775:+                 expected_channels = _layout_channel_count(expected)
/tmp/batch2-r6.diff-776-+                 if expected_channels is None or probe.audio_channels != expected_channels:
/tmp/batch2-r6.diff-777-+                     _invalid(
/tmp/batch2-r6.diff-778-+                         "audio_profile_mismatch",
/tmp/batch2-r6.diff-779-+                         f"probed audio channel layout/count does not match {label}",
/tmp/batch2-r6.diff-780-+                         field=field,
--
/tmp/batch2-r6.diff-791-+                     expected=expected,
/tmp/batch2-r6.diff-792-+                     actual=actual,
/tmp/batch2-r6.diff-793-+                 )
/tmp/batch2-r6.diff-794-+ 
/tmp/batch2-r6.diff-795-+ 
/tmp/batch2-r6.diff:796:+ def _layout_channel_count(layout: str | None) -> int | None:
/tmp/batch2-r6.diff-797-+     return {
/tmp/batch2-r6.diff-798-+         "mono": 1,
/tmp/batch2-r6.diff-799-+         "stereo": 2,
/tmp/batch2-r6.diff-800-+         "5.1": 6,
/tmp/batch2-r6.diff-801-+         "5.1(side)": 6,
--
/tmp/batch2-r6.diff-4578-+            expected = _profile_value(profile, field)
/tmp/batch2-r6.diff-4579-+            if field == "audio_channel_layout" and actual is None:
/tmp/batch2-r6.diff-4580-+                # Some containers (QuickTime sowt) expose channel COUNT but
/tmp/batch2-r6.diff-4581-+                # not a named layout. Compare channel count against the
/tmp/batch2-r6.diff-4582-+                # declared layout's canonical count instead of failing.
/tmp/batch2-r6.diff:4583:+                expected_channels = _layout_channel_count(expected)
/tmp/batch2-r6.diff-4584-+                if expected_channels is None or probe.audio_channels != expected_channels:
/tmp/batch2-r6.diff-4585-+                    _invalid(
/tmp/batch2-r6.diff-4586-+                        "audio_profile_mismatch",
/tmp/batch2-r6.diff-4587-+                        f"probed audio channel layout/count does not match {label}",
/tmp/batch2-r6.diff-4588-+                        field=field,
--
/tmp/batch2-r6.diff-4599-+                    expected=expected,
/tmp/batch2-r6.diff-4600-+                    actual=actual,
/tmp/batch2-r6.diff-4601-+                )
/tmp/batch2-r6.diff-4602-+
/tmp/batch2-r6.diff-4603-+
/tmp/batch2-r6.diff:4604:+def _layout_channel_count(layout: str | None) -> int | None:
/tmp/batch2-r6.diff-4605-+    return {
/tmp/batch2-r6.diff-4606-+        "mono": 1,
/tmp/batch2-r6.diff-4607-+        "stereo": 2,
/tmp/batch2-r6.diff-4608-+        "5.1": 6,
/tmp/batch2-r6.diff-4609-+        "5.1(side)": 6,
--
/tmp/batch2-r6.diff-7387-+   449	            expected = _profile_value(profile, field)
/tmp/batch2-r6.diff-7388-+   450	            if field == "audio_channel_layout" and actual is None:
/tmp/batch2-r6.diff-7389-+   451	                # Some containers (QuickTime sowt) expose channel COUNT but
/tmp/batch2-r6.diff-7390-+   452	                # not a named layout. Compare channel count against the
/tmp/batch2-r6.diff-7391-+   453	                # declared layout's canonical count instead of failing.
/tmp/batch2-r6.diff:7392:+   454	                expected_channels = _layout_channel_count(expected)
/tmp/batch2-r6.diff-7393-+   455	                if expected_channels is None or probe.audio_channels != expected_channels:
/tmp/batch2-r6.diff-7394-+   456	                    _invalid(
/tmp/batch2-r6.diff-7395-+   457	                        "audio_profile_mismatch",
/tmp/batch2-r6.diff-7396-+   458	                        f"probed audio channel layout/count does not match {label}",
/tmp/batch2-r6.diff-7397-+   459	                        field=field,
--
/tmp/batch2-r6.diff-7408-+   470	                    expected=expected,
/tmp/batch2-r6.diff-7409-+   471	                    actual=actual,
/tmp/batch2-r6.diff-7410-+   472	                )
/tmp/batch2-r6.diff-7411-+   473	
/tmp/batch2-r6.diff-7412-+   474	
/tmp/batch2-r6.diff:7413:+   475	def _layout_channel_count(layout: str | None) -> int | None:
/tmp/batch2-r6.diff-7414-+   476	    return {
/tmp/batch2-r6.diff-7415-+   477	        "mono": 1,
/tmp/batch2-r6.diff-7416-+   478	        "stereo": 2,
/tmp/batch2-r6.diff-7417-+   479	        "5.1": 6,
/tmp/batch2-r6.diff-7418-+   480	        "5.1(side)": 6,
--
/tmp/batch2-r6.diff-7655-+   203	    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
/tmp/batch2-r6.diff-7656-+   204	        return None
/tmp/batch2-r6.diff-7657-+   205	    try:
/tmp/batch2-r6.diff-7658-+
/tmp/batch2-r6.diff-7659-+codex
/tmp/batch2-r6.diff:7660:+- `_support()` discards audio mismatches when `profile` is `null`; a valid request with `audio="none", profile=null` still returns `supported: true`. [backend.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:451)
/tmp/batch2-r6.diff-7661-+
/tmp/batch2-r6.diff:7662:+- `_layout_channel_count()` lowercases but does not strip whitespace like normal profile normalization. A valid `" Stereo "` layout matches `"stereo"` normally but fails the channels-only fallback. [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:475)
/tmp/batch2-r6.diff-7663-+tokens used
/tmp/batch2-r6.diff-7664-+124,964
/tmp/batch2-r6.diff:7665:+- `_support()` discards audio mismatches when `profile` is `null`; a valid request with `audio="none", profile=null` still returns `supported: true`. [backend.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:451)
/tmp/batch2-r6.diff-7666-+
/tmp/batch2-r6.diff:7667:+- `_layout_channel_count()` lowercases but does not strip whitespace like normal profile normalization. A valid `" Stereo "` layout matches `"stereo"` normally but fails the channels-only fallback. [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:475)
/tmp/batch2-r6.diff-7668-diff --git a/astrid/core/rendering/artifacts.py b/astrid/core/rendering/artifacts.py
/tmp/batch2-r6.diff-7669-index 736bd7a5..e4a11bdd 100644
/tmp/batch2-r6.diff-7670---- a/astrid/core/rendering/artifacts.py
/tmp/batch2-r6.diff-7671-+++ b/astrid/core/rendering/artifacts.py
/tmp/batch2-r6.diff:7672:@@ -480,7 +480,7 @@ def _layout_channel_count(layout: str | None) -> int | None:
/tmp/batch2-r6.diff-7673-         "5.1(side)": 6,
/tmp/batch2-r6.diff-7674-         "7.1": 8,
/tmp/batch2-r6.diff-7675-         "7.1(wide)": 8,
/tmp/batch2-r6.diff-7676--    }.get((layout or "").lower())
/tmp/batch2-r6.diff-7677-+    }.get((layout or "").strip().lower())
--
.oracle/checkins/batch-2-r5.md-30-     kill → wait).
.oracle/checkins/batch-2-r5.md-31-2. **support returns supported:true for audio="none"** →
.oracle/checkins/batch-2-r5.md-32-   - `_support` now rejects any request `audio` other than `rendered` (the
.oracle/checkins/batch-2-r5.md-33-     renderer always emits PCM stereo) with a structured unsupported result.
.oracle/checkins/batch-2-r5.md-34-3. **Channels-only fallback bypasses layout normalization** →
.oracle/checkins/batch-2-r5.md:35:   - `_layout_channel_count` lowercases the declared layout before lookup, so
.oracle/checkins/batch-2-r5.md-36-     `"Stereo"` and `"stereo"` both map to 2 channels.
.oracle/checkins/batch-2-r5.md-37-4. **Symlink exemption overbroad** →
.oracle/checkins/batch-2-r5.md-38-   - Exemption now applies ONLY to root-level `/tmp|/var|/etc` →
.oracle/checkins/batch-2-r5.md-39-     `/private/<name>` macOS redirects; any other symlink component (named
.oracle/checkins/batch-2-r5.md-40-     tmp/var/etc elsewhere, or resolving under /private/ from a non-root
--
.oracle/checkins/batch-2-r5.md-248-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r5.md-249-?? .oracle/checkins/batch-2-r5.md
.oracle/checkins/batch-2-r5.md-250-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r5.md-251-3557792f931f224c5f8aea2611c901d0f16baa0f
.oracle/checkins/batch-2-r5.md-252-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r5.md:253:3557792f (HEAD -> oracle-run) batch2-rework5: oracle re-review4 issues 1-5 (OSError-safe drain + guaranteed direct-child reap, support rejects audio!=rendered, layout channel-count normalization, tight root-only macOS symlink exemption, committed-read guard before resolve)
.oracle/checkins/batch-2-r5.md-254- .oracle/checkins/batch-2-r4.md                     | 20120 +++++++++++++++++++
.oracle/checkins/batch-2-r5.md-255- astrid/core/media.py                               |     3 +-
.oracle/checkins/batch-2-r5.md-256- astrid/core/rendering/artifacts.py                 |     2 +-
.oracle/checkins/batch-2-r5.md-257- astrid/core/rendering/publication.py               |    23 +-
.oracle/checkins/batch-2-r5.md-258- astrid/core/rendering/transport.py                 |    13 +-
--
.oracle/checkins/batch-2-r5.md-764-             expected = _profile_value(profile, field)
.oracle/checkins/batch-2-r5.md-765-             if field == "audio_channel_layout" and actual is None:
.oracle/checkins/batch-2-r5.md-766-                 # Some containers (QuickTime sowt) expose channel COUNT but
.oracle/checkins/batch-2-r5.md-767-                 # not a named layout. Compare channel count against the
.oracle/checkins/batch-2-r5.md-768-                 # declared layout's canonical count instead of failing.
.oracle/checkins/batch-2-r5.md:769:                 expected_channels = _layout_channel_count(expected)
.oracle/checkins/batch-2-r5.md-770-                 if expected_channels is None or probe.audio_channels != expected_channels:
.oracle/checkins/batch-2-r5.md-771-                     _invalid(
.oracle/checkins/batch-2-r5.md-772-                         "audio_profile_mismatch",
.oracle/checkins/batch-2-r5.md-773-                         f"probed audio channel layout/count does not match {label}",
.oracle/checkins/batch-2-r5.md-774-                         field=field,
--
.oracle/checkins/batch-2-r5.md-785-                     expected=expected,
.oracle/checkins/batch-2-r5.md-786-                     actual=actual,
.oracle/checkins/batch-2-r5.md-787-                 )
.oracle/checkins/batch-2-r5.md-788- 
.oracle/checkins/batch-2-r5.md-789- 
.oracle/checkins/batch-2-r5.md:790: def _layout_channel_count(layout: str | None) -> int | None:
.oracle/checkins/batch-2-r5.md-791-     return {
.oracle/checkins/batch-2-r5.md-792-         "mono": 1,
.oracle/checkins/batch-2-r5.md-793-         "stereo": 2,
.oracle/checkins/batch-2-r5.md-794-         "5.1": 6,
.oracle/checkins/batch-2-r5.md-795-         "5.1(side)": 6,
--
.oracle/checkins/batch-2-r5.md-4572-            expected = _profile_value(profile, field)
.oracle/checkins/batch-2-r5.md-4573-            if field == "audio_channel_layout" and actual is None:
.oracle/checkins/batch-2-r5.md-4574-                # Some containers (QuickTime sowt) expose channel COUNT but
.oracle/checkins/batch-2-r5.md-4575-                # not a named layout. Compare channel count against the
.oracle/checkins/batch-2-r5.md-4576-                # declared layout's canonical count instead of failing.
.oracle/checkins/batch-2-r5.md:4577:                expected_channels = _layout_channel_count(expected)
.oracle/checkins/batch-2-r5.md-4578-                if expected_channels is None or probe.audio_channels != expected_channels:
.oracle/checkins/batch-2-r5.md-4579-                    _invalid(
.oracle/checkins/batch-2-r5.md-4580-                        "audio_profile_mismatch",
.oracle/checkins/batch-2-r5.md-4581-                        f"probed audio channel layout/count does not match {label}",
.oracle/checkins/batch-2-r5.md-4582-                        field=field,
--
.oracle/checkins/batch-2-r5.md-4593-                    expected=expected,
.oracle/checkins/batch-2-r5.md-4594-                    actual=actual,
.oracle/checkins/batch-2-r5.md-4595-                )
.oracle/checkins/batch-2-r5.md-4596-
.oracle/checkins/batch-2-r5.md-4597-
.oracle/checkins/batch-2-r5.md:4598:def _layout_channel_count(layout: str | None) -> int | None:
.oracle/checkins/batch-2-r5.md-4599-    return {
.oracle/checkins/batch-2-r5.md-4600-        "mono": 1,
.oracle/checkins/batch-2-r5.md-4601-        "stereo": 2,
.oracle/checkins/batch-2-r5.md-4602-        "5.1": 6,
.oracle/checkins/batch-2-r5.md-4603-        "5.1(side)": 6,
--
.oracle/checkins/batch-2-r5.md-7381-   449	            expected = _profile_value(profile, field)
.oracle/checkins/batch-2-r5.md-7382-   450	            if field == "audio_channel_layout" and actual is None:
.oracle/checkins/batch-2-r5.md-7383-   451	                # Some containers (QuickTime sowt) expose channel COUNT but
.oracle/checkins/batch-2-r5.md-7384-   452	                # not a named layout. Compare channel count against the
.oracle/checkins/batch-2-r5.md-7385-   453	                # declared layout's canonical count instead of failing.
.oracle/checkins/batch-2-r5.md:7386:   454	                expected_channels = _layout_channel_count(expected)
.oracle/checkins/batch-2-r5.md-7387-   455	                if expected_channels is None or probe.audio_channels != expected_channels:
.oracle/checkins/batch-2-r5.md-7388-   456	                    _invalid(
.oracle/checkins/batch-2-r5.md-7389-   457	                        "audio_profile_mismatch",
.oracle/checkins/batch-2-r5.md-7390-   458	                        f"probed audio channel layout/count does not match {label}",
.oracle/checkins/batch-2-r5.md-7391-   459	                        field=field,
--
.oracle/checkins/batch-2-r5.md-7402-   470	                    expected=expected,
.oracle/checkins/batch-2-r5.md-7403-   471	                    actual=actual,
.oracle/checkins/batch-2-r5.md-7404-   472	                )
.oracle/checkins/batch-2-r5.md-7405-   473	
.oracle/checkins/batch-2-r5.md-7406-   474	
.oracle/checkins/batch-2-r5.md:7407:   475	def _layout_channel_count(layout: str | None) -> int | None:
.oracle/checkins/batch-2-r5.md-7408-   476	    return {
.oracle/checkins/batch-2-r5.md-7409-   477	        "mono": 1,
.oracle/checkins/batch-2-r5.md-7410-   478	        "stereo": 2,
.oracle/checkins/batch-2-r5.md-7411-   479	        "5.1": 6,
.oracle/checkins/batch-2-r5.md-7412-   480	        "5.1(side)": 6,
--
.oracle/checkins/batch-2-r5.md-7649-   203	    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
.oracle/checkins/batch-2-r5.md-7650-   204	        return None
.oracle/checkins/batch-2-r5.md-7651-   205	    try:
.oracle/checkins/batch-2-r5.md-7652-
.oracle/checkins/batch-2-r5.md-7653-codex
.oracle/checkins/batch-2-r5.md:7654:- `_support()` discards audio mismatches when `profile` is `null`; a valid request with `audio="none", profile=null` still returns `supported: true`. [backend.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:451)
.oracle/checkins/batch-2-r5.md-7655-
.oracle/checkins/batch-2-r5.md:7656:- `_layout_channel_count()` lowercases but does not strip whitespace like normal profile normalization. A valid `" Stereo "` layout matches `"stereo"` normally but fails the channels-only fallback. [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:475)
.oracle/checkins/batch-2-r5.md-7657-tokens used
.oracle/checkins/batch-2-r5.md-7658-124,964
.oracle/checkins/batch-2-r5.md:7659:- `_support()` discards audio mismatches when `profile` is `null`; a valid request with `audio="none", profile=null` still returns `supported: true`. [backend.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:451)
.oracle/checkins/batch-2-r5.md-7660-
.oracle/checkins/batch-2-r5.md:7661:- `_layout_channel_count()` lowercases but does not strip whitespace like normal profile normalization. A valid `" Stereo "` layout matches `"stereo"` normally but fails the channels-only fallback. [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:475)

exec
/bin/zsh -lc "rg -n -C 8 \"Stereo|audio_channel_layout|channels.only|channel count|audio='none'|\\\"audio\\\": \\\"none\\\"|profile.*None\" tests/core/rendering astrid/core/rendering | head -n 360" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/provenance.py-312-
astrid/core/rendering/provenance.py-313-def assemble_provenance_v2(
astrid/core/rendering/provenance.py-314-    *,
astrid/core/rendering/provenance.py-315-    engine: str,
astrid/core/rendering/provenance.py-316-    output: str | Path,
astrid/core/rendering/provenance.py-317-    timeline: str | Path,
astrid/core/rendering/provenance.py-318-    assets_registry: str | Path | None,
astrid/core/rendering/provenance.py-319-    plan: RenderPlan | Mapping[str, Any],
astrid/core/rendering/provenance.py:320:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py-321-    audio_ownership: AudioOwnership | str | None = None,
astrid/core/rendering/provenance.py-322-    normalization: Sequence[str] = (),
astrid/core/rendering/provenance.py-323-    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
astrid/core/rendering/provenance.py-324-    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
astrid/core/rendering/provenance.py-325-    v1_compatibility: Mapping[str, Any] | None = None,
astrid/core/rendering/provenance.py-326-) -> dict[str, Any]:
astrid/core/rendering/provenance.py-327-    """Assemble additive provenance v2 with protected ownership boundaries.
astrid/core/rendering/provenance.py-328-
--
astrid/core/rendering/artifacts.py-284-    if field == "video_level":
astrid/core/rendering/artifacts.py-285-        return _level(actual) == _level(expected)
astrid/core/rendering/artifacts.py-286-    if field in {
astrid/core/rendering/artifacts.py-287-        "container",
astrid/core/rendering/artifacts.py-288-        "video_codec",
astrid/core/rendering/artifacts.py-289-        "video_profile",
astrid/core/rendering/artifacts.py-290-        "pixel_format",
astrid/core/rendering/artifacts.py-291-        "audio_codec",
astrid/core/rendering/artifacts.py:292:        "audio_channel_layout",
astrid/core/rendering/artifacts.py-293-    }:
astrid/core/rendering/artifacts.py-294-        return _text(actual) == _text(expected)
astrid/core/rendering/artifacts.py-295-    return actual == expected
astrid/core/rendering/artifacts.py-296-
astrid/core/rendering/artifacts.py-297-
astrid/core/rendering/artifacts.py-298-def _compare_declared_to_expected(
astrid/core/rendering/artifacts.py-299-    declared: RenderProfile,
astrid/core/rendering/artifacts.py-300-    expected: RenderProfile,
--
astrid/core/rendering/artifacts.py-336-    if ownership is AudioOwnership.RENDERED:
astrid/core/rendering/artifacts.py-337-        if not expected.has_audio:
astrid/core/rendering/artifacts.py-338-            _invalid(
astrid/core/rendering/artifacts.py-339-                "audio_profile_mismatch",
astrid/core/rendering/artifacts.py-340-                "renderer declared rendered audio for a visual-only canonical profile",
astrid/core/rendering/artifacts.py-341-                expected_audio=False,
astrid/core/rendering/artifacts.py-342-                actual_audio=True,
astrid/core/rendering/artifacts.py-343-            )
astrid/core/rendering/artifacts.py:344:        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
astrid/core/rendering/artifacts.py-345-            if not _same_profile_value(
astrid/core/rendering/artifacts.py-346-                field, _profile_value(declared, field), _profile_value(expected, field)
astrid/core/rendering/artifacts.py-347-            ):
astrid/core/rendering/artifacts.py-348-                _invalid(
astrid/core/rendering/artifacts.py-349-                    "audio_profile_mismatch",
astrid/core/rendering/artifacts.py-350-                    f"renderer audio profile has incompatible {field}",
astrid/core/rendering/artifacts.py-351-                    field=field,
astrid/core/rendering/artifacts.py-352-                    expected=_profile_value(expected, field),
--
astrid/core/rendering/artifacts.py-439-                expected=expected,
astrid/core/rendering/artifacts.py-440-                actual=actual,
astrid/core/rendering/artifacts.py-441-            )
astrid/core/rendering/artifacts.py-442-
astrid/core/rendering/artifacts.py-443-    if compare_audio:
astrid/core/rendering/artifacts.py-444-        for field, actual in (
astrid/core/rendering/artifacts.py-445-            ("audio_codec", probe.audio_codec),
astrid/core/rendering/artifacts.py-446-            ("audio_sample_rate", probe.audio_sample_rate),
astrid/core/rendering/artifacts.py:447:            ("audio_channel_layout", probe.audio_channel_layout),
astrid/core/rendering/artifacts.py-448-        ):
astrid/core/rendering/artifacts.py-449-            expected = _profile_value(profile, field)
astrid/core/rendering/artifacts.py:450:            if field == "audio_channel_layout" and actual is None:
astrid/core/rendering/artifacts.py-451-                # Some containers (QuickTime sowt) expose channel COUNT but
astrid/core/rendering/artifacts.py:452:                # not a named layout. Compare channel count against the
astrid/core/rendering/artifacts.py-453-                # declared layout's canonical count instead of failing.
astrid/core/rendering/artifacts.py-454-                expected_channels = _layout_channel_count(expected)
astrid/core/rendering/artifacts.py-455-                if expected_channels is None or probe.audio_channels != expected_channels:
astrid/core/rendering/artifacts.py-456-                    _invalid(
astrid/core/rendering/artifacts.py-457-                        "audio_profile_mismatch",
astrid/core/rendering/artifacts.py-458-                        f"probed audio channel layout/count does not match {label}",
astrid/core/rendering/artifacts.py-459-                        field=field,
astrid/core/rendering/artifacts.py-460-                        expected=expected,
--
astrid/core/rendering/artifacts.py-492-) -> None:
astrid/core/rendering/artifacts.py-493-    has_audio = probe.has_audio_stream
astrid/core/rendering/artifacts.py-494-    if has_audio:
astrid/core/rendering/artifacts.py-495-        missing = [
astrid/core/rendering/artifacts.py-496-            field
astrid/core/rendering/artifacts.py-497-            for field in ("audio_codec", "audio_sample_rate")
astrid/core/rendering/artifacts.py-498-            if getattr(probe, field) is None
astrid/core/rendering/artifacts.py-499-        ]
astrid/core/rendering/artifacts.py:500:        if probe.audio_channel_layout is None and probe.audio_channels is None:
astrid/core/rendering/artifacts.py:501:            missing.append("audio_channel_layout/audio_channels")
astrid/core/rendering/artifacts.py-502-        if missing:
astrid/core/rendering/artifacts.py-503-            _invalid(
astrid/core/rendering/artifacts.py-504-                "incomplete_probe",
astrid/core/rendering/artifacts.py-505-                "ffprobe returned an audio stream with incomplete metadata",
astrid/core/rendering/artifacts.py-506-                missing=missing,
astrid/core/rendering/artifacts.py-507-            )
astrid/core/rendering/artifacts.py-508-
astrid/core/rendering/artifacts.py-509-    if ownership is AudioOwnership.RENDERED and not has_audio:
--
tests/core/rendering/test_raw_command_fixture.py-173-    assert profile.height == 1080
tests/core/rendering/test_raw_command_fixture.py-174-    assert profile.fps_rational == (24, 1)
tests/core/rendering/test_raw_command_fixture.py-175-    assert profile.time_base == (1, 12288)
tests/core/rendering/test_raw_command_fixture.py-176-    assert profile.container == "mp4"
tests/core/rendering/test_raw_command_fixture.py-177-    assert profile.video_codec == "h264"
tests/core/rendering/test_raw_command_fixture.py-178-    assert profile.pixel_format == "yuv420p"
tests/core/rendering/test_raw_command_fixture.py-179-    assert profile.audio_codec == "pcm_s16le"
tests/core/rendering/test_raw_command_fixture.py-180-    assert profile.audio_sample_rate == 48000
tests/core/rendering/test_raw_command_fixture.py:181:    assert profile.audio_channel_layout == "stereo"
tests/core/rendering/test_raw_command_fixture.py-182-
tests/core/rendering/test_raw_command_fixture.py-183-
tests/core/rendering/test_raw_command_fixture.py-184-# ---------------------------------------------------------------------------
tests/core/rendering/test_raw_command_fixture.py-185-# Static discovery / validation (no code import)
tests/core/rendering/test_raw_command_fixture.py-186-# ---------------------------------------------------------------------------
tests/core/rendering/test_raw_command_fixture.py-187-
tests/core/rendering/test_raw_command_fixture.py-188-
tests/core/rendering/test_raw_command_fixture.py-189-def test_fixture_pack_validates_and_inspects_without_importing_backend(
--
tests/core/rendering/test_raw_command_fixture.py-298-    second_workspace = tmp_path / "workspace-2"
tests/core/rendering/test_raw_command_fixture.py-299-    _, second_result, _ = _run_transport(second_workspace, PACK_ROOT, verb="render")
tests/core/rendering/test_raw_command_fixture.py-300-    first_bytes = (workspace / result.video.path).read_bytes()
tests/core/rendering/test_raw_command_fixture.py-301-    second_bytes = (second_workspace / second_result.video.path).read_bytes()
tests/core/rendering/test_raw_command_fixture.py-302-    assert first_bytes == second_bytes
tests/core/rendering/test_raw_command_fixture.py-303-    assert result.video.sha256 == second_result.video.sha256
tests/core/rendering/test_raw_command_fixture.py-304-
tests/core/rendering/test_raw_command_fixture.py-305-
tests/core/rendering/test_raw_command_fixture.py:306:def test_support_rejects_audio_none_even_with_null_profile(tmp_path: Path) -> None:
tests/core/rendering/test_raw_command_fixture.py:307:    """A request for audio='none' with profile=null is unsupported: the
tests/core/rendering/test_raw_command_fixture.py-308-    renderer always produces rendered PCM stereo audio."""
tests/core/rendering/test_raw_command_fixture.py-309-    workspace = tmp_path / "workspace"
tests/core/rendering/test_raw_command_fixture.py-310-    workspace.mkdir(parents=True, exist_ok=True)
tests/core/rendering/test_raw_command_fixture.py-311-    request_path = workspace / "request.json"
tests/core/rendering/test_raw_command_fixture.py-312-    request_path.write_text(
tests/core/rendering/test_raw_command_fixture.py-313-        json.dumps(
tests/core/rendering/test_raw_command_fixture.py-314-            {
tests/core/rendering/test_raw_command_fixture.py-315-                "schema_version": 1,
tests/core/rendering/test_raw_command_fixture.py-316-                "output_name": "raw_command.mp4",
tests/core/rendering/test_raw_command_fixture.py:317:                "audio": "none",
tests/core/rendering/test_raw_command_fixture.py:318:                "profile": None,
tests/core/rendering/test_raw_command_fixture.py-319-            }
tests/core/rendering/test_raw_command_fixture.py-320-        ),
tests/core/rendering/test_raw_command_fixture.py-321-        encoding="utf-8",
tests/core/rendering/test_raw_command_fixture.py-322-    )
tests/core/rendering/test_raw_command_fixture.py-323-    result_path = workspace / "result.json"
tests/core/rendering/test_raw_command_fixture.py-324-    transport = CommandTransport(BACKEND_ID, termination_grace=0.15)
tests/core/rendering/test_raw_command_fixture.py-325-    report = transport.run(
tests/core/rendering/test_raw_command_fixture.py-326-        "support",
--
astrid/core/rendering/profile.py-276-
astrid/core/rendering/profile.py-277-    return RenderProfile(
astrid/core/rendering/profile.py-278-        width=width,
astrid/core/rendering/profile.py-279-        height=height,
astrid/core/rendering/profile.py-280-        fps_rational=(fps.numerator, fps.denominator),
astrid/core/rendering/profile.py-281-        time_base=_mp4_time_base(fps),
astrid/core/rendering/profile.py-282-        container="mp4",
astrid/core/rendering/profile.py-283-        video_codec="h264",
astrid/core/rendering/profile.py:284:        video_profile=None,
astrid/core/rendering/profile.py-285-        video_level=None,
astrid/core/rendering/profile.py-286-        pixel_format="yuv420p",
astrid/core/rendering/profile.py-287-        audio_codec="aac" if rendered_audio else None,
astrid/core/rendering/profile.py-288-        audio_sample_rate=48_000 if rendered_audio else None,
astrid/core/rendering/profile.py:289:        audio_channel_layout="stereo" if rendered_audio else None,
astrid/core/rendering/profile.py-290-        duration_tolerance=duration_tolerance,
astrid/core/rendering/profile.py-291-    )
astrid/core/rendering/profile.py-292-
astrid/core/rendering/profile.py-293-
astrid/core/rendering/profile.py-294-__all__ = ["resolve_render_profile"]
--
tests/core/rendering/fixtures/v1/finalize.json-93-      ],
tests/core/rendering/fixtures/v1/finalize.json-94-      "container": "mp4",
tests/core/rendering/fixtures/v1/finalize.json-95-      "video_codec": "h264",
tests/core/rendering/fixtures/v1/finalize.json-96-      "video_profile": null,
tests/core/rendering/fixtures/v1/finalize.json-97-      "video_level": null,
tests/core/rendering/fixtures/v1/finalize.json-98-      "pixel_format": "yuv420p",
tests/core/rendering/fixtures/v1/finalize.json-99-      "audio_codec": null,
tests/core/rendering/fixtures/v1/finalize.json-100-      "audio_sample_rate": null,
tests/core/rendering/fixtures/v1/finalize.json:101:      "audio_channel_layout": null,
tests/core/rendering/fixtures/v1/finalize.json-102-      "duration_tolerance": 1
tests/core/rendering/fixtures/v1/finalize.json-103-    },
tests/core/rendering/fixtures/v1/finalize.json-104-    "total_frames": 1,
tests/core/rendering/fixtures/v1/finalize.json-105-    "reasons": {
tests/core/rendering/fixtures/v1/finalize.json-106-      "0": "visual-only fixture"
tests/core/rendering/fixtures/v1/finalize.json-107-    },
tests/core/rendering/fixtures/v1/finalize.json-108-    "window": null
tests/core/rendering/fixtures/v1/finalize.json-109-  },
--
tests/core/rendering/fixtures/v1/finalize.json-123-        ],
tests/core/rendering/fixtures/v1/finalize.json-124-        "container": "mp4",
tests/core/rendering/fixtures/v1/finalize.json-125-        "video_codec": "h264",
tests/core/rendering/fixtures/v1/finalize.json-126-        "video_profile": null,
tests/core/rendering/fixtures/v1/finalize.json-127-        "video_level": null,
tests/core/rendering/fixtures/v1/finalize.json-128-        "pixel_format": "yuv420p",
tests/core/rendering/fixtures/v1/finalize.json-129-        "audio_codec": null,
tests/core/rendering/fixtures/v1/finalize.json-130-        "audio_sample_rate": null,
tests/core/rendering/fixtures/v1/finalize.json:131:        "audio_channel_layout": null,
tests/core/rendering/fixtures/v1/finalize.json-132-        "duration_tolerance": 1
tests/core/rendering/fixtures/v1/finalize.json-133-      },
tests/core/rendering/fixtures/v1/finalize.json-134-      "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
tests/core/rendering/fixtures/v1/finalize.json-135-      "duration_frames": 1,
tests/core/rendering/fixtures/v1/finalize.json:136:      "audio": "none",
tests/core/rendering/fixtures/v1/finalize.json-137-      "attachments": {}
tests/core/rendering/fixtures/v1/finalize.json-138-    }
tests/core/rendering/fixtures/v1/finalize.json-139-  ],
tests/core/rendering/fixtures/v1/finalize.json-140-  "output_name": "video.mp4",
tests/core/rendering/fixtures/v1/finalize.json-141-  "backend_config": {
tests/core/rendering/fixtures/v1/finalize.json-142-    "rendering.ffmpeg-finalizer": {}
tests/core/rendering/fixtures/v1/finalize.json-143-  },
tests/core/rendering/fixtures/v1/finalize.json-144-  "metadata": {}
--
astrid/core/rendering/contracts.py-453-    """Resolved media profile used to validate and finalize artifacts."""
astrid/core/rendering/contracts.py-454-
astrid/core/rendering/contracts.py-455-    width: int
astrid/core/rendering/contracts.py-456-    height: int
astrid/core/rendering/contracts.py-457-    fps_rational: tuple[int, int]
astrid/core/rendering/contracts.py-458-    time_base: tuple[int, int]
astrid/core/rendering/contracts.py-459-    video_codec: str
astrid/core/rendering/contracts.py-460-    pixel_format: str
astrid/core/rendering/contracts.py:461:    video_profile: str | None = None
astrid/core/rendering/contracts.py-462-    video_level: str | None = None
astrid/core/rendering/contracts.py-463-    container: str = "mp4"
astrid/core/rendering/contracts.py-464-    audio_codec: str | None = None
astrid/core/rendering/contracts.py-465-    audio_sample_rate: int | None = None
astrid/core/rendering/contracts.py:466:    audio_channel_layout: str | None = None
astrid/core/rendering/contracts.py-467-    duration_tolerance: int = 1
astrid/core/rendering/contracts.py-468-
astrid/core/rendering/contracts.py-469-    def __post_init__(self) -> None:
astrid/core/rendering/contracts.py-470-        object.__setattr__(self, "width", _require_int(self.width, "width", minimum=1))
astrid/core/rendering/contracts.py-471-        object.__setattr__(self, "height", _require_int(self.height, "height", minimum=1))
astrid/core/rendering/contracts.py-472-        object.__setattr__(self, "fps_rational", _require_rational(self.fps_rational, "fps_rational"))
astrid/core/rendering/contracts.py-473-        object.__setattr__(self, "time_base", _require_rational(self.time_base, "time_base"))
astrid/core/rendering/contracts.py-474-        object.__setattr__(self, "video_codec", _require_string(self.video_codec, "video_codec"))
--
astrid/core/rendering/contracts.py-482-            self,
astrid/core/rendering/contracts.py-483-            "video_level",
astrid/core/rendering/contracts.py-484-            _require_optional_string(self.video_level, "video_level"),
astrid/core/rendering/contracts.py-485-        )
astrid/core/rendering/contracts.py-486-        object.__setattr__(self, "container", _require_string(self.container, "container"))
astrid/core/rendering/contracts.py-487-        audio_values = (
astrid/core/rendering/contracts.py-488-            self.audio_codec,
astrid/core/rendering/contracts.py-489-            self.audio_sample_rate,
astrid/core/rendering/contracts.py:490:            self.audio_channel_layout,
astrid/core/rendering/contracts.py-491-        )
astrid/core/rendering/contracts.py-492-        if any(value is not None for value in audio_values) and not all(
astrid/core/rendering/contracts.py-493-            value is not None for value in audio_values
astrid/core/rendering/contracts.py-494-        ):
astrid/core/rendering/contracts.py-495-            raise ValueError(
astrid/core/rendering/contracts.py:496:                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
astrid/core/rendering/contracts.py-497-                "provided together or all omitted"
astrid/core/rendering/contracts.py-498-            )
astrid/core/rendering/contracts.py-499-        if self.audio_codec is not None:
astrid/core/rendering/contracts.py-500-            object.__setattr__(self, "audio_codec", _require_string(self.audio_codec, "audio_codec"))
astrid/core/rendering/contracts.py-501-            object.__setattr__(
astrid/core/rendering/contracts.py-502-                self,
astrid/core/rendering/contracts.py-503-                "audio_sample_rate",
astrid/core/rendering/contracts.py-504-                _require_int(self.audio_sample_rate, "audio_sample_rate", minimum=1),
astrid/core/rendering/contracts.py-505-            )
astrid/core/rendering/contracts.py-506-            object.__setattr__(
astrid/core/rendering/contracts.py-507-                self,
astrid/core/rendering/contracts.py:508:                "audio_channel_layout",
astrid/core/rendering/contracts.py:509:                _require_string(self.audio_channel_layout, "audio_channel_layout"),
astrid/core/rendering/contracts.py-510-            )
astrid/core/rendering/contracts.py-511-        object.__setattr__(
astrid/core/rendering/contracts.py-512-            self,
astrid/core/rendering/contracts.py-513-            "duration_tolerance",
astrid/core/rendering/contracts.py-514-            _require_int(self.duration_tolerance, "duration_tolerance", minimum=0),
astrid/core/rendering/contracts.py-515-        )
astrid/core/rendering/contracts.py-516-
astrid/core/rendering/contracts.py-517-    @property
--
astrid/core/rendering/contracts.py-527-                "time_base": self.time_base,
astrid/core/rendering/contracts.py-528-                "container": self.container,
astrid/core/rendering/contracts.py-529-                "video_codec": self.video_codec,
astrid/core/rendering/contracts.py-530-                "video_profile": self.video_profile,
astrid/core/rendering/contracts.py-531-                "video_level": self.video_level,
astrid/core/rendering/contracts.py-532-                "pixel_format": self.pixel_format,
astrid/core/rendering/contracts.py-533-                "audio_codec": self.audio_codec,
astrid/core/rendering/contracts.py-534-                "audio_sample_rate": self.audio_sample_rate,
astrid/core/rendering/contracts.py:535:                "audio_channel_layout": self.audio_channel_layout,
astrid/core/rendering/contracts.py-536-                "duration_tolerance": self.duration_tolerance,
astrid/core/rendering/contracts.py-537-            }
astrid/core/rendering/contracts.py-538-        )
astrid/core/rendering/contracts.py-539-
astrid/core/rendering/contracts.py-540-    @classmethod
astrid/core/rendering/contracts.py-541-    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
astrid/core/rendering/contracts.py-542-        data = _require_mapping(payload, "render profile")
astrid/core/rendering/contracts.py-543-        required = {
--
astrid/core/rendering/contracts.py-547-            "time_base",
astrid/core/rendering/contracts.py-548-            "container",
astrid/core/rendering/contracts.py-549-            "video_codec",
astrid/core/rendering/contracts.py-550-            "video_profile",
astrid/core/rendering/contracts.py-551-            "video_level",
astrid/core/rendering/contracts.py-552-            "pixel_format",
astrid/core/rendering/contracts.py-553-            "duration_tolerance",
astrid/core/rendering/contracts.py-554-        }
astrid/core/rendering/contracts.py:555:        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
astrid/core/rendering/contracts.py-556-        _validate_object_keys(data, required=required, allowed=allowed, label="render profile")
astrid/core/rendering/contracts.py-557-        return cls(
astrid/core/rendering/contracts.py-558-            width=data["width"],
astrid/core/rendering/contracts.py-559-            height=data["height"],
astrid/core/rendering/contracts.py-560-            fps_rational=data["fps_rational"],
astrid/core/rendering/contracts.py-561-            time_base=data["time_base"],
astrid/core/rendering/contracts.py-562-            container=data["container"],
astrid/core/rendering/contracts.py-563-            video_codec=data["video_codec"],
astrid/core/rendering/contracts.py-564-            video_profile=data["video_profile"],
astrid/core/rendering/contracts.py-565-            video_level=data["video_level"],
astrid/core/rendering/contracts.py-566-            pixel_format=data["pixel_format"],
astrid/core/rendering/contracts.py-567-            audio_codec=data.get("audio_codec"),
astrid/core/rendering/contracts.py-568-            audio_sample_rate=data.get("audio_sample_rate"),
astrid/core/rendering/contracts.py:569:            audio_channel_layout=data.get("audio_channel_layout"),
astrid/core/rendering/contracts.py-570-            duration_tolerance=data["duration_tolerance"],
astrid/core/rendering/contracts.py-571-        )
astrid/core/rendering/contracts.py-572-
astrid/core/rendering/contracts.py-573-
astrid/core/rendering/contracts.py-574-def _validate_artifact_audio(
astrid/core/rendering/contracts.py-575-    profile: RenderProfile,
astrid/core/rendering/contracts.py-576-    ownership: AudioOwnership | None,
astrid/core/rendering/contracts.py-577-    label: str,
--
astrid/core/rendering/contracts.py-741-            profile=profile,
astrid/core/rendering/contracts.py-742-            sha256=sha256_file(resolved),
astrid/core/rendering/contracts.py-743-            duration_frames=duration_frames,
astrid/core/rendering/contracts.py-744-            audio=audio,
astrid/core/rendering/contracts.py-745-            attachments=dict(attachments or {}),
astrid/core/rendering/contracts.py-746-        )
astrid/core/rendering/contracts.py-747-
astrid/core/rendering/contracts.py-748-
astrid/core/rendering/contracts.py:749:def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
astrid/core/rendering/contracts.py-750-    if value is None and nullable:
astrid/core/rendering/contracts.py-751-        return None
astrid/core/rendering/contracts.py-752-    if isinstance(value, RenderProfile):
astrid/core/rendering/contracts.py-753-        return value
astrid/core/rendering/contracts.py-754-    return RenderProfile.from_dict(_require_mapping(value, label))
astrid/core/rendering/contracts.py-755-
astrid/core/rendering/contracts.py-756-
astrid/core/rendering/contracts.py-757-def _coerce_window(value: Any, label: str, *, nullable: bool) -> FrameWindow | None:
--
astrid/core/rendering/contracts.py-776-    """Backend-neutral request shared by render, support, and plan operations."""
astrid/core/rendering/contracts.py-777-
astrid/core/rendering/contracts.py-778-    schema_version: int
astrid/core/rendering/contracts.py-779-    timeline_path: str
astrid/core/rendering/contracts.py-780-    output_name: str
astrid/core/rendering/contracts.py-781-    assets_registry_path: str | None = None
astrid/core/rendering/contracts.py-782-    window: FrameWindow | None = None
astrid/core/rendering/contracts.py-783-    audio: AudioOwnership | None = None
astrid/core/rendering/contracts.py:784:    profile: RenderProfile | None = None
astrid/core/rendering/contracts.py-785-    backend_config: BackendConfig = field(default_factory=dict)
astrid/core/rendering/contracts.py-786-    metadata: dict[str, str] = field(default_factory=dict)
astrid/core/rendering/contracts.py-787-
astrid/core/rendering/contracts.py-788-    def __post_init__(self) -> None:
astrid/core/rendering/contracts.py-789-        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
astrid/core/rendering/contracts.py-790-            _protocol_failure(
astrid/core/rendering/contracts.py-791-                f"unknown or malformed render request schema_version "
astrid/core/rendering/contracts.py-792-                f"{self.schema_version!r}; expected integer {SCHEMA_VERSION}",
--
astrid/core/rendering/contracts.py-802-        )
astrid/core/rendering/contracts.py-803-        output_name = _require_string(self.output_name, "output_name")
astrid/core/rendering/contracts.py-804-        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
astrid/core/rendering/contracts.py-805-            raise ValueError("output_name must be a portable basename without path separators")
astrid/core/rendering/contracts.py-806-        object.__setattr__(self, "output_name", output_name)
astrid/core/rendering/contracts.py-807-        object.__setattr__(self, "window", _coerce_window(self.window, "window", nullable=True))
astrid/core/rendering/contracts.py-808-        audio = _coerce_audio_ownership(self.audio, "audio", nullable=True)
astrid/core/rendering/contracts.py-809-        profile = _coerce_profile(self.profile, "profile", nullable=True)
astrid/core/rendering/contracts.py:810:        if audio is not None and profile is not None:

exec
/bin/zsh -lc "rg -n \"channel_layout|channels_only|channel count|QuickTime|sowt|stereo\" tests/core/rendering/test_artifacts.py tests/core/rendering -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_artifacts.py:36:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:54:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:318:        ("audio_channel_layout", "mono"),
tests/core/rendering/test_artifacts.py:36:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:54:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:318:        ("audio_channel_layout", "mono"),
tests/core/rendering/test_raw_command_fixture.py:181:    assert profile.audio_channel_layout == "stereo"
tests/core/rendering/test_raw_command_fixture.py:308:    renderer always produces rendered PCM stereo audio."""
tests/core/rendering/test_profile.py:113:    assert profile.audio_channel_layout == "stereo"
tests/core/rendering/test_contracts.py:65:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_contracts.py:374:    profile_payload.pop("audio_channel_layout")

exec
/bin/zsh -lc "sed -n '1,420p' tests/core/rendering/test_artifacts.py && git log --oneline --decorate -8 -- tests/core/rendering/test_artifacts.py astrid/core/rendering/artifacts.py tests/core/rendering/test_raw_command_fixture.py tests/fixtures/renderer_packs/raw_command/backend.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.media import MediaProbe
from astrid.core.rendering import artifacts
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    Attachment,
    AudioOwnership,
    RenderProfile,
    RenderResult,
    VideoArtifact,
)
from astrid.core.rendering.errors import RendererInvalidArtifactError


def _profile(*, audio: bool = False, tolerance: int = 1) -> RenderProfile:
    return RenderProfile(
        width=1280,
        height=720,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        duration_tolerance=tolerance,
    )


def _probe(*, audio: bool = False, duration: tuple[int, int] = (2, 1)) -> MediaProbe:
    return MediaProbe(
        duration_seconds=float(duration[0] / duration[1]),
        fps=24.0,
        resolution="1280x720",
        width=1280,
        height=720,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        video_codec="h264",
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        container="mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        duration_rational=duration,
        video_stream_present=True,
        audio_stream_present=audio,
    )


def _result(
    root: Path,
    *,
    profile: RenderProfile | None = None,
    ownership: AudioOwnership = AudioOwnership.NONE,
    path: str = "outputs/video.mp4",
    contents: bytes = b"video-bytes",
    write: bool = True,
    attachments: dict[str, Attachment] | None = None,
) -> RenderResult:
    output = root / path
    if write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(contents)
    digest = sha256_file(output) if output.is_file() else "0" * 64
    video = VideoArtifact(
        path=path,
        profile=profile or _profile(audio=ownership is AudioOwnership.RENDERED),
        sha256=digest,
        duration_frames=48,
        audio=ownership,
        attachments=attachments or {},
    )
    return RenderResult(
        schema_version=SCHEMA_VERSION,
        video=video,
        audio_ownership=ownership,
    )


def _assert_invalid(callable_: object, *, reason: str | None = None) -> RendererInvalidArtifactError:
    with pytest.raises(RendererInvalidArtifactError) as caught:
        callable_()  # type: ignore[operator]
    error = caught.value.error
    assert error.kind == "invalid_artifact"
    assert error.backend == "astrid.core"
    assert error.recovery_command
    if reason is not None:
        assert error.details["reason"] == reason
    return caught.value


def test_happy_path_preserves_named_attachment_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attachment_path = tmp_path / "outputs" / "alpha.bin"
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_bytes(b"alpha")
    attachment = Attachment(
        name="alpha",
        path="outputs/alpha.bin",
        kind="alpha",
        sha256=sha256_file(attachment_path),
    )
    result = _result(tmp_path, attachments={attachment.name: attachment})
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    validated = validate_render_result(
        result,
        expected_profile=_profile(),
        workspace_root=tmp_path,
    )

    assert validated is result
    assert validated.attachments["alpha"] is attachment


def test_missing_primary_output_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, write=False)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="missing_artifact",
    )


def test_empty_primary_output_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, contents=b"")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="empty_artifact",
    )


@pytest.mark.parametrize("bad_path", ["../video.mp4", "/tmp/video.mp4", "outputs/../video.mp4"])
def test_traversal_and_absolute_output_paths_are_rejected(
    tmp_path: Path, bad_path: str
) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video, "path", bad_path)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="escaped_path",
    )


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video-bytes")
    (workspace / "escape.mp4").symlink_to(outside)
    result = _result(workspace, path="placeholder.mp4")
    object.__setattr__(result.video, "path", "escape.mp4")
    object.__setattr__(result.video, "sha256", sha256_file(outside))

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=workspace
        ),
        reason="escaped_path",
    )


def test_primary_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video, "sha256", "f" * 64)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="hash_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 1920),
        ("height", 1080),
        ("fps_rational", (25, 1)),
        ("time_base", (1, 12800)),
        ("container", "webm"),
        ("video_codec", "hevc"),
        ("pixel_format", "yuv444p"),
    ],
)
def test_probed_video_profile_mismatches_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: replace(_probe(), **{field: value}),
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="profile_mismatch",
    )


def test_declared_profile_mismatch_is_rejected_before_probe(tmp_path: Path) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video.profile, "width", 1920)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="profile_mismatch",
    )


def test_duration_outside_tolerance_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: _probe(duration=(13, 6)),  # 52 frames, declared 48
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        ),
        reason="duration_mismatch",
    )


def test_duration_at_tolerance_boundary_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: _probe(duration=(49, 24)),  # exactly 49 frames
    )

    assert (
        validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        )
        is result
    )


def test_rendered_ownership_without_audio_stream_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile(audio=True)
    result = _result(
        tmp_path,
        profile=profile,
        ownership=AudioOwnership.RENDERED,
    )
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=profile, workspace_root=tmp_path
        ),
        reason="audio_ownership_mismatch",
    )


def test_none_ownership_with_audio_stream_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts, "ffprobe_metadata_strict", lambda _path: _probe(audio=True)
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="audio_ownership_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("audio_codec", "opus"),
        ("audio_sample_rate", 44100),
        ("audio_channel_layout", "mono"),
    ],
)
def test_rendered_audio_profile_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    profile = _profile(audio=True)
    result = _result(tmp_path, profile=profile, ownership=AudioOwnership.RENDERED)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: replace(_probe(audio=True), **{field: value}),
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=profile, workspace_root=tmp_path
        ),
        reason="audio_profile_mismatch",
    )


def test_passthrough_visual_artifact_may_target_canonical_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path, ownership=AudioOwnership.PASSTHROUGH)
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    assert (
        validate_render_result(
            result,
            expected_profile=_profile(audio=True),
            workspace_root=tmp_path,
        )
        is result
    )


def _attachment_result(tmp_path: Path) -> tuple[RenderResult, Attachment]:
    path = tmp_path / "attachments" / "data.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"attachment")
    attachment = Attachment(
        name="data",
        path="attachments/data.bin",
        kind="project",
        sha256=sha256_file(path),
    )
    return _result(tmp_path, attachments={"data": attachment}), attachment


def test_missing_attachment_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    (tmp_path / attachment.path).unlink()

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="missing_artifact",
    )


def test_invalid_attachment_path_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "path", "../data.bin")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="escaped_path",
    )


def test_invalid_attachment_kind_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "kind", "Bad Kind")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="invalid_attachment_kind",
    )


def test_attachment_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "sha256", "a" * 64)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="hash_mismatch",
    )
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3df2b858 (HEAD -> oracle-run) batch2-rework6: oracle re-review5 issues 1-2 (support rejects audio!=rendered regardless of profile presence, layout channel-count whitespace-strip)
3557792f batch2-rework5: oracle re-review4 issues 1-5 (OSError-safe drain + guaranteed direct-child reap, support rejects audio!=rendered, layout channel-count normalization, tight root-only macOS symlink exemption, committed-read guard before resolve)
9db48731 batch2-rework4: oracle re-review3 issues 1-5 (bounded drain communicate + OSError safety, canonical chan atom + honest channels-only probe + channels-vs-layout validation, full profile fail-closed support, unresolved out_path on all publish routes, ancestor-symlink guards w/ macOS system-redirect exemption)
8c195bf0 batch2-rework3: oracle re-review2 issues 1-6 (transport OSError/KeyboardInterrupt-safe cleanup w/ bounded escalation, chan atom inside wave + mono/stereo-only layout inference + strict-validation integration test, support profile fail-closed + support.json codec fix, run.py unresolved out_path in publication context, default-sidecar symlink guard, remove committed pyc + gitignore)
7f7c25d5 batch2-rework2: oracle re-review issues 1-5 (transport SIGKILL escalation + bounded drain, fixture profile accuracy + chan atom + strict support validation, media channel_layout derivation, run.py unresolved out_path, cleanup sidecar symlink guard)
5231a233 batch2-rework: oracle issues 1-6 (missing result -> protocol, transport group-cleanup on any exception + interrupt-safe escalation, fixture SPS crop 1080 + pcm_s16le codec + support request validation, artifact in-workspace symlink rejection, publication unresolved-path symlink guards + invalidate-before-replace ordering)
dedcc2c5 (tag: C2) batch2: command transport, raw-command fixture, asset cache extraction, invocation-scoped asset materialization, profile resolution + artifact validation, locked publication

exec
/bin/zsh -lc "rg -n \"def _require_string|def _text\" astrid/core/rendering/contracts.py astrid/core/rendering/artifacts.py && sed -n '150,230p' astrid/core/rendering/contracts.py && sed -n '225,275p' astrid/core/rendering/artifacts.py && PYTHONDONTWRITEBYTECODE=1 python3 -c 'from astrid.core.rendering.artifacts import _layout_channel_count; print([_layout_channel_count(v) for v in (\" Stereo \", \" stereo \", \"5.1(side)\", None)])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 132ms:
[2, 2, 6, None]

exec
/bin/zsh -lc "sed -n '220,255p' astrid/core/rendering/contracts.py && git diff --no-ext-diff --numstat 3557792f 3df2b858 && shasum -a 256 /tmp/batch2-r6.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    Python versions and dict insertion orders; replay verifies the request
    against this digest.
    """
    return canonical_json_digest(_json_safe_mapping(request, label="render request"))


def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if "\x00" in value:
        raise ValueError(f"{label} must not contain NUL")
    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
        raise ValueError(f"{label} must not be empty")
    return value


def _require_optional_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, label)


def _require_qualified_id(value: Any, label: str) -> str:
    result = _require_string(value, label)
    if not _QUALIFIED_ID_RE.fullmatch(result):
        raise ValueError(
            f"{label} must be a qualified id '<pack>.<name>' whose dot-separated "
            "segments use lowercase letters, digits, and hyphens"
        )
    return result


def _require_sha256(value: Any, label: str) -> str:
    result = _require_string(value, label)
    if not _SHA256_RE.fullmatch(result):
        raise ValueError(f"{label} must be a lowercase 64-character SHA-256 digest")
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
7661	0	.oracle/checkins/batch-2-r5.md
1	1	astrid/core/rendering/artifacts.py
31	0	tests/core/rendering/test_raw_command_fixture.py
17	17	tests/fixtures/renderer_packs/raw_command/backend.py
1f42d97d648c44ed96c90908d9d4b1fd3a8c11d98167868e1ebe862fa9c729de  /tmp/batch2-r6.diff

exec
/bin/zsh -lc "rg -n \"class MediaProbe|audio_channels\" astrid/core/media.py | head -n 60 && sed -n '15,110p' astrid/core/media.py && PYTHONDONTWRITEBYTECODE=1 python3 -c 'import importlib.util; from pathlib import Path; p=Path(\"tests/fixtures/renderer_packs/raw_command/backend.py\"); s=importlib.util.spec_from_file_location(\"raw_backend_review\", p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); out=[]; m._write_json=lambda _p,payload: out.append(payload); rc=m._support({\"audio\":\"none\",\"profile\":None}, Path(\"/unused\")); print(rc, out[0][\"supported\"], out[0][\"features\"], out[0][\"reasons\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1ms:
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'from astrid.core.media import MediaProbe; from astrid.core.rendering.artifacts import _compare_probe_to_profile; from astrid.core.rendering.contracts import RenderProfile; p=RenderProfile(width=1280,height=720,fps_rational=(24,1),time_base=(1,12288),container=\"mp4\",video_codec=\"h264\",pixel_format=\"yuv420p\",audio_codec=\"aac\",audio_sample_rate=48000,audio_channel_layout=\" Stereo \"); q=MediaProbe(width=1280,height=720,fps_rational=(24,1),time_base=(1,12288),container=\"mp4\",video_codec=\"h264\",pixel_format=\"yuv420p\",audio_codec=\"aac\",audio_sample_rate=48000,audio_channel_layout=None,audio_channels=2,video_stream_present=True,audio_stream_present=True); _compare_probe_to_profile(q,p,label=\"review profile\",compare_audio=True); print(\"PASS\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 87ms:
PASS

exec
/bin/zsh -lc 'rg -n "''^## Batch 2|''^### Batch 2|Batch 2|batch 2" .oracle/tasklist.md | head -n 40 && sed -n '"'1,240p' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
5:**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
26:## Batch 2 — Command protocol and host-owned plumbing
# Renderer Tasklist

## Batch 1 — Baseline, contracts, and discovery

**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
- Active trusted installs, corrupt/mismatched installs, inactive revisions, explicit-extra roots, environment denial, conflicts, cycles, and invalid override targets produce the specified inspectable/executable states.
- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.

### Tasks

- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.

## Batch 2 — Command protocol and host-owned plumbing

**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
- Asset-cache layout, URL keys, resume/drift metadata, locking, and `EphemeralSession` behavior remain unchanged behind the compatibility wrapper.
- Only invocation-staged assets are served from `127.0.0.1` on port `0`; Range requests work and the server always shuts down, closes, and joins.
- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.

### Tasks

- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
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

- The attached-child helper requires a validated parent project/run and unique step, scopes and restores all three `ASTRID_TASK_*` variables, preserves caller-selected output, honors facade overrides, and falls back to public `RenderService` only without a project ledger.
- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
- Targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

### Tasks

- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.

## Batch 6 — Python SDK, conformance, and scaffold

**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
- Any SDK/wire mismatch stops the batch and returns to M1 through the oracle; no SDK-only fields or semantics are introduced.
- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
- Scaffold collision, ownership, command-containment, static validation, trusted install, generated test, two-second smoke, and installed-wheel cases pass.

### Tasks

- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.

## Batch 7 — CLI, replay, documentation, and epic freeze

**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.

**Acceptance criteria:**

- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
- `list` and `inspect` perform static metadata parsing and report source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and overrides without importing backend code.
- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
- Each CLI verb has a frozen raw-dictionary `--json` shape; expected errors exit 2, degraded bugs exit 1, and interruption cleans up before normal exit-130 behavior.
- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
- Renderer-author documentation covers raw JSON, Python SDK, non-Python commands, trust, permissions, selection, configuration, assets, output/audio/attachments, diagnostics, replay, and legacy selectors while explicitly deferring async jobs, remote infrastructure, and layer compositing.
- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
- Full pytest, semantic parity, real FFmpeg, explicit optional-Remotion evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

### Tasks

- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.

## Execution notes

- Persist this markdown exactly as `.oracle/tasklist.md` before implementation. It is frozen; any change requires an explicit oracle-reviewed plan revision.
- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
- If the oracle reports issues, rework only the current batch, recommit, and resubmit the cumulative `C(N-1)..HEAD` range until `PASS`. Do not begin the next batch early.
- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.

exec
/bin/zsh -lc "rg -n -C 5 \"audio_channels\\s*=|audio_channel_layout\\s*=\\s*None|channel_layout.*None|channels.*layout\" tests -g '*.py' | head -n 320" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/util/test_media.py-131-        assert probe.time_base is None
tests/core/util/test_media.py-132-        assert probe.video_codec is None
tests/core/util/test_media.py-133-        assert probe.pixel_format is None
tests/core/util/test_media.py-134-        assert probe.audio_codec is None
tests/core/util/test_media.py-135-        assert probe.audio_sample_rate is None
tests/core/util/test_media.py:136:        assert probe.audio_channel_layout is None
tests/core/util/test_media.py-137-        assert probe.has_video_stream is False
tests/core/util/test_media.py-138-        assert probe.has_audio_stream is False
tests/core/util/test_media.py-139-
tests/core/util/test_media.py-140-    def test_partial_construction(self) -> None:
tests/core/util/test_media.py-141-        probe = MediaProbe(
--
tests/core/util/test_media.py-182-        assert probe.duration_rational == (25, 2)
tests/core/util/test_media.py-183-        assert probe.has_video_stream is True
tests/core/util/test_media.py-184-        assert probe.has_audio_stream is True
tests/core/util/test_media.py-185-        assert probe._raw  # raw JSON preserved
tests/core/util/test_media.py-186-
tests/core/util/test_media.py:187:    def test_channels_reported_without_inferred_layout(self) -> None:
tests/core/util/test_media.py-188-        """Probes that report channel COUNT without channel_layout (e.g.
tests/core/util/test_media.py-189-        QuickTime sowt) must stay honest: layout stays None, channels is
tests/core/util/test_media.py-190-        reported, and validation compares counts (never guessed layouts)."""
tests/core/util/test_media.py-191-        import json as _json
tests/core/util/test_media.py-192-
--
tests/core/util/test_media.py-200-            return_value=subprocess.CompletedProcess(
tests/core/util/test_media.py-201-                [], 0, stdout=_json.dumps(payload), stderr=""
tests/core/util/test_media.py-202-            ),
tests/core/util/test_media.py-203-        ):
tests/core/util/test_media.py-204-            probe = ffprobe_metadata("video.mp4")
tests/core/util/test_media.py:205:        assert probe.audio_channel_layout is None
tests/core/util/test_media.py:206:        assert probe.audio_channels == 2
tests/core/util/test_media.py-207-
tests/core/util/test_media.py-208-    def test_accepts_path_object(self, tmp_path: Path) -> None:
tests/core/util/test_media.py-209-        vid = tmp_path / "clip.mp4"
tests/core/util/test_media.py-210-        vid.write_bytes(b"dummy")
tests/core/util/test_media.py-211-        with patch("subprocess.run") as mock_run, patch(
--
tests/core/rendering/test_artifacts.py-31-        video_profile=None,
tests/core/rendering/test_artifacts.py-32-        video_level=None,
tests/core/rendering/test_artifacts.py-33-        pixel_format="yuv420p",
tests/core/rendering/test_artifacts.py-34-        audio_codec="aac" if audio else None,
tests/core/rendering/test_artifacts.py-35-        audio_sample_rate=48000 if audio else None,
tests/core/rendering/test_artifacts.py:36:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py-37-        duration_tolerance=tolerance,
tests/core/rendering/test_artifacts.py-38-    )
tests/core/rendering/test_artifacts.py-39-
tests/core/rendering/test_artifacts.py-40-
tests/core/rendering/test_artifacts.py-41-def _probe(*, audio: bool = False, duration: tuple[int, int] = (2, 1)) -> MediaProbe:
--
tests/core/rendering/test_artifacts.py-49-        time_base=(1, 12288),
tests/core/rendering/test_artifacts.py-50-        video_codec="h264",
tests/core/rendering/test_artifacts.py-51-        pixel_format="yuv420p",
tests/core/rendering/test_artifacts.py-52-        audio_codec="aac" if audio else None,
tests/core/rendering/test_artifacts.py-53-        audio_sample_rate=48000 if audio else None,
tests/core/rendering/test_artifacts.py:54:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py-55-        container="mp4",
tests/core/rendering/test_artifacts.py-56-        format_name="mov,mp4,m4a,3gp,3g2,mj2",
tests/core/rendering/test_artifacts.py-57-        duration_rational=duration,
tests/core/rendering/test_artifacts.py-58-        video_stream_present=True,
tests/core/rendering/test_artifacts.py-59-        audio_stream_present=audio,
--
tests/core/rendering/test_contracts.py-60-        video_profile="high",
tests/core/rendering/test_contracts.py-61-        video_level="4.1",
tests/core/rendering/test_contracts.py-62-        pixel_format="yuv420p",
tests/core/rendering/test_contracts.py-63-        audio_codec="aac" if audio else None,
tests/core/rendering/test_contracts.py-64-        audio_sample_rate=48000 if audio else None,
tests/core/rendering/test_contracts.py:65:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_contracts.py-66-        duration_tolerance=1,
tests/core/rendering/test_contracts.py-67-    )
tests/core/rendering/test_contracts.py-68-
tests/core/rendering/test_contracts.py-69-
tests/core/rendering/test_contracts.py-70-def _window(

exec
/bin/zsh -lc 'git show --format=fuller --no-patch 3df2b858 && git diff --no-ext-diff --quiet 3df2b858 -- astrid/core/rendering/artifacts.py tests/core/rendering/test_raw_command_fixture.py tests/fixtures/renderer_packs/raw_command/backend.py; status=$?; echo tracked_diff_status=$status; git status --porcelain=v1 --untracked-files=all' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 3df2b858bae0ee6ede9e001745df63c4adbaa56a
Author:     POM <peter@omalley.io>
AuthorDate: Wed Aug 12 09:34:47 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Wed Aug 12 09:34:47 2026 +0200

    batch2-rework6: oracle re-review5 issues 1-2 (support rejects audio!=rendered regardless of profile presence, layout channel-count whitespace-strip)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
zsh:1: read-only variable: status

exec
/bin/zsh -lc 'git diff --no-ext-diff --quiet 3df2b858 -- astrid/core/rendering/artifacts.py tests/core/rendering/test_raw_command_fixture.py tests/fixtures/renderer_packs/raw_command/backend.py; diff_rc=$?; echo tracked_diff_rc=$diff_rc; git status --porcelain=v1 --untracked-files=all' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
tracked_diff_rc=0
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-2-r6.md

exec
/bin/zsh -lc "git diff --no-ext-diff --no-renames --unified=0 3557792f 3df2b858 -- astrid/core/rendering/artifacts.py tests/core/rendering/test_raw_command_fixture.py tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '1,240p'; rg -n \"support.*audio|profile.*support|audio_mode\" tests/core/rendering/test_raw_command_fixture.py tests/core/rendering/test_transport.py | head -n 180" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/artifacts.py b/astrid/core/rendering/artifacts.py
index 736bd7a5..e4a11bdd 100644
--- a/astrid/core/rendering/artifacts.py
+++ b/astrid/core/rendering/artifacts.py
@@ -483 +483 @@ def _layout_channel_count(layout: str | None) -> int | None:
-    }.get((layout or "").lower())
+    }.get((layout or "").strip().lower())
diff --git a/tests/core/rendering/test_raw_command_fixture.py b/tests/core/rendering/test_raw_command_fixture.py
index 7e44fd39..e1cd02c0 100644
--- a/tests/core/rendering/test_raw_command_fixture.py
+++ b/tests/core/rendering/test_raw_command_fixture.py
@@ -305,0 +306,31 @@ def test_render_verb_via_command_transport(tmp_path: Path) -> None:
+def test_support_rejects_audio_none_even_with_null_profile(tmp_path: Path) -> None:
+    """A request for audio='none' with profile=null is unsupported: the
+    renderer always produces rendered PCM stereo audio."""
+    workspace = tmp_path / "workspace"
+    workspace.mkdir(parents=True, exist_ok=True)
+    request_path = workspace / "request.json"
+    request_path.write_text(
+        json.dumps(
+            {
+                "schema_version": 1,
+                "output_name": "raw_command.mp4",
+                "audio": "none",
+                "profile": None,
+            }
+        ),
+        encoding="utf-8",
+    )
+    result_path = workspace / "result.json"
+    transport = CommandTransport(BACKEND_ID, termination_grace=0.15)
+    report = transport.run(
+        "support",
+        [sys.executable, "backend.py"],
+        request_path=request_path,
+        result_path=result_path,
+        cwd=PACK_ROOT,
+        timeout=30,
+    )
+    assert report.supported is False
+    assert report.features == {"media": False, "audio_mode": "none"}
+
+
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 04dc16b1..f628ad48 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -472,17 +472,17 @@ def _support(request: dict, result_path: Path) -> int:
-        if mismatches:
-            _write_json(
-                result_path,
-                {
-                    "schema_version": 1,
-                    "supported": False,
-                    "reasons": [
-                        "profile not produced by " + BACKEND_ID + ": "
-                        + "; ".join(mismatches)
-                    ],
-                    "features": {"media": False, "audio_mode": "none"},
-                    "alternatives": [],
-                    "backend": BACKEND_ID,
-                    "backend_version": "1.0.0",
-                },
-            )
-            return 0
+    if mismatches:
+        _write_json(
+            result_path,
+            {
+                "schema_version": 1,
+                "supported": False,
+                "reasons": [
+                    "profile not produced by " + BACKEND_ID + ": "
+                    + "; ".join(mismatches)
+                ],
+                "features": {"media": False, "audio_mode": "none"},
+                "alternatives": [],
+                "backend": BACKEND_ID,
+                "backend_version": "1.0.0",
+            },
+        )
+        return 0
tests/core/rendering/test_raw_command_fixture.py:237:            "audio_mode": "rendered",
tests/core/rendering/test_raw_command_fixture.py:306:def test_support_rejects_audio_none_even_with_null_profile(tmp_path: Path) -> None:
tests/core/rendering/test_raw_command_fixture.py:307:    """A request for audio='none' with profile=null is unsupported: the
tests/core/rendering/test_raw_command_fixture.py:334:    assert report.features == {"media": False, "audio_mode": "none"}
tests/core/rendering/test_raw_command_fixture.py:345:    assert report.features == {"media": True, "audio_mode": "rendered"}

2026-08-12T07:38:32.596863Z ERROR codex_core::tools::router: error=timeout_ms must be at least 10000
collab: Wait
codex
PASS
tokens used
158,268
PASS
