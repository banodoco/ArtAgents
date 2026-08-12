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
The repository instructions also require keeping wide review work out of the main thread, so I’m applying `contextminning-subagentmaxxing` and `subagent-launcher` for bounded independent checks. Their findings will be advisory; I’ll make the final oracle verdict from the code and evidence myself.
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

2026-08-12T06:44:49.864128Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:49.864158Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:49.864162Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:55.754067Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:55.754129Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:44:55.754134Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:45:01.471972Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:45:01.472013Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T06:45:01.472019Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
codex
Three read-only reviewers are checking transport, media/profile validation, and symlink/publication paths independently. In parallel, I’m tracing the complete commit delta and the prior checkpoint objections so the final verdict is not based only on the host’s summary or test counts.
exec
/bin/zsh -lc "rg --files .oracle | sort | rg 'batch-2|tasklist|status'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/briefs/batch-2-t2.1.md
.oracle/briefs/batch-2-t2.2.md
.oracle/briefs/batch-2-t2.3.md
.oracle/briefs/batch-2-t2.4.md
.oracle/briefs/batch-2-t2.5.md
.oracle/briefs/batch-2-t2.6.md
.oracle/checkins/batch-2-r1.md
.oracle/checkins/batch-2-r2.md
.oracle/checkins/batch-2-r3.md
.oracle/checkins/batch-2.md
.oracle/tasklist.md

exec
/bin/zsh -lc "sed -n '1,320p' /tmp/batch2-r3.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
diff --git a/.gitignore b/.gitignore
index f501f44b..9f441389 100644
--- a/.gitignore
+++ b/.gitignore
@@ -62,6 +62,7 @@ out/
 !tests/**/fixtures/**
 !tests/fixtures/**
 tests/fixtures/__pycache__/
+tests/fixtures/**/__pycache__/
 
 # Agentic test artifacts (regenerated per-run, not source)
 tests/agentic/reports/
diff --git a/.oracle/checkins/batch-2-r2.md b/.oracle/checkins/batch-2-r2.md
new file mode 100644
index 00000000..fba0af3f
--- /dev/null
+++ b/.oracle/checkins/batch-2-r2.md
@@ -0,0 +1,16679 @@
+Reading additional input from stdin...
+2026-08-12T06:18:50.249855Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T06:18:50.249891Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T06:18:50.249896Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff49f-a12e-7cb1-9892-6efd85142f54
+--------
+user
+# Megado Checkpoint — Batch 2 second re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: `.oracle/checkins/batch-2.md` (6 issues), `.oracle/checkins/batch-2-r1.md` (5 issues). Second rework committed as `7f7c25d5` (prior head 5231a233). Incremental diff at /tmp/batch2-r2.diff.
+
+## How each of your 5 re-review1 issues was addressed (host-implemented)
+
+1. **Transport leaks process groups; SIGTERM-ignoring child survives; repeated KeyboardInterrupt escapes** →
+   - `_wait_for_group_exit` now re-SIGKILLs in a loop until the group is gone (a group that ignores SIGKILL cannot exist on POSIX; if it survives the grace window, keep killing).
+   - The reap drain loop is bounded (grace-or-2s deadline) and force-kills the direct child before breaking on repeated KeyboardInterrupt.
+   - New test `test_sigterm_ignoring_child_is_escalated_and_reaped` (the existing sleep-tree fixture already ignores SIGTERM).
+2. **Fixture misdeclares media profile** →
+   - Request `render.json` audio_codec `sowt` → `pcm_s16le` (matches result).
+   - Added a `chan` atom to the `sowt` sample entry; verified ffprobe reports width 1920, height 1080 (SPS crop 4 units), pcm_s16le 48kHz.
+   - `media.py` probe now derives `channel_layout` from channel count when ffprobe reports none (QuickTime PCM limitation): 1→mono, 2→stereo, 6→5.1, 8→7.1. Strict validation now passes.
+3. **support validation non-strict** →
+   - Request must be a JSON object (non-object JSON → `protocol` error, no AttributeError).
+   - `schema_version` must be an int (not bool/float) equal to 1.
+4. **Production publishing follows output symlinks** →
+   - run.py no longer resolves `out_path` before publication; the unresolved path reaches the symlink guard.
+5. **Cleanup invisible sidecar symlinks** →
+   - `_delete_previous_outputs` skips candidates whose raw sidecar path (as well as raw video path) is a symlink.
+
+## Evidence
+
+- Incremental diff: /tmp/batch2-r2.diff (9 files)
+- Host-verified: test_transport (14) + raw fixture (6) + publication (7) + artifacts + media (75 combined) pass; full consolidated acceptance = 746 passed, 2 failed (SAME 2 pre-existing env-dependent failures), 3 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Verify the six closures, especially the SIGKILL escalation (run the SIGTERM-ignoring test), the probe-accuracy (ffprobe on generated output vs declared profile), and the symlink guards on unresolved paths. If PASS, say exactly `PASS`.
+codex
+I’m using the Megado review protocol and the repository’s context-minimizing workflow. I’ll inspect the prior findings and incremental diff, then independently verify transport cleanup, media/profile accuracy, protocol validation, and both symlink boundaries without modifying the worktree.
+exec
+/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc 'git diff --name-status 7f7c25d5..8c195bf0 && wc -l /tmp/batch2-r3.diff && shasum /tmp/batch2-r3.diff' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	.gitignore
A	.oracle/checkins/batch-2-r2.md
M	astrid/core/media.py
M	astrid/core/rendering/publication.py
M	astrid/core/rendering/transport.py
M	astrid/packs/rendering/executors/render/run.py
M	tests/core/rendering/test_raw_command_fixture.py
M	tests/core/util/test_media.py
D	tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc
M	tests/fixtures/renderer_packs/raw_command/backend.py
M	tests/fixtures/renderer_packs/raw_command/requests/support.json
   17039 /tmp/batch2-r3.diff
f36ed26f12a2487fec9cb58ba745765f0b8692d7  /tmp/batch2-r3.diff

exec
/bin/zsh -lc 'git status --short && git rev-parse HEAD && git show --no-ext-diff --stat --oneline --decorate 8c195bf0 && git diff --check 7f7c25d5..8c195bf0' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-2-r3.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8c195bf0ccbdf57efec0ab0b58579dd6c6b3b64f
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8c195bf0 (HEAD -> oracle-run) batch2-rework3: oracle re-review2 issues 1-6 (transport OSError/KeyboardInterrupt-safe cleanup w/ bounded escalation, chan atom inside wave + mono/stereo-only layout inference + strict-validation integration test, support profile fail-closed + support.json codec fix, run.py unresolved out_path in publication context, default-sidecar symlink guard, remove committed pyc + gitignore)
 .gitignore                                         |     1 +
 .oracle/checkins/batch-2-r2.md                     | 16679 +++++++++++++++++++
 astrid/core/media.py                               |     7 +-
 astrid/core/rendering/publication.py               |    16 +-
 astrid/core/rendering/transport.py                 |    47 +-
 astrid/packs/rendering/executors/render/run.py     |     2 +-
 tests/core/rendering/test_raw_command_fixture.py   |    17 +
 tests/core/util/test_media.py                      |    31 +
 .../__pycache__/backend.cpython-311.pyc            |   Bin 29820 -> 0 bytes
 .../fixtures/renderer_packs/raw_command/backend.py |    49 +-
 .../raw_command/requests/support.json              |    17 +-
 11 files changed, 16829 insertions(+), 37 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r2.md:237: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:238: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:240: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:588: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:590: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:592: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:594: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:596: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:598: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:600: trailing whitespace.
++++     2	
.oracle/checkins/batch-2-r2.md:602: trailing whitespace.
++++     4	
.oracle/checkins/batch-2-r2.md:604: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r2.md:606: trailing whitespace.
++++    11	
.oracle/checkins/batch-2-r2.md:608: trailing whitespace.
++++    29	
.oracle/checkins/batch-2-r2.md:610: trailing whitespace.
++++    30	
.oracle/checkins/batch-2-r2.md:612: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r2.md:614: trailing whitespace.
++++    34	
.oracle/checkins/batch-2-r2.md:616: trailing whitespace.
++++    39	
.oracle/checkins/batch-2-r2.md:618: trailing whitespace.
++++    41	
.oracle/checkins/batch-2-r2.md:620: trailing whitespace.
++++    42	
.oracle/checkins/batch-2-r2.md:622: trailing whitespace.
++++    54	
.oracle/checkins/batch-2-r2.md:624: trailing whitespace.
++++    55	
.oracle/checkins/batch-2-r2.md:626: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r2.md:628: trailing whitespace.
++++    83	
.oracle/checkins/batch-2-r2.md:630: trailing whitespace.
++++    86	
.oracle/checkins/batch-2-r2.md:632: trailing whitespace.
++++    93	
.oracle/checkins/batch-2-r2.md:634: trailing whitespace.
++++    94	
.oracle/checkins/batch-2-r2.md:636: trailing whitespace.
++++   106	
.oracle/checkins/batch-2-r2.md:638: trailing whitespace.
++++   107	
.oracle/checkins/batch-2-r2.md:640: trailing whitespace.
++++   199	
.oracle/checkins/batch-2-r2.md:642: trailing whitespace.
++++   200	
.oracle/checkins/batch-2-r2.md:644: trailing whitespace.
++++   915	
.oracle/checkins/batch-2-r2.md:646: trailing whitespace.
++++   916	
.oracle/checkins/batch-2-r2.md:648: trailing whitespace.
++++    35	
.oracle/checkins/batch-2-r2.md:650: trailing whitespace.
++++    40	
.oracle/checkins/batch-2-r2.md:652: trailing whitespace.
++++    49	
.oracle/checkins/batch-2-r2.md:654: trailing whitespace.
++++    61	
.oracle/checkins/batch-2-r2.md:656: trailing whitespace.
++++    82	
.oracle/checkins/batch-2-r2.md:658: trailing whitespace.
++++   102	
.oracle/checkins/batch-2-r2.md:660: trailing whitespace.
++++   119	
.oracle/checkins/batch-2-r2.md:662: trailing whitespace.
++++   132	
.oracle/checkins/batch-2-r2.md:664: trailing whitespace.
++++   139	
.oracle/checkins/batch-2-r2.md:666: trailing whitespace.
++++   140	
.oracle/checkins/batch-2-r2.md:668: trailing whitespace.
++++   143	
.oracle/checkins/batch-2-r2.md:670: trailing whitespace.
++++   167	
.oracle/checkins/batch-2-r2.md:672: trailing whitespace.
++++   168	
.oracle/checkins/batch-2-r2.md:674: trailing whitespace.
++++   516	
.oracle/checkins/batch-2-r2.md:676: trailing whitespace.
++++   520	
.oracle/checkins/batch-2-r2.md:678: trailing whitespace.
++++   539	
.oracle/checkins/batch-2-r2.md:680: trailing whitespace.
++++   572	
.oracle/checkins/batch-2-r2.md:682: trailing whitespace.
++++   573	
.oracle/checkins/batch-2-r2.md:684: trailing whitespace.
++++   580	
.oracle/checkins/batch-2-r2.md:686: trailing whitespace.
++++   585	
.oracle/checkins/batch-2-r2.md:688: trailing whitespace.
++++   591	
.oracle/checkins/batch-2-r2.md:690: trailing whitespace.
++++   592	
.oracle/checkins/batch-2-r2.md:692: trailing whitespace.
++++   596	
.oracle/checkins/batch-2-r2.md:694: trailing whitespace.
++++   601	
.oracle/checkins/batch-2-r2.md:696: trailing whitespace.
++++   613	
.oracle/checkins/batch-2-r2.md:698: trailing whitespace.
++++   618	
.oracle/checkins/batch-2-r2.md:700: trailing whitespace.
++++   630	
.oracle/checkins/batch-2-r2.md:702: trailing whitespace.
++++   642	
.oracle/checkins/batch-2-r2.md:704: trailing whitespace.
++++   643	
.oracle/checkins/batch-2-r2.md:706: trailing whitespace.
++++   664	
.oracle/checkins/batch-2-r2.md:708: trailing whitespace.
++++   665	
.oracle/checkins/batch-2-r2.md:710: trailing whitespace.
++++   669	
.oracle/checkins/batch-2-r2.md:712: trailing whitespace.
++++   676	
.oracle/checkins/batch-2-r2.md:714: trailing whitespace.
++++   699	
.oracle/checkins/batch-2-r2.md:716: trailing whitespace.
++++   711	
.oracle/checkins/batch-2-r2.md:718: trailing whitespace.
++++   200	
.oracle/checkins/batch-2-r2.md:720: trailing whitespace.
++++   276	
.oracle/checkins/batch-2-r2.md:722: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r2.md:724: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r2.md:726: trailing whitespace.
++++   289	
.oracle/checkins/batch-2-r2.md:728: trailing whitespace.
++++   311	
.oracle/checkins/batch-2-r2.md:730: trailing whitespace.
++++   312	
.oracle/checkins/batch-2-r2.md:732: trailing whitespace.
++++   328	
.oracle/checkins/batch-2-r2.md:734: trailing whitespace.
++++   335	
.oracle/checkins/batch-2-r2.md:736: trailing whitespace.
++++   356	
.oracle/checkins/batch-2-r2.md:738: trailing whitespace.
++++   383	
.oracle/checkins/batch-2-r2.md:740: trailing whitespace.
++++   384	
.oracle/checkins/batch-2-r2.md:742: trailing whitespace.
++++   387	
.oracle/checkins/batch-2-r2.md:744: trailing whitespace.
++++   389	
.oracle/checkins/batch-2-r2.md:746: trailing whitespace.
++++   390	
.oracle/checkins/batch-2-r2.md:748: trailing whitespace.
++++   214	
.oracle/checkins/batch-2-r2.md:750: trailing whitespace.
++++   215	
.oracle/checkins/batch-2-r2.md:752: trailing whitespace.
++++   218	
.oracle/checkins/batch-2-r2.md:754: trailing whitespace.
++++   224	
.oracle/checkins/batch-2-r2.md:756: trailing whitespace.
++++   225	
.oracle/checkins/batch-2-r2.md:758: trailing whitespace.
++++   234	
.oracle/checkins/batch-2-r2.md:760: trailing whitespace.
++++   235	
.oracle/checkins/batch-2-r2.md:762: trailing whitespace.
++++   240	
.oracle/checkins/batch-2-r2.md:764: trailing whitespace.
++++   241	
.oracle/checkins/batch-2-r2.md:766: trailing whitespace.
++++   250	
.oracle/checkins/batch-2-r2.md:768: trailing whitespace.
++++   251	
.oracle/checkins/batch-2-r2.md:770: trailing whitespace.
++++   257	
.oracle/checkins/batch-2-r2.md:772: trailing whitespace.
++++   258	
.oracle/checkins/batch-2-r2.md:774: trailing whitespace.
++++   271	
.oracle/checkins/batch-2-r2.md:776: trailing whitespace.
++++   272	
.oracle/checkins/batch-2-r2.md:778: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r2.md:780: trailing whitespace.
++++   278	
.oracle/checkins/batch-2-r2.md:782: trailing whitespace.
++++   285	
.oracle/checkins/batch-2-r2.md:784: trailing whitespace.
++++   286	
.oracle/checkins/batch-2-r2.md:786: trailing whitespace.
++++   293	
.oracle/checkins/batch-2-r2.md:788: trailing whitespace.
++++   294	
.oracle/checkins/batch-2-r2.md:790: trailing whitespace.
++++   303	
.oracle/checkins/batch-2-r2.md:792: trailing whitespace.
++++   304	
.oracle/checkins/batch-2-r2.md:794: trailing whitespace.
++++   311	
.oracle/checkins/batch-2-r2.md:796: trailing whitespace.
++++   312	
.oracle/checkins/batch-2-r2.md:798: trailing whitespace.
++++   321	
.oracle/checkins/batch-2-r2.md:800: trailing whitespace.
++++   322	
.oracle/checkins/batch-2-r2.md:802: trailing whitespace.
++++   339	
.oracle/checkins/batch-2-r2.md:804: trailing whitespace.
++++   340	
.oracle/checkins/batch-2-r2.md:806: trailing whitespace.
++++   352	
.oracle/checkins/batch-2-r2.md:808: trailing whitespace.
++++   353	
.oracle/checkins/batch-2-r2.md:810: trailing whitespace.
++++   356	
.oracle/checkins/batch-2-r2.md:812: trailing whitespace.
++++   362	
.oracle/checkins/batch-2-r2.md:814: trailing whitespace.
++++   363	
.oracle/checkins/batch-2-r2.md:816: trailing whitespace.
++++   664	
.oracle/checkins/batch-2-r2.md:818: trailing whitespace.
++++   665	
.oracle/checkins/batch-2-r2.md:820: trailing whitespace.
++++   669	
.oracle/checkins/batch-2-r2.md:822: trailing whitespace.
++++   676	
.oracle/checkins/batch-2-r2.md:824: trailing whitespace.
++++   699	
.oracle/checkins/batch-2-r2.md:826: trailing whitespace.
++++   711	
.oracle/checkins/batch-2-r2.md:828: trailing whitespace.
++++   726	
.oracle/checkins/batch-2-r2.md:830: trailing whitespace.
++++   747	
.oracle/checkins/batch-2-r2.md:832: trailing whitespace.
++++   748	
.oracle/checkins/batch-2-r2.md:834: trailing whitespace.
++++   755	
.oracle/checkins/batch-2-r2.md:836: trailing whitespace.
++++   276	
.oracle/checkins/batch-2-r2.md:838: trailing whitespace.
++++   277	
.oracle/checkins/batch-2-r2.md:840: trailing whitespace.
++++   288	
.oracle/checkins/batch-2-r2.md:842: trailing whitespace.
++++   289	
.oracle/checkins/batch-2-r2.md:844: trailing whitespace.
++++   311	
.oracle/checkins/batch-2-r2.md:846: trailing whitespace.
++++   312	
.oracle/checkins/batch-2-r2.md:848: trailing whitespace.
++++   328	
.oracle/checkins/batch-2-r2.md:850: trailing whitespace.
++++   335	
.oracle/checkins/batch-2-r2.md:852: trailing whitespace.
++++   356	
.oracle/checkins/batch-2-r2.md:854: trailing whitespace.
++++   383	
.oracle/checkins/batch-2-r2.md:856: trailing whitespace.
++++   384	
.oracle/checkins/batch-2-r2.md:858: trailing whitespace.
++++   387	
.oracle/checkins/batch-2-r2.md:860: trailing whitespace.
++++   389	
.oracle/checkins/batch-2-r2.md:862: trailing whitespace.
++++   390	
.oracle/checkins/batch-2-r2.md:864: trailing whitespace.
++++   749	
.oracle/checkins/batch-2-r2.md:866: trailing whitespace.
++++   750	
.oracle/checkins/batch-2-r2.md:868: trailing whitespace.
++++   786	
.oracle/checkins/batch-2-r2.md:870: trailing whitespace.
++++   787	
.oracle/checkins/batch-2-r2.md:872: trailing whitespace.
++++   801	
.oracle/checkins/batch-2-r2.md:874: trailing whitespace.
++++   802	
.oracle/checkins/batch-2-r2.md:876: trailing whitespace.
++++   818	
.oracle/checkins/batch-2-r2.md:878: trailing whitespace.
++++   819	
.oracle/checkins/batch-2-r2.md:880: trailing whitespace.
++++   915	
.oracle/checkins/batch-2-r2.md:882: trailing whitespace.
++++   916	
.oracle/checkins/batch-2-r2.md:884: trailing whitespace.
++++  1072	
.oracle/checkins/batch-2-r2.md:886: trailing whitespace.
++++  1073	
.oracle/checkins/batch-2-r2.md:888: trailing whitespace.
++++  1082	
.oracle/checkins/batch-2-r2.md:890: trailing whitespace.
++++  1083	
.oracle/checkins/batch-2-r2.md:892: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:894: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:896: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:898: trailing whitespace.
++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:900: trailing whitespace.
++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:902: trailing whitespace.
++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:904: trailing whitespace.
+++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:906: trailing whitespace.
+++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:908: trailing whitespace.
+++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:910: trailing whitespace.
++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:912: trailing whitespace.
++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:914: trailing whitespace.
++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:916: trailing whitespace.
+++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:918: trailing whitespace.
+++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:920: trailing whitespace.
+++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:922: trailing whitespace.
+++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:924: trailing whitespace.
+++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:926: trailing whitespace.
+++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:928: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:930: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:932: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:934: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:936: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:938: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:940: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:942: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:944: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:946: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:948: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:950: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:952: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:954: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:956: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:958: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:960: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:962: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:964: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:966: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:968: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:970: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:972: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:974: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:976: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:978: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:980: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:982: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:984: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:986: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:988: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:990: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:992: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:994: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:996: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:998: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1000: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1002: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1004: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1006: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1008: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1010: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1012: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1014: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1016: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1018: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1020: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1022: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1024: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1026: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1028: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1030: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1032: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1034: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1036: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1038: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1040: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1042: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1044: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1046: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1048: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1050: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1052: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1054: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1056: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1058: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1060: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1062: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1064: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1066: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1068: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1070: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1072: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1074: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1076: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1078: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1080: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1082: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1084: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1086: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1088: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1090: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1092: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1094: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1096: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1098: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1100: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1102: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1104: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1106: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1108: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1110: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1112: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1114: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1116: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1118: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1120: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1122: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1124: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1126: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1128: trailing whitespace.
+++++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:1130: trailing whitespace.
+++++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:1132: trailing whitespace.
+++++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:1134: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1136: trailing whitespace.
+++++++++   730	
.oracle/checkins/batch-2-r2.md:1138: trailing whitespace.
+++++++++   731	
.oracle/checkins/batch-2-r2.md:1140: trailing whitespace.
+++++++++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-2-r2.md:1142: trailing whitespace.
+++++++++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-2-r2.md:1144: trailing whitespace.
+++++++++   453	
.oracle/checkins/batch-2-r2.md:1146: trailing whitespace.
+++++++++   461	
.oracle/checkins/batch-2-r2.md:1148: trailing whitespace.
+++++++++   463	
.oracle/checkins/batch-2-r2.md:1150: trailing whitespace.
+++++++++   465	
.oracle/checkins/batch-2-r2.md:1152: trailing whitespace.
+++++++++   470	
.oracle/checkins/batch-2-r2.md:1154: trailing whitespace.
+++++++++   492	
.oracle/checkins/batch-2-r2.md:1156: trailing whitespace.
+++++++++   520	
.oracle/checkins/batch-2-r2.md:1158: trailing whitespace.
+++++++++   539	
.oracle/checkins/batch-2-r2.md:1160: trailing whitespace.
+++++++++   540	
.oracle/checkins/batch-2-r2.md:1162: trailing whitespace.
+++++++++   550	
.oracle/checkins/batch-2-r2.md:1164: trailing whitespace.
+++++++++   551	
.oracle/checkins/batch-2-r2.md:1166: trailing whitespace.
+++++++++   609	
.oracle/checkins/batch-2-r2.md:1168: trailing whitespace.
+++++++++   613	
.oracle/checkins/batch-2-r2.md:1170: trailing whitespace.
+++++++++   614	
.oracle/checkins/batch-2-r2.md:1172: trailing whitespace.
+++++++++   627	
.oracle/checkins/batch-2-r2.md:1174: trailing whitespace.
+++++++++   628	
.oracle/checkins/batch-2-r2.md:1176: trailing whitespace.
+++++++++   631	
.oracle/checkins/batch-2-r2.md:1178: trailing whitespace.
+++++++++   640	
.oracle/checkins/batch-2-r2.md:1180: trailing whitespace.
+++++++++   641	
.oracle/checkins/batch-2-r2.md:1182: trailing whitespace.
+++++++++   647	
.oracle/checkins/batch-2-r2.md:1184: trailing whitespace.
+++++++++   648	
.oracle/checkins/batch-2-r2.md:1186: trailing whitespace.
+++++++++   679	
.oracle/checkins/batch-2-r2.md:1188: trailing whitespace.
+++++++++   689	
.oracle/checkins/batch-2-r2.md:1190: trailing whitespace.
+++++++++   721	
.oracle/checkins/batch-2-r2.md:1192: trailing whitespace.
+++++++++   722	
.oracle/checkins/batch-2-r2.md:1194: trailing whitespace.
+++++++++   740	
.oracle/checkins/batch-2-r2.md:1196: trailing whitespace.
+++++++++   741	
.oracle/checkins/batch-2-r2.md:1198: trailing whitespace.
+++++++++   777	
.oracle/checkins/batch-2-r2.md:1200: trailing whitespace.
+++++++++   778	
.oracle/checkins/batch-2-r2.md:1202: trailing whitespace.
+++++++++   792	
.oracle/checkins/batch-2-r2.md:1204: trailing whitespace.
+++++++++   793	
.oracle/checkins/batch-2-r2.md:1206: trailing whitespace.
+++++++++   809	
.oracle/checkins/batch-2-r2.md:1208: trailing whitespace.
+++++++++   810	
.oracle/checkins/batch-2-r2.md:1210: trailing whitespace.
+++++++++   904	
.oracle/checkins/batch-2-r2.md:1212: trailing whitespace.
+++++++++   905	
.oracle/checkins/batch-2-r2.md:1214: trailing whitespace.
+++++++++   965	
.oracle/checkins/batch-2-r2.md:1216: trailing whitespace.
+++++++++   966	
.oracle/checkins/batch-2-r2.md:1218: trailing whitespace.
+++++++++   975	
.oracle/checkins/batch-2-r2.md:1220: trailing whitespace.
+++++++++   976	
.oracle/checkins/batch-2-r2.md:1222: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r2.md:1224: trailing whitespace.
+++++++++     4	
.oracle/checkins/batch-2-r2.md:1226: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r2.md:1228: trailing whitespace.
+++++++++    11	
.oracle/checkins/batch-2-r2.md:1230: trailing whitespace.
+++++++++    28	
.oracle/checkins/batch-2-r2.md:1232: trailing whitespace.
+++++++++    29	
.oracle/checkins/batch-2-r2.md:1234: trailing whitespace.
+++++++++    32	
.oracle/checkins/batch-2-r2.md:1236: trailing whitespace.
+++++++++    33	
.oracle/checkins/batch-2-r2.md:1238: trailing whitespace.
+++++++++    38	
.oracle/checkins/batch-2-r2.md:1240: trailing whitespace.
+++++++++    40	
.oracle/checkins/batch-2-r2.md:1242: trailing whitespace.
+++++++++    41	
.oracle/checkins/batch-2-r2.md:1244: trailing whitespace.
+++++++++    53	
.oracle/checkins/batch-2-r2.md:1246: trailing whitespace.
+++++++++    54	
.oracle/checkins/batch-2-r2.md:1248: trailing whitespace.
+++++++++    81	
.oracle/checkins/batch-2-r2.md:1250: trailing whitespace.
+++++++++    82	
.oracle/checkins/batch-2-r2.md:1252: trailing whitespace.
+++++++++    85	
.oracle/checkins/batch-2-r2.md:1254: trailing whitespace.
+++++++++    92	
.oracle/checkins/batch-2-r2.md:1256: trailing whitespace.
+++++++++    93	
.oracle/checkins/batch-2-r2.md:1258: trailing whitespace.
+++++++++   105	
.oracle/checkins/batch-2-r2.md:1260: trailing whitespace.
+++++++++   106	
.oracle/checkins/batch-2-r2.md:1262: trailing whitespace.
+++++++++   168	
.oracle/checkins/batch-2-r2.md:1264: trailing whitespace.
+++++++++   169	
.oracle/checkins/batch-2-r2.md:1266: trailing whitespace.
+++++++++   236	
.oracle/checkins/batch-2-r2.md:1268: trailing whitespace.
+++++++++   237	
.oracle/checkins/batch-2-r2.md:1270: trailing whitespace.
+++++++++   248	
.oracle/checkins/batch-2-r2.md:1272: trailing whitespace.
+++++++++   249	
.oracle/checkins/batch-2-r2.md:1274: trailing whitespace.
+++++++++   271	
.oracle/checkins/batch-2-r2.md:1276: trailing whitespace.
+++++++++   272	
.oracle/checkins/batch-2-r2.md:1278: trailing whitespace.
+++++++++   288	
.oracle/checkins/batch-2-r2.md:1280: trailing whitespace.
+++++++++   295	
.oracle/checkins/batch-2-r2.md:1282: trailing whitespace.
+++++++++   316	
.oracle/checkins/batch-2-r2.md:1284: trailing whitespace.
+++++++++   343	
.oracle/checkins/batch-2-r2.md:1286: trailing whitespace.
+++++++++   344	
.oracle/checkins/batch-2-r2.md:1288: trailing whitespace.
+++++++++   347	
.oracle/checkins/batch-2-r2.md:1290: trailing whitespace.
+++++++++   349	
.oracle/checkins/batch-2-r2.md:1292: trailing whitespace.
+++++++++   350	
.oracle/checkins/batch-2-r2.md:1294: trailing whitespace.
+++++++++   353	
.oracle/checkins/batch-2-r2.md:1296: trailing whitespace.
+++++++++   357	
.oracle/checkins/batch-2-r2.md:1298: trailing whitespace.
+++++++++   358	
.oracle/checkins/batch-2-r2.md:1300: trailing whitespace.
+++++++++   361	
.oracle/checkins/batch-2-r2.md:1302: trailing whitespace.
+++++++++   366	
.oracle/checkins/batch-2-r2.md:1304: trailing whitespace.
+++++++++   367	
.oracle/checkins/batch-2-r2.md:1306: trailing whitespace.
+++++++++   370	
.oracle/checkins/batch-2-r2.md:1308: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r2.md:1310: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r2.md:1312: trailing whitespace.
+++++++++    10	
.oracle/checkins/batch-2-r2.md:1314: trailing whitespace.
+++++++++    18	
.oracle/checkins/batch-2-r2.md:1316: trailing whitespace.
+++++++++    21	
.oracle/checkins/batch-2-r2.md:1318: trailing whitespace.
+++++++++    22	
.oracle/checkins/batch-2-r2.md:1320: trailing whitespace.
+++++++++    24	
.oracle/checkins/batch-2-r2.md:1322: trailing whitespace.
+++++++++    35	
.oracle/checkins/batch-2-r2.md:1324: trailing whitespace.
+++++++++    40	
.oracle/checkins/batch-2-r2.md:1326: trailing whitespace.
+++++++++    52	
.oracle/checkins/batch-2-r2.md:1328: trailing whitespace.
+++++++++    73	
.oracle/checkins/batch-2-r2.md:1330: trailing whitespace.
+++++++++    93	
.oracle/checkins/batch-2-r2.md:1332: trailing whitespace.
+++++++++   110	
.oracle/checkins/batch-2-r2.md:1334: trailing whitespace.
+++++++++   123	
.oracle/checkins/batch-2-r2.md:1336: trailing whitespace.
+++++++++   130	
.oracle/checkins/batch-2-r2.md:1338: trailing whitespace.
+++++++++   131	
.oracle/checkins/batch-2-r2.md:1340: trailing whitespace.
+++++++++   134	
.oracle/checkins/batch-2-r2.md:1342: trailing whitespace.
+++++++++   158	
.oracle/checkins/batch-2-r2.md:1344: trailing whitespace.
+++++++++   159	
.oracle/checkins/batch-2-r2.md:1346: trailing whitespace.
+++++++++   165	
.oracle/checkins/batch-2-r2.md:1348: trailing whitespace.
+++++++++   166	
.oracle/checkins/batch-2-r2.md:1350: trailing whitespace.
+++++++++   171	
.oracle/checkins/batch-2-r2.md:1352: trailing whitespace.
+++++++++   172	
.oracle/checkins/batch-2-r2.md:1354: trailing whitespace.
+++++++++   186	
.oracle/checkins/batch-2-r2.md:1356: trailing whitespace.
+++++++++   187	
.oracle/checkins/batch-2-r2.md:1358: trailing whitespace.
+++++++++   194	
.oracle/checkins/batch-2-r2.md:1360: trailing whitespace.
+++++++++   195	
.oracle/checkins/batch-2-r2.md:1362: trailing whitespace.
+++++++++   205	
.oracle/checkins/batch-2-r2.md:1364: trailing whitespace.
+++++++++   206	
.oracle/checkins/batch-2-r2.md:1366: trailing whitespace.
+++++++++   209	
.oracle/checkins/batch-2-r2.md:1368: trailing whitespace.
+++++++++   215	
.oracle/checkins/batch-2-r2.md:1370: trailing whitespace.
+++++++++   216	
.oracle/checkins/batch-2-r2.md:1372: trailing whitespace.
+++++++++   225	
.oracle/checkins/batch-2-r2.md:1374: trailing whitespace.
+++++++++   226	
.oracle/checkins/batch-2-r2.md:1376: trailing whitespace.
+++++++++   231	
.oracle/checkins/batch-2-r2.md:1378: trailing whitespace.
+++++++++   232	
.oracle/checkins/batch-2-r2.md:1380: trailing whitespace.
+++++++++   241	
.oracle/checkins/batch-2-r2.md:1382: trailing whitespace.
+++++++++   242	
.oracle/checkins/batch-2-r2.md:1384: trailing whitespace.
+++++++++   248	
.oracle/checkins/batch-2-r2.md:1386: trailing whitespace.
+++++++++   249	
.oracle/checkins/batch-2-r2.md:1388: trailing whitespace.
+++++++++   507	
.oracle/checkins/batch-2-r2.md:1390: trailing whitespace.
+++++++++   511	
.oracle/checkins/batch-2-r2.md:1392: trailing whitespace.
+++++++++   530	
.oracle/checkins/batch-2-r2.md:1394: trailing whitespace.
+++++++++   563	
.oracle/checkins/batch-2-r2.md:1396: trailing whitespace.
+++++++++   564	
.oracle/checkins/batch-2-r2.md:1398: trailing whitespace.
+++++++++   571	
.oracle/checkins/batch-2-r2.md:1400: trailing whitespace.
+++++++++   576	
.oracle/checkins/batch-2-r2.md:1402: trailing whitespace.
+++++++++   582	
.oracle/checkins/batch-2-r2.md:1404: trailing whitespace.
+++++++++   583	
.oracle/checkins/batch-2-r2.md:1406: trailing whitespace.
+++++++++   587	
.oracle/checkins/batch-2-r2.md:1408: trailing whitespace.
+++++++++   592	
.oracle/checkins/batch-2-r2.md:1410: trailing whitespace.
+++++++++   604	
.oracle/checkins/batch-2-r2.md:1412: trailing whitespace.
+++++++++   609	
.oracle/checkins/batch-2-r2.md:1414: trailing whitespace.
+++++++++   621	
.oracle/checkins/batch-2-r2.md:1416: trailing whitespace.
+++++++++   633	
.oracle/checkins/batch-2-r2.md:1418: trailing whitespace.
+++++++++   634	
.oracle/checkins/batch-2-r2.md:1420: trailing whitespace.
+++++++++   655	
.oracle/checkins/batch-2-r2.md:1422: trailing whitespace.
+++++++++   656	
.oracle/checkins/batch-2-r2.md:1424: trailing whitespace.
+++++++++   660	
.oracle/checkins/batch-2-r2.md:1426: trailing whitespace.
+++++++++   667	
.oracle/checkins/batch-2-r2.md:1428: trailing whitespace.
+++++++++   690	
.oracle/checkins/batch-2-r2.md:1430: trailing whitespace.
+++++++++   702	
.oracle/checkins/batch-2-r2.md:1432: trailing whitespace.
+++++++++   717	
.oracle/checkins/batch-2-r2.md:1434: trailing whitespace.
+++++++++  1662	
.oracle/checkins/batch-2-r2.md:1436: trailing whitespace.
+++++++++  1686	
.oracle/checkins/batch-2-r2.md:1438: trailing whitespace.
+++++++++  1693	
.oracle/checkins/batch-2-r2.md:1440: trailing whitespace.
+++++++++  1694	
.oracle/checkins/batch-2-r2.md:1442: trailing whitespace.
+++++++++  1698	
.oracle/checkins/batch-2-r2.md:1444: trailing whitespace.
+++++++++  1705	
.oracle/checkins/batch-2-r2.md:1446: trailing whitespace.
+++++++++  1753	
.oracle/checkins/batch-2-r2.md:1448: trailing whitespace.
+++++++++  1757	
.oracle/checkins/batch-2-r2.md:1450: trailing whitespace.
+++++++++  1763	
.oracle/checkins/batch-2-r2.md:1452: trailing whitespace.
+++++++++  1769	
.oracle/checkins/batch-2-r2.md:1454: trailing whitespace.
+++++++++  1773	
.oracle/checkins/batch-2-r2.md:1456: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r2.md:1458: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r2.md:1460: trailing whitespace.
+++++++++    11	
.oracle/checkins/batch-2-r2.md:1462: trailing whitespace.
+++++++++    20	
.oracle/checkins/batch-2-r2.md:1464: trailing whitespace.
+++++++++    21	
.oracle/checkins/batch-2-r2.md:1466: trailing whitespace.
+++++++++    48	
.oracle/checkins/batch-2-r2.md:1468: trailing whitespace.
+++++++++    49	
.oracle/checkins/batch-2-r2.md:1470: trailing whitespace.
+++++++++    52	
.oracle/checkins/batch-2-r2.md:1472: trailing whitespace.
+++++++++    53	
.oracle/checkins/batch-2-r2.md:1474: trailing whitespace.
+++++++++    56	
.oracle/checkins/batch-2-r2.md:1476: trailing whitespace.
+++++++++    57	
.oracle/checkins/batch-2-r2.md:1478: trailing whitespace.
+++++++++    60	
.oracle/checkins/batch-2-r2.md:1480: trailing whitespace.
+++++++++    61	
.oracle/checkins/batch-2-r2.md:1482: trailing whitespace.
+++++++++    72	
.oracle/checkins/batch-2-r2.md:1484: trailing whitespace.
+++++++++    73	
.oracle/checkins/batch-2-r2.md:1486: trailing whitespace.
+++++++++    81	
.oracle/checkins/batch-2-r2.md:1488: trailing whitespace.
+++++++++    88	
.oracle/checkins/batch-2-r2.md:1490: trailing whitespace.
+++++++++    89	
.oracle/checkins/batch-2-r2.md:1492: trailing whitespace.
+++++++++    96	
.oracle/checkins/batch-2-r2.md:1494: trailing whitespace.
+++++++++    97	
.oracle/checkins/batch-2-r2.md:1496: trailing whitespace.
+++++++++   105	
.oracle/checkins/batch-2-r2.md:1498: trailing whitespace.
+++++++++   106	
.oracle/checkins/batch-2-r2.md:1500: trailing whitespace.
+++++++++   113	
.oracle/checkins/batch-2-r2.md:1502: trailing whitespace.
+++++++++   114	
.oracle/checkins/batch-2-r2.md:1504: trailing whitespace.
+++++++++   312	
.oracle/checkins/batch-2-r2.md:1506: trailing whitespace.
+++++++++   313	
.oracle/checkins/batch-2-r2.md:1508: trailing whitespace.
+++++++++   324	
.oracle/checkins/batch-2-r2.md:1510: trailing whitespace.
+++++++++   325	
.oracle/checkins/batch-2-r2.md:1512: trailing whitespace.
+++++++++   338	
.oracle/checkins/batch-2-r2.md:1514: trailing whitespace.
+++++++++   339	
.oracle/checkins/batch-2-r2.md:1516: trailing whitespace.
+++++++++   356	
.oracle/checkins/batch-2-r2.md:1518: trailing whitespace.
+++++++++   357	
.oracle/checkins/batch-2-r2.md:1520: trailing whitespace.
+++++++++   375	
.oracle/checkins/batch-2-r2.md:1522: trailing whitespace.
+++++++++   376	
.oracle/checkins/batch-2-r2.md:1524: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1526: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1528: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1530: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1532: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1534: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1536: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1538: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1540: trailing whitespace.
+++++++++ 
.oracle/checkins/batch-2-r2.md:1542: trailing whitespace.
+++++++++   809	
.oracle/checkins/batch-2-r2.md:1544: trailing whitespace.
+++++++++   810	
.oracle/checkins/batch-2-r2.md:1546: trailing whitespace.
+++++++++   904	
.oracle/checkins/batch-2-r2.md:1548: trailing whitespace.
+++++++++   905	
.oracle/checkins/batch-2-r2.md:1550: trailing whitespace.
+++++++++   965	
.oracle/checkins/batch-2-r2.md:1552: trailing whitespace.
+++++++++   966	
.oracle/checkins/batch-2-r2.md:1554: trailing whitespace.
+++++++++     2	
.oracle/checkins/batch-2-r2.md:1556: trailing whitespace.
+++++++++     4	
.oracle/checkins/batch-2-r2.md:1558: trailing whitespace.
+++++++++     6	
.oracle/checkins/batch-2-r2.md:1560: trailing whitespace.
+++++++++     8	
.oracle/checkins/batch-2-r2.md:1562: trailing whitespace.
+++++++++    17	
.oracle/checkins/batch-2-r2.md:1564: trailing whitespace.
+++++++++    19	
.oracle/checkins/batch-2-r2.md:1566: trailing whitespace.
+++++++++    25	
.oracle/checkins/batch-2-r2.md:1568: trailing whitespace.
+++++++++    27	
.oracle/checkins/batch-2-r2.md:1570: trailing whitespace.
+++++++++    29	
.oracle/checkins/batch-2-r2.md:1572: trailing whitespace.
+++++++++    31	
.oracle/checkins/batch-2-r2.md:1574: trailing whitespace.
+++++++++    40	
.oracle/checkins/batch-2-r2.md:1576: trailing whitespace.
+++++++++    42	
.oracle/checkins/batch-2-r2.md:1578: trailing whitespace.
+++++++++    49	
.oracle/checkins/batch-2-r2.md:1580: trailing whitespace.
+++++++++    51	
.oracle/checkins/batch-2-r2.md:1582: trailing whitespace.
+++++++++    53	
.oracle/checkins/batch-2-r2.md:1584: trailing whitespace.
+++++++++    55	
.oracle/checkins/batch-2-r2.md:1586: trailing whitespace.
+++++++++    63	
.oracle/checkins/batch-2-r2.md:1588: trailing whitespace.
+++++++++    65	
.oracle/checkins/batch-2-r2.md:1590: trailing whitespace.
+++++++++    72	
.oracle/checkins/batch-2-r2.md:1592: trailing whitespace.
+++++++++    74	
.oracle/checkins/batch-2-r2.md:1594: trailing whitespace.
+++++++++    76	
.oracle/checkins/batch-2-r2.md:1596: trailing whitespace.
+++++++++    78	
.oracle/checkins/batch-2-r2.md:1598: trailing whitespace.
+++++++++   131	
.oracle/checkins/batch-2-r2.md:1600: trailing whitespace.
+++++++++   132	
.oracle/checkins/batch-2-r2.md:1602: trailing whitespace.
+++++++++   162	
.oracle/checkins/batch-2-r2.md:1604: trailing whitespace.
+++++++++   163	
.oracle/checkins/batch-2-r2.md:1606: trailing whitespace.
+++++++++   178	
.oracle/checkins/batch-2-r2.md:1608: trailing whitespace.
+++++++++   179	
.oracle/checkins/batch-2-r2.md:1610: trailing whitespace.
+++++++++   206	
.oracle/checkins/batch-2-r2.md:1612: trailing whitespace.
+++++++++   207	
.oracle/checkins/batch-2-r2.md:1614: trailing whitespace.
+++++++++   249	
.oracle/checkins/batch-2-r2.md:1616: trailing whitespace.
+++++++++   250	
.oracle/checkins/batch-2-r2.md:1618: trailing whitespace.
+++++++++   288	
.oracle/checkins/batch-2-r2.md:1620: trailing whitespace.
+++++++++   289	
.oracle/checkins/batch-2-r2.md:1622: trailing whitespace.
+++++++++   302	
.oracle/checkins/batch-2-r2.md:1624: trailing whitespace.
+++++++++   303	
.oracle/checkins/batch-2-r2.md:1626: trailing whitespace.
+++++++++   312	
.oracle/checkins/batch-2-r2.md:1628: trailing whitespace.
+++++++++   313	
.oracle/checkins/batch-2-r2.md:1630: trailing whitespace.
+++++++++   330	
.oracle/checkins/batch-2-r2.md:1632: trailing whitespace.
+++++++++   331	
.oracle/checkins/batch-2-r2.md:1634: trailing whitespace.
+++++++++   343	
.oracle/checkins/batch-2-r2.md:1636: trailing whitespace.
+++++++++   344	
.oracle/checkins/batch-2-r2.md:1638: trailing whitespace.
+++++++++   288	
.oracle/checkins/batch-2-r2.md:1640: trailing whitespace.
+++++++++    98	
.oracle/checkins/batch-2-r2.md:1642: trailing whitespace.
+++++++++   101	
.oracle/checkins/batch-2-r2.md:1644: trailing whitespace.
+++++++++   106	
.oracle/checkins/batch-2-r2.md:1646: trailing whitespace.
+++++++++   107	
.oracle/checkins/batch-2-r2.md:1648: trailing whitespace.
+++++++++   110	
.oracle/checkins/batch-2-r2.md:1650: trailing whitespace.
+++++++++   113	
.oracle/checkins/batch-2-r2.md:1652: trailing whitespace.
+++++++++  1349	
.oracle/checkins/batch-2-r2.md:1654: trailing whitespace.
+++++++++  1350	
.oracle/checkins/batch-2-r2.md:1656: trailing whitespace.
+++++++++  1354	
.oracle/checkins/batch-2-r2.md:1658: trailing whitespace.
+++++++++  1365	
.oracle/checkins/batch-2-r2.md:1660: trailing whitespace.
+++++++++  1444	
.oracle/checkins/batch-2-r2.md:1662: trailing whitespace.
+++++++++  1460	
.oracle/checkins/batch-2-r2.md:1664: trailing whitespace.
++++++++  1444	
.oracle/checkins/batch-2-r2.md:1666: trailing whitespace.
++++++++  1460	
.oracle/checkins/batch-2-r2.md:1668: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1670: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1672: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1674: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1676: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1678: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1680: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1682: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1684: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1686: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1688: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1690: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1692: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1694: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1696: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1698: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1700: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1702: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1704: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1706: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1708: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1710: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1712: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1714: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1716: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1718: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1720: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1722: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1724: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1726: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1728: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1730: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1732: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1734: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1736: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1738: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1740: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1742: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1744: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1746: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1748: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1750: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1752: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1754: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1756: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1758: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1760: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1762: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1764: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1766: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1768: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1770: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1772: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1774: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1776: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1778: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1780: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1782: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1784: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1786: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1788: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1790: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1792: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1794: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1796: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1798: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1800: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1802: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1804: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1806: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1808: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1810: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1812: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1814: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1816: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1818: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1820: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1822: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1824: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1826: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1828: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1830: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1832: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1834: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1836: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1838: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1840: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1842: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1844: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1846: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1848: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1850: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1852: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1854: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1856: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1858: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1860: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1862: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1864: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1866: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1868: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1870: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1872: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1874: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1876: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1878: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1880: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1882: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1884: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1886: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1888: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1890: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1892: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1894: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1896: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1898: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:1900: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r2.md:1902: trailing whitespace.
++++++++     4	
.oracle/checkins/batch-2-r2.md:1904: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r2.md:1906: trailing whitespace.
++++++++    11	
.oracle/checkins/batch-2-r2.md:1908: trailing whitespace.
++++++++    28	
.oracle/checkins/batch-2-r2.md:1910: trailing whitespace.
++++++++    29	
.oracle/checkins/batch-2-r2.md:1912: trailing whitespace.
++++++++    32	
.oracle/checkins/batch-2-r2.md:1914: trailing whitespace.
++++++++    33	
.oracle/checkins/batch-2-r2.md:1916: trailing whitespace.
++++++++    38	
.oracle/checkins/batch-2-r2.md:1918: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r2.md:1920: trailing whitespace.
++++++++    41	
.oracle/checkins/batch-2-r2.md:1922: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r2.md:1924: trailing whitespace.
++++++++    54	
.oracle/checkins/batch-2-r2.md:1926: trailing whitespace.
++++++++    81	
.oracle/checkins/batch-2-r2.md:1928: trailing whitespace.
++++++++    82	
.oracle/checkins/batch-2-r2.md:1930: trailing whitespace.
++++++++    85	
.oracle/checkins/batch-2-r2.md:1932: trailing whitespace.
++++++++    92	
.oracle/checkins/batch-2-r2.md:1934: trailing whitespace.
++++++++    93	
.oracle/checkins/batch-2-r2.md:1936: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r2.md:1938: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r2.md:1940: trailing whitespace.
++++++++   173	
.oracle/checkins/batch-2-r2.md:1942: trailing whitespace.
++++++++   174	
.oracle/checkins/batch-2-r2.md:1944: trailing whitespace.
++++++++   248	
.oracle/checkins/batch-2-r2.md:1946: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r2.md:1948: trailing whitespace.
++++++++   260	
.oracle/checkins/batch-2-r2.md:1950: trailing whitespace.
++++++++   261	
.oracle/checkins/batch-2-r2.md:1952: trailing whitespace.
++++++++   283	
.oracle/checkins/batch-2-r2.md:1954: trailing whitespace.
++++++++   284	
.oracle/checkins/batch-2-r2.md:1956: trailing whitespace.
++++++++   300	
.oracle/checkins/batch-2-r2.md:1958: trailing whitespace.
++++++++   307	
.oracle/checkins/batch-2-r2.md:1960: trailing whitespace.
++++++++   328	
.oracle/checkins/batch-2-r2.md:1962: trailing whitespace.
++++++++   355	
.oracle/checkins/batch-2-r2.md:1964: trailing whitespace.
++++++++   356	
.oracle/checkins/batch-2-r2.md:1966: trailing whitespace.
++++++++   359	
.oracle/checkins/batch-2-r2.md:1968: trailing whitespace.
++++++++   361	
.oracle/checkins/batch-2-r2.md:1970: trailing whitespace.
++++++++   362	
.oracle/checkins/batch-2-r2.md:1972: trailing whitespace.
++++++++   365	
.oracle/checkins/batch-2-r2.md:1974: trailing whitespace.
++++++++   369	
.oracle/checkins/batch-2-r2.md:1976: trailing whitespace.
++++++++   370	
.oracle/checkins/batch-2-r2.md:1978: trailing whitespace.
++++++++   373	
.oracle/checkins/batch-2-r2.md:1980: trailing whitespace.
++++++++   378	
.oracle/checkins/batch-2-r2.md:1982: trailing whitespace.
++++++++   379	
.oracle/checkins/batch-2-r2.md:1984: trailing whitespace.
++++++++   382	
.oracle/checkins/batch-2-r2.md:1986: trailing whitespace.
++++++++   384	
.oracle/checkins/batch-2-r2.md:1988: trailing whitespace.
++++++++   385	
.oracle/checkins/batch-2-r2.md:1990: trailing whitespace.
++++++++   651	
.oracle/checkins/batch-2-r2.md:1992: trailing whitespace.
++++++++   652	
.oracle/checkins/batch-2-r2.md:1994: trailing whitespace.
++++++++   683	
.oracle/checkins/batch-2-r2.md:1996: trailing whitespace.
++++++++   693	
.oracle/checkins/batch-2-r2.md:1998: trailing whitespace.
++++++++   729	
.oracle/checkins/batch-2-r2.md:2000: trailing whitespace.
++++++++   730	
.oracle/checkins/batch-2-r2.md:2002: trailing whitespace.
++++++++   748	
.oracle/checkins/batch-2-r2.md:2004: trailing whitespace.
++++++++   749	
.oracle/checkins/batch-2-r2.md:2006: trailing whitespace.
++++++++   785	
.oracle/checkins/batch-2-r2.md:2008: trailing whitespace.
++++++++   786	
.oracle/checkins/batch-2-r2.md:2010: trailing whitespace.
++++++++   800	
.oracle/checkins/batch-2-r2.md:2012: trailing whitespace.
++++++++   801	
.oracle/checkins/batch-2-r2.md:2014: trailing whitespace.
++++++++   817	
.oracle/checkins/batch-2-r2.md:2016: trailing whitespace.
++++++++   818	
.oracle/checkins/batch-2-r2.md:2018: trailing whitespace.
++++++++   914	
.oracle/checkins/batch-2-r2.md:2020: trailing whitespace.
++++++++   915	
.oracle/checkins/batch-2-r2.md:2022: trailing whitespace.
++++++++  1001	
.oracle/checkins/batch-2-r2.md:2024: trailing whitespace.
++++++++  1002	
.oracle/checkins/batch-2-r2.md:2026: trailing whitespace.
++++++++  1011	
.oracle/checkins/batch-2-r2.md:2028: trailing whitespace.
++++++++  1012	
.oracle/checkins/batch-2-r2.md:2030: trailing whitespace.
++++++++   285	
.oracle/checkins/batch-2-r2.md:2032: trailing whitespace.
++++++++   294	
.oracle/checkins/batch-2-r2.md:2034: trailing whitespace.
++++++++   295	
.oracle/checkins/batch-2-r2.md:2036: trailing whitespace.
++++++++   302	
.oracle/checkins/batch-2-r2.md:2038: trailing whitespace.
++++++++   303	
.oracle/checkins/batch-2-r2.md:2040: trailing whitespace.
++++++++   312	
.oracle/checkins/batch-2-r2.md:2042: trailing whitespace.
++++++++   313	
.oracle/checkins/batch-2-r2.md:2044: trailing whitespace.
++++++++   330	
.oracle/checkins/batch-2-r2.md:2046: trailing whitespace.
++++++++   331	
.oracle/checkins/batch-2-r2.md:2048: trailing whitespace.
++++++++   826	
.oracle/checkins/batch-2-r2.md:2050: trailing whitespace.
++++++++   868	
.oracle/checkins/batch-2-r2.md:2052: trailing whitespace.
++++++++   875	
.oracle/checkins/batch-2-r2.md:2054: trailing whitespace.
++++++++   878	
.oracle/checkins/batch-2-r2.md:2056: trailing whitespace.
++++++++   892	
.oracle/checkins/batch-2-r2.md:2058: trailing whitespace.
++++++++   893	
.oracle/checkins/batch-2-r2.md:2060: trailing whitespace.
++++++++   897	
.oracle/checkins/batch-2-r2.md:2062: trailing whitespace.
++++++++   905	
.oracle/checkins/batch-2-r2.md:2064: trailing whitespace.
++++++++   936	
.oracle/checkins/batch-2-r2.md:2066: trailing whitespace.
++++++++   949	
.oracle/checkins/batch-2-r2.md:2068: trailing whitespace.
++++++++   980	
.oracle/checkins/batch-2-r2.md:2070: trailing whitespace.
++++++++   987	
.oracle/checkins/batch-2-r2.md:2072: trailing whitespace.
++++++++   988	
.oracle/checkins/batch-2-r2.md:2074: trailing whitespace.
++++++++   992	
.oracle/checkins/batch-2-r2.md:2076: trailing whitespace.
++++++++  1000	
.oracle/checkins/batch-2-r2.md:2078: trailing whitespace.
++++++++   440	
.oracle/checkins/batch-2-r2.md:2080: trailing whitespace.
++++++++   441	
.oracle/checkins/batch-2-r2.md:2082: trailing whitespace.
++++++++   445	
.oracle/checkins/batch-2-r2.md:2084: trailing whitespace.
++++++++   459	
.oracle/checkins/batch-2-r2.md:2086: trailing whitespace.
++++++++   507	
.oracle/checkins/batch-2-r2.md:2088: trailing whitespace.
++++++++   511	
.oracle/checkins/batch-2-r2.md:2090: trailing whitespace.
++++++++   530	
.oracle/checkins/batch-2-r2.md:2092: trailing whitespace.
++++++++   563	
.oracle/checkins/batch-2-r2.md:2094: trailing whitespace.
++++++++   564	
.oracle/checkins/batch-2-r2.md:2096: trailing whitespace.
++++++++   571	
.oracle/checkins/batch-2-r2.md:2098: trailing whitespace.
++++++++   576	
.oracle/checkins/batch-2-r2.md:2100: trailing whitespace.
++++++++   582	
.oracle/checkins/batch-2-r2.md:2102: trailing whitespace.
++++++++   583	
.oracle/checkins/batch-2-r2.md:2104: trailing whitespace.
++++++++   587	
.oracle/checkins/batch-2-r2.md:2106: trailing whitespace.
++++++++   592	
.oracle/checkins/batch-2-r2.md:2108: trailing whitespace.
++++++++   604	
.oracle/checkins/batch-2-r2.md:2110: trailing whitespace.
++++++++   609	
.oracle/checkins/batch-2-r2.md:2112: trailing whitespace.
++++++++   621	
.oracle/checkins/batch-2-r2.md:2114: trailing whitespace.
++++++++   633	
.oracle/checkins/batch-2-r2.md:2116: trailing whitespace.
++++++++   634	
.oracle/checkins/batch-2-r2.md:2118: trailing whitespace.
++++++++   655	
.oracle/checkins/batch-2-r2.md:2120: trailing whitespace.
++++++++   656	
.oracle/checkins/batch-2-r2.md:2122: trailing whitespace.
++++++++   660	
.oracle/checkins/batch-2-r2.md:2124: trailing whitespace.
++++++++   667	
.oracle/checkins/batch-2-r2.md:2126: trailing whitespace.
++++++++   690	
.oracle/checkins/batch-2-r2.md:2128: trailing whitespace.
++++++++   702	
.oracle/checkins/batch-2-r2.md:2130: trailing whitespace.
++++++++   717	
.oracle/checkins/batch-2-r2.md:2132: trailing whitespace.
++++++++   225	
.oracle/checkins/batch-2-r2.md:2134: trailing whitespace.
++++++++   230	
.oracle/checkins/batch-2-r2.md:2136: trailing whitespace.
++++++++   238	
.oracle/checkins/batch-2-r2.md:2138: trailing whitespace.
++++++++   240	
.oracle/checkins/batch-2-r2.md:2140: trailing whitespace.
++++++++   243	
.oracle/checkins/batch-2-r2.md:2142: trailing whitespace.
++++++++   251	
.oracle/checkins/batch-2-r2.md:2144: trailing whitespace.
++++++++   255	
.oracle/checkins/batch-2-r2.md:2146: trailing whitespace.
++++++++   257	
.oracle/checkins/batch-2-r2.md:2148: trailing whitespace.
++++++++   262	
.oracle/checkins/batch-2-r2.md:2150: trailing whitespace.
++++++++   274	
.oracle/checkins/batch-2-r2.md:2152: trailing whitespace.
++++++++   276	
.oracle/checkins/batch-2-r2.md:2154: trailing whitespace.
++++++++   280	
.oracle/checkins/batch-2-r2.md:2156: trailing whitespace.
++++++++   290	
.oracle/checkins/batch-2-r2.md:2158: trailing whitespace.
++++++++   292	
.oracle/checkins/batch-2-r2.md:2160: trailing whitespace.
++++++++   461	
.oracle/checkins/batch-2-r2.md:2162: trailing whitespace.
++++++++   463	
.oracle/checkins/batch-2-r2.md:2164: trailing whitespace.
++++++++   465	
.oracle/checkins/batch-2-r2.md:2166: trailing whitespace.
++++++++   470	
.oracle/checkins/batch-2-r2.md:2168: trailing whitespace.
++++++++   492	
.oracle/checkins/batch-2-r2.md:2170: trailing whitespace.
++++++++   502	
.oracle/checkins/batch-2-r2.md:2172: trailing whitespace.
++++++++   504	
.oracle/checkins/batch-2-r2.md:2174: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r2.md:2176: trailing whitespace.
++++++++     4	
.oracle/checkins/batch-2-r2.md:2178: trailing whitespace.
++++++++     6	
.oracle/checkins/batch-2-r2.md:2180: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r2.md:2182: trailing whitespace.
++++++++    17	
.oracle/checkins/batch-2-r2.md:2184: trailing whitespace.
++++++++    19	
.oracle/checkins/batch-2-r2.md:2186: trailing whitespace.
++++++++    25	
.oracle/checkins/batch-2-r2.md:2188: trailing whitespace.
++++++++    27	
.oracle/checkins/batch-2-r2.md:2190: trailing whitespace.
++++++++    29	
.oracle/checkins/batch-2-r2.md:2192: trailing whitespace.
++++++++    31	
.oracle/checkins/batch-2-r2.md:2194: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r2.md:2196: trailing whitespace.
++++++++    42	
.oracle/checkins/batch-2-r2.md:2198: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r2.md:2200: trailing whitespace.
++++++++    51	
.oracle/checkins/batch-2-r2.md:2202: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r2.md:2204: trailing whitespace.
++++++++    55	
.oracle/checkins/batch-2-r2.md:2206: trailing whitespace.
++++++++    63	
.oracle/checkins/batch-2-r2.md:2208: trailing whitespace.
++++++++    65	
.oracle/checkins/batch-2-r2.md:2210: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r2.md:2212: trailing whitespace.
++++++++    74	
.oracle/checkins/batch-2-r2.md:2214: trailing whitespace.
++++++++    76	
.oracle/checkins/batch-2-r2.md:2216: trailing whitespace.
++++++++    78	
.oracle/checkins/batch-2-r2.md:2218: trailing whitespace.
++++++++    86	
.oracle/checkins/batch-2-r2.md:2220: trailing whitespace.
++++++++    88	
.oracle/checkins/batch-2-r2.md:2222: trailing whitespace.
++++++++    94	
.oracle/checkins/batch-2-r2.md:2224: trailing whitespace.
++++++++    96	
.oracle/checkins/batch-2-r2.md:2226: trailing whitespace.
++++++++    98	
.oracle/checkins/batch-2-r2.md:2228: trailing whitespace.
++++++++   100	
.oracle/checkins/batch-2-r2.md:2230: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:2232: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:2234: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:2236: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:2238: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:2240: trailing whitespace.
++++++++ 
.oracle/checkins/batch-2-r2.md:2242: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r2.md:2244: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r2.md:2246: trailing whitespace.
++++++++   168	
.oracle/checkins/batch-2-r2.md:2248: trailing whitespace.
++++++++   169	
.oracle/checkins/batch-2-r2.md:2250: trailing whitespace.
++++++++   236	
.oracle/checkins/batch-2-r2.md:2252: trailing whitespace.
++++++++   237	
.oracle/checkins/batch-2-r2.md:2254: trailing whitespace.
++++++++   248	
.oracle/checkins/batch-2-r2.md:2256: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r2.md:2258: trailing whitespace.
++++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-2-r2.md:2260: trailing whitespace.
++++++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-2-r2.md:2262: trailing whitespace.
++++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-2-r2.md:2264: trailing whitespace.
++++++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-2-r2.md:2266: trailing whitespace.
++++++++     2	
.oracle/checkins/batch-2-r2.md:2268: trailing whitespace.
++++++++     8	
.oracle/checkins/batch-2-r2.md:2270: trailing whitespace.
++++++++    11	
.oracle/checkins/batch-2-r2.md:2272: trailing whitespace.
++++++++    20	
.oracle/checkins/batch-2-r2.md:2274: trailing whitespace.
++++++++    21	
.oracle/checkins/batch-2-r2.md:2276: trailing whitespace.
++++++++    48	
.oracle/checkins/batch-2-r2.md:2278: trailing whitespace.
++++++++    49	
.oracle/checkins/batch-2-r2.md:2280: trailing whitespace.
++++++++    52	
.oracle/checkins/batch-2-r2.md:2282: trailing whitespace.
++++++++    53	
.oracle/checkins/batch-2-r2.md:2284: trailing whitespace.
++++++++    56	
.oracle/checkins/batch-2-r2.md:2286: trailing whitespace.
++++++++    57	
.oracle/checkins/batch-2-r2.md:2288: trailing whitespace.
++++++++    60	
.oracle/checkins/batch-2-r2.md:2290: trailing whitespace.
++++++++    61	
.oracle/checkins/batch-2-r2.md:2292: trailing whitespace.
++++++++    72	
.oracle/checkins/batch-2-r2.md:2294: trailing whitespace.
++++++++    73	
.oracle/checkins/batch-2-r2.md:2296: trailing whitespace.
++++++++    81	
.oracle/checkins/batch-2-r2.md:2298: trailing whitespace.
++++++++    88	
.oracle/checkins/batch-2-r2.md:2300: trailing whitespace.
++++++++    89	
.oracle/checkins/batch-2-r2.md:2302: trailing whitespace.
++++++++    96	
.oracle/checkins/batch-2-r2.md:2304: trailing whitespace.
++++++++    97	
.oracle/checkins/batch-2-r2.md:2306: trailing whitespace.
++++++++   105	
.oracle/checkins/batch-2-r2.md:2308: trailing whitespace.
++++++++   106	
.oracle/checkins/batch-2-r2.md:2310: trailing whitespace.
++++++++   113	
.oracle/checkins/batch-2-r2.md:2312: trailing whitespace.
++++++++   114	
.oracle/checkins/batch-2-r2.md:2314: trailing whitespace.
++++++++   122	
.oracle/checkins/batch-2-r2.md:2316: trailing whitespace.
++++++++   123	
.oracle/checkins/batch-2-r2.md:2318: trailing whitespace.
++++++++   131	
.oracle/checkins/batch-2-r2.md:2320: trailing whitespace.
++++++++   132	
.oracle/checkins/batch-2-r2.md:2322: trailing whitespace.
++++++++   162	
.oracle/checkins/batch-2-r2.md:2324: trailing whitespace.
++++++++   163	
.oracle/checkins/batch-2-r2.md:2326: trailing whitespace.
++++++++   178	
.oracle/checkins/batch-2-r2.md:2328: trailing whitespace.
++++++++   179	
.oracle/checkins/batch-2-r2.md:2330: trailing whitespace.
++++++++   206	
.oracle/checkins/batch-2-r2.md:2332: trailing whitespace.
++++++++   207	
.oracle/checkins/batch-2-r2.md:2334: trailing whitespace.
++++++++   249	
.oracle/checkins/batch-2-r2.md:2336: trailing whitespace.
++++++++   250	
.oracle/checkins/batch-2-r2.md:2338: trailing whitespace.
++++++++   288	
.oracle/checkins/batch-2-r2.md:2340: trailing whitespace.
++++++++   289	
.oracle/checkins/batch-2-r2.md:2342: trailing whitespace.
++++++++   312	
.oracle/checkins/batch-2-r2.md:2344: trailing whitespace.
++++++++   313	
.oracle/checkins/batch-2-r2.md:2346: trailing whitespace.
++++++++   324	
.oracle/checkins/batch-2-r2.md:2348: trailing whitespace.
++++++++   325	
.oracle/checkins/batch-2-r2.md:2350: trailing whitespace.
++++++++   338	
.oracle/checkins/batch-2-r2.md:2352: trailing whitespace.
++++++++   339	
.oracle/checkins/batch-2-r2.md:2354: trailing whitespace.
++++++++   356	
.oracle/checkins/batch-2-r2.md:2356: trailing whitespace.
++++++++   357	
.oracle/checkins/batch-2-r2.md:2358: trailing whitespace.
++++++++   375	
.oracle/checkins/batch-2-r2.md:2360: trailing whitespace.
++++++++   376	
.oracle/checkins/batch-2-r2.md:2362: trailing whitespace.
++++++++    35	
.oracle/checkins/batch-2-r2.md:2364: trailing whitespace.
++++++++    40	
.oracle/checkins/batch-2-r2.md:2366: trailing whitespace.
++++++++    52	
.oracle/checkins/batch-2-r2.md:2368: trailing whitespace.
++++++++    73	
.oracle/checkins/batch-2-r2.md:2370: trailing whitespace.
++++++++   205	
.oracle/checkins/batch-2-r2.md:2372: trailing whitespace.
++++++++   206	
.oracle/checkins/batch-2-r2.md:2374: trailing whitespace.
++++++++   209	
.oracle/checkins/batch-2-r2.md:2376: trailing whitespace.
++++++++   215	
.oracle/checkins/batch-2-r2.md:2378: trailing whitespace.
++++++++   216	
.oracle/checkins/batch-2-r2.md:2380: trailing whitespace.
++++++++   225	
.oracle/checkins/batch-2-r2.md:2382: trailing whitespace.
++++++++   226	
.oracle/checkins/batch-2-r2.md:2384: trailing whitespace.
++++++++   231	
.oracle/checkins/batch-2-r2.md:2386: trailing whitespace.
++++++++   232	
.oracle/checkins/batch-2-r2.md:2388: trailing whitespace.
++++++++   288	
.oracle/checkins/batch-2-r2.md:2390: trailing whitespace.
++++++++   289	
.oracle/checkins/batch-2-r2.md:2392: trailing whitespace.
++++++++   158	
.oracle/checkins/batch-2-r2.md:2394: trailing whitespace.
++++++++   159	
.oracle/checkins/batch-2-r2.md:2396: trailing whitespace.
++++++++   165	
.oracle/checkins/batch-2-r2.md:2398: trailing whitespace.
++++++++   166	
.oracle/checkins/batch-2-r2.md:2400: trailing whitespace.
++++++++   171	
.oracle/checkins/batch-2-r2.md:2402: trailing whitespace.
++++++++   172	
.oracle/checkins/batch-2-r2.md:2404: trailing whitespace.
++++++++   186	
.oracle/checkins/batch-2-r2.md:2406: trailing whitespace.
++++++++   187	
.oracle/checkins/batch-2-r2.md:2408: trailing whitespace.
++++++++   194	
.oracle/checkins/batch-2-r2.md:2410: trailing whitespace.
++++++++   195	
.oracle/checkins/batch-2-r2.md:2412: trailing whitespace.
++++++++   205	
.oracle/checkins/batch-2-r2.md:2414: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2416: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2418: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2420: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2422: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2424: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2426: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2428: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2430: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2432: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2434: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2436: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2438: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2440: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2442: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2444: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2446: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2448: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2450: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2452: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2454: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2456: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2458: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2460: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2462: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2464: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2466: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2468: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2470: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2472: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2474: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2476: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2478: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2480: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2482: trailing whitespace.
+++++++    92	
.oracle/checkins/batch-2-r2.md:2484: trailing whitespace.
+++++++    93	
.oracle/checkins/batch-2-r2.md:2486: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2-r2.md:2488: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2-r2.md:2490: trailing whitespace.
+++++++   181	
.oracle/checkins/batch-2-r2.md:2492: trailing whitespace.
+++++++   182	
.oracle/checkins/batch-2-r2.md:2494: trailing whitespace.
+++++++   285	
.oracle/checkins/batch-2-r2.md:2496: trailing whitespace.
+++++++   294	
.oracle/checkins/batch-2-r2.md:2498: trailing whitespace.
+++++++   295	
.oracle/checkins/batch-2-r2.md:2500: trailing whitespace.
+++++++   302	
.oracle/checkins/batch-2-r2.md:2502: trailing whitespace.
+++++++   303	
.oracle/checkins/batch-2-r2.md:2504: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2-r2.md:2506: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2-r2.md:2508: trailing whitespace.
+++++++   330	
.oracle/checkins/batch-2-r2.md:2510: trailing whitespace.
+++++++   331	
.oracle/checkins/batch-2-r2.md:2512: trailing whitespace.
+++++++   582	
.oracle/checkins/batch-2-r2.md:2514: trailing whitespace.
+++++++   583	
.oracle/checkins/batch-2-r2.md:2516: trailing whitespace.
+++++++   587	
.oracle/checkins/batch-2-r2.md:2518: trailing whitespace.
+++++++   592	
.oracle/checkins/batch-2-r2.md:2520: trailing whitespace.
+++++++   604	
.oracle/checkins/batch-2-r2.md:2522: trailing whitespace.
+++++++   609	
.oracle/checkins/batch-2-r2.md:2524: trailing whitespace.
+++++++   621	
.oracle/checkins/batch-2-r2.md:2526: trailing whitespace.
+++++++   633	
.oracle/checkins/batch-2-r2.md:2528: trailing whitespace.
+++++++   634	
.oracle/checkins/batch-2-r2.md:2530: trailing whitespace.
+++++++   655	
.oracle/checkins/batch-2-r2.md:2532: trailing whitespace.
+++++++   656	
.oracle/checkins/batch-2-r2.md:2534: trailing whitespace.
+++++++   660	
.oracle/checkins/batch-2-r2.md:2536: trailing whitespace.
+++++++   667	
.oracle/checkins/batch-2-r2.md:2538: trailing whitespace.
+++++++   690	
.oracle/checkins/batch-2-r2.md:2540: trailing whitespace.
+++++++   702	
.oracle/checkins/batch-2-r2.md:2542: trailing whitespace.
+++++++   717	
.oracle/checkins/batch-2-r2.md:2544: trailing whitespace.
+++++++   738	
.oracle/checkins/batch-2-r2.md:2546: trailing whitespace.
+++++++   739	
.oracle/checkins/batch-2-r2.md:2548: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2550: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2552: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2554: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2556: trailing whitespace.
+++++++   520	
.oracle/checkins/batch-2-r2.md:2558: trailing whitespace.
+++++++   539	
.oracle/checkins/batch-2-r2.md:2560: trailing whitespace.
+++++++   540	
.oracle/checkins/batch-2-r2.md:2562: trailing whitespace.
+++++++   550	
.oracle/checkins/batch-2-r2.md:2564: trailing whitespace.
+++++++   551	
.oracle/checkins/batch-2-r2.md:2566: trailing whitespace.
+++++++   613	
.oracle/checkins/batch-2-r2.md:2568: trailing whitespace.
+++++++   617	
.oracle/checkins/batch-2-r2.md:2570: trailing whitespace.
+++++++   618	
.oracle/checkins/batch-2-r2.md:2572: trailing whitespace.
+++++++   631	
.oracle/checkins/batch-2-r2.md:2574: trailing whitespace.
+++++++   632	
.oracle/checkins/batch-2-r2.md:2576: trailing whitespace.
+++++++   635	
.oracle/checkins/batch-2-r2.md:2578: trailing whitespace.
+++++++   644	
.oracle/checkins/batch-2-r2.md:2580: trailing whitespace.
+++++++   645	
.oracle/checkins/batch-2-r2.md:2582: trailing whitespace.
+++++++   651	
.oracle/checkins/batch-2-r2.md:2584: trailing whitespace.
+++++++   652	
.oracle/checkins/batch-2-r2.md:2586: trailing whitespace.
+++++++   683	
.oracle/checkins/batch-2-r2.md:2588: trailing whitespace.
+++++++   693	
.oracle/checkins/batch-2-r2.md:2590: trailing whitespace.
+++++++   729	
.oracle/checkins/batch-2-r2.md:2592: trailing whitespace.
+++++++   730	
.oracle/checkins/batch-2-r2.md:2594: trailing whitespace.
+++++++   748	
.oracle/checkins/batch-2-r2.md:2596: trailing whitespace.
+++++++   749	
.oracle/checkins/batch-2-r2.md:2598: trailing whitespace.
+++++++   785	
.oracle/checkins/batch-2-r2.md:2600: trailing whitespace.
+++++++   786	
.oracle/checkins/batch-2-r2.md:2602: trailing whitespace.
+++++++   800	
.oracle/checkins/batch-2-r2.md:2604: trailing whitespace.
+++++++   801	
.oracle/checkins/batch-2-r2.md:2606: trailing whitespace.
+++++++   817	
.oracle/checkins/batch-2-r2.md:2608: trailing whitespace.
+++++++   818	
.oracle/checkins/batch-2-r2.md:2610: trailing whitespace.
+++++++   914	
.oracle/checkins/batch-2-r2.md:2612: trailing whitespace.
+++++++   915	
.oracle/checkins/batch-2-r2.md:2614: trailing whitespace.
+++++++  1014	
.oracle/checkins/batch-2-r2.md:2616: trailing whitespace.
+++++++  1015	
.oracle/checkins/batch-2-r2.md:2618: trailing whitespace.
+++++++  1024	
.oracle/checkins/batch-2-r2.md:2620: trailing whitespace.
+++++++  1025	
.oracle/checkins/batch-2-r2.md:2622: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2-r2.md:2624: trailing whitespace.
+++++++     4	
.oracle/checkins/batch-2-r2.md:2626: trailing whitespace.
+++++++     6	
.oracle/checkins/batch-2-r2.md:2628: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2-r2.md:2630: trailing whitespace.
+++++++    17	
.oracle/checkins/batch-2-r2.md:2632: trailing whitespace.
+++++++    19	
.oracle/checkins/batch-2-r2.md:2634: trailing whitespace.
+++++++    25	
.oracle/checkins/batch-2-r2.md:2636: trailing whitespace.
+++++++    27	
.oracle/checkins/batch-2-r2.md:2638: trailing whitespace.
+++++++    29	
.oracle/checkins/batch-2-r2.md:2640: trailing whitespace.
+++++++    31	
.oracle/checkins/batch-2-r2.md:2642: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2-r2.md:2644: trailing whitespace.
+++++++    42	
.oracle/checkins/batch-2-r2.md:2646: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2-r2.md:2648: trailing whitespace.
+++++++    51	
.oracle/checkins/batch-2-r2.md:2650: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2-r2.md:2652: trailing whitespace.
+++++++    55	
.oracle/checkins/batch-2-r2.md:2654: trailing whitespace.
+++++++    63	
.oracle/checkins/batch-2-r2.md:2656: trailing whitespace.
+++++++    65	
.oracle/checkins/batch-2-r2.md:2658: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2-r2.md:2660: trailing whitespace.
+++++++    74	
.oracle/checkins/batch-2-r2.md:2662: trailing whitespace.
+++++++    76	
.oracle/checkins/batch-2-r2.md:2664: trailing whitespace.
+++++++    78	
.oracle/checkins/batch-2-r2.md:2666: trailing whitespace.
+++++++    86	
.oracle/checkins/batch-2-r2.md:2668: trailing whitespace.
+++++++    88	
.oracle/checkins/batch-2-r2.md:2670: trailing whitespace.
+++++++    94	
.oracle/checkins/batch-2-r2.md:2672: trailing whitespace.
+++++++    96	
.oracle/checkins/batch-2-r2.md:2674: trailing whitespace.
+++++++    98	
.oracle/checkins/batch-2-r2.md:2676: trailing whitespace.
+++++++   100	
.oracle/checkins/batch-2-r2.md:2678: trailing whitespace.
+++++++   109	
.oracle/checkins/batch-2-r2.md:2680: trailing whitespace.
+++++++   111	
.oracle/checkins/batch-2-r2.md:2682: trailing whitespace.
+++++++   119	
.oracle/checkins/batch-2-r2.md:2684: trailing whitespace.
+++++++   121	
.oracle/checkins/batch-2-r2.md:2686: trailing whitespace.
+++++++   123	
.oracle/checkins/batch-2-r2.md:2688: trailing whitespace.
+++++++   125	
.oracle/checkins/batch-2-r2.md:2690: trailing whitespace.
+++++++   133	
.oracle/checkins/batch-2-r2.md:2692: trailing whitespace.
+++++++   135	
.oracle/checkins/batch-2-r2.md:2694: trailing whitespace.
+++++++   142	
.oracle/checkins/batch-2-r2.md:2696: trailing whitespace.
+++++++   144	
.oracle/checkins/batch-2-r2.md:2698: trailing whitespace.
+++++++   146	
.oracle/checkins/batch-2-r2.md:2700: trailing whitespace.
+++++++   148	
.oracle/checkins/batch-2-r2.md:2702: trailing whitespace.
+++++++   159	
.oracle/checkins/batch-2-r2.md:2704: trailing whitespace.
+++++++   161	
.oracle/checkins/batch-2-r2.md:2706: trailing whitespace.
+++++++   168	
.oracle/checkins/batch-2-r2.md:2708: trailing whitespace.
+++++++   170	
.oracle/checkins/batch-2-r2.md:2710: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2-r2.md:2712: trailing whitespace.
+++++++     4	
.oracle/checkins/batch-2-r2.md:2714: trailing whitespace.
+++++++     6	
.oracle/checkins/batch-2-r2.md:2716: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2-r2.md:2718: trailing whitespace.
+++++++    17	
.oracle/checkins/batch-2-r2.md:2720: trailing whitespace.
+++++++    19	
.oracle/checkins/batch-2-r2.md:2722: trailing whitespace.
+++++++    25	
.oracle/checkins/batch-2-r2.md:2724: trailing whitespace.
+++++++    27	
.oracle/checkins/batch-2-r2.md:2726: trailing whitespace.
+++++++    29	
.oracle/checkins/batch-2-r2.md:2728: trailing whitespace.
+++++++    31	
.oracle/checkins/batch-2-r2.md:2730: trailing whitespace.
+++++++    40	
.oracle/checkins/batch-2-r2.md:2732: trailing whitespace.
+++++++    42	
.oracle/checkins/batch-2-r2.md:2734: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2-r2.md:2736: trailing whitespace.
+++++++    51	
.oracle/checkins/batch-2-r2.md:2738: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2-r2.md:2740: trailing whitespace.
+++++++    55	
.oracle/checkins/batch-2-r2.md:2742: trailing whitespace.
+++++++    63	
.oracle/checkins/batch-2-r2.md:2744: trailing whitespace.
+++++++    65	
.oracle/checkins/batch-2-r2.md:2746: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2-r2.md:2748: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2-r2.md:2750: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2-r2.md:2752: trailing whitespace.
+++++++   173	
.oracle/checkins/batch-2-r2.md:2754: trailing whitespace.
+++++++   174	
.oracle/checkins/batch-2-r2.md:2756: trailing whitespace.
+++++++A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-2-r2.md:2758: trailing whitespace.
+++++++   186	
.oracle/checkins/batch-2-r2.md:2760: trailing whitespace.
+++++++   187	
.oracle/checkins/batch-2-r2.md:2762: trailing whitespace.
+++++++   194	
.oracle/checkins/batch-2-r2.md:2764: trailing whitespace.
+++++++   195	
.oracle/checkins/batch-2-r2.md:2766: trailing whitespace.
+++++++   205	
.oracle/checkins/batch-2-r2.md:2768: trailing whitespace.
+++++++   206	
.oracle/checkins/batch-2-r2.md:2770: trailing whitespace.
+++++++   209	
.oracle/checkins/batch-2-r2.md:2772: trailing whitespace.
+++++++   215	
.oracle/checkins/batch-2-r2.md:2774: trailing whitespace.
+++++++   216	
.oracle/checkins/batch-2-r2.md:2776: trailing whitespace.
+++++++   225	
.oracle/checkins/batch-2-r2.md:2778: trailing whitespace.
+++++++   226	
.oracle/checkins/batch-2-r2.md:2780: trailing whitespace.
+++++++   231	
.oracle/checkins/batch-2-r2.md:2782: trailing whitespace.
+++++++   232	
.oracle/checkins/batch-2-r2.md:2784: trailing whitespace.
+++++++   241	
.oracle/checkins/batch-2-r2.md:2786: trailing whitespace.
+++++++   242	
.oracle/checkins/batch-2-r2.md:2788: trailing whitespace.
+++++++   248	
.oracle/checkins/batch-2-r2.md:2790: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2-r2.md:2792: trailing whitespace.
+++++++   262	
.oracle/checkins/batch-2-r2.md:2794: trailing whitespace.
+++++++   263	
.oracle/checkins/batch-2-r2.md:2796: trailing whitespace.
+++++++   268	
.oracle/checkins/batch-2-r2.md:2798: trailing whitespace.
+++++++   269	
.oracle/checkins/batch-2-r2.md:2800: trailing whitespace.
+++++++   276	
.oracle/checkins/batch-2-r2.md:2802: trailing whitespace.
+++++++   277	
.oracle/checkins/batch-2-r2.md:2804: trailing whitespace.
+++++++   284	
.oracle/checkins/batch-2-r2.md:2806: trailing whitespace.
+++++++   285	
.oracle/checkins/batch-2-r2.md:2808: trailing whitespace.
+++++++     2	
.oracle/checkins/batch-2-r2.md:2810: trailing whitespace.
+++++++     8	
.oracle/checkins/batch-2-r2.md:2812: trailing whitespace.
+++++++    11	
.oracle/checkins/batch-2-r2.md:2814: trailing whitespace.
+++++++    20	
.oracle/checkins/batch-2-r2.md:2816: trailing whitespace.
+++++++    21	
.oracle/checkins/batch-2-r2.md:2818: trailing whitespace.
+++++++    48	
.oracle/checkins/batch-2-r2.md:2820: trailing whitespace.
+++++++    49	
.oracle/checkins/batch-2-r2.md:2822: trailing whitespace.
+++++++    52	
.oracle/checkins/batch-2-r2.md:2824: trailing whitespace.
+++++++    53	
.oracle/checkins/batch-2-r2.md:2826: trailing whitespace.
+++++++    56	
.oracle/checkins/batch-2-r2.md:2828: trailing whitespace.
+++++++    57	
.oracle/checkins/batch-2-r2.md:2830: trailing whitespace.
+++++++    60	
.oracle/checkins/batch-2-r2.md:2832: trailing whitespace.
+++++++    61	
.oracle/checkins/batch-2-r2.md:2834: trailing whitespace.
+++++++    72	
.oracle/checkins/batch-2-r2.md:2836: trailing whitespace.
+++++++    73	
.oracle/checkins/batch-2-r2.md:2838: trailing whitespace.
+++++++    81	
.oracle/checkins/batch-2-r2.md:2840: trailing whitespace.
+++++++    88	
.oracle/checkins/batch-2-r2.md:2842: trailing whitespace.
+++++++    89	
.oracle/checkins/batch-2-r2.md:2844: trailing whitespace.
+++++++    96	
.oracle/checkins/batch-2-r2.md:2846: trailing whitespace.
+++++++    97	
.oracle/checkins/batch-2-r2.md:2848: trailing whitespace.
+++++++   105	
.oracle/checkins/batch-2-r2.md:2850: trailing whitespace.
+++++++   106	
.oracle/checkins/batch-2-r2.md:2852: trailing whitespace.
+++++++   113	
.oracle/checkins/batch-2-r2.md:2854: trailing whitespace.
+++++++   114	
.oracle/checkins/batch-2-r2.md:2856: trailing whitespace.
+++++++   122	
.oracle/checkins/batch-2-r2.md:2858: trailing whitespace.
+++++++   123	
.oracle/checkins/batch-2-r2.md:2860: trailing whitespace.
+++++++   131	
.oracle/checkins/batch-2-r2.md:2862: trailing whitespace.
+++++++   132	
.oracle/checkins/batch-2-r2.md:2864: trailing whitespace.
+++++++   162	
.oracle/checkins/batch-2-r2.md:2866: trailing whitespace.
+++++++   163	
.oracle/checkins/batch-2-r2.md:2868: trailing whitespace.
+++++++   178	
.oracle/checkins/batch-2-r2.md:2870: trailing whitespace.
+++++++   179	
.oracle/checkins/batch-2-r2.md:2872: trailing whitespace.
+++++++   206	
.oracle/checkins/batch-2-r2.md:2874: trailing whitespace.
+++++++   207	
.oracle/checkins/batch-2-r2.md:2876: trailing whitespace.
+++++++   249	
.oracle/checkins/batch-2-r2.md:2878: trailing whitespace.
+++++++   250	
.oracle/checkins/batch-2-r2.md:2880: trailing whitespace.
+++++++   288	
.oracle/checkins/batch-2-r2.md:2882: trailing whitespace.
+++++++   289	
.oracle/checkins/batch-2-r2.md:2884: trailing whitespace.
+++++++   312	
.oracle/checkins/batch-2-r2.md:2886: trailing whitespace.
+++++++   313	
.oracle/checkins/batch-2-r2.md:2888: trailing whitespace.
+++++++   324	
.oracle/checkins/batch-2-r2.md:2890: trailing whitespace.
+++++++   325	
.oracle/checkins/batch-2-r2.md:2892: trailing whitespace.
+++++++   338	
.oracle/checkins/batch-2-r2.md:2894: trailing whitespace.
+++++++   339	
.oracle/checkins/batch-2-r2.md:2896: trailing whitespace.
+++++++   356	
.oracle/checkins/batch-2-r2.md:2898: trailing whitespace.
+++++++   357	
.oracle/checkins/batch-2-r2.md:2900: trailing whitespace.
+++++++   375	
.oracle/checkins/batch-2-r2.md:2902: trailing whitespace.
+++++++   376	
.oracle/checkins/batch-2-r2.md:2904: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2906: trailing whitespace.
+++++++ 
.oracle/checkins/batch-2-r2.md:2908: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2910: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2912: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2914: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2916: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2918: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2920: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2922: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2924: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2926: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2928: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2930: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2932: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2934: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2936: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2938: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2940: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2942: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2944: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2946: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2948: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2950: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2952: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2954: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2956: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2958: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2960: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2962: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2964: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2966: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2968: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2970: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2972: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2974: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2976: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2978: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2980: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2982: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2984: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2986: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2988: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2990: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2992: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2994: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2996: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:2998: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3000: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3002: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3004: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3006: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3008: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3010: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3012: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3014: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3016: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3018: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3020: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3022: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3024: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3026: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3028: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3030: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3032: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3034: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3036: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3038: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3040: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3042: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3044: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3046: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3048: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3050: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3052: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3054: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3056: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3058: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3060: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3062: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3064: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3066: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3068: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3070: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3072: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3074: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3076: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3078: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3080: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3082: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3084: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3086: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3088: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3090: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3092: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3094: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3096: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3098: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3100: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3102: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3104: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3106: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3108: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3110: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3112: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3114: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3116: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3118: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3120: trailing whitespace.
++++++   190	
.oracle/checkins/batch-2-r2.md:3122: trailing whitespace.
++++++   191	
.oracle/checkins/batch-2-r2.md:3124: trailing whitespace.
++++++   215	
.oracle/checkins/batch-2-r2.md:3126: trailing whitespace.
++++++   216	
.oracle/checkins/batch-2-r2.md:3128: trailing whitespace.
++++++   225	
.oracle/checkins/batch-2-r2.md:3130: trailing whitespace.
++++++   226	
.oracle/checkins/batch-2-r2.md:3132: trailing whitespace.
++++++   231	
.oracle/checkins/batch-2-r2.md:3134: trailing whitespace.
++++++   232	
.oracle/checkins/batch-2-r2.md:3136: trailing whitespace.
++++++   241	
.oracle/checkins/batch-2-r2.md:3138: trailing whitespace.
++++++   242	
.oracle/checkins/batch-2-r2.md:3140: trailing whitespace.
++++++   248	
.oracle/checkins/batch-2-r2.md:3142: trailing whitespace.
++++++   249	
.oracle/checkins/batch-2-r2.md:3144: trailing whitespace.
++++++   262	
.oracle/checkins/batch-2-r2.md:3146: trailing whitespace.
++++++   263	
.oracle/checkins/batch-2-r2.md:3148: trailing whitespace.
++++++   268	
.oracle/checkins/batch-2-r2.md:3150: trailing whitespace.
++++++   269	
.oracle/checkins/batch-2-r2.md:3152: trailing whitespace.
++++++   276	
.oracle/checkins/batch-2-r2.md:3154: trailing whitespace.
++++++   277	
.oracle/checkins/batch-2-r2.md:3156: trailing whitespace.
++++++   284	
.oracle/checkins/batch-2-r2.md:3158: trailing whitespace.
++++++   285	
.oracle/checkins/batch-2-r2.md:3160: trailing whitespace.
++++++   294	
.oracle/checkins/batch-2-r2.md:3162: trailing whitespace.
++++++   295	
.oracle/checkins/batch-2-r2.md:3164: trailing whitespace.
++++++   302	
.oracle/checkins/batch-2-r2.md:3166: trailing whitespace.
++++++   303	
.oracle/checkins/batch-2-r2.md:3168: trailing whitespace.
++++++   312	
.oracle/checkins/batch-2-r2.md:3170: trailing whitespace.
++++++   313	
.oracle/checkins/batch-2-r2.md:3172: trailing whitespace.
++++++   333	
.oracle/checkins/batch-2-r2.md:3174: trailing whitespace.
++++++   334	
.oracle/checkins/batch-2-r2.md:3176: trailing whitespace.
++++++   375	
.oracle/checkins/batch-2-r2.md:3178: trailing whitespace.
++++++   376	
.oracle/checkins/batch-2-r2.md:3180: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3182: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3184: trailing whitespace.
++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:3186: trailing whitespace.
++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:3188: trailing whitespace.
++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:3190: trailing whitespace.
++++++ 
.oracle/checkins/batch-2-r2.md:3192: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3194: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3196: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3198: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3200: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3202: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3204: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3206: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3208: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3210: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3212: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3214: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3216: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3218: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3220: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3222: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3224: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3226: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3228: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3230: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3232: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3234: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3236: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3238: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3240: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3242: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3244: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3246: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3248: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3250: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3252: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3254: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3256: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3258: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3260: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3262: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3264: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3266: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3268: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3270: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3272: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3274: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3276: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3278: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3280: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3282: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3284: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3286: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3288: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3290: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3292: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3294: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3296: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3298: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3300: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3302: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3304: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3306: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3308: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3310: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3312: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3314: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3316: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3318: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3320: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3322: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3324: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3326: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3328: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3330: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3332: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3334: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3336: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3338: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3340: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3342: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3344: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3346: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3348: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3350: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3352: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3354: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3356: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3358: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3360: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3362: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3364: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3366: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3368: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3370: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3372: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3374: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3376: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3378: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3380: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3382: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3384: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3386: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3388: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3390: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3392: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3394: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3396: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3398: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3400: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3402: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3404: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3406: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3408: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3410: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3412: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3414: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3416: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3418: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3420: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3422: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3424: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3426: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3428: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3430: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3432: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3434: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3436: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3438: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3440: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3442: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3444: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3446: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3448: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3450: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3452: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3454: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3456: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3458: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3460: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3462: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3464: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3466: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3468: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3470: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3472: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3474: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3476: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3478: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3480: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3482: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3484: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3486: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3488: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3490: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3492: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3494: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3496: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3498: trailing whitespace.
++++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:3500: trailing whitespace.
++++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:3502: trailing whitespace.
++++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:3504: trailing whitespace.
+++++ 
.oracle/checkins/batch-2-r2.md:3506: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r2.md:3508: trailing whitespace.
++++ 
.oracle/checkins/batch-2-r2.md:3510: trailing whitespace.
++++    56	
.oracle/checkins/batch-2-r2.md:3512: trailing whitespace.
++++    59	
.oracle/checkins/batch-2-r2.md:3514: trailing whitespace.
++++    72	
.oracle/checkins/batch-2-r2.md:3516: trailing whitespace.
++++    75	
.oracle/checkins/batch-2-r2.md:3518: trailing whitespace.
++++    95	
.oracle/checkins/batch-2-r2.md:3520: trailing whitespace.
++++    99	
.oracle/checkins/batch-2-r2.md:3522: trailing whitespace.
++++     8	
.oracle/checkins/batch-2-r2.md:3524: trailing whitespace.
++++    10	
.oracle/checkins/batch-2-r2.md:3526: trailing whitespace.
++++    12	
.oracle/checkins/batch-2-r2.md:3528: trailing whitespace.
++++    17	
.oracle/checkins/batch-2-r2.md:3530: trailing whitespace.
++++    21	
.oracle/checkins/batch-2-r2.md:3532: trailing whitespace.
++++    25	
.oracle/checkins/batch-2-r2.md:3534: trailing whitespace.
++++    29	
.oracle/checkins/batch-2-r2.md:3536: trailing whitespace.
++++    33	
.oracle/checkins/batch-2-r2.md:3538: trailing whitespace.
++++    37	
.oracle/checkins/batch-2-r2.md:3540: trailing whitespace.
++++    41	
.oracle/checkins/batch-2-r2.md:3542: trailing whitespace.
++++    45	
.oracle/checkins/batch-2-r2.md:3544: trailing whitespace.
++++    48	
.oracle/checkins/batch-2-r2.md:3546: trailing whitespace.
++++    51	
.oracle/checkins/batch-2-r2.md:3548: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:3550: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r2.md:3552: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r2.md:3554: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r2.md:3556: trailing whitespace.
+++    20	
.oracle/checkins/batch-2-r2.md:3558: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r2.md:3560: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r2.md:3562: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r2.md:3564: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:3566: trailing whitespace.
+++    47	
.oracle/checkins/batch-2-r2.md:3568: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r2.md:3570: trailing whitespace.
+++    64	
.oracle/checkins/batch-2-r2.md:3572: trailing whitespace.
+++    65	
.oracle/checkins/batch-2-r2.md:3574: trailing whitespace.
+++    75	
.oracle/checkins/batch-2-r2.md:3576: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r2.md:3578: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:3580: trailing whitespace.
+++    92	
.oracle/checkins/batch-2-r2.md:3582: trailing whitespace.
+++    96	
.oracle/checkins/batch-2-r2.md:3584: trailing whitespace.
+++   108	
.oracle/checkins/batch-2-r2.md:3586: trailing whitespace.
+++   114	
.oracle/checkins/batch-2-r2.md:3588: trailing whitespace.
+++   119	
.oracle/checkins/batch-2-r2.md:3590: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r2.md:3592: trailing whitespace.
+++   130	
.oracle/checkins/batch-2-r2.md:3594: trailing whitespace.
+++   135	
.oracle/checkins/batch-2-r2.md:3596: trailing whitespace.
+++   138	
.oracle/checkins/batch-2-r2.md:3598: trailing whitespace.
+++   149	
.oracle/checkins/batch-2-r2.md:3600: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r2.md:3602: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r2.md:3604: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r2.md:3606: trailing whitespace.
+++   205	
.oracle/checkins/batch-2-r2.md:3608: trailing whitespace.
+++   217	
.oracle/checkins/batch-2-r2.md:3610: trailing whitespace.
+++   218	
.oracle/checkins/batch-2-r2.md:3612: trailing whitespace.
+++   238	
.oracle/checkins/batch-2-r2.md:3614: trailing whitespace.
+++   247	
.oracle/checkins/batch-2-r2.md:3616: trailing whitespace.
+++   253	
.oracle/checkins/batch-2-r2.md:3618: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:3620: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r2.md:3622: trailing whitespace.
+++   265	
.oracle/checkins/batch-2-r2.md:3624: trailing whitespace.
+++   275	
.oracle/checkins/batch-2-r2.md:3626: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r2.md:3628: trailing whitespace.
+++   245	
.oracle/checkins/batch-2-r2.md:3630: trailing whitespace.
+++   255	
.oracle/checkins/batch-2-r2.md:3632: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r2.md:3634: trailing whitespace.
+++   265	
.oracle/checkins/batch-2-r2.md:3636: trailing whitespace.
+++   270	
.oracle/checkins/batch-2-r2.md:3638: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r2.md:3640: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r2.md:3642: trailing whitespace.
+++   296	
.oracle/checkins/batch-2-r2.md:3644: trailing whitespace.
+++   306	
.oracle/checkins/batch-2-r2.md:3646: trailing whitespace.
+++   307	
.oracle/checkins/batch-2-r2.md:3648: trailing whitespace.
+++    14	
.oracle/checkins/batch-2-r2.md:3650: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r2.md:3652: trailing whitespace.
+++    35	
.oracle/checkins/batch-2-r2.md:3654: trailing whitespace.
+++    47	
.oracle/checkins/batch-2-r2.md:3656: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:3658: trailing whitespace.
+++     5	
.oracle/checkins/batch-2-r2.md:3660: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:3662: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r2.md:3664: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r2.md:3666: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r2.md:3668: trailing whitespace.
+++    28	
.oracle/checkins/batch-2-r2.md:3670: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r2.md:3672: trailing whitespace.
+++    32	
.oracle/checkins/batch-2-r2.md:3674: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r2.md:3676: trailing whitespace.
+++    43	
.oracle/checkins/batch-2-r2.md:3678: trailing whitespace.
+++    44	
.oracle/checkins/batch-2-r2.md:3680: trailing whitespace.
+++    50	
.oracle/checkins/batch-2-r2.md:3682: trailing whitespace.
+++    52	
.oracle/checkins/batch-2-r2.md:3684: trailing whitespace.
+++    58	
.oracle/checkins/batch-2-r2.md:3686: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r2.md:3688: trailing whitespace.
+++    70	
.oracle/checkins/batch-2-r2.md:3690: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r2.md:3692: trailing whitespace.
+++    74	
.oracle/checkins/batch-2-r2.md:3694: trailing whitespace.
+++    83	
.oracle/checkins/batch-2-r2.md:3696: trailing whitespace.
+++    85	
.oracle/checkins/batch-2-r2.md:3698: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:3700: trailing whitespace.
+++   108	
.oracle/checkins/batch-2-r2.md:3702: trailing whitespace.
+++   110	
.oracle/checkins/batch-2-r2.md:3704: trailing whitespace.
+++   114	
.oracle/checkins/batch-2-r2.md:3706: trailing whitespace.
+++   115	
.oracle/checkins/batch-2-r2.md:3708: trailing whitespace.
+++   121	
.oracle/checkins/batch-2-r2.md:3710: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r2.md:3712: trailing whitespace.
+++   124	
.oracle/checkins/batch-2-r2.md:3714: trailing whitespace.
+++   137	
.oracle/checkins/batch-2-r2.md:3716: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r2.md:3718: trailing whitespace.
+++   146	
.oracle/checkins/batch-2-r2.md:3720: trailing whitespace.
+++   147	
.oracle/checkins/batch-2-r2.md:3722: trailing whitespace.
+++   157	
.oracle/checkins/batch-2-r2.md:3724: trailing whitespace.
+++   297	
.oracle/checkins/batch-2-r2.md:3726: trailing whitespace.
+++   298	
.oracle/checkins/batch-2-r2.md:3728: trailing whitespace.
+++   301	
.oracle/checkins/batch-2-r2.md:3730: trailing whitespace.
+++   319	
.oracle/checkins/batch-2-r2.md:3732: trailing whitespace.
+++   322	
.oracle/checkins/batch-2-r2.md:3734: trailing whitespace.
+++   325	
.oracle/checkins/batch-2-r2.md:3736: trailing whitespace.
+++   330	
.oracle/checkins/batch-2-r2.md:3738: trailing whitespace.
+++   334	
.oracle/checkins/batch-2-r2.md:3740: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:3742: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r2.md:3744: trailing whitespace.
+++    11	
.oracle/checkins/batch-2-r2.md:3746: trailing whitespace.
+++    15	
.oracle/checkins/batch-2-r2.md:3748: trailing whitespace.
+++    18	
.oracle/checkins/batch-2-r2.md:3750: trailing whitespace.
+++    26	
.oracle/checkins/batch-2-r2.md:3752: trailing whitespace.
+++    28	
.oracle/checkins/batch-2-r2.md:3754: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r2.md:3756: trailing whitespace.
+++    36	
.oracle/checkins/batch-2-r2.md:3758: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r2.md:3760: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r2.md:3762: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:3764: trailing whitespace.
+++    45	
.oracle/checkins/batch-2-r2.md:3766: trailing whitespace.
+++    46	
.oracle/checkins/batch-2-r2.md:3768: trailing whitespace.
+++    58	
.oracle/checkins/batch-2-r2.md:3770: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r2.md:3772: trailing whitespace.
+++    67	
.oracle/checkins/batch-2-r2.md:3774: trailing whitespace.
+++    68	
.oracle/checkins/batch-2-r2.md:3776: trailing whitespace.
+++    87	
.oracle/checkins/batch-2-r2.md:3778: trailing whitespace.
+++    88	
.oracle/checkins/batch-2-r2.md:3780: trailing whitespace.
+++   352	
.oracle/checkins/batch-2-r2.md:3782: trailing whitespace.
+++   353	
.oracle/checkins/batch-2-r2.md:3784: trailing whitespace.
+++   356	
.oracle/checkins/batch-2-r2.md:3786: trailing whitespace.
+++   362	
.oracle/checkins/batch-2-r2.md:3788: trailing whitespace.
+++   363	
.oracle/checkins/batch-2-r2.md:3790: trailing whitespace.
+++   366	
.oracle/checkins/batch-2-r2.md:3792: trailing whitespace.
+++   370	
.oracle/checkins/batch-2-r2.md:3794: trailing whitespace.
+++   371	
.oracle/checkins/batch-2-r2.md:3796: trailing whitespace.
+++   385	
.oracle/checkins/batch-2-r2.md:3798: trailing whitespace.
+++   386	
.oracle/checkins/batch-2-r2.md:3800: trailing whitespace.
+++   390	
.oracle/checkins/batch-2-r2.md:3802: trailing whitespace.
+++   396	
.oracle/checkins/batch-2-r2.md:3804: trailing whitespace.
+++   417	
.oracle/checkins/batch-2-r2.md:3806: trailing whitespace.
+++   421	
.oracle/checkins/batch-2-r2.md:3808: trailing whitespace.
+++   432	
.oracle/checkins/batch-2-r2.md:3810: trailing whitespace.
+++   449	
.oracle/checkins/batch-2-r2.md:3812: trailing whitespace.
+++   450	
.oracle/checkins/batch-2-r2.md:3814: trailing whitespace.
+++   454	
.oracle/checkins/batch-2-r2.md:3816: trailing whitespace.
+++   468	
.oracle/checkins/batch-2-r2.md:3818: trailing whitespace.
+++   664	
.oracle/checkins/batch-2-r2.md:3820: trailing whitespace.
+++   665	
.oracle/checkins/batch-2-r2.md:3822: trailing whitespace.
+++   669	
.oracle/checkins/batch-2-r2.md:3824: trailing whitespace.
+++   676	
.oracle/checkins/batch-2-r2.md:3826: trailing whitespace.
+++   699	
.oracle/checkins/batch-2-r2.md:3828: trailing whitespace.
+++   711	
.oracle/checkins/batch-2-r2.md:3830: trailing whitespace.
+++   726	
.oracle/checkins/batch-2-r2.md:3832: trailing whitespace.
+++   747	
.oracle/checkins/batch-2-r2.md:3834: trailing whitespace.
+++   748	
.oracle/checkins/batch-2-r2.md:3836: trailing whitespace.
+++   755	
.oracle/checkins/batch-2-r2.md:3838: trailing whitespace.
+++   756	
.oracle/checkins/batch-2-r2.md:3840: trailing whitespace.
+++   763	
.oracle/checkins/batch-2-r2.md:3842: trailing whitespace.
+++   764	
.oracle/checkins/batch-2-r2.md:3844: trailing whitespace.
+++   772	
.oracle/checkins/batch-2-r2.md:3846: trailing whitespace.
+++   773	
.oracle/checkins/batch-2-r2.md:3848: trailing whitespace.
+++   777	
.oracle/checkins/batch-2-r2.md:3850: trailing whitespace.
+++   787	
.oracle/checkins/batch-2-r2.md:3852: trailing whitespace.
+++   820	
.oracle/checkins/batch-2-r2.md:3854: trailing whitespace.
+++   835	
.oracle/checkins/batch-2-r2.md:3856: trailing whitespace.
+++  1511	
.oracle/checkins/batch-2-r2.md:3858: trailing whitespace.
+++  1512	
.oracle/checkins/batch-2-r2.md:3860: trailing whitespace.
+++  1527	
.oracle/checkins/batch-2-r2.md:3862: trailing whitespace.
+++  1528	
.oracle/checkins/batch-2-r2.md:3864: trailing whitespace.
+++  1532	
.oracle/checkins/batch-2-r2.md:3866: trailing whitespace.
+++  1540	
.oracle/checkins/batch-2-r2.md:3868: trailing whitespace.
+++  1566	
.oracle/checkins/batch-2-r2.md:3870: trailing whitespace.
+++  1570	
.oracle/checkins/batch-2-r2.md:3872: trailing whitespace.
+++  1572	
.oracle/checkins/batch-2-r2.md:3874: trailing whitespace.
+++  1585	
.oracle/checkins/batch-2-r2.md:3876: trailing whitespace.
+++  1609	
.oracle/checkins/batch-2-r2.md:3878: trailing whitespace.
+++  1616	
.oracle/checkins/batch-2-r2.md:3880: trailing whitespace.
+++  1617	
.oracle/checkins/batch-2-r2.md:3882: trailing whitespace.
+++  1621	
.oracle/checkins/batch-2-r2.md:3884: trailing whitespace.
+++   516	
.oracle/checkins/batch-2-r2.md:3886: trailing whitespace.
+++   520	
.oracle/checkins/batch-2-r2.md:3888: trailing whitespace.
+++   539	
.oracle/checkins/batch-2-r2.md:3890: trailing whitespace.
+++   572	
.oracle/checkins/batch-2-r2.md:3892: trailing whitespace.
+++   573	
.oracle/checkins/batch-2-r2.md:3894: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:3896: trailing whitespace.
+++     4	
.oracle/checkins/batch-2-r2.md:3898: trailing whitespace.
+++    12	
.oracle/checkins/batch-2-r2.md:3900: trailing whitespace.
+++    15	
.oracle/checkins/batch-2-r2.md:3902: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r2.md:3904: trailing whitespace.
+++    25	
.oracle/checkins/batch-2-r2.md:3906: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:3908: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r2.md:3910: trailing whitespace.
+++    49	
.oracle/checkins/batch-2-r2.md:3912: trailing whitespace.
+++    50	
.oracle/checkins/batch-2-r2.md:3914: trailing whitespace.
+++    61	
.oracle/checkins/batch-2-r2.md:3916: trailing whitespace.
+++    62	
.oracle/checkins/batch-2-r2.md:3918: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r2.md:3920: trailing whitespace.
+++    91	
.oracle/checkins/batch-2-r2.md:3922: trailing whitespace.
+++    92	
.oracle/checkins/batch-2-r2.md:3924: trailing whitespace.
+++   109	
.oracle/checkins/batch-2-r2.md:3926: trailing whitespace.
+++   110	
.oracle/checkins/batch-2-r2.md:3928: trailing whitespace.
+++   128	
.oracle/checkins/batch-2-r2.md:3930: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r2.md:3932: trailing whitespace.
+++   152	
.oracle/checkins/batch-2-r2.md:3934: trailing whitespace.
+++   153	
.oracle/checkins/batch-2-r2.md:3936: trailing whitespace.
+++   192	
.oracle/checkins/batch-2-r2.md:3938: trailing whitespace.
+++   193	
.oracle/checkins/batch-2-r2.md:3940: trailing whitespace.
+++   202	
.oracle/checkins/batch-2-r2.md:3942: trailing whitespace.
+++   203	
.oracle/checkins/batch-2-r2.md:3944: trailing whitespace.
+++   223	
.oracle/checkins/batch-2-r2.md:3946: trailing whitespace.
+++   224	
.oracle/checkins/batch-2-r2.md:3948: trailing whitespace.
+++   240	
.oracle/checkins/batch-2-r2.md:3950: trailing whitespace.
+++   241	
.oracle/checkins/batch-2-r2.md:3952: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r2.md:3954: trailing whitespace.
+++   245	
.oracle/checkins/batch-2-r2.md:3956: trailing whitespace.
+++   253	
.oracle/checkins/batch-2-r2.md:3958: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:3960: trailing whitespace.
+++   266	
.oracle/checkins/batch-2-r2.md:3962: trailing whitespace.
+++   267	
.oracle/checkins/batch-2-r2.md:3964: trailing whitespace.
+++   270	
.oracle/checkins/batch-2-r2.md:3966: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r2.md:3968: trailing whitespace.
+++   290	
.oracle/checkins/batch-2-r2.md:3970: trailing whitespace.
+++   291	
.oracle/checkins/batch-2-r2.md:3972: trailing whitespace.
+++   329	
.oracle/checkins/batch-2-r2.md:3974: trailing whitespace.
+++   356	
.oracle/checkins/batch-2-r2.md:3976: trailing whitespace.
+++   357	
.oracle/checkins/batch-2-r2.md:3978: trailing whitespace.
+++   388	
.oracle/checkins/batch-2-r2.md:3980: trailing whitespace.
+++   389	
.oracle/checkins/batch-2-r2.md:3982: trailing whitespace.
+++   436	
.oracle/checkins/batch-2-r2.md:3984: trailing whitespace.
+++   452	
.oracle/checkins/batch-2-r2.md:3986: trailing whitespace.
+++   453	
.oracle/checkins/batch-2-r2.md:3988: trailing whitespace.
+++   474	
.oracle/checkins/batch-2-r2.md:3990: trailing whitespace.
+++   499	
.oracle/checkins/batch-2-r2.md:3992: trailing whitespace.
+++   500	
.oracle/checkins/batch-2-r2.md:3994: trailing whitespace.
+++   527	
.oracle/checkins/batch-2-r2.md:3996: trailing whitespace.
+++   528	
.oracle/checkins/batch-2-r2.md:3998: trailing whitespace.
+++   553	
.oracle/checkins/batch-2-r2.md:4000: trailing whitespace.
+++   554	
.oracle/checkins/batch-2-r2.md:4002: trailing whitespace.
+++   594	
.oracle/checkins/batch-2-r2.md:4004: trailing whitespace.
+++   595	
.oracle/checkins/batch-2-r2.md:4006: trailing whitespace.
+++   622	
.oracle/checkins/batch-2-r2.md:4008: trailing whitespace.
+++   623	
.oracle/checkins/batch-2-r2.md:4010: trailing whitespace.
+++   631	
.oracle/checkins/batch-2-r2.md:4012: trailing whitespace.
+++   637	
.oracle/checkins/batch-2-r2.md:4014: trailing whitespace.
+++   644	
.oracle/checkins/batch-2-r2.md:4016: trailing whitespace.
+++   663	
.oracle/checkins/batch-2-r2.md:4018: trailing whitespace.
+++   673	
.oracle/checkins/batch-2-r2.md:4020: trailing whitespace.
+++   694	
.oracle/checkins/batch-2-r2.md:4022: trailing whitespace.
+++   695	
.oracle/checkins/batch-2-r2.md:4024: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r2.md:4026: trailing whitespace.
+++   139	
.oracle/checkins/batch-2-r2.md:4028: trailing whitespace.
+++   140	
.oracle/checkins/batch-2-r2.md:4030: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r2.md:4032: trailing whitespace.
+++   150	
.oracle/checkins/batch-2-r2.md:4034: trailing whitespace.
+++   151	
.oracle/checkins/batch-2-r2.md:4036: trailing whitespace.
+++   158	
.oracle/checkins/batch-2-r2.md:4038: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:4040: trailing whitespace.
+++   166	
.oracle/checkins/batch-2-r2.md:4042: trailing whitespace.
+++   176	
.oracle/checkins/batch-2-r2.md:4044: trailing whitespace.
+++   183	
.oracle/checkins/batch-2-r2.md:4046: trailing whitespace.
+++   184	
.oracle/checkins/batch-2-r2.md:4048: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r2.md:4050: trailing whitespace.
+++   195	
.oracle/checkins/batch-2-r2.md:4052: trailing whitespace.
+++   196	
.oracle/checkins/batch-2-r2.md:4054: trailing whitespace.
+++   221	
.oracle/checkins/batch-2-r2.md:4056: trailing whitespace.
+++   228	
.oracle/checkins/batch-2-r2.md:4058: trailing whitespace.
+++   229	
.oracle/checkins/batch-2-r2.md:4060: trailing whitespace.
+++   233	
.oracle/checkins/batch-2-r2.md:4062: trailing whitespace.
+++   240	
.oracle/checkins/batch-2-r2.md:4064: trailing whitespace.
+++   241	
.oracle/checkins/batch-2-r2.md:4066: trailing whitespace.
+++   251	
.oracle/checkins/batch-2-r2.md:4068: trailing whitespace.
+++   258	
.oracle/checkins/batch-2-r2.md:4070: trailing whitespace.
+++   259	
.oracle/checkins/batch-2-r2.md:4072: trailing whitespace.
+++   269	
.oracle/checkins/batch-2-r2.md:4074: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r2.md:4076: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r2.md:4078: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:4080: trailing whitespace.
+++     6	
.oracle/checkins/batch-2-r2.md:4082: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:4084: trailing whitespace.
+++    17	
.oracle/checkins/batch-2-r2.md:4086: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r2.md:4088: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r2.md:4090: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r2.md:4092: trailing whitespace.
+++    26	
.oracle/checkins/batch-2-r2.md:4094: trailing whitespace.
+++    27	
.oracle/checkins/batch-2-r2.md:4096: trailing whitespace.
+++    31	
.oracle/checkins/batch-2-r2.md:4098: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r2.md:4100: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:4102: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r2.md:4104: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r2.md:4106: trailing whitespace.
+++    63	
.oracle/checkins/batch-2-r2.md:4108: trailing whitespace.
+++    65	
.oracle/checkins/batch-2-r2.md:4110: trailing whitespace.
+++    69	
.oracle/checkins/batch-2-r2.md:4112: trailing whitespace.
+++    71	
.oracle/checkins/batch-2-r2.md:4114: trailing whitespace.
+++    79	
.oracle/checkins/batch-2-r2.md:4116: trailing whitespace.
+++    85	
.oracle/checkins/batch-2-r2.md:4118: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:4120: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r2.md:4122: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r2.md:4124: trailing whitespace.
+++    93	
.oracle/checkins/batch-2-r2.md:4126: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:4128: trailing whitespace.
+++   107	
.oracle/checkins/batch-2-r2.md:4130: trailing whitespace.
+++   118	
.oracle/checkins/batch-2-r2.md:4132: trailing whitespace.
+++   119	
.oracle/checkins/batch-2-r2.md:4134: trailing whitespace.
+++   124	
.oracle/checkins/batch-2-r2.md:4136: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r2.md:4138: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r2.md:4140: trailing whitespace.
+++   133	
.oracle/checkins/batch-2-r2.md:4142: trailing whitespace.
+++   150	
.oracle/checkins/batch-2-r2.md:4144: trailing whitespace.
+++   151	
.oracle/checkins/batch-2-r2.md:4146: trailing whitespace.
+++   154	
.oracle/checkins/batch-2-r2.md:4148: trailing whitespace.
+++   160	
.oracle/checkins/batch-2-r2.md:4150: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:4152: trailing whitespace.
+++   169	
.oracle/checkins/batch-2-r2.md:4154: trailing whitespace.
+++   186	
.oracle/checkins/batch-2-r2.md:4156: trailing whitespace.
+++   189	
.oracle/checkins/batch-2-r2.md:4158: trailing whitespace.
+++   195	
.oracle/checkins/batch-2-r2.md:4160: trailing whitespace.
+++   203	
.oracle/checkins/batch-2-r2.md:4162: trailing whitespace.
+++   211	
.oracle/checkins/batch-2-r2.md:4164: trailing whitespace.
+++   217	
.oracle/checkins/batch-2-r2.md:4166: trailing whitespace.
+++   226	
.oracle/checkins/batch-2-r2.md:4168: trailing whitespace.
+++   228	
.oracle/checkins/batch-2-r2.md:4170: trailing whitespace.
+++   229	
.oracle/checkins/batch-2-r2.md:4172: trailing whitespace.
+++   241	
.oracle/checkins/batch-2-r2.md:4174: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r2.md:4176: trailing whitespace.
+++   280	
.oracle/checkins/batch-2-r2.md:4178: trailing whitespace.
+++   281	
.oracle/checkins/batch-2-r2.md:4180: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r2.md:4182: trailing whitespace.
+++   293	
.oracle/checkins/batch-2-r2.md:4184: trailing whitespace.
+++   294	
.oracle/checkins/batch-2-r2.md:4186: trailing whitespace.
+++   301	
.oracle/checkins/batch-2-r2.md:4188: trailing whitespace.
+++   307	
.oracle/checkins/batch-2-r2.md:4190: trailing whitespace.
+++   309	
.oracle/checkins/batch-2-r2.md:4192: trailing whitespace.
+++   310	
.oracle/checkins/batch-2-r2.md:4194: trailing whitespace.
+++   314	
.oracle/checkins/batch-2-r2.md:4196: trailing whitespace.
+++   315	
.oracle/checkins/batch-2-r2.md:4198: trailing whitespace.
+++   323	
.oracle/checkins/batch-2-r2.md:4200: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4202: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4204: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4206: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4208: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4210: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4212: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4214: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4216: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4218: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4220: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:4222: trailing whitespace.
+++     6	
.oracle/checkins/batch-2-r2.md:4224: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:4226: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r2.md:4228: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r2.md:4230: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r2.md:4232: trailing whitespace.
+++    38	
.oracle/checkins/batch-2-r2.md:4234: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r2.md:4236: trailing whitespace.
+++    69	
.oracle/checkins/batch-2-r2.md:4238: trailing whitespace.
+++    70	
.oracle/checkins/batch-2-r2.md:4240: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r2.md:4242: trailing whitespace.
+++    79	
.oracle/checkins/batch-2-r2.md:4244: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:4246: trailing whitespace.
+++   113	
.oracle/checkins/batch-2-r2.md:4248: trailing whitespace.
+++   120	
.oracle/checkins/batch-2-r2.md:4250: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r2.md:4252: trailing whitespace.
+++   144	
.oracle/checkins/batch-2-r2.md:4254: trailing whitespace.
+++   160	
.oracle/checkins/batch-2-r2.md:4256: trailing whitespace.
+++   171	
.oracle/checkins/batch-2-r2.md:4258: trailing whitespace.
+++   202	
.oracle/checkins/batch-2-r2.md:4260: trailing whitespace.
+++   237	
.oracle/checkins/batch-2-r2.md:4262: trailing whitespace.
+++   241	
.oracle/checkins/batch-2-r2.md:4264: trailing whitespace.
+++   248	
.oracle/checkins/batch-2-r2.md:4266: trailing whitespace.
+++   260	
.oracle/checkins/batch-2-r2.md:4268: trailing whitespace.
+++   260	
.oracle/checkins/batch-2-r2.md:4270: trailing whitespace.
+++   261	
.oracle/checkins/batch-2-r2.md:4272: trailing whitespace.
+++   268	
.oracle/checkins/batch-2-r2.md:4274: trailing whitespace.
+++   269	
.oracle/checkins/batch-2-r2.md:4276: trailing whitespace.
+++   285	
.oracle/checkins/batch-2-r2.md:4278: trailing whitespace.
+++   286	
.oracle/checkins/batch-2-r2.md:4280: trailing whitespace.
+++   317	
.oracle/checkins/batch-2-r2.md:4282: trailing whitespace.
+++   318	
.oracle/checkins/batch-2-r2.md:4284: trailing whitespace.
+++   335	
.oracle/checkins/batch-2-r2.md:4286: trailing whitespace.
+++   336	
.oracle/checkins/batch-2-r2.md:4288: trailing whitespace.
+++   339	
.oracle/checkins/batch-2-r2.md:4290: trailing whitespace.
+++   340	
.oracle/checkins/batch-2-r2.md:4292: trailing whitespace.
+++   346	
.oracle/checkins/batch-2-r2.md:4294: trailing whitespace.
+++   347	
.oracle/checkins/batch-2-r2.md:4296: trailing whitespace.
+++   383	
.oracle/checkins/batch-2-r2.md:4298: trailing whitespace.
+++   392	
.oracle/checkins/batch-2-r2.md:4300: trailing whitespace.
+++   393	
.oracle/checkins/batch-2-r2.md:4302: trailing whitespace.
+++   400	
.oracle/checkins/batch-2-r2.md:4304: trailing whitespace.
+++   401	
.oracle/checkins/batch-2-r2.md:4306: trailing whitespace.
+++   418	
.oracle/checkins/batch-2-r2.md:4308: trailing whitespace.
+++   419	
.oracle/checkins/batch-2-r2.md:4310: trailing whitespace.
+++   436	
.oracle/checkins/batch-2-r2.md:4312: trailing whitespace.
+++   437	
.oracle/checkins/batch-2-r2.md:4314: trailing whitespace.
+++   450	
.oracle/checkins/batch-2-r2.md:4316: trailing whitespace.
+++   451	
.oracle/checkins/batch-2-r2.md:4318: trailing whitespace.
+++   456	
.oracle/checkins/batch-2-r2.md:4320: trailing whitespace.
+++   464	
.oracle/checkins/batch-2-r2.md:4322: trailing whitespace.
+++   467	
.oracle/checkins/batch-2-r2.md:4324: trailing whitespace.
+++   471	
.oracle/checkins/batch-2-r2.md:4326: trailing whitespace.
+++   484	
.oracle/checkins/batch-2-r2.md:4328: trailing whitespace.
+++   487	
.oracle/checkins/batch-2-r2.md:4330: trailing whitespace.
+++   490	
.oracle/checkins/batch-2-r2.md:4332: trailing whitespace.
+++   491	
.oracle/checkins/batch-2-r2.md:4334: trailing whitespace.
+++   496	
.oracle/checkins/batch-2-r2.md:4336: trailing whitespace.
+++   506	
.oracle/checkins/batch-2-r2.md:4338: trailing whitespace.
+++   507	
.oracle/checkins/batch-2-r2.md:4340: trailing whitespace.
+++   514	
.oracle/checkins/batch-2-r2.md:4342: trailing whitespace.
+++   515	
.oracle/checkins/batch-2-r2.md:4344: trailing whitespace.
+++   526	
.oracle/checkins/batch-2-r2.md:4346: trailing whitespace.
+++   527	
.oracle/checkins/batch-2-r2.md:4348: trailing whitespace.
+++   546	
.oracle/checkins/batch-2-r2.md:4350: trailing whitespace.
+++   547	
.oracle/checkins/batch-2-r2.md:4352: trailing whitespace.
+++   558	
.oracle/checkins/batch-2-r2.md:4354: trailing whitespace.
+++   559	
.oracle/checkins/batch-2-r2.md:4356: trailing whitespace.
+++   612	
.oracle/checkins/batch-2-r2.md:4358: trailing whitespace.
+++   613	
.oracle/checkins/batch-2-r2.md:4360: trailing whitespace.
+++   638	
.oracle/checkins/batch-2-r2.md:4362: trailing whitespace.
+++   646	
.oracle/checkins/batch-2-r2.md:4364: trailing whitespace.
+++   651	
.oracle/checkins/batch-2-r2.md:4366: trailing whitespace.
+++   678	
.oracle/checkins/batch-2-r2.md:4368: trailing whitespace.
+++   679	
.oracle/checkins/batch-2-r2.md:4370: trailing whitespace.
+++   698	
.oracle/checkins/batch-2-r2.md:4372: trailing whitespace.
+++   699	
.oracle/checkins/batch-2-r2.md:4374: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:4376: trailing whitespace.
+++     4	
.oracle/checkins/batch-2-r2.md:4378: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:4380: trailing whitespace.
+++    47	
.oracle/checkins/batch-2-r2.md:4382: trailing whitespace.
+++    68	
.oracle/checkins/batch-2-r2.md:4384: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:4386: trailing whitespace.
+++    91	
.oracle/checkins/batch-2-r2.md:4388: trailing whitespace.
+++    92	
.oracle/checkins/batch-2-r2.md:4390: trailing whitespace.
+++    95	
.oracle/checkins/batch-2-r2.md:4392: trailing whitespace.
+++    96	
.oracle/checkins/batch-2-r2.md:4394: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:4396: trailing whitespace.
+++   111	
.oracle/checkins/batch-2-r2.md:4398: trailing whitespace.
+++   120	
.oracle/checkins/batch-2-r2.md:4400: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r2.md:4402: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r2.md:4404: trailing whitespace.
+++   136	
.oracle/checkins/batch-2-r2.md:4406: trailing whitespace.
+++   137	
.oracle/checkins/batch-2-r2.md:4408: trailing whitespace.
+++   149	
.oracle/checkins/batch-2-r2.md:4410: trailing whitespace.
+++   150	
.oracle/checkins/batch-2-r2.md:4412: trailing whitespace.
+++   153	
.oracle/checkins/batch-2-r2.md:4414: trailing whitespace.
+++   154	
.oracle/checkins/batch-2-r2.md:4416: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:4418: trailing whitespace.
+++    11	
.oracle/checkins/batch-2-r2.md:4420: trailing whitespace.
+++    13	
.oracle/checkins/batch-2-r2.md:4422: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r2.md:4424: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r2.md:4426: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r2.md:4428: trailing whitespace.
+++    30	
.oracle/checkins/batch-2-r2.md:4430: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r2.md:4432: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r2.md:4434: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r2.md:4436: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:4438: trailing whitespace.
+++    63	
.oracle/checkins/batch-2-r2.md:4440: trailing whitespace.
+++    64	
.oracle/checkins/batch-2-r2.md:4442: trailing whitespace.
+++    74	
.oracle/checkins/batch-2-r2.md:4444: trailing whitespace.
+++    75	
.oracle/checkins/batch-2-r2.md:4446: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r2.md:4448: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r2.md:4450: trailing whitespace.
+++    96	
.oracle/checkins/batch-2-r2.md:4452: trailing whitespace.
+++   100	
.oracle/checkins/batch-2-r2.md:4454: trailing whitespace.
+++   101	
.oracle/checkins/batch-2-r2.md:4456: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r2.md:4458: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r2.md:4460: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r2.md:4462: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r2.md:4464: trailing whitespace.
+++   139	
.oracle/checkins/batch-2-r2.md:4466: trailing whitespace.
+++   142	
.oracle/checkins/batch-2-r2.md:4468: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r2.md:4470: trailing whitespace.
+++   155	
.oracle/checkins/batch-2-r2.md:4472: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r2.md:4474: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r2.md:4476: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:4478: trailing whitespace.
+++   168	
.oracle/checkins/batch-2-r2.md:4480: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r2.md:4482: trailing whitespace.
+++   178	
.oracle/checkins/batch-2-r2.md:4484: trailing whitespace.
+++   181	
.oracle/checkins/batch-2-r2.md:4486: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r2.md:4488: trailing whitespace.
+++   194	
.oracle/checkins/batch-2-r2.md:4490: trailing whitespace.
+++   203	
.oracle/checkins/batch-2-r2.md:4492: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r2.md:4494: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r2.md:4496: trailing whitespace.
+++   211	
.oracle/checkins/batch-2-r2.md:4498: trailing whitespace.
+++   212	
.oracle/checkins/batch-2-r2.md:4500: trailing whitespace.
+++   216	
.oracle/checkins/batch-2-r2.md:4502: trailing whitespace.
+++   219	
.oracle/checkins/batch-2-r2.md:4504: trailing whitespace.
+++   220	
.oracle/checkins/batch-2-r2.md:4506: trailing whitespace.
+++   224	
.oracle/checkins/batch-2-r2.md:4508: trailing whitespace.
+++   227	
.oracle/checkins/batch-2-r2.md:4510: trailing whitespace.
+++   231	
.oracle/checkins/batch-2-r2.md:4512: trailing whitespace.
+++   232	
.oracle/checkins/batch-2-r2.md:4514: trailing whitespace.
+++   239	
.oracle/checkins/batch-2-r2.md:4516: trailing whitespace.
+++   249	
.oracle/checkins/batch-2-r2.md:4518: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:4520: trailing whitespace.
+++   255	
.oracle/checkins/batch-2-r2.md:4522: trailing whitespace.
+++   261	
.oracle/checkins/batch-2-r2.md:4524: trailing whitespace.
+++   275	
.oracle/checkins/batch-2-r2.md:4526: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:4528: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:4530: trailing whitespace.
+++    10	
.oracle/checkins/batch-2-r2.md:4532: trailing whitespace.
+++    30	
.oracle/checkins/batch-2-r2.md:4534: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r2.md:4536: trailing whitespace.
+++    35	
.oracle/checkins/batch-2-r2.md:4538: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r2.md:4540: trailing whitespace.
+++    38	
.oracle/checkins/batch-2-r2.md:4542: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r2.md:4544: trailing whitespace.
+++    50	
.oracle/checkins/batch-2-r2.md:4546: trailing whitespace.
+++    54	
.oracle/checkins/batch-2-r2.md:4548: trailing whitespace.
+++    56	
.oracle/checkins/batch-2-r2.md:4550: trailing whitespace.
+++    57	
.oracle/checkins/batch-2-r2.md:4552: trailing whitespace.
+++    60	
.oracle/checkins/batch-2-r2.md:4554: trailing whitespace.
+++    67	
.oracle/checkins/batch-2-r2.md:4556: trailing whitespace.
+++    68	
.oracle/checkins/batch-2-r2.md:4558: trailing whitespace.
+++    72	
.oracle/checkins/batch-2-r2.md:4560: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r2.md:4562: trailing whitespace.
+++    80	
.oracle/checkins/batch-2-r2.md:4564: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r2.md:4566: trailing whitespace.
+++    84	
.oracle/checkins/batch-2-r2.md:4568: trailing whitespace.
+++    91	
.oracle/checkins/batch-2-r2.md:4570: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:4572: trailing whitespace.
+++   107	
.oracle/checkins/batch-2-r2.md:4574: trailing whitespace.
+++   108	
.oracle/checkins/batch-2-r2.md:4576: trailing whitespace.
+++   116	
.oracle/checkins/batch-2-r2.md:4578: trailing whitespace.
+++   117	
.oracle/checkins/batch-2-r2.md:4580: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r2.md:4582: trailing whitespace.
+++   124	
.oracle/checkins/batch-2-r2.md:4584: trailing whitespace.
+++   127	
.oracle/checkins/batch-2-r2.md:4586: trailing whitespace.
+++   164	
.oracle/checkins/batch-2-r2.md:4588: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:4590: trailing whitespace.
+++   168	
.oracle/checkins/batch-2-r2.md:4592: trailing whitespace.
+++   173	
.oracle/checkins/batch-2-r2.md:4594: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r2.md:4596: trailing whitespace.
+++   195	
.oracle/checkins/batch-2-r2.md:4598: trailing whitespace.
+++   216	
.oracle/checkins/batch-2-r2.md:4600: trailing whitespace.
+++   220	
.oracle/checkins/batch-2-r2.md:4602: trailing whitespace.
+++   258	
.oracle/checkins/batch-2-r2.md:4604: trailing whitespace.
+++   268	
.oracle/checkins/batch-2-r2.md:4606: trailing whitespace.
+++   298	
.oracle/checkins/batch-2-r2.md:4608: trailing whitespace.
+++   347	
.oracle/checkins/batch-2-r2.md:4610: trailing whitespace.
+++   375	
.oracle/checkins/batch-2-r2.md:4612: trailing whitespace.
+++   397	
.oracle/checkins/batch-2-r2.md:4614: trailing whitespace.
+++   427	
.oracle/checkins/batch-2-r2.md:4616: trailing whitespace.
+++   449	
.oracle/checkins/batch-2-r2.md:4618: trailing whitespace.
+++   455	
.oracle/checkins/batch-2-r2.md:4620: trailing whitespace.
+++   473	
.oracle/checkins/batch-2-r2.md:4622: trailing whitespace.
+++   482	
.oracle/checkins/batch-2-r2.md:4624: trailing whitespace.
+++   487	
.oracle/checkins/batch-2-r2.md:4626: trailing whitespace.
+++   490	
.oracle/checkins/batch-2-r2.md:4628: trailing whitespace.
+++   491	
.oracle/checkins/batch-2-r2.md:4630: trailing whitespace.
+++   493	
.oracle/checkins/batch-2-r2.md:4632: trailing whitespace.
+++   494	
.oracle/checkins/batch-2-r2.md:4634: trailing whitespace.
+++   497	
.oracle/checkins/batch-2-r2.md:4636: trailing whitespace.
+++   500	
.oracle/checkins/batch-2-r2.md:4638: trailing whitespace.
+++   507	
.oracle/checkins/batch-2-r2.md:4640: trailing whitespace.
+++   520	
.oracle/checkins/batch-2-r2.md:4642: trailing whitespace.
+++   520	
.oracle/checkins/batch-2-r2.md:4644: trailing whitespace.
+++   544	
.oracle/checkins/batch-2-r2.md:4646: trailing whitespace.
+++   560	
.oracle/checkins/batch-2-r2.md:4648: trailing whitespace.
+++   579	
.oracle/checkins/batch-2-r2.md:4650: trailing whitespace.
+++   587	
.oracle/checkins/batch-2-r2.md:4652: trailing whitespace.
+++   606	
.oracle/checkins/batch-2-r2.md:4654: trailing whitespace.
+++   607	
.oracle/checkins/batch-2-r2.md:4656: trailing whitespace.
+++   611	
.oracle/checkins/batch-2-r2.md:4658: trailing whitespace.
+++   612	
.oracle/checkins/batch-2-r2.md:4660: trailing whitespace.
+++   615	
.oracle/checkins/batch-2-r2.md:4662: trailing whitespace.
+++   618	
.oracle/checkins/batch-2-r2.md:4664: trailing whitespace.
+++   626	
.oracle/checkins/batch-2-r2.md:4666: trailing whitespace.
+++   632	
.oracle/checkins/batch-2-r2.md:4668: trailing whitespace.
+++   636	
.oracle/checkins/batch-2-r2.md:4670: trailing whitespace.
+++   642	
.oracle/checkins/batch-2-r2.md:4672: trailing whitespace.
+++   665	
.oracle/checkins/batch-2-r2.md:4674: trailing whitespace.
+++   674	
.oracle/checkins/batch-2-r2.md:4676: trailing whitespace.
+++   684	
.oracle/checkins/batch-2-r2.md:4678: trailing whitespace.
+++   714	
.oracle/checkins/batch-2-r2.md:4680: trailing whitespace.
+++   717	
.oracle/checkins/batch-2-r2.md:4682: trailing whitespace.
+++   720	
.oracle/checkins/batch-2-r2.md:4684: trailing whitespace.
+++   721	
.oracle/checkins/batch-2-r2.md:4686: trailing whitespace.
+++   313	
.oracle/checkins/batch-2-r2.md:4688: trailing whitespace.
+++   317	
.oracle/checkins/batch-2-r2.md:4690: trailing whitespace.
+++   318	
.oracle/checkins/batch-2-r2.md:4692: trailing whitespace.
+++   327	
.oracle/checkins/batch-2-r2.md:4694: trailing whitespace.
+++   330	
.oracle/checkins/batch-2-r2.md:4696: trailing whitespace.
+++   333	
.oracle/checkins/batch-2-r2.md:4698: trailing whitespace.
+++   336	
.oracle/checkins/batch-2-r2.md:4700: trailing whitespace.
+++   339	
.oracle/checkins/batch-2-r2.md:4702: trailing whitespace.
+++   342	
.oracle/checkins/batch-2-r2.md:4704: trailing whitespace.
+++   348	
.oracle/checkins/batch-2-r2.md:4706: trailing whitespace.
+++   349	
.oracle/checkins/batch-2-r2.md:4708: trailing whitespace.
+++   357	
.oracle/checkins/batch-2-r2.md:4710: trailing whitespace.
+++   361	
.oracle/checkins/batch-2-r2.md:4712: trailing whitespace.
+++   364	
.oracle/checkins/batch-2-r2.md:4714: trailing whitespace.
+++   370	
.oracle/checkins/batch-2-r2.md:4716: trailing whitespace.
+++   378	
.oracle/checkins/batch-2-r2.md:4718: trailing whitespace.
+++   379	
.oracle/checkins/batch-2-r2.md:4720: trailing whitespace.
+++   401	
.oracle/checkins/batch-2-r2.md:4722: trailing whitespace.
+++   402	
.oracle/checkins/batch-2-r2.md:4724: trailing whitespace.
+++   412	
.oracle/checkins/batch-2-r2.md:4726: trailing whitespace.
+++   419	
.oracle/checkins/batch-2-r2.md:4728: trailing whitespace.
+++   420	
.oracle/checkins/batch-2-r2.md:4730: trailing whitespace.
+++   429	
.oracle/checkins/batch-2-r2.md:4732: trailing whitespace.
+++   434	
.oracle/checkins/batch-2-r2.md:4734: trailing whitespace.
+++   437	
.oracle/checkins/batch-2-r2.md:4736: trailing whitespace.
+++   438	
.oracle/checkins/batch-2-r2.md:4738: trailing whitespace.
+++   449	
.oracle/checkins/batch-2-r2.md:4740: trailing whitespace.
+++   454	
.oracle/checkins/batch-2-r2.md:4742: trailing whitespace.
+++   458	
.oracle/checkins/batch-2-r2.md:4744: trailing whitespace.
+++   461	
.oracle/checkins/batch-2-r2.md:4746: trailing whitespace.
+++   462	
.oracle/checkins/batch-2-r2.md:4748: trailing whitespace.
+++   470	
.oracle/checkins/batch-2-r2.md:4750: trailing whitespace.
+++   481	
.oracle/checkins/batch-2-r2.md:4752: trailing whitespace.
+++   482	
.oracle/checkins/batch-2-r2.md:4754: trailing whitespace.
+++   493	
.oracle/checkins/batch-2-r2.md:4756: trailing whitespace.
+++   496	
.oracle/checkins/batch-2-r2.md:4758: trailing whitespace.
+++   503	
.oracle/checkins/batch-2-r2.md:4760: trailing whitespace.
+++   504	
.oracle/checkins/batch-2-r2.md:4762: trailing whitespace.
+++   518	
.oracle/checkins/batch-2-r2.md:4764: trailing whitespace.
+++   525	
.oracle/checkins/batch-2-r2.md:4766: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4768: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4770: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4772: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4774: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4776: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4778: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4780: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4782: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4784: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4786: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4788: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4790: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4792: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4794: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4796: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4798: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4800: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4802: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4804: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4806: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4808: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4810: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4812: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4814: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4816: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4818: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4820: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4822: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4824: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4826: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4828: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4830: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4832: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4834: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4836: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4838: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4840: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4842: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4844: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4846: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4848: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4850: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4852: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4854: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4856: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4858: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4860: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4862: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4864: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4866: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4868: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4870: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4872: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4874: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4876: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4878: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4880: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4882: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4884: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4886: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4888: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4890: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4892: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4894: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4896: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4898: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4900: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4902: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4904: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4906: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4908: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4910: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4912: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4914: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4916: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4918: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4920: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4922: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4924: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4926: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4928: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4930: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4932: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4934: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4936: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4938: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4940: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4942: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4944: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4946: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4948: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4950: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4952: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4954: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4956: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4958: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4960: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4962: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4964: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4966: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4968: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4970: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4972: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4974: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4976: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4978: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4980: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4982: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4984: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4986: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4988: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4990: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4992: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4994: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4996: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:4998: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5000: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5002: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5004: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5006: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5008: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5010: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5012: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5014: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5016: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5018: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5020: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5022: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5024: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5026: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5028: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5030: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5032: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5034: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5036: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5038: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5040: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5042: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5044: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5046: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5048: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5050: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5052: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5054: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5056: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5058: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5060: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5062: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5064: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5066: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5068: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5070: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5072: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5074: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5076: trailing whitespace.
+++ 
.oracle/checkins/batch-2-r2.md:5078: trailing whitespace.
+++     3	
.oracle/checkins/batch-2-r2.md:5080: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r2.md:5082: trailing whitespace.
+++    13	
.oracle/checkins/batch-2-r2.md:5084: trailing whitespace.
+++    15	
.oracle/checkins/batch-2-r2.md:5086: trailing whitespace.
+++    17	
.oracle/checkins/batch-2-r2.md:5088: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r2.md:5090: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r2.md:5092: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:5094: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r2.md:5096: trailing whitespace.
+++    57	
.oracle/checkins/batch-2-r2.md:5098: trailing whitespace.
+++    58	
.oracle/checkins/batch-2-r2.md:5100: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:5102: trailing whitespace.
+++     6	
.oracle/checkins/batch-2-r2.md:5104: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:5106: trailing whitespace.
+++    15	
.oracle/checkins/batch-2-r2.md:5108: trailing whitespace.
+++    16	
.oracle/checkins/batch-2-r2.md:5110: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r2.md:5112: trailing whitespace.
+++    20	
.oracle/checkins/batch-2-r2.md:5114: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r2.md:5116: trailing whitespace.
+++    35	
.oracle/checkins/batch-2-r2.md:5118: trailing whitespace.
+++    38	
.oracle/checkins/batch-2-r2.md:5120: trailing whitespace.
+++    44	
.oracle/checkins/batch-2-r2.md:5122: trailing whitespace.
+++    61	
.oracle/checkins/batch-2-r2.md:5124: trailing whitespace.
+++    62	
.oracle/checkins/batch-2-r2.md:5126: trailing whitespace.
+++    66	
.oracle/checkins/batch-2-r2.md:5128: trailing whitespace.
+++    80	
.oracle/checkins/batch-2-r2.md:5130: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r2.md:5132: trailing whitespace.
+++    83	
.oracle/checkins/batch-2-r2.md:5134: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:5136: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r2.md:5138: trailing whitespace.
+++    94	
.oracle/checkins/batch-2-r2.md:5140: trailing whitespace.
+++    95	
.oracle/checkins/batch-2-r2.md:5142: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:5144: trailing whitespace.
+++   101	
.oracle/checkins/batch-2-r2.md:5146: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:5148: trailing whitespace.
+++   107	
.oracle/checkins/batch-2-r2.md:5150: trailing whitespace.
+++   110	
.oracle/checkins/batch-2-r2.md:5152: trailing whitespace.
+++   113	
.oracle/checkins/batch-2-r2.md:5154: trailing whitespace.
+++   130	
.oracle/checkins/batch-2-r2.md:5156: trailing whitespace.
+++   131	
.oracle/checkins/batch-2-r2.md:5158: trailing whitespace.
+++   134	
.oracle/checkins/batch-2-r2.md:5160: trailing whitespace.
+++     3	
.oracle/checkins/batch-2-r2.md:5162: trailing whitespace.
+++     6	
.oracle/checkins/batch-2-r2.md:5164: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:5166: trailing whitespace.
+++    14	
.oracle/checkins/batch-2-r2.md:5168: trailing whitespace.
+++    20	
.oracle/checkins/batch-2-r2.md:5170: trailing whitespace.
+++    22	
.oracle/checkins/batch-2-r2.md:5172: trailing whitespace.
+++    30	
.oracle/checkins/batch-2-r2.md:5174: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r2.md:5176: trailing whitespace.
+++    49	
.oracle/checkins/batch-2-r2.md:5178: trailing whitespace.
+++    53	
.oracle/checkins/batch-2-r2.md:5180: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r2.md:5182: trailing whitespace.
+++    57	
.oracle/checkins/batch-2-r2.md:5184: trailing whitespace.
+++    58	
.oracle/checkins/batch-2-r2.md:5186: trailing whitespace.
+++    62	
.oracle/checkins/batch-2-r2.md:5188: trailing whitespace.
+++    63	
.oracle/checkins/batch-2-r2.md:5190: trailing whitespace.
+++    66	
.oracle/checkins/batch-2-r2.md:5192: trailing whitespace.
+++    68	
.oracle/checkins/batch-2-r2.md:5194: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r2.md:5196: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r2.md:5198: trailing whitespace.
+++    91	
.oracle/checkins/batch-2-r2.md:5200: trailing whitespace.
+++    92	
.oracle/checkins/batch-2-r2.md:5202: trailing whitespace.
+++    99	
.oracle/checkins/batch-2-r2.md:5204: trailing whitespace.
+++   100	
.oracle/checkins/batch-2-r2.md:5206: trailing whitespace.
+++   104	
.oracle/checkins/batch-2-r2.md:5208: trailing whitespace.
+++   105	
.oracle/checkins/batch-2-r2.md:5210: trailing whitespace.
+++   117	
.oracle/checkins/batch-2-r2.md:5212: trailing whitespace.
+++   118	
.oracle/checkins/batch-2-r2.md:5214: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r2.md:5216: trailing whitespace.
+++   144	
.oracle/checkins/batch-2-r2.md:5218: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:5220: trailing whitespace.
+++   166	
.oracle/checkins/batch-2-r2.md:5222: trailing whitespace.
+++   169	
.oracle/checkins/batch-2-r2.md:5224: trailing whitespace.
+++   190	
.oracle/checkins/batch-2-r2.md:5226: trailing whitespace.
+++   191	
.oracle/checkins/batch-2-r2.md:5228: trailing whitespace.
+++   195	
.oracle/checkins/batch-2-r2.md:5230: trailing whitespace.
+++   196	
.oracle/checkins/batch-2-r2.md:5232: trailing whitespace.
+++   199	
.oracle/checkins/batch-2-r2.md:5234: trailing whitespace.
+++   200	
.oracle/checkins/batch-2-r2.md:5236: trailing whitespace.
+++   203	
.oracle/checkins/batch-2-r2.md:5238: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r2.md:5240: trailing whitespace.
+++   207	
.oracle/checkins/batch-2-r2.md:5242: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r2.md:5244: trailing whitespace.
+++   214	
.oracle/checkins/batch-2-r2.md:5246: trailing whitespace.
+++   215	
.oracle/checkins/batch-2-r2.md:5248: trailing whitespace.
+++   228	
.oracle/checkins/batch-2-r2.md:5250: trailing whitespace.
+++   229	
.oracle/checkins/batch-2-r2.md:5252: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r2.md:5254: trailing whitespace.
+++   245	
.oracle/checkins/batch-2-r2.md:5256: trailing whitespace.
+++   252	
.oracle/checkins/batch-2-r2.md:5258: trailing whitespace.
+++   253	
.oracle/checkins/batch-2-r2.md:5260: trailing whitespace.
+++   257	
.oracle/checkins/batch-2-r2.md:5262: trailing whitespace.
+++   258	
.oracle/checkins/batch-2-r2.md:5264: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r2.md:5266: trailing whitespace.
+++   263	
.oracle/checkins/batch-2-r2.md:5268: trailing whitespace.
+++   286	
.oracle/checkins/batch-2-r2.md:5270: trailing whitespace.
+++   287	
.oracle/checkins/batch-2-r2.md:5272: trailing whitespace.
+++   303	
.oracle/checkins/batch-2-r2.md:5274: trailing whitespace.
+++   304	
.oracle/checkins/batch-2-r2.md:5276: trailing whitespace.
+++   326	
.oracle/checkins/batch-2-r2.md:5278: trailing whitespace.
+++   336	
.oracle/checkins/batch-2-r2.md:5280: trailing whitespace.
+++   340	
.oracle/checkins/batch-2-r2.md:5282: trailing whitespace.
+++   341	
.oracle/checkins/batch-2-r2.md:5284: trailing whitespace.
+++   352	
.oracle/checkins/batch-2-r2.md:5286: trailing whitespace.
+++   355	
.oracle/checkins/batch-2-r2.md:5288: trailing whitespace.
+++   359	
.oracle/checkins/batch-2-r2.md:5290: trailing whitespace.
+++   368	
.oracle/checkins/batch-2-r2.md:5292: trailing whitespace.
+++   372	
.oracle/checkins/batch-2-r2.md:5294: trailing whitespace.
+++   376	
.oracle/checkins/batch-2-r2.md:5296: trailing whitespace.
+++   380	
.oracle/checkins/batch-2-r2.md:5298: trailing whitespace.
+++   384	
.oracle/checkins/batch-2-r2.md:5300: trailing whitespace.
+++   385	
.oracle/checkins/batch-2-r2.md:5302: trailing whitespace.
+++   389	
.oracle/checkins/batch-2-r2.md:5304: trailing whitespace.
+++   390	
.oracle/checkins/batch-2-r2.md:5306: trailing whitespace.
+++   393	
.oracle/checkins/batch-2-r2.md:5308: trailing whitespace.
+++   394	
.oracle/checkins/batch-2-r2.md:5310: trailing whitespace.
+++   407	
.oracle/checkins/batch-2-r2.md:5312: trailing whitespace.
+++   408	
.oracle/checkins/batch-2-r2.md:5314: trailing whitespace.
+++   427	
.oracle/checkins/batch-2-r2.md:5316: trailing whitespace.
+++   428	
.oracle/checkins/batch-2-r2.md:5318: trailing whitespace.
+++   443	
.oracle/checkins/batch-2-r2.md:5320: trailing whitespace.
+++   444	
.oracle/checkins/batch-2-r2.md:5322: trailing whitespace.
+++   458	
.oracle/checkins/batch-2-r2.md:5324: trailing whitespace.
+++   467	
.oracle/checkins/batch-2-r2.md:5326: trailing whitespace.
+++   470	
.oracle/checkins/batch-2-r2.md:5328: trailing whitespace.
+++   522	
.oracle/checkins/batch-2-r2.md:5330: trailing whitespace.
+++   523	
.oracle/checkins/batch-2-r2.md:5332: trailing whitespace.
+++   533	
.oracle/checkins/batch-2-r2.md:5334: trailing whitespace.
+++   546	
.oracle/checkins/batch-2-r2.md:5336: trailing whitespace.
+++   558	
.oracle/checkins/batch-2-r2.md:5338: trailing whitespace.
+++   559	
.oracle/checkins/batch-2-r2.md:5340: trailing whitespace.
+++   120	
.oracle/checkins/batch-2-r2.md:5342: trailing whitespace.
+++   121	
.oracle/checkins/batch-2-r2.md:5344: trailing whitespace.
+++   131	
.oracle/checkins/batch-2-r2.md:5346: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r2.md:5348: trailing whitespace.
+++   153	
.oracle/checkins/batch-2-r2.md:5350: trailing whitespace.
+++   154	
.oracle/checkins/batch-2-r2.md:5352: trailing whitespace.
+++   164	
.oracle/checkins/batch-2-r2.md:5354: trailing whitespace.
+++   170	
.oracle/checkins/batch-2-r2.md:5356: trailing whitespace.
+++   182	
.oracle/checkins/batch-2-r2.md:5358: trailing whitespace.
+++   183	
.oracle/checkins/batch-2-r2.md:5360: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r2.md:5362: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r2.md:5364: trailing whitespace.
+++   194	
.oracle/checkins/batch-2-r2.md:5366: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r2.md:5368: trailing whitespace.
+++   221	
.oracle/checkins/batch-2-r2.md:5370: trailing whitespace.
+++   231	
.oracle/checkins/batch-2-r2.md:5372: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r2.md:5374: trailing whitespace.
+++   249	
.oracle/checkins/batch-2-r2.md:5376: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:5378: trailing whitespace.
+++   256	
.oracle/checkins/batch-2-r2.md:5380: trailing whitespace.
+++   266	
.oracle/checkins/batch-2-r2.md:5382: trailing whitespace.
+++   267	
.oracle/checkins/batch-2-r2.md:5384: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r2.md:5386: trailing whitespace.
+++   272	
.oracle/checkins/batch-2-r2.md:5388: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r2.md:5390: trailing whitespace.
+++   279	
.oracle/checkins/batch-2-r2.md:5392: trailing whitespace.
+++   287	
.oracle/checkins/batch-2-r2.md:5394: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r2.md:5396: trailing whitespace.
+++   292	
.oracle/checkins/batch-2-r2.md:5398: trailing whitespace.
+++   301	
.oracle/checkins/batch-2-r2.md:5400: trailing whitespace.
+++   302	
.oracle/checkins/batch-2-r2.md:5402: trailing whitespace.
+++   311	
.oracle/checkins/batch-2-r2.md:5404: trailing whitespace.
+++   314	
.oracle/checkins/batch-2-r2.md:5406: trailing whitespace.
+++   315	
.oracle/checkins/batch-2-r2.md:5408: trailing whitespace.
+++   319	
.oracle/checkins/batch-2-r2.md:5410: trailing whitespace.
+++   320	
.oracle/checkins/batch-2-r2.md:5412: trailing whitespace.
+++   326	
.oracle/checkins/batch-2-r2.md:5414: trailing whitespace.
+++     3	
.oracle/checkins/batch-2-r2.md:5416: trailing whitespace.
+++     4	
.oracle/checkins/batch-2-r2.md:5418: trailing whitespace.
+++    10	
.oracle/checkins/batch-2-r2.md:5420: trailing whitespace.
+++    12	
.oracle/checkins/batch-2-r2.md:5422: trailing whitespace.
+++    14	
.oracle/checkins/batch-2-r2.md:5424: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r2.md:5426: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r2.md:5428: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r2.md:5430: trailing whitespace.
+++    45	
.oracle/checkins/batch-2-r2.md:5432: trailing whitespace.
+++    46	
.oracle/checkins/batch-2-r2.md:5434: trailing whitespace.
+++    49	
.oracle/checkins/batch-2-r2.md:5436: trailing whitespace.
+++    50	
.oracle/checkins/batch-2-r2.md:5438: trailing whitespace.
+++    53	
.oracle/checkins/batch-2-r2.md:5440: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r2.md:5442: trailing whitespace.
+++    63	
.oracle/checkins/batch-2-r2.md:5444: trailing whitespace.
+++    67	
.oracle/checkins/batch-2-r2.md:5446: trailing whitespace.
+++    72	
.oracle/checkins/batch-2-r2.md:5448: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r2.md:5450: trailing whitespace.
+++    97	
.oracle/checkins/batch-2-r2.md:5452: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:5454: trailing whitespace.
+++   100	
.oracle/checkins/batch-2-r2.md:5456: trailing whitespace.
+++   101	
.oracle/checkins/batch-2-r2.md:5458: trailing whitespace.
+++   105	
.oracle/checkins/batch-2-r2.md:5460: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:5462: trailing whitespace.
+++   109	
.oracle/checkins/batch-2-r2.md:5464: trailing whitespace.
+++   110	
.oracle/checkins/batch-2-r2.md:5466: trailing whitespace.
+++   117	
.oracle/checkins/batch-2-r2.md:5468: trailing whitespace.
+++   118	
.oracle/checkins/batch-2-r2.md:5470: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r2.md:5472: trailing whitespace.
+++   136	
.oracle/checkins/batch-2-r2.md:5474: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r2.md:5476: trailing whitespace.
+++   146	
.oracle/checkins/batch-2-r2.md:5478: trailing whitespace.
+++   149	
.oracle/checkins/batch-2-r2.md:5480: trailing whitespace.
+++   150	
.oracle/checkins/batch-2-r2.md:5482: trailing whitespace.
+++   156	
.oracle/checkins/batch-2-r2.md:5484: trailing whitespace.
+++   157	
.oracle/checkins/batch-2-r2.md:5486: trailing whitespace.
+++   160	
.oracle/checkins/batch-2-r2.md:5488: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r2.md:5490: trailing whitespace.
+++   164	
.oracle/checkins/batch-2-r2.md:5492: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:5494: trailing whitespace.
+++   171	
.oracle/checkins/batch-2-r2.md:5496: trailing whitespace.
+++   172	
.oracle/checkins/batch-2-r2.md:5498: trailing whitespace.
+++   182	
.oracle/checkins/batch-2-r2.md:5500: trailing whitespace.
+++   183	
.oracle/checkins/batch-2-r2.md:5502: trailing whitespace.
+++   186	
.oracle/checkins/batch-2-r2.md:5504: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r2.md:5506: trailing whitespace.
+++   190	
.oracle/checkins/batch-2-r2.md:5508: trailing whitespace.
+++   191	
.oracle/checkins/batch-2-r2.md:5510: trailing whitespace.
+++   201	
.oracle/checkins/batch-2-r2.md:5512: trailing whitespace.
+++   202	
.oracle/checkins/batch-2-r2.md:5514: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r2.md:5516: trailing whitespace.
+++   209	
.oracle/checkins/batch-2-r2.md:5518: trailing whitespace.
+++   216	
.oracle/checkins/batch-2-r2.md:5520: trailing whitespace.
+++   217	
.oracle/checkins/batch-2-r2.md:5522: trailing whitespace.
+++   222	
.oracle/checkins/batch-2-r2.md:5524: trailing whitespace.
+++   223	
.oracle/checkins/batch-2-r2.md:5526: trailing whitespace.
+++   229	
.oracle/checkins/batch-2-r2.md:5528: trailing whitespace.
+++   230	
.oracle/checkins/batch-2-r2.md:5530: trailing whitespace.
+++   234	
.oracle/checkins/batch-2-r2.md:5532: trailing whitespace.
+++   235	
.oracle/checkins/batch-2-r2.md:5534: trailing whitespace.
+++   249	
.oracle/checkins/batch-2-r2.md:5536: trailing whitespace.
+++   250	
.oracle/checkins/batch-2-r2.md:5538: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r2.md:5540: trailing whitespace.
+++   266	
.oracle/checkins/batch-2-r2.md:5542: trailing whitespace.
+++   283	
.oracle/checkins/batch-2-r2.md:5544: trailing whitespace.
+++   284	
.oracle/checkins/batch-2-r2.md:5546: trailing whitespace.
+++   304	
.oracle/checkins/batch-2-r2.md:5548: trailing whitespace.
+++   308	
.oracle/checkins/batch-2-r2.md:5550: trailing whitespace.
+++   344	
.oracle/checkins/batch-2-r2.md:5552: trailing whitespace.
+++   345	
.oracle/checkins/batch-2-r2.md:5554: trailing whitespace.
+++   359	
.oracle/checkins/batch-2-r2.md:5556: trailing whitespace.
+++   360	
.oracle/checkins/batch-2-r2.md:5558: trailing whitespace.
+++   408	
.oracle/checkins/batch-2-r2.md:5560: trailing whitespace.
+++   409	
.oracle/checkins/batch-2-r2.md:5562: trailing whitespace.
+++   430	
.oracle/checkins/batch-2-r2.md:5564: trailing whitespace.
+++   431	
.oracle/checkins/batch-2-r2.md:5566: trailing whitespace.
+++   444	
.oracle/checkins/batch-2-r2.md:5568: trailing whitespace.
+++   445	
.oracle/checkins/batch-2-r2.md:5570: trailing whitespace.
+++   455	
.oracle/checkins/batch-2-r2.md:5572: trailing whitespace.
+++   456	
.oracle/checkins/batch-2-r2.md:5574: trailing whitespace.
+++   486	
.oracle/checkins/batch-2-r2.md:5576: trailing whitespace.
+++   487	
.oracle/checkins/batch-2-r2.md:5578: trailing whitespace.
+++   503	
.oracle/checkins/batch-2-r2.md:5580: trailing whitespace.
+++   504	
.oracle/checkins/batch-2-r2.md:5582: trailing whitespace.
+++     3	
.oracle/checkins/batch-2-r2.md:5584: trailing whitespace.
+++    13	
.oracle/checkins/batch-2-r2.md:5586: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r2.md:5588: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r2.md:5590: trailing whitespace.
+++    38	
.oracle/checkins/batch-2-r2.md:5592: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r2.md:5594: trailing whitespace.
+++    47	
.oracle/checkins/batch-2-r2.md:5596: trailing whitespace.
+++    50	
.oracle/checkins/batch-2-r2.md:5598: trailing whitespace.
+++    51	
.oracle/checkins/batch-2-r2.md:5600: trailing whitespace.
+++    54	
.oracle/checkins/batch-2-r2.md:5602: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r2.md:5604: trailing whitespace.
+++    58	
.oracle/checkins/batch-2-r2.md:5606: trailing whitespace.
+++    64	
.oracle/checkins/batch-2-r2.md:5608: trailing whitespace.
+++    68	
.oracle/checkins/batch-2-r2.md:5610: trailing whitespace.
+++    72	
.oracle/checkins/batch-2-r2.md:5612: trailing whitespace.
+++    77	
.oracle/checkins/batch-2-r2.md:5614: trailing whitespace.
+++    87	
.oracle/checkins/batch-2-r2.md:5616: trailing whitespace.
+++   102	
.oracle/checkins/batch-2-r2.md:5618: trailing whitespace.
+++   103	
.oracle/checkins/batch-2-r2.md:5620: trailing whitespace.
+++   105	
.oracle/checkins/batch-2-r2.md:5622: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:5624: trailing whitespace.
+++   110	
.oracle/checkins/batch-2-r2.md:5626: trailing whitespace.
+++   111	
.oracle/checkins/batch-2-r2.md:5628: trailing whitespace.
+++   114	
.oracle/checkins/batch-2-r2.md:5630: trailing whitespace.
+++   115	
.oracle/checkins/batch-2-r2.md:5632: trailing whitespace.
+++   122	
.oracle/checkins/batch-2-r2.md:5634: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r2.md:5636: trailing whitespace.
+++   128	
.oracle/checkins/batch-2-r2.md:5638: trailing whitespace.
+++   141	
.oracle/checkins/batch-2-r2.md:5640: trailing whitespace.
+++   148	
.oracle/checkins/batch-2-r2.md:5642: trailing whitespace.
+++   151	
.oracle/checkins/batch-2-r2.md:5644: trailing whitespace.
+++   154	
.oracle/checkins/batch-2-r2.md:5646: trailing whitespace.
+++   155	
.oracle/checkins/batch-2-r2.md:5648: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r2.md:5650: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r2.md:5652: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:5654: trailing whitespace.
+++   166	
.oracle/checkins/batch-2-r2.md:5656: trailing whitespace.
+++   169	
.oracle/checkins/batch-2-r2.md:5658: trailing whitespace.
+++   170	
.oracle/checkins/batch-2-r2.md:5660: trailing whitespace.
+++   176	
.oracle/checkins/batch-2-r2.md:5662: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r2.md:5664: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r2.md:5666: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r2.md:5668: trailing whitespace.
+++   191	
.oracle/checkins/batch-2-r2.md:5670: trailing whitespace.
+++   192	
.oracle/checkins/batch-2-r2.md:5672: trailing whitespace.
+++   195	
.oracle/checkins/batch-2-r2.md:5674: trailing whitespace.
+++   196	
.oracle/checkins/batch-2-r2.md:5676: trailing whitespace.
+++   206	
.oracle/checkins/batch-2-r2.md:5678: trailing whitespace.
+++   207	
.oracle/checkins/batch-2-r2.md:5680: trailing whitespace.
+++   213	
.oracle/checkins/batch-2-r2.md:5682: trailing whitespace.
+++   214	
.oracle/checkins/batch-2-r2.md:5684: trailing whitespace.
+++   221	
.oracle/checkins/batch-2-r2.md:5686: trailing whitespace.
+++   222	
.oracle/checkins/batch-2-r2.md:5688: trailing whitespace.
+++   227	
.oracle/checkins/batch-2-r2.md:5690: trailing whitespace.
+++   228	
.oracle/checkins/batch-2-r2.md:5692: trailing whitespace.
+++   234	
.oracle/checkins/batch-2-r2.md:5694: trailing whitespace.
+++   235	
.oracle/checkins/batch-2-r2.md:5696: trailing whitespace.
+++   239	
.oracle/checkins/batch-2-r2.md:5698: trailing whitespace.
+++   240	
.oracle/checkins/batch-2-r2.md:5700: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:5702: trailing whitespace.
+++   255	
.oracle/checkins/batch-2-r2.md:5704: trailing whitespace.
+++   267	
.oracle/checkins/batch-2-r2.md:5706: trailing whitespace.
+++   271	
.oracle/checkins/batch-2-r2.md:5708: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r2.md:5710: trailing whitespace.
+++   289	
.oracle/checkins/batch-2-r2.md:5712: trailing whitespace.
+++   309	
.oracle/checkins/batch-2-r2.md:5714: trailing whitespace.
+++   313	
.oracle/checkins/batch-2-r2.md:5716: trailing whitespace.
+++   349	
.oracle/checkins/batch-2-r2.md:5718: trailing whitespace.
+++   350	
.oracle/checkins/batch-2-r2.md:5720: trailing whitespace.
+++   364	
.oracle/checkins/batch-2-r2.md:5722: trailing whitespace.
+++   365	
.oracle/checkins/batch-2-r2.md:5724: trailing whitespace.
+++   413	
.oracle/checkins/batch-2-r2.md:5726: trailing whitespace.
+++   414	
.oracle/checkins/batch-2-r2.md:5728: trailing whitespace.
+++   435	
.oracle/checkins/batch-2-r2.md:5730: trailing whitespace.
+++   436	
.oracle/checkins/batch-2-r2.md:5732: trailing whitespace.
+++   449	
.oracle/checkins/batch-2-r2.md:5734: trailing whitespace.
+++   450	
.oracle/checkins/batch-2-r2.md:5736: trailing whitespace.
+++   460	
.oracle/checkins/batch-2-r2.md:5738: trailing whitespace.
+++   461	
.oracle/checkins/batch-2-r2.md:5740: trailing whitespace.
+++    17	
.oracle/checkins/batch-2-r2.md:5742: trailing whitespace.
+++    20	
.oracle/checkins/batch-2-r2.md:5744: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r2.md:5746: trailing whitespace.
+++    27	
.oracle/checkins/batch-2-r2.md:5748: trailing whitespace.
+++    35	
.oracle/checkins/batch-2-r2.md:5750: trailing whitespace.
+++    36	
.oracle/checkins/batch-2-r2.md:5752: trailing whitespace.
+++    51	
.oracle/checkins/batch-2-r2.md:5754: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r2.md:5756: trailing whitespace.
+++    78	
.oracle/checkins/batch-2-r2.md:5758: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:5760: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:5762: trailing whitespace.
+++   114	
.oracle/checkins/batch-2-r2.md:5764: trailing whitespace.
+++   122	
.oracle/checkins/batch-2-r2.md:5766: trailing whitespace.
+++   132	
.oracle/checkins/batch-2-r2.md:5768: trailing whitespace.
+++   141	
.oracle/checkins/batch-2-r2.md:5770: trailing whitespace.
+++   147	
.oracle/checkins/batch-2-r2.md:5772: trailing whitespace.
+++   154	
.oracle/checkins/batch-2-r2.md:5774: trailing whitespace.
+++   169	
.oracle/checkins/batch-2-r2.md:5776: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r2.md:5778: trailing whitespace.
+++   190	
.oracle/checkins/batch-2-r2.md:5780: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r2.md:5782: trailing whitespace.
+++   216	
.oracle/checkins/batch-2-r2.md:5784: trailing whitespace.
+++   225	
.oracle/checkins/batch-2-r2.md:5786: trailing whitespace.
+++   245	
.oracle/checkins/batch-2-r2.md:5788: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:5790: trailing whitespace.
+++   263	
.oracle/checkins/batch-2-r2.md:5792: trailing whitespace.
+++   273	
.oracle/checkins/batch-2-r2.md:5794: trailing whitespace.
+++   274	
.oracle/checkins/batch-2-r2.md:5796: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:5798: trailing whitespace.
+++     4	
.oracle/checkins/batch-2-r2.md:5800: trailing whitespace.
+++     8	
.oracle/checkins/batch-2-r2.md:5802: trailing whitespace.
+++    11	
.oracle/checkins/batch-2-r2.md:5804: trailing whitespace.
+++    29	
.oracle/checkins/batch-2-r2.md:5806: trailing whitespace.
+++    30	
.oracle/checkins/batch-2-r2.md:5808: trailing whitespace.
+++    33	
.oracle/checkins/batch-2-r2.md:5810: trailing whitespace.
+++    34	
.oracle/checkins/batch-2-r2.md:5812: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r2.md:5814: trailing whitespace.
+++    41	
.oracle/checkins/batch-2-r2.md:5816: trailing whitespace.
+++    42	
.oracle/checkins/batch-2-r2.md:5818: trailing whitespace.
+++    54	
.oracle/checkins/batch-2-r2.md:5820: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r2.md:5822: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r2.md:5824: trailing whitespace.
+++    83	
.oracle/checkins/batch-2-r2.md:5826: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:5828: trailing whitespace.
+++    93	
.oracle/checkins/batch-2-r2.md:5830: trailing whitespace.
+++    94	
.oracle/checkins/batch-2-r2.md:5832: trailing whitespace.
+++   106	
.oracle/checkins/batch-2-r2.md:5834: trailing whitespace.
+++   107	
.oracle/checkins/batch-2-r2.md:5836: trailing whitespace.
+++   199	
.oracle/checkins/batch-2-r2.md:5838: trailing whitespace.
+++   200	
.oracle/checkins/batch-2-r2.md:5840: trailing whitespace.
+++   276	
.oracle/checkins/batch-2-r2.md:5842: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r2.md:5844: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r2.md:5846: trailing whitespace.
+++   289	
.oracle/checkins/batch-2-r2.md:5848: trailing whitespace.
+++   311	
.oracle/checkins/batch-2-r2.md:5850: trailing whitespace.
+++   312	
.oracle/checkins/batch-2-r2.md:5852: trailing whitespace.
+++   959	
.oracle/checkins/batch-2-r2.md:5854: trailing whitespace.
+++   960	
.oracle/checkins/batch-2-r2.md:5856: trailing whitespace.
+++   963	
.oracle/checkins/batch-2-r2.md:5858: trailing whitespace.
+++   964	
.oracle/checkins/batch-2-r2.md:5860: trailing whitespace.
+++   970	
.oracle/checkins/batch-2-r2.md:5862: trailing whitespace.
+++   975	
.oracle/checkins/batch-2-r2.md:5864: trailing whitespace.
+++   989	
.oracle/checkins/batch-2-r2.md:5866: trailing whitespace.
+++   990	
.oracle/checkins/batch-2-r2.md:5868: trailing whitespace.
+++  1001	
.oracle/checkins/batch-2-r2.md:5870: trailing whitespace.
+++  1002	
.oracle/checkins/batch-2-r2.md:5872: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r2.md:5874: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r2.md:5876: trailing whitespace.
+++    85	
.oracle/checkins/batch-2-r2.md:5878: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:5880: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r2.md:5882: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r2.md:5884: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:5886: trailing whitespace.
+++    99	
.oracle/checkins/batch-2-r2.md:5888: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r2.md:5890: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r2.md:5892: trailing whitespace.
+++   133	
.oracle/checkins/batch-2-r2.md:5894: trailing whitespace.
+++   138	
.oracle/checkins/batch-2-r2.md:5896: trailing whitespace.
+++   169	
.oracle/checkins/batch-2-r2.md:5898: trailing whitespace.
+++   170	
.oracle/checkins/batch-2-r2.md:5900: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r2.md:5902: trailing whitespace.
+++   179	
.oracle/checkins/batch-2-r2.md:5904: trailing whitespace.
+++   180	
.oracle/checkins/batch-2-r2.md:5906: trailing whitespace.
+++   196	
.oracle/checkins/batch-2-r2.md:5908: trailing whitespace.
+++   197	
.oracle/checkins/batch-2-r2.md:5910: trailing whitespace.
+++   218	
.oracle/checkins/batch-2-r2.md:5912: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r2.md:5914: trailing whitespace.
+++   245	
.oracle/checkins/batch-2-r2.md:5916: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:5918: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r2.md:5920: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r2.md:5922: trailing whitespace.
+++    18	
.oracle/checkins/batch-2-r2.md:5924: trailing whitespace.
+++    21	
.oracle/checkins/batch-2-r2.md:5926: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r2.md:5928: trailing whitespace.
+++    28	
.oracle/checkins/batch-2-r2.md:5930: trailing whitespace.
+++    31	
.oracle/checkins/batch-2-r2.md:5932: trailing whitespace.
+++    32	
.oracle/checkins/batch-2-r2.md:5934: trailing whitespace.
+++    36	
.oracle/checkins/batch-2-r2.md:5936: trailing whitespace.
+++    37	
.oracle/checkins/batch-2-r2.md:5938: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:5940: trailing whitespace.
+++    44	
.oracle/checkins/batch-2-r2.md:5942: trailing whitespace.
+++    59	
.oracle/checkins/batch-2-r2.md:5944: trailing whitespace.
+++    66	
.oracle/checkins/batch-2-r2.md:5946: trailing whitespace.
+++    69	
.oracle/checkins/batch-2-r2.md:5948: trailing whitespace.
+++    72	
.oracle/checkins/batch-2-r2.md:5950: trailing whitespace.
+++    73	
.oracle/checkins/batch-2-r2.md:5952: trailing whitespace.
+++    76	
.oracle/checkins/batch-2-r2.md:5954: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r2.md:5956: trailing whitespace.
+++    82	
.oracle/checkins/batch-2-r2.md:5958: trailing whitespace.
+++    85	
.oracle/checkins/batch-2-r2.md:5960: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:5962: trailing whitespace.
+++    89	
.oracle/checkins/batch-2-r2.md:5964: trailing whitespace.
+++    90	
.oracle/checkins/batch-2-r2.md:5966: trailing whitespace.
+++    98	
.oracle/checkins/batch-2-r2.md:5968: trailing whitespace.
+++    99	
.oracle/checkins/batch-2-r2.md:5970: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r2.md:5972: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r2.md:5974: trailing whitespace.
+++   133	
.oracle/checkins/batch-2-r2.md:5976: trailing whitespace.
+++   138	
.oracle/checkins/batch-2-r2.md:5978: trailing whitespace.
+++   169	
.oracle/checkins/batch-2-r2.md:5980: trailing whitespace.
+++   170	
.oracle/checkins/batch-2-r2.md:5982: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r2.md:5984: trailing whitespace.
+++   179	
.oracle/checkins/batch-2-r2.md:5986: trailing whitespace.
+++   180	
.oracle/checkins/batch-2-r2.md:5988: trailing whitespace.
+++   196	
.oracle/checkins/batch-2-r2.md:5990: trailing whitespace.
+++   197	
.oracle/checkins/batch-2-r2.md:5992: trailing whitespace.
+++   218	
.oracle/checkins/batch-2-r2.md:5994: trailing whitespace.
+++   244	
.oracle/checkins/batch-2-r2.md:5996: trailing whitespace.
+++   245	
.oracle/checkins/batch-2-r2.md:5998: trailing whitespace.
+++   255	
.oracle/checkins/batch-2-r2.md:6000: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r2.md:6002: trailing whitespace.
+++   265	
.oracle/checkins/batch-2-r2.md:6004: trailing whitespace.
+++   270	
.oracle/checkins/batch-2-r2.md:6006: trailing whitespace.
+++   277	
.oracle/checkins/batch-2-r2.md:6008: trailing whitespace.
+++   288	
.oracle/checkins/batch-2-r2.md:6010: trailing whitespace.
+++   296	
.oracle/checkins/batch-2-r2.md:6012: trailing whitespace.
+++   306	
.oracle/checkins/batch-2-r2.md:6014: trailing whitespace.
+++   307	
.oracle/checkins/batch-2-r2.md:6016: trailing whitespace.
+++     2	
.oracle/checkins/batch-2-r2.md:6018: trailing whitespace.
+++     7	
.oracle/checkins/batch-2-r2.md:6020: trailing whitespace.
+++     9	
.oracle/checkins/batch-2-r2.md:6022: trailing whitespace.
+++    19	
.oracle/checkins/batch-2-r2.md:6024: trailing whitespace.
+++    20	
.oracle/checkins/batch-2-r2.md:6026: trailing whitespace.
+++    23	
.oracle/checkins/batch-2-r2.md:6028: trailing whitespace.
+++    24	
.oracle/checkins/batch-2-r2.md:6030: trailing whitespace.
+++    39	
.oracle/checkins/batch-2-r2.md:6032: trailing whitespace.
+++    40	
.oracle/checkins/batch-2-r2.md:6034: trailing whitespace.
+++    47	
.oracle/checkins/batch-2-r2.md:6036: trailing whitespace.
+++    55	
.oracle/checkins/batch-2-r2.md:6038: trailing whitespace.
+++    64	
.oracle/checkins/batch-2-r2.md:6040: trailing whitespace.
+++    65	
.oracle/checkins/batch-2-r2.md:6042: trailing whitespace.
+++    75	
.oracle/checkins/batch-2-r2.md:6044: trailing whitespace.
+++    81	
.oracle/checkins/batch-2-r2.md:6046: trailing whitespace.
+++    86	
.oracle/checkins/batch-2-r2.md:6048: trailing whitespace.
+++    92	
.oracle/checkins/batch-2-r2.md:6050: trailing whitespace.
+++    96	
.oracle/checkins/batch-2-r2.md:6052: trailing whitespace.
+++   108	
.oracle/checkins/batch-2-r2.md:6054: trailing whitespace.
+++   114	
.oracle/checkins/batch-2-r2.md:6056: trailing whitespace.
+++   119	
.oracle/checkins/batch-2-r2.md:6058: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r2.md:6060: trailing whitespace.
+++   130	
.oracle/checkins/batch-2-r2.md:6062: trailing whitespace.
+++   135	
.oracle/checkins/batch-2-r2.md:6064: trailing whitespace.
+++   138	
.oracle/checkins/batch-2-r2.md:6066: trailing whitespace.
+++   149	
.oracle/checkins/batch-2-r2.md:6068: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r2.md:6070: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r2.md:6072: trailing whitespace.
+++   187	
.oracle/checkins/batch-2-r2.md:6074: trailing whitespace.
+++   205	
.oracle/checkins/batch-2-r2.md:6076: trailing whitespace.
+++   217	
.oracle/checkins/batch-2-r2.md:6078: trailing whitespace.
+++   218	
.oracle/checkins/batch-2-r2.md:6080: trailing whitespace.
+++   238	
.oracle/checkins/batch-2-r2.md:6082: trailing whitespace.
+++   247	
.oracle/checkins/batch-2-r2.md:6084: trailing whitespace.
+++   253	
.oracle/checkins/batch-2-r2.md:6086: trailing whitespace.
+++   254	
.oracle/checkins/batch-2-r2.md:6088: trailing whitespace.
+++   262	
.oracle/checkins/batch-2-r2.md:6090: trailing whitespace.
+++   265	
.oracle/checkins/batch-2-r2.md:6092: trailing whitespace.
+++   275	
.oracle/checkins/batch-2-r2.md:6094: trailing whitespace.
+++   123	
.oracle/checkins/batch-2-r2.md:6096: trailing whitespace.
+++   125	
.oracle/checkins/batch-2-r2.md:6098: trailing whitespace.
+++   126	
.oracle/checkins/batch-2-r2.md:6100: trailing whitespace.
+++   129	
.oracle/checkins/batch-2-r2.md:6102: trailing whitespace.
+++   139	
.oracle/checkins/batch-2-r2.md:6104: trailing whitespace.
+++   142	
.oracle/checkins/batch-2-r2.md:6106: trailing whitespace.
+++   143	
.oracle/checkins/batch-2-r2.md:6108: trailing whitespace.
+++   155	
.oracle/checkins/batch-2-r2.md:6110: trailing whitespace.
+++   161	
.oracle/checkins/batch-2-r2.md:6112: trailing whitespace.
+++   162	
.oracle/checkins/batch-2-r2.md:6114: trailing whitespace.
+++   165	
.oracle/checkins/batch-2-r2.md:6116: trailing whitespace.
+++   168	
.oracle/checkins/batch-2-r2.md:6118: trailing whitespace.
+++   177	
.oracle/checkins/batch-2-r2.md:6120: trailing whitespace.
+++   178	
.oracle/checkins/batch-2-r2.md:6122: trailing whitespace.
+++   181	
.oracle/checkins/batch-2-r2.md:6124: trailing whitespace.
+++   188	
.oracle/checkins/batch-2-r2.md:6126: trailing whitespace.
+++   194	
.oracle/checkins/batch-2-r2.md:6128: trailing whitespace.
+++   203	
.oracle/checkins/batch-2-r2.md:6130: trailing whitespace.
+++   204	
.oracle/checkins/batch-2-r2.md:6132: trailing whitespace.
+++   208	
.oracle/checkins/batch-2-r2.md:6134: trailing whitespace.
+++   211	
.oracle/checkins/batch-2-r2.md:6136: trailing whitespace.
+++   212	
.oracle/checkins/batch-2-r2.md:6138: trailing whitespace.
+++   216	
.oracle/checkins/batch-2-r2.md:6140: trailing whitespace.
+++   219	
.oracle/checkins/batch-2-r2.md:6142: trailing whitespace.
+++   220	
.oracle/checkins/batch-2-r2.md:6144: trailing whitespace.
+++   224	
.oracle/checkins/batch-2-r2.md:6146: trailing whitespace.
+++   227	
.oracle/checkins/batch-2-r2.md:6148: trailing whitespace.
+++   231	
.oracle/checkins/batch-2-r2.md:6150: trailing whitespace.
+++   232	
.oracle/checkins/batch-2-r2.md:6152: trailing whitespace.
+++   436	
.oracle/checkins/batch-2-r2.md:6154: trailing whitespace.
+++   437	
.oracle/checkins/batch-2-r2.md:6156: trailing whitespace.
+++   450	
.oracle/checkins/batch-2-r2.md:6158: trailing whitespace.
+++   451	
.oracle/checkins/batch-2-r2.md:6160: trailing whitespace.
+++   456	
.oracle/checkins/batch-2-r2.md:6162: trailing whitespace.
+++   464	
.oracle/checkins/batch-2-r2.md:6164: trailing whitespace.
+++   467	
.oracle/checkins/batch-2-r2.md:6166: trailing whitespace.
+++   471	
.oracle/checkins/batch-2-r2.md:6168: trailing whitespace.
+++   484	
.oracle/checkins/batch-2-r2.md:6170: trailing whitespace.
+++   487	
.oracle/checkins/batch-2-r2.md:6172: trailing whitespace.
+++   490	
.oracle/checkins/batch-2-r2.md:6174: trailing whitespace.
+++   491	
.oracle/checkins/batch-2-r2.md:6176: trailing whitespace.
+++   496	
.oracle/checkins/batch-2-r2.md:6178: trailing whitespace.
+++   506	
.oracle/checkins/batch-2-r2.md:6180: trailing whitespace.
+++   507	
.oracle/checkins/batch-2-r2.md:6182: trailing whitespace.
+++   514	
.oracle/checkins/batch-2-r2.md:6184: trailing whitespace.
+++   515	
.oracle/checkins/batch-2-r2.md:6186: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6188: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6190: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6192: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6194: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6196: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6198: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6200: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6202: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6204: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6206: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6208: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6210: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6212: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6214: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6216: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6218: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6220: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6222: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6224: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6226: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6228: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6230: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6232: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6234: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6236: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6238: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6240: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6242: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6244: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6246: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6248: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6250: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6252: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6254: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6256: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6258: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6260: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6262: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6264: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6266: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6268: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6270: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6272: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6274: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6276: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6278: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6280: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6282: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6284: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6286: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6288: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6290: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6292: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6294: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6296: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6298: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6300: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6302: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6304: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6306: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6308: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6310: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6312: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6314: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6316: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6318: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6320: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6322: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6324: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6326: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6328: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6330: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6332: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6334: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6336: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6338: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6340: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6342: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6344: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6346: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6348: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6350: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6352: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6354: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6356: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6358: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6360: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6362: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6364: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6366: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6368: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6370: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6372: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6374: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6376: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6378: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6380: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6382: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6384: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6386: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6388: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6390: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6392: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6394: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6396: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6398: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6400: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6402: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6404: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6406: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6408: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6410: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6412: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6414: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6416: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6418: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6420: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6422: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6424: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6426: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6428: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6430: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6432: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6434: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6436: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6438: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6440: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6442: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6444: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6446: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6448: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6450: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6452: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6454: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6456: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6458: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6460: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6462: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6464: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6466: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6468: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6470: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6472: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6474: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6476: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6478: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6480: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6482: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6484: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6486: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6488: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6490: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6492: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6494: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6496: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6498: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6500: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6502: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6504: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6506: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6508: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6510: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6512: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6514: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6516: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6518: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6520: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6522: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6524: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6526: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6528: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6530: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6532: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6534: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6536: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6538: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6540: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6542: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6544: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6546: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6548: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6550: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6552: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6554: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6556: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6558: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6560: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6562: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6564: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6566: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6568: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6570: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6572: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6574: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6576: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6578: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6580: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6582: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6584: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6586: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6588: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6590: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r2.md:6592: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r2.md:6594: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r2.md:6596: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r2.md:6598: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r2.md:6600: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r2.md:6602: trailing whitespace.
++    38	
.oracle/checkins/batch-2-r2.md:6604: trailing whitespace.
++    41	
.oracle/checkins/batch-2-r2.md:6606: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r2.md:6608: trailing whitespace.
++    70	
.oracle/checkins/batch-2-r2.md:6610: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r2.md:6612: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r2.md:6614: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r2.md:6616: trailing whitespace.
++   113	
.oracle/checkins/batch-2-r2.md:6618: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r2.md:6620: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r2.md:6622: trailing whitespace.
++   144	
.oracle/checkins/batch-2-r2.md:6624: trailing whitespace.
++   160	
.oracle/checkins/batch-2-r2.md:6626: trailing whitespace.
++   171	
.oracle/checkins/batch-2-r2.md:6628: trailing whitespace.
++   202	
.oracle/checkins/batch-2-r2.md:6630: trailing whitespace.
++   246	
.oracle/checkins/batch-2-r2.md:6632: trailing whitespace.
++   250	
.oracle/checkins/batch-2-r2.md:6634: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r2.md:6636: trailing whitespace.
++   427	
.oracle/checkins/batch-2-r2.md:6638: trailing whitespace.
++   428	
.oracle/checkins/batch-2-r2.md:6640: trailing whitespace.
++   445	
.oracle/checkins/batch-2-r2.md:6642: trailing whitespace.
++   446	
.oracle/checkins/batch-2-r2.md:6644: trailing whitespace.
++   459	
.oracle/checkins/batch-2-r2.md:6646: trailing whitespace.
++   460	
.oracle/checkins/batch-2-r2.md:6648: trailing whitespace.
++   465	
.oracle/checkins/batch-2-r2.md:6650: trailing whitespace.
++   479	
.oracle/checkins/batch-2-r2.md:6652: trailing whitespace.
++   482	
.oracle/checkins/batch-2-r2.md:6654: trailing whitespace.
++   486	
.oracle/checkins/batch-2-r2.md:6656: trailing whitespace.
++   499	
.oracle/checkins/batch-2-r2.md:6658: trailing whitespace.
++   502	
.oracle/checkins/batch-2-r2.md:6660: trailing whitespace.
++   505	
.oracle/checkins/batch-2-r2.md:6662: trailing whitespace.
++   506	
.oracle/checkins/batch-2-r2.md:6664: trailing whitespace.
++   511	
.oracle/checkins/batch-2-r2.md:6666: trailing whitespace.
++   521	
.oracle/checkins/batch-2-r2.md:6668: trailing whitespace.
++   522	
.oracle/checkins/batch-2-r2.md:6670: trailing whitespace.
++   529	
.oracle/checkins/batch-2-r2.md:6672: trailing whitespace.
++   530	
.oracle/checkins/batch-2-r2.md:6674: trailing whitespace.
++   541	
.oracle/checkins/batch-2-r2.md:6676: trailing whitespace.
++   542	
.oracle/checkins/batch-2-r2.md:6678: trailing whitespace.
++   561	
.oracle/checkins/batch-2-r2.md:6680: trailing whitespace.
++   562	
.oracle/checkins/batch-2-r2.md:6682: trailing whitespace.
++   573	
.oracle/checkins/batch-2-r2.md:6684: trailing whitespace.
++   574	
.oracle/checkins/batch-2-r2.md:6686: trailing whitespace.
++   627	
.oracle/checkins/batch-2-r2.md:6688: trailing whitespace.
++   628	
.oracle/checkins/batch-2-r2.md:6690: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6692: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6694: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6696: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6698: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6700: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6702: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6704: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6706: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6708: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6710: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6712: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6714: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6716: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6718: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6720: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6722: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6724: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6726: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6728: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6730: trailing whitespace.
++ 
.oracle/checkins/batch-2-r2.md:6732: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r2.md:6734: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r2.md:6736: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r2.md:6738: trailing whitespace.
++    18	
.oracle/checkins/batch-2-r2.md:6740: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r2.md:6742: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r2.md:6744: trailing whitespace.
++    28	
.oracle/checkins/batch-2-r2.md:6746: trailing whitespace.
++    31	
.oracle/checkins/batch-2-r2.md:6748: trailing whitespace.
++    32	
.oracle/checkins/batch-2-r2.md:6750: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r2.md:6752: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r2.md:6754: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r2.md:6756: trailing whitespace.
++    44	
.oracle/checkins/batch-2-r2.md:6758: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r2.md:6760: trailing whitespace.
++    66	
.oracle/checkins/batch-2-r2.md:6762: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r2.md:6764: trailing whitespace.
++    72	
.oracle/checkins/batch-2-r2.md:6766: trailing whitespace.
++    73	
.oracle/checkins/batch-2-r2.md:6768: trailing whitespace.
++    76	
.oracle/checkins/batch-2-r2.md:6770: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r2.md:6772: trailing whitespace.
++    82	
.oracle/checkins/batch-2-r2.md:6774: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r2.md:6776: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r2.md:6778: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r2.md:6780: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r2.md:6782: trailing whitespace.
++    98	
.oracle/checkins/batch-2-r2.md:6784: trailing whitespace.
++    99	
.oracle/checkins/batch-2-r2.md:6786: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r2.md:6788: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r2.md:6790: trailing whitespace.
++   133	
.oracle/checkins/batch-2-r2.md:6792: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r2.md:6794: trailing whitespace.
++   173	
.oracle/checkins/batch-2-r2.md:6796: trailing whitespace.
++   174	
.oracle/checkins/batch-2-r2.md:6798: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r2.md:6800: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r2.md:6802: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r2.md:6804: trailing whitespace.
++   200	
.oracle/checkins/batch-2-r2.md:6806: trailing whitespace.
++   201	
.oracle/checkins/batch-2-r2.md:6808: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r2.md:6810: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r2.md:6812: trailing whitespace.
++   258	
.oracle/checkins/batch-2-r2.md:6814: trailing whitespace.
++   268	
.oracle/checkins/batch-2-r2.md:6816: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r2.md:6818: trailing whitespace.
++   278	
.oracle/checkins/batch-2-r2.md:6820: trailing whitespace.
++   292	
.oracle/checkins/batch-2-r2.md:6822: trailing whitespace.
++   299	
.oracle/checkins/batch-2-r2.md:6824: trailing whitespace.
++   310	
.oracle/checkins/batch-2-r2.md:6826: trailing whitespace.
++   318	
.oracle/checkins/batch-2-r2.md:6828: trailing whitespace.
++   328	
.oracle/checkins/batch-2-r2.md:6830: trailing whitespace.
++   329	
.oracle/checkins/batch-2-r2.md:6832: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r2.md:6834: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r2.md:6836: trailing whitespace.
++     9	
.oracle/checkins/batch-2-r2.md:6838: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r2.md:6840: trailing whitespace.
++    20	
.oracle/checkins/batch-2-r2.md:6842: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r2.md:6844: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r2.md:6846: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r2.md:6848: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r2.md:6850: trailing whitespace.
++    47	
.oracle/checkins/batch-2-r2.md:6852: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r2.md:6854: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r2.md:6856: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r2.md:6858: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r2.md:6860: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r2.md:6862: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r2.md:6864: trailing whitespace.
++    92	
.oracle/checkins/batch-2-r2.md:6866: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r2.md:6868: trailing whitespace.
++   108	
.oracle/checkins/batch-2-r2.md:6870: trailing whitespace.
++   114	
.oracle/checkins/batch-2-r2.md:6872: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r2.md:6874: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r2.md:6876: trailing whitespace.
++   130	
.oracle/checkins/batch-2-r2.md:6878: trailing whitespace.
++   135	
.oracle/checkins/batch-2-r2.md:6880: trailing whitespace.
++   138	
.oracle/checkins/batch-2-r2.md:6882: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r2.md:6884: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r2.md:6886: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r2.md:6888: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r2.md:6890: trailing whitespace.
++   205	
.oracle/checkins/batch-2-r2.md:6892: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r2.md:6894: trailing whitespace.
++   218	
.oracle/checkins/batch-2-r2.md:6896: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r2.md:6898: trailing whitespace.
++   247	
.oracle/checkins/batch-2-r2.md:6900: trailing whitespace.
++   253	
.oracle/checkins/batch-2-r2.md:6902: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r2.md:6904: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r2.md:6906: trailing whitespace.
++   265	
.oracle/checkins/batch-2-r2.md:6908: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r2.md:6910: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r2.md:6912: trailing whitespace.
++   128	
.oracle/checkins/batch-2-r2.md:6914: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r2.md:6916: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r2.md:6918: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r2.md:6920: trailing whitespace.
++   140	
.oracle/checkins/batch-2-r2.md:6922: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r2.md:6924: trailing whitespace.
++   150	
.oracle/checkins/batch-2-r2.md:6926: trailing whitespace.
++   151	
.oracle/checkins/batch-2-r2.md:6928: trailing whitespace.
++   158	
.oracle/checkins/batch-2-r2.md:6930: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r2.md:6932: trailing whitespace.
++   166	
.oracle/checkins/batch-2-r2.md:6934: trailing whitespace.
++   176	
.oracle/checkins/batch-2-r2.md:6936: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r2.md:6938: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r2.md:6940: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r2.md:6942: trailing whitespace.
++   195	
.oracle/checkins/batch-2-r2.md:6944: trailing whitespace.
++   196	
.oracle/checkins/batch-2-r2.md:6946: trailing whitespace.
++   221	
.oracle/checkins/batch-2-r2.md:6948: trailing whitespace.
++   228	
.oracle/checkins/batch-2-r2.md:6950: trailing whitespace.
++   229	
.oracle/checkins/batch-2-r2.md:6952: trailing whitespace.
++   233	
.oracle/checkins/batch-2-r2.md:6954: trailing whitespace.
++   240	
.oracle/checkins/batch-2-r2.md:6956: trailing whitespace.
++   241	
.oracle/checkins/batch-2-r2.md:6958: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r2.md:6960: trailing whitespace.
++     7	
.oracle/checkins/batch-2-r2.md:6962: trailing whitespace.
++    15	
.oracle/checkins/batch-2-r2.md:6964: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r2.md:6966: trailing whitespace.
++    27	
.oracle/checkins/batch-2-r2.md:6968: trailing whitespace.
++    36	
.oracle/checkins/batch-2-r2.md:6970: trailing whitespace.
++    37	
.oracle/checkins/batch-2-r2.md:6972: trailing whitespace.
++    45	
.oracle/checkins/batch-2-r2.md:6974: trailing whitespace.
++    46	
.oracle/checkins/batch-2-r2.md:6976: trailing whitespace.
++    50	
.oracle/checkins/batch-2-r2.md:6978: trailing whitespace.
++    51	
.oracle/checkins/batch-2-r2.md:6980: trailing whitespace.
++    55	
.oracle/checkins/batch-2-r2.md:6982: trailing whitespace.
++    57	
.oracle/checkins/batch-2-r2.md:6984: trailing whitespace.
++    58	
.oracle/checkins/batch-2-r2.md:6986: trailing whitespace.
++    80	
.oracle/checkins/batch-2-r2.md:6988: trailing whitespace.
++    81	
.oracle/checkins/batch-2-r2.md:6990: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r2.md:6992: trailing whitespace.
++    87	
.oracle/checkins/batch-2-r2.md:6994: trailing whitespace.
++    95	
.oracle/checkins/batch-2-r2.md:6996: trailing whitespace.
++   120	
.oracle/checkins/batch-2-r2.md:6998: trailing whitespace.
++   121	
.oracle/checkins/batch-2-r2.md:7000: trailing whitespace.
++   131	
.oracle/checkins/batch-2-r2.md:7002: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r2.md:7004: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r2.md:7006: trailing whitespace.
++   154	
.oracle/checkins/batch-2-r2.md:7008: trailing whitespace.
++   164	
.oracle/checkins/batch-2-r2.md:7010: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r2.md:7012: trailing whitespace.
++   182	
.oracle/checkins/batch-2-r2.md:7014: trailing whitespace.
++   183	
.oracle/checkins/batch-2-r2.md:7016: trailing whitespace.
++   187	
.oracle/checkins/batch-2-r2.md:7018: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r2.md:7020: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r2.md:7022: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r2.md:7024: trailing whitespace.
++   221	
.oracle/checkins/batch-2-r2.md:7026: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r2.md:7028: trailing whitespace.
++   244	
.oracle/checkins/batch-2-r2.md:7030: trailing whitespace.
++   249	
.oracle/checkins/batch-2-r2.md:7032: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r2.md:7034: trailing whitespace.
++   256	
.oracle/checkins/batch-2-r2.md:7036: trailing whitespace.
++   266	
.oracle/checkins/batch-2-r2.md:7038: trailing whitespace.
++   267	
.oracle/checkins/batch-2-r2.md:7040: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r2.md:7042: trailing whitespace.
++   272	
.oracle/checkins/batch-2-r2.md:7044: trailing whitespace.
++   276	
.oracle/checkins/batch-2-r2.md:7046: trailing whitespace.
++   279	
.oracle/checkins/batch-2-r2.md:7048: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r2.md:7050: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r2.md:7052: trailing whitespace.
++   292	
.oracle/checkins/batch-2-r2.md:7054: trailing whitespace.
++   301	
.oracle/checkins/batch-2-r2.md:7056: trailing whitespace.
++   302	
.oracle/checkins/batch-2-r2.md:7058: trailing whitespace.
++   311	
.oracle/checkins/batch-2-r2.md:7060: trailing whitespace.
++   314	
.oracle/checkins/batch-2-r2.md:7062: trailing whitespace.
++   315	
.oracle/checkins/batch-2-r2.md:7064: trailing whitespace.
++   319	
.oracle/checkins/batch-2-r2.md:7066: trailing whitespace.
++   320	
.oracle/checkins/batch-2-r2.md:7068: trailing whitespace.
++   326	
.oracle/checkins/batch-2-r2.md:7070: trailing whitespace.
++   340	
.oracle/checkins/batch-2-r2.md:7072: trailing whitespace.
++   344	
.oracle/checkins/batch-2-r2.md:7074: trailing whitespace.
++   347	
.oracle/checkins/batch-2-r2.md:7076: trailing whitespace.
++   348	
.oracle/checkins/batch-2-r2.md:7078: trailing whitespace.
++   354	
.oracle/checkins/batch-2-r2.md:7080: trailing whitespace.
++   368	
.oracle/checkins/batch-2-r2.md:7082: trailing whitespace.
++   372	
.oracle/checkins/batch-2-r2.md:7084: trailing whitespace.
++   376	
.oracle/checkins/batch-2-r2.md:7086: trailing whitespace.
++   380	
.oracle/checkins/batch-2-r2.md:7088: trailing whitespace.
++   384	
.oracle/checkins/batch-2-r2.md:7090: trailing whitespace.
++   385	
.oracle/checkins/batch-2-r2.md:7092: trailing whitespace.
++   389	
.oracle/checkins/batch-2-r2.md:7094: trailing whitespace.
++   390	
.oracle/checkins/batch-2-r2.md:7096: trailing whitespace.
++   393	
.oracle/checkins/batch-2-r2.md:7098: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r2.md:7100: trailing whitespace.
++   407	
.oracle/checkins/batch-2-r2.md:7102: trailing whitespace.
++   408	
.oracle/checkins/batch-2-r2.md:7104: trailing whitespace.
++   427	
.oracle/checkins/batch-2-r2.md:7106: trailing whitespace.
++   428	
.oracle/checkins/batch-2-r2.md:7108: trailing whitespace.
++   443	
.oracle/checkins/batch-2-r2.md:7110: trailing whitespace.
++   444	
.oracle/checkins/batch-2-r2.md:7112: trailing whitespace.
++   458	
.oracle/checkins/batch-2-r2.md:7114: trailing whitespace.
++   467	
.oracle/checkins/batch-2-r2.md:7116: trailing whitespace.
++   470	
.oracle/checkins/batch-2-r2.md:7118: trailing whitespace.
++   522	
.oracle/checkins/batch-2-r2.md:7120: trailing whitespace.
++   523	
.oracle/checkins/batch-2-r2.md:7122: trailing whitespace.
++   533	
.oracle/checkins/batch-2-r2.md:7124: trailing whitespace.
++   546	
.oracle/checkins/batch-2-r2.md:7126: trailing whitespace.
++   568	
.oracle/checkins/batch-2-r2.md:7128: trailing whitespace.
++   569	
.oracle/checkins/batch-2-r2.md:7130: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r2.md:7132: trailing whitespace.
++     6	
.oracle/checkins/batch-2-r2.md:7134: trailing whitespace.
++     8	
.oracle/checkins/batch-2-r2.md:7136: trailing whitespace.
++    17	
.oracle/checkins/batch-2-r2.md:7138: trailing whitespace.
++    19	
.oracle/checkins/batch-2-r2.md:7140: trailing whitespace.
++    21	
.oracle/checkins/batch-2-r2.md:7142: trailing whitespace.
++    22	
.oracle/checkins/batch-2-r2.md:7144: trailing whitespace.
++    26	
.oracle/checkins/batch-2-r2.md:7146: trailing whitespace.
++    27	
.oracle/checkins/batch-2-r2.md:7148: trailing whitespace.
++    31	
.oracle/checkins/batch-2-r2.md:7150: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r2.md:7152: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r2.md:7154: trailing whitespace.
++    42	
.oracle/checkins/batch-2-r2.md:7156: trailing whitespace.
++    59	
.oracle/checkins/batch-2-r2.md:7158: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r2.md:7160: trailing whitespace.
++    65	
.oracle/checkins/batch-2-r2.md:7162: trailing whitespace.
++    69	
.oracle/checkins/batch-2-r2.md:7164: trailing whitespace.
++    71	
.oracle/checkins/batch-2-r2.md:7166: trailing whitespace.
++    79	
.oracle/checkins/batch-2-r2.md:7168: trailing whitespace.
++    85	
.oracle/checkins/batch-2-r2.md:7170: trailing whitespace.
++    86	
.oracle/checkins/batch-2-r2.md:7172: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r2.md:7174: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r2.md:7176: trailing whitespace.
++    93	
.oracle/checkins/batch-2-r2.md:7178: trailing whitespace.
++   106	
.oracle/checkins/batch-2-r2.md:7180: trailing whitespace.
++   107	
.oracle/checkins/batch-2-r2.md:7182: trailing whitespace.
++   118	
.oracle/checkins/batch-2-r2.md:7184: trailing whitespace.
++   119	
.oracle/checkins/batch-2-r2.md:7186: trailing whitespace.
++   124	
.oracle/checkins/batch-2-r2.md:7188: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r2.md:7190: trailing whitespace.
++   271	
.oracle/checkins/batch-2-r2.md:7192: trailing whitespace.
++   280	
.oracle/checkins/batch-2-r2.md:7194: trailing whitespace.
++   281	
.oracle/checkins/batch-2-r2.md:7196: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r2.md:7198: trailing whitespace.
++   293	
.oracle/checkins/batch-2-r2.md:7200: trailing whitespace.
++   294	
.oracle/checkins/batch-2-r2.md:7202: trailing whitespace.
++   301	
.oracle/checkins/batch-2-r2.md:7204: trailing whitespace.
++   307	
.oracle/checkins/batch-2-r2.md:7206: trailing whitespace.
++   309	
.oracle/checkins/batch-2-r2.md:7208: trailing whitespace.
++   310	
.oracle/checkins/batch-2-r2.md:7210: trailing whitespace.
++   314	
.oracle/checkins/batch-2-r2.md:7212: trailing whitespace.
++   315	
.oracle/checkins/batch-2-r2.md:7214: trailing whitespace.
++   323	
.oracle/checkins/batch-2-r2.md:7216: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r2.md:7218: trailing whitespace.
++   395	
.oracle/checkins/batch-2-r2.md:7220: trailing whitespace.
++   442	
.oracle/checkins/batch-2-r2.md:7222: trailing whitespace.
++   458	
.oracle/checkins/batch-2-r2.md:7224: trailing whitespace.
++   459	
.oracle/checkins/batch-2-r2.md:7226: trailing whitespace.
++   480	
.oracle/checkins/batch-2-r2.md:7228: trailing whitespace.
++   505	
.oracle/checkins/batch-2-r2.md:7230: trailing whitespace.
++   506	
.oracle/checkins/batch-2-r2.md:7232: trailing whitespace.
++   533	
.oracle/checkins/batch-2-r2.md:7234: trailing whitespace.
++   534	
.oracle/checkins/batch-2-r2.md:7236: trailing whitespace.
++   559	
.oracle/checkins/batch-2-r2.md:7238: trailing whitespace.
++   560	
.oracle/checkins/batch-2-r2.md:7240: trailing whitespace.
++   600	
.oracle/checkins/batch-2-r2.md:7242: trailing whitespace.
++   601	
.oracle/checkins/batch-2-r2.md:7244: trailing whitespace.
++   628	
.oracle/checkins/batch-2-r2.md:7246: trailing whitespace.
++   629	
.oracle/checkins/batch-2-r2.md:7248: trailing whitespace.
++   637	
.oracle/checkins/batch-2-r2.md:7250: trailing whitespace.
++   643	
.oracle/checkins/batch-2-r2.md:7252: trailing whitespace.
++   650	
.oracle/checkins/batch-2-r2.md:7254: trailing whitespace.
++   669	
.oracle/checkins/batch-2-r2.md:7256: trailing whitespace.
++   679	
.oracle/checkins/batch-2-r2.md:7258: trailing whitespace.
++   700	
.oracle/checkins/batch-2-r2.md:7260: trailing whitespace.
++   701	
.oracle/checkins/batch-2-r2.md:7262: trailing whitespace.
++   250	
.oracle/checkins/batch-2-r2.md:7264: trailing whitespace.
++   251	
.oracle/checkins/batch-2-r2.md:7266: trailing whitespace.
++   259	
.oracle/checkins/batch-2-r2.md:7268: trailing whitespace.
++   260	
.oracle/checkins/batch-2-r2.md:7270: trailing whitespace.
++   272	
.oracle/checkins/batch-2-r2.md:7272: trailing whitespace.
++   273	
.oracle/checkins/batch-2-r2.md:7274: trailing whitespace.
++   276	
.oracle/checkins/batch-2-r2.md:7276: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r2.md:7278: trailing whitespace.
++   296	
.oracle/checkins/batch-2-r2.md:7280: trailing whitespace.
++   297	
.oracle/checkins/batch-2-r2.md:7282: trailing whitespace.
++   335	
.oracle/checkins/batch-2-r2.md:7284: trailing whitespace.
++   362	
.oracle/checkins/batch-2-r2.md:7286: trailing whitespace.
++   363	
.oracle/checkins/batch-2-r2.md:7288: trailing whitespace.
++   246	
.oracle/checkins/batch-2-r2.md:7290: trailing whitespace.
++   250	
.oracle/checkins/batch-2-r2.md:7292: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r2.md:7294: trailing whitespace.
++   269	
.oracle/checkins/batch-2-r2.md:7296: trailing whitespace.
++   270	
.oracle/checkins/batch-2-r2.md:7298: trailing whitespace.
++   277	
.oracle/checkins/batch-2-r2.md:7300: trailing whitespace.
++   278	
.oracle/checkins/batch-2-r2.md:7302: trailing whitespace.
++   294	
.oracle/checkins/batch-2-r2.md:7304: trailing whitespace.
++   295	
.oracle/checkins/batch-2-r2.md:7306: trailing whitespace.
++   326	
.oracle/checkins/batch-2-r2.md:7308: trailing whitespace.
++   327	
.oracle/checkins/batch-2-r2.md:7310: trailing whitespace.
++   344	
.oracle/checkins/batch-2-r2.md:7312: trailing whitespace.
++   345	
.oracle/checkins/batch-2-r2.md:7314: trailing whitespace.
++   348	
.oracle/checkins/batch-2-r2.md:7316: trailing whitespace.
++   349	
.oracle/checkins/batch-2-r2.md:7318: trailing whitespace.
++   355	
.oracle/checkins/batch-2-r2.md:7320: trailing whitespace.
++   356	
.oracle/checkins/batch-2-r2.md:7322: trailing whitespace.
++   392	
.oracle/checkins/batch-2-r2.md:7324: trailing whitespace.
++   401	
.oracle/checkins/batch-2-r2.md:7326: trailing whitespace.
++   402	
.oracle/checkins/batch-2-r2.md:7328: trailing whitespace.
++   409	
.oracle/checkins/batch-2-r2.md:7330: trailing whitespace.
++   410	
.oracle/checkins/batch-2-r2.md:7332: trailing whitespace.
++   427	
.oracle/checkins/batch-2-r2.md:7334: trailing whitespace.
++   428	
.oracle/checkins/batch-2-r2.md:7336: trailing whitespace.
++     2	
.oracle/checkins/batch-2-r2.md:7338: trailing whitespace.
++    11	
.oracle/checkins/batch-2-r2.md:7340: trailing whitespace.
++    13	
.oracle/checkins/batch-2-r2.md:7342: trailing whitespace.
++    23	
.oracle/checkins/batch-2-r2.md:7344: trailing whitespace.
++    24	
.oracle/checkins/batch-2-r2.md:7346: trailing whitespace.
++    29	
.oracle/checkins/batch-2-r2.md:7348: trailing whitespace.
++    30	
.oracle/checkins/batch-2-r2.md:7350: trailing whitespace.
++    33	
.oracle/checkins/batch-2-r2.md:7352: trailing whitespace.
++    34	
.oracle/checkins/batch-2-r2.md:7354: trailing whitespace.
++    39	
.oracle/checkins/batch-2-r2.md:7356: trailing whitespace.
++    40	
.oracle/checkins/batch-2-r2.md:7358: trailing whitespace.
++    63	
.oracle/checkins/batch-2-r2.md:7360: trailing whitespace.
++    64	
.oracle/checkins/batch-2-r2.md:7362: trailing whitespace.
++    74	
.oracle/checkins/batch-2-r2.md:7364: trailing whitespace.
++    75	
.oracle/checkins/batch-2-r2.md:7366: trailing whitespace.
++    89	
.oracle/checkins/batch-2-r2.md:7368: trailing whitespace.
++    90	
.oracle/checkins/batch-2-r2.md:7370: trailing whitespace.
++    96	
.oracle/checkins/batch-2-r2.md:7372: trailing whitespace.
++   100	
.oracle/checkins/batch-2-r2.md:7374: trailing whitespace.
++   101	
.oracle/checkins/batch-2-r2.md:7376: trailing whitespace.
++   123	
.oracle/checkins/batch-2-r2.md:7378: trailing whitespace.
++   125	
.oracle/checkins/batch-2-r2.md:7380: trailing whitespace.
++   126	
.oracle/checkins/batch-2-r2.md:7382: trailing whitespace.
++   129	
.oracle/checkins/batch-2-r2.md:7384: trailing whitespace.
++   139	
.oracle/checkins/batch-2-r2.md:7386: trailing whitespace.
++   142	
.oracle/checkins/batch-2-r2.md:7388: trailing whitespace.
++   143	
.oracle/checkins/batch-2-r2.md:7390: trailing whitespace.
++   155	
.oracle/checkins/batch-2-r2.md:7392: trailing whitespace.
++   161	
.oracle/checkins/batch-2-r2.md:7394: trailing whitespace.
++   162	
.oracle/checkins/batch-2-r2.md:7396: trailing whitespace.
++   165	
.oracle/checkins/batch-2-r2.md:7398: trailing whitespace.
++   168	
.oracle/checkins/batch-2-r2.md:7400: trailing whitespace.
++   177	
.oracle/checkins/batch-2-r2.md:7402: trailing whitespace.
++   178	
.oracle/checkins/batch-2-r2.md:7404: trailing whitespace.
++   181	
.oracle/checkins/batch-2-r2.md:7406: trailing whitespace.
++   188	
.oracle/checkins/batch-2-r2.md:7408: trailing whitespace.
++   194	
.oracle/checkins/batch-2-r2.md:7410: trailing whitespace.
++   203	
.oracle/checkins/batch-2-r2.md:7412: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r2.md:7414: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r2.md:7416: trailing whitespace.
++   211	
.oracle/checkins/batch-2-r2.md:7418: trailing whitespace.
++   212	
.oracle/checkins/batch-2-r2.md:7420: trailing whitespace.
++   216	
.oracle/checkins/batch-2-r2.md:7422: trailing whitespace.
++   219	
.oracle/checkins/batch-2-r2.md:7424: trailing whitespace.
++   220	
.oracle/checkins/batch-2-r2.md:7426: trailing whitespace.
++   224	
.oracle/checkins/batch-2-r2.md:7428: trailing whitespace.
++   227	
.oracle/checkins/batch-2-r2.md:7430: trailing whitespace.
++   231	
.oracle/checkins/batch-2-r2.md:7432: trailing whitespace.
++   232	
.oracle/checkins/batch-2-r2.md:7434: trailing whitespace.
++   239	
.oracle/checkins/batch-2-r2.md:7436: trailing whitespace.
++   249	
.oracle/checkins/batch-2-r2.md:7438: trailing whitespace.
++   254	
.oracle/checkins/batch-2-r2.md:7440: trailing whitespace.
++   255	
.oracle/checkins/batch-2-r2.md:7442: trailing whitespace.
++   261	
.oracle/checkins/batch-2-r2.md:7444: trailing whitespace.
++   275	
.oracle/checkins/batch-2-r2.md:7446: trailing whitespace.
++   132	
.oracle/checkins/batch-2-r2.md:7448: trailing whitespace.
++   140	
.oracle/checkins/batch-2-r2.md:7450: trailing whitespace.
++   142	
.oracle/checkins/batch-2-r2.md:7452: trailing whitespace.
++   147	
.oracle/checkins/batch-2-r2.md:7454: trailing whitespace.
++   149	
.oracle/checkins/batch-2-r2.md:7456: trailing whitespace.
++   153	
.oracle/checkins/batch-2-r2.md:7458: trailing whitespace.
++   163	
.oracle/checkins/batch-2-r2.md:7460: trailing whitespace.
++   170	
.oracle/checkins/batch-2-r2.md:7462: trailing whitespace.
++   172	
.oracle/checkins/batch-2-r2.md:7464: trailing whitespace.
++   175	
.oracle/checkins/batch-2-r2.md:7466: trailing whitespace.
++   184	
.oracle/checkins/batch-2-r2.md:7468: trailing whitespace.
++   189	
.oracle/checkins/batch-2-r2.md:7470: trailing whitespace.
++   191	
.oracle/checkins/batch-2-r2.md:7472: trailing whitespace.
++   193	
.oracle/checkins/batch-2-r2.md:7474: trailing whitespace.
++   204	
.oracle/checkins/batch-2-r2.md:7476: trailing whitespace.
++   208	
.oracle/checkins/batch-2-r2.md:7478: trailing whitespace.
++   217	
.oracle/checkins/batch-2-r2.md:7480: trailing whitespace.
++   223	
.oracle/checkins/batch-2-r2.md:7482: trailing whitespace.
++   225	
.oracle/checkins/batch-2-r2.md:7484: trailing whitespace.
++   230	
.oracle/checkins/batch-2-r2.md:7486: trailing whitespace.
++   238	
.oracle/checkins/batch-2-r2.md:7488: trailing whitespace.
++   240	
.oracle/checkins/batch-2-r2.md:7490: trailing whitespace.
++   243	
.oracle/checkins/batch-2-r2.md:7492: trailing whitespace.
++   251	
.oracle/checkins/batch-2-r2.md:7494: trailing whitespace.
++   255	
.oracle/checkins/batch-2-r2.md:7496: trailing whitespace.
++   257	
.oracle/checkins/batch-2-r2.md:7498: trailing whitespace.
++   262	
.oracle/checkins/batch-2-r2.md:7500: trailing whitespace.
++   408	
.oracle/checkins/batch-2-r2.md:7502: trailing whitespace.
++   410	
.oracle/checkins/batch-2-r2.md:7504: trailing whitespace.
++   412	
.oracle/checkins/batch-2-r2.md:7506: trailing whitespace.
++   421	
.oracle/checkins/batch-2-r2.md:7508: trailing whitespace.
++   430	
.oracle/checkins/batch-2-r2.md:7510: trailing whitespace.
++   434	
.oracle/checkins/batch-2-r2.md:7512: trailing whitespace.
++   436	
.oracle/checkins/batch-2-r2.md:7514: trailing whitespace.
++   438	
.oracle/checkins/batch-2-r2.md:7516: trailing whitespace.
++   453	
.oracle/checkins/batch-2-r2.md:7518: trailing whitespace.
++   461	
.oracle/checkins/batch-2-r2.md:7520: trailing whitespace.
++   463	
.oracle/checkins/batch-2-r2.md:7522: trailing whitespace.
++   465	
.oracle/checkins/batch-2-r2.md:7524: trailing whitespace.
++   470	
.oracle/checkins/batch-2-r2.md:7526: trailing whitespace.
++   288	
.oracle/checkins/batch-2-r2.md:7528: trailing whitespace.
++   289	
.oracle/checkins/batch-2-r2.md:7530: trailing whitespace.
++   312	
.oracle/checkins/batch-2-r2.md:7532: trailing whitespace.
++   313	
.oracle/checkins/batch-2-r2.md:7534: trailing whitespace.
++   334	
.oracle/checkins/batch-2-r2.md:7536: trailing whitespace.
++   335	
.oracle/checkins/batch-2-r2.md:7538: trailing whitespace.
++   346	
.oracle/checkins/batch-2-r2.md:7540: trailing whitespace.
++   347	
.oracle/checkins/batch-2-r2.md:7542: trailing whitespace.
++   357	
.oracle/checkins/batch-2-r2.md:7544: trailing whitespace.
++   358	
.oracle/checkins/batch-2-r2.md:7546: trailing whitespace.
++   370	
.oracle/checkins/batch-2-r2.md:7548: trailing whitespace.
++   371	
.oracle/checkins/batch-2-r2.md:7550: trailing whitespace.
++   375	
.oracle/checkins/batch-2-r2.md:7552: trailing whitespace.
++   382	
.oracle/checkins/batch-2-r2.md:7554: trailing whitespace.
++   383	
.oracle/checkins/batch-2-r2.md:7556: trailing whitespace.
++   387	
.oracle/checkins/batch-2-r2.md:7558: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r2.md:7560: trailing whitespace.
++   395	
.oracle/checkins/batch-2-r2.md:7562: trailing whitespace.
++   399	
.oracle/checkins/batch-2-r2.md:7564: trailing whitespace.
++   406	
.oracle/checkins/batch-2-r2.md:7566: trailing whitespace.
++   407	
.oracle/checkins/batch-2-r2.md:7568: trailing whitespace.
++   411	
.oracle/checkins/batch-2-r2.md:7570: trailing whitespace.
++  1443	
.oracle/checkins/batch-2-r2.md:7572: trailing whitespace.
++  1444	
.oracle/checkins/batch-2-r2.md:7574: trailing whitespace.
++  1458	
.oracle/checkins/batch-2-r2.md:7576: trailing whitespace.
++  1479	
.oracle/checkins/batch-2-r2.md:7578: trailing whitespace.
++  1480	
.oracle/checkins/batch-2-r2.md:7580: trailing whitespace.
++  1537	
.oracle/checkins/batch-2-r2.md:7582: trailing whitespace.
++  1538	
.oracle/checkins/batch-2-r2.md:7584: trailing whitespace.
++   394	
.oracle/checkins/batch-2-r2.md:7586: trailing whitespace.
++   395	
.oracle/checkins/batch-2-r2.md:7588: trailing whitespace.
++   286	
.oracle/checkins/batch-2-r2.md:7590: trailing whitespace.
++   287	
.oracle/checkins/batch-2-r2.md:7592: trailing whitespace.
++   303	
.oracle/checkins/batch-2-r2.md:7594: trailing whitespace.
++   304	
.oracle/checkins/batch-2-r2.md:8124: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:8125: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:8390: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-2-r2.md:8391: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-2-r2.md:8393: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-2-r2.md:8722: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r2.md:8723: trailing whitespace.
+   395	
.oracle/checkins/batch-2-r2.md:8773: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r2.md:8774: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r2.md:8790: trailing whitespace.
+   303	
.oracle/checkins/batch-2-r2.md:8791: trailing whitespace.
+   304	
.oracle/checkins/batch-2-r2.md:8868: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8869: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8876: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8877: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8894: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8895: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8898: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8904: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8909: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8913: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8930: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8933: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8939: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8947: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8955: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8961: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8984: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8986: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8987: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:8999: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9029: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9038: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9039: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9046: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9051: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9052: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9059: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9065: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9067: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9068: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9072: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9073: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9091: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9092: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9099: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9104: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9139: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9140: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9147: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9149: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9150: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9166: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9167: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9206: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9232: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9233: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9243: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9250: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9253: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9267: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9274: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9285: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9293: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9312: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9321: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9322: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9329: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9330: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9347: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9348: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9365: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9366: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9379: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9380: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9385: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9399: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9402: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9406: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9428: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9431: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9434: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9435: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9440: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9450: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9451: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9467: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9468: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9479: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9480: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9499: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9500: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9511: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9512: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9565: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9566: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9656: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9657: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9671: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9693: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9694: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9751: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9752: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9773: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9774: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9780: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9784: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9785: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9807: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9809: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9810: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9813: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9823: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9826: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9827: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9839: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9845: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9846: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9849: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9852: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9873: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9874: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9877: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9884: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9890: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9899: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9900: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9904: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9907: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9908: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9912: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9915: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9916: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9920: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9923: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9927: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9928: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9935: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9945: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9950: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9951: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9957: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9971: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9979: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9980: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9983: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9984: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9990: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:9991: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10004: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10005: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10020: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10021: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10028: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10029: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10033: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10034: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10038: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10039: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10062: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10063: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10088: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10089: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10111: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10121: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10125: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10126: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10137: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10140: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10144: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10153: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10157: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10161: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10165: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10169: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10170: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10174: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10175: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10178: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10179: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10192: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10193: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10215: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10216: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10231: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10232: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10246: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10255: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10258: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10310: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10311: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10321: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10338: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10360: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10361: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:10489: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:10493: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r2.md:10495: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r2.md:10509: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r2.md:10511: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r2.md:10524: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r2.md:10525: trailing whitespace.
+    38	
.oracle/checkins/batch-2-r2.md:10528: trailing whitespace.
+    41	
.oracle/checkins/batch-2-r2.md:10556: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r2.md:10557: trailing whitespace.
+    70	
.oracle/checkins/batch-2-r2.md:10560: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r2.md:10566: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r2.md:10585: trailing whitespace.
+    98	
.oracle/checkins/batch-2-r2.md:10600: trailing whitespace.
+   113	
.oracle/checkins/batch-2-r2.md:10607: trailing whitespace.
+   120	
.oracle/checkins/batch-2-r2.md:10613: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r2.md:10631: trailing whitespace.
+   144	
.oracle/checkins/batch-2-r2.md:10647: trailing whitespace.
+   160	
.oracle/checkins/batch-2-r2.md:10658: trailing whitespace.
+   171	
.oracle/checkins/batch-2-r2.md:10689: trailing whitespace.
+   202	
.oracle/checkins/batch-2-r2.md:10733: trailing whitespace.
+   246	
.oracle/checkins/batch-2-r2.md:10737: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r2.md:10744: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r2.md:10756: trailing whitespace.
+   269	
.oracle/checkins/batch-2-r2.md:10757: trailing whitespace.
+   270	
.oracle/checkins/batch-2-r2.md:10764: trailing whitespace.
+   277	
.oracle/checkins/batch-2-r2.md:10765: trailing whitespace.
+   278	
.oracle/checkins/batch-2-r2.md:10781: trailing whitespace.
+   294	
.oracle/checkins/batch-2-r2.md:10782: trailing whitespace.
+   295	
.oracle/checkins/batch-2-r2.md:10809: trailing whitespace.
+   401	
.oracle/checkins/batch-2-r2.md:10810: trailing whitespace.
+   402	
.oracle/checkins/batch-2-r2.md:10817: trailing whitespace.
+   409	
.oracle/checkins/batch-2-r2.md:10818: trailing whitespace.
+   410	
.oracle/checkins/batch-2-r2.md:10835: trailing whitespace.
+   427	
.oracle/checkins/batch-2-r2.md:10836: trailing whitespace.
+   428	
.oracle/checkins/batch-2-r2.md:10853: trailing whitespace.
+   445	
.oracle/checkins/batch-2-r2.md:10854: trailing whitespace.
+   446	
.oracle/checkins/batch-2-r2.md:10867: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r2.md:10868: trailing whitespace.
+   460	
.oracle/checkins/batch-2-r2.md:10873: trailing whitespace.
+   465	
.oracle/checkins/batch-2-r2.md:10887: trailing whitespace.
+   479	
.oracle/checkins/batch-2-r2.md:10890: trailing whitespace.
+   482	
.oracle/checkins/batch-2-r2.md:10894: trailing whitespace.
+   486	
.oracle/checkins/batch-2-r2.md:10915: trailing whitespace.
+   507	
.oracle/checkins/batch-2-r2.md:10918: trailing whitespace.
+   510	
.oracle/checkins/batch-2-r2.md:10921: trailing whitespace.
+   513	
.oracle/checkins/batch-2-r2.md:10922: trailing whitespace.
+   514	
.oracle/checkins/batch-2-r2.md:10927: trailing whitespace.
+   519	
.oracle/checkins/batch-2-r2.md:10937: trailing whitespace.
+   529	
.oracle/checkins/batch-2-r2.md:10938: trailing whitespace.
+   530	
.oracle/checkins/batch-2-r2.md:10954: trailing whitespace.
+   546	
.oracle/checkins/batch-2-r2.md:10955: trailing whitespace.
+   547	
.oracle/checkins/batch-2-r2.md:10966: trailing whitespace.
+   558	
.oracle/checkins/batch-2-r2.md:10967: trailing whitespace.
+   559	
.oracle/checkins/batch-2-r2.md:10986: trailing whitespace.
+   578	
.oracle/checkins/batch-2-r2.md:10987: trailing whitespace.
+   579	
.oracle/checkins/batch-2-r2.md:10998: trailing whitespace.
+   590	
.oracle/checkins/batch-2-r2.md:10999: trailing whitespace.
+   591	
.oracle/checkins/batch-2-r2.md:11052: trailing whitespace.
+   644	
.oracle/checkins/batch-2-r2.md:11053: trailing whitespace.
+   645	
.oracle/checkins/batch-2-r2.md:11070: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:11079: trailing whitespace.
+    11	
.oracle/checkins/batch-2-r2.md:11081: trailing whitespace.
+    13	
.oracle/checkins/batch-2-r2.md:11091: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r2.md:11092: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r2.md:11097: trailing whitespace.
+    29	
.oracle/checkins/batch-2-r2.md:11098: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r2.md:11101: trailing whitespace.
+    33	
.oracle/checkins/batch-2-r2.md:11102: trailing whitespace.
+    34	
.oracle/checkins/batch-2-r2.md:11107: trailing whitespace.
+    39	
.oracle/checkins/batch-2-r2.md:11108: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r2.md:11131: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r2.md:11132: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r2.md:11142: trailing whitespace.
+    74	
.oracle/checkins/batch-2-r2.md:11143: trailing whitespace.
+    75	
.oracle/checkins/batch-2-r2.md:11157: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r2.md:11158: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r2.md:11164: trailing whitespace.
+    96	
.oracle/checkins/batch-2-r2.md:11168: trailing whitespace.
+   100	
.oracle/checkins/batch-2-r2.md:11169: trailing whitespace.
+   101	
.oracle/checkins/batch-2-r2.md:11191: trailing whitespace.
+   123	
.oracle/checkins/batch-2-r2.md:11193: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r2.md:11194: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r2.md:11197: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r2.md:11207: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r2.md:11210: trailing whitespace.
+   142	
.oracle/checkins/batch-2-r2.md:11211: trailing whitespace.
+   143	
.oracle/checkins/batch-2-r2.md:11223: trailing whitespace.
+   155	
.oracle/checkins/batch-2-r2.md:11229: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r2.md:11230: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r2.md:11233: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r2.md:11236: trailing whitespace.
+   168	
.oracle/checkins/batch-2-r2.md:11244: trailing whitespace.
+   176	
.oracle/checkins/batch-2-r2.md:11245: trailing whitespace.
+   177	
.oracle/checkins/batch-2-r2.md:11249: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r2.md:11252: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r2.md:11256: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r2.md:11257: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r2.md:11260: trailing whitespace.
+   192	
.oracle/checkins/batch-2-r2.md:11267: trailing whitespace.
+   199	
.oracle/checkins/batch-2-r2.md:11273: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r2.md:11282: trailing whitespace.
+   214	
.oracle/checkins/batch-2-r2.md:11283: trailing whitespace.
+   215	
.oracle/checkins/batch-2-r2.md:11287: trailing whitespace.
+   219	
.oracle/checkins/batch-2-r2.md:11290: trailing whitespace.
+   222	
.oracle/checkins/batch-2-r2.md:11291: trailing whitespace.
+   223	
.oracle/checkins/batch-2-r2.md:11295: trailing whitespace.
+   227	
.oracle/checkins/batch-2-r2.md:11298: trailing whitespace.
+   230	
.oracle/checkins/batch-2-r2.md:11299: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r2.md:11303: trailing whitespace.
+   235	
.oracle/checkins/batch-2-r2.md:11306: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r2.md:11310: trailing whitespace.
+   242	
.oracle/checkins/batch-2-r2.md:11311: trailing whitespace.
+   243	
.oracle/checkins/batch-2-r2.md:11318: trailing whitespace.
+   250	
.oracle/checkins/batch-2-r2.md:11328: trailing whitespace.
+   260	
.oracle/checkins/batch-2-r2.md:11333: trailing whitespace.
+   265	
.oracle/checkins/batch-2-r2.md:11334: trailing whitespace.
+   266	
.oracle/checkins/batch-2-r2.md:11340: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r2.md:11354: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r2.md:11381: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11382: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11387: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11401: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11404: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11408: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11430: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11433: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11436: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11437: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11442: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11452: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11453: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11469: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11470: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11481: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11482: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11501: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11502: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11517: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11520: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11521: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11533: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11539: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11540: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11543: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11546: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11567: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11568: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11571: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11578: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11584: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11593: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11594: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11598: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11601: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11602: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11606: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:11614: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:11616: trailing whitespace.
+     4	
.oracle/checkins/batch-2-r2.md:11625: trailing whitespace.
+    13	
.oracle/checkins/batch-2-r2.md:11626: trailing whitespace.
+    14	
.oracle/checkins/batch-2-r2.md:11632: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r2.md:11633: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r2.md:11638: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r2.md:11644: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r2.md:11647: trailing whitespace.
+    35	
.oracle/checkins/batch-2-r2.md:11654: trailing whitespace.
+    42	
.oracle/checkins/batch-2-r2.md:11691: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r2.md:11694: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r2.md:11695: trailing whitespace.
+    83	
.oracle/checkins/batch-2-r2.md:11709: trailing whitespace.
+   155	
.oracle/checkins/batch-2-r2.md:11715: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r2.md:11716: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r2.md:11719: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r2.md:11722: trailing whitespace.
+   168	
.oracle/checkins/batch-2-r2.md:11731: trailing whitespace.
+   177	
.oracle/checkins/batch-2-r2.md:11732: trailing whitespace.
+   178	
.oracle/checkins/batch-2-r2.md:11735: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r2.md:11742: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r2.md:11748: trailing whitespace.
+   194	
.oracle/checkins/batch-2-r2.md:11757: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r2.md:11758: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r2.md:11762: trailing whitespace.
+   208	
.oracle/checkins/batch-2-r2.md:11765: trailing whitespace.
+   211	
.oracle/checkins/batch-2-r2.md:11766: trailing whitespace.
+   212	
.oracle/checkins/batch-2-r2.md:11770: trailing whitespace.
+   216	
.oracle/checkins/batch-2-r2.md:11773: trailing whitespace.
+   219	
.oracle/checkins/batch-2-r2.md:11774: trailing whitespace.
+   220	
.oracle/checkins/batch-2-r2.md:11778: trailing whitespace.
+   224	
.oracle/checkins/batch-2-r2.md:11796: trailing whitespace.
+   445	
.oracle/checkins/batch-2-r2.md:11797: trailing whitespace.
+   446	
.oracle/checkins/batch-2-r2.md:11810: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r2.md:11811: trailing whitespace.
+   460	
.oracle/checkins/batch-2-r2.md:11816: trailing whitespace.
+   465	
.oracle/checkins/batch-2-r2.md:11830: trailing whitespace.
+   479	
.oracle/checkins/batch-2-r2.md:11833: trailing whitespace.
+   482	
.oracle/checkins/batch-2-r2.md:11837: trailing whitespace.
+   486	
.oracle/checkins/batch-2-r2.md:11850: trailing whitespace.
+   499	
.oracle/checkins/batch-2-r2.md:11853: trailing whitespace.
+   502	
.oracle/checkins/batch-2-r2.md:11856: trailing whitespace.
+   505	
.oracle/checkins/batch-2-r2.md:11857: trailing whitespace.
+   506	
.oracle/checkins/batch-2-r2.md:11862: trailing whitespace.
+   511	
.oracle/checkins/batch-2-r2.md:11872: trailing whitespace.
+   521	
.oracle/checkins/batch-2-r2.md:11873: trailing whitespace.
+   522	
.oracle/checkins/batch-2-r2.md:11880: trailing whitespace.
+   529	
.oracle/checkins/batch-2-r2.md:11881: trailing whitespace.
+   530	
.oracle/checkins/batch-2-r2.md:12055: trailing whitespace.
+     3	
.oracle/checkins/batch-2-r2.md:12058: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r2.md:12060: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r2.md:12066: trailing whitespace.
+    14	
.oracle/checkins/batch-2-r2.md:12072: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r2.md:12074: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r2.md:12082: trailing whitespace.
+    30	
.oracle/checkins/batch-2-r2.md:12085: trailing whitespace.
+    33	
.oracle/checkins/batch-2-r2.md:12101: trailing whitespace.
+    49	
.oracle/checkins/batch-2-r2.md:12105: trailing whitespace.
+    53	
.oracle/checkins/batch-2-r2.md:12107: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r2.md:12109: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r2.md:12110: trailing whitespace.
+    58	
.oracle/checkins/batch-2-r2.md:12114: trailing whitespace.
+    62	
.oracle/checkins/batch-2-r2.md:12115: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r2.md:12118: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r2.md:12120: trailing whitespace.
+    68	
.oracle/checkins/batch-2-r2.md:12125: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r2.md:12134: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r2.md:12143: trailing whitespace.
+    91	
.oracle/checkins/batch-2-r2.md:12144: trailing whitespace.
+    92	
.oracle/checkins/batch-2-r2.md:12151: trailing whitespace.
+    99	
.oracle/checkins/batch-2-r2.md:12152: trailing whitespace.
+   100	
.oracle/checkins/batch-2-r2.md:12156: trailing whitespace.
+   104	
.oracle/checkins/batch-2-r2.md:12157: trailing whitespace.
+   105	
.oracle/checkins/batch-2-r2.md:12169: trailing whitespace.
+   117	
.oracle/checkins/batch-2-r2.md:12170: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r2.md:12195: trailing whitespace.
+   143	
.oracle/checkins/batch-2-r2.md:12196: trailing whitespace.
+   144	
.oracle/checkins/batch-2-r2.md:12217: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r2.md:12218: trailing whitespace.
+   166	
.oracle/checkins/batch-2-r2.md:12221: trailing whitespace.
+   169	
.oracle/checkins/batch-2-r2.md:12242: trailing whitespace.
+   190	
.oracle/checkins/batch-2-r2.md:12243: trailing whitespace.
+   191	
.oracle/checkins/batch-2-r2.md:12247: trailing whitespace.
+   195	
.oracle/checkins/batch-2-r2.md:12248: trailing whitespace.
+   196	
.oracle/checkins/batch-2-r2.md:12251: trailing whitespace.
+   199	
.oracle/checkins/batch-2-r2.md:12252: trailing whitespace.
+   200	
.oracle/checkins/batch-2-r2.md:12255: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r2.md:12256: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r2.md:12259: trailing whitespace.
+   207	
.oracle/checkins/batch-2-r2.md:12260: trailing whitespace.
+   208	
.oracle/checkins/batch-2-r2.md:12266: trailing whitespace.
+   214	
.oracle/checkins/batch-2-r2.md:12267: trailing whitespace.
+   215	
.oracle/checkins/batch-2-r2.md:12280: trailing whitespace.
+   228	
.oracle/checkins/batch-2-r2.md:12281: trailing whitespace.
+   229	
.oracle/checkins/batch-2-r2.md:12296: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r2.md:12297: trailing whitespace.
+   245	
.oracle/checkins/batch-2-r2.md:12304: trailing whitespace.
+   252	
.oracle/checkins/batch-2-r2.md:12305: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r2.md:12309: trailing whitespace.
+   257	
.oracle/checkins/batch-2-r2.md:12310: trailing whitespace.
+   258	
.oracle/checkins/batch-2-r2.md:12314: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r2.md:12315: trailing whitespace.
+   263	
.oracle/checkins/batch-2-r2.md:12338: trailing whitespace.
+   286	
.oracle/checkins/batch-2-r2.md:12339: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r2.md:12363: trailing whitespace.
+   311	
.oracle/checkins/batch-2-r2.md:12364: trailing whitespace.
+   312	
.oracle/checkins/batch-2-r2.md:12386: trailing whitespace.
+   334	
.oracle/checkins/batch-2-r2.md:12396: trailing whitespace.
+   344	
.oracle/checkins/batch-2-r2.md:12400: trailing whitespace.
+   348	
.oracle/checkins/batch-2-r2.md:12401: trailing whitespace.
+   349	
.oracle/checkins/batch-2-r2.md:12412: trailing whitespace.
+   360	
.oracle/checkins/batch-2-r2.md:12415: trailing whitespace.
+   363	
.oracle/checkins/batch-2-r2.md:12419: trailing whitespace.
+   367	
.oracle/checkins/batch-2-r2.md:12428: trailing whitespace.
+   376	
.oracle/checkins/batch-2-r2.md:12432: trailing whitespace.
+   380	
.oracle/checkins/batch-2-r2.md:12436: trailing whitespace.
+   384	
.oracle/checkins/batch-2-r2.md:12440: trailing whitespace.
+   388	
.oracle/checkins/batch-2-r2.md:12444: trailing whitespace.
+   392	
.oracle/checkins/batch-2-r2.md:12445: trailing whitespace.
+   393	
.oracle/checkins/batch-2-r2.md:12449: trailing whitespace.
+   397	
.oracle/checkins/batch-2-r2.md:12450: trailing whitespace.
+   398	
.oracle/checkins/batch-2-r2.md:12453: trailing whitespace.
+   401	
.oracle/checkins/batch-2-r2.md:12454: trailing whitespace.
+   402	
.oracle/checkins/batch-2-r2.md:12467: trailing whitespace.
+   415	
.oracle/checkins/batch-2-r2.md:12468: trailing whitespace.
+   416	
.oracle/checkins/batch-2-r2.md:12488: trailing whitespace.
+   436	
.oracle/checkins/batch-2-r2.md:12489: trailing whitespace.
+   437	
.oracle/checkins/batch-2-r2.md:12504: trailing whitespace.
+   452	
.oracle/checkins/batch-2-r2.md:12505: trailing whitespace.
+   453	
.oracle/checkins/batch-2-r2.md:12519: trailing whitespace.
+   467	
.oracle/checkins/batch-2-r2.md:12528: trailing whitespace.
+   476	
.oracle/checkins/batch-2-r2.md:12531: trailing whitespace.
+   479	
.oracle/checkins/batch-2-r2.md:12583: trailing whitespace.
+   531	
.oracle/checkins/batch-2-r2.md:12584: trailing whitespace.
+   532	
.oracle/checkins/batch-2-r2.md:12594: trailing whitespace.
+   542	
.oracle/checkins/batch-2-r2.md:12611: trailing whitespace.
+   559	
.oracle/checkins/batch-2-r2.md:12633: trailing whitespace.
+   581	
.oracle/checkins/batch-2-r2.md:12634: trailing whitespace.
+   582	
.oracle/checkins/batch-2-r2.md:12685: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:12689: trailing whitespace.
+     6	
.oracle/checkins/batch-2-r2.md:12691: trailing whitespace.
+     8	
.oracle/checkins/batch-2-r2.md:12700: trailing whitespace.
+    17	
.oracle/checkins/batch-2-r2.md:12702: trailing whitespace.
+    19	
.oracle/checkins/batch-2-r2.md:12704: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r2.md:12705: trailing whitespace.
+    22	
.oracle/checkins/batch-2-r2.md:12709: trailing whitespace.
+    26	
.oracle/checkins/batch-2-r2.md:12710: trailing whitespace.
+    27	
.oracle/checkins/batch-2-r2.md:12714: trailing whitespace.
+    31	
.oracle/checkins/batch-2-r2.md:12717: trailing whitespace.
+    34	
.oracle/checkins/batch-2-r2.md:12723: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r2.md:12725: trailing whitespace.
+    42	
.oracle/checkins/batch-2-r2.md:12742: trailing whitespace.
+    59	
.oracle/checkins/batch-2-r2.md:12746: trailing whitespace.
+    63	
.oracle/checkins/batch-2-r2.md:12748: trailing whitespace.
+    65	
.oracle/checkins/batch-2-r2.md:12752: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r2.md:12754: trailing whitespace.
+    71	
.oracle/checkins/batch-2-r2.md:12762: trailing whitespace.
+    79	
.oracle/checkins/batch-2-r2.md:12768: trailing whitespace.
+    85	
.oracle/checkins/batch-2-r2.md:12769: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r2.md:12772: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r2.md:12773: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r2.md:12776: trailing whitespace.
+    93	
.oracle/checkins/batch-2-r2.md:12789: trailing whitespace.
+   106	
.oracle/checkins/batch-2-r2.md:12790: trailing whitespace.
+   107	
.oracle/checkins/batch-2-r2.md:12801: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r2.md:12802: trailing whitespace.
+   119	
.oracle/checkins/batch-2-r2.md:12807: trailing whitespace.
+   124	
.oracle/checkins/batch-2-r2.md:12808: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r2.md:12815: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r2.md:12816: trailing whitespace.
+   133	
.oracle/checkins/batch-2-r2.md:12833: trailing whitespace.
+   150	
.oracle/checkins/batch-2-r2.md:12834: trailing whitespace.
+   151	
.oracle/checkins/batch-2-r2.md:12837: trailing whitespace.
+   154	
.oracle/checkins/batch-2-r2.md:12843: trailing whitespace.
+   160	
.oracle/checkins/batch-2-r2.md:12848: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r2.md:12852: trailing whitespace.
+   169	
.oracle/checkins/batch-2-r2.md:12869: trailing whitespace.
+   186	
.oracle/checkins/batch-2-r2.md:12872: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r2.md:12878: trailing whitespace.
+   195	
.oracle/checkins/batch-2-r2.md:12886: trailing whitespace.
+   203	
.oracle/checkins/batch-2-r2.md:12894: trailing whitespace.
+   211	
.oracle/checkins/batch-2-r2.md:12900: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r2.md:12922: trailing whitespace.
+   239	
.oracle/checkins/batch-2-r2.md:12924: trailing whitespace.
+   241	
.oracle/checkins/batch-2-r2.md:12925: trailing whitespace.
+   242	
.oracle/checkins/batch-2-r2.md:12937: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r2.md:13102: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r2.md:13103: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r2.md:13107: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r2.md:13108: trailing whitespace.
+    87	
.oracle/checkins/batch-2-r2.md:13138: trailing whitespace.
+   117	
.oracle/checkins/batch-2-r2.md:13139: trailing whitespace.
+   118	
.oracle/checkins/batch-2-r2.md:13142: trailing whitespace.
+   121	
.oracle/checkins/batch-2-r2.md:13160: trailing whitespace.
+   139	
.oracle/checkins/batch-2-r2.md:13173: trailing whitespace.
+   152	
.oracle/checkins/batch-2-r2.md:13174: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r2.md:13177: trailing whitespace.
+   156	
.oracle/checkins/batch-2-r2.md:13186: trailing whitespace.
+   165	
.oracle/checkins/batch-2-r2.md:13207: trailing whitespace.
+   186	
.oracle/checkins/batch-2-r2.md:13218: trailing whitespace.
+   197	
.oracle/checkins/batch-2-r2.md:13220: trailing whitespace.
+   199	
.oracle/checkins/batch-2-r2.md:13238: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:13243: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r2.md:13251: trailing whitespace.
+    15	
.oracle/checkins/batch-2-r2.md:13253: trailing whitespace.
+    17	
.oracle/checkins/batch-2-r2.md:13263: trailing whitespace.
+    27	
.oracle/checkins/batch-2-r2.md:13272: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r2.md:13273: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r2.md:13281: trailing whitespace.
+    45	
.oracle/checkins/batch-2-r2.md:13282: trailing whitespace.
+    46	
.oracle/checkins/batch-2-r2.md:13286: trailing whitespace.
+    50	
.oracle/checkins/batch-2-r2.md:13287: trailing whitespace.
+    51	
.oracle/checkins/batch-2-r2.md:13291: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r2.md:13293: trailing whitespace.
+    57	
.oracle/checkins/batch-2-r2.md:13294: trailing whitespace.
+    58	
.oracle/checkins/batch-2-r2.md:13316: trailing whitespace.
+    80	
.oracle/checkins/batch-2-r2.md:13317: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r2.md:13322: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r2.md:13323: trailing whitespace.
+    87	
.oracle/checkins/batch-2-r2.md:13331: trailing whitespace.
+    95	
.oracle/checkins/batch-2-r2.md:13356: trailing whitespace.
+   120	
.oracle/checkins/batch-2-r2.md:13357: trailing whitespace.
+   121	
.oracle/checkins/batch-2-r2.md:13367: trailing whitespace.
+   131	
.oracle/checkins/batch-2-r2.md:13368: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r2.md:13389: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r2.md:13390: trailing whitespace.
+   154	
.oracle/checkins/batch-2-r2.md:13400: trailing whitespace.
+   164	
.oracle/checkins/batch-2-r2.md:13406: trailing whitespace.
+   170	
.oracle/checkins/batch-2-r2.md:13418: trailing whitespace.
+   182	
.oracle/checkins/batch-2-r2.md:13419: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r2.md:13423: trailing whitespace.
+   187	
.oracle/checkins/batch-2-r2.md:13424: trailing whitespace.
+   188	
.oracle/checkins/batch-2-r2.md:13430: trailing whitespace.
+   194	
.oracle/checkins/batch-2-r2.md:13440: trailing whitespace.
+   204	
.oracle/checkins/batch-2-r2.md:13457: trailing whitespace.
+   221	
.oracle/checkins/batch-2-r2.md:13467: trailing whitespace.
+   231	
.oracle/checkins/batch-2-r2.md:13480: trailing whitespace.
+   244	
.oracle/checkins/batch-2-r2.md:13485: trailing whitespace.
+   249	
.oracle/checkins/batch-2-r2.md:13490: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r2.md:13492: trailing whitespace.
+   256	
.oracle/checkins/batch-2-r2.md:13502: trailing whitespace.
+   266	
.oracle/checkins/batch-2-r2.md:13503: trailing whitespace.
+   267	
.oracle/checkins/batch-2-r2.md:13507: trailing whitespace.
+   271	
.oracle/checkins/batch-2-r2.md:13508: trailing whitespace.
+   272	
.oracle/checkins/batch-2-r2.md:13512: trailing whitespace.
+   276	
.oracle/checkins/batch-2-r2.md:13515: trailing whitespace.
+   279	
.oracle/checkins/batch-2-r2.md:13523: trailing whitespace.
+   287	
.oracle/checkins/batch-2-r2.md:13524: trailing whitespace.
+   288	
.oracle/checkins/batch-2-r2.md:13528: trailing whitespace.
+   292	
.oracle/checkins/batch-2-r2.md:13537: trailing whitespace.
+   301	
.oracle/checkins/batch-2-r2.md:13538: trailing whitespace.
+   302	
.oracle/checkins/batch-2-r2.md:13547: trailing whitespace.
+   311	
.oracle/checkins/batch-2-r2.md:13550: trailing whitespace.
+   314	
.oracle/checkins/batch-2-r2.md:13551: trailing whitespace.
+   315	
.oracle/checkins/batch-2-r2.md:13555: trailing whitespace.
+   319	
.oracle/checkins/batch-2-r2.md:13556: trailing whitespace.
+   320	
.oracle/checkins/batch-2-r2.md:13562: trailing whitespace.
+   326	
.oracle/checkins/batch-2-r2.md:13576: trailing whitespace.
+   340	
.oracle/checkins/batch-2-r2.md:13580: trailing whitespace.
+   344	
.oracle/checkins/batch-2-r2.md:13583: trailing whitespace.
+   347	
.oracle/checkins/batch-2-r2.md:13584: trailing whitespace.
+   348	
.oracle/checkins/batch-2-r2.md:13590: trailing whitespace.
+   354	
.oracle/checkins/batch-2-r2.md:13604: trailing whitespace.
+   368	
.oracle/checkins/batch-2-r2.md:13608: trailing whitespace.
+   372	
.oracle/checkins/batch-2-r2.md:13613: trailing whitespace.
+   377	
.oracle/checkins/batch-2-r2.md:13616: trailing whitespace.
+   380	
.oracle/checkins/batch-2-r2.md:13618: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:13623: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r2.md:13625: trailing whitespace.
+     9	
.oracle/checkins/batch-2-r2.md:13635: trailing whitespace.
+    19	
.oracle/checkins/batch-2-r2.md:13636: trailing whitespace.
+    20	
.oracle/checkins/batch-2-r2.md:13639: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r2.md:13640: trailing whitespace.
+    24	
.oracle/checkins/batch-2-r2.md:13655: trailing whitespace.
+    39	
.oracle/checkins/batch-2-r2.md:13656: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r2.md:13663: trailing whitespace.
+    47	
.oracle/checkins/batch-2-r2.md:13671: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r2.md:13680: trailing whitespace.
+    64	
.oracle/checkins/batch-2-r2.md:13681: trailing whitespace.
+    65	
.oracle/checkins/batch-2-r2.md:13691: trailing whitespace.
+    75	
.oracle/checkins/batch-2-r2.md:13697: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r2.md:13702: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r2.md:13708: trailing whitespace.
+    92	
.oracle/checkins/batch-2-r2.md:13712: trailing whitespace.
+    96	
.oracle/checkins/batch-2-r2.md:13724: trailing whitespace.
+   108	
.oracle/checkins/batch-2-r2.md:13730: trailing whitespace.
+   114	
.oracle/checkins/batch-2-r2.md:13735: trailing whitespace.
+   119	
.oracle/checkins/batch-2-r2.md:13745: trailing whitespace.
+   129	
.oracle/checkins/batch-2-r2.md:13746: trailing whitespace.
+   130	
.oracle/checkins/batch-2-r2.md:13751: trailing whitespace.
+   135	
.oracle/checkins/batch-2-r2.md:13754: trailing whitespace.
+   138	
.oracle/checkins/batch-2-r2.md:13765: trailing whitespace.
+   149	
.oracle/checkins/batch-2-r2.md:13777: trailing whitespace.
+   161	
.oracle/checkins/batch-2-r2.md:13778: trailing whitespace.
+   162	
.oracle/checkins/batch-2-r2.md:13803: trailing whitespace.
+   187	
.oracle/checkins/batch-2-r2.md:13821: trailing whitespace.
+   205	
.oracle/checkins/batch-2-r2.md:13833: trailing whitespace.
+   217	
.oracle/checkins/batch-2-r2.md:13834: trailing whitespace.
+   218	
.oracle/checkins/batch-2-r2.md:13854: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r2.md:13863: trailing whitespace.
+   247	
.oracle/checkins/batch-2-r2.md:13869: trailing whitespace.
+   253	
.oracle/checkins/batch-2-r2.md:13870: trailing whitespace.
+   254	
.oracle/checkins/batch-2-r2.md:13878: trailing whitespace.
+   262	
.oracle/checkins/batch-2-r2.md:13881: trailing whitespace.
+   265	
.oracle/checkins/batch-2-r2.md:13891: trailing whitespace.
+   275	
.oracle/checkins/batch-2-r2.md:14004: trailing whitespace.
+     2	
.oracle/checkins/batch-2-r2.md:14009: trailing whitespace.
+     7	
.oracle/checkins/batch-2-r2.md:14011: trailing whitespace.
+     9	
.oracle/checkins/batch-2-r2.md:14020: trailing whitespace.
+    18	
.oracle/checkins/batch-2-r2.md:14023: trailing whitespace.
+    21	
.oracle/checkins/batch-2-r2.md:14025: trailing whitespace.
+    23	
.oracle/checkins/batch-2-r2.md:14030: trailing whitespace.
+    28	
.oracle/checkins/batch-2-r2.md:14033: trailing whitespace.
+    31	
.oracle/checkins/batch-2-r2.md:14034: trailing whitespace.
+    32	
.oracle/checkins/batch-2-r2.md:14038: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r2.md:14039: trailing whitespace.
+    37	
.oracle/checkins/batch-2-r2.md:14042: trailing whitespace.
+    40	
.oracle/checkins/batch-2-r2.md:14046: trailing whitespace.
+    44	
.oracle/checkins/batch-2-r2.md:14061: trailing whitespace.
+    59	
.oracle/checkins/batch-2-r2.md:14068: trailing whitespace.
+    66	
.oracle/checkins/batch-2-r2.md:14071: trailing whitespace.
+    69	
.oracle/checkins/batch-2-r2.md:14074: trailing whitespace.
+    72	
.oracle/checkins/batch-2-r2.md:14075: trailing whitespace.
+    73	
.oracle/checkins/batch-2-r2.md:14078: trailing whitespace.
+    76	
.oracle/checkins/batch-2-r2.md:14083: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r2.md:14084: trailing whitespace.
+    82	
.oracle/checkins/batch-2-r2.md:14087: trailing whitespace.
+    85	
.oracle/checkins/batch-2-r2.md:14088: trailing whitespace.
+    86	
.oracle/checkins/batch-2-r2.md:14091: trailing whitespace.
+    89	
.oracle/checkins/batch-2-r2.md:14092: trailing whitespace.
+    90	
.oracle/checkins/batch-2-r2.md:14100: trailing whitespace.
+    98	
.oracle/checkins/batch-2-r2.md:14101: trailing whitespace.
+    99	
.oracle/checkins/batch-2-r2.md:14127: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r2.md:14128: trailing whitespace.
+   126	
.oracle/checkins/batch-2-r2.md:14135: trailing whitespace.
+   133	
.oracle/checkins/batch-2-r2.md:14140: trailing whitespace.
+   138	
.oracle/checkins/batch-2-r2.md:14175: trailing whitespace.
+   173	
.oracle/checkins/batch-2-r2.md:14176: trailing whitespace.
+   174	
.oracle/checkins/batch-2-r2.md:14183: trailing whitespace.
+   181	
.oracle/checkins/batch-2-r2.md:14185: trailing whitespace.
+   183	
.oracle/checkins/batch-2-r2.md:14186: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r2.md:14202: trailing whitespace.
+   200	
.oracle/checkins/batch-2-r2.md:14203: trailing whitespace.
+   201	
.oracle/checkins/batch-2-r2.md:14240: trailing whitespace.
+   238	
.oracle/checkins/batch-2-r2.md:14266: trailing whitespace.
+   264	
.oracle/checkins/batch-2-r2.md:14267: trailing whitespace.
+   265	
.oracle/checkins/batch-2-r2.md:14277: trailing whitespace.
+   275	
.oracle/checkins/batch-2-r2.md:14284: trailing whitespace.
+   282	
.oracle/checkins/batch-2-r2.md:14287: trailing whitespace.
+   285	
.oracle/checkins/batch-2-r2.md:14301: trailing whitespace.
+   299	
.oracle/checkins/batch-2-r2.md:14308: trailing whitespace.
+   306	
.oracle/checkins/batch-2-r2.md:14319: trailing whitespace.
+   317	
.oracle/checkins/batch-2-r2.md:14327: trailing whitespace.
+   325	
.oracle/checkins/batch-2-r2.md:14337: trailing whitespace.
+   335	
.oracle/checkins/batch-2-r2.md:14338: trailing whitespace.
+   336	
.oracle/checkins/batch-2-r2.md:14384: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14385: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14392: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14394: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14395: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14411: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14412: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14451: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14477: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14478: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14488: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14495: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14498: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14512: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14519: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14597: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14598: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14612: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14634: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14635: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14692: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14693: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:14748: trailing whitespace.
+  1443	
.oracle/checkins/batch-2-r2.md:14749: trailing whitespace.
+  1444	
.oracle/checkins/batch-2-r2.md:14763: trailing whitespace.
+  1458	
.oracle/checkins/batch-2-r2.md:14784: trailing whitespace.
+  1479	
.oracle/checkins/batch-2-r2.md:14785: trailing whitespace.
+  1480	
.oracle/checkins/batch-2-r2.md:14929: trailing whitespace.
+  1277	
.oracle/checkins/batch-2-r2.md:14930: trailing whitespace.
+  1278	
.oracle/checkins/batch-2-r2.md:15093: trailing whitespace.
+   435	
.oracle/checkins/batch-2-r2.md:15094: trailing whitespace.
+   436	
.oracle/checkins/batch-2-r2.md:15103: trailing whitespace.
+   445	
.oracle/checkins/batch-2-r2.md:15135: trailing whitespace.
+   477	
.oracle/checkins/batch-2-r2.md:15158: trailing whitespace.
+   649	
.oracle/checkins/batch-2-r2.md:15159: trailing whitespace.
+   650	
.oracle/checkins/batch-2-r2.md:15169: trailing whitespace.
+   660	
.oracle/checkins/batch-2-r2.md:15229: trailing whitespace.
+   720	
.oracle/checkins/batch-2-r2.md:15251: trailing whitespace.
+  1151	
.oracle/checkins/batch-2-r2.md:15252: trailing whitespace.
+  1152	
.oracle/checkins/batch-2-r2.md:15284: trailing whitespace.
+  1184	
.oracle/checkins/batch-2-r2.md:15338: trailing whitespace.
+  1238	
.oracle/checkins/batch-2-r2.md:15412: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15413: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15416: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15422: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15427: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15431: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15448: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15451: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15457: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15465: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15473: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15479: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15502: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15504: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15505: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15517: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15547: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15556: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15557: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15564: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15569: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15570: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15577: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15589: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15590: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15605: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15606: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15613: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15614: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15618: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15619: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15623: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15624: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15647: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15648: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15673: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15674: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15696: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15706: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15710: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15711: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15722: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15725: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15729: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15738: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15742: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15746: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15750: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15754: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15755: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15759: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15760: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15763: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15764: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15777: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15778: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15800: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15801: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15816: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15817: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15831: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15840: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15843: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15895: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15896: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15906: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15923: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15945: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:15946: trailing whitespace.
+ 
.oracle/checkins/batch-2-r2.md:16062: trailing whitespace.
+   959	
.oracle/checkins/batch-2-r2.md:16063: trailing whitespace.
+   960	
.oracle/checkins/batch-2-r2.md:16066: trailing whitespace.
+   963	
.oracle/checkins/batch-2-r2.md:16067: trailing whitespace.
+   964	
.oracle/checkins/batch-2-r2.md:16073: trailing whitespace.
+   970	
.oracle/checkins/batch-2-r2.md:16078: trailing whitespace.
+   975	
.oracle/checkins/batch-2-r2.md:16092: trailing whitespace.
+   989	
.oracle/checkins/batch-2-r2.md:16093: trailing whitespace.
+   990	
.oracle/checkins/batch-2-r2.md:16104: trailing whitespace.
+  1001	
.oracle/checkins/batch-2-r2.md:16105: trailing whitespace.
+  1002	
.oracle/checkins/batch-2-r2.md:16112: trailing whitespace.
+  1009	
.oracle/checkins/batch-2-r2.md:16113: trailing whitespace.
+  1010	
.oracle/checkins/batch-2-r2.md:16320: trailing whitespace.
+    36	
.oracle/checkins/batch-2-r2.md:16325: trailing whitespace.
+    41	
.oracle/checkins/batch-2-r2.md:16333: trailing whitespace.
+    49	
.oracle/checkins/batch-2-r2.md:16337: trailing whitespace.
+    53	
.oracle/checkins/batch-2-r2.md:16339: trailing whitespace.
+    55	
.oracle/checkins/batch-2-r2.md:16342: trailing whitespace.
+    58	
.oracle/checkins/batch-2-r2.md:16358: trailing whitespace.
+    74	
.oracle/checkins/batch-2-r2.md:16365: trailing whitespace.
+    81	
.oracle/checkins/batch-2-r2.md:16367: trailing whitespace.
+    83	
.oracle/checkins/batch-2-r2.md:16390: trailing whitespace.
+   106	
.oracle/checkins/batch-2-r2.md:16394: trailing whitespace.
+   110	
.oracle/checkins/batch-2-r2.md:16396: trailing whitespace.
+   112	
.oracle/checkins/batch-2-r2.md:16400: trailing whitespace.
+   116	
.oracle/checkins/batch-2-r2.md:16407: trailing whitespace.
+   123	
.oracle/checkins/batch-2-r2.md:16409: trailing whitespace.
+   125	
.oracle/checkins/batch-2-r2.md:16416: trailing whitespace.
+   132	
.oracle/checkins/batch-2-r2.md:16424: trailing whitespace.
+   140	
.oracle/checkins/batch-2-r2.md:16426: trailing whitespace.
+   142	
.oracle/checkins/batch-2-r2.md:16431: trailing whitespace.
+   147	
.oracle/checkins/batch-2-r2.md:16433: trailing whitespace.
+   149	
.oracle/checkins/batch-2-r2.md:16437: trailing whitespace.
+   153	
.oracle/checkins/batch-2-r2.md:16447: trailing whitespace.
+   163	
.oracle/checkins/batch-2-r2.md:16454: trailing whitespace.
+   170	
.oracle/checkins/batch-2-r2.md:16456: trailing whitespace.
+   172	
.oracle/checkins/batch-2-r2.md:16459: trailing whitespace.
+   175	
.oracle/checkins/batch-2-r2.md:16468: trailing whitespace.
+   184	
.oracle/checkins/batch-2-r2.md:16473: trailing whitespace.
+   189	
.oracle/checkins/batch-2-r2.md:16487: trailing whitespace.
+   362	
.oracle/checkins/batch-2-r2.md:16488: trailing whitespace.
+   363	
.oracle/checkins/batch-2-r2.md:16519: trailing whitespace.
+   394	
.oracle/checkins/batch-2-r2.md:16520: trailing whitespace.
+   395	
.oracle/checkins/batch-2-r2.md:16567: trailing whitespace.
+   442	
.oracle/checkins/batch-2-r2.md:16583: trailing whitespace.
+   458	
.oracle/checkins/batch-2-r2.md:16584: trailing whitespace.
+   459	
.oracle/checkins/batch-2-r2.md:16605: trailing whitespace.
+   480	
.oracle/checkins/batch-2-r2.md:16630: trailing whitespace.
+   505	
.oracle/checkins/batch-2-r2.md:16631: trailing whitespace.
+   506	

exec
/bin/zsh -lc 'tail -n 140 .oracle/checkins/batch-2-r2.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 7f7c25d5..8c195bf0 -- astrid/core/rendering/transport.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index 3ae65c8f..44671dd2 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -371,275 +371,300 @@ def _resolve_executable(
         else:
             candidate = (cwd / raw).resolve(strict=False)
             try:
                 candidate.relative_to(cwd)
             except ValueError:
                 raise_binary_missing_error(
                     backend=backend,
                     message=f"pack-relative renderer executable escapes its pack root: {executable}",
                     details={"binary": executable, "cwd": str(cwd)},
                 )
         resolved = str(candidate) if _is_executable_file(candidate) else None
     elif _is_executable_file(cwd / executable):
         # Manifest commands commonly name a pack-owned entrypoint without a
         # leading ``./``.  Resolve it explicitly because sanitized PATH must
         # not implicitly contain the pack root.
         resolved = str((cwd / executable).resolve())
     else:
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
-    except (subprocess.TimeoutExpired, KeyboardInterrupt):
+    except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
         captured = None
-        # Interruption during the grace window must not abandon the group:
-        # escalate to SIGKILL right away and reap in the loop below.
+        # Interruption or a communicate failure during the grace window must
+        # not abandon the group: escalate to SIGKILL right away and reap in
+        # the loop below.
         try:
             _signal_process_group(process, signal.SIGKILL)
         except OSError:
             pass
 
     while _process_group_exists(process) and time.monotonic() < deadline:
-        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+        try:
+            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+        except KeyboardInterrupt:
+            try:
+                _signal_process_group(process, signal.SIGKILL)
+            except OSError:
+                pass
+            break
 
     killed_group = _process_group_exists(process)
     if killed_group:
         _signal_process_group(process, signal.SIGKILL)
 
     if process.returncode is None:
         drain_deadline = time.monotonic() + max(grace, 2.0)
         while True:
             try:
                 captured = process.communicate()
                 break
             except KeyboardInterrupt:
                 try:
                     _signal_process_group(process, signal.SIGKILL)
                 except (OSError, PermissionError):
                     pass
                 if time.monotonic() > drain_deadline:
                     process.kill()
                     captured = process.communicate()
                     break
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
-        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+        try:
+            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+        except KeyboardInterrupt:
+            try:
+                _signal_process_group(process, signal.SIGKILL)
+            except OSError:
+                pass
+            break
     if _process_group_exists(process):
         _signal_process_group(process, signal.SIGKILL)
         _wait_for_group_exit(process, timeout=grace)
 
 
 def _wait_for_group_exit(
     process: subprocess.Popen[str], *, timeout: float
 ) -> None:
     deadline = time.monotonic() + timeout
     while _process_group_exists(process) and time.monotonic() < deadline:
-        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
-    # A group that ignores SIGKILL cannot exist on POSIX; if it somehow
-    # survives the grace window, keep SIGKILLing until it is gone so cleanup
-    # never returns with a live orphan.
-    while _process_group_exists(process):
+        try:
+            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
+        except KeyboardInterrupt:
+            try:
+                _signal_process_group(process, signal.SIGKILL)
+            except OSError:
+                pass
+            break
+    # Escalate to SIGKILL for the remaining grace window (bounded) so a
+    # SIGTERM-ignoring group cannot survive cleanup.
+    kill_deadline = time.monotonic() + max(timeout, 1.0)
+    while _process_group_exists(process) and time.monotonic() < kill_deadline:
         try:
             _signal_process_group(process, signal.SIGKILL)
         except (OSError, PermissionError):
             break
-        time.sleep(0.01)
+        try:
+            time.sleep(0.01)
+        except KeyboardInterrupt:
+            break
 
 
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
 
 

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 7f7c25d5..8c195bf0 -- astrid/core/media.py tests/core/util/test_media.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/media.py b/astrid/core/media.py
index e7c6a92d..c120b9c9 100644
--- a/astrid/core/media.py
+++ b/astrid/core/media.py
@@ -125,209 +125,208 @@ def _nonempty_string(value: Any) -> str | None:
 
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
         # Some containers (e.g. QuickTime sowt) report channel counts without
-        # a channel_layout; derive the standard layout so strict profile
-        # validation can still compare audio placement.
+        # a channel_layout; derive the standard layout only for unambiguous
+        # channel counts (mono/stereo). 5.1/7.1 have multiple speaker
+        # variants, so those stay unprobed rather than guessed.
         if probe.audio_channel_layout is None:
             channels = _int_or_none(audio_stream.get("channels"), minimum=1)
             probe.audio_channel_layout = {
                 1: "mono",
                 2: "stereo",
-                6: "5.1",
-                8: "7.1",
             }.get(channels or 0)
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
diff --git a/tests/core/util/test_media.py b/tests/core/util/test_media.py
index cd809fb2..89ca645d 100644
--- a/tests/core/util/test_media.py
+++ b/tests/core/util/test_media.py
@@ -87,200 +87,231 @@ def test_verify_uses_canonical_media_helper() -> None:
 
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
 
+    def test_layout_derived_from_unambiguous_channel_count(self) -> None:
+        """Containers that report channels without channel_layout (e.g.
+        QuickTime sowt) derive mono/stereo only — never ambiguous 5.1/7.1."""
+        import json as _json
+
+        payload = json.loads(HAPPY_FFPROBE_JSON)
+        for stream in payload["streams"]:
+            if stream.get("codec_type") == "audio":
+                del stream["channel_layout"]
+                stream["channels"] = 2
+        with patch(
+            "astrid.core.media.subprocess.run",
+            return_value=subprocess.CompletedProcess(
+                [], 0, stdout=_json.dumps(payload), stderr=""
+            ),
+        ):
+            probe = ffprobe_metadata("video.mp4")
+        assert probe.audio_channel_layout == "stereo"
+
+        for stream in payload["streams"]:
+            if stream.get("codec_type") == "audio":
+                stream["channels"] = 6
+        with patch(
+            "astrid.core.media.subprocess.run",
+            return_value=subprocess.CompletedProcess(
+                [], 0, stdout=_json.dumps(payload), stderr=""
+            ),
+        ):
+            probe = ffprobe_metadata("video.mp4")
+        assert probe.audio_channel_layout is None  # 5.1 variants ambiguous
+
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
         ):

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=80 7f7c25d5..8c195bf0 -- tests/core/rendering/test_transport.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 7f7c25d5..8c195bf0 -- tests/fixtures/renderer_packs/raw_command/backend.py tests/fixtures/renderer_packs/raw_command/requests/support.json tests/core/rendering/test_raw_command_fixture.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_raw_command_fixture.py b/tests/core/rendering/test_raw_command_fixture.py
index 51de30c6..7e44fd39 100644
--- a/tests/core/rendering/test_raw_command_fixture.py
+++ b/tests/core/rendering/test_raw_command_fixture.py
@@ -180,200 +180,217 @@ def _assert_clean_render(result: RenderResult, workspace: Path) -> None:
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
     for name in new_modules:
         module = sys.modules.get(name)
         module_file = getattr(module, "__file__", None)
         assert module_file is None or not str(Path(module_file).resolve()).startswith(
             source_str
         ), f"module {name!r} is backed by the fixture pack: {module_file}"
 
 
 # ---------------------------------------------------------------------------
 # Protocol verbs through CommandTransport
 # ---------------------------------------------------------------------------
 
 
 def test_render_verb_via_command_transport(tmp_path: Path) -> None:
     workspace = tmp_path / "workspace"
     transport, result, _ = _run_transport(workspace, PACK_ROOT, verb="render")
 
     _assert_clean_render(result, workspace)
     assert transport.last_logs == {"stdout": "", "stderr": ""}
 
+    # The fixture output must pass STRICT artifact validation against the
+    # request profile (dimensions, FPS, codecs, pixel format, audio).
+    from astrid.core.rendering.artifacts import validate_render_result
+    from astrid.core.rendering.contracts import RenderRequest
+
+    request = json.loads(
+        (PACK_ROOT / "requests" / "render.json").read_text(encoding="utf-8")
+    )
+    parsed_request = RenderRequest.from_dict(request)
+    video_abs = workspace / result.video.path
+    validate_render_result(
+        result,
+        expected_profile=parsed_request.profile,
+        workspace_root=workspace,
+    )
+    assert video_abs.is_file()
+
     # Determinism: a second invocation produces byte-identical media.
     second_workspace = tmp_path / "workspace-2"
     _, second_result, _ = _run_transport(second_workspace, PACK_ROOT, verb="render")
     first_bytes = (workspace / result.video.path).read_bytes()
     second_bytes = (second_workspace / second_result.video.path).read_bytes()
     assert first_bytes == second_bytes
     assert result.video.sha256 == second_result.video.sha256
 
 
 def test_support_verb_via_command_transport(tmp_path: Path) -> None:
     workspace = tmp_path / "workspace"
     _, report, _ = _run_transport(workspace, PACK_ROOT, verb="support", request_name="support.json")
 
     assert isinstance(report, SupportReport)
     assert report.schema_version == 1
     assert report.supported is True
     assert report.reasons == []
     assert report.features == {"media": True, "audio_mode": "rendered"}
     assert report.alternatives == []
     assert report.backend == BACKEND_ID
     assert report.backend_version == "1.0.0"
 
 
 def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
     _run_transport(tmp_path / "workspace-render", PACK_ROOT, verb="render")
     _run_transport(
         tmp_path / "workspace-support",
         PACK_ROOT,
         verb="support",
         request_name="support.json",
     )
 
     for root in (tmp_path, PACK_ROOT):
         assert list(root.rglob("run.json")) == [], f"run.json found under {root}"
 
 
 # ---------------------------------------------------------------------------
 # Extra pack root and trusted install resolution
 # ---------------------------------------------------------------------------
 
 
 def test_fixture_works_from_explicit_extra_pack_root(tmp_path: Path) -> None:
     extra_root = tmp_path / "extra"
     extra_pack = _copy_pack(extra_root)
     empty_source = tmp_path / "empty-source"
     empty_source.mkdir()
 
     with (
         mock.patch.object(
             rendering_registry_module,
             "discover_packs",
             side_effect=_scanner(empty_source),
         ),
         mock.patch.dict(os.environ, {"ASTRID_PACKS_PATH": ""}, clear=False),
     ):
         renderers, _, _ = load_default_registries(
             tmp_path / "project",
             extra_pack_roots=(str(extra_root),),
             include_installed=False,
         )
 
     candidate = renderers.get(BACKEND_ID)
     assert candidate.source_kind == "extra"
     assert candidate.execution_eligible is True
 
     _, result, workspace = _run_transport(tmp_path / "workspace-extra", extra_pack, verb="render")
     _assert_clean_render(result, workspace)
 
 
 def test_fixture_works_from_trusted_install(tmp_path: Path) -> None:
     astrid_home = tmp_path / "astrid-home"
     empty_source = tmp_path / "empty-source"
     empty_source.mkdir()
     revision = _stage_installed_fixture(astrid_home)
 
     with (
         mock.patch.dict(
             os.environ,
             {"ASTRID_HOME": str(astrid_home), "ASTRID_PACKS_PATH": ""},
             clear=False,
         ),
         mock.patch.object(
             rendering_registry_module,
             "discover_packs",
             side_effect=_scanner(empty_source),
         ),
     ):
         renderers, _, _ = load_default_registries(tmp_path / "project", include_installed=True)
 
     candidate = renderers.get(BACKEND_ID)
     assert candidate.source_kind == "installed"
     assert candidate.execution_eligible is True
 
     alias = renderers.get(ALIAS_ID)
     assert alias.id == BACKEND_ID
     assert alias.source_kind == "installed"
     assert alias.execution_eligible is True
 
     _, result, workspace = _run_transport(tmp_path / "workspace-installed", revision, verb="render")
     _assert_clean_render(result, workspace)
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 37973595..783fb243 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -191,394 +191,419 @@ def _idr_slice_nal(frame_index: int) -> bytes:
 
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
     wave = _box(
         b"wave",
-        _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
+        _box(b"frma", b"sowt")
+        + _box(b"enda", struct.pack(">H", 1))
+        + _box(
+            b"chan",
+            struct.pack(">I", 0)  # version/flags
+            + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)  # layout tag
+            + struct.pack(">I", 0),  # bitmap
+        ),
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
-    # QuickTime channel layout atom so ffprobe reports a concrete
-    # channel_layout (stereo = layout tag 3) instead of None.
-    chan = _box(
-        b"chan",
-        struct.pack(">I", 0)   # version/flags
-        + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)
-        + struct.pack(">I", 0),  # bitmap
-    )
-    return _box(b"sowt", audio + wave + chan)
+    return _box(b"sowt", audio + wave)
 
 
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
 
 
-def _support(result_path: Path) -> int:
+def _support(request: dict, result_path: Path) -> int:
+    profile = request.get("profile")
+    if isinstance(profile, dict):
+        # The renderer can only produce its own exact codec set; a request
+        # for a different codec is unsupported (fail closed).
+        if (
+            profile.get("audio_codec") not in (None, AUDIO_CODEC)
+            or profile.get("video_codec") not in (None, VIDEO_CODEC)
+            or profile.get("width") not in (None, WIDTH)
+            or profile.get("height") not in (None, HEIGHT)
+        ):
+            _write_json(
+                result_path,
+                {
+                    "schema_version": 1,
+                    "supported": False,
+                    "reasons": [
+                        f"requested profile {profile.get('audio_codec')}/"
+                        f"{profile.get('video_codec')} is not produced by {BACKEND_ID}"
+                    ],
+                    "features": {"media": False, "audio_mode": "none"},
+                    "alternatives": [],
+                    "backend": BACKEND_ID,
+                    "backend_version": "1.0.0",
+                },
+            )
+            return 0
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
-        return _support(result_path)
+        return _support(request, result_path)
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
diff --git a/tests/fixtures/renderer_packs/raw_command/requests/support.json b/tests/fixtures/renderer_packs/raw_command/requests/support.json
index aacbf8a4..bd35d972 100644
--- a/tests/fixtures/renderer_packs/raw_command/requests/support.json
+++ b/tests/fixtures/renderer_packs/raw_command/requests/support.json
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
     "purpose": "T2.2 raw protocol fixture support"
   }
 }

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 7f7c25d5..8c195bf0 -- astrid/core/rendering/publication.py astrid/packs/rendering/executors/render/run.py .gitignore' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/.gitignore b/.gitignore
index f501f44b..9f441389 100644
--- a/.gitignore
+++ b/.gitignore
@@ -1,140 +1,141 @@
 # Secrets and local environment
 .env
 .env.*
 this.env
 !.env.example
 *.pem
 *.key
 *.p12
 *.pfx
 *credentials*
 *secret*
 # Real source files whose names trip the broad credential globs above.
 !astrid/core/util/secrets.py
 !astrid/core/util/credentials_scope.py
 !tests/core/test_credentials_scope.py
 !tests/core/test_dataset_build_credentials_parity.py
 !tests/core/util/test_secrets.py
 
 # Python
 __pycache__/
 .venv/
 venv/
 *.py[cod]
 .pytest_cache/
 .mypy_cache/
 .ruff_cache/
 .coverage
 coverage.xml
 htmlcov/
 *.egg-info/
 
 # Node / Remotion
 node_modules/
 npm-debug.log*
 yarn-debug.log*
 yarn-error.log*
 pnpm-debug.log*
 remotion/build/
 remotion/out/
 
 # Generated runtime artifacts
 # projects root -- source media + generated runs, never committed
 /projects/
 runs/
 cache/
 .astrid/
 **/.cas/
 */cache/
 out/
 */out/
 *.log
 *.preview.*
 *tmp_*
 *.mp4
 *.mov
 *.wav
 *.jpg
 *.jpeg
 *.png
 # ...but committed test fixtures must stay tracked (media OUTPUT/cache stays ignored).
 !tests/**/fixtures/
 !tests/**/fixtures/**
 !tests/fixtures/**
 tests/fixtures/__pycache__/
+tests/fixtures/**/__pycache__/
 
 # Agentic test artifacts (regenerated per-run, not source)
 tests/agentic/reports/
 tests/agentic/__pycache__/
 agentic-*.report.md
 report-*.md
 M5_TEST_STATUS.md
 dry_run_map.json
 plan_v1.revised.md
 
 # Local workspace/tool state
 .DS_Store
 .tmp/
 .claude/
 .desloppify/
 .megaplan/
 .megaplan-agentic/
 .compactify/
 .megaplan-worktrees/
 mgt-*/
 *.bak
 
 # Durable inputs for prepared megaplan initiatives.
 # Generated .megaplan plan/run state remains ignored.
 !.megaplan/
 .megaplan/*
 !.megaplan/initiatives/
 .megaplan/initiatives/*
 !.megaplan/initiatives/timeline-visualization/
 !.megaplan/initiatives/timeline-visualization/**
 !.megaplan/initiatives/pluggable-timeline-renderers/
 !.megaplan/initiatives/pluggable-timeline-renderers/**
 
 # Local scratch pack (gitignored)
 /astrid/packs/local/
 
 # Generated orchestrator build artifacts (compiled DSL JSON)
 astrid/packs/*/build/
 examples/packs/*/build/
 
 # Generated Remotion type files (produced by scripts/gen_remotion_types.py)
 remotion/src/*.generated.*
 remotion/src/effects.types.*
 remotion/src/types.augmentations.*
 # …but the .d.ts is a hand-written narrowing contract (NOT generated) that
 # Root.tsx imports — a hygiene sweep once deleted it via the pattern above
 # and broke `tsc --noEmit` on every clean checkout (restored from 2823e9f).
 !remotion/src/types.augmentations.d.ts
 
 # Allow-list intentional assets that would otherwise be caught by broad globs
 !docs/assets/astrid-orchestration.png
 
 # Theme examples: keep the curated sample theme in-repo, but ignore ad-hoc
 # theme drops and large local media by default.
 themes/*
 !themes/ados-paris-2026/
 !themes/ados-paris-2026/**
 themes/**/video/
 themes/**/*.mp4
 themes/**/*.mov
 
 # Megaplan working state
 plan_revision.json
 
 # Astrid file-bound session pointer (T9 / FLAG-S1-003)
 .astrid-session
 
 # Python build metadata (editable install)
 *.egg-info/
 
 # Python build / distribution artifacts (regenerated; never committed)
 build/
 dist/
 
 # Separate Next.js project (Ideogram x Banodoco competition page); not part of Astrid
 /ideogram-competition/
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index 514dfa6c..dd820fb2 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -129,206 +129,212 @@ def read_committed_provenance(
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
         # Never delete through a symlink: neither the raw video nor the raw
         # sidecar path may be a link (the resolved pair may point elsewhere).
         raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
         raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
         try:
             raw_path = Path(raw_candidate).expanduser()
             if raw_path.is_symlink():
                 continue
         except (OSError, TypeError):
             continue
-        if raw_sidecar_candidate is not None:
-            try:
-                if Path(raw_sidecar_candidate).expanduser().is_symlink():
-                    continue
-            except (OSError, TypeError):
+        try:
+            # For bare paths the default sidecar is derived from the raw
+            # video path; it must be checked unresolved like an explicit one.
+            raw_sidecar = (
+                Path(raw_sidecar_candidate).expanduser()
+                if raw_sidecar_candidate is not None
+                else _default_sidecar_path(raw_path)
+            )
+            if raw_sidecar.is_symlink():
                 continue
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
diff --git a/astrid/packs/rendering/executors/render/run.py b/astrid/packs/rendering/executors/render/run.py
index c42443a4..35c58bfe 100644
--- a/astrid/packs/rendering/executors/render/run.py
+++ b/astrid/packs/rendering/executors/render/run.py
@@ -1190,201 +1190,201 @@ def _render_audio_reactive_colour_if_supported(
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
         prefix=f".{out_path.name}.publication-",
         dir=str(out_path.parent),
     ) as publication_tmp:
         staged_video = Path(publication_tmp) / out_path.name
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
-    out_path = out_path.resolve()
+    out_path = Path(out_path)
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
     if engine == "ffmpeg":
         return _render_ffmpeg_media(timeline_path, assets_path, out_path)
     if engine != "remotion":
         raise ValueError(f"Unsupported render engine: {engine}")
     if _can_render_with_ffmpeg_media(timeline_path, assets_path):
         return _render_ffmpeg_media(timeline_path, assets_path, out_path)
     project_dir = project_dir or (REPO_ROOT / "remotion")
     _validate_project_dir(project_dir)
     _regenerate_element_registries(project_dir, theme_path)
     registry_state = _effective_registry_state(theme_path)
     _require_free_space(out_path.parent, min_free_gb)
     props_path = (out_path.parent / ".remotion-props.json").resolve()
     render_hash = _render_asset_stage_hash(timeline_path, assets_path, out_path)
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
             resolved_theme = theme_path or (WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json")
             theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
             # The timeline references a theme by slug + optional theme_overrides;
             # theme.visual.canvas is the source of truth for Remotion calculateMetadata.
             merged_props = {
                 "timeline": _serialize_timeline(
                     timeline_path,
                     default_theme=str(theme_for_props.get("id") or "banodoco-default"),
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
             out_path.parent.mkdir(parents=True, exist_ok=True)
             publication_tmp = asset_lifecycle.enter_context(
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

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '405,620p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   499	                captured = process.communicate()
   500	                break
   501	            except KeyboardInterrupt:
   502	                try:
   503	                    _signal_process_group(process, signal.SIGKILL)
   504	                except (OSError, PermissionError):
   505	                    pass
   506	                if time.monotonic() > drain_deadline:
   507	                    process.kill()
   508	                    captured = process.communicate()
   509	                    break
   510	                continue
   511	    elif captured is None:
   512	        # ``poll`` may have reaped the child while checking the fallback path.
   513	        # Its pipes still need to be drained, and communicate is safe here.
   514	        captured = process.communicate()
   515	
   516	    if killed_group:
   517	        _wait_for_group_exit(process, timeout=grace)
   518	
   519	    stdout, stderr = captured or ("", "")
   520	    return stdout or "", stderr or ""
   521	
   522	
   523	def _terminate_leftover_group(
   524	    process: subprocess.Popen[str], *, grace: float
   525	) -> None:
   526	    """Clean up descendants that outlived an otherwise completed command."""
   527	
   528	    if not _process_group_exists(process):
   529	        return
   530	    _signal_process_group(process, signal.SIGTERM)
   531	    deadline = time.monotonic() + grace
   532	    while _process_group_exists(process) and time.monotonic() < deadline:
   533	        try:
   534	            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   535	        except KeyboardInterrupt:
   536	            try:
   537	                _signal_process_group(process, signal.SIGKILL)
   538	            except OSError:
   539	                pass
   540	            break
   541	    if _process_group_exists(process):
   542	        _signal_process_group(process, signal.SIGKILL)
   543	        _wait_for_group_exit(process, timeout=grace)
   544	
   545	
   546	def _wait_for_group_exit(
   547	    process: subprocess.Popen[str], *, timeout: float
   548	) -> None:
   549	    deadline = time.monotonic() + timeout
   550	    while _process_group_exists(process) and time.monotonic() < deadline:
   551	        try:
   552	            time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
   553	        except KeyboardInterrupt:
   554	            try:
   555	                _signal_process_group(process, signal.SIGKILL)
   556	            except OSError:
   557	                pass
   558	            break
   559	    # Escalate to SIGKILL for the remaining grace window (bounded) so a
   560	    # SIGTERM-ignoring group cannot survive cleanup.
   561	    kill_deadline = time.monotonic() + max(timeout, 1.0)
   562	    while _process_group_exists(process) and time.monotonic() < kill_deadline:
   563	        try:
   564	            _signal_process_group(process, signal.SIGKILL)
   565	        except (OSError, PermissionError):
   566	            break
   567	        try:
   568	            time.sleep(0.01)
   569	        except KeyboardInterrupt:
   570	            break
   571	
   572	
   573	def _secret_environment_values(
   574	    host: Mapping[str, str], overlay: Mapping[str, str] | None
   575	) -> tuple[str, ...]:
   576	    values: set[str] = set()
   577	    for source in (host, overlay or {}):
   578	        for key, value in source.items():
   579	            text = str(value)
   580	            if _SECRET_NAME_RE.search(str(key)) and len(text) >= 4:
   581	                values.add(text)
   582	    return tuple(sorted(values, key=len, reverse=True))
   583	
   584	
   585	def _redact_log(value: str, *, secret_values: Sequence[str]) -> str:
   586	    redacted = value.replace("\x00", "\ufffd")
   587	    for secret in secret_values:
   588	        redacted = redacted.replace(secret, "[redacted]")
   589	    redacted = _AUTH_HEADER_RE.sub(
   590	        lambda match: f"{match.group(1)}: [redacted]", redacted
   591	    )
   592	    redacted = _BEARER_RE.sub("Bearer [redacted]", redacted)
   593	    redacted = _SECRET_QUERY_RE.sub(
   594	        lambda match: f"{match.group(1)}[redacted]", redacted
   595	    )
   596	    redacted = _SECRET_ASSIGNMENT_RE.sub(
   597	        lambda match: f"{match.group(1)}[redacted]", redacted
   598	    )
   599	    redacted = _SECRET_VALUE_RE.sub("[redacted]", redacted)
   600	    if len(redacted) > _MAX_LOG_CHARS:
   601	        redacted = redacted[:_MAX_LOG_CHARS] + "\n[truncated]"
   602	    return redacted
   603	
   604	
   605	def _redacted_logs(
   606	    stdout: str,
   607	    stderr: str,
   608	    *,
   609	    secret_values: Sequence[str],
   610	) -> dict[str, str]:
   611	    return {
   612	        "stdout": _redact_log(stdout or "", secret_values=secret_values),
   613	        "stderr": _redact_log(stderr or "", secret_values=secret_values),
   614	    }
   615	
   616	
   617	def _read_result_file(
   618	    result_path: Path,
   619	    *,
   620	    backend: str,

exec
/bin/zsh -lc "rg -n \"_terminate_process_group|_terminate_leftover_group|_wait_for_group_exit|communicate\\(\" astrid/core/rendering/transport.py tests/core/rendering/test_transport.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/transport.py:204:            stdout, stderr = process.communicate(timeout=normalized_timeout)
astrid/core/rendering/transport.py:206:            stdout, stderr = _terminate_process_group(
astrid/core/rendering/transport.py:221:            stdout, stderr = _terminate_process_group(
astrid/core/rendering/transport.py:242:                _terminate_process_group(process, grace=self.termination_grace)
astrid/core/rendering/transport.py:249:        _terminate_leftover_group(process, grace=self.termination_grace)
astrid/core/rendering/transport.py:461:def _terminate_process_group(
astrid/core/rendering/transport.py:470:        captured = process.communicate(timeout=grace)
astrid/core/rendering/transport.py:499:                captured = process.communicate()
astrid/core/rendering/transport.py:508:                    captured = process.communicate()
astrid/core/rendering/transport.py:514:        captured = process.communicate()
astrid/core/rendering/transport.py:517:        _wait_for_group_exit(process, timeout=grace)
astrid/core/rendering/transport.py:523:def _terminate_leftover_group(
astrid/core/rendering/transport.py:543:        _wait_for_group_exit(process, timeout=grace)
astrid/core/rendering/transport.py:546:def _wait_for_group_exit(

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_transport.py | sed -n '1,300p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '240,520p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/media.py | sed -n '150,265p'; nl -ba tests/core/util/test_media.py | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   291	        _box(b"frma", b"sowt")
   292	        + _box(b"enda", struct.pack(">H", 1))
   293	        + _box(
   294	            b"chan",
   295	            struct.pack(">I", 0)  # version/flags
   296	            + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)  # layout tag
   297	            + struct.pack(">I", 0),  # bitmap
   298	        ),
   299	    )
   300	    audio = (
   301	        b"\x00" * 6
   302	        + struct.pack(">H", 1)             # data_reference_index
   303	        + struct.pack(">HH", 0, 0)
   304	        + struct.pack(">I", 0)             # vendor
   305	        + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
   306	        + struct.pack(">HH", 0, 0)         # compressionid, packetsize
   307	        + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
   308	    )
   309	    return _box(b"sowt", audio + wave)
   310	
   311	
   312	def _sample_tables(
   313	    *,
   314	    video_frames: int,
   315	    video_sizes: list[int],
   316	    video_chunk_offset: int,
   317	    audio_bytes: bytes,
   318	    audio_samples: int,
   319	    audio_chunk_offset: int,
   320	) -> bytes:
   321	    stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
   322	    stts_v = _fullbox(
   323	        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", video_frames, SAMPLES_PER_FRAME)
   324	    )
   325	    stsc_v = _fullbox(
   326	        b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, video_frames, 1)
   327	    )
   328	    stsz_v = _fullbox(
   329	        b"stsz", 0, struct.pack(">II", 0, video_frames)
   330	        + b"".join(struct.pack(">I", size) for size in video_sizes)
   331	    )
   332	    stco_v = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", video_chunk_offset))
   333	
   334	    stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
   335	    stts_a = _fullbox(
   336	        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
   337	    )
   338	    stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
   339	    stsz_a = _fullbox(
   340	        b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
   341	    )
   342	    stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))
   343	
   344	    video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
   345	    audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
   346	    return video_stbl, audio_stbl
   347	
   348	
   349	def _build_mp4(frames: int) -> bytes:
   350	    """Return a deterministic MP4: `frames` H.264 IDR frames + PCM silence."""
   351	    video_chunk = bytearray()
   352	    video_sizes: list[int] = []
   353	    for frame_index in range(frames):
   354	        nal = _idr_slice_nal(frame_index)
   355	        sample = struct.pack(">I", len(nal)) + nal
   356	        video_chunk += sample
   357	        video_sizes.append(len(sample))
   358	    video_chunk = bytes(video_chunk)
   359	
   360	    audio_samples = frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])
   361	    audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))
   362	
   363	    ftyp = _ftyp()
   364	    video_chunk_offset = len(ftyp) + 8
   365	    audio_chunk_offset = video_chunk_offset + len(video_chunk)
   366	
   367	    video_stbl, audio_stbl = _sample_tables(
   368	        video_frames=frames,
   369	        video_sizes=video_sizes,
   370	        video_chunk_offset=video_chunk_offset,
   371	        audio_bytes=audio_bytes,
   372	        audio_samples=audio_samples,
   373	        audio_chunk_offset=audio_chunk_offset,
   374	    )
   375	
   376	    vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
   377	    smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
   378	    dinf = _dinf()
   379	
   380	    minf_v = _box(b"minf", vmhd + dinf + video_stbl)
   381	    mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
   382	    trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)
   383	
   384	    minf_a = _box(b"minf", smhd + dinf + audio_stbl)
   385	    mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, audio_samples) + _hdlr(b"soun", b"SoundHandler") + minf_a)
   386	    trak_a = _box(b"trak", _tkhd(2, audio_samples, 0x0100, 0, 0) + mdia_a)
   387	
   388	    moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME) + trak_v + trak_a)
   389	    mdat = _box(b"mdat", video_chunk + audio_bytes)
   390	    return ftyp + mdat + moov
   391	
   392	
   393	# ---------------------------------------------------------------------------
   394	# Protocol verbs
   395	# ---------------------------------------------------------------------------
   396	
   397	
   398	def _write_json(path: Path, payload: dict) -> None:
   399	    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
   400	
   401	
   402	def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
   403	    _write_json(
   404	        result_path,
   405	        {
   406	            "schema_version": 1,
   407	            "kind": kind,
   408	            "backend": BACKEND_ID,
   409	            "message": message,
   410	            "recovery_command": None,
   411	            "details": details,
   412	        },
   413	    )
   414	
   415	
   416	def _validate_request(request: dict) -> None:
   417	    version = request.get("schema_version")
   418	    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
   419	        raise ValueError(
   420	            f"unsupported request schema_version {version!r}; expected 1"
   421	        )
   422	    output_name = request.get("output_name")
   423	    if not isinstance(output_name, str) or output_name in (".", ".."):
   424	        raise ValueError("output_name must be a non-empty portable basename")
   425	    if not _OUTPUT_NAME_RE.fullmatch(output_name):
   426	        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
   427	    window = request.get("window")
   428	    if window is not None and not isinstance(window, dict):
   429	        raise ValueError("window must be an object or null")
   430	    if isinstance(window, dict):
   431	        end = window.get("end_frame")
   432	        start = window.get("start_frame", 0)
   433	        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
   434	            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
   435	
   436	
   437	def _support(request: dict, result_path: Path) -> int:
   438	    profile = request.get("profile")
   439	    if isinstance(profile, dict):
   440	        # The renderer can only produce its own exact codec set; a request
   441	        # for a different codec is unsupported (fail closed).
   442	        if (
   443	            profile.get("audio_codec") not in (None, AUDIO_CODEC)
   444	            or profile.get("video_codec") not in (None, VIDEO_CODEC)
   445	            or profile.get("width") not in (None, WIDTH)
   446	            or profile.get("height") not in (None, HEIGHT)
   447	        ):
   448	            _write_json(
   449	                result_path,
   450	                {
   451	                    "schema_version": 1,
   452	                    "supported": False,
   453	                    "reasons": [
   454	                        f"requested profile {profile.get('audio_codec')}/"
   455	                        f"{profile.get('video_codec')} is not produced by {BACKEND_ID}"
   456	                    ],
   457	                    "features": {"media": False, "audio_mode": "none"},
   458	                    "alternatives": [],
   459	                    "backend": BACKEND_ID,
   460	                    "backend_version": "1.0.0",
   461	                },
   462	            )
   463	            return 0
   464	    _write_json(
   465	        result_path,
   466	        {
   467	            "schema_version": 1,
   468	            "supported": True,
   469	            "reasons": [],
   470	            "features": {"media": True, "audio_mode": "rendered"},
   471	            "alternatives": [],
   472	            "backend": BACKEND_ID,
   473	            "backend_version": BACKEND_VERSION,
   474	        },
   475	    )
   476	    return 0
   477	
   478	
   479	def _render(request: dict, result_path: Path, request_path: Path) -> int:
   480	    try:
   481	        _validate_request(request)
   482	        window = request.get("window")
   483	        profile = request.get("profile") or {}
   484	        if isinstance(window, dict):
   485	            start = int(window.get("start_frame", 0))
   486	            end = int(window["end_frame"])
   487	        else:
   488	            start, end = 0, 48
   489	        frames = end - start
   490	        if frames <= 0:
   491	            raise ValueError("window must span at least one frame")
   492	
   493	        output_name = request["output_name"]
   494	        # The invocation workspace is the directory holding the request file;
   495	        # keep every generated artifact contained there.
   496	        workspace = request_path.resolve().parent
   497	        out_dir = workspace / "outputs"
   498	        out_dir.mkdir(parents=True, exist_ok=True)
   499	        video_rel = f"outputs/{output_name}"
   500	        video_path = out_dir / output_name
   501	
   502	        media = _build_mp4(frames)
   503	        video_path.write_bytes(media)
   504	
   505	        probed_profile = {
   506	            "width": WIDTH,
   507	            "height": HEIGHT,
   508	            "fps_rational": list(FPS_RATIONAL),
   509	            "time_base": list(TIME_BASE),
   510	            "container": CONTAINER,
   511	            "video_codec": VIDEO_CODEC,
   512	            "video_profile": None,
   513	            "video_level": None,
   514	            "pixel_format": PIXEL_FORMAT,
   515	            "audio_codec": AUDIO_CODEC,
   516	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   517	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   518	            "duration_tolerance": int(profile.get("duration_tolerance", 1)),
   519	        }
   520	        result = {

 succeeded in 0ms:
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
   225	        # a channel_layout; derive the standard layout only for unambiguous
   226	        # channel counts (mono/stereo). 5.1/7.1 have multiple speaker
   227	        # variants, so those stay unprobed rather than guessed.
   228	        if probe.audio_channel_layout is None:
   229	            channels = _int_or_none(audio_stream.get("channels"), minimum=1)
   230	            probe.audio_channel_layout = {
   231	                1: "mono",
   232	                2: "stereo",
   233	            }.get(channels or 0)
   234	        if probe.duration_rational is None:
   235	            probe.duration_rational = _duration_rational(audio_stream.get("duration"))
   236	            if probe.duration_rational is not None:
   237	                probe.duration_seconds = float(Fraction(*probe.duration_rational))
   238	
   239	    return probe
   240	
   241	
   242	def _ffprobe_metadata(
   243	    file_path: str | Path,
   244	    *,
   245	    timeout: float,
   246	    strict: bool,
   247	) -> MediaProbe:
   248	    ffprobe_exe = shutil.which("ffprobe")
   249	    if ffprobe_exe is None:
   250	        if strict:
   251	            raise MediaProbeError("ffprobe is not available on PATH")
   252	        return MediaProbe()
   253	
   254	    try:
   255	        proc = subprocess.run(
   256	            [
   257	                ffprobe_exe,
   258	                "-v",
   259	                "quiet",
   260	                "-print_format",
   261	                "json",
   262	                "-show_format",
   263	                "-show_streams",
   264	                str(file_path),
   265	            ],
     1	from __future__ import annotations
     2	
     3	import json
     4	import subprocess
     5	from pathlib import Path
     6	from typing import Any
     7	from unittest.mock import patch
     8	
     9	import pytest
    10	
    11	from astrid.core.media import (
    12	    MediaProbeError,
    13	    MediaProbe,
    14	    ffprobe_duration_seconds,
    15	    ffprobe_metadata,
    16	    ffprobe_metadata_strict,
    17	)
    18	from astrid.packs.editorial.executors.editor_review.run import (
    19	    _probe_duration as editor_probe_duration,
    20	)
    21	from astrid.core.verify.checks import ffprobe_duration_seconds as checks_ffprobe_duration_seconds
    22	
    23	
    24	def test_ffprobe_duration_seconds_uses_duration_only_probe() -> None:
    25	    calls: list[tuple[list[str], dict[str, Any]]] = []
    26	
    27	    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    28	        calls.append((cmd, kwargs))
    29	        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")
    30	
    31	    assert ffprobe_duration_seconds("clip.mp4", runner=runner) == 12.5
    32	
    33	    cmd, kwargs = calls[0]
    34	    assert cmd == [
    35	        "ffprobe",
    36	        "-v",
    37	        "error",
    38	        "-show_entries",
    39	        "format=duration",
    40	        "-of",
    41	        "default=noprint_wrappers=1:nokey=1",
    42	        "clip.mp4",
    43	    ]
    44	    assert kwargs["check"] is True
    45	    assert kwargs["capture_output"] is True
    46	    assert kwargs["text"] is True
    47	    assert "PATH" in kwargs["env"]
    48	    assert "OPENAI_API_KEY" not in kwargs["env"]
    49	
    50	
    51	def test_ffprobe_duration_seconds_accepts_explicit_env() -> None:
    52	    calls: list[tuple[list[str], dict[str, Any]]] = []
    53	
    54	    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    55	        calls.append((cmd, kwargs))
    56	        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")
    57	
    58	    assert (
    59	        ffprobe_duration_seconds(
    60	            "clip.mp4", runner=runner, env={"FFPROBE_DATADIR": "/tmp/ffprobe"}
    61	        )
    62	        == 12.5
    63	    )
    64	
    65	    assert calls[0][1]["env"]["FFPROBE_DATADIR"] == "/tmp/ffprobe"
    66	
    67	
    68	def test_updated_duration_helpers_preserve_float_parsing(tmp_path: Path) -> None:
    69	    media = tmp_path / "clip.mp4"
    70	    media.write_bytes(b"not-real-media")
    71	
    72	    def fake_runner(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
    73	        return subprocess.CompletedProcess(cmd, 0, stdout="7.25\n", stderr="")
    74	
    75	    assert ffprobe_duration_seconds(media, runner=fake_runner) == 7.25
    76	    assert editor_probe_duration(media, ffprobe_runner=fake_runner) == 7.25
    77	
    78	
    79	def test_verify_uses_canonical_media_helper() -> None:
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
   187	    def test_layout_derived_from_unambiguous_channel_count(self) -> None:
   188	        """Containers that report channels without channel_layout (e.g.
   189	        QuickTime sowt) derive mono/stereo only — never ambiguous 5.1/7.1."""
   190	        import json as _json
   191	
   192	        payload = json.loads(HAPPY_FFPROBE_JSON)
   193	        for stream in payload["streams"]:
   194	            if stream.get("codec_type") == "audio":
   195	                del stream["channel_layout"]
   196	                stream["channels"] = 2
   197	        with patch(
   198	            "astrid.core.media.subprocess.run",
   199	            return_value=subprocess.CompletedProcess(
   200	                [], 0, stdout=_json.dumps(payload), stderr=""
   201	            ),
   202	        ):
   203	            probe = ffprobe_metadata("video.mp4")
   204	        assert probe.audio_channel_layout == "stereo"
   205	
   206	        for stream in payload["streams"]:
   207	            if stream.get("codec_type") == "audio":
   208	                stream["channels"] = 6
   209	        with patch(
   210	            "astrid.core.media.subprocess.run",
   211	            return_value=subprocess.CompletedProcess(
   212	                [], 0, stdout=_json.dumps(payload), stderr=""
   213	            ),
   214	        ):
   215	            probe = ffprobe_metadata("video.mp4")
   216	        assert probe.audio_channel_layout is None  # 5.1 variants ambiguous
   217	
   218	    def test_accepts_path_object(self, tmp_path: Path) -> None:
   219	        vid = tmp_path / "clip.mp4"
   220	        vid.write_bytes(b"dummy")

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '1,280p'; sed -n '1,160p' tests/fixtures/renderer_packs/raw_command/requests/support.json; sed -n '1,160p' tests/fixtures/renderer_packs/raw_command/requests/render.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '145,275p'; nl -ba tests/core/rendering/fixtures/transport_backend.py | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

2026-08-12T06:46:09.545671Z ERROR codex_core::tools::router: error=exec_command failed for `/bin/zsh -lc 'review_tmp=$(mktemp -d /tmp/batch2-r3-media-review.XXXXXX)
media_path="$review_tmp/raw.mp4"
PYTHONDONTWRITEBYTECODE=1 python3 -c '"'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"raw_fixture_probe\"); open(sys.argv[1], \"wb\").write(m[\"_build_mp4\"](48))' \""'$media_path"
ffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,coded_width,coded_height,avg_frame_rate,r_frame_rate,time_base,pix_fmt,sample_rate,channels,channel_layout,duration:format=format_name,duration -of json "$media_path"
find "$review_tmp" -maxdepth 1 -type f -print -exec stat -f '"'%z bytes' {} \\;
rm -rf \""'$review_tmp"'`: CreateProcess { message: "Rejected(\"`/bin/zsh -lc 'review_tmp=$(mktemp -d /tmp/batch2-r3-media-review.XXXXXX)\\nmedia_path=\\\"$review_tmp/raw.mp4\\\"\\nPYTHONDONTWRITEBYTECODE=1 python3 -c '\\\"'import runpy,sys; m=runpy.run_path(\\\\\\\"tests/fixtures/renderer_packs/raw_command/backend.py\\\\\\\", run_name=\\\\\\\"raw_fixture_probe\\\\\\\"); open(sys.argv[1], \\\\\\\"wb\\\\\\\").write(m[\\\\\\\"_build_mp4\\\\\\\"](48))' \\\\\\\"\\\"'$media_path\\\"\\nffprobe -v error -show_entries stream=index,codec_type,codec_name,width,height,coded_width,coded_height,avg_frame_rate,r_frame_rate,time_base,pix_fmt,sample_rate,channels,channel_layout,duration:format=format_name,duration -of json \\\"$media_path\\\"\\nfind \\\"$review_tmp\\\" -maxdepth 1 -type f -print -exec stat -f '\\\"'%z bytes' {} \\\\\\\\;\\nrm -rf \\\\\\\"\\\"'$review_tmp\\\"'` rejected: rm -f style commands are not permitted. Use a safer approach\")" }
exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '270,390p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc "nl -ba tests/core/util/test_media.py | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/media.py | sed -n '180,250p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   225	        # a channel_layout; derive the standard layout only for unambiguous
   226	        # channel counts (mono/stereo). 5.1/7.1 have multiple speaker
   227	        # variants, so those stay unprobed rather than guessed.
   228	        if probe.audio_channel_layout is None:
   229	            channels = _int_or_none(audio_stream.get("channels"), minimum=1)
   230	            probe.audio_channel_layout = {
   231	                1: "mono",
   232	                2: "stereo",
   233	            }.get(channels or 0)
   234	        if probe.duration_rational is None:
   235	            probe.duration_rational = _duration_rational(audio_stream.get("duration"))
   236	            if probe.duration_rational is not None:
   237	                probe.duration_seconds = float(Fraction(*probe.duration_rational))
   238	
   239	    return probe
   240	
   241	
   242	def _ffprobe_metadata(
   243	    file_path: str | Path,
   244	    *,
   245	    timeout: float,
   246	    strict: bool,
   247	) -> MediaProbe:
   248	    ffprobe_exe = shutil.which("ffprobe")
   249	    if ffprobe_exe is None:
   250	        if strict:

 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	import json
     4	import subprocess
     5	from pathlib import Path
     6	from typing import Any
     7	from unittest.mock import patch
     8	
     9	import pytest
    10	
    11	from astrid.core.media import (
    12	    MediaProbeError,
    13	    MediaProbe,
    14	    ffprobe_duration_seconds,
    15	    ffprobe_metadata,
    16	    ffprobe_metadata_strict,
    17	)
    18	from astrid.packs.editorial.executors.editor_review.run import (
    19	    _probe_duration as editor_probe_duration,
    20	)
    21	from astrid.core.verify.checks import ffprobe_duration_seconds as checks_ffprobe_duration_seconds
    22	
    23	
    24	def test_ffprobe_duration_seconds_uses_duration_only_probe() -> None:
    25	    calls: list[tuple[list[str], dict[str, Any]]] = []
    26	
    27	    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    28	        calls.append((cmd, kwargs))
    29	        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")
    30	
    31	    assert ffprobe_duration_seconds("clip.mp4", runner=runner) == 12.5
    32	
    33	    cmd, kwargs = calls[0]
    34	    assert cmd == [
    35	        "ffprobe",
    36	        "-v",
    37	        "error",
    38	        "-show_entries",
    39	        "format=duration",
    40	        "-of",
    41	        "default=noprint_wrappers=1:nokey=1",
    42	        "clip.mp4",
    43	    ]
    44	    assert kwargs["check"] is True
    45	    assert kwargs["capture_output"] is True
    46	    assert kwargs["text"] is True
    47	    assert "PATH" in kwargs["env"]
    48	    assert "OPENAI_API_KEY" not in kwargs["env"]
    49	
    50	
    51	def test_ffprobe_duration_seconds_accepts_explicit_env() -> None:
    52	    calls: list[tuple[list[str], dict[str, Any]]] = []
    53	
    54	    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    55	        calls.append((cmd, kwargs))
    56	        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")
    57	
    58	    assert (
    59	        ffprobe_duration_seconds(
    60	            "clip.mp4", runner=runner, env={"FFPROBE_DATADIR": "/tmp/ffprobe"}
    61	        )
    62	        == 12.5
    63	    )
    64	
    65	    assert calls[0][1]["env"]["FFPROBE_DATADIR"] == "/tmp/ffprobe"
    66	
    67	
    68	def test_updated_duration_helpers_preserve_float_parsing(tmp_path: Path) -> None:
    69	    media = tmp_path / "clip.mp4"
    70	    media.write_bytes(b"not-real-media")
    71	
    72	    def fake_runner(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
    73	        return subprocess.CompletedProcess(cmd, 0, stdout="7.25\n", stderr="")
    74	
    75	    assert ffprobe_duration_seconds(media, runner=fake_runner) == 7.25
    76	    assert editor_probe_duration(media, ffprobe_runner=fake_runner) == 7.25
    77	
    78	
    79	def test_verify_uses_canonical_media_helper() -> None:
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
   187	    def test_layout_derived_from_unambiguous_channel_count(self) -> None:
   188	        """Containers that report channels without channel_layout (e.g.
   189	        QuickTime sowt) derive mono/stereo only — never ambiguous 5.1/7.1."""
   190	        import json as _json
   191	
   192	        payload = json.loads(HAPPY_FFPROBE_JSON)
   193	        for stream in payload["streams"]:
   194	            if stream.get("codec_type") == "audio":
   195	                del stream["channel_layout"]
   196	                stream["channels"] = 2
   197	        with patch(
   198	            "astrid.core.media.subprocess.run",
   199	            return_value=subprocess.CompletedProcess(
   200	                [], 0, stdout=_json.dumps(payload), stderr=""
   201	            ),
   202	        ):
   203	            probe = ffprobe_metadata("video.mp4")
   204	        assert probe.audio_channel_layout == "stereo"
   205	
   206	        for stream in payload["streams"]:
   207	            if stream.get("codec_type") == "audio":
   208	                stream["channels"] = 6
   209	        with patch(
   210	            "astrid.core.media.subprocess.run",
   211	            return_value=subprocess.CompletedProcess(
   212	                [], 0, stdout=_json.dumps(payload), stderr=""
   213	            ),
   214	        ):
   215	            probe = ffprobe_metadata("video.mp4")
   216	        assert probe.audio_channel_layout is None  # 5.1 variants ambiguous
   217	
   218	    def test_accepts_path_object(self, tmp_path: Path) -> None:
   219	        vid = tmp_path / "clip.mp4"
   220	        vid.write_bytes(b"dummy")
   221	        with patch("subprocess.run") as mock_run, patch(
   222	            "shutil.which", return_value="/usr/bin/ffprobe"
   223	        ):
   224	            mock_run.return_value = subprocess.CompletedProcess(
   225	                [], 0, stdout=HAPPY_FFPROBE_JSON, stderr=""
   226	            )
   227	            probe = ffprobe_metadata(vid)
   228	
   229	        assert probe.duration_seconds == pytest.approx(12.5)
   230	
   231	    def test_prefers_average_frame_rate_and_skips_attached_picture(self) -> None:
   232	        payload = json.dumps(
   233	            {
   234	                "format": {"duration": "2", "format_name": "matroska,webm"},
   235	                "streams": [
   236	                    {
   237	                        "codec_type": "video",
   238	                        "codec_name": "mjpeg",
   239	                        "disposition": {"attached_pic": 1},
   240	                    },
   241	                    {
   242	                        "codec_type": "video",
   243	                        "codec_name": "vp9",
   244	                        "pix_fmt": "yuv420p",
   245	                        "width": 1280,
   246	                        "height": 720,
   247	                        "avg_frame_rate": "24/1",
   248	                        "r_frame_rate": "30/1",
   249	                        "time_base": "1/1000",
   250	                    },
   251	                ],
   252	            }
   253	        )
   254	        with patch("subprocess.run") as mock_run, patch(
   255	            "shutil.which", return_value="/usr/bin/ffprobe"
   256	        ):
   257	            mock_run.return_value = subprocess.CompletedProcess(
   258	                [], 0, stdout=payload, stderr=""
   259	            )
   260	            probe = ffprobe_metadata("video.webm")

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '1,390p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   291	        _box(b"frma", b"sowt")
   292	        + _box(b"enda", struct.pack(">H", 1))
   293	        + _box(
   294	            b"chan",
   295	            struct.pack(">I", 0)  # version/flags
   296	            + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)  # layout tag
   297	            + struct.pack(">I", 0),  # bitmap
   298	        ),
   299	    )
   300	    audio = (
   301	        b"\x00" * 6
   302	        + struct.pack(">H", 1)             # data_reference_index
   303	        + struct.pack(">HH", 0, 0)
   304	        + struct.pack(">I", 0)             # vendor
   305	        + struct.pack(">HH", AUDIO_CHANNELS, AUDIO_BITS)
   306	        + struct.pack(">HH", 0, 0)         # compressionid, packetsize
   307	        + struct.pack(">I", AUDIO_SAMPLE_RATE << 16)
   308	    )
   309	    return _box(b"sowt", audio + wave)
   310	
   311	
   312	def _sample_tables(
   313	    *,
   314	    video_frames: int,
   315	    video_sizes: list[int],
   316	    video_chunk_offset: int,
   317	    audio_bytes: bytes,
   318	    audio_samples: int,
   319	    audio_chunk_offset: int,
   320	) -> bytes:
   321	    stsd_v = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _avc1_entry(_sps_nal(), _pps_nal()))
   322	    stts_v = _fullbox(
   323	        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", video_frames, SAMPLES_PER_FRAME)
   324	    )
   325	    stsc_v = _fullbox(
   326	        b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, video_frames, 1)
   327	    )
   328	    stsz_v = _fullbox(
   329	        b"stsz", 0, struct.pack(">II", 0, video_frames)
   330	        + b"".join(struct.pack(">I", size) for size in video_sizes)
   331	    )
   332	    stco_v = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", video_chunk_offset))
   333	
   334	    stsd_a = _fullbox(b"stsd", 0, struct.pack(">I", 1) + _sowt_entry())
   335	    stts_a = _fullbox(
   336	        b"stts", 0, struct.pack(">I", 1) + struct.pack(">II", 1, audio_samples)
   337	    )
   338	    stsc_a = _fullbox(b"stsc", 0, struct.pack(">I", 1) + struct.pack(">III", 1, 1, 1))
   339	    stsz_a = _fullbox(
   340	        b"stsz", 0, struct.pack(">II", 0, 1) + struct.pack(">I", len(audio_bytes))
   341	    )
   342	    stco_a = _fullbox(b"stco", 0, struct.pack(">I", 1) + struct.pack(">I", audio_chunk_offset))
   343	
   344	    video_stbl = _box(b"stbl", stsd_v + stts_v + stsc_v + stsz_v + stco_v)
   345	    audio_stbl = _box(b"stbl", stsd_a + stts_a + stsc_a + stsz_a + stco_a)
   346	    return video_stbl, audio_stbl
   347	
   348	
   349	def _build_mp4(frames: int) -> bytes:
   350	    """Return a deterministic MP4: `frames` H.264 IDR frames + PCM silence."""
   351	    video_chunk = bytearray()
   352	    video_sizes: list[int] = []
   353	    for frame_index in range(frames):
   354	        nal = _idr_slice_nal(frame_index)
   355	        sample = struct.pack(">I", len(nal)) + nal
   356	        video_chunk += sample
   357	        video_sizes.append(len(sample))
   358	    video_chunk = bytes(video_chunk)
   359	
   360	    audio_samples = frames * (AUDIO_SAMPLE_RATE // FPS_RATIONAL[0])
   361	    audio_bytes = b"\x00" * (audio_samples * AUDIO_CHANNELS * (AUDIO_BITS // 8))
   362	
   363	    ftyp = _ftyp()
   364	    video_chunk_offset = len(ftyp) + 8
   365	    audio_chunk_offset = video_chunk_offset + len(video_chunk)
   366	
   367	    video_stbl, audio_stbl = _sample_tables(
   368	        video_frames=frames,
   369	        video_sizes=video_sizes,
   370	        video_chunk_offset=video_chunk_offset,
   371	        audio_bytes=audio_bytes,
   372	        audio_samples=audio_samples,
   373	        audio_chunk_offset=audio_chunk_offset,
   374	    )
   375	
   376	    vmhd = _fullbox(b"vmhd", 1, struct.pack(">H", 0) + b"\x00" * 6)
   377	    smhd = _fullbox(b"smhd", 0, struct.pack(">HH", 0, 0))
   378	    dinf = _dinf()
   379	
   380	    minf_v = _box(b"minf", vmhd + dinf + video_stbl)
   381	    mdia_v = _box(b"mdia", _mdhd(12288, frames * SAMPLES_PER_FRAME) + _hdlr(b"vide", b"VideoHandler") + minf_v)
   382	    trak_v = _box(b"trak", _tkhd(1, frames * SAMPLES_PER_FRAME, 0, WIDTH, HEIGHT) + mdia_v)
   383	
   384	    minf_a = _box(b"minf", smhd + dinf + audio_stbl)
   385	    mdia_a = _box(b"mdia", _mdhd(AUDIO_SAMPLE_RATE, audio_samples) + _hdlr(b"soun", b"SoundHandler") + minf_a)
   386	    trak_a = _box(b"trak", _tkhd(2, audio_samples, 0x0100, 0, 0) + mdia_a)
   387	
   388	    moov = _box(b"moov", _mvhd(frames * SAMPLES_PER_FRAME) + trak_v + trak_a)
   389	    mdat = _box(b"mdat", video_chunk + audio_bytes)
   390	    return ftyp + mdat + moov

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '390,575p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   390	    return ftyp + mdat + moov
   391	
   392	
   393	# ---------------------------------------------------------------------------
   394	# Protocol verbs
   395	# ---------------------------------------------------------------------------
   396	
   397	
   398	def _write_json(path: Path, payload: dict) -> None:
   399	    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
   400	
   401	
   402	def _write_error(result_path: Path, kind: str, message: str, details: dict) -> None:
   403	    _write_json(
   404	        result_path,
   405	        {
   406	            "schema_version": 1,
   407	            "kind": kind,
   408	            "backend": BACKEND_ID,
   409	            "message": message,
   410	            "recovery_command": None,
   411	            "details": details,
   412	        },
   413	    )
   414	
   415	
   416	def _validate_request(request: dict) -> None:
   417	    version = request.get("schema_version")
   418	    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
   419	        raise ValueError(
   420	            f"unsupported request schema_version {version!r}; expected 1"
   421	        )
   422	    output_name = request.get("output_name")
   423	    if not isinstance(output_name, str) or output_name in (".", ".."):
   424	        raise ValueError("output_name must be a non-empty portable basename")
   425	    if not _OUTPUT_NAME_RE.fullmatch(output_name):
   426	        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
   427	    window = request.get("window")
   428	    if window is not None and not isinstance(window, dict):
   429	        raise ValueError("window must be an object or null")
   430	    if isinstance(window, dict):
   431	        end = window.get("end_frame")
   432	        start = window.get("start_frame", 0)
   433	        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
   434	            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
   435	
   436	
   437	def _support(request: dict, result_path: Path) -> int:
   438	    profile = request.get("profile")
   439	    if isinstance(profile, dict):
   440	        # The renderer can only produce its own exact codec set; a request
   441	        # for a different codec is unsupported (fail closed).
   442	        if (
   443	            profile.get("audio_codec") not in (None, AUDIO_CODEC)
   444	            or profile.get("video_codec") not in (None, VIDEO_CODEC)
   445	            or profile.get("width") not in (None, WIDTH)
   446	            or profile.get("height") not in (None, HEIGHT)
   447	        ):
   448	            _write_json(
   449	                result_path,
   450	                {
   451	                    "schema_version": 1,
   452	                    "supported": False,
   453	                    "reasons": [
   454	                        f"requested profile {profile.get('audio_codec')}/"
   455	                        f"{profile.get('video_codec')} is not produced by {BACKEND_ID}"
   456	                    ],
   457	                    "features": {"media": False, "audio_mode": "none"},
   458	                    "alternatives": [],
   459	                    "backend": BACKEND_ID,
   460	                    "backend_version": "1.0.0",
   461	                },
   462	            )
   463	            return 0
   464	    _write_json(
   465	        result_path,
   466	        {
   467	            "schema_version": 1,
   468	            "supported": True,
   469	            "reasons": [],
   470	            "features": {"media": True, "audio_mode": "rendered"},
   471	            "alternatives": [],
   472	            "backend": BACKEND_ID,
   473	            "backend_version": BACKEND_VERSION,
   474	        },
   475	    )
   476	    return 0
   477	
   478	
   479	def _render(request: dict, result_path: Path, request_path: Path) -> int:
   480	    try:
   481	        _validate_request(request)
   482	        window = request.get("window")
   483	        profile = request.get("profile") or {}
   484	        if isinstance(window, dict):
   485	            start = int(window.get("start_frame", 0))
   486	            end = int(window["end_frame"])
   487	        else:
   488	            start, end = 0, 48
   489	        frames = end - start
   490	        if frames <= 0:
   491	            raise ValueError("window must span at least one frame")
   492	
   493	        output_name = request["output_name"]
   494	        # The invocation workspace is the directory holding the request file;
   495	        # keep every generated artifact contained there.
   496	        workspace = request_path.resolve().parent
   497	        out_dir = workspace / "outputs"
   498	        out_dir.mkdir(parents=True, exist_ok=True)
   499	        video_rel = f"outputs/{output_name}"
   500	        video_path = out_dir / output_name
   501	
   502	        media = _build_mp4(frames)
   503	        video_path.write_bytes(media)
   504	
   505	        probed_profile = {
   506	            "width": WIDTH,
   507	            "height": HEIGHT,
   508	            "fps_rational": list(FPS_RATIONAL),
   509	            "time_base": list(TIME_BASE),
   510	            "container": CONTAINER,
   511	            "video_codec": VIDEO_CODEC,
   512	            "video_profile": None,
   513	            "video_level": None,
   514	            "pixel_format": PIXEL_FORMAT,
   515	            "audio_codec": AUDIO_CODEC,
   516	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   517	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   518	            "duration_tolerance": int(profile.get("duration_tolerance", 1)),
   519	        }
   520	        result = {
   521	            "schema_version": 1,
   522	            "video": {
   523	                "path": video_rel,
   524	                "profile": probed_profile,
   525	                "sha256": hashlib.sha256(media).hexdigest(),
   526	                "duration_frames": frames,
   527	                "audio": "rendered",
   528	                "attachments": {},
   529	            },
   530	            "backend_fragments": {
   531	                BACKEND_ID: {
   532	                    "renderer": "raw_command",
   533	                    "media": "generated",
   534	                    "audio_mode": "rendered",
   535	                    "deterministic": True,
   536	                }
   537	            },
   538	            "audio_ownership": "rendered",
   539	            "normalization": [],
   540	            "logs": [],
   541	            "metadata": {},
   542	        }
   543	        _write_json(result_path, result)
   544	        return 0
   545	    except ValueError as exc:
   546	        _write_error(result_path, "protocol", str(exc), {"error_type": "ValueError"})
   547	        return 0
   548	    except Exception as exc:  # pragma: no cover - unexpected failure path
   549	        _write_error(
   550	            result_path,
   551	            "internal",
   552	            f"raw_command renderer failed: {exc}",
   553	            {"error_type": type(exc).__name__},
   554	        )
   555	        return 0
   556	
   557	
   558	def main(argv: list[str]) -> int:
   559	    parser = argparse.ArgumentParser(
   560	        prog="backend.py",
   561	        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
   562	    )
   563	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
   564	    parser.add_argument("--request", required=True, help="absolute path to request JSON")
   565	    parser.add_argument("--result", required=True, help="absolute path to result JSON")
   566	    args = parser.parse_args(argv)
   567	
   568	    request_path = Path(args.request)
   569	    result_path = Path(args.result)
   570	    try:
   571	        request = json.loads(request_path.read_text(encoding="utf-8"))
   572	        if not isinstance(request, dict):
   573	            raise TypeError(
   574	                f"request must be a JSON object, got {type(request).__name__}"
   575	            )

exec
/bin/zsh -lc 'rg -n "def validate_render_result|class RenderValidation|ValidationMode|STRICT" astrid/core/rendering tests/core/rendering | head -120' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/artifacts.py:630:def validate_render_result(
tests/core/rendering/test_raw_command_fixture.py:280:    # The fixture output must pass STRICT artifact validation against the

exec
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '558,640p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   558	def main(argv: list[str]) -> int:
   559	    parser = argparse.ArgumentParser(
   560	        prog="backend.py",
   561	        description="Raw v1 rendering protocol fixture backend (no Astrid SDK).",
   562	    )
   563	    parser.add_argument("verb", choices=("render", "support", "plan", "finalize"))
   564	    parser.add_argument("--request", required=True, help="absolute path to request JSON")
   565	    parser.add_argument("--result", required=True, help="absolute path to result JSON")
   566	    args = parser.parse_args(argv)
   567	
   568	    request_path = Path(args.request)
   569	    result_path = Path(args.result)
   570	    try:
   571	        request = json.loads(request_path.read_text(encoding="utf-8"))
   572	        if not isinstance(request, dict):
   573	            raise TypeError(
   574	                f"request must be a JSON object, got {type(request).__name__}"
   575	            )
   576	    except Exception as exc:
   577	        _write_error(
   578	            result_path,
   579	            "protocol",
   580	            f"cannot read request JSON from {request_path}: {exc}",
   581	            {"error_type": type(exc).__name__},
   582	        )
   583	        return 0
   584	
   585	    if args.verb == "support":
   586	        try:
   587	            _validate_request(request)
   588	        except ValueError as exc:
   589	            _write_error(
   590	                result_path,
   591	                "protocol",
   592	                f"invalid support request: {exc}",
   593	                {"error_type": type(exc).__name__},
   594	            )
   595	            return 0
   596	        return _support(request, result_path)
   597	    if args.verb in ("plan", "finalize"):
   598	        _write_error(
   599	            result_path,
   600	            "unsupported",
   601	            f"{BACKEND_ID} only implements render and support",
   602	            {"verb": args.verb},
   603	        )
   604	        return 0
   605	    return _render(request, result_path, request_path)
   606	
   607	
   608	if __name__ == "__main__":
   609	    raise SystemExit(main(sys.argv[1:]))

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '350,710p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/publication.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
   229	        try:
   230	            # For bare paths the default sidecar is derived from the raw
   231	            # video path; it must be checked unresolved like an explicit one.
   232	            raw_sidecar = (
   233	                Path(raw_sidecar_candidate).expanduser()
   234	                if raw_sidecar_candidate is not None
   235	                else _default_sidecar_path(raw_path)
   236	            )
   237	            if raw_sidecar.is_symlink():
   238	                continue
   239	        except (OSError, TypeError):
   240	            continue
   241	        if video == live_output or video in seen:
   242	            continue
   243	        seen.add(video)
   244	
   245	        # Never wait while holding the live output lock.  Two concurrent
   246	        # publications for sibling outputs can otherwise deadlock while each
   247	        # tries to clean the other, and a locked candidate is by definition a
   248	        # live render that cleanup must preserve.
   249	        candidate_lock = _lock_for(video)
   250	        try:
   251	            candidate_lock.acquire(timeout=0)
   252	        except (Timeout, OSError):
   253	            continue
   254	        try:
   255	            provenance = read_committed_provenance(video, sidecar_path=sidecar)
   256	            if provenance is None or provenance.get("timeline") != timeline:
   257	                continue
   258	            try:
   259	                # The marker disappears first.  A crash or failure between
   260	                # these unlinks leaves an orphan, never a false committed pair.
   261	                sidecar.unlink()
   262	            except (FileNotFoundError, OSError):
   263	                continue
   264	            try:
   265	                video.unlink()
   266	            except (FileNotFoundError, OSError):
   267	                pass
   268	        finally:
   269	            candidate_lock.release()
   270	
   271	
   272	def publish_render_result(
   273	    video_path: str | Path,
   274	    provenance_payload: Mapping[str, Any],
   275	    *,
   276	    out_path: str | Path,
   277	    sidecar_path: str | Path,
   278	    previous_outputs: Iterable[object] = (),
   279	) -> Path:
   280	    """Publish one video and atomically commit its hashed provenance marker.
   281	
   282	    The source video is validated before any destination mutation.  Under the
   283	    per-output lock an old marker is invalidated, the video is moved into
   284	    place with :func:`os.replace`, and the complete sidecar is written
   285	    atomically last.  A sidecar-write failure therefore leaves a detectable,
   286	    recoverable orphan video and is propagated to the caller.
   287	    """
   288	
   289	    if not isinstance(provenance_payload, Mapping):
   290	        raise TypeError("provenance_payload must be a mapping")
   291	
   292	    source = _resolved(video_path)
   293	    output = _resolved(out_path)
   294	    sidecar = _resolved(sidecar_path)
   295	    source_unresolved = Path(video_path).expanduser()
   296	    output_unresolved = Path(out_path).expanduser()
   297	    sidecar_unresolved = Path(sidecar_path).expanduser()
   298	    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
   299	        raise_invalid_artifact_error(
   300	            backend=_BACKEND,
   301	            message="publication paths must not be symbolic links",
   302	            recovery_command=_RECOVERY,
   303	        )
   304	    _validate_source_video(source)
   305	
   306	    output.parent.mkdir(parents=True, exist_ok=True)
   307	    sidecar.parent.mkdir(parents=True, exist_ok=True)
   308	    with _lock_for(output):
   309	        # Validate again after waiting for the lock so a moved or truncated
   310	        # staging artifact can never be reported as successfully published.
   311	        _validate_source_video(source)
   312	
   313	        # Invalidate the previous marker BEFORE the first destination
   314	        # mutation: a crash can then leave an orphan video (recoverable) but
   315	        # can never leave a stale marker claiming the new bytes are committed.
   316	        sidecar.unlink(missing_ok=True)
   317	        os.replace(source, output)
   318	        digest = sha256_file(output)
   319	        committed_payload = dict(provenance_payload)
   320	        committed_payload["output"] = str(output)
   321	        committed_payload["sha256"] = digest
   322	        write_json_atomic(sidecar, committed_payload)
   323	
   324	        # Cleanup happens only after the new pair is committed and while its
   325	        # lock remains held.  Candidate locks are non-blocking (see above).
   326	        _delete_previous_outputs(
   327	            previous_outputs,
   328	            live_output=output,
   329	            timeline=committed_payload.get("timeline"),
   330	        )

exec
/bin/zsh -lc "git diff --name-status 7f7c25d5..8c195bf0; git ls-files | rg '("'^|/)__pycache__/|'"\\.py[co]"'$'"' || true; rg -n 'tests/fixtures/\\*\\*/__pycache__|__pycache__' .gitignore" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	.gitignore
A	.oracle/checkins/batch-2-r2.md
M	astrid/core/media.py
M	astrid/core/rendering/publication.py
M	astrid/core/rendering/transport.py
M	astrid/packs/rendering/executors/render/run.py
M	tests/core/rendering/test_raw_command_fixture.py
M	tests/core/util/test_media.py
D	tests/fixtures/renderer_packs/raw_command/__pycache__/backend.cpython-311.pyc
M	tests/fixtures/renderer_packs/raw_command/backend.py
M	tests/fixtures/renderer_packs/raw_command/requests/support.json
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
20:__pycache__/
64:tests/fixtures/__pycache__/
65:tests/fixtures/**/__pycache__/
69:tests/agentic/__pycache__/

exec
/bin/zsh -lc "rg -n \"symlink|previous_outputs|_render_with_publication_context|publish_render_result\" tests astrid | rg 'publication|render_with_publication|run.py|test_render' | head -260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_publication.py:16:    publish_render_result,
tests/core/rendering/test_publication.py:48:    result = publish_render_result(
tests/core/rendering/test_publication.py:53:        previous_outputs=(),
tests/core/rendering/test_publication.py:99:            publish_render_result(
tests/core/rendering/test_publication.py:104:                previous_outputs=(),
tests/core/rendering/test_publication.py:152:    publish_render_result(
tests/core/rendering/test_publication.py:157:        previous_outputs=(),
tests/core/rendering/test_publication.py:192:    publish_render_result(
tests/core/rendering/test_publication.py:197:        previous_outputs=[
tests/core/rendering/test_publication.py:240:        publish_render_result(
tests/core/rendering/test_publication.py:245:            previous_outputs=(),
tests/core/rendering/test_publication.py:268:        publish_render_result(
tests/core/rendering/test_publication.py:273:            previous_outputs=(),
astrid/packs/moirae/executors/moirae/run.py:29:        Path(args.output).symlink_to(output.name)
astrid/core/rendering/publication.py:144:        if video_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
astrid/core/rendering/publication.py:146:        if video.is_symlink() or sidecar.is_symlink():
astrid/core/rendering/publication.py:202:def _delete_previous_outputs(
astrid/core/rendering/publication.py:203:    previous_outputs: Iterable[object],
astrid/core/rendering/publication.py:211:    for candidate in previous_outputs:
astrid/core/rendering/publication.py:219:        # Never delete through a symlink: neither the raw video nor the raw
astrid/core/rendering/publication.py:225:            if raw_path.is_symlink():
astrid/core/rendering/publication.py:237:            if raw_sidecar.is_symlink():
astrid/core/rendering/publication.py:272:def publish_render_result(
astrid/core/rendering/publication.py:278:    previous_outputs: Iterable[object] = (),
astrid/core/rendering/publication.py:298:    if source_unresolved.is_symlink() or output_unresolved.is_symlink() or sidecar_unresolved.is_symlink():
astrid/core/rendering/publication.py:326:        _delete_previous_outputs(
astrid/core/rendering/publication.py:327:            previous_outputs,
astrid/core/rendering/publication.py:345:    "publish_render_result",
astrid/packs/iteration/executors/experiment_import/run.py:89:    """Return a contained real submission directory, rejecting symlink roots."""
astrid/packs/iteration/executors/experiment_import/run.py:90:    if path.is_symlink():
astrid/packs/iteration/executors/experiment_import/run.py:99:    """Return a contained regular source file, rejecting file symlinks."""
astrid/packs/iteration/executors/experiment_import/run.py:100:    if path.is_symlink():
astrid/packs/iteration/executors/experiment_import/run.py:149:    if src.is_symlink() or not src.is_file():
astrid/packs/iteration/executors/experiment_import/run.py:156:    if dst.is_file() and not dst.is_symlink() and not _same_inode(src, dst):
astrid/packs/iteration/executors/experiment_import/run.py:643:            recovery_command="remove symlinked or escaping submission directories",
astrid/packs/iteration/executors/experiment_prepare/run.py:126:            if run_json_path.is_file() and not run_json_path.is_symlink():
astrid/packs/iteration/executors/experiment_prepare/run.py:152:                # The shared resolver also rejects symlink escapes here before
astrid/packs/rendering/executors/render/run.py:35:from astrid.core.rendering.publication import publish_render_result
astrid/packs/rendering/executors/render/run.py:44:    "render_publication_previous_outputs",
astrid/packs/rendering/executors/render/run.py:442:    _previous_outputs: Sequence[Path] | None = None,
astrid/packs/rendering/executors/render/run.py:466:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:471:            previous_outputs=(
astrid/packs/rendering/executors/render/run.py:473:                if _previous_outputs is None
astrid/packs/rendering/executors/render/run.py:474:                else _previous_outputs
astrid/packs/rendering/executors/render/run.py:682:                    _previous_outputs=(),
astrid/packs/rendering/executors/render/run.py:713:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:718:            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
astrid/packs/rendering/executors/render/run.py:778:    if not link.is_symlink():
astrid/packs/rendering/executors/render/run.py:1231:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1236:            previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
astrid/packs/rendering/executors/render/run.py:1279:def _render_with_publication_context(
astrid/packs/rendering/executors/render/run.py:1413:            output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1418:                previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
astrid/packs/rendering/executors/render/run.py:1460:    previous_outputs = (
astrid/packs/rendering/executors/render/run.py:1465:    publication_token = _PUBLICATION_PREVIOUS_OUTPUTS.set(previous_outputs)
astrid/packs/rendering/executors/render/run.py:1467:        return _render_with_publication_context(
astrid/packs/iteration/orchestrators/experiment_review_session/run.py:15:  permitting traversal/symlink escape.  Mounts are configured at server-launch

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '400,500p'; nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '640,735p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   400	        cursor = at + _clip_duration_seconds(clip)
   401	        audio_index += 1
   402	    if not audio_labels:
   403	        duration = sum(_clip_duration_seconds(clip) for clip in video_clips)
   404	        filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration:.6f}[a0]")
   405	        audio_labels.append("[a0]")
   406	    filters.append("".join(audio_labels) + f"concat=n={len(audio_labels)}:v=0:a=1[aout]")
   407	
   408	    out_path.parent.mkdir(parents=True, exist_ok=True)
   409	    subprocess.run(
   410	        [
   411	            "ffmpeg",
   412	            "-hide_banner",
   413	            "-y",
   414	            *inputs,
   415	            "-filter_complex",
   416	            ";".join(filters),
   417	            "-map",
   418	            f"{copy_video_input}:v:0" if copy_video_input is not None else "[vout]",
   419	            "-map",
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
   491	            stage="render_ffmpeg",
   492	            label="Render media-only timeline with ffmpeg",
   493	            parents=[timeline_id, assets_id],
   494	            outputs=[render_id],
   495	            metadata={"engine": "ffmpeg"},
   496	        )
   497	    return output
   498	
   499	
   500	def _can_render_with_ffmpeg_media(timeline_path: Path, assets_path: Path) -> bool:
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
   731	            metadata={"engine": "hybrid", "segments": segments},
   732	        )
   733	        audit.register_node(
   734	            stage="render_hybrid",
   735	            label="Render hybrid timeline",

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1180,1260p'; nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1270,1435p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_publication.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '1435,1510p'; rg -n \"out_path\\s*=|args\\.out|Path\\(.*out\" astrid/packs/rendering/executors/render/run.py | tail -80" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
  1251	            stage="render_ffmpeg_audio_reactive_colour",
  1252	        )
  1253	        render_id = audit.register_asset(
  1254	            kind="render",
  1255	            path=output,
  1256	            label="Rendered audio-reactive colour video",
  1257	            parents=[timeline_id, assets_id],
  1258	            stage="render_ffmpeg_audio_reactive_colour",
  1259	            metadata={
  1260	                "engine": "ffmpeg",
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
  1290	    out_path = Path(out_path)
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

 succeeded in 0ms:
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

 succeeded in 0ms:
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
  1506	            with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
  1507	                assets_path = Path(tmp_text) / "hype.assets.json"
  1508	                _write_empty_asset_registry(assets_path)
  1509	                output = render(
  1510	                    args.timeline,
446:    out_path = out_path.resolve()
452:        staged_video = Path(publication_tmp) / out_path.name
469:            out_path=out_path,
661:    out_path = out_path.resolve()
674:            segment_out_path = segment_dir / "segment.mp4"
716:            out_path=out_path,
962:    return Path(f"{out_path}.provenance.json")
976:    out_path = out_path.resolve()
1185:    out_path = out_path.resolve()
1210:        staged_video = Path(publication_tmp) / out_path.name
1234:            out_path=out_path,
1290:    out_path = Path(out_path)
1364:            staged_video = Path(publication_tmp) / out_path.name
1416:                out_path=out_path,
1459:    out_path = Path(out_path)
1512:                    args.out,
1524:                args.out,

exec
/bin/zsh -lc 'rg -n "publication.*symlink|symlink.*publication|output.*symlink|_render_with_publication_context" tests | head -200' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/integrations/test_arnold_step_adapter.py:751:        """A complete per-output CAS hit skips execution and symlinks declared outputs."""
tests/core/integrations/test_arnold_step_adapter.py:812:        """A CAS miss interns declared outputs and symlinks them back into the run dir."""

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '920,1010p'; rg -n \"def _render_.*\\(|out_path = out_path.resolve\\(\\)\" astrid/packs/rendering/executors/render/run.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   920	        if isinstance(clip_id, str) and clip_id:
   921	            clip_ids_by_effect.setdefault(effect_id, []).append(clip_id)
   922	
   923	    if not used_effect_ids:
   924	        return {"root": None, "effects": []}
   925	
   926	    public_root = project_dir / "public" / "astrid-effects" / render_hash
   927	    staged_by_effect: dict[str, dict[str, str]] = {}
   928	    for effect_id in sorted(used_effect_ids):
   929	        element = effects[effect_id]
   930	        staged_assets: dict[str, str] = {}
   931	        for asset in element.assets:
   932	            source = (element.root / asset.path).resolve()
   933	            relative_target = Path(effect_id) / asset.path
   934	            target = public_root / relative_target
   935	            target.parent.mkdir(parents=True, exist_ok=True)
   936	            shutil.copy2(source, target)
   937	            staged_assets[asset.name] = f"astrid-effects/{render_hash}/{relative_target.as_posix()}"
   938	        staged_by_effect[effect_id] = staged_assets
   939	
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
298:def _render_ffmpeg_media_to_path(timeline_path: Path, assets_path: Path, out_path: Path) -> Path:
437:def _render_ffmpeg_media(
446:    out_path = out_path.resolve()
651:def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
661:    out_path = out_path.resolve()
835:def _render_asset_stage_hash(timeline_path: Path, assets_path: Path, out_path: Path) -> str:
961:def _render_provenance_sidecar_path(out_path: Path) -> Path:
976:    out_path = out_path.resolve()
1011:def _render_provenance_payload(
1153:def _render_audio_reactive_colour_if_supported(
1185:    out_path = out_path.resolve()
1279:def _render_with_publication_context(

exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_publication.py | sed -n '280,430p'; rg -n \"bare|default sidecar|symlink\" tests/core/rendering/test_publication.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
exec
/bin/zsh -lc "nl -ba tests/core/rendering/test_raw_command_fixture.py | sed -n '390,620p'; rg -n \"unsupported|profile|audio_codec|width|support\" tests/core/rendering/test_raw_command_fixture.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
9:both ``render`` and ``support`` through :class:`CommandTransport`, verify the
171:    profile = result.video.profile
172:    assert profile.width == 1920
173:    assert profile.height == 1080
174:    assert profile.fps_rational == (24, 1)
175:    assert profile.time_base == (1, 12288)
176:    assert profile.container == "mp4"
177:    assert profile.video_codec == "h264"
178:    assert profile.pixel_format == "yuv420p"
179:    assert profile.audio_codec == "pcm_s16le"
180:    assert profile.audio_sample_rate == 48000
181:    assert profile.audio_channel_layout == "stereo"
228:        assert candidate.manifest.operations == ("render", "support")
240:        assert caps["supports_full_timeline"] is True
241:        assert caps["supports_windows"] is True
242:        assert caps["output_profiles"] == ["video/mp4"]
281:    # request profile (dimensions, FPS, codecs, pixel format, audio).
292:        expected_profile=parsed_request.profile,
306:def test_support_verb_via_command_transport(tmp_path: Path) -> None:
308:    _, report, _ = _run_transport(workspace, PACK_ROOT, verb="support", request_name="support.json")
312:    assert report.supported is True
320:def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
323:        tmp_path / "workspace-support",
325:        verb="support",
326:        request_name="support.json",
398:    _, support, _ = _run_transport(
399:        tmp_path / "workspace-installed-support",
401:        verb="support",
402:        request_name="support.json",
404:    assert isinstance(support, SupportReport)
405:    assert support.backend == BACKEND_ID

codex
The first concrete bypass is already visible: removing `.resolve()` at the dispatcher does not preserve the raw output path through the FFmpeg, hybrid, or audio-reactive branches, because each helper resolves it again before calling publication. I’m now validating whether that is the only remaining blocker and checking the claimed strict media pass against a real generated fixture.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/test_transport.py tests/core/rendering/test_raw_command_fixture.py tests/core/util/test_media.py tests/core/rendering/test_publication.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 394ms:
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
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,sys; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\", run_name=\"review\"); sys.stdout.buffer.write(m[\"_build_mp4\"](48))' | ffprobe -v error -show_streams -show_format -of json pipe:0" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 272ms:
[mov,mp4,m4a,3gp,3g2,mj2 @ 0x138f04280] stream 0, offset 0x28: partial file
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
/bin/zsh -lc "command -v mp4dump || true; command -v mediainfo || true; command -v exiftool || true; command -v ffprobe || true; ffprobe -version | sed -n '1,3p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
/opt/homebrew/bin/ffprobe
ffprobe version 7.1.1 Copyright (c) 2007-2025 the FFmpeg developers
built with Apple clang version 17.0.0 (clang-1700.0.13.3)
configuration: --prefix=/opt/homebrew/Cellar/ffmpeg/7.1.1_3 --enable-shared --enable-pthreads --enable-version3 --cc=clang --host-cflags= --host-ldflags='-Wl,-ld_classic' --enable-ffplay --enable-gnutls --enable-gpl --enable-libaom --enable-libaribb24 --enable-libbluray --enable-libdav1d --enable-libharfbuzz --enable-libjxl --enable-libmp3lame --enable-libopus --enable-librav1e --enable-librist --enable-librubberband --enable-libsnappy --enable-libsrt --enable-libssh --enable-libsvtav1 --enable-libtesseract --enable-libtheora --enable-libvidstab --enable-libvmaf --enable-libvorbis --enable-libvpx --enable-libwebp --enable-libx264 --enable-libx265 --enable-libxml2 --enable-libxvid --enable-lzma --enable-libfontconfig --enable-libfreetype --enable-frei0r --enable-libass --enable-libopencore-amrnb --enable-libopencore-amrwb --enable-libopenjpeg --enable-libspeex --enable-libsoxr --enable-libzmq --enable-libzimg --disable-libjack --disable-indev=jack --enable-videotoolbox --enable-audiotoolbox --enable-neon

web search: 
web search: site:developer.apple.com AudioChannelLayout mChannelLayoutTag mChannelBitmap mNumberChannelDescriptions ...
web search: 
web search: 'mov_write_chan_tag'
web search: 
web search: site:github.com/FFmpeg/FFmpeg "ff_mov_write_chan" ...
web search: 
web search: 
web search: 
web search: 
web search: 
web search: 'int ff_mov_read_chan'
web search: 
web search: site:ffmpeg.org/doxygen/8.0 mov_read_chan avio_rb32 chan atom
web search: 
web search: 'ff_mov_read_chan(c->fc'
web search: 
web search: 
exec
/bin/zsh -lc "rg -n \"Batch 2|batch 2|T2\\.2|raw.command|support|publication|transport\" .oracle/tasklist.md | head -220" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
5:**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
26:## Batch 2 — Command protocol and host-owned plumbing
28:**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.
32:- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
52:**Checkpoint:** The oracle reviews the Remotion, FFmpeg, and FFmpeg-finalizer implementations behind the shared manifests and wire protocol, including concurrency, strict support diagnostics, audio semantics, real FFmpeg output, and facade compatibility. Batch 4 cannot begin until the oracle returns `PASS`.
59:- Strict FFmpeg support fails closed for unknown kinds, invalid bounds, visual gaps/overlaps, speed, transforms, crop, effects, transitions, opacity, discarded visual audio, overlapping audio, fades, missing streams, and missing binaries.
60:- FFmpeg implements exact track-volume × clip-volume gain, track mute, clip `volume: 0`, supported sequential audio mixing, stream-copy behavior, and explicit audio ownership without renderer-synthesized silence.
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
79:- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
83:- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
84:- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
130:- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
137:- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
139:- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
153:- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
163:- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
166:- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=40 7f7c25d5..8c195bf0 -- tests/fixtures/renderer_packs/raw_command/backend.py tests/fixtures/renderer_packs/raw_command/requests/support.json tests/core/rendering/test_raw_command_fixture.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/core/rendering/test_raw_command_fixture.py b/tests/core/rendering/test_raw_command_fixture.py
index 51de30c6..7e44fd39 100644
--- a/tests/core/rendering/test_raw_command_fixture.py
+++ b/tests/core/rendering/test_raw_command_fixture.py
@@ -240,80 +240,97 @@ def test_fixture_pack_validates_and_inspects_without_importing_backend(
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
     for name in new_modules:
         module = sys.modules.get(name)
         module_file = getattr(module, "__file__", None)
         assert module_file is None or not str(Path(module_file).resolve()).startswith(
             source_str
         ), f"module {name!r} is backed by the fixture pack: {module_file}"
 
 
 # ---------------------------------------------------------------------------
 # Protocol verbs through CommandTransport
 # ---------------------------------------------------------------------------
 
 
 def test_render_verb_via_command_transport(tmp_path: Path) -> None:
     workspace = tmp_path / "workspace"
     transport, result, _ = _run_transport(workspace, PACK_ROOT, verb="render")
 
     _assert_clean_render(result, workspace)
     assert transport.last_logs == {"stdout": "", "stderr": ""}
 
+    # The fixture output must pass STRICT artifact validation against the
+    # request profile (dimensions, FPS, codecs, pixel format, audio).
+    from astrid.core.rendering.artifacts import validate_render_result
+    from astrid.core.rendering.contracts import RenderRequest
+
+    request = json.loads(
+        (PACK_ROOT / "requests" / "render.json").read_text(encoding="utf-8")
+    )
+    parsed_request = RenderRequest.from_dict(request)
+    video_abs = workspace / result.video.path
+    validate_render_result(
+        result,
+        expected_profile=parsed_request.profile,
+        workspace_root=workspace,
+    )
+    assert video_abs.is_file()
+
     # Determinism: a second invocation produces byte-identical media.
     second_workspace = tmp_path / "workspace-2"
     _, second_result, _ = _run_transport(second_workspace, PACK_ROOT, verb="render")
     first_bytes = (workspace / result.video.path).read_bytes()
     second_bytes = (second_workspace / second_result.video.path).read_bytes()
     assert first_bytes == second_bytes
     assert result.video.sha256 == second_result.video.sha256
 
 
 def test_support_verb_via_command_transport(tmp_path: Path) -> None:
     workspace = tmp_path / "workspace"
     _, report, _ = _run_transport(workspace, PACK_ROOT, verb="support", request_name="support.json")
 
     assert isinstance(report, SupportReport)
     assert report.schema_version == 1
     assert report.supported is True
     assert report.reasons == []
     assert report.features == {"media": True, "audio_mode": "rendered"}
     assert report.alternatives == []
     assert report.backend == BACKEND_ID
     assert report.backend_version == "1.0.0"
 
 
 def test_render_and_support_never_create_run_json(tmp_path: Path) -> None:
     _run_transport(tmp_path / "workspace-render", PACK_ROOT, verb="render")
     _run_transport(
         tmp_path / "workspace-support",
         PACK_ROOT,
         verb="support",
         request_name="support.json",
     )
 
     for root in (tmp_path, PACK_ROOT):
         assert list(root.rglob("run.json")) == [], f"run.json found under {root}"
 
 
 # ---------------------------------------------------------------------------
 # Extra pack root and trusted install resolution
 # ---------------------------------------------------------------------------
 
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index 37973595..783fb243 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -251,100 +251,99 @@ def _mdhd(timescale: int, duration: int) -> bytes:
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
-        _box(b"frma", b"sowt") + _box(b"enda", struct.pack(">H", 1)),
+        _box(b"frma", b"sowt")
+        + _box(b"enda", struct.pack(">H", 1))
+        + _box(
+            b"chan",
+            struct.pack(">I", 0)  # version/flags
+            + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)  # layout tag
+            + struct.pack(">I", 0),  # bitmap
+        ),
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
-    # QuickTime channel layout atom so ffprobe reports a concrete
-    # channel_layout (stereo = layout tag 3) instead of None.
-    chan = _box(
-        b"chan",
-        struct.pack(">I", 0)   # version/flags
-        + struct.pack(">I", 3 if AUDIO_CHANNELS == 2 else 1)
-        + struct.pack(">I", 0),  # bitmap
-    )
-    return _box(b"sowt", audio + wave + chan)
+    return _box(b"sowt", audio + wave)
 
 
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
@@ -398,81 +397,107 @@ def _build_mp4(frames: int) -> bytes:
 
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
 
 
-def _support(result_path: Path) -> int:
+def _support(request: dict, result_path: Path) -> int:
+    profile = request.get("profile")
+    if isinstance(profile, dict):
+        # The renderer can only produce its own exact codec set; a request
+        # for a different codec is unsupported (fail closed).
+        if (
+            profile.get("audio_codec") not in (None, AUDIO_CODEC)
+            or profile.get("video_codec") not in (None, VIDEO_CODEC)
+            or profile.get("width") not in (None, WIDTH)
+            or profile.get("height") not in (None, HEIGHT)
+        ):
+            _write_json(
+                result_path,
+                {
+                    "schema_version": 1,
+                    "supported": False,
+                    "reasons": [
+                        f"requested profile {profile.get('audio_codec')}/"
+                        f"{profile.get('video_codec')} is not produced by {BACKEND_ID}"
+                    ],
+                    "features": {"media": False, "audio_mode": "none"},
+                    "alternatives": [],
+                    "backend": BACKEND_ID,
+                    "backend_version": "1.0.0",
+                },
+            )
+            return 0
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
@@ -531,54 +556,54 @@ def _render(request: dict, result_path: Path, request_path: Path) -> int:
 
 
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
-        return _support(result_path)
+        return _support(request, result_path)
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
diff --git a/tests/fixtures/renderer_packs/raw_command/requests/support.json b/tests/fixtures/renderer_packs/raw_command/requests/support.json
index aacbf8a4..bd35d972 100644
--- a/tests/fixtures/renderer_packs/raw_command/requests/support.json
+++ b/tests/fixtures/renderer_packs/raw_command/requests/support.json
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
     "purpose": "T2.2 raw protocol fixture support"
   }
 }

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '1,145p'; rg -n \"termination_grace\" astrid/core/rendering/transport.py tests/core/rendering/test_transport.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
astrid/core/rendering/transport.py:84:        termination_grace: float = _DEFAULT_TERMINATION_GRACE,
astrid/core/rendering/transport.py:89:            isinstance(termination_grace, bool)
astrid/core/rendering/transport.py:90:            or not isinstance(termination_grace, (int, float))
astrid/core/rendering/transport.py:91:            or not math.isfinite(float(termination_grace))
astrid/core/rendering/transport.py:92:            or termination_grace <= 0
astrid/core/rendering/transport.py:94:            raise ValueError("termination_grace must be a positive finite number")
astrid/core/rendering/transport.py:96:        self.termination_grace = float(termination_grace)
astrid/core/rendering/transport.py:207:                process, grace=self.termination_grace
astrid/core/rendering/transport.py:222:                process, grace=self.termination_grace
astrid/core/rendering/transport.py:242:                _terminate_process_group(process, grace=self.termination_grace)
astrid/core/rendering/transport.py:249:        _terminate_leftover_group(process, grace=self.termination_grace)
tests/core/rendering/test_transport.py:51:    selected = transport or CommandTransport(backend, termination_grace=0.15)

codex
Independent review has now reproduced two additional remaining failures: transport still has unguarded drain/reap calls after the new catch, and the `chan` payload is still structurally incomplete. I’m checking the exact binary layout and the full support-profile surface before writing the issue list.
web search: 
web search: https://github.com/FFmpeg/FFmpeg/blob/master/libavformat/movenc.c#L981-L995
web search: 
web search: site:ffmpeg.org/doxygen/8.0 "mov_write_chan_tag" "avio_wb32" ...
web search: 
web search: 
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy,struct,subprocess; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); e=m[\"_sowt_entry\"](); i=e.index(b\"chan\")-4; s=struct.unpack(\">I\",e[i:i+4])[0]; p=e[i+8:i+s]; print({\"chan_box_size\":s,\"payload_len\":len(p),\"words\":[hex(x) for x in struct.unpack(\">III\",p)]}); c=subprocess.run([\"ffprobe\",\"-v\",\"error\",\"-show_entries\",\"stream=index,codec_type,codec_name,channels,channel_layout,sample_rate,width,height,avg_frame_rate,time_base,pix_fmt\",\"-of\",\"json\",\"pipe:0\"],input=m[\"_build_mp4\"](48),capture_output=True); print(c.stdout.decode())'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 487ms:
{'chan_box_size': 20, 'payload_len': 12, 'words': ['0x0', '0x3', '0x0']}
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
            "avg_frame_rate": "24/1",
            "time_base": "1/12288"
        },
        {
            "index": 1,
            "codec_name": "pcm_s16le",
            "codec_type": "audio",
            "sample_rate": "48000",
            "channels": 2,
            "avg_frame_rate": "0/0",
            "time_base": "1/48000"
        }
    ]
}


exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,runpy,tempfile,pathlib; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); base=json.load(open(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\")); fields={\"fps_rational\":[30,1],\"time_base\":[1,30000],\"container\":\"mov\",\"pixel_format\":\"yuv444p\",\"audio_sample_rate\":44100,\"audio_channel_layout\":\"mono\"}; td=tempfile.TemporaryDirectory(); root=pathlib.Path(td.name); [(lambda req,p:(m[\"_support\"](req,p),print(k,json.loads(p.read_text())[\"supported\"])) )({**base,\"profile\":{**base[\"profile\"],k:v}},root/f\"{k}.json\") for k,v in fields.items()]'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 107ms:
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 871, in __init__
    self.name = mkdtemp(suffix, prefix, dir)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 374, in mkdtemp
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
