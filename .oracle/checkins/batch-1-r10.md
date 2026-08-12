Reading additional input from stdin...
2026-08-12T02:53:35.069924Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:53:35.070866Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:53:35.070871Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3e3-b68c-7d73-9011-1311018369ea
--------
user
# Megado Checkpoint — Batch 1 tenth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1..-r9 (3 each; -r4 had 4). Tenth rework
committed as `6acd4be` (prior head 788501c). Incremental diff at
/tmp/batch1-r10.diff.

## How each of your 2 re-review9 issues was addressed (host-implemented)

1. **VideoArtifact reconstruction bypassable** →
   - Sequence entries now reconstructed through `VideoArtifact.from_dict` at
     the boundary — a mutated artifact with smuggled `path="../escape.mp4"`
     is rejected (regression test added).
   - Mapping-form VideoArtifacts likewise reconstructed.
   - Lineage records always emit the VALIDATED workspace path (`key`), never
     the raw value — integer or mutated paths cannot leak into output.
2. **workspacePath still not DTO-equivalent** →
   - Whitespace-only-component checks now use `\s` (covers `\v`, `\f`, and
     Unicode spaces), and a leading whitespace-only component (`" /v.mp4"`)
     is rejected via a dedicated lookahead.
   - Cross-checked 16 DTO-vs-schema cases: 0 mismatches (includes `" /v.mp4"`,
     `dir/\v/v.mp4`, `dir/\f/v.mp4`, leading/trailing spaces, newlines,
     backslashes, `//`, `..`, drive letters, absolute paths).

## Evidence

- Incremental diff: /tmp/batch1-r10.diff (5 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 10 review rounds. The
contract is heavily validated and language-neutral. If sound and STABLE, say
exactly `PASS` so Batch 2 may begin.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` checkpoint guidance and the repository’s context-minimizing workflow. I’ll inspect only the incremental commit/diff and targeted contract tests, then independently verify the two claimed fixes before returning the binary verdict.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc "sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
The context workflow calls for keeping the audit trail out of the main thread, so I’m splitting the two fixes into independent read-only checks while I inspect the commit boundary and acceptance criteria here.
2026-08-12T02:54:11.647956Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:54:11.648178Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:54:11.648222Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:54:17.955844Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:54:17.956051Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T02:54:17.956065Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show -s --format='%H %P %s' 6acd4be && git diff --stat 788501c..6acd4be && git diff --check 788501c..6acd4be && sed -n '1,260p' /tmp/batch1-r10.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r10.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6acd4bea572e26c1553aa33768a558226358fc22
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6acd4bea572e26c1553aa33768a558226358fc22 788501c934fed0b0a85462418e77c021781681a9 batch1-rework10: oracle re-review9 issues 1-2 (VideoArtifact reconstruction via from_dict in both lineage forms, validated path emission, workspacePath \s whitespace components + leading-component rejection)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r9.md                 | 9184 ++++++++++++++++++++++++
 astrid/core/rendering/provenance.py            |   14 +-
 astrid/core/rendering/schemas/v1/finalize.json |    2 +-
 astrid/core/rendering/schemas/v1/result.json   |    2 +-
 tests/core/rendering/test_contracts.py         |   17 +-
 5 files changed, 9212 insertions(+), 7 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r9.md:254: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r9.md:255: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r9.md:257: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r9.md:2510: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r9.md:2511: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r9.md:2513: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r9.md:2566: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r9.md:2568: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r9.md:2570: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r9.md:2572: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2574: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2576: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2578: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2580: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2582: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2584: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2586: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2588: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2590: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2592: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2594: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2596: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2598: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2600: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2602: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2604: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2606: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2608: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2610: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2612: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2614: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2616: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2618: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2620: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2622: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2624: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2626: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2628: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2630: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2632: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2634: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2636: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2638: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2640: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2642: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2644: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2646: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2648: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2650: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2652: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2654: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2656: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2658: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2660: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2662: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2664: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2666: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2668: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2670: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2672: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2674: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2676: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2678: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2680: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2682: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2684: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2686: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2688: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2690: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2692: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2694: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2696: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2698: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2700: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2702: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2704: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2706: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2708: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2710: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2712: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2714: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2716: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2718: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2720: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2722: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2724: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2726: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2728: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2730: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2732: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2734: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2736: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2738: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2740: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2742: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2744: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2746: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2748: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2750: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2752: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2754: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2756: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2758: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2760: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2762: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2764: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2766: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2768: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2770: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2772: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r9.md:2774: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r9.md:2776: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r9.md:2778: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:2780: trailing whitespace.
++   730	
.oracle/checkins/batch-1-r9.md:2782: trailing whitespace.
++   731	
.oracle/checkins/batch-1-r9.md:2784: trailing whitespace.
++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-1-r9.md:2786: trailing whitespace.
++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-1-r9.md:2788: trailing whitespace.
++   453	
.oracle/checkins/batch-1-r9.md:2790: trailing whitespace.
++   461	
.oracle/checkins/batch-1-r9.md:2792: trailing whitespace.
++   463	
.oracle/checkins/batch-1-r9.md:2794: trailing whitespace.
++   465	
.oracle/checkins/batch-1-r9.md:2796: trailing whitespace.
++   470	
.oracle/checkins/batch-1-r9.md:2798: trailing whitespace.
++   492	
.oracle/checkins/batch-1-r9.md:2800: trailing whitespace.
++   520	
.oracle/checkins/batch-1-r9.md:2802: trailing whitespace.
++   539	
.oracle/checkins/batch-1-r9.md:2804: trailing whitespace.
++   540	
.oracle/checkins/batch-1-r9.md:2806: trailing whitespace.
++   550	
.oracle/checkins/batch-1-r9.md:2808: trailing whitespace.
++   551	
.oracle/checkins/batch-1-r9.md:2810: trailing whitespace.
++   609	
.oracle/checkins/batch-1-r9.md:2812: trailing whitespace.
++   613	
.oracle/checkins/batch-1-r9.md:2814: trailing whitespace.
++   614	
.oracle/checkins/batch-1-r9.md:2816: trailing whitespace.
++   627	
.oracle/checkins/batch-1-r9.md:2818: trailing whitespace.
++   628	
.oracle/checkins/batch-1-r9.md:2820: trailing whitespace.
++   631	
.oracle/checkins/batch-1-r9.md:2822: trailing whitespace.
++   640	
.oracle/checkins/batch-1-r9.md:2824: trailing whitespace.
++   641	
.oracle/checkins/batch-1-r9.md:2826: trailing whitespace.
++   647	
.oracle/checkins/batch-1-r9.md:2828: trailing whitespace.
++   648	
.oracle/checkins/batch-1-r9.md:2830: trailing whitespace.
++   679	
.oracle/checkins/batch-1-r9.md:2832: trailing whitespace.
++   689	
.oracle/checkins/batch-1-r9.md:2834: trailing whitespace.
++   721	
.oracle/checkins/batch-1-r9.md:2836: trailing whitespace.
++   722	
.oracle/checkins/batch-1-r9.md:2838: trailing whitespace.
++   740	
.oracle/checkins/batch-1-r9.md:2840: trailing whitespace.
++   741	
.oracle/checkins/batch-1-r9.md:2842: trailing whitespace.
++   777	
.oracle/checkins/batch-1-r9.md:2844: trailing whitespace.
++   778	
.oracle/checkins/batch-1-r9.md:2846: trailing whitespace.
++   792	
.oracle/checkins/batch-1-r9.md:2848: trailing whitespace.
++   793	
.oracle/checkins/batch-1-r9.md:2850: trailing whitespace.
++   809	
.oracle/checkins/batch-1-r9.md:2852: trailing whitespace.
++   810	
.oracle/checkins/batch-1-r9.md:2854: trailing whitespace.
++   904	
.oracle/checkins/batch-1-r9.md:2856: trailing whitespace.
++   905	
.oracle/checkins/batch-1-r9.md:2858: trailing whitespace.
++   965	
.oracle/checkins/batch-1-r9.md:2860: trailing whitespace.
++   966	
.oracle/checkins/batch-1-r9.md:2862: trailing whitespace.
++   975	
.oracle/checkins/batch-1-r9.md:2864: trailing whitespace.
++   976	
.oracle/checkins/batch-1-r9.md:2866: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r9.md:2868: trailing whitespace.
++     4	
.oracle/checkins/batch-1-r9.md:2870: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r9.md:2872: trailing whitespace.
++    11	
.oracle/checkins/batch-1-r9.md:2874: trailing whitespace.
++    28	
.oracle/checkins/batch-1-r9.md:2876: trailing whitespace.
++    29	
.oracle/checkins/batch-1-r9.md:2878: trailing whitespace.
++    32	
.oracle/checkins/batch-1-r9.md:2880: trailing whitespace.
++    33	
.oracle/checkins/batch-1-r9.md:2882: trailing whitespace.
++    38	
.oracle/checkins/batch-1-r9.md:2884: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r9.md:2886: trailing whitespace.
++    41	
.oracle/checkins/batch-1-r9.md:2888: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r9.md:2890: trailing whitespace.
++    54	
.oracle/checkins/batch-1-r9.md:2892: trailing whitespace.
++    81	
.oracle/checkins/batch-1-r9.md:2894: trailing whitespace.
++    82	
.oracle/checkins/batch-1-r9.md:2896: trailing whitespace.
++    85	
.oracle/checkins/batch-1-r9.md:2898: trailing whitespace.
++    92	
.oracle/checkins/batch-1-r9.md:2900: trailing whitespace.
++    93	
.oracle/checkins/batch-1-r9.md:2902: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r9.md:2904: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r9.md:2906: trailing whitespace.
++   168	
.oracle/checkins/batch-1-r9.md:2908: trailing whitespace.
++   169	
.oracle/checkins/batch-1-r9.md:2910: trailing whitespace.
++   236	
.oracle/checkins/batch-1-r9.md:2912: trailing whitespace.
++   237	
.oracle/checkins/batch-1-r9.md:2914: trailing whitespace.
++   248	
.oracle/checkins/batch-1-r9.md:2916: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r9.md:2918: trailing whitespace.
++   271	
.oracle/checkins/batch-1-r9.md:2920: trailing whitespace.
++   272	
.oracle/checkins/batch-1-r9.md:2922: trailing whitespace.
++   288	
.oracle/checkins/batch-1-r9.md:2924: trailing whitespace.
++   295	
.oracle/checkins/batch-1-r9.md:2926: trailing whitespace.
++   316	
.oracle/checkins/batch-1-r9.md:2928: trailing whitespace.
++   343	
.oracle/checkins/batch-1-r9.md:2930: trailing whitespace.
++   344	
.oracle/checkins/batch-1-r9.md:2932: trailing whitespace.
++   347	
.oracle/checkins/batch-1-r9.md:2934: trailing whitespace.
++   349	
.oracle/checkins/batch-1-r9.md:2936: trailing whitespace.
++   350	
.oracle/checkins/batch-1-r9.md:2938: trailing whitespace.
++   353	
.oracle/checkins/batch-1-r9.md:2940: trailing whitespace.
++   357	
.oracle/checkins/batch-1-r9.md:2942: trailing whitespace.
++   358	
.oracle/checkins/batch-1-r9.md:2944: trailing whitespace.
++   361	
.oracle/checkins/batch-1-r9.md:2946: trailing whitespace.
++   366	
.oracle/checkins/batch-1-r9.md:2948: trailing whitespace.
++   367	
.oracle/checkins/batch-1-r9.md:2950: trailing whitespace.
++   370	
.oracle/checkins/batch-1-r9.md:2952: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r9.md:2954: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r9.md:2956: trailing whitespace.
++    10	
.oracle/checkins/batch-1-r9.md:2958: trailing whitespace.
++    18	
.oracle/checkins/batch-1-r9.md:2960: trailing whitespace.
++    21	
.oracle/checkins/batch-1-r9.md:2962: trailing whitespace.
++    22	
.oracle/checkins/batch-1-r9.md:2964: trailing whitespace.
++    24	
.oracle/checkins/batch-1-r9.md:2966: trailing whitespace.
++    35	
.oracle/checkins/batch-1-r9.md:2968: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r9.md:2970: trailing whitespace.
++    52	
.oracle/checkins/batch-1-r9.md:2972: trailing whitespace.
++    73	
.oracle/checkins/batch-1-r9.md:2974: trailing whitespace.
++    93	
.oracle/checkins/batch-1-r9.md:2976: trailing whitespace.
++   110	
.oracle/checkins/batch-1-r9.md:2978: trailing whitespace.
++   123	
.oracle/checkins/batch-1-r9.md:2980: trailing whitespace.
++   130	
.oracle/checkins/batch-1-r9.md:2982: trailing whitespace.
++   131	
.oracle/checkins/batch-1-r9.md:2984: trailing whitespace.
++   134	
.oracle/checkins/batch-1-r9.md:2986: trailing whitespace.
++   158	
.oracle/checkins/batch-1-r9.md:2988: trailing whitespace.
++   159	
.oracle/checkins/batch-1-r9.md:2990: trailing whitespace.
++   165	
.oracle/checkins/batch-1-r9.md:2992: trailing whitespace.
++   166	
.oracle/checkins/batch-1-r9.md:2994: trailing whitespace.
++   171	
.oracle/checkins/batch-1-r9.md:2996: trailing whitespace.
++   172	
.oracle/checkins/batch-1-r9.md:2998: trailing whitespace.
++   186	
.oracle/checkins/batch-1-r9.md:3000: trailing whitespace.
++   187	
.oracle/checkins/batch-1-r9.md:3002: trailing whitespace.
++   194	
.oracle/checkins/batch-1-r9.md:3004: trailing whitespace.
++   195	
.oracle/checkins/batch-1-r9.md:3006: trailing whitespace.
++   205	
.oracle/checkins/batch-1-r9.md:3008: trailing whitespace.
++   206	
.oracle/checkins/batch-1-r9.md:3010: trailing whitespace.
++   209	
.oracle/checkins/batch-1-r9.md:3012: trailing whitespace.
++   215	
.oracle/checkins/batch-1-r9.md:3014: trailing whitespace.
++   216	
.oracle/checkins/batch-1-r9.md:3016: trailing whitespace.
++   225	
.oracle/checkins/batch-1-r9.md:3018: trailing whitespace.
++   226	
.oracle/checkins/batch-1-r9.md:3020: trailing whitespace.
++   231	
.oracle/checkins/batch-1-r9.md:3022: trailing whitespace.
++   232	
.oracle/checkins/batch-1-r9.md:3024: trailing whitespace.
++   241	
.oracle/checkins/batch-1-r9.md:3026: trailing whitespace.
++   242	
.oracle/checkins/batch-1-r9.md:3028: trailing whitespace.
++   248	
.oracle/checkins/batch-1-r9.md:3030: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r9.md:3032: trailing whitespace.
++   507	
.oracle/checkins/batch-1-r9.md:3034: trailing whitespace.
++   511	
.oracle/checkins/batch-1-r9.md:3036: trailing whitespace.
++   530	
.oracle/checkins/batch-1-r9.md:3038: trailing whitespace.
++   563	
.oracle/checkins/batch-1-r9.md:3040: trailing whitespace.
++   564	
.oracle/checkins/batch-1-r9.md:3042: trailing whitespace.
++   571	
.oracle/checkins/batch-1-r9.md:3044: trailing whitespace.
++   576	
.oracle/checkins/batch-1-r9.md:3046: trailing whitespace.
++   582	
.oracle/checkins/batch-1-r9.md:3048: trailing whitespace.
++   583	
.oracle/checkins/batch-1-r9.md:3050: trailing whitespace.
++   587	
.oracle/checkins/batch-1-r9.md:3052: trailing whitespace.
++   592	
.oracle/checkins/batch-1-r9.md:3054: trailing whitespace.
++   604	
.oracle/checkins/batch-1-r9.md:3056: trailing whitespace.
++   609	
.oracle/checkins/batch-1-r9.md:3058: trailing whitespace.
++   621	
.oracle/checkins/batch-1-r9.md:3060: trailing whitespace.
++   633	
.oracle/checkins/batch-1-r9.md:3062: trailing whitespace.
++   634	
.oracle/checkins/batch-1-r9.md:3064: trailing whitespace.
++   655	
.oracle/checkins/batch-1-r9.md:3066: trailing whitespace.
++   656	
.oracle/checkins/batch-1-r9.md:3068: trailing whitespace.
++   660	
.oracle/checkins/batch-1-r9.md:3070: trailing whitespace.
++   667	
.oracle/checkins/batch-1-r9.md:3072: trailing whitespace.
++   690	
.oracle/checkins/batch-1-r9.md:3074: trailing whitespace.
++   702	
.oracle/checkins/batch-1-r9.md:3076: trailing whitespace.
++   717	
.oracle/checkins/batch-1-r9.md:3078: trailing whitespace.
++  1662	
.oracle/checkins/batch-1-r9.md:3080: trailing whitespace.
++  1686	
.oracle/checkins/batch-1-r9.md:3082: trailing whitespace.
++  1693	
.oracle/checkins/batch-1-r9.md:3084: trailing whitespace.
++  1694	
.oracle/checkins/batch-1-r9.md:3086: trailing whitespace.
++  1698	
.oracle/checkins/batch-1-r9.md:3088: trailing whitespace.
++  1705	
.oracle/checkins/batch-1-r9.md:3090: trailing whitespace.
++  1753	
.oracle/checkins/batch-1-r9.md:3092: trailing whitespace.
++  1757	
.oracle/checkins/batch-1-r9.md:3094: trailing whitespace.
++  1763	
.oracle/checkins/batch-1-r9.md:3096: trailing whitespace.
++  1769	
.oracle/checkins/batch-1-r9.md:3098: trailing whitespace.
++  1773	
.oracle/checkins/batch-1-r9.md:3100: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r9.md:3102: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r9.md:3104: trailing whitespace.
++    11	
.oracle/checkins/batch-1-r9.md:3106: trailing whitespace.
++    20	
.oracle/checkins/batch-1-r9.md:3108: trailing whitespace.
++    21	
.oracle/checkins/batch-1-r9.md:3110: trailing whitespace.
++    48	
.oracle/checkins/batch-1-r9.md:3112: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r9.md:3114: trailing whitespace.
++    52	
.oracle/checkins/batch-1-r9.md:3116: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r9.md:3118: trailing whitespace.
++    56	
.oracle/checkins/batch-1-r9.md:3120: trailing whitespace.
++    57	
.oracle/checkins/batch-1-r9.md:3122: trailing whitespace.
++    60	
.oracle/checkins/batch-1-r9.md:3124: trailing whitespace.
++    61	
.oracle/checkins/batch-1-r9.md:3126: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r9.md:3128: trailing whitespace.
++    73	
.oracle/checkins/batch-1-r9.md:3130: trailing whitespace.
++    81	
.oracle/checkins/batch-1-r9.md:3132: trailing whitespace.
++    88	
.oracle/checkins/batch-1-r9.md:3134: trailing whitespace.
++    89	
.oracle/checkins/batch-1-r9.md:3136: trailing whitespace.
++    96	
.oracle/checkins/batch-1-r9.md:3138: trailing whitespace.
++    97	
.oracle/checkins/batch-1-r9.md:3140: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r9.md:3142: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r9.md:3144: trailing whitespace.
++   113	
.oracle/checkins/batch-1-r9.md:3146: trailing whitespace.
++   114	
.oracle/checkins/batch-1-r9.md:3148: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r9.md:3150: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r9.md:3152: trailing whitespace.
++   324	
.oracle/checkins/batch-1-r9.md:3154: trailing whitespace.
++   325	
.oracle/checkins/batch-1-r9.md:3156: trailing whitespace.
++   338	
.oracle/checkins/batch-1-r9.md:3158: trailing whitespace.
++   339	
.oracle/checkins/batch-1-r9.md:3160: trailing whitespace.
++   356	
.oracle/checkins/batch-1-r9.md:3162: trailing whitespace.
++   357	
.oracle/checkins/batch-1-r9.md:3164: trailing whitespace.
++   375	
.oracle/checkins/batch-1-r9.md:3166: trailing whitespace.
++   376	
.oracle/checkins/batch-1-r9.md:3168: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3170: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3172: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3174: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3176: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3178: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3180: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3182: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3184: trailing whitespace.
++ 
.oracle/checkins/batch-1-r9.md:3186: trailing whitespace.
++   809	
.oracle/checkins/batch-1-r9.md:3188: trailing whitespace.
++   810	
.oracle/checkins/batch-1-r9.md:3190: trailing whitespace.
++   904	
.oracle/checkins/batch-1-r9.md:3192: trailing whitespace.
++   905	
.oracle/checkins/batch-1-r9.md:3194: trailing whitespace.
++   965	
.oracle/checkins/batch-1-r9.md:3196: trailing whitespace.
++   966	
.oracle/checkins/batch-1-r9.md:3198: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r9.md:3200: trailing whitespace.
++     4	
.oracle/checkins/batch-1-r9.md:3202: trailing whitespace.
++     6	
.oracle/checkins/batch-1-r9.md:3204: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r9.md:3206: trailing whitespace.
++    17	
.oracle/checkins/batch-1-r9.md:3208: trailing whitespace.
++    19	
.oracle/checkins/batch-1-r9.md:3210: trailing whitespace.
++    25	
.oracle/checkins/batch-1-r9.md:3212: trailing whitespace.
++    27	
.oracle/checkins/batch-1-r9.md:3214: trailing whitespace.
++    29	
.oracle/checkins/batch-1-r9.md:3216: trailing whitespace.
++    31	
.oracle/checkins/batch-1-r9.md:3218: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r9.md:3220: trailing whitespace.
++    42	
.oracle/checkins/batch-1-r9.md:3222: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r9.md:3224: trailing whitespace.
++    51	
.oracle/checkins/batch-1-r9.md:3226: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r9.md:3228: trailing whitespace.
++    55	
.oracle/checkins/batch-1-r9.md:3230: trailing whitespace.
++    63	
.oracle/checkins/batch-1-r9.md:3232: trailing whitespace.
++    65	
.oracle/checkins/batch-1-r9.md:3234: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r9.md:3236: trailing whitespace.
++    74	
.oracle/checkins/batch-1-r9.md:3238: trailing whitespace.
++    76	
.oracle/checkins/batch-1-r9.md:3240: trailing whitespace.
++    78	
.oracle/checkins/batch-1-r9.md:3242: trailing whitespace.
++   131	
.oracle/checkins/batch-1-r9.md:3244: trailing whitespace.
++   132	
.oracle/checkins/batch-1-r9.md:3246: trailing whitespace.
++   162	
.oracle/checkins/batch-1-r9.md:3248: trailing whitespace.
++   163	
.oracle/checkins/batch-1-r9.md:3250: trailing whitespace.
++   178	
.oracle/checkins/batch-1-r9.md:3252: trailing whitespace.
++   179	
.oracle/checkins/batch-1-r9.md:3254: trailing whitespace.
++   206	
.oracle/checkins/batch-1-r9.md:3256: trailing whitespace.
++   207	
.oracle/checkins/batch-1-r9.md:3258: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r9.md:3260: trailing whitespace.
++   250	
.oracle/checkins/batch-1-r9.md:3262: trailing whitespace.
++   288	
.oracle/checkins/batch-1-r9.md:3264: trailing whitespace.
++   289	
.oracle/checkins/batch-1-r9.md:3266: trailing whitespace.
++   302	
.oracle/checkins/batch-1-r9.md:3268: trailing whitespace.
++   303	
.oracle/checkins/batch-1-r9.md:3270: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r9.md:3272: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r9.md:3274: trailing whitespace.
++   330	
.oracle/checkins/batch-1-r9.md:3276: trailing whitespace.
++   331	
.oracle/checkins/batch-1-r9.md:3278: trailing whitespace.
++   343	
.oracle/checkins/batch-1-r9.md:3280: trailing whitespace.
++   344	
.oracle/checkins/batch-1-r9.md:3282: trailing whitespace.
++   288	
.oracle/checkins/batch-1-r9.md:3284: trailing whitespace.
++    98	
.oracle/checkins/batch-1-r9.md:3286: trailing whitespace.
++   101	
.oracle/checkins/batch-1-r9.md:3288: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r9.md:3290: trailing whitespace.
++   107	
.oracle/checkins/batch-1-r9.md:3292: trailing whitespace.
++   110	
.oracle/checkins/batch-1-r9.md:3294: trailing whitespace.
++   113	
.oracle/checkins/batch-1-r9.md:3296: trailing whitespace.
++  1349	
.oracle/checkins/batch-1-r9.md:3298: trailing whitespace.
++  1350	
.oracle/checkins/batch-1-r9.md:3300: trailing whitespace.
++  1354	
.oracle/checkins/batch-1-r9.md:3302: trailing whitespace.
++  1365	
.oracle/checkins/batch-1-r9.md:3304: trailing whitespace.
++  1444	
.oracle/checkins/batch-1-r9.md:3306: trailing whitespace.
++  1460	
.oracle/checkins/batch-1-r9.md:3376: trailing whitespace.
+  1444	
.oracle/checkins/batch-1-r9.md:3392: trailing whitespace.
+  1460	
.oracle/checkins/batch-1-r9.md:4656: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4657: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4662: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4664: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4665: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4677: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4678: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4705: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4706: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4709: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4716: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4717: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4729: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4730: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4797: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4798: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4874: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4875: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4886: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4887: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4909: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4910: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4926: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4933: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4955: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4982: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4983: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4986: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4988: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4989: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4992: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4996: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:4997: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5000: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5005: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5006: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5009: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5011: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5012: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5037: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5039: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5041: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5050: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5059: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5063: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5065: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5067: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5082: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5090: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5092: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5094: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5099: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5134: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5144: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5146: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5154: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5159: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5169: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5171: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5174: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5184: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5191: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5193: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5203: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5207: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5209: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5221: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5222: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5226: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5227: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5245: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5246: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5251: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5252: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5271: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5272: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5282: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5283: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5357: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5361: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5362: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5375: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5376: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5379: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5388: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5389: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5395: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5396: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5427: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5437: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5485: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5486: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5504: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5505: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5541: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5542: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5556: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5557: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5573: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5574: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5677: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5678: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5778: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5779: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5788: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5789: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5807: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5808: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5814: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5815: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5826: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5827: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5843: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5844: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5849: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:5850: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:6046: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r9.md:6048: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r9.md:6052: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r9.md:6055: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r9.md:6072: trailing whitespace.
+    28	
.oracle/checkins/batch-1-r9.md:6073: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r9.md:6076: trailing whitespace.
+    32	
.oracle/checkins/batch-1-r9.md:6077: trailing whitespace.
+    33	
.oracle/checkins/batch-1-r9.md:6082: trailing whitespace.
+    38	
.oracle/checkins/batch-1-r9.md:6084: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r9.md:6085: trailing whitespace.
+    41	
.oracle/checkins/batch-1-r9.md:6097: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r9.md:6098: trailing whitespace.
+    54	
.oracle/checkins/batch-1-r9.md:6125: trailing whitespace.
+    81	
.oracle/checkins/batch-1-r9.md:6126: trailing whitespace.
+    82	
.oracle/checkins/batch-1-r9.md:6129: trailing whitespace.
+    85	
.oracle/checkins/batch-1-r9.md:6136: trailing whitespace.
+    92	
.oracle/checkins/batch-1-r9.md:6137: trailing whitespace.
+    93	
.oracle/checkins/batch-1-r9.md:6149: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r9.md:6150: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r9.md:6217: trailing whitespace.
+   173	
.oracle/checkins/batch-1-r9.md:6218: trailing whitespace.
+   174	
.oracle/checkins/batch-1-r9.md:6292: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r9.md:6293: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r9.md:6304: trailing whitespace.
+   260	
.oracle/checkins/batch-1-r9.md:6305: trailing whitespace.
+   261	
.oracle/checkins/batch-1-r9.md:6327: trailing whitespace.
+   283	
.oracle/checkins/batch-1-r9.md:6328: trailing whitespace.
+   284	
.oracle/checkins/batch-1-r9.md:6344: trailing whitespace.
+   300	
.oracle/checkins/batch-1-r9.md:6351: trailing whitespace.
+   307	
.oracle/checkins/batch-1-r9.md:6372: trailing whitespace.
+   328	
.oracle/checkins/batch-1-r9.md:6399: trailing whitespace.
+   355	
.oracle/checkins/batch-1-r9.md:6400: trailing whitespace.
+   356	
.oracle/checkins/batch-1-r9.md:6403: trailing whitespace.
+   359	
.oracle/checkins/batch-1-r9.md:6405: trailing whitespace.
+   361	
.oracle/checkins/batch-1-r9.md:6406: trailing whitespace.
+   362	
.oracle/checkins/batch-1-r9.md:6409: trailing whitespace.
+   365	
.oracle/checkins/batch-1-r9.md:6413: trailing whitespace.
+   369	
.oracle/checkins/batch-1-r9.md:6414: trailing whitespace.
+   370	
.oracle/checkins/batch-1-r9.md:6417: trailing whitespace.
+   373	
.oracle/checkins/batch-1-r9.md:6422: trailing whitespace.
+   378	
.oracle/checkins/batch-1-r9.md:6423: trailing whitespace.
+   379	
.oracle/checkins/batch-1-r9.md:6426: trailing whitespace.
+   382	
.oracle/checkins/batch-1-r9.md:6428: trailing whitespace.
+   384	
.oracle/checkins/batch-1-r9.md:6429: trailing whitespace.
+   385	
.oracle/checkins/batch-1-r9.md:6490: trailing whitespace.
+   651	
.oracle/checkins/batch-1-r9.md:6491: trailing whitespace.
+   652	
.oracle/checkins/batch-1-r9.md:6522: trailing whitespace.
+   683	
.oracle/checkins/batch-1-r9.md:6532: trailing whitespace.
+   693	
.oracle/checkins/batch-1-r9.md:6568: trailing whitespace.
+   729	
.oracle/checkins/batch-1-r9.md:6569: trailing whitespace.
+   730	
.oracle/checkins/batch-1-r9.md:6587: trailing whitespace.
+   748	
.oracle/checkins/batch-1-r9.md:6588: trailing whitespace.
+   749	
.oracle/checkins/batch-1-r9.md:6624: trailing whitespace.
+   785	
.oracle/checkins/batch-1-r9.md:6625: trailing whitespace.
+   786	
.oracle/checkins/batch-1-r9.md:6639: trailing whitespace.
+   800	
.oracle/checkins/batch-1-r9.md:6640: trailing whitespace.
+   801	
.oracle/checkins/batch-1-r9.md:6656: trailing whitespace.
+   817	
.oracle/checkins/batch-1-r9.md:6657: trailing whitespace.
+   818	
.oracle/checkins/batch-1-r9.md:6753: trailing whitespace.
+   914	
.oracle/checkins/batch-1-r9.md:6754: trailing whitespace.
+   915	
.oracle/checkins/batch-1-r9.md:6840: trailing whitespace.
+  1001	
.oracle/checkins/batch-1-r9.md:6841: trailing whitespace.
+  1002	
.oracle/checkins/batch-1-r9.md:6850: trailing whitespace.
+  1011	
.oracle/checkins/batch-1-r9.md:6851: trailing whitespace.
+  1012	
.oracle/checkins/batch-1-r9.md:6909: trailing whitespace.
+   285	
.oracle/checkins/batch-1-r9.md:6918: trailing whitespace.
+   294	
.oracle/checkins/batch-1-r9.md:6919: trailing whitespace.
+   295	
.oracle/checkins/batch-1-r9.md:6926: trailing whitespace.
+   302	
.oracle/checkins/batch-1-r9.md:6927: trailing whitespace.
+   303	
.oracle/checkins/batch-1-r9.md:6936: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r9.md:6937: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r9.md:6954: trailing whitespace.
+   330	
.oracle/checkins/batch-1-r9.md:6955: trailing whitespace.
+   331	
.oracle/checkins/batch-1-r9.md:6971: trailing whitespace.
+   826	
.oracle/checkins/batch-1-r9.md:7013: trailing whitespace.
+   868	
.oracle/checkins/batch-1-r9.md:7020: trailing whitespace.
+   875	
.oracle/checkins/batch-1-r9.md:7023: trailing whitespace.
+   878	
.oracle/checkins/batch-1-r9.md:7037: trailing whitespace.
+   892	
.oracle/checkins/batch-1-r9.md:7038: trailing whitespace.
+   893	
.oracle/checkins/batch-1-r9.md:7042: trailing whitespace.
+   897	
.oracle/checkins/batch-1-r9.md:7050: trailing whitespace.
+   905	
.oracle/checkins/batch-1-r9.md:7081: trailing whitespace.
+   936	
.oracle/checkins/batch-1-r9.md:7094: trailing whitespace.
+   949	
.oracle/checkins/batch-1-r9.md:7125: trailing whitespace.
+   980	
.oracle/checkins/batch-1-r9.md:7132: trailing whitespace.
+   987	
.oracle/checkins/batch-1-r9.md:7133: trailing whitespace.
+   988	
.oracle/checkins/batch-1-r9.md:7137: trailing whitespace.
+   992	
.oracle/checkins/batch-1-r9.md:7145: trailing whitespace.
+  1000	
.oracle/checkins/batch-1-r9.md:7200: trailing whitespace.
+   440	
.oracle/checkins/batch-1-r9.md:7201: trailing whitespace.
+   441	
.oracle/checkins/batch-1-r9.md:7205: trailing whitespace.
+   445	
.oracle/checkins/batch-1-r9.md:7219: trailing whitespace.
+   459	
.oracle/checkins/batch-1-r9.md:7267: trailing whitespace.
+   507	
.oracle/checkins/batch-1-r9.md:7271: trailing whitespace.
+   511	
.oracle/checkins/batch-1-r9.md:7290: trailing whitespace.
+   530	
.oracle/checkins/batch-1-r9.md:7323: trailing whitespace.
+   563	
.oracle/checkins/batch-1-r9.md:7324: trailing whitespace.
+   564	
.oracle/checkins/batch-1-r9.md:7331: trailing whitespace.
+   571	
.oracle/checkins/batch-1-r9.md:7336: trailing whitespace.
+   576	
.oracle/checkins/batch-1-r9.md:7342: trailing whitespace.
+   582	
.oracle/checkins/batch-1-r9.md:7343: trailing whitespace.
+   583	
.oracle/checkins/batch-1-r9.md:7347: trailing whitespace.
+   587	
.oracle/checkins/batch-1-r9.md:7352: trailing whitespace.
+   592	
.oracle/checkins/batch-1-r9.md:7364: trailing whitespace.
+   604	
.oracle/checkins/batch-1-r9.md:7369: trailing whitespace.
+   609	
.oracle/checkins/batch-1-r9.md:7381: trailing whitespace.
+   621	
.oracle/checkins/batch-1-r9.md:7393: trailing whitespace.
+   633	
.oracle/checkins/batch-1-r9.md:7394: trailing whitespace.
+   634	
.oracle/checkins/batch-1-r9.md:7415: trailing whitespace.
+   655	
.oracle/checkins/batch-1-r9.md:7416: trailing whitespace.
+   656	
.oracle/checkins/batch-1-r9.md:7420: trailing whitespace.
+   660	
.oracle/checkins/batch-1-r9.md:7427: trailing whitespace.
+   667	
.oracle/checkins/batch-1-r9.md:7450: trailing whitespace.
+   690	
.oracle/checkins/batch-1-r9.md:7462: trailing whitespace.
+   702	
.oracle/checkins/batch-1-r9.md:7477: trailing whitespace.
+   717	
.oracle/checkins/batch-1-r9.md:7500: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r9.md:7505: trailing whitespace.
+   230	
.oracle/checkins/batch-1-r9.md:7513: trailing whitespace.
+   238	
.oracle/checkins/batch-1-r9.md:7515: trailing whitespace.
+   240	
.oracle/checkins/batch-1-r9.md:7518: trailing whitespace.
+   243	
.oracle/checkins/batch-1-r9.md:7526: trailing whitespace.
+   251	
.oracle/checkins/batch-1-r9.md:7530: trailing whitespace.
+   255	
.oracle/checkins/batch-1-r9.md:7532: trailing whitespace.
+   257	
.oracle/checkins/batch-1-r9.md:7537: trailing whitespace.
+   262	
.oracle/checkins/batch-1-r9.md:7549: trailing whitespace.
+   274	
.oracle/checkins/batch-1-r9.md:7551: trailing whitespace.
+   276	
.oracle/checkins/batch-1-r9.md:7555: trailing whitespace.
+   280	
.oracle/checkins/batch-1-r9.md:7565: trailing whitespace.
+   290	
.oracle/checkins/batch-1-r9.md:7567: trailing whitespace.
+   292	
.oracle/checkins/batch-1-r9.md:7577: trailing whitespace.
+   461	
.oracle/checkins/batch-1-r9.md:7579: trailing whitespace.
+   463	
.oracle/checkins/batch-1-r9.md:7581: trailing whitespace.
+   465	
.oracle/checkins/batch-1-r9.md:7586: trailing whitespace.
+   470	
.oracle/checkins/batch-1-r9.md:7608: trailing whitespace.
+   492	
.oracle/checkins/batch-1-r9.md:7618: trailing whitespace.
+   502	
.oracle/checkins/batch-1-r9.md:7620: trailing whitespace.
+   504	
.oracle/checkins/batch-1-r9.md:7628: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r9.md:7630: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r9.md:7632: trailing whitespace.
+     6	
.oracle/checkins/batch-1-r9.md:7634: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r9.md:7643: trailing whitespace.
+    17	
.oracle/checkins/batch-1-r9.md:7645: trailing whitespace.
+    19	
.oracle/checkins/batch-1-r9.md:7651: trailing whitespace.
+    25	
.oracle/checkins/batch-1-r9.md:7653: trailing whitespace.
+    27	
.oracle/checkins/batch-1-r9.md:7655: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r9.md:7657: trailing whitespace.
+    31	
.oracle/checkins/batch-1-r9.md:7666: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r9.md:7668: trailing whitespace.
+    42	
.oracle/checkins/batch-1-r9.md:7675: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r9.md:7677: trailing whitespace.
+    51	
.oracle/checkins/batch-1-r9.md:7679: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r9.md:7681: trailing whitespace.
+    55	
.oracle/checkins/batch-1-r9.md:7689: trailing whitespace.
+    63	
.oracle/checkins/batch-1-r9.md:7691: trailing whitespace.
+    65	
.oracle/checkins/batch-1-r9.md:7698: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r9.md:7700: trailing whitespace.
+    74	
.oracle/checkins/batch-1-r9.md:7702: trailing whitespace.
+    76	
.oracle/checkins/batch-1-r9.md:7704: trailing whitespace.
+    78	
.oracle/checkins/batch-1-r9.md:7712: trailing whitespace.
+    86	
.oracle/checkins/batch-1-r9.md:7714: trailing whitespace.
+    88	
.oracle/checkins/batch-1-r9.md:7720: trailing whitespace.
+    94	
.oracle/checkins/batch-1-r9.md:7722: trailing whitespace.
+    96	
.oracle/checkins/batch-1-r9.md:7724: trailing whitespace.
+    98	
.oracle/checkins/batch-1-r9.md:7726: trailing whitespace.
+   100	
.oracle/checkins/batch-1-r9.md:7842: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:8018: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:8019: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:8028: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:8029: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:8074: trailing whitespace.
+ 
.oracle/checkins/batch-1-r9.md:8175: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r9.md:8176: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r9.md:8238: trailing whitespace.
+   168	
.oracle/checkins/batch-1-r9.md:8239: trailing whitespace.
+   169	
.oracle/checkins/batch-1-r9.md:8306: trailing whitespace.
+   236	
.oracle/checkins/batch-1-r9.md:8307: trailing whitespace.
+   237	
.oracle/checkins/batch-1-r9.md:8318: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r9.md:8319: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r9.md:8402: trailing whitespace.
+f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-1-r9.md:8403: trailing whitespace.
+f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-1-r9.md:8477: trailing whitespace.
+91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-1-r9.md:8478: trailing whitespace.
+91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-1-r9.md:8508: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r9.md:8514: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r9.md:8517: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r9.md:8526: trailing whitespace.
+    20	
.oracle/checkins/batch-1-r9.md:8527: trailing whitespace.
+    21	
.oracle/checkins/batch-1-r9.md:8554: trailing whitespace.
+    48	
.oracle/checkins/batch-1-r9.md:8555: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r9.md:8558: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r9.md:8559: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r9.md:8562: trailing whitespace.
+    56	
.oracle/checkins/batch-1-r9.md:8563: trailing whitespace.
+    57	
.oracle/checkins/batch-1-r9.md:8566: trailing whitespace.
+    60	
.oracle/checkins/batch-1-r9.md:8567: trailing whitespace.
+    61	
.oracle/checkins/batch-1-r9.md:8578: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r9.md:8579: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r9.md:8587: trailing whitespace.
+    81	
.oracle/checkins/batch-1-r9.md:8594: trailing whitespace.
+    88	
.oracle/checkins/batch-1-r9.md:8595: trailing whitespace.
+    89	
.oracle/checkins/batch-1-r9.md:8602: trailing whitespace.
+    96	
.oracle/checkins/batch-1-r9.md:8603: trailing whitespace.
+    97	
.oracle/checkins/batch-1-r9.md:8611: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r9.md:8612: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r9.md:8619: trailing whitespace.
+   113	
.oracle/checkins/batch-1-r9.md:8620: trailing whitespace.
+   114	
.oracle/checkins/batch-1-r9.md:8628: trailing whitespace.
+   122	
.oracle/checkins/batch-1-r9.md:8629: trailing whitespace.
+   123	
.oracle/checkins/batch-1-r9.md:8637: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r9.md:8638: trailing whitespace.
+   132	
.oracle/checkins/batch-1-r9.md:8668: trailing whitespace.
+   162	
.oracle/checkins/batch-1-r9.md:8669: trailing whitespace.
+   163	
.oracle/checkins/batch-1-r9.md:8684: trailing whitespace.
+   178	
.oracle/checkins/batch-1-r9.md:8685: trailing whitespace.
+   179	
.oracle/checkins/batch-1-r9.md:8712: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r9.md:8713: trailing whitespace.
+   207	
.oracle/checkins/batch-1-r9.md:8755: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r9.md:8756: trailing whitespace.
+   250	
.oracle/checkins/batch-1-r9.md:8794: trailing whitespace.
+   288	
.oracle/checkins/batch-1-r9.md:8795: trailing whitespace.
+   289	
.oracle/checkins/batch-1-r9.md:8818: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r9.md:8819: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r9.md:8830: trailing whitespace.
+   324	
.oracle/checkins/batch-1-r9.md:8831: trailing whitespace.
+   325	
.oracle/checkins/batch-1-r9.md:8844: trailing whitespace.
+   338	
.oracle/checkins/batch-1-r9.md:8845: trailing whitespace.
+   339	
.oracle/checkins/batch-1-r9.md:8862: trailing whitespace.
+   356	
.oracle/checkins/batch-1-r9.md:8863: trailing whitespace.
+   357	
.oracle/checkins/batch-1-r9.md:8881: trailing whitespace.
+   375	
.oracle/checkins/batch-1-r9.md:8882: trailing whitespace.
+   376	
.oracle/checkins/batch-1-r9.md:8920: trailing whitespace.
+    35	
.oracle/checkins/batch-1-r9.md:8925: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r9.md:8937: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r9.md:8958: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r9.md:8980: trailing whitespace.
+   205	
.oracle/checkins/batch-1-r9.md:8981: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r9.md:8984: trailing whitespace.
+   209	
.oracle/checkins/batch-1-r9.md:8990: trailing whitespace.
+   215	
.oracle/checkins/batch-1-r9.md:8991: trailing whitespace.
+   216	
.oracle/checkins/batch-1-r9.md:9000: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r9.md:9001: trailing whitespace.
+   226	
.oracle/checkins/batch-1-r9.md:9006: trailing whitespace.
+   231	
.oracle/checkins/batch-1-r9.md:9007: trailing whitespace.
+   232	
.oracle/checkins/batch-1-r9.md:9057: trailing whitespace.
+   288	
.oracle/checkins/batch-1-r9.md:9058: trailing whitespace.
+   289	
.oracle/checkins/batch-1-r9.md:9096: trailing whitespace.
+   158	
.oracle/checkins/batch-1-r9.md:9097: trailing whitespace.
+   159	
.oracle/checkins/batch-1-r9.md:9103: trailing whitespace.
+   165	
.oracle/checkins/batch-1-r9.md:9104: trailing whitespace.
+   166	
.oracle/checkins/batch-1-r9.md:9109: trailing whitespace.
+   171	
.oracle/checkins/batch-1-r9.md:9110: trailing whitespace.
+   172	
.oracle/checkins/batch-1-r9.md:9124: trailing whitespace.
+   186	
.oracle/checkins/batch-1-r9.md:9125: trailing whitespace.
+   187	
.oracle/checkins/batch-1-r9.md:9132: trailing whitespace.
+   194	
.oracle/checkins/batch-1-r9.md:9133: trailing whitespace.
+   195	
.oracle/checkins/batch-1-r9.md:9143: trailing whitespace.
+   205	

exec
/bin/zsh -lc "git diff --no-ext-diff --unified=80 788501c..6acd4be -- astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/result.json tests/core/rendering/test_contracts.py && rg -n -C 8 'VideoArtifact reconstruction|workspacePath still|bypassable|DTO-equivalent|"'^PASS$|''^1'"\\.|"'^2'"\\.' .oracle/checkins/batch-1-r9.md | tail -n 220" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index c97f7d0..3a363c1 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -47,275 +47,283 @@ def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None
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
         if segments and len(segments) > 1:
             raise TypeError(
                 "mapping-form artifact_profiles is unordered; use sequence form "
                 "(ordered VideoArtifacts, one per segment) for multi-segment plans"
             )
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
+                profile = VideoArtifact.from_dict(
+                    _json_safe_mapping(profile.to_dict(), label="artifact")
+                )
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
-        for profile in value:
-            if not isinstance(profile, VideoArtifact):
+        for raw_profile in value:
+            if not isinstance(raw_profile, VideoArtifact):
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
                     "so lineage records stay path-keyed"
                 )
+            # Reconstruct through the DTO so mutation cannot smuggle invalid
+            # paths, profiles, or attachments past validation.
+            profile = VideoArtifact.from_dict(
+                _json_safe_mapping(raw_profile.to_dict(), label="artifact")
+            )
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
     allowed = {"profile", "sha256", "attachments", "path"}
     unknown = sorted(raw_keys - allowed)
     if unknown:
         raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
     missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
     if missing:
         raise ValueError(
             f"artifact lineage is missing required fields: {', '.join(missing)}"
         )
     if raw["sha256"] is None:
         raise ValueError("artifact lineage sha256 is required and must not be null")
     if not isinstance(raw["sha256"], str):
         raise TypeError("artifact lineage sha256 must be a string")
     if "path" in raw:
         embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
         if embedded != key:
             raise ValueError(
                 f"artifact lineage path {embedded!r} must equal its map key {key!r}"
             )
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
-        "path": raw["path"] if "path" in raw else key,
+        "path": key,
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
         RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
         if isinstance(plan, RenderPlan)
         else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
     )
     normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
     legacy_segments = [
         _legacy_segment_projection(segment) for segment in normalized_plan.segments
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index e959bf7..eff7c06 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -1,148 +1,148 @@
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
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
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
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\r\\n]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\s]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\s]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "portableName": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
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
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index 5826c46..c4acc91 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -1,105 +1,105 @@
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
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\r\\n]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\s]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\s]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "portableName": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
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
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 2195b2b..3a87be3 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -911,162 +911,175 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
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
             artifact_profiles=[
                 VideoArtifact(
                     path="outputs/v1.mp4",
                     profile=_profile(),
                     sha256=SHA_B,
                     duration_frames=24,
                     audio=AudioOwnership.RENDERED,
                     attachments={
                         "alpha": Attachment(
                             name="alpha",
                             path="outputs/a.mp4",
                             kind="alpha",
                             sha256=SHA_C,
                         )
                     },
                 ),
                 VideoArtifact(
                     path="outputs/v2.mp4",
                     profile=_profile(),
                     sha256=SHA_D,
                     duration_frames=24,
                     audio=AudioOwnership.RENDERED,
                     attachments={
                         "alpha": Attachment(
                             name="alpha",
                             path="outputs/a2.mp4",
                             kind="alpha",
                             sha256=SHA_C,
                         )
                     },
                 ),
             ],
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
-    # A mutated RenderPlan instance is reconstructed at the boundary, so
-    # clearing its segments cannot bypass the positive-plan invariant.
+    # A mutated VideoArtifact instance is reconstructed at the boundary, so a
+    # smuggled escaped path cannot pass validation.
+    with pytest.raises(ValueError, match="workspace path"):
+        mutated = VideoArtifact(
+            path="outputs/a.mp4",
+            profile=_profile(audio=False),
+            sha256=SHA_B,
+            duration_frames=48,
+        )
+        object.__setattr__(mutated, "path", "../escape.mp4")
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles=[mutated],
+        )
     with pytest.raises(RendererProtocolError, match="positive-frame plan"):
         positive = _plan()
         object.__setattr__(positive, "segments", [])
         assemble_provenance_v2(
             **base,
             plan=positive,
             artifact_profiles=[],
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
 
730-
731-Hivemind writes are public publication, including pending distillations. Never
732-publish automatically: dry-run or preview the payload, remove private paths,
733-prompts, media, and URLs, and obtain explicit user confirmation before calling
734-`hivemind.contribute`. If Hivemind is unavailable, install its pack and shared
--
828-the generic subprocess-plus-manifest contract. Use `local` or `manual` when the
829-step does not need asynchronous artifact fetch/retry behavior.
830-
831-## Create Something New
832-
833-Read `docs/guides/creating-tools.md`, then follow this build order. Complete every
834-step before falling back to the next.
835-
836:1. **Search and compose existing executors first.** If existing executors can
837-   be wired together, build only an orchestrator that calls them.
838:2. **Create missing executors next.** Each new executor does one concrete,
839-   focused, independently runnable unit of work.
840-3. **Then write the orchestrator.** It composes existing and newly created
841-   executors into the workflow.
842-4. **Add elements only for reusable render building blocks.** Effects,
843-   animations, and transitions belong in the element tree, not in ad hoc
844-   timeline code.
845-
846-Do not start by writing a god-orchestrator. If a `run.py` grows past a couple
--
940-- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
941-- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
942-- **Already have the answer?** → don't dispatch. Subagents aren't free.
943-
944-## Use the cheapest subagent that can do the job
945-
946-Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.
947-
948:1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
949:2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
950-3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
951-4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.
952-
953-Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.
954-
955-Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.
956-
957----
--
1156-the generic subprocess-plus-manifest contract. Use `local` or `manual` when the
1157-step does not need asynchronous artifact fetch/retry behavior.
1158-
1159-## Create Something New
1160-
1161-Read `docs/guides/creating-tools.md`, then follow this build order. Complete every
1162-step before falling back to the next.
1163-
1164:1. **Search and compose existing executors first.** If existing executors can
1165-   be wired together, build only an orchestrator that calls them.
1166:2. **Create missing executors next.** Each new executor does one concrete,
1167-   focused, independently runnable unit of work.
1168-3. **Then write the orchestrator.** It composes existing and newly created
1169-   executors into the workflow.
1170-4. **Add elements only for reusable render building blocks.** Effects,
1171-   animations, and transitions belong in the element tree, not in ad hoc
1172-   timeline code.
1173-
1174-Do not start by writing a god-orchestrator. If a `run.py` grows past a couple
--
1656-# edit astrid/packs/local/elements/effects/text-card/component.tsx
1657-python3 scripts/gen_effect_registry.py     # regenerates registry
1658-```
1659-
1660-The local-pack TextCard in this repo already supports anchored positioning (`params.anchor` ∈ {top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right}, plus `offsetX/offsetY/maxWidth/background/padding/borderRadius/lineHeight/weight/letterSpacing/textShadow`) and reads `clip.effects.{fade_in,fade_out}` (seconds) for entry/exit fades.
1661-
1662-### 5-minute "add a caption" recipe
1663-
1664:1. Drop your source `.mp4` into `runs/<name>/`.
1665:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
1666-3. Render with the command above.
1667-4. ffprobe / open the `composed.mp4`.
1668-5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
1669-
1670-## Validate
1671-
1672-```bash
1673-pytest tests/test_doctor_setup.py tests/test_canonical_cli.py
--
1712-the generic subprocess-plus-manifest contract. Use `local` or `manual` when the
1713-step does not need asynchronous artifact fetch/retry behavior.
1714-
1715-## Create Something New
1716-
1717-Read `docs/guides/creating-tools.md`, then follow this build order. Complete every
1718-step before falling back to the next.
1719-
1720:1. **Search and compose existing executors first.** If existing executors can
1721-   be wired together, build only an orchestrator that calls them.
1722:2. **Create missing executors next.** Each new executor does one concrete,
1723-   focused, independently runnable unit of work.
1724-3. **Then write the orchestrator.** It composes existing and newly created
1725-   executors into the workflow.
1726-4. **Add elements only for reusable render building blocks.** Effects,
1727-   animations, and transitions belong in the element tree, not in ad hoc
1728-   timeline code.
1729-
1730-Do not start by writing a god-orchestrator. If a `run.py` grows past a couple
--
2220-# edit astrid/packs/local/elements/effects/text-card/component.tsx
2221-python3 scripts/gen_effect_registry.py     # regenerates registry
2222-```
2223-
2224-The local-pack TextCard in this repo already supports anchored positioning (`params.anchor` ∈ {top-left, top, top-right, left, center, right, bottom-left, bottom, bottom-right}, plus `offsetX/offsetY/maxWidth/background/padding/borderRadius/lineHeight/weight/letterSpacing/textShadow`) and reads `clip.effects.{fade_in,fade_out}` (seconds) for entry/exit fades.
2225-
2226-### 5-minute "add a caption" recipe
2227-
2228:1. Drop your source `.mp4` into `runs/<name>/`.
2229:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
2230-3. Render with the command above.
2231-4. ffprobe / open the `composed.mp4`.
2232-5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
2233-
2234-## Validate
2235-
2236-```bash
2237-pytest tests/test_doctor_setup.py tests/test_canonical_cli.py
--
2279-+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
2280-+
2281-+Prior verdicts: batch-1.md (9), -r1 (5), -r2 (3), -r3 (3), -r4 (4), -r5 (3),
2282-+-r6 (3), -r7 (3). Eighth rework committed as `8418bae` (prior head ab486f9).
2283-+Incremental diff at /tmp/batch1-r8.diff.
2284-+
2285-+## How each of your 3 re-review7 issues was addressed (host-implemented)
2286-+
2287:+1. **Per-segment lineage unbound, cardinality bypassable** →
2288-+   - Sequence form now preserves ORDER (returns a path-keyed list, not an
2289-+     unordered map) and REJECTS duplicate paths.
2290-+   - Mapping form requires path keys == VideoArtifact.path.
2291-+2. **Provenance bypasses artifact/attachment contracts** →
2292-+   - Artifact keys validated as workspace-relative paths (traversal/absolute
2293-+     rejected).
2294-+   - Top-level Attachment values reconstructed through `Attachment.from_dict`
2295-+     (mutation via object.__setattr__ cannot inject invalid fields).
--
3309-/bin/zsh -lc 'git status --short --branch && git rev-parse HEAD && git log -3 --oneline --decorate' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
3310- succeeded in 0ms:
3311-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3312-## oracle-run
3313-?? .oracle/checkins/batch-1-r9.md
3314-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3315-788501c934fed0b0a85462418e77c021781681a9
3316-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3317:788501c (HEAD -> oracle-run) batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
3318-8418bae batch1-rework8: oracle re-review7 issues 1-3 (ordered path-keyed lineage w/ dup-path + cross-artifact attachment uniqueness, DTO reconstruction for attachments/profiles, trailing-LF schema anchors)
3319-ab486f9 batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)
3320-
3321-exec
3322-/bin/zsh -lc 'tail -120 .oracle/checkins/batch-1-r8.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
3323- succeeded in 0ms:
3324-   278	        ),
3325-   279	        ("uppercase config id", _set(base, ("backend_config",), {"Rendering.FfmpegFinalizer": {}})),
--
3424- print(repr(x),v.is_valid(x),d)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
3425- succeeded in 155ms:
3426-'dir/ /video.mp4' True False
3427-'dir/\t/video.mp4' True False
3428-'dir/.\n' False True
3429-'dir/..\n' False True
3430-
3431-codex
3432:1. **Per-segment lineage remains unbound and bypassable.** Sequence output drops `VideoArtifact.path`, accepts mutated escaped paths, and cannot round-trip. Multi-segment mapping remains unordered. A mutated positive `RenderPlan` with `segments.clear()` also accepts empty lineage. Reconstruct DTOs at the boundary and use one canonical ordered, path-bearing entry per segment; reject unordered multi-segment mappings. [provenance.py:107](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:107) [provenance.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:302)
3433-
3434:2. **The JSON Schemas are no longer language-neutral.** All 124 patterns use Python-specific `\Z`; ECMAScript treats it as literal `Z` or rejects it, so canonical IDs and digests fail non-Python validation. Replace it with a portable absolute-end assertion such as `(?![\\s\\S])` and add ECMAScript conformance coverage. The new LF adversaries also target nonexistent top-level finalize fields, so they do not exercise the intended nested patterns. [result.json:16](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:16) [test_schema_roundtrip.py:283](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_schema_roundtrip.py:283)
3435-
3436-3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
3437-tokens used
3438-192,998
3439:1. **Per-segment lineage remains unbound and bypassable.** Sequence output drops `VideoArtifact.path`, accepts mutated escaped paths, and cannot round-trip. Multi-segment mapping remains unordered. A mutated positive `RenderPlan` with `segments.clear()` also accepts empty lineage. Reconstruct DTOs at the boundary and use one canonical ordered, path-bearing entry per segment; reject unordered multi-segment mappings. [provenance.py:107](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:107) [provenance.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:302)
3440-
3441:2. **The JSON Schemas are no longer language-neutral.** All 124 patterns use Python-specific `\Z`; ECMAScript treats it as literal `Z` or rejects it, so canonical IDs and digests fail non-Python validation. Replace it with a portable absolute-end assertion such as `(?![\\s\\S])` and add ECMAScript conformance coverage. The new LF adversaries also target nonexistent top-level finalize fields, so they do not exercise the intended nested patterns. [result.json:16](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:16) [test_schema_roundtrip.py:283](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_schema_roundtrip.py:283)
3442-
3443-3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
3444-
3445-exec
3446-/bin/zsh -lc "rg -n '"'^## Batch 1|''^### Batch 1|Batch 1|render backend|Rendering'"' .oracle/tasklist.md | head -40" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
3447- succeeded in 0ms:
3448-3:## Batch 1 — Baseline, contracts, and discovery
3449-178:- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
--
6891-81	45	tests/core/rendering/test_contracts.py
6892-git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6893-commit 788501c934fed0b0a85462418e77c021781681a9
6894-Author:     POM <peter@omalley.io>
6895-AuthorDate: Wed Aug 12 04:39:08 2026 +0200
6896-Commit:     POM <peter@omalley.io>
6897-CommitDate: Wed Aug 12 04:39:08 2026 +0200
6898-
6899:    batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
6900-
6901-exec
6902-/bin/zsh -lc "rg -n \"class VideoArtifact|def from_dict\\(cls, payload.*VideoArtifact|class Attachment|class RenderProfile|def _require_workspace_relative_path\" astrid/core/rendering/contracts.py && nl -ba astrid/core/rendering/contracts.py | sed -n '285,340p' && nl -ba astrid/core/rendering/contracts.py | sed -n '820,1040p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
6903- succeeded in 0ms:
6904-314:def _require_workspace_relative_path(value: Any, label: str) -> str:
6905-443:class RenderProfile:
6906-585:class Attachment:
6907-658:class VideoArtifact:
--
9169- succeeded in 0ms:
9170-result.json true true true
9171-finalize.json true true true
9172-sha true false
9173-
9174-collab: Wait
9175-collab: Wait
9176-codex
9177:1. **`VideoArtifact` reconstruction remains bypassable.** [provenance.py:150](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150) never reconstructs sequence entries through `VideoArtifact.from_dict`; an artifact mutated to `path="../escape.mp4"` is accepted and emitted. Mapping lineage also validates `str(path)` but emits the original value, allowing an integer `path`. The emitted sequence still cannot round-trip because dictionary records are rejected.
9178-
9179:2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
9180-tokens used
9181-174,264
9182:1. **`VideoArtifact` reconstruction remains bypassable.** [provenance.py:150](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150) never reconstructs sequence entries through `VideoArtifact.from_dict`; an artifact mutated to `path="../escape.mp4"` is accepted and emitted. Mapping lineage also validates `str(path)` but emits the original value, allowing an integer `path`. The emitted sequence still cannot round-trip because dictionary records are rejected.
9183-
9184:2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '90,235p'; nl -ba astrid/core/rendering/contracts.py | sed -n '285,335p'; nl -ba astrid/core/rendering/contracts.py | sed -n '580,740p'; git diff --no-ext-diff --unified=25 788501c..6acd4be -- tests/core/rendering/test_contracts.py; rg -n \"artifact_profiles|lineage|round.trip|VideoArtifact\" tests/core/rendering astrid/core/rendering .oracle/tasklist.md | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   127	                profile = VideoArtifact.from_dict(
   128	                    _json_safe_mapping(profile.to_dict(), label="artifact")
   129	                )
   130	                lineage = _artifact_lineage(profile)
   131	            elif isinstance(profile, Mapping):
   132	                lineage = _artifact_lineage_from_mapping(profile, key=path)
   133	            else:
   134	                raise TypeError(
   135	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   136	                    "hashed lineage record {profile, sha256, attachments}; "
   137	                    "profile-only entries carry no output hash"
   138	                )
   139	            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
   140	            result[path] = lineage
   141	        # A positive plan must record exactly one hashed artifact per segment.
   142	        if segments:
   143	            if len(result) != len(segments):
   144	                raise ValueError(
   145	                    f"artifact_profiles must record exactly one hashed lineage entry "
   146	                    f"per segment: expected {len(segments)}, got {len(result)}"
   147	                )
   148	        return result
   149	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   150	        lineage: list[dict[str, Any]] = []
   151	        seen_paths: set[str] = set()
   152	        seen_attachment_names: set[str] = set()
   153	        for raw_profile in value:
   154	            if not isinstance(raw_profile, VideoArtifact):
   155	                raise TypeError(
   156	                    "sequence artifact_profiles entries must be VideoArtifacts "
   157	                    "so lineage records stay path-keyed"
   158	                )
   159	            # Reconstruct through the DTO so mutation cannot smuggle invalid
   160	            # paths, profiles, or attachments past validation.
   161	            profile = VideoArtifact.from_dict(
   162	                _json_safe_mapping(raw_profile.to_dict(), label="artifact")
   163	            )
   164	            if profile.path in seen_paths:
   165	                raise ValueError(
   166	                    f"artifact_profiles sequence contains duplicate path "
   167	                    f"{profile.path!r}"
   168	                )
   169	            seen_paths.add(profile.path)
   170	            record = _artifact_lineage(profile)
   171	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   172	            lineage.append(record)
   173	        if segments:
   174	            if len(lineage) != len(segments):
   175	                raise ValueError(
   176	                    f"artifact_profiles must record exactly one hashed lineage entry "
   177	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   178	                )
   179	        return lineage
   180	    raise TypeError("artifact_profiles must be an object or array")
   181	
   182	
   183	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   184	    raw_keys = set(raw)
   185	    allowed = {"profile", "sha256", "attachments", "path"}
   186	    unknown = sorted(raw_keys - allowed)
   187	    if unknown:
   188	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   189	    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
   190	    if missing:
   191	        raise ValueError(
   192	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   193	        )
   194	    if raw["sha256"] is None:
   195	        raise ValueError("artifact lineage sha256 is required and must not be null")
   196	    if not isinstance(raw["sha256"], str):
   197	        raise TypeError("artifact lineage sha256 must be a string")
   198	    if "path" in raw:
   199	        embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
   200	        if embedded != key:
   201	            raise ValueError(
   202	                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
   203	            )
   204	    profile = raw["profile"]
   205	    attachments: dict[str, Any] = {}
   206	    raw_attachments = raw["attachments"]
   207	    if raw_attachments is None:
   208	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   209	    if not isinstance(raw_attachments, Mapping):
   210	        raise TypeError("artifact lineage attachments must be an object")
   211	    for name, att in raw_attachments.items():
   212	        name = _require_string(name, "attachment name")
   213	        if isinstance(att, Attachment):
   214	            if att.name != name:
   215	                raise ValueError(
   216	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   217	                )
   218	            att = {
   219	                "path": att.path,
   220	                "kind": att.kind,
   221	                "sha256": att.sha256,
   222	            }
   223	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   224	        if att_unknown:
   225	            raise ValueError(
   226	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   227	            )
   228	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   229	        if att_missing:
   230	            raise ValueError(
   231	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   232	            )
   233	        if not isinstance(att["sha256"], str):
   234	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   235	        # Validate through the Attachment DTO so workspace-path containment and
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
   736	            attachments=dict(attachments or {}),
   737	        )
   738	
   739	
   740	def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 2195b2b..3a87be3 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -966,52 +966,65 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
                             path="outputs/a2.mp4",
                             kind="alpha",
                             sha256=SHA_C,
                         )
                     },
                 ),
             ],
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
-    # A mutated RenderPlan instance is reconstructed at the boundary, so
-    # clearing its segments cannot bypass the positive-plan invariant.
+    # A mutated VideoArtifact instance is reconstructed at the boundary, so a
+    # smuggled escaped path cannot pass validation.
+    with pytest.raises(ValueError, match="workspace path"):
+        mutated = VideoArtifact(
+            path="outputs/a.mp4",
+            profile=_profile(audio=False),
+            sha256=SHA_B,
+            duration_frames=48,
+        )
+        object.__setattr__(mutated, "path", "../escape.mp4")
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles=[mutated],
+        )
     with pytest.raises(RendererProtocolError, match="positive-frame plan"):
         positive = _plan()
         object.__setattr__(positive, "segments", [])
         assemble_provenance_v2(
             **base,
             plan=positive,
             artifact_profiles=[],
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
.oracle/tasklist.md:11:- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
.oracle/tasklist.md:57:- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
astrid/core/rendering/provenance.py:21:    VideoArtifact,
astrid/core/rendering/provenance.py:95:    lineage: Mapping[str, Any],
astrid/core/rendering/provenance.py:99:    for name in (lineage.get("attachments") or {}):
astrid/core/rendering/provenance.py:107:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:113:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:114:                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
astrid/core/rendering/provenance.py:121:            if isinstance(profile, VideoArtifact):
astrid/core/rendering/provenance.py:124:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:127:                profile = VideoArtifact.from_dict(
astrid/core/rendering/provenance.py:130:                lineage = _artifact_lineage(profile)
astrid/core/rendering/provenance.py:132:                lineage = _artifact_lineage_from_mapping(profile, key=path)
astrid/core/rendering/provenance.py:135:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:136:                    "hashed lineage record {profile, sha256, attachments}; "
astrid/core/rendering/provenance.py:139:            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
astrid/core/rendering/provenance.py:140:            result[path] = lineage
astrid/core/rendering/provenance.py:145:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:150:        lineage: list[dict[str, Any]] = []
astrid/core/rendering/provenance.py:154:            if not isinstance(raw_profile, VideoArtifact):
astrid/core/rendering/provenance.py:156:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:157:                    "so lineage records stay path-keyed"
astrid/core/rendering/provenance.py:161:            profile = VideoArtifact.from_dict(
astrid/core/rendering/provenance.py:166:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:170:            record = _artifact_lineage(profile)
astrid/core/rendering/provenance.py:172:            lineage.append(record)
astrid/core/rendering/provenance.py:174:            if len(lineage) != len(segments):
astrid/core/rendering/provenance.py:176:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:177:                    f"per segment: expected {len(segments)}, got {len(lineage)}"
astrid/core/rendering/provenance.py:179:        return lineage
astrid/core/rendering/provenance.py:180:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:183:def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
astrid/core/rendering/provenance.py:188:        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
astrid/core/rendering/provenance.py:192:            f"artifact lineage is missing required fields: {', '.join(missing)}"
astrid/core/rendering/provenance.py:195:        raise ValueError("artifact lineage sha256 is required and must not be null")
astrid/core/rendering/provenance.py:197:        raise TypeError("artifact lineage sha256 must be a string")
astrid/core/rendering/provenance.py:202:                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
astrid/core/rendering/provenance.py:208:        raise ValueError("artifact lineage attachments must be an object (may be empty)")
astrid/core/rendering/provenance.py:210:        raise TypeError("artifact lineage attachments must be an object")
astrid/core/rendering/provenance.py:258:def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
astrid/core/rendering/provenance.py:259:    """One hashed artifact lineage record: profile, sha256, attachments."""
astrid/core/rendering/provenance.py:260:    return _artifact_lineage_from_mapping(
astrid/core/rendering/provenance.py:300:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:310:    replay lineage come exclusively from the validated ``RenderPlan`` so a
astrid/core/rendering/provenance.py:351:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:352:            artifact_profiles,
astrid/core/rendering/contracts.py:65:        "artifact_profiles",
astrid/core/rendering/contracts.py:658:class VideoArtifact:
astrid/core/rendering/contracts.py:704:    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
astrid/core/rendering/contracts.py:728:    ) -> VideoArtifact:
astrid/core/rendering/contracts.py:1525:    video: VideoArtifact
astrid/core/rendering/contracts.py:1536:            if isinstance(self.video, VideoArtifact)
astrid/core/rendering/contracts.py:1537:            else VideoArtifact.from_dict(_require_mapping(self.video, "video"))
astrid/core/rendering/contracts.py:1591:                video=VideoArtifact.from_dict(data["video"]),
astrid/core/rendering/contracts.py:1701:    artifacts: list[VideoArtifact]
astrid/core/rendering/contracts.py:1717:            if isinstance(artifact, VideoArtifact)
astrid/core/rendering/contracts.py:1718:            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
astrid/core/rendering/contracts.py:1825:                artifacts=[VideoArtifact.from_dict(item) for item in data["artifacts"]],
astrid/core/rendering/contracts.py:2195:    "VideoArtifact",
astrid/core/rendering/__init__.py:14:    VideoArtifact,
astrid/core/rendering/__init__.py:24:    "VideoArtifact",
astrid/core/rendering/schemas/v1/plan.json:5:  "description": "Versioned routing lineage and deterministic half-open temporal coverage.",
astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
tests/core/rendering/test_schema_roundtrip.py:85:        round_trip = dto.to_dict()
tests/core/rendering/test_schema_roundtrip.py:86:        validator.validate(round_trip)
tests/core/rendering/test_schema_roundtrip.py:87:        assert round_trip == example
tests/core/rendering/test_schema_roundtrip.py:91:def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
tests/core/rendering/test_contracts.py:21:    VideoArtifact,
tests/core/rendering/test_contracts.py:179:) -> VideoArtifact:
tests/core/rendering/test_contracts.py:180:    return VideoArtifact(
tests/core/rendering/test_contracts.py:190:def _result(*, video: VideoArtifact | None = None) -> RenderResult:
tests/core/rendering/test_contracts.py:207:    artifacts: list[VideoArtifact] | None = None,
tests/core/rendering/test_contracts.py:220:def test_dto_json_round_trip() -> None:
tests/core/rendering/test_contracts.py:375:    artifact = VideoArtifact.from_dict(
tests/core/rendering/test_contracts.py:449:def test_finalize_round_trip_preserves_global_segment_attachments() -> None:
tests/core/rendering/test_contracts.py:460:    round_trip = FinalizeRequest.from_dict(request.to_dict())
tests/core/rendering/test_contracts.py:461:    assert round_trip.expected_attachments == {first.name: first, second.name: second}
tests/core/rendering/test_contracts.py:552:def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
tests/core/rendering/test_contracts.py:567:        "artifact_profiles": [
tests/core/rendering/test_contracts.py:568:            VideoArtifact(
tests/core/rendering/test_contracts.py:575:            VideoArtifact(
tests/core/rendering/test_contracts.py:653:def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
tests/core/rendering/test_contracts.py:655:    plan wire round-trip and the final provenance sidecar."""
tests/core/rendering/test_contracts.py:684:    # Wire round-trip
tests/core/rendering/test_contracts.py:701:        artifact_profiles=[
tests/core/rendering/test_contracts.py:702:            VideoArtifact(
tests/core/rendering/test_contracts.py:709:            VideoArtifact(
tests/core/rendering/test_contracts.py:750:def test_provenance_emits_hashed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:753:    artifact = VideoArtifact(
tests/core/rendering/test_contracts.py:774:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:781:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:782:    assert lineage["sha256"] == SHA_B
tests/core/rendering/test_contracts.py:783:    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
tests/core/rendering/test_contracts.py:784:    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
tests/core/rendering/test_contracts.py:819:def test_provenance_rejects_spoofed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:820:    """Artifact lineage must carry a real sha256; profile-only entries and
tests/core/rendering/test_contracts.py:833:    with pytest.raises(TypeError, match="hashed lineage"):
tests/core/rendering/test_contracts.py:835:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:841:            artifact_profiles={
tests/core/rendering/test_contracts.py:849:            artifact_profiles={
tests/core/rendering/test_contracts.py:861:            artifact_profiles={
tests/core/rendering/test_contracts.py:870:    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
tests/core/rendering/test_contracts.py:876:            artifact_profiles=[
tests/core/rendering/test_contracts.py:877:                VideoArtifact(
tests/core/rendering/test_contracts.py:890:            artifact_profiles={
tests/core/rendering/test_contracts.py:904:            artifact_profiles={
tests/core/rendering/test_contracts.py:920:            artifact_profiles={
tests/core/rendering/test_contracts.py:941:            artifact_profiles=[
tests/core/rendering/test_contracts.py:942:                VideoArtifact(
tests/core/rendering/test_contracts.py:957:                VideoArtifact(
tests/core/rendering/test_contracts.py:978:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:986:            artifact_profiles=[
tests/core/rendering/test_contracts.py:987:                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
tests/core/rendering/test_contracts.py:988:                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
tests/core/rendering/test_contracts.py:991:    # A mutated VideoArtifact instance is reconstructed at the boundary, so a
tests/core/rendering/test_contracts.py:994:        mutated = VideoArtifact(
tests/core/rendering/test_contracts.py:1004:            artifact_profiles=[mutated],
tests/core/rendering/test_contracts.py:1012:            artifact_profiles=[],
tests/core/rendering/test_contracts.py:1087:def test_manifest_round_trip() -> None:

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/schemas/v1/result.json | sed -n '280,390p'; nl -ba tests/core/rendering/test_contracts.py | sed -n '520,815p'; nl -ba tests/core/rendering/test_contracts.py | sed -n '810,1025p'; nl -ba .oracle/tasklist.md | sed -n '1,195p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   356	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
   357	      }
   358	    },
   359	    "stringMap": {
   360	      "type": "object",
   361	      "propertyNames": {
   362	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
   363	      },
   364	      "additionalProperties": {
   365	        "type": "string",
   366	        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
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
   567	        "artifact_profiles": [
   568	            VideoArtifact(
   569	                path="outputs/video.mp4",
   570	                profile=_profile(),
   571	                sha256=SHA_B,
   572	                duration_frames=24,
   573	                audio=AudioOwnership.RENDERED,
   574	            ),
   575	            VideoArtifact(
   576	                path="outputs/segment2.mp4",
   577	                profile=_profile(),
   578	                sha256=SHA_C,
   579	                duration_frames=24,
   580	                audio=AudioOwnership.RENDERED,
   581	            ),
   582	        ],
   583	        "audio_ownership": AudioOwnership.RENDERED,
   584	        "normalization": [],
   585	        "attachments": {},
   586	        "backend_fragments": {"acme.first": {"vendor": "Acme"}},
   587	        "v1_compatibility": compatibility,
   588	    }
   589	    payload = assemble_provenance_v2(**kwargs)
   590	    assert payload["schema_version"] == 2
   591	    assert payload["request_digest"] == SHA_D
   592	    assert payload["requested_policy"] == "hybrid"
   593	    assert payload["planner"] == _planner().to_dict()
   594	    assert [segment["renderer"]["id"] for segment in payload["segments_v2"]] == [
   595	        "acme.first",
   596	        "other.second",
   597	    ]
   598	    assert payload["segments_v2"] == [segment.to_dict() for segment in plan.segments]
   599	    assert [set(segment) for segment in payload["segments_v2"]] == [
   600	        {"window", "renderer", "input_hashes"},
   601	        {"window", "renderer", "input_hashes"},
   602	    ]
   603	    # V1-compatible projections are preserved unchanged.
   604	    assert payload["segments"] == [
   605	        {"engine": "first", "from": 0.0, "to": 1.0},
   606	        {"engine": "second", "from": 1.0, "to": 2.0},
   607	    ]
   608	    # segment_provenance passes through from the v1 compatibility projection
   609	    # verbatim — the host never rewrites it.
   610	    assert payload["segment_provenance"] == compatibility["segment_provenance"]
   611	    assert payload["finalizer"] == _finalizer().to_dict()
   612	    assert payload["composition_id"] == "TimelineComposition"
   613	
   614	    sidecar = tmp_path / "video.mp4.provenance.json"
   615	    assert write_provenance_v2(sidecar, **kwargs) == payload
   616	    assert sidecar.read_text(encoding="utf-8").endswith("\n")
   617	
   618	
   619	def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None:
   620	    plan = _plan().to_dict()
   621	    plan["segments"][0]["engine"] = "spoofed"
   622	    with pytest.raises(RendererProtocolError):
   623	        assemble_provenance_v2(
   624	            engine="hybrid",
   625	            output="out/video.mp4",
   626	            timeline="timeline.json",
   627	            assets_registry=None,
   628	            plan=plan,
   629	            v1_compatibility=_compatibility(),
   630	        )
   631	
   632	
   633	def test_compute_request_digest_is_canonical_and_stable() -> None:
   634	    from astrid.core.rendering.contracts import compute_request_digest
   635	
   636	    a = {"backend_config": {"acme.visual": {"quality": "preview"}}, "schema_version": 1}
   637	    b = {"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}}}
   638	    assert compute_request_digest(a) == compute_request_digest(b)
   639	    digest = compute_request_digest(a)
   640	    assert isinstance(digest, str)
   641	    assert len(digest) == 64
   642	    assert compute_request_digest({**a, "metadata": {"x": "y"}}) != digest
   643	    assert compute_request_digest({"schema_version": 1, "backend_config": {"acme.visual": {"quality": "preview"}, "other.key": {}}}) != digest
   644	
   645	
   646	def test_shared_sha256_helper_is_used_for_input_hashes(tmp_path: Path) -> None:
   647	    input_path = tmp_path / "timeline.json"
   648	    input_path.write_text("abc", encoding="utf-8")
   649	    hashes = hash_input_files({"timeline": input_path})
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
   991	    # A mutated VideoArtifact instance is reconstructed at the boundary, so a
   992	    # smuggled escaped path cannot pass validation.
   993	    with pytest.raises(ValueError, match="workspace path"):
   994	        mutated = VideoArtifact(
   995	            path="outputs/a.mp4",
   996	            profile=_profile(audio=False),
   997	            sha256=SHA_B,
   998	            duration_frames=48,
   999	        )
  1000	        object.__setattr__(mutated, "path", "../escape.mp4")
  1001	        assemble_provenance_v2(
  1002	            **base,
  1003	            plan=_plan(),
  1004	            artifact_profiles=[mutated],
  1005	        )
  1006	    with pytest.raises(RendererProtocolError, match="positive-frame plan"):
  1007	        positive = _plan()
  1008	        object.__setattr__(positive, "segments", [])
  1009	        assemble_provenance_v2(
  1010	            **base,
  1011	            plan=positive,
  1012	            artifact_profiles=[],
  1013	        )
  1014	
  1015	
  1016	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
  1017	    plan = _plan(
  1018	        segments=[_segment(12, 24), _segment(24, 36)],
  1019	        total_frames=48,
  1020	        window=_window(12, 36),
  1021	    )
  1022	    assert plan.total_frames == 48
  1023	    assert plan.window == _window(12, 36)
  1024	
  1025	
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
   121	
   122	**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.
   123	
   124	**Acceptance criteria:**
   125	
   126	- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
   127	- Any SDK/wire mismatch stops the batch and returns to M1 through the oracle; no SDK-only fields or semantics are introduced.
   128	- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
   129	- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
   130	- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
   131	- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
   132	- Scaffold collision, ownership, command-containment, static validation, trusted install, generated test, two-second smoke, and installed-wheel cases pass.
   133	
   134	### Tasks
   135	
   136	- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
   137	- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
   138	- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
   139	- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
   140	- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
   141	- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.
   142	
   143	## Batch 7 — CLI, replay, documentation, and epic freeze
   144	
   145	**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.
   146	
   147	**Acceptance criteria:**
   148	
   149	- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
   150	- `list` and `inspect` perform static metadata parsing and report source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and overrides without importing backend code.
   151	- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
   152	- Each CLI verb has a frozen raw-dictionary `--json` shape; expected errors exit 2, degraded bugs exit 1, and interruption cleans up before normal exit-130 behavior.
   153	- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
   154	- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
   155	- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
   156	- Renderer-author documentation covers raw JSON, Python SDK, non-Python commands, trust, permissions, selection, configuration, assets, output/audio/attachments, diagnostics, replay, and legacy selectors while explicitly deferring async jobs, remote infrastructure, and layer compositing.
   157	- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
   158	- Full pytest, semantic parity, real FFmpeg, explicit optional-Remotion evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.
   159	
   160	### Tasks
   161	
   162	- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
   163	- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
   164	- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
   165	- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
   166	- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
   167	- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
   168	
   169	## Execution notes
   170	
   171	- Persist this markdown exactly as `.oracle/tasklist.md` before implementation. It is frozen; any change requires an explicit oracle-reviewed plan revision.
   172	- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
   173	- If the oracle reports issues, rework only the current batch, recommit, and resubmit the cumulative `C(N-1)..HEAD` range until `PASS`. Do not begin the next batch early.
   174	- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
   175	- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
   176	- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
   177	- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
   178	- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
   179	- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.

exec
/bin/zsh -lc "nl -ba .oracle/tasklist.md | sed -n '1,72p'; rg -n \"artifact_profiles|provenance|lineage|round.trip|workspacePath|workspace path\" .oracle/plan.md .oracle/briefs .oracle/findings docs astrid tests -g '*.md' -g '*.py' -g '*.json' | head -n 400" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
.oracle/plan.md:37:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/plan.md:39:10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.
.oracle/plan.md:61:    - every currently emitted provenance field;
.oracle/plan.md:86:    - provenance v2.
.oracle/plan.md:102:  - Gate: Python DTOs and raw JSON fixtures round-trip identically; unknown versions, invalid frame bounds, duplicate attachments, traversal, and backend attempts to overwrite core fields fail structurally.
.oracle/plan.md:158:  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
.oracle/plan.md:160:  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
.oracle/plan.md:169:  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
.oracle/plan.md:198:  - Gate: support diagnostics, command graphs, stream-copy, gaps/overlaps, track mute/volume, clip volume zero, fades, source bounds, missing streams/binaries, audio-reactive marker frames/hashes, cleanup, output validation, and provenance pass with a real FFmpeg render.
.oracle/plan.md:208:  - Gate: one-segment pass-through, compatible and incompatible multi-segment plans, 24/25/30 and rational FPS, missing audio/video, codec/time-base mismatch, duration mismatch, normalization provenance, and cleanup pass.
.oracle/plan.md:210:- [ ] **M1-08 — Add generic routing, flexible facade output, and provenance v2**
.oracle/plan.md:226:    - use existing input-placeholder expansion for `{out}/{output_name}` and `{out}/{output_name}.provenance.json`;
.oracle/plan.md:227:    - keep declared output names `video` and `provenance` stable;
.oracle/plan.md:233:  - Emit provenance v2 with:
.oracle/plan.md:249:    `staged_asset_root`, `segments`, `segment_provenance`,
.oracle/plan.md:272:  - Preserve legacy `segments` and nested `segment_provenance` projections while adding normalized v2 segment records, including FFmpeg segments.
.oracle/plan.md:273:  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.
.oracle/plan.md:287:  | `video_editing/orchestrators/iteration_video/run.py` | Remove the concrete module import. Use its existing request project/run context to invoke the attached facade with `output_name=iteration.mp4`; eliminate the video-only rename. Declare and return `iteration.mp4.provenance.json`. |
.oracle/plan.md:313:    - provenance;
.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
.oracle/plan.md:418:  - Write the golden path: create → implement → test → static validate → trusted install/expose → smoke → inspect provenance.
.oracle/plan.md:436:- Kept the strict `extensions.rendering` approach, derived trust eligibility, additive provenance, semantic parity, and existing SDK/CLI conventions.
.oracle/plan.md:456:- External Reigh/upload/CAS provenance consumers remain unknown, so no v1 field removal belongs in this epic.
.oracle/plan.md:458:- Real Remotion rendering may remain unavailable in blocking CI, so props/provenance coverage and typechecking must remain strong and optional skips explicit.
.oracle/briefs/batch-1-t1.1.md:39:   - every v1 provenance key written by `_write_render_provenance` (quote the
.oracle/briefs/batch-1-t1.1.md:55:   - v1 provenance keys: build a small helper fixture that calls the
.oracle/briefs/batch-1-t1.1.md:56:     provenance-building function with a fake context (mock out any heavy
.oracle/briefs/08-callsites.md:17:     (does the provenance sidecar get renamed? stale `output` field?).
.oracle/findings/04-provenance-consumers.meta.json:2:  "brief": "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/04-provenance-consumers.md",
.oracle/findings/04-provenance-consumers.meta.json:8:  "meta_file": "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/findings/04-provenance-consumers.meta.json",
.oracle/findings/04-provenance-consumers.meta.json:40:  "response_file": "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/findings/04-provenance-consumers.txt",
.oracle/findings/04-provenance-consumers.meta.json:43:  "stem": "04-provenance-consumers",
.oracle/briefs/batch-1-r1-t1.2.md:10:five issues. Your files: `astrid/core/rendering/{contracts,errors,provenance}.py`,
.oracle/briefs/batch-1-r1-t1.2.md:28:across segments and preservation through finalization, with round-trip
.oracle/briefs/batch-1-r1-t1.2.md:32:## Issue 4 — Provenance cannot represent routing/replay lineage
.oracle/briefs/batch-1-r1-t1.2.md:34:Current provenance has only singular `resolved_backend`, `source_pack`,
.oracle/briefs/batch-1-r1-t1.2.md:38:Rework: freeze explicit records in provenance v2 (in `provenance.py` and the
.oracle/briefs/batch-1-r1-t1.2.md:98:- `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py tests/core/rendering` passes (whole dir, all tests green, including your new versioning/topology/parity/attachment/provenance tests).
.oracle/briefs/batch-1-r2-t1.1.md:49:  cleanup, provenance, secret non-leak);
.oracle/briefs/14-dynamic-outputs.md:8:(so provenance isn't orphaned by a post-render rename). That requires
docs/reference/sdk.md:113:# Identity handle with aliases and provenance
tests/session/test_binding_identity_config_discovery.py:106:def test_identity_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
.oracle/briefs/batch-1-r2-t1.2.md:10:`astrid/core/rendering/{contracts,errors,provenance,registry}.py`,
.oracle/briefs/batch-1-r2-t1.2.md:50:## Issue 2 — Provenance regresses v1 and replay lineage incomplete
.oracle/briefs/batch-1-r2-t1.2.md:52:`provenance.py` replaces the legacy `segments` key and overwrites nested
.oracle/briefs/batch-1-r2-t1.2.md:53:`segment_provenance` sidecars with `{engine,from,to}` projections, contradicting
.oracle/briefs/batch-1-r2-t1.2.md:58:  `segment_provenance` keep exactly the v1 shapes recorded in baseline.
.oracle/briefs/batch-1-r2-t1.2.md:65:- Include artifact hashes (per-segment video/attachments) in provenance.
.oracle/briefs/batch-1-r2-t1.2.md:67:  round-trip test).
.oracle/briefs/batch-1-r2-t1.2.md:96:- `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py` passes (v1 provenance shapes unchanged).
.oracle/briefs/batch-1-r2-t1.2.md:97:- `docs/contracts/render-backend-v1.md` reflects the corrected grammar + provenance v2 additive design.
.oracle/briefs/04-provenance-consumers.md:1:# Explore: provenance consumers and sidecar lifecycle
.oracle/briefs/04-provenance-consumers.md:8:   that writes or reads the `<output>.provenance.json` sidecar. Describe the
.oracle/briefs/04-provenance-consumers.md:9:   current provenance schema fields (engine, timeline, assets, pack order,
.oracle/briefs/04-provenance-consumers.md:15:3. Who ELSE consumes the provenance sidecar? Search the repo
.oracle/briefs/04-provenance-consumers.md:16:   (`grep -rn "provenance" --include=*.py astrid tests` and any JSON consumers):
.oracle/briefs/04-provenance-consumers.md:29:- Risks for provenance v2 migration
docs/reference/architecture.md:121:| `astrid/core/audit/*` | Shared library | Run-local provenance ledger, graph, and HTML report. |
docs/reference/architecture.md:123:| `astrid/core/paths.py` | Shared library | Repository and workspace path resolution. |
docs/reference/architecture.md:138:surface no longer exists. Threads are retained only as an internal lineage
docs/reference/architecture.md:139:model for iteration-video provenance; no current `astrid` command binds to
.oracle/briefs/batch-1-t1.3.md:46:   - a `pack.yaml` with `extensions.rendering` round-trips through schema
tests/test_quality_floor.py:24:    assert "restore or regenerate lineage" in message
tests/session/test_lease.py:35:def test_write_lease_init_round_trip(tmp_path: Path) -> None:
.oracle/briefs/batch-1-r1-t1.4.md:14:`contracts.py`/`provenance.py`/`errors.py`/`schemas/` or
.oracle/briefs/batch-1-r1-t1.4.md:51:Do NOT modify `contracts.py`, `provenance.py`, `errors.py`, `schemas/`,
tests/core/test_scoped_configs_schema.py:5:- Valid entries round-trip through to_dict().
tests/core/test_scoped_configs_schema.py:73:# Valid entries round-trip
tests/core/test_scoped_configs_schema.py:86:def test_executor_valid_scoped_configs_round_trip(keys):
tests/core/test_scoped_configs_schema.py:87:    """Valid scoped_configs entries round-trip through to_dict()."""
tests/core/test_scoped_configs_schema.py:102:def test_orchestrator_valid_scoped_configs_round_trip(keys):
tests/core/test_scoped_configs_schema.py:103:    """Valid scoped_configs entries round-trip through to_dict()."""
.oracle/briefs/batch-1-t1.2.md:68:- `provenance.py` — v2 provenance assembly: core-owned keys (`schema_version`,
.oracle/briefs/batch-1-t1.2.md:72:  `support_decision`, `input_hashes`, `segments`, `artifact_profiles`,
.oracle/briefs/batch-1-t1.2.md:81:  language-neutral source of truth. DTO round-trip must match.
.oracle/briefs/batch-1-t1.2.md:82:- `tests/core/rendering/test_contracts.py` — DTO ↔ JSON round-trip,
.oracle/briefs/batch-1-t1.2.md:85:  backend fragment attempting to overwrite core provenance key rejected.
.oracle/briefs/batch-1-t1.2.md:94:  finalization, provenance ownership (core vs backend), cleanup, replay
.oracle/briefs/batch-1-t1.2.md:99:batches do that. Only contracts, schemas, provenance assembly, and docs.
tests/core/integrations/test_arnold_session_resume.py:85:            event_lineage=EventLineageHashes(
tests/core/rendering/test_schema_roundtrip.py:85:        round_trip = dto.to_dict()
tests/core/rendering/test_schema_roundtrip.py:86:        validator.validate(round_trip)
tests/core/rendering/test_schema_roundtrip.py:87:        assert round_trip == example
tests/core/rendering/test_schema_roundtrip.py:91:def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
tests/core/rendering/test_contracts.py:36:from astrid.core.rendering.provenance import (
tests/core/rendering/test_contracts.py:37:    assemble_provenance_v2,
tests/core/rendering/test_contracts.py:40:    write_provenance_v2,
tests/core/rendering/test_contracts.py:220:def test_dto_json_round_trip() -> None:
tests/core/rendering/test_contracts.py:449:def test_finalize_round_trip_preserves_global_segment_attachments() -> None:
tests/core/rendering/test_contracts.py:460:    round_trip = FinalizeRequest.from_dict(request.to_dict())
tests/core/rendering/test_contracts.py:461:    assert round_trip.expected_attachments == {first.name: first, second.name: second}
tests/core/rendering/test_contracts.py:535:        "segment_provenance": [{"engine": "spoofed", "from": -1, "to": -1}],
tests/core/rendering/test_contracts.py:541:def test_provenance_requires_always_emitted_v1_projection() -> None:
tests/core/rendering/test_contracts.py:543:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:552:def test_provenance_v2_preserves_lineage_and_derives_legacy_segments(tmp_path: Path) -> None:
tests/core/rendering/test_contracts.py:567:        "artifact_profiles": [
tests/core/rendering/test_contracts.py:589:    payload = assemble_provenance_v2(**kwargs)
tests/core/rendering/test_contracts.py:608:    # segment_provenance passes through from the v1 compatibility projection
tests/core/rendering/test_contracts.py:610:    assert payload["segment_provenance"] == compatibility["segment_provenance"]
tests/core/rendering/test_contracts.py:614:    sidecar = tmp_path / "video.mp4.provenance.json"
tests/core/rendering/test_contracts.py:615:    assert write_provenance_v2(sidecar, **kwargs) == payload
tests/core/rendering/test_contracts.py:619:def test_provenance_rejects_spoofed_segment_projection_in_plan_mapping() -> None:
tests/core/rendering/test_contracts.py:623:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:653:def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
tests/core/rendering/test_contracts.py:655:    plan wire round-trip and the final provenance sidecar."""
tests/core/rendering/test_contracts.py:684:    # Wire round-trip
tests/core/rendering/test_contracts.py:695:    payload = assemble_provenance_v2(
tests/core/rendering/test_contracts.py:701:        artifact_profiles=[
tests/core/rendering/test_contracts.py:750:def test_provenance_emits_hashed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:768:    payload = assemble_provenance_v2(
tests/core/rendering/test_contracts.py:774:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:781:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:782:    assert lineage["sha256"] == SHA_B
tests/core/rendering/test_contracts.py:783:    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
tests/core/rendering/test_contracts.py:784:    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
tests/core/rendering/test_contracts.py:819:def test_provenance_rejects_spoofed_artifact_lineage() -> None:
tests/core/rendering/test_contracts.py:820:    """Artifact lineage must carry a real sha256; profile-only entries and
tests/core/rendering/test_contracts.py:833:    with pytest.raises(TypeError, match="hashed lineage"):
tests/core/rendering/test_contracts.py:834:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:835:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:838:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:841:            artifact_profiles={
tests/core/rendering/test_contracts.py:846:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:849:            artifact_profiles={
tests/core/rendering/test_contracts.py:858:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:861:            artifact_profiles={
tests/core/rendering/test_contracts.py:870:    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
tests/core/rendering/test_contracts.py:871:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:876:            artifact_profiles=[
tests/core/rendering/test_contracts.py:887:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:890:            artifact_profiles={
tests/core/rendering/test_contracts.py:901:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:904:            artifact_profiles={
tests/core/rendering/test_contracts.py:917:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:920:            artifact_profiles={
tests/core/rendering/test_contracts.py:936:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:941:            artifact_profiles=[
tests/core/rendering/test_contracts.py:974:    with pytest.raises(ValueError, match="workspace path"):
tests/core/rendering/test_contracts.py:975:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:978:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:981:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:986:            artifact_profiles=[
tests/core/rendering/test_contracts.py:993:    with pytest.raises(ValueError, match="workspace path"):
tests/core/rendering/test_contracts.py:1001:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:1004:            artifact_profiles=[mutated],
tests/core/rendering/test_contracts.py:1009:        assemble_provenance_v2(
tests/core/rendering/test_contracts.py:1012:            artifact_profiles=[],
tests/core/rendering/test_contracts.py:1087:def test_manifest_round_trip() -> None:
docs/guides/build-your-first-agentic-ux.md:308:- **Capability provenance**: inspect `capability.handle.provenance`
tests/test_provenance_fields.py:4:Verifies that to_capability_handle() reads fork/provenance/edit-state fields
tests/test_provenance_fields.py:117:# Executor provenance fields
tests/test_provenance_fields.py:125:        """Without fork metadata, provenance fields are None."""
tests/test_provenance_fields.py:128:        assert h.provenance.forked_from is None
tests/test_provenance_fields.py:129:        assert h.provenance.upstream_version is None
tests/test_provenance_fields.py:130:        assert h.provenance.compatibility_token is None
tests/test_provenance_fields.py:143:        assert h.provenance.forked_from == "builtin.original_render"
tests/test_provenance_fields.py:144:        assert h.provenance.upstream_version == "2.3.0"
tests/test_provenance_fields.py:145:        assert h.provenance.compatibility_token == "abc123def"
tests/test_provenance_fields.py:158:        assert h.provenance.forked_from is None
tests/test_provenance_fields.py:159:        assert h.provenance.upstream_version is None
tests/test_provenance_fields.py:160:        assert h.provenance.compatibility_token is None
tests/test_provenance_fields.py:200:# Orchestrator provenance fields
tests/test_provenance_fields.py:210:        assert h.provenance.forked_from is None
tests/test_provenance_fields.py:211:        assert h.provenance.upstream_version is None
tests/test_provenance_fields.py:212:        assert h.provenance.compatibility_token is None
tests/test_provenance_fields.py:224:        assert h.provenance.forked_from == "builtin.original_pipeline"
tests/test_provenance_fields.py:225:        assert h.provenance.upstream_version == "3.0.0"
tests/test_provenance_fields.py:226:        assert h.provenance.compatibility_token == "tok123"
tests/test_provenance_fields.py:238:        assert h.provenance.forked_from is None
tests/test_provenance_fields.py:239:        assert h.provenance.upstream_version is None
tests/test_provenance_fields.py:240:        assert h.provenance.compatibility_token is None
tests/test_provenance_fields.py:256:# Element provenance fields
tests/test_provenance_fields.py:266:        assert h.provenance.forked_from is None
tests/test_provenance_fields.py:267:        assert h.provenance.upstream_version is None
tests/test_provenance_fields.py:268:        assert h.provenance.compatibility_token is None
tests/test_provenance_fields.py:282:        assert h.provenance.forked_from == "effects/old_blur"
tests/test_provenance_fields.py:283:        assert h.provenance.upstream_version == "0.9.0"
tests/test_provenance_fields.py:284:        assert h.provenance.compatibility_token == "elem_tok"
tests/test_provenance_fields.py:297:        assert h.provenance.forked_from is None
tests/test_provenance_fields.py:298:        assert h.provenance.upstream_version is None
tests/test_provenance_fields.py:299:        assert h.provenance.compatibility_token is None
tests/test_provenance_fields.py:321:    """All three adapters handle provenance fields identically."""
tests/test_provenance_fields.py:336:            assert h.provenance.forked_from == "builtin.original"
tests/test_provenance_fields.py:337:            assert h.provenance.upstream_version == "2.0.0"
tests/test_provenance_fields.py:338:            assert h.provenance.compatibility_token == "shared_token"
docs/guides/discovery-for-agents.md:93:The JSON output merges `_capability` (identity, provenance, deprecation,
docs/guides/discovery-for-agents.md:111:- `provenance` — `source` (pack or active_theme), `version`, `content_root`
tests/core/integrations/test_arnold_session_compiler.py:39:    lineage: tuple[str, ...] = ()
tests/core/integrations/test_arnold_session_compiler.py:2730:    # 3. compile_to_path JSON round-trips through load_plan
tests/test_runtime_correctness_inventory.py:104:        "astrid/core/threads/provenance.py",
.oracle/findings/_report.json:155:      "brief": "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/04-provenance-consumers.md",
.oracle/findings/_report.json:161:      "meta_file": "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/findings/04-provenance-consumers.meta.json",
.oracle/findings/_report.json:193:      "response_file": "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/findings/04-provenance-consumers.txt",
.oracle/findings/_report.json:196:      "stem": "04-provenance-consumers",
tests/core/integrations/test_arnold_host_cli_start.py:39:    lineage: tuple[str, ...] = ()
tests/core/integrations/test_arnold_host_cli_start.py:675:                        "event_lineage": {"segment_start_hash": "sha256:111"},
tests/core/integrations/test_arnold_host_cli_start.py:689:                        "event_lineage": {
tests/core/integrations/test_arnold_host_cli_start.py:804:def test_arnold_next_routes_session_runs_by_mode_and_renders_segment_lineage(
tests/core/integrations/test_arnold_host_cli_start.py:822:    assert "successor lineage:\n  seg-001 -> seg-002" in stdout
tests/core/integrations/test_arnold_host_cli_start.py:1103:        "lineage": ["seg-001", "seg-002"],
tests/test_capability_alias_resolver.py:1700:            assert cap["provenance"]["resolved_alias"] == "builtin.render"
tests/test_capability_alias_resolver.py:1762:            assert cap["provenance"]["resolved_alias"] == "builtin.hype"
tests/core/integrations/test_arnold_host_registry_and_shapes.py:34:    lineage: tuple[str, ...] = ()
tests/test_dirty_detection.py:119:    """write_fork_state() and read_fork_state() round-trip."""
tests/test_dirty_detection.py:121:    def test_write_and_read_round_trip(self):
tests/core/test_executor_schema_capabilities.py:27:    def test_clip_kinds_and_requirements_round_trip(self) -> None:
tests/core/test_executor_schema_capabilities.py:70:    def test_deprecated_produces_for_alias_normalizes_without_round_trip(self) -> None:
tests/test_managed_write_paths.py:351:        """Agent actor with human via preserves chained provenance."""
tests/test_structure_contracts.py:623:    all 10 lineage symbols must remain intact.
tests/test_structure_contracts.py:639:    missing_lineage = _LINEAGE_SYMBOLS - public
tests/test_structure_contracts.py:640:    assert not missing_lineage, (
tests/test_structure_contracts.py:642:        f"{sorted(missing_lineage)}"
tests/test_structure_contracts.py:664:    At the same time, the test must NOT flag legitimate lineage re-exports
tests/test_structure_contracts.py:694:    # Stub lineage modules so AST scans on the synthetic tree don't choke
tests/core/integrations/test_arnold_host_compat.py:106:    assert "RuntimeEnvelope.cross_cutting missing field(s): lineage" in message
tests/core/integrations/test_arnold_host_compat.py:119:        lineage = None
tests/core/integrations/test_arnold_host_compat.py:200:        lineage = None
tests/core/integrations/test_arnold_session_ledger.py:5:  * Manifest round-trip (write → read → all fields preserved)
tests/core/integrations/test_arnold_session_ledger.py:207:    def test_arnold_run_round_trip_preserves_extra_fields(self, tmp_path: Path) -> None:
tests/core/integrations/test_arnold_session_ledger.py:225:# Manifest round-trip
tests/core/integrations/test_arnold_session_ledger.py:231:    def test_empty_manifest_round_trip(self, tmp_path: Path) -> None:
tests/core/integrations/test_arnold_session_ledger.py:242:    def test_manifest_with_segments_round_trip(self, tmp_path: Path) -> None:
tests/core/integrations/test_arnold_session_ledger.py:243:        """Manifest with two segment records round-trips all fields."""
tests/core/integrations/test_arnold_session_ledger.py:260:            event_lineage=EventLineageHashes(
tests/core/integrations/test_arnold_session_ledger.py:315:        assert s1.event_lineage.segment_start_hash == "sha256:start1"
tests/core/integrations/test_arnold_session_ledger.py:316:        assert s1.event_lineage.segment_boundary_hash == "sha256:boundary1"
tests/core/integrations/test_arnold_session_ledger.py:415:    def test_state_file_write_and_read_round_trip(self, tmp_path: Path) -> None:
docs/architecture/timeline-visualization-plan.md:270:### Snapshot and lineage semantics
docs/architecture/timeline-visualization-plan.md:292:creates a new lineage. If current state differs, the old lineage remains valid
docs/architecture/timeline-visualization-plan.md:361:transcript provenance is missing, a group member is absent, or extraction is
docs/architecture/timeline-visualization-plan.md:583:   `sources.<asset>.transcript_ref` and cut provenance such as
docs/architecture/timeline-visualization-plan.md:834:   transcript provenance, and mapped speech occurrences.
docs/architecture/timeline-visualization-plan.md:932:  preservation, missing provenance, and separation from authored captions;
docs/architecture/timeline-visualization-plan.md:966:- snapshot lineage and source hashes survive every drill-down unchanged;
docs/architecture/timeline-visualization-plan.md:985:  versus rendered filmstrip provenance. They also cover the complete
docs/architecture/timeline-visualization-plan.md:1036:- `refresh_root` creates a distinct current-state lineage;
docs/architecture/timeline-visualization-plan.md:1089:    uninspected baked-in text remain distinguishable and provenance-linked;
docs/architecture/timeline-visualization-plan.md:1091:    thumbnail for an original, or guesses missing transcript provenance;
tests/core/integrations/test_arnold_host_driver.py:40:    lineage = []
tests/test_current_run.py:27:def test_write_and_read_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
docs/architecture/timeline-event-sourcing/m1-schema.md:141:3. **Canonical JSON authoritative form.** Python-side canonicalization is authoritative. Rules: sorted keys, UTF-8 bytes, compact separators `","` and `":"`, no trailing whitespace, no NaN/Inf, numbers preserve their parsed source form (integers as int, floats as float, no `1.0` to `1` coercion), `null` values are omitted from canonical form, and the `hash` field itself is excluded. Postgres-side hashing in m6's RPC must use a stored procedure that produces the byte-identical form, either PL/pgSQL or a small extension. Cross-backend hash parity is enforced by m8 round-trip tests against shared golden fixtures introduced in m4.
docs/architecture/timeline-event-sourcing/m1-schema.md:146:   For chained provenance such as human -> agent -> worker, the proximate actor wins in `actor`, and the chain is carried in optional `actor.via: [...]`. This schema is codified in the canonical event schema package.
tests/core/test_project_schema.py:237:def test_build_and_validate_run_record_round_trip() -> None:
tests/core/test_project_schema.py:267:def test_run_record_provenance_defaults_round_trip() -> None:
tests/core/test_project_schema.py:343:def test_default_timeline_id_round_trip_none() -> None:
tests/core/test_project_schema.py:353:def test_default_timeline_id_round_trip_ulid() -> None:
tests/core/test_project_schema.py:408:def test_managed_binding_metadata_round_trip() -> None:
tests/core/test_project_schema.py:409:    """metadata.timeline_slug, timeline_event_stream_id, timeline_binding_mode round-trip."""
tests/core/test_project_schema.py:436:def test_managed_binding_metadata_with_timeline_id_round_trip() -> None:
tests/core/integrations/test_arnold_step_adapter.py:605:    def test_invoke_records_cas_identity_provenance_from_default_project(
tests/core/integrations/test_arnold_step_adapter.py:608:        """Identity provenance records resolved project root and canonical digests."""
tests/core/integrations/test_arnold_step_adapter.py:686:        assert result.contract_result.provenance.chain == (
tests/core/integrations/test_arnold_host_hooks.py:37:    lineage: tuple[str, ...] = ()
tests/core/integrations/test_arnold_host_hooks.py:94:    provenance: _Provenance = field(default_factory=_Provenance)
tests/core/integrations/test_arnold_session_succession.py:149:                    event_lineage=EventLineageHashes(segment_start_hash=str(started["hash"])),
tests/core/integrations/test_arnold_host_invocation.py:33:    lineage: tuple[str, ...] = ()
tests/core/integrations/test_arnold_host_invocation.py:375:def test_human_resume_schema_and_payload_round_trip(
tests/core/experiments/test_normalize.py:1521:                "kind": "ambiguous_provenance",
tests/core/experiments/test_normalize.py:1533:            "kind": "ambiguous_provenance",
tests/core/integrations/test_arnold_host_envelope.py:37:    lineage: tuple[str, ...] = ()
tests/core/integrations/test_arnold_host_envelope.py:222:    assert envelope.cross_cutting.lineage == ("sha256:111", "sha256:222")
tests/core/integrations/test_arnold_host_envelope.py:267:        "lineage": ["sha256:111", "sha256:222"],
docs/architecture/timeline-event-sourcing/m6-reigh-sync.md:29:4. **Canonical JSON parity.** Server-side hashing must byte-match the Python canonical serializer from m1. Use a stored procedure in PL/pgSQL or a small extension to produce the exact canonical JSON form. Cross-backend round-trip tests consume m4's golden fixtures unchanged.
docs/architecture/timeline-event-sourcing/m6-reigh-sync.md:105:5. Cross-backend round-trip tests consume m4's golden fixtures unchanged.
tests/core/experiments/test_capture.py:110:        assert "ambiguous_provenance" in kinds
tests/core/integrations/test_arnold_conformance.py:9:   schema-hash round-trips, required vocabulary items, the every-stage-vocabulary
tests/core/integrations/test_arnold_conformance.py:191:def test_contract_result_schema_hash_round_trips_through_public_version_constant(
tests/core/integrations/test_arnold_conformance.py:601:    use for schema-hash round-trips.
tests/core/test_orchestrator_plan_template_builders.py:54:def test_builtin_task_templates_round_trip_through_kernel(tmp_path: Path) -> None:
docs/architecture/test-relocation-map.json:1461:      "file": "test_provenance_fields.py",
docs/architecture/test-relocation-map.json:1463:      "rationale": "Provenance fields — cross-cutting threads/lineage concern."
docs/architecture/test-relocation-map.json:1601:      "file": "test_threads_provenance.py",
docs/architecture/test-relocation-map.json:1603:      "rationale": "Threads provenance."
tests/core/integrations/test_arnold_session_driver.py:55:    lineage: tuple[str, ...] = ()
tests/core/integrations/test_arnold_session_driver.py:361:                    event_lineage=EventLineageHashes(
tests/core/integrations/test_arnold_session_driver.py:449:    assert manifest["segments"][1]["event_lineage"]["segment_boundary_hash"] == result.boundary_hash
docs/architecture/repo-shape.md:42:| `astrid.core.threads.cli` | `astrid/core/threads/cli.py` | **Threads CLI** — thread index and lineage commands. |
docs/architecture/repo-shape.md:145:| `astrid/core/audit/` | **Shared library** | Run-local provenance ledger, graph, transport, and HTML report. |
docs/architecture/repo-shape.md:146:| `astrid/core/threads/` | **Lineage and thread management** | Thread index, ID generation (ULID), provenance tracking, record schema. The m5a milestone removed thread wrapper symbols from the public surface; only 10 lineage symbols remain in `astrid.core.threads.__all__`. |
docs/architecture/repo-shape.md:152:| `astrid/core/paths.py` | **Shared library** | Repository and workspace path resolution. |
tests/core/experiments/test_evaluation.py:257:    """Phase 2 exit: scores and notes survive a build→validate round trip
tests/test_task_gate_command_match.py:72:def test_command_for_argv_round_trips_through_match() -> None:
docs/architecture/provider-independent-generation-experiments-plan.md:28:`manifest.json`, generation executors, task events, or lineage.
docs/architecture/provider-independent-generation-experiments-plan.md:84:- **Capture gap:** Missing or ambiguous provenance that prevents a reliable
docs/architecture/provider-independent-generation-experiments-plan.md:107:- Treating lineage completeness as aesthetic quality.
docs/architecture/provider-independent-generation-experiments-plan.md:151:Existing lineage can connect causal derivations and selected ancestors.
docs/architecture/provider-independent-generation-experiments-plan.md:153:schema must not write an unsupported `variant` lineage kind.
docs/architecture/provider-independent-generation-experiments-plan.md:179:  provenance quality and renderer fallbacks, not inference cases.
docs/architecture/provider-independent-generation-experiments-plan.md:192:- Existing iteration quality measures provenance completeness, not creative
docs/architecture/provider-independent-generation-experiments-plan.md:692:│ rubric scores · verdict · notes · provenance · warnings │
docs/architecture/provider-independent-generation-experiments-plan.md:701:- Missing provenance and ambiguous legacy associations.
docs/architecture/provider-independent-generation-experiments-plan.md:763:- Unknown additive fields round-trip.
docs/architecture/test-layout.md:168:| `test_threads_provenance.py` | 163 | Threads provenance |
docs/architecture/test-layout.md:186:| `test_provenance_fields.py` | 109 | Provenance fields — cross-cutting threads/lineage concern |
astrid/packs/generation/skill/SKILL.md:144:Every generated file carries its own provenance, so an image stays identifiable
tests/test_task_kernel_gate.py:22:def test_five_event_hash_chain_append_verify_round_trip(tmp_path: Path) -> None:
tests/test_astrid_error_contract.py:375:    """Every migrated error class round-trips through coerce_astrid_error."""
tests/test_astrid_error_contract.py:387:        # envelope round-trip
docs/architecture/hivemind-hybrid-search-plan.md:771:arbitrary `payload`, local `corpus_path`, or other operational provenance
docs/architecture/hivemind-hybrid-search-plan.md:825:   VibeComfy workflow JSON, ready-template source, `corpus_path`, or provenance
docs/architecture/hivemind-hybrid-search-plan.md:848:  provenance, representation version, and SHA-256 hashes where authorized.
docs/architecture/hivemind-hybrid-search-plan.md:1401:| 1.10 | Add SQL plan, unit, integration, timeout, workflow-only/single-workflow/code-snippet/security, Snowflake round-trip, and deterministic-order tests. | **Medium** | 1.7–1.9 | Tests pass, ambiguous `item_ids` are rejected, quarantined code never ranks, and saved `EXPLAIN (ANALYZE, BUFFERS)` plans show index use. |
docs/architecture/hivemind-hybrid-search-plan.md:1868:- All returned Discord snowflakes survive JSON round-trips exactly.
tests/test_supabase_data_provider.py:56:    def test_returns_config_and_version_round_tripped(self) -> None:
tests/timeline/test_branch.py:4:- Branch creation writes provenance: branched identity
tests/timeline/test_branch.py:8:- Normal provenance: created invariant remains intact
tests/timeline/test_branch.py:34:    """Tests for branch provenance invariants."""
tests/timeline/test_branch.py:36:    def test_branch_identity_has_provenance_branched(self, tmp_path: Path, monkeypatch):
tests/timeline/test_branch.py:37:        """Branch creation writes assembly.identity.json with provenance: branched."""
tests/timeline/test_branch.py:48:            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
tests/timeline/test_branch.py:121:        # Verify branch identity has provenance: branched
tests/timeline/test_branch.py:126:        assert identity["provenance"] == "branched"
tests/timeline/test_branch.py:142:            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
tests/timeline/test_branch.py:230:            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
tests/timeline/test_branch.py:317:            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
tests/timeline/test_branch.py:397:            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
tests/timeline/test_branch.py:461:            {"schema_version": 1, "timeline_id": timeline_id, "timeline_ulid": "01J00000000000000000000001", "backend": "local_fs", "provenance": "created", "created_at": "2026-05-21T00:00:00Z"},
docs/architecture/asset-library-architecture.md:18:             │        │  owner {kind,id}                   │  provenance
docs/architecture/asset-library-architecture.md:21:             │   │             role · view · status · provenance   │
docs/architecture/asset-library-architecture.md:49:| `sources/`, `add_source`, `register_source_file` (`core/project/source.py`, `project.py`) | durable media store | `promote_source_file` — **physical copy**, sha256 dedupe, stable `src-<ULID>`, `promoted_from` provenance |
docs/architecture/asset-library-architecture.md:54:| Reference role vocabulary (`core/experiments/schema.py:43`) | reference roles | `view` orthogonal to role; provenance slot on the edge |
docs/architecture/asset-library-architecture.md:58:| `project/run.py` — `finalize_project_run`, `mirror_hype_artifacts`, `record_contributing_run`, `bind_managed_timeline` | provenance + run→timeline linkage | provenance records carry the binding context for auto-`candidate` (Q4) |
docs/architecture/asset-library-architecture.md:128:choice keeps the provenance graph honest without inventing a churn problem?
tests/test_sdk_public_surface.py:94:            provenance=astrid_module.Provenance(source="test"),
tests/test_sdk_public_surface.py:1354:    # round-trip serialization
tests/test_sdk_public_surface.py:1469:    """``discover().to_dict()`` must round-trip through json and still
docs/architecture/asset-library-design.md:33:| **Sources** (exists) | media bytes, hashes, provenance | `projects/<slug>/sources/`, content-addressed `src-<ULID>` |
docs/architecture/asset-library-design.md:134:### Q5 — Primitive granularity. **Take ⊂ Reference iff the edge carries provenance.**
docs/architecture/asset-library-design.md:135:Reference needs a provenance slot (generation id, prompt hash, parent take).
docs/architecture/asset-library-design.md:136:**Tripwire:** when provenance forces its own record anyway → promote Take to
docs/architecture/asset-library-design.md:276:editor round-trip test.
docs/architecture/asset-library-design.md:309:downstream (resolution, provenance, agent reasoning) trusts canon. The apparent
docs/architecture/asset-library-design.md:425:resources, provenance cross-refs.
tests/test_capability_handle.py:115:# CapabilityHandle.to_dict() round-trip
tests/test_capability_handle.py:137:            provenance=prov,
tests/test_capability_handle.py:161:        assert d["provenance"]["source"] == "pack"
tests/test_capability_handle.py:162:        assert d["provenance"]["pack_id"] == "builtin"
tests/test_capability_handle.py:188:            provenance=Provenance(source="pack"),
tests/test_capability_handle.py:192:        assert isinstance(d["provenance"], dict)
tests/test_capability_handle.py:193:        assert d["provenance"]["source"] == "pack"
tests/test_capability_handle.py:260:    def test_provenance_source_from_metadata(self):
tests/test_capability_handle.py:263:        assert h.provenance.source == "pack"
tests/test_capability_handle.py:265:    def test_provenance_source_defaults_to_pack(self):
tests/test_capability_handle.py:268:        assert h.provenance.source == "pack"
tests/test_capability_handle.py:270:    def test_provenance_empty_defaults(self):
tests/test_capability_handle.py:274:        assert h.provenance.manifest_path == ""
tests/test_capability_handle.py:275:        assert h.provenance.content_root == ""
tests/test_capability_handle.py:321:    def test_provenance_source_from_metadata(self):
tests/test_capability_handle.py:324:        assert h.provenance.source == "pack"
tests/test_capability_handle.py:326:    def test_provenance_source_defaults_to_pack(self):
tests/test_capability_handle.py:329:        assert h.provenance.source == "pack"
tests/test_capability_handle.py:331:    def test_provenance_empty_defaults(self):
tests/test_capability_handle.py:334:        assert h.provenance.manifest_path == ""
tests/test_capability_handle.py:335:        assert h.provenance.content_root == ""
tests/test_capability_handle.py:414:    def test_provenance_source_preserved_as_is(self):
tests/test_capability_handle.py:415:        """Element provenance.source is passed through from definition.source."""
tests/test_capability_handle.py:418:        assert h.provenance.source == "pack:builtin"
tests/test_capability_handle.py:420:    def test_provenance_source_active_theme(self):
tests/test_capability_handle.py:421:        """active_theme is a valid provenance.source for elements."""
tests/test_capability_handle.py:424:        assert h.provenance.source == "active_theme"
tests/test_capability_handle.py:426:    def test_provenance_source_asymmetry(self):
tests/test_capability_handle.py:427:        """Executor provenance.source is 'pack', while element can be
tests/test_capability_handle.py:435:        assert ex_h.provenance.source == "pack"
tests/test_capability_handle.py:436:        assert el_h.provenance.source == "pack:builtin"
tests/test_capability_handle.py:451:    def test_provenance_empty_defaults(self):
tests/test_capability_handle.py:454:        assert h.provenance.manifest_path == ""
tests/test_capability_handle.py:455:        assert h.provenance.content_root == ""
tests/test_capability_handle.py:505:            assert isinstance(h.provenance, Provenance)
tests/test_capability_handle.py:510:            assert "provenance" in d
tests/timeline/test_cut_timeline_resume.py:102:        # when missing. Other fields (theme slug, clips, tracks) round-trip
tests/timeline/test_cut_timeline_resume.py:397:    # Resume-mode registry preservation — extended metadata round-trip
astrid/packs/video_editing/executors/cut/timeline_build.py:461:            "pool_provenance": {
astrid/packs/video_editing/executors/cut/timeline_build.py:581:    provenance on the emitted events.
docs/packs/aliases-vs-forks-vs-overrides.md:136:This provenance powers dirty detection (see [fork-and-update.md](fork-and-update.md)).
docs/packs/aliases-vs-forks-vs-overrides.md:221:definition, with alias metadata attached to the capability handle's provenance
docs/packs/fork-and-update.md:67:This provenance powers dirty detection (see below).
tests/test_onboarding_parity.py:7:and the complete tutorial path round-trips without errors.
tests/test_onboarding_parity.py:322:def test_editorial_arrange_handle_has_provenance() -> None:
tests/test_onboarding_parity.py:323:    """The capability handle for ``editorial.arrange`` must carry provenance."""
tests/test_onboarding_parity.py:330:    prov = handle.provenance
tests/test_onboarding_parity.py:595:def test_full_tutorial_path_round_trips(tmp_path: Path) -> None:
tests/test_onboarding_parity.py:775:# Security and trust disclosures: capability provenance
tests/test_onboarding_parity.py:780:def test_provenance_is_populated_on_editorial_arrange() -> None:
tests/test_onboarding_parity.py:781:    """The provenance on editorial.arrange must be populated (not default
tests/test_onboarding_parity.py:788:    prov = cap.handle.provenance
tests/timeline/test_backend_performance.py:49:            "provenance": "imported",
tests/timeline/test_backend_performance.py:154:            "provenance": "imported",
tests/timeline/test_backend_performance.py:200:            "provenance": "imported",
docs/packs/creating-packs.md:323:All scaffold commands validate their output. A round-trip of
tests/test_skills.py:434:    def test_state_round_trip(self) -> None:
astrid/packs/video_editing/executors/cut/run.py:139:        help="Optional JSON TimelineActor for upstream provenance chaining (actor.via).",
tests/timeline/test_timeline_roundtrip_fixture.py:5:1. `examples/hype.timeline.full.json` round-trips load -> dump
tests/timeline/test_timeline_roundtrip_fixture.py:83:    # 1. Byte-equivalent round-trip
tests/timeline/test_timeline_roundtrip_fixture.py:85:    def test_round_trip_is_byte_equivalent(self) -> None:
tests/timeline/test_timeline_roundtrip_fixture.py:125:                f"section {section!r} drifted after round-trip",
docs/packs/contract.md:45:  provenance back to its source and can diverge.
docs/packs/contract.md:89:- `provenance`: source, manifest path, content root, fork source, and override
docs/packs/contract.md:114:- provenance and manifest path;
docs/packs/contract.md:169:  pack, alias/deprecation state, provenance, inputs/outputs, and safety data;
docs/packs/contract.md:202:  metadata for registries to attach pack provenance.

exec
/bin/zsh -lc "rg -n -C 12 \"artifact_profiles|hashed artifact|lineage\" docs/contracts/render-backend-v1.md .oracle/plan.md .oracle/briefs/batch-1-r*.md | head -n 500; git log --oneline --decorate -12; git show 788501c:astrid/core/rendering/provenance.py | nl -ba | sed -n '100,215p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/briefs/batch-1-r1-t1.2.md-20-but `FinalizeRequest` carries only `list[VideoArtifact]` — a standalone
.oracle/briefs/batch-1-r1-t1.2.md-21-finalizer cannot preserve result-level attachments, and collisions across
.oracle/briefs/batch-1-r1-t1.2.md-22-segment artifacts are unchecked.
.oracle/briefs/batch-1-r1-t1.2.md-23-
.oracle/briefs/batch-1-r1-t1.2.md-24-Rework: establish ONE authoritative attachment surface. Cleanest: make
.oracle/briefs/batch-1-r1-t1.2.md-25-`FinalizeRequest` carry complete per-segment result envelopes (segment
.oracle/briefs/batch-1-r1-t1.2.md-26-video artifact + its attachments + namespaced fragments) OR move all
.oracle/briefs/batch-1-r1-t1.2.md-27-attachments onto `VideoArtifact`. Enforce GLOBAL attachment name uniqueness
.oracle/briefs/batch-1-r1-t1.2.md-28-across segments and preservation through finalization, with round-trip
.oracle/briefs/batch-1-r1-t1.2.md-29-tests. Update `finalize.json` schema and `docs/contracts/render-backend-v1.md`
.oracle/briefs/batch-1-r1-t1.2.md-30-accordingly.
.oracle/briefs/batch-1-r1-t1.2.md-31-
.oracle/briefs/batch-1-r1-t1.2.md:32:## Issue 4 — Provenance cannot represent routing/replay lineage
.oracle/briefs/batch-1-r1-t1.2.md-33-
.oracle/briefs/batch-1-r1-t1.2.md-34-Current provenance has only singular `resolved_backend`, `source_pack`,
.oracle/briefs/batch-1-r1-t1.2.md-35-`manifest_digest` keys — a hybrid plan with MULTIPLE renderer invocations
.oracle/briefs/batch-1-r1-t1.2.md-36-cannot represent resolved identity per segment without collapsing evidence.
.oracle/briefs/batch-1-r1-t1.2.md-37-
.oracle/briefs/batch-1-r1-t1.2.md-38-Rework: freeze explicit records in provenance v2 (in `provenance.py` and the
.oracle/briefs/batch-1-r1-t1.2.md-39-result/plan contracts):
.oracle/briefs/batch-1-r1-t1.2.md-40-- `planner`: `{id, source_pack, manifest_digest, trust_eligibility}`;
.oracle/briefs/batch-1-r1-t1.2.md-41-- `segments[]`: each with `{window, renderer: {id, source_pack,
.oracle/briefs/batch-1-r1-t1.2.md-42-  manifest_digest, alias_chain, override, support_decision},
.oracle/briefs/batch-1-r1-t1.2.md-43-  input_hashes}`;
.oracle/briefs/batch-1-r1-t1.2.md-44-- `finalizer`: `{id, source_pack, manifest_digest}`;
--
.oracle/plan.md-148-  - Eliminate the broad `commonpath` server root by hardlinking or copying only required local assets into the invocation stage. Leave existing remote URLs remote.
.oracle/plan.md-149-  - Add one canonical resolved render profile using the same merged theme/timeline canvas consumed by Remotion. Planner, backend requests, and finalizer all receive that profile.
.oracle/plan.md-150-  - Extend `astrid/core/media.py` with fields already available in cut probing: codec, average/rational FPS, pixel format, time base, audio codec/rate/layout, duration, and dimensions.
.oracle/plan.md-151-  - Add renderer-local artifact enforcement for existence, non-empty output, workspace containment, symlinks, hashes, duration, video profile, and audio ownership.
.oracle/plan.md-152-  - Do not change missing-output semantics for all executors globally; `rendering.render` must fail before returning success.
.oracle/plan.md-153-  - Add a locked publication helper in which the sidecar is the final commit marker.
.oracle/plan.md-154-  - Gate: local/cached/remote assets, Range requests, expired URLs, restricted serving, server-start failure, cleanup, invalid artifacts, visual-only modes, attachments, and crash-orphan recovery pass.
.oracle/plan.md-155-
.oracle/plan.md-156-- [ ] **M1-05 — Extract and register `rendering.remotion`**
.oracle/plan.md-157-
.oracle/plan.md-158-  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
.oracle/plan.md-159-  - Register it through `extensions.rendering` and a static renderer manifest using the raw command protocol.
.oracle/plan.md:160:  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
.oracle/plan.md-161-  - Put props and asset staging under the unique invocation workdir.
.oracle/plan.md-162-  - Introduce one outer cross-process lock for generated Remotion sources:
.oracle/plan.md-163-    - acquire it before reading registry state or checking generated outputs;
.oracle/plan.md-164-    - cover the three package registries, shim families, active-theme symlink/text pointer, and registry state;
.oracle/plan.md-165-    - hold it through active-theme selection and the complete Remotion render;
.oracle/plan.md-166-    - write registry state atomically;
.oracle/plan.md-167-    - make the developer `gen-types` path acquire the same outer lock across `types.generated.ts` and effect-registry generation;
.oracle/plan.md-168-    - ensure generator primitives do not recursively acquire the lock.
.oracle/plan.md-169-  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
.oracle/plan.md-170-  - Move private-helper tests to extracted boundaries while keeping a small facade compatibility suite.
.oracle/plan.md-171-  - Gate: registry invalidation, atomic state, theme/profile parity, effect assets, environment redaction, concurrent differing-theme renders, render-versus-`gen-types` contention, success/failure cleanup, output validation, Remotion typecheck, and an available fixture render pass.
.oracle/plan.md-172-
--
.oracle/briefs/batch-1-r2-t1.2.md-38-  `_stage_installed_fixture`); tests must run against the REAL committed
.oracle/briefs/batch-1-r2-t1.2.md-39-  fixtures (`tests/fixtures/renderer_packs/discovery/`), which declare
.oracle/briefs/batch-1-r2-t1.2.md-40-  `rendering.legacy_hybrid`, `rendering.ffmpeg-finalizer`,
.oracle/briefs/batch-1-r2-t1.2.md-41-  `cycle_render`, `env_render`, etc.
.oracle/briefs/batch-1-r2-t1.2.md-42-- Restore/adjust any test that asserted underscore rejection; the grammar
.oracle/briefs/batch-1-r2-t1.2.md-43-  now accepts both. `rendering.ffmpeg_finalizer` and `rendering.legacy-hybrid`
.oracle/briefs/batch-1-r2-t1.2.md-44-  are both VALID ids now (spelling canonicality is separate from validity).
.oracle/briefs/batch-1-r2-t1.2.md-45-- Prove `validate_pack` and the CLI validation path accept the REAL committed
.oracle/briefs/batch-1-r2-t1.2.md-46-  discovery fixture packs (no rewriting).
.oracle/briefs/batch-1-r2-t1.2.md-47-- Re-run the full `tests/core/rendering` suite — all green with no runtime
.oracle/briefs/batch-1-r2-t1.2.md-48-  rewriting.
.oracle/briefs/batch-1-r2-t1.2.md-49-
.oracle/briefs/batch-1-r2-t1.2.md:50:## Issue 2 — Provenance regresses v1 and replay lineage incomplete
.oracle/briefs/batch-1-r2-t1.2.md-51-
.oracle/briefs/batch-1-r2-t1.2.md-52-`provenance.py` replaces the legacy `segments` key and overwrites nested
.oracle/briefs/batch-1-r2-t1.2.md-53-`segment_provenance` sidecars with `{engine,from,to}` projections, contradicting
.oracle/briefs/batch-1-r2-t1.2.md-54-the characterized legacy shapes (`tests/packs/rendering/test_legacy_renderer_characterization.py:385`).
.oracle/briefs/batch-1-r2-t1.2.md-55-
.oracle/briefs/batch-1-r2-t1.2.md-56-Rework:
.oracle/briefs/batch-1-r2-t1.2.md-57-- PRESERVE both v1 projections UNCHANGED: legacy `segments` and
.oracle/briefs/batch-1-r2-t1.2.md-58-  `segment_provenance` keep exactly the v1 shapes recorded in baseline.
.oracle/briefs/batch-1-r2-t1.2.md-59-- Add normalized v2 records under an ADDITIVE field (e.g.
.oracle/briefs/batch-1-r2-t1.2.md-60-  `segments_v2` or `render_plan`) — never overwrite v1 keys.
.oracle/briefs/batch-1-r2-t1.2.md-61-- Resolution records complete for ALL capability kinds: planner, each
.oracle/briefs/batch-1-r2-t1.2.md-62-  renderer invocation/segment, and finalizer each carry `{id, source_pack,
--
docs/contracts/render-backend-v1.md-456-assets, props, generated fragments, servers, subprocess groups, and staging
docs/contracts/render-backend-v1.md-457-directories have one host owner and are cleaned on success, failure, timeout,
docs/contracts/render-backend-v1.md-458-and interruption. Cleanup must not follow an unvalidated path or delete
docs/contracts/render-backend-v1.md-459-unrelated prior output. A crash can leave an orphan video, but never a sidecar
docs/contracts/render-backend-v1.md-460-claiming an incomplete artifact; the sidecar is the publication commit marker.
docs/contracts/render-backend-v1.md-461-
docs/contracts/render-backend-v1.md-462-## Provenance ownership and v1 compatibility
docs/contracts/render-backend-v1.md-463-
docs/contracts/render-backend-v1.md-464-Provenance v2 is additive and has `schema_version: 2`. Core owns and writes:
docs/contracts/render-backend-v1.md-465-
docs/contracts/render-backend-v1.md-466-`schema_version`, `engine`, `output`, `timeline`, `assets_registry`,
docs/contracts/render-backend-v1.md-467-`request_digest`, `requested_policy`, `planner`, `segments`, `segments_v2`,
docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
docs/contracts/render-backend-v1.md-469-`attachments`, and `backend_fragments`.
docs/contracts/render-backend-v1.md-470-
docs/contracts/render-backend-v1.md-471-`request_digest`, `requested_policy`, `planner`, every segment's nested
docs/contracts/render-backend-v1.md-472-`renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
docs/contracts/render-backend-v1.md-473-assembler accepts no parallel singular renderer identity. The nested records
docs/contracts/render-backend-v1.md-474-have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
docs/contracts/render-backend-v1.md-475-distinct source pack, manifest, alias/override, support, and input-hash evidence
docs/contracts/render-backend-v1.md-476-for every renderer invocation. Planner and finalizer records carry the same
docs/contracts/render-backend-v1.md-477-alias/override/trust/support evidence as renderer records. Rendered artifacts
docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
docs/contracts/render-backend-v1.md:479:hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
docs/contracts/render-backend-v1.md-480-sequence form (one VideoArtifact per segment); single-segment plans may use a
docs/contracts/render-backend-v1.md-481-path-keyed mapping. Every record carries its `path`, `profile`, a validated
docs/contracts/render-backend-v1.md-482-64-hex string `sha256`, and `attachments` — each attachment `{path, kind,
docs/contracts/render-backend-v1.md-483-sha256}` with a workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and
docs/contracts/render-backend-v1.md-484-globally unique names across all segment artifacts. All plan, artifact, and
docs/contracts/render-backend-v1.md-485-attachment values are reconstructed through their DTO validators at the
docs/contracts/render-backend-v1.md-486-provenance boundary (mutated frozen instances cannot bypass validation);
docs/contracts/render-backend-v1.md-487-duplicate paths, duplicate attachment names, path escapes, invalid kinds,
docs/contracts/render-backend-v1.md-488-profile-only entries, null/malformed hashes, and cardinality mismatches are
docs/contracts/render-backend-v1.md-489-rejected. All JSON Schema patterns are language-neutral (ECMAScript-valid;
docs/contracts/render-backend-v1.md-490-no Python-only anchors). Replay can verify rendered outputs byte-for-byte.
docs/contracts/render-backend-v1.md-491-`input_hashes` describe inputs only, never rendered outputs.
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6acd4be (HEAD -> oracle-run) batch1-rework10: oracle re-review9 issues 1-2 (VideoArtifact reconstruction via from_dict in both lineage forms, validated path emission, workspacePath \s whitespace components + leading-component rejection)
788501c batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
8418bae batch1-rework8: oracle re-review7 issues 1-3 (ordered path-keyed lineage w/ dup-path + cross-artifact attachment uniqueness, DTO reconstruction for attachments/profiles, trailing-LF schema anchors)
ab486f9 batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)
086d692 batch1-rework6: oracle re-review5 issues 1-3 (lineage required+shape-bound+path-bound, NUL-after-newline, hashMap/feature propertyNames, workspacePath newlines)
91f0fe3 batch1-rework5: oracle re-review4 issues 1-4 (override {from,to} coherence, validated hashed artifact lineage, remaining parity: leading-ws/multiline/NUL/propertyNames, installed-revision override proof)
808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
04767bf batch1-rework3: oracle re-review2 issues 1-3 (complete resolution records w/ trust+support, planner to_dict fix, nullable-string parity, segments_v2 prohibition, temp-fixture override regression)
88c75f3 batch1-rework2: oracle re-review issues 1-5 (real-fixture deconcealment, underscore-compatible ids, provenance v1 preservation + v2 additive, whitespace parity, transitive override routing, baseline C0 evidence)
b357de3 batch1-rework: oracle issues 1-9 (baseline facade ownership, contracts versioning/attachments/provenance, pack validation, transitive alias eligibility)
f8af4b2 (tag: C1) batch1: renderer contracts, schemas, pack extension, trusted registries, baseline characterization
efbfcaa (tag: C0) oracle: freeze stable plan + tasklist (megado phases 1-4)
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

codex
The incremental code is small, but one prior concern was broader than the host summary: ordered lineage emitted as JSON must remain consumable, and `\s` must mean the same thing outside Python. I’m probing those two exact boundaries now, including ECMAScript’s Unicode whitespace set.
exec
/bin/zsh -lc "python -c 'print(\"python_whitespace\", \" \".join(f\"U+{cp:04X}\" for cp in range(0x10000) if chr(cp).isspace())); print(\"python_strip_special\", [(f\"U+{cp:04X}\", bool(chr(cp).strip())) for cp in (0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff)])'
node -e 'const cps=[]; for(let cp=0;cp<0x10000;cp++){if(/"'^'"\\s"'$/u.test(String.fromCodePoint(cp)))cps.push("U+"+cp.toString(16).toUpperCase().padStart(4,"0"));} console.log("ecmascript_whitespace",cps.join(" ")); for(const cp of [0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff]) console.log("U+"+cp.toString(16).toUpperCase().padStart(4,"0"),/''^'"\\s"'$/u.test(String.fromCodePoint(cp)));'"'
python -c 'from astrid.core.rendering.contracts import _require_workspace_relative_path
for cp in (0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff):
 s=\"dir/\"+chr(cp)+\"/v.mp4\"
 try: _require_workspace_relative_path(s,\"p\"); dto=\"ACCEPT\"
 except Exception as e: dto=\"REJECT \"+type(e).__name__
 print(f\"U+{cp:04X}\",dto,repr(s))'
node -e 'const fs=require(\"fs\"); for(const fn of [\"result.json\",\"finalize.json\"]){const schema=JSON.parse(fs.readFileSync(\"astrid/core/rendering/schemas/v1/\"+fn,\"utf8\")); const re=new RegExp(schema.definitions.workspacePath.pattern,\"u\"); console.log(fn); for(const cp of [0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff]){const s=\"dir/\"+String.fromCodePoint(cp)+\"/v.mp4\"; console.log(\"U+\"+cp.toString(16).toUpperCase().padStart(4,\"0\"),re.test(s));}}'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 352ms:
python_whitespace U+0009 U+000A U+000B U+000C U+000D U+001C U+001D U+001E U+001F U+0020 U+0085 U+00A0 U+1680 U+2000 U+2001 U+2002 U+2003 U+2004 U+2005 U+2006 U+2007 U+2008 U+2009 U+200A U+2028 U+2029 U+202F U+205F U+3000
python_strip_special [('U+001C', False), ('U+001D', False), ('U+001E', False), ('U+001F', False), ('U+0085', False), ('U+FEFF', True)]
ecmascript_whitespace U+0009 U+000A U+000B U+000C U+000D U+0020 U+00A0 U+1680 U+2000 U+2001 U+2002 U+2003 U+2004 U+2005 U+2006 U+2007 U+2008 U+2009 U+200A U+2028 U+2029 U+202F U+205F U+3000 U+FEFF
U+001C false
U+001D false
U+001E false
U+001F false
U+0085 false
U+FEFF true
U+001C REJECT ValueError 'dir/\x1c/v.mp4'
U+001D REJECT ValueError 'dir/\x1d/v.mp4'
U+001E REJECT ValueError 'dir/\x1e/v.mp4'
U+001F REJECT ValueError 'dir/\x1f/v.mp4'
U+0085 REJECT ValueError 'dir/\x85/v.mp4'
U+FEFF ACCEPT 'dir/\ufeff/v.mp4'
result.json
U+001C true
U+001D true
U+001E true
U+001F true
U+0085 true
U+FEFF false
finalize.json
U+001C true
U+001D true
U+001E true
U+001F true
U+0085 true
U+FEFF false

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy
m=runpy.run_path(\"tests/core/rendering/test_contracts.py\")
A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
try: P(**base,artifact_profiles=first[\"artifact_profiles\"]); print(\"reconsume ACCEPT\")
except Exception as e: print(\"reconsume REJECT\",type(e).__name__,str(e))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 188ms:
emitted list ['dict', 'dict'] [{'path': 'outputs/a.mp4', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}, {'path': 'outputs/b.mp4', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc', 'attachments': {}}]
reconsume REJECT TypeError sequence artifact_profiles entries must be VideoArtifacts so lineage records stay path-keyed

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '180,285p'; rg -n \"def _require_string|_STRING\" astrid/core/rendering/contracts.py | head -n 30; rg -n -C 3 \"workspacePath\" tests/core/rendering/test_schema_roundtrip.py tests/core/rendering/test_contracts.py | head -n 200" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
217:def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
264:def _require_string_list(value: Any, label: str) -> list[str]:
270:def _require_string_mapping(value: Any, label: str) -> dict[str, str]:

exec
/bin/zsh -lc "rg -n '\"workspacePath\"|\\\\\\\\s\\\\\\\\\\]\\*/|must not contain empty or whitespace-only' astrid/core/rendering tests/fixtures docs/contracts/render-backend-v1.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
astrid/core/rendering/contracts.py:328:        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_schema_roundtrip.py | sed -n '1,380p'; git diff --numstat 788501c..6acd4be -- ':"'!.oracle/checkins/batch-1-r9.md'"'; git diff --check 788501c..6acd4be -- ':"'!.oracle/checkins/batch-1-r9.md'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
11	3	astrid/core/rendering/provenance.py
1	1	astrid/core/rendering/schemas/v1/finalize.json
1	1	astrid/core/rendering/schemas/v1/result.json
15	2	tests/core/rendering/test_contracts.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=10 788501c..6acd4be -- tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 2195b2b..3a87be3 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -981,22 +981,35 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
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
-    # A mutated RenderPlan instance is reconstructed at the boundary, so
-    # clearing its segments cannot bypass the positive-plan invariant.
+    # A mutated VideoArtifact instance is reconstructed at the boundary, so a
+    # smuggled escaped path cannot pass validation.
+    with pytest.raises(ValueError, match="workspace path"):
+        mutated = VideoArtifact(
+            path="outputs/a.mp4",
+            profile=_profile(audio=False),
+            sha256=SHA_B,
+            duration_frames=48,
+        )
+        object.__setattr__(mutated, "path", "../escape.mp4")
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles=[mutated],
+        )
     with pytest.raises(RendererProtocolError, match="positive-frame plan"):
         positive = _plan()
         object.__setattr__(positive, "segments", [])
         assemble_provenance_v2(
             **base,
             plan=positive,
             artifact_profiles=[],
         )
 
 

collab: Wait
codex
1. Multi-segment lineage still cannot round-trip: sequence input accepts only `VideoArtifact`, but output contains dictionaries. Repassing emitted `artifact_profiles` fails with `TypeError`. [provenance.py:153](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:153) [provenance.py:170](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:170)

2. `workspacePath` remains non-equivalent across languages. Python `str.strip()` and ECMAScript `\s` have different character sets: `"dir/\u0085/v.mp4"` is DTO-rejected but schema-accepted; `"dir/\uFEFF/v.mp4"` is DTO-accepted but schema-rejected. [contracts.py:327](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:327) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68)
tokens used
185,431
1. Multi-segment lineage still cannot round-trip: sequence input accepts only `VideoArtifact`, but output contains dictionaries. Repassing emitted `artifact_profiles` fails with `TypeError`. [provenance.py:153](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:153) [provenance.py:170](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:170)

2. `workspacePath` remains non-equivalent across languages. Python `str.strip()` and ECMAScript `\s` have different character sets: `"dir/\u0085/v.mp4"` is DTO-rejected but schema-accepted; `"dir/\uFEFF/v.mp4"` is DTO-accepted but schema-rejected. [contracts.py:327](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:327) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68)
