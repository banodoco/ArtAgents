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

codex
The checkpoint skill reinforces a binary gate and a rework-until-clean standard. Because the cumulative delta is large, I’m splitting independent closure checks while I personally audit the full diff and integration surface; only evidence-backed findings will make the verdict.
exec
/bin/zsh -lc "sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc "sed -n '1,340p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

2026-08-12T01:24:42.760298Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:42.760325Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:42.760329Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:47.370022Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:47.370058Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:47.370063Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:52.447168Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:52.447211Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:24:52.447218Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show -s --format='%H %P %s' HEAD && git diff --stat 808030e..91f0fe3 && git diff --name-status C1..HEAD 2>&1 | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r5.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
91f0fe3f1d416aba0dce5396fb60cf05fb1378fe
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
91f0fe3f1d416aba0dce5396fb60cf05fb1378fe 808030e1182c795ce345df3ea0cb619fd3bf9d23 batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r4.md                     | 39145 +++++++++++++++++++
 astrid/core/rendering/contracts.py                 |    39 +-
 astrid/core/rendering/provenance.py                |    66 +-
 astrid/core/rendering/schemas/v1/finalize.json     |    70 +-
 .../rendering/schemas/v1/finalizer-manifest.json   |    22 +-
 astrid/core/rendering/schemas/v1/plan.json         |    62 +-
 .../rendering/schemas/v1/planner-manifest.json     |    22 +-
 .../rendering/schemas/v1/renderer-manifest.json    |    26 +-
 astrid/core/rendering/schemas/v1/request.json      |    28 +-
 astrid/core/rendering/schemas/v1/result.json       |    32 +-
 astrid/core/rendering/schemas/v1/support.json      |     4 +-
 docs/contracts/render-backend-v1.md                |    28 +-
 tests/core/rendering/test_contracts.py             |    60 +-
 tests/core/rendering/test_registry_matrix.py       |    52 +-
 14 files changed, 39483 insertions(+), 173 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	.oracle/baseline.md
A	.oracle/briefs/batch-1-r1-t1.1.md
A	.oracle/briefs/batch-1-r1-t1.2.md
A	.oracle/briefs/batch-1-r1-t1.3.md
A	.oracle/briefs/batch-1-r1-t1.4.md
A	.oracle/briefs/batch-1-r2-t1.1.md
A	.oracle/briefs/batch-1-r2-t1.2.md
A	.oracle/checkins/batch-1-r1.md
A	.oracle/checkins/batch-1-r2.md
A	.oracle/checkins/batch-1-r3.md
A	.oracle/checkins/batch-1-r4.md
A	.oracle/checkins/batch-1.md
M	astrid/core/pack/schemas/v1/pack.json
M	astrid/core/pack/validate.py
M	astrid/core/rendering/contracts.py
M	astrid/core/rendering/errors.py
M	astrid/core/rendering/provenance.py
M	astrid/core/rendering/registry.py
M	astrid/core/rendering/schemas/v1/finalize.json
M	astrid/core/rendering/schemas/v1/finalizer-manifest.json
M	astrid/core/rendering/schemas/v1/plan.json
M	astrid/core/rendering/schemas/v1/planner-manifest.json
M	astrid/core/rendering/schemas/v1/renderer-manifest.json
M	astrid/core/rendering/schemas/v1/request.json
M	astrid/core/rendering/schemas/v1/result.json
M	astrid/core/rendering/schemas/v1/support.json
M	docs/contracts/render-backend-v1.md
A	tests/core/rendering/fixtures/v1/finalize.json
A	tests/core/rendering/fixtures/v1/plan.json
A	tests/core/rendering/fixtures/v1/request.json
A	tests/core/rendering/fixtures/v1/result.json
A	tests/core/rendering/fixtures/v1/support.json
M	tests/core/rendering/test_contracts.py
M	tests/core/rendering/test_registry.py
M	tests/core/rendering/test_registry_matrix.py
M	tests/core/rendering/test_schema_roundtrip.py
M	tests/fixtures/renderer_packs/discovery/source/rendering/manifests/ffmpeg.finalizer.yaml
M	tests/packs/rendering/test_legacy_renderer_characterization.py
A	tests/packs/rendering/test_render_facade_run_ownership.py
M	tests/packs/test_pack_rendering_extensions.py

exec
/bin/zsh -lc 'rg -n "''^(#|##|###|PASS$|[0-9]+'"\\.|- \\*\\*|Verdict|Issue|Issues|Acceptance|Batch 1)\" .oracle/checkins/batch-1.md .oracle/checkins/batch-1-r1.md .oracle/checkins/batch-1-r2.md .oracle/checkins/batch-1-r3.md .oracle/checkins/batch-1-r4.md .oracle/tasklist.md .oracle/status.md 2>/dev/null | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/tasklist.md:1:# Renderer Tasklist
.oracle/tasklist.md:3:## Batch 1 — Baseline, contracts, and discovery
.oracle/tasklist.md:18:### Tasks
.oracle/tasklist.md:26:## Batch 2 — Command protocol and host-owned plumbing
.oracle/tasklist.md:41:### Tasks
.oracle/tasklist.md:50:## Batch 3 — Built-in renderer and finalizer extraction
.oracle/tasklist.md:64:### Tasks
.oracle/tasklist.md:73:## Batch 4 — Generic routing, provenance, and hybrid planning
.oracle/tasklist.md:87:### Tasks
.oracle/tasklist.md:95:## Batch 5 — Caller migration, semantic parity, and M1 freeze
.oracle/tasklist.md:110:### Tasks
.oracle/tasklist.md:120:## Batch 6 — Python SDK, conformance, and scaffold
.oracle/tasklist.md:134:### Tasks
.oracle/tasklist.md:143:## Batch 7 — CLI, replay, documentation, and epic freeze
.oracle/tasklist.md:160:### Tasks
.oracle/tasklist.md:169:## Execution notes
.oracle/checkins/batch-1-r3.md:17:# Megado Checkpoint — Batch 1 third re-review
.oracle/checkins/batch-1-r3.md:26:## How each of your 3 re-review2 issues was addressed (host-implemented)
.oracle/checkins/batch-1-r3.md:28:1. **Provenance resolution and artifact lineage incomplete** →
.oracle/checkins/batch-1-r3.md:41:2. **Schema/DTO parity still false (nullable strings + segments_v2)** →
.oracle/checkins/batch-1-r3.md:49:3. **Statically invalid committed fixture** →
.oracle/checkins/batch-1-r3.md:56:## Evidence
.oracle/checkins/batch-1-r3.md:65:## Verdict
.oracle/checkins/batch-1-r3.md:85:# Megado
.oracle/checkins/batch-1-r3.md:91:1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
.oracle/checkins/batch-1-r3.md:92:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
.oracle/checkins/batch-1-r3.md:93:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
.oracle/checkins/batch-1-r3.md:94:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
.oracle/checkins/batch-1-r3.md:95:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
.oracle/checkins/batch-1-r3.md:96:6. Open it and sync.
.oracle/checkins/batch-1-r3.md:98:## Roles
.oracle/checkins/batch-1-r3.md:111:## Artifacts (in the worktree)
.oracle/checkins/batch-1-r3.md:123:## Phase 0 — Worktree
.oracle/checkins/batch-1-r3.md:133:## Phase 1 — Initial plan (Codex)
.oracle/checkins/batch-1-r3.md:137:1. A tasklist covering the **entirety** of the project (not just the obvious path).
.oracle/checkins/batch-1-r3.md:138:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
.oracle/checkins/batch-1-r3.md:139:3. Open questions / potential issues.
.oracle/checkins/batch-1-r3.md:148:## Phase 2 — Deep exploration (DeepSeek fan-out)
.oracle/checkins/batch-1-r3.md:161:## Phase 3 — Revise-until-stable loop
.oracle/checkins/batch-1-r3.md:171:## Phase 4 — Batched tasklist with checkpoints (Codex)
.oracle/checkins/batch-1-r3.md:175:- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
.oracle/checkins/batch-1-r3.md:176:- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
.oracle/checkins/batch-1-r3.md:177:- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
.oracle/checkins/batch-1-r3.md:178:- **Per-batch acceptance criteria** the oracle will verify.
.oracle/checkins/batch-1-r3.md:182:## Phase 5 — Execute, with oracle checkpoints
.oracle/checkins/batch-1-r3.md:214:## Phase 6 — Completion
.oracle/checkins/batch-1-r3.md:216:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
.oracle/checkins/batch-1-r3.md:217:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
.oracle/checkins/batch-1-r3.md:218:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
.oracle/checkins/batch-1-r3.md:220:## Gotchas
.oracle/checkins/batch-1-r3.md:222:- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
.oracle/checkins/batch-1-r3.md:223:- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
.oracle/checkins/batch-1-r3.md:224:- **Match brief shape to model mode.** Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs derived straight from the tasklist. Judgement (exploration, revision, oracle) stays at GPT-5.6 Sol; escalate Flash exploration to DeepSeek V4 Pro only on evidence.
.oracle/checkins/batch-1-r3.md:225:- **Liveness ≠ correctness.** Watch `fan.py` `.meta.json` files and the stderr `[tool]`/`[done]` heartbeat; check 30–60 s after launch, not 10 minutes in. But a live agent can still answer uselessly — read the response.
.oracle/checkins/batch-1-r3.md:226:- **Checkpoint discipline is the whole game.** The oracle gate is what makes quality; skipping it to "save a cycle" collapses this into a plain DeepSeek run.
.oracle/checkins/batch-1-r3.md:227:- **Elegance bias is a real instruction.** Codex's revision prompt must name it; otherwise reasoning models add scope, not subtract it.
.oracle/checkins/batch-1-r3.md:229:## Quick reference
.oracle/checkins/batch-1-r3.md:232:# Phase 0
.oracle/checkins/batch-1-r3.md:236:# Phase 1 — initial plan (GPT-5.6 Sol, max reasoning)
.oracle/checkins/batch-1-r3.md:239:# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
.oracle/checkins/batch-1-r3.md:245:# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
.oracle/checkins/batch-1-r3.md:246:# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [HARD] tags)
.oracle/checkins/batch-1-r3.md:248:# Phase 5 — execute (DeepSeek V4 Flash, one agent per batch)
.oracle/checkins/batch-1-r3.md:252:# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=max
.oracle/checkins/batch-1-r3.md:253:# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max "$(cat /tmp/checkin-brief.md)" </dev/null
.oracle/checkins/batch-1-r3.md:255:# Phase 6 — commit, push, open
.oracle/checkins/batch-1-r3.md:270:# Context Minning & Subagent Maxxing
.oracle/checkins/batch-1-r3.md:283:## Move 1 — Context minning: condense at the seams
.oracle/checkins/batch-1-r3.md:303:## Move 2 — Subagent maxxing: do the work elsewhere
.oracle/checkins/batch-1-r3.md:328:## The loop, in one line
.oracle/checkins/batch-1-r3.md:344:# Subagent launcher (multi-model)
.oracle/checkins/batch-1-r3.md:382:## Picking a pathway
.oracle/checkins/batch-1-r3.md:384:- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
.oracle/checkins/batch-1-r3.md:385:- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
.oracle/checkins/batch-1-r3.md:386:- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
.oracle/checkins/batch-1-r3.md:387:- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
.oracle/checkins/batch-1-r3.md:388:- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
.oracle/checkins/batch-1-r3.md:389:- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
.oracle/checkins/batch-1-r3.md:390:- **Already have the answer?** → don't dispatch. Subagents aren't free.
.oracle/checkins/batch-1-r3.md:392:## Use the cheapest subagent that can do the job
.oracle/checkins/batch-1-r3.md:396:1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
.oracle/checkins/batch-1-r3.md:397:2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
.oracle/checkins/batch-1-r3.md:398:3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
.oracle/checkins/batch-1-r3.md:399:4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.
.oracle/checkins/batch-1-r3.md:407:## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default
.oracle/checkins/batch-1-r3.md:419:# Final response → stdout; tool progress/timings → stderr.
.oracle/checkins/batch-1-r3.md:424:- **`--model`** (default `deepseek:deepseek-v4-pro`). Prefix convention from the megaplan key pool:
.oracle/checkins/batch-1-r3.md:430:- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
.oracle/checkins/batch-1-r3.md:431:- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
.oracle/checkins/batch-1-r3.md:432:- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
.oracle/checkins/batch-1-r3.md:433:- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
.oracle/checkins/batch-1-r3.md:434:- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
.oracle/checkins/batch-1-r3.md:435:- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
.oracle/checkins/batch-1-r3.md:436:- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.
.oracle/checkins/batch-1-r3.md:440:### Fan out N at once — `fan.py`
.oracle/checkins/batch-1-r3.md:449:# Or positional brief paths instead of --briefs-dir.
.oracle/checkins/batch-1-r3.md:450:# Per-brief models: --model-map="fast:scan-*.md,pro:verdict-*.md"
.oracle/checkins/batch-1-r3.md:455:### Use `megaplan` instead when you need
.oracle/checkins/batch-1-r3.md:459:### Liveness
.oracle/checkins/batch-1-r3.md:465:## 2. Codex (GPT-5.5)
.oracle/checkins/batch-1-r3.md:476:- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).
.oracle/checkins/batch-1-r3.md:478:## 3. Claude (Opus/Sonnet/Haiku)
.oracle/checkins/batch-1-r3.md:517:## Multi-phase delegation (when a single-turn agent isn't enough)
.oracle/checkins/batch-1-r3.md:524:# Kimi: --profile all-open
.oracle/checkins/batch-1-r3.md:529:## Writing the prompt (any pathway)
.oracle/checkins/batch-1-r3.md:543:## Judge / jury for high-stakes calls
.oracle/checkins/batch-1-r3.md:547:## Detecting hangs
.oracle/checkins/batch-1-r3.md:551:- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
.oracle/checkins/batch-1-r3.md:552:- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
.oracle/checkins/batch-1-r3.md:553:- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
.oracle/checkins/batch-1-r3.md:554:- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.
.oracle/checkins/batch-1-r3.md:558:## Quick reference
.oracle/checkins/batch-1-r3.md:561:# 1. Hermes agentic (default) — DeepSeek/Kimi/Zhipu GLM with tools
.oracle/checkins/batch-1-r3.md:565:# Very fast: --model=fast   Flash: --model="deepseek:deepseek-v4-flash"   Kimi: --model="kimi:kimi-k2.7-code"   GLM: --model="zhipu:glm-5.2"
.oracle/checkins/batch-1-r3.md:566:# Pure chat: --toolsets=""    Fan N≥5: fan.py --briefs-dir=… --output-dir=… --max-workers=5 --task-timeout=1800
.oracle/checkins/batch-1-r3.md:568:# 2. Codex — always seal stdin with </dev/null, allow 30 min
.oracle/checkins/batch-1-r3.md:574:# 3. Claude — explicit Opus selector via Claude CLI
.oracle/checkins/batch-1-r3.md:578:# Multi-phase: megaplan init --profile all-deepseek-pro-direct --robustness light "<task>"
.oracle/checkins/batch-1-r3.md:628:# Megado Checkpoint — Batch 1 review
.oracle/checkins/batch-1-r3.md:637:## Batch 1 tasks (from tasklist.md)
.oracle/checkins/batch-1-r3.md:645:## Acceptance criteria (from tasklist.md Batch 1)
.oracle/checkins/batch-1-r3.md:656:## Evidence to review
.oracle/checkins/batch-1-r3.md:665:## Your verdict
.oracle/checkins/batch-1-r3.md:687:# Megado
.oracle/checkins/batch-1-r3.md:693:1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
.oracle/checkins/batch-1-r3.md:694:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
.oracle/checkins/batch-1-r3.md:695:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
.oracle/checkins/batch-1-r3.md:696:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
.oracle/checkins/batch-1-r3.md:697:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
.oracle/checkins/batch-1-r3.md:698:6. Open it and sync.
.oracle/checkins/batch-1-r3.md:700:## Roles
.oracle/checkins/batch-1-r3.md:713:## Artifacts (in the worktree)
.oracle/checkins/batch-1-r3.md:725:## Phase 0 — Worktree
.oracle/checkins/batch-1-r3.md:735:## Phase 1 — Initial plan (Codex)
.oracle/checkins/batch-1-r3.md:739:1. A tasklist covering the **entirety** of the project (not just the obvious path).
.oracle/checkins/batch-1-r3.md:740:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
.oracle/checkins/batch-1-r3.md:741:3. Open questions / potential issues.
.oracle/checkins/batch-1-r3.md:750:## Phase 2 — Deep exploration (DeepSeek fan-out)
.oracle/checkins/batch-1-r3.md:763:## Phase 3 — Revise-until-stable loop
.oracle/checkins/batch-1-r3.md:773:## Phase 4 — Batched tasklist with checkpoints (Codex)
.oracle/checkins/batch-1-r3.md:777:- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
.oracle/checkins/batch-1-r3.md:778:- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
.oracle/checkins/batch-1-r3.md:779:- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
.oracle/checkins/batch-1-r3.md:780:- **Per-batch acceptance criteria** the oracle will verify.
.oracle/checkins/batch-1-r3.md:784:## Phase 5 — Execute, with oracle checkpoints
.oracle/checkins/batch-1-r3.md:816:## Phase 6 — Completion
.oracle/checkins/batch-1-r3.md:818:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
.oracle/checkins/batch-1-r3.md:819:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
.oracle/checkins/batch-1-r3.md:820:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
.oracle/checkins/batch-1-r3.md:822:## Gotchas
.oracle/checkins/batch-1-r3.md:824:- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
.oracle/checkins/batch-1-r3.md:825:- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
.oracle/checkins/batch-1-r3.md:826:- **Match brief shape to model mode.** Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs derived straight from the tasklist. Judgement (exploration, revision, oracle) stays at GPT-5.6 Sol; escalate Flash exploration to DeepSeek V4 Pro only on evidence.
.oracle/checkins/batch-1-r3.md:827:- **Liveness ≠ correctness.** Watch `fan.py` `.meta.json` files and the stderr `[tool]`/`[done]` heartbeat; check 30–60 s after launch, not 10 minutes in. But a live agent can still answer uselessly — read the response.
.oracle/checkins/batch-1-r3.md:828:- **Checkpoint discipline is the whole game.** The oracle gate is what makes quality; skipping it to "save a cycle" collapses this into a plain DeepSeek run.
.oracle/checkins/batch-1-r3.md:829:- **Elegance bias is a real instruction.** Codex's revision prompt must name it; otherwise reasoning models add scope, not subtract it.
.oracle/checkins/batch-1-r3.md:831:## Quick reference
.oracle/checkins/batch-1-r3.md:834:# Phase 0
.oracle/checkins/batch-1-r3.md:838:# Phase 1 — initial plan (GPT-5.6 Sol, max reasoning)
.oracle/checkins/batch-1-r3.md:841:# Phase 2 — exploration (DeepSeek V4 Flash, fan N areas)
.oracle/checkins/batch-1-r3.md:847:# Phase 3 — revise loop: repeat 2↔3 until Codex says STABLE
.oracle/checkins/batch-1-r3.md:848:# Phase 4 — Codex emits .oracle/tasklist.md (batches, checkpoints, [HARD] tags)
.oracle/checkins/batch-1-r3.md:850:# Phase 5 — execute (DeepSeek V4 Flash, one agent per batch)
.oracle/checkins/batch-1-r3.md:854:# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=max
.oracle/checkins/batch-1-r3.md:855:# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=max "$(cat /tmp/checkin-brief.md)" </dev/null
.oracle/checkins/batch-1-r3.md:857:# Phase 6 — commit, push, open
.oracle/checkins/batch-1-r3.md:888:# Megado Checkpoint — Batch 1 re-review
.oracle/checkins/batch-1-r3.md:897:1. Run ownership boundary → corrected baseline (leaf vs facade) + new
.oracle/checkins/batch-1-r3.md:900:2. Baseline completeness → callsite table corrected (plan_templates added,
.oracle/checkins/batch-1-r3.md:904:3. Result-level attachments finalizer wire → FinalizeRequest now carries
.oracle/checkins/batch-1-r3.md:907:4. Provenance routing/replay lineage → explicit planner/segment/finalizer
.oracle/checkins/batch-1-r3.md:910:5. Unversioned responses + plan topology → schema_version on
.oracle/checkins/batch-1-r3.md:913:6. Schema/DTO mismatch → shared profile definitions, audio-ownership
.oracle/checkins/batch-1-r3.md:916:7. Finalizer ID → canonical `rendering.ffmpeg-finalizer` locked everywhere.
.oracle/checkins/batch-1-r3.md:922:8. Pack validation KeyError → validate.py now validates rendering manifests,
.oracle/checkins/batch-1-r3.md:926:9. Transitive alias eligibility → transitive evaluation against the completed
.oracle/checkins/batch-1-r3.md:931:## Evidence
.oracle/checkins/batch-1-r3.md:948:## Verdict
.oracle/checkins/batch-1-r3.md:977:# Context Minning & Subagent Maxxing
.oracle/checkins/batch-1-r3.md:990:## Move 1 — Context minning: condense at the seams
.oracle/checkins/batch-1-r3.md:1010:## Move 2 — Subagent maxxing: do the work elsewhere
.oracle/checkins/batch-1-r3.md:1035:## The loop, in one line
.oracle/checkins/batch-1-r3.md:1049:# Astrid
.oracle/checkins/batch-1-r3.md:1054:## When in doubt, run `astrid next`
.oracle/checkins/batch-1-r3.md:1076:## Start Here
.oracle/checkins/batch-1-r3.md:1128:# Megado Checkpoint — Batch 1 second re-review
.oracle/checkins/batch-1-r3.md:1139:## How each of your 5 re-review issues was addressed (host-implemented)
.oracle/checkins/batch-1-r3.md:1141:1. **Baseline C0 evidence mislabeled + generated-source coverage map wrong** →
.oracle/checkins/batch-1-r3.md:1150:2. **Provenance regressed v1 + incomplete resolution records** →
.oracle/checkins/batch-1-r3.md:1161:3. **Schema/DTO whitespace parity** → `stringMap` now constrains keys and
.oracle/checkins/batch-1-r3.md:1167:4. **Underscore-compatible IDs** → `_QUALIFIED_ID_RE` accepts `[a-z0-9_-]`
.oracle/checkins/batch-1-r3.md:1175:5. **Pack alias→override route dropped** → removed the `astrid.core`-only
.oracle/checkins/batch-1-r3.md:1180:## Evidence
.oracle/checkins/batch-1-r3.md:1193:## Verdict
.oracle/checkins/batch-1-r3.md:1217:# Megado
.oracle/checkins/batch-1-r3.md:1223:1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
.oracle/checkins/batch-1-r3.md:1224:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
.oracle/checkins/batch-1-r3.md:1225:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
.oracle/checkins/batch-1-r3.md:1226:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
.oracle/checkins/batch-1-r3.md:1227:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
.oracle/checkins/batch-1-r3.md:1228:6. Open it and sync.
.oracle/checkins/batch-1-r3.md:1230:## Roles
.oracle/checkins/batch-1-r3.md:1243:## Artifacts (in the worktree)
.oracle/checkins/batch-1-r3.md:1255:## Phase 0 — Worktree
.oracle/checkins/batch-1-r3.md:1265:## Phase 1 — Initial plan (Codex)
.oracle/checkins/batch-1-r3.md:1269:1. A tasklist covering the **entirety** of the project (not just the obvious path).
.oracle/checkins/batch-1-r3.md:1270:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
.oracle/checkins/batch-1-r3.md:1271:3. Open questions / potential issues.
.oracle/checkins/batch-1-r3.md:1280:## Phase 2 — Deep exploration (DeepSeek fan-out)
.oracle/checkins/batch-1-r3.md:1293:## Phase 3 — Revise-until-stable loop
.oracle/checkins/batch-1-r3.md:1303:## Phase 4 — Batched tasklist with checkpoints (Codex)
.oracle/checkins/batch-1-r3.md:1307:- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
.oracle/checkins/batch-1-r3.md:1308:- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
.oracle/checkins/batch-1-r3.md:1309:- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
.oracle/checkins/batch-1-r3.md:1310:- **Per-batch acceptance criteria** the oracle will verify.
.oracle/checkins/batch-1-r3.md:1314:## Phase 5 — Execute, with oracle checkpoints
.oracle/checkins/batch-1-r3.md:1346:## Phase 6 — Completion
.oracle/checkins/batch-1-r3.md:1348:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
.oracle/checkins/batch-1-r3.md:1349:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
.oracle/checkins/batch-1-r3.md:1350:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
.oracle/checkins/batch-1-r3.md:1393:# ISSUES — Batch 1 does not pass
.oracle/checkins/batch-1-r3.md:1395:1. **Run ownership is characterized at the wrong boundary.** [baseline.md](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:192) and the [characterization test](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:472) prove only that the private leaf module does not create a ledger. The public `rendering.render` facade does call `prepare_project_run`; `requires_timeline: false` does not disable run ownership. Standalone facade ownership, task-attached reuse, retained output, `project=None`, and `run_root` behavior required by the [stable plan](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/plan.md:11) remain uncharacterized.
.oracle/checkins/batch-1-r3.md:1399:2. **The remaining baseline characterization is incomplete.**
.oracle/checkins/batch-1-r3.md:1410:3. **Result-level attachments cannot cross the finalizer wire.** [RenderResult](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1029) has attachments separate from `VideoArtifact.attachments`, but [FinalizeRequest](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1194) carries only `list[VideoArtifact]`. A standalone finalizer therefore cannot preserve result-level attachments, and collisions across segment artifacts are unchecked.
.oracle/checkins/batch-1-r3.md:1414:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r3.md:1418:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
.oracle/checkins/batch-1-r3.md:1422:6. **The normative JSON Schemas do not match the DTOs.** In [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:90), [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:59), and [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:102), the populated-audio branch omits `required`. I confirmed all three schemas accept a profile containing only `audio_codec: "aac"`, while [RenderProfile](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:423) rejects it. `result.json` also accepts contradictory `video.audio` and top-level `audio_ownership`. Both DTO and schema permit drive-relative `C:escape.mp4`, contrary to the documented no-drive path contract. No standalone raw versioned JSON fixtures were committed.
.oracle/checkins/batch-1-r3.md:1426:7. **The frozen FFmpeg finalizer ID is contradicted and currently invalid.** The plan/tasklist require `rendering.ffmpeg-finalizer`, but the contract, fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID regex in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:212) forbids the planned spelling.
.oracle/checkins/batch-1-r3.md:1430:8. **The new alias kinds crash public pack validation.** [validate.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:237) initializes resolver/capability maps only for executors and orchestrators, then indexes them using the newly accepted alias kind at [line 830](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:830). Running `validate_pack` on the committed rendering fixture raises `KeyError: 'renderer'`; consequently such a pack cannot follow the normal validation/install path.
.oracle/checkins/batch-1-r3.md:1434:9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.
.oracle/checkins/batch-1-r3.md:1446:# ISSUES — Batch 1 does not pass
.oracle/checkins/batch-1-r3.md:1448:1. **Run ownership is characterized at the wrong boundary.** [baseline.md](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:192) and the [characterization test](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:472) prove only that the private leaf module does not create a ledger. The public `rendering.render` facade does call `prepare_project_run`; `requires_timeline: false` does not disable run ownership. Standalone facade ownership, task-attached reuse, retained output, `project=None`, and `run_root` behavior required by the [stable plan](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/plan.md:11) remain uncharacterized.
.oracle/checkins/batch-1-r3.md:1452:2. **The remaining baseline characterization is incomplete.**
.oracle/checkins/batch-1-r3.md:1463:3. **Result-level attachments cannot cross the finalizer wire.** [RenderResult](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1029) has attachments separate from `VideoArtifact.attachments`, but [FinalizeRequest](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1194) carries only `list[VideoArtifact]`. A standalone finalizer therefore cannot preserve result-level attachments, and collisions across segment artifacts are unchecked.
.oracle/checkins/batch-1-r3.md:1467:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
.oracle/checkins/batch-1-r3.md:1471:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
.oracle/checkins/batch-1-r3.md:1475:6. **The normative JSON Schemas do not match the DTOs.** In [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:90), [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:59), and [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:102), the populated-audio branch omits `required`. I confirmed all three schemas accept a profile containing only `audio_codec: "aac"`, while [RenderProfile](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:423) rejects it. `result.json` also accepts contradictory `video.audio` and top-level `audio_ownership`. Both DTO and schema permit drive-relative `C:escape.mp4`, contrary to the documented no-drive path contract. No standalone raw versioned JSON fixtures were committed.
.oracle/checkins/batch-1-r3.md:1479:7. **The frozen FFmpeg finalizer ID is contradicted and currently invalid.** The plan/tasklist require `rendering.ffmpeg-finalizer`, but the contract, fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID regex in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:212) forbids the planned spelling.
.oracle/checkins/batch-1-r3.md:1483:8. **The new alias kinds crash public pack validation.** [validate.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:237) initializes resolver/capability maps only for executors and orchestrators, then indexes them using the newly accepted alias kind at [line 830](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:830). Running `validate_pack` on the committed rendering fixture raises `KeyError: 'renderer'`; consequently such a pack cannot follow the normal validation/install path.
.oracle/checkins/batch-1-r3.md:1487:9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.
.oracle/checkins/batch-1-r3.md:1586:## Issues
.oracle/checkins/batch-1-r3.md:1588:1. **Baseline completeness remains open (prior issue 2).** [baseline.md:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:51) labels results “C0 evidence,” but line 53 says they ran at `f8af4b2`/C1 and misidentifies C0. C1 changed shared pack/executor code, so this inference is not valid before/after evidence. The generated-source row at [baseline.md:416](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:416) also maps unrelated URL/Hype behavior instead of [test_remotion_element_generation.py:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_remotion_element_generation.py:22).
.oracle/checkins/batch-1-r3.md:1592:2. **Provenance/replay remains incomplete and regresses v1 (prior issue 4).** [provenance.py:183](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:183) replaces legacy `segments` with v2 records, while [provenance.py:192](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:192) overwrites nested `segment_provenance` sidecars with `{engine,from,to}` projections. This contradicts the characterized legacy shapes at [test_legacy_renderer_characterization.py:385](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:385). Resolution records are also incomplete: planner lacks alias/override evidence, renderer lacks trust evidence, and finalizer lacks alias/override/trust at [contracts.py:962](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:962). Artifact hashes have no provenance surface, and request-digest canonicalization is unspecified.
.oracle/checkins/batch-1-r3.md:1596:3. **Schema/DTO parity remains false (prior issue 6).** For example, [request.json:165](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:165) accepts empty or whitespace-only metadata keys/values, while [contracts.py:244](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:244) rejects them. Result paths and profile strings have equivalent whitespace mismatches.
.oracle/checkins/batch-1-r3.md:1600:4. **The underscore-compatible ID fix is absent, leaving pack validation broken (prior issues 7–8).** [contracts.py:35](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:35) and all rendering schemas remain hyphen-only. Consequently, the frozen [rendering.legacy_hybrid fixture](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/manifests/hybrid.planner.yaml:2) fails direct `validate_pack` and CLI validation. Tests conceal this by rewriting fixture IDs at runtime in [test_registry.py:39](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry.py:39).
.oracle/checkins/batch-1-r3.md:1606:5. **Valid pack alias→override routes are dropped (new issue adjacent to prior issue 9).** [registry.py:1023](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:1023) recognizes an override-routable missing canonical target only when the alias originates from `astrid.core`. Thus a trusted pack route such as `pack.alias → missing.canonical → override → executable.renderer` is discarded, violating the frozen alias→canonical→override ordering.
.oracle/checkins/batch-1-r3.md:1610:Issues 1, 3, and 5 are genuinely closed. The original KeyError portion of issue 8 and transitive-eligibility portion of issue 9 are fixed. No additional substantive non-rendering production scope creep was found.
.oracle/checkins/batch-1-r3.md:1613:## Issues
.oracle/checkins/batch-1-r3.md:1615:1. **Baseline completeness remains open (prior issue 2).** [baseline.md:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:51) labels results “C0 evidence,” but line 53 says they ran at `f8af4b2`/C1 and misidentifies C0. C1 changed shared pack/executor code, so this inference is not valid before/after evidence. The generated-source row at [baseline.md:416](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:416) also maps unrelated URL/Hype behavior instead of [test_remotion_element_generation.py:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_remotion_element_generation.py:22).
.oracle/checkins/batch-1-r3.md:1619:2. **Provenance/replay remains incomplete and regresses v1 (prior issue 4).** [provenance.py:183](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:183) replaces legacy `segments` with v2 records, while [provenance.py:192](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:192) overwrites nested `segment_provenance` sidecars with `{engine,from,to}` projections. This contradicts the characterized legacy shapes at [test_legacy_renderer_characterization.py:385](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:385). Resolution records are also incomplete: planner lacks alias/override evidence, renderer lacks trust evidence, and finalizer lacks alias/override/trust at [contracts.py:962](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:962). Artifact hashes have no provenance surface, and request-digest canonicalization is unspecified.
.oracle/checkins/batch-1-r3.md:1623:3. **Schema/DTO parity remains false (prior issue 6).** For example, [request.json:165](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:165) accepts empty or whitespace-only metadata keys/values, while [contracts.py:244](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:244) rejects them. Result paths and profile strings have equivalent whitespace mismatches.
.oracle/checkins/batch-1-r3.md:1627:4. **The underscore-compatible ID fix is absent, leaving pack validation broken (prior issues 7–8).** [contracts.py:35](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:35) and all rendering schemas remain hyphen-only. Consequently, the frozen [rendering.legacy_hybrid fixture](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/manifests/hybrid.planner.yaml:2) fails direct `validate_pack` and CLI validation. Tests conceal this by rewriting fixture IDs at runtime in [test_registry.py:39](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry.py:39).
.oracle/checkins/batch-1-r3.md:1633:5. **Valid pack alias→override routes are dropped (new issue adjacent to prior issue 9).** [registry.py:1023](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:1023) recognizes an override-routable missing canonical target only when the alias originates from `astrid.core`. Thus a trusted pack route such as `pack.alias → missing.canonical → override → executable.renderer` is discarded, violating the frozen alias→canonical→override ordering.
.oracle/checkins/batch-1-r3.md:1637:Issues 1, 3, and 5 are genuinely closed. The original KeyError portion of issue 8 and transitive-eligibility portion of issue 9 are fixed. No additional substantive non-rendering production scope creep was found.
.oracle/checkins/batch-1-r3.md:1751:## ISSUES
.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r3.md:1757:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r3.md:1761:3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.
.oracle/checkins/batch-1-r3.md:1766:## ISSUES
.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
.oracle/checkins/batch-1-r3.md:1772:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
.oracle/checkins/batch-1-r3.md:1776:3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.
.oracle/checkins/batch-1-r3.md:11121:# Astrid
.oracle/checkins/batch-1-r3.md:11126:## When in doubt, run `astrid next`
.oracle/checkins/batch-1-r3.md:11148:## Start Here
.oracle/checkins/batch-1-r3.md:11186:## Projects
.oracle/checkins/batch-1-r3.md:11215:## Choose The Mode
.oracle/checkins/batch-1-r3.md:11223:## Pack-Specific Guidance
.oracle/checkins/batch-1-r3.md:11245:## Shared Knowledge With Hivemind
.oracle/checkins/batch-1-r3.md:11256:1. Record observations and evidence-backed inferences locally.
.oracle/checkins/batch-1-r3.md:11257:2. Search Hivemind for an existing equivalent learning.
.oracle/checkins/batch-1-r3.md:11258:3. Contribute a concise experiment report as a resource.
.oracle/checkins/batch-1-r3.md:11259:4. Submit the reusable learning as a distillation citing that resource.
.oracle/checkins/batch-1-r3.md:11260:5. Preserve the returned Hivemind IDs beside the local experiment.
.oracle/checkins/batch-1-r3.md:11276:## Run A Tool
.oracle/checkins/batch-1-r3.md:11302:## Continue A Task Run
.oracle/checkins/batch-1-r3.md:11362:## Create Something New
.oracle/checkins/batch-1-r3.md:11367:1. **Search and compose existing executors first.** If existing executors can
.oracle/checkins/batch-1-r3.md:11369:2. **Create missing executors next.** Each new executor does one concrete,
.oracle/checkins/batch-1-r3.md:11371:3. **Then write the orchestrator.** It composes existing and newly created
.oracle/checkins/batch-1-r3.md:11373:4. **Add elements only for reusable render building blocks.** Effects,
.oracle/checkins/batch-1-r3.md:11419:## Safety Rules
.oracle/checkins/batch-1-r3.md:11444:## Common Defaults
.oracle/checkins/batch-1-r3.md:11467:## Pack Model
.oracle/checkins/batch-1-r3.md:11475:### Discovery for Agents
.oracle/checkins/batch-1-r3.md:11488:### Inspect Before Running
.oracle/checkins/batch-1-r3.md:11500:### Capability Kinds
.oracle/checkins/batch-1-r3.md:11508:### Aliases, Forks, and Overrides
.oracle/checkins/batch-1-r3.md:11512:- **Aliases** — Map old or alternate ids to current capabilities. Declared in
.oracle/checkins/batch-1-r3.md:11514:- **Forks** — Copy a capability into a local pack for independent editing.
.oracle/checkins/batch-1-r3.md:11517:- **Overrides** — Redirect a capability id to a preferred fork without
.oracle/checkins/batch-1-r3.md:11522:### Further Reading
.oracle/checkins/batch-1-r3.md:11539:## Per-project plan.md
.oracle/checkins/batch-1-r3.md:11543:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
.oracle/checkins/batch-1-r3.md:11544:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
.oracle/checkins/batch-1-r3.md:11545:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
.oracle/checkins/batch-1-r3.md:11549:### Executors
.oracle/checkins/batch-1-r3.md:11625:### Orchestrators
.oracle/checkins/batch-1-r3.md:11644:### Elements
.oracle/checkins/batch-1-r3.md:11666:## Installing into agent harnesses
.oracle/checkins/batch-1-r3.md:11683:## Adding overlays to a rendered video
.oracle/checkins/batch-1-r3.md:11687:### The timeline and optional asset registry
.oracle/checkins/batch-1-r3.md:11692:### Layering rule (gotcha)
.oracle/checkins/batch-1-r3.md:11696:### Timeline design conventions
.oracle/checkins/batch-1-r3.md:11702:### Minimal maintainable example: video + caption + wordmark
.oracle/checkins/batch-1-r3.md:11742:### Adding music or another audio track
.oracle/checkins/batch-1-r3.md:11787:### Rendering
.oracle/checkins/batch-1-r3.md:11818:### Local effect assets
.oracle/checkins/batch-1-r3.md:11836:### Where the schemas live (authoritative)
.oracle/checkins/batch-1-r3.md:11845:### Available elements
.oracle/checkins/batch-1-r3.md:11853:### Text rendering note (important)
.oracle/checkins/batch-1-r3.md:11859:# edit astrid/packs/local/elements/effects/text-card/component.tsx
.oracle/checkins/batch-1-r3.md:11865:### 5-minute "add a caption" recipe
.oracle/checkins/batch-1-r3.md:11867:1. Drop your source `.mp4` into `runs/<name>/`.
.oracle/checkins/batch-1-r3.md:11868:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
.oracle/checkins/batch-1-r3.md:11869:3. Render with the command above.
.oracle/checkins/batch-1-r3.md:11870:4. ffprobe / open the `composed.mp4`.
.oracle/checkins/batch-1-r3.md:11871:5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
.oracle/checkins/batch-1-r3.md:11873:## Validate
.oracle/checkins/batch-1-r3.md:11880:## Upstream friction
.oracle/checkins/batch-1-r3.md:11884:## Begin
.oracle/checkins/batch-1-r3.md:11896:## Safety Rules
.oracle/checkins/batch-1-r3.md:11921:## Common Defaults
.oracle/checkins/batch-1-r3.md:11944:## Pack Model
.oracle/checkins/batch-1-r3.md:11952:### Discovery for Agents
.oracle/checkins/batch-1-r3.md:11965:### Inspect Before Running
.oracle/checkins/batch-1-r3.md:11977:### Capability Kinds
.oracle/checkins/batch-1-r3.md:11985:### Aliases, Forks, and Overrides
.oracle/checkins/batch-1-r3.md:11989:- **Aliases** — Map old or alternate ids to current capabilities. Declared in
.oracle/checkins/batch-1-r3.md:11991:- **Forks** — Copy a capability into a local pack for independent editing.
.oracle/checkins/batch-1-r3.md:11994:- **Overrides** — Redirect a capability id to a preferred fork without
.oracle/checkins/batch-1-r3.md:11999:### Further Reading
.oracle/checkins/batch-1-r3.md:12016:## Per-project plan.md
.oracle/checkins/batch-1-r3.md:12020:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
.oracle/checkins/batch-1-r3.md:12021:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
.oracle/checkins/batch-1-r3.md:12022:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
.oracle/checkins/batch-1-r3.md:12026:### Executors
.oracle/checkins/batch-1-r3.md:12102:### Orchestrators
.oracle/checkins/batch-1-r3.md:12121:### Elements
.oracle/checkins/batch-1-r3.md:12143:## Installing into agent harnesses
.oracle/checkins/batch-1-r3.md:12160:## Adding overlays to a rendered video
.oracle/checkins/batch-1-r3.md:12164:### The timeline and optional asset registry
.oracle/checkins/batch-1-r3.md:12169:### Layering rule (gotcha)
.oracle/checkins/batch-1-r3.md:12173:### Timeline design conventions
.oracle/checkins/batch-1-r3.md:12179:### Minimal maintainable example: video + caption + wordmark
.oracle/checkins/batch-1-r3.md:24174:## ISSUES
.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r3.md:24182:2. **Schema/DTO parity remains false beyond the repaired nullable scalars.**
.oracle/checkins/batch-1-r3.md:24192:3. **The temp-fixture regression still exercises a statically invalid pack.** [`_write_alias_to_absent_pack()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486) declares a same-pack alias to absent `alias_missing.absent`. `validate_pack` rejects precisely that case ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)), while the tests inject it directly into discovery ([test_registry_matrix.py:530](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:530)). Moving the invalid fixture into `tmp_path` fixes the committed corpus but still does not prove a valid/installable pack route.
.oracle/checkins/batch-1-r3.md:24199:## ISSUES
.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r3.md:24207:2. **Schema/DTO parity remains false beyond the repaired nullable scalars.**
.oracle/checkins/batch-1-r3.md:24217:3. **The temp-fixture regression still exercises a statically invalid pack.** [`_write_alias_to_absent_pack()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486) declares a same-pack alias to absent `alias_missing.absent`. `validate_pack` rejects precisely that case ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)), while the tests inject it directly into discovery ([test_registry_matrix.py:530](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:530)). Moving the invalid fixture into `tmp_path` fixes the committed corpus but still does not prove a valid/installable pack route.
.oracle/checkins/batch-1-r1.md:17:# Megado Checkpoint — Batch 1 re-review
.oracle/checkins/batch-1-r1.md:26:1. Run ownership boundary → corrected baseline (leaf vs facade) + new
.oracle/checkins/batch-1-r1.md:29:2. Baseline completeness → callsite table corrected (plan_templates added,
.oracle/checkins/batch-1-r1.md:33:3. Result-level attachments finalizer wire → FinalizeRequest now carries
.oracle/checkins/batch-1-r1.md:36:4. Provenance routing/replay lineage → explicit planner/segment/finalizer
.oracle/checkins/batch-1-r1.md:39:5. Unversioned responses + plan topology → schema_version on
.oracle/checkins/batch-1-r1.md:42:6. Schema/DTO mismatch → shared profile definitions, audio-ownership

exec
/bin/zsh -lc "sed -n '1,38p' .oracle/tasklist.md && for f in .oracle/checkins/batch-1.md .oracle/checkins/batch-1-r1.md .oracle/checkins/batch-1-r2.md .oracle/checkins/batch-1-r3.md .oracle/checkins/batch-1-r4.md; do echo \""'$f"; rg -n "''^## ISSUES|''^PASS$|''^1'"\\. \\*\\*|"'^2'"\\. \\*\\*|"'^3'"\\. \\*\\*|"'^4'"\\. \\*\\*|"'^5'"\\. \\*\\*|"'^6'"\\. \\*\\*|"'^7'"\\. \\*\\*|"'^8'"\\. \\*\\*|"'^9'"\\. \\*\\*\" \""'$f" | tail -n 14; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
.oracle/checkins/batch-1.md
22597:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
22601:6. **The normative JSON Schemas do not match the DTOs.** In [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:90), [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:59), and [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:102), the populated-audio branch omits `required`. I confirmed all three schemas accept a profile containing only `audio_codec: "aac"`, while [RenderProfile](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:423) rejects it. `result.json` also accepts contradictory `video.audio` and top-level `audio_ownership`. Both DTO and schema permit drive-relative `C:escape.mp4`, contrary to the documented no-drive path contract. No standalone raw versioned JSON fixtures were committed.
22605:7. **The frozen FFmpeg finalizer ID is contradicted and currently invalid.** The plan/tasklist require `rendering.ffmpeg-finalizer`, but the contract, fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID regex in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:212) forbids the planned spelling.
22609:8. **The new alias kinds crash public pack validation.** [validate.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:237) initializes resolver/capability maps only for executors and orchestrators, then indexes them using the newly accepted alias kind at [line 830](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:830). Running `validate_pack` on the committed rendering fixture raises `KeyError: 'renderer'`; consequently such a pack cannot follow the normal validation/install path.
22613:9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.
22627:1. **Run ownership is characterized at the wrong boundary.** [baseline.md](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:192) and the [characterization test](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:472) prove only that the private leaf module does not create a ledger. The public `rendering.render` facade does call `prepare_project_run`; `requires_timeline: false` does not disable run ownership. Standalone facade ownership, task-attached reuse, retained output, `project=None`, and `run_root` behavior required by the [stable plan](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/plan.md:11) remain uncharacterized.
22631:2. **The remaining baseline characterization is incomplete.**
22642:3. **Result-level attachments cannot cross the finalizer wire.** [RenderResult](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1029) has attachments separate from `VideoArtifact.attachments`, but [FinalizeRequest](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1194) carries only `list[VideoArtifact]`. A standalone finalizer therefore cannot preserve result-level attachments, and collisions across segment artifacts are unchecked.
22646:4. **The frozen provenance shape cannot represent the required routing and replay lineage.** The plan requires resolved renderer, planner, and finalizer identity plus source/trust, alias/override, manifest, and request digests. Current provenance has only singular `resolved_backend`, `source_pack`, and `manifest_digest` keys in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53) and [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150). Hybrid plans with multiple renderer invocations cannot represent this without collapsing evidence. Additionally, [raw segment mappings](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:77) can supply spoofed `engine`, `from`, or `to` because core uses `setdefault` instead of deriving them unconditionally.
22650:5. **Several wire responses are unversioned, and plans accept invalid temporal topology.** `SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in both DTOs and schemas—for example [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:7), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:7), and the error branch of [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:166). This contradicts the contract’s rule that V1 readers reject unknown versions. Separately, [RenderPlan validation](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:966) accepts overlapping, out-of-order, gapped, and profile-FPS-mismatched segments despite the documented deterministic, non-overlapping coverage requirement.
22654:6. **The normative JSON Schemas do not match the DTOs.** In [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:90), [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:59), and [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:102), the populated-audio branch omits `required`. I confirmed all three schemas accept a profile containing only `audio_codec: "aac"`, while [RenderProfile](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:423) rejects it. `result.json` also accepts contradictory `video.audio` and top-level `audio_ownership`. Both DTO and schema permit drive-relative `C:escape.mp4`, contrary to the documented no-drive path contract. No standalone raw versioned JSON fixtures were committed.
22658:7. **The frozen FFmpeg finalizer ID is contradicted and currently invalid.** The plan/tasklist require `rendering.ffmpeg-finalizer`, but the contract, fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID regex in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:212) forbids the planned spelling.
22662:8. **The new alias kinds crash public pack validation.** [validate.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:237) initializes resolver/capability maps only for executors and orchestrators, then indexes them using the newly accepted alias kind at [line 830](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:830). Running `validate_pack` on the committed rendering fixture raises `KeyError: 'renderer'`; consequently such a pack cannot follow the normal validation/install path.
22666:9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.
.oracle/checkins/batch-1-r1.md
7433:6. **The normative JSON Schemas do not match the DTOs.** In [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:90), [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:59), and [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:102), the populated-audio branch omits `required`. I confirmed all three schemas accept a profile containing only `audio_codec: "aac"`, while [RenderProfile](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:423) rejects it. `result.json` also accepts contradictory `video.audio` and top-level `audio_ownership`. Both DTO and schema permit drive-relative `C:escape.mp4`, contrary to the documented no-drive path contract. No standalone raw versioned JSON fixtures were committed.
7437:7. **The frozen FFmpeg finalizer ID is contradicted and currently invalid.** The plan/tasklist require `rendering.ffmpeg-finalizer`, but the contract, fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID regex in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:212) forbids the planned spelling.
7441:8. **The new alias kinds crash public pack validation.** [validate.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:237) initializes resolver/capability maps only for executors and orchestrators, then indexes them using the newly accepted alias kind at [line 830](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:830). Running `validate_pack` on the committed rendering fixture raises `KeyError: 'renderer'`; consequently such a pack cannot follow the normal validation/install path.
7445:9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.
20934:1. **Baseline completeness remains open (prior issue 2).** [baseline.md:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:51) labels results “C0 evidence,” but line 53 says they ran at `f8af4b2`/C1 and misidentifies C0. C1 changed shared pack/executor code, so this inference is not valid before/after evidence. The generated-source row at [baseline.md:416](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:416) also maps unrelated URL/Hype behavior instead of [test_remotion_element_generation.py:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_remotion_element_generation.py:22).
20938:2. **Provenance/replay remains incomplete and regresses v1 (prior issue 4).** [provenance.py:183](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:183) replaces legacy `segments` with v2 records, while [provenance.py:192](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:192) overwrites nested `segment_provenance` sidecars with `{engine,from,to}` projections. This contradicts the characterized legacy shapes at [test_legacy_renderer_characterization.py:385](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:385). Resolution records are also incomplete: planner lacks alias/override evidence, renderer lacks trust evidence, and finalizer lacks alias/override/trust at [contracts.py:962](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:962). Artifact hashes have no provenance surface, and request-digest canonicalization is unspecified.
20942:3. **Schema/DTO parity remains false (prior issue 6).** For example, [request.json:165](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:165) accepts empty or whitespace-only metadata keys/values, while [contracts.py:244](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:244) rejects them. Result paths and profile strings have equivalent whitespace mismatches.
20946:4. **The underscore-compatible ID fix is absent, leaving pack validation broken (prior issues 7–8).** [contracts.py:35](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:35) and all rendering schemas remain hyphen-only. Consequently, the frozen [rendering.legacy_hybrid fixture](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/manifests/hybrid.planner.yaml:2) fails direct `validate_pack` and CLI validation. Tests conceal this by rewriting fixture IDs at runtime in [test_registry.py:39](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry.py:39).
20952:5. **Valid pack alias→override routes are dropped (new issue adjacent to prior issue 9).** [registry.py:1023](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:1023) recognizes an override-routable missing canonical target only when the alias originates from `astrid.core`. Thus a trusted pack route such as `pack.alias → missing.canonical → override → executable.renderer` is discarded, violating the frozen alias→canonical→override ordering.
20961:1. **Baseline completeness remains open (prior issue 2).** [baseline.md:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:51) labels results “C0 evidence,” but line 53 says they ran at `f8af4b2`/C1 and misidentifies C0. C1 changed shared pack/executor code, so this inference is not valid before/after evidence. The generated-source row at [baseline.md:416](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/baseline.md:416) also maps unrelated URL/Hype behavior instead of [test_remotion_element_generation.py:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_remotion_element_generation.py:22).
20965:2. **Provenance/replay remains incomplete and regresses v1 (prior issue 4).** [provenance.py:183](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:183) replaces legacy `segments` with v2 records, while [provenance.py:192](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:192) overwrites nested `segment_provenance` sidecars with `{engine,from,to}` projections. This contradicts the characterized legacy shapes at [test_legacy_renderer_characterization.py:385](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/packs/rendering/test_legacy_renderer_characterization.py:385). Resolution records are also incomplete: planner lacks alias/override evidence, renderer lacks trust evidence, and finalizer lacks alias/override/trust at [contracts.py:962](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:962). Artifact hashes have no provenance surface, and request-digest canonicalization is unspecified.
20969:3. **Schema/DTO parity remains false (prior issue 6).** For example, [request.json:165](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:165) accepts empty or whitespace-only metadata keys/values, while [contracts.py:244](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:244) rejects them. Result paths and profile strings have equivalent whitespace mismatches.
20973:4. **The underscore-compatible ID fix is absent, leaving pack validation broken (prior issues 7–8).** [contracts.py:35](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:35) and all rendering schemas remain hyphen-only. Consequently, the frozen [rendering.legacy_hybrid fixture](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/manifests/hybrid.planner.yaml:2) fails direct `validate_pack` and CLI validation. Tests conceal this by rewriting fixture IDs at runtime in [test_registry.py:39](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry.py:39).
20979:5. **Valid pack alias→override routes are dropped (new issue adjacent to prior issue 9).** [registry.py:1023](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:1023) recognizes an override-routable missing canonical target only when the alias originates from `astrid.core`. Thus a trusted pack route such as `pack.alias → missing.canonical → override → executable.renderer` is discarded, violating the frozen alias→canonical→override ordering.
.oracle/checkins/batch-1-r2.md
2790:9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.
3374:1. **Standalone with a project** (`test_facade_standalone_with_project_creates_one_run_json_and_rewrites_out_to_run_root`):
3381:2. **Task-attached reuse** (`test_facade_task_attached_reuses_run_context_without_new_run_json`):
3388:3. **No project** (`test_facade_without_project_fails_before_creating_ledger`):
3392:4. **Retained caller-selected output under attachment**
3400:5. **`run_root` in the request** (`test_facade_run_root_in_request_is_replaced_by_run_context_root`):
28669:## ISSUES
28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
28675:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
28679:3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.
28684:## ISSUES
28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
28690:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
28694:3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.
.oracle/checkins/batch-1-r3.md
1772:2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).
1776:3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.
11367:1. **Search and compose existing executors first.** If existing executors can
11369:2. **Create missing executors next.** Each new executor does one concrete,
11371:3. **Then write the orchestrator.** It composes existing and newly created
11373:4. **Add elements only for reusable render building blocks.** Effects,
24174:## ISSUES
24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
24182:2. **Schema/DTO parity remains false beyond the repaired nullable scalars.**
24192:3. **The temp-fixture regression still exercises a statically invalid pack.** [`_write_alias_to_absent_pack()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486) declares a same-pack alias to absent `alias_missing.absent`. `validate_pack` rejects precisely that case ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)), while the tests inject it directly into discovery ([test_registry_matrix.py:530](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:530)). Moving the invalid fixture into `tmp_path` fixes the committed corpus but still does not prove a valid/installable pack route.
24199:## ISSUES
24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
24207:2. **Schema/DTO parity remains false beyond the repaired nullable scalars.**
24217:3. **The temp-fixture regression still exercises a statically invalid pack.** [`_write_alias_to_absent_pack()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486) declares a same-pack alias to absent `alias_missing.absent`. `validate_pack` rejects precisely that case ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)), while the tests inject it directly into discovery ([test_registry_matrix.py:530](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:530)). Moving the invalid fixture into `tmp_path` fixes the committed corpus but still does not prove a valid/installable pack route.
.oracle/checkins/batch-1-r4.md
38786:6. **Run ownership:** a standalone `rendering.render` invocation owns its executor/project run. When another capability already owns the run, invoke the facade through the existing task-attached path:
38796:7. **Wire protocol:** backend commands run with `shell=False`, pack root as `cwd`, sanitized environment, absolute request/result paths, and an authoritative result file:
38804:8. **Compatibility selection:**
38812:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
39116:## ISSUES
39118:1. **Override coherence remains unvalidated.** Planner, renderer, and finalizer accept arbitrary `override` objects without requiring `{from,to}` or `override.to == resolution.id` ([contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1013)). The round-trip test deliberately records three contradictory targets ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:641)), even though registry semantics make `override.to` the selected implementation ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:367)). Plans and provenance can therefore identify A while claiming routing selected B.
39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
39122:3. **Schema/DTO parity remains materially false.**
39129:4. **The fixture does not exercise the installed revision.** Although validation and installation return success, the created `install_root` is unused and resolution calls `_load_with_source()` with `include_installed=False`, testing the source tree instead ([test_registry_matrix.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:537)). Moreover, installation records `trust_method="fixture-test"`, while installed rendering eligibility accepts only `interactive|cli_flag|api|test` ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:49)). The installed revision would be execution-ineligible if actually loaded.
39132:## ISSUES
39134:1. **Override coherence remains unvalidated.** Planner, renderer, and finalizer accept arbitrary `override` objects without requiring `{from,to}` or `override.to == resolution.id` ([contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1013)). The round-trip test deliberately records three contradictory targets ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:641)), even though registry semantics make `override.to` the selected implementation ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:367)). Plans and provenance can therefore identify A while claiming routing selected B.
39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
39138:3. **Schema/DTO parity remains materially false.**
39145:4. **The fixture does not exercise the installed revision.** Although validation and installation return success, the created `install_root` is unused and resolution calls `_load_with_source()` with `include_installed=False`, testing the source tree instead ([test_registry_matrix.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:537)). Moreover, installation records `trust_method="fixture-test"`, while installed rendering eligibility accepts only `interactive|cli_flag|api|test` ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:49)). The installed revision would be execution-ineligible if actually loaded.

exec
/bin/zsh -lc "git rev-parse C1 && git diff --stat C1..HEAD -- ':"'!.oracle/**'"' && git log --oneline --decorate --reverse C1..HEAD" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
f8af4b20042a90a92ddfef99c9d02defc6bb64ea
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 astrid/core/pack/schemas/v1/pack.json              |   4 +-
 astrid/core/pack/validate.py                       |  73 +-
 astrid/core/rendering/contracts.py                 | 819 +++++++++++++++---
 astrid/core/rendering/errors.py                    |   3 +-
 astrid/core/rendering/provenance.py                | 194 +++--
 astrid/core/rendering/registry.py                  | 167 +++-
 astrid/core/rendering/schemas/v1/finalize.json     | 923 ++++++++++++++++++---
 .../rendering/schemas/v1/finalizer-manifest.json   | 171 +++-
 astrid/core/rendering/schemas/v1/plan.json         | 758 ++++++++++++++---
 .../rendering/schemas/v1/planner-manifest.json     | 147 +++-
 .../rendering/schemas/v1/renderer-manifest.json    | 191 ++++-
 astrid/core/rendering/schemas/v1/request.json      | 421 +++++++---
 astrid/core/rendering/schemas/v1/result.json       | 587 ++++++++++---
 astrid/core/rendering/schemas/v1/support.json      |  70 +-
 docs/contracts/render-backend-v1.md                | 206 +++--
 tests/core/rendering/fixtures/v1/finalize.json     | 145 ++++
 tests/core/rendering/fixtures/v1/plan.json         | 107 +++
 tests/core/rendering/fixtures/v1/request.json      |  11 +
 tests/core/rendering/fixtures/v1/result.json       |  30 +
 tests/core/rendering/fixtures/v1/support.json      |   9 +
 tests/core/rendering/test_contracts.py             | 781 +++++++++++++----
 tests/core/rendering/test_registry.py              | 224 ++++-
 tests/core/rendering/test_registry_matrix.py       | 177 +++-
 tests/core/rendering/test_schema_roundtrip.py      | 414 ++++++---
 .../rendering/manifests/ffmpeg.finalizer.yaml      |   2 +-
 .../test_legacy_renderer_characterization.py       | 149 ++++
 .../rendering/test_render_facade_run_ownership.py  | 380 +++++++++
 tests/packs/test_pack_rendering_extensions.py      | 133 ++-
 28 files changed, 6037 insertions(+), 1259 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
b357de3 batch1-rework: oracle issues 1-9 (baseline facade ownership, contracts versioning/attachments/provenance, pack validation, transitive alias eligibility)
88c75f3 batch1-rework2: oracle re-review issues 1-5 (real-fixture deconcealment, underscore-compatible ids, provenance v1 preservation + v2 additive, whitespace parity, transitive override routing, baseline C0 evidence)
04767bf batch1-rework3: oracle re-review2 issues 1-3 (complete resolution records w/ trust+support, planner to_dict fix, nullable-string parity, segments_v2 prohibition, temp-fixture override regression)
808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
91f0fe3 (HEAD -> oracle-run) batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)

exec
/bin/zsh -lc "git diff --check 808030e..HEAD -- ':"'!.oracle/**'"' && git diff --unified=80 808030e..HEAD -- astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/plan.json astrid/core/rendering/schemas/v1/finalize.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/contracts.py b/astrid/core/rendering/contracts.py
index 587b4dc..3708541 100644
--- a/astrid/core/rendering/contracts.py
+++ b/astrid/core/rendering/contracts.py
@@ -170,160 +170,174 @@ def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
     return value
 
 
 def _validate_object_keys(
     payload: Mapping[str, Any],
     *,
     required: set[str] | frozenset[str],
     allowed: set[str] | frozenset[str],
     label: str,
 ) -> None:
     missing = sorted(required - payload.keys())
     if missing:
         raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
     unknown = sorted(payload.keys() - allowed)
     if unknown:
         raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
 
 
 def _require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
     if type(value) is not int:
         raise TypeError(f"{label} must be an integer")
     if minimum is not None and value < minimum:
         raise ValueError(f"{label} must be >= {minimum}")
     return value
 
 
 def _require_number(value: Any, label: str, *, exclusive_minimum: float | None = None) -> float:
     if isinstance(value, bool) or not isinstance(value, (int, float)):
         raise TypeError(f"{label} must be a number")
     number = float(value)
     if not math.isfinite(number):
         raise ValueError(f"{label} must be finite")
     if exclusive_minimum is not None and number <= exclusive_minimum:
         raise ValueError(f"{label} must be > {exclusive_minimum:g}")
     return number
 
 
 def compute_request_digest(request: Mapping[str, Any]) -> str:
     """Deterministic SHA-256 of a canonical, JSON-normalized render request.
 
     Uses sorted keys and compact separators so the digest is stable across
     Python versions and dict insertion orders; replay verifies the request
     against this digest.
     """
     return canonical_json_digest(_json_safe_mapping(request, label="render request"))
 
 
 def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
     if not isinstance(value, str):
         raise TypeError(f"{label} must be a string")
     if "\x00" in value:
         raise ValueError(f"{label} must not contain NUL")
     if not allow_empty and not value.strip():
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
     return result
 
 
+def _require_override(value: Any, *, capability_id: str, label: str) -> dict[str, Any]:
+    """Validate an override record: ``{from, to}`` with ``to`` equal to the
+    resolution id (the override is what selected this implementation)."""
+    mapping = _json_safe_mapping(value, label=label)
+    required = {"from", "to"}
+    if set(mapping) != required:
+        raise ValueError(f"{label} must contain exactly 'from' and 'to'")
+    _require_qualified_id(mapping["from"], f"{label} 'from'")
+    resolved = _require_qualified_id(mapping["to"], f"{label} 'to'")
+    if resolved != capability_id:
+        raise ValueError(f"{label} 'to' must equal the resolved capability id {capability_id!r}")
+    return mapping
+
+
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
@@ -937,353 +951,365 @@ class SupportReport:
             data = _require_mapping(payload, "support report")
             required = {
                 "schema_version",
                 "supported",
                 "reasons",
                 "features",
                 "alternatives",
                 "backend",
                 "backend_version",
             }
             _validate_object_keys(
                 data,
                 required=required,
                 allowed=required,
                 label="support report",
             )
             return cls(
                 schema_version=data["schema_version"],
                 supported=data["supported"],
                 reasons=data["reasons"],
                 features=data["features"],
                 alternatives=data["alternatives"],
                 backend=data["backend"],
                 backend_version=data["backend_version"],
             )
         except Exception as exc:
             from .errors import RendererException
 
             if isinstance(exc, RendererException):
                 raise
             _protocol_failure(
                 f"malformed support report: {exc}",
                 details={"error_type": type(exc).__name__},
             )
 
 
 @dataclass(frozen=True)
 class PlannerResolution:
     """Resolved planner identity and trust evidence frozen into a plan."""
 
     id: str
     source_pack: dict[str, Any]
     manifest_digest: str
     trust_eligibility: dict[str, Any]
     alias_chain: list[str] = field(default_factory=list)
     override: dict[str, Any] | None = None
     support_decision: SupportReport | None = None
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "id", _require_qualified_id(self.id, "planner id"))
         object.__setattr__(
             self,
             "source_pack",
             _json_safe_mapping(self.source_pack, label="planner source_pack"),
         )
         object.__setattr__(
             self,
             "manifest_digest",
             _require_sha256(self.manifest_digest, "planner manifest_digest"),
         )
         object.__setattr__(
             self,
             "trust_eligibility",
             _json_safe_mapping(
                 self.trust_eligibility,
                 label="planner trust_eligibility",
             ),
         )
         object.__setattr__(
             self,
             "alias_chain",
             [
                 _require_string(item, f"planner alias_chain[{index}]")
                 for index, item in enumerate(_require_string_list(self.alias_chain, "planner alias_chain"))
             ],
         )
         if self.override is not None:
             object.__setattr__(
                 self,
                 "override",
-                _json_safe_mapping(self.override, label="planner override"),
+                _require_override(
+                    self.override,
+                    capability_id=self.id,
+                    label="planner override",
+                ),
             )
         if self.support_decision is not None:
             support = (
                 self.support_decision
                 if isinstance(self.support_decision, SupportReport)
                 else SupportReport.from_dict(
                     _require_mapping(
                         self.support_decision, "planner support_decision"
                     )
                 )
             )
             if support.backend != self.id:
                 raise ValueError("planner support_decision.backend must match planner id")
             object.__setattr__(self, "support_decision", support)
 
     def to_dict(self) -> dict[str, Any]:
         return _json_safe_mapping(
             {
                 "id": self.id,
                 "source_pack": self.source_pack,
                 "manifest_digest": self.manifest_digest,
                 "trust_eligibility": self.trust_eligibility,
                 "alias_chain": list(self.alias_chain),
                 "override": self.override,
                 "support_decision": self.support_decision,
             }
         )
 
     @classmethod
     def from_dict(cls, payload: Mapping[str, Any]) -> PlannerResolution:
         data = _require_mapping(payload, "planner resolution")
         required = {
             "id",
             "source_pack",
             "manifest_digest",
             "trust_eligibility",
             "alias_chain",
             "override",
             "support_decision",
         }
         _validate_object_keys(data, required=required, allowed=required, label="planner resolution")
         return cls(
             id=data["id"],
             source_pack=data["source_pack"],
             manifest_digest=data["manifest_digest"],
             trust_eligibility=data["trust_eligibility"],
             alias_chain=data["alias_chain"],
             override=data["override"],
             support_decision=data["support_decision"],
         )
 
 
 @dataclass(frozen=True)
 class RendererResolution:
     """Resolved renderer identity and request-sensitive routing evidence."""
 
     id: str
     source_pack: dict[str, Any]
     manifest_digest: str
     alias_chain: list[str]
     override: dict[str, Any] | None
     support_decision: SupportReport
     trust_eligibility: dict[str, Any] = field(default_factory=dict)
 
     def __post_init__(self) -> None:
         renderer_id = _require_qualified_id(self.id, "renderer id")
         support = (
             self.support_decision
             if isinstance(self.support_decision, SupportReport)
             else SupportReport.from_dict(
                 _require_mapping(self.support_decision, "renderer support_decision")
             )
         )
         if support.backend != renderer_id:
             raise ValueError("renderer support_decision.backend must match renderer id")
         object.__setattr__(self, "id", renderer_id)
         object.__setattr__(
             self,
             "source_pack",
             _json_safe_mapping(self.source_pack, label="renderer source_pack"),
         )
         object.__setattr__(
             self,
             "manifest_digest",
             _require_sha256(self.manifest_digest, "renderer manifest_digest"),
         )
         object.__setattr__(
             self,
             "trust_eligibility",
             _json_safe_mapping(
                 self.trust_eligibility,
                 label="renderer trust_eligibility",
             ),
         )
         aliases = [
             _require_string(alias, f"renderer alias_chain[{index}]")
             for index, alias in enumerate(_require_string_list(self.alias_chain, "renderer alias_chain"))
         ]
         if len(aliases) != len(set(aliases)):
             raise ValueError("renderer alias_chain must not contain duplicates")
         object.__setattr__(self, "alias_chain", aliases)
         object.__setattr__(
             self,
             "override",
             None
             if self.override is None
-            else _json_safe_mapping(self.override, label="renderer override"),
+            else _require_override(
+                self.override,
+                capability_id=renderer_id,
+                label="renderer override",
+            ),
         )
         object.__setattr__(self, "support_decision", support)
 
     def to_dict(self) -> dict[str, Any]:
         return _json_safe_mapping(
             {
                 "id": self.id,
                 "source_pack": self.source_pack,
                 "manifest_digest": self.manifest_digest,
                 "alias_chain": self.alias_chain,
                 "override": self.override,
                 "support_decision": self.support_decision,
                 "trust_eligibility": self.trust_eligibility,
             }
         )
 
     @classmethod
     def from_dict(cls, payload: Mapping[str, Any]) -> RendererResolution:
         data = _require_mapping(payload, "renderer resolution")
         required = {
             "id",
             "source_pack",
             "manifest_digest",
             "alias_chain",
             "override",
             "support_decision",
             "trust_eligibility",
         }
         _validate_object_keys(data, required=required, allowed=required, label="renderer resolution")
         return cls(
             id=data["id"],
             source_pack=data["source_pack"],
             manifest_digest=data["manifest_digest"],
             alias_chain=data["alias_chain"],
             override=data["override"],
             support_decision=SupportReport.from_dict(data["support_decision"]),
             trust_eligibility=data["trust_eligibility"],
         )
 
 
 @dataclass(frozen=True)
 class FinalizerResolution:
     """Resolved finalizer identity pinned for standalone finalization."""
 
     id: str
     source_pack: dict[str, Any]
     manifest_digest: str
     alias_chain: list[str] = field(default_factory=list)
     override: dict[str, Any] | None = None
     trust_eligibility: dict[str, Any] = field(default_factory=dict)
     support_decision: SupportReport | None = None
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "id", _require_qualified_id(self.id, "finalizer id"))
         object.__setattr__(
             self,
             "source_pack",
             _json_safe_mapping(self.source_pack, label="finalizer source_pack"),
         )
         object.__setattr__(
             self,
             "manifest_digest",
             _require_sha256(self.manifest_digest, "finalizer manifest_digest"),
         )
         object.__setattr__(
             self,
             "trust_eligibility",
             _json_safe_mapping(
                 self.trust_eligibility,
                 label="finalizer trust_eligibility",
             ),
         )
         object.__setattr__(
             self,
             "alias_chain",
             [
                 _require_string(item, f"finalizer alias_chain[{index}]")
                 for index, item in enumerate(_require_string_list(self.alias_chain, "finalizer alias_chain"))
             ],
         )
         if self.override is not None:
             object.__setattr__(
                 self,
                 "override",
-                _json_safe_mapping(self.override, label="finalizer override"),
+                _require_override(
+                    self.override,
+                    capability_id=self.id,
+                    label="finalizer override",
+                ),
             )
         if self.support_decision is not None:
             support = (
                 self.support_decision
                 if isinstance(self.support_decision, SupportReport)
                 else SupportReport.from_dict(
                     _require_mapping(
                         self.support_decision, "finalizer support_decision"
                     )
                 )
             )
             if support.backend != self.id:
                 raise ValueError("finalizer support_decision.backend must match finalizer id")
             object.__setattr__(self, "support_decision", support)
 
     def to_dict(self) -> dict[str, Any]:
         return _json_safe_mapping(
             {
                 "id": self.id,
                 "source_pack": self.source_pack,
                 "manifest_digest": self.manifest_digest,
                 "alias_chain": list(self.alias_chain),
                 "override": self.override,
                 "trust_eligibility": self.trust_eligibility,
                 "support_decision": self.support_decision,
             }
         )
 
     @classmethod
     def from_dict(cls, payload: Mapping[str, Any]) -> FinalizerResolution:
         data = _require_mapping(payload, "finalizer resolution")
         required = {
             "id",
             "source_pack",
             "manifest_digest",
             "alias_chain",
             "override",
             "trust_eligibility",
             "support_decision",
         }
         _validate_object_keys(data, required=required, allowed=required, label="finalizer resolution")
         return cls(
             id=data["id"],
             source_pack=data["source_pack"],
             manifest_digest=data["manifest_digest"],
             alias_chain=data["alias_chain"],
             override=data["override"],
             trust_eligibility=data["trust_eligibility"],
             support_decision=data["support_decision"],
         )
 
 
 def _normalize_requested_policy(value: Any, label: str = "requested_policy") -> str | dict[str, Any]:
     if isinstance(value, str):
         return _require_string(value, label)
     return _json_safe_mapping(value, label=label)
 
 
 @dataclass(frozen=True)
 class RenderSegment:
     """One complete temporal window assigned to one qualified backend."""
 
     window: FrameWindow
     renderer: RendererResolution
     input_hashes: dict[str, str] = field(default_factory=dict)
 
     def __post_init__(self) -> None:
         object.__setattr__(self, "window", _coerce_window(self.window, "segment window", nullable=False))
         renderer = (
             self.renderer
             if isinstance(self.renderer, RendererResolution)
             else RendererResolution.from_dict(_require_mapping(self.renderer, "segment renderer"))
         )
         object.__setattr__(self, "renderer", renderer)
         object.__setattr__(
             self,
             "input_hashes",
             _require_hash_mapping(self.input_hashes, "segment input_hashes"),
         )
 
@@ -1763,163 +1789,166 @@ class FinalizeRequest:
     def to_dict(self) -> dict[str, Any]:
         return _json_safe_mapping(
             {
                 "schema_version": self.schema_version,
                 "plan": self.plan,
                 "artifacts": self.artifacts,
                 "output_name": self.output_name,
                 "backend_config": self.backend_config,
                 "metadata": self.metadata,
             }
         )
 
     @classmethod
     def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
         try:
             data = _require_mapping(payload, "finalize request")
             allowed = {
                 "schema_version",
                 "plan",
                 "artifacts",
                 "output_name",
                 "backend_config",
                 "metadata",
             }
             _validate_object_keys(
                 data,
                 required={"schema_version", "plan", "artifacts", "output_name"},
                 allowed=allowed,
                 label="finalize request",
             )
             version = _require_schema_version(data["schema_version"], "finalize request")
             return cls(
                 schema_version=version,
                 plan=RenderPlan.from_dict(data["plan"]),
                 artifacts=[VideoArtifact.from_dict(item) for item in data["artifacts"]],
                 output_name=data["output_name"],
                 backend_config=data.get("backend_config", {}),
                 metadata=data.get("metadata", {}),
             )
         except Exception as exc:
             from .errors import RendererException
 
             if isinstance(exc, RendererException):
                 raise
             _protocol_failure(
                 f"malformed finalize request: {exc}",
                 details={"error_type": type(exc).__name__},
             )
 
 
 _PERMISSIONS = frozenset(
     {"project_files", "network", "subprocess", "environment", "accelerator", "external_services"}
 )
 
 
 def _manifest_capability_object(
     value: Any,
     *,
     label: str,
     allowed: frozenset[str],
 ) -> dict[str, Any]:
     capabilities = _json_safe_mapping(value, label=label)
     unknown = sorted(set(capabilities) - allowed)
     if unknown:
         raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
     return capabilities
 
 
 def _manifest_string_array(value: Any, label: str) -> list[str]:
     items = _require_string_list(value, label)
     if len(items) != len(set(items)):
         raise ValueError(f"{label} must not contain duplicates")
     return items
 
 
 def _manifest_features(value: Any, label: str) -> dict[str, bool | str]:
     raw = _require_mapping(value, label)
     result: dict[str, bool | str] = {}
     for raw_key, raw_value in raw.items():
         key = _require_string(raw_key, f"{label} key")
-        if not isinstance(raw_value, (bool, str)):
+        if isinstance(raw_value, bool):
+            result[key] = raw_value
+        elif isinstance(raw_value, str):
+            result[key] = _require_string(raw_value, f"{label}[{key!r}]")
+        else:
             raise TypeError(f"{label}[{key!r}] must be a boolean or string")
-        result[key] = raw_value
     return result
 
 
 def _manifest_boolean(value: Any, label: str) -> bool:
     if not isinstance(value, bool):
         raise TypeError(f"{label} must be a boolean")
     return value
 
 
 @dataclass(frozen=True)
 class _CommandManifest:
     schema_version: int
     id: str
     name: str
     version: str
     protocol_version: int
     command: tuple[str, ...]
     operations: tuple[str, ...]
     description: str | None = None
     capabilities: dict[str, Any] = field(default_factory=dict)
     required_permissions: tuple[str, ...] = ()
     required_binaries: tuple[str, ...] = ()
     timeout_seconds: int | None = None
     metadata: dict[str, str] = field(default_factory=dict)
 
     REQUIRED_OPERATION: ClassVar[str]
     ALLOWED_OPERATIONS: ClassVar[frozenset[str]]
     LABEL: ClassVar[str]
 
     @classmethod
     def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
         return _json_safe_mapping(value, label=f"{cls.LABEL} capabilities")
 
     def __post_init__(self) -> None:
         version = _require_int(self.schema_version, "schema_version")
         if version != SCHEMA_VERSION:
             _protocol_failure(
                 f"unknown {self.LABEL} schema_version {version}; expected {SCHEMA_VERSION}",
                 details={"received": version, "supported": [SCHEMA_VERSION]},
             )
         object.__setattr__(self, "schema_version", version)
         object.__setattr__(self, "id", _require_qualified_id(self.id, f"{self.LABEL} id"))
         object.__setattr__(self, "name", _require_string(self.name, f"{self.LABEL} name"))
         object.__setattr__(self, "version", _require_string(self.version, f"{self.LABEL} version"))
         protocol_version = _require_int(self.protocol_version, "protocol_version")
         if protocol_version != SCHEMA_VERSION:
             _protocol_failure(
                 f"unsupported {self.LABEL} protocol_version {protocol_version}; "
                 f"expected {SCHEMA_VERSION}",
                 details={"received": protocol_version, "supported": [SCHEMA_VERSION]},
             )
         object.__setattr__(self, "protocol_version", protocol_version)
         command = tuple(_require_string_list(self.command, "command"))
         if not command:
             raise ValueError("command must contain at least one argument")
         object.__setattr__(self, "command", command)
         operations = tuple(_require_string_list(self.operations, "operations"))
         if self.REQUIRED_OPERATION not in operations:
             raise ValueError(f"{self.LABEL} operations must include {self.REQUIRED_OPERATION!r}")
         unknown_operations = sorted(set(operations) - self.ALLOWED_OPERATIONS)
         if unknown_operations:
             raise ValueError(
                 f"{self.LABEL} has unsupported operations: {', '.join(unknown_operations)}"
             )
         if len(operations) != len(set(operations)):
             raise ValueError("operations must not contain duplicates")
         object.__setattr__(self, "operations", operations)
         object.__setattr__(
             self,
             "description",
             _require_optional_string(self.description, "description"),
         )
         object.__setattr__(
             self,
             "capabilities",
             self._normalize_capabilities(self.capabilities),
         )
         permissions = tuple(_require_string_list(self.required_permissions, "required_permissions"))
         unknown_permissions = sorted(set(permissions) - _PERMISSIONS)
         if unknown_permissions:
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 85bbd9b..6a96b91 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -1,213 +1,221 @@
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
+    _require_sha256,
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
-                raw = _json_safe_mapping(profile, label="artifact")
-                attachments = {
-                    name: {
-                        "path": str(att.get("path")),
-                        "kind": str(att.get("kind")),
-                        "sha256": str(att.get("sha256")),
-                    }
-                    for name, att in (raw.get("attachments") or {}).items()
-                }
-                result[path] = {
-                    "profile": (
-                        raw["profile"]
-                        if isinstance(raw["profile"], RenderProfile)
-                        else RenderProfile.from_dict(
-                            _json_safe_mapping(raw["profile"], label="artifact profile")
-                        )
-                    ).to_dict(),
-                    "sha256": str(raw["sha256"]),
-                    "attachments": attachments,
-                }
+                result[path] = _artifact_lineage_from_mapping(profile)
             else:
-                result[path] = (
-                    profile
-                    if isinstance(profile, RenderProfile)
-                    else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
-                ).to_dict()
+                raise TypeError(
+                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
+                    "hashed lineage record {profile, sha256, attachments}; "
+                    "profile-only entries carry no output hash"
+                )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
         return [
             (
-                profile
-                if isinstance(profile, RenderProfile)
-                else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
-            ).to_dict()
+                _artifact_lineage(profile)
+                if isinstance(profile, VideoArtifact)
+                else _artifact_lineage_from_mapping(profile)
+            )
             for profile in value
         ]
     raise TypeError("artifact_profiles must be an object or array")
 
 
+def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
+    data = _json_safe_mapping(raw, label="artifact")
+    if "sha256" not in data or data["sha256"] is None:
+        raise ValueError("artifact lineage sha256 is required and must not be null")
+    profile = data["profile"]
+    attachments: dict[str, Any] = {}
+    for name, att in (data.get("attachments") or {}).items():
+        att = _json_safe_mapping(att, label=f"artifact attachment {name!r}")
+        if att.get("sha256") is None:
+            raise ValueError(f"artifact attachment {name!r} sha256 must not be null")
+        attachments[str(name)] = {
+            "path": _require_string(str(att.get("path")), f"attachment {name!r} path"),
+            "kind": _require_string(str(att.get("kind")), f"attachment {name!r} kind"),
+            "sha256": _require_sha256(str(att.get("sha256")), f"attachment {name!r} sha256"),
+        }
+    return {
+        "profile": (
+            profile
+            if isinstance(profile, RenderProfile)
+            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
+        ).to_dict(),
+        "sha256": _require_sha256(str(data["sha256"]), "artifact sha256"),
+        "attachments": attachments,
+    }
+
+
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
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 62c861c..0775c9a 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -1,835 +1,855 @@
 {
   "$schema": "http://json-schema.org/draft-07/schema#",
   "$id": "https://astrid.local/schemas/rendering/v1/finalize.json",
   "title": "Astrid finalize request v1",
   "type": "object",
   "additionalProperties": false,
   "required": [
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
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$)\\S.*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
-          "type": [
-            "object",
-            "null"
+          "anyOf": [
+            {
+              "$ref": "#/definitions/overrideRecord"
+            },
+            {
+              "type": "null"
+            }
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-                    "pattern": "^(?!.*\\u0000).*\\S.*$"
+                    "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      }
+    },
+    "overrideRecord": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": [
+        "from",
+        "to"
+      ],
+      "properties": {
+        "from": {
+          "$ref": "#/definitions/qualifiedId"
+        },
+        "to": {
+          "$ref": "#/definitions/qualifiedId"
+        }
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
               "alias_chain": [
                 "example",
                 "acme.example"
               ],
               "override": null,
               "support_decision": {
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
               },
               "trust_eligibility": {
                 "eligible": true,
                 "method": "source-tree"
               }
             },
             "input_hashes": {
               "timeline": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
             }
           }
         ],
         "finalizer": {
           "id": "rendering.ffmpeg-finalizer",
           "source_pack": {
             "id": "rendering"
           },
           "manifest_digest": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
           "alias_chain": [],
           "override": null,
           "trust_eligibility": {
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index 6fff803..e889fe2 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -1,638 +1,658 @@
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
-          "type": [
-            "object",
-            "null"
+          "anyOf": [
+            {
+              "$ref": "#/definitions/overrideRecord"
+            },
+            {
+              "type": "null"
+            }
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
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
+    },
+    "overrideRecord": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": [
+        "from",
+        "to"
+      ],
+      "properties": {
+        "from": {
+          "$ref": "#/definitions/qualifiedId"
+        },
+        "to": {
+          "$ref": "#/definitions/qualifiedId"
+        }
+      }
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
             "alias_chain": [
               "example",
               "acme.example"
             ],
             "override": null,
             "support_decision": {
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
             },
             "trust_eligibility": {
               "eligible": true,
               "method": "source-tree"
             }
           },
           "input_hashes": {
             "timeline": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
           }
         }
       ],
       "finalizer": {
         "id": "rendering.ffmpeg-finalizer",
         "source_pack": {
           "id": "rendering"
         },
         "manifest_digest": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
         "alias_chain": [],
         "override": null,
         "trust_eligibility": {
           "eligible": true,
           "method": "source-tree"
         },

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '1,320p' && nl -ba astrid/core/rendering/contracts.py | sed -n '1,260p' && nl -ba astrid/core/rendering/contracts.py | sed -n '900,1360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   157	
   158	def _normalize_v1_compatibility(
   159	    fields: Mapping[str, Any] | None,
   160	) -> dict[str, Any]:
   161	    if fields is None:
   162	        raise ValueError(
   163	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   164	        )
   165	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   166	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   167	    if unknown:
   168	        raise ValueError(
   169	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   170	            + ", ".join(unknown)
   171	        )
   172	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   173	    if missing:
   174	        raise ValueError(
   175	            "v1 compatibility projection is missing always-emitted fields: "
   176	            + ", ".join(missing)
   177	        )
   178	    return compatibility
   179	
   180	
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
   247	    return _json_safe_mapping(payload, label="provenance")
   248	
   249	
   250	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   251	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   252	
   253	    return assemble_provenance_v2(**kwargs)
   254	
   255	
   256	def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
   257	    """Assemble and atomically write a provenance v2 sidecar."""
   258	
   259	    payload = assemble_provenance_v2(**kwargs)
   260	    write_json_atomic(path, payload)
   261	    return payload
   262	
   263	
   264	def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
   265	    """Return stable SHA-256 input hashes using Astrid's shared helper."""
   266	
   267	    return {
   268	        _require_string(name, "input hash name"): sha256_file(Path(path))
   269	        for name, path in paths.items()
   270	    }
   271	
   272	
   273	def digest_manifest(path: str | Path) -> str:
   274	    """Return the SHA-256 digest used to pin one static manifest."""
   275	
   276	    return sha256_file(Path(path))
   277	
   278	
   279	__all__ = [
   280	    "CORE_OWNED_KEYS",
   281	    "PROVENANCE_SCHEMA_VERSION",
   282	    "assemble_provenance",
   283	    "assemble_provenance_v2",
   284	    "digest_manifest",
   285	    "hash_input_files",
   286	    "validate_backend_fragments",
   287	    "write_provenance_v2",
   288	]
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
   991	    id: str
   992	    source_pack: dict[str, Any]
   993	    manifest_digest: str
   994	    trust_eligibility: dict[str, Any]
   995	    alias_chain: list[str] = field(default_factory=list)
   996	    override: dict[str, Any] | None = None
   997	    support_decision: SupportReport | None = None
   998	
   999	    def __post_init__(self) -> None:
  1000	        object.__setattr__(self, "id", _require_qualified_id(self.id, "planner id"))
  1001	        object.__setattr__(
  1002	            self,
  1003	            "source_pack",
  1004	            _json_safe_mapping(self.source_pack, label="planner source_pack"),
  1005	        )
  1006	        object.__setattr__(
  1007	            self,
  1008	            "manifest_digest",
  1009	            _require_sha256(self.manifest_digest, "planner manifest_digest"),
  1010	        )
  1011	        object.__setattr__(
  1012	            self,
  1013	            "trust_eligibility",
  1014	            _json_safe_mapping(
  1015	                self.trust_eligibility,
  1016	                label="planner trust_eligibility",
  1017	            ),
  1018	        )
  1019	        object.__setattr__(
  1020	            self,
  1021	            "alias_chain",
  1022	            [
  1023	                _require_string(item, f"planner alias_chain[{index}]")
  1024	                for index, item in enumerate(_require_string_list(self.alias_chain, "planner alias_chain"))
  1025	            ],
  1026	        )
  1027	        if self.override is not None:
  1028	            object.__setattr__(
  1029	                self,
  1030	                "override",
  1031	                _require_override(
  1032	                    self.override,
  1033	                    capability_id=self.id,
  1034	                    label="planner override",
  1035	                ),
  1036	            )
  1037	        if self.support_decision is not None:
  1038	            support = (
  1039	                self.support_decision
  1040	                if isinstance(self.support_decision, SupportReport)
  1041	                else SupportReport.from_dict(
  1042	                    _require_mapping(
  1043	                        self.support_decision, "planner support_decision"
  1044	                    )
  1045	                )
  1046	            )
  1047	            if support.backend != self.id:
  1048	                raise ValueError("planner support_decision.backend must match planner id")
  1049	            object.__setattr__(self, "support_decision", support)
  1050	
  1051	    def to_dict(self) -> dict[str, Any]:
  1052	        return _json_safe_mapping(
  1053	            {
  1054	                "id": self.id,
  1055	                "source_pack": self.source_pack,
  1056	                "manifest_digest": self.manifest_digest,
  1057	                "trust_eligibility": self.trust_eligibility,
  1058	                "alias_chain": list(self.alias_chain),
  1059	                "override": self.override,
  1060	                "support_decision": self.support_decision,
  1061	            }
  1062	        )
  1063	
  1064	    @classmethod
  1065	    def from_dict(cls, payload: Mapping[str, Any]) -> PlannerResolution:
  1066	        data = _require_mapping(payload, "planner resolution")
  1067	        required = {
  1068	            "id",
  1069	            "source_pack",
  1070	            "manifest_digest",
  1071	            "trust_eligibility",
  1072	            "alias_chain",
  1073	            "override",
  1074	            "support_decision",
  1075	        }
  1076	        _validate_object_keys(data, required=required, allowed=required, label="planner resolution")
  1077	        return cls(
  1078	            id=data["id"],
  1079	            source_pack=data["source_pack"],
  1080	            manifest_digest=data["manifest_digest"],
  1081	            trust_eligibility=data["trust_eligibility"],
  1082	            alias_chain=data["alias_chain"],
  1083	            override=data["override"],
  1084	            support_decision=data["support_decision"],
  1085	        )
  1086	
  1087	
  1088	@dataclass(frozen=True)
  1089	class RendererResolution:
  1090	    """Resolved renderer identity and request-sensitive routing evidence."""
  1091	
  1092	    id: str
  1093	    source_pack: dict[str, Any]
  1094	    manifest_digest: str
  1095	    alias_chain: list[str]
  1096	    override: dict[str, Any] | None
  1097	    support_decision: SupportReport
  1098	    trust_eligibility: dict[str, Any] = field(default_factory=dict)
  1099	
  1100	    def __post_init__(self) -> None:
  1101	        renderer_id = _require_qualified_id(self.id, "renderer id")
  1102	        support = (
  1103	            self.support_decision
  1104	            if isinstance(self.support_decision, SupportReport)
  1105	            else SupportReport.from_dict(
  1106	                _require_mapping(self.support_decision, "renderer support_decision")
  1107	            )
  1108	        )
  1109	        if support.backend != renderer_id:
  1110	            raise ValueError("renderer support_decision.backend must match renderer id")
  1111	        object.__setattr__(self, "id", renderer_id)
  1112	        object.__setattr__(
  1113	            self,
  1114	            "source_pack",
  1115	            _json_safe_mapping(self.source_pack, label="renderer source_pack"),
  1116	        )
  1117	        object.__setattr__(
  1118	            self,
  1119	            "manifest_digest",
  1120	            _require_sha256(self.manifest_digest, "renderer manifest_digest"),
  1121	        )
  1122	        object.__setattr__(
  1123	            self,
  1124	            "trust_eligibility",
  1125	            _json_safe_mapping(
  1126	                self.trust_eligibility,
  1127	                label="renderer trust_eligibility",
  1128	            ),
  1129	        )
  1130	        aliases = [
  1131	            _require_string(alias, f"renderer alias_chain[{index}]")
  1132	            for index, alias in enumerate(_require_string_list(self.alias_chain, "renderer alias_chain"))
  1133	        ]
  1134	        if len(aliases) != len(set(aliases)):
  1135	            raise ValueError("renderer alias_chain must not contain duplicates")
  1136	        object.__setattr__(self, "alias_chain", aliases)
  1137	        object.__setattr__(
  1138	            self,
  1139	            "override",
  1140	            None
  1141	            if self.override is None
  1142	            else _require_override(
  1143	                self.override,
  1144	                capability_id=renderer_id,
  1145	                label="renderer override",
  1146	            ),
  1147	        )
  1148	        object.__setattr__(self, "support_decision", support)
  1149	
  1150	    def to_dict(self) -> dict[str, Any]:
  1151	        return _json_safe_mapping(
  1152	            {
  1153	                "id": self.id,
  1154	                "source_pack": self.source_pack,
  1155	                "manifest_digest": self.manifest_digest,
  1156	                "alias_chain": self.alias_chain,
  1157	                "override": self.override,
  1158	                "support_decision": self.support_decision,
  1159	                "trust_eligibility": self.trust_eligibility,
  1160	            }
  1161	        )
  1162	
  1163	    @classmethod
  1164	    def from_dict(cls, payload: Mapping[str, Any]) -> RendererResolution:
  1165	        data = _require_mapping(payload, "renderer resolution")
  1166	        required = {
  1167	            "id",
  1168	            "source_pack",
  1169	            "manifest_digest",
  1170	            "alias_chain",
  1171	            "override",
  1172	            "support_decision",
  1173	            "trust_eligibility",
  1174	        }
  1175	        _validate_object_keys(data, required=required, allowed=required, label="renderer resolution")
  1176	        return cls(
  1177	            id=data["id"],
  1178	            source_pack=data["source_pack"],
  1179	            manifest_digest=data["manifest_digest"],
  1180	            alias_chain=data["alias_chain"],
  1181	            override=data["override"],
  1182	            support_decision=SupportReport.from_dict(data["support_decision"]),
  1183	            trust_eligibility=data["trust_eligibility"],
  1184	        )
  1185	
  1186	
  1187	@dataclass(frozen=True)
  1188	class FinalizerResolution:
  1189	    """Resolved finalizer identity pinned for standalone finalization."""
  1190	
  1191	    id: str
  1192	    source_pack: dict[str, Any]
  1193	    manifest_digest: str
  1194	    alias_chain: list[str] = field(default_factory=list)
  1195	    override: dict[str, Any] | None = None
  1196	    trust_eligibility: dict[str, Any] = field(default_factory=dict)
  1197	    support_decision: SupportReport | None = None
  1198	
  1199	    def __post_init__(self) -> None:
  1200	        object.__setattr__(self, "id", _require_qualified_id(self.id, "finalizer id"))
  1201	        object.__setattr__(
  1202	            self,
  1203	            "source_pack",
  1204	            _json_safe_mapping(self.source_pack, label="finalizer source_pack"),
  1205	        )
  1206	        object.__setattr__(
  1207	            self,
  1208	            "manifest_digest",
  1209	            _require_sha256(self.manifest_digest, "finalizer manifest_digest"),
  1210	        )
  1211	        object.__setattr__(
  1212	            self,
  1213	            "trust_eligibility",
  1214	            _json_safe_mapping(
  1215	                self.trust_eligibility,
  1216	                label="finalizer trust_eligibility",
  1217	            ),
  1218	        )
  1219	        object.__setattr__(
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

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '480,820p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '820,1080p' && nl -ba tests/core/rendering/test_registry_matrix.py | sed -n '440,700p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   480	def test_finalize_rejects_dropped_or_changed_attachments() -> None:
   481	    attachment = _attachment("project.blend")
   482	    request = _finalize(artifacts=[_video(attachments={attachment.name: attachment})])
   483	    with pytest.raises(ValueError, match="dropped attachments"):
   484	        request.validate_final_result(_result())
   485	
   486	    changed = _attachment("project.blend", sha256=SHA_C)
   487	    with pytest.raises(ValueError, match="changed attachments"):
   488	        request.validate_final_result(_result(video=_video(attachments={changed.name: changed})))
   489	
   490	
   491	def test_attachment_mapping_key_must_match_name() -> None:
   492	    with pytest.raises(ValueError, match="must match attachment.name"):
   493	        _video(attachments={"other.blend": _attachment("project.blend")})
   494	
   495	
   496	@pytest.mark.parametrize(
   497	    "path",
   498	    [
   499	        "../escape.mp4",
   500	        "outputs/../../escape.mp4",
   501	        "outputs/./escape.mp4",
   502	        "outputs//escape.mp4",
   503	        "outputs/",
   504	        "/tmp/escape.mp4",
   505	        "C:escape.mp4",
   506	        r"C:\\temp\\escape.mp4",
   507	        r"\\\\server\\share\\escape.mp4",
   508	    ],
   509	)
   510	def test_artifact_path_traversal_and_windows_drives_rejected(path: str) -> None:
   511	    with pytest.raises(ValueError, match="workspace|contained|relative"):
   512	        _video(path=path)
   513	
   514	
   515	def test_backend_fragment_cannot_overwrite_current_or_retired_core_keys() -> None:
   516	    for key in ("output", "planner", "resolved_backend", "request_digest"):
   517	        with pytest.raises(ValueError, match=f"core-owned keys: {key}"):
   518	            validate_backend_fragments({"acme.example": {key: "stolen"}})
   519	
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
   692	        artifact_profiles={},
   693	        audio_ownership="rendered",
   694	        normalization=[],
   695	        attachments={},
   696	        backend_fragments={},
   697	        v1_compatibility=_compatibility(),
   698	    )
   699	    assert payload["planner"]["alias_chain"] == planner.alias_chain
   700	    assert payload["planner"]["override"] == planner.override
   701	    assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
   702	    assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
   703	    assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
   704	    assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
   705	
   706	
   707	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   708	    """Every capability resolution requires the complete evidence set;
   709	    a missing key is a structural protocol failure."""
   710	def test_resolution_records_require_all_seven_evidence_keys() -> None:
   711	    """Every capability resolution requires the complete evidence set;
   712	    a missing key is a structural protocol failure."""
   713	    cases = (
   714	        (_planner(), PlannerResolution.from_dict),
   715	        (_finalizer(), FinalizerResolution.from_dict),
   716	        (_renderer(), RendererResolution.from_dict),
   717	    )
   718	    for obj, parser in cases:
   719	        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
   720	            broken = obj.to_dict()
   721	            del broken[missing]
   722	            with pytest.raises(ValueError, match="missing required fields"):
   723	                parser(broken)
   724	
   725	
   726	def test_provenance_emits_hashed_artifact_lineage() -> None:
   727	    """Provenance records per-artifact sha256 and attachment hashes, not
   728	    just profiles — so replay can verify rendered outputs byte-for-byte."""
   729	    artifact = VideoArtifact(
   730	        path="outputs/visual.mp4",
   731	        profile=_profile(),
   732	        sha256=SHA_B,
   733	        duration_frames=48,
   734	        audio=AudioOwnership.RENDERED,
   735	        attachments={
   736	            "alpha": Attachment(
   737	                name="alpha",
   738	                path="outputs/alpha.mp4",
   739	                kind="alpha",
   740	                sha256=SHA_C,
   741	            )
   742	        },
   743	    )
   744	    payload = assemble_provenance_v2(
   745	        engine="hybrid",
   746	        output="/workspace/out/video.mp4",
   747	        timeline="/workspace/timeline.json",
   748	        assets_registry=None,
   749	        plan=_plan(),
   750	        artifact_profiles={"outputs/visual.mp4": artifact},
   751	        audio_ownership="rendered",
   752	        normalization=[],
   753	        attachments={},
   754	        backend_fragments={},
   755	        v1_compatibility=_compatibility(),
   756	    )
   757	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
   758	    assert lineage["sha256"] == SHA_B
   759	    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
   760	    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
   761	
   762	
   763	def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
   764	    """support_decision.backend must equal the resolution id for planner and
   765	    finalizer, exactly as it does for renderer."""
   766	    cases = (
   767	        (_planner, "planner"),
   768	        (_finalizer, "finalizer"),
   769	        (_renderer, "renderer"),
   770	    )
   771	    for factory, label in cases:
   772	        payload = factory().to_dict()
   773	        payload["support_decision"] = _support("other.backend").to_dict()
   774	        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
   775	            type(factory()).from_dict(payload)
   776	
   777	
   778	def test_resolutions_reject_incoherent_override_records() -> None:
   779	    """Override records must be {from, to} with to == resolution id."""
   780	    cases = (
   781	        (_planner, "planner"),
   782	        (_finalizer, "finalizer"),
   783	        (_renderer, "renderer"),
   784	    )
   785	    for factory, label in cases:
   786	        payload = factory().to_dict()
   787	        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
   788	        with pytest.raises(ValueError, match=f"{label} override 'to'"):
   789	            type(factory()).from_dict(payload)
   790	        payload["override"] = {"only": "one"}
   791	        with pytest.raises(ValueError, match=f"{label} override"):
   792	            type(factory()).from_dict(payload)
   793	
   794	
   795	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   796	    """Artifact lineage must carry a real sha256; profile-only entries and
   797	    null hashes are rejected rather than stringified."""
   798	    base = dict(
   799	        engine="hybrid",
   800	        output="/workspace/out/video.mp4",
   801	        timeline="/workspace/timeline.json",
   802	        assets_registry=None,
   803	        plan=_plan(),
   804	        audio_ownership="rendered",
   805	        normalization=[],
   806	        attachments={},
   807	        backend_fragments={},
   808	        v1_compatibility=_compatibility(),
   809	    )
   810	    with pytest.raises(TypeError, match="hashed lineage"):
   811	        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
   812	    with pytest.raises(ValueError, match="sha256"):
   813	        assemble_provenance_v2(
   814	            **base,
   815	            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
   816	        )
   817	    with pytest.raises(ValueError, match="sha256"):
   818	        assemble_provenance_v2(
   819	            **base,
   820	            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
   820	            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
   821	        )
   822	
   823	
   824	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
   825	    plan = _plan(
   826	        segments=[_segment(12, 24), _segment(24, 36)],
   827	        total_frames=48,
   828	        window=_window(12, 36),
   829	    )
   830	    assert plan.total_frames == 48
   831	    assert plan.window == _window(12, 36)
   832	
   833	
   834	@pytest.mark.parametrize(
   835	    ("segments", "total_frames", "match"),
   836	    [
   837	        ([_segment(1, 48)], 48, "gap"),
   838	        ([_segment(0, 47)], 48, "trailing gap"),
   839	        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
   840	        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
   841	        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
   842	    ],
   843	)
   844	def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
   845	    segments: list[RenderSegment],
   846	    total_frames: int,
   847	    match: str,
   848	) -> None:
   849	    with pytest.raises(ValueError, match=match):
   850	        _plan(segments=segments, total_frames=total_frames)
   851	
   852	
   853	def test_plan_rejects_noncanonical_segment_or_window_fps() -> None:
   854	    with pytest.raises(ValueError, match="segment.*FPS"):
   855	        _plan(segments=[_segment(fps=(48, 2))])
   856	    with pytest.raises(ValueError, match="window FPS"):
   857	        _plan(window=_window(0, 48, fps=(48, 2)))
   858	
   859	
   860	def test_zero_frame_plan_semantics_and_no_finalization() -> None:
   861	    empty = _plan(segments=[], total_frames=0, profile=_profile(audio=False))
   862	    assert empty.segments == []
   863	    assert empty.reasons == {}
   864	    with pytest.raises(ValueError, match="zero-frame plan"):
   865	        _plan(segments=[_segment()], total_frames=0)
   866	    with pytest.raises(ValueError, match="positive-frame plan"):
   867	        _plan(segments=[], total_frames=48)
   868	    with pytest.raises(ValueError, match="must not be finalized"):
   869	        _finalize(plan=empty, artifacts=[])
   870	
   871	
   872	def test_qualified_id_grammar_allows_hyphens_and_underscores() -> None:
   873	    assert _finalizer().id == "rendering.ffmpeg-finalizer"
   874	    assert replace(_finalizer(), id="1render.2-finalizer",
   875	                   support_decision=_support("1render.2-finalizer")).id == "1render.2-finalizer"
   876	    assert replace(_finalizer(), id="rendering.legacy_hybrid",
   877	                   support_decision=_support("rendering.legacy_hybrid")).id == "rendering.legacy_hybrid"
   878	    assert replace(_finalizer(), id="acme.bad_id",
   879	                   support_decision=_support("acme.bad_id")).id == "acme.bad_id"
   880	    for invalid in (
   881	        "Rendering.Ffmpeg",
   882	        "rendering.-finalizer",
   883	        "unqualified",
   884	    ):
   885	        with pytest.raises(ValueError, match="qualified id"):
   886	            replace(_finalizer(), id=invalid, support_decision=_support(invalid))
   887	
   888	
   889	def test_contracts_are_frozen() -> None:
   890	    window = _window()
   891	    with pytest.raises(FrozenInstanceError):
   892	        window.start_frame = 1  # type: ignore[misc]
   893	
   894	
   895	def test_manifest_round_trip() -> None:
   896	    common = {
   897	        "schema_version": 1,
   898	        "name": "Example",
   899	        "version": "1.0.0",
   900	        "protocol_version": 1,
   901	        "command": ["python3", "backend.py"],
   902	        "description": "Example implementation",
   903	        "capabilities": {"features": {"media": True}},
   904	        "required_permissions": ["project_files"],
   905	        "required_binaries": [],
   906	        "timeout_seconds": 60,
   907	        "metadata": {"vendor": "Acme"},
   908	    }
   909	    cases = [
   910	        (RendererManifest, {**common, "id": "acme.renderer", "operations": ["render", "support"]}),
   911	        (PlannerManifest, {**common, "id": "acme.planner", "operations": ["plan"]}),
   912	        (FinalizerManifest, {**common, "id": "acme.finalizer", "operations": ["finalize"]}),
   913	    ]
   914	    for manifest_type, payload in cases:
   915	        assert manifest_type.from_dict(payload).to_dict() == payload
   916	
   917	
   918	def test_manifest_dto_rejects_schema_invalid_capabilities_and_scalar_command() -> None:
   919	    base = {
   920	        "schema_version": 1,
   921	        "id": "acme.renderer",
   922	        "name": "Example",
   923	        "version": "1.0.0",
   924	        "protocol_version": 1,
   925	        "operations": ["render"],
   926	    }
   927	    with pytest.raises(RendererProtocolError):
   928	        RendererManifest.from_dict(
   929	            {**base, "command": ["python3"], "capabilities": {"unknown": True}}
   930	        )
   931	    with pytest.raises(RendererProtocolError):
   932	        RendererManifest.from_dict({**base, "command": "python3"})
   440	    renderers, _, _ = _load_env_registries(tmp_path / "project")
   441	
   442	    inspected = renderers.inspect("env_render.legacy")
   443	    assert len(inspected) == 1
   444	    assert inspected[0].manifest.name == "Environment Fixture Renderer"
   445	    assert inspected[0].source_kind == "env"
   446	
   447	    assert renderers.candidates("env_render.legacy", eligible=True) == ()
   448	    with pytest.raises(RendererRegistryError) as caught:
   449	        renderers.get("env_render.legacy")
   450	    assert caught.value.code == "unknown_capability"
   451	    with pytest.raises(RendererRegistryError) as evidence_caught:
   452	        renderers.resolve_evidence("env_render.legacy")
   453	    assert evidence_caught.value.code == "unknown_capability"
   454	
   455	
   456	# ---------------------------------------------------------------------------
   457	# Override matrix
   458	# ---------------------------------------------------------------------------
   459	
   460	
   461	def test_override_to_discovered_ineligible_target_fails_closed(tmp_path: Path) -> None:
   462	    """Overriding onto a discoverable-but-ineligible target is rejected.
   463	
   464	    The override lands on an env-layer renderer that can never be executed;
   465	    resolution fails with a structured error that records the override that
   466	    caused the redirect.
   467	    """
   468	    store = OverrideStore(tmp_path / "project")
   469	    store.set_override("renderer", "rendering.remotion", "env_render.renderer")
   470	
   471	    renderers, _, _ = _load_env_registries(tmp_path / "project")
   472	
   473	    with pytest.raises(RendererRegistryError) as caught:
   474	        renderers.get("rendering.remotion")
   475	
   476	    assert caught.value.code == "execution_ineligible"
   477	    details = caught.value.to_dict()["details"]
   478	    assert details["override"] == {
   479	        "from": "rendering.remotion",
   480	        "to": "env_render.renderer",
   481	    }
   482	    assert details["target_id"] == "env_render.renderer"
   483	    assert details["canonical_id"] == "rendering.remotion"
   484	
   485	
   486	def _write_alias_to_absent_pack(packs_root: Path) -> Path:
   487	    """A source pack whose renderer alias points at a canonical in ANOTHER
   488	    pack namespace that does not exist in the discovery tree. Cross-pack
   489	    alias targets are not statically checked (validate.py only validates
   490	    same-pack targets), so this pack passes validate_pack and can be
   491	    installed, while resolution still requires the override to supply the
   492	    implementation."""
   493	    pack_root = _write_renderer_pack(
   494	        packs_root,
   495	        "alias_missing",
   496	        renderer_name="Alias Missing Renderer",
   497	        renderer_id="alias_missing.renderer",
   498	    )
   499	    pack_yaml = pack_root / "pack.yaml"
   500	    lines = pack_yaml.read_text(encoding="utf-8").splitlines()
   501	    alias_block = [
   502	        "aliases:",
   503	        "  - kind: renderer",
   504	        "    alias: alias_missing.legacy",
   505	        "    canonical_id: other.abstract.renderer",
   506	    ]
   507	    # insert aliases before extensions
   508	    idx = next(i for i, line in enumerate(lines) if line.startswith("extensions:"))
   509	    lines[idx:idx] = alias_block
   510	    pack_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
   511	    return pack_root
   512	
   513	
   514	def test_trusted_pack_alias_to_absent_canonical_routes_through_override(
   515	    tmp_path: Path,
   516	) -> None:
   517	    """A pack-declared alias whose canonical is absent still routes through
   518	    an override to an executable implementation.
   519	
   520	    The frozen ordering is alias -> canonical -> override: a missing canonical
   521	    must not silently drop a trusted pack alias when an override supplies the
   522	    implementation.
   523	    """
   524	    project_root = tmp_path / "project"
   525	    source_root = tmp_path / "source"
   526	    source_root.mkdir()
   527	    pack_root = _write_alias_to_absent_pack(source_root)
   528	
   529	    # The cross-pack alias must pass static pack validation (the same-pack
   530	    # target rule does not apply) so the pack remains installable.
   531	    from astrid.core.pack.validate import validate_pack
   532	    from astrid.core.pack.install_local import install_pack
   533	    from astrid.core.pack.store import InstalledPackStore
   534	
   535	    errors, warnings = validate_pack(str(pack_root))
   536	    assert not errors, errors
   537	
   538	    astrid_home = tmp_path / "astrid-home"
   539	    empty_source = tmp_path / "empty-source"
   540	    empty_source.mkdir()
   541	    store = InstalledPackStore(astrid_home / "packs")
   542	    exit_code = install_pack(
   543	        pack_root,
   544	        store=store,
   545	        dry_run=False,
   546	        skip_confirm=True,
   547	        trust_acknowledged=True,
   548	        trust_method="test",
   549	        trust_actor="test",
   550	    )
   551	    assert exit_code == 0, f"install failed with exit {exit_code}"
   552	
   553	    override_store = OverrideStore(project_root)
   554	    override_store.set_override("renderer", "other.abstract.renderer", "alias_missing.renderer")
   555	
   556	    # Resolve from the INSTALLED revision (include_installed=True, empty
   557	    # source tree) so the override route is proven on the installed pack.
   558	    with (
   559	        mock.patch.dict(
   560	            os.environ,
   561	            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
   562	            clear=False,
   563	        ),
   564	        mock.patch(
   565	            "astrid.core.rendering.registry.discover_packs",
   566	            side_effect=_scanner(empty_source),
   567	        ),
   568	    ):
   569	        renderers, _, _ = load_default_registries(project_root, include_installed=True)
   570	
   571	    candidate = renderers.get("alias_missing.legacy")
   572	    assert candidate.id == "alias_missing.renderer"
   573	    assert candidate.source_kind == "installed"
   574	    assert candidate.execution_eligible is True
   575	
   576	    evidence = renderers.resolve_evidence("alias_missing.legacy")
   577	    assert evidence["canonical_id"] == "other.abstract.renderer"
   578	    assert evidence["resolved_id"] == "alias_missing.renderer"
   579	    assert evidence["override"] == {
   580	        "from": "other.abstract.renderer",
   581	        "to": "alias_missing.renderer",
   582	    }
   583	
   584	
   585	def test_trusted_pack_alias_to_absent_canonical_without_override_fails_closed(
   586	    tmp_path: Path,
   587	) -> None:
   588	    """Without an override, a pack alias to an absent canonical is dropped
   589	    and resolution reports the missing target."""
   590	    project_root = tmp_path / "project"
   591	    source_root = tmp_path / "source"
   592	    source_root.mkdir()
   593	    _write_alias_to_absent_pack(source_root)
   594	
   595	    with _load_with_source(project_root, source_root=source_root) as (renderers, _, _):
   596	        with pytest.raises(RendererRegistryError) as caught:
   597	            renderers.get("alias_missing.legacy")
   598	        assert caught.value.code == "unknown_capability"
   599	        with pytest.raises(RendererRegistryError) as evidence_caught:
   600	            renderers.resolve_evidence("alias_missing.legacy")
   601	        assert evidence_caught.value.code == "unknown_capability"
   602	
   603	
   604	# ---------------------------------------------------------------------------
   605	# Eligibility matrix
   606	# ---------------------------------------------------------------------------
   607	
   608	
   609	def test_env_candidate_cannot_shadow_eligible_extra_in_natural_discovery_order(
   610	    tmp_path: Path,
   611	) -> None:
   612	    """An env-layer candidate stays out of the executable registry.
   613	
   614	    When an eligible extra-root pack and an ineligible env pack declare the
   615	    same renderer id, only the extra pack is ever executable — the env
   616	    candidate remains discoverable and inspectable but contributes no
   617	    conflict and cannot be selected.
   618	    """
   619	    extra_root = tmp_path / "extra"
   620	    env_root = tmp_path / "env"
   621	    _write_renderer_pack(extra_root, "sharedrender", renderer_name="Extra Eligible")
   622	    _write_renderer_pack(env_root, "sharedrender", renderer_name="Env Ineligible")
   623	
   624	    empty_source = tmp_path / "empty-source"
   625	    empty_source.mkdir(exist_ok=True)
   626	    with (
   627	        mock.patch(
   628	            "astrid.core.rendering.registry.discover_packs",
   629	            side_effect=_scanner(empty_source),
   630	        ),
   631	        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": str(env_root)}, clear=False),
   632	    ):
   633	        renderers, _, _ = load_default_registries(
   634	            tmp_path / "project",
   635	            extra_pack_roots=(str(extra_root),),
   636	            include_installed=False,
   637	        )
   638	
   639	    winner = renderers.get("sharedrender.renderer")
   640	    assert winner.manifest.name == "Extra Eligible"
   641	    assert winner.source_kind == "extra"
   642	    assert winner.priority_index == 0
   643	    assert renderers.conflicts() == ()
   644	    assert [
   645	        (candidate.manifest.name, candidate.source_kind, candidate.execution_eligible)
   646	        for candidate in renderers.candidates("sharedrender.renderer")
   647	    ] == [
   648	        ("Extra Eligible", "extra", True),
   649	        ("Env Ineligible", "env", False),
   650	    ]
   651	
   652	
   653	def test_installed_pack_with_unaccepted_permissions_fails_closed(
   654	    tmp_path: Path,
   655	) -> None:
   656	    """An install record that accepted no permissions is not trustworthy.
   657	
   658	    The fixture pack declares ``subprocess`` and the manifest requires it,
   659	    but the install record's accepted-permission list is empty — the trust
   660	    audit cannot be validated, so the candidate is inspectable only.
   661	    """
   662	    astrid_home = tmp_path / "astrid-home"
   663	    empty_source = tmp_path / "empty-source"
   664	    empty_source.mkdir(exist_ok=True)
   665	    _stage_installed_fixture(astrid_home, "installed_render", accepted_permissions=[])
   666	
   667	    with (
   668	        mock.patch.dict(
   669	            os.environ,
   670	            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
   671	            clear=False,
   672	        ),
   673	        mock.patch(
   674	            "astrid.core.rendering.registry.discover_packs",
   675	            side_effect=_scanner(empty_source),
   676	        ),
   677	    ):
   678	        renderers, _, _ = load_default_registries(tmp_path / "project", include_installed=True)
   679	
   680	    candidate = renderers.inspect("installed_render.renderer")[0]
   681	    assert candidate.execution_eligible is False
   682	    assert "accepted permissions" in candidate.eligibility.reason
   683	    assert candidate.eligibility.accepted_permissions == ()
   684	    with pytest.raises(RendererRegistryError) as caught:
   685	        renderers.get("installed_render.renderer")
   686	    assert caught.value.code == "execution_ineligible"
   687	
   688	
   689	def test_permission_deficiency_reason_lists_all_missing_permissions_sorted(
   690	    tmp_path: Path,
   691	) -> None:
   692	    """Every undeclared required permission is named, in sorted order."""
   693	    source_root = tmp_path / "source"
   694	    _write_renderer_pack(
   695	        source_root,
   696	        "permissionrender",
   697	        renderer_name="Missing Declarations",
   698	        required_permissions=("network", "environment"),
   699	    )
   700	

exec
/bin/zsh -lc "sed -n '700,828p' tests/core/rendering/test_contracts.py && python -m py_compile tests/core/rendering/test_contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 3ms:
exec
/bin/zsh -lc "git diff --unified=30 808030e..91f0fe3 -- astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py docs/contracts/render-backend-v1.md | sed -n '1,900p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 85bbd9b..6a96b91 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -1,52 +1,53 @@
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
+    _require_sha256,
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
 
 
@@ -65,99 +66,106 @@ def _normalize_attachments(
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
-                raw = _json_safe_mapping(profile, label="artifact")
-                attachments = {
-                    name: {
-                        "path": str(att.get("path")),
-                        "kind": str(att.get("kind")),
-                        "sha256": str(att.get("sha256")),
-                    }
-                    for name, att in (raw.get("attachments") or {}).items()
-                }
-                result[path] = {
-                    "profile": (
-                        raw["profile"]
-                        if isinstance(raw["profile"], RenderProfile)
-                        else RenderProfile.from_dict(
-                            _json_safe_mapping(raw["profile"], label="artifact profile")
-                        )
-                    ).to_dict(),
-                    "sha256": str(raw["sha256"]),
-                    "attachments": attachments,
-                }
+                result[path] = _artifact_lineage_from_mapping(profile)
             else:
-                result[path] = (
-                    profile
-                    if isinstance(profile, RenderProfile)
-                    else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
-                ).to_dict()
+                raise TypeError(
+                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
+                    "hashed lineage record {profile, sha256, attachments}; "
+                    "profile-only entries carry no output hash"
+                )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
         return [
             (
-                profile
-                if isinstance(profile, RenderProfile)
-                else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
-            ).to_dict()
+                _artifact_lineage(profile)
+                if isinstance(profile, VideoArtifact)
+                else _artifact_lineage_from_mapping(profile)
+            )
             for profile in value
         ]
     raise TypeError("artifact_profiles must be an object or array")
 
 
+def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
+    data = _json_safe_mapping(raw, label="artifact")
+    if "sha256" not in data or data["sha256"] is None:
+        raise ValueError("artifact lineage sha256 is required and must not be null")
+    profile = data["profile"]
+    attachments: dict[str, Any] = {}
+    for name, att in (data.get("attachments") or {}).items():
+        att = _json_safe_mapping(att, label=f"artifact attachment {name!r}")
+        if att.get("sha256") is None:
+            raise ValueError(f"artifact attachment {name!r} sha256 must not be null")
+        attachments[str(name)] = {
+            "path": _require_string(str(att.get("path")), f"attachment {name!r} path"),
+            "kind": _require_string(str(att.get("kind")), f"attachment {name!r} kind"),
+            "sha256": _require_sha256(str(att.get("sha256")), f"attachment {name!r} sha256"),
+        }
+    return {
+        "profile": (
+            profile
+            if isinstance(profile, RenderProfile)
+            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
+        ).to_dict(),
+        "sha256": _require_sha256(str(data["sha256"]), "artifact sha256"),
+        "attachments": attachments,
+    }
+
+
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
         )
     compatibility = _json_safe_mapping(fields, label="v1_compatibility")
     unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
     if unknown:
         raise ValueError(
             "v1 compatibility projection contains non-v1 or core-owned keys: "
             + ", ".join(unknown)
         )
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 5d15754..5406c15 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -330,69 +330,71 @@ strings, and secret environment values are forbidden.
 An unsupported report should contain at least one actionable reason. Support
 is evidence, not routing authority: fallback happens only when an explicit
 planner or fallback policy permits it. Static manifest capabilities never turn
 an unsupported report into support. Every segment's required report must name
 the same backend as the segment.
 
 ## Planning
 
 `RenderPlan` is itself a versioned response. It contains required integer
 `schema_version: 1`, the SHA-256 `request_digest`, `requested_policy`, explicit
 `planner`, ordered `segments`, explicit `finalizer`, one canonical output
 `profile`, `total_frames`, `reasons`, and a nullable target `window`.
 
 `request_digest` is the SHA-256 of the canonical, JSON-normalized
 `RenderRequest` payload (sorted keys, no whitespace) that produced this plan.
 It is computed once by the planner/service and carried unchanged into
 provenance, replay bundles, and finalize requests so a replayed request can be
 verified byte-for-byte against the one that was planned.
 
 Resolution evidence has one canonical representation; ALL of the following
 keys are REQUIRED on every capability resolution record:
 
 - `planner` is `{id, source_pack, manifest_digest, trust_eligibility,
   alias_chain, override, support_decision}`;
 - every segment is `{window, renderer, input_hashes}`, where `renderer` is
   `{id, source_pack, manifest_digest, alias_chain, override,
   support_decision, trust_eligibility}`;
 - `finalizer` is `{id, source_pack, manifest_digest, alias_chain,
   override, trust_eligibility, support_decision}`.
 
-`alias_chain` is an array of strings and defaults to `[]`; `override` is an
-object or `null`; `trust_eligibility` records the derived source/install trust
-decision; `support_decision` is a versioned `SupportReport` or `null` (when no
-request-sensitive probe ran, e.g. for a finalizer). Every non-null
-`support_decision.backend` MUST equal the capability ID — the DTO rejects a
-mismatch for planner, renderer, and finalizer alike. Manifest, request, and
-input-hash values are lowercase SHA-256 digests. There is no parallel
-`segment.backend`, `segment.support`, or string-only finalizer field that
-could disagree with these records.
+`alias_chain` is an array of strings and defaults to `[]`; `override` is
+`{from, to}` with `to` equal to the resolution id (an override records what
+selected this implementation — the DTO rejects `{from, to}` shapes whose `to`
+differs, and rejects any other shape), or `null`; `trust_eligibility` records
+the derived source/install trust decision; `support_decision` is a versioned
+`SupportReport` or `null` (when no request-sensitive probe ran, e.g. for a
+finalizer). Every non-null `support_decision.backend` MUST equal the
+capability ID — the DTO rejects a mismatch for planner, renderer, and
+finalizer alike. Manifest, request, and input-hash values are lowercase
+SHA-256 digests. There is no parallel `segment.backend`, `segment.support`,
+or string-only finalizer field that could disagree with these records.
 
 `total_frames` is the complete timeline frame count. A zero-frame plan has
 `window: null`, no segments, and an empty reasons map; it is not finalized and
 does not invent a frame. A positive-frame plan has at least one segment. Its
 target is the explicit window when present, otherwise `[0,total_frames)`; an
 explicit window cannot exceed `total_frames`. The target window and every
 segment use the canonical profile's exact rational FPS (equivalent but
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
@@ -446,64 +448,66 @@ The host lifecycle is:
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
-are recorded in `artifact_profiles` as hashed lineage records: each maps an
+are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
 output path to `{profile, sha256, attachments: {name: {path, kind, sha256}}}`
-so replay can verify rendered outputs and attachments byte-for-byte.
-`input_hashes` describe inputs only, never rendered outputs.
+with a validated 64-hex `sha256` on the artifact and every attachment
+(profile-only entries and null hashes are rejected), so replay can verify
+rendered outputs byte-for-byte. `input_hashes` describe inputs only, never
+rendered outputs.
 
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
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 9bb379f..36769e5 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -537,61 +537,67 @@ def _compatibility() -> dict[str, Any]:
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
-        "artifact_profiles": {"outputs/video.mp4": _profile()},
+        "artifact_profiles": {
+            "outputs/video.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_B,
+                "attachments": {},
+            }
+        },
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
@@ -614,73 +620,73 @@ def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None
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
-        override={"from": "rendering.legacy_hybrid", "to": "acme.hybrid-planner"},
+        override={"from": "acme.hybrid-planner", "to": "rendering.legacy_hybrid"},
         support_decision=_support("rendering.legacy_hybrid"),
     )
     renderer = replace(
         _renderer("acme.visual"),
         alias_chain=["visual", "acme.visual"],
-        override={"from": "acme.visual", "to": "acme.visual-2"},
+        override={"from": "acme.visual-2", "to": "acme.visual"},
         trust_eligibility={"eligible": True, "method": "source-tree"},
     )
     finalizer = replace(
         _finalizer(),
         alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
-        override={"from": "rendering.ffmpeg-finalizer", "to": "acme.finalizer-2"},
+        override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
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
         artifact_profiles={},
@@ -742,60 +748,106 @@ def test_provenance_emits_hashed_artifact_lineage() -> None:
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
 
 
+def test_resolutions_reject_incoherent_override_records() -> None:
+    """Override records must be {from, to} with to == resolution id."""
+    cases = (
+        (_planner, "planner"),
+        (_finalizer, "finalizer"),
+        (_renderer, "renderer"),
+    )
+    for factory, label in cases:
+        payload = factory().to_dict()
+        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
+        with pytest.raises(ValueError, match=f"{label} override 'to'"):
+            type(factory()).from_dict(payload)
+        payload["override"] = {"only": "one"}
+        with pytest.raises(ValueError, match=f"{label} override"):
+            type(factory()).from_dict(payload)
+
+
+def test_provenance_rejects_spoofed_artifact_lineage() -> None:
+    """Artifact lineage must carry a real sha256; profile-only entries and
+    null hashes are rejected rather than stringified."""
+    base = dict(
+        engine="hybrid",
+        output="/workspace/out/video.mp4",
+        timeline="/workspace/timeline.json",
+        assets_registry=None,
+        plan=_plan(),
+        audio_ownership="rendered",
+        normalization=[],
+        attachments={},
+        backend_fragments={},
+        v1_compatibility=_compatibility(),
+    )
+    with pytest.raises(TypeError, match="hashed lineage"):
+        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
+    with pytest.raises(ValueError, match="sha256"):
+        assemble_provenance_v2(
+            **base,
+            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
+        )
+    with pytest.raises(ValueError, match="sha256"):
+        assemble_provenance_v2(
+            **base,
+            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},
+        )
+
+
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

exec
/bin/zsh -lc "sed -n '39110,39150p' .oracle/checkins/batch-1-r4.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
Mapped the prior reviews and completed the implementation/schema/fixture audit. Multiple acceptance blockers remain, so the checkpoint cannot pass.
  ✓ Map prior findings, incremental diff, and governing Batch 1 contract
  ✓ Audit repaired implementation and adversarial tests across all four issue areas
  ✓ Scan cumulative C1..HEAD changes for new material contract defects
  ✓ Reconcile independent reviews and issue binary verdict
codex
## ISSUES

1. **Override coherence remains unvalidated.** Planner, renderer, and finalizer accept arbitrary `override` objects without requiring `{from,to}` or `override.to == resolution.id` ([contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1013)). The round-trip test deliberately records three contradictory targets ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:641)), even though registry semantics make `override.to` the selected implementation ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:367)). Plans and provenance can therefore identify A while claiming routing selected B.

2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.

3. **Schema/DTO parity remains materially false.**

   - `workspacePath` requires its first character to be non-whitespace, rejecting DTO-valid `" outputs/video.mp4"` ([result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:300)).
   - The generic anchored pattern rejects multiline strings accepted by `_require_string`.
   - Manifest metadata and feature keys, support feature keys, and plan hash-map keys still lack matching nonblank/NUL `propertyNames` constraints ([renderer-manifest.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:95), [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:32), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:534)).
   - Conversely, manifest schemas reject blank/NUL feature-string values that `_manifest_features()` accepts ([contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1838)).

4. **The fixture does not exercise the installed revision.** Although validation and installation return success, the created `install_root` is unused and resolution calls `_load_with_source()` with `include_installed=False`, testing the source tree instead ([test_registry_matrix.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:537)). Moreover, installation records `trust_method="fixture-test"`, while installed rendering eligibility accepts only `interactive|cli_flag|api|test` ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:49)). The installed revision would be execution-ineligible if actually loaded.
tokens used
219,583
## ISSUES

1. **Override coherence remains unvalidated.** Planner, renderer, and finalizer accept arbitrary `override` objects without requiring `{from,to}` or `override.to == resolution.id` ([contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1013)). The round-trip test deliberately records three contradictory targets ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:641)), even though registry semantics make `override.to` the selected implementation ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:367)). Plans and provenance can therefore identify A while claiming routing selected B.

2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.

3. **Schema/DTO parity remains materially false.**

   - `workspacePath` requires its first character to be non-whitespace, rejecting DTO-valid `" outputs/video.mp4"` ([result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:300)).
   - The generic anchored pattern rejects multiline strings accepted by `_require_string`.
   - Manifest metadata and feature keys, support feature keys, and plan hash-map keys still lack matching nonblank/NUL `propertyNames` constraints ([renderer-manifest.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:95), [support.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:32), [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:534)).
   - Conversely, manifest schemas reject blank/NUL feature-string values that `_manifest_features()` accepts ([contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1838)).

4. **The fixture does not exercise the installed revision.** Although validation and installation return success, the created `install_root` is unused and resolution calls `_load_with_source()` with `include_installed=False`, testing the source tree instead ([test_registry_matrix.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:537)). Moreover, installation records `trust_method="fixture-test"`, while installed rendering eligibility accepts only `interactive|cli_flag|api|test` ([registry.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:49)). The installed revision would be execution-ineligible if actually loaded.

exec
/bin/zsh -lc 'for f in astrid/core/rendering/schemas/v1/*.json; do echo "$f"; rg -n '"'workspacePath|propertyNames|overrideRecord|pattern\": \"\\"'^'"\\(\\?"'!'"\\.\\*\\\\u0000\\)' \""'$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
astrid/core/rendering/schemas/v1/finalize.json
65:    "workspacePath": {
384:              "$ref": "#/definitions/overrideRecord"
437:              "$ref": "#/definitions/overrideRecord"
484:              "$ref": "#/definitions/overrideRecord"
579:          "propertyNames": {
645:          "$ref": "#/definitions/workspacePath"
658:      "propertyNames": {
676:          "$ref": "#/definitions/workspacePath"
745:      "propertyNames": {
754:      "propertyNames": {
762:    "overrideRecord": {
astrid/core/rendering/schemas/v1/finalizer-manifest.json
97:      "propertyNames": {
170:          "propertyNames": {
astrid/core/rendering/schemas/v1/plan.json
52:      "propertyNames": {
416:              "$ref": "#/definitions/overrideRecord"
469:              "$ref": "#/definitions/overrideRecord"
516:              "$ref": "#/definitions/overrideRecord"
564:    "overrideRecord": {
astrid/core/rendering/schemas/v1/planner-manifest.json
97:      "propertyNames": {
158:          "propertyNames": {
astrid/core/rendering/schemas/v1/renderer-manifest.json
97:      "propertyNames": {
164:          "propertyNames": {
astrid/core/rendering/schemas/v1/request.json
355:      "propertyNames": {
364:      "propertyNames": {
astrid/core/rendering/schemas/v1/result.json
22:    "workspacePath": {
196:          "$ref": "#/definitions/workspacePath"
209:      "propertyNames": {
227:          "$ref": "#/definitions/workspacePath"
296:      "propertyNames": {
301:        "propertyNames": {
361:      "propertyNames": {
astrid/core/rendering/schemas/v1/support.json

exec
/bin/zsh -lc "sed -n '1,120p' astrid/core/rendering/schemas/v1/result.json && sed -n '1,115p' astrid/core/rendering/schemas/v1/finalize.json && sed -n '330,390p' astrid/core/rendering/schemas/v1/request.json && sed -n '1,90p' astrid/core/rendering/schemas/v1/support.json && sed -n '70,190p' astrid/core/rendering/schemas/v1/renderer-manifest.json && sed -n '535,580p' astrid/core/rendering/schemas/v1/plan.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
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
          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
        },
        "video_codec": {
          "type": "string",
          "minLength": 1,
          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
        },
        "video_profile": {
          "type": [
            "string",
            "null"
          ],
          "minLength": 1,
          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
        },
        "video_level": {
          "type": [
            "string",
            "null"
          ],
          "minLength": 1,
          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
        },
        "pixel_format": {
          "type": "string",
          "minLength": 1,
          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
        },
        "audio_codec": {
          "type": [
            "string",
            "null"
          ],
          "minLength": 1,
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://astrid.local/schemas/rendering/v1/finalize.json",
  "title": "Astrid finalize request v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
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
      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
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
          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
            "audio_codec",
            "audio_sample_rate",
            "audio_channel_layout"
          ],
          "properties": {
            "audio_codec": {
              "type": "string",
              "minLength": 1,
              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
            },
            "audio_sample_rate": {
              "type": "integer",
              "minimum": 1
            },
            "audio_channel_layout": {
              "type": "string",
              "minLength": 1,
              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
      },
      "additionalProperties": {
        "type": "string",
        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
      },
      "additionalProperties": {
        "type": "string",
        "minLength": 1,
        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
          },
          "uniqueItems": true
        },
        "track_types": {
          "type": "array",
          "items": {
            "type": "string",
            "minLength": 1,
            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
              }
            ]
          },
          "propertyNames": {
            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
        }
      }
    },
    "hashMap": {
      "type": "object",
      "additionalProperties": {
        "$ref": "#/definitions/sha256"
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

exec
/bin/zsh -lc "git diff --unified=20 808030e..HEAD -- astrid/core/rendering/schemas/v1/support.json && git diff --unified=15 808030e..HEAD -- astrid/core/rendering/schemas/v1/plan.json | rg -n -C 12 'hashMap|propertyNames'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/support.json b/astrid/core/rendering/schemas/v1/support.json
index c136d5c..614a8a0 100644
--- a/astrid/core/rendering/schemas/v1/support.json
+++ b/astrid/core/rendering/schemas/v1/support.json
@@ -9,69 +9,69 @@
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3---- a/astrid/core/rendering/schemas/v1/plan.json
4-+++ b/astrid/core/rendering/schemas/v1/plan.json
5-@@ -43,31 +43,31 @@
6-     "profile": {
7-       "$ref": "#/definitions/renderProfile"
8-     },
9-     "total_frames": {
10-       "type": "integer",
11-       "minimum": 0
12-     },
13-     "reasons": {
14-       "type": "object",
15:       "propertyNames": {
16-         "pattern": "^(0|[1-9][0-9]*)$"
17-       },
18-       "additionalProperties": {
19-         "type": "string",
20-         "minLength": 1,
21--        "pattern": "^(?!.*\\u0000).*\\S.*$"
22-+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
23-       }
24-     },
25-     "window": {
26-       "anyOf": [
27-         {
--
389-         "window",
390-         "renderer",
391-         "input_hashes"
392-       ],
393-       "properties": {
394-         "window": {
395-           "$ref": "#/definitions/frameWindow"
396-         },
397-         "renderer": {
398-           "$ref": "#/definitions/rendererResolution"
399-         },
400-         "input_hashes": {
401:           "$ref": "#/definitions/hashMap"
402-         }
403-       }
404-+    },
405-+    "overrideRecord": {
406-+      "type": "object",
407-+      "additionalProperties": false,
408-+      "required": [
409-+        "from",
410-+        "to"
411-+      ],
412-+      "properties": {
413-+        "from": {

exec
/bin/zsh -lc 'for f in astrid/core/rendering/schemas/v1/{plan,finalize,support}.json; do echo "$f"; rg -n -A14 -B2 '"'\"features\": \\{' \""'$f"; done; for f in astrid/core/rendering/schemas/v1/{plan,finalize}.json; do echo "$f hashMap"; rg -n -A9 -B2 '"'\"hashMap\"' \""'$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/plan.json
350-          }
351-        },
352:        "features": {
353-          "type": "object",
354-          "additionalProperties": {
355-            "type": [
356-              "boolean",
357-              "string"
358-            ]
359-          }
360-        },
361-        "alternatives": {
362-          "type": "array",
363-          "uniqueItems": true,
364-          "items": {
365-            "$ref": "#/definitions/qualifiedId"
366-          }
--
627-              "supported": true,
628-              "reasons": [],
629:              "features": {
630-                "media": true,
631-                "audio_mode": "rendered"
632-              },
633-              "alternatives": [],
634-              "backend": "acme.example",
635-              "backend_version": "1.0.0"
636-            },
637-            "trust_eligibility": {
638-              "eligible": true,
639-              "method": "source-tree"
640-            }
641-          },
642-          "input_hashes": {
643-            "timeline": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
--
661-          "supported": true,
662-          "reasons": [],
663:          "features": {},
664-          "alternatives": [],
665-          "backend": "rendering.ffmpeg-finalizer",
666-          "backend_version": null
667-        }
668-      },
669-      "profile": {
670-        "width": 1920,
671-        "height": 1080,
672-        "fps_rational": [
673-          24,
674-          1
675-        ],
676-        "time_base": [
677-          1,
--
728-          "supported": true,
729-          "reasons": [],
730:          "features": {},
731-          "alternatives": [],
732-          "backend": "rendering.ffmpeg-finalizer",
733-          "backend_version": null
734-        }
735-      },
736-      "profile": {
737-        "width": 1920,
738-        "height": 1080,
739-        "fps_rational": [
740-          24,
741-          1
742-        ],
743-        "time_base": [
744-          1,
astrid/core/rendering/schemas/v1/finalize.json
318-          }
319-        },
320:        "features": {
321-          "type": "object",
322-          "additionalProperties": {
323-            "type": [
324-              "boolean",
325-              "string"
326-            ]
327-          }
328-        },
329-        "alternatives": {
330-          "type": "array",
331-          "uniqueItems": true,
332-          "items": {
333-            "$ref": "#/definitions/qualifiedId"
334-          }
--
827-                "supported": true,
828-                "reasons": [],
829:                "features": {
830-                  "media": true,
831-                  "audio_mode": "rendered"
832-                },
833-                "alternatives": [],
834-                "backend": "acme.example",
835-                "backend_version": "1.0.0"
836-              },
837-              "trust_eligibility": {
838-                "eligible": true,
839-                "method": "source-tree"
840-              }
841-            },
842-            "input_hashes": {
843-              "timeline": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
--
861-            "supported": true,
862-            "reasons": [],
863:            "features": {},
864-            "alternatives": [],
865-            "backend": "rendering.ffmpeg-finalizer",
866-            "backend_version": null
867-          }
868-        },
869-        "profile": {
870-          "width": 1920,
871-          "height": 1080,
872-          "fps_rational": [
873-            24,
874-            1
875-          ],
876-          "time_base": [
877-            1,
astrid/core/rendering/schemas/v1/support.json
30-      }
31-    },
32:    "features": {
33-      "type": "object",
34-      "additionalProperties": {
35-        "type": [
36-          "boolean",
37-          "string"
38-        ]
39-      }
40-    },
41-    "alternatives": {
42-      "type": "array",
43-      "uniqueItems": true,
44-      "items": {
45-        "$ref": "#/definitions/qualifiedId"
46-      }
--
69-      "supported": true,
70-      "reasons": [],
71:      "features": {
72-        "media": true,
73-        "audio_mode": "rendered"
74-      },
75-      "alternatives": [],
76-      "backend": "acme.example",
77-      "backend_version": "1.0.0"
78-    }
79-  ]
80-}
astrid/core/rendering/schemas/v1/plan.json hashMap
536-      }
537-    },
538:    "hashMap": {
539-      "type": "object",
540-      "additionalProperties": {
541-        "$ref": "#/definitions/sha256"
542-      }
543-    },
544-    "renderSegment": {
545-      "type": "object",
546-      "additionalProperties": false,
547-      "required": [
astrid/core/rendering/schemas/v1/finalize.json hashMap
504-      }
505-    },
506:    "hashMap": {
507-      "type": "object",
508-      "additionalProperties": {
509-        "$ref": "#/definitions/sha256"
510-      }
511-    },
512-    "renderSegment": {
513-      "type": "object",
514-      "additionalProperties": false,
515-      "required": [

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '1760,1905p' && for f in astrid/core/rendering/schemas/v1/{renderer,planner,finalizer}-manifest.json; do echo \""'$f"; rg -n -A18 -B4 '"'\"features\": \\{' \""'$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1760	        }
  1761	
  1762	    def validate_final_result(
  1763	        self,
  1764	        result: RenderResult | Mapping[str, Any],
  1765	    ) -> RenderResult:
  1766	        """Validate attachment preservation on a standalone finalizer response.
  1767	
  1768	        Finalizers may add new attachments, but every input attachment must be
  1769	        present under the same name with the exact same descriptor and digest.
  1770	        """
  1771	
  1772	        final_result = (
  1773	            result
  1774	            if isinstance(result, RenderResult)
  1775	            else RenderResult.from_dict(_require_mapping(result, "final result"))
  1776	        )
  1777	        missing = sorted(set(self.expected_attachments) - set(final_result.attachments))
  1778	        if missing:
  1779	            raise ValueError("finalizer dropped attachments: " + ", ".join(missing))
  1780	        changed = sorted(
  1781	            name
  1782	            for name, expected in self.expected_attachments.items()
  1783	            if final_result.attachments[name] != expected
  1784	        )
  1785	        if changed:
  1786	            raise ValueError("finalizer changed attachments: " + ", ".join(changed))
  1787	        return final_result
  1788	
  1789	    def to_dict(self) -> dict[str, Any]:
  1790	        return _json_safe_mapping(
  1791	            {
  1792	                "schema_version": self.schema_version,
  1793	                "plan": self.plan,
  1794	                "artifacts": self.artifacts,
  1795	                "output_name": self.output_name,
  1796	                "backend_config": self.backend_config,
  1797	                "metadata": self.metadata,
  1798	            }
  1799	        )
  1800	
  1801	    @classmethod
  1802	    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
  1803	        try:
  1804	            data = _require_mapping(payload, "finalize request")
  1805	            allowed = {
  1806	                "schema_version",
  1807	                "plan",
  1808	                "artifacts",
  1809	                "output_name",
  1810	                "backend_config",
  1811	                "metadata",
  1812	            }
  1813	            _validate_object_keys(
  1814	                data,
  1815	                required={"schema_version", "plan", "artifacts", "output_name"},
  1816	                allowed=allowed,
  1817	                label="finalize request",
  1818	            )
  1819	            version = _require_schema_version(data["schema_version"], "finalize request")
  1820	            return cls(
  1821	                schema_version=version,
  1822	                plan=RenderPlan.from_dict(data["plan"]),
  1823	                artifacts=[VideoArtifact.from_dict(item) for item in data["artifacts"]],
  1824	                output_name=data["output_name"],
  1825	                backend_config=data.get("backend_config", {}),
  1826	                metadata=data.get("metadata", {}),
  1827	            )
  1828	        except Exception as exc:
  1829	            from .errors import RendererException
  1830	
  1831	            if isinstance(exc, RendererException):
  1832	                raise
  1833	            _protocol_failure(
  1834	                f"malformed finalize request: {exc}",
  1835	                details={"error_type": type(exc).__name__},
  1836	            )
  1837	
  1838	
  1839	_PERMISSIONS = frozenset(
  1840	    {"project_files", "network", "subprocess", "environment", "accelerator", "external_services"}
  1841	)
  1842	
  1843	
  1844	def _manifest_capability_object(
  1845	    value: Any,
  1846	    *,
  1847	    label: str,
  1848	    allowed: frozenset[str],
  1849	) -> dict[str, Any]:
  1850	    capabilities = _json_safe_mapping(value, label=label)
  1851	    unknown = sorted(set(capabilities) - allowed)
  1852	    if unknown:
  1853	        raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
  1854	    return capabilities
  1855	
  1856	
  1857	def _manifest_string_array(value: Any, label: str) -> list[str]:
  1858	    items = _require_string_list(value, label)
  1859	    if len(items) != len(set(items)):
  1860	        raise ValueError(f"{label} must not contain duplicates")
  1861	    return items
  1862	
  1863	
  1864	def _manifest_features(value: Any, label: str) -> dict[str, bool | str]:
  1865	    raw = _require_mapping(value, label)
  1866	    result: dict[str, bool | str] = {}
  1867	    for raw_key, raw_value in raw.items():
  1868	        key = _require_string(raw_key, f"{label} key")
  1869	        if isinstance(raw_value, bool):
  1870	            result[key] = raw_value
  1871	        elif isinstance(raw_value, str):
  1872	            result[key] = _require_string(raw_value, f"{label}[{key!r}]")
  1873	        else:
  1874	            raise TypeError(f"{label}[{key!r}] must be a boolean or string")
  1875	    return result
  1876	
  1877	
  1878	def _manifest_boolean(value: Any, label: str) -> bool:
  1879	    if not isinstance(value, bool):
  1880	        raise TypeError(f"{label} must be a boolean")
  1881	    return value
  1882	
  1883	
  1884	@dataclass(frozen=True)
  1885	class _CommandManifest:
  1886	    schema_version: int
  1887	    id: str
  1888	    name: str
  1889	    version: str
  1890	    protocol_version: int
  1891	    command: tuple[str, ...]
  1892	    operations: tuple[str, ...]
  1893	    description: str | None = None
  1894	    capabilities: dict[str, Any] = field(default_factory=dict)
  1895	    required_permissions: tuple[str, ...] = ()
  1896	    required_binaries: tuple[str, ...] = ()
  1897	    timeout_seconds: int | None = None
  1898	    metadata: dict[str, str] = field(default_factory=dict)
  1899	
  1900	    REQUIRED_OPERATION: ClassVar[str]
  1901	    ALLOWED_OPERATIONS: ClassVar[frozenset[str]]
  1902	    LABEL: ClassVar[str]
  1903	
  1904	    @classmethod
  1905	    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
astrid/core/rendering/schemas/v1/renderer-manifest.json
147-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
148-          },
149-          "uniqueItems": true
150-        },
151:        "features": {
152-          "type": "object",
153-          "additionalProperties": {
154-            "oneOf": [
155-              {
156-                "type": "boolean"
157-              },
158-              {
159-                "type": "string",
160-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
161-              }
162-            ]
163-          },
164-          "propertyNames": {
165-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
166-          }
167-        },
168-        "supports_full_timeline": {
169-          "type": "boolean"
--
218-        ],
219-        "track_types": [
220-          "visual"
221-        ],
222:        "features": {
223-          "transitions": false
224-        },
225-        "supports_full_timeline": true,
226-        "supports_windows": true,
227-        "output_profiles": [
228-          "video/mp4"
229-        ],
230-        "audio_ownership": [
231-          "passthrough",
232-          "none"
233-        ]
234-      },
235-      "required_permissions": [
236-        "project_files",
237-        "subprocess"
238-      ],
239-      "required_binaries": [
240-        "ffmpeg"
astrid/core/rendering/schemas/v1/planner-manifest.json
141-        },
142-        "supports_fallback": {
143-          "type": "boolean"
144-        },
145:        "features": {
146-          "type": "object",
147-          "additionalProperties": {
148-            "oneOf": [
149-              {
150-                "type": "boolean"
151-              },
152-              {
153-                "type": "string",
154-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
155-              }
156-            ]
157-          },
158-          "propertyNames": {
159-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
160-          }
161-        }
162-      },
163-      "additionalProperties": false
--
182-        "policies": [
183-          "hybrid"
184-        ],
185-        "supports_fallback": true,
186:        "features": {
187-          "half_open_frames": true
188-        }
189-      },
190-      "required_permissions": [
191-        "project_files"
192-      ],
193-      "required_binaries": [],
194-      "timeout_seconds": 60,
195-      "metadata": {
196-        "owner": "rendering"
197-      }
198-    }
199-  ]
200-}
astrid/core/rendering/schemas/v1/finalizer-manifest.json
153-            ]
154-          },
155-          "uniqueItems": true
156-        },
157:        "features": {
158-          "type": "object",
159-          "additionalProperties": {
160-            "oneOf": [
161-              {
162-                "type": "boolean"
163-              },
164-              {
165-                "type": "string",
166-                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
167-              }
168-            ]
169-          },
170-          "propertyNames": {
171-            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
172-          }
173-        }
174-      },
175-      "additionalProperties": false
--
200-          "rendered",
201-          "passthrough",
202-          "none"
203-        ],
204:        "features": {
205-          "stream_copy": true
206-        }
207-      },
208-      "required_permissions": [
209-        "project_files",
210-        "subprocess"
211-      ],
212-      "required_binaries": [
213-        "ffmpeg",
214-        "ffprobe"
215-      ],
216-      "timeout_seconds": 600,
217-      "metadata": {
218-        "owner": "rendering"
219-      }
220-    }
221-  ]
222-}

exec
/bin/zsh -lc "rg -n \"artifact_profiles\" -S --glob '"'!*.pyc'"' --glob '"'!.oracle/checkins/**'"' . | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
./docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
./docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
./astrid/core/rendering/provenance.py:86:def _normalize_artifact_profiles(value: Any) -> Any:
./astrid/core/rendering/provenance.py:99:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
./astrid/core/rendering/provenance.py:113:    raise TypeError("artifact_profiles must be an object or array")
./astrid/core/rendering/provenance.py:188:    artifact_profiles: Any = None,
./astrid/core/rendering/provenance.py:238:        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
./astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
./tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
./tests/core/rendering/test_contracts.py:692:        artifact_profiles={},
./tests/core/rendering/test_contracts.py:750:        artifact_profiles={"outputs/visual.mp4": artifact},
./tests/core/rendering/test_contracts.py:757:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
./tests/core/rendering/test_contracts.py:811:        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
./tests/core/rendering/test_contracts.py:815:            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": None}},
./tests/core/rendering/test_contracts.py:820:            artifact_profiles={"out/v.mp4": {"profile": _profile(), "sha256": "not-a-hash"}},

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '180,390p' && git diff --unified=60 C1..HEAD -- astrid/core/rendering/provenance.py | sed -n '1,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   180	      ]
   181	    },
   182	    "attachment": {
   183	      "type": "object",
   184	      "additionalProperties": false,
   185	      "required": [
   186	        "name",
   187	        "path",
   188	        "kind",
   189	        "sha256"
   190	      ],
   191	      "properties": {
   192	        "name": {
   193	          "$ref": "#/definitions/portableName"
   194	        },
   195	        "path": {
   196	          "$ref": "#/definitions/workspacePath"
   197	        },
   198	        "kind": {
   199	          "type": "string",
   200	          "pattern": "^[a-z][a-z0-9-]*$"
   201	        },
   202	        "sha256": {
   203	          "$ref": "#/definitions/sha256"
   204	        }
   205	      }
   206	    },
   207	    "attachments": {
   208	      "type": "object",
   209	      "propertyNames": {
   210	        "$ref": "#/definitions/portableName"
   211	      },
   212	      "additionalProperties": {
   213	        "$ref": "#/definitions/attachment"
   214	      }
   215	    },
   216	    "videoArtifact": {
   217	      "type": "object",
   218	      "additionalProperties": false,
   219	      "required": [
   220	        "path",
   221	        "profile",
   222	        "sha256",
   223	        "duration_frames"
   224	      ],
   225	      "properties": {
   226	        "path": {
   227	          "$ref": "#/definitions/workspacePath"
   228	        },
   229	        "profile": {
   230	          "$ref": "#/definitions/renderProfile"
   231	        },
   232	        "sha256": {
   233	          "$ref": "#/definitions/sha256"
   234	        },
   235	        "duration_frames": {
   236	          "type": "integer",
   237	          "minimum": 1
   238	        },
   239	        "audio": {
   240	          "anyOf": [
   241	            {
   242	              "$ref": "#/definitions/audioOwnership"
   243	            },
   244	            {
   245	              "type": "null"
   246	            }
   247	          ]
   248	        },
   249	        "attachments": {
   250	          "$ref": "#/definitions/attachments"
   251	        }
   252	      },
   253	      "allOf": [
   254	        {
   255	          "if": {
   256	            "properties": {
   257	              "profile": {
   258	                "required": [
   259	                  "audio_codec"
   260	                ],
   261	                "properties": {
   262	                  "audio_codec": {
   263	                    "type": "string",
   264	                    "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   265	                  }
   266	                }
   267	              }
   268	            }
   269	          },
   270	          "then": {
   271	            "required": [
   272	              "audio"
   273	            ],
   274	            "properties": {
   275	              "audio": {
   276	                "const": "rendered"
   277	              }
   278	            }
   279	          },
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
   356	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   357	      }
   358	    },
   359	    "stringMap": {
   360	      "type": "object",
   361	      "propertyNames": {
   362	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   363	      },
   364	      "additionalProperties": {
   365	        "type": "string",
   366	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index bf3f0a5..6a96b91 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -1,292 +1,288 @@
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
+    RenderPlan,
     RenderProfile,
     RenderSegment,
-    SupportReport,
-    _json_safe,
+    VideoArtifact,
     _json_safe_mapping,
-    _require_qualified_id,
     _require_sha256,
     _require_string,
-    _require_string_mapping,
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
 
 
-def _segment_with_v1_projection(segment: RenderSegment | Mapping[str, Any]) -> dict[str, Any]:
-    """Return a normalized segment retaining legacy ``engine/from/to`` data."""
-
-    if isinstance(segment, RenderSegment):
-        payload = segment.to_dict()
-    else:
-        payload = _json_safe_mapping(segment, label="provenance segment")
-
-    window = payload.get("window")
-    backend = payload.get("backend")
-    if isinstance(window, Mapping) and isinstance(backend, str):
-        fps = window.get("fps_rational")
-        start_frame = window.get("start_frame")
-        end_frame = window.get("end_frame")
-        if (
-            isinstance(fps, Sequence)
-            and not isinstance(fps, (str, bytes))
-            and len(fps) == 2
-            and type(fps[0]) is int
-            and type(fps[1]) is int
-            and fps[0] > 0
-            and fps[1] > 0
-            and type(start_frame) is int
-            and type(end_frame) is int
-        ):
-            frames_per_second = fps[0] / fps[1]
-            payload.setdefault("engine", backend.rsplit(".", 1)[-1])
-            payload.setdefault("from", start_frame / frames_per_second)
-            payload.setdefault("to", end_frame / frames_per_second)
-    return payload
+def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
+    """Derive one v1 segment projection from an authoritative v2 segment."""
+
+    numerator, denominator = segment.window.fps_rational
+    return {
+        "engine": segment.renderer.id.rsplit(".", 1)[-1],
+        "from": segment.window.start_frame * denominator / numerator,
+        "to": segment.window.end_frame * denominator / numerator,
+    }
 
 
 def _normalize_artifact_profiles(value: Any) -> Any:
     if value is None:
         return []
     if isinstance(value, Mapping):
-        return {
-            str(key): (
-                profile.to_dict() if isinstance(profile, RenderProfile) else _json_safe(profile)
-            )
-            for key, profile in value.items()
-        }
+        result: dict[str, Any] = {}
+        for key, profile in value.items():
+            path = _require_string(str(key), "artifact key")
+            if isinstance(profile, VideoArtifact):
+                result[path] = _artifact_lineage(profile)
+            elif isinstance(profile, Mapping) and "profile" in profile and "sha256" in profile:
+                result[path] = _artifact_lineage_from_mapping(profile)
+            else:
+                raise TypeError(
+                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
+                    "hashed lineage record {profile, sha256, attachments}; "
+                    "profile-only entries carry no output hash"
+                )
+        return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
         return [
-            profile.to_dict() if isinstance(profile, RenderProfile) else _json_safe(profile)
+            (
+                _artifact_lineage(profile)
+                if isinstance(profile, VideoArtifact)
+                else _artifact_lineage_from_mapping(profile)
+            )
             for profile in value
         ]
     raise TypeError("artifact_profiles must be an object or array")
 
 
+def _artifact_lineage_from_mapping(raw: Mapping[str, Any]) -> dict[str, Any]:
+    data = _json_safe_mapping(raw, label="artifact")
+    if "sha256" not in data or data["sha256"] is None:
+        raise ValueError("artifact lineage sha256 is required and must not be null")
+    profile = data["profile"]
+    attachments: dict[str, Any] = {}
+    for name, att in (data.get("attachments") or {}).items():
+        att = _json_safe_mapping(att, label=f"artifact attachment {name!r}")
+        if att.get("sha256") is None:
+            raise ValueError(f"artifact attachment {name!r} sha256 must not be null")
+        attachments[str(name)] = {
+            "path": _require_string(str(att.get("path")), f"attachment {name!r} path"),
+            "kind": _require_string(str(att.get("kind")), f"attachment {name!r} kind"),
+            "sha256": _require_sha256(str(att.get("sha256")), f"attachment {name!r} sha256"),
+        }
+    return {
+        "profile": (
+            profile
+            if isinstance(profile, RenderProfile)
+            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
+        ).to_dict(),
+        "sha256": _require_sha256(str(data["sha256"]), "artifact sha256"),
+        "attachments": attachments,
+    }
+
+
+def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
+    """One hashed artifact lineage record: profile, sha256, attachments."""
+    return {
+        "profile": artifact.profile.to_dict(),
+        "sha256": artifact.sha256,
+        "attachments": {
+            name: {
+                "path": attachment.path,
+                "kind": attachment.kind,
+                "sha256": attachment.sha256,
+            }
+            for name, attachment in artifact.attachments.items()
+        },
+    }
+
+
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
-    requested_policy: str | Mapping[str, Any] | None,
-    resolved_backend: str | None,
-    source_pack: Mapping[str, Any] | None,
-    alias_chain: Sequence[str] = (),
-    override: Mapping[str, Any] | None = None,
-    trust_eligibility: Mapping[str, Any] | None = None,
-    manifest_digest: str | None = None,
-    support_decision: SupportReport | Mapping[str, Any] | None = None,
-    input_hashes: Mapping[str, str] | None = None,
-    segments: Sequence[RenderSegment | Mapping[str, Any]] = (),
+    plan: RenderPlan | Mapping[str, Any],
     artifact_profiles: Any = None,
     audio_ownership: AudioOwnership | str | None = None,
     normalization: Sequence[str] = (),
-    finalizer: str | None = None,
     attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
     backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
     v1_compatibility: Mapping[str, Any] | None = None,
 ) -> dict[str, Any]:
     """Assemble additive provenance v2 with protected ownership boundaries.
 
-    ``engine`` is intentionally the legacy request projection.  The actual
-    selected implementation belongs in ``resolved_backend``.  Optional v1
-    fields are accepted only through ``v1_compatibility`` and cannot replace
+    ``engine`` is intentionally the legacy request projection. Routing and
+    replay lineage come exclusively from the validated ``RenderPlan`` so a
+    hybrid invocation cannot collapse multiple renderer identities. Optional
+    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
     any v2 core field.
     """
 
     legacy_engine = _require_string(engine, "engine")
     output_path = _require_string(str(output), "output")
     timeline_path = _require_string(str(timeline), "timeline")
     assets_path = None if assets_registry is None else _require_string(
         str(assets_registry), "assets_registry"
     )
-    if isinstance(requested_policy, str):
-        normalized_policy: Any = _require_string(requested_policy, "requested_policy")
-    elif requested_policy is None:
-        normalized_policy = None
-    else:
-        normalized_policy = _json_safe_mapping(requested_policy, label="requested_policy")
-    normalized_backend = (
-        None
-        if resolved_backend is None
-        else _require_qualified_id(resolved_backend, "resolved_backend")
-    )
-    normalized_finalizer = (
-        None if finalizer is None else _require_qualified_id(finalizer, "finalizer")
+    normalized_plan = (
+        plan
+        if isinstance(plan, RenderPlan)
+        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
     )
-    aliases = [
-        _require_string(alias, f"alias_chain[{index}]")
-        for index, alias in enumerate(alias_chain)
+    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
+    legacy_segments = [
+        _legacy_segment_projection(segment) for segment in normalized_plan.segments
     ]
-    digest = None if manifest_digest is None else _require_sha256(
-        manifest_digest, "manifest_digest"
-    )
-    support = (
-        None
-        if support_decision is None
-        else support_decision.to_dict()
-        if isinstance(support_decision, SupportReport)
-        else _json_safe_mapping(support_decision, label="support_decision")
-    )
-    hashes = _require_string_mapping(input_hashes or {}, "input_hashes")
-    normalized_segments = [_segment_with_v1_projection(segment) for segment in segments]
     normalized_normalization = [
         _require_string(item, f"normalization[{index}]")
         for index, item in enumerate(normalization)
     ]
 
     payload: dict[str, Any] = {
         "schema_version": PROVENANCE_SCHEMA_VERSION,
         "engine": legacy_engine,
         "output": output_path,
         "timeline": timeline_path,
         "assets_registry": assets_path,
-        "requested_policy": normalized_policy,
-        "resolved_backend": normalized_backend,
-        "source_pack": _json_safe_mapping(source_pack or {}, label="source_pack"),
-        "alias_chain": aliases,
-        "override": None
-        if override is None
-        else _json_safe_mapping(override, label="override"),
-        "trust_eligibility": _json_safe_mapping(
-            trust_eligibility or {}, label="trust_eligibility"
-        ),
-        "manifest_digest": digest,
-        "support_decision": support,
-        "input_hashes": hashes,
-        "segments": normalized_segments,
+        "request_digest": normalized_plan.request_digest,
+        "requested_policy": normalized_plan.requested_policy,
+        "planner": normalized_plan.planner.to_dict(),
+        # V1-compatible segment projection: flat {engine, from, to} entries,
+        # exactly the shape legacy consumers read from `segments`.
+        "segments": legacy_segments,
+        # Additive normalized v2 segment records; never overwrite v1 fields.
+        "segments_v2": normalized_segments,
         "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
         "audio_ownership": _normalize_audio_ownership(audio_ownership),
         "normalization": normalized_normalization,
-        "finalizer": normalized_finalizer,
+        "finalizer": normalized_plan.finalizer.to_dict(),
         "attachments": _normalize_attachments(attachments),
         "backend_fragments": validate_backend_fragments(backend_fragments),
     }
-    payload.update(_normalize_v1_compatibility(v1_compatibility))
+    compatibility = _normalize_v1_compatibility(v1_compatibility)
+    payload.update(compatibility)
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

exec
/bin/zsh -lc "git diff --numstat C1..HEAD -- ':"'!.oracle/**'"' ':"'!tests/**'"' ':"'!docs/**'"' && rg -n \"TODO|FIXME|XXX|pass\\s*"'$|NotImplemented|type: ignore" astrid/core/rendering astrid/core/pack/validate.py astrid/core/pack/schemas/v1/pack.json' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2	2	astrid/core/pack/schemas/v1/pack.json
64	9	astrid/core/pack/validate.py
681	138	astrid/core/rendering/contracts.py
2	1	astrid/core/rendering/errors.py
95	99	astrid/core/rendering/provenance.py
144	23	astrid/core/rendering/registry.py
793	130	astrid/core/rendering/schemas/v1/finalize.json
140	31	astrid/core/rendering/schemas/v1/finalizer-manifest.json
648	110	astrid/core/rendering/schemas/v1/plan.json
120	27	astrid/core/rendering/schemas/v1/planner-manifest.json
156	35	astrid/core/rendering/schemas/v1/renderer-manifest.json
328	93	astrid/core/rendering/schemas/v1/request.json
458	129	astrid/core/rendering/schemas/v1/result.json
49	21	astrid/core/rendering/schemas/v1/support.json

exec
/bin/zsh -lc "git diff --unified=50 C1..HEAD -- astrid/core/rendering/registry.py astrid/core/pack/validate.py astrid/core/pack/schemas/v1/pack.json astrid/core/rendering/errors.py | sed -n '1,1400p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/pack/schemas/v1/pack.json b/astrid/core/pack/schemas/v1/pack.json
index 46ff082..8ae5436 100644
--- a/astrid/core/pack/schemas/v1/pack.json
+++ b/astrid/core/pack/schemas/v1/pack.json
@@ -10,105 +10,105 @@
     "version": {"$ref": "_defs.json#/definitions/version_string"},
     "description": {"type": "string"},
     "content": {
       "type": "object",
       "properties": {
         "executors": {"type": "string"},
         "orchestrators": {"type": "string"},
         "elements": {"type": "string"},
         "schemas": {"type": "string"},
         "examples": {"type": "string"},
         "docs": {"type": "string"}
       }
     },
     "docs": {
       "type": "object"
     },
     "agent": {
       "type": "object",
       "properties": {
         "purpose": {"type": "string"},
         "entrypoints": {
           "type": "array",
           "items": {"type": "string"}
         },
         "normal_entrypoints": {
           "type": "array",
           "items": {"type": "string"}
         },
         "do_not_use_for": {"type": "string"},
         "required_context": {
           "type": "array",
           "items": {"type": "string"}
         }
       }
     },
     "metadata": {
       "type": "object"
     },
     "aliases": {
       "type": "array",
       "items": {
         "type": "object",
         "required": ["kind", "alias", "canonical_id"],
         "properties": {
           "kind": {
             "type": "string",
             "enum": ["executor", "orchestrator", "renderer", "planner", "finalizer"]
           },
           "alias": {
             "type": "string",
-            "pattern": "^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$"
+            "pattern": "^[a-z][a-z0-9_]*(\\.[a-z0-9][a-z0-9_-]*)+$"
           },
           "canonical_id": {
             "type": "string",
-            "pattern": "^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$"
+            "pattern": "^[a-z][a-z0-9_]*(\\.[a-z0-9][a-z0-9_-]*)+$"
           },
           "deprecated": {"type": "boolean"},
           "deprecation_message": {"type": "string"}
         },
         "additionalProperties": false
       }
     },
     "permissions": {
       "type": "array",
       "items": {
         "type": "object",
         "required": ["id", "reason"],
         "properties": {
           "id": {
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
           "reason": {
             "type": "string",
             "pattern": "^.*\\S.*$"
           },
           "access": {
             "type": "string",
             "pattern": "^.*\\S.*$"
           },
           "services": {
             "type": "array",
             "items": {
               "type": "string",
               "pattern": "^.*\\S.*$"
             }
           }
         },
         "additionalProperties": false
       }
     },
     "extensions": {
       "type": "object",
       "properties": {
         "generation": {
           "type": "object",
           "properties": {
             "backends": {
diff --git a/astrid/core/pack/validate.py b/astrid/core/pack/validate.py
index c8aaaad..4f857a0 100644
--- a/astrid/core/pack/validate.py
+++ b/astrid/core/pack/validate.py
@@ -1,143 +1,151 @@
 """Static pack validation module.
 
 Uses yaml.safe_load for author-facing YAML, validates each manifest against its
 JSON Schema (v1), rejects unknown schema_version values, and normalizes errors
 into file-specific builder-facing messages.
 
 Validation is static: checks declared content roots, docs, STAGE.md,
 runtime entrypoint files, and component manifests exist on disk without
 importing run.py.
 
 Layout contract validation lives in ``astrid.core.pack.validate_layout``.
 First-party packs root validation lives in ``astrid.core.pack.validate_first_party``.
 """
 
 from __future__ import annotations
 
 import json as _json
 import logging
 import re as _re
 from pathlib import Path
 from typing import Any, Optional
 
 import jsonschema
 from referencing import Registry, Resource
 
 from astrid.core.pack import (
+    PACK_ALIAS_KINDS,
     PackDefinition,
+    PackValidationError,
     _normalize_pack_permissions,
     _optional_pack_aliases,
     _optional_pack_extensions,
     element_kind_registry_for_pack,
     find_component_manifest,
     iter_element_roots,
     iter_executor_roots,
     iter_orchestrator_roots,
     pack_manifest_path,
+    pack_rendering_manifest_paths,
     pack_taxonomy_from_manifest,
     validate_content_id_in_pack,
     validate_element_pack_id,
 )
 from astrid.core.pack.alias_resolver import AliasResolutionError, AliasResolver
 from astrid.core.pack.manifest import (
     ManifestParseError,
     load_manifest_mapping,
     reconcile_runtime_module,
 )
 from astrid.core.pack.validate_first_party import (
     is_first_party_packs_root_candidate,
     validate_first_party_packs_root,
 )
 from astrid.core.pack.validate_layout import (
     CANONICAL_PACK_LAYOUT_RULES,
     CanonicalLayoutRule,
     LayoutExceptionClass,
     LayoutExceptionLifecycle,
     LayoutValidationIssue,
     PackLayoutException,
     parse_layout_exceptions,
 )
 
 logger = logging.getLogger(__name__)
 
 # ---------------------------------------------------------------------------
 # Known schema versions and their schema files
 # ---------------------------------------------------------------------------
 
 _SCHEMAS_ROOT = Path(__file__).resolve().parent / "schemas"
+_RENDERING_SCHEMAS_ROOT = _SCHEMAS_ROOT.parent.parent / "rendering" / "schemas"
 _REPO_ROOT = Path(__file__).resolve().parents[3]
+_RENDERING_MANIFEST_KINDS = ("renderer", "planner", "finalizer")
 
 _PACK_TAXONOMY_ENUMS: dict[str, tuple[str, ...]] = {
     "origin": ("unknown", "builtin", "external"),
     "install_tier": ("default", "core", "optional"),
     "pack_type": ("capability", "adapter"),
     "domain": (
         "general",
         "development",
         "editorial",
         "generation",
         "infrastructure",
         "integration",
         "media",
         "system",
     ),
     "stability": ("stable", "experimental", "deprecated"),
     "support": ("project", "core", "community"),
 }
 
 KNOWN_SCHEMA_VERSIONS: dict[int, dict[str, Path]] = {
     1: {
         "pack": _SCHEMAS_ROOT / "v1" / "pack.json",
         "executor": _SCHEMAS_ROOT / "v1" / "executor.json",
         "orchestrator": _SCHEMAS_ROOT / "v1" / "orchestrator.json",
         "element": _SCHEMAS_ROOT / "v1" / "element.json",
+        "renderer": _RENDERING_SCHEMAS_ROOT / "v1" / "renderer-manifest.json",
+        "planner": _RENDERING_SCHEMAS_ROOT / "v1" / "planner-manifest.json",
+        "finalizer": _RENDERING_SCHEMAS_ROOT / "v1" / "finalizer-manifest.json",
     }
 }
 
 KNOWN_VERSIONS_STR = ", ".join(str(v) for v in sorted(KNOWN_SCHEMA_VERSIONS))
 V1_TRUST_BLOCK: dict[str, Any] = {
     "sandbox": "none",
     "runs_with_user_process_permissions": True,
     "permission_enforcement": "disclosure_only",
 }
 
 
 def _check_schema_version(version_value: Any, manifest_relpath: str) -> int:
     """Validate that schema_version is a known integer."""
     if not isinstance(version_value, int) and not (
         isinstance(version_value, float) and version_value == int(version_value)
     ):
         raise ValidationError(
             f"{manifest_relpath}: schema_version must be an integer, got "
             f"{type(version_value).__name__}"
         )
     version = int(version_value)
     if version not in KNOWN_SCHEMA_VERSIONS:
         raise ValidationError(
             f"{manifest_relpath}: unknown schema_version {version} "
             f"(known: {KNOWN_VERSIONS_STR})"
         )
     return version
 
 
 def _normalize_jsonschema_error(
     error: jsonschema.ValidationError,
     manifest_relpath: str,
     raw_data: dict[str, Any],
 ) -> str:
     """Convert a jsonschema ValidationError into a file-specific message."""
     # Build the field path from the error's absolute path
     path_parts: list[str] = list(error.absolute_path)
     field = ".".join(str(p) for p in path_parts) if path_parts else "<root>"
 
     prefix = f"{manifest_relpath}"
 
     # Special-case schema_version since we handle it separately upstream,
     # but jsonschema may still report it for missing/wrong-type.
     if path_parts == ["schema_version"]:
         if "schema_version" not in raw_data:
             return f"{prefix}: missing required field schema_version"
         return f"{prefix}: schema_version must be 1 (known: {KNOWN_VERSIONS_STR})"
 
     message = error.message
     # Clean up verbose jsonschema messages
@@ -188,177 +196,180 @@ def _normalize_jsonschema_error(
         actual_val = raw_data
         for p in path_parts:
             if isinstance(actual_val, dict):
                 actual_val = actual_val.get(p)
             else:
                 break
         return f"{prefix}: {field} value {actual_val!r} does not match required pattern"
 
     return f"{prefix}: {field} — {message}"
 
 
 class ValidationError(ValueError):
     """Raised when pack validation fails."""
 
 
 class PackLayoutContractError(ValidationError):
     """Aggregate layout-contract failure with per-path detail."""
 
     def __init__(self, issues: list[LayoutValidationIssue]):
         self.issues = tuple(issues)
         count = len(issues)
         noun = "issue" if count == 1 else "issues"
         super().__init__(f"pack layout contract failed ({count} {noun})")
 
     def lines(self) -> list[str]:
         lines = [str(self)]
         for issue in self.issues:
             lines.append(f"{issue.path}: {issue.message}")
         return lines
 
 
 class PackValidator:
     """Validates an external pack directory statically."""
 
     def __init__(self, pack_root: Path):
         self.pack_root = pack_root.resolve()
         self.errors: list[str] = []
         self.warnings: list[str] = []
         self._pack_data: Optional[dict[str, Any]] = None
         self._layout_issues: list[LayoutValidationIssue] = []
         self._layout_exceptions: list[PackLayoutException] = []
 
     def validate(self) -> list[str]:
         """Run all validations. Returns list of error strings (empty = valid)."""
         self.errors = []
         self.warnings = []
         self._layout_issues = []
         self._layout_exceptions = []
         self._capability_locations: dict[str, str] = {}
         self._pack_capability_locations: dict[str, dict[str, str]] = {
-            "executor": {},
-            "orchestrator": {},
+            kind: {} for kind in PACK_ALIAS_KINDS
         }
         self._alias_targets: list[tuple[str, str, str]] = []
         self._pack_alias_resolvers: dict[str, AliasResolver] = {
-            "executor": AliasResolver(),
-            "orchestrator": AliasResolver(),
+            kind: AliasResolver() for kind in PACK_ALIAS_KINDS
         }
         self._pack_alias_targets: list[tuple[str, str, str, str]] = []
 
         if (self.pack_root / ".no-pack").exists():
             return self.errors
 
         pack_yaml = pack_manifest_path(self.pack_root)
         if pack_yaml is None:
             self.errors.append(
                 f"{self._rel(self.pack_root)}: pack manifest not found "
                 f"(pack.yaml, pack.yml, or pack.json)"
             )
             return self.errors
 
         # Parse pack.yaml
         pack_data = self._load_yaml(pack_yaml)
         if pack_data is None:
             return self.errors  # parse error already recorded
         self._pack_data = pack_data
 
         # Check schema_version and validate against JSON Schema
         version = self._validate_manifest(
             pack_data, "pack", self._rel(pack_yaml)
         )
         if version is None:
             return self.errors  # schema_version error already recorded
 
         self._validate_pack_taxonomy()
 
         # Validate content roots exist
         content = pack_data.get("content", {})
         if isinstance(content, dict):
             self._validate_content_roots(content)
 
         # Validate docs exist
         docs = pack_data.get("docs", {})
         if isinstance(docs, dict):
             self._validate_docs(docs)
 
         # Validate component manifests
         self._validate_components(content)
         self._validate_pack_aliases()
         self._validate_alias_targets()
         self._validate_layout_contract()
         self._flush_layout_issues()
 
         return self.errors
 
     def validate_component_manifest(
         self,
         manifest_path: str | Path,
         manifest_kind: str,
     ) -> dict[str, Any] | None:
         """Load and schema-validate one component manifest.
 
         This uses the same parsing and JSON Schema path as full pack validation,
         without requiring callers to validate a whole pack tree.
         """
         path = Path(manifest_path)
         data = self._load_yaml(path)
         if data is None:
             return None
         self._validate_manifest(data, manifest_kind, self._rel(path))
         return data
 
-    def _load_yaml(self, path: Path) -> Optional[dict[str, Any]]:
+    def _load_yaml(
+        self,
+        path: Path,
+        *,
+        manifest_kind: str = "pack",
+    ) -> Optional[dict[str, Any]]:
         """Load a YAML file with safe_load. Returns None on error."""
         rel = self._rel(path)
         try:
-            data = load_manifest_mapping(path, manifest_kind="pack")
+            data = load_manifest_mapping(path, manifest_kind=manifest_kind)
         except ManifestParseError as e:
             self.errors.append(f"{rel}: {e}")
             return None
 
         return data
 
     def _validate_manifest(
         self,
         data: dict[str, Any],
         manifest_kind: str,
         relpath: str,
     ) -> Optional[int]:
         """Validate a manifest dict against its JSON Schema.
 
         Returns the schema_version on success, None on failure.
         """
         # Pack and component manifests are schema-versioned. If a component
         # omits schema_version, validate against v1 so the schema reports the
         # same missing-field error direct JSON Schema validation would report.
         if "schema_version" not in data:
             if manifest_kind == "pack":
                 self.errors.append(f"{relpath}: missing required field schema_version")
                 return None
             version = 1
         else:
             try:
                 version = _check_schema_version(data["schema_version"], relpath)
             except ValidationError as e:
                 self.errors.append(str(e))
                 return None
 
         # Load and validate against JSON Schema
         schema_path = KNOWN_SCHEMA_VERSIONS[version].get(manifest_kind)
         if schema_path is None:
             self.errors.append(
                 f"{relpath}: no schema for {manifest_kind} in version {version}"
             )
             return None
 
         try:
             schema, registry = self._load_schema(schema_path, manifest_kind, version)
         except Exception as e:
             self.errors.append(
                 f"{relpath}: cannot load schema {schema_path} — {e}"
             )
             return None
 
         validator = jsonschema.Draft7Validator(schema, registry=registry)
         raw_errors = list(validator.iter_errors(data))
         raw_errors = self._filter_dynamic_element_kind_errors(
@@ -498,100 +509,143 @@ class PackValidator:
                     f"{self._rel(doc_path)}: declared docs file not found"
                 )
 
     def _validate_components(self, content: dict[str, Any]) -> None:
         """Validate all component manifests declared via content roots."""
         if self._pack_data is None:
             return
         self._validate_discovered_components(content)
 
     def _pack_definition_for_discovery(self, content: dict[str, Any]) -> PackDefinition:
         data = self._pack_data or {}
         status = str(data.get("status") or "active")
         taxonomy = pack_taxonomy_from_manifest(data, status=status)
         return PackDefinition(
             id=str(data.get("id") or self.pack_root.name),
             name=str(data.get("name") or data.get("id") or self.pack_root.name),
             version=str(data.get("version") or ""),
             root=self.pack_root,
             manifest_path=self.pack_root / "pack.yaml",
             schema_version=data.get("schema_version"),
             description=str(data.get("description") or ""),
             status=status,
             visibility=str(data.get("visibility") or "visible"),
             content=dict(content),
             metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata", {}), dict) else {},
             agent=dict(data.get("agent", {})) if isinstance(data.get("agent", {}), dict) else {},
             aliases=_optional_pack_aliases(data.get("aliases"), path="pack.aliases"),
             permissions=_normalize_pack_permissions(data.get("permissions")),
             extensions=_optional_pack_extensions(data.get("extensions"), path="pack.extensions"),
             **taxonomy,
         )
 
     def _validate_discovered_components(self, content: dict[str, Any]) -> None:
         pack = self._pack_definition_for_discovery(content)
         for comp_dir in iter_executor_roots(pack):
             manifest_path = find_component_manifest(comp_dir, "executor")
             if manifest_path is not None:
                 self._validate_component_manifest_file(
                     pack, comp_dir, manifest_path, "executor"
                 )
         for comp_dir in iter_orchestrator_roots(pack):
             manifest_path = find_component_manifest(comp_dir, "orchestrator")
             if manifest_path is not None:
                 self._validate_component_manifest_file(
                     pack, comp_dir, manifest_path, "orchestrator"
                 )
         for kind, elem_dir in iter_element_roots(pack):
             manifest_path = find_component_manifest(elem_dir, "element")
             if manifest_path is not None:
                 self._validate_element_manifest_file(pack, kind, manifest_path)
+        try:
+            rendering_manifest_paths = pack_rendering_manifest_paths(pack)
+        except PackValidationError as exc:
+            self.errors.append(f"pack.yaml: {exc}")
+            return
+        for manifest_kind, manifest_paths in zip(
+            _RENDERING_MANIFEST_KINDS,
+            rendering_manifest_paths,
+        ):
+            for manifest_path in manifest_paths:
+                self._validate_rendering_manifest_file(
+                    pack,
+                    manifest_path,
+                    manifest_kind,
+                )
+
+    def _validate_rendering_manifest_file(
+        self,
+        pack: PackDefinition,
+        manifest_path: Path,
+        manifest_kind: str,
+    ) -> None:
+        data = self._load_yaml(manifest_path, manifest_kind=manifest_kind)
+        if data is None:
+            return
+
+        rel = self._rel(manifest_path)
+        version = self._validate_manifest(data, manifest_kind, rel)
+        if version is None:
+            return
+        capability_id = data.get("id")
+        if not isinstance(capability_id, str):
+            return
+        self._register_capability_id(capability_id, rel)
+        self._pack_capability_locations[manifest_kind][capability_id] = rel
+        try:
+            validate_content_id_in_pack(
+                capability_id,
+                pack,
+                content_type=manifest_kind,
+            )
+        except ValueError as exc:
+            self.errors.append(f"{rel}: {exc}")
 
     def _validate_component_manifest_file(
         self,
         pack: PackDefinition,
         component_dir: Path,
         manifest_path: Path,
         manifest_kind: str,
     ) -> None:
         data = self._load_yaml(manifest_path)
         if data is None:
             return
 
         rel = self._rel(manifest_path)
         version = self._validate_manifest(data, manifest_kind, rel)
         if version is None:
             return
         component_id = data.get("id")
         if isinstance(component_id, str):
             self._register_capability_id(component_id, rel)
             if manifest_kind in self._pack_capability_locations:
                 self._pack_capability_locations[manifest_kind][component_id] = rel
             self._register_aliases(data, rel)
             try:
                 validate_content_id_in_pack(
                     component_id,
                     pack,
                     content_type=manifest_kind,
                 )
             except ValueError as exc:
                 self.errors.append(f"{rel}: {exc}")
 
         self._validate_runtime_entrypoints(component_dir, data, manifest_kind, rel)
         self._validate_runtime_definition(data, manifest_kind, rel)
 
         docs = data.get("docs", {})
         stage = docs.get("stage", "STAGE.md") if isinstance(docs, dict) else "STAGE.md"
         stage_path = component_dir / stage
         if not stage_path.is_file():
             self.warnings.append(f"{self._rel(stage_path)}: STAGE.md not found")
 
     def _validate_runtime_definition(
         self, data: dict[str, Any], manifest_kind: str, rel: str
     ) -> None:
         """Run the pack-tier runtime-reconciliation check after the JSON-Schema pass.
 
         The JSON Schema is permissive about shapes the runtime parser rejects
         (e.g. a manifest declaring its runtime module twice with conflicting
         values). That structural check lives in the pack tier
         (``reconcile_runtime_module``); the executor / orchestrator schemas call
         the same helper at registry-load time, so running it here keeps
@@ -805,106 +859,107 @@ class PackValidator:
             return
         for index, alias in enumerate(aliases):
             if isinstance(alias, str):
                 self._alias_targets.append((relpath, f"metadata.aliases[{index}]", alias))
             elif isinstance(alias, dict):
                 target = alias.get("canonical_id") or alias.get("target") or alias.get("id")
                 if isinstance(target, str):
                     self._alias_targets.append((relpath, f"metadata.aliases[{index}]", target))
                 else:
                     self.errors.append(f"{relpath}: metadata.aliases[{index}] must declare canonical_id")
             else:
                 self.errors.append(f"{relpath}: metadata.aliases[{index}] must be a string or object")
 
     def _validate_pack_aliases(self) -> None:
         if self._pack_data is None:
             return
         aliases = self._pack_data.get("aliases")
         if aliases is None:
             return
         try:
             normalized_aliases = _optional_pack_aliases(aliases, path="pack.aliases")
         except ValueError as exc:
             self.errors.append(f"pack.yaml: {exc}")
             return
 
         for index, alias in enumerate(normalized_aliases):
             kind = str(alias["kind"])
             alias_id = str(alias["alias"])
             canonical_id = str(alias["canonical_id"])
             resolver = self._pack_alias_resolvers[kind]
             if resolver.is_alias(alias_id):
                 self.errors.append(
                     f"pack.yaml: pack.aliases[{index}] duplicates existing {kind} alias {alias_id!r}"
                 )
                 continue
             try:
                 resolver.register_alias(
                     alias_id,
                     canonical_id,
                     deprecated=bool(alias.get("deprecated", False)),
                     deprecation_message=str(alias.get("deprecation_message", "")),
                 )
             except AliasResolutionError as exc:
                 self.errors.append(f"pack.yaml: pack.aliases[{index}] {exc}")
                 continue
             self._pack_alias_targets.append(
                 ("pack.yaml", f"pack.aliases[{index}]", kind, canonical_id)
             )
 
         for relpath, alias_path, kind, target in self._pack_alias_targets:
-            pack_id = target.split(".", 1)[0]
+            resolved_target = self._pack_alias_resolvers[kind].resolve(target)
+            pack_id = resolved_target.split(".", 1)[0]
             if pack_id != self._pack_id():
                 continue
-            if target not in self._pack_capability_locations[kind]:
+            if resolved_target not in self._pack_capability_locations[kind]:
                 self.errors.append(
-                    f"{relpath}: {alias_path} points to unknown {kind} id {target!r}"
+                    f"{relpath}: {alias_path} points to unknown {kind} id {resolved_target!r}"
                 )
 
     def _validate_alias_targets(self) -> None:
         for relpath, alias_path, target in self._alias_targets:
             if target not in self._capability_locations:
                 self.errors.append(
                     f"{relpath}: {alias_path} points to unknown capability id {target!r}"
                 )
 
     # -----------------------------------------------------------------------
     # Layout contract validation (delegates to validate_layout module)
     # -----------------------------------------------------------------------
 
     def _validate_layout_contract(self) -> None:
         """Validate the pack directory layout against the canonical contract."""
         if self._pack_data is None:
             return
         self._layout_exceptions, issues = parse_layout_exceptions(self._pack_data)
         self._layout_issues.extend(issues)
 
     def _flush_layout_issues(self) -> None:
         """Surface any collected layout validation issues as errors."""
         if not self._layout_issues:
             return
         aggregate = PackLayoutContractError(self._layout_issues)
         self.errors.extend(aggregate.lines())
         self._layout_issues = []
 
     def _pack_id(self) -> str:
         if self._pack_data is None:
             return self.pack_root.name
         value = self._pack_data.get("id")
         if isinstance(value, str) and value.strip():
             return value
         return self.pack_root.name
 
     def _rel(self, path: Path) -> str:
         """Return a path relative to the pack root for error messages."""
         try:
             return str(path.relative_to(self.pack_root))
         except ValueError:
             return str(path)
 
 
 def validate_pack(pack_root: str | Path) -> tuple[list[str], list[str]]:
     """Validate an external pack directory.
 
     Args:
         pack_root: Path to the pack root directory.
 
diff --git a/astrid/core/rendering/errors.py b/astrid/core/rendering/errors.py
index ccf2b34..7a17b8f 100644
--- a/astrid/core/rendering/errors.py
+++ b/astrid/core/rendering/errors.py
@@ -1,139 +1,140 @@
 """Raised exceptions for structured rendering protocol failures."""
 
 from __future__ import annotations
 
 from collections.abc import Mapping
 from typing import Any, NoReturn
 
 from astrid.core.contracts.errors import AstridError
 
-from .contracts import RendererError, RendererErrorKind
+from .contracts import SCHEMA_VERSION, RendererError, RendererErrorKind
 
 
 class RendererException(AstridError):
     """Base raised exception carrying a language-neutral ``RendererError``."""
 
     kind: str | None = None
 
     def __init__(self, error: RendererError) -> None:
         if self.kind is not None and error.kind != self.kind:
             raise ValueError(
                 f"{self.__class__.__name__} requires kind {self.kind!r}, got {error.kind!r}"
             )
         super().__init__(
             error.message,
             recovery_command=error.recovery_command,
             state_snapshot={"renderer_error": error.to_dict()},
             code=f"renderer.{error.kind}",
             degraded=error.kind == "internal",
             source_type=self.__class__.__name__,
         )
         self.error = error
         self.renderer_error = error
         self.backend = error.backend
         self.details = error.details
 
     def to_dict(self) -> dict[str, Any]:
         return self.error.to_dict()
 
 
 class RendererProtocolError(RendererException):
     kind = "protocol"
 
 
 class RendererUnsupportedError(RendererException):
     kind = "unsupported"
 
 
 class RendererBinaryMissingError(RendererException):
     kind = "binary_missing"
 
 
 class RendererTimeoutError(RendererException):
     kind = "timeout"
 
 
 class RendererInterruptedError(RendererException):
     kind = "interrupted"
 
 
 class RendererInvalidArtifactError(RendererException):
     kind = "invalid_artifact"
 
 
 class RendererInternalError(RendererException):
     kind = "internal"
 
 
 _EXCEPTION_BY_KIND: dict[str, type[RendererException]] = {
     "protocol": RendererProtocolError,
     "unsupported": RendererUnsupportedError,
     "binary_missing": RendererBinaryMissingError,
     "timeout": RendererTimeoutError,
     "interrupted": RendererInterruptedError,
     "invalid_artifact": RendererInvalidArtifactError,
     "internal": RendererInternalError,
 }
 
 
 def make_renderer_error(
     kind: RendererErrorKind,
     *,
     backend: str,
     message: str,
     recovery_command: str | None = None,
     details: Mapping[str, Any] | None = None,
 ) -> RendererError:
     """Build a validated structured failure without raising it."""
 
     return RendererError(
+        schema_version=SCHEMA_VERSION,
         kind=kind,
         backend=backend,
         message=message,
         recovery_command=recovery_command,
         details=dict(details or {}),
     )
 
 
 def exception_from_error(error: RendererError | Mapping[str, Any]) -> RendererException:
     """Wrap a structured payload in its kind-specific raised exception."""
 
     renderer_error = error if isinstance(error, RendererError) else RendererError.from_dict(error)
     exception_type = _EXCEPTION_BY_KIND[renderer_error.kind]
     return exception_type(renderer_error)
 
 
 def raise_renderer_error(error: RendererError | Mapping[str, Any]) -> NoReturn:
     """Raise the kind-specific exception for *error*."""
 
     raise exception_from_error(error)
 
 
 def raise_structured_failure(
     kind: RendererErrorKind,
     *,
     backend: str,
     message: str,
     recovery_command: str | None = None,
     details: Mapping[str, Any] | None = None,
 ) -> NoReturn:
     raise_renderer_error(
         make_renderer_error(
             kind,
             backend=backend,
             message=message,
             recovery_command=recovery_command,
             details=details,
         )
     )
 
 
 def raise_protocol_error(
     *,
     backend: str,
     message: str,
     recovery_command: str | None = "regenerate the request with renderer protocol v1",
     details: Mapping[str, Any] | None = None,
 ) -> NoReturn:
     raise_structured_failure(
         "protocol",
diff --git a/astrid/core/rendering/registry.py b/astrid/core/rendering/registry.py
index fa9a61d..9a357a1 100644
--- a/astrid/core/rendering/registry.py
+++ b/astrid/core/rendering/registry.py
@@ -845,138 +845,259 @@ def _valid_audit_timestamp(value: object) -> bool:
     try:
         parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
     except ValueError:
         return False
     return parsed.tzinfo is not None
 
 
 def _accepted_permission_ids(
     pack: PackDefinition,
     record: InstallRecord,
 ) -> tuple[tuple[str, ...], str | None]:
     accepted_raw = record.permissions_accepted
     if not isinstance(accepted_raw, list):
         return (), "install record permissions_accepted must be an array"
     if any(not isinstance(item, dict) for item in accepted_raw):
         return (), "install record contains a malformed accepted permission"
 
     expected = [permission.to_dict() for permission in pack.permissions]
     if accepted_raw != expected:
         return (), "install record accepted permissions do not match the installed pack"
     if record.trust_summary.get("permissions") != accepted_raw:
         return (), "install trust summary permissions do not match the accepted permissions"
 
     accepted_ids = tuple(str(item["id"]) for item in accepted_raw)
     if len(accepted_ids) != len(set(accepted_ids)):
         return (), "install record contains duplicate accepted permissions"
     return accepted_ids, None
 
 
 def _build_alias_resolvers(
     discovered: tuple[DiscoveredPack, ...],
     *,
     kind: str,
     pack_trust: Mapping[int, _PackTrust],
     registry: _RenderingRegistry[Any],
     error_type: type[RenderingRegistryError],
     programmatic_aliases: Iterable[tuple[str, str]] = (),
 ) -> tuple[AliasResolver, AliasResolver]:
     # Validate every discovered alias graph, including inspect-only packs.  A
     # separate trusted resolver is then built so environment/corrupt install
     # metadata cannot redirect executable capability resolution.
     try:
         inspection_resolver = create_shared_alias_resolver()
         _populate_alias_resolver(
             inspection_resolver,
             discovered,
             kind=kind,
             eligible_only=False,
             pack_trust=pack_trust,
             registry=registry,
+            programmatic_aliases=programmatic_aliases,
         )
         resolver = create_shared_alias_resolver()
         _populate_alias_resolver(
             resolver,
             discovered,
             kind=kind,
             eligible_only=True,
             pack_trust=pack_trust,
             registry=registry,
+            programmatic_aliases=programmatic_aliases,
         )
-        for alias, canonical_id in programmatic_aliases:
-            for target_resolver in (inspection_resolver, resolver):
-                target_resolver.register_alias(
-                    alias,
-                    canonical_id,
-                    source_pack_id="astrid.core",
-                )
         inspection_resolver.validate_no_cycles()
         resolver.validate_no_cycles()
         return resolver, inspection_resolver
     except AliasResolutionError as exc:
         raise error_type(
             str(exc),
             code="alias_cycle",
             capability_kind=kind,
         ) from exc
 
 
 def _populate_alias_resolver(
     resolver: AliasResolver,
     discovered: tuple[DiscoveredPack, ...],
     *,
     kind: str,
     eligible_only: bool,
     pack_trust: Mapping[int, _PackTrust],
     registry: _RenderingRegistry[Any],
+    programmatic_aliases: Iterable[tuple[str, str]] = (),
 ) -> None:
+    if eligible_only:
+        _populate_executable_alias_resolver(
+            resolver,
+            discovered,
+            kind=kind,
+            pack_trust=pack_trust,
+            registry=registry,
+            programmatic_aliases=programmatic_aliases,
+        )
+        return
+
     # Alias collisions follow the same precedence as candidates.  Register
     # lowest-precedence packs first so a lower priority_index wins last.
     for item in reversed(discovered):
-        if eligible_only and not pack_trust[item.priority_index].eligible:
-            continue
         aliases = [
             alias
             for alias in item.pack.aliases
             if alias.get("kind") == kind
-            and (
-                not eligible_only
-                or _alias_target_can_participate(alias, registry)
-            )
         ]
         if aliases:
             resolver.register_pack_aliases(item.id, aliases)
+    for alias, canonical_id in programmatic_aliases:
+        resolver.register_alias(
+            alias,
+            canonical_id,
+            source_pack_id="astrid.core",
+        )
+
+
+def _populate_executable_alias_resolver(
+    resolver: AliasResolver,
+    discovered: tuple[DiscoveredPack, ...],
+    *,
+    kind: str,
+    pack_trust: Mapping[int, _PackTrust],
+    registry: _RenderingRegistry[Any],
+    programmatic_aliases: Iterable[tuple[str, str]],
+) -> None:
+    """Register the highest-precedence executable declaration per alias.
+
+    Candidates are retained in their real registration order so that a
+    declaration whose chain ends outside the executable graph can fall back
+    to the declaration it would otherwise have overwritten.  Peeling the
+    deepest dangling hop first preserves upstream aliases when an
+    intermediate alias has a usable lower-precedence declaration.
+
+    A core compatibility alias may also terminate at a canonical id with an
+    explicit override.  That alias remains only as the routing key needed to
+    apply the override; normal winner selection still enforces eligibility on
+    the override target.
+    """
+
+    declarations: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
+    for item in reversed(discovered):
+        if not pack_trust[item.priority_index].eligible:
+            continue
+        for alias in item.pack.aliases:
+            if alias.get("kind") != kind:
+                continue
+            alias_name = alias.get("alias")
+            canonical_id = alias.get("canonical_id")
+            if not alias_name or not canonical_id:
+                raise AliasResolutionError(
+                    f"pack {item.id!r}: alias entry missing 'alias' or 'canonical_id'"
+                )
+            declarations.setdefault(str(alias_name), []).append((item.id, alias))
+
+    for alias_name, canonical_id in programmatic_aliases:
+        declarations.setdefault(alias_name, []).append(
+            (
+                "astrid.core",
+                {"alias": alias_name, "canonical_id": canonical_id},
+            )
+        )
+
+    selected_indexes = {
+        alias_name: len(candidates) - 1
+        for alias_name, candidates in declarations.items()
+    }
+    selected = {
+        alias_name: candidates[-1]
+        for alias_name, candidates in declarations.items()
+    }
+
+    override_routing_aliases: set[str] = set()
+    while True:
+        blocked: list[str] = []
+        override_routing_aliases = set()
+        for alias_name, (source_pack_id, declaration) in selected.items():
+            target = declaration.get("canonical_id")
+            if not isinstance(target, str):
+                blocked.append(alias_name)
+                continue
+            if target in selected or target in registry._entries:
+                continue
+            if (
+                registry._resolve_override_key(kind, target) is not None
+            ):
+                override_routing_aliases.add(alias_name)
+                continue
+            blocked.append(alias_name)
+        if not blocked:
+            break
+
+        for alias_name in blocked:
+            next_index = selected_indexes[alias_name] - 1
+            selected_indexes[alias_name] = next_index
+            if next_index < 0:
+                del selected[alias_name]
+            else:
+                selected[alias_name] = declarations[alias_name][next_index]
+
+    for alias_name, (source_pack_id, declaration) in selected.items():
+        if (
+            alias_name not in override_routing_aliases
+            and not _alias_target_can_participate(
+                declaration,
+                registry,
+                aliases=selected,
+                override_routing_aliases=override_routing_aliases,
+            )
+        ):
+            continue
+        resolver.register_alias(
+            alias_name,
+            str(declaration["canonical_id"]),
+            deprecated=bool(declaration.get("deprecated", False)),
+            deprecation_message=str(declaration.get("deprecation_message", "")),
+            source_pack_id=source_pack_id,
+        )
 
 
 def _alias_target_can_participate(
     alias: Mapping[str, Any],
     registry: _RenderingRegistry[Any],
+    *,
+    aliases: Mapping[str, tuple[str, Mapping[str, Any]]],
+    override_routing_aliases: set[str] | frozenset[str] = frozenset(),
 ) -> bool:
-    """Keep aliases to unknown/chained ids, but skip known denied targets.
-
-    An alias-only compatibility pack may legitimately point at a backend from
-    another pack, so absence is not grounds for dropping the declaration.
-    When the direct target was discovered and every candidate was denied,
-    however, letting that alias win would reintroduce the shadowing problem
-    that the executable-only registry is designed to prevent.
-    """
+    """Return whether a chain reaches an executable or override-routed terminal."""
 
     target = alias.get("canonical_id")
     if not isinstance(target, str):
+        return False
+
+    seen: set[str] = set()
+    while target in aliases:
+        if target in override_routing_aliases:
+            return True
+        if target in seen:
+            raise AliasResolutionError(f"alias cycle detected while resolving {target!r}")
+        seen.add(target)
+        target = aliases[target][1].get("canonical_id")
+        if not isinstance(target, str):
+            return False
+    if target in registry._entries:
         return True
-    discovered = registry._discovered.get(target)
-    return discovered is None or target in registry._entries
+    # A missing canonical terminal is still reachable when an override
+    # routes it to an executable implementation (alias -> canonical ->
+    # override ordering is frozen).
+    return registry._resolve_override_key(registry.capability_kind, target) is not None
 
 
 __all__ = [
     "ExecutionEligibility",
     "FinalizerRegistry",
     "FinalizerRegistryError",
     "PlannerRegistry",
     "PlannerRegistryError",
     "RendererRegistry",
     "RendererRegistryError",
     "RenderingCandidate",
     "RenderingEligibility",
     "RenderingRegistryError",
     "load_default_registries",
 ]

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/registry.py | sed -n '1,460p' && nl -ba astrid/core/rendering/registry.py | sed -n '460,900p' && nl -ba astrid/core/rendering/registry.py | sed -n '900,1160p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""Static, trust-aware registries for timeline rendering capabilities.
     2	
     3	Rendering manifests are data, not Python entrypoints.  Discovery in this
     4	module only reads pack and renderer YAML/JSON files; backend code is not
     5	imported until the transport layer (which deliberately lives elsewhere)
     6	chooses to invoke a command.
     7	"""
     8	
     9	from __future__ import annotations
    10	
    11	import json
    12	from collections.abc import Iterable, Mapping
    13	from dataclasses import dataclass
    14	from datetime import datetime
    15	from pathlib import Path
    16	from types import MappingProxyType
    17	from typing import Any, ClassVar, Generic, TypeVar
    18	
    19	from astrid.core.foundation.hash import sha256_file
    20	from astrid.core.foundation.paths import REPO_ROOT
    21	from astrid.core.pack import (
    22	    PackDefinition,
    23	    discover_packs,
    24	    pack_rendering_manifest_paths,
    25	    validate_content_id_in_pack,
    26	)
    27	from astrid.core.pack.alias_resolver import (
    28	    AliasResolutionError,
    29	    AliasResolver,
    30	    create_shared_alias_resolver,
    31	)
    32	from astrid.core.pack.discovery import DiscoveredPack, discover_pack_metadata
    33	from astrid.core.pack.manifest import load_manifest_mapping
    34	from astrid.core.pack.override import OverrideStore
    35	from astrid.core.pack.store import InstallRecord
    36	from astrid.core.registry import CapabilityRegistry, RegistryError
    37	
    38	from .contracts import FinalizerManifest, PlannerManifest, RendererManifest
    39	
    40	
    41	ManifestT = TypeVar("ManifestT", RendererManifest, PlannerManifest, FinalizerManifest)
    42	
    43	_FACADE_EXECUTOR_ID = "rendering.render"
    44	_PROGRAMMATIC_RENDERER_ALIASES: tuple[tuple[str, str], ...] = (
    45	    ("remotion", "rendering.remotion"),
    46	    ("ffmpeg", "rendering.ffmpeg"),
    47	)
    48	_INSTALL_WARNING_VERSION = 1
    49	_INSTALL_TRUST_METHODS = frozenset({"interactive", "cli_flag", "api", "test"})
    50	
    51	
    52	class RenderingRegistryError(RegistryError):
    53	    """A registry failure with stable, machine-readable context."""
    54	
    55	    def __init__(
    56	        self,
    57	        message: str,
    58	        *,
    59	        code: str = "registry_error",
    60	        capability_kind: str = "rendering",
    61	        requested_id: str | None = None,
    62	        details: Mapping[str, Any] | None = None,
    63	    ) -> None:
    64	        super().__init__(message)
    65	        self.code = code
    66	        self.capability_kind = capability_kind
    67	        self.requested_id = requested_id
    68	        self.details = dict(details or {})
    69	
    70	    def to_dict(self) -> dict[str, Any]:
    71	        return {
    72	            "code": self.code,
    73	            "capability_kind": self.capability_kind,
    74	            "requested_id": self.requested_id,
    75	            "message": str(self),
    76	            "details": dict(self.details),
    77	        }
    78	
    79	
    80	class RendererRegistryError(RenderingRegistryError):
    81	    """Renderer lookup or registration failed."""
    82	
    83	
    84	class PlannerRegistryError(RenderingRegistryError):
    85	    """Planner lookup or registration failed."""
    86	
    87	
    88	class FinalizerRegistryError(RenderingRegistryError):
    89	    """Finalizer lookup or registration failed."""
    90	
    91	
    92	@dataclass(frozen=True)
    93	class ExecutionEligibility:
    94	    """Derived permission to execute one statically discovered candidate."""
    95	
    96	    eligible: bool
    97	    reason: str
    98	    trust_method: str | None = None
    99	    required_permissions: tuple[str, ...] = ()
   100	    declared_permissions: tuple[str, ...] = ()
   101	    accepted_permissions: tuple[str, ...] = ()
   102	    active_revision: str | None = None
   103	
   104	    @property
   105	    def executable(self) -> bool:
   106	        return self.eligible
   107	
   108	    def to_dict(self) -> dict[str, Any]:
   109	        return {
   110	            "eligible": self.eligible,
   111	            "reason": self.reason,
   112	            "trust_method": self.trust_method,
   113	            "required_permissions": list(self.required_permissions),
   114	            "declared_permissions": list(self.declared_permissions),
   115	            "accepted_permissions": list(self.accepted_permissions),
   116	            "active_revision": self.active_revision,
   117	        }
   118	
   119	
   120	# Descriptive alias retained for callers that prefer the rendering-specific
   121	# name while the evidence payload uses the shorter ``ExecutionEligibility``.
   122	RenderingEligibility = ExecutionEligibility
   123	
   124	
   125	@dataclass(frozen=True)
   126	class RenderingCandidate(Generic[ManifestT]):
   127	    """A parsed manifest plus immutable discovery and trust evidence."""
   128	
   129	    manifest: ManifestT
   130	    source_kind: str
   131	    pack_id: str
   132	    pack_root: Path
   133	    manifest_path: Path
   134	    manifest_digest: str
   135	    priority_index: int
   136	    eligibility: ExecutionEligibility
   137	
   138	    @property
   139	    def id(self) -> str:
   140	        return self.manifest.id
   141	
   142	    @property
   143	    def execution_eligible(self) -> bool:
   144	        return self.eligibility.eligible
   145	
   146	    def to_dict(self) -> dict[str, Any]:
   147	        return {
   148	            "manifest": self.manifest.to_dict(),
   149	            "source_kind": self.source_kind,
   150	            "pack_id": self.pack_id,
   151	            "pack_root": str(self.pack_root),
   152	            "manifest_path": str(self.manifest_path),
   153	            "manifest_digest": self.manifest_digest,
   154	            "priority_index": self.priority_index,
   155	            "eligibility": self.eligibility.to_dict(),
   156	        }
   157	
   158	
   159	@dataclass(frozen=True)
   160	class _PackTrust:
   161	    eligible: bool
   162	    reason: str
   163	    trust_method: str | None = None
   164	    accepted_permissions: tuple[str, ...] = ()
   165	    active_revision: str | None = None
   166	
   167	
   168	class _RenderingRegistry(CapabilityRegistry[str, RenderingCandidate[ManifestT]], Generic[ManifestT]):
   169	    """Shared implementation for renderer, planner, and finalizer registries."""
   170	
   171	    capability_kind: ClassVar[str]
   172	    manifest_type: ClassVar[type[Any]]
   173	    error_type: ClassVar[type[RenderingRegistryError]]
   174	    rejects_facade: ClassVar[bool] = False
   175	
   176	    def __init__(
   177	        self,
   178	        candidates: Iterable[RenderingCandidate[ManifestT]] = (),
   179	        *,
   180	        alias_resolver: AliasResolver | None = None,
   181	        inspection_alias_resolver: AliasResolver | None = None,
   182	        override_store: OverrideStore | None = None,
   183	    ) -> None:
   184	        super().__init__(alias_resolver=alias_resolver, override_store=override_store)
   185	        self.inspection_alias_resolver = inspection_alias_resolver or alias_resolver
   186	        self._discovered: dict[str, list[RenderingCandidate[ManifestT]]] = {}
   187	        for candidate in candidates:
   188	            self.register(candidate)
   189	
   190	    def _error(
   191	        self,
   192	        message: str,
   193	        *,
   194	        code: str,
   195	        requested_id: str | None = None,
   196	        details: Mapping[str, Any] | None = None,
   197	    ) -> RenderingRegistryError:
   198	        return self.error_type(
   199	            message,
   200	            code=code,
   201	            capability_kind=self.capability_kind,
   202	            requested_id=requested_id,
   203	            details=details,
   204	        )
   205	
   206	    def register(
   207	        self,
   208	        candidate: RenderingCandidate[ManifestT],
   209	    ) -> RenderingCandidate[ManifestT]:
   210	        if not isinstance(candidate, RenderingCandidate):
   211	            raise self._error(
   212	                f"{self.capability_kind} registry entries must be RenderingCandidate objects",
   213	                code="invalid_candidate",
   214	            )
   215	        if not isinstance(candidate.manifest, self.manifest_type):
   216	            raise self._error(
   217	                f"{self.capability_kind} candidate {candidate.id!r} has manifest type "
   218	                f"{type(candidate.manifest).__name__}; expected {self.manifest_type.__name__}",
   219	                code="invalid_candidate",
   220	                requested_id=candidate.id,
   221	            )
   222	        if self.rejects_facade and candidate.id == _FACADE_EXECUTOR_ID:
   223	            raise self._error(
   224	                f"renderer id {_FACADE_EXECUTOR_ID!r} is reserved for the public "
   225	                "facade executor and cannot be registered as a backend",
   226	                code="facade_recursion",
   227	                requested_id=candidate.id,
   228	            )
   229	
   230	        discovered = self._discovered.setdefault(candidate.id, [])
   231	        discovered.append(candidate)
   232	        discovered.sort(key=_candidate_priority_key)
   233	
   234	        # The executable registry is intentionally a strict subset of static
   235	        # discovery.  This is what prevents an untrusted, higher-precedence
   236	        # declaration from shadowing trusted code.
   237	        if candidate.execution_eligible:
   238	            self._register_impl(
   239	                candidate.id,
   240	                candidate,
   241	                priority_key=_candidate_priority_key,
   242	            )
   243	        return candidate
   244	
   245	    def list(self) -> tuple[RenderingCandidate[ManifestT], ...]:
   246	        winners = (self._resolve_entry(entry) for entry in self._entries.values())
   247	        return tuple(sorted(winners, key=lambda candidate: candidate.id))
   248	
   249	    def as_mapping(self) -> MappingProxyType[str, RenderingCandidate[ManifestT]]:
   250	        return MappingProxyType(
   251	            {
   252	                capability_id: self._resolve_entry(entry)
   253	                for capability_id, entry in self._entries.items()
   254	            }
   255	        )
   256	
   257	    def candidates(
   258	        self,
   259	        capability_id: str | None = None,
   260	        *,
   261	        eligible: bool | None = None,
   262	    ) -> tuple[RenderingCandidate[ManifestT], ...]:
   263	        """Return static candidates, including non-executable discoveries."""
   264	
   265	        if capability_id is None:
   266	            values = [
   267	                candidate
   268	                for candidate_id in sorted(self._discovered)
   269	                for candidate in self._discovered[candidate_id]
   270	            ]
   271	        else:
   272	            canonical_id, _ = self._resolve_alias(capability_id, for_inspection=True)
   273	            values = list(self._discovered.get(canonical_id, ()))
   274	        if eligible is not None:
   275	            values = [
   276	                candidate
   277	                for candidate in values
   278	                if candidate.execution_eligible is eligible
   279	            ]
   280	        return tuple(values)
   281	
   282	    @property
   283	    def discovered_candidates(self) -> tuple[RenderingCandidate[ManifestT], ...]:
   284	        """Compatibility-friendly property for static inspection surfaces."""
   285	
   286	        return self.candidates()
   287	
   288	    def inspect(self, capability_id: str) -> tuple[RenderingCandidate[ManifestT], ...]:
   289	        """Return every statically discovered candidate for an id."""
   290	
   291	        return self.candidates(capability_id)
   292	
   293	    def get(self, capability_id: str) -> RenderingCandidate[ManifestT]:
   294	        candidate, _ = self._resolve(capability_id)
   295	        return candidate
   296	
   297	    def get_manifest(self, capability_id: str) -> ManifestT:
   298	        return self.get(capability_id).manifest
   299	
   300	    def resolve_evidence(self, capability_id: str) -> dict[str, Any]:
   301	        """Explain the complete alias/override/priority/trust resolution."""
   302	
   303	        resolution_error: dict[str, Any] | None = None
   304	        try:
   305	            candidate, resolution = self._resolve(capability_id)
   306	        except RenderingRegistryError as exc:
   307	            if exc.code != "execution_ineligible":
   308	                raise
   309	            target_id = exc.details.get("target_id")
   310	            discovered = self._discovered.get(str(target_id), ())
   311	            if not discovered:
   312	                raise
   313	            candidate = discovered[0]
   314	            resolution = {
   315	                "canonical_id": exc.details.get("canonical_id", capability_id),
   316	                "alias_chain": tuple(exc.details.get("alias_chain", ())),
   317	                "override": exc.details.get("override"),
   318	            }
   319	            resolution_error = exc.to_dict()
   320	        eligibility = candidate.eligibility.to_dict()
   321	        return {
   322	            "requested_id": capability_id,
   323	            "canonical_id": resolution["canonical_id"],
   324	            "resolved_id": candidate.id,
   325	            "source_kind": candidate.source_kind,
   326	            "pack_id": candidate.pack_id,
   327	            "pack_root": str(candidate.pack_root),
   328	            "manifest_path": str(candidate.manifest_path),
   329	            "manifest_digest": candidate.manifest_digest,
   330	            "alias_chain": list(resolution["alias_chain"]),
   331	            "override": resolution["override"],
   332	            "priority": candidate.priority_index,
   333	            "priority_index": candidate.priority_index,
   334	            "eligible": candidate.execution_eligible,
   335	            "execution_eligible": candidate.execution_eligible,
   336	            "eligibility_reason": candidate.eligibility.reason,
   337	            "trust_method": candidate.eligibility.trust_method,
   338	            "eligibility": eligibility,
   339	            "resolution_error": resolution_error,
   340	        }
   341	
   342	    def validate_all(self) -> tuple[RenderingCandidate[ManifestT], ...]:
   343	        if self.alias_resolver is not None:
   344	            try:
   345	                self.alias_resolver.validate_no_cycles()
   346	            except AliasResolutionError as exc:
   347	                raise self._error(
   348	                    str(exc),
   349	                    code="alias_cycle",
   350	                ) from exc
   351	        return self.list()
   352	
   353	    def _resolve(
   354	        self,
   355	        requested_id: str,
   356	    ) -> tuple[RenderingCandidate[ManifestT], dict[str, Any]]:
   357	        canonical_id, alias_chain = self._resolve_alias(requested_id)
   358	        if self.rejects_facade and canonical_id == _FACADE_EXECUTOR_ID:
   359	            raise self._error(
   360	                f"{self.capability_kind} {requested_id!r} resolves back to the "
   361	                f"facade executor {_FACADE_EXECUTOR_ID!r}",
   362	                code="facade_recursion",
   363	                requested_id=requested_id,
   364	                details={"canonical_id": canonical_id, "alias_chain": list(alias_chain)},
   365	            )
   366	
   367	        override_target = self._resolve_override_key(self.capability_kind, canonical_id)
   368	        target_id = override_target or canonical_id
   369	        override = (
   370	            None
   371	            if override_target is None
   372	            else {"from": canonical_id, "to": override_target}
   373	        )
   374	        if self.rejects_facade and target_id == _FACADE_EXECUTOR_ID:
   375	            raise self._error(
   376	                f"override target {_FACADE_EXECUTOR_ID!r} for {self.capability_kind} "
   377	                f"{canonical_id!r} resolves back to the facade executor",
   378	                code="facade_recursion",
   379	                requested_id=requested_id,
   380	                details={"canonical_id": canonical_id, "override": override},
   381	            )
   382	
   383	        winner = self._winner_for(target_id)
   384	        if winner is None:
   385	            discovered = self._discovered.get(target_id, ())
   386	            details: dict[str, Any] = {
   387	                "canonical_id": canonical_id,
   388	                "target_id": target_id,
   389	                "alias_chain": list(alias_chain),
   390	                "override": override,
   391	            }
   392	            if discovered:
   393	                details["candidates"] = [candidate.to_dict() for candidate in discovered]
   394	                reasons = "; ".join(
   395	                    dict.fromkeys(candidate.eligibility.reason for candidate in discovered)
   396	                )
   397	                raise self._error(
   398	                    f"{self.capability_kind} {target_id!r} is discoverable but not "
   399	                    f"execution-eligible: {reasons}",
   400	                    code="execution_ineligible",
   401	                    requested_id=requested_id,
   402	                    details=details,
   403	                )
   404	            if override_target is not None:
   405	                raise self._error(
   406	                    f"override target {target_id!r} for {self.capability_kind} "
   407	                    f"{canonical_id!r} not found in executable registry",
   408	                    code="invalid_override_target",
   409	                    requested_id=requested_id,
   410	                    details=details,
   411	                )
   412	            if alias_chain:
   413	                raise self._error(
   414	                    f"alias {requested_id!r} points to missing {self.capability_kind} "
   415	                    f"{target_id!r}",
   416	                    code="invalid_alias_target",
   417	                    requested_id=requested_id,
   418	                    details=details,
   419	                )
   420	            raise self._error(
   421	                f"unknown {self.capability_kind} id {requested_id!r}",
   422	                code="unknown_capability",
   423	                requested_id=requested_id,
   424	                details=details,
   425	            )
   426	
   427	        return winner, {
   428	            "canonical_id": canonical_id,
   429	            "alias_chain": alias_chain,
   430	            "override": override,
   431	        }
   432	
   433	    def _resolve_alias(
   434	        self,
   435	        requested_id: str,
   436	        *,
   437	        for_inspection: bool = False,
   438	    ) -> tuple[str, tuple[str, ...]]:
   439	        if not isinstance(requested_id, str) or not requested_id:
   440	            raise self._error(
   441	                f"{self.capability_kind} id must be a non-empty string",
   442	                code="invalid_id",
   443	                requested_id=requested_id if isinstance(requested_id, str) else None,
   444	            )
   445	        resolver = (
   446	            self.inspection_alias_resolver
   447	            if for_inspection
   448	            else self.alias_resolver
   449	        )
   450	        if resolver is None or not resolver.is_alias(requested_id):
   451	            return requested_id, ()
   452	
   453	        chain: list[str] = [requested_id]
   454	        seen = {requested_id}
   455	        current = requested_id
   456	        try:
   457	            while resolver.is_alias(current):
   458	                record = resolver.get_record(current)
   459	                if record is None:  # defensive against a concurrently-mutated resolver
   460	                    break
   460	                    break
   461	                current = record.canonical_id
   462	                chain.append(current)
   463	                if current in seen:
   464	                    raise AliasResolutionError(
   465	                        f"alias cycle detected while resolving {requested_id!r}"
   466	                    )
   467	                seen.add(current)
   468	        except AliasResolutionError as exc:
   469	            raise self._error(
   470	                str(exc),
   471	                code="alias_cycle",
   472	                requested_id=requested_id,
   473	                details={"alias_chain": chain},
   474	            ) from exc
   475	        return current, tuple(chain)
   476	
   477	
   478	class RendererRegistry(_RenderingRegistry[RendererManifest]):
   479	    capability_kind = "renderer"
   480	    manifest_type = RendererManifest
   481	    error_type = RendererRegistryError
   482	    rejects_facade = True
   483	
   484	
   485	class PlannerRegistry(_RenderingRegistry[PlannerManifest]):
   486	    capability_kind = "planner"
   487	    manifest_type = PlannerManifest
   488	    error_type = PlannerRegistryError
   489	
   490	
   491	class FinalizerRegistry(_RenderingRegistry[FinalizerManifest]):
   492	    capability_kind = "finalizer"
   493	    manifest_type = FinalizerManifest
   494	    error_type = FinalizerRegistryError
   495	
   496	
   497	def load_default_registries(
   498	    project_root: str | Path | None = None,
   499	    *,
   500	    extra_pack_roots: tuple[str, ...] = (),
   501	    include_installed: bool = True,
   502	) -> tuple[RendererRegistry, PlannerRegistry, FinalizerRegistry]:
   503	    """Discover static rendering manifests and build the three registries."""
   504	
   505	    root = REPO_ROOT if project_root is None else Path(project_root).resolve()
   506	    discovered = discover_pack_metadata(
   507	        project_root=root,
   508	        extra_pack_roots=extra_pack_roots,
   509	        include_installed=include_installed,
   510	        discover_packs_fn=discover_packs,
   511	    )
   512	    pack_trust = {
   513	        item.priority_index: _derive_pack_trust(item)
   514	        for item in discovered
   515	    }
   516	    override_store = OverrideStore(root)
   517	
   518	    renderers = RendererRegistry(
   519	        override_store=override_store,
   520	    )
   521	    planners = PlannerRegistry(
   522	        override_store=override_store,
   523	    )
   524	    finalizers = FinalizerRegistry(
   525	        override_store=override_store,
   526	    )
   527	
   528	    for item in discovered:
   529	        renderer_paths, planner_paths, finalizer_paths = pack_rendering_manifest_paths(
   530	            item.pack
   531	        )
   532	        _load_candidates(
   533	            renderers,
   534	            item,
   535	            renderer_paths,
   536	            RendererManifest,
   537	            pack_trust[item.priority_index],
   538	        )
   539	        _load_candidates(
   540	            planners,
   541	            item,
   542	            planner_paths,
   543	            PlannerManifest,
   544	            pack_trust[item.priority_index],
   545	        )
   546	        _load_candidates(
   547	            finalizers,
   548	            item,
   549	            finalizer_paths,
   550	            FinalizerManifest,
   551	            pack_trust[item.priority_index],
   552	        )
   553	
   554	    renderer_resolver, renderer_inspection_resolver = _build_alias_resolvers(
   555	        discovered,
   556	        kind="renderer",
   557	        pack_trust=pack_trust,
   558	        registry=renderers,
   559	        programmatic_aliases=_PROGRAMMATIC_RENDERER_ALIASES,
   560	        error_type=RendererRegistryError,
   561	    )
   562	    planner_resolver, planner_inspection_resolver = _build_alias_resolvers(
   563	        discovered,
   564	        kind="planner",
   565	        pack_trust=pack_trust,
   566	        registry=planners,
   567	        error_type=PlannerRegistryError,
   568	    )
   569	    finalizer_resolver, finalizer_inspection_resolver = _build_alias_resolvers(
   570	        discovered,
   571	        kind="finalizer",
   572	        pack_trust=pack_trust,
   573	        registry=finalizers,
   574	        error_type=FinalizerRegistryError,
   575	    )
   576	    renderers.alias_resolver = renderer_resolver
   577	    renderers.inspection_alias_resolver = renderer_inspection_resolver
   578	    planners.alias_resolver = planner_resolver
   579	    planners.inspection_alias_resolver = planner_inspection_resolver
   580	    finalizers.alias_resolver = finalizer_resolver
   581	    finalizers.inspection_alias_resolver = finalizer_inspection_resolver
   582	
   583	    renderers.validate_all()
   584	    planners.validate_all()
   585	    finalizers.validate_all()
   586	    return renderers, planners, finalizers
   587	
   588	
   589	def _candidate_priority_key(candidate: RenderingCandidate[Any]) -> tuple[int, str, str]:
   590	    return (
   591	        candidate.priority_index,
   592	        str(candidate.manifest_path),
   593	        candidate.manifest_digest,
   594	    )
   595	
   596	
   597	def _load_candidates(
   598	    registry: _RenderingRegistry[Any],
   599	    discovered: DiscoveredPack,
   600	    manifest_paths: Iterable[Path],
   601	    manifest_type: type[ManifestT],
   602	    trust: _PackTrust,
   603	) -> None:
   604	    for manifest_path in manifest_paths:
   605	        try:
   606	            payload = load_manifest_mapping(
   607	                manifest_path,
   608	                manifest_kind=registry.capability_kind,
   609	            )
   610	            manifest = manifest_type.from_dict(payload)
   611	            validate_content_id_in_pack(
   612	                manifest.id,
   613	                discovered.pack,
   614	                content_type=registry.capability_kind,
   615	            )
   616	            digest = sha256_file(manifest_path)
   617	        except Exception as exc:
   618	            if isinstance(exc, RenderingRegistryError):
   619	                raise
   620	            raise registry._error(
   621	                f"invalid {registry.capability_kind} manifest {manifest_path}: {exc}",
   622	                code="invalid_manifest",
   623	                details={
   624	                    "pack_id": discovered.id,
   625	                    "manifest_path": str(manifest_path),
   626	                },
   627	            ) from exc
   628	
   629	        eligibility = _candidate_eligibility(
   630	            discovered.pack,
   631	            manifest.required_permissions,
   632	            trust,
   633	        )
   634	        registry.register(
   635	            RenderingCandidate(
   636	                manifest=manifest,
   637	                source_kind=discovered.source_kind,
   638	                pack_id=discovered.id,
   639	                pack_root=discovered.pack_dir.resolve(),
   640	                manifest_path=manifest_path.resolve(),
   641	                manifest_digest=digest,
   642	                priority_index=discovered.priority_index,
   643	                eligibility=eligibility,
   644	            )
   645	        )
   646	
   647	
   648	def _candidate_eligibility(
   649	    pack: PackDefinition,
   650	    required_permissions: Iterable[str],
   651	    trust: _PackTrust,
   652	) -> ExecutionEligibility:
   653	    required = tuple(required_permissions)
   654	    declared = tuple(permission.id for permission in pack.permissions)
   655	    common = {
   656	        "trust_method": trust.trust_method,
   657	        "required_permissions": required,
   658	        "declared_permissions": declared,
   659	        "accepted_permissions": trust.accepted_permissions,
   660	        "active_revision": trust.active_revision,
   661	    }
   662	    if not trust.eligible:
   663	        return ExecutionEligibility(False, trust.reason, **common)
   664	
   665	    missing_declarations = sorted(set(required) - set(declared))
   666	    if missing_declarations:
   667	        return ExecutionEligibility(
   668	            False,
   669	            "manifest requires permissions not declared by its pack: "
   670	            + ", ".join(missing_declarations),
   671	            **common,
   672	        )
   673	
   674	    if trust.active_revision is not None:
   675	        missing_acceptance = sorted(set(required) - set(trust.accepted_permissions))
   676	        if missing_acceptance:
   677	            return ExecutionEligibility(
   678	                False,
   679	                "installed pack permissions were not accepted: "
   680	                + ", ".join(missing_acceptance),
   681	                **common,
   682	            )
   683	
   684	    return ExecutionEligibility(True, trust.reason, **common)
   685	
   686	
   687	def _derive_pack_trust(discovered: DiscoveredPack) -> _PackTrust:
   688	    source_kind = discovered.source_kind
   689	    if source_kind == "source":
   690	        return _PackTrust(
   691	            True,
   692	            "source-tree pack is execution-eligible",
   693	            trust_method="source_tree",
   694	        )
   695	    if source_kind == "local":
   696	        return _PackTrust(
   697	            True,
   698	            "project-local pack is execution-eligible",
   699	            trust_method="project_local",
   700	        )
   701	    if source_kind == "extra":
   702	        return _PackTrust(
   703	            True,
   704	            "pack root was explicitly supplied by the operator",
   705	            trust_method="explicit_extra_pack_root",
   706	        )
   707	    if source_kind == "env":
   708	        return _PackTrust(
   709	            False,
   710	            "environment-discovered packs are inspectable but not executable",
   711	        )
   712	    if source_kind == "installed":
   713	        return _installed_pack_trust(discovered.pack)
   714	    return _PackTrust(False, f"unknown pack source kind {source_kind!r}")
   715	
   716	
   717	def _installed_pack_trust(pack: PackDefinition) -> _PackTrust:
   718	    root = pack.root.resolve()
   719	    revision_name = root.name
   720	    if root.parent.name != "revisions":
   721	        return _PackTrust(False, "installed pack revision is outside the revisions directory")
   722	    install_root = root.parent.parent.resolve()
   723	    if install_root.name != pack.id:
   724	        return _PackTrust(False, "installed pack root does not match its pack id")
   725	
   726	    active_link = install_root / "active"
   727	    if not active_link.is_symlink():
   728	        return _PackTrust(False, "installed pack has no active revision symlink")
   729	    try:
   730	        active_revision = active_link.resolve(strict=True)
   731	    except OSError:
   732	        return _PackTrust(False, "installed pack active revision symlink is broken")
   733	    if active_revision != root:
   734	        return _PackTrust(False, "discovered installed revision is not the active revision")
   735	
   736	    record_path = root / ".astrid" / "install.json"
   737	    if not record_path.is_file():
   738	        return _PackTrust(False, "active installed revision is missing its install record")
   739	    try:
   740	        raw_record = json.loads(record_path.read_text(encoding="utf-8"))
   741	        if not isinstance(raw_record, dict):
   742	            raise TypeError("install record must be a JSON object")
   743	        record = InstallRecord.from_dict(raw_record)
   744	    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
   745	        return _PackTrust(False, f"active installed revision has a corrupt install record: {exc}")
   746	
   747	    try:
   748	        mismatch = _install_record_mismatch(
   749	            pack,
   750	            record,
   751	            install_root=install_root,
   752	            revision_name=revision_name,
   753	        )
   754	    except Exception as exc:
   755	        return _PackTrust(
   756	            False,
   757	            "active installed revision has a malformed install audit: "
   758	            f"{type(exc).__name__}: {exc}",
   759	        )
   760	    if mismatch is not None:
   761	        return _PackTrust(False, mismatch)
   762	
   763	    try:
   764	        accepted, acceptance_error = _accepted_permission_ids(pack, record)
   765	    except Exception as exc:
   766	        return _PackTrust(
   767	            False,
   768	            "active installed revision has malformed accepted permissions: "
   769	            f"{type(exc).__name__}: {exc}",
   770	        )
   771	    if acceptance_error is not None:
   772	        return _PackTrust(False, acceptance_error)
   773	
   774	    return _PackTrust(
   775	        True,
   776	        "active installed revision has a valid trust audit and accepted permissions",
   777	        trust_method=record.trust_method,
   778	        accepted_permissions=accepted,
   779	        active_revision=revision_name,
   780	    )
   781	
   782	
   783	def _install_record_mismatch(
   784	    pack: PackDefinition,
   785	    record: InstallRecord,
   786	    *,
   787	    install_root: Path,
   788	    revision_name: str,
   789	) -> str | None:
   790	    if record.pack_id != pack.id:
   791	        return "install record pack id does not match the discovered pack"
   792	    if record.version != pack.version:
   793	        return "install record version does not match the discovered pack"
   794	    if pack.schema_version and str(record.schema_version) != pack.schema_version:
   795	        return "install record schema version does not match the discovered pack"
   796	    if record.active is not True:
   797	        return "install record does not mark the active revision active"
   798	    if record.revision != revision_name:
   799	        return "install record revision does not match the active revision"
   800	    try:
   801	        recorded_install_root = Path(record.install_root).expanduser().resolve()
   802	    except (OSError, RuntimeError, TypeError, ValueError):
   803	        return "install record contains an invalid install root"
   804	    if recorded_install_root != install_root:
   805	        return "install record root does not match the active installation"
   806	    if not record.manifest_digest:
   807	        return "install record is missing its pack manifest digest"
   808	    try:
   809	        current_digest = sha256_file(pack.manifest_path)
   810	    except OSError:
   811	        return "installed pack manifest cannot be hashed"
   812	    if record.manifest_digest != current_digest:
   813	        return "install record manifest digest does not match the installed pack"
   814	    if not _valid_audit_timestamp(record.trust_acknowledged_at):
   815	        return "install record is missing a valid trust acknowledgement timestamp"
   816	    if not _valid_audit_timestamp(record.last_validation_time):
   817	        return "install record is missing a valid validation timestamp"
   818	    if not isinstance(record.trust_method, str) or not record.trust_method.strip():
   819	        return "install record is missing its trust acknowledgement method"
   820	    if record.trust_method not in _INSTALL_TRUST_METHODS:
   821	        return "install record contains an unknown trust acknowledgement method"
   822	    if not isinstance(record.trust_actor, str) or not record.trust_actor.strip():
   823	        return "install record is missing its trust acknowledgement actor"
   824	    if record.no_sandbox_warning_version != _INSTALL_WARNING_VERSION:
   825	        return "install record does not contain the current no-sandbox acknowledgement"
   826	    if not isinstance(record.trust_summary, dict) or not record.trust_summary:
   827	        return "install record is missing its trust summary"
   828	    if record.trust_summary.get("pack_id") != pack.id:
   829	        return "install trust summary does not match the discovered pack"
   830	    trust_block = record.trust_summary.get("trust")
   831	    if not isinstance(trust_block, dict):
   832	        return "install trust summary is missing its trust disclosure"
   833	    if (
   834	        trust_block.get("sandbox") != "none"
   835	        or trust_block.get("runs_with_user_process_permissions") is not True
   836	        or trust_block.get("permission_enforcement") != "disclosure_only"
   837	    ):
   838	        return "install trust summary contains an invalid trust disclosure"
   839	    return None
   840	
   841	
   842	def _valid_audit_timestamp(value: object) -> bool:
   843	    if not isinstance(value, str) or not value.strip():
   844	        return False
   845	    try:
   846	        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
   847	    except ValueError:
   848	        return False
   849	    return parsed.tzinfo is not None
   850	
   851	
   852	def _accepted_permission_ids(
   853	    pack: PackDefinition,
   854	    record: InstallRecord,
   855	) -> tuple[tuple[str, ...], str | None]:
   856	    accepted_raw = record.permissions_accepted
   857	    if not isinstance(accepted_raw, list):
   858	        return (), "install record permissions_accepted must be an array"
   859	    if any(not isinstance(item, dict) for item in accepted_raw):
   860	        return (), "install record contains a malformed accepted permission"
   861	
   862	    expected = [permission.to_dict() for permission in pack.permissions]
   863	    if accepted_raw != expected:
   864	        return (), "install record accepted permissions do not match the installed pack"
   865	    if record.trust_summary.get("permissions") != accepted_raw:
   866	        return (), "install trust summary permissions do not match the accepted permissions"
   867	
   868	    accepted_ids = tuple(str(item["id"]) for item in accepted_raw)
   869	    if len(accepted_ids) != len(set(accepted_ids)):
   870	        return (), "install record contains duplicate accepted permissions"
   871	    return accepted_ids, None
   872	
   873	
   874	def _build_alias_resolvers(
   875	    discovered: tuple[DiscoveredPack, ...],
   876	    *,
   877	    kind: str,
   878	    pack_trust: Mapping[int, _PackTrust],
   879	    registry: _RenderingRegistry[Any],
   880	    error_type: type[RenderingRegistryError],
   881	    programmatic_aliases: Iterable[tuple[str, str]] = (),
   882	) -> tuple[AliasResolver, AliasResolver]:
   883	    # Validate every discovered alias graph, including inspect-only packs.  A
   884	    # separate trusted resolver is then built so environment/corrupt install
   885	    # metadata cannot redirect executable capability resolution.
   886	    try:
   887	        inspection_resolver = create_shared_alias_resolver()
   888	        _populate_alias_resolver(
   889	            inspection_resolver,
   890	            discovered,
   891	            kind=kind,
   892	            eligible_only=False,
   893	            pack_trust=pack_trust,
   894	            registry=registry,
   895	            programmatic_aliases=programmatic_aliases,
   896	        )
   897	        resolver = create_shared_alias_resolver()
   898	        _populate_alias_resolver(
   899	            resolver,
   900	            discovered,
   900	            discovered,
   901	            kind=kind,
   902	            eligible_only=True,
   903	            pack_trust=pack_trust,
   904	            registry=registry,
   905	            programmatic_aliases=programmatic_aliases,
   906	        )
   907	        inspection_resolver.validate_no_cycles()
   908	        resolver.validate_no_cycles()
   909	        return resolver, inspection_resolver
   910	    except AliasResolutionError as exc:
   911	        raise error_type(
   912	            str(exc),
   913	            code="alias_cycle",
   914	            capability_kind=kind,
   915	        ) from exc
   916	
   917	
   918	def _populate_alias_resolver(
   919	    resolver: AliasResolver,
   920	    discovered: tuple[DiscoveredPack, ...],
   921	    *,
   922	    kind: str,
   923	    eligible_only: bool,
   924	    pack_trust: Mapping[int, _PackTrust],
   925	    registry: _RenderingRegistry[Any],
   926	    programmatic_aliases: Iterable[tuple[str, str]] = (),
   927	) -> None:
   928	    if eligible_only:
   929	        _populate_executable_alias_resolver(
   930	            resolver,
   931	            discovered,
   932	            kind=kind,
   933	            pack_trust=pack_trust,
   934	            registry=registry,
   935	            programmatic_aliases=programmatic_aliases,
   936	        )
   937	        return
   938	
   939	    # Alias collisions follow the same precedence as candidates.  Register
   940	    # lowest-precedence packs first so a lower priority_index wins last.
   941	    for item in reversed(discovered):
   942	        aliases = [
   943	            alias
   944	            for alias in item.pack.aliases
   945	            if alias.get("kind") == kind
   946	        ]
   947	        if aliases:
   948	            resolver.register_pack_aliases(item.id, aliases)
   949	    for alias, canonical_id in programmatic_aliases:
   950	        resolver.register_alias(
   951	            alias,
   952	            canonical_id,
   953	            source_pack_id="astrid.core",
   954	        )
   955	
   956	
   957	def _populate_executable_alias_resolver(
   958	    resolver: AliasResolver,
   959	    discovered: tuple[DiscoveredPack, ...],
   960	    *,
   961	    kind: str,
   962	    pack_trust: Mapping[int, _PackTrust],
   963	    registry: _RenderingRegistry[Any],
   964	    programmatic_aliases: Iterable[tuple[str, str]],
   965	) -> None:
   966	    """Register the highest-precedence executable declaration per alias.
   967	
   968	    Candidates are retained in their real registration order so that a
   969	    declaration whose chain ends outside the executable graph can fall back
   970	    to the declaration it would otherwise have overwritten.  Peeling the
   971	    deepest dangling hop first preserves upstream aliases when an
   972	    intermediate alias has a usable lower-precedence declaration.
   973	
   974	    A core compatibility alias may also terminate at a canonical id with an
   975	    explicit override.  That alias remains only as the routing key needed to
   976	    apply the override; normal winner selection still enforces eligibility on
   977	    the override target.
   978	    """
   979	
   980	    declarations: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
   981	    for item in reversed(discovered):
   982	        if not pack_trust[item.priority_index].eligible:
   983	            continue
   984	        for alias in item.pack.aliases:
   985	            if alias.get("kind") != kind:
   986	                continue
   987	            alias_name = alias.get("alias")
   988	            canonical_id = alias.get("canonical_id")
   989	            if not alias_name or not canonical_id:
   990	                raise AliasResolutionError(
   991	                    f"pack {item.id!r}: alias entry missing 'alias' or 'canonical_id'"
   992	                )
   993	            declarations.setdefault(str(alias_name), []).append((item.id, alias))
   994	
   995	    for alias_name, canonical_id in programmatic_aliases:
   996	        declarations.setdefault(alias_name, []).append(
   997	            (
   998	                "astrid.core",
   999	                {"alias": alias_name, "canonical_id": canonical_id},
  1000	            )
  1001	        )
  1002	
  1003	    selected_indexes = {
  1004	        alias_name: len(candidates) - 1
  1005	        for alias_name, candidates in declarations.items()
  1006	    }
  1007	    selected = {
  1008	        alias_name: candidates[-1]
  1009	        for alias_name, candidates in declarations.items()
  1010	    }
  1011	
  1012	    override_routing_aliases: set[str] = set()
  1013	    while True:
  1014	        blocked: list[str] = []
  1015	        override_routing_aliases = set()
  1016	        for alias_name, (source_pack_id, declaration) in selected.items():
  1017	            target = declaration.get("canonical_id")
  1018	            if not isinstance(target, str):
  1019	                blocked.append(alias_name)
  1020	                continue
  1021	            if target in selected or target in registry._entries:
  1022	                continue
  1023	            if (
  1024	                registry._resolve_override_key(kind, target) is not None
  1025	            ):
  1026	                override_routing_aliases.add(alias_name)
  1027	                continue
  1028	            blocked.append(alias_name)
  1029	        if not blocked:
  1030	            break
  1031	
  1032	        for alias_name in blocked:
  1033	            next_index = selected_indexes[alias_name] - 1
  1034	            selected_indexes[alias_name] = next_index
  1035	            if next_index < 0:
  1036	                del selected[alias_name]
  1037	            else:
  1038	                selected[alias_name] = declarations[alias_name][next_index]
  1039	
  1040	    for alias_name, (source_pack_id, declaration) in selected.items():
  1041	        if (
  1042	            alias_name not in override_routing_aliases
  1043	            and not _alias_target_can_participate(
  1044	                declaration,
  1045	                registry,
  1046	                aliases=selected,
  1047	                override_routing_aliases=override_routing_aliases,
  1048	            )
  1049	        ):
  1050	            continue
  1051	        resolver.register_alias(
  1052	            alias_name,
  1053	            str(declaration["canonical_id"]),
  1054	            deprecated=bool(declaration.get("deprecated", False)),
  1055	            deprecation_message=str(declaration.get("deprecation_message", "")),
  1056	            source_pack_id=source_pack_id,
  1057	        )
  1058	
  1059	
  1060	def _alias_target_can_participate(
  1061	    alias: Mapping[str, Any],
  1062	    registry: _RenderingRegistry[Any],
  1063	    *,
  1064	    aliases: Mapping[str, tuple[str, Mapping[str, Any]]],
  1065	    override_routing_aliases: set[str] | frozenset[str] = frozenset(),
  1066	) -> bool:
  1067	    """Return whether a chain reaches an executable or override-routed terminal."""
  1068	
  1069	    target = alias.get("canonical_id")
  1070	    if not isinstance(target, str):
  1071	        return False
  1072	
  1073	    seen: set[str] = set()
  1074	    while target in aliases:
  1075	        if target in override_routing_aliases:
  1076	            return True
  1077	        if target in seen:
  1078	            raise AliasResolutionError(f"alias cycle detected while resolving {target!r}")
  1079	        seen.add(target)
  1080	        target = aliases[target][1].get("canonical_id")
  1081	        if not isinstance(target, str):
  1082	            return False
  1083	    if target in registry._entries:
  1084	        return True
  1085	    # A missing canonical terminal is still reachable when an override
  1086	    # routes it to an executable implementation (alias -> canonical ->
  1087	    # override ordering is frozen).
  1088	    return registry._resolve_override_key(registry.capability_kind, target) is not None
  1089	
  1090	
  1091	__all__ = [
  1092	    "ExecutionEligibility",
  1093	    "FinalizerRegistry",
  1094	    "FinalizerRegistryError",
  1095	    "PlannerRegistry",
  1096	    "PlannerRegistryError",
  1097	    "RendererRegistry",
  1098	    "RendererRegistryError",
  1099	    "RenderingCandidate",
  1100	    "RenderingEligibility",
  1101	    "RenderingRegistryError",
  1102	    "load_default_registries",
  1103	]

exec
/bin/zsh -lc "sed -n '890,910p' astrid/core/rendering/registry.py && sed -n '430,620p' astrid/core/rendering/registry.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
            discovered,
            kind=kind,
            eligible_only=False,
            pack_trust=pack_trust,
            registry=registry,
            programmatic_aliases=programmatic_aliases,
        )
        resolver = create_shared_alias_resolver()
        _populate_alias_resolver(
            resolver,
            discovered,
            kind=kind,
            eligible_only=True,
            pack_trust=pack_trust,
            registry=registry,
            programmatic_aliases=programmatic_aliases,
        )
        inspection_resolver.validate_no_cycles()
        resolver.validate_no_cycles()
        return resolver, inspection_resolver
    except AliasResolutionError as exc:
            "override": override,
        }

    def _resolve_alias(
        self,
        requested_id: str,
        *,
        for_inspection: bool = False,
    ) -> tuple[str, tuple[str, ...]]:
        if not isinstance(requested_id, str) or not requested_id:
            raise self._error(
                f"{self.capability_kind} id must be a non-empty string",
                code="invalid_id",
                requested_id=requested_id if isinstance(requested_id, str) else None,
            )
        resolver = (
            self.inspection_alias_resolver
            if for_inspection
            else self.alias_resolver
        )
        if resolver is None or not resolver.is_alias(requested_id):
            return requested_id, ()

        chain: list[str] = [requested_id]
        seen = {requested_id}
        current = requested_id
        try:
            while resolver.is_alias(current):
                record = resolver.get_record(current)
                if record is None:  # defensive against a concurrently-mutated resolver
                    break
                current = record.canonical_id
                chain.append(current)
                if current in seen:
                    raise AliasResolutionError(
                        f"alias cycle detected while resolving {requested_id!r}"
                    )
                seen.add(current)
        except AliasResolutionError as exc:
            raise self._error(
                str(exc),
                code="alias_cycle",
                requested_id=requested_id,
                details={"alias_chain": chain},
            ) from exc
        return current, tuple(chain)


class RendererRegistry(_RenderingRegistry[RendererManifest]):
    capability_kind = "renderer"
    manifest_type = RendererManifest
    error_type = RendererRegistryError
    rejects_facade = True


class PlannerRegistry(_RenderingRegistry[PlannerManifest]):
    capability_kind = "planner"
    manifest_type = PlannerManifest
    error_type = PlannerRegistryError


class FinalizerRegistry(_RenderingRegistry[FinalizerManifest]):
    capability_kind = "finalizer"
    manifest_type = FinalizerManifest
    error_type = FinalizerRegistryError


def load_default_registries(
    project_root: str | Path | None = None,
    *,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[RendererRegistry, PlannerRegistry, FinalizerRegistry]:
    """Discover static rendering manifests and build the three registries."""

    root = REPO_ROOT if project_root is None else Path(project_root).resolve()
    discovered = discover_pack_metadata(
        project_root=root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        discover_packs_fn=discover_packs,
    )
    pack_trust = {
        item.priority_index: _derive_pack_trust(item)
        for item in discovered
    }
    override_store = OverrideStore(root)

    renderers = RendererRegistry(
        override_store=override_store,
    )
    planners = PlannerRegistry(
        override_store=override_store,
    )
    finalizers = FinalizerRegistry(
        override_store=override_store,
    )

    for item in discovered:
        renderer_paths, planner_paths, finalizer_paths = pack_rendering_manifest_paths(
            item.pack
        )
        _load_candidates(
            renderers,
            item,
            renderer_paths,
            RendererManifest,
            pack_trust[item.priority_index],
        )
        _load_candidates(
            planners,
            item,
            planner_paths,
            PlannerManifest,
            pack_trust[item.priority_index],
        )
        _load_candidates(
            finalizers,
            item,
            finalizer_paths,
            FinalizerManifest,
            pack_trust[item.priority_index],
        )

    renderer_resolver, renderer_inspection_resolver = _build_alias_resolvers(
        discovered,
        kind="renderer",
        pack_trust=pack_trust,
        registry=renderers,
        programmatic_aliases=_PROGRAMMATIC_RENDERER_ALIASES,
        error_type=RendererRegistryError,
    )
    planner_resolver, planner_inspection_resolver = _build_alias_resolvers(
        discovered,
        kind="planner",
        pack_trust=pack_trust,
        registry=planners,
        error_type=PlannerRegistryError,
    )
    finalizer_resolver, finalizer_inspection_resolver = _build_alias_resolvers(
        discovered,
        kind="finalizer",
        pack_trust=pack_trust,
        registry=finalizers,
        error_type=FinalizerRegistryError,
    )
    renderers.alias_resolver = renderer_resolver
    renderers.inspection_alias_resolver = renderer_inspection_resolver
    planners.alias_resolver = planner_resolver
    planners.inspection_alias_resolver = planner_inspection_resolver
    finalizers.alias_resolver = finalizer_resolver
    finalizers.inspection_alias_resolver = finalizer_inspection_resolver

    renderers.validate_all()
    planners.validate_all()
    finalizers.validate_all()
    return renderers, planners, finalizers


def _candidate_priority_key(candidate: RenderingCandidate[Any]) -> tuple[int, str, str]:
    return (
        candidate.priority_index,
        str(candidate.manifest_path),
        candidate.manifest_digest,
    )


def _load_candidates(
    registry: _RenderingRegistry[Any],
    discovered: DiscoveredPack,
    manifest_paths: Iterable[Path],
    manifest_type: type[ManifestT],
    trust: _PackTrust,
) -> None:
    for manifest_path in manifest_paths:
        try:
            payload = load_manifest_mapping(
                manifest_path,
                manifest_kind=registry.capability_kind,
            )
            manifest = manifest_type.from_dict(payload)
            validate_content_id_in_pack(
                manifest.id,
                discovered.pack,
                content_type=registry.capability_kind,
            )
            digest = sha256_file(manifest_path)
        except Exception as exc:
            if isinstance(exc, RenderingRegistryError):
                raise
            raise registry._error(

exec
/bin/zsh -lc 'for f in tests/core/rendering/fixtures/v1/*.json; do echo "$f"; jq -c '"'keys' \""'$f"; done && jq -c '"'.features' tests/core/rendering/fixtures/v1/support.json && jq -c '.segments[0].input_hashes' tests/core/rendering/fixtures/v1/plan.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/fixtures/v1/finalize.json
["artifacts","backend_config","metadata","output_name","plan","schema_version"]
tests/core/rendering/fixtures/v1/plan.json
["finalizer","planner","profile","reasons","request_digest","requested_policy","schema_version","segments","total_frames","window"]
tests/core/rendering/fixtures/v1/request.json
["assets_registry_path","audio","backend_config","metadata","output_name","profile","schema_version","timeline_path","window"]
tests/core/rendering/fixtures/v1/result.json
["audio_ownership","backend_fragments","logs","metadata","normalization","schema_version","video"]
tests/core/rendering/fixtures/v1/support.json
["alternatives","backend","backend_version","features","reasons","schema_version","supported"]
{"visual_only":true}
{"timeline":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}

codex
Two closure claims are already under pressure from direct inspection: the provenance API still accepts missing/empty artifact lineage, and the standalone/embedded support schemas plus plan hash maps still lack the stated key constraints. I’m now proving the exact accepted counterexamples and checking whether any cumulative behavior makes those states legitimate.
exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '1,520p' && nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '520,900p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import copy,json,jsonschema; from pathlib import Path; from astrid.core.rendering.contracts import parse_wire_result; p=json.load(open(\"tests/core/rendering/fixtures/v1/result.json\")); p[\"logs\"]=[\"ok\\n\\x00bad\"]; s=json.load(open(\"astrid/core/rendering/schemas/v1/result.json\")); print(\"schema\",jsonschema.Draft7Validator(s).is_valid(p));
try: parse_wire_result(p); print(\"dto\",True)
except Exception as e: print(\"dto\",False,type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 149ms:
schema True
dto False RendererProtocolError malformed render result: logs[0] must not contain NUL

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,jsonschema; from astrid.core.rendering import SupportReport,RenderPlan; cases=[]; p=json.load(open(\"tests/core/rendering/fixtures/v1/support.json\")); p[\"features\"]={\"   \":True}; cases.append((\"support\",p,json.load(open(\"astrid/core/rendering/schemas/v1/support.json\")),SupportReport.from_dict)); q=json.load(open(\"tests/core/rendering/fixtures/v1/plan.json\")); q[\"segments\"][0][\"input_hashes\"]={\"   \":\"a\"*64}; cases.append((\"plan\",q,json.load(open(\"astrid/core/rendering/schemas/v1/plan.json\")),RenderPlan.from_dict));
for n,x,s,f in cases:
 print(n,\"schema\",jsonschema.Draft7Validator(s).is_valid(x));
 try: f(x); print(n,\"dto\",True)
 except Exception as e: print(n,\"dto\",False,type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 107ms:
support schema True
support dto False RendererProtocolError malformed support report: feature key must not be empty
plan schema True
plan dto False RendererProtocolError malformed render plan: segment input_hashes key must not be empty

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '560,760p' && nl -ba astrid/core/rendering/contracts.py | sed -n '200,315p' && nl -ba astrid/core/rendering/schemas/v1/plan.json | sed -n '340,370p;530,548p' && nl -ba astrid/core/rendering/schemas/v1/support.json | sed -n '24,44p' && nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '348,368p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   340	        },
   341	        "supported": {
   342	          "type": "boolean"
   343	        },
   344	        "reasons": {
   345	          "type": "array",
   346	          "items": {
   347	            "type": "string",
   348	            "minLength": 1,
   349	            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
   542	      }
   543	    },
   544	    "renderSegment": {
   545	      "type": "object",
   546	      "additionalProperties": false,
   547	      "required": [
   548	        "window",
    24	    "reasons": {
    25	      "type": "array",
    26	      "items": {
    27	        "type": "string",
    28	        "minLength": 1,
    29	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
    30	      }
    31	    },
    32	    "features": {
    33	      "type": "object",
    34	      "additionalProperties": {
    35	        "type": [
    36	          "boolean",
    37	          "string"
    38	        ]
    39	      }
    40	    },
    41	    "alternatives": {
    42	      "type": "array",
    43	      "uniqueItems": true,
    44	      "items": {
   348	        }
   349	      }
   350	    },
   351	    "stringArray": {
   352	      "type": "array",
   353	      "items": {
   354	        "type": "string",
   355	        "minLength": 1,
   356	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   357	      }
   358	    },
   359	    "stringMap": {
   360	      "type": "object",
   361	      "propertyNames": {
   362	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   363	      },
   364	      "additionalProperties": {
   365	        "type": "string",
   366	        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   367	      }
   368	    },

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,jsonschema; from astrid.core.rendering.contracts import parse_wire_result; p=json.load(open(\"tests/core/rendering/fixtures/v1/result.json\")); p[\"video\"][\"path\"]=\"outputs/vi\\ndeo.mp4\"; s=json.load(open(\"astrid/core/rendering/schemas/v1/result.json\")); print(\"schema\",jsonschema.Draft7Validator(s).is_valid(p));
try: print(\"dto\",parse_wire_result(p).video.path)
except Exception as e: print(\"dto error\",type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 191ms:
schema False
dto outputs/vi
deo.mp4

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json; from astrid.core.rendering.contracts import RenderProfile; from astrid.core.rendering.provenance import _normalize_artifact_profiles as n; p=RenderProfile.from_dict(json.load(open(\"tests/core/rendering/fixtures/v1/plan.json\"))[\"profile\"]); cases=[None,{}, {\"out.mp4\":{\"profile\":p,\"sha256\":int(\"1\"*64)}}, {\"out.mp4\":{\"profile\":p,\"sha256\":\"a\"*64,\"attachments\":None}}, {\"out.mp4\":{\"profile\":p,\"sha256\":\"a\"*64,\"attachments\":{\"x\":{\"path\":\"None\",\"kind\":\"None\",\"sha256\":int(\"2\"*64)}}}}];
for x in cases:
 try: print(\"ACCEPT\",repr(n(x)))
 except Exception as e: print(\"REJECT\",type(e).__name__,e)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 143ms:
ACCEPT []
ACCEPT {}
ACCEPT {'out.mp4': {'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': '1111111111111111111111111111111111111111111111111111111111111111', 'attachments': {}}}
ACCEPT {'out.mp4': {'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'attachments': {}}}
ACCEPT {'out.mp4': {'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'attachments': {'x': {'path': 'None', 'kind': 'None', 'sha256': '2222222222222222222222222222222222222222222222222222222222222222'}}}}

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json; from astrid.core.rendering.contracts import RenderProfile; from astrid.core.rendering.provenance import _normalize_artifact_profiles as n; p=RenderProfile.from_dict(json.load(open(\"tests/core/rendering/fixtures/v1/plan.json\"))[\"profile\"]); print(n({\"out.mp4\":{\"profile\":p,\"sha256\":\"a\"*64,\"attachments\":{\"x\":{\"sha256\":\"b\"*64}}}}))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 73ms:
{'out.mp4': {'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'attachments': {'x': {'path': 'None', 'kind': 'None', 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'}}}}

exec
/bin/zsh -lc "git diff --unified=8 808030e..HEAD -- astrid/core/rendering/schemas/v1/{request,result,finalize,plan,support}.json astrid/core/rendering/schemas/v1/*-manifest.json | sed -n '1,1400p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 62c861c..0775c9a 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -60,34 +60,34 @@
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}$"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$)\\S.*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
@@ -309,17 +309,17 @@
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
@@ -337,17 +337,17 @@
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
@@ -370,23 +370,23 @@
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "support_decision": {
           "anyOf": [
@@ -423,23 +423,27 @@
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
-          "type": [
-            "object",
-            "null"
+          "anyOf": [
+            {
+              "$ref": "#/definitions/overrideRecord"
+            },
+            {
+              "type": "null"
+            }
           ]
         },
         "support_decision": {
           "$ref": "#/definitions/supportReport"
         },
         "trust_eligibility": {
           "type": "object"
         }
@@ -466,23 +470,23 @@
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "trust_eligibility": {
           "type": "object"
@@ -573,17 +577,17 @@
         "reasons": {
           "type": "object",
           "propertyNames": {
             "pattern": "^(0|[1-9][0-9]*)$"
           },
           "additionalProperties": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "window": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameWindow"
             },
             {
@@ -701,17 +705,17 @@
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?!.*\\u0000).*\\S.*$"
+                    "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
@@ -743,21 +747,37 @@
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
+      }
+    },
+    "overrideRecord": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": [
+        "from",
+        "to"
+      ],
+      "properties": {
+        "from": {
+          "$ref": "#/definitions/qualifiedId"
+        },
+        "to": {
+          "$ref": "#/definitions/qualifiedId"
+        }
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "plan": {
         "schema_version": 1,
diff --git a/astrid/core/rendering/schemas/v1/finalizer-manifest.json b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
index 46a1b5f..eac3e4f 100644
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
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,53 +59,54 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "minLength": 1
+        "minLength": 1,
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
@@ -129,17 +130,17 @@
     "finalizerCapabilities": {
       "type": "object",
       "properties": {
         "containers": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           },
           "uniqueItems": true
         },
         "preserves_attachments": {
           "type": "boolean"
         },
         "audio_ownership": {
           "type": "array",
@@ -157,19 +158,22 @@
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?!.*\\u0000).*\\S.*$"
+                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index 6fff803..e889fe2 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -50,17 +50,17 @@
     "reasons": {
       "type": "object",
       "propertyNames": {
         "pattern": "^(0|[1-9][0-9]*)$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     },
     "window": {
       "anyOf": [
         {
           "$ref": "#/definitions/frameWindow"
         },
         {
@@ -109,17 +109,17 @@
       "type": "string",
       "pattern": "^[0-9a-f]{64}$"
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
@@ -341,17 +341,17 @@
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
@@ -369,17 +369,17 @@
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
@@ -402,23 +402,23 @@
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "support_decision": {
           "anyOf": [
@@ -455,23 +455,27 @@
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
-          "type": [
-            "object",
-            "null"
+          "anyOf": [
+            {
+              "$ref": "#/definitions/overrideRecord"
+            },
+            {
+              "type": "null"
+            }
           ]
         },
         "support_decision": {
           "$ref": "#/definitions/supportReport"
         },
         "trust_eligibility": {
           "type": "object"
         }
@@ -498,23 +502,23 @@
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "override": {
           "anyOf": [
             {
-              "type": "object"
+              "$ref": "#/definitions/overrideRecord"
             },
             {
               "type": "null"
             }
           ]
         },
         "trust_eligibility": {
           "type": "object"
@@ -551,16 +555,32 @@
         },
         "renderer": {
           "$ref": "#/definitions/rendererResolution"
         },
         "input_hashes": {
           "$ref": "#/definitions/hashMap"
         }
       }
+    },
+    "overrideRecord": {
+      "type": "object",
+      "additionalProperties": false,
+      "required": [
+        "from",
+        "to"
+      ],
+      "properties": {
+        "from": {
+          "$ref": "#/definitions/qualifiedId"
+        },
+        "to": {
+          "$ref": "#/definitions/qualifiedId"
+        }
+      }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "request_digest": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
       "requested_policy": "hybrid",
       "planner": {
diff --git a/astrid/core/rendering/schemas/v1/planner-manifest.json b/astrid/core/rendering/schemas/v1/planner-manifest.json
index 8ec5160..a6de1d1 100644
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
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,53 +59,54 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "minLength": 1
+        "minLength": 1,
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
@@ -129,35 +130,38 @@
     "plannerCapabilities": {
       "type": "object",
       "properties": {
         "policies": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-                "pattern": "^(?!.*\\u0000).*\\S.*$"
+                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
diff --git a/astrid/core/rendering/schemas/v1/renderer-manifest.json b/astrid/core/rendering/schemas/v1/renderer-manifest.json
index d68a656..6f237fc 100644
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
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,53 +59,54 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "minLength": 1
+        "minLength": 1,
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
@@ -129,55 +130,58 @@
     "rendererCapabilities": {
       "type": "object",
       "properties": {
         "clip_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           },
           "uniqueItems": true
         },
         "track_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-                "pattern": "^(?!.*\\u0000).*\\S.*$"
+                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-            "pattern": "^(?!.*\\u0000).*\\S.*$"
+            "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           },
           "uniqueItems": true
         },
         "audio_ownership": {
           "type": "array",
           "items": {
             "type": "string",
             "enum": [
diff --git a/astrid/core/rendering/schemas/v1/request.json b/astrid/core/rendering/schemas/v1/request.json
index 2577cd6..fa3ad8b 100644
--- a/astrid/core/rendering/schemas/v1/request.json
+++ b/astrid/core/rendering/schemas/v1/request.json
@@ -12,25 +12,25 @@
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "timeline_path": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "assets_registry_path": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?!.*\\u0000).*\\S.*$"
+      "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
     },
     "output_name": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
       "not": {
         "enum": [
           ".",
           ".."
@@ -96,17 +96,17 @@
             "required": [
               "audio_codec",
               "audio_sample_rate",
               "audio_channel_layout"
             ],
             "properties": {
               "audio_codec": {
                 "type": "string",
-                "pattern": "^(?!.*\\u0000).*\\S.*$"
+                "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
               }
             }
           }
         }
       }
     },
     {
       "if": {
@@ -250,66 +250,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?!.*\\u0000).*\\S.*$"
+        "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "timeline_path": "/workspace/timeline.json",
       "assets_registry_path": "/workspace/assets.json",
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index f542a56..fc7c34e 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -17,17 +17,17 @@
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}$"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$)\\S.*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?!.*\\u0000)(?!.*/$).*\\S.*$"
     },
     "portableName": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
       "not": {
         "enum": [
           ".",
           ".."
@@ -79,66 +79,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-          "pattern": "^(?!.*\\u0000).*\\S.*$"
+          "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?!.*\\u0000).*\\S.*$"
+              "pattern": "^(?!.*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             }
           }
         }
       ]
     },
     "attachment": {
       "type": "object",
       "additionalProperties": false,
@@ -256,17 +256,17 @@
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"

exec
/bin/zsh -lc "wc -l astrid/core/rendering/contracts.py astrid/core/rendering/registry.py astrid/core/rendering/provenance.py astrid/core/pack/validate.py && rg -n '"'^class |''^@dataclass|''^def |''^    def '"' astrid/core/rendering/contracts.py | sed -n '1,300p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    2195 astrid/core/rendering/contracts.py
    1103 astrid/core/rendering/registry.py
     288 astrid/core/rendering/provenance.py
    1155 astrid/core/pack/validate.py
    4741 total
132:def _json_safe(value: Any) -> Any:
160:def _json_safe_mapping(value: Any, *, label: str = "value") -> dict[str, Any]:
167:def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
173:def _validate_object_keys(
188:def _require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
196:def _require_number(value: Any, label: str, *, exclusive_minimum: float | None = None) -> float:
207:def compute_request_digest(request: Mapping[str, Any]) -> str:
217:def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
227:def _require_optional_string(value: Any, label: str) -> str | None:
233:def _require_qualified_id(value: Any, label: str) -> str:
243:def _require_sha256(value: Any, label: str) -> str:
250:def _require_override(value: Any, *, capability_id: str, label: str) -> dict[str, Any]:
264:def _require_string_list(value: Any, label: str) -> list[str]:
270:def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
278:def _require_hash_mapping(value: Any, label: str) -> dict[str, str]:
286:def _require_schema_version(value: Any, label: str) -> int:
296:def _require_rational(value: Any, label: str) -> tuple[int, int]:
304:def _require_frame_range(value: Any, label: str) -> tuple[int, int]:
314:def _require_workspace_relative_path(value: Any, label: str) -> str:
330:def _relative_file_path(path: str | Path, workspace_root: str | Path, label: str) -> tuple[str, Path]:
343:def _protocol_failure(message: str, *, details: Mapping[str, Any] | None = None) -> NoReturn:
353:class AudioOwnership(str, Enum):
361:def _coerce_audio_ownership(value: Any, label: str, *, nullable: bool) -> AudioOwnership | None:
376:@dataclass(frozen=True)
377:class FrameWindow:
386:    def __post_init__(self) -> None:
408:    def duration_frames(self) -> int:
411:    def to_dict(self) -> dict[str, Any]:
423:    def from_dict(cls, payload: Mapping[str, Any]) -> FrameWindow:
440:@dataclass(frozen=True)
441:class RenderProfile:
458:    def __post_init__(self) -> None:
507:    def has_audio(self) -> bool:
510:    def to_dict(self) -> dict[str, Any]:
530:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
563:def _validate_artifact_audio(
582:@dataclass(frozen=True)
583:class Attachment:
591:    def __post_init__(self) -> None:
603:    def to_dict(self) -> dict[str, Any]:
609:    def from_dict(cls, payload: Mapping[str, Any]) -> Attachment:
621:    def from_file(
633:def _coerce_attachment_mapping(value: Any, label: str) -> dict[str, Attachment]:
655:@dataclass(frozen=True)
656:class VideoArtifact:
666:    def __post_init__(self) -> None:
689:    def to_dict(self) -> dict[str, Any]:
702:    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
717:    def from_file(
738:def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
746:def _coerce_window(value: Any, label: str, *, nullable: bool) -> FrameWindow | None:
754:def _coerce_namespaced_backend_config(value: Any, label: str) -> BackendConfig:
763:@dataclass(frozen=True)
764:class RenderRequest:
777:    def __post_init__(self) -> None:
810:    def to_dict(self) -> dict[str, Any]:
826:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderRequest:
874:    def for_backend(self, backend: str) -> RenderRequest:
892:@dataclass(frozen=True)
893:class SupportReport:
904:    def __post_init__(self) -> None:
935:    def to_dict(self) -> dict[str, Any]:
949:    def from_dict(cls, payload: Mapping[str, Any]) -> SupportReport:
987:@dataclass(frozen=True)
988:class PlannerResolution:
999:    def __post_init__(self) -> None:
1051:    def to_dict(self) -> dict[str, Any]:
1065:    def from_dict(cls, payload: Mapping[str, Any]) -> PlannerResolution:
1088:@dataclass(frozen=True)
1089:class RendererResolution:
1100:    def __post_init__(self) -> None:
1150:    def to_dict(self) -> dict[str, Any]:
1164:    def from_dict(cls, payload: Mapping[str, Any]) -> RendererResolution:
1187:@dataclass(frozen=True)
1188:class FinalizerResolution:
1199:    def __post_init__(self) -> None:
1251:    def to_dict(self) -> dict[str, Any]:
1265:    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizerResolution:
1288:def _normalize_requested_policy(value: Any, label: str = "requested_policy") -> str | dict[str, Any]:
1294:@dataclass(frozen=True)
1295:class RenderSegment:
1302:    def __post_init__(self) -> None:
1317:    def backend(self) -> str:
1323:    def support(self) -> SupportReport:
1328:    def to_dict(self) -> dict[str, Any]:
1338:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderSegment:
1349:@dataclass(frozen=True)
1350:class RenderPlan:
1364:    def __post_init__(self) -> None:
1443:    def to_dict(self) -> dict[str, Any]:
1460:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderPlan:
1502:def _validate_backend_fragments(value: Any) -> dict[str, dict[str, Any]]:
1518:@dataclass(frozen=True)
1519:class RenderResult:
1530:    def __post_init__(self) -> None:
1557:    def attachments(self) -> dict[str, Attachment]:
1562:    def to_dict(self) -> dict[str, Any]:
1576:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderResult:
1607:@dataclass(frozen=True)
1608:class RendererError:
1630:    def __post_init__(self) -> None:
1649:    def to_dict(self) -> dict[str, Any]:
1662:    def from_dict(cls, payload: Mapping[str, Any]) -> RendererError:
1693:@dataclass(frozen=True)
1694:class FinalizeRequest:
1704:    def __post_init__(self) -> None:
1753:    def expected_attachments(self) -> dict[str, Attachment]:
1762:    def validate_final_result(
1789:    def to_dict(self) -> dict[str, Any]:
1802:    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
1844:def _manifest_capability_object(
1857:def _manifest_string_array(value: Any, label: str) -> list[str]:
1864:def _manifest_features(value: Any, label: str) -> dict[str, bool | str]:
1878:def _manifest_boolean(value: Any, label: str) -> bool:
1884:@dataclass(frozen=True)
1885:class _CommandManifest:
1905:    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
1908:    def __post_init__(self) -> None:
1971:    def to_dict(self) -> dict[str, Any]:
1991:    def from_dict(cls, payload: Mapping[str, Any]) -> _CommandManifest:
2049:@dataclass(frozen=True)
2050:class RendererManifest(_CommandManifest):
2056:    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
2092:@dataclass(frozen=True)
2093:class PlannerManifest(_CommandManifest):
2099:    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
2118:@dataclass(frozen=True)
2119:class FinalizerManifest(_CommandManifest):
2125:    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
2154:def parse_wire_result(payload: Mapping[str, Any]) -> RenderResult | RendererError:

exec
/bin/zsh -lc "sed -n '304,562p' astrid/core/rendering/contracts.py && sed -n '754,986p' astrid/core/rendering/contracts.py && sed -n '1288,1518p' astrid/core/rendering/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
        """Return the request projection visible to one selected backend."""

        qualified = _require_qualified_id(backend, "backend")
        selected = self.backend_config.get(qualified)
        return RenderRequest(
            schema_version=self.schema_version,
            timeline_path=self.timeline_path,
            assets_registry_path=self.assets_registry_path,
            output_name=self.output_name,
            window=self.window,
            audio=self.audio,
            profile=self.profile,
            backend_config={qualified: selected} if selected is not None else {},
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class SupportReport:
    """Request-sensitive support evidence returned by an implementation."""

    schema_version: int
    supported: bool
    reasons: list[str]
    features: dict[str, bool | str]
    alternatives: list[str]
    backend: str
    backend_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(self.schema_version, "support report"),
        )
        if not isinstance(self.supported, bool):
            raise TypeError("supported must be a boolean")
        object.__setattr__(self, "reasons", _require_string_list(self.reasons, "reasons"))
        feature_mapping = _require_mapping(self.features, "features")
        features: dict[str, bool | str] = {}
        for raw_key, raw_value in feature_mapping.items():
            key = _require_string(raw_key, "feature key")
            if not isinstance(raw_value, (bool, str)):
                raise TypeError(f"features[{key!r}] must be a boolean or string")
            features[key] = raw_value
        object.__setattr__(self, "features", features)
        alternatives = [
            _require_qualified_id(item, f"alternatives[{index}]")
            for index, item in enumerate(_require_string_list(self.alternatives, "alternatives"))
        ]
        if len(alternatives) != len(set(alternatives)):
            raise ValueError("alternatives must not contain duplicate backend ids")
        object.__setattr__(self, "alternatives", alternatives)
        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "backend"))
        object.__setattr__(
            self,
            "backend_version",
            _require_optional_string(self.backend_version, "backend_version"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "supported": self.supported,
                "reasons": self.reasons,
                "features": self.features,
                "alternatives": self.alternatives,
                "backend": self.backend,
                "backend_version": self.backend_version,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SupportReport:
        try:
            data = _require_mapping(payload, "support report")
            required = {
                "schema_version",
                "supported",
                "reasons",
                "features",
                "alternatives",
                "backend",
                "backend_version",
            }
            _validate_object_keys(
                data,
                required=required,
                allowed=required,
                label="support report",
            )
            return cls(
                schema_version=data["schema_version"],
                supported=data["supported"],
                reasons=data["reasons"],
                features=data["features"],
                alternatives=data["alternatives"],
                backend=data["backend"],
                backend_version=data["backend_version"],
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed support report: {exc}",
                details={"error_type": type(exc).__name__},
            )


def _normalize_requested_policy(value: Any, label: str = "requested_policy") -> str | dict[str, Any]:
    if isinstance(value, str):
        return _require_string(value, label)
    return _json_safe_mapping(value, label=label)


@dataclass(frozen=True)
class RenderSegment:
    """One complete temporal window assigned to one qualified backend."""

    window: FrameWindow
    renderer: RendererResolution
    input_hashes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "window", _coerce_window(self.window, "segment window", nullable=False))
        renderer = (
            self.renderer
            if isinstance(self.renderer, RendererResolution)
            else RendererResolution.from_dict(_require_mapping(self.renderer, "segment renderer"))
        )
        object.__setattr__(self, "renderer", renderer)
        object.__setattr__(
            self,
            "input_hashes",
            _require_hash_mapping(self.input_hashes, "segment input_hashes"),
        )

    @property
    def backend(self) -> str:
        """Compatibility accessor; ``renderer.id`` is authoritative."""

        return self.renderer.id

    @property
    def support(self) -> SupportReport:
        """Compatibility accessor; ``renderer.support_decision`` is authoritative."""

        return self.renderer.support_decision

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "window": self.window,
                "renderer": self.renderer,
                "input_hashes": self.input_hashes,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderSegment:
        data = _require_mapping(payload, "render segment")
        required = {"window", "renderer", "input_hashes"}
        _validate_object_keys(data, required=required, allowed=required, label="render segment")
        return cls(
            window=FrameWindow.from_dict(data["window"]),
            renderer=RendererResolution.from_dict(data["renderer"]),
            input_hashes=data["input_hashes"],
        )


@dataclass(frozen=True)
class RenderPlan:
    """A deterministic temporal plan plus its explicit finalizer."""

    schema_version: int
    request_digest: str
    requested_policy: str | dict[str, Any]
    planner: PlannerResolution
    segments: list[RenderSegment]
    finalizer: FinalizerResolution
    profile: RenderProfile
    total_frames: int
    reasons: dict[str, str]
    window: FrameWindow | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(self.schema_version, "render plan"),
        )
        object.__setattr__(
            self,
            "request_digest",
            _require_sha256(self.request_digest, "request_digest"),
        )
        object.__setattr__(
            self,
            "requested_policy",
            _normalize_requested_policy(self.requested_policy),
        )
        planner = (
            self.planner
            if isinstance(self.planner, PlannerResolution)
            else PlannerResolution.from_dict(_require_mapping(self.planner, "planner"))
        )
        object.__setattr__(self, "planner", planner)
        if isinstance(self.segments, (str, bytes)) or not isinstance(self.segments, Sequence):
            raise TypeError("segments must be an array")
        segments = [
            item
            if isinstance(item, RenderSegment)
            else RenderSegment.from_dict(_require_mapping(item, f"segments[{index}]"))
            for index, item in enumerate(self.segments)
        ]
        object.__setattr__(self, "segments", segments)
        finalizer = (
            self.finalizer
            if isinstance(self.finalizer, FinalizerResolution)
            else FinalizerResolution.from_dict(_require_mapping(self.finalizer, "finalizer"))
        )
        object.__setattr__(self, "finalizer", finalizer)
        profile = _coerce_profile(self.profile, "plan profile", nullable=False)
        object.__setattr__(self, "profile", profile)
        total_frames = _require_int(self.total_frames, "total_frames", minimum=0)
        object.__setattr__(self, "total_frames", total_frames)
        window = _coerce_window(self.window, "plan window", nullable=True)
        object.__setattr__(self, "window", window)
        if window is not None:
            if window.fps_rational != profile.fps_rational:
                raise ValueError("plan window FPS must exactly match the canonical profile FPS")
            if window.end_frame > total_frames:
                raise ValueError("plan window must not extend beyond total_frames")
        if total_frames == 0:
            if window is not None or segments:
                raise ValueError("a zero-frame plan must have no window or segments")
        else:
            if not segments:
                raise ValueError("a positive-frame plan must contain at least one segment")
            target_start = window.start_frame if window is not None else 0
            target_end = window.end_frame if window is not None else total_frames
            expected_start = target_start
            for index, segment in enumerate(segments):
                if segment.window.fps_rational != profile.fps_rational:
                    raise ValueError(
                        f"segments[{index}] FPS must exactly match the canonical profile FPS"
                    )
                actual_start = segment.window.start_frame
                if actual_start != expected_start:
                    relation = "overlaps or is out of order" if actual_start < expected_start else "leaves a gap"
                    raise ValueError(f"segments[{index}] {relation} at frame {expected_start}")
                if segment.window.end_frame > target_end:
                    raise ValueError(f"segments[{index}] extends beyond the plan target window")
                expected_start = segment.window.end_frame
            if expected_start != target_end:
                raise ValueError("plan segments leave a trailing gap")
        reasons = _require_string_mapping(self.reasons, "reasons")
        expected_reason_keys = {str(index) for index in range(len(segments))}
        if set(reasons) != expected_reason_keys:
            raise ValueError(
                "plan reasons must contain exactly one entry per segment, keyed by zero-based index"
            )
        object.__setattr__(self, "reasons", reasons)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "request_digest": self.request_digest,
                "requested_policy": self.requested_policy,
                "planner": self.planner,
                "segments": self.segments,
                "finalizer": self.finalizer,
                "profile": self.profile,
                "total_frames": self.total_frames,
                "reasons": self.reasons,
                "window": self.window,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderPlan:
        try:
            data = _require_mapping(payload, "render plan")
            required = {
                "schema_version",
                "request_digest",
                "requested_policy",
                "planner",
                "segments",
                "finalizer",
                "profile",
                "total_frames",
                "reasons",
                "window",
            }
            _validate_object_keys(data, required=required, allowed=required, label="render plan")
            raw_segments = data["segments"]
            if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
                raise TypeError("segments must be an array")
            return cls(
                schema_version=data["schema_version"],
                request_digest=data["request_digest"],
                requested_policy=data["requested_policy"],
                planner=PlannerResolution.from_dict(data["planner"]),
                segments=[RenderSegment.from_dict(item) for item in raw_segments],
                finalizer=FinalizerResolution.from_dict(data["finalizer"]),
                profile=RenderProfile.from_dict(data["profile"]),
                total_frames=data["total_frames"],
                reasons=data["reasons"],
                window=FrameWindow.from_dict(data["window"]) if data["window"] is not None else None,
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed render plan: {exc}",
                details={"error_type": type(exc).__name__},
            )


def _validate_backend_fragments(value: Any) -> dict[str, dict[str, Any]]:
    mapping = _require_mapping(value, "backend_fragments")
    fragments: dict[str, dict[str, Any]] = {}
    for raw_namespace, raw_fragment in mapping.items():
        namespace = _require_qualified_id(raw_namespace, "backend fragment namespace")
        fragment = _json_safe_mapping(raw_fragment, label=f"backend_fragments[{namespace!r}]")
        conflicts = sorted(set(fragment) & RESERVED_BACKEND_FRAGMENT_KEYS)
        if conflicts:
            raise ValueError(
                f"backend fragment {namespace!r} attempts to overwrite core-owned keys: "
                f"{', '.join(conflicts)}"
            )
        fragments[namespace] = fragment
    return fragments


@dataclass(frozen=True)

exec
/bin/zsh -lc "sed -n '1500,1843p' astrid/core/rendering/contracts.py && sed -n '1844,2195p' astrid/core/rendering/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:


def _validate_backend_fragments(value: Any) -> dict[str, dict[str, Any]]:
    mapping = _require_mapping(value, "backend_fragments")
    fragments: dict[str, dict[str, Any]] = {}
    for raw_namespace, raw_fragment in mapping.items():
        namespace = _require_qualified_id(raw_namespace, "backend fragment namespace")
        fragment = _json_safe_mapping(raw_fragment, label=f"backend_fragments[{namespace!r}]")
        conflicts = sorted(set(fragment) & RESERVED_BACKEND_FRAGMENT_KEYS)
        if conflicts:
            raise ValueError(
                f"backend fragment {namespace!r} attempts to overwrite core-owned keys: "
                f"{', '.join(conflicts)}"
            )
        fragments[namespace] = fragment
    return fragments


@dataclass(frozen=True)
class RenderResult:
    """Successful renderer/finalizer result written to the authoritative path."""

    schema_version: int
    video: VideoArtifact
    audio_ownership: AudioOwnership
    backend_fragments: dict[str, dict[str, Any]] = field(default_factory=dict)
    normalization: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        version = _require_schema_version(self.schema_version, "render result")
        video = (
            self.video
            if isinstance(self.video, VideoArtifact)
            else VideoArtifact.from_dict(_require_mapping(self.video, "video"))
        )
        ownership = _coerce_audio_ownership(
            self.audio_ownership,
            "audio_ownership",
            nullable=False,
        )
        if video.audio is None or video.audio != ownership:
            raise ValueError("video.audio must be present and match result audio_ownership")
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "video", video)
        object.__setattr__(self, "backend_fragments", _validate_backend_fragments(self.backend_fragments))
        object.__setattr__(self, "audio_ownership", ownership)
        object.__setattr__(
            self,
            "normalization",
            _require_string_list(self.normalization, "normalization"),
        )
        object.__setattr__(self, "logs", _require_string_list(self.logs, "logs"))
        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))

    @property
    def attachments(self) -> dict[str, Attachment]:
        """The sole authoritative attachment map, owned by the primary video."""

        return self.video.attachments

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "video": self.video,
                "backend_fragments": self.backend_fragments,
                "audio_ownership": self.audio_ownership,
                "normalization": self.normalization,
                "logs": self.logs,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderResult:
        try:
            data = _require_mapping(payload, "render result")
            allowed = set(RENDER_RESULT_CORE_KEYS)
            _validate_object_keys(
                data,
                required={"schema_version", "video", "audio_ownership"},
                allowed=allowed,
                label="render result",
            )
            version = _require_schema_version(data["schema_version"], "render result")
            return cls(
                schema_version=version,
                video=VideoArtifact.from_dict(data["video"]),
                audio_ownership=data["audio_ownership"],
                backend_fragments=data.get("backend_fragments", {}),
                normalization=data.get("normalization", []),
                logs=data.get("logs", []),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed render result: {exc}",
                details={"error_type": type(exc).__name__},
            )


@dataclass(frozen=True)
class RendererError:
    """Language-neutral structured renderer failure payload."""

    schema_version: int
    kind: RendererErrorKind
    backend: str
    message: str
    recovery_command: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    KINDS: ClassVar[frozenset[str]] = frozenset(
        {
            "protocol",
            "unsupported",
            "binary_missing",
            "timeout",
            "interrupted",
            "invalid_artifact",
            "internal",
        }
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(self.schema_version, "renderer error"),
        )
        kind = _require_string(self.kind, "renderer error kind")
        if kind not in self.KINDS:
            raise ValueError(f"unknown renderer error kind: {kind}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "backend", _require_qualified_id(self.backend, "error backend"))
        object.__setattr__(self, "message", _require_string(self.message, "error message"))
        object.__setattr__(
            self,
            "recovery_command",
            _require_optional_string(self.recovery_command, "recovery_command"),
        )
        object.__setattr__(self, "details", _json_safe_mapping(self.details, label="error details"))

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "kind": self.kind,
                "backend": self.backend,
                "message": self.message,
                "recovery_command": self.recovery_command,
                "details": self.details,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RendererError:
        try:
            data = _require_mapping(payload, "renderer error")
            required = {
                "schema_version",
                "kind",
                "backend",
                "message",
                "recovery_command",
                "details",
            }
            _validate_object_keys(data, required=required, allowed=required, label="renderer error")
            return cls(
                schema_version=data["schema_version"],
                kind=data["kind"],
                backend=data["backend"],
                message=data["message"],
                recovery_command=data["recovery_command"],
                details=data["details"],
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed renderer error: {exc}",
                details={"error_type": type(exc).__name__},
            )


@dataclass(frozen=True)
class FinalizeRequest:
    """Wire request consumed by the ``finalize`` operation."""

    schema_version: int
    plan: RenderPlan
    artifacts: list[VideoArtifact]
    output_name: str
    backend_config: BackendConfig = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        version = _require_schema_version(self.schema_version, "finalize request")
        plan = (
            self.plan
            if isinstance(self.plan, RenderPlan)
            else RenderPlan.from_dict(_require_mapping(self.plan, "plan"))
        )
        if isinstance(self.artifacts, (str, bytes)) or not isinstance(self.artifacts, Sequence):
            raise TypeError("artifacts must be an array")
        artifacts = [
            artifact
            if isinstance(artifact, VideoArtifact)
            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
            for index, artifact in enumerate(self.artifacts)
        ]
        if len(artifacts) != len(plan.segments):
            raise ValueError("finalize artifacts must correspond one-for-one with plan segments")
        if plan.total_frames == 0:
            raise ValueError("an empty render plan must not be finalized")
        attachment_names: set[str] = set()
        for index, artifact in enumerate(artifacts):
            duplicates = sorted(attachment_names & set(artifact.attachments))
            if duplicates:
                raise ValueError(
                    "duplicate attachment names across segment artifacts at "
                    f"artifacts[{index}]: {', '.join(duplicates)}"
                )
            attachment_names.update(artifact.attachments)
        output_name = _require_string(self.output_name, "output_name")
        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
            raise ValueError("output_name must be a portable basename without path separators")
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "output_name", output_name)
        backend_config = _coerce_namespaced_backend_config(
            self.backend_config,
            "backend_config",
        )
        unexpected_config = sorted(set(backend_config) - {plan.finalizer.id})
        if unexpected_config:
            raise ValueError(
                "finalize backend_config may contain only the selected finalizer namespace "
                f"{plan.finalizer.id!r}"
            )
        object.__setattr__(self, "backend_config", backend_config)
        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))

    @property
    def expected_attachments(self) -> dict[str, Attachment]:
        """Return the globally unique attachments a finalizer must preserve."""

        return {
            name: attachment
            for artifact in self.artifacts
            for name, attachment in artifact.attachments.items()
        }

    def validate_final_result(
        self,
        result: RenderResult | Mapping[str, Any],
    ) -> RenderResult:
        """Validate attachment preservation on a standalone finalizer response.

        Finalizers may add new attachments, but every input attachment must be
        present under the same name with the exact same descriptor and digest.
        """

        final_result = (
            result
            if isinstance(result, RenderResult)
            else RenderResult.from_dict(_require_mapping(result, "final result"))
        )
        missing = sorted(set(self.expected_attachments) - set(final_result.attachments))
        if missing:
            raise ValueError("finalizer dropped attachments: " + ", ".join(missing))
        changed = sorted(
            name
            for name, expected in self.expected_attachments.items()
            if final_result.attachments[name] != expected
        )
        if changed:
            raise ValueError("finalizer changed attachments: " + ", ".join(changed))
        return final_result

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "plan": self.plan,
                "artifacts": self.artifacts,
                "output_name": self.output_name,
                "backend_config": self.backend_config,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizeRequest:
        try:
            data = _require_mapping(payload, "finalize request")
            allowed = {
                "schema_version",
                "plan",
                "artifacts",
                "output_name",
                "backend_config",
                "metadata",
            }
            _validate_object_keys(
                data,
                required={"schema_version", "plan", "artifacts", "output_name"},
                allowed=allowed,
                label="finalize request",
            )
            version = _require_schema_version(data["schema_version"], "finalize request")
            return cls(
                schema_version=version,
                plan=RenderPlan.from_dict(data["plan"]),
                artifacts=[VideoArtifact.from_dict(item) for item in data["artifacts"]],
                output_name=data["output_name"],
                backend_config=data.get("backend_config", {}),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed finalize request: {exc}",
                details={"error_type": type(exc).__name__},
            )


_PERMISSIONS = frozenset(
    {"project_files", "network", "subprocess", "environment", "accelerator", "external_services"}
)


def _manifest_capability_object(
    value: Any,
    *,
    label: str,
    allowed: frozenset[str],
) -> dict[str, Any]:
    capabilities = _json_safe_mapping(value, label=label)
    unknown = sorted(set(capabilities) - allowed)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
    return capabilities


def _manifest_string_array(value: Any, label: str) -> list[str]:
    items = _require_string_list(value, label)
    if len(items) != len(set(items)):
        raise ValueError(f"{label} must not contain duplicates")
    return items


def _manifest_features(value: Any, label: str) -> dict[str, bool | str]:
    raw = _require_mapping(value, label)
    result: dict[str, bool | str] = {}
    for raw_key, raw_value in raw.items():
        key = _require_string(raw_key, f"{label} key")
        if isinstance(raw_value, bool):
            result[key] = raw_value
        elif isinstance(raw_value, str):
            result[key] = _require_string(raw_value, f"{label}[{key!r}]")
        else:
            raise TypeError(f"{label}[{key!r}] must be a boolean or string")
    return result


def _manifest_boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{label} must be a boolean")
    return value


@dataclass(frozen=True)
class _CommandManifest:
    schema_version: int
    id: str
    name: str
    version: str
    protocol_version: int
    command: tuple[str, ...]
    operations: tuple[str, ...]
    description: str | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    required_permissions: tuple[str, ...] = ()
    required_binaries: tuple[str, ...] = ()
    timeout_seconds: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    REQUIRED_OPERATION: ClassVar[str]
    ALLOWED_OPERATIONS: ClassVar[frozenset[str]]
    LABEL: ClassVar[str]

    @classmethod
    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
        return _json_safe_mapping(value, label=f"{cls.LABEL} capabilities")

    def __post_init__(self) -> None:
        version = _require_int(self.schema_version, "schema_version")
        if version != SCHEMA_VERSION:
            _protocol_failure(
                f"unknown {self.LABEL} schema_version {version}; expected {SCHEMA_VERSION}",
                details={"received": version, "supported": [SCHEMA_VERSION]},
            )
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "id", _require_qualified_id(self.id, f"{self.LABEL} id"))
        object.__setattr__(self, "name", _require_string(self.name, f"{self.LABEL} name"))
        object.__setattr__(self, "version", _require_string(self.version, f"{self.LABEL} version"))
        protocol_version = _require_int(self.protocol_version, "protocol_version")
        if protocol_version != SCHEMA_VERSION:
            _protocol_failure(
                f"unsupported {self.LABEL} protocol_version {protocol_version}; "
                f"expected {SCHEMA_VERSION}",
                details={"received": protocol_version, "supported": [SCHEMA_VERSION]},
            )
        object.__setattr__(self, "protocol_version", protocol_version)
        command = tuple(_require_string_list(self.command, "command"))
        if not command:
            raise ValueError("command must contain at least one argument")
        object.__setattr__(self, "command", command)
        operations = tuple(_require_string_list(self.operations, "operations"))
        if self.REQUIRED_OPERATION not in operations:
            raise ValueError(f"{self.LABEL} operations must include {self.REQUIRED_OPERATION!r}")
        unknown_operations = sorted(set(operations) - self.ALLOWED_OPERATIONS)
        if unknown_operations:
            raise ValueError(
                f"{self.LABEL} has unsupported operations: {', '.join(unknown_operations)}"
            )
        if len(operations) != len(set(operations)):
            raise ValueError("operations must not contain duplicates")
        object.__setattr__(self, "operations", operations)
        object.__setattr__(
            self,
            "description",
            _require_optional_string(self.description, "description"),
        )
        object.__setattr__(
            self,
            "capabilities",
            self._normalize_capabilities(self.capabilities),
        )
        permissions = tuple(_require_string_list(self.required_permissions, "required_permissions"))
        unknown_permissions = sorted(set(permissions) - _PERMISSIONS)
        if unknown_permissions:
            raise ValueError(f"unknown required permissions: {', '.join(unknown_permissions)}")
        if len(permissions) != len(set(permissions)):
            raise ValueError("required_permissions must not contain duplicates")
        object.__setattr__(self, "required_permissions", permissions)
        binaries = tuple(_require_string_list(self.required_binaries, "required_binaries"))
        if len(binaries) != len(set(binaries)):
            raise ValueError("required_binaries must not contain duplicates")
        object.__setattr__(self, "required_binaries", binaries)
        if self.timeout_seconds is not None:
            object.__setattr__(
                self,
                "timeout_seconds",
                _require_int(self.timeout_seconds, "timeout_seconds", minimum=1),
            )
        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "id": self.id,
                "name": self.name,
                "version": self.version,
                "protocol_version": self.protocol_version,
                "command": self.command,
                "operations": self.operations,
                "description": self.description,
                "capabilities": self.capabilities,
                "required_permissions": self.required_permissions,
                "required_binaries": self.required_binaries,
                "timeout_seconds": self.timeout_seconds,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> _CommandManifest:
        try:
            data = _require_mapping(payload, cls.LABEL)
            allowed = {
                "schema_version",
                "id",
                "name",
                "version",
                "protocol_version",
                "command",
                "operations",
                "description",
                "capabilities",
                "required_permissions",
                "required_binaries",
                "timeout_seconds",
                "metadata",
            }
            _validate_object_keys(
                data,
                required={
                    "schema_version",
                    "id",
                    "name",
                    "version",
                    "protocol_version",
                    "command",
                    "operations",
                },
                allowed=allowed,
                label=cls.LABEL,
            )
            return cls(
                schema_version=data["schema_version"],
                id=data["id"],
                name=data["name"],
                version=data["version"],
                protocol_version=data["protocol_version"],
                command=data["command"],
                operations=data["operations"],
                description=data.get("description"),
                capabilities=data.get("capabilities", {}),
                required_permissions=data.get("required_permissions", ()),
                required_binaries=data.get("required_binaries", ()),
                timeout_seconds=data.get("timeout_seconds"),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed {cls.LABEL}: {exc}",
                details={"error_type": type(exc).__name__},
            )


@dataclass(frozen=True)
class RendererManifest(_CommandManifest):
    REQUIRED_OPERATION: ClassVar[str] = "render"
    ALLOWED_OPERATIONS: ClassVar[frozenset[str]] = frozenset({"render", "support"})
    LABEL: ClassVar[str] = "renderer manifest"

    @classmethod
    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
        capabilities = _manifest_capability_object(
            value,
            label="renderer capabilities",
            allowed=frozenset(
                {
                    "clip_types",
                    "track_types",
                    "features",
                    "supports_full_timeline",
                    "supports_windows",
                    "output_profiles",
                    "audio_ownership",
                }
            ),
        )
        result: dict[str, Any] = {}
        for key in ("clip_types", "track_types", "output_profiles"):
            if key in capabilities:
                result[key] = _manifest_string_array(capabilities[key], key)
        if "features" in capabilities:
            result["features"] = _manifest_features(capabilities["features"], "features")
        for key in ("supports_full_timeline", "supports_windows"):
            if key in capabilities:
                result[key] = _manifest_boolean(capabilities[key], key)
        if "audio_ownership" in capabilities:
            audio_modes = _manifest_string_array(
                capabilities["audio_ownership"],
                "audio_ownership",
            )
            for index, mode in enumerate(audio_modes):
                _coerce_audio_ownership(mode, f"audio_ownership[{index}]", nullable=False)
            result["audio_ownership"] = audio_modes
        return result


@dataclass(frozen=True)
class PlannerManifest(_CommandManifest):
    REQUIRED_OPERATION: ClassVar[str] = "plan"
    ALLOWED_OPERATIONS: ClassVar[frozenset[str]] = frozenset({"plan", "support"})
    LABEL: ClassVar[str] = "planner manifest"

    @classmethod
    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
        capabilities = _manifest_capability_object(
            value,
            label="planner capabilities",
            allowed=frozenset({"policies", "supports_fallback", "features"}),
        )
        result: dict[str, Any] = {}
        if "policies" in capabilities:
            result["policies"] = _manifest_string_array(capabilities["policies"], "policies")
        if "supports_fallback" in capabilities:
            result["supports_fallback"] = _manifest_boolean(
                capabilities["supports_fallback"],
                "supports_fallback",
            )
        if "features" in capabilities:
            result["features"] = _manifest_features(capabilities["features"], "features")
        return result


@dataclass(frozen=True)
class FinalizerManifest(_CommandManifest):
    REQUIRED_OPERATION: ClassVar[str] = "finalize"
    ALLOWED_OPERATIONS: ClassVar[frozenset[str]] = frozenset({"finalize", "support"})
    LABEL: ClassVar[str] = "finalizer manifest"

    @classmethod
    def _normalize_capabilities(cls, value: Any) -> dict[str, Any]:
        capabilities = _manifest_capability_object(
            value,
            label="finalizer capabilities",
            allowed=frozenset(
                {"containers", "preserves_attachments", "audio_ownership", "features"}
            ),
        )
        result: dict[str, Any] = {}
        if "containers" in capabilities:
            result["containers"] = _manifest_string_array(capabilities["containers"], "containers")
        if "preserves_attachments" in capabilities:
            result["preserves_attachments"] = _manifest_boolean(
                capabilities["preserves_attachments"],
                "preserves_attachments",
            )
        if "audio_ownership" in capabilities:
            audio_modes = _manifest_string_array(
                capabilities["audio_ownership"],
                "audio_ownership",
            )
            for index, mode in enumerate(audio_modes):
                _coerce_audio_ownership(mode, f"audio_ownership[{index}]", nullable=False)
            result["audio_ownership"] = audio_modes
        if "features" in capabilities:
            result["features"] = _manifest_features(capabilities["features"], "features")
        return result


def parse_wire_result(payload: Mapping[str, Any]) -> RenderResult | RendererError:
    """Parse the authoritative result file as success or structured failure."""

    try:
        data = _require_mapping(payload, "wire result")
        if "kind" in data or "backend" in data or "message" in data:
            return RendererError.from_dict(data)
        return RenderResult.from_dict(data)
    except Exception as exc:
        from .errors import RendererException

        if isinstance(exc, RendererException):
            raise
        _protocol_failure(
            f"malformed renderer result: {exc}",
            details={"error_type": type(exc).__name__},
        )


__all__ = [
    "Attachment",
    "AudioOwnership",
    "BackendConfig",
    "compute_request_digest",
    "FinalizeRequest",
    "FinalizerResolution",
    "FinalizerManifest",
    "FrameWindow",
    "PlannerManifest",
    "PlannerResolution",
    "RenderPlan",
    "RenderProfile",
    "RenderRequest",
    "RenderResult",
    "RenderSegment",
    "RendererError",
    "RendererManifest",
    "RendererResolution",
    "SupportReport",
    "VideoArtifact",
    "parse_wire_result",
]

exec
/bin/zsh -lc "rg -n \"class PackDefinition|schema_version:\" astrid/core/pack -g '*.py' | sed -n '1,120p' && rg -n \"class InstallRecord|schema_version\" astrid/core/pack/store.py | sed -n '1,160p' && sed -n '50,160p' astrid/core/pack/store.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/pack/definition.py:32:class PackDefinition:
astrid/core/pack/definition.py:44:    schema_version: str = field(default="")
astrid/core/pack/cli_basic.py:216:        f"""schema_version: 1
astrid/core/pack/store.py:51:    schema_version: int | str
45:class InstallRecord:
51:    schema_version: int | str
    version: str
    schema_version: int | str
    source_path: str
    installed_at: str  # ISO-8601 UTC
    revision: str  # revision directory name, e.g. "<pack_id>" or "<pack_id>.<ts>"
    install_root: str  # absolute path of the per-pack root (<packs root>/<pack_id>)
    active: bool = True

    # Extended fields (populated when available)
    manifest_digest: str = ""
    component_inventory: dict[str, int] = field(default_factory=dict)
    entrypoints: list[str] = field(default_factory=list)
    declared_secrets: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    trust_summary: dict = field(default_factory=dict)

    # Git-backed and trust fields (all defaulted for backward compat)
    source_type: str = "local"  # "local" or "git"
    git_url: str = ""  # durable Git URL (not temp checkout path)
    commit_sha: str = ""  # pinned commit SHA (40 hex chars)
    requested_ref: str = ""  # branch/tag requested at install time
    astrid_version: str = ""  # from pack manifest data.get('astrid_version', '')
    trust_tier: str = ""  # "local" or "git"
    last_validation_time: str = ""  # ISO-8601 UTC of last validation
    previous_active_revision: str = ""  # revision dir name replaced during force-install
    trust_acknowledged_at: str = ""  # ISO-8601 UTC when trust was accepted
    trust_method: str = ""  # "interactive", "cli_flag", "api", or "test"
    trust_actor: str = ""  # "cli", "api", "test", or another caller label
    no_sandbox_warning_version: int | None = None
    permissions_accepted: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "InstallRecord":
        # Filter to known fields to stay forward-compatible
        valid = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# InstalledPackStore
# ---------------------------------------------------------------------------


class InstalledPackStore:
    """Manage installed packs under the per-user packs home.

    The *packs_home* parameter (defaults to ``installed_packs_root()``)
    exists so tests can use temporary directories.
    """

    def __init__(self, packs_home: str | Path | None = None) -> None:
        self._home = Path(packs_home) if packs_home else installed_packs_root()

    # -- path helpers --------------------------------------------------------

    def install_root_for(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>``."""
        return self._home / pack_id

    def active_symlink_path(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/active`` (the symlink)."""
        return self.install_root_for(pack_id) / "active"

    def revisions_dir(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/revisions``."""
        return self.install_root_for(pack_id) / "revisions"

    def active_revision_path(self, pack_id: str) -> Path | None:
        """Resolve the *active* symlink to the real revision directory.

        Returns ``None`` when the symlink does not exist or is broken.
        """
        link = self.active_symlink_path(pack_id)
        try:
            resolved = link.resolve(strict=False)
        except OSError:
            return None
        if not resolved.is_dir():
            return None
        return resolved

    def staging_path_for(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/staging``."""
        return self.install_root_for(pack_id) / "staging"

    def lock_path_for(self, pack_id: str) -> Path:
        """Return ``<packs_home>/<pack_id>/.astrid/install.lock``."""
        return self.install_root_for(pack_id) / ".astrid" / "install.lock"

    # -- locking -------------------------------------------------------------

    def _acquire_lock(self, pack_id: str, timeout: float = 30.0):
        """Acquire a filelock for *pack_id*.  Returns a context-manager.

        If *filelock* is not available, returns a no-op context manager and
        emits a warning.
        """
        if _FileLock is None:
            import warnings
            warnings.warn(
                "filelock not installed; concurrent install protection disabled"
            )
            return _NoOpLock()

        lock_path = self.lock_path_for(pack_id)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        return _FileLock(str(lock_path), timeout=timeout)

exec
/bin/zsh -lc "rg -n \"def pack_rendering_manifest_paths|PACK_ALIAS_KINDS|PackAliasKind|_optional_pack_extensions\" astrid/core/pack -g '*.py' && sed -n '1,180p' astrid/core/pack/definition.py && rg -n \"def _validate_rendering_manifest_file|_register_capability_id|_pack_capability_locations\" -A80 -B20 astrid/core/pack/validate.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/pack/permissions.py:8:    PACK_ALIAS_KINDS,
astrid/core/pack/permissions.py:40:        if kind not in PACK_ALIAS_KINDS:
astrid/core/pack/permissions.py:42:                f"{alias_path}.kind must be one of {list(PACK_ALIAS_KINDS)}"
astrid/core/pack/permissions.py:123:def _optional_pack_extensions(value: Any, *, path: str) -> dict[str, Any]:
astrid/core/pack/loader.py:24:    _optional_pack_extensions,
astrid/core/pack/loader.py:133:    extensions = _optional_pack_extensions(data.get("extensions"), path="pack.extensions")
astrid/core/pack/validate.py:27:    PACK_ALIAS_KINDS,
astrid/core/pack/validate.py:32:    _optional_pack_extensions,
astrid/core/pack/validate.py:246:            kind: {} for kind in PACK_ALIAS_KINDS
astrid/core/pack/validate.py:250:            kind: AliasResolver() for kind in PACK_ALIAS_KINDS
astrid/core/pack/validate.py:537:            extensions=_optional_pack_extensions(data.get("extensions"), path="pack.extensions"),
astrid/core/pack/alias_resolver.py:12:from astrid.core.pack import PackAliasKind, PackDefinition
astrid/core/pack/alias_resolver.py:196:    kind: PackAliasKind,
astrid/core/pack/registry.py:260:def pack_rendering_manifest_paths(
astrid/core/pack/_common.py:40:PackAliasKind = Literal["executor", "orchestrator", "renderer", "planner", "finalizer"]
astrid/core/pack/_common.py:41:PACK_ALIAS_KINDS: tuple[PackAliasKind, ...] = (
astrid/core/pack/__init__.py:26:    PACK_ALIAS_KINDS,
astrid/core/pack/__init__.py:31:    PackAliasKind,
astrid/core/pack/__init__.py:76:    _optional_pack_extensions,
"""Pack data structures: :class:`PackDefinition` and :class:`PackPermission`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrid.core.pack._common import _normalize_json_value


@dataclass(frozen=True)
class PackPermission:
    id: str
    reason: str
    access: str = ""
    services: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "reason": self.reason,
        }
        if self.access:
            payload["access"] = self.access
        if self.services:
            payload["services"] = list(self.services)
        return payload


@dataclass(frozen=True)
class PackDefinition:
    id: str
    name: str
    version: str
    root: Path
    manifest_path: Path
    metadata: dict[str, Any]
    description: str = ""
    content: dict[str, Any] = field(default_factory=dict)
    agent: dict[str, Any] = field(default_factory=dict)
    status: str = field(default="active")
    visibility: str = field(default="visible")
    schema_version: str = field(default="")
    aliases: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    permissions: tuple[PackPermission, ...] = field(default_factory=tuple)
    extensions: dict[str, Any] = field(default_factory=dict)
    origin: str = field(default="unknown")
    install_tier: str = field(default="default")
    pack_type: str = field(default="capability")
    domain: str = field(default="general")
    stability: str = field(default="stable")
    support: str = field(default="project")

    def to_dict(self) -> dict[str, Any]:
        taxonomy = {
            "origin": self.origin,
            "install_tier": self.install_tier,
            "pack_type": self.pack_type,
            "domain": self.domain,
            "stability": self.stability,
            "support": self.support,
        }
        payload = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "root": str(self.root),
            "manifest_path": str(self.manifest_path),
            "metadata": dict(self.metadata),
            "content": dict(self.content),
            "agent": dict(self.agent),
            "status": self.status,
            "visibility": self.visibility,
            "schema_version": self.schema_version,
            **taxonomy,
            "taxonomy": taxonomy,
        }
        if self.aliases:
            payload["aliases"] = [dict(alias) for alias in self.aliases]
        if self.permissions:
            payload["permissions"] = [permission.to_dict() for permission in self.permissions]
        if self.extensions:
            payload["extensions"] = _normalize_json_value(
                self.extensions,
                path="pack.extensions",
            )
        return payload
225-
226-
227-class PackValidator:
228-    """Validates an external pack directory statically."""
229-
230-    def __init__(self, pack_root: Path):
231-        self.pack_root = pack_root.resolve()
232-        self.errors: list[str] = []
233-        self.warnings: list[str] = []
234-        self._pack_data: Optional[dict[str, Any]] = None
235-        self._layout_issues: list[LayoutValidationIssue] = []
236-        self._layout_exceptions: list[PackLayoutException] = []
237-
238-    def validate(self) -> list[str]:
239-        """Run all validations. Returns list of error strings (empty = valid)."""
240-        self.errors = []
241-        self.warnings = []
242-        self._layout_issues = []
243-        self._layout_exceptions = []
244-        self._capability_locations: dict[str, str] = {}
245:        self._pack_capability_locations: dict[str, dict[str, str]] = {
246-            kind: {} for kind in PACK_ALIAS_KINDS
247-        }
248-        self._alias_targets: list[tuple[str, str, str]] = []
249-        self._pack_alias_resolvers: dict[str, AliasResolver] = {
250-            kind: AliasResolver() for kind in PACK_ALIAS_KINDS
251-        }
252-        self._pack_alias_targets: list[tuple[str, str, str, str]] = []
253-
254-        if (self.pack_root / ".no-pack").exists():
255-            return self.errors
256-
257-        pack_yaml = pack_manifest_path(self.pack_root)
258-        if pack_yaml is None:
259-            self.errors.append(
260-                f"{self._rel(self.pack_root)}: pack manifest not found "
261-                f"(pack.yaml, pack.yml, or pack.json)"
262-            )
263-            return self.errors
264-
265-        # Parse pack.yaml
266-        pack_data = self._load_yaml(pack_yaml)
267-        if pack_data is None:
268-            return self.errors  # parse error already recorded
269-        self._pack_data = pack_data
270-
271-        # Check schema_version and validate against JSON Schema
272-        version = self._validate_manifest(
273-            pack_data, "pack", self._rel(pack_yaml)
274-        )
275-        if version is None:
276-            return self.errors  # schema_version error already recorded
277-
278-        self._validate_pack_taxonomy()
279-
280-        # Validate content roots exist
281-        content = pack_data.get("content", {})
282-        if isinstance(content, dict):
283-            self._validate_content_roots(content)
284-
285-        # Validate docs exist
286-        docs = pack_data.get("docs", {})
287-        if isinstance(docs, dict):
288-            self._validate_docs(docs)
289-
290-        # Validate component manifests
291-        self._validate_components(content)
292-        self._validate_pack_aliases()
293-        self._validate_alias_targets()
294-        self._validate_layout_contract()
295-        self._flush_layout_issues()
296-
297-        return self.errors
298-
299-    def validate_component_manifest(
300-        self,
301-        manifest_path: str | Path,
302-        manifest_kind: str,
303-    ) -> dict[str, Any] | None:
304-        """Load and schema-validate one component manifest.
305-
306-        This uses the same parsing and JSON Schema path as full pack validation,
307-        without requiring callers to validate a whole pack tree.
308-        """
309-        path = Path(manifest_path)
310-        data = self._load_yaml(path)
311-        if data is None:
312-            return None
313-        self._validate_manifest(data, manifest_kind, self._rel(path))
314-        return data
315-
316-    def _load_yaml(
317-        self,
318-        path: Path,
319-        *,
320-        manifest_kind: str = "pack",
321-    ) -> Optional[dict[str, Any]]:
322-        """Load a YAML file with safe_load. Returns None on error."""
323-        rel = self._rel(path)
324-        try:
325-            data = load_manifest_mapping(path, manifest_kind=manifest_kind)
--
555-        for kind, elem_dir in iter_element_roots(pack):
556-            manifest_path = find_component_manifest(elem_dir, "element")
557-            if manifest_path is not None:
558-                self._validate_element_manifest_file(pack, kind, manifest_path)
559-        try:
560-            rendering_manifest_paths = pack_rendering_manifest_paths(pack)
561-        except PackValidationError as exc:
562-            self.errors.append(f"pack.yaml: {exc}")
563-            return
564-        for manifest_kind, manifest_paths in zip(
565-            _RENDERING_MANIFEST_KINDS,
566-            rendering_manifest_paths,
567-        ):
568-            for manifest_path in manifest_paths:
569-                self._validate_rendering_manifest_file(
570-                    pack,
571-                    manifest_path,
572-                    manifest_kind,
573-                )
574-
575:    def _validate_rendering_manifest_file(
576-        self,
577-        pack: PackDefinition,
578-        manifest_path: Path,
579-        manifest_kind: str,
580-    ) -> None:
581-        data = self._load_yaml(manifest_path, manifest_kind=manifest_kind)
582-        if data is None:
583-            return
584-
585-        rel = self._rel(manifest_path)
586-        version = self._validate_manifest(data, manifest_kind, rel)
587-        if version is None:
588-            return
589-        capability_id = data.get("id")
590-        if not isinstance(capability_id, str):
591-            return
592:        self._register_capability_id(capability_id, rel)
593:        self._pack_capability_locations[manifest_kind][capability_id] = rel
594-        try:
595-            validate_content_id_in_pack(
596-                capability_id,
597-                pack,
598-                content_type=manifest_kind,
599-            )
600-        except ValueError as exc:
601-            self.errors.append(f"{rel}: {exc}")
602-
603-    def _validate_component_manifest_file(
604-        self,
605-        pack: PackDefinition,
606-        component_dir: Path,
607-        manifest_path: Path,
608-        manifest_kind: str,
609-    ) -> None:
610-        data = self._load_yaml(manifest_path)
611-        if data is None:
612-            return
613-
614-        rel = self._rel(manifest_path)
615-        version = self._validate_manifest(data, manifest_kind, rel)
616-        if version is None:
617-            return
618-        component_id = data.get("id")
619-        if isinstance(component_id, str):
620:            self._register_capability_id(component_id, rel)
621:            if manifest_kind in self._pack_capability_locations:
622:                self._pack_capability_locations[manifest_kind][component_id] = rel
623-            self._register_aliases(data, rel)
624-            try:
625-                validate_content_id_in_pack(
626-                    component_id,
627-                    pack,
628-                    content_type=manifest_kind,
629-                )
630-            except ValueError as exc:
631-                self.errors.append(f"{rel}: {exc}")
632-
633-        self._validate_runtime_entrypoints(component_dir, data, manifest_kind, rel)
634-        self._validate_runtime_definition(data, manifest_kind, rel)
635-
636-        docs = data.get("docs", {})
637-        stage = docs.get("stage", "STAGE.md") if isinstance(docs, dict) else "STAGE.md"
638-        stage_path = component_dir / stage
639-        if not stage_path.is_file():
640-            self.warnings.append(f"{self._rel(stage_path)}: STAGE.md not found")
641-
642-    def _validate_runtime_definition(
643-        self, data: dict[str, Any], manifest_kind: str, rel: str
644-    ) -> None:
645-        """Run the pack-tier runtime-reconciliation check after the JSON-Schema pass.
646-
647-        The JSON Schema is permissive about shapes the runtime parser rejects
648-        (e.g. a manifest declaring its runtime module twice with conflicting
649-        values). That structural check lives in the pack tier
650-        (``reconcile_runtime_module``); the executor / orchestrator schemas call
651-        the same helper at registry-load time, so running it here keeps
652-        ``packs validate`` parity without importing those upper tiers.
653-        """
654-        if manifest_kind == "executor":
655-            if isinstance(data, dict) and isinstance(data.get("executors"), list):
656-                items = data["executors"]
657-            else:
658-                items = [data]
659-            for item in items:
660-                self._reconcile_runtime_module(item, "executor", rel)
661-        elif manifest_kind == "orchestrator":
662-            self._reconcile_runtime_module(data, "orchestrator", rel)
663-
664-    def _reconcile_runtime_module(
665-        self, data: Any, component: str, rel: str
666-    ) -> None:
667-        """Apply the pack-tier runtime-module reconciliation check to one manifest."""
668-        if not isinstance(data, dict):
669-            return
670-        metadata = data.get("metadata", {})
671-        if not isinstance(metadata, dict):
672-            return
673-        try:
674-            reconcile_runtime_module(
675-                data.get("runtime"), metadata, ValidationError, component
676-            )
677-        except ValidationError as exc:
678-            self.errors.append(f"{rel}: {exc}")
679-
680-    def _validate_element_manifest_file(
681-        self,
682-        pack: PackDefinition,
683-        kind: str,
684-        manifest_path: Path,
685-    ) -> None:
686-        data = self._load_yaml(manifest_path)
687-        if data is None:
688-            return
689-
690-        rel = self._rel(manifest_path)
691-        version = self._validate_manifest(data, "element", rel)
692-        if version is None:
693-            return
694-        element_id = data.get("id")
695-        if isinstance(element_id, str):
696:            self._register_capability_id(f"{kind}/{element_id}", rel)
697-            self._register_aliases(data, rel)
698-        try:
699-            validate_element_pack_id(
700-                data.get("pack_id"),
701-                pack,
702-                element_root=manifest_path.parent,
703-            )
704-        except ValueError as exc:
705-            self.errors.append(f"{rel}: {exc}")
706-
707-    def _validate_runtime_entrypoints(
708-        self,
709-        component_dir: Path,
710-        data: dict[str, Any],
711-        manifest_kind: str,
712-        rel: str,
713-    ) -> None:
714-        if manifest_kind == "executor":
715-            self._check_runtime_entrypoint(component_dir, data.get("entrypoint"), "entrypoint")
716-            runtime = data.get("runtime", {})
717-            if isinstance(runtime, dict):
718-                self._check_runtime_entrypoint(component_dir, runtime.get("entrypoint"), "runtime entrypoint")
719-                self._check_command_entrypoint(component_dir, runtime.get("command"))
720-            self._check_command_entrypoint(component_dir, data.get("command"))
721-            self._check_metadata_runtime_file(component_dir, data)
722-            return
723-
724-        if manifest_kind != "orchestrator":
725-            return
726-
727-        runtime = data.get("runtime", {})
728-        if not isinstance(runtime, dict):
729-            return
730-        kind = runtime.get("kind")
731-        if kind == "python":
732-            self._check_python_module(component_dir, runtime.get("module"), rel, "runtime.module")
733-        elif kind == "command":
734-            self._check_command_entrypoint(component_dir, runtime.get("command"))
735-
736-    def _check_runtime_entrypoint(self, component_dir: Path, value: Any, label: str) -> None:
737-        if not isinstance(value, str) or not value.strip():
738-            return
739-        if "{" in value or "}" in value:
740-            return
741-        entrypoint_path = component_dir / value
742-        if not entrypoint_path.is_file():
743-            self.errors.append(f"{self._rel(entrypoint_path)}: {label} file not found")
744-
745-    def _check_metadata_runtime_file(self, component_dir: Path, data: dict[str, Any]) -> None:
746-        metadata = data.get("metadata", {})
747-        if not isinstance(metadata, dict):
748-            return
749-        self._check_runtime_entrypoint(component_dir, metadata.get("runtime_file"), "metadata.runtime_file")
750-        self._check_python_module(
751-            component_dir,
752-            metadata.get("runtime_module"),
753-            self._rel(component_dir),
754-            "metadata.runtime_module",
755-        )
756-
757-    def _check_command_entrypoint(self, component_dir: Path, command: Any) -> None:
758-        if isinstance(command, dict):
759-            argv = command.get("argv")
760-        else:
761-            argv = command
762-        if not isinstance(argv, list):
763-            return
764-        parts = [part for part in argv if isinstance(part, str)]
765-        for index, part in enumerate(parts):
766-            if part == "-m" and index + 1 < len(parts):
767-                self._check_python_module(
768-                    component_dir,
769-                    parts[index + 1],
770-                    self._rel(component_dir),
771-                    "command.argv module",
772-                )
773-                return
774-        for part in parts:
775-            if not self._looks_like_local_entrypoint(part):
776-                continue
--
823-            len(parts) >= 5
824-            and parts[0:2] == ["astrid", "packs"]
825-            and parts[2] == pack_id
826-            and parts[3] == component_dir.name
827-        ):
828-            return component_dir / Path(*parts[4:]).with_suffix(".py")
829-        if len(parts) >= 5 and parts[0:2] == ["astrid", "packs"]:
830-            pack_root = _REPO_ROOT / "astrid" / "packs" / parts[2]
831-            component_name = parts[3]
832-            tail = Path(*parts[4:]).with_suffix(".py")
833-            for kind_root in ("executors", "orchestrators"):
834-                candidate = pack_root / kind_root / component_name / tail
835-                if candidate.is_file():
836-                    return candidate
837-        if module.startswith("astrid."):
838-            return _REPO_ROOT / Path(*module.split(".")).with_suffix(".py")
839-        if "." not in module:
840-            return component_dir / f"{module}.py"
841-        return component_dir / Path(*module.split(".")).with_suffix(".py")
842-
843:    def _register_capability_id(self, capability_id: str, relpath: str) -> None:
844-        existing = self._capability_locations.get(capability_id)
845-        if existing is not None:
846-            self.errors.append(
847-                f"{relpath}: duplicate capability id {capability_id!r}; already declared in {existing}"
848-            )
849-            return
850-        self._capability_locations[capability_id] = relpath
851-
852-    def _register_aliases(self, data: dict[str, Any], relpath: str) -> None:
853-        metadata = data.get("metadata", {})
854-        if not isinstance(metadata, dict):
855-            return
856-        aliases = metadata.get("aliases", [])
857-        if not isinstance(aliases, list):
858-            self.errors.append(f"{relpath}: metadata.aliases must be an array")
859-            return
860-        for index, alias in enumerate(aliases):
861-            if isinstance(alias, str):
862-                self._alias_targets.append((relpath, f"metadata.aliases[{index}]", alias))
863-            elif isinstance(alias, dict):
864-                target = alias.get("canonical_id") or alias.get("target") or alias.get("id")
865-                if isinstance(target, str):
866-                    self._alias_targets.append((relpath, f"metadata.aliases[{index}]", target))
867-                else:
868-                    self.errors.append(f"{relpath}: metadata.aliases[{index}] must declare canonical_id")
869-            else:
870-                self.errors.append(f"{relpath}: metadata.aliases[{index}] must be a string or object")
871-
872-    def _validate_pack_aliases(self) -> None:
873-        if self._pack_data is None:
874-            return
875-        aliases = self._pack_data.get("aliases")
876-        if aliases is None:
877-            return
878-        try:
879-            normalized_aliases = _optional_pack_aliases(aliases, path="pack.aliases")
880-        except ValueError as exc:
881-            self.errors.append(f"pack.yaml: {exc}")
882-            return
883-
884-        for index, alias in enumerate(normalized_aliases):
885-            kind = str(alias["kind"])
886-            alias_id = str(alias["alias"])
887-            canonical_id = str(alias["canonical_id"])
888-            resolver = self._pack_alias_resolvers[kind]
889-            if resolver.is_alias(alias_id):
890-                self.errors.append(
891-                    f"pack.yaml: pack.aliases[{index}] duplicates existing {kind} alias {alias_id!r}"
892-                )
893-                continue
894-            try:
895-                resolver.register_alias(
896-                    alias_id,
897-                    canonical_id,
898-                    deprecated=bool(alias.get("deprecated", False)),
899-                    deprecation_message=str(alias.get("deprecation_message", "")),
900-                )
901-            except AliasResolutionError as exc:
902-                self.errors.append(f"pack.yaml: pack.aliases[{index}] {exc}")
903-                continue
904-            self._pack_alias_targets.append(
905-                ("pack.yaml", f"pack.aliases[{index}]", kind, canonical_id)
906-            )
907-
908-        for relpath, alias_path, kind, target in self._pack_alias_targets:
909-            resolved_target = self._pack_alias_resolvers[kind].resolve(target)
910-            pack_id = resolved_target.split(".", 1)[0]
911-            if pack_id != self._pack_id():
912-                continue
913:            if resolved_target not in self._pack_capability_locations[kind]:
914-                self.errors.append(
915-                    f"{relpath}: {alias_path} points to unknown {kind} id {resolved_target!r}"
916-                )
917-
918-    def _validate_alias_targets(self) -> None:
919-        for relpath, alias_path, target in self._alias_targets:
920-            if target not in self._capability_locations:
921-                self.errors.append(
922-                    f"{relpath}: {alias_path} points to unknown capability id {target!r}"
923-                )
924-
925-    # -----------------------------------------------------------------------
926-    # Layout contract validation (delegates to validate_layout module)
927-    # -----------------------------------------------------------------------
928-
929-    def _validate_layout_contract(self) -> None:
930-        """Validate the pack directory layout against the canonical contract."""
931-        if self._pack_data is None:
932-            return
933-        self._layout_exceptions, issues = parse_layout_exceptions(self._pack_data)
934-        self._layout_issues.extend(issues)
935-
936-    def _flush_layout_issues(self) -> None:
937-        """Surface any collected layout validation issues as errors."""
938-        if not self._layout_issues:
939-            return
940-        aggregate = PackLayoutContractError(self._layout_issues)
941-        self.errors.extend(aggregate.lines())
942-        self._layout_issues = []
943-
944-    def _pack_id(self) -> str:
945-        if self._pack_data is None:
946-            return self.pack_root.name
947-        value = self._pack_data.get("id")
948-        if isinstance(value, str) and value.strip():
949-            return value
950-        return self.pack_root.name
951-
952-    def _rel(self, path: Path) -> str:
953-        """Return a path relative to the pack root for error messages."""
954-        try:
955-            return str(path.relative_to(self.pack_root))
956-        except ValueError:
957-            return str(path)
958-
959-
960-def validate_pack(pack_root: str | Path) -> tuple[list[str], list[str]]:
961-    """Validate an external pack directory.
962-
963-    Args:
964-        pack_root: Path to the pack root directory.
965-
966-    Returns:
967-        A tuple of (errors, warnings). Empty errors list means valid.
968-    """
969-    validator = PackValidator(Path(pack_root))
970-    errors = validator.validate()
971-    return errors, validator.warnings
972-
973-
974-def json_loads(text: str) -> Any:
975-    """Load JSON, wrapping decode errors for consistent messaging."""
976-    return _json.loads(text)
977-
978-
979-def _check_semantic_secrets(data: dict[str, Any]) -> list[str]:
980-    warnings: list[str] = []
981-    secrets_raw = data.get("secrets")
982-    if not isinstance(secrets_raw, list):
983-        return warnings
984-    for idx, item in enumerate(secrets_raw):
985-        if not isinstance(item, dict):
986-            warnings.append(f"secrets[{idx}]: not a mapping, skipping")
987-            continue
988-        name = item.get("name")
989-        if not isinstance(name, str) or not name.strip():
990-            warnings.append(f"secrets[{idx}]: empty or missing secret name")
991-            continue
992-        if not item.get("required", False):
993-            description = item.get("description")

exec
/bin/zsh -lc "sed -n '230,325p' astrid/core/pack/registry.py && sed -n '1,240p' astrid/core/pack/manifest.py && sed -n '110,180p' astrid/core/pack/permissions.py && sed -n '34,55p' astrid/core/pack/_common.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    )


def _builtin_kind_descriptors() -> tuple[ElementKindDescriptor, ...]:
    return (
        *_builtin_element_kind_descriptors(),
        ElementKindDescriptor(catalog="transition", id="cross-fade", aliases=("crossfade",), default=True),
        ElementKindDescriptor(catalog="clip", id="video"),
        ElementKindDescriptor(catalog="clip", id="image"),
        ElementKindDescriptor(catalog="clip", id="audio"),
        ElementKindDescriptor(catalog="clip", id="text"),
        ElementKindDescriptor(catalog="clip", id="effect"),
        ElementKindDescriptor(catalog="clip", id="opaque"),
        ElementKindDescriptor(catalog="track", id="visual", default=True),
        ElementKindDescriptor(catalog="track", id="audio"),
    )


_BUILTIN_KIND_IDS_BY_CATALOG: dict[str, frozenset[str]] = {}
for _descriptor in _builtin_kind_descriptors():
    _BUILTIN_KIND_IDS_BY_CATALOG.setdefault(_descriptor.catalog, set()).add(_descriptor.canonical_name)
_BUILTIN_KIND_IDS_BY_CATALOG = {
    catalog: frozenset(ids)
    for catalog, ids in _BUILTIN_KIND_IDS_BY_CATALOG.items()
}


ELEMENT_KIND_REGISTRY = ElementKindRegistry()


def pack_rendering_manifest_paths(
    pack: "PackDefinition",
) -> tuple[tuple[Path, ...], tuple[Path, ...], tuple[Path, ...]]:
    """Return contained renderer, planner, and finalizer manifest paths.

    Rendering extensions name manifests relative to the pack root. Resolving
    every path before returning it also rejects traversal and symlink escapes.
    """
    rendering = pack.extensions.get("rendering", {})
    renderers = _resolve_pack_rendering_manifest_paths(
        pack,
        rendering.get("renderers", ()),
        kind="renderers",
    )
    planners = _resolve_pack_rendering_manifest_paths(
        pack,
        rendering.get("planners", ()),
        kind="planners",
    )
    finalizers = _resolve_pack_rendering_manifest_paths(
        pack,
        rendering.get("finalizers", ()),
        kind="finalizers",
    )
    return renderers, planners, finalizers


def _resolve_pack_rendering_manifest_paths(
    pack: "PackDefinition",
    paths: Iterable[str],
    *,
    kind: str,
) -> tuple[Path, ...]:
    root = pack.root.resolve()
    resolved_paths: list[Path] = []
    for index, raw_path in enumerate(paths):
        relative_path = Path(raw_path)
        resolved = (root / relative_path).resolve()
        if relative_path.is_absolute() or not resolved.is_relative_to(root):
            raise PackValidationError(
                f"pack.extensions.rendering.{kind}[{index}] must stay within the pack root"
            )
        resolved_paths.append(resolved)
    return tuple(resolved_paths)


def pack_element_kind_descriptors(pack: "PackDefinition") -> tuple[ElementKindDescriptor, ...]:
    element_extensions = pack.extensions.get("elements", {})
    kinds = element_extensions.get("kinds", ())
    return tuple(
        ElementKindDescriptor(
            id=kind["id"],
            singular=kind.get("singular", ""),
            plural=kind.get("plural", ""),
            label=kind.get("label", ""),
            description=kind.get("description", ""),
        )
        for kind in kinds
    )


def pack_timeline_kind_descriptors(pack: "PackDefinition") -> tuple[ElementKindDescriptor, ...]:
    timeline_extensions = pack.extensions.get("timeline", {})
    kinds = timeline_extensions.get("kinds", ())
    return tuple(
        ElementKindDescriptor(
"""Shared manifest parser for Astrid component manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

YAML_MANIFEST_SUFFIXES = frozenset({".yaml", ".yml"})
JSON_MANIFEST_SUFFIXES = frozenset({".json"})


class ManifestParseError(ValueError):
    """Raised when a manifest cannot be parsed with the canonical policy."""


def load_manifest_payload(path: str | Path, *, manifest_kind: str = "manifest") -> Any:
    """Load a JSON or YAML manifest with one parser policy.

    ``.json`` files are strict JSON. ``.yaml`` and ``.yml`` files use
    ``yaml.safe_load``. Runtime loaders and pack validation should share this
    function for component manifests so authoring syntax is accepted or rejected
    consistently.
    """
    manifest_path = Path(path)
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestParseError(f"cannot read {manifest_kind} manifest {manifest_path}: {exc}") from exc

    suffix = manifest_path.suffix.lower()
    if suffix in JSON_MANIFEST_SUFFIXES:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestParseError(
                f"invalid JSON {manifest_kind} manifest {manifest_path}: {exc.msg}"
            ) from exc

    if suffix in YAML_MANIFEST_SUFFIXES:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ManifestParseError(
                f"invalid YAML {manifest_kind} manifest {manifest_path}: {exc}"
            ) from exc
        if data is None:
            raise ManifestParseError(f"empty YAML {manifest_kind} manifest {manifest_path}")
        return data

    raise ManifestParseError(
        f"unsupported {manifest_kind} manifest extension {suffix!r} for {manifest_path}"
    )


def load_manifest_mapping(path: str | Path, *, manifest_kind: str = "manifest") -> dict[str, Any]:
    """Load a manifest and require a top-level object/mapping."""
    payload = load_manifest_payload(path, manifest_kind=manifest_kind)
    if not isinstance(payload, dict):
        raise ManifestParseError(
            f"{manifest_kind} manifest {Path(path)} must contain a mapping object, got {type(payload).__name__}"
        )
    return payload


def _runtime_block_module(runtime_raw: Any) -> str | None:
    """Return the module a ``runtime`` block declares, if any.

    Only the python-kind runtime block names a runtime module (``runtime.module``).
    Command / python-cli blocks declare argv or an entrypoint, not an import path,
    so they never collide with ``metadata.runtime_module``.
    """
    if not isinstance(runtime_raw, dict):
        return None
    if runtime_raw.get("kind") == "python":
        module = runtime_raw.get("module")
        if isinstance(module, str) and module:
            return module
    return None


def reconcile_runtime_module(
    runtime_raw: Any,
    metadata: dict[str, Any],
    error_cls: type[Exception],
    component: str,
) -> dict[str, Any]:
    """Fold a ``runtime.module`` declaration into ``metadata.runtime_module``.

    ``metadata.runtime_module`` is the single canonical runtime declaration the
    loaders read (SD2). A manifest may legacy-declare the same module inside a
    python ``runtime`` block; fold it into metadata so the module is declared
    exactly once, and reject a double-declaration that conflicts.
    """
    block_module = _runtime_block_module(runtime_raw)
    if block_module is None:
        return metadata
    meta_module = metadata.get("runtime_module")
    if isinstance(meta_module, str) and meta_module:
        if meta_module != block_module:
            raise error_cls(
                f"{component} declares its runtime module twice with conflicting "
                f"values: metadata.runtime_module={meta_module!r} vs "
                f"runtime.module={block_module!r}; declare it once via "
                f"metadata.runtime_module"
            )
        return metadata
    return {**metadata, "runtime_module": block_module}


def dump_manifest_payload(path: str | Path, payload: dict[str, Any]) -> None:
    """Write a deterministic JSON-compatible manifest.

    Fork writers historically rewrote ``*.yaml`` manifests as JSON-compatible
    text. Keep that stable; the loading policy remains YAML-aware.
    """
    manifest_path = Path(path)
    suffix = manifest_path.suffix.lower()
    if suffix not in JSON_MANIFEST_SUFFIXES and suffix not in YAML_MANIFEST_SUFFIXES:
        raise ManifestParseError(
            f"unsupported manifest extension {suffix!r} for {manifest_path}"
        )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(text, encoding="utf-8")


__all__ = [
    "JSON_MANIFEST_SUFFIXES",
    "ManifestParseError",
    "YAML_MANIFEST_SUFFIXES",
    "dump_manifest_payload",
    "load_manifest_mapping",
    "load_manifest_payload",
    "reconcile_runtime_module",
]
        return ()
    if not isinstance(value, list):
        raise PackValidationError(f"{path} must be an array")

    normalized: list[str] = []
    for index, raw_service in enumerate(value):
        service_path = f"{path}[{index}]"
        if not isinstance(raw_service, str) or not raw_service.strip():
            raise PackValidationError(f"{service_path} must be a non-empty string")
        normalized.append(raw_service.strip())
    return tuple(normalized)


def _optional_pack_extensions(value: Any, *, path: str) -> dict[str, Any]:
    if value is None:
        return {}
    data = _require_mapping(value, path)
    allowed_keys = {
        "generation",
        "elements",
        "timeline",
        "rendering",
        "schemas",
        "artifact_types",
    }
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise PackValidationError(f"{path} has unknown field(s): {', '.join(unknown_keys)}")

    normalized: dict[str, Any] = {}
    if "generation" in data:
        normalized["generation"] = _normalize_generation_extensions(
            data["generation"],
            path=f"{path}.generation",
        )
    if "elements" in data:
        normalized["elements"] = _normalize_element_extensions(
            data["elements"],
            path=f"{path}.elements",
        )
    if "timeline" in data:
        normalized["timeline"] = _normalize_timeline_extensions(
            data["timeline"],
            path=f"{path}.timeline",
        )
    if "rendering" in data:
        normalized["rendering"] = _normalize_rendering_extensions(
            data["rendering"],
            path=f"{path}.rendering",
        )
    if "schemas" in data:
        normalized["schemas"] = _normalize_json_object(
            data["schemas"],
            path=f"{path}.schemas",
        )
    if "artifact_types" in data:
        normalized["artifact_types"] = _normalize_artifact_types(
            data["artifact_types"],
            path=f"{path}.artifact_types",
        )
    return normalized


def _normalize_rendering_extensions(value: Any, *, path: str) -> dict[str, Any]:
    data = _require_mapping(value, path)
    allowed_keys = {"renderers", "planners", "finalizers"}
    unknown_keys = sorted(set(data) - allowed_keys)
    if unknown_keys:
        raise PackValidationError(f"{path} has unknown field(s): {', '.join(unknown_keys)}")

    normalized: dict[str, Any] = {}
    names = _COMPONENT_MANIFEST_NAMES.get(kind, ())
    for name in names:
        candidate = comp_dir / name
        if candidate.is_file():
            return candidate
    return None
PackAliasKind = Literal["executor", "orchestrator", "renderer", "planner", "finalizer"]
PACK_ALIAS_KINDS: tuple[PackAliasKind, ...] = (
    "executor",
    "orchestrator",
    "renderer",
    "planner",
    "finalizer",
)
PACK_PERMISSION_IDS: tuple[str, ...] = (
    "project_files",
    "network",
    "subprocess",
    "environment",
    "accelerator",
    "external_services",
)

exec
/bin/zsh -lc "rg -n \"def discover_pack_metadata\" -A240 astrid/core/pack/discovery.py && sed -n '1,150p' tests/core/rendering/test_registry_matrix.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
79:def discover_pack_metadata(
80-    *,
81-    project_root: str | Path = REPO_ROOT,
82-    extra_pack_roots: tuple[str, ...] = (),
83-    include_installed: bool = True,
84-    discover_packs_fn: DiscoverPacksFn | None = None,
85-) -> tuple[DiscoveredPack, ...]:
86-    """Return discovered packs in layered priority order.
87-
88-    Layers, in order: source-tree packs (excluding ``local``), the
89-    project-scoped ``local`` scratch pack when *project_root* differs from the
90-    repository root, explicit extra pack roots (excluding ``local``),
91-    ``ASTRID_PACKS_PATH`` roots (excluding ``local``), and installed packs
92-    (excluding ``local``) when *include_installed* is set.
93-
94-    *discover_packs_fn* overrides the source/local/extra layer scanner; callers
95-    pass their own module-level ``discover_packs`` so the historical per-registry
96-    test seam (``mock.patch("astrid.core.<x>.registry.discover_packs")``) keeps
97-    working. Defaults to :func:`astrid.core.pack.discover_packs`.
98-    """
99-    scan = discover_packs_fn if discover_packs_fn is not None else discover_packs
100-    repo_pack_root = (REPO_ROOT / "astrid" / "packs").resolve()
101-    project_pack_root = (Path(project_root) / "astrid" / "packs").resolve()
102-    local_pack_root = ensure_local_pack_for_elements(project_root=project_root)
103-
104-    discovered: list[DiscoveredPack] = []
105-
106-    def _add(pack: PackDefinition, source_kind: str) -> None:
107-        discovered.append(
108-            DiscoveredPack(
109-                pack=pack,
110-                source_kind=source_kind,
111-                priority_index=len(discovered),
112-            )
113-        )
114-
115-    for pack in scan():
116-        if pack.id == "local":
117-            continue
118-        _add(pack, "source")
119-
120-    if local_pack_root is not None and project_pack_root.is_dir():
121-        for pack in scan(project_pack_root):
122-            if pack.id == "local":
123-                _add(pack, "local")
124-
125-    def _resolve_pack_root(raw_root: str | Path) -> Path:
126-        candidate = Path(raw_root).expanduser()
127-        if not candidate.is_absolute():
128-            candidate = Path(project_root) / candidate
129-        return candidate.resolve()
130-
131-    raw_env_roots = os.environ.get(ASTRID_PACKS_PATH_ENV, "")
132-    if extra_pack_roots or raw_env_roots or include_installed:
133-        for extra_root in extra_pack_roots:
134-            extra_path = _resolve_pack_root(extra_root)
135-            if extra_path.is_dir():
136-                for pack in scan(extra_path):
137-                    if pack.id == "local":
138-                        continue
139-                    _add(pack, "extra")
140-        for env_root in raw_env_roots.split(os.pathsep):
141-            if env_root == "":
142-                continue
143-            resolved_env_root = _resolve_pack_root(env_root)
144-            if not resolved_env_root.is_dir():
145-                continue
146-            for pack in scan(resolved_env_root):
147-                if pack.id == "local":
148-                    continue
149-                _add(pack, "env")
150-        if include_installed:
151-            from astrid.core.pack import load_pack_manifest
152-            from astrid.core.pack import pack_manifest_path as _pmp
153-            from astrid.core.pack.store import installed_pack_roots
154-
155-            for installed_root in installed_pack_roots():
156-                if installed_root.is_dir():
157-                    mp = _pmp(installed_root)
158-                    if mp is not None:
159-                        pack = load_pack_manifest(mp)
160-                        if pack.id == "local":
161-                            continue
162-                        _add(pack, "installed")
163-
164-    return tuple(discovered)
165-
166-
167-def discover_packs_ordered(
168-    *,
169-    project_root: str | Path = REPO_ROOT,
170-    extra_pack_roots: tuple[str, ...] = (),
171-    include_installed: bool = True,
172-    discover_packs_fn: DiscoverPacksFn | None = None,
173-) -> tuple[Any, ...]:
174-    """Convenience wrapper returning just the ``PackDefinition`` objects.
175-
176-    Drop-in replacement for the per-registry ``_discover_*_packs`` helpers,
177-    preserving their exact ordering.
178-    """
179-    return tuple(
180-        dp.pack
181-        for dp in discover_pack_metadata(
182-            project_root=project_root,
183-            extra_pack_roots=extra_pack_roots,
184-            include_installed=include_installed,
185-            discover_packs_fn=discover_packs_fn,
186-        )
187-    )
188-
189-
190-__all__ = [
191-    "ASTRID_PACKS_PATH_ENV",
192-    "SOURCE_KINDS",
193-    "DiscoveredPack",
194-    "discover_pack_metadata",
195-    "discover_packs_ordered",
196-]
"""Discovery / eligibility matrix edge cases (T1.5).

Extends ``tests/core/rendering/test_registry.py`` (T1.4) with additional
edge cases that lock the static discovery, precedence, conflict, alias,
override, eligibility, and evidence contract of the rendering registries.

Every test here is fully static: fixture backends are never imported and
never executed (``backend.py`` / ``backend_should_not_import.py`` files
raise ``AssertionError`` if anything tries to run them).
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.pack import discover_packs, load_pack_manifest, pack_manifest_path
from astrid.core.pack.override import OverrideStore
from astrid.core.pack.store import InstallRecord, InstalledPackStore
from astrid.core.pack.validate import extract_trust_summary
from astrid.core.rendering import registry as rendering_registry_module
from astrid.core.rendering.registry import (
    RendererRegistryError,
    load_default_registries,
)


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "renderer_packs" / "discovery"
SOURCE_ROOT = FIXTURES / "source"
ENV_ROOT = FIXTURES / "env"
EXTRA_ROOT = FIXTURES / "extra"
INSTALLED_FIXTURES = FIXTURES / "installed"



def _scanner(source_root: Path):
    def scan(root: str | Path | None = None):
        return discover_packs(source_root if root is None else root)

    return scan


@contextmanager
def _load_with_source(
    project_root: Path,
    source_root: Path = SOURCE_ROOT,
    *,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = False,
):
    with (
        mock.patch.object(
            rendering_registry_module,
            "discover_packs",
            side_effect=_scanner(source_root),
        ),
        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
    ):
        yield load_default_registries(
            project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )


def _write_renderer_pack(
    packs_root: Path,
    pack_id: str,
    *,
    renderer_name: str,
    renderer_id: str | None = None,
    required_permissions: tuple[str, ...] = (),
    declared_permissions: tuple[str, ...] = (),
    duplicate_name: str | None = None,
) -> Path:
    pack_root = packs_root / pack_id
    manifests = pack_root / "manifests"
    manifests.mkdir(parents=True)
    manifest_names = ["a.renderer.yaml"]
    if duplicate_name is not None:
        manifest_names.append("b.renderer.yaml")
    permission_lines = "".join(
        f"  - id: {permission}\n    reason: Fixture permission.\n"
        for permission in declared_permissions
    )
    pack_lines = [
        "schema_version: 1",
        f"id: {pack_id}",
        f"name: {pack_id}",
        "version: 1.0.0",
    ]
    if permission_lines:
        pack_lines.append("permissions:\n" + permission_lines.rstrip())
    pack_lines.extend(
        [
            "extensions:",
            "  rendering:",
            "    renderers:",
            *(f"      - manifests/{name}" for name in manifest_names),
        ]
    )
    (pack_root / "pack.yaml").write_text("\n".join(pack_lines) + "\n", encoding="utf-8")

    capability_id = renderer_id or f"{pack_id}.renderer"
    names = [renderer_name, duplicate_name]
    for index, manifest_name in enumerate(manifest_names):
        required = ", ".join(required_permissions)
        body = [
            "schema_version: 1",
            f"id: {capability_id}",
            f"name: {names[index]}",
            "version: 1.0.0",
            "protocol_version: 1",
            "command: [python3, backend.py]",
            "operations: [render]",
        ]
        if required_permissions:
            body.append(f"required_permissions: [{required}]")
        (manifests / manifest_name).write_text("\n".join(body) + "\n", encoding="utf-8")
    (pack_root / "backend.py").write_text(
        'raise AssertionError("fixture backend must remain inert")\n',
        encoding="utf-8",
    )
    return pack_root


def _stage_installed_fixture(
    astrid_home: Path,
    pack_id: str,
    *,
    accepted_permissions: list[dict] | None = None,
) -> Path:
    fixture_name = pack_id
    fixture = INSTALLED_FIXTURES / fixture_name
    install_root = astrid_home / "packs" / pack_id
    revision = install_root / "revisions" / pack_id
    revision.parent.mkdir(parents=True)
    shutil.copytree(fixture, revision)
    (install_root / "active").symlink_to(Path("revisions") / pack_id)


exec
/bin/zsh -lc "wc -l -c /tmp/batch1-r5.diff && git diff 808030e..91f0fe3 > /dev/null 2>&1; cmp -s /tmp/batch1-r5.diff <(git diff 808030e..91f0fe3) || echo 'incremental diff differs from git diff representation' && git diff --check C1..HEAD -- ':"'!.oracle/**'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 41ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc "git blame -L 700,716 tests/core/rendering/test_contracts.py && git show 808030e:tests/core/rendering/test_contracts.py | sed -n '700,716p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
04767bfb (POM 2026-08-12 02:49:29 +0200 700)     assert payload["planner"]["override"] == planner.override
04767bfb (POM 2026-08-12 02:49:29 +0200 701)     assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
04767bfb (POM 2026-08-12 02:49:29 +0200 702)     assert payload["segments_v2"][0]["renderer"]["trust_eligibility"] == renderer.trust_eligibility
04767bfb (POM 2026-08-12 02:49:29 +0200 703)     assert payload["finalizer"]["alias_chain"] == finalizer.alias_chain
04767bfb (POM 2026-08-12 02:49:29 +0200 704)     assert payload["finalizer"]["trust_eligibility"] == finalizer.trust_eligibility
04767bfb (POM 2026-08-12 02:49:29 +0200 705) 
04767bfb (POM 2026-08-12 02:49:29 +0200 706) 
808030e1 (POM 2026-08-12 03:06:56 +0200 707) def test_resolution_records_require_all_seven_evidence_keys() -> None:
808030e1 (POM 2026-08-12 03:06:56 +0200 708)     """Every capability resolution requires the complete evidence set;
808030e1 (POM 2026-08-12 03:06:56 +0200 709)     a missing key is a structural protocol failure."""
808030e1 (POM 2026-08-12 03:06:56 +0200 710) def test_resolution_records_require_all_seven_evidence_keys() -> None:
808030e1 (POM 2026-08-12 03:06:56 +0200 711)     """Every capability resolution requires the complete evidence set;
808030e1 (POM 2026-08-12 03:06:56 +0200 712)     a missing key is a structural protocol failure."""
808030e1 (POM 2026-08-12 03:06:56 +0200 713)     cases = (
808030e1 (POM 2026-08-12 03:06:56 +0200 714)         (_planner(), PlannerResolution.from_dict),
808030e1 (POM 2026-08-12 03:06:56 +0200 715)         (_finalizer(), FinalizerResolution.from_dict),
808030e1 (POM 2026-08-12 03:06:56 +0200 716)         (_renderer(), RendererResolution.from_dict),
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

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

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '1,220p' && nl -ba astrid/core/rendering/provenance.py | sed -n '82,156p;181,246p' && nl -ba docs/contracts/render-backend-v1.md | sed -n '468,488p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	from collections.abc import Callable
     4	from copy import deepcopy
     5	from dataclasses import FrozenInstanceError, replace
     6	from pathlib import Path
     7	from typing import Any
     8	
     9	import pytest
    10	
    11	from astrid.core.rendering import (
    12	    Attachment,
    13	    AudioOwnership,
    14	    FrameWindow,
    15	    RenderPlan,
    16	    RenderProfile,
    17	    RenderRequest,
    18	    RenderResult,
    19	    RendererError,
    20	    SupportReport,
    21	    VideoArtifact,
    22	)
    23	from astrid.core.rendering.contracts import (
    24	    FinalizeRequest,
    25	    FinalizerManifest,
    26	    FinalizerResolution,
    27	    PlannerManifest,
    28	    PlannerResolution,
    29	    PROVENANCE_V1_COMPATIBILITY_KEYS,
    30	    RenderSegment,
    31	    RendererManifest,
    32	    RendererResolution,
    33	    parse_wire_result,
    34	)
    35	from astrid.core.rendering.errors import RendererProtocolError
    36	from astrid.core.rendering.provenance import (
    37	    assemble_provenance_v2,
    38	    hash_input_files,
    39	    validate_backend_fragments,
    40	    write_provenance_v2,
    41	)
    42	
    43	
    44	SHA_A = "a" * 64
    45	SHA_B = "b" * 64
    46	SHA_C = "c" * 64
    47	SHA_D = "d" * 64
    48	SHA_E = "e" * 64
    49	
    50	
    51	def _profile(*, audio: bool = True, fps: tuple[int, int] = (24, 1)) -> RenderProfile:
    52	    return RenderProfile(
    53	        width=1920,
    54	        height=1080,
    55	        fps_rational=fps,
    56	        time_base=(1, 12288),
    57	        container="mp4",
    58	        video_codec="h264",
    59	        video_profile="high",
    60	        video_level="4.1",
    61	        pixel_format="yuv420p",
    62	        audio_codec="aac" if audio else None,
    63	        audio_sample_rate=48000 if audio else None,
    64	        audio_channel_layout="stereo" if audio else None,
    65	        duration_tolerance=1,
    66	    )
    67	
    68	
    69	def _window(
    70	    start: int = 0,
    71	    end: int = 48,
    72	    *,
    73	    fps: tuple[int, int] = (24, 1),
    74	) -> FrameWindow:
    75	    return FrameWindow(
    76	        start_frame=start,
    77	        end_frame=end,
    78	        fps_rational=fps,
    79	        source_range=(10 + start, 10 + end),
    80	        speed=1.0,
    81	    )
    82	
    83	
    84	def _support(backend: str = "acme.example") -> SupportReport:
    85	    return SupportReport(
    86	        schema_version=1,
    87	        supported=True,
    88	        reasons=[],
    89	        features={"media": True, "audio_mode": "rendered"},
    90	        alternatives=[],
    91	        backend=backend,
    92	        backend_version="1.0.0",
    93	    )
    94	
    95	
    96	def _planner() -> PlannerResolution:
    97	    return PlannerResolution(
    98	        id="rendering.legacy_hybrid",
    99	        source_pack={"id": "rendering"},
   100	        manifest_digest=SHA_C,
   101	        trust_eligibility={"eligible": True, "method": "source-tree"},
   102	        alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
   103	        override=None,
   104	        support_decision=_support("rendering.legacy_hybrid"),
   105	    )
   106	
   107	
   108	def _renderer(backend: str = "acme.example", *, digest: str = SHA_B) -> RendererResolution:
   109	    return RendererResolution(
   110	        id=backend,
   111	        source_pack={"id": backend.split(".", 1)[0]},
   112	        manifest_digest=digest,
   113	        alias_chain=[backend],
   114	        override=None,
   115	        support_decision=_support(backend),
   116	        trust_eligibility={"eligible": True, "method": "source-tree"},
   117	    )
   118	
   119	
   120	def _finalizer() -> FinalizerResolution:
   121	    return FinalizerResolution(
   122	        id="rendering.ffmpeg-finalizer",
   123	        source_pack={"id": "rendering"},
   124	        manifest_digest=SHA_E,
   125	        alias_chain=["ffmpeg-finalizer", "rendering.ffmpeg-finalizer"],
   126	        override=None,
   127	        trust_eligibility={"eligible": True, "method": "source-tree"},
   128	        support_decision=_support("rendering.ffmpeg-finalizer"),
   129	    )
   130	
   131	
   132	def _segment(
   133	    start: int = 0,
   134	    end: int = 48,
   135	    *,
   136	    backend: str = "acme.example",
   137	    fps: tuple[int, int] = (24, 1),
   138	    digest: str = SHA_B,
   139	    renderer: RendererResolution | None = None,
   140	) -> RenderSegment:
   141	    return RenderSegment(
   142	        window=_window(start, end, fps=fps),
   143	        renderer=renderer or _renderer(backend, digest=digest),
   144	        input_hashes={"timeline": SHA_A},
   145	    )
   146	
   147	
   148	def _plan(
   149	    *,
   150	    segments: list[RenderSegment] | None = None,
   151	    total_frames: int = 48,
   152	    profile: RenderProfile | None = None,
   153	    window: FrameWindow | None = None,
   154	    planner: PlannerResolution | None = None,
   155	    finalizer: FinalizerResolution | None = None,
   156	) -> RenderPlan:
   157	    selected = [_segment()] if segments is None else segments
   158	    return RenderPlan(
   159	        schema_version=1,
   160	        request_digest=SHA_D,
   161	        requested_policy="hybrid",
   162	        planner=planner or _planner(),
   163	        segments=selected,
   164	        finalizer=finalizer or _finalizer(),
   165	        profile=profile or _profile(),
   166	        total_frames=total_frames,
   167	        reasons={str(index): "the request is supported" for index in range(len(selected))},
   168	        window=window,
   169	    )
   170	
   171	
   172	def _video(
   173	    *,
   174	    path: str = "outputs/video.mp4",
   175	    duration_frames: int = 48,
   176	    profile: RenderProfile | None = None,
   177	    audio: AudioOwnership = AudioOwnership.RENDERED,
   178	    attachments: dict[str, Attachment] | None = None,
   179	) -> VideoArtifact:
   180	    return VideoArtifact(
   181	        path=path,
   182	        profile=profile or _profile(),
   183	        sha256=SHA_A,
   184	        duration_frames=duration_frames,
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
