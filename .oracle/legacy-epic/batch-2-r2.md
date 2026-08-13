Reading additional input from stdin...
2026-08-12T06:18:50.249855Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:18:50.249891Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:18:50.249896Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff49f-a12e-7cb1-9892-6efd85142f54
--------
user
# Megado Checkpoint — Batch 2 second re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: `.oracle/checkins/batch-2.md` (6 issues), `.oracle/checkins/batch-2-r1.md` (5 issues). Second rework committed as `7f7c25d5` (prior head 5231a233). Incremental diff at /tmp/batch2-r2.diff.

## How each of your 5 re-review1 issues was addressed (host-implemented)

1. **Transport leaks process groups; SIGTERM-ignoring child survives; repeated KeyboardInterrupt escapes** →
   - `_wait_for_group_exit` now re-SIGKILLs in a loop until the group is gone (a group that ignores SIGKILL cannot exist on POSIX; if it survives the grace window, keep killing).
   - The reap drain loop is bounded (grace-or-2s deadline) and force-kills the direct child before breaking on repeated KeyboardInterrupt.
   - New test `test_sigterm_ignoring_child_is_escalated_and_reaped` (the existing sleep-tree fixture already ignores SIGTERM).
2. **Fixture misdeclares media profile** →
   - Request `render.json` audio_codec `sowt` → `pcm_s16le` (matches result).
   - Added a `chan` atom to the `sowt` sample entry; verified ffprobe reports width 1920, height 1080 (SPS crop 4 units), pcm_s16le 48kHz.
   - `media.py` probe now derives `channel_layout` from channel count when ffprobe reports none (QuickTime PCM limitation): 1→mono, 2→stereo, 6→5.1, 8→7.1. Strict validation now passes.
3. **support validation non-strict** →
   - Request must be a JSON object (non-object JSON → `protocol` error, no AttributeError).
   - `schema_version` must be an int (not bool/float) equal to 1.
4. **Production publishing follows output symlinks** →
   - run.py no longer resolves `out_path` before publication; the unresolved path reaches the symlink guard.
5. **Cleanup invisible sidecar symlinks** →
   - `_delete_previous_outputs` skips candidates whose raw sidecar path (as well as raw video path) is a symlink.

## Evidence

- Incremental diff: /tmp/batch2-r2.diff (9 files)
- Host-verified: test_transport (14) + raw fixture (6) + publication (7) + artifacts + media (75 combined) pass; full consolidated acceptance = 746 passed, 2 failed (SAME 2 pre-existing env-dependent failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Verify the six closures, especially the SIGKILL escalation (run the SIGTERM-ignoring test), the probe-accuracy (ffprobe on generated output vs declared profile), and the symlink guards on unresolved paths. If PASS, say exactly `PASS`.
codex
I’m using the Megado review protocol and the repository’s context-minimizing workflow. I’ll inspect the prior findings and incremental diff, then independently verify transport cleanup, media/profile accuracy, protocol validation, and both symlink boundaries without modifying the worktree.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc "sed -n '1,360p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

  → Read prior checkpoint findings and inspect commit/diff scope
  • Verify transport, media/profile, protocol, and symlink closures
  • Run focused regression tests and check worktree integrity
  • Return the binary checkpoint verdict
2026-08-12T06:19:55.168604Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:19:55.168782Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:19:55.168790Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:20:08.518628Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:20:08.518659Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:20:08.518665Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:20:22.595028Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:20:22.595271Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:20:22.595287Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
codex
The review is split across three independent read-only checks: transport lifecycle, media/fixture fidelity, and protocol-plus-symlink guards. I’m separately auditing the complete nine-file delta and the original checkpoint criteria so the final verdict does not rely on the reported test summary.
exec
/bin/zsh -lc "git status --short
git rev-parse HEAD
git log -3 --oneline --decorate
git diff --check 5231a233..7f7c25d5
git diff --stat 5231a233..7f7c25d5
sed -n '1,260p' .oracle/checkins/batch-2.md
sed -n '1,260p' .oracle/checkins/batch-2-r1.md
sed -n '1,360p' /tmp/batch2-r2.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-2-r2.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
7f7c25d5200f4efcd72f02473507fb1a602565a6
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
7f7c25d5 (HEAD -> oracle-run) batch2-rework2: oracle re-review issues 1-5 (transport SIGKILL escalation + bounded drain, fixture profile accuracy + chan atom + strict support validation, media channel_layout derivation, run.py unresolved out_path, cleanup sidecar symlink guard)
5231a233 batch2-rework: oracle issues 1-6 (missing result -> protocol, transport group-cleanup on any exception + interrupt-safe escalation, fixture SPS crop 1080 + pcm_s16le codec + support request validation, artifact in-workspace symlink rejection, publication unresolved-path symlink guards + invalidate-before-replace ordering)
dedcc2c5 (tag: C2) batch2: command transport, raw-command fixture, asset cache extraction, invocation-scoped asset materialization, profile resolution + artifact validation, locked publication
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r1.md:259: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:260: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:262: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1386: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1388: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1390: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1392: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r1.md:1394: trailing whitespace.
+++     4	
.oracle/checkins/batch-2-r1.md:1396: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r1.md:1398: trailing whitespace.
+++    11	
.oracle/checkins/batch-2-r1.md:1400: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r1.md:1402: trailing whitespace.
+++    30	
.oracle/checkins/batch-2-r1.md:1404: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r1.md:1406: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r1.md:1408: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r1.md:1410: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r1.md:1412: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r1.md:1414: trailing whitespace.
+++    54	
.oracle/checkins/batch-2-r1.md:1416: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r1.md:1418: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r1.md:1420: trailing whitespace.
+++    83	
.oracle/checkins/batch-2-r1.md:1422: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r1.md:1424: trailing whitespace.
+++    93	
.oracle/checkins/batch-2-r1.md:1426: trailing whitespace.
+++    94	
.oracle/checkins/batch-2-r1.md:1428: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r1.md:1430: trailing whitespace.
+++   107	
.oracle/checkins/batch-2-r1.md:1432: trailing whitespace.
+++   199	
.oracle/checkins/batch-2-r1.md:1434: trailing whitespace.
+++   200	
.oracle/checkins/batch-2-r1.md:1436: trailing whitespace.
+++   915	
.oracle/checkins/batch-2-r1.md:1438: trailing whitespace.
+++   916	
.oracle/checkins/batch-2-r1.md:1440: trailing whitespace.
+++    35	
.oracle/checkins/batch-2-r1.md:1442: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r1.md:1444: trailing whitespace.
+++    49	
.oracle/checkins/batch-2-r1.md:1446: trailing whitespace.
+++    61	
.oracle/checkins/batch-2-r1.md:1448: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r1.md:1450: trailing whitespace.
+++   102	
.oracle/checkins/batch-2-r1.md:1452: trailing whitespace.
+++   119	
.oracle/checkins/batch-2-r1.md:1454: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r1.md:1456: trailing whitespace.
+++   139	
.oracle/checkins/batch-2-r1.md:1458: trailing whitespace.
+++   140	
.oracle/checkins/batch-2-r1.md:1460: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r1.md:1462: trailing whitespace.
+++   167	
.oracle/checkins/batch-2-r1.md:1464: trailing whitespace.
+++   168	
.oracle/checkins/batch-2-r1.md:1466: trailing whitespace.
+++   516	
.oracle/checkins/batch-2-r1.md:1468: trailing whitespace.
+++   520	
.oracle/checkins/batch-2-r1.md:1470: trailing whitespace.
+++   539	
.oracle/checkins/batch-2-r1.md:1472: trailing whitespace.
+++   572	
.oracle/checkins/batch-2-r1.md:1474: trailing whitespace.
+++   573	
.oracle/checkins/batch-2-r1.md:1476: trailing whitespace.
+++   580	
.oracle/checkins/batch-2-r1.md:1478: trailing whitespace.
+++   585	
.oracle/checkins/batch-2-r1.md:1480: trailing whitespace.
+++   591	
.oracle/checkins/batch-2-r1.md:1482: trailing whitespace.
+++   592	
.oracle/checkins/batch-2-r1.md:1484: trailing whitespace.
+++   596	
.oracle/checkins/batch-2-r1.md:1486: trailing whitespace.
+++   601	
.oracle/checkins/batch-2-r1.md:1488: trailing whitespace.
+++   613	
.oracle/checkins/batch-2-r1.md:1490: trailing whitespace.
+++   618	
.oracle/checkins/batch-2-r1.md:1492: trailing whitespace.
+++   630	
.oracle/checkins/batch-2-r1.md:1494: trailing whitespace.
+++   642	
.oracle/checkins/batch-2-r1.md:1496: trailing whitespace.
+++   643	
.oracle/checkins/batch-2-r1.md:1498: trailing whitespace.
+++   664	
.oracle/checkins/batch-2-r1.md:1500: trailing whitespace.
+++   665	
.oracle/checkins/batch-2-r1.md:1502: trailing whitespace.
+++   669	
.oracle/checkins/batch-2-r1.md:1504: trailing whitespace.
+++   676	
.oracle/checkins/batch-2-r1.md:1506: trailing whitespace.
+++   699	
.oracle/checkins/batch-2-r1.md:1508: trailing whitespace.
+++   711	
.oracle/checkins/batch-2-r1.md:1510: trailing whitespace.
+++   200	
.oracle/checkins/batch-2-r1.md:1512: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r1.md:1514: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r1.md:1516: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r1.md:1518: trailing whitespace.
+++   289	
.oracle/checkins/batch-2-r1.md:1520: trailing whitespace.
+++   311	
.oracle/checkins/batch-2-r1.md:1522: trailing whitespace.
+++   312	
.oracle/checkins/batch-2-r1.md:1524: trailing whitespace.
+++   328	
.oracle/checkins/batch-2-r1.md:1526: trailing whitespace.
+++   335	
.oracle/checkins/batch-2-r1.md:1528: trailing whitespace.
+++   356	
.oracle/checkins/batch-2-r1.md:1530: trailing whitespace.
+++   383	
.oracle/checkins/batch-2-r1.md:1532: trailing whitespace.
+++   384	
.oracle/checkins/batch-2-r1.md:1534: trailing whitespace.
+++   387	
.oracle/checkins/batch-2-r1.md:1536: trailing whitespace.
+++   389	
.oracle/checkins/batch-2-r1.md:1538: trailing whitespace.
+++   390	
.oracle/checkins/batch-2-r1.md:1540: trailing whitespace.
+++   214	
.oracle/checkins/batch-2-r1.md:1542: trailing whitespace.
+++   215	
.oracle/checkins/batch-2-r1.md:1544: trailing whitespace.
+++   218	
.oracle/checkins/batch-2-r1.md:1546: trailing whitespace.
+++   224	
.oracle/checkins/batch-2-r1.md:1548: trailing whitespace.
+++   225	
.oracle/checkins/batch-2-r1.md:1550: trailing whitespace.
+++   234	
.oracle/checkins/batch-2-r1.md:1552: trailing whitespace.
+++   235	
.oracle/checkins/batch-2-r1.md:1554: trailing whitespace.
+++   240	
.oracle/checkins/batch-2-r1.md:1556: trailing whitespace.
+++   241	
.oracle/checkins/batch-2-r1.md:1558: trailing whitespace.
+++   250	
.oracle/checkins/batch-2-r1.md:1560: trailing whitespace.
+++   251	
.oracle/checkins/batch-2-r1.md:1562: trailing whitespace.
+++   257	
.oracle/checkins/batch-2-r1.md:1564: trailing whitespace.
+++   258	
.oracle/checkins/batch-2-r1.md:1566: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r1.md:1568: trailing whitespace.
+++   272	
.oracle/checkins/batch-2-r1.md:1570: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r1.md:1572: trailing whitespace.
+++   278	
.oracle/checkins/batch-2-r1.md:1574: trailing whitespace.
+++   285	
.oracle/checkins/batch-2-r1.md:1576: trailing whitespace.
+++   286	
.oracle/checkins/batch-2-r1.md:1578: trailing whitespace.
+++   293	
.oracle/checkins/batch-2-r1.md:1580: trailing whitespace.
+++   294	
.oracle/checkins/batch-2-r1.md:1582: trailing whitespace.
+++   303	
.oracle/checkins/batch-2-r1.md:1584: trailing whitespace.
+++   304	
.oracle/checkins/batch-2-r1.md:1586: trailing whitespace.
+++   311	
.oracle/checkins/batch-2-r1.md:1588: trailing whitespace.
+++   312	
.oracle/checkins/batch-2-r1.md:1590: trailing whitespace.
+++   321	
.oracle/checkins/batch-2-r1.md:1592: trailing whitespace.
+++   322	
.oracle/checkins/batch-2-r1.md:1594: trailing whitespace.
+++   339	
.oracle/checkins/batch-2-r1.md:1596: trailing whitespace.
+++   340	
.oracle/checkins/batch-2-r1.md:1598: trailing whitespace.
+++   352	
.oracle/checkins/batch-2-r1.md:1600: trailing whitespace.
+++   353	
.oracle/checkins/batch-2-r1.md:1602: trailing whitespace.
+++   356	
.oracle/checkins/batch-2-r1.md:1604: trailing whitespace.
+++   362	
.oracle/checkins/batch-2-r1.md:1606: trailing whitespace.
+++   363	
.oracle/checkins/batch-2-r1.md:1608: trailing whitespace.
+++   664	
.oracle/checkins/batch-2-r1.md:1610: trailing whitespace.
+++   665	
.oracle/checkins/batch-2-r1.md:1612: trailing whitespace.
+++   669	
.oracle/checkins/batch-2-r1.md:1614: trailing whitespace.
+++   676	
.oracle/checkins/batch-2-r1.md:1616: trailing whitespace.
+++   699	
.oracle/checkins/batch-2-r1.md:1618: trailing whitespace.
+++   711	
.oracle/checkins/batch-2-r1.md:1620: trailing whitespace.
+++   726	
.oracle/checkins/batch-2-r1.md:1622: trailing whitespace.
+++   747	
.oracle/checkins/batch-2-r1.md:1624: trailing whitespace.
+++   748	
.oracle/checkins/batch-2-r1.md:1626: trailing whitespace.
+++   755	
.oracle/checkins/batch-2-r1.md:1628: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r1.md:1630: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r1.md:1632: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r1.md:1634: trailing whitespace.
+++   289	
.oracle/checkins/batch-2-r1.md:1636: trailing whitespace.
+++   311	
.oracle/checkins/batch-2-r1.md:1638: trailing whitespace.
+++   312	
.oracle/checkins/batch-2-r1.md:1640: trailing whitespace.
+++   328	
.oracle/checkins/batch-2-r1.md:1642: trailing whitespace.
+++   335	
.oracle/checkins/batch-2-r1.md:1644: trailing whitespace.
+++   356	
.oracle/checkins/batch-2-r1.md:1646: trailing whitespace.
+++   383	
.oracle/checkins/batch-2-r1.md:1648: trailing whitespace.
+++   384	
.oracle/checkins/batch-2-r1.md:1650: trailing whitespace.
+++   387	
.oracle/checkins/batch-2-r1.md:1652: trailing whitespace.
+++   389	
.oracle/checkins/batch-2-r1.md:1654: trailing whitespace.
+++   390	
.oracle/checkins/batch-2-r1.md:1656: trailing whitespace.
+++   749	
.oracle/checkins/batch-2-r1.md:1658: trailing whitespace.
+++   750	
.oracle/checkins/batch-2-r1.md:1660: trailing whitespace.
+++   786	
.oracle/checkins/batch-2-r1.md:1662: trailing whitespace.
+++   787	
.oracle/checkins/batch-2-r1.md:1664: trailing whitespace.
+++   801	
.oracle/checkins/batch-2-r1.md:1666: trailing whitespace.
+++   802	
.oracle/checkins/batch-2-r1.md:1668: trailing whitespace.
+++   818	
.oracle/checkins/batch-2-r1.md:1670: trailing whitespace.
+++   819	
.oracle/checkins/batch-2-r1.md:1672: trailing whitespace.
+++   915	
.oracle/checkins/batch-2-r1.md:1674: trailing whitespace.
+++   916	
.oracle/checkins/batch-2-r1.md:1676: trailing whitespace.
+++  1072	
.oracle/checkins/batch-2-r1.md:1678: trailing whitespace.
+++  1073	
.oracle/checkins/batch-2-r1.md:1680: trailing whitespace.
+++  1082	
.oracle/checkins/batch-2-r1.md:1682: trailing whitespace.
+++  1083	
.oracle/checkins/batch-2-r1.md:1684: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1686: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1688: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1690: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1692: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1694: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1696: trailing whitespace.
++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1698: trailing whitespace.
++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1700: trailing whitespace.
++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1702: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1704: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1706: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1708: trailing whitespace.
++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1710: trailing whitespace.
++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1712: trailing whitespace.
++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1714: trailing whitespace.
++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1716: trailing whitespace.
++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1718: trailing whitespace.
++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1720: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1722: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1724: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1726: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1728: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1730: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1732: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1734: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1736: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1738: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1740: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1742: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1744: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1746: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1748: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1750: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1752: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1754: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1756: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1758: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1760: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1762: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1764: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1766: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1768: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1770: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1772: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1774: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1776: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1778: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1780: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1782: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1784: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1786: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1788: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1790: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1792: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1794: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1796: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1798: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1800: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1802: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1804: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1806: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1808: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1810: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1812: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1814: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1816: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1818: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1820: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1822: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1824: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1826: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1828: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1830: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1832: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1834: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1836: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1838: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1840: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1842: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1844: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1846: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1848: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1850: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1852: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1854: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1856: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1858: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1860: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1862: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1864: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1866: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1868: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1870: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1872: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1874: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1876: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1878: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1880: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1882: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1884: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1886: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1888: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1890: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1892: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1894: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1896: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1898: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1900: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1902: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1904: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1906: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1908: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1910: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1912: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1914: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1916: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1918: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1920: trailing whitespace.
++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:1922: trailing whitespace.
++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:1924: trailing whitespace.
++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:1926: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:1928: trailing whitespace.
++++++++   730	
.oracle/checkins/batch-2-r1.md:1930: trailing whitespace.
++++++++   731	
.oracle/checkins/batch-2-r1.md:1932: trailing whitespace.
++++++++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-2-r1.md:1934: trailing whitespace.
++++++++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-2-r1.md:1936: trailing whitespace.
++++++++   453	
.oracle/checkins/batch-2-r1.md:1938: trailing whitespace.
++++++++   461	
.oracle/checkins/batch-2-r1.md:1940: trailing whitespace.
++++++++   463	
.oracle/checkins/batch-2-r1.md:1942: trailing whitespace.
++++++++   465	
.oracle/checkins/batch-2-r1.md:1944: trailing whitespace.
++++++++   470	
.oracle/checkins/batch-2-r1.md:1946: trailing whitespace.
++++++++   492	
.oracle/checkins/batch-2-r1.md:1948: trailing whitespace.
++++++++   520	
.oracle/checkins/batch-2-r1.md:1950: trailing whitespace.
++++++++   539	
.oracle/checkins/batch-2-r1.md:1952: trailing whitespace.
++++++++   540	
.oracle/checkins/batch-2-r1.md:1954: trailing whitespace.
++++++++   550	
.oracle/checkins/batch-2-r1.md:1956: trailing whitespace.
++++++++   551	
.oracle/checkins/batch-2-r1.md:1958: trailing whitespace.
++++++++   609	
.oracle/checkins/batch-2-r1.md:1960: trailing whitespace.
++++++++   613	
.oracle/checkins/batch-2-r1.md:1962: trailing whitespace.
++++++++   614	
.oracle/checkins/batch-2-r1.md:1964: trailing whitespace.
++++++++   627	
.oracle/checkins/batch-2-r1.md:1966: trailing whitespace.
++++++++   628	
.oracle/checkins/batch-2-r1.md:1968: trailing whitespace.
++++++++   631	
.oracle/checkins/batch-2-r1.md:1970: trailing whitespace.
++++++++   640	
.oracle/checkins/batch-2-r1.md:1972: trailing whitespace.
++++++++   641	
.oracle/checkins/batch-2-r1.md:1974: trailing whitespace.
++++++++   647	
.oracle/checkins/batch-2-r1.md:1976: trailing whitespace.
++++++++   648	
.oracle/checkins/batch-2-r1.md:1978: trailing whitespace.
++++++++   679	
.oracle/checkins/batch-2-r1.md:1980: trailing whitespace.
++++++++   689	
.oracle/checkins/batch-2-r1.md:1982: trailing whitespace.
++++++++   721	
.oracle/checkins/batch-2-r1.md:1984: trailing whitespace.
++++++++   722	
.oracle/checkins/batch-2-r1.md:1986: trailing whitespace.
++++++++   740	
.oracle/checkins/batch-2-r1.md:1988: trailing whitespace.
++++++++   741	
.oracle/checkins/batch-2-r1.md:1990: trailing whitespace.
++++++++   777	
.oracle/checkins/batch-2-r1.md:1992: trailing whitespace.
++++++++   778	
.oracle/checkins/batch-2-r1.md:1994: trailing whitespace.
++++++++   792	
.oracle/checkins/batch-2-r1.md:1996: trailing whitespace.
++++++++   793	
.oracle/checkins/batch-2-r1.md:1998: trailing whitespace.
++++++++   809	
.oracle/checkins/batch-2-r1.md:2000: trailing whitespace.
++++++++   810	
.oracle/checkins/batch-2-r1.md:2002: trailing whitespace.
++++++++   904	
.oracle/checkins/batch-2-r1.md:2004: trailing whitespace.
++++++++   905	
.oracle/checkins/batch-2-r1.md:2006: trailing whitespace.
++++++++   965	
.oracle/checkins/batch-2-r1.md:2008: trailing whitespace.
++++++++   966	
.oracle/checkins/batch-2-r1.md:2010: trailing whitespace.
++++++++   975	
.oracle/checkins/batch-2-r1.md:2012: trailing whitespace.
++++++++   976	
.oracle/checkins/batch-2-r1.md:2014: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r1.md:2016: trailing whitespace.
++++++++     4	
.oracle/checkins/batch-2-r1.md:2018: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r1.md:2020: trailing whitespace.
++++++++    11	
.oracle/checkins/batch-2-r1.md:2022: trailing whitespace.
++++++++    28	
.oracle/checkins/batch-2-r1.md:2024: trailing whitespace.
++++++++    29	
.oracle/checkins/batch-2-r1.md:2026: trailing whitespace.
++++++++    32	
.oracle/checkins/batch-2-r1.md:2028: trailing whitespace.
++++++++    33	
.oracle/checkins/batch-2-r1.md:2030: trailing whitespace.
++++++++    38	
.oracle/checkins/batch-2-r1.md:2032: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r1.md:2034: trailing whitespace.
++++++++    41	
.oracle/checkins/batch-2-r1.md:2036: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r1.md:2038: trailing whitespace.
++++++++    54	
.oracle/checkins/batch-2-r1.md:2040: trailing whitespace.
++++++++    81	
.oracle/checkins/batch-2-r1.md:2042: trailing whitespace.
++++++++    82	
.oracle/checkins/batch-2-r1.md:2044: trailing whitespace.
++++++++    85	
.oracle/checkins/batch-2-r1.md:2046: trailing whitespace.
++++++++    92	
.oracle/checkins/batch-2-r1.md:2048: trailing whitespace.
++++++++    93	
.oracle/checkins/batch-2-r1.md:2050: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r1.md:2052: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r1.md:2054: trailing whitespace.
++++++++   168	
.oracle/checkins/batch-2-r1.md:2056: trailing whitespace.
++++++++   169	
.oracle/checkins/batch-2-r1.md:2058: trailing whitespace.
++++++++   236	
.oracle/checkins/batch-2-r1.md:2060: trailing whitespace.
++++++++   237	
.oracle/checkins/batch-2-r1.md:2062: trailing whitespace.
++++++++   248	
.oracle/checkins/batch-2-r1.md:2064: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r1.md:2066: trailing whitespace.
++++++++   271	
.oracle/checkins/batch-2-r1.md:2068: trailing whitespace.
++++++++   272	
.oracle/checkins/batch-2-r1.md:2070: trailing whitespace.
++++++++   288	
.oracle/checkins/batch-2-r1.md:2072: trailing whitespace.
++++++++   295	
.oracle/checkins/batch-2-r1.md:2074: trailing whitespace.
++++++++   316	
.oracle/checkins/batch-2-r1.md:2076: trailing whitespace.
++++++++   343	
.oracle/checkins/batch-2-r1.md:2078: trailing whitespace.
++++++++   344	
.oracle/checkins/batch-2-r1.md:2080: trailing whitespace.
++++++++   347	
.oracle/checkins/batch-2-r1.md:2082: trailing whitespace.
++++++++   349	
.oracle/checkins/batch-2-r1.md:2084: trailing whitespace.
++++++++   350	
.oracle/checkins/batch-2-r1.md:2086: trailing whitespace.
++++++++   353	
.oracle/checkins/batch-2-r1.md:2088: trailing whitespace.
++++++++   357	
.oracle/checkins/batch-2-r1.md:2090: trailing whitespace.
++++++++   358	
.oracle/checkins/batch-2-r1.md:2092: trailing whitespace.
++++++++   361	
.oracle/checkins/batch-2-r1.md:2094: trailing whitespace.
++++++++   366	
.oracle/checkins/batch-2-r1.md:2096: trailing whitespace.
++++++++   367	
.oracle/checkins/batch-2-r1.md:2098: trailing whitespace.
++++++++   370	
.oracle/checkins/batch-2-r1.md:2100: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r1.md:2102: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r1.md:2104: trailing whitespace.
++++++++    10	
.oracle/checkins/batch-2-r1.md:2106: trailing whitespace.
++++++++    18	
.oracle/checkins/batch-2-r1.md:2108: trailing whitespace.
++++++++    21	
.oracle/checkins/batch-2-r1.md:2110: trailing whitespace.
++++++++    22	
.oracle/checkins/batch-2-r1.md:2112: trailing whitespace.
++++++++    24	
.oracle/checkins/batch-2-r1.md:2114: trailing whitespace.
++++++++    35	
.oracle/checkins/batch-2-r1.md:2116: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r1.md:2118: trailing whitespace.
++++++++    52	
.oracle/checkins/batch-2-r1.md:2120: trailing whitespace.
++++++++    73	
.oracle/checkins/batch-2-r1.md:2122: trailing whitespace.
++++++++    93	
.oracle/checkins/batch-2-r1.md:2124: trailing whitespace.
++++++++   110	
.oracle/checkins/batch-2-r1.md:2126: trailing whitespace.
++++++++   123	
.oracle/checkins/batch-2-r1.md:2128: trailing whitespace.
++++++++   130	
.oracle/checkins/batch-2-r1.md:2130: trailing whitespace.
++++++++   131	
.oracle/checkins/batch-2-r1.md:2132: trailing whitespace.
++++++++   134	
.oracle/checkins/batch-2-r1.md:2134: trailing whitespace.
++++++++   158	
.oracle/checkins/batch-2-r1.md:2136: trailing whitespace.
++++++++   159	
.oracle/checkins/batch-2-r1.md:2138: trailing whitespace.
++++++++   165	
.oracle/checkins/batch-2-r1.md:2140: trailing whitespace.
++++++++   166	
.oracle/checkins/batch-2-r1.md:2142: trailing whitespace.
++++++++   171	
.oracle/checkins/batch-2-r1.md:2144: trailing whitespace.
++++++++   172	
.oracle/checkins/batch-2-r1.md:2146: trailing whitespace.
++++++++   186	
.oracle/checkins/batch-2-r1.md:2148: trailing whitespace.
++++++++   187	
.oracle/checkins/batch-2-r1.md:2150: trailing whitespace.
++++++++   194	
.oracle/checkins/batch-2-r1.md:2152: trailing whitespace.
++++++++   195	
.oracle/checkins/batch-2-r1.md:2154: trailing whitespace.
++++++++   205	
.oracle/checkins/batch-2-r1.md:2156: trailing whitespace.
++++++++   206	
.oracle/checkins/batch-2-r1.md:2158: trailing whitespace.
++++++++   209	
.oracle/checkins/batch-2-r1.md:2160: trailing whitespace.
++++++++   215	
.oracle/checkins/batch-2-r1.md:2162: trailing whitespace.
++++++++   216	
.oracle/checkins/batch-2-r1.md:2164: trailing whitespace.
++++++++   225	
.oracle/checkins/batch-2-r1.md:2166: trailing whitespace.
++++++++   226	
.oracle/checkins/batch-2-r1.md:2168: trailing whitespace.
++++++++   231	
.oracle/checkins/batch-2-r1.md:2170: trailing whitespace.
++++++++   232	
.oracle/checkins/batch-2-r1.md:2172: trailing whitespace.
++++++++   241	
.oracle/checkins/batch-2-r1.md:2174: trailing whitespace.
++++++++   242	
.oracle/checkins/batch-2-r1.md:2176: trailing whitespace.
++++++++   248	
.oracle/checkins/batch-2-r1.md:2178: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r1.md:2180: trailing whitespace.
++++++++   507	
.oracle/checkins/batch-2-r1.md:2182: trailing whitespace.
++++++++   511	
.oracle/checkins/batch-2-r1.md:2184: trailing whitespace.
++++++++   530	
.oracle/checkins/batch-2-r1.md:2186: trailing whitespace.
++++++++   563	
.oracle/checkins/batch-2-r1.md:2188: trailing whitespace.
++++++++   564	
.oracle/checkins/batch-2-r1.md:2190: trailing whitespace.
++++++++   571	
.oracle/checkins/batch-2-r1.md:2192: trailing whitespace.
++++++++   576	
.oracle/checkins/batch-2-r1.md:2194: trailing whitespace.
++++++++   582	
.oracle/checkins/batch-2-r1.md:2196: trailing whitespace.
++++++++   583	
.oracle/checkins/batch-2-r1.md:2198: trailing whitespace.
++++++++   587	
.oracle/checkins/batch-2-r1.md:2200: trailing whitespace.
++++++++   592	
.oracle/checkins/batch-2-r1.md:2202: trailing whitespace.
++++++++   604	
.oracle/checkins/batch-2-r1.md:2204: trailing whitespace.
++++++++   609	
.oracle/checkins/batch-2-r1.md:2206: trailing whitespace.
++++++++   621	
.oracle/checkins/batch-2-r1.md:2208: trailing whitespace.
++++++++   633	
.oracle/checkins/batch-2-r1.md:2210: trailing whitespace.
++++++++   634	
.oracle/checkins/batch-2-r1.md:2212: trailing whitespace.
++++++++   655	
.oracle/checkins/batch-2-r1.md:2214: trailing whitespace.
++++++++   656	
.oracle/checkins/batch-2-r1.md:2216: trailing whitespace.
++++++++   660	
.oracle/checkins/batch-2-r1.md:2218: trailing whitespace.
++++++++   667	
.oracle/checkins/batch-2-r1.md:2220: trailing whitespace.
++++++++   690	
.oracle/checkins/batch-2-r1.md:2222: trailing whitespace.
++++++++   702	
.oracle/checkins/batch-2-r1.md:2224: trailing whitespace.
++++++++   717	
.oracle/checkins/batch-2-r1.md:2226: trailing whitespace.
++++++++  1662	
.oracle/checkins/batch-2-r1.md:2228: trailing whitespace.
++++++++  1686	
.oracle/checkins/batch-2-r1.md:2230: trailing whitespace.
++++++++  1693	
.oracle/checkins/batch-2-r1.md:2232: trailing whitespace.
++++++++  1694	
.oracle/checkins/batch-2-r1.md:2234: trailing whitespace.
++++++++  1698	
.oracle/checkins/batch-2-r1.md:2236: trailing whitespace.
++++++++  1705	
.oracle/checkins/batch-2-r1.md:2238: trailing whitespace.
++++++++  1753	
.oracle/checkins/batch-2-r1.md:2240: trailing whitespace.
++++++++  1757	
.oracle/checkins/batch-2-r1.md:2242: trailing whitespace.
++++++++  1763	
.oracle/checkins/batch-2-r1.md:2244: trailing whitespace.
++++++++  1769	
.oracle/checkins/batch-2-r1.md:2246: trailing whitespace.
++++++++  1773	
.oracle/checkins/batch-2-r1.md:2248: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r1.md:2250: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r1.md:2252: trailing whitespace.
++++++++    11	
.oracle/checkins/batch-2-r1.md:2254: trailing whitespace.
++++++++    20	
.oracle/checkins/batch-2-r1.md:2256: trailing whitespace.
++++++++    21	
.oracle/checkins/batch-2-r1.md:2258: trailing whitespace.
++++++++    48	
.oracle/checkins/batch-2-r1.md:2260: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r1.md:2262: trailing whitespace.
++++++++    52	
.oracle/checkins/batch-2-r1.md:2264: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r1.md:2266: trailing whitespace.
++++++++    56	
.oracle/checkins/batch-2-r1.md:2268: trailing whitespace.
++++++++    57	
.oracle/checkins/batch-2-r1.md:2270: trailing whitespace.
++++++++    60	
.oracle/checkins/batch-2-r1.md:2272: trailing whitespace.
++++++++    61	
.oracle/checkins/batch-2-r1.md:2274: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r1.md:2276: trailing whitespace.
++++++++    73	
.oracle/checkins/batch-2-r1.md:2278: trailing whitespace.
++++++++    81	
.oracle/checkins/batch-2-r1.md:2280: trailing whitespace.
++++++++    88	
.oracle/checkins/batch-2-r1.md:2282: trailing whitespace.
++++++++    89	
.oracle/checkins/batch-2-r1.md:2284: trailing whitespace.
++++++++    96	
.oracle/checkins/batch-2-r1.md:2286: trailing whitespace.
++++++++    97	
.oracle/checkins/batch-2-r1.md:2288: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r1.md:2290: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r1.md:2292: trailing whitespace.
++++++++   113	
.oracle/checkins/batch-2-r1.md:2294: trailing whitespace.
++++++++   114	
.oracle/checkins/batch-2-r1.md:2296: trailing whitespace.
++++++++   312	
.oracle/checkins/batch-2-r1.md:2298: trailing whitespace.
++++++++   313	
.oracle/checkins/batch-2-r1.md:2300: trailing whitespace.
++++++++   324	
.oracle/checkins/batch-2-r1.md:2302: trailing whitespace.
++++++++   325	
.oracle/checkins/batch-2-r1.md:2304: trailing whitespace.
++++++++   338	
.oracle/checkins/batch-2-r1.md:2306: trailing whitespace.
++++++++   339	
.oracle/checkins/batch-2-r1.md:2308: trailing whitespace.
++++++++   356	
.oracle/checkins/batch-2-r1.md:2310: trailing whitespace.
++++++++   357	
.oracle/checkins/batch-2-r1.md:2312: trailing whitespace.
++++++++   375	
.oracle/checkins/batch-2-r1.md:2314: trailing whitespace.
++++++++   376	
.oracle/checkins/batch-2-r1.md:2316: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2318: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2320: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2322: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2324: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2326: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2328: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2330: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2332: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r1.md:2334: trailing whitespace.
++++++++   809	
.oracle/checkins/batch-2-r1.md:2336: trailing whitespace.
++++++++   810	
.oracle/checkins/batch-2-r1.md:2338: trailing whitespace.
++++++++   904	
.oracle/checkins/batch-2-r1.md:2340: trailing whitespace.
++++++++   905	
.oracle/checkins/batch-2-r1.md:2342: trailing whitespace.
++++++++   965	
.oracle/checkins/batch-2-r1.md:2344: trailing whitespace.
++++++++   966	
.oracle/checkins/batch-2-r1.md:2346: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r1.md:2348: trailing whitespace.
++++++++     4	
.oracle/checkins/batch-2-r1.md:2350: trailing whitespace.
++++++++     6	
.oracle/checkins/batch-2-r1.md:2352: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r1.md:2354: trailing whitespace.
++++++++    17	
.oracle/checkins/batch-2-r1.md:2356: trailing whitespace.
++++++++    19	
.oracle/checkins/batch-2-r1.md:2358: trailing whitespace.
++++++++    25	
.oracle/checkins/batch-2-r1.md:2360: trailing whitespace.
++++++++    27	
.oracle/checkins/batch-2-r1.md:2362: trailing whitespace.
++++++++    29	
.oracle/checkins/batch-2-r1.md:2364: trailing whitespace.
++++++++    31	
.oracle/checkins/batch-2-r1.md:2366: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r1.md:2368: trailing whitespace.
++++++++    42	
.oracle/checkins/batch-2-r1.md:2370: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r1.md:2372: trailing whitespace.
++++++++    51	
.oracle/checkins/batch-2-r1.md:2374: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r1.md:2376: trailing whitespace.
++++++++    55	
.oracle/checkins/batch-2-r1.md:2378: trailing whitespace.
++++++++    63	
.oracle/checkins/batch-2-r1.md:2380: trailing whitespace.
++++++++    65	
.oracle/checkins/batch-2-r1.md:2382: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r1.md:2384: trailing whitespace.
++++++++    74	
.oracle/checkins/batch-2-r1.md:2386: trailing whitespace.
++++++++    76	
.oracle/checkins/batch-2-r1.md:2388: trailing whitespace.
++++++++    78	
.oracle/checkins/batch-2-r1.md:2390: trailing whitespace.
++++++++   131	
.oracle/checkins/batch-2-r1.md:2392: trailing whitespace.
++++++++   132	
.oracle/checkins/batch-2-r1.md:2394: trailing whitespace.
++++++++   162	
.oracle/checkins/batch-2-r1.md:2396: trailing whitespace.
++++++++   163	
.oracle/checkins/batch-2-r1.md:2398: trailing whitespace.
++++++++   178	
.oracle/checkins/batch-2-r1.md:2400: trailing whitespace.
++++++++   179	
.oracle/checkins/batch-2-r1.md:2402: trailing whitespace.
++++++++   206	
.oracle/checkins/batch-2-r1.md:2404: trailing whitespace.
++++++++   207	
.oracle/checkins/batch-2-r1.md:2406: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r1.md:2408: trailing whitespace.
++++++++   250	
.oracle/checkins/batch-2-r1.md:2410: trailing whitespace.
++++++++   288	
.oracle/checkins/batch-2-r1.md:2412: trailing whitespace.
++++++++   289	
.oracle/checkins/batch-2-r1.md:2414: trailing whitespace.
++++++++   302	
.oracle/checkins/batch-2-r1.md:2416: trailing whitespace.
++++++++   303	
.oracle/checkins/batch-2-r1.md:2418: trailing whitespace.
++++++++   312	
.oracle/checkins/batch-2-r1.md:2420: trailing whitespace.
++++++++   313	
.oracle/checkins/batch-2-r1.md:2422: trailing whitespace.
++++++++   330	
.oracle/checkins/batch-2-r1.md:2424: trailing whitespace.
++++++++   331	
.oracle/checkins/batch-2-r1.md:2426: trailing whitespace.
++++++++   343	
.oracle/checkins/batch-2-r1.md:2428: trailing whitespace.
++++++++   344	
.oracle/checkins/batch-2-r1.md:2430: trailing whitespace.
++++++++   288	
.oracle/checkins/batch-2-r1.md:2432: trailing whitespace.
++++++++    98	
.oracle/checkins/batch-2-r1.md:2434: trailing whitespace.
++++++++   101	
.oracle/checkins/batch-2-r1.md:2436: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r1.md:2438: trailing whitespace.
++++++++   107	
.oracle/checkins/batch-2-r1.md:2440: trailing whitespace.
++++++++   110	
.oracle/checkins/batch-2-r1.md:2442: trailing whitespace.
++++++++   113	
.oracle/checkins/batch-2-r1.md:2444: trailing whitespace.
++++++++  1349	
.oracle/checkins/batch-2-r1.md:2446: trailing whitespace.
++++++++  1350	
.oracle/checkins/batch-2-r1.md:2448: trailing whitespace.
++++++++  1354	
.oracle/checkins/batch-2-r1.md:2450: trailing whitespace.
++++++++  1365	
.oracle/checkins/batch-2-r1.md:2452: trailing whitespace.
++++++++  1444	
.oracle/checkins/batch-2-r1.md:2454: trailing whitespace.
++++++++  1460	
.oracle/checkins/batch-2-r1.md:2456: trailing whitespace.
+++++++  1444	
.oracle/checkins/batch-2-r1.md:2458: trailing whitespace.
+++++++  1460	
.oracle/checkins/batch-2-r1.md:2460: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2462: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2464: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2466: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2468: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2470: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2472: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2474: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2476: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2478: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2480: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2482: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2484: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2486: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2488: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2490: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2492: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2494: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2496: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2498: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2500: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2502: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2504: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2506: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2508: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2510: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2512: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2514: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2516: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2518: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2520: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2522: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2524: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2526: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2528: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2530: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2532: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2534: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2536: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2538: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2540: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2542: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2544: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2546: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2548: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2550: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2552: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2554: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2556: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2558: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2560: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2562: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2564: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2566: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2568: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2570: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2572: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2574: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2576: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2578: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2580: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2582: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2584: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2586: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2588: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2590: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2592: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2594: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2596: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2598: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2600: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2602: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2604: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2606: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2608: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2610: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2612: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2614: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2616: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2618: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2620: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2622: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2624: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2626: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2628: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2630: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2632: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2634: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2636: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2638: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2640: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2642: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2644: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2646: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2648: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2650: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2652: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2654: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2656: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2658: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2660: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2662: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2664: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2666: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2668: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2670: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2672: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2674: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2676: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2678: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2680: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2682: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2684: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2686: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2688: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2690: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:2692: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2-r1.md:2694: trailing whitespace.
+++++++     4	
.oracle/checkins/batch-2-r1.md:2696: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2-r1.md:2698: trailing whitespace.
+++++++    11	
.oracle/checkins/batch-2-r1.md:2700: trailing whitespace.
+++++++    28	
.oracle/checkins/batch-2-r1.md:2702: trailing whitespace.
+++++++    29	
.oracle/checkins/batch-2-r1.md:2704: trailing whitespace.
+++++++    32	
.oracle/checkins/batch-2-r1.md:2706: trailing whitespace.
+++++++    33	
.oracle/checkins/batch-2-r1.md:2708: trailing whitespace.
+++++++    38	
.oracle/checkins/batch-2-r1.md:2710: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2-r1.md:2712: trailing whitespace.
+++++++    41	
.oracle/checkins/batch-2-r1.md:2714: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2-r1.md:2716: trailing whitespace.
+++++++    54	
.oracle/checkins/batch-2-r1.md:2718: trailing whitespace.
+++++++    81	
.oracle/checkins/batch-2-r1.md:2720: trailing whitespace.
+++++++    82	
.oracle/checkins/batch-2-r1.md:2722: trailing whitespace.
+++++++    85	
.oracle/checkins/batch-2-r1.md:2724: trailing whitespace.
+++++++    92	
.oracle/checkins/batch-2-r1.md:2726: trailing whitespace.
+++++++    93	
.oracle/checkins/batch-2-r1.md:2728: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2-r1.md:2730: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2-r1.md:2732: trailing whitespace.
+++++++   173	
.oracle/checkins/batch-2-r1.md:2734: trailing whitespace.
+++++++   174	
.oracle/checkins/batch-2-r1.md:2736: trailing whitespace.
+++++++   248	
.oracle/checkins/batch-2-r1.md:2738: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2-r1.md:2740: trailing whitespace.
+++++++   260	
.oracle/checkins/batch-2-r1.md:2742: trailing whitespace.
+++++++   261	
.oracle/checkins/batch-2-r1.md:2744: trailing whitespace.
+++++++   283	
.oracle/checkins/batch-2-r1.md:2746: trailing whitespace.
+++++++   284	
.oracle/checkins/batch-2-r1.md:2748: trailing whitespace.
+++++++   300	
.oracle/checkins/batch-2-r1.md:2750: trailing whitespace.
+++++++   307	
.oracle/checkins/batch-2-r1.md:2752: trailing whitespace.
+++++++   328	
.oracle/checkins/batch-2-r1.md:2754: trailing whitespace.
+++++++   355	
.oracle/checkins/batch-2-r1.md:2756: trailing whitespace.
+++++++   356	
.oracle/checkins/batch-2-r1.md:2758: trailing whitespace.
+++++++   359	
.oracle/checkins/batch-2-r1.md:2760: trailing whitespace.
+++++++   361	
.oracle/checkins/batch-2-r1.md:2762: trailing whitespace.
+++++++   362	
.oracle/checkins/batch-2-r1.md:2764: trailing whitespace.
+++++++   365	
.oracle/checkins/batch-2-r1.md:2766: trailing whitespace.
+++++++   369	
.oracle/checkins/batch-2-r1.md:2768: trailing whitespace.
+++++++   370	
.oracle/checkins/batch-2-r1.md:2770: trailing whitespace.
+++++++   373	
.oracle/checkins/batch-2-r1.md:2772: trailing whitespace.
+++++++   378	
.oracle/checkins/batch-2-r1.md:2774: trailing whitespace.
+++++++   379	
.oracle/checkins/batch-2-r1.md:2776: trailing whitespace.
+++++++   382	
.oracle/checkins/batch-2-r1.md:2778: trailing whitespace.
+++++++   384	
.oracle/checkins/batch-2-r1.md:2780: trailing whitespace.
+++++++   385	
.oracle/checkins/batch-2-r1.md:2782: trailing whitespace.
+++++++   651	
.oracle/checkins/batch-2-r1.md:2784: trailing whitespace.
+++++++   652	
.oracle/checkins/batch-2-r1.md:2786: trailing whitespace.
+++++++   683	
.oracle/checkins/batch-2-r1.md:2788: trailing whitespace.
+++++++   693	
.oracle/checkins/batch-2-r1.md:2790: trailing whitespace.
+++++++   729	
.oracle/checkins/batch-2-r1.md:2792: trailing whitespace.
+++++++   730	
.oracle/checkins/batch-2-r1.md:2794: trailing whitespace.
+++++++   748	
.oracle/checkins/batch-2-r1.md:2796: trailing whitespace.
+++++++   749	
.oracle/checkins/batch-2-r1.md:2798: trailing whitespace.
+++++++   785	
.oracle/checkins/batch-2-r1.md:2800: trailing whitespace.
+++++++   786	
.oracle/checkins/batch-2-r1.md:2802: trailing whitespace.
+++++++   800	
.oracle/checkins/batch-2-r1.md:2804: trailing whitespace.
+++++++   801	
.oracle/checkins/batch-2-r1.md:2806: trailing whitespace.
+++++++   817	
.oracle/checkins/batch-2-r1.md:2808: trailing whitespace.
+++++++   818	
.oracle/checkins/batch-2-r1.md:2810: trailing whitespace.
+++++++   914	
.oracle/checkins/batch-2-r1.md:2812: trailing whitespace.
+++++++   915	
.oracle/checkins/batch-2-r1.md:2814: trailing whitespace.
+++++++  1001	
.oracle/checkins/batch-2-r1.md:2816: trailing whitespace.
+++++++  1002	
.oracle/checkins/batch-2-r1.md:2818: trailing whitespace.
+++++++  1011	
.oracle/checkins/batch-2-r1.md:2820: trailing whitespace.
+++++++  1012	
.oracle/checkins/batch-2-r1.md:2822: trailing whitespace.
+++++++   285	
.oracle/checkins/batch-2-r1.md:2824: trailing whitespace.
+++++++   294	
.oracle/checkins/batch-2-r1.md:2826: trailing whitespace.
+++++++   295	
.oracle/checkins/batch-2-r1.md:2828: trailing whitespace.
+++++++   302	
.oracle/checkins/batch-2-r1.md:2830: trailing whitespace.
+++++++   303	
.oracle/checkins/batch-2-r1.md:2832: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2-r1.md:2834: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2-r1.md:2836: trailing whitespace.
+++++++   330	
.oracle/checkins/batch-2-r1.md:2838: trailing whitespace.
+++++++   331	
.oracle/checkins/batch-2-r1.md:2840: trailing whitespace.
+++++++   826	
.oracle/checkins/batch-2-r1.md:2842: trailing whitespace.
+++++++   868	
.oracle/checkins/batch-2-r1.md:2844: trailing whitespace.
+++++++   875	
.oracle/checkins/batch-2-r1.md:2846: trailing whitespace.
+++++++   878	
.oracle/checkins/batch-2-r1.md:2848: trailing whitespace.
+++++++   892	
.oracle/checkins/batch-2-r1.md:2850: trailing whitespace.
+++++++   893	
.oracle/checkins/batch-2-r1.md:2852: trailing whitespace.
+++++++   897	
.oracle/checkins/batch-2-r1.md:2854: trailing whitespace.
+++++++   905	
.oracle/checkins/batch-2-r1.md:2856: trailing whitespace.
+++++++   936	
.oracle/checkins/batch-2-r1.md:2858: trailing whitespace.
+++++++   949	
.oracle/checkins/batch-2-r1.md:2860: trailing whitespace.
+++++++   980	
.oracle/checkins/batch-2-r1.md:2862: trailing whitespace.
+++++++   987	
.oracle/checkins/batch-2-r1.md:2864: trailing whitespace.
+++++++   988	
.oracle/checkins/batch-2-r1.md:2866: trailing whitespace.
+++++++   992	
.oracle/checkins/batch-2-r1.md:2868: trailing whitespace.
+++++++  1000	
.oracle/checkins/batch-2-r1.md:2870: trailing whitespace.
+++++++   440	
.oracle/checkins/batch-2-r1.md:2872: trailing whitespace.
+++++++   441	
.oracle/checkins/batch-2-r1.md:2874: trailing whitespace.
+++++++   445	
.oracle/checkins/batch-2-r1.md:2876: trailing whitespace.
+++++++   459	
.oracle/checkins/batch-2-r1.md:2878: trailing whitespace.
+++++++   507	
.oracle/checkins/batch-2-r1.md:2880: trailing whitespace.
+++++++   511	
.oracle/checkins/batch-2-r1.md:2882: trailing whitespace.
+++++++   530	
.oracle/checkins/batch-2-r1.md:2884: trailing whitespace.
+++++++   563	
.oracle/checkins/batch-2-r1.md:2886: trailing whitespace.
+++++++   564	
.oracle/checkins/batch-2-r1.md:2888: trailing whitespace.
+++++++   571	
.oracle/checkins/batch-2-r1.md:2890: trailing whitespace.
+++++++   576	
.oracle/checkins/batch-2-r1.md:2892: trailing whitespace.
+++++++   582	
.oracle/checkins/batch-2-r1.md:2894: trailing whitespace.
+++++++   583	
.oracle/checkins/batch-2-r1.md:2896: trailing whitespace.
+++++++   587	
.oracle/checkins/batch-2-r1.md:2898: trailing whitespace.
+++++++   592	
.oracle/checkins/batch-2-r1.md:2900: trailing whitespace.
+++++++   604	
.oracle/checkins/batch-2-r1.md:2902: trailing whitespace.
+++++++   609	
.oracle/checkins/batch-2-r1.md:2904: trailing whitespace.
+++++++   621	
.oracle/checkins/batch-2-r1.md:2906: trailing whitespace.
+++++++   633	
.oracle/checkins/batch-2-r1.md:2908: trailing whitespace.
+++++++   634	
.oracle/checkins/batch-2-r1.md:2910: trailing whitespace.
+++++++   655	
.oracle/checkins/batch-2-r1.md:2912: trailing whitespace.
+++++++   656	
.oracle/checkins/batch-2-r1.md:2914: trailing whitespace.
+++++++   660	
.oracle/checkins/batch-2-r1.md:2916: trailing whitespace.
+++++++   667	
.oracle/checkins/batch-2-r1.md:2918: trailing whitespace.
+++++++   690	
.oracle/checkins/batch-2-r1.md:2920: trailing whitespace.
+++++++   702	
.oracle/checkins/batch-2-r1.md:2922: trailing whitespace.
+++++++   717	
.oracle/checkins/batch-2-r1.md:2924: trailing whitespace.
+++++++   225	
.oracle/checkins/batch-2-r1.md:2926: trailing whitespace.
+++++++   230	
.oracle/checkins/batch-2-r1.md:2928: trailing whitespace.
+++++++   238	
.oracle/checkins/batch-2-r1.md:2930: trailing whitespace.
+++++++   240	
.oracle/checkins/batch-2-r1.md:2932: trailing whitespace.
+++++++   243	
.oracle/checkins/batch-2-r1.md:2934: trailing whitespace.
+++++++   251	
.oracle/checkins/batch-2-r1.md:2936: trailing whitespace.
+++++++   255	
.oracle/checkins/batch-2-r1.md:2938: trailing whitespace.
+++++++   257	
.oracle/checkins/batch-2-r1.md:2940: trailing whitespace.
+++++++   262	
.oracle/checkins/batch-2-r1.md:2942: trailing whitespace.
+++++++   274	
.oracle/checkins/batch-2-r1.md:2944: trailing whitespace.
+++++++   276	
.oracle/checkins/batch-2-r1.md:2946: trailing whitespace.
+++++++   280	
.oracle/checkins/batch-2-r1.md:2948: trailing whitespace.
+++++++   290	
.oracle/checkins/batch-2-r1.md:2950: trailing whitespace.
+++++++   292	
.oracle/checkins/batch-2-r1.md:2952: trailing whitespace.
+++++++   461	
.oracle/checkins/batch-2-r1.md:2954: trailing whitespace.
+++++++   463	
.oracle/checkins/batch-2-r1.md:2956: trailing whitespace.
+++++++   465	
.oracle/checkins/batch-2-r1.md:2958: trailing whitespace.
+++++++   470	
.oracle/checkins/batch-2-r1.md:2960: trailing whitespace.
+++++++   492	
.oracle/checkins/batch-2-r1.md:2962: trailing whitespace.
+++++++   502	
.oracle/checkins/batch-2-r1.md:2964: trailing whitespace.
+++++++   504	
.oracle/checkins/batch-2-r1.md:2966: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2-r1.md:2968: trailing whitespace.
+++++++     4	
.oracle/checkins/batch-2-r1.md:2970: trailing whitespace.
+++++++     6	
.oracle/checkins/batch-2-r1.md:2972: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2-r1.md:2974: trailing whitespace.
+++++++    17	
.oracle/checkins/batch-2-r1.md:2976: trailing whitespace.
+++++++    19	
.oracle/checkins/batch-2-r1.md:2978: trailing whitespace.
+++++++    25	
.oracle/checkins/batch-2-r1.md:2980: trailing whitespace.
+++++++    27	
.oracle/checkins/batch-2-r1.md:2982: trailing whitespace.
+++++++    29	
.oracle/checkins/batch-2-r1.md:2984: trailing whitespace.
+++++++    31	
.oracle/checkins/batch-2-r1.md:2986: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2-r1.md:2988: trailing whitespace.
+++++++    42	
.oracle/checkins/batch-2-r1.md:2990: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2-r1.md:2992: trailing whitespace.
+++++++    51	
.oracle/checkins/batch-2-r1.md:2994: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2-r1.md:2996: trailing whitespace.
+++++++    55	
.oracle/checkins/batch-2-r1.md:2998: trailing whitespace.
+++++++    63	
.oracle/checkins/batch-2-r1.md:3000: trailing whitespace.
+++++++    65	
.oracle/checkins/batch-2-r1.md:3002: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2-r1.md:3004: trailing whitespace.
+++++++    74	
.oracle/checkins/batch-2-r1.md:3006: trailing whitespace.
+++++++    76	
.oracle/checkins/batch-2-r1.md:3008: trailing whitespace.
+++++++    78	
.oracle/checkins/batch-2-r1.md:3010: trailing whitespace.
+++++++    86	
.oracle/checkins/batch-2-r1.md:3012: trailing whitespace.
+++++++    88	
.oracle/checkins/batch-2-r1.md:3014: trailing whitespace.
+++++++    94	
.oracle/checkins/batch-2-r1.md:3016: trailing whitespace.
+++++++    96	
.oracle/checkins/batch-2-r1.md:3018: trailing whitespace.
+++++++    98	
.oracle/checkins/batch-2-r1.md:3020: trailing whitespace.
+++++++   100	
.oracle/checkins/batch-2-r1.md:3022: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:3024: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:3026: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:3028: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:3030: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:3032: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r1.md:3034: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2-r1.md:3036: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2-r1.md:3038: trailing whitespace.
+++++++   168	
.oracle/checkins/batch-2-r1.md:3040: trailing whitespace.
+++++++   169	
.oracle/checkins/batch-2-r1.md:3042: trailing whitespace.
+++++++   236	
.oracle/checkins/batch-2-r1.md:3044: trailing whitespace.
+++++++   237	
.oracle/checkins/batch-2-r1.md:3046: trailing whitespace.
+++++++   248	
.oracle/checkins/batch-2-r1.md:3048: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2-r1.md:3050: trailing whitespace.
+++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-2-r1.md:3052: trailing whitespace.
+++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-2-r1.md:3054: trailing whitespace.
+++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-2-r1.md:3056: trailing whitespace.
+++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-2-r1.md:3058: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2-r1.md:3060: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2-r1.md:3062: trailing whitespace.
+++++++    11	
.oracle/checkins/batch-2-r1.md:3064: trailing whitespace.
+++++++    20	
.oracle/checkins/batch-2-r1.md:3066: trailing whitespace.
+++++++    21	
.oracle/checkins/batch-2-r1.md:3068: trailing whitespace.
+++++++    48	
.oracle/checkins/batch-2-r1.md:3070: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2-r1.md:3072: trailing whitespace.
+++++++    52	
.oracle/checkins/batch-2-r1.md:3074: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2-r1.md:3076: trailing whitespace.
+++++++    56	
.oracle/checkins/batch-2-r1.md:3078: trailing whitespace.
+++++++    57	
.oracle/checkins/batch-2-r1.md:3080: trailing whitespace.
+++++++    60	
.oracle/checkins/batch-2-r1.md:3082: trailing whitespace.
+++++++    61	
.oracle/checkins/batch-2-r1.md:3084: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2-r1.md:3086: trailing whitespace.
+++++++    73	
.oracle/checkins/batch-2-r1.md:3088: trailing whitespace.
+++++++    81	
.oracle/checkins/batch-2-r1.md:3090: trailing whitespace.
+++++++    88	
.oracle/checkins/batch-2-r1.md:3092: trailing whitespace.
+++++++    89	
.oracle/checkins/batch-2-r1.md:3094: trailing whitespace.
+++++++    96	
.oracle/checkins/batch-2-r1.md:3096: trailing whitespace.
+++++++    97	
.oracle/checkins/batch-2-r1.md:3098: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2-r1.md:3100: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2-r1.md:3102: trailing whitespace.
+++++++   113	
.oracle/checkins/batch-2-r1.md:3104: trailing whitespace.
+++++++   114	
.oracle/checkins/batch-2-r1.md:3106: trailing whitespace.
+++++++   122	
.oracle/checkins/batch-2-r1.md:3108: trailing whitespace.
+++++++   123	
.oracle/checkins/batch-2-r1.md:3110: trailing whitespace.
+++++++   131	
.oracle/checkins/batch-2-r1.md:3112: trailing whitespace.
+++++++   132	
.oracle/checkins/batch-2-r1.md:3114: trailing whitespace.
+++++++   162	
.oracle/checkins/batch-2-r1.md:3116: trailing whitespace.
+++++++   163	
.oracle/checkins/batch-2-r1.md:3118: trailing whitespace.
+++++++   178	
.oracle/checkins/batch-2-r1.md:3120: trailing whitespace.
+++++++   179	
.oracle/checkins/batch-2-r1.md:3122: trailing whitespace.
+++++++   206	
.oracle/checkins/batch-2-r1.md:3124: trailing whitespace.
+++++++   207	
.oracle/checkins/batch-2-r1.md:3126: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2-r1.md:3128: trailing whitespace.
+++++++   250	
.oracle/checkins/batch-2-r1.md:3130: trailing whitespace.
+++++++   288	
.oracle/checkins/batch-2-r1.md:3132: trailing whitespace.
+++++++   289	
.oracle/checkins/batch-2-r1.md:3134: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2-r1.md:3136: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2-r1.md:3138: trailing whitespace.
+++++++   324	
.oracle/checkins/batch-2-r1.md:3140: trailing whitespace.
+++++++   325	
.oracle/checkins/batch-2-r1.md:3142: trailing whitespace.
+++++++   338	
.oracle/checkins/batch-2-r1.md:3144: trailing whitespace.
+++++++   339	
.oracle/checkins/batch-2-r1.md:3146: trailing whitespace.
+++++++   356	
.oracle/checkins/batch-2-r1.md:3148: trailing whitespace.
+++++++   357	
.oracle/checkins/batch-2-r1.md:3150: trailing whitespace.
+++++++   375	
.oracle/checkins/batch-2-r1.md:3152: trailing whitespace.
+++++++   376	
.oracle/checkins/batch-2-r1.md:3154: trailing whitespace.
+++++++    35	
.oracle/checkins/batch-2-r1.md:3156: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2-r1.md:3158: trailing whitespace.
+++++++    52	
.oracle/checkins/batch-2-r1.md:3160: trailing whitespace.
+++++++    73	
.oracle/checkins/batch-2-r1.md:3162: trailing whitespace.
+++++++   205	
.oracle/checkins/batch-2-r1.md:3164: trailing whitespace.
+++++++   206	
.oracle/checkins/batch-2-r1.md:3166: trailing whitespace.
+++++++   209	
.oracle/checkins/batch-2-r1.md:3168: trailing whitespace.
+++++++   215	
.oracle/checkins/batch-2-r1.md:3170: trailing whitespace.
+++++++   216	
.oracle/checkins/batch-2-r1.md:3172: trailing whitespace.
+++++++   225	
.oracle/checkins/batch-2-r1.md:3174: trailing whitespace.
+++++++   226	
.oracle/checkins/batch-2-r1.md:3176: trailing whitespace.
+++++++   231	
.oracle/checkins/batch-2-r1.md:3178: trailing whitespace.
+++++++   232	
.oracle/checkins/batch-2-r1.md:3180: trailing whitespace.
+++++++   288	
.oracle/checkins/batch-2-r1.md:3182: trailing whitespace.
+++++++   289	
.oracle/checkins/batch-2-r1.md:3184: trailing whitespace.
+++++++   158	
.oracle/checkins/batch-2-r1.md:3186: trailing whitespace.
+++++++   159	
.oracle/checkins/batch-2-r1.md:3188: trailing whitespace.
+++++++   165	
.oracle/checkins/batch-2-r1.md:3190: trailing whitespace.
+++++++   166	
.oracle/checkins/batch-2-r1.md:3192: trailing whitespace.
+++++++   171	
.oracle/checkins/batch-2-r1.md:3194: trailing whitespace.
+++++++   172	
.oracle/checkins/batch-2-r1.md:3196: trailing whitespace.
+++++++   186	
.oracle/checkins/batch-2-r1.md:3198: trailing whitespace.
+++++++   187	
.oracle/checkins/batch-2-r1.md:3200: trailing whitespace.
+++++++   194	
.oracle/checkins/batch-2-r1.md:3202: trailing whitespace.
+++++++   195	
.oracle/checkins/batch-2-r1.md:3204: trailing whitespace.
+++++++   205	
.oracle/checkins/batch-2-r1.md:3206: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3208: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3210: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3212: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3214: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3216: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3218: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3220: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3222: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3224: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3226: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3228: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3230: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3232: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3234: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3236: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3238: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3240: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3242: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3244: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3246: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3248: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3250: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3252: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3254: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3256: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3258: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3260: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3262: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3264: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3266: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3268: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3270: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3272: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3274: trailing whitespace.
++++++    92	
.oracle/checkins/batch-2-r1.md:3276: trailing whitespace.
++++++    93	
.oracle/checkins/batch-2-r1.md:3278: trailing whitespace.
++++++   105	
.oracle/checkins/batch-2-r1.md:3280: trailing whitespace.
++++++   106	
.oracle/checkins/batch-2-r1.md:3282: trailing whitespace.
++++++   181	
.oracle/checkins/batch-2-r1.md:3284: trailing whitespace.
++++++   182	
.oracle/checkins/batch-2-r1.md:3286: trailing whitespace.
++++++   285	
.oracle/checkins/batch-2-r1.md:3288: trailing whitespace.
++++++   294	
.oracle/checkins/batch-2-r1.md:3290: trailing whitespace.
++++++   295	
.oracle/checkins/batch-2-r1.md:3292: trailing whitespace.
++++++   302	
.oracle/checkins/batch-2-r1.md:3294: trailing whitespace.
++++++   303	
.oracle/checkins/batch-2-r1.md:3296: trailing whitespace.
++++++   312	
.oracle/checkins/batch-2-r1.md:3298: trailing whitespace.
++++++   313	
.oracle/checkins/batch-2-r1.md:3300: trailing whitespace.
++++++   330	
.oracle/checkins/batch-2-r1.md:3302: trailing whitespace.
++++++   331	
.oracle/checkins/batch-2-r1.md:3304: trailing whitespace.
++++++   582	
.oracle/checkins/batch-2-r1.md:3306: trailing whitespace.
++++++   583	
.oracle/checkins/batch-2-r1.md:3308: trailing whitespace.
++++++   587	
.oracle/checkins/batch-2-r1.md:3310: trailing whitespace.
++++++   592	
.oracle/checkins/batch-2-r1.md:3312: trailing whitespace.
++++++   604	
.oracle/checkins/batch-2-r1.md:3314: trailing whitespace.
++++++   609	
.oracle/checkins/batch-2-r1.md:3316: trailing whitespace.
++++++   621	
.oracle/checkins/batch-2-r1.md:3318: trailing whitespace.
++++++   633	
.oracle/checkins/batch-2-r1.md:3320: trailing whitespace.
++++++   634	
.oracle/checkins/batch-2-r1.md:3322: trailing whitespace.
++++++   655	
.oracle/checkins/batch-2-r1.md:3324: trailing whitespace.
++++++   656	
.oracle/checkins/batch-2-r1.md:3326: trailing whitespace.
++++++   660	
.oracle/checkins/batch-2-r1.md:3328: trailing whitespace.
++++++   667	
.oracle/checkins/batch-2-r1.md:3330: trailing whitespace.
++++++   690	
.oracle/checkins/batch-2-r1.md:3332: trailing whitespace.
++++++   702	
.oracle/checkins/batch-2-r1.md:3334: trailing whitespace.
++++++   717	
.oracle/checkins/batch-2-r1.md:3336: trailing whitespace.
++++++   738	
.oracle/checkins/batch-2-r1.md:3338: trailing whitespace.
++++++   739	
.oracle/checkins/batch-2-r1.md:3340: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3342: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3344: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3346: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3348: trailing whitespace.
++++++   520	
.oracle/checkins/batch-2-r1.md:3350: trailing whitespace.
++++++   539	
.oracle/checkins/batch-2-r1.md:3352: trailing whitespace.
++++++   540	
.oracle/checkins/batch-2-r1.md:3354: trailing whitespace.
++++++   550	
.oracle/checkins/batch-2-r1.md:3356: trailing whitespace.
++++++   551	
.oracle/checkins/batch-2-r1.md:3358: trailing whitespace.
++++++   613	
.oracle/checkins/batch-2-r1.md:3360: trailing whitespace.
++++++   617	
.oracle/checkins/batch-2-r1.md:3362: trailing whitespace.
++++++   618	
.oracle/checkins/batch-2-r1.md:3364: trailing whitespace.
++++++   631	
.oracle/checkins/batch-2-r1.md:3366: trailing whitespace.
++++++   632	
.oracle/checkins/batch-2-r1.md:3368: trailing whitespace.
++++++   635	
.oracle/checkins/batch-2-r1.md:3370: trailing whitespace.
++++++   644	
.oracle/checkins/batch-2-r1.md:3372: trailing whitespace.
++++++   645	
.oracle/checkins/batch-2-r1.md:3374: trailing whitespace.
++++++   651	
.oracle/checkins/batch-2-r1.md:3376: trailing whitespace.
++++++   652	
.oracle/checkins/batch-2-r1.md:3378: trailing whitespace.
++++++   683	
.oracle/checkins/batch-2-r1.md:3380: trailing whitespace.
++++++   693	
.oracle/checkins/batch-2-r1.md:3382: trailing whitespace.
++++++   729	
.oracle/checkins/batch-2-r1.md:3384: trailing whitespace.
++++++   730	
.oracle/checkins/batch-2-r1.md:3386: trailing whitespace.
++++++   748	
.oracle/checkins/batch-2-r1.md:3388: trailing whitespace.
++++++   749	
.oracle/checkins/batch-2-r1.md:3390: trailing whitespace.
++++++   785	
.oracle/checkins/batch-2-r1.md:3392: trailing whitespace.
++++++   786	
.oracle/checkins/batch-2-r1.md:3394: trailing whitespace.
++++++   800	
.oracle/checkins/batch-2-r1.md:3396: trailing whitespace.
++++++   801	
.oracle/checkins/batch-2-r1.md:3398: trailing whitespace.
++++++   817	
.oracle/checkins/batch-2-r1.md:3400: trailing whitespace.
++++++   818	
.oracle/checkins/batch-2-r1.md:3402: trailing whitespace.
++++++   914	
.oracle/checkins/batch-2-r1.md:3404: trailing whitespace.
++++++   915	
.oracle/checkins/batch-2-r1.md:3406: trailing whitespace.
++++++  1014	
.oracle/checkins/batch-2-r1.md:3408: trailing whitespace.
++++++  1015	
.oracle/checkins/batch-2-r1.md:3410: trailing whitespace.
++++++  1024	
.oracle/checkins/batch-2-r1.md:3412: trailing whitespace.
++++++  1025	
.oracle/checkins/batch-2-r1.md:3414: trailing whitespace.
++++++     2	
.oracle/checkins/batch-2-r1.md:3416: trailing whitespace.
++++++     4	
.oracle/checkins/batch-2-r1.md:3418: trailing whitespace.
++++++     6	
.oracle/checkins/batch-2-r1.md:3420: trailing whitespace.
++++++     8	
.oracle/checkins/batch-2-r1.md:3422: trailing whitespace.
++++++    17	
.oracle/checkins/batch-2-r1.md:3424: trailing whitespace.
++++++    19	
.oracle/checkins/batch-2-r1.md:3426: trailing whitespace.
++++++    25	
.oracle/checkins/batch-2-r1.md:3428: trailing whitespace.
++++++    27	
.oracle/checkins/batch-2-r1.md:3430: trailing whitespace.
++++++    29	
.oracle/checkins/batch-2-r1.md:3432: trailing whitespace.
++++++    31	
.oracle/checkins/batch-2-r1.md:3434: trailing whitespace.
++++++    40	
.oracle/checkins/batch-2-r1.md:3436: trailing whitespace.
++++++    42	
.oracle/checkins/batch-2-r1.md:3438: trailing whitespace.
++++++    49	
.oracle/checkins/batch-2-r1.md:3440: trailing whitespace.
++++++    51	
.oracle/checkins/batch-2-r1.md:3442: trailing whitespace.
++++++    53	
.oracle/checkins/batch-2-r1.md:3444: trailing whitespace.
++++++    55	
.oracle/checkins/batch-2-r1.md:3446: trailing whitespace.
++++++    63	
.oracle/checkins/batch-2-r1.md:3448: trailing whitespace.
++++++    65	
.oracle/checkins/batch-2-r1.md:3450: trailing whitespace.
++++++    72	
.oracle/checkins/batch-2-r1.md:3452: trailing whitespace.
++++++    74	
.oracle/checkins/batch-2-r1.md:3454: trailing whitespace.
++++++    76	
.oracle/checkins/batch-2-r1.md:3456: trailing whitespace.
++++++    78	
.oracle/checkins/batch-2-r1.md:3458: trailing whitespace.
++++++    86	
.oracle/checkins/batch-2-r1.md:3460: trailing whitespace.
++++++    88	
.oracle/checkins/batch-2-r1.md:3462: trailing whitespace.
++++++    94	
.oracle/checkins/batch-2-r1.md:3464: trailing whitespace.
++++++    96	
.oracle/checkins/batch-2-r1.md:3466: trailing whitespace.
++++++    98	
.oracle/checkins/batch-2-r1.md:3468: trailing whitespace.
++++++   100	
.oracle/checkins/batch-2-r1.md:3470: trailing whitespace.
++++++   109	
.oracle/checkins/batch-2-r1.md:3472: trailing whitespace.
++++++   111	
.oracle/checkins/batch-2-r1.md:3474: trailing whitespace.
++++++   119	
.oracle/checkins/batch-2-r1.md:3476: trailing whitespace.
++++++   121	
.oracle/checkins/batch-2-r1.md:3478: trailing whitespace.
++++++   123	
.oracle/checkins/batch-2-r1.md:3480: trailing whitespace.
++++++   125	
.oracle/checkins/batch-2-r1.md:3482: trailing whitespace.
++++++   133	
.oracle/checkins/batch-2-r1.md:3484: trailing whitespace.
++++++   135	
.oracle/checkins/batch-2-r1.md:3486: trailing whitespace.
++++++   142	
.oracle/checkins/batch-2-r1.md:3488: trailing whitespace.
++++++   144	
.oracle/checkins/batch-2-r1.md:3490: trailing whitespace.
++++++   146	
.oracle/checkins/batch-2-r1.md:3492: trailing whitespace.
++++++   148	
.oracle/checkins/batch-2-r1.md:3494: trailing whitespace.
++++++   159	
.oracle/checkins/batch-2-r1.md:3496: trailing whitespace.
++++++   161	
.oracle/checkins/batch-2-r1.md:3498: trailing whitespace.
++++++   168	
.oracle/checkins/batch-2-r1.md:3500: trailing whitespace.
++++++   170	
.oracle/checkins/batch-2-r1.md:3502: trailing whitespace.
++++++     2	
.oracle/checkins/batch-2-r1.md:3504: trailing whitespace.
++++++     4	
.oracle/checkins/batch-2-r1.md:3506: trailing whitespace.
++++++     6	
.oracle/checkins/batch-2-r1.md:3508: trailing whitespace.
++++++     8	
.oracle/checkins/batch-2-r1.md:3510: trailing whitespace.
++++++    17	
.oracle/checkins/batch-2-r1.md:3512: trailing whitespace.
++++++    19	
.oracle/checkins/batch-2-r1.md:3514: trailing whitespace.
++++++    25	
.oracle/checkins/batch-2-r1.md:3516: trailing whitespace.
++++++    27	
.oracle/checkins/batch-2-r1.md:3518: trailing whitespace.
++++++    29	
.oracle/checkins/batch-2-r1.md:3520: trailing whitespace.
++++++    31	
.oracle/checkins/batch-2-r1.md:3522: trailing whitespace.
++++++    40	
.oracle/checkins/batch-2-r1.md:3524: trailing whitespace.
++++++    42	
.oracle/checkins/batch-2-r1.md:3526: trailing whitespace.
++++++    49	
.oracle/checkins/batch-2-r1.md:3528: trailing whitespace.
++++++    51	
.oracle/checkins/batch-2-r1.md:3530: trailing whitespace.
++++++    53	
.oracle/checkins/batch-2-r1.md:3532: trailing whitespace.
++++++    55	
.oracle/checkins/batch-2-r1.md:3534: trailing whitespace.
++++++    63	
.oracle/checkins/batch-2-r1.md:3536: trailing whitespace.
++++++    65	
.oracle/checkins/batch-2-r1.md:3538: trailing whitespace.
++++++    72	
.oracle/checkins/batch-2-r1.md:3540: trailing whitespace.
++++++   105	
.oracle/checkins/batch-2-r1.md:3542: trailing whitespace.
++++++   106	
.oracle/checkins/batch-2-r1.md:3544: trailing whitespace.
++++++   173	
.oracle/checkins/batch-2-r1.md:3546: trailing whitespace.
++++++   174	
.oracle/checkins/batch-2-r1.md:3548: trailing whitespace.
++++++A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-2-r1.md:3550: trailing whitespace.
++++++   186	
.oracle/checkins/batch-2-r1.md:3552: trailing whitespace.
++++++   187	
.oracle/checkins/batch-2-r1.md:3554: trailing whitespace.
++++++   194	
.oracle/checkins/batch-2-r1.md:3556: trailing whitespace.
++++++   195	
.oracle/checkins/batch-2-r1.md:3558: trailing whitespace.
++++++   205	
.oracle/checkins/batch-2-r1.md:3560: trailing whitespace.
++++++   206	
.oracle/checkins/batch-2-r1.md:3562: trailing whitespace.
++++++   209	
.oracle/checkins/batch-2-r1.md:3564: trailing whitespace.
++++++   215	
.oracle/checkins/batch-2-r1.md:3566: trailing whitespace.
++++++   216	
.oracle/checkins/batch-2-r1.md:3568: trailing whitespace.
++++++   225	
.oracle/checkins/batch-2-r1.md:3570: trailing whitespace.
++++++   226	
.oracle/checkins/batch-2-r1.md:3572: trailing whitespace.
++++++   231	
.oracle/checkins/batch-2-r1.md:3574: trailing whitespace.
++++++   232	
.oracle/checkins/batch-2-r1.md:3576: trailing whitespace.
++++++   241	
.oracle/checkins/batch-2-r1.md:3578: trailing whitespace.
++++++   242	
.oracle/checkins/batch-2-r1.md:3580: trailing whitespace.
++++++   248	
.oracle/checkins/batch-2-r1.md:3582: trailing whitespace.
++++++   249	
.oracle/checkins/batch-2-r1.md:3584: trailing whitespace.
++++++   262	
.oracle/checkins/batch-2-r1.md:3586: trailing whitespace.
++++++   263	
.oracle/checkins/batch-2-r1.md:3588: trailing whitespace.
++++++   268	
.oracle/checkins/batch-2-r1.md:3590: trailing whitespace.
++++++   269	
.oracle/checkins/batch-2-r1.md:3592: trailing whitespace.
++++++   276	
.oracle/checkins/batch-2-r1.md:3594: trailing whitespace.
++++++   277	
.oracle/checkins/batch-2-r1.md:3596: trailing whitespace.
++++++   284	
.oracle/checkins/batch-2-r1.md:3598: trailing whitespace.
++++++   285	
.oracle/checkins/batch-2-r1.md:3600: trailing whitespace.
++++++     2	
.oracle/checkins/batch-2-r1.md:3602: trailing whitespace.
++++++     8	
.oracle/checkins/batch-2-r1.md:3604: trailing whitespace.
++++++    11	
.oracle/checkins/batch-2-r1.md:3606: trailing whitespace.
++++++    20	
.oracle/checkins/batch-2-r1.md:3608: trailing whitespace.
++++++    21	
.oracle/checkins/batch-2-r1.md:3610: trailing whitespace.
++++++    48	
.oracle/checkins/batch-2-r1.md:3612: trailing whitespace.
++++++    49	
.oracle/checkins/batch-2-r1.md:3614: trailing whitespace.
++++++    52	
.oracle/checkins/batch-2-r1.md:3616: trailing whitespace.
++++++    53	
.oracle/checkins/batch-2-r1.md:3618: trailing whitespace.
++++++    56	
.oracle/checkins/batch-2-r1.md:3620: trailing whitespace.
++++++    57	
.oracle/checkins/batch-2-r1.md:3622: trailing whitespace.
++++++    60	
.oracle/checkins/batch-2-r1.md:3624: trailing whitespace.
++++++    61	
.oracle/checkins/batch-2-r1.md:3626: trailing whitespace.
++++++    72	
.oracle/checkins/batch-2-r1.md:3628: trailing whitespace.
++++++    73	
.oracle/checkins/batch-2-r1.md:3630: trailing whitespace.
++++++    81	
.oracle/checkins/batch-2-r1.md:3632: trailing whitespace.
++++++    88	
.oracle/checkins/batch-2-r1.md:3634: trailing whitespace.
++++++    89	
.oracle/checkins/batch-2-r1.md:3636: trailing whitespace.
++++++    96	
.oracle/checkins/batch-2-r1.md:3638: trailing whitespace.
++++++    97	
.oracle/checkins/batch-2-r1.md:3640: trailing whitespace.
++++++   105	
.oracle/checkins/batch-2-r1.md:3642: trailing whitespace.
++++++   106	
.oracle/checkins/batch-2-r1.md:3644: trailing whitespace.
++++++   113	
.oracle/checkins/batch-2-r1.md:3646: trailing whitespace.
++++++   114	
.oracle/checkins/batch-2-r1.md:3648: trailing whitespace.
++++++   122	
.oracle/checkins/batch-2-r1.md:3650: trailing whitespace.
++++++   123	
.oracle/checkins/batch-2-r1.md:3652: trailing whitespace.
++++++   131	
.oracle/checkins/batch-2-r1.md:3654: trailing whitespace.
++++++   132	
.oracle/checkins/batch-2-r1.md:3656: trailing whitespace.
++++++   162	
.oracle/checkins/batch-2-r1.md:3658: trailing whitespace.
++++++   163	
.oracle/checkins/batch-2-r1.md:3660: trailing whitespace.
++++++   178	
.oracle/checkins/batch-2-r1.md:3662: trailing whitespace.
++++++   179	
.oracle/checkins/batch-2-r1.md:3664: trailing whitespace.
++++++   206	
.oracle/checkins/batch-2-r1.md:3666: trailing whitespace.
++++++   207	
.oracle/checkins/batch-2-r1.md:3668: trailing whitespace.
++++++   249	
.oracle/checkins/batch-2-r1.md:3670: trailing whitespace.
++++++   250	
.oracle/checkins/batch-2-r1.md:3672: trailing whitespace.
++++++   288	
.oracle/checkins/batch-2-r1.md:3674: trailing whitespace.
++++++   289	
.oracle/checkins/batch-2-r1.md:3676: trailing whitespace.
++++++   312	
.oracle/checkins/batch-2-r1.md:3678: trailing whitespace.
++++++   313	
.oracle/checkins/batch-2-r1.md:3680: trailing whitespace.
++++++   324	
.oracle/checkins/batch-2-r1.md:3682: trailing whitespace.
++++++   325	
.oracle/checkins/batch-2-r1.md:3684: trailing whitespace.
++++++   338	
.oracle/checkins/batch-2-r1.md:3686: trailing whitespace.
++++++   339	
.oracle/checkins/batch-2-r1.md:3688: trailing whitespace.
++++++   356	
.oracle/checkins/batch-2-r1.md:3690: trailing whitespace.
++++++   357	
.oracle/checkins/batch-2-r1.md:3692: trailing whitespace.
++++++   375	
.oracle/checkins/batch-2-r1.md:3694: trailing whitespace.
++++++   376	
.oracle/checkins/batch-2-r1.md:3696: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3698: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r1.md:3700: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3702: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3704: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3706: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3708: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3710: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3712: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3714: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3716: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3718: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3720: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3722: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3724: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3726: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3728: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3730: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3732: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3734: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3736: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3738: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3740: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3742: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3744: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3746: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3748: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3750: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3752: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3754: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3756: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3758: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3760: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3762: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3764: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3766: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3768: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3770: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3772: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3774: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3776: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3778: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3780: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3782: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3784: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3786: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3788: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3790: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3792: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3794: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3796: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3798: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3800: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3802: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3804: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3806: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3808: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3810: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3812: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3814: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3816: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3818: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3820: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3822: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3824: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3826: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3828: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3830: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3832: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3834: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3836: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3838: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3840: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3842: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3844: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3846: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3848: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3850: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3852: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3854: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3856: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3858: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3860: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3862: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3864: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3866: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3868: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3870: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3872: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3874: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3876: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3878: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3880: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3882: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3884: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3886: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3888: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3890: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3892: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3894: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3896: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3898: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3900: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3902: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3904: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3906: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3908: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3910: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3912: trailing whitespace.
+++++   190	
.oracle/checkins/batch-2-r1.md:3914: trailing whitespace.
+++++   191	
.oracle/checkins/batch-2-r1.md:3916: trailing whitespace.
+++++   215	
.oracle/checkins/batch-2-r1.md:3918: trailing whitespace.
+++++   216	
.oracle/checkins/batch-2-r1.md:3920: trailing whitespace.
+++++   225	
.oracle/checkins/batch-2-r1.md:3922: trailing whitespace.
+++++   226	
.oracle/checkins/batch-2-r1.md:3924: trailing whitespace.
+++++   231	
.oracle/checkins/batch-2-r1.md:3926: trailing whitespace.
+++++   232	
.oracle/checkins/batch-2-r1.md:3928: trailing whitespace.
+++++   241	
.oracle/checkins/batch-2-r1.md:3930: trailing whitespace.
+++++   242	
.oracle/checkins/batch-2-r1.md:3932: trailing whitespace.
+++++   248	
.oracle/checkins/batch-2-r1.md:3934: trailing whitespace.
+++++   249	
.oracle/checkins/batch-2-r1.md:3936: trailing whitespace.
+++++   262	
.oracle/checkins/batch-2-r1.md:3938: trailing whitespace.
+++++   263	
.oracle/checkins/batch-2-r1.md:3940: trailing whitespace.
+++++   268	
.oracle/checkins/batch-2-r1.md:3942: trailing whitespace.
+++++   269	
.oracle/checkins/batch-2-r1.md:3944: trailing whitespace.
+++++   276	
.oracle/checkins/batch-2-r1.md:3946: trailing whitespace.
+++++   277	
.oracle/checkins/batch-2-r1.md:3948: trailing whitespace.
+++++   284	
.oracle/checkins/batch-2-r1.md:3950: trailing whitespace.
+++++   285	
.oracle/checkins/batch-2-r1.md:3952: trailing whitespace.
+++++   294	
.oracle/checkins/batch-2-r1.md:3954: trailing whitespace.
+++++   295	
.oracle/checkins/batch-2-r1.md:3956: trailing whitespace.
+++++   302	
.oracle/checkins/batch-2-r1.md:3958: trailing whitespace.
+++++   303	
.oracle/checkins/batch-2-r1.md:3960: trailing whitespace.
+++++   312	
.oracle/checkins/batch-2-r1.md:3962: trailing whitespace.
+++++   313	
.oracle/checkins/batch-2-r1.md:3964: trailing whitespace.
+++++   333	
.oracle/checkins/batch-2-r1.md:3966: trailing whitespace.
+++++   334	
.oracle/checkins/batch-2-r1.md:3968: trailing whitespace.
+++++   375	
.oracle/checkins/batch-2-r1.md:3970: trailing whitespace.
+++++   376	
.oracle/checkins/batch-2-r1.md:3972: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3974: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3976: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:3978: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:3980: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:3982: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r1.md:3984: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3986: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3988: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3990: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3992: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3994: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3996: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:3998: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4000: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4002: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4004: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4006: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4008: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4010: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4012: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4014: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4016: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4018: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4020: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4022: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4024: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4026: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4028: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4030: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4032: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4034: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4036: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4038: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4040: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4042: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4044: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4046: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4048: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4050: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4052: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4054: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4056: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4058: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4060: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4062: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4064: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4066: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4068: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4070: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4072: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4074: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4076: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4078: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4080: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4082: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4084: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4086: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4088: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4090: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4092: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4094: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4096: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4098: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4100: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4102: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4104: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4106: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4108: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4110: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4112: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4114: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4116: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4118: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4120: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4122: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4124: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4126: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4128: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4130: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4132: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4134: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4136: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4138: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4140: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4142: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4144: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4146: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4148: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4150: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4152: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4154: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4156: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4158: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4160: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4162: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4164: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4166: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4168: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4170: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4172: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4174: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4176: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4178: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4180: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4182: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4184: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4186: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4188: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4190: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4192: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4194: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4196: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4198: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4200: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4202: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4204: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4206: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4208: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4210: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4212: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4214: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4216: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4218: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4220: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4222: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4224: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4226: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4228: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4230: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4232: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4234: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4236: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4238: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4240: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4242: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4244: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4246: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4248: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4250: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4252: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4254: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4256: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4258: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4260: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4262: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4264: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4266: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4268: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4270: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4272: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4274: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4276: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4278: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4280: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4282: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4284: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4286: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4288: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4290: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r1.md:4292: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r1.md:4294: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r1.md:4296: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r1.md:4298: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r1.md:4300: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r1.md:4302: trailing whitespace.
+++    56	
.oracle/checkins/batch-2-r1.md:4304: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r1.md:4306: trailing whitespace.
+++    72	
.oracle/checkins/batch-2-r1.md:4308: trailing whitespace.
+++    75	
.oracle/checkins/batch-2-r1.md:4310: trailing whitespace.
+++    95	
.oracle/checkins/batch-2-r1.md:4312: trailing whitespace.
+++    99	
.oracle/checkins/batch-2-r1.md:4314: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r1.md:4316: trailing whitespace.
+++    10	
.oracle/checkins/batch-2-r1.md:4318: trailing whitespace.
+++    12	
.oracle/checkins/batch-2-r1.md:4320: trailing whitespace.
+++    17	
.oracle/checkins/batch-2-r1.md:4322: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r1.md:4324: trailing whitespace.
+++    25	
.oracle/checkins/batch-2-r1.md:4326: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r1.md:4328: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r1.md:4330: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r1.md:4332: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r1.md:4334: trailing whitespace.
+++    45	
.oracle/checkins/batch-2-r1.md:4336: trailing whitespace.
+++    48	
.oracle/checkins/batch-2-r1.md:4338: trailing whitespace.
+++    51	
.oracle/checkins/batch-2-r1.md:4340: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:4342: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r1.md:4344: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r1.md:4346: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r1.md:4348: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r1.md:4350: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r1.md:4352: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r1.md:4354: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r1.md:4356: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:4358: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r1.md:4360: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r1.md:4362: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r1.md:4364: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r1.md:4366: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r1.md:4368: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r1.md:4370: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:4372: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r1.md:4374: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r1.md:4376: trailing whitespace.
++   108	
.oracle/checkins/batch-2-r1.md:4378: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r1.md:4380: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r1.md:4382: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r1.md:4384: trailing whitespace.
++   130	
.oracle/checkins/batch-2-r1.md:4386: trailing whitespace.
++   135	
.oracle/checkins/batch-2-r1.md:4388: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r1.md:4390: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r1.md:4392: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r1.md:4394: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r1.md:4396: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r1.md:4398: trailing whitespace.
++   205	
.oracle/checkins/batch-2-r1.md:4400: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r1.md:4402: trailing whitespace.
++   218	
.oracle/checkins/batch-2-r1.md:4404: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r1.md:4406: trailing whitespace.
++   247	
.oracle/checkins/batch-2-r1.md:4408: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r1.md:4410: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:4412: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r1.md:4414: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r1.md:4416: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r1.md:4418: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r1.md:4420: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r1.md:4422: trailing whitespace.
++   255	
.oracle/checkins/batch-2-r1.md:4424: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r1.md:4426: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r1.md:4428: trailing whitespace.
++   270	
.oracle/checkins/batch-2-r1.md:4430: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r1.md:4432: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r1.md:4434: trailing whitespace.
++   296	
.oracle/checkins/batch-2-r1.md:4436: trailing whitespace.
++   306	
.oracle/checkins/batch-2-r1.md:4438: trailing whitespace.
++   307	
.oracle/checkins/batch-2-r1.md:4440: trailing whitespace.
++    14	
.oracle/checkins/batch-2-r1.md:4442: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r1.md:4444: trailing whitespace.
++    35	
.oracle/checkins/batch-2-r1.md:4446: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r1.md:4448: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:4450: trailing whitespace.
++     5	
.oracle/checkins/batch-2-r1.md:4452: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:4454: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r1.md:4456: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r1.md:4458: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r1.md:4460: trailing whitespace.
++    28	
.oracle/checkins/batch-2-r1.md:4462: trailing whitespace.
++    29	
.oracle/checkins/batch-2-r1.md:4464: trailing whitespace.
++    32	
.oracle/checkins/batch-2-r1.md:4466: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r1.md:4468: trailing whitespace.
++    43	
.oracle/checkins/batch-2-r1.md:4470: trailing whitespace.
++    44	
.oracle/checkins/batch-2-r1.md:4472: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r1.md:4474: trailing whitespace.
++    52	
.oracle/checkins/batch-2-r1.md:4476: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r1.md:4478: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r1.md:4480: trailing whitespace.
++    70	
.oracle/checkins/batch-2-r1.md:4482: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r1.md:4484: trailing whitespace.
++    74	
.oracle/checkins/batch-2-r1.md:4486: trailing whitespace.
++    83	
.oracle/checkins/batch-2-r1.md:4488: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r1.md:4490: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:4492: trailing whitespace.
++   108	
.oracle/checkins/batch-2-r1.md:4494: trailing whitespace.
++   110	
.oracle/checkins/batch-2-r1.md:4496: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r1.md:4498: trailing whitespace.
++   115	
.oracle/checkins/batch-2-r1.md:4500: trailing whitespace.
++   121	
.oracle/checkins/batch-2-r1.md:4502: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r1.md:4504: trailing whitespace.
++   124	
.oracle/checkins/batch-2-r1.md:4506: trailing whitespace.
++   137	
.oracle/checkins/batch-2-r1.md:4508: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r1.md:4510: trailing whitespace.
++   146	
.oracle/checkins/batch-2-r1.md:4512: trailing whitespace.
++   147	
.oracle/checkins/batch-2-r1.md:4514: trailing whitespace.
++   157	
.oracle/checkins/batch-2-r1.md:4516: trailing whitespace.
++   297	
.oracle/checkins/batch-2-r1.md:4518: trailing whitespace.
++   298	
.oracle/checkins/batch-2-r1.md:4520: trailing whitespace.
++   301	
.oracle/checkins/batch-2-r1.md:4522: trailing whitespace.
++   319	
.oracle/checkins/batch-2-r1.md:4524: trailing whitespace.
++   322	
.oracle/checkins/batch-2-r1.md:4526: trailing whitespace.
++   325	
.oracle/checkins/batch-2-r1.md:4528: trailing whitespace.
++   330	
.oracle/checkins/batch-2-r1.md:4530: trailing whitespace.
++   334	
.oracle/checkins/batch-2-r1.md:4532: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:4534: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r1.md:4536: trailing whitespace.
++    11	
.oracle/checkins/batch-2-r1.md:4538: trailing whitespace.
++    15	
.oracle/checkins/batch-2-r1.md:4540: trailing whitespace.
++    18	
.oracle/checkins/batch-2-r1.md:4542: trailing whitespace.
++    26	
.oracle/checkins/batch-2-r1.md:4544: trailing whitespace.
++    28	
.oracle/checkins/batch-2-r1.md:4546: trailing whitespace.
++    29	
.oracle/checkins/batch-2-r1.md:4548: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r1.md:4550: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r1.md:4552: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r1.md:4554: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:4556: trailing whitespace.
++    45	
.oracle/checkins/batch-2-r1.md:4558: trailing whitespace.
++    46	
.oracle/checkins/batch-2-r1.md:4560: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r1.md:4562: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r1.md:4564: trailing whitespace.
++    67	
.oracle/checkins/batch-2-r1.md:4566: trailing whitespace.
++    68	
.oracle/checkins/batch-2-r1.md:4568: trailing whitespace.
++    87	
.oracle/checkins/batch-2-r1.md:4570: trailing whitespace.
++    88	
.oracle/checkins/batch-2-r1.md:4572: trailing whitespace.
++   352	
.oracle/checkins/batch-2-r1.md:4574: trailing whitespace.
++   353	
.oracle/checkins/batch-2-r1.md:4576: trailing whitespace.
++   356	
.oracle/checkins/batch-2-r1.md:4578: trailing whitespace.
++   362	
.oracle/checkins/batch-2-r1.md:4580: trailing whitespace.
++   363	
.oracle/checkins/batch-2-r1.md:4582: trailing whitespace.
++   366	
.oracle/checkins/batch-2-r1.md:4584: trailing whitespace.
++   370	
.oracle/checkins/batch-2-r1.md:4586: trailing whitespace.
++   371	
.oracle/checkins/batch-2-r1.md:4588: trailing whitespace.
++   385	
.oracle/checkins/batch-2-r1.md:4590: trailing whitespace.
++   386	
.oracle/checkins/batch-2-r1.md:4592: trailing whitespace.
++   390	
.oracle/checkins/batch-2-r1.md:4594: trailing whitespace.
++   396	
.oracle/checkins/batch-2-r1.md:4596: trailing whitespace.
++   417	
.oracle/checkins/batch-2-r1.md:4598: trailing whitespace.
++   421	
.oracle/checkins/batch-2-r1.md:4600: trailing whitespace.
++   432	
.oracle/checkins/batch-2-r1.md:4602: trailing whitespace.
++   449	
.oracle/checkins/batch-2-r1.md:4604: trailing whitespace.
++   450	
.oracle/checkins/batch-2-r1.md:4606: trailing whitespace.
++   454	
.oracle/checkins/batch-2-r1.md:4608: trailing whitespace.
++   468	
.oracle/checkins/batch-2-r1.md:4610: trailing whitespace.
++   664	
.oracle/checkins/batch-2-r1.md:4612: trailing whitespace.
++   665	
.oracle/checkins/batch-2-r1.md:4614: trailing whitespace.
++   669	
.oracle/checkins/batch-2-r1.md:4616: trailing whitespace.
++   676	
.oracle/checkins/batch-2-r1.md:4618: trailing whitespace.
++   699	
.oracle/checkins/batch-2-r1.md:4620: trailing whitespace.
++   711	
.oracle/checkins/batch-2-r1.md:4622: trailing whitespace.
++   726	
.oracle/checkins/batch-2-r1.md:4624: trailing whitespace.
++   747	
.oracle/checkins/batch-2-r1.md:4626: trailing whitespace.
++   748	
.oracle/checkins/batch-2-r1.md:4628: trailing whitespace.
++   755	
.oracle/checkins/batch-2-r1.md:4630: trailing whitespace.
++   756	
.oracle/checkins/batch-2-r1.md:4632: trailing whitespace.
++   763	
.oracle/checkins/batch-2-r1.md:4634: trailing whitespace.
++   764	
.oracle/checkins/batch-2-r1.md:4636: trailing whitespace.
++   772	
.oracle/checkins/batch-2-r1.md:4638: trailing whitespace.
++   773	
.oracle/checkins/batch-2-r1.md:4640: trailing whitespace.
++   777	
.oracle/checkins/batch-2-r1.md:4642: trailing whitespace.
++   787	
.oracle/checkins/batch-2-r1.md:4644: trailing whitespace.
++   820	
.oracle/checkins/batch-2-r1.md:4646: trailing whitespace.
++   835	
.oracle/checkins/batch-2-r1.md:4648: trailing whitespace.
++  1511	
.oracle/checkins/batch-2-r1.md:4650: trailing whitespace.
++  1512	
.oracle/checkins/batch-2-r1.md:4652: trailing whitespace.
++  1527	
.oracle/checkins/batch-2-r1.md:4654: trailing whitespace.
++  1528	
.oracle/checkins/batch-2-r1.md:4656: trailing whitespace.
++  1532	
.oracle/checkins/batch-2-r1.md:4658: trailing whitespace.
++  1540	
.oracle/checkins/batch-2-r1.md:4660: trailing whitespace.
++  1566	
.oracle/checkins/batch-2-r1.md:4662: trailing whitespace.
++  1570	
.oracle/checkins/batch-2-r1.md:4664: trailing whitespace.
++  1572	
.oracle/checkins/batch-2-r1.md:4666: trailing whitespace.
++  1585	
.oracle/checkins/batch-2-r1.md:4668: trailing whitespace.
++  1609	
.oracle/checkins/batch-2-r1.md:4670: trailing whitespace.
++  1616	
.oracle/checkins/batch-2-r1.md:4672: trailing whitespace.
++  1617	
.oracle/checkins/batch-2-r1.md:4674: trailing whitespace.
++  1621	
.oracle/checkins/batch-2-r1.md:4676: trailing whitespace.
++   516	
.oracle/checkins/batch-2-r1.md:4678: trailing whitespace.
++   520	
.oracle/checkins/batch-2-r1.md:4680: trailing whitespace.
++   539	
.oracle/checkins/batch-2-r1.md:4682: trailing whitespace.
++   572	
.oracle/checkins/batch-2-r1.md:4684: trailing whitespace.
++   573	
.oracle/checkins/batch-2-r1.md:4686: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:4688: trailing whitespace.
++     4	
.oracle/checkins/batch-2-r1.md:4690: trailing whitespace.
++    12	
.oracle/checkins/batch-2-r1.md:4692: trailing whitespace.
++    15	
.oracle/checkins/batch-2-r1.md:4694: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r1.md:4696: trailing whitespace.
++    25	
.oracle/checkins/batch-2-r1.md:4698: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:4700: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r1.md:4702: trailing whitespace.
++    49	
.oracle/checkins/batch-2-r1.md:4704: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r1.md:4706: trailing whitespace.
++    61	
.oracle/checkins/batch-2-r1.md:4708: trailing whitespace.
++    62	
.oracle/checkins/batch-2-r1.md:4710: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r1.md:4712: trailing whitespace.
++    91	
.oracle/checkins/batch-2-r1.md:4714: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r1.md:4716: trailing whitespace.
++   109	
.oracle/checkins/batch-2-r1.md:4718: trailing whitespace.
++   110	
.oracle/checkins/batch-2-r1.md:4720: trailing whitespace.
++   128	
.oracle/checkins/batch-2-r1.md:4722: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r1.md:4724: trailing whitespace.
++   152	
.oracle/checkins/batch-2-r1.md:4726: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r1.md:4728: trailing whitespace.
++   192	
.oracle/checkins/batch-2-r1.md:4730: trailing whitespace.
++   193	
.oracle/checkins/batch-2-r1.md:4732: trailing whitespace.
++   202	
.oracle/checkins/batch-2-r1.md:4734: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r1.md:4736: trailing whitespace.
++   223	
.oracle/checkins/batch-2-r1.md:4738: trailing whitespace.
++   224	
.oracle/checkins/batch-2-r1.md:4740: trailing whitespace.
++   240	
.oracle/checkins/batch-2-r1.md:4742: trailing whitespace.
++   241	
.oracle/checkins/batch-2-r1.md:4744: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r1.md:4746: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r1.md:4748: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r1.md:4750: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:4752: trailing whitespace.
++   266	
.oracle/checkins/batch-2-r1.md:4754: trailing whitespace.
++   267	
.oracle/checkins/batch-2-r1.md:4756: trailing whitespace.
++   270	
.oracle/checkins/batch-2-r1.md:4758: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r1.md:4760: trailing whitespace.
++   290	
.oracle/checkins/batch-2-r1.md:4762: trailing whitespace.
++   291	
.oracle/checkins/batch-2-r1.md:4764: trailing whitespace.
++   329	
.oracle/checkins/batch-2-r1.md:4766: trailing whitespace.
++   356	
.oracle/checkins/batch-2-r1.md:4768: trailing whitespace.
++   357	
.oracle/checkins/batch-2-r1.md:4770: trailing whitespace.
++   388	
.oracle/checkins/batch-2-r1.md:4772: trailing whitespace.
++   389	
.oracle/checkins/batch-2-r1.md:4774: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r1.md:4776: trailing whitespace.
++   452	
.oracle/checkins/batch-2-r1.md:4778: trailing whitespace.
++   453	
.oracle/checkins/batch-2-r1.md:4780: trailing whitespace.
++   474	
.oracle/checkins/batch-2-r1.md:4782: trailing whitespace.
++   499	
.oracle/checkins/batch-2-r1.md:4784: trailing whitespace.
++   500	
.oracle/checkins/batch-2-r1.md:4786: trailing whitespace.
++   527	
.oracle/checkins/batch-2-r1.md:4788: trailing whitespace.
++   528	
.oracle/checkins/batch-2-r1.md:4790: trailing whitespace.
++   553	
.oracle/checkins/batch-2-r1.md:4792: trailing whitespace.
++   554	
.oracle/checkins/batch-2-r1.md:4794: trailing whitespace.
++   594	
.oracle/checkins/batch-2-r1.md:4796: trailing whitespace.
++   595	
.oracle/checkins/batch-2-r1.md:4798: trailing whitespace.
++   622	
.oracle/checkins/batch-2-r1.md:4800: trailing whitespace.
++   623	
.oracle/checkins/batch-2-r1.md:4802: trailing whitespace.
++   631	
.oracle/checkins/batch-2-r1.md:4804: trailing whitespace.
++   637	
.oracle/checkins/batch-2-r1.md:4806: trailing whitespace.
++   644	
.oracle/checkins/batch-2-r1.md:4808: trailing whitespace.
++   663	
.oracle/checkins/batch-2-r1.md:4810: trailing whitespace.
++   673	
.oracle/checkins/batch-2-r1.md:4812: trailing whitespace.
++   694	
.oracle/checkins/batch-2-r1.md:4814: trailing whitespace.
++   695	
.oracle/checkins/batch-2-r1.md:4816: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r1.md:4818: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r1.md:4820: trailing whitespace.
++   140	
.oracle/checkins/batch-2-r1.md:4822: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r1.md:4824: trailing whitespace.
++   150	
.oracle/checkins/batch-2-r1.md:4826: trailing whitespace.
++   151	
.oracle/checkins/batch-2-r1.md:4828: trailing whitespace.
++   158	
.oracle/checkins/batch-2-r1.md:4830: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:4832: trailing whitespace.
++   166	
.oracle/checkins/batch-2-r1.md:4834: trailing whitespace.
++   176	
.oracle/checkins/batch-2-r1.md:4836: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r1.md:4838: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r1.md:4840: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r1.md:4842: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r1.md:4844: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r1.md:4846: trailing whitespace.
++   221	
.oracle/checkins/batch-2-r1.md:4848: trailing whitespace.
++   228	
.oracle/checkins/batch-2-r1.md:4850: trailing whitespace.
++   229	
.oracle/checkins/batch-2-r1.md:4852: trailing whitespace.
++   233	
.oracle/checkins/batch-2-r1.md:4854: trailing whitespace.
++   240	
.oracle/checkins/batch-2-r1.md:4856: trailing whitespace.
++   241	
.oracle/checkins/batch-2-r1.md:4858: trailing whitespace.
++   251	
.oracle/checkins/batch-2-r1.md:4860: trailing whitespace.
++   258	
.oracle/checkins/batch-2-r1.md:4862: trailing whitespace.
++   259	
.oracle/checkins/batch-2-r1.md:4864: trailing whitespace.
++   269	
.oracle/checkins/batch-2-r1.md:4866: trailing whitespace.
++   276	
.oracle/checkins/batch-2-r1.md:4868: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r1.md:4870: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:4872: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r1.md:4874: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:4876: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r1.md:4878: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r1.md:4880: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r1.md:4882: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r1.md:4884: trailing whitespace.
++    26	
.oracle/checkins/batch-2-r1.md:4886: trailing whitespace.
++    27	
.oracle/checkins/batch-2-r1.md:4888: trailing whitespace.
++    31	
.oracle/checkins/batch-2-r1.md:4890: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r1.md:4892: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:4894: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r1.md:4896: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r1.md:4898: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r1.md:4900: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r1.md:4902: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r1.md:4904: trailing whitespace.
++    71	
.oracle/checkins/batch-2-r1.md:4906: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r1.md:4908: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r1.md:4910: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:4912: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r1.md:4914: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r1.md:4916: trailing whitespace.
++    93	
.oracle/checkins/batch-2-r1.md:4918: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:4920: trailing whitespace.
++   107	
.oracle/checkins/batch-2-r1.md:4922: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r1.md:4924: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r1.md:4926: trailing whitespace.
++   124	
.oracle/checkins/batch-2-r1.md:4928: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r1.md:4930: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r1.md:4932: trailing whitespace.
++   133	
.oracle/checkins/batch-2-r1.md:4934: trailing whitespace.
++   150	
.oracle/checkins/batch-2-r1.md:4936: trailing whitespace.
++   151	
.oracle/checkins/batch-2-r1.md:4938: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r1.md:4940: trailing whitespace.
++   160	
.oracle/checkins/batch-2-r1.md:4942: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:4944: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r1.md:4946: trailing whitespace.
++   186	
.oracle/checkins/batch-2-r1.md:4948: trailing whitespace.
++   189	
.oracle/checkins/batch-2-r1.md:4950: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r1.md:4952: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r1.md:4954: trailing whitespace.
++   211	
.oracle/checkins/batch-2-r1.md:4956: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r1.md:4958: trailing whitespace.
++   226	
.oracle/checkins/batch-2-r1.md:4960: trailing whitespace.
++   228	
.oracle/checkins/batch-2-r1.md:4962: trailing whitespace.
++   229	
.oracle/checkins/batch-2-r1.md:4964: trailing whitespace.
++   241	
.oracle/checkins/batch-2-r1.md:4966: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r1.md:4968: trailing whitespace.
++   280	
.oracle/checkins/batch-2-r1.md:4970: trailing whitespace.
++   281	
.oracle/checkins/batch-2-r1.md:4972: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r1.md:4974: trailing whitespace.
++   293	
.oracle/checkins/batch-2-r1.md:4976: trailing whitespace.
++   294	
.oracle/checkins/batch-2-r1.md:4978: trailing whitespace.
++   301	
.oracle/checkins/batch-2-r1.md:4980: trailing whitespace.
++   307	
.oracle/checkins/batch-2-r1.md:4982: trailing whitespace.
++   309	
.oracle/checkins/batch-2-r1.md:4984: trailing whitespace.
++   310	
.oracle/checkins/batch-2-r1.md:4986: trailing whitespace.
++   314	
.oracle/checkins/batch-2-r1.md:4988: trailing whitespace.
++   315	
.oracle/checkins/batch-2-r1.md:4990: trailing whitespace.
++   323	
.oracle/checkins/batch-2-r1.md:4992: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:4994: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:4996: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:4998: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5000: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5002: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5004: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5006: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5008: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5010: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5012: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:5014: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r1.md:5016: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:5018: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r1.md:5020: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r1.md:5022: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r1.md:5024: trailing whitespace.
++    38	
.oracle/checkins/batch-2-r1.md:5026: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r1.md:5028: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r1.md:5030: trailing whitespace.
++    70	
.oracle/checkins/batch-2-r1.md:5032: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r1.md:5034: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r1.md:5036: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:5038: trailing whitespace.
++   113	
.oracle/checkins/batch-2-r1.md:5040: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r1.md:5042: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r1.md:5044: trailing whitespace.
++   144	
.oracle/checkins/batch-2-r1.md:5046: trailing whitespace.
++   160	
.oracle/checkins/batch-2-r1.md:5048: trailing whitespace.
++   171	
.oracle/checkins/batch-2-r1.md:5050: trailing whitespace.
++   202	
.oracle/checkins/batch-2-r1.md:5052: trailing whitespace.
++   237	
.oracle/checkins/batch-2-r1.md:5054: trailing whitespace.
++   241	
.oracle/checkins/batch-2-r1.md:5056: trailing whitespace.
++   248	
.oracle/checkins/batch-2-r1.md:5058: trailing whitespace.
++   260	
.oracle/checkins/batch-2-r1.md:5060: trailing whitespace.
++   260	
.oracle/checkins/batch-2-r1.md:5062: trailing whitespace.
++   261	
.oracle/checkins/batch-2-r1.md:5064: trailing whitespace.
++   268	
.oracle/checkins/batch-2-r1.md:5066: trailing whitespace.
++   269	
.oracle/checkins/batch-2-r1.md:5068: trailing whitespace.
++   285	
.oracle/checkins/batch-2-r1.md:5070: trailing whitespace.
++   286	
.oracle/checkins/batch-2-r1.md:5072: trailing whitespace.
++   317	
.oracle/checkins/batch-2-r1.md:5074: trailing whitespace.
++   318	
.oracle/checkins/batch-2-r1.md:5076: trailing whitespace.
++   335	
.oracle/checkins/batch-2-r1.md:5078: trailing whitespace.
++   336	
.oracle/checkins/batch-2-r1.md:5080: trailing whitespace.
++   339	
.oracle/checkins/batch-2-r1.md:5082: trailing whitespace.
++   340	
.oracle/checkins/batch-2-r1.md:5084: trailing whitespace.
++   346	
.oracle/checkins/batch-2-r1.md:5086: trailing whitespace.
++   347	
.oracle/checkins/batch-2-r1.md:5088: trailing whitespace.
++   383	
.oracle/checkins/batch-2-r1.md:5090: trailing whitespace.
++   392	
.oracle/checkins/batch-2-r1.md:5092: trailing whitespace.
++   393	
.oracle/checkins/batch-2-r1.md:5094: trailing whitespace.
++   400	
.oracle/checkins/batch-2-r1.md:5096: trailing whitespace.
++   401	
.oracle/checkins/batch-2-r1.md:5098: trailing whitespace.
++   418	
.oracle/checkins/batch-2-r1.md:5100: trailing whitespace.
++   419	
.oracle/checkins/batch-2-r1.md:5102: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r1.md:5104: trailing whitespace.
++   437	
.oracle/checkins/batch-2-r1.md:5106: trailing whitespace.
++   450	
.oracle/checkins/batch-2-r1.md:5108: trailing whitespace.
++   451	
.oracle/checkins/batch-2-r1.md:5110: trailing whitespace.
++   456	
.oracle/checkins/batch-2-r1.md:5112: trailing whitespace.
++   464	
.oracle/checkins/batch-2-r1.md:5114: trailing whitespace.
++   467	
.oracle/checkins/batch-2-r1.md:5116: trailing whitespace.
++   471	
.oracle/checkins/batch-2-r1.md:5118: trailing whitespace.
++   484	
.oracle/checkins/batch-2-r1.md:5120: trailing whitespace.
++   487	
.oracle/checkins/batch-2-r1.md:5122: trailing whitespace.
++   490	
.oracle/checkins/batch-2-r1.md:5124: trailing whitespace.
++   491	
.oracle/checkins/batch-2-r1.md:5126: trailing whitespace.
++   496	
.oracle/checkins/batch-2-r1.md:5128: trailing whitespace.
++   506	
.oracle/checkins/batch-2-r1.md:5130: trailing whitespace.
++   507	
.oracle/checkins/batch-2-r1.md:5132: trailing whitespace.
++   514	
.oracle/checkins/batch-2-r1.md:5134: trailing whitespace.
++   515	
.oracle/checkins/batch-2-r1.md:5136: trailing whitespace.
++   526	
.oracle/checkins/batch-2-r1.md:5138: trailing whitespace.
++   527	
.oracle/checkins/batch-2-r1.md:5140: trailing whitespace.
++   546	
.oracle/checkins/batch-2-r1.md:5142: trailing whitespace.
++   547	
.oracle/checkins/batch-2-r1.md:5144: trailing whitespace.
++   558	
.oracle/checkins/batch-2-r1.md:5146: trailing whitespace.
++   559	
.oracle/checkins/batch-2-r1.md:5148: trailing whitespace.
++   612	
.oracle/checkins/batch-2-r1.md:5150: trailing whitespace.
++   613	
.oracle/checkins/batch-2-r1.md:5152: trailing whitespace.
++   638	
.oracle/checkins/batch-2-r1.md:5154: trailing whitespace.
++   646	
.oracle/checkins/batch-2-r1.md:5156: trailing whitespace.
++   651	
.oracle/checkins/batch-2-r1.md:5158: trailing whitespace.
++   678	
.oracle/checkins/batch-2-r1.md:5160: trailing whitespace.
++   679	
.oracle/checkins/batch-2-r1.md:5162: trailing whitespace.
++   698	
.oracle/checkins/batch-2-r1.md:5164: trailing whitespace.
++   699	
.oracle/checkins/batch-2-r1.md:5166: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:5168: trailing whitespace.
++     4	
.oracle/checkins/batch-2-r1.md:5170: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:5172: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r1.md:5174: trailing whitespace.
++    68	
.oracle/checkins/batch-2-r1.md:5176: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:5178: trailing whitespace.
++    91	
.oracle/checkins/batch-2-r1.md:5180: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r1.md:5182: trailing whitespace.
++    95	
.oracle/checkins/batch-2-r1.md:5184: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r1.md:5186: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:5188: trailing whitespace.
++   111	
.oracle/checkins/batch-2-r1.md:5190: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r1.md:5192: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r1.md:5194: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r1.md:5196: trailing whitespace.
++   136	
.oracle/checkins/batch-2-r1.md:5198: trailing whitespace.
++   137	
.oracle/checkins/batch-2-r1.md:5200: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r1.md:5202: trailing whitespace.
++   150	
.oracle/checkins/batch-2-r1.md:5204: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r1.md:5206: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r1.md:5208: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:5210: trailing whitespace.
++    11	
.oracle/checkins/batch-2-r1.md:5212: trailing whitespace.
++    13	
.oracle/checkins/batch-2-r1.md:5214: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r1.md:5216: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r1.md:5218: trailing whitespace.
++    29	
.oracle/checkins/batch-2-r1.md:5220: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r1.md:5222: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r1.md:5224: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r1.md:5226: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r1.md:5228: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:5230: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r1.md:5232: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r1.md:5234: trailing whitespace.
++    74	
.oracle/checkins/batch-2-r1.md:5236: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r1.md:5238: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r1.md:5240: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r1.md:5242: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r1.md:5244: trailing whitespace.
++   100	
.oracle/checkins/batch-2-r1.md:5246: trailing whitespace.
++   101	
.oracle/checkins/batch-2-r1.md:5248: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r1.md:5250: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r1.md:5252: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r1.md:5254: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r1.md:5256: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r1.md:5258: trailing whitespace.
++   142	
.oracle/checkins/batch-2-r1.md:5260: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r1.md:5262: trailing whitespace.
++   155	
.oracle/checkins/batch-2-r1.md:5264: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r1.md:5266: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r1.md:5268: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:5270: trailing whitespace.
++   168	
.oracle/checkins/batch-2-r1.md:5272: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r1.md:5274: trailing whitespace.
++   178	
.oracle/checkins/batch-2-r1.md:5276: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r1.md:5278: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r1.md:5280: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r1.md:5282: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r1.md:5284: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r1.md:5286: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r1.md:5288: trailing whitespace.
++   211	
.oracle/checkins/batch-2-r1.md:5290: trailing whitespace.
++   212	
.oracle/checkins/batch-2-r1.md:5292: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r1.md:5294: trailing whitespace.
++   219	
.oracle/checkins/batch-2-r1.md:5296: trailing whitespace.
++   220	
.oracle/checkins/batch-2-r1.md:5298: trailing whitespace.
++   224	
.oracle/checkins/batch-2-r1.md:5300: trailing whitespace.
++   227	
.oracle/checkins/batch-2-r1.md:5302: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r1.md:5304: trailing whitespace.
++   232	
.oracle/checkins/batch-2-r1.md:5306: trailing whitespace.
++   239	
.oracle/checkins/batch-2-r1.md:5308: trailing whitespace.
++   249	
.oracle/checkins/batch-2-r1.md:5310: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:5312: trailing whitespace.
++   255	
.oracle/checkins/batch-2-r1.md:5314: trailing whitespace.
++   261	
.oracle/checkins/batch-2-r1.md:5316: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r1.md:5318: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:5320: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:5322: trailing whitespace.
++    10	
.oracle/checkins/batch-2-r1.md:5324: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r1.md:5326: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r1.md:5328: trailing whitespace.
++    35	
.oracle/checkins/batch-2-r1.md:5330: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r1.md:5332: trailing whitespace.
++    38	
.oracle/checkins/batch-2-r1.md:5334: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r1.md:5336: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r1.md:5338: trailing whitespace.
++    54	
.oracle/checkins/batch-2-r1.md:5340: trailing whitespace.
++    56	
.oracle/checkins/batch-2-r1.md:5342: trailing whitespace.
++    57	
.oracle/checkins/batch-2-r1.md:5344: trailing whitespace.
++    60	
.oracle/checkins/batch-2-r1.md:5346: trailing whitespace.
++    67	
.oracle/checkins/batch-2-r1.md:5348: trailing whitespace.
++    68	
.oracle/checkins/batch-2-r1.md:5350: trailing whitespace.
++    72	
.oracle/checkins/batch-2-r1.md:5352: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r1.md:5354: trailing whitespace.
++    80	
.oracle/checkins/batch-2-r1.md:5356: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r1.md:5358: trailing whitespace.
++    84	
.oracle/checkins/batch-2-r1.md:5360: trailing whitespace.
++    91	
.oracle/checkins/batch-2-r1.md:5362: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:5364: trailing whitespace.
++   107	
.oracle/checkins/batch-2-r1.md:5366: trailing whitespace.
++   108	
.oracle/checkins/batch-2-r1.md:5368: trailing whitespace.
++   116	
.oracle/checkins/batch-2-r1.md:5370: trailing whitespace.
++   117	
.oracle/checkins/batch-2-r1.md:5372: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r1.md:5374: trailing whitespace.
++   124	
.oracle/checkins/batch-2-r1.md:5376: trailing whitespace.
++   127	
.oracle/checkins/batch-2-r1.md:5378: trailing whitespace.
++   164	
.oracle/checkins/batch-2-r1.md:5380: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:5382: trailing whitespace.
++   168	
.oracle/checkins/batch-2-r1.md:5384: trailing whitespace.
++   173	
.oracle/checkins/batch-2-r1.md:5386: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r1.md:5388: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r1.md:5390: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r1.md:5392: trailing whitespace.
++   220	
.oracle/checkins/batch-2-r1.md:5394: trailing whitespace.
++   258	
.oracle/checkins/batch-2-r1.md:5396: trailing whitespace.
++   268	
.oracle/checkins/batch-2-r1.md:5398: trailing whitespace.
++   298	
.oracle/checkins/batch-2-r1.md:5400: trailing whitespace.
++   347	
.oracle/checkins/batch-2-r1.md:5402: trailing whitespace.
++   375	
.oracle/checkins/batch-2-r1.md:5404: trailing whitespace.
++   397	
.oracle/checkins/batch-2-r1.md:5406: trailing whitespace.
++   427	
.oracle/checkins/batch-2-r1.md:5408: trailing whitespace.
++   449	
.oracle/checkins/batch-2-r1.md:5410: trailing whitespace.
++   455	
.oracle/checkins/batch-2-r1.md:5412: trailing whitespace.
++   473	
.oracle/checkins/batch-2-r1.md:5414: trailing whitespace.
++   482	
.oracle/checkins/batch-2-r1.md:5416: trailing whitespace.
++   487	
.oracle/checkins/batch-2-r1.md:5418: trailing whitespace.
++   490	
.oracle/checkins/batch-2-r1.md:5420: trailing whitespace.
++   491	
.oracle/checkins/batch-2-r1.md:5422: trailing whitespace.
++   493	
.oracle/checkins/batch-2-r1.md:5424: trailing whitespace.
++   494	
.oracle/checkins/batch-2-r1.md:5426: trailing whitespace.
++   497	
.oracle/checkins/batch-2-r1.md:5428: trailing whitespace.
++   500	
.oracle/checkins/batch-2-r1.md:5430: trailing whitespace.
++   507	
.oracle/checkins/batch-2-r1.md:5432: trailing whitespace.
++   520	
.oracle/checkins/batch-2-r1.md:5434: trailing whitespace.
++   520	
.oracle/checkins/batch-2-r1.md:5436: trailing whitespace.
++   544	
.oracle/checkins/batch-2-r1.md:5438: trailing whitespace.
++   560	
.oracle/checkins/batch-2-r1.md:5440: trailing whitespace.
++   579	
.oracle/checkins/batch-2-r1.md:5442: trailing whitespace.
++   587	
.oracle/checkins/batch-2-r1.md:5444: trailing whitespace.
++   606	
.oracle/checkins/batch-2-r1.md:5446: trailing whitespace.
++   607	
.oracle/checkins/batch-2-r1.md:5448: trailing whitespace.
++   611	
.oracle/checkins/batch-2-r1.md:5450: trailing whitespace.
++   612	
.oracle/checkins/batch-2-r1.md:5452: trailing whitespace.
++   615	
.oracle/checkins/batch-2-r1.md:5454: trailing whitespace.
++   618	
.oracle/checkins/batch-2-r1.md:5456: trailing whitespace.
++   626	
.oracle/checkins/batch-2-r1.md:5458: trailing whitespace.
++   632	
.oracle/checkins/batch-2-r1.md:5460: trailing whitespace.
++   636	
.oracle/checkins/batch-2-r1.md:5462: trailing whitespace.
++   642	
.oracle/checkins/batch-2-r1.md:5464: trailing whitespace.
++   665	
.oracle/checkins/batch-2-r1.md:5466: trailing whitespace.
++   674	
.oracle/checkins/batch-2-r1.md:5468: trailing whitespace.
++   684	
.oracle/checkins/batch-2-r1.md:5470: trailing whitespace.
++   714	
.oracle/checkins/batch-2-r1.md:5472: trailing whitespace.
++   717	
.oracle/checkins/batch-2-r1.md:5474: trailing whitespace.
++   720	
.oracle/checkins/batch-2-r1.md:5476: trailing whitespace.
++   721	
.oracle/checkins/batch-2-r1.md:5478: trailing whitespace.
++   313	
.oracle/checkins/batch-2-r1.md:5480: trailing whitespace.
++   317	
.oracle/checkins/batch-2-r1.md:5482: trailing whitespace.
++   318	
.oracle/checkins/batch-2-r1.md:5484: trailing whitespace.
++   327	
.oracle/checkins/batch-2-r1.md:5486: trailing whitespace.
++   330	
.oracle/checkins/batch-2-r1.md:5488: trailing whitespace.
++   333	
.oracle/checkins/batch-2-r1.md:5490: trailing whitespace.
++   336	
.oracle/checkins/batch-2-r1.md:5492: trailing whitespace.
++   339	
.oracle/checkins/batch-2-r1.md:5494: trailing whitespace.
++   342	
.oracle/checkins/batch-2-r1.md:5496: trailing whitespace.
++   348	
.oracle/checkins/batch-2-r1.md:5498: trailing whitespace.
++   349	
.oracle/checkins/batch-2-r1.md:5500: trailing whitespace.
++   357	
.oracle/checkins/batch-2-r1.md:5502: trailing whitespace.
++   361	
.oracle/checkins/batch-2-r1.md:5504: trailing whitespace.
++   364	
.oracle/checkins/batch-2-r1.md:5506: trailing whitespace.
++   370	
.oracle/checkins/batch-2-r1.md:5508: trailing whitespace.
++   378	
.oracle/checkins/batch-2-r1.md:5510: trailing whitespace.
++   379	
.oracle/checkins/batch-2-r1.md:5512: trailing whitespace.
++   401	
.oracle/checkins/batch-2-r1.md:5514: trailing whitespace.
++   402	
.oracle/checkins/batch-2-r1.md:5516: trailing whitespace.
++   412	
.oracle/checkins/batch-2-r1.md:5518: trailing whitespace.
++   419	
.oracle/checkins/batch-2-r1.md:5520: trailing whitespace.
++   420	
.oracle/checkins/batch-2-r1.md:5522: trailing whitespace.
++   429	
.oracle/checkins/batch-2-r1.md:5524: trailing whitespace.
++   434	
.oracle/checkins/batch-2-r1.md:5526: trailing whitespace.
++   437	
.oracle/checkins/batch-2-r1.md:5528: trailing whitespace.
++   438	
.oracle/checkins/batch-2-r1.md:5530: trailing whitespace.
++   449	
.oracle/checkins/batch-2-r1.md:5532: trailing whitespace.
++   454	
.oracle/checkins/batch-2-r1.md:5534: trailing whitespace.
++   458	
.oracle/checkins/batch-2-r1.md:5536: trailing whitespace.
++   461	
.oracle/checkins/batch-2-r1.md:5538: trailing whitespace.
++   462	
.oracle/checkins/batch-2-r1.md:5540: trailing whitespace.
++   470	
.oracle/checkins/batch-2-r1.md:5542: trailing whitespace.
++   481	
.oracle/checkins/batch-2-r1.md:5544: trailing whitespace.
++   482	
.oracle/checkins/batch-2-r1.md:5546: trailing whitespace.
++   493	
.oracle/checkins/batch-2-r1.md:5548: trailing whitespace.
++   496	
.oracle/checkins/batch-2-r1.md:5550: trailing whitespace.
++   503	
.oracle/checkins/batch-2-r1.md:5552: trailing whitespace.
++   504	
.oracle/checkins/batch-2-r1.md:5554: trailing whitespace.
++   518	
.oracle/checkins/batch-2-r1.md:5556: trailing whitespace.
++   525	
.oracle/checkins/batch-2-r1.md:5558: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5560: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5562: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5564: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5566: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5568: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5570: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5572: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5574: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5576: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5578: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5580: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5582: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5584: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5586: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5588: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5590: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5592: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5594: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5596: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5598: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5600: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5602: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5604: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5606: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5608: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5610: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5612: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5614: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5616: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5618: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5620: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5622: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5624: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5626: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5628: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5630: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5632: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5634: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5636: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5638: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5640: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5642: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5644: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5646: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5648: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5650: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5652: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5654: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5656: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5658: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5660: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5662: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5664: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5666: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5668: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5670: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5672: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5674: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5676: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5678: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5680: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5682: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5684: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5686: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5688: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5690: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5692: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5694: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5696: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5698: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5700: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5702: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5704: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5706: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5708: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5710: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5712: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5714: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5716: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5718: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5720: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5722: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5724: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5726: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5728: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5730: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5732: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5734: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5736: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5738: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5740: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5742: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5744: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5746: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5748: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5750: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5752: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5754: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5756: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5758: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5760: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5762: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5764: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5766: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5768: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5770: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5772: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5774: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5776: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5778: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5780: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5782: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5784: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5786: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5788: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5790: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5792: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5794: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5796: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5798: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5800: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5802: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5804: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5806: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5808: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5810: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5812: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5814: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5816: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5818: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5820: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5822: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5824: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5826: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5828: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5830: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5832: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5834: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5836: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5838: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5840: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5842: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5844: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5846: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5848: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5850: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5852: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5854: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5856: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5858: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5860: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5862: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5864: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5866: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5868: trailing whitespace.
++ 
.oracle/checkins/batch-2-r1.md:5870: trailing whitespace.
++     3	
.oracle/checkins/batch-2-r1.md:5872: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r1.md:5874: trailing whitespace.
++    13	
.oracle/checkins/batch-2-r1.md:5876: trailing whitespace.
++    15	
.oracle/checkins/batch-2-r1.md:5878: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r1.md:5880: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r1.md:5882: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r1.md:5884: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:5886: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r1.md:5888: trailing whitespace.
++    57	
.oracle/checkins/batch-2-r1.md:5890: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r1.md:5892: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:5894: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r1.md:5896: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:5898: trailing whitespace.
++    15	
.oracle/checkins/batch-2-r1.md:5900: trailing whitespace.
++    16	
.oracle/checkins/batch-2-r1.md:5902: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r1.md:5904: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r1.md:5906: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r1.md:5908: trailing whitespace.
++    35	
.oracle/checkins/batch-2-r1.md:5910: trailing whitespace.
++    38	
.oracle/checkins/batch-2-r1.md:5912: trailing whitespace.
++    44	
.oracle/checkins/batch-2-r1.md:5914: trailing whitespace.
++    61	
.oracle/checkins/batch-2-r1.md:5916: trailing whitespace.
++    62	
.oracle/checkins/batch-2-r1.md:5918: trailing whitespace.
++    66	
.oracle/checkins/batch-2-r1.md:5920: trailing whitespace.
++    80	
.oracle/checkins/batch-2-r1.md:5922: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r1.md:5924: trailing whitespace.
++    83	
.oracle/checkins/batch-2-r1.md:5926: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:5928: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r1.md:5930: trailing whitespace.
++    94	
.oracle/checkins/batch-2-r1.md:5932: trailing whitespace.
++    95	
.oracle/checkins/batch-2-r1.md:5934: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:5936: trailing whitespace.
++   101	
.oracle/checkins/batch-2-r1.md:5938: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:5940: trailing whitespace.
++   107	
.oracle/checkins/batch-2-r1.md:5942: trailing whitespace.
++   110	
.oracle/checkins/batch-2-r1.md:5944: trailing whitespace.
++   113	
.oracle/checkins/batch-2-r1.md:5946: trailing whitespace.
++   130	
.oracle/checkins/batch-2-r1.md:5948: trailing whitespace.
++   131	
.oracle/checkins/batch-2-r1.md:5950: trailing whitespace.
++   134	
.oracle/checkins/batch-2-r1.md:5952: trailing whitespace.
++     3	
.oracle/checkins/batch-2-r1.md:5954: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r1.md:5956: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:5958: trailing whitespace.
++    14	
.oracle/checkins/batch-2-r1.md:5960: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r1.md:5962: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r1.md:5964: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r1.md:5966: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r1.md:5968: trailing whitespace.
++    49	
.oracle/checkins/batch-2-r1.md:5970: trailing whitespace.
++    53	
.oracle/checkins/batch-2-r1.md:5972: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r1.md:5974: trailing whitespace.
++    57	
.oracle/checkins/batch-2-r1.md:5976: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r1.md:5978: trailing whitespace.
++    62	
.oracle/checkins/batch-2-r1.md:5980: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r1.md:5982: trailing whitespace.
++    66	
.oracle/checkins/batch-2-r1.md:5984: trailing whitespace.
++    68	
.oracle/checkins/batch-2-r1.md:5986: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r1.md:5988: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r1.md:5990: trailing whitespace.
++    91	
.oracle/checkins/batch-2-r1.md:5992: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r1.md:5994: trailing whitespace.
++    99	
.oracle/checkins/batch-2-r1.md:5996: trailing whitespace.
++   100	
.oracle/checkins/batch-2-r1.md:5998: trailing whitespace.
++   104	
.oracle/checkins/batch-2-r1.md:6000: trailing whitespace.
++   105	
.oracle/checkins/batch-2-r1.md:6002: trailing whitespace.
++   117	
.oracle/checkins/batch-2-r1.md:6004: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r1.md:6006: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r1.md:6008: trailing whitespace.
++   144	
.oracle/checkins/batch-2-r1.md:6010: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:6012: trailing whitespace.
++   166	
.oracle/checkins/batch-2-r1.md:6014: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r1.md:6016: trailing whitespace.
++   190	
.oracle/checkins/batch-2-r1.md:6018: trailing whitespace.
++   191	
.oracle/checkins/batch-2-r1.md:6020: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r1.md:6022: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r1.md:6024: trailing whitespace.
++   199	
.oracle/checkins/batch-2-r1.md:6026: trailing whitespace.
++   200	
.oracle/checkins/batch-2-r1.md:6028: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r1.md:6030: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r1.md:6032: trailing whitespace.
++   207	
.oracle/checkins/batch-2-r1.md:6034: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r1.md:6036: trailing whitespace.
++   214	
.oracle/checkins/batch-2-r1.md:6038: trailing whitespace.
++   215	
.oracle/checkins/batch-2-r1.md:6040: trailing whitespace.
++   228	
.oracle/checkins/batch-2-r1.md:6042: trailing whitespace.
++   229	
.oracle/checkins/batch-2-r1.md:6044: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r1.md:6046: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r1.md:6048: trailing whitespace.
++   252	
.oracle/checkins/batch-2-r1.md:6050: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r1.md:6052: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r1.md:6054: trailing whitespace.
++   258	
.oracle/checkins/batch-2-r1.md:6056: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r1.md:6058: trailing whitespace.
++   263	
.oracle/checkins/batch-2-r1.md:6060: trailing whitespace.
++   286	
.oracle/checkins/batch-2-r1.md:6062: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r1.md:6064: trailing whitespace.
++   303	
.oracle/checkins/batch-2-r1.md:6066: trailing whitespace.
++   304	
.oracle/checkins/batch-2-r1.md:6068: trailing whitespace.
++   326	
.oracle/checkins/batch-2-r1.md:6070: trailing whitespace.
++   336	
.oracle/checkins/batch-2-r1.md:6072: trailing whitespace.
++   340	
.oracle/checkins/batch-2-r1.md:6074: trailing whitespace.
++   341	
.oracle/checkins/batch-2-r1.md:6076: trailing whitespace.
++   352	
.oracle/checkins/batch-2-r1.md:6078: trailing whitespace.
++   355	
.oracle/checkins/batch-2-r1.md:6080: trailing whitespace.
++   359	
.oracle/checkins/batch-2-r1.md:6082: trailing whitespace.
++   368	
.oracle/checkins/batch-2-r1.md:6084: trailing whitespace.
++   372	
.oracle/checkins/batch-2-r1.md:6086: trailing whitespace.
++   376	
.oracle/checkins/batch-2-r1.md:6088: trailing whitespace.
++   380	
.oracle/checkins/batch-2-r1.md:6090: trailing whitespace.
++   384	
.oracle/checkins/batch-2-r1.md:6092: trailing whitespace.
++   385	
.oracle/checkins/batch-2-r1.md:6094: trailing whitespace.
++   389	
.oracle/checkins/batch-2-r1.md:6096: trailing whitespace.
++   390	
.oracle/checkins/batch-2-r1.md:6098: trailing whitespace.
++   393	
.oracle/checkins/batch-2-r1.md:6100: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r1.md:6102: trailing whitespace.
++   407	
.oracle/checkins/batch-2-r1.md:6104: trailing whitespace.
++   408	
.oracle/checkins/batch-2-r1.md:6106: trailing whitespace.
++   427	
.oracle/checkins/batch-2-r1.md:6108: trailing whitespace.
++   428	
.oracle/checkins/batch-2-r1.md:6110: trailing whitespace.
++   443	
.oracle/checkins/batch-2-r1.md:6112: trailing whitespace.
++   444	
.oracle/checkins/batch-2-r1.md:6114: trailing whitespace.
++   458	
.oracle/checkins/batch-2-r1.md:6116: trailing whitespace.
++   467	
.oracle/checkins/batch-2-r1.md:6118: trailing whitespace.
++   470	
.oracle/checkins/batch-2-r1.md:6120: trailing whitespace.
++   522	
.oracle/checkins/batch-2-r1.md:6122: trailing whitespace.
++   523	
.oracle/checkins/batch-2-r1.md:6124: trailing whitespace.
++   533	
.oracle/checkins/batch-2-r1.md:6126: trailing whitespace.
++   546	
.oracle/checkins/batch-2-r1.md:6128: trailing whitespace.
++   558	
.oracle/checkins/batch-2-r1.md:6130: trailing whitespace.
++   559	
.oracle/checkins/batch-2-r1.md:6132: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r1.md:6134: trailing whitespace.
++   121	
.oracle/checkins/batch-2-r1.md:6136: trailing whitespace.
++   131	
.oracle/checkins/batch-2-r1.md:6138: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r1.md:6140: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r1.md:6142: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r1.md:6144: trailing whitespace.
++   164	
.oracle/checkins/batch-2-r1.md:6146: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r1.md:6148: trailing whitespace.
++   182	
.oracle/checkins/batch-2-r1.md:6150: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r1.md:6152: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r1.md:6154: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r1.md:6156: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r1.md:6158: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r1.md:6160: trailing whitespace.
++   221	
.oracle/checkins/batch-2-r1.md:6162: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r1.md:6164: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r1.md:6166: trailing whitespace.
++   249	
.oracle/checkins/batch-2-r1.md:6168: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:6170: trailing whitespace.
++   256	
.oracle/checkins/batch-2-r1.md:6172: trailing whitespace.
++   266	
.oracle/checkins/batch-2-r1.md:6174: trailing whitespace.
++   267	
.oracle/checkins/batch-2-r1.md:6176: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r1.md:6178: trailing whitespace.
++   272	
.oracle/checkins/batch-2-r1.md:6180: trailing whitespace.
++   276	
.oracle/checkins/batch-2-r1.md:6182: trailing whitespace.
++   279	
.oracle/checkins/batch-2-r1.md:6184: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r1.md:6186: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r1.md:6188: trailing whitespace.
++   292	
.oracle/checkins/batch-2-r1.md:6190: trailing whitespace.
++   301	
.oracle/checkins/batch-2-r1.md:6192: trailing whitespace.
++   302	
.oracle/checkins/batch-2-r1.md:6194: trailing whitespace.
++   311	
.oracle/checkins/batch-2-r1.md:6196: trailing whitespace.
++   314	
.oracle/checkins/batch-2-r1.md:6198: trailing whitespace.
++   315	
.oracle/checkins/batch-2-r1.md:6200: trailing whitespace.
++   319	
.oracle/checkins/batch-2-r1.md:6202: trailing whitespace.
++   320	
.oracle/checkins/batch-2-r1.md:6204: trailing whitespace.
++   326	
.oracle/checkins/batch-2-r1.md:6206: trailing whitespace.
++     3	
.oracle/checkins/batch-2-r1.md:6208: trailing whitespace.
++     4	
.oracle/checkins/batch-2-r1.md:6210: trailing whitespace.
++    10	
.oracle/checkins/batch-2-r1.md:6212: trailing whitespace.
++    12	
.oracle/checkins/batch-2-r1.md:6214: trailing whitespace.
++    14	
.oracle/checkins/batch-2-r1.md:6216: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r1.md:6218: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r1.md:6220: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r1.md:6222: trailing whitespace.
++    45	
.oracle/checkins/batch-2-r1.md:6224: trailing whitespace.
++    46	
.oracle/checkins/batch-2-r1.md:6226: trailing whitespace.
++    49	
.oracle/checkins/batch-2-r1.md:6228: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r1.md:6230: trailing whitespace.
++    53	
.oracle/checkins/batch-2-r1.md:6232: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r1.md:6234: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r1.md:6236: trailing whitespace.
++    67	
.oracle/checkins/batch-2-r1.md:6238: trailing whitespace.
++    72	
.oracle/checkins/batch-2-r1.md:6240: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r1.md:6242: trailing whitespace.
++    97	
.oracle/checkins/batch-2-r1.md:6244: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:6246: trailing whitespace.
++   100	
.oracle/checkins/batch-2-r1.md:6248: trailing whitespace.
++   101	
.oracle/checkins/batch-2-r1.md:6250: trailing whitespace.
++   105	
.oracle/checkins/batch-2-r1.md:6252: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:6254: trailing whitespace.
++   109	
.oracle/checkins/batch-2-r1.md:6256: trailing whitespace.
++   110	
.oracle/checkins/batch-2-r1.md:6258: trailing whitespace.
++   117	
.oracle/checkins/batch-2-r1.md:6260: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r1.md:6262: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r1.md:6264: trailing whitespace.
++   136	
.oracle/checkins/batch-2-r1.md:6266: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r1.md:6268: trailing whitespace.
++   146	
.oracle/checkins/batch-2-r1.md:6270: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r1.md:6272: trailing whitespace.
++   150	
.oracle/checkins/batch-2-r1.md:6274: trailing whitespace.
++   156	
.oracle/checkins/batch-2-r1.md:6276: trailing whitespace.
++   157	
.oracle/checkins/batch-2-r1.md:6278: trailing whitespace.
++   160	
.oracle/checkins/batch-2-r1.md:6280: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r1.md:6282: trailing whitespace.
++   164	
.oracle/checkins/batch-2-r1.md:6284: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:6286: trailing whitespace.
++   171	
.oracle/checkins/batch-2-r1.md:6288: trailing whitespace.
++   172	
.oracle/checkins/batch-2-r1.md:6290: trailing whitespace.
++   182	
.oracle/checkins/batch-2-r1.md:6292: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r1.md:6294: trailing whitespace.
++   186	
.oracle/checkins/batch-2-r1.md:6296: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r1.md:6298: trailing whitespace.
++   190	
.oracle/checkins/batch-2-r1.md:6300: trailing whitespace.
++   191	
.oracle/checkins/batch-2-r1.md:6302: trailing whitespace.
++   201	
.oracle/checkins/batch-2-r1.md:6304: trailing whitespace.
++   202	
.oracle/checkins/batch-2-r1.md:6306: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r1.md:6308: trailing whitespace.
++   209	
.oracle/checkins/batch-2-r1.md:6310: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r1.md:6312: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r1.md:6314: trailing whitespace.
++   222	
.oracle/checkins/batch-2-r1.md:6316: trailing whitespace.
++   223	
.oracle/checkins/batch-2-r1.md:6318: trailing whitespace.
++   229	
.oracle/checkins/batch-2-r1.md:6320: trailing whitespace.
++   230	
.oracle/checkins/batch-2-r1.md:6322: trailing whitespace.
++   234	
.oracle/checkins/batch-2-r1.md:6324: trailing whitespace.
++   235	
.oracle/checkins/batch-2-r1.md:6326: trailing whitespace.
++   249	
.oracle/checkins/batch-2-r1.md:6328: trailing whitespace.
++   250	
.oracle/checkins/batch-2-r1.md:6330: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r1.md:6332: trailing whitespace.
++   266	
.oracle/checkins/batch-2-r1.md:6334: trailing whitespace.
++   283	
.oracle/checkins/batch-2-r1.md:6336: trailing whitespace.
++   284	
.oracle/checkins/batch-2-r1.md:6338: trailing whitespace.
++   304	
.oracle/checkins/batch-2-r1.md:6340: trailing whitespace.
++   308	
.oracle/checkins/batch-2-r1.md:6342: trailing whitespace.
++   344	
.oracle/checkins/batch-2-r1.md:6344: trailing whitespace.
++   345	
.oracle/checkins/batch-2-r1.md:6346: trailing whitespace.
++   359	
.oracle/checkins/batch-2-r1.md:6348: trailing whitespace.
++   360	
.oracle/checkins/batch-2-r1.md:6350: trailing whitespace.
++   408	
.oracle/checkins/batch-2-r1.md:6352: trailing whitespace.
++   409	
.oracle/checkins/batch-2-r1.md:6354: trailing whitespace.
++   430	
.oracle/checkins/batch-2-r1.md:6356: trailing whitespace.
++   431	
.oracle/checkins/batch-2-r1.md:6358: trailing whitespace.
++   444	
.oracle/checkins/batch-2-r1.md:6360: trailing whitespace.
++   445	
.oracle/checkins/batch-2-r1.md:6362: trailing whitespace.
++   455	
.oracle/checkins/batch-2-r1.md:6364: trailing whitespace.
++   456	
.oracle/checkins/batch-2-r1.md:6366: trailing whitespace.
++   486	
.oracle/checkins/batch-2-r1.md:6368: trailing whitespace.
++   487	
.oracle/checkins/batch-2-r1.md:6370: trailing whitespace.
++   503	
.oracle/checkins/batch-2-r1.md:6372: trailing whitespace.
++   504	
.oracle/checkins/batch-2-r1.md:6374: trailing whitespace.
++     3	
.oracle/checkins/batch-2-r1.md:6376: trailing whitespace.
++    13	
.oracle/checkins/batch-2-r1.md:6378: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r1.md:6380: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r1.md:6382: trailing whitespace.
++    38	
.oracle/checkins/batch-2-r1.md:6384: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r1.md:6386: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r1.md:6388: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r1.md:6390: trailing whitespace.
++    51	
.oracle/checkins/batch-2-r1.md:6392: trailing whitespace.
++    54	
.oracle/checkins/batch-2-r1.md:6394: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r1.md:6396: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r1.md:6398: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r1.md:6400: trailing whitespace.
++    68	
.oracle/checkins/batch-2-r1.md:6402: trailing whitespace.
++    72	
.oracle/checkins/batch-2-r1.md:6404: trailing whitespace.
++    77	
.oracle/checkins/batch-2-r1.md:6406: trailing whitespace.
++    87	
.oracle/checkins/batch-2-r1.md:6408: trailing whitespace.
++   102	
.oracle/checkins/batch-2-r1.md:6410: trailing whitespace.
++   103	
.oracle/checkins/batch-2-r1.md:6412: trailing whitespace.
++   105	
.oracle/checkins/batch-2-r1.md:6414: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:6416: trailing whitespace.
++   110	
.oracle/checkins/batch-2-r1.md:6418: trailing whitespace.
++   111	
.oracle/checkins/batch-2-r1.md:6420: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r1.md:6422: trailing whitespace.
++   115	
.oracle/checkins/batch-2-r1.md:6424: trailing whitespace.
++   122	
.oracle/checkins/batch-2-r1.md:6426: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r1.md:6428: trailing whitespace.
++   128	
.oracle/checkins/batch-2-r1.md:6430: trailing whitespace.
++   141	
.oracle/checkins/batch-2-r1.md:6432: trailing whitespace.
++   148	
.oracle/checkins/batch-2-r1.md:6434: trailing whitespace.
++   151	
.oracle/checkins/batch-2-r1.md:6436: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r1.md:6438: trailing whitespace.
++   155	
.oracle/checkins/batch-2-r1.md:6440: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r1.md:6442: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r1.md:6444: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:6446: trailing whitespace.
++   166	
.oracle/checkins/batch-2-r1.md:6448: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r1.md:6450: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r1.md:6452: trailing whitespace.
++   176	
.oracle/checkins/batch-2-r1.md:6454: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r1.md:6456: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r1.md:6458: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r1.md:6460: trailing whitespace.
++   191	
.oracle/checkins/batch-2-r1.md:6462: trailing whitespace.
++   192	
.oracle/checkins/batch-2-r1.md:6464: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r1.md:6466: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r1.md:6468: trailing whitespace.
++   206	
.oracle/checkins/batch-2-r1.md:6470: trailing whitespace.
++   207	
.oracle/checkins/batch-2-r1.md:6472: trailing whitespace.
++   213	
.oracle/checkins/batch-2-r1.md:6474: trailing whitespace.
++   214	
.oracle/checkins/batch-2-r1.md:6476: trailing whitespace.
++   221	
.oracle/checkins/batch-2-r1.md:6478: trailing whitespace.
++   222	
.oracle/checkins/batch-2-r1.md:6480: trailing whitespace.
++   227	
.oracle/checkins/batch-2-r1.md:6482: trailing whitespace.
++   228	
.oracle/checkins/batch-2-r1.md:6484: trailing whitespace.
++   234	
.oracle/checkins/batch-2-r1.md:6486: trailing whitespace.
++   235	
.oracle/checkins/batch-2-r1.md:6488: trailing whitespace.
++   239	
.oracle/checkins/batch-2-r1.md:6490: trailing whitespace.
++   240	
.oracle/checkins/batch-2-r1.md:6492: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:6494: trailing whitespace.
++   255	
.oracle/checkins/batch-2-r1.md:6496: trailing whitespace.
++   267	
.oracle/checkins/batch-2-r1.md:6498: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r1.md:6500: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r1.md:6502: trailing whitespace.
++   289	
.oracle/checkins/batch-2-r1.md:6504: trailing whitespace.
++   309	
.oracle/checkins/batch-2-r1.md:6506: trailing whitespace.
++   313	
.oracle/checkins/batch-2-r1.md:6508: trailing whitespace.
++   349	
.oracle/checkins/batch-2-r1.md:6510: trailing whitespace.
++   350	
.oracle/checkins/batch-2-r1.md:6512: trailing whitespace.
++   364	
.oracle/checkins/batch-2-r1.md:6514: trailing whitespace.
++   365	
.oracle/checkins/batch-2-r1.md:6516: trailing whitespace.
++   413	
.oracle/checkins/batch-2-r1.md:6518: trailing whitespace.
++   414	
.oracle/checkins/batch-2-r1.md:6520: trailing whitespace.
++   435	
.oracle/checkins/batch-2-r1.md:6522: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r1.md:6524: trailing whitespace.
++   449	
.oracle/checkins/batch-2-r1.md:6526: trailing whitespace.
++   450	
.oracle/checkins/batch-2-r1.md:6528: trailing whitespace.
++   460	
.oracle/checkins/batch-2-r1.md:6530: trailing whitespace.
++   461	
.oracle/checkins/batch-2-r1.md:6532: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r1.md:6534: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r1.md:6536: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r1.md:6538: trailing whitespace.
++    27	
.oracle/checkins/batch-2-r1.md:6540: trailing whitespace.
++    35	
.oracle/checkins/batch-2-r1.md:6542: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r1.md:6544: trailing whitespace.
++    51	
.oracle/checkins/batch-2-r1.md:6546: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r1.md:6548: trailing whitespace.
++    78	
.oracle/checkins/batch-2-r1.md:6550: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:6552: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:6554: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r1.md:6556: trailing whitespace.
++   122	
.oracle/checkins/batch-2-r1.md:6558: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r1.md:6560: trailing whitespace.
++   141	
.oracle/checkins/batch-2-r1.md:6562: trailing whitespace.
++   147	
.oracle/checkins/batch-2-r1.md:6564: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r1.md:6566: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r1.md:6568: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r1.md:6570: trailing whitespace.
++   190	
.oracle/checkins/batch-2-r1.md:6572: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r1.md:6574: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r1.md:6576: trailing whitespace.
++   225	
.oracle/checkins/batch-2-r1.md:6578: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r1.md:6580: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:6582: trailing whitespace.
++   263	
.oracle/checkins/batch-2-r1.md:6584: trailing whitespace.
++   273	
.oracle/checkins/batch-2-r1.md:6586: trailing whitespace.
++   274	
.oracle/checkins/batch-2-r1.md:6588: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:6590: trailing whitespace.
++     4	
.oracle/checkins/batch-2-r1.md:6592: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r1.md:6594: trailing whitespace.
++    11	
.oracle/checkins/batch-2-r1.md:6596: trailing whitespace.
++    29	
.oracle/checkins/batch-2-r1.md:6598: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r1.md:6600: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r1.md:6602: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r1.md:6604: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r1.md:6606: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r1.md:6608: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r1.md:6610: trailing whitespace.
++    54	
.oracle/checkins/batch-2-r1.md:6612: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r1.md:6614: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r1.md:6616: trailing whitespace.
++    83	
.oracle/checkins/batch-2-r1.md:6618: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:6620: trailing whitespace.
++    93	
.oracle/checkins/batch-2-r1.md:6622: trailing whitespace.
++    94	
.oracle/checkins/batch-2-r1.md:6624: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r1.md:6626: trailing whitespace.
++   107	
.oracle/checkins/batch-2-r1.md:6628: trailing whitespace.
++   199	
.oracle/checkins/batch-2-r1.md:6630: trailing whitespace.
++   200	
.oracle/checkins/batch-2-r1.md:6632: trailing whitespace.
++   276	
.oracle/checkins/batch-2-r1.md:6634: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r1.md:6636: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r1.md:6638: trailing whitespace.
++   289	
.oracle/checkins/batch-2-r1.md:6640: trailing whitespace.
++   311	
.oracle/checkins/batch-2-r1.md:6642: trailing whitespace.
++   312	
.oracle/checkins/batch-2-r1.md:6644: trailing whitespace.
++   959	
.oracle/checkins/batch-2-r1.md:6646: trailing whitespace.
++   960	
.oracle/checkins/batch-2-r1.md:6648: trailing whitespace.
++   963	
.oracle/checkins/batch-2-r1.md:6650: trailing whitespace.
++   964	
.oracle/checkins/batch-2-r1.md:6652: trailing whitespace.
++   970	
.oracle/checkins/batch-2-r1.md:6654: trailing whitespace.
++   975	
.oracle/checkins/batch-2-r1.md:6656: trailing whitespace.
++   989	
.oracle/checkins/batch-2-r1.md:6658: trailing whitespace.
++   990	
.oracle/checkins/batch-2-r1.md:6660: trailing whitespace.
++  1001	
.oracle/checkins/batch-2-r1.md:6662: trailing whitespace.
++  1002	
.oracle/checkins/batch-2-r1.md:6664: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r1.md:6666: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r1.md:6668: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r1.md:6670: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:6672: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r1.md:6674: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r1.md:6676: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:6678: trailing whitespace.
++    99	
.oracle/checkins/batch-2-r1.md:6680: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r1.md:6682: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r1.md:6684: trailing whitespace.
++   133	
.oracle/checkins/batch-2-r1.md:6686: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r1.md:6688: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r1.md:6690: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r1.md:6692: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r1.md:6694: trailing whitespace.
++   179	
.oracle/checkins/batch-2-r1.md:6696: trailing whitespace.
++   180	
.oracle/checkins/batch-2-r1.md:6698: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r1.md:6700: trailing whitespace.
++   197	
.oracle/checkins/batch-2-r1.md:6702: trailing whitespace.
++   218	
.oracle/checkins/batch-2-r1.md:6704: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r1.md:6706: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r1.md:6708: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:6710: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r1.md:6712: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r1.md:6714: trailing whitespace.
++    18	
.oracle/checkins/batch-2-r1.md:6716: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r1.md:6718: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r1.md:6720: trailing whitespace.
++    28	
.oracle/checkins/batch-2-r1.md:6722: trailing whitespace.
++    31	
.oracle/checkins/batch-2-r1.md:6724: trailing whitespace.
++    32	
.oracle/checkins/batch-2-r1.md:6726: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r1.md:6728: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r1.md:6730: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:6732: trailing whitespace.
++    44	
.oracle/checkins/batch-2-r1.md:6734: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r1.md:6736: trailing whitespace.
++    66	
.oracle/checkins/batch-2-r1.md:6738: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r1.md:6740: trailing whitespace.
++    72	
.oracle/checkins/batch-2-r1.md:6742: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r1.md:6744: trailing whitespace.
++    76	
.oracle/checkins/batch-2-r1.md:6746: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r1.md:6748: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r1.md:6750: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r1.md:6752: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:6754: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r1.md:6756: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r1.md:6758: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r1.md:6760: trailing whitespace.
++    99	
.oracle/checkins/batch-2-r1.md:6762: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r1.md:6764: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r1.md:6766: trailing whitespace.
++   133	
.oracle/checkins/batch-2-r1.md:6768: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r1.md:6770: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r1.md:6772: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r1.md:6774: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r1.md:6776: trailing whitespace.
++   179	
.oracle/checkins/batch-2-r1.md:6778: trailing whitespace.
++   180	
.oracle/checkins/batch-2-r1.md:6780: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r1.md:6782: trailing whitespace.
++   197	
.oracle/checkins/batch-2-r1.md:6784: trailing whitespace.
++   218	
.oracle/checkins/batch-2-r1.md:6786: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r1.md:6788: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r1.md:6790: trailing whitespace.
++   255	
.oracle/checkins/batch-2-r1.md:6792: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r1.md:6794: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r1.md:6796: trailing whitespace.
++   270	
.oracle/checkins/batch-2-r1.md:6798: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r1.md:6800: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r1.md:6802: trailing whitespace.
++   296	
.oracle/checkins/batch-2-r1.md:6804: trailing whitespace.
++   306	
.oracle/checkins/batch-2-r1.md:6806: trailing whitespace.
++   307	
.oracle/checkins/batch-2-r1.md:6808: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r1.md:6810: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r1.md:6812: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r1.md:6814: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r1.md:6816: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r1.md:6818: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r1.md:6820: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r1.md:6822: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r1.md:6824: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r1.md:6826: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r1.md:6828: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r1.md:6830: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r1.md:6832: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r1.md:6834: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r1.md:6836: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r1.md:6838: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r1.md:6840: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r1.md:6842: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r1.md:6844: trailing whitespace.
++   108	
.oracle/checkins/batch-2-r1.md:6846: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r1.md:6848: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r1.md:6850: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r1.md:6852: trailing whitespace.
++   130	
.oracle/checkins/batch-2-r1.md:6854: trailing whitespace.
++   135	
.oracle/checkins/batch-2-r1.md:6856: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r1.md:6858: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r1.md:6860: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r1.md:6862: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r1.md:6864: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r1.md:6866: trailing whitespace.
++   205	
.oracle/checkins/batch-2-r1.md:6868: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r1.md:6870: trailing whitespace.
++   218	
.oracle/checkins/batch-2-r1.md:6872: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r1.md:6874: trailing whitespace.
++   247	
.oracle/checkins/batch-2-r1.md:6876: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r1.md:6878: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r1.md:6880: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r1.md:6882: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r1.md:6884: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r1.md:6886: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r1.md:6888: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r1.md:6890: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r1.md:6892: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r1.md:6894: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r1.md:6896: trailing whitespace.
++   142	
.oracle/checkins/batch-2-r1.md:6898: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r1.md:6900: trailing whitespace.
++   155	
.oracle/checkins/batch-2-r1.md:6902: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r1.md:6904: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r1.md:6906: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r1.md:6908: trailing whitespace.
++   168	
.oracle/checkins/batch-2-r1.md:6910: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r1.md:6912: trailing whitespace.
++   178	
.oracle/checkins/batch-2-r1.md:6914: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r1.md:6916: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r1.md:6918: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r1.md:6920: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r1.md:6922: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r1.md:6924: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r1.md:6926: trailing whitespace.
++   211	
.oracle/checkins/batch-2-r1.md:6928: trailing whitespace.
++   212	
.oracle/checkins/batch-2-r1.md:6930: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r1.md:6932: trailing whitespace.
++   219	
.oracle/checkins/batch-2-r1.md:6934: trailing whitespace.
++   220	
.oracle/checkins/batch-2-r1.md:6936: trailing whitespace.
++   224	
.oracle/checkins/batch-2-r1.md:6938: trailing whitespace.
++   227	
.oracle/checkins/batch-2-r1.md:6940: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r1.md:6942: trailing whitespace.
++   232	
.oracle/checkins/batch-2-r1.md:6944: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r1.md:6946: trailing whitespace.
++   437	
.oracle/checkins/batch-2-r1.md:6948: trailing whitespace.
++   450	
.oracle/checkins/batch-2-r1.md:6950: trailing whitespace.
++   451	
.oracle/checkins/batch-2-r1.md:6952: trailing whitespace.
++   456	
.oracle/checkins/batch-2-r1.md:6954: trailing whitespace.
++   464	
.oracle/checkins/batch-2-r1.md:6956: trailing whitespace.
++   467	
.oracle/checkins/batch-2-r1.md:6958: trailing whitespace.
++   471	
.oracle/checkins/batch-2-r1.md:6960: trailing whitespace.
++   484	
.oracle/checkins/batch-2-r1.md:6962: trailing whitespace.
++   487	
.oracle/checkins/batch-2-r1.md:6964: trailing whitespace.
++   490	
.oracle/checkins/batch-2-r1.md:6966: trailing whitespace.
++   491	
.oracle/checkins/batch-2-r1.md:6968: trailing whitespace.
++   496	
.oracle/checkins/batch-2-r1.md:6970: trailing whitespace.
++   506	
.oracle/checkins/batch-2-r1.md:6972: trailing whitespace.
++   507	
.oracle/checkins/batch-2-r1.md:6974: trailing whitespace.
++   514	
.oracle/checkins/batch-2-r1.md:6976: trailing whitespace.
++   515	
.oracle/checkins/batch-2-r1.md:7370: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7379: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7380: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7397: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7398: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7416: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7417: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7440: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7441: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7486: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7487: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7496: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7497: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7517: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7518: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7540: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7543: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7546: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7547: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7550: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7555: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7556: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7559: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7560: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7563: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7564: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7572: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7573: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7599: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7600: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7607: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7612: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7647: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7648: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7655: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7657: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7658: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7674: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7675: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7705: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7731: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7732: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7742: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7749: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7752: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7766: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7773: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7788: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7796: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7806: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7807: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7821: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7832: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7863: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7907: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7911: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7918: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7930: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7931: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7938: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7939: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7955: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7956: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7988: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7997: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:7998: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8005: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8006: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8023: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8024: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8041: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8042: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8055: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8056: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8061: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8076: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8079: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8083: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8096: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8099: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8102: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8103: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8108: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8118: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8119: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8126: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8127: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8138: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8139: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8158: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8159: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8170: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8171: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8225: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8226: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8251: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8259: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8289: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8290: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8300: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8301: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8322: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8323: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8333: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8339: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8352: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8353: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8357: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8358: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8364: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8374: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8391: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8401: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8414: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8419: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8424: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8426: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8435: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8436: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8439: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8449: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8452: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8453: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8465: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8471: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8472: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8475: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8478: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8487: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8488: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8491: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8498: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8504: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8513: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8514: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8520: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8524: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8525: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8529: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8532: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8533: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8537: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8540: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8544: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8545: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8552: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8562: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8567: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8568: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8574: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8588: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8601: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8604: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8606: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8612: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8618: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8620: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8628: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8631: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8648: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8652: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8654: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8656: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8657: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8661: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8662: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8665: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8667: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8672: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8681: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8690: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8691: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8698: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8699: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8703: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8704: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8716: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8717: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8743: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8744: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8765: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8766: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8769: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8790: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8791: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8795: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8796: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8799: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8800: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8803: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8804: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8807: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8808: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8814: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8815: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8823: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8875: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8876: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8886: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8899: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8921: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8922: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:8941: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r1.md:8945: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r1.md:8947: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r1.md:8961: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r1.md:8963: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r1.md:8976: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r1.md:8977: trailing whitespace.
+    38	
.oracle/checkins/batch-2-r1.md:8980: trailing whitespace.
+    41	
.oracle/checkins/batch-2-r1.md:9008: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r1.md:9009: trailing whitespace.
+    70	
.oracle/checkins/batch-2-r1.md:9012: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r1.md:9018: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r1.md:9037: trailing whitespace.
+    98	
.oracle/checkins/batch-2-r1.md:9052: trailing whitespace.
+   113	
.oracle/checkins/batch-2-r1.md:9059: trailing whitespace.
+   120	
.oracle/checkins/batch-2-r1.md:9065: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r1.md:9083: trailing whitespace.
+   144	
.oracle/checkins/batch-2-r1.md:9099: trailing whitespace.
+   160	
.oracle/checkins/batch-2-r1.md:9110: trailing whitespace.
+   171	
.oracle/checkins/batch-2-r1.md:9141: trailing whitespace.
+   202	
.oracle/checkins/batch-2-r1.md:9185: trailing whitespace.
+   246	
.oracle/checkins/batch-2-r1.md:9189: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r1.md:9196: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r1.md:9207: trailing whitespace.
+   427	
.oracle/checkins/batch-2-r1.md:9208: trailing whitespace.
+   428	
.oracle/checkins/batch-2-r1.md:9225: trailing whitespace.
+   445	
.oracle/checkins/batch-2-r1.md:9226: trailing whitespace.
+   446	
.oracle/checkins/batch-2-r1.md:9239: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r1.md:9240: trailing whitespace.
+   460	
.oracle/checkins/batch-2-r1.md:9245: trailing whitespace.
+   465	
.oracle/checkins/batch-2-r1.md:9259: trailing whitespace.
+   479	
.oracle/checkins/batch-2-r1.md:9262: trailing whitespace.
+   482	
.oracle/checkins/batch-2-r1.md:9266: trailing whitespace.
+   486	
.oracle/checkins/batch-2-r1.md:9279: trailing whitespace.
+   499	
.oracle/checkins/batch-2-r1.md:9282: trailing whitespace.
+   502	
.oracle/checkins/batch-2-r1.md:9285: trailing whitespace.
+   505	
.oracle/checkins/batch-2-r1.md:9286: trailing whitespace.
+   506	
.oracle/checkins/batch-2-r1.md:9291: trailing whitespace.
+   511	
.oracle/checkins/batch-2-r1.md:9301: trailing whitespace.
+   521	
.oracle/checkins/batch-2-r1.md:9302: trailing whitespace.
+   522	
.oracle/checkins/batch-2-r1.md:9309: trailing whitespace.
+   529	
.oracle/checkins/batch-2-r1.md:9310: trailing whitespace.
+   530	
.oracle/checkins/batch-2-r1.md:9321: trailing whitespace.
+   541	
.oracle/checkins/batch-2-r1.md:9322: trailing whitespace.
+   542	
.oracle/checkins/batch-2-r1.md:9341: trailing whitespace.
+   561	
.oracle/checkins/batch-2-r1.md:9342: trailing whitespace.
+   562	
.oracle/checkins/batch-2-r1.md:9353: trailing whitespace.
+   573	
.oracle/checkins/batch-2-r1.md:9354: trailing whitespace.
+   574	
.oracle/checkins/batch-2-r1.md:9407: trailing whitespace.
+   627	
.oracle/checkins/batch-2-r1.md:9408: trailing whitespace.
+   628	
.oracle/checkins/batch-2-r1.md:9451: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9455: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9462: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9469: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9470: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9475: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9490: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9493: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9497: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9510: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9511: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9547: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9556: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9557: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9563: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9567: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9568: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9572: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9575: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9576: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9580: trailing whitespace.
+ 
.oracle/checkins/batch-2-r1.md:9586: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r1.md:9591: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r1.md:9593: trailing whitespace.
+     9	
.oracle/checkins/batch-2-r1.md:9602: trailing whitespace.
+    18	
.oracle/checkins/batch-2-r1.md:9605: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r1.md:9607: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r1.md:9612: trailing whitespace.
+    28	
.oracle/checkins/batch-2-r1.md:9615: trailing whitespace.
+    31	
.oracle/checkins/batch-2-r1.md:9616: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r1.md:9620: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r1.md:9621: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r1.md:9624: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r1.md:9628: trailing whitespace.
+    44	
.oracle/checkins/batch-2-r1.md:9643: trailing whitespace.
+    59	
.oracle/checkins/batch-2-r1.md:9650: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r1.md:9653: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r1.md:9656: trailing whitespace.
+    72	
.oracle/checkins/batch-2-r1.md:9657: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r1.md:9660: trailing whitespace.
+    76	
.oracle/checkins/batch-2-r1.md:9665: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r1.md:9666: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r1.md:9669: trailing whitespace.
+    85	
.oracle/checkins/batch-2-r1.md:9670: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r1.md:9673: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r1.md:9674: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r1.md:9682: trailing whitespace.
+    98	
.oracle/checkins/batch-2-r1.md:9683: trailing whitespace.
+    99	
.oracle/checkins/batch-2-r1.md:9709: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r1.md:9710: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r1.md:9717: trailing whitespace.
+   133	
.oracle/checkins/batch-2-r1.md:9722: trailing whitespace.
+   138	
.oracle/checkins/batch-2-r1.md:9757: trailing whitespace.
+   173	
.oracle/checkins/batch-2-r1.md:9758: trailing whitespace.
+   174	
.oracle/checkins/batch-2-r1.md:9765: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r1.md:9767: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r1.md:9768: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r1.md:9784: trailing whitespace.
+   200	
.oracle/checkins/batch-2-r1.md:9785: trailing whitespace.
+   201	
.oracle/checkins/batch-2-r1.md:9815: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r1.md:9841: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r1.md:9842: trailing whitespace.
+   258	
.oracle/checkins/batch-2-r1.md:9852: trailing whitespace.
+   268	
.oracle/checkins/batch-2-r1.md:9859: trailing whitespace.
+   275	
.oracle/checkins/batch-2-r1.md:9862: trailing whitespace.
+   278	
.oracle/checkins/batch-2-r1.md:9876: trailing whitespace.
+   292	
.oracle/checkins/batch-2-r1.md:9883: trailing whitespace.
+   299	
.oracle/checkins/batch-2-r1.md:9894: trailing whitespace.
+   310	
.oracle/checkins/batch-2-r1.md:9902: trailing whitespace.
+   318	
.oracle/checkins/batch-2-r1.md:9912: trailing whitespace.
+   328	
.oracle/checkins/batch-2-r1.md:9913: trailing whitespace.
+   329	
.oracle/checkins/batch-2-r1.md:10000: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r1.md:10005: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r1.md:10007: trailing whitespace.
+     9	
.oracle/checkins/batch-2-r1.md:10017: trailing whitespace.
+    19	
.oracle/checkins/batch-2-r1.md:10018: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r1.md:10021: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r1.md:10022: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r1.md:10037: trailing whitespace.
+    39	
.oracle/checkins/batch-2-r1.md:10038: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r1.md:10045: trailing whitespace.
+    47	
.oracle/checkins/batch-2-r1.md:10053: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r1.md:10062: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r1.md:10063: trailing whitespace.
+    65	
.oracle/checkins/batch-2-r1.md:10073: trailing whitespace.
+    75	
.oracle/checkins/batch-2-r1.md:10079: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r1.md:10084: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r1.md:10090: trailing whitespace.
+    92	
.oracle/checkins/batch-2-r1.md:10094: trailing whitespace.
+    96	
.oracle/checkins/batch-2-r1.md:10106: trailing whitespace.
+   108	
.oracle/checkins/batch-2-r1.md:10112: trailing whitespace.
+   114	
.oracle/checkins/batch-2-r1.md:10117: trailing whitespace.
+   119	
.oracle/checkins/batch-2-r1.md:10127: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r1.md:10128: trailing whitespace.
+   130	
.oracle/checkins/batch-2-r1.md:10133: trailing whitespace.
+   135	
.oracle/checkins/batch-2-r1.md:10136: trailing whitespace.
+   138	
.oracle/checkins/batch-2-r1.md:10147: trailing whitespace.
+   149	
.oracle/checkins/batch-2-r1.md:10159: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r1.md:10160: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r1.md:10185: trailing whitespace.
+   187	
.oracle/checkins/batch-2-r1.md:10203: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r1.md:10215: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r1.md:10216: trailing whitespace.
+   218	
.oracle/checkins/batch-2-r1.md:10236: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r1.md:10245: trailing whitespace.
+   247	
.oracle/checkins/batch-2-r1.md:10251: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r1.md:10252: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r1.md:10260: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r1.md:10263: trailing whitespace.
+   265	
.oracle/checkins/batch-2-r1.md:10273: trailing whitespace.
+   275	
.oracle/checkins/batch-2-r1.md:10283: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r1.md:10286: trailing whitespace.
+   128	
.oracle/checkins/batch-2-r1.md:10287: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r1.md:10290: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r1.md:10297: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r1.md:10298: trailing whitespace.
+   140	
.oracle/checkins/batch-2-r1.md:10301: trailing whitespace.
+   143	
.oracle/checkins/batch-2-r1.md:10308: trailing whitespace.
+   150	
.oracle/checkins/batch-2-r1.md:10309: trailing whitespace.
+   151	
.oracle/checkins/batch-2-r1.md:10316: trailing whitespace.
+   158	
.oracle/checkins/batch-2-r1.md:10323: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r1.md:10324: trailing whitespace.
+   166	
.oracle/checkins/batch-2-r1.md:10334: trailing whitespace.
+   176	
.oracle/checkins/batch-2-r1.md:10341: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r1.md:10342: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r1.md:10346: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r1.md:10353: trailing whitespace.
+   195	
.oracle/checkins/batch-2-r1.md:10354: trailing whitespace.
+   196	
.oracle/checkins/batch-2-r1.md:10379: trailing whitespace.
+   221	
.oracle/checkins/batch-2-r1.md:10386: trailing whitespace.
+   228	
.oracle/checkins/batch-2-r1.md:10387: trailing whitespace.
+   229	
.oracle/checkins/batch-2-r1.md:10391: trailing whitespace.
+   233	
.oracle/checkins/batch-2-r1.md:10398: trailing whitespace.
+   240	
.oracle/checkins/batch-2-r1.md:10399: trailing whitespace.
+   241	
.oracle/checkins/batch-2-r1.md:10476: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r1.md:10481: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r1.md:10489: trailing whitespace.
+    15	
.oracle/checkins/batch-2-r1.md:10491: trailing whitespace.
+    17	
.oracle/checkins/batch-2-r1.md:10501: trailing whitespace.
+    27	
.oracle/checkins/batch-2-r1.md:10510: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r1.md:10511: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r1.md:10519: trailing whitespace.
+    45	
.oracle/checkins/batch-2-r1.md:10520: trailing whitespace.
+    46	
.oracle/checkins/batch-2-r1.md:10524: trailing whitespace.
+    50	
.oracle/checkins/batch-2-r1.md:10525: trailing whitespace.
+    51	
.oracle/checkins/batch-2-r1.md:10529: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r1.md:10531: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r1.md:10532: trailing whitespace.
+    58	
.oracle/checkins/batch-2-r1.md:10554: trailing whitespace.
+    80	
.oracle/checkins/batch-2-r1.md:10555: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r1.md:10560: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r1.md:10561: trailing whitespace.
+    87	
.oracle/checkins/batch-2-r1.md:10569: trailing whitespace.
+    95	
.oracle/checkins/batch-2-r1.md:10594: trailing whitespace.
+   120	
.oracle/checkins/batch-2-r1.md:10595: trailing whitespace.
+   121	
.oracle/checkins/batch-2-r1.md:10605: trailing whitespace.
+   131	
.oracle/checkins/batch-2-r1.md:10606: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r1.md:10627: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r1.md:10628: trailing whitespace.
+   154	
.oracle/checkins/batch-2-r1.md:10638: trailing whitespace.
+   164	
.oracle/checkins/batch-2-r1.md:10644: trailing whitespace.
+   170	
.oracle/checkins/batch-2-r1.md:10656: trailing whitespace.
+   182	
.oracle/checkins/batch-2-r1.md:10657: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r1.md:10661: trailing whitespace.
+   187	
.oracle/checkins/batch-2-r1.md:10662: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r1.md:10668: trailing whitespace.
+   194	
.oracle/checkins/batch-2-r1.md:10678: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r1.md:10695: trailing whitespace.
+   221	
.oracle/checkins/batch-2-r1.md:10705: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r1.md:10718: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r1.md:10723: trailing whitespace.
+   249	
.oracle/checkins/batch-2-r1.md:10728: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r1.md:10730: trailing whitespace.
+   256	
.oracle/checkins/batch-2-r1.md:10740: trailing whitespace.
+   266	
.oracle/checkins/batch-2-r1.md:10741: trailing whitespace.
+   267	
.oracle/checkins/batch-2-r1.md:10745: trailing whitespace.
+   271	
.oracle/checkins/batch-2-r1.md:10746: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r1.md:10750: trailing whitespace.
+   276	
.oracle/checkins/batch-2-r1.md:10753: trailing whitespace.
+   279	
.oracle/checkins/batch-2-r1.md:10761: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r1.md:10762: trailing whitespace.
+   288	
.oracle/checkins/batch-2-r1.md:10766: trailing whitespace.
+   292	
.oracle/checkins/batch-2-r1.md:10775: trailing whitespace.
+   301	
.oracle/checkins/batch-2-r1.md:10776: trailing whitespace.
+   302	
.oracle/checkins/batch-2-r1.md:10785: trailing whitespace.
+   311	
.oracle/checkins/batch-2-r1.md:10788: trailing whitespace.
+   314	
.oracle/checkins/batch-2-r1.md:10789: trailing whitespace.
+   315	
.oracle/checkins/batch-2-r1.md:10793: trailing whitespace.
+   319	
.oracle/checkins/batch-2-r1.md:10794: trailing whitespace.
+   320	
.oracle/checkins/batch-2-r1.md:10800: trailing whitespace.
+   326	
.oracle/checkins/batch-2-r1.md:10814: trailing whitespace.
+   340	
.oracle/checkins/batch-2-r1.md:10818: trailing whitespace.
+   344	
.oracle/checkins/batch-2-r1.md:10821: trailing whitespace.
+   347	
.oracle/checkins/batch-2-r1.md:10822: trailing whitespace.
+   348	
.oracle/checkins/batch-2-r1.md:10828: trailing whitespace.
+   354	
.oracle/checkins/batch-2-r1.md:10843: trailing whitespace.
+   368	
.oracle/checkins/batch-2-r1.md:10847: trailing whitespace.
+   372	
.oracle/checkins/batch-2-r1.md:10851: trailing whitespace.
+   376	
.oracle/checkins/batch-2-r1.md:10855: trailing whitespace.
+   380	
.oracle/checkins/batch-2-r1.md:10859: trailing whitespace.
+   384	
.oracle/checkins/batch-2-r1.md:10860: trailing whitespace.
+   385	
.oracle/checkins/batch-2-r1.md:10864: trailing whitespace.
+   389	
.oracle/checkins/batch-2-r1.md:10865: trailing whitespace.
+   390	
.oracle/checkins/batch-2-r1.md:10868: trailing whitespace.
+   393	
.oracle/checkins/batch-2-r1.md:10869: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r1.md:10882: trailing whitespace.
+   407	
.oracle/checkins/batch-2-r1.md:10883: trailing whitespace.
+   408	
.oracle/checkins/batch-2-r1.md:10902: trailing whitespace.
+   427	
.oracle/checkins/batch-2-r1.md:10903: trailing whitespace.
+   428	
.oracle/checkins/batch-2-r1.md:10918: trailing whitespace.
+   443	
.oracle/checkins/batch-2-r1.md:10919: trailing whitespace.
+   444	
.oracle/checkins/batch-2-r1.md:10933: trailing whitespace.
+   458	
.oracle/checkins/batch-2-r1.md:10942: trailing whitespace.
+   467	
.oracle/checkins/batch-2-r1.md:10945: trailing whitespace.
+   470	
.oracle/checkins/batch-2-r1.md:10997: trailing whitespace.
+   522	
.oracle/checkins/batch-2-r1.md:10998: trailing whitespace.
+   523	
.oracle/checkins/batch-2-r1.md:11008: trailing whitespace.
+   533	
.oracle/checkins/batch-2-r1.md:11021: trailing whitespace.
+   546	
.oracle/checkins/batch-2-r1.md:11043: trailing whitespace.
+   568	
.oracle/checkins/batch-2-r1.md:11044: trailing whitespace.
+   569	
.oracle/checkins/batch-2-r1.md:11052: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r1.md:11056: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r1.md:11058: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r1.md:11067: trailing whitespace.
+    17	
.oracle/checkins/batch-2-r1.md:11069: trailing whitespace.
+    19	
.oracle/checkins/batch-2-r1.md:11071: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r1.md:11072: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r1.md:11076: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r1.md:11077: trailing whitespace.
+    27	
.oracle/checkins/batch-2-r1.md:11081: trailing whitespace.
+    31	
.oracle/checkins/batch-2-r1.md:11084: trailing whitespace.
+    34	
.oracle/checkins/batch-2-r1.md:11090: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r1.md:11092: trailing whitespace.
+    42	
.oracle/checkins/batch-2-r1.md:11109: trailing whitespace.
+    59	
.oracle/checkins/batch-2-r1.md:11113: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r1.md:11115: trailing whitespace.
+    65	
.oracle/checkins/batch-2-r1.md:11119: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r1.md:11121: trailing whitespace.
+    71	
.oracle/checkins/batch-2-r1.md:11129: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r1.md:11135: trailing whitespace.
+    85	
.oracle/checkins/batch-2-r1.md:11136: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r1.md:11139: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r1.md:11140: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r1.md:11143: trailing whitespace.
+    93	
.oracle/checkins/batch-2-r1.md:11156: trailing whitespace.
+   106	
.oracle/checkins/batch-2-r1.md:11157: trailing whitespace.
+   107	
.oracle/checkins/batch-2-r1.md:11168: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r1.md:11169: trailing whitespace.
+   119	
.oracle/checkins/batch-2-r1.md:11174: trailing whitespace.
+   124	
.oracle/checkins/batch-2-r1.md:11175: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r1.md:11182: trailing whitespace.
+   271	
.oracle/checkins/batch-2-r1.md:11191: trailing whitespace.
+   280	
.oracle/checkins/batch-2-r1.md:11192: trailing whitespace.
+   281	
.oracle/checkins/batch-2-r1.md:11199: trailing whitespace.
+   288	
.oracle/checkins/batch-2-r1.md:11204: trailing whitespace.
+   293	
.oracle/checkins/batch-2-r1.md:11205: trailing whitespace.
+   294	
.oracle/checkins/batch-2-r1.md:11212: trailing whitespace.
+   301	
.oracle/checkins/batch-2-r1.md:11218: trailing whitespace.
+   307	
.oracle/checkins/batch-2-r1.md:11220: trailing whitespace.
+   309	
.oracle/checkins/batch-2-r1.md:11221: trailing whitespace.
+   310	
.oracle/checkins/batch-2-r1.md:11225: trailing whitespace.
+   314	
.oracle/checkins/batch-2-r1.md:11226: trailing whitespace.
+   315	
.oracle/checkins/batch-2-r1.md:11234: trailing whitespace.
+   323	
.oracle/checkins/batch-2-r1.md:11359: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r1.md:11360: trailing whitespace.
+   395	
.oracle/checkins/batch-2-r1.md:11407: trailing whitespace.
+   442	
.oracle/checkins/batch-2-r1.md:11423: trailing whitespace.
+   458	
.oracle/checkins/batch-2-r1.md:11424: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r1.md:11445: trailing whitespace.
+   480	
.oracle/checkins/batch-2-r1.md:11470: trailing whitespace.
+   505	
.oracle/checkins/batch-2-r1.md:11471: trailing whitespace.
+   506	
.oracle/checkins/batch-2-r1.md:11498: trailing whitespace.
+   533	
.oracle/checkins/batch-2-r1.md:11499: trailing whitespace.
+   534	
.oracle/checkins/batch-2-r1.md:11524: trailing whitespace.
+   559	
.oracle/checkins/batch-2-r1.md:11525: trailing whitespace.
+   560	
.oracle/checkins/batch-2-r1.md:11565: trailing whitespace.
+   600	
.oracle/checkins/batch-2-r1.md:11566: trailing whitespace.
+   601	
.oracle/checkins/batch-2-r1.md:11593: trailing whitespace.
+   628	
.oracle/checkins/batch-2-r1.md:11594: trailing whitespace.
+   629	
.oracle/checkins/batch-2-r1.md:11602: trailing whitespace.
+   637	
.oracle/checkins/batch-2-r1.md:11608: trailing whitespace.
+   643	
.oracle/checkins/batch-2-r1.md:11615: trailing whitespace.
+   650	
.oracle/checkins/batch-2-r1.md:11634: trailing whitespace.
+   669	
.oracle/checkins/batch-2-r1.md:11644: trailing whitespace.
+   679	
.oracle/checkins/batch-2-r1.md:11665: trailing whitespace.
+   700	
.oracle/checkins/batch-2-r1.md:11666: trailing whitespace.
+   701	
.oracle/checkins/batch-2-r1.md:11676: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r1.md:11677: trailing whitespace.
+   251	
.oracle/checkins/batch-2-r1.md:11685: trailing whitespace.
+   259	
.oracle/checkins/batch-2-r1.md:11686: trailing whitespace.
+   260	
.oracle/checkins/batch-2-r1.md:11698: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r1.md:11699: trailing whitespace.
+   273	
.oracle/checkins/batch-2-r1.md:11702: trailing whitespace.
+   276	
.oracle/checkins/batch-2-r1.md:11703: trailing whitespace.
+   277	
.oracle/checkins/batch-2-r1.md:11722: trailing whitespace.
+   296	
.oracle/checkins/batch-2-r1.md:11723: trailing whitespace.
+   297	
.oracle/checkins/batch-2-r1.md:11761: trailing whitespace.
+   335	
.oracle/checkins/batch-2-r1.md:11788: trailing whitespace.
+   362	
.oracle/checkins/batch-2-r1.md:11789: trailing whitespace.
+   363	
.oracle/checkins/batch-2-r1.md:11884: trailing whitespace.
+   246	
.oracle/checkins/batch-2-r1.md:11888: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r1.md:11895: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r1.md:11907: trailing whitespace.
+   269	
.oracle/checkins/batch-2-r1.md:11908: trailing whitespace.
+   270	
.oracle/checkins/batch-2-r1.md:11915: trailing whitespace.
+   277	
.oracle/checkins/batch-2-r1.md:11916: trailing whitespace.
+   278	
.oracle/checkins/batch-2-r1.md:11932: trailing whitespace.
+   294	
.oracle/checkins/batch-2-r1.md:11933: trailing whitespace.
+   295	
.oracle/checkins/batch-2-r1.md:11964: trailing whitespace.
+   326	
.oracle/checkins/batch-2-r1.md:11965: trailing whitespace.
+   327	
.oracle/checkins/batch-2-r1.md:11982: trailing whitespace.
+   344	
.oracle/checkins/batch-2-r1.md:11983: trailing whitespace.
+   345	
.oracle/checkins/batch-2-r1.md:11986: trailing whitespace.
+   348	
.oracle/checkins/batch-2-r1.md:11987: trailing whitespace.
+   349	
.oracle/checkins/batch-2-r1.md:11993: trailing whitespace.
+   355	
.oracle/checkins/batch-2-r1.md:11994: trailing whitespace.
+   356	
.oracle/checkins/batch-2-r1.md:12030: trailing whitespace.
+   392	
.oracle/checkins/batch-2-r1.md:12039: trailing whitespace.
+   401	
.oracle/checkins/batch-2-r1.md:12040: trailing whitespace.
+   402	
.oracle/checkins/batch-2-r1.md:12047: trailing whitespace.
+   409	
.oracle/checkins/batch-2-r1.md:12048: trailing whitespace.
+   410	
.oracle/checkins/batch-2-r1.md:12065: trailing whitespace.
+   427	
.oracle/checkins/batch-2-r1.md:12066: trailing whitespace.
+   428	
.oracle/checkins/batch-2-r1.md:12071: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r1.md:12080: trailing whitespace.
+    11	
.oracle/checkins/batch-2-r1.md:12082: trailing whitespace.
+    13	
.oracle/checkins/batch-2-r1.md:12092: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r1.md:12093: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r1.md:12098: trailing whitespace.
+    29	
.oracle/checkins/batch-2-r1.md:12099: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r1.md:12102: trailing whitespace.
+    33	
.oracle/checkins/batch-2-r1.md:12103: trailing whitespace.
+    34	
.oracle/checkins/batch-2-r1.md:12108: trailing whitespace.
+    39	
.oracle/checkins/batch-2-r1.md:12109: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r1.md:12132: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r1.md:12133: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r1.md:12143: trailing whitespace.
+    74	
.oracle/checkins/batch-2-r1.md:12144: trailing whitespace.
+    75	
.oracle/checkins/batch-2-r1.md:12158: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r1.md:12159: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r1.md:12165: trailing whitespace.
+    96	
.oracle/checkins/batch-2-r1.md:12169: trailing whitespace.
+   100	
.oracle/checkins/batch-2-r1.md:12170: trailing whitespace.
+   101	
.oracle/checkins/batch-2-r1.md:12192: trailing whitespace.
+   123	
.oracle/checkins/batch-2-r1.md:12194: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r1.md:12195: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r1.md:12198: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r1.md:12208: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r1.md:12211: trailing whitespace.
+   142	
.oracle/checkins/batch-2-r1.md:12212: trailing whitespace.
+   143	
.oracle/checkins/batch-2-r1.md:12224: trailing whitespace.
+   155	
.oracle/checkins/batch-2-r1.md:12230: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r1.md:12231: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r1.md:12234: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r1.md:12237: trailing whitespace.
+   168	
.oracle/checkins/batch-2-r1.md:12246: trailing whitespace.
+   177	
.oracle/checkins/batch-2-r1.md:12247: trailing whitespace.
+   178	
.oracle/checkins/batch-2-r1.md:12250: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r1.md:12257: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r1.md:12263: trailing whitespace.
+   194	
.oracle/checkins/batch-2-r1.md:12272: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r1.md:12273: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r1.md:12277: trailing whitespace.
+   208	
.oracle/checkins/batch-2-r1.md:12280: trailing whitespace.
+   211	
.oracle/checkins/batch-2-r1.md:12281: trailing whitespace.
+   212	
.oracle/checkins/batch-2-r1.md:12285: trailing whitespace.
+   216	
.oracle/checkins/batch-2-r1.md:12288: trailing whitespace.
+   219	
.oracle/checkins/batch-2-r1.md:12289: trailing whitespace.
+   220	
.oracle/checkins/batch-2-r1.md:12293: trailing whitespace.
+   224	
.oracle/checkins/batch-2-r1.md:12296: trailing whitespace.
+   227	
.oracle/checkins/batch-2-r1.md:12300: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r1.md:12301: trailing whitespace.
+   232	
.oracle/checkins/batch-2-r1.md:12308: trailing whitespace.
+   239	
.oracle/checkins/batch-2-r1.md:12318: trailing whitespace.
+   249	
.oracle/checkins/batch-2-r1.md:12323: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r1.md:12324: trailing whitespace.
+   255	
.oracle/checkins/batch-2-r1.md:12330: trailing whitespace.
+   261	
.oracle/checkins/batch-2-r1.md:12344: trailing whitespace.
+   275	
.oracle/checkins/batch-2-r1.md:12538: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r1.md:12546: trailing whitespace.
+   140	
.oracle/checkins/batch-2-r1.md:12548: trailing whitespace.
+   142	
.oracle/checkins/batch-2-r1.md:12553: trailing whitespace.
+   147	
.oracle/checkins/batch-2-r1.md:12555: trailing whitespace.
+   149	
.oracle/checkins/batch-2-r1.md:12559: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r1.md:12569: trailing whitespace.
+   163	
.oracle/checkins/batch-2-r1.md:12576: trailing whitespace.
+   170	
.oracle/checkins/batch-2-r1.md:12578: trailing whitespace.
+   172	
.oracle/checkins/batch-2-r1.md:12581: trailing whitespace.
+   175	
.oracle/checkins/batch-2-r1.md:12590: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r1.md:12595: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r1.md:12597: trailing whitespace.
+   191	
.oracle/checkins/batch-2-r1.md:12599: trailing whitespace.
+   193	
.oracle/checkins/batch-2-r1.md:12610: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r1.md:12614: trailing whitespace.
+   208	
.oracle/checkins/batch-2-r1.md:12623: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r1.md:12629: trailing whitespace.
+   223	
.oracle/checkins/batch-2-r1.md:12631: trailing whitespace.
+   225	
.oracle/checkins/batch-2-r1.md:12636: trailing whitespace.
+   230	
.oracle/checkins/batch-2-r1.md:12644: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r1.md:12646: trailing whitespace.
+   240	
.oracle/checkins/batch-2-r1.md:12649: trailing whitespace.
+   243	
.oracle/checkins/batch-2-r1.md:12657: trailing whitespace.
+   251	
.oracle/checkins/batch-2-r1.md:12661: trailing whitespace.
+   255	
.oracle/checkins/batch-2-r1.md:12663: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r1.md:12668: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r1.md:12685: trailing whitespace.
+   408	
.oracle/checkins/batch-2-r1.md:12687: trailing whitespace.
+   410	
.oracle/checkins/batch-2-r1.md:12689: trailing whitespace.
+   412	
.oracle/checkins/batch-2-r1.md:12698: trailing whitespace.
+   421	
.oracle/checkins/batch-2-r1.md:12707: trailing whitespace.
+   430	
.oracle/checkins/batch-2-r1.md:12711: trailing whitespace.
+   434	
.oracle/checkins/batch-2-r1.md:12713: trailing whitespace.
+   436	
.oracle/checkins/batch-2-r1.md:12715: trailing whitespace.
+   438	
.oracle/checkins/batch-2-r1.md:12730: trailing whitespace.
+   453	
.oracle/checkins/batch-2-r1.md:12738: trailing whitespace.
+   461	
.oracle/checkins/batch-2-r1.md:12740: trailing whitespace.
+   463	
.oracle/checkins/batch-2-r1.md:12742: trailing whitespace.
+   465	
.oracle/checkins/batch-2-r1.md:12747: trailing whitespace.
+   470	
.oracle/checkins/batch-2-r1.md:12751: trailing whitespace.
+   288	
.oracle/checkins/batch-2-r1.md:12752: trailing whitespace.
+   289	
.oracle/checkins/batch-2-r1.md:12775: trailing whitespace.
+   312	
.oracle/checkins/batch-2-r1.md:12776: trailing whitespace.
+   313	
.oracle/checkins/batch-2-r1.md:12797: trailing whitespace.
+   334	
.oracle/checkins/batch-2-r1.md:12798: trailing whitespace.
+   335	
.oracle/checkins/batch-2-r1.md:12809: trailing whitespace.
+   346	
.oracle/checkins/batch-2-r1.md:12810: trailing whitespace.
+   347	
.oracle/checkins/batch-2-r1.md:12821: trailing whitespace.
+   357	
.oracle/checkins/batch-2-r1.md:12822: trailing whitespace.
+   358	
.oracle/checkins/batch-2-r1.md:12834: trailing whitespace.
+   370	
.oracle/checkins/batch-2-r1.md:12835: trailing whitespace.
+   371	
.oracle/checkins/batch-2-r1.md:12839: trailing whitespace.
+   375	
.oracle/checkins/batch-2-r1.md:12846: trailing whitespace.
+   382	
.oracle/checkins/batch-2-r1.md:12847: trailing whitespace.
+   383	
.oracle/checkins/batch-2-r1.md:12851: trailing whitespace.
+   387	
.oracle/checkins/batch-2-r1.md:12858: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r1.md:12859: trailing whitespace.
+   395	
.oracle/checkins/batch-2-r1.md:12863: trailing whitespace.
+   399	
.oracle/checkins/batch-2-r1.md:12870: trailing whitespace.
+   406	
.oracle/checkins/batch-2-r1.md:12871: trailing whitespace.
+   407	
.oracle/checkins/batch-2-r1.md:12875: trailing whitespace.
+   411	
.oracle/checkins/batch-2-r1.md:12958: trailing whitespace.
+  1443	
.oracle/checkins/batch-2-r1.md:12959: trailing whitespace.
+  1444	
.oracle/checkins/batch-2-r1.md:12973: trailing whitespace.
+  1458	
.oracle/checkins/batch-2-r1.md:12994: trailing whitespace.
+  1479	
.oracle/checkins/batch-2-r1.md:12995: trailing whitespace.
+  1480	
.oracle/checkins/batch-2-r1.md:13053: trailing whitespace.
+  1537	
.oracle/checkins/batch-2-r1.md:13054: trailing whitespace.
+  1538	
.oracle/checkins/batch-2-r1.md:13245: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r1.md:13246: trailing whitespace.
+   395	
.oracle/checkins/batch-2-r1.md:13296: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r1.md:13297: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r1.md:13313: trailing whitespace.
+   303	
.oracle/checkins/batch-2-r1.md:13314: trailing whitespace.
+   304	
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-2-r1.md                     | 13375 +++++++++++++++++++
 astrid/core/media.py                               |    15 +-
 astrid/core/rendering/publication.py               |    11 +-
 astrid/core/rendering/transport.py                 |    19 +-
 astrid/packs/rendering/executors/render/run.py     |     2 +-
 tests/core/rendering/test_transport.py             |    13 +-
 .../__pycache__/backend.cpython-311.pyc            |   Bin 0 -> 29820 bytes
 .../fixtures/renderer_packs/raw_command/backend.py |    19 +-
 .../raw_command/requests/render.json               |    17 +-
 9 files changed, 13458 insertions(+), 13 deletions(-)
Reading additional input from stdin...
2026-08-12T05:28:02.338563Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:28:02.339371Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:28:02.339377Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff471-1eed-71d1-9981-cd60dbcb27ce
--------
user
# Megado Checkpoint — Batch 2 review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

You are the ORACLE. Batch 2 ("Command protocol and host-owned plumbing") of
the Pluggable Timeline Renderers epic is complete and committed as C2
(dedcc2c5). Batch 1 passed after 13 review rounds (verdict PASS in
`.oracle/checkins/batch-1-r13.md`); the Batch 1 completion tag is
`C2-batch1-done` (670d5f8). The Batch 2 diff is at /tmp/batch2.diff
(C2-batch1-done..C2, 31 files, +13046/-975).

## Batch 2 tasks (from .oracle/tasklist.md)

- T2.1 — CommandTransport (four protocol verbs, binary preflight, sanitized
  env, process groups, timeout/interrupt cleanup+reap, result parsing,
  structured renderer-qualified failures) [HARD]
- T2.2 — Raw protocol fixture pack (pure-Python generated MP4, no SDK, no
  committed binaries) + tests
- T2.3 — Asset cache extracted to astrid/core/rendering/asset_cache.py with
  training executor as compatible wrapper
- T2.4 — AssetMaterializer + InvocationAssetServer (contained staging,
  127.0.0.1 port 0, Range, thread join, deterministic cleanup) [HARD]
- T2.5 — resolve_render_profile + validate_render_result + extended media
  probe (14 new fields) [HARD]
- T2.6 — publish_render_result (per-output lock, video-first rename, atomic
  sidecar-last commit marker, conservative previous-output cleanup, orphan
  recovery) [HARD]

## Acceptance criteria (tasklist Batch 2)

- Commands execute as `<command> render|support|plan|finalize --request <abs>
  --result <abs>`, shell=False, pack-root cwd, sanitized env, absolute paths,
  binary preflight, timeout, captured logs, authoritative result-file parsing.
- Missing binaries, nonzero exits, timeout, interruption, absent/malformed
  results, absent/empty outputs, incompatible versions → renderer-qualified
  structured failures; process groups terminated and reaped on interruption.
- Raw fixture: no SDK import, deterministic 2s artifact, explicit extra root
  + trusted active install, never creates run.json.
- Asset-cache layout/URL keys/resume/drift/locking/EphemeralSession unchanged.
- Only invocation-staged assets served from 127.0.0.1:0; Range works; server
  always shuts down/closes/joins.
- Canonical profile from merged theme/timeline canvas with dimensions,
  rational FPS/time base, codecs, pixel format, audio rate/layout, tolerance.
- Artifact validation rejects missing/empty/escaped/symlinked/hash-mismatch/
  profile-incompatible/duration-invalid/audio-invalid; preserves attachments.
- Publication: per-output lock, video-first rename, atomic hashed sidecar
  last; crash-orphan recovery never commits an incomplete pair.

## Evidence

- Diff: /tmp/batch2.diff
- Host-verified: tests/core/rendering + asset cache + url smoke = 211 passed
  (after T2.4); 226 passed + 11 skipped (after T2.6, includes test_publication
  7); full consolidated Batch 2 acceptance (rendering + pack + registry +
  characterization + hype/iteration/editorial + audio_render) = 745 passed,
  2 failed (SAME 2 pre-existing env-dependent failures as baseline), 3
  skipped.

## Verdict

Binary: `PASS` or a list of issues. Verify the transport lifecycle (process
group cleanup, timeout, interrupt, reap — no zombies/orphans), the raw
fixture's determinism and no-SDK/no-run.json guarantees, the asset server
containment (port 0 bind, loopback, Range, thread join, cleanup), the probe
fields, artifact validation coverage, and the publication lock/atomicity/
orphan-recovery protocol. Also scan the diff for scope creep into Batch 1
frozen files (contracts.py, schemas/, docs/contracts/) and for regressions in
the render monolith the extraction touched. If PASS, say exactly `PASS`.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Astrid repository guidance plus its context-lean review workflow. I’ll keep the worktree read-only, split the high-risk protocol areas into independent review tracks, then reconcile everything against the exact Batch 2 acceptance criteria.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
    1266 total
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

Reading additional input from stdin...
2026-08-12T05:55:22.661494Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:55:22.661519Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:55:22.661524Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff48a-26ed-7c72-8141-4830b7abfc48
--------
user
# Megado Checkpoint — Batch 2 re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdict: `.oracle/checkins/batch-2.md` (6 issues). Batch 2 rework
committed as `5231a233` (prior head C2 = dedcc2c5). Incremental diff at
/tmp/batch2-r1.diff.

## How each of your 6 issues was addressed (host-implemented)

1. **Transport leaks process groups on post-spawn exceptions** → the entire
   post-spawn block now has a broad `except Exception` that terminates and
   reaps the process group (swallowing cleanup errors) before re-raising; the
   interrupt-grace path escalates to SIGKILL immediately if interrupted
   during the grace communicate, and the reap loop force-kills on repeated
   KeyboardInterrupt.
2. **Missing result classified invalid_artifact, should be protocol** →
   `_read_result_file` now raises `protocol` on FileNotFoundError; test
   renamed + updated (`test_absent_result_file_is_protocol_failure`), docs
   already specified `protocol`.
3. **Fixture misdeclares media profile** → SPS `frame_crop_bottom_offset`
   corrected 1→4 (1088−8=1080, matching the declared height); declared audio
   codec changed `sowt`→`pcm_s16le` (what ffprobe/strict probe reports);
   fixture test updated.
4. **Fixture support verb bypasses request validation** → `support` now runs
   `_validate_request` first and writes a `protocol` error on invalid
   requests (e.g. unsupported schema_version).
5. **Artifact validation accepts in-workspace symlinks** →
   `_contained_regular_file` rejects `candidate.is_symlink()` BEFORE
   resolving; in-workspace symlinks now fail with `escaped_path`.
6. **Publication symlink checks ineffective + replace-before-invalidate** →
   committed-pair read and publish/cleanup paths check `is_symlink()` on the
   UNRESOLVED paths (resolved paths can't reveal links); previous sidecar is
   invalidated BEFORE the video replace so a crash can leave an orphan but
   never a stale committed marker; cleanup skips symlink candidates.

## Evidence

- Incremental diff: /tmp/batch2-r1.diff (7 files)
- Host-verified: test_transport (13) + test_raw_command_fixture (6) +
  test_artifacts + test_publication + test_assets all pass; full consolidated
  Batch 2 acceptance = 745 passed, 2 failed (SAME 2 pre-existing
  env-dependent failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Verify the six closures, especially the
transport cleanup on non-timeout exceptions and interrupt escalation, the
fixture's probe-accuracy (run ffprobe on a generated output and compare), and
the publication ordering. If PASS, say exactly `PASS`.
codex
I’ll re-review the incremental commit as a read-only checkpoint. I’m using the Megado workflow plus the repository’s context-mining guidance; after reading their instructions, I’ll split the six closures into independent reviews and personally reconcile the evidence before returning only the required verdict.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,300p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
     494 total
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
diff --git a/.oracle/checkins/batch-2-r1.md b/.oracle/checkins/batch-2-r1.md
new file mode 100644
index 00000000..c128d49c
--- /dev/null
+++ b/.oracle/checkins/batch-2-r1.md
@@ -0,0 +1,13375 @@
+Reading additional input from stdin...
+2026-08-12T05:55:22.661494Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T05:55:22.661519Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T05:55:22.661524Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff48a-26ed-7c72-8141-4830b7abfc48
+--------
+user
+# Megado Checkpoint — Batch 2 re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdict: `.oracle/checkins/batch-2.md` (6 issues). Batch 2 rework
+committed as `5231a233` (prior head C2 = dedcc2c5). Incremental diff at
+/tmp/batch2-r1.diff.
+
+## How each of your 6 issues was addressed (host-implemented)
+
+1. **Transport leaks process groups on post-spawn exceptions** → the entire
+   post-spawn block now has a broad `except Exception` that terminates and
+   reaps the process group (swallowing cleanup errors) before re-raising; the
+   interrupt-grace path escalates to SIGKILL immediately if interrupted
+   during the grace communicate, and the reap loop force-kills on repeated
+   KeyboardInterrupt.
+2. **Missing result classified invalid_artifact, should be protocol** →
+   `_read_result_file` now raises `protocol` on FileNotFoundError; test
+   renamed + updated (`test_absent_result_file_is_protocol_failure`), docs
+   already specified `protocol`.
+3. **Fixture misdeclares media profile** → SPS `frame_crop_bottom_offset`
+   corrected 1→4 (1088−8=1080, matching the declared height); declared audio
+   codec changed `sowt`→`pcm_s16le` (what ffprobe/strict probe reports);
+   fixture test updated.
+4. **Fixture support verb bypasses request validation** → `support` now runs
+   `_validate_request` first and writes a `protocol` error on invalid
+   requests (e.g. unsupported schema_version).
+5. **Artifact validation accepts in-workspace symlinks** →
+   `_contained_regular_file` rejects `candidate.is_symlink()` BEFORE
+   resolving; in-workspace symlinks now fail with `escaped_path`.
+6. **Publication symlink checks ineffective + replace-before-invalidate** →
+   committed-pair read and publish/cleanup paths check `is_symlink()` on the
+   UNRESOLVED paths (resolved paths can't reveal links); previous sidecar is
+   invalidated BEFORE the video replace so a crash can leave an orphan but
+   never a stale committed marker; cleanup skips symlink candidates.
+
+## Evidence
+
+- Incremental diff: /tmp/batch2-r1.diff (7 files)
+- Host-verified: test_transport (13) + test_raw_command_fixture (6) +
+  test_artifacts + test_publication + test_assets all pass; full consolidated
+  Batch 2 acceptance = 745 passed, 2 failed (SAME 2 pre-existing
+  env-dependent failures), 3 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Verify the six closures, especially the
+transport cleanup on non-timeout exceptions and interrupt escalation, the
+fixture's probe-accuracy (run ffprobe on a generated output and compare), and
+the publication ordering. If PASS, say exactly `PASS`.
+codex
+I’ll re-review the incremental commit as a read-only checkpoint. I’m using the Megado workflow plus the repository’s context-mining guidance; after reading their instructions, I’ll split the six closures into independent reviews and personally reconcile the evidence before returning only the required verdict.
+exec
+/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,300p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
+     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
+      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
+     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
+     494 total
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
+---
+
+# Context Minning & Subagent Maxxing
+
+The goal of this skill is singular: **keep the actual work in the main thread's
+context as small as possible.** Long contexts get slow, expensive, and forgetful.
+Every turn, the most useful tokens should be present and the rest should be
+elsewhere — in a file, in a summary, or in a subagent that already finished.
+
+It runs as two continuous moves — a posture, not a one-time cleanup. This file is the
+philosophy and the high level; each move has a standalone skill with the mechanics,
+syntax, and anti-patterns. **Invoke those for the how.**
+
+---
+
+## Move 1 — Context minning: condense at the seams
+
+When a chunk of work becomes *done and durable* — a plan spec'd out, a bug
+root-caused, a long read distilled to one answer — the path to that conclusion is dead
+weight. At those seams: **write the conclusion to a durable artifact, then compact from
+there.** Prefer landing real work as a megaplan asset (plan file or ticket) over a loose
+note, so what you shed becomes trackable work rather than vanishing.
+
+The discipline is *write it down first* — you can only safely forget what you can
+re-read. And don't over-do it: compact at seams, never on a timer; a slightly long
+context costs less than a lost decision.
+
+→ **`minimize-context`** for the seam catalogue, the `/compact` · `/clear` · `/context`
+mechanics, megaplan-asset detail, and the over-minning failure mode.
+
+→ **`context-usage`** to *see* the context filling: a turn-by-turn token-growth chart
+read from the session transcript, with every compaction boundary marked. Use it to
+check whether you're minning at the right seams or letting context balloon to
+auto-compaction. (`/context` is the live snapshot; `context-usage` is the trajectory.)
+
+## Move 2 — Subagent maxxing: do the work elsewhere
+
+**Default to doing work in a subagent, not the thread.** Flip the question from "should
+a subagent do this?" to "is there any reason this *can't*?" Its tool calls, file reads,
+and reasoning stay in *its* context; only the conclusion returns to you. **Execution is
+the headline case** — implementing, investigating, building is where byproduct piles up,
+so it's the first thing to hand off, not the last. Be willing to launch **many**, even
+in parallel, until you have clarity — that's cheaper than carrying the trail inline.
+
+Two principles carry most of the value: spend the subagent on the *byproduct-heavy*
+part and ask it to **return the conclusion, not the trail**; and **use the cheapest
+model that can do the job** (cheap scan-work → reasoning → frontier only for real
+complexity), preparing the context well enough that a cheaper tier can win. Don't
+dispatch if you already have the answer.
+
+**Match the venue to the scale.** A one-shot subagent dispatch is for ad-hoc work —
+research, a sense-check, a contained fix. Once something is more than ~a day or two of
+work it's a *deliverable*: run it as a **megaplan** (itself launched in a subagent) and
+use **`megaplan-decision`** to size the tier/robustness/depth. Past ~2 weeks → an epic.
+
+→ **`subagent-launcher`** for the pathways, the cost-escalation ladder with model
+identifiers, and how to shape a self-contained subagent prompt.
+
+---
+
+## The loop, in one line
+
+Every turn: *Did I just hit a seam? → write it down, compact. Am I about to do real
+work? → hand it to a subagent.* Keep the main thread holding only what the next
+decision needs.
+---
+name: subagent-launcher
+description: Launch an external model as a subagent for a second opinion, adversarial review, or delegated work. Default pathway is an agentic DeepSeek / Kimi / Zhipu GLM hermes subagent (file/web/terminal tools, one process or fanned out N-wide); also Codex (GPT-5.5) and Claude via the Agent tool. Use for independent root-cause analysis, cross-checking your reasoning, judge/jury panels, or handing implementation to a different model.
+---
+
+# Subagent launcher (multi-model)
+
+Dispatch work to a model other than the one driving the conversation. Two payoffs: **independence** — a *different* model's judgement, not a copy of your own — and **context hygiene** — the subagent's tool calls and reasoning stay in *its* context; only the conclusion returns to you.
+
+Three pathways:
+
+| Pathway | Model | Invocation | Tools |
+| --- | --- | --- | --- |
+| **Hermes agentic** *(default)* | DeepSeek V4 (Pro/Flash), Kimi K2.7, Zhipu GLM, … | `launch_hermes_agent.py` — or `fan.py` to run N in one process | `file`, `web`, optional `terminal` |
+| **Codex** | GPT-5.5 | `codex exec` (CLI) | sandboxed workspace |
+| **Claude** | Claude (Opus/Sonnet/Haiku) | `launch_claude_agent.py --model=opus` or Claude Code `Agent` tool | Claude Code tools |
+
+**Default to the hermes agentic pathway, and to DeepSeek within it** — different model family, cheap, tool-using. Reach for Codex or Claude only when you specifically want their strengths.
+
+> **⚠️ Network sandbox warning for Codex subagents**
+> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Hermes agents (DeepSeek/Kimi/MiMo/GLM/OpenRouter) need outbound network to reach their provider APIs, so **launching them from inside a `codex exec` subagent will fail**. The launcher itself is fine; it fails only because the parent process has no network.
+>
+> **Workarounds:**
+> 1. Launch the hermes subagent directly from a normal shell or Bash tool.
+> 2. If you need a **Codex subagent to orchestrate hermes subagents**, run the
+>    outer Codex command with `--sandbox danger-full-access` and seal stdin with

exec
/bin/zsh -lc 'git diff --name-status 5231a233..7f7c25d5
git diff --numstat 5231a233..7f7c25d5
tail -n 160 .oracle/checkins/batch-2.md
tail -n 180 .oracle/checkins/batch-2-r1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-2-r1.md
M	astrid/core/media.py
M	astrid/core/rendering/publication.py
M	astrid/core/rendering/transport.py
M	astrid/packs/rendering/executors/render/run.py
M	tests/core/rendering/test_transport.py
A	tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc
M	tests/fixtures/renderer_packs/raw_command/backend.py
M	tests/fixtures/renderer_packs/raw_command/requests/render.json
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
13375	0	.oracle/checkins/batch-2-r1.md
14	1	astrid/core/media.py
9	2	astrid/core/rendering/publication.py
18	1	astrid/core/rendering/transport.py
1	1	astrid/packs/rendering/executors/render/run.py
12	1	tests/core/rendering/test_transport.py
-	-	tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc
16	3	tests/fixtures/renderer_packs/raw_command/backend.py
13	4	tests/fixtures/renderer_packs/raw_command/requests/render.json
exec
/bin/zsh -lc "rg -n '"'^def _.*nal|annex|_video'"' tests/fixtures/renderer_packs/raw_command/backend.py | head -80
sed -n '155,250p' tests/fixtures/renderer_packs/raw_command/backend.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
119:def _sps_nal() -> bytes:
145:def _pps_nal() -> bytes:
167:def _idr_slice_nal(frame_index: int) -> bytes:
    w.put(0, 1)             # weighted_pred_flag
    w.put(0, 2)             # weighted_bipred_idc
    _se(w, 0)               # pic_init_qp_minus26
    _se(w, 0)               # pic_init_qs_minus26
    _se(w, 0)               # chroma_qp_index_offset
    w.put(0, 1)             # deblocking_filter_control_present_flag
    w.put(0, 1)             # constrained_intra_pred_flag
    w.put(0, 1)             # redundant_pic_cnt_present_flag
    w.finish()
    return bytes([0x68]) + _escape_rbsp(bytes(w.data))


def _idr_slice_nal(frame_index: int) -> bytes:
    """One IDR I-frame: every macroblock is I_16x16_2_0_0 with no residual.

    With CodedBlockPatternLuma/Chroma = 0 the decoder reconstructs each 16x16
    block from DC prediction (unavailable neighbours default to 128), so the
    whole frame decodes to a deterministic solid color.  Six bits per MB:
    mb_type ue(3) == "00100" (I_16x16 with Intra16x16PredMode 2 = DC) plus
    intra_chroma_pred_mode ue(0) == "1" (chroma DC).
    """
    w = _BitWriter()
    _ue(w, 0)               # first_mb_in_slice
    _ue(w, 2)               # slice_type = I (2)
    _ue(w, 0)               # pic_parameter_set_id
    w.put(0, 4)             # frame_num (IDR pictures use 0)
    _ue(w, 0)               # idr_pic_id
    w.put((2 * frame_index) & 0xFF, 8)  # pic_order_cnt_lsb (POC grows by 2/frame)
    w.put(0, 1)             # no_output_of_prior_pics_flag
    w.put(0, 1)             # long_term_reference_flag
    _se(w, 0)               # slice_qp_delta
    for _ in range(_MB_COUNT):
        w.put(0b001001, 6)  # mb_type=3 (I_16x16_2_0_0) + intra_chroma_pred_mode=0
    w.finish()
    return bytes([0x65]) + _escape_rbsp(bytes(w.data))


# ---------------------------------------------------------------------------
# Minimal ISO BMFF (MP4) muxer
# ---------------------------------------------------------------------------


def _box(box_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(payload), box_type) + payload


def _fullbox(box_type: bytes, version_flags: int, payload: bytes) -> bytes:
    return struct.pack(">I4sI", 12 + len(payload), box_type, version_flags) + payload


def _matrix() -> bytes:
    return _MATRIX


def _ftyp() -> bytes:
    return (
        struct.pack(">I4sII", 32, b"ftyp", 0x69736F6D, 0x00000200)
        + b"isomiso2avc1mp41"
    )


def _mvhd(duration: int) -> bytes:
    payload = (
        struct.pack(">IIII", 0, 0, 12288, duration)  # timescale = 12288
        + struct.pack(">I", 0x00010000)              # rate 1.0
        + struct.pack(">H", 0x0100)                  # volume 1.0
        + struct.pack(">H", 0)
        + struct.pack(">II", 0, 0)
        + _matrix()
        + b"\x00" * 24
        + struct.pack(">I", 3)                       # next_track_ID
    )
    return _fullbox(b"mvhd", 0, payload)


def _tkhd(track_id: int, duration: int, volume: int, width: int, height: int) -> bytes:
    payload = (
        struct.pack(">II", 0, 0)
        + struct.pack(">I", track_id)
        + struct.pack(">I", 0)
        + struct.pack(">I", duration)
        + struct.pack(">II", 0, 0)
        + struct.pack(">Hh", 0, 0)
        + struct.pack(">H", volume)
        + struct.pack(">H", 0)
        + _matrix()
        + struct.pack(">II", width << 16, height << 16)
    )
    return _fullbox(b"tkhd", 0x00000007, payload)


def _mdhd(timescale: int, duration: int) -> bytes:
    payload = (
        struct.pack(">IIII", 0, 0, timescale, duration)
        + struct.pack(">HH", 0x55C4, 0)  # language "und"
    )

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); p=b\"\\x00\\x00\\x00\\x01\"; sys.stdout.buffer.write(p+m[\"_sps_nal\"]()+p+m[\"_pps_nal\"]()+p+m[\"_idr_slice_nal\"](0))' | ffprobe -v error -f h264 -show_entries stream=codec_name,width,height,coded_width,coded_height,pix_fmt -of json pipe:0" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 17ms:
{
    "programs": [

    ],
    "stream_groups": [

    ],
    "streams": [
        {
            "codec_name": "h264",
            "width": 1920,
            "height": 1086,
            "coded_width": 1920,
            "coded_height": 1086,
            "pix_fmt": "yuv420p"
        }
    ]
}

  ✓ Verify Batch 2 commit boundary, frozen-file scope, and review inputs
  ✓ Audit CommandTransport lifecycle and raw protocol fixture
  ✓ Audit asset cache extraction, materialization/server, and render-monolith regressions
  ✓ Audit profile/probe, artifact validation, and publication invariants
  ✓ Consolidate focused verification into the oracle verdict
codex
- `CommandTransport` can leak subprocess groups on post-spawn exceptions other than timeout or `KeyboardInterrupt`; cleanup is itself interruptible before kill/reap completes. [transport.py:203](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:203), [transport.py:465](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:465)

- A missing authoritative result is incorrectly classified as `invalid_artifact`; the frozen protocol requires `protocol`. The test locks in the wrong behavior. [transport.py:567](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:567), [test_transport.py:205](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:205), [render-backend-v1.md:133](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:133)

- The raw fixture misdeclares its generated media profile. Its H.264 SPS crops 1088 lines to 1086, not 1080, and it declares audio codec `sowt` although ffprobe reports `pcm_s16le`. Strict artifact validation therefore rejects the fixture. [backend.py:131](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:131), [backend.py:471](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:471), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481)

- The raw fixture’s `support` verb bypasses request validation, so unsupported request schema versions succeed instead of returning `kind="protocol"`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)

- Artifact validation accepts in-workspace symlinked videos and attachments because it resolves the candidate before checking file type. Coverage only rejects symlinks that escape the workspace. [artifacts.py:154](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:154), [test_artifacts.py:167](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_artifacts.py:167)

- Publication’s symlink checks are ineffective because paths are resolved before `is_symlink()` is called. Publishing and cleanup can consequently replace or delete a symlink target, while committed-pair reads accept symlink aliases. [publication.py:87](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:87), [publication.py:139](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:139), [publication.py:266](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:266)

- Publication replaces the video before invalidating the previous sidecar. If interrupted in that gap and the replacement has the same hash but different provenance, the stale marker still appears committed, violating the crash-orphan invariant. [publication.py:278](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:278), [publication.py:151](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:151)
tokens used
585,441
- `CommandTransport` can leak subprocess groups on post-spawn exceptions other than timeout or `KeyboardInterrupt`; cleanup is itself interruptible before kill/reap completes. [transport.py:203](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:203), [transport.py:465](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:465)

- A missing authoritative result is incorrectly classified as `invalid_artifact`; the frozen protocol requires `protocol`. The test locks in the wrong behavior. [transport.py:567](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:567), [test_transport.py:205](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:205), [render-backend-v1.md:133](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:133)

- The raw fixture misdeclares its generated media profile. Its H.264 SPS crops 1088 lines to 1086, not 1080, and it declares audio codec `sowt` although ffprobe reports `pcm_s16le`. Strict artifact validation therefore rejects the fixture. [backend.py:131](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:131), [backend.py:471](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:471), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481)

- The raw fixture’s `support` verb bypasses request validation, so unsupported request schema versions succeed instead of returning `kind="protocol"`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)

- Artifact validation accepts in-workspace symlinked videos and attachments because it resolves the candidate before checking file type. Coverage only rejects symlinks that escape the workspace. [artifacts.py:154](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:154), [test_artifacts.py:167](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_artifacts.py:167)

- Publication’s symlink checks are ineffective because paths are resolved before `is_symlink()` is called. Publishing and cleanup can consequently replace or delete a symlink target, while committed-pair reads accept symlink aliases. [publication.py:87](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:87), [publication.py:139](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:139), [publication.py:266](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:266)

- Publication replaces the video before invalidating the previous sidecar. If interrupted in that gap and the replacement has the same hash but different provenance, the stale marker still appears committed, violating the crash-orphan invariant. [publication.py:278](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:278), [publication.py:151](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:151)
        "nb_streams": 2,
        "nb_programs": 0,
        "nb_stream_groups": 0,
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "format_long_name": "QuickTime / MOV",
        "start_time": "0.000000",
        "duration": "2.000000",
        "probe_score": 100,
        "tags": {
            "major_brand": "isom",
            "minor_version": "512",
            "compatible_brands": "isomiso2avc1mp41"
        }
    }
}

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '364,396p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   364	def _probe_required_video(probe: MediaProbe) -> None:
   365	    if not isinstance(probe, MediaProbe):
   366	        _invalid(
   367	            "incomplete_probe",
   368	            "strict ffprobe returned an invalid probe object",
   369	            received_type=type(probe).__name__,
   370	        )
   371	    if not probe.has_video_stream:
   372	        _invalid("missing_video_stream", "primary video has no video stream")
   373	    missing = [
   374	        field
   375	        for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
   376	        if getattr(probe, field) is None
   377	    ]
   378	    if probe.container is None and probe.format_name is None:
   379	        missing.append("container")
   380	    if probe.duration_rational is None and probe.duration_seconds is None:
   381	        missing.append("duration")
   382	    if missing:
   383	        _invalid(
   384	            "incomplete_probe",
   385	            "ffprobe returned incomplete primary-video metadata",
   386	            missing=missing,
   387	        )
   388	    if type(probe.width) is not int or probe.width <= 0:
   389	        _invalid("incomplete_probe", "ffprobe returned invalid video width", actual=probe.width)
   390	    if type(probe.height) is not int or probe.height <= 0:
   391	        _invalid("incomplete_probe", "ffprobe returned invalid video height", actual=probe.height)
   392	    _rational(probe.fps_rational, label="video FPS")
   393	    _rational(probe.time_base, label="video time base")
   394	
   395	
   396	def _compare_probe_to_profile(

codex
The key failures are now reproducible from code, not just inferred. I’m doing one final live-process injection using a disposable child that ignores SIGTERM; the harness will forcibly kill and reap it afterward. This specifically tests whether a non-timeout `communicate()` failure can escape the new cleanup path.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'exec(\"\"\"import json\\nimport os\\nimport signal\\nimport subprocess\\nimport sys\\nfrom pathlib import Path\\nfrom unittest.mock import patch\\nfrom astrid.core.rendering.transport import CommandTransport\\nreal_popen = subprocess.Popen\\nraw = real_popen([sys.executable, \\\"-c\\\", \\\"import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)\\\"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)\\nclass BrokenCommunicate:\\n    def __init__(self, process): self._process = process\\n    def __getattr__(self, name): return getattr(self._process, name)\\n    def communicate(self, *args, **kwargs): raise RuntimeError(\\\"synthetic non-timeout communicate failure\\\")\\nwrapped = BrokenCommunicate(raw)\\ntry:\\n    with patch(\\\"astrid.core.rendering.transport.subprocess.Popen\\\", return_value=wrapped):\\n        try:\\n            CommandTransport(\\\"raw_command.renderer\\\", termination_grace=0.05).run(\\\"render\\\", [sys.executable, \\\"-c\\\", \\\"pass\\\"], request_path=Path(\\\"tests/fixtures/renderer_packs/raw_command/requests/render.json\\\").resolve(), result_path=\\\"/tmp/astrid-review-unused-result.json\\\", cwd=Path.cwd(), timeout=1)\\n        except RuntimeError as exc:\\n            survived = raw.poll() is None\\n            print(json.dumps({\\\"reraised\\\": str(exc), \\\"child_survived_cleanup\\\": survived, \\\"pid\\\": raw.pid, \\\"returncode\\\": raw.returncode}))\\n        else:\\n            print(json.dumps({\\\"unexpected\\\": \\\"no exception\\\"}))\\nfinally:\\n    if raw.poll() is None:\\n        try: os.killpg(raw.pid, signal.SIGKILL)\\n        except ProcessLookupError: pass\\n    raw.communicate()\\n\"\"\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 140ms:
{"reraised": "synthetic non-timeout communicate failure", "child_survived_cleanup": true, "pid": 81668, "returncode": null}
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "<string>", line 27, in <module>
PermissionError: [Errno 1] Operation not permitted

exec
/bin/zsh -lc 'ps -p 81668 -o pid=,ppid=,pgid=,stat=,command= || true
kill -KILL 81668 2>/dev/null || true
ps -p 81668 -o pid=,ppid=,pgid=,stat=,command= || true' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
zsh:1: operation not permitted: ps
zsh:3: operation not permitted: ps

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import os; pid=81668
try: os.kill(pid,0)
except ProcessLookupError: print(\"gone\")
except PermissionError: print(\"permission-denied\")
else: print(\"alive\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
gone

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '270,315p' && nl -ba tests/fixtures/renderer_packs/raw_command/requests/render.json | sed -n '17,30p' && nl -ba tests/fixtures/renderer_packs/raw_command/requests/support.json | sed -n '17,30p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   270	        + struct.pack(">H", len(pps))
   271	        + pps
   272	    )
   273	    visual = (
   274	        b"\x00" * 6
   275	        + struct.pack(">H", 1)             # data_reference_index
   276	        + struct.pack(">HH", 0, 0)
   277	        + b"\x00" * 12
   278	        + struct.pack(">HH", WIDTH, HEIGHT)
   279	        + struct.pack(">II", 0x00480000, 0x00480000)  # 72 dpi
   280	        + struct.pack(">I", 0)
   281	        + struct.pack(">H", 1)             # frame_count
   282	        + b"RawCommand\x00" + b"\x00" * 21  # compressorname (32 bytes)
   283	        + struct.pack(">Hh", 24, -1)       # depth 24, pre_defined -1
   284	    )
   285	    return _box(b"avc1", visual + _box(b"avcC", avcc))
   286	
   287	
   288	def _sowt_entry() -> bytes:
   289	    wave = _box(
   290	        b"wave",
   291	        _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
   292	    )
   293	    audio = (
   294	        b"\x00" * 6
   295	        + struct.pack(">H", 1)             # data_reference_index
   296	        + struct.pack(">HH", 0, 0)
   297	        + struct.pack(">I", 0)             # vendor
   298	        + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
   299	        + struct.pack(">HH", 0, 0)         # compressionid, packetsize
   300	        + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
   301	    )
   302	    return _box(b"sowt", audio + wave)
   303	
   304	
   305	def _sample_tables(
   306	    *,
   307	    video_frames: int,
   308	    video_sizes: list[int],
   309	    video_chunk_offset: int,
   310	    audio_bytes: bytes,
   311	    audio_samples: int,
   312	    audio_chunk_offset: int,
   313	) -> bytes:
   314	    stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
   315	    stts_v = _fullbox(
    17	    "fps_rational": [24, 1],
    18	    "time_base": [1, 12288],
    19	    "container": "mp4",
    20	    "video_codec": "h264",
    21	    "video_profile": null,
    22	    "video_level": null,
    23	    "pixel_format": "yuv420p",
    24	    "audio_codec": "sowt",
    25	    "audio_sample_rate": 48000,
    26	    "audio_channel_layout": "stereo",
    27	    "duration_tolerance": 1
    28	  },
    29	  "backend_config": {
    30	    "raw_command.renderer": {
    17	    "fps_rational": [24, 1],
    18	    "time_base": [1, 12288],
    19	    "container": "mp4",
    20	    "video_codec": "h264",
    21	    "video_profile": null,
    22	    "video_level": null,
    23	    "pixel_format": "yuv420p",
    24	    "audio_codec": "sowt",
    25	    "audio_sample_rate": 48000,
    26	    "audio_channel_layout": "stereo",
    27	    "duration_tolerance": 1
    28	  },
    29	  "backend_config": {
    30	    "raw_command.renderer": {

codex
- Transport cleanup can still leak a process group on non-timeout `communicate()` failures, and repeated `KeyboardInterrupt` can escape polling/drain paths before reap. A SIGTERM-ignoring child survived direct injection. [transport.py:237](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:237), [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461)

- The raw fixture still fails strict profile validation. The request declares `sowt` while the result declares `pcm_s16le`; fresh ffprobe also reports no `channel_layout`, producing `audio_profile_mismatch`/`incomplete_probe`. [render.json:24](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/requests/render.json:24), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481), [artifacts.py:469](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:469)

- `support` validation remains non-strict: `True` and `1.0` pass as schema version `1`, while non-object JSON raises uncaught `AttributeError` instead of returning `protocol`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)

- Production publishing still follows output symlinks because `render()` resolves `out_path` before the new unresolved-path guard sees it; replacement then targets the symlink destination. [run.py:1459](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1459), [publication.py:282](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:282)

- Previous-output cleanup checks only the raw video path. It resolves sidecars first, so a sidecar symlink remains invisible and cleanup can unlink its resolved target and the video. [publication.py:185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:185), [publication.py:219](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:219), [publication.py:248](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:248)
tokens used
282,690
- Transport cleanup can still leak a process group on non-timeout `communicate()` failures, and repeated `KeyboardInterrupt` can escape polling/drain paths before reap. A SIGTERM-ignoring child survived direct injection. [transport.py:237](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:237), [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461)

- The raw fixture still fails strict profile validation. The request declares `sowt` while the result declares `pcm_s16le`; fresh ffprobe also reports no `channel_layout`, producing `audio_profile_mismatch`/`incomplete_probe`. [render.json:24](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/requests/render.json:24), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481), [artifacts.py:469](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:469)

- `support` validation remains non-strict: `True` and `1.0` pass as schema version `1`, while non-object JSON raises uncaught `AttributeError` instead of returning `protocol`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)

- Production publishing still follows output symlinks because `render()` resolves `out_path` before the new unresolved-path guard sees it; replacement then targets the symlink destination. [run.py:1459](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1459), [publication.py:282](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:282)

- Previous-output cleanup checks only the raw video path. It resolves sidecars first, so a sidecar symlink remains invisible and cleanup can unlink its resolved target and the video. [publication.py:185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:185), [publication.py:219](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:219), [publication.py:248](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:248)

exec
/bin/zsh -lc "git diff --unified=100 5231a233..7f7c25d5 -- astrid/core/media.py astrid/core/rendering/publication.py astrid/core/rendering/transport.py astrid/packs/rendering/executors/render/run.py tests/core/rendering/test_transport.py tests/fixtures/renderer_packs/raw_command/backend.py tests/fixtures/renderer_packs/raw_command/requests/render.json
rg -n \"Batch 2|acceptance|transport|publication|raw command|fixture|artifact\" .oracle/tasklist.md
rg -n \"__pycache__|\\.pyc\" .gitignore '**/.gitignore' 2>/dev/null" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/media.py b/astrid/core/media.py
index cfc72297..e7c6a92d 100644
--- a/astrid/core/media.py
+++ b/astrid/core/media.py
@@ -121,201 +121,214 @@ def _nonempty_string(value: Any) -> str | None:
     if not isinstance(value, str) or not value.strip():
         return None
     return value
 
 
 def _int_or_none(value: Any, *, minimum: int = 0) -> int | None:
     try:
         parsed = int(value)
     except (TypeError, ValueError):
         return None
     return parsed if parsed >= minimum else None
 
 
 def _container_from_format(format_name: str | None, file_path: str | Path) -> str | None:
     if format_name is None:
         return None
     names = {part.strip().lower() for part in format_name.split(",") if part.strip()}
     suffix = Path(file_path).suffix.lower().lstrip(".")
     if suffix in names:
         return suffix
     if "mp4" in names:
         return "mp4"
     if "webm" in names:
         return "webm"
     if "matroska" in names:
         return "matroska"
     if "mov" in names:
         return "mov"
     return sorted(names)[0] if names else None
 
 
 def _parse_ffprobe_payload(data: dict[str, Any], file_path: str | Path) -> MediaProbe:
     probe = MediaProbe(_raw=data)
 
     fmt = data.get("format", {})
     if not isinstance(fmt, Mapping):
         fmt = {}
     probe.format_name = _nonempty_string(fmt.get("format_name"))
     probe.container = _container_from_format(probe.format_name, file_path)
 
     duration_value = fmt.get("duration")
     probe.duration_rational = _duration_rational(duration_value)
     if probe.duration_rational is not None:
         probe.duration_seconds = float(Fraction(*probe.duration_rational))
 
     streams = data.get("streams", [])
     if not isinstance(streams, list):
         streams = []
 
     video_stream: Mapping[str, Any] | None = None
     audio_stream: Mapping[str, Any] | None = None
     for stream in streams:
         if not isinstance(stream, Mapping):
             continue
         stream_type = stream.get("codec_type")
         if stream_type == "video" and video_stream is None:
             disposition = stream.get("disposition")
             attached_picture = (
                 isinstance(disposition, Mapping)
                 and disposition.get("attached_pic") in {1, True, "1"}
             )
             if not attached_picture:
                 video_stream = stream
         elif stream_type == "audio" and audio_stream is None:
             audio_stream = stream
 
     probe.video_stream_present = video_stream is not None
     probe.audio_stream_present = audio_stream is not None
 
     if video_stream is not None:
         probe.width = _int_or_none(video_stream.get("width"), minimum=1)
         probe.height = _int_or_none(video_stream.get("height"), minimum=1)
         if probe.width is not None and probe.height is not None:
             probe.resolution = f"{probe.width}x{probe.height}"
 
         fps_value = video_stream.get("avg_frame_rate")
         fps_rational = _positive_rational(fps_value)
         if fps_rational is None:
             fps_rational = _positive_rational(video_stream.get("r_frame_rate"))
         probe.fps_rational = fps_rational
         if fps_rational is not None:
             probe.fps = float(Fraction(*fps_rational))
 
         probe.time_base = _positive_rational(video_stream.get("time_base"))
         probe.video_codec = _nonempty_string(video_stream.get("codec_name"))
         probe.video_profile = _nonempty_string(video_stream.get("profile"))
         level = video_stream.get("level")
         if level is not None and str(level).strip() not in {"", "-99"}:
             probe.video_level = str(level).strip()
         probe.pixel_format = _nonempty_string(video_stream.get("pix_fmt"))
 
         # Some containers omit format.duration while exposing stream.duration.
         if probe.duration_rational is None:
             probe.duration_rational = _duration_rational(video_stream.get("duration"))
             if probe.duration_rational is not None:
                 probe.duration_seconds = float(Fraction(*probe.duration_rational))
 
     if audio_stream is not None:
         probe.audio_codec = _nonempty_string(audio_stream.get("codec_name"))
         probe.audio_sample_rate = _int_or_none(audio_stream.get("sample_rate"), minimum=1)
-        probe.audio_channel_layout = _nonempty_string(audio_stream.get("channel_layout"))
+        probe.audio_channel_layout = _nonempty_string(
+            audio_stream.get("channel_layout")
+        )
+        # Some containers (e.g. QuickTime sowt) report channel counts without
+        # a channel_layout; derive the standard layout so strict profile
+        # validation can still compare audio placement.
+        if probe.audio_channel_layout is None:
+            channels = _int_or_none(audio_stream.get("channels"), minimum=1)
+            probe.audio_channel_layout = {
+                1: "mono",
+                2: "stereo",
+                6: "5.1",
+                8: "7.1",
+            }.get(channels or 0)
         if probe.duration_rational is None:
             probe.duration_rational = _duration_rational(audio_stream.get("duration"))
             if probe.duration_rational is not None:
                 probe.duration_seconds = float(Fraction(*probe.duration_rational))
 
     return probe
 
 
 def _ffprobe_metadata(
     file_path: str | Path,
     *,
     timeout: float,
     strict: bool,
 ) -> MediaProbe:
     ffprobe_exe = shutil.which("ffprobe")
     if ffprobe_exe is None:
         if strict:
             raise MediaProbeError("ffprobe is not available on PATH")
         return MediaProbe()
 
     try:
         proc = subprocess.run(
             [
                 ffprobe_exe,
                 "-v",
                 "quiet",
                 "-print_format",
                 "json",
                 "-show_format",
                 "-show_streams",
                 str(file_path),
             ],
             capture_output=True,
             text=True,
             timeout=timeout,
         )
         if proc.returncode != 0:
             if strict:
                 diagnostic = (proc.stderr or "").strip()
                 suffix = f": {diagnostic}" if diagnostic else ""
                 raise MediaProbeError(f"ffprobe failed with exit {proc.returncode}{suffix}")
             return MediaProbe()
         data = json.loads(proc.stdout)
         if not isinstance(data, dict):
             raise ValueError("ffprobe JSON root is not an object")
     except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
         if strict:
             raise MediaProbeError(f"ffprobe could not inspect {file_path}: {exc}") from exc
         return MediaProbe()
 
     try:
         return _parse_ffprobe_payload(data, file_path)
     except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
         if strict:
             raise MediaProbeError(
                 f"ffprobe returned malformed metadata for {file_path}: {exc}"
             ) from exc
         return MediaProbe()
 
 
 def ffprobe_metadata(
     file_path: str | Path,
     *,
     timeout: float = 30.0,
 ) -> MediaProbe:
     """Extract duration, fps, resolution, width, and height via ffprobe.
 
     Returns a :class:`MediaProbe` with best-effort fields populated.
     If ffprobe is not available or fails, all fields are ``None``.
     """
     return _ffprobe_metadata(file_path, timeout=timeout, strict=False)
 
 
 def ffprobe_metadata_strict(
     file_path: str | Path,
     *,
     timeout: float = 30.0,
 ) -> MediaProbe:
     """Return ffprobe metadata or raise :class:`MediaProbeError`.
 
     Unlike :func:`ffprobe_metadata`, this entry point never converts an
     unavailable binary, failed command, timeout, or malformed payload into an
     all-``None`` probe.  Callers still decide which streams and fields their
     particular artifact contract requires.
     """
 
     return _ffprobe_metadata(file_path, timeout=timeout, strict=True)
 
 
 # ---------------------------------------------------------------------------
 # Narrow duration probe (preserved for callers who only need seconds)
 # ---------------------------------------------------------------------------
 
 
 def ffprobe_duration_seconds(
     media_path: str | Path,
     *,
     runner: Runner = subprocess.run,
     env: Mapping[str, str] | None = None,
 ) -> float:
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index b261a09f..514dfa6c 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -119,209 +119,216 @@ def _validate_source_video(video_path: Path) -> None:
     if size <= 0:
         _invalid_video(
             video_path,
             reason="empty_artifact",
             message=f"rendered video is empty: {video_path}",
         )
 
 
 def read_committed_provenance(
     video_path: str | Path,
     *,
     sidecar_path: str | Path | None = None,
 ) -> dict[str, Any] | None:
     """Return provenance only when *video_path* and its marker form a valid pair.
 
     This check intentionally fails closed for missing, malformed, empty, or
     hash-mismatched pairs.  Callers can then re-render or leave the orphan for
     conservative recovery without mistaking it for a successful publication.
     """
 
     video = _resolved(video_path)
     sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
     try:
         video_unresolved = Path(video_path).expanduser()
         sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
         if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
             return None
         if video.is_symlink() or sidecar.is_symlink():
             return None
         if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
             return None
         payload = json.loads(sidecar.read_text(encoding="utf-8"))
     except (OSError, ValueError, TypeError, json.JSONDecodeError):
         return None
     if not isinstance(payload, dict):
         return None
     recorded_output = payload.get("output")
     if not isinstance(recorded_output, str):
         return None
     try:
         recorded_output_path = _resolved(recorded_output)
     except (OSError, RuntimeError, ValueError):
         return None
     if recorded_output_path != video:
         return None
     recorded_sha256 = payload.get("sha256")
     if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
         return None
     try:
         if sha256_file(video) != recorded_sha256:
             return None
     except OSError:
         return None
     return payload
 
 
 def is_render_result_committed(
     video_path: str | Path,
     *,
     sidecar_path: str | Path | None = None,
 ) -> bool:
     """Return whether the video-plus-sidecar pair is committed."""
 
     return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
 
 
 def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
     if isinstance(candidate, Mapping):
         raw_video = candidate.get("out_path", candidate.get("output"))
         raw_sidecar = candidate.get("sidecar_path", candidate.get("sidecar"))
         if raw_video is None:
             return None
         video = _resolved(raw_video)
         return video, _resolved(raw_sidecar or _default_sidecar_path(video))
     if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
         video = _resolved(candidate[0])
         return video, _resolved(candidate[1])
     if isinstance(candidate, (str, os.PathLike)):
         video = _resolved(candidate)
         return video, _resolved(_default_sidecar_path(video))
     return None
 
 
 def _delete_previous_outputs(
     previous_outputs: Iterable[object],
     *,
     live_output: Path,
     timeline: object,
 ) -> None:
     if not isinstance(timeline, str):
         return
     seen: set[Path] = set()
     for candidate in previous_outputs:
         try:
             pair = _previous_pair(candidate)
         except (OSError, RuntimeError, TypeError, ValueError):
             continue
         if pair is None:
             continue
         video, sidecar = pair
-        # Never delete through a symlink: the raw candidate path must not be
-        # a link (the resolved pair may point elsewhere entirely).
+        # Never delete through a symlink: neither the raw video nor the raw
+        # sidecar path may be a link (the resolved pair may point elsewhere).
         raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
+        raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
         try:
             raw_path = Path(raw_candidate).expanduser()
             if raw_path.is_symlink():
                 continue
         except (OSError, TypeError):
             continue
+        if raw_sidecar_candidate is not None:
+            try:
+                if Path(raw_sidecar_candidate).expanduser().is_symlink():
+                    continue
+            except (OSError, TypeError):
+                continue
         if video == live_output or video in seen:
             continue
         seen.add(video)
 
         # Never wait while holding the live output lock.  Two concurrent
         # publications for sibling outputs can otherwise deadlock while each
         # tries to clean the other, and a locked candidate is by definition a
         # live render that cleanup must preserve.
         candidate_lock = _lock_for(video)
         try:
             candidate_lock.acquire(timeout=0)
         except (Timeout, OSError):
             continue
         try:
             provenance = read_committed_provenance(video, sidecar_path=sidecar)
             if provenance is None or provenance.get("timeline") != timeline:
                 continue
             try:
                 # The marker disappears first.  A crash or failure between
                 # these unlinks leaves an orphan, never a false committed pair.
                 sidecar.unlink()
             except (FileNotFoundError, OSError):
                 continue
             try:
                 video.unlink()
             except (FileNotFoundError, OSError):
                 pass
         finally:
             candidate_lock.release()
 
 
 def publish_render_result(
     video_path: str | Path,
     provenance_payload: Mapping[str, Any],
     *,
     out_path: str | Path,
     sidecar_path: str | Path,
     previous_outputs: Iterable[object] = (),
 ) -> Path:
     """Publish one video and atomically commit its hashed provenance marker.
 
     The source video is validated before any destination mutation.  Under the
     per-output lock an old marker is invalidated, the video is moved into
     place with :func:`os.replace`, and the complete sidecar is written
     atomically last.  A sidecar-write failure therefore leaves a detectable,
     recoverable orphan video and is propagated to the caller.
     """
 
     if not isinstance(provenance_payload, Mapping):
         raise TypeError("provenance_payload must be a mapping")
 
     source = _resolved(video_path)
     output = _resolved(out_path)
     sidecar = _resolved(sidecar_path)
     source_unresolved = Path(video_path).expanduser()
     output_unresolved = Path(out_path).expanduser()
     sidecar_unresolved = Path(sidecar_path).expanduser()
     if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
         raise_invalid_artifact_error(
             backend=_BACKEND,
             message="publication paths must not be symbolic links",
             recovery_command=_RECOVERY,
         )
     _validate_source_video(source)
 
     output.parent.mkdir(parents=True, exist_ok=True)
     sidecar.parent.mkdir(parents=True, exist_ok=True)
     with _lock_for(output):
         # Validate again after waiting for the lock so a moved or truncated
         # staging artifact can never be reported as successfully published.
         _validate_source_video(source)
 
         # Invalidate the previous marker BEFORE the first destination
         # mutation: a crash can then leave an orphan video (recoverable) but
         # can never leave a stale marker claiming the new bytes are committed.
         sidecar.unlink(missing_ok=True)
         os.replace(source, output)
         digest = sha256_file(output)
         committed_payload = dict(provenance_payload)
         committed_payload["output"] = str(output)
         committed_payload["sha256"] = digest
         write_json_atomic(sidecar, committed_payload)
 
         # Cleanup happens only after the new pair is committed and while its
         # lock remains held.  Candidate locks are non-blocking (see above).
         _delete_previous_outputs(
             previous_outputs,
             live_output=output,
             timeline=committed_payload.get("timeline"),
         )
 
         # Do not report success unless the bytes and marker we just wrote are
         # still a complete pair under the same lock.
         if read_committed_provenance(output, sidecar_path=sidecar) is None:
             _invalid_video(
                 output,
                 reason="uncommitted_artifact",
                 message=f"published video has no valid provenance commit marker: {output}",
             )
     return output
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index 6085a07c..3ae65c8f 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -388,241 +388,258 @@ def _resolve_executable(
         resolved = shutil.which(
             executable,
             path=child_env.get("PATH", os.defpath),
         )
 
     if resolved is None:
         raise_binary_missing_error(
             backend=backend,
             message=f"required renderer executable was not found: {executable}",
             recovery_command=f"install {executable} and retry",
             details={"binary": executable, "cwd": str(cwd)},
         )
     return resolved
 
 
 def _is_executable_file(path: Path) -> bool:
     try:
         mode = path.stat().st_mode
     except OSError:
         return False
     return stat.S_ISREG(mode) and os.access(path, os.X_OK)
 
 
 def _remove_stale_result(result_path: Path, *, backend: str) -> None:
     if not os.path.lexists(result_path):
         return
     try:
         if result_path.is_dir() and not result_path.is_symlink():
             raise IsADirectoryError(str(result_path))
         result_path.unlink()
     except OSError as exc:
         raise_invalid_artifact_error(
             backend=backend,
             message=f"cannot prepare authoritative result path: {result_path}",
             details={
                 "result_path": str(result_path),
                 "error_type": type(exc).__name__,
             },
         )
 
 
 def _signal_process_group(process: subprocess.Popen[str], sig: int) -> None:
     if hasattr(os, "killpg"):
         try:
             # start_new_session=True makes the child's PID its process-group ID.
             os.killpg(process.pid, sig)
             return
         except ProcessLookupError:
             return
         except (PermissionError, OSError):
             pass
     if process.poll() is not None:
         return
     try:
         process.send_signal(sig)
     except OSError:
         pass
 
 
 def _process_group_exists(process: subprocess.Popen[str]) -> bool:
     if hasattr(os, "killpg"):
         try:
             os.killpg(process.pid, 0)
         except ProcessLookupError:
             return False
         except PermissionError:
             return True
         except OSError:
             return process.poll() is None
         return True
     return process.poll() is None
 
 
 def _terminate_process_group(
     process: subprocess.Popen[str], *, grace: float
 ) -> tuple[str, str]:
     """Terminate the complete child group and reap the direct child."""
 
     _signal_process_group(process, signal.SIGTERM)
     deadline = time.monotonic() + grace
     captured: tuple[str, str] | None = None
     try:
         captured = process.communicate(timeout=grace)
     except (subprocess.TimeoutExpired, KeyboardInterrupt):
         captured = None
         # Interruption during the grace window must not abandon the group:
         # escalate to SIGKILL right away and reap in the loop below.
         try:
             _signal_process_group(process, signal.SIGKILL)
         except OSError:
             pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
+        drain_deadline = time.monotonic() + max(grace, 2.0)
         while True:
             try:
                 captured = process.communicate()
                 break
             except KeyboardInterrupt:
-                _signal_process_group(process, signal.SIGKILL)
+                try:
+                    _signal_process_group(process, signal.SIGKILL)
+                except (OSError, PermissionError):
+                    pass
+                if time.monotonic() > drain_deadline:
+                    process.kill()
+                    captured = process.communicate()
+                    break
                 continue
     elif captured is None:
         # ``poll`` may have reaped the child while checking the fallback path.
         # Its pipes still need to be drained, and communicate is safe here.
         captured = process.communicate()
 
     if killed_group:
         _wait_for_group_exit(process, timeout=grace)
 
     stdout, stderr = captured or ("", "")
     return stdout or "", stderr or ""
 
 
 def _terminate_leftover_group(
     process: subprocess.Popen[str], *, grace: float
 ) -> None:
     """Clean up descendants that outlived an otherwise completed command."""
 
     if not _process_group_exists(process):
         return
     _signal_process_group(process, signal.SIGTERM)
     deadline = time.monotonic() + grace
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
     if _process_group_exists(process):
         _signal_process_group(process, signal.SIGKILL)
         _wait_for_group_exit(process, timeout=grace)
 
 
 def _wait_for_group_exit(
     process: subprocess.Popen[str], *, timeout: float
 ) -> None:
     deadline = time.monotonic() + timeout
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+    # A group that ignores SIGKILL cannot exist on POSIX; if it somehow
+    # survives the grace window, keep SIGKILLing until it is gone so cleanup
+    # never returns with a live orphan.
+    while _process_group_exists(process):
+        try:
+            _signal_process_group(process, signal.SIGKILL)
+        except (OSError, PermissionError):
+            break
+        time.sleep(0.01)
 
 
 def _secret_environment_values(
     host: Mapping[str, str], overlay: Mapping[str, str] | None
 ) -> tuple[str, ...]:
     values: set[str] = set()
     for source in (host, overlay or {}):
         for key, value in source.items():
             text = str(value)
             if _SECRET_NAME_RE.search(str(key)) and len(text) >= 4:
                 values.add(text)
     return tuple(sorted(values, key=len, reverse=True))
 
 
 def _redact_log(value: str, *, secret_values: Sequence[str]) -> str:
     redacted = value.replace("\x00", "\ufffd")
     for secret in secret_values:
         redacted = redacted.replace(secret, "[redacted]")
     redacted = _AUTH_HEADER_RE.sub(
         lambda match: f"{match.group(1)}: [redacted]", redacted
     )
     redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
     redacted = _SECRET_QUERY_RE.sub(
         lambda match: f"{match.group(1)}[redacted]", redacted
     )
     redacted = _SECRET_ASSIGNMENT_RE.sub(
         lambda match: f"{match.group(1)}[redacted]", redacted
     )
     redacted = _SECRET_VALUE_RE.sub("[redacted]", redacted)
     if len(redacted) > _MAX_LOG_CHARS:
         redacted = redacted[:_MAX_LOG_CHARS] + "\n[truncated]"
     return redacted
 
 
 def _redacted_logs(
     stdout: str,
     stderr: str,
     *,
     secret_values: Sequence[str],
 ) -> dict[str, str]:
     return {
         "stdout": _redact_log(stdout or "", secret_values=secret_values),
         "stderr": _redact_log(stderr or "", secret_values=secret_values),
     }
 
 
 def _read_result_file(
     result_path: Path,
     *,
     backend: str,
     logs: Mapping[str, str],
 ) -> Any:
     try:
         result_stat = result_path.lstat()
     except FileNotFoundError:
         raise_protocol_error(
             backend=backend,
             message=f"renderer did not write its authoritative result file: {result_path}",
             details={"result_path": str(result_path), **logs},
         )
     except OSError as exc:
         raise_invalid_artifact_error(
             backend=backend,
             message=f"cannot inspect renderer result file: {result_path}",
             details={
                 "result_path": str(result_path),
                 "error_type": type(exc).__name__,
                 **logs,
             },
         )
     if stat.S_ISLNK(result_stat.st_mode) or not stat.S_ISREG(result_stat.st_mode):
         raise_invalid_artifact_error(
             backend=backend,
             message=f"renderer result path is not a regular file: {result_path}",
             details={"result_path": str(result_path), **logs},
         )
     try:
         return json.loads(result_path.read_text(encoding="utf-8"))
     except (json.JSONDecodeError, UnicodeDecodeError) as exc:
         raise_protocol_error(
             backend=backend,
             message=f"renderer wrote malformed result JSON: {exc}",
             details={
                 "result_path": str(result_path),
                 "error_type": type(exc).__name__,
                 **logs,
             },
         )
     except OSError as exc:
         raise_invalid_artifact_error(
             backend=backend,
             message=f"cannot read renderer result file: {result_path}",
             details={
                 "result_path": str(result_path),
                 "error_type": type(exc).__name__,
                 **logs,
             },
         )
 
 
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index 3f294f01..c42443a4 100644
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -1359,182 +1359,182 @@ def _render_with_publication_context(
                 TemporaryDirectory(
                     prefix=f".{out_path.name}.publication-",
                     dir=str(out_path.parent),
                 )
             )
             staged_video = Path(publication_tmp) / out_path.name
             props_path.write_text(json.dumps(merged_props), encoding="utf-8")
             # Build the Remotion launch env from the canonical safe base plus the
             # Astrid runtime markers it propagates. We do NOT spread os.environ:
             # the only Node/Remotion additions are the safe-base PATH/HOME/TMPDIR
             # that npx + the headless renderer need, and any caller-provided
             # composition source override declared as a build-tool variable.
             remotion_env_additions: dict[str, str] = {}
             composition_src = (
                 project_dir / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
             )
             if composition_src.is_dir():
                 remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
             result = subprocess.run(
                 [
                     "npx",
                     "remotion",
                     "render",
                     composition_id,
                     "--props",
                     str(props_path),
                     "--output",
                     str(staged_video),
                     "--allow-html-in-canvas",
                 ],
                 cwd=str(project_dir),
                 env=build_child_subprocess_env(explicit_env=remotion_env_additions),
                 capture_output=True,
                 check=False,
                 text=True,
             )
             if result.returncode != 0:
                 stderr_tail = _stderr_tail(result.stderr)
                 message = f"Remotion render failed with exit code {result.returncode}"
                 if stderr_tail:
                     message = f"{message}\n{stderr_tail}"
                 raise RuntimeError(message)
             provenance = _render_provenance_payload(
                 out_path,
                 engine="remotion",
                 timeline_path=timeline_path,
                 assets_path=assets_path,
                 project_dir=project_dir,
                 composition_id=composition_id,
                 theme_path=theme_path,
                 active_theme=theme_for_props,
                 registry_state=registry_state,
                 stage_summary=stage_summary,
             )
             output = publish_render_result(
                 staged_video,
                 provenance,
                 out_path=out_path,
                 sidecar_path=_render_provenance_sidecar_path(out_path),
                 previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
             )
         finally:
             props_path.unlink(missing_ok=True)
             shutil.rmtree(staged_public_root, ignore_errors=True)
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_remotion")
         assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_remotion")
         render_id = audit.register_asset(
             kind="render",
             path=output,
             label="Rendered video",
             parents=[timeline_id, assets_id],
             stage="render_remotion",
             metadata={"composition": composition_id},
         )
         audit.register_node(
             stage="render_remotion",
             label="Render Remotion timeline",
             parents=[timeline_id, assets_id],
             outputs=[render_id],
             metadata={"composition": composition_id, "project_dir": str(project_dir)},
         )
     return output
 
 
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
 ) -> Path:
     """Render privately and publish one locked video-plus-sidecar pair."""
 
-    out_path = out_path.resolve()
+    out_path = Path(out_path)
     previous_outputs = (
         ()
         if keep_previous_renders
         else _previous_render_outputs_for_timeline(out_path, timeline_path)
     )
     publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
     try:
         return _render_with_publication_context(
             timeline_path,
             assets_path,
             out_path,
             engine=engine,
             project_dir=project_dir,
             composition_id=composition_id,
             theme_path=theme_path,
             min_free_gb=min_free_gb,
         )
     finally:
         _PUBLICATION_PREVIOUS_OUTPUTS.reset(publication_token)
 
 
 def main(argv: Sequence[str] | None = None) -> int:
     parser = argparse.ArgumentParser()
     parser.add_argument("--timeline", type=Path, required=True)
     parser.add_argument("--assets", type=Path)
     parser.add_argument("--out", type=Path, required=True)
     parser.add_argument("--engine", choices=("remotion", "ffmpeg", "hybrid"), default="remotion")
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
         if args.assets is None:
             with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
                 assets_path = Path(tmp_text) / "hype.assets.json"
                 _write_empty_asset_registry(assets_path)
                 output = render(
                     args.timeline,
                     assets_path,
                     args.out,
                     engine=args.engine,
                     project_dir=args.project_dir,
                     composition_id=args.composition,
                     theme_path=args.theme,
                     min_free_gb=args.min_free_gb,
                     keep_previous_renders=args.keep_previous_renders,
                 )
         else:
             output = render(
                 args.timeline,
                 args.assets,
                 args.out,
                 engine=args.engine,
                 project_dir=args.project_dir,
                 composition_id=args.composition,
                 theme_path=args.theme,
                 min_free_gb=args.min_free_gb,
                 keep_previous_renders=args.keep_previous_renders,
             )
     except Exception as exc:  # pragma: no cover - CLI path
         print(str(exc), file=sys.stderr)
         return 1
     print(output)
     return 0
 
 
 if __name__ == "__main__":
     raise SystemExit(main())
diff --git a/tests/core/rendering/test_transport.py b/tests/core/rendering/test_transport.py
index 5359a13a..5e59b64a 100644
--- a/tests/core/rendering/test_transport.py
+++ b/tests/core/rendering/test_transport.py
@@ -76,201 +76,212 @@ def _assert_pid_disappears(pid: int, *, timeout: float = 3) -> None:
 def _tree_request(tmp_path: Path) -> tuple[dict[str, Any], Path, Path]:
     parent_pid_path = tmp_path / "parent.pid"
     child_pid_path = tmp_path / "child.pid"
     return (
         {
             "action": "sleep-tree",
             "ignore_term": True,
             "parent_pid_path": str(parent_pid_path),
             "child_pid_path": str(child_pid_path),
         },
         parent_pid_path,
         child_pid_path,
     )
 
 
 def test_successful_render_uses_authoritative_result_file(tmp_path: Path) -> None:
     transport, result = _run(
         tmp_path,
         {"action": "result", "payload": _wire_fixture("result.json")},
     )
 
     assert isinstance(result, RenderResult)
     assert result.video.path == "outputs/visual.mp4"
     assert transport.last_logs == {"stdout": "", "stderr": ""}
 
 
 @pytest.mark.parametrize(
     ("verb", "fixture_name", "backend", "result_type"),
     [
         ("support", "support.json", "acme.visual", SupportReport),
         ("plan", "plan.json", "rendering.legacy_hybrid", RenderPlan),
         ("finalize", "result.json", "rendering.ffmpeg-finalizer", RenderResult),
     ],
 )
 def test_each_protocol_verb_uses_its_frozen_result_dto(
     tmp_path: Path,
     verb: str,
     fixture_name: str,
     backend: str,
     result_type: type,
 ) -> None:
     _, result = _run(
         tmp_path,
         {"action": "result", "payload": _wire_fixture(fixture_name)},
         verb=verb,
         backend=backend,
     )
 
     assert isinstance(result, result_type)
 
 
 def test_missing_binary_is_renderer_qualified(tmp_path: Path) -> None:
     request_path = _request(tmp_path, {"action": "absent"})
 
     with pytest.raises(RendererBinaryMissingError) as caught:
         CommandTransport(RENDERER_ID).run(
             "render",
             ["astrid-renderer-that-does-not-exist"],
             request_path=request_path,
             result_path=tmp_path / "result.json",
             cwd=FIXTURE_DIR,
             timeout=1,
         )
 
     assert caught.value.error.kind == "binary_missing"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_nonzero_exit_is_internal_and_captures_both_streams(tmp_path: Path) -> None:
     with pytest.raises(RendererInternalError) as caught:
         _run(
             tmp_path,
             {
                 "action": "nonzero",
                 "returncode": 23,
                 "stdout": "renderer stdout",
                 "stderr": "renderer stderr",
             },
         )
 
     assert caught.value.error.kind == "internal"
     assert caught.value.error.backend == RENDERER_ID
     assert caught.value.details["returncode"] == 23
     assert "renderer stdout" in caught.value.details["stdout"]
     assert "renderer stderr" in caught.value.details["stderr"]
 
 
 def test_timeout_kills_process_group_and_reaps_direct_child(tmp_path: Path) -> None:
     payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
 
     with pytest.raises(RendererTimeoutError) as caught:
         _run(tmp_path, payload, timeout=0.5)
 
     parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
     child_pid = int(child_pid_path.read_text(encoding="utf-8"))
     assert caught.value.error.kind == "timeout"
     assert caught.value.error.backend == RENDERER_ID
     with pytest.raises(ChildProcessError):
         os.waitpid(parent_pid, os.WNOHANG)
     _assert_pid_disappears(parent_pid)
-    _assert_pid_disappears(child_pid)
+
+
+def test_sigterm_ignoring_child_is_escalated_and_reaped(tmp_path: Path) -> None:
+    """A child tree that ignores SIGTERM must still be SIGKILLed and reaped."""
+    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
+
+    with pytest.raises(RendererTimeoutError) as caught:
+        _run(tmp_path, payload, timeout=0.5)
+
+    assert caught.value.error.kind == "timeout"
+    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
+    _assert_pid_disappears(parent_pid)
 
 
 def test_sigint_kills_process_group_reaps_and_reraises(tmp_path: Path) -> None:
     payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
 
     def interrupt_when_started() -> None:
         deadline = time.monotonic() + 5
         while not child_pid_path.exists() and time.monotonic() < deadline:
             time.sleep(0.01)
         if child_pid_path.exists():
             os.kill(os.getpid(), signal.SIGINT)
 
     interrupter = threading.Thread(target=interrupt_when_started, daemon=True)
     interrupter.start()
     with pytest.raises(KeyboardInterrupt) as caught:
         _run(tmp_path, payload, timeout=10)
     interrupter.join(timeout=1)
 
     parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
     child_pid = int(child_pid_path.read_text(encoding="utf-8"))
     assert caught.value.renderer_error.kind == "interrupted"
     assert caught.value.renderer_error.backend == RENDERER_ID
     with pytest.raises(ChildProcessError):
         os.waitpid(parent_pid, os.WNOHANG)
     _assert_pid_disappears(parent_pid)
     _assert_pid_disappears(child_pid)
 
 
 def test_absent_result_file_is_protocol_failure(tmp_path: Path) -> None:
     with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "absent"})
 
     assert caught.value.error.kind == "protocol"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_malformed_result_json_is_protocol_failure(tmp_path: Path) -> None:
     with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "malformed"})
 
     assert caught.value.error.kind == "protocol"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_incompatible_result_version_is_protocol_failure(tmp_path: Path) -> None:
     payload = _wire_fixture("result.json")
     payload["schema_version"] = 2
 
     with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "result", "payload": payload})
 
     assert caught.value.error.kind == "protocol"
     assert caught.value.error.backend == RENDERER_ID
     assert caught.value.details["received"] == 2
 
 
 def test_success_logs_capture_and_redact_stdout_and_stderr(
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     secret = "transport-log-secret-value"
     monkeypatch.setenv("TRANSPORT_LOG_SECRET", secret)
 
     transport, result = _run(
         tmp_path,
         {
             "action": "result",
             "payload": _wire_fixture("result.json"),
             "stdout": "render complete",
             "stderr": f"OPENAI_API_KEY={secret}",
         },
     )
 
     assert isinstance(result, RenderResult)
     assert any("render complete" in log for log in result.logs)
     assert secret not in json.dumps(result.logs)
     assert "[redacted]" in transport.last_logs["stderr"]
 
 
 def test_environment_is_allowlisted_and_host_secrets_are_not_passed(
     tmp_path: Path,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     monkeypatch.setenv("TRANSPORT_HOST_SECRET_TOKEN", "must-not-reach-child")
 
     _, result = _run(
         tmp_path,
         {
             "action": "environment",
             "name": "TRANSPORT_HOST_SECRET_TOKEN",
             "safe_name": "LANG",
             "payload": _wire_fixture("result.json"),
         },
         env={
             "TRANSPORT_HOST_SECRET_TOKEN": "overlay-must-not-reach-child",
             "LANG": "transport-safe-locale",
         },
     )
 
     assert isinstance(result, RenderResult)
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 2910f543..37973595 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -202,370 +202,383 @@ def _fullbox(box_type: bytes, version_flags: int, payload: bytes) -> bytes:
     return struct.pack(">I4sI", 12 + len(payload), box_type, version_flags) + payload
 
 
 def _matrix() -> bytes:
     return _MATRIX
 
 
 def _ftyp() -> bytes:
     return (
         struct.pack(">I4sII", 32, b"ftyp", 0x69736F6D, 0x00000200)
         + b"isomiso2avc1mp41"
     )
 
 
 def _mvhd(duration: int) -> bytes:
     payload = (
         struct.pack(">IIII", 0, 0, 12288, duration)  # timescale = 12288
         + struct.pack(">I", 0x00010000)              # rate 1.0
         + struct.pack(">H", 0x0100)                  # volume 1.0
         + struct.pack(">H", 0)
         + struct.pack(">II", 0, 0)
         + _matrix()
         + b"\x00" * 24
         + struct.pack(">I", 3)                       # next_track_ID
     )
     return _fullbox(b"mvhd", 0, payload)
 
 
 def _tkhd(track_id: int, duration: int, volume: int, width: int, height: int) -> bytes:
     payload = (
         struct.pack(">II", 0, 0)
         + struct.pack(">I", track_id)
         + struct.pack(">I", 0)
         + struct.pack(">I", duration)
         + struct.pack(">II", 0, 0)
         + struct.pack(">Hh", 0, 0)
         + struct.pack(">H", volume)
         + struct.pack(">H", 0)
         + _matrix()
         + struct.pack(">II", width << 16, height << 16)
     )
     return _fullbox(b"tkhd", 0x00000007, payload)
 
 
 def _mdhd(timescale: int, duration: int) -> bytes:
     payload = (
         struct.pack(">IIII", 0, 0, timescale, duration)
         + struct.pack(">HH", 0x55C4, 0)  # language "und"
     )
     return _fullbox(b"mdhd", 0, payload)
 
 
 def _hdlr(handler: bytes, name: bytes) -> bytes:
     payload = struct.pack(">I", 0) + handler + b"\x00" * 12 + name + b"\x00"
     return _fullbox(b"hdlr", 0, payload)
 
 
 def _dinf() -> bytes:
     dref = _fullbox(b"dref", 0, struct.pack(">I", 1) + _fullbox(b"url ", 1, b""))
     return _box(b"dinf", dref)
 
 
 def _avc1_entry(sps: bytes, pps: bytes) -> bytes:
     avcc = (
         bytes([1, 66, 0xC0, 40, 0xFF, 0xE1])
         + struct.pack(">H", len(sps))
         + sps
         + bytes([1])
         + struct.pack(">H", len(pps))
         + pps
     )
     visual = (
         b"\x00" * 6
         + struct.pack(">H", 1)             # data_reference_index
         + struct.pack(">HH", 0, 0)
         + b"\x00" * 12
         + struct.pack(">HH", WIDTH, HEIGHT)
         + struct.pack(">II", 0x00480000, 0x00480000)  # 72 dpi
         + struct.pack(">I", 0)
         + struct.pack(">H", 1)             # frame_count
         + b"RawCommand\x00" + b"\x00" * 21  # compressorname (32 bytes)
         + struct.pack(">Hh", 24, -1)       # depth 24, pre_defined -1
     )
     return _box(b"avc1", visual + _box(b"avcC", avcc))
 
 
 def _sowt_entry() -> bytes:
     wave = _box(
         b"wave",
         _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
     )
     audio = (
         b"\x00" * 6
         + struct.pack(">H", 1)             # data_reference_index
         + struct.pack(">HH", 0, 0)
         + struct.pack(">I", 0)             # vendor
         + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
         + struct.pack(">HH", 0, 0)         # compressionid, packetsize
         + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
     )
-    return _box(b"sowt", audio + wave)
+    # QuickTime channel layout atom so ffprobe reports a concrete
+    # channel_layout (stereo = layout tag 3) instead of None.
+    chan = _box(
+        b"chan",
+        struct.pack(">I", 0)   # version/flags
+        + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)
+        + struct.pack(">I", 0),  # bitmap
+    )
+    return _box(b"sowt", audio + wave + chan)
 
 
 def _sample_tables(
     *,
     video_frames: int,
     video_sizes: list[int],
     video_chunk_offset: int,
     audio_bytes: bytes,
     audio_samples: int,
     audio_chunk_offset: int,
 ) -> bytes:
     stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
     stts_v = _fullbox(
         b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", video_frames, SAMPLES_PER_FRAME)
     )
     stsc_v = _fullbox(
         b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, video_frames, 1)
     )
     stsz_v = _fullbox(
         b"stsz", 0, struct.pack(">II", 0, video_frames)
         + b"".join(struct.pack(">I", size) for size in video_sizes)
     )
     stco_v = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", video_chunk_offset))
 
     stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
     stts_a = _fullbox(
         b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
     )
     stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
     stsz_a = _fullbox(
         b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
     )
     stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))
 
     video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
     audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
     return video_stbl, audio_stbl
 
 
 def _build_mp4(frames: int) -> bytes:
     """Return a deterministic MP4: `frames` H.264 IDR frames + PCM silence."""
     video_chunk = bytearray()
     video_sizes: list[int] = []
     for frame_index in range(frames):
         nal = _idr_slice_nal(frame_index)
         sample = struct.pack(">I", len(nal)) + nal
         video_chunk += sample
         video_sizes.append(len(sample))
     video_chunk = bytes(video_chunk)
 
     audio_samples = frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])
     audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))
 
     ftyp = _ftyp()
     video_chunk_offset = len(ftyp) + 8
     audio_chunk_offset = video_chunk_offset + len(video_chunk)
 
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
-    if request.get("schema_version") != 1:
+    version = request.get("schema_version")
+    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
         raise ValueError(
-            f"unsupported request schema_version {request.get('schema_version')!r}; expected 1"
+            f"unsupported request schema_version {version!r}; expected 1"
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
 
 
 def _support(result_path: Path) -> int:
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
     parser.add_argument("--request", required=True, help="absolute path to request JSON")
     parser.add_argument("--result", required=True, help="absolute path to result JSON")
     args = parser.parse_args(argv)
 
     request_path = Path(args.request)
     result_path = Path(args.result)
     try:
         request = json.loads(request_path.read_text(encoding="utf-8"))
+        if not isinstance(request, dict):
+            raise TypeError(
+                f"request must be a JSON object, got {type(request).__name__}"
+            )
     except Exception as exc:
         _write_error(
             result_path,
             "protocol",
             f"cannot read request JSON from {request_path}: {exc}",
             {"error_type": type(exc).__name__},
         )
         return 0
 
     if args.verb == "support":
         try:
             _validate_request(request)
         except ValueError as exc:
             _write_error(
                 result_path,
                 "protocol",
                 f"invalid support request: {exc}",
                 {"error_type": type(exc).__name__},
             )
             return 0
         return _support(result_path)
     if args.verb in ("plan", "finalize"):
         _write_error(
             result_path,
             "unsupported",
             f"{BACKEND_ID} only implements render and support",
             {"verb": args.verb},
         )
         return 0
     return _render(request, result_path, request_path)
 
 
 if __name__ == "__main__":
     raise SystemExit(main(sys.argv[1:]))
diff --git a/tests/fixtures/renderer_packs/raw_command/requests/render.json b/tests/fixtures/renderer_packs/raw_command/requests/render.json
index 41d98db2..ea881967 100644
--- a/tests/fixtures/renderer_packs/raw_command/requests/render.json
+++ b/tests/fixtures/renderer_packs/raw_command/requests/render.json
@@ -1,38 +1,47 @@
 {
   "schema_version": 1,
   "timeline_path": "timeline.json",
   "assets_registry_path": null,
   "output_name": "raw_command.mp4",
   "window": {
     "start_frame": 0,
     "end_frame": 48,
-    "fps_rational": [24, 1],
+    "fps_rational": [
+      24,
+      1
+    ],
     "source_range": null,
     "speed": 1.0
   },
   "audio": "rendered",
   "profile": {
     "width": 1920,
     "height": 1080,
-    "fps_rational": [24, 1],
-    "time_base": [1, 12288],
+    "fps_rational": [
+      24,
+      1
+    ],
+    "time_base": [
+      1,
+      12288
+    ],
     "container": "mp4",
     "video_codec": "h264",
     "video_profile": null,
     "video_level": null,
     "pixel_format": "yuv420p",
-    "audio_codec": "sowt",
+    "audio_codec": "pcm_s16le",
     "audio_sample_rate": 48000,
     "audio_channel_layout": "stereo",
     "duration_tolerance": 1
   },
   "backend_config": {
     "raw_command.renderer": {
       "mode": "solid"
     }
   },
   "metadata": {
     "fixture": "raw_command",
     "purpose": "T2.2 raw protocol fixture render"
   }
 }
5:**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
9:- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
11:- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
20:- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
23:- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
24:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
26:## Batch 2 — Command protocol and host-owned plumbing
28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
34:- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
45:- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
62:- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
85:- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
90:- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
97:**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.
105:- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
106:- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
107:- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
112:- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
113:- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
114:- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
116:- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
117:- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
118:- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
122:**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.
126:- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
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
166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
167:- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
172:- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
174:- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
.gitignore:20:__pycache__/
.gitignore:64:tests/fixtures/__pycache__/
.gitignore:68:tests/agentic/__pycache__/

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '1,320p'
nl -ba astrid/core/rendering/transport.py | sed -n '400,660p'
nl -ba tests/core/rendering/test_transport.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""Synchronous command transport for rendering protocol v1.
     2	
     3	The result file is the only wire response.  Standard output and standard error
     4	are retained as redacted diagnostics and are never parsed as protocol data.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import json
    10	import math
    11	import os
    12	import re
    13	import shutil
    14	import signal
    15	import stat
    16	import subprocess
    17	import time
    18	from collections.abc import Mapping, Sequence
    19	from dataclasses import replace
    20	from pathlib import Path
    21	from typing import Any, Literal, TypeAlias
    22	
    23	from astrid.core.subprocess_env import build_child_subprocess_env
    24	
    25	from .contracts import RenderPlan, RenderResult, RendererError, SupportReport
    26	from .errors import (
    27	    RendererException,
    28	    make_renderer_error,
    29	    raise_binary_missing_error,
    30	    raise_internal_error,
    31	    raise_invalid_artifact_error,
    32	    raise_protocol_error,
    33	    raise_renderer_error,
    34	    raise_structured_failure,
    35	    raise_timeout_error,
    36	)
    37	
    38	
    39	CommandVerb: TypeAlias = Literal["render", "support", "plan", "finalize"]
    40	CommandResult: TypeAlias = RenderResult | SupportReport | RenderPlan
    41	
    42	_VERBS = frozenset({"render", "support", "plan", "finalize"})
    43	_QUALIFIED_ID_RE = re.compile(
    44	    r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$"
    45	)
    46	_SECRET_NAME_RE = re.compile(
    47	    r"(^|_)(API[_-]?KEY|AUTH|CREDENTIAL|PASSWORD|SECRET|TOKEN)($|_)",
    48	    re.IGNORECASE,
    49	)
    50	_SECRET_ASSIGNMENT_RE = re.compile(
    51	    r"(?i)\b((?:api[_-]?key|auth(?:orization)?|credential|password|secret|token)"
    52	    r"\s*[:=]\s*)(?:[^\s,;]+)"
    53	)
    54	_SECRET_QUERY_RE = re.compile(
    55	    r"(?i)([?&](?:sig|signature|token|secret|access_token|api_key|apikey|key)=)"
    56	    r"[^&#\s]+"
    57	)
    58	_SECRET_VALUE_RE = re.compile(
    59	    r"(sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|"
    60	    r"hf_[A-Za-z0-9]{12,}|AIza[0-9A-Za-z_-]{12,})"
    61	)
    62	_AUTH_HEADER_RE = re.compile(
    63	    r"(?im)\b(authorization|proxy-authorization|cookie|set-cookie|x-api-key)"
    64	    r"\s*:\s*[^\r\n]+"
    65	)
    66	_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
    67	_MAX_LOG_CHARS = 64 * 1024
    68	_DEFAULT_TERMINATION_GRACE = 0.5
    69	
    70	
    71	class CommandTransport:
    72	    """Run one rendering protocol command in an owned process session.
    73	
    74	    A backend may be bound when the transport is constructed or supplied to
    75	    :meth:`run`.  ``env`` is an overlay on the host environment *before* the
    76	    canonical child-environment allowlist is applied; it is not an escape hatch
    77	    for passing arbitrary host variables.
    78	    """
    79	
    80	    def __init__(
    81	        self,
    82	        backend: str | None = None,
    83	        *,
    84	        termination_grace: float = _DEFAULT_TERMINATION_GRACE,
    85	    ) -> None:
    86	        if backend is not None:
    87	            _validate_backend(backend)
    88	        if (
    89	            isinstance(termination_grace, bool)
    90	            or not isinstance(termination_grace, (int, float))
    91	            or not math.isfinite(float(termination_grace))
    92	            or termination_grace <= 0
    93	        ):
    94	            raise ValueError("termination_grace must be a positive finite number")
    95	        self.backend = backend
    96	        self.termination_grace = float(termination_grace)
    97	        self.last_logs: dict[str, str] = {"stdout": "", "stderr": ""}
    98	
    99	    def run(
   100	        self,
   101	        verb: CommandVerb | str,
   102	        command: Sequence[str | os.PathLike[str]],
   103	        *,
   104	        backend: str | None = None,
   105	        request_path: str | os.PathLike[str],
   106	        result_path: str | os.PathLike[str],
   107	        cwd: str | os.PathLike[str],
   108	        env: Mapping[str, str] | None = None,
   109	        timeout: float | None = None,
   110	        required_binaries: Sequence[str | os.PathLike[str]] = (),
   111	    ) -> CommandResult:
   112	        """Execute a v1 verb and return its validated success DTO.
   113	
   114	        Failures raise the matching ``RendererException`` subtype.  A real
   115	        ``KeyboardInterrupt`` is re-raised after the whole child process group
   116	        has been terminated and the direct child reaped; the exception carries
   117	        ``renderer_error``/``error`` attributes with the structured
   118	        ``kind="interrupted"`` payload.
   119	        """
   120	
   121	        selected_backend = backend or self.backend
   122	        if selected_backend is None:
   123	            raise ValueError("a qualified backend id is required")
   124	        _validate_backend(selected_backend)
   125	        self.last_logs = {"stdout": "", "stderr": ""}
   126	
   127	        if verb not in _VERBS:
   128	            raise_protocol_error(
   129	                backend=selected_backend,
   130	                message=f"unsupported rendering protocol verb {verb!r}",
   131	                details={"received": verb, "supported": sorted(_VERBS)},
   132	            )
   133	        normalized_timeout = _validate_timeout(timeout, backend=selected_backend)
   134	        argv_prefix = _normalize_command(command, backend=selected_backend)
   135	        cwd_path = _resolve_cwd(cwd, backend=selected_backend)
   136	        request = _absolute_path(request_path)
   137	        result = _absolute_path(result_path)
   138	        if request == result:
   139	            raise_protocol_error(
   140	                backend=selected_backend,
   141	                message="request and result paths must be different",
   142	                details={"path": str(request)},
   143	            )
   144	
   145	        child_env = _build_environment(env)
   146	        argv_prefix[0] = _resolve_executable(
   147	            argv_prefix[0],
   148	            cwd=cwd_path,
   149	            child_env=child_env,
   150	            backend=selected_backend,
   151	        )
   152	        for binary in required_binaries:
   153	            binary_name = os.fspath(binary)
   154	            _resolve_executable(
   155	                binary_name,
   156	                cwd=cwd_path,
   157	                child_env=child_env,
   158	                backend=selected_backend,
   159	            )
   160	
   161	        _remove_stale_result(result, backend=selected_backend)
   162	        argv = [
   163	            *argv_prefix,
   164	            verb,
   165	            "--request",
   166	            str(request),
   167	            "--result",
   168	            str(result),
   169	        ]
   170	        secret_values = _secret_environment_values(os.environ, env)
   171	
   172	        try:
   173	            process = subprocess.Popen(
   174	                argv,
   175	                shell=False,
   176	                cwd=str(cwd_path),
   177	                env=child_env,
   178	                stdin=subprocess.DEVNULL,
   179	                stdout=subprocess.PIPE,
   180	                stderr=subprocess.PIPE,
   181	                text=True,
   182	                encoding="utf-8",
   183	                errors="replace",
   184	                start_new_session=True,
   185	            )
   186	        except (FileNotFoundError, PermissionError) as exc:
   187	            raise_binary_missing_error(
   188	                backend=selected_backend,
   189	                message=f"renderer executable is unavailable: {argv_prefix[0]}",
   190	                details={
   191	                    "binary": argv_prefix[0],
   192	                    "error_type": type(exc).__name__,
   193	                    **self.last_logs,
   194	                },
   195	            )
   196	        except OSError as exc:
   197	            raise_internal_error(
   198	                backend=selected_backend,
   199	                message=f"failed to start renderer command: {exc}",
   200	                details={"error_type": type(exc).__name__, **self.last_logs},
   201	            )
   202	
   203	        try:
   204	            stdout, stderr = process.communicate(timeout=normalized_timeout)
   205	        except subprocess.TimeoutExpired:
   206	            stdout, stderr = _terminate_process_group(
   207	                process, grace=self.termination_grace
   208	            )
   209	            logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
   210	            self.last_logs = logs
   211	            raise_timeout_error(
   212	                backend=selected_backend,
   213	                message=f"renderer command timed out after {normalized_timeout:g} seconds",
   214	                details={
   215	                    "timeout_seconds": normalized_timeout,
   216	                    "returncode": process.returncode,
   217	                    **logs,
   218	                },
   219	            )
   220	        except KeyboardInterrupt as exc:
   221	            stdout, stderr = _terminate_process_group(
   222	                process, grace=self.termination_grace
   223	            )
   224	            logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
   225	            self.last_logs = logs
   226	            error = make_renderer_error(
   227	                "interrupted",
   228	                backend=selected_backend,
   229	                message="renderer command was interrupted",
   230	                details={"returncode": process.returncode, **logs},
   231	            )
   232	            # Preserve normal SIGINT/exit-130 behavior while still making the
   233	            # frozen structured error available to an embedding caller.
   234	            exc.renderer_error = error  # type: ignore[attr-defined]
   235	            exc.error = error  # type: ignore[attr-defined]
   236	            raise
   237	        except Exception as exc:
   238	            # Any other post-spawn failure (including a defect in result
   239	            # parsing) must still terminate and reap the process group so no
   240	            # orphan is left behind.
   241	            try:
   242	                _terminate_process_group(process, grace=self.termination_grace)
   243	            except Exception:
   244	                pass
   245	            raise
   246	
   247	        logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
   248	        self.last_logs = logs
   249	        _terminate_leftover_group(process, grace=self.termination_grace)
   250	
   251	        if process.returncode != 0:
   252	            raise_internal_error(
   253	                backend=selected_backend,
   254	                message=f"renderer command exited with status {process.returncode}",
   255	                details={"returncode": process.returncode, **logs},
   256	            )
   257	
   258	        payload = _read_result_file(
   259	            result,
   260	            backend=selected_backend,
   261	            logs=logs,
   262	        )
   263	        return _parse_result(
   264	            verb,
   265	            payload,
   266	            backend=selected_backend,
   267	            logs=logs,
   268	        )
   269	
   270	
   271	def _validate_backend(backend: str) -> None:
   272	    if not isinstance(backend, str) or not _QUALIFIED_ID_RE.fullmatch(backend):
   273	        raise ValueError(
   274	            "backend must be a qualified id '<pack>.<name>' using lowercase "
   275	            "letters, digits, hyphens, or underscores"
   276	        )
   277	
   278	
   279	def _validate_timeout(timeout: float | None, *, backend: str) -> float | None:
   280	    if timeout is None:
   281	        return None
   282	    if (
   283	        isinstance(timeout, bool)
   284	        or not isinstance(timeout, (int, float))
   285	        or not math.isfinite(float(timeout))
   286	        or timeout <= 0
   287	    ):
   288	        raise_protocol_error(
   289	            backend=backend,
   290	            message="renderer timeout must be a positive finite number or null",
   291	            details={"received": repr(timeout)},
   292	        )
   293	    return float(timeout)
   294	
   295	
   296	def _normalize_command(
   297	    command: Sequence[str | os.PathLike[str]], *, backend: str
   298	) -> list[str]:
   299	    if isinstance(command, (str, bytes)) or not isinstance(command, Sequence):
   300	        raise_protocol_error(
   301	            backend=backend,
   302	            message="renderer command must be a non-empty argv sequence",
   303	        )
   304	    argv: list[str] = []
   305	    for index, value in enumerate(command):
   306	        if not isinstance(value, (str, os.PathLike)):
   307	            raise_protocol_error(
   308	                backend=backend,
   309	                message=f"renderer command argument {index} must be a path string",
   310	                details={"argument_index": index},
   311	            )
   312	        item = os.fspath(value)
   313	        if not item or "\x00" in item:
   314	            raise_protocol_error(
   315	                backend=backend,
   316	                message=f"renderer command argument {index} must be non-empty and contain no NUL",
   317	                details={"argument_index": index},
   318	            )
   319	        argv.append(item)
   320	    if not argv:
   400	    return resolved
   401	
   402	
   403	def _is_executable_file(path: Path) -> bool:
   404	    try:
   405	        mode = path.stat().st_mode
   406	    except OSError:
   407	        return False
   408	    return stat.S_ISREG(mode) and os.access(path, os.X_OK)
   409	
   410	
   411	def _remove_stale_result(result_path: Path, *, backend: str) -> None:
   412	    if not os.path.lexists(result_path):
   413	        return
   414	    try:
   415	        if result_path.is_dir() and not result_path.is_symlink():
   416	            raise IsADirectoryError(str(result_path))
   417	        result_path.unlink()
   418	    except OSError as exc:
   419	        raise_invalid_artifact_error(
   420	            backend=backend,
   421	            message=f"cannot prepare authoritative result path: {result_path}",
   422	            details={
   423	                "result_path": str(result_path),
   424	                "error_type": type(exc).__name__,
   425	            },
   426	        )
   427	
   428	
   429	def _signal_process_group(process: subprocess.Popen[str], sig: int) -> None:
   430	    if hasattr(os, "killpg"):
   431	        try:
   432	            # start_new_session=True makes the child's PID its process-group ID.
   433	            os.killpg(process.pid, sig)
   434	            return
   435	        except ProcessLookupError:
   436	            return
   437	        except (PermissionError, OSError):
   438	            pass
   439	    if process.poll() is not None:
   440	        return
   441	    try:
   442	        process.send_signal(sig)
   443	    except OSError:
   444	        pass
   445	
   446	
   447	def _process_group_exists(process: subprocess.Popen[str]) -> bool:
   448	    if hasattr(os, "killpg"):
   449	        try:
   450	            os.killpg(process.pid, 0)
   451	        except ProcessLookupError:
   452	            return False
   453	        except PermissionError:
   454	            return True
   455	        except OSError:
   456	            return process.poll() is None
   457	        return True
   458	    return process.poll() is None
   459	
   460	
   461	def _terminate_process_group(
   462	    process: subprocess.Popen[str], *, grace: float
   463	) -> tuple[str, str]:
   464	    """Terminate the complete child group and reap the direct child."""
   465	
   466	    _signal_process_group(process, signal.SIGTERM)
   467	    deadline = time.monotonic() + grace
   468	    captured: tuple[str, str] | None = None
   469	    try:
   470	        captured = process.communicate(timeout=grace)
   471	    except (subprocess.TimeoutExpired, KeyboardInterrupt):
   472	        captured = None
   473	        # Interruption during the grace window must not abandon the group:
   474	        # escalate to SIGKILL right away and reap in the loop below.
   475	        try:
   476	            _signal_process_group(process, signal.SIGKILL)
   477	        except OSError:
   478	            pass
   479	
   480	    while _process_group_exists(process) and time.monotonic() < deadline:
   481	        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   482	
   483	    killed_group = _process_group_exists(process)
   484	    if killed_group:
   485	        _signal_process_group(process, signal.SIGKILL)
   486	
   487	    if process.returncode is None:
   488	        drain_deadline = time.monotonic() + max(grace, 2.0)
   489	        while True:
   490	            try:
   491	                captured = process.communicate()
   492	                break
   493	            except KeyboardInterrupt:
   494	                try:
   495	                    _signal_process_group(process, signal.SIGKILL)
   496	                except (OSError, PermissionError):
   497	                    pass
   498	                if time.monotonic() > drain_deadline:
   499	                    process.kill()
   500	                    captured = process.communicate()
   501	                    break
   502	                continue
   503	    elif captured is None:
   504	        # ``poll`` may have reaped the child while checking the fallback path.
   505	        # Its pipes still need to be drained, and communicate is safe here.
   506	        captured = process.communicate()
   507	
   508	    if killed_group:
   509	        _wait_for_group_exit(process, timeout=grace)
   510	
   511	    stdout, stderr = captured or ("", "")
   512	    return stdout or "", stderr or ""
   513	
   514	
   515	def _terminate_leftover_group(
   516	    process: subprocess.Popen[str], *, grace: float
   517	) -> None:
   518	    """Clean up descendants that outlived an otherwise completed command."""
   519	
   520	    if not _process_group_exists(process):
   521	        return
   522	    _signal_process_group(process, signal.SIGTERM)
   523	    deadline = time.monotonic() + grace
   524	    while _process_group_exists(process) and time.monotonic() < deadline:
   525	        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   526	    if _process_group_exists(process):
   527	        _signal_process_group(process, signal.SIGKILL)
   528	        _wait_for_group_exit(process, timeout=grace)
   529	
   530	
   531	def _wait_for_group_exit(
   532	    process: subprocess.Popen[str], *, timeout: float
   533	) -> None:
   534	    deadline = time.monotonic() + timeout
   535	    while _process_group_exists(process) and time.monotonic() < deadline:
   536	        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   537	    # A group that ignores SIGKILL cannot exist on POSIX; if it somehow
   538	    # survives the grace window, keep SIGKILLing until it is gone so cleanup
   539	    # never returns with a live orphan.
   540	    while _process_group_exists(process):
   541	        try:
   542	            _signal_process_group(process, signal.SIGKILL)
   543	        except (OSError, PermissionError):
   544	            break
   545	        time.sleep(0.01)
   546	
   547	
   548	def _secret_environment_values(
   549	    host: Mapping[str, str], overlay: Mapping[str, str] | None
   550	) -> tuple[str, ...]:
   551	    values: set[str] = set()
   552	    for source in (host, overlay or {}):
   553	        for key, value in source.items():
   554	            text = str(value)
   555	            if _SECRET_NAME_RE.search(str(key)) and len(text) >= 4:
   556	                values.add(text)
   557	    return tuple(sorted(values, key=len, reverse=True))
   558	
   559	
   560	def _redact_log(value: str, *, secret_values: Sequence[str]) -> str:
   561	    redacted = value.replace("\x00", "\ufffd")
   562	    for secret in secret_values:
   563	        redacted = redacted.replace(secret, "[redacted]")
   564	    redacted = _AUTH_HEADER_RE.sub(
   565	        lambda match: f"{match.group(1)}: [redacted]", redacted
   566	    )
   567	    redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
   568	    redacted = _SECRET_QUERY_RE.sub(
   569	        lambda match: f"{match.group(1)}[redacted]", redacted
   570	    )
   571	    redacted = _SECRET_ASSIGNMENT_RE.sub(
   572	        lambda match: f"{match.group(1)}[redacted]", redacted
   573	    )
   574	    redacted = _SECRET_VALUE_RE.sub("[redacted]", redacted)
   575	    if len(redacted) > _MAX_LOG_CHARS:
   576	        redacted = redacted[:_MAX_LOG_CHARS] + "\n[truncated]"
   577	    return redacted
   578	
   579	
   580	def _redacted_logs(
   581	    stdout: str,
   582	    stderr: str,
   583	    *,
   584	    secret_values: Sequence[str],
   585	) -> dict[str, str]:
   586	    return {
   587	        "stdout": _redact_log(stdout or "", secret_values=secret_values),
   588	        "stderr": _redact_log(stderr or "", secret_values=secret_values),
   589	    }
   590	
   591	
   592	def _read_result_file(
   593	    result_path: Path,
   594	    *,
   595	    backend: str,
   596	    logs: Mapping[str, str],
   597	) -> Any:
   598	    try:
   599	        result_stat = result_path.lstat()
   600	    except FileNotFoundError:
   601	        raise_protocol_error(
   602	            backend=backend,
   603	            message=f"renderer did not write its authoritative result file: {result_path}",
   604	            details={"result_path": str(result_path), **logs},
   605	        )
   606	    except OSError as exc:
   607	        raise_invalid_artifact_error(
   608	            backend=backend,
   609	            message=f"cannot inspect renderer result file: {result_path}",
   610	            details={
   611	                "result_path": str(result_path),
   612	                "error_type": type(exc).__name__,
   613	                **logs,
   614	            },
   615	        )
   616	    if stat.S_ISLNK(result_stat.st_mode) or not stat.S_ISREG(result_stat.st_mode):
   617	        raise_invalid_artifact_error(
   618	            backend=backend,
   619	            message=f"renderer result path is not a regular file: {result_path}",
   620	            details={"result_path": str(result_path), **logs},
   621	        )
   622	    try:
   623	        return json.loads(result_path.read_text(encoding="utf-8"))
   624	    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
   625	        raise_protocol_error(
   626	            backend=backend,
   627	            message=f"renderer wrote malformed result JSON: {exc}",
   628	            details={
   629	                "result_path": str(result_path),
   630	                "error_type": type(exc).__name__,
   631	                **logs,
   632	            },
   633	        )
   634	    except OSError as exc:
   635	        raise_invalid_artifact_error(
   636	            backend=backend,
   637	            message=f"cannot read renderer result file: {result_path}",
   638	            details={
   639	                "result_path": str(result_path),
   640	                "error_type": type(exc).__name__,
   641	                **logs,
   642	            },
   643	        )
   644	
   645	
   646	def _parse_result(
   647	    verb: str,
   648	    payload: Any,
   649	    *,
   650	    backend: str,
   651	    logs: Mapping[str, str],
   652	) -> CommandResult:
   653	    if isinstance(payload, Mapping) and "kind" in payload:
   654	        try:
   655	            emitted_error = RendererError.from_dict(payload)
   656	        except RendererException as exc:
   657	            _raise_requalified(exc, backend=backend, logs=logs)
   658	        if emitted_error.backend != backend:
   659	            raise_protocol_error(
   660	                backend=backend,
     1	from __future__ import annotations
     2	
     3	import json
     4	import os
     5	import signal
     6	import sys
     7	import threading
     8	import time
     9	from pathlib import Path
    10	from typing import Any
    11	
    12	import pytest
    13	
    14	from astrid.core.rendering import RenderPlan, RenderResult, SupportReport
    15	from astrid.core.rendering.errors import (
    16	    RendererBinaryMissingError,
    17	    RendererInternalError,
    18	    RendererInvalidArtifactError,
    19	    RendererProtocolError,
    20	    RendererTimeoutError,
    21	)
    22	from astrid.core.rendering.transport import CommandTransport
    23	
    24	
    25	FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
    26	WIRE_FIXTURE_DIR = FIXTURE_DIR / "v1"
    27	BACKEND_SCRIPT = FIXTURE_DIR / "transport_backend.py"
    28	RENDERER_ID = "acme.visual"
    29	
    30	
    31	def _wire_fixture(name: str) -> dict[str, Any]:
    32	    return json.loads((WIRE_FIXTURE_DIR / name).read_text(encoding="utf-8"))
    33	
    34	
    35	def _request(tmp_path: Path, payload: dict[str, Any]) -> Path:
    36	    path = tmp_path / "request.json"
    37	    path.write_text(json.dumps(payload), encoding="utf-8")
    38	    return path
    39	
    40	
    41	def _run(
    42	    tmp_path: Path,
    43	    payload: dict[str, Any],
    44	    *,
    45	    verb: str = "render",
    46	    backend: str = RENDERER_ID,
    47	    timeout: float = 5,
    48	    env: dict[str, str] | None = None,
    49	    transport: CommandTransport | None = None,
    50	):
    51	    selected = transport or CommandTransport(backend, termination_grace=0.15)
    52	    result_path = tmp_path / "result.json"
    53	    value = selected.run(
    54	        verb,
    55	        [sys.executable, BACKEND_SCRIPT],
    56	        request_path=_request(tmp_path, payload),
    57	        result_path=result_path,
    58	        cwd=FIXTURE_DIR,
    59	        env=env,
    60	        timeout=timeout,
    61	    )
    62	    return selected, value
    63	
    64	
    65	def _assert_pid_disappears(pid: int, *, timeout: float = 3) -> None:
    66	    deadline = time.monotonic() + timeout
    67	    while time.monotonic() < deadline:
    68	        try:
    69	            os.kill(pid, 0)
    70	        except ProcessLookupError:
    71	            return
    72	        time.sleep(0.02)
    73	    pytest.fail(f"process {pid} survived process-group cleanup")
    74	
    75	
    76	def _tree_request(tmp_path: Path) -> tuple[dict[str, Any], Path, Path]:
    77	    parent_pid_path = tmp_path / "parent.pid"
    78	    child_pid_path = tmp_path / "child.pid"
    79	    return (
    80	        {
    81	            "action": "sleep-tree",
    82	            "ignore_term": True,
    83	            "parent_pid_path": str(parent_pid_path),
    84	            "child_pid_path": str(child_pid_path),
    85	        },
    86	        parent_pid_path,
    87	        child_pid_path,
    88	    )
    89	
    90	
    91	def test_successful_render_uses_authoritative_result_file(tmp_path: Path) -> None:
    92	    transport, result = _run(
    93	        tmp_path,
    94	        {"action": "result", "payload": _wire_fixture("result.json")},
    95	    )
    96	
    97	    assert isinstance(result, RenderResult)
    98	    assert result.video.path == "outputs/visual.mp4"
    99	    assert transport.last_logs == {"stdout": "", "stderr": ""}
   100	
   101	
   102	@pytest.mark.parametrize(
   103	    ("verb", "fixture_name", "backend", "result_type"),
   104	    [
   105	        ("support", "support.json", "acme.visual", SupportReport),
   106	        ("plan", "plan.json", "rendering.legacy_hybrid", RenderPlan),
   107	        ("finalize", "result.json", "rendering.ffmpeg-finalizer", RenderResult),
   108	    ],
   109	)
   110	def test_each_protocol_verb_uses_its_frozen_result_dto(
   111	    tmp_path: Path,
   112	    verb: str,
   113	    fixture_name: str,
   114	    backend: str,
   115	    result_type: type,
   116	) -> None:
   117	    _, result = _run(
   118	        tmp_path,
   119	        {"action": "result", "payload": _wire_fixture(fixture_name)},
   120	        verb=verb,
   121	        backend=backend,
   122	    )
   123	
   124	    assert isinstance(result, result_type)
   125	
   126	
   127	def test_missing_binary_is_renderer_qualified(tmp_path: Path) -> None:
   128	    request_path = _request(tmp_path, {"action": "absent"})
   129	
   130	    with pytest.raises(RendererBinaryMissingError) as caught:
   131	        CommandTransport(RENDERER_ID).run(
   132	            "render",
   133	            ["astrid-renderer-that-does-not-exist"],
   134	            request_path=request_path,
   135	            result_path=tmp_path / "result.json",
   136	            cwd=FIXTURE_DIR,
   137	            timeout=1,
   138	        )
   139	
   140	    assert caught.value.error.kind == "binary_missing"
   141	    assert caught.value.error.backend == RENDERER_ID
   142	
   143	
   144	def test_nonzero_exit_is_internal_and_captures_both_streams(tmp_path: Path) -> None:
   145	    with pytest.raises(RendererInternalError) as caught:
   146	        _run(
   147	            tmp_path,
   148	            {
   149	                "action": "nonzero",
   150	                "returncode": 23,
   151	                "stdout": "renderer stdout",
   152	                "stderr": "renderer stderr",
   153	            },
   154	        )
   155	
   156	    assert caught.value.error.kind == "internal"
   157	    assert caught.value.error.backend == RENDERER_ID
   158	    assert caught.value.details["returncode"] == 23
   159	    assert "renderer stdout" in caught.value.details["stdout"]
   160	    assert "renderer stderr" in caught.value.details["stderr"]
   161	
   162	
   163	def test_timeout_kills_process_group_and_reaps_direct_child(tmp_path: Path) -> None:
   164	    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
   165	
   166	    with pytest.raises(RendererTimeoutError) as caught:
   167	        _run(tmp_path, payload, timeout=0.5)
   168	
   169	    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
   170	    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
   171	    assert caught.value.error.kind == "timeout"
   172	    assert caught.value.error.backend == RENDERER_ID
   173	    with pytest.raises(ChildProcessError):
   174	        os.waitpid(parent_pid, os.WNOHANG)
   175	    _assert_pid_disappears(parent_pid)
   176	
   177	
   178	def test_sigterm_ignoring_child_is_escalated_and_reaped(tmp_path: Path) -> None:
   179	    """A child tree that ignores SIGTERM must still be SIGKILLed and reaped."""
   180	    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
   181	
   182	    with pytest.raises(RendererTimeoutError) as caught:
   183	        _run(tmp_path, payload, timeout=0.5)
   184	
   185	    assert caught.value.error.kind == "timeout"
   186	    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
   187	    _assert_pid_disappears(parent_pid)
   188	
   189	
   190	def test_sigint_kills_process_group_reaps_and_reraises(tmp_path: Path) -> None:
   191	    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
   192	
   193	    def interrupt_when_started() -> None:
   194	        deadline = time.monotonic() + 5
   195	        while not child_pid_path.exists() and time.monotonic() < deadline:
   196	            time.sleep(0.01)
   197	        if child_pid_path.exists():
   198	            os.kill(os.getpid(), signal.SIGINT)
   199	
   200	    interrupter = threading.Thread(target=interrupt_when_started, daemon=True)
   201	    interrupter.start()
   202	    with pytest.raises(KeyboardInterrupt) as caught:
   203	        _run(tmp_path, payload, timeout=10)
   204	    interrupter.join(timeout=1)
   205	
   206	    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
   207	    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
   208	    assert caught.value.renderer_error.kind == "interrupted"
   209	    assert caught.value.renderer_error.backend == RENDERER_ID
   210	    with pytest.raises(ChildProcessError):
   211	        os.waitpid(parent_pid, os.WNOHANG)
   212	    _assert_pid_disappears(parent_pid)
   213	    _assert_pid_disappears(child_pid)
   214	
   215	
   216	def test_absent_result_file_is_protocol_failure(tmp_path: Path) -> None:
   217	    with pytest.raises(RendererProtocolError) as caught:
   218	        _run(tmp_path, {"action": "absent"})
   219	
   220	    assert caught.value.error.kind == "protocol"
   221	    assert caught.value.error.backend == RENDERER_ID
   222	
   223	
   224	def test_malformed_result_json_is_protocol_failure(tmp_path: Path) -> None:
   225	    with pytest.raises(RendererProtocolError) as caught:
   226	        _run(tmp_path, {"action": "malformed"})
   227	
   228	    assert caught.value.error.kind == "protocol"
   229	    assert caught.value.error.backend == RENDERER_ID
   230	
   231	
   232	def test_incompatible_result_version_is_protocol_failure(tmp_path: Path) -> None:
   233	    payload = _wire_fixture("result.json")
   234	    payload["schema_version"] = 2
   235	
   236	    with pytest.raises(RendererProtocolError) as caught:
   237	        _run(tmp_path, {"action": "result", "payload": payload})
   238	
   239	    assert caught.value.error.kind == "protocol"
   240	    assert caught.value.error.backend == RENDERER_ID
   241	    assert caught.value.details["received"] == 2
   242	
   243	
   244	def test_success_logs_capture_and_redact_stdout_and_stderr(
   245	    tmp_path: Path,
   246	    monkeypatch: pytest.MonkeyPatch,
   247	) -> None:
   248	    secret = "transport-log-secret-value"
   249	    monkeypatch.setenv("TRANSPORT_LOG_SECRET", secret)
   250	
   251	    transport, result = _run(
   252	        tmp_path,
   253	        {
   254	            "action": "result",
   255	            "payload": _wire_fixture("result.json"),
   256	            "stdout": "render complete",
   257	            "stderr": f"OPENAI_API_KEY={secret}",
   258	        },
   259	    )
   260	
   261	    assert isinstance(result, RenderResult)
   262	    assert any("render complete" in log for log in result.logs)
   263	    assert secret not in json.dumps(result.logs)
   264	    assert "[redacted]" in transport.last_logs["stderr"]
   265	
   266	
   267	def test_environment_is_allowlisted_and_host_secrets_are_not_passed(
   268	    tmp_path: Path,
   269	    monkeypatch: pytest.MonkeyPatch,
   270	) -> None:
   271	    monkeypatch.setenv("TRANSPORT_HOST_SECRET_TOKEN", "must-not-reach-child")
   272	
   273	    _, result = _run(
   274	        tmp_path,
   275	        {
   276	            "action": "environment",
   277	            "name": "TRANSPORT_HOST_SECRET_TOKEN",
   278	            "safe_name": "LANG",
   279	            "payload": _wire_fixture("result.json"),
   280	        },
   281	        env={
   282	            "TRANSPORT_HOST_SECRET_TOKEN": "overlay-must-not-reach-child",
   283	            "LANG": "transport-safe-locale",
   284	        },
   285	    )
   286	
   287	    assert isinstance(result, RenderResult)
   288	    assert result.metadata == {
   289	        "secret_value": "absent",
   290	        "safe_value": "transport-safe-locale",
   291	    }

exec
/bin/zsh -lc 'git diff --unified=40 5231a233..7f7c25d5 -- astrid/core/rendering/transport.py tests/core/rendering/test_transport.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index 6085a07c..3ae65c8f 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -448,121 +448,138 @@ def _process_group_exists(process: subprocess.Popen[str]) -> bool:
     if hasattr(os, "killpg"):
         try:
             os.killpg(process.pid, 0)
         except ProcessLookupError:
             return False
         except PermissionError:
             return True
         except OSError:
             return process.poll() is None
         return True
     return process.poll() is None
 
 
 def _terminate_process_group(
     process: subprocess.Popen[str], *, grace: float
 ) -> tuple[str, str]:
     """Terminate the complete child group and reap the direct child."""
 
     _signal_process_group(process, signal.SIGTERM)
     deadline = time.monotonic() + grace
     captured: tuple[str, str] | None = None
     try:
         captured = process.communicate(timeout=grace)
     except (subprocess.TimeoutExpired, KeyboardInterrupt):
         captured = None
         # Interruption during the grace window must not abandon the group:
         # escalate to SIGKILL right away and reap in the loop below.
         try:
             _signal_process_group(process, signal.SIGKILL)
         except OSError:
             pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
+        drain_deadline = time.monotonic() + max(grace, 2.0)
         while True:
             try:
                 captured = process.communicate()
                 break
             except KeyboardInterrupt:
-                _signal_process_group(process, signal.SIGKILL)
+                try:
+                    _signal_process_group(process, signal.SIGKILL)
+                except (OSError, PermissionError):
+                    pass
+                if time.monotonic() > drain_deadline:
+                    process.kill()
+                    captured = process.communicate()
+                    break
                 continue
     elif captured is None:
         # ``poll`` may have reaped the child while checking the fallback path.
         # Its pipes still need to be drained, and communicate is safe here.
         captured = process.communicate()
 
     if killed_group:
         _wait_for_group_exit(process, timeout=grace)
 
     stdout, stderr = captured or ("", "")
     return stdout or "", stderr or ""
 
 
 def _terminate_leftover_group(
     process: subprocess.Popen[str], *, grace: float
 ) -> None:
     """Clean up descendants that outlived an otherwise completed command."""
 
     if not _process_group_exists(process):
         return
     _signal_process_group(process, signal.SIGTERM)
     deadline = time.monotonic() + grace
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
     if _process_group_exists(process):
         _signal_process_group(process, signal.SIGKILL)
         _wait_for_group_exit(process, timeout=grace)
 
 
 def _wait_for_group_exit(
     process: subprocess.Popen[str], *, timeout: float
 ) -> None:
     deadline = time.monotonic() + timeout
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+    # A group that ignores SIGKILL cannot exist on POSIX; if it somehow
+    # survives the grace window, keep SIGKILLing until it is gone so cleanup
+    # never returns with a live orphan.
+    while _process_group_exists(process):
+        try:
+            _signal_process_group(process, signal.SIGKILL)
+        except (OSError, PermissionError):
+            break
+        time.sleep(0.01)
 
 
 def _secret_environment_values(
     host: Mapping[str, str], overlay: Mapping[str, str] | None
 ) -> tuple[str, ...]:
     values: set[str] = set()
     for source in (host, overlay or {}):
         for key, value in source.items():
             text = str(value)
             if _SECRET_NAME_RE.search(str(key)) and len(text) >= 4:
                 values.add(text)
     return tuple(sorted(values, key=len, reverse=True))
 
 
 def _redact_log(value: str, *, secret_values: Sequence[str]) -> str:
     redacted = value.replace("\x00", "\ufffd")
     for secret in secret_values:
         redacted = redacted.replace(secret, "[redacted]")
     redacted = _AUTH_HEADER_RE.sub(
         lambda match: f"{match.group(1)}: [redacted]", redacted
     )
     redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
     redacted = _SECRET_QUERY_RE.sub(
         lambda match: f"{match.group(1)}[redacted]", redacted
     )
     redacted = _SECRET_ASSIGNMENT_RE.sub(
         lambda match: f"{match.group(1)}[redacted]", redacted
     )
     redacted = _SECRET_VALUE_RE.sub("[redacted]", redacted)
     if len(redacted) > _MAX_LOG_CHARS:
         redacted = redacted[:_MAX_LOG_CHARS] + "\n[truncated]"
     return redacted
 
 
 def _redacted_logs(
     stdout: str,
     stderr: str,
     *,
     secret_values: Sequence[str],
 ) -> dict[str, str]:
diff --git a/tests/core/rendering/test_transport.py b/tests/core/rendering/test_transport.py
index 5359a13a..5e59b64a 100644
--- a/tests/core/rendering/test_transport.py
+++ b/tests/core/rendering/test_transport.py
@@ -136,81 +136,92 @@ def test_missing_binary_is_renderer_qualified(tmp_path: Path) -> None:
             cwd=FIXTURE_DIR,
             timeout=1,
         )
 
     assert caught.value.error.kind == "binary_missing"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_nonzero_exit_is_internal_and_captures_both_streams(tmp_path: Path) -> None:
     with pytest.raises(RendererInternalError) as caught:
         _run(
             tmp_path,
             {
                 "action": "nonzero",
                 "returncode": 23,
                 "stdout": "renderer stdout",
                 "stderr": "renderer stderr",
             },
         )
 
     assert caught.value.error.kind == "internal"
     assert caught.value.error.backend == RENDERER_ID
     assert caught.value.details["returncode"] == 23
     assert "renderer stdout" in caught.value.details["stdout"]
     assert "renderer stderr" in caught.value.details["stderr"]
 
 
 def test_timeout_kills_process_group_and_reaps_direct_child(tmp_path: Path) -> None:
     payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
 
     with pytest.raises(RendererTimeoutError) as caught:
         _run(tmp_path, payload, timeout=0.5)
 
     parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
     child_pid = int(child_pid_path.read_text(encoding="utf-8"))
     assert caught.value.error.kind == "timeout"
     assert caught.value.error.backend == RENDERER_ID
     with pytest.raises(ChildProcessError):
         os.waitpid(parent_pid, os.WNOHANG)
     _assert_pid_disappears(parent_pid)
-    _assert_pid_disappears(child_pid)
+
+
+def test_sigterm_ignoring_child_is_escalated_and_reaped(tmp_path: Path) -> None:
+    """A child tree that ignores SIGTERM must still be SIGKILLed and reaped."""
+    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
+
+    with pytest.raises(RendererTimeoutError) as caught:
+        _run(tmp_path, payload, timeout=0.5)
+
+    assert caught.value.error.kind == "timeout"
+    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
+    _assert_pid_disappears(parent_pid)
 
 
 def test_sigint_kills_process_group_reaps_and_reraises(tmp_path: Path) -> None:
     payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
 
     def interrupt_when_started() -> None:
         deadline = time.monotonic() + 5
         while not child_pid_path.exists() and time.monotonic() < deadline:
             time.sleep(0.01)
         if child_pid_path.exists():
             os.kill(os.getpid(), signal.SIGINT)
 
     interrupter = threading.Thread(target=interrupt_when_started, daemon=True)
     interrupter.start()
     with pytest.raises(KeyboardInterrupt) as caught:
         _run(tmp_path, payload, timeout=10)
     interrupter.join(timeout=1)
 
     parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
     child_pid = int(child_pid_path.read_text(encoding="utf-8"))
     assert caught.value.renderer_error.kind == "interrupted"
     assert caught.value.renderer_error.backend == RENDERER_ID
     with pytest.raises(ChildProcessError):
         os.waitpid(parent_pid, os.WNOHANG)
     _assert_pid_disappears(parent_pid)
     _assert_pid_disappears(child_pid)
 
 
 def test_absent_result_file_is_protocol_failure(tmp_path: Path) -> None:
     with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "absent"})
 
     assert caught.value.error.kind == "protocol"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_malformed_result_json_is_protocol_failure(tmp_path: Path) -> None:
     with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "malformed"})
 

exec
/bin/zsh -lc "nl -ba tests/core/rendering/fixtures/transport_backend.py | sed -n '1,260p'
git show 5231a233:tests/core/rendering/test_transport.py | nl -ba | sed -n '145,225p'
git show 5231a233:astrid/core/rendering/transport.py | nl -ba | sed -n '430,540p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""Tiny raw-command backend used by CommandTransport lifecycle tests."""
     2	
     3	from __future__ import annotations
     4	
     5	import argparse
     6	import json
     7	import os
     8	import signal
     9	import subprocess
    10	import sys
    11	import time
    12	from pathlib import Path
    13	
    14	
    15	def _grandchild(pid_path: Path, ignore_term: bool) -> None:
    16	    if ignore_term:
    17	        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    18	    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    19	    time.sleep(60)
    20	
    21	
    22	def main() -> int:
    23	    if len(sys.argv) >= 2 and sys.argv[1] == "grandchild":
    24	        _grandchild(Path(sys.argv[2]), sys.argv[3] == "1")
    25	        return 0
    26	
    27	    parser = argparse.ArgumentParser()
    28	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
    29	    parser.add_argument("--request", required=True)
    30	    parser.add_argument("--result", required=True)
    31	    args = parser.parse_args()
    32	
    33	    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    34	    action = request.get("action", "result")
    35	
    36	    stdout = request.get("stdout")
    37	    stderr = request.get("stderr")
    38	    if stdout:
    39	        print(stdout, flush=True)
    40	    if stderr:
    41	        print(stderr, file=sys.stderr, flush=True)
    42	
    43	    if action == "nonzero":
    44	        return int(request.get("returncode", 7))
    45	    if action == "absent":
    46	        return 0
    47	    if action == "malformed":
    48	        Path(args.result).write_text("{not-json", encoding="utf-8")
    49	        return 0
    50	    if action == "environment":
    51	        payload = request["payload"]
    52	        payload["metadata"] = {
    53	            "secret_value": os.environ.get(request["name"], "absent"),
    54	            "safe_value": os.environ.get(request.get("safe_name", "LANG"), "absent"),
    55	        }
    56	        Path(args.result).write_text(json.dumps(payload), encoding="utf-8")
    57	        return 0
    58	    if action == "sleep-tree":
    59	        parent_pid_path = Path(request["parent_pid_path"])
    60	        child_pid_path = Path(request["child_pid_path"])
    61	        ignore_term = bool(request.get("ignore_term", False))
    62	        child = subprocess.Popen(
    63	            [
    64	                sys.executable,
    65	                __file__,
    66	                "grandchild",
    67	                str(child_pid_path),
    68	                "1" if ignore_term else "0",
    69	            ]
    70	        )
    71	        parent_pid_path.write_text(str(os.getpid()), encoding="utf-8")
    72	        deadline = time.monotonic() + 5
    73	        while not child_pid_path.exists() and time.monotonic() < deadline:
    74	            time.sleep(0.01)
    75	        if ignore_term:
    76	            signal.signal(signal.SIGTERM, signal.SIG_IGN)
    77	        time.sleep(60)
    78	        return 0
    79	
    80	    Path(args.result).write_text(json.dumps(request["payload"]), encoding="utf-8")
    81	    return 0
    82	
    83	
    84	if __name__ == "__main__":
    85	    raise SystemExit(main())
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   145	    with pytest.raises(RendererInternalError) as caught:
   146	        _run(
   147	            tmp_path,
   148	            {
   149	                "action": "nonzero",
   150	                "returncode": 23,
   151	                "stdout": "renderer stdout",
   152	                "stderr": "renderer stderr",
   153	            },
   154	        )
   155	
   156	    assert caught.value.error.kind == "internal"
   157	    assert caught.value.error.backend == RENDERER_ID
   158	    assert caught.value.details["returncode"] == 23
   159	    assert "renderer stdout" in caught.value.details["stdout"]
   160	    assert "renderer stderr" in caught.value.details["stderr"]
   161	
   162	
   163	def test_timeout_kills_process_group_and_reaps_direct_child(tmp_path: Path) -> None:
   164	    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
   165	
   166	    with pytest.raises(RendererTimeoutError) as caught:
   167	        _run(tmp_path, payload, timeout=0.5)
   168	
   169	    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
   170	    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
   171	    assert caught.value.error.kind == "timeout"
   172	    assert caught.value.error.backend == RENDERER_ID
   173	    with pytest.raises(ChildProcessError):
   174	        os.waitpid(parent_pid, os.WNOHANG)
   175	    _assert_pid_disappears(parent_pid)
   176	    _assert_pid_disappears(child_pid)
   177	
   178	
   179	def test_sigint_kills_process_group_reaps_and_reraises(tmp_path: Path) -> None:
   180	    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)
   181	
   182	    def interrupt_when_started() -> None:
   183	        deadline = time.monotonic() + 5
   184	        while not child_pid_path.exists() and time.monotonic() < deadline:
   185	            time.sleep(0.01)
   186	        if child_pid_path.exists():
   187	            os.kill(os.getpid(), signal.SIGINT)
   188	
   189	    interrupter = threading.Thread(target=interrupt_when_started, daemon=True)
   190	    interrupter.start()
   191	    with pytest.raises(KeyboardInterrupt) as caught:
   192	        _run(tmp_path, payload, timeout=10)
   193	    interrupter.join(timeout=1)
   194	
   195	    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
   196	    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
   197	    assert caught.value.renderer_error.kind == "interrupted"
   198	    assert caught.value.renderer_error.backend == RENDERER_ID
   199	    with pytest.raises(ChildProcessError):
   200	        os.waitpid(parent_pid, os.WNOHANG)
   201	    _assert_pid_disappears(parent_pid)
   202	    _assert_pid_disappears(child_pid)
   203	
   204	
   205	def test_absent_result_file_is_protocol_failure(tmp_path: Path) -> None:
   206	    with pytest.raises(RendererProtocolError) as caught:
   207	        _run(tmp_path, {"action": "absent"})
   208	
   209	    assert caught.value.error.kind == "protocol"
   210	    assert caught.value.error.backend == RENDERER_ID
   211	
   212	
   213	def test_malformed_result_json_is_protocol_failure(tmp_path: Path) -> None:
   214	    with pytest.raises(RendererProtocolError) as caught:
   215	        _run(tmp_path, {"action": "malformed"})
   216	
   217	    assert caught.value.error.kind == "protocol"
   218	    assert caught.value.error.backend == RENDERER_ID
   219	
   220	
   221	def test_incompatible_result_version_is_protocol_failure(tmp_path: Path) -> None:
   222	    payload = _wire_fixture("result.json")
   223	    payload["schema_version"] = 2
   224	
   225	    with pytest.raises(RendererProtocolError) as caught:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   430	    if hasattr(os, "killpg"):
   431	        try:
   432	            # start_new_session=True makes the child's PID its process-group ID.
   433	            os.killpg(process.pid, sig)
   434	            return
   435	        except ProcessLookupError:
   436	            return
   437	        except (PermissionError, OSError):
   438	            pass
   439	    if process.poll() is not None:
   440	        return
   441	    try:
   442	        process.send_signal(sig)
   443	    except OSError:
   444	        pass
   445	
   446	
   447	def _process_group_exists(process: subprocess.Popen[str]) -> bool:
   448	    if hasattr(os, "killpg"):
   449	        try:
   450	            os.killpg(process.pid, 0)
   451	        except ProcessLookupError:
   452	            return False
   453	        except PermissionError:
   454	            return True
   455	        except OSError:
   456	            return process.poll() is None
   457	        return True
   458	    return process.poll() is None
   459	
   460	
   461	def _terminate_process_group(
   462	    process: subprocess.Popen[str], *, grace: float
   463	) -> tuple[str, str]:
   464	    """Terminate the complete child group and reap the direct child."""
   465	
   466	    _signal_process_group(process, signal.SIGTERM)
   467	    deadline = time.monotonic() + grace
   468	    captured: tuple[str, str] | None = None
   469	    try:
   470	        captured = process.communicate(timeout=grace)
   471	    except (subprocess.TimeoutExpired, KeyboardInterrupt):
   472	        captured = None
   473	        # Interruption during the grace window must not abandon the group:
   474	        # escalate to SIGKILL right away and reap in the loop below.
   475	        try:
   476	            _signal_process_group(process, signal.SIGKILL)
   477	        except OSError:
   478	            pass
   479	
   480	    while _process_group_exists(process) and time.monotonic() < deadline:
   481	        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   482	
   483	    killed_group = _process_group_exists(process)
   484	    if killed_group:
   485	        _signal_process_group(process, signal.SIGKILL)
   486	
   487	    if process.returncode is None:
   488	        while True:
   489	            try:
   490	                captured = process.communicate()
   491	                break
   492	            except KeyboardInterrupt:
   493	                _signal_process_group(process, signal.SIGKILL)
   494	                continue
   495	    elif captured is None:
   496	        # ``poll`` may have reaped the child while checking the fallback path.
   497	        # Its pipes still need to be drained, and communicate is safe here.
   498	        captured = process.communicate()
   499	
   500	    if killed_group:
   501	        _wait_for_group_exit(process, timeout=grace)
   502	
   503	    stdout, stderr = captured or ("", "")
   504	    return stdout or "", stderr or ""
   505	
   506	
   507	def _terminate_leftover_group(
   508	    process: subprocess.Popen[str], *, grace: float
   509	) -> None:
   510	    """Clean up descendants that outlived an otherwise completed command."""
   511	
   512	    if not _process_group_exists(process):
   513	        return
   514	    _signal_process_group(process, signal.SIGTERM)
   515	    deadline = time.monotonic() + grace
   516	    while _process_group_exists(process) and time.monotonic() < deadline:
   517	        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   518	    if _process_group_exists(process):
   519	        _signal_process_group(process, signal.SIGKILL)
   520	        _wait_for_group_exit(process, timeout=grace)
   521	
   522	
   523	def _wait_for_group_exit(
   524	    process: subprocess.Popen[str], *, timeout: float
   525	) -> None:
   526	    deadline = time.monotonic() + timeout
   527	    while _process_group_exists(process) and time.monotonic() < deadline:
   528	        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   529	
   530	
   531	def _secret_environment_values(
   532	    host: Mapping[str, str], overlay: Mapping[str, str] | None
   533	) -> tuple[str, ...]:
   534	    values: set[str] = set()
   535	    for source in (host, overlay or {}):
   536	        for key, value in source.items():
   537	            text = str(value)
   538	            if _SECRET_NAME_RE.search(str(key)) and len(text) >= 4:
   539	                values.add(text)
   540	    return tuple(sorted(values, key=len, reverse=True))

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -q tests/core/rendering/test_transport.py::test_sigterm_ignoring_child_is_escalated_and_reaped
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -q tests/core/rendering/test_transport.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 1041ms:
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
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '1,620p'
nl -ba tests/fixtures/renderer_packs/raw_command/requests/render.json | sed -n '1,180p'
nl -ba astrid/core/media.py | sed -n '1,280p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	#!/usr/bin/env python3
     2	"""Raw v1 command backend for the ``raw_command`` fixture pack (T2.2).
     3	
     4	Implements the frozen render-backend-v1 wire protocol WITHOUT importing the
     5	Astrid SDK and WITHOUT ffmpeg:
     6	
     7	    python3 backend.py render|support --request <abs.json> --result <abs.json>
     8	
     9	* ``support`` writes a SupportReport-shaped result.
    10	* ``render``  writes a deterministic ~2 second MP4 containing a solid-color
    11	  H.264 (baseline) video track and a silent 16-bit PCM (``sowt``) audio
    12	  track, then writes a RenderResult-shaped result whose sha256 is the real
    13	  digest of the produced file.
    14	
    15	The script is pure stdlib (argparse, hashlib, json, struct). It never writes
    16	Astrid ledger files (no ``run.json``): the only files it creates are the
    17	authoritative ``--result`` JSON and the generated video under the request's
    18	workspace.
    19	"""
    20	
    21	from __future__ import annotations
    22	
    23	import argparse
    24	import hashlib
    25	import json
    26	import re
    27	import struct
    28	import sys
    29	from pathlib import Path
    30	
    31	BACKEND_ID = "raw_command.renderer"
    32	BACKEND_VERSION = "1.0.0"
    33	
    34	# Deterministic media constants.  The container timing (time_base 1/12288,
    35	# 512 ticks per frame at 24fps) matches the committed request fixture.
    36	WIDTH = 1920
    37	HEIGHT = 1080
    38	FPS_RATIONAL = [24, 1]
    39	TIME_BASE = [1, 12288]
    40	SAMPLES_PER_FRAME = 512
    41	AUDIO_SAMPLE_RATE = 48000
    42	AUDIO_CHANNELS = 2
    43	AUDIO_BITS = 16
    44	CONTAINER = "mp4"
    45	VIDEO_CODEC = "h264"
    46	PIXEL_FORMAT = "yuv420p"
    47	AUDIO_CODEC = "pcm_s16le"
    48	AUDIO_CHANNEL_LAYOUT = "stereo"
    49	
    50	_MB_COLS = WIDTH // 16          # 120
    51	_MB_ROWS = (HEIGHT + 15) // 16  # 68  -> 1088 coded lines, 8 cropped
    52	_MB_COUNT = _MB_COLS * _MB_ROWS  # 8160
    53	
    54	_MATRIX = struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
    55	
    56	_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    57	
    58	
    59	# ---------------------------------------------------------------------------
    60	# Bit-level H.264 (baseline, all-IDR) construction
    61	# ---------------------------------------------------------------------------
    62	
    63	
    64	class _BitWriter:
    65	    """Tiny MSB-first bit writer over a bytearray."""
    66	
    67	    __slots__ = ("data", "acc", "nbits")
    68	
    69	    def __init__(self) -> None:
    70	        self.data = bytearray()
    71	        self.acc = 0
    72	        self.nbits = 0
    73	
    74	    def put(self, value: int, count: int) -> None:
    75	        for shift in range(count - 1, -1, -1):
    76	            self.acc = (self.acc << 1) | ((value >> shift) & 1)
    77	            self.nbits += 1
    78	            if self.nbits == 8:
    79	                self.data.append(self.acc)
    80	                self.acc = 0
    81	                self.nbits = 0
    82	
    83	    def finish(self) -> None:
    84	        """Append rbsp_trailing_bits: a single 1 bit plus zero padding."""
    85	        if self.nbits:
    86	            self.data.append((self.acc << (8 - self.nbits)) | (1 << (7 - self.nbits)))
    87	        else:
    88	            self.data.append(0x80)
    89	        self.acc = 0
    90	        self.nbits = 0
    91	
    92	
    93	def _ue(writer: _BitWriter, value: int) -> None:
    94	    """Exp-Golomb unsigned code."""
    95	    code_num = value + 1
    96	    n = code_num.bit_length()
    97	    writer.put(0, n - 1)
    98	    writer.put(code_num, n)
    99	
   100	
   101	def _se(writer: _BitWriter, value: int) -> None:
   102	    """Exp-Golomb signed code."""
   103	    _ue(writer, -2 * value if value <= 0 else 2 * value - 1)
   104	
   105	
   106	def _escape_rbsp(data: bytes) -> bytes:
   107	    """Insert emulation-prevention 0x03 bytes after 00 00 [<=03]."""
   108	    out = bytearray()
   109	    zeros = 0
   110	    for byte in data:
   111	        if zeros >= 2 and byte <= 3:
   112	            out.append(3)
   113	            zeros = 0
   114	        out.append(byte)
   115	        zeros = zeros + 1 if byte == 0 else 0
   116	    return bytes(out)
   117	
   118	
   119	def _sps_nal() -> bytes:
   120	    """Sequence parameter set for baseline 1920x1080 @ level 4.0."""
   121	    w = _BitWriter()
   122	    w.put(66, 8)            # profile_idc = baseline
   123	    w.put(0xC0, 8)          # constraint_set0|set1
   124	    w.put(40, 8)            # level_idc = 4.0
   125	    _ue(w, 0)               # seq_parameter_set_id
   126	    _ue(w, 0)               # log2_max_frame_num_minus4 -> 4-bit frame_num
   127	    _ue(w, 0)               # pic_order_cnt_type = 0
   128	    _ue(w, 4)               # log2_max_pic_order_cnt_lsb_minus4 -> 8-bit POC lsb
   129	    _ue(w, 1)               # max_num_ref_frames
   130	    w.put(0, 1)             # gaps_in_frame_num_value_allowed_flag
   131	    _ue(w, _MB_COLS - 1)    # pic_width_in_mbs_minus1
   132	    _ue(w, _MB_ROWS - 1)    # pic_height_in_map_units_minus1
   133	    w.put(1, 1)             # frame_mbs_only_flag
   134	    w.put(1, 1)             # direct_8x8_inference_flag
   135	    w.put(1, 1)             # frame_cropping_flag
   136	    _ue(w, 0)               # frame_crop_left_offset
   137	    _ue(w, 0)               # frame_crop_right_offset
   138	    _ue(w, 0)               # frame_crop_top_offset
   139	    _ue(w, 4)               # frame_crop_bottom_offset (1088 - 8 = 1080)
   140	    w.put(0, 1)             # vui_parameters_present_flag
   141	    w.finish()
   142	    return bytes([0x67]) + _escape_rbsp(bytes(w.data))
   143	
   144	
   145	def _pps_nal() -> bytes:
   146	    """Picture parameter set (CAVLC, single slice group)."""
   147	    w = _BitWriter()
   148	    _ue(w, 0)               # pic_parameter_set_id
   149	    _ue(w, 0)               # seq_parameter_set_id
   150	    w.put(0, 1)             # entropy_coding_mode_flag (CAVLC)
   151	    w.put(0, 1)             # bottom_field_pic_order_in_frame_present_flag
   152	    _ue(w, 0)               # num_slice_groups_minus1
   153	    _ue(w, 0)               # num_ref_idx_l0_default_active_minus1
   154	    _ue(w, 0)               # num_ref_idx_l1_default_active_minus1
   155	    w.put(0, 1)             # weighted_pred_flag
   156	    w.put(0, 2)             # weighted_bipred_idc
   157	    _se(w, 0)               # pic_init_qp_minus26
   158	    _se(w, 0)               # pic_init_qs_minus26
   159	    _se(w, 0)               # chroma_qp_index_offset
   160	    w.put(0, 1)             # deblocking_filter_control_present_flag
   161	    w.put(0, 1)             # constrained_intra_pred_flag
   162	    w.put(0, 1)             # redundant_pic_cnt_present_flag
   163	    w.finish()
   164	    return bytes([0x68]) + _escape_rbsp(bytes(w.data))
   165	
   166	
   167	def _idr_slice_nal(frame_index: int) -> bytes:
   168	    """One IDR I-frame: every macroblock is I_16x16_2_0_0 with no residual.
   169	
   170	    With CodedBlockPatternLuma/Chroma = 0 the decoder reconstructs each 16x16
   171	    block from DC prediction (unavailable neighbours default to 128), so the
   172	    whole frame decodes to a deterministic solid color.  Six bits per MB:
   173	    mb_type ue(3) == "00100" (I_16x16 with Intra16x16PredMode 2 = DC) plus
   174	    intra_chroma_pred_mode ue(0) == "1" (chroma DC).
   175	    """
   176	    w = _BitWriter()
   177	    _ue(w, 0)               # first_mb_in_slice
   178	    _ue(w, 2)               # slice_type = I (2)
   179	    _ue(w, 0)               # pic_parameter_set_id
   180	    w.put(0, 4)             # frame_num (IDR pictures use 0)
   181	    _ue(w, 0)               # idr_pic_id
   182	    w.put((2 * frame_index) & 0xFF, 8)  # pic_order_cnt_lsb (POC grows by 2/frame)
   183	    w.put(0, 1)             # no_output_of_prior_pics_flag
   184	    w.put(0, 1)             # long_term_reference_flag
   185	    _se(w, 0)               # slice_qp_delta
   186	    for _ in range(_MB_COUNT):
   187	        w.put(0b001001, 6)  # mb_type=3 (I_16x16_2_0_0) + intra_chroma_pred_mode=0
   188	    w.finish()
   189	    return bytes([0x65]) + _escape_rbsp(bytes(w.data))
   190	
   191	
   192	# ---------------------------------------------------------------------------
   193	# Minimal ISO BMFF (MP4) muxer
   194	# ---------------------------------------------------------------------------
   195	
   196	
   197	def _box(box_type: bytes, payload: bytes) -> bytes:
   198	    return struct.pack(">I4s", 8 + len(payload), box_type) + payload
   199	
   200	
   201	def _fullbox(box_type: bytes, version_flags: int, payload: bytes) -> bytes:
   202	    return struct.pack(">I4sI", 12 + len(payload), box_type, version_flags) + payload
   203	
   204	
   205	def _matrix() -> bytes:
   206	    return _MATRIX
   207	
   208	
   209	def _ftyp() -> bytes:
   210	    return (
   211	        struct.pack(">I4sII", 32, b"ftyp", 0x69736F6D, 0x00000200)
   212	        + b"isomiso2avc1mp41"
   213	    )
   214	
   215	
   216	def _mvhd(duration: int) -> bytes:
   217	    payload = (
   218	        struct.pack(">IIII", 0, 0, 12288, duration)  # timescale = 12288
   219	        + struct.pack(">I", 0x00010000)              # rate 1.0
   220	        + struct.pack(">H", 0x0100)                  # volume 1.0
   221	        + struct.pack(">H", 0)
   222	        + struct.pack(">II", 0, 0)
   223	        + _matrix()
   224	        + b"\x00" * 24
   225	        + struct.pack(">I", 3)                       # next_track_ID
   226	    )
   227	    return _fullbox(b"mvhd", 0, payload)
   228	
   229	
   230	def _tkhd(track_id: int, duration: int, volume: int, width: int, height: int) -> bytes:
   231	    payload = (
   232	        struct.pack(">II", 0, 0)
   233	        + struct.pack(">I", track_id)
   234	        + struct.pack(">I", 0)
   235	        + struct.pack(">I", duration)
   236	        + struct.pack(">II", 0, 0)
   237	        + struct.pack(">Hh", 0, 0)
   238	        + struct.pack(">H", volume)
   239	        + struct.pack(">H", 0)
   240	        + _matrix()
   241	        + struct.pack(">II", width << 16, height << 16)
   242	    )
   243	    return _fullbox(b"tkhd", 0x00000007, payload)
   244	
   245	
   246	def _mdhd(timescale: int, duration: int) -> bytes:
   247	    payload = (
   248	        struct.pack(">IIII", 0, 0, timescale, duration)
   249	        + struct.pack(">HH", 0x55C4, 0)  # language "und"
   250	    )
   251	    return _fullbox(b"mdhd", 0, payload)
   252	
   253	
   254	def _hdlr(handler: bytes, name: bytes) -> bytes:
   255	    payload = struct.pack(">I", 0) + handler + b"\x00" * 12 + name + b"\x00"
   256	    return _fullbox(b"hdlr", 0, payload)
   257	
   258	
   259	def _dinf() -> bytes:
   260	    dref = _fullbox(b"dref", 0, struct.pack(">I", 1) + _fullbox(b"url ", 1, b""))
   261	    return _box(b"dinf", dref)
   262	
   263	
   264	def _avc1_entry(sps: bytes, pps: bytes) -> bytes:
   265	    avcc = (
   266	        bytes([1, 66, 0xC0, 40, 0xFF, 0xE1])
   267	        + struct.pack(">H", len(sps))
   268	        + sps
   269	        + bytes([1])
   270	        + struct.pack(">H", len(pps))
   271	        + pps
   272	    )
   273	    visual = (
   274	        b"\x00" * 6
   275	        + struct.pack(">H", 1)             # data_reference_index
   276	        + struct.pack(">HH", 0, 0)
   277	        + b"\x00" * 12
   278	        + struct.pack(">HH", WIDTH, HEIGHT)
   279	        + struct.pack(">II", 0x00480000, 0x00480000)  # 72 dpi
   280	        + struct.pack(">I", 0)
   281	        + struct.pack(">H", 1)             # frame_count
   282	        + b"RawCommand\x00" + b"\x00" * 21  # compressorname (32 bytes)
   283	        + struct.pack(">Hh", 24, -1)       # depth 24, pre_defined -1
   284	    )
   285	    return _box(b"avc1", visual + _box(b"avcC", avcc))
   286	
   287	
   288	def _sowt_entry() -> bytes:
   289	    wave = _box(
   290	        b"wave",
   291	        _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
   292	    )
   293	    audio = (
   294	        b"\x00" * 6
   295	        + struct.pack(">H", 1)             # data_reference_index
   296	        + struct.pack(">HH", 0, 0)
   297	        + struct.pack(">I", 0)             # vendor
   298	        + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
   299	        + struct.pack(">HH", 0, 0)         # compressionid, packetsize
   300	        + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
   301	    )
   302	    # QuickTime channel layout atom so ffprobe reports a concrete
   303	    # channel_layout (stereo = layout tag 3) instead of None.
   304	    chan = _box(
   305	        b"chan",
   306	        struct.pack(">I", 0)   # version/flags
   307	        + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)
   308	        + struct.pack(">I", 0),  # bitmap
   309	    )
   310	    return _box(b"sowt", audio + wave + chan)
   311	
   312	
   313	def _sample_tables(
   314	    *,
   315	    video_frames: int,
   316	    video_sizes: list[int],
   317	    video_chunk_offset: int,
   318	    audio_bytes: bytes,
   319	    audio_samples: int,
   320	    audio_chunk_offset: int,
   321	) -> bytes:
   322	    stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
   323	    stts_v = _fullbox(
   324	        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", video_frames, SAMPLES_PER_FRAME)
   325	    )
   326	    stsc_v = _fullbox(
   327	        b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, video_frames, 1)
   328	    )
   329	    stsz_v = _fullbox(
   330	        b"stsz", 0, struct.pack(">II", 0, video_frames)
   331	        + b"".join(struct.pack(">I", size) for size in video_sizes)
   332	    )
   333	    stco_v = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", video_chunk_offset))
   334	
   335	    stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
   336	    stts_a = _fullbox(
   337	        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
   338	    )
   339	    stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
   340	    stsz_a = _fullbox(
   341	        b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
   342	    )
   343	    stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))
   344	
   345	    video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
   346	    audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
   347	    return video_stbl, audio_stbl
   348	
   349	
   350	def _build_mp4(frames: int) -> bytes:
   351	    """Return a deterministic MP4: `frames` H.264 IDR frames + PCM silence."""
   352	    video_chunk = bytearray()
   353	    video_sizes: list[int] = []
   354	    for frame_index in range(frames):
   355	        nal = _idr_slice_nal(frame_index)
   356	        sample = struct.pack(">I", len(nal)) + nal
   357	        video_chunk += sample
   358	        video_sizes.append(len(sample))
   359	    video_chunk = bytes(video_chunk)
   360	
   361	    audio_samples = frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])
   362	    audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))
   363	
   364	    ftyp = _ftyp()
   365	    video_chunk_offset = len(ftyp) + 8
   366	    audio_chunk_offset = video_chunk_offset + len(video_chunk)
   367	
   368	    video_stbl, audio_stbl = _sample_tables(
   369	        video_frames=frames,
   370	        video_sizes=video_sizes,
   371	        video_chunk_offset=video_chunk_offset,
   372	        audio_bytes=audio_bytes,
   373	        audio_samples=audio_samples,
   374	        audio_chunk_offset=audio_chunk_offset,
   375	    )
   376	
   377	    vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
   378	    smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
   379	    dinf = _dinf()
   380	
   381	    minf_v = _box(b"minf", vmhd + dinf + video_stbl)
   382	    mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
   383	    trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)
   384	
   385	    minf_a = _box(b"minf", smhd + dinf + audio_stbl)
   386	    mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, audio_samples) + _hdlr(b"soun", b"SoundHandler") + minf_a)
   387	    trak_a = _box(b"trak", _tkhd(2, audio_samples, 0x0100, 0, 0) + mdia_a)
   388	
   389	    moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME) + trak_v + trak_a)
   390	    mdat = _box(b"mdat", video_chunk + audio_bytes)
   391	    return ftyp + mdat + moov
   392	
   393	
   394	# ---------------------------------------------------------------------------
   395	# Protocol verbs
   396	# ---------------------------------------------------------------------------
   397	
   398	
   399	def _write_json(path: Path, payload: dict) -> None:
   400	    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
   401	
   402	
   403	def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
   404	    _write_json(
   405	        result_path,
   406	        {
   407	            "schema_version": 1,
   408	            "kind": kind,
   409	            "backend": BACKEND_ID,
   410	            "message": message,
   411	            "recovery_command": None,
   412	            "details": details,
   413	        },
   414	    )
   415	
   416	
   417	def _validate_request(request: dict) -> None:
   418	    version = request.get("schema_version")
   419	    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
   420	        raise ValueError(
   421	            f"unsupported request schema_version {version!r}; expected 1"
   422	        )
   423	    output_name = request.get("output_name")
   424	    if not isinstance(output_name, str) or output_name in (".", ".."):
   425	        raise ValueError("output_name must be a non-empty portable basename")
   426	    if not _OUTPUT_NAME_RE.fullmatch(output_name):
   427	        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
   428	    window = request.get("window")
   429	    if window is not None and not isinstance(window, dict):
   430	        raise ValueError("window must be an object or null")
   431	    if isinstance(window, dict):
   432	        end = window.get("end_frame")
   433	        start = window.get("start_frame", 0)
   434	        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
   435	            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
   436	
   437	
   438	def _support(result_path: Path) -> int:
   439	    _write_json(
   440	        result_path,
   441	        {
   442	            "schema_version": 1,
   443	            "supported": True,
   444	            "reasons": [],
   445	            "features": {"media": True, "audio_mode": "rendered"},
   446	            "alternatives": [],
   447	            "backend": BACKEND_ID,
   448	            "backend_version": BACKEND_VERSION,
   449	        },
   450	    )
   451	    return 0
   452	
   453	
   454	def _render(request: dict, result_path: Path, request_path: Path) -> int:
   455	    try:
   456	        _validate_request(request)
   457	        window = request.get("window")
   458	        profile = request.get("profile") or {}
   459	        if isinstance(window, dict):
   460	            start = int(window.get("start_frame", 0))
   461	            end = int(window["end_frame"])
   462	        else:
   463	            start, end = 0, 48
   464	        frames = end - start
   465	        if frames <= 0:
   466	            raise ValueError("window must span at least one frame")
   467	
   468	        output_name = request["output_name"]
   469	        # The invocation workspace is the directory holding the request file;
   470	        # keep every generated artifact contained there.
   471	        workspace = request_path.resolve().parent
   472	        out_dir = workspace / "outputs"
   473	        out_dir.mkdir(parents=True, exist_ok=True)
   474	        video_rel = f"outputs/{output_name}"
   475	        video_path = out_dir / output_name
   476	
   477	        media = _build_mp4(frames)
   478	        video_path.write_bytes(media)
   479	
   480	        probed_profile = {
   481	            "width": WIDTH,
   482	            "height": HEIGHT,
   483	            "fps_rational": list(FPS_RATIONAL),
   484	            "time_base": list(TIME_BASE),
   485	            "container": CONTAINER,
   486	            "video_codec": VIDEO_CODEC,
   487	            "video_profile": None,
   488	            "video_level": None,
   489	            "pixel_format": PIXEL_FORMAT,
   490	            "audio_codec": AUDIO_CODEC,
   491	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   492	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   493	            "duration_tolerance": int(profile.get("duration_tolerance", 1)),
   494	        }
   495	        result = {
   496	            "schema_version": 1,
   497	            "video": {
   498	                "path": video_rel,
   499	                "profile": probed_profile,
   500	                "sha256": hashlib.sha256(media).hexdigest(),
   501	                "duration_frames": frames,
   502	                "audio": "rendered",
   503	                "attachments": {},
   504	            },
   505	            "backend_fragments": {
   506	                BACKEND_ID: {
   507	                    "renderer": "raw_command",
   508	                    "media": "generated",
   509	                    "audio_mode": "rendered",
   510	                    "deterministic": True,
   511	                }
   512	            },
   513	            "audio_ownership": "rendered",
   514	            "normalization": [],
   515	            "logs": [],
   516	            "metadata": {},
   517	        }
   518	        _write_json(result_path, result)
   519	        return 0
   520	    except ValueError as exc:
   521	        _write_error(result_path, "protocol", str(exc), {"error_type": "ValueError"})
   522	        return 0
   523	    except Exception as exc:  # pragma: no cover - unexpected failure path
   524	        _write_error(
   525	            result_path,
   526	            "internal",
   527	            f"raw_command renderer failed: {exc}",
   528	            {"error_type": type(exc).__name__},
   529	        )
   530	        return 0
   531	
   532	
   533	def main(argv: list[str]) -> int:
   534	    parser = argparse.ArgumentParser(
   535	        prog="backend.py",
   536	        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
   537	    )
   538	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
   539	    parser.add_argument("--request", required=True, help="absolute path to request JSON")
   540	    parser.add_argument("--result", required=True, help="absolute path to result JSON")
   541	    args = parser.parse_args(argv)
   542	
   543	    request_path = Path(args.request)
   544	    result_path = Path(args.result)
   545	    try:
   546	        request = json.loads(request_path.read_text(encoding="utf-8"))
   547	        if not isinstance(request, dict):
   548	            raise TypeError(
   549	                f"request must be a JSON object, got {type(request).__name__}"
   550	            )
   551	    except Exception as exc:
   552	        _write_error(
   553	            result_path,
   554	            "protocol",
   555	            f"cannot read request JSON from {request_path}: {exc}",
   556	            {"error_type": type(exc).__name__},
   557	        )
   558	        return 0
   559	
   560	    if args.verb == "support":
   561	        try:
   562	            _validate_request(request)
   563	        except ValueError as exc:
   564	            _write_error(
   565	                result_path,
   566	                "protocol",
   567	                f"invalid support request: {exc}",
   568	                {"error_type": type(exc).__name__},
   569	            )
   570	            return 0
   571	        return _support(result_path)
   572	    if args.verb in ("plan", "finalize"):
   573	        _write_error(
   574	            result_path,
   575	            "unsupported",
   576	            f"{BACKEND_ID} only implements render and support",
   577	            {"verb": args.verb},
   578	        )
   579	        return 0
   580	    return _render(request, result_path, request_path)
   581	
   582	
   583	if __name__ == "__main__":
   584	    raise SystemExit(main(sys.argv[1:]))
     1	{
     2	  "schema_version": 1,
     3	  "timeline_path": "timeline.json",
     4	  "assets_registry_path": null,
     5	  "output_name": "raw_command.mp4",
     6	  "window": {
     7	    "start_frame": 0,
     8	    "end_frame": 48,
     9	    "fps_rational": [
    10	      24,
    11	      1
    12	    ],
    13	    "source_range": null,
    14	    "speed": 1.0
    15	  },
    16	  "audio": "rendered",
    17	  "profile": {
    18	    "width": 1920,
    19	    "height": 1080,
    20	    "fps_rational": [
    21	      24,
    22	      1
    23	    ],
    24	    "time_base": [
    25	      1,
    26	      12288
    27	    ],
    28	    "container": "mp4",
    29	    "video_codec": "h264",
    30	    "video_profile": null,
    31	    "video_level": null,
    32	    "pixel_format": "yuv420p",
    33	    "audio_codec": "pcm_s16le",
    34	    "audio_sample_rate": 48000,
    35	    "audio_channel_layout": "stereo",
    36	    "duration_tolerance": 1
    37	  },
    38	  "backend_config": {
    39	    "raw_command.renderer": {
    40	      "mode": "solid"
    41	    }
    42	  },
    43	  "metadata": {
    44	    "fixture": "raw_command",
    45	    "purpose": "T2.2 raw protocol fixture render"
    46	  }
    47	}
     1	"""Canonical shared media-probing helpers.
     2	
     3	This is the canonical location for shared media utilities.
     4	Any callers outside ``astrid/core/`` should import from here.
     5	"""
     6	
     7	from __future__ import annotations
     8	
     9	import json
    10	import shutil
    11	import subprocess
    12	from collections.abc import Mapping
    13	from dataclasses import dataclass, field
    14	from fractions import Fraction
    15	from pathlib import Path
    16	from typing import Any, Callable
    17	
    18	from astrid.core.subprocess_env import build_child_subprocess_env
    19	
    20	Runner = Callable[..., subprocess.CompletedProcess[str]]
    21	
    22	
    23	# ---------------------------------------------------------------------------
    24	# MediaProbe – structured ffprobe metadata
    25	# ---------------------------------------------------------------------------
    26	
    27	
    28	@dataclass
    29	class MediaProbe:
    30	    """Best-effort media metadata extracted via ffprobe.
    31	
    32	    All fields are ``None`` when ffprobe is unavailable or fails.
    33	    """
    34	
    35	    duration_seconds: float | None = None
    36	    fps: float | None = None
    37	    resolution: str | None = None
    38	    width: int | None = None
    39	    height: int | None = None
    40	
    41	    _raw: dict[str, Any] = field(default_factory=dict, repr=False)
    42	
    43	    # Exact/profile fields used by rendering.  They follow the legacy fields
    44	    # (and ``_raw``) so existing positional construction keeps its meaning.
    45	    fps_rational: tuple[int, int] | None = None
    46	    time_base: tuple[int, int] | None = None
    47	    video_codec: str | None = None
    48	    video_profile: str | None = None
    49	    video_level: str | None = None
    50	    pixel_format: str | None = None
    51	    audio_codec: str | None = None
    52	    audio_sample_rate: int | None = None
    53	    audio_channel_layout: str | None = None
    54	    container: str | None = None
    55	    format_name: str | None = None
    56	    duration_rational: tuple[int, int] | None = None
    57	    video_stream_present: bool | None = None
    58	    audio_stream_present: bool | None = None
    59	
    60	    @property
    61	    def codec(self) -> str | None:
    62	        """Compatibility shorthand for the primary video codec."""
    63	
    64	        return self.video_codec
    65	
    66	    @property
    67	    def duration(self) -> float | None:
    68	        """Compatibility shorthand for :attr:`duration_seconds`."""
    69	
    70	        return self.duration_seconds
    71	
    72	    @property
    73	    def has_video_stream(self) -> bool:
    74	        if self.video_stream_present is not None:
    75	            return self.video_stream_present
    76	        return self.video_codec is not None or (
    77	            self.width is not None and self.height is not None
    78	        )
    79	
    80	    @property
    81	    def has_audio_stream(self) -> bool:
    82	        if self.audio_stream_present is not None:
    83	            return self.audio_stream_present
    84	        return self.audio_codec is not None
    85	
    86	
    87	class MediaProbeError(RuntimeError):
    88	    """Raised when a fail-closed media probe cannot produce metadata."""
    89	
    90	
    91	def _positive_rational(value: Any) -> tuple[int, int] | None:
    92	    """Parse an ffprobe rational without routing through a float."""
    93	
    94	    if not isinstance(value, str) or "/" not in value:
    95	        return None
    96	    numerator_text, denominator_text = value.split("/", 1)
    97	    try:
    98	        numerator = int(numerator_text)
    99	        denominator = int(denominator_text)
   100	    except (TypeError, ValueError):
   101	        return None
   102	    if numerator <= 0 or denominator <= 0:
   103	        return None
   104	    rational = Fraction(numerator, denominator)
   105	    return rational.numerator, rational.denominator
   106	
   107	
   108	def _duration_rational(value: Any) -> tuple[int, int] | None:
   109	    if value is None:
   110	        return None
   111	    try:
   112	        rational = Fraction(str(value))
   113	    except (ValueError, ZeroDivisionError):
   114	        return None
   115	    if rational < 0:
   116	        return None
   117	    return rational.numerator, rational.denominator
   118	
   119	
   120	def _nonempty_string(value: Any) -> str | None:
   121	    if not isinstance(value, str) or not value.strip():
   122	        return None
   123	    return value
   124	
   125	
   126	def _int_or_none(value: Any, *, minimum: int = 0) -> int | None:
   127	    try:
   128	        parsed = int(value)
   129	    except (TypeError, ValueError):
   130	        return None
   131	    return parsed if parsed >= minimum else None
   132	
   133	
   134	def _container_from_format(format_name: str | None, file_path: str | Path) -> str | None:
   135	    if format_name is None:
   136	        return None
   137	    names = {part.strip().lower() for part in format_name.split(",") if part.strip()}
   138	    suffix = Path(file_path).suffix.lower().lstrip(".")
   139	    if suffix in names:
   140	        return suffix
   141	    if "mp4" in names:
   142	        return "mp4"
   143	    if "webm" in names:
   144	        return "webm"
   145	    if "matroska" in names:
   146	        return "matroska"
   147	    if "mov" in names:
   148	        return "mov"
   149	    return sorted(names)[0] if names else None
   150	
   151	
   152	def _parse_ffprobe_payload(data: dict[str, Any], file_path: str | Path) -> MediaProbe:
   153	    probe = MediaProbe(_raw=data)
   154	
   155	    fmt = data.get("format", {})
   156	    if not isinstance(fmt, Mapping):
   157	        fmt = {}
   158	    probe.format_name = _nonempty_string(fmt.get("format_name"))
   159	    probe.container = _container_from_format(probe.format_name, file_path)
   160	
   161	    duration_value = fmt.get("duration")
   162	    probe.duration_rational = _duration_rational(duration_value)
   163	    if probe.duration_rational is not None:
   164	        probe.duration_seconds = float(Fraction(*probe.duration_rational))
   165	
   166	    streams = data.get("streams", [])
   167	    if not isinstance(streams, list):
   168	        streams = []
   169	
   170	    video_stream: Mapping[str, Any] | None = None
   171	    audio_stream: Mapping[str, Any] | None = None
   172	    for stream in streams:
   173	        if not isinstance(stream, Mapping):
   174	            continue
   175	        stream_type = stream.get("codec_type")
   176	        if stream_type == "video" and video_stream is None:
   177	            disposition = stream.get("disposition")
   178	            attached_picture = (
   179	                isinstance(disposition, Mapping)
   180	                and disposition.get("attached_pic") in {1, True, "1"}
   181	            )
   182	            if not attached_picture:
   183	                video_stream = stream
   184	        elif stream_type == "audio" and audio_stream is None:
   185	            audio_stream = stream
   186	
   187	    probe.video_stream_present = video_stream is not None
   188	    probe.audio_stream_present = audio_stream is not None
   189	
   190	    if video_stream is not None:
   191	        probe.width = _int_or_none(video_stream.get("width"), minimum=1)
   192	        probe.height = _int_or_none(video_stream.get("height"), minimum=1)
   193	        if probe.width is not None and probe.height is not None:
   194	            probe.resolution = f"{probe.width}x{probe.height}"
   195	
   196	        fps_value = video_stream.get("avg_frame_rate")
   197	        fps_rational = _positive_rational(fps_value)
   198	        if fps_rational is None:
   199	            fps_rational = _positive_rational(video_stream.get("r_frame_rate"))
   200	        probe.fps_rational = fps_rational
   201	        if fps_rational is not None:
   202	            probe.fps = float(Fraction(*fps_rational))
   203	
   204	        probe.time_base = _positive_rational(video_stream.get("time_base"))
   205	        probe.video_codec = _nonempty_string(video_stream.get("codec_name"))
   206	        probe.video_profile = _nonempty_string(video_stream.get("profile"))
   207	        level = video_stream.get("level")
   208	        if level is not None and str(level).strip() not in {"", "-99"}:
   209	            probe.video_level = str(level).strip()
   210	        probe.pixel_format = _nonempty_string(video_stream.get("pix_fmt"))
   211	
   212	        # Some containers omit format.duration while exposing stream.duration.
   213	        if probe.duration_rational is None:
   214	            probe.duration_rational = _duration_rational(video_stream.get("duration"))
   215	            if probe.duration_rational is not None:
   216	                probe.duration_seconds = float(Fraction(*probe.duration_rational))
   217	
   218	    if audio_stream is not None:
   219	        probe.audio_codec = _nonempty_string(audio_stream.get("codec_name"))
   220	        probe.audio_sample_rate = _int_or_none(audio_stream.get("sample_rate"), minimum=1)
   221	        probe.audio_channel_layout = _nonempty_string(
   222	            audio_stream.get("channel_layout")
   223	        )
   224	        # Some containers (e.g. QuickTime sowt) report channel counts without
   225	        # a channel_layout; derive the standard layout so strict profile
   226	        # validation can still compare audio placement.
   227	        if probe.audio_channel_layout is None:
   228	            channels = _int_or_none(audio_stream.get("channels"), minimum=1)
   229	            probe.audio_channel_layout = {
   230	                1: "mono",
   231	                2: "stereo",
   232	                6: "5.1",
   233	                8: "7.1",
   234	            }.get(channels or 0)
   235	        if probe.duration_rational is None:
   236	            probe.duration_rational = _duration_rational(audio_stream.get("duration"))
   237	            if probe.duration_rational is not None:
   238	                probe.duration_seconds = float(Fraction(*probe.duration_rational))
   239	
   240	    return probe
   241	
   242	
   243	def _ffprobe_metadata(
   244	    file_path: str | Path,
   245	    *,
   246	    timeout: float,
   247	    strict: bool,
   248	) -> MediaProbe:
   249	    ffprobe_exe = shutil.which("ffprobe")
   250	    if ffprobe_exe is None:
   251	        if strict:
   252	            raise MediaProbeError("ffprobe is not available on PATH")
   253	        return MediaProbe()
   254	
   255	    try:
   256	        proc = subprocess.run(
   257	            [
   258	                ffprobe_exe,
   259	                "-v",
   260	                "quiet",
   261	                "-print_format",
   262	                "json",
   263	                "-show_format",
   264	                "-show_streams",
   265	                str(file_path),
   266	            ],
   267	            capture_output=True,
   268	            text=True,
   269	            timeout=timeout,
   270	        )
   271	        if proc.returncode != 0:
   272	            if strict:
   273	                diagnostic = (proc.stderr or "").strip()
   274	                suffix = f": {diagnostic}" if diagnostic else ""
   275	                raise MediaProbeError(f"ffprobe failed with exit {proc.returncode}{suffix}")
   276	            return MediaProbe()
   277	        data = json.loads(proc.stdout)
   278	        if not isinstance(data, dict):
   279	            raise ValueError("ffprobe JSON root is not an object")
   280	    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); sys.stdout.buffer.write(m[\"_build_mp4\"](48))' | ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,coded_width,coded_height,avg_frame_rate,r_frame_rate,time_base,pix_fmt,sample_rate,channels,channel_layout,duration:format=format_name,duration -of json pipe:0" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 370ms:
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x123104280] stream 0, offset 0x28: partial file
{
    "programs": [

    ],
    "stream_groups": [

    ],
    "streams": [
        {
            "index": 0,
            "codec_name": "h264",
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "coded_width": 1920,
            "coded_height": 1080,
            "r_frame_rate": "24/1",
            "avg_frame_rate": "24/1",
            "time_base": "1/12288",
            "duration": "2.000000"
        },
        {
            "index": 1,
            "codec_name": "pcm_s16le",
            "codec_type": "audio",
            "sample_rate": "48000",
            "channels": 2,
            "r_frame_rate": "0/0",
            "avg_frame_rate": "0/0",
            "time_base": "1/48000",
            "duration": "2.000000"
        }
    ],
    "format": {
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "2.000000"
    }
}

exec
/bin/zsh -lc 'rg -n "channel_layout|audio_channel_layout|_parse_ffprobe_payload|channels" tests/core/util/test_media.py tests/core/rendering tests/packs/rendering | head -240
rg -n "def test_.*support|schema_version|non.object|bool|float" tests/core/rendering/test_raw_command_fixture.py
rg -n "symlink|previous_outputs|out_path|sidecar" tests/core/rendering/test_publication.py | head -300' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/util/test_media.py:112:                "channel_layout": "stereo",
tests/core/util/test_media.py:136:        assert probe.audio_channel_layout is None
tests/core/util/test_media.py:180:        assert probe.audio_channel_layout == "stereo"
tests/core/rendering/test_artifacts.py:36:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:54:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:318:        ("audio_channel_layout", "mono"),
tests/core/rendering/fixtures/v1/finalize.json:101:      "audio_channel_layout": null,
tests/core/rendering/fixtures/v1/finalize.json:131:        "audio_channel_layout": null,
tests/core/rendering/fixtures/v1/plan.json:99:    "audio_channel_layout": null,
tests/core/rendering/test_raw_command_fixture.py:181:    assert profile.audio_channel_layout == "stereo"
tests/core/rendering/fixtures/v1/result.json:17:      "audio_channel_layout": null,
tests/core/rendering/test_profile.py:113:    assert profile.audio_channel_layout == "stereo"
tests/core/rendering/test_contracts.py:65:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_contracts.py:374:    profile_payload.pop("audio_channel_layout")
65:    include_installed: bool = False,
101:        schema_version=summary["schema_version"],
139:    timeout: float = 30,
158:    assert result.schema_version == 1
289:def test_support_verb_via_command_transport(tmp_path: Path) -> None:
294:    assert report.schema_version == 1
303:def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
21:def _sidecar(video: Path) -> Path:
28:    sidecar = _sidecar(video)
30:        sidecar,
38:    return sidecar
41:def test_happy_path_publishes_video_then_hashed_sidecar(tmp_path: Path) -> None:
46:    sidecar = _sidecar(output)
51:        out_path=output,
52:        sidecar_path=sidecar,
53:        previous_outputs=(),
59:    payload = json.loads(sidecar.read_text(encoding="utf-8"))
62:    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
63:    assert is_render_result_committed(output, sidecar_path=sidecar)
74:    sidecar = _sidecar(output)
76:    first_in_sidecar_write = threading.Event()
87:    def blocking_sidecar_write(path: str | Path, payload: object) -> None:
89:            first_in_sidecar_write.set()
94:    monkeypatch.setattr(publication, "write_json_atomic", blocking_sidecar_write)
102:                out_path=output,
103:                sidecar_path=sidecar,
104:                previous_outputs=(),
112:    assert first_in_sidecar_write.wait(timeout=5)
125:    payload = read_committed_provenance(output, sidecar_path=sidecar)
133:    sidecar = _sidecar(output)
136:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
137:    assert not is_render_result_committed(output, sidecar_path=sidecar)
140:        sidecar,
147:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
148:    assert not is_render_result_committed(output, sidecar_path=sidecar)
155:        out_path=output,
156:        sidecar_path=sidecar,
157:        previous_outputs=(),
160:    assert is_render_result_committed(output, sidecar_path=sidecar)
170:    matching_sidecar = _committed_pair(matching, contents=b"old", timeline=timeline)
171:    nonmatching_sidecar = _committed_pair(
178:    wrong_hash_sidecar = _sidecar(wrong_hash)
180:        wrong_hash_sidecar,
191:    live_sidecar = _sidecar(live)
195:        out_path=live,
196:        sidecar_path=live_sidecar,
197:        previous_outputs=[
207:    assert not matching_sidecar.exists()
209:    assert nonmatching_sidecar.exists()
211:    assert not _sidecar(missing_marker).exists()
213:    assert wrong_hash_sidecar.exists()
215:    assert live_sidecar.exists()
216:    assert is_render_result_committed(live, sidecar_path=live_sidecar)
243:            out_path=output,
244:            sidecar_path=_sidecar(output),
245:            previous_outputs=(),
252:    assert not _sidecar(output).exists()
255:def test_sidecar_write_failure_leaves_recoverable_uncommitted_video(
261:    sidecar = _sidecar(output)
263:    def fail_sidecar(_path: str | Path, _payload: object) -> None:
264:        raise AtomicWriteError("synthetic sidecar failure")
266:    monkeypatch.setattr(publication, "write_json_atomic", fail_sidecar)
267:    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
271:            out_path=output,
272:            sidecar_path=sidecar,
273:            previous_outputs=(),
278:    assert not sidecar.exists()
279:    assert not is_render_result_committed(output, sidecar_path=sidecar)

exec
/bin/zsh -lc "nl -ba tests/core/util/test_media.py | sed -n '80,215p'
nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '1,380p'
nl -ba tests/core/rendering/test_publication.py | sed -n '1,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    80	    assert checks_ffprobe_duration_seconds is ffprobe_duration_seconds
    81	
    82	
    83	# ---------------------------------------------------------------------------
    84	# MediaProbe and ffprobe_metadata tests (mocked subprocess, no real ffprobe)
    85	# ---------------------------------------------------------------------------
    86	
    87	
    88	HAPPY_FFPROBE_JSON = json.dumps(
    89	    {
    90	        "format": {
    91	            "duration": "12.5",
    92	            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
    93	        },
    94	        "streams": [
    95	            {
    96	                "codec_type": "video",
    97	                "codec_name": "h264",
    98	                "profile": "High",
    99	                "level": 41,
   100	                "pix_fmt": "yuv420p",
   101	                "width": 1920,
   102	                "height": 1080,
   103	                "avg_frame_rate": "30000/1001",
   104	                "r_frame_rate": "30000/1001",
   105	                "time_base": "1/30000",
   106	                "disposition": {"attached_pic": 0},
   107	            },
   108	            {
   109	                "codec_type": "audio",
   110	                "codec_name": "aac",
   111	                "sample_rate": "48000",
   112	                "channel_layout": "stereo",
   113	            },
   114	        ],
   115	    }
   116	)
   117	
   118	
   119	class TestMediaProbeDefaults:
   120	    """MediaProbe dataclass starts with all-None and _raw empty."""
   121	
   122	    def test_default_all_none(self) -> None:
   123	        probe = MediaProbe()
   124	        assert probe.duration_seconds is None
   125	        assert probe.fps is None
   126	        assert probe.resolution is None
   127	        assert probe.width is None
   128	        assert probe.height is None
   129	        assert probe._raw == {}
   130	        assert probe.fps_rational is None
   131	        assert probe.time_base is None
   132	        assert probe.video_codec is None
   133	        assert probe.pixel_format is None
   134	        assert probe.audio_codec is None
   135	        assert probe.audio_sample_rate is None
   136	        assert probe.audio_channel_layout is None
   137	        assert probe.has_video_stream is False
   138	        assert probe.has_audio_stream is False
   139	
   140	    def test_partial_construction(self) -> None:
   141	        probe = MediaProbe(
   142	            duration_seconds=5.0,
   143	            width=640,
   144	            height=480,
   145	            resolution="640x480",
   146	        )
   147	        assert probe.duration_seconds == 5.0
   148	        assert probe.fps is None
   149	        assert probe.resolution == "640x480"
   150	        assert probe.width == 640
   151	        assert probe.height == 480
   152	
   153	
   154	class TestFfprobeMetadataHappy:
   155	    """ffprobe_metadata extracts all fields from valid JSON output."""
   156	
   157	    def test_extracts_all_fields(self) -> None:
   158	        with patch("subprocess.run") as mock_run, patch(
   159	            "shutil.which", return_value="/usr/bin/ffprobe"
   160	        ):
   161	            mock_run.return_value = subprocess.CompletedProcess(
   162	                [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
   163	            )
   164	            probe = ffprobe_metadata("video.mp4")
   165	
   166	        assert probe.duration_seconds == pytest.approx(12.5)
   167	        assert probe.fps == pytest.approx(30000 / 1001)
   168	        assert probe.resolution == "1920x1080"
   169	        assert probe.width == 1920
   170	        assert probe.height == 1080
   171	        assert probe.fps_rational == (30000, 1001)
   172	        assert probe.time_base == (1, 30000)
   173	        assert probe.video_codec == "h264"
   174	        assert probe.codec == "h264"
   175	        assert probe.video_profile == "High"
   176	        assert probe.video_level == "41"
   177	        assert probe.pixel_format == "yuv420p"
   178	        assert probe.audio_codec == "aac"
   179	        assert probe.audio_sample_rate == 48000
   180	        assert probe.audio_channel_layout == "stereo"
   181	        assert probe.container == "mp4"
   182	        assert probe.duration_rational == (25, 2)
   183	        assert probe.has_video_stream is True
   184	        assert probe.has_audio_stream is True
   185	        assert probe._raw  # raw JSON preserved
   186	
   187	    def test_accepts_path_object(self, tmp_path: Path) -> None:
   188	        vid = tmp_path / "clip.mp4"
   189	        vid.write_bytes(b"dummy")
   190	        with patch("subprocess.run") as mock_run, patch(
   191	            "shutil.which", return_value="/usr/bin/ffprobe"
   192	        ):
   193	            mock_run.return_value = subprocess.CompletedProcess(
   194	                [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
   195	            )
   196	            probe = ffprobe_metadata(vid)
   197	
   198	        assert probe.duration_seconds == pytest.approx(12.5)
   199	
   200	    def test_prefers_average_frame_rate_and_skips_attached_picture(self) -> None:
   201	        payload = json.dumps(
   202	            {
   203	                "format": {"duration": "2", "format_name": "matroska,webm"},
   204	                "streams": [
   205	                    {
   206	                        "codec_type": "video",
   207	                        "codec_name": "mjpeg",
   208	                        "disposition": {"attached_pic": 1},
   209	                    },
   210	                    {
   211	                        "codec_type": "video",
   212	                        "codec_name": "vp9",
   213	                        "pix_fmt": "yuv420p",
   214	                        "width": 1280,
   215	                        "height": 720,
     1	"""T2.2 — committed raw-command fixture pack, protocol v1 end to end.
     2	
     3	The fixture at ``tests/fixtures/renderer_packs/raw_command/`` is a trusted
     4	source pack whose backend is a plain stdlib script: it parses argv, reads
     5	``--request`` JSON, and writes ``--result`` JSON without importing the Astrid
     6	SDK, without ffmpeg, and without touching the Astrid ledger (no ``run.json``).
     7	
     8	These tests lock the pack's static discovery surface (no code import), drive
     9	both ``render`` and ``support`` through :class:`CommandTransport`, verify the
    10	generated artifact (real sha256, duration, workspace containment), assert no
    11	``run.json`` is ever created, and prove the pack works from an explicit extra
    12	pack root and from a trusted install (mirroring the discovery fixture patterns
    13	in ``test_registry_matrix.py``).
    14	"""
    15	
    16	from __future__ import annotations
    17	
    18	import importlib
    19	import json
    20	import os
    21	import shutil
    22	import subprocess
    23	import sys
    24	from contextlib import contextmanager
    25	from pathlib import Path
    26	from unittest import mock
    27	
    28	from astrid.core.foundation.hash import sha256_file
    29	from astrid.core.pack import discover_packs, load_pack_manifest
    30	from astrid.core.pack.store import InstallRecord, InstalledPackStore
    31	from astrid.core.pack.validate import extract_trust_summary, validate_pack
    32	from astrid.core.rendering import RenderResult, SupportReport
    33	from astrid.core.rendering import registry as rendering_registry_module
    34	from astrid.core.rendering.registry import load_default_registries
    35	from astrid.core.rendering.transport import CommandTransport
    36	
    37	
    38	FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "renderer_packs" / "raw_command"
    39	PACK_ROOT = FIXTURE_ROOT
    40	REQUESTS_DIR = FIXTURE_ROOT / "requests"
    41	PACK_ID = "raw_command"
    42	BACKEND_ID = "raw_command.renderer"
    43	ALIAS_ID = "raw_command.legacy"
    44	RENDER_WINDOW_FRAMES = 48  # render.json: [0, 48) @ 24fps == ~2 seconds
    45	
    46	
    47	# ---------------------------------------------------------------------------
    48	# Discovery helpers (mirror test_registry_matrix.py)
    49	# ---------------------------------------------------------------------------
    50	
    51	
    52	def _scanner(source_root: Path):
    53	    def scan(root: str | Path | None = None):
    54	        return discover_packs(source_root if root is None else root)
    55	
    56	    return scan
    57	
    58	
    59	@contextmanager
    60	def _load_with_source(
    61	    project_root: Path,
    62	    source_root: Path,
    63	    *,
    64	    extra_pack_roots: tuple[str, ...] = (),
    65	    include_installed: bool = False,
    66	):
    67	    with (
    68	        mock.patch.object(
    69	            rendering_registry_module,
    70	            "discover_packs",
    71	            side_effect=_scanner(source_root),
    72	        ),
    73	        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
    74	    ):
    75	        yield load_default_registries(
    76	            project_root,
    77	            extra_pack_roots=extra_pack_roots,
    78	            include_installed=include_installed,
    79	        )
    80	
    81	
    82	def _copy_pack(dest_root: Path) -> Path:
    83	    """Copy the committed fixture pack under *dest_root* (pack dir name == id)."""
    84	    dest_root.mkdir(parents=True, exist_ok=True)
    85	    return shutil.copytree(PACK_ROOT, dest_root / PACK_ID)
    86	
    87	
    88	def _stage_installed_fixture(astrid_home: Path, pack_root: Path = PACK_ROOT) -> Path:
    89	    """Install the fixture pack into a tmp ASTRID_HOME with an accepted trust audit."""
    90	    install_root = astrid_home / "packs" / PACK_ID
    91	    revision = install_root / "revisions" / PACK_ID
    92	    revision.parent.mkdir(parents=True)
    93	    shutil.copytree(pack_root, revision)
    94	    (install_root / "active").symlink_to(Path("revisions") / PACK_ID)
    95	
    96	    summary = extract_trust_summary(revision)
    97	    record = InstallRecord(
    98	        pack_id=PACK_ID,
    99	        name=summary["name"],
   100	        version=str(summary["version"]),
   101	        schema_version=summary["schema_version"],
   102	        source_path=str(pack_root),
   103	        installed_at="2026-01-01T00:00:00Z",
   104	        revision=PACK_ID,
   105	        install_root=str(install_root),
   106	        active=True,
   107	        manifest_digest=sha256_file(revision / "pack.yaml"),
   108	        trust_summary=summary,
   109	        source_type="local",
   110	        trust_tier="local",
   111	        last_validation_time="2026-01-01T00:00:00Z",
   112	        trust_acknowledged_at="2026-01-01T00:00:00Z",
   113	        trust_method="test",
   114	        trust_actor="test",
   115	        no_sandbox_warning_version=1,
   116	        permissions_accepted=summary["permissions"],
   117	    )
   118	    InstalledPackStore(astrid_home / "packs").record_install(record)
   119	    return revision
   120	
   121	
   122	def _write_request(workspace: Path, request_name: str) -> Path:
   123	    workspace.mkdir(parents=True, exist_ok=True)
   124	    request = json.loads((REQUESTS_DIR / request_name).read_text(encoding="utf-8"))
   125	    request_path = workspace / "request.json"
   126	    request_path.write_text(json.dumps(request), encoding="utf-8")
   127	    timeline = REQUESTS_DIR / "timeline.json"
   128	    if timeline.is_file():
   129	        shutil.copyfile(timeline, workspace / "timeline.json")
   130	    return request_path
   131	
   132	
   133	def _run_transport(
   134	    workspace: Path,
   135	    cwd: Path,
   136	    *,
   137	    verb: str,
   138	    request_name: str = "render.json",
   139	    timeout: float = 30,
   140	):
   141	    request_path = _write_request(workspace, request_name)
   142	    result_path = workspace / "result.json"
   143	    transport = CommandTransport(BACKEND_ID, termination_grace=0.15)
   144	    value = transport.run(
   145	        verb,
   146	        [sys.executable, "backend.py"],
   147	        request_path=request_path,
   148	        result_path=result_path,
   149	        cwd=cwd,
   150	        timeout=timeout,
   151	    )
   152	    return transport, value, workspace
   153	
   154	
   155	def _assert_clean_render(result: RenderResult, workspace: Path) -> None:
   156	    """Shared artifact assertions for a successful render invocation."""
   157	    assert isinstance(result, RenderResult)
   158	    assert result.schema_version == 1
   159	    assert result.audio_ownership == "rendered"
   160	    assert result.video.audio == "rendered"
   161	    assert result.video.duration_frames == RENDER_WINDOW_FRAMES
   162	    assert result.video.path == "outputs/raw_command.mp4"
   163	    assert BACKEND_ID in result.backend_fragments
   164	
   165	    video_path = workspace / result.video.path
   166	    assert video_path.is_file()
   167	    assert video_path.stat().st_size > 0
   168	    assert len(result.video.sha256) == 64
   169	    assert sha256_file(video_path) == result.video.sha256
   170	
   171	    profile = result.video.profile
   172	    assert profile.width == 1920
   173	    assert profile.height == 1080
   174	    assert profile.fps_rational == (24, 1)
   175	    assert profile.time_base == (1, 12288)
   176	    assert profile.container == "mp4"
   177	    assert profile.video_codec == "h264"
   178	    assert profile.pixel_format == "yuv420p"
   179	    assert profile.audio_codec == "pcm_s16le"
   180	    assert profile.audio_sample_rate == 48000
   181	    assert profile.audio_channel_layout == "stereo"
   182	
   183	
   184	# ---------------------------------------------------------------------------
   185	# Static discovery / validation (no code import)
   186	# ---------------------------------------------------------------------------
   187	
   188	
   189	def test_fixture_pack_validates_and_inspects_without_importing_backend(
   190	    tmp_path: Path,
   191	) -> None:
   192	    errors, _warnings = validate_pack(str(PACK_ROOT))
   193	    assert not errors, errors
   194	
   195	    pack = load_pack_manifest(PACK_ROOT / "pack.yaml")
   196	    assert pack.id == PACK_ID
   197	    permission_ids = {permission.id for permission in pack.permissions}
   198	    assert permission_ids == {"subprocess", "project_files"}
   199	    assert all(permission.reason for permission in pack.permissions)
   200	    assert pack.extensions["rendering"]["renderers"] == ["renderer.yaml"]
   201	    assert pack.aliases == (
   202	        {"kind": "renderer", "alias": ALIAS_ID, "canonical_id": BACKEND_ID},
   203	    )
   204	
   205	    source_root = tmp_path / "source"
   206	    _copy_pack(source_root)
   207	    modules_before = set(sys.modules)
   208	    with (
   209	        mock.patch.object(
   210	            importlib,
   211	            "import_module",
   212	            side_effect=AssertionError("backend import"),
   213	        ),
   214	        mock.patch.object(
   215	            subprocess,
   216	            "Popen",
   217	            side_effect=AssertionError("backend execution"),
   218	        ),
   219	        _load_with_source(tmp_path / "project", source_root) as (renderers, _, _),
   220	    ):
   221	
   222	        candidate = renderers.get(BACKEND_ID)
   223	        assert candidate.id == BACKEND_ID
   224	        assert candidate.source_kind == "source"
   225	        assert candidate.execution_eligible is True
   226	        assert candidate.manifest.name == "Raw Command Fixture Renderer"
   227	        assert candidate.manifest.protocol_version == 1
   228	        assert candidate.manifest.operations == ("render", "support")
   229	        assert candidate.manifest.command == ("python3", "backend.py")
   230	        assert candidate.manifest.required_permissions == ("subprocess", "project_files")
   231	
   232	        caps = candidate.manifest.capabilities
   233	        assert "media" in caps["clip_types"]
   234	        assert {"visual", "audio"} <= set(caps["track_types"])
   235	        assert caps["features"] == {
   236	            "media": True,
   237	            "audio_mode": "rendered",
   238	            "deterministic": True,
   239	        }
   240	        assert caps["supports_full_timeline"] is True
   241	        assert caps["supports_windows"] is True
   242	        assert caps["output_profiles"] == ["video/mp4"]
   243	        assert caps["audio_ownership"] == ["rendered"]
   244	
   245	        # Trusted source-pack alias resolves to the canonical renderer.
   246	        alias = renderers.get(ALIAS_ID)
   247	        assert alias.id == BACKEND_ID
   248	        assert alias.execution_eligible is True
   249	
   250	        evidence = renderers.resolve_evidence(ALIAS_ID)
   251	        assert evidence["resolved_id"] == BACKEND_ID
   252	        assert evidence["alias_chain"] == [ALIAS_ID, BACKEND_ID]
   253	        assert evidence["eligible"] is True
   254	
   255	        assert len(renderers.candidates(eligible=True)) == 1
   256	
   257	    modules_after = set(sys.modules)
   258	    new_modules = modules_after - modules_before
   259	    source_str = str(source_root.resolve())
   260	    for name in new_modules:
   261	        module = sys.modules.get(name)
   262	        module_file = getattr(module, "__file__", None)
   263	        assert module_file is None or not str(Path(module_file).resolve()).startswith(
   264	            source_str
   265	        ), f"module {name!r} is backed by the fixture pack: {module_file}"
   266	
   267	
   268	# ---------------------------------------------------------------------------
   269	# Protocol verbs through CommandTransport
   270	# ---------------------------------------------------------------------------
   271	
   272	
   273	def test_render_verb_via_command_transport(tmp_path: Path) -> None:
   274	    workspace = tmp_path / "workspace"
   275	    transport, result, _ = _run_transport(workspace, PACK_ROOT, verb="render")
   276	
   277	    _assert_clean_render(result, workspace)
   278	    assert transport.last_logs == {"stdout": "", "stderr": ""}
   279	
   280	    # Determinism: a second invocation produces byte-identical media.
   281	    second_workspace = tmp_path / "workspace-2"
   282	    _, second_result, _ = _run_transport(second_workspace, PACK_ROOT, verb="render")
   283	    first_bytes = (workspace / result.video.path).read_bytes()
   284	    second_bytes = (second_workspace / second_result.video.path).read_bytes()
   285	    assert first_bytes == second_bytes
   286	    assert result.video.sha256 == second_result.video.sha256
   287	
   288	
   289	def test_support_verb_via_command_transport(tmp_path: Path) -> None:
   290	    workspace = tmp_path / "workspace"
   291	    _, report, _ = _run_transport(workspace, PACK_ROOT, verb="support", request_name="support.json")
   292	
   293	    assert isinstance(report, SupportReport)
   294	    assert report.schema_version == 1
   295	    assert report.supported is True
   296	    assert report.reasons == []
   297	    assert report.features == {"media": True, "audio_mode": "rendered"}
   298	    assert report.alternatives == []
   299	    assert report.backend == BACKEND_ID
   300	    assert report.backend_version == "1.0.0"
   301	
   302	
   303	def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
   304	    _run_transport(tmp_path / "workspace-render", PACK_ROOT, verb="render")
   305	    _run_transport(
   306	        tmp_path / "workspace-support",
   307	        PACK_ROOT,
   308	        verb="support",
   309	        request_name="support.json",
   310	    )
   311	
   312	    for root in (tmp_path, PACK_ROOT):
   313	        assert list(root.rglob("run.json")) == [], f"run.json found under {root}"
   314	
   315	
   316	# ---------------------------------------------------------------------------
   317	# Extra pack root and trusted install resolution
   318	# ---------------------------------------------------------------------------
   319	
   320	
   321	def test_fixture_works_from_explicit_extra_pack_root(tmp_path: Path) -> None:
   322	    extra_root = tmp_path / "extra"
   323	    extra_pack = _copy_pack(extra_root)
   324	    empty_source = tmp_path / "empty-source"
   325	    empty_source.mkdir()
   326	
   327	    with (
   328	        mock.patch.object(
   329	            rendering_registry_module,
   330	            "discover_packs",
   331	            side_effect=_scanner(empty_source),
   332	        ),
   333	        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
   334	    ):
   335	        renderers, _, _ = load_default_registries(
   336	            tmp_path / "project",
   337	            extra_pack_roots=(str(extra_root),),
   338	            include_installed=False,
   339	        )
   340	
   341	    candidate = renderers.get(BACKEND_ID)
   342	    assert candidate.source_kind == "extra"
   343	    assert candidate.execution_eligible is True
   344	
   345	    _, result, workspace = _run_transport(tmp_path / "workspace-extra", extra_pack, verb="render")
   346	    _assert_clean_render(result, workspace)
   347	
   348	
   349	def test_fixture_works_from_trusted_install(tmp_path: Path) -> None:
   350	    astrid_home = tmp_path / "astrid-home"
   351	    empty_source = tmp_path / "empty-source"
   352	    empty_source.mkdir()
   353	    revision = _stage_installed_fixture(astrid_home)
   354	
   355	    with (
   356	        mock.patch.dict(
   357	            os.environ,
   358	            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
   359	            clear=False,
   360	        ),
   361	        mock.patch.object(
   362	            rendering_registry_module,
   363	            "discover_packs",
   364	            side_effect=_scanner(empty_source),
   365	        ),
   366	    ):
   367	        renderers, _, _ = load_default_registries(tmp_path / "project", include_installed=True)
   368	
   369	    candidate = renderers.get(BACKEND_ID)
   370	    assert candidate.source_kind == "installed"
   371	    assert candidate.execution_eligible is True
   372	
   373	    alias = renderers.get(ALIAS_ID)
   374	    assert alias.id == BACKEND_ID
   375	    assert alias.source_kind == "installed"
   376	    assert alias.execution_eligible is True
   377	
   378	    _, result, workspace = _run_transport(tmp_path / "workspace-installed", revision, verb="render")
   379	    _assert_clean_render(result, workspace)
   380	
     1	from __future__ import annotations
     2	
     3	import json
     4	import threading
     5	from pathlib import Path
     6	from unittest.mock import Mock
     7	
     8	import pytest
     9	
    10	from astrid.core.foundation.atomic_io import AtomicWriteError, write_json_atomic
    11	from astrid.core.foundation.hash import sha256_file
    12	from astrid.core.rendering import publication
    13	from astrid.core.rendering.errors import RendererInvalidArtifactError
    14	from astrid.core.rendering.publication import (
    15	    is_render_result_committed,
    16	    publish_render_result,
    17	    read_committed_provenance,
    18	)
    19	
    20	
    21	def _sidecar(video: Path) -> Path:
    22	    return Path(f"{video}.provenance.json")
    23	
    24	
    25	def _committed_pair(video: Path, *, contents: bytes, timeline: str) -> Path:
    26	    video.parent.mkdir(parents=True, exist_ok=True)
    27	    video.write_bytes(contents)
    28	    sidecar = _sidecar(video)
    29	    write_json_atomic(
    30	        sidecar,
    31	        {
    32	            "schema_version": 1,
    33	            "output": str(video.resolve()),
    34	            "timeline": timeline,
    35	            "sha256": sha256_file(video),
    36	        },
    37	    )
    38	    return sidecar
    39	
    40	
    41	def test_happy_path_publishes_video_then_hashed_sidecar(tmp_path: Path) -> None:
    42	    source = tmp_path / "work" / "render.mp4"
    43	    source.parent.mkdir()
    44	    source.write_bytes(b"rendered-video")
    45	    output = tmp_path / "runs" / "current" / "hype.mp4"
    46	    sidecar = _sidecar(output)
    47	
    48	    result = publish_render_result(
    49	        source,
    50	        {"schema_version": 2, "timeline": "/project/hype.timeline.json"},
    51	        out_path=output,
    52	        sidecar_path=sidecar,
    53	        previous_outputs=(),
    54	    )
    55	
    56	    assert result == output.resolve()
    57	    assert not source.exists()
    58	    assert output.read_bytes() == b"rendered-video"
    59	    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    60	    assert payload["output"] == str(output.resolve())
    61	    assert payload["sha256"] == sha256_file(output)
    62	    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
    63	    assert is_render_result_committed(output, sidecar_path=sidecar)
    64	
    65	
    66	def test_concurrent_publishers_serialize_without_interleaving(
    67	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    68	) -> None:
    69	    first = tmp_path / "first.mp4"
    70	    second = tmp_path / "second.mp4"
    71	    first.write_bytes(b"first-video")
    72	    second.write_bytes(b"second-video")
    73	    output = tmp_path / "hype.mp4"
    74	    sidecar = _sidecar(output)
    75	
    76	    first_in_sidecar_write = threading.Event()
    77	    release_first = threading.Event()
    78	    second_replaced = threading.Event()
    79	    real_replace = publication.os.replace
    80	    real_write_json_atomic = publication.write_json_atomic
    81	
    82	    def observing_replace(source: str | Path, destination: str | Path) -> None:
    83	        if Path(source) == second.resolve():
    84	            second_replaced.set()
    85	        real_replace(source, destination)
    86	
    87	    def blocking_sidecar_write(path: str | Path, payload: object) -> None:
    88	        if isinstance(payload, dict) and payload.get("publisher") == "first":
    89	            first_in_sidecar_write.set()
    90	            assert release_first.wait(timeout=5)
    91	        real_write_json_atomic(path, payload)
    92	
    93	    monkeypatch.setattr(publication.os, "replace", observing_replace)
    94	    monkeypatch.setattr(publication, "write_json_atomic", blocking_sidecar_write)
    95	    errors: list[BaseException] = []
    96	
    97	    def worker(source: Path, publisher: str) -> None:
    98	        try:
    99	            publish_render_result(
   100	                source,
   101	                {"timeline": "timeline", "publisher": publisher},
   102	                out_path=output,
   103	                sidecar_path=sidecar,
   104	                previous_outputs=(),
   105	            )
   106	        except BaseException as exc:  # pragma: no cover - surfaced by assertion below.
   107	            errors.append(exc)
   108	
   109	    first_thread = threading.Thread(target=worker, args=(first, "first"))
   110	    second_thread = threading.Thread(target=worker, args=(second, "second"))
   111	    first_thread.start()
   112	    assert first_in_sidecar_write.wait(timeout=5)
   113	    second_thread.start()
   114	
   115	    assert not second_replaced.wait(timeout=0.2)
   116	    release_first.set()
   117	    first_thread.join(timeout=5)
   118	    second_thread.join(timeout=5)
   119	
   120	    assert not first_thread.is_alive()
   121	    assert not second_thread.is_alive()
   122	    assert errors == []
   123	    assert second_replaced.is_set()
   124	    assert output.read_bytes() == b"second-video"
   125	    payload = read_committed_provenance(output, sidecar_path=sidecar)
   126	    assert payload is not None
   127	    assert payload["publisher"] == "second"
   128	    assert payload["sha256"] == sha256_file(output)
   129	
   130	
   131	def test_crash_orphans_are_not_committed_and_can_be_repaired(tmp_path: Path) -> None:
   132	    output = tmp_path / "hype.mp4"
   133	    sidecar = _sidecar(output)
   134	    output.write_bytes(b"orphan")
   135	
   136	    assert read_committed_provenance(output, sidecar_path=sidecar) is None
   137	    assert not is_render_result_committed(output, sidecar_path=sidecar)
   138	
   139	    write_json_atomic(
   140	        sidecar,
   141	        {
   142	            "output": str(output.resolve()),
   143	            "timeline": "timeline",
   144	            "sha256": "0" * 64,
   145	        },
   146	    )
   147	    assert read_committed_provenance(output, sidecar_path=sidecar) is None
   148	    assert not is_render_result_committed(output, sidecar_path=sidecar)
   149	
   150	    replacement = tmp_path / "replacement.mp4"
   151	    replacement.write_bytes(b"replacement")
   152	    publish_render_result(
   153	        replacement,
   154	        {"timeline": "timeline"},
   155	        out_path=output,
   156	        sidecar_path=sidecar,
   157	        previous_outputs=(),
   158	    )
   159	    assert output.read_bytes() == b"replacement"
   160	    assert is_render_result_committed(output, sidecar_path=sidecar)
   161	
   162	
   163	def test_previous_output_cleanup_is_complete_matching_and_lock_safe(tmp_path: Path) -> None:
   164	    timeline = str((tmp_path / "hype.timeline.json").resolve())
   165	    other_timeline = str((tmp_path / "other.timeline.json").resolve())
   166	    matching = tmp_path / "runs" / "matching" / "hype.mp4"
   167	    nonmatching = tmp_path / "runs" / "nonmatching" / "hype.mp4"
   168	    missing_marker = tmp_path / "runs" / "missing-marker" / "hype.mp4"
   169	    wrong_hash = tmp_path / "runs" / "wrong-hash" / "hype.mp4"
   170	    matching_sidecar = _committed_pair(matching, contents=b"old", timeline=timeline)
   171	    nonmatching_sidecar = _committed_pair(
   172	        nonmatching, contents=b"other", timeline=other_timeline
   173	    )
   174	    missing_marker.parent.mkdir(parents=True)
   175	    missing_marker.write_bytes(b"orphan")
   176	    wrong_hash.parent.mkdir(parents=True)
   177	    wrong_hash.write_bytes(b"wrong")
   178	    wrong_hash_sidecar = _sidecar(wrong_hash)
   179	    write_json_atomic(
   180	        wrong_hash_sidecar,
   181	        {
   182	            "output": str(wrong_hash.resolve()),
   183	            "timeline": timeline,
   184	            "sha256": "f" * 64,
   185	        },
   186	    )
   187	
   188	    source = tmp_path / "new.mp4"
   189	    source.write_bytes(b"new")
   190	    live = tmp_path / "runs" / "live" / "hype.mp4"
   191	    live_sidecar = _sidecar(live)
   192	    publish_render_result(
   193	        source,
   194	        {"timeline": timeline},
   195	        out_path=live,
   196	        sidecar_path=live_sidecar,
   197	        previous_outputs=[
   198	            matching,
   199	            nonmatching,
   200	            missing_marker,
   201	            wrong_hash,
   202	            live,
   203	        ],
   204	    )
   205	
   206	    assert not matching.exists()
   207	    assert not matching_sidecar.exists()
   208	    assert nonmatching.exists()
   209	    assert nonmatching_sidecar.exists()
   210	    assert missing_marker.exists()
   211	    assert not _sidecar(missing_marker).exists()
   212	    assert wrong_hash.exists()
   213	    assert wrong_hash_sidecar.exists()
   214	    assert live.exists()
   215	    assert live_sidecar.exists()
   216	    assert is_render_result_committed(live, sidecar_path=live_sidecar)
   217	
   218	
   219	@pytest.mark.parametrize(
   220	    ("write_source", "reason"),
   221	    [
   222	        (False, "missing_artifact"),
   223	        (True, "empty_artifact"),
   224	    ],
   225	)
   226	def test_missing_or_empty_video_fails_structurally_before_rename(
   227	    tmp_path: Path,
   228	    monkeypatch: pytest.MonkeyPatch,
   229	    write_source: bool,
   230	    reason: str,
   231	) -> None:
   232	    source = tmp_path / "render.mp4"
   233	    if write_source:
   234	        source.write_bytes(b"")
   235	    output = tmp_path / "hype.mp4"
   236	    replace = Mock(side_effect=AssertionError("must not rename"))
   237	    monkeypatch.setattr(publication.os, "replace", replace)
   238	
   239	    with pytest.raises(RendererInvalidArtifactError) as caught:
   240	        publish_render_result(
   241	            source,
   242	            {"timeline": "timeline"},
   243	            out_path=output,
   244	            sidecar_path=_sidecar(output),
   245	            previous_outputs=(),
   246	        )
   247	
   248	    assert caught.value.error.kind == "invalid_artifact"
   249	    assert caught.value.error.details["reason"] == reason
   250	    replace.assert_not_called()
   251	    assert not output.exists()
   252	    assert not _sidecar(output).exists()
   253	
   254	
   255	def test_sidecar_write_failure_leaves_recoverable_uncommitted_video(
   256	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   257	) -> None:
   258	    source = tmp_path / "render.mp4"
   259	    source.write_bytes(b"complete-video")
   260	    output = tmp_path / "hype.mp4"
   261	    sidecar = _sidecar(output)
   262	
   263	    def fail_sidecar(_path: str | Path, _payload: object) -> None:
   264	        raise AtomicWriteError("synthetic sidecar failure")
   265	
   266	    monkeypatch.setattr(publication, "write_json_atomic", fail_sidecar)
   267	    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
   268	        publish_render_result(
   269	            source,
   270	            {"timeline": "timeline"},
   271	            out_path=output,
   272	            sidecar_path=sidecar,
   273	            previous_outputs=(),
   274	        )
   275	
   276	    assert not source.exists()
   277	    assert output.read_bytes() == b"complete-video"
   278	    assert not sidecar.exists()
   279	    assert not is_render_result_committed(output, sidecar_path=sidecar)

exec
/bin/zsh -lc "rg -n \"publication paths must not be symbolic|previous.*symlink|sidecar.*symlink|output.*symlink|symlink.*publication|read_committed.*symlink|publish_render_result\" tests | head -400
rg -n \"render.json|support request|schema_version.*True|schema_version.*1\\.0|JSON object\" tests/core/rendering/test_raw_command_fixture.py tests | head -300" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/integrations/test_arnold_step_adapter.py:751:        """A complete per-output CAS hit skips execution and symlinks declared outputs."""
tests/core/integrations/test_arnold_step_adapter.py:812:        """A CAS miss interns declared outputs and symlinks them back into the run dir."""
tests/core/rendering/test_publication.py:16:    publish_render_result,
tests/core/rendering/test_publication.py:48:    result = publish_render_result(
tests/core/rendering/test_publication.py:99:            publish_render_result(
tests/core/rendering/test_publication.py:152:    publish_render_result(
tests/core/rendering/test_publication.py:192:    publish_render_result(
tests/core/rendering/test_publication.py:240:        publish_render_result(
tests/core/rendering/test_publication.py:268:        publish_render_result(
tests/core/rendering/test_raw_command_fixture.py:44:RENDER_WINDOW_FRAMES = 48  # render.json: [0, 48) @ 24fps == ~2 seconds
tests/core/rendering/test_raw_command_fixture.py:138:    request_name: str = "render.json",
tests/session/test_binding_identity_config_discovery.py:255:    with pytest.raises(config.ConfigError, match="JSON object"):
tests/test_task_status_json.py:4:- ``--json`` emits exactly one JSON object with shared lifecycle fields.
tests/test_task_status_json.py:164:    """--json emits exactly one JSON object terminated by exactly one newline."""
tests/test_lifecycle_ack_json.py:311:    """--json emits exactly one JSON object terminated by exactly one newline."""
tests/test_m5b_end_state_regression.py:232:        self.assertIsInstance(data, dict, "Top-level output must be a JSON object")
tests/test_agent_cli_contract.py:75:    assert isinstance(payload, dict), f"expected JSON object, got {type(payload)!r}"
tests/migrations/sprint-3/test_inbox_migration.py:280:    assert "not a JSON object" in reason
tests/test_task_next_quiet_json.py:112:    """--json emits exactly one JSON object with all NEXT_JSON_KEYS."""
tests/timeline/test_sync_state.py:149:        with pytest.raises(SyncStateError, match="must be a JSON object"):
tests/timeline/test_sync_state.py:313:        with pytest.raises(SyncStateError, match="must be a JSON object"):
tests/timeline/test_model.py:83:        with pytest.raises(TimelineValidationError, match="JSON object"):
tests/test_stream_discipline.py:75:    """cmd_status --json emits exactly one newline-terminated JSON object on stdout."""
tests/test_lifecycle_abort_json.py:4:- ``--json`` emits exactly one JSON object with shared lifecycle fields.
tests/test_lifecycle_abort_json.py:144:    """--json emits exactly one JSON object terminated by exactly one newline."""
tests/core/experiments/test_normalize.py:1493:            "schema_version": True,
tests/core/experiments/test_evaluation.py:230:        p = _payload(schema_version=True)
tests/core/experiments/test_evaluation.py:344:        bad["schema_version"] = True
tests/test_lifecycle_skip_json.py:260:    """--json emits exactly one JSON object terminated by exactly one newline."""
tests/core/experiments/test_schema.py:863:    @pytest.mark.parametrize("schema_version", [True, 2, 1.0, "1"])
tests/core/experiments/test_schema.py:872:        experiment["schema_version"] = True
tests/test_skills.py:570:            f"schema_version: 1\nid: {pack_id}\nname: Installed Demo\nversion: 0.1.0\n",
tests/test_gateway_status_routing.py:50:    """Parse exactly one JSON object from stdout."""
tests/core/experiments/test_state.py:49:            {"schema_version": True, "kind": EXPERIMENT_REVIEW_STATE_KIND, "experiment_id": "x",
tests/core/rendering/test_raw_command_fixture.py:44:RENDER_WINDOW_FRAMES = 48  # render.json: [0, 48) @ 24fps == ~2 seconds
tests/core/rendering/test_raw_command_fixture.py:138:    request_name: str = "render.json",
tests/core/rendering/test_schema_roundtrip.py:244:        ("error boolean version", _set(error, ("schema_version",), True)),
tests/core/rendering/test_schema_roundtrip.py:300:        ("boolean version", _set(base, ("schema_version",), True)),
tests/core/rendering/test_schema_roundtrip.py:320:        ("boolean version", _set(base, ("schema_version",), True)),
tests/packs/test_packs_cli.py:873:                "schema_version: 1\nid: typo.pack\nname: Typo Pack\nversion: 0.1.0\n"
tests/packs/test_packs_cli.py:885:                "schema_version: 1\nid: typo.domain\nname: Typo Domain\nversion: 0.1.0\n"
tests/packs/test_packs_cli.py:897:                "schema_version: 1\nid: good_pack\nname: Good Pack\nversion: 0.1.0\n"
tests/test_lifecycle_start_json.py:4:- ``--json`` emits exactly one JSON object with shared lifecycle fields.
tests/test_lifecycle_start_json.py:129:    """--json outputs exactly one JSON object followed by a single newline."""
tests/test_lifecycle_start_json.py:145:    # No extraneous content on stdout beyond the JSON object + newline.
tests/fixtures/recoverability_conformance_worklist.json:1715:      "source": "print(\"open_in_reigh: timeline JSON must be a JSON object\", file=sys.stderr)",
tests/packs/test_pack_install.py:657:            "schema_version: 1\nname: Bad Pack\nversion: 0.1.0\nagent:\n  purpose: Broken\n"
tests/packs/test_pack_discovery.py:196:                "schema_version: 1\nid: external\nname: External\nversion: '1.0'\nvisibility: hidden\n",
tests/spikes/test_flock_apfs.py:57:    """Verify that every line in the file is a valid JSON object."""
tests/fixtures/renderer_packs/raw_command/backend.py:549:                f"request must be a JSON object, got {type(request).__name__}"
tests/fixtures/renderer_packs/raw_command/backend.py:567:                f"invalid support request: {exc}",
tests/packs/test_pack_yaml_schema.py:1762:        yaml_body = "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1823:            "schema_version: 1\nid: external\nname: Ext\nversion: 1.0.0\n"
tests/packs/test_pack_yaml_schema.py:1835:            "schema_version: 1\nid: external\nname: Ext\nversion: 1.0.0\n"
tests/packs/test_pack_yaml_schema.py:1846:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1860:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1870:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1884:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1895:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1911:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1931:                    "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1941:            'schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n'
tests/packs/test_pack_yaml_schema.py:1954:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1988:        yaml_body = "schema_version: 1\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:1996:            'schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n'
tests/packs/test_pack_yaml_schema.py:2034:                    "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2046:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2056:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2067:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2079:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2090:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2101:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2111:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2121:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2131:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2141:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2160:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2170:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2181:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2193:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2235:        yaml_body = "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_pack_yaml_schema.py:2250:            "schema_version: 1\nid: builtin\nname: builtin\nversion: 0.1.0\n"
tests/packs/test_packs_validate.py:195:            """schema_version: 1.0
tests/packs/test_pack_discovery_canonical.py:29:        "schema_version: 1\nid: demo_pack.summarize\nname: Summarize\nversion: 0.1.0\n",
tests/agentic/test_check_head_consistency.py:324:# FAIL — head is not a JSON object
tests/agentic/ADAPTER.md:106:  - Every line MUST be newline-terminated and contain a valid JSON object with a `"hash"` field
tests/agentic/test_adapter.py:639:        / "render.json"
tests/agentic/test_adapter.py:1481:    assert isinstance(manifest, dict), "manifest.json must be a JSON object"
tests/agentic/test_adapter.py:1671:            f"events.jsonl line {i} must be a JSON object, got {type(obj).__name__}"
tests/agentic/test_adapter.py:1706:    assert isinstance(manifest, dict), "manifest.json must be a JSON object"
tests/agentic/scenarios/executor_failure_recovery.yaml:38:          The transcript must be a JSON object with a non-empty `segments`
tests/agentic/adapter.py:569:        produces_name="render.json",
tests/agentic/checks/head_consistency.py:44:                "error": "assembly.head.json is not a JSON object",
tests/agentic/checks/isolation.py:332:                "issue": "event is not a JSON object",
tests/agentic/checks/isolation.py:408:                "issue": "event is not a JSON object",

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/publication.py | sed -n '1,360p'
git diff --unified=80 5231a233..7f7c25d5 -- astrid/core/rendering/publication.py astrid/packs/rendering/executors/render/run.py
nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1390,1505p'
rg -n \"_delete_previous_outputs|_previous_pair|publish_render_result|read_committed_provenance|out_path.*resolve|resolve\\(\\).*out_path|out_path\" astrid/packs/rendering/executors/render/run.py astrid/core/rendering/publication.py | head -240" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""Locked publication for one rendered video and its provenance sidecar.
     2	
     3	The provenance sidecar is the commit marker.  A video without a valid
     4	sidecar is deliberately visible (and therefore recoverable), but it is never
     5	considered a committed render result.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import fcntl
    11	import json
    12	import os
    13	import re
    14	import time
    15	from collections.abc import Iterable, Mapping
    16	from pathlib import Path
    17	from typing import Any
    18	
    19	from astrid.core.foundation.atomic_io import write_json_atomic
    20	from astrid.core.foundation.hash import sha256_file
    21	
    22	from .errors import raise_invalid_artifact_error
    23	
    24	try:
    25	    from filelock import FileLock, Timeout
    26	except ImportError:  # pragma: no cover - exercised only without optional dep.
    27	    FileLock = None  # type: ignore[assignment]
    28	
    29	    class Timeout(Exception):
    30	        pass
    31	
    32	
    33	_BACKEND = "astrid.core"
    34	_RECOVERY = "rerender the video and retry publication"
    35	_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
    36	
    37	
    38	class _FcntlLock:
    39	    """Small ``filelock``-compatible fallback used by the asset cache too."""
    40	
    41	    def __init__(self, path: Path) -> None:
    42	        self.path = Path(path)
    43	        self._handle: Any | None = None
    44	
    45	    def acquire(self, timeout: float | None = None) -> _FcntlLock:
    46	        self.path.parent.mkdir(parents=True, exist_ok=True)
    47	        self._handle = self.path.open("a+b")
    48	        deadline = None if timeout is None or timeout < 0 else time.monotonic() + timeout
    49	        while True:
    50	            try:
    51	                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    52	                return self
    53	            except BlockingIOError as exc:
    54	                if timeout == 0 or (deadline is not None and time.monotonic() >= deadline):
    55	                    self._handle.close()
    56	                    self._handle = None
    57	                    raise Timeout(str(self.path)) from exc
    58	                time.sleep(0.05)
    59	
    60	    def release(self) -> None:
    61	        if self._handle is None:
    62	            return
    63	        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
    64	        self._handle.close()
    65	        self._handle = None
    66	
    67	    def __enter__(self) -> _FcntlLock:
    68	        return self.acquire()
    69	
    70	    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
    71	        self.release()
    72	
    73	
    74	def _lock_for(path: Path) -> Any:
    75	    """Return the per-output lock at ``<output>.lock``."""
    76	
    77	    lock_path = Path(f"{path}.lock")
    78	    if FileLock is not None:
    79	        return FileLock(str(lock_path))
    80	    return _FcntlLock(lock_path)
    81	
    82	
    83	def _default_sidecar_path(video_path: Path) -> Path:
    84	    return Path(f"{video_path}.provenance.json")
    85	
    86	
    87	def _resolved(path: str | Path) -> Path:
    88	    return Path(path).expanduser().resolve(strict=False)
    89	
    90	
    91	def _invalid_video(video_path: Path, *, reason: str, message: str) -> None:
    92	    raise_invalid_artifact_error(
    93	        backend=_BACKEND,
    94	        message=message,
    95	        recovery_command=_RECOVERY,
    96	        details={"reason": reason, "path": str(video_path)},
    97	    )
    98	
    99	
   100	def _validate_source_video(video_path: Path) -> None:
   101	    try:
   102	        exists = video_path.is_file()
   103	    except OSError:
   104	        exists = False
   105	    if not exists:
   106	        _invalid_video(
   107	            video_path,
   108	            reason="missing_artifact",
   109	            message=f"rendered video does not exist: {video_path}",
   110	        )
   111	    try:
   112	        size = video_path.stat().st_size
   113	    except OSError:
   114	        _invalid_video(
   115	            video_path,
   116	            reason="missing_artifact",
   117	            message=f"rendered video cannot be read: {video_path}",
   118	        )
   119	    if size <= 0:
   120	        _invalid_video(
   121	            video_path,
   122	            reason="empty_artifact",
   123	            message=f"rendered video is empty: {video_path}",
   124	        )
   125	
   126	
   127	def read_committed_provenance(
   128	    video_path: str | Path,
   129	    *,
   130	    sidecar_path: str | Path | None = None,
   131	) -> dict[str, Any] | None:
   132	    """Return provenance only when *video_path* and its marker form a valid pair.
   133	
   134	    This check intentionally fails closed for missing, malformed, empty, or
   135	    hash-mismatched pairs.  Callers can then re-render or leave the orphan for
   136	    conservative recovery without mistaking it for a successful publication.
   137	    """
   138	
   139	    video = _resolved(video_path)
   140	    sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
   141	    try:
   142	        video_unresolved = Path(video_path).expanduser()
   143	        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
   144	        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
   145	            return None
   146	        if video.is_symlink() or sidecar.is_symlink():
   147	            return None
   148	        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
   149	            return None
   150	        payload = json.loads(sidecar.read_text(encoding="utf-8"))
   151	    except (OSError, ValueError, TypeError, json.JSONDecodeError):
   152	        return None
   153	    if not isinstance(payload, dict):
   154	        return None
   155	    recorded_output = payload.get("output")
   156	    if not isinstance(recorded_output, str):
   157	        return None
   158	    try:
   159	        recorded_output_path = _resolved(recorded_output)
   160	    except (OSError, RuntimeError, ValueError):
   161	        return None
   162	    if recorded_output_path != video:
   163	        return None
   164	    recorded_sha256 = payload.get("sha256")
   165	    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
   166	        return None
   167	    try:
   168	        if sha256_file(video) != recorded_sha256:
   169	            return None
   170	    except OSError:
   171	        return None
   172	    return payload
   173	
   174	
   175	def is_render_result_committed(
   176	    video_path: str | Path,
   177	    *,
   178	    sidecar_path: str | Path | None = None,
   179	) -> bool:
   180	    """Return whether the video-plus-sidecar pair is committed."""
   181	
   182	    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
   183	
   184	
   185	def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
   186	    if isinstance(candidate, Mapping):
   187	        raw_video = candidate.get("out_path", candidate.get("output"))
   188	        raw_sidecar = candidate.get("sidecar_path", candidate.get("sidecar"))
   189	        if raw_video is None:
   190	            return None
   191	        video = _resolved(raw_video)
   192	        return video, _resolved(raw_sidecar or _default_sidecar_path(video))
   193	    if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
   194	        video = _resolved(candidate[0])
   195	        return video, _resolved(candidate[1])
   196	    if isinstance(candidate, (str, os.PathLike)):
   197	        video = _resolved(candidate)
   198	        return video, _resolved(_default_sidecar_path(video))
   199	    return None
   200	
   201	
   202	def _delete_previous_outputs(
   203	    previous_outputs: Iterable[object],
   204	    *,
   205	    live_output: Path,
   206	    timeline: object,
   207	) -> None:
   208	    if not isinstance(timeline, str):
   209	        return
   210	    seen: set[Path] = set()
   211	    for candidate in previous_outputs:
   212	        try:
   213	            pair = _previous_pair(candidate)
   214	        except (OSError, RuntimeError, TypeError, ValueError):
   215	            continue
   216	        if pair is None:
   217	            continue
   218	        video, sidecar = pair
   219	        # Never delete through a symlink: neither the raw video nor the raw
   220	        # sidecar path may be a link (the resolved pair may point elsewhere).
   221	        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
   222	        raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
   223	        try:
   224	            raw_path = Path(raw_candidate).expanduser()
   225	            if raw_path.is_symlink():
   226	                continue
   227	        except (OSError, TypeError):
   228	            continue
   229	        if raw_sidecar_candidate is not None:
   230	            try:
   231	                if Path(raw_sidecar_candidate).expanduser().is_symlink():
   232	                    continue
   233	            except (OSError, TypeError):
   234	                continue
   235	        if video == live_output or video in seen:
   236	            continue
   237	        seen.add(video)
   238	
   239	        # Never wait while holding the live output lock.  Two concurrent
   240	        # publications for sibling outputs can otherwise deadlock while each
   241	        # tries to clean the other, and a locked candidate is by definition a
   242	        # live render that cleanup must preserve.
   243	        candidate_lock = _lock_for(video)
   244	        try:
   245	            candidate_lock.acquire(timeout=0)
   246	        except (Timeout, OSError):
   247	            continue
   248	        try:
   249	            provenance = read_committed_provenance(video, sidecar_path=sidecar)
   250	            if provenance is None or provenance.get("timeline") != timeline:
   251	                continue
   252	            try:
   253	                # The marker disappears first.  A crash or failure between
   254	                # these unlinks leaves an orphan, never a false committed pair.
   255	                sidecar.unlink()
   256	            except (FileNotFoundError, OSError):
   257	                continue
   258	            try:
   259	                video.unlink()
   260	            except (FileNotFoundError, OSError):
   261	                pass
   262	        finally:
   263	            candidate_lock.release()
   264	
   265	
   266	def publish_render_result(
   267	    video_path: str | Path,
   268	    provenance_payload: Mapping[str, Any],
   269	    *,
   270	    out_path: str | Path,
   271	    sidecar_path: str | Path,
   272	    previous_outputs: Iterable[object] = (),
   273	) -> Path:
   274	    """Publish one video and atomically commit its hashed provenance marker.
   275	
   276	    The source video is validated before any destination mutation.  Under the
   277	    per-output lock an old marker is invalidated, the video is moved into
   278	    place with :func:`os.replace`, and the complete sidecar is written
   279	    atomically last.  A sidecar-write failure therefore leaves a detectable,
   280	    recoverable orphan video and is propagated to the caller.
   281	    """
   282	
   283	    if not isinstance(provenance_payload, Mapping):
   284	        raise TypeError("provenance_payload must be a mapping")
   285	
   286	    source = _resolved(video_path)
   287	    output = _resolved(out_path)
   288	    sidecar = _resolved(sidecar_path)
   289	    source_unresolved = Path(video_path).expanduser()
   290	    output_unresolved = Path(out_path).expanduser()
   291	    sidecar_unresolved = Path(sidecar_path).expanduser()
   292	    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
   293	        raise_invalid_artifact_error(
   294	            backend=_BACKEND,
   295	            message="publication paths must not be symbolic links",
   296	            recovery_command=_RECOVERY,
   297	        )
   298	    _validate_source_video(source)
   299	
   300	    output.parent.mkdir(parents=True, exist_ok=True)
   301	    sidecar.parent.mkdir(parents=True, exist_ok=True)
   302	    with _lock_for(output):
   303	        # Validate again after waiting for the lock so a moved or truncated
   304	        # staging artifact can never be reported as successfully published.
   305	        _validate_source_video(source)
   306	
   307	        # Invalidate the previous marker BEFORE the first destination
   308	        # mutation: a crash can then leave an orphan video (recoverable) but
   309	        # can never leave a stale marker claiming the new bytes are committed.
   310	        sidecar.unlink(missing_ok=True)
   311	        os.replace(source, output)
   312	        digest = sha256_file(output)
   313	        committed_payload = dict(provenance_payload)
   314	        committed_payload["output"] = str(output)
   315	        committed_payload["sha256"] = digest
   316	        write_json_atomic(sidecar, committed_payload)
   317	
   318	        # Cleanup happens only after the new pair is committed and while its
   319	        # lock remains held.  Candidate locks are non-blocking (see above).
   320	        _delete_previous_outputs(
   321	            previous_outputs,
   322	            live_output=output,
   323	            timeline=committed_payload.get("timeline"),
   324	        )
   325	
   326	        # Do not report success unless the bytes and marker we just wrote are
   327	        # still a complete pair under the same lock.
   328	        if read_committed_provenance(output, sidecar_path=sidecar) is None:
   329	            _invalid_video(
   330	                output,
   331	                reason="uncommitted_artifact",
   332	                message=f"published video has no valid provenance commit marker: {output}",
   333	            )
   334	    return output
   335	
   336	
   337	__all__ = [
   338	    "is_render_result_committed",
   339	    "publish_render_result",
   340	    "read_committed_provenance",
   341	]
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index b261a09f..514dfa6c 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -139,169 +139,176 @@ def read_committed_provenance(
     video = _resolved(video_path)
     sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
     try:
         video_unresolved = Path(video_path).expanduser()
         sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
         if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
             return None
         if video.is_symlink() or sidecar.is_symlink():
             return None
         if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
             return None
         payload = json.loads(sidecar.read_text(encoding="utf-8"))
     except (OSError, ValueError, TypeError, json.JSONDecodeError):
         return None
     if not isinstance(payload, dict):
         return None
     recorded_output = payload.get("output")
     if not isinstance(recorded_output, str):
         return None
     try:
         recorded_output_path = _resolved(recorded_output)
     except (OSError, RuntimeError, ValueError):
         return None
     if recorded_output_path != video:
         return None
     recorded_sha256 = payload.get("sha256")
     if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
         return None
     try:
         if sha256_file(video) != recorded_sha256:
             return None
     except OSError:
         return None
     return payload
 
 
 def is_render_result_committed(
     video_path: str | Path,
     *,
     sidecar_path: str | Path | None = None,
 ) -> bool:
     """Return whether the video-plus-sidecar pair is committed."""
 
     return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
 
 
 def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
     if isinstance(candidate, Mapping):
         raw_video = candidate.get("out_path", candidate.get("output"))
         raw_sidecar = candidate.get("sidecar_path", candidate.get("sidecar"))
         if raw_video is None:
             return None
         video = _resolved(raw_video)
         return video, _resolved(raw_sidecar or _default_sidecar_path(video))
     if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
         video = _resolved(candidate[0])
         return video, _resolved(candidate[1])
     if isinstance(candidate, (str, os.PathLike)):
         video = _resolved(candidate)
         return video, _resolved(_default_sidecar_path(video))
     return None
 
 
 def _delete_previous_outputs(
     previous_outputs: Iterable[object],
     *,
     live_output: Path,
     timeline: object,
 ) -> None:
     if not isinstance(timeline, str):
         return
     seen: set[Path] = set()
     for candidate in previous_outputs:
         try:
             pair = _previous_pair(candidate)
         except (OSError, RuntimeError, TypeError, ValueError):
             continue
         if pair is None:
             continue
         video, sidecar = pair
-        # Never delete through a symlink: the raw candidate path must not be
-        # a link (the resolved pair may point elsewhere entirely).
+        # Never delete through a symlink: neither the raw video nor the raw
+        # sidecar path may be a link (the resolved pair may point elsewhere).
         raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
+        raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
         try:
             raw_path = Path(raw_candidate).expanduser()
             if raw_path.is_symlink():
                 continue
         except (OSError, TypeError):
             continue
+        if raw_sidecar_candidate is not None:
+            try:
+                if Path(raw_sidecar_candidate).expanduser().is_symlink():
+                    continue
+            except (OSError, TypeError):
+                continue
         if video == live_output or video in seen:
             continue
         seen.add(video)
 
         # Never wait while holding the live output lock.  Two concurrent
         # publications for sibling outputs can otherwise deadlock while each
         # tries to clean the other, and a locked candidate is by definition a
         # live render that cleanup must preserve.
         candidate_lock = _lock_for(video)
         try:
             candidate_lock.acquire(timeout=0)
         except (Timeout, OSError):
             continue
         try:
             provenance = read_committed_provenance(video, sidecar_path=sidecar)
             if provenance is None or provenance.get("timeline") != timeline:
                 continue
             try:
                 # The marker disappears first.  A crash or failure between
                 # these unlinks leaves an orphan, never a false committed pair.
                 sidecar.unlink()
             except (FileNotFoundError, OSError):
                 continue
             try:
                 video.unlink()
             except (FileNotFoundError, OSError):
                 pass
         finally:
             candidate_lock.release()
 
 
 def publish_render_result(
     video_path: str | Path,
     provenance_payload: Mapping[str, Any],
     *,
     out_path: str | Path,
     sidecar_path: str | Path,
     previous_outputs: Iterable[object] = (),
 ) -> Path:
     """Publish one video and atomically commit its hashed provenance marker.
 
     The source video is validated before any destination mutation.  Under the
     per-output lock an old marker is invalidated, the video is moved into
     place with :func:`os.replace`, and the complete sidecar is written
     atomically last.  A sidecar-write failure therefore leaves a detectable,
     recoverable orphan video and is propagated to the caller.
     """
 
     if not isinstance(provenance_payload, Mapping):
         raise TypeError("provenance_payload must be a mapping")
 
     source = _resolved(video_path)
     output = _resolved(out_path)
     sidecar = _resolved(sidecar_path)
     source_unresolved = Path(video_path).expanduser()
     output_unresolved = Path(out_path).expanduser()
     sidecar_unresolved = Path(sidecar_path).expanduser()
     if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
         raise_invalid_artifact_error(
             backend=_BACKEND,
             message="publication paths must not be symbolic links",
             recovery_command=_RECOVERY,
         )
     _validate_source_video(source)
 
     output.parent.mkdir(parents=True, exist_ok=True)
     sidecar.parent.mkdir(parents=True, exist_ok=True)
     with _lock_for(output):
         # Validate again after waiting for the lock so a moved or truncated
         # staging artifact can never be reported as successfully published.
         _validate_source_video(source)
 
         # Invalidate the previous marker BEFORE the first destination
         # mutation: a crash can then leave an orphan video (recoverable) but
         # can never leave a stale marker claiming the new bytes are committed.
         sidecar.unlink(missing_ok=True)
         os.replace(source, output)
         digest = sha256_file(output)
         committed_payload = dict(provenance_payload)
         committed_payload["output"] = str(output)
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index 3f294f01..c42443a4 100644
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -1379,161 +1379,161 @@ def _render_with_publication_context(
                     "npx",
                     "remotion",
                     "render",
                     composition_id,
                     "--props",
                     str(props_path),
                     "--output",
                     str(staged_video),
                     "--allow-html-in-canvas",
                 ],
                 cwd=str(project_dir),
                 env=build_child_subprocess_env(explicit_env=remotion_env_additions),
                 capture_output=True,
                 check=False,
                 text=True,
             )
             if result.returncode != 0:
                 stderr_tail = _stderr_tail(result.stderr)
                 message = f"Remotion render failed with exit code {result.returncode}"
                 if stderr_tail:
                     message = f"{message}\n{stderr_tail}"
                 raise RuntimeError(message)
             provenance = _render_provenance_payload(
                 out_path,
                 engine="remotion",
                 timeline_path=timeline_path,
                 assets_path=assets_path,
                 project_dir=project_dir,
                 composition_id=composition_id,
                 theme_path=theme_path,
                 active_theme=theme_for_props,
                 registry_state=registry_state,
                 stage_summary=stage_summary,
             )
             output = publish_render_result(
                 staged_video,
                 provenance,
                 out_path=out_path,
                 sidecar_path=_render_provenance_sidecar_path(out_path),
                 previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
             )
         finally:
             props_path.unlink(missing_ok=True)
             shutil.rmtree(staged_public_root, ignore_errors=True)
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_remotion")
         assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_remotion")
         render_id = audit.register_asset(
             kind="render",
             path=output,
             label="Rendered video",
             parents=[timeline_id, assets_id],
             stage="render_remotion",
             metadata={"composition": composition_id},
         )
         audit.register_node(
             stage="render_remotion",
             label="Render Remotion timeline",
             parents=[timeline_id, assets_id],
             outputs=[render_id],
             metadata={"composition": composition_id, "project_dir": str(project_dir)},
         )
     return output
 
 
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
 ) -> Path:
     """Render privately and publish one locked video-plus-sidecar pair."""
 
-    out_path = out_path.resolve()
+    out_path = Path(out_path)
     previous_outputs = (
         ()
         if keep_previous_renders
         else _previous_render_outputs_for_timeline(out_path, timeline_path)
     )
     publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
     try:
         return _render_with_publication_context(
             timeline_path,
             assets_path,
             out_path,
             engine=engine,
             project_dir=project_dir,
             composition_id=composition_id,
             theme_path=theme_path,
             min_free_gb=min_free_gb,
         )
     finally:
         _PUBLICATION_PREVIOUS_OUTPUTS.reset(publication_token)
 
 
 def main(argv: Sequence[str] | None = None) -> int:
     parser = argparse.ArgumentParser()
     parser.add_argument("--timeline", type=Path, required=True)
     parser.add_argument("--assets", type=Path)
     parser.add_argument("--out", type=Path, required=True)
     parser.add_argument("--engine", choices=("remotion", "ffmpeg", "hybrid"), default="remotion")
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
         if args.assets is None:
             with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
                 assets_path = Path(tmp_text) / "hype.assets.json"
                 _write_empty_asset_registry(assets_path)
                 output = render(
                     args.timeline,
                     assets_path,
                     args.out,
                     engine=args.engine,
                     project_dir=args.project_dir,
                     composition_id=args.composition,
                     theme_path=args.theme,
                     min_free_gb=args.min_free_gb,
                     keep_previous_renders=args.keep_previous_renders,
                 )
         else:
             output = render(
                 args.timeline,
                 args.assets,
                 args.out,
                 engine=args.engine,
                 project_dir=args.project_dir,
                 composition_id=args.composition,
                 theme_path=args.theme,
                 min_free_gb=args.min_free_gb,
                 keep_previous_renders=args.keep_previous_renders,
             )
     except Exception as exc:  # pragma: no cover - CLI path
         print(str(exc), file=sys.stderr)
         return 1
     print(output)
     return 0
 
 
 if __name__ == "__main__":
  1390	                env=build_child_subprocess_env(explicit_env=remotion_env_additions),
  1391	                capture_output=True,
  1392	                check=False,
  1393	                text=True,
  1394	            )
  1395	            if result.returncode != 0:
  1396	                stderr_tail = _stderr_tail(result.stderr)
  1397	                message = f"Remotion render failed with exit code {result.returncode}"
  1398	                if stderr_tail:
  1399	                    message = f"{message}\n{stderr_tail}"
  1400	                raise RuntimeError(message)
  1401	            provenance = _render_provenance_payload(
  1402	                out_path,
  1403	                engine="remotion",
  1404	                timeline_path=timeline_path,
  1405	                assets_path=assets_path,
  1406	                project_dir=project_dir,
  1407	                composition_id=composition_id,
  1408	                theme_path=theme_path,
  1409	                active_theme=theme_for_props,
  1410	                registry_state=registry_state,
  1411	                stage_summary=stage_summary,
  1412	            )
  1413	            output = publish_render_result(
  1414	                staged_video,
  1415	                provenance,
  1416	                out_path=out_path,
  1417	                sidecar_path=_render_provenance_sidecar_path(out_path),
  1418	                previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
  1419	            )
  1420	        finally:
  1421	            props_path.unlink(missing_ok=True)
  1422	            shutil.rmtree(staged_public_root, ignore_errors=True)
  1423	    audit = AuditContext.from_env()
  1424	    if audit is not None:
  1425	        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_remotion")
  1426	        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_remotion")
  1427	        render_id = audit.register_asset(
  1428	            kind="render",
  1429	            path=output,
  1430	            label="Rendered video",
  1431	            parents=[timeline_id, assets_id],
  1432	            stage="render_remotion",
  1433	            metadata={"composition": composition_id},
  1434	        )
  1435	        audit.register_node(
  1436	            stage="render_remotion",
  1437	            label="Render Remotion timeline",
  1438	            parents=[timeline_id, assets_id],
  1439	            outputs=[render_id],
  1440	            metadata={"composition": composition_id, "project_dir": str(project_dir)},
  1441	        )
  1442	    return output
  1443	
  1444	
  1445	def render(
  1446	    timeline_path: Path,
  1447	    assets_path: Path,
  1448	    out_path: Path,
  1449	    *,
  1450	    engine: str = "remotion",
  1451	    project_dir: Path | None = None,
  1452	    composition_id: str = "TimelineComposition",
  1453	    theme_path: Path | None = None,
  1454	    min_free_gb: float | None = None,
  1455	    keep_previous_renders: bool = False,
  1456	) -> Path:
  1457	    """Render privately and publish one locked video-plus-sidecar pair."""
  1458	
  1459	    out_path = Path(out_path)
  1460	    previous_outputs = (
  1461	        ()
  1462	        if keep_previous_renders
  1463	        else _previous_render_outputs_for_timeline(out_path, timeline_path)
  1464	    )
  1465	    publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
  1466	    try:
  1467	        return _render_with_publication_context(
  1468	            timeline_path,
  1469	            assets_path,
  1470	            out_path,
  1471	            engine=engine,
  1472	            project_dir=project_dir,
  1473	            composition_id=composition_id,
  1474	            theme_path=theme_path,
  1475	            min_free_gb=min_free_gb,
  1476	        )
  1477	    finally:
  1478	        _PUBLICATION_PREVIOUS_OUTPUTS.reset(publication_token)
  1479	
  1480	
  1481	def main(argv: Sequence[str] | None = None) -> int:
  1482	    parser = argparse.ArgumentParser()
  1483	    parser.add_argument("--timeline", type=Path, required=True)
  1484	    parser.add_argument("--assets", type=Path)
  1485	    parser.add_argument("--out", type=Path, required=True)
  1486	    parser.add_argument("--engine", choices=("remotion", "ffmpeg", "hybrid"), default="remotion")
  1487	    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
  1488	    parser.add_argument("--composition", default="TimelineComposition")
  1489	    parser.add_argument("--min-free-gb", type=float, default=None, help="Abort before rendering unless this much free disk is available near --out.")
  1490	    parser.add_argument(
  1491	        "--keep-previous-renders",
  1492	        nargs="?",
  1493	        const=True,
  1494	        default=False,
  1495	        type=_parse_bool_arg,
  1496	        help="Preserve previous sibling hype.mp4 outputs for the same timeline.",
  1497	    )
  1498	    parser.add_argument(
  1499	        "--theme",
  1500	        type=Path,
  1501	        default=REPO_ROOT / "themes" / "banodoco-default" / "theme.json",
  1502	    )
  1503	    args = parser.parse_args(argv)
  1504	    try:
  1505	        if args.assets is None:
astrid/core/rendering/publication.py:127:def read_committed_provenance(
astrid/core/rendering/publication.py:182:    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
astrid/core/rendering/publication.py:185:def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
astrid/core/rendering/publication.py:187:        raw_video = candidate.get("out_path", candidate.get("output"))
astrid/core/rendering/publication.py:202:def _delete_previous_outputs(
astrid/core/rendering/publication.py:213:            pair = _previous_pair(candidate)
astrid/core/rendering/publication.py:221:        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
astrid/core/rendering/publication.py:249:            provenance = read_committed_provenance(video, sidecar_path=sidecar)
astrid/core/rendering/publication.py:266:def publish_render_result(
astrid/core/rendering/publication.py:270:    out_path: str | Path,
astrid/core/rendering/publication.py:287:    output = _resolved(out_path)
astrid/core/rendering/publication.py:290:    output_unresolved = Path(out_path).expanduser()
astrid/core/rendering/publication.py:320:        _delete_previous_outputs(
astrid/core/rendering/publication.py:328:        if read_committed_provenance(output, sidecar_path=sidecar) is None:
astrid/core/rendering/publication.py:339:    "publish_render_result",
astrid/core/rendering/publication.py:340:    "read_committed_provenance",
astrid/packs/rendering/executors/render/run.py:35:from astrid.core.rendering.publication import publish_render_result
astrid/packs/rendering/executors/render/run.py:298:def _render_ffmpeg_media_to_path(timeline_path: Path, assets_path: Path, out_path: Path) -> Path:
astrid/packs/rendering/executors/render/run.py:408:    out_path.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/executors/render/run.py:430:            str(out_path),
astrid/packs/rendering/executors/render/run.py:434:    return out_path
astrid/packs/rendering/executors/render/run.py:440:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:446:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:447:    out_path.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/executors/render/run.py:449:        prefix=f".{out_path.name}.publication-",
astrid/packs/rendering/executors/render/run.py:450:        dir=str(out_path.parent),
astrid/packs/rendering/executors/render/run.py:452:        staged_video = Path(publication_tmp) / out_path.name
astrid/packs/rendering/executors/render/run.py:455:            out_path,
astrid/packs/rendering/executors/render/run.py:466:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:469:            out_path=out_path,
astrid/packs/rendering/executors/render/run.py:470:            sidecar_path=_render_provenance_sidecar_path(out_path),
astrid/packs/rendering/executors/render/run.py:611:def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
astrid/packs/rendering/executors/render/run.py:645:            str(out_path),
astrid/packs/rendering/executors/render/run.py:651:def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
astrid/packs/rendering/executors/render/run.py:659:        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
astrid/packs/rendering/executors/render/run.py:661:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:662:    out_path.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/executors/render/run.py:663:    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(out_path.parent)) as tmp:
astrid/packs/rendering/executors/render/run.py:674:            segment_out_path = segment_dir / "segment.mp4"
astrid/packs/rendering/executors/render/run.py:681:                    segment_out_path,
astrid/packs/rendering/executors/render/run.py:688:                    segment_out_path,
astrid/packs/rendering/executors/render/run.py:692:                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
astrid/packs/rendering/executors/render/run.py:695:            segment_paths.append(segment_out_path)
astrid/packs/rendering/executors/render/run.py:696:        staged_video = tmp_dir / "final" / out_path.name
astrid/packs/rendering/executors/render/run.py:700:            out_path,
astrid/packs/rendering/executors/render/run.py:713:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:716:            out_path=out_path,
astrid/packs/rendering/executors/render/run.py:717:            sidecar_path=_render_provenance_sidecar_path(out_path),
astrid/packs/rendering/executors/render/run.py:727:            path=out_path,
astrid/packs/rendering/executors/render/run.py:835:def _render_asset_stage_hash(timeline_path: Path, assets_path: Path, out_path: Path) -> str:
astrid/packs/rendering/executors/render/run.py:844:    digest.update(str(out_path.resolve()).encode("utf-8"))
astrid/packs/rendering/executors/render/run.py:961:def _render_provenance_sidecar_path(out_path: Path) -> Path:
astrid/packs/rendering/executors/render/run.py:962:    return Path(f"{out_path}.provenance.json")
astrid/packs/rendering/executors/render/run.py:966:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:976:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:977:    if out_path.name != "hype.mp4":
astrid/packs/rendering/executors/render/run.py:979:    run_dir = out_path.parent
astrid/packs/rendering/executors/render/run.py:987:        candidates.append(candidate_run_dir / out_path.name)
astrid/packs/rendering/executors/render/run.py:1012:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:1030:        "output": str(out_path.resolve()),
astrid/packs/rendering/executors/render/run.py:1073:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:1088:        out_path,
astrid/packs/rendering/executors/render/run.py:1101:    sidecar_path = _render_provenance_sidecar_path(out_path)
astrid/packs/rendering/executors/render/run.py:1156:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:1185:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1186:    out_path.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/executors/render/run.py:1207:        prefix=f".{out_path.name}.publication-",
astrid/packs/rendering/executors/render/run.py:1208:        dir=str(out_path.parent),
astrid/packs/rendering/executors/render/run.py:1210:        staged_video = Path(publication_tmp) / out_path.name
astrid/packs/rendering/executors/render/run.py:1213:            out_path,
astrid/packs/rendering/executors/render/run.py:1231:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1234:            out_path=out_path,
astrid/packs/rendering/executors/render/run.py:1235:            sidecar_path=_render_provenance_sidecar_path(out_path),
astrid/packs/rendering/executors/render/run.py:1282:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:1290:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1294:        out_path,
astrid/packs/rendering/executors/render/run.py:1305:            out_path,
astrid/packs/rendering/executors/render/run.py:1312:        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
astrid/packs/rendering/executors/render/run.py:1316:        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
astrid/packs/rendering/executors/render/run.py:1321:    _require_free_space(out_path.parent, min_free_gb)
astrid/packs/rendering/executors/render/run.py:1322:    props_path = (out_path.parent / ".remotion-props.json").resolve()
astrid/packs/rendering/executors/render/run.py:1323:    render_hash = _render_asset_stage_hash(timeline_path, assets_path, out_path)
astrid/packs/rendering/executors/render/run.py:1357:            out_path.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/executors/render/run.py:1360:                    prefix=f".{out_path.name}.publication-",
astrid/packs/rendering/executors/render/run.py:1361:                    dir=str(out_path.parent),
astrid/packs/rendering/executors/render/run.py:1364:            staged_video = Path(publication_tmp) / out_path.name
astrid/packs/rendering/executors/render/run.py:1402:                out_path,
astrid/packs/rendering/executors/render/run.py:1413:            output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1416:                out_path=out_path,
astrid/packs/rendering/executors/render/run.py:1417:                sidecar_path=_render_provenance_sidecar_path(out_path),
astrid/packs/rendering/executors/render/run.py:1448:    out_path: Path,
astrid/packs/rendering/executors/render/run.py:1459:    out_path = Path(out_path)
astrid/packs/rendering/executors/render/run.py:1463:        else _previous_render_outputs_for_timeline(out_path, timeline_path)
astrid/packs/rendering/executors/render/run.py:1470:            out_path,

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1260,1425p'
nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '420,490p'
nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '640,730p'
nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1140,1250p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1260	                "engine": "ffmpeg",
  1261	                "specialization": audio_reactive_colour.ADAPTER_ID,
  1262	                "event_count": len(spec.events),
  1263	                "marker_sha256": spec.marker_sha256,
  1264	            },
  1265	        )
  1266	        audit.register_node(
  1267	            stage="render_ffmpeg_audio_reactive_colour",
  1268	            label="Render audio-reactive colour timeline with FFmpeg",
  1269	            parents=[timeline_id, assets_id],
  1270	            outputs=[render_id],
  1271	            metadata={
  1272	                "engine": "ffmpeg",
  1273	                "specialization": audio_reactive_colour.ADAPTER_ID,
  1274	            },
  1275	        )
  1276	    return output
  1277	
  1278	
  1279	def _render_with_publication_context(
  1280	    timeline_path: Path,
  1281	    assets_path: Path,
  1282	    out_path: Path,
  1283	    *,
  1284	    engine: str = "remotion",
  1285	    project_dir: Path | None = None,
  1286	    composition_id: str = "TimelineComposition",
  1287	    theme_path: Path | None = None,
  1288	    min_free_gb: float | None = None,
  1289	) -> Path:
  1290	    out_path = out_path.resolve()
  1291	    audio_reactive_output = _render_audio_reactive_colour_if_supported(
  1292	        timeline_path,
  1293	        assets_path,
  1294	        out_path,
  1295	        project_dir=project_dir,
  1296	        composition_id=composition_id,
  1297	        theme_path=theme_path,
  1298	    )
  1299	    if audio_reactive_output is not None:
  1300	        return audio_reactive_output
  1301	    if engine == "hybrid":
  1302	        return _render_hybrid(
  1303	            timeline_path,
  1304	            assets_path,
  1305	            out_path,
  1306	            project_dir=project_dir,
  1307	            composition_id=composition_id,
  1308	            theme_path=theme_path,
  1309	            min_free_gb=min_free_gb,
  1310	        )
  1311	    if engine == "ffmpeg":
  1312	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
  1313	    if engine != "remotion":
  1314	        raise ValueError(f"Unsupported render engine: {engine}")
  1315	    if _can_render_with_ffmpeg_media(timeline_path, assets_path):
  1316	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
  1317	    project_dir = project_dir or (REPO_ROOT / "remotion")
  1318	    _validate_project_dir(project_dir)
  1319	    _regenerate_element_registries(project_dir, theme_path)
  1320	    registry_state = _effective_registry_state(theme_path)
  1321	    _require_free_space(out_path.parent, min_free_gb)
  1322	    props_path = (out_path.parent / ".remotion-props.json").resolve()
  1323	    render_hash = _render_asset_stage_hash(timeline_path, assets_path, out_path)
  1324	    staged_public_root = project_dir / "public" / "astrid-effects" / render_hash
  1325	    with ExitStack() as asset_lifecycle:
  1326	        try:
  1327	            materializer = asset_lifecycle.enter_context(AssetMaterializer(assets_path))
  1328	            asset_server = None
  1329	            if materializer.needs_server:
  1330	                try:
  1331	                    asset_server = asset_lifecycle.enter_context(
  1332	                        InvocationAssetServer(materializer.staging_dir)
  1333	                    )
  1334	                except OSError as exc:
  1335	                    raise RuntimeError(
  1336	                        f"Permission denied (1100): local HTTP asset server blocked: {exc}"
  1337	                    ) from exc
  1338	            resolved_registry = materializer.resolved_registry(asset_server)
  1339	            resolved_theme = theme_path or (WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json")
  1340	            theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
  1341	            # The timeline references a theme by slug + optional theme_overrides;
  1342	            # theme.visual.canvas is the source of truth for Remotion calculateMetadata.
  1343	            merged_props = {
  1344	                "timeline": _serialize_timeline(
  1345	                    timeline_path,
  1346	                    default_theme=str(theme_for_props.get("id") or "banodoco-default"),
  1347	                ),
  1348	                "assets": resolved_registry,
  1349	                "theme": theme_for_props,
  1350	            }
  1351	            stage_summary = _stage_effect_assets_for_timeline(
  1352	                merged_props["timeline"],
  1353	                project_dir=project_dir,
  1354	                theme_path=theme_path,
  1355	                render_hash=render_hash,
  1356	            )
  1357	            out_path.parent.mkdir(parents=True, exist_ok=True)
  1358	            publication_tmp = asset_lifecycle.enter_context(
  1359	                TemporaryDirectory(
  1360	                    prefix=f".{out_path.name}.publication-",
  1361	                    dir=str(out_path.parent),
  1362	                )
  1363	            )
  1364	            staged_video = Path(publication_tmp) / out_path.name
  1365	            props_path.write_text(json.dumps(merged_props), encoding="utf-8")
  1366	            # Build the Remotion launch env from the canonical safe base plus the
  1367	            # Astrid runtime markers it propagates. We do NOT spread os.environ:
  1368	            # the only Node/Remotion additions are the safe-base PATH/HOME/TMPDIR
  1369	            # that npx + the headless renderer need, and any caller-provided
  1370	            # composition source override declared as a build-tool variable.
  1371	            remotion_env_additions: dict[str, str] = {}
  1372	            composition_src = (
  1373	                project_dir / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
  1374	            )
  1375	            if composition_src.is_dir():
  1376	                remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
  1377	            result = subprocess.run(
  1378	                [
  1379	                    "npx",
  1380	                    "remotion",
  1381	                    "render",
  1382	                    composition_id,
  1383	                    "--props",
  1384	                    str(props_path),
  1385	                    "--output",
  1386	                    str(staged_video),
  1387	                    "--allow-html-in-canvas",
  1388	                ],
  1389	                cwd=str(project_dir),
  1390	                env=build_child_subprocess_env(explicit_env=remotion_env_additions),
  1391	                capture_output=True,
  1392	                check=False,
  1393	                text=True,
  1394	            )
  1395	            if result.returncode != 0:
  1396	                stderr_tail = _stderr_tail(result.stderr)
  1397	                message = f"Remotion render failed with exit code {result.returncode}"
  1398	                if stderr_tail:
  1399	                    message = f"{message}\n{stderr_tail}"
  1400	                raise RuntimeError(message)
  1401	            provenance = _render_provenance_payload(
  1402	                out_path,
  1403	                engine="remotion",
  1404	                timeline_path=timeline_path,
  1405	                assets_path=assets_path,
  1406	                project_dir=project_dir,
  1407	                composition_id=composition_id,
  1408	                theme_path=theme_path,
  1409	                active_theme=theme_for_props,
  1410	                registry_state=registry_state,
  1411	                stage_summary=stage_summary,
  1412	            )
  1413	            output = publish_render_result(
  1414	                staged_video,
  1415	                provenance,
  1416	                out_path=out_path,
  1417	                sidecar_path=_render_provenance_sidecar_path(out_path),
  1418	                previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
  1419	            )
  1420	        finally:
  1421	            props_path.unlink(missing_ok=True)
  1422	            shutil.rmtree(staged_public_root, ignore_errors=True)
  1423	    audit = AuditContext.from_env()
  1424	    if audit is not None:
  1425	        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_remotion")
   420	            "[aout]",
   421	            "-c:v",
   422	            "copy" if copy_video_input is not None else "libx264",
   423	            *(["-preset", "veryfast", "-crf", "20"] if copy_video_input is None else []),
   424	            "-c:a",
   425	            "aac",
   426	            "-b:a",
   427	            "192k",
   428	            "-movflags",
   429	            "+faststart",
   430	            str(out_path),
   431	        ],
   432	        check=True,
   433	    )
   434	    return out_path
   435	
   436	
   437	def _render_ffmpeg_media(
   438	    timeline_path: Path,
   439	    assets_path: Path,
   440	    out_path: Path,
   441	    *,
   442	    _previous_outputs: Sequence[Path] | None = None,
   443	) -> Path:
   444	    """Render FFmpeg output privately, then publish the committed pair."""
   445	
   446	    out_path = out_path.resolve()
   447	    out_path.parent.mkdir(parents=True, exist_ok=True)
   448	    with TemporaryDirectory(
   449	        prefix=f".{out_path.name}.publication-",
   450	        dir=str(out_path.parent),
   451	    ) as publication_tmp:
   452	        staged_video = Path(publication_tmp) / out_path.name
   453	        _render_ffmpeg_media_to_path(timeline_path, assets_path, staged_video)
   454	        provenance = _render_provenance_payload(
   455	            out_path,
   456	            engine="ffmpeg",
   457	            timeline_path=timeline_path,
   458	            assets_path=assets_path,
   459	            project_dir=REPO_ROOT / "remotion",
   460	            composition_id="TimelineComposition",
   461	            theme_path=None,
   462	            active_theme=None,
   463	            registry_state=_effective_registry_state(None),
   464	            stage_summary={"root": None, "effects": []},
   465	        )
   466	        output = publish_render_result(
   467	            staged_video,
   468	            provenance,
   469	            out_path=out_path,
   470	            sidecar_path=_render_provenance_sidecar_path(out_path),
   471	            previous_outputs=(
   472	                _PUBLICATION_PREVIOUS_OUTPUTS.get()
   473	                if _previous_outputs is None
   474	                else _previous_outputs
   475	            ),
   476	        )
   477	
   478	    audit = AuditContext.from_env()
   479	    if audit is not None:
   480	        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_ffmpeg")
   481	        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_ffmpeg")
   482	        render_id = audit.register_asset(
   483	            kind="render",
   484	            path=output,
   485	            label="Rendered video",
   486	            parents=[timeline_id, assets_id],
   487	            stage="render_ffmpeg",
   488	            metadata={"engine": "ffmpeg"},
   489	        )
   490	        audit.register_node(
   640	            "aac",
   641	            "-b:a",
   642	            "192k",
   643	            "-movflags",
   644	            "+faststart",
   645	            str(out_path),
   646	        ],
   647	        check=True,
   648	    )
   649	
   650	
   651	def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
   652	    if not timeline_path.exists():
   653	        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
   654	    if not assets_path.exists():
   655	        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
   656	    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   657	    segments = _hybrid_segments(timeline_data)
   658	    if len(segments) == 1 and segments[0]["engine"] == "ffmpeg":
   659	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
   660	
   661	    out_path = out_path.resolve()
   662	    out_path.parent.mkdir(parents=True, exist_ok=True)
   663	    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(out_path.parent)) as tmp:
   664	        tmp_dir = Path(tmp)
   665	        segment_paths: list[Path] = []
   666	        segment_provenance: list[dict[str, Any]] = []
   667	        for index, segment in enumerate(segments):
   668	            engine = str(segment["engine"])
   669	            start = float(segment["from"])
   670	            end = float(segment["to"])
   671	            segment_dir = tmp_dir / f"{index:04d}-{engine}"
   672	            segment_dir.mkdir(parents=True, exist_ok=True)
   673	            segment_timeline_path = segment_dir / "timeline.json"
   674	            segment_out_path = segment_dir / "segment.mp4"
   675	            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
   676	            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
   677	            if engine == "ffmpeg":
   678	                _render_ffmpeg_media(
   679	                    segment_timeline_path,
   680	                    assets_path,
   681	                    segment_out_path,
   682	                    _previous_outputs=(),
   683	                )
   684	            else:
   685	                render(
   686	                    segment_timeline_path,
   687	                    assets_path,
   688	                    segment_out_path,
   689	                    engine="remotion",
   690	                    **remotion_kwargs,
   691	                )
   692	                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
   693	                if sidecar_path.exists():
   694	                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
   695	            segment_paths.append(segment_out_path)
   696	        staged_video = tmp_dir / "final" / out_path.name
   697	        staged_video.parent.mkdir(parents=True, exist_ok=True)
   698	        _concat_segments(segment_paths, staged_video)
   699	        provenance = _render_provenance_payload(
   700	            out_path,
   701	            engine="hybrid",
   702	            timeline_path=timeline_path,
   703	            assets_path=assets_path,
   704	            project_dir=Path(remotion_kwargs.get("project_dir") or (REPO_ROOT / "remotion")),
   705	            composition_id=str(remotion_kwargs.get("composition_id") or "TimelineComposition"),
   706	            theme_path=remotion_kwargs.get("theme_path"),
   707	            active_theme=None,
   708	            registry_state=_effective_registry_state(remotion_kwargs.get("theme_path")),
   709	            stage_summary={"root": None, "effects": []},
   710	            segments=segments,
   711	            segment_provenance=segment_provenance,
   712	        )
   713	        output = publish_render_result(
   714	            staged_video,
   715	            provenance,
   716	            out_path=out_path,
   717	            sidecar_path=_render_provenance_sidecar_path(out_path),
   718	            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
   719	        )
   720	
   721	    audit = AuditContext.from_env()
   722	    if audit is not None:
   723	        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_hybrid")
   724	        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_hybrid")
   725	        render_id = audit.register_asset(
   726	            kind="render",
   727	            path=out_path,
   728	            label="Rendered video",
   729	            parents=[timeline_id, assets_id],
   730	            stage="render_hybrid",
  1140	    theme_path: Path | None,
  1141	) -> ElementDefinition | None:
  1142	    effects, _aliases = _effect_registry_for_assets(theme_path)
  1143	    element = effects.get(audio_reactive_colour.EFFECT_ID)
  1144	    if (
  1145	        element is None
  1146	        or element.metadata.get("ffmpegAdapter")
  1147	        != audio_reactive_colour.ADAPTER_ID
  1148	    ):
  1149	        return None
  1150	    return element
  1151	
  1152	
  1153	def _render_audio_reactive_colour_if_supported(
  1154	    timeline_path: Path,
  1155	    assets_path: Path,
  1156	    out_path: Path,
  1157	    *,
  1158	    project_dir: Path | None,
  1159	    composition_id: str,
  1160	    theme_path: Path | None,
  1161	) -> Path | None:
  1162	    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
  1163	    clips = timeline_data.get("clips")
  1164	    if (
  1165	        not isinstance(clips, list)
  1166	        or len(clips) != 2
  1167	        or sum(
  1168	            isinstance(clip, dict)
  1169	            and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
  1170	            for clip in clips
  1171	        )
  1172	        != 1
  1173	    ):
  1174	        return None
  1175	    element = _audio_reactive_ffmpeg_element(theme_path)
  1176	    if element is None:
  1177	        return None
  1178	    registry = timeline.load_registry(assets_path)
  1179	    spec = audio_reactive_colour.match_and_validate(
  1180	        timeline_data, registry, assets_path
  1181	    )
  1182	    if spec is None:
  1183	        return None
  1184	
  1185	    out_path = out_path.resolve()
  1186	    out_path.parent.mkdir(parents=True, exist_ok=True)
  1187	    stage_summary = {
  1188	        "root": None,
  1189	        "effects": [
  1190	            {
  1191	                "effect_id": element.id,
  1192	                "source_pack_id": _source_pack_id(element),
  1193	                "source": element.source,
  1194	                "element_root": str(element.root),
  1195	                "clip_ids": [
  1196	                    str(clip.get("id"))
  1197	                    for clip in timeline_data.get("clips", [])
  1198	                    if isinstance(clip, dict)
  1199	                    and clip.get("clipType") == element.id
  1200	                ],
  1201	                "staged_asset_ids": [],
  1202	                "staged_assets": {},
  1203	            }
  1204	        ],
  1205	    }
  1206	    with TemporaryDirectory(
  1207	        prefix=f".{out_path.name}.publication-",
  1208	        dir=str(out_path.parent),
  1209	    ) as publication_tmp:
  1210	        staged_video = Path(publication_tmp) / out_path.name
  1211	        rendered_video = audio_reactive_colour.render(spec, staged_video)
  1212	        provenance = _render_provenance_payload(
  1213	            out_path,
  1214	            engine="ffmpeg",
  1215	            timeline_path=timeline_path,
  1216	            assets_path=assets_path,
  1217	            project_dir=project_dir or (REPO_ROOT / "remotion"),
  1218	            composition_id=composition_id,
  1219	            theme_path=theme_path,
  1220	            active_theme=None,
  1221	            registry_state=_effective_registry_state(theme_path),
  1222	            stage_summary=stage_summary,
  1223	        )
  1224	        provenance["ffmpeg_specialization"] = audio_reactive_colour.ADAPTER_ID
  1225	        provenance["audio_reactive_colour"] = {
  1226	            "event_count": len(spec.events),
  1227	            "fps": spec.fps,
  1228	            "frame_count": spec.total_frames,
  1229	            "marker_sha256": spec.marker_sha256,
  1230	        }
  1231	        output = publish_render_result(
  1232	            rendered_video,
  1233	            provenance,
  1234	            out_path=out_path,
  1235	            sidecar_path=_render_provenance_sidecar_path(out_path),
  1236	            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
  1237	        )
  1238	
  1239	    audit = AuditContext.from_env()
  1240	    if audit is not None:
  1241	        timeline_id = audit.register_asset(
  1242	            kind="timeline",
  1243	            path=timeline_path,
  1244	            label="Audio-reactive render timeline",
  1245	            stage="render_ffmpeg_audio_reactive_colour",
  1246	        )
  1247	        assets_id = audit.register_asset(
  1248	            kind="assets_registry",
  1249	            path=assets_path,
  1250	            label="Audio-reactive asset registry",

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/requests/support.json | sed -n '1,100p'
git diff --unified=80 5231a233..7f7c25d5 -- tests/fixtures/renderer_packs/raw_command/backend.py tests/fixtures/renderer_packs/raw_command/requests/render.json astrid/core/media.py
file tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc
git check-ignore -v tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc || true
git ls-files tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	{
     2	  "schema_version": 1,
     3	  "timeline_path": "timeline.json",
     4	  "assets_registry_path": null,
     5	  "output_name": "raw_command.mp4",
     6	  "window": {
     7	    "start_frame": 0,
     8	    "end_frame": 48,
     9	    "fps_rational": [24, 1],
    10	    "source_range": null,
    11	    "speed": 1.0
    12	  },
    13	  "audio": "rendered",
    14	  "profile": {
    15	    "width": 1920,
    16	    "height": 1080,
    17	    "fps_rational": [24, 1],
    18	    "time_base": [1, 12288],
    19	    "container": "mp4",
    20	    "video_codec": "h264",
    21	    "video_profile": null,
    22	    "video_level": null,
    23	    "pixel_format": "yuv420p",
    24	    "audio_codec": "sowt",
    25	    "audio_sample_rate": 48000,
    26	    "audio_channel_layout": "stereo",
    27	    "duration_tolerance": 1
    28	  },
    29	  "backend_config": {
    30	    "raw_command.renderer": {
    31	      "mode": "solid"
    32	    }
    33	  },
    34	  "metadata": {
    35	    "fixture": "raw_command",
    36	    "purpose": "T2.2 raw protocol fixture support"
    37	  }
    38	}
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/media.py b/astrid/core/media.py
index cfc72297..e7c6a92d 100644
--- a/astrid/core/media.py
+++ b/astrid/core/media.py
@@ -141,161 +141,174 @@ def _container_from_format(format_name: str | None, file_path: str | Path) -> st
     if "mp4" in names:
         return "mp4"
     if "webm" in names:
         return "webm"
     if "matroska" in names:
         return "matroska"
     if "mov" in names:
         return "mov"
     return sorted(names)[0] if names else None
 
 
 def _parse_ffprobe_payload(data: dict[str, Any], file_path: str | Path) -> MediaProbe:
     probe = MediaProbe(_raw=data)
 
     fmt = data.get("format", {})
     if not isinstance(fmt, Mapping):
         fmt = {}
     probe.format_name = _nonempty_string(fmt.get("format_name"))
     probe.container = _container_from_format(probe.format_name, file_path)
 
     duration_value = fmt.get("duration")
     probe.duration_rational = _duration_rational(duration_value)
     if probe.duration_rational is not None:
         probe.duration_seconds = float(Fraction(*probe.duration_rational))
 
     streams = data.get("streams", [])
     if not isinstance(streams, list):
         streams = []
 
     video_stream: Mapping[str, Any] | None = None
     audio_stream: Mapping[str, Any] | None = None
     for stream in streams:
         if not isinstance(stream, Mapping):
             continue
         stream_type = stream.get("codec_type")
         if stream_type == "video" and video_stream is None:
             disposition = stream.get("disposition")
             attached_picture = (
                 isinstance(disposition, Mapping)
                 and disposition.get("attached_pic") in {1, True, "1"}
             )
             if not attached_picture:
                 video_stream = stream
         elif stream_type == "audio" and audio_stream is None:
             audio_stream = stream
 
     probe.video_stream_present = video_stream is not None
     probe.audio_stream_present = audio_stream is not None
 
     if video_stream is not None:
         probe.width = _int_or_none(video_stream.get("width"), minimum=1)
         probe.height = _int_or_none(video_stream.get("height"), minimum=1)
         if probe.width is not None and probe.height is not None:
             probe.resolution = f"{probe.width}x{probe.height}"
 
         fps_value = video_stream.get("avg_frame_rate")
         fps_rational = _positive_rational(fps_value)
         if fps_rational is None:
             fps_rational = _positive_rational(video_stream.get("r_frame_rate"))
         probe.fps_rational = fps_rational
         if fps_rational is not None:
             probe.fps = float(Fraction(*fps_rational))
 
         probe.time_base = _positive_rational(video_stream.get("time_base"))
         probe.video_codec = _nonempty_string(video_stream.get("codec_name"))
         probe.video_profile = _nonempty_string(video_stream.get("profile"))
         level = video_stream.get("level")
         if level is not None and str(level).strip() not in {"", "-99"}:
             probe.video_level = str(level).strip()
         probe.pixel_format = _nonempty_string(video_stream.get("pix_fmt"))
 
         # Some containers omit format.duration while exposing stream.duration.
         if probe.duration_rational is None:
             probe.duration_rational = _duration_rational(video_stream.get("duration"))
             if probe.duration_rational is not None:
                 probe.duration_seconds = float(Fraction(*probe.duration_rational))
 
     if audio_stream is not None:
         probe.audio_codec = _nonempty_string(audio_stream.get("codec_name"))
         probe.audio_sample_rate = _int_or_none(audio_stream.get("sample_rate"), minimum=1)
-        probe.audio_channel_layout = _nonempty_string(audio_stream.get("channel_layout"))
+        probe.audio_channel_layout = _nonempty_string(
+            audio_stream.get("channel_layout")
+        )
+        # Some containers (e.g. QuickTime sowt) report channel counts without
+        # a channel_layout; derive the standard layout so strict profile
+        # validation can still compare audio placement.
+        if probe.audio_channel_layout is None:
+            channels = _int_or_none(audio_stream.get("channels"), minimum=1)
+            probe.audio_channel_layout = {
+                1: "mono",
+                2: "stereo",
+                6: "5.1",
+                8: "7.1",
+            }.get(channels or 0)
         if probe.duration_rational is None:
             probe.duration_rational = _duration_rational(audio_stream.get("duration"))
             if probe.duration_rational is not None:
                 probe.duration_seconds = float(Fraction(*probe.duration_rational))
 
     return probe
 
 
 def _ffprobe_metadata(
     file_path: str | Path,
     *,
     timeout: float,
     strict: bool,
 ) -> MediaProbe:
     ffprobe_exe = shutil.which("ffprobe")
     if ffprobe_exe is None:
         if strict:
             raise MediaProbeError("ffprobe is not available on PATH")
         return MediaProbe()
 
     try:
         proc = subprocess.run(
             [
                 ffprobe_exe,
                 "-v",
                 "quiet",
                 "-print_format",
                 "json",
                 "-show_format",
                 "-show_streams",
                 str(file_path),
             ],
             capture_output=True,
             text=True,
             timeout=timeout,
         )
         if proc.returncode != 0:
             if strict:
                 diagnostic = (proc.stderr or "").strip()
                 suffix = f": {diagnostic}" if diagnostic else ""
                 raise MediaProbeError(f"ffprobe failed with exit {proc.returncode}{suffix}")
             return MediaProbe()
         data = json.loads(proc.stdout)
         if not isinstance(data, dict):
             raise ValueError("ffprobe JSON root is not an object")
     except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
         if strict:
             raise MediaProbeError(f"ffprobe could not inspect {file_path}: {exc}") from exc
         return MediaProbe()
 
     try:
         return _parse_ffprobe_payload(data, file_path)
     except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
         if strict:
             raise MediaProbeError(
                 f"ffprobe returned malformed metadata for {file_path}: {exc}"
             ) from exc
         return MediaProbe()
 
 
 def ffprobe_metadata(
     file_path: str | Path,
     *,
     timeout: float = 30.0,
 ) -> MediaProbe:
     """Extract duration, fps, resolution, width, and height via ffprobe.
 
     Returns a :class:`MediaProbe` with best-effort fields populated.
     If ffprobe is not available or fails, all fields are ``None``.
     """
     return _ffprobe_metadata(file_path, timeout=timeout, strict=False)
 
 
 def ffprobe_metadata_strict(
     file_path: str | Path,
     *,
     timeout: float = 30.0,
 ) -> MediaProbe:
     """Return ffprobe metadata or raise :class:`MediaProbeError`.
 
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 2910f543..37973595 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -222,350 +222,363 @@ def _mvhd(duration: int) -> bytes:
         + struct.pack(">II", 0, 0)
         + _matrix()
         + b"\x00" * 24
         + struct.pack(">I", 3)                       # next_track_ID
     )
     return _fullbox(b"mvhd", 0, payload)
 
 
 def _tkhd(track_id: int, duration: int, volume: int, width: int, height: int) -> bytes:
     payload = (
         struct.pack(">II", 0, 0)
         + struct.pack(">I", track_id)
         + struct.pack(">I", 0)
         + struct.pack(">I", duration)
         + struct.pack(">II", 0, 0)
         + struct.pack(">Hh", 0, 0)
         + struct.pack(">H", volume)
         + struct.pack(">H", 0)
         + _matrix()
         + struct.pack(">II", width << 16, height << 16)
     )
     return _fullbox(b"tkhd", 0x00000007, payload)
 
 
 def _mdhd(timescale: int, duration: int) -> bytes:
     payload = (
         struct.pack(">IIII", 0, 0, timescale, duration)
         + struct.pack(">HH", 0x55C4, 0)  # language "und"
     )
     return _fullbox(b"mdhd", 0, payload)
 
 
 def _hdlr(handler: bytes, name: bytes) -> bytes:
     payload = struct.pack(">I", 0) + handler + b"\x00" * 12 + name + b"\x00"
     return _fullbox(b"hdlr", 0, payload)
 
 
 def _dinf() -> bytes:
     dref = _fullbox(b"dref", 0, struct.pack(">I", 1) + _fullbox(b"url ", 1, b""))
     return _box(b"dinf", dref)
 
 
 def _avc1_entry(sps: bytes, pps: bytes) -> bytes:
     avcc = (
         bytes([1, 66, 0xC0, 40, 0xFF, 0xE1])
         + struct.pack(">H", len(sps))
         + sps
         + bytes([1])
         + struct.pack(">H", len(pps))
         + pps
     )
     visual = (
         b"\x00" * 6
         + struct.pack(">H", 1)             # data_reference_index
         + struct.pack(">HH", 0, 0)
         + b"\x00" * 12
         + struct.pack(">HH", WIDTH, HEIGHT)
         + struct.pack(">II", 0x00480000, 0x00480000)  # 72 dpi
         + struct.pack(">I", 0)
         + struct.pack(">H", 1)             # frame_count
         + b"RawCommand\x00" + b"\x00" * 21  # compressorname (32 bytes)
         + struct.pack(">Hh", 24, -1)       # depth 24, pre_defined -1
     )
     return _box(b"avc1", visual + _box(b"avcC", avcc))
 
 
 def _sowt_entry() -> bytes:
     wave = _box(
         b"wave",
         _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
     )
     audio = (
         b"\x00" * 6
         + struct.pack(">H", 1)             # data_reference_index
         + struct.pack(">HH", 0, 0)
         + struct.pack(">I", 0)             # vendor
         + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
         + struct.pack(">HH", 0, 0)         # compressionid, packetsize
         + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
     )
-    return _box(b"sowt", audio + wave)
+    # QuickTime channel layout atom so ffprobe reports a concrete
+    # channel_layout (stereo = layout tag 3) instead of None.
+    chan = _box(
+        b"chan",
+        struct.pack(">I", 0)   # version/flags
+        + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)
+        + struct.pack(">I", 0),  # bitmap
+    )
+    return _box(b"sowt", audio + wave + chan)
 
 
 def _sample_tables(
     *,
     video_frames: int,
     video_sizes: list[int],
     video_chunk_offset: int,
     audio_bytes: bytes,
     audio_samples: int,
     audio_chunk_offset: int,
 ) -> bytes:
     stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
     stts_v = _fullbox(
         b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", video_frames, SAMPLES_PER_FRAME)
     )
     stsc_v = _fullbox(
         b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, video_frames, 1)
     )
     stsz_v = _fullbox(
         b"stsz", 0, struct.pack(">II", 0, video_frames)
         + b"".join(struct.pack(">I", size) for size in video_sizes)
     )
     stco_v = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", video_chunk_offset))
 
     stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
     stts_a = _fullbox(
         b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
     )
     stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
     stsz_a = _fullbox(
         b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
     )
     stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))
 
     video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
     audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
     return video_stbl, audio_stbl
 
 
 def _build_mp4(frames: int) -> bytes:
     """Return a deterministic MP4: `frames` H.264 IDR frames + PCM silence."""
     video_chunk = bytearray()
     video_sizes: list[int] = []
     for frame_index in range(frames):
         nal = _idr_slice_nal(frame_index)
         sample = struct.pack(">I", len(nal)) + nal
         video_chunk += sample
         video_sizes.append(len(sample))
     video_chunk = bytes(video_chunk)
 
     audio_samples = frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])
     audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))
 
     ftyp = _ftyp()
     video_chunk_offset = len(ftyp) + 8
     audio_chunk_offset = video_chunk_offset + len(video_chunk)
 
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
-    if request.get("schema_version") != 1:
+    version = request.get("schema_version")
+    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
         raise ValueError(
-            f"unsupported request schema_version {request.get('schema_version')!r}; expected 1"
+            f"unsupported request schema_version {version!r}; expected 1"
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
 
 
 def _support(result_path: Path) -> int:
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
     parser.add_argument("--request", required=True, help="absolute path to request JSON")
     parser.add_argument("--result", required=True, help="absolute path to result JSON")
     args = parser.parse_args(argv)
 
     request_path = Path(args.request)
     result_path = Path(args.result)
     try:
         request = json.loads(request_path.read_text(encoding="utf-8"))
+        if not isinstance(request, dict):
+            raise TypeError(
+                f"request must be a JSON object, got {type(request).__name__}"
+            )
     except Exception as exc:
         _write_error(
             result_path,
             "protocol",
             f"cannot read request JSON from {request_path}: {exc}",
             {"error_type": type(exc).__name__},
         )
         return 0
 
     if args.verb == "support":
         try:
             _validate_request(request)
         except ValueError as exc:
             _write_error(
                 result_path,
                 "protocol",
                 f"invalid support request: {exc}",
                 {"error_type": type(exc).__name__},
             )
             return 0
         return _support(result_path)
     if args.verb in ("plan", "finalize"):
         _write_error(
             result_path,
             "unsupported",
             f"{BACKEND_ID} only implements render and support",
             {"verb": args.verb},
         )
         return 0
     return _render(request, result_path, request_path)
 
 
 if __name__ == "__main__":
     raise SystemExit(main(sys.argv[1:]))
diff --git a/tests/fixtures/renderer_packs/raw_command/requests/render.json b/tests/fixtures/renderer_packs/raw_command/requests/render.json
index 41d98db2..ea881967 100644
--- a/tests/fixtures/renderer_packs/raw_command/requests/render.json
+++ b/tests/fixtures/renderer_packs/raw_command/requests/render.json
@@ -1,38 +1,47 @@
 {
   "schema_version": 1,
   "timeline_path": "timeline.json",
   "assets_registry_path": null,
   "output_name": "raw_command.mp4",
   "window": {
     "start_frame": 0,
     "end_frame": 48,
-    "fps_rational": [24, 1],
+    "fps_rational": [
+      24,
+      1
+    ],
     "source_range": null,
     "speed": 1.0
   },
   "audio": "rendered",
   "profile": {
     "width": 1920,
     "height": 1080,
-    "fps_rational": [24, 1],
-    "time_base": [1, 12288],
+    "fps_rational": [
+      24,
+      1
+    ],
+    "time_base": [
+      1,
+      12288
+    ],
     "container": "mp4",
     "video_codec": "h264",
     "video_profile": null,
     "video_level": null,
     "pixel_format": "yuv420p",
-    "audio_codec": "sowt",
+    "audio_codec": "pcm_s16le",
     "audio_sample_rate": 48000,
     "audio_channel_layout": "stereo",
     "duration_tolerance": 1
   },
   "backend_config": {
     "raw_command.renderer": {
       "mode": "solid"
     }
   },
   "metadata": {
     "fixture": "raw_command",
     "purpose": "T2.2 raw protocol fixture render"
   }
 }
tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc: data
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc

codex
The media stream itself now probes as 1920×1080 H.264 with 48 kHz stereo PCM, and the strict parser’s two-channel fallback yields `stereo`. I’ve also found that the publication boundary needs tracing through every caller: preserving the raw path in `render()` is ineffective if a downstream helper resolves it again before calling the guard.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); p=b\"\\x00\\x00\\x00\\x01\"; sys.stdout.buffer.write(p+m[\"_sps_nal\"]()+p+m[\"_pps_nal\"]()+p+m[\"_idr_slice_nal\"](0))' | ffprobe -v error -f h264 -show_entries stream=codec_name,width,height,coded_width,coded_height,pix_fmt,profile,level -of json pipe:0
PYTHONDONTWRITEBYTECODE=1 python -c 'from astrid.core.media import _parse_ffprobe_payload; p=_parse_ffprobe_payload({\"format\":{\"format_name\":\"mov,mp4,m4a,3gp,3g2,mj2\",\"duration\":\"2.000000\"},\"streams\":[{\"codec_type\":\"video\",\"codec_name\":\"h264\",\"width\":1920,\"height\":1080,\"avg_frame_rate\":\"24/1\",\"time_base\":\"1/12288\",\"pix_fmt\":\"yuv420p\"},{\"codec_type\":\"audio\",\"codec_name\":\"pcm_s16le\",\"sample_rate\":\"48000\",\"channels\":2}]}, \"fixture.mp4\"); print(p.width,p.height,p.fps_rational,p.time_base,p.container,p.video_codec,p.pixel_format,p.audio_codec,p.audio_sample_rate,p.audio_channel_layout,p.duration_rational)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 348ms:
{
    "programs": [

    ],
    "stream_groups": [

    ],
    "streams": [
        {
            "codec_name": "h264",
            "profile": "Constrained Baseline",
            "width": 1920,
            "height": 1080,
            "coded_width": 1920,
            "coded_height": 1080,
            "pix_fmt": "yuv420p",
            "level": 40
        }
    ]
}
1920 1080 (24, 1) (1, 12288) mp4 h264 yuv420p pcm_s16le 48000 stereo (2, 1)

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '940,1020p'
rg -n \"_PUBLICATION_PREVIOUS_OUTPUTS|previous_outputs\" astrid/packs/rendering/executors/render/run.py | head -120
git show 7f7c25d5:.oracle/checkins/batch-2-r1.md | tail -n 40" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   940	    for index, effect_id in clip_effect_ids.items():
   941	        clip = clips[index]
   942	        if isinstance(clip, dict) and staged_by_effect[effect_id]:
   943	            _inject_clip_asset_params(clip, staged_by_effect[effect_id])
   944	    return {
   945	        "root": str(public_root),
   946	        "effects": [
   947	            {
   948	                "effect_id": effect_id,
   949	                "source_pack_id": _source_pack_id(effects[effect_id]),
   950	                "source": effects[effect_id].source,
   951	                "element_root": str(effects[effect_id].root),
   952	                "clip_ids": sorted(clip_ids_by_effect.get(effect_id, ())),
   953	                "staged_asset_ids": sorted(staged_by_effect[effect_id]),
   954	                "staged_assets": dict(sorted(staged_by_effect[effect_id].items())),
   955	            }
   956	            for effect_id in sorted(used_effect_ids)
   957	        ],
   958	    }
   959	
   960	
   961	def _render_provenance_sidecar_path(out_path: Path) -> Path:
   962	    return Path(f"{out_path}.provenance.json")
   963	
   964	
   965	def _previous_render_outputs_for_timeline(
   966	    out_path: Path,
   967	    timeline_path: Path,
   968	) -> tuple[Path, ...]:
   969	    """Discover legacy sibling outputs; publication validates before deleting.
   970	
   971	    The timeline argument remains part of the helper boundary for compatibility
   972	    with the legacy cleanup call site.  Filtering now happens under each
   973	    candidate's publication lock using the committed sidecar.
   974	    """
   975	
   976	    out_path = out_path.resolve()
   977	    if out_path.name != "hype.mp4":
   978	        return ()
   979	    run_dir = out_path.parent
   980	    runs_dir = run_dir.parent
   981	    if runs_dir.name != "runs" or not runs_dir.is_dir():
   982	        return ()
   983	    candidates: list[Path] = []
   984	    for candidate_run_dir in runs_dir.iterdir():
   985	        if not candidate_run_dir.is_dir() or candidate_run_dir == run_dir:
   986	            continue
   987	        candidates.append(candidate_run_dir / out_path.name)
   988	    return tuple(candidates)
   989	
   990	
   991	def _active_pack_order_for_provenance() -> list[dict[str, Any]]:
   992	    return [
   993	        {
   994	            "id": discovered.id,
   995	            "source_kind": discovered.source_kind,
   996	            "priority_index": discovered.priority_index,
   997	            "root": str(discovered.pack_dir),
   998	        }
   999	        for discovered in discover_pack_metadata(project_root=REPO_ROOT)
  1000	    ]
  1001	
  1002	
  1003	def _active_theme_for_provenance(theme_path: Path | None, active_theme: dict[str, Any] | None) -> dict[str, Any] | None:
  1004	    theme_id = active_theme.get("id") if isinstance(active_theme, dict) else None
  1005	    if theme_path is None:
  1006	        return {"id": theme_id or "banodoco-default", "path": None}
  1007	    resolved = _resolve_theme_path(theme_path)
  1008	    return {"id": theme_id or resolved.parent.name, "path": str(resolved)}
  1009	
  1010	
  1011	def _render_provenance_payload(
  1012	    out_path: Path,
  1013	    *,
  1014	    engine: str,
  1015	    timeline_path: Path,
  1016	    assets_path: Path,
  1017	    project_dir: Path,
  1018	    composition_id: str,
  1019	    theme_path: Path | None,
  1020	    active_theme: dict[str, Any] | None,
43:_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
44:    "render_publication_previous_outputs",
442:    _previous_outputs: Sequence[Path] | None = None,
471:            previous_outputs=(
472:                _PUBLICATION_PREVIOUS_OUTPUTS.get()
473:                if _previous_outputs is None
474:                else _previous_outputs
682:                    _previous_outputs=(),
718:            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
1236:            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
1418:                previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
1460:    previous_outputs = (
1465:    publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
1478:        _PUBLICATION_PREVIOUS_OUTPUTS.reset(publication_token)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
    27	    "duration_tolerance": 1
    28	  },
    29	  "backend_config": {
    30	    "raw_command.renderer": {
    17	    "fps_rational": [24, 1],
    18	    "time_base": [1, 12288],
    19	    "container": "mp4",
    20	    "video_codec": "h264",
    21	    "video_profile": null,
    22	    "video_level": null,
    23	    "pixel_format": "yuv420p",
    24	    "audio_codec": "sowt",
    25	    "audio_sample_rate": 48000,
    26	    "audio_channel_layout": "stereo",
    27	    "duration_tolerance": 1
    28	  },
    29	  "backend_config": {
    30	    "raw_command.renderer": {

codex
- Transport cleanup can still leak a process group on non-timeout `communicate()` failures, and repeated `KeyboardInterrupt` can escape polling/drain paths before reap. A SIGTERM-ignoring child survived direct injection. [transport.py:237](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:237), [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461)

- The raw fixture still fails strict profile validation. The request declares `sowt` while the result declares `pcm_s16le`; fresh ffprobe also reports no `channel_layout`, producing `audio_profile_mismatch`/`incomplete_probe`. [render.json:24](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/requests/render.json:24), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481), [artifacts.py:469](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:469)

- `support` validation remains non-strict: `True` and `1.0` pass as schema version `1`, while non-object JSON raises uncaught `AttributeError` instead of returning `protocol`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)

- Production publishing still follows output symlinks because `render()` resolves `out_path` before the new unresolved-path guard sees it; replacement then targets the symlink destination. [run.py:1459](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1459), [publication.py:282](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:282)

- Previous-output cleanup checks only the raw video path. It resolves sidecars first, so a sidecar symlink remains invisible and cleanup can unlink its resolved target and the video. [publication.py:185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:185), [publication.py:219](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:219), [publication.py:248](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:248)
tokens used
282,690
- Transport cleanup can still leak a process group on non-timeout `communicate()` failures, and repeated `KeyboardInterrupt` can escape polling/drain paths before reap. A SIGTERM-ignoring child survived direct injection. [transport.py:237](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:237), [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461)

- The raw fixture still fails strict profile validation. The request declares `sowt` while the result declares `pcm_s16le`; fresh ffprobe also reports no `channel_layout`, producing `audio_profile_mismatch`/`incomplete_probe`. [render.json:24](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/requests/render.json:24), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481), [artifacts.py:469](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:469)

- `support` validation remains non-strict: `True` and `1.0` pass as schema version `1`, while non-object JSON raises uncaught `AttributeError` instead of returning `protocol`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)

- Production publishing still follows output symlinks because `render()` resolves `out_path` before the new unresolved-path guard sees it; replacement then targets the symlink destination. [run.py:1459](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1459), [publication.py:282](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:282)

- Previous-output cleanup checks only the raw video path. It resolves sidecars first, so a sidecar symlink remains invisible and cleanup can unlink its resolved target and the video. [publication.py:185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:185), [publication.py:219](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:219), [publication.py:248](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:248)

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'exec(\"\"\"import signal\\nfrom unittest.mock import patch\\nfrom astrid.core.rendering.transport import _terminate_process_group\\nclass BrokenProcess:\\n    pid=424242\\n    returncode=None\\n    def __init__(self): self.communicate_calls=0; self.kill_calls=0\\n    def communicate(self,*args,**kwargs): self.communicate_calls+=1; raise RuntimeError(\\\"broken pipe drain\\\")\\n    def kill(self): self.kill_calls+=1\\np=BrokenProcess(); signals=[]\\nwith patch(\\\"astrid.core.rendering.transport._signal_process_group\\\", side_effect=lambda _p,sig: signals.append(sig)):\\n    try: _terminate_process_group(p, grace=0.01)\\n    except BaseException as exc: print(type(exc).__name__,str(exc),p.communicate_calls,p.kill_calls,signals)\\n\"\"\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 92ms:
RuntimeError broken pipe drain 1 0 [<Signals.SIGTERM: 15>]

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'exec(\"\"\"import signal,subprocess\\nfrom unittest.mock import patch\\nfrom astrid.core.rendering.transport import _terminate_process_group\\nclass InterruptedProcess:\\n    pid=424243\\n    returncode=None\\n    def __init__(self): self.communicate_calls=0; self.kill_calls=0\\n    def communicate(self,*args,**kwargs): self.communicate_calls+=1; raise subprocess.TimeoutExpired(\\\"x\\\",0.01)\\n    def kill(self): self.kill_calls+=1\\np=InterruptedProcess(); signals=[]\\nwith patch(\\\"astrid.core.rendering.transport._signal_process_group\\\", side_effect=lambda _p,sig: signals.append(sig)), patch(\\\"astrid.core.rendering.transport._process_group_exists\\\", return_value=True), patch(\\\"astrid.core.rendering.transport.time.sleep\\\", side_effect=KeyboardInterrupt):\\n    try: _terminate_process_group(p, grace=0.01)\\n    except BaseException as exc: print(type(exc).__name__,p.communicate_calls,p.kill_calls,signals)\\n\"\"\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 104ms:
KeyboardInterrupt 1 0 [<Signals.SIGTERM: 15>, <Signals.SIGKILL: 9>]

exec
/bin/zsh -lc "rg -n \"audio_codec|video_codec|profile.*codec|ffprobe|canonical profile|SupportReport|support\" docs/contracts/render-backend-v1.md .oracle/plan.md .oracle/tasklist.md astrid/core/rendering/profile.py astrid/core/rendering/artifacts.py | head -360
nl -ba docs/contracts/render-backend-v1.md | sed -n '30,190p'
nl -ba astrid/core/rendering/artifacts.py | sed -n '350,510p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/tasklist.md:21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
.oracle/tasklist.md:28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
.oracle/tasklist.md:32:- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
.oracle/tasklist.md:37:- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
.oracle/tasklist.md:46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
.oracle/tasklist.md:52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
.oracle/tasklist.md:59:- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
.oracle/tasklist.md:60:- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
.oracle/tasklist.md:61:- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
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
astrid/core/rendering/profile.py:249:    """Resolve the canonical profile shared by planning and finalization.
astrid/core/rendering/profile.py:283:        video_codec="h264",
astrid/core/rendering/profile.py:287:        audio_codec="aac" if rendered_audio else None,
docs/contracts/render-backend-v1.md:67:| `operations` | Unique supported operations. A renderer must contain `render`, a planner `plan`, and a finalizer `finalize`; `support` is optional. |
docs/contracts/render-backend-v1.md:69:| `capabilities` | Coarse static discovery hints. Missing hints mean unknown/unsupported; a support probe is authoritative. |
docs/contracts/render-backend-v1.md:76:whole-timeline and window support, output-profile labels, and possible audio
docs/contracts/render-backend-v1.md:77:ownership modes. Planner hints cover named policies and fallback support.
docs/contracts/render-backend-v1.md:80:sensitive `SupportReport`.
docs/contracts/render-backend-v1.md:91:operations: [render, support]
docs/contracts/render-backend-v1.md:97:  supports_full_timeline: true
docs/contracts/render-backend-v1.md:98:  supports_windows: true
docs/contracts/render-backend-v1.md:119:<command...> support  --request <absolute-request.json> --result <absolute-result.json>
docs/contracts/render-backend-v1.md:129:| `support` | `request.json` | `support.json` |
docs/contracts/render-backend-v1.md:178:- non-empty `container`, `video_codec`, and `pixel_format`;
docs/contracts/render-backend-v1.md:179:- nullable `video_profile` and `video_level` when the codec does not expose
docs/contracts/render-backend-v1.md:181:- the optional audio trio `audio_codec`, `audio_sample_rate`, and
docs/contracts/render-backend-v1.md:200:- nullable `profile` (`null` means the host resolves the canonical profile);
docs/contracts/render-backend-v1.md:320:`SupportReport` contains:
docs/contracts/render-backend-v1.md:323:- `supported`, the request-sensitive verdict;
docs/contracts/render-backend-v1.md:330:An unsupported report should contain at least one actionable reason. Support
docs/contracts/render-backend-v1.md:333:an unsupported report into support. Every segment's required report must name
docs/contracts/render-backend-v1.md:353:  alias_chain, override, support_decision}`;
docs/contracts/render-backend-v1.md:356:  support_decision, trust_eligibility}`;
docs/contracts/render-backend-v1.md:358:  override, trust_eligibility, support_decision}`.
docs/contracts/render-backend-v1.md:364:the derived source/install trust decision; `support_decision` is a versioned
docs/contracts/render-backend-v1.md:365:`SupportReport` or `null` (when no request-sensitive probe ran, e.g. for a
docs/contracts/render-backend-v1.md:366:finalizer). Every non-null `support_decision.backend` MUST equal the
docs/contracts/render-backend-v1.md:369:SHA-256 digests. There is no parallel `segment.backend`, `segment.support`,
docs/contracts/render-backend-v1.md:377:segment use the canonical profile's exact rational FPS (equivalent but
docs/contracts/render-backend-v1.md:416:| `kind` | One of `protocol`, `unsupported`, `binary_missing`, `timeout`, `interrupted`, `invalid_artifact`, or `internal`. |
docs/contracts/render-backend-v1.md:422:Unknown, missing, boolean, non-integer, or unsupported versions on requests,
docs/contracts/render-backend-v1.md:423:support reports, plans, finalize requests, successful results, and error
docs/contracts/render-backend-v1.md:425:missing authoritative results. Unsupported timelines use `unsupported`; a
docs/contracts/render-backend-v1.md:442:   and supported protocol version.
docs/contracts/render-backend-v1.md:445:4. Obtain static and, where available, request-sensitive support evidence.
docs/contracts/render-backend-v1.md:475:distinct source pack, manifest, alias/override, support, and input-hash evidence
docs/contracts/render-backend-v1.md:477:alias/override/trust/support evidence as renderer records. Rendered artifacts
docs/contracts/render-backend-v1.md:527:`source_pack`, `manifest_digest`, `support_decision`, and `input_hashes` remain
docs/contracts/render-backend-v1.md:544:- support report and render plan, when present;
docs/contracts/render-backend-v1.md:561:`RenderRequest`, `SupportReport`, `RenderPlan`, `FinalizeRequest`, successful
docs/contracts/render-backend-v1.md:589:7. **Unsupported requests fail closed by default.** Fallback occurs only when
docs/contracts/render-backend-v1.md:609:    renderer implements one render operation. Request-sensitive support and
docs/contracts/render-backend-v1.md:617:    A request-sensitive support probe returns structured supported/unsupported
.oracle/plan.md:24:   <command...> render|support|plan|finalize \
.oracle/plan.md:37:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/plan.md:80:    - `RenderRequest`, `SupportReport`, `RenderPlan`, and half-open frame windows;
.oracle/plan.md:87:  - Add versioned JSON Schemas for request, result, support, plan, finalization, and the three manifest types.
.oracle/plan.md:140:  - Gate: render/support success, unsupported response, malformed JSON, missing result/output, nonzero exit, timeout, SIGINT cleanup, untrusted env discovery, trusted install, and static no-import inspection all pass.
.oracle/plan.md:147:  - Serve only invocation-staged assets from `127.0.0.1`; bind the server directly to port `0`, retain Range support, start inside the managed context, and always shut down, close, and join it.
.oracle/plan.md:177:  - Replace validator side effects with an explicit `SupportReport`.
.oracle/plan.md:179:    - unsupported or unknown track/clip kinds;
.oracle/plan.md:183:    - unsupported positioning, crop, effect, transition, or non-default opacity semantics;
.oracle/plan.md:193:  - Let an explicit planner route unsupported windows elsewhere; strict `rendering.ffmpeg` must not silently alter them.
.oracle/plan.md:194:  - Express media optimization and audio-reactive specialization as request-sensitive support evidence, not facade branches.
.oracle/plan.md:195:  - Preserve compatible stream-copy behavior and supported sequential audio mixing.
.oracle/plan.md:198:  - Gate: support diagnostics, command graphs, stream-copy, gaps/overlaps, track mute/volume, clip volume zero, fades, source bounds, missing streams/binaries, audio-reactive marker frames/hashes, cleanup, output validation, and provenance pass with a real FFmpeg render.
.oracle/plan.md:205:  - Stream-copy only when the complete profile is compatible. Otherwise normalize dimensions, FPS/time base, codecs, pixel format, sample rate, channel layout, and audio presence.
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
astrid/core/rendering/artifacts.py:14:from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict
astrid/core/rendering/artifacts.py:242:            f"ffprobe did not return a valid {label}",
astrid/core/rendering/artifacts.py:288:        "video_codec",
astrid/core/rendering/artifacts.py:291:        "audio_codec",
astrid/core/rendering/artifacts.py:309:        "video_codec",
astrid/core/rendering/artifacts.py:340:                "renderer declared rendered audio for a visual-only canonical profile",
astrid/core/rendering/artifacts.py:344:        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
astrid/core/rendering/artifacts.py:358:            "renderer declared no audio for a canonical profile that requires audio",
astrid/core/rendering/artifacts.py:368:            "strict ffprobe returned an invalid probe object",
astrid/core/rendering/artifacts.py:375:        for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
astrid/core/rendering/artifacts.py:385:            "ffprobe returned incomplete primary-video metadata",
astrid/core/rendering/artifacts.py:389:        _invalid("incomplete_probe", "ffprobe returned invalid video width", actual=probe.width)
astrid/core/rendering/artifacts.py:391:        _invalid("incomplete_probe", "ffprobe returned invalid video height", actual=probe.height)
astrid/core/rendering/artifacts.py:408:        "video_codec": probe.video_codec,
astrid/core/rendering/artifacts.py:445:            ("audio_codec", probe.audio_codec),
astrid/core/rendering/artifacts.py:471:            for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout")
astrid/core/rendering/artifacts.py:477:                "ffprobe returned an audio stream with incomplete metadata",
astrid/core/rendering/artifacts.py:504:        _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=True)
astrid/core/rendering/artifacts.py:514:                "ffprobe returned an invalid rational duration",
astrid/core/rendering/artifacts.py:522:                "ffprobe returned an invalid duration",
astrid/core/rendering/artifacts.py:529:            "ffprobe returned a negative duration",
astrid/core/rendering/artifacts.py:681:        probe = ffprobe_metadata_strict(video_path)
astrid/core/rendering/artifacts.py:691:    _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=False)
    30	      - backends/example/renderer.yaml
    31	    planners:
    32	      - planners/example/planner.yaml
    33	    finalizers:
    34	      - finalizers/example/finalizer.yaml
    35	```
    36	
    37	Paths are pack-relative, must stay within the pack root after resolution, and
    38	are parsed without importing or executing backend code. Normal pack
    39	precedence, conflicts, aliases, overrides, and permissions apply. Only an
    40	execution-eligible discovered candidate may run:
    41	
    42	- source and local packs are eligible;
    43	- an extra pack root is eligible only when explicitly supplied;
    44	- environment-discovered packs remain inspectable but are not executable;
    45	- an installed pack is eligible only when its active revision and installation
    46	  trust audit are valid and its required permissions have been accepted;
    47	- corrupt, missing, mismatched, inactive, or insufficient-permission records
    48	  fail closed.
    49	
    50	Trust and permission declarations do not create an operating-system sandbox.
    51	An eligible command retains the invoking user's OS authority, subject to the
    52	host's sanitized environment and invocation staging.
    53	
    54	## Manifest format
    55	
    56	The three manifest schemas are `renderer-manifest.json`,
    57	`planner-manifest.json`, and `finalizer-manifest.json`. Their shared fields are:
    58	
    59	| Field | Contract |
    60	| --- | --- |
    61	| `schema_version` | Integer `1`; version of this manifest shape. |
    62	| `id` | Qualified implementation ID. |
    63	| `name` | Non-empty display name. |
    64	| `version` | Non-empty implementation version. |
    65	| `protocol_version` | Integer `1`; command/wire protocol implemented. |
    66	| `command` | Non-empty argv prefix. The host appends the operation and flags. It is never evaluated by a shell. |
    67	| `operations` | Unique supported operations. A renderer must contain `render`, a planner `plan`, and a finalizer `finalize`; `support` is optional. |
    68	| `description` | Optional human-readable description. |
    69	| `capabilities` | Coarse static discovery hints. Missing hints mean unknown/unsupported; a support probe is authoritative. |
    70	| `required_permissions` | Unique subset of `project_files`, `network`, `subprocess`, `environment`, `accelerator`, and `external_services`. |
    71	| `required_binaries` | Unique binary names checked before invocation. |
    72	| `timeout_seconds` | Optional positive default timeout. Host policy may impose a stricter limit. |
    73	| `metadata` | String-to-string descriptive metadata. |
    74	
    75	Renderer capability hints cover clip and track types, boolean/string features,
    76	whole-timeline and window support, output-profile labels, and possible audio
    77	ownership modes. Planner hints cover named policies and fallback support.
    78	Finalizer hints cover containers, attachment preservation, audio modes, and
    79	features. Hints are intentionally coarse; they cannot override a request-
    80	sensitive `SupportReport`.
    81	
    82	Example renderer manifest:
    83	
    84	```yaml
    85	schema_version: 1
    86	id: acme.example
    87	name: Acme Example Renderer
    88	version: 1.0.0
    89	protocol_version: 1
    90	command: [python3, render.py]
    91	operations: [render, support]
    92	description: Deterministic example renderer
    93	capabilities:
    94	  clip_types: [media]
    95	  track_types: [visual]
    96	  features: {transitions: false}
    97	  supports_full_timeline: true
    98	  supports_windows: true
    99	  output_profiles: [video/mp4]
   100	  audio_ownership: [passthrough, none]
   101	required_permissions: [project_files, subprocess]
   102	required_binaries: [ffmpeg]
   103	timeout_seconds: 300
   104	metadata: {vendor: Acme}
   105	```
   106	
   107	Manifests cannot set a working directory or inject arbitrary environment
   108	variables. The host owns pack-root `cwd`, environment filtering, request/result
   109	paths, process lifetime, and cleanup.
   110	
   111	## Synchronous command protocol
   112	
   113	V1 has exactly four operations. The transport invokes a manifest's argv prefix
   114	with `shell=False`, the owning pack root as `cwd`, a sanitized environment, and
   115	absolute request/result paths:
   116	
   117	```text
   118	<command...> render   --request <absolute-request.json> --result <absolute-result.json>
   119	<command...> support  --request <absolute-request.json> --result <absolute-result.json>
   120	<command...> plan     --request <absolute-request.json> --result <absolute-result.json>
   121	<command...> finalize --request <absolute-request.json> --result <absolute-result.json>
   122	```
   123	
   124	The payload mapping is:
   125	
   126	| Operation | Request schema | Successful result schema |
   127	| --- | --- | --- |
   128	| `render` | `request.json` | successful branch of `result.json` |
   129	| `support` | `request.json` | `support.json` |
   130	| `plan` | `request.json` | `plan.json` |
   131	| `finalize` | `finalize.json` | successful branch of `result.json` |
   132	
   133	`result.json` also defines the structured `RendererError` branch. The result
   134	file is authoritative; stdout and stderr are captured diagnostics, not a
   135	second protocol channel. Exit zero without the required result file, malformed
   136	JSON, the wrong result shape, or an unrecognized version is a `protocol`
   137	failure. A nonzero exit is mapped to a structured failure even if diagnostics
   138	were printed. V1 is synchronous: submit/status/cancel/resume semantics require
   139	a future protocol version.
   140	
   141	## Wire primitives
   142	
   143	JSON numbers must be finite. Python booleans do not count as integers. Fixed
   144	objects reject unknown properties. Optional fields may be omitted; canonical
   145	SDK serialization fills schema defaults and emits nullable values as JSON
   146	`null`.
   147	
   148	### Rational values and frame windows
   149	
   150	`fps_rational` and `time_base` are two-item JSON arrays `[numerator,
   151	denominator]` of positive integers. Decimal FPS is not authoritative. A
   152	`FrameWindow` is:
   153	
   154	```json
   155	{
   156	  "start_frame": 0,
   157	  "end_frame": 48,
   158	  "fps_rational": [24, 1],
   159	  "source_range": [0, 48],
   160	  "speed": 1.0
   161	}
   162	```
   163	
   164	The interval is always half-open: `[start_frame,end_frame)`, with
   165	`0 <= start_frame < end_frame`. Adjacent windows therefore meet without
   166	sharing a frame. `source_range`, when present, is also a non-negative half-open
   167	integer frame pair. `speed`, when present, is finite and greater than zero.
   168	`null` source range means no separate source trim; `null` speed means canonical
   169	speed `1` inherited from the timeline.
   170	
   171	### Render profile
   172	
   173	A `RenderProfile` describes the media that must actually be probed, not merely
   174	the requested encoder flags:
   175	
   176	- positive `width` and `height`;
   177	- rational `fps_rational` and stream `time_base`;
   178	- non-empty `container`, `video_codec`, and `pixel_format`;
   179	- nullable `video_profile` and `video_level` when the codec does not expose
   180	  them;
   181	- the optional audio trio `audio_codec`, `audio_sample_rate`, and
   182	  `audio_channel_layout`, either all populated or all omitted/`null`;
   183	- `duration_tolerance`, a non-negative integer measured in **frames**.
   184	
   185	A visual-only profile omits all three audio fields or sets them all to `null`;
   186	canonical DTO output uses explicit nulls. One frame is the V1 default duration
   187	tolerance. This tolerance never changes window bounds; it only controls
   188	artifact acceptance.
   189	
   190	## Render request and configuration namespacing
   350	                    f"renderer audio profile has incompatible {field}",
   351	                    field=field,
   352	                    expected=_profile_value(expected, field),
   353	                    actual=_profile_value(declared, field),
   354	                )
   355	    elif ownership is AudioOwnership.NONE and expected.has_audio:
   356	        _invalid(
   357	            "audio_profile_mismatch",
   358	            "renderer declared no audio for a canonical profile that requires audio",
   359	            expected_audio=True,
   360	            actual_audio=False,
   361	        )
   362	
   363	
   364	def _probe_required_video(probe: MediaProbe) -> None:
   365	    if not isinstance(probe, MediaProbe):
   366	        _invalid(
   367	            "incomplete_probe",
   368	            "strict ffprobe returned an invalid probe object",
   369	            received_type=type(probe).__name__,
   370	        )
   371	    if not probe.has_video_stream:
   372	        _invalid("missing_video_stream", "primary video has no video stream")
   373	    missing = [
   374	        field
   375	        for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
   376	        if getattr(probe, field) is None
   377	    ]
   378	    if probe.container is None and probe.format_name is None:
   379	        missing.append("container")
   380	    if probe.duration_rational is None and probe.duration_seconds is None:
   381	        missing.append("duration")
   382	    if missing:
   383	        _invalid(
   384	            "incomplete_probe",
   385	            "ffprobe returned incomplete primary-video metadata",
   386	            missing=missing,
   387	        )
   388	    if type(probe.width) is not int or probe.width <= 0:
   389	        _invalid("incomplete_probe", "ffprobe returned invalid video width", actual=probe.width)
   390	    if type(probe.height) is not int or probe.height <= 0:
   391	        _invalid("incomplete_probe", "ffprobe returned invalid video height", actual=probe.height)
   392	    _rational(probe.fps_rational, label="video FPS")
   393	    _rational(probe.time_base, label="video time base")
   394	
   395	
   396	def _compare_probe_to_profile(
   397	    probe: MediaProbe,
   398	    profile: RenderProfile,
   399	    *,
   400	    label: str,
   401	    compare_audio: bool,
   402	) -> None:
   403	    actual_values: dict[str, Any] = {
   404	        "width": probe.width,
   405	        "height": probe.height,
   406	        "fps_rational": probe.fps_rational,
   407	        "time_base": probe.time_base,
   408	        "video_codec": probe.video_codec,
   409	        "pixel_format": probe.pixel_format,
   410	    }
   411	    for field, actual in actual_values.items():
   412	        expected = _profile_value(profile, field)
   413	        if not _same_profile_value(field, actual, expected):
   414	            _invalid(
   415	                "profile_mismatch",
   416	                f"probed video {field} does not match {label}",
   417	                field=field,
   418	                expected=expected,
   419	                actual=actual,
   420	            )
   421	    if not _container_matches(probe, profile.container):
   422	        _invalid(
   423	            "profile_mismatch",
   424	            f"probed video container does not match {label}",
   425	            field="container",
   426	            expected=profile.container,
   427	            actual=probe.container or probe.format_name,
   428	        )
   429	    for field, actual in (
   430	        ("video_profile", probe.video_profile),
   431	        ("video_level", probe.video_level),
   432	    ):
   433	        expected = _profile_value(profile, field)
   434	        if expected is not None and not _same_profile_value(field, actual, expected):
   435	            _invalid(
   436	                "profile_mismatch",
   437	                f"probed video {field} does not match {label}",
   438	                field=field,
   439	                expected=expected,
   440	                actual=actual,
   441	            )
   442	
   443	    if compare_audio:
   444	        for field, actual in (
   445	            ("audio_codec", probe.audio_codec),
   446	            ("audio_sample_rate", probe.audio_sample_rate),
   447	            ("audio_channel_layout", probe.audio_channel_layout),
   448	        ):
   449	            expected = _profile_value(profile, field)
   450	            if not _same_profile_value(field, actual, expected):
   451	                _invalid(
   452	                    "audio_profile_mismatch",
   453	                    f"probed audio {field} does not match {label}",
   454	                    field=field,
   455	                    expected=expected,
   456	                    actual=actual,
   457	                )
   458	
   459	
   460	def _validate_audio(
   461	    probe: MediaProbe,
   462	    *,
   463	    ownership: AudioOwnership,
   464	    declared: RenderProfile,
   465	    expected: RenderProfile,
   466	) -> None:
   467	    has_audio = probe.has_audio_stream
   468	    if has_audio:
   469	        missing = [
   470	            field
   471	            for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout")
   472	            if getattr(probe, field) is None
   473	        ]
   474	        if missing:
   475	            _invalid(
   476	                "incomplete_probe",
   477	                "ffprobe returned an audio stream with incomplete metadata",
   478	                missing=missing,
   479	            )
   480	
   481	    if ownership is AudioOwnership.RENDERED and not has_audio:
   482	        _invalid(
   483	            "audio_ownership_mismatch",
   484	            "renderer declared audio_ownership='rendered' but the video has no audio stream",
   485	            declared_ownership=ownership.value,
   486	            actual_audio_stream=False,
   487	        )
   488	    if ownership in {AudioOwnership.NONE, AudioOwnership.PASSTHROUGH} and has_audio:
   489	        _invalid(
   490	            "audio_ownership_mismatch",
   491	            f"renderer declared audio_ownership={ownership.value!r} but the video has an audio stream",
   492	            declared_ownership=ownership.value,
   493	            actual_audio_stream=True,
   494	        )
   495	    if declared.has_audio != has_audio:
   496	        _invalid(
   497	            "audio_profile_mismatch",
   498	            "declared artifact audio profile does not match probed stream presence",
   499	            declared_audio=declared.has_audio,
   500	            actual_audio_stream=has_audio,
   501	        )
   502	    if has_audio:
   503	        _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=True)
   504	        _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=True)
   505	
   506	
   507	def _duration_fraction(probe: MediaProbe) -> Fraction:
   508	    if probe.duration_rational is not None:
   509	        try:
   510	            duration = Fraction(*probe.duration_rational)

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,runpy,struct; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); e=m[\"_sowt_entry\"](); i=e.index(b\"chan\")-4; size=struct.unpack(\">I\",e[i:i+4])[0]; print(\"chan_payload\",e[i+8:i+size].hex()); s=json.load(open(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\")); r=json.load(open(\"tests/fixtures/renderer_packs/raw_command/requests/render.json\")); print(\"support_codec\",s[\"profile\"][\"audio_codec\"],\"render_codec\",r[\"profile\"][\"audio_codec\"]); vals=[1,True,1.0,False,2]; print([(repr(v), (lambda q: (m[\"_validate_request\"](q),\"accepted\"))({**s,\"schema_version\":v}) if False else \"\") for v in []])'
strings tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc | rg -n \"/Users|backend\\.py\" | head -20 || true" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 95ms:
chan_payload 000000000000000300000000
support_codec sowt render_codec pcm_s16le
[]
strings: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
strings: error: couldn't create cache file '/tmp/xcrun_db-ThJYiCzO' (errno=Operation not permitted)
32:    python3 backend.py render|support --request <abs.json> --result <abs.json>
58:p/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py
344:backend.pyz:Raw v1 rendering protocol fixture backend (no Astrid SDK).)

Independent reviews and direct code/runtime probes agree that several checkpoint blockers remain.
  ✓ Read prior checkpoint findings and inspect commit/diff scope
  ✓ Verify transport, media/profile, protocol, and symlink closures
  ✓ Run focused regression tests and check worktree integrity
  ✓ Return the binary checkpoint verdict
codex
- Transport cleanup remains interruptible and leak-prone. Non-timeout `communicate()` failures escape after only SIGTERM, while repeated `KeyboardInterrupt` can escape unguarded polling/drain operations before reap. `_wait_for_group_exit` can also loop forever. The new test no longer checks the grandchild. [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461), [test_transport.py:178](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:178)

- The fixture’s `chan` atom is malformed. ffprobe still reports no channel layout; `media.py` masks this by inferring layout from channel count, which is ambiguous for six- and eight-channel media and makes strict validation accept unprobed metadata. [backend.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:302), [media.py:224](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py:224)

- The support fixture still requests `sowt`, while the renderer produces `pcm_s16le`; `_support()` ignores that mismatch and returns `supported: true`. [support.json:24](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/requests/support.json:24), [backend.py:438](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:438)

- Production output symlinks are still followed because `_render_with_publication_context()` resolves `out_path` before publication sees it. [run.py:1290](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1290)

- Default previous-output sidecar symlinks remain unchecked. Production passes bare paths, so the default sidecar is resolved before the raw-sidecar guard. [publication.py:185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:185), [publication.py:221](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:221)

- Commit `7f7c25d5` accidentally tracks `tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc`, including an absolute developer-machine path.
tokens used
172,675
- Transport cleanup remains interruptible and leak-prone. Non-timeout `communicate()` failures escape after only SIGTERM, while repeated `KeyboardInterrupt` can escape unguarded polling/drain operations before reap. `_wait_for_group_exit` can also loop forever. The new test no longer checks the grandchild. [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461), [test_transport.py:178](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:178)

- The fixture’s `chan` atom is malformed. ffprobe still reports no channel layout; `media.py` masks this by inferring layout from channel count, which is ambiguous for six- and eight-channel media and makes strict validation accept unprobed metadata. [backend.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:302), [media.py:224](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py:224)

- The support fixture still requests `sowt`, while the renderer produces `pcm_s16le`; `_support()` ignores that mismatch and returns `supported: true`. [support.json:24](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/requests/support.json:24), [backend.py:438](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:438)

- Production output symlinks are still followed because `_render_with_publication_context()` resolves `out_path` before publication sees it. [run.py:1290](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1290)

- Default previous-output sidecar symlinks remain unchecked. Production passes bare paths, so the default sidecar is resolved before the raw-sidecar guard. [publication.py:185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:185), [publication.py:221](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:221)

- Commit `7f7c25d5` accidentally tracks `tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc`, including an absolute developer-machine path.
