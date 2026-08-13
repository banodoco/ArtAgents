Reading additional input from stdin...
2026-08-12T02:39:23.198856Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:39:23.198888Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:39:23.198892Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3d6-b77c-7980-bae7-ed826fb75349
--------
user
# Megado Checkpoint — Batch 1 ninth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3),
-r6 (3), -r7 (3), -r8 (3). Ninth rework committed as `788501c` (prior head
8418bae). Incremental diff at /tmp/batch1-r9.diff.

## How each of your 3 re-review8 issues was addressed (host-implemented)

1. **Per-segment lineage unbound/bypassable** →
   - Multi-segment plans REQUIRE the ordered sequence form (one VideoArtifact
     per segment); unordered mapping form rejected for multi-segment.
   - Sequence output now path-bearing: every record carries `path`.
   - RenderPlan, VideoArtifact, Attachment, and RenderProfile values are all
     reconstructed through their DTO validators at the provenance boundary —
     a mutated frozen RenderPlan with cleared segments is rejected by
     RenderPlan.from_dict before lineage checks.
   - Adversarial tests: dup path, mutated-plan reconstruction.
2. **Schemas not language-neutral (`\Z`)** →
   - All 124 `\Z` anchors replaced with the portable absolute-end assertion
     `(?![\s\S])` — valid in ECMAScript AND Python re.
   - Verified: no `\Z` remains in any schema.
3. **workspacePath parity** →
   - Rewritten to be DTO-equivalent: rejects leading `/`, drive letters,
     empty components, exact `.`/`..` components, whitespace-only components,
     backslashes, NUL; accepts internal newlines, `".\n"` components, and
     leading/trailing whitespace around content. Cross-checked 8+ cases
     DTO vs schema — all match.

## Evidence

- Incremental diff: /tmp/batch1-r9.diff (12 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.
- Docs updated: ordered per-segment lineage, DTO reconstruction, portable
  patterns.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 9 review rounds and the
contract is now heavily validated AND language-neutral. If sound and STABLE,
say exactly `PASS` so Batch 2 may begin.
codex
I’m using the Megado checkpoint guidance plus this repo’s context-mining/Astrid instructions. I’ll inspect the ninth incremental diff and the affected contracts/tests independently, then return only `PASS` if no concrete blocker remains.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/astrid/SKILL.md astrid/packs/_core/skill/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,300p' astrid/packs/_core/skill/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     772 astrid/packs/_core/skill/SKILL.md
    1797 total
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

codex
The repo’s context-mining rule calls for an independent review lane here, so I’m delegating one adversarial pass while I inspect the exact changed implementation and schema parity locally. No files will be modified.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '221,500p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '501,772p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc "sed -n '221,400p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:

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

exec
/bin/zsh -lc "sed -n '401,580p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc "sed -n '581,772p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:

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

2026-08-12T02:40:17.187787Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:40:17.188019Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:40:17.188036Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "sed -n '1,260p' /tmp/batch1-r9.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
diff --git a/.oracle/checkins/batch-1-r8.md b/.oracle/checkins/batch-1-r8.md
new file mode 100644
index 0000000..c41c8b4
--- /dev/null
+++ b/.oracle/checkins/batch-1-r8.md
@@ -0,0 +1,9998 @@
+Reading additional input from stdin...
+2026-08-12T02:20:30.459984Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T02:20:30.460019Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T02:20:30.460026Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff3c5-6ecc-7423-bec6-147c796da278
+--------
+user
+# Megado Checkpoint — Batch 1 eighth re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3),
+-r6 (3), -r7 (3). Eighth rework committed as `8418bae` (prior head ab486f9).
+Incremental diff at /tmp/batch1-r8.diff.
+
+## How each of your 3 re-review7 issues was addressed (host-implemented)
+
+1. **Per-segment lineage unbound, cardinality bypassable** →
+   - Sequence form now preserves ORDER (returns a path-keyed list, not an
+     unordered map) and REJECTS duplicate paths.
+   - Mapping form requires path keys == VideoArtifact.path.
+2. **Provenance bypasses artifact/attachment contracts** →
+   - Artifact keys validated as workspace-relative paths (traversal/absolute
+     rejected).
+   - Top-level Attachment values reconstructed through `Attachment.from_dict`
+     (mutation via object.__setattr__ cannot inject invalid fields).
+   - RenderProfile values reconstructed through `RenderProfile.from_dict`.
+   - Attachment names must be unique ACROSS all segment artifacts.
+   - Adversarial tests: dup path (sequence), dup attachment across artifacts,
+     escaped artifact key, key/name mismatch.
+3. **Schema/DTO parity at terminal LF** →
+   - All fully-anchored schema patterns now end `\Z` (Python re) instead of
+     `$`, rejecting trailing newlines exactly like DTO fullmatch/full-regex
+     (qualified IDs, sha256, portable names, kinds, plan reason indices).
+   - workspacePath rejects whitespace-only path components (DTO aligned with
+     schema for `"dir/\n"`).
+   - Trailing-LF adversaries for digest and reason keys added.
+
+## Evidence
+
+- Incremental diff: /tmp/batch1-r8.diff (14 files)
+- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
+  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
+  failures), 3 skipped.
+- Docs updated.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Batch 1 has passed 8 review rounds. The
+contract is heavily validated; remaining items should be convergence-level.
+If the contract is sound and STABLE, say exactly `PASS` so Batch 2 may begin.
+If blocking issues remain, name them precisely with minimum rework.
+codex
+I’m using the `megado` checkpoint guidance and the repository’s context-minimization/subagent workflow. I’ll inspect the incremental diff and affected contracts read-only, then run focused adversarial checks before returning only `PASS` or precise blockers.
+exec
+/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '241,520p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '261,520p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
+---
+name: contextminning-subagentmaxxing
+description: >
+  Keep the main-thread context as lean as possible while working. Two moves: (1)
+  context minning — after each turn, look for a natural break-off point to condense,
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
+  a subagent (especially the DeepSeek/Kimi agents via subagent-launcher) should research,
+  validate, or execute it so the verbose work never lands in your context. Use on 
+  any long, multi-step, or research-heavy task.

exec
/bin/zsh -lc "rg --files .oracle | sort | rg 'batch-1|tasklist|plan|status'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/briefs/05-hybrid-planner-canvas.md
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
.oracle/checkins/batch-1-r2.md
.oracle/checkins/batch-1-r3.md
.oracle/checkins/batch-1-r4.md
.oracle/checkins/batch-1-r5.md
.oracle/checkins/batch-1-r6.md
.oracle/checkins/batch-1-r7.md
.oracle/checkins/batch-1-r8.md
.oracle/checkins/batch-1-r9.md
.oracle/checkins/batch-1.md
.oracle/findings/05-hybrid-planner-canvas.meta.json
.oracle/findings/05-hybrid-planner-canvas.txt
.oracle/plan-v1.txt
.oracle/plan.md
.oracle/tasklist.md

exec
/bin/zsh -lc 'git diff --stat 8418bae..788501c && git diff --check 8418bae..788501c' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r8.md                     | 9998 ++++++++++++++++++++
 astrid/core/rendering/provenance.py                |   18 +-
 astrid/core/rendering/schemas/v1/finalize.json     |   56 +-
 .../rendering/schemas/v1/finalizer-manifest.json   |   22 +-
 astrid/core/rendering/schemas/v1/plan.json         |   42 +-
 .../rendering/schemas/v1/planner-manifest.json     |   22 +-
 .../rendering/schemas/v1/renderer-manifest.json    |   26 +-
 astrid/core/rendering/schemas/v1/request.json      |   32 +-
 astrid/core/rendering/schemas/v1/result.json       |   40 +-
 astrid/core/rendering/schemas/v1/support.json      |    8 +-
 docs/contracts/render-backend-v1.md                |   26 +-
 tests/core/rendering/test_contracts.py             |  126 +-
 12 files changed, 10231 insertions(+), 185 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r8.md:250: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r8.md:251: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r8.md:253: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r8.md:2324: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2325: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2334: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2335: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2341: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2342: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2355: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2356: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2361: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2362: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2369: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2370: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2377: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2378: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2387: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2388: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2395: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2396: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2405: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2406: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2423: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2424: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2436: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2437: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2440: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2446: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2447: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2450: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2454: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2455: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2469: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2470: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2474: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2480: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2501: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2505: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2516: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2528: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2530: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2534: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2537: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2554: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2555: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2558: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2559: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2564: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2566: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2567: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2579: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2580: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2608: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2609: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2612: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2619: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2620: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2699: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2700: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2771: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2772: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2783: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2784: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2806: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2807: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2823: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2830: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2851: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2951: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:2952: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3012: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3013: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3022: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3023: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3041: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3042: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3048: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3049: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3060: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3061: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3077: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3078: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3083: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3084: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3106: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3107: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3140: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3141: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3183: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3184: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3222: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3223: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3246: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3247: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3258: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3259: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3272: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3273: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3290: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3291: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3309: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3310: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:3634: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r8.md:3635: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r8.md:3637: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r8.md:5351: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:5521: trailing whitespace.
+   730	
.oracle/checkins/batch-1-r8.md:5522: trailing whitespace.
+   731	
.oracle/checkins/batch-1-r8.md:5536: trailing whitespace.
+04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-1-r8.md:5537: trailing whitespace.
+04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-1-r8.md:5663: trailing whitespace.
+   453	
.oracle/checkins/batch-1-r8.md:5671: trailing whitespace.
+   461	
.oracle/checkins/batch-1-r8.md:5673: trailing whitespace.
+   463	
.oracle/checkins/batch-1-r8.md:5675: trailing whitespace.
+   465	
.oracle/checkins/batch-1-r8.md:5680: trailing whitespace.
+   470	
.oracle/checkins/batch-1-r8.md:5702: trailing whitespace.
+   492	
.oracle/checkins/batch-1-r8.md:5711: trailing whitespace.
+   520	
.oracle/checkins/batch-1-r8.md:5730: trailing whitespace.
+   539	
.oracle/checkins/batch-1-r8.md:5731: trailing whitespace.
+   540	
.oracle/checkins/batch-1-r8.md:5741: trailing whitespace.
+   550	
.oracle/checkins/batch-1-r8.md:5742: trailing whitespace.
+   551	
.oracle/checkins/batch-1-r8.md:5800: trailing whitespace.
+   609	
.oracle/checkins/batch-1-r8.md:5804: trailing whitespace.
+   613	
.oracle/checkins/batch-1-r8.md:5805: trailing whitespace.
+   614	
.oracle/checkins/batch-1-r8.md:5818: trailing whitespace.
+   627	
.oracle/checkins/batch-1-r8.md:5819: trailing whitespace.
+   628	
.oracle/checkins/batch-1-r8.md:5822: trailing whitespace.
+   631	
.oracle/checkins/batch-1-r8.md:5831: trailing whitespace.
+   640	
.oracle/checkins/batch-1-r8.md:5832: trailing whitespace.
+   641	
.oracle/checkins/batch-1-r8.md:5838: trailing whitespace.
+   647	
.oracle/checkins/batch-1-r8.md:5839: trailing whitespace.
+   648	
.oracle/checkins/batch-1-r8.md:5870: trailing whitespace.
+   679	
.oracle/checkins/batch-1-r8.md:5880: trailing whitespace.
+   689	
.oracle/checkins/batch-1-r8.md:5912: trailing whitespace.
+   721	
.oracle/checkins/batch-1-r8.md:5913: trailing whitespace.
+   722	
.oracle/checkins/batch-1-r8.md:5931: trailing whitespace.
+   740	
.oracle/checkins/batch-1-r8.md:5932: trailing whitespace.
+   741	
.oracle/checkins/batch-1-r8.md:5968: trailing whitespace.
+   777	
.oracle/checkins/batch-1-r8.md:5969: trailing whitespace.
+   778	
.oracle/checkins/batch-1-r8.md:5983: trailing whitespace.
+   792	
.oracle/checkins/batch-1-r8.md:5984: trailing whitespace.
+   793	
.oracle/checkins/batch-1-r8.md:6000: trailing whitespace.
+   809	
.oracle/checkins/batch-1-r8.md:6001: trailing whitespace.
+   810	
.oracle/checkins/batch-1-r8.md:6095: trailing whitespace.
+   904	
.oracle/checkins/batch-1-r8.md:6096: trailing whitespace.
+   905	
.oracle/checkins/batch-1-r8.md:6156: trailing whitespace.
+   965	
.oracle/checkins/batch-1-r8.md:6157: trailing whitespace.
+   966	
.oracle/checkins/batch-1-r8.md:6166: trailing whitespace.
+   975	
.oracle/checkins/batch-1-r8.md:6167: trailing whitespace.
+   976	
.oracle/checkins/batch-1-r8.md:6183: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r8.md:6185: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r8.md:6189: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r8.md:6192: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r8.md:6209: trailing whitespace.
+    28	
.oracle/checkins/batch-1-r8.md:6210: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r8.md:6213: trailing whitespace.
+    32	
.oracle/checkins/batch-1-r8.md:6214: trailing whitespace.
+    33	
.oracle/checkins/batch-1-r8.md:6219: trailing whitespace.
+    38	
.oracle/checkins/batch-1-r8.md:6221: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r8.md:6222: trailing whitespace.
+    41	
.oracle/checkins/batch-1-r8.md:6234: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r8.md:6235: trailing whitespace.
+    54	
.oracle/checkins/batch-1-r8.md:6262: trailing whitespace.
+    81	
.oracle/checkins/batch-1-r8.md:6263: trailing whitespace.
+    82	
.oracle/checkins/batch-1-r8.md:6266: trailing whitespace.
+    85	
.oracle/checkins/batch-1-r8.md:6273: trailing whitespace.
+    92	
.oracle/checkins/batch-1-r8.md:6274: trailing whitespace.
+    93	
.oracle/checkins/batch-1-r8.md:6286: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r8.md:6287: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r8.md:6349: trailing whitespace.
+   168	
.oracle/checkins/batch-1-r8.md:6350: trailing whitespace.
+   169	
.oracle/checkins/batch-1-r8.md:6417: trailing whitespace.
+   236	
.oracle/checkins/batch-1-r8.md:6418: trailing whitespace.
+   237	
.oracle/checkins/batch-1-r8.md:6429: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r8.md:6430: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r8.md:6452: trailing whitespace.
+   271	
.oracle/checkins/batch-1-r8.md:6453: trailing whitespace.
+   272	
.oracle/checkins/batch-1-r8.md:6469: trailing whitespace.
+   288	
.oracle/checkins/batch-1-r8.md:6476: trailing whitespace.
+   295	
.oracle/checkins/batch-1-r8.md:6497: trailing whitespace.
+   316	
.oracle/checkins/batch-1-r8.md:6524: trailing whitespace.
+   343	
.oracle/checkins/batch-1-r8.md:6525: trailing whitespace.
+   344	
.oracle/checkins/batch-1-r8.md:6528: trailing whitespace.
+   347	
.oracle/checkins/batch-1-r8.md:6530: trailing whitespace.
+   349	
.oracle/checkins/batch-1-r8.md:6531: trailing whitespace.
+   350	
.oracle/checkins/batch-1-r8.md:6534: trailing whitespace.
+   353	
.oracle/checkins/batch-1-r8.md:6538: trailing whitespace.
+   357	
.oracle/checkins/batch-1-r8.md:6539: trailing whitespace.
+   358	
.oracle/checkins/batch-1-r8.md:6542: trailing whitespace.
+   361	
.oracle/checkins/batch-1-r8.md:6547: trailing whitespace.
+   366	
.oracle/checkins/batch-1-r8.md:6548: trailing whitespace.
+   367	
.oracle/checkins/batch-1-r8.md:6551: trailing whitespace.
+   370	
.oracle/checkins/batch-1-r8.md:6557: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r8.md:6563: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r8.md:6565: trailing whitespace.
+    10	
.oracle/checkins/batch-1-r8.md:6573: trailing whitespace.
+    18	
.oracle/checkins/batch-1-r8.md:6576: trailing whitespace.
+    21	
.oracle/checkins/batch-1-r8.md:6577: trailing whitespace.
+    22	
.oracle/checkins/batch-1-r8.md:6579: trailing whitespace.
+    24	
.oracle/checkins/batch-1-r8.md:6590: trailing whitespace.
+    35	
.oracle/checkins/batch-1-r8.md:6595: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r8.md:6607: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r8.md:6628: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r8.md:6648: trailing whitespace.
+    93	
.oracle/checkins/batch-1-r8.md:6665: trailing whitespace.
+   110	
.oracle/checkins/batch-1-r8.md:6678: trailing whitespace.
+   123	
.oracle/checkins/batch-1-r8.md:6685: trailing whitespace.
+   130	
.oracle/checkins/batch-1-r8.md:6686: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r8.md:6689: trailing whitespace.
+   134	
.oracle/checkins/batch-1-r8.md:6713: trailing whitespace.
+   158	
.oracle/checkins/batch-1-r8.md:6714: trailing whitespace.
+   159	
.oracle/checkins/batch-1-r8.md:6720: trailing whitespace.
+   165	
.oracle/checkins/batch-1-r8.md:6721: trailing whitespace.
+   166	
.oracle/checkins/batch-1-r8.md:6726: trailing whitespace.
+   171	
.oracle/checkins/batch-1-r8.md:6727: trailing whitespace.
+   172	
.oracle/checkins/batch-1-r8.md:6741: trailing whitespace.
+   186	
.oracle/checkins/batch-1-r8.md:6742: trailing whitespace.
+   187	
.oracle/checkins/batch-1-r8.md:6749: trailing whitespace.
+   194	
.oracle/checkins/batch-1-r8.md:6750: trailing whitespace.
+   195	
.oracle/checkins/batch-1-r8.md:6760: trailing whitespace.
+   205	
.oracle/checkins/batch-1-r8.md:6761: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r8.md:6764: trailing whitespace.
+   209	
.oracle/checkins/batch-1-r8.md:6770: trailing whitespace.
+   215	
.oracle/checkins/batch-1-r8.md:6771: trailing whitespace.
+   216	
.oracle/checkins/batch-1-r8.md:6780: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r8.md:6781: trailing whitespace.
+   226	
.oracle/checkins/batch-1-r8.md:6786: trailing whitespace.
+   231	
.oracle/checkins/batch-1-r8.md:6787: trailing whitespace.
+   232	
.oracle/checkins/batch-1-r8.md:6796: trailing whitespace.
+   241	
.oracle/checkins/batch-1-r8.md:6797: trailing whitespace.
+   242	
.oracle/checkins/batch-1-r8.md:6803: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r8.md:6804: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r8.md:6833: trailing whitespace.
+   507	
.oracle/checkins/batch-1-r8.md:6837: trailing whitespace.
+   511	
.oracle/checkins/batch-1-r8.md:6856: trailing whitespace.
+   530	
.oracle/checkins/batch-1-r8.md:6889: trailing whitespace.
+   563	
.oracle/checkins/batch-1-r8.md:6890: trailing whitespace.
+   564	
.oracle/checkins/batch-1-r8.md:6897: trailing whitespace.
+   571	
.oracle/checkins/batch-1-r8.md:6902: trailing whitespace.
+   576	
.oracle/checkins/batch-1-r8.md:6908: trailing whitespace.
+   582	
.oracle/checkins/batch-1-r8.md:6909: trailing whitespace.
+   583	
.oracle/checkins/batch-1-r8.md:6913: trailing whitespace.
+   587	
.oracle/checkins/batch-1-r8.md:6918: trailing whitespace.
+   592	
.oracle/checkins/batch-1-r8.md:6930: trailing whitespace.
+   604	
.oracle/checkins/batch-1-r8.md:6935: trailing whitespace.
+   609	
.oracle/checkins/batch-1-r8.md:6947: trailing whitespace.
+   621	
.oracle/checkins/batch-1-r8.md:6959: trailing whitespace.
+   633	
.oracle/checkins/batch-1-r8.md:6960: trailing whitespace.
+   634	
.oracle/checkins/batch-1-r8.md:6981: trailing whitespace.
+   655	
.oracle/checkins/batch-1-r8.md:6982: trailing whitespace.
+   656	
.oracle/checkins/batch-1-r8.md:6986: trailing whitespace.
+   660	
.oracle/checkins/batch-1-r8.md:6993: trailing whitespace.
+   667	
.oracle/checkins/batch-1-r8.md:7016: trailing whitespace.
+   690	
.oracle/checkins/batch-1-r8.md:7028: trailing whitespace.
+   702	
.oracle/checkins/batch-1-r8.md:7043: trailing whitespace.
+   717	
.oracle/checkins/batch-1-r8.md:7059: trailing whitespace.
+  1662	
.oracle/checkins/batch-1-r8.md:7083: trailing whitespace.
+  1686	
.oracle/checkins/batch-1-r8.md:7090: trailing whitespace.
+  1693	
.oracle/checkins/batch-1-r8.md:7091: trailing whitespace.
+  1694	
.oracle/checkins/batch-1-r8.md:7095: trailing whitespace.
+  1698	
.oracle/checkins/batch-1-r8.md:7102: trailing whitespace.
+  1705	
.oracle/checkins/batch-1-r8.md:7150: trailing whitespace.
+  1753	
.oracle/checkins/batch-1-r8.md:7154: trailing whitespace.
+  1757	
.oracle/checkins/batch-1-r8.md:7160: trailing whitespace.
+  1763	
.oracle/checkins/batch-1-r8.md:7166: trailing whitespace.
+  1769	
.oracle/checkins/batch-1-r8.md:7170: trailing whitespace.
+  1773	
.oracle/checkins/batch-1-r8.md:8443: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r8.md:8449: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r8.md:8452: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r8.md:8461: trailing whitespace.
+    20	
.oracle/checkins/batch-1-r8.md:8462: trailing whitespace.
+    21	
.oracle/checkins/batch-1-r8.md:8489: trailing whitespace.
+    48	
.oracle/checkins/batch-1-r8.md:8490: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r8.md:8493: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r8.md:8494: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r8.md:8497: trailing whitespace.
+    56	
.oracle/checkins/batch-1-r8.md:8498: trailing whitespace.
+    57	
.oracle/checkins/batch-1-r8.md:8501: trailing whitespace.
+    60	
.oracle/checkins/batch-1-r8.md:8502: trailing whitespace.
+    61	
.oracle/checkins/batch-1-r8.md:8513: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r8.md:8514: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r8.md:8522: trailing whitespace.
+    81	
.oracle/checkins/batch-1-r8.md:8529: trailing whitespace.
+    88	
.oracle/checkins/batch-1-r8.md:8530: trailing whitespace.
+    89	
.oracle/checkins/batch-1-r8.md:8537: trailing whitespace.
+    96	
.oracle/checkins/batch-1-r8.md:8538: trailing whitespace.
+    97	
.oracle/checkins/batch-1-r8.md:8546: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r8.md:8547: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r8.md:8554: trailing whitespace.
+   113	
.oracle/checkins/batch-1-r8.md:8555: trailing whitespace.
+   114	
.oracle/checkins/batch-1-r8.md:8574: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r8.md:8575: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r8.md:8586: trailing whitespace.
+   324	
.oracle/checkins/batch-1-r8.md:8587: trailing whitespace.
+   325	
.oracle/checkins/batch-1-r8.md:8600: trailing whitespace.
+   338	
.oracle/checkins/batch-1-r8.md:8601: trailing whitespace.
+   339	
.oracle/checkins/batch-1-r8.md:8618: trailing whitespace.
+   356	
.oracle/checkins/batch-1-r8.md:8619: trailing whitespace.
+   357	
.oracle/checkins/batch-1-r8.md:8637: trailing whitespace.
+   375	
.oracle/checkins/batch-1-r8.md:8638: trailing whitespace.
+   376	
.oracle/checkins/batch-1-r8.md:8682: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8714: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8724: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8783: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8784: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8793: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8794: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8817: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8818: trailing whitespace.
+ 
.oracle/checkins/batch-1-r8.md:8834: trailing whitespace.
+   809	
.oracle/checkins/batch-1-r8.md:8835: trailing whitespace.
+   810	
.oracle/checkins/batch-1-r8.md:8929: trailing whitespace.
+   904	
.oracle/checkins/batch-1-r8.md:8930: trailing whitespace.
+   905	
.oracle/checkins/batch-1-r8.md:8990: trailing whitespace.
+   965	
.oracle/checkins/batch-1-r8.md:8991: trailing whitespace.
+   966	
.oracle/checkins/batch-1-r8.md:9173: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r8.md:9175: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r8.md:9177: trailing whitespace.
+     6	
.oracle/checkins/batch-1-r8.md:9179: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r8.md:9188: trailing whitespace.
+    17	
.oracle/checkins/batch-1-r8.md:9190: trailing whitespace.
+    19	
.oracle/checkins/batch-1-r8.md:9196: trailing whitespace.
+    25	
.oracle/checkins/batch-1-r8.md:9198: trailing whitespace.
+    27	
.oracle/checkins/batch-1-r8.md:9200: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r8.md:9202: trailing whitespace.
+    31	
.oracle/checkins/batch-1-r8.md:9211: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r8.md:9213: trailing whitespace.
+    42	
.oracle/checkins/batch-1-r8.md:9220: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r8.md:9222: trailing whitespace.
+    51	
.oracle/checkins/batch-1-r8.md:9224: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r8.md:9226: trailing whitespace.
+    55	
.oracle/checkins/batch-1-r8.md:9234: trailing whitespace.
+    63	
.oracle/checkins/batch-1-r8.md:9236: trailing whitespace.
+    65	
.oracle/checkins/batch-1-r8.md:9243: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r8.md:9245: trailing whitespace.
+    74	
.oracle/checkins/batch-1-r8.md:9247: trailing whitespace.
+    76	
.oracle/checkins/batch-1-r8.md:9249: trailing whitespace.
+    78	
.oracle/checkins/batch-1-r8.md:9406: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r8.md:9407: trailing whitespace.
+   132	
.oracle/checkins/batch-1-r8.md:9437: trailing whitespace.
+   162	
.oracle/checkins/batch-1-r8.md:9438: trailing whitespace.
+   163	
.oracle/checkins/batch-1-r8.md:9453: trailing whitespace.
+   178	
.oracle/checkins/batch-1-r8.md:9454: trailing whitespace.
+   179	
.oracle/checkins/batch-1-r8.md:9481: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r8.md:9482: trailing whitespace.
+   207	
.oracle/checkins/batch-1-r8.md:9524: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r8.md:9525: trailing whitespace.
+   250	
.oracle/checkins/batch-1-r8.md:9563: trailing whitespace.
+   288	
.oracle/checkins/batch-1-r8.md:9564: trailing whitespace.
+   289	
.oracle/checkins/batch-1-r8.md:9661: trailing whitespace.
+   302	
.oracle/checkins/batch-1-r8.md:9662: trailing whitespace.
+   303	
.oracle/checkins/batch-1-r8.md:9671: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r8.md:9672: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r8.md:9689: trailing whitespace.
+   330	
.oracle/checkins/batch-1-r8.md:9690: trailing whitespace.
+   331	
.oracle/checkins/batch-1-r8.md:9702: trailing whitespace.
+   343	
.oracle/checkins/batch-1-r8.md:9703: trailing whitespace.
+   344	
.oracle/checkins/batch-1-r8.md:9764: trailing whitespace.
+   288	
.oracle/checkins/batch-1-r8.md:9779: trailing whitespace.
+    98	
.oracle/checkins/batch-1-r8.md:9782: trailing whitespace.
+   101	
.oracle/checkins/batch-1-r8.md:9787: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r8.md:9788: trailing whitespace.
+   107	
.oracle/checkins/batch-1-r8.md:9791: trailing whitespace.
+   110	
.oracle/checkins/batch-1-r8.md:9794: trailing whitespace.
+   113	
.oracle/checkins/batch-1-r8.md:9817: trailing whitespace.
+  1349	
.oracle/checkins/batch-1-r8.md:9818: trailing whitespace.
+  1350	
.oracle/checkins/batch-1-r8.md:9822: trailing whitespace.
+  1354	
.oracle/checkins/batch-1-r8.md:9833: trailing whitespace.
+  1365	
.oracle/checkins/batch-1-r8.md:9931: trailing whitespace.
+  1444	
.oracle/checkins/batch-1-r8.md:9947: trailing whitespace.
+  1460	

exec
/bin/zsh -lc 'git status --short --branch && git rev-parse HEAD && git log -3 --oneline --decorate' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## oracle-run
?? .oracle/checkins/batch-1-r9.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
788501c934fed0b0a85462418e77c021781681a9
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
788501c (HEAD -> oracle-run) batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
8418bae batch1-rework8: oracle re-review7 issues 1-3 (ordered path-keyed lineage w/ dup-path + cross-artifact attachment uniqueness, DTO reconstruction for attachments/profiles, trailing-LF schema anchors)
ab486f9 batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)

exec
/bin/zsh -lc 'tail -120 .oracle/checkins/batch-1-r8.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc "rg -n '"'^## Batch 1|''^### Batch 1|Batch 1|render backend|Rendering'"' .oracle/tasklist.md | head -40" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
3:## Batch 1 — Baseline, contracts, and discovery
178:- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.

exec
/bin/zsh -lc 'git diff --unified=4 8418bae..788501c -- astrid/core/rendering/schemas/v1' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'git diff --unified=80 8418bae..788501c -- astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py docs/contracts/render-backend-v1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index f21e12d..e959bf7 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -37,9 +37,9 @@
       }
     },
     "output_name": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
       "not": {
         "enum": [
           ".",
           ".."
@@ -55,22 +55,22 @@
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}\\Z"
+      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\r\\n]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "portableName": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
       "not": {
         "enum": [
           ".",
           ".."
@@ -81,9 +81,9 @@
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         {
           "type": "object"
         }
@@ -193,43 +193,43 @@
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
@@ -242,9 +242,9 @@
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
@@ -273,18 +273,18 @@
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
@@ -313,9 +313,9 @@
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "features": {
           "type": "object",
@@ -325,9 +325,9 @@
               "string"
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "alternatives": {
           "type": "array",
@@ -344,9 +344,9 @@
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         }
       }
     },
     "plannerResolution": {
@@ -377,9 +377,9 @@
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
@@ -430,9 +430,9 @@
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
@@ -477,9 +477,9 @@
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
@@ -511,9 +511,9 @@
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "renderSegment": {
       "type": "object",
@@ -582,14 +582,14 @@
         },
         "reasons": {
           "type": "object",
           "propertyNames": {
-            "pattern": "^(0|[1-9][0-9]*)\\Z"
+            "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
           },
           "additionalProperties": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "window": {
           "anyOf": [
@@ -651,9 +651,9 @@
           "$ref": "#/definitions/workspacePath"
         },
         "kind": {
           "type": "string",
-          "pattern": "^[a-z][a-z0-9-]*\\Z"
+          "pattern": "^[a-z][a-z0-9-]*(?![\\s\\S])"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         }
@@ -715,9 +715,9 @@
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
                   }
                 }
               }
             }
@@ -757,13 +757,13 @@
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "overrideRecord": {
       "type": "object",
diff --git a/astrid/core/rendering/schemas/v1/finalizer-manifest.json b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
index 0bde205..724ba56 100644
--- a/astrid/core/rendering/schemas/v1/finalizer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
@@ -22,14 +22,14 @@
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
@@ -38,9 +38,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "minItems": 1
     },
     "operations": {
@@ -63,9 +63,9 @@
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "capabilities": {
       "$ref": "#/definitions/finalizerCapabilities",
       "default": {}
@@ -78,9 +78,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "uniqueItems": true,
       "default": []
     },
@@ -95,23 +95,23 @@
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "permissions": {
       "type": "array",
       "items": {
@@ -134,9 +134,9 @@
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "preserves_attachments": {
@@ -162,14 +162,14 @@
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         }
       },
       "additionalProperties": false
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index 47bb576..f741238 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -49,14 +49,14 @@
     },
     "reasons": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(0|[1-9][0-9]*)\\Z"
+        "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "window": {
       "anyOf": [
@@ -102,20 +102,20 @@
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}\\Z"
+      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         {
           "type": "object"
         }
@@ -225,43 +225,43 @@
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
@@ -274,9 +274,9 @@
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
@@ -305,18 +305,18 @@
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
@@ -345,9 +345,9 @@
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "features": {
           "type": "object",
@@ -357,9 +357,9 @@
               "string"
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "alternatives": {
           "type": "array",
@@ -376,9 +376,9 @@
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         }
       }
     },
     "plannerResolution": {
@@ -409,9 +409,9 @@
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
@@ -462,9 +462,9 @@
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
@@ -509,9 +509,9 @@
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
@@ -543,9 +543,9 @@
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "renderSegment": {
       "type": "object",
diff --git a/astrid/core/rendering/schemas/v1/planner-manifest.json b/astrid/core/rendering/schemas/v1/planner-manifest.json
index 48e0756..fd436e7 100644
--- a/astrid/core/rendering/schemas/v1/planner-manifest.json
+++ b/astrid/core/rendering/schemas/v1/planner-manifest.json
@@ -22,14 +22,14 @@
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
@@ -38,9 +38,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "minItems": 1
     },
     "operations": {
@@ -63,9 +63,9 @@
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "capabilities": {
       "$ref": "#/definitions/plannerCapabilities",
       "default": {}
@@ -78,9 +78,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "uniqueItems": true,
       "default": []
     },
@@ -95,23 +95,23 @@
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "permissions": {
       "type": "array",
       "items": {
@@ -134,9 +134,9 @@
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "supports_fallback": {
@@ -150,14 +150,14 @@
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         }
       },
       "additionalProperties": false
diff --git a/astrid/core/rendering/schemas/v1/renderer-manifest.json b/astrid/core/rendering/schemas/v1/renderer-manifest.json
index b6cf411..b735227 100644
--- a/astrid/core/rendering/schemas/v1/renderer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/renderer-manifest.json
@@ -22,14 +22,14 @@
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
@@ -38,9 +38,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "minItems": 1
     },
     "operations": {
@@ -63,9 +63,9 @@
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "capabilities": {
       "$ref": "#/definitions/rendererCapabilities",
       "default": {}
@@ -78,9 +78,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "uniqueItems": true,
       "default": []
     },
@@ -95,23 +95,23 @@
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "permissions": {
       "type": "array",
       "items": {
@@ -134,18 +134,18 @@
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "track_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "features": {
@@ -156,14 +156,14 @@
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           }
         },
         "supports_full_timeline": {
           "type": "boolean"
@@ -175,9 +175,9 @@
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "audio_ownership": {
diff --git a/astrid/core/rendering/schemas/v1/request.json b/astrid/core/rendering/schemas/v1/request.json
index 575f0da..ebfcba1 100644
--- a/astrid/core/rendering/schemas/v1/request.json
+++ b/astrid/core/rendering/schemas/v1/request.json
@@ -16,21 +16,21 @@
     },
     "timeline_path": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "assets_registry_path": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "output_name": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
       "not": {
         "enum": [
           ".",
           ".."
@@ -100,9 +100,9 @@
             ],
             "properties": {
               "audio_codec": {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
               }
             }
           }
         }
@@ -147,9 +147,9 @@
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "audioOwnership": {
       "type": "string",
       "enum": [
@@ -254,43 +254,43 @@
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
@@ -303,9 +303,9 @@
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
@@ -334,18 +334,18 @@
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
@@ -361,13 +361,13 @@
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     }
   },
   "examples": [
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index 8a93ef7..5826c46 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -12,22 +12,22 @@
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
-      "pattern": "^[0-9a-f]{64}\\Z"
+      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\r\\n]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "portableName": {
       "type": "string",
-      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*\\Z",
+      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
       "not": {
         "enum": [
           ".",
           ".."
@@ -83,43 +83,43 @@
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
@@ -132,9 +132,9 @@
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
@@ -163,18 +163,18 @@
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
@@ -196,9 +196,9 @@
           "$ref": "#/definitions/workspacePath"
         },
         "kind": {
           "type": "string",
-          "pattern": "^[a-z][a-z0-9-]*\\Z"
+          "pattern": "^[a-z][a-z0-9-]*(?![\\s\\S])"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         }
@@ -260,9 +260,9 @@
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
                   }
                 }
               }
             }
@@ -352,19 +352,19 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "success": {
       "type": "object",
@@ -485,17 +485,17 @@
         },
         "message": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "recovery_command": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "details": {
           "type": "object"
         }
diff --git a/astrid/core/rendering/schemas/v1/support.json b/astrid/core/rendering/schemas/v1/support.json
index 49d7095..3df7cbd 100644
--- a/astrid/core/rendering/schemas/v1/support.json
+++ b/astrid/core/rendering/schemas/v1/support.json
@@ -25,9 +25,9 @@
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "features": {
       "type": "object",
@@ -37,9 +37,9 @@
           "string"
         ]
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
       }
     },
     "alternatives": {
       "type": "array",
@@ -56,15 +56,15 @@
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*\\Z"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
-      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+\\Z"
+      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     }
   },
   "examples": [
     {

 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index e8c06a4..c97f7d0 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -31,353 +31,365 @@ PROVENANCE_SCHEMA_VERSION = 2
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
             Attachment.from_dict(
                 {
                     "name": raw_attachment.name,
                     "path": raw_attachment.path,
                     "kind": raw_attachment.kind,
                     "sha256": raw_attachment.sha256,
                 }
             )
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
 
 
 def _reject_duplicate_attachment_names(
     lineage: Mapping[str, Any],
     seen: set[str],
 ) -> None:
     """Reject attachment names repeated across segment artifacts."""
     for name in (lineage.get("attachments") or {}):
         if name in seen:
             raise ValueError(
                 f"duplicate attachment name {name!r} across segment artifacts"
             )
         seen.add(name)
 
 
 def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
     if value is None:
         value = {}
     if isinstance(value, Mapping):
+        if segments and len(segments) > 1:
+            raise TypeError(
+                "mapping-form artifact_profiles is unordered; use sequence form "
+                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
+            )
         result: dict[str, Any] = {}
         seen_attachment_names: set[str] = set()
         for key, profile in value.items():
             path = _require_string(str(key), "artifact key")
             path = _require_workspace_relative_path(path, "artifact key")
             if isinstance(profile, VideoArtifact):
                 if path != profile.path:
                     raise ValueError(
                         f"artifact_profiles key {path!r} must equal VideoArtifact.path "
                         f"{profile.path!r}"
                     )
                 lineage = _artifact_lineage(profile)
             elif isinstance(profile, Mapping):
                 lineage = _artifact_lineage_from_mapping(profile, key=path)
             else:
                 raise TypeError(
                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                     "hashed lineage record {profile, sha256, attachments}; "
                     "profile-only entries carry no output hash"
                 )
             _reject_duplicate_attachment_names(lineage, seen_attachment_names)
             result[path] = lineage
         # A positive plan must record exactly one hashed artifact per segment.
         if segments:
             if len(result) != len(segments):
                 raise ValueError(
                     f"artifact_profiles must record exactly one hashed lineage entry "
                     f"per segment: expected {len(segments)}, got {len(result)}"
                 )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
         lineage: list[dict[str, Any]] = []
         seen_paths: set[str] = set()
         seen_attachment_names: set[str] = set()
         for profile in value:
             if not isinstance(profile, VideoArtifact):
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
                     "so lineage records stay path-keyed"
                 )
             if profile.path in seen_paths:
                 raise ValueError(
                     f"artifact_profiles sequence contains duplicate path "
                     f"{profile.path!r}"
                 )
             seen_paths.add(profile.path)
             record = _artifact_lineage(profile)
             _reject_duplicate_attachment_names(record, seen_attachment_names)
             lineage.append(record)
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
-    allowed = {"profile", "sha256", "attachments"}
+    allowed = {"profile", "sha256", "attachments", "path"}
     unknown = sorted(raw_keys - allowed)
     if unknown:
         raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
-    missing = sorted(allowed - raw_keys)
+    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
     if missing:
         raise ValueError(
             f"artifact lineage is missing required fields: {', '.join(missing)}"
         )
     if raw["sha256"] is None:
         raise ValueError("artifact lineage sha256 is required and must not be null")
     if not isinstance(raw["sha256"], str):
         raise TypeError("artifact lineage sha256 must be a string")
+    if "path" in raw:
+        embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
+        if embedded != key:
+            raise ValueError(
+                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
+            )
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
+        "path": raw["path"] if "path" in raw else key,
         "profile": RenderProfile.from_dict(
             _json_safe_mapping(profile, label="artifact profile")
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
-        plan
+        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
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
             artifact_profiles,
             segments=normalized_plan.segments,
         ),
         "audio_ownership": _normalize_audio_ownership(audio_ownership),
         "normalization": normalized_normalization,
         "finalizer": normalized_plan.finalizer.to_dict(),
         "attachments": _normalize_attachments(attachments),
         "backend_fragments": validate_backend_fragments(backend_fragments),
     }
     payload.update(compatibility)
     return _json_safe_mapping(payload, label="provenance")
 
 
 def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
     """Compatibility spelling for :func:`assemble_provenance_v2`."""
 
     return assemble_provenance_v2(**kwargs)
 
 
 def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
     """Assemble and atomically write a provenance v2 sidecar."""
 
     payload = assemble_provenance_v2(**kwargs)
     write_json_atomic(path, payload)
     return payload
 
 
 def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
     """Return stable SHA-256 input hashes using Astrid's shared helper."""
 
     return {
         _require_string(name, "input hash name"): sha256_file(Path(path))
         for name, path in paths.items()
     }
 
 
 def digest_manifest(path: str | Path) -> str:
     """Return the SHA-256 digest used to pin one static manifest."""
 
     return sha256_file(Path(path))
 
 
 __all__ = [
     "CORE_OWNED_KEYS",
     "PROVENANCE_SCHEMA_VERSION",
     "assemble_provenance",
     "assemble_provenance_v2",
     "digest_manifest",
     "hash_input_files",
     "validate_backend_fragments",
     "write_provenance_v2",
 ]
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index f98e1b1..88d822e 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -399,173 +399,173 @@ additional globally unique finalizer-created attachments are permitted.
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
 
 A `RendererError` contains:
 
 | Field | Meaning |
 | --- | --- |
 | `schema_version` | Required integer `1`. |
 | `kind` | One of `protocol`, `unsupported`, `binary_missing`, `timeout`, `interrupted`, `invalid_artifact`, or `internal`. |
 | `backend` | Qualified implementation ID; host validation uses `astrid.core`. |
 | `message` | Non-empty actionable message. |
 | `recovery_command` | Nullable concrete recovery command or action. |
 | `details` | JSON-safe structured evidence. |
 
 Unknown, missing, boolean, non-integer, or unsupported versions on requests,
 support reports, plans, finalize requests, successful results, and error
 results are always `kind="protocol"`. So are malformed request/result JSON and
 missing authoritative results. Unsupported timelines use `unsupported`; a
 missing manifest-declared executable uses `binary_missing`; deadline expiry
 uses `timeout`; transport cancellation uses `interrupted`; missing, escaping,
 empty, hash-mismatched, or media-incompatible outputs use
 `invalid_artifact`; unexpected implementation bugs use `internal`.
 
 The host cleans and reaps children before surfacing interruption. A real user
 SIGINT/`KeyboardInterrupt` is then re-raised so normal exit-130 behavior is
 preserved rather than converted into an unrelated exit-code layer.
 
 ## Lifecycle, publication, and cleanup
 
 The host lifecycle is:
 
 1. Resolve legacy selector/policy, aliases, overrides, and the precedence
    winner.
 2. Verify trust eligibility, permissions, manifest digest, required binaries,
    and supported protocol version.
 3. Resolve the canonical timeline profile and localize required inputs into a
    unique invocation workspace.
 4. Obtain static and, where available, request-sensitive support evidence.
 5. Invoke `render`, or invoke `plan` followed by each segment render.
 6. Parse only the authoritative result file and validate all artifacts.
 7. Invoke the explicit finalizer when required and validate again.
 8. Acquire the per-output publication lock, rename the final video, then
    atomically write the hashed provenance sidecar as the commit marker.
 9. Remove owned temporary state on success; retain only an explicitly
    requested workdir or failure replay bundle.
 
 Backend commands never create or own Astrid `run.json` ledgers. The facade or
 calling capability owns run attachment. Invocation workspaces, localized
 assets, props, generated fragments, servers, subprocess groups, and staging
 directories have one host owner and are cleaned on success, failure, timeout,
 and interruption. Cleanup must not follow an unvalidated path or delete
 unrelated prior output. A crash can leave an orphan video, but never a sidecar
 claiming an incomplete artifact; the sidecar is the publication commit marker.
 
 ## Provenance ownership and v1 compatibility
 
 Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
 
 `schema_version`, `engine`, `output`, `timeline`, `assets_registry`,
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
-hashed lineage entry PER SEGMENT, each keyed by a workspace-relative output
-path with exactly `{profile, sha256, attachments}` and a validated 64-hex
-string `sha256` on the artifact and every attachment `{path, kind, sha256}`.
-Sequence form preserves segment order (a path-keyed list) and rejects
-duplicate paths; mapping form requires path keys to equal the artifact's own
-path. Attachment paths must be workspace-relative, kinds must match
-`[a-z][a-z0-9-]*`, attachment map keys must equal the attachment's own name,
-and attachment names must be unique ACROSS all segment artifacts. Profile-only
-entries, null/malformed hashes, unknown or missing fields, path escapes,
-invalid kinds, duplicate paths, duplicate attachment names, and cardinality
-mismatches are all rejected; all Attachment and RenderProfile values are
-reconstructed through their DTO validators. Replay can verify rendered outputs
-byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
+hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
+sequence form (one VideoArtifact per segment); single-segment plans may use a
+path-keyed mapping. Every record carries its `path`, `profile`, a validated
+64-hex string `sha256`, and `attachments` — each attachment `{path, kind,
+sha256}` with a workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and
+globally unique names across all segment artifacts. All plan, artifact, and
+attachment values are reconstructed through their DTO validators at the
+provenance boundary (mutated frozen instances cannot bypass validation);
+duplicate paths, duplicate attachment names, path escapes, invalid kinds,
+profile-only entries, null/malformed hashes, and cardinality mismatches are
+rejected. All JSON Schema patterns are language-neutral (ECMAScript-valid;
+no Python-only anchors). Replay can verify rendered outputs byte-for-byte.
+`input_hashes` describe inputs only, never rendered outputs.
 
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
 
 `project_dir`, `composition_id`, `active_pack_order`, `active_theme`,
 `registry_hash`, `registry_state`, `resolved_effect_ids`, `resolved_effects`,
 `source_pack_ids`, `element_roots`, `staged_asset_ids`, `staged_asset_root`,
 optional `segment_provenance`, `ffmpeg_specialization`, and
 `audio_reactive_colour`, in addition to the already core-owned
 `schema_version`, `engine`, `output`, `timeline`, `assets_registry`, and
 `segments` names.
 
 The core assembler requires all historically always-emitted v1 fields on every
 call; it rejects a missing or partial compatibility projection. The three
 conditional fields (`segment_provenance`, `ffmpeg_specialization`, and
 `audio_reactive_colour`) remain conditional on the applicable render path.
 
 Backend-owned data appears only under `backend_fragments[qualified_id]`. Before
 assembly, core rejects a fragment whose top-level member collides with any v2
 or v1 core-owned name. Retired singular v2 names such as `resolved_backend`,
 `source_pack`, `manifest_digest`, `support_decision`, and `input_hashes` remain
 reserved so a fragment cannot revive an ambiguous authority surface. Backends
 cannot replace routing, identity, inputs, segments, artifacts, audio,
 finalization, or compatibility projections.
 Provenance JSON is written with Astrid's atomic JSON helper; file and manifest
 digests use the shared chunked SHA-256 helper.
 
 ## Replay inputs and redaction
 
 A failed invocation can be replayed without rerunning the editorial pipeline.
 The retained bundle contains:
 
 - the resolved request or finalize request;
 - localized timeline, asset registry, and required inputs with hashes;
 - only the selected implementation's configuration namespace;
 - qualified implementation, source pack, version, manifest digest, trust and
   resolution evidence;
 - support report and render plan, when present;
 - redacted captured logs;
 - authoritative result or partial result, if one exists;
 - the exact replay command using absolute request/result bundle paths.
 
 The bundle pins the qualified implementation and request/input/manifest
 digests. Implementation drift must be reported and explicitly acknowledged;
 replay never silently resolves another backend. Credentials, authorization
 headers, private environment values, and signed URL query strings are removed.
 Successful disposable workspaces are deleted unless the caller explicitly
 requests retention. V1 defines no cleanup daemon or TTL service.
 
 ## Versioning
 
 Schema paths and `schema_version` are independent of an implementation's
 `version`. V1 readers accept only integer version `1`; they do not guess,
 coerce, or silently down-convert unknown versions. The version is required on
 `RenderRequest`, `SupportReport`, `RenderPlan`, `FinalizeRequest`, successful
 `RenderResult`, and `RendererError`; missing, boolean, malformed, and unknown
 values are rejected on every operation. Additive backend-private data belongs
 in fragments, not new core fields. A new required core field, operation,
 asynchronous lifecycle, different path semantics, or incompatible media
 meaning requires a new protocol/schema version and parallel schemas.
 
 M2 may wrap these types, provide helpers, scaffold code, and improve error
 presentation. It must emit the same JSON. If tooling finds a kernel defect,
 M1 is amended and re-reviewed rather than creating an SDK-only dialect.
 
 ## Locked epic decisions (verbatim)
 
 1. **Backend, planner, and finalizer are distinct concepts.** `hybrid` is a
    planning policy, not a renderer backend.
 2. **The timeline remains backend-neutral.** Renderer selection is invocation
    or plan configuration, never an arbitrary module path stored in timeline
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 55df8a5..2195b2b 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -487,558 +487,594 @@ def test_finalize_rejects_dropped_or_changed_attachments() -> None:
     with pytest.raises(ValueError, match="changed attachments"):
         request.validate_final_result(_result(video=_video(attachments={changed.name: changed})))
 
 
 def test_attachment_mapping_key_must_match_name() -> None:
     with pytest.raises(ValueError, match="must match attachment.name"):
         _video(attachments={"other.blend": _attachment("project.blend")})
 
 
 @pytest.mark.parametrize(
     "path",
     [
         "../escape.mp4",
         "outputs/../../escape.mp4",
         "outputs/./escape.mp4",
         "outputs//escape.mp4",
         "outputs/",
         "/tmp/escape.mp4",
         "C:escape.mp4",
         r"C:\\temp\\escape.mp4",
         r"\\\\server\\share\\escape.mp4",
     ],
 )
 def test_artifact_path_traversal_and_windows_drives_rejected(path: str) -> None:
     with pytest.raises(ValueError, match="workspace|contained|relative"):
         _video(path=path)
 
 
 def test_backend_fragment_cannot_overwrite_current_or_retired_core_keys() -> None:
     for key in ("output", "planner", "resolved_backend", "request_digest"):
         with pytest.raises(ValueError, match=f"core-owned keys: {key}"):
             validate_backend_fragments({"acme.example": {key: "stolen"}})
 
 
 def _compatibility() -> dict[str, Any]:
     return {
         "project_dir": "/workspace/remotion",
         "composition_id": "TimelineComposition",
         "active_pack_order": [],
         "active_theme": None,
         "registry_hash": SHA_B,
         "registry_state": {},
         "resolved_effect_ids": [],
         "resolved_effects": [],
         "source_pack_ids": [],
         "element_roots": [],
         "staged_asset_ids": [],
         "staged_asset_root": None,
         "segment_provenance": [{"engine": "spoofed", "from": -1, "to": -1}],
         "ffmpeg_specialization": None,
         "audio_reactive_colour": None,
     }
 
 
 def test_provenance_requires_always_emitted_v1_projection() -> None:
     with pytest.raises(ValueError, match="v1_compatibility is required"):
         assemble_provenance_v2(
             engine="remotion",
             output="/workspace/video.mp4",
             timeline="/workspace/timeline.json",
             assets_registry=None,
             plan=_plan(),
         )
 
 
 def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
     compatibility = _compatibility()
     assert set(compatibility) == set(PROVENANCE_V1_COMPATIBILITY_KEYS)
     plan = _plan(
         segments=[
             _segment(0, 24, backend="acme.first", digest=SHA_B),
             _segment(24, 48, backend="other.second", digest=SHA_C),
         ]
     )
     kwargs = {
         "engine": "hybrid",
         "output": "/workspace/out/video.mp4",
         "timeline": "/workspace/timeline.json",
         "assets_registry": "/workspace/assets.json",
         "plan": plan,
-        "artifact_profiles": {
-            "outputs/video.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_B,
-                "attachments": {},
-            },
-            "outputs/segment2.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_C,
-                "attachments": {},
-            },
-        },
+        "artifact_profiles": [
+            VideoArtifact(
+                path="outputs/video.mp4",
+                profile=_profile(),
+                sha256=SHA_B,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+            VideoArtifact(
+                path="outputs/segment2.mp4",
+                profile=_profile(),
+                sha256=SHA_C,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+        ],
         "audio_ownership": AudioOwnership.RENDERED,
         "normalization": [],
         "attachments": {},
         "backend_fragments": {"acme.first": {"vendor": "Acme"}},
         "v1_compatibility": compatibility,
     }
     payload = assemble_provenance_v2(**kwargs)
     assert payload["schema_version"] == 2
     assert payload["request_digest"] == SHA_D
     assert payload["requested_policy"] == "hybrid"
     assert payload["planner"] == _planner().to_dict()
     assert [segment["renderer"]["id"] for segment in payload["segments_v2"]] == [
         "acme.first",
         "other.second",
     ]
     assert payload["segments_v2"] == [segment.to_dict() for segment in plan.segments]
     assert [set(segment) for segment in payload["segments_v2"]] == [
         {"window", "renderer", "input_hashes"},
         {"window", "renderer", "input_hashes"},
     ]
     # V1-compatible projections are preserved unchanged.
     assert payload["segments"] == [
         {"engine": "first", "from": 0.0, "to": 1.0},
         {"engine": "second", "from": 1.0, "to": 2.0},
     ]
     # segment_provenance passes through from the v1 compatibility projection
     # verbatim — the host never rewrites it.
     assert payload["segment_provenance"] == compatibility["segment_provenance"]
     assert payload["finalizer"] == _finalizer().to_dict()
     assert payload["composition_id"] == "TimelineComposition"
 
     sidecar = tmp_path / "video.mp4.provenance.json"
     assert write_provenance_v2(sidecar, **kwargs) == payload
     assert sidecar.read_text(encoding="utf-8").endswith("\n")
 
 
 def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None:
     plan = _plan().to_dict()
     plan["segments"][0]["engine"] = "spoofed"
     with pytest.raises(RendererProtocolError):
         assemble_provenance_v2(
             engine="hybrid",
             output="out/video.mp4",
             timeline="timeline.json",
             assets_registry=None,
             plan=plan,
             v1_compatibility=_compatibility(),
         )
 
 
 def test_compute_request_digest_is_canonical_and_stable() -> None:
     from astrid.core.rendering.contracts import compute_request_digest
 
     a = {"backend_config": {"acme.visual": {"quality": "preview"}}, "schema_version": 1}
     b = {"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}}}
     assert compute_request_digest(a) == compute_request_digest(b)
     digest = compute_request_digest(a)
     assert isinstance(digest, str)
     assert len(digest) == 64
     assert compute_request_digest({**a, "metadata": {"x": "y"}}) != digest
     assert compute_request_digest({"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}, "other.key": {}}}) != digest
 
 
 def test_shared_sha256_helper_is_used_for_input_hashes(tmp_path: Path) -> None:
     input_path = tmp_path / "timeline.json"
     input_path.write_text("abc", encoding="utf-8")
     hashes = hash_input_files({"timeline": input_path})
     assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
 
 
 def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
     """Non-default alias/override/trust/support evidence must survive the
     plan wire round-trip and the final provenance sidecar."""
     planner = replace(
         _planner(),
         alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
         override={"from": "acme.hybrid-planner", "to": "rendering.legacy_hybrid"},
         support_decision=_support("rendering.legacy_hybrid"),
     )
     renderer = replace(
         _renderer("acme.visual"),
         alias_chain=["visual", "acme.visual"],
         override={"from": "acme.visual-2", "to": "acme.visual"},
         trust_eligibility={"eligible": True, "method": "source-tree"},
     )
     finalizer = replace(
         _finalizer(),
         alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
         override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
         trust_eligibility={"eligible": True, "method": "source-tree"},
         support_decision=_support("rendering.ffmpeg-finalizer"),
     )
     plan = _plan(
         planner=planner,
         segments=[
             _segment(0, 24, renderer=renderer),
             _segment(24, 48),
         ],
         finalizer=finalizer,
     )
 
     # Wire round-trip
     reparsed = RenderPlan.from_dict(plan.to_dict())
     assert reparsed.planner.alias_chain == planner.alias_chain
     assert reparsed.planner.override == planner.override
     assert reparsed.planner.support_decision is not None
     assert reparsed.segments[0].renderer.trust_eligibility == renderer.trust_eligibility
     assert reparsed.finalizer.alias_chain == finalizer.alias_chain
     assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
     assert reparsed.finalizer.support_decision is not None
 
     # Provenance sidecar carries the same evidence
     payload = assemble_provenance_v2(
         engine="hybrid",
         output="/workspace/out/video.mp4",
         timeline="/workspace/timeline.json",
         assets_registry=None,
         plan=plan,
-        artifact_profiles={
-            "outputs/visual.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_B,
-                "attachments": {},
-            },
-            "outputs/segment2.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_C,
-                "attachments": {},
-            }
-        },
+        artifact_profiles=[
+            VideoArtifact(
+                path="outputs/visual.mp4",
+                profile=_profile(),
+                sha256=SHA_B,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+            VideoArtifact(
+                path="outputs/segment2.mp4",
+                profile=_profile(),
+                sha256=SHA_C,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+        ],
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     assert payload["planner"]["alias_chain"] == planner.alias_chain
     assert payload["planner"]["override"] == planner.override
     assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
     assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
     assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
     assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
 
 
 def test_resolution_records_require_all_seven_evidence_keys() -> None:
     """Every capability resolution requires the complete evidence set;
     a missing key is a structural protocol failure."""
 def test_resolution_records_require_all_seven_evidence_keys() -> None:
     """Every capability resolution requires the complete evidence set;
     a missing key is a structural protocol failure."""
     cases = (
         (_planner(), PlannerResolution.from_dict),
         (_finalizer(), FinalizerResolution.from_dict),
         (_renderer(), RendererResolution.from_dict),
     )
     for obj, parser in cases:
         for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
             broken = obj.to_dict()
             del broken[missing]
             with pytest.raises(ValueError, match="missing required fields"):
                 parser(broken)
 
 
 def test_provenance_emits_hashed_artifact_lineage() -> None:
     """Provenance records per-artifact sha256 and attachment hashes, not
     just profiles — so replay can verify rendered outputs byte-for-byte."""
     artifact = VideoArtifact(
         path="outputs/visual.mp4",
         profile=_profile(),
         sha256=SHA_B,
         duration_frames=48,
         audio=AudioOwnership.RENDERED,
         attachments={
             "alpha": Attachment(
                 name="alpha",
                 path="outputs/alpha.mp4",
                 kind="alpha",
                 sha256=SHA_C,
             )
         },
     )
     payload = assemble_provenance_v2(
         engine="hybrid",
         output="/workspace/out/video.mp4",
         timeline="/workspace/timeline.json",
         assets_registry=None,
         plan=_plan(),
         artifact_profiles={"outputs/visual.mp4": artifact},
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
     assert lineage["sha256"] == SHA_B
     assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
     assert lineage["attachments"]["alpha"]["kind"] == "alpha"
 
 
 def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
     """support_decision.backend must equal the resolution id for planner and
     finalizer, exactly as it does for renderer."""
     cases = (
         (_planner, "planner"),
         (_finalizer, "finalizer"),
         (_renderer, "renderer"),
     )
     for factory, label in cases:
         payload = factory().to_dict()
         payload["support_decision"] = _support("other.backend").to_dict()
         with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
             type(factory()).from_dict(payload)
 
 
 def test_resolutions_reject_incoherent_override_records() -> None:
     """Override records must be {from, to} with to == resolution id."""
     cases = (
         (_planner, "planner"),
         (_finalizer, "finalizer"),
         (_renderer, "renderer"),
     )
     for factory, label in cases:
         payload = factory().to_dict()
         payload["override"] = {"from": "other.origin", "to": "not.the.id"}
         with pytest.raises(ValueError, match=f"{label} override 'to'"):
             type(factory()).from_dict(payload)
         payload["override"] = {"only": "one"}
         with pytest.raises(ValueError, match=f"{label} override"):
             type(factory()).from_dict(payload)
 
 
 def test_provenance_rejects_spoofed_artifact_lineage() -> None:
     """Artifact lineage must carry a real sha256; profile-only entries and
     null hashes are rejected rather than stringified."""
     base = dict(
         engine="hybrid",
         output="/workspace/out/video.mp4",
         timeline="/workspace/timeline.json",
         assets_registry=None,
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
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
-            artifact_profiles={
-                "out/v.mp4": {
-                    "profile": _profile(),
-                    "sha256": SHA_B,
-                    "attachments": {},
-                }
-            },
+            artifact_profiles=[
+                VideoArtifact(
+                    path="outputs/v.mp4",
+                    profile=_profile(),
+                    sha256=SHA_B,
+                    duration_frames=24,
+                    audio=AudioOwnership.RENDERED,
+                )
+            ],
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
     with pytest.raises(ValueError, match="duplicate attachment name"):
         assemble_provenance_v2(
             **base,
             plan=_plan(
                 segments=[_segment(0, 24), _segment(24, 48)]
             ),
-            artifact_profiles={
-                "out/v1.mp4": {
-                    "profile": _profile(),
-                    "sha256": SHA_B,
-                    "attachments": {
-                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
+            artifact_profiles=[
+                VideoArtifact(
+                    path="outputs/v1.mp4",
+                    profile=_profile(),
+                    sha256=SHA_B,
+                    duration_frames=24,
+                    audio=AudioOwnership.RENDERED,
+                    attachments={
+                        "alpha": Attachment(
+                            name="alpha",
+                            path="outputs/a.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
                     },
-                },
-                "out/v2.mp4": {
-                    "profile": _profile(),
-                    "sha256": SHA_D,
-                    "attachments": {
-                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
+                ),
+                VideoArtifact(
+                    path="outputs/v2.mp4",
+                    profile=_profile(),
+                    sha256=SHA_D,
+                    duration_frames=24,
+                    audio=AudioOwnership.RENDERED,
+                    attachments={
+                        "alpha": Attachment(
+                            name="alpha",
+                            path="outputs/a2.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
                     },
-                },
-            },
+                ),
+            ],
         )
     with pytest.raises(ValueError, match="workspace path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
         )
     with pytest.raises(ValueError, match="duplicate path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(
                 segments=[_segment(0, 24), _segment(24, 48)]
             ),
             artifact_profiles=[
                 VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
                 VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
             ],
         )
+    # A mutated RenderPlan instance is reconstructed at the boundary, so
+    # clearing its segments cannot bypass the positive-plan invariant.
+    with pytest.raises(RendererProtocolError, match="positive-frame plan"):
+        positive = _plan()
+        object.__setattr__(positive, "segments", [])
+        assemble_provenance_v2(
+            **base,
+            plan=positive,
+            artifact_profiles=[],
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

exec
/bin/zsh -lc "sed -n '1,220p' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '1,390p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   111	        if segments and len(segments) > 1:
   112	            raise TypeError(
   113	                "mapping-form artifact_profiles is unordered; use sequence form "
   114	                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
   115	            )
   116	        result: dict[str, Any] = {}
   117	        seen_attachment_names: set[str] = set()
   118	        for key, profile in value.items():
   119	            path = _require_string(str(key), "artifact key")
   120	            path = _require_workspace_relative_path(path, "artifact key")
   121	            if isinstance(profile, VideoArtifact):
   122	                if path != profile.path:
   123	                    raise ValueError(
   124	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
   125	                        f"{profile.path!r}"
   126	                    )
   127	                lineage = _artifact_lineage(profile)
   128	            elif isinstance(profile, Mapping):
   129	                lineage = _artifact_lineage_from_mapping(profile, key=path)
   130	            else:
   131	                raise TypeError(
   132	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   133	                    "hashed lineage record {profile, sha256, attachments}; "
   134	                    "profile-only entries carry no output hash"
   135	                )
   136	            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
   137	            result[path] = lineage
   138	        # A positive plan must record exactly one hashed artifact per segment.
   139	        if segments:
   140	            if len(result) != len(segments):
   141	                raise ValueError(
   142	                    f"artifact_profiles must record exactly one hashed lineage entry "
   143	                    f"per segment: expected {len(segments)}, got {len(result)}"
   144	                )
   145	        return result
   146	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   147	        lineage: list[dict[str, Any]] = []
   148	        seen_paths: set[str] = set()
   149	        seen_attachment_names: set[str] = set()
   150	        for profile in value:
   151	            if not isinstance(profile, VideoArtifact):
   152	                raise TypeError(
   153	                    "sequence artifact_profiles entries must be VideoArtifacts "
   154	                    "so lineage records stay path-keyed"
   155	                )
   156	            if profile.path in seen_paths:
   157	                raise ValueError(
   158	                    f"artifact_profiles sequence contains duplicate path "
   159	                    f"{profile.path!r}"
   160	                )
   161	            seen_paths.add(profile.path)
   162	            record = _artifact_lineage(profile)
   163	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   164	            lineage.append(record)
   165	        if segments:
   166	            if len(lineage) != len(segments):
   167	                raise ValueError(
   168	                    f"artifact_profiles must record exactly one hashed lineage entry "
   169	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   170	                )
   171	        return lineage
   172	    raise TypeError("artifact_profiles must be an object or array")
   173	
   174	
   175	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   176	    raw_keys = set(raw)
   177	    allowed = {"profile", "sha256", "attachments", "path"}
   178	    unknown = sorted(raw_keys - allowed)
   179	    if unknown:
   180	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   181	    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
   182	    if missing:
   183	        raise ValueError(
   184	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   185	        )
   186	    if raw["sha256"] is None:
   187	        raise ValueError("artifact lineage sha256 is required and must not be null")
   188	    if not isinstance(raw["sha256"], str):
   189	        raise TypeError("artifact lineage sha256 must be a string")
   190	    if "path" in raw:
   191	        embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
   192	        if embedded != key:
   193	            raise ValueError(
   194	                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
   195	            )
   196	    profile = raw["profile"]
   197	    attachments: dict[str, Any] = {}
   198	    raw_attachments = raw["attachments"]
   199	    if raw_attachments is None:
   200	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   201	    if not isinstance(raw_attachments, Mapping):
   202	        raise TypeError("artifact lineage attachments must be an object")
   203	    for name, att in raw_attachments.items():
   204	        name = _require_string(name, "attachment name")
   205	        if isinstance(att, Attachment):
   206	            if att.name != name:
   207	                raise ValueError(
   208	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   209	                )
   210	            att = {
   211	                "path": att.path,
   212	                "kind": att.kind,
   213	                "sha256": att.sha256,
   214	            }
   215	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   216	        if att_unknown:
   217	            raise ValueError(
   218	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   219	            )
   220	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   221	        if att_missing:
   222	            raise ValueError(
   223	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   224	            )
   225	        if not isinstance(att["sha256"], str):
   226	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   227	        # Validate through the Attachment DTO so workspace-path containment and
   228	        # kind grammar are enforced uniformly for raw and dataclass values.
   229	        validated = Attachment(
   230	            name=name,
   231	            path=att["path"],
   232	            kind=att["kind"],
   233	            sha256=att["sha256"],
   234	        )
   235	        attachments[name] = {
   236	            "path": validated.path,
   237	            "kind": validated.kind,
   238	            "sha256": validated.sha256,
   239	        }
   240	    return {
   241	        "path": raw["path"] if "path" in raw else key,
   242	        "profile": RenderProfile.from_dict(
   243	            _json_safe_mapping(profile, label="artifact profile")
   244	        ).to_dict(),
   245	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   246	        "attachments": attachments,
   247	    }
   248	
   249	
   250	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   251	    """One hashed artifact lineage record: profile, sha256, attachments."""
   252	    return _artifact_lineage_from_mapping(
   253	        {
   254	            "profile": artifact.profile,
   255	            "sha256": artifact.sha256,
   256	            "attachments": artifact.attachments,
   257	        },
   258	        key=artifact.path,
   259	    )
   260	
   261	
   262	def _normalize_v1_compatibility(
   263	    fields: Mapping[str, Any] | None,
   264	) -> dict[str, Any]:
   265	    if fields is None:
   266	        raise ValueError(
   267	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   268	        )
   269	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   270	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   271	    if unknown:
   272	        raise ValueError(
   273	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   274	            + ", ".join(unknown)
   275	        )
   276	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   277	    if missing:
   278	        raise ValueError(
   279	            "v1 compatibility projection is missing always-emitted fields: "
   280	            + ", ".join(missing)
   281	        )
   282	    return compatibility
   283	
   284	
   285	def assemble_provenance_v2(
   286	    *,
   287	    engine: str,
   288	    output: str | Path,
   289	    timeline: str | Path,
   290	    assets_registry: str | Path | None,
   291	    plan: RenderPlan | Mapping[str, Any],
   292	    artifact_profiles: Any = None,
   293	    audio_ownership: AudioOwnership | str | None = None,
   294	    normalization: Sequence[str] = (),
   295	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   296	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   297	    v1_compatibility: Mapping[str, Any] | None = None,
   298	) -> dict[str, Any]:
   299	    """Assemble additive provenance v2 with protected ownership boundaries.
   300	
   301	    ``engine`` is intentionally the legacy request projection. Routing and
   302	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   303	    hybrid invocation cannot collapse multiple renderer identities. Optional
   304	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   305	    any v2 core field.
   306	    """
   307	
   308	    legacy_engine = _require_string(engine, "engine")
   309	    output_path = _require_string(str(output), "output")
   310	    timeline_path = _require_string(str(timeline), "timeline")
   311	    assets_path = None if assets_registry is None else _require_string(
   312	        str(assets_registry), "assets_registry"
   313	    )
   314	    normalized_plan = (
   315	        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
   316	        if isinstance(plan, RenderPlan)
   317	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   318	    )
   319	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   320	    legacy_segments = [
   321	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   322	    ]
   323	    normalized_normalization = [
   324	        _require_string(item, f"normalization[{index}]")
   325	        for index, item in enumerate(normalization)
   326	    ]
   327	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   328	
   329	    payload: dict[str, Any] = {
   330	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   331	        "engine": legacy_engine,
   332	        "output": output_path,
   333	        "timeline": timeline_path,
   334	        "assets_registry": assets_path,
   335	        "request_digest": normalized_plan.request_digest,
   336	        "requested_policy": normalized_plan.requested_policy,
   337	        "planner": normalized_plan.planner.to_dict(),
   338	        # V1-compatible segment projection: flat {engine, from, to} entries,
   339	        # exactly the shape legacy consumers read from `segments`.
   340	        "segments": legacy_segments,
   341	        # Additive normalized v2 segment records; never overwrite v1 fields.
   342	        "segments_v2": normalized_segments,
   343	        "artifact_profiles": _normalize_artifact_profiles(
   344	            artifact_profiles,
   345	            segments=normalized_plan.segments,
   346	        ),
   347	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   348	        "normalization": normalized_normalization,
   349	        "finalizer": normalized_plan.finalizer.to_dict(),
   350	        "attachments": _normalize_attachments(attachments),
   351	        "backend_fragments": validate_backend_fragments(backend_fragments),
   352	    }
   353	    payload.update(compatibility)
   354	    return _json_safe_mapping(payload, label="provenance")
   355	
   356	
   357	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   358	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   359	
   360	    return assemble_provenance_v2(**kwargs)
   361	
   362	
   363	def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
   364	    """Assemble and atomically write a provenance v2 sidecar."""
   365	
   366	    payload = assemble_provenance_v2(**kwargs)
   367	    write_json_atomic(path, payload)
   368	    return payload
   369	
   370	
   371	def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
   372	    """Return stable SHA-256 input hashes using Astrid's shared helper."""
   373	
   374	    return {
   375	        _require_string(name, "input hash name"): sha256_file(Path(path))
   376	        for name, path in paths.items()
   377	    }
   378	
   379	
   380	def digest_manifest(path: str | Path) -> str:
   381	    """Return the SHA-256 digest used to pin one static manifest."""
   382	
   383	    return sha256_file(Path(path))
   384	
   385	
   386	__all__ = [
   387	    "CORE_OWNED_KEYS",
   388	    "PROVENANCE_SCHEMA_VERSION",
   389	    "assemble_provenance",
   390	    "assemble_provenance_v2",

exec
/bin/zsh -lc "rg -n \"mutat|artifact_profiles|workspacePath|ECMAScript|portable|sequence\" tests/core/rendering/test_contracts.py tests/core/rendering -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_contracts.py:567:        "artifact_profiles": [
tests/core/rendering/test_contracts.py:701:        artifact_profiles=[
tests/core/rendering/test_contracts.py:774:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:781:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:835:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:841:            artifact_profiles={
tests/core/rendering/test_contracts.py:849:            artifact_profiles={
tests/core/rendering/test_contracts.py:861:            artifact_profiles={
tests/core/rendering/test_contracts.py:876:            artifact_profiles=[
tests/core/rendering/test_contracts.py:890:            artifact_profiles={
tests/core/rendering/test_contracts.py:904:            artifact_profiles={
tests/core/rendering/test_contracts.py:920:            artifact_profiles={
tests/core/rendering/test_contracts.py:941:            artifact_profiles=[
tests/core/rendering/test_contracts.py:978:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:986:            artifact_profiles=[
tests/core/rendering/test_contracts.py:991:    # A mutated RenderPlan instance is reconstructed at the boundary, so
tests/core/rendering/test_contracts.py:999:            artifact_profiles=[],
tests/core/rendering/test_contracts.py:567:        "artifact_profiles": [
tests/core/rendering/test_contracts.py:701:        artifact_profiles=[
tests/core/rendering/test_contracts.py:774:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:781:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:835:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:841:            artifact_profiles={
tests/core/rendering/test_contracts.py:849:            artifact_profiles={
tests/core/rendering/test_contracts.py:861:            artifact_profiles={
tests/core/rendering/test_contracts.py:876:            artifact_profiles=[
tests/core/rendering/test_contracts.py:890:            artifact_profiles={
tests/core/rendering/test_contracts.py:904:            artifact_profiles={
tests/core/rendering/test_contracts.py:920:            artifact_profiles={
tests/core/rendering/test_contracts.py:941:            artifact_profiles=[
tests/core/rendering/test_contracts.py:978:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:986:            artifact_profiles=[
tests/core/rendering/test_contracts.py:991:    # A mutated RenderPlan instance is reconstructed at the boundary, so
tests/core/rendering/test_contracts.py:999:            artifact_profiles=[],

exec
/bin/zsh -lc "rg -n -F '\\\\Z' astrid/core/rendering/schemas || true; rg -n 'workspacePath' astrid/core/rendering/schemas/v1/*.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
astrid/core/rendering/schemas/v1/result.json:196:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/result.json:227:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
astrid/core/rendering/schemas/v1/finalize.json:651:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/finalize.json:682:          "$ref": "#/definitions/workspacePath"

codex
A concrete gap is emerging in the lineage fix: the sequence path is emitted but appears not to be revalidated when a frozen `VideoArtifact` is adversarially mutated. I’m reproducing that against the public provenance boundary and checking whether any other schema/runtime parity gap accompanies it.
exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '650,1025p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   650	    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
   651	
   652	
   653	def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
   654	    """Non-default alias/override/trust/support evidence must survive the
   655	    plan wire round-trip and the final provenance sidecar."""
   656	    planner = replace(
   657	        _planner(),
   658	        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
   659	        override={"from": "acme.hybrid-planner", "to": "rendering.legacy_hybrid"},
   660	        support_decision=_support("rendering.legacy_hybrid"),
   661	    )
   662	    renderer = replace(
   663	        _renderer("acme.visual"),
   664	        alias_chain=["visual", "acme.visual"],
   665	        override={"from": "acme.visual-2", "to": "acme.visual"},
   666	        trust_eligibility={"eligible": True, "method": "source-tree"},
   667	    )
   668	    finalizer = replace(
   669	        _finalizer(),
   670	        alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
   671	        override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
   672	        trust_eligibility={"eligible": True, "method": "source-tree"},
   673	        support_decision=_support("rendering.ffmpeg-finalizer"),
   674	    )
   675	    plan = _plan(
   676	        planner=planner,
   677	        segments=[
   678	            _segment(0, 24, renderer=renderer),
   679	            _segment(24, 48),
   680	        ],
   681	        finalizer=finalizer,
   682	    )
   683	
   684	    # Wire round-trip
   685	    reparsed = RenderPlan.from_dict(plan.to_dict())
   686	    assert reparsed.planner.alias_chain == planner.alias_chain
   687	    assert reparsed.planner.override == planner.override
   688	    assert reparsed.planner.support_decision is not None
   689	    assert reparsed.segments[0].renderer.trust_eligibility == renderer.trust_eligibility
   690	    assert reparsed.finalizer.alias_chain == finalizer.alias_chain
   691	    assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
   692	    assert reparsed.finalizer.support_decision is not None
   693	
   694	    # Provenance sidecar carries the same evidence
   695	    payload = assemble_provenance_v2(
   696	        engine="hybrid",
   697	        output="/workspace/out/video.mp4",
   698	        timeline="/workspace/timeline.json",
   699	        assets_registry=None,
   700	        plan=plan,
   701	        artifact_profiles=[
   702	            VideoArtifact(
   703	                path="outputs/visual.mp4",
   704	                profile=_profile(),
   705	                sha256=SHA_B,
   706	                duration_frames=24,
   707	                audio=AudioOwnership.RENDERED,
   708	            ),
   709	            VideoArtifact(
   710	                path="outputs/segment2.mp4",
   711	                profile=_profile(),
   712	                sha256=SHA_C,
   713	                duration_frames=24,
   714	                audio=AudioOwnership.RENDERED,
   715	            ),
   716	        ],
   717	        audio_ownership="rendered",
   718	        normalization=[],
   719	        attachments={},
   720	        backend_fragments={},
   721	        v1_compatibility=_compatibility(),
   722	    )
   723	    assert payload["planner"]["alias_chain"] == planner.alias_chain
   724	    assert payload["planner"]["override"] == planner.override
   725	    assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
   726	    assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
   727	    assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
   728	    assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
   729	
   730	
   731	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   732	    """Every capability resolution requires the complete evidence set;
   733	    a missing key is a structural protocol failure."""
   734	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   735	    """Every capability resolution requires the complete evidence set;
   736	    a missing key is a structural protocol failure."""
   737	    cases = (
   738	        (_planner(), PlannerResolution.from_dict),
   739	        (_finalizer(), FinalizerResolution.from_dict),
   740	        (_renderer(), RendererResolution.from_dict),
   741	    )
   742	    for obj, parser in cases:
   743	        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
   744	            broken = obj.to_dict()
   745	            del broken[missing]
   746	            with pytest.raises(ValueError, match="missing required fields"):
   747	                parser(broken)
   748	
   749	
   750	def test_provenance_emits_hashed_artifact_lineage() -> None:
   751	    """Provenance records per-artifact sha256 and attachment hashes, not
   752	    just profiles — so replay can verify rendered outputs byte-for-byte."""
   753	    artifact = VideoArtifact(
   754	        path="outputs/visual.mp4",
   755	        profile=_profile(),
   756	        sha256=SHA_B,
   757	        duration_frames=48,
   758	        audio=AudioOwnership.RENDERED,
   759	        attachments={
   760	            "alpha": Attachment(
   761	                name="alpha",
   762	                path="outputs/alpha.mp4",
   763	                kind="alpha",
   764	                sha256=SHA_C,
   765	            )
   766	        },
   767	    )
   768	    payload = assemble_provenance_v2(
   769	        engine="hybrid",
   770	        output="/workspace/out/video.mp4",
   771	        timeline="/workspace/timeline.json",
   772	        assets_registry=None,
   773	        plan=_plan(),
   774	        artifact_profiles={"outputs/visual.mp4": artifact},
   775	        audio_ownership="rendered",
   776	        normalization=[],
   777	        attachments={},
   778	        backend_fragments={},
   779	        v1_compatibility=_compatibility(),
   780	    )
   781	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
   782	    assert lineage["sha256"] == SHA_B
   783	    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
   784	    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
   785	
   786	
   787	def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
   788	    """support_decision.backend must equal the resolution id for planner and
   789	    finalizer, exactly as it does for renderer."""
   790	    cases = (
   791	        (_planner, "planner"),
   792	        (_finalizer, "finalizer"),
   793	        (_renderer, "renderer"),
   794	    )
   795	    for factory, label in cases:
   796	        payload = factory().to_dict()
   797	        payload["support_decision"] = _support("other.backend").to_dict()
   798	        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
   799	            type(factory()).from_dict(payload)
   800	
   801	
   802	def test_resolutions_reject_incoherent_override_records() -> None:
   803	    """Override records must be {from, to} with to == resolution id."""
   804	    cases = (
   805	        (_planner, "planner"),
   806	        (_finalizer, "finalizer"),
   807	        (_renderer, "renderer"),
   808	    )
   809	    for factory, label in cases:
   810	        payload = factory().to_dict()
   811	        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
   812	        with pytest.raises(ValueError, match=f"{label} override 'to'"):
   813	            type(factory()).from_dict(payload)
   814	        payload["override"] = {"only": "one"}
   815	        with pytest.raises(ValueError, match=f"{label} override"):
   816	            type(factory()).from_dict(payload)
   817	
   818	
   819	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   820	    """Artifact lineage must carry a real sha256; profile-only entries and
   821	    null hashes are rejected rather than stringified."""
   822	    base = dict(
   823	        engine="hybrid",
   824	        output="/workspace/out/video.mp4",
   825	        timeline="/workspace/timeline.json",
   826	        assets_registry=None,
   827	        audio_ownership="rendered",
   828	        normalization=[],
   829	        attachments={},
   830	        backend_fragments={},
   831	        v1_compatibility=_compatibility(),
   832	    )
   833	    with pytest.raises(TypeError, match="hashed lineage"):
   834	        assemble_provenance_v2(
   835	            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
   836	        )
   837	    with pytest.raises(ValueError, match="sha256"):
   838	        assemble_provenance_v2(
   839	            **base,
   840	            plan=_plan(),
   841	            artifact_profiles={
   842	                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
   843	            },
   844	        )
   845	    with pytest.raises(ValueError, match="sha256"):
   846	        assemble_provenance_v2(
   847	            **base,
   848	            plan=_plan(),
   849	            artifact_profiles={
   850	                "out/v.mp4": {
   851	                    "profile": _profile(),
   852	                    "sha256": "not-a-hash",
   853	                    "attachments": {},
   854	                }
   855	            },
   856	        )
   857	    with pytest.raises(ValueError, match="unknown fields"):
   858	        assemble_provenance_v2(
   859	            **base,
   860	            plan=_plan(),
   861	            artifact_profiles={
   862	                "out/v.mp4": {
   863	                    "profile": _profile(),
   864	                    "sha256": SHA_B,
   865	                    "attachments": {},
   866	                    "spoof": 1,
   867	                }
   868	            },
   869	        )
   870	    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
   871	        assemble_provenance_v2(
   872	            **base,
   873	            plan=_plan(
   874	                segments=[_segment(0, 24), _segment(24, 48)]
   875	            ),
   876	            artifact_profiles=[
   877	                VideoArtifact(
   878	                    path="outputs/v.mp4",
   879	                    profile=_profile(),
   880	                    sha256=SHA_B,
   881	                    duration_frames=24,
   882	                    audio=AudioOwnership.RENDERED,
   883	                )
   884	            ],
   885	        )
   886	    with pytest.raises(ValueError, match="attachment path"):
   887	        assemble_provenance_v2(
   888	            **base,
   889	            plan=_plan(),
   890	            artifact_profiles={
   891	                "out/v.mp4": {
   892	                    "profile": _profile(),
   893	                    "sha256": SHA_B,
   894	                    "attachments": {
   895	                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
   896	                    },
   897	                },
   898	            },
   899	        )
   900	    with pytest.raises(ValueError, match="attachment kind"):
   901	        assemble_provenance_v2(
   902	            **base,
   903	            plan=_plan(),
   904	            artifact_profiles={
   905	                "out/v.mp4": {
   906	                    "profile": _profile(),
   907	                    "sha256": SHA_B,
   908	                    "attachments": {
   909	                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
   910	                    },
   911	                },
   912	            },
   913	        )
   914	
   915	
   916	    with pytest.raises(ValueError, match="must equal Attachment.name"):
   917	        assemble_provenance_v2(
   918	            **base,
   919	            plan=_plan(),
   920	            artifact_profiles={
   921	                "out/v.mp4": {
   922	                    "profile": _profile(),
   923	                    "sha256": SHA_B,
   924	                    "attachments": {
   925	                        "different_key": Attachment(
   926	                            name="alpha",
   927	                            path="outputs/alpha.mp4",
   928	                            kind="alpha",
   929	                            sha256=SHA_C,
   930	                        )
   931	                    },
   932	                }
   933	            },
   934	        )
   935	    with pytest.raises(ValueError, match="duplicate attachment name"):
   936	        assemble_provenance_v2(
   937	            **base,
   938	            plan=_plan(
   939	                segments=[_segment(0, 24), _segment(24, 48)]
   940	            ),
   941	            artifact_profiles=[
   942	                VideoArtifact(
   943	                    path="outputs/v1.mp4",
   944	                    profile=_profile(),
   945	                    sha256=SHA_B,
   946	                    duration_frames=24,
   947	                    audio=AudioOwnership.RENDERED,
   948	                    attachments={
   949	                        "alpha": Attachment(
   950	                            name="alpha",
   951	                            path="outputs/a.mp4",
   952	                            kind="alpha",
   953	                            sha256=SHA_C,
   954	                        )
   955	                    },
   956	                ),
   957	                VideoArtifact(
   958	                    path="outputs/v2.mp4",
   959	                    profile=_profile(),
   960	                    sha256=SHA_D,
   961	                    duration_frames=24,
   962	                    audio=AudioOwnership.RENDERED,
   963	                    attachments={
   964	                        "alpha": Attachment(
   965	                            name="alpha",
   966	                            path="outputs/a2.mp4",
   967	                            kind="alpha",
   968	                            sha256=SHA_C,
   969	                        )
   970	                    },
   971	                ),
   972	            ],
   973	        )
   974	    with pytest.raises(ValueError, match="workspace path"):
   975	        assemble_provenance_v2(
   976	            **base,
   977	            plan=_plan(),
   978	            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
   979	        )
   980	    with pytest.raises(ValueError, match="duplicate path"):
   981	        assemble_provenance_v2(
   982	            **base,
   983	            plan=_plan(
   984	                segments=[_segment(0, 24), _segment(24, 48)]
   985	            ),
   986	            artifact_profiles=[
   987	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
   988	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
   989	            ],
   990	        )
   991	    # A mutated RenderPlan instance is reconstructed at the boundary, so
   992	    # clearing its segments cannot bypass the positive-plan invariant.
   993	    with pytest.raises(RendererProtocolError, match="positive-frame plan"):
   994	        positive = _plan()
   995	        object.__setattr__(positive, "segments", [])
   996	        assemble_provenance_v2(
   997	            **base,
   998	            plan=positive,
   999	            artifact_profiles=[],
  1000	        )
  1001	
  1002	
  1003	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
  1004	    plan = _plan(
  1005	        segments=[_segment(12, 24), _segment(24, 36)],
  1006	        total_frames=48,
  1007	        window=_window(12, 36),
  1008	    )
  1009	    assert plan.total_frames == 48
  1010	    assert plan.window == _window(12, 36)
  1011	
  1012	
  1013	@pytest.mark.parametrize(
  1014	    ("segments", "total_frames", "match"),
  1015	    [
  1016	        ([_segment(1, 48)], 48, "gap"),
  1017	        ([_segment(0, 47)], 48, "trailing gap"),
  1018	        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
  1019	        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
  1020	        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
  1021	    ],
  1022	)
  1023	def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
  1024	    segments: list[RenderSegment],
  1025	    total_frames: int,

exec
/bin/zsh -lc "rg -n 'artifact_profiles|VideoArtifact|lineage' docs/contracts/render-backend-v1.md | head -80" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
242:`VideoArtifact` with:
271:match its non-null `VideoArtifact.audio`. Visual-only renderers are valid and
282:`VideoArtifact.attachments` is the one authoritative attachment surface;
468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
479:hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
480:sequence form (one VideoArtifact per segment); single-segment plans may use a

exec
/bin/zsh -lc "git diff --numstat 8418bae..788501c -- ':"'!.oracle/checkins/batch-1-r8.md'"' && git show --format=fuller --no-patch 788501c" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
15	3	astrid/core/rendering/provenance.py
28	28	astrid/core/rendering/schemas/v1/finalize.json
11	11	astrid/core/rendering/schemas/v1/finalizer-manifest.json
21	21	astrid/core/rendering/schemas/v1/plan.json
11	11	astrid/core/rendering/schemas/v1/planner-manifest.json
13	13	astrid/core/rendering/schemas/v1/renderer-manifest.json
16	16	astrid/core/rendering/schemas/v1/request.json
20	20	astrid/core/rendering/schemas/v1/result.json
4	4	astrid/core/rendering/schemas/v1/support.json
13	13	docs/contracts/render-backend-v1.md
81	45	tests/core/rendering/test_contracts.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 788501c934fed0b0a85462418e77c021781681a9
Author:     POM <peter@omalley.io>
AuthorDate: Wed Aug 12 04:39:08 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Wed Aug 12 04:39:08 2026 +0200

    batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)

exec
/bin/zsh -lc "rg -n \"class VideoArtifact|def from_dict\\(cls, payload.*VideoArtifact|class Attachment|class RenderProfile|def _require_workspace_relative_path\" astrid/core/rendering/contracts.py && nl -ba astrid/core/rendering/contracts.py | sed -n '285,340p' && nl -ba astrid/core/rendering/contracts.py | sed -n '820,1040p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
314:def _require_workspace_relative_path(value: Any, label: str) -> str:
443:class RenderProfile:
585:class Attachment:
658:class VideoArtifact:
704:    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
   285	
   286	def _require_schema_version(value: Any, label: str) -> int:
   287	    if type(value) is not int or value != SCHEMA_VERSION:
   288	        _protocol_failure(
   289	            f"unknown or malformed {label} schema_version {value!r}; "
   290	            f"expected integer {SCHEMA_VERSION}",
   291	            details={"received": value, "supported": [SCHEMA_VERSION]},
   292	        )
   293	    return value
   294	
   295	
   296	def _require_rational(value: Any, label: str) -> tuple[int, int]:
   297	    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
   298	        raise TypeError(f"{label} must be a two-item [numerator, denominator] array")
   299	    numerator = _require_int(value[0], f"{label}[0]", minimum=1)
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
   820	                "audio": self.audio,
   821	                "profile": self.profile,
   822	                "backend_config": self.backend_config,
   823	                "metadata": self.metadata,
   824	            }
   825	        )
   826	
   827	    @classmethod
   828	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderRequest:
   829	        try:
   830	            data = _require_mapping(payload, "render request")
   831	            allowed = {
   832	                "schema_version",
   833	                "timeline_path",
   834	                "assets_registry_path",
   835	                "output_name",
   836	                "window",
   837	                "audio",
   838	                "profile",
   839	                "backend_config",
   840	                "metadata",
   841	            }
   842	            _validate_object_keys(
   843	                data,
   844	                required={"schema_version", "timeline_path", "output_name"},
   845	                allowed=allowed,
   846	                label="render request",
   847	            )
   848	            version = data["schema_version"]
   849	            if type(version) is not int or version != SCHEMA_VERSION:
   850	                _protocol_failure(
   851	                    f"unknown or malformed render request schema_version {version!r}; "
   852	                    f"expected integer {SCHEMA_VERSION}",
   853	                    details={"received": version, "supported": [SCHEMA_VERSION]},
   854	                )
   855	            return cls(
   856	                schema_version=version,
   857	                timeline_path=data["timeline_path"],
   858	                assets_registry_path=data.get("assets_registry_path"),
   859	                output_name=data["output_name"],
   860	                window=data.get("window"),
   861	                audio=data.get("audio"),
   862	                profile=data.get("profile"),
   863	                backend_config=data.get("backend_config", {}),
   864	                metadata=data.get("metadata", {}),
   865	            )
   866	        except Exception as exc:
   867	            from .errors import RendererException
   868	
   869	            if isinstance(exc, RendererException):
   870	                raise
   871	            _protocol_failure(
   872	                f"malformed render request: {exc}",
   873	                details={"error_type": type(exc).__name__},
   874	            )
   875	
   876	    def for_backend(self, backend: str) -> RenderRequest:
   877	        """Return the request projection visible to one selected backend."""
   878	
   879	        qualified = _require_qualified_id(backend, "backend")
   880	        selected = self.backend_config.get(qualified)
   881	        return RenderRequest(
   882	            schema_version=self.schema_version,
   883	            timeline_path=self.timeline_path,
   884	            assets_registry_path=self.assets_registry_path,
   885	            output_name=self.output_name,
   886	            window=self.window,
   887	            audio=self.audio,
   888	            profile=self.profile,
   889	            backend_config={qualified: selected} if selected is not None else {},
   890	            metadata=self.metadata,
   891	        )
   892	
   893	
   894	@dataclass(frozen=True)
   895	class SupportReport:
   896	    """Request-sensitive support evidence returned by an implementation."""
   897	
   898	    schema_version: int
   899	    supported: bool
   900	    reasons: list[str]
   901	    features: dict[str, bool | str]
   902	    alternatives: list[str]
   903	    backend: str
   904	    backend_version: str | None = None
   905	
   906	    def __post_init__(self) -> None:
   907	        object.__setattr__(
   908	            self,
   909	            "schema_version",
   910	            _require_schema_version(self.schema_version, "support report"),
   911	        )
   912	        if not isinstance(self.supported, bool):
   913	            raise TypeError("supported must be a boolean")
   914	        object.__setattr__(self, "reasons", _require_string_list(self.reasons, "reasons"))
   915	        feature_mapping = _require_mapping(self.features, "features")
   916	        features: dict[str, bool | str] = {}
   917	        for raw_key, raw_value in feature_mapping.items():
   918	            key = _require_string(raw_key, "feature key")
   919	            if not isinstance(raw_value, (bool, str)):
   920	                raise TypeError(f"features[{key!r}] must be a boolean or string")
   921	            features[key] = raw_value
   922	        object.__setattr__(self, "features", features)
   923	        alternatives = [
   924	            _require_qualified_id(item, f"alternatives[{index}]")
   925	            for index, item in enumerate(_require_string_list(self.alternatives, "alternatives"))
   926	        ]
   927	        if len(alternatives) != len(set(alternatives)):
   928	            raise ValueError("alternatives must not contain duplicate backend ids")
   929	        object.__setattr__(self, "alternatives", alternatives)
   930	        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "backend"))
   931	        object.__setattr__(
   932	            self,
   933	            "backend_version",
   934	            _require_optional_string(self.backend_version, "backend_version"),
   935	        )
   936	
   937	    def to_dict(self) -> dict[str, Any]:
   938	        return _json_safe_mapping(
   939	            {
   940	                "schema_version": self.schema_version,
   941	                "supported": self.supported,
   942	                "reasons": self.reasons,
   943	                "features": self.features,
   944	                "alternatives": self.alternatives,
   945	                "backend": self.backend,
   946	                "backend_version": self.backend_version,
   947	            }
   948	        )
   949	
   950	    @classmethod
   951	    def from_dict(cls, payload: Mapping[str, Any]) -> SupportReport:
   952	        try:
   953	            data = _require_mapping(payload, "support report")
   954	            required = {
   955	                "schema_version",
   956	                "supported",
   957	                "reasons",
   958	                "features",
   959	                "alternatives",
   960	                "backend",
   961	                "backend_version",
   962	            }
   963	            _validate_object_keys(
   964	                data,
   965	                required=required,
   966	                allowed=required,
   967	                label="support report",
   968	            )
   969	            return cls(
   970	                schema_version=data["schema_version"],
   971	                supported=data["supported"],
   972	                reasons=data["reasons"],
   973	                features=data["features"],
   974	                alternatives=data["alternatives"],
   975	                backend=data["backend"],
   976	                backend_version=data["backend_version"],
   977	            )
   978	        except Exception as exc:
   979	            from .errors import RendererException
   980	
   981	            if isinstance(exc, RendererException):
   982	                raise
   983	            _protocol_failure(
   984	                f"malformed support report: {exc}",
   985	                details={"error_type": type(exc).__name__},
   986	            )
   987	
   988	
   989	@dataclass(frozen=True)
   990	class PlannerResolution:
   991	    """Resolved planner identity and trust evidence frozen into a plan."""
   992	
   993	    id: str
   994	    source_pack: dict[str, Any]
   995	    manifest_digest: str
   996	    trust_eligibility: dict[str, Any]
   997	    alias_chain: list[str] = field(default_factory=list)
   998	    override: dict[str, Any] | None = None
   999	    support_decision: SupportReport | None = None
  1000	
  1001	    def __post_init__(self) -> None:
  1002	        object.__setattr__(self, "id", _require_qualified_id(self.id, "planner id"))
  1003	        object.__setattr__(
  1004	            self,
  1005	            "source_pack",
  1006	            _json_safe_mapping(self.source_pack, label="planner source_pack"),
  1007	        )
  1008	        object.__setattr__(
  1009	            self,
  1010	            "manifest_digest",
  1011	            _require_sha256(self.manifest_digest, "planner manifest_digest"),
  1012	        )
  1013	        object.__setattr__(
  1014	            self,
  1015	            "trust_eligibility",
  1016	            _json_safe_mapping(
  1017	                self.trust_eligibility,
  1018	                label="planner trust_eligibility",
  1019	            ),
  1020	        )
  1021	        object.__setattr__(
  1022	            self,
  1023	            "alias_chain",
  1024	            [
  1025	                _require_string(item, f"planner alias_chain[{index}]")
  1026	                for index, item in enumerate(_require_string_list(self.alias_chain, "planner alias_chain"))
  1027	            ],
  1028	        )
  1029	        if self.override is not None:
  1030	            object.__setattr__(
  1031	                self,
  1032	                "override",
  1033	                _require_override(
  1034	                    self.override,
  1035	                    capability_id=self.id,
  1036	                    label="planner override",
  1037	                ),
  1038	            )
  1039	        if self.support_decision is not None:
  1040	            support = (

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '430,735p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   430	            allowed={"start_frame", "end_frame", "fps_rational", "source_range", "speed"},
   431	            label="frame window",
   432	        )
   433	        return cls(
   434	            start_frame=data["start_frame"],
   435	            end_frame=data["end_frame"],
   436	            fps_rational=data["fps_rational"],
   437	            source_range=data.get("source_range"),
   438	            speed=data.get("speed"),
   439	        )
   440	
   441	
   442	@dataclass(frozen=True)
   443	class RenderProfile:
   444	    """Resolved media profile used to validate and finalize artifacts."""
   445	
   446	    width: int
   447	    height: int
   448	    fps_rational: tuple[int, int]
   449	    time_base: tuple[int, int]
   450	    video_codec: str
   451	    pixel_format: str
   452	    video_profile: str | None = None
   453	    video_level: str | None = None
   454	    container: str = "mp4"
   455	    audio_codec: str | None = None
   456	    audio_sample_rate: int | None = None
   457	    audio_channel_layout: str | None = None
   458	    duration_tolerance: int = 1
   459	
   460	    def __post_init__(self) -> None:
   461	        object.__setattr__(self, "width", _require_int(self.width, "width", minimum=1))
   462	        object.__setattr__(self, "height", _require_int(self.height, "height", minimum=1))
   463	        object.__setattr__(self, "fps_rational", _require_rational(self.fps_rational, "fps_rational"))
   464	        object.__setattr__(self, "time_base", _require_rational(self.time_base, "time_base"))
   465	        object.__setattr__(self, "video_codec", _require_string(self.video_codec, "video_codec"))
   466	        object.__setattr__(self, "pixel_format", _require_string(self.pixel_format, "pixel_format"))
   467	        object.__setattr__(
   468	            self,
   469	            "video_profile",
   470	            _require_optional_string(self.video_profile, "video_profile"),
   471	        )
   472	        object.__setattr__(
   473	            self,
   474	            "video_level",
   475	            _require_optional_string(self.video_level, "video_level"),
   476	        )
   477	        object.__setattr__(self, "container", _require_string(self.container, "container"))
   478	        audio_values = (
   479	            self.audio_codec,
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
   731	            path=relative,
   732	            profile=profile,
   733	            sha256=sha256_file(resolved),
   734	            duration_frames=duration_frames,
   735	            audio=audio,

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '225,295p'; nl -ba docs/contracts/render-backend-v1.md | sed -n '455,510p'; nl -ba .oracle/tasklist.md | sed -n '1,105p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   225	
   226	The host owns asset resolution and localization. Request input paths may be
   227	absolute after localization. The timeline and optional registry remain the
   228	canonical replay inputs; remote URLs and cached assets are materialized or
   229	made available by later host plumbing according to declared permissions.
   230	
   231	Artifact paths in results have a different rule: they are normalized paths
   232	relative to the unique invocation workspace. They cannot be absolute, begin
   233	with a Windows drive prefix such as `C:`, contain backslashes, UNC prefixes,
   234	`.` or `..` traversal, empty path components, trailing separators, or NUL. The
   235	host resolves the path, rejects symlink escapes, requires the expected file or
   236	directory, and verifies its hash before publication. This relative rule lets
   237	the same result and replay bundle move between machines.
   238	
   239	## Primary video, media, and audio ownership
   240	
   241	Every successful render and finalization result contains exactly one primary
   242	`VideoArtifact` with:
   243	
   244	- a contained relative `path`;
   245	- the probed `RenderProfile`;
   246	- lowercase 64-character `sha256`;
   247	- positive `duration_frames`;
   248	- artifact `audio` ownership (nullable only before it is wrapped in a successful
   249	  result);
   250	- optional named attachments (default `{}`).
   251	
   252	The host validates existence, non-empty output, workspace containment,
   253	symlinks, digest, duration, dimensions, FPS/time base, container, codecs,
   254	pixel format, and declared audio state before assembly or publication.
   255	
   256	Audio ownership values have precise meanings:
   257	
   258	- `rendered`: the backend owns and returns final timeline audio in the video;
   259	- `passthrough`: the backend returns visual media and asks Astrid to preserve
   260	  or mux the canonical source/timeline audio;
   261	- `none`: the intended output has no audio.
   262	
   263	The probed profile and artifact ownership are coupled. `rendered` requires the
   264	complete populated audio trio because the returned artifact contains audio.
   265	`passthrough` and `none` require a visual-only profile: passthrough asks the
   266	host/finalizer to supply canonical audio later, while none declares that no
   267	audio is intended. When a request supplies both non-null fields, it follows the
   268	same relationship; it may leave audio or profile `null` for a backend/host
   269	default.
   270	A successful `RenderResult.audio_ownership` is never null and must exactly
   271	match its non-null `VideoArtifact.audio`. Visual-only renderers are valid and
   272	are never required to synthesize silence. The host/finalizer, not an arbitrary
   273	backend, owns passthrough, muxing, normalization, or compatibility silence.
   274	
   275	## Attachments
   276	
   277	An `Attachment` has `name`, relative contained `path`, extensible lowercase
   278	hyphenated `kind`, and `sha256`. Typical kinds include `alpha`, `depth`,
   279	`frames`, `audio-stem`, and `project`; the list is illustrative, not an enum.
   280	
   281	Attachments are maps keyed by name. The key must equal `Attachment.name`.
   282	`VideoArtifact.attachments` is the one authoritative attachment surface;
   283	`RenderResult` has no second attachment map. Names must be globally unique
   284	across every segment artifact in one `FinalizeRequest`, even when two
   285	descriptors are otherwise identical. Planners and finalizers preserve every
   286	input attachment's name, path, kind, and hash unchanged. A finalizer may add a
   287	new attachment, and a custom finalizer may interpret a kind only when its
   288	contract explicitly says so, but it may not silently drop, rename, or mutate an
   289	input attachment.
   290	
   291	## Successful render result
   292	
   293	`RenderResult` has `schema_version: 1`, the primary `video` (including its
   294	attachments), qualified-ID-keyed `backend_fragments`, explicit
   295	`audio_ownership`, `normalization` descriptions, redacted `logs`, and string
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
   479	hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
   480	sequence form (one VideoArtifact per segment); single-segment plans may use a
   481	path-keyed mapping. Every record carries its `path`, `profile`, a validated
   482	64-hex string `sha256`, and `attachments` — each attachment `{path, kind,
   483	sha256}` with a workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and
   484	globally unique names across all segment artifacts. All plan, artifact, and
   485	attachment values are reconstructed through their DTO validators at the
   486	provenance boundary (mutated frozen instances cannot bypass validation);
   487	duplicate paths, duplicate attachment names, path escapes, invalid kinds,
   488	profile-only entries, null/malformed hashes, and cardinality mismatches are
   489	rejected. All JSON Schema patterns are language-neutral (ECMAScript-valid;
   490	no Python-only anchors). Replay can verify rendered outputs byte-for-byte.
   491	`input_hashes` describe inputs only, never rendered outputs.
   492	
   493	`engine` is only the legacy request projection. The `segments` key keeps the
   494	V1-compatible flat projection: one `{engine, from, to}` entry per segment,
   495	derived from `renderer.id` and the validated integer `FrameWindow` at its
   496	rational FPS — exactly the shape legacy consumers read. The additive
   497	`segments_v2` key carries the complete normalized v2 segment records
   498	(`window`, `renderer` resolution, `input_hashes`); it never overwrites or
   499	reshapes a V1 key. When the v1 `segment_provenance` top-level projection
   500	applies, core passes it through VERBATIM from the caller's compatibility
   501	projection — it is never rewritten or re-derived.
   502	
   503	For the whole epic, core also preserves every current v1 top-level projection:
   504	
   505	`project_dir`, `composition_id`, `active_pack_order`, `active_theme`,
   506	`registry_hash`, `registry_state`, `resolved_effect_ids`, `resolved_effects`,
   507	`source_pack_ids`, `element_roots`, `staged_asset_ids`, `staged_asset_root`,
   508	optional `segment_provenance`, `ffmpeg_specialization`, and
   509	`audio_reactive_colour`, in addition to the already core-owned
   510	`schema_version`, `engine`, `output`, `timeline`, `assets_registry`, and
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
    79	- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
    80	- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
    81	- `output_name` uses existing input placeholders and cache/CAS identity, rejects separators/traversal/non-MP4 extensions, preserves declared output names, and leaves Hype’s default `hype.mp4` sentinel unchanged.
    82	- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
    83	- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
    84	- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
    85	- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.
    86	
    87	### Tasks
    88	
    89	- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
    90	- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
    91	- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
    92	- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
    93	- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
    94	
    95	## Batch 5 — Caller migration, semantic parity, and M1 freeze
    96	
    97	**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.
    98	
    99	**Acceptance criteria:**
   100	
   101	- The attached-child helper requires a validated parent project/run and unique step, scopes and restores all three `ASTRID_TASK_*` variables, preserves caller-selected output, honors facade overrides, and falls back to public `RenderService` only without a project ledger.
   102	- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
   103	- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
   104	- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
   105	- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json, runpy
from pathlib import Path
import jsonschema
from astrid.core.rendering.contracts import _require_workspace_relative_path, VideoArtifact, AudioOwnership
from astrid.core.rendering.provenance import assemble_provenance_v2
ns = runpy.run_path(\"tests/core/rendering/test_contracts.py\")
plan = ns[\"_plan\"](segments=[ns[\"_segment\"](0, 24), ns[\"_segment\"](24, 48)])
a1 = VideoArtifact(path=\"outputs/a.mp4\", profile=ns[\"_profile\"](), sha256=ns[\"SHA_B\"], duration_frames=24, audio=AudioOwnership.RENDERED)
a2 = VideoArtifact(path=\"outputs/b.mp4\", profile=ns[\"_profile\"](), sha256=ns[\"SHA_C\"], duration_frames=24, audio=AudioOwnership.RENDERED)
object.__setattr__(a1, \"path\", \"../escape.mp4\")
payload = assemble_provenance_v2(engine=\"hybrid\", output=\"/workspace/out/video.mp4\", timeline=\"/workspace/timeline.json\", assets_registry=None, plan=plan, artifact_profiles=[a1, a2], audio_ownership=\"rendered\", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=ns[\"_compatibility\"]())
print(\"mutated artifact accepted:\", payload[\"artifact_profiles\"][0][\"path\"])
for schema_name in (\"result.json\", \"finalize.json\"):
    schema = json.loads((Path(\"astrid/core/rendering/schemas/v1\") / schema_name).read_text())[\"definitions\"][\"workspacePath\"]
    validator = jsonschema.Draft7Validator(schema)
    print(schema_name)
    for value in (\" /video.mp4\", \"\\t/video.mp4\", \"dir/\\v/video.mp4\", \"dir/\\f/video.mp4\", \"dir/\\u00a0/video.mp4\", \" content /video.mp4\"):
        try:
            _require_workspace_relative_path(value, \"path\")
            dto = True
        except Exception:
            dto = False
        print(repr(value), \"schema=\", validator.is_valid(value), \"dto=\", dto)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 235ms:
mutated artifact accepted: ../escape.mp4
result.json
' /video.mp4' schema= True dto= False
'\t/video.mp4' schema= True dto= False
'dir/\x0b/video.mp4' schema= True dto= False
'dir/\x0c/video.mp4' schema= True dto= False
'dir/\xa0/video.mp4' schema= True dto= False
' content /video.mp4' schema= True dto= True
finalize.json
' /video.mp4' schema= True dto= False
'\t/video.mp4' schema= True dto= False
'dir/\x0b/video.mp4' schema= True dto= False
'dir/\x0c/video.mp4' schema= True dto= False
'dir/\xa0/video.mp4' schema= True dto= False
' content /video.mp4' schema= True dto= True

exec
/bin/zsh -lc 'git diff --unified=12 8418bae..788501c -- tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 55df8a5..2195b2b 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -555,36 +555,40 @@ def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: P
     plan = _plan(
         segments=[
             _segment(0, 24, backend="acme.first", digest=SHA_B),
             _segment(24, 48, backend="other.second", digest=SHA_C),
         ]
     )
     kwargs = {
         "engine": "hybrid",
         "output": "/workspace/out/video.mp4",
         "timeline": "/workspace/timeline.json",
         "assets_registry": "/workspace/assets.json",
         "plan": plan,
-        "artifact_profiles": {
-            "outputs/video.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_B,
-                "attachments": {},
-            },
-            "outputs/segment2.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_C,
-                "attachments": {},
-            },
-        },
+        "artifact_profiles": [
+            VideoArtifact(
+                path="outputs/video.mp4",
+                profile=_profile(),
+                sha256=SHA_B,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+            VideoArtifact(
+                path="outputs/segment2.mp4",
+                profile=_profile(),
+                sha256=SHA_C,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+        ],
         "audio_ownership": AudioOwnership.RENDERED,
         "normalization": [],
         "attachments": {},
         "backend_fragments": {"acme.first": {"vendor": "Acme"}},
         "v1_compatibility": compatibility,
     }
     payload = assemble_provenance_v2(**kwargs)
     assert payload["schema_version"] == 2
     assert payload["request_digest"] == SHA_D
     assert payload["requested_policy"] == "hybrid"
     assert payload["planner"] == _planner().to_dict()
     assert [segment["renderer"]["id"] for segment in payload["segments_v2"]] == [
@@ -685,36 +689,40 @@ def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
     assert reparsed.segments[0].renderer.trust_eligibility == renderer.trust_eligibility
     assert reparsed.finalizer.alias_chain == finalizer.alias_chain
     assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
     assert reparsed.finalizer.support_decision is not None
 
     # Provenance sidecar carries the same evidence
     payload = assemble_provenance_v2(
         engine="hybrid",
         output="/workspace/out/video.mp4",
         timeline="/workspace/timeline.json",
         assets_registry=None,
         plan=plan,
-        artifact_profiles={
-            "outputs/visual.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_B,
-                "attachments": {},
-            },
-            "outputs/segment2.mp4": {
-                "profile": _profile(),
-                "sha256": SHA_C,
-                "attachments": {},
-            }
-        },
+        artifact_profiles=[
+            VideoArtifact(
+                path="outputs/visual.mp4",
+                profile=_profile(),
+                sha256=SHA_B,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+            VideoArtifact(
+                path="outputs/segment2.mp4",
+                profile=_profile(),
+                sha256=SHA_C,
+                duration_frames=24,
+                audio=AudioOwnership.RENDERED,
+            ),
+        ],
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     assert payload["planner"]["alias_chain"] == planner.alias_chain
     assert payload["planner"]["override"] == planner.override
     assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
     assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
     assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
     assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
@@ -856,31 +864,33 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
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
-            artifact_profiles={
-                "out/v.mp4": {
-                    "profile": _profile(),
-                    "sha256": SHA_B,
-                    "attachments": {},
-                }
-            },
+            artifact_profiles=[
+                VideoArtifact(
+                    path="outputs/v.mp4",
+                    profile=_profile(),
+                    sha256=SHA_B,
+                    duration_frames=24,
+                    audio=AudioOwnership.RENDERED,
+                )
+            ],
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
@@ -919,58 +929,84 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
                             sha256=SHA_C,
                         )
                     },
                 }
             },
         )
     with pytest.raises(ValueError, match="duplicate attachment name"):
         assemble_provenance_v2(
             **base,
             plan=_plan(
                 segments=[_segment(0, 24), _segment(24, 48)]
             ),
-            artifact_profiles={
-                "out/v1.mp4": {
-                    "profile": _profile(),
-                    "sha256": SHA_B,
-                    "attachments": {
-                        "alpha": {"path": "outputs/a.mp4", "kind": "alpha", "sha256": SHA_C}
+            artifact_profiles=[
+                VideoArtifact(
+                    path="outputs/v1.mp4",
+                    profile=_profile(),
+                    sha256=SHA_B,
+                    duration_frames=24,
+                    audio=AudioOwnership.RENDERED,
+                    attachments={
+                        "alpha": Attachment(
+                            name="alpha",
+                            path="outputs/a.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
                     },
-                },
-                "out/v2.mp4": {
-                    "profile": _profile(),
-                    "sha256": SHA_D,
-                    "attachments": {
-                        "alpha": {"path": "outputs/a2.mp4", "kind": "alpha", "sha256": SHA_C}
+                ),
+                VideoArtifact(
+                    path="outputs/v2.mp4",
+                    profile=_profile(),
+                    sha256=SHA_D,
+                    duration_frames=24,
+                    audio=AudioOwnership.RENDERED,
+                    attachments={
+                        "alpha": Attachment(
+                            name="alpha",
+                            path="outputs/a2.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
                     },
-                },
-            },
+                ),
+            ],
         )
     with pytest.raises(ValueError, match="workspace path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
         )
     with pytest.raises(ValueError, match="duplicate path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(
                 segments=[_segment(0, 24), _segment(24, 48)]
             ),
             artifact_profiles=[
                 VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
                 VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
             ],
         )
+    # A mutated RenderPlan instance is reconstructed at the boundary, so
+    # clearing its segments cannot bypass the positive-plan invariant.
+    with pytest.raises(RendererProtocolError, match="positive-frame plan"):
+        positive = _plan()
+        object.__setattr__(positive, "segments", [])
+        assemble_provenance_v2(
+            **base,
+            plan=positive,
+            artifact_profiles=[],
+        )
 
 
 def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
     plan = _plan(
         segments=[_segment(12, 24), _segment(24, 36)],
         total_frames=48,
         window=_window(12, 36),
     )
     assert plan.total_frames == 48
     assert plan.window == _window(12, 36)
 
 

exec
/bin/zsh -lc 'git diff --unified=8 8418bae..788501c -- docs/contracts/render-backend-v1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index f98e1b1..88d822e 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -471,29 +471,29 @@ Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
 `request_digest`, `requested_policy`, `planner`, every segment's nested
 `renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
 assembler accepts no parallel singular renderer identity. The nested records
 have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
 distinct source pack, manifest, alias/override, support, and input-hash evidence
 for every renderer invocation. Planner and finalizer records carry the same
 alias/override/trust/support evidence as renderer records. Rendered artifacts
 are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
-hashed lineage entry PER SEGMENT, each keyed by a workspace-relative output
-path with exactly `{profile, sha256, attachments}` and a validated 64-hex
-string `sha256` on the artifact and every attachment `{path, kind, sha256}`.
-Sequence form preserves segment order (a path-keyed list) and rejects
-duplicate paths; mapping form requires path keys to equal the artifact's own
-path. Attachment paths must be workspace-relative, kinds must match
-`[a-z][a-z0-9-]*`, attachment map keys must equal the attachment's own name,
-and attachment names must be unique ACROSS all segment artifacts. Profile-only
-entries, null/malformed hashes, unknown or missing fields, path escapes,
-invalid kinds, duplicate paths, duplicate attachment names, and cardinality
-mismatches are all rejected; all Attachment and RenderProfile values are
-reconstructed through their DTO validators. Replay can verify rendered outputs
-byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
+hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
+sequence form (one VideoArtifact per segment); single-segment plans may use a
+path-keyed mapping. Every record carries its `path`, `profile`, a validated
+64-hex string `sha256`, and `attachments` — each attachment `{path, kind,
+sha256}` with a workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and
+globally unique names across all segment artifacts. All plan, artifact, and
+attachment values are reconstructed through their DTO validators at the
+provenance boundary (mutated frozen instances cannot bypass validation);
+duplicate paths, duplicate attachment names, path escapes, invalid kinds,
+profile-only entries, null/malformed hashes, and cardinality mismatches are
+rejected. All JSON Schema patterns are language-neutral (ECMAScript-valid;
+no Python-only anchors). Replay can verify rendered outputs byte-for-byte.
+`input_hashes` describe inputs only, never rendered outputs.
 
 `engine` is only the legacy request projection. The `segments` key keeps the
 V1-compatible flat projection: one `{engine, from, to}` entry per segment,
 derived from `renderer.id` and the validated integer `FrameWindow` at its
 rational FPS — exactly the shape legacy consumers read. The additive
 `segments_v2` key carries the complete normalized v2 segment records
 (`window`, `renderer` resolution, `input_hashes`); it never overwrites or
 reshapes a V1 key. When the v1 `segment_provenance` top-level projection

exec
/bin/zsh -lc "node -e 'const fs=require(\"fs\"),path=require(\"path\"); const dir=\"astrid/core/rendering/schemas/v1\"; let n=0; for(const name of fs.readdirSync(dir).filter(x=>x.endsWith(\".json\"))){const d=JSON.parse(fs.readFileSync(path.join(dir,name),\"utf8\")); const walk=x=>{if(Array.isArray(x))x.forEach(walk); else if(x&&typeof x===\"object\")for(const [k,v] of Object.entries(x)){if(k===\"pattern\"){new RegExp(v);n++}else walk(v)}}; walk(d)} console.log(\"ecmascript_compile_ok\",n)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
ecmascript_compile_ok 124

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,re; from pathlib import Path
ps=[]
for f in sorted(Path(\"astrid/core/rendering/schemas\").rglob(\"*.json\")):
 d=json.loads(f.read_text())
 def walk(x,p=\"\"):
  if isinstance(x,dict):
   [ps.append((f,p+\"/pattern\",v)) if k==\"pattern\" and isinstance(v,str) else walk(v,p+\"/\"+k) for k,v in x.items()]
  elif isinstance(x,list):
   [walk(v,p+\"/\"+str(i)) for i,v in enumerate(x)]
 walk(d)
print(\"patterns\",len(ps),\"with_Z\",sum(\"\\\\\\\\Z\" in p[2] for p in ps),\"with_dollar\",sum(\""'$" in p[2] for p in ps))
for f,p,s in ps: re.compile(s)
print("python_compile_ok")'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 39ms:
patterns 124 with_Z 0 with_dollar 0
python_compile_ok

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import runpy
from astrid.core.rendering.provenance import assemble_provenance_v2
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
p=assemble_provenance_v2(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=ns[\"_plan\"](),artifact_profiles={\"1\":{\"path\":1,\"profile\":ns[\"_profile\"](),\"sha256\":ns[\"SHA_B\"],\"attachments\":{}}},audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=ns[\"_compatibility\"]())
print(repr(p[\"artifact_profiles\"][\"1\"][\"path\"]),type(p[\"artifact_profiles\"][\"1\"][\"path\"]).__name__)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 200ms:
1 int

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '12,34p'; nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '58,79p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    12	  ],
    13	  "definitions": {
    14	    "qualifiedId": {
    15	      "type": "string",
    16	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
    17	    },
    18	    "sha256": {
    19	      "type": "string",
    20	      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    21	    },
    22	    "workspacePath": {
    23	      "type": "string",
    24	      "minLength": 1,
    25	      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\r\\n]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
    26	    },
    27	    "portableName": {
    28	      "type": "string",
    29	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
    30	      "not": {
    31	        "enum": [
    32	          ".",
    33	          ".."
    34	        ]
    58	      "type": "string",
    59	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
    60	    },
    61	    "sha256": {
    62	      "type": "string",
    63	      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
    64	    },
    65	    "workspacePath": {
    66	      "type": "string",
    67	      "minLength": 1,
    68	      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\r\\n]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
    69	    },
    70	    "portableName": {
    71	      "type": "string",
    72	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
    73	      "not": {
    74	        "enum": [
    75	          ".",
    76	          ".."
    77	        ]
    78	      }
    79	    },

exec
/bin/zsh -lc "git show 8418bae:astrid/core/rendering/provenance.py | nl -ba | sed -n '100,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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

exec
/bin/zsh -lc "git blame -L 107,259 -- astrid/core/rendering/provenance.py | sed -n '1,180p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
086d692e (POM 2026-08-12 03:40:34 +0200 107) def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
f8af4b20 (POM 2026-08-12 00:38:06 +0200 108)     if value is None:
086d692e (POM 2026-08-12 03:40:34 +0200 109)         value = {}
f8af4b20 (POM 2026-08-12 00:38:06 +0200 110)     if isinstance(value, Mapping):
788501c9 (POM 2026-08-12 04:39:08 +0200 111)         if segments and len(segments) > 1:
788501c9 (POM 2026-08-12 04:39:08 +0200 112)             raise TypeError(
788501c9 (POM 2026-08-12 04:39:08 +0200 113)                 "mapping-form artifact_profiles is unordered; use sequence form "
788501c9 (POM 2026-08-12 04:39:08 +0200 114)                 "(ordered VideoArtifacts, one per segment) for multi-segment plans"
788501c9 (POM 2026-08-12 04:39:08 +0200 115)             )
808030e1 (POM 2026-08-12 03:06:56 +0200 116)         result: dict[str, Any] = {}
8418baeb (POM 2026-08-12 04:20:15 +0200 117)         seen_attachment_names: set[str] = set()
808030e1 (POM 2026-08-12 03:06:56 +0200 118)         for key, profile in value.items():
808030e1 (POM 2026-08-12 03:06:56 +0200 119)             path = _require_string(str(key), "artifact key")
8418baeb (POM 2026-08-12 04:20:15 +0200 120)             path = _require_workspace_relative_path(path, "artifact key")
808030e1 (POM 2026-08-12 03:06:56 +0200 121)             if isinstance(profile, VideoArtifact):
086d692e (POM 2026-08-12 03:40:34 +0200 122)                 if path != profile.path:
086d692e (POM 2026-08-12 03:40:34 +0200 123)                     raise ValueError(
086d692e (POM 2026-08-12 03:40:34 +0200 124)                         f"artifact_profiles key {path!r} must equal VideoArtifact.path "
086d692e (POM 2026-08-12 03:40:34 +0200 125)                         f"{profile.path!r}"
086d692e (POM 2026-08-12 03:40:34 +0200 126)                     )
8418baeb (POM 2026-08-12 04:20:15 +0200 127)                 lineage = _artifact_lineage(profile)
086d692e (POM 2026-08-12 03:40:34 +0200 128)             elif isinstance(profile, Mapping):
8418baeb (POM 2026-08-12 04:20:15 +0200 129)                 lineage = _artifact_lineage_from_mapping(profile, key=path)
808030e1 (POM 2026-08-12 03:06:56 +0200 130)             else:
91f0fe3f (POM 2026-08-12 03:23:56 +0200 131)                 raise TypeError(
91f0fe3f (POM 2026-08-12 03:23:56 +0200 132)                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
91f0fe3f (POM 2026-08-12 03:23:56 +0200 133)                     "hashed lineage record {profile, sha256, attachments}; "
91f0fe3f (POM 2026-08-12 03:23:56 +0200 134)                     "profile-only entries carry no output hash"
91f0fe3f (POM 2026-08-12 03:23:56 +0200 135)                 )
8418baeb (POM 2026-08-12 04:20:15 +0200 136)             _reject_duplicate_attachment_names(lineage, seen_attachment_names)
8418baeb (POM 2026-08-12 04:20:15 +0200 137)             result[path] = lineage
ab486f9d (POM 2026-08-12 03:56:17 +0200 138)         # A positive plan must record exactly one hashed artifact per segment.
ab486f9d (POM 2026-08-12 03:56:17 +0200 139)         if segments:
ab486f9d (POM 2026-08-12 03:56:17 +0200 140)             if len(result) != len(segments):
ab486f9d (POM 2026-08-12 03:56:17 +0200 141)                 raise ValueError(
ab486f9d (POM 2026-08-12 03:56:17 +0200 142)                     f"artifact_profiles must record exactly one hashed lineage entry "
ab486f9d (POM 2026-08-12 03:56:17 +0200 143)                     f"per segment: expected {len(segments)}, got {len(result)}"
ab486f9d (POM 2026-08-12 03:56:17 +0200 144)                 )
808030e1 (POM 2026-08-12 03:06:56 +0200 145)         return result
f8af4b20 (POM 2026-08-12 00:38:06 +0200 146)     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
8418baeb (POM 2026-08-12 04:20:15 +0200 147)         lineage: list[dict[str, Any]] = []
8418baeb (POM 2026-08-12 04:20:15 +0200 148)         seen_paths: set[str] = set()
8418baeb (POM 2026-08-12 04:20:15 +0200 149)         seen_attachment_names: set[str] = set()
ab486f9d (POM 2026-08-12 03:56:17 +0200 150)         for profile in value:
ab486f9d (POM 2026-08-12 03:56:17 +0200 151)             if not isinstance(profile, VideoArtifact):
ab486f9d (POM 2026-08-12 03:56:17 +0200 152)                 raise TypeError(
ab486f9d (POM 2026-08-12 03:56:17 +0200 153)                     "sequence artifact_profiles entries must be VideoArtifacts "
ab486f9d (POM 2026-08-12 03:56:17 +0200 154)                     "so lineage records stay path-keyed"
ab486f9d (POM 2026-08-12 03:56:17 +0200 155)                 )
8418baeb (POM 2026-08-12 04:20:15 +0200 156)             if profile.path in seen_paths:
8418baeb (POM 2026-08-12 04:20:15 +0200 157)                 raise ValueError(
8418baeb (POM 2026-08-12 04:20:15 +0200 158)                     f"artifact_profiles sequence contains duplicate path "
8418baeb (POM 2026-08-12 04:20:15 +0200 159)                     f"{profile.path!r}"
8418baeb (POM 2026-08-12 04:20:15 +0200 160)                 )
8418baeb (POM 2026-08-12 04:20:15 +0200 161)             seen_paths.add(profile.path)
8418baeb (POM 2026-08-12 04:20:15 +0200 162)             record = _artifact_lineage(profile)
8418baeb (POM 2026-08-12 04:20:15 +0200 163)             _reject_duplicate_attachment_names(record, seen_attachment_names)
8418baeb (POM 2026-08-12 04:20:15 +0200 164)             lineage.append(record)
ab486f9d (POM 2026-08-12 03:56:17 +0200 165)         if segments:
ab486f9d (POM 2026-08-12 03:56:17 +0200 166)             if len(lineage) != len(segments):
ab486f9d (POM 2026-08-12 03:56:17 +0200 167)                 raise ValueError(
ab486f9d (POM 2026-08-12 03:56:17 +0200 168)                     f"artifact_profiles must record exactly one hashed lineage entry "
ab486f9d (POM 2026-08-12 03:56:17 +0200 169)                     f"per segment: expected {len(segments)}, got {len(lineage)}"
ab486f9d (POM 2026-08-12 03:56:17 +0200 170)                 )
086d692e (POM 2026-08-12 03:40:34 +0200 171)         return lineage
f8af4b20 (POM 2026-08-12 00:38:06 +0200 172)     raise TypeError("artifact_profiles must be an object or array")
f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
086d692e (POM 2026-08-12 03:40:34 +0200 175) def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
086d692e (POM 2026-08-12 03:40:34 +0200 176)     raw_keys = set(raw)
788501c9 (POM 2026-08-12 04:39:08 +0200 177)     allowed = {"profile", "sha256", "attachments", "path"}
086d692e (POM 2026-08-12 03:40:34 +0200 178)     unknown = sorted(raw_keys - allowed)
086d692e (POM 2026-08-12 03:40:34 +0200 179)     if unknown:
086d692e (POM 2026-08-12 03:40:34 +0200 180)         raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
788501c9 (POM 2026-08-12 04:39:08 +0200 181)     missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
086d692e (POM 2026-08-12 03:40:34 +0200 182)     if missing:
086d692e (POM 2026-08-12 03:40:34 +0200 183)         raise ValueError(
086d692e (POM 2026-08-12 03:40:34 +0200 184)             f"artifact lineage is missing required fields: {', '.join(missing)}"
086d692e (POM 2026-08-12 03:40:34 +0200 185)         )
086d692e (POM 2026-08-12 03:40:34 +0200 186)     if raw["sha256"] is None:
91f0fe3f (POM 2026-08-12 03:23:56 +0200 187)         raise ValueError("artifact lineage sha256 is required and must not be null")
086d692e (POM 2026-08-12 03:40:34 +0200 188)     if not isinstance(raw["sha256"], str):
086d692e (POM 2026-08-12 03:40:34 +0200 189)         raise TypeError("artifact lineage sha256 must be a string")
788501c9 (POM 2026-08-12 04:39:08 +0200 190)     if "path" in raw:
788501c9 (POM 2026-08-12 04:39:08 +0200 191)         embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
788501c9 (POM 2026-08-12 04:39:08 +0200 192)         if embedded != key:
788501c9 (POM 2026-08-12 04:39:08 +0200 193)             raise ValueError(
788501c9 (POM 2026-08-12 04:39:08 +0200 194)                 f"artifact lineage path {embedded!r} must equal its map key {key!r}"
788501c9 (POM 2026-08-12 04:39:08 +0200 195)             )
086d692e (POM 2026-08-12 03:40:34 +0200 196)     profile = raw["profile"]
91f0fe3f (POM 2026-08-12 03:23:56 +0200 197)     attachments: dict[str, Any] = {}
086d692e (POM 2026-08-12 03:40:34 +0200 198)     raw_attachments = raw["attachments"]
086d692e (POM 2026-08-12 03:40:34 +0200 199)     if raw_attachments is None:
086d692e (POM 2026-08-12 03:40:34 +0200 200)         raise ValueError("artifact lineage attachments must be an object (may be empty)")
086d692e (POM 2026-08-12 03:40:34 +0200 201)     if not isinstance(raw_attachments, Mapping):
086d692e (POM 2026-08-12 03:40:34 +0200 202)         raise TypeError("artifact lineage attachments must be an object")
086d692e (POM 2026-08-12 03:40:34 +0200 203)     for name, att in raw_attachments.items():
086d692e (POM 2026-08-12 03:40:34 +0200 204)         name = _require_string(name, "attachment name")
086d692e (POM 2026-08-12 03:40:34 +0200 205)         if isinstance(att, Attachment):
ab486f9d (POM 2026-08-12 03:56:17 +0200 206)             if att.name != name:
ab486f9d (POM 2026-08-12 03:56:17 +0200 207)                 raise ValueError(
ab486f9d (POM 2026-08-12 03:56:17 +0200 208)                     f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
ab486f9d (POM 2026-08-12 03:56:17 +0200 209)                 )
086d692e (POM 2026-08-12 03:40:34 +0200 210)             att = {
086d692e (POM 2026-08-12 03:40:34 +0200 211)                 "path": att.path,
086d692e (POM 2026-08-12 03:40:34 +0200 212)                 "kind": att.kind,
086d692e (POM 2026-08-12 03:40:34 +0200 213)                 "sha256": att.sha256,
086d692e (POM 2026-08-12 03:40:34 +0200 214)             }
086d692e (POM 2026-08-12 03:40:34 +0200 215)         att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
086d692e (POM 2026-08-12 03:40:34 +0200 216)         if att_unknown:
086d692e (POM 2026-08-12 03:40:34 +0200 217)             raise ValueError(
086d692e (POM 2026-08-12 03:40:34 +0200 218)                 f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
086d692e (POM 2026-08-12 03:40:34 +0200 219)             )
086d692e (POM 2026-08-12 03:40:34 +0200 220)         att_missing = sorted({"path", "kind", "sha256"} - set(att))
086d692e (POM 2026-08-12 03:40:34 +0200 221)         if att_missing:
086d692e (POM 2026-08-12 03:40:34 +0200 222)             raise ValueError(
086d692e (POM 2026-08-12 03:40:34 +0200 223)                 f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
086d692e (POM 2026-08-12 03:40:34 +0200 224)             )
086d692e (POM 2026-08-12 03:40:34 +0200 225)         if not isinstance(att["sha256"], str):
086d692e (POM 2026-08-12 03:40:34 +0200 226)             raise TypeError(f"attachment {name!r} sha256 must be a string")
ab486f9d (POM 2026-08-12 03:56:17 +0200 227)         # Validate through the Attachment DTO so workspace-path containment and
ab486f9d (POM 2026-08-12 03:56:17 +0200 228)         # kind grammar are enforced uniformly for raw and dataclass values.
ab486f9d (POM 2026-08-12 03:56:17 +0200 229)         validated = Attachment(
ab486f9d (POM 2026-08-12 03:56:17 +0200 230)             name=name,
ab486f9d (POM 2026-08-12 03:56:17 +0200 231)             path=att["path"],
ab486f9d (POM 2026-08-12 03:56:17 +0200 232)             kind=att["kind"],
ab486f9d (POM 2026-08-12 03:56:17 +0200 233)             sha256=att["sha256"],
ab486f9d (POM 2026-08-12 03:56:17 +0200 234)         )
086d692e (POM 2026-08-12 03:40:34 +0200 235)         attachments[name] = {
ab486f9d (POM 2026-08-12 03:56:17 +0200 236)             "path": validated.path,
ab486f9d (POM 2026-08-12 03:56:17 +0200 237)             "kind": validated.kind,
ab486f9d (POM 2026-08-12 03:56:17 +0200 238)             "sha256": validated.sha256,
91f0fe3f (POM 2026-08-12 03:23:56 +0200 239)         }
91f0fe3f (POM 2026-08-12 03:23:56 +0200 240)     return {
788501c9 (POM 2026-08-12 04:39:08 +0200 241)         "path": raw["path"] if "path" in raw else key,
8418baeb (POM 2026-08-12 04:20:15 +0200 242)         "profile": RenderProfile.from_dict(
8418baeb (POM 2026-08-12 04:20:15 +0200 243)             _json_safe_mapping(profile, label="artifact profile")
91f0fe3f (POM 2026-08-12 03:23:56 +0200 244)         ).to_dict(),
086d692e (POM 2026-08-12 03:40:34 +0200 245)         "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
91f0fe3f (POM 2026-08-12 03:23:56 +0200 246)         "attachments": attachments,
91f0fe3f (POM 2026-08-12 03:23:56 +0200 247)     }
91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
808030e1 (POM 2026-08-12 03:06:56 +0200 250) def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
808030e1 (POM 2026-08-12 03:06:56 +0200 251)     """One hashed artifact lineage record: profile, sha256, attachments."""
086d692e (POM 2026-08-12 03:40:34 +0200 252)     return _artifact_lineage_from_mapping(
086d692e (POM 2026-08-12 03:40:34 +0200 253)         {
086d692e (POM 2026-08-12 03:40:34 +0200 254)             "profile": artifact.profile,
086d692e (POM 2026-08-12 03:40:34 +0200 255)             "sha256": artifact.sha256,
086d692e (POM 2026-08-12 03:40:34 +0200 256)             "attachments": artifact.attachments,
808030e1 (POM 2026-08-12 03:06:56 +0200 257)         },
086d692e (POM 2026-08-12 03:40:34 +0200 258)         key=artifact.path,
086d692e (POM 2026-08-12 03:40:34 +0200 259)     )

exec
/bin/zsh -lc "rg -n \"def test_.*schema|schema.*DTO|schema.*dto|Draft7Validator|validator\" tests/core/rendering/test_schema_roundtrip.py | head -100 && nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '1,380p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
75:def test_every_schema_and_example_is_valid_and_parses(schema_name: str) -> None:
77:    jsonschema.Draft7Validator.check_schema(schema)
78:    validator = jsonschema.Draft7Validator(schema)
83:        validator.validate(example)
86:        validator.validate(round_trip)
91:def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
93:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
94:    validator.validate(payload)
341:def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
342:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
345:        schema_accepts = validator.is_valid(payload)
354:            f"schema={schema_accepts}, dto={dto_accepts}"
371:def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
374:    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
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
   121	    return result
   122	
   123	
   124	def _delete(payload: dict[str, Any], path: tuple[str | int, ...]) -> dict[str, Any]:
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
   296	        ("valid canonical", base),
   297	        ("missing id", _delete(base, ("id",))),
   298	        ("valid underscore id", _set(base, ("id",), "acme.bad_id")),
   299	        ("unknown field", {**base, "priority": 1}),
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
/bin/zsh -lc "git diff --name-status 8418bae..788501c -- ':"'!.oracle/checkins/batch-1-r8.md'"' && git status --porcelain=v2" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
? .oracle/checkins/batch-1-r9.md

exec
/bin/zsh -lc "rg -n -F ' /video.mp4' tests astrid || true; rg -n -F '\\u00a0' tests/core/rendering astrid/core/rendering || true; rg -n 'workspace.*parity|workspacePath|whitespace-only|dir/ ' tests/core/rendering" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
exec
/bin/zsh -lc "rg -n '"'^def _require_string|''^_.*RE'"' astrid/core/rendering/contracts.py | head -40 && nl -ba astrid/core/rendering/contracts.py | sed -n '35,90p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
36:_QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
37:_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
38:_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
39:_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
111:_RETIRED_PROVENANCE_V2_KEYS = frozenset(
217:def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
264:def _require_string_list(value: Any, label: str) -> list[str]:
270:def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
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

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '205,235p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

collab: Wait
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import json
from pathlib import Path
import jsonschema
from astrid.core.rendering.contracts import parse_wire_result, FinalizeRequest
root=Path(\"tests/core/rendering/fixtures/v1\")
schemas=Path(\"astrid/core/rendering/schemas/v1\")
r=json.loads((root/\"result.json\").read_text()); r[\"video\"][\"path\"]=\" /video.mp4\"
print(\"result schema\",jsonschema.Draft7Validator(json.loads((schemas/\"result.json\").read_text())).is_valid(r))
try:
 parse_wire_result(r); print(\"result dto True\")
except Exception as e: print(\"result dto False\",type(e).__name__,str(e))
f=json.loads((root/\"finalize.json\").read_text()); f[\"artifacts\"][0][\"path\"]=\"dir/\\v/video.mp4\"
print(\"finalize schema\",jsonschema.Draft7Validator(json.loads((schemas/\"finalize.json\").read_text())).is_valid(f))
try:
 FinalizeRequest.from_dict(f); print(\"finalize dto True\")
except Exception as e: print(\"finalize dto False\",type(e).__name__,str(e))
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 195ms:
result schema True
result dto False RendererProtocolError malformed render result: video path must not contain empty or whitespace-only path components
finalize schema True
finalize dto False RendererProtocolError malformed finalize request: video path must not contain empty or whitespace-only path components

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json; from pathlib import Path
p=json.loads(Path(\"tests/core/rendering/fixtures/v1/finalize.json\").read_text()); print(sorted(p)); print(sorted(p[\"plan\"]))' && nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '275,289p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
['artifacts', 'backend_config', 'metadata', 'output_name', 'plan', 'schema_version']
['finalizer', 'planner', 'profile', 'reasons', 'request_digest', 'requested_policy', 'schema_version', 'segments', 'total_frames', 'window']
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

exec
/bin/zsh -lc "rg -n 'trailing lf|trailing newline|\\\\n\"\\)|\\\\n\"\\]|reason key|request_digest.*\\\\n' tests/core/rendering" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_schema_roundtrip.py:283:        ("trailing lf digest", _set(base, ("request_digest",), "a" * 64 + "\n")),
tests/core/rendering/test_schema_roundtrip.py:284:        ("trailing lf reason key", _set(base, ("reasons",), {"0\n": "why"})),
tests/core/rendering/test_contracts.py:616:    assert sidecar.read_text(encoding="utf-8").endswith("\n")

collab: Wait
exec
/bin/zsh -lc "rg -n '"'^def _json_safe|''^def _json_safe_mapping'"' astrid/core/rendering/contracts.py && nl -ba astrid/core/rendering/contracts.py | sed -n '135,205p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
132:def _json_safe(value: Any) -> Any:
160:def _json_safe_mapping(value: Any, *, label: str = "value") -> dict[str, Any]:
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

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import runpy
from astrid.core.rendering.contracts import VideoArtifact, AudioOwnership
from astrid.core.rendering.provenance import assemble_provenance_v2
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
plan=ns[\"_plan\"](segments=[ns[\"_segment\"](0,24),ns[\"_segment\"](24,48)])
base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=ns[\"_compatibility\"]())
arts=[VideoArtifact(path=\"outputs/a.mp4\",profile=ns[\"_profile\"](),sha256=ns[\"SHA_B\"],duration_frames=24,audio=AudioOwnership.RENDERED),VideoArtifact(path=\"outputs/b.mp4\",profile=ns[\"_profile\"](),sha256=ns[\"SHA_C\"],duration_frames=24,audio=AudioOwnership.RENDERED)]
out=assemble_provenance_v2(**base,artifact_profiles=arts)[\"artifact_profiles\"]
print(out)
try:
 assemble_provenance_v2(**base,artifact_profiles=out); print(\"roundtrip accepted\")
except Exception as e:
 print(\"roundtrip rejected\",type(e).__name__,str(e))
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 153ms:
[{'path': 'outputs/a.mp4', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}, {'path': 'outputs/b.mp4', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc', 'attachments': {}}]
roundtrip rejected TypeError sequence artifact_profiles entries must be VideoArtifacts so lineage records stay path-keyed

codex
The portable end assertion itself checks out: all 124 patterns compile in both Python and ECMAScript, with no `\Z` or `$` anchors left. Two blockers remain reproducible: mutated sequence artifacts can still emit `../escape.mp4`, and both workspace-path schemas accept whitespace-only leading components that the DTO rejects. I’m finishing the independent cross-check before issuing the verdict.
exec
/bin/zsh -lc "node -e 'const fs=require(\"fs\"); for(const n of [\"result.json\",\"finalize.json\"]){const s=JSON.parse(fs.readFileSync("'`astrid/core/rendering/schemas/v1/${n}`,"utf8")); const r=new RegExp(s.definitions.workspacePath.pattern); console.log(n,r.test(" /video.mp4"),r.test("dir/'"\\v/video.mp4\"),r.test(\"ok/video.mp4\"));} const s=JSON.parse(fs.readFileSync(\"astrid/core/rendering/schemas/v1/result.json\",\"utf8\")); console.log(\"sha\",new RegExp(s.definitions.sha256.pattern).test(\"a\".repeat(64)),new RegExp(s.definitions.sha256.pattern).test(\"a\".repeat(64)+\"\\n\"));'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
result.json true true true
finalize.json true true true
sha true false

collab: Wait
collab: Wait
codex
1. **`VideoArtifact` reconstruction remains bypassable.** [provenance.py:150](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150) never reconstructs sequence entries through `VideoArtifact.from_dict`; an artifact mutated to `path="../escape.mp4"` is accepted and emitted. Mapping lineage also validates `str(path)` but emits the original value, allowing an integer `path`. The emitted sequence still cannot round-trip because dictionary records are rejected.

2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
tokens used
174,264
1. **`VideoArtifact` reconstruction remains bypassable.** [provenance.py:150](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150) never reconstructs sequence entries through `VideoArtifact.from_dict`; an artifact mutated to `path="../escape.mp4"` is accepted and emitted. Mapping lineage also validates `str(path)` but emits the original value, allowing an integer `path`. The emitted sequence still cannot round-trip because dictionary records are rejected.

2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
