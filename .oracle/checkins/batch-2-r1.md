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

codex
The context-mining skill is now causing a concrete action: I’m delegating three bounded, read-only audit slices so their search trails stay out of the main review context. Each reviewer must return a terse conclusion with file/line evidence; I’ll still inspect the complete incremental diff and run the critical checks myself.
2026-08-12T05:55:57.782899Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:55:57.782930Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:55:57.782935Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:56:04.322158Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:56:04.322222Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:56:04.322232Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:56:10.918732Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:56:10.918764Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T05:56:10.918769Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
codex
Because the checkpoint concerns Astrid’s own transport/artifact protocol, I’m also applying the repository’s Astrid skill contract before interpreting behavior. This is a read-only review; I won’t run any Astrid action that mutates project state.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md astrid/packs/_core/skill/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && rg --files -g 'AGENTS.md' -g '"'!**/.git/**'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     772 astrid/packs/_core/skill/SKILL.md
    1544 total
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
AGENTS.md
examples/packs/media/AGENTS.md
examples/packs/file_summarizer/AGENTS.md
examples/packs/text_review/AGENTS.md
examples/packs/minimal/AGENTS.md
examples/packs/text_digest/AGENTS.md

exec
/bin/zsh -lc "sed -n '261,560p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '561,860p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc 'git status --short && git rev-parse --short HEAD && git rev-parse --verify 5231a233''^{commit} && git rev-parse --verify dedcc2c5''^{commit} && git diff --check dedcc2c5..5231a233 && git diff --stat dedcc2c5..5231a233 && wc -l /tmp/batch2-r1.diff && sed -n '"'1,260p' .oracle/checkins/batch-2.md && git diff --name-status dedcc2c5..5231a233" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-2-r1.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
5231a233
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
5231a233aa86fb32d238d697b3b1b7063b3c2eb0
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
dedcc2c534a181fb93d52a9a38d60c1cfddf0e9b
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2.md:361: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:362: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:364: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2235: trailing whitespace.
++     2	
.oracle/checkins/batch-2.md:2237: trailing whitespace.
++     4	
.oracle/checkins/batch-2.md:2239: trailing whitespace.
++     8	
.oracle/checkins/batch-2.md:2241: trailing whitespace.
++    11	
.oracle/checkins/batch-2.md:2243: trailing whitespace.
++    29	
.oracle/checkins/batch-2.md:2245: trailing whitespace.
++    30	
.oracle/checkins/batch-2.md:2247: trailing whitespace.
++    33	
.oracle/checkins/batch-2.md:2249: trailing whitespace.
++    34	
.oracle/checkins/batch-2.md:2251: trailing whitespace.
++    39	
.oracle/checkins/batch-2.md:2253: trailing whitespace.
++    41	
.oracle/checkins/batch-2.md:2255: trailing whitespace.
++    42	
.oracle/checkins/batch-2.md:2257: trailing whitespace.
++    54	
.oracle/checkins/batch-2.md:2259: trailing whitespace.
++    55	
.oracle/checkins/batch-2.md:2261: trailing whitespace.
++    82	
.oracle/checkins/batch-2.md:2263: trailing whitespace.
++    83	
.oracle/checkins/batch-2.md:2265: trailing whitespace.
++    86	
.oracle/checkins/batch-2.md:2267: trailing whitespace.
++    93	
.oracle/checkins/batch-2.md:2269: trailing whitespace.
++    94	
.oracle/checkins/batch-2.md:2271: trailing whitespace.
++   106	
.oracle/checkins/batch-2.md:2273: trailing whitespace.
++   107	
.oracle/checkins/batch-2.md:2275: trailing whitespace.
++   199	
.oracle/checkins/batch-2.md:2277: trailing whitespace.
++   200	
.oracle/checkins/batch-2.md:2279: trailing whitespace.
++   915	
.oracle/checkins/batch-2.md:2281: trailing whitespace.
++   916	
.oracle/checkins/batch-2.md:2283: trailing whitespace.
++    35	
.oracle/checkins/batch-2.md:2285: trailing whitespace.
++    40	
.oracle/checkins/batch-2.md:2287: trailing whitespace.
++    49	
.oracle/checkins/batch-2.md:2289: trailing whitespace.
++    61	
.oracle/checkins/batch-2.md:2291: trailing whitespace.
++    82	
.oracle/checkins/batch-2.md:2293: trailing whitespace.
++   102	
.oracle/checkins/batch-2.md:2295: trailing whitespace.
++   119	
.oracle/checkins/batch-2.md:2297: trailing whitespace.
++   132	
.oracle/checkins/batch-2.md:2299: trailing whitespace.
++   139	
.oracle/checkins/batch-2.md:2301: trailing whitespace.
++   140	
.oracle/checkins/batch-2.md:2303: trailing whitespace.
++   143	
.oracle/checkins/batch-2.md:2305: trailing whitespace.
++   167	
.oracle/checkins/batch-2.md:2307: trailing whitespace.
++   168	
.oracle/checkins/batch-2.md:2309: trailing whitespace.
++   516	
.oracle/checkins/batch-2.md:2311: trailing whitespace.
++   520	
.oracle/checkins/batch-2.md:2313: trailing whitespace.
++   539	
.oracle/checkins/batch-2.md:2315: trailing whitespace.
++   572	
.oracle/checkins/batch-2.md:2317: trailing whitespace.
++   573	
.oracle/checkins/batch-2.md:2319: trailing whitespace.
++   580	
.oracle/checkins/batch-2.md:2321: trailing whitespace.
++   585	
.oracle/checkins/batch-2.md:2323: trailing whitespace.
++   591	
.oracle/checkins/batch-2.md:2325: trailing whitespace.
++   592	
.oracle/checkins/batch-2.md:2327: trailing whitespace.
++   596	
.oracle/checkins/batch-2.md:2329: trailing whitespace.
++   601	
.oracle/checkins/batch-2.md:2331: trailing whitespace.
++   613	
.oracle/checkins/batch-2.md:2333: trailing whitespace.
++   618	
.oracle/checkins/batch-2.md:2335: trailing whitespace.
++   630	
.oracle/checkins/batch-2.md:2337: trailing whitespace.
++   642	
.oracle/checkins/batch-2.md:2339: trailing whitespace.
++   643	
.oracle/checkins/batch-2.md:2341: trailing whitespace.
++   664	
.oracle/checkins/batch-2.md:2343: trailing whitespace.
++   665	
.oracle/checkins/batch-2.md:2345: trailing whitespace.
++   669	
.oracle/checkins/batch-2.md:2347: trailing whitespace.
++   676	
.oracle/checkins/batch-2.md:2349: trailing whitespace.
++   699	
.oracle/checkins/batch-2.md:2351: trailing whitespace.
++   711	
.oracle/checkins/batch-2.md:2353: trailing whitespace.
++   200	
.oracle/checkins/batch-2.md:2355: trailing whitespace.
++   276	
.oracle/checkins/batch-2.md:2357: trailing whitespace.
++   277	
.oracle/checkins/batch-2.md:2359: trailing whitespace.
++   288	
.oracle/checkins/batch-2.md:2361: trailing whitespace.
++   289	
.oracle/checkins/batch-2.md:2363: trailing whitespace.
++   311	
.oracle/checkins/batch-2.md:2365: trailing whitespace.
++   312	
.oracle/checkins/batch-2.md:2367: trailing whitespace.
++   328	
.oracle/checkins/batch-2.md:2369: trailing whitespace.
++   335	
.oracle/checkins/batch-2.md:2371: trailing whitespace.
++   356	
.oracle/checkins/batch-2.md:2373: trailing whitespace.
++   383	
.oracle/checkins/batch-2.md:2375: trailing whitespace.
++   384	
.oracle/checkins/batch-2.md:2377: trailing whitespace.
++   387	
.oracle/checkins/batch-2.md:2379: trailing whitespace.
++   389	
.oracle/checkins/batch-2.md:2381: trailing whitespace.
++   390	
.oracle/checkins/batch-2.md:2383: trailing whitespace.
++   214	
.oracle/checkins/batch-2.md:2385: trailing whitespace.
++   215	
.oracle/checkins/batch-2.md:2387: trailing whitespace.
++   218	
.oracle/checkins/batch-2.md:2389: trailing whitespace.
++   224	
.oracle/checkins/batch-2.md:2391: trailing whitespace.
++   225	
.oracle/checkins/batch-2.md:2393: trailing whitespace.
++   234	
.oracle/checkins/batch-2.md:2395: trailing whitespace.
++   235	
.oracle/checkins/batch-2.md:2397: trailing whitespace.
++   240	
.oracle/checkins/batch-2.md:2399: trailing whitespace.
++   241	
.oracle/checkins/batch-2.md:2401: trailing whitespace.
++   250	
.oracle/checkins/batch-2.md:2403: trailing whitespace.
++   251	
.oracle/checkins/batch-2.md:2405: trailing whitespace.
++   257	
.oracle/checkins/batch-2.md:2407: trailing whitespace.
++   258	
.oracle/checkins/batch-2.md:2409: trailing whitespace.
++   271	
.oracle/checkins/batch-2.md:2411: trailing whitespace.
++   272	
.oracle/checkins/batch-2.md:2413: trailing whitespace.
++   277	
.oracle/checkins/batch-2.md:2415: trailing whitespace.
++   278	
.oracle/checkins/batch-2.md:2417: trailing whitespace.
++   285	
.oracle/checkins/batch-2.md:2419: trailing whitespace.
++   286	
.oracle/checkins/batch-2.md:2421: trailing whitespace.
++   293	
.oracle/checkins/batch-2.md:2423: trailing whitespace.
++   294	
.oracle/checkins/batch-2.md:2425: trailing whitespace.
++   303	
.oracle/checkins/batch-2.md:2427: trailing whitespace.
++   304	
.oracle/checkins/batch-2.md:2429: trailing whitespace.
++   311	
.oracle/checkins/batch-2.md:2431: trailing whitespace.
++   312	
.oracle/checkins/batch-2.md:2433: trailing whitespace.
++   321	
.oracle/checkins/batch-2.md:2435: trailing whitespace.
++   322	
.oracle/checkins/batch-2.md:2437: trailing whitespace.
++   339	
.oracle/checkins/batch-2.md:2439: trailing whitespace.
++   340	
.oracle/checkins/batch-2.md:2441: trailing whitespace.
++   352	
.oracle/checkins/batch-2.md:2443: trailing whitespace.
++   353	
.oracle/checkins/batch-2.md:2445: trailing whitespace.
++   356	
.oracle/checkins/batch-2.md:2447: trailing whitespace.
++   362	
.oracle/checkins/batch-2.md:2449: trailing whitespace.
++   363	
.oracle/checkins/batch-2.md:2451: trailing whitespace.
++   664	
.oracle/checkins/batch-2.md:2453: trailing whitespace.
++   665	
.oracle/checkins/batch-2.md:2455: trailing whitespace.
++   669	
.oracle/checkins/batch-2.md:2457: trailing whitespace.
++   676	
.oracle/checkins/batch-2.md:2459: trailing whitespace.
++   699	
.oracle/checkins/batch-2.md:2461: trailing whitespace.
++   711	
.oracle/checkins/batch-2.md:2463: trailing whitespace.
++   726	
.oracle/checkins/batch-2.md:2465: trailing whitespace.
++   747	
.oracle/checkins/batch-2.md:2467: trailing whitespace.
++   748	
.oracle/checkins/batch-2.md:2469: trailing whitespace.
++   755	
.oracle/checkins/batch-2.md:2471: trailing whitespace.
++   276	
.oracle/checkins/batch-2.md:2473: trailing whitespace.
++   277	
.oracle/checkins/batch-2.md:2475: trailing whitespace.
++   288	
.oracle/checkins/batch-2.md:2477: trailing whitespace.
++   289	
.oracle/checkins/batch-2.md:2479: trailing whitespace.
++   311	
.oracle/checkins/batch-2.md:2481: trailing whitespace.
++   312	
.oracle/checkins/batch-2.md:2483: trailing whitespace.
++   328	
.oracle/checkins/batch-2.md:2485: trailing whitespace.
++   335	
.oracle/checkins/batch-2.md:2487: trailing whitespace.
++   356	
.oracle/checkins/batch-2.md:2489: trailing whitespace.
++   383	
.oracle/checkins/batch-2.md:2491: trailing whitespace.
++   384	
.oracle/checkins/batch-2.md:2493: trailing whitespace.
++   387	
.oracle/checkins/batch-2.md:2495: trailing whitespace.
++   389	
.oracle/checkins/batch-2.md:2497: trailing whitespace.
++   390	
.oracle/checkins/batch-2.md:2499: trailing whitespace.
++   749	
.oracle/checkins/batch-2.md:2501: trailing whitespace.
++   750	
.oracle/checkins/batch-2.md:2503: trailing whitespace.
++   786	
.oracle/checkins/batch-2.md:2505: trailing whitespace.
++   787	
.oracle/checkins/batch-2.md:2507: trailing whitespace.
++   801	
.oracle/checkins/batch-2.md:2509: trailing whitespace.
++   802	
.oracle/checkins/batch-2.md:2511: trailing whitespace.
++   818	
.oracle/checkins/batch-2.md:2513: trailing whitespace.
++   819	
.oracle/checkins/batch-2.md:2515: trailing whitespace.
++   915	
.oracle/checkins/batch-2.md:2517: trailing whitespace.
++   916	
.oracle/checkins/batch-2.md:2519: trailing whitespace.
++  1072	
.oracle/checkins/batch-2.md:2521: trailing whitespace.
++  1073	
.oracle/checkins/batch-2.md:2523: trailing whitespace.
++  1082	
.oracle/checkins/batch-2.md:2525: trailing whitespace.
++  1083	
.oracle/checkins/batch-2.md:2527: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2529: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2531: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2533: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2535: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2537: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2539: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2541: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2543: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2545: trailing whitespace.
++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2547: trailing whitespace.
++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2549: trailing whitespace.
++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2551: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2553: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2555: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2557: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2559: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2561: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2563: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2565: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2567: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2569: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2571: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2573: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2575: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2577: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2579: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2581: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2583: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2585: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2587: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2589: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2591: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2593: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2595: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2597: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2599: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2601: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2603: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2605: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2607: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2609: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2611: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2613: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2615: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2617: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2619: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2621: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2623: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2625: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2627: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2629: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2631: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2633: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2635: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2637: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2639: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2641: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2643: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2645: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2647: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2649: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2651: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2653: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2655: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2657: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2659: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2661: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2663: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2665: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2667: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2669: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2671: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2673: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2675: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2677: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2679: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2681: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2683: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2685: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2687: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2689: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2691: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2693: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2695: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2697: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2699: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2701: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2703: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2705: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2707: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2709: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2711: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2713: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2715: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2717: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2719: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2721: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2723: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2725: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2727: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2729: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2731: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2733: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2735: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2737: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2739: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2741: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2743: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2745: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2747: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2749: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2751: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2753: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2755: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2757: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2759: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2761: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2763: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:2765: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:2767: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:2769: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:2771: trailing whitespace.
+++++++   730	
.oracle/checkins/batch-2.md:2773: trailing whitespace.
+++++++   731	
.oracle/checkins/batch-2.md:2775: trailing whitespace.
+++++++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-2.md:2777: trailing whitespace.
+++++++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-2.md:2779: trailing whitespace.
+++++++   453	
.oracle/checkins/batch-2.md:2781: trailing whitespace.
+++++++   461	
.oracle/checkins/batch-2.md:2783: trailing whitespace.
+++++++   463	
.oracle/checkins/batch-2.md:2785: trailing whitespace.
+++++++   465	
.oracle/checkins/batch-2.md:2787: trailing whitespace.
+++++++   470	
.oracle/checkins/batch-2.md:2789: trailing whitespace.
+++++++   492	
.oracle/checkins/batch-2.md:2791: trailing whitespace.
+++++++   520	
.oracle/checkins/batch-2.md:2793: trailing whitespace.
+++++++   539	
.oracle/checkins/batch-2.md:2795: trailing whitespace.
+++++++   540	
.oracle/checkins/batch-2.md:2797: trailing whitespace.
+++++++   550	
.oracle/checkins/batch-2.md:2799: trailing whitespace.
+++++++   551	
.oracle/checkins/batch-2.md:2801: trailing whitespace.
+++++++   609	
.oracle/checkins/batch-2.md:2803: trailing whitespace.
+++++++   613	
.oracle/checkins/batch-2.md:2805: trailing whitespace.
+++++++   614	
.oracle/checkins/batch-2.md:2807: trailing whitespace.
+++++++   627	
.oracle/checkins/batch-2.md:2809: trailing whitespace.
+++++++   628	
.oracle/checkins/batch-2.md:2811: trailing whitespace.
+++++++   631	
.oracle/checkins/batch-2.md:2813: trailing whitespace.
+++++++   640	
.oracle/checkins/batch-2.md:2815: trailing whitespace.
+++++++   641	
.oracle/checkins/batch-2.md:2817: trailing whitespace.
+++++++   647	
.oracle/checkins/batch-2.md:2819: trailing whitespace.
+++++++   648	
.oracle/checkins/batch-2.md:2821: trailing whitespace.
+++++++   679	
.oracle/checkins/batch-2.md:2823: trailing whitespace.
+++++++   689	
.oracle/checkins/batch-2.md:2825: trailing whitespace.
+++++++   721	
.oracle/checkins/batch-2.md:2827: trailing whitespace.
+++++++   722	
.oracle/checkins/batch-2.md:2829: trailing whitespace.
+++++++   740	
.oracle/checkins/batch-2.md:2831: trailing whitespace.
+++++++   741	
.oracle/checkins/batch-2.md:2833: trailing whitespace.
+++++++   777	
.oracle/checkins/batch-2.md:2835: trailing whitespace.
+++++++   778	
.oracle/checkins/batch-2.md:2837: trailing whitespace.
+++++++   792	
.oracle/checkins/batch-2.md:2839: trailing whitespace.
+++++++   793	
.oracle/checkins/batch-2.md:2841: trailing whitespace.
+++++++   809	
.oracle/checkins/batch-2.md:2843: trailing whitespace.
+++++++   810	
.oracle/checkins/batch-2.md:2845: trailing whitespace.
+++++++   904	
.oracle/checkins/batch-2.md:2847: trailing whitespace.
+++++++   905	
.oracle/checkins/batch-2.md:2849: trailing whitespace.
+++++++   965	
.oracle/checkins/batch-2.md:2851: trailing whitespace.
+++++++   966	
.oracle/checkins/batch-2.md:2853: trailing whitespace.
+++++++   975	
.oracle/checkins/batch-2.md:2855: trailing whitespace.
+++++++   976	
.oracle/checkins/batch-2.md:2857: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2.md:2859: trailing whitespace.
+++++++     4	
.oracle/checkins/batch-2.md:2861: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2.md:2863: trailing whitespace.
+++++++    11	
.oracle/checkins/batch-2.md:2865: trailing whitespace.
+++++++    28	
.oracle/checkins/batch-2.md:2867: trailing whitespace.
+++++++    29	
.oracle/checkins/batch-2.md:2869: trailing whitespace.
+++++++    32	
.oracle/checkins/batch-2.md:2871: trailing whitespace.
+++++++    33	
.oracle/checkins/batch-2.md:2873: trailing whitespace.
+++++++    38	
.oracle/checkins/batch-2.md:2875: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2.md:2877: trailing whitespace.
+++++++    41	
.oracle/checkins/batch-2.md:2879: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2.md:2881: trailing whitespace.
+++++++    54	
.oracle/checkins/batch-2.md:2883: trailing whitespace.
+++++++    81	
.oracle/checkins/batch-2.md:2885: trailing whitespace.
+++++++    82	
.oracle/checkins/batch-2.md:2887: trailing whitespace.
+++++++    85	
.oracle/checkins/batch-2.md:2889: trailing whitespace.
+++++++    92	
.oracle/checkins/batch-2.md:2891: trailing whitespace.
+++++++    93	
.oracle/checkins/batch-2.md:2893: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2.md:2895: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2.md:2897: trailing whitespace.
+++++++   168	
.oracle/checkins/batch-2.md:2899: trailing whitespace.
+++++++   169	
.oracle/checkins/batch-2.md:2901: trailing whitespace.
+++++++   236	
.oracle/checkins/batch-2.md:2903: trailing whitespace.
+++++++   237	
.oracle/checkins/batch-2.md:2905: trailing whitespace.
+++++++   248	
.oracle/checkins/batch-2.md:2907: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2.md:2909: trailing whitespace.
+++++++   271	
.oracle/checkins/batch-2.md:2911: trailing whitespace.
+++++++   272	
.oracle/checkins/batch-2.md:2913: trailing whitespace.
+++++++   288	
.oracle/checkins/batch-2.md:2915: trailing whitespace.
+++++++   295	
.oracle/checkins/batch-2.md:2917: trailing whitespace.
+++++++   316	
.oracle/checkins/batch-2.md:2919: trailing whitespace.
+++++++   343	
.oracle/checkins/batch-2.md:2921: trailing whitespace.
+++++++   344	
.oracle/checkins/batch-2.md:2923: trailing whitespace.
+++++++   347	
.oracle/checkins/batch-2.md:2925: trailing whitespace.
+++++++   349	
.oracle/checkins/batch-2.md:2927: trailing whitespace.
+++++++   350	
.oracle/checkins/batch-2.md:2929: trailing whitespace.
+++++++   353	
.oracle/checkins/batch-2.md:2931: trailing whitespace.
+++++++   357	
.oracle/checkins/batch-2.md:2933: trailing whitespace.
+++++++   358	
.oracle/checkins/batch-2.md:2935: trailing whitespace.
+++++++   361	
.oracle/checkins/batch-2.md:2937: trailing whitespace.
+++++++   366	
.oracle/checkins/batch-2.md:2939: trailing whitespace.
+++++++   367	
.oracle/checkins/batch-2.md:2941: trailing whitespace.
+++++++   370	
.oracle/checkins/batch-2.md:2943: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2.md:2945: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2.md:2947: trailing whitespace.
+++++++    10	
.oracle/checkins/batch-2.md:2949: trailing whitespace.
+++++++    18	
.oracle/checkins/batch-2.md:2951: trailing whitespace.
+++++++    21	
.oracle/checkins/batch-2.md:2953: trailing whitespace.
+++++++    22	
.oracle/checkins/batch-2.md:2955: trailing whitespace.
+++++++    24	
.oracle/checkins/batch-2.md:2957: trailing whitespace.
+++++++    35	
.oracle/checkins/batch-2.md:2959: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2.md:2961: trailing whitespace.
+++++++    52	
.oracle/checkins/batch-2.md:2963: trailing whitespace.
+++++++    73	
.oracle/checkins/batch-2.md:2965: trailing whitespace.
+++++++    93	
.oracle/checkins/batch-2.md:2967: trailing whitespace.
+++++++   110	
.oracle/checkins/batch-2.md:2969: trailing whitespace.
+++++++   123	
.oracle/checkins/batch-2.md:2971: trailing whitespace.
+++++++   130	
.oracle/checkins/batch-2.md:2973: trailing whitespace.
+++++++   131	
.oracle/checkins/batch-2.md:2975: trailing whitespace.
+++++++   134	
.oracle/checkins/batch-2.md:2977: trailing whitespace.
+++++++   158	
.oracle/checkins/batch-2.md:2979: trailing whitespace.
+++++++   159	
.oracle/checkins/batch-2.md:2981: trailing whitespace.
+++++++   165	
.oracle/checkins/batch-2.md:2983: trailing whitespace.
+++++++   166	
.oracle/checkins/batch-2.md:2985: trailing whitespace.
+++++++   171	
.oracle/checkins/batch-2.md:2987: trailing whitespace.
+++++++   172	
.oracle/checkins/batch-2.md:2989: trailing whitespace.
+++++++   186	
.oracle/checkins/batch-2.md:2991: trailing whitespace.
+++++++   187	
.oracle/checkins/batch-2.md:2993: trailing whitespace.
+++++++   194	
.oracle/checkins/batch-2.md:2995: trailing whitespace.
+++++++   195	
.oracle/checkins/batch-2.md:2997: trailing whitespace.
+++++++   205	
.oracle/checkins/batch-2.md:2999: trailing whitespace.
+++++++   206	
.oracle/checkins/batch-2.md:3001: trailing whitespace.
+++++++   209	
.oracle/checkins/batch-2.md:3003: trailing whitespace.
+++++++   215	
.oracle/checkins/batch-2.md:3005: trailing whitespace.
+++++++   216	
.oracle/checkins/batch-2.md:3007: trailing whitespace.
+++++++   225	
.oracle/checkins/batch-2.md:3009: trailing whitespace.
+++++++   226	
.oracle/checkins/batch-2.md:3011: trailing whitespace.
+++++++   231	
.oracle/checkins/batch-2.md:3013: trailing whitespace.
+++++++   232	
.oracle/checkins/batch-2.md:3015: trailing whitespace.
+++++++   241	
.oracle/checkins/batch-2.md:3017: trailing whitespace.
+++++++   242	
.oracle/checkins/batch-2.md:3019: trailing whitespace.
+++++++   248	
.oracle/checkins/batch-2.md:3021: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2.md:3023: trailing whitespace.
+++++++   507	
.oracle/checkins/batch-2.md:3025: trailing whitespace.
+++++++   511	
.oracle/checkins/batch-2.md:3027: trailing whitespace.
+++++++   530	
.oracle/checkins/batch-2.md:3029: trailing whitespace.
+++++++   563	
.oracle/checkins/batch-2.md:3031: trailing whitespace.
+++++++   564	
.oracle/checkins/batch-2.md:3033: trailing whitespace.
+++++++   571	
.oracle/checkins/batch-2.md:3035: trailing whitespace.
+++++++   576	
.oracle/checkins/batch-2.md:3037: trailing whitespace.
+++++++   582	
.oracle/checkins/batch-2.md:3039: trailing whitespace.
+++++++   583	
.oracle/checkins/batch-2.md:3041: trailing whitespace.
+++++++   587	
.oracle/checkins/batch-2.md:3043: trailing whitespace.
+++++++   592	
.oracle/checkins/batch-2.md:3045: trailing whitespace.
+++++++   604	
.oracle/checkins/batch-2.md:3047: trailing whitespace.
+++++++   609	
.oracle/checkins/batch-2.md:3049: trailing whitespace.
+++++++   621	
.oracle/checkins/batch-2.md:3051: trailing whitespace.
+++++++   633	
.oracle/checkins/batch-2.md:3053: trailing whitespace.
+++++++   634	
.oracle/checkins/batch-2.md:3055: trailing whitespace.
+++++++   655	
.oracle/checkins/batch-2.md:3057: trailing whitespace.
+++++++   656	
.oracle/checkins/batch-2.md:3059: trailing whitespace.
+++++++   660	
.oracle/checkins/batch-2.md:3061: trailing whitespace.
+++++++   667	
.oracle/checkins/batch-2.md:3063: trailing whitespace.
+++++++   690	
.oracle/checkins/batch-2.md:3065: trailing whitespace.
+++++++   702	
.oracle/checkins/batch-2.md:3067: trailing whitespace.
+++++++   717	
.oracle/checkins/batch-2.md:3069: trailing whitespace.
+++++++  1662	
.oracle/checkins/batch-2.md:3071: trailing whitespace.
+++++++  1686	
.oracle/checkins/batch-2.md:3073: trailing whitespace.
+++++++  1693	
.oracle/checkins/batch-2.md:3075: trailing whitespace.
+++++++  1694	
.oracle/checkins/batch-2.md:3077: trailing whitespace.
+++++++  1698	
.oracle/checkins/batch-2.md:3079: trailing whitespace.
+++++++  1705	
.oracle/checkins/batch-2.md:3081: trailing whitespace.
+++++++  1753	
.oracle/checkins/batch-2.md:3083: trailing whitespace.
+++++++  1757	
.oracle/checkins/batch-2.md:3085: trailing whitespace.
+++++++  1763	
.oracle/checkins/batch-2.md:3087: trailing whitespace.
+++++++  1769	
.oracle/checkins/batch-2.md:3089: trailing whitespace.
+++++++  1773	
.oracle/checkins/batch-2.md:3091: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2.md:3093: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2.md:3095: trailing whitespace.
+++++++    11	
.oracle/checkins/batch-2.md:3097: trailing whitespace.
+++++++    20	
.oracle/checkins/batch-2.md:3099: trailing whitespace.
+++++++    21	
.oracle/checkins/batch-2.md:3101: trailing whitespace.
+++++++    48	
.oracle/checkins/batch-2.md:3103: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2.md:3105: trailing whitespace.
+++++++    52	
.oracle/checkins/batch-2.md:3107: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2.md:3109: trailing whitespace.
+++++++    56	
.oracle/checkins/batch-2.md:3111: trailing whitespace.
+++++++    57	
.oracle/checkins/batch-2.md:3113: trailing whitespace.
+++++++    60	
.oracle/checkins/batch-2.md:3115: trailing whitespace.
+++++++    61	
.oracle/checkins/batch-2.md:3117: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2.md:3119: trailing whitespace.
+++++++    73	
.oracle/checkins/batch-2.md:3121: trailing whitespace.
+++++++    81	
.oracle/checkins/batch-2.md:3123: trailing whitespace.
+++++++    88	
.oracle/checkins/batch-2.md:3125: trailing whitespace.
+++++++    89	
.oracle/checkins/batch-2.md:3127: trailing whitespace.
+++++++    96	
.oracle/checkins/batch-2.md:3129: trailing whitespace.
+++++++    97	
.oracle/checkins/batch-2.md:3131: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2.md:3133: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2.md:3135: trailing whitespace.
+++++++   113	
.oracle/checkins/batch-2.md:3137: trailing whitespace.
+++++++   114	
.oracle/checkins/batch-2.md:3139: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2.md:3141: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2.md:3143: trailing whitespace.
+++++++   324	
.oracle/checkins/batch-2.md:3145: trailing whitespace.
+++++++   325	
.oracle/checkins/batch-2.md:3147: trailing whitespace.
+++++++   338	
.oracle/checkins/batch-2.md:3149: trailing whitespace.
+++++++   339	
.oracle/checkins/batch-2.md:3151: trailing whitespace.
+++++++   356	
.oracle/checkins/batch-2.md:3153: trailing whitespace.
+++++++   357	
.oracle/checkins/batch-2.md:3155: trailing whitespace.
+++++++   375	
.oracle/checkins/batch-2.md:3157: trailing whitespace.
+++++++   376	
.oracle/checkins/batch-2.md:3159: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3161: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3163: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3165: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3167: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3169: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3171: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3173: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3175: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2.md:3177: trailing whitespace.
+++++++   809	
.oracle/checkins/batch-2.md:3179: trailing whitespace.
+++++++   810	
.oracle/checkins/batch-2.md:3181: trailing whitespace.
+++++++   904	
.oracle/checkins/batch-2.md:3183: trailing whitespace.
+++++++   905	
.oracle/checkins/batch-2.md:3185: trailing whitespace.
+++++++   965	
.oracle/checkins/batch-2.md:3187: trailing whitespace.
+++++++   966	
.oracle/checkins/batch-2.md:3189: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2.md:3191: trailing whitespace.
+++++++     4	
.oracle/checkins/batch-2.md:3193: trailing whitespace.
+++++++     6	
.oracle/checkins/batch-2.md:3195: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2.md:3197: trailing whitespace.
+++++++    17	
.oracle/checkins/batch-2.md:3199: trailing whitespace.
+++++++    19	
.oracle/checkins/batch-2.md:3201: trailing whitespace.
+++++++    25	
.oracle/checkins/batch-2.md:3203: trailing whitespace.
+++++++    27	
.oracle/checkins/batch-2.md:3205: trailing whitespace.
+++++++    29	
.oracle/checkins/batch-2.md:3207: trailing whitespace.
+++++++    31	
.oracle/checkins/batch-2.md:3209: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2.md:3211: trailing whitespace.
+++++++    42	
.oracle/checkins/batch-2.md:3213: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2.md:3215: trailing whitespace.
+++++++    51	
.oracle/checkins/batch-2.md:3217: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2.md:3219: trailing whitespace.
+++++++    55	
.oracle/checkins/batch-2.md:3221: trailing whitespace.
+++++++    63	
.oracle/checkins/batch-2.md:3223: trailing whitespace.
+++++++    65	
.oracle/checkins/batch-2.md:3225: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2.md:3227: trailing whitespace.
+++++++    74	
.oracle/checkins/batch-2.md:3229: trailing whitespace.
+++++++    76	
.oracle/checkins/batch-2.md:3231: trailing whitespace.
+++++++    78	
.oracle/checkins/batch-2.md:3233: trailing whitespace.
+++++++   131	
.oracle/checkins/batch-2.md:3235: trailing whitespace.
+++++++   132	
.oracle/checkins/batch-2.md:3237: trailing whitespace.
+++++++   162	
.oracle/checkins/batch-2.md:3239: trailing whitespace.
+++++++   163	
.oracle/checkins/batch-2.md:3241: trailing whitespace.
+++++++   178	
.oracle/checkins/batch-2.md:3243: trailing whitespace.
+++++++   179	
.oracle/checkins/batch-2.md:3245: trailing whitespace.
+++++++   206	
.oracle/checkins/batch-2.md:3247: trailing whitespace.
+++++++   207	
.oracle/checkins/batch-2.md:3249: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2.md:3251: trailing whitespace.
+++++++   250	
.oracle/checkins/batch-2.md:3253: trailing whitespace.
+++++++   288	
.oracle/checkins/batch-2.md:3255: trailing whitespace.
+++++++   289	
.oracle/checkins/batch-2.md:3257: trailing whitespace.
+++++++   302	
.oracle/checkins/batch-2.md:3259: trailing whitespace.
+++++++   303	
.oracle/checkins/batch-2.md:3261: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2.md:3263: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2.md:3265: trailing whitespace.
+++++++   330	
.oracle/checkins/batch-2.md:3267: trailing whitespace.
+++++++   331	
.oracle/checkins/batch-2.md:3269: trailing whitespace.
+++++++   343	
.oracle/checkins/batch-2.md:3271: trailing whitespace.
+++++++   344	
.oracle/checkins/batch-2.md:3273: trailing whitespace.
+++++++   288	
.oracle/checkins/batch-2.md:3275: trailing whitespace.
+++++++    98	
.oracle/checkins/batch-2.md:3277: trailing whitespace.
+++++++   101	
.oracle/checkins/batch-2.md:3279: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2.md:3281: trailing whitespace.
+++++++   107	
.oracle/checkins/batch-2.md:3283: trailing whitespace.
+++++++   110	
.oracle/checkins/batch-2.md:3285: trailing whitespace.
+++++++   113	
.oracle/checkins/batch-2.md:3287: trailing whitespace.
+++++++  1349	
.oracle/checkins/batch-2.md:3289: trailing whitespace.
+++++++  1350	
.oracle/checkins/batch-2.md:3291: trailing whitespace.
+++++++  1354	
.oracle/checkins/batch-2.md:3293: trailing whitespace.
+++++++  1365	
.oracle/checkins/batch-2.md:3295: trailing whitespace.
+++++++  1444	
.oracle/checkins/batch-2.md:3297: trailing whitespace.
+++++++  1460	
.oracle/checkins/batch-2.md:3299: trailing whitespace.
++++++  1444	
.oracle/checkins/batch-2.md:3301: trailing whitespace.
++++++  1460	
.oracle/checkins/batch-2.md:3303: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3305: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3307: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3309: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3311: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3313: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3315: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3317: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3319: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3321: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3323: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3325: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3327: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3329: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3331: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3333: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3335: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3337: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3339: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3341: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3343: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3345: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3347: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3349: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3351: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3353: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3355: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3357: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3359: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3361: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3363: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3365: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3367: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3369: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3371: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3373: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3375: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3377: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3379: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3381: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3383: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3385: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3387: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3389: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3391: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3393: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3395: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3397: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3399: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3401: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3403: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3405: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3407: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3409: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3411: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3413: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3415: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3417: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3419: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3421: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3423: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3425: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3427: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3429: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3431: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3433: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3435: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3437: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3439: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3441: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3443: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3445: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3447: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3449: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3451: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3453: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3455: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3457: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3459: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3461: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3463: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3465: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3467: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3469: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3471: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3473: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3475: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3477: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3479: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3481: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3483: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3485: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3487: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3489: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3491: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3493: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3495: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3497: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3499: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3501: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3503: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3505: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3507: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3509: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3511: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3513: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3515: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3517: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3519: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3521: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3523: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3525: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3527: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3529: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3531: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3533: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3535: trailing whitespace.
++++++     2	
.oracle/checkins/batch-2.md:3537: trailing whitespace.
++++++     4	
.oracle/checkins/batch-2.md:3539: trailing whitespace.
++++++     8	
.oracle/checkins/batch-2.md:3541: trailing whitespace.
++++++    11	
.oracle/checkins/batch-2.md:3543: trailing whitespace.
++++++    28	
.oracle/checkins/batch-2.md:3545: trailing whitespace.
++++++    29	
.oracle/checkins/batch-2.md:3547: trailing whitespace.
++++++    32	
.oracle/checkins/batch-2.md:3549: trailing whitespace.
++++++    33	
.oracle/checkins/batch-2.md:3551: trailing whitespace.
++++++    38	
.oracle/checkins/batch-2.md:3553: trailing whitespace.
++++++    40	
.oracle/checkins/batch-2.md:3555: trailing whitespace.
++++++    41	
.oracle/checkins/batch-2.md:3557: trailing whitespace.
++++++    53	
.oracle/checkins/batch-2.md:3559: trailing whitespace.
++++++    54	
.oracle/checkins/batch-2.md:3561: trailing whitespace.
++++++    81	
.oracle/checkins/batch-2.md:3563: trailing whitespace.
++++++    82	
.oracle/checkins/batch-2.md:3565: trailing whitespace.
++++++    85	
.oracle/checkins/batch-2.md:3567: trailing whitespace.
++++++    92	
.oracle/checkins/batch-2.md:3569: trailing whitespace.
++++++    93	
.oracle/checkins/batch-2.md:3571: trailing whitespace.
++++++   105	
.oracle/checkins/batch-2.md:3573: trailing whitespace.
++++++   106	
.oracle/checkins/batch-2.md:3575: trailing whitespace.
++++++   173	
.oracle/checkins/batch-2.md:3577: trailing whitespace.
++++++   174	
.oracle/checkins/batch-2.md:3579: trailing whitespace.
++++++   248	
.oracle/checkins/batch-2.md:3581: trailing whitespace.
++++++   249	
.oracle/checkins/batch-2.md:3583: trailing whitespace.
++++++   260	
.oracle/checkins/batch-2.md:3585: trailing whitespace.
++++++   261	
.oracle/checkins/batch-2.md:3587: trailing whitespace.
++++++   283	
.oracle/checkins/batch-2.md:3589: trailing whitespace.
++++++   284	
.oracle/checkins/batch-2.md:3591: trailing whitespace.
++++++   300	
.oracle/checkins/batch-2.md:3593: trailing whitespace.
++++++   307	
.oracle/checkins/batch-2.md:3595: trailing whitespace.
++++++   328	
.oracle/checkins/batch-2.md:3597: trailing whitespace.
++++++   355	
.oracle/checkins/batch-2.md:3599: trailing whitespace.
++++++   356	
.oracle/checkins/batch-2.md:3601: trailing whitespace.
++++++   359	
.oracle/checkins/batch-2.md:3603: trailing whitespace.
++++++   361	
.oracle/checkins/batch-2.md:3605: trailing whitespace.
++++++   362	
.oracle/checkins/batch-2.md:3607: trailing whitespace.
++++++   365	
.oracle/checkins/batch-2.md:3609: trailing whitespace.
++++++   369	
.oracle/checkins/batch-2.md:3611: trailing whitespace.
++++++   370	
.oracle/checkins/batch-2.md:3613: trailing whitespace.
++++++   373	
.oracle/checkins/batch-2.md:3615: trailing whitespace.
++++++   378	
.oracle/checkins/batch-2.md:3617: trailing whitespace.
++++++   379	
.oracle/checkins/batch-2.md:3619: trailing whitespace.
++++++   382	
.oracle/checkins/batch-2.md:3621: trailing whitespace.
++++++   384	
.oracle/checkins/batch-2.md:3623: trailing whitespace.
++++++   385	
.oracle/checkins/batch-2.md:3625: trailing whitespace.
++++++   651	
.oracle/checkins/batch-2.md:3627: trailing whitespace.
++++++   652	
.oracle/checkins/batch-2.md:3629: trailing whitespace.
++++++   683	
.oracle/checkins/batch-2.md:3631: trailing whitespace.
++++++   693	
.oracle/checkins/batch-2.md:3633: trailing whitespace.
++++++   729	
.oracle/checkins/batch-2.md:3635: trailing whitespace.
++++++   730	
.oracle/checkins/batch-2.md:3637: trailing whitespace.
++++++   748	
.oracle/checkins/batch-2.md:3639: trailing whitespace.
++++++   749	
.oracle/checkins/batch-2.md:3641: trailing whitespace.
++++++   785	
.oracle/checkins/batch-2.md:3643: trailing whitespace.
++++++   786	
.oracle/checkins/batch-2.md:3645: trailing whitespace.
++++++   800	
.oracle/checkins/batch-2.md:3647: trailing whitespace.
++++++   801	
.oracle/checkins/batch-2.md:3649: trailing whitespace.
++++++   817	
.oracle/checkins/batch-2.md:3651: trailing whitespace.
++++++   818	
.oracle/checkins/batch-2.md:3653: trailing whitespace.
++++++   914	
.oracle/checkins/batch-2.md:3655: trailing whitespace.
++++++   915	
.oracle/checkins/batch-2.md:3657: trailing whitespace.
++++++  1001	
.oracle/checkins/batch-2.md:3659: trailing whitespace.
++++++  1002	
.oracle/checkins/batch-2.md:3661: trailing whitespace.
++++++  1011	
.oracle/checkins/batch-2.md:3663: trailing whitespace.
++++++  1012	
.oracle/checkins/batch-2.md:3665: trailing whitespace.
++++++   285	
.oracle/checkins/batch-2.md:3667: trailing whitespace.
++++++   294	
.oracle/checkins/batch-2.md:3669: trailing whitespace.
++++++   295	
.oracle/checkins/batch-2.md:3671: trailing whitespace.
++++++   302	
.oracle/checkins/batch-2.md:3673: trailing whitespace.
++++++   303	
.oracle/checkins/batch-2.md:3675: trailing whitespace.
++++++   312	
.oracle/checkins/batch-2.md:3677: trailing whitespace.
++++++   313	
.oracle/checkins/batch-2.md:3679: trailing whitespace.
++++++   330	
.oracle/checkins/batch-2.md:3681: trailing whitespace.
++++++   331	
.oracle/checkins/batch-2.md:3683: trailing whitespace.
++++++   826	
.oracle/checkins/batch-2.md:3685: trailing whitespace.
++++++   868	
.oracle/checkins/batch-2.md:3687: trailing whitespace.
++++++   875	
.oracle/checkins/batch-2.md:3689: trailing whitespace.
++++++   878	
.oracle/checkins/batch-2.md:3691: trailing whitespace.
++++++   892	
.oracle/checkins/batch-2.md:3693: trailing whitespace.
++++++   893	
.oracle/checkins/batch-2.md:3695: trailing whitespace.
++++++   897	
.oracle/checkins/batch-2.md:3697: trailing whitespace.
++++++   905	
.oracle/checkins/batch-2.md:3699: trailing whitespace.
++++++   936	
.oracle/checkins/batch-2.md:3701: trailing whitespace.
++++++   949	
.oracle/checkins/batch-2.md:3703: trailing whitespace.
++++++   980	
.oracle/checkins/batch-2.md:3705: trailing whitespace.
++++++   987	
.oracle/checkins/batch-2.md:3707: trailing whitespace.
++++++   988	
.oracle/checkins/batch-2.md:3709: trailing whitespace.
++++++   992	
.oracle/checkins/batch-2.md:3711: trailing whitespace.
++++++  1000	
.oracle/checkins/batch-2.md:3713: trailing whitespace.
++++++   440	
.oracle/checkins/batch-2.md:3715: trailing whitespace.
++++++   441	
.oracle/checkins/batch-2.md:3717: trailing whitespace.
++++++   445	
.oracle/checkins/batch-2.md:3719: trailing whitespace.
++++++   459	
.oracle/checkins/batch-2.md:3721: trailing whitespace.
++++++   507	
.oracle/checkins/batch-2.md:3723: trailing whitespace.
++++++   511	
.oracle/checkins/batch-2.md:3725: trailing whitespace.
++++++   530	
.oracle/checkins/batch-2.md:3727: trailing whitespace.
++++++   563	
.oracle/checkins/batch-2.md:3729: trailing whitespace.
++++++   564	
.oracle/checkins/batch-2.md:3731: trailing whitespace.
++++++   571	
.oracle/checkins/batch-2.md:3733: trailing whitespace.
++++++   576	
.oracle/checkins/batch-2.md:3735: trailing whitespace.
++++++   582	
.oracle/checkins/batch-2.md:3737: trailing whitespace.
++++++   583	
.oracle/checkins/batch-2.md:3739: trailing whitespace.
++++++   587	
.oracle/checkins/batch-2.md:3741: trailing whitespace.
++++++   592	
.oracle/checkins/batch-2.md:3743: trailing whitespace.
++++++   604	
.oracle/checkins/batch-2.md:3745: trailing whitespace.
++++++   609	
.oracle/checkins/batch-2.md:3747: trailing whitespace.
++++++   621	
.oracle/checkins/batch-2.md:3749: trailing whitespace.
++++++   633	
.oracle/checkins/batch-2.md:3751: trailing whitespace.
++++++   634	
.oracle/checkins/batch-2.md:3753: trailing whitespace.
++++++   655	
.oracle/checkins/batch-2.md:3755: trailing whitespace.
++++++   656	
.oracle/checkins/batch-2.md:3757: trailing whitespace.
++++++   660	
.oracle/checkins/batch-2.md:3759: trailing whitespace.
++++++   667	
.oracle/checkins/batch-2.md:3761: trailing whitespace.
++++++   690	
.oracle/checkins/batch-2.md:3763: trailing whitespace.
++++++   702	
.oracle/checkins/batch-2.md:3765: trailing whitespace.
++++++   717	
.oracle/checkins/batch-2.md:3767: trailing whitespace.
++++++   225	
.oracle/checkins/batch-2.md:3769: trailing whitespace.
++++++   230	
.oracle/checkins/batch-2.md:3771: trailing whitespace.
++++++   238	
.oracle/checkins/batch-2.md:3773: trailing whitespace.
++++++   240	
.oracle/checkins/batch-2.md:3775: trailing whitespace.
++++++   243	
.oracle/checkins/batch-2.md:3777: trailing whitespace.
++++++   251	
.oracle/checkins/batch-2.md:3779: trailing whitespace.
++++++   255	
.oracle/checkins/batch-2.md:3781: trailing whitespace.
++++++   257	
.oracle/checkins/batch-2.md:3783: trailing whitespace.
++++++   262	
.oracle/checkins/batch-2.md:3785: trailing whitespace.
++++++   274	
.oracle/checkins/batch-2.md:3787: trailing whitespace.
++++++   276	
.oracle/checkins/batch-2.md:3789: trailing whitespace.
++++++   280	
.oracle/checkins/batch-2.md:3791: trailing whitespace.
++++++   290	
.oracle/checkins/batch-2.md:3793: trailing whitespace.
++++++   292	
.oracle/checkins/batch-2.md:3795: trailing whitespace.
++++++   461	
.oracle/checkins/batch-2.md:3797: trailing whitespace.
++++++   463	
.oracle/checkins/batch-2.md:3799: trailing whitespace.
++++++   465	
.oracle/checkins/batch-2.md:3801: trailing whitespace.
++++++   470	
.oracle/checkins/batch-2.md:3803: trailing whitespace.
++++++   492	
.oracle/checkins/batch-2.md:3805: trailing whitespace.
++++++   502	
.oracle/checkins/batch-2.md:3807: trailing whitespace.
++++++   504	
.oracle/checkins/batch-2.md:3809: trailing whitespace.
++++++     2	
.oracle/checkins/batch-2.md:3811: trailing whitespace.
++++++     4	
.oracle/checkins/batch-2.md:3813: trailing whitespace.
++++++     6	
.oracle/checkins/batch-2.md:3815: trailing whitespace.
++++++     8	
.oracle/checkins/batch-2.md:3817: trailing whitespace.
++++++    17	
.oracle/checkins/batch-2.md:3819: trailing whitespace.
++++++    19	
.oracle/checkins/batch-2.md:3821: trailing whitespace.
++++++    25	
.oracle/checkins/batch-2.md:3823: trailing whitespace.
++++++    27	
.oracle/checkins/batch-2.md:3825: trailing whitespace.
++++++    29	
.oracle/checkins/batch-2.md:3827: trailing whitespace.
++++++    31	
.oracle/checkins/batch-2.md:3829: trailing whitespace.
++++++    40	
.oracle/checkins/batch-2.md:3831: trailing whitespace.
++++++    42	
.oracle/checkins/batch-2.md:3833: trailing whitespace.
++++++    49	
.oracle/checkins/batch-2.md:3835: trailing whitespace.
++++++    51	
.oracle/checkins/batch-2.md:3837: trailing whitespace.
++++++    53	
.oracle/checkins/batch-2.md:3839: trailing whitespace.
++++++    55	
.oracle/checkins/batch-2.md:3841: trailing whitespace.
++++++    63	
.oracle/checkins/batch-2.md:3843: trailing whitespace.
++++++    65	
.oracle/checkins/batch-2.md:3845: trailing whitespace.
++++++    72	
.oracle/checkins/batch-2.md:3847: trailing whitespace.
++++++    74	
.oracle/checkins/batch-2.md:3849: trailing whitespace.
++++++    76	
.oracle/checkins/batch-2.md:3851: trailing whitespace.
++++++    78	
.oracle/checkins/batch-2.md:3853: trailing whitespace.
++++++    86	
.oracle/checkins/batch-2.md:3855: trailing whitespace.
++++++    88	
.oracle/checkins/batch-2.md:3857: trailing whitespace.
++++++    94	
.oracle/checkins/batch-2.md:3859: trailing whitespace.
++++++    96	
.oracle/checkins/batch-2.md:3861: trailing whitespace.
++++++    98	
.oracle/checkins/batch-2.md:3863: trailing whitespace.
++++++   100	
.oracle/checkins/batch-2.md:3865: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3867: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3869: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3871: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3873: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3875: trailing whitespace.
++++++ 
.oracle/checkins/batch-2.md:3877: trailing whitespace.
++++++   105	
.oracle/checkins/batch-2.md:3879: trailing whitespace.
++++++   106	
.oracle/checkins/batch-2.md:3881: trailing whitespace.
++++++   168	
.oracle/checkins/batch-2.md:3883: trailing whitespace.
++++++   169	
.oracle/checkins/batch-2.md:3885: trailing whitespace.
++++++   236	
.oracle/checkins/batch-2.md:3887: trailing whitespace.
++++++   237	
.oracle/checkins/batch-2.md:3889: trailing whitespace.
++++++   248	
.oracle/checkins/batch-2.md:3891: trailing whitespace.
++++++   249	
.oracle/checkins/batch-2.md:3893: trailing whitespace.
++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-2.md:3895: trailing whitespace.
++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-2.md:3897: trailing whitespace.
++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-2.md:3899: trailing whitespace.
++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-2.md:3901: trailing whitespace.
++++++     2	
.oracle/checkins/batch-2.md:3903: trailing whitespace.
++++++     8	
.oracle/checkins/batch-2.md:3905: trailing whitespace.
++++++    11	
.oracle/checkins/batch-2.md:3907: trailing whitespace.
++++++    20	
.oracle/checkins/batch-2.md:3909: trailing whitespace.
++++++    21	
.oracle/checkins/batch-2.md:3911: trailing whitespace.
++++++    48	
.oracle/checkins/batch-2.md:3913: trailing whitespace.
++++++    49	
.oracle/checkins/batch-2.md:3915: trailing whitespace.
++++++    52	
.oracle/checkins/batch-2.md:3917: trailing whitespace.
++++++    53	
.oracle/checkins/batch-2.md:3919: trailing whitespace.
++++++    56	
.oracle/checkins/batch-2.md:3921: trailing whitespace.
++++++    57	
.oracle/checkins/batch-2.md:3923: trailing whitespace.
++++++    60	
.oracle/checkins/batch-2.md:3925: trailing whitespace.
++++++    61	
.oracle/checkins/batch-2.md:3927: trailing whitespace.
++++++    72	
.oracle/checkins/batch-2.md:3929: trailing whitespace.
++++++    73	
.oracle/checkins/batch-2.md:3931: trailing whitespace.
++++++    81	
.oracle/checkins/batch-2.md:3933: trailing whitespace.
++++++    88	
.oracle/checkins/batch-2.md:3935: trailing whitespace.
++++++    89	
.oracle/checkins/batch-2.md:3937: trailing whitespace.
++++++    96	
.oracle/checkins/batch-2.md:3939: trailing whitespace.
++++++    97	
.oracle/checkins/batch-2.md:3941: trailing whitespace.
++++++   105	
.oracle/checkins/batch-2.md:3943: trailing whitespace.
++++++   106	
.oracle/checkins/batch-2.md:3945: trailing whitespace.
++++++   113	
.oracle/checkins/batch-2.md:3947: trailing whitespace.
++++++   114	
.oracle/checkins/batch-2.md:3949: trailing whitespace.
++++++   122	
.oracle/checkins/batch-2.md:3951: trailing whitespace.
++++++   123	
.oracle/checkins/batch-2.md:3953: trailing whitespace.
++++++   131	
.oracle/checkins/batch-2.md:3955: trailing whitespace.
++++++   132	
.oracle/checkins/batch-2.md:3957: trailing whitespace.
++++++   162	
.oracle/checkins/batch-2.md:3959: trailing whitespace.
++++++   163	
.oracle/checkins/batch-2.md:3961: trailing whitespace.
++++++   178	
.oracle/checkins/batch-2.md:3963: trailing whitespace.
++++++   179	
.oracle/checkins/batch-2.md:3965: trailing whitespace.
++++++   206	
.oracle/checkins/batch-2.md:3967: trailing whitespace.
++++++   207	
.oracle/checkins/batch-2.md:3969: trailing whitespace.
++++++   249	
.oracle/checkins/batch-2.md:3971: trailing whitespace.
++++++   250	
.oracle/checkins/batch-2.md:3973: trailing whitespace.
++++++   288	
.oracle/checkins/batch-2.md:3975: trailing whitespace.
++++++   289	
.oracle/checkins/batch-2.md:3977: trailing whitespace.
++++++   312	
.oracle/checkins/batch-2.md:3979: trailing whitespace.
++++++   313	
.oracle/checkins/batch-2.md:3981: trailing whitespace.
++++++   324	
.oracle/checkins/batch-2.md:3983: trailing whitespace.
++++++   325	
.oracle/checkins/batch-2.md:3985: trailing whitespace.
++++++   338	
.oracle/checkins/batch-2.md:3987: trailing whitespace.
++++++   339	
.oracle/checkins/batch-2.md:3989: trailing whitespace.
++++++   356	
.oracle/checkins/batch-2.md:3991: trailing whitespace.
++++++   357	
.oracle/checkins/batch-2.md:3993: trailing whitespace.
++++++   375	
.oracle/checkins/batch-2.md:3995: trailing whitespace.
++++++   376	
.oracle/checkins/batch-2.md:3997: trailing whitespace.
++++++    35	
.oracle/checkins/batch-2.md:3999: trailing whitespace.
++++++    40	
.oracle/checkins/batch-2.md:4001: trailing whitespace.
++++++    52	
.oracle/checkins/batch-2.md:4003: trailing whitespace.
++++++    73	
.oracle/checkins/batch-2.md:4005: trailing whitespace.
++++++   205	
.oracle/checkins/batch-2.md:4007: trailing whitespace.
++++++   206	
.oracle/checkins/batch-2.md:4009: trailing whitespace.
++++++   209	
.oracle/checkins/batch-2.md:4011: trailing whitespace.
++++++   215	
.oracle/checkins/batch-2.md:4013: trailing whitespace.
++++++   216	
.oracle/checkins/batch-2.md:4015: trailing whitespace.
++++++   225	
.oracle/checkins/batch-2.md:4017: trailing whitespace.
++++++   226	
.oracle/checkins/batch-2.md:4019: trailing whitespace.
++++++   231	
.oracle/checkins/batch-2.md:4021: trailing whitespace.
++++++   232	
.oracle/checkins/batch-2.md:4023: trailing whitespace.
++++++   288	
.oracle/checkins/batch-2.md:4025: trailing whitespace.
++++++   289	
.oracle/checkins/batch-2.md:4027: trailing whitespace.
++++++   158	
.oracle/checkins/batch-2.md:4029: trailing whitespace.
++++++   159	
.oracle/checkins/batch-2.md:4031: trailing whitespace.
++++++   165	
.oracle/checkins/batch-2.md:4033: trailing whitespace.
++++++   166	
.oracle/checkins/batch-2.md:4035: trailing whitespace.
++++++   171	
.oracle/checkins/batch-2.md:4037: trailing whitespace.
++++++   172	
.oracle/checkins/batch-2.md:4039: trailing whitespace.
++++++   186	
.oracle/checkins/batch-2.md:4041: trailing whitespace.
++++++   187	
.oracle/checkins/batch-2.md:4043: trailing whitespace.
++++++   194	
.oracle/checkins/batch-2.md:4045: trailing whitespace.
++++++   195	
.oracle/checkins/batch-2.md:4047: trailing whitespace.
++++++   205	
.oracle/checkins/batch-2.md:4049: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4051: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4053: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4055: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4057: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4059: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4061: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4063: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4065: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4067: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4069: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4071: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4073: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4075: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4077: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4079: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4081: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4083: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4085: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4087: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4089: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4091: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4093: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4095: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4097: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4099: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4101: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4103: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4105: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4107: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4109: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4111: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4113: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4115: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4117: trailing whitespace.
+++++    92	
.oracle/checkins/batch-2.md:4119: trailing whitespace.
+++++    93	
.oracle/checkins/batch-2.md:4121: trailing whitespace.
+++++   105	
.oracle/checkins/batch-2.md:4123: trailing whitespace.
+++++   106	
.oracle/checkins/batch-2.md:4125: trailing whitespace.
+++++   181	
.oracle/checkins/batch-2.md:4127: trailing whitespace.
+++++   182	
.oracle/checkins/batch-2.md:4129: trailing whitespace.
+++++   285	
.oracle/checkins/batch-2.md:4131: trailing whitespace.
+++++   294	
.oracle/checkins/batch-2.md:4133: trailing whitespace.
+++++   295	
.oracle/checkins/batch-2.md:4135: trailing whitespace.
+++++   302	
.oracle/checkins/batch-2.md:4137: trailing whitespace.
+++++   303	
.oracle/checkins/batch-2.md:4139: trailing whitespace.
+++++   312	
.oracle/checkins/batch-2.md:4141: trailing whitespace.
+++++   313	
.oracle/checkins/batch-2.md:4143: trailing whitespace.
+++++   330	
.oracle/checkins/batch-2.md:4145: trailing whitespace.
+++++   331	
.oracle/checkins/batch-2.md:4147: trailing whitespace.
+++++   582	
.oracle/checkins/batch-2.md:4149: trailing whitespace.
+++++   583	
.oracle/checkins/batch-2.md:4151: trailing whitespace.
+++++   587	
.oracle/checkins/batch-2.md:4153: trailing whitespace.
+++++   592	
.oracle/checkins/batch-2.md:4155: trailing whitespace.
+++++   604	
.oracle/checkins/batch-2.md:4157: trailing whitespace.
+++++   609	
.oracle/checkins/batch-2.md:4159: trailing whitespace.
+++++   621	
.oracle/checkins/batch-2.md:4161: trailing whitespace.
+++++   633	
.oracle/checkins/batch-2.md:4163: trailing whitespace.
+++++   634	
.oracle/checkins/batch-2.md:4165: trailing whitespace.
+++++   655	
.oracle/checkins/batch-2.md:4167: trailing whitespace.
+++++   656	
.oracle/checkins/batch-2.md:4169: trailing whitespace.
+++++   660	
.oracle/checkins/batch-2.md:4171: trailing whitespace.
+++++   667	
.oracle/checkins/batch-2.md:4173: trailing whitespace.
+++++   690	
.oracle/checkins/batch-2.md:4175: trailing whitespace.
+++++   702	
.oracle/checkins/batch-2.md:4177: trailing whitespace.
+++++   717	
.oracle/checkins/batch-2.md:4179: trailing whitespace.
+++++   738	
.oracle/checkins/batch-2.md:4181: trailing whitespace.
+++++   739	
.oracle/checkins/batch-2.md:4183: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4185: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4187: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4189: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4191: trailing whitespace.
+++++   520	
.oracle/checkins/batch-2.md:4193: trailing whitespace.
+++++   539	
.oracle/checkins/batch-2.md:4195: trailing whitespace.
+++++   540	
.oracle/checkins/batch-2.md:4197: trailing whitespace.
+++++   550	
.oracle/checkins/batch-2.md:4199: trailing whitespace.
+++++   551	
.oracle/checkins/batch-2.md:4201: trailing whitespace.
+++++   613	
.oracle/checkins/batch-2.md:4203: trailing whitespace.
+++++   617	
.oracle/checkins/batch-2.md:4205: trailing whitespace.
+++++   618	
.oracle/checkins/batch-2.md:4207: trailing whitespace.
+++++   631	
.oracle/checkins/batch-2.md:4209: trailing whitespace.
+++++   632	
.oracle/checkins/batch-2.md:4211: trailing whitespace.
+++++   635	
.oracle/checkins/batch-2.md:4213: trailing whitespace.
+++++   644	
.oracle/checkins/batch-2.md:4215: trailing whitespace.
+++++   645	
.oracle/checkins/batch-2.md:4217: trailing whitespace.
+++++   651	
.oracle/checkins/batch-2.md:4219: trailing whitespace.
+++++   652	
.oracle/checkins/batch-2.md:4221: trailing whitespace.
+++++   683	
.oracle/checkins/batch-2.md:4223: trailing whitespace.
+++++   693	
.oracle/checkins/batch-2.md:4225: trailing whitespace.
+++++   729	
.oracle/checkins/batch-2.md:4227: trailing whitespace.
+++++   730	
.oracle/checkins/batch-2.md:4229: trailing whitespace.
+++++   748	
.oracle/checkins/batch-2.md:4231: trailing whitespace.
+++++   749	
.oracle/checkins/batch-2.md:4233: trailing whitespace.
+++++   785	
.oracle/checkins/batch-2.md:4235: trailing whitespace.
+++++   786	
.oracle/checkins/batch-2.md:4237: trailing whitespace.
+++++   800	
.oracle/checkins/batch-2.md:4239: trailing whitespace.
+++++   801	
.oracle/checkins/batch-2.md:4241: trailing whitespace.
+++++   817	
.oracle/checkins/batch-2.md:4243: trailing whitespace.
+++++   818	
.oracle/checkins/batch-2.md:4245: trailing whitespace.
+++++   914	
.oracle/checkins/batch-2.md:4247: trailing whitespace.
+++++   915	
.oracle/checkins/batch-2.md:4249: trailing whitespace.
+++++  1014	
.oracle/checkins/batch-2.md:4251: trailing whitespace.
+++++  1015	
.oracle/checkins/batch-2.md:4253: trailing whitespace.
+++++  1024	
.oracle/checkins/batch-2.md:4255: trailing whitespace.
+++++  1025	
.oracle/checkins/batch-2.md:4257: trailing whitespace.
+++++     2	
.oracle/checkins/batch-2.md:4259: trailing whitespace.
+++++     4	
.oracle/checkins/batch-2.md:4261: trailing whitespace.
+++++     6	
.oracle/checkins/batch-2.md:4263: trailing whitespace.
+++++     8	
.oracle/checkins/batch-2.md:4265: trailing whitespace.
+++++    17	
.oracle/checkins/batch-2.md:4267: trailing whitespace.
+++++    19	
.oracle/checkins/batch-2.md:4269: trailing whitespace.
+++++    25	
.oracle/checkins/batch-2.md:4271: trailing whitespace.
+++++    27	
.oracle/checkins/batch-2.md:4273: trailing whitespace.
+++++    29	
.oracle/checkins/batch-2.md:4275: trailing whitespace.
+++++    31	
.oracle/checkins/batch-2.md:4277: trailing whitespace.
+++++    40	
.oracle/checkins/batch-2.md:4279: trailing whitespace.
+++++    42	
.oracle/checkins/batch-2.md:4281: trailing whitespace.
+++++    49	
.oracle/checkins/batch-2.md:4283: trailing whitespace.
+++++    51	
.oracle/checkins/batch-2.md:4285: trailing whitespace.
+++++    53	
.oracle/checkins/batch-2.md:4287: trailing whitespace.
+++++    55	
.oracle/checkins/batch-2.md:4289: trailing whitespace.
+++++    63	
.oracle/checkins/batch-2.md:4291: trailing whitespace.
+++++    65	
.oracle/checkins/batch-2.md:4293: trailing whitespace.
+++++    72	
.oracle/checkins/batch-2.md:4295: trailing whitespace.
+++++    74	
.oracle/checkins/batch-2.md:4297: trailing whitespace.
+++++    76	
.oracle/checkins/batch-2.md:4299: trailing whitespace.
+++++    78	
.oracle/checkins/batch-2.md:4301: trailing whitespace.
+++++    86	
.oracle/checkins/batch-2.md:4303: trailing whitespace.
+++++    88	
.oracle/checkins/batch-2.md:4305: trailing whitespace.
+++++    94	
.oracle/checkins/batch-2.md:4307: trailing whitespace.
+++++    96	
.oracle/checkins/batch-2.md:4309: trailing whitespace.
+++++    98	
.oracle/checkins/batch-2.md:4311: trailing whitespace.
+++++   100	
.oracle/checkins/batch-2.md:4313: trailing whitespace.
+++++   109	
.oracle/checkins/batch-2.md:4315: trailing whitespace.
+++++   111	
.oracle/checkins/batch-2.md:4317: trailing whitespace.
+++++   119	
.oracle/checkins/batch-2.md:4319: trailing whitespace.
+++++   121	
.oracle/checkins/batch-2.md:4321: trailing whitespace.
+++++   123	
.oracle/checkins/batch-2.md:4323: trailing whitespace.
+++++   125	
.oracle/checkins/batch-2.md:4325: trailing whitespace.
+++++   133	
.oracle/checkins/batch-2.md:4327: trailing whitespace.
+++++   135	
.oracle/checkins/batch-2.md:4329: trailing whitespace.
+++++   142	
.oracle/checkins/batch-2.md:4331: trailing whitespace.
+++++   144	
.oracle/checkins/batch-2.md:4333: trailing whitespace.
+++++   146	
.oracle/checkins/batch-2.md:4335: trailing whitespace.
+++++   148	
.oracle/checkins/batch-2.md:4337: trailing whitespace.
+++++   159	
.oracle/checkins/batch-2.md:4339: trailing whitespace.
+++++   161	
.oracle/checkins/batch-2.md:4341: trailing whitespace.
+++++   168	
.oracle/checkins/batch-2.md:4343: trailing whitespace.
+++++   170	
.oracle/checkins/batch-2.md:4345: trailing whitespace.
+++++     2	
.oracle/checkins/batch-2.md:4347: trailing whitespace.
+++++     4	
.oracle/checkins/batch-2.md:4349: trailing whitespace.
+++++     6	
.oracle/checkins/batch-2.md:4351: trailing whitespace.
+++++     8	
.oracle/checkins/batch-2.md:4353: trailing whitespace.
+++++    17	
.oracle/checkins/batch-2.md:4355: trailing whitespace.
+++++    19	
.oracle/checkins/batch-2.md:4357: trailing whitespace.
+++++    25	
.oracle/checkins/batch-2.md:4359: trailing whitespace.
+++++    27	
.oracle/checkins/batch-2.md:4361: trailing whitespace.
+++++    29	
.oracle/checkins/batch-2.md:4363: trailing whitespace.
+++++    31	
.oracle/checkins/batch-2.md:4365: trailing whitespace.
+++++    40	
.oracle/checkins/batch-2.md:4367: trailing whitespace.
+++++    42	
.oracle/checkins/batch-2.md:4369: trailing whitespace.
+++++    49	
.oracle/checkins/batch-2.md:4371: trailing whitespace.
+++++    51	
.oracle/checkins/batch-2.md:4373: trailing whitespace.
+++++    53	
.oracle/checkins/batch-2.md:4375: trailing whitespace.
+++++    55	
.oracle/checkins/batch-2.md:4377: trailing whitespace.
+++++    63	
.oracle/checkins/batch-2.md:4379: trailing whitespace.
+++++    65	
.oracle/checkins/batch-2.md:4381: trailing whitespace.
+++++    72	
.oracle/checkins/batch-2.md:4383: trailing whitespace.
+++++   105	
.oracle/checkins/batch-2.md:4385: trailing whitespace.
+++++   106	
.oracle/checkins/batch-2.md:4387: trailing whitespace.
+++++   173	
.oracle/checkins/batch-2.md:4389: trailing whitespace.
+++++   174	
.oracle/checkins/batch-2.md:4391: trailing whitespace.
+++++A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-2.md:4393: trailing whitespace.
+++++   186	
.oracle/checkins/batch-2.md:4395: trailing whitespace.
+++++   187	
.oracle/checkins/batch-2.md:4397: trailing whitespace.
+++++   194	
.oracle/checkins/batch-2.md:4399: trailing whitespace.
+++++   195	
.oracle/checkins/batch-2.md:4401: trailing whitespace.
+++++   205	
.oracle/checkins/batch-2.md:4403: trailing whitespace.
+++++   206	
.oracle/checkins/batch-2.md:4405: trailing whitespace.
+++++   209	
.oracle/checkins/batch-2.md:4407: trailing whitespace.
+++++   215	
.oracle/checkins/batch-2.md:4409: trailing whitespace.
+++++   216	
.oracle/checkins/batch-2.md:4411: trailing whitespace.
+++++   225	
.oracle/checkins/batch-2.md:4413: trailing whitespace.
+++++   226	
.oracle/checkins/batch-2.md:4415: trailing whitespace.
+++++   231	
.oracle/checkins/batch-2.md:4417: trailing whitespace.
+++++   232	
.oracle/checkins/batch-2.md:4419: trailing whitespace.
+++++   241	
.oracle/checkins/batch-2.md:4421: trailing whitespace.
+++++   242	
.oracle/checkins/batch-2.md:4423: trailing whitespace.
+++++   248	
.oracle/checkins/batch-2.md:4425: trailing whitespace.
+++++   249	
.oracle/checkins/batch-2.md:4427: trailing whitespace.
+++++   262	
.oracle/checkins/batch-2.md:4429: trailing whitespace.
+++++   263	
.oracle/checkins/batch-2.md:4431: trailing whitespace.
+++++   268	
.oracle/checkins/batch-2.md:4433: trailing whitespace.
+++++   269	
.oracle/checkins/batch-2.md:4435: trailing whitespace.
+++++   276	
.oracle/checkins/batch-2.md:4437: trailing whitespace.
+++++   277	
.oracle/checkins/batch-2.md:4439: trailing whitespace.
+++++   284	
.oracle/checkins/batch-2.md:4441: trailing whitespace.
+++++   285	
.oracle/checkins/batch-2.md:4443: trailing whitespace.
+++++     2	
.oracle/checkins/batch-2.md:4445: trailing whitespace.
+++++     8	
.oracle/checkins/batch-2.md:4447: trailing whitespace.
+++++    11	
.oracle/checkins/batch-2.md:4449: trailing whitespace.
+++++    20	
.oracle/checkins/batch-2.md:4451: trailing whitespace.
+++++    21	
.oracle/checkins/batch-2.md:4453: trailing whitespace.
+++++    48	
.oracle/checkins/batch-2.md:4455: trailing whitespace.
+++++    49	
.oracle/checkins/batch-2.md:4457: trailing whitespace.
+++++    52	
.oracle/checkins/batch-2.md:4459: trailing whitespace.
+++++    53	
.oracle/checkins/batch-2.md:4461: trailing whitespace.
+++++    56	
.oracle/checkins/batch-2.md:4463: trailing whitespace.
+++++    57	
.oracle/checkins/batch-2.md:4465: trailing whitespace.
+++++    60	
.oracle/checkins/batch-2.md:4467: trailing whitespace.
+++++    61	
.oracle/checkins/batch-2.md:4469: trailing whitespace.
+++++    72	
.oracle/checkins/batch-2.md:4471: trailing whitespace.
+++++    73	
.oracle/checkins/batch-2.md:4473: trailing whitespace.
+++++    81	
.oracle/checkins/batch-2.md:4475: trailing whitespace.
+++++    88	
.oracle/checkins/batch-2.md:4477: trailing whitespace.
+++++    89	
.oracle/checkins/batch-2.md:4479: trailing whitespace.
+++++    96	
.oracle/checkins/batch-2.md:4481: trailing whitespace.
+++++    97	
.oracle/checkins/batch-2.md:4483: trailing whitespace.
+++++   105	
.oracle/checkins/batch-2.md:4485: trailing whitespace.
+++++   106	
.oracle/checkins/batch-2.md:4487: trailing whitespace.
+++++   113	
.oracle/checkins/batch-2.md:4489: trailing whitespace.
+++++   114	
.oracle/checkins/batch-2.md:4491: trailing whitespace.
+++++   122	
.oracle/checkins/batch-2.md:4493: trailing whitespace.
+++++   123	
.oracle/checkins/batch-2.md:4495: trailing whitespace.
+++++   131	
.oracle/checkins/batch-2.md:4497: trailing whitespace.
+++++   132	
.oracle/checkins/batch-2.md:4499: trailing whitespace.
+++++   162	
.oracle/checkins/batch-2.md:4501: trailing whitespace.
+++++   163	
.oracle/checkins/batch-2.md:4503: trailing whitespace.
+++++   178	
.oracle/checkins/batch-2.md:4505: trailing whitespace.
+++++   179	
.oracle/checkins/batch-2.md:4507: trailing whitespace.
+++++   206	
.oracle/checkins/batch-2.md:4509: trailing whitespace.
+++++   207	
.oracle/checkins/batch-2.md:4511: trailing whitespace.
+++++   249	
.oracle/checkins/batch-2.md:4513: trailing whitespace.
+++++   250	
.oracle/checkins/batch-2.md:4515: trailing whitespace.
+++++   288	
.oracle/checkins/batch-2.md:4517: trailing whitespace.
+++++   289	
.oracle/checkins/batch-2.md:4519: trailing whitespace.
+++++   312	
.oracle/checkins/batch-2.md:4521: trailing whitespace.
+++++   313	
.oracle/checkins/batch-2.md:4523: trailing whitespace.
+++++   324	
.oracle/checkins/batch-2.md:4525: trailing whitespace.
+++++   325	
.oracle/checkins/batch-2.md:4527: trailing whitespace.
+++++   338	
.oracle/checkins/batch-2.md:4529: trailing whitespace.
+++++   339	
.oracle/checkins/batch-2.md:4531: trailing whitespace.
+++++   356	
.oracle/checkins/batch-2.md:4533: trailing whitespace.
+++++   357	
.oracle/checkins/batch-2.md:4535: trailing whitespace.
+++++   375	
.oracle/checkins/batch-2.md:4537: trailing whitespace.
+++++   376	
.oracle/checkins/batch-2.md:4539: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4541: trailing whitespace.
+++++ 
.oracle/checkins/batch-2.md:4543: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4545: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4547: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4549: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4551: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4553: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4555: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4557: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4559: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4561: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4563: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4565: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4567: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4569: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4571: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4573: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4575: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4577: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4579: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4581: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4583: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4585: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4587: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4589: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4591: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4593: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4595: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4597: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4599: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4601: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4603: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4605: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4607: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4609: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4611: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4613: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4615: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4617: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4619: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4621: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4623: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4625: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4627: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4629: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4631: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4633: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4635: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4637: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4639: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4641: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4643: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4645: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4647: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4649: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4651: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4653: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4655: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4657: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4659: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4661: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4663: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4665: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4667: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4669: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4671: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4673: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4675: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4677: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4679: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4681: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4683: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4685: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4687: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4689: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4691: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4693: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4695: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4697: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4699: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4701: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4703: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4705: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4707: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4709: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4711: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4713: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4715: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4717: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4719: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4721: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4723: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4725: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4727: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4729: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4731: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4733: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4735: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4737: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4739: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4741: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4743: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4745: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4747: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4749: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4751: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4753: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4755: trailing whitespace.
++++   190	
.oracle/checkins/batch-2.md:4757: trailing whitespace.
++++   191	
.oracle/checkins/batch-2.md:4759: trailing whitespace.
++++   215	
.oracle/checkins/batch-2.md:4761: trailing whitespace.
++++   216	
.oracle/checkins/batch-2.md:4763: trailing whitespace.
++++   225	
.oracle/checkins/batch-2.md:4765: trailing whitespace.
++++   226	
.oracle/checkins/batch-2.md:4767: trailing whitespace.
++++   231	
.oracle/checkins/batch-2.md:4769: trailing whitespace.
++++   232	
.oracle/checkins/batch-2.md:4771: trailing whitespace.
++++   241	
.oracle/checkins/batch-2.md:4773: trailing whitespace.
++++   242	
.oracle/checkins/batch-2.md:4775: trailing whitespace.
++++   248	
.oracle/checkins/batch-2.md:4777: trailing whitespace.
++++   249	
.oracle/checkins/batch-2.md:4779: trailing whitespace.
++++   262	
.oracle/checkins/batch-2.md:4781: trailing whitespace.
++++   263	
.oracle/checkins/batch-2.md:4783: trailing whitespace.
++++   268	
.oracle/checkins/batch-2.md:4785: trailing whitespace.
++++   269	
.oracle/checkins/batch-2.md:4787: trailing whitespace.
++++   276	
.oracle/checkins/batch-2.md:4789: trailing whitespace.
++++   277	
.oracle/checkins/batch-2.md:4791: trailing whitespace.
++++   284	
.oracle/checkins/batch-2.md:4793: trailing whitespace.
++++   285	
.oracle/checkins/batch-2.md:4795: trailing whitespace.
++++   294	
.oracle/checkins/batch-2.md:4797: trailing whitespace.
++++   295	
.oracle/checkins/batch-2.md:4799: trailing whitespace.
++++   302	
.oracle/checkins/batch-2.md:4801: trailing whitespace.
++++   303	
.oracle/checkins/batch-2.md:4803: trailing whitespace.
++++   312	
.oracle/checkins/batch-2.md:4805: trailing whitespace.
++++   313	
.oracle/checkins/batch-2.md:4807: trailing whitespace.
++++   333	
.oracle/checkins/batch-2.md:4809: trailing whitespace.
++++   334	
.oracle/checkins/batch-2.md:4811: trailing whitespace.
++++   375	
.oracle/checkins/batch-2.md:4813: trailing whitespace.
++++   376	
.oracle/checkins/batch-2.md:4815: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4817: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4819: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:4821: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:4823: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:4825: trailing whitespace.
++++ 
.oracle/checkins/batch-2.md:4827: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4829: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4831: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4833: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4835: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4837: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4839: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4841: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4843: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4845: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4847: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4849: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4851: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4853: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4855: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4857: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4859: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4861: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4863: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4865: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4867: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4869: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4871: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4873: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4875: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4877: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4879: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4881: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4883: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4885: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4887: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4889: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4891: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4893: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4895: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4897: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4899: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4901: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4903: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4905: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4907: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4909: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4911: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4913: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4915: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4917: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4919: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4921: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4923: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4925: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4927: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4929: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4931: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4933: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4935: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4937: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4939: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4941: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4943: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4945: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4947: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4949: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4951: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4953: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4955: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4957: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4959: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4961: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4963: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4965: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4967: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4969: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4971: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4973: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4975: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4977: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4979: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4981: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4983: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4985: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4987: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4989: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4991: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4993: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4995: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4997: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:4999: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5001: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5003: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5005: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5007: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5009: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5011: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5013: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5015: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5017: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5019: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5021: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5023: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5025: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5027: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5029: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5031: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5033: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5035: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5037: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5039: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5041: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5043: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5045: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5047: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5049: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5051: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5053: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5055: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5057: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5059: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5061: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5063: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5065: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5067: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5069: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5071: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5073: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5075: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5077: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5079: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5081: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5083: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5085: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5087: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5089: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5091: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5093: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5095: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5097: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5099: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5101: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5103: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5105: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5107: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5109: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5111: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5113: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5115: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5117: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5119: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5121: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5123: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5125: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5127: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5129: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5131: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5133: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2.md:5135: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2.md:5137: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2.md:5139: trailing whitespace.
+++ 
.oracle/checkins/batch-2.md:5141: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5143: trailing whitespace.
++ 
.oracle/checkins/batch-2.md:5145: trailing whitespace.
++    56	
.oracle/checkins/batch-2.md:5147: trailing whitespace.
++    59	
.oracle/checkins/batch-2.md:5149: trailing whitespace.
++    72	
.oracle/checkins/batch-2.md:5151: trailing whitespace.
++    75	
.oracle/checkins/batch-2.md:5153: trailing whitespace.
++    95	
.oracle/checkins/batch-2.md:5155: trailing whitespace.
++    99	
.oracle/checkins/batch-2.md:5157: trailing whitespace.
++     8	
.oracle/checkins/batch-2.md:5159: trailing whitespace.
++    10	
.oracle/checkins/batch-2.md:5161: trailing whitespace.
++    12	
.oracle/checkins/batch-2.md:5163: trailing whitespace.
++    17	
.oracle/checkins/batch-2.md:5165: trailing whitespace.
++    21	
.oracle/checkins/batch-2.md:5167: trailing whitespace.
++    25	
.oracle/checkins/batch-2.md:5169: trailing whitespace.
++    29	
.oracle/checkins/batch-2.md:5171: trailing whitespace.
++    33	
.oracle/checkins/batch-2.md:5173: trailing whitespace.
++    37	
.oracle/checkins/batch-2.md:5175: trailing whitespace.
++    41	
.oracle/checkins/batch-2.md:5177: trailing whitespace.
++    45	
.oracle/checkins/batch-2.md:5179: trailing whitespace.
++    48	
.oracle/checkins/batch-2.md:5181: trailing whitespace.
++    51	
.oracle/checkins/batch-2.md:6302: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:6307: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:6309: trailing whitespace.
+     9	
.oracle/checkins/batch-2.md:6319: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:6320: trailing whitespace.
+    20	
.oracle/checkins/batch-2.md:6323: trailing whitespace.
+    23	
.oracle/checkins/batch-2.md:6324: trailing whitespace.
+    24	
.oracle/checkins/batch-2.md:6339: trailing whitespace.
+    39	
.oracle/checkins/batch-2.md:6340: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:6347: trailing whitespace.
+    47	
.oracle/checkins/batch-2.md:6355: trailing whitespace.
+    55	
.oracle/checkins/batch-2.md:6364: trailing whitespace.
+    64	
.oracle/checkins/batch-2.md:6365: trailing whitespace.
+    65	
.oracle/checkins/batch-2.md:6375: trailing whitespace.
+    75	
.oracle/checkins/batch-2.md:6381: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:6386: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:6392: trailing whitespace.
+    92	
.oracle/checkins/batch-2.md:6396: trailing whitespace.
+    96	
.oracle/checkins/batch-2.md:6408: trailing whitespace.
+   108	
.oracle/checkins/batch-2.md:6414: trailing whitespace.
+   114	
.oracle/checkins/batch-2.md:6419: trailing whitespace.
+   119	
.oracle/checkins/batch-2.md:6429: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:6430: trailing whitespace.
+   130	
.oracle/checkins/batch-2.md:6435: trailing whitespace.
+   135	
.oracle/checkins/batch-2.md:6438: trailing whitespace.
+   138	
.oracle/checkins/batch-2.md:6449: trailing whitespace.
+   149	
.oracle/checkins/batch-2.md:6461: trailing whitespace.
+   161	
.oracle/checkins/batch-2.md:6462: trailing whitespace.
+   162	
.oracle/checkins/batch-2.md:6487: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:6505: trailing whitespace.
+   205	
.oracle/checkins/batch-2.md:6517: trailing whitespace.
+   217	
.oracle/checkins/batch-2.md:6518: trailing whitespace.
+   218	
.oracle/checkins/batch-2.md:6538: trailing whitespace.
+   238	
.oracle/checkins/batch-2.md:6547: trailing whitespace.
+   247	
.oracle/checkins/batch-2.md:6553: trailing whitespace.
+   253	
.oracle/checkins/batch-2.md:6554: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:6562: trailing whitespace.
+   262	
.oracle/checkins/batch-2.md:6565: trailing whitespace.
+   265	
.oracle/checkins/batch-2.md:6575: trailing whitespace.
+   275	
.oracle/checkins/batch-2.md:6594: trailing whitespace.
+   244	
.oracle/checkins/batch-2.md:6595: trailing whitespace.
+   245	
.oracle/checkins/batch-2.md:6605: trailing whitespace.
+   255	
.oracle/checkins/batch-2.md:6612: trailing whitespace.
+   262	
.oracle/checkins/batch-2.md:6615: trailing whitespace.
+   265	
.oracle/checkins/batch-2.md:6620: trailing whitespace.
+   270	
.oracle/checkins/batch-2.md:6627: trailing whitespace.
+   277	
.oracle/checkins/batch-2.md:6638: trailing whitespace.
+   288	
.oracle/checkins/batch-2.md:6646: trailing whitespace.
+   296	
.oracle/checkins/batch-2.md:6656: trailing whitespace.
+   306	
.oracle/checkins/batch-2.md:6657: trailing whitespace.
+   307	
.oracle/checkins/batch-2.md:6691: trailing whitespace.
+    14	
.oracle/checkins/batch-2.md:6710: trailing whitespace.
+    33	
.oracle/checkins/batch-2.md:6712: trailing whitespace.
+    35	
.oracle/checkins/batch-2.md:6724: trailing whitespace.
+    47	
.oracle/checkins/batch-2.md:6746: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:6749: trailing whitespace.
+     5	
.oracle/checkins/batch-2.md:6752: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:6753: trailing whitespace.
+     9	
.oracle/checkins/batch-2.md:6766: trailing whitespace.
+    22	
.oracle/checkins/batch-2.md:6767: trailing whitespace.
+    23	
.oracle/checkins/batch-2.md:6772: trailing whitespace.
+    28	
.oracle/checkins/batch-2.md:6773: trailing whitespace.
+    29	
.oracle/checkins/batch-2.md:6776: trailing whitespace.
+    32	
.oracle/checkins/batch-2.md:6778: trailing whitespace.
+    34	
.oracle/checkins/batch-2.md:6787: trailing whitespace.
+    43	
.oracle/checkins/batch-2.md:6788: trailing whitespace.
+    44	
.oracle/checkins/batch-2.md:6794: trailing whitespace.
+    50	
.oracle/checkins/batch-2.md:6796: trailing whitespace.
+    52	
.oracle/checkins/batch-2.md:6802: trailing whitespace.
+    58	
.oracle/checkins/batch-2.md:6803: trailing whitespace.
+    59	
.oracle/checkins/batch-2.md:6814: trailing whitespace.
+    70	
.oracle/checkins/batch-2.md:6817: trailing whitespace.
+    73	
.oracle/checkins/batch-2.md:6818: trailing whitespace.
+    74	
.oracle/checkins/batch-2.md:6827: trailing whitespace.
+    83	
.oracle/checkins/batch-2.md:6829: trailing whitespace.
+    85	
.oracle/checkins/batch-2.md:6830: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:6852: trailing whitespace.
+   108	
.oracle/checkins/batch-2.md:6854: trailing whitespace.
+   110	
.oracle/checkins/batch-2.md:6858: trailing whitespace.
+   114	
.oracle/checkins/batch-2.md:6859: trailing whitespace.
+   115	
.oracle/checkins/batch-2.md:6865: trailing whitespace.
+   121	
.oracle/checkins/batch-2.md:6867: trailing whitespace.
+   123	
.oracle/checkins/batch-2.md:6868: trailing whitespace.
+   124	
.oracle/checkins/batch-2.md:6881: trailing whitespace.
+   137	
.oracle/checkins/batch-2.md:6887: trailing whitespace.
+   143	
.oracle/checkins/batch-2.md:6890: trailing whitespace.
+   146	
.oracle/checkins/batch-2.md:6891: trailing whitespace.
+   147	
.oracle/checkins/batch-2.md:6901: trailing whitespace.
+   157	
.oracle/checkins/batch-2.md:6942: trailing whitespace.
+   297	
.oracle/checkins/batch-2.md:6943: trailing whitespace.
+   298	
.oracle/checkins/batch-2.md:6946: trailing whitespace.
+   301	
.oracle/checkins/batch-2.md:6964: trailing whitespace.
+   319	
.oracle/checkins/batch-2.md:6967: trailing whitespace.
+   322	
.oracle/checkins/batch-2.md:6970: trailing whitespace.
+   325	
.oracle/checkins/batch-2.md:6975: trailing whitespace.
+   330	
.oracle/checkins/batch-2.md:6979: trailing whitespace.
+   334	
.oracle/checkins/batch-2.md:6982: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:6989: trailing whitespace.
+     9	
.oracle/checkins/batch-2.md:6991: trailing whitespace.
+    11	
.oracle/checkins/batch-2.md:6995: trailing whitespace.
+    15	
.oracle/checkins/batch-2.md:6998: trailing whitespace.
+    18	
.oracle/checkins/batch-2.md:7006: trailing whitespace.
+    26	
.oracle/checkins/batch-2.md:7008: trailing whitespace.
+    28	
.oracle/checkins/batch-2.md:7009: trailing whitespace.
+    29	
.oracle/checkins/batch-2.md:7016: trailing whitespace.
+    36	
.oracle/checkins/batch-2.md:7017: trailing whitespace.
+    37	
.oracle/checkins/batch-2.md:7019: trailing whitespace.
+    39	
.oracle/checkins/batch-2.md:7020: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:7025: trailing whitespace.
+    45	
.oracle/checkins/batch-2.md:7026: trailing whitespace.
+    46	
.oracle/checkins/batch-2.md:7038: trailing whitespace.
+    58	
.oracle/checkins/batch-2.md:7039: trailing whitespace.
+    59	
.oracle/checkins/batch-2.md:7047: trailing whitespace.
+    67	
.oracle/checkins/batch-2.md:7048: trailing whitespace.
+    68	
.oracle/checkins/batch-2.md:7067: trailing whitespace.
+    87	
.oracle/checkins/batch-2.md:7068: trailing whitespace.
+    88	
.oracle/checkins/batch-2.md:7072: trailing whitespace.
+   352	
.oracle/checkins/batch-2.md:7073: trailing whitespace.
+   353	
.oracle/checkins/batch-2.md:7076: trailing whitespace.
+   356	
.oracle/checkins/batch-2.md:7082: trailing whitespace.
+   362	
.oracle/checkins/batch-2.md:7083: trailing whitespace.
+   363	
.oracle/checkins/batch-2.md:7086: trailing whitespace.
+   366	
.oracle/checkins/batch-2.md:7090: trailing whitespace.
+   370	
.oracle/checkins/batch-2.md:7091: trailing whitespace.
+   371	
.oracle/checkins/batch-2.md:7105: trailing whitespace.
+   385	
.oracle/checkins/batch-2.md:7106: trailing whitespace.
+   386	
.oracle/checkins/batch-2.md:7110: trailing whitespace.
+   390	
.oracle/checkins/batch-2.md:7116: trailing whitespace.
+   396	
.oracle/checkins/batch-2.md:7137: trailing whitespace.
+   417	
.oracle/checkins/batch-2.md:7141: trailing whitespace.
+   421	
.oracle/checkins/batch-2.md:7152: trailing whitespace.
+   432	
.oracle/checkins/batch-2.md:7169: trailing whitespace.
+   449	
.oracle/checkins/batch-2.md:7170: trailing whitespace.
+   450	
.oracle/checkins/batch-2.md:7174: trailing whitespace.
+   454	
.oracle/checkins/batch-2.md:7188: trailing whitespace.
+   468	
.oracle/checkins/batch-2.md:7245: trailing whitespace.
+   664	
.oracle/checkins/batch-2.md:7246: trailing whitespace.
+   665	
.oracle/checkins/batch-2.md:7250: trailing whitespace.
+   669	
.oracle/checkins/batch-2.md:7257: trailing whitespace.
+   676	
.oracle/checkins/batch-2.md:7280: trailing whitespace.
+   699	
.oracle/checkins/batch-2.md:7292: trailing whitespace.
+   711	
.oracle/checkins/batch-2.md:7307: trailing whitespace.
+   726	
.oracle/checkins/batch-2.md:7328: trailing whitespace.
+   747	
.oracle/checkins/batch-2.md:7329: trailing whitespace.
+   748	
.oracle/checkins/batch-2.md:7336: trailing whitespace.
+   755	
.oracle/checkins/batch-2.md:7337: trailing whitespace.
+   756	
.oracle/checkins/batch-2.md:7344: trailing whitespace.
+   763	
.oracle/checkins/batch-2.md:7345: trailing whitespace.
+   764	
.oracle/checkins/batch-2.md:7353: trailing whitespace.
+   772	
.oracle/checkins/batch-2.md:7354: trailing whitespace.
+   773	
.oracle/checkins/batch-2.md:7358: trailing whitespace.
+   777	
.oracle/checkins/batch-2.md:7368: trailing whitespace.
+   787	
.oracle/checkins/batch-2.md:7401: trailing whitespace.
+   820	
.oracle/checkins/batch-2.md:7416: trailing whitespace.
+   835	
.oracle/checkins/batch-2.md:7433: trailing whitespace.
+  1511	
.oracle/checkins/batch-2.md:7434: trailing whitespace.
+  1512	
.oracle/checkins/batch-2.md:7449: trailing whitespace.
+  1527	
.oracle/checkins/batch-2.md:7450: trailing whitespace.
+  1528	
.oracle/checkins/batch-2.md:7454: trailing whitespace.
+  1532	
.oracle/checkins/batch-2.md:7462: trailing whitespace.
+  1540	
.oracle/checkins/batch-2.md:7488: trailing whitespace.
+  1566	
.oracle/checkins/batch-2.md:7492: trailing whitespace.
+  1570	
.oracle/checkins/batch-2.md:7494: trailing whitespace.
+  1572	
.oracle/checkins/batch-2.md:7507: trailing whitespace.
+  1585	
.oracle/checkins/batch-2.md:7531: trailing whitespace.
+  1609	
.oracle/checkins/batch-2.md:7538: trailing whitespace.
+  1616	
.oracle/checkins/batch-2.md:7539: trailing whitespace.
+  1617	
.oracle/checkins/batch-2.md:7543: trailing whitespace.
+  1621	
.oracle/checkins/batch-2.md:7568: trailing whitespace.
+   516	
.oracle/checkins/batch-2.md:7572: trailing whitespace.
+   520	
.oracle/checkins/batch-2.md:7591: trailing whitespace.
+   539	
.oracle/checkins/batch-2.md:7624: trailing whitespace.
+   572	
.oracle/checkins/batch-2.md:7625: trailing whitespace.
+   573	
.oracle/checkins/batch-2.md:7660: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:7662: trailing whitespace.
+     4	
.oracle/checkins/batch-2.md:7670: trailing whitespace.
+    12	
.oracle/checkins/batch-2.md:7673: trailing whitespace.
+    15	
.oracle/checkins/batch-2.md:7682: trailing whitespace.
+    24	
.oracle/checkins/batch-2.md:7683: trailing whitespace.
+    25	
.oracle/checkins/batch-2.md:7698: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:7699: trailing whitespace.
+    41	
.oracle/checkins/batch-2.md:7707: trailing whitespace.
+    49	
.oracle/checkins/batch-2.md:7708: trailing whitespace.
+    50	
.oracle/checkins/batch-2.md:7719: trailing whitespace.
+    61	
.oracle/checkins/batch-2.md:7720: trailing whitespace.
+    62	
.oracle/checkins/batch-2.md:7740: trailing whitespace.
+    82	
.oracle/checkins/batch-2.md:7749: trailing whitespace.
+    91	
.oracle/checkins/batch-2.md:7750: trailing whitespace.
+    92	
.oracle/checkins/batch-2.md:7767: trailing whitespace.
+   109	
.oracle/checkins/batch-2.md:7768: trailing whitespace.
+   110	
.oracle/checkins/batch-2.md:7786: trailing whitespace.
+   128	
.oracle/checkins/batch-2.md:7787: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:7810: trailing whitespace.
+   152	
.oracle/checkins/batch-2.md:7811: trailing whitespace.
+   153	
.oracle/checkins/batch-2.md:7850: trailing whitespace.
+   192	
.oracle/checkins/batch-2.md:7851: trailing whitespace.
+   193	
.oracle/checkins/batch-2.md:7860: trailing whitespace.
+   202	
.oracle/checkins/batch-2.md:7861: trailing whitespace.
+   203	
.oracle/checkins/batch-2.md:7881: trailing whitespace.
+   223	
.oracle/checkins/batch-2.md:7882: trailing whitespace.
+   224	
.oracle/checkins/batch-2.md:7898: trailing whitespace.
+   240	
.oracle/checkins/batch-2.md:7899: trailing whitespace.
+   241	
.oracle/checkins/batch-2.md:7902: trailing whitespace.
+   244	
.oracle/checkins/batch-2.md:7903: trailing whitespace.
+   245	
.oracle/checkins/batch-2.md:7911: trailing whitespace.
+   253	
.oracle/checkins/batch-2.md:7912: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:7924: trailing whitespace.
+   266	
.oracle/checkins/batch-2.md:7925: trailing whitespace.
+   267	
.oracle/checkins/batch-2.md:7928: trailing whitespace.
+   270	
.oracle/checkins/batch-2.md:7929: trailing whitespace.
+   271	
.oracle/checkins/batch-2.md:7948: trailing whitespace.
+   290	
.oracle/checkins/batch-2.md:7949: trailing whitespace.
+   291	
.oracle/checkins/batch-2.md:7987: trailing whitespace.
+   329	
.oracle/checkins/batch-2.md:8014: trailing whitespace.
+   356	
.oracle/checkins/batch-2.md:8015: trailing whitespace.
+   357	
.oracle/checkins/batch-2.md:8046: trailing whitespace.
+   388	
.oracle/checkins/batch-2.md:8047: trailing whitespace.
+   389	
.oracle/checkins/batch-2.md:8094: trailing whitespace.
+   436	
.oracle/checkins/batch-2.md:8110: trailing whitespace.
+   452	
.oracle/checkins/batch-2.md:8111: trailing whitespace.
+   453	
.oracle/checkins/batch-2.md:8132: trailing whitespace.
+   474	
.oracle/checkins/batch-2.md:8157: trailing whitespace.
+   499	
.oracle/checkins/batch-2.md:8158: trailing whitespace.
+   500	
.oracle/checkins/batch-2.md:8185: trailing whitespace.
+   527	
.oracle/checkins/batch-2.md:8186: trailing whitespace.
+   528	
.oracle/checkins/batch-2.md:8211: trailing whitespace.
+   553	
.oracle/checkins/batch-2.md:8212: trailing whitespace.
+   554	
.oracle/checkins/batch-2.md:8252: trailing whitespace.
+   594	
.oracle/checkins/batch-2.md:8253: trailing whitespace.
+   595	
.oracle/checkins/batch-2.md:8280: trailing whitespace.
+   622	
.oracle/checkins/batch-2.md:8281: trailing whitespace.
+   623	
.oracle/checkins/batch-2.md:8289: trailing whitespace.
+   631	
.oracle/checkins/batch-2.md:8295: trailing whitespace.
+   637	
.oracle/checkins/batch-2.md:8302: trailing whitespace.
+   644	
.oracle/checkins/batch-2.md:8321: trailing whitespace.
+   663	
.oracle/checkins/batch-2.md:8331: trailing whitespace.
+   673	
.oracle/checkins/batch-2.md:8352: trailing whitespace.
+   694	
.oracle/checkins/batch-2.md:8353: trailing whitespace.
+   695	
.oracle/checkins/batch-2.md:8417: trailing whitespace.
+   132	
.oracle/checkins/batch-2.md:8424: trailing whitespace.
+   139	
.oracle/checkins/batch-2.md:8425: trailing whitespace.
+   140	
.oracle/checkins/batch-2.md:8428: trailing whitespace.
+   143	
.oracle/checkins/batch-2.md:8435: trailing whitespace.
+   150	
.oracle/checkins/batch-2.md:8436: trailing whitespace.
+   151	
.oracle/checkins/batch-2.md:8443: trailing whitespace.
+   158	
.oracle/checkins/batch-2.md:8450: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:8451: trailing whitespace.
+   166	
.oracle/checkins/batch-2.md:8461: trailing whitespace.
+   176	
.oracle/checkins/batch-2.md:8468: trailing whitespace.
+   183	
.oracle/checkins/batch-2.md:8469: trailing whitespace.
+   184	
.oracle/checkins/batch-2.md:8473: trailing whitespace.
+   188	
.oracle/checkins/batch-2.md:8480: trailing whitespace.
+   195	
.oracle/checkins/batch-2.md:8481: trailing whitespace.
+   196	
.oracle/checkins/batch-2.md:8506: trailing whitespace.
+   221	
.oracle/checkins/batch-2.md:8513: trailing whitespace.
+   228	
.oracle/checkins/batch-2.md:8514: trailing whitespace.
+   229	
.oracle/checkins/batch-2.md:8518: trailing whitespace.
+   233	
.oracle/checkins/batch-2.md:8525: trailing whitespace.
+   240	
.oracle/checkins/batch-2.md:8526: trailing whitespace.
+   241	
.oracle/checkins/batch-2.md:8536: trailing whitespace.
+   251	
.oracle/checkins/batch-2.md:8543: trailing whitespace.
+   258	
.oracle/checkins/batch-2.md:8544: trailing whitespace.
+   259	
.oracle/checkins/batch-2.md:8554: trailing whitespace.
+   269	
.oracle/checkins/batch-2.md:8561: trailing whitespace.
+   276	
.oracle/checkins/batch-2.md:8562: trailing whitespace.
+   277	
.oracle/checkins/batch-2.md:8672: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:8676: trailing whitespace.
+     6	
.oracle/checkins/batch-2.md:8678: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:8687: trailing whitespace.
+    17	
.oracle/checkins/batch-2.md:8689: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:8691: trailing whitespace.
+    21	
.oracle/checkins/batch-2.md:8692: trailing whitespace.
+    22	
.oracle/checkins/batch-2.md:8696: trailing whitespace.
+    26	
.oracle/checkins/batch-2.md:8697: trailing whitespace.
+    27	
.oracle/checkins/batch-2.md:8701: trailing whitespace.
+    31	
.oracle/checkins/batch-2.md:8704: trailing whitespace.
+    34	
.oracle/checkins/batch-2.md:8710: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:8712: trailing whitespace.
+    42	
.oracle/checkins/batch-2.md:8729: trailing whitespace.
+    59	
.oracle/checkins/batch-2.md:8733: trailing whitespace.
+    63	
.oracle/checkins/batch-2.md:8735: trailing whitespace.
+    65	
.oracle/checkins/batch-2.md:8739: trailing whitespace.
+    69	
.oracle/checkins/batch-2.md:8741: trailing whitespace.
+    71	
.oracle/checkins/batch-2.md:8749: trailing whitespace.
+    79	
.oracle/checkins/batch-2.md:8755: trailing whitespace.
+    85	
.oracle/checkins/batch-2.md:8756: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:8759: trailing whitespace.
+    89	
.oracle/checkins/batch-2.md:8760: trailing whitespace.
+    90	
.oracle/checkins/batch-2.md:8763: trailing whitespace.
+    93	
.oracle/checkins/batch-2.md:8776: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:8777: trailing whitespace.
+   107	
.oracle/checkins/batch-2.md:8788: trailing whitespace.
+   118	
.oracle/checkins/batch-2.md:8789: trailing whitespace.
+   119	
.oracle/checkins/batch-2.md:8794: trailing whitespace.
+   124	
.oracle/checkins/batch-2.md:8795: trailing whitespace.
+   125	
.oracle/checkins/batch-2.md:8802: trailing whitespace.
+   132	
.oracle/checkins/batch-2.md:8803: trailing whitespace.
+   133	
.oracle/checkins/batch-2.md:8820: trailing whitespace.
+   150	
.oracle/checkins/batch-2.md:8821: trailing whitespace.
+   151	
.oracle/checkins/batch-2.md:8824: trailing whitespace.
+   154	
.oracle/checkins/batch-2.md:8830: trailing whitespace.
+   160	
.oracle/checkins/batch-2.md:8835: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:8839: trailing whitespace.
+   169	
.oracle/checkins/batch-2.md:8856: trailing whitespace.
+   186	
.oracle/checkins/batch-2.md:8859: trailing whitespace.
+   189	
.oracle/checkins/batch-2.md:8865: trailing whitespace.
+   195	
.oracle/checkins/batch-2.md:8873: trailing whitespace.
+   203	
.oracle/checkins/batch-2.md:8881: trailing whitespace.
+   211	
.oracle/checkins/batch-2.md:8887: trailing whitespace.
+   217	
.oracle/checkins/batch-2.md:8896: trailing whitespace.
+   226	
.oracle/checkins/batch-2.md:8898: trailing whitespace.
+   228	
.oracle/checkins/batch-2.md:8899: trailing whitespace.
+   229	
.oracle/checkins/batch-2.md:8911: trailing whitespace.
+   241	
.oracle/checkins/batch-2.md:8941: trailing whitespace.
+   271	
.oracle/checkins/batch-2.md:8950: trailing whitespace.
+   280	
.oracle/checkins/batch-2.md:8951: trailing whitespace.
+   281	
.oracle/checkins/batch-2.md:8958: trailing whitespace.
+   288	
.oracle/checkins/batch-2.md:8963: trailing whitespace.
+   293	
.oracle/checkins/batch-2.md:8964: trailing whitespace.
+   294	
.oracle/checkins/batch-2.md:8971: trailing whitespace.
+   301	
.oracle/checkins/batch-2.md:8977: trailing whitespace.
+   307	
.oracle/checkins/batch-2.md:8979: trailing whitespace.
+   309	
.oracle/checkins/batch-2.md:8980: trailing whitespace.
+   310	
.oracle/checkins/batch-2.md:8984: trailing whitespace.
+   314	
.oracle/checkins/batch-2.md:8985: trailing whitespace.
+   315	
.oracle/checkins/batch-2.md:8993: trailing whitespace.
+   323	
.oracle/checkins/batch-2.md:9023: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9025: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9027: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9044: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9235: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9258: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9268: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9300: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9329: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9330: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:9337: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:9341: trailing whitespace.
+     6	
.oracle/checkins/batch-2.md:9343: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:9357: trailing whitespace.
+    22	
.oracle/checkins/batch-2.md:9359: trailing whitespace.
+    24	
.oracle/checkins/batch-2.md:9372: trailing whitespace.
+    37	
.oracle/checkins/batch-2.md:9373: trailing whitespace.
+    38	
.oracle/checkins/batch-2.md:9376: trailing whitespace.
+    41	
.oracle/checkins/batch-2.md:9404: trailing whitespace.
+    69	
.oracle/checkins/batch-2.md:9405: trailing whitespace.
+    70	
.oracle/checkins/batch-2.md:9408: trailing whitespace.
+    73	
.oracle/checkins/batch-2.md:9414: trailing whitespace.
+    79	
.oracle/checkins/batch-2.md:9433: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:9448: trailing whitespace.
+   113	
.oracle/checkins/batch-2.md:9455: trailing whitespace.
+   120	
.oracle/checkins/batch-2.md:9461: trailing whitespace.
+   126	
.oracle/checkins/batch-2.md:9479: trailing whitespace.
+   144	
.oracle/checkins/batch-2.md:9495: trailing whitespace.
+   160	
.oracle/checkins/batch-2.md:9506: trailing whitespace.
+   171	
.oracle/checkins/batch-2.md:9537: trailing whitespace.
+   202	
.oracle/checkins/batch-2.md:9572: trailing whitespace.
+   237	
.oracle/checkins/batch-2.md:9576: trailing whitespace.
+   241	
.oracle/checkins/batch-2.md:9583: trailing whitespace.
+   248	
.oracle/checkins/batch-2.md:9595: trailing whitespace.
+   260	
.oracle/checkins/batch-2.md:9596: trailing whitespace.
+   260	
.oracle/checkins/batch-2.md:9597: trailing whitespace.
+   261	
.oracle/checkins/batch-2.md:9604: trailing whitespace.
+   268	
.oracle/checkins/batch-2.md:9605: trailing whitespace.
+   269	
.oracle/checkins/batch-2.md:9621: trailing whitespace.
+   285	
.oracle/checkins/batch-2.md:9622: trailing whitespace.
+   286	
.oracle/checkins/batch-2.md:9653: trailing whitespace.
+   317	
.oracle/checkins/batch-2.md:9654: trailing whitespace.
+   318	
.oracle/checkins/batch-2.md:9671: trailing whitespace.
+   335	
.oracle/checkins/batch-2.md:9672: trailing whitespace.
+   336	
.oracle/checkins/batch-2.md:9675: trailing whitespace.
+   339	
.oracle/checkins/batch-2.md:9676: trailing whitespace.
+   340	
.oracle/checkins/batch-2.md:9682: trailing whitespace.
+   346	
.oracle/checkins/batch-2.md:9683: trailing whitespace.
+   347	
.oracle/checkins/batch-2.md:9719: trailing whitespace.
+   383	
.oracle/checkins/batch-2.md:9728: trailing whitespace.
+   392	
.oracle/checkins/batch-2.md:9729: trailing whitespace.
+   393	
.oracle/checkins/batch-2.md:9736: trailing whitespace.
+   400	
.oracle/checkins/batch-2.md:9737: trailing whitespace.
+   401	
.oracle/checkins/batch-2.md:9754: trailing whitespace.
+   418	
.oracle/checkins/batch-2.md:9755: trailing whitespace.
+   419	
.oracle/checkins/batch-2.md:9772: trailing whitespace.
+   436	
.oracle/checkins/batch-2.md:9773: trailing whitespace.
+   437	
.oracle/checkins/batch-2.md:9786: trailing whitespace.
+   450	
.oracle/checkins/batch-2.md:9787: trailing whitespace.
+   451	
.oracle/checkins/batch-2.md:9792: trailing whitespace.
+   456	
.oracle/checkins/batch-2.md:9800: trailing whitespace.
+   464	
.oracle/checkins/batch-2.md:9803: trailing whitespace.
+   467	
.oracle/checkins/batch-2.md:9807: trailing whitespace.
+   471	
.oracle/checkins/batch-2.md:9820: trailing whitespace.
+   484	
.oracle/checkins/batch-2.md:9823: trailing whitespace.
+   487	
.oracle/checkins/batch-2.md:9826: trailing whitespace.
+   490	
.oracle/checkins/batch-2.md:9827: trailing whitespace.
+   491	
.oracle/checkins/batch-2.md:9832: trailing whitespace.
+   496	
.oracle/checkins/batch-2.md:9842: trailing whitespace.
+   506	
.oracle/checkins/batch-2.md:9843: trailing whitespace.
+   507	
.oracle/checkins/batch-2.md:9850: trailing whitespace.
+   514	
.oracle/checkins/batch-2.md:9851: trailing whitespace.
+   515	
.oracle/checkins/batch-2.md:9862: trailing whitespace.
+   526	
.oracle/checkins/batch-2.md:9863: trailing whitespace.
+   527	
.oracle/checkins/batch-2.md:9882: trailing whitespace.
+   546	
.oracle/checkins/batch-2.md:9883: trailing whitespace.
+   547	
.oracle/checkins/batch-2.md:9894: trailing whitespace.
+   558	
.oracle/checkins/batch-2.md:9895: trailing whitespace.
+   559	
.oracle/checkins/batch-2.md:9949: trailing whitespace.
+   612	
.oracle/checkins/batch-2.md:9950: trailing whitespace.
+   613	
.oracle/checkins/batch-2.md:9975: trailing whitespace.
+   638	
.oracle/checkins/batch-2.md:9983: trailing whitespace.
+   646	
.oracle/checkins/batch-2.md:9988: trailing whitespace.
+   651	
.oracle/checkins/batch-2.md:10015: trailing whitespace.
+   678	
.oracle/checkins/batch-2.md:10016: trailing whitespace.
+   679	
.oracle/checkins/batch-2.md:10035: trailing whitespace.
+   698	
.oracle/checkins/batch-2.md:10036: trailing whitespace.
+   699	
.oracle/checkins/batch-2.md:10043: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:10045: trailing whitespace.
+     4	
.oracle/checkins/batch-2.md:10049: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:10088: trailing whitespace.
+    47	
.oracle/checkins/batch-2.md:10109: trailing whitespace.
+    68	
.oracle/checkins/batch-2.md:10127: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:10132: trailing whitespace.
+    91	
.oracle/checkins/batch-2.md:10133: trailing whitespace.
+    92	
.oracle/checkins/batch-2.md:10136: trailing whitespace.
+    95	
.oracle/checkins/batch-2.md:10137: trailing whitespace.
+    96	
.oracle/checkins/batch-2.md:10147: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:10152: trailing whitespace.
+   111	
.oracle/checkins/batch-2.md:10161: trailing whitespace.
+   120	
.oracle/checkins/batch-2.md:10167: trailing whitespace.
+   126	
.oracle/checkins/batch-2.md:10170: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:10177: trailing whitespace.
+   136	
.oracle/checkins/batch-2.md:10178: trailing whitespace.
+   137	
.oracle/checkins/batch-2.md:10190: trailing whitespace.
+   149	
.oracle/checkins/batch-2.md:10191: trailing whitespace.
+   150	
.oracle/checkins/batch-2.md:10194: trailing whitespace.
+   153	
.oracle/checkins/batch-2.md:10195: trailing whitespace.
+   154	
.oracle/checkins/batch-2.md:10210: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:10219: trailing whitespace.
+    11	
.oracle/checkins/batch-2.md:10221: trailing whitespace.
+    13	
.oracle/checkins/batch-2.md:10231: trailing whitespace.
+    23	
.oracle/checkins/batch-2.md:10232: trailing whitespace.
+    24	
.oracle/checkins/batch-2.md:10237: trailing whitespace.
+    29	
.oracle/checkins/batch-2.md:10238: trailing whitespace.
+    30	
.oracle/checkins/batch-2.md:10241: trailing whitespace.
+    33	
.oracle/checkins/batch-2.md:10242: trailing whitespace.
+    34	
.oracle/checkins/batch-2.md:10247: trailing whitespace.
+    39	
.oracle/checkins/batch-2.md:10248: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:10271: trailing whitespace.
+    63	
.oracle/checkins/batch-2.md:10272: trailing whitespace.
+    64	
.oracle/checkins/batch-2.md:10282: trailing whitespace.
+    74	
.oracle/checkins/batch-2.md:10283: trailing whitespace.
+    75	
.oracle/checkins/batch-2.md:10297: trailing whitespace.
+    89	
.oracle/checkins/batch-2.md:10298: trailing whitespace.
+    90	
.oracle/checkins/batch-2.md:10304: trailing whitespace.
+    96	
.oracle/checkins/batch-2.md:10308: trailing whitespace.
+   100	
.oracle/checkins/batch-2.md:10309: trailing whitespace.
+   101	
.oracle/checkins/batch-2.md:10331: trailing whitespace.
+   123	
.oracle/checkins/batch-2.md:10333: trailing whitespace.
+   125	
.oracle/checkins/batch-2.md:10334: trailing whitespace.
+   126	
.oracle/checkins/batch-2.md:10337: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:10347: trailing whitespace.
+   139	
.oracle/checkins/batch-2.md:10350: trailing whitespace.
+   142	
.oracle/checkins/batch-2.md:10351: trailing whitespace.
+   143	
.oracle/checkins/batch-2.md:10363: trailing whitespace.
+   155	
.oracle/checkins/batch-2.md:10369: trailing whitespace.
+   161	
.oracle/checkins/batch-2.md:10370: trailing whitespace.
+   162	
.oracle/checkins/batch-2.md:10373: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:10376: trailing whitespace.
+   168	
.oracle/checkins/batch-2.md:10385: trailing whitespace.
+   177	
.oracle/checkins/batch-2.md:10386: trailing whitespace.
+   178	
.oracle/checkins/batch-2.md:10389: trailing whitespace.
+   181	
.oracle/checkins/batch-2.md:10396: trailing whitespace.
+   188	
.oracle/checkins/batch-2.md:10402: trailing whitespace.
+   194	
.oracle/checkins/batch-2.md:10411: trailing whitespace.
+   203	
.oracle/checkins/batch-2.md:10412: trailing whitespace.
+   204	
.oracle/checkins/batch-2.md:10416: trailing whitespace.
+   208	
.oracle/checkins/batch-2.md:10419: trailing whitespace.
+   211	
.oracle/checkins/batch-2.md:10420: trailing whitespace.
+   212	
.oracle/checkins/batch-2.md:10424: trailing whitespace.
+   216	
.oracle/checkins/batch-2.md:10427: trailing whitespace.
+   219	
.oracle/checkins/batch-2.md:10428: trailing whitespace.
+   220	
.oracle/checkins/batch-2.md:10432: trailing whitespace.
+   224	
.oracle/checkins/batch-2.md:10435: trailing whitespace.
+   227	
.oracle/checkins/batch-2.md:10439: trailing whitespace.
+   231	
.oracle/checkins/batch-2.md:10440: trailing whitespace.
+   232	
.oracle/checkins/batch-2.md:10447: trailing whitespace.
+   239	
.oracle/checkins/batch-2.md:10457: trailing whitespace.
+   249	
.oracle/checkins/batch-2.md:10462: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:10463: trailing whitespace.
+   255	
.oracle/checkins/batch-2.md:10469: trailing whitespace.
+   261	
.oracle/checkins/batch-2.md:10483: trailing whitespace.
+   275	
.oracle/checkins/batch-2.md:10617: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:10623: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:10625: trailing whitespace.
+    10	
.oracle/checkins/batch-2.md:10645: trailing whitespace.
+    30	
.oracle/checkins/batch-2.md:10649: trailing whitespace.
+    34	
.oracle/checkins/batch-2.md:10650: trailing whitespace.
+    35	
.oracle/checkins/batch-2.md:10652: trailing whitespace.
+    37	
.oracle/checkins/batch-2.md:10653: trailing whitespace.
+    38	
.oracle/checkins/batch-2.md:10657: trailing whitespace.
+    42	
.oracle/checkins/batch-2.md:10665: trailing whitespace.
+    50	
.oracle/checkins/batch-2.md:10669: trailing whitespace.
+    54	
.oracle/checkins/batch-2.md:10671: trailing whitespace.
+    56	
.oracle/checkins/batch-2.md:10672: trailing whitespace.
+    57	
.oracle/checkins/batch-2.md:10675: trailing whitespace.
+    60	
.oracle/checkins/batch-2.md:10682: trailing whitespace.
+    67	
.oracle/checkins/batch-2.md:10683: trailing whitespace.
+    68	
.oracle/checkins/batch-2.md:10687: trailing whitespace.
+    72	
.oracle/checkins/batch-2.md:10688: trailing whitespace.
+    73	
.oracle/checkins/batch-2.md:10695: trailing whitespace.
+    80	
.oracle/checkins/batch-2.md:10696: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:10699: trailing whitespace.
+    84	
.oracle/checkins/batch-2.md:10706: trailing whitespace.
+    91	
.oracle/checkins/batch-2.md:10713: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:10722: trailing whitespace.
+   107	
.oracle/checkins/batch-2.md:10723: trailing whitespace.
+   108	
.oracle/checkins/batch-2.md:10731: trailing whitespace.
+   116	
.oracle/checkins/batch-2.md:10732: trailing whitespace.
+   117	
.oracle/checkins/batch-2.md:10738: trailing whitespace.
+   123	
.oracle/checkins/batch-2.md:10739: trailing whitespace.
+   124	
.oracle/checkins/batch-2.md:10742: trailing whitespace.
+   127	
.oracle/checkins/batch-2.md:10779: trailing whitespace.
+   164	
.oracle/checkins/batch-2.md:10780: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:10783: trailing whitespace.
+   168	
.oracle/checkins/batch-2.md:10788: trailing whitespace.
+   173	
.oracle/checkins/batch-2.md:10802: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:10810: trailing whitespace.
+   195	
.oracle/checkins/batch-2.md:10831: trailing whitespace.
+   216	
.oracle/checkins/batch-2.md:10835: trailing whitespace.
+   220	
.oracle/checkins/batch-2.md:10873: trailing whitespace.
+   258	
.oracle/checkins/batch-2.md:10884: trailing whitespace.
+   268	
.oracle/checkins/batch-2.md:10914: trailing whitespace.
+   298	
.oracle/checkins/batch-2.md:10963: trailing whitespace.
+   347	
.oracle/checkins/batch-2.md:10991: trailing whitespace.
+   375	
.oracle/checkins/batch-2.md:11013: trailing whitespace.
+   397	
.oracle/checkins/batch-2.md:11043: trailing whitespace.
+   427	
.oracle/checkins/batch-2.md:11065: trailing whitespace.
+   449	
.oracle/checkins/batch-2.md:11071: trailing whitespace.
+   455	
.oracle/checkins/batch-2.md:11089: trailing whitespace.
+   473	
.oracle/checkins/batch-2.md:11098: trailing whitespace.
+   482	
.oracle/checkins/batch-2.md:11103: trailing whitespace.
+   487	
.oracle/checkins/batch-2.md:11106: trailing whitespace.
+   490	
.oracle/checkins/batch-2.md:11107: trailing whitespace.
+   491	
.oracle/checkins/batch-2.md:11109: trailing whitespace.
+   493	
.oracle/checkins/batch-2.md:11110: trailing whitespace.
+   494	
.oracle/checkins/batch-2.md:11113: trailing whitespace.
+   497	
.oracle/checkins/batch-2.md:11116: trailing whitespace.
+   500	
.oracle/checkins/batch-2.md:11123: trailing whitespace.
+   507	
.oracle/checkins/batch-2.md:11136: trailing whitespace.
+   520	
.oracle/checkins/batch-2.md:11137: trailing whitespace.
+   520	
.oracle/checkins/batch-2.md:11161: trailing whitespace.
+   544	
.oracle/checkins/batch-2.md:11177: trailing whitespace.
+   560	
.oracle/checkins/batch-2.md:11196: trailing whitespace.
+   579	
.oracle/checkins/batch-2.md:11204: trailing whitespace.
+   587	
.oracle/checkins/batch-2.md:11223: trailing whitespace.
+   606	
.oracle/checkins/batch-2.md:11224: trailing whitespace.
+   607	
.oracle/checkins/batch-2.md:11228: trailing whitespace.
+   611	
.oracle/checkins/batch-2.md:11229: trailing whitespace.
+   612	
.oracle/checkins/batch-2.md:11232: trailing whitespace.
+   615	
.oracle/checkins/batch-2.md:11235: trailing whitespace.
+   618	
.oracle/checkins/batch-2.md:11243: trailing whitespace.
+   626	
.oracle/checkins/batch-2.md:11249: trailing whitespace.
+   632	
.oracle/checkins/batch-2.md:11253: trailing whitespace.
+   636	
.oracle/checkins/batch-2.md:11259: trailing whitespace.
+   642	
.oracle/checkins/batch-2.md:11282: trailing whitespace.
+   665	
.oracle/checkins/batch-2.md:11291: trailing whitespace.
+   674	
.oracle/checkins/batch-2.md:11301: trailing whitespace.
+   684	
.oracle/checkins/batch-2.md:11331: trailing whitespace.
+   714	
.oracle/checkins/batch-2.md:11334: trailing whitespace.
+   717	
.oracle/checkins/batch-2.md:11337: trailing whitespace.
+   720	
.oracle/checkins/batch-2.md:11338: trailing whitespace.
+   721	
.oracle/checkins/batch-2.md:11460: trailing whitespace.
+   313	
.oracle/checkins/batch-2.md:11464: trailing whitespace.
+   317	
.oracle/checkins/batch-2.md:11465: trailing whitespace.
+   318	
.oracle/checkins/batch-2.md:11474: trailing whitespace.
+   327	
.oracle/checkins/batch-2.md:11477: trailing whitespace.
+   330	
.oracle/checkins/batch-2.md:11480: trailing whitespace.
+   333	
.oracle/checkins/batch-2.md:11483: trailing whitespace.
+   336	
.oracle/checkins/batch-2.md:11486: trailing whitespace.
+   339	
.oracle/checkins/batch-2.md:11489: trailing whitespace.
+   342	
.oracle/checkins/batch-2.md:11495: trailing whitespace.
+   348	
.oracle/checkins/batch-2.md:11496: trailing whitespace.
+   349	
.oracle/checkins/batch-2.md:11504: trailing whitespace.
+   357	
.oracle/checkins/batch-2.md:11508: trailing whitespace.
+   361	
.oracle/checkins/batch-2.md:11511: trailing whitespace.
+   364	
.oracle/checkins/batch-2.md:11517: trailing whitespace.
+   370	
.oracle/checkins/batch-2.md:11525: trailing whitespace.
+   378	
.oracle/checkins/batch-2.md:11526: trailing whitespace.
+   379	
.oracle/checkins/batch-2.md:11548: trailing whitespace.
+   401	
.oracle/checkins/batch-2.md:11549: trailing whitespace.
+   402	
.oracle/checkins/batch-2.md:11559: trailing whitespace.
+   412	
.oracle/checkins/batch-2.md:11566: trailing whitespace.
+   419	
.oracle/checkins/batch-2.md:11567: trailing whitespace.
+   420	
.oracle/checkins/batch-2.md:11576: trailing whitespace.
+   429	
.oracle/checkins/batch-2.md:11581: trailing whitespace.
+   434	
.oracle/checkins/batch-2.md:11584: trailing whitespace.
+   437	
.oracle/checkins/batch-2.md:11585: trailing whitespace.
+   438	
.oracle/checkins/batch-2.md:11596: trailing whitespace.
+   449	
.oracle/checkins/batch-2.md:11601: trailing whitespace.
+   454	
.oracle/checkins/batch-2.md:11605: trailing whitespace.
+   458	
.oracle/checkins/batch-2.md:11608: trailing whitespace.
+   461	
.oracle/checkins/batch-2.md:11609: trailing whitespace.
+   462	
.oracle/checkins/batch-2.md:11617: trailing whitespace.
+   470	
.oracle/checkins/batch-2.md:11628: trailing whitespace.
+   481	
.oracle/checkins/batch-2.md:11629: trailing whitespace.
+   482	
.oracle/checkins/batch-2.md:11640: trailing whitespace.
+   493	
.oracle/checkins/batch-2.md:11643: trailing whitespace.
+   496	
.oracle/checkins/batch-2.md:11650: trailing whitespace.
+   503	
.oracle/checkins/batch-2.md:11651: trailing whitespace.
+   504	
.oracle/checkins/batch-2.md:11665: trailing whitespace.
+   518	
.oracle/checkins/batch-2.md:11672: trailing whitespace.
+   525	
.oracle/checkins/batch-2.md:11691: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11693: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11695: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11697: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11698: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11718: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11737: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11738: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11934: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11935: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11941: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11942: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11981: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11982: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:11995: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12016: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12017: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12020: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12021: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12030: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12031: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12060: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12061: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12066: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12067: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12076: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12088: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12089: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12110: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12111: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12137: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12138: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12162: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12172: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12184: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12219: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12249: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12342: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12343: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12358: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12359: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12434: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12435: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12474: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12475: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12485: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12548: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12570: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12571: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12575: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12576: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12597: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12598: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12601: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12602: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12643: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12644: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12655: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12656: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12663: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12664: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12761: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12762: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12767: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12768: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12781: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12782: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12794: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12795: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12808: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12809: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12841: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12920: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12959: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:12960: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13252: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13253: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13310: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13311: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13323: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13333: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13338: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13341: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13342: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13363: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13364: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13380: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13392: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13416: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13427: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13435: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13439: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13445: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13459: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13470: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13473: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13475: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13485: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13487: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13491: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13494: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13496: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13499: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13515: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13517: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13521: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13524: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13526: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13542: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13551: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13564: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13582: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13592: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13604: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13614: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13625: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13627: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13636: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13646: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13680: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13685: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13689: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13701: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13715: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13750: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13764: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13799: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13816: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13841: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13853: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13886: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13892: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13904: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13906: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13912: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13929: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13948: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13966: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13983: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:13989: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14007: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14024: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14035: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14043: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14046: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14068: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14074: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14080: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14089: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14099: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14105: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14112: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14119: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14156: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14170: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14171: trailing whitespace.
+ 
.oracle/checkins/batch-2.md:14492: trailing whitespace.
+     3	
.oracle/checkins/batch-2.md:14496: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:14502: trailing whitespace.
+    13	
.oracle/checkins/batch-2.md:14504: trailing whitespace.
+    15	
.oracle/checkins/batch-2.md:14506: trailing whitespace.
+    17	
.oracle/checkins/batch-2.md:14508: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:14511: trailing whitespace.
+    22	
.oracle/checkins/batch-2.md:14529: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:14530: trailing whitespace.
+    41	
.oracle/checkins/batch-2.md:14546: trailing whitespace.
+    57	
.oracle/checkins/batch-2.md:14547: trailing whitespace.
+    58	
.oracle/checkins/batch-2.md:14930: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:14934: trailing whitespace.
+     6	
.oracle/checkins/batch-2.md:14936: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:14943: trailing whitespace.
+    15	
.oracle/checkins/batch-2.md:14944: trailing whitespace.
+    16	
.oracle/checkins/batch-2.md:14947: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:14948: trailing whitespace.
+    20	
.oracle/checkins/batch-2.md:14962: trailing whitespace.
+    34	
.oracle/checkins/batch-2.md:14963: trailing whitespace.
+    35	
.oracle/checkins/batch-2.md:14966: trailing whitespace.
+    38	
.oracle/checkins/batch-2.md:14972: trailing whitespace.
+    44	
.oracle/checkins/batch-2.md:14989: trailing whitespace.
+    61	
.oracle/checkins/batch-2.md:14990: trailing whitespace.
+    62	
.oracle/checkins/batch-2.md:14994: trailing whitespace.
+    66	
.oracle/checkins/batch-2.md:15008: trailing whitespace.
+    80	
.oracle/checkins/batch-2.md:15009: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:15011: trailing whitespace.
+    83	
.oracle/checkins/batch-2.md:15014: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:15017: trailing whitespace.
+    89	
.oracle/checkins/batch-2.md:15022: trailing whitespace.
+    94	
.oracle/checkins/batch-2.md:15023: trailing whitespace.
+    95	
.oracle/checkins/batch-2.md:15026: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:15029: trailing whitespace.
+   101	
.oracle/checkins/batch-2.md:15034: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:15035: trailing whitespace.
+   107	
.oracle/checkins/batch-2.md:15038: trailing whitespace.
+   110	
.oracle/checkins/batch-2.md:15041: trailing whitespace.
+   113	
.oracle/checkins/batch-2.md:15058: trailing whitespace.
+   130	
.oracle/checkins/batch-2.md:15059: trailing whitespace.
+   131	
.oracle/checkins/batch-2.md:15062: trailing whitespace.
+   134	
.oracle/checkins/batch-2.md:15084: trailing whitespace.
+     3	
.oracle/checkins/batch-2.md:15087: trailing whitespace.
+     6	
.oracle/checkins/batch-2.md:15089: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:15095: trailing whitespace.
+    14	
.oracle/checkins/batch-2.md:15101: trailing whitespace.
+    20	
.oracle/checkins/batch-2.md:15103: trailing whitespace.
+    22	
.oracle/checkins/batch-2.md:15111: trailing whitespace.
+    30	
.oracle/checkins/batch-2.md:15114: trailing whitespace.
+    33	
.oracle/checkins/batch-2.md:15130: trailing whitespace.
+    49	
.oracle/checkins/batch-2.md:15134: trailing whitespace.
+    53	
.oracle/checkins/batch-2.md:15136: trailing whitespace.
+    55	
.oracle/checkins/batch-2.md:15138: trailing whitespace.
+    57	
.oracle/checkins/batch-2.md:15139: trailing whitespace.
+    58	
.oracle/checkins/batch-2.md:15143: trailing whitespace.
+    62	
.oracle/checkins/batch-2.md:15144: trailing whitespace.
+    63	
.oracle/checkins/batch-2.md:15147: trailing whitespace.
+    66	
.oracle/checkins/batch-2.md:15149: trailing whitespace.
+    68	
.oracle/checkins/batch-2.md:15154: trailing whitespace.
+    73	
.oracle/checkins/batch-2.md:15163: trailing whitespace.
+    82	
.oracle/checkins/batch-2.md:15172: trailing whitespace.
+    91	
.oracle/checkins/batch-2.md:15173: trailing whitespace.
+    92	
.oracle/checkins/batch-2.md:15180: trailing whitespace.
+    99	
.oracle/checkins/batch-2.md:15181: trailing whitespace.
+   100	
.oracle/checkins/batch-2.md:15185: trailing whitespace.
+   104	
.oracle/checkins/batch-2.md:15186: trailing whitespace.
+   105	
.oracle/checkins/batch-2.md:15198: trailing whitespace.
+   117	
.oracle/checkins/batch-2.md:15199: trailing whitespace.
+   118	
.oracle/checkins/batch-2.md:15224: trailing whitespace.
+   143	
.oracle/checkins/batch-2.md:15225: trailing whitespace.
+   144	
.oracle/checkins/batch-2.md:15246: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:15247: trailing whitespace.
+   166	
.oracle/checkins/batch-2.md:15250: trailing whitespace.
+   169	
.oracle/checkins/batch-2.md:15271: trailing whitespace.
+   190	
.oracle/checkins/batch-2.md:15272: trailing whitespace.
+   191	
.oracle/checkins/batch-2.md:15276: trailing whitespace.
+   195	
.oracle/checkins/batch-2.md:15277: trailing whitespace.
+   196	
.oracle/checkins/batch-2.md:15280: trailing whitespace.
+   199	
.oracle/checkins/batch-2.md:15281: trailing whitespace.
+   200	
.oracle/checkins/batch-2.md:15284: trailing whitespace.
+   203	
.oracle/checkins/batch-2.md:15285: trailing whitespace.
+   204	
.oracle/checkins/batch-2.md:15288: trailing whitespace.
+   207	
.oracle/checkins/batch-2.md:15289: trailing whitespace.
+   208	
.oracle/checkins/batch-2.md:15295: trailing whitespace.
+   214	
.oracle/checkins/batch-2.md:15296: trailing whitespace.
+   215	
.oracle/checkins/batch-2.md:15310: trailing whitespace.
+   228	
.oracle/checkins/batch-2.md:15311: trailing whitespace.
+   229	
.oracle/checkins/batch-2.md:15326: trailing whitespace.
+   244	
.oracle/checkins/batch-2.md:15327: trailing whitespace.
+   245	
.oracle/checkins/batch-2.md:15334: trailing whitespace.
+   252	
.oracle/checkins/batch-2.md:15335: trailing whitespace.
+   253	
.oracle/checkins/batch-2.md:15339: trailing whitespace.
+   257	
.oracle/checkins/batch-2.md:15340: trailing whitespace.
+   258	
.oracle/checkins/batch-2.md:15344: trailing whitespace.
+   262	
.oracle/checkins/batch-2.md:15345: trailing whitespace.
+   263	
.oracle/checkins/batch-2.md:15368: trailing whitespace.
+   286	
.oracle/checkins/batch-2.md:15369: trailing whitespace.
+   287	
.oracle/checkins/batch-2.md:15385: trailing whitespace.
+   303	
.oracle/checkins/batch-2.md:15386: trailing whitespace.
+   304	
.oracle/checkins/batch-2.md:15408: trailing whitespace.
+   326	
.oracle/checkins/batch-2.md:15418: trailing whitespace.
+   336	
.oracle/checkins/batch-2.md:15422: trailing whitespace.
+   340	
.oracle/checkins/batch-2.md:15423: trailing whitespace.
+   341	
.oracle/checkins/batch-2.md:15434: trailing whitespace.
+   352	
.oracle/checkins/batch-2.md:15437: trailing whitespace.
+   355	
.oracle/checkins/batch-2.md:15441: trailing whitespace.
+   359	
.oracle/checkins/batch-2.md:15450: trailing whitespace.
+   368	
.oracle/checkins/batch-2.md:15454: trailing whitespace.
+   372	
.oracle/checkins/batch-2.md:15458: trailing whitespace.
+   376	
.oracle/checkins/batch-2.md:15462: trailing whitespace.
+   380	
.oracle/checkins/batch-2.md:15466: trailing whitespace.
+   384	
.oracle/checkins/batch-2.md:15467: trailing whitespace.
+   385	
.oracle/checkins/batch-2.md:15471: trailing whitespace.
+   389	
.oracle/checkins/batch-2.md:15472: trailing whitespace.
+   390	
.oracle/checkins/batch-2.md:15475: trailing whitespace.
+   393	
.oracle/checkins/batch-2.md:15476: trailing whitespace.
+   394	
.oracle/checkins/batch-2.md:15489: trailing whitespace.
+   407	
.oracle/checkins/batch-2.md:15490: trailing whitespace.
+   408	
.oracle/checkins/batch-2.md:15509: trailing whitespace.
+   427	
.oracle/checkins/batch-2.md:15510: trailing whitespace.
+   428	
.oracle/checkins/batch-2.md:15525: trailing whitespace.
+   443	
.oracle/checkins/batch-2.md:15526: trailing whitespace.
+   444	
.oracle/checkins/batch-2.md:15540: trailing whitespace.
+   458	
.oracle/checkins/batch-2.md:15550: trailing whitespace.
+   467	
.oracle/checkins/batch-2.md:15553: trailing whitespace.
+   470	
.oracle/checkins/batch-2.md:15605: trailing whitespace.
+   522	
.oracle/checkins/batch-2.md:15606: trailing whitespace.
+   523	
.oracle/checkins/batch-2.md:15616: trailing whitespace.
+   533	
.oracle/checkins/batch-2.md:15629: trailing whitespace.
+   546	
.oracle/checkins/batch-2.md:15641: trailing whitespace.
+   558	
.oracle/checkins/batch-2.md:15642: trailing whitespace.
+   559	
.oracle/checkins/batch-2.md:15780: trailing whitespace.
+   120	
.oracle/checkins/batch-2.md:15781: trailing whitespace.
+   121	
.oracle/checkins/batch-2.md:15791: trailing whitespace.
+   131	
.oracle/checkins/batch-2.md:15792: trailing whitespace.
+   132	
.oracle/checkins/batch-2.md:15813: trailing whitespace.
+   153	
.oracle/checkins/batch-2.md:15814: trailing whitespace.
+   154	
.oracle/checkins/batch-2.md:15824: trailing whitespace.
+   164	
.oracle/checkins/batch-2.md:15830: trailing whitespace.
+   170	
.oracle/checkins/batch-2.md:15842: trailing whitespace.
+   182	
.oracle/checkins/batch-2.md:15843: trailing whitespace.
+   183	
.oracle/checkins/batch-2.md:15847: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:15848: trailing whitespace.
+   188	
.oracle/checkins/batch-2.md:15854: trailing whitespace.
+   194	
.oracle/checkins/batch-2.md:15864: trailing whitespace.
+   204	
.oracle/checkins/batch-2.md:15881: trailing whitespace.
+   221	
.oracle/checkins/batch-2.md:15891: trailing whitespace.
+   231	
.oracle/checkins/batch-2.md:15904: trailing whitespace.
+   244	
.oracle/checkins/batch-2.md:15909: trailing whitespace.
+   249	
.oracle/checkins/batch-2.md:15914: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:15916: trailing whitespace.
+   256	
.oracle/checkins/batch-2.md:15926: trailing whitespace.
+   266	
.oracle/checkins/batch-2.md:15927: trailing whitespace.
+   267	
.oracle/checkins/batch-2.md:15931: trailing whitespace.
+   271	
.oracle/checkins/batch-2.md:15932: trailing whitespace.
+   272	
.oracle/checkins/batch-2.md:15936: trailing whitespace.
+   276	
.oracle/checkins/batch-2.md:15939: trailing whitespace.
+   279	
.oracle/checkins/batch-2.md:15947: trailing whitespace.
+   287	
.oracle/checkins/batch-2.md:15948: trailing whitespace.
+   288	
.oracle/checkins/batch-2.md:15952: trailing whitespace.
+   292	
.oracle/checkins/batch-2.md:15961: trailing whitespace.
+   301	
.oracle/checkins/batch-2.md:15962: trailing whitespace.
+   302	
.oracle/checkins/batch-2.md:15971: trailing whitespace.
+   311	
.oracle/checkins/batch-2.md:15974: trailing whitespace.
+   314	
.oracle/checkins/batch-2.md:15975: trailing whitespace.
+   315	
.oracle/checkins/batch-2.md:15979: trailing whitespace.
+   319	
.oracle/checkins/batch-2.md:15980: trailing whitespace.
+   320	
.oracle/checkins/batch-2.md:15986: trailing whitespace.
+   326	
.oracle/checkins/batch-2.md:16369: trailing whitespace.
+     3	
.oracle/checkins/batch-2.md:16370: trailing whitespace.
+     4	
.oracle/checkins/batch-2.md:16376: trailing whitespace.
+    10	
.oracle/checkins/batch-2.md:16378: trailing whitespace.
+    12	
.oracle/checkins/batch-2.md:16380: trailing whitespace.
+    14	
.oracle/checkins/batch-2.md:16399: trailing whitespace.
+    33	
.oracle/checkins/batch-2.md:16403: trailing whitespace.
+    37	
.oracle/checkins/batch-2.md:16408: trailing whitespace.
+    42	
.oracle/checkins/batch-2.md:16411: trailing whitespace.
+    45	
.oracle/checkins/batch-2.md:16412: trailing whitespace.
+    46	
.oracle/checkins/batch-2.md:16415: trailing whitespace.
+    49	
.oracle/checkins/batch-2.md:16416: trailing whitespace.
+    50	
.oracle/checkins/batch-2.md:16419: trailing whitespace.
+    53	
.oracle/checkins/batch-2.md:16425: trailing whitespace.
+    59	
.oracle/checkins/batch-2.md:16429: trailing whitespace.
+    63	
.oracle/checkins/batch-2.md:16433: trailing whitespace.
+    67	
.oracle/checkins/batch-2.md:16438: trailing whitespace.
+    72	
.oracle/checkins/batch-2.md:16448: trailing whitespace.
+    82	
.oracle/checkins/batch-2.md:16463: trailing whitespace.
+    97	
.oracle/checkins/batch-2.md:16464: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:16466: trailing whitespace.
+   100	
.oracle/checkins/batch-2.md:16467: trailing whitespace.
+   101	
.oracle/checkins/batch-2.md:16471: trailing whitespace.
+   105	
.oracle/checkins/batch-2.md:16472: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:16475: trailing whitespace.
+   109	
.oracle/checkins/batch-2.md:16476: trailing whitespace.
+   110	
.oracle/checkins/batch-2.md:16483: trailing whitespace.
+   117	
.oracle/checkins/batch-2.md:16484: trailing whitespace.
+   118	
.oracle/checkins/batch-2.md:16489: trailing whitespace.
+   123	
.oracle/checkins/batch-2.md:16502: trailing whitespace.
+   136	
.oracle/checkins/batch-2.md:16509: trailing whitespace.
+   143	
.oracle/checkins/batch-2.md:16512: trailing whitespace.
+   146	
.oracle/checkins/batch-2.md:16515: trailing whitespace.
+   149	
.oracle/checkins/batch-2.md:16516: trailing whitespace.
+   150	
.oracle/checkins/batch-2.md:16522: trailing whitespace.
+   156	
.oracle/checkins/batch-2.md:16523: trailing whitespace.
+   157	
.oracle/checkins/batch-2.md:16526: trailing whitespace.
+   160	
.oracle/checkins/batch-2.md:16527: trailing whitespace.
+   161	
.oracle/checkins/batch-2.md:16530: trailing whitespace.
+   164	
.oracle/checkins/batch-2.md:16531: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:16537: trailing whitespace.
+   171	
.oracle/checkins/batch-2.md:16538: trailing whitespace.
+   172	
.oracle/checkins/batch-2.md:16548: trailing whitespace.
+   182	
.oracle/checkins/batch-2.md:16549: trailing whitespace.
+   183	
.oracle/checkins/batch-2.md:16552: trailing whitespace.
+   186	
.oracle/checkins/batch-2.md:16553: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:16556: trailing whitespace.
+   190	
.oracle/checkins/batch-2.md:16557: trailing whitespace.
+   191	
.oracle/checkins/batch-2.md:16567: trailing whitespace.
+   201	
.oracle/checkins/batch-2.md:16568: trailing whitespace.
+   202	
.oracle/checkins/batch-2.md:16574: trailing whitespace.
+   208	
.oracle/checkins/batch-2.md:16575: trailing whitespace.
+   209	
.oracle/checkins/batch-2.md:16582: trailing whitespace.
+   216	
.oracle/checkins/batch-2.md:16583: trailing whitespace.
+   217	
.oracle/checkins/batch-2.md:16588: trailing whitespace.
+   222	
.oracle/checkins/batch-2.md:16589: trailing whitespace.
+   223	
.oracle/checkins/batch-2.md:16595: trailing whitespace.
+   229	
.oracle/checkins/batch-2.md:16596: trailing whitespace.
+   230	
.oracle/checkins/batch-2.md:16600: trailing whitespace.
+   234	
.oracle/checkins/batch-2.md:16601: trailing whitespace.
+   235	
.oracle/checkins/batch-2.md:16615: trailing whitespace.
+   249	
.oracle/checkins/batch-2.md:16616: trailing whitespace.
+   250	
.oracle/checkins/batch-2.md:16628: trailing whitespace.
+   262	
.oracle/checkins/batch-2.md:16632: trailing whitespace.
+   266	
.oracle/checkins/batch-2.md:16649: trailing whitespace.
+   283	
.oracle/checkins/batch-2.md:16650: trailing whitespace.
+   284	
.oracle/checkins/batch-2.md:16670: trailing whitespace.
+   304	
.oracle/checkins/batch-2.md:16674: trailing whitespace.
+   308	
.oracle/checkins/batch-2.md:16710: trailing whitespace.
+   344	
.oracle/checkins/batch-2.md:16711: trailing whitespace.
+   345	
.oracle/checkins/batch-2.md:16725: trailing whitespace.
+   359	
.oracle/checkins/batch-2.md:16726: trailing whitespace.
+   360	
.oracle/checkins/batch-2.md:16774: trailing whitespace.
+   408	
.oracle/checkins/batch-2.md:16775: trailing whitespace.
+   409	
.oracle/checkins/batch-2.md:16796: trailing whitespace.
+   430	
.oracle/checkins/batch-2.md:16797: trailing whitespace.
+   431	
.oracle/checkins/batch-2.md:16810: trailing whitespace.
+   444	
.oracle/checkins/batch-2.md:16811: trailing whitespace.
+   445	
.oracle/checkins/batch-2.md:16821: trailing whitespace.
+   455	
.oracle/checkins/batch-2.md:16822: trailing whitespace.
+   456	
.oracle/checkins/batch-2.md:16852: trailing whitespace.
+   486	
.oracle/checkins/batch-2.md:16853: trailing whitespace.
+   487	
.oracle/checkins/batch-2.md:16869: trailing whitespace.
+   503	
.oracle/checkins/batch-2.md:16870: trailing whitespace.
+   504	
.oracle/checkins/batch-2.md:16879: trailing whitespace.
+     3	
.oracle/checkins/batch-2.md:16889: trailing whitespace.
+    13	
.oracle/checkins/batch-2.md:16895: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:16897: trailing whitespace.
+    21	
.oracle/checkins/batch-2.md:16914: trailing whitespace.
+    38	
.oracle/checkins/batch-2.md:16918: trailing whitespace.
+    42	
.oracle/checkins/batch-2.md:16923: trailing whitespace.
+    47	
.oracle/checkins/batch-2.md:16926: trailing whitespace.
+    50	
.oracle/checkins/batch-2.md:16927: trailing whitespace.
+    51	
.oracle/checkins/batch-2.md:16930: trailing whitespace.
+    54	
.oracle/checkins/batch-2.md:16931: trailing whitespace.
+    55	
.oracle/checkins/batch-2.md:16934: trailing whitespace.
+    58	
.oracle/checkins/batch-2.md:16940: trailing whitespace.
+    64	
.oracle/checkins/batch-2.md:16944: trailing whitespace.
+    68	
.oracle/checkins/batch-2.md:16948: trailing whitespace.
+    72	
.oracle/checkins/batch-2.md:16953: trailing whitespace.
+    77	
.oracle/checkins/batch-2.md:16963: trailing whitespace.
+    87	
.oracle/checkins/batch-2.md:16978: trailing whitespace.
+   102	
.oracle/checkins/batch-2.md:16979: trailing whitespace.
+   103	
.oracle/checkins/batch-2.md:16981: trailing whitespace.
+   105	
.oracle/checkins/batch-2.md:16982: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:16986: trailing whitespace.
+   110	
.oracle/checkins/batch-2.md:16987: trailing whitespace.
+   111	
.oracle/checkins/batch-2.md:16990: trailing whitespace.
+   114	
.oracle/checkins/batch-2.md:16991: trailing whitespace.
+   115	
.oracle/checkins/batch-2.md:16998: trailing whitespace.
+   122	
.oracle/checkins/batch-2.md:16999: trailing whitespace.
+   123	
.oracle/checkins/batch-2.md:17004: trailing whitespace.
+   128	
.oracle/checkins/batch-2.md:17017: trailing whitespace.
+   141	
.oracle/checkins/batch-2.md:17024: trailing whitespace.
+   148	
.oracle/checkins/batch-2.md:17027: trailing whitespace.
+   151	
.oracle/checkins/batch-2.md:17030: trailing whitespace.
+   154	
.oracle/checkins/batch-2.md:17031: trailing whitespace.
+   155	
.oracle/checkins/batch-2.md:17037: trailing whitespace.
+   161	
.oracle/checkins/batch-2.md:17038: trailing whitespace.
+   162	
.oracle/checkins/batch-2.md:17041: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:17042: trailing whitespace.
+   166	
.oracle/checkins/batch-2.md:17045: trailing whitespace.
+   169	
.oracle/checkins/batch-2.md:17046: trailing whitespace.
+   170	
.oracle/checkins/batch-2.md:17052: trailing whitespace.
+   176	
.oracle/checkins/batch-2.md:17053: trailing whitespace.
+   177	
.oracle/checkins/batch-2.md:17063: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:17064: trailing whitespace.
+   188	
.oracle/checkins/batch-2.md:17067: trailing whitespace.
+   191	
.oracle/checkins/batch-2.md:17068: trailing whitespace.
+   192	
.oracle/checkins/batch-2.md:17071: trailing whitespace.
+   195	
.oracle/checkins/batch-2.md:17072: trailing whitespace.
+   196	
.oracle/checkins/batch-2.md:17082: trailing whitespace.
+   206	
.oracle/checkins/batch-2.md:17083: trailing whitespace.
+   207	
.oracle/checkins/batch-2.md:17089: trailing whitespace.
+   213	
.oracle/checkins/batch-2.md:17090: trailing whitespace.
+   214	
.oracle/checkins/batch-2.md:17098: trailing whitespace.
+   221	
.oracle/checkins/batch-2.md:17099: trailing whitespace.
+   222	
.oracle/checkins/batch-2.md:17104: trailing whitespace.
+   227	
.oracle/checkins/batch-2.md:17105: trailing whitespace.
+   228	
.oracle/checkins/batch-2.md:17111: trailing whitespace.
+   234	
.oracle/checkins/batch-2.md:17112: trailing whitespace.
+   235	
.oracle/checkins/batch-2.md:17116: trailing whitespace.
+   239	
.oracle/checkins/batch-2.md:17117: trailing whitespace.
+   240	
.oracle/checkins/batch-2.md:17131: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:17132: trailing whitespace.
+   255	
.oracle/checkins/batch-2.md:17144: trailing whitespace.
+   267	
.oracle/checkins/batch-2.md:17148: trailing whitespace.
+   271	
.oracle/checkins/batch-2.md:17165: trailing whitespace.
+   288	
.oracle/checkins/batch-2.md:17166: trailing whitespace.
+   289	
.oracle/checkins/batch-2.md:17186: trailing whitespace.
+   309	
.oracle/checkins/batch-2.md:17190: trailing whitespace.
+   313	
.oracle/checkins/batch-2.md:17226: trailing whitespace.
+   349	
.oracle/checkins/batch-2.md:17227: trailing whitespace.
+   350	
.oracle/checkins/batch-2.md:17241: trailing whitespace.
+   364	
.oracle/checkins/batch-2.md:17242: trailing whitespace.
+   365	
.oracle/checkins/batch-2.md:17290: trailing whitespace.
+   413	
.oracle/checkins/batch-2.md:17291: trailing whitespace.
+   414	
.oracle/checkins/batch-2.md:17312: trailing whitespace.
+   435	
.oracle/checkins/batch-2.md:17313: trailing whitespace.
+   436	
.oracle/checkins/batch-2.md:17326: trailing whitespace.
+   449	
.oracle/checkins/batch-2.md:17327: trailing whitespace.
+   450	
.oracle/checkins/batch-2.md:17337: trailing whitespace.
+   460	
.oracle/checkins/batch-2.md:17338: trailing whitespace.
+   461	
.oracle/checkins/batch-2.md:17388: trailing whitespace.
+    17	
.oracle/checkins/batch-2.md:17391: trailing whitespace.
+    20	
.oracle/checkins/batch-2.md:17392: trailing whitespace.
+    21	
.oracle/checkins/batch-2.md:17398: trailing whitespace.
+    27	
.oracle/checkins/batch-2.md:17406: trailing whitespace.
+    35	
.oracle/checkins/batch-2.md:17407: trailing whitespace.
+    36	
.oracle/checkins/batch-2.md:17422: trailing whitespace.
+    51	
.oracle/checkins/batch-2.md:17426: trailing whitespace.
+    55	
.oracle/checkins/batch-2.md:17449: trailing whitespace.
+    78	
.oracle/checkins/batch-2.md:17469: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:17477: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:17485: trailing whitespace.
+   114	
.oracle/checkins/batch-2.md:17493: trailing whitespace.
+   122	
.oracle/checkins/batch-2.md:17503: trailing whitespace.
+   132	
.oracle/checkins/batch-2.md:17512: trailing whitespace.
+   141	
.oracle/checkins/batch-2.md:17518: trailing whitespace.
+   147	
.oracle/checkins/batch-2.md:17525: trailing whitespace.
+   154	
.oracle/checkins/batch-2.md:17540: trailing whitespace.
+   169	
.oracle/checkins/batch-2.md:17548: trailing whitespace.
+   177	
.oracle/checkins/batch-2.md:17561: trailing whitespace.
+   190	
.oracle/checkins/batch-2.md:17579: trailing whitespace.
+   208	
.oracle/checkins/batch-2.md:17587: trailing whitespace.
+   216	
.oracle/checkins/batch-2.md:17596: trailing whitespace.
+   225	
.oracle/checkins/batch-2.md:17616: trailing whitespace.
+   245	
.oracle/checkins/batch-2.md:17625: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:17634: trailing whitespace.
+   263	
.oracle/checkins/batch-2.md:17644: trailing whitespace.
+   273	
.oracle/checkins/batch-2.md:17645: trailing whitespace.
+   274	
.oracle/checkins/batch-2.md:17671: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:17673: trailing whitespace.
+     4	
.oracle/checkins/batch-2.md:17677: trailing whitespace.
+     8	
.oracle/checkins/batch-2.md:17680: trailing whitespace.
+    11	
.oracle/checkins/batch-2.md:17698: trailing whitespace.
+    29	
.oracle/checkins/batch-2.md:17699: trailing whitespace.
+    30	
.oracle/checkins/batch-2.md:17702: trailing whitespace.
+    33	
.oracle/checkins/batch-2.md:17703: trailing whitespace.
+    34	
.oracle/checkins/batch-2.md:17708: trailing whitespace.
+    39	
.oracle/checkins/batch-2.md:17710: trailing whitespace.
+    41	
.oracle/checkins/batch-2.md:17711: trailing whitespace.
+    42	
.oracle/checkins/batch-2.md:17723: trailing whitespace.
+    54	
.oracle/checkins/batch-2.md:17724: trailing whitespace.
+    55	
.oracle/checkins/batch-2.md:17751: trailing whitespace.
+    82	
.oracle/checkins/batch-2.md:17752: trailing whitespace.
+    83	
.oracle/checkins/batch-2.md:17755: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:17762: trailing whitespace.
+    93	
.oracle/checkins/batch-2.md:17763: trailing whitespace.
+    94	
.oracle/checkins/batch-2.md:17775: trailing whitespace.
+   106	
.oracle/checkins/batch-2.md:17776: trailing whitespace.
+   107	
.oracle/checkins/batch-2.md:17868: trailing whitespace.
+   199	
.oracle/checkins/batch-2.md:17869: trailing whitespace.
+   200	
.oracle/checkins/batch-2.md:17945: trailing whitespace.
+   276	
.oracle/checkins/batch-2.md:17946: trailing whitespace.
+   277	
.oracle/checkins/batch-2.md:17957: trailing whitespace.
+   288	
.oracle/checkins/batch-2.md:17958: trailing whitespace.
+   289	
.oracle/checkins/batch-2.md:17980: trailing whitespace.
+   311	
.oracle/checkins/batch-2.md:17981: trailing whitespace.
+   312	
.oracle/checkins/batch-2.md:18069: trailing whitespace.
+   959	
.oracle/checkins/batch-2.md:18070: trailing whitespace.
+   960	
.oracle/checkins/batch-2.md:18073: trailing whitespace.
+   963	
.oracle/checkins/batch-2.md:18074: trailing whitespace.
+   964	
.oracle/checkins/batch-2.md:18080: trailing whitespace.
+   970	
.oracle/checkins/batch-2.md:18085: trailing whitespace.
+   975	
.oracle/checkins/batch-2.md:18099: trailing whitespace.
+   989	
.oracle/checkins/batch-2.md:18100: trailing whitespace.
+   990	
.oracle/checkins/batch-2.md:18111: trailing whitespace.
+  1001	
.oracle/checkins/batch-2.md:18112: trailing whitespace.
+  1002	
.oracle/checkins/batch-2.md:18117: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:18118: trailing whitespace.
+    82	
.oracle/checkins/batch-2.md:18121: trailing whitespace.
+    85	
.oracle/checkins/batch-2.md:18122: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:18125: trailing whitespace.
+    89	
.oracle/checkins/batch-2.md:18126: trailing whitespace.
+    90	
.oracle/checkins/batch-2.md:18134: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:18135: trailing whitespace.
+    99	
.oracle/checkins/batch-2.md:18161: trailing whitespace.
+   125	
.oracle/checkins/batch-2.md:18162: trailing whitespace.
+   126	
.oracle/checkins/batch-2.md:18169: trailing whitespace.
+   133	
.oracle/checkins/batch-2.md:18174: trailing whitespace.
+   138	
.oracle/checkins/batch-2.md:18205: trailing whitespace.
+   169	
.oracle/checkins/batch-2.md:18206: trailing whitespace.
+   170	
.oracle/checkins/batch-2.md:18213: trailing whitespace.
+   177	
.oracle/checkins/batch-2.md:18215: trailing whitespace.
+   179	
.oracle/checkins/batch-2.md:18216: trailing whitespace.
+   180	
.oracle/checkins/batch-2.md:18232: trailing whitespace.
+   196	
.oracle/checkins/batch-2.md:18233: trailing whitespace.
+   197	
.oracle/checkins/batch-2.md:18254: trailing whitespace.
+   218	
.oracle/checkins/batch-2.md:18280: trailing whitespace.
+   244	
.oracle/checkins/batch-2.md:18281: trailing whitespace.
+   245	
.oracle/checkins/batch-2.md:19510: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:19515: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:19517: trailing whitespace.
+     9	
.oracle/checkins/batch-2.md:19526: trailing whitespace.
+    18	
.oracle/checkins/batch-2.md:19529: trailing whitespace.
+    21	
.oracle/checkins/batch-2.md:19531: trailing whitespace.
+    23	
.oracle/checkins/batch-2.md:19536: trailing whitespace.
+    28	
.oracle/checkins/batch-2.md:19539: trailing whitespace.
+    31	
.oracle/checkins/batch-2.md:19540: trailing whitespace.
+    32	
.oracle/checkins/batch-2.md:19544: trailing whitespace.
+    36	
.oracle/checkins/batch-2.md:19545: trailing whitespace.
+    37	
.oracle/checkins/batch-2.md:19548: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:19552: trailing whitespace.
+    44	
.oracle/checkins/batch-2.md:19567: trailing whitespace.
+    59	
.oracle/checkins/batch-2.md:19574: trailing whitespace.
+    66	
.oracle/checkins/batch-2.md:19577: trailing whitespace.
+    69	
.oracle/checkins/batch-2.md:19580: trailing whitespace.
+    72	
.oracle/checkins/batch-2.md:19581: trailing whitespace.
+    73	
.oracle/checkins/batch-2.md:19584: trailing whitespace.
+    76	
.oracle/checkins/batch-2.md:19589: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:19590: trailing whitespace.
+    82	
.oracle/checkins/batch-2.md:19593: trailing whitespace.
+    85	
.oracle/checkins/batch-2.md:19594: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:19597: trailing whitespace.
+    89	
.oracle/checkins/batch-2.md:19598: trailing whitespace.
+    90	
.oracle/checkins/batch-2.md:19606: trailing whitespace.
+    98	
.oracle/checkins/batch-2.md:19607: trailing whitespace.
+    99	
.oracle/checkins/batch-2.md:19633: trailing whitespace.
+   125	
.oracle/checkins/batch-2.md:19634: trailing whitespace.
+   126	
.oracle/checkins/batch-2.md:19641: trailing whitespace.
+   133	
.oracle/checkins/batch-2.md:19646: trailing whitespace.
+   138	
.oracle/checkins/batch-2.md:19677: trailing whitespace.
+   169	
.oracle/checkins/batch-2.md:19678: trailing whitespace.
+   170	
.oracle/checkins/batch-2.md:19685: trailing whitespace.
+   177	
.oracle/checkins/batch-2.md:19687: trailing whitespace.
+   179	
.oracle/checkins/batch-2.md:19688: trailing whitespace.
+   180	
.oracle/checkins/batch-2.md:19704: trailing whitespace.
+   196	
.oracle/checkins/batch-2.md:19705: trailing whitespace.
+   197	
.oracle/checkins/batch-2.md:19726: trailing whitespace.
+   218	
.oracle/checkins/batch-2.md:19752: trailing whitespace.
+   244	
.oracle/checkins/batch-2.md:19753: trailing whitespace.
+   245	
.oracle/checkins/batch-2.md:19763: trailing whitespace.
+   255	
.oracle/checkins/batch-2.md:19770: trailing whitespace.
+   262	
.oracle/checkins/batch-2.md:19773: trailing whitespace.
+   265	
.oracle/checkins/batch-2.md:19778: trailing whitespace.
+   270	
.oracle/checkins/batch-2.md:19785: trailing whitespace.
+   277	
.oracle/checkins/batch-2.md:19796: trailing whitespace.
+   288	
.oracle/checkins/batch-2.md:19804: trailing whitespace.
+   296	
.oracle/checkins/batch-2.md:19814: trailing whitespace.
+   306	
.oracle/checkins/batch-2.md:19815: trailing whitespace.
+   307	
.oracle/checkins/batch-2.md:19822: trailing whitespace.
+     2	
.oracle/checkins/batch-2.md:19827: trailing whitespace.
+     7	
.oracle/checkins/batch-2.md:19829: trailing whitespace.
+     9	
.oracle/checkins/batch-2.md:19839: trailing whitespace.
+    19	
.oracle/checkins/batch-2.md:19840: trailing whitespace.
+    20	
.oracle/checkins/batch-2.md:19843: trailing whitespace.
+    23	
.oracle/checkins/batch-2.md:19844: trailing whitespace.
+    24	
.oracle/checkins/batch-2.md:19859: trailing whitespace.
+    39	
.oracle/checkins/batch-2.md:19860: trailing whitespace.
+    40	
.oracle/checkins/batch-2.md:19867: trailing whitespace.
+    47	
.oracle/checkins/batch-2.md:19875: trailing whitespace.
+    55	
.oracle/checkins/batch-2.md:19884: trailing whitespace.
+    64	
.oracle/checkins/batch-2.md:19885: trailing whitespace.
+    65	
.oracle/checkins/batch-2.md:19895: trailing whitespace.
+    75	
.oracle/checkins/batch-2.md:19901: trailing whitespace.
+    81	
.oracle/checkins/batch-2.md:19906: trailing whitespace.
+    86	
.oracle/checkins/batch-2.md:19912: trailing whitespace.
+    92	
.oracle/checkins/batch-2.md:19916: trailing whitespace.
+    96	
.oracle/checkins/batch-2.md:19928: trailing whitespace.
+   108	
.oracle/checkins/batch-2.md:19934: trailing whitespace.
+   114	
.oracle/checkins/batch-2.md:19939: trailing whitespace.
+   119	
.oracle/checkins/batch-2.md:19949: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:19950: trailing whitespace.
+   130	
.oracle/checkins/batch-2.md:19955: trailing whitespace.
+   135	
.oracle/checkins/batch-2.md:19958: trailing whitespace.
+   138	
.oracle/checkins/batch-2.md:19969: trailing whitespace.
+   149	
.oracle/checkins/batch-2.md:19981: trailing whitespace.
+   161	
.oracle/checkins/batch-2.md:19982: trailing whitespace.
+   162	
.oracle/checkins/batch-2.md:20007: trailing whitespace.
+   187	
.oracle/checkins/batch-2.md:20025: trailing whitespace.
+   205	
.oracle/checkins/batch-2.md:20037: trailing whitespace.
+   217	
.oracle/checkins/batch-2.md:20038: trailing whitespace.
+   218	
.oracle/checkins/batch-2.md:20058: trailing whitespace.
+   238	
.oracle/checkins/batch-2.md:20067: trailing whitespace.
+   247	
.oracle/checkins/batch-2.md:20073: trailing whitespace.
+   253	
.oracle/checkins/batch-2.md:20074: trailing whitespace.
+   254	
.oracle/checkins/batch-2.md:20082: trailing whitespace.
+   262	
.oracle/checkins/batch-2.md:20085: trailing whitespace.
+   265	
.oracle/checkins/batch-2.md:20095: trailing whitespace.
+   275	
.oracle/checkins/batch-2.md:20167: trailing whitespace.
+   123	
.oracle/checkins/batch-2.md:20169: trailing whitespace.
+   125	
.oracle/checkins/batch-2.md:20170: trailing whitespace.
+   126	
.oracle/checkins/batch-2.md:20173: trailing whitespace.
+   129	
.oracle/checkins/batch-2.md:20183: trailing whitespace.
+   139	
.oracle/checkins/batch-2.md:20186: trailing whitespace.
+   142	
.oracle/checkins/batch-2.md:20187: trailing whitespace.
+   143	
.oracle/checkins/batch-2.md:20199: trailing whitespace.
+   155	
.oracle/checkins/batch-2.md:20205: trailing whitespace.
+   161	
.oracle/checkins/batch-2.md:20206: trailing whitespace.
+   162	
.oracle/checkins/batch-2.md:20209: trailing whitespace.
+   165	
.oracle/checkins/batch-2.md:20212: trailing whitespace.
+   168	
.oracle/checkins/batch-2.md:20221: trailing whitespace.
+   177	
.oracle/checkins/batch-2.md:20222: trailing whitespace.
+   178	
.oracle/checkins/batch-2.md:20225: trailing whitespace.
+   181	
.oracle/checkins/batch-2.md:20232: trailing whitespace.
+   188	
.oracle/checkins/batch-2.md:20238: trailing whitespace.
+   194	
.oracle/checkins/batch-2.md:20247: trailing whitespace.
+   203	
.oracle/checkins/batch-2.md:20248: trailing whitespace.
+   204	
.oracle/checkins/batch-2.md:20252: trailing whitespace.
+   208	
.oracle/checkins/batch-2.md:20255: trailing whitespace.
+   211	
.oracle/checkins/batch-2.md:20256: trailing whitespace.
+   212	
.oracle/checkins/batch-2.md:20260: trailing whitespace.
+   216	
.oracle/checkins/batch-2.md:20263: trailing whitespace.
+   219	
.oracle/checkins/batch-2.md:20264: trailing whitespace.
+   220	
.oracle/checkins/batch-2.md:20268: trailing whitespace.
+   224	
.oracle/checkins/batch-2.md:20271: trailing whitespace.
+   227	
.oracle/checkins/batch-2.md:20275: trailing whitespace.
+   231	
.oracle/checkins/batch-2.md:20276: trailing whitespace.
+   232	
.oracle/checkins/batch-2.md:20286: trailing whitespace.
+   436	
.oracle/checkins/batch-2.md:20287: trailing whitespace.
+   437	
.oracle/checkins/batch-2.md:20300: trailing whitespace.
+   450	
.oracle/checkins/batch-2.md:20301: trailing whitespace.
+   451	
.oracle/checkins/batch-2.md:20306: trailing whitespace.
+   456	
.oracle/checkins/batch-2.md:20314: trailing whitespace.
+   464	
.oracle/checkins/batch-2.md:20317: trailing whitespace.
+   467	
.oracle/checkins/batch-2.md:20321: trailing whitespace.
+   471	
.oracle/checkins/batch-2.md:20334: trailing whitespace.
+   484	
.oracle/checkins/batch-2.md:20337: trailing whitespace.
+   487	
.oracle/checkins/batch-2.md:20340: trailing whitespace.
+   490	
.oracle/checkins/batch-2.md:20341: trailing whitespace.
+   491	
.oracle/checkins/batch-2.md:20346: trailing whitespace.
+   496	
.oracle/checkins/batch-2.md:20356: trailing whitespace.
+   506	
.oracle/checkins/batch-2.md:20357: trailing whitespace.
+   507	
.oracle/checkins/batch-2.md:20364: trailing whitespace.
+   514	
.oracle/checkins/batch-2.md:20365: trailing whitespace.
+   515	

codex
The supplied worktree is at `5231a233`. I also found an existing untracked `.oracle/checkins/batch-2-r1.md`; I’m treating it as host-owned and will not touch or rely on it. The prior check-in is unusually large because it embeds review transcript material, so I’m narrowing inspection to its final findings and the seven-file incremental delta.
exec
/bin/zsh -lc "git diff --name-status dedcc2c5..5231a233 && git diff --numstat dedcc2c5..5231a233 && git show --no-ext-diff --format='%H%n%P%n%s' --no-renames --stat 5231a233 && wc -l .oracle/checkins/batch-2.md /tmp/batch2-r1.diff && tail -n 180 .oracle/checkins/batch-2.md && rg -n \"("'^|[[:space:]])(Transport|transport|invalid_artifact|protocol|fixture|symlink|publication|sidecar|Issue|ISSUE|PASS|FAIL)" .oracle/checkins/batch-2.md | tail -n 160' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-2.md
M	astrid/core/rendering/artifacts.py
M	astrid/core/rendering/publication.py
M	astrid/core/rendering/transport.py
M	tests/core/rendering/test_raw_command_fixture.py
M	tests/core/rendering/test_transport.py
M	tests/fixtures/renderer_packs/raw_command/backend.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
20674	0	.oracle/checkins/batch-2.md
6	0	astrid/core/rendering/artifacts.py
26	4	astrid/core/rendering/publication.py
17	2	astrid/core/rendering/transport.py
1	1	tests/core/rendering/test_raw_command_fixture.py
3	3	tests/core/rendering/test_transport.py
12	2	tests/fixtures/renderer_packs/raw_command/backend.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
5231a233aa86fb32d238d697b3b1b7063b3c2eb0
dedcc2c534a181fb93d52a9a38d60c1cfddf0e9b
batch2-rework: oracle issues 1-6 (missing result -> protocol, transport group-cleanup on any exception + interrupt-safe escalation, fixture SPS crop 1080 + pcm_s16le codec + support request validation, artifact in-workspace symlink rejection, publication unresolved-path symlink guards + invalidate-before-replace ordering)

 .oracle/checkins/batch-2.md                        | 20674 +++++++++++++++++++
 astrid/core/rendering/artifacts.py                 |     6 +
 astrid/core/rendering/publication.py               |    30 +-
 astrid/core/rendering/transport.py                 |    19 +-
 tests/core/rendering/test_raw_command_fixture.py   |     2 +-
 tests/core/rendering/test_transport.py             |     6 +-
 .../fixtures/renderer_packs/raw_command/backend.py |    14 +-
 7 files changed, 20739 insertions(+), 12 deletions(-)
   20674 .oracle/checkins/batch-2.md
   20875 /tmp/batch2-r1.diff
   41549 total
[vost#0:0/wrapped_avframe @ 0x13f804840] Could not open encoder before EOF
[vost#0:0/wrapped_avframe @ 0x13f804840] Task finished with error code: -22 (Invalid argument)
[vost#0:0/wrapped_avframe @ 0x13f804840] Terminating thread with return code -22 (Invalid argument)
[af#0:1 @ 0x13f855240] No filtered frames for output stream, trying to initialize anyway.
[out#0/null @ 0x6000023403c0] Nothing was written into output file, because at least one of its streams received no packets.

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'exec(\"\"\"import runpy, subprocess, threading\\nfrom http.server import BaseHTTPRequestHandler, ThreadingHTTPServer\\nm=runpy.run_path(\\\"tests/fixtures/renderer_packs/raw_command/backend.py\\\", run_name=\\\"raw_fixture_probe\\\")\\ndata=m[\\\"_build_mp4\\\"](48)\\nclass H(BaseHTTPRequestHandler):\\n def do_HEAD(self): self._send(False)\\n def do_GET(self): self._send(True)\\n def _send(self, body):\\n  raw=self.headers.get(\\\"Range\\\")\\n  start,end=0,len(data)-1\\n  status=200\\n  if raw and raw.startswith(\\\"bytes=\\\"):\\n   a,b=raw[6:].split(\\\"-\\\",1); start=int(a or 0); end=int(b) if b else end; end=min(end,len(data)-1); status=206\\n  chunk=data[start:end+1]\\n  self.send_response(status); self.send_header(\\\"Content-Type\\\",\\\"video/mp4\\\"); self.send_header(\\\"Content-Length\\\",str(len(chunk))); self.send_header(\\\"Accept-Ranges\\\",\\\"bytes\\\")\\n  if status==206: self.send_header(\\\"Content-Range\\\",f\\\"bytes {start}-{end}/{len(data)}\\\")\\n  self.end_headers()\\n  if body: self.wfile.write(chunk)\\n def log_message(self,*args): pass\\ns=ThreadingHTTPServer((\\\"127.0.0.1\\\",0),H); t=threading.Thread(target=s.serve_forever); t.start()\\nurl=f\\\"http://127.0.0.1:{s.server_address[1]}/x.mp4\\\"\\np=subprocess.run([\\\"ffprobe\\\",\\\"-v\\\",\\\"error\\\",\\\"-show_entries\\\",\\\"stream=index,codec_name,codec_tag_string,width,height,coded_width,coded_height,pix_fmt,sample_rate,channel_layout,duration\\\",\\\"-of\\\",\\\"json\\\",url],text=True,capture_output=True)\\ns.shutdown(); s.server_close(); t.join(); print(p.stdout); print(p.stderr,end=\\\"\\\"); raise SystemExit(p.returncode)\\n\"\"\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 260ms:
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "<string>", line 20, in <module>
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/socketserver.py", line 456, in __init__
    self.server_bind()
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/http/server.py", line 136, in server_bind
    socketserver.TCPServer.server_bind(self)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/socketserver.py", line 472, in server_bind
    self.socket.bind(self.server_address)
PermissionError: [Errno 1] Operation not permitted

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
18953:.oracle/briefs/batch-2-t2.6.md:20:  sidecar_path, previous_outputs)`:
18954:.oracle/briefs/batch-2-t2.6.md:25:  - Write the hashed provenance sidecar ATOMICALLY LAST
18955:.oracle/briefs/batch-2-t2.6.md:26:    (`write_json_atomic`; the sidecar contains the video's sha256 and the
18956:.oracle/briefs/batch-2-t2.6.md:28:  - Crash-orphan recovery: if a video exists but its sidecar is missing or
18958:.oracle/briefs/batch-2-t2.6.md:34:    delete only outputs whose sidecar `timeline` matches and whose pair is
18959:.oracle/briefs/batch-2-t2.6.md:36:    per pair (sidecar first, then video — the video without sidecar is
18960:.oracle/briefs/batch-2-t2.6.md:40:  write + sidecar write with the new publication path, preserving observable
18961:.oracle/briefs/batch-2-t2.6.md:41:  behavior (same filenames, same sidecar contents, same cleanup semantics).
18962:.oracle/briefs/batch-2-t2.6.md:43:  - happy path: video + sidecar published, sidecar sha256 matches;
18963:.oracle/briefs/batch-2-t2.6.md:45:  - crash-orphan: video without sidecar → not committed, conservative
18964:.oracle/briefs/batch-2-t2.6.md:46:    recovery; sidecar with wrong hash → not committed;
18966:.oracle/briefs/batch-2-t2.6.md:50:  - atomicity: sidecar write failure leaves video visible but pair
18973:.oracle/briefs/batch-2-t2.1.md:42:  structured failure; incompatible protocol version → `kind="protocol"`.
18979:.oracle/briefs/batch-2-t2.1.md:59:- incompatible protocol version;
18987:# Task T2.1 — Implement command transport and process lifecycle [HARD]
18997:`docs/contracts/render-backend-v1.md`. The frozen wire protocol is:
19028:  structured failure; incompatible protocol version → `kind="protocol"`.
19037:- successful render (use a tiny fixture script that writes a valid result
19045:- incompatible protocol version;
19058:Report: files changed, test results, the exact transport design.
19059:# Task T2.2 — Add the raw protocol fixture pack (DeepSeek Flash)
19069:`tests/core/rendering/test_transport.py`. The frozen wire protocol (from
19076:Your job: a committed RAW-COMMAND fixture renderer that implements this
19077:protocol WITHOUT importing Astrid's SDK — a plain Python script reading JSON
19116:   - assert discovery/static inspection of the fixture pack (no code import);
19121:   - assert NO `run.json` is created anywhere (the fixture must not touch
19123:   - assert the fixture works from an explicit extra pack root and (if
19125:     fixture patterns from `tests/core/rendering/test_registry_matrix.py`).
19127:   fixture doesn't break it; otherwise skip it (it needs network).
19136:owns it — if you find a transport defect, note it in your report), or
19173:     symlink escape), hash mismatch (recompute sha256 vs declared),
19197:# Task T2.6 — Locked video-plus-sidecar publication [HARD]
19207:its hashed provenance sidecar LAST (the sidecar is the commit marker),
19216:  sidecar_path, previous_outputs)`:
19221:  - Write the hashed provenance sidecar ATOMICALLY LAST
19222:    (`write_json_atomic`; the sidecar contains the video's sha256 and the
19224:  - Crash-orphan recovery: if a video exists but its sidecar is missing or
19230:    delete only outputs whose sidecar `timeline` matches and whose pair is
19232:    per pair (sidecar first, then video — the video without sidecar is
19236:  write + sidecar write with the new publication path, preserving observable
19237:  behavior (same filenames, same sidecar contents, same cleanup semantics).
19239:  - happy path: video + sidecar published, sidecar sha256 matches;
19241:  - crash-orphan: video without sidecar → not committed, conservative
19242:    recovery; sidecar with wrong hash → not committed;
19246:  - atomicity: sidecar write failure leaves video visible but pair
19260:test results, the publication protocol.
19373:    return transport, value, workspace
19509:     1	"""Locked publication for one rendered video and its provenance sidecar.
19511:     3	The provenance sidecar is the commit marker.  A video without a valid
19512:     4	sidecar is deliberately visible (and therefore recoverable), but it is never
19542:    34	_RECOVERY = "rerender the video and retry publication"
19638:   130	    sidecar_path: str | Path | None = None,
19644:   136	    conservative recovery without mistaking it for a successful publication.
19648:   140	    sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
19650:   142	        if video.is_symlink() or sidecar.is_symlink():
19652:   144	        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
19682:   174	    sidecar_path: str | Path | None = None,
19686:   178	    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
19722:   214	        video, sidecar = pair
19728:   220	        # publications for sibling outputs can otherwise deadlock while each
19737:   229	            provenance = read_committed_provenance(video, sidecar_path=sidecar)
19743:   235	                sidecar.unlink()
19759:   251	    sidecar_path: str | Path,
19766:   258	    place with :func:`os.replace`, and the complete sidecar is written
19767:   259	    atomically last.  A sidecar-write failure therefore leaves a detectable,
19776:   268	    sidecar = _resolved(sidecar_path)
19780:   272	    sidecar.parent.mkdir(parents=True, exist_ok=True)
19790:   282	        sidecar.unlink(missing_ok=True)
19807:   299	        if read_committed_provenance(output, sidecar_path=sidecar) is None:
19832:    12	from astrid.core.rendering import publication
19848:    28	    sidecar = _sidecar(video)
19850:    30	        sidecar,
19858:    38	    return sidecar
19866:    46	    sidecar = _sidecar(output)
19872:    52	        sidecar_path=sidecar,
19882:    62	    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
19883:    63	    assert is_render_result_committed(output, sidecar_path=sidecar)
19894:    74	    sidecar = _sidecar(output)
19899:    79	    real_replace = publication.os.replace
19900:    80	    real_write_json_atomic = publication.write_json_atomic
19923:   103	                sidecar_path=sidecar,
19945:   125	    payload = read_committed_provenance(output, sidecar_path=sidecar)
19953:   133	    sidecar = _sidecar(output)
19956:   136	    assert read_committed_provenance(output, sidecar_path=sidecar) is None
19957:   137	    assert not is_render_result_committed(output, sidecar_path=sidecar)
19960:   140	        sidecar,
19967:   147	    assert read_committed_provenance(output, sidecar_path=sidecar) is None
19968:   148	    assert not is_render_result_committed(output, sidecar_path=sidecar)
19976:   156	        sidecar_path=sidecar,
19980:   160	    assert is_render_result_committed(output, sidecar_path=sidecar)
20016:   196	        sidecar_path=live_sidecar,
20036:   216	    assert is_render_result_committed(live, sidecar_path=live_sidecar)
20064:   244	            sidecar_path=_sidecar(output),
20081:   261	    sidecar = _sidecar(output)
20084:   264	        raise AtomicWriteError("synthetic sidecar failure")
20087:   267	    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
20092:   272	            sidecar_path=sidecar,
20098:   278	    assert not sidecar.exists()
20099:   279	    assert not is_render_result_committed(output, sidecar_path=sidecar)
20151:    "purpose": "T2.2 raw protocol fixture render"
20381:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
20383:## Batch 2 — Command protocol and host-owned plumbing
20385:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
20390:- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
20391:- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
20395:- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
20396:- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
20400:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
20401:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
20405:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
20409:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
20410:.oracle/tasklist.md:26:## Batch 2 — Command protocol and host-owned plumbing
20411:.oracle/tasklist.md:28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
20412:.oracle/tasklist.md:33:- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
20413:.oracle/tasklist.md:43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
20414:.oracle/tasklist.md:44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
20415:.oracle/tasklist.md:52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
20416:.oracle/tasklist.md:126:- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
20417:.oracle/tasklist.md:136:- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
20418:docs/contracts/render-backend-v1.md:1:# Render backend protocol v1
20419:docs/contracts/render-backend-v1.md:65:| `protocol_version` | Integer `1`; command/wire protocol implemented. |
20421:docs/contracts/render-backend-v1.md:111:## Synchronous command protocol
20422:docs/contracts/render-backend-v1.md:135:second protocol channel. Exit zero without the required result file, malformed
20424:docs/contracts/render-backend-v1.md:139:a future protocol version.
20425:docs/contracts/render-backend-v1.md:221:Backends must ignore no unknown core fields: unknown core fields are protocol
20430:docs/contracts/render-backend-v1.md:442:   and supported protocol version.
20432:docs/contracts/render-backend-v1.md:566:meaning requires a new protocol/schema version and parallel schemas.
20433:docs/contracts/render-backend-v1.md:606:    versioned command/JSON request-result protocol is the source of truth;
20434:.oracle/plan.md:21:7. **Wire protocol:** backend commands run with `shell=False`, pack root as `cwd`, sanitized environment, absolute request/result paths, and an authoritative result file:
20435:.oracle/plan.md:85:    - structured protocol/backend/artifact/finalizer failures;
20436:.oracle/plan.md:134:  - Map missing binary, nonzero exit, timeout/interruption, missing result, malformed result, and invalid protocol versions into renderer-qualified symbolic failures.
20437:.oracle/plan.md:136:  - Commit `tests/fixtures/renderer_packs/raw_command/`, implementing the protocol without importing the Astrid SDK and producing a deterministic two-second artifact.
20438:.oracle/plan.md:159:  - Register it through `extensions.rendering` and a static renderer manifest using the raw command protocol.
20439:.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
20440:.oracle/plan.md:342:  - Verify the frozen protocol reference, schemas, raw fixture, trusted discovery, built-in registrations, generic service, and conformance suite.
20441:.oracle/plan.md:344:  - If the SDK cannot represent the wire protocol exactly, amend and re-review M1 rather than adding SDK-only behavior.
20442:.oracle/plan.md:370:    - intentional protocol/backend failure.
20443:.oracle/plan.md:21:7. **Wire protocol:** backend commands run with `shell=False`, pack root as `cwd`, sanitized environment, absolute request/result paths, and an authoritative result file:
20444:.oracle/plan.md:85:    - structured protocol/backend/artifact/finalizer failures;
20445:.oracle/plan.md:134:  - Map missing binary, nonzero exit, timeout/interruption, missing result, malformed result, and invalid protocol versions into renderer-qualified symbolic failures.
20446:.oracle/plan.md:136:  - Commit `tests/fixtures/renderer_packs/raw_command/`, implementing the protocol without importing the Astrid SDK and producing a deterministic two-second artifact.
20447:.oracle/plan.md:159:  - Register it through `extensions.rendering` and a static renderer manifest using the raw command protocol.
20448:.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
20449:.oracle/plan.md:342:  - Verify the frozen protocol reference, schemas, raw fixture, trusted discovery, built-in registrations, generic service, and conformance suite.
20450:.oracle/plan.md:344:  - If the SDK cannot represent the wire protocol exactly, amend and re-review M1 rather than adding SDK-only behavior.
20451:.oracle/plan.md:370:    - intentional protocol/backend failure.
20642:  ✓ Audit CommandTransport lifecycle and raw protocol fixture
20644:  ✓ Audit profile/probe, artifact validation, and publication invariants
20649:- A missing authoritative result is incorrectly classified as `invalid_artifact`; the frozen protocol requires `protocol`. The test locks in the wrong behavior. [transport.py:567](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:567), [test_transport.py:205](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:205), [render-backend-v1.md:133](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:133)
20651:- The raw fixture misdeclares its generated media profile. Its H.264 SPS crops 1088 lines to 1086, not 1080, and it declares audio codec `sowt` although ffprobe reports `pcm_s16le`. Strict artifact validation therefore rejects the fixture. [backend.py:131](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:131), [backend.py:471](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:471), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481)
20653:- The raw fixture’s `support` verb bypasses request validation, so unsupported request schema versions succeed instead of returning `kind="protocol"`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)
20655:- Artifact validation accepts in-workspace symlinked videos and attachments because it resolves the candidate before checking file type. Coverage only rejects symlinks that escape the workspace. [artifacts.py:154](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:154), [test_artifacts.py:167](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_artifacts.py:167)
20657:- Publication’s symlink checks are ineffective because paths are resolved before `is_symlink()` is called. Publishing and cleanup can consequently replace or delete a symlink target, while committed-pair reads accept symlink aliases. [publication.py:87](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:87), [publication.py:139](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:139), [publication.py:266](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:266)
20659:- Publication replaces the video before invalidating the previous sidecar. If interrupted in that gap and the replacement has the same hash but different provenance, the stale marker still appears committed, violating the crash-orphan invariant. [publication.py:278](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:278), [publication.py:151](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:151)
20664:- A missing authoritative result is incorrectly classified as `invalid_artifact`; the frozen protocol requires `protocol`. The test locks in the wrong behavior. [transport.py:567](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/transport.py:567), [test_transport.py:205](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_transport.py:205), [render-backend-v1.md:133](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:133)
20666:- The raw fixture misdeclares its generated media profile. Its H.264 SPS crops 1088 lines to 1086, not 1080, and it declares audio codec `sowt` although ffprobe reports `pcm_s16le`. Strict artifact validation therefore rejects the fixture. [backend.py:131](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:131), [backend.py:471](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:471), [backend.py:481](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:481)
20668:- The raw fixture’s `support` verb bypasses request validation, so unsupported request schema versions succeed instead of returning `kind="protocol"`. [backend.py:409](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:409), [backend.py:547](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:547)
20670:- Artifact validation accepts in-workspace symlinked videos and attachments because it resolves the candidate before checking file type. Coverage only rejects symlinks that escape the workspace. [artifacts.py:154](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:154), [test_artifacts.py:167](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_artifacts.py:167)
20672:- Publication’s symlink checks are ineffective because paths are resolved before `is_symlink()` is called. Publishing and cleanup can consequently replace or delete a symlink target, while committed-pair reads accept symlink aliases. [publication.py:87](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:87), [publication.py:139](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:139), [publication.py:266](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:266)
20674:- Publication replaces the video before invalidating the previous sidecar. If interrupted in that gap and the replacement has the same hash but different provenance, the stale marker still appears committed, violating the crash-orphan invariant. [publication.py:278](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:278), [publication.py:151](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/publication.py:151)

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=80 dedcc2c5..5231a233 -- astrid/core/rendering/transport.py tests/core/rendering/test_transport.py astrid/core/rendering/artifacts.py astrid/core/rendering/publication.py tests/core/rendering/test_raw_command_fixture.py tests/fixtures/renderer_packs/raw_command/backend.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/artifacts.py b/astrid/core/rendering/artifacts.py
index a5cae883..d3a83193 100644
--- a/astrid/core/rendering/artifacts.py
+++ b/astrid/core/rendering/artifacts.py
@@ -77,160 +77,166 @@ def _coerce_expected_profile(
         # Reconstruct solely to catch forged/mutated frozen instances.  The
         # caller's object remains authoritative and is returned untouched.
         RenderProfile.from_dict(candidate.to_dict())
     except Exception as exc:
         from .errors import RendererException
 
         if isinstance(exc, RendererException):
             raise
         raise_protocol_error(
             backend=_BACKEND,
             message=f"expected_profile is malformed: {exc}",
             details={"error_type": type(exc).__name__},
         )
     return candidate
 
 
 def _validate_declared_profile(profile: Any) -> RenderProfile:
     if not isinstance(profile, RenderProfile):
         _invalid(
             "malformed_profile",
             "renderer video profile is not a RenderProfile",
             received_type=type(profile).__name__,
         )
     try:
         RenderProfile.from_dict(profile.to_dict())
     except Exception as exc:
         _invalid(
             "malformed_profile",
             f"renderer video profile is malformed: {exc}",
             error_type=type(exc).__name__,
         )
     return profile
 
 
 def _workspace_root(path: str | Path) -> Path:
     try:
         root = Path(path).resolve(strict=True)
     except (OSError, RuntimeError) as exc:
         _invalid(
             "invalid_workspace",
             f"cannot resolve invocation workspace: {path}",
             workspace_root=str(path),
             error_type=type(exc).__name__,
         )
     if not root.is_dir():
         _invalid(
             "invalid_workspace",
             f"invocation workspace is not a directory: {root}",
             workspace_root=str(root),
         )
     return root
 
 
 def _validate_relative_path(raw: Any, *, label: str) -> str:
     if not isinstance(raw, str):
         _invalid(
             "invalid_path",
             f"{label} must be a workspace-relative string path",
             path_type=type(raw).__name__,
         )
     if not raw or "\x00" in raw or "\\" in raw:
         _invalid("invalid_path", f"{label} is not a normalized relative path", path=raw)
     if raw.startswith("/") or raw.startswith("//") or _WINDOWS_DRIVE_RE.match(raw):
         _invalid("escaped_path", f"{label} must not be absolute", path=raw)
     parts = raw.split("/")
     if any(
         part in {"", ".", ".."} or not part.strip(_ECMA_WHITESPACE)
         for part in parts
     ):
         _invalid(
             "escaped_path",
             f"{label} contains traversal or a non-normalized component",
             path=raw,
         )
     return raw
 
 
 def _contained_regular_file(raw: Any, *, root: Path, label: str) -> Path:
     relative = _validate_relative_path(raw, label=label)
     candidate = root.joinpath(*relative.split("/"))
+    if candidate.is_symlink():
+        _invalid(
+            "escaped_path",
+            f"{label} must not be a symbolic link: {relative}",
+            path=relative,
+        )
     try:
         resolved = candidate.resolve(strict=True)
     except (OSError, RuntimeError) as exc:
         _invalid(
             "missing_artifact",
             f"{label} does not resolve to an existing file: {relative}",
             path=relative,
             error_type=type(exc).__name__,
         )
     try:
         resolved.relative_to(root)
     except ValueError:
         _invalid(
             "escaped_path",
             f"{label} escapes the invocation workspace",
             path=relative,
             resolved_path=str(resolved),
             workspace_root=str(root),
         )
     try:
         mode = resolved.stat().st_mode
     except OSError as exc:
         _invalid(
             "missing_artifact",
             f"cannot inspect {label}: {relative}",
             path=relative,
             error_type=type(exc).__name__,
         )
     if not stat.S_ISREG(mode):
         _invalid(
             "invalid_file_type",
             f"{label} is not a regular file: {relative}",
             path=relative,
         )
     return resolved
 
 
 def _validate_digest(value: Any, *, label: str) -> str:
     if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
         _invalid(
             "invalid_hash",
             f"{label} must declare a lowercase 64-character SHA-256 digest",
             declared_sha256=value if isinstance(value, str) else None,
         )
     return value
 
 
 def _verify_hash(path: Path, declared: Any, *, label: str) -> None:
     declared_hash = _validate_digest(declared, label=label)
     try:
         actual_hash = sha256_file(path)
     except OSError as exc:
         _invalid(
             "hash_failed",
             f"cannot hash {label}",
             path=str(path),
             error_type=type(exc).__name__,
         )
     if actual_hash != declared_hash:
         _invalid(
             "hash_mismatch",
             f"{label} SHA-256 does not match the declared digest",
             path=str(path),
             expected=declared_hash,
             actual=actual_hash,
         )
 
 
 def _rational(value: Any, *, label: str) -> Fraction:
     if (
         not isinstance(value, tuple)
         or len(value) != 2
         or type(value[0]) is not int
         or type(value[1]) is not int
         or value[0] <= 0
         or value[1] <= 0
     ):
         _invalid(
             "incomplete_probe",
             f"ffprobe did not return a valid {label}",
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index 2f40b092..b261a09f 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -62,251 +62,273 @@ class _FcntlLock:
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
+        video_unresolved = Path(video_path).expanduser()
+        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
+        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
+            return None
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
+        # Never delete through a symlink: the raw candidate path must not be
+        # a link (the resolved pair may point elsewhere entirely).
+        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
+        try:
+            raw_path = Path(raw_candidate).expanduser()
+            if raw_path.is_symlink():
+                continue
+        except (OSError, TypeError):
+            continue
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
+    source_unresolved = Path(video_path).expanduser()
+    output_unresolved = Path(out_path).expanduser()
+    sidecar_unresolved = Path(sidecar_path).expanduser()
+    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
+        raise_invalid_artifact_error(
+            backend=_BACKEND,
+            message="publication paths must not be symbolic links",
+            recovery_command=_RECOVERY,
+        )
     _validate_source_video(source)
 
     output.parent.mkdir(parents=True, exist_ok=True)
     sidecar.parent.mkdir(parents=True, exist_ok=True)
     with _lock_for(output):
         # Validate again after waiting for the lock so a moved or truncated
         # staging artifact can never be reported as successfully published.
         _validate_source_video(source)
 
-        os.replace(source, output)
-        # The video rename is the first destination mutation.  Invalidate the
-        # old marker immediately afterward so a crash can leave an orphan but
-        # can never leave a marker for hash-mismatched bytes.
+        # Invalidate the previous marker BEFORE the first destination
+        # mutation: a crash can then leave an orphan video (recoverable) but
+        # can never leave a stale marker claiming the new bytes are committed.
         sidecar.unlink(missing_ok=True)
+        os.replace(source, output)
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
index c58ff3f8..6085a07c 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -157,160 +157,169 @@ class CommandTransport:
                 child_env=child_env,
                 backend=selected_backend,
             )
 
         _remove_stale_result(result, backend=selected_backend)
         argv = [
             *argv_prefix,
             verb,
             "--request",
             str(request),
             "--result",
             str(result),
         ]
         secret_values = _secret_environment_values(os.environ, env)
 
         try:
             process = subprocess.Popen(
                 argv,
                 shell=False,
                 cwd=str(cwd_path),
                 env=child_env,
                 stdin=subprocess.DEVNULL,
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 text=True,
                 encoding="utf-8",
                 errors="replace",
                 start_new_session=True,
             )
         except (FileNotFoundError, PermissionError) as exc:
             raise_binary_missing_error(
                 backend=selected_backend,
                 message=f"renderer executable is unavailable: {argv_prefix[0]}",
                 details={
                     "binary": argv_prefix[0],
                     "error_type": type(exc).__name__,
                     **self.last_logs,
                 },
             )
         except OSError as exc:
             raise_internal_error(
                 backend=selected_backend,
                 message=f"failed to start renderer command: {exc}",
                 details={"error_type": type(exc).__name__, **self.last_logs},
             )
 
         try:
             stdout, stderr = process.communicate(timeout=normalized_timeout)
         except subprocess.TimeoutExpired:
             stdout, stderr = _terminate_process_group(
                 process, grace=self.termination_grace
             )
             logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
             self.last_logs = logs
             raise_timeout_error(
                 backend=selected_backend,
                 message=f"renderer command timed out after {normalized_timeout:g} seconds",
                 details={
                     "timeout_seconds": normalized_timeout,
                     "returncode": process.returncode,
                     **logs,
                 },
             )
         except KeyboardInterrupt as exc:
             stdout, stderr = _terminate_process_group(
                 process, grace=self.termination_grace
             )
             logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
             self.last_logs = logs
             error = make_renderer_error(
                 "interrupted",
                 backend=selected_backend,
                 message="renderer command was interrupted",
                 details={"returncode": process.returncode, **logs},
             )
             # Preserve normal SIGINT/exit-130 behavior while still making the
             # frozen structured error available to an embedding caller.
             exc.renderer_error = error  # type: ignore[attr-defined]
             exc.error = error  # type: ignore[attr-defined]
             raise
+        except Exception as exc:
+            # Any other post-spawn failure (including a defect in result
+            # parsing) must still terminate and reap the process group so no
+            # orphan is left behind.
+            try:
+                _terminate_process_group(process, grace=self.termination_grace)
+            except Exception:
+                pass
+            raise
 
         logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
         self.last_logs = logs
         _terminate_leftover_group(process, grace=self.termination_grace)
 
         if process.returncode != 0:
             raise_internal_error(
                 backend=selected_backend,
                 message=f"renderer command exited with status {process.returncode}",
                 details={"returncode": process.returncode, **logs},
             )
 
         payload = _read_result_file(
             result,
             backend=selected_backend,
             logs=logs,
         )
         return _parse_result(
             verb,
             payload,
             backend=selected_backend,
             logs=logs,
         )
 
 
 def _validate_backend(backend: str) -> None:
     if not isinstance(backend, str) or not _QUALIFIED_ID_RE.fullmatch(backend):
         raise ValueError(
             "backend must be a qualified id '<pack>.<name>' using lowercase "
             "letters, digits, hyphens, or underscores"
         )
 
 
 def _validate_timeout(timeout: float | None, *, backend: str) -> float | None:
     if timeout is None:
         return None
     if (
         isinstance(timeout, bool)
         or not isinstance(timeout, (int, float))
         or not math.isfinite(float(timeout))
         or timeout <= 0
     ):
         raise_protocol_error(
             backend=backend,
             message="renderer timeout must be a positive finite number or null",
             details={"received": repr(timeout)},
         )
     return float(timeout)
 
 
 def _normalize_command(
     command: Sequence[str | os.PathLike[str]], *, backend: str
 ) -> list[str]:
     if isinstance(command, (str, bytes)) or not isinstance(command, Sequence):
         raise_protocol_error(
             backend=backend,
             message="renderer command must be a non-empty argv sequence",
         )
     argv: list[str] = []
     for index, value in enumerate(command):
         if not isinstance(value, (str, os.PathLike)):
             raise_protocol_error(
                 backend=backend,
                 message=f"renderer command argument {index} must be a path string",
                 details={"argument_index": index},
             )
         item = os.fspath(value)
         if not item or "\x00" in item:
             raise_protocol_error(
                 backend=backend,
                 message=f"renderer command argument {index} must be non-empty and contain no NUL",
                 details={"argument_index": index},
             )
         argv.append(item)
     if not argv:
         raise_protocol_error(
             backend=backend,
             message="renderer command must contain at least one argument",
         )
     return argv
@@ -383,267 +392,273 @@ def _resolve_executable(
 
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
-        pass
+        captured = None
+        # Interruption during the grace window must not abandon the group:
+        # escalate to SIGKILL right away and reap in the loop below.
+        try:
+            _signal_process_group(process, signal.SIGKILL)
+        except OSError:
+            pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
         while True:
             try:
                 captured = process.communicate()
                 break
             except KeyboardInterrupt:
                 _signal_process_group(process, signal.SIGKILL)
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
-        raise_invalid_artifact_error(
+        raise_protocol_error(
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
 
 
 def _parse_result(
     verb: str,
     payload: Any,
     *,
     backend: str,
     logs: Mapping[str, str],
 ) -> CommandResult:
     if isinstance(payload, Mapping) and "kind" in payload:
         try:
             emitted_error = RendererError.from_dict(payload)
         except RendererException as exc:
             _raise_requalified(exc, backend=backend, logs=logs)
         if emitted_error.backend != backend:
             raise_protocol_error(
                 backend=backend,
                 message="renderer error result names a different backend",
                 details={"reported_backend": emitted_error.backend, **logs},
             )
         raise_renderer_error(
             replace(
                 emitted_error,
                 details={**emitted_error.details, **logs},
             )
         )
 
     parser: Any
     if verb in {"render", "finalize"}:
         parser = RenderResult.from_dict
     elif verb == "support":
         parser = SupportReport.from_dict
     else:
         parser = RenderPlan.from_dict
 
     try:
         parsed = parser(payload)
     except RendererException as exc:
diff --git a/tests/core/rendering/test_raw_command_fixture.py b/tests/core/rendering/test_raw_command_fixture.py
index b00810a2..51de30c6 100644
--- a/tests/core/rendering/test_raw_command_fixture.py
+++ b/tests/core/rendering/test_raw_command_fixture.py
@@ -99,161 +99,161 @@ def _stage_installed_fixture(astrid_home: Path, pack_root: Path = PACK_ROOT) ->
         name=summary["name"],
         version=str(summary["version"]),
         schema_version=summary["schema_version"],
         source_path=str(pack_root),
         installed_at="2026-01-01T00:00:00Z",
         revision=PACK_ID,
         install_root=str(install_root),
         active=True,
         manifest_digest=sha256_file(revision / "pack.yaml"),
         trust_summary=summary,
         source_type="local",
         trust_tier="local",
         last_validation_time="2026-01-01T00:00:00Z",
         trust_acknowledged_at="2026-01-01T00:00:00Z",
         trust_method="test",
         trust_actor="test",
         no_sandbox_warning_version=1,
         permissions_accepted=summary["permissions"],
     )
     InstalledPackStore(astrid_home / "packs").record_install(record)
     return revision
 
 
 def _write_request(workspace: Path, request_name: str) -> Path:
     workspace.mkdir(parents=True, exist_ok=True)
     request = json.loads((REQUESTS_DIR / request_name).read_text(encoding="utf-8"))
     request_path = workspace / "request.json"
     request_path.write_text(json.dumps(request), encoding="utf-8")
     timeline = REQUESTS_DIR / "timeline.json"
     if timeline.is_file():
         shutil.copyfile(timeline, workspace / "timeline.json")
     return request_path
 
 
 def _run_transport(
     workspace: Path,
     cwd: Path,
     *,
     verb: str,
     request_name: str = "render.json",
     timeout: float = 30,
 ):
     request_path = _write_request(workspace, request_name)
     result_path = workspace / "result.json"
     transport = CommandTransport(BACKEND_ID, termination_grace=0.15)
     value = transport.run(
         verb,
         [sys.executable, "backend.py"],
         request_path=request_path,
         result_path=result_path,
         cwd=cwd,
         timeout=timeout,
     )
     return transport, value, workspace
 
 
 def _assert_clean_render(result: RenderResult, workspace: Path) -> None:
     """Shared artifact assertions for a successful render invocation."""
     assert isinstance(result, RenderResult)
     assert result.schema_version == 1
     assert result.audio_ownership == "rendered"
     assert result.video.audio == "rendered"
     assert result.video.duration_frames == RENDER_WINDOW_FRAMES
     assert result.video.path == "outputs/raw_command.mp4"
     assert BACKEND_ID in result.backend_fragments
 
     video_path = workspace / result.video.path
     assert video_path.is_file()
     assert video_path.stat().st_size > 0
     assert len(result.video.sha256) == 64
     assert sha256_file(video_path) == result.video.sha256
 
     profile = result.video.profile
     assert profile.width == 1920
     assert profile.height == 1080
     assert profile.fps_rational == (24, 1)
     assert profile.time_base == (1, 12288)
     assert profile.container == "mp4"
     assert profile.video_codec == "h264"
     assert profile.pixel_format == "yuv420p"
-    assert profile.audio_codec == "sowt"
+    assert profile.audio_codec == "pcm_s16le"
     assert profile.audio_sample_rate == 48000
     assert profile.audio_channel_layout == "stereo"
 
 
 # ---------------------------------------------------------------------------
 # Static discovery / validation (no code import)
 # ---------------------------------------------------------------------------
 
 
 def test_fixture_pack_validates_and_inspects_without_importing_backend(
     tmp_path: Path,
 ) -> None:
     errors, _warnings = validate_pack(str(PACK_ROOT))
     assert not errors, errors
 
     pack = load_pack_manifest(PACK_ROOT / "pack.yaml")
     assert pack.id == PACK_ID
     permission_ids = {permission.id for permission in pack.permissions}
     assert permission_ids == {"subprocess", "project_files"}
     assert all(permission.reason for permission in pack.permissions)
     assert pack.extensions["rendering"]["renderers"] == ["renderer.yaml"]
     assert pack.aliases == (
         {"kind": "renderer", "alias": ALIAS_ID, "canonical_id": BACKEND_ID},
     )
 
     source_root = tmp_path / "source"
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
diff --git a/tests/core/rendering/test_transport.py b/tests/core/rendering/test_transport.py
index df5b2833..5359a13a 100644
--- a/tests/core/rendering/test_transport.py
+++ b/tests/core/rendering/test_transport.py
@@ -125,156 +125,156 @@ def test_each_protocol_verb_uses_its_frozen_result_dto(
 
 
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
     _assert_pid_disappears(child_pid)
 
 
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
 
 
-def test_absent_result_file_is_invalid_artifact(tmp_path: Path) -> None:
-    with pytest.raises(RendererInvalidArtifactError) as caught:
+def test_absent_result_file_is_protocol_failure(tmp_path: Path) -> None:
+    with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "absent"})
 
-    assert caught.value.error.kind == "invalid_artifact"
+    assert caught.value.error.kind == "protocol"
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
     assert result.metadata == {
         "secret_value": "absent",
         "safe_value": "transport-safe-locale",
     }
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index aac40405..2910f543 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -1,219 +1,219 @@
 #!/usr/bin/env python3
 """Raw v1 command backend for the ``raw_command`` fixture pack (T2.2).
 
 Implements the frozen render-backend-v1 wire protocol WITHOUT importing the
 Astrid SDK and WITHOUT ffmpeg:
 
     python3 backend.py render|support --request <abs.json> --result <abs.json>
 
 * ``support`` writes a SupportReport-shaped result.
 * ``render``  writes a deterministic ~2 second MP4 containing a solid-color
   H.264 (baseline) video track and a silent 16-bit PCM (``sowt``) audio
   track, then writes a RenderResult-shaped result whose sha256 is the real
   digest of the produced file.
 
 The script is pure stdlib (argparse, hashlib, json, struct). It never writes
 Astrid ledger files (no ``run.json``): the only files it creates are the
 authoritative ``--result`` JSON and the generated video under the request's
 workspace.
 """
 
 from __future__ import annotations
 
 import argparse
 import hashlib
 import json
 import re
 import struct
 import sys
 from pathlib import Path
 
 BACKEND_ID = "raw_command.renderer"
 BACKEND_VERSION = "1.0.0"
 
 # Deterministic media constants.  The container timing (time_base 1/12288,
 # 512 ticks per frame at 24fps) matches the committed request fixture.
 WIDTH = 1920
 HEIGHT = 1080
 FPS_RATIONAL = [24, 1]
 TIME_BASE = [1, 12288]
 SAMPLES_PER_FRAME = 512
 AUDIO_SAMPLE_RATE = 48000
 AUDIO_CHANNELS = 2
 AUDIO_BITS = 16
 CONTAINER = "mp4"
 VIDEO_CODEC = "h264"
 PIXEL_FORMAT = "yuv420p"
-AUDIO_CODEC = "sowt"
+AUDIO_CODEC = "pcm_s16le"
 AUDIO_CHANNEL_LAYOUT = "stereo"
 
 _MB_COLS = WIDTH // 16          # 120
 _MB_ROWS = (HEIGHT + 15) // 16  # 68  -> 1088 coded lines, 8 cropped
 _MB_COUNT = _MB_COLS * _MB_ROWS  # 8160
 
 _MATRIX = struct.pack(">9I", 0x00010000, 0, 0, 0, 0x00010000, 0, 0, 0, 0x40000000)
 
 _OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
 
 
 # ---------------------------------------------------------------------------
 # Bit-level H.264 (baseline, all-IDR) construction
 # ---------------------------------------------------------------------------
 
 
 class _BitWriter:
     """Tiny MSB-first bit writer over a bytearray."""
 
     __slots__ = ("data", "acc", "nbits")
 
     def __init__(self) -> None:
         self.data = bytearray()
         self.acc = 0
         self.nbits = 0
 
     def put(self, value: int, count: int) -> None:
         for shift in range(count - 1, -1, -1):
             self.acc = (self.acc << 1) | ((value >> shift) & 1)
             self.nbits += 1
             if self.nbits == 8:
                 self.data.append(self.acc)
                 self.acc = 0
                 self.nbits = 0
 
     def finish(self) -> None:
         """Append rbsp_trailing_bits: a single 1 bit plus zero padding."""
         if self.nbits:
             self.data.append((self.acc << (8 - self.nbits)) | (1 << (7 - self.nbits)))
         else:
             self.data.append(0x80)
         self.acc = 0
         self.nbits = 0
 
 
 def _ue(writer: _BitWriter, value: int) -> None:
     """Exp-Golomb unsigned code."""
     code_num = value + 1
     n = code_num.bit_length()
     writer.put(0, n - 1)
     writer.put(code_num, n)
 
 
 def _se(writer: _BitWriter, value: int) -> None:
     """Exp-Golomb signed code."""
     _ue(writer, -2 * value if value <= 0 else 2 * value - 1)
 
 
 def _escape_rbsp(data: bytes) -> bytes:
     """Insert emulation-prevention 0x03 bytes after 00 00 [<=03]."""
     out = bytearray()
     zeros = 0
     for byte in data:
         if zeros >= 2 and byte <= 3:
             out.append(3)
             zeros = 0
         out.append(byte)
         zeros = zeros + 1 if byte == 0 else 0
     return bytes(out)
 
 
 def _sps_nal() -> bytes:
     """Sequence parameter set for baseline 1920x1080 @ level 4.0."""
     w = _BitWriter()
     w.put(66, 8)            # profile_idc = baseline
     w.put(0xC0, 8)          # constraint_set0|set1
     w.put(40, 8)            # level_idc = 4.0
     _ue(w, 0)               # seq_parameter_set_id
     _ue(w, 0)               # log2_max_frame_num_minus4 -> 4-bit frame_num
     _ue(w, 0)               # pic_order_cnt_type = 0
     _ue(w, 4)               # log2_max_pic_order_cnt_lsb_minus4 -> 8-bit POC lsb
     _ue(w, 1)               # max_num_ref_frames
     w.put(0, 1)             # gaps_in_frame_num_value_allowed_flag
     _ue(w, _MB_COLS - 1)    # pic_width_in_mbs_minus1
     _ue(w, _MB_ROWS - 1)    # pic_height_in_map_units_minus1
     w.put(1, 1)             # frame_mbs_only_flag
     w.put(1, 1)             # direct_8x8_inference_flag
     w.put(1, 1)             # frame_cropping_flag
     _ue(w, 0)               # frame_crop_left_offset
     _ue(w, 0)               # frame_crop_right_offset
     _ue(w, 0)               # frame_crop_top_offset
-    _ue(w, 1)               # frame_crop_bottom_offset (1088 -> 1080)
+    _ue(w, 4)               # frame_crop_bottom_offset (1088 - 8 = 1080)
     w.put(0, 1)             # vui_parameters_present_flag
     w.finish()
     return bytes([0x67]) + _escape_rbsp(bytes(w.data))
 
 
 def _pps_nal() -> bytes:
     """Picture parameter set (CAVLC, single slice group)."""
     w = _BitWriter()
     _ue(w, 0)               # pic_parameter_set_id
     _ue(w, 0)               # seq_parameter_set_id
     w.put(0, 1)             # entropy_coding_mode_flag (CAVLC)
     w.put(0, 1)             # bottom_field_pic_order_in_frame_present_flag
     _ue(w, 0)               # num_slice_groups_minus1
     _ue(w, 0)               # num_ref_idx_l0_default_active_minus1
     _ue(w, 0)               # num_ref_idx_l1_default_active_minus1
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
@@ -468,94 +468,104 @@ def _render(request: dict, result_path: Path, request_path: Path) -> int:
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
     except Exception as exc:
         _write_error(
             result_path,
             "protocol",
             f"cannot read request JSON from {request_path}: {exc}",
             {"error_type": type(exc).__name__},
         )
         return 0
 
     if args.verb == "support":
+        try:
+            _validate_request(request)
+        except ValueError as exc:
+            _write_error(
+                result_path,
+                "protocol",
+                f"invalid support request: {exc}",
+                {"error_type": type(exc).__name__},
+            )
+            return 0
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

exec
/bin/zsh -lc "rg -n \"def (_terminate_process_group|_kill_process_group|_read_result_file|run\\b)|except (KeyboardInterrupt|Exception)|communicate\\(|wait\\(\" astrid/core/rendering/transport.py && nl -ba astrid/core/rendering/transport.py | sed -n '1,260p' && nl -ba astrid/core/rendering/transport.py | sed -n '420,640p' && git diff --no-ext-diff --unified=15 dedcc2c5..5231a233 -- astrid/core/rendering/transport.py tests/core/rendering/test_transport.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
99:    def run(
204:            stdout, stderr = process.communicate(timeout=normalized_timeout)
220:        except KeyboardInterrupt as exc:
237:        except Exception as exc:
243:            except Exception:
461:def _terminate_process_group(
470:        captured = process.communicate(timeout=grace)
490:                captured = process.communicate()
492:            except KeyboardInterrupt:
498:        captured = process.communicate()
575:def _read_result_file(
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
   541	
   542	
   543	def _redact_log(value: str, *, secret_values: Sequence[str]) -> str:
   544	    redacted = value.replace("\x00", "\ufffd")
   545	    for secret in secret_values:
   546	        redacted = redacted.replace(secret, "[redacted]")
   547	    redacted = _AUTH_HEADER_RE.sub(
   548	        lambda match: f"{match.group(1)}: [redacted]", redacted
   549	    )
   550	    redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
   551	    redacted = _SECRET_QUERY_RE.sub(
   552	        lambda match: f"{match.group(1)}[redacted]", redacted
   553	    )
   554	    redacted = _SECRET_ASSIGNMENT_RE.sub(
   555	        lambda match: f"{match.group(1)}[redacted]", redacted
   556	    )
   557	    redacted = _SECRET_VALUE_RE.sub("[redacted]", redacted)
   558	    if len(redacted) > _MAX_LOG_CHARS:
   559	        redacted = redacted[:_MAX_LOG_CHARS] + "\n[truncated]"
   560	    return redacted
   561	
   562	
   563	def _redacted_logs(
   564	    stdout: str,
   565	    stderr: str,
   566	    *,
   567	    secret_values: Sequence[str],
   568	) -> dict[str, str]:
   569	    return {
   570	        "stdout": _redact_log(stdout or "", secret_values=secret_values),
   571	        "stderr": _redact_log(stderr or "", secret_values=secret_values),
   572	    }
   573	
   574	
   575	def _read_result_file(
   576	    result_path: Path,
   577	    *,
   578	    backend: str,
   579	    logs: Mapping[str, str],
   580	) -> Any:
   581	    try:
   582	        result_stat = result_path.lstat()
   583	    except FileNotFoundError:
   584	        raise_protocol_error(
   585	            backend=backend,
   586	            message=f"renderer did not write its authoritative result file: {result_path}",
   587	            details={"result_path": str(result_path), **logs},
   588	        )
   589	    except OSError as exc:
   590	        raise_invalid_artifact_error(
   591	            backend=backend,
   592	            message=f"cannot inspect renderer result file: {result_path}",
   593	            details={
   594	                "result_path": str(result_path),
   595	                "error_type": type(exc).__name__,
   596	                **logs,
   597	            },
   598	        )
   599	    if stat.S_ISLNK(result_stat.st_mode) or not stat.S_ISREG(result_stat.st_mode):
   600	        raise_invalid_artifact_error(
   601	            backend=backend,
   602	            message=f"renderer result path is not a regular file: {result_path}",
   603	            details={"result_path": str(result_path), **logs},
   604	        )
   605	    try:
   606	        return json.loads(result_path.read_text(encoding="utf-8"))
   607	    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
   608	        raise_protocol_error(
   609	            backend=backend,
   610	            message=f"renderer wrote malformed result JSON: {exc}",
   611	            details={
   612	                "result_path": str(result_path),
   613	                "error_type": type(exc).__name__,
   614	                **logs,
   615	            },
   616	        )
   617	    except OSError as exc:
   618	        raise_invalid_artifact_error(
   619	            backend=backend,
   620	            message=f"cannot read renderer result file: {result_path}",
   621	            details={
   622	                "result_path": str(result_path),
   623	                "error_type": type(exc).__name__,
   624	                **logs,
   625	            },
   626	        )
   627	
   628	
   629	def _parse_result(
   630	    verb: str,
   631	    payload: Any,
   632	    *,
   633	    backend: str,
   634	    logs: Mapping[str, str],
   635	) -> CommandResult:
   636	    if isinstance(payload, Mapping) and "kind" in payload:
   637	        try:
   638	            emitted_error = RendererError.from_dict(payload)
   639	        except RendererException as exc:
   640	            _raise_requalified(exc, backend=backend, logs=logs)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index c58ff3f8..6085a07c 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -222,30 +222,39 @@ class CommandTransport:
                 process, grace=self.termination_grace
             )
             logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
             self.last_logs = logs
             error = make_renderer_error(
                 "interrupted",
                 backend=selected_backend,
                 message="renderer command was interrupted",
                 details={"returncode": process.returncode, **logs},
             )
             # Preserve normal SIGINT/exit-130 behavior while still making the
             # frozen structured error available to an embedding caller.
             exc.renderer_error = error  # type: ignore[attr-defined]
             exc.error = error  # type: ignore[attr-defined]
             raise
+        except Exception as exc:
+            # Any other post-spawn failure (including a defect in result
+            # parsing) must still terminate and reap the process group so no
+            # orphan is left behind.
+            try:
+                _terminate_process_group(process, grace=self.termination_grace)
+            except Exception:
+                pass
+            raise
 
         logs = _redacted_logs(stdout, stderr, secret_values=secret_values)
         self.last_logs = logs
         _terminate_leftover_group(process, grace=self.termination_grace)
 
         if process.returncode != 0:
             raise_internal_error(
                 backend=selected_backend,
                 message=f"renderer command exited with status {process.returncode}",
                 details={"returncode": process.returncode, **logs},
             )
 
         payload = _read_result_file(
             result,
             backend=selected_backend,
@@ -448,31 +457,37 @@ def _process_group_exists(process: subprocess.Popen[str]) -> bool:
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
-        pass
+        captured = None
+        # Interruption during the grace window must not abandon the group:
+        # escalate to SIGKILL right away and reap in the loop below.
+        try:
+            _signal_process_group(process, signal.SIGKILL)
+        except OSError:
+            pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
         time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
         while True:
             try:
                 captured = process.communicate()
                 break
             except KeyboardInterrupt:
                 _signal_process_group(process, signal.SIGKILL)
@@ -554,31 +569,31 @@ def _redacted_logs(
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
-        raise_invalid_artifact_error(
+        raise_protocol_error(
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
diff --git a/tests/core/rendering/test_transport.py b/tests/core/rendering/test_transport.py
index df5b2833..5359a13a 100644
--- a/tests/core/rendering/test_transport.py
+++ b/tests/core/rendering/test_transport.py
@@ -190,35 +190,35 @@ def test_sigint_kills_process_group_reaps_and_reraises(tmp_path: Path) -> None:
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
 
 
-def test_absent_result_file_is_invalid_artifact(tmp_path: Path) -> None:
-    with pytest.raises(RendererInvalidArtifactError) as caught:
+def test_absent_result_file_is_protocol_failure(tmp_path: Path) -> None:
+    with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "absent"})
 
-    assert caught.value.error.kind == "invalid_artifact"
+    assert caught.value.error.kind == "protocol"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_malformed_result_json_is_protocol_failure(tmp_path: Path) -> None:
     with pytest.raises(RendererProtocolError) as caught:
         _run(tmp_path, {"action": "malformed"})
 
     assert caught.value.error.kind == "protocol"
     assert caught.value.error.backend == RENDERER_ID
 
 
 def test_incompatible_result_version_is_protocol_failure(tmp_path: Path) -> None:
     payload = _wire_fixture("result.json")
     payload["schema_version"] = 2
 

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/publication.py | sed -n '1,360p' && rg -n \"symlink|replace|sidecar|crash|cleanup|previous|committed|interrupt\" tests/core/rendering/test_publication.py tests/core/rendering/test_artifacts.py && nl -ba tests/core/rendering/test_publication.py | sed -n '1,390p' && nl -ba tests/core/rendering/test_artifacts.py | sed -n '120,250p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   219	        # Never delete through a symlink: the raw candidate path must not be
   220	        # a link (the resolved pair may point elsewhere entirely).
   221	        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
   222	        try:
   223	            raw_path = Path(raw_candidate).expanduser()
   224	            if raw_path.is_symlink():
   225	                continue
   226	        except (OSError, TypeError):
   227	            continue
   228	        if video == live_output or video in seen:
   229	            continue
   230	        seen.add(video)
   231	
   232	        # Never wait while holding the live output lock.  Two concurrent
   233	        # publications for sibling outputs can otherwise deadlock while each
   234	        # tries to clean the other, and a locked candidate is by definition a
   235	        # live render that cleanup must preserve.
   236	        candidate_lock = _lock_for(video)
   237	        try:
   238	            candidate_lock.acquire(timeout=0)
   239	        except (Timeout, OSError):
   240	            continue
   241	        try:
   242	            provenance = read_committed_provenance(video, sidecar_path=sidecar)
   243	            if provenance is None or provenance.get("timeline") != timeline:
   244	                continue
   245	            try:
   246	                # The marker disappears first.  A crash or failure between
   247	                # these unlinks leaves an orphan, never a false committed pair.
   248	                sidecar.unlink()
   249	            except (FileNotFoundError, OSError):
   250	                continue
   251	            try:
   252	                video.unlink()
   253	            except (FileNotFoundError, OSError):
   254	                pass
   255	        finally:
   256	            candidate_lock.release()
   257	
   258	
   259	def publish_render_result(
   260	    video_path: str | Path,
   261	    provenance_payload: Mapping[str, Any],
   262	    *,
   263	    out_path: str | Path,
   264	    sidecar_path: str | Path,
   265	    previous_outputs: Iterable[object] = (),
   266	) -> Path:
   267	    """Publish one video and atomically commit its hashed provenance marker.
   268	
   269	    The source video is validated before any destination mutation.  Under the
   270	    per-output lock an old marker is invalidated, the video is moved into
   271	    place with :func:`os.replace`, and the complete sidecar is written
   272	    atomically last.  A sidecar-write failure therefore leaves a detectable,
   273	    recoverable orphan video and is propagated to the caller.
   274	    """
   275	
   276	    if not isinstance(provenance_payload, Mapping):
   277	        raise TypeError("provenance_payload must be a mapping")
   278	
   279	    source = _resolved(video_path)
   280	    output = _resolved(out_path)
   281	    sidecar = _resolved(sidecar_path)
   282	    source_unresolved = Path(video_path).expanduser()
   283	    output_unresolved = Path(out_path).expanduser()
   284	    sidecar_unresolved = Path(sidecar_path).expanduser()
   285	    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
   286	        raise_invalid_artifact_error(
   287	            backend=_BACKEND,
   288	            message="publication paths must not be symbolic links",
   289	            recovery_command=_RECOVERY,
   290	        )
   291	    _validate_source_video(source)
   292	
   293	    output.parent.mkdir(parents=True, exist_ok=True)
   294	    sidecar.parent.mkdir(parents=True, exist_ok=True)
   295	    with _lock_for(output):
   296	        # Validate again after waiting for the lock so a moved or truncated
   297	        # staging artifact can never be reported as successfully published.
   298	        _validate_source_video(source)
   299	
   300	        # Invalidate the previous marker BEFORE the first destination
   301	        # mutation: a crash can then leave an orphan video (recoverable) but
   302	        # can never leave a stale marker claiming the new bytes are committed.
   303	        sidecar.unlink(missing_ok=True)
   304	        os.replace(source, output)
   305	        digest = sha256_file(output)
   306	        committed_payload = dict(provenance_payload)
   307	        committed_payload["output"] = str(output)
   308	        committed_payload["sha256"] = digest
   309	        write_json_atomic(sidecar, committed_payload)
   310	
   311	        # Cleanup happens only after the new pair is committed and while its
   312	        # lock remains held.  Candidate locks are non-blocking (see above).
   313	        _delete_previous_outputs(
   314	            previous_outputs,
   315	            live_output=output,
   316	            timeline=committed_payload.get("timeline"),
   317	        )
   318	
   319	        # Do not report success unless the bytes and marker we just wrote are
   320	        # still a complete pair under the same lock.
   321	        if read_committed_provenance(output, sidecar_path=sidecar) is None:
   322	            _invalid_video(
   323	                output,
   324	                reason="uncommitted_artifact",
   325	                message=f"published video has no valid provenance commit marker: {output}",
   326	            )
   327	    return output
   328	
   329	
   330	__all__ = [
   331	    "is_render_result_committed",
   332	    "publish_render_result",
   333	    "read_committed_provenance",
   334	]
tests/core/rendering/test_artifacts.py:3:from dataclasses import replace
tests/core/rendering/test_artifacts.py:167:def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
tests/core/rendering/test_artifacts.py:172:    (workspace / "escape.mp4").symlink_to(outside)
tests/core/rendering/test_artifacts.py:219:        lambda _path: replace(_probe(), **{field: value}),
tests/core/rendering/test_artifacts.py:332:        lambda _path: replace(_probe(audio=True), **{field: value}),
tests/core/rendering/test_publication.py:15:    is_render_result_committed,
tests/core/rendering/test_publication.py:17:    read_committed_provenance,
tests/core/rendering/test_publication.py:21:def _sidecar(video: Path) -> Path:
tests/core/rendering/test_publication.py:25:def _committed_pair(video: Path, *, contents: bytes, timeline: str) -> Path:
tests/core/rendering/test_publication.py:28:    sidecar = _sidecar(video)
tests/core/rendering/test_publication.py:30:        sidecar,
tests/core/rendering/test_publication.py:38:    return sidecar
tests/core/rendering/test_publication.py:41:def test_happy_path_publishes_video_then_hashed_sidecar(tmp_path: Path) -> None:
tests/core/rendering/test_publication.py:46:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:52:        sidecar_path=sidecar,
tests/core/rendering/test_publication.py:53:        previous_outputs=(),
tests/core/rendering/test_publication.py:59:    payload = json.loads(sidecar.read_text(encoding="utf-8"))
tests/core/rendering/test_publication.py:62:    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
tests/core/rendering/test_publication.py:63:    assert is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:74:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:76:    first_in_sidecar_write = threading.Event()
tests/core/rendering/test_publication.py:78:    second_replaced = threading.Event()
tests/core/rendering/test_publication.py:79:    real_replace = publication.os.replace
tests/core/rendering/test_publication.py:82:    def observing_replace(source: str | Path, destination: str | Path) -> None:
tests/core/rendering/test_publication.py:84:            second_replaced.set()
tests/core/rendering/test_publication.py:85:        real_replace(source, destination)
tests/core/rendering/test_publication.py:87:    def blocking_sidecar_write(path: str | Path, payload: object) -> None:
tests/core/rendering/test_publication.py:89:            first_in_sidecar_write.set()
tests/core/rendering/test_publication.py:93:    monkeypatch.setattr(publication.os, "replace", observing_replace)
tests/core/rendering/test_publication.py:94:    monkeypatch.setattr(publication, "write_json_atomic", blocking_sidecar_write)
tests/core/rendering/test_publication.py:103:                sidecar_path=sidecar,
tests/core/rendering/test_publication.py:104:                previous_outputs=(),
tests/core/rendering/test_publication.py:112:    assert first_in_sidecar_write.wait(timeout=5)
tests/core/rendering/test_publication.py:115:    assert not second_replaced.wait(timeout=0.2)
tests/core/rendering/test_publication.py:123:    assert second_replaced.is_set()
tests/core/rendering/test_publication.py:125:    payload = read_committed_provenance(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:131:def test_crash_orphans_are_not_committed_and_can_be_repaired(tmp_path: Path) -> None:
tests/core/rendering/test_publication.py:133:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:136:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:137:    assert not is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:140:        sidecar,
tests/core/rendering/test_publication.py:147:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:148:    assert not is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:150:    replacement = tmp_path / "replacement.mp4"
tests/core/rendering/test_publication.py:151:    replacement.write_bytes(b"replacement")
tests/core/rendering/test_publication.py:153:        replacement,
tests/core/rendering/test_publication.py:156:        sidecar_path=sidecar,
tests/core/rendering/test_publication.py:157:        previous_outputs=(),
tests/core/rendering/test_publication.py:159:    assert output.read_bytes() == b"replacement"
tests/core/rendering/test_publication.py:160:    assert is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:163:def test_previous_output_cleanup_is_complete_matching_and_lock_safe(tmp_path: Path) -> None:
tests/core/rendering/test_publication.py:170:    matching_sidecar = _committed_pair(matching, contents=b"old", timeline=timeline)
tests/core/rendering/test_publication.py:171:    nonmatching_sidecar = _committed_pair(
tests/core/rendering/test_publication.py:178:    wrong_hash_sidecar = _sidecar(wrong_hash)
tests/core/rendering/test_publication.py:180:        wrong_hash_sidecar,
tests/core/rendering/test_publication.py:191:    live_sidecar = _sidecar(live)
tests/core/rendering/test_publication.py:196:        sidecar_path=live_sidecar,
tests/core/rendering/test_publication.py:197:        previous_outputs=[
tests/core/rendering/test_publication.py:207:    assert not matching_sidecar.exists()
tests/core/rendering/test_publication.py:209:    assert nonmatching_sidecar.exists()
tests/core/rendering/test_publication.py:211:    assert not _sidecar(missing_marker).exists()
tests/core/rendering/test_publication.py:213:    assert wrong_hash_sidecar.exists()
tests/core/rendering/test_publication.py:215:    assert live_sidecar.exists()
tests/core/rendering/test_publication.py:216:    assert is_render_result_committed(live, sidecar_path=live_sidecar)
tests/core/rendering/test_publication.py:236:    replace = Mock(side_effect=AssertionError("must not rename"))
tests/core/rendering/test_publication.py:237:    monkeypatch.setattr(publication.os, "replace", replace)
tests/core/rendering/test_publication.py:244:            sidecar_path=_sidecar(output),
tests/core/rendering/test_publication.py:245:            previous_outputs=(),
tests/core/rendering/test_publication.py:250:    replace.assert_not_called()
tests/core/rendering/test_publication.py:252:    assert not _sidecar(output).exists()
tests/core/rendering/test_publication.py:255:def test_sidecar_write_failure_leaves_recoverable_uncommitted_video(
tests/core/rendering/test_publication.py:261:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:263:    def fail_sidecar(_path: str | Path, _payload: object) -> None:
tests/core/rendering/test_publication.py:264:        raise AtomicWriteError("synthetic sidecar failure")
tests/core/rendering/test_publication.py:266:    monkeypatch.setattr(publication, "write_json_atomic", fail_sidecar)
tests/core/rendering/test_publication.py:267:    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
tests/core/rendering/test_publication.py:272:            sidecar_path=sidecar,
tests/core/rendering/test_publication.py:273:            previous_outputs=(),
tests/core/rendering/test_publication.py:278:    assert not sidecar.exists()
tests/core/rendering/test_publication.py:279:    assert not is_render_result_committed(output, sidecar_path=sidecar)
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

2026-08-12T05:58:11.536063Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/zsh -lc 'set -euo pipefail
probe_dir=$(mktemp -d /tmp/astrid-b2-fixture.XXXXXX)
case "$probe_dir" in
  /tmp/astrid-b2-fixture.*) ;;
  *) exit 2 ;;
esac
trap '"'rm -rf -- \""'$probe_dir"'"' EXIT
cp tests/fixtures/renderer_packs/raw_command/requests/render.json \""'$probe_dir/request.json"
python3 tests/fixtures/renderer_packs/raw_command/backend.py render --request "$probe_dir/request.json" --result "$probe_dir/result.json"
printf '"'%s\\n' \""'$probe_dir/outputs/raw_command.mp4"
ffprobe -v error -show_entries '"'format=format_name,duration:stream=index,codec_type,codec_name,codec_tag_string,profile,level,width,height,coded_width,coded_height,pix_fmt,avg_frame_rate,r_frame_rate,time_base,sample_rate,channel_layout,duration' -of json \""'$probe_dir/outputs/raw_command.mp4"
PYTHONDONTWRITEBYTECODE=1 python3 - "$probe_dir" <<'"'PY'
import json
import sys
from dataclasses import asdict
from pathlib import Path

from astrid.core.media import ffprobe_metadata_strict
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.errors import RendererException

root = Path(sys.argv[1])
request = json.loads((root / \"request.json\").read_text(encoding=\"utf-8\"))
result = json.loads((root / \"result.json\").read_text(encoding=\"utf-8\"))
probe = ffprobe_metadata_strict(root / result[\"video\"][\"path\"])
print(json.dumps({
    \"strict_probe\": {
        key: value for key, value in asdict(probe).items() if key "'!= "_raw"
    },
    "request_profile": request["profile"],
    "result_declared_profile": result["video"]["profile"],
}, indent=2, default=list))
for label, expected in (
    ("request_profile", request["profile"]),
    ("result_declared_profile", result["video"]["profile"]),
):
    try:
        validate_render_result(result, expected_profile=expected, workspace_root=root)
    except RendererException as exc:
        print(json.dumps({
            "validation_against": label,
            "status": "REJECTED",
            "kind": exc.error.kind,
            "details": exc.error.details,
        }, indent=2, default=str))
    else:
        print(json.dumps({"validation_against": label, "status": "ACCEPTED"}))
PY'`: CreateProcess { message: "Rejected(\"`/bin/zsh -lc 'set -euo pipefail\\nprobe_dir=$(mktemp -d /tmp/astrid-b2-fixture.XXXXXX)\\ncase \\\"$probe_dir\\\" in\\n  /tmp/astrid-b2-fixture.*) ;;\\n  *) exit 2 ;;\\nesac\\ntrap '\\\"'rm -rf -- \\\\\\\"\\\"'$probe_dir\\\"'\\\"' EXIT\\ncp tests/fixtures/renderer_packs/raw_command/requests/render.json \\\\\\\"\\\"'$probe_dir/request.json\\\"\\npython3 tests/fixtures/renderer_packs/raw_command/backend.py render --request \\\"$probe_dir/request.json\\\" --result \\\"$probe_dir/result.json\\\"\\nprintf '\\\"'%s\\\\\\\\n' \\\\\\\"\\\"'$probe_dir/outputs/raw_command.mp4\\\"\\nffprobe -v error -show_entries '\\\"'format=format_name,duration:stream=index,codec_type,codec_name,codec_tag_string,profile,level,width,height,coded_width,coded_height,pix_fmt,avg_frame_rate,r_frame_rate,time_base,sample_rate,channel_layout,duration' -of json \\\\\\\"\\\"'$probe_dir/outputs/raw_command.mp4\\\"\\nPYTHONDONTWRITEBYTECODE=1 python3 - \\\"$probe_dir\\\" <<'\\\"'PY'\\nimport json\\nimport sys\\nfrom dataclasses import asdict\\nfrom pathlib import Path\\n\\nfrom astrid.core.media import ffprobe_metadata_strict\\nfrom astrid.core.rendering.artifacts import validate_render_result\\nfrom astrid.core.rendering.errors import RendererException\\n\\nroot = Path(sys.argv[1])\\nrequest = json.loads((root / \\\\\\\"request.json\\\\\\\").read_text(encoding=\\\\\\\"utf-8\\\\\\\"))\\nresult = json.loads((root / \\\\\\\"result.json\\\\\\\").read_text(encoding=\\\\\\\"utf-8\\\\\\\"))\\nprobe = ffprobe_metadata_strict(root / result[\\\\\\\"video\\\\\\\"][\\\\\\\"path\\\\\\\"])\\nprint(json.dumps({\\n    \\\\\\\"strict_probe\\\\\\\": {\\n        key: value for key, value in asdict(probe).items() if key \\\"'!= \\\"_raw\\\"\\n    },\\n    \\\"request_profile\\\": request[\\\"profile\\\"],\\n    \\\"result_declared_profile\\\": result[\\\"video\\\"][\\\"profile\\\"],\\n}, indent=2, default=list))\\nfor label, expected in (\\n    (\\\"request_profile\\\", request[\\\"profile\\\"]),\\n    (\\\"result_declared_profile\\\", result[\\\"video\\\"][\\\"profile\\\"]),\\n):\\n    try:\\n        validate_render_result(result, expected_profile=expected, workspace_root=root)\\n    except RendererException as exc:\\n        print(json.dumps({\\n            \\\"validation_against\\\": label,\\n            \\\"status\\\": \\\"REJECTED\\\",\\n            \\\"kind\\\": exc.error.kind,\\n            \\\"details\\\": exc.error.details,\\n        }, indent=2, default=str))\\n    else:\\n        print(json.dumps({\\\"validation_against\\\": label, \\\"status\\\": \\\"ACCEPTED\\\"}))\\nPY'` rejected: rm -f style commands are not permitted. Use a safer approach\")" }
codex
The first concrete risk is in publication cleanup: the new guard appears to inspect only the raw video candidate, while an explicitly supplied sidecar may also be a symlink and is resolved before cleanup. I’m reproducing that path now, alongside the requested strict probe of a freshly generated fixture MP4 and transport interrupt injection.
exec
/bin/zsh -lc "rg --files tests/fixtures/renderer_packs/raw_command && rg -n \"def ffprobe_metadata_strict|class .*Probe|ffprobe_metadata_strict\" astrid tests/core/rendering/test_raw_command_fixture.py && nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '1,360p' && nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '360,580p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/fixtures/renderer_packs/raw_command/requests/support.json
tests/fixtures/renderer_packs/raw_command/requests/timeline.json
tests/fixtures/renderer_packs/raw_command/requests/render.json
tests/fixtures/renderer_packs/raw_command/renderer.yaml
tests/fixtures/renderer_packs/raw_command/pack.yaml
tests/fixtures/renderer_packs/raw_command/backend.py
astrid/packs/foley/executors/tile_video/run.py:34:class FoleyProbeError(ValueError):
astrid/core/media.py:29:class MediaProbe:
astrid/core/media.py:87:class MediaProbeError(RuntimeError):
astrid/core/media.py:295:def ffprobe_metadata_strict(
astrid/core/rendering/artifacts.py:14:from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict
astrid/core/rendering/artifacts.py:681:        probe = ffprobe_metadata_strict(video_path)
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
   360	    video_stbl, audio_stbl = _sample_tables(
   361	        video_frames=frames,
   362	        video_sizes=video_sizes,
   363	        video_chunk_offset=video_chunk_offset,
   364	        audio_bytes=audio_bytes,
   365	        audio_samples=audio_samples,
   366	        audio_chunk_offset=audio_chunk_offset,
   367	    )
   368	
   369	    vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
   370	    smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
   371	    dinf = _dinf()
   372	
   373	    minf_v = _box(b"minf", vmhd + dinf + video_stbl)
   374	    mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
   375	    trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)
   376	
   377	    minf_a = _box(b"minf", smhd + dinf + audio_stbl)
   378	    mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, audio_samples) + _hdlr(b"soun", b"SoundHandler") + minf_a)
   379	    trak_a = _box(b"trak", _tkhd(2, audio_samples, 0x0100, 0, 0) + mdia_a)
   380	
   381	    moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME) + trak_v + trak_a)
   382	    mdat = _box(b"mdat", video_chunk + audio_bytes)
   383	    return ftyp + mdat + moov
   384	
   385	
   386	# ---------------------------------------------------------------------------
   387	# Protocol verbs
   388	# ---------------------------------------------------------------------------
   389	
   390	
   391	def _write_json(path: Path, payload: dict) -> None:
   392	    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
   393	
   394	
   395	def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
   396	    _write_json(
   397	        result_path,
   398	        {
   399	            "schema_version": 1,
   400	            "kind": kind,
   401	            "backend": BACKEND_ID,
   402	            "message": message,
   403	            "recovery_command": None,
   404	            "details": details,
   405	        },
   406	    )
   407	
   408	
   409	def _validate_request(request: dict) -> None:
   410	    if request.get("schema_version") != 1:
   411	        raise ValueError(
   412	            f"unsupported request schema_version {request.get('schema_version')!r}; expected 1"
   413	        )
   414	    output_name = request.get("output_name")
   415	    if not isinstance(output_name, str) or output_name in (".", ".."):
   416	        raise ValueError("output_name must be a non-empty portable basename")
   417	    if not _OUTPUT_NAME_RE.fullmatch(output_name):
   418	        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
   419	    window = request.get("window")
   420	    if window is not None and not isinstance(window, dict):
   421	        raise ValueError("window must be an object or null")
   422	    if isinstance(window, dict):
   423	        end = window.get("end_frame")
   424	        start = window.get("start_frame", 0)
   425	        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
   426	            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
   427	
   428	
   429	def _support(result_path: Path) -> int:
   430	    _write_json(
   431	        result_path,
   432	        {
   433	            "schema_version": 1,
   434	            "supported": True,
   435	            "reasons": [],
   436	            "features": {"media": True, "audio_mode": "rendered"},
   437	            "alternatives": [],
   438	            "backend": BACKEND_ID,
   439	            "backend_version": BACKEND_VERSION,
   440	        },
   441	    )
   442	    return 0
   443	
   444	
   445	def _render(request: dict, result_path: Path, request_path: Path) -> int:
   446	    try:
   447	        _validate_request(request)
   448	        window = request.get("window")
   449	        profile = request.get("profile") or {}
   450	        if isinstance(window, dict):
   451	            start = int(window.get("start_frame", 0))
   452	            end = int(window["end_frame"])
   453	        else:
   454	            start, end = 0, 48
   455	        frames = end - start
   456	        if frames <= 0:
   457	            raise ValueError("window must span at least one frame")
   458	
   459	        output_name = request["output_name"]
   460	        # The invocation workspace is the directory holding the request file;
   461	        # keep every generated artifact contained there.
   462	        workspace = request_path.resolve().parent
   463	        out_dir = workspace / "outputs"
   464	        out_dir.mkdir(parents=True, exist_ok=True)
   465	        video_rel = f"outputs/{output_name}"
   466	        video_path = out_dir / output_name
   467	
   468	        media = _build_mp4(frames)
   469	        video_path.write_bytes(media)
   470	
   471	        probed_profile = {
   472	            "width": WIDTH,
   473	            "height": HEIGHT,
   474	            "fps_rational": list(FPS_RATIONAL),
   475	            "time_base": list(TIME_BASE),
   476	            "container": CONTAINER,
   477	            "video_codec": VIDEO_CODEC,
   478	            "video_profile": None,
   479	            "video_level": None,
   480	            "pixel_format": PIXEL_FORMAT,
   481	            "audio_codec": AUDIO_CODEC,
   482	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   483	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   484	            "duration_tolerance": int(profile.get("duration_tolerance", 1)),
   485	        }
   486	        result = {
   487	            "schema_version": 1,
   488	            "video": {
   489	                "path": video_rel,
   490	                "profile": probed_profile,
   491	                "sha256": hashlib.sha256(media).hexdigest(),
   492	                "duration_frames": frames,
   493	                "audio": "rendered",
   494	                "attachments": {},
   495	            },
   496	            "backend_fragments": {
   497	                BACKEND_ID: {
   498	                    "renderer": "raw_command",
   499	                    "media": "generated",
   500	                    "audio_mode": "rendered",
   501	                    "deterministic": True,
   502	                }
   503	            },
   504	            "audio_ownership": "rendered",
   505	            "normalization": [],
   506	            "logs": [],
   507	            "metadata": {},
   508	        }
   509	        _write_json(result_path, result)
   510	        return 0
   511	    except ValueError as exc:
   512	        _write_error(result_path, "protocol", str(exc), {"error_type": "ValueError"})
   513	        return 0
   514	    except Exception as exc:  # pragma: no cover - unexpected failure path
   515	        _write_error(
   516	            result_path,
   517	            "internal",
   518	            f"raw_command renderer failed: {exc}",
   519	            {"error_type": type(exc).__name__},
   520	        )
   521	        return 0
   522	
   523	
   524	def main(argv: list[str]) -> int:
   525	    parser = argparse.ArgumentParser(
   526	        prog="backend.py",
   527	        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
   528	    )
   529	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
   530	    parser.add_argument("--request", required=True, help="absolute path to request JSON")
   531	    parser.add_argument("--result", required=True, help="absolute path to result JSON")
   532	    args = parser.parse_args(argv)
   533	
   534	    request_path = Path(args.request)
   535	    result_path = Path(args.result)
   536	    try:
   537	        request = json.loads(request_path.read_text(encoding="utf-8"))
   538	    except Exception as exc:
   539	        _write_error(
   540	            result_path,
   541	            "protocol",
   542	            f"cannot read request JSON from {request_path}: {exc}",
   543	            {"error_type": type(exc).__name__},
   544	        )
   545	        return 0
   546	
   547	    if args.verb == "support":
   548	        try:
   549	            _validate_request(request)
   550	        except ValueError as exc:
   551	            _write_error(
   552	                result_path,
   553	                "protocol",
   554	                f"invalid support request: {exc}",
   555	                {"error_type": type(exc).__name__},
   556	            )
   557	            return 0
   558	        return _support(result_path)
   559	    if args.verb in ("plan", "finalize"):
   560	        _write_error(
   561	            result_path,
   562	            "unsupported",
   563	            f"{BACKEND_ID} only implements render and support",
   564	            {"verb": args.verb},
   565	        )
   566	        return 0
   567	    return _render(request, result_path, request_path)
   568	
   569	
   570	if __name__ == "__main__":
   571	    raise SystemExit(main(sys.argv[1:]))

exec
/bin/zsh -lc "nl -ba astrid/core/media.py | sed -n '1,130p' && nl -ba astrid/core/media.py | sed -n '270,380p' && sed -n '1,220p' tests/fixtures/renderer_packs/raw_command/requests/render.json && sed -n '1,220p' tests/fixtures/renderer_packs/raw_command/requests/support.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   270	        return MediaProbe()
   271	
   272	    try:
   273	        return _parse_ffprobe_payload(data, file_path)
   274	    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
   275	        if strict:
   276	            raise MediaProbeError(
   277	                f"ffprobe returned malformed metadata for {file_path}: {exc}"
   278	            ) from exc
   279	        return MediaProbe()
   280	
   281	
   282	def ffprobe_metadata(
   283	    file_path: str | Path,
   284	    *,
   285	    timeout: float = 30.0,
   286	) -> MediaProbe:
   287	    """Extract duration, fps, resolution, width, and height via ffprobe.
   288	
   289	    Returns a :class:`MediaProbe` with best-effort fields populated.
   290	    If ffprobe is not available or fails, all fields are ``None``.
   291	    """
   292	    return _ffprobe_metadata(file_path, timeout=timeout, strict=False)
   293	
   294	
   295	def ffprobe_metadata_strict(
   296	    file_path: str | Path,
   297	    *,
   298	    timeout: float = 30.0,
   299	) -> MediaProbe:
   300	    """Return ffprobe metadata or raise :class:`MediaProbeError`.
   301	
   302	    Unlike :func:`ffprobe_metadata`, this entry point never converts an
   303	    unavailable binary, failed command, timeout, or malformed payload into an
   304	    all-``None`` probe.  Callers still decide which streams and fields their
   305	    particular artifact contract requires.
   306	    """
   307	
   308	    return _ffprobe_metadata(file_path, timeout=timeout, strict=True)
   309	
   310	
   311	# ---------------------------------------------------------------------------
   312	# Narrow duration probe (preserved for callers who only need seconds)
   313	# ---------------------------------------------------------------------------
   314	
   315	
   316	def ffprobe_duration_seconds(
   317	    media_path: str | Path,
   318	    *,
   319	    runner: Runner = subprocess.run,
   320	    env: Mapping[str, str] | None = None,
   321	) -> float:
   322	    """Return format duration in seconds using the narrow ffprobe duration probe."""
   323	
   324	    result = runner(
   325	        [
   326	            "ffprobe",
   327	            "-v",
   328	            "error",
   329	            "-show_entries",
   330	            "format=duration",
   331	            "-of",
   332	            "default=noprint_wrappers=1:nokey=1",
   333	            str(media_path),
   334	        ],
   335	        check=True,
   336	        capture_output=True,
   337	        env=build_child_subprocess_env(explicit_env=env or {}),
   338	        text=True,
   339	    )
   340	    return float(str(result.stdout).strip())
{
  "schema_version": 1,
  "timeline_path": "timeline.json",
  "assets_registry_path": null,
  "output_name": "raw_command.mp4",
  "window": {
    "start_frame": 0,
    "end_frame": 48,
    "fps_rational": [24, 1],
    "source_range": null,
    "speed": 1.0
  },
  "audio": "rendered",
  "profile": {
    "width": 1920,
    "height": 1080,
    "fps_rational": [24, 1],
    "time_base": [1, 12288],
    "container": "mp4",
    "video_codec": "h264",
    "video_profile": null,
    "video_level": null,
    "pixel_format": "yuv420p",
    "audio_codec": "sowt",
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
{
  "schema_version": 1,
  "timeline_path": "timeline.json",
  "assets_registry_path": null,
  "output_name": "raw_command.mp4",
  "window": {
    "start_frame": 0,
    "end_frame": 48,
    "fps_rational": [24, 1],
    "source_range": null,
    "speed": 1.0
  },
  "audio": "rendered",
  "profile": {
    "width": 1920,
    "height": 1080,
    "fps_rational": [24, 1],
    "time_base": [1, 12288],
    "container": "mp4",
    "video_codec": "h264",
    "video_profile": null,
    "video_level": null,
    "pixel_format": "yuv420p",
    "audio_codec": "sowt",
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

exec
/bin/zsh -lc "rg -n \"def (_profile|validate_render_result)|audio_codec|expected_profile|declared_profile\" astrid/core/rendering/artifacts.py | head -n 120 && nl -ba astrid/core/rendering/artifacts.py | sed -n '380,760p' && rg -n '\"audio_codec\"\\s*:\\s*\"sowt\"|AUDIO_CODEC\\s*=|pcm_s16le' tests/fixtures/renderer_packs/raw_command tests/core/rendering/test_raw_command_fixture.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
63:def _coerce_expected_profile(
74:                message="expected_profile must be a RenderProfile or profile mapping",
87:            message=f"expected_profile is malformed: {exc}",
93:def _validate_declared_profile(profile: Any) -> RenderProfile:
274:def _profile_value(profile: RenderProfile, field: str) -> Any:
291:        "audio_codec",
344:        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
445:            ("audio_codec", probe.audio_codec),
471:            for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout")
630:def validate_render_result(
633:    expected_profile: RenderProfile | Mapping[str, Any],
645:    expected = _coerce_expected_profile(expected_profile)
648:    declared = _validate_declared_profile(video.profile)
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
   511	        except (TypeError, ValueError, ZeroDivisionError):
   512	            _invalid(
   513	                "incomplete_probe",
   514	                "ffprobe returned an invalid rational duration",
   515	                actual=probe.duration_rational,
   516	            )
   517	    else:
   518	        seconds = probe.duration_seconds
   519	        if seconds is None or not math.isfinite(seconds):
   520	            _invalid(
   521	                "incomplete_probe",
   522	                "ffprobe returned an invalid duration",
   523	                actual=seconds,
   524	            )
   525	        duration = Fraction(str(seconds))
   526	    if duration < 0:
   527	        _invalid(
   528	            "incomplete_probe",
   529	            "ffprobe returned a negative duration",
   530	            actual=float(duration),
   531	        )
   532	    return duration
   533	
   534	
   535	def _validate_duration(
   536	    probe: MediaProbe,
   537	    *,
   538	    duration_frames: Any,
   539	    expected: RenderProfile,
   540	) -> None:
   541	    if type(duration_frames) is not int or duration_frames <= 0:
   542	        _invalid(
   543	            "invalid_duration",
   544	            "video artifact duration_frames must be a positive integer",
   545	            declared_duration_frames=duration_frames,
   546	        )
   547	    fps = Fraction(*expected.fps_rational)
   548	    actual_frames = _duration_fraction(probe) * fps
   549	    delta = abs(actual_frames - duration_frames)
   550	    if delta > expected.duration_tolerance:
   551	        _invalid(
   552	            "duration_mismatch",
   553	            "probed video duration is outside the canonical frame tolerance",
   554	            declared_duration_frames=duration_frames,
   555	            actual_duration_frames=float(actual_frames),
   556	            actual_duration_frames_rational=[actual_frames.numerator, actual_frames.denominator],
   557	            tolerance_frames=expected.duration_tolerance,
   558	        )
   559	
   560	
   561	def _validate_attachment(
   562	    key: Any,
   563	    attachment: Any,
   564	    *,
   565	    root: Path,
   566	) -> None:
   567	    if not isinstance(key, str) or not _OUTPUT_NAME_RE.fullmatch(key):
   568	        _invalid(
   569	            "invalid_attachment",
   570	            "attachment map key must be a portable name",
   571	            attachment_name=key if isinstance(key, str) else None,
   572	        )
   573	    if not isinstance(attachment, Attachment):
   574	        _invalid(
   575	            "invalid_attachment",
   576	            f"attachment {key!r} is not an Attachment",
   577	            attachment_name=key,
   578	            received_type=type(attachment).__name__,
   579	        )
   580	    if attachment.name != key or not _OUTPUT_NAME_RE.fullmatch(attachment.name):
   581	        _invalid(
   582	            "invalid_attachment",
   583	            f"attachment {key!r} has an invalid or mismatched name",
   584	            attachment_name=attachment.name,
   585	            map_key=key,
   586	        )
   587	    if not isinstance(attachment.kind, str) or not _KIND_RE.fullmatch(attachment.kind):
   588	        _invalid(
   589	            "invalid_attachment_kind",
   590	            f"attachment {key!r} has an invalid kind",
   591	            attachment_name=key,
   592	            kind=attachment.kind if isinstance(attachment.kind, str) else None,
   593	        )
   594	    path = _contained_regular_file(
   595	        attachment.path,
   596	        root=root,
   597	        label=f"attachment {key!r} path",
   598	    )
   599	    _verify_hash(path, attachment.sha256, label=f"attachment {key!r}")
   600	
   601	
   602	def _validate_result_shape(result: RenderResult) -> tuple[VideoArtifact, AudioOwnership]:
   603	    video = result.video
   604	    if not isinstance(video, VideoArtifact):
   605	        _invalid(
   606	            "malformed_artifact",
   607	            "render result video is not a VideoArtifact",
   608	            received_type=type(video).__name__,
   609	        )
   610	    ownership = result.audio_ownership
   611	    if not isinstance(ownership, AudioOwnership):
   612	        try:
   613	            ownership = AudioOwnership(ownership)
   614	        except (TypeError, ValueError):
   615	            _invalid(
   616	                "audio_ownership_mismatch",
   617	                "render result has an invalid audio_ownership value",
   618	                actual=str(result.audio_ownership),
   619	            )
   620	    if video.audio is not ownership:
   621	        _invalid(
   622	            "audio_ownership_mismatch",
   623	            "video.audio does not match result audio_ownership",
   624	            result_audio=ownership.value,
   625	            video_audio=video.audio.value if isinstance(video.audio, AudioOwnership) else None,
   626	        )
   627	    return video, ownership
   628	
   629	
   630	def validate_render_result(
   631	    result: RenderResult | Mapping[str, Any],
   632	    *,
   633	    expected_profile: RenderProfile | Mapping[str, Any],
   634	    workspace_root: str | Path,
   635	) -> RenderResult:
   636	    """Validate one renderer result before finalization or publication.
   637	
   638	    Every artifact path is resolved inside the invocation workspace, every
   639	    digest is recomputed, and the primary media is strictly probed.  On
   640	    success the same :class:`RenderResult` object is returned, preserving its
   641	    named attachments exactly as supplied.
   642	    """
   643	
   644	    render_result = _coerce_result(result)
   645	    expected = _coerce_expected_profile(expected_profile)
   646	    root = _workspace_root(workspace_root)
   647	    video, ownership = _validate_result_shape(render_result)
   648	    declared = _validate_declared_profile(video.profile)
   649	    _compare_declared_to_expected(declared, expected, ownership)
   650	
   651	    video_path = _contained_regular_file(video.path, root=root, label="primary video path")
   652	    try:
   653	        output_size = video_path.stat().st_size
   654	    except OSError as exc:
   655	        _invalid(
   656	            "missing_artifact",
   657	            "cannot inspect primary video size",
   658	            path=video.path,
   659	            error_type=type(exc).__name__,
   660	        )
   661	    if output_size <= 0:
   662	        _invalid(
   663	            "empty_artifact",
   664	            "renderer primary video is empty",
   665	            path=video.path,
   666	            size=output_size,
   667	        )
   668	    _verify_hash(video_path, video.sha256, label="primary video")
   669	
   670	    attachments = video.attachments
   671	    if not isinstance(attachments, Mapping):
   672	        _invalid(
   673	            "invalid_attachment",
   674	            "video attachments must be a named mapping",
   675	            received_type=type(attachments).__name__,
   676	        )
   677	    for name, attachment in attachments.items():
   678	        _validate_attachment(name, attachment, root=root)
   679	
   680	    try:
   681	        probe = ffprobe_metadata_strict(video_path)
   682	    except (MediaProbeError, OSError, RuntimeError, ValueError) as exc:
   683	        _invalid(
   684	            "probe_failed",
   685	            f"strict media probe failed for renderer output: {exc}",
   686	            path=video.path,
   687	            error_type=type(exc).__name__,
   688	        )
   689	    _probe_required_video(probe)
   690	    _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=False)
   691	    _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=False)
   692	    _validate_audio(
   693	        probe,
   694	        ownership=ownership,
   695	        declared=declared,
   696	        expected=expected,
   697	    )
   698	    _validate_duration(probe, duration_frames=video.duration_frames, expected=expected)
   699	    return render_result
   700	
   701	
   702	__all__ = ["validate_render_result"]
tests/core/rendering/test_raw_command_fixture.py:179:    assert profile.audio_codec == "pcm_s16le"
tests/fixtures/renderer_packs/raw_command/requests/support.json:24:    "audio_codec": "sowt",
tests/fixtures/renderer_packs/raw_command/backend.py:47:AUDIO_CODEC = "pcm_s16le"
tests/fixtures/renderer_packs/raw_command/requests/render.json:24:    "audio_codec": "sowt",

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '250,370p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The sandbox enforces the requested read-only mode even for `/tmp`, so file-producing pytest/fixture runs are unavailable here. I can still generate the MP4 bytes entirely through pipes: raw `ffprobe` and Astrid’s strict probe can inspect stdin without touching disk. I’ll use that plus pure in-memory contract checks; the host’s test totals remain supporting evidence, not a substitute for this review.
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); sys.stdout.buffer.write(m[\"_build_mp4\"](48))' | ffprobe -v error -show_entries stream=index,codec_name,codec_tag_string,profile,level,width,height,coded_width,coded_height,pix_fmt,r_frame_rate,time_base,sample_rate,channel_layout,duration -show_entries format=format_name,duration -of json pipe:0
PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); sys.stdout.buffer.write(m[\"_build_mp4\"](48))' | PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
from dataclasses import asdict
import json
from astrid.core.media import ffprobe_metadata_strict
probe = ffprobe_metadata_strict(\"/dev/stdin\")
print(json.dumps({key: value for key, value in asdict(probe).items() if key "'!= "_raw"}, sort_keys=True))
PY
PYTHONDONTWRITEBYTECODE=1 python - <<'"'PY'
import json
import runpy
from pathlib import Path
from astrid.core.rendering.artifacts import _compare_declared_to_expected
from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
backend = runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_profile\")
request = json.loads(Path(\"tests/fixtures/renderer_packs/raw_command/requests/render.json\").read_text())
result_profile = dict(request[\"profile\"])
result_profile[\"audio_codec\"] = backend[\"AUDIO_CODEC\"]
declared = RenderProfile.from_dict(result_profile)
expected = RenderProfile.from_dict(request[\"profile\"])
try:
    _compare_declared_to_expected(declared, expected, AudioOwnership.RENDERED)
except Exception as exc:
    error = getattr(exc, \"error\", None)
    print(json.dumps({\"request_audio_codec\": expected.audio_codec, \"result_audio_codec\": declared.audio_codec, \"exception\": type(exc).__name__, \"kind\": getattr(error, \"kind\", None), \"details\": getattr(exc, \"details\", None)}, sort_keys=True, default=str))
else:
    print(\"profile-comparison-passed\")
PY" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 662ms:
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x1589044f0] stream 0, offset 0x28: partial file
{
    "programs": [

    ],
    "stream_groups": [

    ],
    "streams": [
        {
            "index": 0,
            "codec_name": "h264",
            "codec_tag_string": "avc1",
            "width": 1920,
            "height": 1080,
            "coded_width": 1920,
            "coded_height": 1080,
            "level": -99,
            "r_frame_rate": "24/1",
            "time_base": "1/12288",
            "duration": "2.000000"
        },
        {
            "index": 1,
            "codec_name": "pcm_s16le",
            "codec_tag_string": "sowt",
            "sample_rate": "48000",
            "r_frame_rate": "0/0",
            "time_base": "1/48000",
            "duration": "2.000000"
        }
    ],
    "format": {
        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
        "duration": "2.000000"
    }
}
zsh:2: can't create temp file for here document: operation not permitted
Traceback (most recent call last):
  File "<string>", line 1, in <module>
BrokenPipeError: [Errno 32] Broken pipe
zsh:9: can't create temp file for here document: operation not permitted

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); sys.stdout.buffer.write(m[\"_build_mp4\"](48))' | PYTHONDONTWRITEBYTECODE=1 python -c 'from dataclasses import asdict; import json; from astrid.core.media import ffprobe_metadata_strict; p=ffprobe_metadata_strict(\"/dev/stdin\"); print(json.dumps({k:v for k,v in asdict(p).items() if k "'!= "_raw"}, sort_keys=True))'"'
PYTHONDONTWRITEBYTECODE=1 python -c 'exec(\"\"\"import json\\nimport runpy\\nfrom pathlib import Path\\nfrom astrid.core.rendering.artifacts import _compare_declared_to_expected\\nfrom astrid.core.rendering.contracts import AudioOwnership, RenderProfile\\nbackend = runpy.run_path(\\\"tests/fixtures/renderer_packs/raw_command/backend.py\\\", run_name=\\\"raw_fixture_profile\\\")\\nrequest = json.loads(Path(\\\"tests/fixtures/renderer_packs/raw_command/requests/render.json\\\").read_text())\\nresult_profile = dict(request[\\\"profile\\\"])\\nresult_profile[\\\"audio_codec\\\"] = backend[\\\"AUDIO_CODEC\\\"]\\ndeclared = RenderProfile.from_dict(result_profile)\\nexpected = RenderProfile.from_dict(request[\\\"profile\\\"])\\ntry:\\n    _compare_declared_to_expected(declared, expected, AudioOwnership.RENDERED)\\nexcept Exception as exc:\\n    error = getattr(exc, \\\"error\\\", None)\\n    print(json.dumps({\\\"request_audio_codec\\\": expected.audio_codec, \\\"result_audio_codec\\\": declared.audio_codec, \\\"exception\\\": type(exc).__name__, \\\"kind\\\": getattr(error, \\\"kind\\\", None), \\\"details\\\": getattr(exc, \\\"details\\\", None)}, sort_keys=True, default=str))\\nelse:\\n    print(\\\"profile-comparison-passed\\\")\\n\"\"\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 557ms:
{"audio_channel_layout": null, "audio_codec": "pcm_s16le", "audio_sample_rate": 48000, "audio_stream_present": true, "container": "mp4", "duration_rational": [2, 1], "duration_seconds": 2.0, "format_name": "mov,mp4,m4a,3gp,3g2,mj2", "fps": 24.0, "fps_rational": [24, 1], "height": 1080, "pixel_format": null, "resolution": "1920x1080", "time_base": [1, 12288], "video_codec": "h264", "video_level": null, "video_profile": null, "video_stream_present": true, "width": 1920}
{"details": {"actual": "pcm_s16le", "expected": "sowt", "field": "audio_codec", "reason": "audio_profile_mismatch"}, "exception": "RendererInvalidArtifactError", "kind": "invalid_artifact", "request_audio_codec": "sowt", "result_audio_codec": "pcm_s16le"}

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '245,430p' && nl -ba tests/core/rendering/test_transport.py | sed -n '1,380p' && nl -ba tests/fixtures/renderer_commands.py | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
nl: tests/fixtures/renderer_commands.py: No such file or directory
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
   226	        _run(tmp_path, {"action": "result", "payload": payload})
   227	
   228	    assert caught.value.error.kind == "protocol"
   229	    assert caught.value.error.backend == RENDERER_ID
   230	    assert caught.value.details["received"] == 2
   231	
   232	
   233	def test_success_logs_capture_and_redact_stdout_and_stderr(
   234	    tmp_path: Path,
   235	    monkeypatch: pytest.MonkeyPatch,
   236	) -> None:
   237	    secret = "transport-log-secret-value"
   238	    monkeypatch.setenv("TRANSPORT_LOG_SECRET", secret)
   239	
   240	    transport, result = _run(
   241	        tmp_path,
   242	        {
   243	            "action": "result",
   244	            "payload": _wire_fixture("result.json"),
   245	            "stdout": "render complete",
   246	            "stderr": f"OPENAI_API_KEY={secret}",
   247	        },
   248	    )
   249	
   250	    assert isinstance(result, RenderResult)
   251	    assert any("render complete" in log for log in result.logs)
   252	    assert secret not in json.dumps(result.logs)
   253	    assert "[redacted]" in transport.last_logs["stderr"]
   254	
   255	
   256	def test_environment_is_allowlisted_and_host_secrets_are_not_passed(
   257	    tmp_path: Path,
   258	    monkeypatch: pytest.MonkeyPatch,
   259	) -> None:
   260	    monkeypatch.setenv("TRANSPORT_HOST_SECRET_TOKEN", "must-not-reach-child")
   261	
   262	    _, result = _run(
   263	        tmp_path,
   264	        {
   265	            "action": "environment",
   266	            "name": "TRANSPORT_HOST_SECRET_TOKEN",
   267	            "safe_name": "LANG",
   268	            "payload": _wire_fixture("result.json"),
   269	        },
   270	        env={
   271	            "TRANSPORT_HOST_SECRET_TOKEN": "overlay-must-not-reach-child",
   272	            "LANG": "transport-safe-locale",
   273	        },
   274	    )
   275	
   276	    assert isinstance(result, RenderResult)
   277	    assert result.metadata == {
   278	        "secret_value": "absent",
   279	        "safe_value": "transport-safe-locale",
   280	    }

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'exec(\"\"\"import json\\nimport signal\\nimport sys\\nfrom pathlib import Path\\nfrom unittest.mock import Mock, patch\\nfrom astrid.core.rendering.transport import CommandTransport, _terminate_process_group\\nrequest = Path(\\\"tests/fixtures/renderer_packs/raw_command/requests/render.json\\\").resolve()\\nprocess = Mock()\\nprocess.communicate.side_effect = RuntimeError(\\\"synthetic communicate failure\\\")\\ncleanup = Mock(return_value=(\\\"\\\", \\\"\\\"))\\ntry:\\n    with patch(\\\"astrid.core.rendering.transport.subprocess.Popen\\\", return_value=process), patch(\\\"astrid.core.rendering.transport._terminate_process_group\\\", cleanup):\\n        CommandTransport(\\\"raw_command.renderer\\\").run(\\\"render\\\", [sys.executable], request_path=request, result_path=\\\"/tmp/astrid-nonexistent-result-review.json\\\", cwd=Path.cwd(), timeout=1)\\nexcept RuntimeError as exc:\\n    generic = {\\\"reraised\\\": str(exc), \\\"cleanup_calls\\\": cleanup.call_count}\\nelse:\\n    generic = {\\\"unexpected\\\": \\\"no exception\\\"}\\nclass Fake:\\n    pid = 424242\\n    returncode = None\\n    def __init__(self): self.calls = 0\\n    def communicate(self, timeout=None):\\n        self.calls += 1\\n        if self.calls <= 3: raise KeyboardInterrupt\\n        self.returncode = -signal.SIGKILL\\n        return (\\\"out\\\", \\\"err\\\")\\nfake = Fake()\\nsignals = []\\nwith patch(\\\"astrid.core.rendering.transport._signal_process_group\\\", side_effect=lambda proc, sig: signals.append(sig)), patch(\\\"astrid.core.rendering.transport._process_group_exists\\\", return_value=False):\\n    captured = _terminate_process_group(fake, grace=0.1)\\nprint(json.dumps({\\\"generic_exception\\\": generic, \\\"interrupt_cleanup\\\": {\\\"communicate_calls\\\": fake.calls, \\\"signals\\\": signals, \\\"captured\\\": captured, \\\"returncode\\\": fake.returncode}}, sort_keys=True))\\n\"\"\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 153ms:
{"generic_exception": {"cleanup_calls": 1, "reraised": "synthetic communicate failure"}, "interrupt_cleanup": {"captured": ["out", "err"], "communicate_calls": 4, "returncode": -9, "signals": [15, 9, 9, 9]}}

codex
The fresh probe uncovered a separate fixture inconsistency despite the SPS/audio codec edit: the committed request still asks for `sowt`, while the result now declares `pcm_s16le`; strict validation compares those and rejects the render. On this ffprobe build, the fixture also exposes no audio `channel_layout`, so the strict probe remains incomplete. I’m finishing the remaining lifecycle and symlink-path analysis to ensure the issue list is complete and minimal.
exec
/bin/zsh -lc 'rg -n "symlink|symbolic link|escaped_path|publication paths|previous_outputs|sidecar" .oracle/tasklist.md .oracle/plan.md docs/contracts/render-backend-v1.md tests/core/rendering astrid/core/rendering | head -n 300 && rg -n "schema_version.*bool|schema_version.*integer|unsupported request|invalid support|support request|non-object|boolean" docs/contracts/render-backend-v1.md tests/core/rendering tests/fixtures/renderer_packs/raw_command .oracle/tasklist.md | head -n 240' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/tasklist.md:38:- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
.oracle/tasklist.md:39:- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
.oracle/tasklist.md:48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
.oracle/tasklist.md:82:- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
.oracle/tasklist.md:93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
.oracle/tasklist.md:113:- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
.oracle/tasklist.md:145:**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.
.oracle/tasklist.md:157:- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
.oracle/tasklist.md:167:- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
.oracle/plan.md:39:10. **Publication:** validate in an invocation workdir, take a per-output lock, rename the video, then atomically write the hashed provenance sidecar as the commit marker. A crash may leave a detectable orphaned video, but never a sidecar claiming an incomplete artifact.
.oracle/plan.md:114:  - For installed candidates, verify the active symlink’s revision and installation trust audit; deny execution for missing, corrupt, or mismatched records. Keep such candidates inspectable for diagnosis. Do not expose staging or inactive revisions through normal discovery.
.oracle/plan.md:151:  - Add renderer-local artifact enforcement for existence, non-empty output, workspace containment, symlinks, hashes, duration, video profile, and audio ownership.
.oracle/plan.md:153:  - Add a locked publication helper in which the sidecar is the final commit marker.
.oracle/plan.md:164:    - cover the three package registries, shim families, active-theme symlink/text pointer, and registry state;
.oracle/plan.md:221:    9. publish video and sidecar.
.oracle/plan.md:251:  - Ensure plain FFmpeg, FFmpeg fast paths, audio-reactive, Remotion, and single-segment hybrid produce exactly one sidecar.
.oracle/plan.md:252:  - Make previous-output cleanup lock-aware and conservative around corrupt/orphaned pairs; never delete unrelated output solely because a sidecar is unreadable.
.oracle/plan.md:253:  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.
.oracle/plan.md:429:  - Verify every successful facade/service path produces one validated video and one committed sidecar.
.oracle/plan.md:443:- Corrected caller migration to distinguish attached facade paths from public-service paths while preserving one ledger and one matching sidecar.
.oracle/plan.md:449:- A valid active symlink with a corrupt install record must remain inspectable while being excluded from execution.
.oracle/plan.md:455:- Video plus sidecar cannot be atomically renamed as one filesystem object; the sidecar remains the commit marker and orphan recovery is required.
docs/contracts/render-backend-v1.md:8:workspace containment after symlink resolution.
docs/contracts/render-backend-v1.md:235:host resolves the path, rejects symlink escapes, requires the expected file or
docs/contracts/render-backend-v1.md:253:symlinks, digest, duration, dimensions, FPS/time base, container, codecs,
docs/contracts/render-backend-v1.md:450:   atomically write the hashed provenance sidecar as the commit marker.
docs/contracts/render-backend-v1.md:459:unrelated prior output. A crash can leave an orphan video, but never a sidecar
docs/contracts/render-backend-v1.md:460:claiming an incomplete artifact; the sidecar is the publication commit marker.
astrid/core/rendering/registry.py:727:    if not active_link.is_symlink():
astrid/core/rendering/registry.py:728:        return _PackTrust(False, "installed pack has no active revision symlink")
astrid/core/rendering/registry.py:732:        return _PackTrust(False, "installed pack active revision symlink is broken")
astrid/core/rendering/publication.py:1:"""Locked publication for one rendered video and its provenance sidecar.
astrid/core/rendering/publication.py:3:The provenance sidecar is the commit marker.  A video without a valid
astrid/core/rendering/publication.py:4:sidecar is deliberately visible (and therefore recoverable), but it is never
astrid/core/rendering/publication.py:83:def _default_sidecar_path(video_path: Path) -> Path:
astrid/core/rendering/publication.py:130:    sidecar_path: str | Path | None = None,
astrid/core/rendering/publication.py:140:    sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
astrid/core/rendering/publication.py:143:        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
astrid/core/rendering/publication.py:144:        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
astrid/core/rendering/publication.py:146:        if video.is_symlink() or sidecar.is_symlink():
astrid/core/rendering/publication.py:148:        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
astrid/core/rendering/publication.py:150:        payload = json.loads(sidecar.read_text(encoding="utf-8"))
astrid/core/rendering/publication.py:178:    sidecar_path: str | Path | None = None,
astrid/core/rendering/publication.py:180:    """Return whether the video-plus-sidecar pair is committed."""
astrid/core/rendering/publication.py:182:    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
astrid/core/rendering/publication.py:188:        raw_sidecar = candidate.get("sidecar_path", candidate.get("sidecar"))
astrid/core/rendering/publication.py:192:        return video, _resolved(raw_sidecar or _default_sidecar_path(video))
astrid/core/rendering/publication.py:198:        return video, _resolved(_default_sidecar_path(video))
astrid/core/rendering/publication.py:202:def _delete_previous_outputs(
astrid/core/rendering/publication.py:203:    previous_outputs: Iterable[object],
astrid/core/rendering/publication.py:211:    for candidate in previous_outputs:
astrid/core/rendering/publication.py:218:        video, sidecar = pair
astrid/core/rendering/publication.py:219:        # Never delete through a symlink: the raw candidate path must not be
astrid/core/rendering/publication.py:224:            if raw_path.is_symlink():
astrid/core/rendering/publication.py:242:            provenance = read_committed_provenance(video, sidecar_path=sidecar)
astrid/core/rendering/publication.py:248:                sidecar.unlink()
astrid/core/rendering/publication.py:264:    sidecar_path: str | Path,
astrid/core/rendering/publication.py:265:    previous_outputs: Iterable[object] = (),
astrid/core/rendering/publication.py:271:    place with :func:`os.replace`, and the complete sidecar is written
astrid/core/rendering/publication.py:272:    atomically last.  A sidecar-write failure therefore leaves a detectable,
astrid/core/rendering/publication.py:281:    sidecar = _resolved(sidecar_path)
astrid/core/rendering/publication.py:284:    sidecar_unresolved = Path(sidecar_path).expanduser()
astrid/core/rendering/publication.py:285:    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
astrid/core/rendering/publication.py:288:            message="publication paths must not be symbolic links",
astrid/core/rendering/publication.py:294:    sidecar.parent.mkdir(parents=True, exist_ok=True)
astrid/core/rendering/publication.py:303:        sidecar.unlink(missing_ok=True)
astrid/core/rendering/publication.py:309:        write_json_atomic(sidecar, committed_payload)
astrid/core/rendering/publication.py:313:        _delete_previous_outputs(
astrid/core/rendering/publication.py:314:            previous_outputs,
astrid/core/rendering/publication.py:321:        if read_committed_provenance(output, sidecar_path=sidecar) is None:
astrid/core/rendering/provenance.py:392:    """Assemble and atomically write a provenance v2 sidecar."""
astrid/core/rendering/transport.py:415:        if result_path.is_dir() and not result_path.is_symlink():
tests/core/rendering/test_publication.py:21:def _sidecar(video: Path) -> Path:
tests/core/rendering/test_publication.py:28:    sidecar = _sidecar(video)
tests/core/rendering/test_publication.py:30:        sidecar,
tests/core/rendering/test_publication.py:38:    return sidecar
tests/core/rendering/test_publication.py:41:def test_happy_path_publishes_video_then_hashed_sidecar(tmp_path: Path) -> None:
tests/core/rendering/test_publication.py:46:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:52:        sidecar_path=sidecar,
tests/core/rendering/test_publication.py:53:        previous_outputs=(),
tests/core/rendering/test_publication.py:59:    payload = json.loads(sidecar.read_text(encoding="utf-8"))
tests/core/rendering/test_publication.py:62:    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
tests/core/rendering/test_publication.py:63:    assert is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:74:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:76:    first_in_sidecar_write = threading.Event()
tests/core/rendering/test_publication.py:87:    def blocking_sidecar_write(path: str | Path, payload: object) -> None:
tests/core/rendering/test_publication.py:89:            first_in_sidecar_write.set()
tests/core/rendering/test_publication.py:94:    monkeypatch.setattr(publication, "write_json_atomic", blocking_sidecar_write)
tests/core/rendering/test_publication.py:103:                sidecar_path=sidecar,
tests/core/rendering/test_publication.py:104:                previous_outputs=(),
tests/core/rendering/test_publication.py:112:    assert first_in_sidecar_write.wait(timeout=5)
tests/core/rendering/test_publication.py:125:    payload = read_committed_provenance(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:133:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:136:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:137:    assert not is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:140:        sidecar,
tests/core/rendering/test_publication.py:147:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:148:    assert not is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:156:        sidecar_path=sidecar,
tests/core/rendering/test_publication.py:157:        previous_outputs=(),
tests/core/rendering/test_publication.py:160:    assert is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:170:    matching_sidecar = _committed_pair(matching, contents=b"old", timeline=timeline)
tests/core/rendering/test_publication.py:171:    nonmatching_sidecar = _committed_pair(
tests/core/rendering/test_publication.py:178:    wrong_hash_sidecar = _sidecar(wrong_hash)
tests/core/rendering/test_publication.py:180:        wrong_hash_sidecar,
tests/core/rendering/test_publication.py:191:    live_sidecar = _sidecar(live)
tests/core/rendering/test_publication.py:196:        sidecar_path=live_sidecar,
tests/core/rendering/test_publication.py:197:        previous_outputs=[
tests/core/rendering/test_publication.py:207:    assert not matching_sidecar.exists()
tests/core/rendering/test_publication.py:209:    assert nonmatching_sidecar.exists()
tests/core/rendering/test_publication.py:211:    assert not _sidecar(missing_marker).exists()
tests/core/rendering/test_publication.py:213:    assert wrong_hash_sidecar.exists()
tests/core/rendering/test_publication.py:215:    assert live_sidecar.exists()
tests/core/rendering/test_publication.py:216:    assert is_render_result_committed(live, sidecar_path=live_sidecar)
tests/core/rendering/test_publication.py:244:            sidecar_path=_sidecar(output),
tests/core/rendering/test_publication.py:245:            previous_outputs=(),
tests/core/rendering/test_publication.py:252:    assert not _sidecar(output).exists()
tests/core/rendering/test_publication.py:255:def test_sidecar_write_failure_leaves_recoverable_uncommitted_video(
tests/core/rendering/test_publication.py:261:    sidecar = _sidecar(output)
tests/core/rendering/test_publication.py:263:    def fail_sidecar(_path: str | Path, _payload: object) -> None:
tests/core/rendering/test_publication.py:264:        raise AtomicWriteError("synthetic sidecar failure")
tests/core/rendering/test_publication.py:266:    monkeypatch.setattr(publication, "write_json_atomic", fail_sidecar)
tests/core/rendering/test_publication.py:267:    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
tests/core/rendering/test_publication.py:272:            sidecar_path=sidecar,
tests/core/rendering/test_publication.py:273:            previous_outputs=(),
tests/core/rendering/test_publication.py:278:    assert not sidecar.exists()
tests/core/rendering/test_publication.py:279:    assert not is_render_result_committed(output, sidecar_path=sidecar)
astrid/core/rendering/assets.py:126:    """Stage a validated local file without following a later symlink swap."""
astrid/core/rendering/assets.py:137:            os.link(source, destination, follow_symlinks=False)
astrid/core/rendering/assets.py:138:            destination_stat = os.stat(destination, follow_symlinks=False)
astrid/core/rendering/assets.py:267:        """Open a project asset component-by-component without symlink traversal."""
astrid/core/rendering/assets.py:317:                    follow_symlinks=False,
astrid/core/rendering/assets.py:319:                destination_stat = os.stat(destination, follow_symlinks=False)
astrid/core/rendering/artifacts.py:140:        _invalid("escaped_path", f"{label} must not be absolute", path=raw)
astrid/core/rendering/artifacts.py:147:            "escaped_path",
astrid/core/rendering/artifacts.py:157:    if candidate.is_symlink():
astrid/core/rendering/artifacts.py:159:            "escaped_path",
astrid/core/rendering/artifacts.py:160:            f"{label} must not be a symbolic link: {relative}",
astrid/core/rendering/artifacts.py:176:            "escaped_path",
tests/core/rendering/test_artifacts.py:163:        reason="escaped_path",
tests/core/rendering/test_artifacts.py:167:def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
tests/core/rendering/test_artifacts.py:172:    (workspace / "escape.mp4").symlink_to(outside)
tests/core/rendering/test_artifacts.py:181:        reason="escaped_path",
tests/core/rendering/test_artifacts.py:392:        reason="escaped_path",
tests/core/rendering/test_raw_command_fixture.py:94:    (install_root / "active").symlink_to(Path("revisions") / PACK_ID)
tests/core/rendering/test_assets.py:239:def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
tests/core/rendering/test_assets.py:245:    link.symlink_to(outside)
tests/core/rendering/test_assets.py:255:def test_symlink_to_contained_file_is_staged_safely(tmp_path: Path) -> None:
tests/core/rendering/test_assets.py:262:    link.symlink_to(source)
tests/core/rendering/test_contracts.py:615:    sidecar = tmp_path / "video.mp4.provenance.json"
tests/core/rendering/test_contracts.py:616:    assert write_provenance_v2(sidecar, **kwargs) == payload
tests/core/rendering/test_contracts.py:617:    assert sidecar.read_text(encoding="utf-8").endswith("\n")
tests/core/rendering/test_contracts.py:656:    plan wire round-trip and the final provenance sidecar."""
tests/core/rendering/test_contracts.py:695:    # Provenance sidecar carries the same evidence
tests/core/rendering/test_registry.py:169:        (install_root / "active").symlink_to(Path("revisions") / pack_id)
tests/core/rendering/test_registry_matrix.py:149:    (install_root / "active").symlink_to(Path("revisions") / pack_id)
docs/contracts/render-backend-v1.md:75:Renderer capability hints cover clip and track types, boolean/string features,
docs/contracts/render-backend-v1.md:143:JSON numbers must be finite. Python booleans do not count as integers. Fixed
docs/contracts/render-backend-v1.md:194:- `schema_version` (required integer `1`);
docs/contracts/render-backend-v1.md:325:- `features`, a string-keyed map of boolean or string evidence;
docs/contracts/render-backend-v1.md:415:| `schema_version` | Required integer `1`. |
docs/contracts/render-backend-v1.md:422:Unknown, missing, boolean, non-integer, or unsupported versions on requests,
docs/contracts/render-backend-v1.md:562:`RenderResult`, and `RendererError`; missing, boolean, malformed, and unknown
tests/core/rendering/test_schema_roundtrip.py:201:        ("boolean total", _set(base, ("total_frames",), True)),
tests/core/rendering/test_schema_roundtrip.py:244:        ("error boolean version", _set(error, ("schema_version",), True)),
tests/core/rendering/test_schema_roundtrip.py:300:        ("boolean version", _set(base, ("schema_version",), True)),
tests/core/rendering/test_schema_roundtrip.py:320:        ("boolean version", _set(base, ("schema_version",), True)),
tests/core/rendering/test_contracts.py:314:@pytest.mark.parametrize("case", ["missing", "boolean", "malformed", "unknown"])
tests/core/rendering/test_contracts.py:326:            "boolean": True,
tests/fixtures/renderer_packs/raw_command/backend.py:412:            f"unsupported request schema_version {request.get('schema_version')!r}; expected 1"
tests/fixtures/renderer_packs/raw_command/backend.py:554:                f"invalid support request: {exc}",

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '130,270p' && nl -ba docs/contracts/render-backend-v1.md | sed -n '400,470p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '285,350p' && nl -ba tests/core/rendering/test_artifacts.py | sed -n '350,420p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   191	
   192	`RenderRequest` contains:
   193	
   194	- `schema_version` (required integer `1`);
   195	- `timeline_path` (required input path);
   196	- optional nullable `assets_registry_path`;
   197	- `output_name`, a portable basename with no separator or traversal;
   198	- nullable `window` (`null` means the complete timeline);
   199	- nullable requested `audio` ownership (`null` means backend default);
   200	- nullable `profile` (`null` means the host resolves the canonical profile);
   201	- `backend_config`, an object keyed only by qualified implementation IDs;
   202	- string-to-string `metadata`, for correlation data such as project, run, or
   203	  session IDs.
   204	
   205	The timeline stays backend-neutral. No Remotion, FFmpeg, Blender, Unreal, or
   206	other implementation field may appear at the request top level. Configuration
   207	is scoped like this:
   208	
   209	```json
   210	{
   211	  "backend_config": {
   212	    "acme.example": {"quality": "preview"},
   213	    "rendering.ffmpeg-finalizer": {"faststart": true}
   214	  }
   215	}
   216	```
   217	
   218	Before invoking an implementation, the host removes unrelated namespaces.
   219	The renderer receives an empty mapping or only its own namespace. A finalize
   220	request carries an empty mapping or only its selected finalizer's namespace.
   221	Backends must ignore no unknown core fields: unknown core fields are protocol
   222	errors.
   223	
   224	## Assets and workspace paths
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
   411	A `RendererError` contains:
   412	
   413	| Field | Meaning |
   414	| --- | --- |
   415	| `schema_version` | Required integer `1`. |
   416	| `kind` | One of `protocol`, `unsupported`, `binary_missing`, `timeout`, `interrupted`, `invalid_artifact`, or `internal`. |
   417	| `backend` | Qualified implementation ID; host validation uses `astrid.core`. |
   418	| `message` | Non-empty actionable message. |
   419	| `recovery_command` | Nullable concrete recovery command or action. |
   420	| `details` | JSON-safe structured evidence. |
   421	
   422	Unknown, missing, boolean, non-integer, or unsupported versions on requests,
   423	support reports, plans, finalize requests, successful results, and error
   424	results are always `kind="protocol"`. So are malformed request/result JSON and
   425	missing authoritative results. Unsupported timelines use `unsupported`; a
   426	missing manifest-declared executable uses `binary_missing`; deadline expiry
   427	uses `timeout`; transport cancellation uses `interrupted`; missing, escaping,
   428	empty, hash-mismatched, or media-incompatible outputs use
   429	`invalid_artifact`; unexpected implementation bugs use `internal`.
   430	
   431	The host cleans and reaps children before surfacing interruption. A real user
   432	SIGINT/`KeyboardInterrupt` is then re-raised so normal exit-130 behavior is
   433	preserved rather than converted into an unrelated exit-code layer.
   434	
   435	## Lifecycle, publication, and cleanup
   436	
   437	The host lifecycle is:
   438	
   439	1. Resolve legacy selector/policy, aliases, overrides, and the precedence
   440	   winner.
   441	2. Verify trust eligibility, permissions, manifest digest, required binaries,
   442	   and supported protocol version.
   443	3. Resolve the canonical timeline profile and localize required inputs into a
   444	   unique invocation workspace.
   445	4. Obtain static and, where available, request-sensitive support evidence.
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
   285	    assert configured.for_backend("acme.example").backend_config == {
   286	        "acme.example": {"quality": "high"}
   287	    }
   288	
   289	
   290	def _versioned_payloads() -> dict[str, tuple[Callable[[dict[str, Any]], Any], dict[str, Any]]]:
   291	    request = RenderRequest(
   292	        schema_version=1,
   293	        timeline_path="/workspace/timeline.json",
   294	        output_name="video.mp4",
   295	    ).to_dict()
   296	    error = RendererError(
   297	        schema_version=1,
   298	        kind="unsupported",
   299	        backend="acme.example",
   300	        message="unsupported",
   301	        recovery_command=None,
   302	        details={},
   303	    ).to_dict()
   304	    return {
   305	        "request": (RenderRequest.from_dict, request),
   306	        "support": (SupportReport.from_dict, _support().to_dict()),
   307	        "plan": (RenderPlan.from_dict, _plan().to_dict()),
   308	        "finalize": (FinalizeRequest.from_dict, _finalize().to_dict()),
   309	        "result-success": (parse_wire_result, _result().to_dict()),
   310	        "result-error": (parse_wire_result, error),
   311	    }
   312	
   313	
   314	@pytest.mark.parametrize("case", ["missing", "boolean", "malformed", "unknown"])
   315	@pytest.mark.parametrize("operation", list(_versioned_payloads()))
   316	def test_every_wire_reader_rejects_missing_malformed_or_unknown_versions(
   317	    operation: str,
   318	    case: str,
   319	) -> None:
   320	    parser, base = _versioned_payloads()[operation]
   321	    payload = deepcopy(base)
   322	    if case == "missing":
   323	        payload.pop("schema_version")
   324	    else:
   325	        payload["schema_version"] = {
   326	            "boolean": True,
   327	            "malformed": "1",
   328	            "unknown": 2,
   329	        }[case]
   330	    with pytest.raises(RendererProtocolError) as caught:
   331	        parser(payload)
   332	    assert caught.value.error.kind == "protocol"
   333	    assert caught.value.error.backend == "astrid.core"
   334	
   335	
   336	def test_unknown_request_top_level_field_is_protocol_error() -> None:
   337	    with pytest.raises(RendererProtocolError):
   338	        RenderRequest.from_dict(
   339	            {
   340	                "schema_version": 1,
   341	                "timeline_path": "/workspace/timeline.json",
   342	                "output_name": "video.mp4",
   343	                "remotion_composition": "TimelineComposition",
   344	            }
   345	        )
   346	
   347	
   348	@pytest.mark.parametrize(
   349	    ("start", "end"),
   350	    [(-1, 1), (0, 0), (2, 2), (3, 2), (True, 2)],
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
   381	    )
   382	
   383	
   384	def test_invalid_attachment_path_is_rejected(tmp_path: Path) -> None:
   385	    result, attachment = _attachment_result(tmp_path)
   386	    object.__setattr__(attachment, "path", "../data.bin")
   387	
   388	    _assert_invalid(
   389	        lambda: validate_render_result(
   390	            result, expected_profile=_profile(), workspace_root=tmp_path
   391	        ),
   392	        reason="escaped_path",
   393	    )
   394	
   395	
   396	def test_invalid_attachment_kind_is_rejected(tmp_path: Path) -> None:
   397	    result, attachment = _attachment_result(tmp_path)
   398	    object.__setattr__(attachment, "kind", "Bad Kind")
   399	
   400	    _assert_invalid(
   401	        lambda: validate_render_result(
   402	            result, expected_profile=_profile(), workspace_root=tmp_path
   403	        ),
   404	        reason="invalid_attachment_kind",
   405	    )
   406	
   407	
   408	def test_attachment_hash_mismatch_is_rejected(tmp_path: Path) -> None:
   409	    result, attachment = _attachment_result(tmp_path)
   410	    object.__setattr__(attachment, "sha256", "a" * 64)
   411	
   412	    _assert_invalid(
   413	        lambda: validate_render_result(
   414	            result, expected_profile=_profile(), workspace_root=tmp_path
   415	        ),
   416	        reason="hash_mismatch",
   417	    )

exec
/bin/zsh -lc "rg -n \"publish_render_result\\(\" -g '*.py' . && rg -n \"out_path\\s*=.*resolve|sidecar.*resolve|render_result.*publish\" astrid/packs/rendering astrid/core | head -n 240 && nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1400,1490p' && nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1490,1555p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
./tests/core/rendering/test_publication.py:48:    result = publish_render_result(
./tests/core/rendering/test_publication.py:99:            publish_render_result(
./tests/core/rendering/test_publication.py:152:    publish_render_result(
./tests/core/rendering/test_publication.py:192:    publish_render_result(
./tests/core/rendering/test_publication.py:240:        publish_render_result(
./tests/core/rendering/test_publication.py:268:        publish_render_result(
./astrid/packs/rendering/executors/render/run.py:466:        output = publish_render_result(
./astrid/packs/rendering/executors/render/run.py:713:        output = publish_render_result(
./astrid/packs/rendering/executors/render/run.py:1231:        output = publish_render_result(
./astrid/packs/rendering/executors/render/run.py:1413:            output = publish_render_result(
./astrid/core/rendering/publication.py:259:def publish_render_result(
astrid/packs/rendering/executors/render/audio_reactive_colour.py:384:    out_path = out_path.resolve()
astrid/core/cli/project.py:367:    out_path = Path(args.out).expanduser().resolve()
astrid/core/cli/timeline_output.py:49:    out_path = Path(args.out).expanduser().resolve()
astrid/core/cli/timeline_events.py:622:        out_path = Path(out_path_raw).expanduser().resolve()
astrid/packs/rendering/executors/render/run.py:446:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:661:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:976:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1185:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1290:    out_path = out_path.resolve()
astrid/packs/rendering/executors/render/run.py:1459:    out_path = out_path.resolve()
astrid/core/rendering/publication.py:140:    sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
astrid/core/rendering/publication.py:143:        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
astrid/core/rendering/publication.py:144:        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
astrid/core/rendering/publication.py:281:    sidecar = _resolved(sidecar_path)
astrid/core/rendering/publication.py:284:    sidecar_unresolved = Path(sidecar_path).expanduser()
astrid/core/rendering/publication.py:285:    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
astrid/core/pack/install_git.py:262:    checkout_path = Path(checkout).resolve()
astrid/packs/rendering/executors/timeline_storyboard/run.py:550:    out_path = out_path.expanduser().resolve()
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
  1459	    out_path = out_path.resolve()
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
  1506	            with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
  1507	                assets_path = Path(tmp_text) / "hype.assets.json"
  1508	                _write_empty_asset_registry(assets_path)
  1509	                output = render(
  1510	                    args.timeline,
  1511	                    assets_path,
  1512	                    args.out,
  1513	                    engine=args.engine,
  1514	                    project_dir=args.project_dir,
  1515	                    composition_id=args.composition,
  1516	                    theme_path=args.theme,
  1517	                    min_free_gb=args.min_free_gb,
  1518	                    keep_previous_renders=args.keep_previous_renders,
  1519	                )
  1520	        else:
  1521	            output = render(
  1522	                args.timeline,
  1523	                args.assets,
  1524	                args.out,
  1525	                engine=args.engine,
  1526	                project_dir=args.project_dir,
  1527	                composition_id=args.composition,
  1528	                theme_path=args.theme,
  1529	                min_free_gb=args.min_free_gb,
  1530	                keep_previous_renders=args.keep_previous_renders,
  1531	            )
  1532	    except Exception as exc:  # pragma: no cover - CLI path
  1533	        print(str(exc), file=sys.stderr)
  1534	        return 1
  1535	    print(output)
  1536	    return 0
  1537	
  1538	
  1539	if __name__ == "__main__":
  1540	    raise SystemExit(main())

exec
/bin/zsh -lc "nl -ba astrid/core/media.py | sed -n '130,270p' && ffprobe -version | head -n 3" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 5ms:
ffprobe version 7.1.1 Copyright (c) 2007-2025 the FFmpeg developers
built with Apple clang version 17.0.0 (clang-1700.0.13.3)
configuration: --prefix=/opt/homebrew/Cellar/ffmpeg/7.1.1_3 --enable-shared --enable-pthreads --enable-version3 --cc=clang --host-cflags= --host-ldflags='-Wl,-ld_classic' --enable-ffplay --enable-gnutls --enable-gpl --enable-libaom --enable-libaribb24 --enable-libbluray --enable-libdav1d --enable-libharfbuzz --enable-libjxl --enable-libmp3lame --enable-libopus --enable-librav1e --enable-librist --enable-librubberband --enable-libsnappy --enable-libsrt --enable-libssh --enable-libsvtav1 --enable-libtesseract --enable-libtheora --enable-libvidstab --enable-libvmaf --enable-libvorbis --enable-libvpx --enable-libwebp --enable-libx264 --enable-libx265 --enable-libxml2 --enable-libxvid --enable-lzma --enable-libfontconfig --enable-libfreetype --enable-frei0r --enable-libass --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopenjpeg --enable-libspeex --enable-libsoxr --enable-libzmq --enable-libzimg --disable-libjack --disable-indev=jack --enable-videotoolbox --enable-audiotoolbox --enable-neon

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"size\"); print(len(m[\"_build_mp4\"](48)))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 237ms:
679408

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import base64,runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); print(\"data:video/mp4;base64,\"+base64.b64encode(m[\"_build_mp4\"](48)).decode())' | PYTHONDONTWRITEBYTECODE=1 python -c 'import sys; from dataclasses import asdict; import json; from astrid.core.media import ffprobe_metadata_strict; uri=sys.stdin.read(); p=ffprobe_metadata_strict(uri); print(json.dumps({k:v for k,v in asdict(p).items() if k "'!= "_raw"}, sort_keys=True))'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 503ms:
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py", line 308, in ffprobe_metadata_strict
    return _ffprobe_metadata(file_path, timeout=timeout, strict=True)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/media.py", line 262, in _ffprobe_metadata
    raise MediaProbeError(f"ffprobe failed with exit {proc.returncode}{suffix}")
astrid.core.media.MediaProbeError: ffprobe failed with exit 1

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); sys.stdout.buffer.write(m[\"_build_mp4\"](48))' | ffprobe -v quiet -print_format json -show_format -show_streams pipe:0" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 291ms:
{
    "streams": [
        {
            "index": 0,
            "codec_name": "h264",
            "codec_long_name": "H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10",
            "codec_type": "video",
            "codec_tag_string": "avc1",
            "codec_tag": "0x31637661",
            "width": 1920,
            "height": 1080,
            "coded_width": 1920,
            "coded_height": 1080,
            "closed_captions": 0,
            "film_grain": 0,
            "has_b_frames": 0,
            "level": -99,
            "refs": 1,
            "is_avc": "true",
            "nal_length_size": "4",
            "id": "0x1",
            "r_frame_rate": "24/1",
            "avg_frame_rate": "24/1",
            "time_base": "1/12288",
            "start_pts": 0,
            "start_time": "0.000000",
            "duration_ts": 24576,
            "duration": "2.000000",
            "bit_rate": "1176576",
            "nb_frames": "48",
            "extradata_size": 26,
            "disposition": {
                "default": 1,
                "dub": 0,
                "original": 0,
                "comment": 0,
                "lyrics": 0,
                "karaoke": 0,
                "forced": 0,
                "hearing_impaired": 0,
                "visual_impaired": 0,
                "clean_effects": 0,
                "attached_pic": 0,
                "timed_thumbnails": 0,
                "non_diegetic": 0,
                "captions": 0,
                "descriptions": 0,
                "metadata": 0,
                "dependent": 0,
                "still_image": 0,
                "multilayer": 0
            },
            "tags": {
                "language": "und",
                "handler_name": "VideoHandler",
                "vendor_id": "[0][0][0][0]",
                "encoder": "awCommand"
            }
        },
        {
            "index": 1,
            "codec_name": "pcm_s16le",
            "codec_long_name": "PCM signed 16-bit little-endian",
            "codec_type": "audio",
            "codec_tag_string": "sowt",
            "codec_tag": "0x74776f73",
            "sample_fmt": "s16",
            "sample_rate": "48000",
            "channels": 2,
            "bits_per_sample": 16,
            "initial_padding": 0,
            "id": "0x2",
            "r_frame_rate": "0/0",
            "avg_frame_rate": "0/0",
            "time_base": "1/48000",
            "start_pts": 0,
            "start_time": "0.000000",
            "duration_ts": 96000,
            "duration": "2.000000",
            "bit_rate": "1536000",
            "nb_frames": "1",
            "disposition": {
                "default": 1,
                "dub": 0,
                "original": 0,
                "comment": 0,
                "lyrics": 0,
                "karaoke": 0,
                "forced": 0,
                "hearing_impaired": 0,
                "visual_impaired": 0,
                "clean_effects": 0,
                "attached_pic": 0,
                "timed_thumbnails": 0,
                "non_diegetic": 0,
                "captions": 0,
                "descriptions": 0,
                "metadata": 0,
                "dependent": 0,
                "still_image": 0,
                "multilayer": 0
            },
            "tags": {
                "language": "und",
                "handler_name": "SoundHandler",
                "vendor_id": "[0][0][0][0]"
            }
        }
    ],
    "format": {
        "filename": "pipe:0",
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
