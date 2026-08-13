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

2026-08-12T01:56:58.527298Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:56:58.527377Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:56:58.527391Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:57:02.864838Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:57:02.864874Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:57:02.864879Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:57:07.663115Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:57:07.663156Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T01:57:07.663162Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "rg --files -g 'AGENTS.md' -g '"'!node_modules'"' -g '"'!vendor'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
AGENTS.md
examples/packs/media/AGENTS.md
examples/packs/file_summarizer/AGENTS.md
examples/packs/text_review/AGENTS.md
examples/packs/minimal/AGENTS.md
examples/packs/text_digest/AGENTS.md

exec
/bin/zsh -lc "pwd; git status --short --branch; git rev-parse HEAD; git show -s --format='%H%n%P%n%s' ab486f9; git diff --check 086d692..ab486f9" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## oracle-run
?? .oracle/checkins/batch-1-r7.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
ab486f9d5292bc6d2b60d523fbc55075a906d8ed
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
ab486f9d5292bc6d2b60d523fbc55075a906d8ed
086d692ea5c373470a2993c6a7e47b06e2f5bebc
batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r6.md:1585: trailing whitespace.
+   188	
.oracle/checkins/batch-1-r6.md:1586: trailing whitespace.
+   189	
.oracle/checkins/batch-1-r6.md:1599: trailing whitespace.
+   202	
.oracle/checkins/batch-1-r6.md:1600: trailing whitespace.
+   203	
.oracle/checkins/batch-1-r6.md:1615: trailing whitespace.
+   218	
.oracle/checkins/batch-1-r6.md:1616: trailing whitespace.
+   219	
.oracle/checkins/batch-1-r6.md:1620: trailing whitespace.
+    84	
.oracle/checkins/batch-1-r6.md:1621: trailing whitespace.
+    85	
.oracle/checkins/batch-1-r6.md:1650: trailing whitespace.
+   114	
.oracle/checkins/batch-1-r6.md:1651: trailing whitespace.
+   115	
.oracle/checkins/batch-1-r6.md:1676: trailing whitespace.
+   140	
.oracle/checkins/batch-1-r6.md:1677: trailing whitespace.
+   141	
.oracle/checkins/batch-1-r6.md:1692: trailing whitespace.
+   156	
.oracle/checkins/batch-1-r6.md:1708: trailing whitespace.
+   196	
.oracle/checkins/batch-1-r6.md:1715: trailing whitespace.
+   203	
.oracle/checkins/batch-1-r6.md:1735: trailing whitespace.
+   223	
.oracle/checkins/batch-1-r6.md:1761: trailing whitespace.
+   470	
.oracle/checkins/batch-1-r6.md:1775: trailing whitespace.
+   484	
.oracle/checkins/batch-1-r6.md:1813: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1815: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1819: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1822: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1838: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1839: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1842: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1843: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1848: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1850: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1851: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1863: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1864: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1884: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1885: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1888: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1895: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1896: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1948: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:1949: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2019: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2020: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2042: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2043: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2065: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2066: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2082: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2089: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2110: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2139: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2140: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2143: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2145: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2146: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2149: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2153: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2154: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2157: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2162: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2163: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2166: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2168: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2169: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2190: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2194: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2196: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2205: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2215: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2217: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2219: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2228: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2237: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2241: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2243: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2245: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2260: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2268: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2270: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2272: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2277: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2298: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2308: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2310: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2318: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2323: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2333: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2335: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2338: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2348: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2355: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2357: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2367: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2371: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2373: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2415: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2419: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2420: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2433: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2434: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2437: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2446: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2447: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2453: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2454: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2485: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2495: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2523: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2524: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2542: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2543: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2579: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2580: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2594: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2595: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2611: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2612: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2662: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2663: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2672: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2673: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2691: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2692: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2698: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2699: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2710: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2711: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2727: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2728: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2733: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2734: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2756: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2757: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:2766: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r6.md:2768: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r6.md:2772: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r6.md:2775: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r6.md:2791: trailing whitespace.
+    27	
.oracle/checkins/batch-1-r6.md:2792: trailing whitespace.
+    28	
.oracle/checkins/batch-1-r6.md:2795: trailing whitespace.
+    31	
.oracle/checkins/batch-1-r6.md:2796: trailing whitespace.
+    32	
.oracle/checkins/batch-1-r6.md:2801: trailing whitespace.
+    37	
.oracle/checkins/batch-1-r6.md:2803: trailing whitespace.
+    39	
.oracle/checkins/batch-1-r6.md:2804: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r6.md:2816: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r6.md:2817: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r6.md:2837: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r6.md:2838: trailing whitespace.
+    74	
.oracle/checkins/batch-1-r6.md:2841: trailing whitespace.
+    77	
.oracle/checkins/batch-1-r6.md:2848: trailing whitespace.
+    84	
.oracle/checkins/batch-1-r6.md:2849: trailing whitespace.
+    85	
.oracle/checkins/batch-1-r6.md:2895: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r6.md:2896: trailing whitespace.
+   132	
.oracle/checkins/batch-1-r6.md:2953: trailing whitespace.
+   189	
.oracle/checkins/batch-1-r6.md:2954: trailing whitespace.
+   190	
.oracle/checkins/batch-1-r6.md:2965: trailing whitespace.
+   201	
.oracle/checkins/batch-1-r6.md:2966: trailing whitespace.
+   202	
.oracle/checkins/batch-1-r6.md:2988: trailing whitespace.
+   224	
.oracle/checkins/batch-1-r6.md:2989: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r6.md:3005: trailing whitespace.
+   241	
.oracle/checkins/batch-1-r6.md:3012: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r6.md:3033: trailing whitespace.
+   269	
.oracle/checkins/batch-1-r6.md:3060: trailing whitespace.
+   296	
.oracle/checkins/batch-1-r6.md:3061: trailing whitespace.
+   297	
.oracle/checkins/batch-1-r6.md:3064: trailing whitespace.
+   300	
.oracle/checkins/batch-1-r6.md:3066: trailing whitespace.
+   302	
.oracle/checkins/batch-1-r6.md:3067: trailing whitespace.
+   303	
.oracle/checkins/batch-1-r6.md:3070: trailing whitespace.
+   306	
.oracle/checkins/batch-1-r6.md:3074: trailing whitespace.
+   310	
.oracle/checkins/batch-1-r6.md:3075: trailing whitespace.
+   311	
.oracle/checkins/batch-1-r6.md:3078: trailing whitespace.
+   314	
.oracle/checkins/batch-1-r6.md:3083: trailing whitespace.
+   319	
.oracle/checkins/batch-1-r6.md:3084: trailing whitespace.
+   320	
.oracle/checkins/batch-1-r6.md:3087: trailing whitespace.
+   323	
.oracle/checkins/batch-1-r6.md:3089: trailing whitespace.
+   325	
.oracle/checkins/batch-1-r6.md:3090: trailing whitespace.
+   326	
.oracle/checkins/batch-1-r6.md:3101: trailing whitespace.
+   520	
.oracle/checkins/batch-1-r6.md:3120: trailing whitespace.
+   539	
.oracle/checkins/batch-1-r6.md:3121: trailing whitespace.
+   540	
.oracle/checkins/batch-1-r6.md:3131: trailing whitespace.
+   550	
.oracle/checkins/batch-1-r6.md:3132: trailing whitespace.
+   551	
.oracle/checkins/batch-1-r6.md:3185: trailing whitespace.
+   604	
.oracle/checkins/batch-1-r6.md:3189: trailing whitespace.
+   608	
.oracle/checkins/batch-1-r6.md:3190: trailing whitespace.
+   609	
.oracle/checkins/batch-1-r6.md:3203: trailing whitespace.
+   622	
.oracle/checkins/batch-1-r6.md:3204: trailing whitespace.
+   623	
.oracle/checkins/batch-1-r6.md:3207: trailing whitespace.
+   626	
.oracle/checkins/batch-1-r6.md:3216: trailing whitespace.
+   635	
.oracle/checkins/batch-1-r6.md:3217: trailing whitespace.
+   636	
.oracle/checkins/batch-1-r6.md:3223: trailing whitespace.
+   642	
.oracle/checkins/batch-1-r6.md:3224: trailing whitespace.
+   643	
.oracle/checkins/batch-1-r6.md:3255: trailing whitespace.
+   674	
.oracle/checkins/batch-1-r6.md:3265: trailing whitespace.
+   684	
.oracle/checkins/batch-1-r6.md:3292: trailing whitespace.
+   711	
.oracle/checkins/batch-1-r6.md:3293: trailing whitespace.
+   712	
.oracle/checkins/batch-1-r6.md:3311: trailing whitespace.
+   730	
.oracle/checkins/batch-1-r6.md:3312: trailing whitespace.
+   731	
.oracle/checkins/batch-1-r6.md:3348: trailing whitespace.
+   767	
.oracle/checkins/batch-1-r6.md:3349: trailing whitespace.
+   768	
.oracle/checkins/batch-1-r6.md:3363: trailing whitespace.
+   782	
.oracle/checkins/batch-1-r6.md:3364: trailing whitespace.
+   783	
.oracle/checkins/batch-1-r6.md:3380: trailing whitespace.
+   799	
.oracle/checkins/batch-1-r6.md:3381: trailing whitespace.
+   800	
.oracle/checkins/batch-1-r6.md:3453: trailing whitespace.
+   453	
.oracle/checkins/batch-1-r6.md:3461: trailing whitespace.
+   461	
.oracle/checkins/batch-1-r6.md:3463: trailing whitespace.
+   463	
.oracle/checkins/batch-1-r6.md:3465: trailing whitespace.
+   465	
.oracle/checkins/batch-1-r6.md:3470: trailing whitespace.
+   470	
.oracle/checkins/batch-1-r6.md:3485: trailing whitespace.
+   485	
.oracle/checkins/batch-1-r6.md:3495: trailing whitespace.
+   495	
.oracle/checkins/batch-1-r6.md:3497: trailing whitespace.
+   497	
.oracle/checkins/batch-1-r6.md:3613: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r6.md:3619: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r6.md:3621: trailing whitespace.
+    10	
.oracle/checkins/batch-1-r6.md:3629: trailing whitespace.
+    18	
.oracle/checkins/batch-1-r6.md:3632: trailing whitespace.
+    21	
.oracle/checkins/batch-1-r6.md:3633: trailing whitespace.
+    22	
.oracle/checkins/batch-1-r6.md:3635: trailing whitespace.
+    24	
.oracle/checkins/batch-1-r6.md:3646: trailing whitespace.
+    35	
.oracle/checkins/batch-1-r6.md:3651: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r6.md:3663: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r6.md:3684: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r6.md:3704: trailing whitespace.
+    93	
.oracle/checkins/batch-1-r6.md:3721: trailing whitespace.
+   110	
.oracle/checkins/batch-1-r6.md:3738: trailing whitespace.
+   186	
.oracle/checkins/batch-1-r6.md:3739: trailing whitespace.
+   187	
.oracle/checkins/batch-1-r6.md:3746: trailing whitespace.
+   194	
.oracle/checkins/batch-1-r6.md:3747: trailing whitespace.
+   195	
.oracle/checkins/batch-1-r6.md:3757: trailing whitespace.
+   205	
.oracle/checkins/batch-1-r6.md:3758: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r6.md:3761: trailing whitespace.
+   209	
.oracle/checkins/batch-1-r6.md:3767: trailing whitespace.
+   215	
.oracle/checkins/batch-1-r6.md:3768: trailing whitespace.
+   216	
.oracle/checkins/batch-1-r6.md:3777: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r6.md:3778: trailing whitespace.
+   226	
.oracle/checkins/batch-1-r6.md:3783: trailing whitespace.
+   231	
.oracle/checkins/batch-1-r6.md:3784: trailing whitespace.
+   232	
.oracle/checkins/batch-1-r6.md:3793: trailing whitespace.
+   241	
.oracle/checkins/batch-1-r6.md:3794: trailing whitespace.
+   242	
.oracle/checkins/batch-1-r6.md:3800: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r6.md:3801: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r6.md:3814: trailing whitespace.
+   262	
.oracle/checkins/batch-1-r6.md:3815: trailing whitespace.
+   263	
.oracle/checkins/batch-1-r6.md:3820: trailing whitespace.
+   268	
.oracle/checkins/batch-1-r6.md:3821: trailing whitespace.
+   269	
.oracle/checkins/batch-1-r6.md:3828: trailing whitespace.
+   276	
.oracle/checkins/batch-1-r6.md:3829: trailing whitespace.
+   277	
.oracle/checkins/batch-1-r6.md:3836: trailing whitespace.
+   284	
.oracle/checkins/batch-1-r6.md:3837: trailing whitespace.
+   285	
.oracle/checkins/batch-1-r6.md:3846: trailing whitespace.
+   294	
.oracle/checkins/batch-1-r6.md:3847: trailing whitespace.
+   295	
.oracle/checkins/batch-1-r6.md:3854: trailing whitespace.
+   302	
.oracle/checkins/batch-1-r6.md:3855: trailing whitespace.
+   303	
.oracle/checkins/batch-1-r6.md:3864: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r6.md:3865: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r6.md:3880: trailing whitespace.
+   328	
.oracle/checkins/batch-1-r6.md:3881: trailing whitespace.
+   329	
.oracle/checkins/batch-1-r6.md:3914: trailing whitespace.
+   561	
.oracle/checkins/batch-1-r6.md:3915: trailing whitespace.
+   562	
.oracle/checkins/batch-1-r6.md:3922: trailing whitespace.
+   569	
.oracle/checkins/batch-1-r6.md:3927: trailing whitespace.
+   574	
.oracle/checkins/batch-1-r6.md:3933: trailing whitespace.
+   580	
.oracle/checkins/batch-1-r6.md:3934: trailing whitespace.
+   581	
.oracle/checkins/batch-1-r6.md:3938: trailing whitespace.
+   585	
.oracle/checkins/batch-1-r6.md:3943: trailing whitespace.
+   590	
.oracle/checkins/batch-1-r6.md:3955: trailing whitespace.
+   602	
.oracle/checkins/batch-1-r6.md:3960: trailing whitespace.
+   607	
.oracle/checkins/batch-1-r6.md:3972: trailing whitespace.
+   619	
.oracle/checkins/batch-1-r6.md:3984: trailing whitespace.
+   631	
.oracle/checkins/batch-1-r6.md:3985: trailing whitespace.
+   632	
.oracle/checkins/batch-1-r6.md:4006: trailing whitespace.
+   653	
.oracle/checkins/batch-1-r6.md:4007: trailing whitespace.
+   654	
.oracle/checkins/batch-1-r6.md:4011: trailing whitespace.
+   658	
.oracle/checkins/batch-1-r6.md:4018: trailing whitespace.
+   665	
.oracle/checkins/batch-1-r6.md:4041: trailing whitespace.
+   688	
.oracle/checkins/batch-1-r6.md:4053: trailing whitespace.
+   700	
.oracle/checkins/batch-1-r6.md:4068: trailing whitespace.
+   715	
.oracle/checkins/batch-1-r6.md:4089: trailing whitespace.
+   736	
.oracle/checkins/batch-1-r6.md:4090: trailing whitespace.
+   737	
.oracle/checkins/batch-1-r6.md:4097: trailing whitespace.
+   744	
.oracle/checkins/batch-1-r6.md:4098: trailing whitespace.
+   745	
.oracle/checkins/batch-1-r6.md:4105: trailing whitespace.
+   752	
.oracle/checkins/batch-1-r6.md:4106: trailing whitespace.
+   753	
.oracle/checkins/batch-1-r6.md:6718: trailing whitespace.
+   866	
.oracle/checkins/batch-1-r6.md:6725: trailing whitespace.
+   873	
.oracle/checkins/batch-1-r6.md:6728: trailing whitespace.
+   876	
.oracle/checkins/batch-1-r6.md:6742: trailing whitespace.
+   890	
.oracle/checkins/batch-1-r6.md:6743: trailing whitespace.
+   891	
.oracle/checkins/batch-1-r6.md:6747: trailing whitespace.
+   895	
.oracle/checkins/batch-1-r6.md:6755: trailing whitespace.
+   903	
.oracle/checkins/batch-1-r6.md:6786: trailing whitespace.
+   934	
.oracle/checkins/batch-1-r6.md:6799: trailing whitespace.
+   947	
.oracle/checkins/batch-1-r6.md:6830: trailing whitespace.
+   978	
.oracle/checkins/batch-1-r6.md:6837: trailing whitespace.
+   985	
.oracle/checkins/batch-1-r6.md:6838: trailing whitespace.
+   986	
.oracle/checkins/batch-1-r6.md:6842: trailing whitespace.
+   990	
.oracle/checkins/batch-1-r6.md:7871: trailing whitespace.
+   877	
.oracle/checkins/batch-1-r6.md:7872: trailing whitespace.
+   878	
.oracle/checkins/batch-1-r6.md:7878: trailing whitespace.
+   884	
.oracle/checkins/batch-1-r6.md:7879: trailing whitespace.
+   885	
.oracle/checkins/batch-1-r6.md:7890: trailing whitespace.
+   896	
.oracle/checkins/batch-1-r6.md:7891: trailing whitespace.
+   897	
.oracle/checkins/batch-1-r6.md:7907: trailing whitespace.
+   913	
.oracle/checkins/batch-1-r6.md:7908: trailing whitespace.
+   914	
.oracle/checkins/batch-1-r6.md:7913: trailing whitespace.
+   919	
.oracle/checkins/batch-1-r6.md:7914: trailing whitespace.
+   920	
.oracle/checkins/batch-1-r6.md:7936: trailing whitespace.
+   942	
.oracle/checkins/batch-1-r6.md:7937: trailing whitespace.
+   943	
.oracle/checkins/batch-1-r6.md:8244: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r6.md:8250: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r6.md:8253: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r6.md:8262: trailing whitespace.
+    20	
.oracle/checkins/batch-1-r6.md:8263: trailing whitespace.
+    21	
.oracle/checkins/batch-1-r6.md:8290: trailing whitespace.
+    48	
.oracle/checkins/batch-1-r6.md:8291: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r6.md:8294: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r6.md:8295: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r6.md:8298: trailing whitespace.
+    56	
.oracle/checkins/batch-1-r6.md:8299: trailing whitespace.
+    57	
.oracle/checkins/batch-1-r6.md:8302: trailing whitespace.
+    60	
.oracle/checkins/batch-1-r6.md:8303: trailing whitespace.
+    61	
.oracle/checkins/batch-1-r6.md:8314: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r6.md:8315: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r6.md:8323: trailing whitespace.
+    81	
.oracle/checkins/batch-1-r6.md:8330: trailing whitespace.
+    88	
.oracle/checkins/batch-1-r6.md:8331: trailing whitespace.
+    89	
.oracle/checkins/batch-1-r6.md:8338: trailing whitespace.
+    96	
.oracle/checkins/batch-1-r6.md:8339: trailing whitespace.
+    97	
.oracle/checkins/batch-1-r6.md:8347: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r6.md:8348: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r6.md:8355: trailing whitespace.
+   113	
.oracle/checkins/batch-1-r6.md:8356: trailing whitespace.
+   114	
.oracle/checkins/batch-1-r6.md:8364: trailing whitespace.
+   122	
.oracle/checkins/batch-1-r6.md:8365: trailing whitespace.
+   123	
.oracle/checkins/batch-1-r6.md:8373: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r6.md:8374: trailing whitespace.
+   132	
.oracle/checkins/batch-1-r6.md:8404: trailing whitespace.
+   162	
.oracle/checkins/batch-1-r6.md:8405: trailing whitespace.
+   163	
.oracle/checkins/batch-1-r6.md:8420: trailing whitespace.
+   178	
.oracle/checkins/batch-1-r6.md:8421: trailing whitespace.
+   179	
.oracle/checkins/batch-1-r6.md:8448: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r6.md:8449: trailing whitespace.
+   207	
.oracle/checkins/batch-1-r6.md:8491: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r6.md:8492: trailing whitespace.
+   250	
.oracle/checkins/batch-1-r6.md:8528: trailing whitespace.
+   286	
.oracle/checkins/batch-1-r6.md:8529: trailing whitespace.
+   287	
.oracle/checkins/batch-1-r6.md:8552: trailing whitespace.
+   310	
.oracle/checkins/batch-1-r6.md:8553: trailing whitespace.
+   311	
.oracle/checkins/batch-1-r6.md:8564: trailing whitespace.
+   322	
.oracle/checkins/batch-1-r6.md:8565: trailing whitespace.
+   323	
.oracle/checkins/batch-1-r6.md:8578: trailing whitespace.
+   336	
.oracle/checkins/batch-1-r6.md:8579: trailing whitespace.
+   337	
.oracle/checkins/batch-1-r6.md:8596: trailing whitespace.
+   354	
.oracle/checkins/batch-1-r6.md:8597: trailing whitespace.
+   355	
.oracle/checkins/batch-1-r6.md:8615: trailing whitespace.
+   373	
.oracle/checkins/batch-1-r6.md:8616: trailing whitespace.
+   374	
.oracle/checkins/batch-1-r6.md:8641: trailing whitespace.
+   800	
.oracle/checkins/batch-1-r6.md:8689: trailing whitespace.
+   848	
.oracle/checkins/batch-1-r6.md:8690: trailing whitespace.
+   849	
.oracle/checkins/batch-1-r6.md:8699: trailing whitespace.
+   858	
.oracle/checkins/batch-1-r6.md:8700: trailing whitespace.
+   859	
.oracle/checkins/batch-1-r6.md:8715: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:8781: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:8782: trailing whitespace.
+ 
.oracle/checkins/batch-1-r6.md:8910: trailing whitespace.
+   251	
.oracle/checkins/batch-1-r6.md:8914: trailing whitespace.
+   255	
.oracle/checkins/batch-1-r6.md:8916: trailing whitespace.
+   257	
.oracle/checkins/batch-1-r6.md:8921: trailing whitespace.
+   262	
.oracle/checkins/batch-1-r6.md:8933: trailing whitespace.
+   274	
.oracle/checkins/batch-1-r6.md:8935: trailing whitespace.
+   276	
.oracle/checkins/batch-1-r6.md:8939: trailing whitespace.
+   280	
.oracle/checkins/batch-1-r6.md:8949: trailing whitespace.
+   290	
.oracle/checkins/batch-1-r6.md:8951: trailing whitespace.
+   292	
.oracle/checkins/batch-1-r6.md:8957: trailing whitespace.
+   298	
.oracle/checkins/batch-1-r6.md:8959: trailing whitespace.
+   300	
.oracle/checkins/batch-1-r6.md:8971: trailing whitespace.
+   351	
.oracle/checkins/batch-1-r6.md:8979: trailing whitespace.
+   359	
.oracle/checkins/batch-1-r6.md:8991: trailing whitespace.
+   371	
.oracle/checkins/batch-1-r6.md:9003: trailing whitespace.
+   383	
.oracle/checkins/batch-1-r6.md:9007: trailing whitespace.
+   387	
.oracle/checkins/batch-1-r6.md:9009: trailing whitespace.
+   389	
.oracle/checkins/batch-1-r6.md:9018: trailing whitespace.
+   398	
.oracle/checkins/batch-1-r6.md:9028: trailing whitespace.
+   408	
.oracle/checkins/batch-1-r6.md:9030: trailing whitespace.
+   410	
.oracle/checkins/batch-1-r6.md:9061: trailing whitespace.
+  1250	
.oracle/checkins/batch-1-r6.md:9074: trailing whitespace.
+  1263	
.oracle/checkins/batch-1-r6.md:9097: trailing whitespace.
+  1286	
.oracle/checkins/batch-1-r6.md:9098: trailing whitespace.
+  1287	
.oracle/checkins/batch-1-r6.md:9103: trailing whitespace.
+  1292	
.oracle/checkins/batch-1-r6.md:9104: trailing whitespace.
+  1293	
.oracle/checkins/batch-1-r6.md:9108: trailing whitespace.
+  1297	
.oracle/checkins/batch-1-r6.md:9112: trailing whitespace.
+  1301	
.oracle/checkins/batch-1-r6.md:9126: trailing whitespace.
+  1315	
.oracle/checkins/batch-1-r6.md:9130: trailing whitespace.
+  1319	
.oracle/checkins/batch-1-r6.md:9132: trailing whitespace.
+  1321	
.oracle/checkins/batch-1-r6.md:9136: trailing whitespace.
+  1325	
.oracle/checkins/batch-1-r6.md:9138: trailing whitespace.
+  1327	
.oracle/checkins/batch-1-r6.md:9147: trailing whitespace.
+  1336	
.oracle/checkins/batch-1-r6.md:9158: trailing whitespace.
+  1347	
.oracle/checkins/batch-1-r6.md:9159: trailing whitespace.
+  1348	
.oracle/checkins/batch-1-r6.md:9163: trailing whitespace.
+  1352	
.oracle/checkins/batch-1-r6.md:9174: trailing whitespace.
+  1363	
.oracle/checkins/batch-1-r6.md:9240: trailing whitespace.
+  1458	
.oracle/checkins/batch-1-r6.md:9275: trailing whitespace.
+  1493	
.oracle/checkins/batch-1-r6.md:9282: trailing whitespace.
+  1500	
.oracle/checkins/batch-1-r6.md:9283: trailing whitespace.
+  1501	
.oracle/checkins/batch-1-r6.md:9298: trailing whitespace.
+  1516	
.oracle/checkins/batch-1-r6.md:9299: trailing whitespace.
+  1517	
.oracle/checkins/batch-1-r6.md:9303: trailing whitespace.
+  1521	
.oracle/checkins/batch-1-r6.md:9311: trailing whitespace.
+  1529	
.oracle/checkins/batch-1-r6.md:9337: trailing whitespace.
+  1555	
.oracle/checkins/batch-1-r6.md:9341: trailing whitespace.
+  1559	
.oracle/checkins/batch-1-r6.md:9343: trailing whitespace.
+  1561	
.oracle/checkins/batch-1-r6.md:9356: trailing whitespace.
+  1574	
.oracle/checkins/batch-1-r6.md:9380: trailing whitespace.
+  1598	
.oracle/checkins/batch-1-r6.md:10150: trailing whitespace.
+    84	
.oracle/checkins/batch-1-r6.md:10151: trailing whitespace.
+    85	
.oracle/checkins/batch-1-r6.md:10197: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r6.md:10198: trailing whitespace.
+   132	
.oracle/checkins/batch-1-r6.md:10255: trailing whitespace.
+   189	
.oracle/checkins/batch-1-r6.md:10256: trailing whitespace.
+   190	
.oracle/checkins/batch-1-r6.md:10267: trailing whitespace.
+   201	
.oracle/checkins/batch-1-r6.md:10268: trailing whitespace.
+   202	
.oracle/checkins/batch-1-r6.md:10396: trailing whitespace.
+  1605	
.oracle/checkins/batch-1-r6.md:10397: trailing whitespace.
+  1606	
.oracle/checkins/batch-1-r6.md:10401: trailing whitespace.
+  1610	
.oracle/checkins/batch-1-r6.md:10408: trailing whitespace.
+  1617	
.oracle/checkins/batch-1-r6.md:10420: trailing whitespace.
+  1629	
.oracle/checkins/batch-1-r6.md:10439: trailing whitespace.
+  1648	
.oracle/checkins/batch-1-r6.md:10451: trailing whitespace.
+  1660	
.oracle/checkins/batch-1-r6.md:10475: trailing whitespace.
+  1684	
.oracle/checkins/batch-1-r6.md:10482: trailing whitespace.
+  1691	
.oracle/checkins/batch-1-r6.md:10483: trailing whitespace.
+  1692	
.oracle/checkins/batch-1-r6.md:10487: trailing whitespace.
+  1696	
.oracle/checkins/batch-1-r6.md:10494: trailing whitespace.
+  1703	
.oracle/checkins/batch-1-r6.md:10542: trailing whitespace.
+  1751	
.oracle/checkins/batch-1-r6.md:10546: trailing whitespace.
+  1755	
.oracle/checkins/batch-1-r6.md:10577: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r6.md:10579: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r6.md:10581: trailing whitespace.
+     6	
.oracle/checkins/batch-1-r6.md:10583: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r6.md:10592: trailing whitespace.
+    17	
.oracle/checkins/batch-1-r6.md:10594: trailing whitespace.
+    19	
.oracle/checkins/batch-1-r6.md:10600: trailing whitespace.
+    25	
.oracle/checkins/batch-1-r6.md:10602: trailing whitespace.
+    27	
.oracle/checkins/batch-1-r6.md:10604: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r6.md:10606: trailing whitespace.
+    31	
.oracle/checkins/batch-1-r6.md:10615: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r6.md:10617: trailing whitespace.
+    42	
.oracle/checkins/batch-1-r6.md:10628: trailing whitespace.
+   550	
.oracle/checkins/batch-1-r6.md:10629: trailing whitespace.
+   551	
.oracle/checkins/batch-1-r6.md:10659: trailing whitespace.
+   800	
.oracle/checkins/batch-1-r6.md:10707: trailing whitespace.
+   848	
.oracle/checkins/batch-1-r6.md:10708: trailing whitespace.
+   849	

exec
/bin/zsh -lc 'git diff --stat 086d692..ab486f9; git diff --name-status 086d692..ab486f9; wc -l /tmp/batch1-r7.diff; shasum -a 256 /tmp/batch1-r7.diff' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r6.md                 | 10833 +++++++++++++++++++++++
 astrid/core/rendering/provenance.py            |    58 +-
 astrid/core/rendering/schemas/v1/finalize.json |     5 +-
 astrid/core/rendering/schemas/v1/plan.json     |     3 +
 astrid/core/rendering/schemas/v1/result.json   |     2 +-
 docs/contracts/render-backend-v1.md            |    18 +-
 tests/core/rendering/test_contracts.py         |    83 +-
 7 files changed, 10968 insertions(+), 34 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-1-r6.md
M	astrid/core/rendering/provenance.py
M	astrid/core/rendering/schemas/v1/finalize.json
M	astrid/core/rendering/schemas/v1/plan.json
M	astrid/core/rendering/schemas/v1/result.json
M	docs/contracts/render-backend-v1.md
M	tests/core/rendering/test_contracts.py
   11143 /tmp/batch1-r7.diff
f0b76681acfbebd438dd8ec1577b087b5fbd52312e8644962f01628d133a09b3  /tmp/batch1-r7.diff

codex
The commit and parent match the checkpoint. The only noisy addition is the prior review transcript; I’m excluding that from semantic review and concentrating on the six implementation/docs/test files, while still checking the commit as a whole for unintended effects.
exec
/bin/zsh -lc 'git diff --find-renames --find-copies --unified=100 086d692..ab486f9 -- astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/plan.json astrid/core/rendering/schemas/v1/result.json docs/contracts/render-backend-v1.md tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 03786c3..6881c6a 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -8,271 +8,285 @@ from typing import Any
 
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
 
 
 def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
     if value is None:
         value = {}
     if isinstance(value, Mapping):
         result: dict[str, Any] = {}
         for key, profile in value.items():
             path = _require_string(str(key), "artifact key")
             if isinstance(profile, VideoArtifact):
                 if path != profile.path:
                     raise ValueError(
                         f"artifact_profiles key {path!r} must equal VideoArtifact.path "
                         f"{profile.path!r}"
                     )
                 result[path] = _artifact_lineage(profile)
             elif isinstance(profile, Mapping):
                 result[path] = _artifact_lineage_from_mapping(profile, key=path)
             else:
                 raise TypeError(
                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                     "hashed lineage record {profile, sha256, attachments}; "
                     "profile-only entries carry no output hash"
                 )
-        # A positive plan must record a hashed artifact for every segment.
-        if segments and not result:
-            raise ValueError(
-                "artifact_profiles must record a hashed lineage entry for every "
-                "segment of a positive render plan"
-            )
+        # A positive plan must record exactly one hashed artifact per segment.
+        if segments:
+            if len(result) != len(segments):
+                raise ValueError(
+                    f"artifact_profiles must record exactly one hashed lineage entry "
+                    f"per segment: expected {len(segments)}, got {len(result)}"
+                )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
-        lineage = [
-            (
-                _artifact_lineage(profile)
-                if isinstance(profile, VideoArtifact)
-                else _artifact_lineage_from_mapping(profile, key=str(profile.get("path", "")))
-            )
-            for profile in value
-        ]
-        if segments and not lineage:
-            raise ValueError(
-                "artifact_profiles must record a hashed lineage entry for every "
-                "segment of a positive render plan"
-            )
+        lineage: dict[str, Any] = {}
+        for profile in value:
+            if not isinstance(profile, VideoArtifact):
+                raise TypeError(
+                    "sequence artifact_profiles entries must be VideoArtifacts "
+                    "so lineage records stay path-keyed"
+                )
+            lineage[profile.path] = _artifact_lineage(profile)
+        if segments:
+            if len(lineage) != len(segments):
+                raise ValueError(
+                    f"artifact_profiles must record exactly one hashed lineage entry "
+                    f"per segment: expected {len(segments)}, got {len(lineage)}"
+                )
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
+            if att.name != name:
+                raise ValueError(
+                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
+                )
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
+        # Validate through the Attachment DTO so workspace-path containment and
+        # kind grammar are enforced uniformly for raw and dataclass values.
+        validated = Attachment(
+            name=name,
+            path=att["path"],
+            kind=att["kind"],
+            sha256=att["sha256"],
+        )
         attachments[name] = {
-            "path": _require_string(att["path"], f"attachment {name!r} path"),
-            "kind": _require_string(att["kind"], f"attachment {name!r} kind"),
-            "sha256": _require_sha256(att["sha256"], f"attachment {name!r} sha256"),
+            "path": validated.path,
+            "kind": validated.kind,
+            "sha256": validated.sha256,
         }
     return {
         "profile": (
             profile
             if isinstance(profile, RenderProfile)
             else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
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
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 8319f7b..1e49ad3 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -1,168 +1,168 @@
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
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
@@ -227,200 +227,203 @@
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
               "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
               "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
             "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
             "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index feb4bc2..47740f8 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -259,200 +259,203 @@
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
               "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
               "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
             "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
             "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index 577adb3..e089030 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -1,125 +1,125 @@
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
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 47f9307..dc24a65 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -378,207 +378,211 @@ segment use the canonical profile's exact rational FPS (equivalent but
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
-are REQUIRED in `artifact_profiles` for any positive render plan as hashed
-lineage records: each maps an output path to exactly `{profile, sha256,
-attachments}` with a validated 64-hex string `sha256` on the artifact and
-every attachment `{path, kind, sha256}` (profile-only entries, null/malformed
-hashes, unknown fields, and missing fields are rejected; mapping keys must
-equal the artifact's own path), so replay can verify rendered outputs
-byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
+are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
+hashed lineage record PER SEGMENT, each mapping a unique output path to
+exactly `{profile, sha256, attachments}` with a validated 64-hex string
+`sha256` on the artifact and every attachment `{path, kind, sha256}`.
+Attachment paths must be workspace-relative, kinds must match
+`[a-z][a-z0-9-]*`, and attachment map keys must equal the attachment's own
+name. Profile-only entries, null/malformed hashes, unknown or missing fields,
+path escapes, invalid kinds, and cardinality mismatches are all rejected.
+Sequence-form lineage requires VideoArtifacts so records stay path-keyed.
+Replay can verify rendered outputs byte-for-byte. `input_hashes` describe
+inputs only, never rendered outputs.
 
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
index 69b4791..69d4327 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -472,476 +472,553 @@ def test_finalize_rejects_attachment_name_collisions_across_segments() -> None:
             plan=plan,
             artifacts=[
                 _video(path="segments/0.mp4", duration_frames=24, attachments={attachment.name: attachment}),
                 _video(path="segments/1.mp4", duration_frames=24, attachments={attachment.name: attachment}),
             ],
         )
 
 
 def test_finalize_rejects_dropped_or_changed_attachments() -> None:
     attachment = _attachment("project.blend")
     request = _finalize(artifacts=[_video(attachments={attachment.name: attachment})])
     with pytest.raises(ValueError, match="dropped attachments"):
         request.validate_final_result(_result())
 
     changed = _attachment("project.blend", sha256=SHA_C)
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
         "artifact_profiles": {
             "outputs/video.mp4": {
                 "profile": _profile(),
                 "sha256": SHA_B,
                 "attachments": {},
-            }
+            },
+            "outputs/segment2.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_C,
+                "attachments": {},
+            },
         },
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
         artifact_profiles={
             "outputs/visual.mp4": {
                 "profile": _profile(),
                 "sha256": SHA_B,
                 "attachments": {},
+            },
+            "outputs/segment2.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_C,
+                "attachments": {},
             }
         },
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
-        plan=_plan(),
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     with pytest.raises(TypeError, match="hashed lineage"):
-        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
+        assemble_provenance_v2(
+            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
+        )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
+            plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
             },
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
+            plan=_plan(),
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
+            plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {},
                     "spoof": 1,
                 }
             },
         )
+    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {},
+                }
+            },
+        )
+    with pytest.raises(ValueError, match="attachment path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+    with pytest.raises(ValueError, match="attachment kind"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+
+
+    with pytest.raises(ValueError, match="must equal Attachment.name"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "different_key": Attachment(
+                            name="alpha",
+                            path="outputs/alpha.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
+                    },
+                }
+            },
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

exec
/bin/zsh -lc "git diff --unified=25 086d692..ab486f9 -- 'astrid/core/rendering/provenance.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 03786c3..6881c6a 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -83,121 +83,135 @@ def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
     }
 
 
 def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
     if value is None:
         value = {}
     if isinstance(value, Mapping):
         result: dict[str, Any] = {}
         for key, profile in value.items():
             path = _require_string(str(key), "artifact key")
             if isinstance(profile, VideoArtifact):
                 if path != profile.path:
                     raise ValueError(
                         f"artifact_profiles key {path!r} must equal VideoArtifact.path "
                         f"{profile.path!r}"
                     )
                 result[path] = _artifact_lineage(profile)
             elif isinstance(profile, Mapping):
                 result[path] = _artifact_lineage_from_mapping(profile, key=path)
             else:
                 raise TypeError(
                     f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
                     "hashed lineage record {profile, sha256, attachments}; "
                     "profile-only entries carry no output hash"
                 )
-        # A positive plan must record a hashed artifact for every segment.
-        if segments and not result:
-            raise ValueError(
-                "artifact_profiles must record a hashed lineage entry for every "
-                "segment of a positive render plan"
-            )
+        # A positive plan must record exactly one hashed artifact per segment.
+        if segments:
+            if len(result) != len(segments):
+                raise ValueError(
+                    f"artifact_profiles must record exactly one hashed lineage entry "
+                    f"per segment: expected {len(segments)}, got {len(result)}"
+                )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
-        lineage = [
-            (
-                _artifact_lineage(profile)
-                if isinstance(profile, VideoArtifact)
-                else _artifact_lineage_from_mapping(profile, key=str(profile.get("path", "")))
-            )
-            for profile in value
-        ]
-        if segments and not lineage:
-            raise ValueError(
-                "artifact_profiles must record a hashed lineage entry for every "
-                "segment of a positive render plan"
-            )
+        lineage: dict[str, Any] = {}
+        for profile in value:
+            if not isinstance(profile, VideoArtifact):
+                raise TypeError(
+                    "sequence artifact_profiles entries must be VideoArtifacts "
+                    "so lineage records stay path-keyed"
+                )
+            lineage[profile.path] = _artifact_lineage(profile)
+        if segments:
+            if len(lineage) != len(segments):
+                raise ValueError(
+                    f"artifact_profiles must record exactly one hashed lineage entry "
+                    f"per segment: expected {len(segments)}, got {len(lineage)}"
+                )
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
+            if att.name != name:
+                raise ValueError(
+                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
+                )
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
+        # Validate through the Attachment DTO so workspace-path containment and
+        # kind grammar are enforced uniformly for raw and dataclass values.
+        validated = Attachment(
+            name=name,
+            path=att["path"],
+            kind=att["kind"],
+            sha256=att["sha256"],
+        )
         attachments[name] = {
-            "path": _require_string(att["path"], f"attachment {name!r} path"),
-            "kind": _require_string(att["kind"], f"attachment {name!r} kind"),
-            "sha256": _require_sha256(att["sha256"], f"attachment {name!r} sha256"),
+            "path": validated.path,
+            "kind": validated.kind,
+            "sha256": validated.sha256,
         }
     return {
         "profile": (
             profile
             if isinstance(profile, RenderProfile)
             else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
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

exec
/bin/zsh -lc "git diff --unified=25 086d692..ab486f9 -- 'astrid/core/rendering/schemas/v1/finalize.json'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "git diff --unified=25 086d692..ab486f9 -- 'astrid/core/rendering/schemas/v1/plan.json'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index 8319f7b..1e49ad3 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -43,51 +43,51 @@
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
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
@@ -302,50 +302,53 @@
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
             "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,

 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index feb4bc2..47740f8 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -334,50 +334,53 @@
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
             "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
+          },
+          "propertyNames": {
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,

exec
/bin/zsh -lc "git diff --unified=25 086d692..ab486f9 -- 'astrid/core/rendering/schemas/v1/result.json'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index 577adb3..e089030 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -1,50 +1,50 @@
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
-      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?!.*?/\\.{1,2}(?:/|$))(?!.*//)(?!.*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
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

exec
/bin/zsh -lc "git diff --unified=25 086d692..ab486f9 -- 'docs/contracts/render-backend-v1.md'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 47f9307..dc24a65 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -453,57 +453,61 @@ The host lifecycle is:
 
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
-are REQUIRED in `artifact_profiles` for any positive render plan as hashed
-lineage records: each maps an output path to exactly `{profile, sha256,
-attachments}` with a validated 64-hex string `sha256` on the artifact and
-every attachment `{path, kind, sha256}` (profile-only entries, null/malformed
-hashes, unknown fields, and missing fields are rejected; mapping keys must
-equal the artifact's own path), so replay can verify rendered outputs
-byte-for-byte. `input_hashes` describe inputs only, never rendered outputs.
+are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
+hashed lineage record PER SEGMENT, each mapping a unique output path to
+exactly `{profile, sha256, attachments}` with a validated 64-hex string
+`sha256` on the artifact and every attachment `{path, kind, sha256}`.
+Attachment paths must be workspace-relative, kinds must match
+`[a-z][a-z0-9-]*`, and attachment map keys must equal the attachment's own
+name. Profile-only entries, null/malformed hashes, unknown or missing fields,
+path escapes, invalid kinds, and cardinality mismatches are all rejected.
+Sequence-form lineage requires VideoArtifacts so records stay path-keyed.
+Replay can verify rendered outputs byte-for-byte. `input_hashes` describe
+inputs only, never rendered outputs.
 
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

exec
/bin/zsh -lc "git diff --unified=25 086d692..ab486f9 -- 'tests/core/rendering/test_contracts.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 69b4791..69d4327 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -547,51 +547,56 @@ def test_provenance_requires_always_emitted_v1_projection() -> None:
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
         "artifact_profiles": {
             "outputs/video.mp4": {
                 "profile": _profile(),
                 "sha256": SHA_B,
                 "attachments": {},
-            }
+            },
+            "outputs/segment2.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_C,
+                "attachments": {},
+            },
         },
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
@@ -672,50 +677,55 @@ def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
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
         artifact_profiles={
             "outputs/visual.mp4": {
                 "profile": _profile(),
                 "sha256": SHA_B,
                 "attachments": {},
+            },
+            "outputs/segment2.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_C,
+                "attachments": {},
             }
         },
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
@@ -784,89 +794,156 @@ def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
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
-        plan=_plan(),
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     with pytest.raises(TypeError, match="hashed lineage"):
-        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
+        assemble_provenance_v2(
+            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
+        )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
+            plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
             },
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
+            plan=_plan(),
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
+            plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {},
                     "spoof": 1,
                 }
             },
         )
+    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {},
+                }
+            },
+        )
+    with pytest.raises(ValueError, match="attachment path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+    with pytest.raises(ValueError, match="attachment kind"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+
+
+    with pytest.raises(ValueError, match="must equal Attachment.name"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "different_key": Attachment(
+                            name="alpha",
+                            path="outputs/alpha.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
+                    },
+                }
+            },
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

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '700,900p'; nl -ba astrid/core/rendering/provenance.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   108	        # A positive plan must record exactly one hashed artifact per segment.
   109	        if segments:
   110	            if len(result) != len(segments):
   111	                raise ValueError(
   112	                    f"artifact_profiles must record exactly one hashed lineage entry "
   113	                    f"per segment: expected {len(segments)}, got {len(result)}"
   114	                )
   115	        return result
   116	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   117	        lineage: dict[str, Any] = {}
   118	        for profile in value:
   119	            if not isinstance(profile, VideoArtifact):
   120	                raise TypeError(
   121	                    "sequence artifact_profiles entries must be VideoArtifacts "
   122	                    "so lineage records stay path-keyed"
   123	                )
   124	            lineage[profile.path] = _artifact_lineage(profile)
   125	        if segments:
   126	            if len(lineage) != len(segments):
   127	                raise ValueError(
   128	                    f"artifact_profiles must record exactly one hashed lineage entry "
   129	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   130	                )
   131	        return lineage
   132	    raise TypeError("artifact_profiles must be an object or array")
   133	
   134	
   135	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   136	    raw_keys = set(raw)
   137	    allowed = {"profile", "sha256", "attachments"}
   138	    unknown = sorted(raw_keys - allowed)
   139	    if unknown:
   140	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   141	    missing = sorted(allowed - raw_keys)
   142	    if missing:
   143	        raise ValueError(
   144	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   145	        )
   146	    if raw["sha256"] is None:
   147	        raise ValueError("artifact lineage sha256 is required and must not be null")
   148	    if not isinstance(raw["sha256"], str):
   149	        raise TypeError("artifact lineage sha256 must be a string")
   150	    profile = raw["profile"]
   151	    attachments: dict[str, Any] = {}
   152	    raw_attachments = raw["attachments"]
   153	    if raw_attachments is None:
   154	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   155	    if not isinstance(raw_attachments, Mapping):
   156	        raise TypeError("artifact lineage attachments must be an object")
   157	    for name, att in raw_attachments.items():
   158	        name = _require_string(name, "attachment name")
   159	        if isinstance(att, Attachment):
   160	            if att.name != name:
   161	                raise ValueError(
   162	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   163	                )
   164	            att = {
   165	                "path": att.path,
   166	                "kind": att.kind,
   167	                "sha256": att.sha256,
   168	            }
   169	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   170	        if att_unknown:
   171	            raise ValueError(
   172	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   173	            )
   174	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   175	        if att_missing:
   176	            raise ValueError(
   177	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   178	            )
   179	        if not isinstance(att["sha256"], str):
   180	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   181	        # Validate through the Attachment DTO so workspace-path containment and
   182	        # kind grammar are enforced uniformly for raw and dataclass values.
   183	        validated = Attachment(
   184	            name=name,
   185	            path=att["path"],
   186	            kind=att["kind"],
   187	            sha256=att["sha256"],
   188	        )
   189	        attachments[name] = {
   190	            "path": validated.path,
   191	            "kind": validated.kind,
   192	            "sha256": validated.sha256,
   193	        }
   194	    return {
   195	        "profile": (
   196	            profile
   197	            if isinstance(profile, RenderProfile)
   198	            else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
   199	        ).to_dict(),
   200	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   201	        "attachments": attachments,
   202	    }
   203	
   204	
   205	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   206	    """One hashed artifact lineage record: profile, sha256, attachments."""
   207	    return _artifact_lineage_from_mapping(
   208	        {
   209	            "profile": artifact.profile,
   210	            "sha256": artifact.sha256,
   211	            "attachments": artifact.attachments,
   212	        },
   213	        key=artifact.path,
   214	    )
   215	
   216	
   217	def _normalize_v1_compatibility(
   218	    fields: Mapping[str, Any] | None,
   219	) -> dict[str, Any]:
   220	    if fields is None:
   221	        raise ValueError(
   222	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   223	        )
   224	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   225	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   226	    if unknown:
   227	        raise ValueError(
   228	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   229	            + ", ".join(unknown)
   230	        )
   231	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   232	    if missing:
   233	        raise ValueError(
   234	            "v1 compatibility projection is missing always-emitted fields: "
   235	            + ", ".join(missing)
   236	        )
   237	    return compatibility
   238	
   239	
   240	def assemble_provenance_v2(
   241	    *,
   242	    engine: str,
   243	    output: str | Path,
   244	    timeline: str | Path,
   245	    assets_registry: str | Path | None,
   246	    plan: RenderPlan | Mapping[str, Any],
   247	    artifact_profiles: Any = None,
   248	    audio_ownership: AudioOwnership | str | None = None,
   249	    normalization: Sequence[str] = (),
   250	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   251	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   252	    v1_compatibility: Mapping[str, Any] | None = None,
   253	) -> dict[str, Any]:
   254	    """Assemble additive provenance v2 with protected ownership boundaries.
   255	
   256	    ``engine`` is intentionally the legacy request projection. Routing and
   257	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   258	    hybrid invocation cannot collapse multiple renderer identities. Optional
   259	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   260	    any v2 core field.
   261	    """
   262	
   263	    legacy_engine = _require_string(engine, "engine")
   264	    output_path = _require_string(str(output), "output")
   265	    timeline_path = _require_string(str(timeline), "timeline")
   266	    assets_path = None if assets_registry is None else _require_string(
   267	        str(assets_registry), "assets_registry"
   268	    )
   269	    normalized_plan = (
   270	        plan
   271	        if isinstance(plan, RenderPlan)
   272	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   273	    )
   274	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   275	    legacy_segments = [
   276	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   277	    ]
   278	    normalized_normalization = [
   279	        _require_string(item, f"normalization[{index}]")
   280	        for index, item in enumerate(normalization)
   281	    ]
   282	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   283	
   284	    payload: dict[str, Any] = {
   285	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   286	        "engine": legacy_engine,
   287	        "output": output_path,
   288	        "timeline": timeline_path,
   289	        "assets_registry": assets_path,
   290	        "request_digest": normalized_plan.request_digest,
   291	        "requested_policy": normalized_plan.requested_policy,
   292	        "planner": normalized_plan.planner.to_dict(),
   293	        # V1-compatible segment projection: flat {engine, from, to} entries,
   294	        # exactly the shape legacy consumers read from `segments`.
   295	        "segments": legacy_segments,
   296	        # Additive normalized v2 segment records; never overwrite v1 fields.
   297	        "segments_v2": normalized_segments,
   298	        "artifact_profiles": _normalize_artifact_profiles(
   299	            artifact_profiles,
   300	            segments=normalized_plan.segments,
   301	        ),
   302	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   303	        "normalization": normalized_normalization,
   304	        "finalizer": normalized_plan.finalizer.to_dict(),
   305	        "attachments": _normalize_attachments(attachments),
   306	        "backend_fragments": validate_backend_fragments(backend_fragments),
   307	    }
   308	    payload.update(compatibility)
   309	    return _json_safe_mapping(payload, label="provenance")
   310	
   311	
   312	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   313	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   314	
   315	    return assemble_provenance_v2(**kwargs)
   316	
   317	
   318	def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
   319	    """Assemble and atomically write a provenance v2 sidecar."""
   320	
   321	    payload = assemble_provenance_v2(**kwargs)
   322	    write_json_atomic(path, payload)
   323	    return payload
   324	
   325	
   326	def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
   327	    """Return stable SHA-256 input hashes using Astrid's shared helper."""
   328	
   329	    return {
   330	        _require_string(name, "input hash name"): sha256_file(Path(path))

exec
/bin/zsh -lc "rg -n \"Artifact lineage unbound|Attachment lineage bypasses|Schema/DTO parity|artifact.*lineage|workspacePath|propertyNames|Verdict|PASS\" .oracle/checkins/batch-1-r6.md | tail -n 120; if [ -f .oracle/checkins/batch-1-r7.md ]; then sed -n '1,240p' .oracle/checkins/batch-1-r7.md; fi" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
7852:/bin/zsh -lc "rg -n \"schema.*DTO|DTO.*schema|parity|workspacePath|NUL|multiline|propertyNames|feature key|hashMap|schema_valid|Draft7Validator|validate\\(\" tests/core/rendering/test_contracts.py | sed -n '1,280p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '860,1160p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
7955:/bin/zsh -lc "rg -n \"workspacePath|schema.*DTO|DTO.*schema|parity|NUL|multiline|propertyNames|hashMap|Draft7Validator|jsonschema\" tests/core/rendering tests | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8625:diff -u <(jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/result.json) <(jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/finalize.json) || true" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
8635:support feature {'type': 'object', 'additionalProperties': {'type': ['boolean', 'string']}, 'propertyNames': {'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}
8642:   801	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
8741:@@ -805,26 +811,46 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
8792:/bin/zsh -lc "rg -n \"positive render plan|must equal VideoArtifact.path|artifact lineage.*attachments|missing required fields|attachment.*unknown|Attachment\\(\" tests/core/rendering | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
9407:.oracle/checkins/batch-1-r6.md:1394:.oracle/checkins/batch-1-r5.md:35:   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
9408:.oracle/checkins/batch-1-r6.md:1420:.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9409:.oracle/checkins/batch-1-r6.md:1422:.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9410:.oracle/checkins/batch-1-r6.md:1424:.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9411:.oracle/checkins/batch-1-r6.md:1425:.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9412:.oracle/checkins/batch-1-r6.md:1433:.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9413:.oracle/checkins/batch-1-r6.md:1435:.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9414:.oracle/checkins/batch-1-r6.md:1438:.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9415:.oracle/checkins/batch-1-r6.md:1439:.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9416:.oracle/checkins/batch-1-r6.md:1441:.oracle/checkins/batch-1-r5.md:1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9417:.oracle/checkins/batch-1-r6.md:1442:.oracle/checkins/batch-1-r5.md:1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9424:.oracle/checkins/batch-1-r6.md:1769:   478	are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
9429:.oracle/checkins/batch-1-r6.md:1926:+                "artifact_profiles must record a hashed lineage entry for every "
9430:.oracle/checkins/batch-1-r6.md:1943:+                "artifact_profiles must record a hashed lineage entry for every "
9437:.oracle/checkins/batch-1-r6.md:2285:-are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
9452:.oracle/checkins/batch-1-r6.md:2875:   111	                "artifact_profiles must record a hashed lineage entry for every "
9453:.oracle/checkins/batch-1-r6.md:2890:   126	                "artifact_profiles must record a hashed lineage entry for every "
9477:.oracle/checkins/batch-1-r6.md:3428:./astrid/core/rendering/provenance.py:111:                "artifact_profiles must record a hashed lineage entry for every "
9478:.oracle/checkins/batch-1-r6.md:3429:./astrid/core/rendering/provenance.py:126:                "artifact_profiles must record a hashed lineage entry for every "
9505:.oracle/checkins/batch-1-r5.md:35:   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
9506:.oracle/checkins/batch-1-r5.md:916:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9507:.oracle/checkins/batch-1-r5.md:920:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9508:.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9509:.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9510:.oracle/checkins/batch-1-r5.md:1101:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9511:.oracle/checkins/batch-1-r5.md:1105:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9512:.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9513:.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9514:.oracle/checkins/batch-1-r5.md:1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9515:.oracle/checkins/batch-1-r5.md:1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9538:.oracle/checkins/batch-1-r5.md:5777:-are recorded in `artifact_profiles` as hashed lineage records: each maps an
9539:.oracle/checkins/batch-1-r5.md:5778:+are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
9548:.oracle/checkins/batch-1-r5.md:6087:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9549:.oracle/checkins/batch-1-r5.md:6103:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9552:.oracle/checkins/batch-1-r5.md:7318:./docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
9581:.oracle/checkins/batch-1-r5.md:16014:   478	are REQUIRED in `artifact_profiles` as hashed lineage records: each maps an
9659:.oracle/checkins/batch-1-r2.md:28671:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9660:.oracle/checkins/batch-1-r2.md:28686:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9662:.oracle/checkins/batch-1-r3.md:1753:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9663:.oracle/checkins/batch-1-r3.md:1768:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9672:.oracle/checkins/batch-1-r3.md:9384:astrid/core/rendering/schemas/v1/result.json	definitions.backendFragments.additionalProperties.propertyNames	{"not":{"enum":["schema_version","video","backend_fragments","audio_ownership","normalization","logs","metadata","engine","output","timeline","assets_registry","request_digest","requested_policy","planner","segments","artifact_profiles","finalizer","attachments","project_dir","composition_id","active_pack_order","active_theme","registry_hash","registry_state","resolved_effect_ids","resolved_effects","source_pack_ids","element_roots","staged_asset_ids","staged_asset_root","segment_provenance","ffmpeg_specialization","audio_reactive_colour","resolved_backend","source_pack","alias_chain","override","trust_eligibility","manifest_digest","support_decision","input_hashes","segments_v2"]}}
9681:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9682:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9700:.oracle/checkins/batch-1-r4.md:35:   - Hashed artifact lineage: `artifact_profiles` now emits per-output
9701:.oracle/checkins/batch-1-r4.md:15314:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9702:.oracle/checkins/batch-1-r4.md:15329:1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).
9703:.oracle/checkins/batch-1-r4.md:15415:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9704:.oracle/checkins/batch-1-r4.md:15440:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
9717:.oracle/checkins/batch-1-r4.md:18257:   476	are recorded in `artifact_profiles` as hashed lineage records: each maps an
9719:.oracle/checkins/batch-1-r4.md:18308:./docs/contracts/render-backend-v1.md:476:are recorded in `artifact_profiles` as hashed lineage records: each maps an
9728:/bin/zsh -lc "sed -n '1,120p' .oracle/checkins/batch-1-r6.md && sed -n '1,110p' .oracle/checkins/batch-1-r5.md && rg -n \"codex"'$|tokens used|Hashed artifact lineage remains optional" .oracle/checkins/batch-1-r5.md | tail -n 30' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
9756:1. **Hashed artifact lineage optional and unbound** →
9769:3. **Schema/DTO parity** →
9772:   - workspacePath accepts internal newlines (uses `[\s\S]*`), still rejects
9775:     `propertyNames`.
9785:## Verdict
9787:Binary: `PASS` or a list of issues. Batch 1 has now passed 6 review rounds.
9789:remaining nits are non-blocking or absent, say exactly `PASS`. If you find
9792:I’m using the Astrid repo skill for repository-specific rules and the Megado skill for the checkpoint contract. I’ll inspect the incremental diff and the affected implementation/tests read-only, then return only `PASS` or precise blocking issues.
9883:2. **Hashed artifact lineage optional/spoofable** →
9884:   - `_normalize_artifact_profiles` now REQUIRES hashed lineage: entries must
9888:   - `test_provenance_rejects_spoofed_artifact_lineage` (profile-only, null
9890:3. **Schema/DTO parity** →
9891:   - workspacePath accepts DTO-valid leading whitespace (`. *\S.*` tail),
9896:     gained nonblank/NUL `propertyNames` constraints.
9916:## Verdict
9918:Binary: `PASS` or a list of issues. Verify the four closures above; also scan
9919:the cumulative C1..HEAD diff (now ~57k lines) for anything new. If PASS, say
9920:exactly `PASS` — Batch 2 may then begin.
9962:1130:39120:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9963:1135:39136:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9965:6087:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9967:6103:2. **Hashed artifact lineage remains optional and spoofable.** `_normalize_artifact_profiles()` still accepts `None`, empty maps, profile-only maps, and profile arrays without hashes. Artifact-shaped mappings stringify rather than validate hashes and attachment fields—e.g. `sha256: null` becomes `"None"`—and do not enforce path or segment correspondence ([provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:85)). Existing tests still exercise empty and profile-only lineage ([test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:567)). This does not guarantee the documented per-output hashed lineage.
9970:16027:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
9972:16038:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
10022:referencing.exceptions.PointerToNowhere: '/definitions/workspacePath' does not exist within {'type': 'object', 'additionalProperties': False, 'required': ['path', 'profile', 'sha256', 'duration_frames'], 'properties': {'path': {'$ref': '#/definitions/workspacePath'}, 'profile': {'$ref': '#/definitions/renderProfile'}, 'sha256': {'$ref': '#/definitions/sha256'}, 'duration_frames': {'type': 'integer', 'minimum': 1}, 'audio': {'anyOf': [{'$ref': '#/definitions/audioOwnership'}, {'type': 'null'}]}, 'attachments': {'$ref': '#/definitions/attachments'}}, 'allOf': [{'if': {'properties': {'profile': {'required': ['audio_codec'], 'properties': {'audio_codec': {'type': 'string', 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}}}}, 'then': {'required': ['audio'], 'properties': {'audio': {'const': 'rendered'}}}, 'else': {'properties': {'audio': {'enum': ['passthrough', 'none', None]}}}}]}
10042:jsonschema.exceptions._WrappedReferencingError: PointerToNowhere: '/definitions/workspacePath' does not exist within {'type': 'object', 'additionalProperties': False, 'required': ['path', 'profile', 'sha256', 'duration_frames'], 'properties': {'path': {'$ref': '#/definitions/workspacePath'}, 'profile': {'$ref': '#/definitions/renderProfile'}, 'sha256': {'$ref': '#/definitions/sha256'}, 'duration_frames': {'type': 'integer', 'minimum': 1}, 'audio': {'anyOf': [{'$ref': '#/definitions/audioOwnership'}, {'type': 'null'}]}, 'attachments': {'$ref': '#/definitions/attachments'}}, 'allOf': [{'if': {'properties': {'profile': {'required': ['audio_codec'], 'properties': {'audio_codec': {'type': 'string', 'pattern': '^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$'}}}}}, 'then': {'required': ['audio'], 'properties': {'audio': {'const': 'rendered'}}}, 'else': {'properties': {'audio': {'enum': ['passthrough', 'none', None]}}}}]}
10129:    22	    "workspacePath": {
10142:    65	    "workspacePath": {
10165:    99	                result[path] = _artifact_lineage(profile)
10167:   101	                result[path] = _artifact_lineage_from_mapping(profile, key=path)
10177:   111	                "artifact_profiles must record a hashed lineage entry for every "
10184:   118	                _artifact_lineage(profile)
10186:   120	                else _artifact_lineage_from_mapping(profile, key=str(profile.get("path", "")))
10192:   126	                "artifact_profiles must record a hashed lineage entry for every "
10199:   133	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
10204:   138	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
10208:   142	            f"artifact lineage is missing required fields: {', '.join(missing)}"
10211:   145	        raise ValueError("artifact lineage sha256 is required and must not be null")
10213:   147	        raise TypeError("artifact lineage sha256 must be a string")
10218:   152	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
10220:   154	        raise TypeError("artifact lineage attachments must be an object")
10257:   191	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
10258:   192	    """One hashed artifact lineage record: profile, sha256, attachments."""
10259:   193	    return _artifact_lineage_from_mapping(
10564:/bin/zsh -lc "rg -n '\"workspacePath\"' astrid/core/rendering/schemas/v1/*.json && rg -n '\"supportReport\"' astrid/core/rendering/schemas/v1/*.json && rg -n '\"hashMap\"' astrid/core/rendering/schemas/v1/*.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
10566:astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
10567:astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
10580:     5	**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
10603:    28	**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
10660:   801	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
10722:086d692 batch1-rework6: oracle re-review5 issues 1-3 (lineage required+shape-bound+path-bound, NUL-after-newline, hashMap/feature propertyNames, workspacePath newlines)
10723:91f0fe3 batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
10724:808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
10751:                result[path] = _artifact_lineage(profile)
10792:def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
10793:    """One hashed artifact lineage record: profile, sha256, attachments."""
10820:3. **Schema/DTO parity remains false.**
10822:   - Embedded `supportReport.features` in plan/finalize still lacks `propertyNames`, so blank/NUL keys pass schema but fail DTO validation. [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:352) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:320)
10823:   - `workspacePath` enables newlines but retains `.*` in containment lookaheads. Thus `ok\nsub/../evil.mp4`, double slashes, and backslashes after a newline pass result/finalize schemas while the DTO rejects them. Use `[\s\S]*` in every full-string lookahead and add multiline traversal cases. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:65)
10830:3. **Schema/DTO parity remains false.**
10832:   - Embedded `supportReport.features` in plan/finalize still lacks `propertyNames`, so blank/NUL keys pass schema but fail DTO validation. [plan.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:352) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:320)
10833:   - `workspacePath` enables newlines but retains `.*` in containment lookaheads. Thus `ok\nsub/../evil.mp4`, double slashes, and backslashes after a newline pass result/finalize schemas while the DTO rejects them. Use `[\s\S]*` in every full-string lookahead and add multiline traversal cases. [result.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22) [finalize.json](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:65)
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

exec
/bin/zsh -lc "sed -n '10790,10838p' .oracle/checkins/batch-1-r6.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:


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

exec
/bin/zsh -lc "rg -n \"artifact_profiles|artifact lineage|VideoArtifact|per.segment|per segment|output path|path-keyed|lineage\" .oracle/tasklist.md .oracle/plan.md .oracle/briefs docs/contracts/render-backend-v1.md astrid tests/core/rendering -g '*.md' -g '*.py' -g '*.json' | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
docs/contracts/render-backend-v1.md:242:`VideoArtifact` with:
docs/contracts/render-backend-v1.md:271:match its non-null `VideoArtifact.audio`. Visual-only renderers are valid and
docs/contracts/render-backend-v1.md:282:`VideoArtifact.attachments` is the one authoritative attachment surface;
docs/contracts/render-backend-v1.md:385:with exactly one entry per segment. A renderer owns all pixels for its assigned
docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
docs/contracts/render-backend-v1.md:479:hashed lineage record PER SEGMENT, each mapping a unique output path to
docs/contracts/render-backend-v1.md:486:Sequence-form lineage requires VideoArtifacts so records stay path-keyed.
docs/contracts/render-backend-v1.md:491:V1-compatible flat projection: one `{engine, from, to}` entry per segment,
.oracle/tasklist.md:57:- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
.oracle/plan.md:84:    - primary `VideoArtifact`, named attachments, and `RenderResult`;
.oracle/plan.md:160:  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
tests/core/rendering/test_contracts.py:21:    VideoArtifact,
tests/core/rendering/test_contracts.py:179:) -> VideoArtifact:
tests/core/rendering/test_contracts.py:180:    return VideoArtifact(
tests/core/rendering/test_contracts.py:190:def _result(*, video: VideoArtifact | None = None) -> RenderResult:
tests/core/rendering/test_contracts.py:207:    artifacts: list[VideoArtifact] | None = None,
tests/core/rendering/test_contracts.py:375:    artifact = VideoArtifact.from_dict(
tests/core/rendering/test_contracts.py:552:def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
tests/core/rendering/test_contracts.py:697:        artifact_profiles={
tests/core/rendering/test_contracts.py:742:def test_provenance_emits_hashed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:745:    artifact = VideoArtifact(
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
.oracle/briefs/batch-1-t1.2.md:23:  `VideoArtifact`, `RenderResult`, `RendererError`, `BackendConfig`,
.oracle/briefs/batch-1-t1.2.md:35:  - `VideoArtifact`: `path` (contained in workspace), `profile: RenderProfile`,
.oracle/briefs/batch-1-t1.2.md:54:    per segment).
.oracle/briefs/batch-1-t1.2.md:57:  - `RenderResult`: `schema_version`, `video: VideoArtifact`,
.oracle/briefs/batch-1-t1.2.md:72:  `support_decision`, `input_hashes`, `segments`, `artifact_profiles`,
.oracle/briefs/batch-1-r1-t1.2.md:19:`RenderResult` has attachments separate from `VideoArtifact.attachments`,
.oracle/briefs/batch-1-r1-t1.2.md:20:but `FinalizeRequest` carries only `list[VideoArtifact]` — a standalone
.oracle/briefs/batch-1-r1-t1.2.md:25:`FinalizeRequest` carry complete per-segment result envelopes (segment
.oracle/briefs/batch-1-r1-t1.2.md:27:attachments onto `VideoArtifact`. Enforce GLOBAL attachment name uniqueness
.oracle/briefs/batch-1-r1-t1.2.md:32:## Issue 4 — Provenance cannot represent routing/replay lineage
.oracle/briefs/batch-1-r1-t1.2.md:36:cannot represent resolved identity per segment without collapsing evidence.
.oracle/briefs/14-dynamic-outputs.md:18:     output paths? (grep consumers of `result.outputs` /
.oracle/briefs/batch-1-r2-t1.2.md:50:## Issue 2 — Provenance regresses v1 and replay lineage incomplete
.oracle/briefs/batch-1-r2-t1.2.md:65:- Include artifact hashes (per-segment video/attachments) in provenance.
astrid/core/threads/prefix.py:1:"""User-facing non-binding lineage prefix formatting."""
astrid/core/threads/prefix.py:17:    label = decision.label.strip() or "Astrid lineage"
astrid/core/threads/prefix.py:19:    lines = [f"[lineage] {label} · {run_part} · {decision.thread_id}"]
astrid/core/threads/prefix.py:21:        message = variants_message or f"requested {variants}; record keepers only as non-binding lineage after reviewing outputs."
astrid/core/threads/variants.py:116:    return f"{count} unresolved variant {plural}; review outputs and record any keeper as non-binding lineage selection."
astrid/core/audit/cli.py:17:    parser.add_argument("--out", type=Path, help="HTML output path. Defaults to <run>/audit/report.html.")
astrid/core/threads/__init__.py:9:and its re-exports). The lineage modules (``ids``, ``index``, ``record``,
astrid/core/threads/attribute.py:52:    lineage_thread_id = None if explicit else infer_lineage_thread_id(repo_root, request)
astrid/core/threads/attribute.py:69:        if thread_id is None and lineage_thread_id and lineage_thread_id in index["threads"]:
astrid/core/threads/attribute.py:70:            thread_id = lineage_thread_id
astrid/core/threads/attribute.py:71:            source = "lineage"
astrid/core/threads/attribute.py:131:def infer_lineage_thread_id(repo_root: Path, request: Any) -> str | None:
astrid/core/rendering/provenance.py:21:    VideoArtifact,
astrid/core/rendering/provenance.py:86:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:93:            if isinstance(profile, VideoArtifact):
astrid/core/rendering/provenance.py:96:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:99:                result[path] = _artifact_lineage(profile)
astrid/core/rendering/provenance.py:101:                result[path] = _artifact_lineage_from_mapping(profile, key=path)
astrid/core/rendering/provenance.py:104:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:105:                    "hashed lineage record {profile, sha256, attachments}; "
astrid/core/rendering/provenance.py:108:        # A positive plan must record exactly one hashed artifact per segment.
astrid/core/rendering/provenance.py:112:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:113:                    f"per segment: expected {len(segments)}, got {len(result)}"
astrid/core/rendering/provenance.py:117:        lineage: dict[str, Any] = {}
astrid/core/rendering/provenance.py:119:            if not isinstance(profile, VideoArtifact):
astrid/core/rendering/provenance.py:121:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:122:                    "so lineage records stay path-keyed"
astrid/core/rendering/provenance.py:124:            lineage[profile.path] = _artifact_lineage(profile)
astrid/core/rendering/provenance.py:126:            if len(lineage) != len(segments):
astrid/core/rendering/provenance.py:128:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:129:                    f"per segment: expected {len(segments)}, got {len(lineage)}"
astrid/core/rendering/provenance.py:131:        return lineage
astrid/core/rendering/provenance.py:132:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:135:def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
astrid/core/rendering/provenance.py:140:        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
astrid/core/rendering/provenance.py:144:            f"artifact lineage is missing required fields: {', '.join(missing)}"
astrid/core/rendering/provenance.py:147:        raise ValueError("artifact lineage sha256 is required and must not be null")
astrid/core/rendering/provenance.py:149:        raise TypeError("artifact lineage sha256 must be a string")
astrid/core/rendering/provenance.py:154:        raise ValueError("artifact lineage attachments must be an object (may be empty)")
astrid/core/rendering/provenance.py:156:        raise TypeError("artifact lineage attachments must be an object")
astrid/core/rendering/provenance.py:205:def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
astrid/core/rendering/provenance.py:206:    """One hashed artifact lineage record: profile, sha256, attachments."""
astrid/core/rendering/provenance.py:207:    return _artifact_lineage_from_mapping(
astrid/core/rendering/provenance.py:247:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:257:    replay lineage come exclusively from the validated ``RenderPlan`` so a
astrid/core/rendering/provenance.py:298:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:299:            artifact_profiles,
astrid/core/rendering/contracts.py:65:        "artifact_profiles",
astrid/core/rendering/contracts.py:656:class VideoArtifact:
astrid/core/rendering/contracts.py:702:    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
astrid/core/rendering/contracts.py:726:    ) -> VideoArtifact:
astrid/core/rendering/contracts.py:1439:                "plan reasons must contain exactly one entry per segment, keyed by zero-based index"
astrid/core/rendering/contracts.py:1523:    video: VideoArtifact
astrid/core/rendering/contracts.py:1534:            if isinstance(self.video, VideoArtifact)
astrid/core/rendering/contracts.py:1535:            else VideoArtifact.from_dict(_require_mapping(self.video, "video"))
astrid/core/rendering/contracts.py:1589:                video=VideoArtifact.from_dict(data["video"]),
astrid/core/rendering/contracts.py:1699:    artifacts: list[VideoArtifact]
astrid/core/rendering/contracts.py:1715:            if isinstance(artifact, VideoArtifact)
astrid/core/rendering/contracts.py:1716:            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
astrid/core/rendering/contracts.py:1823:                artifacts=[VideoArtifact.from_dict(item) for item in data["artifacts"]],
astrid/core/rendering/contracts.py:2193:    "VideoArtifact",
astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
astrid/core/rendering/schemas/v1/plan.json:5:  "description": "Versioned routing lineage and deterministic half-open temporal coverage.",
astrid/core/rendering/__init__.py:14:    VideoArtifact,
astrid/core/rendering/__init__.py:24:    "VideoArtifact",
astrid/core/integrations/arnold/session/driver.py:337:        event_lineage=EventLineageHashes(
astrid/core/integrations/arnold/session/driver.py:338:            segment_start_hash=from_segment.event_lineage.segment_boundary_hash
astrid/core/integrations/arnold/session/driver.py:339:            or from_segment.event_lineage.segment_start_hash,
astrid/core/integrations/arnold/session/driver.py:365:        event_lineage=segment.event_lineage,
astrid/core/integrations/arnold/session/driver.py:393:                event_lineage=EventLineageHashes(
astrid/core/integrations/arnold/session/driver.py:394:                    segment_start_hash=segment.event_lineage.segment_start_hash,
astrid/core/generation/backends/base.py:95:        When generating video the output paths still live in ``image_paths``
astrid/core/generation/backends/base.py:278:            A :class:`GenerationResult` with output paths, metadata, and
astrid/core/integrations/arnold/session/cli.py:112:                        event_lineage=EventLineageHashes(
astrid/core/integrations/arnold/session/render.py:30:    segment_lineage: tuple[str, ...]
astrid/core/integrations/arnold/session/render.py:72:        segment_lineage=_segment_lineage(manifest.segments, current_segment.segment_id),
astrid/core/integrations/arnold/session/render.py:93:        "lineage": list(snapshot.segment_lineage),
astrid/core/integrations/arnold/session/render.py:99:        _lineage_section(snapshot.segment_lineage),
astrid/core/integrations/arnold/session/render.py:170:def _segment_lineage(segments: tuple[SegmentRecord, ...], segment_id: str) -> tuple[str, ...]:
astrid/core/integrations/arnold/session/render.py:172:    lineage: list[str] = []
astrid/core/integrations/arnold/session/render.py:175:        lineage.append(current_id)
astrid/core/integrations/arnold/session/render.py:180:    lineage.reverse()
astrid/core/integrations/arnold/session/render.py:181:    return tuple(lineage)
astrid/core/integrations/arnold/session/render.py:243:def _lineage_section(lineage: tuple[str, ...]) -> str:
astrid/core/integrations/arnold/session/render.py:244:    if not lineage:
astrid/core/integrations/arnold/session/render.py:245:        return "successor lineage:\n  (none)"
astrid/core/integrations/arnold/session/render.py:246:    return "successor lineage:\n  " + " -> ".join(lineage)
astrid/core/integrations/arnold/session/manifest.py:62:    event_lineage: EventLineageHashes = field(default_factory=EventLineageHashes)
astrid/core/integrations/arnold/session/manifest.py:88:            event_lineage=EventLineageHashes.from_dict(payload.get("event_lineage")),
astrid/core/integrations/arnold/session/manifest.py:109:        lineage = self.event_lineage.to_dict()
astrid/core/integrations/arnold/session/manifest.py:110:        if lineage:
astrid/core/integrations/arnold/session/manifest.py:111:            payload["event_lineage"] = lineage
astrid/core/generation/backends/vibecomfy.py:349:        # --- collect output paths and copy to out_dir ------------------------
astrid/core/integrations/arnold/session/resume.py:210:        current_segment.event_lineage.segment_start_hash
astrid/core/integrations/arnold/step_adapter.py:452:    """Remove a pre-existing materialized output path of any filesystem kind."""
astrid/core/integrations/arnold/step_adapter.py:474:    """Resolve every declared output path the runner is expected to populate."""
astrid/core/integrations/arnold/host/envelope.py:12:  second source of truth for lease or event lineage.
astrid/core/integrations/arnold/host/envelope.py:69:    lineage = _project_lineage(events)
astrid/core/integrations/arnold/host/envelope.py:74:        "lineage": list(lineage),
astrid/core/integrations/arnold/host/envelope.py:99:            lineage=lineage,
astrid/core/integrations/arnold/host/envelope.py:119:        "lineage": list(_project_lineage(events)),
astrid/core/integrations/arnold/host/envelope.py:132:    lineage: tuple[str, ...],
astrid/core/integrations/arnold/host/envelope.py:140:        lineage=lineage,
astrid/core/integrations/arnold/host/envelope.py:167:def _project_lineage(events: list[dict[str, Any]]) -> tuple[str, ...]:
astrid/core/integrations/arnold/host/envelope.py:168:    lineage: list[str] = []
astrid/core/integrations/arnold/host/envelope.py:172:            lineage.append(event_hash)
astrid/core/integrations/arnold/host/envelope.py:173:    return tuple(lineage)
astrid/core/integrations/arnold/host/compat.py:155:                for name in ("cost", "lineage")
astrid/core/integrations/arnold/host/shapes.py:250:    identity, ledger context, and output paths matching task runtime behavior.
astrid/core/integrations/arnold/host/shapes.py:2004:            "per-segment media.clip_extract fanout before candidate scoring "
astrid/packs/stream_content/executors/segment_map/core.py:114:    # Whisper segment-level timestamps are enough for density fallback.
astrid/packs/video_editing/orchestrators/iteration_video/STAGE.md:13:Run through the canonical gateway. The pack-level `--thread` is a lineage
astrid/core/execution/executor/runner.py:371:    """Resolve declared-output paths and return only those that exist on disk.
astrid/core/execution/executor/runner.py:404:    """Resolve declared-output paths *without* requiring files to exist on disk.
astrid/packs/_core/skill/SKILL.md:351:Before rendering an iteration video, run `python3 -m astrid.packs.video_editing.orchestrators.iteration_video.run inspect <thread>` to see modalities, renderers, quality, cache counts, and estimated cost without rendering. Note: the pack-level `--thread <id>` argument identifies a non-binding variant lineage WITHIN a pack and is UNRELATED to the removed `astrid thread` CLI verb or to session binding. Threads as a generic user-facing runtime concept were retired in Sprint 1 (DEC-001); the internal `astrid.core.threads` library is retained for pack lineage utilities.
astrid/packs/comfy_wrap/executors/run/run.py:115:    """Execute the workflow through vibecomfy and return output paths.
astrid/packs/blender/server/blender_render_server.py:161:    """Render per ``payload``. Returns a dict with result metadata + output path."""
astrid/packs/iteration/executors/assemble/run.py:368:            commands.append(f"restore or regenerate lineage for unresolved producer {run_id}")
astrid/packs/iteration/executors/assemble/run.py:369:    detail = "\n".join(commands) if commands else "restore or regenerate missing lineage inputs"
astrid/packs/understanding/executors/visual_understand/run.py:524:    add("--contact-sheet", type=Path, help="Optional output path for the generated contact sheet.")
astrid/packs/iteration/executors/prepare/run.py:241:        missing_signals.append("producer_lineage")
astrid/packs/rendering/executors/timeline_storyboard/run.py:719:                recovery_command="check the timeline, asset registry, and output paths, then retry",
astrid/packs/training/orchestrators/dataset_build/schemas/training-run-config.schema.json:163:          "description": "Identifier for this LoRA (used in output paths)."
astrid/packs/rendering/executors/html_canvas_effect/run.py:185:    parser.add_argument("--out", type=Path, required=True, help="Report JSON output path.")
astrid/packs/rendering/executors/html_canvas_effect/run.py:186:    parser.add_argument("--timeline", type=Path, help="Preview timeline JSON output path.")
astrid/packs/rendering/executors/html_canvas_effect/run.py:187:    parser.add_argument("--assets", type=Path, help="Preview assets JSON output path.")

exec
/bin/zsh -lc "sed -n '1,130p' .oracle/briefs/batch-1-t1.2.md; sed -n '1,120p' .oracle/briefs/batch-1-r2-t1.2.md; sed -n '220,310p' docs/contracts/render-backend-v1.md; sed -n '360,410p' docs/contracts/render-backend-v1.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
# Task T1.2 — Freeze language-neutral contracts and schemas [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 1 of "Pluggable Timeline Renderers". Read first, in this order:
- `.oracle/plan.md` (the stable plan; resolved decisions 1–12)
- `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` (18 locked decisions — FINAL, do not reopen)
- `.oracle/baseline.md` (created by T1.1; may exist)
- `astrid/core/foundation/` for `write_json_atomic` and `sha256_file` helpers
- `astrid/sdk/generation.py` for repo DTO conventions (frozen dataclasses, `_json_safe`)

Your job: define the frozen, language-neutral wire contracts and schemas for
render backends. This is THE contract M2 must build on — be precise.

## Change

Create `astrid/core/rendering/` with:
- `__init__.py` — public names: `RenderRequest`, `SupportReport`,
  `RenderPlan`, `FrameWindow`, `RenderProfile`, `AudioOwnership`,
  `VideoArtifact`, `RenderResult`, `RendererError`, `BackendConfig`,
  `Attachment`.
- `contracts.py` — frozen dataclasses (mirror `sdk/generation.py` style,
  `_json_safe` serialization, `to_dict`), exactly matching the JSON schemas
  below:
  - `FrameWindow`: `start_frame:int >=0`, `end_frame:int > start_frame`
    (half-open `[start,end)`), `fps_rational:(num,den)`, optional
    `source_range` and `speed`.
  - `AudioOwnership`: enum `rendered|passthrough|none`.
  - `RenderProfile`: dimensions (w,h >0), `fps_rational`, time base,
    video codec/profile/level, pixel format, audio codec/sample rate/channel
    layout (optional — visual-only profiles omit audio), `duration_tolerance`.
  - `VideoArtifact`: `path` (contained in workspace), `profile: RenderProfile`,
    `sha256`, `duration_frames`, `audio: AudioOwnership | None`,
    `attachments: dict[str, Attachment]` (named, optional, preserved but not
    interpreted by default finalizers).
  - `Attachment`: `name`, `path`, `kind` (e.g. `alpha|depth|frames|audio-stem|project`), `sha256`.
  - `RenderRequest`: `schema_version` (int, required, unknown → error),
    `timeline_path`, `assets_registry_path | None`, `output_name` (neutral,
    no backend names), `window: FrameWindow | None` (None = full timeline),
    `audio: AudioOwnership | None` (None = backend default),
    `profile: RenderProfile | None` (None = host resolves canonical profile),
    `backend_config: dict[str, dict]` (keyed by QUALIFIED backend id; core
    request carries NO backend-specific top-level fields),
    `metadata: dict[str,str]` (free-form, e.g. project/session ids).
  - `SupportReport`: `supported: bool`, `reasons: list[str]`, `features:
    dict[str, bool|str]` (request-sensitive capability evidence),
    `alternatives: list[str]` (qualified backend ids),
    `backend: str` (qualified id), `backend_version: str|None`.
  - `RenderPlan`: `segments: list[RenderSegment]`, `finalizer: str` (qualified
    id), `profile: RenderProfile`, `reasons: dict[str,str]` (selection reason
    per segment).
  - `RenderSegment`: `window: FrameWindow`, `backend: str` (qualified id),
    `backend_config`, `support: SupportReport | None`, `input_hashes: dict[str,str]`.
  - `RenderResult`: `schema_version`, `video: VideoArtifact`,
    `attachments: dict[str, Attachment]`, `backend_fragments: dict[str, dict]`
    (namespaced, cannot overwrite core keys), `audio_ownership`,
    `normalization: list[str]`, `logs: list[str]` (redacted), `metadata`.
  - `RendererError`: `kind` enum
    (`protocol|unsupported|binary_missing|timeout|interrupted|invalid_artifact|internal`),
    `backend` (qualified id), `message`, `recovery_command: str|None`,
    `details: dict` (JSON-safe).
- `errors.py` — exception hierarchy wrapping `RendererError` plus helpers to
  raise structured failures; unknown/malformed request versions must fail
  with `kind="protocol"`.
- `provenance.py` — v2 provenance assembly: core-owned keys (`schema_version`,
  `engine` (legacy request projection), `output`, `timeline`,
  `assets_registry`, `requested_policy`, `resolved_backend`, `source_pack`,
  `alias_chain`, `override`, `trust_eligibility`, `manifest_digest`,
  `support_decision`, `input_hashes`, `segments`, `artifact_profiles`,
  `audio_ownership`, `normalization`, `finalizer`, `attachments`) PLUS
  backend-owned fragments under a `backend_fragments` namespace that is
  validated to NOT overwrite core keys (a fragment attempting to set a
  core-owned key must be rejected). Keep every current v1 key as a
  compatibility projection (see baseline for the v1 key list).
- `schemas/v1/` — JSON Schemas: `request.json`, `result.json`,
  `support.json`, `plan.json`, `finalize.json`, `renderer-manifest.json`,
  `planner-manifest.json`, `finalizer-manifest.json`. These are the
  language-neutral source of truth. DTO round-trip must match.
- `tests/core/rendering/test_contracts.py` — DTO ↔ JSON round-trip,
  unknown version rejected, invalid frame bounds rejected, duplicate
  attachment names rejected, path traversal in artifact paths rejected,
  backend fragment attempting to overwrite core provenance key rejected.
- `tests/core/rendering/test_schema_roundtrip.py` — every example in the
  schemas validates; DTO `to_dict` output validates against the JSON Schema;
  schema examples parse into DTOs.
- `docs/contracts/render-backend-v1.md` — the frozen contract reference:
  discovery/trust summary, manifest format, the four operations
  (`render|support|plan|finalize` with `--request <abs> --result <abs>`),
  wire schema, lifecycle, configuration namespacing, assets, media/audio
  ownership contract, attachments, support reporting, errors, planning,
  finalization, provenance ownership (core vs backend), cleanup, replay
  inputs, versioning. Preserve locked decisions 1–18 from the epic brief
  verbatim in a section.

Do NOT implement discovery, transport, the service, or backends — later
batches do that. Only contracts, schemas, provenance assembly, and docs.

## Acceptance

- `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py` passes.
- `pytest -q tests/core/rendering` (whole dir) has no failures.
- `docs/contracts/render-backend-v1.md` exists and is complete.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do not modify files outside `astrid/core/rendering/`,
`docs/contracts/render-backend-v1.md`, and `tests/core/rendering/`. Preserve
all existing work; never reset. Report: what you created, test results, and
any contract decisions you made (with rationale).
# Rework T1.2R2 — Contract/schema/registry fixes (oracle re-review issues 2–5) [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

The Batch 1 re-review (`.oracle/checkins/batch-1-r1.md`, final ISSUES block)
found these remaining issues. Fix ALL of them. Your files:
`astrid/core/rendering/{contracts,errors,provenance,registry}.py`,
`astrid/core/rendering/schemas/v1/*.json`, `tests/core/rendering/`,
`docs/contracts/render-backend-v1.md`. A Flash agent is fixing the baseline
doc in parallel (`.oracle/baseline.md` + characterization tests) — do NOT
touch those.

## Issue 4 (most urgent) — underscore-compatible qualified IDs missing; fixture rewriting masks it

The frozen plan (decision 6) requires `rendering.legacy_hybrid` (underscore);
pack ids use underscores; the canonical finalizer is `rendering.ffmpeg-finalizer`
(hyphen). The committed `_QUALIFIED_ID_RE` in
`astrid/core/rendering/contracts.py:35` is hyphen-only, and the schemas match
it. Tests CONCEAL this by rewriting fixture IDs at runtime in
`tests/core/rendering/test_registry.py` `_canonical_fixture_root` (added by a
prior agent). The oracle: "Allowing both `_` and `-` is correct given the
locked planner ID and pack-ID conventions; `rendering.ffmpeg-finalizer`
should remain canonical."

Rework:
- `contracts.py:35`: `_QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")`.
- Update EVERY `id`/`backend`/`alternatives` pattern in
  `schemas/v1/*.json` from `[a-z0-9-]*` to `[a-z0-9_-]*` (same for any
  pattern elsewhere in contracts/schemas).
- Update `docs/contracts/render-backend-v1.md` ID grammar section: segments
  match `[a-z0-9][a-z0-9_-]*` (hyphens and underscores valid); examples
  `rendering.remotion`, `rendering.legacy_hybrid`, `rendering.ffmpeg-finalizer`.
- REMOVE the runtime fixture-rewriting in `test_registry.py`
  (`_canonical_fixture_root` and any `_`→`-` rewriting in
  `_stage_installed_fixture`); tests must run against the REAL committed
  fixtures (`tests/fixtures/renderer_packs/discovery/`), which declare
  `rendering.legacy_hybrid`, `rendering.ffmpeg-finalizer`,
  `cycle_render`, `env_render`, etc.
- Restore/adjust any test that asserted underscore rejection; the grammar
  now accepts both. `rendering.ffmpeg_finalizer` and `rendering.legacy-hybrid`
  are both VALID ids now (spelling canonicality is separate from validity).
- Prove `validate_pack` and the CLI validation path accept the REAL committed
  discovery fixture packs (no rewriting).
- Re-run the full `tests/core/rendering` suite — all green with no runtime
  rewriting.

## Issue 2 — Provenance regresses v1 and replay lineage incomplete

`provenance.py` replaces the legacy `segments` key and overwrites nested
`segment_provenance` sidecars with `{engine,from,to}` projections, contradicting
the characterized legacy shapes (`tests/packs/rendering/test_legacy_renderer_characterization.py:385`).

Rework:
- PRESERVE both v1 projections UNCHANGED: legacy `segments` and
  `segment_provenance` keep exactly the v1 shapes recorded in baseline.
- Add normalized v2 records under an ADDITIVE field (e.g.
  `segments_v2` or `render_plan`) — never overwrite v1 keys.
- Resolution records complete for ALL capability kinds: planner, each
  renderer invocation/segment, and finalizer each carry `{id, source_pack,
  manifest_digest, alias_chain, override, trust_eligibility, support_decision}`
  (host-authoritative).
- Include artifact hashes (per-segment video/attachments) in provenance.
- Define and verify `request_digest` semantics (what exactly is hashed;
  round-trip test).

## Issue 3 — Schema/DTO parity still false for whitespace

`request.json:165` accepts empty/whitespace-only metadata keys/values while
`contracts.py:244` rejects them; result paths and profile strings have
equivalent mismatches.

Rework: align every schema string constraint with the DTO's nonblank-string
rules (pattern `\S` or minLength where DTO requires nonblank). Add
whitespace adversaries to the parity battery for requests, plans, results,
finalization, support reports, and manifests.

## Issue 5 (new) — Valid pack alias→override routes dropped

`registry.py:1023` recognizes an override-routable missing canonical target
only when the alias originates from `astrid.core`. A trusted pack route
`pack.alias → missing.canonical → override → executable.renderer` is
discarded, violating the frozen alias→canonical→override ordering.

Rework: evaluate override-routable terminals for EVERY eligible alias
declaration (not just core aliases); retain fail-closed behavior for invalid
targets; add a regression: trusted-pack alias → absent canonical → executable
override target resolves successfully with evidence recording the override.

## Acceptance

- `pytest -q tests/core/rendering` passes (whole dir).
- `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py` passes (validate_pack on real fixtures, no rewriting).
- `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py` passes (v1 provenance shapes unchanged).
- `docs/contracts/render-backend-v1.md` reflects the corrected grammar + provenance v2 additive design.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do NOT modify `.oracle/baseline.md`, `astrid/packs/` production code,
`astrid/core/pack/` (unless a minimal validate_pack regression requires it —
prefer test-only), or `tests/packs/rendering/test_legacy_renderer_characterization.py`.
Preserve all existing work. Report: changes, test results, how you removed
the runtime rewriting, the request-digest semantics you locked.
request carries an empty mapping or only its selected finalizer's namespace.
Backends must ignore no unknown core fields: unknown core fields are protocol
errors.

## Assets and workspace paths

The host owns asset resolution and localization. Request input paths may be
absolute after localization. The timeline and optional registry remain the
canonical replay inputs; remote URLs and cached assets are materialized or
made available by later host plumbing according to declared permissions.

Artifact paths in results have a different rule: they are normalized paths
relative to the unique invocation workspace. They cannot be absolute, begin
with a Windows drive prefix such as `C:`, contain backslashes, UNC prefixes,
`.` or `..` traversal, empty path components, trailing separators, or NUL. The
host resolves the path, rejects symlink escapes, requires the expected file or
directory, and verifies its hash before publication. This relative rule lets
the same result and replay bundle move between machines.

## Primary video, media, and audio ownership

Every successful render and finalization result contains exactly one primary
`VideoArtifact` with:

- a contained relative `path`;
- the probed `RenderProfile`;
- lowercase 64-character `sha256`;
- positive `duration_frames`;
- artifact `audio` ownership (nullable only before it is wrapped in a successful
  result);
- optional named attachments (default `{}`).

The host validates existence, non-empty output, workspace containment,
symlinks, digest, duration, dimensions, FPS/time base, container, codecs,
pixel format, and declared audio state before assembly or publication.

Audio ownership values have precise meanings:

- `rendered`: the backend owns and returns final timeline audio in the video;
- `passthrough`: the backend returns visual media and asks Astrid to preserve
  or mux the canonical source/timeline audio;
- `none`: the intended output has no audio.

The probed profile and artifact ownership are coupled. `rendered` requires the
complete populated audio trio because the returned artifact contains audio.
`passthrough` and `none` require a visual-only profile: passthrough asks the
host/finalizer to supply canonical audio later, while none declares that no
audio is intended. When a request supplies both non-null fields, it follows the
same relationship; it may leave audio or profile `null` for a backend/host
default.
A successful `RenderResult.audio_ownership` is never null and must exactly
match its non-null `VideoArtifact.audio`. Visual-only renderers are valid and
are never required to synthesize silence. The host/finalizer, not an arbitrary
backend, owns passthrough, muxing, normalization, or compatibility silence.

## Attachments

An `Attachment` has `name`, relative contained `path`, extensible lowercase
hyphenated `kind`, and `sha256`. Typical kinds include `alpha`, `depth`,
`frames`, `audio-stem`, and `project`; the list is illustrative, not an enum.

Attachments are maps keyed by name. The key must equal `Attachment.name`.
`VideoArtifact.attachments` is the one authoritative attachment surface;
`RenderResult` has no second attachment map. Names must be globally unique
across every segment artifact in one `FinalizeRequest`, even when two
descriptors are otherwise identical. Planners and finalizers preserve every
input attachment's name, path, kind, and hash unchanged. A finalizer may add a
new attachment, and a custom finalizer may interpret a kind only when its
contract explicitly says so, but it may not silently drop, rename, or mutate an
input attachment.

## Successful render result

`RenderResult` has `schema_version: 1`, the primary `video` (including its
attachments), qualified-ID-keyed `backend_fragments`, explicit
`audio_ownership`, `normalization` descriptions, redacted `logs`, and string
`metadata`. Successful result fields are core-owned. A top-level result
`attachments` member is invalid rather than a compatibility alias.

Backend fragments are JSON objects beneath their qualified namespace:

```json
{
  "backend_fragments": {
    "acme.example": {
      "renderer": "example",
      "quality": "preview"
    }
  }
}
```
`alias_chain` is an array of strings and defaults to `[]`; `override` is
`{from, to}` with `to` equal to the resolution id (an override records what
selected this implementation — the DTO rejects `{from, to}` shapes whose `to`
differs, and rejects any other shape), or `null`; `trust_eligibility` records
the derived source/install trust decision; `support_decision` is a versioned
`SupportReport` or `null` (when no request-sensitive probe ran, e.g. for a
finalizer). Every non-null `support_decision.backend` MUST equal the
capability ID — the DTO rejects a mismatch for planner, renderer, and
finalizer alike. Manifest, request, and input-hash values are lowercase
SHA-256 digests. There is no parallel `segment.backend`, `segment.support`,
or string-only finalizer field that could disagree with these records.

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
segments may stream-copy. Otherwise the finalizer normalizes dimensions,
rational FPS/time base, container, video codec/profile/level, pixel format,
audio codec/sample rate/channel layout, and audio presence. Every performed
normalization is appended to `normalization`. The finalizer preserves
attachments it does not understand. The first built-in finalizer uses FFmpeg;
its one canonical qualified ID is `rendering.ffmpeg-finalizer`. FFmpeg is not
part of the generic contract.

## Structured errors


exec
/bin/zsh -lc "git show 086d692:astrid/core/rendering/provenance.py | nl -ba | sed -n '70,230p'; git log --oneline -- astrid/core/rendering/provenance.py | head -n 15" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 74ms:
ab486f9 batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)
086d692 batch1-rework6: oracle re-review5 issues 1-3 (lineage required+shape-bound+path-bound, NUL-after-newline, hashMap/feature propertyNames, workspacePath newlines)
91f0fe3 batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
88c75f3 batch1-rework2: oracle re-review issues 1-5 (real-fixture deconcealment, underscore-compatible ids, provenance v1 preservation + v2 additive, whitespace parity, transitive override routing, baseline C0 evidence)
b357de3 batch1-rework: oracle issues 1-9 (baseline facade ownership, contracts versioning/attachments/provenance, pack validation, transitive alias eligibility)
f8af4b2 batch1: renderer contracts, schemas, pack extension, trusted registries, baseline characterization

exec
/bin/zsh -lc 'tail -n 120 .oracle/checkins/batch-1-r5.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc "rg -n \"def _require_workspace|class Attachment|class VideoArtifact|def _require_string|_ATTACHMENT_KIND|KIND_RE\" astrid/core/rendering/contracts.py; nl -ba astrid/core/rendering/contracts.py | sed -n '180,360p'; nl -ba astrid/core/rendering/contracts.py | sed -n '600,750p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
39:_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
217:def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
264:def _require_string_list(value: Any, label: str) -> list[str]:
270:def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
314:def _require_workspace_relative_path(value: Any, label: str) -> str:
583:class Attachment:
596:        if not _KIND_RE.fullmatch(kind):
656:class VideoArtifact:
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
   341	
   342	
   343	def _protocol_failure(message: str, *, details: Mapping[str, Any] | None = None) -> NoReturn:
   344	    from .errors import raise_protocol_error
   345	
   346	    raise_protocol_error(
   347	        backend="astrid.core",
   348	        message=message,
   349	        details=dict(details or {}),
   350	    )
   351	
   352	
   353	class AudioOwnership(str, Enum):
   354	    """Who is responsible for audio in a returned primary video."""
   355	
   356	    RENDERED = "rendered"
   357	    PASSTHROUGH = "passthrough"
   358	    NONE = "none"
   359	
   360	
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

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '570,610p'; rg -n \"artifact_profiles\" -g '*.py' -g '*.md' -g '*.json' --glob '"'!.oracle/checkins/**'"' . | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
./docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
./docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
./astrid/core/rendering/provenance.py:86:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
./astrid/core/rendering/provenance.py:96:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
./astrid/core/rendering/provenance.py:104:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
./astrid/core/rendering/provenance.py:112:                    f"artifact_profiles must record exactly one hashed lineage entry "
./astrid/core/rendering/provenance.py:121:                    "sequence artifact_profiles entries must be VideoArtifacts "
./astrid/core/rendering/provenance.py:128:                    f"artifact_profiles must record exactly one hashed lineage entry "
./astrid/core/rendering/provenance.py:132:    raise TypeError("artifact_profiles must be an object or array")
./astrid/core/rendering/provenance.py:247:    artifact_profiles: Any = None,
./astrid/core/rendering/provenance.py:298:        "artifact_profiles": _normalize_artifact_profiles(
./astrid/core/rendering/provenance.py:299:            artifact_profiles,
./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
./astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
./tests/core/rendering/test_contracts.py:567:        "artifact_profiles": {
./tests/core/rendering/test_contracts.py:697:        artifact_profiles={
./tests/core/rendering/test_contracts.py:766:        artifact_profiles={"outputs/visual.mp4": artifact},
./tests/core/rendering/test_contracts.py:773:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
./tests/core/rendering/test_contracts.py:827:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
./tests/core/rendering/test_contracts.py:833:            artifact_profiles={
./tests/core/rendering/test_contracts.py:841:            artifact_profiles={
./tests/core/rendering/test_contracts.py:853:            artifact_profiles={
./tests/core/rendering/test_contracts.py:868:            artifact_profiles={
./tests/core/rendering/test_contracts.py:880:            artifact_profiles={
./tests/core/rendering/test_contracts.py:894:            artifact_profiles={
./tests/core/rendering/test_contracts.py:910:            artifact_profiles={

exec
/bin/zsh -lc "git diff --unified=12 086d692..ab486f9 -- tests/core/rendering/test_contracts.py | rg -n '"'^@@|''^'"\\+["'^+]|''^-[''^-]'"' | sed -n '1,320p'; rg -n \"multiline|workspace.*newline|features.*property|blank.*feature|nul.*feature|artifact_profiles.*sequence|exactly one hashed|different_key|Bad_Kind|escape.mp4\" tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
5:@@ -560,25 +560,30 @@ def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: P
18:-            }
19:+            },
20:+            "outputs/segment2.mp4": {
21:+                "profile": _profile(),
22:+                "sha256": SHA_C,
23:+                "attachments": {},
24:+            },
37:@@ -685,24 +690,29 @@ def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
50:+            },
51:+            "outputs/segment2.mp4": {
52:+                "profile": _profile(),
53:+                "sha256": SHA_C,
54:+                "attachments": {},
67:@@ -797,63 +807,130 @@ def test_resolutions_reject_incoherent_override_records() -> None:
80:-        plan=_plan(),
88:-        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
89:+        assemble_provenance_v2(
90:+            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
91:+        )
95:+            plan=_plan(),
103:+            plan=_plan(),
115:+            plan=_plan(),
125:+    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
126:+        assemble_provenance_v2(
127:+            **base,
128:+            plan=_plan(
129:+                segments=[_segment(0, 24), _segment(24, 48)]
130:+            ),
131:+            artifact_profiles={
132:+                "out/v.mp4": {
133:+                    "profile": _profile(),
134:+                    "sha256": SHA_B,
135:+                    "attachments": {},
136:+                }
137:+            },
138:+        )
139:+    with pytest.raises(ValueError, match="attachment path"):
140:+        assemble_provenance_v2(
141:+            **base,
142:+            plan=_plan(),
143:+            artifact_profiles={
144:+                "out/v.mp4": {
145:+                    "profile": _profile(),
146:+                    "sha256": SHA_B,
147:+                    "attachments": {
148:+                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
149:+                    },
150:+                },
151:+            },
152:+        )
153:+    with pytest.raises(ValueError, match="attachment kind"):
154:+        assemble_provenance_v2(
155:+            **base,
156:+            plan=_plan(),
157:+            artifact_profiles={
158:+                "out/v.mp4": {
159:+                    "profile": _profile(),
160:+                    "sha256": SHA_B,
161:+                    "attachments": {
162:+                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
163:+                    },
164:+                },
165:+            },
166:+        )
169:+    with pytest.raises(ValueError, match="must equal Attachment.name"):
170:+        assemble_provenance_v2(
171:+            **base,
172:+            plan=_plan(),
173:+            artifact_profiles={
174:+                "out/v.mp4": {
175:+                    "profile": _profile(),
176:+                    "sha256": SHA_B,
177:+                    "attachments": {
178:+                        "different_key": Attachment(
179:+                            name="alpha",
180:+                            path="outputs/alpha.mp4",
181:+                            kind="alpha",
182:+                            sha256=SHA_C,
183:+                        )
184:+                    },
185:+                }
186:+            },
187:+        )
tests/core/rendering/test_schema_roundtrip.py:222:        ("drive-relative video", _set(base, ("video", "path"), "C:escape.mp4")),
tests/core/rendering/test_schema_roundtrip.py:359:        "../escape.mp4",
tests/core/rendering/test_schema_roundtrip.py:360:        "outputs/./escape.mp4",
tests/core/rendering/test_schema_roundtrip.py:361:        "outputs//escape.mp4",
tests/core/rendering/test_schema_roundtrip.py:363:        "/tmp/escape.mp4",
tests/core/rendering/test_schema_roundtrip.py:364:        "C:escape.mp4",
tests/core/rendering/test_schema_roundtrip.py:365:        r"C:\\temp\\escape.mp4",
tests/core/rendering/test_schema_roundtrip.py:366:        r"dir\\escape.mp4",
tests/core/rendering/test_contracts.py:499:        "../escape.mp4",
tests/core/rendering/test_contracts.py:500:        "outputs/../../escape.mp4",
tests/core/rendering/test_contracts.py:501:        "outputs/./escape.mp4",
tests/core/rendering/test_contracts.py:502:        "outputs//escape.mp4",
tests/core/rendering/test_contracts.py:504:        "/tmp/escape.mp4",
tests/core/rendering/test_contracts.py:505:        "C:escape.mp4",
tests/core/rendering/test_contracts.py:506:        r"C:\\temp\\escape.mp4",
tests/core/rendering/test_contracts.py:507:        r"\\\\server\\share\\escape.mp4",
tests/core/rendering/test_contracts.py:862:    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
tests/core/rendering/test_contracts.py:885:                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
tests/core/rendering/test_contracts.py:899:                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
tests/core/rendering/test_contracts.py:915:                        "different_key": Attachment(

exec
/bin/zsh -lc "rg -n -U \"ok\\\\n|newline|line break|sub/\\.\\.|after.*newline|double slash|backslash|support feature|features.*key|blank.*key|NUL.*key\" tests/core/rendering/test_contracts.py | sed -n '1,260p'; git diff --unified=8 086d692..ab486f9 -- tests/core/rendering/test_contracts.py | tail -n 250" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 69b4791..69d4327 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -564,17 +564,22 @@ def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: P
         "timeline": "/workspace/timeline.json",
         "assets_registry": "/workspace/assets.json",
         "plan": plan,
         "artifact_profiles": {
             "outputs/video.mp4": {
                 "profile": _profile(),
                 "sha256": SHA_B,
                 "attachments": {},
-            }
+            },
+            "outputs/segment2.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_C,
+                "attachments": {},
+            },
         },
         "audio_ownership": AudioOwnership.RENDERED,
         "normalization": [],
         "attachments": {},
         "backend_fragments": {"acme.first": {"vendor": "Acme"}},
         "v1_compatibility": compatibility,
     }
     payload = assemble_provenance_v2(**kwargs)
@@ -689,16 +694,21 @@ def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
         timeline="/workspace/timeline.json",
         assets_registry=None,
         plan=plan,
         artifact_profiles={
             "outputs/visual.mp4": {
                 "profile": _profile(),
                 "sha256": SHA_B,
                 "attachments": {},
+            },
+            "outputs/segment2.mp4": {
+                "profile": _profile(),
+                "sha256": SHA_C,
+                "attachments": {},
             }
         },
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
@@ -801,55 +811,122 @@ def test_resolutions_reject_incoherent_override_records() -> None:
 def test_provenance_rejects_spoofed_artifact_lineage() -> None:
     """Artifact lineage must carry a real sha256; profile-only entries and
     null hashes are rejected rather than stringified."""
     base = dict(
         engine="hybrid",
         output="/workspace/out/video.mp4",
         timeline="/workspace/timeline.json",
         assets_registry=None,
-        plan=_plan(),
         audio_ownership="rendered",
         normalization=[],
         attachments={},
         backend_fragments={},
         v1_compatibility=_compatibility(),
     )
     with pytest.raises(TypeError, match="hashed lineage"):
-        assemble_provenance_v2(**base, artifact_profiles={"out/v.mp4": _profile()})
+        assemble_provenance_v2(
+            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
+        )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
+            plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
             },
         )
     with pytest.raises(ValueError, match="sha256"):
         assemble_provenance_v2(
             **base,
+            plan=_plan(),
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
+            plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {},
                     "spoof": 1,
                 }
             },
         )
+    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(
+                segments=[_segment(0, 24), _segment(24, 48)]
+            ),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {},
+                }
+            },
+        )
+    with pytest.raises(ValueError, match="attachment path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+    with pytest.raises(ValueError, match="attachment kind"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
+                    },
+                },
+            },
+        )
+
+
+    with pytest.raises(ValueError, match="must equal Attachment.name"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "out/v.mp4": {
+                    "profile": _profile(),
+                    "sha256": SHA_B,
+                    "attachments": {
+                        "different_key": Attachment(
+                            name="alpha",
+                            path="outputs/alpha.mp4",
+                            kind="alpha",
+                            sha256=SHA_C,
+                        )
+                    },
+                }
+            },
+        )
 
 
 def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
     plan = _plan(
         segments=[_segment(12, 24), _segment(24, 36)],
         total_frames=48,
         window=_window(12, 36),
     )

exec
/bin/zsh -lc "rg -n \"SCHEMA|schema|Draft7|Validator|workspacePath|workspace path|path_cases|support\" tests/core/rendering/test_contracts.py | sed -n '1,320p'; rg -n -U '\"["'^"'"\\n]*\\\\n["'^"'"\\n]*\"|\\\\x00|\\\\u0000' tests/core/rendering/test_contracts.py | sed -n '1,260p'; nl -ba tests/core/rendering/test_contracts.py | sed -n '1160,1500p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
84:def _support(backend: str = "acme.example") -> SupportReport:
86:        schema_version=1,
87:        supported=True,
104:        support_decision=_support("rendering.legacy_hybrid"),
115:        support_decision=_support(backend),
128:        support_decision=_support("rendering.ffmpeg-finalizer"),
159:        schema_version=1,
167:        reasons={str(index): "the request is supported" for index in range(len(selected))},
194:        schema_version=1,
211:        schema_version=1,
222:        schema_version=1,
240:        schema_version=1,
241:        kind="unsupported",
243:        message="transitions are unsupported",
250:        (SupportReport, _support()),
264:            "schema_version": 1,
276:        schema_version=1,
291:        schema_version=1,
296:        schema_version=1,
297:        kind="unsupported",
299:        message="unsupported",
305:        "support": (SupportReport.from_dict, _support().to_dict()),
322:        payload.pop("schema_version")
324:        payload["schema_version"] = {
339:                "schema_version": 1,
401:            schema_version=1,
409:            schema_version=1,
417:        schema_version=1,
430:            schema_version=1,
586:    assert payload["schema_version"] == 2
632:    a = {"backend_config": {"acme.visual": {"quality": "preview"}}, "schema_version": 1}
633:    b = {"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}}}
639:    assert compute_request_digest({"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}, "other.key": {}}}) != digest
650:    """Non-default alias/override/trust/support evidence must survive the
656:        support_decision=_support("rendering.legacy_hybrid"),
669:        support_decision=_support("rendering.ffmpeg-finalizer"),
684:    assert reparsed.planner.support_decision is not None
688:    assert reparsed.finalizer.support_decision is not None
717:    assert payload["planner"]["support_decision"]["backend"] == "rendering.legacy_hybrid"
735:        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
779:def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
780:    """support_decision.backend must equal the resolution id for planner and
789:        payload["support_decision"] = _support("other.backend").to_dict()
790:        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
978:                   support_decision=_support("1render.2-finalizer")).id == "1render.2-finalizer"
980:                   support_decision=_support("rendering.legacy_hybrid")).id == "rendering.legacy_hybrid"
982:                   support_decision=_support("acme.bad_id")).id == "acme.bad_id"
989:            replace(_finalizer(), id=invalid, support_decision=_support(invalid))
1000:        "schema_version": 1,
1013:        (RendererManifest, {**common, "id": "acme.renderer", "operations": ["render", "support"]}),
1021:def test_manifest_dto_rejects_schema_invalid_capabilities_and_scalar_command() -> None:
1023:        "schema_version": 1,
612:    assert sidecar.read_text(encoding="utf-8").endswith("\n")

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '1,450p'; nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '450,900p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc "rg -n -F '\\n' tests/core/rendering || true; rg -n -F 'ok' tests/core/rendering/test_schema_roundtrip.py tests/core/rendering/test_contracts.py | tail -n 80; git show --format= --name-only ab486f9" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_contracts.py:612:    assert sidecar.read_text(encoding="utf-8").endswith("\n")
tests/core/rendering/test_registry.py:91:        f"  - id: {permission}\n    reason: Fixture permission.\n"
tests/core/rendering/test_registry.py:101:        pack_lines.append("permissions:\n" + permission_lines.rstrip())
tests/core/rendering/test_registry.py:110:    (pack_root / "pack.yaml").write_text("\n".join(pack_lines) + "\n", encoding="utf-8")
tests/core/rendering/test_registry.py:127:        (manifests / manifest_name).write_text("\n".join(body) + "\n", encoding="utf-8")
tests/core/rendering/test_registry.py:129:        'raise AssertionError("fixture backend must remain inert")\n',
tests/core/rendering/test_registry.py:150:        manifest.read_text(encoding="utf-8") + "\n".join(lines) + "\n",
tests/core/rendering/test_registry.py:332:            + "aliases:\n"
tests/core/rendering/test_registry.py:333:            + "  - kind: renderer\n"
tests/core/rendering/test_registry.py:334:            + "    alias: shared.renderer-alias\n"
tests/core/rendering/test_registry.py:335:            + f"    canonical_id: {target}\n",
tests/core/rendering/test_registry_matrix.py:93:        f"  - id: {permission}\n    reason: Fixture permission.\n"
tests/core/rendering/test_registry_matrix.py:103:        pack_lines.append("permissions:\n" + permission_lines.rstrip())
tests/core/rendering/test_registry_matrix.py:112:    (pack_root / "pack.yaml").write_text("\n".join(pack_lines) + "\n", encoding="utf-8")
tests/core/rendering/test_registry_matrix.py:129:        (manifests / manifest_name).write_text("\n".join(body) + "\n", encoding="utf-8")
tests/core/rendering/test_registry_matrix.py:131:        'raise AssertionError("fixture backend must remain inert")\n',
tests/core/rendering/test_registry_matrix.py:374:        duplicate.read_text(encoding="utf-8") + "required_permissions: [network]\n",
tests/core/rendering/test_registry_matrix.py:510:    pack_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")
tests/core/rendering/test_contracts.py:736:            broken = obj.to_dict()
tests/core/rendering/test_contracts.py:737:            del broken[missing]
tests/core/rendering/test_contracts.py:739:                parser(broken)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r6.md
astrid/core/rendering/provenance.py
astrid/core/rendering/schemas/v1/finalize.json
astrid/core/rendering/schemas/v1/plan.json
astrid/core/rendering/schemas/v1/result.json
docs/contracts/render-backend-v1.md
tests/core/rendering/test_contracts.py

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_contracts.py | sed -n '1,230p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   221	    request = RenderRequest(
   222	        schema_version=1,
   223	        timeline_path="/workspace/timeline.json",
   224	        assets_registry_path="/workspace/assets.json",
   225	        output_name="preview.mp4",
   226	        window=_window(),
   227	        audio=AudioOwnership.RENDERED,
   228	        profile=_profile(),
   229	        backend_config={"acme.example": {"quality": "preview"}},
   230	        metadata={"project_id": "demo"},

exec
/bin/zsh -lc "rg -n \"class SupportReport|features\" astrid/core/rendering/contracts.py | head -n 30; nl -ba astrid/core/rendering/contracts.py | sed -n '890,1010p'; jq '.definitions.supportReport.properties.features, .properties.features' astrid/core/rendering/schemas/v1/plan.json astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/support.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
893:class SupportReport:
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
{
  "type": "object",
  "additionalProperties": {
    "type": [
      "boolean",
      "string"
    ]
  },
  "propertyNames": {
    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
  }
}
null
{
  "type": "object",
  "additionalProperties": {
    "type": [
      "boolean",
      "string"
    ]
  },
  "propertyNames": {
    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
  }
}
null
null
{
  "type": "object",
  "additionalProperties": {
    "type": [
      "boolean",
      "string"
    ]
  },
  "propertyNames": {
    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
  }
}

exec
/bin/zsh -lc "rg -n \"def _json_safe|NUL\" astrid/core/rendering/contracts.py | head -n 40; nl -ba astrid/core/rendering/contracts.py | sed -n '90,180p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
132:def _json_safe(value: Any) -> Any:
160:def _json_safe_mapping(value: Any, *, label: str = "value") -> dict[str, Any]:
221:        raise ValueError(f"{label} must not contain NUL")
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

exec
/bin/zsh -lc "jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/result.json > /tmp/ws-result.json; jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/finalize.json > /tmp/ws-finalize.json; diff -u /tmp/ws-result.json /tmp/ws-finalize.json || true; jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/plan.json > /tmp/sr-plan.json; jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/finalize.json > /tmp/sr-finalize.json; jq -S '.' astrid/core/rendering/schemas/v1/support.json > /tmp/sr-support-whole.json; diff -u /tmp/sr-plan.json /tmp/sr-finalize.json || true; git diff --no-index -- /tmp/sr-plan.json <(jq -S 'del(."'$schema, .$id, .title, .examples)'"' astrid/core/rendering/schemas/v1/support.json) || true" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
zsh:1: operation not permitted: /tmp/ws-result.json
zsh:1: operation not permitted: /tmp/ws-finalize.json
diff: /tmp/ws-result.json: No such file or directory
zsh:1: operation not permitted: /tmp/sr-plan.json
zsh:1: operation not permitted: /tmp/sr-finalize.json
zsh:1: operation not permitted: /tmp/sr-support-whole.json
diff: /tmp/sr-plan.json: No such file or directory
jq: error: syntax error, unexpected BINDING (Unix shell quoting issues?) at <top-level>, line 1:
del(.$schema, .$id, .title, .examples)     
jq: error: try .["field"] instead of .field for unusually named fields at <top-level>, line 1:
del(.$schema, .$id, .title, .examples)    
jq: 2 compile errors
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
error: Could not access '/tmp/sr-plan.json'

exec
/bin/zsh -lc "diff -u <(jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/result.json) <(jq -S '.definitions.workspacePath' astrid/core/rendering/schemas/v1/finalize.json) || true; diff -u <(jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/plan.json) <(jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/finalize.json) || true; diff -u <(jq -S '.definitions.supportReport' astrid/core/rendering/schemas/v1/plan.json) <(jq -S 'del(.\""'$schema", ."$id", .title, .examples)'"' astrid/core/rendering/schemas/v1/support.json) || true" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
diff: /dev/fd/11: Operation not permitted
diff: /dev/fd/11: Operation not permitted
diff: /dev/fd/11: Operation not permitted

exec
/bin/zsh -lc 'a=$(jq -cS '"'.definitions.workspacePath' astrid/core/rendering/schemas/v1/result.json); b="'$(jq -cS '"'.definitions.workspacePath' astrid/core/rendering/schemas/v1/finalize.json); if [[ \""'$a" == "$b" ]]; then print '"'workspacePath identical'; else print -r -- \""'$a'"\\n"'$b"; fi; a=$(jq -cS '"'.definitions.supportReport' astrid/core/rendering/schemas/v1/plan.json); b="'$(jq -cS '"'.definitions.supportReport' astrid/core/rendering/schemas/v1/finalize.json); c="'$(jq -cS '"'del(.\""'$schema", ."$id", .title, .examples)'"' astrid/core/rendering/schemas/v1/support.json); [[ \""'$a" == "$b" ]] && print '"'embedded supportReport identical'; [[ \""'$a" == "$c" ]] && print '"'embedded supportReport matches support.json' || { print 'supportReport differs'; print -r -- \""'$a'"\\n"'$c"; }' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
workspacePath identical
embedded supportReport identical
supportReport differs
{"additionalProperties":false,"properties":{"alternatives":{"items":{"$ref":"#/definitions/qualifiedId"},"type":"array","uniqueItems":true},"backend":{"$ref":"#/definitions/qualifiedId"},"backend_version":{"minLength":1,"pattern":"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$","type":["string","null"]},"features":{"additionalProperties":{"type":["boolean","string"]},"propertyNames":{"pattern":"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"},"type":"object"},"reasons":{"items":{"minLength":1,"pattern":"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$","type":"string"},"type":"array"},"schema_version":{"const":1,"type":"integer"},"supported":{"type":"boolean"}},"required":["schema_version","supported","reasons","features","alternatives","backend","backend_version"],"type":"object"}\n{"additionalProperties":false,"definitions":{"qualifiedId":{"pattern":"^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$","type":"string"}},"properties":{"alternatives":{"items":{"$ref":"#/definitions/qualifiedId"},"type":"array","uniqueItems":true},"backend":{"$ref":"#/definitions/qualifiedId"},"backend_version":{"minLength":1,"pattern":"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$","type":["string","null"]},"features":{"additionalProperties":{"type":["boolean","string"]},"propertyNames":{"pattern":"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"},"type":"object"},"reasons":{"items":{"minLength":1,"pattern":"^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$","type":"string"},"type":"array"},"schema_version":{"const":1,"type":"integer"},"supported":{"type":"boolean"}},"required":["schema_version","supported","reasons","features","alternatives","backend","backend_version"],"type":"object"}

codex
The independent schema pass found a real edge case worth reproducing: JSON Schema’s `$` anchor can treat the position before a final newline as end-of-string, while the DTO treats that newline as part of the last path component. I’m checking this directly against both validators before deciding the verdict.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import copy, json
from pathlib import Path
import jsonschema
from astrid.core.rendering.contracts import FinalizeRequest, parse_wire_result
schema_dir = Path(\"astrid/core/rendering/schemas/v1\")
fixture_dir = Path(\"tests/core/rendering/fixtures/v1\")
cases = [(\"result.json\", parse_wire_result, (\"video\", \"path\")), (\"finalize.json\", FinalizeRequest.from_dict, (\"artifacts\", 0, \"path\"))]
paths = [\"outputs/segment.mp4\", \"outputs\\n/segment.mp4\", \"outputs/\\n\", \"outputs/.\\n\", \"ok\\nsub/../evil.mp4\", \"ok\\nsub//evil.mp4\", \"ok\\nsub\\\\\\\\evil.mp4\"]
for schema_name, parser, path_bits in cases:
    schema = json.loads((schema_dir/schema_name).read_text())
    base = json.loads((fixture_dir/schema_name).read_text())
    validator = jsonschema.Draft7Validator(schema)
    print(schema_name)
    for candidate in paths:
        payload = copy.deepcopy(base)
        target = payload
        for bit in path_bits[:-1]: target = target[bit]
        target[path_bits[-1]] = candidate
        schema_ok = validator.is_valid(payload)
        try:
            parser(payload)
            dto_ok = True
        except Exception:
            dto_ok = False
        print(repr(candidate), \"schema=\", schema_ok, \"dto=\", dto_ok)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 144ms:
result.json
'outputs/segment.mp4' schema= True dto= True
'outputs\n/segment.mp4' schema= True dto= True
'outputs/\n' schema= False dto= True
'outputs/.\n' schema= False dto= True
'ok\nsub/../evil.mp4' schema= False dto= False
'ok\nsub//evil.mp4' schema= False dto= False
'ok\nsub\\\\evil.mp4' schema= False dto= False
finalize.json
'outputs/segment.mp4' schema= True dto= True
'outputs\n/segment.mp4' schema= True dto= True
'outputs/\n' schema= False dto= True
'outputs/.\n' schema= False dto= True
'ok\nsub/../evil.mp4' schema= False dto= False
'ok\nsub//evil.mp4' schema= False dto= False
'ok\nsub\\\\evil.mp4' schema= False dto= False

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from astrid.core.rendering.provenance import _normalize_artifact_profiles
ns = runpy.run_path(\"tests/core/rendering/test_contracts.py\")
a = ns[\"_video\"](path=\"outputs/a.mp4\")
b = ns[\"_video\"](path=\"outputs/b.mp4\")
for label, value, n in [
    (\"duplicate sequence overcount\", [a, a], 1),
    (\"duplicate-plus-extra sequence\", [a, a, b], 2),
    (\"absolute raw key\", {\"/tmp/escape.mp4\": {\"profile\": ns[\"_profile\"](), \"sha256\": ns[\"SHA_A\"], \"attachments\": {}}}, 1),
    (\"traversal raw key\", {\"../escape.mp4\": {\"profile\": ns[\"_profile\"](), \"sha256\": ns[\"SHA_A\"], \"attachments\": {}}}, 1),
    (\"nonstring raw key\", {1: {\"profile\": ns[\"_profile\"](), \"sha256\": ns[\"SHA_A\"], \"attachments\": {}}}, 1),
]:
    try:
        out = _normalize_artifact_profiles(value, segments=[object()] * n)
        print(label, \"ACCEPTED\", list(out))
    except Exception as exc:
        print(label, \"REJECTED\", type(exc).__name__, str(exc))
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 126ms:
duplicate sequence overcount ACCEPTED ['outputs/a.mp4']
duplicate-plus-extra sequence ACCEPTED ['outputs/a.mp4', 'outputs/b.mp4']
absolute raw key ACCEPTED ['/tmp/escape.mp4']
traversal raw key ACCEPTED ['../escape.mp4']
nonstring raw key ACCEPTED ['1']

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 pytest -q -p no:cacheprovider tests/core/rendering/test_schema_roundtrip.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 492ms:
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
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 pytest -q -s -p no:cacheprovider tests/core/rendering/test_schema_roundtrip.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 4 in 333ms:
ImportError while loading conftest '/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/conftest.py'.
tests/conftest.py:19: in <module>
    _pycache_prefix = Path(tempfile.mkdtemp(prefix="astrid-pycache-"))
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:374: in mkdtemp
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:127: in _sanitize_params
    dir = gettempdir()
          ^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:316: in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:309: in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
../../../.pyenv/versions/3.11.11/lib/python3.11/tempfile.py:224: in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
E   FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle']

exec
/bin/zsh -lc 'git diff --check 086d692..ab486f9 -- astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/plan.json astrid/core/rendering/schemas/v1/result.json docs/contracts/render-backend-v1.md tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc 'git diff --binary 086d692..ab486f9 | shasum -a 256; shasum -a 256 /tmp/batch1-r7.diff; head -n 5 /tmp/batch1-r7.diff; git diff --binary 086d692..ab486f9 | head -n 5' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
f0b76681acfbebd438dd8ec1577b087b5fbd52312e8644962f01628d133a09b3  -
f0b76681acfbebd438dd8ec1577b087b5fbd52312e8644962f01628d133a09b3  /tmp/batch1-r7.diff
diff --git a/.oracle/checkins/batch-1-r6.md b/.oracle/checkins/batch-1-r6.md
new file mode 100644
index 0000000..0b7ad46
--- /dev/null
+++ b/.oracle/checkins/batch-1-r6.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/.oracle/checkins/batch-1-r6.md b/.oracle/checkins/batch-1-r6.md
new file mode 100644
index 0000000..0b7ad46
--- /dev/null
+++ b/.oracle/checkins/batch-1-r6.md

exec
/bin/zsh -lc "rg -n \"artifact_profiles=.*\\[|artifact_profiles=\\[|artifact_profiles=None|artifact_profiles=\\{\\}|must record a hashed|positive render plan|VideoArtifact.path|artifact key\" tests/core/rendering/test_contracts.py; git show 086d692:tests/core/rendering/test_contracts.py | rg -n \"artifact_profiles=.*\\[|artifact_profiles=\\[|artifact_profiles=None|artifact_profiles=\\{\\}|must record a hashed|positive render plan|VideoArtifact.path|artifact key\"" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import copy, json
from pathlib import Path
import jsonschema
from astrid.core.rendering import RenderPlan
from astrid.core.rendering.contracts import FinalizeRequest
sd = Path(\"astrid/core/rendering/schemas/v1\")
fd = Path(\"tests/core/rendering/fixtures/v1\")
for name, parser, pth in [(\"plan.json\", RenderPlan.from_dict, (\"planner\", \"support_decision\", \"features\")), (\"finalize.json\", FinalizeRequest.from_dict, (\"plan\", \"planner\", \"support_decision\", \"features\"))]:
    schema = json.loads((sd/name).read_text()); base = json.loads((fd/name).read_text()); val = jsonschema.Draft7Validator(schema)
    print(name)
    for key in [\"ok\", \" \", \"bad\\x00key\", \"ok\\nkey\"]:
        x=copy.deepcopy(base); t=x
        for part in pth[:-1]: t=t[part]
        t[pth[-1]]={key: True}
        so=val.is_valid(x)
        try: parser(x); do=True
        except Exception: do=False
        print(repr(key), so, do)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 116ms:
plan.json
Traceback (most recent call last):
  File "<string>", line 15, in <module>
TypeError: 'NoneType' object does not support item assignment

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import copy, json
from pathlib import Path
import jsonschema
from astrid.core.rendering import RenderPlan
from astrid.core.rendering.contracts import FinalizeRequest
sd = Path(\"astrid/core/rendering/schemas/v1\")
fd = Path(\"tests/core/rendering/fixtures/v1\")
for name, parser, pth in [(\"plan.json\", RenderPlan.from_dict, (\"segments\", 0, \"renderer\", \"support_decision\", \"features\")), (\"finalize.json\", FinalizeRequest.from_dict, (\"plan\", \"segments\", 0, \"renderer\", \"support_decision\", \"features\"))]:
    schema = json.loads((sd/name).read_text()); base = json.loads((fd/name).read_text()); val = jsonschema.Draft7Validator(schema)
    print(name)
    for key in [\"ok\", \" \", \"bad\\x00key\", \"ok\\nkey\"]:
        x=copy.deepcopy(base); t=x
        for part in pth[:-1]: t=t[part]
        t[pth[-1]]={key: True}
        so=val.is_valid(x)
        try: parser(x); do=True
        except Exception: do=False
        print(repr(key), so, do)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 80ms:
plan.json
'ok' True True
' ' False False
'bad\x00key' False False
'ok\nkey' True True
finalize.json
'ok' True True
' ' False False
'bad\x00key' False False
'ok\nkey' True True

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '1680,1750p'; nl -ba astrid/core/foundation/atomic_io.py | sed -n '90,125p'; rg -n \"global.*attachment|globally unique|duplicate attachment|correspond one.for.one|ordered.*artifacts|one-for-one\" docs/contracts/render-backend-v1.md .oracle/briefs .oracle/plan.md -g '*.md' | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
    90	    try:
    91	        _write_atomic(Path(path), _write_text)
    92	    except OSError as exc:
    93	        raise AtomicWriteError(str(exc)) from exc
    94	
    95	
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
.oracle/plan.md:102:  - Gate: Python DTOs and raw JSON fixtures round-trip identically; unknown versions, invalid frame bounds, duplicate attachments, traversal, and backend attempts to overwrite core fields fail structurally.
docs/contracts/render-backend-v1.md:283:`RenderResult` has no second attachment map. Names must be globally unique
docs/contracts/render-backend-v1.md:392:and metadata. Artifacts correspond one-for-one with plan segments. A finalizer
docs/contracts/render-backend-v1.md:397:additional globally unique finalizer-created attachments are permitted.

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '275,405p'; rg -n \"provenance|artifact_profiles|artifact hashes\" .oracle/briefs/batch-1-r*.md | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   311	
   312	A fragment cannot contain any core result key, provenance v2 key, or v1
   313	compatibility key at its top level. Such a result is rejected rather than
   314	merged. Nested backend-private names are opaque to core. Logs must be redacted
   315	before they cross the wire; credentials, authorization headers, signed query
   316	strings, and secret environment values are forbidden.
   317	
   318	## Support reporting
   319	
   320	`SupportReport` contains:
   321	
   322	- required integer `schema_version: 1`;
   323	- `supported`, the request-sensitive verdict;
   324	- ordered human-readable `reasons`;
   325	- `features`, a string-keyed map of boolean or string evidence;
   326	- ordered unique qualified backend `alternatives`;
   327	- the qualified `backend` making the decision;
   328	- nullable `backend_version`.
   329	
   330	An unsupported report should contain at least one actionable reason. Support
   331	is evidence, not routing authority: fallback happens only when an explicit
   332	planner or fallback policy permits it. Static manifest capabilities never turn
   333	an unsupported report into support. Every segment's required report must name
   334	the same backend as the segment.
   335	
   336	## Planning
   337	
   338	`RenderPlan` is itself a versioned response. It contains required integer
   339	`schema_version: 1`, the SHA-256 `request_digest`, `requested_policy`, explicit
   340	`planner`, ordered `segments`, explicit `finalizer`, one canonical output
   341	`profile`, `total_frames`, `reasons`, and a nullable target `window`.
   342	
   343	`request_digest` is the SHA-256 of the canonical, JSON-normalized
   344	`RenderRequest` payload (sorted keys, no whitespace) that produced this plan.
   345	It is computed once by the planner/service and carried unchanged into
   346	provenance, replay bundles, and finalize requests so a replayed request can be
   347	verified byte-for-byte against the one that was planned.
   348	
   349	Resolution evidence has one canonical representation; ALL of the following
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
.oracle/briefs/batch-1-r2-t1.1.md:49:  cleanup, provenance, secret non-leak);
.oracle/briefs/batch-1-r2-t1.2.md:10:`astrid/core/rendering/{contracts,errors,provenance,registry}.py`,
.oracle/briefs/batch-1-r2-t1.2.md:52:`provenance.py` replaces the legacy `segments` key and overwrites nested
.oracle/briefs/batch-1-r2-t1.2.md:53:`segment_provenance` sidecars with `{engine,from,to}` projections, contradicting
.oracle/briefs/batch-1-r2-t1.2.md:58:  `segment_provenance` keep exactly the v1 shapes recorded in baseline.
.oracle/briefs/batch-1-r2-t1.2.md:65:- Include artifact hashes (per-segment video/attachments) in provenance.
.oracle/briefs/batch-1-r2-t1.2.md:96:- `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py` passes (v1 provenance shapes unchanged).
.oracle/briefs/batch-1-r2-t1.2.md:97:- `docs/contracts/render-backend-v1.md` reflects the corrected grammar + provenance v2 additive design.
.oracle/briefs/batch-1-r1-t1.4.md:14:`contracts.py`/`provenance.py`/`errors.py`/`schemas/` or
.oracle/briefs/batch-1-r1-t1.4.md:51:Do NOT modify `contracts.py`, `provenance.py`, `errors.py`, `schemas/`,
.oracle/briefs/batch-1-r1-t1.2.md:10:five issues. Your files: `astrid/core/rendering/{contracts,errors,provenance}.py`,
.oracle/briefs/batch-1-r1-t1.2.md:34:Current provenance has only singular `resolved_backend`, `source_pack`,
.oracle/briefs/batch-1-r1-t1.2.md:38:Rework: freeze explicit records in provenance v2 (in `provenance.py` and the
.oracle/briefs/batch-1-r1-t1.2.md:98:- `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py tests/core/rendering` passes (whole dir, all tests green, including your new versioning/topology/parity/attachment/provenance tests).

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import json, re
from pathlib import Path
from astrid.core.rendering.contracts import _require_workspace_relative_path
for name in [\"result.json\", \"finalize.json\"]:
 p=json.loads(Path(\"astrid/core/rendering/schemas/v1/\"+name).read_text())[\"definitions\"][\"workspacePath\"][\"pattern\"]
 print(name)
 for s in [\"a\\n\",\"a\\r\",\"a\\r\\n\",\"a/\\n\",\"a/\\r\",\"a/\\r\\n\",\"a/.\\n\",\"a/..\\n\",\"a\\n/..\",\"a\\r/..\",\"a\\r\\n/..\",\"a\\n//b\",\"a\\r//b\",\"a\\n/b\\\\c\",\"a\\r/b\\\\c\",\"a\\x0bb\",\"a\\x0cb\"]:
  so=bool(re.search(p,s))
  try: _require_workspace_relative_path(s,\"p\"); do=True
  except Exception: do=False
  if so "'!= do: print(repr(s), so, do)
'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 60ms:
result.json
'a/\n' False True
'a/.\n' False True
'a/..\n' False True
finalize.json
'a/\n' False True
'a/.\n' False True
'a/..\n' False True

exec
/bin/zsh -lc "sed -n '1,120p' .oracle/briefs/batch-1-r1-t1.2.md; git show 88c75f3:docs/contracts/render-backend-v1.md | sed -n '450,510p'; git show 88c75f3:astrid/core/rendering/provenance.py | nl -ba | sed -n '70,160p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
# Rework T1.2R — Fix contract/schema issues (oracle issues 3–7) [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

The Batch 1 oracle review found five issues in your T1.2 contracts/schemas
work. The full review is at `.oracle/checkins/batch-1.md`. Fix ONLY these
five issues. Your files: `astrid/core/rendering/{contracts,errors,provenance}.py`,
`astrid/core/rendering/schemas/v1/*.json`, `tests/core/rendering/`,
`docs/contracts/render-backend-v1.md`. Another agent is reworking baseline
characterization in parallel and must NOT touch these paths; a third agent
will fix pack validation + registry afterwards (do not touch
`astrid/core/pack/`).

## Issue 3 — Result-level attachments cannot cross the finalizer wire

`RenderResult` has attachments separate from `VideoArtifact.attachments`,
but `FinalizeRequest` carries only `list[VideoArtifact]` — a standalone
finalizer cannot preserve result-level attachments, and collisions across
segment artifacts are unchecked.

Rework: establish ONE authoritative attachment surface. Cleanest: make
`FinalizeRequest` carry complete per-segment result envelopes (segment
video artifact + its attachments + namespaced fragments) OR move all
attachments onto `VideoArtifact`. Enforce GLOBAL attachment name uniqueness
across segments and preservation through finalization, with round-trip
tests. Update `finalize.json` schema and `docs/contracts/render-backend-v1.md`
accordingly.

## Issue 4 — Provenance cannot represent routing/replay lineage

Current provenance has only singular `resolved_backend`, `source_pack`,
`manifest_digest` keys — a hybrid plan with MULTIPLE renderer invocations
cannot represent resolved identity per segment without collapsing evidence.

Rework: freeze explicit records in provenance v2 (in `provenance.py` and the
result/plan contracts):
- `planner`: `{id, source_pack, manifest_digest, trust_eligibility}`;
- `segments[]`: each with `{window, renderer: {id, source_pack,
  manifest_digest, alias_chain, override, support_decision},
  input_hashes}`;
- `finalizer`: `{id, source_pack, manifest_digest}`;
- top-level `request_digest` and `requested_policy`.
Derive all legacy v1 segment projections from validated frame windows (no
separate inconsistent segment representation). Keep every current v1
top-level projection. Update schemas + docs.

## Issue 5 — Unversioned wire responses + invalid plan topology

`SupportReport`, `RenderPlan`, and `RendererError` lack `schema_version` in
DTOs and schemas — contradicts the contract rule that V1 readers reject
unknown versions. And `RenderPlan` accepts invalid temporal topology.

Rework:
- Add `schema_version` to `SupportReport`, `RenderPlan`, `RendererError`
  (DTOs + schemas + the error branch of `result.json`). Readers must reject
  missing/unknown versions (tests: missing, boolean, malformed, unknown for
  EVERY operation: request, support, plan, finalize, result).
- `RenderPlan` validation: define total-frame/empty-plan semantics; validate
  segment ordering, coverage (segments tile the window/full timeline without
  gaps or overlaps), non-overlap, and canonical FPS consistency. Add tests.

## Issue 6 — JSON Schemas do not match DTOs

`plan.json`, `result.json`, `finalize.json` populated-audio profile branches
omit `required` — all three accept a profile with only `audio_codec: "aac"`
while `RenderProfile` rejects it. `result.json` also accepts contradictory
`video.audio` and top-level audio fields.

Rework:
- Align EVERY duplicated profile definition across schemas (extract a shared
  `profile` definition per schema file, or a `$ref` chain) so schema
  validation matches DTO validation exactly.
- Encode the expressible audio-ownership relationship (audio present in
  profile ⟺ audio ownership consistent; visual-only profile has no audio).
- Reject Windows drive-letter paths (`^[A-Za-z]:`) in artifact paths.
- Add canonical raw fixture JSONs (committed, minimal) for request/result/
  support/plan/finalize.
- Add adversarial schema-vs-DTO parity tests: for each schema, generate a
  battery of valid/invalid JSON cases and assert DTO parse/validation agrees.

## Issue 7 — FFmpeg finalizer ID contradicted and invalid

The plan/tasklist require `rendering.ffmpeg-finalizer`; the contract,
fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID
regex in `contracts.py` forbids the planned spelling.

Rework: resolve ONE canonical spelling. Under the frozen tasklist, the
canonical spelling is `rendering.ffmpeg-finalizer` — make the qualified-ID
validation accept it (id segments: `[a-z0-9][a-z0-9-]*` — hyphens allowed,
no underscores), and align EVERY DTO, schema, document, fixture, and test to
that spelling. Update `docs/contracts/render-backend-v1.md`.

## Acceptance

- `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py tests/core/rendering` passes (whole dir, all tests green, including your new versioning/topology/parity/attachment/provenance tests).
- `docs/contracts/render-backend-v1.md` reflects issues 3–7 fixes.

Run ONLY those commands. Do not run the full suite, formatters, or linters.
Do NOT modify `astrid/core/pack/`, `astrid/packs/`, production render code,
or files outside `astrid/core/rendering/`, `tests/core/rendering/`,
`docs/contracts/render-backend-v1.md`. Preserve all existing work. Report:
changes made, test results, the canonical finalizer ID you locked.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
alias/override evidence as renderer records; artifact hashes are recorded per
segment in the plan's `input_hashes` and in `artifact_profiles`.

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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
    70	    return result
    71	
    72	
    73	def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
    74	    """Derive one v1 segment projection from an authoritative v2 segment."""
    75	
    76	    numerator, denominator = segment.window.fps_rational
    77	    return {
    78	        "engine": segment.renderer.id.rsplit(".", 1)[-1],
    79	        "from": segment.window.start_frame * denominator / numerator,
    80	        "to": segment.window.end_frame * denominator / numerator,
    81	    }
    82	
    83	
    84	def _normalize_artifact_profiles(value: Any) -> Any:
    85	    if value is None:
    86	        return []
    87	    if isinstance(value, Mapping):
    88	        return {
    89	            str(key): (
    90	                profile
    91	                if isinstance(profile, RenderProfile)
    92	                else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
    93	            ).to_dict()
    94	            for key, profile in value.items()
    95	        }
    96	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
    97	        return [
    98	            (
    99	                profile
   100	                if isinstance(profile, RenderProfile)
   101	                else RenderProfile.from_dict(_json_safe_mapping(profile, label="artifact profile"))
   102	            ).to_dict()
   103	            for profile in value
   104	        ]
   105	    raise TypeError("artifact_profiles must be an object or array")
   106	
   107	
   108	def _normalize_v1_compatibility(
   109	    fields: Mapping[str, Any] | None,
   110	) -> dict[str, Any]:
   111	    if fields is None:
   112	        raise ValueError(
   113	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   114	        )
   115	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   116	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   117	    if unknown:
   118	        raise ValueError(
   119	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   120	            + ", ".join(unknown)
   121	        )
   122	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   123	    if missing:
   124	        raise ValueError(
   125	            "v1 compatibility projection is missing always-emitted fields: "
   126	            + ", ".join(missing)
   127	        )
   128	    return compatibility
   129	
   130	
   131	def assemble_provenance_v2(
   132	    *,
   133	    engine: str,
   134	    output: str | Path,
   135	    timeline: str | Path,
   136	    assets_registry: str | Path | None,
   137	    plan: RenderPlan | Mapping[str, Any],
   138	    artifact_profiles: Any = None,
   139	    audio_ownership: AudioOwnership | str | None = None,
   140	    normalization: Sequence[str] = (),
   141	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   142	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   143	    v1_compatibility: Mapping[str, Any] | None = None,
   144	) -> dict[str, Any]:
   145	    """Assemble additive provenance v2 with protected ownership boundaries.
   146	
   147	    ``engine`` is intentionally the legacy request projection. Routing and
   148	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   149	    hybrid invocation cannot collapse multiple renderer identities. Optional
   150	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   151	    any v2 core field.
   152	    """
   153	
   154	    legacy_engine = _require_string(engine, "engine")
   155	    output_path = _require_string(str(output), "output")
   156	    timeline_path = _require_string(str(timeline), "timeline")
   157	    assets_path = None if assets_registry is None else _require_string(
   158	        str(assets_registry), "assets_registry"
   159	    )
   160	    normalized_plan = (

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from dataclasses import object as nope
' 2>/dev/null || true
PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from astrid.core.rendering import Attachment, VideoArtifact
from astrid.core.rendering.provenance import assemble_provenance_v2
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
plan=ns[\"_plan\"](segments=[ns[\"_segment\"](0,24), ns[\"_segment\"](24,48)])
att=Attachment(name=\"alpha\",path=\"outputs/alpha.dat\",kind=\"alpha\",sha256=ns[\"SHA_C\"])
a=ns[\"_video\"](path=\"outputs/a.mp4\",duration_frames=24,attachments={\"alpha\":att})
b=ns[\"_video\"](path=\"outputs/b.mp4\",duration_frames=24,attachments={\"alpha\":att})
kw=dict(engine=\"hybrid\",output=\"out.mp4\",timeline=\"timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=ns[\"_compatibility\"]())
for label, val in [(\"ab\",[a,b]),(\"ba\",[b,a])]:
 try:
  out=assemble_provenance_v2(**kw,artifact_profiles=val)
  print(label,\"ACCEPTED\",list(out[\"artifact_profiles\"]),[list(v[\"attachments\"]) for v in out[\"artifact_profiles\"].values()])
 except Exception as e: print(label,\"REJECTED\",type(e).__name__,e)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 249ms:
ab ACCEPTED ['outputs/a.mp4', 'outputs/b.mp4'] [['alpha'], ['alpha']]
ba ACCEPTED ['outputs/b.mp4', 'outputs/a.mp4'] [['alpha'], ['alpha']]

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from astrid.core.rendering.provenance import assemble_provenance_v2
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
plan=ns[\"_plan\"](segments=[],total_frames=0,profile=ns[\"_profile\"](audio=False))
record={\"profile\":ns[\"_profile\"](),\"sha256\":ns[\"SHA_A\"],\"attachments\":{}}
kw=dict(engine=\"hybrid\",output=\"out.mp4\",timeline=\"timeline.json\",assets_registry=None,plan=plan,audio_ownership=None,normalization=[],attachments={},backend_fragments={},v1_compatibility=ns[\"_compatibility\"]())
for val in [None,{}, {\"out.mp4\":record}, [ns[\"_video\"]()]]:
 try: print(type(val).__name__,\"ACCEPTED\",assemble_provenance_v2(**kw,artifact_profiles=val)[\"artifact_profiles\"])
 except Exception as e: print(type(val).__name__,\"REJECTED\",type(e).__name__,e)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 146ms:
NoneType ACCEPTED {}
dict ACCEPTED {}
dict ACCEPTED {'out.mp4': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'attachments': {}}}
list ACCEPTED {'outputs/video.mp4': {'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'attachments': {}}}

exec
/bin/zsh -lc 'rg -n "zero.*artifact|empty.*artifact|artifact_profiles.*zero|zero-frame.*provenance|not finalized|positive plan" docs/contracts/render-backend-v1.md .oracle/checkins/batch-1-r6.md .oracle/checkins/batch-1-r5.md | tail -n 80' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
docs/contracts/render-backend-v1.md:373:`window: null`, no segments, and an empty reasons map; it is not finalized and
.oracle/checkins/batch-1-r6.md:1424:.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1425:.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1438:.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1439:.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:1782:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
.oracle/checkins/batch-1-r6.md:1793:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
.oracle/checkins/batch-1-r6.md:1923:+        # A positive plan must record a hashed artifact for every segment.
.oracle/checkins/batch-1-r6.md:2709:         _finalize(plan=empty, artifacts=[])
.oracle/checkins/batch-1-r6.md:2872:   108	        # A positive plan must record a hashed artifact for every segment.
.oracle/checkins/batch-1-r6.md:7889:   895	        _finalize(plan=empty, artifacts=[])
.oracle/checkins/batch-1-r6.md:8504:   262	        ("empty artifacts", _set(base, ("artifacts",), [])),
.oracle/checkins/batch-1-r6.md:8993:   373	`window: null`, no segments, and an empty reasons map; it is not finalized and
.oracle/checkins/batch-1-r6.md:9410:.oracle/checkins/batch-1-r6.md:1424:.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9411:.oracle/checkins/batch-1-r6.md:1425:.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9414:.oracle/checkins/batch-1-r6.md:1438:.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9415:.oracle/checkins/batch-1-r6.md:1439:.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9508:.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9509:.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9512:.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9513:.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9681:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9682:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9703:.oracle/checkins/batch-1-r4.md:15415:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9704:.oracle/checkins/batch-1-r4.md:15440:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r6.md:9970:16027:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
.oracle/checkins/batch-1-r6.md:9972:16038:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
.oracle/checkins/batch-1-r6.md:10174:   108	        # A positive plan must record a hashed artifact for every segment.
.oracle/checkins/batch-1-r5.md:1007:.oracle/checkins/batch-1-r3.md:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1011:.oracle/checkins/batch-1-r3.md:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1116:24176:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:1120:24201:1. **Resolution and artifact lineage remain incomplete.** [`_normalize_artifact_profiles()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84) serializes only `RenderProfile`; it never emits [`VideoArtifact.sha256`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:647) or per-segment attachment hashes. The provenance test still supplies a profile, while the new resolution test supplies an empty map. `input_hashes` describe inputs, not rendered artifacts.
.oracle/checkins/batch-1-r5.md:5134:   869	        _finalize(plan=empty, artifacts=[])
.oracle/checkins/batch-1-r5.md:5718: `window: null`, no segments, and an empty reasons map; it is not finalized and
.oracle/checkins/batch-1-r5.md:10451:Two closure claims are already under pressure from direct inspection: the provenance API still accepts missing/empty artifact lineage, and the standalone/embedded support schemas plus plan hash maps still lack the stated key constraints. I’m now proving the exact accepted counterexamples and checking whether any cumulative behavior makes those states legitimate.
.oracle/checkins/batch-1-r5.md:10716:   262	        ("empty artifacts", _set(base, ("artifacts",), [])),
.oracle/checkins/batch-1-r5.md:16027:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)
.oracle/checkins/batch-1-r5.md:16038:1. **Hashed artifact lineage remains optional and unbound.** `None` becomes `[]`, and `{}` is accepted for positive plans; an existing test preserves this bypass. Artifact keys are also not checked against `VideoArtifact.path`. [provenance.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:86) [test_contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_contracts.py:692)

exec
/bin/zsh -lc "rg -n \"assemble_provenance_v2|write_provenance_v2|artifact_profiles\" . --glob '"'!.git/**'"' --glob '"'!.oracle/checkins/**'"' --glob '"'!tests/core/rendering/test_contracts.py'"' --glob '"'!astrid/core/rendering/provenance.py'"' --glob '"'!docs/contracts/render-backend-v1.md'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
./astrid/core/rendering/contracts.py:65:        "artifact_profiles",
./astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '285,345p'; nl -ba astrid/core/rendering/contracts.py | sed -n '45,78p'; nl -ba docs/contracts/render-backend-v1.md | sed -n '460,495p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   479	hashed lineage record PER SEGMENT, each mapping a unique output path to
   480	exactly `{profile, sha256, attachments}` with a validated 64-hex string
   481	`sha256` on the artifact and every attachment `{path, kind, sha256}`.
   482	Attachment paths must be workspace-relative, kinds must match
   483	`[a-z][a-z0-9-]*`, and attachment map keys must equal the attachment's own
   484	name. Profile-only entries, null/malformed hashes, unknown or missing fields,
   485	path escapes, invalid kinds, and cardinality mismatches are all rejected.
   486	Sequence-form lineage requires VideoArtifacts so records stay path-keyed.
   487	Replay can verify rendered outputs byte-for-byte. `input_hashes` describe
   488	inputs only, never rendered outputs.
   489	
   490	`engine` is only the legacy request projection. The `segments` key keeps the
   491	V1-compatible flat projection: one `{engine, from, to}` entry per segment,
   492	derived from `renderer.id` and the validated integer `FrameWindow` at its
   493	rational FPS — exactly the shape legacy consumers read. The additive
   494	`segments_v2` key carries the complete normalized v2 segment records
   495	(`window`, `renderer` resolution, `input_hashes`); it never overwrites or

exec
/bin/zsh -lc "sed -n '1,90p' astrid/core/rendering/contracts.py; for f in astrid/core/rendering/schemas/v1/*.json; do print -- \"## "'$f"; rg -n '"'\"pattern\"' \""'$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
"""Language-neutral rendering protocol data transfer objects.

The JSON Schemas in :mod:`astrid.core.rendering.schemas.v1` are the wire
source of truth.  These frozen dataclasses are the small Python projection of
that contract; they deliberately contain no discovery, transport, or backend
execution behavior.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, Literal, NoReturn, TypeAlias

from astrid.core.foundation.hash import sha256_file
from astrid.core.io.cas import canonical_json_digest


SCHEMA_VERSION = 1

BackendConfig: TypeAlias = dict[str, dict[str, Any]]
RendererErrorKind: TypeAlias = Literal[
    "protocol",
    "unsupported",
    "binary_missing",
    "timeout",
    "interrupted",
    "invalid_artifact",
    "internal",
]

_QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")

RENDER_RESULT_CORE_KEYS = frozenset(
    {
        "schema_version",
        "video",
        "backend_fragments",
        "audio_ownership",
        "normalization",
        "logs",
        "metadata",
    }
)

PROVENANCE_V2_CORE_KEYS = frozenset(
    {
        "schema_version",
        "engine",
        "output",
        "timeline",
        "assets_registry",
        "request_digest",
        "requested_policy",
        "planner",
        "segments",
        "segments_v2",
        "artifact_profiles",
        "audio_ownership",
        "normalization",
        "finalizer",
        "attachments",
        "backend_fragments",
    }
)

PROVENANCE_V1_COMPATIBILITY_KEYS = frozenset(
    {
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
## astrid/core/rendering/schemas/v1/finalize.json
41:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
59:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
63:      "pattern": "^[0-9a-f]{64}$"
68:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
72:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
85:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
197:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
202:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
210:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
218:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
223:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
231:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
246:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
277:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
286:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
317:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
329:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
348:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
381:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
434:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
481:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
515:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
586:            "pattern": "^(0|[1-9][0-9]*)$"
591:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
655:          "pattern": "^[a-z][a-z0-9-]*$"
719:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
761:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
765:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/finalizer-manifest.json
26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
166:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
171:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/plan.json
53:        "pattern": "^(0|[1-9][0-9]*)$"
58:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
106:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
110:      "pattern": "^[0-9a-f]{64}$"
117:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
229:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
234:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
242:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
250:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
255:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
278:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
309:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
318:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
349:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
361:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
380:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
413:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
466:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
513:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
547:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/planner-manifest.json
26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
154:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
159:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/renderer-manifest.json
26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
147:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
160:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
165:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
179:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/request.json
20:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
28:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
32:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
104:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
151:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
258:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
271:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
279:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
284:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
292:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
307:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
338:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
347:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
365:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
369:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/result.json
16:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
20:      "pattern": "^[0-9a-f]{64}$"
25:      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
29:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
87:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
92:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
100:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
108:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
113:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
121:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
136:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
167:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
176:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
200:          "pattern": "^[a-z][a-z0-9-]*$"
264:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
356:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
362:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
366:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
489:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
497:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
## astrid/core/rendering/schemas/v1/support.json
29:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
41:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
60:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
66:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import copy,json
from pathlib import Path
import jsonschema
from astrid.core.rendering.contracts import parse_wire_result
sd=Path(\"astrid/core/rendering/schemas/v1/result.json\"); fd=Path(\"tests/core/rendering/fixtures/v1/result.json\")
schema=json.loads(sd.read_text()); base=json.loads(fd.read_text()); v=jsonschema.Draft7Validator(schema)
for field,value in [(\"keyname\",\"alpha\\n\"),(\"kind\",\"alpha\\n\"),(\"sha\",\"a\"*64+\"\\n\"),(\"path\",\"outputs/a\\n\")]:
 x=copy.deepcopy(base); a=x[\"video\"][\"attachments\"].pop(next(iter(x[\"video\"][\"attachments\"]))) if x[\"video\"][\"attachments\"] else {\"name\":\"alpha\",\"path\":\"outputs/a\",\"kind\":\"alpha\",\"sha256\":\"a\"*64}
 if field==\"keyname\": a[\"name\"]=value; x[\"video\"][\"attachments\"]={value:a}
 elif field==\"kind\": a[\"kind\"]=value; x[\"video\"][\"attachments\"]={a[\"name\"]:a}
 elif field==\"sha\": a[\"sha256\"]=value; x[\"video\"][\"attachments\"]={a[\"name\"]:a}
 else: a[\"path\"]=value; x[\"video\"][\"attachments\"]={a[\"name\"]:a}
 so=v.is_valid(x)
 try: parse_wire_result(x); do=True
 except Exception: do=False
 print(field,repr(value),so,do)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 111ms:
keyname 'alpha\n' True False
kind 'alpha\n' True False
sha 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n' True False
path 'outputs/a\n' True True

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import copy,json
from pathlib import Path
import jsonschema
from astrid.core.rendering import RenderRequest,RenderPlan,SupportReport
from astrid.core.rendering.contracts import FinalizeRequest,parse_wire_result,RendererManifest,PlannerManifest,FinalizerManifest
sd=Path(\"astrid/core/rendering/schemas/v1\"); fd=Path(\"tests/core/rendering/fixtures/v1\")
cases=[]
# (schema, parser, fixture source, path, appended value)
def add(n,p,src,path,val): cases.append((n,p,src,path,val))
add(\"request.json\",RenderRequest.from_dict,\"request.json\",(\"output_name\",),\"preview.mp4\\n\")
add(\"request.json\",RenderRequest.from_dict,\"request.json\",(\"backend_config\",),{\"acme.visual\\n\":{}})
add(\"plan.json\",RenderPlan.from_dict,\"plan.json\",(\"request_digest\",),\"d\"*64+\"\\n\")
add(\"plan.json\",RenderPlan.from_dict,\"plan.json\",(\"planner\",\"id\"),\"rendering.legacy_hybrid\\n\")
add(\"support.json\",SupportReport.from_dict,\"support.json\",(\"backend\",),\"acme.visual\\n\")
add(\"result.json\",parse_wire_result,\"result.json\",(\"video\",\"sha256\"),\"a\"*64+\"\\n\")
add(\"result.json\",parse_wire_result,\"result.json\",(\"backend_fragments\",),{\"acme.visual\\n\":{}})
add(\"finalize.json\",FinalizeRequest.from_dict,\"finalize.json\",(\"output_name\",),\"preview.mp4\\n\")
for n,p,src,path,val in cases:
 x=json.loads((fd/src).read_text()); t=x
 for b in path[:-1]: t=t[b]
 t[path[-1]]=val
 so=jsonschema.Draft7Validator(json.loads((sd/n).read_text())).is_valid(x)
 try:p(x);do=True
 except Exception:do=False
 print(n,path,so,do)
# manifests
for n,p in [(\"renderer-manifest.json\",RendererManifest.from_dict),(\"planner-manifest.json\",PlannerManifest.from_dict),(\"finalizer-manifest.json\",FinalizerManifest.from_dict)]:
 x=json.loads((sd/n).read_text())[\"examples\"][0]; x=copy.deepcopy(x); x[\"id\"] += \"\\n\"
 so=jsonschema.Draft7Validator(json.loads((sd/n).read_text())).is_valid(x)
 try:p(x);do=True
 except Exception:do=False
 print(n,(\"id\",),so,do)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 84ms:
request.json ('output_name',) True False
request.json ('backend_config',) True False
plan.json ('request_digest',) True False
plan.json ('planner', 'id') True False
support.json ('backend',) True False
result.json ('video', 'sha256') True False
result.json ('backend_fragments',) True False
finalize.json ('output_name',) True False
renderer-manifest.json ('id',) True False
planner-manifest.json ('id',) True False
finalizer-manifest.json ('id',) True False

exec
/bin/zsh -lc "rg -n \"absolute-end|terminal newline|trailing newline|newline.*qualified|newline.*sha|\\\\Z|end.of.string|output_name.*newline\" .oracle/checkins/batch-1*.md tests/core/rendering docs/contracts/render-backend-v1.md | tail -n 120" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
rg: regex parse error:
    (?:absolute-end|terminal newline|trailing newline|newline.*qualified|newline.*sha|\Z|end.of.string|output_name.*newline)
                                                                                      ^^
error: unrecognized escape sequence

exec
/bin/zsh -lc 'rg -n -e "absolute-end" -e "terminal newline" -e "trailing newline" -e "newline.*qualified" -e "newline.*sha" -e "end.of.string" -e "output_name.*newline" .oracle/checkins/batch-1*.md tests/core/rendering docs/contracts/render-backend-v1.md | tail -n 160' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/checkins/batch-1-r7.md:7459:The independent schema pass found a real edge case worth reproducing: JSON Schema’s `$` anchor can treat the position before a final newline as end-of-string, while the DTO treats that newline as part of the last path component. I’m checking this directly against both validators before deciding the verdict.
.oracle/checkins/batch-1-r7.md:8800:/bin/zsh -lc "rg -n \"absolute-end|terminal newline|trailing newline|newline.*qualified|newline.*sha|\\\\Z|end.of.string|output_name.*newline\" .oracle/checkins/batch-1*.md tests/core/rendering docs/contracts/render-backend-v1.md | tail -n 120" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r7.md:8803:    (?:absolute-end|terminal newline|trailing newline|newline.*qualified|newline.*sha|\Z|end.of.string|output_name.*newline)

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/request.json | sed -n '1,42p;140,160p'; nl -ba astrid/core/rendering/schemas/v1/plan.json | sed -n '96,120p'; nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '10,36p;188,206p'; nl -ba astrid/core/rendering/schemas/v1/support.json | sed -n '56,72p'; nl -ba astrid/core/rendering/schemas/v1/finalize.json | sed -n '34,80p;644,664p'; nl -ba astrid/core/rendering/schemas/v1/renderer-manifest.json | sed -n '106,118p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	{
     2	  "$schema": "http://json-schema.org/draft-07/schema#",
     3	  "$id": "https://astrid.local/schemas/rendering/v1/request.json",
     4	  "title": "Astrid render request v1",
     5	  "type": "object",
     6	  "additionalProperties": false,
     7	  "required": [
     8	    "schema_version",
     9	    "timeline_path",
    10	    "output_name"
    11	  ],
    12	  "properties": {
    13	    "schema_version": {
    14	      "type": "integer",
    15	      "const": 1
    16	    },
    17	    "timeline_path": {
    18	      "type": "string",
    19	      "minLength": 1,
    20	      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
    21	    },
    22	    "assets_registry_path": {
    23	      "type": [
    24	        "string",
    25	        "null"
    26	      ],
    27	      "minLength": 1,
    28	      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
    29	    },
    30	    "output_name": {
    31	      "type": "string",
    32	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
    33	      "not": {
    34	        "enum": [
    35	          ".",
    36	          ".."
    37	        ]
    38	      }
    39	    },
    40	    "window": {
    41	      "anyOf": [
    42	        {
   140	                "type": "null"
   141	              }
   142	            }
   143	          }
   144	        }
   145	      }
   146	    }
   147	  ],
   148	  "definitions": {
   149	    "qualifiedId": {
   150	      "type": "string",
   151	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
   152	    },
   153	    "audioOwnership": {
   154	      "type": "string",
   155	      "enum": [
   156	        "rendered",
   157	        "passthrough",
   158	        "none"
   159	      ]
   160	    },
    96	          "segments": {
    97	            "minItems": 1
    98	          }
    99	        }
   100	      }
   101	    }
   102	  ],
   103	  "definitions": {
   104	    "qualifiedId": {
   105	      "type": "string",
   106	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
   107	    },
   108	    "sha256": {
   109	      "type": "string",
   110	      "pattern": "^[0-9a-f]{64}$"
   111	    },
   112	    "requestedPolicy": {
   113	      "oneOf": [
   114	        {
   115	          "type": "string",
   116	          "minLength": 1,
   117	          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
   118	        },
   119	        {
   120	          "type": "object"
    10	      "$ref": "#/definitions/error"
    11	    }
    12	  ],
    13	  "definitions": {
    14	    "qualifiedId": {
    15	      "type": "string",
    16	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
    17	    },
    18	    "sha256": {
    19	      "type": "string",
    20	      "pattern": "^[0-9a-f]{64}$"
    21	    },
    22	    "workspacePath": {
    23	      "type": "string",
    24	      "minLength": 1,
    25	      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
    26	    },
    27	    "portableName": {
    28	      "type": "string",
    29	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
    30	      "not": {
    31	        "enum": [
    32	          ".",
    33	          ".."
    34	        ]
    35	      }
    36	    },
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
    56	        "string",
    57	        "null"
    58	      ],
    59	      "minLength": 1,
    60	      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*$"
    61	    }
    62	  },
    63	  "definitions": {
    64	    "qualifiedId": {
    65	      "type": "string",
    66	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
    67	    }
    68	  },
    69	  "examples": [
    70	    {
    71	      "schema_version": 1,
    72	      "supported": true,
    34	      "minItems": 1,
    35	      "items": {
    36	        "$ref": "#/definitions/videoArtifact"
    37	      }
    38	    },
    39	    "output_name": {
    40	      "type": "string",
    41	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
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
    59	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
    60	    },
    61	    "sha256": {
    62	      "type": "string",
    63	      "pattern": "^[0-9a-f]{64}$"
    64	    },
    65	    "workspacePath": {
    66	      "type": "string",
    67	      "minLength": 1,
    68	      "pattern": "^(?![A-Za-z]:)(?!/)(?!\\.{1,2}(?:/|$))(?![\\s\\S]*?/\\.{1,2}(?:/|$))(?![\\s\\S]*//)(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)(?![\\s\\S]*/$)[\\s\\S]*\\S[\\s\\S]*$"
    69	    },
    70	    "portableName": {
    71	      "type": "string",
    72	      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*$",
    73	      "not": {
    74	        "enum": [
    75	          ".",
    76	          ".."
    77	        ]
    78	      }
    79	    },
    80	    "requestedPolicy": {
   644	        "sha256"
   645	      ],
   646	      "properties": {
   647	        "name": {
   648	          "$ref": "#/definitions/portableName"
   649	        },
   650	        "path": {
   651	          "$ref": "#/definitions/workspacePath"
   652	        },
   653	        "kind": {
   654	          "type": "string",
   655	          "pattern": "^[a-z][a-z0-9-]*$"
   656	        },
   657	        "sha256": {
   658	          "$ref": "#/definitions/sha256"
   659	        }
   660	      }
   661	    },
   662	    "attachments": {
   663	      "type": "object",
   664	      "propertyNames": {
   106	      "default": {}
   107	    }
   108	  },
   109	  "additionalProperties": false,
   110	  "definitions": {
   111	    "qualifiedId": {
   112	      "type": "string",
   113	      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+$"
   114	    },
   115	    "permissions": {
   116	      "type": "array",
   117	      "items": {
   118	        "type": "string",

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from astrid.core.rendering import Attachment
from astrid.core.rendering.provenance import _normalize_attachments,_normalize_artifact_profiles
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
a=Attachment(name=\"alpha\",path=\"outputs/a\",kind=\"alpha\",sha256=\"a\"*64)
object.__setattr__(a,\"path\",\"../escape\")
object.__setattr__(a,\"kind\",\"Bad_Kind\")
object.__setattr__(a,\"sha256\",\"bad\")
for f,val in [(_normalize_attachments,{\"alpha\":a}),(_normalize_artifact_profiles,{\"out.mp4\":{\"profile\":ns[\"_profile\"](),\"sha256\":ns[\"SHA_A\"],\"attachments\":{\"alpha\":a}}})]:
 try:
  if f is _normalize_artifact_profiles: print(f.__name__,f(val,segments=[object()]))
  else: print(f.__name__,f(val))
 except Exception as e: print(f.__name__,\"REJECTED\",type(e).__name__,e)
for val in [[],False,0,\"\"]:
 try: print(\"top\",repr(val),_normalize_attachments(val))
 except Exception as e: print(\"top\",repr(val),\"REJECTED\",type(e).__name__,e)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 94ms:
_normalize_attachments {'alpha': {'name': 'alpha', 'path': '../escape', 'kind': 'Bad_Kind', 'sha256': 'bad'}}
_normalize_artifact_profiles REJECTED ValueError attachment kind must be a lowercase hyphenated token
top [] {}
top False {}
top 0 {}
top '' {}

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from astrid.core.rendering import Attachment
from astrid.core.rendering.provenance import _normalize_artifact_profiles
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
for attr,bad in [(\"path\",\"../escape\"),(\"kind\",\"Bad_Kind\"),(\"sha256\",\"bad\")]:
 a=Attachment(name=\"alpha\",path=\"outputs/a\",kind=\"alpha\",sha256=\"a\"*64); object.__setattr__(a,attr,bad)
 val={\"out.mp4\":{\"profile\":ns[\"_profile\"](),\"sha256\":ns[\"SHA_A\"],\"attachments\":{\"alpha\":a}}}
 try: print(attr,\"ACCEPTED\",_normalize_artifact_profiles(val,segments=[object()]))
 except Exception as e: print(attr,\"REJECTED\",type(e).__name__,e)
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 108ms:
path REJECTED ValueError attachment path must be a normalized contained workspace path
kind REJECTED ValueError attachment kind must be a lowercase hyphenated token
sha256 REJECTED ValueError attachment sha256 must be a lowercase 64-character SHA-256 digest

exec
/bin/zsh -lc "rg -n \"attachments=\" tests/core/rendering/test_contracts.py | sed -n '1,160p'; rg -n '\"attachments\"' docs/contracts/render-backend-v1.md | sed -n '1,160p'; git log -S '_normalize_attachments' --oneline -- astrid/core/rendering/provenance.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 84ms:
exec
/bin/zsh -lc "git show f8af4b2:astrid/core/rendering/provenance.py | nl -ba | sed -n '35,90p;120,220p'; git show f8af4b2:docs/contracts/render-backend-v1.md | rg -n \"Provenance ownership|attachments\" | tail -n 20" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
    35	def validate_backend_fragments(
    36	    fragments: Mapping[str, Mapping[str, Any]] | None,
    37	) -> dict[str, dict[str, Any]]:
    38	    """Validate namespaces and reject top-level core-key collisions."""
    39	
    40	    return _validate_backend_fragments(fragments or {})
    41	
    42	
    43	def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
    44	    if value is None:
    45	        return None
    46	    if isinstance(value, AudioOwnership):
    47	        return value.value
    48	    try:
    49	        return AudioOwnership(value).value
    50	    except (TypeError, ValueError) as exc:
    51	        raise ValueError(
    52	            "audio_ownership must be rendered, passthrough, none, or null"
    53	        ) from exc
    54	
    55	
    56	def _normalize_attachments(
    57	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None,
    58	) -> dict[str, Any]:
    59	    result: dict[str, Any] = {}
    60	    for raw_name, raw_attachment in (attachments or {}).items():
    61	        name = _require_string(raw_name, "attachment key")
    62	        attachment = (
    63	            raw_attachment
    64	            if isinstance(raw_attachment, Attachment)
    65	            else Attachment.from_dict(raw_attachment)
    66	        )
    67	        if attachment.name != name:
    68	            raise ValueError(
    69	                f"attachment key {name!r} must match attachment.name {attachment.name!r}"
    70	            )
    71	        if name in result:
    72	            raise ValueError(f"duplicate attachment name: {name}")
    73	        result[name] = attachment.to_dict()
    74	    return result
    75	
    76	
    77	def _segment_with_v1_projection(segment: RenderSegment | Mapping[str, Any]) -> dict[str, Any]:
    78	    """Return a normalized segment retaining legacy ``engine/from/to`` data."""
    79	
    80	    if isinstance(segment, RenderSegment):
    81	        payload = segment.to_dict()
    82	    else:
    83	        payload = _json_safe_mapping(segment, label="provenance segment")
    84	
    85	    window = payload.get("window")
    86	    backend = payload.get("backend")
    87	    if isinstance(window, Mapping) and isinstance(backend, str):
    88	        fps = window.get("fps_rational")
    89	        start_frame = window.get("start_frame")
    90	        end_frame = window.get("end_frame")
   120	        return [
   121	            profile.to_dict() if isinstance(profile, RenderProfile) else _json_safe(profile)
   122	            for profile in value
   123	        ]
   124	    raise TypeError("artifact_profiles must be an object or array")
   125	
   126	
   127	def _normalize_v1_compatibility(
   128	    fields: Mapping[str, Any] | None,
   129	) -> dict[str, Any]:
   130	    if fields is None:
   131	        raise ValueError(
   132	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   133	        )
   134	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   135	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   136	    if unknown:
   137	        raise ValueError(
   138	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   139	            + ", ".join(unknown)
   140	        )
   141	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   142	    if missing:
   143	        raise ValueError(
   144	            "v1 compatibility projection is missing always-emitted fields: "
   145	            + ", ".join(missing)
   146	        )
   147	    return compatibility
   148	
   149	
   150	def assemble_provenance_v2(
   151	    *,
   152	    engine: str,
   153	    output: str | Path,
   154	    timeline: str | Path,
   155	    assets_registry: str | Path | None,
   156	    requested_policy: str | Mapping[str, Any] | None,
   157	    resolved_backend: str | None,
   158	    source_pack: Mapping[str, Any] | None,
   159	    alias_chain: Sequence[str] = (),
   160	    override: Mapping[str, Any] | None = None,
   161	    trust_eligibility: Mapping[str, Any] | None = None,
   162	    manifest_digest: str | None = None,
   163	    support_decision: SupportReport | Mapping[str, Any] | None = None,
   164	    input_hashes: Mapping[str, str] | None = None,
   165	    segments: Sequence[RenderSegment | Mapping[str, Any]] = (),
   166	    artifact_profiles: Any = None,
   167	    audio_ownership: AudioOwnership | str | None = None,
   168	    normalization: Sequence[str] = (),
   169	    finalizer: str | None = None,
   170	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   171	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   172	    v1_compatibility: Mapping[str, Any] | None = None,
   173	) -> dict[str, Any]:
   174	    """Assemble additive provenance v2 with protected ownership boundaries.
   175	
   176	    ``engine`` is intentionally the legacy request projection.  The actual
   177	    selected implementation belongs in ``resolved_backend``.  Optional v1
   178	    fields are accepted only through ``v1_compatibility`` and cannot replace
   179	    any v2 core field.
   180	    """
   181	
   182	    legacy_engine = _require_string(engine, "engine")
   183	    output_path = _require_string(str(output), "output")
   184	    timeline_path = _require_string(str(timeline), "timeline")
   185	    assets_path = None if assets_registry is None else _require_string(
   186	        str(assets_registry), "assets_registry"
   187	    )
   188	    if isinstance(requested_policy, str):
   189	        normalized_policy: Any = _require_string(requested_policy, "requested_policy")
   190	    elif requested_policy is None:
   191	        normalized_policy = None
   192	    else:
   193	        normalized_policy = _json_safe_mapping(requested_policy, label="requested_policy")
   194	    normalized_backend = (
   195	        None
   196	        if resolved_backend is None
   197	        else _require_qualified_id(resolved_backend, "resolved_backend")
   198	    )
   199	    normalized_finalizer = (
   200	        None if finalizer is None else _require_qualified_id(finalizer, "finalizer")
   201	    )
   202	    aliases = [
   203	        _require_string(alias, f"alias_chain[{index}]")
   204	        for index, alias in enumerate(alias_chain)
   205	    ]
   206	    digest = None if manifest_digest is None else _require_sha256(
   207	        manifest_digest, "manifest_digest"
   208	    )
   209	    support = (
   210	        None
   211	        if support_decision is None
   212	        else support_decision.to_dict()
   213	        if isinstance(support_decision, SupportReport)
   214	        else _json_safe_mapping(support_decision, label="support_decision")
   215	    )
   216	    hashes = _require_string_mapping(input_hashes or {}, "input_hashes")
   217	    normalized_segments = [_segment_with_v1_projection(segment) for segment in segments]
   218	    normalized_normalization = [
   219	        _require_string(item, f"normalization[{index}]")
   220	        for index, item in enumerate(normalization)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
246:- optional named attachments (default `{}`).
274:attachments and their hashes unchanged but do not interpret them. A custom
280:`attachments`, qualified-ID-keyed `backend_fragments`, explicit
351:attachments it does not understand. The first built-in finalizer uses FFmpeg;
405:## Provenance ownership and v1 compatibility
413:`normalization`, `finalizer`, `attachments`, and `backend_fragments`.
528:18. **Primary video is required; attachments are extensible.** V1 planners and
529:    finalizers operate on a validated primary video. Optional named attachments

exec
/bin/zsh -lc "git show f8af4b2:astrid/core/rendering/provenance.py | nl -ba | sed -n '215,285p'; git show f8af4b2:docs/contracts/render-backend-v1.md | nl -ba | sed -n '400,440p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   215	    )
   216	    hashes = _require_string_mapping(input_hashes or {}, "input_hashes")
   217	    normalized_segments = [_segment_with_v1_projection(segment) for segment in segments]
   218	    normalized_normalization = [
   219	        _require_string(item, f"normalization[{index}]")
   220	        for index, item in enumerate(normalization)
   221	    ]
   222	
   223	    payload: dict[str, Any] = {
   224	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   225	        "engine": legacy_engine,
   226	        "output": output_path,
   227	        "timeline": timeline_path,
   228	        "assets_registry": assets_path,
   229	        "requested_policy": normalized_policy,
   230	        "resolved_backend": normalized_backend,
   231	        "source_pack": _json_safe_mapping(source_pack or {}, label="source_pack"),
   232	        "alias_chain": aliases,
   233	        "override": None
   234	        if override is None
   235	        else _json_safe_mapping(override, label="override"),
   236	        "trust_eligibility": _json_safe_mapping(
   237	            trust_eligibility or {}, label="trust_eligibility"
   238	        ),
   239	        "manifest_digest": digest,
   240	        "support_decision": support,
   241	        "input_hashes": hashes,
   242	        "segments": normalized_segments,
   243	        "artifact_profiles": _normalize_artifact_profiles(artifact_profiles),
   244	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   245	        "normalization": normalized_normalization,
   246	        "finalizer": normalized_finalizer,
   247	        "attachments": _normalize_attachments(attachments),
   248	        "backend_fragments": validate_backend_fragments(backend_fragments),
   249	    }
   250	    payload.update(_normalize_v1_compatibility(v1_compatibility))
   251	    return _json_safe_mapping(payload, label="provenance")
   252	
   253	
   254	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   255	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   256	
   257	    return assemble_provenance_v2(**kwargs)
   258	
   259	
   260	def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
   261	    """Assemble and atomically write a provenance v2 sidecar."""
   262	
   263	    payload = assemble_provenance_v2(**kwargs)
   264	    write_json_atomic(path, payload)
   265	    return payload
   266	
   267	
   268	def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
   269	    """Return stable SHA-256 input hashes using Astrid's shared helper."""
   270	
   271	    return {
   272	        _require_string(name, "input hash name"): sha256_file(Path(path))
   273	        for name, path in paths.items()
   274	    }
   275	
   276	
   277	def digest_manifest(path: str | Path) -> str:
   278	    """Return the SHA-256 digest used to pin one static manifest."""
   279	
   280	    return sha256_file(Path(path))
   281	
   282	
   283	__all__ = [
   284	    "CORE_OWNED_KEYS",
   285	    "PROVENANCE_SCHEMA_VERSION",
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   400	directories have one host owner and are cleaned on success, failure, timeout,
   401	and interruption. Cleanup must not follow an unvalidated path or delete
   402	unrelated prior output. A crash can leave an orphan video, but never a sidecar
   403	claiming an incomplete artifact; the sidecar is the publication commit marker.
   404	
   405	## Provenance ownership and v1 compatibility
   406	
   407	Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
   408	
   409	`schema_version`, `engine`, `output`, `timeline`, `assets_registry`,
   410	`requested_policy`, `resolved_backend`, `source_pack`, `alias_chain`,
   411	`override`, `trust_eligibility`, `manifest_digest`, `support_decision`,
   412	`input_hashes`, `segments`, `artifact_profiles`, `audio_ownership`,
   413	`normalization`, `finalizer`, `attachments`, and `backend_fragments`.
   414	
   415	`engine` is the legacy request projection, not the selected implementation.
   416	The authoritative selected qualified ID is `resolved_backend`. Segment records
   417	use the normalized v2 fields and also retain legacy `engine`, `from`, and `to`
   418	projections. `from`/`to` are derived from integer window frames and rational
   419	FPS; they never drive rendering.
   420	
   421	For the whole epic, core also preserves every current v1 top-level projection:
   422	
   423	`project_dir`, `composition_id`, `active_pack_order`, `active_theme`,
   424	`registry_hash`, `registry_state`, `resolved_effect_ids`, `resolved_effects`,
   425	`source_pack_ids`, `element_roots`, `staged_asset_ids`, `staged_asset_root`,
   426	optional `segment_provenance`, `ffmpeg_specialization`, and
   427	`audio_reactive_colour`, in addition to the already core-owned
   428	`schema_version`, `engine`, `output`, `timeline`, `assets_registry`, and
   429	`segments` names.
   430	
   431	The core assembler requires all historically always-emitted v1 fields on every
   432	call; it rejects a missing or partial compatibility projection. The three
   433	conditional fields (`segment_provenance`, `ffmpeg_specialization`, and
   434	`audio_reactive_colour`) remain conditional on the applicable render path.
   435	
   436	Backend-owned data appears only under `backend_fragments[qualified_id]`. Before
   437	assembly, core rejects a fragment whose top-level member collides with any v2
   438	or v1 core-owned name. Backends cannot replace routing, identity, inputs,
   439	segments, artifacts, audio, finalization, or compatibility projections.
   440	Provenance JSON is written with Astrid's atomic JSON helper; file and manifest

exec
/bin/zsh -lc "nl -ba .oracle/tasklist.md | sed -n '1,120p'; rg -n \"per-segment video|artifact hashes|provenance|attachments\" .oracle/plan.md .megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   106	- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
   107	- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
   108	- Targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.
   109	
   110	### Tasks
   111	
   112	- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
   113	- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
   114	- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
   115	- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
   116	- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
   117	- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
   118	- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
   119	
   120	## Batch 6 — Python SDK, conformance, and scaffold
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:24:provenance.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:29:registry internals, provenance implementation, or FFmpeg finalization path.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:47:  effect asset staging, subprocess execution, cleanup, and provenance live in
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:66:Existing hybrid test coverage is narrow: the provenance test patches the
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:105:15. Optional named render-result attachments so future compositors can consume
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:172:    passthrough/muxing, hashes, core provenance, cleanup, and replay metadata.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:173:    Backend authors return media plus a namespaced provenance fragment.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:180:18. **Primary video is required; attachments are extensible.** V1 planners and
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:181:    finalizers operate on a validated primary video. Optional named attachments
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:182:    are preserved in results and provenance but need not be interpreted by the
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:205:5. Which provenance-v1 fields must remain top-level for current consumers, and
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:211:   extraction, and where command/provenance parity is a better assertion than
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:261:  segment validation, and provenance modules, likely under
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:279:- Dedicated core contract/discovery/planner/segment/provenance tests, a fixture
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:291:   compatibility mapping, media/audio ownership, and provenance ownership.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:297:   planning, migrates callers, and closes parity/provenance/source-search gates.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:327:   valid provenance sidecar with reproducible backend resolution.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:338:    provenance, and failure behavior.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:341:    planner, project-ledger, provenance, cleanup, or finalization code.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:354:20. Optional result attachments survive validation, finalization, and
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:355:    provenance even when the default finalizer ignores their content.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:381:semantics, failure cleanup, and provenance consumers—not only the happy-path
.oracle/plan.md:37:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/plan.md:39:10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.
.oracle/plan.md:61:    - every currently emitted provenance field;
.oracle/plan.md:84:    - primary `VideoArtifact`, named attachments, and `RenderResult`;
.oracle/plan.md:86:    - provenance v2.
.oracle/plan.md:89:  - Require one primary video. Preserve uniquely named, contained attachments without requiring the default finalizer to understand them.
.oracle/plan.md:102:  - Gate: Python DTOs and raw JSON fixtures round-trip identically; unknown versions, invalid frame bounds, duplicate attachments, traversal, and backend attempts to overwrite core fields fail structurally.
.oracle/plan.md:154:  - Gate: local/cached/remote assets, Range requests, expired URLs, restricted serving, server-start failure, cleanup, invalid artifacts, visual-only modes, attachments, and crash-orphan recovery pass.
.oracle/plan.md:158:  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
.oracle/plan.md:169:  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
.oracle/plan.md:198:  - Gate: support diagnostics, command graphs, stream-copy, gaps/overlaps, track mute/volume, clip volume zero, fades, source bounds, missing streams/binaries, audio-reactive marker frames/hashes, cleanup, output validation, and provenance pass with a real FFmpeg render.
.oracle/plan.md:207:  - Record every normalization and preserve named attachments unchanged.
.oracle/plan.md:208:  - Gate: one-segment pass-through, compatible and incompatible multi-segment plans, 24/25/30 and rational FPS, missing audio/video, codec/time-base mismatch, duration mismatch, normalization provenance, and cleanup pass.
.oracle/plan.md:210:- [ ] **M1-08 — Add generic routing, flexible facade output, and provenance v2**
.oracle/plan.md:226:    - use existing input-placeholder expansion for `{out}/{output_name}` and `{out}/{output_name}.provenance.json`;
.oracle/plan.md:227:    - keep declared output names `video` and `provenance` stable;
.oracle/plan.md:233:  - Emit provenance v2 with:
.oracle/plan.md:240:    - input and artifact hashes/profiles;
.oracle/plan.md:242:    - normalization and attachments;
.oracle/plan.md:249:    `staged_asset_root`, `segments`, `segment_provenance`,
.oracle/plan.md:272:  - Preserve legacy `segments` and nested `segment_provenance` projections while adding normalized v2 segment records, including FFmpeg segments.
.oracle/plan.md:273:  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.
.oracle/plan.md:287:  | `video_editing/orchestrators/iteration_video/run.py` | Remove the concrete module import. Use its existing request project/run context to invoke the attached facade with `output_name=iteration.mp4`; eliminate the video-only rename. Declare and return `iteration.mp4.provenance.json`. |
.oracle/plan.md:313:    - provenance;
.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
.oracle/plan.md:361:  - Provide allocated output/work paths, descriptor-based local path/URL access, declared-permission checks, sanitized subprocess execution, redacted logging/progress, read-only interruption state, probing, hashing, completion, attachments, and cleanup.
.oracle/plan.md:418:  - Write the golden path: create → implement → test → static validate → trusted install/expose → smoke → inspect provenance.
.oracle/plan.md:421:  - Document trust, disclosure-only permissions, selection, aliases/overrides, backend configuration, assets, output/audio/attachments, cleanup, diagnostics, replay/redaction, and legacy selectors.
.oracle/plan.md:427:  - Run the complete matrix for raw-wire and SDK fixtures, trusted/untrusted discovery, built-ins, strict IDs, legacy selectors, aliases, overrides, hybrid planning, audio modes, attachments, failures, and replay.
.oracle/plan.md:436:- Kept the strict `extensions.rendering` approach, derived trust eligibility, additive provenance, semantic parity, and existing SDK/CLI conventions.
.oracle/plan.md:456:- External Reigh/upload/CAS provenance consumers remain unknown, so no v1 field removal belongs in this epic.
.oracle/plan.md:458:- Real Remotion rendering may remain unavailable in blocking CI, so props/provenance coverage and typechecking must remain strong and optional skips explicit.

exec
/bin/zsh -lc "nl -ba .oracle/plan.md | sed -n '228,278p'; nl -ba .megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md | sed -n '168,186p;348,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   228	    - rely on the existing inclusion of inputs in cache/CAS identity;
   229	    - add no new dynamic-output or dynamic-sentinel subsystem.
   230	  - Keep Hype’s real pipeline sentinel as `hype.mp4`, since Hype uses the default. Test non-default names through declared output resolution, pipeline propagation, and Arnold collection.
   231	  - Make `render/run.py` a thin facade adapter.
   232	  - Characterize the current argument-order shim, make facade parsing order-independent, then delete `_normalize_render_command_compat` if the compatibility test proves it unnecessary.
   233	  - Emit provenance v2 with:
   234	    - requested legacy selector/policy;
   235	    - resolved renderer/planner/finalizer;
   236	    - source pack/kind/revision and derived trust method;
   237	    - alias and override evidence;
   238	    - manifest and request digests;
   239	    - support decision and alternatives;
   240	    - input and artifact hashes/profiles;
   241	    - audio ownership/completion;
   242	    - normalization and attachments;
   243	    - backend-owned fragments.
   244	  - Preserve all currently emitted optional v1 keys where applicable:
   245	    `engine`, `output`, `timeline`, `assets_registry`, `project_dir`,
   246	    `composition_id`, `active_pack_order`, `active_theme`, `registry_hash`,
   247	    `registry_state`, `resolved_effect_ids`, `resolved_effects`,
   248	    `source_pack_ids`, `element_roots`, `staged_asset_ids`,
   249	    `staged_asset_root`, `segments`, `segment_provenance`,
   250	    `ffmpeg_specialization`, and `audio_reactive_colour`.
   251	  - Ensure plain FFmpeg, FFmpeg fast paths, audio-reactive, Remotion, and single-segment hybrid produce exactly one sidecar.
   252	  - Make previous-output cleanup lock-aware and conservative around corrupt/orphaned pairs; never delete unrelated output solely because a sidecar is unreadable.
   253	  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.
   254	
   255	- [ ] **M1-09 — Port hybrid to a generic planner/dispatcher**
   256	
   257	  - Extract legacy complexity/window planning as `rendering.legacy_hybrid`.
   258	  - Resolve canvas/FPS once from the canonical merged theme/timeline profile.
   259	  - Represent every segment as integer half-open frames.
   260	  - Preserve characterized transition `duration`/`durationFrames` and handle behavior.
   261	  - Retain effects, transitions, overlays, opacity, and fades while closing fatal gaps:
   262	    - speed changes;
   263	    - overlapping audio;
   264	    - unsupported non-media clips;
   265	    - strict-FFmpeg-invalid visual gaps/overlaps;
   266	    - controls rejected by the selected renderer’s support report.
   267	  - Permit FFmpeg track mute/volume after M1-06 proves exact support; fades continue to route away from FFmpeg.
   268	  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
   269	  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
   270	  - Remove recursive calls to `render()`. The dispatcher invokes plan entries only through `RenderService`.
   271	  - Add a deterministic mixed plan using the raw fixture renderer for one window and a built-in renderer for another.
   272	  - Preserve legacy `segments` and nested `segment_provenance` projections while adding normalized v2 segment records, including FFmpeg segments.
   273	  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.
   274	
   275	- [ ] **M1-10 — Migrate every production caller and remove stale resolution**
   276	
   277	  - Add one small attached-child invocation helper over existing executor/task primitives. It must:
   278	    - require a validated parent project/run ID and unique step ID;
   168	    custom finalizers are optional layers exposed only when needed.
   169	    Asynchronous remote jobs are explicitly deferred beyond V1.
   170	15. **Astrid owns plumbing.** Core services own asset resolution, temporary
   171	    workspace allocation, output probing and normalization, audio
   172	    passthrough/muxing, hashes, core provenance, cleanup, and replay metadata.
   173	    Backend authors return media plus a namespaced provenance fragment.
   174	16. **Static capabilities are coarse discovery hints, not the final verdict.**
   175	    A request-sensitive support probe returns structured supported/unsupported
   176	    features, reasons, and alternatives.
   177	17. **Failures are replayable.** Every failed backend invocation can retain or
   178	    emit a self-contained request bundle and exact replay command without
   179	    rerunning the editorial pipeline.
   180	18. **Primary video is required; attachments are extensible.** V1 planners and
   181	    finalizers operate on a validated primary video. Optional named attachments
   182	    are preserved in results and provenance but need not be interpreted by the
   183	    default finalizer.
   184	
   185	## Open questions for the planner
   186	
   348	    synthesizing an audio track inside the renderer.
   349	18. A failed fixture render produces or preserves a replay bundle containing
   350	    the resolved request, inputs, configuration, logs, partial result, and exact
   351	    replay command.
   352	19. A synthetic request-sensitive backend explains unsupported features and
   353	    planner alternatives rather than returning a bare boolean or exception.
   354	20. Optional result attachments survive validation, finalization, and
   355	    provenance even when the default finalizer ignores their content.
   356	21. Developer documentation demonstrates the path from scaffold to first
   357	    successful render, keeps advanced support probing and custom finalization
   358	    in separate progressive sections, and labels asynchronous jobs as deferred
   359	    beyond V1.
   360	

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 PYENV_VERSION=3.11.11 python -c '
import runpy
from astrid.core.rendering import Attachment
from astrid.core.rendering.provenance import assemble_provenance_v2
ns=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
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
