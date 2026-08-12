Reading additional input from stdin...
2026-08-12T12:24:35.706477Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:24:35.706509Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:24:35.706515Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff5ee-7d82-7b70-93c9-f90f176fac97
--------
user
# Megado Checkpoint — Batch 3 third re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-3.md (8), -r1 (6), -r2 (4). Third rework committed as
`a7b7b080` (prior head 58473c3a). Incremental diff at /tmp/batch3-r3.diff.

## How each of your 4 re-review2 issues was addressed (host-implemented)

1. **Remotion doesn't enforce always-rendered audio** → the remotion render
   command now passes `--enforce-audio-track` (Remotion 4.0.455 default is
   false, so visual-only/muted timelines would otherwise render without
   audio despite support/manifest promising rendered AAC).
2. **FFmpeg time-base formula wrong + rational gaps** →
   `_profile_support_reasons` now uses the CANONICAL `_mp4_time_base`
   doubling rule (24→12288, 30→15360, 60→15360) from `profile.py` instead of
   `fps*512`; fps/time_base compared via `Fraction` equality (non-integral
   FPS and equivalent rationals handled); `video_profile`/`video_level`
   remain unpinned by the command (encoder default) — support does not
   falsely promise them.
3. **Stream-copy ignores probed time base** →
   `_whole_media_optimization` now requires the probed `time_base` to equal
   the canonical MP4 timescale via `_probe_time_base_matches` (an H.264
   source at 1/90000 for a 1/15360 request is no longer copied).
4. **50ms duration tolerance lets extra frames through** →
   frame-accurate tolerance `0.5/fps` (half a frame each way) replaces the
   coarse 50ms window; extra trailing frames at high FPS cannot pass.

## Evidence

- Incremental diff: /tmp/batch3-r3.diff (5 files)
- Host-verified: 106 combined backend/finalizer/locking tests pass; full
  consolidated acceptance = 835 passed, 1 failed (SAME pre-existing
  model-trends env failure), 2 skipped.

## Verdict

Binary: `PASS` or a list of issues. If PASS, say exactly `PASS` so Batch 4
may begin.
codex
I’m using the `megado` checkpoint workflow to independently verify the incremental commit and each of the four prior findings. I’ll keep the worktree read-only and return only the required binary verdict.
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

2026-08-12T12:24:58.618706Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:24:58.619057Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:24:58.619080Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "rg --files .oracle | sort | rg 'batch-3|tasklist|status|plan'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/briefs/05-hybrid-planner-canvas.md
.oracle/briefs/batch-3-t3.1.md
.oracle/briefs/batch-3-t3.2.md
.oracle/briefs/batch-3-t3.3.md
.oracle/briefs/batch-3-t3.4.md
.oracle/briefs/batch-3-t3.5.md
.oracle/briefs/batch-3-t3.6.md
.oracle/checkins/batch-3-r1.md
.oracle/checkins/batch-3-r2.md
.oracle/checkins/batch-3-r3.md
.oracle/checkins/batch-3.md
.oracle/findings/05-hybrid-planner-canvas.meta.json
.oracle/findings/05-hybrid-planner-canvas.txt
.oracle/plan-v1.txt
.oracle/plan.md
.oracle/tasklist.md

exec
/bin/zsh -lc "wc -l /tmp/batch3-r3.diff && sed -n '1,260p' /tmp/batch3-r3.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   14531 /tmp/batch3-r3.diff
diff --git a/.oracle/checkins/batch-3-r2.md b/.oracle/checkins/batch-3-r2.md
new file mode 100644
index 00000000..7ea91a8e
--- /dev/null
+++ b/.oracle/checkins/batch-3-r2.md
@@ -0,0 +1,14396 @@
+Reading additional input from stdin...
+2026-08-12T12:01:06.961123Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T12:01:06.965031Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T12:01:06.965046Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff5d8-f77d-7153-b48d-78e9b114f468
+--------
+user
+# Megado Checkpoint — Batch 3 second re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-3.md (8), batch-3-r1.md (6). Second rework committed as
+`58473c3a` (prior head 72b70944). Incremental diff at /tmp/batch3-r2.diff.
+
+## How each of your 6 re-review1 issues was addressed (host-implemented)
+
+1. **Launcher not env-authoritative** → `_selects_finalizer` now checks the
+   transport-selected backend id FIRST and returns False for any other id; a
+   `rendering.remotion` invocation with a finalizer namespace in the request
+   can never route to the finalizer.
+2. **Remotion support/render inconsistent** → support now forces the FULL
+   render profile (time_base 1/90000 + AAC 48k stereo) when comparing the
+   request profile, so a visual-only profile fails closed and the actual
+   rendered profile is accepted; manifest `audio_ownership` narrowed to
+   `[rendered]`.
+3. **FFmpeg profile validation misses time_base** → added time_base
+   `(1, fps*512)` comparison to `_profile_support_reasons`.
+4. **Audio-reactive hard-codes 44.1kHz** → `AudioReactiveColourSpec` gains
+   `audio_sample_rate` (default 48000) and `build_mux_command` uses it.
+5. **Stream-copy not gated on whole-source compatibility** →
+   `_whole_media_optimization` now also requires probed `video_codec == h264`
+   and `pixel_format == yuv420p`; `build_render_command` requires
+   `report.supported` before consuming `stream_copy`.
+6. **Legacy facade TOCTOU** → new `build_render_command_from_data` builds
+   from the EXACT mappings the facade validated with strict support (no
+   reload); the facade path uses it.
+
+## Evidence
+
+- Incremental diff: /tmp/batch3-r2.diff (10 files)
+- Host-verified: 106 combined backend/finalizer/locking tests pass; full
+  consolidated acceptance = 835 passed, 1 failed (SAME pre-existing
+  env-dependent model-trends fixture failure), 2 skipped. Remotion typecheck
+  passes; real Remotion + FFmpeg smokes pass.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. If PASS, say exactly `PASS` so Batch 4
+may begin.
+warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
+codex
+I’m using the Megado checkpoint workflow and the repo’s context-minimizing review posture. I’ll inspect the incremental diff, delegate independent adversarial checks, and return only the required binary verdict or concrete issues.
+exec
+/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
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
+
+exec
+/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/megado/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+exec
+/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
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
+**Default to the hermes agentic pathway, and to DeepSeek Flash within it** — different model family, cheap, fast, tool-using. Reach for DeepSeek Pro only when the task needs reasoning judgement; reach for Codex or Claude only when you specifically want their strengths.
+
+> **⚠️ Network sandbox warning for Codex subagents**
+> `codex exec` runs its subprocess with `CODEX_SANDBOX_NETWORK_DISABLED=1`. Hermes agents (DeepSeek/Kimi/MiMo/GLM/OpenRouter) need outbound network to reach their provider APIs, so **launching them from inside a `codex exec` subagent will fail**. The launcher itself is fine; it fails only because the parent process has no network.
+>
+> **Workarounds:**
+> 1. Launch the hermes subagent directly from a normal shell or Bash tool.
+> 2. If you need a **Codex subagent to orchestrate hermes subagents**, run the
+>    outer Codex command with `--sandbox danger-full-access` and seal stdin with
+>    `</dev/null`, for example:
+>
+>    ```bash
+>    timeout 3600 codex exec --sandbox danger-full-access \
+>      -c model_reasoning_effort=high \
+>      "$(cat /tmp/brief.md)" </dev/null
+>    ```
+>
+>    `read-only` and `workspace-write` both disable outbound network for the
+>    Codex subprocess; only `danger-full-access` allows nested Hermes provider
+>    API calls from inside `codex exec`. Tell Codex explicitly to use
+>    `launch_hermes_agent.py` or `fan.py`, and to spend its own context budget
+>    by delegating broad searches, file mapping, and independent reviews to
+>    DeepSeek/Kimi subagents wherever practical.
+>
+> This network restriction does not affect Codex or Claude subagents.
+
+## Picking a pathway
+
+- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
+- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
+- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
+- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
+- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
+- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
+- **Already have the answer?** → don't dispatch. Subagents aren't free.
+
+## Use the cheapest subagent that can do the job
+
+Independence is the *why*; cost is the *which*. Default to the cheapest model that can plausibly succeed; escalate only on evidence.
+
+1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
+2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`, **the default**) — non-reasoning, fast, cheap. The default for most dispatches: implementation, mechanical edits, focused investigation, verification. Escalate to Pro only on evidence that reasoning is needed.
+3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`) — reasoning model. Use when the task needs judgement: root-cause analysis, "is this sound", "should this merge".
+4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.
+
+Two rules: **start low, escalate on evidence** (don't reach for the frontier model "to be safe"); and **prepare the context so a cheap model can win** — most "cheap model failed" cases are under-specified prompts. A moment spent scoping the task is cheaper than burning a Claude subagent on something Flash could do.
+
+Beware the asymmetry: reasoning models handed mechanical briefs refactor (because that's what reasoning does); non-reasoning models handed architectural briefs literally execute fragments without understanding the intent. Match brief shape to model mode, not just model to task.
+
+---
+
+## 1. Hermes agentic (DeepSeek / Kimi / Zhipu GLM) — the default
+
+A real tool-using agent in a non-Claude model's voice, far lighter than a `megaplan` run. It wraps megaplan's `AIAgent` primitive as a standalone CLI: the agent reads files, searches the codebase, fetches URLs, and (with `terminal`) runs commands — single-turn, no plan state or critique loop. For a pure-chat opinion with no repo access, run the same command with `--toolsets=""`.
+
+The launcher discovers the active runtime itself. It first tries an installed legacy `megaplan.agent` distribution, then falls back to the current Arnold checkout (`~/Documents/Arnold` by default, or `ARNOLD_PATH=/path/to/Arnold`). Do not add an `arnold_pipelines.megaplan.agent` compatibility package to fix import failures; the real Hermes runtime lives under `arnold_pipelines.megaplan.agent` in the Arnold checkout.
+
+```bash
+PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/launch_hermes_agent.py \
+  --toolsets="file,web" \
+  --query-file=/tmp/brief.md \
+  --max-tokens=65536 \
+  --project-dir="$PWD"
+# Final response → stdout; tool progress/timings → stderr.
+```
+
+Key flags:
+
+- **`--model`** (default `deepseek:deepseek-v4-flash`). Prefix convention from the megaplan key pool:
+  - `fast`, `mimo`, `mimo-fast` → `mimo:mimo-v2.5-pro-ultraspeed` (very fast MiMo path; requires `MIMO_API_KEY`)
+  - `deepseek:deepseek-v4-flash` (default, non-reasoning) / `deepseek:deepseek-v4-pro` (reasoning) → DeepSeek API
+  - `kimi:kimi-k2.7-code` → Kimi coding API (requires `KIMI_API_KEY` or `MOONSHOT_API_KEY`)
+  - `zhipu:glm-5.2` / `zhipu:glm-4.6` → Zhipu GLM API (requires `ZHIPU_API_KEY`)
+  - `google:gemini-…`, `minimax:MiniMax-M2`, … — see `megaplan/runtime/key_pool.py:resolve_model`
+- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
+- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
+- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
+- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
+- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
+- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
+- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.
+
+Output is **freeform text** — if you want JSON, ask for it in the prompt and parse defensively; for an *enforced* schema, use megaplan, not this pathway.
+
+### Fan out N at once — `fan.py`
+
+`launch_hermes_agent.py` is one subprocess per call; each re-imports the Arnold/Hermes runtime. For **≥ ~5 parallel agents or programmatic batches**, `fan.py` runs N `AIAgent`s in one process (imports once, ~5–15× less RAM). Same flags, plus a briefs directory and per-task output:
+
+```bash
+PYENV_VERSION=3.11.11 python ~/.claude/skills/subagent-launcher/fan.py \
+  --briefs-dir=/tmp/briefs --output-dir=/tmp/results \
+  --max-workers=5 --model="deepseek:deepseek-v4-flash" \

exec
/bin/zsh -lc 'git diff --stat 58473c3a..a7b7b080 && git diff --name-status 58473c3a..a7b7b080' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-3-r2.md                    | 14396 ++++++++++++++++++++
 astrid/packs/rendering/backends/ffmpeg/support.py |    40 +-
 astrid/packs/rendering/backends/remotion/run.py   |     1 +
 tests/packs/rendering/test_ffmpeg_backend.py      |     1 +
 tests/packs/rendering/test_ffmpeg_support.py      |     1 +
 5 files changed, 14434 insertions(+), 5 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-3-r2.md
M	astrid/packs/rendering/backends/ffmpeg/support.py
M	astrid/packs/rendering/backends/remotion/run.py
M	tests/packs/rendering/test_ffmpeg_backend.py
M	tests/packs/rendering/test_ffmpeg_support.py

exec
/bin/zsh -lc 'git status --short --branch && git log -3 --oneline --decorate' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## oracle-run
?? .oracle/checkins/batch-3-r3.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
a7b7b080 (HEAD -> oracle-run) batch3-rework3: oracle re-review2 issues 1-4 (remotion --enforce-audio-track, canonical MP4 time-base rule + rational-aware ffmpeg support, stream-copy time-base gate, frame-accurate whole-source tolerance)
58473c3a batch3-rework2: oracle re-review issues 1-6 (env-authoritative launcher routing, remotion full render-profile support + manifest audio, ffmpeg time_base support check, audio-reactive 48kHz, whole-source stream-copy gate incl codec/pixel + supported required, TOCTOU-free legacy facade via preloaded-data builder)
72b70944 batch3-rework: oracle issues 1-8 (launcher backend-id routing, remotion support/render contract alignment + ffprobe binary, ffmpeg full-profile support + canonical 48kHz, probe-gated stream-copy, legacy path strict support, finalizer audio-presence + codec-anchor tests, lock test timeouts)

exec
/bin/zsh -lc "rg -n -C 5 'Batch 3|T3\\.|acceptance|rendering|finalizer|backend' .oracle/tasklist.md | head -n 700" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
5-**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
6-
7-**Acceptance criteria:**
8-
9-- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
10:- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
11:- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
12:- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
13:- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
14-- Active trusted installs, corrupt/mismatched installs, inactive revisions, explicit-extra roots, environment denial, conflicts, cycles, and invalid override targets produce the specified inspectable/executable states.
15-- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
16:- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.
17-
18-### Tasks
19-
20:- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
23:- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
24:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
25-
26-## Batch 2 — Command protocol and host-owned plumbing
27-
28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
29-
30-**Acceptance criteria:**
31-
32-- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
33-- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
--
38-- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
39-- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
40-
41-### Tasks
42-
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
45:- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
49-
50:## Batch 3 — Built-in renderer and finalizer extraction
51-
52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
53-
54-**Acceptance criteria:**
55-
56:- `rendering.remotion`, `rendering.ffmpeg`, and `rendering.ffmpeg-finalizer` are statically registered through `astrid/packs/rendering/pack.yaml` and their manifests.
57-- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
58-- One non-recursive cross-process lock spans registry-state reads, all registry/shim/theme-pointer writes, active-theme selection, the complete Remotion render, and the `gen-types` writer path.
59-- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
60-- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
61:- The finalizer probes every segment, stream-copies only complete profile matches, otherwise normalizes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout/presence, and records each normalization.
62-- Existing compatibility tests, Remotion typecheck, an available Remotion fixture render, and a real FFmpeg render pass.
63-
64-### Tasks
65-
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
72-
73-## Batch 4 — Generic routing, provenance, and hybrid planning
74-
75:**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.
76-
77-**Acceptance criteria:**
78-
79-- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
80:- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
81-- `output_name` uses existing input placeholders and cache/CAS identity, rejects separators/traversal/non-MP4 extensions, preserves declared output names, and leaves Hype’s default `hype.mp4` sentinel unchanged.
82-- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
84-- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
85-- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.
86-
87-### Tasks
88-
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
90:- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
94-
95-## Batch 5 — Caller migration, semantic parity, and M1 freeze
96-
97-**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.
98-
99-**Acceptance criteria:**
100-
101-- The attached-child helper requires a validated parent project/run and unique step, scopes and restores all three `ASTRID_TASK_*` variables, preserves caller-selected output, honors facade overrides, and falls back to public `RenderService` only without a project ledger.
102-- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
103:- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
104:- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
105-- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
106-- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
107-- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
108-- Targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.
109-
110-### Tasks
111-
112:- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
113:- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
114:- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
116:- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
117:- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
118:- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
119-
120-## Batch 6 — Python SDK, conformance, and scaffold
121-
122-**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.
123-
124-**Acceptance criteria:**
125-
126-- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
127-- Any SDK/wire mismatch stops the batch and returns to M1 through the oracle; no SDK-only fields or semantics are introduced.
128:- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
129-- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
130:- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
131-- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
132-- Scaffold collision, ownership, command-containment, static validation, trusted install, generated test, two-second smoke, and installed-wheel cases pass.
133-
134-### Tasks
135-
136:- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
138:- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
140:- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
141:- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.
142-
143-## Batch 7 — CLI, replay, documentation, and epic freeze
144-
145-**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.
146-
147-**Acceptance criteria:**
148-
149-- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
150:- `list` and `inspect` perform static metadata parsing and report source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and overrides without importing backend code.
151-- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
152-- Each CLI verb has a frozen raw-dictionary `--json` shape; expected errors exit 2, degraded bugs exit 1, and interruption cleans up before normal exit-130 behavior.
153:- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
154-- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
155-- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
156-- Renderer-author documentation covers raw JSON, Python SDK, non-Python commands, trust, permissions, selection, configuration, assets, output/audio/attachments, diagnostics, replay, and legacy selectors while explicitly deferring async jobs, remote infrastructure, and layer compositing.
157:- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
158-- Full pytest, semantic parity, real FFmpeg, explicit optional-Remotion evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.
159-
160-### Tasks
161-
162:- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
164:- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
165:- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
167:- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
168-
169-## Execution notes
170-
171-- Persist this markdown exactly as `.oracle/tasklist.md` before implementation. It is frozen; any change requires an explicit oracle-reviewed plan revision.
172:- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
173-- If the oracle reports issues, rework only the current batch, recommit, and resubmit the cumulative `C(N-1)..HEAD` range until `PASS`. Do not begin the next batch early.
174:- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
175-- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
176-- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
177:- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
178-- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
179-- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=120 58473c3a..a7b7b080 -- astrid/packs/rendering/backends/ffmpeg/support.py astrid/packs/rendering/backends/remotion/run.py tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_support.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/packs/rendering/backends/ffmpeg/support.py b/astrid/packs/rendering/backends/ffmpeg/support.py
index 3c372c94..d9c3b35f 100644
--- a/astrid/packs/rendering/backends/ffmpeg/support.py
+++ b/astrid/packs/rendering/backends/ffmpeg/support.py
@@ -1,134 +1,137 @@
 """Fail-closed, request-sensitive support evidence for ``rendering.ffmpeg``.
 
 This module is deliberately read-only.  It validates a decoded timeline and
 asset registry, probes every referenced local source, and reports every reason
 the FFmpeg renderer cannot preserve the requested semantics.
 """
 
 from __future__ import annotations
 
 import math
 import shutil
 from collections.abc import Callable, Mapping
 from dataclasses import dataclass
+from fractions import Fraction
 from pathlib import Path
+
+from astrid.core.rendering.profile import _mp4_time_base
 from typing import Any
 
 from astrid.core.media import MediaProbe, ffprobe_metadata_strict
 from astrid.core.rendering.contracts import (
     AudioOwnership,
     RenderRequest,
     SCHEMA_VERSION,
     SupportReport,
 )
 from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
 
 
 BACKEND_ID = "rendering.ffmpeg"
 BACKEND_VERSION = "1.0.0"
 ALTERNATIVE_BACKENDS = ("rendering.remotion",)
 
 _TRACK_KINDS = frozenset({"visual", "audio"})
 _POSITION_KEYS = frozenset({"x", "y", "width", "height"})
 _CROP_KEYS = frozenset({"cropTop", "cropBottom", "cropLeft", "cropRight"})
 _EFFECT_KEYS = frozenset({"effects", "entrance", "exit", "continuous", "keyframes"})
 _TIMELINE_EPSILON_SECONDS = 1e-9
 _SOURCE_BOUND_TOLERANCE_SECONDS = 0.001
 
 
 Probe = Callable[[str | Path], MediaProbe]
 BinaryResolver = Callable[[str], str | None]
 
 
 @dataclass(frozen=True)
 class _ClipRange:
     clip: Mapping[str, Any]
     at: float
     source_from: float
     source_to: float
 
     @property
     def duration(self) -> float:
         return self.source_to - self.source_from
 
     @property
     def end(self) -> float:
         return self.at + self.duration
 
 
 def _number(value: Any, label: str) -> float:
     if isinstance(value, bool) or not isinstance(value, (int, float)):
         raise ValueError(f"{label} must be a finite number")
     result = float(value)
     if not math.isfinite(result):
         raise ValueError(f"{label} must be a finite number")
     return result
 
 
 def _gain(value: Any, label: str, *, default: float = 1.0) -> float:
     resolved = default if value is None else _number(value, label)
     if not 0.0 <= resolved <= 1.0:
         raise ValueError(f"{label} must be between 0 and 1")
     return resolved
 
 
 def effective_gain(track: Mapping[str, Any], clip: Mapping[str, Any]) -> float:
     """Return the exact timeline gain for one media clip.
 
     Track mute is authoritative; otherwise track and clip gains multiply.  A
     missing gain means unity, while malformed or out-of-range values are
     rejected instead of clamped.
     """
 
     muted = track.get("muted", False)
     if not isinstance(muted, bool):
         raise ValueError(f"Track {track.get('id')!r} muted must be a boolean")
     track_gain = _gain(
         track.get("volume"),
         f"Track {track.get('id')!r} volume",
     )
     clip_gain = _gain(
         clip.get("volume"),
         f"Clip {clip.get('id')!r} volume",
     )
     return 0.0 if muted else track_gain * clip_gain
 
 
 def _clip_range(clip: Mapping[str, Any]) -> _ClipRange:
     clip_id = clip.get("id")
     at = _number(clip.get("at", 0), f"Clip {clip_id!r} at")
     source_from = _number(
         clip.get("from", 0),
         f"Clip {clip_id!r} from",
     )
     if "to" not in clip:
         raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
     source_to = _number(clip.get("to"), f"Clip {clip_id!r} to")
     if at < 0:
         raise ValueError(f"Clip {clip_id!r} has a negative timeline frame bound")
     if source_from < 0 or source_to <= source_from:
         raise ValueError(
             f"Clip {clip_id!r} must have positive source bounds with to > from"
         )
     return _ClipRange(
         clip=clip,
         at=at,
         source_from=source_from,
         source_to=source_to,
     )
 
 
 def _is_default(value: Any, default: Any) -> bool:
     return value is None or value == default
 
 
 def _nonempty(value: Any) -> bool:
     return value not in (None, False, "", (), [], {})
 
 
 def _validate_track_semantics(track: Mapping[str, Any]) -> list[str]:
     reasons: list[str] = []
     track_id = track.get("id")
     try:
         effective_gain(track, {})
     except ValueError as exc:
@@ -360,307 +363,334 @@ def structural_reasons(
                 reasons.append(
                     f"Overlapping audio at clip {clip_id!r}: starts at {bounds.at:.6f}, previous audio ends at {audio_cursor:.6f}"
                 )
             if bounds.end > cursor + _TIMELINE_EPSILON_SECONDS:
                 reasons.append(
                     f"Audio clip {clip_id!r} ends outside the visual frame bounds"
                 )
             audio_cursor = max(audio_cursor, bounds.end)
     return _dedupe(reasons)
 
 
 def _dedupe(reasons: list[str]) -> list[str]:
     return list(dict.fromkeys(reason for reason in reasons if reason))
 
 
 def _assets_table(assets: Mapping[str, Any]) -> Mapping[str, Any] | None:
     value = assets.get("assets")
     return value if isinstance(value, Mapping) else None
 
 
 def _registry_path(request: RenderRequest) -> Path:
     if request.assets_registry_path is None:
         return Path.cwd() / "assets.json"
     return Path(request.assets_registry_path).expanduser().resolve()
 
 
 def _asset_path(
     entry: Mapping[str, Any],
     *,
     asset_id: str,
     assets_path: Path,
 ) -> Path:
     if _nonempty(entry.get("url")):
         raise ValueError(
             f"Asset {asset_id!r} is remote; rendering.ffmpeg requires a local source file"
         )
     file_value = entry.get("file")
     if not isinstance(file_value, str) or not file_value:
         raise ValueError(f"Asset {asset_id!r} has no local source file")
     path = Path(file_value).expanduser()
     if not path.is_absolute():
         path = (assets_path.parent / path).resolve()
     else:
         path = path.resolve()
     if not path.is_file():
         raise FileNotFoundError(f"Asset {asset_id!r} source is missing: {path}")
     return path
 
 
 def _probe_duration(probe: MediaProbe) -> float | None:
     if probe.duration_seconds is not None:
         return float(probe.duration_seconds)
     if probe.duration_rational is not None:
         numerator, denominator = probe.duration_rational
         return numerator / denominator
     return None
 
 
 def _requested_ownership(
     request: RenderRequest,
     *,
     has_audio_clips: bool,
 ) -> tuple[AudioOwnership, list[str]]:
     natural = AudioOwnership.RENDERED if has_audio_clips else AudioOwnership.NONE
     ownership = natural
     reasons: list[str] = []
     if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
         ownership = AudioOwnership.PASSTHROUGH
     elif request.audio is not None and request.audio is not natural:
         reasons.append(
             f"audio={request.audio.value!r} is incompatible with timeline audio ownership {natural.value!r}"
         )
     if request.profile is not None and request.profile.has_audio != (
         ownership is AudioOwnership.RENDERED
     ):
         reasons.append(
             "requested profile audio fields do not match rendering.ffmpeg audio ownership"
         )
     return ownership, reasons
 
 
 def _whole_media_optimization(
     timeline_data: Mapping[str, Any],
     assets: Mapping[str, Any],
     probes: Mapping[str, MediaProbe],
 ) -> bool:
     tracks = {
         track.get("id"): track
         for track in timeline_data.get("tracks", [])
         if isinstance(track, Mapping)
     }
     visual = [
         clip
         for clip in timeline_data.get("clips", [])
         if isinstance(clip, Mapping)
         and clip.get("clipType") == "media"
         and tracks.get(clip.get("track"), {}).get("kind") == "visual"
     ]
     table = _assets_table(assets)
     if len(visual) != 1 or table is None:
         return False
     clip = visual[0]
     entry = table.get(clip.get("asset"))
     if not isinstance(entry, Mapping):
         return False
     media_probe = probes.get(str(clip.get("asset")))
     if media_probe is None or not media_probe.has_video_stream:
         return False
     try:
         bounds = _clip_range(clip)
         width, height, fps = _canvas(timeline_data)
         duration = _number(entry.get("duration"), "asset duration")
         source_fps = _number(entry.get("fps"), "asset fps")
     except ValueError:
         return False
     probed_duration = _probe_duration(media_probe)
     probed_fps = media_probe.fps
     if probed_fps is None and media_probe.fps_rational is not None:
         numerator, denominator = media_probe.fps_rational
         probed_fps = numerator / denominator
+    # Frame-accurate tolerance: at most ONE frame of drift is acceptable
+    # (half a frame each way), so extra trailing frames at high FPS cannot
+    # slip through a coarse 50 ms window.
+    frame_tolerance = 0.5 / fps if fps > 0 else 0.0
     return (
         bounds.at == 0
         and bounds.source_from == 0
-        and abs(bounds.duration - duration) < 0.05
+        and abs(bounds.duration - duration) < frame_tolerance
         and entry.get("resolution") == f"{width}x{height}"
         and abs(source_fps - fps) < 1e-6
         and probed_duration is not None
-        and abs(bounds.duration - probed_duration) < 0.05
+        and abs(bounds.duration - probed_duration) < frame_tolerance
         and media_probe.width == width
         and media_probe.height == height
         and probed_fps is not None
         and abs(probed_fps - fps) < 1e-6
         and (media_probe.video_codec or "") == "h264"
         and (media_probe.pixel_format or "") == "yuv420p"
+        and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
     )
 
 
+def _probe_time_base_matches(
+    probe: MediaProbe, expected: tuple[int, int]
+) -> bool:
+    """The probed stream time base must equal the canonical MP4 timescale."""
+    if probe.time_base is None:
+        return False
+    return Fraction(*probe.time_base) == Fraction(*expected)
+
+
 def _profile_support_reasons(
     request: RenderRequest, timeline_data: Mapping[str, Any]
 ) -> list[str]:
     """Fail closed when the requested profile deviates from what the FFmpeg
     backend actually produces (canvas dims/fps, codecs, pixel format, and
     canonical audio rate/layout)."""
     profile = request.profile
     if profile is None:
         return []
     reasons: list[str] = []
     try:
         width, height, fps = _canvas(timeline_data)
     except ValueError:
         return reasons  # canvas failure already reported elsewhere
     checks = (
         ("width", profile.width, width),
         ("height", profile.height, height),
-        ("fps", _fps_int(profile.fps_rational), fps),
-        ("time_base", profile.time_base, (1, fps * 512)),
+        ("fps", profile.fps_rational, (fps, 1)),
+        ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
         ("container", profile.container, "mp4"),
         ("video_codec", profile.video_codec, "h264"),
         ("pixel_format", profile.pixel_format, "yuv420p"),
     )
     for field, requested, produced in checks:
-        if requested is not None and requested != produced:
+        if requested is None:
+            continue
+        if field in ("fps", "time_base"):
+            equal = _rational_equal(requested, produced)
+        else:
+            equal = requested == produced
+        if not equal:
             reasons.append(
                 f"requested profile {field}={requested!r} is not produced by "
                 f"rendering.ffmpeg (produces {produced!r})"
             )
     if profile.has_audio:
         for field, requested, produced in (
             ("audio_sample_rate", profile.audio_sample_rate, 48000),
             ("audio_channel_layout", profile.audio_channel_layout, "stereo"),
             ("audio_codec", profile.audio_codec, "aac"),
         ):
             if requested is not None and requested != produced:
                 reasons.append(
                     f"requested profile {field}={requested!r} is not produced by "
                     f"rendering.ffmpeg (produces {produced!r})"
                 )
     return reasons
 
 
 def _fps_int(fps_rational: tuple[int, int] | None) -> int | None:
     if fps_rational is None:
         return None
     num, den = fps_rational
     return num // den if den and num % den == 0 else None
 
 
+def _rational_equal(a: Any, b: Any) -> bool:
+    try:
+        return Fraction(*a) == Fraction(*b)
+    except (TypeError, ValueError, ZeroDivisionError):
+        return False
+
+
 def _canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
     overrides = timeline_data.get("theme_overrides")
     visual = overrides.get("visual") if isinstance(overrides, Mapping) else None
     canvas = visual.get("canvas") if isinstance(visual, Mapping) else None
     canvas = canvas if isinstance(canvas, Mapping) else {}
     values: list[int] = []
     for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
         value = canvas.get(key, default)
         if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
             raise ValueError(f"Canvas {key} must be a positive integer")
         values.append(value)
     return values[0], values[1], values[2]
 
 
 def support(
     request: RenderRequest,
     timeline_data: Mapping[str, Any],
     assets: Mapping[str, Any],
     *,
     probe: Probe | None = None,
     which: BinaryResolver | None = None,
 ) -> SupportReport:
     """Return strict support evidence for one already-decoded request."""
 
     reasons: list[str] = []
     probe_media = probe or ffprobe_metadata_strict
     resolve_binary = which or shutil.which
     binary_available: dict[str, bool] = {}
     for binary in ("ffmpeg", "ffprobe"):
         available = resolve_binary(binary) is not None
         binary_available[binary] = available
         if not available:
             reasons.append(f"required binary is unavailable: {binary}")
 
     if request.window is not None:
         reasons.append(
             "rendering.ffmpeg accepts complete timelines, not native frame windows"
         )
     config = request.backend_config.get(BACKEND_ID, {})
     if config:
         reasons.append(
             "rendering.ffmpeg does not accept backend-specific configuration"
         )
     if request.assets_registry_path is None:
         reasons.append("rendering.ffmpeg requires an assets registry")
     try:
         _canvas(timeline_data)
     except ValueError as exc:
         reasons.append(str(exc))
     reasons.extend(structural_reasons(timeline_data))
 
     table = _assets_table(assets)
     if table is None:
         reasons.append("assets registry must contain an assets object")
         table = {}
     assets_path = _registry_path(request)
     tracks = {
         track.get("id"): track
         for track in timeline_data.get("tracks", [])
         if isinstance(track, Mapping)
     }
     media_clips = [
         clip
         for clip in timeline_data.get("clips", [])
         if isinstance(clip, Mapping) and clip.get("clipType") == "media"
     ]
     audio_clips = [
         clip
         for clip in media_clips
         if tracks.get(clip.get("track"), {}).get("kind") == "audio"
     ]
     ownership, ownership_reasons = _requested_ownership(
         request,
         has_audio_clips=bool(audio_clips),
     )
     reasons.extend(ownership_reasons)
 
     probes: dict[str, MediaProbe] = {}
     for clip in media_clips:
         clip_id = clip.get("id")
         asset_id = clip.get("asset")
         if not isinstance(asset_id, str) or not asset_id:
             reasons.append(f"Clip {clip_id!r} has no asset")
             continue
         entry = table.get(asset_id)
         if not isinstance(entry, Mapping):
             reasons.append(f"Clip {clip_id!r} references missing asset {asset_id!r}")
             continue
         try:
             path = _asset_path(entry, asset_id=asset_id, assets_path=assets_path)
         except (ValueError, FileNotFoundError) as exc:
             reasons.append(str(exc))
             continue
         if asset_id not in probes and binary_available["ffprobe"]:
             try:
                 probed = probe_media(path)
                 if not isinstance(probed, MediaProbe):
                     raise TypeError("probe did not return MediaProbe")
                 probes[asset_id] = probed
             except Exception as exc:
                 reasons.append(f"Asset {asset_id!r} cannot be probed: {exc}")
 
         media_probe = probes.get(asset_id)
         if media_probe is None:
             continue
         track = tracks.get(clip.get("track"), {})
         kind = track.get("kind")
         if kind == "visual" and not media_probe.has_video_stream:
             reasons.append(
                 f"Visual clip {clip_id!r} source {asset_id!r} has no video stream"
             )
         if kind == "audio" and not media_probe.has_audio_stream:
             reasons.append(
                 f"Audio clip {clip_id!r} source {asset_id!r} has no audio stream"
             )
         if kind == "visual" and media_probe.has_audio_stream:
             try:
                 gain = effective_gain(track, clip)
             except ValueError:
                 gain = 0.0
diff --git a/astrid/packs/rendering/backends/remotion/run.py b/astrid/packs/rendering/backends/remotion/run.py
index 2daded5b..cde4cd66 100644
--- a/astrid/packs/rendering/backends/remotion/run.py
+++ b/astrid/packs/rendering/backends/remotion/run.py
@@ -583,240 +583,241 @@ def _stderr_tail(stderr: str) -> str:
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
 
 
 def _execute_remotion(
     timeline_path: Path,
     assets_path: Path,
     staged_video: Path,
     *,
     provenance_out_path: Path,
     project_dir: Path,
     composition_id: str,
     theme_path: Path | None,
     min_free_gb: float | None,
 ) -> _ExecutionDetails:
     """Render one private video and return the data needed for provenance."""
 
     with remotion_lock.remotion_render_lock():
         return _execute_remotion_locked(
             timeline_path,
             assets_path,
             staged_video,
             provenance_out_path=provenance_out_path,
             project_dir=project_dir,
             composition_id=composition_id,
             theme_path=theme_path,
             min_free_gb=min_free_gb,
         )
 
 
 def _execute_remotion_locked(
     timeline_path: Path,
     assets_path: Path,
     staged_video: Path,
     *,
     provenance_out_path: Path,
     project_dir: Path,
     composition_id: str,
     theme_path: Path | None,
     min_free_gb: float | None,
 ) -> _ExecutionDetails:
     """Execute one render while the caller owns the non-recursive outer lock."""
 
     _validate_project_dir(project_dir)
     _regenerate_element_registries(project_dir, theme_path)
     registry_state = _effective_registry_state(theme_path)
     _require_free_space(provenance_out_path.parent, min_free_gb)
     props_path = (provenance_out_path.parent / ".remotion-props.json").resolve()
     render_hash = _render_asset_stage_hash(
         timeline_path,
         assets_path,
         provenance_out_path,
     )
     staged_public_root = project_dir / "public" / "astrid-effects" / render_hash
     with ExitStack() as asset_lifecycle:
         try:
             materializer = asset_lifecycle.enter_context(AssetMaterializer(assets_path))
             asset_server = None
             if materializer.needs_server:
                 try:
                     asset_server = asset_lifecycle.enter_context(
                         InvocationAssetServer(materializer.staging_dir)
                     )
                 except OSError as exc:
                     raise RuntimeError(
                         f"Permission denied (1100): local HTTP asset server blocked: {exc}"
                     ) from exc
             resolved_registry = materializer.resolved_registry(asset_server)
             resolved_theme = theme_path or (
                 WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
             )
             theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
             merged_props = {
                 "timeline": _serialize_timeline(
                     timeline_path,
                     default_theme=str(
                         theme_for_props.get("id") or "banodoco-default"
                     ),
                 ),
                 "assets": resolved_registry,
                 "theme": theme_for_props,
             }
             stage_summary = _stage_effect_assets_for_timeline(
                 merged_props["timeline"],
                 project_dir=project_dir,
                 theme_path=theme_path,
                 render_hash=render_hash,
             )
             staged_video.parent.mkdir(parents=True, exist_ok=True)
             props_path.write_text(json.dumps(merged_props), encoding="utf-8")
             remotion_env_additions: dict[str, str] = {}
             composition_src = _timeline_composition_src(project_dir)
             if composition_src is not None:
                 remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(
                     composition_src
                 )
             completed = subprocess.run(
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
+                    "--enforce-audio-track",
                 ],
                 cwd=str(project_dir),
                 env=build_child_subprocess_env(explicit_env=remotion_env_additions),
                 capture_output=True,
                 check=False,
                 text=True,
             )
             if completed.returncode != 0:
                 stderr_tail = _stderr_tail(completed.stderr)
                 message = f"Remotion render failed with exit code {completed.returncode}"
                 if stderr_tail:
                     message = f"{message}\n{stderr_tail}"
                 raise RuntimeError(message)
             if not staged_video.is_file() or staged_video.stat().st_size <= 0:
                 raise RuntimeError("Remotion render did not produce a non-empty video")
             return _ExecutionDetails(
                 active_theme=theme_for_props,
                 registry_state=registry_state,
                 stage_summary=stage_summary,
             )
         finally:
             props_path.unlink(missing_ok=True)
             shutil.rmtree(staged_public_root, ignore_errors=True)
 
 
 def render(
     timeline_path: Path,
     assets_path: Path,
     out_path: Path,
     *,
     project_dir: Path | None = None,
     composition_id: str = DEFAULT_COMPOSITION_ID,
     theme_path: Path | None = None,
     min_free_gb: float | None = None,
     previous_outputs: Sequence[Path] = (),
 ) -> Path:
     """Render privately, then publish the legacy video/provenance pair."""
 
     timeline_path = Path(timeline_path)
     assets_path = Path(assets_path)
     out_path = Path(out_path)
     project_dir = Path(project_dir) if project_dir is not None else REPO_ROOT / "remotion"
     out_path.parent.mkdir(parents=True, exist_ok=True)
     with TemporaryDirectory(
         prefix=f".{out_path.name}.publication-",
         dir=str(out_path.parent),
     ) as publication_tmp:
         staged_video = Path(publication_tmp) / out_path.name
         details = _execute_remotion(
             timeline_path,
             assets_path,
             staged_video,
             provenance_out_path=out_path,
             project_dir=project_dir,
             composition_id=composition_id,
             theme_path=theme_path,
             min_free_gb=min_free_gb,
         )
         provenance = _render_provenance_payload(
             out_path,
             engine="remotion",
             timeline_path=timeline_path,
             assets_path=assets_path,
             project_dir=project_dir,
             composition_id=composition_id,
             theme_path=theme_path,
             active_theme=details.active_theme,
             registry_state=details.registry_state,
             stage_summary=details.stage_summary,
         )
         output = publish_render_result(
             staged_video,
             provenance,
             out_path=out_path,
             sidecar_path=_render_provenance_sidecar_path(out_path),
             previous_outputs=previous_outputs,
         )
 
     audit = AuditContext.from_env()
     if audit is not None:
         timeline_id = audit.register_asset(
             kind="timeline",
             path=timeline_path,
             label="Render timeline",
             stage="render_remotion",
         )
         assets_id = audit.register_asset(
             kind="assets_registry",
             path=assets_path,
             label="Render asset registry",
             stage="render_remotion",
         )
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
             metadata={
                 "composition": composition_id,
                 "project_dir": str(project_dir),
             },
         )
     return output
 
 
 def _input_path(raw_path: str, workspace: Path) -> Path:
     candidate = Path(raw_path).expanduser()
     return (candidate if candidate.is_absolute() else workspace / candidate).resolve()
 
 
 def _theme_setting_path(raw_path: str, workspace: Path) -> Path:
     """Preserve legacy theme slugs while localizing actual request paths."""
diff --git a/tests/packs/rendering/test_ffmpeg_backend.py b/tests/packs/rendering/test_ffmpeg_backend.py
index b2ded32d..5147cf21 100644
--- a/tests/packs/rendering/test_ffmpeg_backend.py
+++ b/tests/packs/rendering/test_ffmpeg_backend.py
@@ -68,240 +68,241 @@ def _media_timeline(*, include_audio: bool = True) -> dict:
             }
         },
         "tracks": tracks,
         "clips": clips,
     }
 
 
 def _text_timeline() -> dict:
     data = _media_timeline()
     data["clips"].append(
         {
             "id": "title",
             "at": 0.5,
             "track": "v",
             "clipType": "text-card",
             "hold": 1,
         }
     )
     return data
 
 
 def _write_inputs(
     tmp_path: Path,
     *,
     timeline_data: dict | None = None,
     registered: bool = True,
     source_resolution: str = "1920x1080",
 ) -> tuple[Path, Path]:
     timeline_path = tmp_path / "timeline.json"
     assets_path = tmp_path / "assets.json"
     source_path = tmp_path / "source.mp4"
     source_path.write_bytes(b"placeholder")
     timeline_path.write_text(
         json.dumps(timeline_data or _media_timeline()),
         encoding="utf-8",
     )
     assets = (
         {
             "main": {
                 "file": source_path.name,
                 "type": "video/mp4",
                 "duration": 2,
                 "resolution": source_resolution,
                 "fps": 30,
             }
         }
         if registered
         else {}
     )
     assets_path.write_text(json.dumps({"assets": assets}), encoding="utf-8")
     return timeline_path, assets_path
 
 
 def _request(timeline_path: Path, assets_path: Path) -> RenderRequest:
     return RenderRequest(
         schema_version=SCHEMA_VERSION,
         timeline_path=str(timeline_path),
         assets_registry_path=str(assets_path),
         output_name="result.mp4",
         backend_config={ffmpeg.BACKEND_ID: {}},
     )
 
 
 def _profile() -> RenderProfile:
     return RenderProfile(
         width=1920,
         height=1080,
         fps_rational=(30, 1),
         time_base=(1, 15360),
         container="mp4",
         video_codec="h264",
         video_profile="High",
         video_level="4.0",
         pixel_format="yuv420p",
         audio_codec="aac",
         audio_sample_rate=48000,
         audio_channel_layout="stereo",
     )
 
 
 def test_manifest_registers_static_raw_command_backend() -> None:
     manifest_path = (
         ROOT
         / "astrid"
         / "packs"
         / "rendering"
         / "backends"
         / "ffmpeg"
         / "renderer.yaml"
     )
     manifest = RendererManifest.from_dict(
         yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
     )
 
     assert manifest.id == "rendering.ffmpeg"
     assert manifest.protocol_version == 1
     assert manifest.command == ("python3", "run.py")
     assert manifest.operations == ("render", "support")
     assert manifest.required_permissions == ("project_files", "subprocess")
     assert manifest.required_binaries == ("ffmpeg", "ffprobe")
     assert manifest.capabilities["clip_types"] == ["media"]
     assert (manifest_path.parents[2] / manifest.command[1]).is_file()
 
     pack = yaml.safe_load(
         (manifest_path.parents[2] / "pack.yaml").read_text(encoding="utf-8")
     )
     assert "backends/ffmpeg/renderer.yaml" in pack["extensions"]["rendering"][
         "renderers"
     ]
 
 
 def test_support_is_strict_while_legacy_facade_eligibility_is_preserved(
     tmp_path: Path,
 ) -> None:
     timeline_path, assets_path = _write_inputs(tmp_path)
     source_probe = MediaProbe(
         duration_seconds=2,
         width=1920,
         height=1080,
         fps=30,
+        time_base=(1, 15360),
         video_codec="h264",
         pixel_format="yuv420p",
         audio_codec="aac",
         video_stream_present=True,
         audio_stream_present=True,
     )
 
     with mock.patch.object(
         ffmpeg,
         "ffprobe_metadata_strict",
         return_value=source_probe,
     ):
         report = ffmpeg.support(
             _request(timeline_path, assets_path),
             workspace=tmp_path,
         )
 
     assert report.supported is True
     assert report.reasons == []
     assert report.backend == ffmpeg.BACKEND_ID
     assert report.features["audio_ownership"] == "rendered"
     assert report.features["whole_media"] is True
     assert ffmpeg.can_render_with_ffmpeg_media(timeline_path, assets_path) is True
 
 
 def test_support_rejects_non_media_timeline(tmp_path: Path) -> None:
     timeline_path, assets_path = _write_inputs(
         tmp_path,
         timeline_data=_text_timeline(),
     )
 
     report = ffmpeg.support(_request(timeline_path, assets_path), workspace=tmp_path)
 
     assert report.supported is False
     assert any("unsupported clip kind" in reason for reason in report.reasons)
     assert ffmpeg.can_render_with_ffmpeg_media(timeline_path, assets_path) is False
 
 
 def test_raw_support_adapter_writes_authoritative_report(tmp_path: Path) -> None:
     timeline_path, assets_path = _write_inputs(tmp_path, registered=False)
     request_path = tmp_path / "request.json"
     result_path = tmp_path / "result.json"
     request_path.write_text(
         json.dumps(_request(timeline_path, assets_path).to_dict()),
         encoding="utf-8",
     )
 
     assert ffmpeg.main(
         [
             "support",
             "--request",
             str(request_path),
             "--result",
             str(result_path),
         ]
     ) == 0
 
     report = SupportReport.from_dict(
         json.loads(result_path.read_text(encoding="utf-8"))
     )
     assert report.supported is False
     assert report.alternatives == ["rendering.remotion"]
     assert report.backend == ffmpeg.BACKEND_ID
 
 
 def test_manifest_command_dispatches_from_pack_root(tmp_path: Path) -> None:
     timeline_path, assets_path = _write_inputs(tmp_path, registered=False)
     request_path = tmp_path / "transport-request.json"
     result_path = tmp_path / "transport-result.json"
     request_payload = _request(timeline_path, assets_path).to_dict()
     request_payload["backend_config"] = {}
     request_path.write_text(
         json.dumps(request_payload),
         encoding="utf-8",
     )
 
     report = CommandTransport(ffmpeg.BACKEND_ID).run(
         "support",
         ("python3", "run.py"),
         request_path=request_path,
         result_path=result_path,
         cwd=ROOT / "astrid" / "packs" / "rendering",
     )
 
     assert isinstance(report, SupportReport)
     assert report.backend == ffmpeg.BACKEND_ID
     assert report.supported is False
 
 
 def test_build_render_command_is_pure_and_preserves_stream_copy(
     tmp_path: Path,
 ) -> None:
     timeline_path, assets_path = _write_inputs(tmp_path)
     request = _request(timeline_path, assets_path)
     inputs = command.resolve_render_command_inputs(request, tmp_path)
 
     # Stream-copy is gated on probe evidence; the pure builder emits the copy
     # path only when the caller passes stream_copy_allowed=True. A placeholder
     # source (no real probe) must default to re-encoding.
     argv = command.build_render_command(request, tmp_path)
     assert argv[argv.index("-c:v") + 1] == "libx264"
 
     copy_argv = command.build_render_command_from_inputs(
         dataclasses.replace(inputs, stream_copy_allowed=True)
     )
     assert copy_argv[copy_argv.index("-c:v") + 1] == "copy"
     assert copy_argv[-1] == str((tmp_path / "outputs" / "result.mp4").resolve())
     assert not (tmp_path / "outputs").exists()
 
 
 def test_build_render_command_encodes_visual_only_without_synthesizing_silence(
     tmp_path: Path,
 ) -> None:
     timeline_path, assets_path = _write_inputs(
         tmp_path,
         timeline_data=_media_timeline(include_audio=False),
         source_resolution="1280x720",
     )
 
     argv = command.build_render_command(
diff --git a/tests/packs/rendering/test_ffmpeg_support.py b/tests/packs/rendering/test_ffmpeg_support.py
index 68707f58..dcc8fb33 100644
--- a/tests/packs/rendering/test_ffmpeg_support.py
+++ b/tests/packs/rendering/test_ffmpeg_support.py
@@ -1,222 +1,223 @@
 from __future__ import annotations
 
 import copy
 import importlib
 import json
 import subprocess
 from pathlib import Path
 from unittest import mock
 
 import pytest
 
 from astrid.core.media import MediaProbe
 from astrid.core.rendering.contracts import (
     AudioOwnership,
     FrameWindow,
     RenderRequest,
     RenderResult,
     SCHEMA_VERSION,
 )
 from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
 from astrid.packs.rendering.backends.ffmpeg import command
 from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
 from astrid.packs.rendering.backends.ffmpeg.support import support as evaluate_support
 
 
 support_module = importlib.import_module(
     "astrid.packs.rendering.backends.ffmpeg.support"
 )
 
 
 def _timeline(*, include_audio: bool = True, duration: float = 4.0) -> dict:
     tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
     clips = [
         {
             "id": "video",
             "at": 0,
             "track": "v",
             "clipType": "media",
             "asset": "video",
             "from": 0,
             "to": duration,
             "speed": 1,
             "volume": 0,
         }
     ]
     if include_audio:
         tracks.append(
             {
                 "id": "a",
                 "kind": "audio",
                 "label": "Audio",
                 "volume": 0.5,
             }
         )
         clips.append(
             {
                 "id": "audio",
                 "at": 0,
                 "track": "a",
                 "clipType": "media",
                 "asset": "audio",
                 "from": 0,
                 "to": duration,
                 "speed": 1,
                 "volume": 0.4,
             }
         )
     return {
         "theme": "banodoco-default",
         "theme_overrides": {
             "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
         },
         "tracks": tracks,
         "clips": clips,
     }
 
 
 def _assets(tmp_path: Path, *, duration: float = 4.0) -> dict:
     return {
         "assets": {
             "video": {
                 "file": "video.mp4",
                 "type": "video/mp4",
                 "duration": duration,
                 "resolution": "640x360",
                 "fps": 30,
             },
             "audio": {
                 "file": "audio.wav",
                 "type": "audio/wav",
                 "duration": duration,
             },
         }
     }
 
 
 def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
     return MediaProbe(
         duration_seconds=duration,
         width=640,
         height=360,
         fps=30,
+        time_base=(1, 15360),
         resolution="640x360",
         video_codec="h264",
         pixel_format="yuv420p",
         audio_codec="aac" if audio else None,
         video_stream_present=True,
         audio_stream_present=audio,
     )
 
 
 def _audio_probe(*, duration: float = 4.0, present: bool = True) -> MediaProbe:
     return MediaProbe(
         duration_seconds=duration,
         audio_codec="pcm_s16le" if present else None,
         video_stream_present=False,
         audio_stream_present=present,
     )
 
 
 def _request(
     tmp_path: Path,
     *,
     audio: AudioOwnership | None = None,
     window: FrameWindow | None = None,
 ) -> RenderRequest:
     return RenderRequest(
         schema_version=SCHEMA_VERSION,
         timeline_path=str(tmp_path / "timeline.json"),
         assets_registry_path=str(tmp_path / "assets.json"),
         output_name="result.mp4",
         window=window,
         audio=audio,
         backend_config={ffmpeg.BACKEND_ID: {}},
     )
 
 
 def _evaluate(
     tmp_path: Path,
     timeline_data: dict,
     assets: dict,
     *,
     probes: dict[str, MediaProbe] | None = None,
     missing_files: set[str] | None = None,
     which=None,
     request: RenderRequest | None = None,
 ):
     missing = missing_files or set()
     for entry in assets.get("assets", {}).values():
         file_value = entry.get("file")
         if isinstance(file_value, str) and file_value not in missing:
             (tmp_path / file_value).write_bytes(b"source")
     (tmp_path / "timeline.json").write_text(
         json.dumps(timeline_data),
         encoding="utf-8",
     )
     (tmp_path / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
     probe_map = probes or {
         "video.mp4": _video_probe(),
         "audio.wav": _audio_probe(),
     }
 
     return evaluate_support(
         request or _request(tmp_path),
         timeline_data,
         assets,
         probe=lambda path: probe_map[Path(path).name],
         which=which or (lambda binary: f"/usr/bin/{binary}"),
     )
 
 
 def _build_command(tmp_path: Path, timeline_data: dict, assets: dict) -> list[str]:
     _evaluate(tmp_path, timeline_data, assets)
     return command.build_render_command(_request(tmp_path), tmp_path)
 
 
 def test_supported_report_exposes_request_specific_evidence(tmp_path: Path) -> None:
     report = _evaluate(tmp_path, _timeline(), _assets(tmp_path))
 
     assert report.supported is True
     assert report.reasons == []
     assert report.alternatives == []
     assert report.features["whole_media"] is True
     assert report.features["stream_copy"] is True
     assert report.features["audio_reactive_colour"] is False
     assert report.features["audio_ownership"] == "rendered"
 
 
 @pytest.mark.parametrize(
     ("case", "reason"),
     [
         ("unknown_track_kind", "unsupported kind"),
         ("unknown_clip_kind", "unsupported clip kind"),
         ("unknown_track", "unknown track"),
         ("invalid_bounds", "positive source bounds"),
         ("source_bound", "exceeds"),
         ("visual_gap", "Visual gap"),
         ("visual_overlap", "Visual overlap"),
         ("speed", "unsupported speed"),
         ("transform", "unsupported transforms"),
         ("track_transform", "transform semantics"),
         ("crop", "unsupported crop"),
         ("effects", "unsupported effects"),
         ("transition", "unsupported transition"),
         ("opacity", "non-default opacity"),
         ("discarded_visual_audio", "embedded audio"),
         ("overlapping_audio", "Overlapping audio"),
         ("fade", "audio fades"),
         ("missing_source", "source is missing"),
         ("missing_video_stream", "no video stream"),
         ("missing_audio_stream", "no audio stream"),
         ("missing_binary", "required binary is unavailable"),
         ("window", "frame windows"),
     ],
 )
 def test_support_fails_closed_for_every_unsupported_semantic(
     tmp_path: Path,
     case: str,
     reason: str,
 ) -> None:
     timeline_data = _timeline()
     assets = _assets(tmp_path)

exec
/bin/zsh -lc 'for f in .oracle/checkins/batch-3.md .oracle/checkins/batch-3-r1.md .oracle/checkins/batch-3-r2.md; do echo FILE:$f; tail -n 180 "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
FILE:.oracle/checkins/batch-3.md
   351	                    f"Visual overlap at clip {clip_id!r}: starts at {bounds.at:.6f}, previous visual ends at {cursor:.6f}"
   352	                )
   353	            cursor = max(cursor, bounds.end)
   354	
   355	        audio_ranges.sort(key=lambda item: item.at)
   356	        audio_cursor = 0.0
   357	        for bounds in audio_ranges:
   358	            clip_id = bounds.clip.get("id")
   359	            if bounds.at < audio_cursor - _TIMELINE_EPSILON_SECONDS:
   360	                reasons.append(
   361	                    f"Overlapping audio at clip {clip_id!r}: starts at {bounds.at:.6f}, previous audio ends at {audio_cursor:.6f}"
   362	                )
   363	            if bounds.end > cursor + _TIMELINE_EPSILON_SECONDS:
   364	                reasons.append(
   365	                    f"Audio clip {clip_id!r} ends outside the visual frame bounds"
   366	                )
   367	            audio_cursor = max(audio_cursor, bounds.end)
   368	    return _dedupe(reasons)
   369	
   370	
   371	def _dedupe(reasons: list[str]) -> list[str]:
   372	    return list(dict.fromkeys(reason for reason in reasons if reason))
   373	
   374	
   375	def _assets_table(assets: Mapping[str, Any]) -> Mapping[str, Any] | None:
   376	    value = assets.get("assets")
   377	    return value if isinstance(value, Mapping) else None
   378	
   379	
   380	def _registry_path(request: RenderRequest) -> Path:
   381	    if request.assets_registry_path is None:
   382	        return Path.cwd() / "assets.json"
   383	    return Path(request.assets_registry_path).expanduser().resolve()
   384	
   385	
   386	def _asset_path(
   387	    entry: Mapping[str, Any],
   388	    *,
   389	    asset_id: str,
   390	    assets_path: Path,
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
    80	
    81	def _write_empty_asset_registry(path: Path) -> None:
    82	    path.parent.mkdir(parents=True, exist_ok=True)
    83	    timeline.save_registry({"assets": {}}, path)
    84	
    85	
    86	def _clip_timeline_end_seconds(clip: dict) -> float:
    87	    start = float(clip.get("at", 0) or 0)
    88	    if clip.get("clipType") == "media":
    89	        return start + _clip_duration_seconds(clip)
    90	    hold = clip.get("hold")
    91	    if isinstance(hold, (int, float)):
    92	        return start + max(0.0, float(hold))
    93	    if isinstance(clip.get("to"), (int, float)):
    94	        return float(clip["to"])
    95	    return start
    96	
    97	
    98	def _timeline_duration_seconds(timeline_data: dict) -> float:
    99	    metadata = timeline_data.get("metadata", {})
   100	    explicit = metadata.get("duration_seconds") if isinstance(metadata, dict) else None
   101	    if not isinstance(explicit, (int, float)) and isinstance(metadata, dict):
   102	        explicit = metadata.get("expected_duration_seconds")
   103	    if isinstance(explicit, (int, float)):
   104	        return float(explicit)
   105	    return max((_clip_timeline_end_seconds(clip) for clip in timeline_data.get("clips", [])), default=0.0)
   106	
   107	
   108	def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
   109	    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
   110	    instant = (
   111	        seconds
   112	        if isinstance(seconds, Fraction)
   113	        else Fraction(seconds).limit_denominator(1_000_000)
   114	    )
   115	    frames = instant * rate
99:        duration_seconds=duration,
113:        duration_seconds=duration,
196:        ("visual_gap", "Visual gap"),
240:    elif case == "visual_gap":
442:        duration_seconds=4,

exec
/bin/zsh -lc "git show HEAD:.oracle/tasklist.md | nl -ba | sed -n '45,80p'; git show HEAD:.oracle/plan.md | nl -ba | sed -n '156,173p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 313ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   156	- [ ] **M1-05 — Extract and register `rendering.remotion`**
   157	
   158	  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
   159	  - Register it through `extensions.rendering` and a static renderer manifest using the raw command protocol.
   160	  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
   161	  - Put props and asset staging under the unique invocation workdir.
   162	  - Introduce one outer cross-process lock for generated Remotion sources:
   163	    - acquire it before reading registry state or checking generated outputs;
   164	    - cover the three package registries, shim families, active-theme symlink/text pointer, and registry state;
   165	    - hold it through active-theme selection and the complete Remotion render;
   166	    - write registry state atomically;
   167	    - make the developer `gen-types` path acquire the same outer lock across `types.generated.ts` and effect-registry generation;
   168	    - ensure generator primitives do not recursively acquire the lock.
   169	  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
   170	  - Move private-helper tests to extracted boundaries while keeping a small facade compatibility suite.
   171	  - Gate: registry invalidation, atomic state, theme/profile parity, effect assets, environment redaction, concurrent differing-theme renders, render-versus-`gen-types` contention, success/failure cleanup, output validation, Remotion typecheck, and an available fixture render pass.
   172	
   173	- [ ] **M1-06 — Extract and register `rendering.ffmpeg`**

codex
Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):

1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.

2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.

3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.

4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.

5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.

6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.

7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.

8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
tokens used
494,207
Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):

1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.

2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.

3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.

4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.

5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.

6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.

7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.

8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
FILE:.oracle/checkins/batch-3-r1.md
   249	    raw_tracks = timeline_data.get("tracks")
   250	    raw_clips = timeline_data.get("clips")
   250	    raw_clips = timeline_data.get("clips")
   251	    if not isinstance(raw_tracks, list):
   252	        reasons.append("timeline tracks must be an array")
   253	        raw_tracks = []
   254	    if not isinstance(raw_clips, list):
   255	        reasons.append("timeline clips must be an array")
   256	        raw_clips = []
   257	
   258	    tracks: dict[str, Mapping[str, Any]] = {}
   259	    visual_track_ids: set[str] = set()
   260	    for index, raw_track in enumerate(raw_tracks):
   261	        if not isinstance(raw_track, Mapping):
   262	            reasons.append(f"Track at index {index} must be an object")
   263	            continue
   264	        track_id = raw_track.get("id")
   265	        if not isinstance(track_id, str) or not track_id:
   266	            reasons.append(f"Track at index {index} must have a non-empty id")
   267	            continue
   268	        if track_id in tracks:
   269	            reasons.append(f"Timeline contains duplicate track id {track_id!r}")
   270	            continue
   271	        tracks[track_id] = raw_track
   272	        kind = raw_track.get("kind")
   273	        if kind not in _TRACK_KINDS:
   274	            reasons.append(f"Track {track_id!r} has unsupported kind {kind!r}")
   275	        elif kind == "visual":
   276	            visual_track_ids.add(track_id)
   277	        reasons.extend(_validate_track_semantics(raw_track))
   278	
   279	    if len(visual_track_ids) != 1:
   280	        reasons.append("rendering.ffmpeg requires exactly one visual track")
   281	
   282	    clips: list[Mapping[str, Any]] = []
   283	    seen_clip_ids: set[str] = set()
   284	    reactive_count = 0
   285	    for index, raw_clip in enumerate(raw_clips):
   286	        if not isinstance(raw_clip, Mapping):
   287	            reasons.append(f"Clip at index {index} must be an object")
   288	            continue
   289	        clips.append(raw_clip)
   290	        clip_id = raw_clip.get("id")
   291	        if not isinstance(clip_id, str) or not clip_id:
   292	            reasons.append(f"Clip at index {index} must have a non-empty id")
   293	        elif clip_id in seen_clip_ids:
   294	            reasons.append(f"Timeline contains duplicate clip id {clip_id!r}")
   295	        else:
   296	            seen_clip_ids.add(clip_id)
   297	        track = tracks.get(str(raw_clip.get("track")))
   298	        if track is None:
   299	            reasons.append(
   300	                f"Clip {clip_id!r} references unknown track {raw_clip.get('track')!r}"
   301	            )
   302	            track = {}
   303	        clip_type = raw_clip.get("clipType")
   304	        if clip_type == audio_reactive_colour.EFFECT_ID:
   305	            reactive_count += 1
   306	            if not allow_audio_reactive:
   307	                reasons.append(
   308	                    f"rendering.ffmpeg media path does not support clip kind {clip_type!r}"
   309	                )
   310	        elif clip_type != "media":
   311	            reasons.append(
   312	                f"Clip {clip_id!r} has unsupported clip kind {clip_type!r}"
   313	            )
   314	        reasons.extend(_validate_clip_semantics(raw_clip, track))
   315	
   316	    if reactive_count:
   317	        if reactive_count != 1:
   318	            reasons.append(
   319	                "audio-reactive-colour specialization requires exactly one effect clip"
   320	            )
   321	        return _dedupe(reasons)
   322	
   323	    visual_ranges: list[_ClipRange] = []
   324	    audio_ranges: list[_ClipRange] = []
   325	    for clip in clips:
   326	        if clip.get("clipType") != "media":
   327	            continue
   328	        track = tracks.get(str(clip.get("track")), {})
   329	        try:
   330	            bounds = _clip_range(clip)
   331	        except ValueError:
   332	            continue
   333	        if track.get("kind") == "visual":
   334	            visual_ranges.append(bounds)
   335	        elif track.get("kind") == "audio":
   336	            audio_ranges.append(bounds)
   337	
   338	    visual_ranges.sort(key=lambda item: item.at)
   339	    if not visual_ranges:
   340	        reasons.append("rendering.ffmpeg needs at least one visual media clip")
   341	    else:
   342	        cursor = 0.0
   343	        for bounds in visual_ranges:
   344	            clip_id = bounds.clip.get("id")
   345	            if bounds.at > cursor + _TIMELINE_EPSILON_SECONDS:
   346	                reasons.append(
   347	                    f"Visual gap before clip {clip_id!r}: starts at {bounds.at:.6f}, expected {cursor:.6f}"
   348	                )
   349	            elif bounds.at < cursor - _TIMELINE_EPSILON_SECONDS:
   350	                reasons.append(
   351	                    f"Visual overlap at clip {clip_id!r}: starts at {bounds.at:.6f}, previous visual ends at {cursor:.6f}"
   352	                )
   353	            cursor = max(cursor, bounds.end)
   354	
   355	        audio_ranges.sort(key=lambda item: item.at)
   356	        audio_cursor = 0.0
   357	        for bounds in audio_ranges:
   358	            clip_id = bounds.clip.get("id")
   359	            if bounds.at < audio_cursor - _TIMELINE_EPSILON_SECONDS:
   360	                reasons.append(
   361	                    f"Overlapping audio at clip {clip_id!r}: starts at {bounds.at:.6f}, previous audio ends at {audio_cursor:.6f}"
   362	                )
   363	            if bounds.end > cursor + _TIMELINE_EPSILON_SECONDS:
   364	                reasons.append(
   365	                    f"Audio clip {clip_id!r} ends outside the visual frame bounds"
   366	                )
   367	            audio_cursor = max(audio_cursor, bounds.end)
   368	    return _dedupe(reasons)
   369	
   370	
   371	def _dedupe(reasons: list[str]) -> list[str]:
   372	    return list(dict.fromkeys(reason for reason in reasons if reason))
   373	
   374	
   375	def _assets_table(assets: Mapping[str, Any]) -> Mapping[str, Any] | None:
   376	    value = assets.get("assets")
   377	    return value if isinstance(value, Mapping) else None
   378	
   379	
   380	def _registry_path(request: RenderRequest) -> Path:
   381	    if request.assets_registry_path is None:
   382	        return Path.cwd() / "assets.json"
   383	    return Path(request.assets_registry_path).expanduser().resolve()
   384	
   385	
   386	def _asset_path(
   387	    entry: Mapping[str, Any],
   388	    *,
   389	    asset_id: str,
   390	    assets_path: Path,
   391	) -> Path:
   392	    if _nonempty(entry.get("url")):
   393	        raise ValueError(
   394	            f"Asset {asset_id!r} is remote; rendering.ffmpeg requires a local source file"
   395	        )
   396	    file_value = entry.get("file")
   397	    if not isinstance(file_value, str) or not file_value:
   398	        raise ValueError(f"Asset {asset_id!r} has no local source file")
   399	    path = Path(file_value).expanduser()
   400	    if not path.is_absolute():

context compacted
codex
1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)

2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)

4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)

5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)

6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
tokens used
461,027
1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)

2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)

4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)

5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)

6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
FILE:.oracle/checkins/batch-3-r2.md
    28	  supports_windows: false
    29	  output_profiles:
    30	    - video/mp4
    31	  audio_ownership:
    32	    - rendered
    33	required_permissions:
    34	  - project_files
    35	  - subprocess
    36	required_binaries:
    37	  - node
    38	  - npx
    39	  - ffprobe
   475	    probed_duration = _probe_duration(media_probe)
   476	    probed_fps = media_probe.fps
   477	    if probed_fps is None and media_probe.fps_rational is not None:
   478	        numerator, denominator = media_probe.fps_rational
   479	        probed_fps = numerator / denominator
   480	    return (
   481	        bounds.at == 0
   482	        and bounds.source_from == 0
   483	        and abs(bounds.duration - duration) < 0.05
   484	        and entry.get("resolution") == f"{width}x{height}"
   485	        and abs(source_fps - fps) < 1e-6
   486	        and probed_duration is not None
   487	        and abs(bounds.duration - probed_duration) < 0.05
   488	        and media_probe.width == width
   489	        and media_probe.height == height
   490	        and probed_fps is not None
   491	        and abs(probed_fps - fps) < 1e-6
   492	        and (media_probe.video_codec or "") == "h264"
   493	        and (media_probe.pixel_format or "") == "yuv420p"
   494	    )
   495	
   496	
   497	def _profile_support_reasons(
   498	    request: RenderRequest, timeline_data: Mapping[str, Any]
   499	) -> list[str]:
   500	    """Fail closed when the requested profile deviates from what the FFmpeg
   501	    backend actually produces (canvas dims/fps, codecs, pixel format, and
   502	    canonical audio rate/layout)."""
   503	    profile = request.profile
   504	    if profile is None:
   505	        return []
   506	    reasons: list[str] = []
   507	    try:
   508	        width, height, fps = _canvas(timeline_data)
   509	    except ValueError:
   510	        return reasons  # canvas failure already reported elsewhere
   511	    checks = (
   512	        ("width", profile.width, width),
   513	        ("height", profile.height, height),
   514	        ("fps", _fps_int(profile.fps_rational), fps),
   515	        ("time_base", profile.time_base, (1, fps * 512)),
   516	        ("container", profile.container, "mp4"),
   517	        ("video_codec", profile.video_codec, "h264"),
   518	        ("pixel_format", profile.pixel_format, "yuv420p"),
   519	    )
   520	    for field, requested, produced in checks:
   521	        if requested is not None and requested != produced:
   522	            reasons.append(
   523	                f"requested profile {field}={requested!r} is not produced by "
   524	                f"rendering.ffmpeg (produces {produced!r})"
   525	            )
   526	    if profile.has_audio:
   527	        for field, requested, produced in (
   528	            ("audio_sample_rate", profile.audio_sample_rate, 48000),
   529	            ("audio_channel_layout", profile.audio_channel_layout, "stereo"),
   530	            ("audio_codec", profile.audio_codec, "aac"),
   531	        ):
   532	            if requested is not None and requested != produced:
   533	                reasons.append(
   534	                    f"requested profile {field}={requested!r} is not produced by "
   535	                    f"rendering.ffmpeg (produces {produced!r})"
   536	                )
   537	    return reasons
   538	
   539	
   540	def _fps_int(fps_rational: tuple[int, int] | None) -> int | None:
   250	                "cropLeft",
   251	                "cropRight",
   252	                "effects",
   253	                "transition",
   254	            )
   255	        )
   256	        if (
   257	            inputs.stream_copy_allowed
   258	            and at == 0
   259	            and start == 0
   260	            and full_duration
   261	            and same_resolution
   262	            and same_fps
   263	            and no_visual_adjustments
   264	        ):
   265	            copy_video_input = asset_index[asset_key]
   266	    if copy_video_input is None:
   267	        for index, clip in enumerate(video_clips):
   268	            inp = asset_index[str(clip["asset"])]
   269	            start = float(clip.get("from", 0) or 0)
   270	            end = float(clip.get("to", start) or start)
   175	        raise ValueError("canvas fps must be positive")
   176	    return fps
   177	
   178	
   179	def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
   180	    """Mirror FFmpeg's MP4 video-track timescale selection.
   181	
   182	    Integer rates are repeatedly doubled until the timescale is at least
   183	    10,000 (24 -> 12,288; 30 -> 15,360).  NTSC-style rationals already carry
   184	    a large numerator (30000/1001 -> 30,000).
   185	    """
   186	
   187	    timescale = fps.numerator
   188	    while timescale < 10_000:
   189	        timescale *= 2
   190	    return 1, timescale
   191	
   192	

exec
/bin/zsh -lc "node -p \"require('./remotion/node_modules/@remotion/renderer/package.json').version\"; nl -ba remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js | sed -n '5,18p'; nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '560,585p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
4.0.455
     5	const DEFAULT_ENFORCE_AUDIO_TRACK = false;
     6	let enforceAudioTrackState = DEFAULT_ENFORCE_AUDIO_TRACK;
     7	const cliFlag = 'enforce-audio-track';
     8	exports.enforceAudioOption = {
     9	    name: 'Enforce Audio Track',
    10	    cliFlag,
    11	    description: () => (jsx_runtime_1.jsx(jsx_runtime_1.Fragment, { children: "Render a silent audio track if there would be none otherwise." })),
    12	    ssrName: 'enforceAudioTrack',
    13	    docLink: 'https://www.remotion.dev/docs/config#setenforceaudiotrack-',
    14	    type: false,
    15	    getValue: ({ commandLine }) => {
    16	        if (commandLine[cliFlag]) {
    17	            return {
    18	                source: 'cli',
   560	    try:
   561	        if specialization_spec is not None:
   562	            audio_reactive_colour.render(specialization_spec, output_path)
   563	        else:
   564	            subprocess.run(build_render_command(request, workspace), check=True)
   565	        try:
   566	            probe = ffprobe_metadata_strict(output_path)
   567	            probed_profile = _profile_from_probe(probe, ownership)
   568	        except (MediaProbeError, RuntimeError) as exc:
   569	            raise_invalid_artifact_error(
   570	                backend=BACKEND_ID,
   571	                message=f"FFmpeg output could not be validated: {exc}",
   572	                recovery_command=(
   573	                    "rerun rendering.ffmpeg in a fresh invocation workspace"
   574	                ),
   575	                details={"error_type": type(exc).__name__},
   576	            )
   577	        declared_profile = request.profile or probed_profile
   578	        duration_frames = _duration_frames(probe, declared_profile)
   579	        provenance_v1 = remotion_backend._render_provenance_payload(
   580	            output_path,
   581	            engine="ffmpeg",
   582	            timeline_path=timeline_path,
   583	            assets_path=assets_path,
   584	            project_dir=REPO_ROOT / "remotion",
   585	            composition_id="TimelineComposition",

codex
1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)

3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)

4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)
tokens used
450,040
1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)

3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)

4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)

exec
/bin/zsh -lc 'git show --stat --oneline --decorate a7b7b080 && git show --format=fuller --no-patch a7b7b080' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
a7b7b080 (HEAD -> oracle-run) batch3-rework3: oracle re-review2 issues 1-4 (remotion --enforce-audio-track, canonical MP4 time-base rule + rational-aware ffmpeg support, stream-copy time-base gate, frame-accurate whole-source tolerance)
 .oracle/checkins/batch-3-r2.md                    | 14396 ++++++++++++++++++++
 astrid/packs/rendering/backends/ffmpeg/support.py |    40 +-
 astrid/packs/rendering/backends/remotion/run.py   |     1 +
 tests/packs/rendering/test_ffmpeg_backend.py      |     1 +
 tests/packs/rendering/test_ffmpeg_support.py      |     1 +
 5 files changed, 14434 insertions(+), 5 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit a7b7b08001cd4a61a801df5ea593b0d4f0727201
Author:     POM <peter@omalley.io>
AuthorDate: Wed Aug 12 14:24:06 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Wed Aug 12 14:24:06 2026 +0200

    batch3-rework3: oracle re-review2 issues 1-4 (remotion --enforce-audio-track, canonical MP4 time-base rule + rational-aware ffmpeg support, stream-copy time-base gate, frame-accurate whole-source tolerance)

codex
The four intended code paths are present. I’m now tracing them against the actual profile builder, FFmpeg command construction, probe model, and Remotion CLI invocation—the places where a seemingly correct local patch can still disagree with runtime behavior.
exec
/bin/zsh -lc "rg -n '"'^## Batch 3|''^'"\\*\\*Acceptance criteria|"'^### Tasks|T3'"\\.[1-6]' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
7:**Acceptance criteria:**
18:### Tasks
30:**Acceptance criteria:**
41:### Tasks
50:## Batch 3 — Built-in renderer and finalizer extraction
54:**Acceptance criteria:**
64:### Tasks
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
77:**Acceptance criteria:**
87:### Tasks
99:**Acceptance criteria:**
110:### Tasks
124:**Acceptance criteria:**
134:### Tasks
147:**Acceptance criteria:**
160:### Tasks

exec
/bin/zsh -lc "sed -n '1,180p' astrid/core/rendering/profile.py && sed -n '1,220p' astrid/core/media.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
"""Canonical render-profile resolution for timeline rendering."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

from astrid.core.theme import resolve_themes_root
from astrid.core.timeline import Timeline, resolve_timeline_theme

from .contracts import AudioOwnership, RenderProfile


_DEFAULT_CANVAS = {"width": 1920, "height": 1080, "fps": 30}
_DEFAULT_THEME = "banodoco-default"


def _load_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (str, Path)):
        path = Path(value)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{label} must contain a JSON object")
        return data
    to_config = getattr(value, "to_config", None)
    if callable(to_config):
        data = to_config()
        if isinstance(data, Mapping):
            return dict(data)
    raise TypeError(f"{label} must be a mapping, JSON path, or Timeline")


def _timeline_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Timeline):
        return dict(value.to_config())
    return _load_mapping(value, label="timeline")


def _asset_mapping(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return _load_mapping(value, label="assets registry")


def _deep_merge_theme(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Mirror the timeline theme merge used by ``resolve_timeline_theme``."""

    result: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged_block: dict[str, Any] = dict(existing)
            for sub_key, sub_value in value.items():
                existing_sub = merged_block.get(sub_key)
                if isinstance(existing_sub, Mapping) and isinstance(sub_value, Mapping):
                    inner = dict(existing_sub)
                    inner.update(sub_value)
                    merged_block[sub_key] = inner
                else:
                    merged_block[sub_key] = sub_value
            result[key] = merged_block
        else:
            result[key] = value
    return result


def _read_theme_path(path: Path) -> dict[str, Any]:
    theme_path = path / "theme.json" if path.is_dir() else path
    return _load_mapping(theme_path, label="theme")


def _resolve_merged_theme(
    timeline: Mapping[str, Any],
    *,
    theme: Mapping[str, Any] | str | Path | None,
    themes_root: str | Path | None,
) -> dict[str, Any]:
    overrides = timeline.get("theme_overrides")
    override_mapping = overrides if isinstance(overrides, Mapping) else {}

    if isinstance(theme, Mapping):
        return _deep_merge_theme(theme, override_mapping)

    root = resolve_themes_root(themes_root)
    if theme is not None:
        candidate = Path(theme).expanduser()
        if candidate.exists() or candidate.name == "theme.json":
            return _deep_merge_theme(_read_theme_path(candidate), override_mapping)
        config = dict(timeline)
        config["theme"] = str(theme)
    else:
        config = dict(timeline)
        config.setdefault("theme", _DEFAULT_THEME)

    try:
        return resolve_timeline_theme(config, root)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        # Remotion falls back to DEFAULT_CANVAS when neither a theme nor a
        # complete override can provide a canvas.  Keeping the empty merged
        # theme here lets the exact getCanvas precedence below do the same.
        return _deep_merge_theme({}, override_mapping)


def _remotion_canvas(
    timeline: Mapping[str, Any], merged_theme: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Return the canvas selected by ``remotion/src/Root.tsx::getCanvas``.

    Root selects the *whole* override canvas before the resolved theme canvas.
    A partial override consequently falls back to Remotion's field defaults,
    not to the missing fields in the base theme.  Mirroring that edge is
    important: this profile is the contract for what Remotion actually emits.
    """

    overrides = timeline.get("theme_overrides")
    if isinstance(overrides, Mapping):
        visual = overrides.get("visual")
        if isinstance(visual, Mapping) and isinstance(visual.get("canvas"), Mapping):
            return visual["canvas"]
    visual = merged_theme.get("visual")
    if isinstance(visual, Mapping) and isinstance(visual.get("canvas"), Mapping):
        return visual["canvas"]
    return _DEFAULT_CANVAS


def _positive_dimension(value: Any, *, default: int, label: str) -> int:
    candidate = default if value is None else value
    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
        raise TypeError(f"canvas {label} must be a positive integer")
    if isinstance(candidate, float) and not candidate.is_integer():
        raise ValueError(f"canvas {label} must be a positive integer")
    result = int(candidate)
    if result <= 0:
        raise ValueError(f"canvas {label} must be a positive integer")
    return result


def _fps_fraction(value: Any) -> Fraction:
    if isinstance(value, bool):
        raise TypeError("canvas fps must be a positive number or rational")
    if isinstance(value, str):
        try:
            fps = Fraction(value)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError(f"invalid canvas fps {value!r}") from exc
    elif (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) == 2
    ):
        numerator, denominator = value
        if type(numerator) is not int or type(denominator) is not int:
            raise TypeError("canvas fps rational must contain two integers")
        try:
            fps = Fraction(numerator, denominator)
        except ZeroDivisionError as exc:
            raise ValueError("canvas fps denominator must be positive") from exc
    elif isinstance(value, int):
        fps = Fraction(value, 1)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canvas fps must be finite")
        # Decimal text is the authored value.  Fraction(float) would preserve
        # the binary approximation and make the wire profile drift.
        fps = Fraction(str(value))
    else:
        raise TypeError("canvas fps must be a positive number or rational")
    if fps <= 0:
        raise ValueError("canvas fps must be positive")
    return fps


def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
    """Mirror FFmpeg's MP4 video-track timescale selection.
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
    container: str | None = None
    format_name: str | None = None
    duration_rational: tuple[int, int] | None = None
    video_stream_present: bool | None = None
    audio_stream_present: bool | None = None
    # Appended last so existing positional construction is unaffected.
    audio_channels: int | None = None

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

exec
/bin/zsh -lc "rg -n -C 8 'video_track_timescale|time_base|stream_copy|_whole_media_optimization|_profile_support_reasons|build_render_command' astrid/packs/rendering/backends/ffmpeg tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_support.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/packs/rendering/test_ffmpeg_backend.py-128-    )
tests/packs/rendering/test_ffmpeg_backend.py-129-
tests/packs/rendering/test_ffmpeg_backend.py-130-
tests/packs/rendering/test_ffmpeg_backend.py-131-def _profile() -> RenderProfile:
tests/packs/rendering/test_ffmpeg_backend.py-132-    return RenderProfile(
tests/packs/rendering/test_ffmpeg_backend.py-133-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-134-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-135-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_backend.py:136:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-137-        container="mp4",
tests/packs/rendering/test_ffmpeg_backend.py-138-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py-139-        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py-140-        video_level="4.0",
tests/packs/rendering/test_ffmpeg_backend.py-141-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-142-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-143-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_backend.py-144-        audio_channel_layout="stereo",
--
tests/packs/rendering/test_ffmpeg_backend.py-180-    tmp_path: Path,
tests/packs/rendering/test_ffmpeg_backend.py-181-) -> None:
tests/packs/rendering/test_ffmpeg_backend.py-182-    timeline_path, assets_path = _write_inputs(tmp_path)
tests/packs/rendering/test_ffmpeg_backend.py-183-    source_probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_backend.py-184-        duration_seconds=2,
tests/packs/rendering/test_ffmpeg_backend.py-185-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-186-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-187-        fps=30,
tests/packs/rendering/test_ffmpeg_backend.py:188:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-189-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py-190-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-191-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-192-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_backend.py-193-        audio_stream_present=True,
tests/packs/rendering/test_ffmpeg_backend.py-194-    )
tests/packs/rendering/test_ffmpeg_backend.py-195-
tests/packs/rendering/test_ffmpeg_backend.py-196-    with mock.patch.object(
--
tests/packs/rendering/test_ffmpeg_backend.py-270-        cwd=ROOT / "astrid" / "packs" / "rendering",
tests/packs/rendering/test_ffmpeg_backend.py-271-    )
tests/packs/rendering/test_ffmpeg_backend.py-272-
tests/packs/rendering/test_ffmpeg_backend.py-273-    assert isinstance(report, SupportReport)
tests/packs/rendering/test_ffmpeg_backend.py-274-    assert report.backend == ffmpeg.BACKEND_ID
tests/packs/rendering/test_ffmpeg_backend.py-275-    assert report.supported is False
tests/packs/rendering/test_ffmpeg_backend.py-276-
tests/packs/rendering/test_ffmpeg_backend.py-277-
tests/packs/rendering/test_ffmpeg_backend.py:278:def test_build_render_command_is_pure_and_preserves_stream_copy(
tests/packs/rendering/test_ffmpeg_backend.py-279-    tmp_path: Path,
tests/packs/rendering/test_ffmpeg_backend.py-280-) -> None:
tests/packs/rendering/test_ffmpeg_backend.py-281-    timeline_path, assets_path = _write_inputs(tmp_path)
tests/packs/rendering/test_ffmpeg_backend.py-282-    request = _request(timeline_path, assets_path)
tests/packs/rendering/test_ffmpeg_backend.py-283-    inputs = command.resolve_render_command_inputs(request, tmp_path)
tests/packs/rendering/test_ffmpeg_backend.py-284-
tests/packs/rendering/test_ffmpeg_backend.py-285-    # Stream-copy is gated on probe evidence; the pure builder emits the copy
tests/packs/rendering/test_ffmpeg_backend.py:286:    # path only when the caller passes stream_copy_allowed=True. A placeholder
tests/packs/rendering/test_ffmpeg_backend.py-287-    # source (no real probe) must default to re-encoding.
tests/packs/rendering/test_ffmpeg_backend.py:288:    argv = command.build_render_command(request, tmp_path)
tests/packs/rendering/test_ffmpeg_backend.py-289-    assert argv[argv.index("-c:v") + 1] == "libx264"
tests/packs/rendering/test_ffmpeg_backend.py-290-
tests/packs/rendering/test_ffmpeg_backend.py:291:    copy_argv = command.build_render_command_from_inputs(
tests/packs/rendering/test_ffmpeg_backend.py:292:        dataclasses.replace(inputs, stream_copy_allowed=True)
tests/packs/rendering/test_ffmpeg_backend.py-293-    )
tests/packs/rendering/test_ffmpeg_backend.py-294-    assert copy_argv[copy_argv.index("-c:v") + 1] == "copy"
tests/packs/rendering/test_ffmpeg_backend.py-295-    assert copy_argv[-1] == str((tmp_path / "outputs" / "result.mp4").resolve())
tests/packs/rendering/test_ffmpeg_backend.py-296-    assert not (tmp_path / "outputs").exists()
tests/packs/rendering/test_ffmpeg_backend.py-297-
tests/packs/rendering/test_ffmpeg_backend.py-298-
tests/packs/rendering/test_ffmpeg_backend.py:299:def test_build_render_command_encodes_visual_only_without_synthesizing_silence(
tests/packs/rendering/test_ffmpeg_backend.py-300-    tmp_path: Path,
tests/packs/rendering/test_ffmpeg_backend.py-301-) -> None:
tests/packs/rendering/test_ffmpeg_backend.py-302-    timeline_path, assets_path = _write_inputs(
tests/packs/rendering/test_ffmpeg_backend.py-303-        tmp_path,
tests/packs/rendering/test_ffmpeg_backend.py-304-        timeline_data=_media_timeline(include_audio=False),
tests/packs/rendering/test_ffmpeg_backend.py-305-        source_resolution="1280x720",
tests/packs/rendering/test_ffmpeg_backend.py-306-    )
tests/packs/rendering/test_ffmpeg_backend.py-307-
tests/packs/rendering/test_ffmpeg_backend.py:308:    argv = command.build_render_command(
tests/packs/rendering/test_ffmpeg_backend.py-309-        _request(timeline_path, assets_path),
tests/packs/rendering/test_ffmpeg_backend.py-310-        tmp_path,
tests/packs/rendering/test_ffmpeg_backend.py-311-    )
tests/packs/rendering/test_ffmpeg_backend.py-312-
tests/packs/rendering/test_ffmpeg_backend.py-313-    filters = argv[argv.index("-filter_complex") + 1]
tests/packs/rendering/test_ffmpeg_backend.py-314-    assert (
tests/packs/rendering/test_ffmpeg_backend.py-315-        "[0:v]trim=start=0.000000:end=2.000000,setpts=PTS-STARTPTS,"
tests/packs/rendering/test_ffmpeg_backend.py-316-        "scale=1920:1080:force_original_aspect_ratio=decrease,"
--
tests/packs/rendering/test_ffmpeg_backend.py-339-        output.parent.mkdir(parents=True, exist_ok=True)
tests/packs/rendering/test_ffmpeg_backend.py-340-        output.write_bytes(b"ffmpeg-video")
tests/packs/rendering/test_ffmpeg_backend.py-341-        return subprocess.CompletedProcess(argv, 0)
tests/packs/rendering/test_ffmpeg_backend.py-342-
tests/packs/rendering/test_ffmpeg_backend.py-343-    probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_backend.py-344-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-345-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-346-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_backend.py:347:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-348-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py-349-        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py-350-        video_level="40",
tests/packs/rendering/test_ffmpeg_backend.py-351-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-352-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-353-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_backend.py-354-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_backend.py-355-        audio_channels=2,
--
tests/packs/rendering/test_ffmpeg_support.py-95-
tests/packs/rendering/test_ffmpeg_support.py-96-
tests/packs/rendering/test_ffmpeg_support.py-97-def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
tests/packs/rendering/test_ffmpeg_support.py-98-    return MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-99-        duration_seconds=duration,
tests/packs/rendering/test_ffmpeg_support.py-100-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-101-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-102-        fps=30,
tests/packs/rendering/test_ffmpeg_support.py:103:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-104-        resolution="640x360",
tests/packs/rendering/test_ffmpeg_support.py-105-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py-106-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-107-        audio_codec="aac" if audio else None,
tests/packs/rendering/test_ffmpeg_support.py-108-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_support.py-109-        audio_stream_present=audio,
tests/packs/rendering/test_ffmpeg_support.py-110-    )
tests/packs/rendering/test_ffmpeg_support.py-111-
--
tests/packs/rendering/test_ffmpeg_support.py-167-        assets,
tests/packs/rendering/test_ffmpeg_support.py-168-        probe=lambda path: probe_map[Path(path).name],
tests/packs/rendering/test_ffmpeg_support.py-169-        which=which or (lambda binary: f"/usr/bin/{binary}"),
tests/packs/rendering/test_ffmpeg_support.py-170-    )
tests/packs/rendering/test_ffmpeg_support.py-171-
tests/packs/rendering/test_ffmpeg_support.py-172-
tests/packs/rendering/test_ffmpeg_support.py-173-def _build_command(tmp_path: Path, timeline_data: dict, assets: dict) -> list[str]:
tests/packs/rendering/test_ffmpeg_support.py-174-    _evaluate(tmp_path, timeline_data, assets)
tests/packs/rendering/test_ffmpeg_support.py:175:    return command.build_render_command(_request(tmp_path), tmp_path)
tests/packs/rendering/test_ffmpeg_support.py-176-
tests/packs/rendering/test_ffmpeg_support.py-177-
tests/packs/rendering/test_ffmpeg_support.py-178-def test_supported_report_exposes_request_specific_evidence(tmp_path: Path) -> None:
tests/packs/rendering/test_ffmpeg_support.py-179-    report = _evaluate(tmp_path, _timeline(), _assets(tmp_path))
tests/packs/rendering/test_ffmpeg_support.py-180-
tests/packs/rendering/test_ffmpeg_support.py-181-    assert report.supported is True
tests/packs/rendering/test_ffmpeg_support.py-182-    assert report.reasons == []
tests/packs/rendering/test_ffmpeg_support.py-183-    assert report.alternatives == []
tests/packs/rendering/test_ffmpeg_support.py-184-    assert report.features["whole_media"] is True
tests/packs/rendering/test_ffmpeg_support.py:185:    assert report.features["stream_copy"] is True
tests/packs/rendering/test_ffmpeg_support.py-186-    assert report.features["audio_reactive_colour"] is False
tests/packs/rendering/test_ffmpeg_support.py-187-    assert report.features["audio_ownership"] == "rendered"
tests/packs/rendering/test_ffmpeg_support.py-188-
tests/packs/rendering/test_ffmpeg_support.py-189-
tests/packs/rendering/test_ffmpeg_support.py-190-@pytest.mark.parametrize(
tests/packs/rendering/test_ffmpeg_support.py-191-    ("case", "reason"),
tests/packs/rendering/test_ffmpeg_support.py-192-    [
tests/packs/rendering/test_ffmpeg_support.py-193-        ("unknown_track_kind", "unsupported kind"),
--
tests/packs/rendering/test_ffmpeg_support.py-376-            "id": "audio_2",
tests/packs/rendering/test_ffmpeg_support.py-377-            "at": 2,
tests/packs/rendering/test_ffmpeg_support.py-378-            "from": 1,
tests/packs/rendering/test_ffmpeg_support.py-379-            "to": 3,
tests/packs/rendering/test_ffmpeg_support.py-380-        }
tests/packs/rendering/test_ffmpeg_support.py-381-    )
tests/packs/rendering/test_ffmpeg_support.py-382-
tests/packs/rendering/test_ffmpeg_support.py-383-    report = _evaluate(tmp_path, timeline_data, _assets(tmp_path))
tests/packs/rendering/test_ffmpeg_support.py:384:    argv = command.build_render_command(_request(tmp_path), tmp_path)
tests/packs/rendering/test_ffmpeg_support.py-385-    filters = argv[argv.index("-filter_complex") + 1]
tests/packs/rendering/test_ffmpeg_support.py-386-
tests/packs/rendering/test_ffmpeg_support.py-387-    assert report.supported is True
tests/packs/rendering/test_ffmpeg_support.py-388-    assert "anullsrc=r=48000:cl=stereo,atrim=duration=1.000000" in filters
tests/packs/rendering/test_ffmpeg_support.py-389-    assert filters.count("volume=0.200000") == 2
tests/packs/rendering/test_ffmpeg_support.py-390-    assert "concat=n=3:v=0:a=1[aout]" in filters
tests/packs/rendering/test_ffmpeg_support.py-391-
tests/packs/rendering/test_ffmpeg_support.py-392-
--
tests/packs/rendering/test_ffmpeg_support.py-398-    del assets["assets"]["audio"]
tests/packs/rendering/test_ffmpeg_support.py-399-
tests/packs/rendering/test_ffmpeg_support.py-400-    report = _evaluate(
tests/packs/rendering/test_ffmpeg_support.py-401-        tmp_path,
tests/packs/rendering/test_ffmpeg_support.py-402-        timeline_data,
tests/packs/rendering/test_ffmpeg_support.py-403-        assets,
tests/packs/rendering/test_ffmpeg_support.py-404-        probes={"video.mp4": _video_probe()},
tests/packs/rendering/test_ffmpeg_support.py-405-    )
tests/packs/rendering/test_ffmpeg_support.py:406:    argv = command.build_render_command(_request(tmp_path), tmp_path)
tests/packs/rendering/test_ffmpeg_support.py-407-
tests/packs/rendering/test_ffmpeg_support.py-408-    assert report.supported is True
tests/packs/rendering/test_ffmpeg_support.py-409-    assert report.features["audio_ownership"] == "none"
tests/packs/rendering/test_ffmpeg_support.py-410-    # Without probe evidence of whole-source compatibility, stream-copy must
tests/packs/rendering/test_ffmpeg_support.py-411-    # NOT be trusted from registry metadata: the builder re-encodes via
tests/packs/rendering/test_ffmpeg_support.py-412-    # filter_complex with no audio mapping (-an).
tests/packs/rendering/test_ffmpeg_support.py-413-    assert "-filter_complex" in argv
tests/packs/rendering/test_ffmpeg_support.py-414-    assert "-c:a" not in argv
--
tests/packs/rendering/test_ffmpeg_support.py-444-        probes={"video.mp4": _video_probe()},
tests/packs/rendering/test_ffmpeg_support.py-445-    )
tests/packs/rendering/test_ffmpeg_support.py-446-    probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-447-        duration_seconds=4,
tests/packs/rendering/test_ffmpeg_support.py-448-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-449-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-450-        fps=30,
tests/packs/rendering/test_ffmpeg_support.py-451-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py:452:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-453-        resolution="640x360",
tests/packs/rendering/test_ffmpeg_support.py-454-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py-455-        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py-456-        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py-457-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-458-        container="mp4",
tests/packs/rendering/test_ffmpeg_support.py-459-        duration_rational=(4, 1),
tests/packs/rendering/test_ffmpeg_support.py-460-        video_stream_present=True,
--
tests/packs/rendering/test_ffmpeg_support.py-564-    assert report.features["specialization"] == "audio-reactive-colour/v1"
tests/packs/rendering/test_ffmpeg_support.py-565-    assert spec is not None
tests/packs/rendering/test_ffmpeg_support.py-566-    assert spec.audio_volume == pytest.approx(0.2)
tests/packs/rendering/test_ffmpeg_support.py-567-
tests/packs/rendering/test_ffmpeg_support.py-568-    output_probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-569-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-570-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-571-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py:572:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-573-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py-574-        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py-575-        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py-576-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-577-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_support.py-578-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_support.py-579-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_support.py-580-        audio_channels=2,
--
astrid/packs/rendering/backends/ffmpeg/support.py-9-
astrid/packs/rendering/backends/ffmpeg/support.py-10-import math
astrid/packs/rendering/backends/ffmpeg/support.py-11-import shutil
astrid/packs/rendering/backends/ffmpeg/support.py-12-from collections.abc import Callable, Mapping
astrid/packs/rendering/backends/ffmpeg/support.py-13-from dataclasses import dataclass
astrid/packs/rendering/backends/ffmpeg/support.py-14-from fractions import Fraction
astrid/packs/rendering/backends/ffmpeg/support.py-15-from pathlib import Path
astrid/packs/rendering/backends/ffmpeg/support.py-16-
astrid/packs/rendering/backends/ffmpeg/support.py:17:from astrid.core.rendering.profile import _mp4_time_base
astrid/packs/rendering/backends/ffmpeg/support.py-18-from typing import Any
astrid/packs/rendering/backends/ffmpeg/support.py-19-
astrid/packs/rendering/backends/ffmpeg/support.py-20-from astrid.core.media import MediaProbe, ffprobe_metadata_strict
astrid/packs/rendering/backends/ffmpeg/support.py-21-from astrid.core.rendering.contracts import (
astrid/packs/rendering/backends/ffmpeg/support.py-22-    AudioOwnership,
astrid/packs/rendering/backends/ffmpeg/support.py-23-    RenderRequest,
astrid/packs/rendering/backends/ffmpeg/support.py-24-    SCHEMA_VERSION,
astrid/packs/rendering/backends/ffmpeg/support.py-25-    SupportReport,
--
astrid/packs/rendering/backends/ffmpeg/support.py-436-        ownership is AudioOwnership.RENDERED
astrid/packs/rendering/backends/ffmpeg/support.py-437-    ):
astrid/packs/rendering/backends/ffmpeg/support.py-438-        reasons.append(
astrid/packs/rendering/backends/ffmpeg/support.py-439-            "requested profile audio fields do not match rendering.ffmpeg audio ownership"
astrid/packs/rendering/backends/ffmpeg/support.py-440-        )
astrid/packs/rendering/backends/ffmpeg/support.py-441-    return ownership, reasons
astrid/packs/rendering/backends/ffmpeg/support.py-442-
astrid/packs/rendering/backends/ffmpeg/support.py-443-
astrid/packs/rendering/backends/ffmpeg/support.py:444:def _whole_media_optimization(
astrid/packs/rendering/backends/ffmpeg/support.py-445-    timeline_data: Mapping[str, Any],
astrid/packs/rendering/backends/ffmpeg/support.py-446-    assets: Mapping[str, Any],
astrid/packs/rendering/backends/ffmpeg/support.py-447-    probes: Mapping[str, MediaProbe],
astrid/packs/rendering/backends/ffmpeg/support.py-448-) -> bool:
astrid/packs/rendering/backends/ffmpeg/support.py-449-    tracks = {
astrid/packs/rendering/backends/ffmpeg/support.py-450-        track.get("id"): track
astrid/packs/rendering/backends/ffmpeg/support.py-451-        for track in timeline_data.get("tracks", [])
astrid/packs/rendering/backends/ffmpeg/support.py-452-        if isinstance(track, Mapping)
--
astrid/packs/rendering/backends/ffmpeg/support.py-493-        and probed_duration is not None
astrid/packs/rendering/backends/ffmpeg/support.py-494-        and abs(bounds.duration - probed_duration) < frame_tolerance
astrid/packs/rendering/backends/ffmpeg/support.py-495-        and media_probe.width == width
astrid/packs/rendering/backends/ffmpeg/support.py-496-        and media_probe.height == height
astrid/packs/rendering/backends/ffmpeg/support.py-497-        and probed_fps is not None
astrid/packs/rendering/backends/ffmpeg/support.py-498-        and abs(probed_fps - fps) < 1e-6
astrid/packs/rendering/backends/ffmpeg/support.py-499-        and (media_probe.video_codec or "") == "h264"
astrid/packs/rendering/backends/ffmpeg/support.py-500-        and (media_probe.pixel_format or "") == "yuv420p"
astrid/packs/rendering/backends/ffmpeg/support.py:501:        and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
astrid/packs/rendering/backends/ffmpeg/support.py-502-    )
astrid/packs/rendering/backends/ffmpeg/support.py-503-
astrid/packs/rendering/backends/ffmpeg/support.py-504-
astrid/packs/rendering/backends/ffmpeg/support.py:505:def _probe_time_base_matches(
astrid/packs/rendering/backends/ffmpeg/support.py-506-    probe: MediaProbe, expected: tuple[int, int]
astrid/packs/rendering/backends/ffmpeg/support.py-507-) -> bool:
astrid/packs/rendering/backends/ffmpeg/support.py-508-    """The probed stream time base must equal the canonical MP4 timescale."""
astrid/packs/rendering/backends/ffmpeg/support.py:509:    if probe.time_base is None:
astrid/packs/rendering/backends/ffmpeg/support.py-510-        return False
astrid/packs/rendering/backends/ffmpeg/support.py:511:    return Fraction(*probe.time_base) == Fraction(*expected)
astrid/packs/rendering/backends/ffmpeg/support.py-512-
astrid/packs/rendering/backends/ffmpeg/support.py-513-
astrid/packs/rendering/backends/ffmpeg/support.py:514:def _profile_support_reasons(
astrid/packs/rendering/backends/ffmpeg/support.py-515-    request: RenderRequest, timeline_data: Mapping[str, Any]
astrid/packs/rendering/backends/ffmpeg/support.py-516-) -> list[str]:
astrid/packs/rendering/backends/ffmpeg/support.py-517-    """Fail closed when the requested profile deviates from what the FFmpeg
astrid/packs/rendering/backends/ffmpeg/support.py-518-    backend actually produces (canvas dims/fps, codecs, pixel format, and
astrid/packs/rendering/backends/ffmpeg/support.py-519-    canonical audio rate/layout)."""
astrid/packs/rendering/backends/ffmpeg/support.py-520-    profile = request.profile
astrid/packs/rendering/backends/ffmpeg/support.py-521-    if profile is None:
astrid/packs/rendering/backends/ffmpeg/support.py-522-        return []
--
astrid/packs/rendering/backends/ffmpeg/support.py-524-    try:
astrid/packs/rendering/backends/ffmpeg/support.py-525-        width, height, fps = _canvas(timeline_data)
astrid/packs/rendering/backends/ffmpeg/support.py-526-    except ValueError:
astrid/packs/rendering/backends/ffmpeg/support.py-527-        return reasons  # canvas failure already reported elsewhere
astrid/packs/rendering/backends/ffmpeg/support.py-528-    checks = (
astrid/packs/rendering/backends/ffmpeg/support.py-529-        ("width", profile.width, width),
astrid/packs/rendering/backends/ffmpeg/support.py-530-        ("height", profile.height, height),
astrid/packs/rendering/backends/ffmpeg/support.py-531-        ("fps", profile.fps_rational, (fps, 1)),
astrid/packs/rendering/backends/ffmpeg/support.py:532:        ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
astrid/packs/rendering/backends/ffmpeg/support.py-533-        ("container", profile.container, "mp4"),
astrid/packs/rendering/backends/ffmpeg/support.py-534-        ("video_codec", profile.video_codec, "h264"),
astrid/packs/rendering/backends/ffmpeg/support.py-535-        ("pixel_format", profile.pixel_format, "yuv420p"),
astrid/packs/rendering/backends/ffmpeg/support.py-536-    )
astrid/packs/rendering/backends/ffmpeg/support.py-537-    for field, requested, produced in checks:
astrid/packs/rendering/backends/ffmpeg/support.py-538-        if requested is None:
astrid/packs/rendering/backends/ffmpeg/support.py-539-            continue
astrid/packs/rendering/backends/ffmpeg/support.py:540:        if field in ("fps", "time_base"):
astrid/packs/rendering/backends/ffmpeg/support.py-541-            equal = _rational_equal(requested, produced)
astrid/packs/rendering/backends/ffmpeg/support.py-542-        else:
astrid/packs/rendering/backends/ffmpeg/support.py-543-            equal = requested == produced
astrid/packs/rendering/backends/ffmpeg/support.py-544-        if not equal:
astrid/packs/rendering/backends/ffmpeg/support.py-545-            reasons.append(
astrid/packs/rendering/backends/ffmpeg/support.py-546-                f"requested profile {field}={requested!r} is not produced by "
astrid/packs/rendering/backends/ffmpeg/support.py-547-                f"rendering.ffmpeg (produces {produced!r})"
astrid/packs/rendering/backends/ffmpeg/support.py-548-            )
--
astrid/packs/rendering/backends/ffmpeg/support.py-726-                dict(assets),
astrid/packs/rendering/backends/ffmpeg/support.py-727-                assets_path,
astrid/packs/rendering/backends/ffmpeg/support.py-728-            )
astrid/packs/rendering/backends/ffmpeg/support.py-729-        except Exception as exc:
astrid/packs/rendering/backends/ffmpeg/support.py-730-            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
astrid/packs/rendering/backends/ffmpeg/support.py-731-        else:
astrid/packs/rendering/backends/ffmpeg/support.py-732-            specialization = spec is not None
astrid/packs/rendering/backends/ffmpeg/support.py-733-
astrid/packs/rendering/backends/ffmpeg/support.py:734:    whole_media = not reactive and _whole_media_optimization(
astrid/packs/rendering/backends/ffmpeg/support.py-735-        timeline_data,
astrid/packs/rendering/backends/ffmpeg/support.py-736-        assets,
astrid/packs/rendering/backends/ffmpeg/support.py-737-        probes,
astrid/packs/rendering/backends/ffmpeg/support.py-738-    )
astrid/packs/rendering/backends/ffmpeg/support.py-739-    features: dict[str, bool | str] = {
astrid/packs/rendering/backends/ffmpeg/support.py-740-        "media_only": not specialization,
astrid/packs/rendering/backends/ffmpeg/support.py-741-        "full_timeline": True,
astrid/packs/rendering/backends/ffmpeg/support.py-742-        "windows": False,
astrid/packs/rendering/backends/ffmpeg/support.py-743-        "sequential_audio": True,
astrid/packs/rendering/backends/ffmpeg/support.py-744-        "audio_reactive_colour": specialization,
astrid/packs/rendering/backends/ffmpeg/support.py-745-        "whole_media": whole_media,
astrid/packs/rendering/backends/ffmpeg/support.py-746-        "whole_media_optimization": whole_media,
astrid/packs/rendering/backends/ffmpeg/support.py:747:        "stream_copy": whole_media,
astrid/packs/rendering/backends/ffmpeg/support.py-748-        "audio_ownership": ownership.value,
astrid/packs/rendering/backends/ffmpeg/support.py-749-    }
astrid/packs/rendering/backends/ffmpeg/support.py-750-    if specialization:
astrid/packs/rendering/backends/ffmpeg/support.py-751-        features["specialization"] = audio_reactive_colour.ADAPTER_ID
astrid/packs/rendering/backends/ffmpeg/support.py-752-
astrid/packs/rendering/backends/ffmpeg/support.py:753:    reasons.extend(_profile_support_reasons(request, timeline_data))
astrid/packs/rendering/backends/ffmpeg/support.py-754-
astrid/packs/rendering/backends/ffmpeg/support.py-755-    reasons = _dedupe(reasons)
astrid/packs/rendering/backends/ffmpeg/support.py-756-    return SupportReport(
astrid/packs/rendering/backends/ffmpeg/support.py-757-        schema_version=SCHEMA_VERSION,
astrid/packs/rendering/backends/ffmpeg/support.py-758-        supported=not reasons,
astrid/packs/rendering/backends/ffmpeg/support.py-759-        reasons=reasons,
astrid/packs/rendering/backends/ffmpeg/support.py-760-        features=features,
astrid/packs/rendering/backends/ffmpeg/support.py-761-        alternatives=list(ALTERNATIVE_BACKENDS) if reasons else [],
--
astrid/packs/rendering/backends/ffmpeg/run.py-40-    RendererException,
astrid/packs/rendering/backends/ffmpeg/run.py-41-    make_renderer_error,
astrid/packs/rendering/backends/ffmpeg/run.py-42-    raise_invalid_artifact_error,
astrid/packs/rendering/backends/ffmpeg/run.py-43-    raise_unsupported_error,
astrid/packs/rendering/backends/ffmpeg/run.py-44-)
astrid/packs/rendering/backends/ffmpeg/run.py-45-from astrid.core.rendering.publication import publish_render_result
astrid/packs/rendering/backends/ffmpeg/run.py-46-from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
astrid/packs/rendering/backends/ffmpeg/run.py-47-from astrid.packs.rendering.backends.ffmpeg.command import (
astrid/packs/rendering/backends/ffmpeg/run.py:48:    build_render_command,
astrid/packs/rendering/backends/ffmpeg/run.py:49:    build_render_command_for_paths,
astrid/packs/rendering/backends/ffmpeg/run.py:50:    build_render_command_from_data,
astrid/packs/rendering/backends/ffmpeg/run.py-51-    validate_ffmpeg_media_timeline,
astrid/packs/rendering/backends/ffmpeg/run.py-52-)
astrid/packs/rendering/backends/ffmpeg/run.py-53-from astrid.packs.rendering.backends.ffmpeg.support import (
astrid/packs/rendering/backends/ffmpeg/run.py-54-    ALTERNATIVE_BACKENDS,
astrid/packs/rendering/backends/ffmpeg/run.py-55-    BACKEND_ID,
astrid/packs/rendering/backends/ffmpeg/run.py-56-    BACKEND_VERSION,
astrid/packs/rendering/backends/ffmpeg/run.py-57-    support as strict_support,
astrid/packs/rendering/backends/ffmpeg/run.py-58-)
--
astrid/packs/rendering/backends/ffmpeg/run.py-107-    report = _support(request, timeline_data, assets_data)
astrid/packs/rendering/backends/ffmpeg/run.py-108-    if not report.supported:
astrid/packs/rendering/backends/ffmpeg/run.py-109-        raise ValueError(
astrid/packs/rendering/backends/ffmpeg/run.py-110-            "FFmpeg media render refused by strict support: "
astrid/packs/rendering/backends/ffmpeg/run.py-111-            + "; ".join(report.reasons)
astrid/packs/rendering/backends/ffmpeg/run.py-112-        )
astrid/packs/rendering/backends/ffmpeg/run.py-113-
astrid/packs/rendering/backends/ffmpeg/run.py-114-    output = Path(out_path)
astrid/packs/rendering/backends/ffmpeg/run.py:115:    command_argv = build_render_command_from_data(
astrid/packs/rendering/backends/ffmpeg/run.py-116-        Path(timeline_path),
astrid/packs/rendering/backends/ffmpeg/run.py-117-        Path(assets_path),
astrid/packs/rendering/backends/ffmpeg/run.py-118-        output,
astrid/packs/rendering/backends/ffmpeg/run.py-119-        timeline_data,
astrid/packs/rendering/backends/ffmpeg/run.py-120-        assets_data,
astrid/packs/rendering/backends/ffmpeg/run.py:121:        stream_copy_allowed=bool(report.features.get("stream_copy")),
astrid/packs/rendering/backends/ffmpeg/run.py-122-    )
astrid/packs/rendering/backends/ffmpeg/run.py-123-    output.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/backends/ffmpeg/run.py-124-    (subprocess.run if runner is None else runner)(command_argv, check=True)
astrid/packs/rendering/backends/ffmpeg/run.py-125-    return output
astrid/packs/rendering/backends/ffmpeg/run.py-126-
astrid/packs/rendering/backends/ffmpeg/run.py-127-
astrid/packs/rendering/backends/ffmpeg/run.py-128-def render(
astrid/packs/rendering/backends/ffmpeg/run.py-129-    timeline_path: Path,
--
astrid/packs/rendering/backends/ffmpeg/run.py-280-        features={
astrid/packs/rendering/backends/ffmpeg/run.py-281-            "media_only": False,
astrid/packs/rendering/backends/ffmpeg/run.py-282-            "full_timeline": True,
astrid/packs/rendering/backends/ffmpeg/run.py-283-            "windows": False,
astrid/packs/rendering/backends/ffmpeg/run.py-284-            "sequential_audio": True,
astrid/packs/rendering/backends/ffmpeg/run.py-285-            "audio_reactive_colour": False,
astrid/packs/rendering/backends/ffmpeg/run.py-286-            "whole_media": False,
astrid/packs/rendering/backends/ffmpeg/run.py-287-            "whole_media_optimization": False,
astrid/packs/rendering/backends/ffmpeg/run.py:288:            "stream_copy": False,
astrid/packs/rendering/backends/ffmpeg/run.py-289-            "audio_ownership": AudioOwnership.NONE.value,
astrid/packs/rendering/backends/ffmpeg/run.py-290-        },
astrid/packs/rendering/backends/ffmpeg/run.py-291-        alternatives=list(ALTERNATIVE_BACKENDS),
astrid/packs/rendering/backends/ffmpeg/run.py-292-        backend=BACKEND_ID,
astrid/packs/rendering/backends/ffmpeg/run.py-293-        backend_version=BACKEND_VERSION,
astrid/packs/rendering/backends/ffmpeg/run.py-294-    )
astrid/packs/rendering/backends/ffmpeg/run.py-295-
astrid/packs/rendering/backends/ffmpeg/run.py-296-
--
astrid/packs/rendering/backends/ffmpeg/run.py-479-    if audio_layout is None and probe.audio_channels == 2:
astrid/packs/rendering/backends/ffmpeg/run.py-480-        audio_layout = "stereo"
astrid/packs/rendering/backends/ffmpeg/run.py-481-    elif audio_layout is None and probe.audio_channels == 1:
astrid/packs/rendering/backends/ffmpeg/run.py-482-        audio_layout = "mono"
astrid/packs/rendering/backends/ffmpeg/run.py-483-    return RenderProfile(
astrid/packs/rendering/backends/ffmpeg/run.py-484-        width=_required(probe.width, "video width"),
astrid/packs/rendering/backends/ffmpeg/run.py-485-        height=_required(probe.height, "video height"),
astrid/packs/rendering/backends/ffmpeg/run.py-486-        fps_rational=_required(probe.fps_rational, "video frame rate"),
astrid/packs/rendering/backends/ffmpeg/run.py:487:        time_base=_required(probe.time_base, "video time base"),
astrid/packs/rendering/backends/ffmpeg/run.py-488-        container=_required(probe.container, "container"),
astrid/packs/rendering/backends/ffmpeg/run.py-489-        video_codec=_required(probe.video_codec, "video codec"),
astrid/packs/rendering/backends/ffmpeg/run.py-490-        video_profile=probe.video_profile,
astrid/packs/rendering/backends/ffmpeg/run.py-491-        video_level=probe.video_level,
astrid/packs/rendering/backends/ffmpeg/run.py-492-        pixel_format=_required(probe.pixel_format, "pixel format"),
astrid/packs/rendering/backends/ffmpeg/run.py-493-        audio_codec=(
astrid/packs/rendering/backends/ffmpeg/run.py-494-            _required(probe.audio_codec, "audio codec")
astrid/packs/rendering/backends/ffmpeg/run.py-495-            if ownership is AudioOwnership.RENDERED
--
astrid/packs/rendering/backends/ffmpeg/run.py-556-    outputs_dir = workspace / "outputs"
astrid/packs/rendering/backends/ffmpeg/run.py-557-    output_path = outputs_dir / request.output_name
astrid/packs/rendering/backends/ffmpeg/run.py-558-    outputs_dir.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/backends/ffmpeg/run.py-559-    output_path.unlink(missing_ok=True)
astrid/packs/rendering/backends/ffmpeg/run.py-560-    try:
astrid/packs/rendering/backends/ffmpeg/run.py-561-        if specialization_spec is not None:
astrid/packs/rendering/backends/ffmpeg/run.py-562-            audio_reactive_colour.render(specialization_spec, output_path)
astrid/packs/rendering/backends/ffmpeg/run.py-563-        else:
astrid/packs/rendering/backends/ffmpeg/run.py:564:            subprocess.run(build_render_command(request, workspace), check=True)
astrid/packs/rendering/backends/ffmpeg/run.py-565-        try:
astrid/packs/rendering/backends/ffmpeg/run.py-566-            probe = ffprobe_metadata_strict(output_path)
astrid/packs/rendering/backends/ffmpeg/run.py-567-            probed_profile = _profile_from_probe(probe, ownership)
astrid/packs/rendering/backends/ffmpeg/run.py-568-        except (MediaProbeError, RuntimeError) as exc:
astrid/packs/rendering/backends/ffmpeg/run.py-569-            raise_invalid_artifact_error(
astrid/packs/rendering/backends/ffmpeg/run.py-570-                backend=BACKEND_ID,
astrid/packs/rendering/backends/ffmpeg/run.py-571-                message=f"FFmpeg output could not be validated: {exc}",
astrid/packs/rendering/backends/ffmpeg/run.py-572-                recovery_command=(
--
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-13-capabilities:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-14-  clip_types:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-15-    - media
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-16-  track_types:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-17-    - visual
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-18-    - audio
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-19-  features:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-20-    media_only: true
astrid/packs/rendering/backends/ffmpeg/renderer.yaml:21:    stream_copy: true
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-22-    sequential_audio: true
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-23-  supports_full_timeline: true
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-24-  supports_windows: false
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-25-  output_profiles:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-26-    - video/mp4
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-27-  audio_ownership:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-28-    - rendered
astrid/packs/rendering/backends/ffmpeg/renderer.yaml-29-    - passthrough
--
astrid/packs/rendering/backends/ffmpeg/__init__.py-1-"""FFmpeg implementation of Astrid's rendering protocol v1."""
astrid/packs/rendering/backends/ffmpeg/__init__.py-2-
astrid/packs/rendering/backends/ffmpeg/__init__.py-3-from __future__ import annotations
astrid/packs/rendering/backends/ffmpeg/__init__.py-4-
astrid/packs/rendering/backends/ffmpeg/__init__.py-5-from typing import Any
astrid/packs/rendering/backends/ffmpeg/__init__.py-6-
astrid/packs/rendering/backends/ffmpeg/__init__.py:7:from .command import build_render_command
astrid/packs/rendering/backends/ffmpeg/__init__.py-8-
astrid/packs/rendering/backends/ffmpeg/__init__.py-9-
astrid/packs/rendering/backends/ffmpeg/__init__.py-10-BACKEND_ID = "rendering.ffmpeg"
astrid/packs/rendering/backends/ffmpeg/__init__.py-11-BACKEND_VERSION = "1.0.0"
astrid/packs/rendering/backends/ffmpeg/__init__.py-12-
astrid/packs/rendering/backends/ffmpeg/__init__.py-13-
astrid/packs/rendering/backends/ffmpeg/__init__.py-14-def can_render_with_ffmpeg_media(*args: Any, **kwargs: Any) -> bool:
astrid/packs/rendering/backends/ffmpeg/__init__.py-15-    """Lazily enter the executable backend from the package surface."""
--
astrid/packs/rendering/backends/ffmpeg/__init__.py-32-
astrid/packs/rendering/backends/ffmpeg/__init__.py-33-    from .run import support as implementation
astrid/packs/rendering/backends/ffmpeg/__init__.py-34-
astrid/packs/rendering/backends/ffmpeg/__init__.py-35-    return implementation(*args, **kwargs)
astrid/packs/rendering/backends/ffmpeg/__init__.py-36-
astrid/packs/rendering/backends/ffmpeg/__init__.py-37-__all__ = [
astrid/packs/rendering/backends/ffmpeg/__init__.py-38-    "BACKEND_ID",
astrid/packs/rendering/backends/ffmpeg/__init__.py-39-    "BACKEND_VERSION",
astrid/packs/rendering/backends/ffmpeg/__init__.py:40:    "build_render_command",
astrid/packs/rendering/backends/ffmpeg/__init__.py-41-    "can_render_with_ffmpeg_media",
astrid/packs/rendering/backends/ffmpeg/__init__.py-42-    "render",
astrid/packs/rendering/backends/ffmpeg/__init__.py-43-    "support",
astrid/packs/rendering/backends/ffmpeg/__init__.py-44-]
--
astrid/packs/rendering/backends/ffmpeg/command.py-26-    assets_path: Path
astrid/packs/rendering/backends/ffmpeg/command.py-27-    output_path: Path
astrid/packs/rendering/backends/ffmpeg/command.py-28-    timeline_data: dict[str, Any]
astrid/packs/rendering/backends/ffmpeg/command.py-29-    registry: dict[str, Any]
astrid/packs/rendering/backends/ffmpeg/command.py-30-    audio_sample_rate: int = 48000
astrid/packs/rendering/backends/ffmpeg/command.py-31-    # Probe-derived evidence from strict support: stream-copy is only
astrid/packs/rendering/backends/ffmpeg/command.py-32-    # permitted when the actual media probe confirmed whole-source
astrid/packs/rendering/backends/ffmpeg/command.py-33-    # compatibility (never trust registry metadata alone).
astrid/packs/rendering/backends/ffmpeg/command.py:34:    stream_copy_allowed: bool = False
astrid/packs/rendering/backends/ffmpeg/command.py-35-
astrid/packs/rendering/backends/ffmpeg/command.py-36-
astrid/packs/rendering/backends/ffmpeg/command.py-37-def timeline_canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
astrid/packs/rendering/backends/ffmpeg/command.py-38-    canvas = (
astrid/packs/rendering/backends/ffmpeg/command.py-39-        timeline_data.get("theme_overrides", {})
astrid/packs/rendering/backends/ffmpeg/command.py-40-        .get("visual", {})
astrid/packs/rendering/backends/ffmpeg/command.py-41-        .get("canvas", {})
astrid/packs/rendering/backends/ffmpeg/command.py-42-    )
--
astrid/packs/rendering/backends/ffmpeg/command.py-249-                "cropBottom",
astrid/packs/rendering/backends/ffmpeg/command.py-250-                "cropLeft",
astrid/packs/rendering/backends/ffmpeg/command.py-251-                "cropRight",
astrid/packs/rendering/backends/ffmpeg/command.py-252-                "effects",
astrid/packs/rendering/backends/ffmpeg/command.py-253-                "transition",
astrid/packs/rendering/backends/ffmpeg/command.py-254-            )
astrid/packs/rendering/backends/ffmpeg/command.py-255-        )
astrid/packs/rendering/backends/ffmpeg/command.py-256-        if (
astrid/packs/rendering/backends/ffmpeg/command.py:257:            inputs.stream_copy_allowed
astrid/packs/rendering/backends/ffmpeg/command.py-258-            and at == 0
astrid/packs/rendering/backends/ffmpeg/command.py-259-            and start == 0
astrid/packs/rendering/backends/ffmpeg/command.py-260-            and full_duration
astrid/packs/rendering/backends/ffmpeg/command.py-261-            and same_resolution
astrid/packs/rendering/backends/ffmpeg/command.py-262-            and same_fps
astrid/packs/rendering/backends/ffmpeg/command.py-263-            and no_visual_adjustments
astrid/packs/rendering/backends/ffmpeg/command.py-264-        ):
astrid/packs/rendering/backends/ffmpeg/command.py-265-            copy_video_input = asset_index[asset_key]
--
astrid/packs/rendering/backends/ffmpeg/command.py-397-            )
astrid/packs/rendering/backends/ffmpeg/command.py-398-        asset_path = Path(file_value)
astrid/packs/rendering/backends/ffmpeg/command.py-399-        if not asset_path.is_absolute():
astrid/packs/rendering/backends/ffmpeg/command.py-400-            asset_path = (inputs.assets_path.parent / asset_path).resolve()
astrid/packs/rendering/backends/ffmpeg/command.py-401-        argv.extend(["-i", str(asset_path)])
astrid/packs/rendering/backends/ffmpeg/command.py-402-    return argv
astrid/packs/rendering/backends/ffmpeg/command.py-403-
astrid/packs/rendering/backends/ffmpeg/command.py-404-
astrid/packs/rendering/backends/ffmpeg/command.py:405:def build_render_command_from_inputs(inputs: RenderCommandInputs) -> list[str]:
astrid/packs/rendering/backends/ffmpeg/command.py-406-    """Return FFmpeg argv for already-resolved, strictly supported inputs."""
astrid/packs/rendering/backends/ffmpeg/command.py-407-    filters, copy_video_input = build_filter_graph(inputs)
astrid/packs/rendering/backends/ffmpeg/command.py-408-    has_audio = _has_audio_clips(inputs.timeline_data)
astrid/packs/rendering/backends/ffmpeg/command.py-409-    return [
astrid/packs/rendering/backends/ffmpeg/command.py-410-        "ffmpeg",
astrid/packs/rendering/backends/ffmpeg/command.py-411-        "-hide_banner",
astrid/packs/rendering/backends/ffmpeg/command.py-412-        "-y",
astrid/packs/rendering/backends/ffmpeg/command.py-413-        *_asset_input_argv(inputs),
--
astrid/packs/rendering/backends/ffmpeg/command.py-432-            else ["-an"]
astrid/packs/rendering/backends/ffmpeg/command.py-433-        ),
astrid/packs/rendering/backends/ffmpeg/command.py-434-        "-movflags",
astrid/packs/rendering/backends/ffmpeg/command.py-435-        "+faststart",
astrid/packs/rendering/backends/ffmpeg/command.py-436-        str(inputs.output_path),
astrid/packs/rendering/backends/ffmpeg/command.py-437-    ]
astrid/packs/rendering/backends/ffmpeg/command.py-438-
astrid/packs/rendering/backends/ffmpeg/command.py-439-
astrid/packs/rendering/backends/ffmpeg/command.py:440:def build_render_command(
astrid/packs/rendering/backends/ffmpeg/command.py-441-    request: RenderRequest | Mapping[str, Any],
astrid/packs/rendering/backends/ffmpeg/command.py-442-    workspace: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-443-) -> list[str]:
astrid/packs/rendering/backends/ffmpeg/command.py-444-    """Build FFmpeg argv for ``workspace/outputs/<request.output_name>``.
astrid/packs/rendering/backends/ffmpeg/command.py-445-
astrid/packs/rendering/backends/ffmpeg/command.py-446-    Stream-copy is permitted only when strict support's probe evidence says
astrid/packs/rendering/backends/ffmpeg/command.py-447-    the whole source is compatible (never trust registry metadata alone).
astrid/packs/rendering/backends/ffmpeg/command.py-448-    """
--
astrid/packs/rendering/backends/ffmpeg/command.py-456-            if isinstance(request, RenderRequest)
astrid/packs/rendering/backends/ffmpeg/command.py-457-            else RenderRequest.from_dict(request)
astrid/packs/rendering/backends/ffmpeg/command.py-458-        )
astrid/packs/rendering/backends/ffmpeg/command.py-459-        report = support(
astrid/packs/rendering/backends/ffmpeg/command.py-460-            normalized_request,
astrid/packs/rendering/backends/ffmpeg/command.py-461-            inputs.timeline_data,
astrid/packs/rendering/backends/ffmpeg/command.py-462-            inputs.registry,
astrid/packs/rendering/backends/ffmpeg/command.py-463-        )
astrid/packs/rendering/backends/ffmpeg/command.py:464:        stream_copy_allowed = (
astrid/packs/rendering/backends/ffmpeg/command.py:465:            report.supported and bool(report.features.get("stream_copy"))
astrid/packs/rendering/backends/ffmpeg/command.py-466-        )
astrid/packs/rendering/backends/ffmpeg/command.py-467-    except Exception:
astrid/packs/rendering/backends/ffmpeg/command.py:468:        stream_copy_allowed = False
astrid/packs/rendering/backends/ffmpeg/command.py:469:    inputs = replace(inputs, stream_copy_allowed=stream_copy_allowed)
astrid/packs/rendering/backends/ffmpeg/command.py:470:    return build_render_command_from_inputs(inputs)
astrid/packs/rendering/backends/ffmpeg/command.py-471-
astrid/packs/rendering/backends/ffmpeg/command.py-472-
astrid/packs/rendering/backends/ffmpeg/command.py:473:def build_render_command_from_data(
astrid/packs/rendering/backends/ffmpeg/command.py-474-    timeline_path: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-475-    assets_path: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-476-    output_path: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-477-    timeline_data: Mapping[str, Any],
astrid/packs/rendering/backends/ffmpeg/command.py-478-    registry: Mapping[str, Any],
astrid/packs/rendering/backends/ffmpeg/command.py-479-    *,
astrid/packs/rendering/backends/ffmpeg/command.py-480-    audio_sample_rate: int = 48000,
astrid/packs/rendering/backends/ffmpeg/command.py:481:    stream_copy_allowed: bool = False,
astrid/packs/rendering/backends/ffmpeg/command.py-482-) -> list[str]:
astrid/packs/rendering/backends/ffmpeg/command.py-483-    """Build FFmpeg argv from ALREADY-LOADED, strictly supported data.
astrid/packs/rendering/backends/ffmpeg/command.py-484-
astrid/packs/rendering/backends/ffmpeg/command.py-485-    Used by the legacy facade path so the exact mappings it validated with
astrid/packs/rendering/backends/ffmpeg/command.py-486-    strict support are the ones rendered — no reload, no TOCTOU window.
astrid/packs/rendering/backends/ffmpeg/command.py-487-    """
astrid/packs/rendering/backends/ffmpeg/command.py:488:    return build_render_command_from_inputs(
astrid/packs/rendering/backends/ffmpeg/command.py-489-        RenderCommandInputs(
astrid/packs/rendering/backends/ffmpeg/command.py-490-            timeline_path=Path(timeline_path).resolve(),
astrid/packs/rendering/backends/ffmpeg/command.py-491-            assets_path=Path(assets_path).resolve(),
astrid/packs/rendering/backends/ffmpeg/command.py-492-            output_path=Path(output_path).resolve(),
astrid/packs/rendering/backends/ffmpeg/command.py-493-            timeline_data=dict(timeline_data),
astrid/packs/rendering/backends/ffmpeg/command.py-494-            registry=dict(registry),
astrid/packs/rendering/backends/ffmpeg/command.py-495-            audio_sample_rate=audio_sample_rate,
astrid/packs/rendering/backends/ffmpeg/command.py:496:            stream_copy_allowed=stream_copy_allowed,
astrid/packs/rendering/backends/ffmpeg/command.py-497-        )
astrid/packs/rendering/backends/ffmpeg/command.py-498-    )
astrid/packs/rendering/backends/ffmpeg/command.py-499-
astrid/packs/rendering/backends/ffmpeg/command.py-500-
astrid/packs/rendering/backends/ffmpeg/command.py:501:def build_render_command_for_paths(
astrid/packs/rendering/backends/ffmpeg/command.py-502-    timeline_path: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-503-    assets_path: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-504-    output_path: Path,
astrid/packs/rendering/backends/ffmpeg/command.py-505-) -> list[str]:
astrid/packs/rendering/backends/ffmpeg/command.py-506-    """Compatibility builder for the legacy facade's explicit output path."""
astrid/packs/rendering/backends/ffmpeg/command.py-507-
astrid/packs/rendering/backends/ffmpeg/command.py:508:    return build_render_command_from_inputs(
astrid/packs/rendering/backends/ffmpeg/command.py-509-        _command_inputs_for_paths(timeline_path, assets_path, output_path)
astrid/packs/rendering/backends/ffmpeg/command.py-510-    )
astrid/packs/rendering/backends/ffmpeg/command.py-511-
astrid/packs/rendering/backends/ffmpeg/command.py-512-
astrid/packs/rendering/backends/ffmpeg/command.py-513-__all__ = [
astrid/packs/rendering/backends/ffmpeg/command.py-514-    "RenderCommandInputs",
astrid/packs/rendering/backends/ffmpeg/command.py-515-    "build_filter_graph",
astrid/packs/rendering/backends/ffmpeg/command.py:516:    "build_render_command",
astrid/packs/rendering/backends/ffmpeg/command.py:517:    "build_render_command_for_paths",
astrid/packs/rendering/backends/ffmpeg/command.py:518:    "build_render_command_from_inputs",
astrid/packs/rendering/backends/ffmpeg/command.py-519-    "clip_duration_seconds",
astrid/packs/rendering/backends/ffmpeg/command.py-520-    "resolve_render_command_inputs",
astrid/packs/rendering/backends/ffmpeg/command.py-521-    "timeline_canvas",
astrid/packs/rendering/backends/ffmpeg/command.py-522-    "validate_ffmpeg_media_timeline",
astrid/packs/rendering/backends/ffmpeg/command.py-523-]

exec
/bin/zsh -lc "rg -n -C 12 'enforce-audio-track|execute_remotion_locked|remotion.*render|--codec|--audio-codec' astrid/packs/rendering/backends/remotion/run.py remotion package.json pyproject.toml" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/remotion/run.py-266-def _write_registry_state(project_dir: Path, state: dict[str, Any]) -> None:
astrid/packs/rendering/backends/remotion/run.py-267-    state_path = project_dir / _REGISTRY_STATE_PATH
astrid/packs/rendering/backends/remotion/run.py-268-    state_path.write_text(
astrid/packs/rendering/backends/remotion/run.py-269-        json.dumps(state, sort_keys=True, indent=2) + "\n",
astrid/packs/rendering/backends/remotion/run.py-270-        encoding="utf-8",
astrid/packs/rendering/backends/remotion/run.py-271-    )
astrid/packs/rendering/backends/remotion/run.py-272-
astrid/packs/rendering/backends/remotion/run.py-273-
astrid/packs/rendering/backends/remotion/run.py-274-def _regenerate_element_registries(
astrid/packs/rendering/backends/remotion/run.py-275-    project_dir: Path,
astrid/packs/rendering/backends/remotion/run.py-276-    theme_path: Path | None,
astrid/packs/rendering/backends/remotion/run.py-277-) -> None:
astrid/packs/rendering/backends/remotion/run.py:278:    if remotion_lock.remotion_render_lock_held():
astrid/packs/rendering/backends/remotion/run.py-279-        _regenerate_element_registries_locked(project_dir, theme_path)
astrid/packs/rendering/backends/remotion/run.py-280-        return
astrid/packs/rendering/backends/remotion/run.py:281:    with remotion_lock.remotion_render_lock():
astrid/packs/rendering/backends/remotion/run.py-282-        _regenerate_element_registries_locked(project_dir, theme_path)
astrid/packs/rendering/backends/remotion/run.py-283-
astrid/packs/rendering/backends/remotion/run.py-284-
astrid/packs/rendering/backends/remotion/run.py-285-def _regenerate_element_registries_locked(
astrid/packs/rendering/backends/remotion/run.py-286-    project_dir: Path,
astrid/packs/rendering/backends/remotion/run.py-287-    theme_path: Path | None,
astrid/packs/rendering/backends/remotion/run.py-288-) -> None:
astrid/packs/rendering/backends/remotion/run.py-289-    """Regenerate shared registries while the caller owns the Remotion lock."""
astrid/packs/rendering/backends/remotion/run.py-290-
astrid/packs/rendering/backends/remotion/run.py-291-    state = _effective_registry_state(theme_path)
astrid/packs/rendering/backends/remotion/run.py-292-    cached_state = _read_registry_state(project_dir)
astrid/packs/rendering/backends/remotion/run.py-293-    if (
--
astrid/packs/rendering/backends/remotion/run.py-297-        and _active_theme_pointer_current(theme_path)
astrid/packs/rendering/backends/remotion/run.py-298-    ):
astrid/packs/rendering/backends/remotion/run.py-299-        return
astrid/packs/rendering/backends/remotion/run.py-300-
astrid/packs/rendering/backends/remotion/run.py-301-    generator = REPO_ROOT / "scripts" / "gen_effect_registry.py"
astrid/packs/rendering/backends/remotion/run.py-302-    cmd = [sys.executable, str(generator)]
astrid/packs/rendering/backends/remotion/run.py-303-    if theme_path is not None:
astrid/packs/rendering/backends/remotion/run.py-304-        cmd.extend(["--theme", str(_resolve_theme_path(theme_path))])
astrid/packs/rendering/backends/remotion/run.py-305-    env: dict[str, str] = {}
astrid/packs/rendering/backends/remotion/run.py-306-    composition_src = _timeline_composition_src(project_dir)
astrid/packs/rendering/backends/remotion/run.py-307-    if composition_src is not None:
astrid/packs/rendering/backends/remotion/run.py-308-        env["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(composition_src)
astrid/packs/rendering/backends/remotion/run.py:309:    env.update(remotion_lock.remotion_render_lock_child_env())
astrid/packs/rendering/backends/remotion/run.py-310-    subprocess.run(
astrid/packs/rendering/backends/remotion/run.py-311-        cmd,
astrid/packs/rendering/backends/remotion/run.py-312-        cwd=str(REPO_ROOT),
astrid/packs/rendering/backends/remotion/run.py-313-        env=build_child_subprocess_env(explicit_env=env),
astrid/packs/rendering/backends/remotion/run.py-314-        capture_output=True,
astrid/packs/rendering/backends/remotion/run.py-315-        check=True,
astrid/packs/rendering/backends/remotion/run.py-316-        text=True,
astrid/packs/rendering/backends/remotion/run.py-317-    )
astrid/packs/rendering/backends/remotion/run.py-318-    _write_registry_state(project_dir, state)
astrid/packs/rendering/backends/remotion/run.py-319-
astrid/packs/rendering/backends/remotion/run.py-320-
astrid/packs/rendering/backends/remotion/run.py-321-def _render_asset_stage_hash(
--
astrid/packs/rendering/backends/remotion/run.py-601-    timeline_path: Path,
astrid/packs/rendering/backends/remotion/run.py-602-    assets_path: Path,
astrid/packs/rendering/backends/remotion/run.py-603-    staged_video: Path,
astrid/packs/rendering/backends/remotion/run.py-604-    *,
astrid/packs/rendering/backends/remotion/run.py-605-    provenance_out_path: Path,
astrid/packs/rendering/backends/remotion/run.py-606-    project_dir: Path,
astrid/packs/rendering/backends/remotion/run.py-607-    composition_id: str,
astrid/packs/rendering/backends/remotion/run.py-608-    theme_path: Path | None,
astrid/packs/rendering/backends/remotion/run.py-609-    min_free_gb: float | None,
astrid/packs/rendering/backends/remotion/run.py-610-) -> _ExecutionDetails:
astrid/packs/rendering/backends/remotion/run.py-611-    """Render one private video and return the data needed for provenance."""
astrid/packs/rendering/backends/remotion/run.py-612-
astrid/packs/rendering/backends/remotion/run.py:613:    with remotion_lock.remotion_render_lock():
astrid/packs/rendering/backends/remotion/run.py:614:        return _execute_remotion_locked(
astrid/packs/rendering/backends/remotion/run.py-615-            timeline_path,
astrid/packs/rendering/backends/remotion/run.py-616-            assets_path,
astrid/packs/rendering/backends/remotion/run.py-617-            staged_video,
astrid/packs/rendering/backends/remotion/run.py-618-            provenance_out_path=provenance_out_path,
astrid/packs/rendering/backends/remotion/run.py-619-            project_dir=project_dir,
astrid/packs/rendering/backends/remotion/run.py-620-            composition_id=composition_id,
astrid/packs/rendering/backends/remotion/run.py-621-            theme_path=theme_path,
astrid/packs/rendering/backends/remotion/run.py-622-            min_free_gb=min_free_gb,
astrid/packs/rendering/backends/remotion/run.py-623-        )
astrid/packs/rendering/backends/remotion/run.py-624-
astrid/packs/rendering/backends/remotion/run.py-625-
astrid/packs/rendering/backends/remotion/run.py:626:def _execute_remotion_locked(
astrid/packs/rendering/backends/remotion/run.py-627-    timeline_path: Path,
astrid/packs/rendering/backends/remotion/run.py-628-    assets_path: Path,
astrid/packs/rendering/backends/remotion/run.py-629-    staged_video: Path,
astrid/packs/rendering/backends/remotion/run.py-630-    *,
astrid/packs/rendering/backends/remotion/run.py-631-    provenance_out_path: Path,
astrid/packs/rendering/backends/remotion/run.py-632-    project_dir: Path,
astrid/packs/rendering/backends/remotion/run.py-633-    composition_id: str,
astrid/packs/rendering/backends/remotion/run.py-634-    theme_path: Path | None,
astrid/packs/rendering/backends/remotion/run.py-635-    min_free_gb: float | None,
astrid/packs/rendering/backends/remotion/run.py-636-) -> _ExecutionDetails:
astrid/packs/rendering/backends/remotion/run.py-637-    """Execute one render while the caller owns the non-recursive outer lock."""
astrid/packs/rendering/backends/remotion/run.py-638-
--
astrid/packs/rendering/backends/remotion/run.py-691-                )
astrid/packs/rendering/backends/remotion/run.py-692-            completed = subprocess.run(
astrid/packs/rendering/backends/remotion/run.py-693-                [
astrid/packs/rendering/backends/remotion/run.py-694-                    "npx",
astrid/packs/rendering/backends/remotion/run.py-695-                    "remotion",
astrid/packs/rendering/backends/remotion/run.py-696-                    "render",
astrid/packs/rendering/backends/remotion/run.py-697-                    composition_id,
astrid/packs/rendering/backends/remotion/run.py-698-                    "--props",
astrid/packs/rendering/backends/remotion/run.py-699-                    str(props_path),
astrid/packs/rendering/backends/remotion/run.py-700-                    "--output",
astrid/packs/rendering/backends/remotion/run.py-701-                    str(staged_video),
astrid/packs/rendering/backends/remotion/run.py-702-                    "--allow-html-in-canvas",
astrid/packs/rendering/backends/remotion/run.py:703:                    "--enforce-audio-track",
astrid/packs/rendering/backends/remotion/run.py-704-                ],
astrid/packs/rendering/backends/remotion/run.py-705-                cwd=str(project_dir),
astrid/packs/rendering/backends/remotion/run.py-706-                env=build_child_subprocess_env(explicit_env=remotion_env_additions),
astrid/packs/rendering/backends/remotion/run.py-707-                capture_output=True,
astrid/packs/rendering/backends/remotion/run.py-708-                check=False,
astrid/packs/rendering/backends/remotion/run.py-709-                text=True,
astrid/packs/rendering/backends/remotion/run.py-710-            )
astrid/packs/rendering/backends/remotion/run.py-711-            if completed.returncode != 0:
astrid/packs/rendering/backends/remotion/run.py-712-                stderr_tail = _stderr_tail(completed.stderr)
astrid/packs/rendering/backends/remotion/run.py-713-                message = f"Remotion render failed with exit code {completed.returncode}"
astrid/packs/rendering/backends/remotion/run.py-714-                if stderr_tail:
astrid/packs/rendering/backends/remotion/run.py-715-                    message = f"{message}\n{stderr_tail}"
--
remotion/package.json-1-{
remotion/package.json-2-  "name": "tools-remotion",
remotion/package.json-3-  "private": true,
remotion/package.json-4-  "type": "module",
remotion/package.json-5-  "scripts": {
remotion/package.json-6-    "typecheck": "tsc --noEmit",
remotion/package.json-7-    "bundle": "remotion bundle src/index.ts",
remotion/package.json:8:    "render": "remotion render",
remotion/package.json-9-    "smoke": "node __smoke__/bundle.mjs",
remotion/package.json-10-    "gen-types": "python3 ../scripts/gen_remotion_types.py --include-element-registries"
remotion/package.json-11-  },
remotion/package.json-12-  "dependencies": {
remotion/package.json-13-    "@banodoco/timeline-composition": "https://github.com/banodoco/timeline-composition/archive/refs/tags/v0.0.6.tar.gz",
remotion/package.json-14-    "@banodoco/timeline-theme-2rp": "https://github.com/banodoco/timeline-theme-2rp/archive/refs/tags/v0.1.1.tar.gz",
remotion/package.json-15-    "@remotion/cli": "4.0.455",
remotion/package.json-16-    "@remotion/google-fonts": "4.0.455",
remotion/package.json-17-    "@remotion/layout-utils": "4.0.455",
remotion/package.json-18-    "@remotion/media": "4.0.455",
remotion/package.json:19:    "@remotion/renderer": "4.0.455",
remotion/package.json-20-    "react": "^18.3.1",
remotion/package.json-21-    "react-dom": "^18.3.1",
remotion/package.json-22-    "remotion": "4.0.455"
remotion/package.json-23-  },
remotion/package.json-24-  "devDependencies": {
remotion/package.json-25-    "@remotion/bundler": "4.0.455",
remotion/package.json-26-    "@types/node": "^25.6.0",
remotion/package.json-27-    "@types/react": "^19.2.14",
remotion/package.json-28-    "@types/react-dom": "^19.2.3",
remotion/package.json-29-    "typescript": "^5.8.3"
remotion/package.json-30-  }
remotion/package.json-31-}
--
remotion/__smoke__/bundle.mjs-1-import {mkdtemp, readFile, rm, writeFile} from 'node:fs/promises';
remotion/__smoke__/bundle.mjs-2-import os from 'node:os';
remotion/__smoke__/bundle.mjs-3-import path from 'node:path';
remotion/__smoke__/bundle.mjs-4-import {fileURLToPath, pathToFileURL} from 'node:url';
remotion/__smoke__/bundle.mjs-5-
remotion/__smoke__/bundle.mjs-6-import {bundle} from '@remotion/bundler';
remotion/__smoke__/bundle.mjs:7:import {selectComposition} from '@remotion/renderer';
remotion/__smoke__/bundle.mjs-8-import {applyWorkspaceEffectsAlias} from '../webpack-alias.mjs';
remotion/__smoke__/bundle.mjs-9-import ts from 'typescript';
remotion/__smoke__/bundle.mjs-10-
remotion/__smoke__/bundle.mjs-11-const __filename = fileURLToPath(import.meta.url);
remotion/__smoke__/bundle.mjs-12-const __dirname = path.dirname(__filename);
remotion/__smoke__/bundle.mjs-13-const projectDir = path.resolve(__dirname, '..');
remotion/__smoke__/bundle.mjs-14-const repoDir = path.resolve(projectDir, '..');
remotion/__smoke__/bundle.mjs-15-const entryPoint = path.resolve(projectDir, 'src/index.ts');
remotion/__smoke__/bundle.mjs-16-const typesGeneratedPath = path.resolve(projectDir, 'src/types.generated.ts');
remotion/__smoke__/bundle.mjs-17-// Sprint 5 rename: HypeComposition → TimelineComposition.
remotion/__smoke__/bundle.mjs-18-const compositionId = 'TimelineComposition';
remotion/__smoke__/bundle.mjs-19-
--
remotion/package-lock.json-3-  "lockfileVersion": 3,
remotion/package-lock.json-4-  "requires": true,
remotion/package-lock.json-5-  "packages": {
remotion/package-lock.json-6-    "": {
remotion/package-lock.json-7-      "name": "tools-remotion",
remotion/package-lock.json-8-      "dependencies": {
remotion/package-lock.json-9-        "@banodoco/timeline-composition": "https://github.com/banodoco/timeline-composition/archive/refs/tags/v0.0.6.tar.gz",
remotion/package-lock.json-10-        "@banodoco/timeline-theme-2rp": "https://github.com/banodoco/timeline-theme-2rp/archive/refs/tags/v0.1.1.tar.gz",
remotion/package-lock.json-11-        "@remotion/cli": "4.0.455",
remotion/package-lock.json-12-        "@remotion/google-fonts": "4.0.455",
remotion/package-lock.json-13-        "@remotion/layout-utils": "4.0.455",
remotion/package-lock.json-14-        "@remotion/media": "4.0.455",
remotion/package-lock.json:15:        "@remotion/renderer": "4.0.455",
remotion/package-lock.json-16-        "react": "^18.3.1",
remotion/package-lock.json-17-        "react-dom": "^18.3.1",
remotion/package-lock.json-18-        "remotion": "4.0.455"
remotion/package-lock.json-19-      },
remotion/package-lock.json-20-      "devDependencies": {
remotion/package-lock.json-21-        "@remotion/bundler": "4.0.455",
remotion/package-lock.json-22-        "@types/node": "^25.6.0",
remotion/package-lock.json-23-        "@types/react": "^19.2.14",
remotion/package-lock.json-24-        "@types/react-dom": "^19.2.3",
remotion/package-lock.json-25-        "typescript": "^5.8.3"
remotion/package-lock.json-26-      }
remotion/package-lock.json-27-    },
--
remotion/package-lock.json-722-        "react-dom": ">=16.8.0"
remotion/package-lock.json-723-      }
remotion/package-lock.json-724-    },
remotion/package-lock.json-725-    "node_modules/@remotion/cli": {
remotion/package-lock.json-726-      "version": "4.0.455",
remotion/package-lock.json-727-      "resolved": "https://registry.npmjs.org/@remotion/cli/-/cli-4.0.455.tgz",
remotion/package-lock.json-728-      "integrity": "sha512-FzqtL3QPnvQC3dX0AEGqllV5qSGIc8fxIqToUk8vDKbhDZshhgXOUW+LAyiXZTY8JiuBFE6KO8YrjhJkjbGtrw==",
remotion/package-lock.json-729-      "license": "SEE LICENSE IN LICENSE.md",
remotion/package-lock.json-730-      "dependencies": {
remotion/package-lock.json-731-        "@remotion/bundler": "4.0.455",
remotion/package-lock.json-732-        "@remotion/media-utils": "4.0.455",
remotion/package-lock.json-733-        "@remotion/player": "4.0.455",
remotion/package-lock.json:734:        "@remotion/renderer": "4.0.455",
remotion/package-lock.json-735-        "@remotion/studio": "4.0.455",
remotion/package-lock.json-736-        "@remotion/studio-server": "4.0.455",
remotion/package-lock.json-737-        "@remotion/studio-shared": "4.0.455",
remotion/package-lock.json-738-        "dotenv": "17.3.1",
remotion/package-lock.json-739-        "minimist": "1.2.6",
remotion/package-lock.json-740-        "prompts": "2.4.2",
remotion/package-lock.json-741-        "remotion": "4.0.455"
remotion/package-lock.json-742-      },
remotion/package-lock.json-743-      "bin": {
remotion/package-lock.json-744-        "remotion": "remotion-cli.js",
remotion/package-lock.json-745-        "remotionb": "remotionb-cli.js",
remotion/package-lock.json-746-        "remotiond": "remotiond-cli.js"
--
remotion/package-lock.json-893-      "version": "4.0.455",
remotion/package-lock.json-894-      "resolved": "https://registry.npmjs.org/@remotion/player/-/player-4.0.455.tgz",
remotion/package-lock.json-895-      "integrity": "sha512-87iynJ2qddMc80D1kUQsqzQcCFl9iy30ox+VqeHY0T4T14c1azQ6umB0TlLziIj5Em6MT/EX3Fp4Vsr5RjuLSQ==",
remotion/package-lock.json-896-      "license": "SEE LICENSE IN LICENSE.md",
remotion/package-lock.json-897-      "dependencies": {
remotion/package-lock.json-898-        "remotion": "4.0.455"
remotion/package-lock.json-899-      },
remotion/package-lock.json-900-      "peerDependencies": {
remotion/package-lock.json-901-        "react": ">=16.8.0",
remotion/package-lock.json-902-        "react-dom": ">=16.8.0"
remotion/package-lock.json-903-      }
remotion/package-lock.json-904-    },
remotion/package-lock.json:905:    "node_modules/@remotion/renderer": {
remotion/package-lock.json-906-      "version": "4.0.455",
remotion/package-lock.json:907:      "resolved": "https://registry.npmjs.org/@remotion/renderer/-/renderer-4.0.455.tgz",
remotion/package-lock.json-908-      "integrity": "sha512-6UE01Dhu3AEl+cvA09QGarHEQUOc7KRO7wN7vRupODU/JjBcWj3h/oPBDkOY7dLbhiMHsP+i2yT8ENJJaEntzA==",
remotion/package-lock.json-909-      "license": "SEE LICENSE IN LICENSE.md",
remotion/package-lock.json-910-      "dependencies": {
remotion/package-lock.json-911-        "@remotion/licensing": "4.0.455",
remotion/package-lock.json-912-        "@remotion/streaming": "4.0.455",
remotion/package-lock.json-913-        "execa": "5.1.1",
remotion/package-lock.json-914-        "extract-zip": "2.0.1",
remotion/package-lock.json-915-        "remotion": "4.0.455",
remotion/package-lock.json-916-        "source-map": "^0.8.0-beta.0",
remotion/package-lock.json-917-        "ws": "8.17.1"
remotion/package-lock.json-918-      },
remotion/package-lock.json-919-      "optionalDependencies": {
--
remotion/package-lock.json-921-        "@remotion/compositor-darwin-x64": "4.0.455",
remotion/package-lock.json-922-        "@remotion/compositor-linux-arm64-gnu": "4.0.455",
remotion/package-lock.json-923-        "@remotion/compositor-linux-arm64-musl": "4.0.455",
remotion/package-lock.json-924-        "@remotion/compositor-linux-x64-gnu": "4.0.455",
remotion/package-lock.json-925-        "@remotion/compositor-linux-x64-musl": "4.0.455",
remotion/package-lock.json-926-        "@remotion/compositor-win32-x64-msvc": "4.0.455"
remotion/package-lock.json-927-      },
remotion/package-lock.json-928-      "peerDependencies": {
remotion/package-lock.json-929-        "react": ">=16.8.0",
remotion/package-lock.json-930-        "react-dom": ">=16.8.0"
remotion/package-lock.json-931-      }
remotion/package-lock.json-932-    },
remotion/package-lock.json:933:    "node_modules/@remotion/renderer/node_modules/source-map": {
remotion/package-lock.json-934-      "version": "0.8.0-beta.0",
remotion/package-lock.json-935-      "resolved": "https://registry.npmjs.org/source-map/-/source-map-0.8.0-beta.0.tgz",
remotion/package-lock.json-936-      "integrity": "sha512-2ymg6oRBpebeZi9UUNsgQ89bhx01TcTkmNTGnNO88imTmbSgy4nfujrgVEFKWpMTEGA11EDkTt7mqObTPdigIA==",
remotion/package-lock.json-937-      "deprecated": "The work that was done in this beta branch won't be included in future versions",
remotion/package-lock.json-938-      "license": "BSD-3-Clause",
remotion/package-lock.json-939-      "dependencies": {
remotion/package-lock.json-940-        "whatwg-url": "^7.0.0"
remotion/package-lock.json-941-      },
remotion/package-lock.json-942-      "engines": {
remotion/package-lock.json-943-        "node": ">= 8"
remotion/package-lock.json-944-      }
remotion/package-lock.json-945-    },
--
remotion/package-lock.json-948-      "resolved": "https://registry.npmjs.org/@remotion/streaming/-/streaming-4.0.455.tgz",
remotion/package-lock.json-949-      "integrity": "sha512-KiFV14nJd2REbLp6eJCxrdT7Cv4uaMWw22LjP+pUcS1LEVpORpFCAIVdfIUARml27vLEzeVNrP6LrH/msEmdBA==",
remotion/package-lock.json-950-      "license": "MIT"
remotion/package-lock.json-951-    },
remotion/package-lock.json-952-    "node_modules/@remotion/studio": {
remotion/package-lock.json-953-      "version": "4.0.455",
remotion/package-lock.json-954-      "resolved": "https://registry.npmjs.org/@remotion/studio/-/studio-4.0.455.tgz",
remotion/package-lock.json-955-      "integrity": "sha512-goYOHDZDcn1reOmFCWTzXbYp+okwo8AVLFxKvtr+5Z3II2esZCud9WCrXi10xSEY0mePT/VHkIj81EF2Zhgu6Q==",
remotion/package-lock.json-956-      "license": "MIT",
remotion/package-lock.json-957-      "dependencies": {
remotion/package-lock.json-958-        "@remotion/media-utils": "4.0.455",
remotion/package-lock.json-959-        "@remotion/player": "4.0.455",
remotion/package-lock.json:960:        "@remotion/renderer": "4.0.455",
remotion/package-lock.json-961-        "@remotion/studio-shared": "4.0.455",
remotion/package-lock.json:962:        "@remotion/web-renderer": "4.0.455",
remotion/package-lock.json-963-        "@remotion/zod-types": "4.0.455",
remotion/package-lock.json-964-        "mediabunny": "1.42.0",
remotion/package-lock.json-965-        "memfs": "3.4.3",
remotion/package-lock.json-966-        "open": "^8.4.2",
remotion/package-lock.json-967-        "remotion": "4.0.455",
remotion/package-lock.json-968-        "semver": "7.5.3",
remotion/package-lock.json-969-        "source-map": "0.7.3",
remotion/package-lock.json-970-        "zod": "4.3.6"
remotion/package-lock.json-971-      },
remotion/package-lock.json-972-      "peerDependencies": {
remotion/package-lock.json-973-        "react": ">=16.8.0",
remotion/package-lock.json-974-        "react-dom": ">=16.8.0"
remotion/package-lock.json-975-      }
remotion/package-lock.json-976-    },
remotion/package-lock.json-977-    "node_modules/@remotion/studio-server": {
remotion/package-lock.json-978-      "version": "4.0.455",
remotion/package-lock.json-979-      "resolved": "https://registry.npmjs.org/@remotion/studio-server/-/studio-server-4.0.455.tgz",
remotion/package-lock.json-980-      "integrity": "sha512-BXlUxtSqE3jTRyWONnHn2gKIprECGIPLwWNdOr6FIWScM9d2jg/bRDPv1xIsIW/Ok1BlU/lVvNXC+sCkJV9XnQ==",
remotion/package-lock.json-981-      "license": "MIT",
remotion/package-lock.json-982-      "dependencies": {
remotion/package-lock.json-983-        "@babel/parser": "7.24.1",
remotion/package-lock.json-984-        "@babel/types": "7.24.0",
remotion/package-lock.json-985-        "@remotion/bundler": "4.0.455",
remotion/package-lock.json:986:        "@remotion/renderer": "4.0.455",
remotion/package-lock.json-987-        "@remotion/studio-shared": "4.0.455",
remotion/package-lock.json-988-        "memfs": "3.4.3",
remotion/package-lock.json-989-        "open": "^8.4.2",
remotion/package-lock.json-990-        "prettier": "3.8.1",
remotion/package-lock.json-991-        "recast": "0.23.11",
remotion/package-lock.json-992-        "remotion": "4.0.455",
remotion/package-lock.json-993-        "semver": "7.5.3",
remotion/package-lock.json-994-        "source-map": "0.7.3"
remotion/package-lock.json-995-      }
remotion/package-lock.json-996-    },
remotion/package-lock.json-997-    "node_modules/@remotion/studio-shared": {
remotion/package-lock.json-998-      "version": "4.0.455",
remotion/package-lock.json-999-      "resolved": "https://registry.npmjs.org/@remotion/studio-shared/-/studio-shared-4.0.455.tgz",
remotion/package-lock.json-1000-      "integrity": "sha512-ZwRLlfPucYKhi1/AKOIaglDELqQCll/lcem/9pMoovIz9QXWOscKgkPcC5s20a6fy3DBzzmNBZ5gryC3Td9bCQ==",
remotion/package-lock.json-1001-      "license": "MIT",
remotion/package-lock.json-1002-      "dependencies": {
remotion/package-lock.json-1003-        "remotion": "4.0.455"
remotion/package-lock.json-1004-      }
remotion/package-lock.json-1005-    },
remotion/package-lock.json:1006:    "node_modules/@remotion/web-renderer": {
remotion/package-lock.json-1007-      "version": "4.0.455",
remotion/package-lock.json:1008:      "resolved": "https://registry.npmjs.org/@remotion/web-renderer/-/web-renderer-4.0.455.tgz",
remotion/package-lock.json-1009-      "integrity": "sha512-RHFPXqH7ZvG1IzWn97sq8oPR7+TAorTNDI1eKzqY+Ljwu3tFz/aCE2SCxU9irIbDqUKPNSihsP+qBMOOvWs+Ow==",
remotion/package-lock.json-1010-      "license": "UNLICENSED",
remotion/package-lock.json-1011-      "dependencies": {
remotion/package-lock.json-1012-        "@mediabunny/aac-encoder": "1.42.0",
remotion/package-lock.json-1013-        "@mediabunny/flac-encoder": "1.42.0",
remotion/package-lock.json-1014-        "@mediabunny/mp3-encoder": "1.42.0",
remotion/package-lock.json-1015-        "@remotion/licensing": "4.0.455",
remotion/package-lock.json-1016-        "mediabunny": "1.42.0",
remotion/package-lock.json-1017-        "remotion": "4.0.455"
remotion/package-lock.json-1018-      },
remotion/package-lock.json-1019-      "peerDependencies": {
remotion/package-lock.json-1020-        "react": ">=18.0.0",

exec
/bin/zsh -lc 'for f in .oracle/checkins/batch-3.md .oracle/checkins/batch-3-r1.md .oracle/checkins/batch-3-r2.md; do echo FILE:$f; rg -n '"'"'^([0-9]+'"\\.|[-*] \\*\\*|PASS"'$|## Verdict|### Verdict|Issue|issue)'"' \""'$f" | tail -n 80; echo TAIL; tail -n 80 "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
FILE:.oracle/checkins/batch-3.md
404:- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
405:- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
406:- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
407:- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
408:- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
409:- **Already have the answer?** → don't dispatch. Subagents aren't free.
415:1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
416:2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
417:3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
418:4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.
443:- **`--model`** (default `deepseek:deepseek-v4-pro`). Prefix convention from the megaplan key pool:
449:- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
450:- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
451:- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
452:- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
453:- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
454:- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
455:- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.
495:- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).
570:- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
571:- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
572:- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
573:- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.
6178:## Verdict
6203:1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
6204:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
6205:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
6206:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
6207:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
6208:6. Open it and sync.
6249:1. A tasklist covering the **entirety** of the project (not just the obvious path).
6250:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
6251:3. Open questions / potential issues.
6287:- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
6288:- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
6289:- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
6290:- **Per-batch acceptance criteria** the oracle will verify.
6328:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
6329:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
6330:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
6334:- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
6335:- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
8434:1. Create `astrid/packs/rendering/backends/remotion/`:
8448:2. Register in `astrid/packs/rendering/pack.yaml`:
8450:3. Keep `astrid/packs/rendering/executors/render/run.py` a thin facade that
8455:4. Relocate private-helper tests: move Remotion-specific tests from
8460:5. Preserve: `TimelineComposition` usage, merged themes, props,
8492:1. Create `astrid/packs/rendering/finalizers/ffmpeg/`:
8509:2. Register in `astrid/packs/rendering/pack.yaml`
8511:3. Keep the facade's hybrid concat working via the finalizer module.
8512:4. Add `tests/packs/rendering/test_ffmpeg_finalizer.py`:
17691:1. **Track-level `muted` is real; clip-level mute does not exist.** `TrackDefinition` has `volume: float, muted: bool` (`banodoco_schema.py:163-169`); `_TRACK_ALLOWED` includes `muted` (`:349`). Clip `_CLIP_ALLOWED` has `volume` but no `muted` (`:340-348`) — clip mute is expressed as `volume: 0`. Precedence documented in `SKILL.md:667`: "track and clip volume multiply. `track.muted: true` forces silence regardless."
17693:2. **Fades are free-form clip params, not schema fields.** `params.fadeIn/fadeOut` in seconds (`SKILL.md:668`); `TimelineEffect.fade_in/fade_out` (`banodoco_schema.py:123-125`) is visual text-card, not audio.
17695:3. **FFmpeg validator (`run.py:491-515`) checks only:** exactly one visual track (`:495`), media-only clips (`:498`), speed==1 (`:500`), visual clips `volume==0` (`:503`), non-overlapping audio clips (`:510-514`). It **never inspects `track.muted`, `track.volume`, or fades**.
17697:4. **FFmpeg renderer (`run.py:600-626`) honors only clip `volume`** (`:612,:617` volume filter) and `from/to` trim (`:610-615`). Track volume/muted are **silently ignored**; fades are accidentally routed to Remotion via `has_audio_fade` complex windows (`:715-717`). No `afade`/`amix` anywhere.
17699:5. **AudioTrack.tsx is not vendored** — @banodoco packages are GitHub-tarball adapter installs (`run.py:297-300`, `:905-907`); `remotion/src` has no audio code. Local evidence is SKILL.md:668 only.
17701:6. **Zero test coverage.** `tests/packs/rendering/*` grep for muted/volume/fade/overlap: 0 hits. `audio_reactive_colour.py:230-251` rejects fades/effects/overlaps/negative volume (only audio assertions in repo).
17770:1. `astrid/packs/rendering/backends/remotion/lock.py`:
17776:2. Route `_regenerate_element_registries` (or its extracted equivalent) and
17778:3. Update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`,
17782:4. Add `tests/packs/rendering/test_remotion_locking.py`:
17789:5. Keep `tests/packs/rendering/test_render_remotion_registry.py` passing.
24699:Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):
24701:1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.
24703:2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.
24705:3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.
24707:4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.
24709:5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.
24711:6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.
24713:7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.
24715:8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
24718:Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):
24720:1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.
24722:2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.
24724:3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.
24726:4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.
24728:5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.
24730:6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.
24732:7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.
24734:8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
TAIL
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
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
   156	- [ ] **M1-05 — Extract and register `rendering.remotion`**
   157	
   158	  - Move theme resolution, timeline serialization, project checks, element-registry generation, effect staging, props creation, Remotion subprocess handling, and backend provenance into `astrid/packs/rendering/backends/remotion/`.
   159	  - Register it through `extensions.rendering` and a static renderer manifest using the raw command protocol.
   160	  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
   161	  - Put props and asset staging under the unique invocation workdir.
   162	  - Introduce one outer cross-process lock for generated Remotion sources:
   163	    - acquire it before reading registry state or checking generated outputs;
   164	    - cover the three package registries, shim families, active-theme symlink/text pointer, and registry state;
   165	    - hold it through active-theme selection and the complete Remotion render;
   166	    - write registry state atomically;
   167	    - make the developer `gen-types` path acquire the same outer lock across `types.generated.ts` and effect-registry generation;
   168	    - ensure generator primitives do not recursively acquire the lock.
   169	  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
   170	  - Move private-helper tests to extracted boundaries while keeping a small facade compatibility suite.
   171	  - Gate: registry invalidation, atomic state, theme/profile parity, effect assets, environment redaction, concurrent differing-theme renders, render-versus-`gen-types` contention, success/failure cleanup, output validation, Remotion typecheck, and an available fixture render pass.
   172	
   173	- [ ] **M1-06 — Extract and register `rendering.ffmpeg`**

codex
Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):

1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.

2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.

3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.

4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.

5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.

6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.

7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.

8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
tokens used
494,207
Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):

1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.

2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.

3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.

4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.

5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.

6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.

7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.

8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
FILE:.oracle/checkins/batch-3-r1.md
2109:- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.
2285:1. Record observations and evidence-backed inferences locally.
2286:2. Search Hivemind for an existing equivalent learning.
2287:3. Contribute a concise experiment report as a resource.
2288:4. Submit the reusable learning as a distillation citing that resource.
2289:5. Preserve the returned Hivemind IDs beside the local experiment.
2400:1. **Search and compose existing executors first.** If existing executors can
2402:2. **Create missing executors next.** Each new executor does one concrete,
2404:3. **Then write the orchestrator.** It composes existing and newly created
2406:4. **Add elements only for reusable render building blocks.** Effects,
2545:- **Aliases** — Map old or alternate ids to current capabilities. Declared in
2547:- **Forks** — Copy a capability into a local pack for independent editing.
2554:- **Overrides** — Redirect a capability id to a preferred fork without
2580:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
2581:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
2582:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
2908:1. Drop your source `.mp4` into `runs/<name>/`.
2909:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
2910:3. Render with the command above.
2911:4. ffprobe / open the `composed.mp4`.
2912:5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
2977:- **Default — an independent DeepSeek/Kimi subagent that reads the repo itself?** → §1 (`launch_hermes_agent.py --toolsets="file,web"`). Need many at once (≥ ~5 parallel)? Same pathway, `fan.py`.
2978:- **Pure chat opinion, no tools?** → §1 with `--toolsets=""`.
2979:- **Most-different-from-Claude judgement, or write-heavy implementation in a sandbox?** → §2 Codex.
2980:- **Same-*family* judgement but isolated from this thread, with explicit Opus/Sonnet selection?** → §3 Claude CLI launcher. If the host exposes the Claude Code `Agent` tool and model selection is not required, that is also fine.
2981:- **Jury for a high-stakes call?** → fan the same prompt to Codex + hermes-DeepSeek + hermes-Kimi in parallel; divergence is the signal.
2982:- **Bigger than ~a day or two of work?** → it's a *deliverable*, not a dispatch: run a `megaplan` (itself launched as a subagent) and size it with the **`megaplan-decision`** skill. Past ~2 weeks → an epic.
2983:- **Already have the answer?** → don't dispatch. Subagents aren't free.
2989:1. **MiMo V2.5 Pro Ultraspeed** (`fast`, alias for `mimo:mimo-v2.5-pro-ultraspeed`) — very fast. High-volume, low-judgement work: scan files, extract facts, short first-pass research.
2990:2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`) — non-reasoning, fast, cheap. High-volume work that needs more coding-tuned behavior than MiMo.
2991:3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`, the default) — reasoning model. When the task needs judgement: root-cause analysis, "is this sound", "should this merge".
2992:4. **GPT-5.5 (Codex) or Claude** — only for *real* complexity: subtle multi-step reasoning, write-heavy implementation, the strongest adversarial review.
3017:- **`--model`** (default `deepseek:deepseek-v4-pro`). Prefix convention from the megaplan key pool:
3023:- **`--toolsets`** (default `"file,web"`): `file` (`read_file`/`write_file`/`patch`/`search_files`), `web` (`fetch_url`), `terminal` (shell — **no sandbox**, runs as you; never for untrusted prompts). `""` = pure chat.
3024:- **Note:** in the standalone `launch_hermes_agent.py` entrypoint, the `file` toolset is only available when `terminal` is also enabled, because file operations are routed through the terminal environment. If the agent emits tool-call markup but does not actually read files (or claims it has no filesystem access), pass `--toolsets="file,web,terminal"`.
3025:- **`--query` / `--query-file`** — pass exactly one; use `--query-file` for anything past a sentence.
3026:- **`--max-tokens`** (default 65536 — model output ceiling for DeepSeek V4). **In normal use, do not pass this flag.** The launcher already defaults to the model's ceiling, so adding it yourself just creates copy-paste noise and makes it easy to accidentally inflate the cap for no benefit. These are reasoning models; reasoning tokens are billed and counted against `max_tokens`, so a brief that fires 20+ tool calls can burn the entire budget on reasoning before emitting a single output token — the result is an empty answer (`finish_reason: length`) with the tool history visible in stderr. The built-in ceiling protects against that silent failure. **Only pass `--max-tokens` when you specifically want a shorter cap** because you have already scoped the brief to ≤5 tool calls and want to bound cost/output length. Other ceilings: Kimi K2.7 ~32768, Zhipu GLM-5.2 / GLM-4.6 ~32768, DeepSeek Flash 8192 (non-reasoning, doesn't burn budget on thinking so 8K is fine).
3027:- **`--project-dir`** — chdir so the `file` tool resolves relative paths as you expect.
3028:- **Runtime discovery** — set `ARNOLD_PATH=/path/to/Arnold` only for nonstandard checkouts. Normal shells should not need manual `PYTHONPATH`.
3029:- **`--context-budget-tokens`** — raise the auto-compaction floor when a broad file audit on a long-context model compacts too early, e.g. `--context-budget-tokens=100000`.
3069:- **Always seal stdin with `</dev/null`.** Otherwise `codex exec` blocks forever at `Reading additional input from stdin...` (0% CPU, no error) even when the prompt is in argv. That banner prints on healthy runs too — the wedge signal is the output file *not growing*. Wrap long runs in `timeout 1800` (30 min — review and write-heavy briefs routinely run 15+ min; 600s is too tight).
3144:- **Codex** — see the `</dev/null` wedge above; the tell is an output file stuck at the banner size while wall-clock climbs.
3145:- **Hermes / fan.py** — `--max-tokens` too low → empty answer (`finish_reason: length`); else watch the stderr `[tool]`/`[done]` heartbeat.
3146:- **Claude Agent / launcher** — synchronous, rarely wedges; the common failure is a terse prompt → shallow hedged answer in < 30 s. Cap length and demand a position.
3147:- **megaplan** — an "stuck" run is usually a gated step awaiting approval; `megaplan status --plan <name>`.
3311:## Verdict
3336:1. In a worktree, Codex (GPT-5.6 Sol, max reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
3337:2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
3338:3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
3339:4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at max reasoning produces this structure.
3340:5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
3341:6. Open it and sync.
3382:1. A tasklist covering the **entirety** of the project (not just the obvious path).
3383:2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
3384:3. Open questions / potential issues.
3420:- **Sensible batches** — ordered so each batch is self-contained and ends at a natural seam.
3421:- **Checkpoints** — one per batch: send completed work since the last check-in for feedback; flag implementation issues. At each formal check-in, rework what was just implemented until happy.
3422:- **`[HARD]` tags** on the extremely hard tasks (subtle multi-step reasoning, write-heavy, cross-cutting) — these go to GPT-5.6 Sol, not DeepSeek Flash.
3423:- **Per-batch acceptance criteria** the oracle will verify.
3461:1. End-to-end verification: run the project / full suite; confirm the whole thing executes.
3462:2. Commit and sync: `git add -A && git commit -m "megado: <project>" && git push` (merge back to main if that's the sync target).
3463:3. `open` the worktree / project for the user, and report phase-by-phase evidence.
3467:- **Seal Codex stdin** with `</dev/null` — otherwise `codex exec` blocks at "Reading additional input from stdin..." with 0% CPU. The tell is an output file stuck at the banner size. Allow 30 min (`timeout 1800`) for write-heavy/review runs.
3468:- **Hermes agents need outbound network.** Never launch DeepSeek from inside a `codex exec` subagent unless it runs `--sandbox danger-full-access`. Orchestrate from the host, not from Codex.
3469:- **Match brief shape to model mode.** Flash handed an architectural brief "executes fragments without understanding the intent"; give it mechanical, per-batch briefs derived straight from the tasklist. Judgement (exploration, revision, oracle) stays at GPT-5.6 Sol; escalate Flash exploration to DeepSeek V4 Pro only on evidence.
3470:- **Liveness ≠ correctness.** Watch `fan.py` `.meta.json` files and the stderr `[tool]`/`[done]` heartbeat; check 30–60 s after launch, not 10 minutes in. But a live agent can still answer uselessly — read the response.
3471:- **Checkpoint discipline is the whole game.** The oracle gate is what makes quality; skipping it to "save a cycle" collapses this into a plain DeepSeek run.
3472:- **Elegance bias is a real instruction.** Codex's revision prompt must name it; otherwise reasoning models add scope, not subtract it.
20968:1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)
20970:2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)
20972:3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)
20974:4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)
20976:5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)
20978:6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
20981:1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)
20983:2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)
20985:3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)
20987:4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)
20989:5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)
20991:6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
TAIL
   348	                )
   349	            elif bounds.at < cursor - _TIMELINE_EPSILON_SECONDS:
   350	                reasons.append(
   351	                    f"Visual overlap at clip {clip_id!r}: starts at {bounds.at:.6f}, previous visual ends at {cursor:.6f}"
   352	                )
   353	            cursor = max(cursor, bounds.end)
   354	
   355	        audio_ranges.sort(key=lambda item: item.at)
   356	        audio_cursor = 0.0
   357	        for bounds in audio_ranges:
   358	            clip_id = bounds.clip.get("id")
   359	            if bounds.at < audio_cursor - _TIMELINE_EPSILON_SECONDS:
   360	                reasons.append(
   361	                    f"Overlapping audio at clip {clip_id!r}: starts at {bounds.at:.6f}, previous audio ends at {audio_cursor:.6f}"
   362	                )
   363	            if bounds.end > cursor + _TIMELINE_EPSILON_SECONDS:
   364	                reasons.append(
   365	                    f"Audio clip {clip_id!r} ends outside the visual frame bounds"
   366	                )
   367	            audio_cursor = max(audio_cursor, bounds.end)
   368	    return _dedupe(reasons)
   369	
   370	
   371	def _dedupe(reasons: list[str]) -> list[str]:
   372	    return list(dict.fromkeys(reason for reason in reasons if reason))
   373	
   374	
   375	def _assets_table(assets: Mapping[str, Any]) -> Mapping[str, Any] | None:
   376	    value = assets.get("assets")
   377	    return value if isinstance(value, Mapping) else None
   378	
   379	
   380	def _registry_path(request: RenderRequest) -> Path:
   381	    if request.assets_registry_path is None:
   382	        return Path.cwd() / "assets.json"
   383	    return Path(request.assets_registry_path).expanduser().resolve()
   384	
   385	
   386	def _asset_path(
   387	    entry: Mapping[str, Any],
   388	    *,
   389	    asset_id: str,
   390	    assets_path: Path,
   391	) -> Path:
   392	    if _nonempty(entry.get("url")):
   393	        raise ValueError(
   394	            f"Asset {asset_id!r} is remote; rendering.ffmpeg requires a local source file"
   395	        )
   396	    file_value = entry.get("file")
   397	    if not isinstance(file_value, str) or not file_value:
   398	        raise ValueError(f"Asset {asset_id!r} has no local source file")
   399	    path = Path(file_value).expanduser()
   400	    if not path.is_absolute():

context compacted
codex
1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)

2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)

4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)

5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)

6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
tokens used
461,027
1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)

2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)

4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)

5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)

6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
FILE:.oracle/checkins/batch-3-r2.md
8570:1. **Search and compose existing executors first.** If existing executors can
8572:2. **Create missing executors next.** Each new executor does one concrete,
8574:3. **Then write the orchestrator.** It composes existing and newly created
8576:4. **Add elements only for reusable render building blocks.** Effects,
8715:- **Aliases** — Map old or alternate ids to current capabilities. Declared in
8717:- **Forks** — Copy a capability into a local pack for independent editing.
8720:- **Overrides** — Redirect a capability id to a preferred fork without
8746:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
8747:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
8748:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
9070:1. Drop your source `.mp4` into `runs/<name>/`.
9071:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
9072:3. Render with the command above.
9073:4. ffprobe / open the `composed.mp4`.
9074:5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
9235:1. Record observations and evidence-backed inferences locally.
9236:2. Search Hivemind for an existing equivalent learning.
9237:3. Contribute a concise experiment report as a resource.
9238:4. Submit the reusable learning as a distillation citing that resource.
9239:5. Preserve the returned Hivemind IDs beside the local experiment.
9346:1. **Search and compose existing executors first.** If existing executors can
9348:2. **Create missing executors next.** Each new executor does one concrete,
9350:3. **Then write the orchestrator.** It composes existing and newly created
9352:4. **Add elements only for reusable render building blocks.** Effects,
9491:- **Aliases** — Map old or alternate ids to current capabilities. Declared in
9493:- **Forks** — Copy a capability into a local pack for independent editing.
9496:- **Overrides** — Redirect a capability id to a preferred fork without
9522:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
9523:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
9524:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
9846:1. Drop your source `.mp4` into `runs/<name>/`.
9847:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
9848:3. Render with the command above.
9849:4. ffprobe / open the `composed.mp4`.
9850:5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
10022:1. Drop your source `.mp4` into `runs/<name>/`.
10023:2. Copy the JSON snippets above into `runs/<name>/{timeline,assets}.json`. Adjust `at`, `hold`, `text.content`, and `params.anchor`; add a new track when the new clip is a new concern, not just another caption.
10024:3. Render with the command above.
10025:4. ffprobe / open the `composed.mp4`.
10026:5. If captions don't appear after editing the local-pack component, blow away `remotion/node_modules/.cache` — Remotion's webpack caches aggressively across renders.
10098:1. **Search and compose existing executors first.** If existing executors can
10100:2. **Create missing executors next.** Each new executor does one concrete,
10102:3. **Then write the orchestrator.** It composes existing and newly created
10104:4. **Add elements only for reusable render building blocks.** Effects,
10243:- **Aliases** — Map old or alternate ids to current capabilities. Declared in
10245:- **Forks** — Copy a capability into a local pack for independent editing.
10256:- **Overrides** — Redirect a capability id to a preferred fork without
10282:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
10283:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
10284:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
10597:1. Record observations and evidence-backed inferences locally.
10598:2. Search Hivemind for an existing equivalent learning.
10599:3. Contribute a concise experiment report as a resource.
10600:4. Submit the reusable learning as a distillation citing that resource.
10601:5. Preserve the returned Hivemind IDs beside the local experiment.
10671:- **Overrides** — Redirect a capability id to a preferred fork without
10697:- **Read on attach.** After `astrid attach <project>`, read `<project>/plan.md` alongside `project.json` as part of orienting. New projects ship with an empty skeleton; that's fine.
10698:- **Update when project-level state changes.** A new focus, a closed thread, a settled decision, a fresh open question. Don't log ephemeral per-run state — that belongs in `events.jsonl` and step produces.
10699:- **Refactor when it grows tangled.** If `plan.md` becomes overly long, repetitive, or contradictory, rewrite it: promote stale items to a `## Archive` section or remove them, keep `## Current focus` short, and trim `## Open threads` if it grows past ~10 entries. Treat it as a living doc, not an append-only log. The signal: finding the relevant section takes more than a glance.
10900:1. **Input**: `hype.timeline.json` (clip sequence, effects, animations,
10903:2. **HTTP server start**: Before launching Remotion, the executor starts a
10907:3. **Composition**: Remotion renders the timeline using the resolved theme
10909:4. **Output**: `hype.mp4` and `hype.mp4.provenance.json`.
10922:- **Handler**: `_RangeHTTPRequestHandler` (extends `SimpleHTTPRequestHandler`)
10923:- **Range request support**: Implements HTTP `Range` (byte-range) headers
10929:- **CORS**: Responds with `Access-Control-Allow-Origin: *` and allows
10931:- **Lifecycle**: Started as a daemon thread before Remotion and shut down
10933:- **Port**: Auto-picked via `_pick_free_port()` (binds to `127.0.0.1:0`
11081:- **Remotion** (`npx remotion render`) — must be installed in the `remotion/` project directory
11082:- **Node.js / npm** — `npm install` must have been run in the Remotion project
11083:- **ffmpeg/ffprobe** — required by Remotion's render pipeline and `sprite_sheet` frame extraction
14338:4.0.455
14381:1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)
14383:2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)
14385:3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)
14387:4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)
14390:1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)
14392:2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)
14394:3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)
14396:4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)
TAIL
   176	    return fps
   177	
   178	
   179	def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
   180	    """Mirror FFmpeg's MP4 video-track timescale selection.
   181	
   182	    Integer rates are repeatedly doubled until the timescale is at least
   183	    10,000 (24 -> 12,288; 30 -> 15,360).  NTSC-style rationals already carry
   184	    a large numerator (30000/1001 -> 30,000).
   185	    """
   186	
   187	    timescale = fps.numerator
   188	    while timescale < 10_000:
   189	        timescale *= 2
   190	    return 1, timescale
   191	
   192	

exec
/bin/zsh -lc "node -p \"require('./remotion/node_modules/@remotion/renderer/package.json').version\"; nl -ba remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js | sed -n '5,18p'; nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '560,585p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
4.0.455
     5	const DEFAULT_ENFORCE_AUDIO_TRACK = false;
     6	let enforceAudioTrackState = DEFAULT_ENFORCE_AUDIO_TRACK;
     7	const cliFlag = 'enforce-audio-track';
     8	exports.enforceAudioOption = {
     9	    name: 'Enforce Audio Track',
    10	    cliFlag,
    11	    description: () => (jsx_runtime_1.jsx(jsx_runtime_1.Fragment, { children: "Render a silent audio track if there would be none otherwise." })),
    12	    ssrName: 'enforceAudioTrack',
    13	    docLink: 'https://www.remotion.dev/docs/config#setenforceaudiotrack-',
    14	    type: false,
    15	    getValue: ({ commandLine }) => {
    16	        if (commandLine[cliFlag]) {
    17	            return {
    18	                source: 'cli',
   560	    try:
   561	        if specialization_spec is not None:
   562	            audio_reactive_colour.render(specialization_spec, output_path)
   563	        else:
   564	            subprocess.run(build_render_command(request, workspace), check=True)
   565	        try:
   566	            probe = ffprobe_metadata_strict(output_path)
   567	            probed_profile = _profile_from_probe(probe, ownership)
   568	        except (MediaProbeError, RuntimeError) as exc:
   569	            raise_invalid_artifact_error(
   570	                backend=BACKEND_ID,
   571	                message=f"FFmpeg output could not be validated: {exc}",
   572	                recovery_command=(
   573	                    "rerun rendering.ffmpeg in a fresh invocation workspace"
   574	                ),
   575	                details={"error_type": type(exc).__name__},
   576	            )
   577	        declared_profile = request.profile or probed_profile
   578	        duration_frames = _duration_frames(probe, declared_profile)
   579	        provenance_v1 = remotion_backend._render_provenance_payload(
   580	            output_path,
   581	            engine="ffmpeg",
   582	            timeline_path=timeline_path,
   583	            assets_path=assets_path,
   584	            project_dir=REPO_ROOT / "remotion",
   585	            composition_id="TimelineComposition",

codex
1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)

3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)

4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)
tokens used
450,040
1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)

3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)

4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)

exec
/bin/zsh -lc "sed -n '50,72p' .oracle/tasklist.md
for f in .oracle/checkins/batch-3.md .oracle/checkins/batch-3-r1.md .oracle/checkins/batch-3-r2.md; do echo \"FILE:"'$f LINES:$(wc -l < "$f")"; tail -n 45 "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 281ms:
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

FILE:.oracle/checkins/batch-3.md LINES:   24734
   167	    - make the developer `gen-types` path acquire the same outer lock across `types.generated.ts` and effect-registry generation;
   168	    - ensure generator primitives do not recursively acquire the lock.
   169	  - Use the invocation-scoped asset server and reject exit-zero/no-output or empty-output cases before provenance.
   170	  - Move private-helper tests to extracted boundaries while keeping a small facade compatibility suite.
   171	  - Gate: registry invalidation, atomic state, theme/profile parity, effect assets, environment redaction, concurrent differing-theme renders, render-versus-`gen-types` contention, success/failure cleanup, output validation, Remotion typecheck, and an available fixture render pass.
   172	
   173	- [ ] **M1-06 — Extract and register `rendering.ffmpeg`**

codex
Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):

1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.

2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.

3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.

4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.

5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.

6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.

7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.

8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
tokens used
494,207
Issues in committed C3 (`0c2733ed`; later uncommitted changes excluded):

1. `astrid/packs/rendering/run.py:30-106` cannot identify the selected implementation when the contract-valid `backend_config={}` is supplied. It guesses from timeline shape, so Remotion can execute FFmpeg, FFmpeg can execute Remotion, and finalizer `support` can execute renderer support. The smoke tests mask this by inserting a backend namespace.

2. Remotion support and render contradict each other. `backends/remotion/run.py:1007-1024` validates canonical ownership/time base, but `:1088-1103` silently rewrites them to rendered AAC and `1/90000`, then validates against the rewritten profile at `:1160-1164`. Thus a visual-only `audio=none`, `1/15360` request passes support but returns a different contract. The corrections describe the observed file but are not a sound request-profile implementation.

3. `backends/remotion/renderer.yaml:37-39` omits `ffprobe`, although `_duration_frames()` and artifact validation require it (`run.py:1045-1054,1160-1164`). Preflight/support succeeds without a required runtime binary and fails only after rendering.

4. FFmpeg support checks only requested audio presence (`support.py:418-438`), ignoring the remaining requested profile. The canonical audio profile is 48 kHz, while `command.py:279-326` hard-codes 44.1 kHz. Support therefore reports success for a canonical request that necessarily fails post-render validation. Dimensions, FPS, time base, codecs, and pixel format have the same support gap.

5. FFmpeg’s stream-copy execution ignores its probe-derived support evidence. `support.py:441-492,652-666` can correctly report `stream_copy=false`, but `command.py:215-260` independently trusts registry duration/resolution/FPS and may still copy. Stale metadata can consequently turn a two-second clip into the complete ten-second source.

6. Legacy facade routing no longer preserves behavior for embedded visual audio. `backends/ffmpeg/run.py:171-206` bypasses full support, accepts a visual clip with nonzero effective volume, and `command.py:416-428` emits `-an`. This silently discards requested audio; the pre-extraction facade rejected that case.

7. The finalizer does not normalize audio presence. `finalizers/ffmpeg/run.py:391-470,879-908` requires homogeneous rendered or passthrough ownership and can only map an already-present audio stream. Hybrid forces overall rendered ownership (`executors/render/run.py:337-351`), so an audio-bearing timeline containing a video-only FFmpeg segment fails instead of receiving required presence normalization.

8. Finalizer profile anchoring is codec-unsafe. `finalizers/ffmpeg/run.py:259-286,442-445` can inherit profile/level from an incompatible first segment and pass those values directly to another encoder—for example, HEVC `Main`/`120` normalized to H.264. Existing mocked tests do not execute and re-probe this normalization path.
FILE:.oracle/checkins/batch-3-r1.md LINES:   20991
   383	    return Path(request.assets_registry_path).expanduser().resolve()
   384	
   385	
   386	def _asset_path(
   387	    entry: Mapping[str, Any],
   388	    *,
   389	    asset_id: str,
   390	    assets_path: Path,
   391	) -> Path:
   392	    if _nonempty(entry.get("url")):
   393	        raise ValueError(
   394	            f"Asset {asset_id!r} is remote; rendering.ffmpeg requires a local source file"
   395	        )
   396	    file_value = entry.get("file")
   397	    if not isinstance(file_value, str) or not file_value:
   398	        raise ValueError(f"Asset {asset_id!r} has no local source file")
   399	    path = Path(file_value).expanduser()
   400	    if not path.is_absolute():

context compacted
codex
1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)

2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)

4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)

5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)

6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
tokens used
461,027
1. Launcher routing is still not environment-authoritative. With `ASTRID_RENDER_BACKEND=rendering.remotion`, a request containing a finalizer namespace is routed to the finalizer because `_selects_finalizer()` falls through to `backend_config` before `_selects_ffmpeg()` or Remotion dispatch runs. [rendering/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/run.py:30)

2. Remotion support and render remain inconsistent. Support only forces `time_base=1/90000`, so a visual-only profile with no audio passes; render then silently adds rendered AAC/48k/stereo. Conversely, explicitly requesting that actual rendered profile is rejected by support. The manifest also still advertises `audio_ownership: [rendered, none]`. [remotion/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:1007) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

3. FFmpeg profile validation is not fail-closed for every field: `time_base`, `video_profile`, and `video_level` are not compared. Requests with mismatches in each field still report `supported=True`, then can fail post-render validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:495)

4. The audio-reactive FFmpeg specialization still hard-codes 44.1 kHz while support promises the canonical 48 kHz profile. A supported 48 kHz request therefore produces a 44.1 kHz artifact and fails strict result validation. [audio_reactive_colour.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:345)

5. Stream-copy is not gated by whole-source compatibility. Probe evidence checks duration, dimensions, and FPS, but not source codec, pixel format, profile, or level. A probed HEVC/yuv444p source can be marked copyable for an H.264/yuv420p request and copied unchanged. The builder also consumes `features.stream_copy` without requiring `report.supported`. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:441) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:450)

6. The legacy facade performs strict support on loaded mappings, then the command builder reloads the timeline and assets. A mutation between those reads can bypass the strict refusal and restore the embedded-audio-loss behavior. [ffmpeg/run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:73) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:133)
FILE:.oracle/checkins/batch-3-r2.md LINES:   14396
    18	                source: 'cli',
   560	    try:
   561	        if specialization_spec is not None:
   562	            audio_reactive_colour.render(specialization_spec, output_path)
   563	        else:
   564	            subprocess.run(build_render_command(request, workspace), check=True)
   565	        try:
   566	            probe = ffprobe_metadata_strict(output_path)
   567	            probed_profile = _profile_from_probe(probe, ownership)
   568	        except (MediaProbeError, RuntimeError) as exc:
   569	            raise_invalid_artifact_error(
   570	                backend=BACKEND_ID,
   571	                message=f"FFmpeg output could not be validated: {exc}",
   572	                recovery_command=(
   573	                    "rerun rendering.ffmpeg in a fresh invocation workspace"
   574	                ),
   575	                details={"error_type": type(exc).__name__},
   576	            )
   577	        declared_profile = request.profile or probed_profile
   578	        duration_frames = _duration_frames(probe, declared_profile)
   579	        provenance_v1 = remotion_backend._render_provenance_payload(
   580	            output_path,
   581	            engine="ffmpeg",
   582	            timeline_path=timeline_path,
   583	            assets_path=assets_path,
   584	            project_dir=REPO_ROOT / "remotion",
   585	            composition_id="TimelineComposition",

codex
1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)

3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)

4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)
tokens used
450,040
1. Remotion still does not enforce its always-rendered-audio contract. The command omits `--enforce-audio-track`, whose Remotion 4.0.455 default is false. Visual-only or muted timelines can therefore render without audio despite support and the manifest promising rendered AAC, causing artifact validation to fail. [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/run.py:692) [renderer.yaml](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/remotion/renderer.yaml:31)

2. FFmpeg profile support remains incomplete and incorrect. The `fps * 512` time-base formula diverges from the canonical doubling rule—for example, canonical and real FFmpeg output at 60 fps is `1/15360`, but support requires `1/30720`. Non-integral requested FPS values are silently skipped, equivalent rational time bases are rejected, and `video_profile`/`video_level` remain unchecked despite not being pinned by the command. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:511) [profile.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/profile.py:179)

3. Stream-copy is still not gated on the complete source/request profile. `_whole_media_optimization()` ignores probed time base, video profile, and level. An H.264/yuv420p 30-fps source using `1/90000` is therefore copied for a canonical `1/15360` request; FFmpeg preserves `1/90000`, so support succeeds and post-render validation fails. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:480) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:256)

4. “Whole-source” matching still permits extra frames through a fixed 50 ms duration tolerance. At higher frame rates, several trailing frames can pass the check, after which the copy path maps the entire untrimmed source and derives the declared duration from that oversized output. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:483) [run.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/run.py:577)

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/profile.py | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/media.py | sed -n '1,280p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '420,590p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '180,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '1,250p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 79ms:
     1	"""Canonical render-profile resolution for timeline rendering."""
     2	
     3	from __future__ import annotations
     4	
     5	import json
     6	import math
     7	from collections.abc import Mapping, Sequence
     8	from fractions import Fraction
     9	from pathlib import Path
    10	from typing import Any
    11	
    12	from astrid.core.theme import resolve_themes_root
    13	from astrid.core.timeline import Timeline, resolve_timeline_theme
    14	
    15	from .contracts import AudioOwnership, RenderProfile
    16	
    17	
    18	_DEFAULT_CANVAS = {"width": 1920, "height": 1080, "fps": 30}
    19	_DEFAULT_THEME = "banodoco-default"
    20	
    21	
    22	def _load_mapping(value: Any, *, label: str) -> dict[str, Any]:
    23	    if isinstance(value, Mapping):
    24	        return dict(value)
    25	    if isinstance(value, (str, Path)):
    26	        path = Path(value)
    27	        data = json.loads(path.read_text(encoding="utf-8"))
    28	        if not isinstance(data, dict):
    29	            raise ValueError(f"{label} must contain a JSON object")
    30	        return data
    31	    to_config = getattr(value, "to_config", None)
    32	    if callable(to_config):
    33	        data = to_config()
    34	        if isinstance(data, Mapping):
    35	            return dict(data)
    36	    raise TypeError(f"{label} must be a mapping, JSON path, or Timeline")
    37	
    38	
    39	def _timeline_mapping(value: Any) -> dict[str, Any]:
    40	    if isinstance(value, Timeline):
    41	        return dict(value.to_config())
    42	    return _load_mapping(value, label="timeline")
    43	
    44	
    45	def _asset_mapping(value: Any) -> dict[str, Any] | None:
    46	    if value is None:
    47	        return None
    48	    return _load_mapping(value, label="assets registry")
    49	
    50	
    51	def _deep_merge_theme(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    52	    """Mirror the timeline theme merge used by ``resolve_timeline_theme``."""
    53	
    54	    result: dict[str, Any] = dict(base)
    55	    for key, value in overlay.items():
    56	        existing = result.get(key)
    57	        if isinstance(existing, Mapping) and isinstance(value, Mapping):
    58	            merged_block: dict[str, Any] = dict(existing)
    59	            for sub_key, sub_value in value.items():
    60	                existing_sub = merged_block.get(sub_key)
    61	                if isinstance(existing_sub, Mapping) and isinstance(sub_value, Mapping):
    62	                    inner = dict(existing_sub)
    63	                    inner.update(sub_value)
    64	                    merged_block[sub_key] = inner
    65	                else:
    66	                    merged_block[sub_key] = sub_value
    67	            result[key] = merged_block
    68	        else:
    69	            result[key] = value
    70	    return result
    71	
    72	
    73	def _read_theme_path(path: Path) -> dict[str, Any]:
    74	    theme_path = path / "theme.json" if path.is_dir() else path
    75	    return _load_mapping(theme_path, label="theme")
    76	
    77	
    78	def _resolve_merged_theme(
    79	    timeline: Mapping[str, Any],
    80	    *,
    81	    theme: Mapping[str, Any] | str | Path | None,
    82	    themes_root: str | Path | None,
    83	) -> dict[str, Any]:
    84	    overrides = timeline.get("theme_overrides")
    85	    override_mapping = overrides if isinstance(overrides, Mapping) else {}
    86	
    87	    if isinstance(theme, Mapping):
    88	        return _deep_merge_theme(theme, override_mapping)
    89	
    90	    root = resolve_themes_root(themes_root)
    91	    if theme is not None:
    92	        candidate = Path(theme).expanduser()
    93	        if candidate.exists() or candidate.name == "theme.json":
    94	            return _deep_merge_theme(_read_theme_path(candidate), override_mapping)
    95	        config = dict(timeline)
    96	        config["theme"] = str(theme)
    97	    else:
    98	        config = dict(timeline)
    99	        config.setdefault("theme", _DEFAULT_THEME)
   100	
   101	    try:
   102	        return resolve_timeline_theme(config, root)
   103	    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
   104	        # Remotion falls back to DEFAULT_CANVAS when neither a theme nor a
   105	        # complete override can provide a canvas.  Keeping the empty merged
   106	        # theme here lets the exact getCanvas precedence below do the same.
   107	        return _deep_merge_theme({}, override_mapping)
   108	
   109	
   110	def _remotion_canvas(
   111	    timeline: Mapping[str, Any], merged_theme: Mapping[str, Any]
   112	) -> Mapping[str, Any]:
   113	    """Return the canvas selected by ``remotion/src/Root.tsx::getCanvas``.
   114	
   115	    Root selects the *whole* override canvas before the resolved theme canvas.
   116	    A partial override consequently falls back to Remotion's field defaults,
   117	    not to the missing fields in the base theme.  Mirroring that edge is
   118	    important: this profile is the contract for what Remotion actually emits.
   119	    """
   120	
   121	    overrides = timeline.get("theme_overrides")
   122	    if isinstance(overrides, Mapping):
   123	        visual = overrides.get("visual")
   124	        if isinstance(visual, Mapping) and isinstance(visual.get("canvas"), Mapping):
   125	            return visual["canvas"]
   126	    visual = merged_theme.get("visual")
   127	    if isinstance(visual, Mapping) and isinstance(visual.get("canvas"), Mapping):
   128	        return visual["canvas"]
   129	    return _DEFAULT_CANVAS
   130	
   131	
   132	def _positive_dimension(value: Any, *, default: int, label: str) -> int:
   133	    candidate = default if value is None else value
   134	    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
   135	        raise TypeError(f"canvas {label} must be a positive integer")
   136	    if isinstance(candidate, float) and not candidate.is_integer():
   137	        raise ValueError(f"canvas {label} must be a positive integer")
   138	    result = int(candidate)
   139	    if result <= 0:
   140	        raise ValueError(f"canvas {label} must be a positive integer")
   141	    return result
   142	
   143	
   144	def _fps_fraction(value: Any) -> Fraction:
   145	    if isinstance(value, bool):
   146	        raise TypeError("canvas fps must be a positive number or rational")
   147	    if isinstance(value, str):
   148	        try:
   149	            fps = Fraction(value)
   150	        except (ValueError, ZeroDivisionError) as exc:
   151	            raise ValueError(f"invalid canvas fps {value!r}") from exc
   152	    elif (
   153	        isinstance(value, Sequence)
   154	        and not isinstance(value, (str, bytes))
   155	        and len(value) == 2
   156	    ):
   157	        numerator, denominator = value
   158	        if type(numerator) is not int or type(denominator) is not int:
   159	            raise TypeError("canvas fps rational must contain two integers")
   160	        try:
   161	            fps = Fraction(numerator, denominator)
   162	        except ZeroDivisionError as exc:
   163	            raise ValueError("canvas fps denominator must be positive") from exc
   164	    elif isinstance(value, int):
   165	        fps = Fraction(value, 1)
   166	    elif isinstance(value, float):
   167	        if not math.isfinite(value):
   168	            raise ValueError("canvas fps must be finite")
   169	        # Decimal text is the authored value.  Fraction(float) would preserve
   170	        # the binary approximation and make the wire profile drift.
   171	        fps = Fraction(str(value))
   172	    else:
   173	        raise TypeError("canvas fps must be a positive number or rational")
   174	    if fps <= 0:
   175	        raise ValueError("canvas fps must be positive")
   176	    return fps
   177	
   178	
   179	def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
   180	    """Mirror FFmpeg's MP4 video-track timescale selection.
   181	
   182	    Integer rates are repeatedly doubled until the timescale is at least
   183	    10,000 (24 -> 12,288; 30 -> 15,360).  NTSC-style rationals already carry
   184	    a large numerator (30000/1001 -> 30,000).
   185	    """
   186	
   187	    timescale = fps.numerator
   188	    while timescale < 10_000:
   189	        timescale *= 2
   190	    return 1, timescale
   191	
   192	
   193	def _coerce_audio_ownership(value: AudioOwnership | str | None) -> AudioOwnership | None:
   194	    if value is None or isinstance(value, AudioOwnership):
   195	        return value
   196	    if isinstance(value, str):
   197	        try:
   198	            return AudioOwnership(value)
   199	        except ValueError as exc:
   200	            raise ValueError(
   201	                "audio_ownership must be one of: rendered, passthrough, none"
   202	            ) from exc
   203	    raise TypeError("audio_ownership must be an AudioOwnership value or string")
   204	
   205	
   206	def _has_referenced_audio(
   207	    timeline: Mapping[str, Any], assets: Mapping[str, Any] | None
   208	) -> bool:
   209	    tracks = timeline.get("tracks")
   210	    clips = timeline.get("clips")
   211	    if not isinstance(tracks, list) or not isinstance(clips, list):
   212	        return False
   213	    audio_tracks = {
   214	        track.get("id")
   215	        for track in tracks
   216	        if isinstance(track, Mapping) and track.get("kind") == "audio"
   217	    }
   218	    if not audio_tracks:
   219	        return False
   220	
   221	    registered_assets: Mapping[str, Any] | None = None
   222	    if isinstance(assets, Mapping):
   223	        candidates = assets.get("assets")
   224	        if isinstance(candidates, Mapping):
   225	            registered_assets = candidates
   226	
   227	    for clip in clips:
   228	        if not isinstance(clip, Mapping) or clip.get("track") not in audio_tracks:
   229	            continue
   230	        if clip.get("clipType", "media") != "media":
   231	            continue
   232	        asset_id = clip.get("asset")
   233	        if not isinstance(asset_id, str) or not asset_id:
   234	            continue
   235	        if registered_assets is None or asset_id in registered_assets:
   236	            return True
   237	    return False
   238	
   239	
   240	def resolve_render_profile(
   241	    timeline: Mapping[str, Any] | str | Path | Timeline,
   242	    assets: Mapping[str, Any] | str | Path | None = None,
   243	    *,
   244	    theme: Mapping[str, Any] | str | Path | None = None,
   245	    themes_root: str | Path | None = None,
   246	    audio_ownership: AudioOwnership | str | None = None,
   247	    duration_tolerance: int = 1,
   248	) -> RenderProfile:
   249	    """Resolve the canonical profile shared by planning and finalization.
   250	
   251	    Canvas selection deliberately mirrors Remotion's metadata calculation.
   252	    The encoder target remains backend-neutral but matches Astrid's canonical
   253	    MP4 output: H.264/yuv420p and, when audio is rendered, AAC 48 kHz stereo.
   254	    """
   255	
   256	    timeline_data = _timeline_mapping(timeline)
   257	    assets_data = _asset_mapping(assets)
   258	    merged_theme = _resolve_merged_theme(
   259	        timeline_data,
   260	        theme=theme,

 succeeded in 69ms:
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
    59	    # Appended last so existing positional construction is unaffected.
    60	    audio_channels: int | None = None
    61	
    62	    @property
    63	    def codec(self) -> str | None:
    64	        """Compatibility shorthand for the primary video codec."""
    65	
    66	        return self.video_codec
    67	
    68	    @property
    69	    def duration(self) -> float | None:
    70	        """Compatibility shorthand for :attr:`duration_seconds`."""
    71	
    72	        return self.duration_seconds
    73	
    74	    @property
    75	    def has_video_stream(self) -> bool:
    76	        if self.video_stream_present is not None:
    77	            return self.video_stream_present
    78	        return self.video_codec is not None or (
    79	            self.width is not None and self.height is not None
    80	        )
    81	
    82	    @property
    83	    def has_audio_stream(self) -> bool:
    84	        if self.audio_stream_present is not None:
    85	            return self.audio_stream_present
    86	        return self.audio_codec is not None
    87	
    88	
    89	class MediaProbeError(RuntimeError):
    90	    """Raised when a fail-closed media probe cannot produce metadata."""
    91	
    92	
    93	def _positive_rational(value: Any) -> tuple[int, int] | None:
    94	    """Parse an ffprobe rational without routing through a float."""
    95	
    96	    if not isinstance(value, str) or "/" not in value:
    97	        return None
    98	    numerator_text, denominator_text = value.split("/", 1)
    99	    try:
   100	        numerator = int(numerator_text)
   101	        denominator = int(denominator_text)
   102	    except (TypeError, ValueError):
   103	        return None
   104	    if numerator <= 0 or denominator <= 0:
   105	        return None
   106	    rational = Fraction(numerator, denominator)
   107	    return rational.numerator, rational.denominator
   108	
   109	
   110	def _duration_rational(value: Any) -> tuple[int, int] | None:
   111	    if value is None:
   112	        return None
   113	    try:
   114	        rational = Fraction(str(value))
   115	    except (ValueError, ZeroDivisionError):
   116	        return None
   117	    if rational < 0:
   118	        return None
   119	    return rational.numerator, rational.denominator
   120	
   121	
   122	def _nonempty_string(value: Any) -> str | None:
   123	    if not isinstance(value, str) or not value.strip():
   124	        return None
   125	    return value
   126	
   127	
   128	def _int_or_none(value: Any, *, minimum: int = 0) -> int | None:
   129	    try:
   130	        parsed = int(value)
   131	    except (TypeError, ValueError):
   132	        return None
   133	    return parsed if parsed >= minimum else None
   134	
   135	
   136	def _container_from_format(format_name: str | None, file_path: str | Path) -> str | None:
   137	    if format_name is None:
   138	        return None
   139	    names = {part.strip().lower() for part in format_name.split(",") if part.strip()}
   140	    suffix = Path(file_path).suffix.lower().lstrip(".")
   141	    if suffix in names:
   142	        return suffix
   143	    if "mp4" in names:
   144	        return "mp4"
   145	    if "webm" in names:
   146	        return "webm"
   147	    if "matroska" in names:
   148	        return "matroska"
   149	    if "mov" in names:
   150	        return "mov"
   151	    return sorted(names)[0] if names else None
   152	
   153	
   154	def _parse_ffprobe_payload(data: dict[str, Any], file_path: str | Path) -> MediaProbe:
   155	    probe = MediaProbe(_raw=data)
   156	
   157	    fmt = data.get("format", {})
   158	    if not isinstance(fmt, Mapping):
   159	        fmt = {}
   160	    probe.format_name = _nonempty_string(fmt.get("format_name"))
   161	    probe.container = _container_from_format(probe.format_name, file_path)
   162	
   163	    duration_value = fmt.get("duration")
   164	    probe.duration_rational = _duration_rational(duration_value)
   165	    if probe.duration_rational is not None:
   166	        probe.duration_seconds = float(Fraction(*probe.duration_rational))
   167	
   168	    streams = data.get("streams", [])
   169	    if not isinstance(streams, list):
   170	        streams = []
   171	
   172	    video_stream: Mapping[str, Any] | None = None
   173	    audio_stream: Mapping[str, Any] | None = None
   174	    for stream in streams:
   175	        if not isinstance(stream, Mapping):
   176	            continue
   177	        stream_type = stream.get("codec_type")
   178	        if stream_type == "video" and video_stream is None:
   179	            disposition = stream.get("disposition")
   180	            attached_picture = (
   181	                isinstance(disposition, Mapping)
   182	                and disposition.get("attached_pic") in {1, True, "1"}
   183	            )
   184	            if not attached_picture:
   185	                video_stream = stream
   186	        elif stream_type == "audio" and audio_stream is None:
   187	            audio_stream = stream
   188	
   189	    probe.video_stream_present = video_stream is not None
   190	    probe.audio_stream_present = audio_stream is not None
   191	
   192	    if video_stream is not None:
   193	        probe.width = _int_or_none(video_stream.get("width"), minimum=1)
   194	        probe.height = _int_or_none(video_stream.get("height"), minimum=1)
   195	        if probe.width is not None and probe.height is not None:
   196	            probe.resolution = f"{probe.width}x{probe.height}"
   197	
   198	        fps_value = video_stream.get("avg_frame_rate")
   199	        fps_rational = _positive_rational(fps_value)
   200	        if fps_rational is None:
   201	            fps_rational = _positive_rational(video_stream.get("r_frame_rate"))
   202	        probe.fps_rational = fps_rational
   203	        if fps_rational is not None:
   204	            probe.fps = float(Fraction(*fps_rational))
   205	
   206	        probe.time_base = _positive_rational(video_stream.get("time_base"))
   207	        probe.video_codec = _nonempty_string(video_stream.get("codec_name"))
   208	        probe.video_profile = _nonempty_string(video_stream.get("profile"))
   209	        level = video_stream.get("level")
   210	        if level is not None and str(level).strip() not in {"", "-99"}:
   211	            probe.video_level = str(level).strip()
   212	        probe.pixel_format = _nonempty_string(video_stream.get("pix_fmt"))
   213	
   214	        # Some containers omit format.duration while exposing stream.duration.
   215	        if probe.duration_rational is None:
   216	            probe.duration_rational = _duration_rational(video_stream.get("duration"))
   217	            if probe.duration_rational is not None:
   218	                probe.duration_seconds = float(Fraction(*probe.duration_rational))
   219	
   220	    if audio_stream is not None:
   221	        probe.audio_codec = _nonempty_string(audio_stream.get("codec_name"))
   222	        probe.audio_sample_rate = _int_or_none(audio_stream.get("sample_rate"), minimum=1)
   223	        probe.audio_channel_layout = _nonempty_string(
   224	            audio_stream.get("channel_layout")
   225	        )
   226	        probe.audio_channels = _int_or_none(audio_stream.get("channels"), minimum=1)
   227	        if probe.duration_rational is None:
   228	            probe.duration_rational = _duration_rational(audio_stream.get("duration"))
   229	            if probe.duration_rational is not None:
   230	                probe.duration_seconds = float(Fraction(*probe.duration_rational))
   231	
   232	    return probe
   233	
   234	
   235	def _ffprobe_metadata(
   236	    file_path: str | Path,
   237	    *,
   238	    timeout: float,
   239	    strict: bool,
   240	) -> MediaProbe:
   241	    ffprobe_exe = shutil.which("ffprobe")
   242	    if ffprobe_exe is None:
   243	        if strict:
   244	            raise MediaProbeError("ffprobe is not available on PATH")
   245	        return MediaProbe()
   246	
   247	    try:
   248	        proc = subprocess.run(
   249	            [
   250	                ffprobe_exe,
   251	                "-v",
   252	                "quiet",
   253	                "-print_format",
   254	                "json",
   255	                "-show_format",
   256	                "-show_streams",
   257	                str(file_path),
   258	            ],
   259	            capture_output=True,
   260	            text=True,
   261	            timeout=timeout,
   262	        )
   263	        if proc.returncode != 0:
   264	            if strict:
   265	                diagnostic = (proc.stderr or "").strip()
   266	                suffix = f": {diagnostic}" if diagnostic else ""
   267	                raise MediaProbeError(f"ffprobe failed with exit {proc.returncode}{suffix}")
   268	            return MediaProbe()
   269	        data = json.loads(proc.stdout)
   270	        if not isinstance(data, dict):
   271	            raise ValueError("ffprobe JSON root is not an object")
   272	    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
   273	        if strict:
   274	            raise MediaProbeError(f"ffprobe could not inspect {file_path}: {exc}") from exc
   275	        return MediaProbe()
   276	
   277	    try:
   278	        return _parse_ffprobe_payload(data, file_path)
   279	    except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
   280	        if strict:

 succeeded in 59ms:
   180	        if track.get("kind") == "audio"
   181	    }
   182	    video_clips = sorted(
   183	        [
   184	            clip
   185	            for clip in timeline_data.get("clips", [])
   186	            if clip.get("track") in visual_track_ids
   187	        ],
   188	        key=lambda clip: float(clip.get("at", 0) or 0),
   189	    )
   190	    audio_clips = sorted(
   191	        [
   192	            clip
   193	            for clip in timeline_data.get("clips", [])
   194	            if clip.get("track") in audio_track_ids
   195	        ],
   196	        key=lambda clip: float(clip.get("at", 0) or 0),
   197	    )
   198	    if not video_clips:
   199	        raise ValueError("ffmpeg engine needs at least one visual media clip")
   200	
   201	    asset_keys: list[str] = []
   202	    for clip in [*video_clips, *audio_clips]:
   203	        asset_key = str(clip.get("asset") or "")
   204	        if not asset_key:
   205	            raise ValueError(f"Clip {clip.get('id')!r} has no asset")
   206	        if asset_key not in registry["assets"]:
   207	            raise ValueError(
   208	                f"Clip {clip.get('id')!r} references unknown asset "
   209	                f"{asset_key!r}"
   210	            )
   211	        if asset_key not in asset_keys:
   212	            asset_keys.append(asset_key)
   213	
   214	    asset_index = {
   215	        asset_key: index for index, asset_key in enumerate(asset_keys)
   216	    }
   217	    filters: list[str] = []
   218	    video_labels: list[str] = []
   219	    copy_video_input: int | None = None
   220	    if len(video_clips) == 1:
   221	        clip = video_clips[0]
   222	        asset_key = str(clip["asset"])
   223	        entry = registry["assets"][asset_key]
   224	        source_duration = entry.get("duration")
   225	        source_resolution = entry.get("resolution")
   226	        source_fps = entry.get("fps")
   227	        start = float(clip.get("from", 0) or 0)
   228	        end = float(clip.get("to", start) or start)
   229	        at = float(clip.get("at", 0) or 0)
   230	        full_duration = (
   231	            isinstance(source_duration, (int, float))
   232	            and abs((end - start) - float(source_duration)) < 0.05
   233	        )
   234	        same_resolution = source_resolution == f"{width}x{height}"
   235	        same_fps = (
   236	            isinstance(source_fps, (int, float))
   237	            and not isinstance(source_fps, bool)
   238	            and math.isfinite(float(source_fps))
   239	            and abs(float(source_fps) - fps) < 1e-6
   240	        )
   241	        no_visual_adjustments = not any(
   242	            key in clip
   243	            for key in (
   244	                "x",
   245	                "y",
   246	                "width",
   247	                "height",
   248	                "cropTop",
   249	                "cropBottom",
   250	                "cropLeft",
   251	                "cropRight",
   252	                "effects",
   253	                "transition",
   254	            )
   255	        )
   256	        if (
   257	            inputs.stream_copy_allowed
   258	            and at == 0
   259	            and start == 0
   260	            and full_duration
   261	            and same_resolution
   262	            and same_fps
   263	            and no_visual_adjustments
   264	        ):
   265	            copy_video_input = asset_index[asset_key]
   266	    if copy_video_input is None:
   267	        for index, clip in enumerate(video_clips):
   268	            inp = asset_index[str(clip["asset"])]
   269	            start = float(clip.get("from", 0) or 0)
   270	            end = float(clip.get("to", start) or start)
   271	            label = f"v{index}"
   272	            filters.append(
   273	                f"[{inp}:v]trim=start={start:.6f}:end={end:.6f},"
   274	                "setpts=PTS-STARTPTS,"
   275	                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
   276	                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
   277	                f"fps={fps},format=yuv420p[{label}]"
   278	            )
   279	            video_labels.append(f"[{label}]")
   280	        filters.append(
   281	            "".join(video_labels)
   282	            + f"concat=n={len(video_labels)}:v=1:a=0[vout]"
   283	        )
   284	
   285	    audio_labels: list[str] = []
   286	    cursor = 0.0
   287	    audio_index = 0
   288	    for clip in audio_clips:
   289	        at = float(clip.get("at", 0))
   290	        if at > cursor + 1e-9:
   291	            duration = at - cursor
   292	            label = f"a{audio_index}"
   293	            filters.append(
   294	                f"anullsrc=r={inputs.audio_sample_rate}:cl=stereo,"
   295	                f"atrim=duration={duration:.6f}[{label}]"
   296	            )
   297	            audio_labels.append(f"[{label}]")
   298	            audio_index += 1
   299	        inp = asset_index[str(clip["asset"])]
   300	        start = float(clip.get("from", 0))
   301	        end = float(clip.get("to"))
   302	        track = tracks[str(clip["track"])]
   303	        from astrid.packs.rendering.backends.ffmpeg.support import effective_gain
   304	
   305	        volume = effective_gain(track, clip)
   306	        label = f"a{audio_index}"
   307	        filters.append(
   308	            f"[{inp}:a]atrim=start={start:.6f}:end={end:.6f},"
   309	            "asetpts=PTS-STARTPTS,"
   310	            f"aformat=sample_rates={inputs.audio_sample_rate}:channel_layouts=stereo,"
   311	            f"volume={volume:.6f}[{label}]"
   312	        )
   313	        audio_labels.append(f"[{label}]")
   314	        cursor = at + clip_duration_seconds(clip)
   315	        audio_index += 1
   316	
   317	    if audio_clips:
   318	        visual_duration = max(
   319	            float(clip.get("at", 0)) + clip_duration_seconds(clip)
   320	            for clip in video_clips
   321	        )
   322	        if visual_duration > cursor + 1e-9:
   323	            duration = visual_duration - cursor
   324	            label = f"a{audio_index}"
   325	            filters.append(
   326	                f"anullsrc=r={inputs.audio_sample_rate}:cl=stereo,"
   327	                f"atrim=duration={duration:.6f}[{label}]"
   328	            )
   329	            audio_labels.append(f"[{label}]")
   330	        filters.append(
   331	            "".join(audio_labels)
   332	            + f"concat=n={len(audio_labels)}:v=0:a=1[aout]"
   333	        )
   334	    return filters, copy_video_input
   335	
   336	
   337	def _has_audio_clips(timeline_data: Mapping[str, Any]) -> bool:
   338	    tracks = {
   339	        track.get("id"): track
   340	        for track in timeline_data.get("tracks", [])
   341	        if isinstance(track, Mapping)
   342	    }
   343	    return any(
   344	        isinstance(clip, Mapping)
   345	        and clip.get("clipType") == "media"
   346	        and tracks.get(clip.get("track"), {}).get("kind") == "audio"
   347	        for clip in timeline_data.get("clips", [])
   348	    )
   349	
   350	
   351	def _asset_input_argv(inputs: RenderCommandInputs) -> list[str]:
   352	    timeline_data = inputs.timeline_data
   353	    registry = inputs.registry
   354	    tracks = {
   355	        track.get("id"): track for track in timeline_data.get("tracks", [])
   356	    }
   357	    visual_track_ids = {
   358	        track["id"]
   359	        for track in tracks.values()
   360	        if track.get("kind") == "visual"
   361	    }
   362	    audio_track_ids = {
   363	        track["id"]
   364	        for track in tracks.values()
   365	        if track.get("kind") == "audio"
   366	    }
   367	    video_clips = sorted(
   368	        [
   369	            clip
   370	            for clip in timeline_data.get("clips", [])
   371	            if clip.get("track") in visual_track_ids
   372	        ],
   373	        key=lambda clip: float(clip.get("at", 0) or 0),
   374	    )
   375	    audio_clips = sorted(
   376	        [
   377	            clip
   378	            for clip in timeline_data.get("clips", [])
   379	            if clip.get("track") in audio_track_ids
   380	        ],
   381	        key=lambda clip: float(clip.get("at", 0) or 0),
   382	    )
   383	    asset_keys: list[str] = []
   384	    for clip in [*video_clips, *audio_clips]:
   385	        asset_key = str(clip.get("asset") or "")
   386	        if asset_key and asset_key not in asset_keys:
   387	            asset_keys.append(asset_key)
   388	
   389	    argv: list[str] = []
   390	    for asset_key in asset_keys:
   391	        entry = registry["assets"][asset_key]
   392	        file_value = entry.get("file")
   393	        if not isinstance(file_value, str) or not file_value:
   394	            raise ValueError(
   395	                "ffmpeg engine requires local file assets; "
   396	                f"{asset_key!r} has no file"
   397	            )
   398	        asset_path = Path(file_value)
   399	        if not asset_path.is_absolute():
   400	            asset_path = (inputs.assets_path.parent / asset_path).resolve()
   401	        argv.extend(["-i", str(asset_path)])
   402	    return argv
   403	
   404	
   405	def build_render_command_from_inputs(inputs: RenderCommandInputs) -> list[str]:
   406	    """Return FFmpeg argv for already-resolved, strictly supported inputs."""
   407	    filters, copy_video_input = build_filter_graph(inputs)
   408	    has_audio = _has_audio_clips(inputs.timeline_data)
   409	    return [
   410	        "ffmpeg",
   411	        "-hide_banner",
   412	        "-y",
   413	        *_asset_input_argv(inputs),
   414	        *(["-filter_complex", ";".join(filters)] if filters else []),
   415	        "-map",
   416	        (
   417	            f"{copy_video_input}:v:0"
   418	            if copy_video_input is not None
   419	            else "[vout]"
   420	        ),
   421	        *(["-map", "[aout]"] if has_audio else []),
   422	        "-c:v",
   423	        "copy" if copy_video_input is not None else "libx264",
   424	        *(
   425	            ["-preset", "veryfast", "-crf", "20"]
   426	            if copy_video_input is None
   427	            else []
   428	        ),
   429	        *(
   430	            ["-c:a", "aac", "-b:a", "192k"]
   431	            if has_audio
   432	            else ["-an"]
   433	        ),
   434	        "-movflags",
   435	        "+faststart",
   436	        str(inputs.output_path),
   437	    ]
   438	
   439	
   440	def build_render_command(
   441	    request: RenderRequest | Mapping[str, Any],
   442	    workspace: Path,
   443	) -> list[str]:
   444	    """Build FFmpeg argv for ``workspace/outputs/<request.output_name>``.
   445	
   446	    Stream-copy is permitted only when strict support's probe evidence says
   447	    the whole source is compatible (never trust registry metadata alone).
   448	    """
   449	    inputs = resolve_render_command_inputs(request, workspace)
   450	    try:
   451	        from astrid.core.rendering.contracts import RenderRequest
   452	        from astrid.packs.rendering.backends.ffmpeg.support import support
   453	
   454	        normalized_request = (
   455	            request
   456	            if isinstance(request, RenderRequest)
   457	            else RenderRequest.from_dict(request)
   458	        )
   459	        report = support(
   460	            normalized_request,
   461	            inputs.timeline_data,
   462	            inputs.registry,
   463	        )
   464	        stream_copy_allowed = (
   465	            report.supported and bool(report.features.get("stream_copy"))
   466	        )
   467	    except Exception:
   468	        stream_copy_allowed = False
   469	    inputs = replace(inputs, stream_copy_allowed=stream_copy_allowed)
   470	    return build_render_command_from_inputs(inputs)
   471	
   472	
   473	def build_render_command_from_data(
   474	    timeline_path: Path,
   475	    assets_path: Path,
   476	    output_path: Path,
   477	    timeline_data: Mapping[str, Any],
   478	    registry: Mapping[str, Any],
   479	    *,
   480	    audio_sample_rate: int = 48000,
   481	    stream_copy_allowed: bool = False,
   482	) -> list[str]:
   483	    """Build FFmpeg argv from ALREADY-LOADED, strictly supported data.
   484	
   485	    Used by the legacy facade path so the exact mappings it validated with
   486	    strict support are the ones rendered — no reload, no TOCTOU window.
   487	    """
   488	    return build_render_command_from_inputs(
   489	        RenderCommandInputs(
   490	            timeline_path=Path(timeline_path).resolve(),
   491	            assets_path=Path(assets_path).resolve(),
   492	            output_path=Path(output_path).resolve(),
   493	            timeline_data=dict(timeline_data),
   494	            registry=dict(registry),
   495	            audio_sample_rate=audio_sample_rate,
   496	            stream_copy_allowed=stream_copy_allowed,
   497	        )
   498	    )
   499	
   500	
   501	def build_render_command_for_paths(
   502	    timeline_path: Path,
   503	    assets_path: Path,
   504	    output_path: Path,
   505	) -> list[str]:
   506	    """Compatibility builder for the legacy facade's explicit output path."""
   507	
   508	    return build_render_command_from_inputs(
   509	        _command_inputs_for_paths(timeline_path, assets_path, output_path)
   510	    )
   511	
   512	
   513	__all__ = [
   514	    "RenderCommandInputs",
   515	    "build_filter_graph",
   516	    "build_render_command",
   517	    "build_render_command_for_paths",
   518	    "build_render_command_from_inputs",
   519	    "clip_duration_seconds",
   520	    "resolve_render_command_inputs",

 succeeded in 93ms:
   420	
   421	def _requested_ownership(
   422	    request: RenderRequest,
   423	    *,
   424	    has_audio_clips: bool,
   425	) -> tuple[AudioOwnership, list[str]]:
   426	    natural = AudioOwnership.RENDERED if has_audio_clips else AudioOwnership.NONE
   427	    ownership = natural
   428	    reasons: list[str] = []
   429	    if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
   430	        ownership = AudioOwnership.PASSTHROUGH
   431	    elif request.audio is not None and request.audio is not natural:
   432	        reasons.append(
   433	            f"audio={request.audio.value!r} is incompatible with timeline audio ownership {natural.value!r}"
   434	        )
   435	    if request.profile is not None and request.profile.has_audio != (
   436	        ownership is AudioOwnership.RENDERED
   437	    ):
   438	        reasons.append(
   439	            "requested profile audio fields do not match rendering.ffmpeg audio ownership"
   440	        )
   441	    return ownership, reasons
   442	
   443	
   444	def _whole_media_optimization(
   445	    timeline_data: Mapping[str, Any],
   446	    assets: Mapping[str, Any],
   447	    probes: Mapping[str, MediaProbe],
   448	) -> bool:
   449	    tracks = {
   450	        track.get("id"): track
   451	        for track in timeline_data.get("tracks", [])
   452	        if isinstance(track, Mapping)
   453	    }
   454	    visual = [
   455	        clip
   456	        for clip in timeline_data.get("clips", [])
   457	        if isinstance(clip, Mapping)
   458	        and clip.get("clipType") == "media"
   459	        and tracks.get(clip.get("track"), {}).get("kind") == "visual"
   460	    ]
   461	    table = _assets_table(assets)
   462	    if len(visual) != 1 or table is None:
   463	        return False
   464	    clip = visual[0]
   465	    entry = table.get(clip.get("asset"))
   466	    if not isinstance(entry, Mapping):
   467	        return False
   468	    media_probe = probes.get(str(clip.get("asset")))
   469	    if media_probe is None or not media_probe.has_video_stream:
   470	        return False
   471	    try:
   472	        bounds = _clip_range(clip)
   473	        width, height, fps = _canvas(timeline_data)
   474	        duration = _number(entry.get("duration"), "asset duration")
   475	        source_fps = _number(entry.get("fps"), "asset fps")
   476	    except ValueError:
   477	        return False
   478	    probed_duration = _probe_duration(media_probe)
   479	    probed_fps = media_probe.fps
   480	    if probed_fps is None and media_probe.fps_rational is not None:
   481	        numerator, denominator = media_probe.fps_rational
   482	        probed_fps = numerator / denominator
   483	    # Frame-accurate tolerance: at most ONE frame of drift is acceptable
   484	    # (half a frame each way), so extra trailing frames at high FPS cannot
   485	    # slip through a coarse 50 ms window.
   486	    frame_tolerance = 0.5 / fps if fps > 0 else 0.0
   487	    return (
   488	        bounds.at == 0
   489	        and bounds.source_from == 0
   490	        and abs(bounds.duration - duration) < frame_tolerance
   491	        and entry.get("resolution") == f"{width}x{height}"
   492	        and abs(source_fps - fps) < 1e-6
   493	        and probed_duration is not None
   494	        and abs(bounds.duration - probed_duration) < frame_tolerance
   495	        and media_probe.width == width
   496	        and media_probe.height == height
   497	        and probed_fps is not None
   498	        and abs(probed_fps - fps) < 1e-6
   499	        and (media_probe.video_codec or "") == "h264"
   500	        and (media_probe.pixel_format or "") == "yuv420p"
   501	        and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
   502	    )
   503	
   504	
   505	def _probe_time_base_matches(
   506	    probe: MediaProbe, expected: tuple[int, int]
   507	) -> bool:
   508	    """The probed stream time base must equal the canonical MP4 timescale."""
   509	    if probe.time_base is None:
   510	        return False
   511	    return Fraction(*probe.time_base) == Fraction(*expected)
   512	
   513	
   514	def _profile_support_reasons(
   515	    request: RenderRequest, timeline_data: Mapping[str, Any]
   516	) -> list[str]:
   517	    """Fail closed when the requested profile deviates from what the FFmpeg
   518	    backend actually produces (canvas dims/fps, codecs, pixel format, and
   519	    canonical audio rate/layout)."""
   520	    profile = request.profile
   521	    if profile is None:
   522	        return []
   523	    reasons: list[str] = []
   524	    try:
   525	        width, height, fps = _canvas(timeline_data)
   526	    except ValueError:
   527	        return reasons  # canvas failure already reported elsewhere
   528	    checks = (
   529	        ("width", profile.width, width),
   530	        ("height", profile.height, height),
   531	        ("fps", profile.fps_rational, (fps, 1)),
   532	        ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
   533	        ("container", profile.container, "mp4"),
   534	        ("video_codec", profile.video_codec, "h264"),
   535	        ("pixel_format", profile.pixel_format, "yuv420p"),
   536	    )
   537	    for field, requested, produced in checks:
   538	        if requested is None:
   539	            continue
   540	        if field in ("fps", "time_base"):
   541	            equal = _rational_equal(requested, produced)
   542	        else:
   543	            equal = requested == produced
   544	        if not equal:
   545	            reasons.append(
   546	                f"requested profile {field}={requested!r} is not produced by "
   547	                f"rendering.ffmpeg (produces {produced!r})"
   548	            )
   549	    if profile.has_audio:
   550	        for field, requested, produced in (
   551	            ("audio_sample_rate", profile.audio_sample_rate, 48000),
   552	            ("audio_channel_layout", profile.audio_channel_layout, "stereo"),
   553	            ("audio_codec", profile.audio_codec, "aac"),
   554	        ):
   555	            if requested is not None and requested != produced:
   556	                reasons.append(
   557	                    f"requested profile {field}={requested!r} is not produced by "
   558	                    f"rendering.ffmpeg (produces {produced!r})"
   559	                )
   560	    return reasons
   561	
   562	
   563	def _fps_int(fps_rational: tuple[int, int] | None) -> int | None:
   564	    if fps_rational is None:
   565	        return None
   566	    num, den = fps_rational
   567	    return num // den if den and num % den == 0 else None
   568	
   569	
   570	def _rational_equal(a: Any, b: Any) -> bool:
   571	    try:
   572	        return Fraction(*a) == Fraction(*b)
   573	    except (TypeError, ValueError, ZeroDivisionError):
   574	        return False
   575	
   576	
   577	def _canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
   578	    overrides = timeline_data.get("theme_overrides")
   579	    visual = overrides.get("visual") if isinstance(overrides, Mapping) else None
   580	    canvas = visual.get("canvas") if isinstance(visual, Mapping) else None
   581	    canvas = canvas if isinstance(canvas, Mapping) else {}
   582	    values: list[int] = []
   583	    for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
   584	        value = canvas.get(key, default)
   585	        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
   586	            raise ValueError(f"Canvas {key} must be a positive integer")
   587	        values.append(value)
   588	    return values[0], values[1], values[2]
   589	
   590	

 succeeded in 46ms:
     1	#!/usr/bin/env python3
     2	"""FFmpeg renderer and raw rendering-protocol v1 command adapter."""
     3	
     4	from __future__ import annotations
     5	
     6	import argparse
     7	import json
     8	import subprocess
     9	import sys
    10	from collections.abc import Mapping, Sequence
    11	from dataclasses import replace
    12	from fractions import Fraction
    13	from pathlib import Path
    14	from tempfile import TemporaryDirectory
    15	from typing import Any
    16	
    17	# Raw renderer commands run with a sanitized environment and the owning pack
    18	# as cwd.  Make the checkout importable when this file is executed directly.
    19	if __package__ in {None, ""}:
    20	    _CHECKOUT_ROOT = Path(__file__).resolve().parents[5]
    21	    if str(_CHECKOUT_ROOT) not in sys.path:
    22	        sys.path.insert(0, str(_CHECKOUT_ROOT))
    23	
    24	from astrid.core import timeline
    25	from astrid.core.audit import AuditContext
    26	from astrid.core.foundation.atomic_io import write_json_atomic
    27	from astrid.core.foundation.paths import REPO_ROOT
    28	from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict
    29	from astrid.core.rendering.artifacts import validate_render_result
    30	from astrid.core.rendering.contracts import (
    31	    AudioOwnership,
    32	    RenderProfile,
    33	    RenderRequest,
    34	    RenderResult,
    35	    SCHEMA_VERSION,
    36	    SupportReport,
    37	    VideoArtifact,
    38	)
    39	from astrid.core.rendering.errors import (
    40	    RendererException,
    41	    make_renderer_error,
    42	    raise_invalid_artifact_error,
    43	    raise_unsupported_error,
    44	)
    45	from astrid.core.rendering.publication import publish_render_result
    46	from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
    47	from astrid.packs.rendering.backends.ffmpeg.command import (
    48	    build_render_command,
    49	    build_render_command_for_paths,
    50	    build_render_command_from_data,
    51	    validate_ffmpeg_media_timeline,
    52	)
    53	from astrid.packs.rendering.backends.ffmpeg.support import (
    54	    ALTERNATIVE_BACKENDS,
    55	    BACKEND_ID,
    56	    BACKEND_VERSION,
    57	    support as strict_support,
    58	)
    59	from astrid.packs.rendering.backends.remotion import run as remotion_backend
    60	
    61	
    62	# Compatibility spellings retained while callers migrate off the facade's
    63	# historical private helper names.
    64	_validate_ffmpeg_media_timeline = validate_ffmpeg_media_timeline
    65	
    66	
    67	def _input_path(raw_path: str, workspace: Path) -> Path:
    68	    candidate = Path(raw_path).expanduser()
    69	    return (
    70	        candidate if candidate.is_absolute() else workspace / candidate
    71	    ).resolve()
    72	
    73	
    74	def _render_ffmpeg_media_to_path(
    75	    timeline_path: Path,
    76	    assets_path: Path,
    77	    out_path: Path,
    78	    *,
    79	    runner: Any | None = None,
    80	) -> Path:
    81	    """Execute the pure media command builder for one explicit output path.
    82	
    83	    The legacy facade path must enforce the same strict support as the
    84	    protocol backend: a timeline whose audio would be silently discarded
    85	    (e.g. a visual clip with nonzero effective volume) is refused here
    86	    rather than rendered with -an.
    87	    """
    88	    try:
    89	        timeline_data = json.loads(
    90	            Path(timeline_path).read_text(encoding="utf-8")
    91	        )
    92	        assets_data = timeline.load_registry(Path(assets_path))
    93	    except Exception as exc:
    94	        raise ValueError(
    95	            f"cannot load timeline/assets for FFmpeg render: {exc}"
    96	        ) from exc
    97	    from astrid.core.rendering.contracts import RenderRequest
    98	
    99	    request = RenderRequest(
   100	        schema_version=1,
   101	        timeline_path=str(timeline_path),
   102	        assets_registry_path=str(assets_path),
   103	        output_name=Path(out_path).name,
   104	    )
   105	    from astrid.packs.rendering.backends.ffmpeg.support import support as _support
   106	
   107	    report = _support(request, timeline_data, assets_data)
   108	    if not report.supported:
   109	        raise ValueError(
   110	            "FFmpeg media render refused by strict support: "
   111	            + "; ".join(report.reasons)
   112	        )
   113	
   114	    output = Path(out_path)
   115	    command_argv = build_render_command_from_data(
   116	        Path(timeline_path),
   117	        Path(assets_path),
   118	        output,
   119	        timeline_data,
   120	        assets_data,
   121	        stream_copy_allowed=bool(report.features.get("stream_copy")),
   122	    )
   123	    output.parent.mkdir(parents=True, exist_ok=True)
   124	    (subprocess.run if runner is None else runner)(command_argv, check=True)
   125	    return output
   126	
   127	
   128	def render(
   129	    timeline_path: Path,
   130	    assets_path: Path,
   131	    out_path: Path,
   132	    *,
   133	    previous_outputs: Sequence[Path] = (),
   134	    _render_to_path: Any | None = None,
   135	) -> Path:
   136	    """Render privately and publish the legacy video-plus-sidecar pair."""
   137	
   138	    resolved_out = Path(out_path).resolve()
   139	    resolved_out.parent.mkdir(parents=True, exist_ok=True)
   140	    with TemporaryDirectory(
   141	        prefix=f".{resolved_out.name}.publication-",
   142	        dir=str(resolved_out.parent),
   143	    ) as publication_tmp:
   144	        staged_video = Path(publication_tmp) / resolved_out.name
   145	        render_to_path = _render_ffmpeg_media_to_path
   146	        if _render_to_path is not None:
   147	            render_to_path = _render_to_path
   148	        render_to_path(timeline_path, assets_path, staged_video)
   149	        provenance = remotion_backend._render_provenance_payload(
   150	            out_path,
   151	            engine="ffmpeg",
   152	            timeline_path=timeline_path,
   153	            assets_path=assets_path,
   154	            project_dir=REPO_ROOT / "remotion",
   155	            composition_id="TimelineComposition",
   156	            theme_path=None,
   157	            active_theme=None,
   158	            registry_state=remotion_backend._effective_registry_state(None),
   159	            stage_summary={"root": None, "effects": []},
   160	        )
   161	        output = publish_render_result(
   162	            staged_video,
   163	            provenance,
   164	            out_path=out_path,
   165	            sidecar_path=remotion_backend._render_provenance_sidecar_path(
   166	                out_path
   167	            ),
   168	            previous_outputs=previous_outputs,
   169	        )
   170	
   171	    audit = AuditContext.from_env()
   172	    if audit is not None:
   173	        timeline_id = audit.register_asset(
   174	            kind="timeline",
   175	            path=timeline_path,
   176	            label="Render timeline",
   177	            stage="render_ffmpeg",
   178	        )
   179	        assets_id = audit.register_asset(
   180	            kind="assets_registry",
   181	            path=assets_path,
   182	            label="Render asset registry",
   183	            stage="render_ffmpeg",
   184	        )
   185	        render_id = audit.register_asset(
   186	            kind="render",
   187	            path=output,
   188	            label="Rendered video",
   189	            parents=[timeline_id, assets_id],
   190	            stage="render_ffmpeg",
   191	            metadata={"engine": "ffmpeg"},
   192	        )
   193	        audit.register_node(
   194	            stage="render_ffmpeg",
   195	            label="Render media-only timeline with ffmpeg",
   196	            parents=[timeline_id, assets_id],
   197	            outputs=[render_id],
   198	            metadata={"engine": "ffmpeg"},
   199	        )
   200	    return output
   201	
   202	
   203	_render_ffmpeg_media = render
   204	
   205	
   206	def _legacy_media_acceptance(
   207	    timeline_path: Path,
   208	    assets_path: Path,
   209	) -> tuple[bool, str | None]:
   210	    try:
   211	        timeline_data = json.loads(
   212	            Path(timeline_path).read_text(encoding="utf-8")
   213	        )
   214	        if not isinstance(timeline_data, dict):
   215	            raise ValueError("timeline must contain a JSON object")
   216	        timeline.load_registry(Path(assets_path))
   217	        validate_ffmpeg_media_timeline(timeline_data)
   218	        tracks = {
   219	            track.get("id"): track
   220	            for track in timeline_data.get("tracks", [])
   221	        }
   222	        has_visual_media_clip = any(
   223	            clip.get("clipType") == "media"
   224	            and tracks.get(clip.get("track"), {}).get("kind") == "visual"
   225	            for clip in timeline_data.get("clips", [])
   226	        )
   227	        if not has_visual_media_clip:
   228	            return False, "ffmpeg engine needs at least one visual media clip"
   229	    except Exception as exc:
   230	        return False, str(exc) or type(exc).__name__
   231	    return True, None
   232	
   233	
   234	def can_render_with_ffmpeg_media(
   235	    timeline_path: Path,
   236	    assets_path: Path,
   237	) -> bool:
   238	    """Return the facade's legacy FFmpeg-media eligibility decision."""
   239	
   240	    accepted, _reason = _legacy_media_acceptance(timeline_path, assets_path)
   241	    return accepted
   242	
   243	
   244	_can_render_with_ffmpeg_media = can_render_with_ffmpeg_media
   245	
   246	
   247	def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
   248	    """Load request files and delegate to the fail-closed evaluator."""
   249	
   250	    timeline_path = _input_path(request.timeline_path, workspace)

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '1,245p'
nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '420,590p'
nl -ba astrid/core/rendering/profile.py | sed -n '240,340p'
nl -ba astrid/core/rendering/contracts.py | sed -n '120,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 112ms:
     1	"""Pure FFmpeg command builders for the media-only renderer.
     2	
     3	The builders read the immutable request inputs and return argv.  They do not
     4	create directories, write files, or launch subprocesses, which keeps command
     5	construction independently testable from execution and publication.
     6	"""
     7	
     8	from __future__ import annotations
     9	
    10	import json
    11	import math
    12	from collections.abc import Mapping
    13	from dataclasses import dataclass, replace
    14	from pathlib import Path
    15	from typing import Any
    16	
    17	from astrid.core import timeline
    18	from astrid.core.rendering.contracts import RenderRequest
    19	
    20	
    21	@dataclass(frozen=True)
    22	class RenderCommandInputs:
    23	    """Resolved, validated inputs used to construct one FFmpeg argv."""
    24	
    25	    timeline_path: Path
    26	    assets_path: Path
    27	    output_path: Path
    28	    timeline_data: dict[str, Any]
    29	    registry: dict[str, Any]
    30	    audio_sample_rate: int = 48000
    31	    # Probe-derived evidence from strict support: stream-copy is only
    32	    # permitted when the actual media probe confirmed whole-source
    33	    # compatibility (never trust registry metadata alone).
    34	    stream_copy_allowed: bool = False
    35	
    36	
    37	def timeline_canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
    38	    canvas = (
    39	        timeline_data.get("theme_overrides", {})
    40	        .get("visual", {})
    41	        .get("canvas", {})
    42	    )
    43	    return (
    44	        int(canvas.get("width", 1920)),
    45	        int(canvas.get("height", 1080)),
    46	        int(canvas.get("fps", 30)),
    47	    )
    48	
    49	
    50	def clip_duration_seconds(clip: Mapping[str, Any]) -> float:
    51	    clip_id = clip.get("id")
    52	
    53	    def number(value: Any, label: str) -> float:
    54	        if isinstance(value, bool) or not isinstance(value, (int, float)):
    55	            raise ValueError(f"Clip {clip_id!r} {label} must be a finite number")
    56	        result = float(value)
    57	        if not math.isfinite(result):
    58	            raise ValueError(f"Clip {clip_id!r} {label} must be a finite number")
    59	        return result
    60	
    61	    start = number(clip.get("from", 0), "from")
    62	    if "to" not in clip:
    63	        raise ValueError(f"Clip {clip_id!r} must declare a source to bound")
    64	    end = number(clip.get("to"), "to")
    65	    speed = number(clip.get("speed", 1), "speed")
    66	    if speed <= 0:
    67	        raise ValueError(f"Clip {clip_id!r} has non-positive speed {speed}")
    68	    if start < 0 or end <= start:
    69	        raise ValueError(
    70	            f"Clip {clip_id!r} must have positive source bounds with to > from"
    71	        )
    72	    return (end - start) / speed
    73	
    74	
    75	def validate_ffmpeg_media_timeline(timeline_data: Mapping[str, Any]) -> None:
    76	    """Reject every media-timeline semantic the pure builder would discard."""
    77	
    78	    # Local import avoids a module cycle: support owns semantic validation and
    79	    # imports this module only for command construction helpers.
    80	    from astrid.packs.rendering.backends.ffmpeg.support import structural_reasons
    81	
    82	    reasons = structural_reasons(
    83	        timeline_data,
    84	        allow_audio_reactive=False,
    85	    )
    86	    if reasons:
    87	        raise ValueError(reasons[0])
    88	
    89	
    90	def _input_path(raw_path: str, workspace: Path) -> Path:
    91	    candidate = Path(raw_path).expanduser()
    92	    return (
    93	        candidate if candidate.is_absolute() else workspace / candidate
    94	    ).resolve()
    95	
    96	
    97	def _coerce_request(request: RenderRequest | Mapping[str, Any]) -> RenderRequest:
    98	    if isinstance(request, RenderRequest):
    99	        return request
   100	    return RenderRequest.from_dict(request)
   101	
   102	
   103	def resolve_render_command_inputs(
   104	    request: RenderRequest | Mapping[str, Any],
   105	    workspace: Path,
   106	) -> RenderCommandInputs:
   107	    """Resolve the request's existing input files without mutating anything."""
   108	
   109	    normalized = _coerce_request(request)
   110	    root = Path(workspace).resolve()
   111	    timeline_path = _input_path(normalized.timeline_path, root)
   112	    if normalized.assets_registry_path is None:
   113	        raise ValueError("rendering.ffmpeg requires an assets registry")
   114	    assets_path = _input_path(normalized.assets_registry_path, root)
   115	    if not timeline_path.exists():
   116	        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
   117	    if not assets_path.exists():
   118	        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
   119	    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   120	    if not isinstance(timeline_data, dict):
   121	        raise ValueError("timeline must contain a JSON object")
   122	    registry = timeline.load_registry(assets_path)
   123	    validate_ffmpeg_media_timeline(timeline_data)
   124	    return RenderCommandInputs(
   125	        timeline_path=timeline_path,
   126	        assets_path=assets_path,
   127	        output_path=(root / "outputs" / normalized.output_name).resolve(),
   128	        timeline_data=timeline_data,
   129	        registry=dict(registry),
   130	    )
   131	
   132	
   133	def _command_inputs_for_paths(
   134	    timeline_path: Path,
   135	    assets_path: Path,
   136	    output_path: Path,
   137	) -> RenderCommandInputs:
   138	    resolved_timeline = Path(timeline_path).resolve()
   139	    resolved_assets = Path(assets_path).resolve()
   140	    if not resolved_timeline.exists():
   141	        raise FileNotFoundError(f"Timeline missing: {resolved_timeline}")
   142	    if not resolved_assets.exists():
   143	        raise FileNotFoundError(f"Asset registry missing: {resolved_assets}")
   144	    timeline_data = json.loads(resolved_timeline.read_text(encoding="utf-8"))
   145	    if not isinstance(timeline_data, dict):
   146	        raise ValueError("timeline must contain a JSON object")
   147	    registry = timeline.load_registry(resolved_assets)
   148	    validate_ffmpeg_media_timeline(timeline_data)
   149	    return RenderCommandInputs(
   150	        timeline_path=resolved_timeline,
   151	        assets_path=resolved_assets,
   152	        # The legacy explicit-path helper passed the caller's spelling through
   153	        # to FFmpeg and returned the same Path.  Protocol requests use the
   154	        # workspace builder above, which deliberately resolves their output.
   155	        output_path=Path(output_path),
   156	        timeline_data=timeline_data,
   157	        registry=dict(registry),
   158	    )
   159	
   160	
   161	def build_filter_graph(
   162	    inputs: RenderCommandInputs,
   163	) -> tuple[list[str], int | None]:
   164	    """Return the legacy filter graph and optional stream-copy input index."""
   165	
   166	    timeline_data = inputs.timeline_data
   167	    registry = inputs.registry
   168	    width, height, fps = timeline_canvas(timeline_data)
   169	    tracks = {
   170	        track.get("id"): track for track in timeline_data.get("tracks", [])
   171	    }
   172	    visual_track_ids = {
   173	        track["id"]
   174	        for track in tracks.values()
   175	        if track.get("kind") == "visual"
   176	    }
   177	    audio_track_ids = {
   178	        track["id"]
   179	        for track in tracks.values()
   180	        if track.get("kind") == "audio"
   181	    }
   182	    video_clips = sorted(
   183	        [
   184	            clip
   185	            for clip in timeline_data.get("clips", [])
   186	            if clip.get("track") in visual_track_ids
   187	        ],
   188	        key=lambda clip: float(clip.get("at", 0) or 0),
   189	    )
   190	    audio_clips = sorted(
   191	        [
   192	            clip
   193	            for clip in timeline_data.get("clips", [])
   194	            if clip.get("track") in audio_track_ids
   195	        ],
   196	        key=lambda clip: float(clip.get("at", 0) or 0),
   197	    )
   198	    if not video_clips:
   199	        raise ValueError("ffmpeg engine needs at least one visual media clip")
   200	
   201	    asset_keys: list[str] = []
   202	    for clip in [*video_clips, *audio_clips]:
   203	        asset_key = str(clip.get("asset") or "")
   204	        if not asset_key:
   205	            raise ValueError(f"Clip {clip.get('id')!r} has no asset")
   206	        if asset_key not in registry["assets"]:
   207	            raise ValueError(
   208	                f"Clip {clip.get('id')!r} references unknown asset "
   209	                f"{asset_key!r}"
   210	            )
   211	        if asset_key not in asset_keys:
   212	            asset_keys.append(asset_key)
   213	
   214	    asset_index = {
   215	        asset_key: index for index, asset_key in enumerate(asset_keys)
   216	    }
   217	    filters: list[str] = []
   218	    video_labels: list[str] = []
   219	    copy_video_input: int | None = None
   220	    if len(video_clips) == 1:
   221	        clip = video_clips[0]
   222	        asset_key = str(clip["asset"])
   223	        entry = registry["assets"][asset_key]
   224	        source_duration = entry.get("duration")
   225	        source_resolution = entry.get("resolution")
   226	        source_fps = entry.get("fps")
   227	        start = float(clip.get("from", 0) or 0)
   228	        end = float(clip.get("to", start) or start)
   229	        at = float(clip.get("at", 0) or 0)
   230	        full_duration = (
   231	            isinstance(source_duration, (int, float))
   232	            and abs((end - start) - float(source_duration)) < 0.05
   233	        )
   234	        same_resolution = source_resolution == f"{width}x{height}"
   235	        same_fps = (
   236	            isinstance(source_fps, (int, float))
   237	            and not isinstance(source_fps, bool)
   238	            and math.isfinite(float(source_fps))
   239	            and abs(float(source_fps) - fps) < 1e-6
   240	        )
   241	        no_visual_adjustments = not any(
   242	            key in clip
   243	            for key in (
   244	                "x",
   245	                "y",
   420	
   421	def _requested_ownership(
   422	    request: RenderRequest,
   423	    *,
   424	    has_audio_clips: bool,
   425	) -> tuple[AudioOwnership, list[str]]:
   426	    natural = AudioOwnership.RENDERED if has_audio_clips else AudioOwnership.NONE
   427	    ownership = natural
   428	    reasons: list[str] = []
   429	    if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
   430	        ownership = AudioOwnership.PASSTHROUGH
   431	    elif request.audio is not None and request.audio is not natural:
   432	        reasons.append(
   433	            f"audio={request.audio.value!r} is incompatible with timeline audio ownership {natural.value!r}"
   434	        )
   435	    if request.profile is not None and request.profile.has_audio != (
   436	        ownership is AudioOwnership.RENDERED
   437	    ):
   438	        reasons.append(
   439	            "requested profile audio fields do not match rendering.ffmpeg audio ownership"
   440	        )
   441	    return ownership, reasons
   442	
   443	
   444	def _whole_media_optimization(
   445	    timeline_data: Mapping[str, Any],
   446	    assets: Mapping[str, Any],
   447	    probes: Mapping[str, MediaProbe],
   448	) -> bool:
   449	    tracks = {
   450	        track.get("id"): track
   451	        for track in timeline_data.get("tracks", [])
   452	        if isinstance(track, Mapping)
   453	    }
   454	    visual = [
   455	        clip
   456	        for clip in timeline_data.get("clips", [])
   457	        if isinstance(clip, Mapping)
   458	        and clip.get("clipType") == "media"
   459	        and tracks.get(clip.get("track"), {}).get("kind") == "visual"
   460	    ]
   461	    table = _assets_table(assets)
   462	    if len(visual) != 1 or table is None:
   463	        return False
   464	    clip = visual[0]
   465	    entry = table.get(clip.get("asset"))
   466	    if not isinstance(entry, Mapping):
   467	        return False
   468	    media_probe = probes.get(str(clip.get("asset")))
   469	    if media_probe is None or not media_probe.has_video_stream:
   470	        return False
   471	    try:
   472	        bounds = _clip_range(clip)
   473	        width, height, fps = _canvas(timeline_data)
   474	        duration = _number(entry.get("duration"), "asset duration")
   475	        source_fps = _number(entry.get("fps"), "asset fps")
   476	    except ValueError:
   477	        return False
   478	    probed_duration = _probe_duration(media_probe)
   479	    probed_fps = media_probe.fps
   480	    if probed_fps is None and media_probe.fps_rational is not None:
   481	        numerator, denominator = media_probe.fps_rational
   482	        probed_fps = numerator / denominator
   483	    # Frame-accurate tolerance: at most ONE frame of drift is acceptable
   484	    # (half a frame each way), so extra trailing frames at high FPS cannot
   485	    # slip through a coarse 50 ms window.
   486	    frame_tolerance = 0.5 / fps if fps > 0 else 0.0
   487	    return (
   488	        bounds.at == 0
   489	        and bounds.source_from == 0
   490	        and abs(bounds.duration - duration) < frame_tolerance
   491	        and entry.get("resolution") == f"{width}x{height}"
   492	        and abs(source_fps - fps) < 1e-6
   493	        and probed_duration is not None
   494	        and abs(bounds.duration - probed_duration) < frame_tolerance
   495	        and media_probe.width == width
   496	        and media_probe.height == height
   497	        and probed_fps is not None
   498	        and abs(probed_fps - fps) < 1e-6
   499	        and (media_probe.video_codec or "") == "h264"
   500	        and (media_probe.pixel_format or "") == "yuv420p"
   501	        and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
   502	    )
   503	
   504	
   505	def _probe_time_base_matches(
   506	    probe: MediaProbe, expected: tuple[int, int]
   507	) -> bool:
   508	    """The probed stream time base must equal the canonical MP4 timescale."""
   509	    if probe.time_base is None:
   510	        return False
   511	    return Fraction(*probe.time_base) == Fraction(*expected)
   512	
   513	
   514	def _profile_support_reasons(
   515	    request: RenderRequest, timeline_data: Mapping[str, Any]
   516	) -> list[str]:
   517	    """Fail closed when the requested profile deviates from what the FFmpeg
   518	    backend actually produces (canvas dims/fps, codecs, pixel format, and
   519	    canonical audio rate/layout)."""
   520	    profile = request.profile
   521	    if profile is None:
   522	        return []
   523	    reasons: list[str] = []
   524	    try:
   525	        width, height, fps = _canvas(timeline_data)
   526	    except ValueError:
   527	        return reasons  # canvas failure already reported elsewhere
   528	    checks = (
   529	        ("width", profile.width, width),
   530	        ("height", profile.height, height),
   531	        ("fps", profile.fps_rational, (fps, 1)),
   532	        ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
   533	        ("container", profile.container, "mp4"),
   534	        ("video_codec", profile.video_codec, "h264"),
   535	        ("pixel_format", profile.pixel_format, "yuv420p"),
   536	    )
   537	    for field, requested, produced in checks:
   538	        if requested is None:
   539	            continue
   540	        if field in ("fps", "time_base"):
   541	            equal = _rational_equal(requested, produced)
   542	        else:
   543	            equal = requested == produced
   544	        if not equal:
   545	            reasons.append(
   546	                f"requested profile {field}={requested!r} is not produced by "
   547	                f"rendering.ffmpeg (produces {produced!r})"
   548	            )
   549	    if profile.has_audio:
   550	        for field, requested, produced in (
   551	            ("audio_sample_rate", profile.audio_sample_rate, 48000),
   552	            ("audio_channel_layout", profile.audio_channel_layout, "stereo"),
   553	            ("audio_codec", profile.audio_codec, "aac"),
   554	        ):
   555	            if requested is not None and requested != produced:
   556	                reasons.append(
   557	                    f"requested profile {field}={requested!r} is not produced by "
   558	                    f"rendering.ffmpeg (produces {produced!r})"
   559	                )
   560	    return reasons
   561	
   562	
   563	def _fps_int(fps_rational: tuple[int, int] | None) -> int | None:
   564	    if fps_rational is None:
   565	        return None
   566	    num, den = fps_rational
   567	    return num // den if den and num % den == 0 else None
   568	
   569	
   570	def _rational_equal(a: Any, b: Any) -> bool:
   571	    try:
   572	        return Fraction(*a) == Fraction(*b)
   573	    except (TypeError, ValueError, ZeroDivisionError):
   574	        return False
   575	
   576	
   577	def _canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
   578	    overrides = timeline_data.get("theme_overrides")
   579	    visual = overrides.get("visual") if isinstance(overrides, Mapping) else None
   580	    canvas = visual.get("canvas") if isinstance(visual, Mapping) else None
   581	    canvas = canvas if isinstance(canvas, Mapping) else {}
   582	    values: list[int] = []
   583	    for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
   584	        value = canvas.get(key, default)
   585	        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
   586	            raise ValueError(f"Canvas {key} must be a positive integer")
   587	        values.append(value)
   588	    return values[0], values[1], values[2]
   589	
   590	
   240	def resolve_render_profile(
   241	    timeline: Mapping[str, Any] | str | Path | Timeline,
   242	    assets: Mapping[str, Any] | str | Path | None = None,
   243	    *,
   244	    theme: Mapping[str, Any] | str | Path | None = None,
   245	    themes_root: str | Path | None = None,
   246	    audio_ownership: AudioOwnership | str | None = None,
   247	    duration_tolerance: int = 1,
   248	) -> RenderProfile:
   249	    """Resolve the canonical profile shared by planning and finalization.
   250	
   251	    Canvas selection deliberately mirrors Remotion's metadata calculation.
   252	    The encoder target remains backend-neutral but matches Astrid's canonical
   253	    MP4 output: H.264/yuv420p and, when audio is rendered, AAC 48 kHz stereo.
   254	    """
   255	
   256	    timeline_data = _timeline_mapping(timeline)
   257	    assets_data = _asset_mapping(assets)
   258	    merged_theme = _resolve_merged_theme(
   259	        timeline_data,
   260	        theme=theme,
   261	        themes_root=themes_root,
   262	    )
   263	    canvas = _remotion_canvas(timeline_data, merged_theme)
   264	    width = _positive_dimension(canvas.get("width"), default=1920, label="width")
   265	    height = _positive_dimension(canvas.get("height"), default=1080, label="height")
   266	    fps = _fps_fraction(canvas.get("fps", 30))
   267	
   268	    ownership = _coerce_audio_ownership(audio_ownership)
   269	    if ownership is None:
   270	        ownership = (
   271	            AudioOwnership.RENDERED
   272	            if _has_referenced_audio(timeline_data, assets_data)
   273	            else AudioOwnership.NONE
   274	        )
   275	    rendered_audio = ownership is AudioOwnership.RENDERED
   276	
   277	    return RenderProfile(
   278	        width=width,
   279	        height=height,
   280	        fps_rational=(fps.numerator, fps.denominator),
   281	        time_base=_mp4_time_base(fps),
   282	        container="mp4",
   283	        video_codec="h264",
   284	        video_profile=None,
   285	        video_level=None,
   286	        pixel_format="yuv420p",
   287	        audio_codec="aac" if rendered_audio else None,
   288	        audio_sample_rate=48_000 if rendered_audio else None,
   289	        audio_channel_layout="stereo" if rendered_audio else None,
   290	        duration_tolerance=duration_tolerance,
   291	    )
   292	
   293	
   294	__all__ = ["resolve_render_profile"]
   120	_RETIRED_PROVENANCE_V2_KEYS = frozenset(
   121	    {
   122	        "resolved_backend",
   123	        "source_pack",
   124	        "alias_chain",
   125	        "override",
   126	        "trust_eligibility",
   127	        "manifest_digest",
   128	        "support_decision",
   129	        "input_hashes",
   130	    }
   131	)
   132	
   133	RESERVED_BACKEND_FRAGMENT_KEYS = frozenset(
   134	    RENDER_RESULT_CORE_KEYS
   135	    | PROVENANCE_V2_CORE_KEYS
   136	    | PROVENANCE_V1_COMPATIBILITY_KEYS
   137	    | _RETIRED_PROVENANCE_V2_KEYS
   138	)
   139	
   140	
   141	def _json_safe(value: Any) -> Any:
   142	    """Return a recursively JSON-safe copy, rejecting non-wire values."""
   143	
   144	    if isinstance(value, Enum):
   145	        return _json_safe(value.value)
   146	    if value is None or isinstance(value, (str, bool, int)):
   147	        return value
   148	    if isinstance(value, float):
   149	        if not math.isfinite(value):
   150	            raise TypeError("JSON numbers must be finite")
   151	        return value
   152	    if isinstance(value, Path):
   153	        return str(value)
   154	    to_dict = getattr(value, "to_dict", None)
   155	    if callable(to_dict):
   156	        return _json_safe(to_dict())
   157	    if isinstance(value, Mapping):
   158	        return {str(key): _json_safe(item) for key, item in value.items()}
   159	    if isinstance(value, (list, tuple)):
   160	        return [_json_safe(item) for item in value]
   161	    if is_dataclass(value):
   162	        return {
   163	            dataclass_field.name: _json_safe(getattr(value, dataclass_field.name))
   164	            for dataclass_field in fields(value)
   165	        }
   166	    raise TypeError(f"value of type {type(value).__name__} is not JSON-safe")
   167	
   168	
   169	def _json_safe_mapping(value: Any, *, label: str = "value") -> dict[str, Any]:
   170	    payload = _json_safe(value)
   171	    if not isinstance(payload, dict):
   172	        raise TypeError(f"{label} must be a JSON object")
   173	    return payload
   174	
   175	
   176	def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
   177	    if not isinstance(value, Mapping):
   178	        raise TypeError(f"{label} must be an object")
   179	    return value
   180	
   181	
   182	def _validate_object_keys(
   183	    payload: Mapping[str, Any],
   184	    *,
   185	    required: set[str] | frozenset[str],
   186	    allowed: set[str] | frozenset[str],
   187	    label: str,
   188	) -> None:
   189	    missing = sorted(required - payload.keys())
   190	    if missing:
   191	        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
   192	    unknown = sorted(payload.keys() - allowed)
   193	    if unknown:
   194	        raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
   195	
   196	
   197	def _require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
   198	    if type(value) is not int:
   199	        raise TypeError(f"{label} must be an integer")
   200	    if minimum is not None and value < minimum:
   201	        raise ValueError(f"{label} must be >= {minimum}")
   202	    return value
   203	
   204	
   205	def _require_number(value: Any, label: str, *, exclusive_minimum: float | None = None) -> float:
   206	    if isinstance(value, bool) or not isinstance(value, (int, float)):
   207	        raise TypeError(f"{label} must be a number")
   208	    number = float(value)
   209	    if not math.isfinite(number):
   210	        raise ValueError(f"{label} must be finite")
   211	    if exclusive_minimum is not None and number <= exclusive_minimum:
   212	        raise ValueError(f"{label} must be > {exclusive_minimum:g}")
   213	    return number
   214	
   215	
   216	def compute_request_digest(request: Mapping[str, Any]) -> str:
   217	    """Deterministic SHA-256 of a canonical, JSON-normalized render request.
   218	
   219	    Uses sorted keys and compact separators so the digest is stable across
   220	    Python versions and dict insertion orders; replay verifies the request
   221	    against this digest.
   222	    """
   223	    return canonical_json_digest(_json_safe_mapping(request, label="render request"))
   224	
   225	
   226	def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
   227	    if not isinstance(value, str):
   228	        raise TypeError(f"{label} must be a string")
   229	    if "\x00" in value:
   230	        raise ValueError(f"{label} must not contain NUL")
   231	    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
   232	        raise ValueError(f"{label} must not be empty")
   233	    return value
   234	
   235	
   236	def _require_optional_string(value: Any, label: str) -> str | None:
   237	    if value is None:
   238	        return None
   239	    return _require_string(value, label)
   240	
   241	
   242	def _require_qualified_id(value: Any, label: str) -> str:
   243	    result = _require_string(value, label)
   244	    if not _QUALIFIED_ID_RE.fullmatch(result):
   245	        raise ValueError(
   246	            f"{label} must be a qualified id '<pack>.<name>' whose dot-separated "
   247	            "segments use lowercase letters, digits, and hyphens"
   248	        )
   249	    return result
   250	
   251	
   252	def _require_sha256(value: Any, label: str) -> str:
   253	    result = _require_string(value, label)
   254	    if not _SHA256_RE.fullmatch(result):
   255	        raise ValueError(f"{label} must be a lowercase 64-character SHA-256 digest")
   256	    return result
   257	
   258	
   259	def _require_override(value: Any, *, capability_id: str, label: str) -> dict[str, Any]:
   260	    """Validate an override record: ``{from, to}`` with ``to`` equal to the
   261	    resolution id (the override is what selected this implementation)."""
   262	    mapping = _json_safe_mapping(value, label=label)
   263	    required = {"from", "to"}
   264	    if set(mapping) != required:
   265	        raise ValueError(f"{label} must contain exactly 'from' and 'to'")
   266	    _require_qualified_id(mapping["from"], f"{label} 'from'")
   267	    resolved = _require_qualified_id(mapping["to"], f"{label} 'to'")
   268	    if resolved != capability_id:
   269	        raise ValueError(f"{label} 'to' must equal the resolved capability id {capability_id!r}")
   270	    return mapping
   271	
   272	
   273	def _require_string_list(value: Any, label: str) -> list[str]:
   274	    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
   275	        raise TypeError(f"{label} must be an array of strings")
   276	    return [_require_string(item, f"{label}[{index}]") for index, item in enumerate(value)]
   277	
   278	
   279	def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
   280	    mapping = _require_mapping(value, label)
   281	    return {
   282	        _require_string(key, f"{label} key"): _require_string(item, f"{label}[{key!r}]")
   283	        for key, item in mapping.items()
   284	    }
   285	
   286	
   287	def _require_hash_mapping(value: Any, label: str) -> dict[str, str]:
   288	    mapping = _require_mapping(value, label)
   289	    return {
   290	        _require_string(key, f"{label} key"): _require_sha256(item, f"{label}[{key!r}]")
   291	        for key, item in mapping.items()
   292	    }
   293	
   294	
   295	def _require_schema_version(value: Any, label: str) -> int:
   296	    if type(value) is not int or value != SCHEMA_VERSION:
   297	        _protocol_failure(
   298	            f"unknown or malformed {label} schema_version {value!r}; "
   299	            f"expected integer {SCHEMA_VERSION}",
   300	            details={"received": value, "supported": [SCHEMA_VERSION]},
   301	        )
   302	    return value
   303	
   304	
   305	def _require_rational(value: Any, label: str) -> tuple[int, int]:
   306	    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
   307	        raise TypeError(f"{label} must be a two-item [numerator, denominator] array")
   308	    numerator = _require_int(value[0], f"{label}[0]", minimum=1)
   309	    denominator = _require_int(value[1], f"{label}[1]", minimum=1)
   310	    return numerator, denominator
   311	
   312	
   313	def _require_frame_range(value: Any, label: str) -> tuple[int, int]:
   314	    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) != 2:
   315	        raise TypeError(f"{label} must be a two-item [start_frame, end_frame] array")
   316	    start = _require_int(value[0], f"{label}[0]", minimum=0)
   317	    end = _require_int(value[1], f"{label}[1]", minimum=1)
   318	    if end <= start:
   319	        raise ValueError(f"{label} must be half-open with end_frame > start_frame")
   320	    return start, end
   321	
   322	
   323	def _require_workspace_relative_path(value: Any, label: str) -> str:
   324	    raw = _require_string(value, label)
   325	    if "\\" in raw:
   326	        raise ValueError(f"{label} must be a normalized workspace path using forward slashes")
   327	    normalized = raw.replace("\\", "/")
   328	    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
   329	        raise ValueError(f"{label} must be relative to the invocation workspace")
   330	    if normalized.startswith("//"):

exec
/bin/zsh -lc "rg -n 'class RenderProfile|def .*match|video_profile|video_level' astrid/core/rendering/contracts.py astrid/core/rendering/artifacts.py astrid/packs/rendering/backends/ffmpeg astrid/packs/rendering/backends/remotion tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py | head -n 500" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '430,650p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '1,300p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'git diff --unified=50 58473c3a..a7b7b080 -- tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 82ms:
tests/packs/rendering/test_ffmpeg_support.py:455:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:456:        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py:574:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:575:        video_level="40",
astrid/core/rendering/artifacts.py:261:def _container_matches(probe: MediaProbe, expected: str) -> bool:
astrid/core/rendering/artifacts.py:284:    if field == "video_level":
astrid/core/rendering/artifacts.py:294:        "video_profile",
astrid/core/rendering/artifacts.py:334:    for field in ("video_profile", "video_level"):
astrid/core/rendering/artifacts.py:441:        ("video_profile", probe.video_profile),
astrid/core/rendering/artifacts.py:442:        ("video_level", probe.video_level),
tests/packs/rendering/test_ffmpeg_backend.py:139:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:140:        video_level="4.0",
tests/packs/rendering/test_ffmpeg_backend.py:349:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:350:        video_level="40",
astrid/core/rendering/contracts.py:452:class RenderProfile:
astrid/core/rendering/contracts.py:461:    video_profile: str | None = None
astrid/core/rendering/contracts.py:462:    video_level: str | None = None
astrid/core/rendering/contracts.py:478:            "video_profile",
astrid/core/rendering/contracts.py:479:            _require_optional_string(self.video_profile, "video_profile"),
astrid/core/rendering/contracts.py:483:            "video_level",
astrid/core/rendering/contracts.py:484:            _require_optional_string(self.video_level, "video_level"),
astrid/core/rendering/contracts.py:530:                "video_profile": self.video_profile,
astrid/core/rendering/contracts.py:531:                "video_level": self.video_level,
astrid/core/rendering/contracts.py:550:            "video_profile",
astrid/core/rendering/contracts.py:551:            "video_level",
astrid/core/rendering/contracts.py:564:            video_profile=data["video_profile"],
astrid/core/rendering/contracts.py:565:            video_level=data["video_level"],
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py:107:def match_and_validate(
astrid/packs/rendering/backends/ffmpeg/support.py:505:def _probe_time_base_matches(
astrid/packs/rendering/backends/remotion/run.py:904:def _profile_mismatches(
astrid/packs/rendering/backends/ffmpeg/run.py:490:        video_profile=probe.video_profile,
astrid/packs/rendering/backends/ffmpeg/run.py:491:        video_level=probe.video_level,

 succeeded in 125ms:
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
   586	    if profile.has_audio:
   587	        if ownership is not AudioOwnership.RENDERED:
   588	            raise ValueError(f"{label} with an audio profile must declare audio='rendered'")
   589	    elif ownership is AudioOwnership.RENDERED:
   590	        raise ValueError(f"{label} with audio='rendered' must have an audio profile")
   591	
   592	
   593	@dataclass(frozen=True)
   594	class Attachment:
   595	    """A named, opaque artifact preserved alongside the primary video."""
   596	
   597	    name: str
   598	    path: str
   599	    kind: str
   600	    sha256: str
   601	
   602	    def __post_init__(self) -> None:
   603	        name = _require_string(self.name, "attachment name")
   604	        if not _OUTPUT_NAME_RE.fullmatch(name):
   605	            raise ValueError("attachment name must be a portable basename")
   606	        kind = _require_string(self.kind, "attachment kind")
   607	        if not _KIND_RE.fullmatch(kind):
   608	            raise ValueError("attachment kind must be a lowercase hyphenated token")
   609	        object.__setattr__(self, "name", name)
   610	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))
   611	        object.__setattr__(self, "kind", kind)
   612	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "attachment sha256"))
   613	
   614	    def to_dict(self) -> dict[str, Any]:
   615	        return _json_safe_mapping(
   616	            {"name": self.name, "path": self.path, "kind": self.kind, "sha256": self.sha256}
   617	        )
   618	
   619	    @classmethod
   620	    def from_dict(cls, payload: Mapping[str, Any]) -> Attachment:
   621	        data = _require_mapping(payload, "attachment")
   622	        required = {"name", "path", "kind", "sha256"}
   623	        _validate_object_keys(data, required=required, allowed=required, label="attachment")
   624	        return cls(
   625	            name=data["name"],
   626	            path=data["path"],
   627	            kind=data["kind"],
   628	            sha256=data["sha256"],
   629	        )
   630	
   631	    @classmethod
   632	    def from_file(
   633	        cls,
   634	        *,
   635	        name: str,
   636	        path: str | Path,
   637	        kind: str,
   638	        workspace_root: str | Path,
   639	    ) -> Attachment:
   640	        relative, resolved = _relative_file_path(path, workspace_root, "attachment path")
   641	        return cls(name=name, path=relative, kind=kind, sha256=sha256_file(resolved))
   642	
   643	
   644	def _coerce_attachment_mapping(value: Any, label: str) -> dict[str, Attachment]:
   645	    mapping = _require_mapping(value, label)
   646	    result: dict[str, Attachment] = {}
   647	    seen_names: set[str] = set()
   648	    for raw_key, raw_attachment in mapping.items():
   649	        key = _require_string(raw_key, f"{label} key")
   650	        attachment = (

 succeeded in 100ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/packs/rendering/test_ffmpeg_backend.py b/tests/packs/rendering/test_ffmpeg_backend.py
index b2ded32d..5147cf21 100644
--- a/tests/packs/rendering/test_ffmpeg_backend.py
+++ b/tests/packs/rendering/test_ffmpeg_backend.py
@@ -138,100 +138,101 @@ def _profile() -> RenderProfile:
         video_codec="h264",
         video_profile="High",
         video_level="4.0",
         pixel_format="yuv420p",
         audio_codec="aac",
         audio_sample_rate=48000,
         audio_channel_layout="stereo",
     )
 
 
 def test_manifest_registers_static_raw_command_backend() -> None:
     manifest_path = (
         ROOT
         / "astrid"
         / "packs"
         / "rendering"
         / "backends"
         / "ffmpeg"
         / "renderer.yaml"
     )
     manifest = RendererManifest.from_dict(
         yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
     )
 
     assert manifest.id == "rendering.ffmpeg"
     assert manifest.protocol_version == 1
     assert manifest.command == ("python3", "run.py")
     assert manifest.operations == ("render", "support")
     assert manifest.required_permissions == ("project_files", "subprocess")
     assert manifest.required_binaries == ("ffmpeg", "ffprobe")
     assert manifest.capabilities["clip_types"] == ["media"]
     assert (manifest_path.parents[2] / manifest.command[1]).is_file()
 
     pack = yaml.safe_load(
         (manifest_path.parents[2] / "pack.yaml").read_text(encoding="utf-8")
     )
     assert "backends/ffmpeg/renderer.yaml" in pack["extensions"]["rendering"][
         "renderers"
     ]
 
 
 def test_support_is_strict_while_legacy_facade_eligibility_is_preserved(
     tmp_path: Path,
 ) -> None:
     timeline_path, assets_path = _write_inputs(tmp_path)
     source_probe = MediaProbe(
         duration_seconds=2,
         width=1920,
         height=1080,
         fps=30,
+        time_base=(1, 15360),
         video_codec="h264",
         pixel_format="yuv420p",
         audio_codec="aac",
         video_stream_present=True,
         audio_stream_present=True,
     )
 
     with mock.patch.object(
         ffmpeg,
         "ffprobe_metadata_strict",
         return_value=source_probe,
     ):
         report = ffmpeg.support(
             _request(timeline_path, assets_path),
             workspace=tmp_path,
         )
 
     assert report.supported is True
     assert report.reasons == []
     assert report.backend == ffmpeg.BACKEND_ID
     assert report.features["audio_ownership"] == "rendered"
     assert report.features["whole_media"] is True
     assert ffmpeg.can_render_with_ffmpeg_media(timeline_path, assets_path) is True
 
 
 def test_support_rejects_non_media_timeline(tmp_path: Path) -> None:
     timeline_path, assets_path = _write_inputs(
         tmp_path,
         timeline_data=_text_timeline(),
     )
 
     report = ffmpeg.support(_request(timeline_path, assets_path), workspace=tmp_path)
 
     assert report.supported is False
     assert any("unsupported clip kind" in reason for reason in report.reasons)
     assert ffmpeg.can_render_with_ffmpeg_media(timeline_path, assets_path) is False
 
 
 def test_raw_support_adapter_writes_authoritative_report(tmp_path: Path) -> None:
     timeline_path, assets_path = _write_inputs(tmp_path, registered=False)
     request_path = tmp_path / "request.json"
     result_path = tmp_path / "result.json"
     request_path.write_text(
         json.dumps(_request(timeline_path, assets_path).to_dict()),
         encoding="utf-8",
     )
 
     assert ffmpeg.main(
         [
             "support",
diff --git a/tests/packs/rendering/test_ffmpeg_support.py b/tests/packs/rendering/test_ffmpeg_support.py
index 68707f58..dcc8fb33 100644
--- a/tests/packs/rendering/test_ffmpeg_support.py
+++ b/tests/packs/rendering/test_ffmpeg_support.py
@@ -53,100 +53,101 @@ def _timeline(*, include_audio: bool = True, duration: float = 4.0) -> dict:
             }
         )
         clips.append(
             {
                 "id": "audio",
                 "at": 0,
                 "track": "a",
                 "clipType": "media",
                 "asset": "audio",
                 "from": 0,
                 "to": duration,
                 "speed": 1,
                 "volume": 0.4,
             }
         )
     return {
         "theme": "banodoco-default",
         "theme_overrides": {
             "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
         },
         "tracks": tracks,
         "clips": clips,
     }
 
 
 def _assets(tmp_path: Path, *, duration: float = 4.0) -> dict:
     return {
         "assets": {
             "video": {
                 "file": "video.mp4",
                 "type": "video/mp4",
                 "duration": duration,
                 "resolution": "640x360",
                 "fps": 30,
             },
             "audio": {
                 "file": "audio.wav",
                 "type": "audio/wav",
                 "duration": duration,
             },
         }
     }
 
 
 def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
     return MediaProbe(
         duration_seconds=duration,
         width=640,
         height=360,
         fps=30,
+        time_base=(1, 15360),
         resolution="640x360",
         video_codec="h264",
         pixel_format="yuv420p",
         audio_codec="aac" if audio else None,
         video_stream_present=True,
         audio_stream_present=audio,
     )
 
 
 def _audio_probe(*, duration: float = 4.0, present: bool = True) -> MediaProbe:
     return MediaProbe(
         duration_seconds=duration,
         audio_codec="pcm_s16le" if present else None,
         video_stream_present=False,
         audio_stream_present=present,
     )
 
 
 def _request(
     tmp_path: Path,
     *,
     audio: AudioOwnership | None = None,
     window: FrameWindow | None = None,
 ) -> RenderRequest:
     return RenderRequest(
         schema_version=SCHEMA_VERSION,
         timeline_path=str(tmp_path / "timeline.json"),
         assets_registry_path=str(tmp_path / "assets.json"),
         output_name="result.mp4",
         window=window,
         audio=audio,
         backend_config={ffmpeg.BACKEND_ID: {}},
     )
 
 
 def _evaluate(
     tmp_path: Path,
     timeline_data: dict,
     assets: dict,
     *,
     probes: dict[str, MediaProbe] | None = None,
     missing_files: set[str] | None = None,
     which=None,
     request: RenderRequest | None = None,
 ):
     missing = missing_files or set()
     for entry in assets.get("assets", {}).values():
         file_value = entry.get("file")
         if isinstance(file_value, str) and file_value not in missing:
             (tmp_path / file_value).write_bytes(b"source")

 succeeded in 158ms:
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
   286	    if field == "pixel_format":
   287	        # ffmpeg's deprecated yuvj* names are full-range variants of the
   288	        # standard yuv* formats (e.g. yuvj420p == yuv420p); treat them as
   289	        # equivalent so strict validation accepts real encoder output.
   290	        return _pixel_format_canonical(actual) == _pixel_format_canonical(expected)
   291	    if field in {
   292	        "container",
   293	        "video_codec",
   294	        "video_profile",
   295	        "audio_codec",
   296	        "audio_channel_layout",
   297	    }:
   298	        return _text(actual) == _text(expected)
   299	    return actual == expected
   300	

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '300,470p'
nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '430,620p'
nl -ba tests/packs/rendering/test_ffmpeg_support.py | sed -n '420,610p'
nl -ba tests/packs/rendering/test_ffmpeg_backend.py | sed -n '110,165p;320,380p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 254ms:
   300	
   301	
   302	def _pixel_format_canonical(value: Any) -> str:
   303	    text = _text(value) or ""
   304	    if text.startswith("yuvj"):
   305	        return "yuv" + text[4:]
   306	    return text
   307	
   308	
   309	def _compare_declared_to_expected(
   310	    declared: RenderProfile,
   311	    expected: RenderProfile,
   312	    ownership: AudioOwnership,
   313	) -> None:
   314	    fields = (
   315	        "width",
   316	        "height",
   317	        "fps_rational",
   318	        "time_base",
   319	        "container",
   320	        "video_codec",
   321	        "pixel_format",
   322	    )
   323	    for field in fields:
   324	        actual_value = _profile_value(declared, field)
   325	        expected_value = _profile_value(expected, field)
   326	        if not _same_profile_value(field, actual_value, expected_value):
   327	            _invalid(
   328	                "profile_mismatch",
   329	                f"renderer video profile has incompatible {field}",
   330	                field=field,
   331	                expected=expected_value,
   332	                actual=actual_value,
   333	            )
   334	    for field in ("video_profile", "video_level"):
   335	        expected_value = _profile_value(expected, field)
   336	        if expected_value is not None and not _same_profile_value(
   337	            field, _profile_value(declared, field), expected_value
   338	        ):
   339	            _invalid(
   340	                "profile_mismatch",
   341	                f"renderer video profile has incompatible {field}",
   342	                field=field,
   343	                expected=expected_value,
   344	                actual=_profile_value(declared, field),
   345	            )
   346	
   347	    if ownership is AudioOwnership.RENDERED:
   348	        if not expected.has_audio:
   349	            _invalid(
   350	                "audio_profile_mismatch",
   351	                "renderer declared rendered audio for a visual-only canonical profile",
   352	                expected_audio=False,
   353	                actual_audio=True,
   354	            )
   355	        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
   356	            if not _same_profile_value(
   357	                field, _profile_value(declared, field), _profile_value(expected, field)
   358	            ):
   359	                _invalid(
   360	                    "audio_profile_mismatch",
   361	                    f"renderer audio profile has incompatible {field}",
   362	                    field=field,
   363	                    expected=_profile_value(expected, field),
   364	                    actual=_profile_value(declared, field),
   365	                )
   366	    elif ownership is AudioOwnership.NONE and expected.has_audio:
   367	        _invalid(
   368	            "audio_profile_mismatch",
   369	            "renderer declared no audio for a canonical profile that requires audio",
   370	            expected_audio=True,
   371	            actual_audio=False,
   372	        )
   373	
   374	
   375	def _probe_required_video(probe: MediaProbe) -> None:
   376	    if not isinstance(probe, MediaProbe):
   377	        _invalid(
   378	            "incomplete_probe",
   379	            "strict ffprobe returned an invalid probe object",
   380	            received_type=type(probe).__name__,
   381	        )
   382	    if not probe.has_video_stream:
   383	        _invalid("missing_video_stream", "primary video has no video stream")
   384	    missing = [
   385	        field
   386	        for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
   387	        if getattr(probe, field) is None
   388	    ]
   389	    if probe.container is None and probe.format_name is None:
   390	        missing.append("container")
   391	    if probe.duration_rational is None and probe.duration_seconds is None:
   392	        missing.append("duration")
   393	    if missing:
   394	        _invalid(
   395	            "incomplete_probe",
   396	            "ffprobe returned incomplete primary-video metadata",
   397	            missing=missing,
   398	        )
   399	    if type(probe.width) is not int or probe.width <= 0:
   400	        _invalid("incomplete_probe", "ffprobe returned invalid video width", actual=probe.width)
   401	    if type(probe.height) is not int or probe.height <= 0:
   402	        _invalid("incomplete_probe", "ffprobe returned invalid video height", actual=probe.height)
   403	    _rational(probe.fps_rational, label="video FPS")
   404	    _rational(probe.time_base, label="video time base")
   405	
   406	
   407	def _compare_probe_to_profile(
   408	    probe: MediaProbe,
   409	    profile: RenderProfile,
   410	    *,
   411	    label: str,
   412	    compare_audio: bool,
   413	) -> None:
   414	    actual_values: dict[str, Any] = {
   415	        "width": probe.width,
   416	        "height": probe.height,
   417	        "fps_rational": probe.fps_rational,
   418	        "time_base": probe.time_base,
   419	        "video_codec": probe.video_codec,
   420	        "pixel_format": probe.pixel_format,
   421	    }
   422	    for field, actual in actual_values.items():
   423	        expected = _profile_value(profile, field)
   424	        if not _same_profile_value(field, actual, expected):
   425	            _invalid(
   426	                "profile_mismatch",
   427	                f"probed video {field} does not match {label}",
   428	                field=field,
   429	                expected=expected,
   430	                actual=actual,
   431	            )
   432	    if not _container_matches(probe, profile.container):
   433	        _invalid(
   434	            "profile_mismatch",
   435	            f"probed video container does not match {label}",
   436	            field="container",
   437	            expected=profile.container,
   438	            actual=probe.container or probe.format_name,
   439	        )
   440	    for field, actual in (
   441	        ("video_profile", probe.video_profile),
   442	        ("video_level", probe.video_level),
   443	    ):
   444	        expected = _profile_value(profile, field)
   445	        if expected is not None and not _same_profile_value(field, actual, expected):
   446	            _invalid(
   447	                "profile_mismatch",
   448	                f"probed video {field} does not match {label}",
   449	                field=field,
   450	                expected=expected,
   451	                actual=actual,
   452	            )
   453	
   454	    if compare_audio:
   455	        for field, actual in (
   456	            ("audio_codec", probe.audio_codec),
   457	            ("audio_sample_rate", probe.audio_sample_rate),
   458	            ("audio_channel_layout", probe.audio_channel_layout),
   459	        ):
   460	            expected = _profile_value(profile, field)
   461	            if field == "audio_channel_layout" and actual is None:
   462	                # Some containers (QuickTime sowt) expose channel COUNT but
   463	                # not a named layout. Compare channel count against the
   464	                # declared layout's canonical count instead of failing.
   465	                expected_channels = _layout_channel_count(expected)
   466	                if expected_channels is None or probe.audio_channels != expected_channels:
   467	                    _invalid(
   468	                        "audio_profile_mismatch",
   469	                        f"probed audio channel layout/count does not match {label}",
   470	                        field=field,
   430	            stage="render_ffmpeg_audio_reactive_colour",
   431	        )
   432	        render_id = audit.register_asset(
   433	            kind="render",
   434	            path=output,
   435	            label="Rendered audio-reactive colour video",
   436	            parents=[timeline_id, assets_id],
   437	            stage="render_ffmpeg_audio_reactive_colour",
   438	            metadata={
   439	                "engine": "ffmpeg",
   440	                "specialization": audio_reactive_colour.ADAPTER_ID,
   441	                "event_count": len(spec.events),
   442	                "marker_sha256": spec.marker_sha256,
   443	            },
   444	        )
   445	        audit.register_node(
   446	            stage="render_ffmpeg_audio_reactive_colour",
   447	            label="Render audio-reactive colour timeline with FFmpeg",
   448	            parents=[timeline_id, assets_id],
   449	            outputs=[render_id],
   450	            metadata={
   451	                "engine": "ffmpeg",
   452	                "specialization": audio_reactive_colour.ADAPTER_ID,
   453	            },
   454	        )
   455	    return output
   456	
   457	
   458	def _required(value: Any, label: str) -> Any:
   459	    if value is None:
   460	        raise RuntimeError(f"ffprobe did not report {label}")
   461	    return value
   462	
   463	
   464	def _profile_from_probe(
   465	    probe: MediaProbe,
   466	    ownership: AudioOwnership,
   467	) -> RenderProfile:
   468	    if not probe.has_video_stream:
   469	        raise RuntimeError("ffprobe did not report a video stream")
   470	    if ownership is AudioOwnership.RENDERED and not probe.has_audio_stream:
   471	        raise RuntimeError(
   472	            "rendering.ffmpeg media output did not contain its rendered audio"
   473	        )
   474	    if ownership is not AudioOwnership.RENDERED and probe.has_audio_stream:
   475	        raise RuntimeError(
   476	            "rendering.ffmpeg visual-only output unexpectedly contained audio"
   477	        )
   478	    audio_layout = probe.audio_channel_layout
   479	    if audio_layout is None and probe.audio_channels == 2:
   480	        audio_layout = "stereo"
   481	    elif audio_layout is None and probe.audio_channels == 1:
   482	        audio_layout = "mono"
   483	    return RenderProfile(
   484	        width=_required(probe.width, "video width"),
   485	        height=_required(probe.height, "video height"),
   486	        fps_rational=_required(probe.fps_rational, "video frame rate"),
   487	        time_base=_required(probe.time_base, "video time base"),
   488	        container=_required(probe.container, "container"),
   489	        video_codec=_required(probe.video_codec, "video codec"),
   490	        video_profile=probe.video_profile,
   491	        video_level=probe.video_level,
   492	        pixel_format=_required(probe.pixel_format, "pixel format"),
   493	        audio_codec=(
   494	            _required(probe.audio_codec, "audio codec")
   495	            if ownership is AudioOwnership.RENDERED
   496	            else None
   497	        ),
   498	        audio_sample_rate=(
   499	            _required(probe.audio_sample_rate, "audio sample rate")
   500	            if ownership is AudioOwnership.RENDERED
   501	            else None
   502	        ),
   503	        audio_channel_layout=(
   504	            _required(audio_layout, "audio channel layout")
   505	            if ownership is AudioOwnership.RENDERED
   506	            else None
   507	        ),
   508	        duration_tolerance=1,
   509	    )
   510	
   511	
   512	def _duration_frames(probe: MediaProbe, profile: RenderProfile) -> int:
   513	    if probe.duration_rational is not None:
   514	        duration = Fraction(*probe.duration_rational)
   515	    elif probe.duration_seconds is not None:
   516	        duration = Fraction(str(probe.duration_seconds))
   517	    else:
   518	        raise RuntimeError("ffprobe did not report a video duration")
   519	    frames = duration * Fraction(*profile.fps_rational)
   520	    return max(1, int(frames + Fraction(1, 2)))
   521	
   522	
   523	def _protocol_render(
   524	    request: RenderRequest,
   525	    *,
   526	    workspace: Path,
   527	) -> RenderResult:
   528	    report = support(request, workspace=workspace)
   529	    if not report.supported:
   530	        raise_unsupported_error(
   531	            backend=BACKEND_ID,
   532	            message="FFmpeg does not support this render request",
   533	            recovery_command="resolve the reported support reasons and retry",
   534	            details={"reasons": report.reasons, "features": report.features},
   535	        )
   536	
   537	    ownership = AudioOwnership(str(report.features["audio_ownership"]))
   538	    timeline_path = _input_path(request.timeline_path, workspace)
   539	    if request.assets_registry_path is None:
   540	        raise ValueError("rendering.ffmpeg requires an assets registry")
   541	    assets_path = _input_path(request.assets_registry_path, workspace)
   542	    specialization_spec: audio_reactive_colour.AudioReactiveColourSpec | None = None
   543	    if report.features.get("audio_reactive_colour") is True:
   544	        timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   545	        registry = timeline.load_registry(assets_path)
   546	        specialization_spec = audio_reactive_colour.match_and_validate(
   547	            timeline_data,
   548	            registry,
   549	            assets_path,
   550	        )
   551	        if specialization_spec is None:
   552	            raise RuntimeError(
   553	                "audio-reactive support evidence did not produce a specialization spec"
   554	            )
   555	
   556	    outputs_dir = workspace / "outputs"
   557	    output_path = outputs_dir / request.output_name
   558	    outputs_dir.mkdir(parents=True, exist_ok=True)
   559	    output_path.unlink(missing_ok=True)
   560	    try:
   561	        if specialization_spec is not None:
   562	            audio_reactive_colour.render(specialization_spec, output_path)
   563	        else:
   564	            subprocess.run(build_render_command(request, workspace), check=True)
   565	        try:
   566	            probe = ffprobe_metadata_strict(output_path)
   567	            probed_profile = _profile_from_probe(probe, ownership)
   568	        except (MediaProbeError, RuntimeError) as exc:
   569	            raise_invalid_artifact_error(
   570	                backend=BACKEND_ID,
   571	                message=f"FFmpeg output could not be validated: {exc}",
   572	                recovery_command=(
   573	                    "rerun rendering.ffmpeg in a fresh invocation workspace"
   574	                ),
   575	                details={"error_type": type(exc).__name__},
   576	            )
   577	        declared_profile = request.profile or probed_profile
   578	        duration_frames = _duration_frames(probe, declared_profile)
   579	        provenance_v1 = remotion_backend._render_provenance_payload(
   580	            output_path,
   581	            engine="ffmpeg",
   582	            timeline_path=timeline_path,
   583	            assets_path=assets_path,
   584	            project_dir=REPO_ROOT / "remotion",
   585	            composition_id="TimelineComposition",
   586	            theme_path=None,
   587	            active_theme=None,
   588	            registry_state=remotion_backend._effective_registry_state(None),
   589	            stage_summary={"root": None, "effects": []},
   590	        )
   591	        fragment: dict[str, Any] = {
   592	            "renderer": "ffmpeg",
   593	            "renderer_version": BACKEND_VERSION,
   594	            "support_evidence": report.features,
   595	            "legacy_v1": provenance_v1,
   596	        }
   597	        if specialization_spec is not None:
   598	            markers = [
   599	                {
   600	                    "frame": event.frame,
   601	                    "color": event.color,
   602	                    "id": event.event_id,
   603	                }
   604	                for event in specialization_spec.events
   605	            ]
   606	            specialization_fragment = {
   607	                "id": audio_reactive_colour.ADAPTER_ID,
   608	                "markers": markers,
   609	                "event_count": len(specialization_spec.events),
   610	                "frame_count": specialization_spec.total_frames,
   611	                "fps": specialization_spec.fps,
   612	                "marker_sha256": specialization_spec.marker_sha256,
   613	            }
   614	            fragment["specialization"] = specialization_fragment
   615	            provenance_v1["ffmpeg_specialization"] = (
   616	                audio_reactive_colour.ADAPTER_ID
   617	            )
   618	            provenance_v1["audio_reactive_colour"] = {
   619	                key: value
   620	                for key, value in specialization_fragment.items()
   420	    timeline_data = _timeline(include_audio=False)
   421	    assets = _assets(tmp_path)
   422	    del assets["assets"]["audio"]
   423	
   424	    report = _evaluate(
   425	        tmp_path,
   426	        timeline_data,
   427	        assets,
   428	        probes={"video.mp4": _video_probe()},
   429	        request=_request(tmp_path, audio=AudioOwnership.PASSTHROUGH),
   430	    )
   431	
   432	    assert report.supported is True
   433	    assert report.features["audio_ownership"] == "passthrough"
   434	
   435	
   436	def test_visual_only_protocol_result_declares_none(tmp_path: Path) -> None:
   437	    timeline_data = _timeline(include_audio=False)
   438	    assets = _assets(tmp_path)
   439	    del assets["assets"]["audio"]
   440	    _evaluate(
   441	        tmp_path,
   442	        timeline_data,
   443	        assets,
   444	        probes={"video.mp4": _video_probe()},
   445	    )
   446	    probe = MediaProbe(
   447	        duration_seconds=4,
   448	        width=640,
   449	        height=360,
   450	        fps=30,
   451	        fps_rational=(30, 1),
   452	        time_base=(1, 15360),
   453	        resolution="640x360",
   454	        video_codec="h264",
   455	        video_profile="High",
   456	        video_level="40",
   457	        pixel_format="yuv420p",
   458	        container="mp4",
   459	        duration_rational=(4, 1),
   460	        video_stream_present=True,
   461	        audio_stream_present=False,
   462	    )
   463	    seen: dict[str, list[str]] = {}
   464	
   465	    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
   466	        seen["argv"] = argv
   467	        output = Path(argv[-1])
   468	        output.parent.mkdir(parents=True, exist_ok=True)
   469	        output.write_bytes(b"video")
   470	        return subprocess.CompletedProcess(argv, 0)
   471	
   472	    with (
   473	        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
   474	        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", return_value=probe),
   475	        mock.patch.object(ffmpeg.subprocess, "run", side_effect=fake_run),
   476	        mock.patch.object(
   477	            ffmpeg.remotion_backend,
   478	            "_render_provenance_payload",
   479	            return_value={"engine": "ffmpeg"},
   480	        ),
   481	        mock.patch.object(ffmpeg, "validate_render_result"),
   482	    ):
   483	        result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)
   484	
   485	    assert result.audio_ownership is AudioOwnership.NONE
   486	    assert result.video.audio is AudioOwnership.NONE
   487	    assert result.video.profile.has_audio is False
   488	    assert "-an" in seen["argv"]
   489	    assert "-c:a" not in seen["argv"]
   490	
   491	
   492	def _reactive_timeline() -> dict:
   493	    return {
   494	        "theme": "banodoco-default",
   495	        "theme_overrides": {
   496	            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
   497	        },
   498	        "tracks": [
   499	            {"id": "v", "kind": "visual", "label": "Colour"},
   500	            {
   501	                "id": "a",
   502	                "kind": "audio",
   503	                "label": "Audio",
   504	                "volume": 0.5,
   505	            },
   506	        ],
   507	        "clips": [
   508	            {
   509	                "id": "colour",
   510	                "at": 0,
   511	                "track": "v",
   512	                "clipType": "audio-reactive-colour",
   513	                "hold": 1,
   514	                "params": {
   515	                    "schemaVersion": 1,
   516	                    "initialColor": "#102030",
   517	                    "events": [
   518	                        {"id": "one", "frame": 3, "color": "#D47795"},
   519	                        {"id": "two", "frame": 8, "color": "#26A7D0"},
   520	                    ],
   521	                },
   522	            },
   523	            {
   524	                "id": "audio",
   525	                "at": 0,
   526	                "track": "a",
   527	                "clipType": "media",
   528	                "asset": "audio",
   529	                "from": 0,
   530	                "to": 1,
   531	                "volume": 0.4,
   532	            },
   533	        ],
   534	    }
   535	
   536	
   537	def test_audio_reactive_support_gain_and_protocol_provenance_fragments(
   538	    tmp_path: Path,
   539	) -> None:
   540	    timeline_data = _reactive_timeline()
   541	    assets = {
   542	        "assets": {
   543	            "audio": {
   544	                "file": "audio.wav",
   545	                "type": "audio/wav",
   546	                "duration": 1,
   547	            }
   548	        }
   549	    }
   550	    report = _evaluate(
   551	        tmp_path,
   552	        timeline_data,
   553	        assets,
   554	        probes={"audio.wav": _audio_probe(duration=1)},
   555	    )
   556	    spec = audio_reactive_colour.match_and_validate(
   557	        timeline_data,
   558	        assets,
   559	        tmp_path / "assets.json",
   560	    )
   561	
   562	    assert report.supported is True
   563	    assert report.features["audio_reactive_colour"] is True
   564	    assert report.features["specialization"] == "audio-reactive-colour/v1"
   565	    assert spec is not None
   566	    assert spec.audio_volume == pytest.approx(0.2)
   567	
   568	    output_probe = MediaProbe(
   569	        width=640,
   570	        height=360,
   571	        fps_rational=(30, 1),
   572	        time_base=(1, 15360),
   573	        video_codec="h264",
   574	        video_profile="High",
   575	        video_level="40",
   576	        pixel_format="yuv420p",
   577	        audio_codec="aac",
   578	        audio_sample_rate=48000,
   579	        audio_channel_layout="stereo",
   580	        audio_channels=2,
   581	        container="mp4",
   582	        duration_rational=(1, 1),
   583	        video_stream_present=True,
   584	        audio_stream_present=True,
   585	    )
   586	
   587	    def fake_render(
   588	        _spec: audio_reactive_colour.AudioReactiveColourSpec,
   589	        output: Path,
   590	    ) -> Path:
   591	        output.parent.mkdir(parents=True, exist_ok=True)
   592	        output.write_bytes(b"video")
   593	        return output
   594	
   595	    def probe(path: Path) -> MediaProbe:
   596	        return (
   597	            _audio_probe(duration=1)
   598	            if Path(path).name == "audio.wav"
   599	            else output_probe
   600	        )
   601	
   602	    with (
   603	        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
   604	        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", side_effect=probe),
   605	        mock.patch.object(audio_reactive_colour, "render", side_effect=fake_render),
   606	        mock.patch.object(
   607	            ffmpeg.remotion_backend,
   608	            "_render_provenance_payload",
   609	            return_value={"engine": "ffmpeg"},
   610	        ),
   110	                "resolution": source_resolution,
   111	                "fps": 30,
   112	            }
   113	        }
   114	        if registered
   115	        else {}
   116	    )
   117	    assets_path.write_text(json.dumps({"assets": assets}), encoding="utf-8")
   118	    return timeline_path, assets_path
   119	
   120	
   121	def _request(timeline_path: Path, assets_path: Path) -> RenderRequest:
   122	    return RenderRequest(
   123	        schema_version=SCHEMA_VERSION,
   124	        timeline_path=str(timeline_path),
   125	        assets_registry_path=str(assets_path),
   126	        output_name="result.mp4",
   127	        backend_config={ffmpeg.BACKEND_ID: {}},
   128	    )
   129	
   130	
   131	def _profile() -> RenderProfile:
   132	    return RenderProfile(
   133	        width=1920,
   134	        height=1080,
   135	        fps_rational=(30, 1),
   136	        time_base=(1, 15360),
   137	        container="mp4",
   138	        video_codec="h264",
   139	        video_profile="High",
   140	        video_level="4.0",
   141	        pixel_format="yuv420p",
   142	        audio_codec="aac",
   143	        audio_sample_rate=48000,
   144	        audio_channel_layout="stereo",
   145	    )
   146	
   147	
   148	def test_manifest_registers_static_raw_command_backend() -> None:
   149	    manifest_path = (
   150	        ROOT
   151	        / "astrid"
   152	        / "packs"
   153	        / "rendering"
   154	        / "backends"
   155	        / "ffmpeg"
   156	        / "renderer.yaml"
   157	    )
   158	    manifest = RendererManifest.from_dict(
   159	        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
   160	    )
   161	
   162	    assert manifest.id == "rendering.ffmpeg"
   163	    assert manifest.protocol_version == 1
   164	    assert manifest.command == ("python3", "run.py")
   165	    assert manifest.operations == ("render", "support")
   320	    assert "[v0]concat=n=1:v=1:a=0[vout]" in filters
   321	    assert "anullsrc" not in filters
   322	    assert "[aout]" not in argv
   323	    assert "-c:a" not in argv
   324	    assert "-an" in argv
   325	    assert argv[argv.index("-c:v") + 1] == "libx264"
   326	    assert argv[argv.index("-preset") + 1] == "veryfast"
   327	    assert argv[argv.index("-crf") + 1] == "20"
   328	
   329	
   330	def test_protocol_render_returns_explicit_rendered_audio_result(
   331	    tmp_path: Path,
   332	) -> None:
   333	    timeline_path, assets_path = _write_inputs(tmp_path)
   334	    seen: dict[str, list[str]] = {}
   335	
   336	    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
   337	        seen["argv"] = argv
   338	        output = Path(argv[-1])
   339	        output.parent.mkdir(parents=True, exist_ok=True)
   340	        output.write_bytes(b"ffmpeg-video")
   341	        return subprocess.CompletedProcess(argv, 0)
   342	
   343	    probe = MediaProbe(
   344	        width=1920,
   345	        height=1080,
   346	        fps_rational=(30, 1),
   347	        time_base=(1, 15360),
   348	        video_codec="h264",
   349	        video_profile="High",
   350	        video_level="40",
   351	        pixel_format="yuv420p",
   352	        audio_codec="aac",
   353	        audio_sample_rate=48000,
   354	        audio_channel_layout="stereo",
   355	        audio_channels=2,
   356	        container="mp4",
   357	        format_name="mov,mp4",
   358	        duration_rational=(2, 1),
   359	        video_stream_present=True,
   360	        audio_stream_present=True,
   361	    )
   362	    with (
   363	        mock.patch.object(ffmpeg.subprocess, "run", side_effect=fake_run),
   364	        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", return_value=probe),
   365	        mock.patch.object(ffmpeg, "validate_render_result") as validate,
   366	        mock.patch.object(
   367	            ffmpeg.remotion_backend,
   368	            "_effective_registry_state",
   369	            return_value={"hash": "registry"},
   370	        ),
   371	        mock.patch.object(
   372	            ffmpeg.remotion_backend,
   373	            "_active_pack_order_for_provenance",
   374	            return_value=[],
   375	        ),
   376	    ):
   377	        result = ffmpeg._protocol_render(
   378	            _request(timeline_path, assets_path),
   379	            workspace=tmp_path,
   380	        )

exec
/bin/zsh -lc "rg -n -C 6 'profile=|_profile_support_reasons|video_profile|video_level|time_base|fps_rational' tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py | sed -n '1,500p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/packs/rendering/test_ffmpeg_support.py-97-def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
tests/packs/rendering/test_ffmpeg_support.py-98-    return MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-99-        duration_seconds=duration,
tests/packs/rendering/test_ffmpeg_support.py-100-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-101-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-102-        fps=30,
tests/packs/rendering/test_ffmpeg_support.py:103:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-104-        resolution="640x360",
tests/packs/rendering/test_ffmpeg_support.py-105-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py-106-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-107-        audio_codec="aac" if audio else None,
tests/packs/rendering/test_ffmpeg_support.py-108-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_support.py-109-        audio_stream_present=audio,
--
tests/packs/rendering/test_ffmpeg_support.py-293-    elif case == "window":
tests/packs/rendering/test_ffmpeg_support.py-294-        request = _request(
tests/packs/rendering/test_ffmpeg_support.py-295-            tmp_path,
tests/packs/rendering/test_ffmpeg_support.py-296-            window=FrameWindow(
tests/packs/rendering/test_ffmpeg_support.py-297-                start_frame=0,
tests/packs/rendering/test_ffmpeg_support.py-298-                end_frame=30,
tests/packs/rendering/test_ffmpeg_support.py:299:                fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py-300-            ),
tests/packs/rendering/test_ffmpeg_support.py-301-        )
tests/packs/rendering/test_ffmpeg_support.py-302-
tests/packs/rendering/test_ffmpeg_support.py-303-    report = _evaluate(
tests/packs/rendering/test_ffmpeg_support.py-304-        tmp_path,
tests/packs/rendering/test_ffmpeg_support.py-305-        timeline_data,
--
tests/packs/rendering/test_ffmpeg_support.py-445-    )
tests/packs/rendering/test_ffmpeg_support.py-446-    probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-447-        duration_seconds=4,
tests/packs/rendering/test_ffmpeg_support.py-448-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-449-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-450-        fps=30,
tests/packs/rendering/test_ffmpeg_support.py:451:        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py:452:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-453-        resolution="640x360",
tests/packs/rendering/test_ffmpeg_support.py-454-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py:455:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:456:        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py-457-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-458-        container="mp4",
tests/packs/rendering/test_ffmpeg_support.py-459-        duration_rational=(4, 1),
tests/packs/rendering/test_ffmpeg_support.py-460-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_support.py-461-        audio_stream_present=False,
tests/packs/rendering/test_ffmpeg_support.py-462-    )
--
tests/packs/rendering/test_ffmpeg_support.py-565-    assert spec is not None
tests/packs/rendering/test_ffmpeg_support.py-566-    assert spec.audio_volume == pytest.approx(0.2)
tests/packs/rendering/test_ffmpeg_support.py-567-
tests/packs/rendering/test_ffmpeg_support.py-568-    output_probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-569-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-570-        height=360,
tests/packs/rendering/test_ffmpeg_support.py:571:        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py:572:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-573-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py:574:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:575:        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py-576-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-577-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_support.py-578-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_support.py-579-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_support.py-580-        audio_channels=2,
tests/packs/rendering/test_ffmpeg_support.py-581-        container="mp4",
--
tests/packs/rendering/test_ffmpeg_backend.py-129-
tests/packs/rendering/test_ffmpeg_backend.py-130-
tests/packs/rendering/test_ffmpeg_backend.py-131-def _profile() -> RenderProfile:
tests/packs/rendering/test_ffmpeg_backend.py-132-    return RenderProfile(
tests/packs/rendering/test_ffmpeg_backend.py-133-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-134-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py:135:        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_backend.py:136:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-137-        container="mp4",
tests/packs/rendering/test_ffmpeg_backend.py-138-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py:139:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:140:        video_level="4.0",
tests/packs/rendering/test_ffmpeg_backend.py-141-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-142-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-143-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_backend.py-144-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_backend.py-145-    )
tests/packs/rendering/test_ffmpeg_backend.py-146-
--
tests/packs/rendering/test_ffmpeg_backend.py-182-    timeline_path, assets_path = _write_inputs(tmp_path)
tests/packs/rendering/test_ffmpeg_backend.py-183-    source_probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_backend.py-184-        duration_seconds=2,
tests/packs/rendering/test_ffmpeg_backend.py-185-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-186-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-187-        fps=30,
tests/packs/rendering/test_ffmpeg_backend.py:188:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-189-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py-190-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-191-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-192-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_backend.py-193-        audio_stream_present=True,
tests/packs/rendering/test_ffmpeg_backend.py-194-    )
--
tests/packs/rendering/test_ffmpeg_backend.py-340-        output.write_bytes(b"ffmpeg-video")
tests/packs/rendering/test_ffmpeg_backend.py-341-        return subprocess.CompletedProcess(argv, 0)
tests/packs/rendering/test_ffmpeg_backend.py-342-
tests/packs/rendering/test_ffmpeg_backend.py-343-    probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_backend.py-344-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-345-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py:346:        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_backend.py:347:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-348-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py:349:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:350:        video_level="40",
tests/packs/rendering/test_ffmpeg_backend.py-351-        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-352-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-353-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_backend.py-354-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_backend.py-355-        audio_channels=2,
tests/packs/rendering/test_ffmpeg_backend.py-356-        container="mp4",
--
tests/packs/rendering/test_ffmpeg_backend.py-403-    output_path.write_bytes(b"video")
tests/packs/rendering/test_ffmpeg_backend.py-404-    result = RenderResult(
tests/packs/rendering/test_ffmpeg_backend.py-405-        schema_version=SCHEMA_VERSION,
tests/packs/rendering/test_ffmpeg_backend.py-406-        video=VideoArtifact.from_file(
tests/packs/rendering/test_ffmpeg_backend.py-407-            path=output_path,
tests/packs/rendering/test_ffmpeg_backend.py-408-            workspace_root=tmp_path,
tests/packs/rendering/test_ffmpeg_backend.py:409:            profile=_profile(),
tests/packs/rendering/test_ffmpeg_backend.py-410-            duration_frames=60,
tests/packs/rendering/test_ffmpeg_backend.py-411-            audio=AudioOwnership.RENDERED,
tests/packs/rendering/test_ffmpeg_backend.py-412-        ),
tests/packs/rendering/test_ffmpeg_backend.py-413-        audio_ownership=AudioOwnership.RENDERED,
tests/packs/rendering/test_ffmpeg_backend.py-414-        backend_fragments={ffmpeg.BACKEND_ID: {"renderer": "ffmpeg"}},
tests/packs/rendering/test_ffmpeg_backend.py-415-    )

exec
/bin/zsh -lc "rg -n -C 4 'profile.*support|requested profile' tests/packs/rendering tests/core/rendering | head -n 400" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_raw_command_fixture.py-303-    assert result.video.sha256 == second_result.video.sha256
tests/core/rendering/test_raw_command_fixture.py-304-
tests/core/rendering/test_raw_command_fixture.py-305-
tests/core/rendering/test_raw_command_fixture.py-306-def test_support_rejects_audio_none_even_with_null_profile(tmp_path: Path) -> None:
tests/core/rendering/test_raw_command_fixture.py:307:    """A request for audio='none' with profile=null is unsupported: the
tests/core/rendering/test_raw_command_fixture.py-308-    renderer always produces rendered PCM stereo audio."""
tests/core/rendering/test_raw_command_fixture.py-309-    workspace = tmp_path / "workspace"
tests/core/rendering/test_raw_command_fixture.py-310-    workspace.mkdir(parents=True, exist_ok=True)
tests/core/rendering/test_raw_command_fixture.py-311-    request_path = workspace / "request.json"

exec
/bin/zsh -lc "rg -n '\\[tool\\.ruff|ruff|lint|format' pyproject.toml Makefile .github/workflows -g '*' | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
Makefile:3:#   make check   fast pre-deploy gates (structure, doctor, ruff, mypy, cycles) — seconds
Makefile:11:.PHONY: help check ci structure doctor ruff mypy cycles wheel ci-mirror editable
Makefile:14:	@echo "make check   - fast pre-deploy gates: structure, doctor, ruff, mypy, cycles (seconds)"
Makefile:16:	@echo "make <gate>  - run one gate: structure | doctor | ruff | mypy | cycles | wheel | ci-mirror | editable"
Makefile:19:check: structure doctor ruff mypy cycles
Makefile:30:ruff:
Makefile:31:	@$(PY) scripts/reshape/compare_ruff_baseline.py
Makefile:32:	@echo "✓ ruff baseline (no lint regression)"
pyproject.toml:43:    "ruff==0.12.0",
pyproject.toml:60:[tool.ruff]
pyproject.toml:63:# Evidence: advisory lint scope was introduced in 7d343bc with only reshape/concurrency paths.
pyproject.toml:73:[tool.ruff.lint]
.github/workflows/ci.yml:65:          python scripts/reshape/compare_ruff_baseline.py

exec
/bin/zsh -lc "rg -n -C 5 'enforce-audio-track|enforceAudioTrack' remotion/node_modules/@remotion remotion/node_modules/remotion 2>/dev/null | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
exec
/bin/zsh -lc "rg -n -C 4 'video_track_timescale|video_track' astrid tests | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n -C 6 '_mp4_time_base\\(' astrid tests | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 54ms:
tests/packs/rendering/test_ffmpeg_finalizer.py-701-            "-level:v",
tests/packs/rendering/test_ffmpeg_finalizer.py-702-            "3.1",
tests/packs/rendering/test_ffmpeg_finalizer.py-703-            "-pix_fmt",
tests/packs/rendering/test_ffmpeg_finalizer.py-704-            "yuv420p",
tests/packs/rendering/test_ffmpeg_finalizer.py:705:            "-video_track_timescale",
tests/packs/rendering/test_ffmpeg_finalizer.py-706-            "12800",
tests/packs/rendering/test_ffmpeg_finalizer.py-707-            "-an",
tests/packs/rendering/test_ffmpeg_finalizer.py-708-            str(source_path),
tests/packs/rendering/test_ffmpeg_finalizer.py-709-        ],
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-618-        argv.append("-shortest")
astrid/packs/rendering/finalizers/ffmpeg/run.py-619-
astrid/packs/rendering/finalizers/ffmpeg/run.py-620-    argv.extend(
astrid/packs/rendering/finalizers/ffmpeg/run.py-621-        [
astrid/packs/rendering/finalizers/ffmpeg/run.py:622:            "-video_track_timescale",
astrid/packs/rendering/finalizers/ffmpeg/run.py-623-            str(_mp4_timescale(target_profile)),
astrid/packs/rendering/finalizers/ffmpeg/run.py-624-        ]
astrid/packs/rendering/finalizers/ffmpeg/run.py-625-    )
astrid/packs/rendering/finalizers/ffmpeg/run.py-626-    if faststart:
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-658-    argv.extend(
astrid/packs/rendering/finalizers/ffmpeg/run.py-659-        [
astrid/packs/rendering/finalizers/ffmpeg/run.py-660-            "-c",
astrid/packs/rendering/finalizers/ffmpeg/run.py-661-            "copy",
astrid/packs/rendering/finalizers/ffmpeg/run.py:662:            "-video_track_timescale",
astrid/packs/rendering/finalizers/ffmpeg/run.py-663-            str(_mp4_timescale(target_profile)),
astrid/packs/rendering/finalizers/ffmpeg/run.py-664-        ]
astrid/packs/rendering/finalizers/ffmpeg/run.py-665-    )
astrid/packs/rendering/finalizers/ffmpeg/run.py-666-    if faststart:

 succeeded in 38ms:
astrid/packs/rendering/backends/ffmpeg/support.py-495-        and media_probe.width == width
astrid/packs/rendering/backends/ffmpeg/support.py-496-        and media_probe.height == height
astrid/packs/rendering/backends/ffmpeg/support.py-497-        and probed_fps is not None
astrid/packs/rendering/backends/ffmpeg/support.py-498-        and abs(probed_fps - fps) < 1e-6
astrid/packs/rendering/backends/ffmpeg/support.py-499-        and (media_probe.video_codec or "") == "h264"
astrid/packs/rendering/backends/ffmpeg/support.py-500-        and (media_probe.pixel_format or "") == "yuv420p"
astrid/packs/rendering/backends/ffmpeg/support.py:501:        and _probe_time_base_matches(media_probe, (1, _mp4_time_base(Fraction(fps))[1]))
astrid/packs/rendering/backends/ffmpeg/support.py-502-    )
astrid/packs/rendering/backends/ffmpeg/support.py-503-
astrid/packs/rendering/backends/ffmpeg/support.py-504-
astrid/packs/rendering/backends/ffmpeg/support.py-505-def _probe_time_base_matches(
astrid/packs/rendering/backends/ffmpeg/support.py-506-    probe: MediaProbe, expected: tuple[int, int]
astrid/packs/rendering/backends/ffmpeg/support.py-507-) -> bool:
--
astrid/packs/rendering/backends/ffmpeg/support.py-526-    except ValueError:
astrid/packs/rendering/backends/ffmpeg/support.py-527-        return reasons  # canvas failure already reported elsewhere
astrid/packs/rendering/backends/ffmpeg/support.py-528-    checks = (
astrid/packs/rendering/backends/ffmpeg/support.py-529-        ("width", profile.width, width),
astrid/packs/rendering/backends/ffmpeg/support.py-530-        ("height", profile.height, height),
astrid/packs/rendering/backends/ffmpeg/support.py-531-        ("fps", profile.fps_rational, (fps, 1)),
astrid/packs/rendering/backends/ffmpeg/support.py:532:        ("time_base", profile.time_base, _mp4_time_base(Fraction(fps))),
astrid/packs/rendering/backends/ffmpeg/support.py-533-        ("container", profile.container, "mp4"),
astrid/packs/rendering/backends/ffmpeg/support.py-534-        ("video_codec", profile.video_codec, "h264"),
astrid/packs/rendering/backends/ffmpeg/support.py-535-        ("pixel_format", profile.pixel_format, "yuv420p"),
astrid/packs/rendering/backends/ffmpeg/support.py-536-    )
astrid/packs/rendering/backends/ffmpeg/support.py-537-    for field, requested, produced in checks:
astrid/packs/rendering/backends/ffmpeg/support.py-538-        if requested is None:
--
astrid/core/rendering/profile.py-173-        raise TypeError("canvas fps must be a positive number or rational")
astrid/core/rendering/profile.py-174-    if fps <= 0:
astrid/core/rendering/profile.py-175-        raise ValueError("canvas fps must be positive")
astrid/core/rendering/profile.py-176-    return fps
astrid/core/rendering/profile.py-177-
astrid/core/rendering/profile.py-178-
astrid/core/rendering/profile.py:179:def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
astrid/core/rendering/profile.py-180-    """Mirror FFmpeg's MP4 video-track timescale selection.
astrid/core/rendering/profile.py-181-
astrid/core/rendering/profile.py-182-    Integer rates are repeatedly doubled until the timescale is at least
astrid/core/rendering/profile.py-183-    10,000 (24 -> 12,288; 30 -> 15,360).  NTSC-style rationals already carry
astrid/core/rendering/profile.py-184-    a large numerator (30000/1001 -> 30,000).
astrid/core/rendering/profile.py-185-    """
--
astrid/core/rendering/profile.py-275-    rendered_audio = ownership is AudioOwnership.RENDERED
astrid/core/rendering/profile.py-276-
astrid/core/rendering/profile.py-277-    return RenderProfile(
astrid/core/rendering/profile.py-278-        width=width,
astrid/core/rendering/profile.py-279-        height=height,
astrid/core/rendering/profile.py-280-        fps_rational=(fps.numerator, fps.denominator),
astrid/core/rendering/profile.py:281:        time_base=_mp4_time_base(fps),
astrid/core/rendering/profile.py-282-        container="mp4",
astrid/core/rendering/profile.py-283-        video_codec="h264",
astrid/core/rendering/profile.py-284-        video_profile=None,
astrid/core/rendering/profile.py-285-        video_level=None,
astrid/core/rendering/profile.py-286-        pixel_format="yuv420p",
astrid/core/rendering/profile.py-287-        audio_codec="aac" if rendered_audio else None,

exec
/bin/zsh -lc "command -v ruff || true
if command -v ruff >/dev/null 2>&1; then ruff check --no-cache astrid/packs/rendering/backends/ffmpeg/support.py astrid/packs/rendering/backends/remotion/run.py tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_ffmpeg_support.py; fi
sed -n '55,95p' pyproject.toml" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 743ms:
/Users/peteromalley/.pyenv/shims/ruff
astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
   |
 6 |   """
 7 |
 8 | / from __future__ import annotations
 9 | |
10 | | import math
11 | | import shutil
12 | | from collections.abc import Callable, Mapping
13 | | from dataclasses import dataclass
14 | | from fractions import Fraction
15 | | from pathlib import Path
16 | |
17 | | from astrid.core.rendering.profile import _mp4_time_base
18 | | from typing import Any
19 | |
20 | | from astrid.core.media import MediaProbe, ffprobe_metadata_strict
21 | | from astrid.core.rendering.contracts import (
22 | |     AudioOwnership,
23 | |     RenderRequest,
24 | |     SCHEMA_VERSION,
25 | |     SupportReport,
26 | | )
27 | | from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
   | |________________________________________________________________________^ I001
   |
   = help: Organize imports

astrid/packs/rendering/backends/ffmpeg/support.py:676:20: BLE001 Do not catch blind exception: `Exception`
    |
674 |                     raise TypeError("probe did not return MediaProbe")
675 |                 probes[asset_id] = probed
676 |             except Exception as exc:
    |                    ^^^^^^^^^ BLE001
677 |                 reasons.append(f"Asset {asset_id!r} cannot be probed: {exc}")
    |

astrid/packs/rendering/backends/ffmpeg/support.py:729:16: BLE001 Do not catch blind exception: `Exception`
    |
727 |                 assets_path,
728 |             )
729 |         except Exception as exc:
    |                ^^^^^^^^^ BLE001
730 |             reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
731 |         else:
    |

astrid/packs/rendering/backends/remotion/run.py:34:1: I001 [*] Import block is un-sorted or un-formatted
   |
32 |           sys.path.insert(0, str(_CHECKOUT_ROOT))
33 |
34 | / from astrid.core import timeline
35 | | from astrid.core.audit import AuditContext
36 | | from astrid.core.element.registry import load_default_registry
37 | | from astrid.core.element.schema import ElementDefinition
38 | | from astrid.core.foundation.atomic_io import write_json_atomic
39 | | from astrid.core.foundation.paths import REPO_ROOT, WORKSPACE_ROOT
40 | | from astrid.core.media import ffprobe_metadata_strict
41 | | from astrid.core.pack.discovery import discover_pack_metadata
42 | | from astrid.core.rendering.artifacts import validate_render_result
43 | | from astrid.core.rendering.assets import (
44 | |     AssetMaterializer,
45 | |     InvocationAssetServer,
46 | |     RangeHTTPRequestHandler as _RangeHTTPRequestHandler,
47 | | )
48 | | from astrid.core.rendering.contracts import (
49 | |     AudioOwnership,
50 | |     RenderProfile,
51 | |     RenderRequest,
52 | |     RenderResult,
53 | |     SCHEMA_VERSION,
54 | |     SupportReport,
55 | |     VideoArtifact,
56 | | )
57 | | from astrid.core.rendering.errors import (
58 | |     RendererException,
59 | |     make_renderer_error,
60 | |     raise_unsupported_error,
61 | | )
62 | | from astrid.core.rendering.profile import resolve_render_profile
63 | | from astrid.core.rendering.publication import publish_render_result
64 | | from astrid.core.subprocess_env import build_child_subprocess_env
65 | | from astrid.core.theme import load_theme
66 | | from astrid.packs.rendering.backends.remotion import lock as remotion_lock
67 | | from scripts import gen_effect_registry
   | |_______________________________________^ I001
   |
   = help: Organize imports

astrid/packs/rendering/backends/remotion/run.py:46:32: F401 [*] `astrid.core.rendering.assets.RangeHTTPRequestHandler` imported but unused
   |
44 |     AssetMaterializer,
45 |     InvocationAssetServer,
46 |     RangeHTTPRequestHandler as _RangeHTTPRequestHandler,
   |                                ^^^^^^^^^^^^^^^^^^^^^^^^ F401
47 | )
48 | from astrid.core.rendering.contracts import (
   |
   = help: Remove unused import: `astrid.core.rendering.assets.RangeHTTPRequestHandler`

astrid/packs/rendering/backends/remotion/run.py:957:12: BLE001 Do not catch blind exception: `Exception`
    |
955 |     try:
956 |         timeline_data = _serialize_timeline(timeline_path)
957 |     except Exception as exc:
    |            ^^^^^^^^^ BLE001
958 |         reasons.append(f"timeline is not renderable: {exc}")
959 |     try:
    |

astrid/packs/rendering/backends/remotion/run.py:961:12: BLE001 Do not catch blind exception: `Exception`
    |
959 |     try:
960 |         assets_data = _load_registry_mapping(assets_path)
961 |     except Exception as exc:
    |            ^^^^^^^^^ BLE001
962 |         reasons.append(f"assets registry is not renderable: {exc}")
    |

astrid/packs/rendering/backends/remotion/run.py:990:20: BLE001 Do not catch blind exception: `Exception`
    |
988 |             try:
989 |                 effects, aliases = _effect_registry_for_assets(settings.theme_path)
990 |             except Exception as exc:
    |                    ^^^^^^^^^ BLE001
991 |                 reasons.append(f"Remotion element registry cannot be resolved: {exc}")
992 |             else:
    |

astrid/packs/rendering/backends/remotion/run.py:1005:16: BLE001 Do not catch blind exception: `Exception`
     |
1003 |         try:
1004 |             canonical = _canonical_profile(timeline_path, assets_data, settings)
1005 |         except Exception as exc:
     |                ^^^^^^^^^ BLE001
1006 |             reasons.append(f"canonical Remotion profile cannot be resolved: {exc}")
1007 |         else:
     |

tests/packs/rendering/test_ffmpeg_backend.py:1:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 | / from __future__ import annotations
 2 | |
 3 | | import dataclasses
 4 | | import json
 5 | | import subprocess
 6 | | from pathlib import Path
 7 | | from unittest import mock
 8 | |
 9 | | import yaml
10 | |
11 | | from astrid.core.media import MediaProbe
12 | | from astrid.core.rendering.contracts import (
13 | |     AudioOwnership,
14 | |     RenderProfile,
15 | |     RenderRequest,
16 | |     RenderResult,
17 | |     RendererManifest,
18 | |     SCHEMA_VERSION,
19 | |     SupportReport,
20 | |     VideoArtifact,
21 | | )
22 | | from astrid.core.rendering.transport import CommandTransport
23 | | from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
24 | | from astrid.packs.rendering.backends.ffmpeg import command
25 | | from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
26 | | from astrid.packs.rendering.executors.render import audio_reactive_colour as legacy_audio_reactive
27 | | from astrid.packs.rendering.executors.render import run as facade
   | |_________________________________________________________________^ I001
   |
   = help: Organize imports

tests/packs/rendering/test_ffmpeg_support.py:1:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 | / from __future__ import annotations
 2 | |
 3 | | import copy
 4 | | import importlib
 5 | | import json
 6 | | import subprocess
 7 | | from pathlib import Path
 8 | | from unittest import mock
 9 | |
10 | | import pytest
11 | |
12 | | from astrid.core.media import MediaProbe
13 | | from astrid.core.rendering.contracts import (
14 | |     AudioOwnership,
15 | |     FrameWindow,
16 | |     RenderRequest,
17 | |     RenderResult,
18 | |     SCHEMA_VERSION,
19 | | )
20 | | from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
21 | | from astrid.packs.rendering.backends.ffmpeg import command
22 | | from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
23 | | from astrid.packs.rendering.backends.ffmpeg.support import support as evaluate_support
   | |______________________________________________________________________________________^ I001
   |
   = help: Organize imports

tests/packs/rendering/test_ffmpeg_support.py:229:5: E731 Do not assign a `lambda` expression, use a `def`
    |
227 |     }
228 |     missing_files: set[str] = set()
229 |     which = lambda binary: f"/usr/bin/{binary}"
    |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E731
230 |     request = _request(tmp_path)
    |
    = help: Rewrite `which` as a `def`

tests/packs/rendering/test_ffmpeg_support.py:292:9: E731 Do not assign a `lambda` expression, use a `def`
    |
290 |         probes["audio.wav"] = _audio_probe(present=False)
291 |     elif case == "missing_binary":
292 |         which = lambda binary: None if binary == "ffmpeg" else "/usr/bin/ffprobe"
    |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ E731
293 |     elif case == "window":
294 |         request = _request(
    |
    = help: Rewrite `which` as a `def`

Found 13 errors.
[*] 5 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
]

[tool.setuptools.packages.find]
include = ["astrid*"]

[tool.ruff]
target-version = "py311"
line-length = 100
# Evidence: advisory lint scope was introduced in 7d343bc with only reshape/concurrency paths.
# Inference: astrid/ was left out to keep the initial S0 gate narrow while known backlog remained.
include = [
    "astrid/**/*.py",
    "scripts/reshape/**/*.py",
    "tests/reshape/**/*.py",
    "tests/concurrency/two_tab_harness.py",
    "tests/concurrency/test_two_tab_harness_smoke.py",
]

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "I", "BLE"]

[tool.coverage.run]
source = ["astrid"]
omit = [
    ".megaplan/*",
    "out/*",
    "runs/*",
    ".venv/*",
    "venv/*",
    "*/venv/*",
    "*/.venv/*",
    "remotion/*",
    "tests/*",
    "*/tests/*",
    "scripts/*",
    "*/site-packages/*",
    "node_modules/*",
    "build/*",
    "dist/*",
]


exec
/bin/zsh -lc "sed -n '1,300p' scripts/reshape/compare_ruff_baseline.py
rg -n 'support.py' scripts/reshape -g '*.json' -g '*.txt' -g '*.toml' -g '*.py' | head -n 100
rg --files | rg 'ruff.*baseline|baseline.*ruff'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BASELINE_PATH = Path("scripts/reshape/baselines/ruff_astrid.json")
COMMAND = [
    sys.executable,
    "-m",
    "ruff",
    "check",
    ".",
    "--output-format",
    "json",
]


def _run() -> dict[str, Any]:
    proc = subprocess.run(COMMAND, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        if proc.stdout:
            sys.stdout.write(proc.stdout)
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        raise SystemExit(proc.returncode)
    findings = json.loads(proc.stdout or "[]")
    return {
        "tool": "ruff",
        "scope": ["pyproject.toml [tool.ruff].include"],
        "command": COMMAND,
        "finding_count": len(findings),
        "code_counts": dict(collections.Counter(item["code"] for item in findings)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--write-baseline", action="store_true")
    args = parser.parse_args()

    current = _run()
    if args.write_baseline:
        args.baseline.write_text(json.dumps(current, indent=2) + "\n")
        print(f"Wrote Ruff baseline to {args.baseline} ({current['finding_count']} findings)")
        return 0

    baseline = json.loads(args.baseline.read_text())
    baseline_count = int(baseline["finding_count"])
    current_count = int(current["finding_count"])
    print(f"Ruff findings: current={current_count} baseline={baseline_count}")
    if current_count <= baseline_count:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
scripts/reshape/baselines/ruff_astrid.json
scripts/reshape/compare_ruff_baseline.py

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 python scripts/reshape/compare_ruff_baseline.py; status=$?; echo exit=$status; cat scripts/reshape/baselines/ruff_astrid.json' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 994ms:
error: Failed to initialize cache at /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.ruff_cache: Operation not permitted (os error 1)
error: Failed to initialize cache at /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.ruff_cache: Operation not permitted (os error 1)
ruff failed
  Cause: Failed to create temporary file
  Cause: No such file or directory (os error 2) at path "/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.ruff_cache/0.12.0/.tmpJ0hrfG"
zsh:1: read-only variable: status

exec
/bin/zsh -lc 'RUFF_CACHE_DIR=/tmp/astrid-oracle-r3-ruff-cache PYTHONDONTWRITEBYTECODE=1 python scripts/reshape/compare_ruff_baseline.py; exit_code=$?; echo exit=$exit_code; sed -n '"'1,80p' scripts/reshape/baselines/ruff_astrid.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1292ms:
error: Failed to initialize cache at /tmp/astrid-oracle-r3-ruff-cache: Operation not permitted (os error 1)
error: Failed to initialize cache at /tmp/astrid-oracle-r3-ruff-cache: Operation not permitted (os error 1)
ruff failed
  Cause: Failed to create temporary file
  Cause: No such file or directory (os error 2) at path "/tmp/astrid-oracle-r3-ruff-cache/0.12.0/.tmpLV6hu1"
exit=2
{
  "tool": "ruff",
  "scope": [
    "pyproject.toml [tool.ruff].include"
  ],
  "command": [
    "/Users/peteromalley/.pyenv/versions/3.11.11/bin/python",
    "-m",
    "ruff",
    "check",
    ".",
    "--output-format",
    "json"
  ],
  "finding_count": 1383,
  "code_counts": {
    "I001": 95,
    "BLE001": 145,
    "F401": 430,
    "F841": 14,
    "E402": 644,
    "F821": 24,
    "F541": 2,
    "F811": 29
  }
}

exec
/bin/zsh -lc "ruff check . --no-cache --output-format json 2>/dev/null | PYTHONDONTWRITEBYTECODE=1 python -c 'import json,sys,collections; x=json.load(sys.stdin); print(len(x)); print(dict(collections.Counter(i[\"code\"] for i in x)))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 717ms:
1440
{'F401': 385, 'I001': 68, 'BLE001': 201, 'E402': 718, 'F841': 21, 'F821': 32, 'E702': 8, 'F402': 1, 'F541': 5, 'F601': 1}

exec
/bin/zsh -lc "git show 58473c3a:astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '1,35p'
git show a7b7b080"'^:astrid/packs/rendering/backends/remotion/run.py | sed -n '"'1,75p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
"""Fail-closed, request-sensitive support evidence for ``rendering.ffmpeg``.

This module is deliberately read-only.  It validates a decoded timeline and
asset registry, probes every referenced local source, and reports every reason
the FFmpeg renderer cannot preserve the requested semantics.
"""

from __future__ import annotations

import math
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrid.core.media import MediaProbe, ffprobe_metadata_strict
from astrid.core.rendering.contracts import (
    AudioOwnership,
    RenderRequest,
    SCHEMA_VERSION,
    SupportReport,
)
from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour


BACKEND_ID = "rendering.ffmpeg"
BACKEND_VERSION = "1.0.0"
ALTERNATIVE_BACKENDS = ("rendering.remotion",)

_TRACK_KINDS = frozenset({"visual", "audio"})
_POSITION_KEYS = frozenset({"x", "y", "width", "height"})
_CROP_KEYS = frozenset({"cropTop", "cropBottom", "cropLeft", "cropRight"})
_EFFECT_KEYS = frozenset({"effects", "entrance", "exit", "continuous", "keyframes"})
_TIMELINE_EPSILON_SECONDS = 1e-9
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
#!/usr/bin/env python3
"""Remotion renderer and raw rendering-protocol v1 command adapter.

The public ``render`` function is the compatibility seam used by the legacy
``rendering.render`` executor.  The command-line entry point is the leaf
backend protocol used by the generic renderer transport: it reads one request
file and writes exactly one result or structured error file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

# Raw renderer commands are deliberately executable without an installed
# Astrid wheel.  The command transport sanitizes PYTHONPATH, so direct script
# execution must make the owning checkout importable before SDK imports.
if __package__ in {None, ""}:
    _CHECKOUT_ROOT = Path(__file__).resolve().parents[5]
    if str(_CHECKOUT_ROOT) not in sys.path:
        sys.path.insert(0, str(_CHECKOUT_ROOT))

from astrid.core import timeline
from astrid.core.audit import AuditContext
from astrid.core.element.registry import load_default_registry
from astrid.core.element.schema import ElementDefinition
from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.paths import REPO_ROOT, WORKSPACE_ROOT
from astrid.core.media import ffprobe_metadata_strict
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.assets import (
    AssetMaterializer,
    InvocationAssetServer,
    RangeHTTPRequestHandler as _RangeHTTPRequestHandler,
)
from astrid.core.rendering.contracts import (
    AudioOwnership,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SCHEMA_VERSION,
    SupportReport,
    VideoArtifact,
)
from astrid.core.rendering.errors import (
    RendererException,
    make_renderer_error,
    raise_unsupported_error,
)
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.core.subprocess_env import build_child_subprocess_env
from astrid.core.theme import load_theme
from astrid.packs.rendering.backends.remotion import lock as remotion_lock
from scripts import gen_effect_registry


BACKEND_ID = "rendering.remotion"
BACKEND_VERSION = "1.0.0"
DEFAULT_COMPOSITION_ID = "TimelineComposition"
_REGISTRY_STATE_PATH = ".astrid-registry-state.json"
_CONFIG_KEYS = frozenset(
    {"project_dir", "composition_id", "composition", "theme_path", "theme", "min_free_gb"}

exec
/bin/zsh -lc 'echo CURRENT
ruff check --no-cache astrid/packs/rendering/backends/ffmpeg/support.py --output-format concise 2>/dev/null || true
echo PRIOR
git show 58473c3a:astrid/packs/rendering/backends/ffmpeg/support.py | ruff check --no-cache --stdin-filename astrid/packs/rendering/backends/ffmpeg/support.py --output-format concise - 2>/dev/null || true' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 169ms:
astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
astrid/packs/rendering/backends/ffmpeg/support.py:676:20: BLE001 Do not catch blind exception: `Exception`
astrid/packs/rendering/backends/ffmpeg/support.py:729:16: BLE001 Do not catch blind exception: `Exception`
Found 3 errors.
[*] 1 fixable with the `--fix` option.
PRIOR
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
astrid/packs/rendering/backends/ffmpeg/support.py:8:1: I001 [*] Import block is un-sorted or un-formatted
astrid/packs/rendering/backends/ffmpeg/support.py:646:20: BLE001 Do not catch blind exception: `Exception`
astrid/packs/rendering/backends/ffmpeg/support.py:699:16: BLE001 Do not catch blind exception: `Exception`
Found 3 errors.
[*] 1 fixable with the `--fix` option.

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from astrid.core.media import MediaProbe; from astrid.core.rendering.contracts import RenderProfile,RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import _profile_support_reasons,_whole_media_optimization; timeline={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":60}}},\"tracks\":[{\"id\":\"v\",\"kind\":\"visual\"}],\"clips\":[{\"id\":\"c\",\"track\":\"v\",\"clipType\":\"media\",\"asset\":\"video\",\"at\":0,\"from\":0,\"to\":1}]}; assets={\"assets\":{\"video\":{\"duration\":1,\"resolution\":\"640x360\",\"fps\":60}}}; request=RenderRequest(schema_version=1,timeline_path=\"timeline.json\",assets_registry_path=\"assets.json\",output_name=\"out.mp4\",profile=RenderProfile(width=640,height=360,fps_rational=(120,2),time_base=(2,30720),container=\"mp4\",video_codec=\"h264\",video_profile=\"Constrained Baseline\",video_level=\"5.2\",pixel_format=\"yuv420p\")); print(\"profile_reasons=\",_profile_support_reasons(request,timeline)); base=dict(width=640,height=360,fps=60,video_codec=\"h264\",pixel_format=\"yuv420p\",video_stream_present=True); print(\"copy canonical=\",_whole_media_optimization(timeline,assets,{\"video\":MediaProbe(duration_seconds=1,time_base=(1,15360),**base)})); print(\"copy 90k=\",_whole_media_optimization(timeline,assets,{\"video\":MediaProbe(duration_seconds=1,time_base=(1,90000),**base)})); print(\"copy extra frame=\",_whole_media_optimization(timeline,assets,{\"video\":MediaProbe(duration_seconds=1+1/60,time_base=(1,15360),**base)}))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 430ms:
profile_reasons= []
copy canonical= True
copy 90k= False
copy extra frame= False

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '590,780p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   590	
   591	def support(
   592	    request: RenderRequest,
   593	    timeline_data: Mapping[str, Any],
   594	    assets: Mapping[str, Any],
   595	    *,
   596	    probe: Probe | None = None,
   597	    which: BinaryResolver | None = None,
   598	) -> SupportReport:
   599	    """Return strict support evidence for one already-decoded request."""
   600	
   601	    reasons: list[str] = []
   602	    probe_media = probe or ffprobe_metadata_strict
   603	    resolve_binary = which or shutil.which
   604	    binary_available: dict[str, bool] = {}
   605	    for binary in ("ffmpeg", "ffprobe"):
   606	        available = resolve_binary(binary) is not None
   607	        binary_available[binary] = available
   608	        if not available:
   609	            reasons.append(f"required binary is unavailable: {binary}")
   610	
   611	    if request.window is not None:
   612	        reasons.append(
   613	            "rendering.ffmpeg accepts complete timelines, not native frame windows"
   614	        )
   615	    config = request.backend_config.get(BACKEND_ID, {})
   616	    if config:
   617	        reasons.append(
   618	            "rendering.ffmpeg does not accept backend-specific configuration"
   619	        )
   620	    if request.assets_registry_path is None:
   621	        reasons.append("rendering.ffmpeg requires an assets registry")
   622	    try:
   623	        _canvas(timeline_data)
   624	    except ValueError as exc:
   625	        reasons.append(str(exc))
   626	    reasons.extend(structural_reasons(timeline_data))
   627	
   628	    table = _assets_table(assets)
   629	    if table is None:
   630	        reasons.append("assets registry must contain an assets object")
   631	        table = {}
   632	    assets_path = _registry_path(request)
   633	    tracks = {
   634	        track.get("id"): track
   635	        for track in timeline_data.get("tracks", [])
   636	        if isinstance(track, Mapping)
   637	    }
   638	    media_clips = [
   639	        clip
   640	        for clip in timeline_data.get("clips", [])
   641	        if isinstance(clip, Mapping) and clip.get("clipType") == "media"
   642	    ]
   643	    audio_clips = [
   644	        clip
   645	        for clip in media_clips
   646	        if tracks.get(clip.get("track"), {}).get("kind") == "audio"
   647	    ]
   648	    ownership, ownership_reasons = _requested_ownership(
   649	        request,
   650	        has_audio_clips=bool(audio_clips),
   651	    )
   652	    reasons.extend(ownership_reasons)
   653	
   654	    probes: dict[str, MediaProbe] = {}
   655	    for clip in media_clips:
   656	        clip_id = clip.get("id")
   657	        asset_id = clip.get("asset")
   658	        if not isinstance(asset_id, str) or not asset_id:
   659	            reasons.append(f"Clip {clip_id!r} has no asset")
   660	            continue
   661	        entry = table.get(asset_id)
   662	        if not isinstance(entry, Mapping):
   663	            reasons.append(f"Clip {clip_id!r} references missing asset {asset_id!r}")
   664	            continue
   665	        try:
   666	            path = _asset_path(entry, asset_id=asset_id, assets_path=assets_path)
   667	        except (ValueError, FileNotFoundError) as exc:
   668	            reasons.append(str(exc))
   669	            continue
   670	        if asset_id not in probes and binary_available["ffprobe"]:
   671	            try:
   672	                probed = probe_media(path)
   673	                if not isinstance(probed, MediaProbe):
   674	                    raise TypeError("probe did not return MediaProbe")
   675	                probes[asset_id] = probed
   676	            except Exception as exc:
   677	                reasons.append(f"Asset {asset_id!r} cannot be probed: {exc}")
   678	
   679	        media_probe = probes.get(asset_id)
   680	        if media_probe is None:
   681	            continue
   682	        track = tracks.get(clip.get("track"), {})
   683	        kind = track.get("kind")
   684	        if kind == "visual" and not media_probe.has_video_stream:
   685	            reasons.append(
   686	                f"Visual clip {clip_id!r} source {asset_id!r} has no video stream"
   687	            )
   688	        if kind == "audio" and not media_probe.has_audio_stream:
   689	            reasons.append(
   690	                f"Audio clip {clip_id!r} source {asset_id!r} has no audio stream"
   691	            )
   692	        if kind == "visual" and media_probe.has_audio_stream:
   693	            try:
   694	                gain = effective_gain(track, clip)
   695	            except ValueError:
   696	                gain = 0.0
   697	            if gain != 0.0:
   698	                reasons.append(
   699	                    f"Visual clip {clip_id!r} requests embedded audio that rendering.ffmpeg would discard"
   700	                )
   701	        try:
   702	            bounds = _clip_range(clip)
   703	        except ValueError:
   704	            continue
   705	        source_duration = _probe_duration(media_probe)
   706	        if source_duration is None:
   707	            reasons.append(
   708	                f"Asset {asset_id!r} has no probed duration for source-bound validation"
   709	            )
   710	        elif bounds.source_to > source_duration + _SOURCE_BOUND_TOLERANCE_SECONDS:
   711	            reasons.append(
   712	                f"Clip {clip_id!r} source bound {bounds.source_to:.6f} exceeds "
   713	                f"asset {asset_id!r} duration {source_duration:.6f}"
   714	            )
   715	
   716	    reactive = any(
   717	        isinstance(clip, Mapping)
   718	        and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
   719	        for clip in timeline_data.get("clips", [])
   720	    )
   721	    specialization = False
   722	    if reactive:
   723	        try:
   724	            spec = audio_reactive_colour.match_and_validate(
   725	                dict(timeline_data),
   726	                dict(assets),
   727	                assets_path,
   728	            )
   729	        except Exception as exc:
   730	            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
   731	        else:
   732	            specialization = spec is not None
   733	
   734	    whole_media = not reactive and _whole_media_optimization(
   735	        timeline_data,
   736	        assets,
   737	        probes,
   738	    )
   739	    features: dict[str, bool | str] = {
   740	        "media_only": not specialization,
   741	        "full_timeline": True,
   742	        "windows": False,
   743	        "sequential_audio": True,
   744	        "audio_reactive_colour": specialization,
   745	        "whole_media": whole_media,
   746	        "whole_media_optimization": whole_media,
   747	        "stream_copy": whole_media,
   748	        "audio_ownership": ownership.value,
   749	    }
   750	    if specialization:
   751	        features["specialization"] = audio_reactive_colour.ADAPTER_ID
   752	
   753	    reasons.extend(_profile_support_reasons(request, timeline_data))
   754	
   755	    reasons = _dedupe(reasons)
   756	    return SupportReport(
   757	        schema_version=SCHEMA_VERSION,
   758	        supported=not reasons,
   759	        reasons=reasons,
   760	        features=features,
   761	        alternatives=list(ALTERNATIVE_BACKENDS) if reasons else [],
   762	        backend=BACKEND_ID,
   763	        backend_version=BACKEND_VERSION,
   764	    )
   765	
   766	
   767	__all__ = [
   768	    "ALTERNATIVE_BACKENDS",
   769	    "BACKEND_ID",
   770	    "BACKEND_VERSION",
   771	    "effective_gain",
   772	    "structural_reasons",
   773	    "support",
   774	]

exec
/bin/zsh -lc 'for fps_value in 24 30 60; do echo fps=$fps_value; ffmpeg -v error -f lavfi -i "color=c=black:s=16x16:r=$fps_value" -frames:v 4 -vf "fps=$fps_value,format=yuv420p" -c:v libx264 -preset veryfast -crf 20 -movflags frag_keyframe+empty_moov -f mp4 pipe:1 | ffprobe -v error -select_streams v:0 -show_entries stream=avg_frame_rate,time_base -of default=noprint_wrappers=1 pipe:0; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 293ms:
avg_frame_rate=24/1
time_base=1/12288
fps=30
avg_frame_rate=30/1
time_base=1/15360
fps=60
avg_frame_rate=60/1
time_base=1/15360

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '880,1060p'
nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '1060,1210p'
nl -ba astrid/packs/rendering/backends/remotion/renderer.yaml | sed -n '1,120p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   880	        return {"assets": {}}
   881	    data = json.loads(path.read_text(encoding="utf-8"))
   882	    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
   883	        raise ValueError("assets registry must be an object containing an assets object")
   884	    return data
   885	
   886	
   887	def _canonical_profile(
   888	    timeline_path: Path,
   889	    assets_data: Mapping[str, Any],
   890	    settings: _RenderSettings,
   891	) -> RenderProfile:
   892	    fallback_theme = settings.theme_path or (
   893	        WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
   894	    )
   895	    active_theme = _resolved_theme_for_render(timeline_path, fallback_theme)
   896	    return resolve_render_profile(
   897	        timeline_path,
   898	        assets_data,
   899	        theme=active_theme,
   900	        themes_root=REPO_ROOT / "themes",
   901	    )
   902	
   903	
   904	def _profile_mismatches(
   905	    requested: RenderProfile,
   906	    canonical: RenderProfile,
   907	) -> list[str]:
   908	    requested_data = requested.to_dict()
   909	    canonical_data = canonical.to_dict()
   910	    mismatches: list[str] = []
   911	    for field, expected in canonical_data.items():
   912	        if field == "duration_tolerance":
   913	            continue
   914	        actual = requested_data[field]
   915	        if actual != expected:
   916	            mismatches.append(f"{field}={actual!r} (requires {expected!r})")
   917	    return mismatches
   918	
   919	
   920	def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
   921	    """Return request-specific evidence for the timeline Remotion can render."""
   922	
   923	    reasons: list[str] = []
   924	    features: dict[str, bool | str] = {
   925	        "timeline_composition": True,
   926	        "full_timeline": True,
   927	        "windows": False,
   928	        "effects": True,
   929	        "asset_serving": "invocation-scoped",
   930	    }
   931	    try:
   932	        settings = _settings_from_request(request, workspace)
   933	    except (TypeError, ValueError) as exc:
   934	        settings = _RenderSettings(
   935	            project_dir=REPO_ROOT / "remotion",
   936	            composition_id=DEFAULT_COMPOSITION_ID,
   937	            theme_path=None,
   938	            min_free_gb=None,
   939	        )
   940	        reasons.append(str(exc))
   941	
   942	    if request.window is not None:
   943	        reasons.append(
   944	            "rendering.remotion accepts complete timelines, not native frame windows"
   945	        )
   946	
   947	    timeline_path = _input_path(request.timeline_path, workspace)
   948	    assets_path = (
   949	        _input_path(request.assets_registry_path, workspace)
   950	        if request.assets_registry_path is not None
   951	        else None
   952	    )
   953	    timeline_data: dict[str, Any] | None = None
   954	    assets_data: dict[str, Any] | None = None
   955	    try:
   956	        timeline_data = _serialize_timeline(timeline_path)
   957	    except Exception as exc:
   958	        reasons.append(f"timeline is not renderable: {exc}")
   959	    try:
   960	        assets_data = _load_registry_mapping(assets_path)
   961	    except Exception as exc:
   962	        reasons.append(f"assets registry is not renderable: {exc}")
   963	
   964	    if timeline_data is not None and assets_data is not None:
   965	        registered_assets = assets_data.get("assets", {})
   966	        missing_asset_ids = sorted(
   967	            {
   968	                str(clip.get("asset"))
   969	                for clip in timeline_data.get("clips", [])
   970	                if isinstance(clip, dict)
   971	                and isinstance(clip.get("asset"), str)
   972	                and clip.get("asset") not in registered_assets
   973	            }
   974	        )
   975	        if missing_asset_ids:
   976	            reasons.append(
   977	                "timeline references missing asset ids: " + ", ".join(missing_asset_ids)
   978	            )
   979	        dynamic_clip_types = sorted(
   980	            {
   981	                str(clip.get("clipType"))
   982	                for clip in timeline_data.get("clips", [])
   983	                if isinstance(clip, dict)
   984	                and clip.get("clipType", "media") != "media"
   985	            }
   986	        )
   987	        if dynamic_clip_types:
   988	            try:
   989	                effects, aliases = _effect_registry_for_assets(settings.theme_path)
   990	            except Exception as exc:
   991	                reasons.append(f"Remotion element registry cannot be resolved: {exc}")
   992	            else:
   993	                unknown_clip_types = [
   994	                    clip_type
   995	                    for clip_type in dynamic_clip_types
   996	                    if clip_type not in effects and clip_type not in aliases
   997	                ]
   998	                if unknown_clip_types:
   999	                    reasons.append(
  1000	                        "timeline uses unregistered Remotion clip types: "
  1001	                        + ", ".join(unknown_clip_types)
  1002	                    )
  1003	        try:
  1004	            canonical = _canonical_profile(timeline_path, assets_data, settings)
  1005	        except Exception as exc:
  1006	            reasons.append(f"canonical Remotion profile cannot be resolved: {exc}")
  1007	        else:
  1008	            # Remotion ALWAYS muxes an audio track (silent when the timeline
  1009	            # has none) and always muxes at the 90 kHz timescale; support must
  1010	            # describe the same contract render() implements.
  1011	            features["audio_ownership"] = AudioOwnership.RENDERED.value
  1012	            if request.audio is not None and request.audio is not AudioOwnership.RENDERED:
  1013	                reasons.append(
  1014	                    f"audio={request.audio.value!r} is incompatible with "
  1015	                    f"Remotion's always-rendered audio output"
  1016	                )
  1017	            if request.profile is not None:
  1018	                render_profile = replace(
  1019	                    canonical,
  1020	                    time_base=(1, 90000),
  1021	                    audio_codec=canonical.audio_codec or "aac",
  1022	                    audio_sample_rate=canonical.audio_sample_rate or 48000,
  1023	                    audio_channel_layout=canonical.audio_channel_layout or "stereo",
  1024	                )
  1025	                mismatches = _profile_mismatches(request.profile, render_profile)
  1026	                if mismatches:
  1027	                    reasons.append(
  1028	                        "requested profile is not produced by Remotion: "
  1029	                        + "; ".join(mismatches)
  1030	                    )
  1031	
  1032	    try:
  1033	        _validate_project_dir(settings.project_dir)
  1034	    except (FileNotFoundError, OSError) as exc:
  1035	        reasons.append(str(exc))
  1036	    for binary in ("node", "npx"):
  1037	        if shutil.which(binary) is None:
  1038	            reasons.append(f"required binary is unavailable: {binary}")
  1039	
  1040	    return SupportReport(
  1041	        schema_version=SCHEMA_VERSION,
  1042	        supported=not reasons,
  1043	        reasons=reasons,
  1044	        features=features,
  1045	        alternatives=[],
  1046	        backend=BACKEND_ID,
  1047	        backend_version=BACKEND_VERSION,
  1048	    )
  1049	
  1050	
  1051	def _duration_frames(video_path: Path, profile: RenderProfile) -> int:
  1052	    probe = ffprobe_metadata_strict(video_path)
  1053	    if probe.duration_rational is not None:
  1054	        duration = Fraction(*probe.duration_rational)
  1055	    elif probe.duration_seconds is not None:
  1056	        duration = Fraction(str(probe.duration_seconds))
  1057	    else:
  1058	        raise RuntimeError("ffprobe did not report a video duration")
  1059	    frames = duration * Fraction(*profile.fps_rational)
  1060	    return max(1, int(frames + Fraction(1, 2)))
  1060	    return max(1, int(frames + Fraction(1, 2)))
  1061	
  1062	
  1063	def _protocol_render(request: RenderRequest, *, workspace: Path) -> RenderResult:
  1064	    report = support(request, workspace=workspace)
  1065	    if not report.supported:
  1066	        raise_unsupported_error(
  1067	            backend=BACKEND_ID,
  1068	            message="Remotion does not support this render request",
  1069	            recovery_command="resolve the reported support reasons and retry",
  1070	            details={"reasons": report.reasons, "features": report.features},
  1071	        )
  1072	
  1073	    settings = _settings_from_request(request, workspace)
  1074	    timeline_path = _input_path(request.timeline_path, workspace)
  1075	    requested_assets_path = (
  1076	        _input_path(request.assets_registry_path, workspace)
  1077	        if request.assets_registry_path is not None
  1078	        else None
  1079	    )
  1080	    outputs_dir = workspace / "outputs"
  1081	    outputs_dir.mkdir(parents=True, exist_ok=True)
  1082	    output_path = outputs_dir / request.output_name
  1083	
  1084	    with ExitStack() as lifecycle:
  1085	        if requested_assets_path is None:
  1086	            empty_assets_tmp = lifecycle.enter_context(
  1087	                TemporaryDirectory(prefix=".remotion-empty-assets-", dir=str(workspace))
  1088	            )
  1089	            assets_path = Path(empty_assets_tmp) / "assets.json"
  1090	            timeline.save_registry({"assets": {}}, assets_path)
  1091	        else:
  1092	            assets_path = requested_assets_path
  1093	        assets_data = _load_registry_mapping(assets_path)
  1094	        canonical = _canonical_profile(timeline_path, assets_data, settings)
  1095	        declared_profile = request.profile or canonical
  1096	        # Remotion always muxes MP4 at the 90 kHz timescale regardless of the
  1097	        # input timeline's time base; the declared profile must match what the
  1098	        # renderer actually produces or strict validation rejects the output.
  1099	        declared_profile = replace(declared_profile, time_base=(1, 90000))
  1100	        # Remotion always muxes an audio track into its MP4 (silent when the
  1101	        # timeline has none), so ownership is effectively 'rendered' and the
  1102	        # declared profile must carry the AAC audio fields it always emits.
  1103	        ownership = AudioOwnership.RENDERED
  1104	        declared_profile = replace(
  1105	            declared_profile,
  1106	            audio_codec=declared_profile.audio_codec or "aac",
  1107	            audio_sample_rate=declared_profile.audio_sample_rate or 48000,
  1108	            audio_channel_layout=declared_profile.audio_channel_layout or "stereo",
  1109	        )
  1110	        private_tmp = lifecycle.enter_context(
  1111	            TemporaryDirectory(
  1112	                prefix=f".{request.output_name}.remotion-",
  1113	                dir=str(outputs_dir),
  1114	            )
  1115	        )
  1116	        staged_video = Path(private_tmp) / request.output_name
  1117	        details = _execute_remotion(
  1118	            timeline_path,
  1119	            assets_path,
  1120	            staged_video,
  1121	            provenance_out_path=output_path,
  1122	            project_dir=settings.project_dir,
  1123	            composition_id=settings.composition_id,
  1124	            theme_path=settings.theme_path,
  1125	            min_free_gb=settings.min_free_gb,
  1126	        )
  1127	        output_path.unlink(missing_ok=True)
  1128	        os.replace(staged_video, output_path)
  1129	
  1130	    try:
  1131	        provenance_v1 = _render_provenance_payload(
  1132	            output_path,
  1133	            engine="remotion",
  1134	            timeline_path=timeline_path,
  1135	            assets_path=requested_assets_path or assets_path,
  1136	            project_dir=settings.project_dir,
  1137	            composition_id=settings.composition_id,
  1138	            theme_path=settings.theme_path,
  1139	            active_theme=details.active_theme,
  1140	            registry_state=details.registry_state,
  1141	            stage_summary=details.stage_summary,
  1142	        )
  1143	        video = VideoArtifact.from_file(
  1144	            path=output_path,
  1145	            workspace_root=workspace,
  1146	            profile=declared_profile,
  1147	            duration_frames=_duration_frames(output_path, declared_profile),
  1148	            audio=ownership,
  1149	        )
  1150	        result = RenderResult(
  1151	            schema_version=SCHEMA_VERSION,
  1152	            video=video,
  1153	            audio_ownership=ownership,
  1154	            backend_fragments={
  1155	                BACKEND_ID: {
  1156	                    "renderer": "remotion",
  1157	                    "renderer_version": BACKEND_VERSION,
  1158	                    "composition": settings.composition_id,
  1159	                    "legacy_v1": provenance_v1,
  1160	                }
  1161	            },
  1162	            normalization=[],
  1163	            logs=[],
  1164	            metadata=request.metadata,
  1165	        )
  1166	        validate_render_result(
  1167	            result,
  1168	            expected_profile=declared_profile,
  1169	            workspace_root=workspace,
  1170	        )
  1171	        return result
  1172	    except BaseException:
  1173	        output_path.unlink(missing_ok=True)
  1174	        raise
  1175	
  1176	
  1177	def _load_request(path: Path) -> RenderRequest:
  1178	    payload = json.loads(path.read_text(encoding="utf-8"))
  1179	    if not isinstance(payload, Mapping):
  1180	        raise TypeError("render request must contain a JSON object")
  1181	    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)
  1182	
  1183	
  1184	def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
  1185	    if isinstance(exc, RendererException):
  1186	        error_kind = exc.error.kind
  1187	        message = exc.error.message
  1188	        recovery = exc.error.recovery_command
  1189	        details = exc.error.details
  1190	    else:
  1191	        error_kind = kind
  1192	        message = str(exc) or type(exc).__name__
  1193	        recovery = None
  1194	        details = {"error_type": type(exc).__name__}
  1195	    error = make_renderer_error(
  1196	        error_kind,
  1197	        backend=BACKEND_ID,
  1198	        message=message,
  1199	        recovery_command=recovery,
  1200	        details=details,
  1201	    )
  1202	    write_json_atomic(result_path, error.to_dict())
  1203	
  1204	
  1205	def main(argv: Sequence[str] | None = None) -> int:
  1206	    parser = argparse.ArgumentParser()
  1207	    parser.add_argument("verb", choices=("render", "support"))
  1208	    parser.add_argument("--request", type=Path, required=True)
  1209	    parser.add_argument("--result", type=Path, required=True)
  1210	    args = parser.parse_args(argv)
     1	schema_version: 1
     2	id: rendering.remotion
     3	name: Remotion Timeline Renderer
     4	version: 1.0.0
     5	protocol_version: 1
     6	command:
     7	  - python3
     8	  - run.py
     9	operations:
    10	  - render
    11	  - support
    12	description: Render complete Astrid timelines with TimelineComposition and Remotion.
    13	capabilities:
    14	  clip_types:
    15	    - media
    16	    - text
    17	  track_types:
    18	    - visual
    19	    - audio
    20	  features:
    21	    timeline_composition: true
    22	    merged_themes: true
    23	    effects: true
    24	    animations: true
    25	    transitions: true
    26	    html_in_canvas: true
    27	  supports_full_timeline: true
    28	  supports_windows: false
    29	  output_profiles:
    30	    - video/mp4
    31	  audio_ownership:
    32	    - rendered
    33	required_permissions:
    34	  - project_files
    35	  - subprocess
    36	required_binaries:
    37	  - node
    38	  - npx
    39	  - ffprobe

collab: Wait
exec
/bin/zsh -lc "rg -n -C 6 'video_profile|video_level|RenderProfile|profile fields|requested profile' docs astrid/packs/rendering -g '*.md' -g '*.json' -g '*.py' | head -n 500" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n -C 5 'duration_tolerance|time_base|fps_rational' docs/contracts docs/reference astrid/packs/rendering -g '*.md' -g '*.json' | head -n 500" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
docs/contracts/render-backend-v1.md-145-SDK serialization fills schema defaults and emits nullable values as JSON
docs/contracts/render-backend-v1.md-146-`null`.
docs/contracts/render-backend-v1.md-147-
docs/contracts/render-backend-v1.md-148-### Rational values and frame windows
docs/contracts/render-backend-v1.md-149-
docs/contracts/render-backend-v1.md:150:`fps_rational` and `time_base` are two-item JSON arrays `[numerator,
docs/contracts/render-backend-v1.md-151-denominator]` of positive integers. Decimal FPS is not authoritative. A
docs/contracts/render-backend-v1.md-152-`FrameWindow` is:
docs/contracts/render-backend-v1.md-153-
docs/contracts/render-backend-v1.md-154-```json
docs/contracts/render-backend-v1.md-155-{
docs/contracts/render-backend-v1.md-156-  "start_frame": 0,
docs/contracts/render-backend-v1.md-157-  "end_frame": 48,
docs/contracts/render-backend-v1.md:158:  "fps_rational": [24, 1],
docs/contracts/render-backend-v1.md-159-  "source_range": [0, 48],
docs/contracts/render-backend-v1.md-160-  "speed": 1.0
docs/contracts/render-backend-v1.md-161-}
docs/contracts/render-backend-v1.md-162-```
docs/contracts/render-backend-v1.md-163-
--
docs/contracts/render-backend-v1.md-172-
docs/contracts/render-backend-v1.md-173-A `RenderProfile` describes the media that must actually be probed, not merely
docs/contracts/render-backend-v1.md-174-the requested encoder flags:
docs/contracts/render-backend-v1.md-175-
docs/contracts/render-backend-v1.md-176-- positive `width` and `height`;
docs/contracts/render-backend-v1.md:177:- rational `fps_rational` and stream `time_base`;
docs/contracts/render-backend-v1.md-178-- non-empty `container`, `video_codec`, and `pixel_format`;
docs/contracts/render-backend-v1.md-179-- nullable `video_profile` and `video_level` when the codec does not expose
docs/contracts/render-backend-v1.md-180-  them;
docs/contracts/render-backend-v1.md-181-- the optional audio trio `audio_codec`, `audio_sample_rate`, and
docs/contracts/render-backend-v1.md-182-  `audio_channel_layout`, either all populated or all omitted/`null`;
docs/contracts/render-backend-v1.md:183:- `duration_tolerance`, a non-negative integer measured in **frames**.
docs/contracts/render-backend-v1.md-184-
docs/contracts/render-backend-v1.md-185-A visual-only profile omits all three audio fields or sets them all to `null`;
docs/contracts/render-backend-v1.md-186-canonical DTO output uses explicit nulls. One frame is the V1 default duration
docs/contracts/render-backend-v1.md-187-tolerance. This tolerance never changes window bounds; it only controls
docs/contracts/render-backend-v1.md-188-artifact acceptance.

 succeeded in 0ms:
astrid/packs/rendering/finalizers/ffmpeg/run.py-33-from astrid.core.foundation.atomic_io import write_json_atomic
astrid/packs/rendering/finalizers/ffmpeg/run.py-34-from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict
astrid/packs/rendering/finalizers/ffmpeg/run.py-35-from astrid.core.rendering.artifacts import validate_render_result
astrid/packs/rendering/finalizers/ffmpeg/run.py-36-from astrid.core.rendering.contracts import (
astrid/packs/rendering/finalizers/ffmpeg/run.py-37-    AudioOwnership,
astrid/packs/rendering/finalizers/ffmpeg/run.py-38-    FinalizeRequest,
astrid/packs/rendering/finalizers/ffmpeg/run.py:39:    RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-40-    RenderRequest,
astrid/packs/rendering/finalizers/ffmpeg/run.py-41-    RenderResult,
astrid/packs/rendering/finalizers/ffmpeg/run.py-42-    SCHEMA_VERSION,
astrid/packs/rendering/finalizers/ffmpeg/run.py-43-    SupportReport,
astrid/packs/rendering/finalizers/ffmpeg/run.py-44-    VideoArtifact,
astrid/packs/rendering/finalizers/ffmpeg/run.py-45-)
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-58-    {
astrid/packs/rendering/finalizers/ffmpeg/run.py-59-        "width",
astrid/packs/rendering/finalizers/ffmpeg/run.py-60-        "height",
astrid/packs/rendering/finalizers/ffmpeg/run.py-61-        "fps_rational",
astrid/packs/rendering/finalizers/ffmpeg/run.py-62-        "time_base",
astrid/packs/rendering/finalizers/ffmpeg/run.py-63-        "video_codec",
astrid/packs/rendering/finalizers/ffmpeg/run.py:64:        "video_profile",
astrid/packs/rendering/finalizers/ffmpeg/run.py:65:        "video_level",
astrid/packs/rendering/finalizers/ffmpeg/run.py-66-        "pixel_format",
astrid/packs/rendering/finalizers/ffmpeg/run.py-67-    }
astrid/packs/rendering/finalizers/ffmpeg/run.py-68-)
astrid/packs/rendering/finalizers/ffmpeg/run.py-69-_AUDIO_TRANSCODE_FIELDS = frozenset(
astrid/packs/rendering/finalizers/ffmpeg/run.py-70-    {
astrid/packs/rendering/finalizers/ffmpeg/run.py-71-        "audio_presence",
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-88-
astrid/packs/rendering/finalizers/ffmpeg/run.py-89-
astrid/packs/rendering/finalizers/ffmpeg/run.py-90-@dataclass(frozen=True)
astrid/packs/rendering/finalizers/ffmpeg/run.py-91-class _PreparedSegment:
astrid/packs/rendering/finalizers/ffmpeg/run.py-92-    index: int
astrid/packs/rendering/finalizers/ffmpeg/run.py-93-    path: Path
astrid/packs/rendering/finalizers/ffmpeg/run.py:94:    profile: RenderProfile
astrid/packs/rendering/finalizers/ffmpeg/run.py-95-    audio: AudioOwnership
astrid/packs/rendering/finalizers/ffmpeg/run.py-96-    duration_frames: int
astrid/packs/rendering/finalizers/ffmpeg/run.py-97-
astrid/packs/rendering/finalizers/ffmpeg/run.py-98-
astrid/packs/rendering/finalizers/ffmpeg/run.py-99-@dataclass(frozen=True)
astrid/packs/rendering/finalizers/ffmpeg/run.py-100-class _ProfileDifference:
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-165-            recovery_command="choose an unused portable output name",
astrid/packs/rendering/finalizers/ffmpeg/run.py-166-            details={"output": output_name},
astrid/packs/rendering/finalizers/ffmpeg/run.py-167-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-168-    return candidate
astrid/packs/rendering/finalizers/ffmpeg/run.py-169-
astrid/packs/rendering/finalizers/ffmpeg/run.py-170-
astrid/packs/rendering/finalizers/ffmpeg/run.py:171:def _profile_without_audio(profile: RenderProfile) -> RenderProfile:
astrid/packs/rendering/finalizers/ffmpeg/run.py:172:    return RenderProfile(
astrid/packs/rendering/finalizers/ffmpeg/run.py-173-        width=profile.width,
astrid/packs/rendering/finalizers/ffmpeg/run.py-174-        height=profile.height,
astrid/packs/rendering/finalizers/ffmpeg/run.py-175-        fps_rational=profile.fps_rational,
astrid/packs/rendering/finalizers/ffmpeg/run.py-176-        time_base=profile.time_base,
astrid/packs/rendering/finalizers/ffmpeg/run.py-177-        container=profile.container,
astrid/packs/rendering/finalizers/ffmpeg/run.py-178-        video_codec=profile.video_codec,
astrid/packs/rendering/finalizers/ffmpeg/run.py:179:        video_profile=profile.video_profile,
astrid/packs/rendering/finalizers/ffmpeg/run.py:180:        video_level=profile.video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-181-        pixel_format=profile.pixel_format,
astrid/packs/rendering/finalizers/ffmpeg/run.py-182-        audio_codec=None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-183-        audio_sample_rate=None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-184-        audio_channel_layout=None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-185-        duration_tolerance=profile.duration_tolerance,
astrid/packs/rendering/finalizers/ffmpeg/run.py-186-    )
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-217-) -> bool:
astrid/packs/rendering/finalizers/ffmpeg/run.py-218-    if field in {"fps_rational", "time_base"}:
astrid/packs/rendering/finalizers/ffmpeg/run.py-219-        try:
astrid/packs/rendering/finalizers/ffmpeg/run.py-220-            return Fraction(*actual) == Fraction(*expected)
astrid/packs/rendering/finalizers/ffmpeg/run.py-221-        except (TypeError, ValueError, ZeroDivisionError):
astrid/packs/rendering/finalizers/ffmpeg/run.py-222-            return False
astrid/packs/rendering/finalizers/ffmpeg/run.py:223:    if field == "video_level":
astrid/packs/rendering/finalizers/ffmpeg/run.py-224-        return _level(actual, codec=codec) == _level(expected, codec=codec)
astrid/packs/rendering/finalizers/ffmpeg/run.py-225-    if field in {
astrid/packs/rendering/finalizers/ffmpeg/run.py-226-        "container",
astrid/packs/rendering/finalizers/ffmpeg/run.py-227-        "video_codec",
astrid/packs/rendering/finalizers/ffmpeg/run.py:228:        "video_profile",
astrid/packs/rendering/finalizers/ffmpeg/run.py-229-        "pixel_format",
astrid/packs/rendering/finalizers/ffmpeg/run.py-230-        "audio_codec",
astrid/packs/rendering/finalizers/ffmpeg/run.py-231-        "audio_channel_layout",
astrid/packs/rendering/finalizers/ffmpeg/run.py-232-    }:
astrid/packs/rendering/finalizers/ffmpeg/run.py-233-        return _text(actual) == _text(expected)
astrid/packs/rendering/finalizers/ffmpeg/run.py-234-    return actual == expected
astrid/packs/rendering/finalizers/ffmpeg/run.py-235-
astrid/packs/rendering/finalizers/ffmpeg/run.py-236-
astrid/packs/rendering/finalizers/ffmpeg/run.py-237-def _profile_differences(
astrid/packs/rendering/finalizers/ffmpeg/run.py:238:    actual: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py:239:    expected: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-240-) -> list[_ProfileDifference]:
astrid/packs/rendering/finalizers/ffmpeg/run.py-241-    differences: list[_ProfileDifference] = []
astrid/packs/rendering/finalizers/ffmpeg/run.py-242-    for field in (
astrid/packs/rendering/finalizers/ffmpeg/run.py-243-        "width",
astrid/packs/rendering/finalizers/ffmpeg/run.py-244-        "height",
astrid/packs/rendering/finalizers/ffmpeg/run.py-245-        "fps_rational",
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-252-        expected_value = getattr(expected, field)
astrid/packs/rendering/finalizers/ffmpeg/run.py-253-        if not _same_value(field, actual_value, expected_value):
astrid/packs/rendering/finalizers/ffmpeg/run.py-254-            differences.append(_ProfileDifference(field, actual_value, expected_value))
astrid/packs/rendering/finalizers/ffmpeg/run.py-255-
astrid/packs/rendering/finalizers/ffmpeg/run.py-256-    # Null profile/level values are deliberately unconstrained in the V1
astrid/packs/rendering/finalizers/ffmpeg/run.py-257-    # artifact contract.  A concrete canonical value, however, must match.
astrid/packs/rendering/finalizers/ffmpeg/run.py:258:    for field in ("video_profile", "video_level"):
astrid/packs/rendering/finalizers/ffmpeg/run.py-259-        expected_value = getattr(expected, field)
astrid/packs/rendering/finalizers/ffmpeg/run.py-260-        actual_value = getattr(actual, field)
astrid/packs/rendering/finalizers/ffmpeg/run.py-261-        if expected_value is not None and not _same_value(
astrid/packs/rendering/finalizers/ffmpeg/run.py-262-            field,
astrid/packs/rendering/finalizers/ffmpeg/run.py-263-            actual_value,
astrid/packs/rendering/finalizers/ffmpeg/run.py-264-            expected_value,
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-287-                    _ProfileDifference(field, actual_value, expected_value)
astrid/packs/rendering/finalizers/ffmpeg/run.py-288-                )
astrid/packs/rendering/finalizers/ffmpeg/run.py-289-    return differences
astrid/packs/rendering/finalizers/ffmpeg/run.py-290-
astrid/packs/rendering/finalizers/ffmpeg/run.py-291-
astrid/packs/rendering/finalizers/ffmpeg/run.py-292-def _assembly_profile(
astrid/packs/rendering/finalizers/ffmpeg/run.py:293:    canonical: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-294-    segments: Sequence[_PreparedSegment],
astrid/packs/rendering/finalizers/ffmpeg/run.py:295:) -> RenderProfile:
astrid/packs/rendering/finalizers/ffmpeg/run.py-296-    """Refine optional H.26x fields so concat inputs share stream metadata."""
astrid/packs/rendering/finalizers/ffmpeg/run.py-297-
astrid/packs/rendering/finalizers/ffmpeg/run.py-298-    eligible = [
astrid/packs/rendering/finalizers/ffmpeg/run.py-299-        segment
astrid/packs/rendering/finalizers/ffmpeg/run.py-300-        for segment in segments
astrid/packs/rendering/finalizers/ffmpeg/run.py-301-        if not any(
astrid/packs/rendering/finalizers/ffmpeg/run.py-302-            difference.field in _PROFILE_ANCHOR_BLOCKERS
astrid/packs/rendering/finalizers/ffmpeg/run.py-303-            for difference in _profile_differences(segment.profile, canonical)
astrid/packs/rendering/finalizers/ffmpeg/run.py-304-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-305-    ]
astrid/packs/rendering/finalizers/ffmpeg/run.py:306:    video_profile = canonical.video_profile
astrid/packs/rendering/finalizers/ffmpeg/run.py:307:    video_level = canonical.video_level
astrid/packs/rendering/finalizers/ffmpeg/run.py:308:    if video_profile is None:
astrid/packs/rendering/finalizers/ffmpeg/run.py:309:        video_profile = next(
astrid/packs/rendering/finalizers/ffmpeg/run.py-310-            (
astrid/packs/rendering/finalizers/ffmpeg/run.py:311:                segment.profile.video_profile
astrid/packs/rendering/finalizers/ffmpeg/run.py-312-                for segment in eligible
astrid/packs/rendering/finalizers/ffmpeg/run.py:313:                if segment.profile.video_profile is not None
astrid/packs/rendering/finalizers/ffmpeg/run.py-314-            ),
astrid/packs/rendering/finalizers/ffmpeg/run.py-315-            None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-316-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py:317:    if video_level is None:
astrid/packs/rendering/finalizers/ffmpeg/run.py:318:        video_level = next(
astrid/packs/rendering/finalizers/ffmpeg/run.py-319-            (
astrid/packs/rendering/finalizers/ffmpeg/run.py:320:                segment.profile.video_level
astrid/packs/rendering/finalizers/ffmpeg/run.py-321-                for segment in eligible
astrid/packs/rendering/finalizers/ffmpeg/run.py:322:                if segment.profile.video_level is not None
astrid/packs/rendering/finalizers/ffmpeg/run.py-323-            ),
astrid/packs/rendering/finalizers/ffmpeg/run.py-324-            None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-325-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-326-    if (
astrid/packs/rendering/finalizers/ffmpeg/run.py:327:        video_profile == canonical.video_profile
astrid/packs/rendering/finalizers/ffmpeg/run.py:328:        and video_level == canonical.video_level
astrid/packs/rendering/finalizers/ffmpeg/run.py-329-    ):
astrid/packs/rendering/finalizers/ffmpeg/run.py-330-        return canonical
astrid/packs/rendering/finalizers/ffmpeg/run.py-331-    return replace(
astrid/packs/rendering/finalizers/ffmpeg/run.py-332-        canonical,
astrid/packs/rendering/finalizers/ffmpeg/run.py:333:        video_profile=video_profile,
astrid/packs/rendering/finalizers/ffmpeg/run.py:334:        video_level=video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-335-    )
astrid/packs/rendering/finalizers/ffmpeg/run.py-336-
astrid/packs/rendering/finalizers/ffmpeg/run.py-337-
astrid/packs/rendering/finalizers/ffmpeg/run.py-338-def _format_value(value: Any) -> str:
astrid/packs/rendering/finalizers/ffmpeg/run.py-339-    if isinstance(value, tuple) and len(value) == 2:
astrid/packs/rendering/finalizers/ffmpeg/run.py-340-        return f"{value[0]}/{value[1]}"
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-412-            backend=BACKEND_ID,
astrid/packs/rendering/finalizers/ffmpeg/run.py-413-            message=(
astrid/packs/rendering/finalizers/ffmpeg/run.py-414-                f"unsupported {codec} encoder profile for FFmpeg finalization: "
astrid/packs/rendering/finalizers/ffmpeg/run.py-415-                f"{profile}"
astrid/packs/rendering/finalizers/ffmpeg/run.py-416-            ),
astrid/packs/rendering/finalizers/ffmpeg/run.py-417-            recovery_command="select a supported canonical video profile",
astrid/packs/rendering/finalizers/ffmpeg/run.py:418:            details={"video_codec": codec, "video_profile": profile},
astrid/packs/rendering/finalizers/ffmpeg/run.py-419-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-420-    return encoded
astrid/packs/rendering/finalizers/ffmpeg/run.py-421-
astrid/packs/rendering/finalizers/ffmpeg/run.py-422-
astrid/packs/rendering/finalizers/ffmpeg/run.py-423-def _audio_encoder(codec: str) -> str:
astrid/packs/rendering/finalizers/ffmpeg/run.py-424-    normalized = _text(codec)
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-438-            recovery_command="select an FFmpeg-encodable canonical audio profile",
astrid/packs/rendering/finalizers/ffmpeg/run.py-439-            details={"audio_codec": codec},
astrid/packs/rendering/finalizers/ffmpeg/run.py-440-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-441-    return encoders[normalized]
astrid/packs/rendering/finalizers/ffmpeg/run.py-442-
astrid/packs/rendering/finalizers/ffmpeg/run.py-443-
astrid/packs/rendering/finalizers/ffmpeg/run.py:444:def _mp4_timescale(profile: RenderProfile) -> int:
astrid/packs/rendering/finalizers/ffmpeg/run.py-445-    time_base = Fraction(*profile.time_base)
astrid/packs/rendering/finalizers/ffmpeg/run.py-446-    reciprocal = 1 / time_base
astrid/packs/rendering/finalizers/ffmpeg/run.py-447-    if reciprocal.denominator != 1:
astrid/packs/rendering/finalizers/ffmpeg/run.py-448-        raise_unsupported_error(
astrid/packs/rendering/finalizers/ffmpeg/run.py-449-            backend=BACKEND_ID,
astrid/packs/rendering/finalizers/ffmpeg/run.py-450-            message=(
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-454-            recovery_command="resolve the canonical MP4 profile with Astrid's profile resolver",
astrid/packs/rendering/finalizers/ffmpeg/run.py-455-            details={"time_base": list(profile.time_base)},
astrid/packs/rendering/finalizers/ffmpeg/run.py-456-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-457-    return reciprocal.numerator
astrid/packs/rendering/finalizers/ffmpeg/run.py-458-
astrid/packs/rendering/finalizers/ffmpeg/run.py-459-
astrid/packs/rendering/finalizers/ffmpeg/run.py:460:def _validate_target_profile(profile: RenderProfile) -> None:
astrid/packs/rendering/finalizers/ffmpeg/run.py-461-    if _text(profile.container) != "mp4":
astrid/packs/rendering/finalizers/ffmpeg/run.py-462-        raise_unsupported_error(
astrid/packs/rendering/finalizers/ffmpeg/run.py-463-            backend=BACKEND_ID,
astrid/packs/rendering/finalizers/ffmpeg/run.py-464-            message=f"FFmpeg finalizer supports canonical MP4 output, not {profile.container!r}",
astrid/packs/rendering/finalizers/ffmpeg/run.py-465-            recovery_command="select a finalizer supporting the canonical container",
astrid/packs/rendering/finalizers/ffmpeg/run.py-466-            details={"container": profile.container},
astrid/packs/rendering/finalizers/ffmpeg/run.py-467-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-468-    _video_encoder(profile.video_codec)
astrid/packs/rendering/finalizers/ffmpeg/run.py:469:    if profile.video_profile is not None:
astrid/packs/rendering/finalizers/ffmpeg/run.py:470:        _encoder_profile(profile.video_codec, profile.video_profile)
astrid/packs/rendering/finalizers/ffmpeg/run.py:471:    if profile.video_level is not None:
astrid/packs/rendering/finalizers/ffmpeg/run.py-472-        normalized_level = _level(
astrid/packs/rendering/finalizers/ffmpeg/run.py:473:            profile.video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-474-            codec=profile.video_codec,
astrid/packs/rendering/finalizers/ffmpeg/run.py-475-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py-476-        if (
astrid/packs/rendering/finalizers/ffmpeg/run.py-477-            _text(profile.video_codec) not in {"h264", "hevc"}
astrid/packs/rendering/finalizers/ffmpeg/run.py-478-            or normalized_level is None
astrid/packs/rendering/finalizers/ffmpeg/run.py-479-            or re.fullmatch(r"[1-9][0-9]*(?:\.[0-9]+)?", normalized_level) is None
astrid/packs/rendering/finalizers/ffmpeg/run.py-480-        ):
astrid/packs/rendering/finalizers/ffmpeg/run.py-481-            raise_unsupported_error(
astrid/packs/rendering/finalizers/ffmpeg/run.py-482-                backend=BACKEND_ID,
astrid/packs/rendering/finalizers/ffmpeg/run.py-483-                message=(
astrid/packs/rendering/finalizers/ffmpeg/run.py-484-                    "unsupported encoder level for FFmpeg finalization: "
astrid/packs/rendering/finalizers/ffmpeg/run.py:485:                    f"{profile.video_level}"
astrid/packs/rendering/finalizers/ffmpeg/run.py-486-                ),
astrid/packs/rendering/finalizers/ffmpeg/run.py-487-                recovery_command="select a supported canonical video level",
astrid/packs/rendering/finalizers/ffmpeg/run.py-488-                details={
astrid/packs/rendering/finalizers/ffmpeg/run.py-489-                    "video_codec": profile.video_codec,
astrid/packs/rendering/finalizers/ffmpeg/run.py:490:                    "video_level": profile.video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-491-                },
astrid/packs/rendering/finalizers/ffmpeg/run.py-492-            )
astrid/packs/rendering/finalizers/ffmpeg/run.py-493-    if profile.has_audio:
astrid/packs/rendering/finalizers/ffmpeg/run.py-494-        assert profile.audio_codec is not None
astrid/packs/rendering/finalizers/ffmpeg/run.py-495-        _audio_encoder(profile.audio_codec)
astrid/packs/rendering/finalizers/ffmpeg/run.py-496-    _mp4_timescale(profile)
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-500-
astrid/packs/rendering/finalizers/ffmpeg/run.py-501-
astrid/packs/rendering/finalizers/ffmpeg/run.py-502-def build_normalize_command(
astrid/packs/rendering/finalizers/ffmpeg/run.py-503-    segment: _PreparedSegment,
astrid/packs/rendering/finalizers/ffmpeg/run.py-504-    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py-505-    *,
astrid/packs/rendering/finalizers/ffmpeg/run.py:506:    target_profile: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-507-    differences: Sequence[_ProfileDifference],
astrid/packs/rendering/finalizers/ffmpeg/run.py-508-    faststart: bool,
astrid/packs/rendering/finalizers/ffmpeg/run.py-509-) -> list[str]:
astrid/packs/rendering/finalizers/ffmpeg/run.py-510-    """Build one segment-normalization command without touching the filesystem."""
astrid/packs/rendering/finalizers/ffmpeg/run.py-511-
astrid/packs/rendering/finalizers/ffmpeg/run.py-512-    fields = {difference.field for difference in differences}
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-562-            filters.append(f"format={target_profile.pixel_format}")
astrid/packs/rendering/finalizers/ffmpeg/run.py-563-        argv.extend(["-vf", ",".join(filters)])
astrid/packs/rendering/finalizers/ffmpeg/run.py-564-        encoder = _video_encoder(target_profile.video_codec)
astrid/packs/rendering/finalizers/ffmpeg/run.py-565-        argv.extend(["-c:v", encoder, "-r:v", fps, "-fps_mode", "cfr"])
astrid/packs/rendering/finalizers/ffmpeg/run.py-566-        if encoder in {"libx264", "libx265"}:
astrid/packs/rendering/finalizers/ffmpeg/run.py-567-            argv.extend(["-preset", "veryfast", "-crf", "20"])
astrid/packs/rendering/finalizers/ffmpeg/run.py:568:        if target_profile.video_profile is not None:
astrid/packs/rendering/finalizers/ffmpeg/run.py-569-            argv.extend(
astrid/packs/rendering/finalizers/ffmpeg/run.py-570-                [
astrid/packs/rendering/finalizers/ffmpeg/run.py-571-                    "-profile:v",
astrid/packs/rendering/finalizers/ffmpeg/run.py-572-                    _encoder_profile(
astrid/packs/rendering/finalizers/ffmpeg/run.py-573-                        target_profile.video_codec,
astrid/packs/rendering/finalizers/ffmpeg/run.py:574:                        target_profile.video_profile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-575-                    ),
astrid/packs/rendering/finalizers/ffmpeg/run.py-576-                ]
astrid/packs/rendering/finalizers/ffmpeg/run.py-577-            )
astrid/packs/rendering/finalizers/ffmpeg/run.py:578:        if target_profile.video_level is not None:
astrid/packs/rendering/finalizers/ffmpeg/run.py-579-            argv.extend(
astrid/packs/rendering/finalizers/ffmpeg/run.py-580-                [
astrid/packs/rendering/finalizers/ffmpeg/run.py-581-                    "-level:v",
astrid/packs/rendering/finalizers/ffmpeg/run.py-582-                    _level(
astrid/packs/rendering/finalizers/ffmpeg/run.py:583:                        target_profile.video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-584-                        codec=target_profile.video_codec,
astrid/packs/rendering/finalizers/ffmpeg/run.py-585-                    )
astrid/packs/rendering/finalizers/ffmpeg/run.py:586:                    or target_profile.video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-587-                ]
astrid/packs/rendering/finalizers/ffmpeg/run.py-588-            )
astrid/packs/rendering/finalizers/ffmpeg/run.py-589-        argv.extend(["-pix_fmt", target_profile.pixel_format])
astrid/packs/rendering/finalizers/ffmpeg/run.py-590-    else:
astrid/packs/rendering/finalizers/ffmpeg/run.py-591-        argv.extend(["-c:v", "copy"])
astrid/packs/rendering/finalizers/ffmpeg/run.py-592-
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-630-
astrid/packs/rendering/finalizers/ffmpeg/run.py-631-
astrid/packs/rendering/finalizers/ffmpeg/run.py-632-def build_concat_command(
astrid/packs/rendering/finalizers/ffmpeg/run.py-633-    list_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py-634-    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py-635-    *,
astrid/packs/rendering/finalizers/ffmpeg/run.py:636:    target_profile: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-637-    faststart: bool,
astrid/packs/rendering/finalizers/ffmpeg/run.py-638-) -> list[str]:
astrid/packs/rendering/finalizers/ffmpeg/run.py-639-    """Build the final concat-demuxer stream-copy command."""
astrid/packs/rendering/finalizers/ffmpeg/run.py-640-
astrid/packs/rendering/finalizers/ffmpeg/run.py-641-    argv = [
astrid/packs/rendering/finalizers/ffmpeg/run.py-642-        "ffmpeg",
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-684-
astrid/packs/rendering/finalizers/ffmpeg/run.py-685-
astrid/packs/rendering/finalizers/ffmpeg/run.py-686-def _assemble_prepared_segments(
astrid/packs/rendering/finalizers/ffmpeg/run.py-687-    segments: Sequence[_PreparedSegment],
astrid/packs/rendering/finalizers/ffmpeg/run.py-688-    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py-689-    *,
astrid/packs/rendering/finalizers/ffmpeg/run.py:690:    target_profile: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py-691-    faststart: bool,
astrid/packs/rendering/finalizers/ffmpeg/run.py-692-    runner: Runner,
astrid/packs/rendering/finalizers/ffmpeg/run.py-693-) -> list[str]:
astrid/packs/rendering/finalizers/ffmpeg/run.py-694-    """Normalize incompatible segments and atomically assemble the output."""
astrid/packs/rendering/finalizers/ffmpeg/run.py-695-
astrid/packs/rendering/finalizers/ffmpeg/run.py-696-    if not segments:
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-804-
astrid/packs/rendering/finalizers/ffmpeg/run.py-805-def _profile_from_probe(
astrid/packs/rendering/finalizers/ffmpeg/run.py-806-    probe: MediaProbe,
astrid/packs/rendering/finalizers/ffmpeg/run.py-807-    *,
astrid/packs/rendering/finalizers/ffmpeg/run.py-808-    ownership: AudioOwnership,
astrid/packs/rendering/finalizers/ffmpeg/run.py-809-    duration_tolerance: int,
astrid/packs/rendering/finalizers/ffmpeg/run.py:810:) -> RenderProfile:
astrid/packs/rendering/finalizers/ffmpeg/run.py-811-    if not probe.has_video_stream:
astrid/packs/rendering/finalizers/ffmpeg/run.py-812-        raise MediaProbeError("media has no video stream")
astrid/packs/rendering/finalizers/ffmpeg/run.py-813-    if ownership is AudioOwnership.RENDERED and not probe.has_audio_stream:
astrid/packs/rendering/finalizers/ffmpeg/run.py-814-        raise MediaProbeError("media has no required audio stream")
astrid/packs/rendering/finalizers/ffmpeg/run.py-815-    if ownership is not AudioOwnership.RENDERED and probe.has_audio_stream:
astrid/packs/rendering/finalizers/ffmpeg/run.py-816-        raise MediaProbeError(
astrid/packs/rendering/finalizers/ffmpeg/run.py-817-            f"visual-only {ownership.value} media unexpectedly contains audio"
astrid/packs/rendering/finalizers/ffmpeg/run.py-818-        )
astrid/packs/rendering/finalizers/ffmpeg/run.py:819:    return RenderProfile(
astrid/packs/rendering/finalizers/ffmpeg/run.py-820-        width=_required_probe_value(probe.width, "video width"),
astrid/packs/rendering/finalizers/ffmpeg/run.py-821-        height=_required_probe_value(probe.height, "video height"),
astrid/packs/rendering/finalizers/ffmpeg/run.py-822-        fps_rational=_required_probe_value(probe.fps_rational, "video frame rate"),
astrid/packs/rendering/finalizers/ffmpeg/run.py-823-        time_base=_required_probe_value(probe.time_base, "video time base"),
astrid/packs/rendering/finalizers/ffmpeg/run.py-824-        container=_required_probe_value(probe.container, "container"),
astrid/packs/rendering/finalizers/ffmpeg/run.py-825-        video_codec=_required_probe_value(probe.video_codec, "video codec"),
astrid/packs/rendering/finalizers/ffmpeg/run.py:826:        video_profile=probe.video_profile,
astrid/packs/rendering/finalizers/ffmpeg/run.py:827:        video_level=probe.video_level,
astrid/packs/rendering/finalizers/ffmpeg/run.py-828-        pixel_format=_required_probe_value(probe.pixel_format, "pixel format"),
astrid/packs/rendering/finalizers/ffmpeg/run.py-829-        audio_codec=(
astrid/packs/rendering/finalizers/ffmpeg/run.py-830-            _required_probe_value(probe.audio_codec, "audio codec")
astrid/packs/rendering/finalizers/ffmpeg/run.py-831-            if ownership is AudioOwnership.RENDERED
astrid/packs/rendering/finalizers/ffmpeg/run.py-832-            else None
astrid/packs/rendering/finalizers/ffmpeg/run.py-833-        ),
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-842-            else None
astrid/packs/rendering/finalizers/ffmpeg/run.py-843-        ),
astrid/packs/rendering/finalizers/ffmpeg/run.py-844-        duration_tolerance=duration_tolerance,
astrid/packs/rendering/finalizers/ffmpeg/run.py-845-    )
astrid/packs/rendering/finalizers/ffmpeg/run.py-846-
astrid/packs/rendering/finalizers/ffmpeg/run.py-847-
astrid/packs/rendering/finalizers/ffmpeg/run.py:848:def _duration_frames_from_probe(probe: MediaProbe, profile: RenderProfile) -> int:
astrid/packs/rendering/finalizers/ffmpeg/run.py-849-    frames = _duration_fraction(probe) * Fraction(*profile.fps_rational)
astrid/packs/rendering/finalizers/ffmpeg/run.py-850-    return max(1, int(frames + Fraction(1, 2)))
astrid/packs/rendering/finalizers/ffmpeg/run.py-851-
astrid/packs/rendering/finalizers/ffmpeg/run.py-852-
astrid/packs/rendering/finalizers/ffmpeg/run.py-853-def concat_segment_files(
astrid/packs/rendering/finalizers/ffmpeg/run.py-854-    segment_paths: Sequence[Path],
astrid/packs/rendering/finalizers/ffmpeg/run.py-855-    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py-856-    *,
astrid/packs/rendering/finalizers/ffmpeg/run.py:857:    profile: RenderProfile | None = None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-858-    audio: AudioOwnership | str | None = None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-859-    faststart: bool = True,
astrid/packs/rendering/finalizers/ffmpeg/run.py-860-    runner: Runner | None = None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-861-    probe: Probe | None = None,
astrid/packs/rendering/finalizers/ffmpeg/run.py-862-) -> list[str]:
astrid/packs/rendering/finalizers/ffmpeg/run.py-863-    """Strictly probe and assemble explicit files for the legacy facade.
--
astrid/packs/rendering/finalizers/ffmpeg/run.py-1143-    return prepared
astrid/packs/rendering/finalizers/ffmpeg/run.py-1144-
astrid/packs/rendering/finalizers/ffmpeg/run.py-1145-
astrid/packs/rendering/finalizers/ffmpeg/run.py-1146-def _probe_normalized_segments(
astrid/packs/rendering/finalizers/ffmpeg/run.py-1147-    prepared: Sequence[_PreparedSegment],
astrid/packs/rendering/finalizers/ffmpeg/run.py-1148-    *,
astrid/packs/rendering/finalizers/ffmpeg/run.py:1149:    target_profile: RenderProfile,
astrid/packs/rendering/finalizers/ffmpeg/run.py:1150:) -> RenderProfile:
astrid/packs/rendering/finalizers/ffmpeg/run.py-1151-    """Strictly probe every normalized segment before final assembly."""
astrid/packs/rendering/finalizers/ffmpeg/run.py-1152-
astrid/packs/rendering/finalizers/ffmpeg/run.py-1153-    probed: list[_PreparedSegment] = []
astrid/packs/rendering/finalizers/ffmpeg/run.py-1154-    for segment in prepared:
astrid/packs/rendering/finalizers/ffmpeg/run.py-1155-        try:
astrid/packs/rendering/finalizers/ffmpeg/run.py-1156-            probe = ffprobe_metadata_strict(segment.path)
--
astrid/packs/rendering/backends/remotion/run.py-44-    AssetMaterializer,
astrid/packs/rendering/backends/remotion/run.py-45-    InvocationAssetServer,
astrid/packs/rendering/backends/remotion/run.py-46-    RangeHTTPRequestHandler as _RangeHTTPRequestHandler,
astrid/packs/rendering/backends/remotion/run.py-47-)
astrid/packs/rendering/backends/remotion/run.py-48-from astrid.core.rendering.contracts import (
astrid/packs/rendering/backends/remotion/run.py-49-    AudioOwnership,
astrid/packs/rendering/backends/remotion/run.py:50:    RenderProfile,
astrid/packs/rendering/backends/remotion/run.py-51-    RenderRequest,
astrid/packs/rendering/backends/remotion/run.py-52-    RenderResult,
astrid/packs/rendering/backends/remotion/run.py-53-    SCHEMA_VERSION,
astrid/packs/rendering/backends/remotion/run.py-54-    SupportReport,
astrid/packs/rendering/backends/remotion/run.py-55-    VideoArtifact,
astrid/packs/rendering/backends/remotion/run.py-56-)
--
astrid/packs/rendering/backends/remotion/run.py-885-
astrid/packs/rendering/backends/remotion/run.py-886-
astrid/packs/rendering/backends/remotion/run.py-887-def _canonical_profile(
astrid/packs/rendering/backends/remotion/run.py-888-    timeline_path: Path,
astrid/packs/rendering/backends/remotion/run.py-889-    assets_data: Mapping[str, Any],
astrid/packs/rendering/backends/remotion/run.py-890-    settings: _RenderSettings,
astrid/packs/rendering/backends/remotion/run.py:891:) -> RenderProfile:
astrid/packs/rendering/backends/remotion/run.py-892-    fallback_theme = settings.theme_path or (
astrid/packs/rendering/backends/remotion/run.py-893-        WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
astrid/packs/rendering/backends/remotion/run.py-894-    )
astrid/packs/rendering/backends/remotion/run.py-895-    active_theme = _resolved_theme_for_render(timeline_path, fallback_theme)
astrid/packs/rendering/backends/remotion/run.py-896-    return resolve_render_profile(
astrid/packs/rendering/backends/remotion/run.py-897-        timeline_path,
--
astrid/packs/rendering/backends/remotion/run.py-899-        theme=active_theme,
astrid/packs/rendering/backends/remotion/run.py-900-        themes_root=REPO_ROOT / "themes",
astrid/packs/rendering/backends/remotion/run.py-901-    )
astrid/packs/rendering/backends/remotion/run.py-902-
astrid/packs/rendering/backends/remotion/run.py-903-
astrid/packs/rendering/backends/remotion/run.py-904-def _profile_mismatches(
astrid/packs/rendering/backends/remotion/run.py:905:    requested: RenderProfile,
astrid/packs/rendering/backends/remotion/run.py:906:    canonical: RenderProfile,
astrid/packs/rendering/backends/remotion/run.py-907-) -> list[str]:
astrid/packs/rendering/backends/remotion/run.py-908-    requested_data = requested.to_dict()
astrid/packs/rendering/backends/remotion/run.py-909-    canonical_data = canonical.to_dict()
astrid/packs/rendering/backends/remotion/run.py-910-    mismatches: list[str] = []
astrid/packs/rendering/backends/remotion/run.py-911-    for field, expected in canonical_data.items():
astrid/packs/rendering/backends/remotion/run.py-912-        if field == "duration_tolerance":
--
astrid/packs/rendering/backends/remotion/run.py-1022-                    audio_sample_rate=canonical.audio_sample_rate or 48000,
astrid/packs/rendering/backends/remotion/run.py-1023-                    audio_channel_layout=canonical.audio_channel_layout or "stereo",
astrid/packs/rendering/backends/remotion/run.py-1024-                )
astrid/packs/rendering/backends/remotion/run.py-1025-                mismatches = _profile_mismatches(request.profile, render_profile)
astrid/packs/rendering/backends/remotion/run.py-1026-                if mismatches:
astrid/packs/rendering/backends/remotion/run.py-1027-                    reasons.append(
astrid/packs/rendering/backends/remotion/run.py:1028:                        "requested profile is not produced by Remotion: "
astrid/packs/rendering/backends/remotion/run.py-1029-                        + "; ".join(mismatches)
astrid/packs/rendering/backends/remotion/run.py-1030-                    )
astrid/packs/rendering/backends/remotion/run.py-1031-
astrid/packs/rendering/backends/remotion/run.py-1032-    try:
astrid/packs/rendering/backends/remotion/run.py-1033-        _validate_project_dir(settings.project_dir)
astrid/packs/rendering/backends/remotion/run.py-1034-    except (FileNotFoundError, OSError) as exc:
--
astrid/packs/rendering/backends/remotion/run.py-1045-        alternatives=[],
astrid/packs/rendering/backends/remotion/run.py-1046-        backend=BACKEND_ID,
astrid/packs/rendering/backends/remotion/run.py-1047-        backend_version=BACKEND_VERSION,
astrid/packs/rendering/backends/remotion/run.py-1048-    )
astrid/packs/rendering/backends/remotion/run.py-1049-
astrid/packs/rendering/backends/remotion/run.py-1050-
astrid/packs/rendering/backends/remotion/run.py:1051:def _duration_frames(video_path: Path, profile: RenderProfile) -> int:
astrid/packs/rendering/backends/remotion/run.py-1052-    probe = ffprobe_metadata_strict(video_path)
astrid/packs/rendering/backends/remotion/run.py-1053-    if probe.duration_rational is not None:
astrid/packs/rendering/backends/remotion/run.py-1054-        duration = Fraction(*probe.duration_rational)
astrid/packs/rendering/backends/remotion/run.py-1055-    elif probe.duration_seconds is not None:
astrid/packs/rendering/backends/remotion/run.py-1056-        duration = Fraction(str(probe.duration_seconds))
astrid/packs/rendering/backends/remotion/run.py-1057-    else:
--
astrid/packs/rendering/backends/ffmpeg/run.py-26-from astrid.core.foundation.atomic_io import write_json_atomic
astrid/packs/rendering/backends/ffmpeg/run.py-27-from astrid.core.foundation.paths import REPO_ROOT
astrid/packs/rendering/backends/ffmpeg/run.py-28-from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict
astrid/packs/rendering/backends/ffmpeg/run.py-29-from astrid.core.rendering.artifacts import validate_render_result
astrid/packs/rendering/backends/ffmpeg/run.py-30-from astrid.core.rendering.contracts import (
astrid/packs/rendering/backends/ffmpeg/run.py-31-    AudioOwnership,
astrid/packs/rendering/backends/ffmpeg/run.py:32:    RenderProfile,
astrid/packs/rendering/backends/ffmpeg/run.py-33-    RenderRequest,
astrid/packs/rendering/backends/ffmpeg/run.py-34-    RenderResult,
astrid/packs/rendering/backends/ffmpeg/run.py-35-    SCHEMA_VERSION,
astrid/packs/rendering/backends/ffmpeg/run.py-36-    SupportReport,
astrid/packs/rendering/backends/ffmpeg/run.py-37-    VideoArtifact,
astrid/packs/rendering/backends/ffmpeg/run.py-38-)
--
astrid/packs/rendering/backends/ffmpeg/run.py-461-    return value
astrid/packs/rendering/backends/ffmpeg/run.py-462-
astrid/packs/rendering/backends/ffmpeg/run.py-463-
astrid/packs/rendering/backends/ffmpeg/run.py-464-def _profile_from_probe(
astrid/packs/rendering/backends/ffmpeg/run.py-465-    probe: MediaProbe,
astrid/packs/rendering/backends/ffmpeg/run.py-466-    ownership: AudioOwnership,
astrid/packs/rendering/backends/ffmpeg/run.py:467:) -> RenderProfile:
astrid/packs/rendering/backends/ffmpeg/run.py-468-    if not probe.has_video_stream:
astrid/packs/rendering/backends/ffmpeg/run.py-469-        raise RuntimeError("ffprobe did not report a video stream")
astrid/packs/rendering/backends/ffmpeg/run.py-470-    if ownership is AudioOwnership.RENDERED and not probe.has_audio_stream:
astrid/packs/rendering/backends/ffmpeg/run.py-471-        raise RuntimeError(
astrid/packs/rendering/backends/ffmpeg/run.py-472-            "rendering.ffmpeg media output did not contain its rendered audio"
astrid/packs/rendering/backends/ffmpeg/run.py-473-        )
--
astrid/packs/rendering/backends/ffmpeg/run.py-477-        )
astrid/packs/rendering/backends/ffmpeg/run.py-478-    audio_layout = probe.audio_channel_layout
astrid/packs/rendering/backends/ffmpeg/run.py-479-    if audio_layout is None and probe.audio_channels == 2:
astrid/packs/rendering/backends/ffmpeg/run.py-480-        audio_layout = "stereo"
astrid/packs/rendering/backends/ffmpeg/run.py-481-    elif audio_layout is None and probe.audio_channels == 1:
astrid/packs/rendering/backends/ffmpeg/run.py-482-        audio_layout = "mono"
astrid/packs/rendering/backends/ffmpeg/run.py:483:    return RenderProfile(
astrid/packs/rendering/backends/ffmpeg/run.py-484-        width=_required(probe.width, "video width"),
astrid/packs/rendering/backends/ffmpeg/run.py-485-        height=_required(probe.height, "video height"),
astrid/packs/rendering/backends/ffmpeg/run.py-486-        fps_rational=_required(probe.fps_rational, "video frame rate"),
astrid/packs/rendering/backends/ffmpeg/run.py-487-        time_base=_required(probe.time_base, "video time base"),
astrid/packs/rendering/backends/ffmpeg/run.py-488-        container=_required(probe.container, "container"),
astrid/packs/rendering/backends/ffmpeg/run.py-489-        video_codec=_required(probe.video_codec, "video codec"),
astrid/packs/rendering/backends/ffmpeg/run.py:490:        video_profile=probe.video_profile,
astrid/packs/rendering/backends/ffmpeg/run.py:491:        video_level=probe.video_level,
astrid/packs/rendering/backends/ffmpeg/run.py-492-        pixel_format=_required(probe.pixel_format, "pixel format"),
astrid/packs/rendering/backends/ffmpeg/run.py-493-        audio_codec=(
astrid/packs/rendering/backends/ffmpeg/run.py-494-            _required(probe.audio_codec, "audio codec")
astrid/packs/rendering/backends/ffmpeg/run.py-495-            if ownership is AudioOwnership.RENDERED
astrid/packs/rendering/backends/ffmpeg/run.py-496-            else None
astrid/packs/rendering/backends/ffmpeg/run.py-497-        ),

exec
/bin/zsh -lc "rg -n -C 5 'support.*profile|profile.*support|fail.closed|fail closed' docs astrid/core/rendering -g '*.md' -g '*.py' | head -n 500" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/publication.py-176-            _contains_symlink_component(video_unresolved)
astrid/core/rendering/publication.py-177-            or _contains_symlink_component(sidecar_unresolved)
astrid/core/rendering/publication.py-178-        ):
astrid/core/rendering/publication.py-179-            return None
astrid/core/rendering/publication.py-180-        # Resolve only AFTER the symlink guard so a symlink loop cannot
astrid/core/rendering/publication.py:181:        # raise RuntimeError here — it must fail closed to None.
astrid/core/rendering/publication.py-182-        video = _resolved(video_path)
astrid/core/rendering/publication.py-183-        sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
astrid/core/rendering/publication.py-184-        if video.is_symlink() or sidecar.is_symlink():
astrid/core/rendering/publication.py-185-            return None
astrid/core/rendering/publication.py-186-        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
--
docs/architecture/hivemind-hybrid-search-plan.md-775-`kind=message|resource|distillation`. Preserve that contract and add
docs/architecture/hivemind-hybrid-search-plan.md-776-`kind=workflow` as a backwards-compatible convenience alias for
docs/architecture/hivemind-hybrid-search-plan.md-777-`kind=resource` plus concrete resource-kind validation. Both
docs/architecture/hivemind-hybrid-search-plan.md-778-`kind=resource id=2580 representation=python` and
docs/architecture/hivemind-hybrid-search-plan.md-779-`kind=workflow id=2580 representation=python` may resolve the same workflow;
docs/architecture/hivemind-hybrid-search-plan.md:780:the Python option must fail closed if the hydrated resource is not actually
docs/architecture/hivemind-hybrid-search-plan.md-781-`kind=workflow`.
docs/architecture/hivemind-hybrid-search-plan.md-782-
docs/architecture/hivemind-hybrid-search-plan.md-783-Retain the existing no-distillation nudge, but base it on the final ranked
docs/architecture/hivemind-hybrid-search-plan.md-784-results rather than a separate distillation request.
docs/architecture/hivemind-hybrid-search-plan.md-785-
--
docs/architecture/hivemind-hybrid-search-plan.md-1792-and workflow-semantics search, never synthesize code from prose, and permit a
docs/architecture/hivemind-hybrid-search-plan.md-1793-later authoritative source repair without changing the workflow identity.
docs/architecture/hivemind-hybrid-search-plan.md-1794-
docs/architecture/hivemind-hybrid-search-plan.md-1795-### Workflow Python contains an accidentally committed credential
docs/architecture/hivemind-hybrid-search-plan.md-1796-
docs/architecture/hivemind-hybrid-search-plan.md:1797:Mitigation: deterministic pre-publication scanning, fail-closed new ingestion,
docs/architecture/hivemind-hybrid-search-plan.md-1798-historical quarantine, snippet redaction, non-secret reason codes, and a
docs/architecture/hivemind-hybrid-search-plan.md-1799-documented remove/rotate incident path. Never rely on embeddings or model
docs/architecture/hivemind-hybrid-search-plan.md-1800-behavior to hide a secret.
docs/architecture/hivemind-hybrid-search-plan.md-1801-
docs/architecture/hivemind-hybrid-search-plan.md-1802-### Source weighting hides better raw evidence
--
docs/contracts/error-model.md-85-  unless the committed inventory explicitly justifies it.
docs/contracts/error-model.md-86-- Best-effort non-CLI catches are allowed only when failure must not abort the
docs/contracts/error-model.md-87-  primary operation. Those catches must be narrow, or they must log/contextualize
docs/contracts/error-model.md-88-  why the failure is being ignored unless the inventory documents why logging is
docs/contracts/error-model.md-89-  noisy, recursive, or unsafe.
docs/contracts/error-model.md:90:- Audit integrity failures fail closed by default. Any corruption-tolerant or
docs/contracts/error-model.md-91-  verification-skipping path must be explicit, operator-chosen, and documented
docs/contracts/error-model.md-92-  as an opt-out.
docs/contracts/error-model.md-93-- `assert` is not runtime validation. Python strips asserts under `-O`, so
docs/contracts/error-model.md-94-  operator-facing validation and runtime invariants must raise explicit
docs/contracts/error-model.md-95-  exceptions instead.
--
docs/contracts/run-ledger-contract.md-320-
docs/contracts/run-ledger-contract.md-321-1. If a **configured default project** (`astrid projects default`) is among the
docs/contracts/run-ledger-contract.md-322-   candidate slugs, it is selected with a stderr notice:
docs/contracts/run-ledger-contract.md-323-   > `_most_recent_session_slug: N projects have a bound session on disk — preferring configured default project '<slug>'.`
docs/contracts/run-ledger-contract.md-324-
docs/contracts/run-ledger-contract.md:325:2. Otherwise, the hardened fail-closed refusal is retained — an enumerated list
docs/contracts/run-ledger-contract.md-326-   of `--project <slug>` suggestions is printed to stderr.
docs/contracts/run-ledger-contract.md-327-
docs/contracts/run-ledger-contract.md-328-Single-candidate resolution is unchanged: one `.astrid-session` → auto-resolve.
docs/contracts/run-ledger-contract.md-329-
docs/contracts/run-ledger-contract.md-330----
--
docs/contracts/render-backend-v1.md-43-- an extra pack root is eligible only when explicitly supplied;
docs/contracts/render-backend-v1.md-44-- environment-discovered packs remain inspectable but are not executable;
docs/contracts/render-backend-v1.md-45-- an installed pack is eligible only when its active revision and installation
docs/contracts/render-backend-v1.md-46-  trust audit are valid and its required permissions have been accepted;
docs/contracts/render-backend-v1.md-47-- corrupt, missing, mismatched, inactive, or insufficient-permission records
docs/contracts/render-backend-v1.md:48:  fail closed.
docs/contracts/render-backend-v1.md-49-
docs/contracts/render-backend-v1.md-50-Trust and permission declarations do not create an operating-system sandbox.
docs/contracts/render-backend-v1.md-51-An eligible command retains the invoking user's OS authority, subject to the
docs/contracts/render-backend-v1.md-52-host's sanitized environment and invocation staging.
docs/contracts/render-backend-v1.md-53-
--
docs/contracts/render-backend-v1.md-71-| `required_binaries` | Unique binary names checked before invocation. |
docs/contracts/render-backend-v1.md-72-| `timeout_seconds` | Optional positive default timeout. Host policy may impose a stricter limit. |
docs/contracts/render-backend-v1.md-73-| `metadata` | String-to-string descriptive metadata. |
docs/contracts/render-backend-v1.md-74-
docs/contracts/render-backend-v1.md-75-Renderer capability hints cover clip and track types, boolean/string features,
docs/contracts/render-backend-v1.md:76:whole-timeline and window support, output-profile labels, and possible audio
docs/contracts/render-backend-v1.md-77-ownership modes. Planner hints cover named policies and fallback support.
docs/contracts/render-backend-v1.md-78-Finalizer hints cover containers, attachment preservation, audio modes, and
docs/contracts/render-backend-v1.md-79-features. Hints are intentionally coarse; they cannot override a request-
docs/contracts/render-backend-v1.md-80-sensitive `SupportReport`.
docs/contracts/render-backend-v1.md-81-
--
docs/contracts/render-backend-v1.md-584-   accept arbitrary CLI import strings.
docs/contracts/render-backend-v1.md-585-5. **`rendering.render` remains the stable facade.** Existing pipelines should
docs/contracts/render-backend-v1.md-586-   not need to know how a backend is loaded or invoked.
docs/contracts/render-backend-v1.md-587-6. **Selection is deterministic and inspectable.** A render plan records the
docs/contracts/render-backend-v1.md-588-   selected backend for every segment plus the capability evidence and reason.
docs/contracts/render-backend-v1.md:589:7. **Unsupported requests fail closed by default.** Fallback occurs only when
docs/contracts/render-backend-v1.md-590-   an explicit planner policy or ordered fallback list permits it.
docs/contracts/render-backend-v1.md-591-8. **Every backend returns a validated artifact.** Finalizers consume declared
docs/contracts/render-backend-v1.md-592-   media metadata rather than assuming that arbitrary MP4 files are compatible.
docs/contracts/render-backend-v1.md-593-9. **Final assembly is explicit.** Ship an FFmpeg finalizer first, but keep
docs/contracts/render-backend-v1.md-594-   finalization behind a contract so arbitrary backends do not become secretly

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '135,215p;245,330p;570,605p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   570	M1 is amended and re-reviewed rather than creating an SDK-only dialect.
   571	
   572	## Locked epic decisions (verbatim)
   573	
   574	1. **Backend, planner, and finalizer are distinct concepts.** `hybrid` is a
   575	   planning policy, not a renderer backend.
   576	2. **The timeline remains backend-neutral.** Renderer selection is invocation
   577	   or plan configuration, never an arbitrary module path stored in timeline
   578	   data.
   579	3. **Backends have qualified IDs.** Built-ins should resolve canonically as
   580	   names such as `rendering.remotion` and `rendering.ffmpeg`; short legacy names
   581	   remain compatibility aliases.
   582	4. **Only trusted discovered packs contribute implementations.** Reuse existing
   583	   pack permission, precedence, conflict, alias, and override semantics. Do not
   584	   accept arbitrary CLI import strings.
   585	5. **`rendering.render` remains the stable facade.** Existing pipelines should
   586	   not need to know how a backend is loaded or invoked.
   587	6. **Selection is deterministic and inspectable.** A render plan records the
   588	   selected backend for every segment plus the capability evidence and reason.
   589	7. **Unsupported requests fail closed by default.** Fallback occurs only when
   590	   an explicit planner policy or ordered fallback list permits it.
   591	8. **Every backend returns a validated artifact.** Finalizers consume declared
   592	   media metadata rather than assuming that arbitrary MP4 files are compatible.
   593	9. **Final assembly is explicit.** Ship an FFmpeg finalizer first, but keep
   594	   finalization behind a contract so arbitrary backends do not become secretly
   595	   coupled to inlined FFmpeg logic.
   596	10. **Compatibility precedes semantic cleanup.** Preserve current
   597	    `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the
   598	    initial rollout. A later deprecation may make explicit Remotion strict and
   599	    move opportunistic selection to `planner=auto`.
   600	11. **Provenance has core-owned keys and backend-owned fragments.** Backend
   601	    fragments cannot overwrite core identity, routing, input, segment, or
   602	    finalizer fields.
   603	12. **No concrete backend imports outside the rendering implementation.**
   604	    External callers use the capability runner or one public render service.
   605	13. **The canonical interoperability boundary is language-neutral.** A

codex
The repo’s `contextminning-subagentmaxxing` guidance also applies to this multi-step review; I’m using it to keep the independent adversarial audit isolated and bring back only its conclusion. The direct check has already exposed one fail-closed profile gap that the passing suite does not exercise.
exec
/bin/zsh -lc "sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc 'wc -l /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md

codex
That posture points to `subagent-launcher` for shaping the independent review, so I’m applying its bounded, conclusion-only brief discipline to the adversarial check already in flight.
exec
/bin/zsh -lc "sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 242ms:
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

**Default to the hermes agentic pathway, and to DeepSeek Flash within it** — different model family, cheap, fast, tool-using. Reach for DeepSeek Pro only when the task needs reasoning judgement; reach for Codex or Claude only when you specifically want their strengths.

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
2. **DeepSeek V4 Flash** (`deepseek:deepseek-v4-flash`, **the default**) — non-reasoning, fast, cheap. The default for most dispatches: implementation, mechanical edits, focused investigation, verification. Escalate to Pro only on evidence that reasoning is needed.
3. **DeepSeek V4 Pro** (`deepseek:deepseek-v4-pro`) — reasoning model. Use when the task needs judgement: root-cause analysis, "is this sound", "should this merge".
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

- **`--model`** (default `deepseek:deepseek-v4-flash`). Prefix convention from the megaplan key pool:
  - `fast`, `mimo`, `mimo-fast` → `mimo:mimo-v2.5-pro-ultraspeed` (very fast MiMo path; requires `MIMO_API_KEY`)
  - `deepseek:deepseek-v4-flash` (default, non-reasoning) / `deepseek:deepseek-v4-pro` (reasoning) → DeepSeek API
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
  --max-workers=5 --model="deepseek:deepseek-v4-flash" \
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
  --model="deepseek:deepseek-v4-flash" --toolsets="file,web" \
  --query-file=/tmp/brief.md --max-tokens=65536 --project-dir="$PWD"
# Default: --model="deepseek:deepseek-v4-flash"   Very fast: --model=fast   Pro (reasoning): --model="deepseek:deepseek-v4-pro"   Kimi: --model="kimi:kimi-k2.7-code"   GLM: --model="zhipu:glm-5.2"
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

collab: Wait
codex
1. FFmpeg support still accepts pinned `video_profile`/`video_level` values it cannot guarantee. A request for `High`/`9.9` against a `Constrained Baseline`/`4.0` source returns `supported=True` and `stream_copy=True`, then fails strict artifact validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:487) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:422) [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:440)
tokens used
286,415
1. FFmpeg support still accepts pinned `video_profile`/`video_level` values it cannot guarantee. A request for `High`/`9.9` against a `Constrained Baseline`/`4.0` source returns `supported=True` and `stream_copy=True`, then fails strict artifact validation. [support.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/support.py:487) [command.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/backends/ffmpeg/command.py:422) [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:440)
