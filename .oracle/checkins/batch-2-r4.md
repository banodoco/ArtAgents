Reading additional input from stdin...
2026-08-12T07:08:03.866098Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:03.866121Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:03.866126Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff4cc-b2ea-7441-977e-a994c0b72127
--------
user
# Megado Checkpoint — Batch 2 fourth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-2.md (6), -r1 (5), -r2 (6), -r3 (5). Fourth rework
committed as `9db48731` (prior head 8c195bf0). Incremental diff at
/tmp/batch2-r4.diff.

## How each of your 5 re-review3 issues was addressed (host-implemented)

1. **Transport cleanup unbounded/interruptible** →
   - Drain `communicate()` now bounded (max(grace, 2.0)s) with
     TimeoutExpired/KeyboardInterrupt/OSError all escalating to group
     SIGKILL; the elif-drain branch is likewise bounded. No unguarded
     communicate remains in cleanup.
2. **chan atom malformed; layout inference masks** →
   - chan atom now canonical FFmpeg movenc format: version(2)+revision(2)+
     layout_tag(4, 0x00650002 stereo)+bitmap(4)+num_descriptions(4).
   - media.py NO LONGER infers layout from channel count: it reports
     `audio_channels` and leaves `audio_channel_layout` honest (None).
   - artifacts.py compares declared layout's canonical channel count against
     probed `audio_channels` when layout is unprobed (QuickTime sowt
     limitation) — no guessed layouts; `incomplete_probe` accepts
     channels-only probes.
3. **support not profile-fail-closed** →
   - `_support` now checks EVERY fixed profile field (dimensions, fps,
     time base, container, codecs, pixel format, profile/level, sample
     rate, layout); any deviation returns supported:false with reasons.
4. **Output symlinks followed on ffmpeg/hybrid/audio-reactive routes** →
   - All three helpers preserve the UNRESOLVED `publication_out` (resolved
     path used only for temp-dir placement); publication symlink-guards the
     unresolved path.
5. **Ancestor symlinks unchecked (symlinked run dirs)** →
   - `_contains_symlink_component` walks ALL path components, rejecting any
     non-system symlink (macOS `/tmp`→`/private/tmp`, `/var`→`/private/var`
     exempted); used in publish guard, committed-pair read, and cleanup.

## Evidence

- Incremental diff: /tmp/batch2-r4.diff (8 files)
- Host-verified: transport (14) + fixture (6) + publication (7) + artifacts +
  media (76 combined) pass; rendering tests 77 pass (2 pre-existing env
  failures); full consolidated acceptance = 746 passed, 2 failed (SAME 2
  pre-existing), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Verify the five closures: the bounded
cleanup (no unguarded communicate), the honest probe (channels vs layout),
the full support fail-closed matrix, unresolved paths on all publish routes,
and the ancestor-symlink guard (including that it does NOT false-positive on
macOS system redirects). If PASS, say exactly `PASS`.
codex
I’m using the `megado` checkpoint workflow to inspect the incremental diff and verify each of the five claimed closures. I’ll keep the final response strictly to the requested verdict.
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
The repository guidance also calls for context-minimized parallel review on multi-part checks. I’m applying that guidance by splitting the five independent invariants while I inspect the combined diff and integration points.
exec
/bin/zsh -lc "sed -n '1,320p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

2026-08-12T07:08:37.797725Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:37.797797Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:37.797805Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:43.616745Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:43.616794Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:43.616800Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:48.592804Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:48.592852Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:08:48.592861Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git diff --stat 8c195bf0..9db48731 && git diff --check 8c195bf0..9db48731 && sed -n '1,260p' /tmp/batch2-r4.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-2-r4.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
9db48731e07a017c3e1cb40533d807dc38d70850
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-2-r3.md                     | 17554 +++++++++++++++++++
 astrid/core/media.py                               |    12 +-
 astrid/core/rendering/artifacts.py                 |    30 +-
 astrid/core/rendering/publication.py               |    47 +-
 astrid/core/rendering/transport.py                 |    24 +-
 astrid/packs/rendering/executors/render/run.py     |    29 +-
 tests/core/util/test_media.py                      |    22 +-
 .../fixtures/renderer_packs/raw_command/backend.py |    52 +-
 8 files changed, 17704 insertions(+), 66 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r3.md:507: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:508: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:510: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:616: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:861: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:862: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:864: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:969: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:971: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:973: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:975: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:977: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:979: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:981: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:983: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:985: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:987: trailing whitespace.
+++++     2	
.oracle/checkins/batch-2-r3.md:989: trailing whitespace.
+++++     4	
.oracle/checkins/batch-2-r3.md:991: trailing whitespace.
+++++     8	
.oracle/checkins/batch-2-r3.md:993: trailing whitespace.
+++++    11	
.oracle/checkins/batch-2-r3.md:995: trailing whitespace.
+++++    29	
.oracle/checkins/batch-2-r3.md:997: trailing whitespace.
+++++    30	
.oracle/checkins/batch-2-r3.md:999: trailing whitespace.
+++++    33	
.oracle/checkins/batch-2-r3.md:1001: trailing whitespace.
+++++    34	
.oracle/checkins/batch-2-r3.md:1003: trailing whitespace.
+++++    39	
.oracle/checkins/batch-2-r3.md:1005: trailing whitespace.
+++++    41	
.oracle/checkins/batch-2-r3.md:1007: trailing whitespace.
+++++    42	
.oracle/checkins/batch-2-r3.md:1009: trailing whitespace.
+++++    54	
.oracle/checkins/batch-2-r3.md:1011: trailing whitespace.
+++++    55	
.oracle/checkins/batch-2-r3.md:1013: trailing whitespace.
+++++    82	
.oracle/checkins/batch-2-r3.md:1015: trailing whitespace.
+++++    83	
.oracle/checkins/batch-2-r3.md:1017: trailing whitespace.
+++++    86	
.oracle/checkins/batch-2-r3.md:1019: trailing whitespace.
+++++    93	
.oracle/checkins/batch-2-r3.md:1021: trailing whitespace.
+++++    94	
.oracle/checkins/batch-2-r3.md:1023: trailing whitespace.
+++++   106	
.oracle/checkins/batch-2-r3.md:1025: trailing whitespace.
+++++   107	
.oracle/checkins/batch-2-r3.md:1027: trailing whitespace.
+++++   199	
.oracle/checkins/batch-2-r3.md:1029: trailing whitespace.
+++++   200	
.oracle/checkins/batch-2-r3.md:1031: trailing whitespace.
+++++   915	
.oracle/checkins/batch-2-r3.md:1033: trailing whitespace.
+++++   916	
.oracle/checkins/batch-2-r3.md:1035: trailing whitespace.
+++++    35	
.oracle/checkins/batch-2-r3.md:1037: trailing whitespace.
+++++    40	
.oracle/checkins/batch-2-r3.md:1039: trailing whitespace.
+++++    49	
.oracle/checkins/batch-2-r3.md:1041: trailing whitespace.
+++++    61	
.oracle/checkins/batch-2-r3.md:1043: trailing whitespace.
+++++    82	
.oracle/checkins/batch-2-r3.md:1045: trailing whitespace.
+++++   102	
.oracle/checkins/batch-2-r3.md:1047: trailing whitespace.
+++++   119	
.oracle/checkins/batch-2-r3.md:1049: trailing whitespace.
+++++   132	
.oracle/checkins/batch-2-r3.md:1051: trailing whitespace.
+++++   139	
.oracle/checkins/batch-2-r3.md:1053: trailing whitespace.
+++++   140	
.oracle/checkins/batch-2-r3.md:1055: trailing whitespace.
+++++   143	
.oracle/checkins/batch-2-r3.md:1057: trailing whitespace.
+++++   167	
.oracle/checkins/batch-2-r3.md:1059: trailing whitespace.
+++++   168	
.oracle/checkins/batch-2-r3.md:1061: trailing whitespace.
+++++   516	
.oracle/checkins/batch-2-r3.md:1063: trailing whitespace.
+++++   520	
.oracle/checkins/batch-2-r3.md:1065: trailing whitespace.
+++++   539	
.oracle/checkins/batch-2-r3.md:1067: trailing whitespace.
+++++   572	
.oracle/checkins/batch-2-r3.md:1069: trailing whitespace.
+++++   573	
.oracle/checkins/batch-2-r3.md:1071: trailing whitespace.
+++++   580	
.oracle/checkins/batch-2-r3.md:1073: trailing whitespace.
+++++   585	
.oracle/checkins/batch-2-r3.md:1075: trailing whitespace.
+++++   591	
.oracle/checkins/batch-2-r3.md:1077: trailing whitespace.
+++++   592	
.oracle/checkins/batch-2-r3.md:1079: trailing whitespace.
+++++   596	
.oracle/checkins/batch-2-r3.md:1081: trailing whitespace.
+++++   601	
.oracle/checkins/batch-2-r3.md:1083: trailing whitespace.
+++++   613	
.oracle/checkins/batch-2-r3.md:1085: trailing whitespace.
+++++   618	
.oracle/checkins/batch-2-r3.md:1087: trailing whitespace.
+++++   630	
.oracle/checkins/batch-2-r3.md:1089: trailing whitespace.
+++++   642	
.oracle/checkins/batch-2-r3.md:1091: trailing whitespace.
+++++   643	
.oracle/checkins/batch-2-r3.md:1093: trailing whitespace.
+++++   664	
.oracle/checkins/batch-2-r3.md:1095: trailing whitespace.
+++++   665	
.oracle/checkins/batch-2-r3.md:1097: trailing whitespace.
+++++   669	
.oracle/checkins/batch-2-r3.md:1099: trailing whitespace.
+++++   676	
.oracle/checkins/batch-2-r3.md:1101: trailing whitespace.
+++++   699	
.oracle/checkins/batch-2-r3.md:1103: trailing whitespace.
+++++   711	
.oracle/checkins/batch-2-r3.md:1105: trailing whitespace.
+++++   200	
.oracle/checkins/batch-2-r3.md:1107: trailing whitespace.
+++++   276	
.oracle/checkins/batch-2-r3.md:1109: trailing whitespace.
+++++   277	
.oracle/checkins/batch-2-r3.md:1111: trailing whitespace.
+++++   288	
.oracle/checkins/batch-2-r3.md:1113: trailing whitespace.
+++++   289	
.oracle/checkins/batch-2-r3.md:1115: trailing whitespace.
+++++   311	
.oracle/checkins/batch-2-r3.md:1117: trailing whitespace.
+++++   312	
.oracle/checkins/batch-2-r3.md:1119: trailing whitespace.
+++++   328	
.oracle/checkins/batch-2-r3.md:1121: trailing whitespace.
+++++   335	
.oracle/checkins/batch-2-r3.md:1123: trailing whitespace.
+++++   356	
.oracle/checkins/batch-2-r3.md:1125: trailing whitespace.
+++++   383	
.oracle/checkins/batch-2-r3.md:1127: trailing whitespace.
+++++   384	
.oracle/checkins/batch-2-r3.md:1129: trailing whitespace.
+++++   387	
.oracle/checkins/batch-2-r3.md:1131: trailing whitespace.
+++++   389	
.oracle/checkins/batch-2-r3.md:1133: trailing whitespace.
+++++   390	
.oracle/checkins/batch-2-r3.md:1135: trailing whitespace.
+++++   214	
.oracle/checkins/batch-2-r3.md:1137: trailing whitespace.
+++++   215	
.oracle/checkins/batch-2-r3.md:1139: trailing whitespace.
+++++   218	
.oracle/checkins/batch-2-r3.md:1141: trailing whitespace.
+++++   224	
.oracle/checkins/batch-2-r3.md:1143: trailing whitespace.
+++++   225	
.oracle/checkins/batch-2-r3.md:1145: trailing whitespace.
+++++   234	
.oracle/checkins/batch-2-r3.md:1147: trailing whitespace.
+++++   235	
.oracle/checkins/batch-2-r3.md:1149: trailing whitespace.
+++++   240	
.oracle/checkins/batch-2-r3.md:1151: trailing whitespace.
+++++   241	
.oracle/checkins/batch-2-r3.md:1153: trailing whitespace.
+++++   250	
.oracle/checkins/batch-2-r3.md:1155: trailing whitespace.
+++++   251	
.oracle/checkins/batch-2-r3.md:1157: trailing whitespace.
+++++   257	
.oracle/checkins/batch-2-r3.md:1159: trailing whitespace.
+++++   258	
.oracle/checkins/batch-2-r3.md:1161: trailing whitespace.
+++++   271	
.oracle/checkins/batch-2-r3.md:1163: trailing whitespace.
+++++   272	
.oracle/checkins/batch-2-r3.md:1165: trailing whitespace.
+++++   277	
.oracle/checkins/batch-2-r3.md:1167: trailing whitespace.
+++++   278	
.oracle/checkins/batch-2-r3.md:1169: trailing whitespace.
+++++   285	
.oracle/checkins/batch-2-r3.md:1171: trailing whitespace.
+++++   286	
.oracle/checkins/batch-2-r3.md:1173: trailing whitespace.
+++++   293	
.oracle/checkins/batch-2-r3.md:1175: trailing whitespace.
+++++   294	
.oracle/checkins/batch-2-r3.md:1177: trailing whitespace.
+++++   303	
.oracle/checkins/batch-2-r3.md:1179: trailing whitespace.
+++++   304	
.oracle/checkins/batch-2-r3.md:1181: trailing whitespace.
+++++   311	
.oracle/checkins/batch-2-r3.md:1183: trailing whitespace.
+++++   312	
.oracle/checkins/batch-2-r3.md:1185: trailing whitespace.
+++++   321	
.oracle/checkins/batch-2-r3.md:1187: trailing whitespace.
+++++   322	
.oracle/checkins/batch-2-r3.md:1189: trailing whitespace.
+++++   339	
.oracle/checkins/batch-2-r3.md:1191: trailing whitespace.
+++++   340	
.oracle/checkins/batch-2-r3.md:1193: trailing whitespace.
+++++   352	
.oracle/checkins/batch-2-r3.md:1195: trailing whitespace.
+++++   353	
.oracle/checkins/batch-2-r3.md:1197: trailing whitespace.
+++++   356	
.oracle/checkins/batch-2-r3.md:1199: trailing whitespace.
+++++   362	
.oracle/checkins/batch-2-r3.md:1201: trailing whitespace.
+++++   363	
.oracle/checkins/batch-2-r3.md:1203: trailing whitespace.
+++++   664	
.oracle/checkins/batch-2-r3.md:1205: trailing whitespace.
+++++   665	
.oracle/checkins/batch-2-r3.md:1207: trailing whitespace.
+++++   669	
.oracle/checkins/batch-2-r3.md:1209: trailing whitespace.
+++++   676	
.oracle/checkins/batch-2-r3.md:1211: trailing whitespace.
+++++   699	
.oracle/checkins/batch-2-r3.md:1213: trailing whitespace.
+++++   711	
.oracle/checkins/batch-2-r3.md:1215: trailing whitespace.
+++++   726	
.oracle/checkins/batch-2-r3.md:1217: trailing whitespace.
+++++   747	
.oracle/checkins/batch-2-r3.md:1219: trailing whitespace.
+++++   748	
.oracle/checkins/batch-2-r3.md:1221: trailing whitespace.
+++++   755	
.oracle/checkins/batch-2-r3.md:1223: trailing whitespace.
+++++   276	
.oracle/checkins/batch-2-r3.md:1225: trailing whitespace.
+++++   277	
.oracle/checkins/batch-2-r3.md:1227: trailing whitespace.
+++++   288	
.oracle/checkins/batch-2-r3.md:1229: trailing whitespace.
+++++   289	
.oracle/checkins/batch-2-r3.md:1231: trailing whitespace.
+++++   311	
.oracle/checkins/batch-2-r3.md:1233: trailing whitespace.
+++++   312	
.oracle/checkins/batch-2-r3.md:1235: trailing whitespace.
+++++   328	
.oracle/checkins/batch-2-r3.md:1237: trailing whitespace.
+++++   335	
.oracle/checkins/batch-2-r3.md:1239: trailing whitespace.
+++++   356	
.oracle/checkins/batch-2-r3.md:1241: trailing whitespace.
+++++   383	
.oracle/checkins/batch-2-r3.md:1243: trailing whitespace.
+++++   384	
.oracle/checkins/batch-2-r3.md:1245: trailing whitespace.
+++++   387	
.oracle/checkins/batch-2-r3.md:1247: trailing whitespace.
+++++   389	
.oracle/checkins/batch-2-r3.md:1249: trailing whitespace.
+++++   390	
.oracle/checkins/batch-2-r3.md:1251: trailing whitespace.
+++++   749	
.oracle/checkins/batch-2-r3.md:1253: trailing whitespace.
+++++   750	
.oracle/checkins/batch-2-r3.md:1255: trailing whitespace.
+++++   786	
.oracle/checkins/batch-2-r3.md:1257: trailing whitespace.
+++++   787	
.oracle/checkins/batch-2-r3.md:1259: trailing whitespace.
+++++   801	
.oracle/checkins/batch-2-r3.md:1261: trailing whitespace.
+++++   802	
.oracle/checkins/batch-2-r3.md:1263: trailing whitespace.
+++++   818	
.oracle/checkins/batch-2-r3.md:1265: trailing whitespace.
+++++   819	
.oracle/checkins/batch-2-r3.md:1267: trailing whitespace.
+++++   915	
.oracle/checkins/batch-2-r3.md:1269: trailing whitespace.
+++++   916	
.oracle/checkins/batch-2-r3.md:1271: trailing whitespace.
+++++  1072	
.oracle/checkins/batch-2-r3.md:1273: trailing whitespace.
+++++  1073	
.oracle/checkins/batch-2-r3.md:1275: trailing whitespace.
+++++  1082	
.oracle/checkins/batch-2-r3.md:1277: trailing whitespace.
+++++  1083	
.oracle/checkins/batch-2-r3.md:1279: trailing whitespace.
++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1281: trailing whitespace.
++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1283: trailing whitespace.
++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1285: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1287: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1289: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1291: trailing whitespace.
++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1293: trailing whitespace.
++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1295: trailing whitespace.
++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1297: trailing whitespace.
+++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1299: trailing whitespace.
+++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1301: trailing whitespace.
+++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1303: trailing whitespace.
++++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1305: trailing whitespace.
++++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1307: trailing whitespace.
++++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1309: trailing whitespace.
++++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1311: trailing whitespace.
++++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1313: trailing whitespace.
++++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1315: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1317: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1319: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1321: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1323: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1325: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1327: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1329: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1331: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1333: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1335: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1337: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1339: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1341: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1343: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1345: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1347: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1349: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1351: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1353: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1355: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1357: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1359: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1361: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1363: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1365: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1367: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1369: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1371: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1373: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1375: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1377: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1379: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1381: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1383: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1385: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1387: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1389: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1391: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1393: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1395: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1397: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1399: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1401: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1403: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1405: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1407: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1409: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1411: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1413: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1415: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1417: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1419: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1421: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1423: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1425: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1427: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1429: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1431: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1433: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1435: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1437: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1439: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1441: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1443: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1445: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1447: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1449: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1451: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1453: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1455: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1457: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1459: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1461: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1463: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1465: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1467: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1469: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1471: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1473: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1475: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1477: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1479: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1481: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1483: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1485: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1487: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1489: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1491: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1493: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1495: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1497: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1499: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1501: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1503: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1505: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1507: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1509: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1511: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1513: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1515: trailing whitespace.
++++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:1517: trailing whitespace.
++++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:1519: trailing whitespace.
++++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:1521: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1523: trailing whitespace.
++++++++++   730	
.oracle/checkins/batch-2-r3.md:1525: trailing whitespace.
++++++++++   731	
.oracle/checkins/batch-2-r3.md:1527: trailing whitespace.
++++++++++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-2-r3.md:1529: trailing whitespace.
++++++++++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-2-r3.md:1531: trailing whitespace.
++++++++++   453	
.oracle/checkins/batch-2-r3.md:1533: trailing whitespace.
++++++++++   461	
.oracle/checkins/batch-2-r3.md:1535: trailing whitespace.
++++++++++   463	
.oracle/checkins/batch-2-r3.md:1537: trailing whitespace.
++++++++++   465	
.oracle/checkins/batch-2-r3.md:1539: trailing whitespace.
++++++++++   470	
.oracle/checkins/batch-2-r3.md:1541: trailing whitespace.
++++++++++   492	
.oracle/checkins/batch-2-r3.md:1543: trailing whitespace.
++++++++++   520	
.oracle/checkins/batch-2-r3.md:1545: trailing whitespace.
++++++++++   539	
.oracle/checkins/batch-2-r3.md:1547: trailing whitespace.
++++++++++   540	
.oracle/checkins/batch-2-r3.md:1549: trailing whitespace.
++++++++++   550	
.oracle/checkins/batch-2-r3.md:1551: trailing whitespace.
++++++++++   551	
.oracle/checkins/batch-2-r3.md:1553: trailing whitespace.
++++++++++   609	
.oracle/checkins/batch-2-r3.md:1555: trailing whitespace.
++++++++++   613	
.oracle/checkins/batch-2-r3.md:1557: trailing whitespace.
++++++++++   614	
.oracle/checkins/batch-2-r3.md:1559: trailing whitespace.
++++++++++   627	
.oracle/checkins/batch-2-r3.md:1561: trailing whitespace.
++++++++++   628	
.oracle/checkins/batch-2-r3.md:1563: trailing whitespace.
++++++++++   631	
.oracle/checkins/batch-2-r3.md:1565: trailing whitespace.
++++++++++   640	
.oracle/checkins/batch-2-r3.md:1567: trailing whitespace.
++++++++++   641	
.oracle/checkins/batch-2-r3.md:1569: trailing whitespace.
++++++++++   647	
.oracle/checkins/batch-2-r3.md:1571: trailing whitespace.
++++++++++   648	
.oracle/checkins/batch-2-r3.md:1573: trailing whitespace.
++++++++++   679	
.oracle/checkins/batch-2-r3.md:1575: trailing whitespace.
++++++++++   689	
.oracle/checkins/batch-2-r3.md:1577: trailing whitespace.
++++++++++   721	
.oracle/checkins/batch-2-r3.md:1579: trailing whitespace.
++++++++++   722	
.oracle/checkins/batch-2-r3.md:1581: trailing whitespace.
++++++++++   740	
.oracle/checkins/batch-2-r3.md:1583: trailing whitespace.
++++++++++   741	
.oracle/checkins/batch-2-r3.md:1585: trailing whitespace.
++++++++++   777	
.oracle/checkins/batch-2-r3.md:1587: trailing whitespace.
++++++++++   778	
.oracle/checkins/batch-2-r3.md:1589: trailing whitespace.
++++++++++   792	
.oracle/checkins/batch-2-r3.md:1591: trailing whitespace.
++++++++++   793	
.oracle/checkins/batch-2-r3.md:1593: trailing whitespace.
++++++++++   809	
.oracle/checkins/batch-2-r3.md:1595: trailing whitespace.
++++++++++   810	
.oracle/checkins/batch-2-r3.md:1597: trailing whitespace.
++++++++++   904	
.oracle/checkins/batch-2-r3.md:1599: trailing whitespace.
++++++++++   905	
.oracle/checkins/batch-2-r3.md:1601: trailing whitespace.
++++++++++   965	
.oracle/checkins/batch-2-r3.md:1603: trailing whitespace.
++++++++++   966	
.oracle/checkins/batch-2-r3.md:1605: trailing whitespace.
++++++++++   975	
.oracle/checkins/batch-2-r3.md:1607: trailing whitespace.
++++++++++   976	
.oracle/checkins/batch-2-r3.md:1609: trailing whitespace.
++++++++++     2	
.oracle/checkins/batch-2-r3.md:1611: trailing whitespace.
++++++++++     4	
.oracle/checkins/batch-2-r3.md:1613: trailing whitespace.
++++++++++     8	
.oracle/checkins/batch-2-r3.md:1615: trailing whitespace.
++++++++++    11	
.oracle/checkins/batch-2-r3.md:1617: trailing whitespace.
++++++++++    28	
.oracle/checkins/batch-2-r3.md:1619: trailing whitespace.
++++++++++    29	
.oracle/checkins/batch-2-r3.md:1621: trailing whitespace.
++++++++++    32	
.oracle/checkins/batch-2-r3.md:1623: trailing whitespace.
++++++++++    33	
.oracle/checkins/batch-2-r3.md:1625: trailing whitespace.
++++++++++    38	
.oracle/checkins/batch-2-r3.md:1627: trailing whitespace.
++++++++++    40	
.oracle/checkins/batch-2-r3.md:1629: trailing whitespace.
++++++++++    41	
.oracle/checkins/batch-2-r3.md:1631: trailing whitespace.
++++++++++    53	
.oracle/checkins/batch-2-r3.md:1633: trailing whitespace.
++++++++++    54	
.oracle/checkins/batch-2-r3.md:1635: trailing whitespace.
++++++++++    81	
.oracle/checkins/batch-2-r3.md:1637: trailing whitespace.
++++++++++    82	
.oracle/checkins/batch-2-r3.md:1639: trailing whitespace.
++++++++++    85	
.oracle/checkins/batch-2-r3.md:1641: trailing whitespace.
++++++++++    92	
.oracle/checkins/batch-2-r3.md:1643: trailing whitespace.
++++++++++    93	
.oracle/checkins/batch-2-r3.md:1645: trailing whitespace.
++++++++++   105	
.oracle/checkins/batch-2-r3.md:1647: trailing whitespace.
++++++++++   106	
.oracle/checkins/batch-2-r3.md:1649: trailing whitespace.
++++++++++   168	
.oracle/checkins/batch-2-r3.md:1651: trailing whitespace.
++++++++++   169	
.oracle/checkins/batch-2-r3.md:1653: trailing whitespace.
++++++++++   236	
.oracle/checkins/batch-2-r3.md:1655: trailing whitespace.
++++++++++   237	
.oracle/checkins/batch-2-r3.md:1657: trailing whitespace.
++++++++++   248	
.oracle/checkins/batch-2-r3.md:1659: trailing whitespace.
++++++++++   249	
.oracle/checkins/batch-2-r3.md:1661: trailing whitespace.
++++++++++   271	
.oracle/checkins/batch-2-r3.md:1663: trailing whitespace.
++++++++++   272	
.oracle/checkins/batch-2-r3.md:1665: trailing whitespace.
++++++++++   288	
.oracle/checkins/batch-2-r3.md:1667: trailing whitespace.
++++++++++   295	
.oracle/checkins/batch-2-r3.md:1669: trailing whitespace.
++++++++++   316	
.oracle/checkins/batch-2-r3.md:1671: trailing whitespace.
++++++++++   343	
.oracle/checkins/batch-2-r3.md:1673: trailing whitespace.
++++++++++   344	
.oracle/checkins/batch-2-r3.md:1675: trailing whitespace.
++++++++++   347	
.oracle/checkins/batch-2-r3.md:1677: trailing whitespace.
++++++++++   349	
.oracle/checkins/batch-2-r3.md:1679: trailing whitespace.
++++++++++   350	
.oracle/checkins/batch-2-r3.md:1681: trailing whitespace.
++++++++++   353	
.oracle/checkins/batch-2-r3.md:1683: trailing whitespace.
++++++++++   357	
.oracle/checkins/batch-2-r3.md:1685: trailing whitespace.
++++++++++   358	
.oracle/checkins/batch-2-r3.md:1687: trailing whitespace.
++++++++++   361	
.oracle/checkins/batch-2-r3.md:1689: trailing whitespace.
++++++++++   366	
.oracle/checkins/batch-2-r3.md:1691: trailing whitespace.
++++++++++   367	
.oracle/checkins/batch-2-r3.md:1693: trailing whitespace.
++++++++++   370	
.oracle/checkins/batch-2-r3.md:1695: trailing whitespace.
++++++++++     2	
.oracle/checkins/batch-2-r3.md:1697: trailing whitespace.
++++++++++     8	
.oracle/checkins/batch-2-r3.md:1699: trailing whitespace.
++++++++++    10	
.oracle/checkins/batch-2-r3.md:1701: trailing whitespace.
++++++++++    18	
.oracle/checkins/batch-2-r3.md:1703: trailing whitespace.
++++++++++    21	
.oracle/checkins/batch-2-r3.md:1705: trailing whitespace.
++++++++++    22	
.oracle/checkins/batch-2-r3.md:1707: trailing whitespace.
++++++++++    24	
.oracle/checkins/batch-2-r3.md:1709: trailing whitespace.
++++++++++    35	
.oracle/checkins/batch-2-r3.md:1711: trailing whitespace.
++++++++++    40	
.oracle/checkins/batch-2-r3.md:1713: trailing whitespace.
++++++++++    52	
.oracle/checkins/batch-2-r3.md:1715: trailing whitespace.
++++++++++    73	
.oracle/checkins/batch-2-r3.md:1717: trailing whitespace.
++++++++++    93	
.oracle/checkins/batch-2-r3.md:1719: trailing whitespace.
++++++++++   110	
.oracle/checkins/batch-2-r3.md:1721: trailing whitespace.
++++++++++   123	
.oracle/checkins/batch-2-r3.md:1723: trailing whitespace.
++++++++++   130	
.oracle/checkins/batch-2-r3.md:1725: trailing whitespace.
++++++++++   131	
.oracle/checkins/batch-2-r3.md:1727: trailing whitespace.
++++++++++   134	
.oracle/checkins/batch-2-r3.md:1729: trailing whitespace.
++++++++++   158	
.oracle/checkins/batch-2-r3.md:1731: trailing whitespace.
++++++++++   159	
.oracle/checkins/batch-2-r3.md:1733: trailing whitespace.
++++++++++   165	
.oracle/checkins/batch-2-r3.md:1735: trailing whitespace.
++++++++++   166	
.oracle/checkins/batch-2-r3.md:1737: trailing whitespace.
++++++++++   171	
.oracle/checkins/batch-2-r3.md:1739: trailing whitespace.
++++++++++   172	
.oracle/checkins/batch-2-r3.md:1741: trailing whitespace.
++++++++++   186	
.oracle/checkins/batch-2-r3.md:1743: trailing whitespace.
++++++++++   187	
.oracle/checkins/batch-2-r3.md:1745: trailing whitespace.
++++++++++   194	
.oracle/checkins/batch-2-r3.md:1747: trailing whitespace.
++++++++++   195	
.oracle/checkins/batch-2-r3.md:1749: trailing whitespace.
++++++++++   205	
.oracle/checkins/batch-2-r3.md:1751: trailing whitespace.
++++++++++   206	
.oracle/checkins/batch-2-r3.md:1753: trailing whitespace.
++++++++++   209	
.oracle/checkins/batch-2-r3.md:1755: trailing whitespace.
++++++++++   215	
.oracle/checkins/batch-2-r3.md:1757: trailing whitespace.
++++++++++   216	
.oracle/checkins/batch-2-r3.md:1759: trailing whitespace.
++++++++++   225	
.oracle/checkins/batch-2-r3.md:1761: trailing whitespace.
++++++++++   226	
.oracle/checkins/batch-2-r3.md:1763: trailing whitespace.
++++++++++   231	
.oracle/checkins/batch-2-r3.md:1765: trailing whitespace.
++++++++++   232	
.oracle/checkins/batch-2-r3.md:1767: trailing whitespace.
++++++++++   241	
.oracle/checkins/batch-2-r3.md:1769: trailing whitespace.
++++++++++   242	
.oracle/checkins/batch-2-r3.md:1771: trailing whitespace.
++++++++++   248	
.oracle/checkins/batch-2-r3.md:1773: trailing whitespace.
++++++++++   249	
.oracle/checkins/batch-2-r3.md:1775: trailing whitespace.
++++++++++   507	
.oracle/checkins/batch-2-r3.md:1777: trailing whitespace.
++++++++++   511	
.oracle/checkins/batch-2-r3.md:1779: trailing whitespace.
++++++++++   530	
.oracle/checkins/batch-2-r3.md:1781: trailing whitespace.
++++++++++   563	
.oracle/checkins/batch-2-r3.md:1783: trailing whitespace.
++++++++++   564	
.oracle/checkins/batch-2-r3.md:1785: trailing whitespace.
++++++++++   571	
.oracle/checkins/batch-2-r3.md:1787: trailing whitespace.
++++++++++   576	
.oracle/checkins/batch-2-r3.md:1789: trailing whitespace.
++++++++++   582	
.oracle/checkins/batch-2-r3.md:1791: trailing whitespace.
++++++++++   583	
.oracle/checkins/batch-2-r3.md:1793: trailing whitespace.
++++++++++   587	
.oracle/checkins/batch-2-r3.md:1795: trailing whitespace.
++++++++++   592	
.oracle/checkins/batch-2-r3.md:1797: trailing whitespace.
++++++++++   604	
.oracle/checkins/batch-2-r3.md:1799: trailing whitespace.
++++++++++   609	
.oracle/checkins/batch-2-r3.md:1801: trailing whitespace.
++++++++++   621	
.oracle/checkins/batch-2-r3.md:1803: trailing whitespace.
++++++++++   633	
.oracle/checkins/batch-2-r3.md:1805: trailing whitespace.
++++++++++   634	
.oracle/checkins/batch-2-r3.md:1807: trailing whitespace.
++++++++++   655	
.oracle/checkins/batch-2-r3.md:1809: trailing whitespace.
++++++++++   656	
.oracle/checkins/batch-2-r3.md:1811: trailing whitespace.
++++++++++   660	
.oracle/checkins/batch-2-r3.md:1813: trailing whitespace.
++++++++++   667	
.oracle/checkins/batch-2-r3.md:1815: trailing whitespace.
++++++++++   690	
.oracle/checkins/batch-2-r3.md:1817: trailing whitespace.
++++++++++   702	
.oracle/checkins/batch-2-r3.md:1819: trailing whitespace.
++++++++++   717	
.oracle/checkins/batch-2-r3.md:1821: trailing whitespace.
++++++++++  1662	
.oracle/checkins/batch-2-r3.md:1823: trailing whitespace.
++++++++++  1686	
.oracle/checkins/batch-2-r3.md:1825: trailing whitespace.
++++++++++  1693	
.oracle/checkins/batch-2-r3.md:1827: trailing whitespace.
++++++++++  1694	
.oracle/checkins/batch-2-r3.md:1829: trailing whitespace.
++++++++++  1698	
.oracle/checkins/batch-2-r3.md:1831: trailing whitespace.
++++++++++  1705	
.oracle/checkins/batch-2-r3.md:1833: trailing whitespace.
++++++++++  1753	
.oracle/checkins/batch-2-r3.md:1835: trailing whitespace.
++++++++++  1757	
.oracle/checkins/batch-2-r3.md:1837: trailing whitespace.
++++++++++  1763	
.oracle/checkins/batch-2-r3.md:1839: trailing whitespace.
++++++++++  1769	
.oracle/checkins/batch-2-r3.md:1841: trailing whitespace.
++++++++++  1773	
.oracle/checkins/batch-2-r3.md:1843: trailing whitespace.
++++++++++     2	
.oracle/checkins/batch-2-r3.md:1845: trailing whitespace.
++++++++++     8	
.oracle/checkins/batch-2-r3.md:1847: trailing whitespace.
++++++++++    11	
.oracle/checkins/batch-2-r3.md:1849: trailing whitespace.
++++++++++    20	
.oracle/checkins/batch-2-r3.md:1851: trailing whitespace.
++++++++++    21	
.oracle/checkins/batch-2-r3.md:1853: trailing whitespace.
++++++++++    48	
.oracle/checkins/batch-2-r3.md:1855: trailing whitespace.
++++++++++    49	
.oracle/checkins/batch-2-r3.md:1857: trailing whitespace.
++++++++++    52	
.oracle/checkins/batch-2-r3.md:1859: trailing whitespace.
++++++++++    53	
.oracle/checkins/batch-2-r3.md:1861: trailing whitespace.
++++++++++    56	
.oracle/checkins/batch-2-r3.md:1863: trailing whitespace.
++++++++++    57	
.oracle/checkins/batch-2-r3.md:1865: trailing whitespace.
++++++++++    60	
.oracle/checkins/batch-2-r3.md:1867: trailing whitespace.
++++++++++    61	
.oracle/checkins/batch-2-r3.md:1869: trailing whitespace.
++++++++++    72	
.oracle/checkins/batch-2-r3.md:1871: trailing whitespace.
++++++++++    73	
.oracle/checkins/batch-2-r3.md:1873: trailing whitespace.
++++++++++    81	
.oracle/checkins/batch-2-r3.md:1875: trailing whitespace.
++++++++++    88	
.oracle/checkins/batch-2-r3.md:1877: trailing whitespace.
++++++++++    89	
.oracle/checkins/batch-2-r3.md:1879: trailing whitespace.
++++++++++    96	
.oracle/checkins/batch-2-r3.md:1881: trailing whitespace.
++++++++++    97	
.oracle/checkins/batch-2-r3.md:1883: trailing whitespace.
++++++++++   105	
.oracle/checkins/batch-2-r3.md:1885: trailing whitespace.
++++++++++   106	
.oracle/checkins/batch-2-r3.md:1887: trailing whitespace.
++++++++++   113	
.oracle/checkins/batch-2-r3.md:1889: trailing whitespace.
++++++++++   114	
.oracle/checkins/batch-2-r3.md:1891: trailing whitespace.
++++++++++   312	
.oracle/checkins/batch-2-r3.md:1893: trailing whitespace.
++++++++++   313	
.oracle/checkins/batch-2-r3.md:1895: trailing whitespace.
++++++++++   324	
.oracle/checkins/batch-2-r3.md:1897: trailing whitespace.
++++++++++   325	
.oracle/checkins/batch-2-r3.md:1899: trailing whitespace.
++++++++++   338	
.oracle/checkins/batch-2-r3.md:1901: trailing whitespace.
++++++++++   339	
.oracle/checkins/batch-2-r3.md:1903: trailing whitespace.
++++++++++   356	
.oracle/checkins/batch-2-r3.md:1905: trailing whitespace.
++++++++++   357	
.oracle/checkins/batch-2-r3.md:1907: trailing whitespace.
++++++++++   375	
.oracle/checkins/batch-2-r3.md:1909: trailing whitespace.
++++++++++   376	
.oracle/checkins/batch-2-r3.md:1911: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1913: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1915: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1917: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1919: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1921: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1923: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1925: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1927: trailing whitespace.
++++++++++ 
.oracle/checkins/batch-2-r3.md:1929: trailing whitespace.
++++++++++   809	
.oracle/checkins/batch-2-r3.md:1931: trailing whitespace.
++++++++++   810	
.oracle/checkins/batch-2-r3.md:1933: trailing whitespace.
++++++++++   904	
.oracle/checkins/batch-2-r3.md:1935: trailing whitespace.
++++++++++   905	
.oracle/checkins/batch-2-r3.md:1937: trailing whitespace.
++++++++++   965	
.oracle/checkins/batch-2-r3.md:1939: trailing whitespace.
++++++++++   966	
.oracle/checkins/batch-2-r3.md:1941: trailing whitespace.
++++++++++     2	
.oracle/checkins/batch-2-r3.md:1943: trailing whitespace.
++++++++++     4	
.oracle/checkins/batch-2-r3.md:1945: trailing whitespace.
++++++++++     6	
.oracle/checkins/batch-2-r3.md:1947: trailing whitespace.
++++++++++     8	
.oracle/checkins/batch-2-r3.md:1949: trailing whitespace.
++++++++++    17	
.oracle/checkins/batch-2-r3.md:1951: trailing whitespace.
++++++++++    19	
.oracle/checkins/batch-2-r3.md:1953: trailing whitespace.
++++++++++    25	
.oracle/checkins/batch-2-r3.md:1955: trailing whitespace.
++++++++++    27	
.oracle/checkins/batch-2-r3.md:1957: trailing whitespace.
++++++++++    29	
.oracle/checkins/batch-2-r3.md:1959: trailing whitespace.
++++++++++    31	
.oracle/checkins/batch-2-r3.md:1961: trailing whitespace.
++++++++++    40	
.oracle/checkins/batch-2-r3.md:1963: trailing whitespace.
++++++++++    42	
.oracle/checkins/batch-2-r3.md:1965: trailing whitespace.
++++++++++    49	
.oracle/checkins/batch-2-r3.md:1967: trailing whitespace.
++++++++++    51	
.oracle/checkins/batch-2-r3.md:1969: trailing whitespace.
++++++++++    53	
.oracle/checkins/batch-2-r3.md:1971: trailing whitespace.
++++++++++    55	
.oracle/checkins/batch-2-r3.md:1973: trailing whitespace.
++++++++++    63	
.oracle/checkins/batch-2-r3.md:1975: trailing whitespace.
++++++++++    65	
.oracle/checkins/batch-2-r3.md:1977: trailing whitespace.
++++++++++    72	
.oracle/checkins/batch-2-r3.md:1979: trailing whitespace.
++++++++++    74	
.oracle/checkins/batch-2-r3.md:1981: trailing whitespace.
++++++++++    76	
.oracle/checkins/batch-2-r3.md:1983: trailing whitespace.
++++++++++    78	
.oracle/checkins/batch-2-r3.md:1985: trailing whitespace.
++++++++++   131	
.oracle/checkins/batch-2-r3.md:1987: trailing whitespace.
++++++++++   132	
.oracle/checkins/batch-2-r3.md:1989: trailing whitespace.
++++++++++   162	
.oracle/checkins/batch-2-r3.md:1991: trailing whitespace.
++++++++++   163	
.oracle/checkins/batch-2-r3.md:1993: trailing whitespace.
++++++++++   178	
.oracle/checkins/batch-2-r3.md:1995: trailing whitespace.
++++++++++   179	
.oracle/checkins/batch-2-r3.md:1997: trailing whitespace.
++++++++++   206	
.oracle/checkins/batch-2-r3.md:1999: trailing whitespace.
++++++++++   207	
.oracle/checkins/batch-2-r3.md:2001: trailing whitespace.
++++++++++   249	
.oracle/checkins/batch-2-r3.md:2003: trailing whitespace.
++++++++++   250	
.oracle/checkins/batch-2-r3.md:2005: trailing whitespace.
++++++++++   288	
.oracle/checkins/batch-2-r3.md:2007: trailing whitespace.
++++++++++   289	
.oracle/checkins/batch-2-r3.md:2009: trailing whitespace.
++++++++++   302	
.oracle/checkins/batch-2-r3.md:2011: trailing whitespace.
++++++++++   303	
.oracle/checkins/batch-2-r3.md:2013: trailing whitespace.
++++++++++   312	
.oracle/checkins/batch-2-r3.md:2015: trailing whitespace.
++++++++++   313	
.oracle/checkins/batch-2-r3.md:2017: trailing whitespace.
++++++++++   330	
.oracle/checkins/batch-2-r3.md:2019: trailing whitespace.
++++++++++   331	
.oracle/checkins/batch-2-r3.md:2021: trailing whitespace.
++++++++++   343	
.oracle/checkins/batch-2-r3.md:2023: trailing whitespace.
++++++++++   344	
.oracle/checkins/batch-2-r3.md:2025: trailing whitespace.
++++++++++   288	
.oracle/checkins/batch-2-r3.md:2027: trailing whitespace.
++++++++++    98	
.oracle/checkins/batch-2-r3.md:2029: trailing whitespace.
++++++++++   101	
.oracle/checkins/batch-2-r3.md:2031: trailing whitespace.
++++++++++   106	
.oracle/checkins/batch-2-r3.md:2033: trailing whitespace.
++++++++++   107	
.oracle/checkins/batch-2-r3.md:2035: trailing whitespace.
++++++++++   110	
.oracle/checkins/batch-2-r3.md:2037: trailing whitespace.
++++++++++   113	
.oracle/checkins/batch-2-r3.md:2039: trailing whitespace.
++++++++++  1349	
.oracle/checkins/batch-2-r3.md:2041: trailing whitespace.
++++++++++  1350	
.oracle/checkins/batch-2-r3.md:2043: trailing whitespace.
++++++++++  1354	
.oracle/checkins/batch-2-r3.md:2045: trailing whitespace.
++++++++++  1365	
.oracle/checkins/batch-2-r3.md:2047: trailing whitespace.
++++++++++  1444	
.oracle/checkins/batch-2-r3.md:2049: trailing whitespace.
++++++++++  1460	
.oracle/checkins/batch-2-r3.md:2051: trailing whitespace.
+++++++++  1444	
.oracle/checkins/batch-2-r3.md:2053: trailing whitespace.
+++++++++  1460	
.oracle/checkins/batch-2-r3.md:2055: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2057: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2059: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2061: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2063: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2065: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2067: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2069: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2071: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2073: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2075: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2077: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2079: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2081: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2083: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2085: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2087: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2089: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2091: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2093: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2095: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2097: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2099: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2101: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2103: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2105: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2107: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2109: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2111: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2113: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2115: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2117: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2119: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2121: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2123: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2125: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2127: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2129: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2131: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2133: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2135: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2137: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2139: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2141: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2143: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2145: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2147: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2149: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2151: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2153: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2155: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2157: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2159: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2161: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2163: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2165: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2167: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2169: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2171: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2173: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2175: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2177: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2179: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2181: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2183: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2185: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2187: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2189: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2191: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2193: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2195: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2197: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2199: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2201: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2203: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2205: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2207: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2209: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2211: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2213: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2215: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2217: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2219: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2221: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2223: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2225: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2227: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2229: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2231: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2233: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2235: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2237: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2239: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2241: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2243: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2245: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2247: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2249: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2251: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2253: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2255: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2257: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2259: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2261: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2263: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2265: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2267: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2269: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2271: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2273: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2275: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2277: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2279: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2281: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2283: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2285: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2287: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r3.md:2289: trailing whitespace.
+++++++++     4	
.oracle/checkins/batch-2-r3.md:2291: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r3.md:2293: trailing whitespace.
+++++++++    11	
.oracle/checkins/batch-2-r3.md:2295: trailing whitespace.
+++++++++    28	
.oracle/checkins/batch-2-r3.md:2297: trailing whitespace.
+++++++++    29	
.oracle/checkins/batch-2-r3.md:2299: trailing whitespace.
+++++++++    32	
.oracle/checkins/batch-2-r3.md:2301: trailing whitespace.
+++++++++    33	
.oracle/checkins/batch-2-r3.md:2303: trailing whitespace.
+++++++++    38	
.oracle/checkins/batch-2-r3.md:2305: trailing whitespace.
+++++++++    40	
.oracle/checkins/batch-2-r3.md:2307: trailing whitespace.
+++++++++    41	
.oracle/checkins/batch-2-r3.md:2309: trailing whitespace.
+++++++++    53	
.oracle/checkins/batch-2-r3.md:2311: trailing whitespace.
+++++++++    54	
.oracle/checkins/batch-2-r3.md:2313: trailing whitespace.
+++++++++    81	
.oracle/checkins/batch-2-r3.md:2315: trailing whitespace.
+++++++++    82	
.oracle/checkins/batch-2-r3.md:2317: trailing whitespace.
+++++++++    85	
.oracle/checkins/batch-2-r3.md:2319: trailing whitespace.
+++++++++    92	
.oracle/checkins/batch-2-r3.md:2321: trailing whitespace.
+++++++++    93	
.oracle/checkins/batch-2-r3.md:2323: trailing whitespace.
+++++++++   105	
.oracle/checkins/batch-2-r3.md:2325: trailing whitespace.
+++++++++   106	
.oracle/checkins/batch-2-r3.md:2327: trailing whitespace.
+++++++++   173	
.oracle/checkins/batch-2-r3.md:2329: trailing whitespace.
+++++++++   174	
.oracle/checkins/batch-2-r3.md:2331: trailing whitespace.
+++++++++   248	
.oracle/checkins/batch-2-r3.md:2333: trailing whitespace.
+++++++++   249	
.oracle/checkins/batch-2-r3.md:2335: trailing whitespace.
+++++++++   260	
.oracle/checkins/batch-2-r3.md:2337: trailing whitespace.
+++++++++   261	
.oracle/checkins/batch-2-r3.md:2339: trailing whitespace.
+++++++++   283	
.oracle/checkins/batch-2-r3.md:2341: trailing whitespace.
+++++++++   284	
.oracle/checkins/batch-2-r3.md:2343: trailing whitespace.
+++++++++   300	
.oracle/checkins/batch-2-r3.md:2345: trailing whitespace.
+++++++++   307	
.oracle/checkins/batch-2-r3.md:2347: trailing whitespace.
+++++++++   328	
.oracle/checkins/batch-2-r3.md:2349: trailing whitespace.
+++++++++   355	
.oracle/checkins/batch-2-r3.md:2351: trailing whitespace.
+++++++++   356	
.oracle/checkins/batch-2-r3.md:2353: trailing whitespace.
+++++++++   359	
.oracle/checkins/batch-2-r3.md:2355: trailing whitespace.
+++++++++   361	
.oracle/checkins/batch-2-r3.md:2357: trailing whitespace.
+++++++++   362	
.oracle/checkins/batch-2-r3.md:2359: trailing whitespace.
+++++++++   365	
.oracle/checkins/batch-2-r3.md:2361: trailing whitespace.
+++++++++   369	
.oracle/checkins/batch-2-r3.md:2363: trailing whitespace.
+++++++++   370	
.oracle/checkins/batch-2-r3.md:2365: trailing whitespace.
+++++++++   373	
.oracle/checkins/batch-2-r3.md:2367: trailing whitespace.
+++++++++   378	
.oracle/checkins/batch-2-r3.md:2369: trailing whitespace.
+++++++++   379	
.oracle/checkins/batch-2-r3.md:2371: trailing whitespace.
+++++++++   382	
.oracle/checkins/batch-2-r3.md:2373: trailing whitespace.
+++++++++   384	
.oracle/checkins/batch-2-r3.md:2375: trailing whitespace.
+++++++++   385	
.oracle/checkins/batch-2-r3.md:2377: trailing whitespace.
+++++++++   651	
.oracle/checkins/batch-2-r3.md:2379: trailing whitespace.
+++++++++   652	
.oracle/checkins/batch-2-r3.md:2381: trailing whitespace.
+++++++++   683	
.oracle/checkins/batch-2-r3.md:2383: trailing whitespace.
+++++++++   693	
.oracle/checkins/batch-2-r3.md:2385: trailing whitespace.
+++++++++   729	
.oracle/checkins/batch-2-r3.md:2387: trailing whitespace.
+++++++++   730	
.oracle/checkins/batch-2-r3.md:2389: trailing whitespace.
+++++++++   748	
.oracle/checkins/batch-2-r3.md:2391: trailing whitespace.
+++++++++   749	
.oracle/checkins/batch-2-r3.md:2393: trailing whitespace.
+++++++++   785	
.oracle/checkins/batch-2-r3.md:2395: trailing whitespace.
+++++++++   786	
.oracle/checkins/batch-2-r3.md:2397: trailing whitespace.
+++++++++   800	
.oracle/checkins/batch-2-r3.md:2399: trailing whitespace.
+++++++++   801	
.oracle/checkins/batch-2-r3.md:2401: trailing whitespace.
+++++++++   817	
.oracle/checkins/batch-2-r3.md:2403: trailing whitespace.
+++++++++   818	
.oracle/checkins/batch-2-r3.md:2405: trailing whitespace.
+++++++++   914	
.oracle/checkins/batch-2-r3.md:2407: trailing whitespace.
+++++++++   915	
.oracle/checkins/batch-2-r3.md:2409: trailing whitespace.
+++++++++  1001	
.oracle/checkins/batch-2-r3.md:2411: trailing whitespace.
+++++++++  1002	
.oracle/checkins/batch-2-r3.md:2413: trailing whitespace.
+++++++++  1011	
.oracle/checkins/batch-2-r3.md:2415: trailing whitespace.
+++++++++  1012	
.oracle/checkins/batch-2-r3.md:2417: trailing whitespace.
+++++++++   285	
.oracle/checkins/batch-2-r3.md:2419: trailing whitespace.
+++++++++   294	
.oracle/checkins/batch-2-r3.md:2421: trailing whitespace.
+++++++++   295	
.oracle/checkins/batch-2-r3.md:2423: trailing whitespace.
+++++++++   302	
.oracle/checkins/batch-2-r3.md:2425: trailing whitespace.
+++++++++   303	
.oracle/checkins/batch-2-r3.md:2427: trailing whitespace.
+++++++++   312	
.oracle/checkins/batch-2-r3.md:2429: trailing whitespace.
+++++++++   313	
.oracle/checkins/batch-2-r3.md:2431: trailing whitespace.
+++++++++   330	
.oracle/checkins/batch-2-r3.md:2433: trailing whitespace.
+++++++++   331	
.oracle/checkins/batch-2-r3.md:2435: trailing whitespace.
+++++++++   826	
.oracle/checkins/batch-2-r3.md:2437: trailing whitespace.
+++++++++   868	
.oracle/checkins/batch-2-r3.md:2439: trailing whitespace.
+++++++++   875	
.oracle/checkins/batch-2-r3.md:2441: trailing whitespace.
+++++++++   878	
.oracle/checkins/batch-2-r3.md:2443: trailing whitespace.
+++++++++   892	
.oracle/checkins/batch-2-r3.md:2445: trailing whitespace.
+++++++++   893	
.oracle/checkins/batch-2-r3.md:2447: trailing whitespace.
+++++++++   897	
.oracle/checkins/batch-2-r3.md:2449: trailing whitespace.
+++++++++   905	
.oracle/checkins/batch-2-r3.md:2451: trailing whitespace.
+++++++++   936	
.oracle/checkins/batch-2-r3.md:2453: trailing whitespace.
+++++++++   949	
.oracle/checkins/batch-2-r3.md:2455: trailing whitespace.
+++++++++   980	
.oracle/checkins/batch-2-r3.md:2457: trailing whitespace.
+++++++++   987	
.oracle/checkins/batch-2-r3.md:2459: trailing whitespace.
+++++++++   988	
.oracle/checkins/batch-2-r3.md:2461: trailing whitespace.
+++++++++   992	
.oracle/checkins/batch-2-r3.md:2463: trailing whitespace.
+++++++++  1000	
.oracle/checkins/batch-2-r3.md:2465: trailing whitespace.
+++++++++   440	
.oracle/checkins/batch-2-r3.md:2467: trailing whitespace.
+++++++++   441	
.oracle/checkins/batch-2-r3.md:2469: trailing whitespace.
+++++++++   445	
.oracle/checkins/batch-2-r3.md:2471: trailing whitespace.
+++++++++   459	
.oracle/checkins/batch-2-r3.md:2473: trailing whitespace.
+++++++++   507	
.oracle/checkins/batch-2-r3.md:2475: trailing whitespace.
+++++++++   511	
.oracle/checkins/batch-2-r3.md:2477: trailing whitespace.
+++++++++   530	
.oracle/checkins/batch-2-r3.md:2479: trailing whitespace.
+++++++++   563	
.oracle/checkins/batch-2-r3.md:2481: trailing whitespace.
+++++++++   564	
.oracle/checkins/batch-2-r3.md:2483: trailing whitespace.
+++++++++   571	
.oracle/checkins/batch-2-r3.md:2485: trailing whitespace.
+++++++++   576	
.oracle/checkins/batch-2-r3.md:2487: trailing whitespace.
+++++++++   582	
.oracle/checkins/batch-2-r3.md:2489: trailing whitespace.
+++++++++   583	
.oracle/checkins/batch-2-r3.md:2491: trailing whitespace.
+++++++++   587	
.oracle/checkins/batch-2-r3.md:2493: trailing whitespace.
+++++++++   592	
.oracle/checkins/batch-2-r3.md:2495: trailing whitespace.
+++++++++   604	
.oracle/checkins/batch-2-r3.md:2497: trailing whitespace.
+++++++++   609	
.oracle/checkins/batch-2-r3.md:2499: trailing whitespace.
+++++++++   621	
.oracle/checkins/batch-2-r3.md:2501: trailing whitespace.
+++++++++   633	
.oracle/checkins/batch-2-r3.md:2503: trailing whitespace.
+++++++++   634	
.oracle/checkins/batch-2-r3.md:2505: trailing whitespace.
+++++++++   655	
.oracle/checkins/batch-2-r3.md:2507: trailing whitespace.
+++++++++   656	
.oracle/checkins/batch-2-r3.md:2509: trailing whitespace.
+++++++++   660	
.oracle/checkins/batch-2-r3.md:2511: trailing whitespace.
+++++++++   667	
.oracle/checkins/batch-2-r3.md:2513: trailing whitespace.
+++++++++   690	
.oracle/checkins/batch-2-r3.md:2515: trailing whitespace.
+++++++++   702	
.oracle/checkins/batch-2-r3.md:2517: trailing whitespace.
+++++++++   717	
.oracle/checkins/batch-2-r3.md:2519: trailing whitespace.
+++++++++   225	
.oracle/checkins/batch-2-r3.md:2521: trailing whitespace.
+++++++++   230	
.oracle/checkins/batch-2-r3.md:2523: trailing whitespace.
+++++++++   238	
.oracle/checkins/batch-2-r3.md:2525: trailing whitespace.
+++++++++   240	
.oracle/checkins/batch-2-r3.md:2527: trailing whitespace.
+++++++++   243	
.oracle/checkins/batch-2-r3.md:2529: trailing whitespace.
+++++++++   251	
.oracle/checkins/batch-2-r3.md:2531: trailing whitespace.
+++++++++   255	
.oracle/checkins/batch-2-r3.md:2533: trailing whitespace.
+++++++++   257	
.oracle/checkins/batch-2-r3.md:2535: trailing whitespace.
+++++++++   262	
.oracle/checkins/batch-2-r3.md:2537: trailing whitespace.
+++++++++   274	
.oracle/checkins/batch-2-r3.md:2539: trailing whitespace.
+++++++++   276	
.oracle/checkins/batch-2-r3.md:2541: trailing whitespace.
+++++++++   280	
.oracle/checkins/batch-2-r3.md:2543: trailing whitespace.
+++++++++   290	
.oracle/checkins/batch-2-r3.md:2545: trailing whitespace.
+++++++++   292	
.oracle/checkins/batch-2-r3.md:2547: trailing whitespace.
+++++++++   461	
.oracle/checkins/batch-2-r3.md:2549: trailing whitespace.
+++++++++   463	
.oracle/checkins/batch-2-r3.md:2551: trailing whitespace.
+++++++++   465	
.oracle/checkins/batch-2-r3.md:2553: trailing whitespace.
+++++++++   470	
.oracle/checkins/batch-2-r3.md:2555: trailing whitespace.
+++++++++   492	
.oracle/checkins/batch-2-r3.md:2557: trailing whitespace.
+++++++++   502	
.oracle/checkins/batch-2-r3.md:2559: trailing whitespace.
+++++++++   504	
.oracle/checkins/batch-2-r3.md:2561: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r3.md:2563: trailing whitespace.
+++++++++     4	
.oracle/checkins/batch-2-r3.md:2565: trailing whitespace.
+++++++++     6	
.oracle/checkins/batch-2-r3.md:2567: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r3.md:2569: trailing whitespace.
+++++++++    17	
.oracle/checkins/batch-2-r3.md:2571: trailing whitespace.
+++++++++    19	
.oracle/checkins/batch-2-r3.md:2573: trailing whitespace.
+++++++++    25	
.oracle/checkins/batch-2-r3.md:2575: trailing whitespace.
+++++++++    27	
.oracle/checkins/batch-2-r3.md:2577: trailing whitespace.
+++++++++    29	
.oracle/checkins/batch-2-r3.md:2579: trailing whitespace.
+++++++++    31	
.oracle/checkins/batch-2-r3.md:2581: trailing whitespace.
+++++++++    40	
.oracle/checkins/batch-2-r3.md:2583: trailing whitespace.
+++++++++    42	
.oracle/checkins/batch-2-r3.md:2585: trailing whitespace.
+++++++++    49	
.oracle/checkins/batch-2-r3.md:2587: trailing whitespace.
+++++++++    51	
.oracle/checkins/batch-2-r3.md:2589: trailing whitespace.
+++++++++    53	
.oracle/checkins/batch-2-r3.md:2591: trailing whitespace.
+++++++++    55	
.oracle/checkins/batch-2-r3.md:2593: trailing whitespace.
+++++++++    63	
.oracle/checkins/batch-2-r3.md:2595: trailing whitespace.
+++++++++    65	
.oracle/checkins/batch-2-r3.md:2597: trailing whitespace.
+++++++++    72	
.oracle/checkins/batch-2-r3.md:2599: trailing whitespace.
+++++++++    74	
.oracle/checkins/batch-2-r3.md:2601: trailing whitespace.
+++++++++    76	
.oracle/checkins/batch-2-r3.md:2603: trailing whitespace.
+++++++++    78	
.oracle/checkins/batch-2-r3.md:2605: trailing whitespace.
+++++++++    86	
.oracle/checkins/batch-2-r3.md:2607: trailing whitespace.
+++++++++    88	
.oracle/checkins/batch-2-r3.md:2609: trailing whitespace.
+++++++++    94	
.oracle/checkins/batch-2-r3.md:2611: trailing whitespace.
+++++++++    96	
.oracle/checkins/batch-2-r3.md:2613: trailing whitespace.
+++++++++    98	
.oracle/checkins/batch-2-r3.md:2615: trailing whitespace.
+++++++++   100	
.oracle/checkins/batch-2-r3.md:2617: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2619: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2621: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2623: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2625: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2627: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r3.md:2629: trailing whitespace.
+++++++++   105	
.oracle/checkins/batch-2-r3.md:2631: trailing whitespace.
+++++++++   106	
.oracle/checkins/batch-2-r3.md:2633: trailing whitespace.
+++++++++   168	
.oracle/checkins/batch-2-r3.md:2635: trailing whitespace.
+++++++++   169	
.oracle/checkins/batch-2-r3.md:2637: trailing whitespace.
+++++++++   236	
.oracle/checkins/batch-2-r3.md:2639: trailing whitespace.
+++++++++   237	
.oracle/checkins/batch-2-r3.md:2641: trailing whitespace.
+++++++++   248	
.oracle/checkins/batch-2-r3.md:2643: trailing whitespace.
+++++++++   249	
.oracle/checkins/batch-2-r3.md:2645: trailing whitespace.
+++++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-2-r3.md:2647: trailing whitespace.
+++++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-2-r3.md:2649: trailing whitespace.
+++++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-2-r3.md:2651: trailing whitespace.
+++++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-2-r3.md:2653: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r3.md:2655: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r3.md:2657: trailing whitespace.
+++++++++    11	
.oracle/checkins/batch-2-r3.md:2659: trailing whitespace.
+++++++++    20	
.oracle/checkins/batch-2-r3.md:2661: trailing whitespace.
+++++++++    21	
.oracle/checkins/batch-2-r3.md:2663: trailing whitespace.
+++++++++    48	
.oracle/checkins/batch-2-r3.md:2665: trailing whitespace.
+++++++++    49	
.oracle/checkins/batch-2-r3.md:2667: trailing whitespace.
+++++++++    52	
.oracle/checkins/batch-2-r3.md:2669: trailing whitespace.
+++++++++    53	
.oracle/checkins/batch-2-r3.md:2671: trailing whitespace.
+++++++++    56	
.oracle/checkins/batch-2-r3.md:2673: trailing whitespace.
+++++++++    57	
.oracle/checkins/batch-2-r3.md:2675: trailing whitespace.
+++++++++    60	
.oracle/checkins/batch-2-r3.md:2677: trailing whitespace.
+++++++++    61	
.oracle/checkins/batch-2-r3.md:2679: trailing whitespace.
+++++++++    72	
.oracle/checkins/batch-2-r3.md:2681: trailing whitespace.
+++++++++    73	
.oracle/checkins/batch-2-r3.md:2683: trailing whitespace.
+++++++++    81	
.oracle/checkins/batch-2-r3.md:2685: trailing whitespace.
+++++++++    88	
.oracle/checkins/batch-2-r3.md:2687: trailing whitespace.
+++++++++    89	
.oracle/checkins/batch-2-r3.md:2689: trailing whitespace.
+++++++++    96	
.oracle/checkins/batch-2-r3.md:2691: trailing whitespace.
+++++++++    97	
.oracle/checkins/batch-2-r3.md:2693: trailing whitespace.
+++++++++   105	
.oracle/checkins/batch-2-r3.md:2695: trailing whitespace.
+++++++++   106	
.oracle/checkins/batch-2-r3.md:2697: trailing whitespace.
+++++++++   113	
.oracle/checkins/batch-2-r3.md:2699: trailing whitespace.
+++++++++   114	
.oracle/checkins/batch-2-r3.md:2701: trailing whitespace.
+++++++++   122	
.oracle/checkins/batch-2-r3.md:2703: trailing whitespace.
+++++++++   123	
.oracle/checkins/batch-2-r3.md:2705: trailing whitespace.
+++++++++   131	
.oracle/checkins/batch-2-r3.md:2707: trailing whitespace.
+++++++++   132	
.oracle/checkins/batch-2-r3.md:2709: trailing whitespace.
+++++++++   162	
.oracle/checkins/batch-2-r3.md:2711: trailing whitespace.
+++++++++   163	
.oracle/checkins/batch-2-r3.md:2713: trailing whitespace.
+++++++++   178	
.oracle/checkins/batch-2-r3.md:2715: trailing whitespace.
+++++++++   179	
.oracle/checkins/batch-2-r3.md:2717: trailing whitespace.
+++++++++   206	
.oracle/checkins/batch-2-r3.md:2719: trailing whitespace.
+++++++++   207	
.oracle/checkins/batch-2-r3.md:2721: trailing whitespace.
+++++++++   249	
.oracle/checkins/batch-2-r3.md:2723: trailing whitespace.
+++++++++   250	
.oracle/checkins/batch-2-r3.md:2725: trailing whitespace.
+++++++++   288	
.oracle/checkins/batch-2-r3.md:2727: trailing whitespace.
+++++++++   289	
.oracle/checkins/batch-2-r3.md:2729: trailing whitespace.
+++++++++   312	
.oracle/checkins/batch-2-r3.md:2731: trailing whitespace.
+++++++++   313	
.oracle/checkins/batch-2-r3.md:2733: trailing whitespace.
+++++++++   324	
.oracle/checkins/batch-2-r3.md:2735: trailing whitespace.
+++++++++   325	
.oracle/checkins/batch-2-r3.md:2737: trailing whitespace.
+++++++++   338	
.oracle/checkins/batch-2-r3.md:2739: trailing whitespace.
+++++++++   339	
.oracle/checkins/batch-2-r3.md:2741: trailing whitespace.
+++++++++   356	
.oracle/checkins/batch-2-r3.md:2743: trailing whitespace.
+++++++++   357	
.oracle/checkins/batch-2-r3.md:2745: trailing whitespace.
+++++++++   375	
.oracle/checkins/batch-2-r3.md:2747: trailing whitespace.
+++++++++   376	
.oracle/checkins/batch-2-r3.md:2749: trailing whitespace.
+++++++++    35	
.oracle/checkins/batch-2-r3.md:2751: trailing whitespace.
+++++++++    40	
.oracle/checkins/batch-2-r3.md:2753: trailing whitespace.
+++++++++    52	
.oracle/checkins/batch-2-r3.md:2755: trailing whitespace.
+++++++++    73	
.oracle/checkins/batch-2-r3.md:2757: trailing whitespace.
+++++++++   205	
.oracle/checkins/batch-2-r3.md:2759: trailing whitespace.
+++++++++   206	
.oracle/checkins/batch-2-r3.md:2761: trailing whitespace.
+++++++++   209	
.oracle/checkins/batch-2-r3.md:2763: trailing whitespace.
+++++++++   215	
.oracle/checkins/batch-2-r3.md:2765: trailing whitespace.
+++++++++   216	
.oracle/checkins/batch-2-r3.md:2767: trailing whitespace.
+++++++++   225	
.oracle/checkins/batch-2-r3.md:2769: trailing whitespace.
+++++++++   226	
.oracle/checkins/batch-2-r3.md:2771: trailing whitespace.
+++++++++   231	
.oracle/checkins/batch-2-r3.md:2773: trailing whitespace.
+++++++++   232	
.oracle/checkins/batch-2-r3.md:2775: trailing whitespace.
+++++++++   288	
.oracle/checkins/batch-2-r3.md:2777: trailing whitespace.
+++++++++   289	
.oracle/checkins/batch-2-r3.md:2779: trailing whitespace.
+++++++++   158	
.oracle/checkins/batch-2-r3.md:2781: trailing whitespace.
+++++++++   159	
.oracle/checkins/batch-2-r3.md:2783: trailing whitespace.
+++++++++   165	
.oracle/checkins/batch-2-r3.md:2785: trailing whitespace.
+++++++++   166	
.oracle/checkins/batch-2-r3.md:2787: trailing whitespace.
+++++++++   171	
.oracle/checkins/batch-2-r3.md:2789: trailing whitespace.
+++++++++   172	
.oracle/checkins/batch-2-r3.md:2791: trailing whitespace.
+++++++++   186	
.oracle/checkins/batch-2-r3.md:2793: trailing whitespace.
+++++++++   187	
.oracle/checkins/batch-2-r3.md:2795: trailing whitespace.
+++++++++   194	
.oracle/checkins/batch-2-r3.md:2797: trailing whitespace.
+++++++++   195	
.oracle/checkins/batch-2-r3.md:2799: trailing whitespace.
+++++++++   205	
.oracle/checkins/batch-2-r3.md:2801: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2803: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2805: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2807: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2809: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2811: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2813: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2815: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2817: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2819: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2821: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2823: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2825: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2827: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2829: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2831: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2833: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2835: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2837: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2839: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2841: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2843: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2845: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2847: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2849: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2851: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2853: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2855: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2857: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2859: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2861: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2863: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2865: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2867: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2869: trailing whitespace.
++++++++    92	
.oracle/checkins/batch-2-r3.md:2871: trailing whitespace.
++++++++    93	
.oracle/checkins/batch-2-r3.md:2873: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r3.md:2875: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r3.md:2877: trailing whitespace.
++++++++   181	
.oracle/checkins/batch-2-r3.md:2879: trailing whitespace.
++++++++   182	
.oracle/checkins/batch-2-r3.md:2881: trailing whitespace.
++++++++   285	
.oracle/checkins/batch-2-r3.md:2883: trailing whitespace.
++++++++   294	
.oracle/checkins/batch-2-r3.md:2885: trailing whitespace.
++++++++   295	
.oracle/checkins/batch-2-r3.md:2887: trailing whitespace.
++++++++   302	
.oracle/checkins/batch-2-r3.md:2889: trailing whitespace.
++++++++   303	
.oracle/checkins/batch-2-r3.md:2891: trailing whitespace.
++++++++   312	
.oracle/checkins/batch-2-r3.md:2893: trailing whitespace.
++++++++   313	
.oracle/checkins/batch-2-r3.md:2895: trailing whitespace.
++++++++   330	
.oracle/checkins/batch-2-r3.md:2897: trailing whitespace.
++++++++   331	
.oracle/checkins/batch-2-r3.md:2899: trailing whitespace.
++++++++   582	
.oracle/checkins/batch-2-r3.md:2901: trailing whitespace.
++++++++   583	
.oracle/checkins/batch-2-r3.md:2903: trailing whitespace.
++++++++   587	
.oracle/checkins/batch-2-r3.md:2905: trailing whitespace.
++++++++   592	
.oracle/checkins/batch-2-r3.md:2907: trailing whitespace.
++++++++   604	
.oracle/checkins/batch-2-r3.md:2909: trailing whitespace.
++++++++   609	
.oracle/checkins/batch-2-r3.md:2911: trailing whitespace.
++++++++   621	
.oracle/checkins/batch-2-r3.md:2913: trailing whitespace.
++++++++   633	
.oracle/checkins/batch-2-r3.md:2915: trailing whitespace.
++++++++   634	
.oracle/checkins/batch-2-r3.md:2917: trailing whitespace.
++++++++   655	
.oracle/checkins/batch-2-r3.md:2919: trailing whitespace.
++++++++   656	
.oracle/checkins/batch-2-r3.md:2921: trailing whitespace.
++++++++   660	
.oracle/checkins/batch-2-r3.md:2923: trailing whitespace.
++++++++   667	
.oracle/checkins/batch-2-r3.md:2925: trailing whitespace.
++++++++   690	
.oracle/checkins/batch-2-r3.md:2927: trailing whitespace.
++++++++   702	
.oracle/checkins/batch-2-r3.md:2929: trailing whitespace.
++++++++   717	
.oracle/checkins/batch-2-r3.md:2931: trailing whitespace.
++++++++   738	
.oracle/checkins/batch-2-r3.md:2933: trailing whitespace.
++++++++   739	
.oracle/checkins/batch-2-r3.md:2935: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2937: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2939: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2941: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:2943: trailing whitespace.
++++++++   520	
.oracle/checkins/batch-2-r3.md:2945: trailing whitespace.
++++++++   539	
.oracle/checkins/batch-2-r3.md:2947: trailing whitespace.
++++++++   540	
.oracle/checkins/batch-2-r3.md:2949: trailing whitespace.
++++++++   550	
.oracle/checkins/batch-2-r3.md:2951: trailing whitespace.
++++++++   551	
.oracle/checkins/batch-2-r3.md:2953: trailing whitespace.
++++++++   613	
.oracle/checkins/batch-2-r3.md:2955: trailing whitespace.
++++++++   617	
.oracle/checkins/batch-2-r3.md:2957: trailing whitespace.
++++++++   618	
.oracle/checkins/batch-2-r3.md:2959: trailing whitespace.
++++++++   631	
.oracle/checkins/batch-2-r3.md:2961: trailing whitespace.
++++++++   632	
.oracle/checkins/batch-2-r3.md:2963: trailing whitespace.
++++++++   635	
.oracle/checkins/batch-2-r3.md:2965: trailing whitespace.
++++++++   644	
.oracle/checkins/batch-2-r3.md:2967: trailing whitespace.
++++++++   645	
.oracle/checkins/batch-2-r3.md:2969: trailing whitespace.
++++++++   651	
.oracle/checkins/batch-2-r3.md:2971: trailing whitespace.
++++++++   652	
.oracle/checkins/batch-2-r3.md:2973: trailing whitespace.
++++++++   683	
.oracle/checkins/batch-2-r3.md:2975: trailing whitespace.
++++++++   693	
.oracle/checkins/batch-2-r3.md:2977: trailing whitespace.
++++++++   729	
.oracle/checkins/batch-2-r3.md:2979: trailing whitespace.
++++++++   730	
.oracle/checkins/batch-2-r3.md:2981: trailing whitespace.
++++++++   748	
.oracle/checkins/batch-2-r3.md:2983: trailing whitespace.
++++++++   749	
.oracle/checkins/batch-2-r3.md:2985: trailing whitespace.
++++++++   785	
.oracle/checkins/batch-2-r3.md:2987: trailing whitespace.
++++++++   786	
.oracle/checkins/batch-2-r3.md:2989: trailing whitespace.
++++++++   800	
.oracle/checkins/batch-2-r3.md:2991: trailing whitespace.
++++++++   801	
.oracle/checkins/batch-2-r3.md:2993: trailing whitespace.
++++++++   817	
.oracle/checkins/batch-2-r3.md:2995: trailing whitespace.
++++++++   818	
.oracle/checkins/batch-2-r3.md:2997: trailing whitespace.
++++++++   914	
.oracle/checkins/batch-2-r3.md:2999: trailing whitespace.
++++++++   915	
.oracle/checkins/batch-2-r3.md:3001: trailing whitespace.
++++++++  1014	
.oracle/checkins/batch-2-r3.md:3003: trailing whitespace.
++++++++  1015	
.oracle/checkins/batch-2-r3.md:3005: trailing whitespace.
++++++++  1024	
.oracle/checkins/batch-2-r3.md:3007: trailing whitespace.
++++++++  1025	
.oracle/checkins/batch-2-r3.md:3009: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r3.md:3011: trailing whitespace.
++++++++     4	
.oracle/checkins/batch-2-r3.md:3013: trailing whitespace.
++++++++     6	
.oracle/checkins/batch-2-r3.md:3015: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r3.md:3017: trailing whitespace.
++++++++    17	
.oracle/checkins/batch-2-r3.md:3019: trailing whitespace.
++++++++    19	
.oracle/checkins/batch-2-r3.md:3021: trailing whitespace.
++++++++    25	
.oracle/checkins/batch-2-r3.md:3023: trailing whitespace.
++++++++    27	
.oracle/checkins/batch-2-r3.md:3025: trailing whitespace.
++++++++    29	
.oracle/checkins/batch-2-r3.md:3027: trailing whitespace.
++++++++    31	
.oracle/checkins/batch-2-r3.md:3029: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r3.md:3031: trailing whitespace.
++++++++    42	
.oracle/checkins/batch-2-r3.md:3033: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r3.md:3035: trailing whitespace.
++++++++    51	
.oracle/checkins/batch-2-r3.md:3037: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r3.md:3039: trailing whitespace.
++++++++    55	
.oracle/checkins/batch-2-r3.md:3041: trailing whitespace.
++++++++    63	
.oracle/checkins/batch-2-r3.md:3043: trailing whitespace.
++++++++    65	
.oracle/checkins/batch-2-r3.md:3045: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r3.md:3047: trailing whitespace.
++++++++    74	
.oracle/checkins/batch-2-r3.md:3049: trailing whitespace.
++++++++    76	
.oracle/checkins/batch-2-r3.md:3051: trailing whitespace.
++++++++    78	
.oracle/checkins/batch-2-r3.md:3053: trailing whitespace.
++++++++    86	
.oracle/checkins/batch-2-r3.md:3055: trailing whitespace.
++++++++    88	
.oracle/checkins/batch-2-r3.md:3057: trailing whitespace.
++++++++    94	
.oracle/checkins/batch-2-r3.md:3059: trailing whitespace.
++++++++    96	
.oracle/checkins/batch-2-r3.md:3061: trailing whitespace.
++++++++    98	
.oracle/checkins/batch-2-r3.md:3063: trailing whitespace.
++++++++   100	
.oracle/checkins/batch-2-r3.md:3065: trailing whitespace.
++++++++   109	
.oracle/checkins/batch-2-r3.md:3067: trailing whitespace.
++++++++   111	
.oracle/checkins/batch-2-r3.md:3069: trailing whitespace.
++++++++   119	
.oracle/checkins/batch-2-r3.md:3071: trailing whitespace.
++++++++   121	
.oracle/checkins/batch-2-r3.md:3073: trailing whitespace.
++++++++   123	
.oracle/checkins/batch-2-r3.md:3075: trailing whitespace.
++++++++   125	
.oracle/checkins/batch-2-r3.md:3077: trailing whitespace.
++++++++   133	
.oracle/checkins/batch-2-r3.md:3079: trailing whitespace.
++++++++   135	
.oracle/checkins/batch-2-r3.md:3081: trailing whitespace.
++++++++   142	
.oracle/checkins/batch-2-r3.md:3083: trailing whitespace.
++++++++   144	
.oracle/checkins/batch-2-r3.md:3085: trailing whitespace.
++++++++   146	
.oracle/checkins/batch-2-r3.md:3087: trailing whitespace.
++++++++   148	
.oracle/checkins/batch-2-r3.md:3089: trailing whitespace.
++++++++   159	
.oracle/checkins/batch-2-r3.md:3091: trailing whitespace.
++++++++   161	
.oracle/checkins/batch-2-r3.md:3093: trailing whitespace.
++++++++   168	
.oracle/checkins/batch-2-r3.md:3095: trailing whitespace.
++++++++   170	
.oracle/checkins/batch-2-r3.md:3097: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r3.md:3099: trailing whitespace.
++++++++     4	
.oracle/checkins/batch-2-r3.md:3101: trailing whitespace.
++++++++     6	
.oracle/checkins/batch-2-r3.md:3103: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r3.md:3105: trailing whitespace.
++++++++    17	
.oracle/checkins/batch-2-r3.md:3107: trailing whitespace.
++++++++    19	
.oracle/checkins/batch-2-r3.md:3109: trailing whitespace.
++++++++    25	
.oracle/checkins/batch-2-r3.md:3111: trailing whitespace.
++++++++    27	
.oracle/checkins/batch-2-r3.md:3113: trailing whitespace.
++++++++    29	
.oracle/checkins/batch-2-r3.md:3115: trailing whitespace.
++++++++    31	
.oracle/checkins/batch-2-r3.md:3117: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r3.md:3119: trailing whitespace.
++++++++    42	
.oracle/checkins/batch-2-r3.md:3121: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r3.md:3123: trailing whitespace.
++++++++    51	
.oracle/checkins/batch-2-r3.md:3125: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r3.md:3127: trailing whitespace.
++++++++    55	
.oracle/checkins/batch-2-r3.md:3129: trailing whitespace.
++++++++    63	
.oracle/checkins/batch-2-r3.md:3131: trailing whitespace.
++++++++    65	
.oracle/checkins/batch-2-r3.md:3133: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r3.md:3135: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r3.md:3137: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r3.md:3139: trailing whitespace.
++++++++   173	
.oracle/checkins/batch-2-r3.md:3141: trailing whitespace.
++++++++   174	
.oracle/checkins/batch-2-r3.md:3143: trailing whitespace.
++++++++A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-2-r3.md:3145: trailing whitespace.
++++++++   186	
.oracle/checkins/batch-2-r3.md:3147: trailing whitespace.
++++++++   187	
.oracle/checkins/batch-2-r3.md:3149: trailing whitespace.
++++++++   194	
.oracle/checkins/batch-2-r3.md:3151: trailing whitespace.
++++++++   195	
.oracle/checkins/batch-2-r3.md:3153: trailing whitespace.
++++++++   205	
.oracle/checkins/batch-2-r3.md:3155: trailing whitespace.
++++++++   206	
.oracle/checkins/batch-2-r3.md:3157: trailing whitespace.
++++++++   209	
.oracle/checkins/batch-2-r3.md:3159: trailing whitespace.
++++++++   215	
.oracle/checkins/batch-2-r3.md:3161: trailing whitespace.
++++++++   216	
.oracle/checkins/batch-2-r3.md:3163: trailing whitespace.
++++++++   225	
.oracle/checkins/batch-2-r3.md:3165: trailing whitespace.
++++++++   226	
.oracle/checkins/batch-2-r3.md:3167: trailing whitespace.
++++++++   231	
.oracle/checkins/batch-2-r3.md:3169: trailing whitespace.
++++++++   232	
.oracle/checkins/batch-2-r3.md:3171: trailing whitespace.
++++++++   241	
.oracle/checkins/batch-2-r3.md:3173: trailing whitespace.
++++++++   242	
.oracle/checkins/batch-2-r3.md:3175: trailing whitespace.
++++++++   248	
.oracle/checkins/batch-2-r3.md:3177: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r3.md:3179: trailing whitespace.
++++++++   262	
.oracle/checkins/batch-2-r3.md:3181: trailing whitespace.
++++++++   263	
.oracle/checkins/batch-2-r3.md:3183: trailing whitespace.
++++++++   268	
.oracle/checkins/batch-2-r3.md:3185: trailing whitespace.
++++++++   269	
.oracle/checkins/batch-2-r3.md:3187: trailing whitespace.
++++++++   276	
.oracle/checkins/batch-2-r3.md:3189: trailing whitespace.
++++++++   277	
.oracle/checkins/batch-2-r3.md:3191: trailing whitespace.
++++++++   284	
.oracle/checkins/batch-2-r3.md:3193: trailing whitespace.
++++++++   285	
.oracle/checkins/batch-2-r3.md:3195: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r3.md:3197: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r3.md:3199: trailing whitespace.
++++++++    11	
.oracle/checkins/batch-2-r3.md:3201: trailing whitespace.
++++++++    20	
.oracle/checkins/batch-2-r3.md:3203: trailing whitespace.
++++++++    21	
.oracle/checkins/batch-2-r3.md:3205: trailing whitespace.
++++++++    48	
.oracle/checkins/batch-2-r3.md:3207: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r3.md:3209: trailing whitespace.
++++++++    52	
.oracle/checkins/batch-2-r3.md:3211: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r3.md:3213: trailing whitespace.
++++++++    56	
.oracle/checkins/batch-2-r3.md:3215: trailing whitespace.
++++++++    57	
.oracle/checkins/batch-2-r3.md:3217: trailing whitespace.
++++++++    60	
.oracle/checkins/batch-2-r3.md:3219: trailing whitespace.
++++++++    61	
.oracle/checkins/batch-2-r3.md:3221: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r3.md:3223: trailing whitespace.
++++++++    73	
.oracle/checkins/batch-2-r3.md:3225: trailing whitespace.
++++++++    81	
.oracle/checkins/batch-2-r3.md:3227: trailing whitespace.
++++++++    88	
.oracle/checkins/batch-2-r3.md:3229: trailing whitespace.
++++++++    89	
.oracle/checkins/batch-2-r3.md:3231: trailing whitespace.
++++++++    96	
.oracle/checkins/batch-2-r3.md:3233: trailing whitespace.
++++++++    97	
.oracle/checkins/batch-2-r3.md:3235: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r3.md:3237: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r3.md:3239: trailing whitespace.
++++++++   113	
.oracle/checkins/batch-2-r3.md:3241: trailing whitespace.
++++++++   114	
.oracle/checkins/batch-2-r3.md:3243: trailing whitespace.
++++++++   122	
.oracle/checkins/batch-2-r3.md:3245: trailing whitespace.
++++++++   123	
.oracle/checkins/batch-2-r3.md:3247: trailing whitespace.
++++++++   131	
.oracle/checkins/batch-2-r3.md:3249: trailing whitespace.
++++++++   132	
.oracle/checkins/batch-2-r3.md:3251: trailing whitespace.
++++++++   162	
.oracle/checkins/batch-2-r3.md:3253: trailing whitespace.
++++++++   163	
.oracle/checkins/batch-2-r3.md:3255: trailing whitespace.
++++++++   178	
.oracle/checkins/batch-2-r3.md:3257: trailing whitespace.
++++++++   179	
.oracle/checkins/batch-2-r3.md:3259: trailing whitespace.
++++++++   206	
.oracle/checkins/batch-2-r3.md:3261: trailing whitespace.
++++++++   207	
.oracle/checkins/batch-2-r3.md:3263: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r3.md:3265: trailing whitespace.
++++++++   250	
.oracle/checkins/batch-2-r3.md:3267: trailing whitespace.
++++++++   288	
.oracle/checkins/batch-2-r3.md:3269: trailing whitespace.
++++++++   289	
.oracle/checkins/batch-2-r3.md:3271: trailing whitespace.
++++++++   312	
.oracle/checkins/batch-2-r3.md:3273: trailing whitespace.
++++++++   313	
.oracle/checkins/batch-2-r3.md:3275: trailing whitespace.
++++++++   324	
.oracle/checkins/batch-2-r3.md:3277: trailing whitespace.
++++++++   325	
.oracle/checkins/batch-2-r3.md:3279: trailing whitespace.
++++++++   338	
.oracle/checkins/batch-2-r3.md:3281: trailing whitespace.
++++++++   339	
.oracle/checkins/batch-2-r3.md:3283: trailing whitespace.
++++++++   356	
.oracle/checkins/batch-2-r3.md:3285: trailing whitespace.
++++++++   357	
.oracle/checkins/batch-2-r3.md:3287: trailing whitespace.
++++++++   375	
.oracle/checkins/batch-2-r3.md:3289: trailing whitespace.
++++++++   376	
.oracle/checkins/batch-2-r3.md:3291: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:3293: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r3.md:3295: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3297: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3299: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3301: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3303: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3305: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3307: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3309: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3311: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3313: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3315: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3317: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3319: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3321: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3323: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3325: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3327: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3329: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3331: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3333: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3335: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3337: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3339: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3341: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3343: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3345: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3347: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3349: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3351: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3353: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3355: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3357: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3359: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3361: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3363: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3365: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3367: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3369: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3371: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3373: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3375: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3377: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3379: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3381: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3383: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3385: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3387: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3389: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3391: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3393: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3395: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3397: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3399: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3401: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3403: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3405: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3407: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3409: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3411: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3413: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3415: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3417: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3419: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3421: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3423: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3425: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3427: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3429: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3431: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3433: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3435: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3437: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3439: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3441: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3443: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3445: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3447: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3449: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3451: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3453: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3455: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3457: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3459: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3461: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3463: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3465: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3467: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3469: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3471: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3473: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3475: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3477: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3479: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3481: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3483: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3485: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3487: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3489: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3491: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3493: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3495: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3497: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3499: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3501: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3503: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3505: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3507: trailing whitespace.
+++++++   190	
.oracle/checkins/batch-2-r3.md:3509: trailing whitespace.
+++++++   191	
.oracle/checkins/batch-2-r3.md:3511: trailing whitespace.
+++++++   215	
.oracle/checkins/batch-2-r3.md:3513: trailing whitespace.
+++++++   216	
.oracle/checkins/batch-2-r3.md:3515: trailing whitespace.
+++++++   225	
.oracle/checkins/batch-2-r3.md:3517: trailing whitespace.
+++++++   226	
.oracle/checkins/batch-2-r3.md:3519: trailing whitespace.
+++++++   231	
.oracle/checkins/batch-2-r3.md:3521: trailing whitespace.
+++++++   232	
.oracle/checkins/batch-2-r3.md:3523: trailing whitespace.
+++++++   241	
.oracle/checkins/batch-2-r3.md:3525: trailing whitespace.
+++++++   242	
.oracle/checkins/batch-2-r3.md:3527: trailing whitespace.
+++++++   248	
.oracle/checkins/batch-2-r3.md:3529: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2-r3.md:3531: trailing whitespace.
+++++++   262	
.oracle/checkins/batch-2-r3.md:3533: trailing whitespace.
+++++++   263	
.oracle/checkins/batch-2-r3.md:3535: trailing whitespace.
+++++++   268	
.oracle/checkins/batch-2-r3.md:3537: trailing whitespace.
+++++++   269	
.oracle/checkins/batch-2-r3.md:3539: trailing whitespace.
+++++++   276	
.oracle/checkins/batch-2-r3.md:3541: trailing whitespace.
+++++++   277	
.oracle/checkins/batch-2-r3.md:3543: trailing whitespace.
+++++++   284	
.oracle/checkins/batch-2-r3.md:3545: trailing whitespace.
+++++++   285	
.oracle/checkins/batch-2-r3.md:3547: trailing whitespace.
+++++++   294	
.oracle/checkins/batch-2-r3.md:3549: trailing whitespace.
+++++++   295	
.oracle/checkins/batch-2-r3.md:3551: trailing whitespace.
+++++++   302	
.oracle/checkins/batch-2-r3.md:3553: trailing whitespace.
+++++++   303	
.oracle/checkins/batch-2-r3.md:3555: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2-r3.md:3557: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2-r3.md:3559: trailing whitespace.
+++++++   333	
.oracle/checkins/batch-2-r3.md:3561: trailing whitespace.
+++++++   334	
.oracle/checkins/batch-2-r3.md:3563: trailing whitespace.
+++++++   375	
.oracle/checkins/batch-2-r3.md:3565: trailing whitespace.
+++++++   376	
.oracle/checkins/batch-2-r3.md:3567: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3569: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3571: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:3573: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:3575: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:3577: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r3.md:3579: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3581: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3583: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3585: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3587: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3589: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3591: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3593: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3595: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3597: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3599: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3601: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3603: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3605: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3607: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3609: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3611: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3613: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3615: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3617: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3619: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3621: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3623: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3625: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3627: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3629: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3631: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3633: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3635: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3637: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3639: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3641: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3643: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3645: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3647: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3649: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3651: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3653: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3655: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3657: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3659: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3661: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3663: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3665: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3667: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3669: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3671: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3673: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3675: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3677: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3679: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3681: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3683: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3685: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3687: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3689: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3691: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3693: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3695: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3697: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3699: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3701: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3703: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3705: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3707: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3709: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3711: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3713: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3715: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3717: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3719: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3721: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3723: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3725: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3727: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3729: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3731: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3733: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3735: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3737: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3739: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3741: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3743: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3745: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3747: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3749: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3751: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3753: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3755: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3757: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3759: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3761: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3763: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3765: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3767: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3769: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3771: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3773: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3775: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3777: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3779: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3781: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3783: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3785: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3787: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3789: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3791: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3793: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3795: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3797: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3799: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3801: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3803: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3805: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3807: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3809: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3811: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3813: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3815: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3817: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3819: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3821: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3823: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3825: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3827: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3829: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3831: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3833: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3835: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3837: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3839: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3841: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3843: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3845: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3847: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3849: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3851: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3853: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3855: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3857: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3859: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3861: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3863: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3865: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3867: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3869: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3871: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3873: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3875: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3877: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3879: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3881: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3883: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3885: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:3887: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:3889: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:3891: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r3.md:3893: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r3.md:3895: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r3.md:3897: trailing whitespace.
+++++    56	
.oracle/checkins/batch-2-r3.md:3899: trailing whitespace.
+++++    59	
.oracle/checkins/batch-2-r3.md:3901: trailing whitespace.
+++++    72	
.oracle/checkins/batch-2-r3.md:3903: trailing whitespace.
+++++    75	
.oracle/checkins/batch-2-r3.md:3905: trailing whitespace.
+++++    95	
.oracle/checkins/batch-2-r3.md:3907: trailing whitespace.
+++++    99	
.oracle/checkins/batch-2-r3.md:3909: trailing whitespace.
+++++     8	
.oracle/checkins/batch-2-r3.md:3911: trailing whitespace.
+++++    10	
.oracle/checkins/batch-2-r3.md:3913: trailing whitespace.
+++++    12	
.oracle/checkins/batch-2-r3.md:3915: trailing whitespace.
+++++    17	
.oracle/checkins/batch-2-r3.md:3917: trailing whitespace.
+++++    21	
.oracle/checkins/batch-2-r3.md:3919: trailing whitespace.
+++++    25	
.oracle/checkins/batch-2-r3.md:3921: trailing whitespace.
+++++    29	
.oracle/checkins/batch-2-r3.md:3923: trailing whitespace.
+++++    33	
.oracle/checkins/batch-2-r3.md:3925: trailing whitespace.
+++++    37	
.oracle/checkins/batch-2-r3.md:3927: trailing whitespace.
+++++    41	
.oracle/checkins/batch-2-r3.md:3929: trailing whitespace.
+++++    45	
.oracle/checkins/batch-2-r3.md:3931: trailing whitespace.
+++++    48	
.oracle/checkins/batch-2-r3.md:3933: trailing whitespace.
+++++    51	
.oracle/checkins/batch-2-r3.md:3935: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:3937: trailing whitespace.
++++     7	
.oracle/checkins/batch-2-r3.md:3939: trailing whitespace.
++++     9	
.oracle/checkins/batch-2-r3.md:3941: trailing whitespace.
++++    19	
.oracle/checkins/batch-2-r3.md:3943: trailing whitespace.
++++    20	
.oracle/checkins/batch-2-r3.md:3945: trailing whitespace.
++++    23	
.oracle/checkins/batch-2-r3.md:3947: trailing whitespace.
++++    24	
.oracle/checkins/batch-2-r3.md:3949: trailing whitespace.
++++    39	
.oracle/checkins/batch-2-r3.md:3951: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:3953: trailing whitespace.
++++    47	
.oracle/checkins/batch-2-r3.md:3955: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r3.md:3957: trailing whitespace.
++++    64	
.oracle/checkins/batch-2-r3.md:3959: trailing whitespace.
++++    65	
.oracle/checkins/batch-2-r3.md:3961: trailing whitespace.
++++    75	
.oracle/checkins/batch-2-r3.md:3963: trailing whitespace.
++++    81	
.oracle/checkins/batch-2-r3.md:3965: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:3967: trailing whitespace.
++++    92	
.oracle/checkins/batch-2-r3.md:3969: trailing whitespace.
++++    96	
.oracle/checkins/batch-2-r3.md:3971: trailing whitespace.
++++   108	
.oracle/checkins/batch-2-r3.md:3973: trailing whitespace.
++++   114	
.oracle/checkins/batch-2-r3.md:3975: trailing whitespace.
++++   119	
.oracle/checkins/batch-2-r3.md:3977: trailing whitespace.
++++   129	
.oracle/checkins/batch-2-r3.md:3979: trailing whitespace.
++++   130	
.oracle/checkins/batch-2-r3.md:3981: trailing whitespace.
++++   135	
.oracle/checkins/batch-2-r3.md:3983: trailing whitespace.
++++   138	
.oracle/checkins/batch-2-r3.md:3985: trailing whitespace.
++++   149	
.oracle/checkins/batch-2-r3.md:3987: trailing whitespace.
++++   161	
.oracle/checkins/batch-2-r3.md:3989: trailing whitespace.
++++   162	
.oracle/checkins/batch-2-r3.md:3991: trailing whitespace.
++++   187	
.oracle/checkins/batch-2-r3.md:3993: trailing whitespace.
++++   205	
.oracle/checkins/batch-2-r3.md:3995: trailing whitespace.
++++   217	
.oracle/checkins/batch-2-r3.md:3997: trailing whitespace.
++++   218	
.oracle/checkins/batch-2-r3.md:3999: trailing whitespace.
++++   238	
.oracle/checkins/batch-2-r3.md:4001: trailing whitespace.
++++   247	
.oracle/checkins/batch-2-r3.md:4003: trailing whitespace.
++++   253	
.oracle/checkins/batch-2-r3.md:4005: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:4007: trailing whitespace.
++++   262	
.oracle/checkins/batch-2-r3.md:4009: trailing whitespace.
++++   265	
.oracle/checkins/batch-2-r3.md:4011: trailing whitespace.
++++   275	
.oracle/checkins/batch-2-r3.md:4013: trailing whitespace.
++++   244	
.oracle/checkins/batch-2-r3.md:4015: trailing whitespace.
++++   245	
.oracle/checkins/batch-2-r3.md:4017: trailing whitespace.
++++   255	
.oracle/checkins/batch-2-r3.md:4019: trailing whitespace.
++++   262	
.oracle/checkins/batch-2-r3.md:4021: trailing whitespace.
++++   265	
.oracle/checkins/batch-2-r3.md:4023: trailing whitespace.
++++   270	
.oracle/checkins/batch-2-r3.md:4025: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r3.md:4027: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r3.md:4029: trailing whitespace.
++++   296	
.oracle/checkins/batch-2-r3.md:4031: trailing whitespace.
++++   306	
.oracle/checkins/batch-2-r3.md:4033: trailing whitespace.
++++   307	
.oracle/checkins/batch-2-r3.md:4035: trailing whitespace.
++++    14	
.oracle/checkins/batch-2-r3.md:4037: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r3.md:4039: trailing whitespace.
++++    35	
.oracle/checkins/batch-2-r3.md:4041: trailing whitespace.
++++    47	
.oracle/checkins/batch-2-r3.md:4043: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4045: trailing whitespace.
++++     5	
.oracle/checkins/batch-2-r3.md:4047: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:4049: trailing whitespace.
++++     9	
.oracle/checkins/batch-2-r3.md:4051: trailing whitespace.
++++    22	
.oracle/checkins/batch-2-r3.md:4053: trailing whitespace.
++++    23	
.oracle/checkins/batch-2-r3.md:4055: trailing whitespace.
++++    28	
.oracle/checkins/batch-2-r3.md:4057: trailing whitespace.
++++    29	
.oracle/checkins/batch-2-r3.md:4059: trailing whitespace.
++++    32	
.oracle/checkins/batch-2-r3.md:4061: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r3.md:4063: trailing whitespace.
++++    43	
.oracle/checkins/batch-2-r3.md:4065: trailing whitespace.
++++    44	
.oracle/checkins/batch-2-r3.md:4067: trailing whitespace.
++++    50	
.oracle/checkins/batch-2-r3.md:4069: trailing whitespace.
++++    52	
.oracle/checkins/batch-2-r3.md:4071: trailing whitespace.
++++    58	
.oracle/checkins/batch-2-r3.md:4073: trailing whitespace.
++++    59	
.oracle/checkins/batch-2-r3.md:4075: trailing whitespace.
++++    70	
.oracle/checkins/batch-2-r3.md:4077: trailing whitespace.
++++    73	
.oracle/checkins/batch-2-r3.md:4079: trailing whitespace.
++++    74	
.oracle/checkins/batch-2-r3.md:4081: trailing whitespace.
++++    83	
.oracle/checkins/batch-2-r3.md:4083: trailing whitespace.
++++    85	
.oracle/checkins/batch-2-r3.md:4085: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:4087: trailing whitespace.
++++   108	
.oracle/checkins/batch-2-r3.md:4089: trailing whitespace.
++++   110	
.oracle/checkins/batch-2-r3.md:4091: trailing whitespace.
++++   114	
.oracle/checkins/batch-2-r3.md:4093: trailing whitespace.
++++   115	
.oracle/checkins/batch-2-r3.md:4095: trailing whitespace.
++++   121	
.oracle/checkins/batch-2-r3.md:4097: trailing whitespace.
++++   123	
.oracle/checkins/batch-2-r3.md:4099: trailing whitespace.
++++   124	
.oracle/checkins/batch-2-r3.md:4101: trailing whitespace.
++++   137	
.oracle/checkins/batch-2-r3.md:4103: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r3.md:4105: trailing whitespace.
++++   146	
.oracle/checkins/batch-2-r3.md:4107: trailing whitespace.
++++   147	
.oracle/checkins/batch-2-r3.md:4109: trailing whitespace.
++++   157	
.oracle/checkins/batch-2-r3.md:4111: trailing whitespace.
++++   297	
.oracle/checkins/batch-2-r3.md:4113: trailing whitespace.
++++   298	
.oracle/checkins/batch-2-r3.md:4115: trailing whitespace.
++++   301	
.oracle/checkins/batch-2-r3.md:4117: trailing whitespace.
++++   319	
.oracle/checkins/batch-2-r3.md:4119: trailing whitespace.
++++   322	
.oracle/checkins/batch-2-r3.md:4121: trailing whitespace.
++++   325	
.oracle/checkins/batch-2-r3.md:4123: trailing whitespace.
++++   330	
.oracle/checkins/batch-2-r3.md:4125: trailing whitespace.
++++   334	
.oracle/checkins/batch-2-r3.md:4127: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4129: trailing whitespace.
++++     9	
.oracle/checkins/batch-2-r3.md:4131: trailing whitespace.
++++    11	
.oracle/checkins/batch-2-r3.md:4133: trailing whitespace.
++++    15	
.oracle/checkins/batch-2-r3.md:4135: trailing whitespace.
++++    18	
.oracle/checkins/batch-2-r3.md:4137: trailing whitespace.
++++    26	
.oracle/checkins/batch-2-r3.md:4139: trailing whitespace.
++++    28	
.oracle/checkins/batch-2-r3.md:4141: trailing whitespace.
++++    29	
.oracle/checkins/batch-2-r3.md:4143: trailing whitespace.
++++    36	
.oracle/checkins/batch-2-r3.md:4145: trailing whitespace.
++++    37	
.oracle/checkins/batch-2-r3.md:4147: trailing whitespace.
++++    39	
.oracle/checkins/batch-2-r3.md:4149: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:4151: trailing whitespace.
++++    45	
.oracle/checkins/batch-2-r3.md:4153: trailing whitespace.
++++    46	
.oracle/checkins/batch-2-r3.md:4155: trailing whitespace.
++++    58	
.oracle/checkins/batch-2-r3.md:4157: trailing whitespace.
++++    59	
.oracle/checkins/batch-2-r3.md:4159: trailing whitespace.
++++    67	
.oracle/checkins/batch-2-r3.md:4161: trailing whitespace.
++++    68	
.oracle/checkins/batch-2-r3.md:4163: trailing whitespace.
++++    87	
.oracle/checkins/batch-2-r3.md:4165: trailing whitespace.
++++    88	
.oracle/checkins/batch-2-r3.md:4167: trailing whitespace.
++++   352	
.oracle/checkins/batch-2-r3.md:4169: trailing whitespace.
++++   353	
.oracle/checkins/batch-2-r3.md:4171: trailing whitespace.
++++   356	
.oracle/checkins/batch-2-r3.md:4173: trailing whitespace.
++++   362	
.oracle/checkins/batch-2-r3.md:4175: trailing whitespace.
++++   363	
.oracle/checkins/batch-2-r3.md:4177: trailing whitespace.
++++   366	
.oracle/checkins/batch-2-r3.md:4179: trailing whitespace.
++++   370	
.oracle/checkins/batch-2-r3.md:4181: trailing whitespace.
++++   371	
.oracle/checkins/batch-2-r3.md:4183: trailing whitespace.
++++   385	
.oracle/checkins/batch-2-r3.md:4185: trailing whitespace.
++++   386	
.oracle/checkins/batch-2-r3.md:4187: trailing whitespace.
++++   390	
.oracle/checkins/batch-2-r3.md:4189: trailing whitespace.
++++   396	
.oracle/checkins/batch-2-r3.md:4191: trailing whitespace.
++++   417	
.oracle/checkins/batch-2-r3.md:4193: trailing whitespace.
++++   421	
.oracle/checkins/batch-2-r3.md:4195: trailing whitespace.
++++   432	
.oracle/checkins/batch-2-r3.md:4197: trailing whitespace.
++++   449	
.oracle/checkins/batch-2-r3.md:4199: trailing whitespace.
++++   450	
.oracle/checkins/batch-2-r3.md:4201: trailing whitespace.
++++   454	
.oracle/checkins/batch-2-r3.md:4203: trailing whitespace.
++++   468	
.oracle/checkins/batch-2-r3.md:4205: trailing whitespace.
++++   664	
.oracle/checkins/batch-2-r3.md:4207: trailing whitespace.
++++   665	
.oracle/checkins/batch-2-r3.md:4209: trailing whitespace.
++++   669	
.oracle/checkins/batch-2-r3.md:4211: trailing whitespace.
++++   676	
.oracle/checkins/batch-2-r3.md:4213: trailing whitespace.
++++   699	
.oracle/checkins/batch-2-r3.md:4215: trailing whitespace.
++++   711	
.oracle/checkins/batch-2-r3.md:4217: trailing whitespace.
++++   726	
.oracle/checkins/batch-2-r3.md:4219: trailing whitespace.
++++   747	
.oracle/checkins/batch-2-r3.md:4221: trailing whitespace.
++++   748	
.oracle/checkins/batch-2-r3.md:4223: trailing whitespace.
++++   755	
.oracle/checkins/batch-2-r3.md:4225: trailing whitespace.
++++   756	
.oracle/checkins/batch-2-r3.md:4227: trailing whitespace.
++++   763	
.oracle/checkins/batch-2-r3.md:4229: trailing whitespace.
++++   764	
.oracle/checkins/batch-2-r3.md:4231: trailing whitespace.
++++   772	
.oracle/checkins/batch-2-r3.md:4233: trailing whitespace.
++++   773	
.oracle/checkins/batch-2-r3.md:4235: trailing whitespace.
++++   777	
.oracle/checkins/batch-2-r3.md:4237: trailing whitespace.
++++   787	
.oracle/checkins/batch-2-r3.md:4239: trailing whitespace.
++++   820	
.oracle/checkins/batch-2-r3.md:4241: trailing whitespace.
++++   835	
.oracle/checkins/batch-2-r3.md:4243: trailing whitespace.
++++  1511	
.oracle/checkins/batch-2-r3.md:4245: trailing whitespace.
++++  1512	
.oracle/checkins/batch-2-r3.md:4247: trailing whitespace.
++++  1527	
.oracle/checkins/batch-2-r3.md:4249: trailing whitespace.
++++  1528	
.oracle/checkins/batch-2-r3.md:4251: trailing whitespace.
++++  1532	
.oracle/checkins/batch-2-r3.md:4253: trailing whitespace.
++++  1540	
.oracle/checkins/batch-2-r3.md:4255: trailing whitespace.
++++  1566	
.oracle/checkins/batch-2-r3.md:4257: trailing whitespace.
++++  1570	
.oracle/checkins/batch-2-r3.md:4259: trailing whitespace.
++++  1572	
.oracle/checkins/batch-2-r3.md:4261: trailing whitespace.
++++  1585	
.oracle/checkins/batch-2-r3.md:4263: trailing whitespace.
++++  1609	
.oracle/checkins/batch-2-r3.md:4265: trailing whitespace.
++++  1616	
.oracle/checkins/batch-2-r3.md:4267: trailing whitespace.
++++  1617	
.oracle/checkins/batch-2-r3.md:4269: trailing whitespace.
++++  1621	
.oracle/checkins/batch-2-r3.md:4271: trailing whitespace.
++++   516	
.oracle/checkins/batch-2-r3.md:4273: trailing whitespace.
++++   520	
.oracle/checkins/batch-2-r3.md:4275: trailing whitespace.
++++   539	
.oracle/checkins/batch-2-r3.md:4277: trailing whitespace.
++++   572	
.oracle/checkins/batch-2-r3.md:4279: trailing whitespace.
++++   573	
.oracle/checkins/batch-2-r3.md:4281: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4283: trailing whitespace.
++++     4	
.oracle/checkins/batch-2-r3.md:4285: trailing whitespace.
++++    12	
.oracle/checkins/batch-2-r3.md:4287: trailing whitespace.
++++    15	
.oracle/checkins/batch-2-r3.md:4289: trailing whitespace.
++++    24	
.oracle/checkins/batch-2-r3.md:4291: trailing whitespace.
++++    25	
.oracle/checkins/batch-2-r3.md:4293: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:4295: trailing whitespace.
++++    41	
.oracle/checkins/batch-2-r3.md:4297: trailing whitespace.
++++    49	
.oracle/checkins/batch-2-r3.md:4299: trailing whitespace.
++++    50	
.oracle/checkins/batch-2-r3.md:4301: trailing whitespace.
++++    61	
.oracle/checkins/batch-2-r3.md:4303: trailing whitespace.
++++    62	
.oracle/checkins/batch-2-r3.md:4305: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r3.md:4307: trailing whitespace.
++++    91	
.oracle/checkins/batch-2-r3.md:4309: trailing whitespace.
++++    92	
.oracle/checkins/batch-2-r3.md:4311: trailing whitespace.
++++   109	
.oracle/checkins/batch-2-r3.md:4313: trailing whitespace.
++++   110	
.oracle/checkins/batch-2-r3.md:4315: trailing whitespace.
++++   128	
.oracle/checkins/batch-2-r3.md:4317: trailing whitespace.
++++   129	
.oracle/checkins/batch-2-r3.md:4319: trailing whitespace.
++++   152	
.oracle/checkins/batch-2-r3.md:4321: trailing whitespace.
++++   153	
.oracle/checkins/batch-2-r3.md:4323: trailing whitespace.
++++   192	
.oracle/checkins/batch-2-r3.md:4325: trailing whitespace.
++++   193	
.oracle/checkins/batch-2-r3.md:4327: trailing whitespace.
++++   202	
.oracle/checkins/batch-2-r3.md:4329: trailing whitespace.
++++   203	
.oracle/checkins/batch-2-r3.md:4331: trailing whitespace.
++++   223	
.oracle/checkins/batch-2-r3.md:4333: trailing whitespace.
++++   224	
.oracle/checkins/batch-2-r3.md:4335: trailing whitespace.
++++   240	
.oracle/checkins/batch-2-r3.md:4337: trailing whitespace.
++++   241	
.oracle/checkins/batch-2-r3.md:4339: trailing whitespace.
++++   244	
.oracle/checkins/batch-2-r3.md:4341: trailing whitespace.
++++   245	
.oracle/checkins/batch-2-r3.md:4343: trailing whitespace.
++++   253	
.oracle/checkins/batch-2-r3.md:4345: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:4347: trailing whitespace.
++++   266	
.oracle/checkins/batch-2-r3.md:4349: trailing whitespace.
++++   267	
.oracle/checkins/batch-2-r3.md:4351: trailing whitespace.
++++   270	
.oracle/checkins/batch-2-r3.md:4353: trailing whitespace.
++++   271	
.oracle/checkins/batch-2-r3.md:4355: trailing whitespace.
++++   290	
.oracle/checkins/batch-2-r3.md:4357: trailing whitespace.
++++   291	
.oracle/checkins/batch-2-r3.md:4359: trailing whitespace.
++++   329	
.oracle/checkins/batch-2-r3.md:4361: trailing whitespace.
++++   356	
.oracle/checkins/batch-2-r3.md:4363: trailing whitespace.
++++   357	
.oracle/checkins/batch-2-r3.md:4365: trailing whitespace.
++++   388	
.oracle/checkins/batch-2-r3.md:4367: trailing whitespace.
++++   389	
.oracle/checkins/batch-2-r3.md:4369: trailing whitespace.
++++   436	
.oracle/checkins/batch-2-r3.md:4371: trailing whitespace.
++++   452	
.oracle/checkins/batch-2-r3.md:4373: trailing whitespace.
++++   453	
.oracle/checkins/batch-2-r3.md:4375: trailing whitespace.
++++   474	
.oracle/checkins/batch-2-r3.md:4377: trailing whitespace.
++++   499	
.oracle/checkins/batch-2-r3.md:4379: trailing whitespace.
++++   500	
.oracle/checkins/batch-2-r3.md:4381: trailing whitespace.
++++   527	
.oracle/checkins/batch-2-r3.md:4383: trailing whitespace.
++++   528	
.oracle/checkins/batch-2-r3.md:4385: trailing whitespace.
++++   553	
.oracle/checkins/batch-2-r3.md:4387: trailing whitespace.
++++   554	
.oracle/checkins/batch-2-r3.md:4389: trailing whitespace.
++++   594	
.oracle/checkins/batch-2-r3.md:4391: trailing whitespace.
++++   595	
.oracle/checkins/batch-2-r3.md:4393: trailing whitespace.
++++   622	
.oracle/checkins/batch-2-r3.md:4395: trailing whitespace.
++++   623	
.oracle/checkins/batch-2-r3.md:4397: trailing whitespace.
++++   631	
.oracle/checkins/batch-2-r3.md:4399: trailing whitespace.
++++   637	
.oracle/checkins/batch-2-r3.md:4401: trailing whitespace.
++++   644	
.oracle/checkins/batch-2-r3.md:4403: trailing whitespace.
++++   663	
.oracle/checkins/batch-2-r3.md:4405: trailing whitespace.
++++   673	
.oracle/checkins/batch-2-r3.md:4407: trailing whitespace.
++++   694	
.oracle/checkins/batch-2-r3.md:4409: trailing whitespace.
++++   695	
.oracle/checkins/batch-2-r3.md:4411: trailing whitespace.
++++   132	
.oracle/checkins/batch-2-r3.md:4413: trailing whitespace.
++++   139	
.oracle/checkins/batch-2-r3.md:4415: trailing whitespace.
++++   140	
.oracle/checkins/batch-2-r3.md:4417: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r3.md:4419: trailing whitespace.
++++   150	
.oracle/checkins/batch-2-r3.md:4421: trailing whitespace.
++++   151	
.oracle/checkins/batch-2-r3.md:4423: trailing whitespace.
++++   158	
.oracle/checkins/batch-2-r3.md:4425: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:4427: trailing whitespace.
++++   166	
.oracle/checkins/batch-2-r3.md:4429: trailing whitespace.
++++   176	
.oracle/checkins/batch-2-r3.md:4431: trailing whitespace.
++++   183	
.oracle/checkins/batch-2-r3.md:4433: trailing whitespace.
++++   184	
.oracle/checkins/batch-2-r3.md:4435: trailing whitespace.
++++   188	
.oracle/checkins/batch-2-r3.md:4437: trailing whitespace.
++++   195	
.oracle/checkins/batch-2-r3.md:4439: trailing whitespace.
++++   196	
.oracle/checkins/batch-2-r3.md:4441: trailing whitespace.
++++   221	
.oracle/checkins/batch-2-r3.md:4443: trailing whitespace.
++++   228	
.oracle/checkins/batch-2-r3.md:4445: trailing whitespace.
++++   229	
.oracle/checkins/batch-2-r3.md:4447: trailing whitespace.
++++   233	
.oracle/checkins/batch-2-r3.md:4449: trailing whitespace.
++++   240	
.oracle/checkins/batch-2-r3.md:4451: trailing whitespace.
++++   241	
.oracle/checkins/batch-2-r3.md:4453: trailing whitespace.
++++   251	
.oracle/checkins/batch-2-r3.md:4455: trailing whitespace.
++++   258	
.oracle/checkins/batch-2-r3.md:4457: trailing whitespace.
++++   259	
.oracle/checkins/batch-2-r3.md:4459: trailing whitespace.
++++   269	
.oracle/checkins/batch-2-r3.md:4461: trailing whitespace.
++++   276	
.oracle/checkins/batch-2-r3.md:4463: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r3.md:4465: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4467: trailing whitespace.
++++     6	
.oracle/checkins/batch-2-r3.md:4469: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:4471: trailing whitespace.
++++    17	
.oracle/checkins/batch-2-r3.md:4473: trailing whitespace.
++++    19	
.oracle/checkins/batch-2-r3.md:4475: trailing whitespace.
++++    21	
.oracle/checkins/batch-2-r3.md:4477: trailing whitespace.
++++    22	
.oracle/checkins/batch-2-r3.md:4479: trailing whitespace.
++++    26	
.oracle/checkins/batch-2-r3.md:4481: trailing whitespace.
++++    27	
.oracle/checkins/batch-2-r3.md:4483: trailing whitespace.
++++    31	
.oracle/checkins/batch-2-r3.md:4485: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r3.md:4487: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:4489: trailing whitespace.
++++    42	
.oracle/checkins/batch-2-r3.md:4491: trailing whitespace.
++++    59	
.oracle/checkins/batch-2-r3.md:4493: trailing whitespace.
++++    63	
.oracle/checkins/batch-2-r3.md:4495: trailing whitespace.
++++    65	
.oracle/checkins/batch-2-r3.md:4497: trailing whitespace.
++++    69	
.oracle/checkins/batch-2-r3.md:4499: trailing whitespace.
++++    71	
.oracle/checkins/batch-2-r3.md:4501: trailing whitespace.
++++    79	
.oracle/checkins/batch-2-r3.md:4503: trailing whitespace.
++++    85	
.oracle/checkins/batch-2-r3.md:4505: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:4507: trailing whitespace.
++++    89	
.oracle/checkins/batch-2-r3.md:4509: trailing whitespace.
++++    90	
.oracle/checkins/batch-2-r3.md:4511: trailing whitespace.
++++    93	
.oracle/checkins/batch-2-r3.md:4513: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:4515: trailing whitespace.
++++   107	
.oracle/checkins/batch-2-r3.md:4517: trailing whitespace.
++++   118	
.oracle/checkins/batch-2-r3.md:4519: trailing whitespace.
++++   119	
.oracle/checkins/batch-2-r3.md:4521: trailing whitespace.
++++   124	
.oracle/checkins/batch-2-r3.md:4523: trailing whitespace.
++++   125	
.oracle/checkins/batch-2-r3.md:4525: trailing whitespace.
++++   132	
.oracle/checkins/batch-2-r3.md:4527: trailing whitespace.
++++   133	
.oracle/checkins/batch-2-r3.md:4529: trailing whitespace.
++++   150	
.oracle/checkins/batch-2-r3.md:4531: trailing whitespace.
++++   151	
.oracle/checkins/batch-2-r3.md:4533: trailing whitespace.
++++   154	
.oracle/checkins/batch-2-r3.md:4535: trailing whitespace.
++++   160	
.oracle/checkins/batch-2-r3.md:4537: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:4539: trailing whitespace.
++++   169	
.oracle/checkins/batch-2-r3.md:4541: trailing whitespace.
++++   186	
.oracle/checkins/batch-2-r3.md:4543: trailing whitespace.
++++   189	
.oracle/checkins/batch-2-r3.md:4545: trailing whitespace.
++++   195	
.oracle/checkins/batch-2-r3.md:4547: trailing whitespace.
++++   203	
.oracle/checkins/batch-2-r3.md:4549: trailing whitespace.
++++   211	
.oracle/checkins/batch-2-r3.md:4551: trailing whitespace.
++++   217	
.oracle/checkins/batch-2-r3.md:4553: trailing whitespace.
++++   226	
.oracle/checkins/batch-2-r3.md:4555: trailing whitespace.
++++   228	
.oracle/checkins/batch-2-r3.md:4557: trailing whitespace.
++++   229	
.oracle/checkins/batch-2-r3.md:4559: trailing whitespace.
++++   241	
.oracle/checkins/batch-2-r3.md:4561: trailing whitespace.
++++   271	
.oracle/checkins/batch-2-r3.md:4563: trailing whitespace.
++++   280	
.oracle/checkins/batch-2-r3.md:4565: trailing whitespace.
++++   281	
.oracle/checkins/batch-2-r3.md:4567: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r3.md:4569: trailing whitespace.
++++   293	
.oracle/checkins/batch-2-r3.md:4571: trailing whitespace.
++++   294	
.oracle/checkins/batch-2-r3.md:4573: trailing whitespace.
++++   301	
.oracle/checkins/batch-2-r3.md:4575: trailing whitespace.
++++   307	
.oracle/checkins/batch-2-r3.md:4577: trailing whitespace.
++++   309	
.oracle/checkins/batch-2-r3.md:4579: trailing whitespace.
++++   310	
.oracle/checkins/batch-2-r3.md:4581: trailing whitespace.
++++   314	
.oracle/checkins/batch-2-r3.md:4583: trailing whitespace.
++++   315	
.oracle/checkins/batch-2-r3.md:4585: trailing whitespace.
++++   323	
.oracle/checkins/batch-2-r3.md:4587: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4589: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4591: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4593: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4595: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4597: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4599: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4601: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4603: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4605: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:4607: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4609: trailing whitespace.
++++     6	
.oracle/checkins/batch-2-r3.md:4611: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:4613: trailing whitespace.
++++    22	
.oracle/checkins/batch-2-r3.md:4615: trailing whitespace.
++++    24	
.oracle/checkins/batch-2-r3.md:4617: trailing whitespace.
++++    37	
.oracle/checkins/batch-2-r3.md:4619: trailing whitespace.
++++    38	
.oracle/checkins/batch-2-r3.md:4621: trailing whitespace.
++++    41	
.oracle/checkins/batch-2-r3.md:4623: trailing whitespace.
++++    69	
.oracle/checkins/batch-2-r3.md:4625: trailing whitespace.
++++    70	
.oracle/checkins/batch-2-r3.md:4627: trailing whitespace.
++++    73	
.oracle/checkins/batch-2-r3.md:4629: trailing whitespace.
++++    79	
.oracle/checkins/batch-2-r3.md:4631: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:4633: trailing whitespace.
++++   113	
.oracle/checkins/batch-2-r3.md:4635: trailing whitespace.
++++   120	
.oracle/checkins/batch-2-r3.md:4637: trailing whitespace.
++++   126	
.oracle/checkins/batch-2-r3.md:4639: trailing whitespace.
++++   144	
.oracle/checkins/batch-2-r3.md:4641: trailing whitespace.
++++   160	
.oracle/checkins/batch-2-r3.md:4643: trailing whitespace.
++++   171	
.oracle/checkins/batch-2-r3.md:4645: trailing whitespace.
++++   202	
.oracle/checkins/batch-2-r3.md:4647: trailing whitespace.
++++   237	
.oracle/checkins/batch-2-r3.md:4649: trailing whitespace.
++++   241	
.oracle/checkins/batch-2-r3.md:4651: trailing whitespace.
++++   248	
.oracle/checkins/batch-2-r3.md:4653: trailing whitespace.
++++   260	
.oracle/checkins/batch-2-r3.md:4655: trailing whitespace.
++++   260	
.oracle/checkins/batch-2-r3.md:4657: trailing whitespace.
++++   261	
.oracle/checkins/batch-2-r3.md:4659: trailing whitespace.
++++   268	
.oracle/checkins/batch-2-r3.md:4661: trailing whitespace.
++++   269	
.oracle/checkins/batch-2-r3.md:4663: trailing whitespace.
++++   285	
.oracle/checkins/batch-2-r3.md:4665: trailing whitespace.
++++   286	
.oracle/checkins/batch-2-r3.md:4667: trailing whitespace.
++++   317	
.oracle/checkins/batch-2-r3.md:4669: trailing whitespace.
++++   318	
.oracle/checkins/batch-2-r3.md:4671: trailing whitespace.
++++   335	
.oracle/checkins/batch-2-r3.md:4673: trailing whitespace.
++++   336	
.oracle/checkins/batch-2-r3.md:4675: trailing whitespace.
++++   339	
.oracle/checkins/batch-2-r3.md:4677: trailing whitespace.
++++   340	
.oracle/checkins/batch-2-r3.md:4679: trailing whitespace.
++++   346	
.oracle/checkins/batch-2-r3.md:4681: trailing whitespace.
++++   347	
.oracle/checkins/batch-2-r3.md:4683: trailing whitespace.
++++   383	
.oracle/checkins/batch-2-r3.md:4685: trailing whitespace.
++++   392	
.oracle/checkins/batch-2-r3.md:4687: trailing whitespace.
++++   393	
.oracle/checkins/batch-2-r3.md:4689: trailing whitespace.
++++   400	
.oracle/checkins/batch-2-r3.md:4691: trailing whitespace.
++++   401	
.oracle/checkins/batch-2-r3.md:4693: trailing whitespace.
++++   418	
.oracle/checkins/batch-2-r3.md:4695: trailing whitespace.
++++   419	
.oracle/checkins/batch-2-r3.md:4697: trailing whitespace.
++++   436	
.oracle/checkins/batch-2-r3.md:4699: trailing whitespace.
++++   437	
.oracle/checkins/batch-2-r3.md:4701: trailing whitespace.
++++   450	
.oracle/checkins/batch-2-r3.md:4703: trailing whitespace.
++++   451	
.oracle/checkins/batch-2-r3.md:4705: trailing whitespace.
++++   456	
.oracle/checkins/batch-2-r3.md:4707: trailing whitespace.
++++   464	
.oracle/checkins/batch-2-r3.md:4709: trailing whitespace.
++++   467	
.oracle/checkins/batch-2-r3.md:4711: trailing whitespace.
++++   471	
.oracle/checkins/batch-2-r3.md:4713: trailing whitespace.
++++   484	
.oracle/checkins/batch-2-r3.md:4715: trailing whitespace.
++++   487	
.oracle/checkins/batch-2-r3.md:4717: trailing whitespace.
++++   490	
.oracle/checkins/batch-2-r3.md:4719: trailing whitespace.
++++   491	
.oracle/checkins/batch-2-r3.md:4721: trailing whitespace.
++++   496	
.oracle/checkins/batch-2-r3.md:4723: trailing whitespace.
++++   506	
.oracle/checkins/batch-2-r3.md:4725: trailing whitespace.
++++   507	
.oracle/checkins/batch-2-r3.md:4727: trailing whitespace.
++++   514	
.oracle/checkins/batch-2-r3.md:4729: trailing whitespace.
++++   515	
.oracle/checkins/batch-2-r3.md:4731: trailing whitespace.
++++   526	
.oracle/checkins/batch-2-r3.md:4733: trailing whitespace.
++++   527	
.oracle/checkins/batch-2-r3.md:4735: trailing whitespace.
++++   546	
.oracle/checkins/batch-2-r3.md:4737: trailing whitespace.
++++   547	
.oracle/checkins/batch-2-r3.md:4739: trailing whitespace.
++++   558	
.oracle/checkins/batch-2-r3.md:4741: trailing whitespace.
++++   559	
.oracle/checkins/batch-2-r3.md:4743: trailing whitespace.
++++   612	
.oracle/checkins/batch-2-r3.md:4745: trailing whitespace.
++++   613	
.oracle/checkins/batch-2-r3.md:4747: trailing whitespace.
++++   638	
.oracle/checkins/batch-2-r3.md:4749: trailing whitespace.
++++   646	
.oracle/checkins/batch-2-r3.md:4751: trailing whitespace.
++++   651	
.oracle/checkins/batch-2-r3.md:4753: trailing whitespace.
++++   678	
.oracle/checkins/batch-2-r3.md:4755: trailing whitespace.
++++   679	
.oracle/checkins/batch-2-r3.md:4757: trailing whitespace.
++++   698	
.oracle/checkins/batch-2-r3.md:4759: trailing whitespace.
++++   699	
.oracle/checkins/batch-2-r3.md:4761: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4763: trailing whitespace.
++++     4	
.oracle/checkins/batch-2-r3.md:4765: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:4767: trailing whitespace.
++++    47	
.oracle/checkins/batch-2-r3.md:4769: trailing whitespace.
++++    68	
.oracle/checkins/batch-2-r3.md:4771: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:4773: trailing whitespace.
++++    91	
.oracle/checkins/batch-2-r3.md:4775: trailing whitespace.
++++    92	
.oracle/checkins/batch-2-r3.md:4777: trailing whitespace.
++++    95	
.oracle/checkins/batch-2-r3.md:4779: trailing whitespace.
++++    96	
.oracle/checkins/batch-2-r3.md:4781: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:4783: trailing whitespace.
++++   111	
.oracle/checkins/batch-2-r3.md:4785: trailing whitespace.
++++   120	
.oracle/checkins/batch-2-r3.md:4787: trailing whitespace.
++++   126	
.oracle/checkins/batch-2-r3.md:4789: trailing whitespace.
++++   129	
.oracle/checkins/batch-2-r3.md:4791: trailing whitespace.
++++   136	
.oracle/checkins/batch-2-r3.md:4793: trailing whitespace.
++++   137	
.oracle/checkins/batch-2-r3.md:4795: trailing whitespace.
++++   149	
.oracle/checkins/batch-2-r3.md:4797: trailing whitespace.
++++   150	
.oracle/checkins/batch-2-r3.md:4799: trailing whitespace.
++++   153	
.oracle/checkins/batch-2-r3.md:4801: trailing whitespace.
++++   154	
.oracle/checkins/batch-2-r3.md:4803: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4805: trailing whitespace.
++++    11	
.oracle/checkins/batch-2-r3.md:4807: trailing whitespace.
++++    13	
.oracle/checkins/batch-2-r3.md:4809: trailing whitespace.
++++    23	
.oracle/checkins/batch-2-r3.md:4811: trailing whitespace.
++++    24	
.oracle/checkins/batch-2-r3.md:4813: trailing whitespace.
++++    29	
.oracle/checkins/batch-2-r3.md:4815: trailing whitespace.
++++    30	
.oracle/checkins/batch-2-r3.md:4817: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r3.md:4819: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r3.md:4821: trailing whitespace.
++++    39	
.oracle/checkins/batch-2-r3.md:4823: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:4825: trailing whitespace.
++++    63	
.oracle/checkins/batch-2-r3.md:4827: trailing whitespace.
++++    64	
.oracle/checkins/batch-2-r3.md:4829: trailing whitespace.
++++    74	
.oracle/checkins/batch-2-r3.md:4831: trailing whitespace.
++++    75	
.oracle/checkins/batch-2-r3.md:4833: trailing whitespace.
++++    89	
.oracle/checkins/batch-2-r3.md:4835: trailing whitespace.
++++    90	
.oracle/checkins/batch-2-r3.md:4837: trailing whitespace.
++++    96	
.oracle/checkins/batch-2-r3.md:4839: trailing whitespace.
++++   100	
.oracle/checkins/batch-2-r3.md:4841: trailing whitespace.
++++   101	
.oracle/checkins/batch-2-r3.md:4843: trailing whitespace.
++++   123	
.oracle/checkins/batch-2-r3.md:4845: trailing whitespace.
++++   125	
.oracle/checkins/batch-2-r3.md:4847: trailing whitespace.
++++   126	
.oracle/checkins/batch-2-r3.md:4849: trailing whitespace.
++++   129	
.oracle/checkins/batch-2-r3.md:4851: trailing whitespace.
++++   139	
.oracle/checkins/batch-2-r3.md:4853: trailing whitespace.
++++   142	
.oracle/checkins/batch-2-r3.md:4855: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r3.md:4857: trailing whitespace.
++++   155	
.oracle/checkins/batch-2-r3.md:4859: trailing whitespace.
++++   161	
.oracle/checkins/batch-2-r3.md:4861: trailing whitespace.
++++   162	
.oracle/checkins/batch-2-r3.md:4863: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:4865: trailing whitespace.
++++   168	
.oracle/checkins/batch-2-r3.md:4867: trailing whitespace.
++++   177	
.oracle/checkins/batch-2-r3.md:4869: trailing whitespace.
++++   178	
.oracle/checkins/batch-2-r3.md:4871: trailing whitespace.
++++   181	
.oracle/checkins/batch-2-r3.md:4873: trailing whitespace.
++++   188	
.oracle/checkins/batch-2-r3.md:4875: trailing whitespace.
++++   194	
.oracle/checkins/batch-2-r3.md:4877: trailing whitespace.
++++   203	
.oracle/checkins/batch-2-r3.md:4879: trailing whitespace.
++++   204	
.oracle/checkins/batch-2-r3.md:4881: trailing whitespace.
++++   208	
.oracle/checkins/batch-2-r3.md:4883: trailing whitespace.
++++   211	
.oracle/checkins/batch-2-r3.md:4885: trailing whitespace.
++++   212	
.oracle/checkins/batch-2-r3.md:4887: trailing whitespace.
++++   216	
.oracle/checkins/batch-2-r3.md:4889: trailing whitespace.
++++   219	
.oracle/checkins/batch-2-r3.md:4891: trailing whitespace.
++++   220	
.oracle/checkins/batch-2-r3.md:4893: trailing whitespace.
++++   224	
.oracle/checkins/batch-2-r3.md:4895: trailing whitespace.
++++   227	
.oracle/checkins/batch-2-r3.md:4897: trailing whitespace.
++++   231	
.oracle/checkins/batch-2-r3.md:4899: trailing whitespace.
++++   232	
.oracle/checkins/batch-2-r3.md:4901: trailing whitespace.
++++   239	
.oracle/checkins/batch-2-r3.md:4903: trailing whitespace.
++++   249	
.oracle/checkins/batch-2-r3.md:4905: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:4907: trailing whitespace.
++++   255	
.oracle/checkins/batch-2-r3.md:4909: trailing whitespace.
++++   261	
.oracle/checkins/batch-2-r3.md:4911: trailing whitespace.
++++   275	
.oracle/checkins/batch-2-r3.md:4913: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:4915: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:4917: trailing whitespace.
++++    10	
.oracle/checkins/batch-2-r3.md:4919: trailing whitespace.
++++    30	
.oracle/checkins/batch-2-r3.md:4921: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r3.md:4923: trailing whitespace.
++++    35	
.oracle/checkins/batch-2-r3.md:4925: trailing whitespace.
++++    37	
.oracle/checkins/batch-2-r3.md:4927: trailing whitespace.
++++    38	
.oracle/checkins/batch-2-r3.md:4929: trailing whitespace.
++++    42	
.oracle/checkins/batch-2-r3.md:4931: trailing whitespace.
++++    50	
.oracle/checkins/batch-2-r3.md:4933: trailing whitespace.
++++    54	
.oracle/checkins/batch-2-r3.md:4935: trailing whitespace.
++++    56	
.oracle/checkins/batch-2-r3.md:4937: trailing whitespace.
++++    57	
.oracle/checkins/batch-2-r3.md:4939: trailing whitespace.
++++    60	
.oracle/checkins/batch-2-r3.md:4941: trailing whitespace.
++++    67	
.oracle/checkins/batch-2-r3.md:4943: trailing whitespace.
++++    68	
.oracle/checkins/batch-2-r3.md:4945: trailing whitespace.
++++    72	
.oracle/checkins/batch-2-r3.md:4947: trailing whitespace.
++++    73	
.oracle/checkins/batch-2-r3.md:4949: trailing whitespace.
++++    80	
.oracle/checkins/batch-2-r3.md:4951: trailing whitespace.
++++    81	
.oracle/checkins/batch-2-r3.md:4953: trailing whitespace.
++++    84	
.oracle/checkins/batch-2-r3.md:4955: trailing whitespace.
++++    91	
.oracle/checkins/batch-2-r3.md:4957: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:4959: trailing whitespace.
++++   107	
.oracle/checkins/batch-2-r3.md:4961: trailing whitespace.
++++   108	
.oracle/checkins/batch-2-r3.md:4963: trailing whitespace.
++++   116	
.oracle/checkins/batch-2-r3.md:4965: trailing whitespace.
++++   117	
.oracle/checkins/batch-2-r3.md:4967: trailing whitespace.
++++   123	
.oracle/checkins/batch-2-r3.md:4969: trailing whitespace.
++++   124	
.oracle/checkins/batch-2-r3.md:4971: trailing whitespace.
++++   127	
.oracle/checkins/batch-2-r3.md:4973: trailing whitespace.
++++   164	
.oracle/checkins/batch-2-r3.md:4975: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:4977: trailing whitespace.
++++   168	
.oracle/checkins/batch-2-r3.md:4979: trailing whitespace.
++++   173	
.oracle/checkins/batch-2-r3.md:4981: trailing whitespace.
++++   187	
.oracle/checkins/batch-2-r3.md:4983: trailing whitespace.
++++   195	
.oracle/checkins/batch-2-r3.md:4985: trailing whitespace.
++++   216	
.oracle/checkins/batch-2-r3.md:4987: trailing whitespace.
++++   220	
.oracle/checkins/batch-2-r3.md:4989: trailing whitespace.
++++   258	
.oracle/checkins/batch-2-r3.md:4991: trailing whitespace.
++++   268	
.oracle/checkins/batch-2-r3.md:4993: trailing whitespace.
++++   298	
.oracle/checkins/batch-2-r3.md:4995: trailing whitespace.
++++   347	
.oracle/checkins/batch-2-r3.md:4997: trailing whitespace.
++++   375	
.oracle/checkins/batch-2-r3.md:4999: trailing whitespace.
++++   397	
.oracle/checkins/batch-2-r3.md:5001: trailing whitespace.
++++   427	
.oracle/checkins/batch-2-r3.md:5003: trailing whitespace.
++++   449	
.oracle/checkins/batch-2-r3.md:5005: trailing whitespace.
++++   455	
.oracle/checkins/batch-2-r3.md:5007: trailing whitespace.
++++   473	
.oracle/checkins/batch-2-r3.md:5009: trailing whitespace.
++++   482	
.oracle/checkins/batch-2-r3.md:5011: trailing whitespace.
++++   487	
.oracle/checkins/batch-2-r3.md:5013: trailing whitespace.
++++   490	
.oracle/checkins/batch-2-r3.md:5015: trailing whitespace.
++++   491	
.oracle/checkins/batch-2-r3.md:5017: trailing whitespace.
++++   493	
.oracle/checkins/batch-2-r3.md:5019: trailing whitespace.
++++   494	
.oracle/checkins/batch-2-r3.md:5021: trailing whitespace.
++++   497	
.oracle/checkins/batch-2-r3.md:5023: trailing whitespace.
++++   500	
.oracle/checkins/batch-2-r3.md:5025: trailing whitespace.
++++   507	
.oracle/checkins/batch-2-r3.md:5027: trailing whitespace.
++++   520	
.oracle/checkins/batch-2-r3.md:5029: trailing whitespace.
++++   520	
.oracle/checkins/batch-2-r3.md:5031: trailing whitespace.
++++   544	
.oracle/checkins/batch-2-r3.md:5033: trailing whitespace.
++++   560	
.oracle/checkins/batch-2-r3.md:5035: trailing whitespace.
++++   579	
.oracle/checkins/batch-2-r3.md:5037: trailing whitespace.
++++   587	
.oracle/checkins/batch-2-r3.md:5039: trailing whitespace.
++++   606	
.oracle/checkins/batch-2-r3.md:5041: trailing whitespace.
++++   607	
.oracle/checkins/batch-2-r3.md:5043: trailing whitespace.
++++   611	
.oracle/checkins/batch-2-r3.md:5045: trailing whitespace.
++++   612	
.oracle/checkins/batch-2-r3.md:5047: trailing whitespace.
++++   615	
.oracle/checkins/batch-2-r3.md:5049: trailing whitespace.
++++   618	
.oracle/checkins/batch-2-r3.md:5051: trailing whitespace.
++++   626	
.oracle/checkins/batch-2-r3.md:5053: trailing whitespace.
++++   632	
.oracle/checkins/batch-2-r3.md:5055: trailing whitespace.
++++   636	
.oracle/checkins/batch-2-r3.md:5057: trailing whitespace.
++++   642	
.oracle/checkins/batch-2-r3.md:5059: trailing whitespace.
++++   665	
.oracle/checkins/batch-2-r3.md:5061: trailing whitespace.
++++   674	
.oracle/checkins/batch-2-r3.md:5063: trailing whitespace.
++++   684	
.oracle/checkins/batch-2-r3.md:5065: trailing whitespace.
++++   714	
.oracle/checkins/batch-2-r3.md:5067: trailing whitespace.
++++   717	
.oracle/checkins/batch-2-r3.md:5069: trailing whitespace.
++++   720	
.oracle/checkins/batch-2-r3.md:5071: trailing whitespace.
++++   721	
.oracle/checkins/batch-2-r3.md:5073: trailing whitespace.
++++   313	
.oracle/checkins/batch-2-r3.md:5075: trailing whitespace.
++++   317	
.oracle/checkins/batch-2-r3.md:5077: trailing whitespace.
++++   318	
.oracle/checkins/batch-2-r3.md:5079: trailing whitespace.
++++   327	
.oracle/checkins/batch-2-r3.md:5081: trailing whitespace.
++++   330	
.oracle/checkins/batch-2-r3.md:5083: trailing whitespace.
++++   333	
.oracle/checkins/batch-2-r3.md:5085: trailing whitespace.
++++   336	
.oracle/checkins/batch-2-r3.md:5087: trailing whitespace.
++++   339	
.oracle/checkins/batch-2-r3.md:5089: trailing whitespace.
++++   342	
.oracle/checkins/batch-2-r3.md:5091: trailing whitespace.
++++   348	
.oracle/checkins/batch-2-r3.md:5093: trailing whitespace.
++++   349	
.oracle/checkins/batch-2-r3.md:5095: trailing whitespace.
++++   357	
.oracle/checkins/batch-2-r3.md:5097: trailing whitespace.
++++   361	
.oracle/checkins/batch-2-r3.md:5099: trailing whitespace.
++++   364	
.oracle/checkins/batch-2-r3.md:5101: trailing whitespace.
++++   370	
.oracle/checkins/batch-2-r3.md:5103: trailing whitespace.
++++   378	
.oracle/checkins/batch-2-r3.md:5105: trailing whitespace.
++++   379	
.oracle/checkins/batch-2-r3.md:5107: trailing whitespace.
++++   401	
.oracle/checkins/batch-2-r3.md:5109: trailing whitespace.
++++   402	
.oracle/checkins/batch-2-r3.md:5111: trailing whitespace.
++++   412	
.oracle/checkins/batch-2-r3.md:5113: trailing whitespace.
++++   419	
.oracle/checkins/batch-2-r3.md:5115: trailing whitespace.
++++   420	
.oracle/checkins/batch-2-r3.md:5117: trailing whitespace.
++++   429	
.oracle/checkins/batch-2-r3.md:5119: trailing whitespace.
++++   434	
.oracle/checkins/batch-2-r3.md:5121: trailing whitespace.
++++   437	
.oracle/checkins/batch-2-r3.md:5123: trailing whitespace.
++++   438	
.oracle/checkins/batch-2-r3.md:5125: trailing whitespace.
++++   449	
.oracle/checkins/batch-2-r3.md:5127: trailing whitespace.
++++   454	
.oracle/checkins/batch-2-r3.md:5129: trailing whitespace.
++++   458	
.oracle/checkins/batch-2-r3.md:5131: trailing whitespace.
++++   461	
.oracle/checkins/batch-2-r3.md:5133: trailing whitespace.
++++   462	
.oracle/checkins/batch-2-r3.md:5135: trailing whitespace.
++++   470	
.oracle/checkins/batch-2-r3.md:5137: trailing whitespace.
++++   481	
.oracle/checkins/batch-2-r3.md:5139: trailing whitespace.
++++   482	
.oracle/checkins/batch-2-r3.md:5141: trailing whitespace.
++++   493	
.oracle/checkins/batch-2-r3.md:5143: trailing whitespace.
++++   496	
.oracle/checkins/batch-2-r3.md:5145: trailing whitespace.
++++   503	
.oracle/checkins/batch-2-r3.md:5147: trailing whitespace.
++++   504	
.oracle/checkins/batch-2-r3.md:5149: trailing whitespace.
++++   518	
.oracle/checkins/batch-2-r3.md:5151: trailing whitespace.
++++   525	
.oracle/checkins/batch-2-r3.md:5153: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5155: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5157: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5159: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5161: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5163: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5165: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5167: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5169: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5171: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5173: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5175: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5177: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5179: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5181: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5183: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5185: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5187: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5189: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5191: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5193: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5195: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5197: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5199: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5201: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5203: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5205: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5207: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5209: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5211: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5213: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5215: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5217: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5219: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5221: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5223: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5225: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5227: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5229: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5231: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5233: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5235: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5237: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5239: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5241: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5243: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5245: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5247: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5249: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5251: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5253: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5255: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5257: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5259: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5261: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5263: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5265: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5267: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5269: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5271: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5273: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5275: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5277: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5279: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5281: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5283: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5285: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5287: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5289: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5291: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5293: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5295: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5297: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5299: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5301: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5303: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5305: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5307: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5309: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5311: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5313: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5315: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5317: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5319: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5321: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5323: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5325: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5327: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5329: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5331: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5333: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5335: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5337: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5339: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5341: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5343: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5345: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5347: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5349: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5351: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5353: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5355: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5357: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5359: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5361: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5363: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5365: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5367: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5369: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5371: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5373: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5375: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5377: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5379: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5381: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5383: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5385: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5387: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5389: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5391: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5393: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5395: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5397: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5399: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5401: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5403: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5405: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5407: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5409: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5411: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5413: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5415: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5417: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5419: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5421: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5423: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5425: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5427: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5429: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5431: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5433: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5435: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5437: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5439: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5441: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5443: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5445: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5447: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5449: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5451: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5453: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5455: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5457: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5459: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5461: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5463: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r3.md:5465: trailing whitespace.
++++     3	
.oracle/checkins/batch-2-r3.md:5467: trailing whitespace.
++++     7	
.oracle/checkins/batch-2-r3.md:5469: trailing whitespace.
++++    13	
.oracle/checkins/batch-2-r3.md:5471: trailing whitespace.
++++    15	
.oracle/checkins/batch-2-r3.md:5473: trailing whitespace.
++++    17	
.oracle/checkins/batch-2-r3.md:5475: trailing whitespace.
++++    19	
.oracle/checkins/batch-2-r3.md:5477: trailing whitespace.
++++    22	
.oracle/checkins/batch-2-r3.md:5479: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:5481: trailing whitespace.
++++    41	
.oracle/checkins/batch-2-r3.md:5483: trailing whitespace.
++++    57	
.oracle/checkins/batch-2-r3.md:5485: trailing whitespace.
++++    58	
.oracle/checkins/batch-2-r3.md:5487: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:5489: trailing whitespace.
++++     6	
.oracle/checkins/batch-2-r3.md:5491: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:5493: trailing whitespace.
++++    15	
.oracle/checkins/batch-2-r3.md:5495: trailing whitespace.
++++    16	
.oracle/checkins/batch-2-r3.md:5497: trailing whitespace.
++++    19	
.oracle/checkins/batch-2-r3.md:5499: trailing whitespace.
++++    20	
.oracle/checkins/batch-2-r3.md:5501: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r3.md:5503: trailing whitespace.
++++    35	
.oracle/checkins/batch-2-r3.md:5505: trailing whitespace.
++++    38	
.oracle/checkins/batch-2-r3.md:5507: trailing whitespace.
++++    44	
.oracle/checkins/batch-2-r3.md:5509: trailing whitespace.
++++    61	
.oracle/checkins/batch-2-r3.md:5511: trailing whitespace.
++++    62	
.oracle/checkins/batch-2-r3.md:5513: trailing whitespace.
++++    66	
.oracle/checkins/batch-2-r3.md:5515: trailing whitespace.
++++    80	
.oracle/checkins/batch-2-r3.md:5517: trailing whitespace.
++++    81	
.oracle/checkins/batch-2-r3.md:5519: trailing whitespace.
++++    83	
.oracle/checkins/batch-2-r3.md:5521: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:5523: trailing whitespace.
++++    89	
.oracle/checkins/batch-2-r3.md:5525: trailing whitespace.
++++    94	
.oracle/checkins/batch-2-r3.md:5527: trailing whitespace.
++++    95	
.oracle/checkins/batch-2-r3.md:5529: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:5531: trailing whitespace.
++++   101	
.oracle/checkins/batch-2-r3.md:5533: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:5535: trailing whitespace.
++++   107	
.oracle/checkins/batch-2-r3.md:5537: trailing whitespace.
++++   110	
.oracle/checkins/batch-2-r3.md:5539: trailing whitespace.
++++   113	
.oracle/checkins/batch-2-r3.md:5541: trailing whitespace.
++++   130	
.oracle/checkins/batch-2-r3.md:5543: trailing whitespace.
++++   131	
.oracle/checkins/batch-2-r3.md:5545: trailing whitespace.
++++   134	
.oracle/checkins/batch-2-r3.md:5547: trailing whitespace.
++++     3	
.oracle/checkins/batch-2-r3.md:5549: trailing whitespace.
++++     6	
.oracle/checkins/batch-2-r3.md:5551: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:5553: trailing whitespace.
++++    14	
.oracle/checkins/batch-2-r3.md:5555: trailing whitespace.
++++    20	
.oracle/checkins/batch-2-r3.md:5557: trailing whitespace.
++++    22	
.oracle/checkins/batch-2-r3.md:5559: trailing whitespace.
++++    30	
.oracle/checkins/batch-2-r3.md:5561: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r3.md:5563: trailing whitespace.
++++    49	
.oracle/checkins/batch-2-r3.md:5565: trailing whitespace.
++++    53	
.oracle/checkins/batch-2-r3.md:5567: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r3.md:5569: trailing whitespace.
++++    57	
.oracle/checkins/batch-2-r3.md:5571: trailing whitespace.
++++    58	
.oracle/checkins/batch-2-r3.md:5573: trailing whitespace.
++++    62	
.oracle/checkins/batch-2-r3.md:5575: trailing whitespace.
++++    63	
.oracle/checkins/batch-2-r3.md:5577: trailing whitespace.
++++    66	
.oracle/checkins/batch-2-r3.md:5579: trailing whitespace.
++++    68	
.oracle/checkins/batch-2-r3.md:5581: trailing whitespace.
++++    73	
.oracle/checkins/batch-2-r3.md:5583: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r3.md:5585: trailing whitespace.
++++    91	
.oracle/checkins/batch-2-r3.md:5587: trailing whitespace.
++++    92	
.oracle/checkins/batch-2-r3.md:5589: trailing whitespace.
++++    99	
.oracle/checkins/batch-2-r3.md:5591: trailing whitespace.
++++   100	
.oracle/checkins/batch-2-r3.md:5593: trailing whitespace.
++++   104	
.oracle/checkins/batch-2-r3.md:5595: trailing whitespace.
++++   105	
.oracle/checkins/batch-2-r3.md:5597: trailing whitespace.
++++   117	
.oracle/checkins/batch-2-r3.md:5599: trailing whitespace.
++++   118	
.oracle/checkins/batch-2-r3.md:5601: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r3.md:5603: trailing whitespace.
++++   144	
.oracle/checkins/batch-2-r3.md:5605: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:5607: trailing whitespace.
++++   166	
.oracle/checkins/batch-2-r3.md:5609: trailing whitespace.
++++   169	
.oracle/checkins/batch-2-r3.md:5611: trailing whitespace.
++++   190	
.oracle/checkins/batch-2-r3.md:5613: trailing whitespace.
++++   191	
.oracle/checkins/batch-2-r3.md:5615: trailing whitespace.
++++   195	
.oracle/checkins/batch-2-r3.md:5617: trailing whitespace.
++++   196	
.oracle/checkins/batch-2-r3.md:5619: trailing whitespace.
++++   199	
.oracle/checkins/batch-2-r3.md:5621: trailing whitespace.
++++   200	
.oracle/checkins/batch-2-r3.md:5623: trailing whitespace.
++++   203	
.oracle/checkins/batch-2-r3.md:5625: trailing whitespace.
++++   204	
.oracle/checkins/batch-2-r3.md:5627: trailing whitespace.
++++   207	
.oracle/checkins/batch-2-r3.md:5629: trailing whitespace.
++++   208	
.oracle/checkins/batch-2-r3.md:5631: trailing whitespace.
++++   214	
.oracle/checkins/batch-2-r3.md:5633: trailing whitespace.
++++   215	
.oracle/checkins/batch-2-r3.md:5635: trailing whitespace.
++++   228	
.oracle/checkins/batch-2-r3.md:5637: trailing whitespace.
++++   229	
.oracle/checkins/batch-2-r3.md:5639: trailing whitespace.
++++   244	
.oracle/checkins/batch-2-r3.md:5641: trailing whitespace.
++++   245	
.oracle/checkins/batch-2-r3.md:5643: trailing whitespace.
++++   252	
.oracle/checkins/batch-2-r3.md:5645: trailing whitespace.
++++   253	
.oracle/checkins/batch-2-r3.md:5647: trailing whitespace.
++++   257	
.oracle/checkins/batch-2-r3.md:5649: trailing whitespace.
++++   258	
.oracle/checkins/batch-2-r3.md:5651: trailing whitespace.
++++   262	
.oracle/checkins/batch-2-r3.md:5653: trailing whitespace.
++++   263	
.oracle/checkins/batch-2-r3.md:5655: trailing whitespace.
++++   286	
.oracle/checkins/batch-2-r3.md:5657: trailing whitespace.
++++   287	
.oracle/checkins/batch-2-r3.md:5659: trailing whitespace.
++++   303	
.oracle/checkins/batch-2-r3.md:5661: trailing whitespace.
++++   304	
.oracle/checkins/batch-2-r3.md:5663: trailing whitespace.
++++   326	
.oracle/checkins/batch-2-r3.md:5665: trailing whitespace.
++++   336	
.oracle/checkins/batch-2-r3.md:5667: trailing whitespace.
++++   340	
.oracle/checkins/batch-2-r3.md:5669: trailing whitespace.
++++   341	
.oracle/checkins/batch-2-r3.md:5671: trailing whitespace.
++++   352	
.oracle/checkins/batch-2-r3.md:5673: trailing whitespace.
++++   355	
.oracle/checkins/batch-2-r3.md:5675: trailing whitespace.
++++   359	
.oracle/checkins/batch-2-r3.md:5677: trailing whitespace.
++++   368	
.oracle/checkins/batch-2-r3.md:5679: trailing whitespace.
++++   372	
.oracle/checkins/batch-2-r3.md:5681: trailing whitespace.
++++   376	
.oracle/checkins/batch-2-r3.md:5683: trailing whitespace.
++++   380	
.oracle/checkins/batch-2-r3.md:5685: trailing whitespace.
++++   384	
.oracle/checkins/batch-2-r3.md:5687: trailing whitespace.
++++   385	
.oracle/checkins/batch-2-r3.md:5689: trailing whitespace.
++++   389	
.oracle/checkins/batch-2-r3.md:5691: trailing whitespace.
++++   390	
.oracle/checkins/batch-2-r3.md:5693: trailing whitespace.
++++   393	
.oracle/checkins/batch-2-r3.md:5695: trailing whitespace.
++++   394	
.oracle/checkins/batch-2-r3.md:5697: trailing whitespace.
++++   407	
.oracle/checkins/batch-2-r3.md:5699: trailing whitespace.
++++   408	
.oracle/checkins/batch-2-r3.md:5701: trailing whitespace.
++++   427	
.oracle/checkins/batch-2-r3.md:5703: trailing whitespace.
++++   428	
.oracle/checkins/batch-2-r3.md:5705: trailing whitespace.
++++   443	
.oracle/checkins/batch-2-r3.md:5707: trailing whitespace.
++++   444	
.oracle/checkins/batch-2-r3.md:5709: trailing whitespace.
++++   458	
.oracle/checkins/batch-2-r3.md:5711: trailing whitespace.
++++   467	
.oracle/checkins/batch-2-r3.md:5713: trailing whitespace.
++++   470	
.oracle/checkins/batch-2-r3.md:5715: trailing whitespace.
++++   522	
.oracle/checkins/batch-2-r3.md:5717: trailing whitespace.
++++   523	
.oracle/checkins/batch-2-r3.md:5719: trailing whitespace.
++++   533	
.oracle/checkins/batch-2-r3.md:5721: trailing whitespace.
++++   546	
.oracle/checkins/batch-2-r3.md:5723: trailing whitespace.
++++   558	
.oracle/checkins/batch-2-r3.md:5725: trailing whitespace.
++++   559	
.oracle/checkins/batch-2-r3.md:5727: trailing whitespace.
++++   120	
.oracle/checkins/batch-2-r3.md:5729: trailing whitespace.
++++   121	
.oracle/checkins/batch-2-r3.md:5731: trailing whitespace.
++++   131	
.oracle/checkins/batch-2-r3.md:5733: trailing whitespace.
++++   132	
.oracle/checkins/batch-2-r3.md:5735: trailing whitespace.
++++   153	
.oracle/checkins/batch-2-r3.md:5737: trailing whitespace.
++++   154	
.oracle/checkins/batch-2-r3.md:5739: trailing whitespace.
++++   164	
.oracle/checkins/batch-2-r3.md:5741: trailing whitespace.
++++   170	
.oracle/checkins/batch-2-r3.md:5743: trailing whitespace.
++++   182	
.oracle/checkins/batch-2-r3.md:5745: trailing whitespace.
++++   183	
.oracle/checkins/batch-2-r3.md:5747: trailing whitespace.
++++   187	
.oracle/checkins/batch-2-r3.md:5749: trailing whitespace.
++++   188	
.oracle/checkins/batch-2-r3.md:5751: trailing whitespace.
++++   194	
.oracle/checkins/batch-2-r3.md:5753: trailing whitespace.
++++   204	
.oracle/checkins/batch-2-r3.md:5755: trailing whitespace.
++++   221	
.oracle/checkins/batch-2-r3.md:5757: trailing whitespace.
++++   231	
.oracle/checkins/batch-2-r3.md:5759: trailing whitespace.
++++   244	
.oracle/checkins/batch-2-r3.md:5761: trailing whitespace.
++++   249	
.oracle/checkins/batch-2-r3.md:5763: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:5765: trailing whitespace.
++++   256	
.oracle/checkins/batch-2-r3.md:5767: trailing whitespace.
++++   266	
.oracle/checkins/batch-2-r3.md:5769: trailing whitespace.
++++   267	
.oracle/checkins/batch-2-r3.md:5771: trailing whitespace.
++++   271	
.oracle/checkins/batch-2-r3.md:5773: trailing whitespace.
++++   272	
.oracle/checkins/batch-2-r3.md:5775: trailing whitespace.
++++   276	
.oracle/checkins/batch-2-r3.md:5777: trailing whitespace.
++++   279	
.oracle/checkins/batch-2-r3.md:5779: trailing whitespace.
++++   287	
.oracle/checkins/batch-2-r3.md:5781: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r3.md:5783: trailing whitespace.
++++   292	
.oracle/checkins/batch-2-r3.md:5785: trailing whitespace.
++++   301	
.oracle/checkins/batch-2-r3.md:5787: trailing whitespace.
++++   302	
.oracle/checkins/batch-2-r3.md:5789: trailing whitespace.
++++   311	
.oracle/checkins/batch-2-r3.md:5791: trailing whitespace.
++++   314	
.oracle/checkins/batch-2-r3.md:5793: trailing whitespace.
++++   315	
.oracle/checkins/batch-2-r3.md:5795: trailing whitespace.
++++   319	
.oracle/checkins/batch-2-r3.md:5797: trailing whitespace.
++++   320	
.oracle/checkins/batch-2-r3.md:5799: trailing whitespace.
++++   326	
.oracle/checkins/batch-2-r3.md:5801: trailing whitespace.
++++     3	
.oracle/checkins/batch-2-r3.md:5803: trailing whitespace.
++++     4	
.oracle/checkins/batch-2-r3.md:5805: trailing whitespace.
++++    10	
.oracle/checkins/batch-2-r3.md:5807: trailing whitespace.
++++    12	
.oracle/checkins/batch-2-r3.md:5809: trailing whitespace.
++++    14	
.oracle/checkins/batch-2-r3.md:5811: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r3.md:5813: trailing whitespace.
++++    37	
.oracle/checkins/batch-2-r3.md:5815: trailing whitespace.
++++    42	
.oracle/checkins/batch-2-r3.md:5817: trailing whitespace.
++++    45	
.oracle/checkins/batch-2-r3.md:5819: trailing whitespace.
++++    46	
.oracle/checkins/batch-2-r3.md:5821: trailing whitespace.
++++    49	
.oracle/checkins/batch-2-r3.md:5823: trailing whitespace.
++++    50	
.oracle/checkins/batch-2-r3.md:5825: trailing whitespace.
++++    53	
.oracle/checkins/batch-2-r3.md:5827: trailing whitespace.
++++    59	
.oracle/checkins/batch-2-r3.md:5829: trailing whitespace.
++++    63	
.oracle/checkins/batch-2-r3.md:5831: trailing whitespace.
++++    67	
.oracle/checkins/batch-2-r3.md:5833: trailing whitespace.
++++    72	
.oracle/checkins/batch-2-r3.md:5835: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r3.md:5837: trailing whitespace.
++++    97	
.oracle/checkins/batch-2-r3.md:5839: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:5841: trailing whitespace.
++++   100	
.oracle/checkins/batch-2-r3.md:5843: trailing whitespace.
++++   101	
.oracle/checkins/batch-2-r3.md:5845: trailing whitespace.
++++   105	
.oracle/checkins/batch-2-r3.md:5847: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:5849: trailing whitespace.
++++   109	
.oracle/checkins/batch-2-r3.md:5851: trailing whitespace.
++++   110	
.oracle/checkins/batch-2-r3.md:5853: trailing whitespace.
++++   117	
.oracle/checkins/batch-2-r3.md:5855: trailing whitespace.
++++   118	
.oracle/checkins/batch-2-r3.md:5857: trailing whitespace.
++++   123	
.oracle/checkins/batch-2-r3.md:5859: trailing whitespace.
++++   136	
.oracle/checkins/batch-2-r3.md:5861: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r3.md:5863: trailing whitespace.
++++   146	
.oracle/checkins/batch-2-r3.md:5865: trailing whitespace.
++++   149	
.oracle/checkins/batch-2-r3.md:5867: trailing whitespace.
++++   150	
.oracle/checkins/batch-2-r3.md:5869: trailing whitespace.
++++   156	
.oracle/checkins/batch-2-r3.md:5871: trailing whitespace.
++++   157	
.oracle/checkins/batch-2-r3.md:5873: trailing whitespace.
++++   160	
.oracle/checkins/batch-2-r3.md:5875: trailing whitespace.
++++   161	
.oracle/checkins/batch-2-r3.md:5877: trailing whitespace.
++++   164	
.oracle/checkins/batch-2-r3.md:5879: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:5881: trailing whitespace.
++++   171	
.oracle/checkins/batch-2-r3.md:5883: trailing whitespace.
++++   172	
.oracle/checkins/batch-2-r3.md:5885: trailing whitespace.
++++   182	
.oracle/checkins/batch-2-r3.md:5887: trailing whitespace.
++++   183	
.oracle/checkins/batch-2-r3.md:5889: trailing whitespace.
++++   186	
.oracle/checkins/batch-2-r3.md:5891: trailing whitespace.
++++   187	
.oracle/checkins/batch-2-r3.md:5893: trailing whitespace.
++++   190	
.oracle/checkins/batch-2-r3.md:5895: trailing whitespace.
++++   191	
.oracle/checkins/batch-2-r3.md:5897: trailing whitespace.
++++   201	
.oracle/checkins/batch-2-r3.md:5899: trailing whitespace.
++++   202	
.oracle/checkins/batch-2-r3.md:5901: trailing whitespace.
++++   208	
.oracle/checkins/batch-2-r3.md:5903: trailing whitespace.
++++   209	
.oracle/checkins/batch-2-r3.md:5905: trailing whitespace.
++++   216	
.oracle/checkins/batch-2-r3.md:5907: trailing whitespace.
++++   217	
.oracle/checkins/batch-2-r3.md:5909: trailing whitespace.
++++   222	
.oracle/checkins/batch-2-r3.md:5911: trailing whitespace.
++++   223	
.oracle/checkins/batch-2-r3.md:5913: trailing whitespace.
++++   229	
.oracle/checkins/batch-2-r3.md:5915: trailing whitespace.
++++   230	
.oracle/checkins/batch-2-r3.md:5917: trailing whitespace.
++++   234	
.oracle/checkins/batch-2-r3.md:5919: trailing whitespace.
++++   235	
.oracle/checkins/batch-2-r3.md:5921: trailing whitespace.
++++   249	
.oracle/checkins/batch-2-r3.md:5923: trailing whitespace.
++++   250	
.oracle/checkins/batch-2-r3.md:5925: trailing whitespace.
++++   262	
.oracle/checkins/batch-2-r3.md:5927: trailing whitespace.
++++   266	
.oracle/checkins/batch-2-r3.md:5929: trailing whitespace.
++++   283	
.oracle/checkins/batch-2-r3.md:5931: trailing whitespace.
++++   284	
.oracle/checkins/batch-2-r3.md:5933: trailing whitespace.
++++   304	
.oracle/checkins/batch-2-r3.md:5935: trailing whitespace.
++++   308	
.oracle/checkins/batch-2-r3.md:5937: trailing whitespace.
++++   344	
.oracle/checkins/batch-2-r3.md:5939: trailing whitespace.
++++   345	
.oracle/checkins/batch-2-r3.md:5941: trailing whitespace.
++++   359	
.oracle/checkins/batch-2-r3.md:5943: trailing whitespace.
++++   360	
.oracle/checkins/batch-2-r3.md:5945: trailing whitespace.
++++   408	
.oracle/checkins/batch-2-r3.md:5947: trailing whitespace.
++++   409	
.oracle/checkins/batch-2-r3.md:5949: trailing whitespace.
++++   430	
.oracle/checkins/batch-2-r3.md:5951: trailing whitespace.
++++   431	
.oracle/checkins/batch-2-r3.md:5953: trailing whitespace.
++++   444	
.oracle/checkins/batch-2-r3.md:5955: trailing whitespace.
++++   445	
.oracle/checkins/batch-2-r3.md:5957: trailing whitespace.
++++   455	
.oracle/checkins/batch-2-r3.md:5959: trailing whitespace.
++++   456	
.oracle/checkins/batch-2-r3.md:5961: trailing whitespace.
++++   486	
.oracle/checkins/batch-2-r3.md:5963: trailing whitespace.
++++   487	
.oracle/checkins/batch-2-r3.md:5965: trailing whitespace.
++++   503	
.oracle/checkins/batch-2-r3.md:5967: trailing whitespace.
++++   504	
.oracle/checkins/batch-2-r3.md:5969: trailing whitespace.
++++     3	
.oracle/checkins/batch-2-r3.md:5971: trailing whitespace.
++++    13	
.oracle/checkins/batch-2-r3.md:5973: trailing whitespace.
++++    19	
.oracle/checkins/batch-2-r3.md:5975: trailing whitespace.
++++    21	
.oracle/checkins/batch-2-r3.md:5977: trailing whitespace.
++++    38	
.oracle/checkins/batch-2-r3.md:5979: trailing whitespace.
++++    42	
.oracle/checkins/batch-2-r3.md:5981: trailing whitespace.
++++    47	
.oracle/checkins/batch-2-r3.md:5983: trailing whitespace.
++++    50	
.oracle/checkins/batch-2-r3.md:5985: trailing whitespace.
++++    51	
.oracle/checkins/batch-2-r3.md:5987: trailing whitespace.
++++    54	
.oracle/checkins/batch-2-r3.md:5989: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r3.md:5991: trailing whitespace.
++++    58	
.oracle/checkins/batch-2-r3.md:5993: trailing whitespace.
++++    64	
.oracle/checkins/batch-2-r3.md:5995: trailing whitespace.
++++    68	
.oracle/checkins/batch-2-r3.md:5997: trailing whitespace.
++++    72	
.oracle/checkins/batch-2-r3.md:5999: trailing whitespace.
++++    77	
.oracle/checkins/batch-2-r3.md:6001: trailing whitespace.
++++    87	
.oracle/checkins/batch-2-r3.md:6003: trailing whitespace.
++++   102	
.oracle/checkins/batch-2-r3.md:6005: trailing whitespace.
++++   103	
.oracle/checkins/batch-2-r3.md:6007: trailing whitespace.
++++   105	
.oracle/checkins/batch-2-r3.md:6009: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:6011: trailing whitespace.
++++   110	
.oracle/checkins/batch-2-r3.md:6013: trailing whitespace.
++++   111	
.oracle/checkins/batch-2-r3.md:6015: trailing whitespace.
++++   114	
.oracle/checkins/batch-2-r3.md:6017: trailing whitespace.
++++   115	
.oracle/checkins/batch-2-r3.md:6019: trailing whitespace.
++++   122	
.oracle/checkins/batch-2-r3.md:6021: trailing whitespace.
++++   123	
.oracle/checkins/batch-2-r3.md:6023: trailing whitespace.
++++   128	
.oracle/checkins/batch-2-r3.md:6025: trailing whitespace.
++++   141	
.oracle/checkins/batch-2-r3.md:6027: trailing whitespace.
++++   148	
.oracle/checkins/batch-2-r3.md:6029: trailing whitespace.
++++   151	
.oracle/checkins/batch-2-r3.md:6031: trailing whitespace.
++++   154	
.oracle/checkins/batch-2-r3.md:6033: trailing whitespace.
++++   155	
.oracle/checkins/batch-2-r3.md:6035: trailing whitespace.
++++   161	
.oracle/checkins/batch-2-r3.md:6037: trailing whitespace.
++++   162	
.oracle/checkins/batch-2-r3.md:6039: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:6041: trailing whitespace.
++++   166	
.oracle/checkins/batch-2-r3.md:6043: trailing whitespace.
++++   169	
.oracle/checkins/batch-2-r3.md:6045: trailing whitespace.
++++   170	
.oracle/checkins/batch-2-r3.md:6047: trailing whitespace.
++++   176	
.oracle/checkins/batch-2-r3.md:6049: trailing whitespace.
++++   177	
.oracle/checkins/batch-2-r3.md:6051: trailing whitespace.
++++   187	
.oracle/checkins/batch-2-r3.md:6053: trailing whitespace.
++++   188	
.oracle/checkins/batch-2-r3.md:6055: trailing whitespace.
++++   191	
.oracle/checkins/batch-2-r3.md:6057: trailing whitespace.
++++   192	
.oracle/checkins/batch-2-r3.md:6059: trailing whitespace.
++++   195	
.oracle/checkins/batch-2-r3.md:6061: trailing whitespace.
++++   196	
.oracle/checkins/batch-2-r3.md:6063: trailing whitespace.
++++   206	
.oracle/checkins/batch-2-r3.md:6065: trailing whitespace.
++++   207	
.oracle/checkins/batch-2-r3.md:6067: trailing whitespace.
++++   213	
.oracle/checkins/batch-2-r3.md:6069: trailing whitespace.
++++   214	
.oracle/checkins/batch-2-r3.md:6071: trailing whitespace.
++++   221	
.oracle/checkins/batch-2-r3.md:6073: trailing whitespace.
++++   222	
.oracle/checkins/batch-2-r3.md:6075: trailing whitespace.
++++   227	
.oracle/checkins/batch-2-r3.md:6077: trailing whitespace.
++++   228	
.oracle/checkins/batch-2-r3.md:6079: trailing whitespace.
++++   234	
.oracle/checkins/batch-2-r3.md:6081: trailing whitespace.
++++   235	
.oracle/checkins/batch-2-r3.md:6083: trailing whitespace.
++++   239	
.oracle/checkins/batch-2-r3.md:6085: trailing whitespace.
++++   240	
.oracle/checkins/batch-2-r3.md:6087: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:6089: trailing whitespace.
++++   255	
.oracle/checkins/batch-2-r3.md:6091: trailing whitespace.
++++   267	
.oracle/checkins/batch-2-r3.md:6093: trailing whitespace.
++++   271	
.oracle/checkins/batch-2-r3.md:6095: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r3.md:6097: trailing whitespace.
++++   289	
.oracle/checkins/batch-2-r3.md:6099: trailing whitespace.
++++   309	
.oracle/checkins/batch-2-r3.md:6101: trailing whitespace.
++++   313	
.oracle/checkins/batch-2-r3.md:6103: trailing whitespace.
++++   349	
.oracle/checkins/batch-2-r3.md:6105: trailing whitespace.
++++   350	
.oracle/checkins/batch-2-r3.md:6107: trailing whitespace.
++++   364	
.oracle/checkins/batch-2-r3.md:6109: trailing whitespace.
++++   365	
.oracle/checkins/batch-2-r3.md:6111: trailing whitespace.
++++   413	
.oracle/checkins/batch-2-r3.md:6113: trailing whitespace.
++++   414	
.oracle/checkins/batch-2-r3.md:6115: trailing whitespace.
++++   435	
.oracle/checkins/batch-2-r3.md:6117: trailing whitespace.
++++   436	
.oracle/checkins/batch-2-r3.md:6119: trailing whitespace.
++++   449	
.oracle/checkins/batch-2-r3.md:6121: trailing whitespace.
++++   450	
.oracle/checkins/batch-2-r3.md:6123: trailing whitespace.
++++   460	
.oracle/checkins/batch-2-r3.md:6125: trailing whitespace.
++++   461	
.oracle/checkins/batch-2-r3.md:6127: trailing whitespace.
++++    17	
.oracle/checkins/batch-2-r3.md:6129: trailing whitespace.
++++    20	
.oracle/checkins/batch-2-r3.md:6131: trailing whitespace.
++++    21	
.oracle/checkins/batch-2-r3.md:6133: trailing whitespace.
++++    27	
.oracle/checkins/batch-2-r3.md:6135: trailing whitespace.
++++    35	
.oracle/checkins/batch-2-r3.md:6137: trailing whitespace.
++++    36	
.oracle/checkins/batch-2-r3.md:6139: trailing whitespace.
++++    51	
.oracle/checkins/batch-2-r3.md:6141: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r3.md:6143: trailing whitespace.
++++    78	
.oracle/checkins/batch-2-r3.md:6145: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:6147: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:6149: trailing whitespace.
++++   114	
.oracle/checkins/batch-2-r3.md:6151: trailing whitespace.
++++   122	
.oracle/checkins/batch-2-r3.md:6153: trailing whitespace.
++++   132	
.oracle/checkins/batch-2-r3.md:6155: trailing whitespace.
++++   141	
.oracle/checkins/batch-2-r3.md:6157: trailing whitespace.
++++   147	
.oracle/checkins/batch-2-r3.md:6159: trailing whitespace.
++++   154	
.oracle/checkins/batch-2-r3.md:6161: trailing whitespace.
++++   169	
.oracle/checkins/batch-2-r3.md:6163: trailing whitespace.
++++   177	
.oracle/checkins/batch-2-r3.md:6165: trailing whitespace.
++++   190	
.oracle/checkins/batch-2-r3.md:6167: trailing whitespace.
++++   208	
.oracle/checkins/batch-2-r3.md:6169: trailing whitespace.
++++   216	
.oracle/checkins/batch-2-r3.md:6171: trailing whitespace.
++++   225	
.oracle/checkins/batch-2-r3.md:6173: trailing whitespace.
++++   245	
.oracle/checkins/batch-2-r3.md:6175: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:6177: trailing whitespace.
++++   263	
.oracle/checkins/batch-2-r3.md:6179: trailing whitespace.
++++   273	
.oracle/checkins/batch-2-r3.md:6181: trailing whitespace.
++++   274	
.oracle/checkins/batch-2-r3.md:6183: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:6185: trailing whitespace.
++++     4	
.oracle/checkins/batch-2-r3.md:6187: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r3.md:6189: trailing whitespace.
++++    11	
.oracle/checkins/batch-2-r3.md:6191: trailing whitespace.
++++    29	
.oracle/checkins/batch-2-r3.md:6193: trailing whitespace.
++++    30	
.oracle/checkins/batch-2-r3.md:6195: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r3.md:6197: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r3.md:6199: trailing whitespace.
++++    39	
.oracle/checkins/batch-2-r3.md:6201: trailing whitespace.
++++    41	
.oracle/checkins/batch-2-r3.md:6203: trailing whitespace.
++++    42	
.oracle/checkins/batch-2-r3.md:6205: trailing whitespace.
++++    54	
.oracle/checkins/batch-2-r3.md:6207: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r3.md:6209: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r3.md:6211: trailing whitespace.
++++    83	
.oracle/checkins/batch-2-r3.md:6213: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:6215: trailing whitespace.
++++    93	
.oracle/checkins/batch-2-r3.md:6217: trailing whitespace.
++++    94	
.oracle/checkins/batch-2-r3.md:6219: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r3.md:6221: trailing whitespace.
++++   107	
.oracle/checkins/batch-2-r3.md:6223: trailing whitespace.
++++   199	
.oracle/checkins/batch-2-r3.md:6225: trailing whitespace.
++++   200	
.oracle/checkins/batch-2-r3.md:6227: trailing whitespace.
++++   276	
.oracle/checkins/batch-2-r3.md:6229: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r3.md:6231: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r3.md:6233: trailing whitespace.
++++   289	
.oracle/checkins/batch-2-r3.md:6235: trailing whitespace.
++++   311	
.oracle/checkins/batch-2-r3.md:6237: trailing whitespace.
++++   312	
.oracle/checkins/batch-2-r3.md:6239: trailing whitespace.
++++   959	
.oracle/checkins/batch-2-r3.md:6241: trailing whitespace.
++++   960	
.oracle/checkins/batch-2-r3.md:6243: trailing whitespace.
++++   963	
.oracle/checkins/batch-2-r3.md:6245: trailing whitespace.
++++   964	
.oracle/checkins/batch-2-r3.md:6247: trailing whitespace.
++++   970	
.oracle/checkins/batch-2-r3.md:6249: trailing whitespace.
++++   975	
.oracle/checkins/batch-2-r3.md:6251: trailing whitespace.
++++   989	
.oracle/checkins/batch-2-r3.md:6253: trailing whitespace.
++++   990	
.oracle/checkins/batch-2-r3.md:6255: trailing whitespace.
++++  1001	
.oracle/checkins/batch-2-r3.md:6257: trailing whitespace.
++++  1002	
.oracle/checkins/batch-2-r3.md:6259: trailing whitespace.
++++    81	
.oracle/checkins/batch-2-r3.md:6261: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r3.md:6263: trailing whitespace.
++++    85	
.oracle/checkins/batch-2-r3.md:6265: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:6267: trailing whitespace.
++++    89	
.oracle/checkins/batch-2-r3.md:6269: trailing whitespace.
++++    90	
.oracle/checkins/batch-2-r3.md:6271: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:6273: trailing whitespace.
++++    99	
.oracle/checkins/batch-2-r3.md:6275: trailing whitespace.
++++   125	
.oracle/checkins/batch-2-r3.md:6277: trailing whitespace.
++++   126	
.oracle/checkins/batch-2-r3.md:6279: trailing whitespace.
++++   133	
.oracle/checkins/batch-2-r3.md:6281: trailing whitespace.
++++   138	
.oracle/checkins/batch-2-r3.md:6283: trailing whitespace.
++++   169	
.oracle/checkins/batch-2-r3.md:6285: trailing whitespace.
++++   170	
.oracle/checkins/batch-2-r3.md:6287: trailing whitespace.
++++   177	
.oracle/checkins/batch-2-r3.md:6289: trailing whitespace.
++++   179	
.oracle/checkins/batch-2-r3.md:6291: trailing whitespace.
++++   180	
.oracle/checkins/batch-2-r3.md:6293: trailing whitespace.
++++   196	
.oracle/checkins/batch-2-r3.md:6295: trailing whitespace.
++++   197	
.oracle/checkins/batch-2-r3.md:6297: trailing whitespace.
++++   218	
.oracle/checkins/batch-2-r3.md:6299: trailing whitespace.
++++   244	
.oracle/checkins/batch-2-r3.md:6301: trailing whitespace.
++++   245	
.oracle/checkins/batch-2-r3.md:6303: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:6305: trailing whitespace.
++++     7	
.oracle/checkins/batch-2-r3.md:6307: trailing whitespace.
++++     9	
.oracle/checkins/batch-2-r3.md:6309: trailing whitespace.
++++    18	
.oracle/checkins/batch-2-r3.md:6311: trailing whitespace.
++++    21	
.oracle/checkins/batch-2-r3.md:6313: trailing whitespace.
++++    23	
.oracle/checkins/batch-2-r3.md:6315: trailing whitespace.
++++    28	
.oracle/checkins/batch-2-r3.md:6317: trailing whitespace.
++++    31	
.oracle/checkins/batch-2-r3.md:6319: trailing whitespace.
++++    32	
.oracle/checkins/batch-2-r3.md:6321: trailing whitespace.
++++    36	
.oracle/checkins/batch-2-r3.md:6323: trailing whitespace.
++++    37	
.oracle/checkins/batch-2-r3.md:6325: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:6327: trailing whitespace.
++++    44	
.oracle/checkins/batch-2-r3.md:6329: trailing whitespace.
++++    59	
.oracle/checkins/batch-2-r3.md:6331: trailing whitespace.
++++    66	
.oracle/checkins/batch-2-r3.md:6333: trailing whitespace.
++++    69	
.oracle/checkins/batch-2-r3.md:6335: trailing whitespace.
++++    72	
.oracle/checkins/batch-2-r3.md:6337: trailing whitespace.
++++    73	
.oracle/checkins/batch-2-r3.md:6339: trailing whitespace.
++++    76	
.oracle/checkins/batch-2-r3.md:6341: trailing whitespace.
++++    81	
.oracle/checkins/batch-2-r3.md:6343: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r3.md:6345: trailing whitespace.
++++    85	
.oracle/checkins/batch-2-r3.md:6347: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:6349: trailing whitespace.
++++    89	
.oracle/checkins/batch-2-r3.md:6351: trailing whitespace.
++++    90	
.oracle/checkins/batch-2-r3.md:6353: trailing whitespace.
++++    98	
.oracle/checkins/batch-2-r3.md:6355: trailing whitespace.
++++    99	
.oracle/checkins/batch-2-r3.md:6357: trailing whitespace.
++++   125	
.oracle/checkins/batch-2-r3.md:6359: trailing whitespace.
++++   126	
.oracle/checkins/batch-2-r3.md:6361: trailing whitespace.
++++   133	
.oracle/checkins/batch-2-r3.md:6363: trailing whitespace.
++++   138	
.oracle/checkins/batch-2-r3.md:6365: trailing whitespace.
++++   169	
.oracle/checkins/batch-2-r3.md:6367: trailing whitespace.
++++   170	
.oracle/checkins/batch-2-r3.md:6369: trailing whitespace.
++++   177	
.oracle/checkins/batch-2-r3.md:6371: trailing whitespace.
++++   179	
.oracle/checkins/batch-2-r3.md:6373: trailing whitespace.
++++   180	
.oracle/checkins/batch-2-r3.md:6375: trailing whitespace.
++++   196	
.oracle/checkins/batch-2-r3.md:6377: trailing whitespace.
++++   197	
.oracle/checkins/batch-2-r3.md:6379: trailing whitespace.
++++   218	
.oracle/checkins/batch-2-r3.md:6381: trailing whitespace.
++++   244	
.oracle/checkins/batch-2-r3.md:6383: trailing whitespace.
++++   245	
.oracle/checkins/batch-2-r3.md:6385: trailing whitespace.
++++   255	
.oracle/checkins/batch-2-r3.md:6387: trailing whitespace.
++++   262	
.oracle/checkins/batch-2-r3.md:6389: trailing whitespace.
++++   265	
.oracle/checkins/batch-2-r3.md:6391: trailing whitespace.
++++   270	
.oracle/checkins/batch-2-r3.md:6393: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r3.md:6395: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r3.md:6397: trailing whitespace.
++++   296	
.oracle/checkins/batch-2-r3.md:6399: trailing whitespace.
++++   306	
.oracle/checkins/batch-2-r3.md:6401: trailing whitespace.
++++   307	
.oracle/checkins/batch-2-r3.md:6403: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r3.md:6405: trailing whitespace.
++++     7	
.oracle/checkins/batch-2-r3.md:6407: trailing whitespace.
++++     9	
.oracle/checkins/batch-2-r3.md:6409: trailing whitespace.
++++    19	
.oracle/checkins/batch-2-r3.md:6411: trailing whitespace.
++++    20	
.oracle/checkins/batch-2-r3.md:6413: trailing whitespace.
++++    23	
.oracle/checkins/batch-2-r3.md:6415: trailing whitespace.
++++    24	
.oracle/checkins/batch-2-r3.md:6417: trailing whitespace.
++++    39	
.oracle/checkins/batch-2-r3.md:6419: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r3.md:6421: trailing whitespace.
++++    47	
.oracle/checkins/batch-2-r3.md:6423: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r3.md:6425: trailing whitespace.
++++    64	
.oracle/checkins/batch-2-r3.md:6427: trailing whitespace.
++++    65	
.oracle/checkins/batch-2-r3.md:6429: trailing whitespace.
++++    75	
.oracle/checkins/batch-2-r3.md:6431: trailing whitespace.
++++    81	
.oracle/checkins/batch-2-r3.md:6433: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r3.md:6435: trailing whitespace.
++++    92	
.oracle/checkins/batch-2-r3.md:6437: trailing whitespace.
++++    96	
.oracle/checkins/batch-2-r3.md:6439: trailing whitespace.
++++   108	
.oracle/checkins/batch-2-r3.md:6441: trailing whitespace.
++++   114	
.oracle/checkins/batch-2-r3.md:6443: trailing whitespace.
++++   119	
.oracle/checkins/batch-2-r3.md:6445: trailing whitespace.
++++   129	
.oracle/checkins/batch-2-r3.md:6447: trailing whitespace.
++++   130	
.oracle/checkins/batch-2-r3.md:6449: trailing whitespace.
++++   135	
.oracle/checkins/batch-2-r3.md:6451: trailing whitespace.
++++   138	
.oracle/checkins/batch-2-r3.md:6453: trailing whitespace.
++++   149	
.oracle/checkins/batch-2-r3.md:6455: trailing whitespace.
++++   161	
.oracle/checkins/batch-2-r3.md:6457: trailing whitespace.
++++   162	
.oracle/checkins/batch-2-r3.md:6459: trailing whitespace.
++++   187	
.oracle/checkins/batch-2-r3.md:6461: trailing whitespace.
++++   205	
.oracle/checkins/batch-2-r3.md:6463: trailing whitespace.
++++   217	
.oracle/checkins/batch-2-r3.md:6465: trailing whitespace.
++++   218	
.oracle/checkins/batch-2-r3.md:6467: trailing whitespace.
++++   238	
.oracle/checkins/batch-2-r3.md:6469: trailing whitespace.
++++   247	
.oracle/checkins/batch-2-r3.md:6471: trailing whitespace.
++++   253	
.oracle/checkins/batch-2-r3.md:6473: trailing whitespace.
++++   254	
.oracle/checkins/batch-2-r3.md:6475: trailing whitespace.
++++   262	
.oracle/checkins/batch-2-r3.md:6477: trailing whitespace.
++++   265	
.oracle/checkins/batch-2-r3.md:6479: trailing whitespace.
++++   275	
.oracle/checkins/batch-2-r3.md:6481: trailing whitespace.
++++   123	
.oracle/checkins/batch-2-r3.md:6483: trailing whitespace.
++++   125	
.oracle/checkins/batch-2-r3.md:6485: trailing whitespace.
++++   126	
.oracle/checkins/batch-2-r3.md:6487: trailing whitespace.
++++   129	
.oracle/checkins/batch-2-r3.md:6489: trailing whitespace.
++++   139	
.oracle/checkins/batch-2-r3.md:6491: trailing whitespace.
++++   142	
.oracle/checkins/batch-2-r3.md:6493: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r3.md:6495: trailing whitespace.
++++   155	
.oracle/checkins/batch-2-r3.md:6497: trailing whitespace.
++++   161	
.oracle/checkins/batch-2-r3.md:6499: trailing whitespace.
++++   162	
.oracle/checkins/batch-2-r3.md:6501: trailing whitespace.
++++   165	
.oracle/checkins/batch-2-r3.md:6503: trailing whitespace.
++++   168	
.oracle/checkins/batch-2-r3.md:6505: trailing whitespace.
++++   177	
.oracle/checkins/batch-2-r3.md:6507: trailing whitespace.
++++   178	
.oracle/checkins/batch-2-r3.md:6509: trailing whitespace.
++++   181	
.oracle/checkins/batch-2-r3.md:6511: trailing whitespace.
++++   188	
.oracle/checkins/batch-2-r3.md:6513: trailing whitespace.
++++   194	
.oracle/checkins/batch-2-r3.md:6515: trailing whitespace.
++++   203	
.oracle/checkins/batch-2-r3.md:6517: trailing whitespace.
++++   204	
.oracle/checkins/batch-2-r3.md:6519: trailing whitespace.
++++   208	
.oracle/checkins/batch-2-r3.md:6521: trailing whitespace.
++++   211	
.oracle/checkins/batch-2-r3.md:6523: trailing whitespace.
++++   212	
.oracle/checkins/batch-2-r3.md:6525: trailing whitespace.
++++   216	
.oracle/checkins/batch-2-r3.md:6527: trailing whitespace.
++++   219	
.oracle/checkins/batch-2-r3.md:6529: trailing whitespace.
++++   220	
.oracle/checkins/batch-2-r3.md:6531: trailing whitespace.
++++   224	
.oracle/checkins/batch-2-r3.md:6533: trailing whitespace.
++++   227	
.oracle/checkins/batch-2-r3.md:6535: trailing whitespace.
++++   231	
.oracle/checkins/batch-2-r3.md:6537: trailing whitespace.
++++   232	
.oracle/checkins/batch-2-r3.md:6539: trailing whitespace.
++++   436	
.oracle/checkins/batch-2-r3.md:6541: trailing whitespace.
++++   437	
.oracle/checkins/batch-2-r3.md:6543: trailing whitespace.
++++   450	
.oracle/checkins/batch-2-r3.md:6545: trailing whitespace.
++++   451	
.oracle/checkins/batch-2-r3.md:6547: trailing whitespace.
++++   456	
.oracle/checkins/batch-2-r3.md:6549: trailing whitespace.
++++   464	
.oracle/checkins/batch-2-r3.md:6551: trailing whitespace.
++++   467	
.oracle/checkins/batch-2-r3.md:6553: trailing whitespace.
++++   471	
.oracle/checkins/batch-2-r3.md:6555: trailing whitespace.
++++   484	
.oracle/checkins/batch-2-r3.md:6557: trailing whitespace.
++++   487	
.oracle/checkins/batch-2-r3.md:6559: trailing whitespace.
++++   490	
.oracle/checkins/batch-2-r3.md:6561: trailing whitespace.
++++   491	
.oracle/checkins/batch-2-r3.md:6563: trailing whitespace.
++++   496	
.oracle/checkins/batch-2-r3.md:6565: trailing whitespace.
++++   506	
.oracle/checkins/batch-2-r3.md:6567: trailing whitespace.
++++   507	
.oracle/checkins/batch-2-r3.md:6569: trailing whitespace.
++++   514	
.oracle/checkins/batch-2-r3.md:6571: trailing whitespace.
++++   515	
.oracle/checkins/batch-2-r3.md:6573: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6575: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6577: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6579: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6581: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6583: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6585: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6587: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6589: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6591: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6593: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6595: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6597: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6599: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6601: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6603: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6605: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6607: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6609: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6611: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6613: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6615: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6617: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6619: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6621: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6623: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6625: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6627: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6629: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6631: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6633: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6635: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6637: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6639: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6641: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6643: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6645: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6647: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6649: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6651: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6653: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6655: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6657: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6659: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6661: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6663: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6665: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6667: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6669: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6671: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6673: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6675: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6677: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6679: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6681: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6683: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6685: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6687: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6689: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6691: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6693: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6695: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6697: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6699: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6701: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6703: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6705: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6707: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6709: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6711: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6713: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6715: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6717: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6719: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6721: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6723: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6725: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6727: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6729: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6731: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6733: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6735: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6737: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6739: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6741: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6743: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6745: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6747: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6749: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6751: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6753: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6755: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6757: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6759: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6761: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6763: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6765: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6767: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6769: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6771: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6773: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6775: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6777: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6779: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6781: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6783: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6785: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6787: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6789: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6791: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6793: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6795: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6797: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6799: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6801: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6803: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6805: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6807: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6809: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6811: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6813: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6815: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6817: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6819: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6821: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6823: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6825: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6827: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6829: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6831: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6833: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6835: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6837: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6839: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6841: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6843: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6845: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6847: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6849: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6851: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6853: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6855: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6857: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6859: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6861: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6863: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6865: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6867: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6869: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6871: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6873: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6875: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6877: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6879: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6881: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6883: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6885: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6887: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6889: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6891: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6893: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6895: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6897: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6899: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6901: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6903: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6905: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6907: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6909: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6911: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6913: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6915: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6917: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6919: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6921: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6923: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6925: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6927: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6929: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6931: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6933: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6935: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6937: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6939: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6941: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6943: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6945: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6947: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6949: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6951: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6953: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6955: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6957: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6959: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6961: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6963: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6965: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6967: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6969: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6971: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6973: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6975: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:6977: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r3.md:6979: trailing whitespace.
+++     6	
.oracle/checkins/batch-2-r3.md:6981: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r3.md:6983: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r3.md:6985: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r3.md:6987: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r3.md:6989: trailing whitespace.
+++    38	
.oracle/checkins/batch-2-r3.md:6991: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r3.md:6993: trailing whitespace.
+++    69	
.oracle/checkins/batch-2-r3.md:6995: trailing whitespace.
+++    70	
.oracle/checkins/batch-2-r3.md:6997: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r3.md:6999: trailing whitespace.
+++    79	
.oracle/checkins/batch-2-r3.md:7001: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r3.md:7003: trailing whitespace.
+++   113	
.oracle/checkins/batch-2-r3.md:7005: trailing whitespace.
+++   120	
.oracle/checkins/batch-2-r3.md:7007: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r3.md:7009: trailing whitespace.
+++   144	
.oracle/checkins/batch-2-r3.md:7011: trailing whitespace.
+++   160	
.oracle/checkins/batch-2-r3.md:7013: trailing whitespace.
+++   171	
.oracle/checkins/batch-2-r3.md:7015: trailing whitespace.
+++   202	
.oracle/checkins/batch-2-r3.md:7017: trailing whitespace.
+++   246	
.oracle/checkins/batch-2-r3.md:7019: trailing whitespace.
+++   250	
.oracle/checkins/batch-2-r3.md:7021: trailing whitespace.
+++   257	
.oracle/checkins/batch-2-r3.md:7023: trailing whitespace.
+++   427	
.oracle/checkins/batch-2-r3.md:7025: trailing whitespace.
+++   428	
.oracle/checkins/batch-2-r3.md:7027: trailing whitespace.
+++   445	
.oracle/checkins/batch-2-r3.md:7029: trailing whitespace.
+++   446	
.oracle/checkins/batch-2-r3.md:7031: trailing whitespace.
+++   459	
.oracle/checkins/batch-2-r3.md:7033: trailing whitespace.
+++   460	
.oracle/checkins/batch-2-r3.md:7035: trailing whitespace.
+++   465	
.oracle/checkins/batch-2-r3.md:7037: trailing whitespace.
+++   479	
.oracle/checkins/batch-2-r3.md:7039: trailing whitespace.
+++   482	
.oracle/checkins/batch-2-r3.md:7041: trailing whitespace.
+++   486	
.oracle/checkins/batch-2-r3.md:7043: trailing whitespace.
+++   499	
.oracle/checkins/batch-2-r3.md:7045: trailing whitespace.
+++   502	
.oracle/checkins/batch-2-r3.md:7047: trailing whitespace.
+++   505	
.oracle/checkins/batch-2-r3.md:7049: trailing whitespace.
+++   506	
.oracle/checkins/batch-2-r3.md:7051: trailing whitespace.
+++   511	
.oracle/checkins/batch-2-r3.md:7053: trailing whitespace.
+++   521	
.oracle/checkins/batch-2-r3.md:7055: trailing whitespace.
+++   522	
.oracle/checkins/batch-2-r3.md:7057: trailing whitespace.
+++   529	
.oracle/checkins/batch-2-r3.md:7059: trailing whitespace.
+++   530	
.oracle/checkins/batch-2-r3.md:7061: trailing whitespace.
+++   541	
.oracle/checkins/batch-2-r3.md:7063: trailing whitespace.
+++   542	
.oracle/checkins/batch-2-r3.md:7065: trailing whitespace.
+++   561	
.oracle/checkins/batch-2-r3.md:7067: trailing whitespace.
+++   562	
.oracle/checkins/batch-2-r3.md:7069: trailing whitespace.
+++   573	
.oracle/checkins/batch-2-r3.md:7071: trailing whitespace.
+++   574	
.oracle/checkins/batch-2-r3.md:7073: trailing whitespace.
+++   627	
.oracle/checkins/batch-2-r3.md:7075: trailing whitespace.
+++   628	
.oracle/checkins/batch-2-r3.md:7077: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7079: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7081: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7083: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7085: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7087: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7089: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7091: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7093: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7095: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7097: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7099: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7101: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7103: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7105: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7107: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7109: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7111: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7113: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7115: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7117: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r3.md:7119: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r3.md:7121: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r3.md:7123: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r3.md:7125: trailing whitespace.
+++    18	
.oracle/checkins/batch-2-r3.md:7127: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r3.md:7129: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r3.md:7131: trailing whitespace.
+++    28	
.oracle/checkins/batch-2-r3.md:7133: trailing whitespace.
+++    31	
.oracle/checkins/batch-2-r3.md:7135: trailing whitespace.
+++    32	
.oracle/checkins/batch-2-r3.md:7137: trailing whitespace.
+++    36	
.oracle/checkins/batch-2-r3.md:7139: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r3.md:7141: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r3.md:7143: trailing whitespace.
+++    44	
.oracle/checkins/batch-2-r3.md:7145: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r3.md:7147: trailing whitespace.
+++    66	
.oracle/checkins/batch-2-r3.md:7149: trailing whitespace.
+++    69	
.oracle/checkins/batch-2-r3.md:7151: trailing whitespace.
+++    72	
.oracle/checkins/batch-2-r3.md:7153: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r3.md:7155: trailing whitespace.
+++    76	
.oracle/checkins/batch-2-r3.md:7157: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r3.md:7159: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r3.md:7161: trailing whitespace.
+++    85	
.oracle/checkins/batch-2-r3.md:7163: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r3.md:7165: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r3.md:7167: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r3.md:7169: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r3.md:7171: trailing whitespace.
+++    99	
.oracle/checkins/batch-2-r3.md:7173: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r3.md:7175: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r3.md:7177: trailing whitespace.
+++   133	
.oracle/checkins/batch-2-r3.md:7179: trailing whitespace.
+++   138	
.oracle/checkins/batch-2-r3.md:7181: trailing whitespace.
+++   173	
.oracle/checkins/batch-2-r3.md:7183: trailing whitespace.
+++   174	
.oracle/checkins/batch-2-r3.md:7185: trailing whitespace.
+++   181	
.oracle/checkins/batch-2-r3.md:7187: trailing whitespace.
+++   183	
.oracle/checkins/batch-2-r3.md:7189: trailing whitespace.
+++   184	
.oracle/checkins/batch-2-r3.md:7191: trailing whitespace.
+++   200	
.oracle/checkins/batch-2-r3.md:7193: trailing whitespace.
+++   201	
.oracle/checkins/batch-2-r3.md:7195: trailing whitespace.
+++   231	
.oracle/checkins/batch-2-r3.md:7197: trailing whitespace.
+++   257	
.oracle/checkins/batch-2-r3.md:7199: trailing whitespace.
+++   258	
.oracle/checkins/batch-2-r3.md:7201: trailing whitespace.
+++   268	
.oracle/checkins/batch-2-r3.md:7203: trailing whitespace.
+++   275	
.oracle/checkins/batch-2-r3.md:7205: trailing whitespace.
+++   278	
.oracle/checkins/batch-2-r3.md:7207: trailing whitespace.
+++   292	
.oracle/checkins/batch-2-r3.md:7209: trailing whitespace.
+++   299	
.oracle/checkins/batch-2-r3.md:7211: trailing whitespace.
+++   310	
.oracle/checkins/batch-2-r3.md:7213: trailing whitespace.
+++   318	
.oracle/checkins/batch-2-r3.md:7215: trailing whitespace.
+++   328	
.oracle/checkins/batch-2-r3.md:7217: trailing whitespace.
+++   329	
.oracle/checkins/batch-2-r3.md:7219: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r3.md:7221: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r3.md:7223: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r3.md:7225: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r3.md:7227: trailing whitespace.
+++    20	
.oracle/checkins/batch-2-r3.md:7229: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r3.md:7231: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r3.md:7233: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r3.md:7235: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r3.md:7237: trailing whitespace.
+++    47	
.oracle/checkins/batch-2-r3.md:7239: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r3.md:7241: trailing whitespace.
+++    64	
.oracle/checkins/batch-2-r3.md:7243: trailing whitespace.
+++    65	
.oracle/checkins/batch-2-r3.md:7245: trailing whitespace.
+++    75	
.oracle/checkins/batch-2-r3.md:7247: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r3.md:7249: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r3.md:7251: trailing whitespace.
+++    92	
.oracle/checkins/batch-2-r3.md:7253: trailing whitespace.
+++    96	
.oracle/checkins/batch-2-r3.md:7255: trailing whitespace.
+++   108	
.oracle/checkins/batch-2-r3.md:7257: trailing whitespace.
+++   114	
.oracle/checkins/batch-2-r3.md:7259: trailing whitespace.
+++   119	
.oracle/checkins/batch-2-r3.md:7261: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r3.md:7263: trailing whitespace.
+++   130	
.oracle/checkins/batch-2-r3.md:7265: trailing whitespace.
+++   135	
.oracle/checkins/batch-2-r3.md:7267: trailing whitespace.
+++   138	
.oracle/checkins/batch-2-r3.md:7269: trailing whitespace.
+++   149	
.oracle/checkins/batch-2-r3.md:7271: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r3.md:7273: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r3.md:7275: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r3.md:7277: trailing whitespace.
+++   205	
.oracle/checkins/batch-2-r3.md:7279: trailing whitespace.
+++   217	
.oracle/checkins/batch-2-r3.md:7281: trailing whitespace.
+++   218	
.oracle/checkins/batch-2-r3.md:7283: trailing whitespace.
+++   238	
.oracle/checkins/batch-2-r3.md:7285: trailing whitespace.
+++   247	
.oracle/checkins/batch-2-r3.md:7287: trailing whitespace.
+++   253	
.oracle/checkins/batch-2-r3.md:7289: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r3.md:7291: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r3.md:7293: trailing whitespace.
+++   265	
.oracle/checkins/batch-2-r3.md:7295: trailing whitespace.
+++   275	
.oracle/checkins/batch-2-r3.md:7297: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r3.md:7299: trailing whitespace.
+++   128	
.oracle/checkins/batch-2-r3.md:7301: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r3.md:7303: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r3.md:7305: trailing whitespace.
+++   139	
.oracle/checkins/batch-2-r3.md:7307: trailing whitespace.
+++   140	
.oracle/checkins/batch-2-r3.md:7309: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r3.md:7311: trailing whitespace.
+++   150	
.oracle/checkins/batch-2-r3.md:7313: trailing whitespace.
+++   151	
.oracle/checkins/batch-2-r3.md:7315: trailing whitespace.
+++   158	
.oracle/checkins/batch-2-r3.md:7317: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r3.md:7319: trailing whitespace.
+++   166	
.oracle/checkins/batch-2-r3.md:7321: trailing whitespace.
+++   176	
.oracle/checkins/batch-2-r3.md:7323: trailing whitespace.
+++   183	
.oracle/checkins/batch-2-r3.md:7325: trailing whitespace.
+++   184	
.oracle/checkins/batch-2-r3.md:7327: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r3.md:7329: trailing whitespace.
+++   195	
.oracle/checkins/batch-2-r3.md:7331: trailing whitespace.
+++   196	
.oracle/checkins/batch-2-r3.md:7333: trailing whitespace.
+++   221	
.oracle/checkins/batch-2-r3.md:7335: trailing whitespace.
+++   228	
.oracle/checkins/batch-2-r3.md:7337: trailing whitespace.
+++   229	
.oracle/checkins/batch-2-r3.md:7339: trailing whitespace.
+++   233	
.oracle/checkins/batch-2-r3.md:7341: trailing whitespace.
+++   240	
.oracle/checkins/batch-2-r3.md:7343: trailing whitespace.
+++   241	
.oracle/checkins/batch-2-r3.md:7345: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r3.md:7347: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r3.md:7349: trailing whitespace.
+++    15	
.oracle/checkins/batch-2-r3.md:7351: trailing whitespace.
+++    17	
.oracle/checkins/batch-2-r3.md:7353: trailing whitespace.
+++    27	
.oracle/checkins/batch-2-r3.md:7355: trailing whitespace.
+++    36	
.oracle/checkins/batch-2-r3.md:7357: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r3.md:7359: trailing whitespace.
+++    45	
.oracle/checkins/batch-2-r3.md:7361: trailing whitespace.
+++    46	
.oracle/checkins/batch-2-r3.md:7363: trailing whitespace.
+++    50	
.oracle/checkins/batch-2-r3.md:7365: trailing whitespace.
+++    51	
.oracle/checkins/batch-2-r3.md:7367: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r3.md:7369: trailing whitespace.
+++    57	
.oracle/checkins/batch-2-r3.md:7371: trailing whitespace.
+++    58	
.oracle/checkins/batch-2-r3.md:7373: trailing whitespace.
+++    80	
.oracle/checkins/batch-2-r3.md:7375: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r3.md:7377: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r3.md:7379: trailing whitespace.
+++    87	
.oracle/checkins/batch-2-r3.md:7381: trailing whitespace.
+++    95	
.oracle/checkins/batch-2-r3.md:7383: trailing whitespace.
+++   120	
.oracle/checkins/batch-2-r3.md:7385: trailing whitespace.
+++   121	
.oracle/checkins/batch-2-r3.md:7387: trailing whitespace.
+++   131	
.oracle/checkins/batch-2-r3.md:7389: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r3.md:7391: trailing whitespace.
+++   153	
.oracle/checkins/batch-2-r3.md:7393: trailing whitespace.
+++   154	
.oracle/checkins/batch-2-r3.md:7395: trailing whitespace.
+++   164	
.oracle/checkins/batch-2-r3.md:7397: trailing whitespace.
+++   170	
.oracle/checkins/batch-2-r3.md:7399: trailing whitespace.
+++   182	
.oracle/checkins/batch-2-r3.md:7401: trailing whitespace.
+++   183	
.oracle/checkins/batch-2-r3.md:7403: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r3.md:7405: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r3.md:7407: trailing whitespace.
+++   194	
.oracle/checkins/batch-2-r3.md:7409: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r3.md:7411: trailing whitespace.
+++   221	
.oracle/checkins/batch-2-r3.md:7413: trailing whitespace.
+++   231	
.oracle/checkins/batch-2-r3.md:7415: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r3.md:7417: trailing whitespace.
+++   249	
.oracle/checkins/batch-2-r3.md:7419: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r3.md:7421: trailing whitespace.
+++   256	
.oracle/checkins/batch-2-r3.md:7423: trailing whitespace.
+++   266	
.oracle/checkins/batch-2-r3.md:7425: trailing whitespace.
+++   267	
.oracle/checkins/batch-2-r3.md:7427: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r3.md:7429: trailing whitespace.
+++   272	
.oracle/checkins/batch-2-r3.md:7431: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r3.md:7433: trailing whitespace.
+++   279	
.oracle/checkins/batch-2-r3.md:7435: trailing whitespace.
+++   287	
.oracle/checkins/batch-2-r3.md:7437: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r3.md:7439: trailing whitespace.
+++   292	
.oracle/checkins/batch-2-r3.md:7441: trailing whitespace.
+++   301	
.oracle/checkins/batch-2-r3.md:7443: trailing whitespace.
+++   302	
.oracle/checkins/batch-2-r3.md:7445: trailing whitespace.
+++   311	
.oracle/checkins/batch-2-r3.md:7447: trailing whitespace.
+++   314	
.oracle/checkins/batch-2-r3.md:7449: trailing whitespace.
+++   315	
.oracle/checkins/batch-2-r3.md:7451: trailing whitespace.
+++   319	
.oracle/checkins/batch-2-r3.md:7453: trailing whitespace.
+++   320	
.oracle/checkins/batch-2-r3.md:7455: trailing whitespace.
+++   326	
.oracle/checkins/batch-2-r3.md:7457: trailing whitespace.
+++   340	
.oracle/checkins/batch-2-r3.md:7459: trailing whitespace.
+++   344	
.oracle/checkins/batch-2-r3.md:7461: trailing whitespace.
+++   347	
.oracle/checkins/batch-2-r3.md:7463: trailing whitespace.
+++   348	
.oracle/checkins/batch-2-r3.md:7465: trailing whitespace.
+++   354	
.oracle/checkins/batch-2-r3.md:7467: trailing whitespace.
+++   368	
.oracle/checkins/batch-2-r3.md:7469: trailing whitespace.
+++   372	
.oracle/checkins/batch-2-r3.md:7471: trailing whitespace.
+++   376	
.oracle/checkins/batch-2-r3.md:7473: trailing whitespace.
+++   380	
.oracle/checkins/batch-2-r3.md:7475: trailing whitespace.
+++   384	
.oracle/checkins/batch-2-r3.md:7477: trailing whitespace.
+++   385	
.oracle/checkins/batch-2-r3.md:7479: trailing whitespace.
+++   389	
.oracle/checkins/batch-2-r3.md:7481: trailing whitespace.
+++   390	
.oracle/checkins/batch-2-r3.md:7483: trailing whitespace.
+++   393	
.oracle/checkins/batch-2-r3.md:7485: trailing whitespace.
+++   394	
.oracle/checkins/batch-2-r3.md:7487: trailing whitespace.
+++   407	
.oracle/checkins/batch-2-r3.md:7489: trailing whitespace.
+++   408	
.oracle/checkins/batch-2-r3.md:7491: trailing whitespace.
+++   427	
.oracle/checkins/batch-2-r3.md:7493: trailing whitespace.
+++   428	
.oracle/checkins/batch-2-r3.md:7495: trailing whitespace.
+++   443	
.oracle/checkins/batch-2-r3.md:7497: trailing whitespace.
+++   444	
.oracle/checkins/batch-2-r3.md:7499: trailing whitespace.
+++   458	
.oracle/checkins/batch-2-r3.md:7501: trailing whitespace.
+++   467	
.oracle/checkins/batch-2-r3.md:7503: trailing whitespace.
+++   470	
.oracle/checkins/batch-2-r3.md:7505: trailing whitespace.
+++   522	
.oracle/checkins/batch-2-r3.md:7507: trailing whitespace.
+++   523	
.oracle/checkins/batch-2-r3.md:7509: trailing whitespace.
+++   533	
.oracle/checkins/batch-2-r3.md:7511: trailing whitespace.
+++   546	
.oracle/checkins/batch-2-r3.md:7513: trailing whitespace.
+++   568	
.oracle/checkins/batch-2-r3.md:7515: trailing whitespace.
+++   569	
.oracle/checkins/batch-2-r3.md:7517: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r3.md:7519: trailing whitespace.
+++     6	
.oracle/checkins/batch-2-r3.md:7521: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r3.md:7523: trailing whitespace.
+++    17	
.oracle/checkins/batch-2-r3.md:7525: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r3.md:7527: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r3.md:7529: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r3.md:7531: trailing whitespace.
+++    26	
.oracle/checkins/batch-2-r3.md:7533: trailing whitespace.
+++    27	
.oracle/checkins/batch-2-r3.md:7535: trailing whitespace.
+++    31	
.oracle/checkins/batch-2-r3.md:7537: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r3.md:7539: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r3.md:7541: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r3.md:7543: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r3.md:7545: trailing whitespace.
+++    63	
.oracle/checkins/batch-2-r3.md:7547: trailing whitespace.
+++    65	
.oracle/checkins/batch-2-r3.md:7549: trailing whitespace.
+++    69	
.oracle/checkins/batch-2-r3.md:7551: trailing whitespace.
+++    71	
.oracle/checkins/batch-2-r3.md:7553: trailing whitespace.
+++    79	
.oracle/checkins/batch-2-r3.md:7555: trailing whitespace.
+++    85	
.oracle/checkins/batch-2-r3.md:7557: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r3.md:7559: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r3.md:7561: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r3.md:7563: trailing whitespace.
+++    93	
.oracle/checkins/batch-2-r3.md:7565: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r3.md:7567: trailing whitespace.
+++   107	
.oracle/checkins/batch-2-r3.md:7569: trailing whitespace.
+++   118	
.oracle/checkins/batch-2-r3.md:7571: trailing whitespace.
+++   119	
.oracle/checkins/batch-2-r3.md:7573: trailing whitespace.
+++   124	
.oracle/checkins/batch-2-r3.md:7575: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r3.md:7577: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r3.md:7579: trailing whitespace.
+++   280	
.oracle/checkins/batch-2-r3.md:7581: trailing whitespace.
+++   281	
.oracle/checkins/batch-2-r3.md:7583: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r3.md:7585: trailing whitespace.
+++   293	
.oracle/checkins/batch-2-r3.md:7587: trailing whitespace.
+++   294	
.oracle/checkins/batch-2-r3.md:7589: trailing whitespace.
+++   301	
.oracle/checkins/batch-2-r3.md:7591: trailing whitespace.
+++   307	
.oracle/checkins/batch-2-r3.md:7593: trailing whitespace.
+++   309	
.oracle/checkins/batch-2-r3.md:7595: trailing whitespace.
+++   310	
.oracle/checkins/batch-2-r3.md:7597: trailing whitespace.
+++   314	
.oracle/checkins/batch-2-r3.md:7599: trailing whitespace.
+++   315	
.oracle/checkins/batch-2-r3.md:7601: trailing whitespace.
+++   323	
.oracle/checkins/batch-2-r3.md:7603: trailing whitespace.
+++   394	
.oracle/checkins/batch-2-r3.md:7605: trailing whitespace.
+++   395	
.oracle/checkins/batch-2-r3.md:7607: trailing whitespace.
+++   442	
.oracle/checkins/batch-2-r3.md:7609: trailing whitespace.
+++   458	
.oracle/checkins/batch-2-r3.md:7611: trailing whitespace.
+++   459	
.oracle/checkins/batch-2-r3.md:7613: trailing whitespace.
+++   480	
.oracle/checkins/batch-2-r3.md:7615: trailing whitespace.
+++   505	
.oracle/checkins/batch-2-r3.md:7617: trailing whitespace.
+++   506	
.oracle/checkins/batch-2-r3.md:7619: trailing whitespace.
+++   533	
.oracle/checkins/batch-2-r3.md:7621: trailing whitespace.
+++   534	
.oracle/checkins/batch-2-r3.md:7623: trailing whitespace.
+++   559	
.oracle/checkins/batch-2-r3.md:7625: trailing whitespace.
+++   560	
.oracle/checkins/batch-2-r3.md:7627: trailing whitespace.
+++   600	
.oracle/checkins/batch-2-r3.md:7629: trailing whitespace.
+++   601	
.oracle/checkins/batch-2-r3.md:7631: trailing whitespace.
+++   628	
.oracle/checkins/batch-2-r3.md:7633: trailing whitespace.
+++   629	
.oracle/checkins/batch-2-r3.md:7635: trailing whitespace.
+++   637	
.oracle/checkins/batch-2-r3.md:7637: trailing whitespace.
+++   643	
.oracle/checkins/batch-2-r3.md:7639: trailing whitespace.
+++   650	
.oracle/checkins/batch-2-r3.md:7641: trailing whitespace.
+++   669	
.oracle/checkins/batch-2-r3.md:7643: trailing whitespace.
+++   679	
.oracle/checkins/batch-2-r3.md:7645: trailing whitespace.
+++   700	
.oracle/checkins/batch-2-r3.md:7647: trailing whitespace.
+++   701	
.oracle/checkins/batch-2-r3.md:7649: trailing whitespace.
+++   250	
.oracle/checkins/batch-2-r3.md:7651: trailing whitespace.
+++   251	
.oracle/checkins/batch-2-r3.md:7653: trailing whitespace.
+++   259	
.oracle/checkins/batch-2-r3.md:7655: trailing whitespace.
+++   260	
.oracle/checkins/batch-2-r3.md:7657: trailing whitespace.
+++   272	
.oracle/checkins/batch-2-r3.md:7659: trailing whitespace.
+++   273	
.oracle/checkins/batch-2-r3.md:7661: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r3.md:7663: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r3.md:7665: trailing whitespace.
+++   296	
.oracle/checkins/batch-2-r3.md:7667: trailing whitespace.
+++   297	
.oracle/checkins/batch-2-r3.md:7669: trailing whitespace.
+++   335	
.oracle/checkins/batch-2-r3.md:7671: trailing whitespace.
+++   362	
.oracle/checkins/batch-2-r3.md:7673: trailing whitespace.
+++   363	
.oracle/checkins/batch-2-r3.md:7675: trailing whitespace.
+++   246	
.oracle/checkins/batch-2-r3.md:7677: trailing whitespace.
+++   250	
.oracle/checkins/batch-2-r3.md:7679: trailing whitespace.
+++   257	
.oracle/checkins/batch-2-r3.md:7681: trailing whitespace.
+++   269	
.oracle/checkins/batch-2-r3.md:7683: trailing whitespace.
+++   270	
.oracle/checkins/batch-2-r3.md:7685: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r3.md:7687: trailing whitespace.
+++   278	
.oracle/checkins/batch-2-r3.md:7689: trailing whitespace.
+++   294	
.oracle/checkins/batch-2-r3.md:7691: trailing whitespace.
+++   295	
.oracle/checkins/batch-2-r3.md:7693: trailing whitespace.
+++   326	
.oracle/checkins/batch-2-r3.md:7695: trailing whitespace.
+++   327	
.oracle/checkins/batch-2-r3.md:7697: trailing whitespace.
+++   344	
.oracle/checkins/batch-2-r3.md:7699: trailing whitespace.
+++   345	
.oracle/checkins/batch-2-r3.md:7701: trailing whitespace.
+++   348	
.oracle/checkins/batch-2-r3.md:7703: trailing whitespace.
+++   349	
.oracle/checkins/batch-2-r3.md:7705: trailing whitespace.
+++   355	
.oracle/checkins/batch-2-r3.md:7707: trailing whitespace.
+++   356	
.oracle/checkins/batch-2-r3.md:7709: trailing whitespace.
+++   392	
.oracle/checkins/batch-2-r3.md:7711: trailing whitespace.
+++   401	
.oracle/checkins/batch-2-r3.md:7713: trailing whitespace.
+++   402	
.oracle/checkins/batch-2-r3.md:7715: trailing whitespace.
+++   409	
.oracle/checkins/batch-2-r3.md:7717: trailing whitespace.
+++   410	
.oracle/checkins/batch-2-r3.md:7719: trailing whitespace.
+++   427	
.oracle/checkins/batch-2-r3.md:7721: trailing whitespace.
+++   428	
.oracle/checkins/batch-2-r3.md:7723: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r3.md:7725: trailing whitespace.
+++    11	
.oracle/checkins/batch-2-r3.md:7727: trailing whitespace.
+++    13	
.oracle/checkins/batch-2-r3.md:7729: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r3.md:7731: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r3.md:7733: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r3.md:7735: trailing whitespace.
+++    30	
.oracle/checkins/batch-2-r3.md:7737: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r3.md:7739: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r3.md:7741: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r3.md:7743: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r3.md:7745: trailing whitespace.
+++    63	
.oracle/checkins/batch-2-r3.md:7747: trailing whitespace.
+++    64	
.oracle/checkins/batch-2-r3.md:7749: trailing whitespace.
+++    74	
.oracle/checkins/batch-2-r3.md:7751: trailing whitespace.
+++    75	
.oracle/checkins/batch-2-r3.md:7753: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r3.md:7755: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r3.md:7757: trailing whitespace.
+++    96	
.oracle/checkins/batch-2-r3.md:7759: trailing whitespace.
+++   100	
.oracle/checkins/batch-2-r3.md:7761: trailing whitespace.
+++   101	
.oracle/checkins/batch-2-r3.md:7763: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r3.md:7765: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r3.md:7767: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r3.md:7769: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r3.md:7771: trailing whitespace.
+++   139	
.oracle/checkins/batch-2-r3.md:7773: trailing whitespace.
+++   142	
.oracle/checkins/batch-2-r3.md:7775: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r3.md:7777: trailing whitespace.
+++   155	
.oracle/checkins/batch-2-r3.md:7779: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r3.md:7781: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r3.md:7783: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r3.md:7785: trailing whitespace.
+++   168	
.oracle/checkins/batch-2-r3.md:7787: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r3.md:7789: trailing whitespace.
+++   178	
.oracle/checkins/batch-2-r3.md:7791: trailing whitespace.
+++   181	
.oracle/checkins/batch-2-r3.md:7793: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r3.md:7795: trailing whitespace.
+++   194	
.oracle/checkins/batch-2-r3.md:7797: trailing whitespace.
+++   203	
.oracle/checkins/batch-2-r3.md:7799: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r3.md:7801: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r3.md:7803: trailing whitespace.
+++   211	
.oracle/checkins/batch-2-r3.md:7805: trailing whitespace.
+++   212	
.oracle/checkins/batch-2-r3.md:7807: trailing whitespace.
+++   216	
.oracle/checkins/batch-2-r3.md:7809: trailing whitespace.
+++   219	
.oracle/checkins/batch-2-r3.md:7811: trailing whitespace.
+++   220	
.oracle/checkins/batch-2-r3.md:7813: trailing whitespace.
+++   224	
.oracle/checkins/batch-2-r3.md:7815: trailing whitespace.
+++   227	
.oracle/checkins/batch-2-r3.md:7817: trailing whitespace.
+++   231	
.oracle/checkins/batch-2-r3.md:7819: trailing whitespace.
+++   232	
.oracle/checkins/batch-2-r3.md:7821: trailing whitespace.
+++   239	
.oracle/checkins/batch-2-r3.md:7823: trailing whitespace.
+++   249	
.oracle/checkins/batch-2-r3.md:7825: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r3.md:7827: trailing whitespace.
+++   255	
.oracle/checkins/batch-2-r3.md:7829: trailing whitespace.
+++   261	
.oracle/checkins/batch-2-r3.md:7831: trailing whitespace.
+++   275	
.oracle/checkins/batch-2-r3.md:7833: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r3.md:7835: trailing whitespace.
+++   140	
.oracle/checkins/batch-2-r3.md:7837: trailing whitespace.
+++   142	
.oracle/checkins/batch-2-r3.md:7839: trailing whitespace.
+++   147	
.oracle/checkins/batch-2-r3.md:7841: trailing whitespace.
+++   149	
.oracle/checkins/batch-2-r3.md:7843: trailing whitespace.
+++   153	
.oracle/checkins/batch-2-r3.md:7845: trailing whitespace.
+++   163	
.oracle/checkins/batch-2-r3.md:7847: trailing whitespace.
+++   170	
.oracle/checkins/batch-2-r3.md:7849: trailing whitespace.
+++   172	
.oracle/checkins/batch-2-r3.md:7851: trailing whitespace.
+++   175	
.oracle/checkins/batch-2-r3.md:7853: trailing whitespace.
+++   184	
.oracle/checkins/batch-2-r3.md:7855: trailing whitespace.
+++   189	
.oracle/checkins/batch-2-r3.md:7857: trailing whitespace.
+++   191	
.oracle/checkins/batch-2-r3.md:7859: trailing whitespace.
+++   193	
.oracle/checkins/batch-2-r3.md:7861: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r3.md:7863: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r3.md:7865: trailing whitespace.
+++   217	
.oracle/checkins/batch-2-r3.md:7867: trailing whitespace.
+++   223	
.oracle/checkins/batch-2-r3.md:7869: trailing whitespace.
+++   225	
.oracle/checkins/batch-2-r3.md:7871: trailing whitespace.
+++   230	
.oracle/checkins/batch-2-r3.md:7873: trailing whitespace.
+++   238	
.oracle/checkins/batch-2-r3.md:7875: trailing whitespace.
+++   240	
.oracle/checkins/batch-2-r3.md:7877: trailing whitespace.
+++   243	
.oracle/checkins/batch-2-r3.md:7879: trailing whitespace.
+++   251	
.oracle/checkins/batch-2-r3.md:7881: trailing whitespace.
+++   255	
.oracle/checkins/batch-2-r3.md:7883: trailing whitespace.
+++   257	
.oracle/checkins/batch-2-r3.md:7885: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r3.md:7887: trailing whitespace.
+++   408	
.oracle/checkins/batch-2-r3.md:7889: trailing whitespace.
+++   410	
.oracle/checkins/batch-2-r3.md:7891: trailing whitespace.
+++   412	
.oracle/checkins/batch-2-r3.md:7893: trailing whitespace.
+++   421	
.oracle/checkins/batch-2-r3.md:7895: trailing whitespace.
+++   430	
.oracle/checkins/batch-2-r3.md:7897: trailing whitespace.
+++   434	
.oracle/checkins/batch-2-r3.md:7899: trailing whitespace.
+++   436	
.oracle/checkins/batch-2-r3.md:7901: trailing whitespace.
+++   438	
.oracle/checkins/batch-2-r3.md:7903: trailing whitespace.
+++   453	
.oracle/checkins/batch-2-r3.md:7905: trailing whitespace.
+++   461	
.oracle/checkins/batch-2-r3.md:7907: trailing whitespace.
+++   463	
.oracle/checkins/batch-2-r3.md:7909: trailing whitespace.
+++   465	
.oracle/checkins/batch-2-r3.md:7911: trailing whitespace.
+++   470	
.oracle/checkins/batch-2-r3.md:7913: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r3.md:7915: trailing whitespace.
+++   289	
.oracle/checkins/batch-2-r3.md:7917: trailing whitespace.
+++   312	
.oracle/checkins/batch-2-r3.md:7919: trailing whitespace.
+++   313	
.oracle/checkins/batch-2-r3.md:7921: trailing whitespace.
+++   334	
.oracle/checkins/batch-2-r3.md:7923: trailing whitespace.
+++   335	
.oracle/checkins/batch-2-r3.md:7925: trailing whitespace.
+++   346	
.oracle/checkins/batch-2-r3.md:7927: trailing whitespace.
+++   347	
.oracle/checkins/batch-2-r3.md:7929: trailing whitespace.
+++   357	
.oracle/checkins/batch-2-r3.md:7931: trailing whitespace.
+++   358	
.oracle/checkins/batch-2-r3.md:7933: trailing whitespace.
+++   370	
.oracle/checkins/batch-2-r3.md:7935: trailing whitespace.
+++   371	
.oracle/checkins/batch-2-r3.md:7937: trailing whitespace.
+++   375	
.oracle/checkins/batch-2-r3.md:7939: trailing whitespace.
+++   382	
.oracle/checkins/batch-2-r3.md:7941: trailing whitespace.
+++   383	
.oracle/checkins/batch-2-r3.md:7943: trailing whitespace.
+++   387	
.oracle/checkins/batch-2-r3.md:7945: trailing whitespace.
+++   394	
.oracle/checkins/batch-2-r3.md:7947: trailing whitespace.
+++   395	
.oracle/checkins/batch-2-r3.md:7949: trailing whitespace.
+++   399	
.oracle/checkins/batch-2-r3.md:7951: trailing whitespace.
+++   406	
.oracle/checkins/batch-2-r3.md:7953: trailing whitespace.
+++   407	
.oracle/checkins/batch-2-r3.md:7955: trailing whitespace.
+++   411	
.oracle/checkins/batch-2-r3.md:7957: trailing whitespace.
+++  1443	
.oracle/checkins/batch-2-r3.md:7959: trailing whitespace.
+++  1444	
.oracle/checkins/batch-2-r3.md:7961: trailing whitespace.
+++  1458	
.oracle/checkins/batch-2-r3.md:7963: trailing whitespace.
+++  1479	
.oracle/checkins/batch-2-r3.md:7965: trailing whitespace.
+++  1480	
.oracle/checkins/batch-2-r3.md:7967: trailing whitespace.
+++  1537	
.oracle/checkins/batch-2-r3.md:7969: trailing whitespace.
+++  1538	
.oracle/checkins/batch-2-r3.md:7971: trailing whitespace.
+++   394	
.oracle/checkins/batch-2-r3.md:7973: trailing whitespace.
+++   395	
.oracle/checkins/batch-2-r3.md:7975: trailing whitespace.
+++   286	
.oracle/checkins/batch-2-r3.md:7977: trailing whitespace.
+++   287	
.oracle/checkins/batch-2-r3.md:7979: trailing whitespace.
+++   303	
.oracle/checkins/batch-2-r3.md:7981: trailing whitespace.
+++   304	
.oracle/checkins/batch-2-r3.md:7983: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:7985: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:7987: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r3.md:7989: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r3.md:7991: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r3.md:7993: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r3.md:7995: trailing whitespace.
++   395	
.oracle/checkins/batch-2-r3.md:7997: trailing whitespace.
++   286	
.oracle/checkins/batch-2-r3.md:7999: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r3.md:8001: trailing whitespace.
++   303	
.oracle/checkins/batch-2-r3.md:8003: trailing whitespace.
++   304	
.oracle/checkins/batch-2-r3.md:8005: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8007: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8009: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8011: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8013: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8015: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8017: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8019: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8021: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8023: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8025: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8027: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8029: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8031: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8033: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8035: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8037: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8039: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8041: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8043: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8045: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8047: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8049: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8051: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8053: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8055: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8057: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8059: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8061: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8063: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8065: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8067: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8069: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8071: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8073: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8075: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8077: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8079: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8081: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8083: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8085: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8087: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8089: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8091: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8093: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8095: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8097: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8099: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8101: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8103: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8105: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8107: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8109: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8111: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8113: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8115: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8117: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8119: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8121: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8123: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8125: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8127: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8129: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8131: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8133: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8135: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8137: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8139: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8141: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8143: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8145: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8147: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8149: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8151: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8153: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8155: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8157: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8159: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8161: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8163: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8165: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8167: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8169: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8171: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8173: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8175: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8177: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8179: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8181: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8183: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8185: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8187: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8189: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8191: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8193: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8195: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8197: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8199: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8201: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8203: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8205: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8207: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8209: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8211: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8213: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8215: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8217: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8219: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8221: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8223: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8225: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8227: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8229: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8231: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8233: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8235: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8237: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8239: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8241: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8243: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8245: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8247: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8249: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8251: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8253: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8255: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8257: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8259: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8261: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8263: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8265: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8267: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8269: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8271: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8273: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8275: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8277: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8279: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8281: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8283: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8285: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8287: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8289: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8291: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8293: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8295: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8297: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8299: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8301: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8303: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8305: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8307: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8309: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8311: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8313: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8315: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8317: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8319: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8321: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8323: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8325: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8327: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8329: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8331: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8333: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8335: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8337: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8339: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8341: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8343: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8345: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8347: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8349: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8351: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8353: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8355: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8357: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8359: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8361: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8363: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8365: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8367: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8369: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8371: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8373: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:8375: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r3.md:8377: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r3.md:8379: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r3.md:8381: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r3.md:8383: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r3.md:8385: trailing whitespace.
++    38	
.oracle/checkins/batch-2-r3.md:8387: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r3.md:8389: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r3.md:8391: trailing whitespace.
++    70	
.oracle/checkins/batch-2-r3.md:8393: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r3.md:8395: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r3.md:8397: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r3.md:8399: trailing whitespace.
++   113	
.oracle/checkins/batch-2-r3.md:8401: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r3.md:8403: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r3.md:8405: trailing whitespace.
++   144	
.oracle/checkins/batch-2-r3.md:8407: trailing whitespace.
++   160	
.oracle/checkins/batch-2-r3.md:8409: trailing whitespace.
++   171	
.oracle/checkins/batch-2-r3.md:8411: trailing whitespace.
++   202	
.oracle/checkins/batch-2-r3.md:8413: trailing whitespace.
++   246	
.oracle/checkins/batch-2-r3.md:8415: trailing whitespace.
++   250	
.oracle/checkins/batch-2-r3.md:8417: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r3.md:8419: trailing whitespace.
++   269	
.oracle/checkins/batch-2-r3.md:8421: trailing whitespace.
++   270	
.oracle/checkins/batch-2-r3.md:8423: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r3.md:8425: trailing whitespace.
++   278	
.oracle/checkins/batch-2-r3.md:8427: trailing whitespace.
++   294	
.oracle/checkins/batch-2-r3.md:8429: trailing whitespace.
++   295	
.oracle/checkins/batch-2-r3.md:8431: trailing whitespace.
++   401	
.oracle/checkins/batch-2-r3.md:8433: trailing whitespace.
++   402	
.oracle/checkins/batch-2-r3.md:8435: trailing whitespace.
++   409	
.oracle/checkins/batch-2-r3.md:8437: trailing whitespace.
++   410	
.oracle/checkins/batch-2-r3.md:8439: trailing whitespace.
++   427	
.oracle/checkins/batch-2-r3.md:8441: trailing whitespace.
++   428	
.oracle/checkins/batch-2-r3.md:8443: trailing whitespace.
++   445	
.oracle/checkins/batch-2-r3.md:8445: trailing whitespace.
++   446	
.oracle/checkins/batch-2-r3.md:8447: trailing whitespace.
++   459	
.oracle/checkins/batch-2-r3.md:8449: trailing whitespace.
++   460	
.oracle/checkins/batch-2-r3.md:8451: trailing whitespace.
++   465	
.oracle/checkins/batch-2-r3.md:8453: trailing whitespace.
++   479	
.oracle/checkins/batch-2-r3.md:8455: trailing whitespace.
++   482	
.oracle/checkins/batch-2-r3.md:8457: trailing whitespace.
++   486	
.oracle/checkins/batch-2-r3.md:8459: trailing whitespace.
++   507	
.oracle/checkins/batch-2-r3.md:8461: trailing whitespace.
++   510	
.oracle/checkins/batch-2-r3.md:8463: trailing whitespace.
++   513	
.oracle/checkins/batch-2-r3.md:8465: trailing whitespace.
++   514	
.oracle/checkins/batch-2-r3.md:8467: trailing whitespace.
++   519	
.oracle/checkins/batch-2-r3.md:8469: trailing whitespace.
++   529	
.oracle/checkins/batch-2-r3.md:8471: trailing whitespace.
++   530	
.oracle/checkins/batch-2-r3.md:8473: trailing whitespace.
++   546	
.oracle/checkins/batch-2-r3.md:8475: trailing whitespace.
++   547	
.oracle/checkins/batch-2-r3.md:8477: trailing whitespace.
++   558	
.oracle/checkins/batch-2-r3.md:8479: trailing whitespace.
++   559	
.oracle/checkins/batch-2-r3.md:8481: trailing whitespace.
++   578	
.oracle/checkins/batch-2-r3.md:8483: trailing whitespace.
++   579	
.oracle/checkins/batch-2-r3.md:8485: trailing whitespace.
++   590	
.oracle/checkins/batch-2-r3.md:8487: trailing whitespace.
++   591	
.oracle/checkins/batch-2-r3.md:8489: trailing whitespace.
++   644	
.oracle/checkins/batch-2-r3.md:8491: trailing whitespace.
++   645	
.oracle/checkins/batch-2-r3.md:8493: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:8495: trailing whitespace.
++    11	
.oracle/checkins/batch-2-r3.md:8497: trailing whitespace.
++    13	
.oracle/checkins/batch-2-r3.md:8499: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r3.md:8501: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r3.md:8503: trailing whitespace.
++    29	
.oracle/checkins/batch-2-r3.md:8505: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r3.md:8507: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r3.md:8509: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r3.md:8511: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r3.md:8513: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r3.md:8515: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r3.md:8517: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r3.md:8519: trailing whitespace.
++    74	
.oracle/checkins/batch-2-r3.md:8521: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r3.md:8523: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r3.md:8525: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r3.md:8527: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r3.md:8529: trailing whitespace.
++   100	
.oracle/checkins/batch-2-r3.md:8531: trailing whitespace.
++   101	
.oracle/checkins/batch-2-r3.md:8533: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r3.md:8535: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r3.md:8537: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r3.md:8539: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r3.md:8541: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r3.md:8543: trailing whitespace.
++   142	
.oracle/checkins/batch-2-r3.md:8545: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r3.md:8547: trailing whitespace.
++   155	
.oracle/checkins/batch-2-r3.md:8549: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r3.md:8551: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r3.md:8553: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r3.md:8555: trailing whitespace.
++   168	
.oracle/checkins/batch-2-r3.md:8557: trailing whitespace.
++   176	
.oracle/checkins/batch-2-r3.md:8559: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r3.md:8561: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r3.md:8563: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r3.md:8565: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r3.md:8567: trailing whitespace.
++   189	
.oracle/checkins/batch-2-r3.md:8569: trailing whitespace.
++   192	
.oracle/checkins/batch-2-r3.md:8571: trailing whitespace.
++   199	
.oracle/checkins/batch-2-r3.md:8573: trailing whitespace.
++   205	
.oracle/checkins/batch-2-r3.md:8575: trailing whitespace.
++   214	
.oracle/checkins/batch-2-r3.md:8577: trailing whitespace.
++   215	
.oracle/checkins/batch-2-r3.md:8579: trailing whitespace.
++   219	
.oracle/checkins/batch-2-r3.md:8581: trailing whitespace.
++   222	
.oracle/checkins/batch-2-r3.md:8583: trailing whitespace.
++   223	
.oracle/checkins/batch-2-r3.md:8585: trailing whitespace.
++   227	
.oracle/checkins/batch-2-r3.md:8587: trailing whitespace.
++   230	
.oracle/checkins/batch-2-r3.md:8589: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r3.md:8591: trailing whitespace.
++   235	
.oracle/checkins/batch-2-r3.md:8593: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r3.md:8595: trailing whitespace.
++   242	
.oracle/checkins/batch-2-r3.md:8597: trailing whitespace.
++   243	
.oracle/checkins/batch-2-r3.md:8599: trailing whitespace.
++   250	
.oracle/checkins/batch-2-r3.md:8601: trailing whitespace.
++   260	
.oracle/checkins/batch-2-r3.md:8603: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r3.md:8605: trailing whitespace.
++   266	
.oracle/checkins/batch-2-r3.md:8607: trailing whitespace.
++   272	
.oracle/checkins/batch-2-r3.md:8609: trailing whitespace.
++   286	
.oracle/checkins/batch-2-r3.md:8611: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8613: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8615: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8617: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8619: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8621: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8623: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8625: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8627: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8629: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8631: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8633: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8635: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8637: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8639: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8641: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8643: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8645: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8647: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8649: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8651: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8653: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8655: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8657: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8659: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8661: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8663: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8665: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8667: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8669: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8671: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8673: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8675: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8677: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8679: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8681: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8683: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8685: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:8687: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:8689: trailing whitespace.
++     4	
.oracle/checkins/batch-2-r3.md:8691: trailing whitespace.
++    13	
.oracle/checkins/batch-2-r3.md:8693: trailing whitespace.
++    14	
.oracle/checkins/batch-2-r3.md:8695: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r3.md:8697: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r3.md:8699: trailing whitespace.
++    26	
.oracle/checkins/batch-2-r3.md:8701: trailing whitespace.
++    32	
.oracle/checkins/batch-2-r3.md:8703: trailing whitespace.
++    35	
.oracle/checkins/batch-2-r3.md:8705: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r3.md:8707: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r3.md:8709: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r3.md:8711: trailing whitespace.
++    83	
.oracle/checkins/batch-2-r3.md:8713: trailing whitespace.
++   155	
.oracle/checkins/batch-2-r3.md:8715: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r3.md:8717: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r3.md:8719: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r3.md:8721: trailing whitespace.
++   168	
.oracle/checkins/batch-2-r3.md:8723: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r3.md:8725: trailing whitespace.
++   178	
.oracle/checkins/batch-2-r3.md:8727: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r3.md:8729: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r3.md:8731: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r3.md:8733: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r3.md:8735: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r3.md:8737: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r3.md:8739: trailing whitespace.
++   211	
.oracle/checkins/batch-2-r3.md:8741: trailing whitespace.
++   212	
.oracle/checkins/batch-2-r3.md:8743: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r3.md:8745: trailing whitespace.
++   219	
.oracle/checkins/batch-2-r3.md:8747: trailing whitespace.
++   220	
.oracle/checkins/batch-2-r3.md:8749: trailing whitespace.
++   224	
.oracle/checkins/batch-2-r3.md:8751: trailing whitespace.
++   445	
.oracle/checkins/batch-2-r3.md:8753: trailing whitespace.
++   446	
.oracle/checkins/batch-2-r3.md:8755: trailing whitespace.
++   459	
.oracle/checkins/batch-2-r3.md:8757: trailing whitespace.
++   460	
.oracle/checkins/batch-2-r3.md:8759: trailing whitespace.
++   465	
.oracle/checkins/batch-2-r3.md:8761: trailing whitespace.
++   479	
.oracle/checkins/batch-2-r3.md:8763: trailing whitespace.
++   482	
.oracle/checkins/batch-2-r3.md:8765: trailing whitespace.
++   486	
.oracle/checkins/batch-2-r3.md:8767: trailing whitespace.
++   499	
.oracle/checkins/batch-2-r3.md:8769: trailing whitespace.
++   502	
.oracle/checkins/batch-2-r3.md:8771: trailing whitespace.
++   505	
.oracle/checkins/batch-2-r3.md:8773: trailing whitespace.
++   506	
.oracle/checkins/batch-2-r3.md:8775: trailing whitespace.
++   511	
.oracle/checkins/batch-2-r3.md:8777: trailing whitespace.
++   521	
.oracle/checkins/batch-2-r3.md:8779: trailing whitespace.
++   522	
.oracle/checkins/batch-2-r3.md:8781: trailing whitespace.
++   529	
.oracle/checkins/batch-2-r3.md:8783: trailing whitespace.
++   530	
.oracle/checkins/batch-2-r3.md:8785: trailing whitespace.
++     3	
.oracle/checkins/batch-2-r3.md:8787: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r3.md:8789: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r3.md:8791: trailing whitespace.
++    14	
.oracle/checkins/batch-2-r3.md:8793: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r3.md:8795: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r3.md:8797: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r3.md:8799: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r3.md:8801: trailing whitespace.
++    49	
.oracle/checkins/batch-2-r3.md:8803: trailing whitespace.
++    53	
.oracle/checkins/batch-2-r3.md:8805: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r3.md:8807: trailing whitespace.
++    57	
.oracle/checkins/batch-2-r3.md:8809: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r3.md:8811: trailing whitespace.
++    62	
.oracle/checkins/batch-2-r3.md:8813: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r3.md:8815: trailing whitespace.
++    66	
.oracle/checkins/batch-2-r3.md:8817: trailing whitespace.
++    68	
.oracle/checkins/batch-2-r3.md:8819: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r3.md:8821: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r3.md:8823: trailing whitespace.
++    91	
.oracle/checkins/batch-2-r3.md:8825: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r3.md:8827: trailing whitespace.
++    99	
.oracle/checkins/batch-2-r3.md:8829: trailing whitespace.
++   100	
.oracle/checkins/batch-2-r3.md:8831: trailing whitespace.
++   104	
.oracle/checkins/batch-2-r3.md:8833: trailing whitespace.
++   105	
.oracle/checkins/batch-2-r3.md:8835: trailing whitespace.
++   117	
.oracle/checkins/batch-2-r3.md:8837: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r3.md:8839: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r3.md:8841: trailing whitespace.
++   144	
.oracle/checkins/batch-2-r3.md:8843: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r3.md:8845: trailing whitespace.
++   166	
.oracle/checkins/batch-2-r3.md:8847: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r3.md:8849: trailing whitespace.
++   190	
.oracle/checkins/batch-2-r3.md:8851: trailing whitespace.
++   191	
.oracle/checkins/batch-2-r3.md:8853: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r3.md:8855: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r3.md:8857: trailing whitespace.
++   199	
.oracle/checkins/batch-2-r3.md:8859: trailing whitespace.
++   200	
.oracle/checkins/batch-2-r3.md:8861: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r3.md:8863: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r3.md:8865: trailing whitespace.
++   207	
.oracle/checkins/batch-2-r3.md:8867: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r3.md:8869: trailing whitespace.
++   214	
.oracle/checkins/batch-2-r3.md:8871: trailing whitespace.
++   215	
.oracle/checkins/batch-2-r3.md:8873: trailing whitespace.
++   228	
.oracle/checkins/batch-2-r3.md:8875: trailing whitespace.
++   229	
.oracle/checkins/batch-2-r3.md:8877: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r3.md:8879: trailing whitespace.
++   245	
.oracle/checkins/batch-2-r3.md:8881: trailing whitespace.
++   252	
.oracle/checkins/batch-2-r3.md:8883: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r3.md:8885: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r3.md:8887: trailing whitespace.
++   258	
.oracle/checkins/batch-2-r3.md:8889: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r3.md:8891: trailing whitespace.
++   263	
.oracle/checkins/batch-2-r3.md:8893: trailing whitespace.
++   286	
.oracle/checkins/batch-2-r3.md:8895: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r3.md:8897: trailing whitespace.
++   311	
.oracle/checkins/batch-2-r3.md:8899: trailing whitespace.
++   312	
.oracle/checkins/batch-2-r3.md:8901: trailing whitespace.
++   334	
.oracle/checkins/batch-2-r3.md:8903: trailing whitespace.
++   344	
.oracle/checkins/batch-2-r3.md:8905: trailing whitespace.
++   348	
.oracle/checkins/batch-2-r3.md:8907: trailing whitespace.
++   349	
.oracle/checkins/batch-2-r3.md:8909: trailing whitespace.
++   360	
.oracle/checkins/batch-2-r3.md:8911: trailing whitespace.
++   363	
.oracle/checkins/batch-2-r3.md:8913: trailing whitespace.
++   367	
.oracle/checkins/batch-2-r3.md:8915: trailing whitespace.
++   376	
.oracle/checkins/batch-2-r3.md:8917: trailing whitespace.
++   380	
.oracle/checkins/batch-2-r3.md:8919: trailing whitespace.
++   384	
.oracle/checkins/batch-2-r3.md:8921: trailing whitespace.
++   388	
.oracle/checkins/batch-2-r3.md:8923: trailing whitespace.
++   392	
.oracle/checkins/batch-2-r3.md:8925: trailing whitespace.
++   393	
.oracle/checkins/batch-2-r3.md:8927: trailing whitespace.
++   397	
.oracle/checkins/batch-2-r3.md:8929: trailing whitespace.
++   398	
.oracle/checkins/batch-2-r3.md:8931: trailing whitespace.
++   401	
.oracle/checkins/batch-2-r3.md:8933: trailing whitespace.
++   402	
.oracle/checkins/batch-2-r3.md:8935: trailing whitespace.
++   415	
.oracle/checkins/batch-2-r3.md:8937: trailing whitespace.
++   416	
.oracle/checkins/batch-2-r3.md:8939: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r3.md:8941: trailing whitespace.
++   437	
.oracle/checkins/batch-2-r3.md:8943: trailing whitespace.
++   452	
.oracle/checkins/batch-2-r3.md:8945: trailing whitespace.
++   453	
.oracle/checkins/batch-2-r3.md:8947: trailing whitespace.
++   467	
.oracle/checkins/batch-2-r3.md:8949: trailing whitespace.
++   476	
.oracle/checkins/batch-2-r3.md:8951: trailing whitespace.
++   479	
.oracle/checkins/batch-2-r3.md:8953: trailing whitespace.
++   531	
.oracle/checkins/batch-2-r3.md:8955: trailing whitespace.
++   532	
.oracle/checkins/batch-2-r3.md:8957: trailing whitespace.
++   542	
.oracle/checkins/batch-2-r3.md:8959: trailing whitespace.
++   559	
.oracle/checkins/batch-2-r3.md:8961: trailing whitespace.
++   581	
.oracle/checkins/batch-2-r3.md:8963: trailing whitespace.
++   582	
.oracle/checkins/batch-2-r3.md:8965: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:8967: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r3.md:8969: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r3.md:8971: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r3.md:8973: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r3.md:8975: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r3.md:8977: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r3.md:8979: trailing whitespace.
++    26	
.oracle/checkins/batch-2-r3.md:8981: trailing whitespace.
++    27	
.oracle/checkins/batch-2-r3.md:8983: trailing whitespace.
++    31	
.oracle/checkins/batch-2-r3.md:8985: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r3.md:8987: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r3.md:8989: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r3.md:8991: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r3.md:8993: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r3.md:8995: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r3.md:8997: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r3.md:8999: trailing whitespace.
++    71	
.oracle/checkins/batch-2-r3.md:9001: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r3.md:9003: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r3.md:9005: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r3.md:9007: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r3.md:9009: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r3.md:9011: trailing whitespace.
++    93	
.oracle/checkins/batch-2-r3.md:9013: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r3.md:9015: trailing whitespace.
++   107	
.oracle/checkins/batch-2-r3.md:9017: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r3.md:9019: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r3.md:9021: trailing whitespace.
++   124	
.oracle/checkins/batch-2-r3.md:9023: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r3.md:9025: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r3.md:9027: trailing whitespace.
++   133	
.oracle/checkins/batch-2-r3.md:9029: trailing whitespace.
++   150	
.oracle/checkins/batch-2-r3.md:9031: trailing whitespace.
++   151	
.oracle/checkins/batch-2-r3.md:9033: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r3.md:9035: trailing whitespace.
++   160	
.oracle/checkins/batch-2-r3.md:9037: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r3.md:9039: trailing whitespace.
++   169	
.oracle/checkins/batch-2-r3.md:9041: trailing whitespace.
++   186	
.oracle/checkins/batch-2-r3.md:9043: trailing whitespace.
++   189	
.oracle/checkins/batch-2-r3.md:9045: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r3.md:9047: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r3.md:9049: trailing whitespace.
++   211	
.oracle/checkins/batch-2-r3.md:9051: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r3.md:9053: trailing whitespace.
++   239	
.oracle/checkins/batch-2-r3.md:9055: trailing whitespace.
++   241	
.oracle/checkins/batch-2-r3.md:9057: trailing whitespace.
++   242	
.oracle/checkins/batch-2-r3.md:9059: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r3.md:9061: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r3.md:9063: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r3.md:9065: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r3.md:9067: trailing whitespace.
++    87	
.oracle/checkins/batch-2-r3.md:9069: trailing whitespace.
++   117	
.oracle/checkins/batch-2-r3.md:9071: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r3.md:9073: trailing whitespace.
++   121	
.oracle/checkins/batch-2-r3.md:9075: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r3.md:9077: trailing whitespace.
++   152	
.oracle/checkins/batch-2-r3.md:9079: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r3.md:9081: trailing whitespace.
++   156	
.oracle/checkins/batch-2-r3.md:9083: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r3.md:9085: trailing whitespace.
++   186	
.oracle/checkins/batch-2-r3.md:9087: trailing whitespace.
++   197	
.oracle/checkins/batch-2-r3.md:9089: trailing whitespace.
++   199	
.oracle/checkins/batch-2-r3.md:9091: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:9093: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r3.md:9095: trailing whitespace.
++    15	
.oracle/checkins/batch-2-r3.md:9097: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r3.md:9099: trailing whitespace.
++    27	
.oracle/checkins/batch-2-r3.md:9101: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r3.md:9103: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r3.md:9105: trailing whitespace.
++    45	
.oracle/checkins/batch-2-r3.md:9107: trailing whitespace.
++    46	
.oracle/checkins/batch-2-r3.md:9109: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r3.md:9111: trailing whitespace.
++    51	
.oracle/checkins/batch-2-r3.md:9113: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r3.md:9115: trailing whitespace.
++    57	
.oracle/checkins/batch-2-r3.md:9117: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r3.md:9119: trailing whitespace.
++    80	
.oracle/checkins/batch-2-r3.md:9121: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r3.md:9123: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r3.md:9125: trailing whitespace.
++    87	
.oracle/checkins/batch-2-r3.md:9127: trailing whitespace.
++    95	
.oracle/checkins/batch-2-r3.md:9129: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r3.md:9131: trailing whitespace.
++   121	
.oracle/checkins/batch-2-r3.md:9133: trailing whitespace.
++   131	
.oracle/checkins/batch-2-r3.md:9135: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r3.md:9137: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r3.md:9139: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r3.md:9141: trailing whitespace.
++   164	
.oracle/checkins/batch-2-r3.md:9143: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r3.md:9145: trailing whitespace.
++   182	
.oracle/checkins/batch-2-r3.md:9147: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r3.md:9149: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r3.md:9151: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r3.md:9153: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r3.md:9155: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r3.md:9157: trailing whitespace.
++   221	
.oracle/checkins/batch-2-r3.md:9159: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r3.md:9161: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r3.md:9163: trailing whitespace.
++   249	
.oracle/checkins/batch-2-r3.md:9165: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r3.md:9167: trailing whitespace.
++   256	
.oracle/checkins/batch-2-r3.md:9169: trailing whitespace.
++   266	
.oracle/checkins/batch-2-r3.md:9171: trailing whitespace.
++   267	
.oracle/checkins/batch-2-r3.md:9173: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r3.md:9175: trailing whitespace.
++   272	
.oracle/checkins/batch-2-r3.md:9177: trailing whitespace.
++   276	
.oracle/checkins/batch-2-r3.md:9179: trailing whitespace.
++   279	
.oracle/checkins/batch-2-r3.md:9181: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r3.md:9183: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r3.md:9185: trailing whitespace.
++   292	
.oracle/checkins/batch-2-r3.md:9187: trailing whitespace.
++   301	
.oracle/checkins/batch-2-r3.md:9189: trailing whitespace.
++   302	
.oracle/checkins/batch-2-r3.md:9191: trailing whitespace.
++   311	
.oracle/checkins/batch-2-r3.md:9193: trailing whitespace.
++   314	
.oracle/checkins/batch-2-r3.md:9195: trailing whitespace.
++   315	
.oracle/checkins/batch-2-r3.md:9197: trailing whitespace.
++   319	
.oracle/checkins/batch-2-r3.md:9199: trailing whitespace.
++   320	
.oracle/checkins/batch-2-r3.md:9201: trailing whitespace.
++   326	
.oracle/checkins/batch-2-r3.md:9203: trailing whitespace.
++   340	
.oracle/checkins/batch-2-r3.md:9205: trailing whitespace.
++   344	
.oracle/checkins/batch-2-r3.md:9207: trailing whitespace.
++   347	
.oracle/checkins/batch-2-r3.md:9209: trailing whitespace.
++   348	
.oracle/checkins/batch-2-r3.md:9211: trailing whitespace.
++   354	
.oracle/checkins/batch-2-r3.md:9213: trailing whitespace.
++   368	
.oracle/checkins/batch-2-r3.md:9215: trailing whitespace.
++   372	
.oracle/checkins/batch-2-r3.md:9217: trailing whitespace.
++   377	
.oracle/checkins/batch-2-r3.md:9219: trailing whitespace.
++   380	
.oracle/checkins/batch-2-r3.md:9221: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:9223: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r3.md:9225: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r3.md:9227: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r3.md:9229: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r3.md:9231: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r3.md:9233: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r3.md:9235: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r3.md:9237: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r3.md:9239: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r3.md:9241: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r3.md:9243: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r3.md:9245: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r3.md:9247: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r3.md:9249: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r3.md:9251: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r3.md:9253: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r3.md:9255: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r3.md:9257: trailing whitespace.
++   108	
.oracle/checkins/batch-2-r3.md:9259: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r3.md:9261: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r3.md:9263: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r3.md:9265: trailing whitespace.
++   130	
.oracle/checkins/batch-2-r3.md:9267: trailing whitespace.
++   135	
.oracle/checkins/batch-2-r3.md:9269: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r3.md:9271: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r3.md:9273: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r3.md:9275: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r3.md:9277: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r3.md:9279: trailing whitespace.
++   205	
.oracle/checkins/batch-2-r3.md:9281: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r3.md:9283: trailing whitespace.
++   218	
.oracle/checkins/batch-2-r3.md:9285: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r3.md:9287: trailing whitespace.
++   247	
.oracle/checkins/batch-2-r3.md:9289: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r3.md:9291: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r3.md:9293: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r3.md:9295: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r3.md:9297: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r3.md:9299: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r3.md:9301: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r3.md:9303: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r3.md:9305: trailing whitespace.
++    18	
.oracle/checkins/batch-2-r3.md:9307: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r3.md:9309: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r3.md:9311: trailing whitespace.
++    28	
.oracle/checkins/batch-2-r3.md:9313: trailing whitespace.
++    31	
.oracle/checkins/batch-2-r3.md:9315: trailing whitespace.
++    32	
.oracle/checkins/batch-2-r3.md:9317: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r3.md:9319: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r3.md:9321: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r3.md:9323: trailing whitespace.
++    44	
.oracle/checkins/batch-2-r3.md:9325: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r3.md:9327: trailing whitespace.
++    66	
.oracle/checkins/batch-2-r3.md:9329: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r3.md:9331: trailing whitespace.
++    72	
.oracle/checkins/batch-2-r3.md:9333: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r3.md:9335: trailing whitespace.
++    76	
.oracle/checkins/batch-2-r3.md:9337: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r3.md:9339: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r3.md:9341: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r3.md:9343: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r3.md:9345: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r3.md:9347: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r3.md:9349: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r3.md:9351: trailing whitespace.
++    99	
.oracle/checkins/batch-2-r3.md:9353: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r3.md:9355: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r3.md:9357: trailing whitespace.
++   133	
.oracle/checkins/batch-2-r3.md:9359: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r3.md:9361: trailing whitespace.
++   173	
.oracle/checkins/batch-2-r3.md:9363: trailing whitespace.
++   174	
.oracle/checkins/batch-2-r3.md:9365: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r3.md:9367: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r3.md:9369: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r3.md:9371: trailing whitespace.
++   200	
.oracle/checkins/batch-2-r3.md:9373: trailing whitespace.
++   201	
.oracle/checkins/batch-2-r3.md:9375: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r3.md:9377: trailing whitespace.
++   264	
.oracle/checkins/batch-2-r3.md:9379: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r3.md:9381: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r3.md:9383: trailing whitespace.
++   282	
.oracle/checkins/batch-2-r3.md:9385: trailing whitespace.
++   285	
.oracle/checkins/batch-2-r3.md:9387: trailing whitespace.
++   299	
.oracle/checkins/batch-2-r3.md:9389: trailing whitespace.
++   306	
.oracle/checkins/batch-2-r3.md:9391: trailing whitespace.
++   317	
.oracle/checkins/batch-2-r3.md:9393: trailing whitespace.
++   325	
.oracle/checkins/batch-2-r3.md:9395: trailing whitespace.
++   335	
.oracle/checkins/batch-2-r3.md:9397: trailing whitespace.
++   336	
.oracle/checkins/batch-2-r3.md:9399: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9401: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9403: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9405: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9407: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9409: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9411: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9413: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9415: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9417: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9419: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9421: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9423: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9425: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9427: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9429: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9431: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9433: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9435: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9437: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9439: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9441: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9443: trailing whitespace.
++  1443	
.oracle/checkins/batch-2-r3.md:9445: trailing whitespace.
++  1444	
.oracle/checkins/batch-2-r3.md:9447: trailing whitespace.
++  1458	
.oracle/checkins/batch-2-r3.md:9449: trailing whitespace.
++  1479	
.oracle/checkins/batch-2-r3.md:9451: trailing whitespace.
++  1480	
.oracle/checkins/batch-2-r3.md:9453: trailing whitespace.
++  1277	
.oracle/checkins/batch-2-r3.md:9455: trailing whitespace.
++  1278	
.oracle/checkins/batch-2-r3.md:9457: trailing whitespace.
++   435	
.oracle/checkins/batch-2-r3.md:9459: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r3.md:9461: trailing whitespace.
++   445	
.oracle/checkins/batch-2-r3.md:9463: trailing whitespace.
++   477	
.oracle/checkins/batch-2-r3.md:9465: trailing whitespace.
++   649	
.oracle/checkins/batch-2-r3.md:9467: trailing whitespace.
++   650	
.oracle/checkins/batch-2-r3.md:9469: trailing whitespace.
++   660	
.oracle/checkins/batch-2-r3.md:9471: trailing whitespace.
++   720	
.oracle/checkins/batch-2-r3.md:9473: trailing whitespace.
++  1151	
.oracle/checkins/batch-2-r3.md:9475: trailing whitespace.
++  1152	
.oracle/checkins/batch-2-r3.md:9477: trailing whitespace.
++  1184	
.oracle/checkins/batch-2-r3.md:9479: trailing whitespace.
++  1238	
.oracle/checkins/batch-2-r3.md:9481: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9483: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9485: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9487: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9489: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9491: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9493: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9495: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9497: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9499: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9501: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9503: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9505: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9507: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9509: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9511: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9513: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9515: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9517: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9519: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9521: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9523: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9525: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9527: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9529: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9531: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9533: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9535: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9537: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9539: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9541: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9543: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9545: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9547: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9549: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9551: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9553: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9555: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9557: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9559: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9561: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9563: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9565: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9567: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9569: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9571: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9573: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9575: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9577: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9579: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9581: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9583: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9585: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9587: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9589: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9591: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9593: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9595: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9597: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9599: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9601: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9603: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9605: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9607: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9609: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9611: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9613: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9615: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9617: trailing whitespace.
++ 
.oracle/checkins/batch-2-r3.md:9619: trailing whitespace.
++   959	
.oracle/checkins/batch-2-r3.md:9621: trailing whitespace.
++   960	
.oracle/checkins/batch-2-r3.md:9623: trailing whitespace.
++   963	
.oracle/checkins/batch-2-r3.md:9625: trailing whitespace.
++   964	
.oracle/checkins/batch-2-r3.md:9627: trailing whitespace.
++   970	
.oracle/checkins/batch-2-r3.md:9629: trailing whitespace.
++   975	
.oracle/checkins/batch-2-r3.md:9631: trailing whitespace.
++   989	
.oracle/checkins/batch-2-r3.md:9633: trailing whitespace.
++   990	
.oracle/checkins/batch-2-r3.md:9635: trailing whitespace.
++  1001	
.oracle/checkins/batch-2-r3.md:9637: trailing whitespace.
++  1002	
.oracle/checkins/batch-2-r3.md:9639: trailing whitespace.
++  1009	
.oracle/checkins/batch-2-r3.md:9641: trailing whitespace.
++  1010	
.oracle/checkins/batch-2-r3.md:9643: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r3.md:9645: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r3.md:9647: trailing whitespace.
++    49	
.oracle/checkins/batch-2-r3.md:9649: trailing whitespace.
++    53	
.oracle/checkins/batch-2-r3.md:9651: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r3.md:9653: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r3.md:9655: trailing whitespace.
++    74	
.oracle/checkins/batch-2-r3.md:9657: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r3.md:9659: trailing whitespace.
++    83	
.oracle/checkins/batch-2-r3.md:9661: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r3.md:9663: trailing whitespace.
++   110	
.oracle/checkins/batch-2-r3.md:9665: trailing whitespace.
++   112	
.oracle/checkins/batch-2-r3.md:9667: trailing whitespace.
++   116	
.oracle/checkins/batch-2-r3.md:9669: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r3.md:9671: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r3.md:9673: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r3.md:9675: trailing whitespace.
++   140	
.oracle/checkins/batch-2-r3.md:9677: trailing whitespace.
++   142	
.oracle/checkins/batch-2-r3.md:9679: trailing whitespace.
++   147	
.oracle/checkins/batch-2-r3.md:9681: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r3.md:9683: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r3.md:9685: trailing whitespace.
++   163	
.oracle/checkins/batch-2-r3.md:9687: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r3.md:9689: trailing whitespace.
++   172	
.oracle/checkins/batch-2-r3.md:9691: trailing whitespace.
++   175	
.oracle/checkins/batch-2-r3.md:9693: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r3.md:9695: trailing whitespace.
++   189	
.oracle/checkins/batch-2-r3.md:9697: trailing whitespace.
++   362	
.oracle/checkins/batch-2-r3.md:9699: trailing whitespace.
++   363	
.oracle/checkins/batch-2-r3.md:9701: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r3.md:9703: trailing whitespace.
++   395	
.oracle/checkins/batch-2-r3.md:9705: trailing whitespace.
++   442	
.oracle/checkins/batch-2-r3.md:9707: trailing whitespace.
++   458	
.oracle/checkins/batch-2-r3.md:9709: trailing whitespace.
++   459	
.oracle/checkins/batch-2-r3.md:9711: trailing whitespace.
++   480	
.oracle/checkins/batch-2-r3.md:9713: trailing whitespace.
++   505	
.oracle/checkins/batch-2-r3.md:9715: trailing whitespace.
++   506	
.oracle/checkins/batch-2-r3.md:9747: trailing whitespace.
+   442	
.oracle/checkins/batch-2-r3.md:9763: trailing whitespace.
+   458	
.oracle/checkins/batch-2-r3.md:9764: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r3.md:9785: trailing whitespace.
+   480	
.oracle/checkins/batch-2-r3.md:9810: trailing whitespace.
+   505	
.oracle/checkins/batch-2-r3.md:9811: trailing whitespace.
+   506	
.oracle/checkins/batch-2-r3.md:9891: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9900: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9901: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9908: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9909: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9926: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9927: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9944: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9945: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9958: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9959: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9964: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9982: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9993: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:9997: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10018: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10021: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10024: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10025: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10030: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10048: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10049: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10081: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10082: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10093: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10094: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10113: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10114: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10125: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10126: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10179: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10180: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10191: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10198: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10199: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10216: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10217: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10220: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10226: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10231: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10235: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10252: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10255: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10261: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10269: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10277: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10283: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10308: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10310: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10311: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10323: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10353: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10362: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10363: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10370: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10375: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10376: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10383: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10389: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10391: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10392: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10396: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10397: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10408: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10438: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10439: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10442: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10460: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10473: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10474: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10477: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10486: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10507: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10549: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10551: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10582: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10586: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10609: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10612: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10613: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10616: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10624: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10634: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10656: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10657: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10661: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10662: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10668: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10678: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10695: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10705: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10718: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10723: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10728: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10730: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10740: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10741: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10745: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10746: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10750: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10753: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10778: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10779: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10783: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10792: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10793: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10802: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10805: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10806: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10810: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10811: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10817: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10831: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10835: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10838: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10839: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10845: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10859: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10863: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10868: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10876: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10880: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10881: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10884: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10885: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10888: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10889: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10892: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10893: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10899: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10900: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10913: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10914: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10929: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10930: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10937: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10938: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10942: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10943: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10947: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10948: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10971: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:10972: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11005: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11006: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11028: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11038: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11042: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11043: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11054: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11057: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11061: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11070: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11074: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11078: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11082: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11086: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11087: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11091: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11092: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11095: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11096: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11109: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11110: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11130: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11131: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11173: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11174: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11188: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11197: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11200: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11252: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11253: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11263: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11280: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11303: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11304: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11390: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11403: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11412: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11438: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11447: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11459: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11470: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11473: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11477: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11486: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11489: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11498: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11501: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11504: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11507: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11511: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11523: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11528: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11563: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11564: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11571: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11573: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11574: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11590: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11591: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11639: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11665: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11666: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11676: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11683: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11686: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11700: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11707: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11718: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11726: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11789: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11828: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11829: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:11951: trailing whitespace.
+   409	
.oracle/checkins/batch-2-r3.md:11952: trailing whitespace.
+   410	
.oracle/checkins/batch-2-r3.md:11969: trailing whitespace.
+   427	
.oracle/checkins/batch-2-r3.md:11970: trailing whitespace.
+   428	
.oracle/checkins/batch-2-r3.md:11987: trailing whitespace.
+   445	
.oracle/checkins/batch-2-r3.md:11988: trailing whitespace.
+   446	
.oracle/checkins/batch-2-r3.md:12001: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r3.md:12002: trailing whitespace.
+   460	
.oracle/checkins/batch-2-r3.md:12007: trailing whitespace.
+   465	
.oracle/checkins/batch-2-r3.md:12022: trailing whitespace.
+   480	
.oracle/checkins/batch-2-r3.md:12032: trailing whitespace.
+   490	
.oracle/checkins/batch-2-r3.md:12036: trailing whitespace.
+   494	
.oracle/checkins/batch-2-r3.md:12057: trailing whitespace.
+   515	
.oracle/checkins/batch-2-r3.md:12060: trailing whitespace.
+   518	
.oracle/checkins/batch-2-r3.md:12063: trailing whitespace.
+   521	
.oracle/checkins/batch-2-r3.md:12064: trailing whitespace.
+   522	
.oracle/checkins/batch-2-r3.md:12069: trailing whitespace.
+   527	
.oracle/checkins/batch-2-r3.md:12086: trailing whitespace.
+   544	
.oracle/checkins/batch-2-r3.md:12087: trailing whitespace.
+   545	
.oracle/checkins/batch-2-r3.md:12113: trailing whitespace.
+   571	
.oracle/checkins/batch-2-r3.md:12114: trailing whitespace.
+   572	
.oracle/checkins/batch-2-r3.md:12125: trailing whitespace.
+   583	
.oracle/checkins/batch-2-r3.md:12126: trailing whitespace.
+   584	
.oracle/checkins/batch-2-r3.md:12145: trailing whitespace.
+   603	
.oracle/checkins/batch-2-r3.md:12146: trailing whitespace.
+   604	
.oracle/checkins/batch-2-r3.md:12157: trailing whitespace.
+   615	
.oracle/checkins/batch-2-r3.md:12158: trailing whitespace.
+   616	
.oracle/checkins/batch-2-r3.md:12186: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:12195: trailing whitespace.
+    11	
.oracle/checkins/batch-2-r3.md:12197: trailing whitespace.
+    13	
.oracle/checkins/batch-2-r3.md:12207: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r3.md:12208: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r3.md:12213: trailing whitespace.
+    29	
.oracle/checkins/batch-2-r3.md:12214: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r3.md:12217: trailing whitespace.
+    33	
.oracle/checkins/batch-2-r3.md:12218: trailing whitespace.
+    34	
.oracle/checkins/batch-2-r3.md:12223: trailing whitespace.
+    39	
.oracle/checkins/batch-2-r3.md:12224: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r3.md:12247: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r3.md:12248: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r3.md:12258: trailing whitespace.
+    74	
.oracle/checkins/batch-2-r3.md:12259: trailing whitespace.
+    75	
.oracle/checkins/batch-2-r3.md:12273: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r3.md:12274: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r3.md:12280: trailing whitespace.
+    96	
.oracle/checkins/batch-2-r3.md:12284: trailing whitespace.
+   100	
.oracle/checkins/batch-2-r3.md:12285: trailing whitespace.
+   101	
.oracle/checkins/batch-2-r3.md:12307: trailing whitespace.
+   123	
.oracle/checkins/batch-2-r3.md:12309: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r3.md:12310: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r3.md:12313: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r3.md:12323: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r3.md:12326: trailing whitespace.
+   142	
.oracle/checkins/batch-2-r3.md:12327: trailing whitespace.
+   143	
.oracle/checkins/batch-2-r3.md:12339: trailing whitespace.
+   155	
.oracle/checkins/batch-2-r3.md:12345: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r3.md:12346: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r3.md:12349: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r3.md:12352: trailing whitespace.
+   168	
.oracle/checkins/batch-2-r3.md:12360: trailing whitespace.
+   176	
.oracle/checkins/batch-2-r3.md:12361: trailing whitespace.
+   177	
.oracle/checkins/batch-2-r3.md:12365: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r3.md:12368: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r3.md:12372: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r3.md:12373: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r3.md:12376: trailing whitespace.
+   192	
.oracle/checkins/batch-2-r3.md:12383: trailing whitespace.
+   199	
.oracle/checkins/batch-2-r3.md:12389: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r3.md:12398: trailing whitespace.
+   214	
.oracle/checkins/batch-2-r3.md:12399: trailing whitespace.
+   215	
.oracle/checkins/batch-2-r3.md:12403: trailing whitespace.
+   219	
.oracle/checkins/batch-2-r3.md:12406: trailing whitespace.
+   222	
.oracle/checkins/batch-2-r3.md:12407: trailing whitespace.
+   223	
.oracle/checkins/batch-2-r3.md:12411: trailing whitespace.
+   227	
.oracle/checkins/batch-2-r3.md:12414: trailing whitespace.
+   230	
.oracle/checkins/batch-2-r3.md:12415: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r3.md:12419: trailing whitespace.
+   235	
.oracle/checkins/batch-2-r3.md:12422: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r3.md:12426: trailing whitespace.
+   242	
.oracle/checkins/batch-2-r3.md:12427: trailing whitespace.
+   243	
.oracle/checkins/batch-2-r3.md:12434: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r3.md:12444: trailing whitespace.
+   260	
.oracle/checkins/batch-2-r3.md:12449: trailing whitespace.
+   265	
.oracle/checkins/batch-2-r3.md:12450: trailing whitespace.
+   266	
.oracle/checkins/batch-2-r3.md:12456: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r3.md:12470: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r3.md:12486: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r3.md:12487: trailing whitespace.
+   245	
.oracle/checkins/batch-2-r3.md:12494: trailing whitespace.
+   252	
.oracle/checkins/batch-2-r3.md:12495: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r3.md:12499: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r3.md:12500: trailing whitespace.
+   258	
.oracle/checkins/batch-2-r3.md:12504: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r3.md:12505: trailing whitespace.
+   263	
.oracle/checkins/batch-2-r3.md:12528: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r3.md:12529: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r3.md:12552: trailing whitespace.
+   310	
.oracle/checkins/batch-2-r3.md:12553: trailing whitespace.
+   311	
.oracle/checkins/batch-2-r3.md:12575: trailing whitespace.
+   333	
.oracle/checkins/batch-2-r3.md:12585: trailing whitespace.
+   343	
.oracle/checkins/batch-2-r3.md:12589: trailing whitespace.
+   347	
.oracle/checkins/batch-2-r3.md:12590: trailing whitespace.
+   348	
.oracle/checkins/batch-2-r3.md:12601: trailing whitespace.
+   359	
.oracle/checkins/batch-2-r3.md:12604: trailing whitespace.
+   362	
.oracle/checkins/batch-2-r3.md:12608: trailing whitespace.
+   366	
.oracle/checkins/batch-2-r3.md:12617: trailing whitespace.
+   375	
.oracle/checkins/batch-2-r3.md:12621: trailing whitespace.
+   379	
.oracle/checkins/batch-2-r3.md:12625: trailing whitespace.
+   383	
.oracle/checkins/batch-2-r3.md:12629: trailing whitespace.
+   387	
.oracle/checkins/batch-2-r3.md:12633: trailing whitespace.
+   391	
.oracle/checkins/batch-2-r3.md:12634: trailing whitespace.
+   392	
.oracle/checkins/batch-2-r3.md:12638: trailing whitespace.
+   396	
.oracle/checkins/batch-2-r3.md:12639: trailing whitespace.
+   397	
.oracle/checkins/batch-2-r3.md:12642: trailing whitespace.
+   400	
.oracle/checkins/batch-2-r3.md:12643: trailing whitespace.
+   401	
.oracle/checkins/batch-2-r3.md:12656: trailing whitespace.
+   414	
.oracle/checkins/batch-2-r3.md:12657: trailing whitespace.
+   415	
.oracle/checkins/batch-2-r3.md:12677: trailing whitespace.
+   435	
.oracle/checkins/batch-2-r3.md:12678: trailing whitespace.
+   436	
.oracle/checkins/batch-2-r3.md:12719: trailing whitespace.
+   477	
.oracle/checkins/batch-2-r3.md:12720: trailing whitespace.
+   478	
.oracle/checkins/batch-2-r3.md:12734: trailing whitespace.
+   492	
.oracle/checkins/batch-2-r3.md:12743: trailing whitespace.
+   501	
.oracle/checkins/batch-2-r3.md:12746: trailing whitespace.
+   504	
.oracle/checkins/batch-2-r3.md:12765: trailing whitespace.
+   150	
.oracle/checkins/batch-2-r3.md:12766: trailing whitespace.
+   151	
.oracle/checkins/batch-2-r3.md:12769: trailing whitespace.
+   154	
.oracle/checkins/batch-2-r3.md:12775: trailing whitespace.
+   160	
.oracle/checkins/batch-2-r3.md:12780: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r3.md:12784: trailing whitespace.
+   169	
.oracle/checkins/batch-2-r3.md:12801: trailing whitespace.
+   186	
.oracle/checkins/batch-2-r3.md:12804: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r3.md:12810: trailing whitespace.
+   195	
.oracle/checkins/batch-2-r3.md:12818: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r3.md:12826: trailing whitespace.
+   211	
.oracle/checkins/batch-2-r3.md:12832: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r3.md:12853: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r3.md:12855: trailing whitespace.
+   240	
.oracle/checkins/batch-2-r3.md:12856: trailing whitespace.
+   241	
.oracle/checkins/batch-2-r3.md:12868: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r3.md:12882: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:12888: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r3.md:12890: trailing whitespace.
+    10	
.oracle/checkins/batch-2-r3.md:12902: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r3.md:12903: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r3.md:12906: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r3.md:12910: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r3.md:12912: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r3.md:12929: trailing whitespace.
+    49	
.oracle/checkins/batch-2-r3.md:12930: trailing whitespace.
+    50	
.oracle/checkins/batch-2-r3.md:12933: trailing whitespace.
+    53	
.oracle/checkins/batch-2-r3.md:12937: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r3.md:12944: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r3.md:12946: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r3.md:12947: trailing whitespace.
+    67	
.oracle/checkins/batch-2-r3.md:12951: trailing whitespace.
+    71	
.oracle/checkins/batch-2-r3.md:12954: trailing whitespace.
+    74	
.oracle/checkins/batch-2-r3.md:12957: trailing whitespace.
+    77	
.oracle/checkins/batch-2-r3.md:12958: trailing whitespace.
+    78	
.oracle/checkins/batch-2-r3.md:12961: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r3.md:12962: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r3.md:12966: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r3.md:12967: trailing whitespace.
+    87	
.oracle/checkins/batch-2-r3.md:12997: trailing whitespace.
+   117	
.oracle/checkins/batch-2-r3.md:12998: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r3.md:13001: trailing whitespace.
+   121	
.oracle/checkins/batch-2-r3.md:13019: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r3.md:13032: trailing whitespace.
+   152	
.oracle/checkins/batch-2-r3.md:13033: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r3.md:13036: trailing whitespace.
+   156	
.oracle/checkins/batch-2-r3.md:13045: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r3.md:13066: trailing whitespace.
+   186	
.oracle/checkins/batch-2-r3.md:13071: trailing whitespace.
+   191	
.oracle/checkins/batch-2-r3.md:13085: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r3.md:13097: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r3.md:13106: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:13111: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r3.md:13119: trailing whitespace.
+    15	
.oracle/checkins/batch-2-r3.md:13121: trailing whitespace.
+    17	
.oracle/checkins/batch-2-r3.md:13131: trailing whitespace.
+    27	
.oracle/checkins/batch-2-r3.md:13140: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r3.md:13141: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r3.md:13149: trailing whitespace.
+    45	
.oracle/checkins/batch-2-r3.md:13150: trailing whitespace.
+    46	
.oracle/checkins/batch-2-r3.md:13154: trailing whitespace.
+    50	
.oracle/checkins/batch-2-r3.md:13155: trailing whitespace.
+    51	
.oracle/checkins/batch-2-r3.md:13159: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r3.md:13161: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r3.md:13162: trailing whitespace.
+    58	
.oracle/checkins/batch-2-r3.md:13184: trailing whitespace.
+    80	
.oracle/checkins/batch-2-r3.md:13185: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r3.md:13190: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r3.md:13191: trailing whitespace.
+    87	
.oracle/checkins/batch-2-r3.md:13199: trailing whitespace.
+    95	
.oracle/checkins/batch-2-r3.md:13224: trailing whitespace.
+   120	
.oracle/checkins/batch-2-r3.md:13225: trailing whitespace.
+   121	
.oracle/checkins/batch-2-r3.md:13235: trailing whitespace.
+   131	
.oracle/checkins/batch-2-r3.md:13236: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r3.md:13257: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r3.md:13258: trailing whitespace.
+   154	
.oracle/checkins/batch-2-r3.md:13268: trailing whitespace.
+   164	
.oracle/checkins/batch-2-r3.md:13274: trailing whitespace.
+   170	
.oracle/checkins/batch-2-r3.md:13286: trailing whitespace.
+   182	
.oracle/checkins/batch-2-r3.md:13287: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r3.md:13291: trailing whitespace.
+   187	
.oracle/checkins/batch-2-r3.md:13292: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r3.md:13298: trailing whitespace.
+   194	
.oracle/checkins/batch-2-r3.md:13308: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r3.md:13325: trailing whitespace.
+   221	
.oracle/checkins/batch-2-r3.md:13335: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r3.md:13348: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r3.md:13353: trailing whitespace.
+   249	
.oracle/checkins/batch-2-r3.md:13358: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r3.md:13360: trailing whitespace.
+   256	
.oracle/checkins/batch-2-r3.md:13370: trailing whitespace.
+   266	
.oracle/checkins/batch-2-r3.md:13371: trailing whitespace.
+   267	
.oracle/checkins/batch-2-r3.md:13375: trailing whitespace.
+   271	
.oracle/checkins/batch-2-r3.md:13376: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r3.md:13380: trailing whitespace.
+   276	
.oracle/checkins/batch-2-r3.md:13383: trailing whitespace.
+   279	
.oracle/checkins/batch-2-r3.md:13498: trailing whitespace.
+   160	
.oracle/checkins/batch-2-r3.md:13509: trailing whitespace.
+   171	
.oracle/checkins/batch-2-r3.md:13540: trailing whitespace.
+   202	
.oracle/checkins/batch-2-r3.md:13584: trailing whitespace.
+   246	
.oracle/checkins/batch-2-r3.md:13588: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r3.md:13595: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r3.md:13607: trailing whitespace.
+   269	
.oracle/checkins/batch-2-r3.md:13608: trailing whitespace.
+   270	
.oracle/checkins/batch-2-r3.md:13615: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:13617: trailing whitespace.
+     4	
.oracle/checkins/batch-2-r3.md:13626: trailing whitespace.
+    13	
.oracle/checkins/batch-2-r3.md:13627: trailing whitespace.
+    14	
.oracle/checkins/batch-2-r3.md:13633: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r3.md:13634: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r3.md:13639: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r3.md:13645: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r3.md:13648: trailing whitespace.
+    35	
.oracle/checkins/batch-2-r3.md:13655: trailing whitespace.
+    42	
.oracle/checkins/batch-2-r3.md:13692: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r3.md:13695: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r3.md:13696: trailing whitespace.
+    83	
.oracle/checkins/batch-2-r3.md:13710: trailing whitespace.
+   271	
.oracle/checkins/batch-2-r3.md:13711: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r3.md:13715: trailing whitespace.
+   276	
.oracle/checkins/batch-2-r3.md:13718: trailing whitespace.
+   279	
.oracle/checkins/batch-2-r3.md:13723: trailing whitespace.
+   284	
.oracle/checkins/batch-2-r3.md:13735: trailing whitespace.
+   296	
.oracle/checkins/batch-2-r3.md:13743: trailing whitespace.
+   304	
.oracle/checkins/batch-2-r3.md:13744: trailing whitespace.
+   305	
.oracle/checkins/batch-2-r3.md:13748: trailing whitespace.
+   309	
.oracle/checkins/batch-2-r3.md:13757: trailing whitespace.
+   318	
.oracle/checkins/batch-2-r3.md:13758: trailing whitespace.
+   319	
.oracle/checkins/batch-2-r3.md:13767: trailing whitespace.
+   328	
.oracle/checkins/batch-2-r3.md:13770: trailing whitespace.
+   331	
.oracle/checkins/batch-2-r3.md:13771: trailing whitespace.
+   332	
.oracle/checkins/batch-2-r3.md:13775: trailing whitespace.
+   336	
.oracle/checkins/batch-2-r3.md:13776: trailing whitespace.
+   337	
.oracle/checkins/batch-2-r3.md:13782: trailing whitespace.
+   343	
.oracle/checkins/batch-2-r3.md:13796: trailing whitespace.
+   357	
.oracle/checkins/batch-2-r3.md:13800: trailing whitespace.
+   361	
.oracle/checkins/batch-2-r3.md:13803: trailing whitespace.
+   364	
.oracle/checkins/batch-2-r3.md:13804: trailing whitespace.
+   365	
.oracle/checkins/batch-2-r3.md:13810: trailing whitespace.
+   371	
.oracle/checkins/batch-2-r3.md:13824: trailing whitespace.
+   385	
.oracle/checkins/batch-2-r3.md:13828: trailing whitespace.
+   389	
.oracle/checkins/batch-2-r3.md:13842: trailing whitespace.
+   186	
.oracle/checkins/batch-2-r3.md:13845: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r3.md:13851: trailing whitespace.
+   195	
.oracle/checkins/batch-2-r3.md:13859: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r3.md:13867: trailing whitespace.
+   211	
.oracle/checkins/batch-2-r3.md:13873: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r3.md:13894: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r3.md:13896: trailing whitespace.
+   240	
.oracle/checkins/batch-2-r3.md:13897: trailing whitespace.
+   241	
.oracle/checkins/batch-2-r3.md:13910: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:13916: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r3.md:13918: trailing whitespace.
+    10	
.oracle/checkins/batch-2-r3.md:13930: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r3.md:13931: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r3.md:13934: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r3.md:13938: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r3.md:13940: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r3.md:13957: trailing whitespace.
+    49	
.oracle/checkins/batch-2-r3.md:13958: trailing whitespace.
+    50	
.oracle/checkins/batch-2-r3.md:13961: trailing whitespace.
+    53	
.oracle/checkins/batch-2-r3.md:13965: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r3.md:13972: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r3.md:13974: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r3.md:13975: trailing whitespace.
+    67	
.oracle/checkins/batch-2-r3.md:13979: trailing whitespace.
+    71	
.oracle/checkins/batch-2-r3.md:13982: trailing whitespace.
+    74	
.oracle/checkins/batch-2-r3.md:13985: trailing whitespace.
+    77	
.oracle/checkins/batch-2-r3.md:13986: trailing whitespace.
+    78	
.oracle/checkins/batch-2-r3.md:13989: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r3.md:13990: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r3.md:13994: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r3.md:13995: trailing whitespace.
+    87	
.oracle/checkins/batch-2-r3.md:14025: trailing whitespace.
+   117	
.oracle/checkins/batch-2-r3.md:14026: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r3.md:14029: trailing whitespace.
+   121	
.oracle/checkins/batch-2-r3.md:14047: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r3.md:14060: trailing whitespace.
+   152	
.oracle/checkins/batch-2-r3.md:14061: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r3.md:14064: trailing whitespace.
+   156	
.oracle/checkins/batch-2-r3.md:14073: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r3.md:14094: trailing whitespace.
+   186	
.oracle/checkins/batch-2-r3.md:14099: trailing whitespace.
+   191	
.oracle/checkins/batch-2-r3.md:14113: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r3.md:14125: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r3.md:14136: trailing whitespace.
+   228	
.oracle/checkins/batch-2-r3.md:14138: trailing whitespace.
+   230	
.oracle/checkins/batch-2-r3.md:14175: trailing whitespace.
+     3	
.oracle/checkins/batch-2-r3.md:14178: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r3.md:14180: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r3.md:14186: trailing whitespace.
+    14	
.oracle/checkins/batch-2-r3.md:14192: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r3.md:14194: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r3.md:14202: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r3.md:14205: trailing whitespace.
+    33	
.oracle/checkins/batch-2-r3.md:14221: trailing whitespace.
+    49	
.oracle/checkins/batch-2-r3.md:14225: trailing whitespace.
+    53	
.oracle/checkins/batch-2-r3.md:14227: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r3.md:14229: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r3.md:14230: trailing whitespace.
+    58	
.oracle/checkins/batch-2-r3.md:14234: trailing whitespace.
+    62	
.oracle/checkins/batch-2-r3.md:14235: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r3.md:14238: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r3.md:14240: trailing whitespace.
+    68	
.oracle/checkins/batch-2-r3.md:14245: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r3.md:14254: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r3.md:14263: trailing whitespace.
+    91	
.oracle/checkins/batch-2-r3.md:14264: trailing whitespace.
+    92	
.oracle/checkins/batch-2-r3.md:14271: trailing whitespace.
+    99	
.oracle/checkins/batch-2-r3.md:14272: trailing whitespace.
+   100	
.oracle/checkins/batch-2-r3.md:14276: trailing whitespace.
+   104	
.oracle/checkins/batch-2-r3.md:14277: trailing whitespace.
+   105	
.oracle/checkins/batch-2-r3.md:14289: trailing whitespace.
+   117	
.oracle/checkins/batch-2-r3.md:14290: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r3.md:14315: trailing whitespace.
+   143	
.oracle/checkins/batch-2-r3.md:14316: trailing whitespace.
+   144	
.oracle/checkins/batch-2-r3.md:14337: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r3.md:14338: trailing whitespace.
+   166	
.oracle/checkins/batch-2-r3.md:14341: trailing whitespace.
+   169	
.oracle/checkins/batch-2-r3.md:14362: trailing whitespace.
+   190	
.oracle/checkins/batch-2-r3.md:14363: trailing whitespace.
+   191	
.oracle/checkins/batch-2-r3.md:14367: trailing whitespace.
+   195	
.oracle/checkins/batch-2-r3.md:14368: trailing whitespace.
+   196	
.oracle/checkins/batch-2-r3.md:14371: trailing whitespace.
+   199	
.oracle/checkins/batch-2-r3.md:14372: trailing whitespace.
+   200	
.oracle/checkins/batch-2-r3.md:14375: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r3.md:14376: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r3.md:14379: trailing whitespace.
+   207	
.oracle/checkins/batch-2-r3.md:14380: trailing whitespace.
+   208	
.oracle/checkins/batch-2-r3.md:14386: trailing whitespace.
+   214	
.oracle/checkins/batch-2-r3.md:14387: trailing whitespace.
+   215	
.oracle/checkins/batch-2-r3.md:14400: trailing whitespace.
+   228	
.oracle/checkins/batch-2-r3.md:14401: trailing whitespace.
+   229	
.oracle/checkins/batch-2-r3.md:14416: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r3.md:14417: trailing whitespace.
+   245	
.oracle/checkins/batch-2-r3.md:14424: trailing whitespace.
+   252	
.oracle/checkins/batch-2-r3.md:14425: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r3.md:14429: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r3.md:14430: trailing whitespace.
+   258	
.oracle/checkins/batch-2-r3.md:14434: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r3.md:14435: trailing whitespace.
+   263	
.oracle/checkins/batch-2-r3.md:14458: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r3.md:14459: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r3.md:14482: trailing whitespace.
+   310	
.oracle/checkins/batch-2-r3.md:14483: trailing whitespace.
+   311	
.oracle/checkins/batch-2-r3.md:14505: trailing whitespace.
+   333	
.oracle/checkins/batch-2-r3.md:14515: trailing whitespace.
+   343	
.oracle/checkins/batch-2-r3.md:14519: trailing whitespace.
+   347	
.oracle/checkins/batch-2-r3.md:14520: trailing whitespace.
+   348	
.oracle/checkins/batch-2-r3.md:14531: trailing whitespace.
+   359	
.oracle/checkins/batch-2-r3.md:14534: trailing whitespace.
+   362	
.oracle/checkins/batch-2-r3.md:14538: trailing whitespace.
+   366	
.oracle/checkins/batch-2-r3.md:14547: trailing whitespace.
+   375	
.oracle/checkins/batch-2-r3.md:14551: trailing whitespace.
+   379	
.oracle/checkins/batch-2-r3.md:14555: trailing whitespace.
+   383	
.oracle/checkins/batch-2-r3.md:14559: trailing whitespace.
+   387	
.oracle/checkins/batch-2-r3.md:14568: trailing whitespace.
+   391	
.oracle/checkins/batch-2-r3.md:14569: trailing whitespace.
+   392	
.oracle/checkins/batch-2-r3.md:14573: trailing whitespace.
+   396	
.oracle/checkins/batch-2-r3.md:14574: trailing whitespace.
+   397	
.oracle/checkins/batch-2-r3.md:14577: trailing whitespace.
+   400	
.oracle/checkins/batch-2-r3.md:14578: trailing whitespace.
+   401	
.oracle/checkins/batch-2-r3.md:14591: trailing whitespace.
+   414	
.oracle/checkins/batch-2-r3.md:14592: trailing whitespace.
+   415	
.oracle/checkins/batch-2-r3.md:14612: trailing whitespace.
+   435	
.oracle/checkins/batch-2-r3.md:14613: trailing whitespace.
+   436	
.oracle/checkins/batch-2-r3.md:14654: trailing whitespace.
+   477	
.oracle/checkins/batch-2-r3.md:14655: trailing whitespace.
+   478	
.oracle/checkins/batch-2-r3.md:14669: trailing whitespace.
+   492	
.oracle/checkins/batch-2-r3.md:14678: trailing whitespace.
+   501	
.oracle/checkins/batch-2-r3.md:14681: trailing whitespace.
+   504	
.oracle/checkins/batch-2-r3.md:14733: trailing whitespace.
+   556	
.oracle/checkins/batch-2-r3.md:14734: trailing whitespace.
+   557	
.oracle/checkins/batch-2-r3.md:14744: trailing whitespace.
+   567	
.oracle/checkins/batch-2-r3.md:14772: trailing whitespace.
+   567	
.oracle/checkins/batch-2-r3.md:14789: trailing whitespace.
+   584	
.oracle/checkins/batch-2-r3.md:14811: trailing whitespace.
+   606	
.oracle/checkins/batch-2-r3.md:14812: trailing whitespace.
+   607	
.oracle/checkins/batch-2-r3.md:14831: trailing whitespace.
+   362	
.oracle/checkins/batch-2-r3.md:14832: trailing whitespace.
+   363	
.oracle/checkins/batch-2-r3.md:14863: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r3.md:14864: trailing whitespace.
+   395	
.oracle/checkins/batch-2-r3.md:14911: trailing whitespace.
+   442	
.oracle/checkins/batch-2-r3.md:14927: trailing whitespace.
+   458	
.oracle/checkins/batch-2-r3.md:14928: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r3.md:14949: trailing whitespace.
+   480	
.oracle/checkins/batch-2-r3.md:14974: trailing whitespace.
+   505	
.oracle/checkins/batch-2-r3.md:14975: trailing whitespace.
+   506	
.oracle/checkins/batch-2-r3.md:15002: trailing whitespace.
+   533	
.oracle/checkins/batch-2-r3.md:15003: trailing whitespace.
+   534	
.oracle/checkins/batch-2-r3.md:15028: trailing whitespace.
+   559	
.oracle/checkins/batch-2-r3.md:15029: trailing whitespace.
+   560	
.oracle/checkins/batch-2-r3.md:15069: trailing whitespace.
+   600	
.oracle/checkins/batch-2-r3.md:15070: trailing whitespace.
+   601	
.oracle/checkins/batch-2-r3.md:15097: trailing whitespace.
+   628	
.oracle/checkins/batch-2-r3.md:15098: trailing whitespace.
+   629	
.oracle/checkins/batch-2-r3.md:15106: trailing whitespace.
+   637	
.oracle/checkins/batch-2-r3.md:15112: trailing whitespace.
+   643	
.oracle/checkins/batch-2-r3.md:15119: trailing whitespace.
+   650	
.oracle/checkins/batch-2-r3.md:15138: trailing whitespace.
+   669	
.oracle/checkins/batch-2-r3.md:15148: trailing whitespace.
+   679	
.oracle/checkins/batch-2-r3.md:15169: trailing whitespace.
+   700	
.oracle/checkins/batch-2-r3.md:15170: trailing whitespace.
+   701	
.oracle/checkins/batch-2-r3.md:15177: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:15182: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r3.md:15184: trailing whitespace.
+     9	
.oracle/checkins/batch-2-r3.md:15193: trailing whitespace.
+    18	
.oracle/checkins/batch-2-r3.md:15196: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r3.md:15198: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r3.md:15203: trailing whitespace.
+    28	
.oracle/checkins/batch-2-r3.md:15206: trailing whitespace.
+    31	
.oracle/checkins/batch-2-r3.md:15207: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r3.md:15211: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r3.md:15212: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r3.md:15215: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r3.md:15219: trailing whitespace.
+    44	
.oracle/checkins/batch-2-r3.md:15234: trailing whitespace.
+    59	
.oracle/checkins/batch-2-r3.md:15241: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r3.md:15244: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r3.md:15247: trailing whitespace.
+    72	
.oracle/checkins/batch-2-r3.md:15248: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r3.md:15251: trailing whitespace.
+    76	
.oracle/checkins/batch-2-r3.md:15256: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r3.md:15257: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r3.md:15260: trailing whitespace.
+    85	
.oracle/checkins/batch-2-r3.md:15261: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r3.md:15264: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r3.md:15265: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r3.md:15273: trailing whitespace.
+    98	
.oracle/checkins/batch-2-r3.md:15274: trailing whitespace.
+    99	
.oracle/checkins/batch-2-r3.md:15300: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r3.md:15301: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r3.md:15308: trailing whitespace.
+   133	
.oracle/checkins/batch-2-r3.md:15313: trailing whitespace.
+   138	
.oracle/checkins/batch-2-r3.md:15348: trailing whitespace.
+   173	
.oracle/checkins/batch-2-r3.md:15349: trailing whitespace.
+   174	
.oracle/checkins/batch-2-r3.md:15356: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r3.md:15358: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r3.md:15359: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r3.md:15375: trailing whitespace.
+   200	
.oracle/checkins/batch-2-r3.md:15376: trailing whitespace.
+   201	
.oracle/checkins/batch-2-r3.md:15419: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r3.md:15445: trailing whitespace.
+   270	
.oracle/checkins/batch-2-r3.md:15446: trailing whitespace.
+   271	
.oracle/checkins/batch-2-r3.md:15456: trailing whitespace.
+   281	
.oracle/checkins/batch-2-r3.md:15463: trailing whitespace.
+   288	
.oracle/checkins/batch-2-r3.md:15466: trailing whitespace.
+   291	
.oracle/checkins/batch-2-r3.md:15480: trailing whitespace.
+   305	
.oracle/checkins/batch-2-r3.md:15487: trailing whitespace.
+   312	
.oracle/checkins/batch-2-r3.md:15498: trailing whitespace.
+   323	
.oracle/checkins/batch-2-r3.md:15599: trailing whitespace.
+   407	
.oracle/checkins/batch-2-r3.md:15627: trailing whitespace.
+   435	
.oracle/checkins/batch-2-r3.md:15628: trailing whitespace.
+   436	
.oracle/checkins/batch-2-r3.md:15637: trailing whitespace.
+   445	
.oracle/checkins/batch-2-r3.md:15669: trailing whitespace.
+   477	
.oracle/checkins/batch-2-r3.md:15690: trailing whitespace.
+   498	
.oracle/checkins/batch-2-r3.md:15691: trailing whitespace.
+   499	
.oracle/checkins/batch-2-r3.md:15702: trailing whitespace.
+   649	
.oracle/checkins/batch-2-r3.md:15703: trailing whitespace.
+   650	
.oracle/checkins/batch-2-r3.md:15713: trailing whitespace.
+   660	
.oracle/checkins/batch-2-r3.md:15773: trailing whitespace.
+   720	
.oracle/checkins/batch-2-r3.md:15801: trailing whitespace.
+  1184	
.oracle/checkins/batch-2-r3.md:15855: trailing whitespace.
+  1238	
.oracle/checkins/batch-2-r3.md:15885: trailing whitespace.
+  1277	
.oracle/checkins/batch-2-r3.md:15886: trailing whitespace.
+  1278	
.oracle/checkins/batch-2-r3.md:16047: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:16052: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r3.md:16054: trailing whitespace.
+     9	
.oracle/checkins/batch-2-r3.md:16064: trailing whitespace.
+    19	
.oracle/checkins/batch-2-r3.md:16065: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r3.md:16068: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r3.md:16069: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r3.md:16084: trailing whitespace.
+    39	
.oracle/checkins/batch-2-r3.md:16085: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r3.md:16092: trailing whitespace.
+    47	
.oracle/checkins/batch-2-r3.md:16100: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r3.md:16109: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r3.md:16110: trailing whitespace.
+    65	
.oracle/checkins/batch-2-r3.md:16120: trailing whitespace.
+    75	
.oracle/checkins/batch-2-r3.md:16126: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r3.md:16131: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r3.md:16137: trailing whitespace.
+    92	
.oracle/checkins/batch-2-r3.md:16141: trailing whitespace.
+    96	
.oracle/checkins/batch-2-r3.md:16153: trailing whitespace.
+   108	
.oracle/checkins/batch-2-r3.md:16159: trailing whitespace.
+   114	
.oracle/checkins/batch-2-r3.md:16164: trailing whitespace.
+   119	
.oracle/checkins/batch-2-r3.md:16174: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r3.md:16175: trailing whitespace.
+   130	
.oracle/checkins/batch-2-r3.md:16180: trailing whitespace.
+   135	
.oracle/checkins/batch-2-r3.md:16183: trailing whitespace.
+   138	
.oracle/checkins/batch-2-r3.md:16194: trailing whitespace.
+   149	
.oracle/checkins/batch-2-r3.md:16206: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r3.md:16207: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r3.md:16232: trailing whitespace.
+   187	
.oracle/checkins/batch-2-r3.md:16250: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r3.md:16262: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r3.md:16263: trailing whitespace.
+   218	
.oracle/checkins/batch-2-r3.md:16283: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r3.md:16292: trailing whitespace.
+   247	
.oracle/checkins/batch-2-r3.md:16298: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r3.md:16299: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r3.md:16307: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r3.md:16310: trailing whitespace.
+   265	
.oracle/checkins/batch-2-r3.md:16320: trailing whitespace.
+   275	
.oracle/checkins/batch-2-r3.md:16335: trailing whitespace.
+  1443	
.oracle/checkins/batch-2-r3.md:16336: trailing whitespace.
+  1444	
.oracle/checkins/batch-2-r3.md:16350: trailing whitespace.
+  1458	
.oracle/checkins/batch-2-r3.md:16371: trailing whitespace.
+  1479	
.oracle/checkins/batch-2-r3.md:16372: trailing whitespace.
+  1480	
.oracle/checkins/batch-2-r3.md:16432: trailing whitespace.
+   922	
.oracle/checkins/batch-2-r3.md:16435: trailing whitespace.
+   925	
.oracle/checkins/batch-2-r3.md:16449: trailing whitespace.
+   939	
.oracle/checkins/batch-2-r3.md:16469: trailing whitespace.
+   959	
.oracle/checkins/batch-2-r3.md:16470: trailing whitespace.
+   960	
.oracle/checkins/batch-2-r3.md:16473: trailing whitespace.
+   963	
.oracle/checkins/batch-2-r3.md:16474: trailing whitespace.
+   964	
.oracle/checkins/batch-2-r3.md:16480: trailing whitespace.
+   970	
.oracle/checkins/batch-2-r3.md:16485: trailing whitespace.
+   975	
.oracle/checkins/batch-2-r3.md:16499: trailing whitespace.
+   989	
.oracle/checkins/batch-2-r3.md:16500: trailing whitespace.
+   990	
.oracle/checkins/batch-2-r3.md:16511: trailing whitespace.
+  1001	
.oracle/checkins/batch-2-r3.md:16512: trailing whitespace.
+  1002	
.oracle/checkins/batch-2-r3.md:16519: trailing whitespace.
+  1009	
.oracle/checkins/batch-2-r3.md:16520: trailing whitespace.
+  1010	
.oracle/checkins/batch-2-r3.md:16544: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r3.md:16547: trailing whitespace.
+   397	
.oracle/checkins/batch-2-r3.md:16808: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16810: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16812: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16814: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16815: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16816: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16817: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16818: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16820: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16822: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16824: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16825: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:16869: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16874: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16879: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16881: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16891: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16892: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16896: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16897: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16901: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16904: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16929: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16930: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16934: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16943: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16944: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16953: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16956: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16957: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16961: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16968: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16969: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16973: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16974: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16978: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:16979: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17002: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17003: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17036: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17037: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17059: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17069: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17073: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17074: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17077: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17080: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17081: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17094: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17095: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17115: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17116: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17158: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17159: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17173: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17182: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17186: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17187: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17197: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17214: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17237: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17238: trailing whitespace.
+ 
.oracle/checkins/batch-2-r3.md:17302: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r3.md:17306: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r3.md:17308: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r3.md:17322: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r3.md:17324: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r3.md:17337: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r3.md:17338: trailing whitespace.
+    38	
.oracle/checkins/batch-2-r3.md:17341: trailing whitespace.
+    41	
.oracle/checkins/batch-2-r3.md:17369: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r3.md:17370: trailing whitespace.
+    70	
.oracle/checkins/batch-2-r3.md:17373: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r3.md:17379: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r3.md:17398: trailing whitespace.
+    98	
.oracle/checkins/batch-2-r3.md:17413: trailing whitespace.
+   113	
.oracle/checkins/batch-2-r3.md:17420: trailing whitespace.
+   120	
.oracle/checkins/batch-2-r3.md:17426: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r3.md:17444: trailing whitespace.
+   144	
.oracle/checkins/batch-2-r3.md:17461: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:17463: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:17465: trailing whitespace.
+web search: 
.oracle/checkins/batch-2-r3.md:17466: trailing whitespace.
+web search: 

exec
/bin/zsh -lc 'git diff --find-renames --unified=100 8c195bf0..9db48731 -- astrid/core/media.py astrid/core/rendering/artifacts.py astrid/core/rendering/publication.py astrid/core/rendering/transport.py astrid/packs/rendering/executors/render/run.py tests/core/util/test_media.py tests/fixtures/renderer_packs/raw_command/backend.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/media.py b/astrid/core/media.py
index c120b9c9..15543e71 100644
--- a/astrid/core/media.py
+++ b/astrid/core/media.py
@@ -1,333 +1,325 @@
 """Canonical shared media-probing helpers.
 
 This is the canonical location for shared media utilities.
 Any callers outside ``astrid/core/`` should import from here.
 """
 
 from __future__ import annotations
 
 import json
 import shutil
 import subprocess
 from collections.abc import Mapping
 from dataclasses import dataclass, field
 from fractions import Fraction
 from pathlib import Path
 from typing import Any, Callable
 
 from astrid.core.subprocess_env import build_child_subprocess_env
 
 Runner = Callable[..., subprocess.CompletedProcess[str]]
 
 
 # ---------------------------------------------------------------------------
 # MediaProbe – structured ffprobe metadata
 # ---------------------------------------------------------------------------
 
 
 @dataclass
 class MediaProbe:
     """Best-effort media metadata extracted via ffprobe.
 
     All fields are ``None`` when ffprobe is unavailable or fails.
     """
 
     duration_seconds: float | None = None
     fps: float | None = None
     resolution: str | None = None
     width: int | None = None
     height: int | None = None
 
     _raw: dict[str, Any] = field(default_factory=dict, repr=False)
 
     # Exact/profile fields used by rendering.  They follow the legacy fields
     # (and ``_raw``) so existing positional construction keeps its meaning.
     fps_rational: tuple[int, int] | None = None
     time_base: tuple[int, int] | None = None
     video_codec: str | None = None
     video_profile: str | None = None
     video_level: str | None = None
     pixel_format: str | None = None
     audio_codec: str | None = None
     audio_sample_rate: int | None = None
     audio_channel_layout: str | None = None
+    audio_channels: int | None = None
     container: str | None = None
     format_name: str | None = None
     duration_rational: tuple[int, int] | None = None
     video_stream_present: bool | None = None
     audio_stream_present: bool | None = None
 
     @property
     def codec(self) -> str | None:
         """Compatibility shorthand for the primary video codec."""
 
         return self.video_codec
 
     @property
     def duration(self) -> float | None:
         """Compatibility shorthand for :attr:`duration_seconds`."""
 
         return self.duration_seconds
 
     @property
     def has_video_stream(self) -> bool:
         if self.video_stream_present is not None:
             return self.video_stream_present
         return self.video_codec is not None or (
             self.width is not None and self.height is not None
         )
 
     @property
     def has_audio_stream(self) -> bool:
         if self.audio_stream_present is not None:
             return self.audio_stream_present
         return self.audio_codec is not None
 
 
 class MediaProbeError(RuntimeError):
     """Raised when a fail-closed media probe cannot produce metadata."""
 
 
 def _positive_rational(value: Any) -> tuple[int, int] | None:
     """Parse an ffprobe rational without routing through a float."""
 
     if not isinstance(value, str) or "/" not in value:
         return None
     numerator_text, denominator_text = value.split("/", 1)
     try:
         numerator = int(numerator_text)
         denominator = int(denominator_text)
     except (TypeError, ValueError):
         return None
     if numerator <= 0 or denominator <= 0:
         return None
     rational = Fraction(numerator, denominator)
     return rational.numerator, rational.denominator
 
 
 def _duration_rational(value: Any) -> tuple[int, int] | None:
     if value is None:
         return None
     try:
         rational = Fraction(str(value))
     except (ValueError, ZeroDivisionError):
         return None
     if rational < 0:
         return None
     return rational.numerator, rational.denominator
 
 
 def _nonempty_string(value: Any) -> str | None:
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
         probe.audio_channel_layout = _nonempty_string(
             audio_stream.get("channel_layout")
         )
-        # Some containers (e.g. QuickTime sowt) report channel counts without
-        # a channel_layout; derive the standard layout only for unambiguous
-        # channel counts (mono/stereo). 5.1/7.1 have multiple speaker
-        # variants, so those stay unprobed rather than guessed.
-        if probe.audio_channel_layout is None:
-            channels = _int_or_none(audio_stream.get("channels"), minimum=1)
-            probe.audio_channel_layout = {
-                1: "mono",
-                2: "stereo",
-            }.get(channels or 0)
+        probe.audio_channels = _int_or_none(audio_stream.get("channels"), minimum=1)
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
diff --git a/astrid/core/rendering/artifacts.py b/astrid/core/rendering/artifacts.py
index d3a83193..92629b49 100644
--- a/astrid/core/rendering/artifacts.py
+++ b/astrid/core/rendering/artifacts.py
@@ -350,224 +350,252 @@ def _compare_declared_to_expected(
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
             actual_audio=False,
         )
 
 
 def _probe_required_video(probe: MediaProbe) -> None:
     if not isinstance(probe, MediaProbe):
         _invalid(
             "incomplete_probe",
             "strict ffprobe returned an invalid probe object",
             received_type=type(probe).__name__,
         )
     if not probe.has_video_stream:
         _invalid("missing_video_stream", "primary video has no video stream")
     missing = [
         field
         for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
         if getattr(probe, field) is None
     ]
     if probe.container is None and probe.format_name is None:
         missing.append("container")
     if probe.duration_rational is None and probe.duration_seconds is None:
         missing.append("duration")
     if missing:
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
+            if field == "audio_channel_layout" and actual is None:
+                # Some containers (QuickTime sowt) expose channel COUNT but
+                # not a named layout. Compare channel count against the
+                # declared layout's canonical count instead of failing.
+                expected_channels = _layout_channel_count(expected)
+                if expected_channels is None or probe.audio_channels != expected_channels:
+                    _invalid(
+                        "audio_profile_mismatch",
+                        f"probed audio channel layout/count does not match {label}",
+                        field=field,
+                        expected=expected,
+                        actual=actual,
+                        probed_channels=probe.audio_channels,
+                    )
+                continue
             if not _same_profile_value(field, actual, expected):
                 _invalid(
                     "audio_profile_mismatch",
                     f"probed audio {field} does not match {label}",
                     field=field,
                     expected=expected,
                     actual=actual,
                 )
 
 
+def _layout_channel_count(layout: str | None) -> int | None:
+    return {
+        "mono": 1,
+        "stereo": 2,
+        "5.1": 6,
+        "5.1(side)": 6,
+        "7.1": 8,
+        "7.1(wide)": 8,
+    }.get(layout or "")
+
+
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
-            for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout")
+            for field in ("audio_codec", "audio_sample_rate")
             if getattr(probe, field) is None
         ]
+        if probe.audio_channel_layout is None and probe.audio_channels is None:
+            missing.append("audio_channel_layout/audio_channels")
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
             actual_duration_frames_rational=[actual_frames.numerator, actual_frames.denominator],
             tolerance_frames=expected.duration_tolerance,
         )
 
 
 def _validate_attachment(
     key: Any,
     attachment: Any,
     *,
     root: Path,
 ) -> None:
     if not isinstance(key, str) or not _OUTPUT_NAME_RE.fullmatch(key):
         _invalid(
             "invalid_attachment",
             "attachment map key must be a portable name",
             attachment_name=key if isinstance(key, str) else None,
         )
     if not isinstance(attachment, Attachment):
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index dd820fb2..8a094907 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -1,347 +1,384 @@
 """Locked publication for one rendered video and its provenance sidecar.
 
 The provenance sidecar is the commit marker.  A video without a valid
 sidecar is deliberately visible (and therefore recoverable), but it is never
 considered a committed render result.
 """
 
 from __future__ import annotations
 
 import fcntl
 import json
 import os
 import re
 import time
 from collections.abc import Iterable, Mapping
 from pathlib import Path
 from typing import Any
 
 from astrid.core.foundation.atomic_io import write_json_atomic
 from astrid.core.foundation.hash import sha256_file
 
 from .errors import raise_invalid_artifact_error
 
 try:
     from filelock import FileLock, Timeout
 except ImportError:  # pragma: no cover - exercised only without optional dep.
     FileLock = None  # type: ignore[assignment]
 
     class Timeout(Exception):
         pass
 
 
 _BACKEND = "astrid.core"
 _RECOVERY = "rerender the video and retry publication"
 _SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
 
 
 class _FcntlLock:
     """Small ``filelock``-compatible fallback used by the asset cache too."""
 
     def __init__(self, path: Path) -> None:
         self.path = Path(path)
         self._handle: Any | None = None
 
     def acquire(self, timeout: float | None = None) -> _FcntlLock:
         self.path.parent.mkdir(parents=True, exist_ok=True)
         self._handle = self.path.open("a+b")
         deadline = None if timeout is None or timeout < 0 else time.monotonic() + timeout
         while True:
             try:
                 fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                 return self
             except BlockingIOError as exc:
                 if timeout == 0 or (deadline is not None and time.monotonic() >= deadline):
                     self._handle.close()
                     self._handle = None
                     raise Timeout(str(self.path)) from exc
                 time.sleep(0.05)
 
     def release(self) -> None:
         if self._handle is None:
             return
         fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
         self._handle.close()
         self._handle = None
 
     def __enter__(self) -> _FcntlLock:
         return self.acquire()
 
     def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
         self.release()
 
 
 def _lock_for(path: Path) -> Any:
     """Return the per-output lock at ``<output>.lock``."""
 
     lock_path = Path(f"{path}.lock")
     if FileLock is not None:
         return FileLock(str(lock_path))
     return _FcntlLock(lock_path)
 
 
 def _default_sidecar_path(video_path: Path) -> Path:
     return Path(f"{video_path}.provenance.json")
 
 
 def _resolved(path: str | Path) -> Path:
     return Path(path).expanduser().resolve(strict=False)
 
 
+def _contains_symlink_component(path: str | Path) -> bool:
+    """True if a non-system path component is a symbolic link.
+
+    macOS resolves ``/tmp`` -> ``/private/tmp`` and ``/var`` ->
+    ``/private/var``; those system redirects are not containment escapes.
+    Any other symlink component (e.g. a symlinked run directory) is treated
+    as an escape and rejected.
+    """
+    current = Path(path).expanduser()
+    parts = list(current.parts)
+    for index in range(len(parts), 0, -1):
+        candidate = Path(*parts[:index])
+        try:
+            if not candidate.is_symlink():
+                continue
+        except OSError:
+            return True
+        try:
+            resolved = candidate.resolve(strict=False)
+        except (OSError, RuntimeError):
+            return True
+        # System redirects: /tmp, /var, /etc, /private/* -> /private/*
+        if str(resolved).startswith("/private/"):
+            continue
+        if candidate.name in ("tmp", "var", "etc", "home", "usr") and str(resolved).startswith("/"):
+            continue
+        return True
+    return False
+
+
 def _invalid_video(video_path: Path, *, reason: str, message: str) -> None:
     raise_invalid_artifact_error(
         backend=_BACKEND,
         message=message,
         recovery_command=_RECOVERY,
         details={"reason": reason, "path": str(video_path)},
     )
 
 
 def _validate_source_video(video_path: Path) -> None:
     try:
         exists = video_path.is_file()
     except OSError:
         exists = False
     if not exists:
         _invalid_video(
             video_path,
             reason="missing_artifact",
             message=f"rendered video does not exist: {video_path}",
         )
     try:
         size = video_path.stat().st_size
     except OSError:
         _invalid_video(
             video_path,
             reason="missing_artifact",
             message=f"rendered video cannot be read: {video_path}",
         )
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
-        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
+        if (
+            _contains_symlink_component(video_unresolved)
+            or _contains_symlink_component(sidecar_unresolved)
+        ):
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
         # Never delete through a symlink: neither the raw video nor the raw
         # sidecar path may be a link (the resolved pair may point elsewhere).
         raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
         raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
         try:
             raw_path = Path(raw_candidate).expanduser()
-            if raw_path.is_symlink():
+            if _contains_symlink_component(raw_path):
                 continue
         except (OSError, TypeError):
             continue
         try:
             # For bare paths the default sidecar is derived from the raw
             # video path; it must be checked unresolved like an explicit one.
             raw_sidecar = (
                 Path(raw_sidecar_candidate).expanduser()
                 if raw_sidecar_candidate is not None
                 else _default_sidecar_path(raw_path)
             )
-            if raw_sidecar.is_symlink():
+            if _contains_symlink_component(raw_sidecar):
                 continue
         except (OSError, TypeError):
             continue
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
-    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
+    if (
+        _contains_symlink_component(source_unresolved)
+        or _contains_symlink_component(output_unresolved)
+        or _contains_symlink_component(sidecar_unresolved)
+    ):
         raise_invalid_artifact_error(
             backend=_BACKEND,
-            message="publication paths must not be symbolic links",
+            message="publication paths must not be symbolic links (or contain symlinked directories)",
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
 
 
 __all__ = [
     "is_render_result_committed",
     "publish_render_result",
     "read_committed_provenance",
 ]
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index 44671dd2..74f0919a 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -399,216 +399,230 @@ def _resolve_executable(
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
     except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
         captured = None
         # Interruption or a communicate failure during the grace window must
         # not abandon the group: escalate to SIGKILL right away and reap in
         # the loop below.
         try:
             _signal_process_group(process, signal.SIGKILL)
         except OSError:
             pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
         try:
             time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
         except KeyboardInterrupt:
             try:
                 _signal_process_group(process, signal.SIGKILL)
             except OSError:
                 pass
             break
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
         drain_deadline = time.monotonic() + max(grace, 2.0)
         while True:
             try:
-                captured = process.communicate()
+                captured = process.communicate(timeout=max(grace, 2.0))
                 break
+            except subprocess.TimeoutExpired:
+                try:
+                    _signal_process_group(process, signal.SIGKILL)
+                except (OSError, PermissionError):
+                    pass
+                if time.monotonic() > drain_deadline:
+                    break
+                continue
             except KeyboardInterrupt:
                 try:
                     _signal_process_group(process, signal.SIGKILL)
                 except (OSError, PermissionError):
                     pass
                 if time.monotonic() > drain_deadline:
-                    process.kill()
-                    captured = process.communicate()
                     break
                 continue
     elif captured is None:
         # ``poll`` may have reaped the child while checking the fallback path.
-        # Its pipes still need to be drained, and communicate is safe here.
-        captured = process.communicate()
+        # Its pipes still need to be drained; bound the drain so cleanup can
+        # never block forever on a stuck pipe.
+        try:
+            captured = process.communicate(timeout=max(grace, 2.0))
+        except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
+            try:
+                _signal_process_group(process, signal.SIGKILL)
+            except (OSError, PermissionError):
+                pass
+            captured = ("", "")
 
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
         try:
             time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
         except KeyboardInterrupt:
             try:
                 _signal_process_group(process, signal.SIGKILL)
             except OSError:
                 pass
             break
     if _process_group_exists(process):
         _signal_process_group(process, signal.SIGKILL)
         _wait_for_group_exit(process, timeout=grace)
 
 
 def _wait_for_group_exit(
     process: subprocess.Popen[str], *, timeout: float
 ) -> None:
     deadline = time.monotonic() + timeout
     while _process_group_exists(process) and time.monotonic() < deadline:
         try:
             time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
         except KeyboardInterrupt:
             try:
                 _signal_process_group(process, signal.SIGKILL)
             except OSError:
                 pass
             break
     # Escalate to SIGKILL for the remaining grace window (bounded) so a
     # SIGTERM-ignoring group cannot survive cleanup.
     kill_deadline = time.monotonic() + max(timeout, 1.0)
     while _process_group_exists(process) and time.monotonic() < kill_deadline:
         try:
             _signal_process_group(process, signal.SIGKILL)
         except (OSError, PermissionError):
             break
         try:
             time.sleep(0.01)
         except KeyboardInterrupt:
             break
 
 
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
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index 35c58bfe..8323c223 100644
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -346,207 +346,208 @@ def _render_ffmpeg_media_to_path(timeline_path: Path, assets_path: Path, out_pat
     if len(video_clips) == 1:
         clip = video_clips[0]
         asset_key = str(clip["asset"])
         entry = registry["assets"][asset_key]
         source_duration = entry.get("duration")
         source_resolution = entry.get("resolution")
         start = float(clip.get("from", 0) or 0)
         end = float(clip.get("to", start) or start)
         at = float(clip.get("at", 0) or 0)
         full_duration = isinstance(source_duration, (int, float)) and abs((end - start) - float(source_duration)) < 0.05
         same_resolution = source_resolution == f"{width}x{height}"
         no_visual_adjustments = not any(
             key in clip
             for key in ("x", "y", "width", "height", "cropTop", "cropBottom", "cropLeft", "cropRight", "effects", "transition")
         )
         if at == 0 and start == 0 and full_duration and same_resolution and no_visual_adjustments:
             copy_video_input = asset_index[asset_key]
     if copy_video_input is None:
         for index, clip in enumerate(video_clips):
             inp = asset_index[str(clip["asset"])]
             start = float(clip.get("from", 0) or 0)
             end = float(clip.get("to", start) or start)
             label = f"v{index}"
             filters.append(
                 f"[{inp}:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS,"
                 f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                 f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                 f"fps={fps},format=yuv420p[{label}]"
             )
             video_labels.append(f"[{label}]")
         filters.append("".join(video_labels) + f"concat=n={len(video_labels)}:v=1:a=0[vout]")
 
     audio_labels: list[str] = []
     cursor = 0.0
     audio_index = 0
     for clip in audio_clips:
         at = float(clip.get("at", 0) or 0)
         if at > cursor + 0.001:
             duration = at - cursor
             label = f"a{audio_index}"
             filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[{label}]")
             audio_labels.append(f"[{label}]")
             audio_index += 1
         inp = asset_index[str(clip["asset"])]
         start = float(clip.get("from", 0) or 0)
         end = float(clip.get("to", start) or start)
         volume = float(clip.get("volume", 1) or 0)
         label = f"a{audio_index}"
         filters.append(
             f"[{inp}:a]atrim=start={start:.6f}:end={end:.6f},"
             f"asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,"
             f"volume={volume:.6f}[{label}]"
         )
         audio_labels.append(f"[{label}]")
         cursor = at + _clip_duration_seconds(clip)
         audio_index += 1
     if not audio_labels:
         duration = sum(_clip_duration_seconds(clip) for clip in video_clips)
         filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[a0]")
         audio_labels.append("[a0]")
     filters.append("".join(audio_labels) + f"concat=n={len(audio_labels)}:v=0:a=1[aout]")
 
     out_path.parent.mkdir(parents=True, exist_ok=True)
     subprocess.run(
         [
             "ffmpeg",
             "-hide_banner",
             "-y",
             *inputs,
             "-filter_complex",
             ";".join(filters),
             "-map",
             f"{copy_video_input}:v:0" if copy_video_input is not None else "[vout]",
             "-map",
             "[aout]",
             "-c:v",
             "copy" if copy_video_input is not None else "libx264",
             *(["-preset", "veryfast", "-crf", "20"] if copy_video_input is None else []),
             "-c:a",
             "aac",
             "-b:a",
             "192k",
             "-movflags",
             "+faststart",
             str(out_path),
         ],
         check=True,
     )
     return out_path
 
 
 def _render_ffmpeg_media(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     _previous_outputs: Sequence[Path] | None = None,
 ) -> Path:
     """Render FFmpeg output privately, then publish the committed pair."""
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
     with TemporaryDirectory(
-        prefix=f".{out_path.name}.publication-",
-        dir=str(out_path.parent),
+        prefix=f".{resolved_out.name}.publication-",
+        dir=str(resolved_out.parent),
     ) as publication_tmp:
-        staged_video = Path(publication_tmp) / out_path.name
+        staged_video = Path(publication_tmp) / resolved_out.name
         _render_ffmpeg_media_to_path(timeline_path, assets_path, staged_video)
         provenance = _render_provenance_payload(
             out_path,
             engine="ffmpeg",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=REPO_ROOT / "remotion",
             composition_id="TimelineComposition",
             theme_path=None,
             active_theme=None,
             registry_state=_effective_registry_state(None),
             stage_summary={"root": None, "effects": []},
         )
         output = publish_render_result(
             staged_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=(
                 _PUBLICATION_PREVIOUS_OUTPUTS.get()
                 if _previous_outputs is None
                 else _previous_outputs
             ),
         )
 
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_ffmpeg")
         assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_ffmpeg")
         render_id = audit.register_asset(
             kind="render",
             path=output,
             label="Rendered video",
             parents=[timeline_id, assets_id],
             stage="render_ffmpeg",
             metadata={"engine": "ffmpeg"},
         )
         audit.register_node(
             stage="render_ffmpeg",
             label="Render media-only timeline with ffmpeg",
             parents=[timeline_id, assets_id],
             outputs=[render_id],
             metadata={"engine": "ffmpeg"},
         )
     return output
 
 
 def _can_render_with_ffmpeg_media(timeline_path: Path, assets_path: Path) -> bool:
     try:
         timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
         timeline.load_registry(assets_path)
         _validate_ffmpeg_media_timeline(timeline_data)
         tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
         has_visual_media_clip = any(
             clip.get("clipType") == "media"
             and tracks.get(clip.get("track"), {}).get("kind") == "visual"
             for clip in timeline_data.get("clips", [])
         )
     except Exception:
         return False
     return has_visual_media_clip
 
 
 def _complex_clip_windows(timeline_data: dict, fps: int, *, handle_seconds: float = 0.25) -> list[tuple[float, float]]:
     duration = _timeline_duration_seconds(timeline_data)
     tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
     visual_track_ids = {track.get("id") for track in timeline_data.get("tracks", []) if track.get("kind") == "visual"}
     visual_media_coverage: dict[str, float] = {}
     for candidate in timeline_data.get("clips", []):
         if candidate.get("clipType") != "media" or candidate.get("track") not in visual_track_ids:
             continue
         track_id = str(candidate.get("track"))
         visual_media_coverage[track_id] = visual_media_coverage.get(track_id, 0.0) + _clip_duration_seconds(candidate)
     base_visual_track_id = max(visual_media_coverage, key=visual_media_coverage.get) if visual_media_coverage else None
     windows: list[tuple[float, float]] = []
     clips = timeline_data.get("clips", [])
     for index, clip in enumerate(clips):
         media_clip = clip.get("clipType") == "media"
         if media_clip:
             track = tracks.get(clip.get("track"), {})
             params = clip.get("params") if isinstance(clip.get("params"), dict) else {}
             effects = clip.get("effects")
             has_effects = bool(effects)
             has_transition = bool(clip.get("transition"))
             has_overlay_track = track.get("kind") == "visual" and clip.get("track") != base_visual_track_id
             has_opacity = isinstance(clip.get("opacity"), (int, float)) and float(clip.get("opacity") or 0) != 1.0
             has_audio_fade = track.get("kind") == "audio" and (
                 isinstance(params.get("fadeIn"), (int, float)) or isinstance(params.get("fadeOut"), (int, float))
             )
             if not (has_effects or has_transition or has_overlay_track or has_opacity or has_audio_fade):
                 continue
             next_same_track = next(
                 (candidate for candidate in clips[index + 1 :] if candidate.get("track") == clip.get("track")),
                 None,
             )
             if has_transition and next_same_track is not None:
                 transition = clip.get("transition")
                 transition_seconds = 8 / fps
                 if isinstance(transition, dict):
                     if isinstance(transition.get("duration"), (int, float)):
@@ -561,203 +562,204 @@ def _complex_clip_windows(timeline_data: dict, fps: int, *, handle_seconds: floa
                     windows.append(
                         (
                             _round_frame_time(start, fps, mode="floor"),
                             _round_frame_time(end, fps, mode="ceil"),
                         )
                     )
                 continue
         start = max(0.0, float(clip.get("at", 0) or 0) - handle_seconds)
         end = min(duration, _clip_timeline_end_seconds(clip) + handle_seconds)
         if end <= start:
             continue
         windows.append(
             (
                 _round_frame_time(start, fps, mode="floor"),
                 _round_frame_time(end, fps, mode="ceil"),
             )
         )
     if not windows:
         return []
     windows.sort()
     merged: list[tuple[float, float]] = []
     for start, end in windows:
         if not merged or start > merged[-1][1]:
             merged.append((start, end))
         else:
             merged[-1] = (merged[-1][0], max(merged[-1][1], end))
     return merged
 
 
 def _hybrid_segments(timeline_data: dict) -> list[dict[str, float | str]]:
     _width, _height, fps = _timeline_canvas(timeline_data)
     duration = _round_frame_time(_timeline_duration_seconds(timeline_data), fps, mode="ceil")
     complex_windows = _complex_clip_windows(timeline_data, fps)
     if not complex_windows:
         return [{"engine": "ffmpeg", "from": 0.0, "to": duration}]
     segments: list[dict[str, float | str]] = []
     cursor = 0.0
     for start, end in complex_windows:
         start = max(0.0, min(start, duration))
         end = max(start, min(end, duration))
         if start > cursor:
             segments.append({"engine": "ffmpeg", "from": cursor, "to": start})
         if end > start:
             segments.append({"engine": "remotion", "from": start, "to": end})
         cursor = max(cursor, end)
     if cursor < duration:
         segments.append({"engine": "ffmpeg", "from": cursor, "to": duration})
     return [segment for segment in segments if float(segment["to"]) > float(segment["from"])]
 
 
 def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
     inputs: list[str] = []
     filters: list[str] = []
     concat_inputs: list[str] = []
     for index, path in enumerate(segment_paths):
         inputs.extend(["-i", str(path)])
         filters.append(f"[{index}:v]setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{index}]")
         filters.append(f"[{index}:a]asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a{index}]")
         concat_inputs.append(f"[v{index}][a{index}]")
     filters.append("".join(concat_inputs) + f"concat=n={len(segment_paths)}:v=1:a=1[vout][aout]")
     subprocess.run(
         [
             "ffmpeg",
             "-hide_banner",
             "-y",
             *inputs,
             "-filter_complex",
             ";".join(filters),
             "-map",
             "[vout]",
             "-map",
             "[aout]",
             "-c:v",
             "libx264",
             "-preset",
             "veryfast",
             "-crf",
             "20",
             "-c:a",
             "aac",
             "-b:a",
             "192k",
             "-movflags",
             "+faststart",
             str(out_path),
         ],
         check=True,
     )
 
 
 def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
     if not timeline_path.exists():
         raise FileNotFoundError(f"Timeline missing: {timeline_path}")
     if not assets_path.exists():
         raise FileNotFoundError(f"Asset registry missing: {assets_path}")
     timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
     segments = _hybrid_segments(timeline_data)
     if len(segments) == 1 and segments[0]["engine"] == "ffmpeg":
         return _render_ffmpeg_media(timeline_path, assets_path, out_path)
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
-    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(out_path.parent)) as tmp:
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
+    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
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
         _concat_segments(segment_paths, staged_video)
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
 
 
 def _timeline_composition_src(project_dir: Path) -> Path | None:
     composition_src = project_dir / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
     return composition_src if composition_src.is_dir() else None
 
 
 def _registry_output_paths(project_dir: Path) -> list[Path]:
     composition_src = _timeline_composition_src(project_dir)
     package_src = composition_src or (WORKSPACE_ROOT / "packages" / "timeline-composition" / "typescript" / "src")
     paths = [
         package_src / f"{kind}.generated.ts"
         for kind in ("effects", "animations", "transitions")
     ]
     remotion_src = REPO_ROOT / "remotion" / "src"
     for kind in ("effects", "animations", "transitions"):
         base = remotion_src / f"{kind}.generated"
         paths.extend(Path(f"{base}{extension}") for extension in gen_effect_registry.SHIM_EXTENSIONS)
     return paths
 
 
 def _registry_outputs_exist(project_dir: Path) -> bool:
     return all(path.exists() for path in _registry_output_paths(project_dir))
@@ -1085,226 +1087,227 @@ def _write_render_provenance(
     segment_provenance: list[dict[str, Any]] | None = None,
 ) -> Path:
     payload = _render_provenance_payload(
         out_path,
         engine=engine,
         timeline_path=timeline_path,
         assets_path=assets_path,
         project_dir=project_dir,
         composition_id=composition_id,
         theme_path=theme_path,
         active_theme=active_theme,
         registry_state=registry_state,
         stage_summary=stage_summary,
         segments=segments,
         segment_provenance=segment_provenance,
     )
     sidecar_path = _render_provenance_sidecar_path(out_path)
     write_json_atomic(sidecar_path, payload)
     return sidecar_path
 
 
 def _stderr_tail(stderr: str) -> str:
     lines = stderr.splitlines()
     tail = lines[-40:] if len(lines) > 40 else lines
     return "\n".join(tail).strip()
 
 
 def _require_free_space(path: Path, min_free_gb: float | None) -> None:
     if min_free_gb is None or min_free_gb <= 0:
         return
     target = path if path.exists() else path.parent
     usage = shutil.disk_usage(target)
     min_free = int(min_free_gb * 1024 * 1024 * 1024)
     if usage.free < min_free:
         free_gb = usage.free / (1024 * 1024 * 1024)
         raise RuntimeError(
             f"Remotion render needs at least {min_free_gb:.1f} GiB free at {target}; "
             f"only {free_gb:.1f} GiB is available"
         )
 
 
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
 
 
 def _audio_reactive_ffmpeg_element(
     theme_path: Path | None,
 ) -> ElementDefinition | None:
     effects, _aliases = _effect_registry_for_assets(theme_path)
     element = effects.get(audio_reactive_colour.EFFECT_ID)
     if (
         element is None
         or element.metadata.get("ffmpegAdapter")
         != audio_reactive_colour.ADAPTER_ID
     ):
         return None
     return element
 
 
 def _render_audio_reactive_colour_if_supported(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     project_dir: Path | None,
     composition_id: str,
     theme_path: Path | None,
 ) -> Path | None:
     timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
     clips = timeline_data.get("clips")
     if (
         not isinstance(clips, list)
         or len(clips) != 2
         or sum(
             isinstance(clip, dict)
             and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
             for clip in clips
         )
         != 1
     ):
         return None
     element = _audio_reactive_ffmpeg_element(theme_path)
     if element is None:
         return None
     registry = timeline.load_registry(assets_path)
     spec = audio_reactive_colour.match_and_validate(
         timeline_data, registry, assets_path
     )
     if spec is None:
         return None
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
     stage_summary = {
         "root": None,
         "effects": [
             {
                 "effect_id": element.id,
                 "source_pack_id": _source_pack_id(element),
                 "source": element.source,
                 "element_root": str(element.root),
                 "clip_ids": [
                     str(clip.get("id"))
                     for clip in timeline_data.get("clips", [])
                     if isinstance(clip, dict)
                     and clip.get("clipType") == element.id
                 ],
                 "staged_asset_ids": [],
                 "staged_assets": {},
             }
         ],
     }
     with TemporaryDirectory(
-        prefix=f".{out_path.name}.publication-",
-        dir=str(out_path.parent),
+        prefix=f".{resolved_out.name}.publication-",
+        dir=str(resolved_out.parent),
     ) as publication_tmp:
-        staged_video = Path(publication_tmp) / out_path.name
+        staged_video = Path(publication_tmp) / resolved_out.name
         rendered_video = audio_reactive_colour.render(spec, staged_video)
         provenance = _render_provenance_payload(
             out_path,
             engine="ffmpeg",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=project_dir or (REPO_ROOT / "remotion"),
             composition_id=composition_id,
             theme_path=theme_path,
             active_theme=None,
             registry_state=_effective_registry_state(theme_path),
             stage_summary=stage_summary,
         )
         provenance["ffmpeg_specialization"] = audio_reactive_colour.ADAPTER_ID
         provenance["audio_reactive_colour"] = {
             "event_count": len(spec.events),
             "fps": spec.fps,
             "frame_count": spec.total_frames,
             "marker_sha256": spec.marker_sha256,
         }
         output = publish_render_result(
             rendered_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
         )
 
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(
             kind="timeline",
             path=timeline_path,
             label="Audio-reactive render timeline",
             stage="render_ffmpeg_audio_reactive_colour",
         )
         assets_id = audit.register_asset(
             kind="assets_registry",
             path=assets_path,
             label="Audio-reactive asset registry",
             stage="render_ffmpeg_audio_reactive_colour",
         )
         render_id = audit.register_asset(
             kind="render",
             path=output,
             label="Rendered audio-reactive colour video",
             parents=[timeline_id, assets_id],
             stage="render_ffmpeg_audio_reactive_colour",
             metadata={
                 "engine": "ffmpeg",
                 "specialization": audio_reactive_colour.ADAPTER_ID,
                 "event_count": len(spec.events),
                 "marker_sha256": spec.marker_sha256,
             },
         )
         audit.register_node(
             stage="render_ffmpeg_audio_reactive_colour",
             label="Render audio-reactive colour timeline with FFmpeg",
             parents=[timeline_id, assets_id],
             outputs=[render_id],
             metadata={
                 "engine": "ffmpeg",
                 "specialization": audio_reactive_colour.ADAPTER_ID,
             },
         )
     return output
 
 
 def _render_with_publication_context(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     engine: str = "remotion",
     project_dir: Path | None = None,
     composition_id: str = "TimelineComposition",
     theme_path: Path | None = None,
     min_free_gb: float | None = None,
 ) -> Path:
     out_path = Path(out_path)
     audio_reactive_output = _render_audio_reactive_colour_if_supported(
         timeline_path,
         assets_path,
         out_path,
         project_dir=project_dir,
         composition_id=composition_id,
         theme_path=theme_path,
     )
     if audio_reactive_output is not None:
         return audio_reactive_output
     if engine == "hybrid":
         return _render_hybrid(
             timeline_path,
             assets_path,
             out_path,
             project_dir=project_dir,
             composition_id=composition_id,
             theme_path=theme_path,
             min_free_gb=min_free_gb,
         )
diff --git a/tests/core/util/test_media.py b/tests/core/util/test_media.py
index 89ca645d..421b3bd7 100644
--- a/tests/core/util/test_media.py
+++ b/tests/core/util/test_media.py
@@ -87,230 +87,220 @@ def test_verify_uses_canonical_media_helper() -> None:
 
 HAPPY_FFPROBE_JSON = json.dumps(
     {
         "format": {
             "duration": "12.5",
             "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
         },
         "streams": [
             {
                 "codec_type": "video",
                 "codec_name": "h264",
                 "profile": "High",
                 "level": 41,
                 "pix_fmt": "yuv420p",
                 "width": 1920,
                 "height": 1080,
                 "avg_frame_rate": "30000/1001",
                 "r_frame_rate": "30000/1001",
                 "time_base": "1/30000",
                 "disposition": {"attached_pic": 0},
             },
             {
                 "codec_type": "audio",
                 "codec_name": "aac",
                 "sample_rate": "48000",
                 "channel_layout": "stereo",
             },
         ],
     }
 )
 
 
 class TestMediaProbeDefaults:
     """MediaProbe dataclass starts with all-None and _raw empty."""
 
     def test_default_all_none(self) -> None:
         probe = MediaProbe()
         assert probe.duration_seconds is None
         assert probe.fps is None
         assert probe.resolution is None
         assert probe.width is None
         assert probe.height is None
         assert probe._raw == {}
         assert probe.fps_rational is None
         assert probe.time_base is None
         assert probe.video_codec is None
         assert probe.pixel_format is None
         assert probe.audio_codec is None
         assert probe.audio_sample_rate is None
         assert probe.audio_channel_layout is None
         assert probe.has_video_stream is False
         assert probe.has_audio_stream is False
 
     def test_partial_construction(self) -> None:
         probe = MediaProbe(
             duration_seconds=5.0,
             width=640,
             height=480,
             resolution="640x480",
         )
         assert probe.duration_seconds == 5.0
         assert probe.fps is None
         assert probe.resolution == "640x480"
         assert probe.width == 640
         assert probe.height == 480
 
 
 class TestFfprobeMetadataHappy:
     """ffprobe_metadata extracts all fields from valid JSON output."""
 
     def test_extracts_all_fields(self) -> None:
         with patch("subprocess.run") as mock_run, patch(
             "shutil.which", return_value="/usr/bin/ffprobe"
         ):
             mock_run.return_value = subprocess.CompletedProcess(
                 [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
             )
             probe = ffprobe_metadata("video.mp4")
 
         assert probe.duration_seconds == pytest.approx(12.5)
         assert probe.fps == pytest.approx(30000 / 1001)
         assert probe.resolution == "1920x1080"
         assert probe.width == 1920
         assert probe.height == 1080
         assert probe.fps_rational == (30000, 1001)
         assert probe.time_base == (1, 30000)
         assert probe.video_codec == "h264"
         assert probe.codec == "h264"
         assert probe.video_profile == "High"
         assert probe.video_level == "41"
         assert probe.pixel_format == "yuv420p"
         assert probe.audio_codec == "aac"
         assert probe.audio_sample_rate == 48000
         assert probe.audio_channel_layout == "stereo"
         assert probe.container == "mp4"
         assert probe.duration_rational == (25, 2)
         assert probe.has_video_stream is True
         assert probe.has_audio_stream is True
         assert probe._raw  # raw JSON preserved
 
-    def test_layout_derived_from_unambiguous_channel_count(self) -> None:
-        """Containers that report channels without channel_layout (e.g.
-        QuickTime sowt) derive mono/stereo only — never ambiguous 5.1/7.1."""
+    def test_channels_reported_without_inferred_layout(self) -> None:
+        """Probes that report channel COUNT without channel_layout (e.g.
+        QuickTime sowt) must stay honest: layout stays None, channels is
+        reported, and validation compares counts (never guessed layouts)."""
         import json as _json
 
         payload = json.loads(HAPPY_FFPROBE_JSON)
         for stream in payload["streams"]:
             if stream.get("codec_type") == "audio":
                 del stream["channel_layout"]
                 stream["channels"] = 2
         with patch(
             "astrid.core.media.subprocess.run",
             return_value=subprocess.CompletedProcess(
                 [], 0, stdout=_json.dumps(payload), stderr=""
             ),
         ):
             probe = ffprobe_metadata("video.mp4")
-        assert probe.audio_channel_layout == "stereo"
-
-        for stream in payload["streams"]:
-            if stream.get("codec_type") == "audio":
-                stream["channels"] = 6
-        with patch(
-            "astrid.core.media.subprocess.run",
-            return_value=subprocess.CompletedProcess(
-                [], 0, stdout=_json.dumps(payload), stderr=""
-            ),
-        ):
-            probe = ffprobe_metadata("video.mp4")
-        assert probe.audio_channel_layout is None  # 5.1 variants ambiguous
+        assert probe.audio_channel_layout is None
+        assert probe.audio_channels == 2
 
     def test_accepts_path_object(self, tmp_path: Path) -> None:
         vid = tmp_path / "clip.mp4"
         vid.write_bytes(b"dummy")
         with patch("subprocess.run") as mock_run, patch(
             "shutil.which", return_value="/usr/bin/ffprobe"
         ):
             mock_run.return_value = subprocess.CompletedProcess(
                 [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
             )
             probe = ffprobe_metadata(vid)
 
         assert probe.duration_seconds == pytest.approx(12.5)
 
     def test_prefers_average_frame_rate_and_skips_attached_picture(self) -> None:
         payload = json.dumps(
             {
                 "format": {"duration": "2", "format_name": "matroska,webm"},
                 "streams": [
                     {
                         "codec_type": "video",
                         "codec_name": "mjpeg",
                         "disposition": {"attached_pic": 1},
                     },
                     {
                         "codec_type": "video",
                         "codec_name": "vp9",
                         "pix_fmt": "yuv420p",
                         "width": 1280,
                         "height": 720,
                         "avg_frame_rate": "24/1",
                         "r_frame_rate": "30/1",
                         "time_base": "1/1000",
                     },
                 ],
             }
         )
         with patch("subprocess.run") as mock_run, patch(
             "shutil.which", return_value="/usr/bin/ffprobe"
         ):
             mock_run.return_value = subprocess.CompletedProcess(
                 [], 0, stdout=payload, stderr=""
             )
             probe = ffprobe_metadata("video.webm")
 
         assert probe.video_codec == "vp9"
         assert probe.fps_rational == (24, 1)
         assert probe.container == "webm"
 
     def test_uses_r_frame_rate_when_average_is_unusable(self) -> None:
         payload = json.dumps(
             {
                 "format": {"duration": "1"},
                 "streams": [
                     {
                         "codec_type": "video",
                         "width": 320,
                         "height": 240,
                         "avg_frame_rate": "0/0",
                         "r_frame_rate": "25/1",
                     }
                 ],
             }
         )
         with patch("subprocess.run") as mock_run, patch(
             "shutil.which", return_value="/usr/bin/ffprobe"
         ):
             mock_run.return_value = subprocess.CompletedProcess(
                 [], 0, stdout=payload, stderr=""
             )
             probe = ffprobe_metadata("video.mp4")
 
         assert probe.fps_rational == (25, 1)
         assert probe.fps == 25.0
 
 
 class TestFfprobeMetadataDegraded:
     """ffprobe_metadata returns all-None MediaProbe on errors / missing ffprobe."""
 
     def test_no_ffprobe_on_path(self) -> None:
         with patch("shutil.which", return_value=None):
             probe = ffprobe_metadata("video.mp4")
         assert probe.duration_seconds is None
         assert probe.fps is None
         assert probe.resolution is None
         assert probe._raw == {}
 
     def test_nonzero_returncode(self) -> None:
         with patch("subprocess.run") as mock_run, patch(
             "shutil.which", return_value="/usr/bin/ffprobe"
         ):
             mock_run.return_value = subprocess.CompletedProcess(
                 [], 1, stdout="", stderr="error"
             )
             probe = ffprobe_metadata("video.mp4")
         assert probe.duration_seconds is None
 
     def test_strict_probe_raises_on_nonzero_returncode(self) -> None:
         with patch("subprocess.run") as mock_run, patch(
             "shutil.which", return_value="/usr/bin/ffprobe"
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 783fb243..ffdc422d 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -189,367 +189,387 @@ def _idr_slice_nal(frame_index: int) -> bytes:
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
+    # Canonical QuickTime channel layout atom (FFmpeg movenc format):
+    # version(2) + revision(2) + layout_tag(4) + bitmap(4) +
+    # num_descriptions(4). Stereo layout tag = 0x00650002.
+    chan = _box(
+        b"chan",
+        struct.pack(">H", 0)   # version
+        + struct.pack(">H", 0)  # revision
+        + struct.pack(">I", 0x00650002 if AUDIO_CHANNELS == 2 else 0x00650000)
+        + struct.pack(">I", 0)  # bitmap (kAudioChannelBit_None)
+        + struct.pack(">I", 0),  # num channel descriptions
+    )
     wave = _box(
         b"wave",
         _box(b"frma", b"sowt")
         + _box(b"enda", struct.pack(">H", 1))
-        + _box(
-            b"chan",
-            struct.pack(">I", 0)  # version/flags
-            + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)  # layout tag
-            + struct.pack(">I", 0),  # bitmap
-        ),
+        + chan,
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
     return _box(b"sowt", audio + wave)
 
 
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
     profile = request.get("profile")
     if isinstance(profile, dict):
-        # The renderer can only produce its own exact codec set; a request
-        # for a different codec is unsupported (fail closed).
-        if (
-            profile.get("audio_codec") not in (None, AUDIO_CODEC)
-            or profile.get("video_codec") not in (None, VIDEO_CODEC)
-            or profile.get("width") not in (None, WIDTH)
-            or profile.get("height") not in (None, HEIGHT)
-        ):
+        # The renderer emits a fixed profile; ANY deviation is unsupported
+        # (fail closed on every field, not just codecs/dimensions).
+        mismatches: list[str] = []
+        expected = {
+            "width": WIDTH,
+            "height": HEIGHT,
+            "fps_rational": list(FPS_RATIONAL),
+            "time_base": list(TIME_BASE),
+            "container": CONTAINER,
+            "video_codec": VIDEO_CODEC,
+            "video_profile": None,
+            "video_level": None,
+            "pixel_format": PIXEL_FORMAT,
+            "audio_codec": AUDIO_CODEC,
+            "audio_sample_rate": AUDIO_SAMPLE_RATE,
+            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
+        }
+        for field, fixed in expected.items():
+            requested = profile.get(field)
+            if requested is not None and requested != fixed:
+                mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
+        if mismatches:
             _write_json(
                 result_path,
                 {
                     "schema_version": 1,
                     "supported": False,
                     "reasons": [
-                        f"requested profile {profile.get('audio_codec')}/"
-                        f"{profile.get('video_codec')} is not produced by {BACKEND_ID}"
+                        "profile not produced by " + BACKEND_ID + ": "
+                        + "; ".join(mismatches)
                     ],
                     "features": {"media": False, "audio_mode": "none"},
                     "alternatives": [],
                     "backend": BACKEND_ID,
                     "backend_version": "1.0.0",
                 },
             )
             return 0
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

exec
/bin/zsh -lc "git diff --numstat 8c195bf0..9db48731 -- ':(exclude).oracle/**' && git show --stat --oneline --decorate --no-renames 9db48731" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2	10	astrid/core/media.py
29	1	astrid/core/rendering/artifacts.py
42	5	astrid/core/rendering/publication.py
19	5	astrid/core/rendering/transport.py
16	13	astrid/packs/rendering/executors/render/run.py
6	16	tests/core/util/test_media.py
36	16	tests/fixtures/renderer_packs/raw_command/backend.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
9db48731 (HEAD -> oracle-run) batch2-rework4: oracle re-review3 issues 1-5 (bounded drain communicate + OSError safety, canonical chan atom + honest channels-only probe + channels-vs-layout validation, full profile fail-closed support, unresolved out_path on all publish routes, ancestor-symlink guards w/ macOS system-redirect exemption)
 .oracle/checkins/batch-2-r3.md                     | 17554 +++++++++++++++++++
 astrid/core/media.py                               |    12 +-
 astrid/core/rendering/artifacts.py                 |    30 +-
 astrid/core/rendering/publication.py               |    47 +-
 astrid/core/rendering/transport.py                 |    24 +-
 astrid/packs/rendering/executors/render/run.py     |    29 +-
 tests/core/util/test_media.py                      |    22 +-
 .../fixtures/renderer_packs/raw_command/backend.py |    52 +-
 8 files changed, 17704 insertions(+), 66 deletions(-)

exec
/bin/zsh -lc 'git diff --unified=30 8c195bf0..9db48731 -- astrid/core/rendering/transport.py astrid/core/rendering/publication.py astrid/packs/rendering/executors/render/run.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index dd820fb2..8a094907 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -61,114 +61,147 @@ class _FcntlLock:
         if self._handle is None:
             return
         fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
         self._handle.close()
         self._handle = None
 
     def __enter__(self) -> _FcntlLock:
         return self.acquire()
 
     def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
         self.release()
 
 
 def _lock_for(path: Path) -> Any:
     """Return the per-output lock at ``<output>.lock``."""
 
     lock_path = Path(f"{path}.lock")
     if FileLock is not None:
         return FileLock(str(lock_path))
     return _FcntlLock(lock_path)
 
 
 def _default_sidecar_path(video_path: Path) -> Path:
     return Path(f"{video_path}.provenance.json")
 
 
 def _resolved(path: str | Path) -> Path:
     return Path(path).expanduser().resolve(strict=False)
 
 
+def _contains_symlink_component(path: str | Path) -> bool:
+    """True if a non-system path component is a symbolic link.
+
+    macOS resolves ``/tmp`` -> ``/private/tmp`` and ``/var`` ->
+    ``/private/var``; those system redirects are not containment escapes.
+    Any other symlink component (e.g. a symlinked run directory) is treated
+    as an escape and rejected.
+    """
+    current = Path(path).expanduser()
+    parts = list(current.parts)
+    for index in range(len(parts), 0, -1):
+        candidate = Path(*parts[:index])
+        try:
+            if not candidate.is_symlink():
+                continue
+        except OSError:
+            return True
+        try:
+            resolved = candidate.resolve(strict=False)
+        except (OSError, RuntimeError):
+            return True
+        # System redirects: /tmp, /var, /etc, /private/* -> /private/*
+        if str(resolved).startswith("/private/"):
+            continue
+        if candidate.name in ("tmp", "var", "etc", "home", "usr") and str(resolved).startswith("/"):
+            continue
+        return True
+    return False
+
+
 def _invalid_video(video_path: Path, *, reason: str, message: str) -> None:
     raise_invalid_artifact_error(
         backend=_BACKEND,
         message=message,
         recovery_command=_RECOVERY,
         details={"reason": reason, "path": str(video_path)},
     )
 
 
 def _validate_source_video(video_path: Path) -> None:
     try:
         exists = video_path.is_file()
     except OSError:
         exists = False
     if not exists:
         _invalid_video(
             video_path,
             reason="missing_artifact",
             message=f"rendered video does not exist: {video_path}",
         )
     try:
         size = video_path.stat().st_size
     except OSError:
         _invalid_video(
             video_path,
             reason="missing_artifact",
             message=f"rendered video cannot be read: {video_path}",
         )
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
-        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
+        if (
+            _contains_symlink_component(video_unresolved)
+            or _contains_symlink_component(sidecar_unresolved)
+        ):
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
 
 
@@ -195,137 +228,141 @@ def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
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
         # Never delete through a symlink: neither the raw video nor the raw
         # sidecar path may be a link (the resolved pair may point elsewhere).
         raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
         raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
         try:
             raw_path = Path(raw_candidate).expanduser()
-            if raw_path.is_symlink():
+            if _contains_symlink_component(raw_path):
                 continue
         except (OSError, TypeError):
             continue
         try:
             # For bare paths the default sidecar is derived from the raw
             # video path; it must be checked unresolved like an explicit one.
             raw_sidecar = (
                 Path(raw_sidecar_candidate).expanduser()
                 if raw_sidecar_candidate is not None
                 else _default_sidecar_path(raw_path)
             )
-            if raw_sidecar.is_symlink():
+            if _contains_symlink_component(raw_sidecar):
                 continue
         except (OSError, TypeError):
             continue
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
-    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
+    if (
+        _contains_symlink_component(source_unresolved)
+        or _contains_symlink_component(output_unresolved)
+        or _contains_symlink_component(sidecar_unresolved)
+    ):
         raise_invalid_artifact_error(
             backend=_BACKEND,
-            message="publication paths must not be symbolic links",
+            message="publication paths must not be symbolic links (or contain symlinked directories)",
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
 
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index 44671dd2..74f0919a 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -469,76 +469,90 @@ def _terminate_process_group(
     try:
         captured = process.communicate(timeout=grace)
     except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
         captured = None
         # Interruption or a communicate failure during the grace window must
         # not abandon the group: escalate to SIGKILL right away and reap in
         # the loop below.
         try:
             _signal_process_group(process, signal.SIGKILL)
         except OSError:
             pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
         try:
             time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
         except KeyboardInterrupt:
             try:
                 _signal_process_group(process, signal.SIGKILL)
             except OSError:
                 pass
             break
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
         drain_deadline = time.monotonic() + max(grace, 2.0)
         while True:
             try:
-                captured = process.communicate()
+                captured = process.communicate(timeout=max(grace, 2.0))
                 break
+            except subprocess.TimeoutExpired:
+                try:
+                    _signal_process_group(process, signal.SIGKILL)
+                except (OSError, PermissionError):
+                    pass
+                if time.monotonic() > drain_deadline:
+                    break
+                continue
             except KeyboardInterrupt:
                 try:
                     _signal_process_group(process, signal.SIGKILL)
                 except (OSError, PermissionError):
                     pass
                 if time.monotonic() > drain_deadline:
-                    process.kill()
-                    captured = process.communicate()
                     break
                 continue
     elif captured is None:
         # ``poll`` may have reaped the child while checking the fallback path.
-        # Its pipes still need to be drained, and communicate is safe here.
-        captured = process.communicate()
+        # Its pipes still need to be drained; bound the drain so cleanup can
+        # never block forever on a stuck pipe.
+        try:
+            captured = process.communicate(timeout=max(grace, 2.0))
+        except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
+            try:
+                _signal_process_group(process, signal.SIGKILL)
+            except (OSError, PermissionError):
+                pass
+            captured = ("", "")
 
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
         try:
             time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
         except KeyboardInterrupt:
             try:
                 _signal_process_group(process, signal.SIGKILL)
             except OSError:
                 pass
             break
     if _process_group_exists(process):
         _signal_process_group(process, signal.SIGKILL)
         _wait_for_group_exit(process, timeout=grace)
 
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index 35c58bfe..8323c223 100644
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -416,67 +416,68 @@ def _render_ffmpeg_media_to_path(timeline_path: Path, assets_path: Path, out_pat
             ";".join(filters),
             "-map",
             f"{copy_video_input}:v:0" if copy_video_input is not None else "[vout]",
             "-map",
             "[aout]",
             "-c:v",
             "copy" if copy_video_input is not None else "libx264",
             *(["-preset", "veryfast", "-crf", "20"] if copy_video_input is None else []),
             "-c:a",
             "aac",
             "-b:a",
             "192k",
             "-movflags",
             "+faststart",
             str(out_path),
         ],
         check=True,
     )
     return out_path
 
 
 def _render_ffmpeg_media(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     _previous_outputs: Sequence[Path] | None = None,
 ) -> Path:
     """Render FFmpeg output privately, then publish the committed pair."""
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
     with TemporaryDirectory(
-        prefix=f".{out_path.name}.publication-",
-        dir=str(out_path.parent),
+        prefix=f".{resolved_out.name}.publication-",
+        dir=str(resolved_out.parent),
     ) as publication_tmp:
-        staged_video = Path(publication_tmp) / out_path.name
+        staged_video = Path(publication_tmp) / resolved_out.name
         _render_ffmpeg_media_to_path(timeline_path, assets_path, staged_video)
         provenance = _render_provenance_payload(
             out_path,
             engine="ffmpeg",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=REPO_ROOT / "remotion",
             composition_id="TimelineComposition",
             theme_path=None,
             active_theme=None,
             registry_state=_effective_registry_state(None),
             stage_summary={"root": None, "effects": []},
         )
         output = publish_render_result(
             staged_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=(
                 _PUBLICATION_PREVIOUS_OUTPUTS.get()
                 if _previous_outputs is None
                 else _previous_outputs
             ),
         )
 
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_ffmpeg")
         assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_ffmpeg")
         render_id = audit.register_asset(
@@ -631,63 +632,64 @@ def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
             "-map",
             "[aout]",
             "-c:v",
             "libx264",
             "-preset",
             "veryfast",
             "-crf",
             "20",
             "-c:a",
             "aac",
             "-b:a",
             "192k",
             "-movflags",
             "+faststart",
             str(out_path),
         ],
         check=True,
     )
 
 
 def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
     if not timeline_path.exists():
         raise FileNotFoundError(f"Timeline missing: {timeline_path}")
     if not assets_path.exists():
         raise FileNotFoundError(f"Asset registry missing: {assets_path}")
     timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
     segments = _hybrid_segments(timeline_data)
     if len(segments) == 1 and segments[0]["engine"] == "ffmpeg":
         return _render_ffmpeg_media(timeline_path, assets_path, out_path)
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
-    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(out_path.parent)) as tmp:
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
+    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
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
@@ -1155,86 +1157,87 @@ def _render_audio_reactive_colour_if_supported(
     assets_path: Path,
     out_path: Path,
     *,
     project_dir: Path | None,
     composition_id: str,
     theme_path: Path | None,
 ) -> Path | None:
     timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
     clips = timeline_data.get("clips")
     if (
         not isinstance(clips, list)
         or len(clips) != 2
         or sum(
             isinstance(clip, dict)
             and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
             for clip in clips
         )
         != 1
     ):
         return None
     element = _audio_reactive_ffmpeg_element(theme_path)
     if element is None:
         return None
     registry = timeline.load_registry(assets_path)
     spec = audio_reactive_colour.match_and_validate(
         timeline_data, registry, assets_path
     )
     if spec is None:
         return None
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
     stage_summary = {
         "root": None,
         "effects": [
             {
                 "effect_id": element.id,
                 "source_pack_id": _source_pack_id(element),
                 "source": element.source,
                 "element_root": str(element.root),
                 "clip_ids": [
                     str(clip.get("id"))
                     for clip in timeline_data.get("clips", [])
                     if isinstance(clip, dict)
                     and clip.get("clipType") == element.id
                 ],
                 "staged_asset_ids": [],
                 "staged_assets": {},
             }
         ],
     }
     with TemporaryDirectory(
-        prefix=f".{out_path.name}.publication-",
-        dir=str(out_path.parent),
+        prefix=f".{resolved_out.name}.publication-",
+        dir=str(resolved_out.parent),
     ) as publication_tmp:
-        staged_video = Path(publication_tmp) / out_path.name
+        staged_video = Path(publication_tmp) / resolved_out.name
         rendered_video = audio_reactive_colour.render(spec, staged_video)
         provenance = _render_provenance_payload(
             out_path,
             engine="ffmpeg",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=project_dir or (REPO_ROOT / "remotion"),
             composition_id=composition_id,
             theme_path=theme_path,
             active_theme=None,
             registry_state=_effective_registry_state(theme_path),
             stage_summary=stage_summary,
         )
         provenance["ffmpeg_specialization"] = audio_reactive_colour.ADAPTER_ID
         provenance["audio_reactive_colour"] = {
             "event_count": len(spec.events),
             "fps": spec.fps,
             "frame_count": spec.total_frames,
             "marker_sha256": spec.marker_sha256,
         }
         output = publish_render_result(
             rendered_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
         )
 
     audit = AuditContext.from_env()
     if audit is not None:

exec
/bin/zsh -lc "git diff --unified=80 8c195bf0..9db48731 -- astrid/packs/rendering/executors/render/run.py | sed -n '1,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index 35c58bfe..8323c223 100644
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -366,167 +366,168 @@ def _render_ffmpeg_media_to_path(timeline_path: Path, assets_path: Path, out_pat
             start = float(clip.get("from", 0) or 0)
             end = float(clip.get("to", start) or start)
             label = f"v{index}"
             filters.append(
                 f"[{inp}:v]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS,"
                 f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                 f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
                 f"fps={fps},format=yuv420p[{label}]"
             )
             video_labels.append(f"[{label}]")
         filters.append("".join(video_labels) + f"concat=n={len(video_labels)}:v=1:a=0[vout]")
 
     audio_labels: list[str] = []
     cursor = 0.0
     audio_index = 0
     for clip in audio_clips:
         at = float(clip.get("at", 0) or 0)
         if at > cursor + 0.001:
             duration = at - cursor
             label = f"a{audio_index}"
             filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[{label}]")
             audio_labels.append(f"[{label}]")
             audio_index += 1
         inp = asset_index[str(clip["asset"])]
         start = float(clip.get("from", 0) or 0)
         end = float(clip.get("to", start) or start)
         volume = float(clip.get("volume", 1) or 0)
         label = f"a{audio_index}"
         filters.append(
             f"[{inp}:a]atrim=start={start:.6f}:end={end:.6f},"
             f"asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,"
             f"volume={volume:.6f}[{label}]"
         )
         audio_labels.append(f"[{label}]")
         cursor = at + _clip_duration_seconds(clip)
         audio_index += 1
     if not audio_labels:
         duration = sum(_clip_duration_seconds(clip) for clip in video_clips)
         filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[a0]")
         audio_labels.append("[a0]")
     filters.append("".join(audio_labels) + f"concat=n={len(audio_labels)}:v=0:a=1[aout]")
 
     out_path.parent.mkdir(parents=True, exist_ok=True)
     subprocess.run(
         [
             "ffmpeg",
             "-hide_banner",
             "-y",
             *inputs,
             "-filter_complex",
             ";".join(filters),
             "-map",
             f"{copy_video_input}:v:0" if copy_video_input is not None else "[vout]",
             "-map",
             "[aout]",
             "-c:v",
             "copy" if copy_video_input is not None else "libx264",
             *(["-preset", "veryfast", "-crf", "20"] if copy_video_input is None else []),
             "-c:a",
             "aac",
             "-b:a",
             "192k",
             "-movflags",
             "+faststart",
             str(out_path),
         ],
         check=True,
     )
     return out_path
 
 
 def _render_ffmpeg_media(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     _previous_outputs: Sequence[Path] | None = None,
 ) -> Path:
     """Render FFmpeg output privately, then publish the committed pair."""
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
     with TemporaryDirectory(
-        prefix=f".{out_path.name}.publication-",
-        dir=str(out_path.parent),
+        prefix=f".{resolved_out.name}.publication-",
+        dir=str(resolved_out.parent),
     ) as publication_tmp:
-        staged_video = Path(publication_tmp) / out_path.name
+        staged_video = Path(publication_tmp) / resolved_out.name
         _render_ffmpeg_media_to_path(timeline_path, assets_path, staged_video)
         provenance = _render_provenance_payload(
             out_path,
             engine="ffmpeg",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=REPO_ROOT / "remotion",
             composition_id="TimelineComposition",
             theme_path=None,
             active_theme=None,
             registry_state=_effective_registry_state(None),
             stage_summary={"root": None, "effects": []},
         )
         output = publish_render_result(
             staged_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=(
                 _PUBLICATION_PREVIOUS_OUTPUTS.get()
                 if _previous_outputs is None
                 else _previous_outputs
             ),
         )
 
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_ffmpeg")
         assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_ffmpeg")
         render_id = audit.register_asset(
             kind="render",
             path=output,
             label="Rendered video",
             parents=[timeline_id, assets_id],
             stage="render_ffmpeg",
             metadata={"engine": "ffmpeg"},
         )
         audit.register_node(
             stage="render_ffmpeg",
             label="Render media-only timeline with ffmpeg",
             parents=[timeline_id, assets_id],
             outputs=[render_id],
             metadata={"engine": "ffmpeg"},
         )
     return output
 
 
 def _can_render_with_ffmpeg_media(timeline_path: Path, assets_path: Path) -> bool:
     try:
         timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
         timeline.load_registry(assets_path)
         _validate_ffmpeg_media_timeline(timeline_data)
         tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
         has_visual_media_clip = any(
             clip.get("clipType") == "media"
             and tracks.get(clip.get("track"), {}).get("kind") == "visual"
             for clip in timeline_data.get("clips", [])
         )
     except Exception:
         return False
     return has_visual_media_clip
 
 
 def _complex_clip_windows(timeline_data: dict, fps: int, *, handle_seconds: float = 0.25) -> list[tuple[float, float]]:
     duration = _timeline_duration_seconds(timeline_data)
     tracks = {track.get("id"): track for track in timeline_data.get("tracks", [])}
     visual_track_ids = {track.get("id") for track in timeline_data.get("tracks", []) if track.get("kind") == "visual"}
     visual_media_coverage: dict[str, float] = {}
     for candidate in timeline_data.get("clips", []):
         if candidate.get("clipType") != "media" or candidate.get("track") not in visual_track_ids:
             continue
         track_id = str(candidate.get("track"))
         visual_media_coverage[track_id] = visual_media_coverage.get(track_id, 0.0) + _clip_duration_seconds(candidate)
     base_visual_track_id = max(visual_media_coverage, key=visual_media_coverage.get) if visual_media_coverage else None
     windows: list[tuple[float, float]] = []
     clips = timeline_data.get("clips", [])
     for index, clip in enumerate(clips):
         media_clip = clip.get("clipType") == "media"
         if media_clip:
             track = tracks.get(clip.get("track"), {})
@@ -581,163 +582,164 @@ def _complex_clip_windows(timeline_data: dict, fps: int, *, handle_seconds: floa
     merged: list[tuple[float, float]] = []
     for start, end in windows:
         if not merged or start > merged[-1][1]:
             merged.append((start, end))
         else:
             merged[-1] = (merged[-1][0], max(merged[-1][1], end))
     return merged
 
 
 def _hybrid_segments(timeline_data: dict) -> list[dict[str, float | str]]:
     _width, _height, fps = _timeline_canvas(timeline_data)
     duration = _round_frame_time(_timeline_duration_seconds(timeline_data), fps, mode="ceil")
     complex_windows = _complex_clip_windows(timeline_data, fps)
     if not complex_windows:
         return [{"engine": "ffmpeg", "from": 0.0, "to": duration}]
     segments: list[dict[str, float | str]] = []
     cursor = 0.0
     for start, end in complex_windows:
         start = max(0.0, min(start, duration))
         end = max(start, min(end, duration))
         if start > cursor:
             segments.append({"engine": "ffmpeg", "from": cursor, "to": start})
         if end > start:
             segments.append({"engine": "remotion", "from": start, "to": end})
         cursor = max(cursor, end)
     if cursor < duration:
         segments.append({"engine": "ffmpeg", "from": cursor, "to": duration})
     return [segment for segment in segments if float(segment["to"]) > float(segment["from"])]
 
 
 def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
     inputs: list[str] = []
     filters: list[str] = []
     concat_inputs: list[str] = []
     for index, path in enumerate(segment_paths):
         inputs.extend(["-i", str(path)])
         filters.append(f"[{index}:v]setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{index}]")
         filters.append(f"[{index}:a]asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo[a{index}]")
         concat_inputs.append(f"[v{index}][a{index}]")
     filters.append("".join(concat_inputs) + f"concat=n={len(segment_paths)}:v=1:a=1[vout][aout]")
     subprocess.run(
         [
             "ffmpeg",
             "-hide_banner",
             "-y",
             *inputs,
             "-filter_complex",
             ";".join(filters),
             "-map",
             "[vout]",
             "-map",
             "[aout]",
             "-c:v",
             "libx264",
             "-preset",
             "veryfast",
             "-crf",
             "20",
             "-c:a",
             "aac",
             "-b:a",
             "192k",
             "-movflags",
             "+faststart",
             str(out_path),
         ],
         check=True,
     )
 
 
 def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
     if not timeline_path.exists():
         raise FileNotFoundError(f"Timeline missing: {timeline_path}")
     if not assets_path.exists():
         raise FileNotFoundError(f"Asset registry missing: {assets_path}")
     timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
     segments = _hybrid_segments(timeline_data)
     if len(segments) == 1 and segments[0]["engine"] == "ffmpeg":
         return _render_ffmpeg_media(timeline_path, assets_path, out_path)
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
-    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(out_path.parent)) as tmp:
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
+    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
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
         _concat_segments(segment_paths, staged_video)
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
 
 
 def _timeline_composition_src(project_dir: Path) -> Path | None:
@@ -1105,186 +1107,187 @@ def _write_render_provenance(
 
 def _stderr_tail(stderr: str) -> str:
     lines = stderr.splitlines()
     tail = lines[-40:] if len(lines) > 40 else lines
     return "\n".join(tail).strip()
 
 
 def _require_free_space(path: Path, min_free_gb: float | None) -> None:
     if min_free_gb is None or min_free_gb <= 0:
         return
     target = path if path.exists() else path.parent
     usage = shutil.disk_usage(target)
     min_free = int(min_free_gb * 1024 * 1024 * 1024)
     if usage.free < min_free:
         free_gb = usage.free / (1024 * 1024 * 1024)
         raise RuntimeError(
             f"Remotion render needs at least {min_free_gb:.1f} GiB free at {target}; "
             f"only {free_gb:.1f} GiB is available"
         )
 
 
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
 
 
 def _audio_reactive_ffmpeg_element(
     theme_path: Path | None,
 ) -> ElementDefinition | None:
     effects, _aliases = _effect_registry_for_assets(theme_path)
     element = effects.get(audio_reactive_colour.EFFECT_ID)
     if (
         element is None
         or element.metadata.get("ffmpegAdapter")
         != audio_reactive_colour.ADAPTER_ID
     ):
         return None
     return element
 
 
 def _render_audio_reactive_colour_if_supported(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     project_dir: Path | None,
     composition_id: str,
     theme_path: Path | None,
 ) -> Path | None:
     timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
     clips = timeline_data.get("clips")
     if (
         not isinstance(clips, list)
         or len(clips) != 2
         or sum(
             isinstance(clip, dict)
             and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
             for clip in clips
         )
         != 1
     ):
         return None
     element = _audio_reactive_ffmpeg_element(theme_path)
     if element is None:
         return None
     registry = timeline.load_registry(assets_path)
     spec = audio_reactive_colour.match_and_validate(
         timeline_data, registry, assets_path
     )
     if spec is None:
         return None
 
-    out_path = out_path.resolve()
-    out_path.parent.mkdir(parents=True, exist_ok=True)
+    publication_out = out_path  # unresolved: publication symlink-guards it
+    resolved_out = out_path.resolve()
+    resolved_out.parent.mkdir(parents=True, exist_ok=True)
     stage_summary = {
         "root": None,
         "effects": [
             {
                 "effect_id": element.id,
                 "source_pack_id": _source_pack_id(element),
                 "source": element.source,
                 "element_root": str(element.root),
                 "clip_ids": [
                     str(clip.get("id"))
                     for clip in timeline_data.get("clips", [])
                     if isinstance(clip, dict)
                     and clip.get("clipType") == element.id
                 ],
                 "staged_asset_ids": [],
                 "staged_assets": {},
             }
         ],
     }
     with TemporaryDirectory(
-        prefix=f".{out_path.name}.publication-",
-        dir=str(out_path.parent),
+        prefix=f".{resolved_out.name}.publication-",
+        dir=str(resolved_out.parent),
     ) as publication_tmp:
-        staged_video = Path(publication_tmp) / out_path.name
+        staged_video = Path(publication_tmp) / resolved_out.name
         rendered_video = audio_reactive_colour.render(spec, staged_video)
         provenance = _render_provenance_payload(
             out_path,
             engine="ffmpeg",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=project_dir or (REPO_ROOT / "remotion"),
             composition_id=composition_id,
             theme_path=theme_path,
             active_theme=None,
             registry_state=_effective_registry_state(theme_path),
             stage_summary=stage_summary,
         )
         provenance["ffmpeg_specialization"] = audio_reactive_colour.ADAPTER_ID
         provenance["audio_reactive_colour"] = {
             "event_count": len(spec.events),
             "fps": spec.fps,
             "frame_count": spec.total_frames,
             "marker_sha256": spec.marker_sha256,
         }
         output = publish_render_result(
             rendered_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
         )
 
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(
             kind="timeline",
             path=timeline_path,
             label="Audio-reactive render timeline",
             stage="render_ffmpeg_audio_reactive_colour",
         )
         assets_id = audit.register_asset(
             kind="assets_registry",
             path=assets_path,
             label="Audio-reactive asset registry",
             stage="render_ffmpeg_audio_reactive_colour",
         )
         render_id = audit.register_asset(
             kind="render",
             path=output,
             label="Rendered audio-reactive colour video",
             parents=[timeline_id, assets_id],
             stage="render_ffmpeg_audio_reactive_colour",
             metadata={
                 "engine": "ffmpeg",
                 "specialization": audio_reactive_colour.ADAPTER_ID,
                 "event_count": len(spec.events),
                 "marker_sha256": spec.marker_sha256,
             },
         )
         audit.register_node(
             stage="render_ffmpeg_audio_reactive_colour",
             label="Render audio-reactive colour timeline with FFmpeg",
             parents=[timeline_id, assets_id],
             outputs=[render_id],
             metadata={

exec
/bin/zsh -lc 'rg -n "Transport cleanup|chan atom|support not|Output symlinks|Ancestor symlinks|communicate|symlinked run" .oracle/checkins/batch-2-r3.md | tail -80' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
27:1. **Transport cleanup still interruptible/leak-prone; _wait_for_group_exit loops forever** →
28:   - Grace-window `communicate()` now catches OSError too (any post-spawn
34:2. **chan atom malformed; layout inference masks** →
35:   - chan atom restructured inside the `wave` box (QTFF placement).
954:8c195bf0 (HEAD -> oracle-run) batch2-rework3: oracle re-review2 issues 1-6 (transport OSError/KeyboardInterrupt-safe cleanup w/ bounded escalation, chan atom inside wave + mono/stereo-only layout inference + strict-validation integration test, support profile fail-closed + support.json codec fix, run.py unresolved out_path in publication context, default-sidecar symlink guard, remove committed pyc + gitignore)
9836:- Transport cleanup remains interruptible and leak-prone. Non-timeout `communicate()` failures escape after only SIGTERM, while repeated `KeyboardInterrupt` can escape unguarded polling/drain operations before reap. `_wait_for_group_exit` can also loop forever. The new test no longer checks the grandchild. [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461), [test_transport.py:178](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:178)
9849:- Transport cleanup remains interruptible and leak-prone. Non-timeout `communicate()` failures escape after only SIGTERM, while repeated `KeyboardInterrupt` can escape unguarded polling/drain operations before reap. `_wait_for_group_exit` can also loop forever. The new test no longer checks the grandchild. [transport.py:461](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:461), [test_transport.py:178](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:178)
9969:         captured = process.communicate(timeout=grace)
9975:+        # Interruption or a communicate failure during the grace window must
10002:                 captured = process.communicate()
10011:                     captured = process.communicate()
10016:         # Its pipes still need to be drained, and communicate is safe here.
10017:         captured = process.communicate()
12012:   470	        captured = process.communicate(timeout=grace)
12015:   473	        # Interruption or a communicate failure during the grace window must
12041:   499	                captured = process.communicate()
12050:   508	                    captured = process.communicate()
12055:   513	        # Its pipes still need to be drained, and communicate is safe here.
12056:   514	        captured = process.communicate()
12165:/bin/zsh -lc "rg -n \"_terminate_process_group|_terminate_leftover_group|_wait_for_group_exit|communicate\\(\" astrid/core/rendering/transport.py tests/core/rendering/test_transport.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
12167:astrid/core/rendering/transport.py:204:            stdout, stderr = process.communicate(timeout=normalized_timeout)
12173:astrid/core/rendering/transport.py:470:        captured = process.communicate(timeout=grace)
12174:astrid/core/rendering/transport.py:499:                captured = process.communicate()
12175:astrid/core/rendering/transport.py:508:                    captured = process.communicate()
12176:astrid/core/rendering/transport.py:514:        captured = process.communicate()
13542:   204	            stdout, stderr = process.communicate(timeout=normalized_timeout)
16821:web search: site:ffmpeg.org/doxygen/8.0 mov_read_chan avio_rb32 chan atom
17535:- Transport cleanup is still unbounded and interruptible. Unguarded `communicate()` calls can block indefinitely or propagate persistent `OSError`/repeated `KeyboardInterrupt` before guaranteed reap. `_wait_for_group_exit` itself is bounded, but overall cleanup is not. [transport.py:495](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:495)
17541:- Output symlinks remain followed on FFmpeg, hybrid, and audio-reactive production routes because those helpers resolve `out_path` again before publication. This includes automatic media-only FFmpeg fallback. [run.py:446](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:446), [run.py:661](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:661), [run.py:1185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1185)
17543:- Previous-output guards inspect only the leaf path. A candidate beneath a symlinked run directory is resolved and can delete the target video/sidecar outside that directory. [publication.py:221](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:221), [run.py:984](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:984)
17546:- Transport cleanup is still unbounded and interruptible. Unguarded `communicate()` calls can block indefinitely or propagate persistent `OSError`/repeated `KeyboardInterrupt` before guaranteed reap. `_wait_for_group_exit` itself is bounded, but overall cleanup is not. [transport.py:495](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:495)
17552:- Output symlinks remain followed on FFmpeg, hybrid, and audio-reactive production routes because those helpers resolve `out_path` again before publication. This includes automatic media-only FFmpeg fallback. [run.py:446](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:446), [run.py:661](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:661), [run.py:1185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1185)
17554:- Previous-output guards inspect only the leaf path. A candidate beneath a symlinked run directory is resolved and can delete the target video/sidecar outside that directory. [publication.py:221](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:221), [run.py:984](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:984)

exec
/bin/zsh -lc "sed -n '1,80p' .oracle/checkins/batch-2-r3.md && tail -40 .oracle/checkins/batch-2-r3.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
Reading additional input from stdin...
2026-08-12T06:44:09.268491Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:09.268521Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:09.268526Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff4b6-cefa-7361-b4f2-2bcdf5d1bf06
--------
user
# Megado Checkpoint — Batch 2 third re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-2.md (6), batch-2-r1.md (5), batch-2-r2.md (6). Third
rework committed as `8c195bf0` (prior head 7f7c25d5). Incremental diff at
/tmp/batch2-r3.diff.

## How each of your 6 re-review2 issues was addressed (host-implemented)

1. **Transport cleanup still interruptible/leak-prone; _wait_for_group_exit loops forever** →
   - Grace-window `communicate()` now catches OSError too (any post-spawn
     failure escalates to SIGKILL immediately).
   - All three grace-wait sleep loops are KeyboardInterrupt-safe (SIGKILL +
     break).
   - `_wait_for_group_exit` SIGKILL escalation is now BOUNDED (max(timeout,
     1.0)s) and interrupt-safe — no infinite loop.
2. **chan atom malformed; layout inference masks** →
   - chan atom restructured inside the `wave` box (QTFF placement).
   - Layout inference restricted to unambiguous mono/stereo; 5.1/7.1 stay
     unprobed (no guessing). Test added covering both.
   - Fixture render test now runs STRICT `validate_render_result` against the
     request profile end-to-end — the generated media passes (h264 1920x1080
     24fps, pcm_s16le 48kHz stereo).
3. **support requests sowt while renderer produces pcm_s16le; _support ignores mismatch** →
   - support.json audio_codec → pcm_s16le.
   - `_support` now validates the request profile fail-closed: a request for
     a codec/dimension the renderer cannot produce returns `supported:
     false` with a reason.
4. **Production output symlinks still followed (run.py:1290)** →
   - `_render_with_publication_context` no longer resolves `out_path`; the
     unresolved path reaches the publication symlink guard.
5. **Default previous-output sidecar symlinks unchecked** →
   - For bare paths, the default sidecar is derived from the raw video path
     and checked unresolved.
6. **Committed __pycache__/.pyc with absolute path** →
   - Removed from git, added `tests/fixtures/**/__pycache__/` to .gitignore.

## Evidence

- Incremental diff: /tmp/batch2-r3.diff (11 files)
- Host-verified: media (21) + transport (14) + raw fixture (6) + publication +
  artifacts + assets (76 combined) pass; full consolidated acceptance = 746
  passed, 2 failed (SAME 2 pre-existing env-dependent failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Verify the six closures, especially the
bounded SIGKILL escalation, the strict-validation integration (the fixture
output must genuinely pass validate_render_result), and the unresolved-path
symlink guards. If PASS, say exactly `PASS`.
codex
I’m using the `megado` skill because this is a formal Megado checkpoint. I’ll inspect the checkpoint rules first, then verify the incremental diff and run targeted read-only checks around all six claimed closures.
exec
/bin/zsh -lc "sed -n '1,260p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, max reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where a GPT-5.6 Sol oracle reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

A delivery pipeline for a whole project: **Codex plans, DeepSeek explores, Codex revises, DeepSeek executes, Codex oracles** — all in a worktree, opened and synced when done. Two models only: **DeepSeek V4 Flash** and **GPT-5.6 Sol**.
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
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,runpy; from unittest.mock import patch; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); base=json.load(open(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\")); fields={\"fps_rational\":[30,1],\"time_base\":[1,30000],\"container\":\"mov\",\"pixel_format\":\"yuv444p\",\"audio_sample_rate\":44100,\"audio_channel_layout\":\"mono\"}; out=[]; [(lambda req:(out.clear(),m[\"_write_json\"] if False else None,patch.object(m[\"Path\"],\"write_text\")))(base) for _ in []]; print(sorted(set(base[\"profile\"])-{\"audio_codec\",\"video_codec\",\"width\",\"height\"})); print(fields)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 103ms:
['audio_channel_layout', 'audio_sample_rate', 'container', 'duration_tolerance', 'fps_rational', 'pixel_format', 'time_base', 'video_level', 'video_profile']
{'fps_rational': [30, 1], 'time_base': [1, 30000], 'container': 'mov', 'pixel_format': 'yuv444p', 'audio_sample_rate': 44100, 'audio_channel_layout': 'mono'}

exec
/bin/zsh -lc "find /tmp -maxdepth 4 -type f \\( -name 'raw_command.mp4' -o -name 'result.json' \\) -print 2>/dev/null | head -100" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
codex
- Transport cleanup is still unbounded and interruptible. Unguarded `communicate()` calls can block indefinitely or propagate persistent `OSError`/repeated `KeyboardInterrupt` before guaranteed reap. `_wait_for_group_exit` itself is bounded, but overall cleanup is not. [transport.py:495](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:495)

- The `chan` atom remains malformed: its 20-byte box omits `mNumberChannelDescriptions` and uses tag `3`, not stereo tag `0x00650002`. Actual FFprobe output still has no `channel_layout`; strict validation passes only through the two-channel inference fallback. [backend.py:288](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:288), [media.py:224](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py:224), [FFmpeg canonical writer](https://www.ffmpeg.org/doxygen/8.0/movenc_8c_source.html#l01018)

- `_support()` is not profile-fail-closed. It checks only codecs and dimensions; unsupported FPS, time base, container, pixel format, video profile/level, sample rate, and channel layout still return `supported: true`, although rendering always emits fixed values. [backend.py:437](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:437)

- Output symlinks remain followed on FFmpeg, hybrid, and audio-reactive production routes because those helpers resolve `out_path` again before publication. This includes automatic media-only FFmpeg fallback. [run.py:446](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:446), [run.py:661](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:661), [run.py:1185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1185)

- Previous-output guards inspect only the leaf path. A candidate beneath a symlinked run directory is resolved and can delete the target video/sidecar outside that directory. [publication.py:221](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:221), [run.py:984](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:984)
tokens used
277,299
- Transport cleanup is still unbounded and interruptible. Unguarded `communicate()` calls can block indefinitely or propagate persistent `OSError`/repeated `KeyboardInterrupt` before guaranteed reap. `_wait_for_group_exit` itself is bounded, but overall cleanup is not. [transport.py:495](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:495)

- The `chan` atom remains malformed: its 20-byte box omits `mNumberChannelDescriptions` and uses tag `3`, not stereo tag `0x00650002`. Actual FFprobe output still has no `channel_layout`; strict validation passes only through the two-channel inference fallback. [backend.py:288](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:288), [media.py:224](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py:224), [FFmpeg canonical writer](https://www.ffmpeg.org/doxygen/8.0/movenc_8c_source.html#l01018)

- `_support()` is not profile-fail-closed. It checks only codecs and dimensions; unsupported FPS, time base, container, pixel format, video profile/level, sample rate, and channel layout still return `supported: true`, although rendering always emits fixed values. [backend.py:437](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:437)

- Output symlinks remain followed on FFmpeg, hybrid, and audio-reactive production routes because those helpers resolve `out_path` again before publication. This includes automatic media-only FFmpeg fallback. [run.py:446](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:446), [run.py:661](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:661), [run.py:1185](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:1185)

- Previous-output guards inspect only the leaf path. A candidate beneath a symlinked run directory is resolved and can delete the target video/sidecar outside that directory. [publication.py:221](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:221), [run.py:984](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:984)

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '150,560p' && rg -n \"communicate\\(\" astrid/core/rendering/transport.py tests/core/rendering/test_transport.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   321	        raise_protocol_error(
   322	            backend=backend,
   323	            message="renderer command must contain at least one argument",
   324	        )
   325	    return argv
   326	
   327	
   328	def _resolve_cwd(cwd: str | os.PathLike[str], *, backend: str) -> Path:
   329	    try:
   330	        path = Path(cwd).expanduser().resolve(strict=True)
   331	    except (OSError, RuntimeError) as exc:
   332	        raise_internal_error(
   333	            backend=backend,
   334	            message=f"renderer pack root is unavailable: {cwd}",
   335	            details={"cwd": os.fspath(cwd), "error_type": type(exc).__name__},
   336	        )
   337	    if not path.is_dir():
   338	        raise_internal_error(
   339	            backend=backend,
   340	            message=f"renderer pack root is not a directory: {path}",
   341	            details={"cwd": str(path)},
   342	        )
   343	    return path
   344	
   345	
   346	def _absolute_path(path: str | os.PathLike[str]) -> Path:
   347	    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))
   348	
   349	
   350	def _build_environment(env: Mapping[str, str] | None) -> dict[str, str]:
   351	    base = dict(os.environ)
   352	    if env is not None:
   353	        base.update({str(key): str(value) for key, value in env.items()})
   354	    return build_child_subprocess_env(base=base, parent=base)
   355	
   356	
   357	def _resolve_executable(
   358	    executable: str,
   359	    *,
   360	    cwd: Path,
   361	    child_env: Mapping[str, str],
   362	    backend: str,
   363	) -> str:
   364	    path_like = os.sep in executable or (
   365	        os.altsep is not None and os.altsep in executable
   366	    )
   367	    if path_like:
   368	        raw = Path(executable).expanduser()
   369	        if raw.is_absolute():
   370	            candidate = raw.resolve(strict=False)
   371	        else:
   372	            candidate = (cwd / raw).resolve(strict=False)
   373	            try:
   374	                candidate.relative_to(cwd)
   375	            except ValueError:
   376	                raise_binary_missing_error(
   377	                    backend=backend,
   378	                    message=f"pack-relative renderer executable escapes its pack root: {executable}",
   379	                    details={"binary": executable, "cwd": str(cwd)},
   380	                )
   381	        resolved = str(candidate) if _is_executable_file(candidate) else None
   382	    elif _is_executable_file(cwd / executable):
   383	        # Manifest commands commonly name a pack-owned entrypoint without a
   384	        # leading ``./``.  Resolve it explicitly because sanitized PATH must
   385	        # not implicitly contain the pack root.
   386	        resolved = str((cwd / executable).resolve())
   387	    else:
   388	        resolved = shutil.which(
   389	            executable,
   390	            path=child_env.get("PATH", os.defpath),
   391	        )
   392	
   393	    if resolved is None:
   394	        raise_binary_missing_error(
   395	            backend=backend,
   396	            message=f"required renderer executable was not found: {executable}",
   397	            recovery_command=f"install {executable} and retry",
   398	            details={"binary": executable, "cwd": str(cwd)},
   399	        )
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
   471	    except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
   472	        captured = None
   473	        # Interruption or a communicate failure during the grace window must
   474	        # not abandon the group: escalate to SIGKILL right away and reap in
   475	        # the loop below.
   476	        try:
   477	            _signal_process_group(process, signal.SIGKILL)
   478	        except OSError:
   479	            pass
   480	
   481	    while _process_group_exists(process) and time.monotonic() < deadline:
   482	        try:
   483	            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   484	        except KeyboardInterrupt:
   485	            try:
   486	                _signal_process_group(process, signal.SIGKILL)
   487	            except OSError:
   488	                pass
   489	            break
   490	
   491	    killed_group = _process_group_exists(process)
   492	    if killed_group:
   493	        _signal_process_group(process, signal.SIGKILL)
   494	
   495	    if process.returncode is None:
   496	        drain_deadline = time.monotonic() + max(grace, 2.0)
   497	        while True:
   498	            try:
   499	                captured = process.communicate(timeout=max(grace, 2.0))
   500	                break
   501	            except subprocess.TimeoutExpired:
   502	                try:
   503	                    _signal_process_group(process, signal.SIGKILL)
   504	                except (OSError, PermissionError):
   505	                    pass
   506	                if time.monotonic() > drain_deadline:
   507	                    break
   508	                continue
   509	            except KeyboardInterrupt:
   510	                try:
   511	                    _signal_process_group(process, signal.SIGKILL)
   512	                except (OSError, PermissionError):
   513	                    pass
   514	                if time.monotonic() > drain_deadline:
   515	                    break
   516	                continue
   517	    elif captured is None:
   518	        # ``poll`` may have reaped the child while checking the fallback path.
   519	        # Its pipes still need to be drained; bound the drain so cleanup can
   520	        # never block forever on a stuck pipe.
   521	        try:
   522	            captured = process.communicate(timeout=max(grace, 2.0))
   523	        except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
   524	            try:
   525	                _signal_process_group(process, signal.SIGKILL)
   526	            except (OSError, PermissionError):
   527	                pass
   528	            captured = ("", "")
   529	
   530	    if killed_group:
   531	        _wait_for_group_exit(process, timeout=grace)
   532	
   533	    stdout, stderr = captured or ("", "")
   534	    return stdout or "", stderr or ""
   535	
   536	
   537	def _terminate_leftover_group(
   538	    process: subprocess.Popen[str], *, grace: float
   539	) -> None:
   540	    """Clean up descendants that outlived an otherwise completed command."""
   541	
   542	    if not _process_group_exists(process):
   543	        return
   544	    _signal_process_group(process, signal.SIGTERM)
   545	    deadline = time.monotonic() + grace
   546	    while _process_group_exists(process) and time.monotonic() < deadline:
   547	        try:
   548	            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   549	        except KeyboardInterrupt:
   550	            try:
   551	                _signal_process_group(process, signal.SIGKILL)
   552	            except OSError:
   553	                pass
   554	            break
   555	    if _process_group_exists(process):
   556	        _signal_process_group(process, signal.SIGKILL)
   557	        _wait_for_group_exit(process, timeout=grace)
   558	
   559	
   560	def _wait_for_group_exit(
astrid/core/rendering/transport.py:204:            stdout, stderr = process.communicate(timeout=normalized_timeout)
astrid/core/rendering/transport.py:470:        captured = process.communicate(timeout=grace)
astrid/core/rendering/transport.py:499:                captured = process.communicate(timeout=max(grace, 2.0))
astrid/core/rendering/transport.py:522:            captured = process.communicate(timeout=max(grace, 2.0))

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '555,640p' && nl -ba tests/core/rendering/test_transport.py | sed -n '1,280p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   555	    if _process_group_exists(process):
   556	        _signal_process_group(process, signal.SIGKILL)
   557	        _wait_for_group_exit(process, timeout=grace)
   558	
   559	
   560	def _wait_for_group_exit(
   561	    process: subprocess.Popen[str], *, timeout: float
   562	) -> None:
   563	    deadline = time.monotonic() + timeout
   564	    while _process_group_exists(process) and time.monotonic() < deadline:
   565	        try:
   566	            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   567	        except KeyboardInterrupt:
   568	            try:
   569	                _signal_process_group(process, signal.SIGKILL)
   570	            except OSError:
   571	                pass
   572	            break
   573	    # Escalate to SIGKILL for the remaining grace window (bounded) so a
   574	    # SIGTERM-ignoring group cannot survive cleanup.
   575	    kill_deadline = time.monotonic() + max(timeout, 1.0)
   576	    while _process_group_exists(process) and time.monotonic() < kill_deadline:
   577	        try:
   578	            _signal_process_group(process, signal.SIGKILL)
   579	        except (OSError, PermissionError):
   580	            break
   581	        try:
   582	            time.sleep(0.01)
   583	        except KeyboardInterrupt:
   584	            break
   585	
   586	
   587	def _secret_environment_values(
   588	    host: Mapping[str, str], overlay: Mapping[str, str] | None
   589	) -> tuple[str, ...]:
   590	    values: set[str] = set()
   591	    for source in (host, overlay or {}):
   592	        for key, value in source.items():
   593	            text = str(value)
   594	            if _SECRET_NAME_RE.search(str(key)) and len(text) >= 4:
   595	                values.add(text)
   596	    return tuple(sorted(values, key=len, reverse=True))
   597	
   598	
   599	def _redact_log(value: str, *, secret_values: Sequence[str]) -> str:
   600	    redacted = value.replace("\x00", "\ufffd")
   601	    for secret in secret_values:
   602	        redacted = redacted.replace(secret, "[redacted]")
   603	    redacted = _AUTH_HEADER_RE.sub(
   604	        lambda match: f"{match.group(1)}: [redacted]", redacted
   605	    )
   606	    redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
   607	    redacted = _SECRET_QUERY_RE.sub(
   608	        lambda match: f"{match.group(1)}[redacted]", redacted
   609	    )
   610	    redacted = _SECRET_ASSIGNMENT_RE.sub(
   611	        lambda match: f"{match.group(1)}[redacted]", redacted
   612	    )
   613	    redacted = _SECRET_VALUE_RE.sub("[redacted]", redacted)
   614	    if len(redacted) > _MAX_LOG_CHARS:
   615	        redacted = redacted[:_MAX_LOG_CHARS] + "\n[truncated]"
   616	    return redacted
   617	
   618	
   619	def _redacted_logs(
   620	    stdout: str,
   621	    stderr: str,
   622	    *,
   623	    secret_values: Sequence[str],
   624	) -> dict[str, str]:
   625	    return {
   626	        "stdout": _redact_log(stdout or "", secret_values=secret_values),
   627	        "stderr": _redact_log(stderr or "", secret_values=secret_values),
   628	    }
   629	
   630	
   631	def _read_result_file(
   632	    result_path: Path,
   633	    *,
   634	    backend: str,
   635	    logs: Mapping[str, str],
   636	) -> Any:
   637	    try:
   638	        result_stat = result_path.lstat()
   639	    except FileNotFoundError:
   640	        raise_protocol_error(
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

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '1,680p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""Strict validation for renderer and finalizer artifacts."""
     2	
     3	from __future__ import annotations
     4	
     5	import math
     6	import re
     7	import stat
     8	from collections.abc import Mapping
     9	from fractions import Fraction
    10	from pathlib import Path
    11	from typing import Any, NoReturn
    12	
    13	from astrid.core.foundation.hash import sha256_file
    14	from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict
    15	
    16	from .contracts import (
    17	    Attachment,
    18	    AudioOwnership,
    19	    RenderProfile,
    20	    RenderResult,
    21	    VideoArtifact,
    22	)
    23	from .errors import raise_invalid_artifact_error, raise_protocol_error
    24	
    25	
    26	_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
    27	_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    28	_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
    29	_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
    30	_ECMA_WHITESPACE = (
    31	    " \t\n\r\f\v\u00a0\u1680"
    32	    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    33	    "\u2028\u2029\u202f\u205f\u3000\ufeff"
    34	)
    35	_BACKEND = "astrid.core"
    36	_RECOVERY = (
    37	    "rerun the renderer in a fresh invocation workspace and emit a contained, "
    38	    "non-empty artifact matching the canonical render profile"
    39	)
    40	
    41	
    42	def _invalid(reason: str, message: str, **details: Any) -> NoReturn:
    43	    raise_invalid_artifact_error(
    44	        backend=_BACKEND,
    45	        message=message,
    46	        recovery_command=_RECOVERY,
    47	        details={"reason": reason, **details},
    48	    )
    49	
    50	
    51	def _coerce_result(result: RenderResult | Mapping[str, Any]) -> RenderResult:
    52	    if isinstance(result, RenderResult):
    53	        return result
    54	    if isinstance(result, Mapping):
    55	        return RenderResult.from_dict(result)
    56	    raise_protocol_error(
    57	        backend=_BACKEND,
    58	        message="render result must be a RenderResult or result mapping",
    59	        details={"received_type": type(result).__name__},
    60	    )
    61	
    62	
    63	def _coerce_expected_profile(
    64	    profile: RenderProfile | Mapping[str, Any],
    65	) -> RenderProfile:
    66	    try:
    67	        if isinstance(profile, RenderProfile):
    68	            candidate = profile
    69	        elif isinstance(profile, Mapping):
    70	            candidate = RenderProfile.from_dict(profile)
    71	        else:
    72	            raise_protocol_error(
    73	                backend=_BACKEND,
    74	                message="expected_profile must be a RenderProfile or profile mapping",
    75	                details={"received_type": type(profile).__name__},
    76	            )
    77	        # Reconstruct solely to catch forged/mutated frozen instances.  The
    78	        # caller's object remains authoritative and is returned untouched.
    79	        RenderProfile.from_dict(candidate.to_dict())
    80	    except Exception as exc:
    81	        from .errors import RendererException
    82	
    83	        if isinstance(exc, RendererException):
    84	            raise
    85	        raise_protocol_error(
    86	            backend=_BACKEND,
    87	            message=f"expected_profile is malformed: {exc}",
    88	            details={"error_type": type(exc).__name__},
    89	        )
    90	    return candidate
    91	
    92	
    93	def _validate_declared_profile(profile: Any) -> RenderProfile:
    94	    if not isinstance(profile, RenderProfile):
    95	        _invalid(
    96	            "malformed_profile",
    97	            "renderer video profile is not a RenderProfile",
    98	            received_type=type(profile).__name__,
    99	        )
   100	    try:
   101	        RenderProfile.from_dict(profile.to_dict())
   102	    except Exception as exc:
   103	        _invalid(
   104	            "malformed_profile",
   105	            f"renderer video profile is malformed: {exc}",
   106	            error_type=type(exc).__name__,
   107	        )
   108	    return profile
   109	
   110	
   111	def _workspace_root(path: str | Path) -> Path:
   112	    try:
   113	        root = Path(path).resolve(strict=True)
   114	    except (OSError, RuntimeError) as exc:
   115	        _invalid(
   116	            "invalid_workspace",
   117	            f"cannot resolve invocation workspace: {path}",
   118	            workspace_root=str(path),
   119	            error_type=type(exc).__name__,
   120	        )
   121	    if not root.is_dir():
   122	        _invalid(
   123	            "invalid_workspace",
   124	            f"invocation workspace is not a directory: {root}",
   125	            workspace_root=str(root),
   126	        )
   127	    return root
   128	
   129	
   130	def _validate_relative_path(raw: Any, *, label: str) -> str:
   131	    if not isinstance(raw, str):
   132	        _invalid(
   133	            "invalid_path",
   134	            f"{label} must be a workspace-relative string path",
   135	            path_type=type(raw).__name__,
   136	        )
   137	    if not raw or "\x00" in raw or "\\" in raw:
   138	        _invalid("invalid_path", f"{label} is not a normalized relative path", path=raw)
   139	    if raw.startswith("/") or raw.startswith("//") or _WINDOWS_DRIVE_RE.match(raw):
   140	        _invalid("escaped_path", f"{label} must not be absolute", path=raw)
   141	    parts = raw.split("/")
   142	    if any(
   143	        part in {"", ".", ".."} or not part.strip(_ECMA_WHITESPACE)
   144	        for part in parts
   145	    ):
   146	        _invalid(
   147	            "escaped_path",
   148	            f"{label} contains traversal or a non-normalized component",
   149	            path=raw,
   150	        )
   151	    return raw
   152	
   153	
   154	def _contained_regular_file(raw: Any, *, root: Path, label: str) -> Path:
   155	    relative = _validate_relative_path(raw, label=label)
   156	    candidate = root.joinpath(*relative.split("/"))
   157	    if candidate.is_symlink():
   158	        _invalid(
   159	            "escaped_path",
   160	            f"{label} must not be a symbolic link: {relative}",
   161	            path=relative,
   162	        )
   163	    try:
   164	        resolved = candidate.resolve(strict=True)
   165	    except (OSError, RuntimeError) as exc:
   166	        _invalid(
   167	            "missing_artifact",
   168	            f"{label} does not resolve to an existing file: {relative}",
   169	            path=relative,
   170	            error_type=type(exc).__name__,
   171	        )
   172	    try:
   173	        resolved.relative_to(root)
   174	    except ValueError:
   175	        _invalid(
   176	            "escaped_path",
   177	            f"{label} escapes the invocation workspace",
   178	            path=relative,
   179	            resolved_path=str(resolved),
   180	            workspace_root=str(root),
   181	        )
   182	    try:
   183	        mode = resolved.stat().st_mode
   184	    except OSError as exc:
   185	        _invalid(
   186	            "missing_artifact",
   187	            f"cannot inspect {label}: {relative}",
   188	            path=relative,
   189	            error_type=type(exc).__name__,
   190	        )
   191	    if not stat.S_ISREG(mode):
   192	        _invalid(
   193	            "invalid_file_type",
   194	            f"{label} is not a regular file: {relative}",
   195	            path=relative,
   196	        )
   197	    return resolved
   198	
   199	
   200	def _validate_digest(value: Any, *, label: str) -> str:
   201	    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
   202	        _invalid(
   203	            "invalid_hash",
   204	            f"{label} must declare a lowercase 64-character SHA-256 digest",
   205	            declared_sha256=value if isinstance(value, str) else None,
   206	        )
   207	    return value
   208	
   209	
   210	def _verify_hash(path: Path, declared: Any, *, label: str) -> None:
   211	    declared_hash = _validate_digest(declared, label=label)
   212	    try:
   213	        actual_hash = sha256_file(path)
   214	    except OSError as exc:
   215	        _invalid(
   216	            "hash_failed",
   217	            f"cannot hash {label}",
   218	            path=str(path),
   219	            error_type=type(exc).__name__,
   220	        )
   221	    if actual_hash != declared_hash:
   222	        _invalid(
   223	            "hash_mismatch",
   224	            f"{label} SHA-256 does not match the declared digest",
   225	            path=str(path),
   226	            expected=declared_hash,
   227	            actual=actual_hash,
   228	        )
   229	
   230	
   231	def _rational(value: Any, *, label: str) -> Fraction:
   232	    if (
   233	        not isinstance(value, tuple)
   234	        or len(value) != 2
   235	        or type(value[0]) is not int
   236	        or type(value[1]) is not int
   237	        or value[0] <= 0
   238	        or value[1] <= 0
   239	    ):
   240	        _invalid(
   241	            "incomplete_probe",
   242	            f"ffprobe did not return a valid {label}",
   243	            actual=value,
   244	        )
   245	    return Fraction(value[0], value[1])
   246	
   247	
   248	def _text(value: Any) -> str | None:
   249	    return value.strip().lower() if isinstance(value, str) and value.strip() else None
   250	
   251	
   252	def _level(value: Any) -> str | None:
   253	    normalized = _text(value)
   254	    if normalized is None:
   255	        return None
   256	    if normalized.isdigit() and len(normalized) >= 2:
   257	        return f"{int(normalized[:-1])}.{normalized[-1]}"
   258	    return normalized
   259	
   260	
   261	def _container_matches(probe: MediaProbe, expected: str) -> bool:
   262	    target = expected.lower().lstrip(".")
   263	    probed_container = _text(probe.container)
   264	    if probed_container is not None:
   265	        return probed_container == target
   266	    format_names = {
   267	        item.strip().lower()
   268	        for item in (probe.format_name or "").split(",")
   269	        if item.strip()
   270	    }
   271	    return target in format_names
   272	
   273	
   274	def _profile_value(profile: RenderProfile, field: str) -> Any:
   275	    return getattr(profile, field)
   276	
   277	
   278	def _same_profile_value(field: str, actual: Any, expected: Any) -> bool:
   279	    if field in {"fps_rational", "time_base"}:
   280	        try:
   281	            return Fraction(*actual) == Fraction(*expected)
   282	        except (TypeError, ValueError, ZeroDivisionError):
   283	            return False
   284	    if field == "video_level":
   285	        return _level(actual) == _level(expected)
   286	    if field in {
   287	        "container",
   288	        "video_codec",
   289	        "video_profile",
   290	        "pixel_format",
   291	        "audio_codec",
   292	        "audio_channel_layout",
   293	    }:
   294	        return _text(actual) == _text(expected)
   295	    return actual == expected
   296	
   297	
   298	def _compare_declared_to_expected(
   299	    declared: RenderProfile,
   300	    expected: RenderProfile,
   301	    ownership: AudioOwnership,
   302	) -> None:
   303	    fields = (
   304	        "width",
   305	        "height",
   306	        "fps_rational",
   307	        "time_base",
   308	        "container",
   309	        "video_codec",
   310	        "pixel_format",
   311	    )
   312	    for field in fields:
   313	        actual_value = _profile_value(declared, field)
   314	        expected_value = _profile_value(expected, field)
   315	        if not _same_profile_value(field, actual_value, expected_value):
   316	            _invalid(
   317	                "profile_mismatch",
   318	                f"renderer video profile has incompatible {field}",
   319	                field=field,
   320	                expected=expected_value,
   321	                actual=actual_value,
   322	            )
   323	    for field in ("video_profile", "video_level"):
   324	        expected_value = _profile_value(expected, field)
   325	        if expected_value is not None and not _same_profile_value(
   326	            field, _profile_value(declared, field), expected_value
   327	        ):
   328	            _invalid(
   329	                "profile_mismatch",
   330	                f"renderer video profile has incompatible {field}",
   331	                field=field,
   332	                expected=expected_value,
   333	                actual=_profile_value(declared, field),
   334	            )
   335	
   336	    if ownership is AudioOwnership.RENDERED:
   337	        if not expected.has_audio:
   338	            _invalid(
   339	                "audio_profile_mismatch",
   340	                "renderer declared rendered audio for a visual-only canonical profile",
   341	                expected_audio=False,
   342	                actual_audio=True,
   343	            )
   344	        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
   345	            if not _same_profile_value(
   346	                field, _profile_value(declared, field), _profile_value(expected, field)
   347	            ):
   348	                _invalid(
   349	                    "audio_profile_mismatch",
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
   450	            if field == "audio_channel_layout" and actual is None:
   451	                # Some containers (QuickTime sowt) expose channel COUNT but
   452	                # not a named layout. Compare channel count against the
   453	                # declared layout's canonical count instead of failing.
   454	                expected_channels = _layout_channel_count(expected)
   455	                if expected_channels is None or probe.audio_channels != expected_channels:
   456	                    _invalid(
   457	                        "audio_profile_mismatch",
   458	                        f"probed audio channel layout/count does not match {label}",
   459	                        field=field,
   460	                        expected=expected,
   461	                        actual=actual,
   462	                        probed_channels=probe.audio_channels,
   463	                    )
   464	                continue
   465	            if not _same_profile_value(field, actual, expected):
   466	                _invalid(
   467	                    "audio_profile_mismatch",
   468	                    f"probed audio {field} does not match {label}",
   469	                    field=field,
   470	                    expected=expected,
   471	                    actual=actual,
   472	                )
   473	
   474	
   475	def _layout_channel_count(layout: str | None) -> int | None:
   476	    return {
   477	        "mono": 1,
   478	        "stereo": 2,
   479	        "5.1": 6,
   480	        "5.1(side)": 6,
   481	        "7.1": 8,
   482	        "7.1(wide)": 8,
   483	    }.get(layout or "")
   484	
   485	
   486	def _validate_audio(
   487	    probe: MediaProbe,
   488	    *,
   489	    ownership: AudioOwnership,
   490	    declared: RenderProfile,
   491	    expected: RenderProfile,
   492	) -> None:
   493	    has_audio = probe.has_audio_stream
   494	    if has_audio:
   495	        missing = [
   496	            field
   497	            for field in ("audio_codec", "audio_sample_rate")
   498	            if getattr(probe, field) is None
   499	        ]
   500	        if probe.audio_channel_layout is None and probe.audio_channels is None:
   501	            missing.append("audio_channel_layout/audio_channels")
   502	        if missing:
   503	            _invalid(
   504	                "incomplete_probe",
   505	                "ffprobe returned an audio stream with incomplete metadata",
   506	                missing=missing,
   507	            )
   508	
   509	    if ownership is AudioOwnership.RENDERED and not has_audio:
   510	        _invalid(
   511	            "audio_ownership_mismatch",
   512	            "renderer declared audio_ownership='rendered' but the video has no audio stream",
   513	            declared_ownership=ownership.value,
   514	            actual_audio_stream=False,
   515	        )
   516	    if ownership in {AudioOwnership.NONE, AudioOwnership.PASSTHROUGH} and has_audio:
   517	        _invalid(
   518	            "audio_ownership_mismatch",
   519	            f"renderer declared audio_ownership={ownership.value!r} but the video has an audio stream",
   520	            declared_ownership=ownership.value,
   521	            actual_audio_stream=True,
   522	        )
   523	    if declared.has_audio != has_audio:
   524	        _invalid(
   525	            "audio_profile_mismatch",
   526	            "declared artifact audio profile does not match probed stream presence",
   527	            declared_audio=declared.has_audio,
   528	            actual_audio_stream=has_audio,
   529	        )
   530	    if has_audio:
   531	        _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=True)
   532	        _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=True)
   533	
   534	
   535	def _duration_fraction(probe: MediaProbe) -> Fraction:
   536	    if probe.duration_rational is not None:
   537	        try:
   538	            duration = Fraction(*probe.duration_rational)
   539	        except (TypeError, ValueError, ZeroDivisionError):
   540	            _invalid(
   541	                "incomplete_probe",
   542	                "ffprobe returned an invalid rational duration",
   543	                actual=probe.duration_rational,
   544	            )
   545	    else:
   546	        seconds = probe.duration_seconds
   547	        if seconds is None or not math.isfinite(seconds):
   548	            _invalid(
   549	                "incomplete_probe",
   550	                "ffprobe returned an invalid duration",
   551	                actual=seconds,
   552	            )
   553	        duration = Fraction(str(seconds))
   554	    if duration < 0:
   555	        _invalid(
   556	            "incomplete_probe",
   557	            "ffprobe returned a negative duration",
   558	            actual=float(duration),
   559	        )
   560	    return duration
   561	
   562	
   563	def _validate_duration(
   564	    probe: MediaProbe,
   565	    *,
   566	    duration_frames: Any,
   567	    expected: RenderProfile,
   568	) -> None:
   569	    if type(duration_frames) is not int or duration_frames <= 0:
   570	        _invalid(
   571	            "invalid_duration",
   572	            "video artifact duration_frames must be a positive integer",
   573	            declared_duration_frames=duration_frames,
   574	        )
   575	    fps = Fraction(*expected.fps_rational)
   576	    actual_frames = _duration_fraction(probe) * fps
   577	    delta = abs(actual_frames - duration_frames)
   578	    if delta > expected.duration_tolerance:
   579	        _invalid(
   580	            "duration_mismatch",
   581	            "probed video duration is outside the canonical frame tolerance",
   582	            declared_duration_frames=duration_frames,
   583	            actual_duration_frames=float(actual_frames),
   584	            actual_duration_frames_rational=[actual_frames.numerator, actual_frames.denominator],
   585	            tolerance_frames=expected.duration_tolerance,
   586	        )
   587	
   588	
   589	def _validate_attachment(
   590	    key: Any,
   591	    attachment: Any,
   592	    *,
   593	    root: Path,
   594	) -> None:
   595	    if not isinstance(key, str) or not _OUTPUT_NAME_RE.fullmatch(key):
   596	        _invalid(
   597	            "invalid_attachment",
   598	            "attachment map key must be a portable name",
   599	            attachment_name=key if isinstance(key, str) else None,
   600	        )
   601	    if not isinstance(attachment, Attachment):
   602	        _invalid(
   603	            "invalid_attachment",
   604	            f"attachment {key!r} is not an Attachment",
   605	            attachment_name=key,
   606	            received_type=type(attachment).__name__,
   607	        )
   608	    if attachment.name != key or not _OUTPUT_NAME_RE.fullmatch(attachment.name):
   609	        _invalid(
   610	            "invalid_attachment",
   611	            f"attachment {key!r} has an invalid or mismatched name",
   612	            attachment_name=attachment.name,
   613	            map_key=key,
   614	        )
   615	    if not isinstance(attachment.kind, str) or not _KIND_RE.fullmatch(attachment.kind):
   616	        _invalid(
   617	            "invalid_attachment_kind",
   618	            f"attachment {key!r} has an invalid kind",
   619	            attachment_name=key,
   620	            kind=attachment.kind if isinstance(attachment.kind, str) else None,
   621	        )
   622	    path = _contained_regular_file(
   623	        attachment.path,
   624	        root=root,
   625	        label=f"attachment {key!r} path",
   626	    )
   627	    _verify_hash(path, attachment.sha256, label=f"attachment {key!r}")
   628	
   629	
   630	def _validate_result_shape(result: RenderResult) -> tuple[VideoArtifact, AudioOwnership]:
   631	    video = result.video
   632	    if not isinstance(video, VideoArtifact):
   633	        _invalid(
   634	            "malformed_artifact",
   635	            "render result video is not a VideoArtifact",
   636	            received_type=type(video).__name__,
   637	        )
   638	    ownership = result.audio_ownership
   639	    if not isinstance(ownership, AudioOwnership):
   640	        try:
   641	            ownership = AudioOwnership(ownership)
   642	        except (TypeError, ValueError):
   643	            _invalid(
   644	                "audio_ownership_mismatch",
   645	                "render result has an invalid audio_ownership value",
   646	                actual=str(result.audio_ownership),
   647	            )
   648	    if video.audio is not ownership:
   649	        _invalid(
   650	            "audio_ownership_mismatch",
   651	            "video.audio does not match result audio_ownership",
   652	            result_audio=ownership.value,
   653	            video_audio=video.audio.value if isinstance(video.audio, AudioOwnership) else None,
   654	        )
   655	    return video, ownership
   656	
   657	
   658	def validate_render_result(
   659	    result: RenderResult | Mapping[str, Any],
   660	    *,
   661	    expected_profile: RenderProfile | Mapping[str, Any],
   662	    workspace_root: str | Path,
   663	) -> RenderResult:
   664	    """Validate one renderer result before finalization or publication.
   665	
   666	    Every artifact path is resolved inside the invocation workspace, every
   667	    digest is recomputed, and the primary media is strictly probed.  On
   668	    success the same :class:`RenderResult` object is returned, preserving its
   669	    named attachments exactly as supplied.
   670	    """
   671	
   672	    render_result = _coerce_result(result)
   673	    expected = _coerce_expected_profile(expected_profile)
   674	    root = _workspace_root(workspace_root)
   675	    video, ownership = _validate_result_shape(render_result)
   676	    declared = _validate_declared_profile(video.profile)
   677	    _compare_declared_to_expected(declared, expected, ownership)
   678	
   679	    video_path = _contained_regular_file(video.path, root=root, label="primary video path")
   680	    try:

exec
/bin/zsh -lc "rg -n \"audio_channel_layout|RenderProfile|AUDIO_CHANNEL\" astrid/core/rendering/contracts.py tests/core/rendering tests/fixtures/renderer_packs/raw_command -g '*.py' -g '*.json'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/contracts.py:452:class RenderProfile:
astrid/core/rendering/contracts.py:466:    audio_channel_layout: str | None = None
astrid/core/rendering/contracts.py:490:            self.audio_channel_layout,
astrid/core/rendering/contracts.py:496:                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
astrid/core/rendering/contracts.py:508:                "audio_channel_layout",
astrid/core/rendering/contracts.py:509:                _require_string(self.audio_channel_layout, "audio_channel_layout"),
astrid/core/rendering/contracts.py:535:                "audio_channel_layout": self.audio_channel_layout,
astrid/core/rendering/contracts.py:541:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
astrid/core/rendering/contracts.py:555:        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
astrid/core/rendering/contracts.py:569:            audio_channel_layout=data.get("audio_channel_layout"),
astrid/core/rendering/contracts.py:575:    profile: RenderProfile,
astrid/core/rendering/contracts.py:671:    profile: RenderProfile
astrid/core/rendering/contracts.py:680:            if isinstance(self.profile, RenderProfile)
astrid/core/rendering/contracts.py:681:            else RenderProfile.from_dict(_require_mapping(self.profile, "video profile"))
astrid/core/rendering/contracts.py:720:            profile=RenderProfile.from_dict(data["profile"]),
astrid/core/rendering/contracts.py:733:        profile: RenderProfile,
astrid/core/rendering/contracts.py:749:def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
astrid/core/rendering/contracts.py:752:    if isinstance(value, RenderProfile):
astrid/core/rendering/contracts.py:754:    return RenderProfile.from_dict(_require_mapping(value, label))
astrid/core/rendering/contracts.py:784:    profile: RenderProfile | None = None
astrid/core/rendering/contracts.py:1370:    profile: RenderProfile
astrid/core/rendering/contracts.py:1497:                profile=RenderProfile.from_dict(data["profile"]),
astrid/core/rendering/contracts.py:2196:    "RenderProfile",
tests/fixtures/renderer_packs/raw_command/requests/support.json:35:    "audio_channel_layout": "stereo",
tests/fixtures/renderer_packs/raw_command/requests/render.json:35:    "audio_channel_layout": "stereo",
tests/fixtures/renderer_packs/raw_command/backend.py:42:AUDIO_CHANNELS = 2
tests/fixtures/renderer_packs/raw_command/backend.py:48:AUDIO_CHANNEL_LAYOUT = "stereo"
tests/fixtures/renderer_packs/raw_command/backend.py:296:        + struct.pack(">I", 0x00650002 if AUDIO_CHANNELS == 2 else 0x00650000)
tests/fixtures/renderer_packs/raw_command/backend.py:311:        + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
tests/fixtures/renderer_packs/raw_command/backend.py:367:    audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))
tests/fixtures/renderer_packs/raw_command/backend.py:461:            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
tests/fixtures/renderer_packs/raw_command/backend.py:537:            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
tests/core/rendering/test_contracts.py:16:    RenderProfile,
tests/core/rendering/test_contracts.py:52:def _profile(*, audio: bool = True, fps: tuple[int, int] = (24, 1)) -> RenderProfile:
tests/core/rendering/test_contracts.py:53:    return RenderProfile(
tests/core/rendering/test_contracts.py:65:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_contracts.py:153:    profile: RenderProfile | None = None,
tests/core/rendering/test_contracts.py:177:    profile: RenderProfile | None = None,
tests/core/rendering/test_contracts.py:359:        RenderProfile(
tests/core/rendering/test_contracts.py:374:    profile_payload.pop("audio_channel_layout")
tests/core/rendering/test_contracts.py:375:    profile = RenderProfile.from_dict(profile_payload)
tests/core/rendering/test_artifacts.py:16:    RenderProfile,
tests/core/rendering/test_artifacts.py:23:def _profile(*, audio: bool = False, tolerance: int = 1) -> RenderProfile:
tests/core/rendering/test_artifacts.py:24:    return RenderProfile(
tests/core/rendering/test_artifacts.py:36:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:54:        audio_channel_layout="stereo" if audio else None,
tests/core/rendering/test_artifacts.py:66:    profile: RenderProfile | None = None,
tests/core/rendering/test_artifacts.py:318:        ("audio_channel_layout", "mono"),
tests/core/rendering/fixtures/v1/plan.json:99:    "audio_channel_layout": null,
tests/core/rendering/fixtures/v1/finalize.json:101:      "audio_channel_layout": null,
tests/core/rendering/fixtures/v1/finalize.json:131:        "audio_channel_layout": null,
tests/core/rendering/test_profile.py:113:    assert profile.audio_channel_layout == "stereo"
tests/core/rendering/fixtures/v1/result.json:17:      "audio_channel_layout": null,
tests/core/rendering/test_raw_command_fixture.py:181:    assert profile.audio_channel_layout == "stereo"

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '430,585p' && nl -ba tests/core/rendering/test_artifacts.py | sed -n '1,380p' && nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '1,280p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   430	            }
   431	        )
   432	
   433	    @classmethod
   434	    def from_dict(cls, payload: Mapping[str, Any]) -> FrameWindow:
   435	        data = _require_mapping(payload, "frame window")
   436	        _validate_object_keys(
   437	            data,
   438	            required={"start_frame", "end_frame", "fps_rational"},
   439	            allowed={"start_frame", "end_frame", "fps_rational", "source_range", "speed"},
   440	            label="frame window",
   441	        )
   442	        return cls(
   443	            start_frame=data["start_frame"],
   444	            end_frame=data["end_frame"],
   445	            fps_rational=data["fps_rational"],
   446	            source_range=data.get("source_range"),
   447	            speed=data.get("speed"),
   448	        )
   449	
   450	
   451	@dataclass(frozen=True)
   452	class RenderProfile:
   453	    """Resolved media profile used to validate and finalize artifacts."""
   454	
   455	    width: int
   456	    height: int
   457	    fps_rational: tuple[int, int]
   458	    time_base: tuple[int, int]
   459	    video_codec: str
   460	    pixel_format: str
   461	    video_profile: str | None = None
   462	    video_level: str | None = None
   463	    container: str = "mp4"
   464	    audio_codec: str | None = None
   465	    audio_sample_rate: int | None = None
   466	    audio_channel_layout: str | None = None
   467	    duration_tolerance: int = 1
   468	
   469	    def __post_init__(self) -> None:
   470	        object.__setattr__(self, "width", _require_int(self.width, "width", minimum=1))
   471	        object.__setattr__(self, "height", _require_int(self.height, "height", minimum=1))
   472	        object.__setattr__(self, "fps_rational", _require_rational(self.fps_rational, "fps_rational"))
   473	        object.__setattr__(self, "time_base", _require_rational(self.time_base, "time_base"))
   474	        object.__setattr__(self, "video_codec", _require_string(self.video_codec, "video_codec"))
   475	        object.__setattr__(self, "pixel_format", _require_string(self.pixel_format, "pixel_format"))
   476	        object.__setattr__(
   477	            self,
   478	            "video_profile",
   479	            _require_optional_string(self.video_profile, "video_profile"),
   480	        )
   481	        object.__setattr__(
   482	            self,
   483	            "video_level",
   484	            _require_optional_string(self.video_level, "video_level"),
   485	        )
   486	        object.__setattr__(self, "container", _require_string(self.container, "container"))
   487	        audio_values = (
   488	            self.audio_codec,
   489	            self.audio_sample_rate,
   490	            self.audio_channel_layout,
   491	        )
   492	        if any(value is not None for value in audio_values) and not all(
   493	            value is not None for value in audio_values
   494	        ):
   495	            raise ValueError(
   496	                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
   497	                "provided together or all omitted"
   498	            )
   499	        if self.audio_codec is not None:
   500	            object.__setattr__(self, "audio_codec", _require_string(self.audio_codec, "audio_codec"))
   501	            object.__setattr__(
   502	                self,
   503	                "audio_sample_rate",
   504	                _require_int(self.audio_sample_rate, "audio_sample_rate", minimum=1),
   505	            )
   506	            object.__setattr__(
   507	                self,
   508	                "audio_channel_layout",
   509	                _require_string(self.audio_channel_layout, "audio_channel_layout"),
   510	            )
   511	        object.__setattr__(
   512	            self,
   513	            "duration_tolerance",
   514	            _require_int(self.duration_tolerance, "duration_tolerance", minimum=0),
   515	        )
   516	
   517	    @property
   518	    def has_audio(self) -> bool:
   519	        return self.audio_codec is not None
   520	
   521	    def to_dict(self) -> dict[str, Any]:
   522	        return _json_safe_mapping(
   523	            {
   524	                "width": self.width,
   525	                "height": self.height,
   526	                "fps_rational": self.fps_rational,
   527	                "time_base": self.time_base,
   528	                "container": self.container,
   529	                "video_codec": self.video_codec,
   530	                "video_profile": self.video_profile,
   531	                "video_level": self.video_level,
   532	                "pixel_format": self.pixel_format,
   533	                "audio_codec": self.audio_codec,
   534	                "audio_sample_rate": self.audio_sample_rate,
   535	                "audio_channel_layout": self.audio_channel_layout,
   536	                "duration_tolerance": self.duration_tolerance,
   537	            }
   538	        )
   539	
   540	    @classmethod
   541	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
   542	        data = _require_mapping(payload, "render profile")
   543	        required = {
   544	            "width",
   545	            "height",
   546	            "fps_rational",
   547	            "time_base",
   548	            "container",
   549	            "video_codec",
   550	            "video_profile",
   551	            "video_level",
   552	            "pixel_format",
   553	            "duration_tolerance",
   554	        }
   555	        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
   556	        _validate_object_keys(data, required=required, allowed=allowed, label="render profile")
   557	        return cls(
   558	            width=data["width"],
   559	            height=data["height"],
   560	            fps_rational=data["fps_rational"],
   561	            time_base=data["time_base"],
   562	            container=data["container"],
   563	            video_codec=data["video_codec"],
   564	            video_profile=data["video_profile"],
   565	            video_level=data["video_level"],
   566	            pixel_format=data["pixel_format"],
   567	            audio_codec=data.get("audio_codec"),
   568	            audio_sample_rate=data.get("audio_sample_rate"),
   569	            audio_channel_layout=data.get("audio_channel_layout"),
   570	            duration_tolerance=data["duration_tolerance"],
   571	        )
   572	
   573	
   574	def _validate_artifact_audio(
   575	    profile: RenderProfile,
   576	    ownership: AudioOwnership | None,
   577	    label: str,
   578	) -> None:
   579	    """Keep probed media audio and ownership semantically aligned.
   580	
   581	    ``rendered`` means the artifact itself contains audio and therefore has a
   582	    populated audio profile. ``passthrough`` and ``none`` describe visual-only
   583	    artifacts; the former asks the host/finalizer to supply canonical audio.
   584	    """
   585	
     1	from __future__ import annotations
     2	
     3	from dataclasses import replace
     4	from pathlib import Path
     5	
     6	import pytest
     7	
     8	from astrid.core.foundation.hash import sha256_file
     9	from astrid.core.media import MediaProbe
    10	from astrid.core.rendering import artifacts
    11	from astrid.core.rendering.artifacts import validate_render_result
    12	from astrid.core.rendering.contracts import (
    13	    SCHEMA_VERSION,
    14	    Attachment,
    15	    AudioOwnership,
    16	    RenderProfile,
    17	    RenderResult,
    18	    VideoArtifact,
    19	)
    20	from astrid.core.rendering.errors import RendererInvalidArtifactError
    21	
    22	
    23	def _profile(*, audio: bool = False, tolerance: int = 1) -> RenderProfile:
    24	    return RenderProfile(
    25	        width=1280,
    26	        height=720,
    27	        fps_rational=(24, 1),
    28	        time_base=(1, 12288),
    29	        container="mp4",
    30	        video_codec="h264",
    31	        video_profile=None,
    32	        video_level=None,
    33	        pixel_format="yuv420p",
    34	        audio_codec="aac" if audio else None,
    35	        audio_sample_rate=48000 if audio else None,
    36	        audio_channel_layout="stereo" if audio else None,
    37	        duration_tolerance=tolerance,
    38	    )
    39	
    40	
    41	def _probe(*, audio: bool = False, duration: tuple[int, int] = (2, 1)) -> MediaProbe:
    42	    return MediaProbe(
    43	        duration_seconds=float(duration[0] / duration[1]),
    44	        fps=24.0,
    45	        resolution="1280x720",
    46	        width=1280,
    47	        height=720,
    48	        fps_rational=(24, 1),
    49	        time_base=(1, 12288),
    50	        video_codec="h264",
    51	        pixel_format="yuv420p",
    52	        audio_codec="aac" if audio else None,
    53	        audio_sample_rate=48000 if audio else None,
    54	        audio_channel_layout="stereo" if audio else None,
    55	        container="mp4",
    56	        format_name="mov,mp4,m4a,3gp,3g2,mj2",
    57	        duration_rational=duration,
    58	        video_stream_present=True,
    59	        audio_stream_present=audio,
    60	    )
    61	
    62	
    63	def _result(
    64	    root: Path,
    65	    *,
    66	    profile: RenderProfile | None = None,
    67	    ownership: AudioOwnership = AudioOwnership.NONE,
    68	    path: str = "outputs/video.mp4",
    69	    contents: bytes = b"video-bytes",
    70	    write: bool = True,
    71	    attachments: dict[str, Attachment] | None = None,
    72	) -> RenderResult:
    73	    output = root / path
    74	    if write:
    75	        output.parent.mkdir(parents=True, exist_ok=True)
    76	        output.write_bytes(contents)
    77	    digest = sha256_file(output) if output.is_file() else "0" * 64
    78	    video = VideoArtifact(
    79	        path=path,
    80	        profile=profile or _profile(audio=ownership is AudioOwnership.RENDERED),
    81	        sha256=digest,
    82	        duration_frames=48,
    83	        audio=ownership,
    84	        attachments=attachments or {},
    85	    )
    86	    return RenderResult(
    87	        schema_version=SCHEMA_VERSION,
    88	        video=video,
    89	        audio_ownership=ownership,
    90	    )
    91	
    92	
    93	def _assert_invalid(callable_: object, *, reason: str | None = None) -> RendererInvalidArtifactError:
    94	    with pytest.raises(RendererInvalidArtifactError) as caught:
    95	        callable_()  # type: ignore[operator]
    96	    error = caught.value.error
    97	    assert error.kind == "invalid_artifact"
    98	    assert error.backend == "astrid.core"
    99	    assert error.recovery_command
   100	    if reason is not None:
   101	        assert error.details["reason"] == reason
   102	    return caught.value
   103	
   104	
   105	def test_happy_path_preserves_named_attachment_objects(
   106	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   107	) -> None:
   108	    attachment_path = tmp_path / "outputs" / "alpha.bin"
   109	    attachment_path.parent.mkdir(parents=True)
   110	    attachment_path.write_bytes(b"alpha")
   111	    attachment = Attachment(
   112	        name="alpha",
   113	        path="outputs/alpha.bin",
   114	        kind="alpha",
   115	        sha256=sha256_file(attachment_path),
   116	    )
   117	    result = _result(tmp_path, attachments={attachment.name: attachment})
   118	    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())
   119	
   120	    validated = validate_render_result(
   121	        result,
   122	        expected_profile=_profile(),
   123	        workspace_root=tmp_path,
   124	    )
   125	
   126	    assert validated is result
   127	    assert validated.attachments["alpha"] is attachment
   128	
   129	
   130	def test_missing_primary_output_is_rejected(tmp_path: Path) -> None:
   131	    result = _result(tmp_path, write=False)
   132	
   133	    _assert_invalid(
   134	        lambda: validate_render_result(
   135	            result, expected_profile=_profile(), workspace_root=tmp_path
   136	        ),
   137	        reason="missing_artifact",
   138	    )
   139	
   140	
   141	def test_empty_primary_output_is_rejected(tmp_path: Path) -> None:
   142	    result = _result(tmp_path, contents=b"")
   143	
   144	    _assert_invalid(
   145	        lambda: validate_render_result(
   146	            result, expected_profile=_profile(), workspace_root=tmp_path
   147	        ),
   148	        reason="empty_artifact",
   149	    )
   150	
   151	
   152	@pytest.mark.parametrize("bad_path", ["../video.mp4", "/tmp/video.mp4", "outputs/../video.mp4"])
   153	def test_traversal_and_absolute_output_paths_are_rejected(
   154	    tmp_path: Path, bad_path: str
   155	) -> None:
   156	    result = _result(tmp_path)
   157	    object.__setattr__(result.video, "path", bad_path)
   158	
   159	    _assert_invalid(
   160	        lambda: validate_render_result(
   161	            result, expected_profile=_profile(), workspace_root=tmp_path
   162	        ),
   163	        reason="escaped_path",
   164	    )
   165	
   166	
   167	def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
   168	    workspace = tmp_path / "workspace"
   169	    workspace.mkdir()
   170	    outside = tmp_path / "outside.mp4"
   171	    outside.write_bytes(b"video-bytes")
   172	    (workspace / "escape.mp4").symlink_to(outside)
   173	    result = _result(workspace, path="placeholder.mp4")
   174	    object.__setattr__(result.video, "path", "escape.mp4")
   175	    object.__setattr__(result.video, "sha256", sha256_file(outside))
   176	
   177	    _assert_invalid(
   178	        lambda: validate_render_result(
   179	            result, expected_profile=_profile(), workspace_root=workspace
   180	        ),
   181	        reason="escaped_path",
   182	    )
   183	
   184	
   185	def test_primary_hash_mismatch_is_rejected(tmp_path: Path) -> None:
   186	    result = _result(tmp_path)
   187	    object.__setattr__(result.video, "sha256", "f" * 64)
   188	
   189	    _assert_invalid(
   190	        lambda: validate_render_result(
   191	            result, expected_profile=_profile(), workspace_root=tmp_path
   192	        ),
   193	        reason="hash_mismatch",
   194	    )
   195	
   196	
   197	@pytest.mark.parametrize(
   198	    ("field", "value"),
   199	    [
   200	        ("width", 1920),
   201	        ("height", 1080),
   202	        ("fps_rational", (25, 1)),
   203	        ("time_base", (1, 12800)),
   204	        ("container", "webm"),
   205	        ("video_codec", "hevc"),
   206	        ("pixel_format", "yuv444p"),
   207	    ],
   208	)
   209	def test_probed_video_profile_mismatches_are_rejected(
   210	    tmp_path: Path,
   211	    monkeypatch: pytest.MonkeyPatch,
   212	    field: str,
   213	    value: object,
   214	) -> None:
   215	    result = _result(tmp_path)
   216	    monkeypatch.setattr(
   217	        artifacts,
   218	        "ffprobe_metadata_strict",
   219	        lambda _path: replace(_probe(), **{field: value}),
   220	    )
   221	
   222	    _assert_invalid(
   223	        lambda: validate_render_result(
   224	            result, expected_profile=_profile(), workspace_root=tmp_path
   225	        ),
   226	        reason="profile_mismatch",
   227	    )
   228	
   229	
   230	def test_declared_profile_mismatch_is_rejected_before_probe(tmp_path: Path) -> None:
   231	    result = _result(tmp_path)
   232	    object.__setattr__(result.video.profile, "width", 1920)
   233	
   234	    _assert_invalid(
   235	        lambda: validate_render_result(
   236	            result, expected_profile=_profile(), workspace_root=tmp_path
   237	        ),
   238	        reason="profile_mismatch",
   239	    )
   240	
   241	
   242	def test_duration_outside_tolerance_is_rejected(
   243	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   244	) -> None:
   245	    result = _result(tmp_path)
   246	    monkeypatch.setattr(
   247	        artifacts,
   248	        "ffprobe_metadata_strict",
   249	        lambda _path: _probe(duration=(13, 6)),  # 52 frames, declared 48
   250	    )
   251	
   252	    _assert_invalid(
   253	        lambda: validate_render_result(
   254	            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
   255	        ),
   256	        reason="duration_mismatch",
   257	    )
   258	
   259	
   260	def test_duration_at_tolerance_boundary_is_accepted(
   261	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   262	) -> None:
   263	    result = _result(tmp_path)
   264	    monkeypatch.setattr(
   265	        artifacts,
   266	        "ffprobe_metadata_strict",
   267	        lambda _path: _probe(duration=(49, 24)),  # exactly 49 frames
   268	    )
   269	
   270	    assert (
   271	        validate_render_result(
   272	            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
   273	        )
   274	        is result
   275	    )
   276	
   277	
   278	def test_rendered_ownership_without_audio_stream_is_rejected(
   279	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   280	) -> None:
   281	    profile = _profile(audio=True)
   282	    result = _result(
   283	        tmp_path,
   284	        profile=profile,
   285	        ownership=AudioOwnership.RENDERED,
   286	    )
   287	    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())
   288	
   289	    _assert_invalid(
   290	        lambda: validate_render_result(
   291	            result, expected_profile=profile, workspace_root=tmp_path
   292	        ),
   293	        reason="audio_ownership_mismatch",
   294	    )
   295	
   296	
   297	def test_none_ownership_with_audio_stream_is_rejected(
   298	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   299	) -> None:
   300	    result = _result(tmp_path)
   301	    monkeypatch.setattr(
   302	        artifacts, "ffprobe_metadata_strict", lambda _path: _probe(audio=True)
   303	    )
   304	
   305	    _assert_invalid(
   306	        lambda: validate_render_result(
   307	            result, expected_profile=_profile(), workspace_root=tmp_path
   308	        ),
   309	        reason="audio_ownership_mismatch",
   310	    )
   311	
   312	
   313	@pytest.mark.parametrize(
   314	    ("field", "value"),
   315	    [
   316	        ("audio_codec", "opus"),
   317	        ("audio_sample_rate", 44100),
   318	        ("audio_channel_layout", "mono"),
   319	    ],
   320	)
   321	def test_rendered_audio_profile_mismatch_is_rejected(
   322	    tmp_path: Path,
   323	    monkeypatch: pytest.MonkeyPatch,
   324	    field: str,
   325	    value: object,
   326	) -> None:
   327	    profile = _profile(audio=True)
   328	    result = _result(tmp_path, profile=profile, ownership=AudioOwnership.RENDERED)
   329	    monkeypatch.setattr(
   330	        artifacts,
   331	        "ffprobe_metadata_strict",
   332	        lambda _path: replace(_probe(audio=True), **{field: value}),
   333	    )
   334	
   335	    _assert_invalid(
   336	        lambda: validate_render_result(
   337	            result, expected_profile=profile, workspace_root=tmp_path
   338	        ),
   339	        reason="audio_profile_mismatch",
   340	    )
   341	
   342	
   343	def test_passthrough_visual_artifact_may_target_canonical_audio(
   344	    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
   345	) -> None:
   346	    result = _result(tmp_path, ownership=AudioOwnership.PASSTHROUGH)
   347	    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())
   348	
   349	    assert (
   350	        validate_render_result(
   351	            result,
   352	            expected_profile=_profile(audio=True),
   353	            workspace_root=tmp_path,
   354	        )
   355	        is result
   356	    )
   357	
   358	
   359	def _attachment_result(tmp_path: Path) -> tuple[RenderResult, Attachment]:
   360	    path = tmp_path / "attachments" / "data.bin"
   361	    path.parent.mkdir(parents=True)
   362	    path.write_bytes(b"attachment")
   363	    attachment = Attachment(
   364	        name="data",
   365	        path="attachments/data.bin",
   366	        kind="project",
   367	        sha256=sha256_file(path),
   368	    )
   369	    return _result(tmp_path, attachments={"data": attachment}), attachment
   370	
   371	
   372	def test_missing_attachment_is_rejected(tmp_path: Path) -> None:
   373	    result, attachment = _attachment_result(tmp_path)
   374	    (tmp_path / attachment.path).unlink()
   375	
   376	    _assert_invalid(
   377	        lambda: validate_render_result(
   378	            result, expected_profile=_profile(), workspace_root=tmp_path
   379	        ),
   380	        reason="missing_artifact",
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
   280	    # The fixture output must pass STRICT artifact validation against the

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '268,520p' && rg -n \"audio_channels|channels-only|layout/count|_layout_channel_count|incomplete_probe\" tests -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   280	    # The fixture output must pass STRICT artifact validation against the
   281	    # request profile (dimensions, FPS, codecs, pixel format, audio).
   282	    from astrid.core.rendering.artifacts import validate_render_result
   283	    from astrid.core.rendering.contracts import RenderRequest
   284	
   285	    request = json.loads(
   286	        (PACK_ROOT / "requests" / "render.json").read_text(encoding="utf-8")
   287	    )
   288	    parsed_request = RenderRequest.from_dict(request)
   289	    video_abs = workspace / result.video.path
   290	    validate_render_result(
   291	        result,
   292	        expected_profile=parsed_request.profile,
   293	        workspace_root=workspace,
   294	    )
   295	    assert video_abs.is_file()
   296	
   297	    # Determinism: a second invocation produces byte-identical media.
   298	    second_workspace = tmp_path / "workspace-2"
   299	    _, second_result, _ = _run_transport(second_workspace, PACK_ROOT, verb="render")
   300	    first_bytes = (workspace / result.video.path).read_bytes()
   301	    second_bytes = (second_workspace / second_result.video.path).read_bytes()
   302	    assert first_bytes == second_bytes
   303	    assert result.video.sha256 == second_result.video.sha256
   304	
   305	
   306	def test_support_verb_via_command_transport(tmp_path: Path) -> None:
   307	    workspace = tmp_path / "workspace"
   308	    _, report, _ = _run_transport(workspace, PACK_ROOT, verb="support", request_name="support.json")
   309	
   310	    assert isinstance(report, SupportReport)
   311	    assert report.schema_version == 1
   312	    assert report.supported is True
   313	    assert report.reasons == []
   314	    assert report.features == {"media": True, "audio_mode": "rendered"}
   315	    assert report.alternatives == []
   316	    assert report.backend == BACKEND_ID
   317	    assert report.backend_version == "1.0.0"
   318	
   319	
   320	def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
   321	    _run_transport(tmp_path / "workspace-render", PACK_ROOT, verb="render")
   322	    _run_transport(
   323	        tmp_path / "workspace-support",
   324	        PACK_ROOT,
   325	        verb="support",
   326	        request_name="support.json",
   327	    )
   328	
   329	    for root in (tmp_path, PACK_ROOT):
   330	        assert list(root.rglob("run.json")) == [], f"run.json found under {root}"
   331	
   332	
   333	# ---------------------------------------------------------------------------
   334	# Extra pack root and trusted install resolution
   335	# ---------------------------------------------------------------------------
   336	
   337	
   338	def test_fixture_works_from_explicit_extra_pack_root(tmp_path: Path) -> None:
   339	    extra_root = tmp_path / "extra"
   340	    extra_pack = _copy_pack(extra_root)
   341	    empty_source = tmp_path / "empty-source"
   342	    empty_source.mkdir()
   343	
   344	    with (
   345	        mock.patch.object(
   346	            rendering_registry_module,
   347	            "discover_packs",
   348	            side_effect=_scanner(empty_source),
   349	        ),
   350	        mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
   351	    ):
   352	        renderers, _, _ = load_default_registries(
   353	            tmp_path / "project",
   354	            extra_pack_roots=(str(extra_root),),
   355	            include_installed=False,
   356	        )
   357	
   358	    candidate = renderers.get(BACKEND_ID)
   359	    assert candidate.source_kind == "extra"
   360	    assert candidate.execution_eligible is True
   361	
   362	    _, result, workspace = _run_transport(tmp_path / "workspace-extra", extra_pack, verb="render")
   363	    _assert_clean_render(result, workspace)
   364	
   365	
   366	def test_fixture_works_from_trusted_install(tmp_path: Path) -> None:
   367	    astrid_home = tmp_path / "astrid-home"
   368	    empty_source = tmp_path / "empty-source"
   369	    empty_source.mkdir()
   370	    revision = _stage_installed_fixture(astrid_home)
   371	
   372	    with (
   373	        mock.patch.dict(
   374	            os.environ,
   375	            {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
   376	            clear=False,
   377	        ),
   378	        mock.patch.object(
   379	            rendering_registry_module,
   380	            "discover_packs",
   381	            side_effect=_scanner(empty_source),
   382	        ),
   383	    ):
   384	        renderers, _, _ = load_default_registries(tmp_path / "project", include_installed=True)
   385	
   386	    candidate = renderers.get(BACKEND_ID)
   387	    assert candidate.source_kind == "installed"
   388	    assert candidate.execution_eligible is True
   389	
   390	    alias = renderers.get(ALIAS_ID)
   391	    assert alias.id == BACKEND_ID
   392	    assert alias.source_kind == "installed"
   393	    assert alias.execution_eligible is True
   394	
   395	    _, result, workspace = _run_transport(tmp_path / "workspace-installed", revision, verb="render")
   396	    _assert_clean_render(result, workspace)
   397	
   398	    _, support, _ = _run_transport(
   399	        tmp_path / "workspace-installed-support",
   400	        revision,
   401	        verb="support",
   402	        request_name="support.json",
   403	    )
   404	    assert isinstance(support, SupportReport)
   405	    assert support.backend == BACKEND_ID
tests/core/util/test_media.py:206:        assert probe.audio_channels == 2

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '1,90p;405,590p' && cat tests/fixtures/renderer_packs/raw_command/requests/support.json && cat tests/fixtures/renderer_packs/raw_command/requests/render.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   405	    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
   406	
   407	
   408	def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
   409	    _write_json(
   410	        result_path,
   411	        {
   412	            "schema_version": 1,
   413	            "kind": kind,
   414	            "backend": BACKEND_ID,
   415	            "message": message,
   416	            "recovery_command": None,
   417	            "details": details,
   418	        },
   419	    )
   420	
   421	
   422	def _validate_request(request: dict) -> None:
   423	    version = request.get("schema_version")
   424	    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
   425	        raise ValueError(
   426	            f"unsupported request schema_version {version!r}; expected 1"
   427	        )
   428	    output_name = request.get("output_name")
   429	    if not isinstance(output_name, str) or output_name in (".", ".."):
   430	        raise ValueError("output_name must be a non-empty portable basename")
   431	    if not _OUTPUT_NAME_RE.fullmatch(output_name):
   432	        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
   433	    window = request.get("window")
   434	    if window is not None and not isinstance(window, dict):
   435	        raise ValueError("window must be an object or null")
   436	    if isinstance(window, dict):
   437	        end = window.get("end_frame")
   438	        start = window.get("start_frame", 0)
   439	        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
   440	            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
   441	
   442	
   443	def _support(request: dict, result_path: Path) -> int:
   444	    profile = request.get("profile")
   445	    if isinstance(profile, dict):
   446	        # The renderer emits a fixed profile; ANY deviation is unsupported
   447	        # (fail closed on every field, not just codecs/dimensions).
   448	        mismatches: list[str] = []
   449	        expected = {
   450	            "width": WIDTH,
   451	            "height": HEIGHT,
   452	            "fps_rational": list(FPS_RATIONAL),
   453	            "time_base": list(TIME_BASE),
   454	            "container": CONTAINER,
   455	            "video_codec": VIDEO_CODEC,
   456	            "video_profile": None,
   457	            "video_level": None,
   458	            "pixel_format": PIXEL_FORMAT,
   459	            "audio_codec": AUDIO_CODEC,
   460	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   461	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   462	        }
   463	        for field, fixed in expected.items():
   464	            requested = profile.get(field)
   465	            if requested is not None and requested != fixed:
   466	                mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
   467	        if mismatches:
   468	            _write_json(
   469	                result_path,
   470	                {
   471	                    "schema_version": 1,
   472	                    "supported": False,
   473	                    "reasons": [
   474	                        "profile not produced by " + BACKEND_ID + ": "
   475	                        + "; ".join(mismatches)
   476	                    ],
   477	                    "features": {"media": False, "audio_mode": "none"},
   478	                    "alternatives": [],
   479	                    "backend": BACKEND_ID,
   480	                    "backend_version": "1.0.0",
   481	                },
   482	            )
   483	            return 0
   484	    _write_json(
   485	        result_path,
   486	        {
   487	            "schema_version": 1,
   488	            "supported": True,
   489	            "reasons": [],
   490	            "features": {"media": True, "audio_mode": "rendered"},
   491	            "alternatives": [],
   492	            "backend": BACKEND_ID,
   493	            "backend_version": BACKEND_VERSION,
   494	        },
   495	    )
   496	    return 0
   497	
   498	
   499	def _render(request: dict, result_path: Path, request_path: Path) -> int:
   500	    try:
   501	        _validate_request(request)
   502	        window = request.get("window")
   503	        profile = request.get("profile") or {}
   504	        if isinstance(window, dict):
   505	            start = int(window.get("start_frame", 0))
   506	            end = int(window["end_frame"])
   507	        else:
   508	            start, end = 0, 48
   509	        frames = end - start
   510	        if frames <= 0:
   511	            raise ValueError("window must span at least one frame")
   512	
   513	        output_name = request["output_name"]
   514	        # The invocation workspace is the directory holding the request file;
   515	        # keep every generated artifact contained there.
   516	        workspace = request_path.resolve().parent
   517	        out_dir = workspace / "outputs"
   518	        out_dir.mkdir(parents=True, exist_ok=True)
   519	        video_rel = f"outputs/{output_name}"
   520	        video_path = out_dir / output_name
   521	
   522	        media = _build_mp4(frames)
   523	        video_path.write_bytes(media)
   524	
   525	        probed_profile = {
   526	            "width": WIDTH,
   527	            "height": HEIGHT,
   528	            "fps_rational": list(FPS_RATIONAL),
   529	            "time_base": list(TIME_BASE),
   530	            "container": CONTAINER,
   531	            "video_codec": VIDEO_CODEC,
   532	            "video_profile": None,
   533	            "video_level": None,
   534	            "pixel_format": PIXEL_FORMAT,
   535	            "audio_codec": AUDIO_CODEC,
   536	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   537	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   538	            "duration_tolerance": int(profile.get("duration_tolerance", 1)),
   539	        }
   540	        result = {
   541	            "schema_version": 1,
   542	            "video": {
   543	                "path": video_rel,
   544	                "profile": probed_profile,
   545	                "sha256": hashlib.sha256(media).hexdigest(),
   546	                "duration_frames": frames,
   547	                "audio": "rendered",
   548	                "attachments": {},
   549	            },
   550	            "backend_fragments": {
   551	                BACKEND_ID: {
   552	                    "renderer": "raw_command",
   553	                    "media": "generated",
   554	                    "audio_mode": "rendered",
   555	                    "deterministic": True,
   556	                }
   557	            },
   558	            "audio_ownership": "rendered",
   559	            "normalization": [],
   560	            "logs": [],
   561	            "metadata": {},
   562	        }
   563	        _write_json(result_path, result)
   564	        return 0
   565	    except ValueError as exc:
   566	        _write_error(result_path, "protocol", str(exc), {"error_type": "ValueError"})
   567	        return 0
   568	    except Exception as exc:  # pragma: no cover - unexpected failure path
   569	        _write_error(
   570	            result_path,
   571	            "internal",
   572	            f"raw_command renderer failed: {exc}",
   573	            {"error_type": type(exc).__name__},
   574	        )
   575	        return 0
   576	
   577	
   578	def main(argv: list[str]) -> int:
   579	    parser = argparse.ArgumentParser(
   580	        prog="backend.py",
   581	        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
   582	    )
   583	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
   584	    parser.add_argument("--request", required=True, help="absolute path to request JSON")
   585	    parser.add_argument("--result", required=True, help="absolute path to result JSON")
   586	    args = parser.parse_args(argv)
   587	
   588	    request_path = Path(args.request)
   589	    result_path = Path(args.result)
   590	    try:
{
  "schema_version": 1,
  "timeline_path": "timeline.json",
  "assets_registry_path": null,
  "output_name": "raw_command.mp4",
  "window": {
    "start_frame": 0,
    "end_frame": 48,
    "fps_rational": [
      24,
      1
    ],
    "source_range": null,
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
    "video_profile": null,
    "video_level": null,
    "pixel_format": "yuv420p",
    "audio_codec": "pcm_s16le",
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
    "purpose": "T2.2 raw protocol fixture support"
  }
}
{
  "schema_version": 1,
  "timeline_path": "timeline.json",
  "assets_registry_path": null,
  "output_name": "raw_command.mp4",
  "window": {
    "start_frame": 0,
    "end_frame": 48,
    "fps_rational": [
      24,
      1
    ],
    "source_range": null,
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
    "video_profile": null,
    "video_level": null,
    "pixel_format": "yuv420p",
    "audio_codec": "pcm_s16le",
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

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '578,660p' && git diff --unified=120 8c195bf0..9db48731 -- tests/fixtures/renderer_packs/raw_command/backend.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   578	def main(argv: list[str]) -> int:
   579	    parser = argparse.ArgumentParser(
   580	        prog="backend.py",
   581	        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
   582	    )
   583	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
   584	    parser.add_argument("--request", required=True, help="absolute path to request JSON")
   585	    parser.add_argument("--result", required=True, help="absolute path to result JSON")
   586	    args = parser.parse_args(argv)
   587	
   588	    request_path = Path(args.request)
   589	    result_path = Path(args.result)
   590	    try:
   591	        request = json.loads(request_path.read_text(encoding="utf-8"))
   592	        if not isinstance(request, dict):
   593	            raise TypeError(
   594	                f"request must be a JSON object, got {type(request).__name__}"
   595	            )
   596	    except Exception as exc:
   597	        _write_error(
   598	            result_path,
   599	            "protocol",
   600	            f"cannot read request JSON from {request_path}: {exc}",
   601	            {"error_type": type(exc).__name__},
   602	        )
   603	        return 0
   604	
   605	    if args.verb == "support":
   606	        try:
   607	            _validate_request(request)
   608	        except ValueError as exc:
   609	            _write_error(
   610	                result_path,
   611	                "protocol",
   612	                f"invalid support request: {exc}",
   613	                {"error_type": type(exc).__name__},
   614	            )
   615	            return 0
   616	        return _support(request, result_path)
   617	    if args.verb in ("plan", "finalize"):
   618	        _write_error(
   619	            result_path,
   620	            "unsupported",
   621	            f"{BACKEND_ID} only implements render and support",
   622	            {"verb": args.verb},
   623	        )
   624	        return 0
   625	    return _render(request, result_path, request_path)
   626	
   627	
   628	if __name__ == "__main__":
   629	    raise SystemExit(main(sys.argv[1:]))
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 783fb243..ffdc422d 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -169,407 +169,427 @@ def _idr_slice_nal(frame_index: int) -> bytes:
 
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
+    # Canonical QuickTime channel layout atom (FFmpeg movenc format):
+    # version(2) + revision(2) + layout_tag(4) + bitmap(4) +
+    # num_descriptions(4). Stereo layout tag = 0x00650002.
+    chan = _box(
+        b"chan",
+        struct.pack(">H", 0)   # version
+        + struct.pack(">H", 0)  # revision
+        + struct.pack(">I", 0x00650002 if AUDIO_CHANNELS == 2 else 0x00650000)
+        + struct.pack(">I", 0)  # bitmap (kAudioChannelBit_None)
+        + struct.pack(">I", 0),  # num channel descriptions
+    )
     wave = _box(
         b"wave",
         _box(b"frma", b"sowt")
         + _box(b"enda", struct.pack(">H", 1))
-        + _box(
-            b"chan",
-            struct.pack(">I", 0)  # version/flags
-            + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)  # layout tag
-            + struct.pack(">I", 0),  # bitmap
-        ),
+        + chan,
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
     return _box(b"sowt", audio + wave)
 
 
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
     profile = request.get("profile")
     if isinstance(profile, dict):
-        # The renderer can only produce its own exact codec set; a request
-        # for a different codec is unsupported (fail closed).
-        if (
-            profile.get("audio_codec") not in (None, AUDIO_CODEC)
-            or profile.get("video_codec") not in (None, VIDEO_CODEC)
-            or profile.get("width") not in (None, WIDTH)
-            or profile.get("height") not in (None, HEIGHT)
-        ):
+        # The renderer emits a fixed profile; ANY deviation is unsupported
+        # (fail closed on every field, not just codecs/dimensions).
+        mismatches: list[str] = []
+        expected = {
+            "width": WIDTH,
+            "height": HEIGHT,
+            "fps_rational": list(FPS_RATIONAL),
+            "time_base": list(TIME_BASE),
+            "container": CONTAINER,
+            "video_codec": VIDEO_CODEC,
+            "video_profile": None,
+            "video_level": None,
+            "pixel_format": PIXEL_FORMAT,
+            "audio_codec": AUDIO_CODEC,
+            "audio_sample_rate": AUDIO_SAMPLE_RATE,
+            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
+        }
+        for field, fixed in expected.items():
+            requested = profile.get(field)
+            if requested is not None and requested != fixed:
+                mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
+        if mismatches:
             _write_json(
                 result_path,
                 {
                     "schema_version": 1,
                     "supported": False,
                     "reasons": [
-                        f"requested profile {profile.get('audio_codec')}/"
-                        f"{profile.get('video_codec')} is not produced by {BACKEND_ID}"
+                        "profile not produced by " + BACKEND_ID + ": "
+                        + "; ".join(mismatches)
                     ],
                     "features": {"media": False, "audio_mode": "none"},
                     "alternatives": [],
                     "backend": BACKEND_ID,
                     "backend_version": "1.0.0",
                 },
             )
             return 0
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
         if not isinstance(request, dict):
             raise TypeError(
                 f"request must be a JSON object, got {type(request).__name__}"
             )

exec
/bin/zsh -lc 'rg -n "def _support|profile not produced|supported.*false|support.*profile|SupportRequest|support request" astrid tests docs .oracle/tasklist.md | head -240' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/tasklist.md:83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
docs/contracts/render-backend-v1.md:76:whole-timeline and window support, output-profile labels, and possible audio
tests/core/rendering/test_contracts.py:85:def _support(backend: str = "acme.example") -> SupportReport:
tests/core/rendering/test_schema_roundtrip.py:164:def _support_cases() -> list[tuple[str, dict[str, Any]]]:
tests/fixtures/renderer_packs/raw_command/backend.py:443:def _support(request: dict, result_path: Path) -> int:
tests/fixtures/renderer_packs/raw_command/backend.py:474:                        "profile not produced by " + BACKEND_ID + ": "
tests/fixtures/renderer_packs/raw_command/backend.py:612:                f"invalid support request: {exc}",
astrid/core/integrations/arnold/session/lowering.py:308:def _supports_repeat_until(stage_type: type[Any]) -> bool:

exec
/bin/zsh -lc "sed -n '1,180p' docs/contracts/render-backend-v1.md && rg -n \"RenderRequest\" astrid/core/rendering/contracts.py | head -20 && nl -ba astrid/core/rendering/contracts.py | sed -n '740,920p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
# Render backend protocol v1

Status: **frozen M1 interoperability contract**. This document and the JSON
Schemas under `astrid/core/rendering/schemas/v1/` are the boundary that M2 SDKs,
scaffolds, and non-Python implementations must use. The schemas are normative
for wire shape; this document is normative for lifecycle and semantic rules
that JSON Schema cannot express, such as `end_frame > start_frame` and
workspace containment after symlink resolution.

This contract defines data and ownership only. Discovery, transport, the render
service, built-in backends, and installation tooling are implemented in later
batches.

## Identity, discovery, and trust

A renderer, planner, or finalizer has a qualified ID with at least one dot,
such as `rendering.remotion`, `rendering.legacy_hybrid`, or the canonical
`rendering.ffmpeg-finalizer`. Each dot-separated ID segment matches
`[a-z0-9][a-z0-9_-]*`: lowercase ASCII letters, digits, hyphens, and
underscores are valid. Bare `remotion` and `ffmpeg` are legacy selectors
translated by the host; `hybrid` names a planning policy and is never a
renderer ID.

Packs advertise static manifests through the strict pack extension:

```yaml
extensions:
  rendering:
    renderers:
      - backends/example/renderer.yaml
    planners:
      - planners/example/planner.yaml
    finalizers:
      - finalizers/example/finalizer.yaml
```

Paths are pack-relative, must stay within the pack root after resolution, and
are parsed without importing or executing backend code. Normal pack
precedence, conflicts, aliases, overrides, and permissions apply. Only an
execution-eligible discovered candidate may run:

- source and local packs are eligible;
- an extra pack root is eligible only when explicitly supplied;
- environment-discovered packs remain inspectable but are not executable;
- an installed pack is eligible only when its active revision and installation
  trust audit are valid and its required permissions have been accepted;
- corrupt, missing, mismatched, inactive, or insufficient-permission records
  fail closed.

Trust and permission declarations do not create an operating-system sandbox.
An eligible command retains the invoking user's OS authority, subject to the
host's sanitized environment and invocation staging.

## Manifest format

The three manifest schemas are `renderer-manifest.json`,
`planner-manifest.json`, and `finalizer-manifest.json`. Their shared fields are:

| Field | Contract |
| --- | --- |
| `schema_version` | Integer `1`; version of this manifest shape. |
| `id` | Qualified implementation ID. |
| `name` | Non-empty display name. |
| `version` | Non-empty implementation version. |
| `protocol_version` | Integer `1`; command/wire protocol implemented. |
| `command` | Non-empty argv prefix. The host appends the operation and flags. It is never evaluated by a shell. |
| `operations` | Unique supported operations. A renderer must contain `render`, a planner `plan`, and a finalizer `finalize`; `support` is optional. |
| `description` | Optional human-readable description. |
| `capabilities` | Coarse static discovery hints. Missing hints mean unknown/unsupported; a support probe is authoritative. |
| `required_permissions` | Unique subset of `project_files`, `network`, `subprocess`, `environment`, `accelerator`, and `external_services`. |
| `required_binaries` | Unique binary names checked before invocation. |
| `timeout_seconds` | Optional positive default timeout. Host policy may impose a stricter limit. |
| `metadata` | String-to-string descriptive metadata. |

Renderer capability hints cover clip and track types, boolean/string features,
whole-timeline and window support, output-profile labels, and possible audio
ownership modes. Planner hints cover named policies and fallback support.
Finalizer hints cover containers, attachment preservation, audio modes, and
features. Hints are intentionally coarse; they cannot override a request-
sensitive `SupportReport`.

Example renderer manifest:

```yaml
schema_version: 1
id: acme.example
name: Acme Example Renderer
version: 1.0.0
protocol_version: 1
command: [python3, render.py]
operations: [render, support]
description: Deterministic example renderer
capabilities:
  clip_types: [media]
  track_types: [visual]
  features: {transitions: false}
  supports_full_timeline: true
  supports_windows: true
  output_profiles: [video/mp4]
  audio_ownership: [passthrough, none]
required_permissions: [project_files, subprocess]
required_binaries: [ffmpeg]
timeout_seconds: 300
metadata: {vendor: Acme}
```

Manifests cannot set a working directory or inject arbitrary environment
variables. The host owns pack-root `cwd`, environment filtering, request/result
paths, process lifetime, and cleanup.

## Synchronous command protocol

V1 has exactly four operations. The transport invokes a manifest's argv prefix
with `shell=False`, the owning pack root as `cwd`, a sanitized environment, and
absolute request/result paths:

```text
<command...> render   --request <absolute-request.json> --result <absolute-result.json>
<command...> support  --request <absolute-request.json> --result <absolute-result.json>
<command...> plan     --request <absolute-request.json> --result <absolute-result.json>
<command...> finalize --request <absolute-request.json> --result <absolute-result.json>
```

The payload mapping is:

| Operation | Request schema | Successful result schema |
| --- | --- | --- |
| `render` | `request.json` | successful branch of `result.json` |
| `support` | `request.json` | `support.json` |
| `plan` | `request.json` | `plan.json` |
| `finalize` | `finalize.json` | successful branch of `result.json` |

`result.json` also defines the structured `RendererError` branch. The result
file is authoritative; stdout and stderr are captured diagnostics, not a
second protocol channel. Exit zero without the required result file, malformed
JSON, the wrong result shape, or an unrecognized version is a `protocol`
failure. A nonzero exit is mapped to a structured failure even if diagnostics
were printed. V1 is synchronous: submit/status/cancel/resume semantics require
a future protocol version.

## Wire primitives

JSON numbers must be finite. Python booleans do not count as integers. Fixed
objects reject unknown properties. Optional fields may be omitted; canonical
SDK serialization fills schema defaults and emits nullable values as JSON
`null`.

### Rational values and frame windows

`fps_rational` and `time_base` are two-item JSON arrays `[numerator,
denominator]` of positive integers. Decimal FPS is not authoritative. A
`FrameWindow` is:

```json
{
  "start_frame": 0,
  "end_frame": 48,
  "fps_rational": [24, 1],
  "source_range": [0, 48],
  "speed": 1.0
}
```

The interval is always half-open: `[start_frame,end_frame)`, with
`0 <= start_frame < end_frame`. Adjacent windows therefore meet without
sharing a frame. `source_range`, when present, is also a non-negative half-open
integer frame pair. `speed`, when present, is finite and greater than zero.
`null` source range means no separate source trim; `null` speed means canonical
speed `1` inherited from the timeline.

### Render profile

A `RenderProfile` describes the media that must actually be probed, not merely
the requested encoder flags:

- positive `width` and `height`;
- rational `fps_rational` and stream `time_base`;
- non-empty `container`, `video_codec`, and `pixel_format`;
- nullable `video_profile` and `video_level` when the codec does not expose
  them;
775:class RenderRequest:
837:    def from_dict(cls, payload: Mapping[str, Any]) -> RenderRequest:
885:    def for_backend(self, backend: str) -> RenderRequest:
890:        return RenderRequest(
2197:    "RenderRequest",
   740	            path=relative,
   741	            profile=profile,
   742	            sha256=sha256_file(resolved),
   743	            duration_frames=duration_frames,
   744	            audio=audio,
   745	            attachments=dict(attachments or {}),
   746	        )
   747	
   748	
   749	def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
   750	    if value is None and nullable:
   751	        return None
   752	    if isinstance(value, RenderProfile):
   753	        return value
   754	    return RenderProfile.from_dict(_require_mapping(value, label))
   755	
   756	
   757	def _coerce_window(value: Any, label: str, *, nullable: bool) -> FrameWindow | None:
   758	    if value is None and nullable:
   759	        return None
   760	    if isinstance(value, FrameWindow):
   761	        return value
   762	    return FrameWindow.from_dict(_require_mapping(value, label))
   763	
   764	
   765	def _coerce_namespaced_backend_config(value: Any, label: str) -> BackendConfig:
   766	    mapping = _require_mapping(value, label)
   767	    result: BackendConfig = {}
   768	    for raw_backend, raw_config in mapping.items():
   769	        backend = _require_qualified_id(raw_backend, f"{label} key")
   770	        result[backend] = _json_safe_mapping(raw_config, label=f"{label}[{backend!r}]")
   771	    return result
   772	
   773	
   774	@dataclass(frozen=True)
   775	class RenderRequest:
   776	    """Backend-neutral request shared by render, support, and plan operations."""
   777	
   778	    schema_version: int
   779	    timeline_path: str
   780	    output_name: str
   781	    assets_registry_path: str | None = None
   782	    window: FrameWindow | None = None
   783	    audio: AudioOwnership | None = None
   784	    profile: RenderProfile | None = None
   785	    backend_config: BackendConfig = field(default_factory=dict)
   786	    metadata: dict[str, str] = field(default_factory=dict)
   787	
   788	    def __post_init__(self) -> None:
   789	        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
   790	            _protocol_failure(
   791	                f"unknown or malformed render request schema_version "
   792	                f"{self.schema_version!r}; expected integer {SCHEMA_VERSION}",
   793	                details={"received": self.schema_version, "supported": [SCHEMA_VERSION]},
   794	            )
   795	        version = self.schema_version
   796	        object.__setattr__(self, "schema_version", version)
   797	        object.__setattr__(self, "timeline_path", _require_string(self.timeline_path, "timeline_path"))
   798	        object.__setattr__(
   799	            self,
   800	            "assets_registry_path",
   801	            _require_optional_string(self.assets_registry_path, "assets_registry_path"),
   802	        )
   803	        output_name = _require_string(self.output_name, "output_name")
   804	        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
   805	            raise ValueError("output_name must be a portable basename without path separators")
   806	        object.__setattr__(self, "output_name", output_name)
   807	        object.__setattr__(self, "window", _coerce_window(self.window, "window", nullable=True))
   808	        audio = _coerce_audio_ownership(self.audio, "audio", nullable=True)
   809	        profile = _coerce_profile(self.profile, "profile", nullable=True)
   810	        if audio is not None and profile is not None:
   811	            _validate_artifact_audio(profile, audio, "render request")
   812	        object.__setattr__(self, "audio", audio)
   813	        object.__setattr__(self, "profile", profile)
   814	        object.__setattr__(
   815	            self,
   816	            "backend_config",
   817	            _coerce_namespaced_backend_config(self.backend_config, "backend_config"),
   818	        )
   819	        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
   820	
   821	    def to_dict(self) -> dict[str, Any]:
   822	        return _json_safe_mapping(
   823	            {
   824	                "schema_version": self.schema_version,
   825	                "timeline_path": self.timeline_path,
   826	                "assets_registry_path": self.assets_registry_path,
   827	                "output_name": self.output_name,
   828	                "window": self.window,
   829	                "audio": self.audio,
   830	                "profile": self.profile,
   831	                "backend_config": self.backend_config,
   832	                "metadata": self.metadata,
   833	            }
   834	        )
   835	
   836	    @classmethod
   837	    def from_dict(cls, payload: Mapping[str, Any]) -> RenderRequest:
   838	        try:
   839	            data = _require_mapping(payload, "render request")
   840	            allowed = {
   841	                "schema_version",
   842	                "timeline_path",
   843	                "assets_registry_path",
   844	                "output_name",
   845	                "window",
   846	                "audio",
   847	                "profile",
   848	                "backend_config",
   849	                "metadata",
   850	            }
   851	            _validate_object_keys(
   852	                data,
   853	                required={"schema_version", "timeline_path", "output_name"},
   854	                allowed=allowed,
   855	                label="render request",
   856	            )
   857	            version = data["schema_version"]
   858	            if type(version) is not int or version != SCHEMA_VERSION:
   859	                _protocol_failure(
   860	                    f"unknown or malformed render request schema_version {version!r}; "
   861	                    f"expected integer {SCHEMA_VERSION}",
   862	                    details={"received": version, "supported": [SCHEMA_VERSION]},
   863	                )
   864	            return cls(
   865	                schema_version=version,
   866	                timeline_path=data["timeline_path"],
   867	                assets_registry_path=data.get("assets_registry_path"),
   868	                output_name=data["output_name"],
   869	                window=data.get("window"),
   870	                audio=data.get("audio"),
   871	                profile=data.get("profile"),
   872	                backend_config=data.get("backend_config", {}),
   873	                metadata=data.get("metadata", {}),
   874	            )
   875	        except Exception as exc:
   876	            from .errors import RendererException
   877	
   878	            if isinstance(exc, RendererException):
   879	                raise
   880	            _protocol_failure(
   881	                f"malformed render request: {exc}",
   882	                details={"error_type": type(exc).__name__},
   883	            )
   884	
   885	    def for_backend(self, backend: str) -> RenderRequest:
   886	        """Return the request projection visible to one selected backend."""
   887	
   888	        qualified = _require_qualified_id(backend, "backend")
   889	        selected = self.backend_config.get(qualified)
   890	        return RenderRequest(
   891	            schema_version=self.schema_version,
   892	            timeline_path=self.timeline_path,
   893	            assets_registry_path=self.assets_registry_path,
   894	            output_name=self.output_name,
   895	            window=self.window,
   896	            audio=self.audio,
   897	            profile=self.profile,
   898	            backend_config={qualified: selected} if selected is not None else {},
   899	            metadata=self.metadata,
   900	        )
   901	
   902	
   903	@dataclass(frozen=True)
   904	class SupportReport:
   905	    """Request-sensitive support evidence returned by an implementation."""
   906	
   907	    schema_version: int
   908	    supported: bool
   909	    reasons: list[str]
   910	    features: dict[str, bool | str]
   911	    alternatives: list[str]
   912	    backend: str
   913	    backend_version: str | None = None
   914	
   915	    def __post_init__(self) -> None:
   916	        object.__setattr__(
   917	            self,
   918	            "schema_version",
   919	            _require_schema_version(self.schema_version, "support report"),
   920	        )

exec
/bin/zsh -lc "rg -n \"publish_render_result\\(|read_committed_provenance\\(|_delete_previous_outputs\\(|_render_with_publication_context|_PUBLICATION_PREVIOUS_OUTPUTS|out_path.*resolve|Path\\(out_path\\)\" astrid -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/cli/project.py:367:    out_path = Path(args.out).expanduser().resolve()
astrid/packs/foley/executors/foley_review/run.py:144:    out_path = args.out.expanduser().resolve()
astrid/core/pack/install_git.py:262:    checkout_path = Path(checkout).resolve()
astrid/core/cli/timeline_output.py:49:    out_path = Path(args.out).expanduser().resolve()
astrid/core/cli/timeline_events.py:622:        out_path = Path(out_path_raw).expanduser().resolve()
astrid/core/cli/timeline_events.py:627:            out_path.relative_to(timeline_home_resolved)
astrid/core/cli/timeline_events.py:635:                state_snapshot={"out": out_path_raw, "timeline_home": timeline_home_resolved},
astrid/core/rendering/publication.py:157:def read_committed_provenance(
astrid/core/rendering/publication.py:215:    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
astrid/core/rendering/publication.py:235:def _delete_previous_outputs(
astrid/core/rendering/publication.py:288:            provenance = read_committed_provenance(video, sidecar_path=sidecar)
astrid/core/rendering/publication.py:305:def publish_render_result(
astrid/core/rendering/publication.py:329:    output_unresolved = Path(out_path).expanduser()
astrid/core/rendering/publication.py:363:        _delete_previous_outputs(
astrid/core/rendering/publication.py:371:        if read_committed_provenance(output, sidecar_path=sidecar) is None:
astrid/packs/training/orchestrators/training_run/trainer_adapters/ai_toolkit_ltx.py:43:        out_path = Path(str(trainer_config.get("config_path") or Path(dataset_manifest).parent / "config.yaml")).expanduser().resolve()
astrid/packs/editorial/executors/human_review/run.py:532:        out_path=args.out.resolve(),
astrid/packs/editorial/executors/transcribe/run.py:59:    out_path = out_dir.resolve() if out_dir else (audio_path.parent / audio_path.stem).resolve()
astrid/packs/editorial/executors/transcribe/run.py:60:    return out_path, cache_dir.resolve() if cache_dir else out_path / "cache"
astrid/packs/video_editing/orchestrators/iteration_video/run.py:42:    out_path = Path(request.out).expanduser().resolve()
astrid/packs/video_editing/orchestrators/iteration_video/run.py:98:    out_path = out_path.expanduser().resolve()
astrid/packs/editorial/executors/quality_zones/run.py:115:    out_path = args.out.resolve()
astrid/packs/training/orchestrators/dataset_build/media.py:44:    target = Path(out_path)
astrid/packs/editorial/executors/scenes/run.py:43:    resolved = out_path.resolve()
astrid/packs/training/orchestrators/dataset_build/manifest_adapters/ai_toolkit_ltx.py:27:        self.out_path = Path(out_path)
astrid/packs/training/orchestrators/dataset_build/manifest_adapters/ai_toolkit_ltx.py:63:        out_path = _resolve_output_path(self.out_path, self.repo_root)
astrid/packs/editorial/executors/validate/run.py:104:    out_path = (args.out or (video_dir / "validation.json")).resolve()
astrid/packs/rendering/executors/render/audio_reactive_colour.py:384:    out_path = out_path.resolve()
astrid/packs/iteration/executors/assemble/run.py:179:    out_path = out_path.expanduser().resolve()
astrid/packs/iteration/executors/prepare/run.py:124:    out_path = out_path.expanduser().resolve()
astrid/packs/rendering/executors/render/run.py:43:_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
astrid/packs/rendering/executors/render/run.py:446:    publication_out = out_path  # unresolved: publication symlink-guards it
astrid/packs/rendering/executors/render/run.py:447:    resolved_out = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:467:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:473:                _PUBLICATION_PREVIOUS_OUTPUTS.get()
astrid/packs/rendering/executors/render/run.py:662:    publication_out = out_path  # unresolved: publication symlink-guards it
astrid/packs/rendering/executors/render/run.py:663:    resolved_out = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:715:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:720:            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
astrid/packs/rendering/executors/render/run.py:846:    digest.update(str(out_path.resolve()).encode("utf-8"))
astrid/packs/rendering/executors/render/run.py:978:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1032:        "output": str(out_path.resolve()),
astrid/packs/rendering/executors/render/run.py:1187:    publication_out = out_path  # unresolved: publication symlink-guards it
astrid/packs/rendering/executors/render/run.py:1188:    resolved_out = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1234:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1239:            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
astrid/packs/rendering/executors/render/run.py:1282:def _render_with_publication_context(
astrid/packs/rendering/executors/render/run.py:1293:    out_path = Path(out_path)
astrid/packs/rendering/executors/render/run.py:1325:    props_path = (out_path.parent / ".remotion-props.json").resolve()
astrid/packs/rendering/executors/render/run.py:1416:            output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1421:                previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
astrid/packs/rendering/executors/render/run.py:1462:    out_path = Path(out_path)
astrid/packs/rendering/executors/render/run.py:1468:    publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
astrid/packs/rendering/executors/render/run.py:1470:        return _render_with_publication_context(
astrid/packs/rendering/executors/render/run.py:1481:        _PUBLICATION_PREVIOUS_OUTPUTS.reset(publication_token)
astrid/packs/blender/deploy.py:547:    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
astrid/packs/blender/deploy.py:548:    Path(out_path).write_bytes(data)
astrid/packs/blender/deploy.py:600:    out_path = str(Path(args.out).expanduser().resolve())
astrid/packs/rendering/executors/timeline_storyboard/run.py:550:    out_path = out_path.expanduser().resolve()

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '800,1065p;1260,1505p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   800	
   801	
   802	def _write_registry_state(project_dir: Path, state: dict[str, Any]) -> None:
   803	    state_path = project_dir / _REGISTRY_STATE_PATH
   804	    state_path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
   805	
   806	
   807	def _regenerate_element_registries(project_dir: Path, theme_path: Path | None) -> None:
   808	    state = _effective_registry_state(theme_path)
   809	    cached_state = _read_registry_state(project_dir)
   810	    if (
   811	        cached_state is not None
   812	        and cached_state.get("hash") == state.get("hash")
   813	        and _registry_outputs_exist(project_dir)
   814	        and _active_theme_pointer_current(theme_path)
   815	    ):
   816	        return
   817	
   818	    generator = REPO_ROOT / "scripts" / "gen_effect_registry.py"
   819	    cmd = [sys.executable, str(generator)]
   820	    if theme_path is not None:
   821	        cmd.extend(["--theme", str(_resolve_theme_path(theme_path))])
   822	    env: dict[str, str] = {}
   823	    composition_src = _timeline_composition_src(project_dir)
   824	    if composition_src is not None:
   825	        env["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
   826	    subprocess.run(
   827	        cmd,
   828	        cwd=str(REPO_ROOT),
   829	        env=build_child_subprocess_env(explicit_env=env),
   830	        capture_output=True,
   831	        check=True,
   832	        text=True,
   833	    )
   834	    _write_registry_state(project_dir, state)
   835	
   836	
   837	def _render_asset_stage_hash(timeline_path: Path, assets_path: Path, out_path: Path) -> str:
   838	    digest = hashlib.sha256()
   839	    for path in (timeline_path, assets_path):
   840	        resolved = path.resolve()
   841	        digest.update(str(resolved).encode("utf-8"))
   842	        digest.update(b"\0")
   843	        if resolved.exists():
   844	            digest.update(resolved.read_bytes())
   845	        digest.update(b"\0")
   846	    digest.update(str(out_path.resolve()).encode("utf-8"))
   847	    return digest.hexdigest()[:16]
   848	
   849	
   850	def _effect_registry_for_assets(theme_path: Path | None) -> tuple[dict[str, ElementDefinition], dict[str, str]]:
   851	    active_theme: Path | None = None
   852	    if theme_path is not None:
   853	        active_theme = _resolve_theme_path(theme_path)
   854	    registry = load_default_registry(active_theme=active_theme, project_root=REPO_ROOT)
   855	    effects = {element.id: element for element in registry.list(kind="effects")}
   856	    aliases: dict[str, str] = {}
   857	    if "text-card" in effects:
   858	        aliases["text"] = "text-card"
   859	    for effect_id, element in effects.items():
   860	        raw_aliases = element.metadata.get("clipTypeAliases")
   861	        if not isinstance(raw_aliases, list):
   862	            continue
   863	        for alias in raw_aliases:
   864	            if isinstance(alias, str) and alias:
   865	                aliases[alias] = effect_id
   866	    return effects, aliases
   867	
   868	
   869	def _effect_id_for_clip(clip: dict[str, Any], effects: dict[str, ElementDefinition], aliases: dict[str, str]) -> str | None:
   870	    clip_type = clip.get("clipType")
   871	    if not isinstance(clip_type, str) or clip_type == "effect-layer":
   872	        return None
   873	    if clip_type in effects:
   874	        return clip_type
   875	    return aliases.get(clip_type)
   876	
   877	
   878	def _source_pack_id(element: ElementDefinition) -> str:
   879	    pack_id = element.metadata.get("pack_id")
   880	    if isinstance(pack_id, str) and pack_id:
   881	        return pack_id
   882	    if element.source.startswith("pack:"):
   883	        return element.source.split(":", 1)[1]
   884	    return element.source
   885	
   886	
   887	def _inject_clip_asset_params(clip: dict[str, Any], staged_assets: dict[str, str]) -> None:
   888	    params = clip.get("params")
   889	    if isinstance(params, dict):
   890	        next_params = dict(params)
   891	    else:
   892	        next_params = {}
   893	    next_params["__astridAssets"] = staged_assets
   894	    clip["params"] = next_params
   895	
   896	
   897	def _stage_effect_assets_for_timeline(
   898	    timeline_data: dict[str, Any],
   899	    *,
   900	    project_dir: Path,
   901	    theme_path: Path | None,
   902	    render_hash: str,
   903	) -> dict[str, Any]:
   904	    effects, aliases = _effect_registry_for_assets(theme_path)
   905	    clips = timeline_data.get("clips")
   906	    if not isinstance(clips, list):
   907	        return {"root": None, "effects": []}
   908	
   909	    used_effect_ids: set[str] = set()
   910	    clip_effect_ids: dict[int, str] = {}
   911	    clip_ids_by_effect: dict[str, list[str]] = {}
   912	    for index, clip in enumerate(clips):
   913	        if not isinstance(clip, dict):
   914	            continue
   915	        effect_id = _effect_id_for_clip(clip, effects, aliases)
   916	        if effect_id is None:
   917	            continue
   918	        element = effects[effect_id]
   919	        used_effect_ids.add(effect_id)
   920	        clip_effect_ids[index] = effect_id
   921	        clip_id = clip.get("id")
   922	        if isinstance(clip_id, str) and clip_id:
   923	            clip_ids_by_effect.setdefault(effect_id, []).append(clip_id)
   924	
   925	    if not used_effect_ids:
   926	        return {"root": None, "effects": []}
   927	
   928	    public_root = project_dir / "public" / "astrid-effects" / render_hash
   929	    staged_by_effect: dict[str, dict[str, str]] = {}
   930	    for effect_id in sorted(used_effect_ids):
   931	        element = effects[effect_id]
   932	        staged_assets: dict[str, str] = {}
   933	        for asset in element.assets:
   934	            source = (element.root / asset.path).resolve()
   935	            relative_target = Path(effect_id) / asset.path
   936	            target = public_root / relative_target
   937	            target.parent.mkdir(parents=True, exist_ok=True)
   938	            shutil.copy2(source, target)
   939	            staged_assets[asset.name] = f"astrid-effects/{render_hash}/{relative_target.as_posix()}"
   940	        staged_by_effect[effect_id] = staged_assets
   941	
   942	    for index, effect_id in clip_effect_ids.items():
   943	        clip = clips[index]
   944	        if isinstance(clip, dict) and staged_by_effect[effect_id]:
   945	            _inject_clip_asset_params(clip, staged_by_effect[effect_id])
   946	    return {
   947	        "root": str(public_root),
   948	        "effects": [
   949	            {
   950	                "effect_id": effect_id,
   951	                "source_pack_id": _source_pack_id(effects[effect_id]),
   952	                "source": effects[effect_id].source,
   953	                "element_root": str(effects[effect_id].root),
   954	                "clip_ids": sorted(clip_ids_by_effect.get(effect_id, ())),
   955	                "staged_asset_ids": sorted(staged_by_effect[effect_id]),
   956	                "staged_assets": dict(sorted(staged_by_effect[effect_id].items())),
   957	            }
   958	            for effect_id in sorted(used_effect_ids)
   959	        ],
   960	    }
   961	
   962	
   963	def _render_provenance_sidecar_path(out_path: Path) -> Path:
   964	    return Path(f"{out_path}.provenance.json")
   965	
   966	
   967	def _previous_render_outputs_for_timeline(
   968	    out_path: Path,
   969	    timeline_path: Path,
   970	) -> tuple[Path, ...]:
   971	    """Discover legacy sibling outputs; publication validates before deleting.
   972	
   973	    The timeline argument remains part of the helper boundary for compatibility
   974	    with the legacy cleanup call site.  Filtering now happens under each
   975	    candidate's publication lock using the committed sidecar.
   976	    """
   977	
   978	    out_path = out_path.resolve()
   979	    if out_path.name != "hype.mp4":
   980	        return ()
   981	    run_dir = out_path.parent
   982	    runs_dir = run_dir.parent
   983	    if runs_dir.name != "runs" or not runs_dir.is_dir():
   984	        return ()
   985	    candidates: list[Path] = []
   986	    for candidate_run_dir in runs_dir.iterdir():
   987	        if not candidate_run_dir.is_dir() or candidate_run_dir == run_dir:
   988	            continue
   989	        candidates.append(candidate_run_dir / out_path.name)
   990	    return tuple(candidates)
   991	
   992	
   993	def _active_pack_order_for_provenance() -> list[dict[str, Any]]:
   994	    return [
   995	        {
   996	            "id": discovered.id,
   997	            "source_kind": discovered.source_kind,
   998	            "priority_index": discovered.priority_index,
   999	            "root": str(discovered.pack_dir),
  1000	        }
  1001	        for discovered in discover_pack_metadata(project_root=REPO_ROOT)
  1002	    ]
  1003	
  1004	
  1005	def _active_theme_for_provenance(theme_path: Path | None, active_theme: dict[str, Any] | None) -> dict[str, Any] | None:
  1006	    theme_id = active_theme.get("id") if isinstance(active_theme, dict) else None
  1007	    if theme_path is None:
  1008	        return {"id": theme_id or "banodoco-default", "path": None}
  1009	    resolved = _resolve_theme_path(theme_path)
  1010	    return {"id": theme_id or resolved.parent.name, "path": str(resolved)}
  1011	
  1012	
  1013	def _render_provenance_payload(
  1014	    out_path: Path,
  1015	    *,
  1016	    engine: str,
  1017	    timeline_path: Path,
  1018	    assets_path: Path,
  1019	    project_dir: Path,
  1020	    composition_id: str,
  1021	    theme_path: Path | None,
  1022	    active_theme: dict[str, Any] | None,
  1023	    registry_state: dict[str, Any],
  1024	    stage_summary: dict[str, Any],
  1025	    segments: list[dict[str, float | str]] | None = None,
  1026	    segment_provenance: list[dict[str, Any]] | None = None,
  1027	) -> dict[str, Any]:
  1028	    effects = list(stage_summary.get("effects") or [])
  1029	    payload: dict[str, Any] = {
  1030	        "schema_version": 1,
  1031	        "engine": engine,
  1032	        "output": str(out_path.resolve()),
  1033	        "timeline": str(timeline_path.resolve()),
  1034	        "assets_registry": str(assets_path.resolve()),
  1035	        "project_dir": str(project_dir.resolve()),
  1036	        "composition_id": composition_id,
  1037	        "active_pack_order": _active_pack_order_for_provenance(),
  1038	        "active_theme": _active_theme_for_provenance(theme_path, active_theme),
  1039	        "registry_hash": registry_state.get("hash"),
  1040	        "registry_state": registry_state,
  1041	        "resolved_effect_ids": [str(effect["effect_id"]) for effect in effects if "effect_id" in effect],
  1042	        "resolved_effects": effects,
  1043	        "source_pack_ids": sorted(
  1044	            {
  1045	                str(effect["source_pack_id"])
  1046	                for effect in effects
  1047	                if isinstance(effect, dict) and effect.get("source_pack_id")
  1048	            }
  1049	        ),
  1050	        "element_roots": sorted(
  1051	            {
  1052	                str(effect["element_root"])
  1053	                for effect in effects
  1054	                if isinstance(effect, dict) and effect.get("element_root")
  1055	            }
  1056	        ),
  1057	        "staged_asset_ids": sorted(
  1058	            {
  1059	                str(asset_id)
  1060	                for effect in effects
  1061	                if isinstance(effect, dict)
  1062	                for asset_id in effect.get("staged_asset_ids", ())
  1063	            }
  1064	        ),
  1065	        "staged_asset_root": stage_summary.get("root"),
  1260	            parents=[timeline_id, assets_id],
  1261	            stage="render_ffmpeg_audio_reactive_colour",
  1262	            metadata={
  1263	                "engine": "ffmpeg",
  1264	                "specialization": audio_reactive_colour.ADAPTER_ID,
  1265	                "event_count": len(spec.events),
  1266	                "marker_sha256": spec.marker_sha256,
  1267	            },
  1268	        )
  1269	        audit.register_node(
  1270	            stage="render_ffmpeg_audio_reactive_colour",
  1271	            label="Render audio-reactive colour timeline with FFmpeg",
  1272	            parents=[timeline_id, assets_id],
  1273	            outputs=[render_id],
  1274	            metadata={
  1275	                "engine": "ffmpeg",
  1276	                "specialization": audio_reactive_colour.ADAPTER_ID,
  1277	            },
  1278	        )
  1279	    return output
  1280	
  1281	
  1282	def _render_with_publication_context(
  1283	    timeline_path: Path,
  1284	    assets_path: Path,
  1285	    out_path: Path,
  1286	    *,
  1287	    engine: str = "remotion",
  1288	    project_dir: Path | None = None,
  1289	    composition_id: str = "TimelineComposition",
  1290	    theme_path: Path | None = None,
  1291	    min_free_gb: float | None = None,
  1292	) -> Path:
  1293	    out_path = Path(out_path)
  1294	    audio_reactive_output = _render_audio_reactive_colour_if_supported(
  1295	        timeline_path,
  1296	        assets_path,
  1297	        out_path,
  1298	        project_dir=project_dir,
  1299	        composition_id=composition_id,
  1300	        theme_path=theme_path,
  1301	    )
  1302	    if audio_reactive_output is not None:
  1303	        return audio_reactive_output
  1304	    if engine == "hybrid":
  1305	        return _render_hybrid(
  1306	            timeline_path,
  1307	            assets_path,
  1308	            out_path,
  1309	            project_dir=project_dir,
  1310	            composition_id=composition_id,
  1311	            theme_path=theme_path,
  1312	            min_free_gb=min_free_gb,
  1313	        )
  1314	    if engine == "ffmpeg":
  1315	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
  1316	    if engine != "remotion":
  1317	        raise ValueError(f"Unsupported render engine: {engine}")
  1318	    if _can_render_with_ffmpeg_media(timeline_path, assets_path):
  1319	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
  1320	    project_dir = project_dir or (REPO_ROOT / "remotion")
  1321	    _validate_project_dir(project_dir)
  1322	    _regenerate_element_registries(project_dir, theme_path)
  1323	    registry_state = _effective_registry_state(theme_path)
  1324	    _require_free_space(out_path.parent, min_free_gb)
  1325	    props_path = (out_path.parent / ".remotion-props.json").resolve()
  1326	    render_hash = _render_asset_stage_hash(timeline_path, assets_path, out_path)
  1327	    staged_public_root = project_dir / "public" / "astrid-effects" / render_hash
  1328	    with ExitStack() as asset_lifecycle:
  1329	        try:
  1330	            materializer = asset_lifecycle.enter_context(AssetMaterializer(assets_path))
  1331	            asset_server = None
  1332	            if materializer.needs_server:
  1333	                try:
  1334	                    asset_server = asset_lifecycle.enter_context(
  1335	                        InvocationAssetServer(materializer.staging_dir)
  1336	                    )
  1337	                except OSError as exc:
  1338	                    raise RuntimeError(
  1339	                        f"Permission denied (1100): local HTTP asset server blocked: {exc}"
  1340	                    ) from exc
  1341	            resolved_registry = materializer.resolved_registry(asset_server)
  1342	            resolved_theme = theme_path or (WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json")
  1343	            theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
  1344	            # The timeline references a theme by slug + optional theme_overrides;
  1345	            # theme.visual.canvas is the source of truth for Remotion calculateMetadata.
  1346	            merged_props = {
  1347	                "timeline": _serialize_timeline(
  1348	                    timeline_path,
  1349	                    default_theme=str(theme_for_props.get("id") or "banodoco-default"),
  1350	                ),
  1351	                "assets": resolved_registry,
  1352	                "theme": theme_for_props,
  1353	            }
  1354	            stage_summary = _stage_effect_assets_for_timeline(
  1355	                merged_props["timeline"],
  1356	                project_dir=project_dir,
  1357	                theme_path=theme_path,
  1358	                render_hash=render_hash,
  1359	            )
  1360	            out_path.parent.mkdir(parents=True, exist_ok=True)
  1361	            publication_tmp = asset_lifecycle.enter_context(
  1362	                TemporaryDirectory(
  1363	                    prefix=f".{out_path.name}.publication-",
  1364	                    dir=str(out_path.parent),
  1365	                )
  1366	            )
  1367	            staged_video = Path(publication_tmp) / out_path.name
  1368	            props_path.write_text(json.dumps(merged_props), encoding="utf-8")
  1369	            # Build the Remotion launch env from the canonical safe base plus the
  1370	            # Astrid runtime markers it propagates. We do NOT spread os.environ:
  1371	            # the only Node/Remotion additions are the safe-base PATH/HOME/TMPDIR
  1372	            # that npx + the headless renderer need, and any caller-provided
  1373	            # composition source override declared as a build-tool variable.
  1374	            remotion_env_additions: dict[str, str] = {}
  1375	            composition_src = (
  1376	                project_dir / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
  1377	            )
  1378	            if composition_src.is_dir():
  1379	                remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
  1380	            result = subprocess.run(
  1381	                [
  1382	                    "npx",
  1383	                    "remotion",
  1384	                    "render",
  1385	                    composition_id,
  1386	                    "--props",
  1387	                    str(props_path),
  1388	                    "--output",
  1389	                    str(staged_video),
  1390	                    "--allow-html-in-canvas",
  1391	                ],
  1392	                cwd=str(project_dir),
  1393	                env=build_child_subprocess_env(explicit_env=remotion_env_additions),
  1394	                capture_output=True,
  1395	                check=False,
  1396	                text=True,
  1397	            )
  1398	            if result.returncode != 0:
  1399	                stderr_tail = _stderr_tail(result.stderr)
  1400	                message = f"Remotion render failed with exit code {result.returncode}"
  1401	                if stderr_tail:
  1402	                    message = f"{message}\n{stderr_tail}"
  1403	                raise RuntimeError(message)
  1404	            provenance = _render_provenance_payload(
  1405	                out_path,
  1406	                engine="remotion",
  1407	                timeline_path=timeline_path,
  1408	                assets_path=assets_path,
  1409	                project_dir=project_dir,
  1410	                composition_id=composition_id,
  1411	                theme_path=theme_path,
  1412	                active_theme=theme_for_props,
  1413	                registry_state=registry_state,
  1414	                stage_summary=stage_summary,
  1415	            )
  1416	            output = publish_render_result(
  1417	                staged_video,
  1418	                provenance,
  1419	                out_path=out_path,
  1420	                sidecar_path=_render_provenance_sidecar_path(out_path),
  1421	                previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
  1422	            )
  1423	        finally:
  1424	            props_path.unlink(missing_ok=True)
  1425	            shutil.rmtree(staged_public_root, ignore_errors=True)
  1426	    audit = AuditContext.from_env()
  1427	    if audit is not None:
  1428	        timeline_id = audit.register_asset(kind="timeline", path=timeline_path, label="Render timeline", stage="render_remotion")
  1429	        assets_id = audit.register_asset(kind="assets_registry", path=assets_path, label="Render asset registry", stage="render_remotion")
  1430	        render_id = audit.register_asset(
  1431	            kind="render",
  1432	            path=output,
  1433	            label="Rendered video",
  1434	            parents=[timeline_id, assets_id],
  1435	            stage="render_remotion",
  1436	            metadata={"composition": composition_id},
  1437	        )
  1438	        audit.register_node(
  1439	            stage="render_remotion",
  1440	            label="Render Remotion timeline",
  1441	            parents=[timeline_id, assets_id],
  1442	            outputs=[render_id],
  1443	            metadata={"composition": composition_id, "project_dir": str(project_dir)},
  1444	        )
  1445	    return output
  1446	
  1447	
  1448	def render(
  1449	    timeline_path: Path,
  1450	    assets_path: Path,
  1451	    out_path: Path,
  1452	    *,
  1453	    engine: str = "remotion",
  1454	    project_dir: Path | None = None,
  1455	    composition_id: str = "TimelineComposition",
  1456	    theme_path: Path | None = None,
  1457	    min_free_gb: float | None = None,
  1458	    keep_previous_renders: bool = False,
  1459	) -> Path:
  1460	    """Render privately and publish one locked video-plus-sidecar pair."""
  1461	
  1462	    out_path = Path(out_path)
  1463	    previous_outputs = (
  1464	        ()
  1465	        if keep_previous_renders
  1466	        else _previous_render_outputs_for_timeline(out_path, timeline_path)
  1467	    )
  1468	    publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
  1469	    try:
  1470	        return _render_with_publication_context(
  1471	            timeline_path,
  1472	            assets_path,
  1473	            out_path,
  1474	            engine=engine,
  1475	            project_dir=project_dir,
  1476	            composition_id=composition_id,
  1477	            theme_path=theme_path,
  1478	            min_free_gb=min_free_gb,
  1479	        )
  1480	    finally:
  1481	        _PUBLICATION_PREVIOUS_OUTPUTS.reset(publication_token)
  1482	
  1483	
  1484	def main(argv: Sequence[str] | None = None) -> int:
  1485	    parser = argparse.ArgumentParser()
  1486	    parser.add_argument("--timeline", type=Path, required=True)
  1487	    parser.add_argument("--assets", type=Path)
  1488	    parser.add_argument("--out", type=Path, required=True)
  1489	    parser.add_argument("--engine", choices=("remotion", "ffmpeg", "hybrid"), default="remotion")
  1490	    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
  1491	    parser.add_argument("--composition", default="TimelineComposition")
  1492	    parser.add_argument("--min-free-gb", type=float, default=None, help="Abort before rendering unless this much free disk is available near --out.")
  1493	    parser.add_argument(
  1494	        "--keep-previous-renders",
  1495	        nargs="?",
  1496	        const=True,
  1497	        default=False,
  1498	        type=_parse_bool_arg,
  1499	        help="Preserve previous sibling hype.mp4 outputs for the same timeline.",
  1500	    )
  1501	    parser.add_argument(
  1502	        "--theme",
  1503	        type=Path,
  1504	        default=REPO_ROOT / "themes" / "banodoco-default" / "theme.json",
  1505	    )

exec
/bin/zsh -lc "rg -n \"symlink|system redirect|private/tmp|private/var|previous_outputs|read_committed\" tests/core/rendering/test_publication.py tests/packs/rendering -g '*.py' | head -300 && nl -ba tests/core/rendering/test_publication.py | sed -n '1,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_publication.py:17:    read_committed_provenance,
tests/core/rendering/test_publication.py:53:        previous_outputs=(),
tests/core/rendering/test_publication.py:62:    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
tests/core/rendering/test_publication.py:104:                previous_outputs=(),
tests/core/rendering/test_publication.py:125:    payload = read_committed_provenance(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:136:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:147:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:157:        previous_outputs=(),
tests/core/rendering/test_publication.py:197:        previous_outputs=[
tests/core/rendering/test_publication.py:245:            previous_outputs=(),
tests/core/rendering/test_publication.py:273:            previous_outputs=(),
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
/bin/zsh -lc "nl -ba astrid/core/rendering/publication.py | sed -n '80,155p;150,215p;228,380p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
    91	def _contains_symlink_component(path: str | Path) -> bool:
    92	    """True if a non-system path component is a symbolic link.
    93	
    94	    macOS resolves ``/tmp`` -> ``/private/tmp`` and ``/var`` ->
    95	    ``/private/var``; those system redirects are not containment escapes.
    96	    Any other symlink component (e.g. a symlinked run directory) is treated
    97	    as an escape and rejected.
    98	    """
    99	    current = Path(path).expanduser()
   100	    parts = list(current.parts)
   101	    for index in range(len(parts), 0, -1):
   102	        candidate = Path(*parts[:index])
   103	        try:
   104	            if not candidate.is_symlink():
   105	                continue
   106	        except OSError:
   107	            return True
   108	        try:
   109	            resolved = candidate.resolve(strict=False)
   110	        except (OSError, RuntimeError):
   111	            return True
   112	        # System redirects: /tmp, /var, /etc, /private/* -> /private/*
   113	        if str(resolved).startswith("/private/"):
   114	            continue
   115	        if candidate.name in ("tmp", "var", "etc", "home", "usr") and str(resolved).startswith("/"):
   116	            continue
   117	        return True
   118	    return False
   119	
   120	
   121	def _invalid_video(video_path: Path, *, reason: str, message: str) -> None:
   122	    raise_invalid_artifact_error(
   123	        backend=_BACKEND,
   124	        message=message,
   125	        recovery_command=_RECOVERY,
   126	        details={"reason": reason, "path": str(video_path)},
   127	    )
   128	
   129	
   130	def _validate_source_video(video_path: Path) -> None:
   131	    try:
   132	        exists = video_path.is_file()
   133	    except OSError:
   134	        exists = False
   135	    if not exists:
   136	        _invalid_video(
   137	            video_path,
   138	            reason="missing_artifact",
   139	            message=f"rendered video does not exist: {video_path}",
   140	        )
   141	    try:
   142	        size = video_path.stat().st_size
   143	    except OSError:
   144	        _invalid_video(
   145	            video_path,
   146	            reason="missing_artifact",
   147	            message=f"rendered video cannot be read: {video_path}",
   148	        )
   149	    if size <= 0:
   150	        _invalid_video(
   150	        _invalid_video(
   151	            video_path,
   151	            video_path,
   152	            reason="empty_artifact",
   152	            reason="empty_artifact",
   153	            message=f"rendered video is empty: {video_path}",
   153	            message=f"rendered video is empty: {video_path}",
   154	        )
   154	        )
   155	
   155	
   156	
   157	def read_committed_provenance(
   158	    video_path: str | Path,
   159	    *,
   160	    sidecar_path: str | Path | None = None,
   161	) -> dict[str, Any] | None:
   162	    """Return provenance only when *video_path* and its marker form a valid pair.
   163	
   164	    This check intentionally fails closed for missing, malformed, empty, or
   165	    hash-mismatched pairs.  Callers can then re-render or leave the orphan for
   166	    conservative recovery without mistaking it for a successful publication.
   167	    """
   168	
   169	    video = _resolved(video_path)
   170	    sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
   171	    try:
   172	        video_unresolved = Path(video_path).expanduser()
   173	        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
   174	        if (
   175	            _contains_symlink_component(video_unresolved)
   176	            or _contains_symlink_component(sidecar_unresolved)
   177	        ):
   178	            return None
   179	        if video.is_symlink() or sidecar.is_symlink():
   180	            return None
   181	        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
   182	            return None
   183	        payload = json.loads(sidecar.read_text(encoding="utf-8"))
   184	    except (OSError, ValueError, TypeError, json.JSONDecodeError):
   185	        return None
   186	    if not isinstance(payload, dict):
   187	        return None
   188	    recorded_output = payload.get("output")
   189	    if not isinstance(recorded_output, str):
   190	        return None
   191	    try:
   192	        recorded_output_path = _resolved(recorded_output)
   193	    except (OSError, RuntimeError, ValueError):
   194	        return None
   195	    if recorded_output_path != video:
   196	        return None
   197	    recorded_sha256 = payload.get("sha256")
   198	    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
   199	        return None
   200	    try:
   201	        if sha256_file(video) != recorded_sha256:
   202	            return None
   203	    except OSError:
   204	        return None
   205	    return payload
   206	
   207	
   208	def is_render_result_committed(
   209	    video_path: str | Path,
   210	    *,
   211	    sidecar_path: str | Path | None = None,
   212	) -> bool:
   213	    """Return whether the video-plus-sidecar pair is committed."""
   214	
   215	    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
   228	        return video, _resolved(candidate[1])
   229	    if isinstance(candidate, (str, os.PathLike)):
   230	        video = _resolved(candidate)
   231	        return video, _resolved(_default_sidecar_path(video))
   232	    return None
   233	
   234	
   235	def _delete_previous_outputs(
   236	    previous_outputs: Iterable[object],
   237	    *,
   238	    live_output: Path,
   239	    timeline: object,
   240	) -> None:
   241	    if not isinstance(timeline, str):
   242	        return
   243	    seen: set[Path] = set()
   244	    for candidate in previous_outputs:
   245	        try:
   246	            pair = _previous_pair(candidate)
   247	        except (OSError, RuntimeError, TypeError, ValueError):
   248	            continue
   249	        if pair is None:
   250	            continue
   251	        video, sidecar = pair
   252	        # Never delete through a symlink: neither the raw video nor the raw
   253	        # sidecar path may be a link (the resolved pair may point elsewhere).
   254	        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
   255	        raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
   256	        try:
   257	            raw_path = Path(raw_candidate).expanduser()
   258	            if _contains_symlink_component(raw_path):
   259	                continue
   260	        except (OSError, TypeError):
   261	            continue
   262	        try:
   263	            # For bare paths the default sidecar is derived from the raw
   264	            # video path; it must be checked unresolved like an explicit one.
   265	            raw_sidecar = (
   266	                Path(raw_sidecar_candidate).expanduser()
   267	                if raw_sidecar_candidate is not None
   268	                else _default_sidecar_path(raw_path)
   269	            )
   270	            if _contains_symlink_component(raw_sidecar):
   271	                continue
   272	        except (OSError, TypeError):
   273	            continue
   274	        if video == live_output or video in seen:
   275	            continue
   276	        seen.add(video)
   277	
   278	        # Never wait while holding the live output lock.  Two concurrent
   279	        # publications for sibling outputs can otherwise deadlock while each
   280	        # tries to clean the other, and a locked candidate is by definition a
   281	        # live render that cleanup must preserve.
   282	        candidate_lock = _lock_for(video)
   283	        try:
   284	            candidate_lock.acquire(timeout=0)
   285	        except (Timeout, OSError):
   286	            continue
   287	        try:
   288	            provenance = read_committed_provenance(video, sidecar_path=sidecar)
   289	            if provenance is None or provenance.get("timeline") != timeline:
   290	                continue
   291	            try:
   292	                # The marker disappears first.  A crash or failure between
   293	                # these unlinks leaves an orphan, never a false committed pair.
   294	                sidecar.unlink()
   295	            except (FileNotFoundError, OSError):
   296	                continue
   297	            try:
   298	                video.unlink()
   299	            except (FileNotFoundError, OSError):
   300	                pass
   301	        finally:
   302	            candidate_lock.release()
   303	
   304	
   305	def publish_render_result(
   306	    video_path: str | Path,
   307	    provenance_payload: Mapping[str, Any],
   308	    *,
   309	    out_path: str | Path,
   310	    sidecar_path: str | Path,
   311	    previous_outputs: Iterable[object] = (),
   312	) -> Path:
   313	    """Publish one video and atomically commit its hashed provenance marker.
   314	
   315	    The source video is validated before any destination mutation.  Under the
   316	    per-output lock an old marker is invalidated, the video is moved into
   317	    place with :func:`os.replace`, and the complete sidecar is written
   318	    atomically last.  A sidecar-write failure therefore leaves a detectable,
   319	    recoverable orphan video and is propagated to the caller.
   320	    """
   321	
   322	    if not isinstance(provenance_payload, Mapping):
   323	        raise TypeError("provenance_payload must be a mapping")
   324	
   325	    source = _resolved(video_path)
   326	    output = _resolved(out_path)
   327	    sidecar = _resolved(sidecar_path)
   328	    source_unresolved = Path(video_path).expanduser()
   329	    output_unresolved = Path(out_path).expanduser()
   330	    sidecar_unresolved = Path(sidecar_path).expanduser()
   331	    if (
   332	        _contains_symlink_component(source_unresolved)
   333	        or _contains_symlink_component(output_unresolved)
   334	        or _contains_symlink_component(sidecar_unresolved)
   335	    ):
   336	        raise_invalid_artifact_error(
   337	            backend=_BACKEND,
   338	            message="publication paths must not be symbolic links (or contain symlinked directories)",
   339	            recovery_command=_RECOVERY,
   340	        )
   341	    _validate_source_video(source)
   342	
   343	    output.parent.mkdir(parents=True, exist_ok=True)
   344	    sidecar.parent.mkdir(parents=True, exist_ok=True)
   345	    with _lock_for(output):
   346	        # Validate again after waiting for the lock so a moved or truncated
   347	        # staging artifact can never be reported as successfully published.
   348	        _validate_source_video(source)
   349	
   350	        # Invalidate the previous marker BEFORE the first destination
   351	        # mutation: a crash can then leave an orphan video (recoverable) but
   352	        # can never leave a stale marker claiming the new bytes are committed.
   353	        sidecar.unlink(missing_ok=True)
   354	        os.replace(source, output)
   355	        digest = sha256_file(output)
   356	        committed_payload = dict(provenance_payload)
   357	        committed_payload["output"] = str(output)
   358	        committed_payload["sha256"] = digest
   359	        write_json_atomic(sidecar, committed_payload)
   360	
   361	        # Cleanup happens only after the new pair is committed and while its
   362	        # lock remains held.  Candidate locks are non-blocking (see above).
   363	        _delete_previous_outputs(
   364	            previous_outputs,
   365	            live_output=output,
   366	            timeline=committed_payload.get("timeline"),
   367	        )
   368	
   369	        # Do not report success unless the bytes and marker we just wrote are
   370	        # still a complete pair under the same lock.
   371	        if read_committed_provenance(output, sidecar_path=sidecar) is None:
   372	            _invalid_video(
   373	                output,
   374	                reason="uncommitted_artifact",
   375	                message=f"published video has no valid provenance commit marker: {output}",
   376	            )
   377	    return output
   378	
   379	
   380	__all__ = [

codex
Two claimed closures already show fail-closed gaps in static review. I’m still checking the media atom/probe behavior and route-level path flow so the issue list is complete rather than stopping at the first failure.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,runpy,subprocess; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); data=m[\"_build_mp4\"](2); p=subprocess.run([\"ffprobe\",\"-v\",\"quiet\",\"-print_format\",\"json\",\"-show_streams\",\"-show_format\",\"pipe:0\"],input=data,capture_output=True); print(\"returncode\",p.returncode,\"size\",len(data),\"stderr\",p.stderr.decode(errors=\"replace\")[:500]); payload=json.loads(p.stdout) if p.returncode==0 else {}; [print(s.get(\"codec_type\"),{k:s.get(k) for k in (\"codec_name\",\"profile\",\"level\",\"pix_fmt\",\"width\",\"height\",\"avg_frame_rate\",\"time_base\",\"sample_rate\",\"channels\",\"channel_layout\")}) for s in payload.get(\"streams\",[])]; print(payload.get(\"format\",{}).get(\"format_name\"))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 134ms:
returncode 0 size 29360 stderr 
video {'codec_name': 'h264', 'profile': 'Constrained Baseline', 'level': 40, 'pix_fmt': 'yuv420p', 'width': 1920, 'height': 1080, 'avg_frame_rate': '24/1', 'time_base': '1/12288', 'sample_rate': None, 'channels': None, 'channel_layout': None}
audio {'codec_name': 'pcm_s16le', 'profile': None, 'level': None, 'pix_fmt': None, 'width': None, 'height': None, 'avg_frame_rate': '0/0', 'time_base': '1/48000', 'sample_rate': '48000', 'channels': 2, 'channel_layout': 'stereo'}
mov,mp4,m4a,3gp,3g2,mj2

exec
/bin/zsh -lc "rg -n \"MediaProbe\\(\" --glob '*.py' . | head -200" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
./tests/core/rendering/test_artifacts.py:42:    return MediaProbe(
./astrid/core/media.py:154:    probe = MediaProbe(_raw=data)
./astrid/core/media.py:244:        return MediaProbe()
./astrid/core/media.py:267:            return MediaProbe()
./astrid/core/media.py:274:        return MediaProbe()
./astrid/core/media.py:283:        return MediaProbe()
./tests/core/util/test_media.py:123:        probe = MediaProbe()
./tests/core/util/test_media.py:141:        probe = MediaProbe(
./tests/packs/builtin/generate_video/test_execution_validation.py:89:        lambda path: MediaProbe(
./tests/packs/test_generate_video_partial_manifest.py:114:            return_value=MediaProbe(),
./tests/packs/test_generate_video_partial_manifest.py:325:            return_value=MediaProbe(
./tests/packs/test_generate_video_partial_manifest.py:357:            return_value=MediaProbe(

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import copy,json,runpy,pathlib; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); base=json.load(open(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\")); got=[]; m[\"_support\"].__globals__[\"_write_json\"]=lambda p,x:got.append(x); checks={\"width\":1,\"height\":1,\"fps_rational\":[25,1],\"time_base\":[1,999],\"container\":\"mov\",\"video_codec\":\"hevc\",\"video_profile\":\"Main\",\"video_level\":\"4.1\",\"pixel_format\":\"yuv444p\",\"audio_codec\":\"aac\",\"audio_sample_rate\":44100,\"audio_channel_layout\":\"mono\"}; [(got.clear(), (lambda r,f,v:(r[\"profile\"].__setitem__(f,v),m[\"_support\"](r,pathlib.Path(\"unused\"))))(copy.deepcopy(base),f,v), print(f,got[-1][\"supported\"])) for f,v in checks.items()]; got.clear(); r=copy.deepcopy(base); [r[\"profile\"].__setitem__(f,None) for f in (\"audio_codec\",\"audio_sample_rate\",\"audio_channel_layout\")]; r[\"audio\"]=\"none\"; m[\"_support\"](r,pathlib.Path(\"unused\")); print(\"visual_only_audio_null\",got[-1][\"supported\"],got[-1][\"reasons\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 5ms:
width False
height False
fps_rational False
time_base False
container False
video_codec False
video_profile False
video_level False
pixel_format False
audio_codec False
audio_sample_rate False
audio_channel_layout False
visual_only_audio_null True []

exec
/bin/zsh -lc "ls -ld /tmp /var /etc /home /usr /private /private/tmp /private/var 2>&1 && PYTHONDONTWRITEBYTECODE=1 python -c 'from astrid.core.rendering.publication import _contains_symlink_component; from pathlib import Path; [print(p,Path(p).is_symlink(),Path(p).resolve(strict=False),_contains_symlink_component(p)) for p in (\"/tmp/review.mp4\",\"/var/tmp/review.mp4\",\"/etc/review\",\"/private/tmp/review.mp4\")]'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 85ms:
/tmp/review.mp4 False /private/tmp/review.mp4 False
/var/tmp/review.mp4 False /private/var/tmp/review.mp4 False
/etc/review False /private/etc/review False
/private/tmp/review.mp4 False /private/tmp/review.mp4 False

exec
/bin/zsh -lc 'find . /tmp -maxdepth 5 -type l -print 2>/dev/null | head -100' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
/tmp

collab: Wait
collab: Wait
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import copy,json,runpy,pathlib; from astrid.core.rendering.contracts import RenderRequest; base=json.load(open(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\")); r=copy.deepcopy(base); r[\"audio\"]=\"none\"; [r[\"profile\"].__setitem__(f,None) for f in (\"audio_codec\",\"audio_sample_rate\",\"audio_channel_layout\")]; RenderRequest.from_dict(r); m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); got=[]; m[\"_support\"].__globals__[\"_write_json\"]=lambda p,x:got.append(x); m[\"_validate_request\"](r); m[\"_support\"](r,pathlib.Path(\"unused\")); print(got[-1])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 132ms:
{'schema_version': 1, 'supported': True, 'reasons': [], 'features': {'media': True, 'audio_mode': 'rendered'}, 'alternatives': [], 'backend': 'raw_command.renderer', 'backend_version': '1.0.0'}

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import os,tempfile; from pathlib import Path; from astrid.core.rendering.publication import _contains_symlink_component; d=tempfile.mkdtemp(dir=\"/private/tmp\"); root=Path(d); outside=root/\"outside\"; outside.mkdir(); link=root/\"runs\"/\"tmp\"; link.parent.mkdir(); link.symlink_to(outside,target_is_directory=True); print(link,\"->\",link.resolve(),\"guard\",_contains_symlink_component(link/\"victim.mp4\")); priv=root/\"private-link\"; priv.symlink_to(Path(\"/private/tmp\"),target_is_directory=True); print(priv,\"->\",priv.resolve(),\"guard\",_contains_symlink_component(priv/\"victim.mp4\"))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 72ms:
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 385, in mkdtemp
    _os.mkdir(file, 0o700)
PermissionError: [Errno 1] Operation not permitted: '/private/tmp/tmp2h0nmqn5'

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from pathlib import Path; from unittest.mock import patch; from astrid.core.rendering.publication import _contains_symlink_component; fake=Path(\"/project/runs/tmp\"); orig=Path.is_symlink; res=Path.resolve; f=lambda self: self==fake; rr=lambda self,strict=False: Path(\"/outside\") if self==fake else res(self,strict=strict); p1=patch.object(Path,\"is_symlink\",f); p2=patch.object(Path,\"resolve\",rr); p1.start(); p2.start(); print(_contains_symlink_component(fake/\"victim.mp4\")); p2.stop(); p1.stop()'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 71ms:
False

collab: Wait
collab: Wait
exec
/bin/zsh -lc 'rg -n "publication|symlink|atomic|cleanup|support|profile|transport|process group" .oracle/tasklist.md .oracle/plan.md | head -260' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/tasklist.md:21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
.oracle/tasklist.md:28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
.oracle/tasklist.md:32:- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
.oracle/tasklist.md:33:- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
.oracle/tasklist.md:37:- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
.oracle/tasklist.md:38:- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
.oracle/tasklist.md:39:- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
.oracle/tasklist.md:43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
.oracle/tasklist.md:46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
.oracle/tasklist.md:47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
.oracle/tasklist.md:48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
.oracle/tasklist.md:52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
.oracle/tasklist.md:57:- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
.oracle/tasklist.md:59:- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
.oracle/tasklist.md:60:- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
.oracle/tasklist.md:61:- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
.oracle/tasklist.md:68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
.oracle/tasklist.md:69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
.oracle/tasklist.md:70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
.oracle/tasklist.md:71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
.oracle/tasklist.md:79:- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
.oracle/tasklist.md:83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
.oracle/tasklist.md:84:- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
.oracle/tasklist.md:89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
.oracle/tasklist.md:91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
.oracle/tasklist.md:92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
.oracle/tasklist.md:93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
.oracle/tasklist.md:115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
.oracle/tasklist.md:129:- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
.oracle/tasklist.md:130:- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
.oracle/tasklist.md:137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
.oracle/tasklist.md:138:- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
.oracle/tasklist.md:139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
.oracle/tasklist.md:153:- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
.oracle/tasklist.md:155:- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
.oracle/tasklist.md:163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
.oracle/tasklist.md:166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
.oracle/plan.md:24:   <command...> render|support|plan|finalize \
.oracle/plan.md:37:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/plan.md:39:10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.
.oracle/plan.md:82:    - video and audio profiles;
.oracle/plan.md:87:  - Add versioned JSON Schemas for request, result, support, plan, finalization, and the three manifest types.
.oracle/plan.md:101:  - Use existing atomic JSON and SHA-256 helpers.
.oracle/plan.md:114:  - For installed candidates, verify the active symlink’s revision and installation trust audit; deny execution for missing, corrupt, or mismatched records. Keep such candidates inspectable for diagnosis. Do not expose staging or inactive revisions through normal discovery.
.oracle/plan.md:121:- [ ] **M1-03 — Implement command transport and the raw fixture pack**
.oracle/plan.md:123:  - Implement synchronous backend transport with:
.oracle/plan.md:135:  - On interruption, terminate and reap the backend process group, clean owned resources, then re-raise interruption.
.oracle/plan.md:140:  - Gate: render/support success, unsupported response, malformed JSON, missing result/output, nonzero exit, timeout, SIGINT cleanup, untrusted env discovery, trusted install, and static no-import inspection all pass.
.oracle/plan.md:145:  - Preserve cache layout, URL keying, resume/drift behavior, metadata, locking, and `EphemeralSession` cleanup semantics.
.oracle/plan.md:147:  - Serve only invocation-staged assets from `127.0.0.1`; bind the server directly to port `0`, retain Range support, start inside the managed context, and always shut down, close, and join it.
.oracle/plan.md:149:  - Add one canonical resolved render profile using the same merged theme/timeline canvas consumed by Remotion. Planner, backend requests, and finalizer all receive that profile.
.oracle/plan.md:151:  - Add renderer-local artifact enforcement for existence, non-empty output, workspace containment, symlinks, hashes, duration, video profile, and audio ownership.
.oracle/plan.md:153:  - Add a locked publication helper in which the sidecar is the final commit marker.
.oracle/plan.md:154:  - Gate: local/cached/remote assets, Range requests, expired URLs, restricted serving, server-start failure, cleanup, invalid artifacts, visual-only modes, attachments, and crash-orphan recovery pass.
.oracle/plan.md:164:    - cover the three package registries, shim families, active-theme symlink/text pointer, and registry state;
.oracle/plan.md:166:    - write registry state atomically;
.oracle/plan.md:171:  - Gate: registry invalidation, atomic state, theme/profile parity, effect assets, environment redaction, concurrent differing-theme renders, render-versus-`gen-types` contention, success/failure cleanup, output validation, Remotion typecheck, and an available fixture render pass.
.oracle/plan.md:179:    - unsupported or unknown track/clip kinds;
.oracle/plan.md:183:    - unsupported positioning, crop, effect, transition, or non-default opacity semantics;
.oracle/plan.md:193:  - Let an explicit planner route unsupported windows elsewhere; strict `rendering.ffmpeg` must not silently alter them.
.oracle/plan.md:194:  - Express media optimization and audio-reactive specialization as request-sensitive support evidence, not facade branches.
.oracle/plan.md:195:  - Preserve compatible stream-copy behavior and supported sequential audio mixing.
.oracle/plan.md:198:  - Gate: support diagnostics, command graphs, stream-copy, gaps/overlaps, track mute/volume, clip volume zero, fades, source bounds, missing streams/binaries, audio-reactive marker frames/hashes, cleanup, output validation, and provenance pass with a real FFmpeg render.
.oracle/plan.md:205:  - Stream-copy only when the complete profile is compatible. Otherwise normalize dimensions, FPS/time base, codecs, pixel format, sample rate, channel layout, and audio presence.
.oracle/plan.md:208:  - Gate: one-segment pass-through, compatible and incompatible multi-segment plans, 24/25/30 and rational FPS, missing audio/video, codec/time-base mismatch, duration mismatch, normalization provenance, and cleanup pass.
.oracle/plan.md:218:    6. obtain static/request-sensitive support;
.oracle/plan.md:239:    - support decision and alternatives;
.oracle/plan.md:240:    - input and artifact hashes/profiles;
.oracle/plan.md:252:  - Make previous-output cleanup lock-aware and conservative around corrupt/orphaned pairs; never delete unrelated output solely because a sidecar is unreadable.
.oracle/plan.md:253:  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.
.oracle/plan.md:258:  - Resolve canvas/FPS once from the canonical merged theme/timeline profile.
.oracle/plan.md:264:    - unsupported non-media clips;
.oracle/plan.md:266:    - controls rejected by the selected renderer’s support report.
.oracle/plan.md:267:  - Permit FFmpeg track mute/volume after M1-06 proves exact support; fades continue to route away from FFmpeg.
.oracle/plan.md:268:  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
.oracle/plan.md:269:  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
.oracle/plan.md:273:  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.
.oracle/plan.md:308:    - support decisions;
.oracle/plan.md:310:    - resolved canvas/profile;
.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
.oracle/plan.md:349:  - Provide `renderer_main()` plus functional `render(request, context)` and optional `support(request, context)` author hooks.
.oracle/plan.md:361:  - Provide allocated output/work paths, descriptor-based local path/URL access, declared-permission checks, sanitized subprocess execution, redacted logging/progress, read-only interruption state, probing, hashing, completion, attachments, and cleanup.
.oracle/plan.md:366:    - request-sensitive support;
.oracle/plan.md:405:  - Gate: help, dispatch, session independence, JSON keys, error/recovery behavior, conflicts, trust denial, installed selection, unsupported support, interruption, and smoke output pass.
.oracle/plan.md:410:  - Bundle the resolved request, localized inputs, backend configuration, renderer/manifest identity and digest, support report, logs, result/partial result, hashes, and exact replay command.
.oracle/plan.md:413:  - Delete successful disposable workdirs unless `--keep-workdir` is requested. Add no TTL daemon or background cleanup system.
.oracle/plan.md:419:  - Keep support probing and custom finalizers in separate advanced sections.
.oracle/plan.md:421:  - Document trust, disclosure-only permissions, selection, aliases/overrides, backend configuration, assets, output/audio/attachments, cleanup, diagnostics, replay/redaction, and legacy selectors.
.oracle/plan.md:440:- Made FFmpeg audio semantics exact: track and clip gains multiply, track mute wins, clip mute is volume zero, and fades remain unsupported.
.oracle/plan.md:444:- Retained the earlier scope cuts: no generic component system, OS sandbox, global missing-output enforcement, universal CLI envelope, committed MP4s, or replay-cleanup daemon.
.oracle/plan.md:449:- A valid active symlink with a corrupt install record must remain inspectable while being excluded from execution.
.oracle/plan.md:455:- Video plus sidecar cannot be atomically renamed as one filesystem object; the sidecar remains the commit marker and orphan recovery is required.

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from astrid.core.rendering.artifacts import _compare_declared_to_expected,_validate_audio; from astrid.core.rendering.contracts import RenderProfile,AudioOwnership; from astrid.core.media import MediaProbe; kw=dict(width=1,height=1,fps_rational=(1,1),time_base=(1,1),video_codec=\"h264\",pixel_format=\"yuv420p\",container=\"mp4\",audio_codec=\"aac\",audio_sample_rate=48000,duration_tolerance=1); declared=RenderProfile(**kw,audio_channel_layout=\"Stereo\"); expected=RenderProfile(**kw,audio_channel_layout=\"stereo\"); _compare_declared_to_expected(declared,expected,AudioOwnership.RENDERED); p=MediaProbe(width=1,height=1,fps_rational=(1,1),time_base=(1,1),video_codec=\"h264\",pixel_format=\"yuv420p\",container=\"mp4\",audio_codec=\"aac\",audio_sample_rate=48000,audio_channel_layout=None,audio_channels=2,video_stream_present=True,audio_stream_present=True); print(\"declared comparison passed\"); _validate_audio(p,ownership=AudioOwnership.RENDERED,declared=declared,expected=expected)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 97ms:
declared comparison passed
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py", line 531, in _validate_audio
    _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=True)
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py", line 456, in _compare_probe_to_profile
    _invalid(
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py", line 43, in _invalid
    raise_invalid_artifact_error(
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/errors.py", line 219, in raise_invalid_artifact_error
    raise_structured_failure(
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/errors.py", line 121, in raise_structured_failure
    raise_renderer_error(
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/errors.py", line 110, in raise_renderer_error
    raise exception_from_error(error)
astrid.core.rendering.errors.RendererInvalidArtifactError: probed audio channel layout/count does not match the declared profile

codex
- The post-SIGKILL drain still omits `OSError`; deadline exits also do not guarantee reaping the direct child. [transport.py:497](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:497)

- `_support()` skips missing/`None` fixed fields. A valid `audio="none"` profile returns `supported: true`, although rendering always emits PCM stereo audio. [backend.py:443](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:443)

- The channels-only fallback bypasses normal layout normalization: `"Stereo"` matches `"stereo"` ordinarily but fails with `audio_channels=2`. [artifacts.py:450](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:450)

- The symlink exemption is overbroad: any symlink resolving beneath `/private/`, or named `tmp`, `var`, `etc`, `home`, or `usr`, is accepted anywhere. Non-system symlinks can therefore bypass publish/read/cleanup guards. [publication.py:109](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:109)

- `read_committed_provenance()` resolves paths before its fail-closed guard, so a symlink loop raises `RuntimeError` instead of returning `None`. [publication.py:169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:169)

- `audio_channels` was inserted before existing `MediaProbe` fields, shifting positional arguments despite the documented positional-compatibility guarantee. [media.py:43](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py:43)
tokens used
298,950
- The post-SIGKILL drain still omits `OSError`; deadline exits also do not guarantee reaping the direct child. [transport.py:497](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:497)

- `_support()` skips missing/`None` fixed fields. A valid `audio="none"` profile returns `supported: true`, although rendering always emits PCM stereo audio. [backend.py:443](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:443)

- The channels-only fallback bypasses normal layout normalization: `"Stereo"` matches `"stereo"` ordinarily but fails with `audio_channels=2`. [artifacts.py:450](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:450)

- The symlink exemption is overbroad: any symlink resolving beneath `/private/`, or named `tmp`, `var`, `etc`, `home`, or `usr`, is accepted anywhere. Non-system symlinks can therefore bypass publish/read/cleanup guards. [publication.py:109](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:109)

- `read_committed_provenance()` resolves paths before its fail-closed guard, so a symlink loop raises `RuntimeError` instead of returning `None`. [publication.py:169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:169)

- `audio_channels` was inserted before existing `MediaProbe` fields, shifting positional arguments despite the documented positional-compatibility guarantee. [media.py:43](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py:43)
