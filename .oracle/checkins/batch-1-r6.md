Reading additional input from stdin...
2026-08-12T01:40:48.514651Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:40:48.514675Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:40:48.514680Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3a1-165c-7371-b898-2a174fb34ef5
--------
user
# Megado Checkpoint — Batch 1 sixth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3).
Sixth rework committed as `086d692` (prior head 91f0fe3). Incremental diff at
/tmp/batch1-r6.diff.

## How each of your 3 re-review5 issues was addressed (host-implemented)

1. **Hashed artifact lineage optional and unbound** →
   - `_normalize_artifact_profiles` now takes the plan's segments: `None`
     becomes `{}` (not `[]`) and a POSITIVE plan with no lineage entries
     raises ValueError.
   - Mapping keys must equal `VideoArtifact.path` for VideoArtifact values.
   - Spoof tests extended (unknown field, null sha256, malformed sha256).
2. **Lineage mappings spoofable** →
   - Exact `{profile, sha256, attachments}` shape enforced: unknown and
     missing fields rejected on the artifact and every attachment; null
     sha256 raises ValueError; non-string sha256 raises TypeError; hashes
     validated as 64-hex; attachment path/kind nonblank; Sequence entries
     share the same path; Attachment dataclass values handled without
     leaking the redundant `name` field.
3. **Schema/DTO parity** →
   - Anchored nonblank pattern now `^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*$`
     (rejects NUL after newlines; multiline accepted).
   - workspacePath accepts internal newlines (uses `[\s\S]*`), still rejects
     whitespace-only and NUL.
   - support features + plan/finalize hashMap gained nonblank/NUL
     `propertyNames`.

## Evidence

- Incremental diff: /tmp/batch1-r6.diff (12 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.
- Docs updated: strict lineage shape + path binding.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has now passed 6 review rounds.
The contract must be sound and STABLE for M2 (Batches 2-5 build on it). If the
remaining nits are non-blocking or absent, say exactly `PASS`. If you find
blocking issues, name them precisely with minimum rework.
codex
I’m using the Astrid repo skill for repository-specific rules and the Megado skill for the checkpoint contract. I’ll inspect the incremental diff and the affected implementation/tests read-only, then return only `PASS` or precise blocking issues.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
     950 total
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
/bin/zsh -lc "sed -n '241,520p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '521,820p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The Megado checkpoint rule makes this a strict regression gate: I’m checking the committed delta itself, not relying on the reported test totals. I’ll also compare the runtime DTO validation against both schemas and the documented M2-facing contract.
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show --no-ext-diff --stat --oneline --decorate 086d692 && git diff --no-ext-diff --stat 91f0fe3..086d692 && git diff --no-ext-diff --name-only 91f0fe3..086d692 && shasum -a 256 /tmp/batch1-r6.diff && rg --files -g 'AGENTS.md' -g '"'!remotion/node_modules/**'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r6.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
086d692ea5c373470a2993c6a7e47b06e2f5bebc
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
086d692 (HEAD -> oracle-run) batch1-rework6: oracle re-review5 issues 1-3 (lineage required+shape-bound+path-bound, NUL-after-newline, hashMap/feature propertyNames, workspacePath newlines)
 .oracle/checkins/batch-1-r5.md                     | 16046 +++++++++++++++++++
 astrid/core/rendering/provenance.py                |   112 +-
 astrid/core/rendering/schemas/v1/finalize.json     |    43 +-
 .../rendering/schemas/v1/finalizer-manifest.json   |    20 +-
 astrid/core/rendering/schemas/v1/plan.json         |    35 +-
 .../rendering/schemas/v1/planner-manifest.json     |    20 +-
 .../rendering/schemas/v1/renderer-manifest.json    |    24 +-
 astrid/core/rendering/schemas/v1/request.json      |    28 +-
 astrid/core/rendering/schemas/v1/result.json       |    32 +-
 astrid/core/rendering/schemas/v1/support.json      |     7 +-
 docs/contracts/render-backend-v1.md                |    13 +-
 tests/core/rendering/test_contracts.py             |    32 +-
 12 files changed, 16271 insertions(+), 141 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r5.md                     | 16046 +++++++++++++++++++
 astrid/core/rendering/provenance.py                |   112 +-
 astrid/core/rendering/schemas/v1/finalize.json     |    43 +-
 .../rendering/schemas/v1/finalizer-manifest.json   |    20 +-
 astrid/core/rendering/schemas/v1/plan.json         |    35 +-
 .../rendering/schemas/v1/planner-manifest.json     |    20 +-
 .../rendering/schemas/v1/renderer-manifest.json    |    24 +-
 astrid/core/rendering/schemas/v1/request.json      |    28 +-
 astrid/core/rendering/schemas/v1/result.json       |    32 +-
 astrid/core/rendering/schemas/v1/support.json      |     7 +-
 docs/contracts/render-backend-v1.md                |    13 +-
 tests/core/rendering/test_contracts.py             |    32 +-
 12 files changed, 16271 insertions(+), 141 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r5.md
astrid/core/rendering/provenance.py
astrid/core/rendering/schemas/v1/finalize.json
astrid/core/rendering/schemas/v1/finalizer-manifest.json
astrid/core/rendering/schemas/v1/plan.json
astrid/core/rendering/schemas/v1/planner-manifest.json
astrid/core/rendering/schemas/v1/renderer-manifest.json
astrid/core/rendering/schemas/v1/request.json
astrid/core/rendering/schemas/v1/result.json
astrid/core/rendering/schemas/v1/support.json
docs/contracts/render-backend-v1.md
tests/core/rendering/test_contracts.py
3ba6672176ce8513a9971f61be4edd999643db5ad5ad09682480de34a679a14c  /tmp/batch1-r6.diff
AGENTS.md
examples/packs/media/AGENTS.md
examples/packs/text_digest/AGENTS.md
examples/packs/file_summarizer/AGENTS.md
examples/packs/text_review/AGENTS.md
examples/packs/minimal/AGENTS.md

exec
/bin/zsh -lc "cmp -s /Users/peteromalley/.codex/skills/astrid/SKILL.md astrid/packs/_core/skill/SKILL.md; printf '%s\\n' "'$? && wc -l /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '"'1,260p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
0
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

codex
The repository posture calls for an independent adversarial pass on review-heavy work, so I’m applying the subagent-launcher pattern through two isolated, read-only reviewers: one on lineage normalization/security, one on schema/DTO parity. Their conclusions are inputs only; I’ll independently verify any finding before the verdict.
2026-08-12T01:41:46.552472Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:41:46.552500Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:41:46.552505Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:41:53.030347Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:41:53.031118Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:41:53.031132Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc 'rg -n "Batch 1|lineage|artifactProfiles|hashMap|workspacePath|support" .oracle/tasklist.md .oracle/plan.md .oracle/checkins/batch-1-r5.md | head -n 240 && tail -n 220 .oracle/checkins/batch-1-r5.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/plan.md:24:   <command...> render|support|plan|finalize \
.oracle/plan.md:37:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/plan.md:87:  - Add versioned JSON Schemas for request, result, support, plan, finalization, and the three manifest types.
.oracle/plan.md:140:  - Gate: render/support success, unsupported response, malformed JSON, missing result/output, nonzero exit, timeout, SIGINT cleanup, untrusted env discovery, trusted install, and static no-import inspection all pass.
.oracle/plan.md:147:  - Serve only invocation-staged assets from `127.0.0.1`; bind the server directly to port `0`, retain Range support, start inside the managed context, and always shut down, close, and join it.
.oracle/plan.md:160:  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
.oracle/plan.md:179:    - unsupported or unknown track/clip kinds;
.oracle/plan.md:183:    - unsupported positioning, crop, effect, transition, or non-default opacity semantics;
.oracle/plan.md:193:  - Let an explicit planner route unsupported windows elsewhere; strict `rendering.ffmpeg` must not silently alter them.
.oracle/plan.md:194:  - Express media optimization and audio-reactive specialization as request-sensitive support evidence, not facade branches.
.oracle/plan.md:195:  - Preserve compatible stream-copy behavior and supported sequential audio mixing.
.oracle/plan.md:198:  - Gate: support diagnostics, command graphs, stream-copy, gaps/overlaps, track mute/volume, clip volume zero, fades, source bounds, missing streams/binaries, audio-reactive marker frames/hashes, cleanup, output validation, and provenance pass with a real FFmpeg render.
.oracle/plan.md:218:    6. obtain static/request-sensitive support;
.oracle/plan.md:239:    - support decision and alternatives;
.oracle/plan.md:253:  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.
.oracle/plan.md:264:    - unsupported non-media clips;
.oracle/plan.md:266:    - controls rejected by the selected renderer’s support report.
.oracle/plan.md:267:  - Permit FFmpeg track mute/volume after M1-06 proves exact support; fades continue to route away from FFmpeg.
.oracle/plan.md:268:  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
.oracle/plan.md:269:  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
.oracle/plan.md:308:    - support decisions;
.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
.oracle/plan.md:349:  - Provide `renderer_main()` plus functional `render(request, context)` and optional `support(request, context)` author hooks.
.oracle/plan.md:366:    - request-sensitive support;
.oracle/plan.md:405:  - Gate: help, dispatch, session independence, JSON keys, error/recovery behavior, conflicts, trust denial, installed selection, unsupported support, interruption, and smoke output pass.
.oracle/plan.md:410:  - Bundle the resolved request, localized inputs, backend configuration, renderer/manifest identity and digest, support report, logs, result/partial result, hashes, and exact replay command.
.oracle/plan.md:419:  - Keep support probing and custom finalizers in separate advanced sections.
.oracle/plan.md:440:- Made FFmpeg audio semantics exact: track and clip gains multiply, track mute wins, clip mute is volume zero, and fades remain unsupported.
.oracle/tasklist.md:3:## Batch 1 — Baseline, contracts, and discovery
.oracle/tasklist.md:32:- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
.oracle/tasklist.md:46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
.oracle/tasklist.md:52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
.oracle/tasklist.md:57:- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
.oracle/tasklist.md:59:- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
.oracle/tasklist.md:60:- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
.oracle/tasklist.md:68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
.oracle/tasklist.md:69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
.oracle/tasklist.md:79:- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
.oracle/tasklist.md:83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
.oracle/tasklist.md:84:- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
.oracle/tasklist.md:89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
.oracle/tasklist.md:92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
.oracle/tasklist.md:93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
.oracle/tasklist.md:130:- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
.oracle/tasklist.md:137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
.oracle/tasklist.md:139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
.oracle/tasklist.md:153:- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
.oracle/tasklist.md:163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
.oracle/tasklist.md:166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
.oracle/tasklist.md:178:- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
.oracle/checkins/batch-1-r5.md:17:# Megado Checkpoint — Batch 1 fifth re-review
.oracle/checkins/batch-1-r5.md:34:2. **Hashed artifact lineage optional/spoofable** →
.oracle/checkins/batch-1-r5.md:35:   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
.oracle/checkins/batch-1-r5.md:39:   - `test_provenance_rejects_spoofed_artifact_lineage` (profile-only, null
.oracle/checkins/batch-1-r5.md:42:   - workspacePath accepts DTO-valid leading whitespace (`. *\S.*` tail),
.oracle/checkins/batch-1-r5.md:46:   - Manifest metadata, feature maps, support features, and plan hashMap
.oracle/checkins/batch-1-r5.md:61:- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
.oracle/checkins/batch-1-r5.md:65:  lineage.
.oracle/checkins/batch-1-r5.md:599:91f0fe3f1d416aba0dce5396fb60cf05fb1378fe 808030e1182c795ce345df3ea0cb619fd3bf9d23 batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
.oracle/checkins/batch-1-r5.md:611: astrid/core/rendering/schemas/v1/support.json      |     4 +-
.oracle/checkins/batch-1-r5.md:642:M	astrid/core/rendering/schemas/v1/support.json
.oracle/checkins/batch-1-r5.md:648:A	tests/core/rendering/fixtures/v1/support.json
.oracle/checkins/batch-1-r5.md:659:/bin/zsh -lc 'rg -n "''^(#|##|###|PASS$|[0-9]+'"\\.|- \\*\\*|Verdict|Issue|Issues|Acceptance|Batch 1)\" .oracle/checkins/batch-1.md .oracle/checkins/batch-1-r1.md .oracle/checkins/batch-1-r2.md .oracle/checkins/batch-1-r3.md .oracle/checkins/batch-1-r4.md .oracle/tasklist.md .oracle/status.md 2>/dev/null | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r5.md:662:.oracle/tasklist.md:3:## Batch 1 — Baseline, contracts, and discovery
.oracle/checkins/batch-1-r5.md:677:.oracle/checkins/batch-1-r3.md:17:# Megado Checkpoint — Batch 1 third re-review
.oracle/checkins/batch-1-r5.md:679:.oracle/checkins/batch-1-r3.md:28:1. **Provenance resolution and artifact lineage incomplete** →
.oracle/checkins/batch-1-r5.md:779:.oracle/checkins/batch-1-r3.md:628:# Megado Checkpoint — Batch 1 review
.oracle/checkins/batch-1-r5.md:780:.oracle/checkins/batch-1-r3.md:637:## Batch 1 tasks (from tasklist.md)
.oracle/checkins/batch-1-r5.md:781:.oracle/checkins/batch-1-r3.md:645:## Acceptance criteria (from tasklist.md Batch 1)
.oracle/checkins/batch-1-r5.md:827:.oracle/checkins/batch-1-r3.md:888:# Megado Checkpoint — Batch 1 re-review
.oracle/checkins/batch-1-r5.md:831:.oracle/checkins/batch-1-r3.md:907:4. Provenance routing/replay lineage → explicit planner/segment/finalizer
.oracle/checkins/batch-1-r5.md:846:.oracle/checkins/batch-1-r3.md:1128:# Megado Checkpoint — Batch 1 second re-review
.oracle/checkins/batch-1-r5.md:881:.oracle/checkins/batch-1-r3.md:1393:# ISSUES — Batch 1 does not pass
.oracle/checkins/batch-1-r5.md:885:.oracle/checkins/batch-1-r3.md:1414:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r5.md:886:.oracle/checkins/batch-1-r3.md:1418:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
.oracle/checkins/batch-1-r5.md:891:.oracle/checkins/batch-1-r3.md:1446:# ISSUES — Batch 1 does not pass
.oracle/checkins/batch-1-r5.md:895:.oracle/checkins/batch-1-r3.md:1467:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r5.md:896:.oracle/checkins/batch-1-r3.md:1471:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:917:.oracle/checkins/batch-1-r3.md:1757:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:921:.oracle/checkins/batch-1-r3.md:1772:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1014:.oracle/checkins/batch-1-r1.md:17:# Megado Checkpoint — Batch 1 re-review
.oracle/checkins/batch-1-r5.md:1018:.oracle/checkins/batch-1-r1.md:36:4. Provenance routing/replay lineage → explicit planner/segment/finalizer
.oracle/checkins/batch-1-r5.md:1027:## Batch 1 — Baseline, contracts, and discovery
.oracle/checkins/batch-1-r5.md:1056:- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
.oracle/checkins/batch-1-r5.md:1064:22597:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
.oracle/checkins/batch-1-r5.md:1072:22646:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r5.md:1073:22650:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:1102:28675:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:1106:28690:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r5.md:1109:1772:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1127:38812:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/checkins/batch-1-r5.md:1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r5.md:1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r5.md:1158: astrid/core/rendering/schemas/v1/support.json      |  70 +-
.oracle/checkins/batch-1-r5.md:1164: tests/core/rendering/fixtures/v1/support.json      |   9 +
.oracle/checkins/batch-1-r5.md:1177:04767bf batch1-rework3: oracle re-review2 issues 1-3 (complete resolution records w/ trust+support, planner to_dict fix, nullable-string parity, segments_v2 prohibition, temp-fixture override regression)
.oracle/checkins/batch-1-r5.md:1178:808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
.oracle/checkins/batch-1-r5.md:1179:91f0fe3 (HEAD -> oracle-run) batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
.oracle/checkins/batch-1-r5.md:1312:             details={"received": value, "supported": [SCHEMA_VERSION]},
.oracle/checkins/batch-1-r5.md:1366:             data = _require_mapping(payload, "support report")
.oracle/checkins/batch-1-r5.md:1369:                 "supported",
.oracle/checkins/batch-1-r5.md:1380:                 label="support report",
.oracle/checkins/batch-1-r5.md:1384:                 supported=data["supported"],
.oracle/checkins/batch-1-r5.md:1397:                 f"malformed support report: {exc}",
.oracle/checkins/batch-1-r5.md:1412:     support_decision: SupportReport | None = None
.oracle/checkins/batch-1-r5.md:1453:         if self.support_decision is not None:
.oracle/checkins/batch-1-r5.md:1454:             support = (
.oracle/checkins/batch-1-r5.md:1455:                 self.support_decision
.oracle/checkins/batch-1-r5.md:1456:                 if isinstance(self.support_decision, SupportReport)
.oracle/checkins/batch-1-r5.md:1459:                         self.support_decision, "planner support_decision"
.oracle/checkins/batch-1-r5.md:1463:             if support.backend != self.id:
.oracle/checkins/batch-1-r5.md:1464:                 raise ValueError("planner support_decision.backend must match planner id")
.oracle/checkins/batch-1-r5.md:1465:             object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r5.md:1476:                 "support_decision": self.support_decision,
.oracle/checkins/batch-1-r5.md:1490:             "support_decision",
.oracle/checkins/batch-1-r5.md:1500:             support_decision=data["support_decision"],
.oracle/checkins/batch-1-r5.md:1513:     support_decision: SupportReport
.oracle/checkins/batch-1-r5.md:1518:         support = (
.oracle/checkins/batch-1-r5.md:1519:             self.support_decision
.oracle/checkins/batch-1-r5.md:1520:             if isinstance(self.support_decision, SupportReport)
.oracle/checkins/batch-1-r5.md:1522:                 _require_mapping(self.support_decision, "renderer support_decision")
.oracle/checkins/batch-1-r5.md:1525:         if support.backend != renderer_id:
.oracle/checkins/batch-1-r5.md:1526:             raise ValueError("renderer support_decision.backend must match renderer id")
.oracle/checkins/batch-1-r5.md:1565:         object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r5.md:1575:                 "support_decision": self.support_decision,
.oracle/checkins/batch-1-r5.md:1589:             "support_decision",
.oracle/checkins/batch-1-r5.md:1599:             support_decision=SupportReport.from_dict(data["support_decision"]),
.oracle/checkins/batch-1-r5.md:1614:     support_decision: SupportReport | None = None
.oracle/checkins/batch-1-r5.md:1655:         if self.support_decision is not None:
.oracle/checkins/batch-1-r5.md:1656:             support = (
.oracle/checkins/batch-1-r5.md:1657:                 self.support_decision
.oracle/checkins/batch-1-r5.md:1658:                 if isinstance(self.support_decision, SupportReport)
.oracle/checkins/batch-1-r5.md:1661:                         self.support_decision, "finalizer support_decision"
.oracle/checkins/batch-1-r5.md:1665:             if support.backend != self.id:
.oracle/checkins/batch-1-r5.md:1666:                 raise ValueError("finalizer support_decision.backend must match finalizer id")
.oracle/checkins/batch-1-r5.md:1667:             object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r5.md:1678:                 "support_decision": self.support_decision,
.oracle/checkins/batch-1-r5.md:1692:             "support_decision",
.oracle/checkins/batch-1-r5.md:1702:             support_decision=data["support_decision"],
.oracle/checkins/batch-1-r5.md:1861:                 details={"received": version, "supported": [SCHEMA_VERSION]},
.oracle/checkins/batch-1-r5.md:1870:                 f"unsupported {self.LABEL} protocol_version {protocol_version}; "
.oracle/checkins/batch-1-r5.md:1872:                 details={"received": protocol_version, "supported": [SCHEMA_VERSION]},
.oracle/checkins/batch-1-r5.md:1885:                 f"{self.LABEL} has unsupported operations: {', '.join(unknown_operations)}"
.oracle/checkins/batch-1-r5.md:2001:                 result[path] = _artifact_lineage(profile)
.oracle/checkins/batch-1-r5.md:2023:+                result[path] = _artifact_lineage_from_mapping(profile)
.oracle/checkins/batch-1-r5.md:2032:+                    "hashed lineage record {profile, sha256, attachments}; "
.oracle/checkins/batch-1-r5.md:2043:+                _artifact_lineage(profile)
.oracle/checkins/batch-1-r5.md:2045:+                else _artifact_lineage_from_mapping(profile)
.oracle/checkins/batch-1-r5.md:2052:+def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
.oracle/checkins/batch-1-r5.md:2055:+        raise ValueError("artifact lineage sha256 is required and must not be null")
.oracle/checkins/batch-1-r5.md:2078: def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
.oracle/checkins/batch-1-r5.md:2079:     """One hashed artifact lineage record: profile, sha256, attachments."""
.oracle/checkins/batch-1-r5.md:2134:     replay lineage come exclusively from the validated ``RenderPlan`` so a
.oracle/checkins/batch-1-r5.md:2227:     "workspacePath": {
.oracle/checkins/batch-1-r5.md:2465:     "supportReport": {
.oracle/checkins/batch-1-r5.md:2470:         "supported",
.oracle/checkins/batch-1-r5.md:2482:         "supported": {
.oracle/checkins/batch-1-r5.md:2534:         "support_decision"
.oracle/checkins/batch-1-r5.md:2568:         "support_decision": {
.oracle/checkins/batch-1-r5.md:2571:               "$ref": "#/definitions/supportReport"
.oracle/checkins/batch-1-r5.md:2590:         "support_decision"
.oracle/checkins/batch-1-r5.md:2625:         "support_decision": {
.oracle/checkins/batch-1-r5.md:2626:           "$ref": "#/definitions/supportReport"
.oracle/checkins/batch-1-r5.md:2643:         "support_decision"
.oracle/checkins/batch-1-r5.md:2677:         "support_decision": {
.oracle/checkins/batch-1-r5.md:2680:               "$ref": "#/definitions/supportReport"
.oracle/checkins/batch-1-r5.md:2689:     "hashMap": {
.oracle/checkins/batch-1-r5.md:2711:           "$ref": "#/definitions/hashMap"
.oracle/checkins/batch-1-r5.md:2829:           "$ref": "#/definitions/workspacePath"
.oracle/checkins/batch-1-r5.md:2860:           "$ref": "#/definitions/workspacePath"
.oracle/checkins/batch-1-r5.md:2984:           "support_decision": null
.oracle/checkins/batch-1-r5.md:3012:               "support_decision": {
.oracle/checkins/batch-1-r5.md:3014:                 "supported": true,
.oracle/checkins/batch-1-r5.md:3052:   "description": "Versioned routing lineage and deterministic half-open temporal coverage.",
.oracle/checkins/batch-1-r5.md:3382:     "supportReport": {
.oracle/checkins/batch-1-r5.md:3387:         "supported",
.oracle/checkins/batch-1-r5.md:3399:         "supported": {
.oracle/checkins/batch-1-r5.md:3451:         "support_decision"
.oracle/checkins/batch-1-r5.md:3485:         "support_decision": {
.oracle/checkins/batch-1-r5.md:3488:               "$ref": "#/definitions/supportReport"
.oracle/checkins/batch-1-r5.md:3507:         "support_decision"
.oracle/checkins/batch-1-r5.md:3542:         "support_decision": {
.oracle/checkins/batch-1-r5.md:3543:           "$ref": "#/definitions/supportReport"
.oracle/checkins/batch-1-r5.md:3560:         "support_decision"
.oracle/checkins/batch-1-r5.md:3594:         "support_decision": {
.oracle/checkins/batch-1-r5.md:3597:               "$ref": "#/definitions/supportReport"
.oracle/checkins/batch-1-r5.md:3606:     "hashMap": {
.oracle/checkins/batch-1-r5.md:3628:           "$ref": "#/definitions/hashMap"
.oracle/checkins/batch-1-r5.md:3665:         "support_decision": null
.oracle/checkins/batch-1-r5.md:3693:             "support_decision": {
.oracle/checkins/batch-1-r5.md:3695:               "supported": true,
.oracle/checkins/batch-1-r5.md:3824:    94	                result[path] = _artifact_lineage(profile)
.oracle/checkins/batch-1-r5.md:3826:    96	                result[path] = _artifact_lineage_from_mapping(profile)
.oracle/checkins/batch-1-r5.md:3830:   100	                    "hashed lineage record {profile, sha256, attachments}; "
.oracle/checkins/batch-1-r5.md:3837:   107	                _artifact_lineage(profile)
.oracle/checkins/batch-1-r5.md:3839:   109	                else _artifact_lineage_from_mapping(profile)
.oracle/checkins/batch-1-r5.md:3846:   116	def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
.oracle/checkins/batch-1-r5.md:3849:   119	        raise ValueError("artifact lineage sha256 is required and must not be null")
.oracle/checkins/batch-1-r5.md:3872:   142	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
.oracle/checkins/batch-1-r5.md:3873:   143	    """One hashed artifact lineage record: profile, sha256, attachments."""
.oracle/checkins/batch-1-r5.md:3928:   198	    replay lineage come exclusively from the validated ``RenderPlan`` so a
.oracle/checkins/batch-1-r5.md:4046:    28	    "unsupported",
.oracle/checkins/batch-1-r5.md:4137:   119	        "support_decision",
.oracle/checkins/batch-1-r5.md:4287:   908	            _require_schema_version(self.schema_version, "support report"),
.oracle/checkins/batch-1-r5.md:4289:   910	        if not isinstance(self.supported, bool):
.oracle/checkins/batch-1-r5.md:4290:   911	            raise TypeError("supported must be a boolean")
.oracle/checkins/batch-1-r5.md:4318:   939	                "supported": self.supported,
.oracle/checkins/batch-1-r5.md:4330:   951	            data = _require_mapping(payload, "support report")
.oracle/checkins/batch-1-r5.md:4333:   954	                "supported",
.oracle/checkins/batch-1-r5.md:4344:   965	                label="support report",
.oracle/checkins/batch-1-r5.md:4348:   969	                supported=data["supported"],
.oracle/checkins/batch-1-r5.md:4361:   982	                f"malformed support report: {exc}",
.oracle/checkins/batch-1-r5.md:4376:   997	    support_decision: SupportReport | None = None
.oracle/checkins/batch-1-r5.md:4416:  1037	        if self.support_decision is not None:
.oracle/checkins/batch-1-r5.md:4417:  1038	            support = (
.oracle/checkins/batch-1-r5.md:4418:  1039	                self.support_decision
.oracle/checkins/batch-1-r5.md:4419:  1040	                if isinstance(self.support_decision, SupportReport)
.oracle/checkins/batch-1-r5.md:4422:  1043	                        self.support_decision, "planner support_decision"
.oracle/checkins/batch-1-r5.md:4426:  1047	            if support.backend != self.id:
.oracle/checkins/batch-1-r5.md:4427:  1048	                raise ValueError("planner support_decision.backend must match planner id")
.oracle/checkins/batch-1-r5.md:4428:  1049	            object.__setattr__(self, "support_decision", support)
.oracle/checkins/batch-1-r5.md:4439:  1060	                "support_decision": self.support_decision,
.oracle/checkins/batch-1-r5.md:4453:  1074	            "support_decision",
.oracle/checkins/batch-1-r5.md:4463:  1084	            support_decision=data["support_decision"],
.oracle/checkins/batch-1-r5.md:4476:  1097	    support_decision: SupportReport
.oracle/checkins/batch-1-r5.md:4481:  1102	        support = (
.oracle/checkins/batch-1-r5.md:4482:  1103	            self.support_decision
.oracle/checkins/batch-1-r5.md:4483:  1104	            if isinstance(self.support_decision, SupportReport)
.oracle/checkins/batch-1-r5.md:4485:  1106	                _require_mapping(self.support_decision, "renderer support_decision")
.oracle/checkins/batch-1-r5.md:4488:  1109	        if support.backend != renderer_id:
.oracle/checkins/batch-1-r5.md:4489:  1110	            raise ValueError("renderer support_decision.backend must match renderer id")
.oracle/checkins/batch-1-r5.md:4527:  1148	        object.__setattr__(self, "support_decision", support)
   185	        audio=audio,
   186	        attachments=attachments or {},
   187	    )
   188	
   189	
   190	def _result(*, video: VideoArtifact | None = None) -> RenderResult:
   191	    selected = video or _video()
   192	    assert selected.audio is not None
   193	    return RenderResult(
   194	        schema_version=1,
   195	        video=selected,
   196	        backend_fragments={"acme.example": {"renderer": "example"}},
   197	        audio_ownership=selected.audio,
   198	        normalization=[],
   199	        logs=["render completed"],
   200	        metadata={"request_id": "render-001"},
   201	    )
   202	
   203	
   204	def _finalize(
   205	    *,
   206	    plan: RenderPlan | None = None,
   207	    artifacts: list[VideoArtifact] | None = None,
   208	) -> FinalizeRequest:
   209	    selected_plan = plan or _plan()
   210	    return FinalizeRequest(
   211	        schema_version=1,
   212	        plan=selected_plan,
   213	        artifacts=[_video()] if artifacts is None else artifacts,
   214	        output_name="preview.mp4",
   215	        backend_config={"rendering.ffmpeg-finalizer": {"faststart": True}},
   216	        metadata={"request_id": "render-001"},
   217	    )
   218	
   219	
   220	def test_dto_json_round_trip() -> None:
    82	        "to": segment.window.end_frame * denominator / numerator,
    83	    }
    84	
    85	
    86	def _normalize_artifact_profiles(value: Any) -> Any:
    87	    if value is None:
    88	        return []
    89	    if isinstance(value, Mapping):
    90	        result: dict[str, Any] = {}
    91	        for key, profile in value.items():
    92	            path = _require_string(str(key), "artifact key")
    93	            if isinstance(profile, VideoArtifact):
    94	                result[path] = _artifact_lineage(profile)
    95	            elif isinstance(profile, Mapping) and "profile" in profile and "sha256" in profile:
    96	                result[path] = _artifact_lineage_from_mapping(profile)
    97	            else:
    98	                raise TypeError(
    99	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   100	                    "hashed lineage record {profile, sha256, attachments}; "
   101	                    "profile-only entries carry no output hash"
   102	                )
   103	        return result
   104	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   105	        return [
   106	            (
   107	                _artifact_lineage(profile)
   108	                if isinstance(profile, VideoArtifact)
   109	                else _artifact_lineage_from_mapping(profile)
   110	            )
   111	            for profile in value
   112	        ]
   113	    raise TypeError("artifact_profiles must be an object or array")
   114	
   115	
   116	def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
   117	    data = _json_safe_mapping(raw, label="artifact")
   118	    if "sha256" not in data or data["sha256"] is None:
   119	        raise ValueError("artifact lineage sha256 is required and must not be null")
   120	    profile = data["profile"]
   121	    attachments: dict[str, Any] = {}
   122	    for name, att in (data.get("attachments") or {}).items():
   123	        att = _json_safe_mapping(att, label=f"artifact attachment {name!r}")
   124	        if att.get("sha256") is None:
   125	            raise ValueError(f"artifact attachment {name!r} sha256 must not be null")
   126	        attachments[str(name)] = {
   127	            "path": _require_string(str(att.get("path")), f"attachment {name!r} path"),
   128	            "kind": _require_string(str(att.get("kind")), f"attachment {name!r} kind"),
   129	            "sha256": _require_sha256(str(att.get("sha256")), f"attachment {name!r} sha256"),
   130	        }
   131	    return {
   132	        "profile": (
   133	            profile
   134	            if isinstance(profile, RenderProfile)
   135	            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
   136	        ).to_dict(),
   137	        "sha256": _require_sha256(str(data["sha256"]), "artifact sha256"),
   138	        "attachments": attachments,
   139	    }
   140	
   141	
   142	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   143	    """One hashed artifact lineage record: profile, sha256, attachments."""
   144	    return {
   145	        "profile": artifact.profile.to_dict(),
   146	        "sha256": artifact.sha256,
   147	        "attachments": {
   148	            name: {
   149	                "path": attachment.path,
   150	                "kind": attachment.kind,
   151	                "sha256": attachment.sha256,
   152	            }
   153	            for name, attachment in artifact.attachments.items()
   154	        },
   155	    }
   156	
   181	def assemble_provenance_v2(
   182	    *,
   183	    engine: str,
   184	    output: str | Path,
   185	    timeline: str | Path,
   186	    assets_registry: str | Path | None,
   187	    plan: RenderPlan | Mapping[str, Any],
   188	    artifact_profiles: Any = None,
   189	    audio_ownership: AudioOwnership | str | None = None,
   190	    normalization: Sequence[str] = (),
   191	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   192	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   193	    v1_compatibility: Mapping[str, Any] | None = None,
   194	) -> dict[str, Any]:
   195	    """Assemble additive provenance v2 with protected ownership boundaries.
   196	
   197	    ``engine`` is intentionally the legacy request projection. Routing and
   198	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   199	    hybrid invocation cannot collapse multiple renderer identities. Optional
   200	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   201	    any v2 core field.
   202	    """
   203	
   204	    legacy_engine = _require_string(engine, "engine")
   205	    output_path = _require_string(str(output), "output")
   206	    timeline_path = _require_string(str(timeline), "timeline")
   207	    assets_path = None if assets_registry is None else _require_string(
   208	        str(assets_registry), "assets_registry"
   209	    )
   210	    normalized_plan = (
   211	        plan
   212	        if isinstance(plan, RenderPlan)
   213	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   214	    )
   215	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   216	    legacy_segments = [
   217	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   218	    ]
   219	    normalized_normalization = [
   220	        _require_string(item, f"normalization[{index}]")
   221	        for index, item in enumerate(normalization)
   222	    ]
   223	
   224	    payload: dict[str, Any] = {
   225	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   226	        "engine": legacy_engine,
   227	        "output": output_path,
   228	        "timeline": timeline_path,
   229	        "assets_registry": assets_path,
   230	        "request_digest": normalized_plan.request_digest,
   231	        "requested_policy": normalized_plan.requested_policy,
   232	        "planner": normalized_plan.planner.to_dict(),
   233	        # V1-compatible segment projection: flat {engine, from, to} entries,
   234	        # exactly the shape legacy consumers read from `segments`.
   235	        "segments": legacy_segments,
   236	        # Additive normalized v2 segment records; never overwrite v1 fields.
   237	        "segments_v2": normalized_segments,
   238	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
   239	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   240	        "normalization": normalized_normalization,
   241	        "finalizer": normalized_plan.finalizer.to_dict(),
   242	        "attachments": _normalize_attachments(attachments),
   243	        "backend_fragments": validate_backend_fragments(backend_fragments),
   244	    }
   245	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   246	    payload.update(compatibility)
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
   478	are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
   479	output path to `{profile, sha256, attachments: {name: {path, kind, sha256}}}`
   480	with a validated 64-hex `sha256` on the artifact and every attachment
   481	(profile-only entries and null hashes are rejected), so replay can verify
   482	rendered outputs byte-for-byte. `input_hashes` describe inputs only, never
   483	rendered outputs.
   484	
   485	`engine` is only the legacy request projection. The `segments` key keeps the
   486	V1-compatible flat projection: one `{engine, from, to}` entry per segment,
   487	derived from `renderer.id` and the validated integer `FrameWindow` at its
   488	rational FPS — exactly the shape legacy consumers read. The additive

codex
1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)

2. **Lineage mappings remain spoofable.** The required exact `{profile, sha256, attachments}` shape is not enforced: attachments may be missing/null, extra fields are accepted, hashes are stringified before validation—so a 64-digit integer passes—and missing attachment paths/kinds become `"None"`. Sequence entries share this path; mutable `VideoArtifact.attachments` are copied without revalidation. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:95) [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:116)

3. **Schema/DTO parity remains false.**

   - `^(?!.*\u0000)[\s\S]*\S[\s\S]*$` does not detect NUL after a newline because `.` stops at line breaks. For example, `"ok\n\u0000bad"` is schema-valid but DTO-invalid. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:356) [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:217)
   - Support `features` and plan/finalize `hashMap` still lack the claimed `propertyNames` constraints, so blank keys are schema-valid but DTO-invalid. [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:32) [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:538) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:506)
   - `workspacePath` still rejects DTO-valid internal newlines. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22) [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314)
tokens used
351,171
1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)

2. **Lineage mappings remain spoofable.** The required exact `{profile, sha256, attachments}` shape is not enforced: attachments may be missing/null, extra fields are accepted, hashes are stringified before validation—so a 64-digit integer passes—and missing attachment paths/kinds become `"None"`. Sequence entries share this path; mutable `VideoArtifact.attachments` are copied without revalidation. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:95) [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:116)

3. **Schema/DTO parity remains false.**

   - `^(?!.*\u0000)[\s\S]*\S[\s\S]*$` does not detect NUL after a newline because `.` stops at line breaks. For example, `"ok\n\u0000bad"` is schema-valid but DTO-invalid. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:356) [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:217)
   - Support `features` and plan/finalize `hashMap` still lack the claimed `propertyNames` constraints, so blank keys are schema-valid but DTO-invalid. [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:32) [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:538) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:506)
   - `workspacePath` still rejects DTO-valid internal newlines. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22) [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314)

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 91f0fe3..086d692 -- astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py docs/contracts/render-backend-v1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 6a96b91..03786c3 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -1,288 +1,336 @@
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
             raw_attachment
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
 
 
-def _normalize_artifact_profiles(value: Any) -> Any:
+def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
     if value is None:
-        return []
+        value = {}
     if isinstance(value, Mapping):
         result: dict[str, Any] = {}
         for key, profile in value.items():
             path = _require_string(str(key), "artifact key")
             if isinstance(profile, VideoArtifact):
+                if path != profile.path:
+                    raise ValueError(
+                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
+                        f"{profile.path!r}"
+                    )
                 result[path] = _artifact_lineage(profile)
-            elif isinstance(profile, Mapping) and "profile" in profile and "sha256" in profile:
-                result[path] = _artifact_lineage_from_mapping(profile)
+            elif isinstance(profile, Mapping):
+                result[path] = _artifact_lineage_from_mapping(profile, key=path)
             else:
                 raise TypeError(
                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                     "hashed lineage record {profile, sha256, attachments}; "
                     "profile-only entries carry no output hash"
                 )
+        # A positive plan must record a hashed artifact for every segment.
+        if segments and not result:
+            raise ValueError(
+                "artifact_profiles must record a hashed lineage entry for every "
+                "segment of a positive render plan"
+            )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
-        return [
+        lineage = [
             (
                 _artifact_lineage(profile)
                 if isinstance(profile, VideoArtifact)
-                else _artifact_lineage_from_mapping(profile)
+                else _artifact_lineage_from_mapping(profile, key=str(profile.get("path", "")))
             )
             for profile in value
         ]
+        if segments and not lineage:
+            raise ValueError(
+                "artifact_profiles must record a hashed lineage entry for every "
+                "segment of a positive render plan"
+            )
+        return lineage
     raise TypeError("artifact_profiles must be an object or array")
 
 
-def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
-    data = _json_safe_mapping(raw, label="artifact")
-    if "sha256" not in data or data["sha256"] is None:
+def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
+    raw_keys = set(raw)
+    allowed = {"profile", "sha256", "attachments"}
+    unknown = sorted(raw_keys - allowed)
+    if unknown:
+        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
+    missing = sorted(allowed - raw_keys)
+    if missing:
+        raise ValueError(
+            f"artifact lineage is missing required fields: {', '.join(missing)}"
+        )
+    if raw["sha256"] is None:
         raise ValueError("artifact lineage sha256 is required and must not be null")
-    profile = data["profile"]
+    if not isinstance(raw["sha256"], str):
+        raise TypeError("artifact lineage sha256 must be a string")
+    profile = raw["profile"]
     attachments: dict[str, Any] = {}
-    for name, att in (data.get("attachments") or {}).items():
-        att = _json_safe_mapping(att, label=f"artifact attachment {name!r}")
-        if att.get("sha256") is None:
-            raise ValueError(f"artifact attachment {name!r} sha256 must not be null")
-        attachments[str(name)] = {
-            "path": _require_string(str(att.get("path")), f"attachment {name!r} path"),
-            "kind": _require_string(str(att.get("kind")), f"attachment {name!r} kind"),
-            "sha256": _require_sha256(str(att.get("sha256")), f"attachment {name!r} sha256"),
+    raw_attachments = raw["attachments"]
+    if raw_attachments is None:
+        raise ValueError("artifact lineage attachments must be an object (may be empty)")
+    if not isinstance(raw_attachments, Mapping):
+        raise TypeError("artifact lineage attachments must be an object")
+    for name, att in raw_attachments.items():
+        name = _require_string(name, "attachment name")
+        if isinstance(att, Attachment):
+            att = {
+                "path": att.path,
+                "kind": att.kind,
+                "sha256": att.sha256,
+            }
+        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
+        if att_unknown:
+            raise ValueError(
+                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
+            )
+        att_missing = sorted({"path", "kind", "sha256"} - set(att))
+        if att_missing:
+            raise ValueError(
+                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
+            )
+        if not isinstance(att["sha256"], str):
+            raise TypeError(f"attachment {name!r} sha256 must be a string")
+        attachments[name] = {
+            "path": _require_string(att["path"], f"attachment {name!r} path"),
+            "kind": _require_string(att["kind"], f"attachment {name!r} kind"),
+            "sha256": _require_sha256(att["sha256"], f"attachment {name!r} sha256"),
         }
     return {
         "profile": (
             profile
             if isinstance(profile, RenderProfile)
             else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
         ).to_dict(),
-        "sha256": _require_sha256(str(data["sha256"]), "artifact sha256"),
+        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
         "attachments": attachments,
     }
 
 
 def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
     """One hashed artifact lineage record: profile, sha256, attachments."""
-    return {
-        "profile": artifact.profile.to_dict(),
-        "sha256": artifact.sha256,
-        "attachments": {
-            name: {
-                "path": attachment.path,
-                "kind": attachment.kind,
-                "sha256": attachment.sha256,
-            }
-            for name, attachment in artifact.attachments.items()
+    return _artifact_lineage_from_mapping(
+        {
+            "profile": artifact.profile,
+            "sha256": artifact.sha256,
+            "attachments": artifact.attachments,
         },
-    }
+        key=artifact.path,
+    )
 
 
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
+    compatibility = _normalize_v1_compatibility(v1_compatibility)
 
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
-        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
+        "artifact_profiles": _normalize_artifact_profiles(
+            artifact_profiles,
+            segments=normalized_plan.segments,
+        ),
         "audio_ownership": _normalize_audio_ownership(audio_ownership),
         "normalization": normalized_normalization,
         "finalizer": normalized_plan.finalizer.to_dict(),
         "attachments": _normalize_attachments(attachments),
         "backend_fragments": validate_backend_fragments(backend_fragments),
     }
-    compatibility = _normalize_v1_compatibility(v1_compatibility)
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
index 5406c15..47f9307 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -378,206 +378,207 @@ segment use the canonical profile's exact rational FPS (equivalent but
 noncanonical ratios are rejected). The first segment starts at the target,
 every subsequent start equals the preceding end, and the last end equals the
 target end. This tiles the target without leading, internal, or trailing gaps,
 overlap, or reordering. JSON Schema expresses the zero/nonzero structural
 branches; the DTO enforces adjacency, bounds, and exact FPS equality.
 
 Reasons are keyed by zero-based decimal segment index (`"0"`, `"1"`, ...),
 with exactly one entry per segment. A renderer owns all pixels for its assigned
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
-are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
-output path to `{profile, sha256, attachments: {name: {path, kind, sha256}}}`
-with a validated 64-hex `sha256` on the artifact and every attachment
-(profile-only entries and null hashes are rejected), so replay can verify
-rendered outputs byte-for-byte. `input_hashes` describe inputs only, never
-rendered outputs.
+are REQUIRED in `artifact_profiles` for any positive render plan as hashed
+lineage records: each maps an output path to exactly `{profile, sha256,
+attachments}` with a validated 64-hex string `sha256` on the artifact and
+every attachment `{path, kind, sha256}` (profile-only entries, null/malformed
+hashes, unknown fields, and missing fields are rejected; mapping keys must
+equal the artifact's own path), so replay can verify rendered outputs
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
    data.
 3. **Backends have qualified IDs.** Built-ins should resolve canonically as
    names such as `rendering.remotion` and `rendering.ffmpeg`; short legacy names
    remain compatibility aliases.
 4. **Only trusted discovered packs contribute implementations.** Reuse existing
    pack permission, precedence, conflict, alias, and override semantics. Do not
    accept arbitrary CLI import strings.
 5. **`rendering.render` remains the stable facade.** Existing pipelines should
    not need to know how a backend is loaded or invoked.
 6. **Selection is deterministic and inspectable.** A render plan records the
    selected backend for every segment plus the capability evidence and reason.
 7. **Unsupported requests fail closed by default.** Fallback occurs only when
    an explicit planner policy or ordered fallback list permits it.
 8. **Every backend returns a validated artifact.** Finalizers consume declared
    media metadata rather than assuming that arbitrary MP4 files are compatible.
 9. **Final assembly is explicit.** Ship an FFmpeg finalizer first, but keep
    finalization behind a contract so arbitrary backends do not become secretly
    coupled to inlined FFmpeg logic.
 10. **Compatibility precedes semantic cleanup.** Preserve current
     `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 36769e5..69b4791 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -592,329 +592,355 @@ def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: P
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
-        artifact_profiles={},
+        artifact_profiles={
+            "outputs/visual.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_B,
+                "attachments": {},
+            }
+        },
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
         plan=_plan(),
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     with pytest.raises(TypeError, match="hashed lineage"):
         assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
+            artifact_profiles={
+                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
+            },
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": "not-a-hash",
+                    "attachments": {},
+                }
+            },
+        )
+    with pytest.raises(ValueError, match="unknown fields"):
+        assemble_provenance_v2(
+            **base,
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {},
+                    "spoof": 1,
+                }
+            },
         )
 
 
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

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '1,380p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '520,820p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
    25	    _validate_backend_fragments,
    26	)
    27	
    28	
    29	PROVENANCE_SCHEMA_VERSION = 2
    30	CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)
    31	
    32	
    33	def validate_backend_fragments(
    34	    fragments: Mapping[str, Mapping[str, Any]] | None,
    35	) -> dict[str, dict[str, Any]]:
    36	    """Validate namespaces and reject top-level core-key collisions."""
    37	
    38	    return _validate_backend_fragments(fragments or {})
    39	
    40	
    41	def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
    42	    if value is None:
    43	        return None
    44	    if isinstance(value, AudioOwnership):
    45	        return value.value
    46	    try:
    47	        return AudioOwnership(value).value
    48	    except (TypeError, ValueError) as exc:
    49	        raise ValueError(
    50	            "audio_ownership must be rendered, passthrough, none, or null"
    51	        ) from exc
    52	
    53	
    54	def _normalize_attachments(
    55	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None,
    56	) -> dict[str, Any]:
    57	    result: dict[str, Any] = {}
    58	    for raw_name, raw_attachment in (attachments or {}).items():
    59	        name = _require_string(raw_name, "attachment key")
    60	        attachment = (
    61	            raw_attachment
    62	            if isinstance(raw_attachment, Attachment)
    63	            else Attachment.from_dict(raw_attachment)
    64	        )
    65	        if attachment.name != name:
    66	            raise ValueError(
    67	                f"attachment key {name!r} must match attachment.name {attachment.name!r}"
    68	            )
    69	        if name in result:
    70	            raise ValueError(f"duplicate attachment name: {name}")
    71	        result[name] = attachment.to_dict()
    72	    return result
    73	
    74	
    75	def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
    76	    """Derive one v1 segment projection from an authoritative v2 segment."""
    77	
    78	    numerator, denominator = segment.window.fps_rational
    79	    return {
    80	        "engine": segment.renderer.id.rsplit(".", 1)[-1],
    81	        "from": segment.window.start_frame * denominator / numerator,
    82	        "to": segment.window.end_frame * denominator / numerator,
    83	    }
    84	
    85	
    86	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
    87	    if value is None:
    88	        value = {}
    89	    if isinstance(value, Mapping):
    90	        result: dict[str, Any] = {}
    91	        for key, profile in value.items():
    92	            path = _require_string(str(key), "artifact key")
    93	            if isinstance(profile, VideoArtifact):
    94	                if path != profile.path:
    95	                    raise ValueError(
    96	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
    97	                        f"{profile.path!r}"
    98	                    )
    99	                result[path] = _artifact_lineage(profile)
   100	            elif isinstance(profile, Mapping):
   101	                result[path] = _artifact_lineage_from_mapping(profile, key=path)
   102	            else:
   103	                raise TypeError(
   104	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   105	                    "hashed lineage record {profile, sha256, attachments}; "
   106	                    "profile-only entries carry no output hash"
   107	                )
   108	        # A positive plan must record a hashed artifact for every segment.
   109	        if segments and not result:
   110	            raise ValueError(
   111	                "artifact_profiles must record a hashed lineage entry for every "
   112	                "segment of a positive render plan"
   113	            )
   114	        return result
   115	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   116	        lineage = [
   117	            (
   118	                _artifact_lineage(profile)
   119	                if isinstance(profile, VideoArtifact)
   120	                else _artifact_lineage_from_mapping(profile, key=str(profile.get("path", "")))
   121	            )
   122	            for profile in value
   123	        ]
   124	        if segments and not lineage:
   125	            raise ValueError(
   126	                "artifact_profiles must record a hashed lineage entry for every "
   127	                "segment of a positive render plan"
   128	            )
   129	        return lineage
   130	    raise TypeError("artifact_profiles must be an object or array")
   131	
   132	
   133	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   134	    raw_keys = set(raw)
   135	    allowed = {"profile", "sha256", "attachments"}
   136	    unknown = sorted(raw_keys - allowed)
   137	    if unknown:
   138	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   139	    missing = sorted(allowed - raw_keys)
   140	    if missing:
   141	        raise ValueError(
   142	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   143	        )
   144	    if raw["sha256"] is None:
   145	        raise ValueError("artifact lineage sha256 is required and must not be null")
   146	    if not isinstance(raw["sha256"], str):
   147	        raise TypeError("artifact lineage sha256 must be a string")
   148	    profile = raw["profile"]
   149	    attachments: dict[str, Any] = {}
   150	    raw_attachments = raw["attachments"]
   151	    if raw_attachments is None:
   152	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   153	    if not isinstance(raw_attachments, Mapping):
   154	        raise TypeError("artifact lineage attachments must be an object")
   155	    for name, att in raw_attachments.items():
   156	        name = _require_string(name, "attachment name")
   157	        if isinstance(att, Attachment):
   158	            att = {
   159	                "path": att.path,
   160	                "kind": att.kind,
   161	                "sha256": att.sha256,
   162	            }
   163	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   164	        if att_unknown:
   165	            raise ValueError(
   166	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   167	            )
   168	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   169	        if att_missing:
   170	            raise ValueError(
   171	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   172	            )
   173	        if not isinstance(att["sha256"], str):
   174	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   175	        attachments[name] = {
   176	            "path": _require_string(att["path"], f"attachment {name!r} path"),
   177	            "kind": _require_string(att["kind"], f"attachment {name!r} kind"),
   178	            "sha256": _require_sha256(att["sha256"], f"attachment {name!r} sha256"),
   179	        }
   180	    return {
   181	        "profile": (
   182	            profile
   183	            if isinstance(profile, RenderProfile)
   184	            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
   185	        ).to_dict(),
   186	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   187	        "attachments": attachments,
   188	    }
   189	
   190	
   191	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   192	    """One hashed artifact lineage record: profile, sha256, attachments."""
   193	    return _artifact_lineage_from_mapping(
   194	        {
   195	            "profile": artifact.profile,
   196	            "sha256": artifact.sha256,
   197	            "attachments": artifact.attachments,
   198	        },
   199	        key=artifact.path,
   200	    )
   201	
   202	
   203	def _normalize_v1_compatibility(
   204	    fields: Mapping[str, Any] | None,
   205	) -> dict[str, Any]:
   206	    if fields is None:
   207	        raise ValueError(
   208	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   209	        )
   210	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   211	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   212	    if unknown:
   213	        raise ValueError(
   214	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   215	            + ", ".join(unknown)
   216	        )
   217	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   218	    if missing:
   219	        raise ValueError(
   220	            "v1 compatibility projection is missing always-emitted fields: "
   221	            + ", ".join(missing)
   222	        )
   223	    return compatibility
   224	
   225	
   226	def assemble_provenance_v2(
   227	    *,
   228	    engine: str,
   229	    output: str | Path,
   230	    timeline: str | Path,
   231	    assets_registry: str | Path | None,
   232	    plan: RenderPlan | Mapping[str, Any],
   233	    artifact_profiles: Any = None,
   234	    audio_ownership: AudioOwnership | str | None = None,
   235	    normalization: Sequence[str] = (),
   236	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   237	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   238	    v1_compatibility: Mapping[str, Any] | None = None,
   239	) -> dict[str, Any]:
   240	    """Assemble additive provenance v2 with protected ownership boundaries.
   241	
   242	    ``engine`` is intentionally the legacy request projection. Routing and
   243	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   244	    hybrid invocation cannot collapse multiple renderer identities. Optional
   245	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   246	    any v2 core field.
   247	    """
   248	
   249	    legacy_engine = _require_string(engine, "engine")
   250	    output_path = _require_string(str(output), "output")
   251	    timeline_path = _require_string(str(timeline), "timeline")
   252	    assets_path = None if assets_registry is None else _require_string(
   253	        str(assets_registry), "assets_registry"
   254	    )
   255	    normalized_plan = (
   256	        plan
   257	        if isinstance(plan, RenderPlan)
   258	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   259	    )
   260	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   261	    legacy_segments = [
   262	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   263	    ]
   264	    normalized_normalization = [
   265	        _require_string(item, f"normalization[{index}]")
   266	        for index, item in enumerate(normalization)
   267	    ]
   268	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   269	
   270	    payload: dict[str, Any] = {
   271	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   272	        "engine": legacy_engine,
   273	        "output": output_path,
   274	        "timeline": timeline_path,
   275	        "assets_registry": assets_path,
   276	        "request_digest": normalized_plan.request_digest,
   277	        "requested_policy": normalized_plan.requested_policy,
   278	        "planner": normalized_plan.planner.to_dict(),
   279	        # V1-compatible segment projection: flat {engine, from, to} entries,
   280	        # exactly the shape legacy consumers read from `segments`.
   281	        "segments": legacy_segments,
   282	        # Additive normalized v2 segment records; never overwrite v1 fields.
   283	        "segments_v2": normalized_segments,
   284	        "artifact_profiles": _normalize_artifact_profiles(
   285	            artifact_profiles,
   286	            segments=normalized_plan.segments,
   287	        ),
   288	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   289	        "normalization": normalized_normalization,
   290	        "finalizer": normalized_plan.finalizer.to_dict(),
   291	        "attachments": _normalize_attachments(attachments),
   292	        "backend_fragments": validate_backend_fragments(backend_fragments),
   293	    }
   294	    payload.update(compatibility)
   295	    return _json_safe_mapping(payload, label="provenance")
   296	
   297	
   298	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   299	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   300	
   301	    return assemble_provenance_v2(**kwargs)
   302	
   303	
   304	def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
   305	    """Assemble and atomically write a provenance v2 sidecar."""
   306	
   307	    payload = assemble_provenance_v2(**kwargs)
   308	    write_json_atomic(path, payload)
   309	    return payload
   310	
   311	
   312	def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
   313	    """Return stable SHA-256 input hashes using Astrid's shared helper."""
   314	
   315	    return {
   316	        _require_string(name, "input hash name"): sha256_file(Path(path))
   317	        for name, path in paths.items()
   318	    }
   319	
   320	
   321	def digest_manifest(path: str | Path) -> str:
   322	    """Return the SHA-256 digest used to pin one static manifest."""
   323	
   324	    return sha256_file(Path(path))
   325	
   326	
   327	__all__ = [
   328	    "CORE_OWNED_KEYS",
   329	    "PROVENANCE_SCHEMA_VERSION",
   330	    "assemble_provenance",
   331	    "assemble_provenance_v2",
   332	    "digest_manifest",
   333	    "hash_input_files",
   334	    "validate_backend_fragments",
   335	    "write_provenance_v2",
   336	]
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
   572	            }
   573	        },
   574	        "audio_ownership": AudioOwnership.RENDERED,
   575	        "normalization": [],
   576	        "attachments": {},
   577	        "backend_fragments": {"acme.first": {"vendor": "Acme"}},
   578	        "v1_compatibility": compatibility,
   579	    }
   580	    payload = assemble_provenance_v2(**kwargs)
   581	    assert payload["schema_version"] == 2
   582	    assert payload["request_digest"] == SHA_D
   583	    assert payload["requested_policy"] == "hybrid"
   584	    assert payload["planner"] == _planner().to_dict()
   585	    assert [segment["renderer"]["id"] for segment in payload["segments_v2"]] == [
   586	        "acme.first",
   587	        "other.second",
   588	    ]
   589	    assert payload["segments_v2"] == [segment.to_dict() for segment in plan.segments]
   590	    assert [set(segment) for segment in payload["segments_v2"]] == [
   591	        {"window", "renderer", "input_hashes"},
   592	        {"window", "renderer", "input_hashes"},
   593	    ]
   594	    # V1-compatible projections are preserved unchanged.
   595	    assert payload["segments"] == [
   596	        {"engine": "first", "from": 0.0, "to": 1.0},
   597	        {"engine": "second", "from": 1.0, "to": 2.0},
   598	    ]
   599	    # segment_provenance passes through from the v1 compatibility projection
   600	    # verbatim — the host never rewrites it.
   601	    assert payload["segment_provenance"] == compatibility["segment_provenance"]
   602	    assert payload["finalizer"] == _finalizer().to_dict()
   603	    assert payload["composition_id"] == "TimelineComposition"
   604	
   605	    sidecar = tmp_path / "video.mp4.provenance.json"
   606	    assert write_provenance_v2(sidecar, **kwargs) == payload
   607	    assert sidecar.read_text(encoding="utf-8").endswith("\n")
   608	
   609	
   610	def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None:
   611	    plan = _plan().to_dict()
   612	    plan["segments"][0]["engine"] = "spoofed"
   613	    with pytest.raises(RendererProtocolError):
   614	        assemble_provenance_v2(
   615	            engine="hybrid",
   616	            output="out/video.mp4",
   617	            timeline="timeline.json",
   618	            assets_registry=None,
   619	            plan=plan,
   620	            v1_compatibility=_compatibility(),
   621	        )
   622	
   623	
   624	def test_compute_request_digest_is_canonical_and_stable() -> None:
   625	    from astrid.core.rendering.contracts import compute_request_digest
   626	
   627	    a = {"backend_config": {"acme.visual": {"quality": "preview"}}, "schema_version": 1}
   628	    b = {"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}}}
   629	    assert compute_request_digest(a) == compute_request_digest(b)
   630	    digest = compute_request_digest(a)
   631	    assert isinstance(digest, str)
   632	    assert len(digest) == 64
   633	    assert compute_request_digest({**a, "metadata": {"x": "y"}}) != digest
   634	    assert compute_request_digest({"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}, "other.key": {}}}) != digest
   635	
   636	
   637	def test_shared_sha256_helper_is_used_for_input_hashes(tmp_path: Path) -> None:
   638	    input_path = tmp_path / "timeline.json"
   639	    input_path.write_text("abc", encoding="utf-8")
   640	    hashes = hash_input_files({"timeline": input_path})
   641	    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
   642	
   643	
   644	def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
   645	    """Non-default alias/override/trust/support evidence must survive the
   646	    plan wire round-trip and the final provenance sidecar."""
   647	    planner = replace(
   648	        _planner(),
   649	        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
   650	        override={"from": "acme.hybrid-planner", "to": "rendering.legacy_hybrid"},
   651	        support_decision=_support("rendering.legacy_hybrid"),
   652	    )
   653	    renderer = replace(
   654	        _renderer("acme.visual"),
   655	        alias_chain=["visual", "acme.visual"],
   656	        override={"from": "acme.visual-2", "to": "acme.visual"},
   657	        trust_eligibility={"eligible": True, "method": "source-tree"},
   658	    )
   659	    finalizer = replace(
   660	        _finalizer(),
   661	        alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
   662	        override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
   663	        trust_eligibility={"eligible": True, "method": "source-tree"},
   664	        support_decision=_support("rendering.ffmpeg-finalizer"),
   665	    )
   666	    plan = _plan(
   667	        planner=planner,
   668	        segments=[
   669	            _segment(0, 24, renderer=renderer),
   670	            _segment(24, 48),
   671	        ],
   672	        finalizer=finalizer,
   673	    )
   674	
   675	    # Wire round-trip
   676	    reparsed = RenderPlan.from_dict(plan.to_dict())
   677	    assert reparsed.planner.alias_chain == planner.alias_chain
   678	    assert reparsed.planner.override == planner.override
   679	    assert reparsed.planner.support_decision is not None
   680	    assert reparsed.segments[0].renderer.trust_eligibility == renderer.trust_eligibility
   681	    assert reparsed.finalizer.alias_chain == finalizer.alias_chain
   682	    assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
   683	    assert reparsed.finalizer.support_decision is not None
   684	
   685	    # Provenance sidecar carries the same evidence
   686	    payload = assemble_provenance_v2(
   687	        engine="hybrid",
   688	        output="/workspace/out/video.mp4",
   689	        timeline="/workspace/timeline.json",
   690	        assets_registry=None,
   691	        plan=plan,
   692	        artifact_profiles={
   693	            "outputs/visual.mp4": {
   694	                "profile": _profile(),
   695	                "sha256": SHA_B,
   696	                "attachments": {},
   697	            }
   698	        },
   699	        audio_ownership="rendered",
   700	        normalization=[],
   701	        attachments={},
   702	        backend_fragments={},
   703	        v1_compatibility=_compatibility(),
   704	    )
   705	    assert payload["planner"]["alias_chain"] == planner.alias_chain
   706	    assert payload["planner"]["override"] == planner.override
   707	    assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
   708	    assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
   709	    assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
   710	    assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
   711	
   712	
   713	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   714	    """Every capability resolution requires the complete evidence set;
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
   741	        attachments={
   742	            "alpha": Attachment(
   743	                name="alpha",
   744	                path="outputs/alpha.mp4",
   745	                kind="alpha",
   746	                sha256=SHA_C,
   747	            )
   748	        },
   749	    )
   750	    payload = assemble_provenance_v2(
   751	        engine="hybrid",
   752	        output="/workspace/out/video.mp4",
   753	        timeline="/workspace/timeline.json",
   754	        assets_registry=None,
   755	        plan=_plan(),
   756	        artifact_profiles={"outputs/visual.mp4": artifact},
   757	        audio_ownership="rendered",
   758	        normalization=[],
   759	        attachments={},
   760	        backend_fragments={},
   761	        v1_compatibility=_compatibility(),
   762	    )
   763	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
   764	    assert lineage["sha256"] == SHA_B
   765	    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
   766	    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
   767	
   768	
   769	def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
   770	    """support_decision.backend must equal the resolution id for planner and
   771	    finalizer, exactly as it does for renderer."""
   772	    cases = (
   773	        (_planner, "planner"),
   774	        (_finalizer, "finalizer"),
   775	        (_renderer, "renderer"),
   776	    )
   777	    for factory, label in cases:
   778	        payload = factory().to_dict()
   779	        payload["support_decision"] = _support("other.backend").to_dict()
   780	        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
   781	            type(factory()).from_dict(payload)
   782	
   783	
   784	def test_resolutions_reject_incoherent_override_records() -> None:
   785	    """Override records must be {from, to} with to == resolution id."""
   786	    cases = (
   787	        (_planner, "planner"),
   788	        (_finalizer, "finalizer"),
   789	        (_renderer, "renderer"),
   790	    )
   791	    for factory, label in cases:
   792	        payload = factory().to_dict()
   793	        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
   794	        with pytest.raises(ValueError, match=f"{label} override 'to'"):
   795	            type(factory()).from_dict(payload)
   796	        payload["override"] = {"only": "one"}
   797	        with pytest.raises(ValueError, match=f"{label} override"):
   798	            type(factory()).from_dict(payload)
   799	
   800	
   801	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   802	    """Artifact lineage must carry a real sha256; profile-only entries and
   803	    null hashes are rejected rather than stringified."""
   804	    base = dict(
   805	        engine="hybrid",
   806	        output="/workspace/out/video.mp4",
   807	        timeline="/workspace/timeline.json",
   808	        assets_registry=None,
   809	        plan=_plan(),
   810	        audio_ownership="rendered",
   811	        normalization=[],
   812	        attachments={},
   813	        backend_fragments={},
   814	        v1_compatibility=_compatibility(),
   815	    )
   816	    with pytest.raises(TypeError, match="hashed lineage"):
   817	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
   818	    with pytest.raises(ValueError, match="sha256"):
   819	        assemble_provenance_v2(
   820	            **base,

exec
/bin/zsh -lc "rg -n \"artifact_profiles|_normalize_artifact_profiles|assemble_provenance_v2|assemble_provenance\\(\" -g '*.py' -g '*.md' -g '*.json' --glob '"'!.oracle/checkins/batch-1-r5.md'"' --glob '"'!remotion/node_modules/**'"' . | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
./tests/core/rendering/test_contracts.py:37:    assemble_provenance_v2,
./tests/core/rendering/test_contracts.py:543:        assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
./tests/core/rendering/test_contracts.py:580:    payload = assemble_provenance_v2(**kwargs)
./tests/core/rendering/test_contracts.py:614:        assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:686:    payload = assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:692:        artifact_profiles={
./tests/core/rendering/test_contracts.py:750:    payload = assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:756:        artifact_profiles={"outputs/visual.mp4": artifact},
./tests/core/rendering/test_contracts.py:763:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
./tests/core/rendering/test_contracts.py:817:        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
./tests/core/rendering/test_contracts.py:819:        assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:821:            artifact_profiles={
./tests/core/rendering/test_contracts.py:826:        assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:828:            artifact_profiles={
./tests/core/rendering/test_contracts.py:837:        assemble_provenance_v2(
./tests/core/rendering/test_contracts.py:839:            artifact_profiles={
./docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
./docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan as hashed
./astrid/core/rendering/provenance.py:86:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
./astrid/core/rendering/provenance.py:96:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
./astrid/core/rendering/provenance.py:104:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
./astrid/core/rendering/provenance.py:111:                "artifact_profiles must record a hashed lineage entry for every "
./astrid/core/rendering/provenance.py:126:                "artifact_profiles must record a hashed lineage entry for every "
./astrid/core/rendering/provenance.py:130:    raise TypeError("artifact_profiles must be an object or array")
./astrid/core/rendering/provenance.py:226:def assemble_provenance_v2(
./astrid/core/rendering/provenance.py:233:    artifact_profiles: Any = None,
./astrid/core/rendering/provenance.py:284:        "artifact_profiles": _normalize_artifact_profiles(
./astrid/core/rendering/provenance.py:285:            artifact_profiles,
./astrid/core/rendering/provenance.py:298:def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
./astrid/core/rendering/provenance.py:299:    """Compatibility spelling for :func:`assemble_provenance_v2`."""
./astrid/core/rendering/provenance.py:301:    return assemble_provenance_v2(**kwargs)
./astrid/core/rendering/provenance.py:307:    payload = assemble_provenance_v2(**kwargs)
./astrid/core/rendering/provenance.py:331:    "assemble_provenance_v2",
./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
./astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '446,500p' && nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '280,390p' && nl -ba astrid/core/rendering/contracts.py | sed -n '1,120p;180,340p;540,760p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   446	5. Invoke `render`, or invoke `plan` followed by each segment render.
   447	6. Parse only the authoritative result file and validate all artifacts.
   448	7. Invoke the explicit finalizer when required and validate again.
   449	8. Acquire the per-output publication lock, rename the final video, then
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
   478	are REQUIRED in `artifact_profiles` for any positive render plan as hashed
   479	lineage records: each maps an output path to exactly `{profile, sha256,
   480	attachments}` with a validated 64-hex string `sha256` on the artifact and
   481	every attachment `{path, kind, sha256}` (profile-only entries, null/malformed
   482	hashes, unknown fields, and missing fields are rejected; mapping keys must
   483	equal the artifact's own path), so replay can verify rendered outputs
   484	byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
   485	
   486	`engine` is only the legacy request projection. The `segments` key keeps the
   487	V1-compatible flat projection: one `{engine, from, to}` entry per segment,
   488	derived from `renderer.id` and the validated integer `FrameWindow` at its
   489	rational FPS — exactly the shape legacy consumers read. The additive
   490	`segments_v2` key carries the complete normalized v2 segment records
   491	(`window`, `renderer` resolution, `input_hashes`); it never overwrites or
   492	reshapes a V1 key. When the v1 `segment_provenance` top-level projection
   493	applies, core passes it through VERBATIM from the caller's compatibility
   494	projection — it is never rewritten or re-derived.
   495	
   496	For the whole epic, core also preserves every current v1 top-level projection:
   497	
   498	`project_dir`, `composition_id`, `active_pack_order`, `active_theme`,
   499	`registry_hash`, `registry_state`, `resolved_effect_ids`, `resolved_effects`,
   500	`source_pack_ids`, `element_roots`, `staged_asset_ids`, `staged_asset_root`,
   280	          "else": {
   281	            "properties": {
   282	              "audio": {
   283	                "enum": [
   284	                  "passthrough",
   285	                  "none",
   286	                  null
   287	                ]
   288	              }
   289	            }
   290	          }
   291	        }
   292	      ]
   293	    },
   294	    "backendFragments": {
   295	      "type": "object",
   296	      "propertyNames": {
   297	        "$ref": "#/definitions/qualifiedId"
   298	      },
   299	      "additionalProperties": {
   300	        "type": "object",
   301	        "propertyNames": {
   302	          "not": {
   303	            "enum": [
   304	              "schema_version",
   305	              "video",
   306	              "backend_fragments",
   307	              "audio_ownership",
   308	              "normalization",
   309	              "logs",
   310	              "metadata",
   311	              "engine",
   312	              "output",
   313	              "timeline",
   314	              "assets_registry",
   315	              "request_digest",
   316	              "requested_policy",
   317	              "planner",
   318	              "segments",
   319	              "artifact_profiles",
   320	              "finalizer",
   321	              "attachments",
   322	              "project_dir",
   323	              "composition_id",
   324	              "active_pack_order",
   325	              "active_theme",
   326	              "registry_hash",
   327	              "registry_state",
   328	              "resolved_effect_ids",
   329	              "resolved_effects",
   330	              "source_pack_ids",
   331	              "element_roots",
   332	              "staged_asset_ids",
   333	              "staged_asset_root",
   334	              "segment_provenance",
   335	              "ffmpeg_specialization",
   336	              "audio_reactive_colour",
   337	              "resolved_backend",
   338	              "source_pack",
   339	              "alias_chain",
   340	              "override",
   341	              "trust_eligibility",
   342	              "manifest_digest",
   343	              "support_decision",
   344	              "input_hashes",
   345	              "segments_v2"
   346	            ]
   347	          }
   348	        }
   349	      }
   350	    },
   351	    "stringArray": {
   352	      "type": "array",
   353	      "items": {
   354	        "type": "string",
   355	        "minLength": 1,
   356	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   357	      }
   358	    },
   359	    "stringMap": {
   360	      "type": "object",
   361	      "propertyNames": {
   362	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   363	      },
   364	      "additionalProperties": {
   365	        "type": "string",
   366	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   367	      }
   368	    },
   369	    "success": {
   370	      "type": "object",
   371	      "additionalProperties": false,
   372	      "required": [
   373	        "schema_version",
   374	        "video",
   375	        "audio_ownership"
   376	      ],
   377	      "properties": {
   378	        "schema_version": {
   379	          "type": "integer",
   380	          "const": 1
   381	        },
   382	        "video": {
   383	          "$ref": "#/definitions/videoArtifact"
   384	        },
   385	        "backend_fragments": {
   386	          "$ref": "#/definitions/backendFragments"
   387	        },
   388	        "audio_ownership": {
   389	          "$ref": "#/definitions/audioOwnership"
   390	        },
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
   251	    """Validate an override record: ``{from, to}`` with ``to`` equal to the
   252	    resolution id (the override is what selected this implementation)."""
   253	    mapping = _json_safe_mapping(value, label=label)
   254	    required = {"from", "to"}
   255	    if set(mapping) != required:
   256	        raise ValueError(f"{label} must contain exactly 'from' and 'to'")
   257	    _require_qualified_id(mapping["from"], f"{label} 'from'")
   258	    resolved = _require_qualified_id(mapping["to"], f"{label} 'to'")
   259	    if resolved != capability_id:
   260	        raise ValueError(f"{label} 'to' must equal the resolved capability id {capability_id!r}")
   261	    return mapping
   262	
   263	
   264	def _require_string_list(value: Any, label: str) -> list[str]:
   265	    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
   266	        raise TypeError(f"{label} must be an array of strings")
   267	    return [_require_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
   268	
   269	
   270	def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
   271	    mapping = _require_mapping(value, label)
   272	    return {
   273	        _require_string(key, f"{label} key"): _require_string(item, f"{label}[{key!r}]")
   274	        for key, item in mapping.items()
   275	    }
   276	
   277	
   278	def _require_hash_mapping(value: Any, label: str) -> dict[str, str]:
   279	    mapping = _require_mapping(value, label)
   280	    return {
   281	        _require_string(key, f"{label} key"): _require_sha256(item, f"{label}[{key!r}]")
   282	        for key, item in mapping.items()
   283	    }
   284	
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
   327	    return raw
   328	
   329	
   330	def _relative_file_path(path: str | Path, workspace_root: str | Path, label: str) -> tuple[str, Path]:
   331	    root = Path(workspace_root).resolve()
   332	    candidate = Path(path)
   333	    if not candidate.is_absolute():
   334	        candidate = root / candidate
   335	    resolved = candidate.resolve(strict=True)
   336	    try:
   337	        relative = resolved.relative_to(root)
   338	    except ValueError as exc:
   339	        raise ValueError(f"{label} escapes invocation workspace {root}") from exc
   340	    return relative.as_posix(), resolved
   540	            "video_level",
   541	            "pixel_format",
   542	            "duration_tolerance",
   543	        }
   544	        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
   545	        _validate_object_keys(data, required=required, allowed=allowed, label="render profile")
   546	        return cls(
   547	            width=data["width"],
   548	            height=data["height"],
   549	            fps_rational=data["fps_rational"],
   550	            time_base=data["time_base"],
   551	            container=data["container"],
   552	            video_codec=data["video_codec"],
   553	            video_profile=data["video_profile"],
   554	            video_level=data["video_level"],
   555	            pixel_format=data["pixel_format"],
   556	            audio_codec=data.get("audio_codec"),
   557	            audio_sample_rate=data.get("audio_sample_rate"),
   558	            audio_channel_layout=data.get("audio_channel_layout"),
   559	            duration_tolerance=data["duration_tolerance"],
   560	        )
   561	
   562	
   563	def _validate_artifact_audio(
   564	    profile: RenderProfile,
   565	    ownership: AudioOwnership | None,
   566	    label: str,
   567	) -> None:
   568	    """Keep probed media audio and ownership semantically aligned.
   569	
   570	    ``rendered`` means the artifact itself contains audio and therefore has a
   571	    populated audio profile. ``passthrough`` and ``none`` describe visual-only
   572	    artifacts; the former asks the host/finalizer to supply canonical audio.
   573	    """
   574	
   575	    if profile.has_audio:
   576	        if ownership is not AudioOwnership.RENDERED:
   577	            raise ValueError(f"{label} with an audio profile must declare audio='rendered'")
   578	    elif ownership is AudioOwnership.RENDERED:
   579	        raise ValueError(f"{label} with audio='rendered' must have an audio profile")
   580	
   581	
   582	@dataclass(frozen=True)
   583	class Attachment:
   584	    """A named, opaque artifact preserved alongside the primary video."""
   585	
   586	    name: str
   587	    path: str
   588	    kind: str
   589	    sha256: str
   590	
   591	    def __post_init__(self) -> None:
   592	        name = _require_string(self.name, "attachment name")
   593	        if not _OUTPUT_NAME_RE.fullmatch(name):
   594	            raise ValueError("attachment name must be a portable basename")
   595	        kind = _require_string(self.kind, "attachment kind")
   596	        if not _KIND_RE.fullmatch(kind):
   597	            raise ValueError("attachment kind must be a lowercase hyphenated token")
   598	        object.__setattr__(self, "name", name)
   599	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))
   600	        object.__setattr__(self, "kind", kind)
   601	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "attachment sha256"))
   602	
   603	    def to_dict(self) -> dict[str, Any]:
   604	        return _json_safe_mapping(
   605	            {"name": self.name, "path": self.path, "kind": self.kind, "sha256": self.sha256}
   606	        )
   607	
   608	    @classmethod
   609	    def from_dict(cls, payload: Mapping[str, Any]) -> Attachment:
   610	        data = _require_mapping(payload, "attachment")
   611	        required = {"name", "path", "kind", "sha256"}
   612	        _validate_object_keys(data, required=required, allowed=required, label="attachment")
   613	        return cls(
   614	            name=data["name"],
   615	            path=data["path"],
   616	            kind=data["kind"],
   617	            sha256=data["sha256"],
   618	        )
   619	
   620	    @classmethod
   621	    def from_file(
   622	        cls,
   623	        *,
   624	        name: str,
   625	        path: str | Path,
   626	        kind: str,
   627	        workspace_root: str | Path,
   628	    ) -> Attachment:
   629	        relative, resolved = _relative_file_path(path, workspace_root, "attachment path")
   630	        return cls(name=name, path=relative, kind=kind, sha256=sha256_file(resolved))
   631	
   632	
   633	def _coerce_attachment_mapping(value: Any, label: str) -> dict[str, Attachment]:
   634	    mapping = _require_mapping(value, label)
   635	    result: dict[str, Attachment] = {}
   636	    seen_names: set[str] = set()
   637	    for raw_key, raw_attachment in mapping.items():
   638	        key = _require_string(raw_key, f"{label} key")
   639	        attachment = (
   640	            raw_attachment
   641	            if isinstance(raw_attachment, Attachment)
   642	            else Attachment.from_dict(_require_mapping(raw_attachment, f"{label}[{key!r}]"))
   643	        )
   644	        if attachment.name != key:
   645	            raise ValueError(
   646	                f"{label} key {key!r} must match attachment.name {attachment.name!r}"
   647	            )
   648	        if attachment.name in seen_names:
   649	            raise ValueError(f"duplicate attachment name: {attachment.name}")
   650	        seen_names.add(attachment.name)
   651	        result[key] = attachment
   652	    return result
   653	
   654	
   655	@dataclass(frozen=True)
   656	class VideoArtifact:
   657	    """The required primary video produced by a renderer or finalizer."""
   658	
   659	    path: str
   660	    profile: RenderProfile
   661	    sha256: str
   662	    duration_frames: int
   663	    audio: AudioOwnership | None = None
   664	    attachments: dict[str, Attachment] = field(default_factory=dict)
   665	
   666	    def __post_init__(self) -> None:
   667	        profile = (
   668	            self.profile
   669	            if isinstance(self.profile, RenderProfile)
   670	            else RenderProfile.from_dict(_require_mapping(self.profile, "video profile"))
   671	        )
   672	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
   673	        object.__setattr__(self, "profile", profile)
   674	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
   675	        object.__setattr__(
   676	            self,
   677	            "duration_frames",
   678	            _require_int(self.duration_frames, "duration_frames", minimum=1),
   679	        )
   680	        audio = _coerce_audio_ownership(self.audio, "video audio", nullable=True)
   681	        _validate_artifact_audio(profile, audio, "video artifact")
   682	        object.__setattr__(self, "audio", audio)
   683	        object.__setattr__(
   684	            self,
   685	            "attachments",
   686	            _coerce_attachment_mapping(self.attachments, "video attachments"),
   687	        )
   688	
   689	    def to_dict(self) -> dict[str, Any]:
   690	        return _json_safe_mapping(
   691	            {
   692	                "path": self.path,
   693	                "profile": self.profile,
   694	                "sha256": self.sha256,
   695	                "duration_frames": self.duration_frames,
   696	                "audio": self.audio,
   697	                "attachments": self.attachments,
   698	            }
   699	        )
   700	
   701	    @classmethod
   702	    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
   703	        data = _require_mapping(payload, "video artifact")
   704	        required = {"path", "profile", "sha256", "duration_frames"}
   705	        allowed = required | {"audio", "attachments"}
   706	        _validate_object_keys(data, required=required, allowed=allowed, label="video artifact")
   707	        return cls(
   708	            path=data["path"],
   709	            profile=RenderProfile.from_dict(data["profile"]),
   710	            sha256=data["sha256"],
   711	            duration_frames=data["duration_frames"],
   712	            audio=data.get("audio"),
   713	            attachments=data.get("attachments", {}),
   714	        )
   715	
   716	    @classmethod
   717	    def from_file(
   718	        cls,
   719	        *,
   720	        path: str | Path,
   721	        workspace_root: str | Path,
   722	        profile: RenderProfile,
   723	        duration_frames: int,
   724	        audio: AudioOwnership | None = None,
   725	        attachments: Mapping[str, Attachment] | None = None,
   726	    ) -> VideoArtifact:
   727	        relative, resolved = _relative_file_path(path, workspace_root, "video path")
   728	        return cls(
   729	            path=relative,
   730	            profile=profile,
   731	            sha256=sha256_file(resolved),
   732	            duration_frames=duration_frames,
   733	            audio=audio,
   734	            attachments=dict(attachments or {}),
   735	        )
   736	
   737	
   738	def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
   739	    if value is None and nullable:
   740	        return None
   741	    if isinstance(value, RenderProfile):
   742	        return value
   743	    return RenderProfile.from_dict(_require_mapping(value, label))
   744	
   745	
   746	def _coerce_window(value: Any, label: str, *, nullable: bool) -> FrameWindow | None:
   747	    if value is None and nullable:
   748	        return None
   749	    if isinstance(value, FrameWindow):
   750	        return value
   751	    return FrameWindow.from_dict(_require_mapping(value, label))
   752	
   753	
   754	def _coerce_namespaced_backend_config(value: Any, label: str) -> BackendConfig:
   755	    mapping = _require_mapping(value, label)
   756	    result: BackendConfig = {}
   757	    for raw_backend, raw_config in mapping.items():
   758	        backend = _require_qualified_id(raw_backend, f"{label} key")
   759	        result[backend] = _json_safe_mapping(raw_config, label=f"{label}[{backend!r}]")
   760	    return result

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=60 91f0fe3..086d692 -- astrid/core/rendering/schemas/v1/request.json astrid/core/rendering/schemas/v1/result.json astrid/core/rendering/schemas/v1/support.json astrid/core/rendering/schemas/v1/plan.json astrid/core/rendering/schemas/v1/finalize.json' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 0775c9a..8319f7b 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -8,638 +8,641 @@
     "schema_version",
     "plan",
     "artifacts",
     "output_name"
   ],
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "plan": {
       "allOf": [
         {
           "$ref": "#/definitions/renderPlan"
         },
         {
           "properties": {
             "total_frames": {
               "minimum": 1
             }
           }
         }
       ]
     },
     "artifacts": {
       "type": "array",
       "minItems": 1,
       "items": {
         "$ref": "#/definitions/videoArtifact"
       }
     },
     "output_name": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "backend_config": {
       "$ref": "#/definitions/backendConfig"
     },
     "metadata": {
       "$ref": "#/definitions/stringMap"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}$"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "portableName": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
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
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
       "enum": [
         "rendered",
         "passthrough",
         "none"
       ]
     },
     "positiveRational": {
       "type": "array",
       "minItems": 2,
       "maxItems": 2,
       "items": {
         "type": "integer",
         "minimum": 1
       }
     },
     "frameRange": {
       "type": "array",
       "minItems": 2,
       "maxItems": 2,
       "items": [
         {
           "type": "integer",
           "minimum": 0
         },
         {
           "type": "integer",
           "minimum": 1
         }
       ],
       "additionalItems": false
     },
     "frameWindow": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "start_frame",
         "end_frame",
         "fps_rational"
       ],
       "properties": {
         "start_frame": {
           "type": "integer",
           "minimum": 0
         },
         "end_frame": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "source_range": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameRange"
             },
             {
               "type": "null"
             }
           ]
         },
         "speed": {
           "type": [
             "number",
             "null"
           ],
           "exclusiveMinimum": 0
         }
       }
     },
     "renderProfile": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "width",
         "height",
         "fps_rational",
         "time_base",
         "container",
         "video_codec",
         "video_profile",
         "video_level",
         "pixel_format",
         "duration_tolerance"
       ],
       "properties": {
         "width": {
           "type": "integer",
           "minimum": 1
         },
         "height": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
           "properties": {
             "audio_codec": {
               "type": "null"
             },
             "audio_sample_rate": {
               "type": "null"
             },
             "audio_channel_layout": {
               "type": "null"
             }
           }
         },
         {
           "required": [
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "supported",
         "reasons",
         "features",
         "alternatives",
         "backend",
         "backend_version"
       ],
       "properties": {
         "schema_version": {
           "type": "integer",
           "const": 1
         },
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
           }
         },
         "alternatives": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "$ref": "#/definitions/qualifiedId"
           }
         },
         "backend": {
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
         "source_pack",
         "manifest_digest",
         "alias_chain",
         "override",
         "trust_eligibility",
         "support_decision"
       ],
       "properties": {
         "id": {
           "$ref": "#/definitions/qualifiedId"
         },
         "source_pack": {
           "type": "object"
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "support_decision": {
           "anyOf": [
             {
               "$ref": "#/definitions/supportReport"
             },
             {
               "type": "null"
             }
           ]
         }
       }
     },
     "rendererResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
         "source_pack",
         "manifest_digest",
         "alias_chain",
         "override",
         "trust_eligibility",
         "support_decision"
       ],
       "properties": {
         "id": {
           "$ref": "#/definitions/qualifiedId"
         },
         "source_pack": {
           "type": "object"
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "support_decision": {
           "$ref": "#/definitions/supportReport"
         },
         "trust_eligibility": {
           "type": "object"
         }
       }
     },
     "finalizerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
         "source_pack",
         "manifest_digest",
         "alias_chain",
         "override",
         "trust_eligibility",
         "support_decision"
       ],
       "properties": {
         "id": {
           "$ref": "#/definitions/qualifiedId"
         },
         "source_pack": {
           "type": "object"
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "trust_eligibility": {
           "type": "object"
         },
         "support_decision": {
           "anyOf": [
             {
               "$ref": "#/definitions/supportReport"
             },
             {
               "type": "null"
             }
           ]
         }
       }
     },
     "hashMap": {
       "type": "object",
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
+      },
+      "propertyNames": {
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "renderSegment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "window",
         "renderer",
         "input_hashes"
       ],
       "properties": {
         "window": {
           "$ref": "#/definitions/frameWindow"
         },
         "renderer": {
           "$ref": "#/definitions/rendererResolution"
         },
         "input_hashes": {
           "$ref": "#/definitions/hashMap"
         }
       }
     },
     "renderPlan": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "request_digest",
         "requested_policy",
         "planner",
         "segments",
         "finalizer",
         "profile",
         "total_frames",
         "reasons",
         "window"
       ],
       "properties": {
         "schema_version": {
           "type": "integer",
           "const": 1
         },
         "request_digest": {
           "$ref": "#/definitions/sha256"
         },
         "requested_policy": {
           "$ref": "#/definitions/requestedPolicy"
         },
         "planner": {
           "$ref": "#/definitions/plannerResolution"
         },
         "segments": {
           "type": "array",
           "items": {
             "$ref": "#/definitions/renderSegment"
           }
         },
         "finalizer": {
           "$ref": "#/definitions/finalizerResolution"
         },
         "profile": {
           "$ref": "#/definitions/renderProfile"
         },
         "total_frames": {
           "type": "integer",
           "minimum": 0
         },
         "reasons": {
           "type": "object",
           "propertyNames": {
             "pattern": "^(0|[1-9][0-9]*)$"
           },
           "additionalProperties": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "window": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameWindow"
             },
             {
               "type": "null"
             }
           ]
         }
       },
       "allOf": [
         {
           "if": {
             "properties": {
               "total_frames": {
                 "const": 0
               }
             }
           },
           "then": {
             "properties": {
               "segments": {
                 "maxItems": 0
               },
               "reasons": {
                 "maxProperties": 0
               },
               "window": {
                 "type": "null"
               }
             }
           },
           "else": {
             "properties": {
               "segments": {
                 "minItems": 1
               }
             }
           }
         }
       ]
     },
     "attachment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "name",
         "path",
         "kind",
         "sha256"
       ],
       "properties": {
         "name": {
           "$ref": "#/definitions/portableName"
         },
         "path": {
           "$ref": "#/definitions/workspacePath"
@@ -653,167 +656,167 @@
         }
       }
     },
     "attachments": {
       "type": "object",
       "propertyNames": {
         "$ref": "#/definitions/portableName"
       },
       "additionalProperties": {
         "$ref": "#/definitions/attachment"
       }
     },
     "videoArtifact": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "path",
         "profile",
         "sha256",
         "duration_frames"
       ],
       "properties": {
         "path": {
           "$ref": "#/definitions/workspacePath"
         },
         "profile": {
           "$ref": "#/definitions/renderProfile"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         },
         "duration_frames": {
           "type": "integer",
           "minimum": 1
         },
         "audio": {
           "anyOf": [
             {
               "$ref": "#/definitions/audioOwnership"
             },
             {
               "type": "null"
             }
           ]
         },
         "attachments": {
           "$ref": "#/definitions/attachments"
         }
       },
       "allOf": [
         {
           "if": {
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
             ],
             "properties": {
               "audio": {
                 "const": "rendered"
               }
             }
           },
           "else": {
             "properties": {
               "audio": {
                 "enum": [
                   "passthrough",
                   "none",
                   null
                 ]
               }
             }
           }
         }
       ]
     },
     "backendConfig": {
       "type": "object",
       "propertyNames": {
         "$ref": "#/definitions/qualifiedId"
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "overrideRecord": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "from",
         "to"
       ],
       "properties": {
         "from": {
           "$ref": "#/definitions/qualifiedId"
         },
         "to": {
           "$ref": "#/definitions/qualifiedId"
         }
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "plan": {
         "schema_version": 1,
         "request_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
         "requested_policy": "hybrid",
         "planner": {
           "id": "rendering.legacy_hybrid",
           "source_pack": {
             "id": "rendering"
           },
           "manifest_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
           "trust_eligibility": {
             "eligible": true
           },
           "alias_chain": [],
           "override": null,
           "support_decision": null
         },
         "segments": [
           {
             "window": {
               "start_frame": 0,
               "end_frame": 48,
               "fps_rational": [
                 24,
                 1
               ],
               "source_range": [
                 10,
                 58
               ],
               "speed": 1.0
             },
             "renderer": {
               "id": "acme.example",
               "source_pack": {
                 "id": "acme"
               },
               "manifest_digest": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index e889fe2..feb4bc2 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -1,601 +1,604 @@
 {
   "$schema": "http://json-schema.org/draft-07/schema#",
   "$id": "https://astrid.local/schemas/rendering/v1/plan.json",
   "title": "Astrid render plan v1",
   "description": "Versioned routing lineage and deterministic half-open temporal coverage.",
   "type": "object",
   "additionalProperties": false,
   "required": [
     "schema_version",
     "request_digest",
     "requested_policy",
     "planner",
     "segments",
     "finalizer",
     "profile",
     "total_frames",
     "reasons",
     "window"
   ],
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "request_digest": {
       "$ref": "#/definitions/sha256"
     },
     "requested_policy": {
       "$ref": "#/definitions/requestedPolicy"
     },
     "planner": {
       "$ref": "#/definitions/plannerResolution"
     },
     "segments": {
       "type": "array",
       "items": {
         "$ref": "#/definitions/renderSegment"
       }
     },
     "finalizer": {
       "$ref": "#/definitions/finalizerResolution"
     },
     "profile": {
       "$ref": "#/definitions/renderProfile"
     },
     "total_frames": {
       "type": "integer",
       "minimum": 0
     },
     "reasons": {
       "type": "object",
       "propertyNames": {
         "pattern": "^(0|[1-9][0-9]*)$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "window": {
       "anyOf": [
         {
           "$ref": "#/definitions/frameWindow"
         },
         {
           "type": "null"
         }
       ]
     }
   },
   "allOf": [
     {
       "if": {
         "properties": {
           "total_frames": {
             "const": 0
           }
         }
       },
       "then": {
         "properties": {
           "segments": {
             "maxItems": 0
           },
           "reasons": {
             "maxProperties": 0
           },
           "window": {
             "type": "null"
           }
         }
       },
       "else": {
         "properties": {
           "segments": {
             "minItems": 1
           }
         }
       }
     }
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}$"
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
       "enum": [
         "rendered",
         "passthrough",
         "none"
       ]
     },
     "positiveRational": {
       "type": "array",
       "minItems": 2,
       "maxItems": 2,
       "items": {
         "type": "integer",
         "minimum": 1
       }
     },
     "frameRange": {
       "type": "array",
       "minItems": 2,
       "maxItems": 2,
       "items": [
         {
           "type": "integer",
           "minimum": 0
         },
         {
           "type": "integer",
           "minimum": 1
         }
       ],
       "additionalItems": false
     },
     "frameWindow": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "start_frame",
         "end_frame",
         "fps_rational"
       ],
       "properties": {
         "start_frame": {
           "type": "integer",
           "minimum": 0
         },
         "end_frame": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "source_range": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameRange"
             },
             {
               "type": "null"
             }
           ]
         },
         "speed": {
           "type": [
             "number",
             "null"
           ],
           "exclusiveMinimum": 0
         }
       }
     },
     "renderProfile": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "width",
         "height",
         "fps_rational",
         "time_base",
         "container",
         "video_codec",
         "video_profile",
         "video_level",
         "pixel_format",
         "duration_tolerance"
       ],
       "properties": {
         "width": {
           "type": "integer",
           "minimum": 1
         },
         "height": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
           "properties": {
             "audio_codec": {
               "type": "null"
             },
             "audio_sample_rate": {
               "type": "null"
             },
             "audio_channel_layout": {
               "type": "null"
             }
           }
         },
         {
           "required": [
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "supported",
         "reasons",
         "features",
         "alternatives",
         "backend",
         "backend_version"
       ],
       "properties": {
         "schema_version": {
           "type": "integer",
           "const": 1
         },
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
           }
         },
         "alternatives": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "$ref": "#/definitions/qualifiedId"
           }
         },
         "backend": {
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
         "source_pack",
         "manifest_digest",
         "alias_chain",
         "override",
         "trust_eligibility",
         "support_decision"
       ],
       "properties": {
         "id": {
           "$ref": "#/definitions/qualifiedId"
         },
         "source_pack": {
           "type": "object"
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "support_decision": {
           "anyOf": [
             {
               "$ref": "#/definitions/supportReport"
             },
             {
               "type": "null"
             }
           ]
         }
       }
     },
     "rendererResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
         "source_pack",
         "manifest_digest",
         "alias_chain",
         "override",
         "trust_eligibility",
         "support_decision"
       ],
       "properties": {
         "id": {
           "$ref": "#/definitions/qualifiedId"
         },
         "source_pack": {
           "type": "object"
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "support_decision": {
           "$ref": "#/definitions/supportReport"
         },
         "trust_eligibility": {
           "type": "object"
         }
       }
     },
     "finalizerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
         "source_pack",
         "manifest_digest",
         "alias_chain",
         "override",
         "trust_eligibility",
         "support_decision"
       ],
       "properties": {
         "id": {
           "$ref": "#/definitions/qualifiedId"
         },
         "source_pack": {
           "type": "object"
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "trust_eligibility": {
           "type": "object"
         },
         "support_decision": {
           "anyOf": [
             {
               "$ref": "#/definitions/supportReport"
             },
             {
               "type": "null"
             }
           ]
         }
       }
     },
     "hashMap": {
       "type": "object",
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
+      },
+      "propertyNames": {
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "renderSegment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "window",
         "renderer",
         "input_hashes"
       ],
       "properties": {
         "window": {
           "$ref": "#/definitions/frameWindow"
         },
         "renderer": {
           "$ref": "#/definitions/rendererResolution"
         },
         "input_hashes": {
           "$ref": "#/definitions/hashMap"
         }
       }
     },
     "overrideRecord": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "from",
         "to"
       ],
       "properties": {
         "from": {
           "$ref": "#/definitions/qualifiedId"
         },
         "to": {
           "$ref": "#/definitions/qualifiedId"
         }
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "request_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
       "requested_policy": "hybrid",
       "planner": {
         "id": "rendering.legacy_hybrid",
         "source_pack": {
           "id": "rendering"
         },
         "manifest_digest": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
         "trust_eligibility": {
           "eligible": true
         },
         "alias_chain": [],
         "override": null,
         "support_decision": null
       },
       "segments": [
         {
           "window": {
diff --git a/astrid/core/rendering/schemas/v1/request.json b/astrid/core/rendering/schemas/v1/request.json
index fa3ad8b..a69ff83 100644
--- a/astrid/core/rendering/schemas/v1/request.json
+++ b/astrid/core/rendering/schemas/v1/request.json
@@ -1,164 +1,164 @@
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
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "timeline_path": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "assets_registry_path": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "output_name": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "window": {
       "anyOf": [
         {
           "$ref": "#/definitions/frameWindow"
         },
         {
           "type": "null"
         }
       ]
     },
     "audio": {
       "anyOf": [
         {
           "$ref": "#/definitions/audioOwnership"
         },
         {
           "type": "null"
         }
       ]
     },
     "profile": {
       "anyOf": [
         {
           "$ref": "#/definitions/renderProfile"
         },
         {
           "type": "null"
         }
       ]
     },
     "backend_config": {
       "$ref": "#/definitions/backendConfig"
     },
     "metadata": {
       "$ref": "#/definitions/stringMap"
     }
   },
   "allOf": [
     {
       "if": {
         "required": [
           "audio",
           "profile"
         ],
         "properties": {
           "audio": {
             "const": "rendered"
           },
           "profile": {
             "type": "object"
           }
         }
       },
       "then": {
         "properties": {
           "profile": {
             "required": [
               "audio_codec",
               "audio_sample_rate",
               "audio_channel_layout"
             ],
             "properties": {
               "audio_codec": {
                 "type": "string",
-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             }
           }
         }
       }
     },
     {
       "if": {
         "required": [
           "audio",
           "profile"
         ],
         "properties": {
           "audio": {
             "enum": [
               "passthrough",
               "none"
             ]
           },
           "profile": {
             "type": "object"
           }
         }
       },
       "then": {
         "properties": {
           "profile": {
             "properties": {
               "audio_codec": {
                 "type": "null"
               },
               "audio_sample_rate": {
                 "type": "null"
               },
               "audio_channel_layout": {
                 "type": "null"
               }
             }
           }
         }
       }
     }
   ],
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "audioOwnership": {
       "type": "string",
       "enum": [
         "rendered",
         "passthrough",
         "none"
       ]
     },
     "positiveRational": {
       "type": "array",
       "minItems": 2,
       "maxItems": 2,
@@ -198,227 +198,227 @@
         },
         "end_frame": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "source_range": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameRange"
             },
             {
               "type": "null"
             }
           ]
         },
         "speed": {
           "type": [
             "number",
             "null"
           ],
           "exclusiveMinimum": 0
         }
       }
     },
     "renderProfile": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "width",
         "height",
         "fps_rational",
         "time_base",
         "container",
         "video_codec",
         "video_profile",
         "video_level",
         "pixel_format",
         "duration_tolerance"
       ],
       "properties": {
         "width": {
           "type": "integer",
           "minimum": 1
         },
         "height": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
           "properties": {
             "audio_codec": {
               "type": "null"
             },
             "audio_sample_rate": {
               "type": "null"
             },
             "audio_channel_layout": {
               "type": "null"
             }
           }
         },
         {
           "required": [
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "backendConfig": {
       "type": "object",
       "propertyNames": {
         "$ref": "#/definitions/qualifiedId"
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "timeline_path": "/workspace/timeline.json",
       "assets_registry_path": "/workspace/assets.json",
       "output_name": "preview.mp4",
       "window": {
         "start_frame": 0,
         "end_frame": 48,
         "fps_rational": [
           24,
           1
         ],
         "source_range": [
           10,
           58
         ],
         "speed": 1.0
       },
       "audio": "rendered",
       "profile": {
         "width": 1920,
         "height": 1080,
         "fps_rational": [
           24,
           1
         ],
         "time_base": [
           1,
           12288
         ],
         "container": "mp4",
         "video_codec": "h264",
         "video_profile": "high",
         "video_level": "4.1",
         "pixel_format": "yuv420p",
         "audio_codec": "aac",
         "audio_sample_rate": 48000,
         "audio_channel_layout": "stereo",
         "duration_tolerance": 1
       },
       "backend_config": {
         "acme.example": {
           "quality": "preview"
         }
       },
       "metadata": {
         "project_id": "demo"
       }
     }
   ]
 }
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index fc7c34e..577adb3 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -1,426 +1,426 @@
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
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}$"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "portableName": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
       "not": {
         "enum": [
           ".",
           ".."
         ]
       }
     },
     "audioOwnership": {
       "type": "string",
       "enum": [
         "rendered",
         "passthrough",
         "none"
       ]
     },
     "positiveRational": {
       "type": "array",
       "minItems": 2,
       "maxItems": 2,
       "items": {
         "type": "integer",
         "minimum": 1
       }
     },
     "renderProfile": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "width",
         "height",
         "fps_rational",
         "time_base",
         "container",
         "video_codec",
         "video_profile",
         "video_level",
         "pixel_format",
         "duration_tolerance"
       ],
       "properties": {
         "width": {
           "type": "integer",
           "minimum": 1
         },
         "height": {
           "type": "integer",
           "minimum": 1
         },
         "fps_rational": {
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
           "properties": {
             "audio_codec": {
               "type": "null"
             },
             "audio_sample_rate": {
               "type": "null"
             },
             "audio_channel_layout": {
               "type": "null"
             }
           }
         },
         {
           "required": [
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "attachment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "name",
         "path",
         "kind",
         "sha256"
       ],
       "properties": {
         "name": {
           "$ref": "#/definitions/portableName"
         },
         "path": {
           "$ref": "#/definitions/workspacePath"
         },
         "kind": {
           "type": "string",
           "pattern": "^[a-z][a-z0-9-]*$"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         }
       }
     },
     "attachments": {
       "type": "object",
       "propertyNames": {
         "$ref": "#/definitions/portableName"
       },
       "additionalProperties": {
         "$ref": "#/definitions/attachment"
       }
     },
     "videoArtifact": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "path",
         "profile",
         "sha256",
         "duration_frames"
       ],
       "properties": {
         "path": {
           "$ref": "#/definitions/workspacePath"
         },
         "profile": {
           "$ref": "#/definitions/renderProfile"
         },
         "sha256": {
           "$ref": "#/definitions/sha256"
         },
         "duration_frames": {
           "type": "integer",
           "minimum": 1
         },
         "audio": {
           "anyOf": [
             {
               "$ref": "#/definitions/audioOwnership"
             },
             {
               "type": "null"
             }
           ]
         },
         "attachments": {
           "$ref": "#/definitions/attachments"
         }
       },
       "allOf": [
         {
           "if": {
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
             ],
             "properties": {
               "audio": {
                 "const": "rendered"
               }
             }
           },
           "else": {
             "properties": {
               "audio": {
                 "enum": [
                   "passthrough",
                   "none",
                   null
                 ]
               }
             }
           }
         }
       ]
     },
     "backendFragments": {
       "type": "object",
       "propertyNames": {
         "$ref": "#/definitions/qualifiedId"
       },
       "additionalProperties": {
         "type": "object",
         "propertyNames": {
           "not": {
             "enum": [
               "schema_version",
               "video",
               "backend_fragments",
               "audio_ownership",
               "normalization",
               "logs",
               "metadata",
               "engine",
               "output",
               "timeline",
               "assets_registry",
               "request_digest",
               "requested_policy",
               "planner",
               "segments",
               "artifact_profiles",
               "finalizer",
               "attachments",
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
               "segment_provenance",
               "ffmpeg_specialization",
               "audio_reactive_colour",
               "resolved_backend",
               "source_pack",
               "alias_chain",
               "override",
               "trust_eligibility",
               "manifest_digest",
               "support_decision",
               "input_hashes",
               "segments_v2"
             ]
           }
         }
       }
     },
     "stringArray": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "success": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "video",
         "audio_ownership"
       ],
       "properties": {
         "schema_version": {
           "type": "integer",
           "const": 1
         },
         "video": {
           "$ref": "#/definitions/videoArtifact"
         },
         "backend_fragments": {
           "$ref": "#/definitions/backendFragments"
         },
         "audio_ownership": {
           "$ref": "#/definitions/audioOwnership"
         },
         "normalization": {
           "$ref": "#/definitions/stringArray"
         },
         "logs": {
           "$ref": "#/definitions/stringArray"
         },
         "metadata": {
           "$ref": "#/definitions/stringMap"
         }
       },
       "oneOf": [
         {
           "properties": {
             "audio_ownership": {
               "const": "rendered"
             },
             "video": {
               "properties": {
                 "audio": {
                   "const": "rendered"
                 }
               },
               "required": [
                 "audio"
               ]
             }
           }
         },
         {
           "properties": {
             "audio_ownership": {
               "const": "passthrough"
             },
             "video": {
               "properties": {
                 "audio": {
@@ -429,129 +429,129 @@
               },
               "required": [
                 "audio"
               ]
             }
           }
         },
         {
           "properties": {
             "audio_ownership": {
               "const": "none"
             },
             "video": {
               "properties": {
                 "audio": {
                   "const": "none"
                 }
               },
               "required": [
                 "audio"
               ]
             }
           }
         }
       ]
     },
     "error": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "kind",
         "backend",
         "message",
         "recovery_command",
         "details"
       ],
       "properties": {
         "schema_version": {
           "type": "integer",
           "const": 1
         },
         "kind": {
           "type": "string",
           "enum": [
             "protocol",
             "unsupported",
             "binary_missing",
             "timeout",
             "interrupted",
             "invalid_artifact",
             "internal"
           ]
         },
         "backend": {
           "$ref": "#/definitions/qualifiedId"
         },
         "message": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "recovery_command": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "details": {
           "type": "object"
         }
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "video": {
         "path": "outputs/video.mp4",
         "profile": {
           "width": 1920,
           "height": 1080,
           "fps_rational": [
             24,
             1
           ],
           "time_base": [
             1,
             12288
           ],
           "container": "mp4",
           "video_codec": "h264",
           "video_profile": "high",
           "video_level": "4.1",
           "pixel_format": "yuv420p",
           "audio_codec": "aac",
           "audio_sample_rate": 48000,
           "audio_channel_layout": "stereo",
           "duration_tolerance": 1
         },
         "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
         "duration_frames": 48,
         "audio": "rendered",
         "attachments": {
           "project.blend": {
             "name": "project.blend",
             "path": "outputs/project.blend",
             "kind": "project",
             "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
           }
         }
       },
       "backend_fragments": {
         "acme.example": {
           "renderer": "example"
         }
       },
       "audio_ownership": "rendered",
       "normalization": [],
       "logs": [
         "render completed"
       ],
       "metadata": {
         "request_id": "render-001"
       }
     },
     {
diff --git a/astrid/core/rendering/schemas/v1/support.json b/astrid/core/rendering/schemas/v1/support.json
index 614a8a0..af94ae5 100644
--- a/astrid/core/rendering/schemas/v1/support.json
+++ b/astrid/core/rendering/schemas/v1/support.json
@@ -1,80 +1,83 @@
 {
   "$schema": "http://json-schema.org/draft-07/schema#",
   "$id": "https://astrid.local/schemas/rendering/v1/support.json",
   "title": "Astrid renderer support report v1",
   "type": "object",
   "additionalProperties": false,
   "required": [
     "schema_version",
     "supported",
     "reasons",
     "features",
     "alternatives",
     "backend",
     "backend_version"
   ],
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "supported": {
       "type": "boolean"
     },
     "reasons": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "features": {
       "type": "object",
       "additionalProperties": {
         "type": [
           "boolean",
           "string"
         ]
+      },
+      "propertyNames": {
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "alternatives": {
       "type": "array",
       "uniqueItems": true,
       "items": {
         "$ref": "#/definitions/qualifiedId"
       }
     },
     "backend": {
       "$ref": "#/definitions/qualifiedId"
     },
     "backend_version": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "supported": true,
       "reasons": [],
       "features": {
         "media": true,
         "audio_mode": "rendered"
       },
       "alternatives": [],
       "backend": "acme.example",
       "backend_version": "1.0.0"
     }
   ]
 }

exec
/bin/zsh -lc "rg -nF '(?"'!.*'"\\\\u0000)' astrid/core/rendering/schemas/v1 || true
rg -n '\"workspacePath\"|\"pattern\": \"\\"'^'"\\(\\?"'!'"\\[A-Za-z\\]' astrid/core/rendering/schemas/v1/*.json
rg -n '\"features\"|\"hashMap\"|\"propertyNames\"' astrid/core/rendering/schemas/v1/{support,plan,finalize}.json | sed -n '1,260p'
for f in astrid/core/rendering/schemas/v1/*.json; do jq empty \""'$f" || exit; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
astrid/core/rendering/schemas/v1/result.json:25:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
astrid/core/rendering/schemas/v1/finalize.json:68:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
astrid/core/rendering/schemas/v1/support.json:11:    "features",
astrid/core/rendering/schemas/v1/support.json:32:    "features": {
astrid/core/rendering/schemas/v1/support.json:40:      "propertyNames": {
astrid/core/rendering/schemas/v1/support.json:74:      "features": {
astrid/core/rendering/schemas/v1/plan.json:52:      "propertyNames": {
astrid/core/rendering/schemas/v1/plan.json:331:        "features",
astrid/core/rendering/schemas/v1/plan.json:352:        "features": {
astrid/core/rendering/schemas/v1/plan.json:538:    "hashMap": {
astrid/core/rendering/schemas/v1/plan.json:543:      "propertyNames": {
astrid/core/rendering/schemas/v1/plan.json:632:              "features": {
astrid/core/rendering/schemas/v1/plan.json:666:          "features": {},
astrid/core/rendering/schemas/v1/plan.json:733:          "features": {},
astrid/core/rendering/schemas/v1/finalize.json:299:        "features",
astrid/core/rendering/schemas/v1/finalize.json:320:        "features": {
astrid/core/rendering/schemas/v1/finalize.json:506:    "hashMap": {
astrid/core/rendering/schemas/v1/finalize.json:511:      "propertyNames": {
astrid/core/rendering/schemas/v1/finalize.json:582:          "propertyNames": {
astrid/core/rendering/schemas/v1/finalize.json:661:      "propertyNames": {
astrid/core/rendering/schemas/v1/finalize.json:748:      "propertyNames": {
astrid/core/rendering/schemas/v1/finalize.json:757:      "propertyNames": {
astrid/core/rendering/schemas/v1/finalize.json:832:                "features": {
astrid/core/rendering/schemas/v1/finalize.json:866:            "features": {},

exec
/bin/zsh -lc "rg -n \"def _coerce.*feature|features\" astrid/core/rendering/contracts.py | sed -n '1,140p' && nl -ba astrid/core/rendering/contracts.py | sed -n '860,990p' && nl -ba astrid/core/rendering/schemas/v1/plan.json | sed -n '310,370p;525,555p' && nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '280,340p;495,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
899:    features: dict[str, bool | str]
913:        feature_mapping = _require_mapping(self.features, "features")
914:        features: dict[str, bool | str] = {}
918:                raise TypeError(f"features[{key!r}] must be a boolean or string")
919:            features[key] = raw_value
920:        object.__setattr__(self, "features", features)
941:                "features": self.features,
956:                "features",
971:                features=data["features"],
1864:def _manifest_features(value: Any, label: str) -> dict[str, bool | str]:
2064:                    "features",
2076:        if "features" in capabilities:
2077:            result["features"] = _manifest_features(capabilities["features"], "features")
2103:            allowed=frozenset({"policies", "supports_fallback", "features"}),
2113:        if "features" in capabilities:
2114:            result["features"] = _manifest_features(capabilities["features"], "features")
2130:                {"containers", "preserves_attachments", "audio_ownership", "features"}
2149:        if "features" in capabilities:
2150:            result["features"] = _manifest_features(capabilities["features"], "features")
   860	                profile=data.get("profile"),
   861	                backend_config=data.get("backend_config", {}),
   862	                metadata=data.get("metadata", {}),
   863	            )
   864	        except Exception as exc:
   865	            from .errors import RendererException
   866	
   867	            if isinstance(exc, RendererException):
   868	                raise
   869	            _protocol_failure(
   870	                f"malformed render request: {exc}",
   871	                details={"error_type": type(exc).__name__},
   872	            )
   873	
   874	    def for_backend(self, backend: str) -> RenderRequest:
   875	        """Return the request projection visible to one selected backend."""
   876	
   877	        qualified = _require_qualified_id(backend, "backend")
   878	        selected = self.backend_config.get(qualified)
   879	        return RenderRequest(
   880	            schema_version=self.schema_version,
   881	            timeline_path=self.timeline_path,
   882	            assets_registry_path=self.assets_registry_path,
   883	            output_name=self.output_name,
   884	            window=self.window,
   885	            audio=self.audio,
   886	            profile=self.profile,
   887	            backend_config={qualified: selected} if selected is not None else {},
   888	            metadata=self.metadata,
   889	        )
   890	
   891	
   892	@dataclass(frozen=True)
   893	class SupportReport:
   894	    """Request-sensitive support evidence returned by an implementation."""
   895	
   896	    schema_version: int
   897	    supported: bool
   898	    reasons: list[str]
   899	    features: dict[str, bool | str]
   900	    alternatives: list[str]
   901	    backend: str
   902	    backend_version: str | None = None
   903	
   904	    def __post_init__(self) -> None:
   905	        object.__setattr__(
   906	            self,
   907	            "schema_version",
   908	            _require_schema_version(self.schema_version, "support report"),
   909	        )
   910	        if not isinstance(self.supported, bool):
   911	            raise TypeError("supported must be a boolean")
   912	        object.__setattr__(self, "reasons", _require_string_list(self.reasons, "reasons"))
   913	        feature_mapping = _require_mapping(self.features, "features")
   914	        features: dict[str, bool | str] = {}
   915	        for raw_key, raw_value in feature_mapping.items():
   916	            key = _require_string(raw_key, "feature key")
   917	            if not isinstance(raw_value, (bool, str)):
   918	                raise TypeError(f"features[{key!r}] must be a boolean or string")
   919	            features[key] = raw_value
   920	        object.__setattr__(self, "features", features)
   921	        alternatives = [
   922	            _require_qualified_id(item, f"alternatives[{index}]")
   923	            for index, item in enumerate(_require_string_list(self.alternatives, "alternatives"))
   924	        ]
   925	        if len(alternatives) != len(set(alternatives)):
   926	            raise ValueError("alternatives must not contain duplicate backend ids")
   927	        object.__setattr__(self, "alternatives", alternatives)
   928	        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "backend"))
   929	        object.__setattr__(
   930	            self,
   931	            "backend_version",
   932	            _require_optional_string(self.backend_version, "backend_version"),
   933	        )
   934	
   935	    def to_dict(self) -> dict[str, Any]:
   936	        return _json_safe_mapping(
   937	            {
   938	                "schema_version": self.schema_version,
   939	                "supported": self.supported,
   940	                "reasons": self.reasons,
   941	                "features": self.features,
   942	                "alternatives": self.alternatives,
   943	                "backend": self.backend,
   944	                "backend_version": self.backend_version,
   945	            }
   946	        )
   947	
   948	    @classmethod
   949	    def from_dict(cls, payload: Mapping[str, Any]) -> SupportReport:
   950	        try:
   951	            data = _require_mapping(payload, "support report")
   952	            required = {
   953	                "schema_version",
   954	                "supported",
   955	                "reasons",
   956	                "features",
   957	                "alternatives",
   958	                "backend",
   959	                "backend_version",
   960	            }
   961	            _validate_object_keys(
   962	                data,
   963	                required=required,
   964	                allowed=required,
   965	                label="support report",
   966	            )
   967	            return cls(
   968	                schema_version=data["schema_version"],
   969	                supported=data["supported"],
   970	                reasons=data["reasons"],
   971	                features=data["features"],
   972	                alternatives=data["alternatives"],
   973	                backend=data["backend"],
   974	                backend_version=data["backend_version"],
   975	            )
   976	        except Exception as exc:
   977	            from .errors import RendererException
   978	
   979	            if isinstance(exc, RendererException):
   980	                raise
   981	            _protocol_failure(
   982	                f"malformed support report: {exc}",
   983	                details={"error_type": type(exc).__name__},
   984	            )
   985	
   986	
   987	@dataclass(frozen=True)
   988	class PlannerResolution:
   989	    """Resolved planner identity and trust evidence frozen into a plan."""
   990	
   310	            },
   311	            "audio_sample_rate": {
   312	              "type": "integer",
   313	              "minimum": 1
   314	            },
   315	            "audio_channel_layout": {
   316	              "type": "string",
   317	              "minLength": 1,
   318	              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   319	            }
   320	          }
   321	        }
   322	      ]
   323	    },
   324	    "supportReport": {
   325	      "type": "object",
   326	      "additionalProperties": false,
   327	      "required": [
   328	        "schema_version",
   329	        "supported",
   330	        "reasons",
   331	        "features",
   332	        "alternatives",
   333	        "backend",
   334	        "backend_version"
   335	      ],
   336	      "properties": {
   337	        "schema_version": {
   338	          "type": "integer",
   339	          "const": 1
   340	        },
   341	        "supported": {
   342	          "type": "boolean"
   343	        },
   344	        "reasons": {
   345	          "type": "array",
   346	          "items": {
   347	            "type": "string",
   348	            "minLength": 1,
   349	            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   350	          }
   351	        },
   352	        "features": {
   353	          "type": "object",
   354	          "additionalProperties": {
   355	            "type": [
   356	              "boolean",
   357	              "string"
   358	            ]
   359	          }
   360	        },
   361	        "alternatives": {
   362	          "type": "array",
   363	          "uniqueItems": true,
   364	          "items": {
   365	            "$ref": "#/definitions/qualifiedId"
   366	          }
   367	        },
   368	        "backend": {
   369	          "$ref": "#/definitions/qualifiedId"
   370	        },
   525	        },
   526	        "support_decision": {
   527	          "anyOf": [
   528	            {
   529	              "$ref": "#/definitions/supportReport"
   530	            },
   531	            {
   532	              "type": "null"
   533	            }
   534	          ]
   535	        }
   536	      }
   537	    },
   538	    "hashMap": {
   539	      "type": "object",
   540	      "additionalProperties": {
   541	        "$ref": "#/definitions/sha256"
   542	      },
   543	      "propertyNames": {
   544	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   545	      }
   546	    },
   547	    "renderSegment": {
   548	      "type": "object",
   549	      "additionalProperties": false,
   550	      "required": [
   551	        "window",
   552	        "renderer",
   553	        "input_hashes"
   554	      ],
   555	      "properties": {
   280	              "type": "integer",
   281	              "minimum": 1
   282	            },
   283	            "audio_channel_layout": {
   284	              "type": "string",
   285	              "minLength": 1,
   286	              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   287	            }
   288	          }
   289	        }
   290	      ]
   291	    },
   292	    "supportReport": {
   293	      "type": "object",
   294	      "additionalProperties": false,
   295	      "required": [
   296	        "schema_version",
   297	        "supported",
   298	        "reasons",
   299	        "features",
   300	        "alternatives",
   301	        "backend",
   302	        "backend_version"
   303	      ],
   304	      "properties": {
   305	        "schema_version": {
   306	          "type": "integer",
   307	          "const": 1
   308	        },
   309	        "supported": {
   310	          "type": "boolean"
   311	        },
   312	        "reasons": {
   313	          "type": "array",
   314	          "items": {
   315	            "type": "string",
   316	            "minLength": 1,
   317	            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   318	          }
   319	        },
   320	        "features": {
   321	          "type": "object",
   322	          "additionalProperties": {
   323	            "type": [
   324	              "boolean",
   325	              "string"
   326	            ]
   327	          }
   328	        },
   329	        "alternatives": {
   330	          "type": "array",
   331	          "uniqueItems": true,
   332	          "items": {
   333	            "$ref": "#/definitions/qualifiedId"
   334	          }
   335	        },
   336	        "backend": {
   337	          "$ref": "#/definitions/qualifiedId"
   338	        },
   339	        "backend_version": {
   340	          "type": [
   495	          "anyOf": [
   496	            {
   497	              "$ref": "#/definitions/supportReport"
   498	            },
   499	            {
   500	              "type": "null"
   501	            }
   502	          ]
   503	        }
   504	      }
   505	    },
   506	    "hashMap": {
   507	      "type": "object",
   508	      "additionalProperties": {
   509	        "$ref": "#/definitions/sha256"
   510	      },
   511	      "propertyNames": {
   512	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   513	      }
   514	    },
   515	    "renderSegment": {
   516	      "type": "object",
   517	      "additionalProperties": false,
   518	      "required": [
   519	        "window",
   520	        "renderer",

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=50 91f0fe3..086d692 -- astrid/core/rendering/schemas/v1/renderer-manifest.json astrid/core/rendering/schemas/v1/planner-manifest.json astrid/core/rendering/schemas/v1/finalizer-manifest.json' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalizer-manifest.json b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
index eac3e4f..0525220 100644
--- a/astrid/core/rendering/schemas/v1/finalizer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
@@ -1,221 +1,221 @@
 {
   "$schema": "http://json-schema.org/draft-07/schema#",
   "$id": "https://astrid.dev/schemas/rendering/v1/finalizer-manifest.json",
   "title": "Astrid render finalizer manifest v1",
   "type": "object",
   "required": [
     "schema_version",
     "id",
     "name",
     "version",
     "protocol_version",
     "command",
     "operations"
   ],
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "finalize",
           "support"
         ]
       },
       "contains": {
         "const": "finalize"
       },
       "uniqueItems": true
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "project_files",
           "network",
           "subprocess",
           "environment",
           "accelerator",
           "external_services"
         ]
       },
       "uniqueItems": true
     },
     "finalizerCapabilities": {
       "type": "object",
       "properties": {
         "containers": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           },
           "uniqueItems": true
         },
         "preserves_attachments": {
           "type": "boolean"
         },
         "audio_ownership": {
           "type": "array",
           "items": {
             "type": "string",
             "enum": [
               "rendered",
               "passthrough",
               "none"
             ]
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
-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "id": "rendering.ffmpeg-finalizer",
       "name": "FFmpeg Finalizer",
       "version": "1.0.0",
       "protocol_version": 1,
       "command": [
         "python3",
         "finalize.py"
       ],
       "operations": [
         "finalize"
       ],
       "description": "Validates, normalizes, and concatenates segment artifacts",
       "capabilities": {
         "containers": [
           "mp4",
           "mov"
         ],
         "preserves_attachments": true,
         "audio_ownership": [
           "rendered",
           "passthrough",
           "none"
         ],
         "features": {
           "stream_copy": true
         }
       },
       "required_permissions": [
         "project_files",
         "subprocess"
       ],
       "required_binaries": [
         "ffmpeg",
         "ffprobe"
       ],
       "timeout_seconds": 600,
       "metadata": {
         "owner": "rendering"
       }
     }
   ]
diff --git a/astrid/core/rendering/schemas/v1/planner-manifest.json b/astrid/core/rendering/schemas/v1/planner-manifest.json
index a6de1d1..1334afe 100644
--- a/astrid/core/rendering/schemas/v1/planner-manifest.json
+++ b/astrid/core/rendering/schemas/v1/planner-manifest.json
@@ -1,200 +1,200 @@
 {
   "$schema": "http://json-schema.org/draft-07/schema#",
   "$id": "https://astrid.dev/schemas/rendering/v1/planner-manifest.json",
   "title": "Astrid render planner manifest v1",
   "type": "object",
   "required": [
     "schema_version",
     "id",
     "name",
     "version",
     "protocol_version",
     "command",
     "operations"
   ],
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "plan",
           "support"
         ]
       },
       "contains": {
         "const": "plan"
       },
       "uniqueItems": true
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "project_files",
           "network",
           "subprocess",
           "environment",
           "accelerator",
           "external_services"
         ]
       },
       "uniqueItems": true
     },
     "plannerCapabilities": {
       "type": "object",
       "properties": {
         "policies": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "id": "rendering.legacy_hybrid",
       "name": "Legacy Hybrid Planner",
       "version": "1.0.0",
       "protocol_version": 1,
       "command": [
         "python3",
         "planner.py"
       ],
       "operations": [
         "plan"
       ],
       "description": "Preserves the legacy hybrid segmentation policy",
       "capabilities": {
         "policies": [
           "hybrid"
         ],
         "supports_fallback": true,
         "features": {
           "half_open_frames": true
         }
       },
       "required_permissions": [
         "project_files"
       ],
       "required_binaries": [],
       "timeout_seconds": 60,
       "metadata": {
         "owner": "rendering"
       }
     }
   ]
 }
diff --git a/astrid/core/rendering/schemas/v1/renderer-manifest.json b/astrid/core/rendering/schemas/v1/renderer-manifest.json
index 6f237fc..c079378 100644
--- a/astrid/core/rendering/schemas/v1/renderer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/renderer-manifest.json
@@ -1,229 +1,229 @@
 {
   "$schema": "http://json-schema.org/draft-07/schema#",
   "$id": "https://astrid.dev/schemas/rendering/v1/renderer-manifest.json",
   "title": "Astrid renderer manifest v1",
   "type": "object",
   "required": [
     "schema_version",
     "id",
     "name",
     "version",
     "protocol_version",
     "command",
     "operations"
   ],
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "render",
           "support"
         ]
       },
       "contains": {
         "const": "render"
       },
       "uniqueItems": true
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
           "project_files",
           "network",
           "subprocess",
           "environment",
           "accelerator",
           "external_services"
         ]
       },
       "uniqueItems": true
     },
     "rendererCapabilities": {
       "type": "object",
       "properties": {
         "clip_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           },
           "uniqueItems": true
         },
         "track_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           },
           "uniqueItems": true
         },
         "audio_ownership": {
           "type": "array",
           "items": {
             "type": "string",
             "enum": [
               "rendered",
               "passthrough",
               "none"
             ]
           },
           "uniqueItems": true
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "id": "acme.example",
       "name": "Acme Example Renderer",
       "version": "1.0.0",
       "protocol_version": 1,
       "command": [
         "python3",
         "render.py"
       ],
       "operations": [
         "render",
         "support"
       ],
       "description": "Deterministic example renderer",
       "capabilities": {
         "clip_types": [
           "media"
         ],
         "track_types": [
           "visual"
         ],
         "features": {
           "transitions": false
         },
         "supports_full_timeline": true,
         "supports_windows": true,
         "output_profiles": [
           "video/mp4"
         ],

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; cases=(\"ok\\nsub/../evil.mp4\",\"ok\\nsub//evil.mp4\",\"ok\\nsub\\\\evil.mp4\",\"ok\\nsub/evil.mp4\",\"ok\\n\\x00evil.mp4\"); [(print(n), [print(repr(s), Draft7Validator(json.load(open(\"astrid/core/rendering/schemas/v1/\"+n))[\"definitions\"][\"workspacePath\"]).is_valid(s)) for s in cases]) for n in (\"result.json\",\"finalize.json\")]'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 74ms:
result.json
'ok\nsub/../evil.mp4' True
'ok\nsub//evil.mp4' True
'ok\nsub\\evil.mp4' True
'ok\nsub/evil.mp4' True
'ok\n\x00evil.mp4' False
finalize.json
'ok\nsub/../evil.mp4' True
'ok\nsub//evil.mp4' True
'ok\nsub\\evil.mp4' True
'ok\nsub/evil.mp4' True
'ok\n\x00evil.mp4' False

exec
/bin/zsh -lc "python3 -c 'from astrid.core.rendering.contracts import _require_workspace_relative_path; cases=(\"ok\\nsub/../evil.mp4\",\"ok\\nsub//evil.mp4\",\"ok\\nsub\\\\evil.mp4\",\"ok\\nsub/evil.mp4\");
for s in cases:
 try: print(repr(s), \"DTO\", repr(_require_workspace_relative_path(s,\"path\")))
 except Exception as e: print(repr(s), \"DTO rejects\", type(e).__name__, str(e))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 92ms:
'ok\nsub/../evil.mp4' DTO rejects ValueError path must be a normalized contained workspace path
'ok\nsub//evil.mp4' DTO rejects ValueError path must be a normalized contained workspace path
'ok\nsub\\evil.mp4' DTO rejects ValueError path must be a normalized workspace path using forward slashes
'ok\nsub/evil.mp4' DTO 'ok\nsub/evil.mp4'

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; base={\"schema_version\":1,\"supported\":True,\"reasons\":[],\"features\":{\"   \":True},\"alternatives\":[],\"backend\":\"acme.example\",\"backend_version\":None};
for n in (\"support.json\",\"plan.json\",\"finalize.json\"):
 s=json.load(open(\"astrid/core/rendering/schemas/v1/\"+n)); sub=s if n==\"support.json\" else s[\"definitions\"][\"supportReport\"]; print(n, Draft7Validator(sub,resolver=None).is_valid(base), sub[\"properties\"][\"features\"].get(\"propertyNames\"))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 48ms:
support.json False {'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}
Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/referencing/_core.py", line 276, in pointer
    contents = contents[segment]  # type: ignore[reportUnknownArgumentType]
               ~~~~~~~~^^^^^^^^^
KeyError: 'definitions'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 462, in _validate_reference
    resolved = self._resolver.lookup(ref)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/referencing/_core.py", line 690, in lookup
    return retrieved.value.pointer(pointer=fragment, resolver=resolver)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/referencing/_core.py", line 279, in pointer
    raise error from lookup_error
referencing.exceptions.PointerToNowhere: '/definitions/qualifiedId' does not exist within {'type': 'object', 'additionalProperties': False, 'required': ['schema_version', 'supported', 'reasons', 'features', 'alternatives', 'backend', 'backend_version'], 'properties': {'schema_version': {'type': 'integer', 'const': 1}, 'supported': {'type': 'boolean'}, 'reasons': {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}, 'features': {'type': 'object', 'additionalProperties': {'type': ['boolean', 'string']}}, 'alternatives': {'type': 'array', 'uniqueItems': True, 'items': {'$ref': '#/definitions/qualifiedId'}}, 'backend': {'$ref': '#/definitions/qualifiedId'}, 'backend_version': {'type': ['string', 'null'], 'minLength': 1, 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}}

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "<string>", line 3, in <module>
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 499, in is_valid
    error = next(self.iter_errors(instance), None)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 383, in iter_errors
    for error in errors:
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/_keywords.py", line 296, in properties
    yield from validator.descend(
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 431, in descend
    for error in errors:
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/_keywords.py", line 275, in ref
    yield from validator._validate_reference(ref=ref, instance=instance)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 464, in _validate_reference
    raise exceptions._WrappedReferencingError(err) from err
jsonschema.exceptions._WrappedReferencingError: PointerToNowhere: '/definitions/qualifiedId' does not exist within {'type': 'object', 'additionalProperties': False, 'required': ['schema_version', 'supported', 'reasons', 'features', 'alternatives', 'backend', 'backend_version'], 'properties': {'schema_version': {'type': 'integer', 'const': 1}, 'supported': {'type': 'boolean'}, 'reasons': {'type': 'array', 'items': {'type': 'string', 'minLength': 1, 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}, 'features': {'type': 'object', 'additionalProperties': {'type': ['boolean', 'string']}}, 'alternatives': {'type': 'array', 'uniqueItems': True, 'items': {'$ref': '#/definitions/qualifiedId'}}, 'backend': {'$ref': '#/definitions/qualifiedId'}, 'backend_version': {'type': ['string', 'null'], 'minLength': 1, 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}}

exec
/bin/zsh -lc "rg --files tests/core/rendering/fixtures/v1 | sort && jq '.planner.support_decision, .segments[0].renderer.support_decision, .finalizer.support_decision' tests/core/rendering/fixtures/v1/plan.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/fixtures/v1/finalize.json
tests/core/rendering/fixtures/v1/plan.json
tests/core/rendering/fixtures/v1/request.json
tests/core/rendering/fixtures/v1/result.json
tests/core/rendering/fixtures/v1/support.json
null
{
  "schema_version": 1,
  "supported": true,
  "reasons": [],
  "features": {
    "visual_only": true
  },
  "alternatives": [],
  "backend": "acme.visual",
  "backend_version": null
}
{
  "schema_version": 1,
  "supported": true,
  "reasons": [],
  "features": {},
  "alternatives": [],
  "backend": "rendering.ffmpeg-finalizer",
  "backend_version": null
}

exec
/bin/zsh -lc "python3 -c 'import copy,json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import RenderPlan,FinalizeRequest; p=json.load(open(\"tests/core/rendering/fixtures/v1/plan.json\")); p[\"segments\"][0][\"renderer\"][\"support_decision\"][\"features\"]={\"   \":True}; ps=json.load(open(\"astrid/core/rendering/schemas/v1/plan.json\")); print(\"plan schema\",Draft7Validator(ps).is_valid(p));
try: RenderPlan.from_dict(p); print(\"plan dto True\")
except Exception as e: print(\"plan dto False\",type(e).__name__,str(e)); f=json.load(open(\"tests/core/rendering/fixtures/v1/finalize.json\")); f[\"plan\"][\"segments\"][0][\"renderer\"][\"support_decision\"][\"features\"]={\"   \":True}; fs=json.load(open(\"astrid/core/rendering/schemas/v1/finalize.json\")); print(\"finalize schema\",Draft7Validator(fs).is_valid(f));
try: FinalizeRequest.from_dict(f); print(\"finalize dto True\")
except Exception as e: print(\"finalize dto False\",type(e).__name__,str(e))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 145ms:
plan schema True
plan dto False RendererProtocolError malformed support report: feature key must not be empty
finalize schema True
finalize dto False RendererProtocolError malformed support report: feature key must not be empty

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import _require_workspace_relative_path; p=json.load(open(\"astrid/core/rendering/schemas/v1/result.json\"))[\"definitions\"][\"workspacePath\"];
for s in (\"foo/\\n\",\"foo\\n/\",\"foo/\\r\\n\",\"foo/\\t\"):
 try: d=repr(_require_workspace_relative_path(s,\"p\"))
 except Exception as e: d=\"reject \"+str(e)
 print(repr(s),\"schema\",Draft7Validator(p).is_valid(s),\"dto\",d)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 139ms:
'foo/\n' schema False dto 'foo/\n'
'foo\n/' schema False dto reject p must be a normalized contained workspace path
'foo/\r\n' schema True dto 'foo/\r\n'
'foo/\t' schema True dto 'foo/\t'

exec
/bin/zsh -lc "rg -n \"schema.*DTO|DTO.*schema|parity|workspacePath|NUL|multiline|propertyNames|feature key|hashMap|schema_valid|Draft7Validator|validate\\(\" tests/core/rendering/test_contracts.py | sed -n '1,280p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '860,1160p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   860	@pytest.mark.parametrize(
   861	    ("segments", "total_frames", "match"),
   862	    [
   863	        ([_segment(1, 48)], 48, "gap"),
   864	        ([_segment(0, 47)], 48, "trailing gap"),
   865	        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
   866	        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
   867	        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
   868	    ],
   869	)
   870	def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
   871	    segments: list[RenderSegment],
   872	    total_frames: int,
   873	    match: str,
   874	) -> None:
   875	    with pytest.raises(ValueError, match=match):
   876	        _plan(segments=segments, total_frames=total_frames)
   877	
   878	
   879	def test_plan_rejects_noncanonical_segment_or_window_fps() -> None:
   880	    with pytest.raises(ValueError, match="segment.*FPS"):
   881	        _plan(segments=[_segment(fps=(48, 2))])
   882	    with pytest.raises(ValueError, match="window FPS"):
   883	        _plan(window=_window(0, 48, fps=(48, 2)))
   884	
   885	
   886	def test_zero_frame_plan_semantics_and_no_finalization() -> None:
   887	    empty = _plan(segments=[], total_frames=0, profile=_profile(audio=False))
   888	    assert empty.segments == []
   889	    assert empty.reasons == {}
   890	    with pytest.raises(ValueError, match="zero-frame plan"):
   891	        _plan(segments=[_segment()], total_frames=0)
   892	    with pytest.raises(ValueError, match="positive-frame plan"):
   893	        _plan(segments=[], total_frames=48)
   894	    with pytest.raises(ValueError, match="must not be finalized"):
   895	        _finalize(plan=empty, artifacts=[])
   896	
   897	
   898	def test_qualified_id_grammar_allows_hyphens_and_underscores() -> None:
   899	    assert _finalizer().id == "rendering.ffmpeg-finalizer"
   900	    assert replace(_finalizer(), id="1render.2-finalizer",
   901	                   support_decision=_support("1render.2-finalizer")).id == "1render.2-finalizer"
   902	    assert replace(_finalizer(), id="rendering.legacy_hybrid",
   903	                   support_decision=_support("rendering.legacy_hybrid")).id == "rendering.legacy_hybrid"
   904	    assert replace(_finalizer(), id="acme.bad_id",
   905	                   support_decision=_support("acme.bad_id")).id == "acme.bad_id"
   906	    for invalid in (
   907	        "Rendering.Ffmpeg",
   908	        "rendering.-finalizer",
   909	        "unqualified",
   910	    ):
   911	        with pytest.raises(ValueError, match="qualified id"):
   912	            replace(_finalizer(), id=invalid, support_decision=_support(invalid))
   913	
   914	
   915	def test_contracts_are_frozen() -> None:
   916	    window = _window()
   917	    with pytest.raises(FrozenInstanceError):
   918	        window.start_frame = 1  # type: ignore[misc]
   919	
   920	
   921	def test_manifest_round_trip() -> None:
   922	    common = {
   923	        "schema_version": 1,
   924	        "name": "Example",
   925	        "version": "1.0.0",
   926	        "protocol_version": 1,
   927	        "command": ["python3", "backend.py"],
   928	        "description": "Example implementation",
   929	        "capabilities": {"features": {"media": True}},
   930	        "required_permissions": ["project_files"],
   931	        "required_binaries": [],
   932	        "timeout_seconds": 60,
   933	        "metadata": {"vendor": "Acme"},
   934	    }
   935	    cases = [
   936	        (RendererManifest, {**common, "id": "acme.renderer", "operations": ["render", "support"]}),
   937	        (PlannerManifest, {**common, "id": "acme.planner", "operations": ["plan"]}),
   938	        (FinalizerManifest, {**common, "id": "acme.finalizer", "operations": ["finalize"]}),
   939	    ]
   940	    for manifest_type, payload in cases:
   941	        assert manifest_type.from_dict(payload).to_dict() == payload
   942	
   943	
   944	def test_manifest_dto_rejects_schema_invalid_capabilities_and_scalar_command() -> None:
   945	    base = {
   946	        "schema_version": 1,
   947	        "id": "acme.renderer",
   948	        "name": "Example",
   949	        "version": "1.0.0",
   950	        "protocol_version": 1,
   951	        "operations": ["render"],
   952	    }
   953	    with pytest.raises(RendererProtocolError):
   954	        RendererManifest.from_dict(
   955	            {**base, "command": ["python3"], "capabilities": {"unknown": True}}
   956	        )
   957	    with pytest.raises(RendererProtocolError):
   958	        RendererManifest.from_dict({**base, "command": "python3"})

exec
/bin/zsh -lc "rg -n \"workspacePath|schema.*DTO|DTO.*schema|parity|NUL|multiline|propertyNames|hashMap|Draft7Validator|jsonschema\" tests/core/rendering tests | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_schema_roundtrip.py:9:import jsonschema
tests/core/rendering/test_schema_roundtrip.py:77:    jsonschema.Draft7Validator.check_schema(schema)
tests/core/rendering/test_schema_roundtrip.py:78:    validator = jsonschema.Draft7Validator(schema)
tests/core/rendering/test_schema_roundtrip.py:93:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:339:def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
tests/core/rendering/test_schema_roundtrip.py:340:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:351:            f"{schema_name} parity mismatch for {label}: "
tests/core/rendering/test_schema_roundtrip.py:372:    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
tests/test_component_manifest_parser_parity.py:6:import jsonschema
tests/test_component_manifest_parser_parity.py:52:        jsonschema.Draft7Validator(schema, registry=registry).iter_errors(payload),
tests/core/integrations/test_arnold_startup_smoke.py:7:parity.
tests/core/integrations/test_arnold_static_orchestrator_parity.py:8:from tests.core.integrations.arnold_parity import (
tests/core/integrations/test_arnold_static_orchestrator_parity.py:18:    load_artifact_for_parity,
tests/core/integrations/test_arnold_static_orchestrator_parity.py:19:    normalize_for_parity,
tests/core/integrations/test_arnold_static_orchestrator_parity.py:23:def test_parity_normalization_contract_only_allows_explicit_entropy_fields(
tests/core/integrations/test_arnold_static_orchestrator_parity.py:55:    normalized = normalize_for_parity(
tests/core/integrations/test_arnold_static_orchestrator_parity.py:78:def test_parity_harness_rejects_unapproved_artifact_ignore_paths() -> None:
tests/core/integrations/test_arnold_static_orchestrator_parity.py:90:        normalize_for_parity(
tests/core/integrations/test_arnold_static_orchestrator_parity.py:96:def test_load_artifact_for_parity_normalizes_common_fixture_shapes(
tests/core/integrations/test_arnold_static_orchestrator_parity.py:115:    text_path.write_text("hello parity\n", encoding="utf-8")
tests/core/integrations/test_arnold_static_orchestrator_parity.py:120:    assert load_artifact_for_parity(json_path) == {"ok": True, "count": 2}
tests/core/integrations/test_arnold_static_orchestrator_parity.py:121:    assert load_artifact_for_parity(jsonl_path) == [
tests/core/integrations/test_arnold_static_orchestrator_parity.py:125:    assert load_artifact_for_parity(text_path) == "hello parity\n"
tests/core/integrations/test_arnold_static_orchestrator_parity.py:126:    assert load_artifact_for_parity(binary_path) == b"\x00\x01raw"
tests/core/generation/test_param_map_migration_parity.py:1:"""Parametric parity test: every model×mode×backend combination in models.yaml
tests/core/generation/test_param_map_migration_parity.py:45:    """Yield (model_id, mode, backend_id, manifest_param_map, default_param_map, strict_parity).
tests/core/generation/test_param_map_migration_parity.py:50:    strict parity: some cloud APIs use genuinely different remote parameter
tests/core/generation/test_param_map_migration_parity.py:66:            strict_parity = not (
tests/core/generation/test_param_map_migration_parity.py:93:                        strict_parity,
tests/core/generation/test_param_map_migration_parity.py:112:    omitted — this test validates the *mapping* parity, not the per-value
tests/core/generation/test_param_map_migration_parity.py:134:    "model_id,mode,backend_id,manifest_map,default_map,strict_parity",
tests/core/generation/test_param_map_migration_parity.py:142:def test_param_map_parity(
tests/core/generation/test_param_map_migration_parity.py:148:    strict_parity: bool,
tests/core/generation/test_param_map_migration_parity.py:167:    #    parity when requested.
tests/core/generation/test_param_map_migration_parity.py:168:    if strict_parity:
tests/core/generation/test_param_map_migration_parity.py:183:    # 3. For strict-parity modes, build full canonical params from the union
tests/core/generation/test_param_map_migration_parity.py:186:    if not strict_parity:
tests/core/experiments/test_evaluation.py:103:        import jsonschema
tests/core/experiments/test_evaluation.py:105:        jsonschema.Draft7Validator(self._schema()).validate(payload)
tests/core/experiments/test_evaluation.py:111:        import jsonschema
tests/core/experiments/test_evaluation.py:115:        with pytest.raises(jsonschema.ValidationError):
tests/core/experiments/test_evaluation.py:119:        import jsonschema
tests/core/experiments/test_evaluation.py:123:        with pytest.raises(jsonschema.ValidationError):
tests/core/experiments/test_evaluation.py:127:        import jsonschema
tests/core/experiments/test_evaluation.py:132:        with pytest.raises(jsonschema.ValidationError):
tests/core/experiments/test_evaluation.py:136:        import jsonschema
tests/core/experiments/test_evaluation.py:140:        with pytest.raises(jsonschema.ValidationError):
tests/core/experiments/test_evaluation.py:144:        import jsonschema
tests/core/experiments/test_evaluation.py:148:        with pytest.raises(jsonschema.ValidationError):
tests/core/experiments/test_evaluation.py:433:        import jsonschema
tests/core/experiments/test_evaluation.py:445:        with pytest.raises(jsonschema.ValidationError):
tests/core/experiments/test_evaluation.py:446:            jsonschema.Draft7Validator(schema).validate(payload)
tests/core/integrations/arnold_parity.py:38:# T3 contract: parity normalization is placeholder replacement only for the
tests/core/integrations/arnold_parity.py:45:    """Raised when parity normalization is asked to ignore an unapproved field."""
tests/core/integrations/arnold_parity.py:48:def load_artifact_for_parity(path: str | Path) -> Any:
tests/core/integrations/arnold_parity.py:74:            "artifact ignore path(s) are not approved by the parity contract: "
tests/core/integrations/arnold_parity.py:80:def normalize_for_parity(
tests/core/integrations/arnold_parity.py:86:    """Normalize only the approved entropy fields before parity comparison."""
tests/core/integrations/arnold_parity.py:192:#  T5: Reusable parity test helpers for Arnold migration orchestrators
tests/core/integrations/arnold_parity.py:231:    """Create a project directory with state files suitable for parity testing.
tests/core/integrations/arnold_parity.py:451:def make_plan_for_parity(
tests/core/experiments/test_schema.py:54:        with pytest.raises(ExperimentValidationError, match="NUL"):
tests/core/test_scoped_config_parity.py:9:This replaces the S0 spike-based parity test
tests/core/test_scoped_config_parity.py:10:(``test_spike_scoped_config_parity.py``) deleted at T12.  The spike itself
tests/core/test_scoped_config_parity.py:217:def test_golden_parity(case_name: str) -> None:
tests/core/test_orchestrator_manifest_schema.py:6:import jsonschema
tests/core/test_orchestrator_manifest_schema.py:21:def _orchestrator_validator() -> jsonschema.Draft7Validator:
tests/core/test_orchestrator_manifest_schema.py:28:    return jsonschema.Draft7Validator(schema, registry=registry)
tests/core/rendering/test_schema_roundtrip.py:9:import jsonschema
tests/core/rendering/test_schema_roundtrip.py:77:    jsonschema.Draft7Validator.check_schema(schema)
tests/core/rendering/test_schema_roundtrip.py:78:    validator = jsonschema.Draft7Validator(schema)
tests/core/rendering/test_schema_roundtrip.py:93:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:339:def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
tests/core/rendering/test_schema_roundtrip.py:340:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:351:            f"{schema_name} parity mismatch for {label}: "
tests/core/rendering/test_schema_roundtrip.py:372:    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
tests/test_asset_cache.py:73:            stdout=subprocess.DEVNULL,
tests/test_asset_cache.py:74:            stderr=subprocess.DEVNULL,
tests/test_task_next_quiet_json.py:1:"""T3: ``cmd_next --quiet`` preamble suppression and JSON parity tests.
tests/test_task_next_quiet_json.py:161:    # This is a parity check — the reader-state JSON path was also migrated
tests/test_url_pipeline_smoke.py:58:            stdout=subprocess.DEVNULL,
tests/test_url_pipeline_smoke.py:59:            stderr=subprocess.DEVNULL,
tests/test_capability_schema.py:198:# Cross-domain parity: executor, orchestrator, and element all delegate their
tests/golden/README.md:58:Cross-backend parity tests (m6, m8) consume these same fixtures unchanged.
tests/agentic/test_adapter.py:1365:def test_parity_bypass_detected_by_both_legacy_and_adapter(
tests/agentic/test_adapter.py:1370:    adapter's canonical_bypass_patterns — proving parity at the M1
tests/agentic/test_adapter.py:1398:    patterns = adapter.canonical_bypass_patterns(Scenario(name="parity"))
tests/test_styledoc_schema.py:89:    def test_hand_rolled_references_check_is_independent_of_jsonschema(self) -> None:
tests/timeline/test_timeline_roundtrip_fixture.py:155:    # 3. Allowlist parity with the shared schema package
tests/timeline/test_timeline_roundtrip_fixture.py:157:    def test_allowlist_parity_with_shared_schema(self) -> None:
tests/packs/test_portfolio_parity.py:1:"""Sprint 9 Phase 8 — portfolio-wide parity tests.
tests/packs/test_portfolio_parity.py:97:# Resolver + validator parity
tests/packs/test_portfolio_parity.py:262:# Dispatch path parity — every pack's representative executor goes through
tests/packs/test_portfolio_parity.py:274:    Same parity proof the seinfeld pack already carries: we patch both
tests/packs/test_portfolio_parity.py:337:            # other four packs cover the external-dispatch parity claim;
tests/packs/test_portfolio_parity.py:457:    sid = _seed_session(astrid_home, projects_root, "parity")
tests/timeline/test_parity_shim_self_test.py:3:SC7 requirement: test_parity_shim_self_test.py must demonstrate that a
tests/timeline/test_parity_shim_self_test.py:13:from astrid.core.timeline.validators import _parity
tests/timeline/test_parity_shim_self_test.py:17:    _parity._get_element_registry.cache_clear()
tests/timeline/test_parity_shim_self_test.py:20:def test_parity_oracle_catches_divergence():
tests/timeline/test_parity_shim_self_test.py:21:    """A deliberate divergence raises AssertionError in parity mode."""
tests/timeline/test_parity_shim_self_test.py:29:                mp.setenv("ASTRID_TIMELINE_TYPECHECK", "parity")
tests/timeline/test_parity_shim_self_test.py:31:                    _parity.is_effect_clip("text-card", None)
tests/timeline/test_parity_shim_self_test.py:36:def test_parity_agrees_for_known_effect():
tests/timeline/test_parity_shim_self_test.py:41:            mp.setenv("ASTRID_TIMELINE_TYPECHECK", "parity")
tests/timeline/test_parity_shim_self_test.py:42:            result = _parity.is_effect_clip("text-card", None)
tests/timeline/test_parity_shim_self_test.py:55:                assert _parity.is_effect_clip("synthetic-only", None) is True
tests/timeline/test_parity_shim_self_test.py:56:                assert _parity.is_effect_clip("text-card", None) is False
tests/timeline/test_parity_shim_self_test.py:68:            assert _parity.is_effect_clip("text-card", None) is True
tests/timeline/test_parity_shim_self_test.py:70:            assert _parity.is_effect_clip("nonexistent-xyz-clip", None) is False
tests/timeline/test_parity_shim_self_test.py:75:def test_parity_unknown_clip_type_no_divergence():
tests/timeline/test_parity_shim_self_test.py:76:    """Unknown clip types produce False in both paths — no parity error."""
tests/timeline/test_parity_shim_self_test.py:80:            mp.setenv("ASTRID_TIMELINE_TYPECHECK", "parity")
tests/timeline/test_parity_shim_self_test.py:81:            result = _parity.is_effect_clip("nonexistent-xyz-clip", None)
tests/fixtures/sprint08/README.md:1:# Sprint-08 renderer-parity fixtures
tests/fixtures/sprint08/README.md:8:`tests/test_renderer_parity.py` skips itself when this directory has no
tests/packs/video_editing/test_arrange_revise.py:221:    def test_revise_flag_parity(self) -> None:
tests/packs/builtin/training_run/test_seinfeld_parity.py:1:"""Seinfeld example parity through generic training_run."""
tests/packs/test_pack_yaml_schema.py:10:import jsonschema
tests/packs/test_pack_yaml_schema.py:1727:        validator = jsonschema.Draft7Validator(
tests/packs/test_pack_yaml_schema.py:1758:    # -- parity: valid payloads (both paths accept) -----------------------
tests/packs/test_pack_yaml_schema.py:1760:    def test_parity_minimal_manifest_with_name_version_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1768:    def test_parity_runtime_defaults_name_version_when_absent(self) -> None:
tests/packs/test_pack_yaml_schema.py:1790:    def test_parity_timeline_kind_extensions_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1811:    def test_parity_full_manifest_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1821:    def test_parity_full_manifest_defaults_determined_by_status(self) -> None:
tests/packs/test_pack_yaml_schema.py:1833:    def test_parity_full_manifest_defaults_deprecated_status(self) -> None:
tests/packs/test_pack_yaml_schema.py:1844:    def test_parity_extensions_valid_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1858:    def test_parity_extensions_minimal_generation_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1868:    def test_parity_extensions_full_element_kinds_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1882:    def test_parity_taxonomy_explicit_values_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1893:    def test_parity_taxonomy_explicit_values_preserved(self) -> None:
tests/packs/test_pack_yaml_schema.py:1909:    def test_parity_taxonomy_non_standard_values_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1927:    def test_parity_taxonomy_whitespace_only_string_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:1939:    def test_parity_taxonomy_empty_string_uses_defaults(self) -> None:
tests/packs/test_pack_yaml_schema.py:1952:    def test_parity_permissions_valid_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:1985:    # -- parity: invalid payloads — both MUST reject -----------------------
tests/packs/test_pack_yaml_schema.py:1987:    def test_parity_missing_id_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:1994:    def test_parity_non_object_extensions_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2004:    def test_parity_permissions_invalid_shapes_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2044:    def test_parity_unknown_extension_root_key_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2054:    def test_parity_backend_missing_required_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2065:    def test_parity_backend_unknown_field_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2077:    def test_parity_element_kind_missing_id_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2088:    def test_parity_element_kind_unknown_field_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2099:    def test_parity_non_array_kinds_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2109:    def test_parity_non_array_backends_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2119:    def test_parity_non_object_generation_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2129:    def test_parity_non_object_elements_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2139:    def test_parity_wrong_type_for_status_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2149:    def test_parity_wrong_type_for_status_both_reject(self) -> None:
tests/packs/test_pack_yaml_schema.py:2156:    # -- parity: valid features/modes shorthand ----------------------------
tests/packs/test_pack_yaml_schema.py:2158:    def test_parity_features_string_shorthand_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:2168:    def test_parity_features_object_form_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:2179:    def test_parity_modes_string_shorthand_both_accept(self) -> None:
tests/packs/test_pack_yaml_schema.py:2189:    # -- parity: extensions round-trip defaults ----------------------------
tests/packs/test_pack_yaml_schema.py:2191:    def test_parity_extensions_round_trip_normalized_shape(self) -> None:
tests/packs/test_pack_yaml_schema.py:2232:    # -- parity: JSON serialization agreement --------------------------------
tests/packs/test_pack_yaml_schema.py:2234:    def test_parity_to_dict_is_json_serializable(self) -> None:
tests/packs/test_pack_yaml_schema.py:2245:    # -- parity: no import during static validation --------------------------
tests/packs/test_pack_yaml_schema.py:2247:    def test_parity_no_import_during_static_validation(self) -> None:
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:1:"""T9: Thumbnail maker resume-injection parity tests.
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:6:task and Arnold paths, and requires normalized ledger parity plus
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:7:generated JSON artifact parity for every thumbnail maker scenario.
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:27:from tests.core.integrations.arnold_parity import (
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:29:    make_plan_for_parity,
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:32:    normalize_for_parity,
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:178:    make_plan_for_parity(plan, plan_path.parent, filename="plan.json")
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:349:#  Command parity: task vs Arnold paths
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:494:        from tests.core.integrations.arnold_parity import read_review_state_file
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:576:#  Stub step failure parity
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:584:    generate-thumbnails) raise ``NotImplementedError``.  The parity
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:754:#  Normalized ledger parity
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:772:        normalized = normalize_for_parity(
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:800:        norm1 = normalize_for_parity(events1, path_roots=[str(proot1), str(run_root1)])
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:801:        norm2 = normalize_for_parity(events2, path_roots=[str(proot2), str(run_root2)])
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:842:        norm1 = normalize_for_parity(events1, path_roots=[str(proot1), str(run_root1)])
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:843:        norm2 = normalize_for_parity(events2, path_roots=[str(proot2), str(run_root2)])
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:889:        normalized = normalize_for_parity(
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:982:#  Topology parity: plan_template vs workflow
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:987:    """Topology parity between plan_template.build_plan_v2() and workflow stage/edge specs.
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:1251:    """Timeline assembly assertions for thumbnail maker parity."""
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:1272:        from tests.core.integrations.arnold_parity import assert_managed_timeline_exists
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:1298:#  JSON artifact parity
tests/packs/thumbnail_maker/test_thumbnail_maker_parity.py:1303:    """Generated JSON artifact parity for every thumbnail maker scenario.
tests/packs/test_renderer_parity.py:1:"""Optional renderer parity gate against sprint-08 timeline fixtures.
tests/packs/test_renderer_parity.py:32:    assert EXPORT_HELPER.is_file(), f"renderer parity export helper missing: {EXPORT_HELPER}"
tests/packs/test_renderer_parity.py:33:    assert _node_available(), "node not available; renderer parity helper requires Node ESM"
tests/packs/test_renderer_parity.py:54:@pytest.mark.renderer_parity
tests/packs/test_renderer_parity.py:57:def test_renderer_parity_against_sprint08_fixtures() -> None:
tests/packs/test_renderer_parity.py:59:        pytest.skip("renderer parity integration is opt-in; set ASTRID_RENDERER_PARITY=1")
tests/packs/test_renderer_parity.py:78:        assert path.is_file(), f"renderer parity fixture file missing for {fixture['name']}: {path}"
tests/packs/test_renderer_parity.py:83:            f"renderer parity hash mismatch for {fixture['name']}: "
tests/packs/builtin/test_training_run_seinfeld_parity.py:1:"""Seinfeld-by-config parity coverage for training.training_run."""
tests/packs/builtin/test_training_run_seinfeld_parity.py:226:    register_rc = training_run_main(["resume", "--out", str(run_dir), "--pick", "final", "--notes", "parity pick", "--json"])
tests/packs/builtin/test_training_run_seinfeld_parity.py:234:    assert registered["registration"]["notes"] == "parity pick"
tests/packs/test_pack_rendering_extensions.py:6:import jsonschema
tests/packs/test_pack_rendering_extensions.py:41:    validator = jsonschema.Draft7Validator(pack_schema, registry=registry)
tests/packs/builtin/generate_image/test_codex_backend.py:77:    assert seen["kwargs"]["stdin"] is subprocess.DEVNULL  # type: ignore[index]
tests/packs/test_packs_cli.py:925:    def _assert_ls_list_parity(self, noun: str, expect_option: str = "") -> None:
tests/packs/test_packs_cli.py:940:        self._assert_ls_list_parity("executors", "--json")
tests/packs/test_packs_cli.py:943:        self._assert_ls_list_parity("orchestrators")
tests/packs/test_packs_cli.py:946:        self._assert_ls_list_parity("elements")
tests/packs/test_packs_cli.py:949:        self._assert_ls_list_parity("models")
tests/packs/test_packs_cli.py:952:        self._assert_ls_list_parity("packs")
tests/packs/test_packs_cli.py:955:        self._assert_ls_list_parity("sessions")
tests/packs/test_packs_cli.py:958:        self._assert_ls_list_parity("timelines")
tests/test_onboarding_parity.py:1:"""Onboarding documentation parity tests.
tests/test_onboarding_parity.py:364:    with tempfile.TemporaryDirectory(prefix="astrid-parity-") as tmp_out:
tests/test_onboarding_parity.py:371:                "brief": "parity test brief",
tests/test_onboarding_parity.py:397:    with tempfile.TemporaryDirectory(prefix="astrid-parity-") as tmp_out:
tests/test_onboarding_parity.py:661:# DTO serializability (capability.schema, capability.definition)
tests/timeline/test_migration.py:799:        assert result["parity_ok"] is None
tests/timeline/test_migration.py:853:    def test_parity_failure_after_source_change(self, tmp_path: Path) -> None:
tests/timeline/test_migration.py:872:        assert result2["parity_ok"] is None
tests/timeline/test_migration.py:876:    def test_parity_failure_leaves_source_blobs_intact(self, tmp_path: Path) -> None:
tests/timeline/test_migration.py:877:        """After parity failure, assembly.json must retain its (modified) content."""
tests/timeline/test_migration.py:896:        assert result["parity_ok"] is None
tests/timeline/test_migration.py:902:    def test_parity_failure_does_not_add_events(self, tmp_path: Path) -> None:
tests/timeline/test_migration.py:922:        assert result["parity_ok"] is None
tests/timeline/test_migration.py:1110:        assert result["parity_ok"] is True
tests/timeline/test_migration.py:1156:        assert result2["parity_ok"] is True
tests/timeline/test_migration.py:1199:    def test_parity_failure_config_as_snapshot_sd2(
tests/timeline/test_migration.py:1214:        assert r1["parity_ok"] is True
tests/timeline/test_migration.py:1216:        # Re-import with a different config — parity must fail
tests/timeline/test_migration.py:1229:        assert r2["parity_ok"] is False
tests/timeline/test_migration.py:1231:        assert "TimelineConfig parity does NOT hold" in r2["detail"]
tests/timeline/test_migration.py:1269:    def test_config_event_is_not_mutated_on_parity_failure(
tests/timeline/test_migration.py:1272:        """The original event snapshot is preserved when parity fails."""
tests/packs/test_public_id_resolution.py:1:"""Sprint 9 Phase 6 Step 12 — public id resolution parity.
tests/packs/test_public_id_resolution.py:8:parity guard for that decision.
tests/timeline/test_timeline_type_resolution_parity.py:45:def _clear_parity_cache() -> None:
tests/timeline/test_timeline_type_resolution_parity.py:47:    from astrid.core.timeline.validators import _parity
tests/timeline/test_timeline_type_resolution_parity.py:49:    _parity._get_element_registry.cache_clear()
tests/timeline/test_timeline_type_resolution_parity.py:69:        _clear_parity_cache()
tests/timeline/test_timeline_type_resolution_parity.py:86:def test_corpus_parity_identical_verdict(fixture_path: Path) -> None:
tests/timeline/test_timeline_type_resolution_parity.py:90:    identical first-error-message-substring (per the plan's parity
tests/packs/event_talks/test_event_talks_parity.py:1:"""T7: Event talks resume-injection parity tests.
tests/packs/event_talks/test_event_talks_parity.py:4:ledger parity under both task-gate and Arnold lifecycle paths.
tests/packs/event_talks/test_event_talks_parity.py:22:from tests.core.integrations.arnold_parity import (
tests/packs/event_talks/test_event_talks_parity.py:24:    make_plan_for_parity,
tests/packs/event_talks/test_event_talks_parity.py:27:    normalize_for_parity,
tests/packs/event_talks/test_event_talks_parity.py:166:    make_plan_for_parity(plan, plan_path.parent, filename="plan.json")
tests/packs/event_talks/test_event_talks_parity.py:313:#  Command parity: task vs Arnold paths
tests/packs/event_talks/test_event_talks_parity.py:438:        from tests.core.integrations.arnold_parity import read_review_state_file
tests/packs/event_talks/test_event_talks_parity.py:520:#  Normalized ledger parity
tests/packs/event_talks/test_event_talks_parity.py:538:        normalized = normalize_for_parity(
tests/packs/event_talks/test_event_talks_parity.py:566:        norm1 = normalize_for_parity(events1, path_roots=[str(proot1), str(run_root1)])
tests/packs/event_talks/test_event_talks_parity.py:567:        norm2 = normalize_for_parity(events2, path_roots=[str(proot2), str(run_root2)])
tests/packs/event_talks/test_event_talks_parity.py:608:        norm1 = normalize_for_parity(events1, path_roots=[str(proot1), str(run_root1)])
tests/packs/event_talks/test_event_talks_parity.py:609:        norm2 = normalize_for_parity(events2, path_roots=[str(proot2), str(run_root2)])
tests/packs/event_talks/test_event_talks_parity.py:704:    """Topology parity between plan_template.build_plan_v2() and workflow stage/edge specs.
tests/packs/event_talks/test_event_talks_parity.py:939:    """Timeline assembly assertions for event talks parity."""
tests/packs/event_talks/test_event_talks_parity.py:960:        from tests.core.integrations.arnold_parity import assert_managed_timeline_exists
tests/audit/test_audit.py:68:    pytest.importorskip("jsonschema")
tests/audit/test_audit.py:80:    pytest.importorskip("jsonschema")
tests/timeline/test_projection.py:926:# ── checkpoint-assisted replay parity ─────────────────────────────────────────
tests/timeline/test_timeline_cli.py:2237:        return {"ok": True, "imported": False, "event_id": None, "parity_ok": None, "detail": "skipped"}
tests/timeline/test_timeline_cli.py:2282:    """Confirm audit reports projection parity after import."""
tests/timeline/test_timeline_cli.py:2297:        assert result.get("parity_ok") is None
tests/timeline/test_timeline_cli.py:2304:    def test_supabase_mocked_audit_parity(
tests/packs/builtin/dataset_build/test_contract_foundation.py:11:import jsonschema
tests/packs/builtin/dataset_build/test_contract_foundation.py:45:def _validator(schema_root: Path, schema_name: str) -> jsonschema.Draft7Validator:
tests/packs/builtin/dataset_build/test_contract_foundation.py:47:    return jsonschema.Draft7Validator(schema, registry=_schema_registry(schema_root))
tests/test_lifecycle_peek.py:157:def test_peek_parity_with_gate_command_on_parallel_events(tmp_projects_root: Path) -> None:
tests/test_lifecycle_peek.py:158:    """FLAG-P5-003 load-bearing parity test.
tests/packs/builtin/dataset_build/test_shared_utilities.py:8:import jsonschema
tests/packs/builtin/dataset_build/test_shared_utilities.py:53:    jsonschema.Draft7Validator(schema, registry=_schema_registry()).validate(payload)
tests/packs/builtin/dataset_build/test_state_injection_parity.py:31:from tests.core.integrations.arnold_parity import (
tests/packs/builtin/dataset_build/test_state_injection_parity.py:32:    make_plan_for_parity,
tests/packs/builtin/dataset_build/test_state_injection_parity.py:33:    normalize_for_parity,
tests/packs/builtin/dataset_build/test_state_injection_parity.py:196:    plan_path = make_plan_for_parity(plan, tmp_path / "plan-source", filename="plan.json")
tests/packs/builtin/dataset_build/test_state_injection_parity.py:262:def test_dataset_build_review_state_injection_parity_for_task_and_arnold(
tests/packs/builtin/dataset_build/test_state_injection_parity.py:296:    normalized_task_summary = normalize_for_parity(
tests/packs/builtin/dataset_build/test_state_injection_parity.py:300:    normalized_arnold_summary = normalize_for_parity(
tests/packs/builtin/dataset_build/test_state_injection_parity.py:311:    normalized_task_state = normalize_for_parity(
tests/packs/builtin/dataset_build/test_state_injection_parity.py:315:    normalized_arnold_state = normalize_for_parity(
tests/packs/builtin/test_training_run_manifest_input.py:9:import jsonschema
tests/packs/builtin/test_training_run_manifest_input.py:135:    with pytest.raises(jsonschema.ValidationError):
tests/packs/builtin/dataset_build/test_filter_stages.py:8:import jsonschema
tests/packs/builtin/dataset_build/test_filter_stages.py:52:    jsonschema.Draft7Validator(schema).validate(stats)
tests/packs/builtin/dataset_build/test_filter_stages.py:364:    with pytest.raises(jsonschema.ValidationError):

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '1,430p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   283	        ("zero-frame plan", zero_plan),
   284	    ]
   285	    return _with_version_adversaries(base, cases)
   286	
   287	
   288	def _manifest_cases(
   289	    schema_name: str,
   290	    required_operation: str,
   291	) -> list[tuple[str, dict[str, Any]]]:
   292	    base = deepcopy(_load_schema(schema_name)["examples"][0])
   293	    return [
   294	        ("valid canonical", base),
   295	        ("missing id", _delete(base, ("id",))),
   296	        ("valid underscore id", _set(base, ("id",), "acme.bad_id")),
   297	        ("unknown field", {**base, "priority": 1}),
   298	        ("boolean version", _set(base, ("schema_version",), True)),
   299	        ("unknown version", _set(base, ("schema_version",), 2)),
   300	        ("malformed protocol version", _set(base, ("protocol_version",), "1")),
   301	        ("empty command", _set(base, ("command",), [])),
   302	        ("missing required operation", _set(base, ("operations",), ["support"])),
   303	        (
   304	            "duplicate operation",
   305	            _set(base, ("operations",), [required_operation, required_operation]),
   306	        ),
   307	        ("unknown permission", _set(base, ("required_permissions",), ["root"])),
   308	        ("unknown capability", _set(base, ("capabilities",), {"unknown": True})),
   309	    ]
   310	
   311	
   312	def _with_version_adversaries(
   313	    base: dict[str, Any],
   314	    cases: list[tuple[str, dict[str, Any]]],
   315	) -> list[tuple[str, dict[str, Any]]]:
   316	    return cases + [
   317	        ("missing version", _delete(base, ("schema_version",))),
   318	        ("boolean version", _set(base, ("schema_version",), True)),
   319	        ("malformed version", _set(base, ("schema_version",), "1")),
   320	        ("unknown version", _set(base, ("schema_version",), 2)),
   321	    ]
   322	
   323	
   324	CASE_BUILDERS: dict[str, Callable[[], list[tuple[str, dict[str, Any]]]]] = {
   325	    "request.json": _request_cases,
   326	    "support.json": _support_cases,
   327	    "plan.json": _plan_cases,
   328	    "result.json": _result_cases,
   329	    "finalize.json": _finalize_cases,
   330	    "renderer-manifest.json": lambda: _manifest_cases("renderer-manifest.json", "render"),
   331	    "planner-manifest.json": lambda: _manifest_cases("planner-manifest.json", "plan"),
   332	    "finalizer-manifest.json": lambda: _manifest_cases(
   333	        "finalizer-manifest.json", "finalize"
   334	    ),
   335	}
   336	
   337	
   338	@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
   339	def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
   340	    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
   341	    parser = PARSERS[schema_name]
   342	    for label, payload in CASE_BUILDERS[schema_name]():
   343	        schema_accepts = validator.is_valid(payload)
   344	        dto_accepts = _accepted(parser, payload)
   345	        expected = label.startswith("valid ")
   346	        assert schema_accepts is expected, (
   347	            f"{schema_name} unexpected schema result for {label}: "
   348	            f"expected={expected}, actual={schema_accepts}"
   349	        )
   350	        assert dto_accepts == schema_accepts, (
   351	            f"{schema_name} parity mismatch for {label}: "
   352	            f"schema={schema_accepts}, dto={dto_accepts}"
   353	        )
   354	
   355	
   356	@pytest.mark.parametrize(
   357	    "path",
   358	    [
   359	        "../escape.mp4",
   360	        "outputs/./escape.mp4",
   361	        "outputs//escape.mp4",
   362	        "outputs/",
   363	        "/tmp/escape.mp4",
   364	        "C:escape.mp4",
   365	        r"C:\\temp\\escape.mp4",
   366	        r"dir\\escape.mp4",
   367	    ],
   368	)
   369	def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
   370	    result = _load_fixture("result.json")
   371	    result["video"]["path"] = path
   372	    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
   373	
   374	
   375	def test_python_result_type_annotation_remains_the_success_dto() -> None:
   376	    payload = _load_fixture("result.json")
   377	    parsed = parse_wire_result(payload)
   378	    assert isinstance(parsed, RenderResult)

exec
/bin/zsh -lc "diff -u <(jq -S '{type,additionalProperties,required,properties}' astrid/core/rendering/schemas/v1/support.json) <(jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/plan.json) || true
diff -u <(jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/plan.json) <(jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/finalize.json) || true
diff -u <(jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/result.json) <(jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/finalize.json) || true" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
diff: /dev/fd/11: Operation not permitted
diff: /dev/fd/11: Operation not permitted
diff: /dev/fd/11: Operation not permitted

exec
/bin/zsh -lc "python3 -c 'import json,pprint; L=lambda n:json.load(open(\"astrid/core/rendering/schemas/v1/\"+n)); s=L(\"support.json\"); a={k:s[k] for k in (\"type\",\"additionalProperties\",\"required\",\"properties\")}; p=L(\"plan.json\")[\"definitions\"][\"supportReport\"]; f=L(\"finalize.json\")[\"definitions\"][\"supportReport\"]; print(\"support==plan\",a==p,\"plan==finalize\",p==f); print(\"support feature\",a[\"properties\"][\"features\"]); print(\"plan feature\",p[\"properties\"][\"features\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 5ms:
support==plan False plan==finalize True
support feature {'type': 'object', 'additionalProperties': {'type': ['boolean', 'string']}, 'propertyNames': {'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}
plan feature {'type': 'object', 'additionalProperties': {'type': ['boolean', 'string']}}

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '800,865p' && git diff --no-ext-diff --unified=10 91f0fe3..086d692 -- tests/core/rendering/test_contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   800	
   801	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   802	    """Artifact lineage must carry a real sha256; profile-only entries and
   803	    null hashes are rejected rather than stringified."""
   804	    base = dict(
   805	        engine="hybrid",
   806	        output="/workspace/out/video.mp4",
   807	        timeline="/workspace/timeline.json",
   808	        assets_registry=None,
   809	        plan=_plan(),
   810	        audio_ownership="rendered",
   811	        normalization=[],
   812	        attachments={},
   813	        backend_fragments={},
   814	        v1_compatibility=_compatibility(),
   815	    )
   816	    with pytest.raises(TypeError, match="hashed lineage"):
   817	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
   818	    with pytest.raises(ValueError, match="sha256"):
   819	        assemble_provenance_v2(
   820	            **base,
   821	            artifact_profiles={
   822	                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
   823	            },
   824	        )
   825	    with pytest.raises(ValueError, match="sha256"):
   826	        assemble_provenance_v2(
   827	            **base,
   828	            artifact_profiles={
   829	                "out/v.mp4": {
   830	                    "profile": _profile(),
   831	                    "sha256": "not-a-hash",
   832	                    "attachments": {},
   833	                }
   834	            },
   835	        )
   836	    with pytest.raises(ValueError, match="unknown fields"):
   837	        assemble_provenance_v2(
   838	            **base,
   839	            artifact_profiles={
   840	                "out/v.mp4": {
   841	                    "profile": _profile(),
   842	                    "sha256": SHA_B,
   843	                    "attachments": {},
   844	                    "spoof": 1,
   845	                }
   846	            },
   847	        )
   848	
   849	
   850	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
   851	    plan = _plan(
   852	        segments=[_segment(12, 24), _segment(24, 36)],
   853	        total_frames=48,
   854	        window=_window(12, 36),
   855	    )
   856	    assert plan.total_frames == 48
   857	    assert plan.window == _window(12, 36)
   858	
   859	
   860	@pytest.mark.parametrize(
   861	    ("segments", "total_frames", "match"),
   862	    [
   863	        ([_segment(1, 48)], 48, "gap"),
   864	        ([_segment(0, 47)], 48, "trailing gap"),
   865	        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 36769e5..69b4791 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -682,21 +682,27 @@ def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
     assert reparsed.finalizer.trust_eligibility == finalizer.trust_eligibility
     assert reparsed.finalizer.support_decision is not None
 
     # Provenance sidecar carries the same evidence
     payload = assemble_provenance_v2(
         engine="hybrid",
         output="/workspace/out/video.mp4",
         timeline="/workspace/timeline.json",
         assets_registry=None,
         plan=plan,
-        artifact_profiles={},
+        artifact_profiles={
+            "outputs/visual.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_B,
+                "attachments": {},
+            }
+        },
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
@@ -805,26 +811,46 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     with pytest.raises(TypeError, match="hashed lineage"):
         assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
+            artifact_profiles={
+                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
+            },
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": "not-a-hash",
+                    "attachments": {},
+                }
+            },
+        )
+    with pytest.raises(ValueError, match="unknown fields"):
+        assemble_provenance_v2(
+            **base,
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {},
+                    "spoof": 1,
+                }
+            },
         )
 
 
 def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
     plan = _plan(
         segments=[_segment(12, 24), _segment(24, 36)],
         total_frames=48,
         window=_window(12, 36),
     )
     assert plan.total_frames == 48

exec
/bin/zsh -lc "rg -n \"positive render plan|must equal VideoArtifact.path|artifact lineage.*attachments|missing required fields|attachment.*unknown|Attachment\\(\" tests/core/rendering | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_contracts.py:232:    project = Attachment(
tests/core/rendering/test_contracts.py:437:    return Attachment(name=name, path=f"outputs/{name}", kind="project", sha256=sha256)
tests/core/rendering/test_contracts.py:728:            with pytest.raises(ValueError, match="missing required fields"):
tests/core/rendering/test_contracts.py:742:            "alpha": Attachment(

exec
/bin/zsh -lc "python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from astrid.core.rendering.contracts import Attachment, VideoArtifact; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B,SHA_C; base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=_plan(),audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility()); a=VideoArtifact(path=\"outputs/visual.mp4\",profile=_profile(),sha256=SHA_B,duration_frames=48,audio=\"rendered\",attachments={}); print(\"sequence video ->\",assemble_provenance_v2(**base,artifact_profiles=[a])[\"artifact_profiles\"]); x={\"out/v.mp4\":{\"profile\":_profile(),\"sha256\":SHA_B,\"attachments\":{\"spoofed\":Attachment(name=\"real\",path=\"outputs/real.dat\",kind=\"project\",sha256=SHA_C)}}}; print(\"attachment mismatch ->\",assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 183ms:
sequence video -> [{'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}]
attachment mismatch -> {'out/v.mp4': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {'spoofed': {'path': 'outputs/real.dat', 'kind': 'project', 'sha256': 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc'}}}}

exec
/bin/zsh -lc 'git diff --no-ext-diff 91f0fe3..086d692 | shasum -a 256 && wc -l /tmp/batch1-r6.diff && git diff --no-ext-diff --numstat 91f0fe3..086d692' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3ba6672176ce8513a9971f61be4edd999643db5ad5ad09682480de34a679a14c  -
   17210 /tmp/batch1-r6.diff
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
16046	0	.oracle/checkins/batch-1-r5.md
80	32	astrid/core/rendering/provenance.py
23	20	astrid/core/rendering/schemas/v1/finalize.json
10	10	astrid/core/rendering/schemas/v1/finalizer-manifest.json
19	16	astrid/core/rendering/schemas/v1/plan.json
10	10	astrid/core/rendering/schemas/v1/planner-manifest.json
12	12	astrid/core/rendering/schemas/v1/renderer-manifest.json
14	14	astrid/core/rendering/schemas/v1/request.json
16	16	astrid/core/rendering/schemas/v1/result.json
5	2	astrid/core/rendering/schemas/v1/support.json
7	6	docs/contracts/render-backend-v1.md
29	3	tests/core/rendering/test_contracts.py

codex
Two concrete parity gaps have emerged despite the green suite: embedded support-report schemas were not updated with the standalone support schema, and the newline-enabled workspace-path regex leaves later path segments unchecked. I’m validating whether lineage still has any equivalent bypass before fixing the verdict.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 553ms:
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
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '250,310p;350,410p' && nl -ba astrid/core/rendering/contracts.py | sed -n '1220,1420p;1450,1600p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   296	`metadata`. Successful result fields are core-owned. A top-level result
   297	`attachments` member is invalid rather than a compatibility alias.
   298	
   299	Backend fragments are JSON objects beneath their qualified namespace:
   300	
   301	```json
   302	{
   303	  "backend_fragments": {
   304	    "acme.example": {
   305	      "renderer": "example",
   306	      "quality": "preview"
   307	    }
   308	  }
   309	}
   310	```
   350	keys are REQUIRED on every capability resolution record:
   351	
   352	- `planner` is `{id, source_pack, manifest_digest, trust_eligibility,
   353	  alias_chain, override, support_decision}`;
   354	- every segment is `{window, renderer, input_hashes}`, where `renderer` is
   355	  `{id, source_pack, manifest_digest, alias_chain, override,
   356	  support_decision, trust_eligibility}`;
   357	- `finalizer` is `{id, source_pack, manifest_digest, alias_chain,
   358	  override, trust_eligibility, support_decision}`.
   359	
   360	`alias_chain` is an array of strings and defaults to `[]`; `override` is
   361	`{from, to}` with `to` equal to the resolution id (an override records what
   362	selected this implementation — the DTO rejects `{from, to}` shapes whose `to`
   363	differs, and rejects any other shape), or `null`; `trust_eligibility` records
   364	the derived source/install trust decision; `support_decision` is a versioned
   365	`SupportReport` or `null` (when no request-sensitive probe ran, e.g. for a
   366	finalizer). Every non-null `support_decision.backend` MUST equal the
   367	capability ID — the DTO rejects a mismatch for planner, renderer, and
   368	finalizer alike. Manifest, request, and input-hash values are lowercase
   369	SHA-256 digests. There is no parallel `segment.backend`, `segment.support`,
   370	or string-only finalizer field that could disagree with these records.
   371	
   372	`total_frames` is the complete timeline frame count. A zero-frame plan has
   373	`window: null`, no segments, and an empty reasons map; it is not finalized and
   374	does not invent a frame. A positive-frame plan has at least one segment. Its
   375	target is the explicit window when present, otherwise `[0,total_frames)`; an
   376	explicit window cannot exceed `total_frames`. The target window and every
   377	segment use the canonical profile's exact rational FPS (equivalent but
   378	noncanonical ratios are rejected). The first segment starts at the target,
   379	every subsequent start equals the preceding end, and the last end equals the
   380	target end. This tiles the target without leading, internal, or trailing gaps,
   381	overlap, or reordering. JSON Schema expresses the zero/nonzero structural
   382	branches; the DTO enforces adjacency, bounds, and exact FPS equality.
   383	
   384	Reasons are keyed by zero-based decimal segment index (`"0"`, `"1"`, ...),
   385	with exactly one entry per segment. A renderer owns all pixels for its assigned
   386	temporal window; V1 does not combine overlapping renderer layers.
   387	
   388	## Finalization
   389	
   390	`FinalizeRequest` contains `schema_version: 1`, the complete `plan`, an ordered
   391	`artifacts` array, neutral `output_name`, selected finalizer configuration,
   392	and metadata. Artifacts correspond one-for-one with plan segments. A finalizer
   393	returns the same `RenderResult` shape as a renderer. Empty plans are not sent
   394	to finalizers. Before invocation, the host rejects any attachment name reused
   395	by two segment artifacts. After invocation, it verifies that the final video's
   396	attachment map contains the unchanged union of all input attachments;
   397	additional globally unique finalizer-created attachments are permitted.
   398	
   399	Final assembly is explicit even when it is a one-segment pass-through.
   400	Finalizers probe every input and compare it with the plan profile. Compatible
   401	segments may stream-copy. Otherwise the finalizer normalizes dimensions,
   402	rational FPS/time base, container, video codec/profile/level, pixel format,
   403	audio codec/sample rate/channel layout, and audio presence. Every performed
   404	normalization is appended to `normalization`. The finalizer preserves
   405	attachments it does not understand. The first built-in finalizer uses FFmpeg;
   406	its one canonical qualified ID is `rendering.ffmpeg-finalizer`. FFmpeg is not
   407	part of the generic contract.
   408	
   409	## Structured errors
   410	
  1220	            self,
  1221	            "alias_chain",
  1222	            [
  1223	                _require_string(item, f"finalizer alias_chain[{index}]")
  1224	                for index, item in enumerate(_require_string_list(self.alias_chain, "finalizer alias_chain"))
  1225	            ],
  1226	        )
  1227	        if self.override is not None:
  1228	            object.__setattr__(
  1229	                self,
  1230	                "override",
  1231	                _require_override(
  1232	                    self.override,
  1233	                    capability_id=self.id,
  1234	                    label="finalizer override",
  1235	                ),
  1236	            )
  1237	        if self.support_decision is not None:
  1238	            support = (
  1239	                self.support_decision
  1240	                if isinstance(self.support_decision, SupportReport)
  1241	                else SupportReport.from_dict(
  1242	                    _require_mapping(
  1243	                        self.support_decision, "finalizer support_decision"
  1244	                    )
  1245	                )
  1246	            )
  1247	            if support.backend != self.id:
  1248	                raise ValueError("finalizer support_decision.backend must match finalizer id")
  1249	            object.__setattr__(self, "support_decision", support)
  1250	
  1251	    def to_dict(self) -> dict[str, Any]:
  1252	        return _json_safe_mapping(
  1253	            {
  1254	                "id": self.id,
  1255	                "source_pack": self.source_pack,
  1256	                "manifest_digest": self.manifest_digest,
  1257	                "alias_chain": list(self.alias_chain),
  1258	                "override": self.override,
  1259	                "trust_eligibility": self.trust_eligibility,
  1260	                "support_decision": self.support_decision,
  1261	            }
  1262	        )
  1263	
  1264	    @classmethod
  1265	    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizerResolution:
  1266	        data = _require_mapping(payload, "finalizer resolution")
  1267	        required = {
  1268	            "id",
  1269	            "source_pack",
  1270	            "manifest_digest",
  1271	            "alias_chain",
  1272	            "override",
  1273	            "trust_eligibility",
  1274	            "support_decision",
  1275	        }
  1276	        _validate_object_keys(data, required=required, allowed=required, label="finalizer resolution")
  1277	        return cls(
  1278	            id=data["id"],
  1279	            source_pack=data["source_pack"],
  1280	            manifest_digest=data["manifest_digest"],
  1281	            alias_chain=data["alias_chain"],
  1282	            override=data["override"],
  1283	            trust_eligibility=data["trust_eligibility"],
  1284	            support_decision=data["support_decision"],
  1285	        )
  1286	
  1287	
  1288	def _normalize_requested_policy(value: Any, label: str = "requested_policy") -> str | dict[str, Any]:
  1289	    if isinstance(value, str):
  1290	        return _require_string(value, label)
  1291	    return _json_safe_mapping(value, label=label)
  1292	
  1293	
  1294	@dataclass(frozen=True)
  1295	class RenderSegment:
  1296	    """One complete temporal window assigned to one qualified backend."""
  1297	
  1298	    window: FrameWindow
  1299	    renderer: RendererResolution
  1300	    input_hashes: dict[str, str] = field(default_factory=dict)
  1301	
  1302	    def __post_init__(self) -> None:
  1303	        object.__setattr__(self, "window", _coerce_window(self.window, "segment window", nullable=False))
  1304	        renderer = (
  1305	            self.renderer
  1306	            if isinstance(self.renderer, RendererResolution)
  1307	            else RendererResolution.from_dict(_require_mapping(self.renderer, "segment renderer"))
  1308	        )
  1309	        object.__setattr__(self, "renderer", renderer)
  1310	        object.__setattr__(
  1311	            self,
  1312	            "input_hashes",
  1313	            _require_hash_mapping(self.input_hashes, "segment input_hashes"),
  1314	        )
  1315	
  1316	    @property
  1317	    def backend(self) -> str:
  1318	        """Compatibility accessor; ``renderer.id`` is authoritative."""
  1319	
  1320	        return self.renderer.id
  1321	
  1322	    @property
  1323	    def support(self) -> SupportReport:
  1324	        """Compatibility accessor; ``renderer.support_decision`` is authoritative."""
  1325	
  1326	        return self.renderer.support_decision
  1327	
  1328	    def to_dict(self) -> dict[str, Any]:
  1329	        return _json_safe_mapping(
  1330	            {
  1331	                "window": self.window,
  1332	                "renderer": self.renderer,
  1333	                "input_hashes": self.input_hashes,
  1334	            }
  1335	        )
  1336	
  1337	    @classmethod
  1338	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderSegment:
  1339	        data = _require_mapping(payload, "render segment")
  1340	        required = {"window", "renderer", "input_hashes"}
  1341	        _validate_object_keys(data, required=required, allowed=required, label="render segment")
  1342	        return cls(
  1343	            window=FrameWindow.from_dict(data["window"]),
  1344	            renderer=RendererResolution.from_dict(data["renderer"]),
  1345	            input_hashes=data["input_hashes"],
  1346	        )
  1347	
  1348	
  1349	@dataclass(frozen=True)
  1350	class RenderPlan:
  1351	    """A deterministic temporal plan plus its explicit finalizer."""
  1352	
  1353	    schema_version: int
  1354	    request_digest: str
  1355	    requested_policy: str | dict[str, Any]
  1356	    planner: PlannerResolution
  1357	    segments: list[RenderSegment]
  1358	    finalizer: FinalizerResolution
  1359	    profile: RenderProfile
  1360	    total_frames: int
  1361	    reasons: dict[str, str]
  1362	    window: FrameWindow | None = None
  1363	
  1364	    def __post_init__(self) -> None:
  1365	        object.__setattr__(
  1366	            self,
  1367	            "schema_version",
  1368	            _require_schema_version(self.schema_version, "render plan"),
  1369	        )
  1370	        object.__setattr__(
  1371	            self,
  1372	            "request_digest",
  1373	            _require_sha256(self.request_digest, "request_digest"),
  1374	        )
  1375	        object.__setattr__(
  1376	            self,
  1377	            "requested_policy",
  1378	            _normalize_requested_policy(self.requested_policy),
  1379	        )
  1380	        planner = (
  1381	            self.planner
  1382	            if isinstance(self.planner, PlannerResolution)
  1383	            else PlannerResolution.from_dict(_require_mapping(self.planner, "planner"))
  1384	        )
  1385	        object.__setattr__(self, "planner", planner)
  1386	        if isinstance(self.segments, (str, bytes)) or not isinstance(self.segments, Sequence):
  1387	            raise TypeError("segments must be an array")
  1388	        segments = [
  1389	            item
  1390	            if isinstance(item, RenderSegment)
  1391	            else RenderSegment.from_dict(_require_mapping(item, f"segments[{index}]"))
  1392	            for index, item in enumerate(self.segments)
  1393	        ]
  1394	        object.__setattr__(self, "segments", segments)
  1395	        finalizer = (
  1396	            self.finalizer
  1397	            if isinstance(self.finalizer, FinalizerResolution)
  1398	            else FinalizerResolution.from_dict(_require_mapping(self.finalizer, "finalizer"))
  1399	        )
  1400	        object.__setattr__(self, "finalizer", finalizer)
  1401	        profile = _coerce_profile(self.profile, "plan profile", nullable=False)
  1402	        object.__setattr__(self, "profile", profile)
  1403	        total_frames = _require_int(self.total_frames, "total_frames", minimum=0)
  1404	        object.__setattr__(self, "total_frames", total_frames)
  1405	        window = _coerce_window(self.window, "plan window", nullable=True)
  1406	        object.__setattr__(self, "window", window)
  1407	        if window is not None:
  1408	            if window.fps_rational != profile.fps_rational:
  1409	                raise ValueError("plan window FPS must exactly match the canonical profile FPS")
  1410	            if window.end_frame > total_frames:
  1411	                raise ValueError("plan window must not extend beyond total_frames")
  1412	        if total_frames == 0:
  1413	            if window is not None or segments:
  1414	                raise ValueError("a zero-frame plan must have no window or segments")
  1415	        else:
  1416	            if not segments:
  1417	                raise ValueError("a positive-frame plan must contain at least one segment")
  1418	            target_start = window.start_frame if window is not None else 0
  1419	            target_end = window.end_frame if window is not None else total_frames
  1420	            expected_start = target_start
  1450	                "segments": self.segments,
  1451	                "finalizer": self.finalizer,
  1452	                "profile": self.profile,
  1453	                "total_frames": self.total_frames,
  1454	                "reasons": self.reasons,
  1455	                "window": self.window,
  1456	            }
  1457	        )
  1458	
  1459	    @classmethod
  1460	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderPlan:
  1461	        try:
  1462	            data = _require_mapping(payload, "render plan")
  1463	            required = {
  1464	                "schema_version",
  1465	                "request_digest",
  1466	                "requested_policy",
  1467	                "planner",
  1468	                "segments",
  1469	                "finalizer",
  1470	                "profile",
  1471	                "total_frames",
  1472	                "reasons",
  1473	                "window",
  1474	            }
  1475	            _validate_object_keys(data, required=required, allowed=required, label="render plan")
  1476	            raw_segments = data["segments"]
  1477	            if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
  1478	                raise TypeError("segments must be an array")
  1479	            return cls(
  1480	                schema_version=data["schema_version"],
  1481	                request_digest=data["request_digest"],
  1482	                requested_policy=data["requested_policy"],
  1483	                planner=PlannerResolution.from_dict(data["planner"]),
  1484	                segments=[RenderSegment.from_dict(item) for item in raw_segments],
  1485	                finalizer=FinalizerResolution.from_dict(data["finalizer"]),
  1486	                profile=RenderProfile.from_dict(data["profile"]),
  1487	                total_frames=data["total_frames"],
  1488	                reasons=data["reasons"],
  1489	                window=FrameWindow.from_dict(data["window"]) if data["window"] is not None else None,
  1490	            )
  1491	        except Exception as exc:
  1492	            from .errors import RendererException
  1493	
  1494	            if isinstance(exc, RendererException):
  1495	                raise
  1496	            _protocol_failure(
  1497	                f"malformed render plan: {exc}",
  1498	                details={"error_type": type(exc).__name__},
  1499	            )
  1500	
  1501	
  1502	def _validate_backend_fragments(value: Any) -> dict[str, dict[str, Any]]:
  1503	    mapping = _require_mapping(value, "backend_fragments")
  1504	    fragments: dict[str, dict[str, Any]] = {}
  1505	    for raw_namespace, raw_fragment in mapping.items():
  1506	        namespace = _require_qualified_id(raw_namespace, "backend fragment namespace")
  1507	        fragment = _json_safe_mapping(raw_fragment, label=f"backend_fragments[{namespace!r}]")
  1508	        conflicts = sorted(set(fragment) & RESERVED_BACKEND_FRAGMENT_KEYS)
  1509	        if conflicts:
  1510	            raise ValueError(
  1511	                f"backend fragment {namespace!r} attempts to overwrite core-owned keys: "
  1512	                f"{', '.join(conflicts)}"
  1513	            )
  1514	        fragments[namespace] = fragment
  1515	    return fragments
  1516	
  1517	
  1518	@dataclass(frozen=True)
  1519	class RenderResult:
  1520	    """Successful renderer/finalizer result written to the authoritative path."""
  1521	
  1522	    schema_version: int
  1523	    video: VideoArtifact
  1524	    audio_ownership: AudioOwnership
  1525	    backend_fragments: dict[str, dict[str, Any]] = field(default_factory=dict)
  1526	    normalization: list[str] = field(default_factory=list)
  1527	    logs: list[str] = field(default_factory=list)
  1528	    metadata: dict[str, str] = field(default_factory=dict)
  1529	
  1530	    def __post_init__(self) -> None:
  1531	        version = _require_schema_version(self.schema_version, "render result")
  1532	        video = (
  1533	            self.video
  1534	            if isinstance(self.video, VideoArtifact)
  1535	            else VideoArtifact.from_dict(_require_mapping(self.video, "video"))
  1536	        )
  1537	        ownership = _coerce_audio_ownership(
  1538	            self.audio_ownership,
  1539	            "audio_ownership",
  1540	            nullable=False,
  1541	        )
  1542	        if video.audio is None or video.audio != ownership:
  1543	            raise ValueError("video.audio must be present and match result audio_ownership")
  1544	        object.__setattr__(self, "schema_version", version)
  1545	        object.__setattr__(self, "video", video)
  1546	        object.__setattr__(self, "backend_fragments", _validate_backend_fragments(self.backend_fragments))
  1547	        object.__setattr__(self, "audio_ownership", ownership)
  1548	        object.__setattr__(
  1549	            self,
  1550	            "normalization",
  1551	            _require_string_list(self.normalization, "normalization"),
  1552	        )
  1553	        object.__setattr__(self, "logs", _require_string_list(self.logs, "logs"))
  1554	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
  1555	
  1556	    @property
  1557	    def attachments(self) -> dict[str, Attachment]:
  1558	        """The sole authoritative attachment map, owned by the primary video."""
  1559	
  1560	        return self.video.attachments
  1561	
  1562	    def to_dict(self) -> dict[str, Any]:
  1563	        return _json_safe_mapping(
  1564	            {
  1565	                "schema_version": self.schema_version,
  1566	                "video": self.video,
  1567	                "backend_fragments": self.backend_fragments,
  1568	                "audio_ownership": self.audio_ownership,
  1569	                "normalization": self.normalization,
  1570	                "logs": self.logs,
  1571	                "metadata": self.metadata,
  1572	            }
  1573	        )
  1574	
  1575	    @classmethod
  1576	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderResult:
  1577	        try:
  1578	            data = _require_mapping(payload, "render result")
  1579	            allowed = set(RENDER_RESULT_CORE_KEYS)
  1580	            _validate_object_keys(
  1581	                data,
  1582	                required={"schema_version", "video", "audio_ownership"},
  1583	                allowed=allowed,
  1584	                label="render result",
  1585	            )
  1586	            version = _require_schema_version(data["schema_version"], "render result")
  1587	            return cls(
  1588	                schema_version=version,
  1589	                video=VideoArtifact.from_dict(data["video"]),
  1590	                audio_ownership=data["audio_ownership"],
  1591	                backend_fragments=data.get("backend_fragments", {}),
  1592	                normalization=data.get("normalization", []),
  1593	                logs=data.get("logs", []),
  1594	                metadata=data.get("metadata", {}),
  1595	            )
  1596	        except Exception as exc:
  1597	            from .errors import RendererException
  1598	
  1599	            if isinstance(exc, RendererException):
  1600	                raise

exec
/bin/zsh -lc "python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B; base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=_plan(segments=[] , total_frames=0, profile=_profile(audio=False)),audio_ownership=\"none\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility());
for x in (None,{},[],{\"x\":{\"profile\":_profile(audio=False),\"sha256\":SHA_B,\"attachments\":{}}}):
 try: print(type(x).__name__,assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])
 except Exception as e: print(type(x).__name__,type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 154ms:
NoneType {}
dict {}
list []
dict {'x': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}}

exec
/bin/zsh -lc "python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B; p=_plan(segments=[] , total_frames=0, profile=_profile(audio=False)); base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=p,audio_ownership=\"none\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility());
for x in ([{\"profile\":_profile(audio=False),\"sha256\":SHA_B,\"attachments\":{}}],):
 try: print(assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])
 except Exception as e: print(type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 128ms:
[{'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}]

exec
/bin/zsh -lc "rg -n \"artifact_profiles\" .oracle/checkins/batch-1*.md .oracle/briefs .oracle/plan.md docs | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/checkins/batch-1-r6.md:28:   - `_normalize_artifact_profiles` now takes the plan's segments: `None`
.oracle/checkins/batch-1-r6.md:1394:.oracle/checkins/batch-1-r5.md:35:   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
.oracle/checkins/batch-1-r6.md:1420:.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1422:.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1424:.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1425:.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1433:.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1435:.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r6.md:1438:.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1439:.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1441:.oracle/checkins/batch-1-r5.md:1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r6.md:1442:.oracle/checkins/batch-1-r5.md:1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r6.md:1622:    86	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r6.md:1635:    99	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r6.md:1649:   113	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r6.md:1700:   188	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r6.md:1750:   238	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r6.md:1759:   468	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r6.md:1769:   478	are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r6.md:1897:-def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r6.md:1898:+def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
.oracle/checkins/batch-1-r6.md:1909:+                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
.oracle/checkins/batch-1-r6.md:1919:                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r6.md:1926:+                "artifact_profiles must record a hashed lineage entry for every "
.oracle/checkins/batch-1-r6.md:1943:+                "artifact_profiles must record a hashed lineage entry for every "
.oracle/checkins/batch-1-r6.md:1947:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r6.md:2074:     artifact_profiles: Any = None,
.oracle/checkins/batch-1-r6.md:2125:-        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r6.md:2126:+        "artifact_profiles": _normalize_artifact_profiles(
.oracle/checkins/batch-1-r6.md:2127:+            artifact_profiles,
.oracle/checkins/batch-1-r6.md:2275: `artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r6.md:2285:-are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r6.md:2291:+are REQUIRED in `artifact_profiles` for any positive render plan as hashed
.oracle/checkins/batch-1-r6.md:2503:-        artifact_profiles={},
.oracle/checkins/batch-1-r6.md:2504:+        artifact_profiles={
.oracle/checkins/batch-1-r6.md:2568:         artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r6.md:2575:     lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r6.md:2629:         assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r6.md:2633:-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
.oracle/checkins/batch-1-r6.md:2634:+            artifact_profiles={
.oracle/checkins/batch-1-r6.md:2641:-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
.oracle/checkins/batch-1-r6.md:2642:+            artifact_profiles={
.oracle/checkins/batch-1-r6.md:2653:+            artifact_profiles={
.oracle/checkins/batch-1-r6.md:2850:    86	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
.oracle/checkins/batch-1-r6.md:2860:    96	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
.oracle/checkins/batch-1-r6.md:2868:   104	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r6.md:2875:   111	                "artifact_profiles must record a hashed lineage entry for every "
.oracle/checkins/batch-1-r6.md:2890:   126	                "artifact_profiles must record a hashed lineage entry for every "
.oracle/checkins/batch-1-r6.md:2894:   130	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r6.md:2997:   233	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r6.md:3048:   284	        "artifact_profiles": _normalize_artifact_profiles(
.oracle/checkins/batch-1-r6.md:3049:   285	            artifact_profiles,
.oracle/checkins/batch-1-r6.md:3148:   567	        "artifact_profiles": {
.oracle/checkins/batch-1-r6.md:3273:   692	        artifact_profiles={
.oracle/checkins/batch-1-r6.md:3337:   756	        artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r6.md:3344:   763	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r6.md:3398:   817	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r6.md:3404:/bin/zsh -lc "rg -n \"artifact_profiles|_normalize_artifact_profiles|assemble_provenance_v2|assemble_provenance\\(\" -g '*.py' -g '*.md' -g '*.json' --glob '"'!.oracle/checkins/batch-1-r5.md'"' --glob '"'!remotion/node_modules/**'"' . | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r6.md:3408:./tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
.oracle/checkins/batch-1-r6.md:3412:./tests/core/rendering/test_contracts.py:692:        artifact_profiles={
.oracle/checkins/batch-1-r6.md:3414:./tests/core/rendering/test_contracts.py:756:        artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r6.md:3415:./tests/core/rendering/test_contracts.py:763:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r6.md:3416:./tests/core/rendering/test_contracts.py:817:        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r6.md:3418:./tests/core/rendering/test_contracts.py:821:            artifact_profiles={
.oracle/checkins/batch-1-r6.md:3420:./tests/core/rendering/test_contracts.py:828:            artifact_profiles={
.oracle/checkins/batch-1-r6.md:3422:./tests/core/rendering/test_contracts.py:839:            artifact_profiles={
.oracle/checkins/batch-1-r6.md:3423:./docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r6.md:3424:./docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan as hashed
.oracle/checkins/batch-1-r6.md:3425:./astrid/core/rendering/provenance.py:86:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
.oracle/checkins/batch-1-r6.md:3426:./astrid/core/rendering/provenance.py:96:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
.oracle/checkins/batch-1-r6.md:3427:./astrid/core/rendering/provenance.py:104:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r6.md:3428:./astrid/core/rendering/provenance.py:111:                "artifact_profiles must record a hashed lineage entry for every "
.oracle/checkins/batch-1-r6.md:3429:./astrid/core/rendering/provenance.py:126:                "artifact_profiles must record a hashed lineage entry for every "
.oracle/checkins/batch-1-r6.md:3430:./astrid/core/rendering/provenance.py:130:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r6.md:3432:./astrid/core/rendering/provenance.py:233:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r6.md:3433:./astrid/core/rendering/provenance.py:284:        "artifact_profiles": _normalize_artifact_profiles(
.oracle/checkins/batch-1-r6.md:3434:./astrid/core/rendering/provenance.py:285:            artifact_profiles,
.oracle/checkins/batch-1-r6.md:3440:./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
.oracle/checkins/batch-1-r6.md:3441:./astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
.oracle/checkins/batch-1-r6.md:3468:   468	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r6.md:3478:   478	are REQUIRED in `artifact_profiles` for any positive render plan as hashed
.oracle/checkins/batch-1-r6.md:3540:   319	              "artifact_profiles",
.oracle/checkins/batch-1-r6.md:3676:    65	        "artifact_profiles",
.oracle/checkins/batch-1-r6.md:6323:               "artifact_profiles",
.oracle/checkins/batch-1-r6.md:8658:   817	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r6.md:8662:   821	            artifact_profiles={
.oracle/checkins/batch-1-r6.md:8669:   828	            artifact_profiles={
.oracle/checkins/batch-1-r6.md:8680:   839	            artifact_profiles={
.oracle/checkins/batch-1-r6.md:8723:-        artifact_profiles={},
.oracle/checkins/batch-1-r6.md:8724:+        artifact_profiles={
.oracle/checkins/batch-1-r6.md:8748:         assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r6.md:8752:-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
.oracle/checkins/batch-1-r6.md:8753:+            artifact_profiles={
.oracle/checkins/batch-1-r6.md:8760:-            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
.oracle/checkins/batch-1-r6.md:8761:+            artifact_profiles={
.oracle/checkins/batch-1-r6.md:8772:+            artifact_profiles={
.oracle/checkins/batch-1-r6.md:8800:/bin/zsh -lc "python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from astrid.core.rendering.contracts import Attachment, VideoArtifact; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B,SHA_C; base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=_plan(),audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility()); a=VideoArtifact(path=\"outputs/visual.mp4\",profile=_profile(),sha256=SHA_B,duration_frames=48,audio=\"rendered\",attachments={}); print(\"sequence video ->\",assemble_provenance_v2(**base,artifact_profiles=[a])[\"artifact_profiles\"]); x={\"out/v.mp4\":{\"profile\":_profile(),\"sha256\":SHA_B,\"attachments\":{\"spoofed\":Attachment(name=\"real\",path=\"outputs/real.dat\",kind=\"project\",sha256=SHA_C)}}}; print(\"attachment mismatch ->\",assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r6.md:9387: try: print(type(x).__name__,assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])
.oracle/checkins/batch-1-r6.md:9398: try: print(assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])
.oracle/checkins/batch-1-r5.md:35:   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r5.md:1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r5.md:1993: def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r5.md:2031:+                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r5.md:2049:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r5.md:2124:     artifact_profiles: Any = None,
.oracle/checkins/batch-1-r5.md:3816:    86	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r5.md:3829:    99	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r5.md:3843:   113	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r5.md:3918:   188	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r5.md:3968:   238	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r5.md:4083:    65	        "artifact_profiles",
.oracle/checkins/batch-1-r5.md:4831:   567	        "artifact_profiles": {
.oracle/checkins/batch-1-r5.md:4956:   692	        artifact_profiles={},
.oracle/checkins/batch-1-r5.md:5014:   750	        artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r5.md:5021:   757	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r5.md:5075:   811	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r5.md:5079:   815	            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
.oracle/checkins/batch-1-r5.md:5084:   820	            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
.oracle/checkins/batch-1-r5.md:5085:   820	            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
.oracle/checkins/batch-1-r5.md:5546: def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r5.md:5584:+                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r5.md:5602:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r5.md:5767: `artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r5.md:5777:-are recorded in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r5.md:5778:+are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r5.md:5851:-        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r5.md:5852:+        "artifact_profiles": {
.oracle/checkins/batch-1-r5.md:5965:         artifact_profiles={},
.oracle/checkins/batch-1-r5.md:5969:         artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r5.md:5976:     lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r5.md:6030:+        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r5.md:6034:+            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
.oracle/checkins/batch-1-r5.md:6039:+            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
.oracle/checkins/batch-1-r5.md:6087:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r5.md:6103:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
.oracle/checkins/batch-1-r5.md:7315:/bin/zsh -lc "rg -n \"artifact_profiles\" -S --glob '"'!*.pyc'"' --glob '"'!.oracle/checkins/**'"' . | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r5.md:7317:./docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r5.md:7318:./docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r5.md:7319:./astrid/core/rendering/provenance.py:86:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r5.md:7320:./astrid/core/rendering/provenance.py:99:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r5.md:7321:./astrid/core/rendering/provenance.py:113:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r5.md:7322:./astrid/core/rendering/provenance.py:188:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r5.md:7323:./astrid/core/rendering/provenance.py:238:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r5.md:7324:./astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
.oracle/checkins/batch-1-r5.md:7325:./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
.oracle/checkins/batch-1-r5.md:7326:./tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
.oracle/checkins/batch-1-r5.md:7327:./tests/core/rendering/test_contracts.py:692:        artifact_profiles={},
.oracle/checkins/batch-1-r5.md:7328:./tests/core/rendering/test_contracts.py:750:        artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r5.md:7329:./tests/core/rendering/test_contracts.py:757:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r5.md:7330:./tests/core/rendering/test_contracts.py:811:        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
.oracle/checkins/batch-1-r5.md:7331:./tests/core/rendering/test_contracts.py:815:            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
.oracle/checkins/batch-1-r5.md:7332:./tests/core/rendering/test_contracts.py:820:            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
.oracle/checkins/batch-1-r5.md:7476:   319	              "artifact_profiles",
.oracle/checkins/batch-1-r5.md:7673: def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r5.md:7692:+                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r5.md:7707:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r5.md:7792:     artifact_profiles: Any = None,
.oracle/checkins/batch-1-r5.md:7888:         "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r5.md:11277:/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json; from astrid.core.rendering.contracts import RenderProfile; from astrid.core.rendering.provenance import _normalize_artifact_profiles as n; p=RenderProfile.from_dict(json.load(open(\"tests/core/rendering/fixtures/v1/plan.json\"))[\"profile\"]); cases=[None,{}, {\"out.mp4\":{\"profile\":p,\"sha256\":int(\"1\"*64)}}, {\"out.mp4\":{\"profile\":p,\"sha256\":\"a\"*64,\"attachments\":None}}, {\"out.mp4\":{\"profile\":p,\"sha256\":\"a\"*64,\"attachments\":{\"x\":{\"path\":\"None\",\"kind\":\"None\",\"sha256\":int(\"2\"*64)}}}}];
.oracle/checkins/batch-1-r5.md:11289:/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json; from astrid.core.rendering.contracts import RenderProfile; from astrid.core.rendering.provenance import _normalize_artifact_profiles as n; p=RenderProfile.from_dict(json.load(open(\"tests/core/rendering/fixtures/v1/plan.json\"))[\"profile\"]); print(n({\"out.mp4\":{\"profile\":p,\"sha256\":\"a\"*64,\"attachments\":{\"x\":{\"sha256\":\"b\"*64}}}}))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r5.md:15867:    86	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r5.md:15880:    99	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
.oracle/checkins/batch-1-r5.md:15894:   113	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r5.md:15945:   188	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r5.md:15995:   238	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r5.md:16004:   468	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r5.md:16014:   478	are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r1.md:7556:84:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r1.md:8889:         "artifact_profiles",
.oracle/checkins/batch-1-r1.md:10488: def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r1.md:10512:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r1.md:10555:     artifact_profiles: Any = None,
.oracle/checkins/batch-1-r1.md:10646:         "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r1.md:11608:452:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r1.md:12643:docs/contracts/render-backend-v1.md-452-`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r1.md:13455:   556	        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r1.md:13593:    84	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r1.md:13614:   105	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r1.md:13647:   138	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r1.md:13693:   184	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r1.md:13758:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r1.md:14008:astrid/core/rendering/schemas/v1/result.json:140:              "segments", "artifact_profiles", "finalizer", "attachments",
.oracle/checkins/batch-1-r1.md:14609:   140	              "segments", "artifact_profiles", "finalizer", "attachments",
.oracle/checkins/batch-1-r1.md:20043:    84	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r1.md:20064:   105	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r1.md:20097:   138	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r1.md:20143:   184	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r1.md:20669:/bin/zsh -lc 'rg -n "request_digest|request digest|canonical.*digest|artifact_profiles|artifact.*hash" docs/contracts/render-backend-v1.md astrid/core/rendering tests/core/rendering | head -160' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r1.md:20673:docs/contracts/render-backend-v1.md:452:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r1.md:20675:astrid/core/rendering/provenance.py:84:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r1.md:20676:astrid/core/rendering/provenance.py:105:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r1.md:20677:astrid/core/rendering/provenance.py:138:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r1.md:20679:astrid/core/rendering/provenance.py:184:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r1.md:20683:astrid/core/rendering/schemas/v1/result.json:140:              "segments", "artifact_profiles", "finalizer", "attachments",
.oracle/checkins/batch-1-r1.md:20688:astrid/core/rendering/contracts.py:63:        "artifact_profiles",
.oracle/checkins/batch-1-r1.md:20701:tests/core/rendering/test_contracts.py:556:        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r1.md:20733:    63	        "artifact_profiles",
.oracle/checkins/batch-1-r1.md:20792:   556	        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:2325:    63	        "artifact_profiles",
.oracle/checkins/batch-1-r2.md:2384:   556	        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:3507:         "artifact_profiles",
.oracle/checkins/batch-1-r2.md:4413: def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r2.md:4434:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r2.md:4467:     artifact_profiles: Any = None,
.oracle/checkins/batch-1-r2.md:4518:         "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r2.md:6715:463-`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r2.md:6725:473-segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r2.md:6862:    84	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r2.md:6883:   105	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r2.md:6916:   138	    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r2.md:6966:   188	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r2.md:7079:   556	        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:7348:tests/core/rendering/test_contracts.py-556-        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:15479:docs/contracts/render-backend-v1.md-473-segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r2.md:15696:/bin/zsh -lc "rg -n 'artifact_profiles|artifact_hash|output_hash|sha256' astrid/core/rendering/provenance.py astrid/core/rendering/contracts.py docs/contracts/render-backend-v1.md tests/core/rendering/test_contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r2.md:15706:tests/core/rendering/test_contracts.py:556:        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:15710:docs/contracts/render-backend-v1.md:463:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r2.md:15711:docs/contracts/render-backend-v1.md:473:segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r2.md:15713:astrid/core/rendering/provenance.py:84:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r2.md:15714:astrid/core/rendering/provenance.py:105:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r2.md:15715:astrid/core/rendering/provenance.py:138:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r2.md:15716:astrid/core/rendering/provenance.py:188:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r2.md:15720:astrid/core/rendering/contracts.py:65:        "artifact_profiles",
.oracle/checkins/batch-1-r2.md:26177:   314	              "artifact_profiles",
.oracle/checkins/batch-1-r2.md:26304:    65	        "artifact_profiles",
.oracle/checkins/batch-1-r2.md:26895:    65	        "artifact_profiles",
.oracle/checkins/batch-1-r2.md:27093:    84	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r2.md:27114:   105	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r2.md:27140:   188	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r2.md:27466:   314	              "artifact_profiles",
.oracle/checkins/batch-1-r2.md:27630:rg -n \"artifact.*hash|output.*hash|trust_eligibility|artifact_profiles\" astrid/core/rendering docs/contracts/render-backend-v1.md tests/core/rendering/test_provenance.py tests/core/rendering -g '*.py' -g '*.md' | head -120" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r2.md:27671:   463	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r2.md:27681:   473	segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r2.md:27691:docs/contracts/render-backend-v1.md:463:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r2.md:27693:docs/contracts/render-backend-v1.md:473:segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r2.md:27694:astrid/core/rendering/provenance.py:84:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r2.md:27695:astrid/core/rendering/provenance.py:105:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r2.md:27696:astrid/core/rendering/provenance.py:138:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r2.md:27697:astrid/core/rendering/provenance.py:188:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r2.md:27698:astrid/core/rendering/contracts.py:65:        "artifact_profiles",
.oracle/checkins/batch-1-r2.md:27708:tests/core/rendering/test_contracts.py:556:        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:27942:/bin/zsh -lc "rg -n \"class Attachment|class VideoArtifact|artifact_profiles|input_hashes\" astrid/core/rendering/contracts.py | head -60
.oracle/checkins/batch-1-r2.md:27945:65:        "artifact_profiles",
.oracle/checkins/batch-1-r2.md:28403:   556	        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r2.md:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r2.md:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r3.md:39:   - Artifact hashes: `artifact_profiles` carries per-artifact profiles
.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r3.md:4545:               "artifact_profiles",
.oracle/checkins/batch-1-r3.md:4953:    65	        "artifact_profiles",
.oracle/checkins/batch-1-r3.md:8289:/bin/zsh -lc "nl -ba .oracle/briefs/batch-1-r2-t1.2.md | sed -n '1,140p' && rg -n \"resolution|trust_eligibility|support_decision|alias_chain|override|artifact_profiles|hash\" docs/contracts/render-backend-v1.md .oracle/plan.md .oracle/tasklist.md | head -260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r3.md:8418:docs/contracts/render-backend-v1.md:466:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r3.md:8422:docs/contracts/render-backend-v1.md:476:segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r3.md:8555:   466	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r3.md:8565:   476	segment in the plan's `input_hashes` and in `artifact_profiles`.
.oracle/checkins/batch-1-r3.md:8830:+        artifact_profiles={},
.oracle/checkins/batch-1-r3.md:9384:astrid/core/rendering/schemas/v1/result.json	definitions.backendFragments.additionalProperties.propertyNames	{"not":{"enum":["schema_version","video","backend_fragments","audio_ownership","normalization","logs","metadata","engine","output","timeline","assets_registry","request_digest","requested_policy","planner","segments","artifact_profiles","finalizer","attachments","project_dir","composition_id","active_pack_order","active_theme","registry_hash","registry_state","resolved_effect_ids","resolved_effects","source_pack_ids","element_roots","staged_asset_ids","staged_asset_root","segment_provenance","ffmpeg_specialization","audio_reactive_colour","resolved_backend","source_pack","alias_chain","override","trust_eligibility","manifest_digest","support_decision","input_hashes","segments_v2"]}}
.oracle/checkins/batch-1-r3.md:10861:/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '1,340p' && rg -n \"assemble_provenance_v2|artifact_profiles|segments_v2|PlannerResolution|RendererResolution|FinalizerResolution\" -g'*.py' . | head -260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r3.md:10863:./astrid/core/rendering/provenance.py:84:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r3.md:10864:./astrid/core/rendering/provenance.py:105:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r3.md:10866:./astrid/core/rendering/provenance.py:138:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r3.md:10868:./astrid/core/rendering/provenance.py:188:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r3.md:10874:./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
.oracle/checkins/batch-1-r3.md:10910:./tests/core/rendering/test_contracts.py:559:        "artifact_profiles": {"outputs/video.mp4": _profile()},
.oracle/checkins/batch-1-r3.md:10917:./tests/core/rendering/test_contracts.py:678:        artifact_profiles={},
.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1.md:1705:   412	`input_hashes`, `segments`, `artifact_profiles`, `audio_ownership`,
.oracle/checkins/batch-1.md:1876:astrid/core/rendering/provenance.py:109:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1.md:2478:    70	        "artifact_profiles",
.oracle/checkins/batch-1.md:4972:   121	            "input_hashes", "segments", "artifact_profiles", "audio_ownership",
.oracle/checkins/batch-1.md:5729:   109	def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1.md:5744:   124	    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1.md:5786:   166	    artifact_profiles: Any = None,
.oracle/checkins/batch-1.md:5863:   243	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1.md:14018:    72	  `support_decision`, `input_hashes`, `segments`, `artifact_profiles`,
.oracle/checkins/batch-1.md:16111:        "artifact_profiles",
.oracle/checkins/batch-1.md:17963:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1.md:17978:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1.md:18020:    artifact_profiles: Any = None,
.oracle/checkins/batch-1.md:18097:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1.md:18642:            "input_hashes", "segments", "artifact_profiles", "audio_ownership",
.oracle/checkins/batch-1.md:19634:    72	  `support_decision`, `input_hashes`, `segments`, `artifact_profiles`,
.oracle/checkins/batch-1.md:19751:   412	`input_hashes`, `segments`, `artifact_profiles`, `audio_ownership`,
.oracle/checkins/batch-1-r4.md:35:   - Hashed artifact lineage: `artifact_profiles` now emits per-output
.oracle/checkins/batch-1-r4.md:15314:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r4.md:15329:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r4.md:15415:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r4.md:15440:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r4.md:16149:   686	        artifact_profiles={},
.oracle/checkins/batch-1-r4.md:16207:   744	        artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r4.md:16214:   751	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r4.md:17476: def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r4.md:17530:     raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r4.md:17579:     artifact_profiles: Any = None,
.oracle/checkins/batch-1-r4.md:17629:         "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r4.md:18028:         artifact_profiles={},
.oracle/checkins/batch-1-r4.md:18086:+        artifact_profiles={"outputs/visual.mp4": artifact},
.oracle/checkins/batch-1-r4.md:18093:+    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
.oracle/checkins/batch-1-r4.md:18229:/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '450,525p'; rg -n \"artifact_profiles\" -S . --glob '"'!'"\\.oracle/checkins/**' --glob '"'!/tmp/**'"' | head -n 200" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r4.md:18247:   466	`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r4.md:18257:   476	are recorded in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r4.md:18307:./docs/contracts/render-backend-v1.md:466:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
.oracle/checkins/batch-1-r4.md:18308:./docs/contracts/render-backend-v1.md:476:are recorded in `artifact_profiles` as hashed lineage records: each maps an
.oracle/checkins/batch-1-r4.md:18309:./astrid/core/rendering/provenance.py:85:def _normalize_artifact_profiles(value: Any) -> Any:
.oracle/checkins/batch-1-r4.md:18310:./astrid/core/rendering/provenance.py:131:    raise TypeError("artifact_profiles must be an object or array")
.oracle/checkins/batch-1-r4.md:18311:./astrid/core/rendering/provenance.py:180:    artifact_profiles: Any = None,
.oracle/checkins/batch-1-r4.md:18312:./astrid/core/rendering/provenance.py:230:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
.oracle/checkins/batch-1-r4.md:18313:./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
.oracle/checkins/batch-1-r4.md:18314:./tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {"outputs/video.mp4": _profile()},

exec
/bin/zsh -lc "sed -n '1,120p' .oracle/checkins/batch-1-r6.md && sed -n '1,110p' .oracle/checkins/batch-1-r5.md && rg -n \"codex"'$|tokens used|Hashed artifact lineage remains optional" .oracle/checkins/batch-1-r5.md | tail -n 30' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
Reading additional input from stdin...
2026-08-12T01:40:48.514651Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:40:48.514675Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:40:48.514680Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3a1-165c-7371-b898-2a174fb34ef5
--------
user
# Megado Checkpoint — Batch 1 sixth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3).
Sixth rework committed as `086d692` (prior head 91f0fe3). Incremental diff at
/tmp/batch1-r6.diff.

## How each of your 3 re-review5 issues was addressed (host-implemented)

1. **Hashed artifact lineage optional and unbound** →
   - `_normalize_artifact_profiles` now takes the plan's segments: `None`
     becomes `{}` (not `[]`) and a POSITIVE plan with no lineage entries
     raises ValueError.
   - Mapping keys must equal `VideoArtifact.path` for VideoArtifact values.
   - Spoof tests extended (unknown field, null sha256, malformed sha256).
2. **Lineage mappings spoofable** →
   - Exact `{profile, sha256, attachments}` shape enforced: unknown and
     missing fields rejected on the artifact and every attachment; null
     sha256 raises ValueError; non-string sha256 raises TypeError; hashes
     validated as 64-hex; attachment path/kind nonblank; Sequence entries
     share the same path; Attachment dataclass values handled without
     leaking the redundant `name` field.
3. **Schema/DTO parity** →
   - Anchored nonblank pattern now `^(?![\s\S]*\u0000)[\s\S]*\S[\s\S]*$`
     (rejects NUL after newlines; multiline accepted).
   - workspacePath accepts internal newlines (uses `[\s\S]*`), still rejects
     whitespace-only and NUL.
   - support features + plan/finalize hashMap gained nonblank/NUL
     `propertyNames`.

## Evidence

- Incremental diff: /tmp/batch1-r6.diff (12 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.
- Docs updated: strict lineage shape + path binding.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has now passed 6 review rounds.
The contract must be sound and STABLE for M2 (Batches 2-5 build on it). If the
remaining nits are non-blocking or absent, say exactly `PASS`. If you find
blocking issues, name them precisely with minimum rework.
codex
I’m using the Astrid repo skill for repository-specific rules and the Megado skill for the checkpoint contract. I’ll inspect the incremental diff and the affected implementation/tests read-only, then return only `PASS` or precise blocking issues.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
     950 total
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
Reading additional input from stdin...
2026-08-12T01:24:13.326119Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:13.326149Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:13.326154Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff391-e6bd-7441-9ad0-9566582bed05
--------
user
# Megado Checkpoint — Batch 1 fifth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), batch-1-r1.md (5), batch-1-r2.md (3),
batch-1-r3.md (3), batch-1-r4.md (4). Fifth rework committed as `91f0fe3`
(prior head 808030e). Incremental diff at /tmp/batch1-r5.diff.

## How each of your 4 re-review4 issues was addressed (host-implemented)

1. **Override coherence unvalidated** →
   - New `_require_override` helper: override must be exactly `{from, to}`
     (both qualified ids) with `to` == the resolution id. Applied to planner,
     renderer, AND finalizer post_init. Schema `overrideRecord` definition
     (`{from, to}` required, both `qualifiedId`) referenced from all three
     resolution schemas in plan.json + finalize.json. Adversarial test
     (wrong `to`, wrong shape) for all three classes.
2. **Hashed artifact lineage optional/spoofable** →
   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
     be VideoArtifact or `{profile, sha256, attachments}` with validated
     64-hex sha256 on artifact and every attachment; null/malformed hashes
     rejected; profile-only entries raise TypeError. Sequence form likewise.
   - `test_provenance_rejects_spoofed_artifact_lineage` (profile-only, null
     sha256, malformed sha256).
3. **Schema/DTO parity** →
   - workspacePath accepts DTO-valid leading whitespace (`. *\S.*` tail),
     still rejects whitespace-only.
   - Anchored nonblank pattern now `^(?!.*\u0000)[\s\S]*\S[\s\S]*$` — accepts
     multiline like the DTO, rejects NUL anywhere.
   - Manifest metadata, feature maps, support features, and plan hashMap
     gained nonblank/NUL `propertyNames` constraints.
   - `_manifest_features` string values now pass `_require_string` (blank/NUL
     rejected), matching the schema.
4. **Fixture doesn't exercise installed revision** →
   - Install proof now installs into a temp `InstalledPackStore` with
     `trust_method="test"` (a valid trust method), then resolves
     `include_installed=True` with an empty source tree, asserting
     `source_kind == "installed"`, `execution_eligible`, and the full
     alias → absent-canonical → override evidence from the INSTALLED
     revision. Also proves validate_pack passes before install.

## Evidence

- Incremental diff: /tmp/batch1-r5.diff (14 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.
- Docs updated: override `{from,to}` coherence, REQUIRED hashed artifact
  lineage.

## Verdict

Binary: `PASS` or a list of issues. Verify the four closures above; also scan
the cumulative C1..HEAD diff (now ~57k lines) for anything new. If PASS, say
exactly `PASS` — Batch 2 may then begin.
codex
I’m using the `megado` checkpoint workflow for this fifth re-review. I’ll verify the four claimed closures against code, schemas, and tests, then inspect both the incremental and cumulative diffs for regressions; the worktree will remain read-only.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
72:codex
256:codex
1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
6082:codex
6087:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
6097:tokens used
6103:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
10450:codex
16026:codex
16027:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
16036:tokens used
16038:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/request.json | sed -n '1,110p' && nl -ba astrid/core/rendering/contracts.py | sed -n '770,870p' && python3 -c 'import json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import RenderRequest; b=json.load(open(\"tests/core/rendering/fixtures/v1/request.json\"));
for k in (\"timeline_path\",\"assets_registry_path\"):
 for s in (\"ok\\nsub/../evil.json\",\"ok\\nsub//evil.json\",\"ok\\nsub\\\\evil.json\"):
  x=dict(b); x[k]=s; print(k,repr(s),Draft7Validator(json.load(open(\"astrid/core/rendering/schemas/v1/request.json\"))).is_valid(x),end=\" \");
  try: RenderRequest.from_dict(x); print(\"dto true\")
  except Exception as e: print(\"dto false\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 113ms:
timeline_path 'ok\nsub/../evil.json' True dto true
timeline_path 'ok\nsub//evil.json' True dto true
timeline_path 'ok\nsub\\evil.json' True dto true
assets_registry_path 'ok\nsub/../evil.json' True dto true
assets_registry_path 'ok\nsub//evil.json' True dto true
assets_registry_path 'ok\nsub\\evil.json' True dto true

exec
/bin/zsh -lc "python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B; plan=_plan(segments=[] , total_frames=0, profile=_profile(audio=False)); base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"none\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility());
for x in ({\"fake\":{\"profile\":_profile(audio=False),\"sha256\":SHA_B,\"attachments\":{}}}, [{\"profile\":_profile(audio=False),\"sha256\":SHA_B,\"attachments\":{}}]):
 try: print(\"accepted\",assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])
 except Exception as e: print(\"rejected\",type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 123ms:
accepted {'fake': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}}
accepted [{'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}]

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import VideoArtifact; b=json.load(open(\"tests/core/rendering/fixtures/v1/result.json\"))[\"video\"]; s=json.load(open(\"astrid/core/rendering/schemas/v1/result.json\")); v=Draft7Validator(s[\"definitions\"][\"videoArtifact\"]); cases=(\"ok\\nsub/../evil.mp4\",\"ok\\nsub//evil.mp4\",\"ok\\nsub\\\\evil.mp4\");
for p in cases:
 x={**b,\"path\":p}; print(repr(p),\"schema\",v.is_valid(x),end=\" \");
 try: VideoArtifact.from_dict(x); print(\"dto true\")
 except Exception as e: print(\"dto false\",type(e).__name__)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 114ms:
Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/referencing/_core.py", line 276, in pointer
    contents = contents[segment]  # type: ignore[reportUnknownArgumentType]
               ~~~~~~~~^^^^^^^^^
KeyError: 'definitions'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 462, in _validate_reference
    resolved = self._resolver.lookup(ref)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/referencing/_core.py", line 690, in lookup
    return retrieved.value.pointer(pointer=fragment, resolver=resolver)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/referencing/_core.py", line 279, in pointer
    raise error from lookup_error
referencing.exceptions.PointerToNowhere: '/definitions/workspacePath' does not exist within {'type': 'object', 'additionalProperties': False, 'required': ['path', 'profile', 'sha256', 'duration_frames'], 'properties': {'path': {'$ref': '#/definitions/workspacePath'}, 'profile': {'$ref': '#/definitions/renderProfile'}, 'sha256': {'$ref': '#/definitions/sha256'}, 'duration_frames': {'type': 'integer', 'minimum': 1}, 'audio': {'anyOf': [{'$ref': '#/definitions/audioOwnership'}, {'type': 'null'}]}, 'attachments': {'$ref': '#/definitions/attachments'}}, 'allOf': [{'if': {'properties': {'profile': {'required': ['audio_codec'], 'properties': {'audio_codec': {'type': 'string', 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}}}}, 'then': {'required': ['audio'], 'properties': {'audio': {'const': 'rendered'}}}, 'else': {'properties': {'audio': {'enum': ['passthrough', 'none', None]}}}}]}

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "<string>", line 3, in <module>
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 499, in is_valid
    error = next(self.iter_errors(instance), None)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 383, in iter_errors
    for error in errors:
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/_keywords.py", line 296, in properties
    yield from validator.descend(
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 431, in descend
    for error in errors:
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/_keywords.py", line 275, in ref
    yield from validator._validate_reference(ref=ref, instance=instance)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/jsonschema/validators.py", line 464, in _validate_reference
    raise exceptions._WrappedReferencingError(err) from err
jsonschema.exceptions._WrappedReferencingError: PointerToNowhere: '/definitions/workspacePath' does not exist within {'type': 'object', 'additionalProperties': False, 'required': ['path', 'profile', 'sha256', 'duration_frames'], 'properties': {'path': {'$ref': '#/definitions/workspacePath'}, 'profile': {'$ref': '#/definitions/renderProfile'}, 'sha256': {'$ref': '#/definitions/sha256'}, 'duration_frames': {'type': 'integer', 'minimum': 1}, 'audio': {'anyOf': [{'$ref': '#/definitions/audioOwnership'}, {'type': 'null'}]}, 'attachments': {'$ref': '#/definitions/attachments'}}, 'allOf': [{'if': {'properties': {'profile': {'required': ['audio_codec'], 'properties': {'audio_codec': {'type': 'string', 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}}}}, 'then': {'required': ['audio'], 'properties': {'audio': {'const': 'rendered'}}}, 'else': {'properties': {'audio': {'enum': ['passthrough', 'none', None]}}}}]}

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import parse_wire_result; b=json.load(open(\"tests/core/rendering/fixtures/v1/result.json\")); v=Draft7Validator(json.load(open(\"astrid/core/rendering/schemas/v1/result.json\"))); cases=(\"ok\\nsub/../evil.mp4\",\"ok\\nsub//evil.mp4\",\"ok\\nsub\\\\evil.mp4\");
for p in cases:
 x=json.loads(json.dumps(b)); x[\"video\"][\"path\"]=p; print(repr(p),\"schema\",v.is_valid(x),end=\" \");
 try: parse_wire_result(x); print(\"dto true\")
 except Exception as e: print(\"dto false\",type(e).__name__)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 111ms:
'ok\nsub/../evil.mp4' schema True dto false RendererProtocolError
'ok\nsub//evil.mp4' schema True dto false RendererProtocolError
'ok\nsub\\evil.mp4' schema True dto false RendererProtocolError

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import FinalizeRequest; b=json.load(open(\"tests/core/rendering/fixtures/v1/finalize.json\")); v=Draft7Validator(json.load(open(\"astrid/core/rendering/schemas/v1/finalize.json\"))); cases=(\"ok\\nsub/../evil.mp4\",\"ok\\nsub//evil.mp4\",\"ok\\nsub\\\\evil.mp4\");
for p in cases:
 x=json.loads(json.dumps(b)); x[\"artifacts\"][0][\"path\"]=p; print(repr(p),\"schema\",v.is_valid(x),end=\" \");
 try: FinalizeRequest.from_dict(x); print(\"dto true\")
 except Exception as e: print(\"dto false\",type(e).__name__)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 115ms:
'ok\nsub/../evil.mp4' schema True dto false RendererProtocolError
'ok\nsub//evil.mp4' schema True dto false RendererProtocolError
'ok\nsub\\evil.mp4' schema True dto false RendererProtocolError

exec
/bin/zsh -lc "python3 -c 'import json; from jsonschema import Draft7Validator; from astrid.core.rendering.contracts import SupportReport; b=json.load(open(\"tests/core/rendering/fixtures/v1/support.json\")); v=Draft7Validator(json.load(open(\"astrid/core/rendering/schemas/v1/support.json\")));
for val in (\"   \",\"\\n\\t\",\"ok\\n\\x00bad\"):
 x=json.loads(json.dumps(b)); x[\"features\"]={\"key\":val}; print(repr(val),\"schema\",v.is_valid(x),end=\" \");
 try: SupportReport.from_dict(x); print(\"dto true\")
 except Exception as e: print(\"dto false\",type(e).__name__)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 127ms:
'   ' schema True dto true
'\n\t' schema True dto true
'ok\n\x00bad' schema True dto true

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/plan.json | sed -n '344,365p' && nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '312,334p' && nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '18,30p' && nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '61,72p' && nl -ba astrid/core/rendering/provenance.py | sed -n '84,205p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   344	        "reasons": {
   345	          "type": "array",
   346	          "items": {
   347	            "type": "string",
   348	            "minLength": 1,
   349	            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   350	          }
   351	        },
   352	        "features": {
   353	          "type": "object",
   354	          "additionalProperties": {
   355	            "type": [
   356	              "boolean",
   357	              "string"
   358	            ]
   359	          }
   360	        },
   361	        "alternatives": {
   362	          "type": "array",
   363	          "uniqueItems": true,
   364	          "items": {
   365	            "$ref": "#/definitions/qualifiedId"
   312	        "reasons": {
   313	          "type": "array",
   314	          "items": {
   315	            "type": "string",
   316	            "minLength": 1,
   317	            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   318	          }
   319	        },
   320	        "features": {
   321	          "type": "object",
   322	          "additionalProperties": {
   323	            "type": [
   324	              "boolean",
   325	              "string"
   326	            ]
   327	          }
   328	        },
   329	        "alternatives": {
   330	          "type": "array",
   331	          "uniqueItems": true,
   332	          "items": {
   333	            "$ref": "#/definitions/qualifiedId"
   334	          }
    18	    "sha256": {
    19	      "type": "string",
    20	      "pattern": "^[0-9a-f]{64}$"
    21	    },
    22	    "workspacePath": {
    23	      "type": "string",
    24	      "minLength": 1,
    25	      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
    26	    },
    27	    "portableName": {
    28	      "type": "string",
    29	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
    30	      "not": {
    61	    "sha256": {
    62	      "type": "string",
    63	      "pattern": "^[0-9a-f]{64}$"
    64	    },
    65	    "workspacePath": {
    66	      "type": "string",
    67	      "minLength": 1,
    68	      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
    69	    },
    70	    "portableName": {
    71	      "type": "string",
    72	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
    84	
    85	
    86	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
    87	    if value is None:
    88	        value = {}
    89	    if isinstance(value, Mapping):
    90	        result: dict[str, Any] = {}
    91	        for key, profile in value.items():
    92	            path = _require_string(str(key), "artifact key")
    93	            if isinstance(profile, VideoArtifact):
    94	                if path != profile.path:
    95	                    raise ValueError(
    96	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
    97	                        f"{profile.path!r}"
    98	                    )
    99	                result[path] = _artifact_lineage(profile)
   100	            elif isinstance(profile, Mapping):
   101	                result[path] = _artifact_lineage_from_mapping(profile, key=path)
   102	            else:
   103	                raise TypeError(
   104	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   105	                    "hashed lineage record {profile, sha256, attachments}; "
   106	                    "profile-only entries carry no output hash"
   107	                )
   108	        # A positive plan must record a hashed artifact for every segment.
   109	        if segments and not result:
   110	            raise ValueError(
   111	                "artifact_profiles must record a hashed lineage entry for every "
   112	                "segment of a positive render plan"
   113	            )
   114	        return result
   115	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   116	        lineage = [
   117	            (
   118	                _artifact_lineage(profile)
   119	                if isinstance(profile, VideoArtifact)
   120	                else _artifact_lineage_from_mapping(profile, key=str(profile.get("path", "")))
   121	            )
   122	            for profile in value
   123	        ]
   124	        if segments and not lineage:
   125	            raise ValueError(
   126	                "artifact_profiles must record a hashed lineage entry for every "
   127	                "segment of a positive render plan"
   128	            )
   129	        return lineage
   130	    raise TypeError("artifact_profiles must be an object or array")
   131	
   132	
   133	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   134	    raw_keys = set(raw)
   135	    allowed = {"profile", "sha256", "attachments"}
   136	    unknown = sorted(raw_keys - allowed)
   137	    if unknown:
   138	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   139	    missing = sorted(allowed - raw_keys)
   140	    if missing:
   141	        raise ValueError(
   142	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   143	        )
   144	    if raw["sha256"] is None:
   145	        raise ValueError("artifact lineage sha256 is required and must not be null")
   146	    if not isinstance(raw["sha256"], str):
   147	        raise TypeError("artifact lineage sha256 must be a string")
   148	    profile = raw["profile"]
   149	    attachments: dict[str, Any] = {}
   150	    raw_attachments = raw["attachments"]
   151	    if raw_attachments is None:
   152	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   153	    if not isinstance(raw_attachments, Mapping):
   154	        raise TypeError("artifact lineage attachments must be an object")
   155	    for name, att in raw_attachments.items():
   156	        name = _require_string(name, "attachment name")
   157	        if isinstance(att, Attachment):
   158	            att = {
   159	                "path": att.path,
   160	                "kind": att.kind,
   161	                "sha256": att.sha256,
   162	            }
   163	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   164	        if att_unknown:
   165	            raise ValueError(
   166	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   167	            )
   168	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   169	        if att_missing:
   170	            raise ValueError(
   171	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   172	            )
   173	        if not isinstance(att["sha256"], str):
   174	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   175	        attachments[name] = {
   176	            "path": _require_string(att["path"], f"attachment {name!r} path"),
   177	            "kind": _require_string(att["kind"], f"attachment {name!r} kind"),
   178	            "sha256": _require_sha256(att["sha256"], f"attachment {name!r} sha256"),
   179	        }
   180	    return {
   181	        "profile": (
   182	            profile
   183	            if isinstance(profile, RenderProfile)
   184	            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
   185	        ).to_dict(),
   186	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   187	        "attachments": attachments,
   188	    }
   189	
   190	
   191	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   192	    """One hashed artifact lineage record: profile, sha256, attachments."""
   193	    return _artifact_lineage_from_mapping(
   194	        {
   195	            "profile": artifact.profile,
   196	            "sha256": artifact.sha256,
   197	            "attachments": artifact.attachments,
   198	        },
   199	        key=artifact.path,
   200	    )
   201	
   202	
   203	def _normalize_v1_compatibility(
   204	    fields: Mapping[str, Any] | None,
   205	) -> dict[str, Any]:

2026-08-12T01:48:41.958356Z ERROR codex_core::tools::router: error=timeout_ms must be at least 10000
collab: Wait
exec
/bin/zsh -lc "python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B; base=dict(engine=\"hybrid\",output=\"/workspace/out/video.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=_plan(),audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility()); cases=(\"../evil.dat\",\"x//evil.dat\",\"x\\\\evil.dat\",\" \");
for p in cases:
 x={\"out/v.mp4\":{\"profile\":_profile(),\"sha256\":SHA_B,\"attachments\":{\"a\":{\"path\":p,\"kind\":\"UPPER_bad\",\"sha256\":SHA_B}}}};
 try: print(repr(p),\"accepted\",assemble_provenance_v2(**base,artifact_profiles=x)[\"artifact_profiles\"])
 except Exception as e: print(repr(p),\"rejected\",type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 201ms:
'../evil.dat' accepted {'out/v.mp4': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {'a': {'path': '../evil.dat', 'kind': 'UPPER_bad', 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}}}}
'x//evil.dat' accepted {'out/v.mp4': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {'a': {'path': 'x//evil.dat', 'kind': 'UPPER_bad', 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}}}}
'x\\evil.dat' accepted {'out/v.mp4': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {'a': {'path': 'x\\evil.dat', 'kind': 'UPPER_bad', 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}}}}
' ' rejected ValueError attachment 'a' path must not be empty

exec
/bin/zsh -lc "nl -ba tests/core/rendering/fixtures/v1/finalize.json | sed -n '1,220p' | tail -n 90 && rg -n \"len\\(artifacts\\)|plan.segments|one-for-one|artifacts.*segments\" astrid/core/rendering/contracts.py tests/core/rendering | sed -n '1,220p' && nl -ba astrid/core/rendering/contracts.py | sed -n '1600,1760p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    56	        "input_hashes": {
    57	          "timeline": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    58	        }
    59	      }
    60	    ],
    61	    "finalizer": {
    62	      "id": "rendering.ffmpeg-finalizer",
    63	      "source_pack": {
    64	        "id": "rendering"
    65	      },
    66	      "manifest_digest": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    67	      "alias_chain": [],
    68	      "override": null,
    69	      "trust_eligibility": {
    70	        "eligible": true,
    71	        "method": "source-tree"
    72	      },
    73	      "support_decision": {
    74	        "schema_version": 1,
    75	        "supported": true,
    76	        "reasons": [],
    77	        "features": {},
    78	        "alternatives": [],
    79	        "backend": "rendering.ffmpeg-finalizer",
    80	        "backend_version": null
    81	      }
    82	    },
    83	    "profile": {
    84	      "width": 1280,
    85	      "height": 720,
    86	      "fps_rational": [
    87	        24,
    88	        1
    89	      ],
    90	      "time_base": [
    91	        1,
    92	        12288
    93	      ],
    94	      "container": "mp4",
    95	      "video_codec": "h264",
    96	      "video_profile": null,
    97	      "video_level": null,
    98	      "pixel_format": "yuv420p",
    99	      "audio_codec": null,
   100	      "audio_sample_rate": null,
   101	      "audio_channel_layout": null,
   102	      "duration_tolerance": 1
   103	    },
   104	    "total_frames": 1,
   105	    "reasons": {
   106	      "0": "visual-only fixture"
   107	    },
   108	    "window": null
   109	  },
   110	  "artifacts": [
   111	    {
   112	      "path": "segments/visual.mp4",
   113	      "profile": {
   114	        "width": 1280,
   115	        "height": 720,
   116	        "fps_rational": [
   117	          24,
   118	          1
   119	        ],
   120	        "time_base": [
   121	          1,
   122	          12288
   123	        ],
   124	        "container": "mp4",
   125	        "video_codec": "h264",
   126	        "video_profile": null,
   127	        "video_level": null,
   128	        "pixel_format": "yuv420p",
   129	        "audio_codec": null,
   130	        "audio_sample_rate": null,
   131	        "audio_channel_layout": null,
   132	        "duration_tolerance": 1
   133	      },
   134	      "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
   135	      "duration_frames": 1,
   136	      "audio": "none",
   137	      "attachments": {}
   138	    }
   139	  ],
   140	  "output_name": "video.mp4",
   141	  "backend_config": {
   142	    "rendering.ffmpeg-finalizer": {}
   143	  },
   144	  "metadata": {}
   145	}
astrid/core/rendering/contracts.py:1434:                raise ValueError("plan segments leave a trailing gap")
astrid/core/rendering/contracts.py:1719:        if len(artifacts) != len(plan.segments):
astrid/core/rendering/contracts.py:1720:            raise ValueError("finalize artifacts must correspond one-for-one with plan segments")
tests/core/rendering/test_contracts.py:452:    plan = _plan(segments=[_segment(0, 24), _segment(24, 48)])
tests/core/rendering/test_contracts.py:469:    plan = _plan(segments=[_segment(0, 24), _segment(24, 48)])
tests/core/rendering/test_contracts.py:589:    assert payload["segments_v2"] == [segment.to_dict() for segment in plan.segments]
tests/core/rendering/test_contracts.py:876:        _plan(segments=segments, total_frames=total_frames)
tests/core/rendering/test_contracts.py:881:        _plan(segments=[_segment(fps=(48, 2))])
tests/core/rendering/test_contracts.py:887:    empty = _plan(segments=[], total_frames=0, profile=_profile(audio=False))
tests/core/rendering/test_contracts.py:891:        _plan(segments=[_segment()], total_frames=0)
tests/core/rendering/test_contracts.py:893:        _plan(segments=[], total_frames=48)
  1600	                raise
  1601	            _protocol_failure(
  1602	                f"malformed render result: {exc}",
  1603	                details={"error_type": type(exc).__name__},
  1604	            )
  1605	
  1606	
  1607	@dataclass(frozen=True)
  1608	class RendererError:
  1609	    """Language-neutral structured renderer failure payload."""
  1610	
  1611	    schema_version: int
  1612	    kind: RendererErrorKind
  1613	    backend: str
  1614	    message: str
  1615	    recovery_command: str | None = None
  1616	    details: dict[str, Any] = field(default_factory=dict)
  1617	
  1618	    KINDS: ClassVar[frozenset[str]] = frozenset(
  1619	        {
  1620	            "protocol",
  1621	            "unsupported",
  1622	            "binary_missing",
  1623	            "timeout",
  1624	            "interrupted",
  1625	            "invalid_artifact",
  1626	            "internal",
  1627	        }
  1628	    )
  1629	
  1630	    def __post_init__(self) -> None:
  1631	        object.__setattr__(
  1632	            self,
  1633	            "schema_version",
  1634	            _require_schema_version(self.schema_version, "renderer error"),
  1635	        )
  1636	        kind = _require_string(self.kind, "renderer error kind")
  1637	        if kind not in self.KINDS:
  1638	            raise ValueError(f"unknown renderer error kind: {kind}")
  1639	        object.__setattr__(self, "kind", kind)
  1640	        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "error backend"))
  1641	        object.__setattr__(self, "message", _require_string(self.message, "error message"))
  1642	        object.__setattr__(
  1643	            self,
  1644	            "recovery_command",
  1645	            _require_optional_string(self.recovery_command, "recovery_command"),
  1646	        )
  1647	        object.__setattr__(self, "details", _json_safe_mapping(self.details, label="error details"))
  1648	
  1649	    def to_dict(self) -> dict[str, Any]:
  1650	        return _json_safe_mapping(
  1651	            {
  1652	                "schema_version": self.schema_version,
  1653	                "kind": self.kind,
  1654	                "backend": self.backend,
  1655	                "message": self.message,
  1656	                "recovery_command": self.recovery_command,
  1657	                "details": self.details,
  1658	            }
  1659	        )
  1660	
  1661	    @classmethod
  1662	    def from_dict(cls, payload: Mapping[str, Any]) -> RendererError:
  1663	        try:
  1664	            data = _require_mapping(payload, "renderer error")
  1665	            required = {
  1666	                "schema_version",
  1667	                "kind",
  1668	                "backend",
  1669	                "message",
  1670	                "recovery_command",
  1671	                "details",
  1672	            }
  1673	            _validate_object_keys(data, required=required, allowed=required, label="renderer error")
  1674	            return cls(
  1675	                schema_version=data["schema_version"],
  1676	                kind=data["kind"],
  1677	                backend=data["backend"],
  1678	                message=data["message"],
  1679	                recovery_command=data["recovery_command"],
  1680	                details=data["details"],
  1681	            )
  1682	        except Exception as exc:
  1683	            from .errors import RendererException
  1684	
  1685	            if isinstance(exc, RendererException):
  1686	                raise
  1687	            _protocol_failure(
  1688	                f"malformed renderer error: {exc}",
  1689	                details={"error_type": type(exc).__name__},
  1690	            )
  1691	
  1692	
  1693	@dataclass(frozen=True)
  1694	class FinalizeRequest:
  1695	    """Wire request consumed by the ``finalize`` operation."""
  1696	
  1697	    schema_version: int
  1698	    plan: RenderPlan
  1699	    artifacts: list[VideoArtifact]
  1700	    output_name: str
  1701	    backend_config: BackendConfig = field(default_factory=dict)
  1702	    metadata: dict[str, str] = field(default_factory=dict)
  1703	
  1704	    def __post_init__(self) -> None:
  1705	        version = _require_schema_version(self.schema_version, "finalize request")
  1706	        plan = (
  1707	            self.plan
  1708	            if isinstance(self.plan, RenderPlan)
  1709	            else RenderPlan.from_dict(_require_mapping(self.plan, "plan"))
  1710	        )
  1711	        if isinstance(self.artifacts, (str, bytes)) or not isinstance(self.artifacts, Sequence):
  1712	            raise TypeError("artifacts must be an array")
  1713	        artifacts = [
  1714	            artifact
  1715	            if isinstance(artifact, VideoArtifact)
  1716	            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
  1717	            for index, artifact in enumerate(self.artifacts)
  1718	        ]
  1719	        if len(artifacts) != len(plan.segments):
  1720	            raise ValueError("finalize artifacts must correspond one-for-one with plan segments")
  1721	        if plan.total_frames == 0:
  1722	            raise ValueError("an empty render plan must not be finalized")
  1723	        attachment_names: set[str] = set()
  1724	        for index, artifact in enumerate(artifacts):
  1725	            duplicates = sorted(attachment_names & set(artifact.attachments))
  1726	            if duplicates:
  1727	                raise ValueError(
  1728	                    "duplicate attachment names across segment artifacts at "
  1729	                    f"artifacts[{index}]: {', '.join(duplicates)}"
  1730	                )
  1731	            attachment_names.update(artifact.attachments)
  1732	        output_name = _require_string(self.output_name, "output_name")
  1733	        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
  1734	            raise ValueError("output_name must be a portable basename without path separators")
  1735	        object.__setattr__(self, "schema_version", version)
  1736	        object.__setattr__(self, "plan", plan)
  1737	        object.__setattr__(self, "artifacts", artifacts)
  1738	        object.__setattr__(self, "output_name", output_name)
  1739	        backend_config = _coerce_namespaced_backend_config(
  1740	            self.backend_config,
  1741	            "backend_config",
  1742	        )
  1743	        unexpected_config = sorted(set(backend_config) - {plan.finalizer.id})
  1744	        if unexpected_config:
  1745	            raise ValueError(
  1746	                "finalize backend_config may contain only the selected finalizer namespace "
  1747	                f"{plan.finalizer.id!r}"
  1748	            )
  1749	        object.__setattr__(self, "backend_config", backend_config)
  1750	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
  1751	
  1752	    @property
  1753	    def expected_attachments(self) -> dict[str, Attachment]:
  1754	        """Return the globally unique attachments a finalizer must preserve."""
  1755	
  1756	        return {
  1757	            name: attachment
  1758	            for artifact in self.artifacts
  1759	            for name, attachment in artifact.attachments.items()
  1760	        }

exec
/bin/zsh -lc "rg -n \"def _json_safe_mapping|def _json_safe|is_dataclass\" astrid/core/rendering/contracts.py | sed -n '1,120p' && nl -ba astrid/core/rendering/contracts.py | sed -n '120,190p' && python3 -c 'from astrid.core.rendering.provenance import assemble_provenance_v2; from tests.core.rendering.test_contracts import _plan,_profile,_compatibility,SHA_B; base=dict(engine=\"hybrid\",output=\"o\",timeline=\"t\",assets_registry=None,plan=_plan(),audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=_compatibility()); cases=({\"out\":{\"profile\":_profile(),\"sha256\":SHA_B,\"attachments\":{\"a\":7}}},{\"out\":{\"profile\":_profile(),\"sha256\":SHA_B,\"attachments\":{7:{\"path\":\"x\",\"kind\":\"alpha\",\"sha256\":SHA_B}}}});
for x in cases:
 try: print(assemble_provenance_v2(**base,artifact_profiles=x))
 except Exception as e: print(type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 191ms:
TypeError 'int' object is not iterable
TypeError attachment name must be a string

collab: Wait
exec
/bin/zsh -lc "rg -n '\"workspacePath\"' astrid/core/rendering/schemas/v1/*.json && rg -n '\"supportReport\"' astrid/core/rendering/schemas/v1/*.json && rg -n '\"hashMap\"' astrid/core/rendering/schemas/v1/*.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
astrid/core/rendering/schemas/v1/plan.json:324:    "supportReport": {
astrid/core/rendering/schemas/v1/finalize.json:292:    "supportReport": {
astrid/core/rendering/schemas/v1/plan.json:538:    "hashMap": {
astrid/core/rendering/schemas/v1/finalize.json:506:    "hashMap": {

exec
/bin/zsh -lc "nl -ba .oracle/tasklist.md | sed -n '1,45p;174,190p' && git show 086d692:tests/core/rendering/test_contracts.py | nl -ba | sed -n '550,580p;800,850p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   174	- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
   175	- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
   176	- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
   177	- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
   178	- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
   179	- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
   572	            }
   573	        },
   574	        "audio_ownership": AudioOwnership.RENDERED,
   575	        "normalization": [],
   576	        "attachments": {},
   577	        "backend_fragments": {"acme.first": {"vendor": "Acme"}},
   578	        "v1_compatibility": compatibility,
   579	    }
   580	    payload = assemble_provenance_v2(**kwargs)
   800	
   801	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   802	    """Artifact lineage must carry a real sha256; profile-only entries and
   803	    null hashes are rejected rather than stringified."""
   804	    base = dict(
   805	        engine="hybrid",
   806	        output="/workspace/out/video.mp4",
   807	        timeline="/workspace/timeline.json",
   808	        assets_registry=None,
   809	        plan=_plan(),
   810	        audio_ownership="rendered",
   811	        normalization=[],
   812	        attachments={},
   813	        backend_fragments={},
   814	        v1_compatibility=_compatibility(),
   815	    )
   816	    with pytest.raises(TypeError, match="hashed lineage"):
   817	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
   818	    with pytest.raises(ValueError, match="sha256"):
   819	        assemble_provenance_v2(
   820	            **base,
   821	            artifact_profiles={
   822	                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
   823	            },
   824	        )
   825	    with pytest.raises(ValueError, match="sha256"):
   826	        assemble_provenance_v2(
   827	            **base,
   828	            artifact_profiles={
   829	                "out/v.mp4": {
   830	                    "profile": _profile(),
   831	                    "sha256": "not-a-hash",
   832	                    "attachments": {},
   833	                }
   834	            },
   835	        )
   836	    with pytest.raises(ValueError, match="unknown fields"):
   837	        assemble_provenance_v2(
   838	            **base,
   839	            artifact_profiles={
   840	                "out/v.mp4": {
   841	                    "profile": _profile(),
   842	                    "sha256": SHA_B,
   843	                    "attachments": {},
   844	                    "spoof": 1,
   845	                }
   846	            },
   847	        )
   848	
   849	
   850	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:

collab: Wait
exec
/bin/zsh -lc "rg -n \"artifact_profiles|artifact profile|per-artifact|per-segment.*hash|output.*hash\" .oracle/plan.md .oracle/baseline.md .megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md .oracle/briefs/batch-1-r2-t1.2.md 2>/dev/null | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/plan.md:39:10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.
.oracle/plan.md:151:  - Add renderer-local artifact enforcement for existence, non-empty output, workspace containment, symlinks, hashes, duration, video profile, and audio ownership.
.oracle/plan.md:361:  - Provide allocated output/work paths, descriptor-based local path/URL access, declared-permission checks, sanitized subprocess execution, redacted logging/progress, read-only interruption state, probing, hashing, completion, attachments, and cleanup.

exec
/bin/zsh -lc 'git log --oneline --all -- astrid/core/rendering/provenance.py | head -20 && git show 91f0fe3''^:astrid/core/rendering/provenance.py 2>/dev/null | sed -n '"'70,155p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 68ms:
086d692 batch1-rework6: oracle re-review5 issues 1-3 (lineage required+shape-bound+path-bound, NUL-after-newline, hashMap/feature propertyNames, workspacePath newlines)
91f0fe3 batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
88c75f3 batch1-rework2: oracle re-review issues 1-5 (real-fixture deconcealment, underscore-compatible ids, provenance v1 preservation + v2 additive, whitespace parity, transitive override routing, baseline C0 evidence)
b357de3 batch1-rework: oracle issues 1-9 (baseline facade ownership, contracts versioning/attachments/provenance, pack validation, transitive alias eligibility)
f8af4b2 batch1: renderer contracts, schemas, pack extension, trusted registries, baseline characterization
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


def _normalize_artifact_profiles(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, profile in value.items():
            path = _require_string(str(key), "artifact key")
            if isinstance(profile, VideoArtifact):
                result[path] = _artifact_lineage(profile)
            elif isinstance(profile, Mapping) and "profile" in profile and "sha256" in profile:
                raw = _json_safe_mapping(profile, label="artifact")
                attachments = {
                    name: {
                        "path": str(att.get("path")),
                        "kind": str(att.get("kind")),
                        "sha256": str(att.get("sha256")),
                    }
                    for name, att in (raw.get("attachments") or {}).items()
                }
                result[path] = {
                    "profile": (
                        raw["profile"]
                        if isinstance(raw["profile"], RenderProfile)
                        else RenderProfile.from_dict(
                            _json_safe_mapping(raw["profile"], label="artifact profile")
                        )
                    ).to_dict(),
                    "sha256": str(raw["sha256"]),
                    "attachments": attachments,
                }
            else:
                result[path] = (
                    profile
                    if isinstance(profile, RenderProfile)
                    else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
                ).to_dict()
        return result
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            (
                profile
                if isinstance(profile, RenderProfile)
                else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
            ).to_dict()
            for profile in value
        ]
    raise TypeError("artifact_profiles must be an object or array")


def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
    """One hashed artifact lineage record: profile, sha256, attachments."""
    return {
        "profile": artifact.profile.to_dict(),
        "sha256": artifact.sha256,
        "attachments": {
            name: {
                "path": attachment.path,
                "kind": attachment.kind,
                "sha256": attachment.sha256,
            }
            for name, attachment in artifact.attachments.items()
        },
    }


def _normalize_v1_compatibility(
    fields: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if fields is None:
        raise ValueError(
            "v1_compatibility is required and must preserve all always-emitted v1 fields"

codex
1. **Artifact lineage remains unbound.** A two-segment plan still accepts one lineage entry, and sequence form discards `VideoArtifact.path` into anonymous records. Require a unique path-keyed entry per segment and reject cardinality mismatches. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:108) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:555)

2. **Attachment lineage still bypasses the `Attachment` contract.** Raw lineage accepts traversal paths and invalid kinds; mutated `Attachment` values whose `name` differs from the map key are silently relabeled when `name` is stripped. Validate workspace path, kind grammar, and key/name equality before emitting the three-field projection. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:155)

3. **Schema/DTO parity remains false.**

   - Embedded `supportReport.features` in plan/finalize still lacks `propertyNames`, so blank/NUL keys pass schema but fail DTO validation. [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:352) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:320)
   - `workspacePath` enables newlines but retains `.*` in containment lookaheads. Thus `ok\nsub/../evil.mp4`, double slashes, and backslashes after a newline pass result/finalize schemas while the DTO rejects them. Use `[\s\S]*` in every full-string lookahead and add multiline traversal cases. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:65)
tokens used
325,515
1. **Artifact lineage remains unbound.** A two-segment plan still accepts one lineage entry, and sequence form discards `VideoArtifact.path` into anonymous records. Require a unique path-keyed entry per segment and reject cardinality mismatches. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:108) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:555)

2. **Attachment lineage still bypasses the `Attachment` contract.** Raw lineage accepts traversal paths and invalid kinds; mutated `Attachment` values whose `name` differs from the map key are silently relabeled when `name` is stripped. Validate workspace path, kind grammar, and key/name equality before emitting the three-field projection. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:155)

3. **Schema/DTO parity remains false.**

   - Embedded `supportReport.features` in plan/finalize still lacks `propertyNames`, so blank/NUL keys pass schema but fail DTO validation. [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:352) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:320)
   - `workspacePath` enables newlines but retains `.*` in containment lookaheads. Thus `ok\nsub/../evil.mp4`, double slashes, and backslashes after a newline pass result/finalize schemas while the DTO rejects them. Use `[\s\S]*` in every full-string lookahead and add multiline traversal cases. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:65)
