Reading additional input from stdin...
2026-08-12T02:20:30.459984Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:20:30.460019Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:20:30.460026Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3c5-6ecc-7423-bec6-147c796da278
--------
user
# Megado Checkpoint — Batch 1 eighth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3),
-r6 (3), -r7 (3). Eighth rework committed as `8418bae` (prior head ab486f9).
Incremental diff at /tmp/batch1-r8.diff.

## How each of your 3 re-review7 issues was addressed (host-implemented)

1. **Per-segment lineage unbound, cardinality bypassable** →
   - Sequence form now preserves ORDER (returns a path-keyed list, not an
     unordered map) and REJECTS duplicate paths.
   - Mapping form requires path keys == VideoArtifact.path.
2. **Provenance bypasses artifact/attachment contracts** →
   - Artifact keys validated as workspace-relative paths (traversal/absolute
     rejected).
   - Top-level Attachment values reconstructed through `Attachment.from_dict`
     (mutation via object.__setattr__ cannot inject invalid fields).
   - RenderProfile values reconstructed through `RenderProfile.from_dict`.
   - Attachment names must be unique ACROSS all segment artifacts.
   - Adversarial tests: dup path (sequence), dup attachment across artifacts,
     escaped artifact key, key/name mismatch.
3. **Schema/DTO parity at terminal LF** →
   - All fully-anchored schema patterns now end `\Z` (Python re) instead of
     `$`, rejecting trailing newlines exactly like DTO fullmatch/full-regex
     (qualified IDs, sha256, portable names, kinds, plan reason indices).
   - workspacePath rejects whitespace-only path components (DTO aligned with
     schema for `"dir/\n"`).
   - Trailing-LF adversaries for digest and reason keys added.

## Evidence

- Incremental diff: /tmp/batch1-r8.diff (14 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.
- Docs updated.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 8 review rounds. The
contract is heavily validated; remaining items should be convergence-level.
If the contract is sound and STABLE, say exactly `PASS` so Batch 2 may begin.
If blocking issues remain, name them precisely with minimum rework.
codex
I’m using the `megado` checkpoint guidance and the repository’s context-minimization/subagent workflow. I’ll inspect the incremental diff and affected contracts read-only, then run focused adversarial checks before returning only `PASS` or precise blockers.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '241,520p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '261,520p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The Astrid repository skill also applies here; I’m loading its review rules before touching the checkpoint evidence. The context workflow calls for independent bounded reviews, so I’m also loading its subagent-launcher instructions before dispatching them.
exec
/bin/zsh -lc "sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '261,560p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,300p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '301,680p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc 'wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
    1013 total

exec
/bin/zsh -lc "sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc "sed -n '261,520p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc "sed -n '521,772p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc "sed -n '1,241p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
I’m splitting the re-review into three independent lenses: lineage/provenance, schema↔DTO parity, and regression/contract completeness. Each reviewer is read-only and must report only a concrete blocker or `PASS`; I’ll reconcile their findings against the code myself.
2026-08-12T02:21:26.213332Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:26.213363Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:26.213370Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:31.957159Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:31.957241Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:31.957267Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:37.022757Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:37.023500Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:21:37.023527Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "rg --files .oracle/checkins .oracle | sort | sed -n '1,160p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/baseline.md
.oracle/briefs/01-pack-discovery-trust.md
.oracle/briefs/02-schema-registry.md
.oracle/briefs/03-run-ownership-facade.md
.oracle/briefs/04-provenance-consumers.md
.oracle/briefs/05-hybrid-planner-canvas.md
.oracle/briefs/06-ffmpeg-media-audio.md
.oracle/briefs/07-serving-remotion-lifecycle.md
.oracle/briefs/08-callsites.md
.oracle/briefs/09-parity-fixtures-tests-ci.md
.oracle/briefs/10-sdk-cli-conventions.md
.oracle/briefs/11-errors-asset-cache-output.md
.oracle/briefs/12-pack-schema-permissions.md
.oracle/briefs/13-single-ledger-facade.md
.oracle/briefs/14-dynamic-outputs.md
.oracle/briefs/15-audio-semantics.md
.oracle/briefs/16-registry-lock.md
.oracle/briefs/batch-1-r1-t1.1.md
.oracle/briefs/batch-1-r1-t1.2.md
.oracle/briefs/batch-1-r1-t1.3.md
.oracle/briefs/batch-1-r1-t1.4.md
.oracle/briefs/batch-1-r2-t1.1.md
.oracle/briefs/batch-1-r2-t1.2.md
.oracle/briefs/batch-1-t1.1.md
.oracle/briefs/batch-1-t1.2.md
.oracle/briefs/batch-1-t1.3.md
.oracle/briefs/batch-1-t1.4.md
.oracle/briefs/batch-1-t1.5.md
.oracle/checkins/batch-1-r1.md
.oracle/checkins/batch-1-r1.md
.oracle/checkins/batch-1-r2.md
.oracle/checkins/batch-1-r2.md
.oracle/checkins/batch-1-r3.md
.oracle/checkins/batch-1-r3.md
.oracle/checkins/batch-1-r4.md
.oracle/checkins/batch-1-r4.md
.oracle/checkins/batch-1-r5.md
.oracle/checkins/batch-1-r5.md
.oracle/checkins/batch-1-r6.md
.oracle/checkins/batch-1-r6.md
.oracle/checkins/batch-1-r7.md
.oracle/checkins/batch-1-r7.md
.oracle/checkins/batch-1-r8.md
.oracle/checkins/batch-1-r8.md
.oracle/checkins/batch-1.md
.oracle/checkins/batch-1.md
.oracle/findings/01-pack-discovery-trust.meta.json
.oracle/findings/01-pack-discovery-trust.txt
.oracle/findings/02-schema-registry.meta.json
.oracle/findings/02-schema-registry.txt
.oracle/findings/03-run-ownership-facade.meta.json
.oracle/findings/03-run-ownership-facade.txt
.oracle/findings/04-provenance-consumers.meta.json
.oracle/findings/04-provenance-consumers.txt
.oracle/findings/05-hybrid-planner-canvas.meta.json
.oracle/findings/05-hybrid-planner-canvas.txt
.oracle/findings/06-ffmpeg-media-audio.meta.json
.oracle/findings/06-ffmpeg-media-audio.txt
.oracle/findings/07-serving-remotion-lifecycle.meta.json
.oracle/findings/07-serving-remotion-lifecycle.txt
.oracle/findings/08-callsites.meta.json
.oracle/findings/08-callsites.txt
.oracle/findings/09-parity-fixtures-tests-ci.meta.json
.oracle/findings/09-parity-fixtures-tests-ci.txt
.oracle/findings/10-sdk-cli-conventions.meta.json
.oracle/findings/10-sdk-cli-conventions.txt
.oracle/findings/11-errors-asset-cache-output.meta.json
.oracle/findings/11-errors-asset-cache-output.txt
.oracle/findings/12-pack-schema-permissions.meta.json
.oracle/findings/12-pack-schema-permissions.txt
.oracle/findings/13-single-ledger-facade.meta.json
.oracle/findings/13-single-ledger-facade.txt
.oracle/findings/14-dynamic-outputs.meta.json
.oracle/findings/14-dynamic-outputs.txt
.oracle/findings/15-audio-semantics.meta.json
.oracle/findings/15-audio-semantics.txt
.oracle/findings/16-registry-lock.meta.json
.oracle/findings/16-registry-lock.txt
.oracle/findings/_report.json
.oracle/plan-v1.txt
.oracle/plan.md
.oracle/tasklist.md

exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show -s --format='%H%n%P%n%s' 8418bae" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'wc -l -c /tmp/batch1-r8.diff && git diff --stat ab486f9..8418bae && git diff --name-status ab486f9..8418bae' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r8.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8418baeb18a909e2d0802cb177ce6a283d837f76
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8418baeb18a909e2d0802cb177ce6a283d837f76
ab486f9d5292bc6d2b60d523fbc55075a906d8ed
batch1-rework8: oracle re-review7 issues 1-3 (ordered path-keyed lineage w/ dup-path + cross-artifact attachment uniqueness, DTO reconstruction for attachments/profiles, trailing-LF schema anchors)

 succeeded in 0ms:
   11153  662844 /tmp/batch1-r8.diff
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r7.md                     | 9876 ++++++++++++++++++++
 astrid/core/rendering/contracts.py                 |    2 +
 astrid/core/rendering/provenance.py                |   51 +-
 astrid/core/rendering/schemas/v1/finalize.json     |   56 +-
 .../rendering/schemas/v1/finalizer-manifest.json   |   22 +-
 astrid/core/rendering/schemas/v1/plan.json         |   42 +-
 .../rendering/schemas/v1/planner-manifest.json     |   22 +-
 .../rendering/schemas/v1/renderer-manifest.json    |   26 +-
 astrid/core/rendering/schemas/v1/request.json      |   32 +-
 astrid/core/rendering/schemas/v1/result.json       |   40 +-
 astrid/core/rendering/schemas/v1/support.json      |    8 +-
 docs/contracts/render-backend-v1.md                |   23 +-
 tests/core/rendering/test_contracts.py             |   40 +
 tests/core/rendering/test_schema_roundtrip.py      |    2 +
 14 files changed, 10099 insertions(+), 143 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-1-r7.md
M	astrid/core/rendering/contracts.py
M	astrid/core/rendering/provenance.py
M	astrid/core/rendering/schemas/v1/finalize.json
M	astrid/core/rendering/schemas/v1/finalizer-manifest.json
M	astrid/core/rendering/schemas/v1/plan.json
M	astrid/core/rendering/schemas/v1/planner-manifest.json
M	astrid/core/rendering/schemas/v1/renderer-manifest.json
M	astrid/core/rendering/schemas/v1/request.json
M	astrid/core/rendering/schemas/v1/result.json
M	astrid/core/rendering/schemas/v1/support.json
M	docs/contracts/render-backend-v1.md
M	tests/core/rendering/test_contracts.py
M	tests/core/rendering/test_schema_roundtrip.py

exec
/bin/zsh -lc 'git diff --unified=100 ab486f9..8418bae -- astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n \"Batch 1|T1\\.|acceptance|render\" .oracle/tasklist.md | sed -n '1,220p'; sed -n '1,260p' .oracle/checkins/batch-1-r7.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/contracts.py b/astrid/core/rendering/contracts.py
index 3708541..62166f6 100644
--- a/astrid/core/rendering/contracts.py
+++ b/astrid/core/rendering/contracts.py
@@ -227,200 +227,202 @@ def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str
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
     return result
 
 
 def _require_override(value: Any, *, capability_id: str, label: str) -> dict[str, Any]:
     """Validate an override record: ``{from, to}`` with ``to`` equal to the
     resolution id (the override is what selected this implementation)."""
     mapping = _json_safe_mapping(value, label=label)
     required = {"from", "to"}
     if set(mapping) != required:
         raise ValueError(f"{label} must contain exactly 'from' and 'to'")
     _require_qualified_id(mapping["from"], f"{label} 'from'")
     resolved = _require_qualified_id(mapping["to"], f"{label} 'to'")
     if resolved != capability_id:
         raise ValueError(f"{label} 'to' must equal the resolved capability id {capability_id!r}")
     return mapping
 
 
 def _require_string_list(value: Any, label: str) -> list[str]:
     if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
         raise TypeError(f"{label} must be an array of strings")
     return [_require_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
 
 
 def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
     mapping = _require_mapping(value, label)
     return {
         _require_string(key, f"{label} key"): _require_string(item, f"{label}[{key!r}]")
         for key, item in mapping.items()
     }
 
 
 def _require_hash_mapping(value: Any, label: str) -> dict[str, str]:
     mapping = _require_mapping(value, label)
     return {
         _require_string(key, f"{label} key"): _require_sha256(item, f"{label}[{key!r}]")
         for key, item in mapping.items()
     }
 
 
 def _require_schema_version(value: Any, label: str) -> int:
     if type(value) is not int or value != SCHEMA_VERSION:
         _protocol_failure(
             f"unknown or malformed {label} schema_version {value!r}; "
             f"expected integer {SCHEMA_VERSION}",
             details={"received": value, "supported": [SCHEMA_VERSION]},
         )
     return value
 
 
 def _require_rational(value: Any, label: str) -> tuple[int, int]:
     if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
         raise TypeError(f"{label} must be a two-item [numerator, denominator] array")
     numerator = _require_int(value[0], f"{label}[0]", minimum=1)
     denominator = _require_int(value[1], f"{label}[1]", minimum=1)
     return numerator, denominator
 
 
 def _require_frame_range(value: Any, label: str) -> tuple[int, int]:
     if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
         raise TypeError(f"{label} must be a two-item [start_frame, end_frame] array")
     start = _require_int(value[0], f"{label}[0]", minimum=0)
     end = _require_int(value[1], f"{label}[1]", minimum=1)
     if end <= start:
         raise ValueError(f"{label} must be half-open with end_frame > start_frame")
     return start, end
 
 
 def _require_workspace_relative_path(value: Any, label: str) -> str:
     raw = _require_string(value, label)
     if "\\" in raw:
         raise ValueError(f"{label} must be a normalized workspace path using forward slashes")
     normalized = raw.replace("\\", "/")
     if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
         raise ValueError(f"{label} must be relative to the invocation workspace")
     if normalized.startswith("//"):
         raise ValueError(f"{label} must not be a UNC path")
     raw_parts = normalized.split("/")
     parts = PurePosixPath(normalized).parts
     if not parts or any(part in {"", ".", ".."} for part in raw_parts):
         raise ValueError(f"{label} must be a normalized contained workspace path")
+    if any(not part.strip() for part in raw_parts):
+        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
     return raw
 
 
 def _relative_file_path(path: str | Path, workspace_root: str | Path, label: str) -> tuple[str, Path]:
     root = Path(workspace_root).resolve()
     candidate = Path(path)
     if not candidate.is_absolute():
         candidate = root / candidate
     resolved = candidate.resolve(strict=True)
     try:
         relative = resolved.relative_to(root)
     except ValueError as exc:
         raise ValueError(f"{label} escapes invocation workspace {root}") from exc
     return relative.as_posix(), resolved
 
 
 def _protocol_failure(message: str, *, details: Mapping[str, Any] | None = None) -> NoReturn:
     from .errors import raise_protocol_error
 
     raise_protocol_error(
         backend="astrid.core",
         message=message,
         details=dict(details or {}),
     )
 
 
 class AudioOwnership(str, Enum):
     """Who is responsible for audio in a returned primary video."""
 
     RENDERED = "rendered"
     PASSTHROUGH = "passthrough"
     NONE = "none"
 
 
 def _coerce_audio_ownership(value: Any, label: str, *, nullable: bool) -> AudioOwnership | None:
     if value is None and nullable:
         return None
     if isinstance(value, AudioOwnership):
         return value
     if isinstance(value, str):
         try:
             return AudioOwnership(value)
         except ValueError as exc:
             raise ValueError(
                 f"{label} must be one of: {', '.join(item.value for item in AudioOwnership)}"
             ) from exc
     raise TypeError(f"{label} must be an audio ownership string")
 
 
 @dataclass(frozen=True)
 class FrameWindow:
     """A half-open integer frame window ``[start_frame, end_frame)``."""
 
     start_frame: int
     end_frame: int
     fps_rational: tuple[int, int]
     source_range: tuple[int, int] | None = None
     speed: float | None = None
 
     def __post_init__(self) -> None:
         start = _require_int(self.start_frame, "start_frame", minimum=0)
         end = _require_int(self.end_frame, "end_frame", minimum=1)
         if end <= start:
             raise ValueError("end_frame must be greater than start_frame")
         object.__setattr__(self, "start_frame", start)
         object.__setattr__(self, "end_frame", end)
         object.__setattr__(self, "fps_rational", _require_rational(self.fps_rational, "fps_rational"))
         if self.source_range is not None:
             object.__setattr__(
                 self,
                 "source_range",
                 _require_frame_range(self.source_range, "source_range"),
             )
         if self.speed is not None:
             object.__setattr__(
                 self,
                 "speed",
                 _require_number(self.speed, "speed", exclusive_minimum=0),
             )
 
     @property
     def duration_frames(self) -> int:
         return self.end_frame - self.start_frame
 
     def to_dict(self) -> dict[str, Any]:
         return _json_safe_mapping(
             {
                 "start_frame": self.start_frame,
                 "end_frame": self.end_frame,
                 "fps_rational": self.fps_rational,
                 "source_range": self.source_range,
                 "speed": self.speed,
             }
         )
 
     @classmethod
     def from_dict(cls, payload: Mapping[str, Any]) -> FrameWindow:
         data = _require_mapping(payload, "frame window")
         _validate_object_keys(
             data,
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 6881c6a..e8c06a4 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -1,298 +1,331 @@
 """Core-owned provenance v2 assembly for timeline renders."""
 
 from __future__ import annotations
 
 from collections.abc import Mapping, Sequence
 from pathlib import Path
 from typing import Any
 
 from astrid.core.foundation.atomic_io import write_json_atomic
 from astrid.core.foundation.hash import sha256_file
 
 from .contracts import (
     PROVENANCE_V1_ALWAYS_KEYS,
     PROVENANCE_V1_COMPATIBILITY_KEYS,
     PROVENANCE_V2_CORE_KEYS,
     Attachment,
     AudioOwnership,
     RenderPlan,
     RenderProfile,
     RenderSegment,
     VideoArtifact,
     _json_safe_mapping,
     _require_sha256,
     _require_string,
+    _require_workspace_relative_path,
     _validate_backend_fragments,
 )
 
 
 PROVENANCE_SCHEMA_VERSION = 2
 CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)
 
 
 def validate_backend_fragments(
     fragments: Mapping[str, Mapping[str, Any]] | None,
 ) -> dict[str, dict[str, Any]]:
     """Validate namespaces and reject top-level core-key collisions."""
 
     return _validate_backend_fragments(fragments or {})
 
 
 def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
     if value is None:
         return None
     if isinstance(value, AudioOwnership):
         return value.value
     try:
         return AudioOwnership(value).value
     except (TypeError, ValueError) as exc:
         raise ValueError(
             "audio_ownership must be rendered, passthrough, none, or null"
         ) from exc
 
 
 def _normalize_attachments(
     attachments: Mapping[str, Attachment | Mapping[str, Any]] | None,
 ) -> dict[str, Any]:
     result: dict[str, Any] = {}
     for raw_name, raw_attachment in (attachments or {}).items():
         name = _require_string(raw_name, "attachment key")
         attachment = (
-            raw_attachment
+            Attachment.from_dict(
+                {
+                    "name": raw_attachment.name,
+                    "path": raw_attachment.path,
+                    "kind": raw_attachment.kind,
+                    "sha256": raw_attachment.sha256,
+                }
+            )
             if isinstance(raw_attachment, Attachment)
             else Attachment.from_dict(raw_attachment)
         )
         if attachment.name != name:
             raise ValueError(
                 f"attachment key {name!r} must match attachment.name {attachment.name!r}"
             )
         if name in result:
             raise ValueError(f"duplicate attachment name: {name}")
         result[name] = attachment.to_dict()
     return result
 
 
 def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
     """Derive one v1 segment projection from an authoritative v2 segment."""
 
     numerator, denominator = segment.window.fps_rational
     return {
         "engine": segment.renderer.id.rsplit(".", 1)[-1],
         "from": segment.window.start_frame * denominator / numerator,
         "to": segment.window.end_frame * denominator / numerator,
     }
 
 
+def _reject_duplicate_attachment_names(
+    lineage: Mapping[str, Any],
+    seen: set[str],
+) -> None:
+    """Reject attachment names repeated across segment artifacts."""
+    for name in (lineage.get("attachments") or {}):
+        if name in seen:
+            raise ValueError(
+                f"duplicate attachment name {name!r} across segment artifacts"
+            )
+        seen.add(name)
+
+
 def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
     if value is None:
         value = {}
     if isinstance(value, Mapping):
         result: dict[str, Any] = {}
+        seen_attachment_names: set[str] = set()
         for key, profile in value.items():
             path = _require_string(str(key), "artifact key")
+            path = _require_workspace_relative_path(path, "artifact key")
             if isinstance(profile, VideoArtifact):
                 if path != profile.path:
                     raise ValueError(
                         f"artifact_profiles key {path!r} must equal VideoArtifact.path "
                         f"{profile.path!r}"
                     )
-                result[path] = _artifact_lineage(profile)
+                lineage = _artifact_lineage(profile)
             elif isinstance(profile, Mapping):
-                result[path] = _artifact_lineage_from_mapping(profile, key=path)
+                lineage = _artifact_lineage_from_mapping(profile, key=path)
             else:
                 raise TypeError(
                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                     "hashed lineage record {profile, sha256, attachments}; "
                     "profile-only entries carry no output hash"
                 )
+            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
+            result[path] = lineage
         # A positive plan must record exactly one hashed artifact per segment.
         if segments:
             if len(result) != len(segments):
                 raise ValueError(
                     f"artifact_profiles must record exactly one hashed lineage entry "
                     f"per segment: expected {len(segments)}, got {len(result)}"
                 )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
-        lineage: dict[str, Any] = {}
+        lineage: list[dict[str, Any]] = []
+        seen_paths: set[str] = set()
+        seen_attachment_names: set[str] = set()
         for profile in value:
             if not isinstance(profile, VideoArtifact):
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
                     "so lineage records stay path-keyed"
                 )
-            lineage[profile.path] = _artifact_lineage(profile)
+            if profile.path in seen_paths:
+                raise ValueError(
+                    f"artifact_profiles sequence contains duplicate path "
+                    f"{profile.path!r}"
+                )
+            seen_paths.add(profile.path)
+            record = _artifact_lineage(profile)
+            _reject_duplicate_attachment_names(record, seen_attachment_names)
+            lineage.append(record)
         if segments:
             if len(lineage) != len(segments):
                 raise ValueError(
                     f"artifact_profiles must record exactly one hashed lineage entry "
                     f"per segment: expected {len(segments)}, got {len(lineage)}"
                 )
         return lineage
     raise TypeError("artifact_profiles must be an object or array")
 
 
 def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
     raw_keys = set(raw)
     allowed = {"profile", "sha256", "attachments"}
     unknown = sorted(raw_keys - allowed)
     if unknown:
         raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
     missing = sorted(allowed - raw_keys)
     if missing:
         raise ValueError(
             f"artifact lineage is missing required fields: {', '.join(missing)}"
         )
     if raw["sha256"] is None:
         raise ValueError("artifact lineage sha256 is required and must not be null")
     if not isinstance(raw["sha256"], str):
         raise TypeError("artifact lineage sha256 must be a string")
     profile = raw["profile"]
     attachments: dict[str, Any] = {}
     raw_attachments = raw["attachments"]
     if raw_attachments is None:
         raise ValueError("artifact lineage attachments must be an object (may be empty)")
     if not isinstance(raw_attachments, Mapping):
         raise TypeError("artifact lineage attachments must be an object")
     for name, att in raw_attachments.items():
         name = _require_string(name, "attachment name")
         if isinstance(att, Attachment):
             if att.name != name:
                 raise ValueError(
                     f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
                 )
             att = {
                 "path": att.path,
                 "kind": att.kind,
                 "sha256": att.sha256,
             }
         att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
         if att_unknown:
             raise ValueError(
                 f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
             )
         att_missing = sorted({"path", "kind", "sha256"} - set(att))
         if att_missing:
             raise ValueError(
                 f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
             )
         if not isinstance(att["sha256"], str):
             raise TypeError(f"attachment {name!r} sha256 must be a string")
         # Validate through the Attachment DTO so workspace-path containment and
         # kind grammar are enforced uniformly for raw and dataclass values.
         validated = Attachment(
             name=name,
             path=att["path"],
             kind=att["kind"],
             sha256=att["sha256"],
         )
         attachments[name] = {
             "path": validated.path,
             "kind": validated.kind,
             "sha256": validated.sha256,
         }
     return {
-        "profile": (
-            profile
-            if isinstance(profile, RenderProfile)
-            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
+        "profile": RenderProfile.from_dict(
+            _json_safe_mapping(profile, label="artifact profile")
         ).to_dict(),
         "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
         "attachments": attachments,
     }
 
 
 def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
     """One hashed artifact lineage record: profile, sha256, attachments."""
     return _artifact_lineage_from_mapping(
         {
             "profile": artifact.profile,
             "sha256": artifact.sha256,
             "attachments": artifact.attachments,
         },
         key=artifact.path,
     )
 
 
 def _normalize_v1_compatibility(
     fields: Mapping[str, Any] | None,
 ) -> dict[str, Any]:
     if fields is None:
         raise ValueError(
             "v1_compatibility is required and must preserve all always-emitted v1 fields"
         )
     compatibility = _json_safe_mapping(fields, label="v1_compatibility")
     unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
     if unknown:
         raise ValueError(
             "v1 compatibility projection contains non-v1 or core-owned keys: "
             + ", ".join(unknown)
         )
     missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
     if missing:
         raise ValueError(
             "v1 compatibility projection is missing always-emitted fields: "
             + ", ".join(missing)
         )
     return compatibility
 
 
 def assemble_provenance_v2(
     *,
     engine: str,
     output: str | Path,
     timeline: str | Path,
     assets_registry: str | Path | None,
     plan: RenderPlan | Mapping[str, Any],
     artifact_profiles: Any = None,
     audio_ownership: AudioOwnership | str | None = None,
     normalization: Sequence[str] = (),
     attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
     backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
     v1_compatibility: Mapping[str, Any] | None = None,
 ) -> dict[str, Any]:
     """Assemble additive provenance v2 with protected ownership boundaries.
 
     ``engine`` is intentionally the legacy request projection. Routing and
     replay lineage come exclusively from the validated ``RenderPlan`` so a
     hybrid invocation cannot collapse multiple renderer identities. Optional
     v1 fields are accepted only through ``v1_compatibility`` and cannot replace
     any v2 core field.
     """
 
     legacy_engine = _require_string(engine, "engine")
     output_path = _require_string(str(output), "output")
     timeline_path = _require_string(str(timeline), "timeline")
     assets_path = None if assets_registry is None else _require_string(
         str(assets_registry), "assets_registry"
     )
     normalized_plan = (
         plan
         if isinstance(plan, RenderPlan)
         else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
     )
     normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
     legacy_segments = [
         _legacy_segment_projection(segment) for segment in normalized_plan.segments
     ]
     normalized_normalization = [
         _require_string(item, f"normalization[{index}]")
         for index, item in enumerate(normalization)
     ]
     compatibility = _normalize_v1_compatibility(v1_compatibility)
 
     payload: dict[str, Any] = {
         "schema_version": PROVENANCE_SCHEMA_VERSION,
         "engine": legacy_engine,
         "output": output_path,
         "timeline": timeline_path,
         "assets_registry": assets_path,
         "request_digest": normalized_plan.request_digest,
         "requested_policy": normalized_plan.requested_policy,
         "planner": normalized_plan.planner.to_dict(),
         # V1-compatible segment projection: flat {engine, from, to} entries,
         # exactly the shape legacy consumers read from `segments`.
         "segments": legacy_segments,
         # Additive normalized v2 segment records; never overwrite v1 fields.
         "segments_v2": normalized_segments,
         "artifact_profiles": _normalize_artifact_profiles(
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 69d4327..55df8a5 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -825,200 +825,240 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
     with pytest.raises(TypeError, match="hashed lineage"):
         assemble_provenance_v2(
             **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
             },
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": "not-a-hash",
                     "attachments": {},
                 }
             },
         )
     with pytest.raises(ValueError, match="unknown fields"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {},
                     "spoof": 1,
                 }
             },
         )
     with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
         assemble_provenance_v2(
             **base,
             plan=_plan(
                 segments=[_segment(0, 24), _segment(24, 48)]
             ),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {},
                 }
             },
         )
     with pytest.raises(ValueError, match="attachment path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {
                         "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
                     },
                 },
             },
         )
     with pytest.raises(ValueError, match="attachment kind"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {
                         "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
                     },
                 },
             },
         )
 
 
     with pytest.raises(ValueError, match="must equal Attachment.name"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {
                         "different_key": Attachment(
                             name="alpha",
                             path="outputs/alpha.mp4",
                             kind="alpha",
                             sha256=SHA_C,
                         )
                     },
                 }
             },
         )
+    with pytest.raises(ValueError, match="duplicate attachment name"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles={
+                "out/v1.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+                "out/v2.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_D,
+                    "attachments": {
+                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+    with pytest.raises(ValueError, match="workspace path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
+        )
+    with pytest.raises(ValueError, match="duplicate path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles=[
+                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
+                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
+            ],
+        )
 
 
 def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
     plan = _plan(
         segments=[_segment(12, 24), _segment(24, 36)],
         total_frames=48,
         window=_window(12, 36),
     )
     assert plan.total_frames == 48
     assert plan.window == _window(12, 36)
 
 
 @pytest.mark.parametrize(
     ("segments", "total_frames", "match"),
     [
         ([_segment(1, 48)], 48, "gap"),
         ([_segment(0, 47)], 48, "trailing gap"),
         ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
         ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
         ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
     ],
 )
 def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
     segments: list[RenderSegment],
     total_frames: int,
     match: str,
 ) -> None:
     with pytest.raises(ValueError, match=match):
         _plan(segments=segments, total_frames=total_frames)
 
 
 def test_plan_rejects_noncanonical_segment_or_window_fps() -> None:
     with pytest.raises(ValueError, match="segment.*FPS"):
         _plan(segments=[_segment(fps=(48, 2))])
     with pytest.raises(ValueError, match="window FPS"):
         _plan(window=_window(0, 48, fps=(48, 2)))
 
 
 def test_zero_frame_plan_semantics_and_no_finalization() -> None:
     empty = _plan(segments=[], total_frames=0, profile=_profile(audio=False))
     assert empty.segments == []
     assert empty.reasons == {}
     with pytest.raises(ValueError, match="zero-frame plan"):
         _plan(segments=[_segment()], total_frames=0)
     with pytest.raises(ValueError, match="positive-frame plan"):
         _plan(segments=[], total_frames=48)
     with pytest.raises(ValueError, match="must not be finalized"):
         _finalize(plan=empty, artifacts=[])
 
 
 def test_qualified_id_grammar_allows_hyphens_and_underscores() -> None:
     assert _finalizer().id == "rendering.ffmpeg-finalizer"
     assert replace(_finalizer(), id="1render.2-finalizer",
                    support_decision=_support("1render.2-finalizer")).id == "1render.2-finalizer"
     assert replace(_finalizer(), id="rendering.legacy_hybrid",
                    support_decision=_support("rendering.legacy_hybrid")).id == "rendering.legacy_hybrid"
     assert replace(_finalizer(), id="acme.bad_id",
                    support_decision=_support("acme.bad_id")).id == "acme.bad_id"
     for invalid in (
         "Rendering.Ffmpeg",
         "rendering.-finalizer",
         "unqualified",
     ):
         with pytest.raises(ValueError, match="qualified id"):
             replace(_finalizer(), id=invalid, support_decision=_support(invalid))
 
 
 def test_contracts_are_frozen() -> None:
     window = _window()
     with pytest.raises(FrozenInstanceError):
         window.start_frame = 1  # type: ignore[misc]
 
 
 def test_manifest_round_trip() -> None:
     common = {
         "schema_version": 1,
         "name": "Example",
         "version": "1.0.0",
         "protocol_version": 1,
         "command": ["python3", "backend.py"],
         "description": "Example implementation",
         "capabilities": {"features": {"media": True}},
         "required_permissions": ["project_files"],
         "required_binaries": [],
         "timeout_seconds": 60,
         "metadata": {"vendor": "Acme"},
     }
     cases = [
         (RendererManifest, {**common, "id": "acme.renderer", "operations": ["render", "support"]}),
         (PlannerManifest, {**common, "id": "acme.planner", "operations": ["plan"]}),
         (FinalizerManifest, {**common, "id": "acme.finalizer", "operations": ["finalize"]}),
     ]
     for manifest_type, payload in cases:
         assert manifest_type.from_dict(payload).to_dict() == payload
 
 
 def test_manifest_dto_rejects_schema_invalid_capabilities_and_scalar_command() -> None:
     base = {
         "schema_version": 1,
         "id": "acme.renderer",
diff --git a/tests/core/rendering/test_schema_roundtrip.py b/tests/core/rendering/test_schema_roundtrip.py
index f5de62c..6bb12a3 100644
--- a/tests/core/rendering/test_schema_roundtrip.py
+++ b/tests/core/rendering/test_schema_roundtrip.py
@@ -183,196 +183,198 @@ def _plan_cases() -> list[tuple[str, dict[str, Any]]]:
     partial["profile"]["audio_codec"] = "aac"
     zero_with_segment = deepcopy(base)
     zero_with_segment["total_frames"] = 0
     zero_with_segment["reasons"] = {}
     cases = [
         ("valid canonical", base),
         ("valid object policy", _set(base, ("requested_policy",), {"ordered": ["acme.visual"]})),
         ("missing total", _delete(base, ("total_frames",))),
         ("unknown field", {**base, "backend": "acme.visual"}),
         ("uppercase renderer", _set(base, ("segments", 0, "renderer", "id"), "Acme.Visual")),
         ("valid underscore renderer", _set(
             _set(base, ("segments", 0, "renderer", "id"), "acme.bad_id"),
             ("segments", 0, "renderer", "support_decision", "backend"),
             "acme.bad_id",
         )),
         ("malformed request hash", _set(base, ("request_digest",), "bad")),
         ("malformed input hash", _set(base, ("segments", 0, "input_hashes", "timeline"), "bad")),
         ("partial populated audio", partial),
         ("boolean total", _set(base, ("total_frames",), True)),
         ("zero with segment", zero_with_segment),
         ("nested support version", _set(base, ("segments", 0, "renderer", "support_decision", "schema_version"), 2)),
     ]
     return _with_version_adversaries(base, cases)
 
 
 def _result_cases() -> list[tuple[str, dict[str, Any]]]:
     base = _load_fixture("result.json")
     error = deepcopy(_load_schema("result.json")["examples"][1])
     partial = deepcopy(base)
     partial["video"]["profile"]["audio_codec"] = "aac"
     cases = [
         ("valid canonical success", base),
         ("valid canonical error", error),
         ("missing video", _delete(base, ("video",))),
         ("unknown top-level attachment surface", {**base, "attachments": {}}),
         ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
         ("whitespace log", _set(base, ("logs",), ["   "])),
         ("nul in log", _set(base, ("logs",), ["bad\u0000log"])),
         ("whitespace video path", _set(base, ("video", "path"), "   ")),
         ("drive-relative video", _set(base, ("video", "path"), "C:escape.mp4")),
         ("drive-relative attachment", _set(_set(base, ("video", "attachments"), {"x.dat": {"name": "x.dat", "path": "C:escape.dat", "kind": "project", "sha256": "a" * 64}}), ("video", "path"), "outputs/visual.mp4")),
         (
             "underscore attachment kind",
             _set(
                 base,
                 ("video", "attachments"),
                 {
                     "x.dat": {
                         "name": "x.dat",
                         "path": "outputs/x.dat",
                         "kind": "project_file",
                         "sha256": "a" * 64,
                     }
                 },
             ),
         ),
         ("partial populated audio", partial),
         ("contradictory ownership", _set(base, ("audio_ownership",), "passthrough")),
         ("valid underscore fragment namespace", _set(base, ("backend_fragments",), {"acme.bad_id": {}})),
         ("core fragment key", _set(base, ("backend_fragments",), {"acme.visual": {"planner": {}}})),
         ("error missing version", _delete(error, ("schema_version",))),
         ("error boolean version", _set(error, ("schema_version",), True)),
         ("error malformed version", _set(error, ("schema_version",), "1")),
         ("error unknown version", _set(error, ("schema_version",), 2)),
     ]
     return _with_version_adversaries(base, cases)
 
 
 def _finalize_cases() -> list[tuple[str, dict[str, Any]]]:
     base = _load_fixture("finalize.json")
     partial = deepcopy(base)
     partial["artifacts"][0]["profile"]["audio_codec"] = "aac"
     zero_plan = deepcopy(base)
     zero_plan["plan"] = deepcopy(_load_schema("plan.json")["examples"][1])
     cases = [
         ("valid canonical", base),
         ("missing artifacts", _delete(base, ("artifacts",))),
         ("unknown field", {**base, "faststart": True}),
         ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
         ("empty artifacts", _set(base, ("artifacts",), [])),
         ("drive-relative artifact", _set(base, ("artifacts", 0, "path"), "C:segment.mp4")),
         (
             "underscore attachment kind",
             _set(
                 base,
                 ("artifacts", 0, "attachments"),
                 {
                     "x.dat": {
                         "name": "x.dat",
                         "path": "outputs/x.dat",
                         "kind": "project_file",
                         "sha256": "a" * 64,
                     }
                 },
             ),
         ),
         ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
                 ("partial populated audio", partial),
         ("contradictory artifact audio", _set(base, ("artifacts", 0, "audio"), "rendered")),
         ("nested plan version", _set(base, ("plan", "schema_version"), 2)),
+        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
+        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
         ("zero-frame plan", zero_plan),
     ]
     return _with_version_adversaries(base, cases)
 
 
 def _manifest_cases(
     schema_name: str,
     required_operation: str,
 ) -> list[tuple[str, dict[str, Any]]]:
     base = deepcopy(_load_schema(schema_name)["examples"][0])
     return [
         ("valid canonical", base),
         ("missing id", _delete(base, ("id",))),
         ("valid underscore id", _set(base, ("id",), "acme.bad_id")),
         ("unknown field", {**base, "priority": 1}),
         ("boolean version", _set(base, ("schema_version",), True)),
         ("unknown version", _set(base, ("schema_version",), 2)),
         ("malformed protocol version", _set(base, ("protocol_version",), "1")),
         ("empty command", _set(base, ("command",), [])),
         ("missing required operation", _set(base, ("operations",), ["support"])),
         (
             "duplicate operation",
             _set(base, ("operations",), [required_operation, required_operation]),
         ),
         ("unknown permission", _set(base, ("required_permissions",), ["root"])),
         ("unknown capability", _set(base, ("capabilities",), {"unknown": True})),
     ]
 
 
 def _with_version_adversaries(
     base: dict[str, Any],
     cases: list[tuple[str, dict[str, Any]]],
 ) -> list[tuple[str, dict[str, Any]]]:
     return cases + [
         ("missing version", _delete(base, ("schema_version",))),
         ("boolean version", _set(base, ("schema_version",), True)),
         ("malformed version", _set(base, ("schema_version",), "1")),
         ("unknown version", _set(base, ("schema_version",), 2)),
     ]
 
 
 CASE_BUILDERS: dict[str, Callable[[], list[tuple[str, dict[str, Any]]]]] = {
     "request.json": _request_cases,
     "support.json": _support_cases,
     "plan.json": _plan_cases,
     "result.json": _result_cases,
     "finalize.json": _finalize_cases,
     "renderer-manifest.json": lambda: _manifest_cases("renderer-manifest.json", "render"),
     "planner-manifest.json": lambda: _manifest_cases("planner-manifest.json", "plan"),
     "finalizer-manifest.json": lambda: _manifest_cases(
         "finalizer-manifest.json", "finalize"
     ),
 }
 
 
 @pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
 def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
     validator = jsonschema.Draft7Validator(_load_schema(schema_name))
     parser = PARSERS[schema_name]
     for label, payload in CASE_BUILDERS[schema_name]():
         schema_accepts = validator.is_valid(payload)
         dto_accepts = _accepted(parser, payload)
         expected = label.startswith("valid ")
         assert schema_accepts is expected, (
             f"{schema_name} unexpected schema result for {label}: "
             f"expected={expected}, actual={schema_accepts}"
         )
         assert dto_accepts == schema_accepts, (
             f"{schema_name} parity mismatch for {label}: "
             f"schema={schema_accepts}, dto={dto_accepts}"
         )
 
 
 @pytest.mark.parametrize(
     "path",
     [
         "../escape.mp4",
         "outputs/./escape.mp4",
         "outputs//escape.mp4",
         "outputs/",
         "/tmp/escape.mp4",
         "C:escape.mp4",
         r"C:\\temp\\escape.mp4",
         r"dir\\escape.mp4",
     ],
 )
 def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
     result = _load_fixture("result.json")
     result["video"]["path"] = path
     assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
 
 
 def test_python_result_type_annotation_remains_the_success_dto() -> None:
     payload = _load_fixture("result.json")
     parsed = parse_wire_result(payload)
     assert isinstance(parsed, RenderResult)

 succeeded in 0ms:
3:## Batch 1 — Baseline, contracts, and discovery
10:- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
12:- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
15:- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
16:- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.
20:- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
23:- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
24:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
32:- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
33:- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
45:- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
50:## Batch 3 — Built-in renderer and finalizer extraction
56:- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
58:- One non-recursive cross-process lock spans registry-state reads, all registry/shim/theme-pointer writes, active-theme selection, the complete Remotion render, and the `gen-types` writer path.
60:- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
62:- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
80:- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
84:- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
90:- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
102:- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
103:- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
104:- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
105:- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
106:- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
112:- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
113:- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
114:- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
116:- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
117:- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
118:- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
128:- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
130:- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
131:- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
136:- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
138:- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
140:- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
141:- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.
149:- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
154:- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
162:- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
164:- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
165:- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
167:- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
172:- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
174:- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
175:- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
177:- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
178:- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
Reading additional input from stdin...
2026-08-12T01:56:32.453726Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:56:32.454769Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:56:32.454775Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3af-7d28-7402-85a0-bf8fa09993c3
--------
user
# Megado Checkpoint — Batch 1 seventh re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3),
-r6 (3). Seventh rework committed as `ab486f9` (prior head 086d692).
Incremental diff at /tmp/batch1-r7.diff.

## How each of your 3 re-review6 issues was addressed (host-implemented)

1. **Artifact lineage unbound** →
   - A positive plan now requires EXACTLY ONE path-keyed lineage entry PER
     SEGMENT (cardinality mismatch rejected).
   - Sequence form requires VideoArtifacts so records stay path-keyed;
     `None`/`{}` for positive plans rejected.
2. **Attachment lineage bypasses Attachment contract** →
   - Attachment paths validated as workspace-relative, kinds validated
     against `[a-z][a-z0-9-]*`, sha256 validated — via the `Attachment` DTO
     (uniform for raw and dataclass values).
   - Attachment map key must equal `Attachment.name` (mutated values
     rejected, not silently relabeled).
   - Adversarial tests: traversal path, bad kind, key/name mismatch.
3. **Schema/DTO parity** →
   - Embedded `supportReport.features` in plan.json/finalize.json gained
     nonblank/NUL `propertyNames`.
   - workspacePath containment lookaheads now use `[\s\S]*` — traversal
     (`../`), double slashes, and backslashes after newlines rejected;
     internal newlines accepted like the DTO. Multiline traversal tests.

## Evidence

- Incremental diff: /tmp/batch1-r7.diff (7 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.
- Docs updated: per-segment lineage cardinality + attachment contract.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 7 review rounds and the
contract is now heavily validated. If the remaining items are non-blocking or
absent, say exactly `PASS` so Batch 2 can begin. If blocking, name precisely.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` checkpoint guidance and the repo’s context-minimization/subagent guidance. I’ll audit the incremental diff plus the affected contracts/tests, delegate independent adversarial checks, and return exactly `PASS` if I find no blocking defect.
exec
/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/megado/SKILL.md && cat /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && cat /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc 'git diff --unified=8 ab486f9..8418bae -- astrid/core/rendering/schemas/v1 docs/contracts/render-backend-v1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 1e49ad3..f21e12d 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -33,17 +33,17 @@
       "type": "array",
       "minItems": 1,
       "items": {
         "$ref": "#/definitions/videoArtifact"
       }
     },
     "output_name": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "backend_config": {
@@ -51,43 +51,43 @@
     },
     "metadata": {
       "$ref": "#/definitions/stringMap"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}$"
+      "pattern": "^[0-9a-f]{64}\\Z"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "portableName": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
@@ -189,66 +189,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -269,26 +269,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
@@ -309,29 +309,29 @@
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "alternatives": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "$ref": "#/definitions/qualifiedId"
           }
@@ -340,17 +340,17 @@
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
@@ -373,17 +373,17 @@
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -426,17 +426,17 @@
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -473,17 +473,17 @@
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -507,17 +507,17 @@
       }
     },
     "hashMap": {
       "type": "object",
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "renderSegment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "window",
         "renderer",
@@ -578,22 +578,22 @@
         },
         "total_frames": {
           "type": "integer",
           "minimum": 0
         },
         "reasons": {
           "type": "object",
           "propertyNames": {
-            "pattern": "^(0|[1-9][0-9]*)$"
+            "pattern": "^(0|[1-9][0-9]*)\\Z"
           },
           "additionalProperties": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "window": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameWindow"
             },
             {
@@ -647,17 +647,17 @@
         "name": {
           "$ref": "#/definitions/portableName"
         },
         "path": {
           "$ref": "#/definitions/workspacePath"
         },
         "kind": {
           "type": "string",
-          "pattern": "^[a-z][a-z0-9-]*$"
+          "pattern": "^[a-z][a-z0-9-]*\\Z"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         }
       }
     },
     "attachments": {
       "type": "object",
@@ -711,17 +711,17 @@
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
@@ -753,21 +753,21 @@
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "overrideRecord": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "from",
         "to"
diff --git a/astrid/core/rendering/schemas/v1/finalizer-manifest.json b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
index 0525220..0bde205 100644
--- a/astrid/core/rendering/schemas/v1/finalizer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
@@ -18,33 +18,33 @@
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
     },
     "command": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,63 +59,63 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "capabilities": {
       "$ref": "#/definitions/finalizerCapabilities",
       "default": {}
     },
     "required_permissions": {
       "$ref": "#/definitions/permissions",
       "default": []
     },
     "required_binaries": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "uniqueItems": true,
       "default": []
     },
     "timeout_seconds": {
       "type": [
         "integer",
         "null"
       ],
       "minimum": 1,
       "default": null
     },
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "project_files",
           "network",
@@ -130,17 +130,17 @@
     "finalizerCapabilities": {
       "type": "object",
       "properties": {
         "containers": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
         "preserves_attachments": {
           "type": "boolean"
         },
         "audio_ownership": {
           "type": "array",
@@ -158,22 +158,22 @@
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index 47740f8..47bb576 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -45,22 +45,22 @@
     },
     "total_frames": {
       "type": "integer",
       "minimum": 0
     },
     "reasons": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(0|[1-9][0-9]*)$"
+        "pattern": "^(0|[1-9][0-9]*)\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "window": {
       "anyOf": [
         {
           "$ref": "#/definitions/frameWindow"
         },
         {
@@ -98,28 +98,28 @@
           }
         }
       }
     }
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}$"
+      "pattern": "^[0-9a-f]{64}\\Z"
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
@@ -221,66 +221,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -301,26 +301,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
@@ -341,29 +341,29 @@
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "alternatives": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "$ref": "#/definitions/qualifiedId"
           }
@@ -372,17 +372,17 @@
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
@@ -405,17 +405,17 @@
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -458,17 +458,17 @@
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -505,17 +505,17 @@
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -539,17 +539,17 @@
       }
     },
     "hashMap": {
       "type": "object",
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "renderSegment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "window",
         "renderer",
diff --git a/astrid/core/rendering/schemas/v1/planner-manifest.json b/astrid/core/rendering/schemas/v1/planner-manifest.json
index 1334afe..48e0756 100644
--- a/astrid/core/rendering/schemas/v1/planner-manifest.json
+++ b/astrid/core/rendering/schemas/v1/planner-manifest.json
@@ -18,33 +18,33 @@
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
     },
     "command": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,63 +59,63 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "capabilities": {
       "$ref": "#/definitions/plannerCapabilities",
       "default": {}
     },
     "required_permissions": {
       "$ref": "#/definitions/permissions",
       "default": []
     },
     "required_binaries": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "uniqueItems": true,
       "default": []
     },
     "timeout_seconds": {
       "type": [
         "integer",
         "null"
       ],
       "minimum": 1,
       "default": null
     },
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "project_files",
           "network",
@@ -130,38 +130,38 @@
     "plannerCapabilities": {
       "type": "object",
       "properties": {
         "policies": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
         "supports_fallback": {
           "type": "boolean"
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
diff --git a/astrid/core/rendering/schemas/v1/renderer-manifest.json b/astrid/core/rendering/schemas/v1/renderer-manifest.json
index c079378..b6cf411 100644
--- a/astrid/core/rendering/schemas/v1/renderer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/renderer-manifest.json
@@ -18,33 +18,33 @@
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
     },
     "command": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,63 +59,63 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "capabilities": {
       "$ref": "#/definitions/rendererCapabilities",
       "default": {}
     },
     "required_permissions": {
       "$ref": "#/definitions/permissions",
       "default": []
     },
     "required_binaries": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "uniqueItems": true,
       "default": []
     },
     "timeout_seconds": {
       "type": [
         "integer",
         "null"
       ],
       "minimum": 1,
       "default": null
     },
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "project_files",
           "network",
@@ -130,58 +130,58 @@
     "rendererCapabilities": {
       "type": "object",
       "properties": {
         "clip_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
         "track_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "supports_full_timeline": {
           "type": "boolean"
         },
         "supports_windows": {
           "type": "boolean"
         },
         "output_profiles": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
         "audio_ownership": {
           "type": "array",
           "items": {
             "type": "string",
             "enum": [
diff --git a/astrid/core/rendering/schemas/v1/request.json b/astrid/core/rendering/schemas/v1/request.json
index a69ff83..575f0da 100644
--- a/astrid/core/rendering/schemas/v1/request.json
+++ b/astrid/core/rendering/schemas/v1/request.json
@@ -12,29 +12,29 @@
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "timeline_path": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "assets_registry_path": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "output_name": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "window": {
@@ -96,17 +96,17 @@
             "required": [
               "audio_codec",
               "audio_sample_rate",
               "audio_channel_layout"
             ],
             "properties": {
               "audio_codec": {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             }
           }
         }
       }
     },
     {
       "if": {
@@ -143,17 +143,17 @@
           }
         }
       }
     }
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "audioOwnership": {
       "type": "string",
       "enum": [
         "rendered",
         "passthrough",
         "none"
       ]
@@ -250,66 +250,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -330,26 +330,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
       ]
     },
     "backendConfig": {
       "type": "object",
       "propertyNames": {
@@ -357,21 +357,21 @@
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "timeline_path": "/workspace/timeline.json",
       "assets_registry_path": "/workspace/assets.json",
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index e089030..8a93ef7 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -8,30 +8,30 @@
     },
     {
       "$ref": "#/definitions/error"
     }
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}$"
+      "pattern": "^[0-9a-f]{64}\\Z"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "portableName": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "audioOwnership": {
@@ -79,66 +79,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -159,26 +159,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
       ]
     },
     "attachment": {
       "type": "object",
       "additionalProperties": false,
@@ -192,17 +192,17 @@
         "name": {
           "$ref": "#/definitions/portableName"
         },
         "path": {
           "$ref": "#/definitions/workspacePath"
         },
         "kind": {
           "type": "string",
-          "pattern": "^[a-z][a-z0-9-]*$"
+          "pattern": "^[a-z][a-z0-9-]*\\Z"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         }
       }
     },
     "attachments": {
       "type": "object",
@@ -256,17 +256,17 @@
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
@@ -348,27 +348,27 @@
         }
       }
     },
     "stringArray": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "success": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "video",
@@ -481,25 +481,25 @@
           ]
         },
         "backend": {
           "$ref": "#/definitions/qualifiedId"
         },
         "message": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "recovery_command": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "details": {
           "type": "object"
         }
       }
     }
   },
   "examples": [
diff --git a/astrid/core/rendering/schemas/v1/support.json b/astrid/core/rendering/schemas/v1/support.json
index af94ae5..49d7095 100644
--- a/astrid/core/rendering/schemas/v1/support.json
+++ b/astrid/core/rendering/schemas/v1/support.json
@@ -21,29 +21,29 @@
     "supported": {
       "type": "boolean"
     },
     "reasons": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "features": {
       "type": "object",
       "additionalProperties": {
         "type": [
           "boolean",
           "string"
         ]
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "alternatives": {
       "type": "array",
       "uniqueItems": true,
       "items": {
         "$ref": "#/definitions/qualifiedId"
       }
@@ -52,23 +52,23 @@
       "$ref": "#/definitions/qualifiedId"
     },
     "backend_version": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "supported": true,
       "reasons": [],
       "features": {
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index dc24a65..f98e1b1 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -471,26 +471,29 @@ Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
 `request_digest`, `requested_policy`, `planner`, every segment's nested
 `renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
 assembler accepts no parallel singular renderer identity. The nested records
 have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
 distinct source pack, manifest, alias/override, support, and input-hash evidence
 for every renderer invocation. Planner and finalizer records carry the same
 alias/override/trust/support evidence as renderer records. Rendered artifacts
 are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
-hashed lineage record PER SEGMENT, each mapping a unique output path to
-exactly `{profile, sha256, attachments}` with a validated 64-hex string
-`sha256` on the artifact and every attachment `{path, kind, sha256}`.
-Attachment paths must be workspace-relative, kinds must match
-`[a-z][a-z0-9-]*`, and attachment map keys must equal the attachment's own
-name. Profile-only entries, null/malformed hashes, unknown or missing fields,
-path escapes, invalid kinds, and cardinality mismatches are all rejected.
-Sequence-form lineage requires VideoArtifacts so records stay path-keyed.
-Replay can verify rendered outputs byte-for-byte. `input_hashes` describe
-inputs only, never rendered outputs.
+hashed lineage entry PER SEGMENT, each keyed by a workspace-relative output
+path with exactly `{profile, sha256, attachments}` and a validated 64-hex
+string `sha256` on the artifact and every attachment `{path, kind, sha256}`.
+Sequence form preserves segment order (a path-keyed list) and rejects
+duplicate paths; mapping form requires path keys to equal the artifact's own
+path. Attachment paths must be workspace-relative, kinds must match
+`[a-z][a-z0-9-]*`, attachment map keys must equal the attachment's own name,
+and attachment names must be unique ACROSS all segment artifacts. Profile-only
+entries, null/malformed hashes, unknown or missing fields, path escapes,
+invalid kinds, duplicate paths, duplicate attachment names, and cardinality
+mismatches are all rejected; all Attachment and RenderProfile values are
+reconstructed through their DTO validators. Replay can verify rendered outputs
+byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
 
 `engine` is only the legacy request projection. The `segments` key keeps the
 V1-compatible flat projection: one `{engine, from, to}` entry per segment,
 derived from `renderer.id` and the validated integer `FrameWindow` at its
 rational FPS — exactly the shape legacy consumers read. The additive
 `segments_v2` key carries the complete normalized v2 segment records
 (`window`, `renderer` resolution, `input_hashes`); it never overwrites or
 reshapes a V1 key. When the v1 `segment_provenance` top-level projection

exec
/bin/zsh -lc 'tail -n 220 .oracle/checkins/batch-1-r7.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
a=Attachment(name=\"alpha\",path=\"outputs/a\",kind=\"alpha\",sha256=ns[\"SHA_A\"])
object.__setattr__(a,\"path\",\"../escape\"); object.__setattr__(a,\"kind\",\"Bad_Kind\"); object.__setattr__(a,\"sha256\",\"bad\")
record={\"profile\":ns[\"_profile\"](),\"sha256\":ns[\"SHA_A\"],\"attachments\":{}}
kw=dict(engine=\"hybrid\",output=\"out.mp4\",timeline=\"timeline.json\",assets_registry=None,plan=ns[\"_plan\"](),artifact_profiles={\"outputs/out.mp4\":record},audio_ownership=\"rendered\",normalization=[],attachments={\"alpha\":a},backend_fragments={},v1_compatibility=ns[\"_compatibility\"]())
try:
 out=assemble_provenance_v2(**kw); print(\"ACCEPTED\",out[\"attachments\"])
except Exception as e: print(\"REJECTED\",type(e).__name__,e)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 166ms:
ACCEPTED {'alpha': {'name': 'alpha', 'path': '../escape', 'kind': 'Bad_Kind', 'sha256': 'bad'}}

exec
/bin/zsh -lc 'rg -n "object.__setattr__|mutat|FrozenInstance|frozen" tests/core/rendering .oracle/checkins/batch-1-r6.md | tail -n 160' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/checkins/batch-1-r6.md:139:`setup` is dry-run by default; pass `--apply` to mutate.
.oracle/checkins/batch-1-r6.md:284:`astrid sessions takeover` atomically increments the run's `writer_epoch` and swaps the lease writer; any other tab that was writing to the run gets a `StaleEpochError` on its next mutating verb.
.oracle/checkins/batch-1-r6.md:291:Normal task-run mutations must go through the writer-owned task APIs; do not
.oracle/checkins/batch-1-r6.md:304:cached projection replayed from `plan_initialized` plus `plan_mutated`, not as
.oracle/checkins/batch-1-r6.md:305:the source of truth. Use plan mutation verbs for edits.
.oracle/checkins/batch-1-r6.md:348:  tasklist.md        # frozen batched task list with checkpoints + [HARD] tags
.oracle/checkins/batch-1-r6.md:410:Emit as markdown (or JSON if the host will script it) into `.oracle/tasklist.md`. This file is **frozen** — execution follows it; plan revisions during execution go through the oracle, not silent edits.
.oracle/checkins/batch-1-r6.md:791:| `effects/audio-reactive-colour` | Fill the frame with colours selected by frozen integer-frame markers. |
.oracle/checkins/batch-1-r6.md:1382:.oracle/tasklist.md:89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
.oracle/checkins/batch-1-r6.md:1415:.oracle/checkins/batch-1-r5.md:885:.oracle/checkins/batch-1-r3.md:1414:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r6.md:1418:.oracle/checkins/batch-1-r5.md:895:.oracle/checkins/batch-1-r3.md:1467:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r6.md:1420:.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1422:.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1431:.oracle/checkins/batch-1-r5.md:1072:22646:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r6.md:1433:.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1435:.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1462:.oracle/checkins/batch-1-r5.md:1465:             object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r6.md:1473:.oracle/checkins/batch-1-r5.md:1565:         object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r6.md:1485:.oracle/checkins/batch-1-r5.md:1667:             object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r6.md:1570:.oracle/checkins/batch-1-r5.md:4428:  1049	            object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r6.md:1581:.oracle/checkins/batch-1-r5.md:4527:  1148	        object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r6.md:1841: CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)
.oracle/checkins/batch-1-r6.md:2729: def test_contracts_are_frozen() -> None:
.oracle/checkins/batch-1-r6.md:2731:     with pytest.raises(FrozenInstanceError):
.oracle/checkins/batch-1-r6.md:2794:    30	CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)
.oracle/checkins/batch-1-r6.md:3615:     4	source of truth.  These frozen dataclasses are the small Python projection of
.oracle/checkins/batch-1-r6.md:3652:    41	RENDER_RESULT_CORE_KEYS = frozenset(
.oracle/checkins/batch-1-r6.md:3664:    53	PROVENANCE_V2_CORE_KEYS = frozenset(
.oracle/checkins/batch-1-r6.md:3685:    74	PROVENANCE_V1_COMPATIBILITY_KEYS = frozenset(
.oracle/checkins/batch-1-r6.md:3705:    94	PROVENANCE_V1_ALWAYS_KEYS = frozenset(
.oracle/checkins/batch-1-r6.md:3722:   111	_RETIRED_PROVENANCE_V2_KEYS = frozenset(
.oracle/checkins/batch-1-r6.md:3935:   582	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:3951:   598	        object.__setattr__(self, "name", name)
.oracle/checkins/batch-1-r6.md:3952:   599	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))
.oracle/checkins/batch-1-r6.md:3953:   600	        object.__setattr__(self, "kind", kind)
.oracle/checkins/batch-1-r6.md:3954:   601	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "attachment sha256"))
.oracle/checkins/batch-1-r6.md:4008:   655	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:4025:   672	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
.oracle/checkins/batch-1-r6.md:4026:   673	        object.__setattr__(self, "profile", profile)
.oracle/checkins/batch-1-r6.md:4027:   674	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
.oracle/checkins/batch-1-r6.md:4028:   675	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:4035:   682	        object.__setattr__(self, "audio", audio)
.oracle/checkins/batch-1-r6.md:4036:   683	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:6698:920:        object.__setattr__(self, "features", features)
.oracle/checkins/batch-1-r6.md:6706:2103:            allowed=frozenset({"policies", "supports_fallback", "features"}),
.oracle/checkins/batch-1-r6.md:6744:   892	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:6757:   905	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:6764:   912	        object.__setattr__(self, "reasons", _require_string_list(self.reasons, "reasons"))
.oracle/checkins/batch-1-r6.md:6772:   920	        object.__setattr__(self, "features", features)
.oracle/checkins/batch-1-r6.md:6779:   927	        object.__setattr__(self, "alternatives", alternatives)
.oracle/checkins/batch-1-r6.md:6780:   928	        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "backend"))
.oracle/checkins/batch-1-r6.md:6781:   929	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:6839:   987	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:6841:   989	    """Resolved planner identity and trust evidence frozen into a plan."""
.oracle/checkins/batch-1-r6.md:7909:   915	def test_contracts_are_frozen() -> None:
.oracle/checkins/batch-1-r6.md:7911:   917	    with pytest.raises(FrozenInstanceError):
.oracle/checkins/batch-1-r6.md:8184:tests/timeline/test_migration.py:1269:    def test_config_event_is_not_mutated_on_parity_failure(
.oracle/checkins/batch-1-r6.md:8947:   288	contract explicitly says so, but it may not silently drop, rename, or mutate an
.oracle/checkins/batch-1-r6.md:9039:  1228	            object.__setattr__(
.oracle/checkins/batch-1-r6.md:9060:  1249	            object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r6.md:9105:  1294	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:9114:  1303	        object.__setattr__(self, "window", _coerce_window(self.window, "segment window", nullable=False))
.oracle/checkins/batch-1-r6.md:9120:  1309	        object.__setattr__(self, "renderer", renderer)
.oracle/checkins/batch-1-r6.md:9121:  1310	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:9160:  1349	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:9176:  1365	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:9181:  1370	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:9186:  1375	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:9196:  1385	        object.__setattr__(self, "planner", planner)
.oracle/checkins/batch-1-r6.md:9205:  1394	        object.__setattr__(self, "segments", segments)
.oracle/checkins/batch-1-r6.md:9211:  1400	        object.__setattr__(self, "finalizer", finalizer)
.oracle/checkins/batch-1-r6.md:9213:  1402	        object.__setattr__(self, "profile", profile)
.oracle/checkins/batch-1-r6.md:9215:  1404	        object.__setattr__(self, "total_frames", total_frames)
.oracle/checkins/batch-1-r6.md:9217:  1406	        object.__setattr__(self, "window", window)
.oracle/checkins/batch-1-r6.md:9300:  1518	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:9326:  1544	        object.__setattr__(self, "schema_version", version)
.oracle/checkins/batch-1-r6.md:9327:  1545	        object.__setattr__(self, "video", video)
.oracle/checkins/batch-1-r6.md:9328:  1546	        object.__setattr__(self, "backend_fragments", _validate_backend_fragments(self.backend_fragments))
.oracle/checkins/batch-1-r6.md:9329:  1547	        object.__setattr__(self, "audio_ownership", ownership)
.oracle/checkins/batch-1-r6.md:9330:  1548	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:9335:  1553	        object.__setattr__(self, "logs", _require_string_list(self.logs, "logs"))
.oracle/checkins/batch-1-r6.md:9336:  1554	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
.oracle/checkins/batch-1-r6.md:9408:.oracle/checkins/batch-1-r6.md:1420:.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9409:.oracle/checkins/batch-1-r6.md:1422:.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9412:.oracle/checkins/batch-1-r6.md:1433:.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9413:.oracle/checkins/batch-1-r6.md:1435:.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9506:.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9507:.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9510:.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9511:.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9659:.oracle/checkins/batch-1-r2.md:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9660:.oracle/checkins/batch-1-r2.md:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9662:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9663:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9701:.oracle/checkins/batch-1-r4.md:15314:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:9702:.oracle/checkins/batch-1-r4.md:15329:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:10398:  1607	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:10409:  1618	    KINDS: ClassVar[frozenset[str]] = frozenset(
.oracle/checkins/batch-1-r6.md:10422:  1631	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:10430:  1639	        object.__setattr__(self, "kind", kind)
.oracle/checkins/batch-1-r6.md:10431:  1640	        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "error backend"))
.oracle/checkins/batch-1-r6.md:10432:  1641	        object.__setattr__(self, "message", _require_string(self.message, "error message"))
.oracle/checkins/batch-1-r6.md:10433:  1642	        object.__setattr__(
.oracle/checkins/batch-1-r6.md:10438:  1647	        object.__setattr__(self, "details", _json_safe_mapping(self.details, label="error details"))
.oracle/checkins/batch-1-r6.md:10484:  1693	@dataclass(frozen=True)
.oracle/checkins/batch-1-r6.md:10526:  1735	        object.__setattr__(self, "schema_version", version)
.oracle/checkins/batch-1-r6.md:10527:  1736	        object.__setattr__(self, "plan", plan)
.oracle/checkins/batch-1-r6.md:10528:  1737	        object.__setattr__(self, "artifacts", artifacts)
.oracle/checkins/batch-1-r6.md:10529:  1738	        object.__setattr__(self, "output_name", output_name)
.oracle/checkins/batch-1-r6.md:10540:  1749	        object.__setattr__(self, "backend_config", backend_config)
.oracle/checkins/batch-1-r6.md:10541:  1750	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
.oracle/checkins/batch-1-r6.md:10580:     5	**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
.oracle/checkins/batch-1-r6.md:10590:    15	- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
.oracle/checkins/batch-1-r6.md:10818:2. **Attachment lineage still bypasses the `Attachment` contract.** Raw lineage accepts traversal paths and invalid kinds; mutated `Attachment` values whose `name` differs from the map key are silently relabeled when `name` is stripped. Validate workspace path, kind grammar, and key/name equality before emitting the three-field projection. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:155)
.oracle/checkins/batch-1-r6.md:10828:2. **Attachment lineage still bypasses the `Attachment` contract.** Raw lineage accepts traversal paths and invalid kinds; mutated `Attachment` values whose `name` differs from the map key are silently relabeled when `name` is stripped. Validate workspace path, kind grammar, and key/name equality before emitting the three-field projection. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:155)
tests/core/rendering/test_registry_matrix.py:520:    The frozen ordering is alias -> canonical -> override: a missing canonical
tests/core/rendering/test_contracts.py:5:from dataclasses import FrozenInstanceError, replace
tests/core/rendering/test_contracts.py:992:def test_contracts_are_frozen() -> None:
tests/core/rendering/test_contracts.py:994:    with pytest.raises(FrozenInstanceError):

codex
The three targeted reviews converge on two substantive gaps—lineage normalization and regex end anchoring—and one separate provenance attachment bypass. I’m doing a final cross-contract sweep now so the issue list is complete rather than drip-feeding another round.
2026-08-12T02:09:22.733237Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:09:22.733293Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:09:22.733299Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git show 086d692:tests/core/rendering/test_contracts.py | nl -ba | sed -n '715,740p'; git blame -L 718,735 tests/core/rendering/test_contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   715	    a missing key is a structural protocol failure."""
   716	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   717	    """Every capability resolution requires the complete evidence set;
   718	    a missing key is a structural protocol failure."""
   719	    cases = (
   720	        (_planner(), PlannerResolution.from_dict),
   721	        (_finalizer(), FinalizerResolution.from_dict),
   722	        (_renderer(), RendererResolution.from_dict),
   723	    )
   724	    for obj, parser in cases:
   725	        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
   726	            broken = obj.to_dict()
   727	            del broken[missing]
   728	            with pytest.raises(ValueError, match="missing required fields"):
   729	                parser(broken)
   730	
   731	
   732	def test_provenance_emits_hashed_artifact_lineage() -> None:
   733	    """Provenance records per-artifact sha256 and attachment hashes, not
   734	    just profiles — so replay can verify rendered outputs byte-for-byte."""
   735	    artifact = VideoArtifact(
   736	        path="outputs/visual.mp4",
   737	        profile=_profile(),
   738	        sha256=SHA_B,
   739	        duration_frames=48,
   740	        audio=AudioOwnership.RENDERED,
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
04767bfb (POM 2026-08-12 02:49:29 +0200 718)     assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
04767bfb (POM 2026-08-12 02:49:29 +0200 719)     assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
04767bfb (POM 2026-08-12 02:49:29 +0200 720)     assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
808030e1 (POM 2026-08-12 03:06:56 +0200 723) def test_resolution_records_require_all_seven_evidence_keys() -> None:
808030e1 (POM 2026-08-12 03:06:56 +0200 724)     """Every capability resolution requires the complete evidence set;
808030e1 (POM 2026-08-12 03:06:56 +0200 725)     a missing key is a structural protocol failure."""
808030e1 (POM 2026-08-12 03:06:56 +0200 726) def test_resolution_records_require_all_seven_evidence_keys() -> None:
808030e1 (POM 2026-08-12 03:06:56 +0200 727)     """Every capability resolution requires the complete evidence set;
808030e1 (POM 2026-08-12 03:06:56 +0200 728)     a missing key is a structural protocol failure."""
808030e1 (POM 2026-08-12 03:06:56 +0200 729)     cases = (
808030e1 (POM 2026-08-12 03:06:56 +0200 730)         (_planner(), PlannerResolution.from_dict),
808030e1 (POM 2026-08-12 03:06:56 +0200 731)         (_finalizer(), FinalizerResolution.from_dict),
808030e1 (POM 2026-08-12 03:06:56 +0200 732)         (_renderer(), RendererResolution.from_dict),
808030e1 (POM 2026-08-12 03:06:56 +0200 733)     )
808030e1 (POM 2026-08-12 03:06:56 +0200 734)     for obj, parser in cases:
808030e1 (POM 2026-08-12 03:06:56 +0200 735)         for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import copy,json
from pathlib import Path
import jsonschema
from astrid.core.rendering import RenderPlan
x=json.loads(Path(\"tests/core/rendering/fixtures/v1/plan.json\").read_text()); x[\"reasons\"]={\"0\\n\":\"why\"}; s=json.loads(Path(\"astrid/core/rendering/schemas/v1/plan.json\").read_text()); print(\"schema\",jsonschema.Draft7Validator(s).is_valid(x));
try: RenderPlan.from_dict(x); print(\"dto\",True)
except Exception as e: print(\"dto\",False,type(e).__name__,e)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 165ms:
schema True
dto False RendererProtocolError malformed render plan: plan reasons must contain exactly one entry per segment, keyed by zero-based index

collab: Wait
collab: Wait
collab: Wait
collab: Wait
codex
1. **Per-segment lineage remains unbound and cardinality is bypassable.** Ordered artifacts are collapsed into an unordered path map. `[A(x), B(y)]` and `[B(y), A(x)]` serialize identically, so no artifact is associated with a specific segment. For two segments, `[A(x), A′(x), B(y)]` silently overwrites one `x` and passes. [provenance.py:116](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:116) [contracts.py:1713](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1713)

2. **Provenance still bypasses artifact/attachment contracts.** Raw artifact keys are string-coerced but never workspace-path validated, so `"../escape.mp4"` and absolute paths pass; `_artifact_lineage_from_mapping(..., key=...)` never uses `key`. Existing `Attachment` values in the top-level attachment map and `RenderProfile` values in lineage are emitted without reconstruction, allowing invalid fields injected via `object.__setattr__`. Duplicate attachment names across segment artifacts also pass despite the finalization invariant. [provenance.py:54](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:54) [provenance.py:91](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:91) [provenance.py:195](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:195) [contracts.py:1723](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1723)

3. **Schema/DTO parity still fails at terminal LF.** Patterns ending in `$` schema-accept values such as `"acme.example\n"`, a 64-hex digest plus `"\n"`, `"video.mp4\n"`, `"alpha\n"`, and reason key `"0\n"` while DTO `fullmatch`/exact-key validation rejects them. This affects qualified IDs, hashes, portable names, attachment kinds, and plan indices across the schemas. Conversely, workspace paths such as `"dir/\n"` are DTO-valid but schema-invalid. [request.json:30](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:30) [plan.json:104](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:104) [result.json:18](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:18) [finalize.json:65](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:65)
tokens used
378,101
1. **Per-segment lineage remains unbound and cardinality is bypassable.** Ordered artifacts are collapsed into an unordered path map. `[A(x), B(y)]` and `[B(y), A(x)]` serialize identically, so no artifact is associated with a specific segment. For two segments, `[A(x), A′(x), B(y)]` silently overwrites one `x` and passes. [provenance.py:116](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:116) [contracts.py:1713](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1713)

2. **Provenance still bypasses artifact/attachment contracts.** Raw artifact keys are string-coerced but never workspace-path validated, so `"../escape.mp4"` and absolute paths pass; `_artifact_lineage_from_mapping(..., key=...)` never uses `key`. Existing `Attachment` values in the top-level attachment map and `RenderProfile` values in lineage are emitted without reconstruction, allowing invalid fields injected via `object.__setattr__`. Duplicate attachment names across segment artifacts also pass despite the finalization invariant. [provenance.py:54](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:54) [provenance.py:91](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:91) [provenance.py:195](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:195) [contracts.py:1723](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1723)

3. **Schema/DTO parity still fails at terminal LF.** Patterns ending in `$` schema-accept values such as `"acme.example\n"`, a 64-hex digest plus `"\n"`, `"video.mp4\n"`, `"alpha\n"`, and reason key `"0\n"` while DTO `fullmatch`/exact-key validation rejects them. This affects qualified IDs, hashes, portable names, attachment kinds, and plan indices across the schemas. Conversely, workspace paths such as `"dir/\n"` are DTO-valid but schema-invalid. [request.json:30](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:30) [plan.json:104](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:104) [result.json:18](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:18) [finalize.json:65](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:65)

exec
/bin/zsh -lc "rg -n \"artifact_profiles|artifactProfiles|per-segment|path-keyed|segment artifacts|lineage\" astrid/core/rendering/provenance.py tests/core/rendering docs/contracts/render-backend-v1.md .oracle/tasklist.md | sed -n '1,280p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/tasklist.md:57:- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
astrid/core/rendering/provenance.py:95:    lineage: Mapping[str, Any],
astrid/core/rendering/provenance.py:98:    """Reject attachment names repeated across segment artifacts."""
astrid/core/rendering/provenance.py:99:    for name in (lineage.get("attachments") or {}):
astrid/core/rendering/provenance.py:102:                f"duplicate attachment name {name!r} across segment artifacts"
astrid/core/rendering/provenance.py:107:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:119:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:122:                lineage = _artifact_lineage(profile)
astrid/core/rendering/provenance.py:124:                lineage = _artifact_lineage_from_mapping(profile, key=path)
astrid/core/rendering/provenance.py:127:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:128:                    "hashed lineage record {profile, sha256, attachments}; "
astrid/core/rendering/provenance.py:131:            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
astrid/core/rendering/provenance.py:132:            result[path] = lineage
astrid/core/rendering/provenance.py:137:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:142:        lineage: list[dict[str, Any]] = []
astrid/core/rendering/provenance.py:148:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:149:                    "so lineage records stay path-keyed"
astrid/core/rendering/provenance.py:153:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:157:            record = _artifact_lineage(profile)
astrid/core/rendering/provenance.py:159:            lineage.append(record)
astrid/core/rendering/provenance.py:161:            if len(lineage) != len(segments):
astrid/core/rendering/provenance.py:163:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:164:                    f"per segment: expected {len(segments)}, got {len(lineage)}"
astrid/core/rendering/provenance.py:166:        return lineage
astrid/core/rendering/provenance.py:167:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:170:def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
astrid/core/rendering/provenance.py:175:        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
astrid/core/rendering/provenance.py:179:            f"artifact lineage is missing required fields: {', '.join(missing)}"
astrid/core/rendering/provenance.py:182:        raise ValueError("artifact lineage sha256 is required and must not be null")
astrid/core/rendering/provenance.py:184:        raise TypeError("artifact lineage sha256 must be a string")
astrid/core/rendering/provenance.py:189:        raise ValueError("artifact lineage attachments must be an object (may be empty)")
astrid/core/rendering/provenance.py:191:        raise TypeError("artifact lineage attachments must be an object")
astrid/core/rendering/provenance.py:238:def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
astrid/core/rendering/provenance.py:239:    """One hashed artifact lineage record: profile, sha256, attachments."""
astrid/core/rendering/provenance.py:240:    return _artifact_lineage_from_mapping(
astrid/core/rendering/provenance.py:280:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:290:    replay lineage come exclusively from the validated ``RenderPlan`` so a
astrid/core/rendering/provenance.py:331:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:332:            artifact_profiles,
docs/contracts/render-backend-v1.md:395:by two segment artifacts. After invocation, it verifies that the final video's
docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
docs/contracts/render-backend-v1.md:479:hashed lineage entry PER SEGMENT, each keyed by a workspace-relative output
docs/contracts/render-backend-v1.md:482:Sequence form preserves segment order (a path-keyed list) and rejects
docs/contracts/render-backend-v1.md:486:and attachment names must be unique ACROSS all segment artifacts. Profile-only
tests/core/rendering/test_contracts.py:552:def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
tests/core/rendering/test_contracts.py:697:        artifact_profiles={
tests/core/rendering/test_contracts.py:742:def test_provenance_emits_hashed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:766:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:773:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:774:    assert lineage["sha256"] == SHA_B
tests/core/rendering/test_contracts.py:775:    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
tests/core/rendering/test_contracts.py:776:    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
tests/core/rendering/test_contracts.py:811:def test_provenance_rejects_spoofed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:812:    """Artifact lineage must carry a real sha256; profile-only entries and
tests/core/rendering/test_contracts.py:825:    with pytest.raises(TypeError, match="hashed lineage"):
tests/core/rendering/test_contracts.py:827:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:833:            artifact_profiles={
tests/core/rendering/test_contracts.py:841:            artifact_profiles={
tests/core/rendering/test_contracts.py:853:            artifact_profiles={
tests/core/rendering/test_contracts.py:862:    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
tests/core/rendering/test_contracts.py:868:            artifact_profiles={
tests/core/rendering/test_contracts.py:880:            artifact_profiles={
tests/core/rendering/test_contracts.py:894:            artifact_profiles={
tests/core/rendering/test_contracts.py:910:            artifact_profiles={
tests/core/rendering/test_contracts.py:931:            artifact_profiles={
tests/core/rendering/test_contracts.py:952:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:960:            artifact_profiles=[

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '450,500p'; nl -ba tests/core/rendering/test_contracts.py | sed -n '520,990p'; nl -ba astrid/core/rendering/provenance.py | sed -n '1,370p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   450	   atomically write the hashed provenance sidecar as the commit marker.
   451	9. Remove owned temporary state on success; retain only an explicitly
   452	   requested workdir or failure replay bundle.
   453	
   454	Backend commands never create or own Astrid `run.json` ledgers. The facade or
   455	calling capability owns run attachment. Invocation workspaces, localized
   456	assets, props, generated fragments, servers, subprocess groups, and staging
   457	directories have one host owner and are cleaned on success, failure, timeout,
   458	and interruption. Cleanup must not follow an unvalidated path or delete
   459	unrelated prior output. A crash can leave an orphan video, but never a sidecar
   460	claiming an incomplete artifact; the sidecar is the publication commit marker.
   461	
   462	## Provenance ownership and v1 compatibility
   463	
   464	Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
   465	
   466	`schema_version`, `engine`, `output`, `timeline`, `assets_registry`,
   467	`request_digest`, `requested_policy`, `planner`, `segments`, `segments_v2`,
   468	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
   469	`attachments`, and `backend_fragments`.
   470	
   471	`request_digest`, `requested_policy`, `planner`, every segment's nested
   472	`renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
   473	assembler accepts no parallel singular renderer identity. The nested records
   474	have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
   475	distinct source pack, manifest, alias/override, support, and input-hash evidence
   476	for every renderer invocation. Planner and finalizer records carry the same
   477	alias/override/trust/support evidence as renderer records. Rendered artifacts
   478	are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
   479	hashed lineage entry PER SEGMENT, each keyed by a workspace-relative output
   480	path with exactly `{profile, sha256, attachments}` and a validated 64-hex
   481	string `sha256` on the artifact and every attachment `{path, kind, sha256}`.
   482	Sequence form preserves segment order (a path-keyed list) and rejects
   483	duplicate paths; mapping form requires path keys to equal the artifact's own
   484	path. Attachment paths must be workspace-relative, kinds must match
   485	`[a-z][a-z0-9-]*`, attachment map keys must equal the attachment's own name,
   486	and attachment names must be unique ACROSS all segment artifacts. Profile-only
   487	entries, null/malformed hashes, unknown or missing fields, path escapes,
   488	invalid kinds, duplicate paths, duplicate attachment names, and cardinality
   489	mismatches are all rejected; all Attachment and RenderProfile values are
   490	reconstructed through their DTO validators. Replay can verify rendered outputs
   491	byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
   492	
   493	`engine` is only the legacy request projection. The `segments` key keeps the
   494	V1-compatible flat projection: one `{engine, from, to}` entry per segment,
   495	derived from `renderer.id` and the validated integer `FrameWindow` at its
   496	rational FPS — exactly the shape legacy consumers read. The additive
   497	`segments_v2` key carries the complete normalized v2 segment records
   498	(`window`, `renderer` resolution, `input_hashes`); it never overwrites or
   499	reshapes a V1 key. When the v1 `segment_provenance` top-level projection
   500	applies, core passes it through VERBATIM from the caller's compatibility
   520	
   521	def _compatibility() -> dict[str, Any]:
   522	    return {
   523	        "project_dir": "/workspace/remotion",
   524	        "composition_id": "TimelineComposition",
   525	        "active_pack_order": [],
   526	        "active_theme": None,
   527	        "registry_hash": SHA_B,
   528	        "registry_state": {},
   529	        "resolved_effect_ids": [],
   530	        "resolved_effects": [],
   531	        "source_pack_ids": [],
   532	        "element_roots": [],
   533	        "staged_asset_ids": [],
   534	        "staged_asset_root": None,
   535	        "segment_provenance": [{"engine": "spoofed", "from": -1, "to": -1}],
   536	        "ffmpeg_specialization": None,
   537	        "audio_reactive_colour": None,
   538	    }
   539	
   540	
   541	def test_provenance_requires_always_emitted_v1_projection() -> None:
   542	    with pytest.raises(ValueError, match="v1_compatibility is required"):
   543	        assemble_provenance_v2(
   544	            engine="remotion",
   545	            output="/workspace/video.mp4",
   546	            timeline="/workspace/timeline.json",
   547	            assets_registry=None,
   548	            plan=_plan(),
   549	        )
   550	
   551	
   552	def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
   553	    compatibility = _compatibility()
   554	    assert set(compatibility) == set(PROVENANCE_V1_COMPATIBILITY_KEYS)
   555	    plan = _plan(
   556	        segments=[
   557	            _segment(0, 24, backend="acme.first", digest=SHA_B),
   558	            _segment(24, 48, backend="other.second", digest=SHA_C),
   559	        ]
   560	    )
   561	    kwargs = {
   562	        "engine": "hybrid",
   563	        "output": "/workspace/out/video.mp4",
   564	        "timeline": "/workspace/timeline.json",
   565	        "assets_registry": "/workspace/assets.json",
   566	        "plan": plan,
   567	        "artifact_profiles": {
   568	            "outputs/video.mp4": {
   569	                "profile": _profile(),
   570	                "sha256": SHA_B,
   571	                "attachments": {},
   572	            },
   573	            "outputs/segment2.mp4": {
   574	                "profile": _profile(),
   575	                "sha256": SHA_C,
   576	                "attachments": {},
   577	            },
   578	        },
   579	        "audio_ownership": AudioOwnership.RENDERED,
   580	        "normalization": [],
   581	        "attachments": {},
   582	        "backend_fragments": {"acme.first": {"vendor": "Acme"}},
   583	        "v1_compatibility": compatibility,
   584	    }
   585	    payload = assemble_provenance_v2(**kwargs)
   586	    assert payload["schema_version"] == 2
   587	    assert payload["request_digest"] == SHA_D
   588	    assert payload["requested_policy"] == "hybrid"
   589	    assert payload["planner"] == _planner().to_dict()
   590	    assert [segment["renderer"]["id"] for segment in payload["segments_v2"]] == [
   591	        "acme.first",
   592	        "other.second",
   593	    ]
   594	    assert payload["segments_v2"] == [segment.to_dict() for segment in plan.segments]
   595	    assert [set(segment) for segment in payload["segments_v2"]] == [
   596	        {"window", "renderer", "input_hashes"},
   597	        {"window", "renderer", "input_hashes"},
   598	    ]
   599	    # V1-compatible projections are preserved unchanged.
   600	    assert payload["segments"] == [
   601	        {"engine": "first", "from": 0.0, "to": 1.0},
   602	        {"engine": "second", "from": 1.0, "to": 2.0},
   603	    ]
   604	    # segment_provenance passes through from the v1 compatibility projection
   605	    # verbatim — the host never rewrites it.
   606	    assert payload["segment_provenance"] == compatibility["segment_provenance"]
   607	    assert payload["finalizer"] == _finalizer().to_dict()
   608	    assert payload["composition_id"] == "TimelineComposition"
   609	
   610	    sidecar = tmp_path / "video.mp4.provenance.json"
   611	    assert write_provenance_v2(sidecar, **kwargs) == payload
   612	    assert sidecar.read_text(encoding="utf-8").endswith("\n")
   613	
   614	
   615	def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None:
   616	    plan = _plan().to_dict()
   617	    plan["segments"][0]["engine"] = "spoofed"
   618	    with pytest.raises(RendererProtocolError):
   619	        assemble_provenance_v2(
   620	            engine="hybrid",
   621	            output="out/video.mp4",
   622	            timeline="timeline.json",
   623	            assets_registry=None,
   624	            plan=plan,
   625	            v1_compatibility=_compatibility(),
   626	        )
   627	
   628	
   629	def test_compute_request_digest_is_canonical_and_stable() -> None:
   630	    from astrid.core.rendering.contracts import compute_request_digest
   631	
   632	    a = {"backend_config": {"acme.visual": {"quality": "preview"}}, "schema_version": 1}
   633	    b = {"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}}}
   634	    assert compute_request_digest(a) == compute_request_digest(b)
   635	    digest = compute_request_digest(a)
   636	    assert isinstance(digest, str)
   637	    assert len(digest) == 64
   638	    assert compute_request_digest({**a, "metadata": {"x": "y"}}) != digest
   639	    assert compute_request_digest({"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}, "other.key": {}}}) != digest
   640	
   641	
   642	def test_shared_sha256_helper_is_used_for_input_hashes(tmp_path: Path) -> None:
   643	    input_path = tmp_path / "timeline.json"
   644	    input_path.write_text("abc", encoding="utf-8")
   645	    hashes = hash_input_files({"timeline": input_path})
   646	    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
   647	
   648	
   649	def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
   650	    """Non-default alias/override/trust/support evidence must survive the
   651	    plan wire round-trip and the final provenance sidecar."""
   652	    planner = replace(
   653	        _planner(),
   654	        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
   655	        override={"from": "acme.hybrid-planner", "to": "rendering.legacy_hybrid"},
   656	        support_decision=_support("rendering.legacy_hybrid"),
   657	    )
   658	    renderer = replace(
   659	        _renderer("acme.visual"),
   660	        alias_chain=["visual", "acme.visual"],
   661	        override={"from": "acme.visual-2", "to": "acme.visual"},
   662	        trust_eligibility={"eligible": True, "method": "source-tree"},
   663	    )
   664	    finalizer = replace(
   665	        _finalizer(),
   666	        alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
   667	        override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
   668	        trust_eligibility={"eligible": True, "method": "source-tree"},
   669	        support_decision=_support("rendering.ffmpeg-finalizer"),
   670	    )
   671	    plan = _plan(
   672	        planner=planner,
   673	        segments=[
   674	            _segment(0, 24, renderer=renderer),
   675	            _segment(24, 48),
   676	        ],
   677	        finalizer=finalizer,
   678	    )
   679	
   680	    # Wire round-trip
   681	    reparsed = RenderPlan.from_dict(plan.to_dict())
   682	    assert reparsed.planner.alias_chain == planner.alias_chain
   683	    assert reparsed.planner.override == planner.override
   684	    assert reparsed.planner.support_decision is not None
   685	    assert reparsed.segments[0].renderer.trust_eligibility == renderer.trust_eligibility
   686	    assert reparsed.finalizer.alias_chain == finalizer.alias_chain
   687	    assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
   688	    assert reparsed.finalizer.support_decision is not None
   689	
   690	    # Provenance sidecar carries the same evidence
   691	    payload = assemble_provenance_v2(
   692	        engine="hybrid",
   693	        output="/workspace/out/video.mp4",
   694	        timeline="/workspace/timeline.json",
   695	        assets_registry=None,
   696	        plan=plan,
   697	        artifact_profiles={
   698	            "outputs/visual.mp4": {
   699	                "profile": _profile(),
   700	                "sha256": SHA_B,
   701	                "attachments": {},
   702	            },
   703	            "outputs/segment2.mp4": {
   704	                "profile": _profile(),
   705	                "sha256": SHA_C,
   706	                "attachments": {},
   707	            }
   708	        },
   709	        audio_ownership="rendered",
   710	        normalization=[],
   711	        attachments={},
   712	        backend_fragments={},
   713	        v1_compatibility=_compatibility(),
   714	    )
   715	    assert payload["planner"]["alias_chain"] == planner.alias_chain
   716	    assert payload["planner"]["override"] == planner.override
   717	    assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
   718	    assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
   719	    assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
   720	    assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
   721	
   722	
   723	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   724	    """Every capability resolution requires the complete evidence set;
   725	    a missing key is a structural protocol failure."""
   726	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   727	    """Every capability resolution requires the complete evidence set;
   728	    a missing key is a structural protocol failure."""
   729	    cases = (
   730	        (_planner(), PlannerResolution.from_dict),
   731	        (_finalizer(), FinalizerResolution.from_dict),
   732	        (_renderer(), RendererResolution.from_dict),
   733	    )
   734	    for obj, parser in cases:
   735	        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
   736	            broken = obj.to_dict()
   737	            del broken[missing]
   738	            with pytest.raises(ValueError, match="missing required fields"):
   739	                parser(broken)
   740	
   741	
   742	def test_provenance_emits_hashed_artifact_lineage() -> None:
   743	    """Provenance records per-artifact sha256 and attachment hashes, not
   744	    just profiles — so replay can verify rendered outputs byte-for-byte."""
   745	    artifact = VideoArtifact(
   746	        path="outputs/visual.mp4",
   747	        profile=_profile(),
   748	        sha256=SHA_B,
   749	        duration_frames=48,
   750	        audio=AudioOwnership.RENDERED,
   751	        attachments={
   752	            "alpha": Attachment(
   753	                name="alpha",
   754	                path="outputs/alpha.mp4",
   755	                kind="alpha",
   756	                sha256=SHA_C,
   757	            )
   758	        },
   759	    )
   760	    payload = assemble_provenance_v2(
   761	        engine="hybrid",
   762	        output="/workspace/out/video.mp4",
   763	        timeline="/workspace/timeline.json",
   764	        assets_registry=None,
   765	        plan=_plan(),
   766	        artifact_profiles={"outputs/visual.mp4": artifact},
   767	        audio_ownership="rendered",
   768	        normalization=[],
   769	        attachments={},
   770	        backend_fragments={},
   771	        v1_compatibility=_compatibility(),
   772	    )
   773	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
   774	    assert lineage["sha256"] == SHA_B
   775	    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
   776	    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
   777	
   778	
   779	def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
   780	    """support_decision.backend must equal the resolution id for planner and
   781	    finalizer, exactly as it does for renderer."""
   782	    cases = (
   783	        (_planner, "planner"),
   784	        (_finalizer, "finalizer"),
   785	        (_renderer, "renderer"),
   786	    )
   787	    for factory, label in cases:
   788	        payload = factory().to_dict()
   789	        payload["support_decision"] = _support("other.backend").to_dict()
   790	        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
   791	            type(factory()).from_dict(payload)
   792	
   793	
   794	def test_resolutions_reject_incoherent_override_records() -> None:
   795	    """Override records must be {from, to} with to == resolution id."""
   796	    cases = (
   797	        (_planner, "planner"),
   798	        (_finalizer, "finalizer"),
   799	        (_renderer, "renderer"),
   800	    )
   801	    for factory, label in cases:
   802	        payload = factory().to_dict()
   803	        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
   804	        with pytest.raises(ValueError, match=f"{label} override 'to'"):
   805	            type(factory()).from_dict(payload)
   806	        payload["override"] = {"only": "one"}
   807	        with pytest.raises(ValueError, match=f"{label} override"):
   808	            type(factory()).from_dict(payload)
   809	
   810	
   811	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   812	    """Artifact lineage must carry a real sha256; profile-only entries and
   813	    null hashes are rejected rather than stringified."""
   814	    base = dict(
   815	        engine="hybrid",
   816	        output="/workspace/out/video.mp4",
   817	        timeline="/workspace/timeline.json",
   818	        assets_registry=None,
   819	        audio_ownership="rendered",
   820	        normalization=[],
   821	        attachments={},
   822	        backend_fragments={},
   823	        v1_compatibility=_compatibility(),
   824	    )
   825	    with pytest.raises(TypeError, match="hashed lineage"):
   826	        assemble_provenance_v2(
   827	            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
   828	        )
   829	    with pytest.raises(ValueError, match="sha256"):
   830	        assemble_provenance_v2(
   831	            **base,
   832	            plan=_plan(),
   833	            artifact_profiles={
   834	                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
   835	            },
   836	        )
   837	    with pytest.raises(ValueError, match="sha256"):
   838	        assemble_provenance_v2(
   839	            **base,
   840	            plan=_plan(),
   841	            artifact_profiles={
   842	                "out/v.mp4": {
   843	                    "profile": _profile(),
   844	                    "sha256": "not-a-hash",
   845	                    "attachments": {},
   846	                }
   847	            },
   848	        )
   849	    with pytest.raises(ValueError, match="unknown fields"):
   850	        assemble_provenance_v2(
   851	            **base,
   852	            plan=_plan(),
   853	            artifact_profiles={
   854	                "out/v.mp4": {
   855	                    "profile": _profile(),
   856	                    "sha256": SHA_B,
   857	                    "attachments": {},
   858	                    "spoof": 1,
   859	                }
   860	            },
   861	        )
   862	    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
   863	        assemble_provenance_v2(
   864	            **base,
   865	            plan=_plan(
   866	                segments=[_segment(0, 24), _segment(24, 48)]
   867	            ),
   868	            artifact_profiles={
   869	                "out/v.mp4": {
   870	                    "profile": _profile(),
   871	                    "sha256": SHA_B,
   872	                    "attachments": {},
   873	                }
   874	            },
   875	        )
   876	    with pytest.raises(ValueError, match="attachment path"):
   877	        assemble_provenance_v2(
   878	            **base,
   879	            plan=_plan(),
   880	            artifact_profiles={
   881	                "out/v.mp4": {
   882	                    "profile": _profile(),
   883	                    "sha256": SHA_B,
   884	                    "attachments": {
   885	                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
   886	                    },
   887	                },
   888	            },
   889	        )
   890	    with pytest.raises(ValueError, match="attachment kind"):
   891	        assemble_provenance_v2(
   892	            **base,
   893	            plan=_plan(),
   894	            artifact_profiles={
   895	                "out/v.mp4": {
   896	                    "profile": _profile(),
   897	                    "sha256": SHA_B,
   898	                    "attachments": {
   899	                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
   900	                    },
   901	                },
   902	            },
   903	        )
   904	
   905	
   906	    with pytest.raises(ValueError, match="must equal Attachment.name"):
   907	        assemble_provenance_v2(
   908	            **base,
   909	            plan=_plan(),
   910	            artifact_profiles={
   911	                "out/v.mp4": {
   912	                    "profile": _profile(),
   913	                    "sha256": SHA_B,
   914	                    "attachments": {
   915	                        "different_key": Attachment(
   916	                            name="alpha",
   917	                            path="outputs/alpha.mp4",
   918	                            kind="alpha",
   919	                            sha256=SHA_C,
   920	                        )
   921	                    },
   922	                }
   923	            },
   924	        )
   925	    with pytest.raises(ValueError, match="duplicate attachment name"):
   926	        assemble_provenance_v2(
   927	            **base,
   928	            plan=_plan(
   929	                segments=[_segment(0, 24), _segment(24, 48)]
   930	            ),
   931	            artifact_profiles={
   932	                "out/v1.mp4": {
   933	                    "profile": _profile(),
   934	                    "sha256": SHA_B,
   935	                    "attachments": {
   936	                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
   937	                    },
   938	                },
   939	                "out/v2.mp4": {
   940	                    "profile": _profile(),
   941	                    "sha256": SHA_D,
   942	                    "attachments": {
   943	                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
   944	                    },
   945	                },
   946	            },
   947	        )
   948	    with pytest.raises(ValueError, match="workspace path"):
   949	        assemble_provenance_v2(
   950	            **base,
   951	            plan=_plan(),
   952	            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
   953	        )
   954	    with pytest.raises(ValueError, match="duplicate path"):
   955	        assemble_provenance_v2(
   956	            **base,
   957	            plan=_plan(
   958	                segments=[_segment(0, 24), _segment(24, 48)]
   959	            ),
   960	            artifact_profiles=[
   961	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
   962	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
   963	            ],
   964	        )
   965	
   966	
   967	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
   968	    plan = _plan(
   969	        segments=[_segment(12, 24), _segment(24, 36)],
   970	        total_frames=48,
   971	        window=_window(12, 36),
   972	    )
   973	    assert plan.total_frames == 48
   974	    assert plan.window == _window(12, 36)
   975	
   976	
   977	@pytest.mark.parametrize(
   978	    ("segments", "total_frames", "match"),
   979	    [
   980	        ([_segment(1, 48)], 48, "gap"),
   981	        ([_segment(0, 47)], 48, "trailing gap"),
   982	        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
   983	        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
   984	        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
   985	    ],
   986	)
   987	def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
   988	    segments: list[RenderSegment],
   989	    total_frames: int,
   990	    match: str,
     1	"""Core-owned provenance v2 assembly for timeline renders."""
     2	
     3	from __future__ import annotations
     4	
     5	from collections.abc import Mapping, Sequence
     6	from pathlib import Path
     7	from typing import Any
     8	
     9	from astrid.core.foundation.atomic_io import write_json_atomic
    10	from astrid.core.foundation.hash import sha256_file
    11	
    12	from .contracts import (
    13	    PROVENANCE_V1_ALWAYS_KEYS,
    14	    PROVENANCE_V1_COMPATIBILITY_KEYS,
    15	    PROVENANCE_V2_CORE_KEYS,
    16	    Attachment,
    17	    AudioOwnership,
    18	    RenderPlan,
    19	    RenderProfile,
    20	    RenderSegment,
    21	    VideoArtifact,
    22	    _json_safe_mapping,
    23	    _require_sha256,
    24	    _require_string,
    25	    _require_workspace_relative_path,
    26	    _validate_backend_fragments,
    27	)
    28	
    29	
    30	PROVENANCE_SCHEMA_VERSION = 2
    31	CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)
    32	
    33	
    34	def validate_backend_fragments(
    35	    fragments: Mapping[str, Mapping[str, Any]] | None,
    36	) -> dict[str, dict[str, Any]]:
    37	    """Validate namespaces and reject top-level core-key collisions."""
    38	
    39	    return _validate_backend_fragments(fragments or {})
    40	
    41	
    42	def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
    43	    if value is None:
    44	        return None
    45	    if isinstance(value, AudioOwnership):
    46	        return value.value
    47	    try:
    48	        return AudioOwnership(value).value
    49	    except (TypeError, ValueError) as exc:
    50	        raise ValueError(
    51	            "audio_ownership must be rendered, passthrough, none, or null"
    52	        ) from exc
    53	
    54	
    55	def _normalize_attachments(
    56	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None,
    57	) -> dict[str, Any]:
    58	    result: dict[str, Any] = {}
    59	    for raw_name, raw_attachment in (attachments or {}).items():
    60	        name = _require_string(raw_name, "attachment key")
    61	        attachment = (
    62	            Attachment.from_dict(
    63	                {
    64	                    "name": raw_attachment.name,
    65	                    "path": raw_attachment.path,
    66	                    "kind": raw_attachment.kind,
    67	                    "sha256": raw_attachment.sha256,
    68	                }
    69	            )
    70	            if isinstance(raw_attachment, Attachment)
    71	            else Attachment.from_dict(raw_attachment)
    72	        )
    73	        if attachment.name != name:
    74	            raise ValueError(
    75	                f"attachment key {name!r} must match attachment.name {attachment.name!r}"
    76	            )
    77	        if name in result:
    78	            raise ValueError(f"duplicate attachment name: {name}")
    79	        result[name] = attachment.to_dict()
    80	    return result
    81	
    82	
    83	def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
    84	    """Derive one v1 segment projection from an authoritative v2 segment."""
    85	
    86	    numerator, denominator = segment.window.fps_rational
    87	    return {
    88	        "engine": segment.renderer.id.rsplit(".", 1)[-1],
    89	        "from": segment.window.start_frame * denominator / numerator,
    90	        "to": segment.window.end_frame * denominator / numerator,
    91	    }
    92	
    93	
    94	def _reject_duplicate_attachment_names(
    95	    lineage: Mapping[str, Any],
    96	    seen: set[str],
    97	) -> None:
    98	    """Reject attachment names repeated across segment artifacts."""
    99	    for name in (lineage.get("attachments") or {}):
   100	        if name in seen:
   101	            raise ValueError(
   102	                f"duplicate attachment name {name!r} across segment artifacts"
   103	            )
   104	        seen.add(name)
   105	
   106	
   107	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
   108	    if value is None:
   109	        value = {}
   110	    if isinstance(value, Mapping):
   111	        result: dict[str, Any] = {}
   112	        seen_attachment_names: set[str] = set()
   113	        for key, profile in value.items():
   114	            path = _require_string(str(key), "artifact key")
   115	            path = _require_workspace_relative_path(path, "artifact key")
   116	            if isinstance(profile, VideoArtifact):
   117	                if path != profile.path:
   118	                    raise ValueError(
   119	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
   120	                        f"{profile.path!r}"
   121	                    )
   122	                lineage = _artifact_lineage(profile)
   123	            elif isinstance(profile, Mapping):
   124	                lineage = _artifact_lineage_from_mapping(profile, key=path)
   125	            else:
   126	                raise TypeError(
   127	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   128	                    "hashed lineage record {profile, sha256, attachments}; "
   129	                    "profile-only entries carry no output hash"
   130	                )
   131	            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
   132	            result[path] = lineage
   133	        # A positive plan must record exactly one hashed artifact per segment.
   134	        if segments:
   135	            if len(result) != len(segments):
   136	                raise ValueError(
   137	                    f"artifact_profiles must record exactly one hashed lineage entry "
   138	                    f"per segment: expected {len(segments)}, got {len(result)}"
   139	                )
   140	        return result
   141	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   142	        lineage: list[dict[str, Any]] = []
   143	        seen_paths: set[str] = set()
   144	        seen_attachment_names: set[str] = set()
   145	        for profile in value:
   146	            if not isinstance(profile, VideoArtifact):
   147	                raise TypeError(
   148	                    "sequence artifact_profiles entries must be VideoArtifacts "
   149	                    "so lineage records stay path-keyed"
   150	                )
   151	            if profile.path in seen_paths:
   152	                raise ValueError(
   153	                    f"artifact_profiles sequence contains duplicate path "
   154	                    f"{profile.path!r}"
   155	                )
   156	            seen_paths.add(profile.path)
   157	            record = _artifact_lineage(profile)
   158	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   159	            lineage.append(record)
   160	        if segments:
   161	            if len(lineage) != len(segments):
   162	                raise ValueError(
   163	                    f"artifact_profiles must record exactly one hashed lineage entry "
   164	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   165	                )
   166	        return lineage
   167	    raise TypeError("artifact_profiles must be an object or array")
   168	
   169	
   170	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   171	    raw_keys = set(raw)
   172	    allowed = {"profile", "sha256", "attachments"}
   173	    unknown = sorted(raw_keys - allowed)
   174	    if unknown:
   175	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   176	    missing = sorted(allowed - raw_keys)
   177	    if missing:
   178	        raise ValueError(
   179	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   180	        )
   181	    if raw["sha256"] is None:
   182	        raise ValueError("artifact lineage sha256 is required and must not be null")
   183	    if not isinstance(raw["sha256"], str):
   184	        raise TypeError("artifact lineage sha256 must be a string")
   185	    profile = raw["profile"]
   186	    attachments: dict[str, Any] = {}
   187	    raw_attachments = raw["attachments"]
   188	    if raw_attachments is None:
   189	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   190	    if not isinstance(raw_attachments, Mapping):
   191	        raise TypeError("artifact lineage attachments must be an object")
   192	    for name, att in raw_attachments.items():
   193	        name = _require_string(name, "attachment name")
   194	        if isinstance(att, Attachment):
   195	            if att.name != name:
   196	                raise ValueError(
   197	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   198	                )
   199	            att = {
   200	                "path": att.path,
   201	                "kind": att.kind,
   202	                "sha256": att.sha256,
   203	            }
   204	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   205	        if att_unknown:
   206	            raise ValueError(
   207	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   208	            )
   209	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   210	        if att_missing:
   211	            raise ValueError(
   212	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   213	            )
   214	        if not isinstance(att["sha256"], str):
   215	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   216	        # Validate through the Attachment DTO so workspace-path containment and
   217	        # kind grammar are enforced uniformly for raw and dataclass values.
   218	        validated = Attachment(
   219	            name=name,
   220	            path=att["path"],
   221	            kind=att["kind"],
   222	            sha256=att["sha256"],
   223	        )
   224	        attachments[name] = {
   225	            "path": validated.path,
   226	            "kind": validated.kind,
   227	            "sha256": validated.sha256,
   228	        }
   229	    return {
   230	        "profile": RenderProfile.from_dict(
   231	            _json_safe_mapping(profile, label="artifact profile")
   232	        ).to_dict(),
   233	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   234	        "attachments": attachments,
   235	    }
   236	
   237	
   238	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   239	    """One hashed artifact lineage record: profile, sha256, attachments."""
   240	    return _artifact_lineage_from_mapping(
   241	        {
   242	            "profile": artifact.profile,
   243	            "sha256": artifact.sha256,
   244	            "attachments": artifact.attachments,
   245	        },
   246	        key=artifact.path,
   247	    )
   248	
   249	
   250	def _normalize_v1_compatibility(
   251	    fields: Mapping[str, Any] | None,
   252	) -> dict[str, Any]:
   253	    if fields is None:
   254	        raise ValueError(
   255	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   256	        )
   257	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   258	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   259	    if unknown:
   260	        raise ValueError(
   261	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   262	            + ", ".join(unknown)
   263	        )
   264	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   265	    if missing:
   266	        raise ValueError(
   267	            "v1 compatibility projection is missing always-emitted fields: "
   268	            + ", ".join(missing)
   269	        )
   270	    return compatibility
   271	
   272	
   273	def assemble_provenance_v2(
   274	    *,
   275	    engine: str,
   276	    output: str | Path,
   277	    timeline: str | Path,
   278	    assets_registry: str | Path | None,
   279	    plan: RenderPlan | Mapping[str, Any],
   280	    artifact_profiles: Any = None,
   281	    audio_ownership: AudioOwnership | str | None = None,
   282	    normalization: Sequence[str] = (),
   283	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   284	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   285	    v1_compatibility: Mapping[str, Any] | None = None,
   286	) -> dict[str, Any]:
   287	    """Assemble additive provenance v2 with protected ownership boundaries.
   288	
   289	    ``engine`` is intentionally the legacy request projection. Routing and
   290	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   291	    hybrid invocation cannot collapse multiple renderer identities. Optional
   292	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   293	    any v2 core field.
   294	    """
   295	
   296	    legacy_engine = _require_string(engine, "engine")
   297	    output_path = _require_string(str(output), "output")
   298	    timeline_path = _require_string(str(timeline), "timeline")
   299	    assets_path = None if assets_registry is None else _require_string(
   300	        str(assets_registry), "assets_registry"
   301	    )
   302	    normalized_plan = (
   303	        plan
   304	        if isinstance(plan, RenderPlan)
   305	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   306	    )
   307	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   308	    legacy_segments = [
   309	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   310	    ]
   311	    normalized_normalization = [
   312	        _require_string(item, f"normalization[{index}]")
   313	        for index, item in enumerate(normalization)
   314	    ]
   315	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   316	
   317	    payload: dict[str, Any] = {
   318	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   319	        "engine": legacy_engine,
   320	        "output": output_path,
   321	        "timeline": timeline_path,
   322	        "assets_registry": assets_path,
   323	        "request_digest": normalized_plan.request_digest,
   324	        "requested_policy": normalized_plan.requested_policy,
   325	        "planner": normalized_plan.planner.to_dict(),
   326	        # V1-compatible segment projection: flat {engine, from, to} entries,
   327	        # exactly the shape legacy consumers read from `segments`.
   328	        "segments": legacy_segments,
   329	        # Additive normalized v2 segment records; never overwrite v1 fields.
   330	        "segments_v2": normalized_segments,
   331	        "artifact_profiles": _normalize_artifact_profiles(
   332	            artifact_profiles,
   333	            segments=normalized_plan.segments,
   334	        ),
   335	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   336	        "normalization": normalized_normalization,
   337	        "finalizer": normalized_plan.finalizer.to_dict(),
   338	        "attachments": _normalize_attachments(attachments),
   339	        "backend_fragments": validate_backend_fragments(backend_fragments),
   340	    }
   341	    payload.update(compatibility)
   342	    return _json_safe_mapping(payload, label="provenance")
   343	
   344	
   345	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   346	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   347	
   348	    return assemble_provenance_v2(**kwargs)
   349	
   350	
   351	def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
   352	    """Assemble and atomically write a provenance v2 sidecar."""
   353	
   354	    payload = assemble_provenance_v2(**kwargs)
   355	    write_json_atomic(path, payload)
   356	    return payload
   357	
   358	
   359	def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
   360	    """Return stable SHA-256 input hashes using Astrid's shared helper."""
   361	
   362	    return {
   363	        _require_string(name, "input hash name"): sha256_file(Path(path))
   364	        for name, path in paths.items()
   365	    }
   366	
   367	
   368	def digest_manifest(path: str | Path) -> str:
   369	    """Return the SHA-256 digest used to pin one static manifest."""
   370	

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '1,250p'; nl -ba astrid/core/rendering/contracts.py | sed -n '480,730p'; nl -ba astrid/core/rendering/contracts.py | sed -n '1660,1775p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""Language-neutral rendering protocol data transfer objects.
     2	
     3	The JSON Schemas in :mod:`astrid.core.rendering.schemas.v1` are the wire
     4	source of truth.  These frozen dataclasses are the small Python projection of
     5	that contract; they deliberately contain no discovery, transport, or backend
     6	execution behavior.
     7	"""
     8	
     9	from __future__ import annotations
    10	
    11	import math
    12	import re
    13	from collections.abc import Mapping, Sequence
    14	from dataclasses import dataclass, field, fields, is_dataclass
    15	from enum import Enum
    16	from pathlib import Path, PurePosixPath
    17	from typing import Any, ClassVar, Literal, NoReturn, TypeAlias
    18	
    19	from astrid.core.foundation.hash import sha256_file
    20	from astrid.core.io.cas import canonical_json_digest
    21	
    22	
    23	SCHEMA_VERSION = 1
    24	
    25	BackendConfig: TypeAlias = dict[str, dict[str, Any]]
    26	RendererErrorKind: TypeAlias = Literal[
    27	    "protocol",
    28	    "unsupported",
    29	    "binary_missing",
    30	    "timeout",
    31	    "interrupted",
    32	    "invalid_artifact",
    33	    "internal",
    34	]
    35	
    36	_QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
    37	_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
    38	_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    39	_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
    40	
    41	RENDER_RESULT_CORE_KEYS = frozenset(
    42	    {
    43	        "schema_version",
    44	        "video",
    45	        "backend_fragments",
    46	        "audio_ownership",
    47	        "normalization",
    48	        "logs",
    49	        "metadata",
    50	    }
    51	)
    52	
    53	PROVENANCE_V2_CORE_KEYS = frozenset(
    54	    {
    55	        "schema_version",
    56	        "engine",
    57	        "output",
    58	        "timeline",
    59	        "assets_registry",
    60	        "request_digest",
    61	        "requested_policy",
    62	        "planner",
    63	        "segments",
    64	        "segments_v2",
    65	        "artifact_profiles",
    66	        "audio_ownership",
    67	        "normalization",
    68	        "finalizer",
    69	        "attachments",
    70	        "backend_fragments",
    71	    }
    72	)
    73	
    74	PROVENANCE_V1_COMPATIBILITY_KEYS = frozenset(
    75	    {
    76	        "project_dir",
    77	        "composition_id",
    78	        "active_pack_order",
    79	        "active_theme",
    80	        "registry_hash",
    81	        "registry_state",
    82	        "resolved_effect_ids",
    83	        "resolved_effects",
    84	        "source_pack_ids",
    85	        "element_roots",
    86	        "staged_asset_ids",
    87	        "staged_asset_root",
    88	        "segment_provenance",
    89	        "ffmpeg_specialization",
    90	        "audio_reactive_colour",
    91	    }
    92	)
    93	
    94	PROVENANCE_V1_ALWAYS_KEYS = frozenset(
    95	    {
    96	        "project_dir",
    97	        "composition_id",
    98	        "active_pack_order",
    99	        "active_theme",
   100	        "registry_hash",
   101	        "registry_state",
   102	        "resolved_effect_ids",
   103	        "resolved_effects",
   104	        "source_pack_ids",
   105	        "element_roots",
   106	        "staged_asset_ids",
   107	        "staged_asset_root",
   108	    }
   109	)
   110	
   111	_RETIRED_PROVENANCE_V2_KEYS = frozenset(
   112	    {
   113	        "resolved_backend",
   114	        "source_pack",
   115	        "alias_chain",
   116	        "override",
   117	        "trust_eligibility",
   118	        "manifest_digest",
   119	        "support_decision",
   120	        "input_hashes",
   121	    }
   122	)
   123	
   124	RESERVED_BACKEND_FRAGMENT_KEYS = frozenset(
   125	    RENDER_RESULT_CORE_KEYS
   126	    | PROVENANCE_V2_CORE_KEYS
   127	    | PROVENANCE_V1_COMPATIBILITY_KEYS
   128	    | _RETIRED_PROVENANCE_V2_KEYS
   129	)
   130	
   131	
   132	def _json_safe(value: Any) -> Any:
   133	    """Return a recursively JSON-safe copy, rejecting non-wire values."""
   134	
   135	    if isinstance(value, Enum):
   136	        return _json_safe(value.value)
   137	    if value is None or isinstance(value, (str, bool, int)):
   138	        return value
   139	    if isinstance(value, float):
   140	        if not math.isfinite(value):
   141	            raise TypeError("JSON numbers must be finite")
   142	        return value
   143	    if isinstance(value, Path):
   144	        return str(value)
   145	    to_dict = getattr(value, "to_dict", None)
   146	    if callable(to_dict):
   147	        return _json_safe(to_dict())
   148	    if isinstance(value, Mapping):
   149	        return {str(key): _json_safe(item) for key, item in value.items()}
   150	    if isinstance(value, (list, tuple)):
   151	        return [_json_safe(item) for item in value]
   152	    if is_dataclass(value):
   153	        return {
   154	            dataclass_field.name: _json_safe(getattr(value, dataclass_field.name))
   155	            for dataclass_field in fields(value)
   156	        }
   157	    raise TypeError(f"value of type {type(value).__name__} is not JSON-safe")
   158	
   159	
   160	def _json_safe_mapping(value: Any, *, label: str = "value") -> dict[str, Any]:
   161	    payload = _json_safe(value)
   162	    if not isinstance(payload, dict):
   163	        raise TypeError(f"{label} must be a JSON object")
   164	    return payload
   165	
   166	
   167	def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
   168	    if not isinstance(value, Mapping):
   169	        raise TypeError(f"{label} must be an object")
   170	    return value
   171	
   172	
   173	def _validate_object_keys(
   174	    payload: Mapping[str, Any],
   175	    *,
   176	    required: set[str] | frozenset[str],
   177	    allowed: set[str] | frozenset[str],
   178	    label: str,
   179	) -> None:
   180	    missing = sorted(required - payload.keys())
   181	    if missing:
   182	        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
   183	    unknown = sorted(payload.keys() - allowed)
   184	    if unknown:
   185	        raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
   186	
   187	
   188	def _require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
   189	    if type(value) is not int:
   190	        raise TypeError(f"{label} must be an integer")
   191	    if minimum is not None and value < minimum:
   192	        raise ValueError(f"{label} must be >= {minimum}")
   193	    return value
   194	
   195	
   196	def _require_number(value: Any, label: str, *, exclusive_minimum: float | None = None) -> float:
   197	    if isinstance(value, bool) or not isinstance(value, (int, float)):
   198	        raise TypeError(f"{label} must be a number")
   199	    number = float(value)
   200	    if not math.isfinite(number):
   201	        raise ValueError(f"{label} must be finite")
   202	    if exclusive_minimum is not None and number <= exclusive_minimum:
   203	        raise ValueError(f"{label} must be > {exclusive_minimum:g}")
   204	    return number
   205	
   206	
   207	def compute_request_digest(request: Mapping[str, Any]) -> str:
   208	    """Deterministic SHA-256 of a canonical, JSON-normalized render request.
   209	
   210	    Uses sorted keys and compact separators so the digest is stable across
   211	    Python versions and dict insertion orders; replay verifies the request
   212	    against this digest.
   213	    """
   214	    return canonical_json_digest(_json_safe_mapping(request, label="render request"))
   215	
   216	
   217	def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
   218	    if not isinstance(value, str):
   219	        raise TypeError(f"{label} must be a string")
   220	    if "\x00" in value:
   221	        raise ValueError(f"{label} must not contain NUL")
   222	    if not allow_empty and not value.strip():
   223	        raise ValueError(f"{label} must not be empty")
   224	    return value
   225	
   226	
   227	def _require_optional_string(value: Any, label: str) -> str | None:
   228	    if value is None:
   229	        return None
   230	    return _require_string(value, label)
   231	
   232	
   233	def _require_qualified_id(value: Any, label: str) -> str:
   234	    result = _require_string(value, label)
   235	    if not _QUALIFIED_ID_RE.fullmatch(result):
   236	        raise ValueError(
   237	            f"{label} must be a qualified id '<pack>.<name>' whose dot-separated "
   238	            "segments use lowercase letters, digits, and hyphens"
   239	        )
   240	    return result
   241	
   242	
   243	def _require_sha256(value: Any, label: str) -> str:
   244	    result = _require_string(value, label)
   245	    if not _SHA256_RE.fullmatch(result):
   246	        raise ValueError(f"{label} must be a lowercase 64-character SHA-256 digest")
   247	    return result
   248	
   249	
   250	def _require_override(value: Any, *, capability_id: str, label: str) -> dict[str, Any]:
   480	            self.audio_sample_rate,
   481	            self.audio_channel_layout,
   482	        )
   483	        if any(value is not None for value in audio_values) and not all(
   484	            value is not None for value in audio_values
   485	        ):
   486	            raise ValueError(
   487	                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
   488	                "provided together or all omitted"
   489	            )
   490	        if self.audio_codec is not None:
   491	            object.__setattr__(self, "audio_codec", _require_string(self.audio_codec, "audio_codec"))
   492	            object.__setattr__(
   493	                self,
   494	                "audio_sample_rate",
   495	                _require_int(self.audio_sample_rate, "audio_sample_rate", minimum=1),
   496	            )
   497	            object.__setattr__(
   498	                self,
   499	                "audio_channel_layout",
   500	                _require_string(self.audio_channel_layout, "audio_channel_layout"),
   501	            )
   502	        object.__setattr__(
   503	            self,
   504	            "duration_tolerance",
   505	            _require_int(self.duration_tolerance, "duration_tolerance", minimum=0),
   506	        )
   507	
   508	    @property
   509	    def has_audio(self) -> bool:
   510	        return self.audio_codec is not None
   511	
   512	    def to_dict(self) -> dict[str, Any]:
   513	        return _json_safe_mapping(
   514	            {
   515	                "width": self.width,
   516	                "height": self.height,
   517	                "fps_rational": self.fps_rational,
   518	                "time_base": self.time_base,
   519	                "container": self.container,
   520	                "video_codec": self.video_codec,
   521	                "video_profile": self.video_profile,
   522	                "video_level": self.video_level,
   523	                "pixel_format": self.pixel_format,
   524	                "audio_codec": self.audio_codec,
   525	                "audio_sample_rate": self.audio_sample_rate,
   526	                "audio_channel_layout": self.audio_channel_layout,
   527	                "duration_tolerance": self.duration_tolerance,
   528	            }
   529	        )
   530	
   531	    @classmethod
   532	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
   533	        data = _require_mapping(payload, "render profile")
   534	        required = {
   535	            "width",
   536	            "height",
   537	            "fps_rational",
   538	            "time_base",
   539	            "container",
   540	            "video_codec",
   541	            "video_profile",
   542	            "video_level",
   543	            "pixel_format",
   544	            "duration_tolerance",
   545	        }
   546	        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
   547	        _validate_object_keys(data, required=required, allowed=allowed, label="render profile")
   548	        return cls(
   549	            width=data["width"],
   550	            height=data["height"],
   551	            fps_rational=data["fps_rational"],
   552	            time_base=data["time_base"],
   553	            container=data["container"],
   554	            video_codec=data["video_codec"],
   555	            video_profile=data["video_profile"],
   556	            video_level=data["video_level"],
   557	            pixel_format=data["pixel_format"],
   558	            audio_codec=data.get("audio_codec"),
   559	            audio_sample_rate=data.get("audio_sample_rate"),
   560	            audio_channel_layout=data.get("audio_channel_layout"),
   561	            duration_tolerance=data["duration_tolerance"],
   562	        )
   563	
   564	
   565	def _validate_artifact_audio(
   566	    profile: RenderProfile,
   567	    ownership: AudioOwnership | None,
   568	    label: str,
   569	) -> None:
   570	    """Keep probed media audio and ownership semantically aligned.
   571	
   572	    ``rendered`` means the artifact itself contains audio and therefore has a
   573	    populated audio profile. ``passthrough`` and ``none`` describe visual-only
   574	    artifacts; the former asks the host/finalizer to supply canonical audio.
   575	    """
   576	
   577	    if profile.has_audio:
   578	        if ownership is not AudioOwnership.RENDERED:
   579	            raise ValueError(f"{label} with an audio profile must declare audio='rendered'")
   580	    elif ownership is AudioOwnership.RENDERED:
   581	        raise ValueError(f"{label} with audio='rendered' must have an audio profile")
   582	
   583	
   584	@dataclass(frozen=True)
   585	class Attachment:
   586	    """A named, opaque artifact preserved alongside the primary video."""
   587	
   588	    name: str
   589	    path: str
   590	    kind: str
   591	    sha256: str
   592	
   593	    def __post_init__(self) -> None:
   594	        name = _require_string(self.name, "attachment name")
   595	        if not _OUTPUT_NAME_RE.fullmatch(name):
   596	            raise ValueError("attachment name must be a portable basename")
   597	        kind = _require_string(self.kind, "attachment kind")
   598	        if not _KIND_RE.fullmatch(kind):
   599	            raise ValueError("attachment kind must be a lowercase hyphenated token")
   600	        object.__setattr__(self, "name", name)
   601	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))
   602	        object.__setattr__(self, "kind", kind)
   603	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "attachment sha256"))
   604	
   605	    def to_dict(self) -> dict[str, Any]:
   606	        return _json_safe_mapping(
   607	            {"name": self.name, "path": self.path, "kind": self.kind, "sha256": self.sha256}
   608	        )
   609	
   610	    @classmethod
   611	    def from_dict(cls, payload: Mapping[str, Any]) -> Attachment:
   612	        data = _require_mapping(payload, "attachment")
   613	        required = {"name", "path", "kind", "sha256"}
   614	        _validate_object_keys(data, required=required, allowed=required, label="attachment")
   615	        return cls(
   616	            name=data["name"],
   617	            path=data["path"],
   618	            kind=data["kind"],
   619	            sha256=data["sha256"],
   620	        )
   621	
   622	    @classmethod
   623	    def from_file(
   624	        cls,
   625	        *,
   626	        name: str,
   627	        path: str | Path,
   628	        kind: str,
   629	        workspace_root: str | Path,
   630	    ) -> Attachment:
   631	        relative, resolved = _relative_file_path(path, workspace_root, "attachment path")
   632	        return cls(name=name, path=relative, kind=kind, sha256=sha256_file(resolved))
   633	
   634	
   635	def _coerce_attachment_mapping(value: Any, label: str) -> dict[str, Attachment]:
   636	    mapping = _require_mapping(value, label)
   637	    result: dict[str, Attachment] = {}
   638	    seen_names: set[str] = set()
   639	    for raw_key, raw_attachment in mapping.items():
   640	        key = _require_string(raw_key, f"{label} key")
   641	        attachment = (
   642	            raw_attachment
   643	            if isinstance(raw_attachment, Attachment)
   644	            else Attachment.from_dict(_require_mapping(raw_attachment, f"{label}[{key!r}]"))
   645	        )
   646	        if attachment.name != key:
   647	            raise ValueError(
   648	                f"{label} key {key!r} must match attachment.name {attachment.name!r}"
   649	            )
   650	        if attachment.name in seen_names:
   651	            raise ValueError(f"duplicate attachment name: {attachment.name}")
   652	        seen_names.add(attachment.name)
   653	        result[key] = attachment
   654	    return result
   655	
   656	
   657	@dataclass(frozen=True)
   658	class VideoArtifact:
   659	    """The required primary video produced by a renderer or finalizer."""
   660	
   661	    path: str
   662	    profile: RenderProfile
   663	    sha256: str
   664	    duration_frames: int
   665	    audio: AudioOwnership | None = None
   666	    attachments: dict[str, Attachment] = field(default_factory=dict)
   667	
   668	    def __post_init__(self) -> None:
   669	        profile = (
   670	            self.profile
   671	            if isinstance(self.profile, RenderProfile)
   672	            else RenderProfile.from_dict(_require_mapping(self.profile, "video profile"))
   673	        )
   674	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
   675	        object.__setattr__(self, "profile", profile)
   676	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
   677	        object.__setattr__(
   678	            self,
   679	            "duration_frames",
   680	            _require_int(self.duration_frames, "duration_frames", minimum=1),
   681	        )
   682	        audio = _coerce_audio_ownership(self.audio, "video audio", nullable=True)
   683	        _validate_artifact_audio(profile, audio, "video artifact")
   684	        object.__setattr__(self, "audio", audio)
   685	        object.__setattr__(
   686	            self,
   687	            "attachments",
   688	            _coerce_attachment_mapping(self.attachments, "video attachments"),
   689	        )
   690	
   691	    def to_dict(self) -> dict[str, Any]:
   692	        return _json_safe_mapping(
   693	            {
   694	                "path": self.path,
   695	                "profile": self.profile,
   696	                "sha256": self.sha256,
   697	                "duration_frames": self.duration_frames,
   698	                "audio": self.audio,
   699	                "attachments": self.attachments,
   700	            }
   701	        )
   702	
   703	    @classmethod
   704	    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
   705	        data = _require_mapping(payload, "video artifact")
   706	        required = {"path", "profile", "sha256", "duration_frames"}
   707	        allowed = required | {"audio", "attachments"}
   708	        _validate_object_keys(data, required=required, allowed=allowed, label="video artifact")
   709	        return cls(
   710	            path=data["path"],
   711	            profile=RenderProfile.from_dict(data["profile"]),
   712	            sha256=data["sha256"],
   713	            duration_frames=data["duration_frames"],
   714	            audio=data.get("audio"),
   715	            attachments=data.get("attachments", {}),
   716	        )
   717	
   718	    @classmethod
   719	    def from_file(
   720	        cls,
   721	        *,
   722	        path: str | Path,
   723	        workspace_root: str | Path,
   724	        profile: RenderProfile,
   725	        duration_frames: int,
   726	        audio: AudioOwnership | None = None,
   727	        attachments: Mapping[str, Attachment] | None = None,
   728	    ) -> VideoArtifact:
   729	        relative, resolved = _relative_file_path(path, workspace_root, "video path")
   730	        return cls(
  1660	            }
  1661	        )
  1662	
  1663	    @classmethod
  1664	    def from_dict(cls, payload: Mapping[str, Any]) -> RendererError:
  1665	        try:
  1666	            data = _require_mapping(payload, "renderer error")
  1667	            required = {
  1668	                "schema_version",
  1669	                "kind",
  1670	                "backend",
  1671	                "message",
  1672	                "recovery_command",
  1673	                "details",
  1674	            }
  1675	            _validate_object_keys(data, required=required, allowed=required, label="renderer error")
  1676	            return cls(
  1677	                schema_version=data["schema_version"],
  1678	                kind=data["kind"],
  1679	                backend=data["backend"],
  1680	                message=data["message"],
  1681	                recovery_command=data["recovery_command"],
  1682	                details=data["details"],
  1683	            )
  1684	        except Exception as exc:
  1685	            from .errors import RendererException
  1686	
  1687	            if isinstance(exc, RendererException):
  1688	                raise
  1689	            _protocol_failure(
  1690	                f"malformed renderer error: {exc}",
  1691	                details={"error_type": type(exc).__name__},
  1692	            )
  1693	
  1694	
  1695	@dataclass(frozen=True)
  1696	class FinalizeRequest:
  1697	    """Wire request consumed by the ``finalize`` operation."""
  1698	
  1699	    schema_version: int
  1700	    plan: RenderPlan
  1701	    artifacts: list[VideoArtifact]
  1702	    output_name: str
  1703	    backend_config: BackendConfig = field(default_factory=dict)
  1704	    metadata: dict[str, str] = field(default_factory=dict)
  1705	
  1706	    def __post_init__(self) -> None:
  1707	        version = _require_schema_version(self.schema_version, "finalize request")
  1708	        plan = (
  1709	            self.plan
  1710	            if isinstance(self.plan, RenderPlan)
  1711	            else RenderPlan.from_dict(_require_mapping(self.plan, "plan"))
  1712	        )
  1713	        if isinstance(self.artifacts, (str, bytes)) or not isinstance(self.artifacts, Sequence):
  1714	            raise TypeError("artifacts must be an array")
  1715	        artifacts = [
  1716	            artifact
  1717	            if isinstance(artifact, VideoArtifact)
  1718	            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
  1719	            for index, artifact in enumerate(self.artifacts)
  1720	        ]
  1721	        if len(artifacts) != len(plan.segments):
  1722	            raise ValueError("finalize artifacts must correspond one-for-one with plan segments")
  1723	        if plan.total_frames == 0:
  1724	            raise ValueError("an empty render plan must not be finalized")
  1725	        attachment_names: set[str] = set()
  1726	        for index, artifact in enumerate(artifacts):
  1727	            duplicates = sorted(attachment_names & set(artifact.attachments))
  1728	            if duplicates:
  1729	                raise ValueError(
  1730	                    "duplicate attachment names across segment artifacts at "
  1731	                    f"artifacts[{index}]: {', '.join(duplicates)}"
  1732	                )
  1733	            attachment_names.update(artifact.attachments)
  1734	        output_name = _require_string(self.output_name, "output_name")
  1735	        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
  1736	            raise ValueError("output_name must be a portable basename without path separators")
  1737	        object.__setattr__(self, "schema_version", version)
  1738	        object.__setattr__(self, "plan", plan)
  1739	        object.__setattr__(self, "artifacts", artifacts)
  1740	        object.__setattr__(self, "output_name", output_name)
  1741	        backend_config = _coerce_namespaced_backend_config(
  1742	            self.backend_config,
  1743	            "backend_config",
  1744	        )
  1745	        unexpected_config = sorted(set(backend_config) - {plan.finalizer.id})
  1746	        if unexpected_config:
  1747	            raise ValueError(
  1748	                "finalize backend_config may contain only the selected finalizer namespace "
  1749	                f"{plan.finalizer.id!r}"
  1750	            )
  1751	        object.__setattr__(self, "backend_config", backend_config)
  1752	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
  1753	
  1754	    @property
  1755	    def expected_attachments(self) -> dict[str, Attachment]:
  1756	        """Return the globally unique attachments a finalizer must preserve."""
  1757	
  1758	        return {
  1759	            name: attachment
  1760	            for artifact in self.artifacts
  1761	            for name, attachment in artifact.attachments.items()
  1762	        }
  1763	
  1764	    def validate_final_result(
  1765	        self,
  1766	        result: RenderResult | Mapping[str, Any],
  1767	    ) -> RenderResult:
  1768	        """Validate attachment preservation on a standalone finalizer response.
  1769	
  1770	        Finalizers may add new attachments, but every input attachment must be
  1771	        present under the same name with the exact same descriptor and digest.
  1772	        """
  1773	
  1774	        final_result = (
  1775	            result

codex
One concrete concern has surfaced in my own pass: the sequence output preserves order but appears to drop each artifact path entirely, despite the documented “path-keyed list” shape. I’m checking that alongside whether the new `\Z` schema anchors remain valid for non-Python JSON Schema consumers.
exec
/bin/zsh -lc 'for f in astrid/core/rendering/schemas/v1/*.json; do echo "$f"; jq -r '"'.. | objects | .pattern? // empty' \""'$f" | nl -ba; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/finalize.json
     1	^[A-Za-z0-9][A-Za-z0-9._-]*\Z
     2	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     3	^[0-9a-f]{64}\Z
     4	^(?![A-Za-z]:)(?!/)(?!\.{1,2}(?:/|$))(?![\s\S]*?/\.{1,2}(?:/|$))(?![\s\S]*//)(?![\s\S]*\\)(?![\s\S]*\u0000)(?![\s\S]*/$)[\s\S]*\S[\s\S]*\Z
     5	^[A-Za-z0-9][A-Za-z0-9._-]*\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    12	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    13	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    14	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    15	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    16	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    17	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    18	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    19	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    20	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    21	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    22	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    23	^(0|[1-9][0-9]*)\Z
    24	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    25	^[a-z][a-z0-9-]*\Z
    26	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    27	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    28	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/finalizer-manifest.json
     1	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     2	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     3	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     4	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     5	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/plan.json
     1	^(0|[1-9][0-9]*)\Z
     2	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     3	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     4	^[0-9a-f]{64}\Z
     5	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    12	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    13	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    14	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    15	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    16	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    17	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    18	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    19	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    20	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    21	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/planner-manifest.json
     1	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     2	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     3	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     4	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     5	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/renderer-manifest.json
     1	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     2	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     3	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     4	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     5	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    12	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    13	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/request.json
     1	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     2	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     3	^[A-Za-z0-9][A-Za-z0-9._-]*\Z
     4	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     5	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    12	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    13	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    14	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    15	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    16	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/result.json
     1	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z
     2	^[0-9a-f]{64}\Z
     3	^(?![A-Za-z]:)(?!/)(?!\.{1,2}(?:/|$))(?![\s\S]*?/\.{1,2}(?:/|$))(?![\s\S]*//)(?![\s\S]*\\)(?![\s\S]*\u0000)(?![\s\S]*/$)[\s\S]*\S[\s\S]*\Z
     4	^[A-Za-z0-9][A-Za-z0-9._-]*\Z
     5	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     6	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     7	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     8	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     9	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    10	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    11	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    12	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    13	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    14	^[a-z][a-z0-9-]*\Z
    15	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    16	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    17	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    18	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    19	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
    20	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
astrid/core/rendering/schemas/v1/support.json
     1	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     2	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     3	^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z
     4	^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+\Z

exec
/bin/zsh -lc "node - <<'NODE'
const patterns = [
  '"'^[0-9a-f]{64}'"\\\\Z',
  '"'^[A-Za-z0-9][A-Za-z0-9._-]*'"\\\\Z',
  '"'^(?!['"\\\\s\\\\S]*\\\\u0000)[\\\\s\\\\S]*\\\\S[\\\\s\\\\S]*\\\\Z'
];
const values = ['a'.repeat(64), 'video.mp4', 'hello'];
patterns.forEach((p,i) => {
  const r = new RegExp(p);
  console.log(JSON.stringify(p), r.toString(), JSON.stringify(values[i]), r.test(values[i]), 'Z suffix', r.test(values[i]+'Z'));
});
for (const p of patterns) {
  try { new RegExp(p, 'u'); console.log('u-mode accepted', p); }
  catch (e) { console.log('u-mode rejected', p, e.name); }
}
NODE
rg -n 'ajv|json schema|ECMA-262|Draft.?7|schema source of truth|language-neutral' pyproject.toml package.json remotion/package.json docs astrid/core/rendering tests/core/rendering | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
zsh:1: can't create temp file for here document: operation not permitted
astrid/core/rendering/errors.py:14:    """Base raised exception carrying a language-neutral ``RendererError``."""
tests/core/rendering/test_schema_roundtrip.py:77:    jsonschema.Draft7Validator.check_schema(schema)
tests/core/rendering/test_schema_roundtrip.py:78:    validator = jsonschema.Draft7Validator(schema)
tests/core/rendering/test_schema_roundtrip.py:93:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:342:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:374:    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
docs/contracts/render-backend-v1.md:599:13. **The canonical interoperability boundary is language-neutral.** A

exec
/bin/zsh -lc "node -e 'const ps=[\""'^[0-9a-f]{64}'"\\\\Z\",\""'^[A-Za-z0-9][A-Za-z0-9._-]*'"\\\\Z\",\""'^(?!['"\\\\s\\\\S]*\\\\u0000)[\\\\s\\\\S]*\\\\S[\\\\s\\\\S]*\\\\Z\"],vs=[\"a\".repeat(64),\"video.mp4\",\"hello\"]; ps.forEach((p,i)=>{const r=new RegExp(p); console.log(JSON.stringify(p),r.toString(),JSON.stringify(vs[i]),r.test(vs[i]),\"Z suffix\",r.test(vs[i]+\"Z\"));}); ps.forEach(p=>{try{new RegExp(p,\"u\"); console.log(\"u-mode accepted\",p)}catch(e){console.log(\"u-mode rejected\",p,e.name)}});'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
"^[0-9a-f]{64}\\Z" /^[0-9a-f]{64}\Z/ "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" false Z suffix true
"^[A-Za-z0-9][A-Za-z0-9._-]*\\Z" /^[A-Za-z0-9][A-Za-z0-9._-]*\Z/ "video.mp4" false Z suffix true
"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z" /^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z/ "hello" false Z suffix true
u-mode rejected ^[0-9a-f]{64}\Z SyntaxError
u-mode rejected ^[A-Za-z0-9][A-Za-z0-9._-]*\Z SyntaxError
u-mode rejected ^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*\Z SyntaxError

exec
/bin/zsh -lc "git diff --unified=3 ab486f9..8418bae -- 'astrid/core/rendering/schemas/v1/*.json' | sed -n '1,1200p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 1e49ad3..f21e12d 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -38,7 +38,7 @@
     },
     "output_name": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
@@ -56,20 +56,20 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}$"
+      "pattern": "^[0-9a-f]{64}\\Z"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "portableName": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
@@ -82,7 +82,7 @@
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         {
           "type": "object"
@@ -194,12 +194,12 @@
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
@@ -207,7 +207,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
@@ -215,12 +215,12 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
@@ -228,7 +228,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
@@ -243,7 +243,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
@@ -274,7 +274,7 @@
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
@@ -283,7 +283,7 @@
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
@@ -314,7 +314,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "features": {
@@ -326,7 +326,7 @@
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "alternatives": {
@@ -345,7 +345,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         }
       }
     },
@@ -378,7 +378,7 @@
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
@@ -431,7 +431,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
@@ -478,7 +478,7 @@
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
@@ -512,7 +512,7 @@
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "renderSegment": {
@@ -583,12 +583,12 @@
         "reasons": {
           "type": "object",
           "propertyNames": {
-            "pattern": "^(0|[1-9][0-9]*)$"
+            "pattern": "^(0|[1-9][0-9]*)\\Z"
           },
           "additionalProperties": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "window": {
@@ -652,7 +652,7 @@
         },
         "kind": {
           "type": "string",
-          "pattern": "^[a-z][a-z0-9-]*$"
+          "pattern": "^[a-z][a-z0-9-]*\\Z"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
@@ -716,7 +716,7 @@
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
                   }
                 }
               }
@@ -758,11 +758,11 @@
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "overrideRecord": {
diff --git a/astrid/core/rendering/schemas/v1/finalizer-manifest.json b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
index 0525220..0bde205 100644
--- a/astrid/core/rendering/schemas/v1/finalizer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
@@ -23,12 +23,12 @@
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "protocol_version": {
       "type": "integer",
@@ -39,7 +39,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "minItems": 1
     },
@@ -64,7 +64,7 @@
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "capabilities": {
       "$ref": "#/definitions/finalizerCapabilities",
@@ -79,7 +79,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "uniqueItems": true,
       "default": []
@@ -96,12 +96,12 @@
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "default": {}
     }
@@ -110,7 +110,7 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "permissions": {
       "type": "array",
@@ -135,7 +135,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
@@ -163,12 +163,12 @@
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         }
       },
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index 47740f8..47bb576 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -50,12 +50,12 @@
     "reasons": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(0|[1-9][0-9]*)$"
+        "pattern": "^(0|[1-9][0-9]*)\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "window": {
@@ -103,18 +103,18 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}$"
+      "pattern": "^[0-9a-f]{64}\\Z"
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         {
           "type": "object"
@@ -226,12 +226,12 @@
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
@@ -239,7 +239,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
@@ -247,12 +247,12 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
@@ -260,7 +260,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
@@ -275,7 +275,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
@@ -306,7 +306,7 @@
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
@@ -315,7 +315,7 @@
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
@@ -346,7 +346,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "features": {
@@ -358,7 +358,7 @@
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "alternatives": {
@@ -377,7 +377,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         }
       }
     },
@@ -410,7 +410,7 @@
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
@@ -463,7 +463,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
@@ -510,7 +510,7 @@
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "override": {
@@ -544,7 +544,7 @@
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "renderSegment": {
diff --git a/astrid/core/rendering/schemas/v1/planner-manifest.json b/astrid/core/rendering/schemas/v1/planner-manifest.json
index 1334afe..48e0756 100644
--- a/astrid/core/rendering/schemas/v1/planner-manifest.json
+++ b/astrid/core/rendering/schemas/v1/planner-manifest.json
@@ -23,12 +23,12 @@
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "protocol_version": {
       "type": "integer",
@@ -39,7 +39,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "minItems": 1
     },
@@ -64,7 +64,7 @@
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "capabilities": {
       "$ref": "#/definitions/plannerCapabilities",
@@ -79,7 +79,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "uniqueItems": true,
       "default": []
@@ -96,12 +96,12 @@
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "default": {}
     }
@@ -110,7 +110,7 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "permissions": {
       "type": "array",
@@ -135,7 +135,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
@@ -151,12 +151,12 @@
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         }
       },
diff --git a/astrid/core/rendering/schemas/v1/renderer-manifest.json b/astrid/core/rendering/schemas/v1/renderer-manifest.json
index c079378..b6cf411 100644
--- a/astrid/core/rendering/schemas/v1/renderer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/renderer-manifest.json
@@ -23,12 +23,12 @@
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "protocol_version": {
       "type": "integer",
@@ -39,7 +39,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "minItems": 1
     },
@@ -64,7 +64,7 @@
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "capabilities": {
       "$ref": "#/definitions/rendererCapabilities",
@@ -79,7 +79,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "uniqueItems": true,
       "default": []
@@ -96,12 +96,12 @@
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "default": {}
     }
@@ -110,7 +110,7 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "permissions": {
       "type": "array",
@@ -135,7 +135,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
@@ -144,7 +144,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
@@ -157,12 +157,12 @@
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           }
         },
         "supports_full_timeline": {
@@ -176,7 +176,7 @@
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
           },
           "uniqueItems": true
         },
diff --git a/astrid/core/rendering/schemas/v1/request.json b/astrid/core/rendering/schemas/v1/request.json
index a69ff83..575f0da 100644
--- a/astrid/core/rendering/schemas/v1/request.json
+++ b/astrid/core/rendering/schemas/v1/request.json
@@ -17,7 +17,7 @@
     "timeline_path": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "assets_registry_path": {
       "type": [
@@ -25,11 +25,11 @@
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "output_name": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
@@ -101,7 +101,7 @@
             "properties": {
               "audio_codec": {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
               }
             }
           }
@@ -148,7 +148,7 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "audioOwnership": {
       "type": "string",
@@ -255,12 +255,12 @@
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
@@ -268,7 +268,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
@@ -276,12 +276,12 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
@@ -289,7 +289,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
@@ -304,7 +304,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
@@ -335,7 +335,7 @@
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
@@ -344,7 +344,7 @@
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
@@ -362,11 +362,11 @@
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     }
   },
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index e089030..8a93ef7 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -13,20 +13,20 @@
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}$"
+      "pattern": "^[0-9a-f]{64}\\Z"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
     },
     "portableName": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
       "not": {
         "enum": [
           ".",
@@ -84,12 +84,12 @@
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_profile": {
           "type": [
@@ -97,7 +97,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "video_level": {
           "type": [
@@ -105,12 +105,12 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_codec": {
           "type": [
@@ -118,7 +118,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "audio_sample_rate": {
           "type": [
@@ -133,7 +133,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "duration_tolerance": {
           "type": "integer",
@@ -164,7 +164,7 @@
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             },
             "audio_sample_rate": {
               "type": "integer",
@@ -173,7 +173,7 @@
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
             }
           }
         }
@@ -197,7 +197,7 @@
         },
         "kind": {
           "type": "string",
-          "pattern": "^[a-z][a-z0-9-]*$"
+          "pattern": "^[a-z][a-z0-9-]*\\Z"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
@@ -261,7 +261,7 @@
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
                   }
                 }
               }
@@ -353,17 +353,17 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "success": {
@@ -486,7 +486,7 @@
         "message": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "recovery_command": {
           "type": [
@@ -494,7 +494,7 @@
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
         },
         "details": {
           "type": "object"
diff --git a/astrid/core/rendering/schemas/v1/support.json b/astrid/core/rendering/schemas/v1/support.json
index af94ae5..49d7095 100644
--- a/astrid/core/rendering/schemas/v1/support.json
+++ b/astrid/core/rendering/schemas/v1/support.json
@@ -26,7 +26,7 @@
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "features": {
@@ -38,7 +38,7 @@
         ]
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
       }
     },
     "alternatives": {
@@ -57,13 +57,13 @@
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
     }
   },
   "examples": [

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '580,625p'; nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '1,120p'; nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '300,410p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   580	   not need to know how a backend is loaded or invoked.
   581	6. **Selection is deterministic and inspectable.** A render plan records the
   582	   selected backend for every segment plus the capability evidence and reason.
   583	7. **Unsupported requests fail closed by default.** Fallback occurs only when
   584	   an explicit planner policy or ordered fallback list permits it.
   585	8. **Every backend returns a validated artifact.** Finalizers consume declared
   586	   media metadata rather than assuming that arbitrary MP4 files are compatible.
   587	9. **Final assembly is explicit.** Ship an FFmpeg finalizer first, but keep
   588	   finalization behind a contract so arbitrary backends do not become secretly
   589	   coupled to inlined FFmpeg logic.
   590	10. **Compatibility precedes semantic cleanup.** Preserve current
   591	    `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the
   592	    initial rollout. A later deprecation may make explicit Remotion strict and
   593	    move opportunistic selection to `planner=auto`.
   594	11. **Provenance has core-owned keys and backend-owned fragments.** Backend
   595	    fragments cannot overwrite core identity, routing, input, segment, or
   596	    finalizer fields.
   597	12. **No concrete backend imports outside the rendering implementation.**
   598	    External callers use the capability runner or one public render service.
   599	13. **The canonical interoperability boundary is language-neutral.** A
   600	    versioned command/JSON request-result protocol is the source of truth;
   601	    Python SDK types and helpers wrap it rather than replacing it.
   602	14. **Developer complexity is progressive.** The minimum local synchronous
   603	    renderer implements one render operation. Request-sensitive support and
   604	    custom finalizers are optional layers exposed only when needed.
   605	    Asynchronous remote jobs are explicitly deferred beyond V1.
   606	15. **Astrid owns plumbing.** Core services own asset resolution, temporary
   607	    workspace allocation, output probing and normalization, audio
   608	    passthrough/muxing, hashes, core provenance, cleanup, and replay metadata.
   609	    Backend authors return media plus a namespaced provenance fragment.
   610	16. **Static capabilities are coarse discovery hints, not the final verdict.**
   611	    A request-sensitive support probe returns structured supported/unsupported
   612	    features, reasons, and alternatives.
   613	17. **Failures are replayable.** Every failed backend invocation can retain or
   614	    emit a self-contained request bundle and exact replay command without
   615	    rerunning the editorial pipeline.
   616	18. **Primary video is required; attachments are extensible.** V1 planners and
   617	    finalizers operate on a validated primary video. Optional named attachments
   618	    are preserved in results and provenance but need not be interpreted by the
   619	    default finalizer.
     1	from __future__ import annotations
     2	
     3	import json
     4	from collections.abc import Callable
     5	from copy import deepcopy
     6	from pathlib import Path
     7	from typing import Any
     8	
     9	import jsonschema
    10	import pytest
    11	
    12	from astrid.core.rendering import RenderPlan, RenderRequest, RenderResult, SupportReport
    13	from astrid.core.rendering.contracts import (
    14	    FinalizeRequest,
    15	    FinalizerManifest,
    16	    PlannerManifest,
    17	    RendererManifest,
    18	    parse_wire_result,
    19	)
    20	
    21	
    22	SCHEMA_DIR = (
    23	    Path(__file__).resolve().parents[3]
    24	    / "astrid"
    25	    / "core"
    26	    / "rendering"
    27	    / "schemas"
    28	    / "v1"
    29	)
    30	FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v1"
    31	SCHEMA_NAMES = (
    32	    "request.json",
    33	    "result.json",
    34	    "support.json",
    35	    "plan.json",
    36	    "finalize.json",
    37	    "renderer-manifest.json",
    38	    "planner-manifest.json",
    39	    "finalizer-manifest.json",
    40	)
    41	WIRE_SCHEMA_NAMES = (
    42	    "request.json",
    43	    "result.json",
    44	    "support.json",
    45	    "plan.json",
    46	    "finalize.json",
    47	)
    48	
    49	
    50	def _load_json(path: Path) -> dict[str, Any]:
    51	    return json.loads(path.read_text(encoding="utf-8"))
    52	
    53	
    54	def _load_schema(name: str) -> dict[str, Any]:
    55	    return _load_json(SCHEMA_DIR / name)
    56	
    57	
    58	def _load_fixture(name: str) -> dict[str, Any]:
    59	    return _load_json(FIXTURE_DIR / name)
    60	
    61	
    62	PARSERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    63	    "request.json": RenderRequest.from_dict,
    64	    "result.json": parse_wire_result,
    65	    "support.json": SupportReport.from_dict,
    66	    "plan.json": RenderPlan.from_dict,
    67	    "finalize.json": FinalizeRequest.from_dict,
    68	    "renderer-manifest.json": RendererManifest.from_dict,
    69	    "planner-manifest.json": PlannerManifest.from_dict,
    70	    "finalizer-manifest.json": FinalizerManifest.from_dict,
    71	}
    72	
    73	
    74	@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
    75	def test_every_schema_and_example_is_valid_and_parses(schema_name: str) -> None:
    76	    schema = _load_schema(schema_name)
    77	    jsonschema.Draft7Validator.check_schema(schema)
    78	    validator = jsonschema.Draft7Validator(schema)
    79	    examples = schema.get("examples")
    80	    assert isinstance(examples, list) and examples, f"{schema_name} must carry examples"
    81	
    82	    for example in examples:
    83	        validator.validate(example)
    84	        dto = PARSERS[schema_name](example)
    85	        round_trip = dto.to_dict()
    86	        validator.validate(round_trip)
    87	        assert round_trip == example
    88	
    89	
    90	@pytest.mark.parametrize("schema_name", WIRE_SCHEMA_NAMES)
    91	def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
    92	    payload = _load_fixture(schema_name)
    93	    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
    94	    validator.validate(payload)
    95	    assert PARSERS[schema_name](payload).to_dict() == payload
    96	
    97	
    98	def test_every_duplicated_profile_definition_is_identical() -> None:
    99	    profile_definitions = {
   100	        name: _load_schema(name)["definitions"]["renderProfile"]
   101	        for name in ("request.json", "plan.json", "result.json", "finalize.json")
   102	    }
   103	    reference = profile_definitions["request.json"]
   104	    assert all(definition == reference for definition in profile_definitions.values())
   105	
   106	
   107	def _accepted(parser: Callable[[dict[str, Any]], Any], payload: dict[str, Any]) -> bool:
   108	    try:
   109	        parser(payload)
   110	    except Exception:
   111	        return False
   112	    return True
   113	
   114	
   115	def _set(payload: dict[str, Any], path: tuple[str | int, ...], value: Any) -> dict[str, Any]:
   116	    result = deepcopy(payload)
   117	    target: Any = result
   118	    for part in path[:-1]:
   119	        target = target[part]
   120	    target[path[-1]] = value
   300	        ("boolean version", _set(base, ("schema_version",), True)),
   301	        ("unknown version", _set(base, ("schema_version",), 2)),
   302	        ("malformed protocol version", _set(base, ("protocol_version",), "1")),
   303	        ("empty command", _set(base, ("command",), [])),
   304	        ("missing required operation", _set(base, ("operations",), ["support"])),
   305	        (
   306	            "duplicate operation",
   307	            _set(base, ("operations",), [required_operation, required_operation]),
   308	        ),
   309	        ("unknown permission", _set(base, ("required_permissions",), ["root"])),
   310	        ("unknown capability", _set(base, ("capabilities",), {"unknown": True})),
   311	    ]
   312	
   313	
   314	def _with_version_adversaries(
   315	    base: dict[str, Any],
   316	    cases: list[tuple[str, dict[str, Any]]],
   317	) -> list[tuple[str, dict[str, Any]]]:
   318	    return cases + [
   319	        ("missing version", _delete(base, ("schema_version",))),
   320	        ("boolean version", _set(base, ("schema_version",), True)),
   321	        ("malformed version", _set(base, ("schema_version",), "1")),
   322	        ("unknown version", _set(base, ("schema_version",), 2)),
   323	    ]
   324	
   325	
   326	CASE_BUILDERS: dict[str, Callable[[], list[tuple[str, dict[str, Any]]]]] = {
   327	    "request.json": _request_cases,
   328	    "support.json": _support_cases,
   329	    "plan.json": _plan_cases,
   330	    "result.json": _result_cases,
   331	    "finalize.json": _finalize_cases,
   332	    "renderer-manifest.json": lambda: _manifest_cases("renderer-manifest.json", "render"),
   333	    "planner-manifest.json": lambda: _manifest_cases("planner-manifest.json", "plan"),
   334	    "finalizer-manifest.json": lambda: _manifest_cases(
   335	        "finalizer-manifest.json", "finalize"
   336	    ),
   337	}
   338	
   339	
   340	@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
   341	def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
   342	    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
   343	    parser = PARSERS[schema_name]
   344	    for label, payload in CASE_BUILDERS[schema_name]():
   345	        schema_accepts = validator.is_valid(payload)
   346	        dto_accepts = _accepted(parser, payload)
   347	        expected = label.startswith("valid ")
   348	        assert schema_accepts is expected, (
   349	            f"{schema_name} unexpected schema result for {label}: "
   350	            f"expected={expected}, actual={schema_accepts}"
   351	        )
   352	        assert dto_accepts == schema_accepts, (
   353	            f"{schema_name} parity mismatch for {label}: "
   354	            f"schema={schema_accepts}, dto={dto_accepts}"
   355	        )
   356	
   357	
   358	@pytest.mark.parametrize(
   359	    "path",
   360	    [
   361	        "../escape.mp4",
   362	        "outputs/./escape.mp4",
   363	        "outputs//escape.mp4",
   364	        "outputs/",
   365	        "/tmp/escape.mp4",
   366	        "C:escape.mp4",
   367	        r"C:\\temp\\escape.mp4",
   368	        r"dir\\escape.mp4",
   369	    ],
   370	)
   371	def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
   372	    result = _load_fixture("result.json")
   373	    result["video"]["path"] = path
   374	    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
   375	
   376	
   377	def test_python_result_type_annotation_remains_the_success_dto() -> None:
   378	    payload = _load_fixture("result.json")
   379	    parsed = parse_wire_result(payload)
   380	    assert isinstance(parsed, RenderResult)

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,jsonschema; from pathlib import Path; from astrid.core.rendering.contracts import _require_workspace_relative_path as d; s=json.loads(Path(\"astrid/core/rendering/schemas/v1/result.json\").read_text())[\"definitions\"][\"workspacePath\"]; v=jsonschema.Draft7Validator(s); xs=[\"dir/ \",\"dir/\\t\",\"dir/\\n\",\"dir/ \\n\",\" /file\",\"dir/ /file\",\"dir/\\t/file\",\"dir\\n/ /x\",\" a /b\"]; [(print(repr(x),\"schema\",v.is_valid(x),\"dto\",(lambda:None)())) for x in []];
for x in xs:
 ok=True
 try:d(x,\"x\")
 except Exception:ok=False
 print(repr(x),\"schema\",v.is_valid(x),\"dto\",ok)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 108ms:
'dir/ ' schema True dto False
'dir/\t' schema True dto False
'dir/\n' schema False dto False
'dir/ \n' schema True dto False
' /file' schema True dto False
'dir/ /file' schema True dto False
'dir/\t/file' schema True dto False
'dir\n/ /x' schema True dto False
' a /b' schema True dto True

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\"); A=ns[\"VideoArtifact\"]; p=ns[\"_profile\"](audio=False); a=A(path=\"outputs/a.mp4\",profile=p,sha256=ns[\"SHA_B\"],duration_frames=24); b=A(path=\"outputs/b.mp4\",profile=p,sha256=ns[\"SHA_C\"],duration_frames=24); kw=dict(engine=\"hybrid\",output=\"out.mp4\",timeline=\"timeline.json\",assets_registry=None,plan=ns[\"_plan\"](segments=[ns[\"_segment\"](0,24),ns[\"_segment\"](24,48)]),artifact_profiles=[a,b],v1_compatibility=ns[\"_compatibility\"]()); out=ns[\"assemble_provenance_v2\"](**kw); print(type(out[\"artifact_profiles\"]).__name__); print([sorted(x) for x in out[\"artifact_profiles\"]]); print(\"paths present\",[x.get(\"path\") for x in out[\"artifact_profiles\"]]); object.__setattr__(a,\"path\",\"../escape.mp4\"); out=ns[\"assemble_provenance_v2\"](**{**kw,\"artifact_profiles\":[a,b]}); print(\"mutated escape accepted\",[x.get(\"path\") for x in out[\"artifact_profiles\"]])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 183ms:
list
[['attachments', 'profile', 'sha256'], ['attachments', 'profile', 'sha256']]
paths present [None, None]
mutated escape accepted [None, None]

exec
/bin/zsh -lc "git diff --unified=12 ab486f9..8418bae -- docs/contracts/render-backend-v1.md tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py | sed -n '1,1100p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index dc24a65..f98e1b1 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -467,34 +467,37 @@ Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
 `request_digest`, `requested_policy`, `planner`, `segments`, `segments_v2`,
 `artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
 `attachments`, and `backend_fragments`.
 
 `request_digest`, `requested_policy`, `planner`, every segment's nested
 `renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
 assembler accepts no parallel singular renderer identity. The nested records
 have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
 distinct source pack, manifest, alias/override, support, and input-hash evidence
 for every renderer invocation. Planner and finalizer records carry the same
 alias/override/trust/support evidence as renderer records. Rendered artifacts
 are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
-hashed lineage record PER SEGMENT, each mapping a unique output path to
-exactly `{profile, sha256, attachments}` with a validated 64-hex string
-`sha256` on the artifact and every attachment `{path, kind, sha256}`.
-Attachment paths must be workspace-relative, kinds must match
-`[a-z][a-z0-9-]*`, and attachment map keys must equal the attachment's own
-name. Profile-only entries, null/malformed hashes, unknown or missing fields,
-path escapes, invalid kinds, and cardinality mismatches are all rejected.
-Sequence-form lineage requires VideoArtifacts so records stay path-keyed.
-Replay can verify rendered outputs byte-for-byte. `input_hashes` describe
-inputs only, never rendered outputs.
+hashed lineage entry PER SEGMENT, each keyed by a workspace-relative output
+path with exactly `{profile, sha256, attachments}` and a validated 64-hex
+string `sha256` on the artifact and every attachment `{path, kind, sha256}`.
+Sequence form preserves segment order (a path-keyed list) and rejects
+duplicate paths; mapping form requires path keys to equal the artifact's own
+path. Attachment paths must be workspace-relative, kinds must match
+`[a-z][a-z0-9-]*`, attachment map keys must equal the attachment's own name,
+and attachment names must be unique ACROSS all segment artifacts. Profile-only
+entries, null/malformed hashes, unknown or missing fields, path escapes,
+invalid kinds, duplicate paths, duplicate attachment names, and cardinality
+mismatches are all rejected; all Attachment and RenderProfile values are
+reconstructed through their DTO validators. Replay can verify rendered outputs
+byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
 
 `engine` is only the legacy request projection. The `segments` key keeps the
 V1-compatible flat projection: one `{engine, from, to}` entry per segment,
 derived from `renderer.id` and the validated integer `FrameWindow` at its
 rational FPS — exactly the shape legacy consumers read. The additive
 `segments_v2` key carries the complete normalized v2 segment records
 (`window`, `renderer` resolution, `input_hashes`); it never overwrites or
 reshapes a V1 key. When the v1 `segment_provenance` top-level projection
 applies, core passes it through VERBATIM from the caller's compatibility
 projection — it is never rewritten or re-derived.
 
 For the whole epic, core also preserves every current v1 top-level projection:
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 69d4327..55df8a5 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -913,24 +913,64 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
                     "sha256": SHA_B,
                     "attachments": {
                         "different_key": Attachment(
                             name="alpha",
                             path="outputs/alpha.mp4",
                             kind="alpha",
                             sha256=SHA_C,
                         )
                     },
                 }
             },
         )
+    with pytest.raises(ValueError, match="duplicate attachment name"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles={
+                "out/v1.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+                "out/v2.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_D,
+                    "attachments": {
+                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+    with pytest.raises(ValueError, match="workspace path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
+        )
+    with pytest.raises(ValueError, match="duplicate path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles=[
+                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
+                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
+            ],
+        )
 
 
 def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
     plan = _plan(
         segments=[_segment(12, 24), _segment(24, 36)],
         total_frames=48,
         window=_window(12, 36),
     )
     assert plan.total_frames == 48
     assert plan.window == _window(12, 36)
 
 
diff --git a/tests/core/rendering/test_schema_roundtrip.py b/tests/core/rendering/test_schema_roundtrip.py
index f5de62c..6bb12a3 100644
--- a/tests/core/rendering/test_schema_roundtrip.py
+++ b/tests/core/rendering/test_schema_roundtrip.py
@@ -271,24 +271,26 @@ def _finalize_cases() -> list[tuple[str, dict[str, Any]]]:
                         "name": "x.dat",
                         "path": "outputs/x.dat",
                         "kind": "project_file",
                         "sha256": "a" * 64,
                     }
                 },
             ),
         ),
         ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
                 ("partial populated audio", partial),
         ("contradictory artifact audio", _set(base, ("artifacts", 0, "audio"), "rendered")),
         ("nested plan version", _set(base, ("plan", "schema_version"), 2)),
+        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
+        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
         ("zero-frame plan", zero_plan),
     ]
     return _with_version_adversaries(base, cases)
 
 
 def _manifest_cases(
     schema_name: str,
     required_operation: str,
 ) -> list[tuple[str, dict[str, Any]]]:
     base = deepcopy(_load_schema(schema_name)["examples"][0])
     return [
         ("valid canonical", base),

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '805,970p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   805	            type(factory()).from_dict(payload)
   806	        payload["override"] = {"only": "one"}
   807	        with pytest.raises(ValueError, match=f"{label} override"):
   808	            type(factory()).from_dict(payload)
   809	
   810	
   811	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   812	    """Artifact lineage must carry a real sha256; profile-only entries and
   813	    null hashes are rejected rather than stringified."""
   814	    base = dict(
   815	        engine="hybrid",
   816	        output="/workspace/out/video.mp4",
   817	        timeline="/workspace/timeline.json",
   818	        assets_registry=None,
   819	        audio_ownership="rendered",
   820	        normalization=[],
   821	        attachments={},
   822	        backend_fragments={},
   823	        v1_compatibility=_compatibility(),
   824	    )
   825	    with pytest.raises(TypeError, match="hashed lineage"):
   826	        assemble_provenance_v2(
   827	            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
   828	        )
   829	    with pytest.raises(ValueError, match="sha256"):
   830	        assemble_provenance_v2(
   831	            **base,
   832	            plan=_plan(),
   833	            artifact_profiles={
   834	                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
   835	            },
   836	        )
   837	    with pytest.raises(ValueError, match="sha256"):
   838	        assemble_provenance_v2(
   839	            **base,
   840	            plan=_plan(),
   841	            artifact_profiles={
   842	                "out/v.mp4": {
   843	                    "profile": _profile(),
   844	                    "sha256": "not-a-hash",
   845	                    "attachments": {},
   846	                }
   847	            },
   848	        )
   849	    with pytest.raises(ValueError, match="unknown fields"):
   850	        assemble_provenance_v2(
   851	            **base,
   852	            plan=_plan(),
   853	            artifact_profiles={
   854	                "out/v.mp4": {
   855	                    "profile": _profile(),
   856	                    "sha256": SHA_B,
   857	                    "attachments": {},
   858	                    "spoof": 1,
   859	                }
   860	            },
   861	        )
   862	    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
   863	        assemble_provenance_v2(
   864	            **base,
   865	            plan=_plan(
   866	                segments=[_segment(0, 24), _segment(24, 48)]
   867	            ),
   868	            artifact_profiles={
   869	                "out/v.mp4": {
   870	                    "profile": _profile(),
   871	                    "sha256": SHA_B,
   872	                    "attachments": {},
   873	                }
   874	            },
   875	        )
   876	    with pytest.raises(ValueError, match="attachment path"):
   877	        assemble_provenance_v2(
   878	            **base,
   879	            plan=_plan(),
   880	            artifact_profiles={
   881	                "out/v.mp4": {
   882	                    "profile": _profile(),
   883	                    "sha256": SHA_B,
   884	                    "attachments": {
   885	                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
   886	                    },
   887	                },
   888	            },
   889	        )
   890	    with pytest.raises(ValueError, match="attachment kind"):
   891	        assemble_provenance_v2(
   892	            **base,
   893	            plan=_plan(),
   894	            artifact_profiles={
   895	                "out/v.mp4": {
   896	                    "profile": _profile(),
   897	                    "sha256": SHA_B,
   898	                    "attachments": {
   899	                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
   900	                    },
   901	                },
   902	            },
   903	        )
   904	
   905	
   906	    with pytest.raises(ValueError, match="must equal Attachment.name"):
   907	        assemble_provenance_v2(
   908	            **base,
   909	            plan=_plan(),
   910	            artifact_profiles={
   911	                "out/v.mp4": {
   912	                    "profile": _profile(),
   913	                    "sha256": SHA_B,
   914	                    "attachments": {
   915	                        "different_key": Attachment(
   916	                            name="alpha",
   917	                            path="outputs/alpha.mp4",
   918	                            kind="alpha",
   919	                            sha256=SHA_C,
   920	                        )
   921	                    },
   922	                }
   923	            },
   924	        )
   925	    with pytest.raises(ValueError, match="duplicate attachment name"):
   926	        assemble_provenance_v2(
   927	            **base,
   928	            plan=_plan(
   929	                segments=[_segment(0, 24), _segment(24, 48)]
   930	            ),
   931	            artifact_profiles={
   932	                "out/v1.mp4": {
   933	                    "profile": _profile(),
   934	                    "sha256": SHA_B,
   935	                    "attachments": {
   936	                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
   937	                    },
   938	                },
   939	                "out/v2.mp4": {
   940	                    "profile": _profile(),
   941	                    "sha256": SHA_D,
   942	                    "attachments": {
   943	                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
   944	                    },
   945	                },
   946	            },
   947	        )
   948	    with pytest.raises(ValueError, match="workspace path"):
   949	        assemble_provenance_v2(
   950	            **base,
   951	            plan=_plan(),
   952	            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
   953	        )
   954	    with pytest.raises(ValueError, match="duplicate path"):
   955	        assemble_provenance_v2(
   956	            **base,
   957	            plan=_plan(
   958	                segments=[_segment(0, 24), _segment(24, 48)]
   959	            ),
   960	            artifact_profiles=[
   961	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
   962	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
   963	            ],
   964	        )
   965	
   966	
   967	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
   968	    plan = _plan(
   969	        segments=[_segment(12, 24), _segment(24, 36)],
   970	        total_frames=48,

exec
/bin/zsh -lc "rg -n '\"pattern\":.*\\"'$'"' astrid/core/rendering/schemas/v1 || true; rg -n '\\\\Z' astrid/core/rendering/schemas/v1 | wc -l; rg -n '\\\\Z' astrid/core/rendering/schemas/v1 | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/finalize.json:68:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:25:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
     124
astrid/core/rendering/schemas/v1/support.json:29:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/support.json:41:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/support.json:60:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/support.json:66:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/finalize.json:41:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
astrid/core/rendering/schemas/v1/finalize.json:59:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/finalize.json:63:      "pattern": "^[0-9a-f]{64}\\Z"
astrid/core/rendering/schemas/v1/finalize.json:68:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:72:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
astrid/core/rendering/schemas/v1/finalize.json:85:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:197:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:202:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:210:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:218:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:223:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:231:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:246:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:277:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:286:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:317:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:329:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:348:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:381:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:434:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:481:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:515:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:586:            "pattern": "^(0|[1-9][0-9]*)\\Z"
astrid/core/rendering/schemas/v1/finalize.json:591:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:655:          "pattern": "^[a-z][a-z0-9-]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:719:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:761:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalize.json:765:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:147:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:160:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:165:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/renderer-manifest.json:179:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:154:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/planner-manifest.json:159:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:16:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/result.json:20:      "pattern": "^[0-9a-f]{64}\\Z"
astrid/core/rendering/schemas/v1/result.json:25:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:29:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
astrid/core/rendering/schemas/v1/result.json:87:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:92:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:100:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:108:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:113:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:121:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:136:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:167:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:176:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:200:          "pattern": "^[a-z][a-z0-9-]*\\Z"
astrid/core/rendering/schemas/v1/result.json:264:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:356:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:362:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:366:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:489:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/result.json:497:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:53:        "pattern": "^(0|[1-9][0-9]*)\\Z"
astrid/core/rendering/schemas/v1/plan.json:58:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:106:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/plan.json:110:      "pattern": "^[0-9a-f]{64}\\Z"
astrid/core/rendering/schemas/v1/plan.json:117:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:229:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:234:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:242:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:250:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:255:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:278:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:309:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:318:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:349:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:361:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:380:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:413:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:466:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:513:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/plan.json:547:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:166:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:171:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:20:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:28:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:32:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
astrid/core/rendering/schemas/v1/request.json:104:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:151:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
astrid/core/rendering/schemas/v1/request.json:258:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:271:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:279:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:284:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:292:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:307:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:338:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:347:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:365:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
astrid/core/rendering/schemas/v1/request.json:369:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"

exec
/bin/zsh -lc 'head -n 12 astrid/core/rendering/schemas/v1/request.json; head -n 12 astrid/core/rendering/schemas/v1/result.json; git show ab486f9:astrid/core/rendering/schemas/v1/request.json | head -n 12' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://astrid.local/schemas/rendering/v1/request.json",
  "title": "Astrid render request v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "timeline_path",
    "output_name"
  ],
  "properties": {
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://astrid.local/schemas/rendering/v1/result.json",
  "title": "Astrid renderer result v1",
  "oneOf": [
    {
      "$ref": "#/definitions/success"
    },
    {
      "$ref": "#/definitions/error"
    }
  ],
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://astrid.local/schemas/rendering/v1/request.json",
  "title": "Astrid render request v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "timeline_path",
    "output_name"
  ],
  "properties": {

exec
/bin/zsh -lc "nl -ba .oracle/tasklist.md | sed -n '1,78p'; nl -ba .oracle/plan.md | sed -n '1,180p' | rg -n 'language|schema|provenance|artifact|JSON|interop|Batch 1|contract'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	# Renderer Tasklist
     2	
     3	## Batch 1 — Baseline, contracts, and discovery
     4	
     5	**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
     6	
     7	**Acceptance criteria:**
     8	
     9	- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
    10	- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
    11	- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
    12	- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
    13	- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
    14	- Active trusted installs, corrupt/mismatched installs, inactive revisions, explicit-extra roots, environment denial, conflicts, cycles, and invalid override targets produce the specified inspectable/executable states.
    15	- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
    16	- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.
    17	
    18	### Tasks
    19	
    20	- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
    21	- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
    22	- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
    23	- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
    24	- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
    25	
    26	## Batch 2 — Command protocol and host-owned plumbing
    27	
    28	**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
    29	
    30	**Acceptance criteria:**
    31	
    32	- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
    33	- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
    34	- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
    35	- Asset-cache layout, URL keys, resume/drift metadata, locking, and `EphemeralSession` behavior remain unchanged behind the compatibility wrapper.
    36	- Only invocation-staged assets are served from `127.0.0.1` on port `0`; Range requests work and the server always shuts down, closes, and joins.
    37	- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
    38	- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
    39	- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
    40	
    41	### Tasks
    42	
    43	- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
    44	- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
    45	- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
    46	- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
    47	- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
    48	- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
    49	
    50	## Batch 3 — Built-in renderer and finalizer extraction
    51	
    52	**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
    53	
    54	**Acceptance criteria:**
    55	
    56	- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
    57	- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
    58	- One non-recursive cross-process lock spans registry-state reads, all registry/shim/theme-pointer writes, active-theme selection, the complete Remotion render, and the `gen-types` writer path.
    59	- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
    60	- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
    61	- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
    62	- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.
    63	
    64	### Tasks
    65	
    66	- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
    67	- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
    68	- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
    69	- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
    70	- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
    71	- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
    72	
    73	## Batch 4 — Generic routing, provenance, and hybrid planning
    74	
    75	**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.
    76	
    77	**Acceptance criteria:**
    78	
9:     9	5. **Aliases and overrides:** extend pack-schema and normalizer alias-kind allowlists for `renderer`, `planner`, and `finalizer`, while keeping bare legacy names programmatic. Resolution is alias → canonical ID → override target → registry winner. Wire `OverrideStore` during default registry construction rather than CLI-only post-attachment.
37:    37	9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
39:    39	10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.
45:    45	   - verb-specific raw JSON dictionaries, not a universal CLI envelope;
54:    54	  - Draft `docs/contracts/render-backend-v1.md` with the decisions above and an explicit statement that all 18 locked decisions remain unchanged.
61:    61	    - every currently emitted provenance field;
76:    76	- [ ] **M1-01 — Freeze the language-neutral contracts**
85:    85	    - structured protocol/backend/artifact/finalizer failures;
86:    86	    - provenance v2.
87:    87	  - Add versioned JSON Schemas for request, result, support, plan, finalization, and the three manifest types.
101:   101	  - Use existing atomic JSON and SHA-256 helpers.
102:   102	  - Gate: Python DTOs and raw JSON fixtures round-trip identically; unknown versions, invalid frame bounds, duplicate attachments, traversal, and backend attempts to overwrite core fields fail structurally.
106:   106	  - Extend `astrid/core/pack/schemas/v1/pack.json` and `_optional_pack_extensions()` in `pack/permissions.py` with the exact `extensions.rendering` shape.
107:   107	  - Add schema/normalizer parity tests for extension keys and alias-kind enums.
119:   119	  - Gate: schema/runtime parity, precedence, conflicts, aliases, overrides, cycles, invalid targets, active/inactive installs, corrupt trust records, env denial, explicit-extra eligibility, traversal, and no-import listing tests pass.
136:   136	  - Commit `tests/fixtures/renderer_packs/raw_command/`, implementing the protocol without importing the Astrid SDK and producing a deterministic two-second artifact.
140:   140	  - Gate: render/support success, unsupported response, malformed JSON, missing result/output, nonzero exit, timeout, SIGINT cleanup, untrusted env discovery, trusted install, and static no-import inspection all pass.
151:   151	  - Add renderer-local artifact enforcement for existence, non-empty output, workspace containment, symlinks, hashes, duration, video profile, and audio ownership.
154:   154	  - Gate: local/cached/remote assets, Range requests, expired URLs, restricted serving, server-start failure, cleanup, invalid artifacts, visual-only modes, attachments, and crash-orphan recovery pass.
158:   158	  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
169:   169	  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.

exec
/bin/zsh -lc 'git diff --check ab486f9..8418bae; PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py --tb=short' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 463ms:
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

collab: Wait
exec
/bin/zsh -lc "node -e 'const fs=require(\"fs\"); const files=process.argv.slice(1); let n=0,badU=0,literal=0; function walk(x){if(x&&typeof x===\"object\"){if(typeof x.pattern===\"string\"){n++; try{new RegExp(x.pattern,\"u\")}catch(e){badU++} if(x.pattern.includes(\"\\\\Z\")) literal++} for(const v of Object.values(x)) walk(v)}} for(const f of files) walk(JSON.parse(fs.readFileSync(f,\"utf8\"))); console.log({patterns:n,patternsWithBackslashZ:literal,invalidEcmaUnicode:badU});' astrid/core/rendering/schemas/v1/*.json
node -e 'for(const p of [\"remotion/node_modules/ajv\",\"node_modules/ajv\"]){try{console.log(require.resolve(p));}catch(e){}}'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
{ patterns: 124, patternsWithBackslashZ: 124, invalidEcmaUnicode: 124 }

exec
/bin/zsh -lc "rg --files remotion/node_modules 2>/dev/null | rg '("'^|/)ajv(/|$)|ajv'"\\.js"'$'"' | sed -n '1,40p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
exec
/bin/zsh -lc "rg -n 'trailing lf|multiline|whitespace|dir/|workspace|newline|\\\\n' tests/core/rendering/test_schema_roundtrip.py tests/core/rendering/test_contracts.py | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_contracts.py:223:        timeline_path="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:224:        assets_registry_path="/workspace/assets.json",
tests/core/rendering/test_contracts.py:265:            "timeline_path": "/workspace/timeline.json",
tests/core/rendering/test_contracts.py:277:        timeline_path="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:292:        timeline_path="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:340:                "timeline_path": "/workspace/timeline.json",
tests/core/rendering/test_contracts.py:511:    with pytest.raises(ValueError, match="workspace|contained|relative"):
tests/core/rendering/test_contracts.py:523:        "project_dir": "/workspace/remotion",
tests/core/rendering/test_contracts.py:545:            output="/workspace/video.mp4",
tests/core/rendering/test_contracts.py:546:            timeline="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:563:        "output": "/workspace/out/video.mp4",
tests/core/rendering/test_contracts.py:564:        "timeline": "/workspace/timeline.json",
tests/core/rendering/test_contracts.py:565:        "assets_registry": "/workspace/assets.json",
tests/core/rendering/test_contracts.py:612:    assert sidecar.read_text(encoding="utf-8").endswith("\n")
tests/core/rendering/test_contracts.py:693:        output="/workspace/out/video.mp4",
tests/core/rendering/test_contracts.py:694:        timeline="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:762:        output="/workspace/out/video.mp4",
tests/core/rendering/test_contracts.py:763:        timeline="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:816:        output="/workspace/out/video.mp4",
tests/core/rendering/test_contracts.py:817:        timeline="/workspace/timeline.json",
tests/core/rendering/test_contracts.py:948:    with pytest.raises(ValueError, match="workspace path"):
tests/core/rendering/test_schema_roundtrip.py:154:        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
tests/core/rendering/test_schema_roundtrip.py:155:        ("whitespace metadata key", _set(base, ("metadata",), {"   ": "demo"})),
tests/core/rendering/test_schema_roundtrip.py:157:        ("whitespace assets path", _set(base, ("assets_registry_path",), "   ")),
tests/core/rendering/test_schema_roundtrip.py:169:        ("whitespace reason", _set(base, ("reasons",), ["   "])),
tests/core/rendering/test_schema_roundtrip.py:170:        ("whitespace backend version", _set(base, ("backend_version",), "   ")),
tests/core/rendering/test_schema_roundtrip.py:218:        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
tests/core/rendering/test_schema_roundtrip.py:219:        ("whitespace log", _set(base, ("logs",), ["   "])),
tests/core/rendering/test_schema_roundtrip.py:221:        ("whitespace video path", _set(base, ("video", "path"), "   ")),
tests/core/rendering/test_schema_roundtrip.py:261:        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
tests/core/rendering/test_schema_roundtrip.py:283:        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
tests/core/rendering/test_schema_roundtrip.py:284:        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '125,295p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   125	    result = deepcopy(payload)
   126	    target: Any = result
   127	    for part in path[:-1]:
   128	        target = target[part]
   129	    del target[path[-1]]
   130	    return result
   131	
   132	
   133	def _request_cases() -> list[tuple[str, dict[str, Any]]]:
   134	    base = _load_fixture("request.json")
   135	    profile = _load_fixture("plan.json")["profile"]
   136	    partial_audio = deepcopy(profile)
   137	    partial_audio["audio_codec"] = "aac"
   138	    rendered_visual = _set(_set(base, ("profile",), profile), ("audio",), "rendered")
   139	    none_with_audio = _set(
   140	        _set(base, ("profile",), _load_schema("request.json")["examples"][0]["profile"]),
   141	        ("audio",),
   142	        "none",
   143	    )
   144	    cases = [
   145	        ("valid canonical", base),
   146	        ("valid populated profile", _set(base, ("profile",), _load_schema("request.json")["examples"][0]["profile"])),
   147	        ("missing required", _delete(base, ("timeline_path",))),
   148	        ("unknown field", {**base, "remotion_composition": "TimelineComposition"}),
   149	        ("wrong path type", _set(base, ("timeline_path",), 7)),
   150	        ("valid underscore backend id", _set(base, ("backend_config",), {"acme.bad_id": {}})),
   151	        ("partial populated audio", _set(base, ("profile",), partial_audio)),
   152	        ("rendered with visual profile", rendered_visual),
   153	        ("none with audio profile", none_with_audio),
   154	        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
   155	        ("whitespace metadata key", _set(base, ("metadata",), {"   ": "demo"})),
   156	        ("empty metadata value", _set(base, ("metadata",), {"project_id": ""})),
   157	        ("whitespace assets path", _set(base, ("assets_registry_path",), "   ")),
   158	        ("empty assets path", _set(base, ("assets_registry_path",), "")),
   159	        ("nul in metadata value", _set(base, ("metadata",), {"project_id": "a\u0000b"})),
   160	    ]
   161	    return _with_version_adversaries(base, cases)
   162	
   163	
   164	def _support_cases() -> list[tuple[str, dict[str, Any]]]:
   165	    base = _load_fixture("support.json")
   166	    cases = [
   167	        ("valid canonical", base),
   168	        ("valid string feature", _set(base, ("features",), {"mode": "visual"})),
   169	        ("whitespace reason", _set(base, ("reasons",), ["   "])),
   170	        ("whitespace backend version", _set(base, ("backend_version",), "   ")),
   171	        ("missing backend", _delete(base, ("backend",))),
   172	        ("valid underscore backend", _set(base, ("backend",), "acme.bad_id")),
   173	        ("duplicate alternatives", _set(base, ("alternatives",), ["acme.other", "acme.other"])),
   174	        ("invalid feature value", _set(base, ("features",), {"count": 2})),
   175	        ("unknown field", {**base, "priority": 1}),
   176	    ]
   177	    return _with_version_adversaries(base, cases)
   178	
   179	
   180	def _plan_cases() -> list[tuple[str, dict[str, Any]]]:
   181	    base = _load_fixture("plan.json")
   182	    partial = deepcopy(base)
   183	    partial["profile"]["audio_codec"] = "aac"
   184	    zero_with_segment = deepcopy(base)
   185	    zero_with_segment["total_frames"] = 0
   186	    zero_with_segment["reasons"] = {}
   187	    cases = [
   188	        ("valid canonical", base),
   189	        ("valid object policy", _set(base, ("requested_policy",), {"ordered": ["acme.visual"]})),
   190	        ("missing total", _delete(base, ("total_frames",))),
   191	        ("unknown field", {**base, "backend": "acme.visual"}),
   192	        ("uppercase renderer", _set(base, ("segments", 0, "renderer", "id"), "Acme.Visual")),
   193	        ("valid underscore renderer", _set(
   194	            _set(base, ("segments", 0, "renderer", "id"), "acme.bad_id"),
   195	            ("segments", 0, "renderer", "support_decision", "backend"),
   196	            "acme.bad_id",
   197	        )),
   198	        ("malformed request hash", _set(base, ("request_digest",), "bad")),
   199	        ("malformed input hash", _set(base, ("segments", 0, "input_hashes", "timeline"), "bad")),
   200	        ("partial populated audio", partial),
   201	        ("boolean total", _set(base, ("total_frames",), True)),
   202	        ("zero with segment", zero_with_segment),
   203	        ("nested support version", _set(base, ("segments", 0, "renderer", "support_decision", "schema_version"), 2)),
   204	    ]
   205	    return _with_version_adversaries(base, cases)
   206	
   207	
   208	def _result_cases() -> list[tuple[str, dict[str, Any]]]:
   209	    base = _load_fixture("result.json")
   210	    error = deepcopy(_load_schema("result.json")["examples"][1])
   211	    partial = deepcopy(base)
   212	    partial["video"]["profile"]["audio_codec"] = "aac"
   213	    cases = [
   214	        ("valid canonical success", base),
   215	        ("valid canonical error", error),
   216	        ("missing video", _delete(base, ("video",))),
   217	        ("unknown top-level attachment surface", {**base, "attachments": {}}),
   218	        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
   219	        ("whitespace log", _set(base, ("logs",), ["   "])),
   220	        ("nul in log", _set(base, ("logs",), ["bad\u0000log"])),
   221	        ("whitespace video path", _set(base, ("video", "path"), "   ")),
   222	        ("drive-relative video", _set(base, ("video", "path"), "C:escape.mp4")),
   223	        ("drive-relative attachment", _set(_set(base, ("video", "attachments"), {"x.dat": {"name": "x.dat", "path": "C:escape.dat", "kind": "project", "sha256": "a" * 64}}), ("video", "path"), "outputs/visual.mp4")),
   224	        (
   225	            "underscore attachment kind",
   226	            _set(
   227	                base,
   228	                ("video", "attachments"),
   229	                {
   230	                    "x.dat": {
   231	                        "name": "x.dat",
   232	                        "path": "outputs/x.dat",
   233	                        "kind": "project_file",
   234	                        "sha256": "a" * 64,
   235	                    }
   236	                },
   237	            ),
   238	        ),
   239	        ("partial populated audio", partial),
   240	        ("contradictory ownership", _set(base, ("audio_ownership",), "passthrough")),
   241	        ("valid underscore fragment namespace", _set(base, ("backend_fragments",), {"acme.bad_id": {}})),
   242	        ("core fragment key", _set(base, ("backend_fragments",), {"acme.visual": {"planner": {}}})),
   243	        ("error missing version", _delete(error, ("schema_version",))),
   244	        ("error boolean version", _set(error, ("schema_version",), True)),
   245	        ("error malformed version", _set(error, ("schema_version",), "1")),
   246	        ("error unknown version", _set(error, ("schema_version",), 2)),
   247	    ]
   248	    return _with_version_adversaries(base, cases)
   249	
   250	
   251	def _finalize_cases() -> list[tuple[str, dict[str, Any]]]:
   252	    base = _load_fixture("finalize.json")
   253	    partial = deepcopy(base)
   254	    partial["artifacts"][0]["profile"]["audio_codec"] = "aac"
   255	    zero_plan = deepcopy(base)
   256	    zero_plan["plan"] = deepcopy(_load_schema("plan.json")["examples"][1])
   257	    cases = [
   258	        ("valid canonical", base),
   259	        ("missing artifacts", _delete(base, ("artifacts",))),
   260	        ("unknown field", {**base, "faststart": True}),
   261	        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
   262	        ("empty artifacts", _set(base, ("artifacts",), [])),
   263	        ("drive-relative artifact", _set(base, ("artifacts", 0, "path"), "C:segment.mp4")),
   264	        (
   265	            "underscore attachment kind",
   266	            _set(
   267	                base,
   268	                ("artifacts", 0, "attachments"),
   269	                {
   270	                    "x.dat": {
   271	                        "name": "x.dat",
   272	                        "path": "outputs/x.dat",
   273	                        "kind": "project_file",
   274	                        "sha256": "a" * 64,
   275	                    }
   276	                },
   277	            ),
   278	        ),
   279	        ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
   280	                ("partial populated audio", partial),
   281	        ("contradictory artifact audio", _set(base, ("artifacts", 0, "audio"), "rendered")),
   282	        ("nested plan version", _set(base, ("plan", "schema_version"), 2)),
   283	        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
   284	        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
   285	        ("zero-frame plan", zero_plan),
   286	    ]
   287	    return _with_version_adversaries(base, cases)
   288	
   289	
   290	def _manifest_cases(
   291	    schema_name: str,
   292	    required_operation: str,
   293	) -> list[tuple[str, dict[str, Any]]]:
   294	    base = deepcopy(_load_schema(schema_name)["examples"][0])
   295	    return [

exec
/bin/zsh -lc "jq 'keys' tests/core/rendering/fixtures/v1/finalize.json; jq '.plan|keys' tests/core/rendering/fixtures/v1/finalize.json; nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '1,60p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
[
  "artifacts",
  "backend_config",
  "metadata",
  "output_name",
  "plan",
  "schema_version"
]
[
  "finalizer",
  "planner",
  "profile",
  "reasons",
  "request_digest",
  "requested_policy",
  "schema_version",
  "segments",
  "total_frames",
  "window"
]
     1	{
     2	  "$schema": "http://json-schema.org/draft-07/schema#",
     3	  "$id": "https://astrid.local/schemas/rendering/v1/finalize.json",
     4	  "title": "Astrid finalize request v1",
     5	  "type": "object",
     6	  "additionalProperties": false,
     7	  "required": [
     8	    "schema_version",
     9	    "plan",
    10	    "artifacts",
    11	    "output_name"
    12	  ],
    13	  "properties": {
    14	    "schema_version": {
    15	      "type": "integer",
    16	      "const": 1
    17	    },
    18	    "plan": {
    19	      "allOf": [
    20	        {
    21	          "$ref": "#/definitions/renderPlan"
    22	        },
    23	        {
    24	          "properties": {
    25	            "total_frames": {
    26	              "minimum": 1
    27	            }
    28	          }
    29	        }
    30	      ]
    31	    },
    32	    "artifacts": {
    33	      "type": "array",
    34	      "minItems": 1,
    35	      "items": {
    36	        "$ref": "#/definitions/videoArtifact"
    37	      }
    38	    },
    39	    "output_name": {
    40	      "type": "string",
    41	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
    42	      "not": {
    43	        "enum": [
    44	          ".",
    45	          ".."
    46	        ]
    47	      }
    48	    },
    49	    "backend_config": {
    50	      "$ref": "#/definitions/backendConfig"
    51	    },
    52	    "metadata": {
    53	      "$ref": "#/definitions/stringMap"
    54	    }
    55	  },
    56	  "definitions": {
    57	    "qualifiedId": {
    58	      "type": "string",
    59	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
    60	    },

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '300,345p'; nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '10,35p'; nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '56,76p'; nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '276,288p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   300	    denominator = _require_int(value[1], f"{label}[1]", minimum=1)
   301	    return numerator, denominator
   302	
   303	
   304	def _require_frame_range(value: Any, label: str) -> tuple[int, int]:
   305	    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
   306	        raise TypeError(f"{label} must be a two-item [start_frame, end_frame] array")
   307	    start = _require_int(value[0], f"{label}[0]", minimum=0)
   308	    end = _require_int(value[1], f"{label}[1]", minimum=1)
   309	    if end <= start:
   310	        raise ValueError(f"{label} must be half-open with end_frame > start_frame")
   311	    return start, end
   312	
   313	
   314	def _require_workspace_relative_path(value: Any, label: str) -> str:
   315	    raw = _require_string(value, label)
   316	    if "\\" in raw:
   317	        raise ValueError(f"{label} must be a normalized workspace path using forward slashes")
   318	    normalized = raw.replace("\\", "/")
   319	    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
   320	        raise ValueError(f"{label} must be relative to the invocation workspace")
   321	    if normalized.startswith("//"):
   322	        raise ValueError(f"{label} must not be a UNC path")
   323	    raw_parts = normalized.split("/")
   324	    parts = PurePosixPath(normalized).parts
   325	    if not parts or any(part in {"", ".", ".."} for part in raw_parts):
   326	        raise ValueError(f"{label} must be a normalized contained workspace path")
   327	    if any(not part.strip() for part in raw_parts):
   328	        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
   329	    return raw
   330	
   331	
   332	def _relative_file_path(path: str | Path, workspace_root: str | Path, label: str) -> tuple[str, Path]:
   333	    root = Path(workspace_root).resolve()
   334	    candidate = Path(path)
   335	    if not candidate.is_absolute():
   336	        candidate = root / candidate
   337	    resolved = candidate.resolve(strict=True)
   338	    try:
   339	        relative = resolved.relative_to(root)
   340	    except ValueError as exc:
   341	        raise ValueError(f"{label} escapes invocation workspace {root}") from exc
   342	    return relative.as_posix(), resolved
   343	
   344	
   345	def _protocol_failure(message: str, *, details: Mapping[str, Any] | None = None) -> NoReturn:
    10	      "$ref": "#/definitions/error"
    11	    }
    12	  ],
    13	  "definitions": {
    14	    "qualifiedId": {
    15	      "type": "string",
    16	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
    17	    },
    18	    "sha256": {
    19	      "type": "string",
    20	      "pattern": "^[0-9a-f]{64}\\Z"
    21	    },
    22	    "workspacePath": {
    23	      "type": "string",
    24	      "minLength": 1,
    25	      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
    26	    },
    27	    "portableName": {
    28	      "type": "string",
    29	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
    30	      "not": {
    31	        "enum": [
    32	          ".",
    33	          ".."
    34	        ]
    35	      }
    56	  "definitions": {
    57	    "qualifiedId": {
    58	      "type": "string",
    59	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
    60	    },
    61	    "sha256": {
    62	      "type": "string",
    63	      "pattern": "^[0-9a-f]{64}\\Z"
    64	    },
    65	    "workspacePath": {
    66	      "type": "string",
    67	      "minLength": 1,
    68	      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
    69	    },
    70	    "portableName": {
    71	      "type": "string",
    72	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
    73	      "not": {
    74	        "enum": [
    75	          ".",
    76	          ".."
   276	                },
   277	            ),
   278	        ),
   279	        ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
   280	                ("partial populated audio", partial),
   281	        ("contradictory artifact audio", _set(base, ("artifacts", 0, "audio"), "rendered")),
   282	        ("nested plan version", _set(base, ("plan", "schema_version"), 2)),
   283	        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
   284	        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
   285	        ("zero-frame plan", zero_plan),
   286	    ]
   287	    return _with_version_adversaries(base, cases)
   288	

codex
The independent reviews agree on the two main defects and found one deeper boundary bypass: `assemble_provenance_v2` trusts an already-created `RenderPlan`, whose nested lists remain mutable despite the frozen dataclass. I’m validating the smallest reproducible case and then I’ll issue the binary checkpoint verdict.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\"); p=ns[\"_plan\"](); print(\"before\",p.total_frames,len(p.segments)); p.segments.clear(); out=ns[\"assemble_provenance_v2\"](engine=\"hybrid\",output=\"out.mp4\",timeline=\"timeline.json\",assets_registry=None,plan=p,artifact_profiles={},v1_compatibility=ns[\"_compatibility\"]()); print(\"accepted\",out[\"request_digest\"],out[\"segments_v2\"],out[\"artifact_profiles\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 244ms:
before 48 1
accepted dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd [] {}

exec
/bin/zsh -lc "nl -ba astrid/core/foundation/atomic_io.py | sed -n '96,126p'; nl -ba astrid/core/rendering/contracts.py | sed -n '1340,1410p'; nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '278,286p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    96	def write_bytes_atomic(path: str | Path, data: bytes) -> None:
    97	    """Atomically write *data* to *path*."""
    98	
    99	    def _write_bytes(tmp: Path) -> None:
   100	        tmp.write_bytes(data)
   101	
   102	    try:
   103	        _write_atomic_binary(Path(path), _write_bytes)
   104	    except OSError as exc:
   105	        raise AtomicWriteError(str(exc)) from exc
   106	
   107	
   108	def write_json_atomic(path: str | Path, payload: Any) -> None:
   109	    """Atomically write *payload* as pretty-printed, sorted-key JSON."""
   110	
   111	    json_path = Path(path)
   112	    json_path.parent.mkdir(parents=True, exist_ok=True)
   113	
   114	    fd, tmp_name = tempfile.mkstemp(
   115	        prefix=f".{json_path.name}.", suffix=".tmp", dir=json_path.parent
   116	    )
   117	    tmp_path = Path(tmp_name)
   118	    try:
   119	        with os.fdopen(fd, "w", encoding="utf-8") as handle:
   120	            json.dump(payload, handle, indent=2, sort_keys=True)
   121	            handle.write("\n")
   122	            handle.flush()
   123	            os.fsync(handle.fileno())
   124	        os.replace(tmp_path, json_path)
   125	        _fsync_dir(json_path.parent)
   126	    except OSError as exc:
  1340	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderSegment:
  1341	        data = _require_mapping(payload, "render segment")
  1342	        required = {"window", "renderer", "input_hashes"}
  1343	        _validate_object_keys(data, required=required, allowed=required, label="render segment")
  1344	        return cls(
  1345	            window=FrameWindow.from_dict(data["window"]),
  1346	            renderer=RendererResolution.from_dict(data["renderer"]),
  1347	            input_hashes=data["input_hashes"],
  1348	        )
  1349	
  1350	
  1351	@dataclass(frozen=True)
  1352	class RenderPlan:
  1353	    """A deterministic temporal plan plus its explicit finalizer."""
  1354	
  1355	    schema_version: int
  1356	    request_digest: str
  1357	    requested_policy: str | dict[str, Any]
  1358	    planner: PlannerResolution
  1359	    segments: list[RenderSegment]
  1360	    finalizer: FinalizerResolution
  1361	    profile: RenderProfile
  1362	    total_frames: int
  1363	    reasons: dict[str, str]
  1364	    window: FrameWindow | None = None
  1365	
  1366	    def __post_init__(self) -> None:
  1367	        object.__setattr__(
  1368	            self,
  1369	            "schema_version",
  1370	            _require_schema_version(self.schema_version, "render plan"),
  1371	        )
  1372	        object.__setattr__(
  1373	            self,
  1374	            "request_digest",
  1375	            _require_sha256(self.request_digest, "request_digest"),
  1376	        )
  1377	        object.__setattr__(
  1378	            self,
  1379	            "requested_policy",
  1380	            _normalize_requested_policy(self.requested_policy),
  1381	        )
  1382	        planner = (
  1383	            self.planner
  1384	            if isinstance(self.planner, PlannerResolution)
  1385	            else PlannerResolution.from_dict(_require_mapping(self.planner, "planner"))
  1386	        )
  1387	        object.__setattr__(self, "planner", planner)
  1388	        if isinstance(self.segments, (str, bytes)) or not isinstance(self.segments, Sequence):
  1389	            raise TypeError("segments must be an array")
  1390	        segments = [
  1391	            item
  1392	            if isinstance(item, RenderSegment)
  1393	            else RenderSegment.from_dict(_require_mapping(item, f"segments[{index}]"))
  1394	            for index, item in enumerate(self.segments)
  1395	        ]
  1396	        object.__setattr__(self, "segments", segments)
  1397	        finalizer = (
  1398	            self.finalizer
  1399	            if isinstance(self.finalizer, FinalizerResolution)
  1400	            else FinalizerResolution.from_dict(_require_mapping(self.finalizer, "finalizer"))
  1401	        )
  1402	        object.__setattr__(self, "finalizer", finalizer)
  1403	        profile = _coerce_profile(self.profile, "plan profile", nullable=False)
  1404	        object.__setattr__(self, "profile", profile)
  1405	        total_frames = _require_int(self.total_frames, "total_frames", minimum=0)
  1406	        object.__setattr__(self, "total_frames", total_frames)
  1407	        window = _coerce_window(self.window, "plan window", nullable=True)
  1408	        object.__setattr__(self, "window", window)
  1409	        if window is not None:
  1410	            if window.fps_rational != profile.fps_rational:
   278	        ),
   279	        ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
   280	                ("partial populated audio", partial),
   281	        ("contradictory artifact audio", _set(base, ("artifacts", 0, "audio"), "rendered")),
   282	        ("nested plan version", _set(base, ("plan", "schema_version"), 2)),
   283	        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
   284	        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
   285	        ("zero-frame plan", zero_plan),
   286	    ]

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '1405,1485p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1405	        total_frames = _require_int(self.total_frames, "total_frames", minimum=0)
  1406	        object.__setattr__(self, "total_frames", total_frames)
  1407	        window = _coerce_window(self.window, "plan window", nullable=True)
  1408	        object.__setattr__(self, "window", window)
  1409	        if window is not None:
  1410	            if window.fps_rational != profile.fps_rational:
  1411	                raise ValueError("plan window FPS must exactly match the canonical profile FPS")
  1412	            if window.end_frame > total_frames:
  1413	                raise ValueError("plan window must not extend beyond total_frames")
  1414	        if total_frames == 0:
  1415	            if window is not None or segments:
  1416	                raise ValueError("a zero-frame plan must have no window or segments")
  1417	        else:
  1418	            if not segments:
  1419	                raise ValueError("a positive-frame plan must contain at least one segment")
  1420	            target_start = window.start_frame if window is not None else 0
  1421	            target_end = window.end_frame if window is not None else total_frames
  1422	            expected_start = target_start
  1423	            for index, segment in enumerate(segments):
  1424	                if segment.window.fps_rational != profile.fps_rational:
  1425	                    raise ValueError(
  1426	                        f"segments[{index}] FPS must exactly match the canonical profile FPS"
  1427	                    )
  1428	                actual_start = segment.window.start_frame
  1429	                if actual_start != expected_start:
  1430	                    relation = "overlaps or is out of order" if actual_start < expected_start else "leaves a gap"
  1431	                    raise ValueError(f"segments[{index}] {relation} at frame {expected_start}")
  1432	                if segment.window.end_frame > target_end:
  1433	                    raise ValueError(f"segments[{index}] extends beyond the plan target window")
  1434	                expected_start = segment.window.end_frame
  1435	            if expected_start != target_end:
  1436	                raise ValueError("plan segments leave a trailing gap")
  1437	        reasons = _require_string_mapping(self.reasons, "reasons")
  1438	        expected_reason_keys = {str(index) for index in range(len(segments))}
  1439	        if set(reasons) != expected_reason_keys:
  1440	            raise ValueError(
  1441	                "plan reasons must contain exactly one entry per segment, keyed by zero-based index"
  1442	            )
  1443	        object.__setattr__(self, "reasons", reasons)
  1444	
  1445	    def to_dict(self) -> dict[str, Any]:
  1446	        return _json_safe_mapping(
  1447	            {
  1448	                "schema_version": self.schema_version,
  1449	                "request_digest": self.request_digest,
  1450	                "requested_policy": self.requested_policy,
  1451	                "planner": self.planner,
  1452	                "segments": self.segments,
  1453	                "finalizer": self.finalizer,
  1454	                "profile": self.profile,
  1455	                "total_frames": self.total_frames,
  1456	                "reasons": self.reasons,
  1457	                "window": self.window,
  1458	            }
  1459	        )
  1460	
  1461	    @classmethod
  1462	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderPlan:
  1463	        try:
  1464	            data = _require_mapping(payload, "render plan")
  1465	            required = {
  1466	                "schema_version",
  1467	                "request_digest",
  1468	                "requested_policy",
  1469	                "planner",
  1470	                "segments",
  1471	                "finalizer",
  1472	                "profile",
  1473	                "total_frames",
  1474	                "reasons",
  1475	                "window",
  1476	            }
  1477	            _validate_object_keys(data, required=required, allowed=required, label="render plan")
  1478	            raw_segments = data["segments"]
  1479	            if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
  1480	                raise TypeError("segments must be an array")
  1481	            return cls(
  1482	                schema_version=data["schema_version"],
  1483	                request_digest=data["request_digest"],
  1484	                requested_policy=data["requested_policy"],
  1485	                planner=PlannerResolution.from_dict(data["planner"]),

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,jsonschema; from pathlib import Path; from astrid.core.rendering.contracts import _require_workspace_relative_path as f; s=json.loads(Path(\"astrid/core/rendering/schemas/v1/result.json\").read_text())[\"definitions\"][\"workspacePath\"]; v=jsonschema.Draft7Validator(s); xs=[\"dir/ /video.mp4\",\"dir/\\t/video.mp4\",\"dir/.\\n\",\"dir/..\\n\"];
for x in xs:
 try:f(x,\"x\"); d=True
 except Exception:d=False
 print(repr(x),v.is_valid(x),d)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 155ms:
'dir/ /video.mp4' True False
'dir/\t/video.mp4' True False
'dir/.\n' False True
'dir/..\n' False True

codex
1. **Per-segment lineage remains unbound and bypassable.** Sequence output drops `VideoArtifact.path`, accepts mutated escaped paths, and cannot round-trip. Multi-segment mapping remains unordered. A mutated positive `RenderPlan` with `segments.clear()` also accepts empty lineage. Reconstruct DTOs at the boundary and use one canonical ordered, path-bearing entry per segment; reject unordered multi-segment mappings. [provenance.py:107](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:107) [provenance.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:302)

2. **The JSON Schemas are no longer language-neutral.** All 124 patterns use Python-specific `\Z`; ECMAScript treats it as literal `Z` or rejects it, so canonical IDs and digests fail non-Python validation. Replace it with a portable absolute-end assertion such as `(?![\\s\\S])` and add ECMAScript conformance coverage. The new LF adversaries also target nonexistent top-level finalize fields, so they do not exercise the intended nested patterns. [result.json:16](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:16) [test_schema_roundtrip.py:283](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_schema_roundtrip.py:283)

3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
tokens used
192,998
1. **Per-segment lineage remains unbound and bypassable.** Sequence output drops `VideoArtifact.path`, accepts mutated escaped paths, and cannot round-trip. Multi-segment mapping remains unordered. A mutated positive `RenderPlan` with `segments.clear()` also accepts empty lineage. Reconstruct DTOs at the boundary and use one canonical ordered, path-bearing entry per segment; reject unordered multi-segment mappings. [provenance.py:107](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:107) [provenance.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:302)

2. **The JSON Schemas are no longer language-neutral.** All 124 patterns use Python-specific `\Z`; ECMAScript treats it as literal `Z` or rejects it, so canonical IDs and digests fail non-Python validation. Replace it with a portable absolute-end assertion such as `(?![\\s\\S])` and add ECMAScript conformance coverage. The new LF adversaries also target nonexistent top-level finalize fields, so they do not exercise the intended nested patterns. [result.json:16](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:16) [test_schema_roundtrip.py:283](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_schema_roundtrip.py:283)

3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
