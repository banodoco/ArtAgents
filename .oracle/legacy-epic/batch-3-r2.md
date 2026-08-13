Reading additional input from stdin...
2026-08-12T12:01:06.961123Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:06.965031Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:06.965046Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff5d8-f77d-7153-b48d-78e9b114f468
--------
user
# Megado Checkpoint — Batch 3 second re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-3.md (8), batch-3-r1.md (6). Second rework committed as
`58473c3a` (prior head 72b70944). Incremental diff at /tmp/batch3-r2.diff.

## How each of your 6 re-review1 issues was addressed (host-implemented)

1. **Launcher not env-authoritative** → `_selects_finalizer` now checks the
   transport-selected backend id FIRST and returns False for any other id; a
   `rendering.remotion` invocation with a finalizer namespace in the request
   can never route to the finalizer.
2. **Remotion support/render inconsistent** → support now forces the FULL
   render profile (time_base 1/90000 + AAC 48k stereo) when comparing the
   request profile, so a visual-only profile fails closed and the actual
   rendered profile is accepted; manifest `audio_ownership` narrowed to
   `[rendered]`.
3. **FFmpeg profile validation misses time_base** → added time_base
   `(1, fps*512)` comparison to `_profile_support_reasons`.
4. **Audio-reactive hard-codes 44.1kHz** → `AudioReactiveColourSpec` gains
   `audio_sample_rate` (default 48000) and `build_mux_command` uses it.
5. **Stream-copy not gated on whole-source compatibility** →
   `_whole_media_optimization` now also requires probed `video_codec == h264`
   and `pixel_format == yuv420p`; `build_render_command` requires
   `report.supported` before consuming `stream_copy`.
6. **Legacy facade TOCTOU** → new `build_render_command_from_data` builds
   from the EXACT mappings the facade validated with strict support (no
   reload); the facade path uses it.

## Evidence

- Incremental diff: /tmp/batch3-r2.diff (10 files)
- Host-verified: 106 combined backend/finalizer/locking tests pass; full
  consolidated acceptance = 835 passed, 1 failed (SAME pre-existing
  env-dependent model-trends fixture failure), 2 skipped. Remotion typecheck
  passes; real Remotion + FFmpeg smokes pass.

## Verdict

Binary: `PASS` or a list of issues. If PASS, say exactly `PASS` so Batch 4
may begin.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Megado checkpoint workflow and the repo’s context-minimizing review posture. I’ll inspect the incremental diff, delegate independent adversarial checks, and return only the required binary verdict or concrete issues.
exec
/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/megado/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

2026-08-12T12:01:41.732202Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:41.732822Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:41.732863Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:48.210190Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:48.210362Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:48.210383Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:53.622267Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:53.622519Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T12:01:53.622554Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc 'git status --short && git rev-parse HEAD && git diff --stat 72b70944..58473c3a && git diff --name-only 72b70944..58473c3a' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg --files .oracle | sort | rg 'batch-3|tasklist|status|plan' && sed -n '1,240p' .oracle/checkins/batch-3.md && sed -n '1,240p' .oracle/checkins/batch-3-r1.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "wc -l /tmp/batch3-r2.diff && sed -n '1,240p' /tmp/batch3-r2.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 186ms:
.oracle/briefs/05-hybrid-planner-canvas.md
.oracle/briefs/batch-3-t3.1.md
.oracle/briefs/batch-3-t3.2.md
.oracle/briefs/batch-3-t3.3.md
.oracle/briefs/batch-3-t3.4.md
.oracle/briefs/batch-3-t3.5.md
.oracle/briefs/batch-3-t3.6.md
.oracle/checkins/batch-3-r1.md
.oracle/checkins/batch-3-r2.md
.oracle/checkins/batch-3.md
.oracle/findings/05-hybrid-planner-canvas.meta.json
.oracle/findings/05-hybrid-planner-canvas.txt
.oracle/plan-v1.txt
.oracle/plan.md
.oracle/tasklist.md
Reading additional input from stdin...
2026-08-12T10:26:50.522701Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T10:26:50.523434Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T10:26:50.523446Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff582-ad96-7ad1-9a73-9e653929f24e
--------
user
# Megado Checkpoint — Batch 3 review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

You are the ORACLE. Batch 3 ("Built-in renderer and finalizer extraction")
is complete and committed as C3 (0c2733ed). Batch 2 passed after 6 review
rounds (PASS in `.oracle/checkins/batch-2-r6.md`); tag `C3-batch2-done` =
3df2b858. The Batch 3 diff is at /tmp/batch3.diff (C3-batch2-done..C3, 40
files, +13074/-2089).

## Batch 3 tasks (from .oracle/tasklist.md)

- T3.1 — Extract `rendering.remotion` backend (raw-command adapter,
  renderer.yaml, moved Remotion helpers) [HARD]
- T3.2 — Remotion outer lock (non-recursive, spans generation+render+
  gen-types) [HARD]
- T3.3 — Extract FFmpeg backend + pure builders (+ audio_reactive_colour)
  [HARD]
- T3.4 — Strict FFmpeg support (fail closed) + exact audio semantics
  [HARD]
- T3.5 — Extract `rendering.ffmpeg-finalizer` (probe, normalize, audio
  modes, attachments, cleanup) [HARD]
- T3.6 — Register built-ins, real FFmpeg + Remotion smokes, typecheck
  [HARD]

## Host fixes during verification (beyond agent work)

- Finalizer fragment key `finalizer` → `finalizer_kind` (collided with a
  core-owned provenance key; caught by test).
- Remotion backend: declared profile time_base forced to 1/90000 (Remotion's
  actual MP4 timescale vs the input timeline's); pixel-format validation
  treats deprecated full-range `yuvj420p` ≡ `yuv420p`; Remotion always muxes
  an audio track so ownership is `rendered` with AAC profile fields forced.
  These were REAL defects the real-render smoke exposed.

## Acceptance criteria (tasklist Batch 3)

- rendering.remotion/ffmpeg/ffmpeg-finalizer statically registered via
  pack.yaml + manifests.
- Remotion preserves TimelineComposition, merged themes, props, registry
  state/hashes, lineage, staging, env, cleanup, output validation.
- One non-recursive cross-process lock spans registry reads/writes,
  theme-pointer, full render, gen-types.
- Strict FFmpeg support fails closed (unknown kinds, invalid bounds, gaps/
  overlaps, speed, transforms, crop, effects, transitions, opacity,
  discarded audio, overlapping audio, fades, missing streams/binaries).
- FFmpeg exact track×clip gain, track mute, clip volume 0, sequential
  mixing, stream-copy, explicit audio ownership (no synthesized silence).
- Finalizer probes every segment, stream-copies compatible, normalizes
  otherwise (rational FPS, codecs, pixel format, audio), records
  normalization, no hard-coded fps=30.
- Compatibility tests, Remotion typecheck, real FFmpeg render, real Remotion
  fixture render pass.

## Evidence

- Diff: /tmp/batch3.diff
- Host-verified: full consolidated acceptance = 833 passed, 1 failed (the
  remaining pre-existing env-dependent failure: missing developer-local
  `model-trends` effect fixture), 2 skipped.
- `cd remotion && npm run typecheck` → PASS (node_modules was absent; host
  ran `npm install` then typecheck — exit 0).
- Real Remotion render through the registered backend → PASS (exposed and
  fixed the time_base/audio-ownership defects above).
- No hard-coded fps=30 remains in the finalizer (grep-verified).

## Verdict

Binary: `PASS` or a list of issues. Verify the extraction preserved behavior
(facade still routes remotion/ffmpeg/hybrid identically), the lock is truly
non-recursive and complete, strict FFmpeg support covers every listed
rejection, the finalizer normalizes without hard-coded assumptions, and the
Remotion ownership/profile corrections are sound (not hacks). If PASS, say
exactly `PASS` so Batch 4 may begin.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Megado review protocol and the repository’s context-mining guidance. I’ll inspect the checkpoint evidence read-only, split the high-risk areas into independent review tracks, and return only `PASS` if every criterion survives scrutiny.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '241,520p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
Reading additional input from stdin...
2026-08-12T11:34:58.586243Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T11:34:58.587926Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T11:34:58.587940Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff5c1-03a5-70c1-a5d6-1e6b0cdc44cb
--------
user
# Megado Checkpoint — Batch 3 re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdict: `.oracle/checkins/batch-3.md` (8 issues). Batch 3 rework
committed as `72b70944` (prior head C3 = 0c2733ed). Incremental diff at
/tmp/batch3-r1.diff.

## How each of your 8 issues was addressed (host-implemented)

1. **Launcher cannot identify selected backend with `backend_config={}`** →
   CommandTransport now sets `ASTRID_RENDER_BACKEND=<qualified-id>` in the
   child env; the launcher routes by that first, then by the request's
   backend_config namespace, NEVER by timeline shape (which could route
   Remotion→FFmpeg). The legacy media-only auto-route stays inside the
   Remotion backend's own support.
2. **Remotion support contradicts render** → support now validates against
   the same contract render implements: audio always `rendered`, time_base
   always 1/90000, AAC profile fields forced. Support features report
   `audio_ownership: rendered`; the visual-only-NONE contradiction is gone.
3. **renderer.yaml omits ffprobe** → added to required_binaries (node, npx,
   ffprobe); static-registration tests updated.
4. **FFmpeg support ignores requested profile beyond audio presence** →
   new `_profile_support_reasons` compares EVERY field (dims, fps,
   container, codecs, pixel format, sample rate, layout) fail-closed.
   `command.py` sample rate is now threaded from the canonical profile
   (48000 default), not hard-coded 44100.
5. **Stream-copy ignores probe evidence** → `RenderCommandInputs` gains
   `stream_copy_allowed`; `build_render_command` derives it from strict
   support's probe evidence; the pure builder copies only when the probe
   confirmed whole-source compatibility. Tests updated to the strict
   contract (placeholder source → libx264).
6. **Legacy facade routing discards embedded visual audio** →
   `_render_ffmpeg_media_to_path` now runs strict support and refuses
   unsupported timelines (e.g. visual clip with nonzero volume) instead of
   silently emitting `-an`.
7. **Finalizer doesn't normalize audio presence** → verified the finalizer
   already synthesizes anullsrc for video-only segments in a rendered
   target; the existing
   `test_rendered_mode_normalizes_visual_only_segment_audio_presence`
   covers it (passes).
8. **Finalizer profile anchoring codec-unsafe** → verified
   `_PROFILE_ANCHOR_BLOCKERS` excludes codec-differing segments; the HEVC→
   H.264 mismatch test now asserts HEVC Main@120 profile/level never reach
   the H.264 encoder (strengthened).

Also fixed: the flaky concurrent-lock test waits (5s→60s; spawn + real lock
wrapper exceed 5s under load).

## Evidence

- Incremental diff: /tmp/batch3-r1.diff (16 files)
- Host-verified: full consolidated acceptance = 835 passed, 1 failed (the
  remaining pre-existing env-dependent failure: missing developer-local
  `model-trends` effect fixture), 2 skipped. Remotion typecheck passes.
  Real Remotion + FFmpeg smokes pass.

## Verdict

Binary: `PASS` or a list of issues. Verify the eight closures — especially
the launcher routing (must never shape-guess), the Remotion support/render
contract alignment, the probe-gated stream-copy, and the legacy-path strict
support. If PASS, say exactly `PASS` so Batch 4 may begin.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Megado checkpoint guidance and Astrid’s repository workflow, with the context-minimizing/subagent discipline required by this worktree. I’ll independently verify the incremental diff against all eight prior findings, then run focused read-only tests where feasible.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 68ms:
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
    1025 total
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


 succeeded in 284ms:
   21199 /tmp/batch3-r2.diff
diff --git a/.oracle/checkins/batch-3-r1.md b/.oracle/checkins/batch-3-r1.md
new file mode 100644
index 00000000..89ed9db8
--- /dev/null
+++ b/.oracle/checkins/batch-3-r1.md
@@ -0,0 +1,20991 @@
+Reading additional input from stdin...
+2026-08-12T11:34:58.586243Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T11:34:58.587926Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T11:34:58.587940Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff5c1-03a5-70c1-a5d6-1e6b0cdc44cb
+--------
+user
+# Megado Checkpoint — Batch 3 re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdict: `.oracle/checkins/batch-3.md` (8 issues). Batch 3 rework
+committed as `72b70944` (prior head C3 = 0c2733ed). Incremental diff at
+/tmp/batch3-r1.diff.
+
+## How each of your 8 issues was addressed (host-implemented)
+
+1. **Launcher cannot identify selected backend with `backend_config={}`** →
+   CommandTransport now sets `ASTRID_RENDER_BACKEND=<qualified-id>` in the
+   child env; the launcher routes by that first, then by the request's
+   backend_config namespace, NEVER by timeline shape (which could route
+   Remotion→FFmpeg). The legacy media-only auto-route stays inside the
+   Remotion backend's own support.
+2. **Remotion support contradicts render** → support now validates against
+   the same contract render implements: audio always `rendered`, time_base
+   always 1/90000, AAC profile fields forced. Support features report
+   `audio_ownership: rendered`; the visual-only-NONE contradiction is gone.
+3. **renderer.yaml omits ffprobe** → added to required_binaries (node, npx,
+   ffprobe); static-registration tests updated.
+4. **FFmpeg support ignores requested profile beyond audio presence** →
+   new `_profile_support_reasons` compares EVERY field (dims, fps,
+   container, codecs, pixel format, sample rate, layout) fail-closed.
+   `command.py` sample rate is now threaded from the canonical profile
+   (48000 default), not hard-coded 44100.
+5. **Stream-copy ignores probe evidence** → `RenderCommandInputs` gains
+   `stream_copy_allowed`; `build_render_command` derives it from strict
+   support's probe evidence; the pure builder copies only when the probe
+   confirmed whole-source compatibility. Tests updated to the strict
+   contract (placeholder source → libx264).
+6. **Legacy facade routing discards embedded visual audio** →
+   `_render_ffmpeg_media_to_path` now runs strict support and refuses
+   unsupported timelines (e.g. visual clip with nonzero volume) instead of
+   silently emitting `-an`.
+7. **Finalizer doesn't normalize audio presence** → verified the finalizer
+   already synthesizes anullsrc for video-only segments in a rendered
+   target; the existing
+   `test_rendered_mode_normalizes_visual_only_segment_audio_presence`
+   covers it (passes).
+8. **Finalizer profile anchoring codec-unsafe** → verified
+   `_PROFILE_ANCHOR_BLOCKERS` excludes codec-differing segments; the HEVC→
+   H.264 mismatch test now asserts HEVC Main@120 profile/level never reach
+   the H.264 encoder (strengthened).
+
+Also fixed: the flaky concurrent-lock test waits (5s→60s; spawn + real lock
+wrapper exceed 5s under load).
+
+## Evidence
+
+- Incremental diff: /tmp/batch3-r1.diff (16 files)
+- Host-verified: full consolidated acceptance = 835 passed, 1 failed (the
+  remaining pre-existing env-dependent failure: missing developer-local
+  `model-trends` effect fixture), 2 skipped. Remotion typecheck passes.
+  Real Remotion + FFmpeg smokes pass.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Verify the eight closures — especially
+the launcher routing (must never shape-guess), the Remotion support/render
+contract alignment, the probe-gated stream-copy, and the legacy-path strict
+support. If PASS, say exactly `PASS` so Batch 4 may begin.
+warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
+codex
+I’m using the Megado checkpoint guidance and Astrid’s repository workflow, with the context-minimizing/subagent discipline required by this worktree. I’ll independently verify the incremental diff against all eight prior findings, then run focused read-only tests where feasible.
+exec
+/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 68ms:
+     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
+     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
+      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
+    1025 total
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

 succeeded in 621ms:
?? .oracle/checkins/batch-3-r2.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
58473c3ae3390738771898127c73c09230a3cfd8
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-3-r1.md                     | 20991 +++++++++++++++++++
 .../backends/ffmpeg/audio_reactive_colour.py       |     3 +-
 astrid/packs/rendering/backends/ffmpeg/command.py  |    33 +-
 astrid/packs/rendering/backends/ffmpeg/run.py      |     6 +-
 astrid/packs/rendering/backends/ffmpeg/support.py  |     3 +
 .../rendering/backends/remotion/renderer.yaml      |     1 -
 astrid/packs/rendering/backends/remotion/run.py    |     8 +-
 astrid/packs/rendering/run.py                      |     8 +-
 tests/packs/rendering/test_ffmpeg_backend.py       |     1 +
 tests/packs/rendering/test_ffmpeg_support.py       |     1 +
 10 files changed, 21047 insertions(+), 8 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-3-r1.md
astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py
astrid/packs/rendering/backends/ffmpeg/command.py
astrid/packs/rendering/backends/ffmpeg/run.py
astrid/packs/rendering/backends/ffmpeg/support.py
astrid/packs/rendering/backends/remotion/renderer.yaml
astrid/packs/rendering/backends/remotion/run.py
astrid/packs/rendering/run.py
tests/packs/rendering/test_ffmpeg_backend.py
tests/packs/rendering/test_ffmpeg_support.py

exec
/bin/zsh -lc 'tail -n 180 .oracle/checkins/batch-3-r1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc 'tail -n 220 .oracle/checkins/batch-3.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc 'git diff --find-renames --find-copies 72b70944..58473c3a -- astrid tests' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n '"'^## Batch 3|''^### T3'"\\.|"'^### Acceptance|''^## Batch 4'"' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
50:## Batch 3 — Built-in renderer and finalizer extraction
73:## Batch 4 — Generic routing, provenance, and hybrid planning

 succeeded in 118ms:
diff --git a/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py b/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py
index 967731fa..e0dfdedc 100644
--- a/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py
+++ b/astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py
@@ -53,6 +53,7 @@ class AudioReactiveColourSpec:
     audio_from: float
     audio_to: float
     audio_volume: float
+    audio_sample_rate: int = 48000
 
     @property
     def duration_seconds(self) -> float:
@@ -348,7 +349,7 @@ def build_mux_command(
     audio_filter = (
         f"atrim=start={spec.audio_from:.9f}:end={spec.audio_to:.9f},"
         "asetpts=PTS-STARTPTS,"
-        "aformat=sample_rates=44100:channel_layouts=stereo,"
+        f"aformat=sample_rates={spec.audio_sample_rate}:channel_layouts=stereo,"
         f"volume={spec.audio_volume:.9f}"
     )
     return [
diff --git a/astrid/packs/rendering/backends/ffmpeg/command.py b/astrid/packs/rendering/backends/ffmpeg/command.py
index bbd18d97..ef999e4c 100644
--- a/astrid/packs/rendering/backends/ffmpeg/command.py
+++ b/astrid/packs/rendering/backends/ffmpeg/command.py
@@ -404,7 +404,6 @@ def _asset_input_argv(inputs: RenderCommandInputs) -> list[str]:
 
 def build_render_command_from_inputs(inputs: RenderCommandInputs) -> list[str]:
     """Return FFmpeg argv for already-resolved, strictly supported inputs."""
-
     filters, copy_video_input = build_filter_graph(inputs)
     has_audio = _has_audio_clips(inputs.timeline_data)
     return [
@@ -462,13 +461,43 @@ def build_render_command(
             inputs.timeline_data,
             inputs.registry,
         )
-        stream_copy_allowed = bool(report.features.get("stream_copy"))
+        stream_copy_allowed = (
+            report.supported and bool(report.features.get("stream_copy"))
+        )
     except Exception:
         stream_copy_allowed = False
     inputs = replace(inputs, stream_copy_allowed=stream_copy_allowed)
     return build_render_command_from_inputs(inputs)
 
 
+def build_render_command_from_data(
+    timeline_path: Path,
+    assets_path: Path,
+    output_path: Path,
+    timeline_data: Mapping[str, Any],
+    registry: Mapping[str, Any],
+    *,
+    audio_sample_rate: int = 48000,
+    stream_copy_allowed: bool = False,
+) -> list[str]:
+    """Build FFmpeg argv from ALREADY-LOADED, strictly supported data.
+
+    Used by the legacy facade path so the exact mappings it validated with
+    strict support are the ones rendered — no reload, no TOCTOU window.
+    """
+    return build_render_command_from_inputs(
+        RenderCommandInputs(
+            timeline_path=Path(timeline_path).resolve(),
+            assets_path=Path(assets_path).resolve(),
+            output_path=Path(output_path).resolve(),
+            timeline_data=dict(timeline_data),
+            registry=dict(registry),
+            audio_sample_rate=audio_sample_rate,
+            stream_copy_allowed=stream_copy_allowed,
+        )
+    )
+
+
 def build_render_command_for_paths(
     timeline_path: Path,
     assets_path: Path,
diff --git a/astrid/packs/rendering/backends/ffmpeg/run.py b/astrid/packs/rendering/backends/ffmpeg/run.py
index 6e47d1e8..74d590c4 100644
--- a/astrid/packs/rendering/backends/ffmpeg/run.py
+++ b/astrid/packs/rendering/backends/ffmpeg/run.py
@@ -47,6 +47,7 @@ from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
 from astrid.packs.rendering.backends.ffmpeg.command import (
     build_render_command,
     build_render_command_for_paths,
+    build_render_command_from_data,
     validate_ffmpeg_media_timeline,
 )
 from astrid.packs.rendering.backends.ffmpeg.support import (
@@ -111,10 +112,13 @@ def _render_ffmpeg_media_to_path(
         )
 
     output = Path(out_path)
-    command_argv = build_render_command_for_paths(
+    command_argv = build_render_command_from_data(
         Path(timeline_path),
         Path(assets_path),
         output,
+        timeline_data,
+        assets_data,
+        stream_copy_allowed=bool(report.features.get("stream_copy")),
     )
     output.parent.mkdir(parents=True, exist_ok=True)
     (subprocess.run if runner is None else runner)(command_argv, check=True)
diff --git a/astrid/packs/rendering/backends/ffmpeg/support.py b/astrid/packs/rendering/backends/ffmpeg/support.py
index 39f3db56..3c372c94 100644
--- a/astrid/packs/rendering/backends/ffmpeg/support.py
+++ b/astrid/packs/rendering/backends/ffmpeg/support.py
@@ -489,6 +489,8 @@ def _whole_media_optimization(
         and media_probe.height == height
         and probed_fps is not None
         and abs(probed_fps - fps) < 1e-6
+        and (media_probe.video_codec or "") == "h264"
+        and (media_probe.pixel_format or "") == "yuv420p"
     )
 
 
@@ -510,6 +512,7 @@ def _profile_support_reasons(
         ("width", profile.width, width),
         ("height", profile.height, height),
         ("fps", _fps_int(profile.fps_rational), fps),
+        ("time_base", profile.time_base, (1, fps * 512)),
         ("container", profile.container, "mp4"),
         ("video_codec", profile.video_codec, "h264"),
         ("pixel_format", profile.pixel_format, "yuv420p"),
diff --git a/astrid/packs/rendering/backends/remotion/renderer.yaml b/astrid/packs/rendering/backends/remotion/renderer.yaml
index 598f7f40..edf879e5 100644
--- a/astrid/packs/rendering/backends/remotion/renderer.yaml
+++ b/astrid/packs/rendering/backends/remotion/renderer.yaml
@@ -30,7 +30,6 @@ capabilities:
     - video/mp4
   audio_ownership:
     - rendered
-    - none
 required_permissions:
   - project_files
   - subprocess
diff --git a/astrid/packs/rendering/backends/remotion/run.py b/astrid/packs/rendering/backends/remotion/run.py
index 3c76d745..2daded5b 100644
--- a/astrid/packs/rendering/backends/remotion/run.py
+++ b/astrid/packs/rendering/backends/remotion/run.py
@@ -1014,7 +1014,13 @@ def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
                     f"Remotion's always-rendered audio output"
                 )
             if request.profile is not None:
-                render_profile = replace(canonical, time_base=(1, 90000))
+                render_profile = replace(
+                    canonical,
+                    time_base=(1, 90000),
+                    audio_codec=canonical.audio_codec or "aac",
+                    audio_sample_rate=canonical.audio_sample_rate or 48000,
+                    audio_channel_layout=canonical.audio_channel_layout or "stereo",
+                )
                 mismatches = _profile_mismatches(request.profile, render_profile)
                 if mismatches:
                     reasons.append(
diff --git a/astrid/packs/rendering/run.py b/astrid/packs/rendering/run.py
index a97d5bf8..f0009b1f 100644
--- a/astrid/packs/rendering/run.py
+++ b/astrid/packs/rendering/run.py
@@ -30,10 +30,14 @@ def _request_path(argv: Sequence[str]) -> Path | None:
 def _selects_finalizer(argv: Sequence[str]) -> bool:
     """Route finalize and explicitly-namespaced support operations."""
 
+    selected = _transport_selected_backend()
+    if selected is not None:
+        # The transport-selected backend id is authoritative over request
+        # content: a remotion invocation must never route to the finalizer
+        # merely because the request carries a finalizer namespace.
+        return selected == "rendering.ffmpeg-finalizer"
     if argv and argv[0] == "finalize":
         return True
-    if _transport_selected_backend() == "rendering.ffmpeg-finalizer":
-        return True
     if not argv or argv[0] != "support":
         return False
     request_path = _request_path(argv)
diff --git a/tests/packs/rendering/test_ffmpeg_backend.py b/tests/packs/rendering/test_ffmpeg_backend.py
index 1c5c25d5..b2ded32d 100644
--- a/tests/packs/rendering/test_ffmpeg_backend.py
+++ b/tests/packs/rendering/test_ffmpeg_backend.py
@@ -186,6 +186,7 @@ def test_support_is_strict_while_legacy_facade_eligibility_is_preserved(
         height=1080,
         fps=30,
         video_codec="h264",
+        pixel_format="yuv420p",
         audio_codec="aac",
         video_stream_present=True,
         audio_stream_present=True,
diff --git a/tests/packs/rendering/test_ffmpeg_support.py b/tests/packs/rendering/test_ffmpeg_support.py
index 3f575b3c..68707f58 100644
--- a/tests/packs/rendering/test_ffmpeg_support.py
+++ b/tests/packs/rendering/test_ffmpeg_support.py
@@ -102,6 +102,7 @@ def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
         fps=30,
         resolution="640x360",
         video_codec="h264",
+        pixel_format="yuv420p",
         audio_codec="aac" if audio else None,
         video_stream_present=True,
         audio_stream_present=audio,

codex
The six targeted patches are small, so I’m now tracing their call sites and invariants rather than relying on the stated tests. The main risks are “validated data differs from rendered data” and optimization flags escaping strict support.
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/run.py | sed -n '1,190p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 6ms:
     1	#!/usr/bin/env python3
     2	"""Pack-root launcher for rendering raw-command adapters.
     3	
     4	Rendering protocol commands execute with their owning pack as the working
     5	directory.  Built-in manifests intentionally keep the portable
     6	``[python3, run.py]`` command, so this launcher bridges that lifecycle to the
     7	implementation stored beside each manifest.
     8	"""
     9	
    10	from __future__ import annotations
    11	
    12	import json
    13	import sys
    14	from collections.abc import Mapping, Sequence
    15	from pathlib import Path
    16	
    17	
    18	_CHECKOUT_ROOT = Path(__file__).resolve().parents[3]
    19	if str(_CHECKOUT_ROOT) not in sys.path:
    20	    sys.path.insert(0, str(_CHECKOUT_ROOT))
    21	
    22	def _request_path(argv: Sequence[str]) -> Path | None:
    23	    try:
    24	        index = argv.index("--request")
    25	        return Path(argv[index + 1])
    26	    except (ValueError, IndexError):
    27	        return None
    28	
    29	
    30	def _selects_finalizer(argv: Sequence[str]) -> bool:
    31	    """Route finalize and explicitly-namespaced support operations."""
    32	
    33	    selected = _transport_selected_backend()
    34	    if selected is not None:
    35	        # The transport-selected backend id is authoritative over request
    36	        # content: a remotion invocation must never route to the finalizer
    37	        # merely because the request carries a finalizer namespace.
    38	        return selected == "rendering.ffmpeg-finalizer"
    39	    if argv and argv[0] == "finalize":
    40	        return True
    41	    if not argv or argv[0] != "support":
    42	        return False
    43	    request_path = _request_path(argv)
    44	    if request_path is None:
    45	        return False
    46	    try:
    47	        payload = json.loads(request_path.read_text(encoding="utf-8"))
    48	    except (OSError, json.JSONDecodeError):
    49	        return False
    50	    if not isinstance(payload, Mapping):
    51	        return False
    52	    backend_config = payload.get("backend_config")
    53	    return isinstance(backend_config, Mapping) and (
    54	        "rendering.ffmpeg-finalizer" in backend_config
    55	    )
    56	
    57	
    58	def _transport_selected_backend() -> str | None:
    59	    """The transport sets ASTRID_RENDER_BACKEND to the qualified backend id
    60	    it selected; this is authoritative over any request content."""
    61	    value = __import__("os").environ.get("ASTRID_RENDER_BACKEND")
    62	    if isinstance(value, str) and value:
    63	        return value
    64	    return None
    65	
    66	
    67	def _selects_ffmpeg(argv: Sequence[str]) -> bool:
    68	    """Select FFmpeg from the transport-selected backend id or the request's
    69	    backend-config namespace.
    70	
    71	    The launcher never guesses from timeline shape: a shape guess can route a
    72	    Remotion request to FFmpeg or vice versa.  The legacy media-only
    73	    auto-route lives inside the Remotion backend's own support logic.
    74	    """
    75	
    76	    selected = _transport_selected_backend()
    77	    if selected is not None:
    78	        return selected == "rendering.ffmpeg"
    79	    request_path = _request_path(argv)
    80	    if request_path is None:
    81	        return False
    82	    try:
    83	        payload = json.loads(request_path.read_text(encoding="utf-8"))
    84	    except (OSError, json.JSONDecodeError):
    85	        return False
    86	    if not isinstance(payload, Mapping):
    87	        return False
    88	    backend_config = payload.get("backend_config")
    89	    if not isinstance(backend_config, Mapping):
    90	        return False
    91	    if "rendering.ffmpeg" in backend_config:
    92	        return True
    93	    return False
    94	
    95	
    96	def main(argv: Sequence[str] | None = None) -> int:
    97	    args = list(sys.argv[1:] if argv is None else argv)
    98	    if _selects_finalizer(args):
    99	        from astrid.packs.rendering.finalizers.ffmpeg.run import (
   100	            main as backend_main,
   101	        )
   102	    elif _selects_ffmpeg(args):
   103	        from astrid.packs.rendering.backends.ffmpeg.run import main as backend_main
   104	    else:
   105	        from astrid.packs.rendering.backends.remotion.run import main as backend_main
   106	
   107	    return backend_main(args)
   108	
   109	
   110	if __name__ == "__main__":
   111	    raise SystemExit(main())

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '930,1195p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   930	    try:
   931	        settings = _settings_from_request(request, workspace)
   932	    except (TypeError, ValueError) as exc:
   933	        settings = _RenderSettings(
   934	            project_dir=REPO_ROOT / "remotion",
   935	            composition_id=DEFAULT_COMPOSITION_ID,
   936	            theme_path=None,
   937	            min_free_gb=None,
   938	        )
   939	        reasons.append(str(exc))
   940	
   941	    if request.window is not None:
   942	        reasons.append(
   943	            "rendering.remotion accepts complete timelines, not native frame windows"
   944	        )
   945	
   946	    timeline_path = _input_path(request.timeline_path, workspace)
   947	    assets_path = (
   948	        _input_path(request.assets_registry_path, workspace)
   949	        if request.assets_registry_path is not None
   950	        else None
   951	    )
   952	    timeline_data: dict[str, Any] | None = None
   953	    assets_data: dict[str, Any] | None = None
   954	    try:
   955	        timeline_data = _serialize_timeline(timeline_path)
   956	    except Exception as exc:
   957	        reasons.append(f"timeline is not renderable: {exc}")
   958	    try:
   959	        assets_data = _load_registry_mapping(assets_path)
   960	    except Exception as exc:
   961	        reasons.append(f"assets registry is not renderable: {exc}")
   962	
   963	    if timeline_data is not None and assets_data is not None:
   964	        registered_assets = assets_data.get("assets", {})
   965	        missing_asset_ids = sorted(
   966	            {
   967	                str(clip.get("asset"))
   968	                for clip in timeline_data.get("clips", [])
   969	                if isinstance(clip, dict)
   970	                and isinstance(clip.get("asset"), str)
   971	                and clip.get("asset") not in registered_assets
   972	            }
   973	        )
   974	        if missing_asset_ids:
   975	            reasons.append(
   976	                "timeline references missing asset ids: " + ", ".join(missing_asset_ids)
   977	            )
   978	        dynamic_clip_types = sorted(
   979	            {
   980	                str(clip.get("clipType"))
   981	                for clip in timeline_data.get("clips", [])
   982	                if isinstance(clip, dict)
   983	                and clip.get("clipType", "media") != "media"
   984	            }
   985	        )
   986	        if dynamic_clip_types:
   987	            try:
   988	                effects, aliases = _effect_registry_for_assets(settings.theme_path)
   989	            except Exception as exc:
   990	                reasons.append(f"Remotion element registry cannot be resolved: {exc}")
   991	            else:
   992	                unknown_clip_types = [
   993	                    clip_type
   994	                    for clip_type in dynamic_clip_types
   995	                    if clip_type not in effects and clip_type not in aliases
   996	                ]
   997	                if unknown_clip_types:
   998	                    reasons.append(
   999	                        "timeline uses unregistered Remotion clip types: "
  1000	                        + ", ".join(unknown_clip_types)
  1001	                    )
  1002	        try:
  1003	            canonical = _canonical_profile(timeline_path, assets_data, settings)
  1004	        except Exception as exc:
  1005	            reasons.append(f"canonical Remotion profile cannot be resolved: {exc}")
  1006	        else:
  1007	            # Remotion ALWAYS muxes an audio track (silent when the timeline
  1008	            # has none) and always muxes at the 90 kHz timescale; support must
  1009	            # describe the same contract render() implements.
  1010	            features["audio_ownership"] = AudioOwnership.RENDERED.value
  1011	            if request.audio is not None and request.audio is not AudioOwnership.RENDERED:
  1012	                reasons.append(
  1013	                    f"audio={request.audio.value!r} is incompatible with "
  1014	                    f"Remotion's always-rendered audio output"
  1015	                )
  1016	            if request.profile is not None:
  1017	                render_profile = replace(
  1018	                    canonical,
  1019	                    time_base=(1, 90000),
  1020	                    audio_codec=canonical.audio_codec or "aac",
  1021	                    audio_sample_rate=canonical.audio_sample_rate or 48000,
  1022	                    audio_channel_layout=canonical.audio_channel_layout or "stereo",
  1023	                )
  1024	                mismatches = _profile_mismatches(request.profile, render_profile)
  1025	                if mismatches:
  1026	                    reasons.append(
  1027	                        "requested profile is not produced by Remotion: "
  1028	                        + "; ".join(mismatches)
  1029	                    )
  1030	
  1031	    try:
  1032	        _validate_project_dir(settings.project_dir)
  1033	    except (FileNotFoundError, OSError) as exc:
  1034	        reasons.append(str(exc))
  1035	    for binary in ("node", "npx"):
  1036	        if shutil.which(binary) is None:
  1037	            reasons.append(f"required binary is unavailable: {binary}")
  1038	
  1039	    return SupportReport(
  1040	        schema_version=SCHEMA_VERSION,
  1041	        supported=not reasons,
  1042	        reasons=reasons,
  1043	        features=features,
  1044	        alternatives=[],
  1045	        backend=BACKEND_ID,
  1046	        backend_version=BACKEND_VERSION,
  1047	    )
  1048	
  1049	
  1050	def _duration_frames(video_path: Path, profile: RenderProfile) -> int:
  1051	    probe = ffprobe_metadata_strict(video_path)
  1052	    if probe.duration_rational is not None:
  1053	        duration = Fraction(*probe.duration_rational)
  1054	    elif probe.duration_seconds is not None:
  1055	        duration = Fraction(str(probe.duration_seconds))
  1056	    else:
  1057	        raise RuntimeError("ffprobe did not report a video duration")
  1058	    frames = duration * Fraction(*profile.fps_rational)
  1059	    return max(1, int(frames + Fraction(1, 2)))
  1060	
  1061	
  1062	def _protocol_render(request: RenderRequest, *, workspace: Path) -> RenderResult:
  1063	    report = support(request, workspace=workspace)
  1064	    if not report.supported:
  1065	        raise_unsupported_error(
  1066	            backend=BACKEND_ID,
  1067	            message="Remotion does not support this render request",
  1068	            recovery_command="resolve the reported support reasons and retry",
  1069	            details={"reasons": report.reasons, "features": report.features},
  1070	        )
  1071	
  1072	    settings = _settings_from_request(request, workspace)
  1073	    timeline_path = _input_path(request.timeline_path, workspace)
  1074	    requested_assets_path = (
  1075	        _input_path(request.assets_registry_path, workspace)
  1076	        if request.assets_registry_path is not None
  1077	        else None
  1078	    )
  1079	    outputs_dir = workspace / "outputs"
  1080	    outputs_dir.mkdir(parents=True, exist_ok=True)
  1081	    output_path = outputs_dir / request.output_name
  1082	
  1083	    with ExitStack() as lifecycle:
  1084	        if requested_assets_path is None:
  1085	            empty_assets_tmp = lifecycle.enter_context(
  1086	                TemporaryDirectory(prefix=".remotion-empty-assets-", dir=str(workspace))
  1087	            )
  1088	            assets_path = Path(empty_assets_tmp) / "assets.json"
  1089	            timeline.save_registry({"assets": {}}, assets_path)
  1090	        else:
  1091	            assets_path = requested_assets_path
  1092	        assets_data = _load_registry_mapping(assets_path)
  1093	        canonical = _canonical_profile(timeline_path, assets_data, settings)
  1094	        declared_profile = request.profile or canonical
  1095	        # Remotion always muxes MP4 at the 90 kHz timescale regardless of the
  1096	        # input timeline's time base; the declared profile must match what the
  1097	        # renderer actually produces or strict validation rejects the output.
  1098	        declared_profile = replace(declared_profile, time_base=(1, 90000))
  1099	        # Remotion always muxes an audio track into its MP4 (silent when the
  1100	        # timeline has none), so ownership is effectively 'rendered' and the
  1101	        # declared profile must carry the AAC audio fields it always emits.
  1102	        ownership = AudioOwnership.RENDERED
  1103	        declared_profile = replace(
  1104	            declared_profile,
  1105	            audio_codec=declared_profile.audio_codec or "aac",
  1106	            audio_sample_rate=declared_profile.audio_sample_rate or 48000,
  1107	            audio_channel_layout=declared_profile.audio_channel_layout or "stereo",
  1108	        )
  1109	        private_tmp = lifecycle.enter_context(
  1110	            TemporaryDirectory(
  1111	                prefix=f".{request.output_name}.remotion-",
  1112	                dir=str(outputs_dir),
  1113	            )
  1114	        )
  1115	        staged_video = Path(private_tmp) / request.output_name
  1116	        details = _execute_remotion(
  1117	            timeline_path,
  1118	            assets_path,
  1119	            staged_video,
  1120	            provenance_out_path=output_path,
  1121	            project_dir=settings.project_dir,
  1122	            composition_id=settings.composition_id,
  1123	            theme_path=settings.theme_path,
  1124	            min_free_gb=settings.min_free_gb,
  1125	        )
  1126	        output_path.unlink(missing_ok=True)
  1127	        os.replace(staged_video, output_path)
  1128	
  1129	    try:
  1130	        provenance_v1 = _render_provenance_payload(
  1131	            output_path,
  1132	            engine="remotion",
  1133	            timeline_path=timeline_path,
  1134	            assets_path=requested_assets_path or assets_path,
  1135	            project_dir=settings.project_dir,
  1136	            composition_id=settings.composition_id,
  1137	            theme_path=settings.theme_path,
  1138	            active_theme=details.active_theme,
  1139	            registry_state=details.registry_state,
  1140	            stage_summary=details.stage_summary,
  1141	        )
  1142	        video = VideoArtifact.from_file(
  1143	            path=output_path,
  1144	            workspace_root=workspace,
  1145	            profile=declared_profile,
  1146	            duration_frames=_duration_frames(output_path, declared_profile),
  1147	            audio=ownership,
  1148	        )
  1149	        result = RenderResult(
  1150	            schema_version=SCHEMA_VERSION,
  1151	            video=video,
  1152	            audio_ownership=ownership,
  1153	            backend_fragments={
  1154	                BACKEND_ID: {
  1155	                    "renderer": "remotion",
  1156	                    "renderer_version": BACKEND_VERSION,
  1157	                    "composition": settings.composition_id,
  1158	                    "legacy_v1": provenance_v1,
  1159	                }
  1160	            },
  1161	            normalization=[],
  1162	            logs=[],
  1163	            metadata=request.metadata,
  1164	        )
  1165	        validate_render_result(
  1166	            result,
  1167	            expected_profile=declared_profile,
  1168	            workspace_root=workspace,
  1169	        )
  1170	        return result
  1171	    except BaseException:
  1172	        output_path.unlink(missing_ok=True)
  1173	        raise
  1174	
  1175	
  1176	def _load_request(path: Path) -> RenderRequest:
  1177	    payload = json.loads(path.read_text(encoding="utf-8"))
  1178	    if not isinstance(payload, Mapping):
  1179	        raise TypeError("render request must contain a JSON object")
  1180	    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)
  1181	
  1182	
  1183	def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
  1184	    if isinstance(exc, RendererException):
  1185	        error_kind = exc.error.kind
  1186	        message = exc.error.message
  1187	        recovery = exc.error.recovery_command
  1188	        details = exc.error.details
  1189	    else:
  1190	        error_kind = kind
  1191	        message = str(exc) or type(exc).__name__
  1192	        recovery = None
  1193	        details = {"error_type": type(exc).__name__}
  1194	    error = make_renderer_error(
  1195	        error_kind,

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '1,540p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '400,760p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   400	    if not path.is_absolute():
   401	        path = (assets_path.parent / path).resolve()
   402	    else:
   403	        path = path.resolve()
   404	    if not path.is_file():
   405	        raise FileNotFoundError(f"Asset {asset_id!r} source is missing: {path}")
   406	    return path
   407	
   408	
   409	def _probe_duration(probe: MediaProbe) -> float | None:
   410	    if probe.duration_seconds is not None:
   411	        return float(probe.duration_seconds)
   412	    if probe.duration_rational is not None:
   413	        numerator, denominator = probe.duration_rational
   414	        return numerator / denominator
   415	    return None
   416	
   417	
   418	def _requested_ownership(
   419	    request: RenderRequest,
   420	    *,
   421	    has_audio_clips: bool,
   422	) -> tuple[AudioOwnership, list[str]]:
   423	    natural = AudioOwnership.RENDERED if has_audio_clips else AudioOwnership.NONE
   424	    ownership = natural
   425	    reasons: list[str] = []
   426	    if request.audio is AudioOwnership.PASSTHROUGH and not has_audio_clips:
   427	        ownership = AudioOwnership.PASSTHROUGH
   428	    elif request.audio is not None and request.audio is not natural:
   429	        reasons.append(
   430	            f"audio={request.audio.value!r} is incompatible with timeline audio ownership {natural.value!r}"
   431	        )
   432	    if request.profile is not None and request.profile.has_audio != (
   433	        ownership is AudioOwnership.RENDERED
   434	    ):
   435	        reasons.append(
   436	            "requested profile audio fields do not match rendering.ffmpeg audio ownership"
   437	        )
   438	    return ownership, reasons
   439	
   440	
   441	def _whole_media_optimization(
   442	    timeline_data: Mapping[str, Any],
   443	    assets: Mapping[str, Any],
   444	    probes: Mapping[str, MediaProbe],
   445	) -> bool:
   446	    tracks = {
   447	        track.get("id"): track
   448	        for track in timeline_data.get("tracks", [])
   449	        if isinstance(track, Mapping)
   450	    }
   451	    visual = [
   452	        clip
   453	        for clip in timeline_data.get("clips", [])
   454	        if isinstance(clip, Mapping)
   455	        and clip.get("clipType") == "media"
   456	        and tracks.get(clip.get("track"), {}).get("kind") == "visual"
   457	    ]
   458	    table = _assets_table(assets)
   459	    if len(visual) != 1 or table is None:
   460	        return False
   461	    clip = visual[0]
   462	    entry = table.get(clip.get("asset"))
   463	    if not isinstance(entry, Mapping):
   464	        return False
   465	    media_probe = probes.get(str(clip.get("asset")))
   466	    if media_probe is None or not media_probe.has_video_stream:
   467	        return False
   468	    try:
   469	        bounds = _clip_range(clip)
   470	        width, height, fps = _canvas(timeline_data)
   471	        duration = _number(entry.get("duration"), "asset duration")
   472	        source_fps = _number(entry.get("fps"), "asset fps")
   473	    except ValueError:
   474	        return False
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
   541	    if fps_rational is None:
   542	        return None
   543	    num, den = fps_rational
   544	    return num // den if den and num % den == 0 else None
   545	
   546	
   547	def _canvas(timeline_data: Mapping[str, Any]) -> tuple[int, int, int]:
   548	    overrides = timeline_data.get("theme_overrides")
   549	    visual = overrides.get("visual") if isinstance(overrides, Mapping) else None
   550	    canvas = visual.get("canvas") if isinstance(visual, Mapping) else None
   551	    canvas = canvas if isinstance(canvas, Mapping) else {}
   552	    values: list[int] = []
   553	    for key, default in (("width", 1920), ("height", 1080), ("fps", 30)):
   554	        value = canvas.get(key, default)
   555	        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
   556	            raise ValueError(f"Canvas {key} must be a positive integer")
   557	        values.append(value)
   558	    return values[0], values[1], values[2]
   559	
   560	
   561	def support(
   562	    request: RenderRequest,
   563	    timeline_data: Mapping[str, Any],
   564	    assets: Mapping[str, Any],
   565	    *,
   566	    probe: Probe | None = None,
   567	    which: BinaryResolver | None = None,
   568	) -> SupportReport:
   569	    """Return strict support evidence for one already-decoded request."""
   570	
   571	    reasons: list[str] = []
   572	    probe_media = probe or ffprobe_metadata_strict
   573	    resolve_binary = which or shutil.which
   574	    binary_available: dict[str, bool] = {}
   575	    for binary in ("ffmpeg", "ffprobe"):
   576	        available = resolve_binary(binary) is not None
   577	        binary_available[binary] = available
   578	        if not available:
   579	            reasons.append(f"required binary is unavailable: {binary}")
   580	
   581	    if request.window is not None:
   582	        reasons.append(
   583	            "rendering.ffmpeg accepts complete timelines, not native frame windows"
   584	        )
   585	    config = request.backend_config.get(BACKEND_ID, {})
   586	    if config:
   587	        reasons.append(
   588	            "rendering.ffmpeg does not accept backend-specific configuration"
   589	        )
   590	    if request.assets_registry_path is None:
   591	        reasons.append("rendering.ffmpeg requires an assets registry")
   592	    try:
   593	        _canvas(timeline_data)
   594	    except ValueError as exc:
   595	        reasons.append(str(exc))
   596	    reasons.extend(structural_reasons(timeline_data))
   597	
   598	    table = _assets_table(assets)
   599	    if table is None:
   600	        reasons.append("assets registry must contain an assets object")
   601	        table = {}
   602	    assets_path = _registry_path(request)
   603	    tracks = {
   604	        track.get("id"): track
   605	        for track in timeline_data.get("tracks", [])
   606	        if isinstance(track, Mapping)
   607	    }
   608	    media_clips = [
   609	        clip
   610	        for clip in timeline_data.get("clips", [])
   611	        if isinstance(clip, Mapping) and clip.get("clipType") == "media"
   612	    ]
   613	    audio_clips = [
   614	        clip
   615	        for clip in media_clips
   616	        if tracks.get(clip.get("track"), {}).get("kind") == "audio"
   617	    ]
   618	    ownership, ownership_reasons = _requested_ownership(
   619	        request,
   620	        has_audio_clips=bool(audio_clips),
   621	    )
   622	    reasons.extend(ownership_reasons)
   623	
   624	    probes: dict[str, MediaProbe] = {}
   625	    for clip in media_clips:
   626	        clip_id = clip.get("id")
   627	        asset_id = clip.get("asset")
   628	        if not isinstance(asset_id, str) or not asset_id:
   629	            reasons.append(f"Clip {clip_id!r} has no asset")
   630	            continue
   631	        entry = table.get(asset_id)
   632	        if not isinstance(entry, Mapping):
   633	            reasons.append(f"Clip {clip_id!r} references missing asset {asset_id!r}")
   634	            continue
   635	        try:
   636	            path = _asset_path(entry, asset_id=asset_id, assets_path=assets_path)
   637	        except (ValueError, FileNotFoundError) as exc:
   638	            reasons.append(str(exc))
   639	            continue
   640	        if asset_id not in probes and binary_available["ffprobe"]:
   641	            try:
   642	                probed = probe_media(path)
   643	                if not isinstance(probed, MediaProbe):
   644	                    raise TypeError("probe did not return MediaProbe")
   645	                probes[asset_id] = probed
   646	            except Exception as exc:
   647	                reasons.append(f"Asset {asset_id!r} cannot be probed: {exc}")
   648	
   649	        media_probe = probes.get(asset_id)
   650	        if media_probe is None:
   651	            continue
   652	        track = tracks.get(clip.get("track"), {})
   653	        kind = track.get("kind")
   654	        if kind == "visual" and not media_probe.has_video_stream:
   655	            reasons.append(
   656	                f"Visual clip {clip_id!r} source {asset_id!r} has no video stream"
   657	            )
   658	        if kind == "audio" and not media_probe.has_audio_stream:
   659	            reasons.append(
   660	                f"Audio clip {clip_id!r} source {asset_id!r} has no audio stream"
   661	            )
   662	        if kind == "visual" and media_probe.has_audio_stream:
   663	            try:
   664	                gain = effective_gain(track, clip)
   665	            except ValueError:
   666	                gain = 0.0
   667	            if gain != 0.0:
   668	                reasons.append(
   669	                    f"Visual clip {clip_id!r} requests embedded audio that rendering.ffmpeg would discard"
   670	                )
   671	        try:
   672	            bounds = _clip_range(clip)
   673	        except ValueError:
   674	            continue
   675	        source_duration = _probe_duration(media_probe)
   676	        if source_duration is None:
   677	            reasons.append(
   678	                f"Asset {asset_id!r} has no probed duration for source-bound validation"
   679	            )
   680	        elif bounds.source_to > source_duration + _SOURCE_BOUND_TOLERANCE_SECONDS:
   681	            reasons.append(
   682	                f"Clip {clip_id!r} source bound {bounds.source_to:.6f} exceeds "
   683	                f"asset {asset_id!r} duration {source_duration:.6f}"
   684	            )
   685	
   686	    reactive = any(
   687	        isinstance(clip, Mapping)
   688	        and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
   689	        for clip in timeline_data.get("clips", [])
   690	    )
   691	    specialization = False
   692	    if reactive:
   693	        try:
   694	            spec = audio_reactive_colour.match_and_validate(
   695	                dict(timeline_data),
   696	                dict(assets),
   697	                assets_path,
   698	            )
   699	        except Exception as exc:
   700	            reasons.append(f"audio-reactive-colour specialization is unsupported: {exc}")
   701	        else:
   702	            specialization = spec is not None
   703	
   704	    whole_media = not reactive and _whole_media_optimization(
   705	        timeline_data,
   706	        assets,
   707	        probes,
   708	    )
   709	    features: dict[str, bool | str] = {
   710	        "media_only": not specialization,
   711	        "full_timeline": True,
   712	        "windows": False,
   713	        "sequential_audio": True,
   714	        "audio_reactive_colour": specialization,
   715	        "whole_media": whole_media,
   716	        "whole_media_optimization": whole_media,
   717	        "stream_copy": whole_media,
   718	        "audio_ownership": ownership.value,
   719	    }
   720	    if specialization:
   721	        features["specialization"] = audio_reactive_colour.ADAPTER_ID
   722	
   723	    reasons.extend(_profile_support_reasons(request, timeline_data))
   724	
   725	    reasons = _dedupe(reasons)
   726	    return SupportReport(
   727	        schema_version=SCHEMA_VERSION,
   728	        supported=not reasons,
   729	        reasons=reasons,
   730	        features=features,
   731	        alternatives=list(ALTERNATIVE_BACKENDS) if reasons else [],
   732	        backend=BACKEND_ID,
   733	        backend_version=BACKEND_VERSION,
   734	    )
   735	
   736	
   737	__all__ = [
   738	    "ALTERNATIVE_BACKENDS",
   739	    "BACKEND_ID",
   740	    "BACKEND_VERSION",
   741	    "effective_gain",
   742	    "structural_reasons",
   743	    "support",
   744	]

 succeeded in 15ms:
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
   521	    "timeline_canvas",
   522	    "validate_ffmpeg_media_timeline",
   523	]

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   251	    if request.assets_registry_path is None:
   252	        return _support_load_failure("rendering.ffmpeg requires an assets registry")
   253	    assets_path = _input_path(request.assets_registry_path, workspace)
   254	    try:
   255	        timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   256	        if not isinstance(timeline_data, dict):
   257	            raise ValueError("timeline must contain a JSON object")
   258	        assets = timeline.load_registry(assets_path)
   259	    except Exception as exc:
   260	        return _support_load_failure(str(exc) or type(exc).__name__)
   261	
   262	    localized = replace(
   263	        request,
   264	        timeline_path=str(timeline_path),
   265	        assets_registry_path=str(assets_path),
   266	    )
   267	    return strict_support(
   268	        localized,
   269	        timeline_data,
   270	        assets,
   271	        probe=ffprobe_metadata_strict,
   272	    )
   273	
   274	
   275	def _support_load_failure(reason: str) -> SupportReport:
   276	    return SupportReport(
   277	        schema_version=SCHEMA_VERSION,
   278	        supported=False,
   279	        reasons=[reason],
   280	        features={
   281	            "media_only": False,
   282	            "full_timeline": True,
   283	            "windows": False,
   284	            "sequential_audio": True,
   285	            "audio_reactive_colour": False,
   286	            "whole_media": False,
   287	            "whole_media_optimization": False,
   288	            "stream_copy": False,
   289	            "audio_ownership": AudioOwnership.NONE.value,
   290	        },
   291	        alternatives=list(ALTERNATIVE_BACKENDS),
   292	        backend=BACKEND_ID,
   293	        backend_version=BACKEND_VERSION,
   294	    )
   295	
   296	
   297	def _audio_reactive_ffmpeg_element(
   298	    theme_path: Path | None,
   299	) -> Any | None:
   300	    effects, _aliases = remotion_backend._effect_registry_for_assets(theme_path)
   301	    element = effects.get(audio_reactive_colour.EFFECT_ID)
   302	    if (
   303	        element is None
   304	        or element.metadata.get("ffmpegAdapter")
   305	        != audio_reactive_colour.ADAPTER_ID
   306	    ):
   307	        return None
   308	    return element
   309	
   310	
   311	def render_audio_reactive_colour_if_supported(
   312	    timeline_path: Path,
   313	    assets_path: Path,
   314	    out_path: Path,
   315	    *,
   316	    project_dir: Path | None,
   317	    composition_id: str,
   318	    theme_path: Path | None,
   319	    previous_outputs: Sequence[Path] = (),
   320	    element_resolver: Any | None = None,
   321	) -> Path | None:
   322	    """Preserve the facade's early audio-reactive FFmpeg specialization."""
   323	
   324	    timeline_data = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
   325	    clips = timeline_data.get("clips")
   326	    if (
   327	        not isinstance(clips, list)
   328	        or len(clips) != 2
   329	        or sum(
   330	            isinstance(clip, dict)

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/profile.py | sed -n '1,300p'; nl -ba astrid/core/rendering/artifacts.py | sed -n '1,390p'; nl -ba astrid/core/media.py | sed -n '1,270p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc 'rg -n "class MediaProbe|time_base|video_profile|video_level|validate_render_result|profile_mismatches" astrid/core astrid/packs/rendering/backends/ffmpeg astrid/packs/rendering/backends/remotion tests/packs/rendering | head -n 320' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/ffmpeg/support.py:515:        ("time_base", profile.time_base, (1, fps * 512)),
astrid/packs/rendering/backends/ffmpeg/run.py:29:from astrid.core.rendering.artifacts import validate_render_result
astrid/packs/rendering/backends/ffmpeg/run.py:487:        time_base=_required(probe.time_base, "video time base"),
astrid/packs/rendering/backends/ffmpeg/run.py:490:        video_profile=probe.video_profile,
astrid/packs/rendering/backends/ffmpeg/run.py:491:        video_level=probe.video_level,
astrid/packs/rendering/backends/ffmpeg/run.py:641:        validate_render_result(
tests/packs/rendering/test_ffmpeg_backend.py:136:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py:139:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:140:        video_level="4.0",
tests/packs/rendering/test_ffmpeg_backend.py:346:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py:348:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:349:        video_level="40",
tests/packs/rendering/test_ffmpeg_backend.py:364:        mock.patch.object(ffmpeg, "validate_render_result") as validate,
tests/packs/rendering/test_ffmpeg_finalizer.py:43:    time_base: tuple[int, int] | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py:47:    video_profile: str | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py:48:    video_level: str | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py:55:    if time_base is None:
tests/packs/rendering/test_ffmpeg_finalizer.py:59:        time_base = (1, timescale)
tests/packs/rendering/test_ffmpeg_finalizer.py:64:        time_base=time_base,
tests/packs/rendering/test_ffmpeg_finalizer.py:67:        video_profile=video_profile,
tests/packs/rendering/test_ffmpeg_finalizer.py:68:        video_level=video_level,
tests/packs/rendering/test_ffmpeg_finalizer.py:232:            time_base=profile.time_base,
tests/packs/rendering/test_ffmpeg_finalizer.py:234:            video_profile=profile.video_profile or "High",
tests/packs/rendering/test_ffmpeg_finalizer.py:235:            video_level=profile.video_level or "40",
tests/packs/rendering/test_ffmpeg_finalizer.py:258:        "validate_render_result",
tests/packs/rendering/test_ffmpeg_finalizer.py:369:    source = _profile(fps=(60, 1), time_base=(1, 60_000))
tests/packs/rendering/test_ffmpeg_finalizer.py:392:    assert f"settb=expr={target.time_base[0]}/{target.time_base[1]}" in filters
tests/packs/rendering/test_ffmpeg_finalizer.py:411:        "validate_render_result",
tests/packs/rendering/test_ffmpeg_finalizer.py:441:                time_base=(1, 12_288),
tests/packs/rendering/test_ffmpeg_finalizer.py:462:                video_profile="Main",
tests/packs/rendering/test_ffmpeg_finalizer.py:463:                video_level="120",
tests/packs/rendering/test_ffmpeg_finalizer.py:487:            replace(canonical, video_profile="High", video_level="40"),
tests/packs/rendering/test_ffmpeg_finalizer.py:488:            replace(canonical, video_profile="Main", video_level="31"),
tests/packs/rendering/test_ffmpeg_finalizer.py:499:    assert "segment[1] video_profile: Main -> High" in result.normalization
tests/packs/rendering/test_ffmpeg_finalizer.py:500:    assert "segment[1] video_level: 31 -> 40" in result.normalization
tests/packs/rendering/test_ffmpeg_finalizer.py:639:            "validate_render_result",
tests/packs/rendering/test_ffmpeg_finalizer.py:730:        time_base=(1, 30_000),
tests/packs/rendering/test_ffmpeg_finalizer.py:733:        video_profile="High",
tests/packs/rendering/test_ffmpeg_finalizer.py:734:        video_level="4.0",
tests/packs/rendering/test_ffmpeg_finalizer.py:749:    assert output_probe.time_base == (1, 30_000)
tests/packs/rendering/test_ffmpeg_finalizer.py:750:    assert output_probe.video_profile == "High"
tests/packs/rendering/test_ffmpeg_finalizer.py:752:        output_probe.video_level,
tests/packs/rendering/test_remotion_backend.py:268:        time_base=(1, 15360),
tests/packs/rendering/test_remotion_backend.py:271:        video_profile=None,
tests/packs/rendering/test_remotion_backend.py:272:        video_level=None,
tests/packs/rendering/test_remotion_backend.py:298:        mock.patch.object(remotion, "validate_render_result"),
tests/packs/rendering/test_ffmpeg_support.py:451:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py:454:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:455:        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py:480:        mock.patch.object(ffmpeg, "validate_render_result"),
tests/packs/rendering/test_ffmpeg_support.py:571:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py:573:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:574:        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py:610:        mock.patch.object(ffmpeg, "validate_render_result"),
astrid/packs/rendering/backends/remotion/run.py:42:from astrid.core.rendering.artifacts import validate_render_result
astrid/packs/rendering/backends/remotion/run.py:903:def _profile_mismatches(
astrid/packs/rendering/backends/remotion/run.py:1019:                    time_base=(1, 90000),
astrid/packs/rendering/backends/remotion/run.py:1024:                mismatches = _profile_mismatches(request.profile, render_profile)
astrid/packs/rendering/backends/remotion/run.py:1098:        declared_profile = replace(declared_profile, time_base=(1, 90000))
astrid/packs/rendering/backends/remotion/run.py:1165:        validate_render_result(
astrid/core/media.py:29:class MediaProbe:
astrid/core/media.py:46:    time_base: tuple[int, int] | None = None
astrid/core/media.py:48:    video_profile: str | None = None
astrid/core/media.py:49:    video_level: str | None = None
astrid/core/media.py:89:class MediaProbeError(RuntimeError):
astrid/core/media.py:206:        probe.time_base = _positive_rational(video_stream.get("time_base"))
astrid/core/media.py:208:        probe.video_profile = _nonempty_string(video_stream.get("profile"))
astrid/core/media.py:211:            probe.video_level = str(level).strip()
astrid/core/rendering/artifacts.py:279:    if field in {"fps_rational", "time_base"}:
astrid/core/rendering/artifacts.py:284:    if field == "video_level":
astrid/core/rendering/artifacts.py:294:        "video_profile",
astrid/core/rendering/artifacts.py:318:        "time_base",
astrid/core/rendering/artifacts.py:334:    for field in ("video_profile", "video_level"):
astrid/core/rendering/artifacts.py:386:        for field in ("width", "height", "fps_rational", "time_base", "video_codec", "pixel_format")
astrid/core/rendering/artifacts.py:404:    _rational(probe.time_base, label="video time base")
astrid/core/rendering/artifacts.py:418:        "time_base": probe.time_base,
astrid/core/rendering/artifacts.py:441:        ("video_profile", probe.video_profile),
astrid/core/rendering/artifacts.py:442:        ("video_level", probe.video_level),
astrid/core/rendering/artifacts.py:669:def validate_render_result(
astrid/core/rendering/artifacts.py:741:__all__ = ["validate_render_result"]
astrid/core/rendering/profile.py:179:def _mp4_time_base(fps: Fraction) -> tuple[int, int]:
astrid/core/rendering/profile.py:281:        time_base=_mp4_time_base(fps),
astrid/core/rendering/profile.py:284:        video_profile=None,
astrid/core/rendering/profile.py:285:        video_level=None,
astrid/core/rendering/schemas/v1/finalize.json:171:        "time_base",
astrid/core/rendering/schemas/v1/finalize.json:174:        "video_profile",
astrid/core/rendering/schemas/v1/finalize.json:175:        "video_level",
astrid/core/rendering/schemas/v1/finalize.json:191:        "time_base": {
astrid/core/rendering/schemas/v1/finalize.json:204:        "video_profile": {
astrid/core/rendering/schemas/v1/finalize.json:212:        "video_level": {
astrid/core/rendering/schemas/v1/finalize.json:882:          "time_base": [
astrid/core/rendering/schemas/v1/finalize.json:888:          "video_profile": "high",
astrid/core/rendering/schemas/v1/finalize.json:889:          "video_level": "4.1",
astrid/core/rendering/schemas/v1/finalize.json:912:            "time_base": [
astrid/core/rendering/schemas/v1/finalize.json:918:            "video_profile": "high",
astrid/core/rendering/schemas/v1/finalize.json:919:            "video_level": "4.1",
astrid/core/rendering/schemas/v1/plan.json:203:        "time_base",
astrid/core/rendering/schemas/v1/plan.json:206:        "video_profile",
astrid/core/rendering/schemas/v1/plan.json:207:        "video_level",
astrid/core/rendering/schemas/v1/plan.json:223:        "time_base": {
astrid/core/rendering/schemas/v1/plan.json:236:        "video_profile": {
astrid/core/rendering/schemas/v1/plan.json:244:        "video_level": {
astrid/core/rendering/schemas/v1/plan.json:682:        "time_base": [
astrid/core/rendering/schemas/v1/plan.json:688:        "video_profile": "high",
astrid/core/rendering/schemas/v1/plan.json:689:        "video_level": "4.1",
astrid/core/rendering/schemas/v1/plan.json:749:        "time_base": [
astrid/core/rendering/schemas/v1/plan.json:755:        "video_profile": null,
astrid/core/rendering/schemas/v1/plan.json:756:        "video_level": null,
astrid/core/rendering/schemas/v1/request.json:232:        "time_base",
astrid/core/rendering/schemas/v1/request.json:235:        "video_profile",
astrid/core/rendering/schemas/v1/request.json:236:        "video_level",
astrid/core/rendering/schemas/v1/request.json:252:        "time_base": {
astrid/core/rendering/schemas/v1/request.json:265:        "video_profile": {
astrid/core/rendering/schemas/v1/request.json:273:        "video_level": {
astrid/core/rendering/schemas/v1/request.json:400:        "time_base": [
astrid/core/rendering/schemas/v1/request.json:406:        "video_profile": "high",
astrid/core/rendering/schemas/v1/request.json:407:        "video_level": "4.1",
astrid/core/rendering/schemas/v1/result.json:61:        "time_base",
astrid/core/rendering/schemas/v1/result.json:64:        "video_profile",
astrid/core/rendering/schemas/v1/result.json:65:        "video_level",
astrid/core/rendering/schemas/v1/result.json:81:        "time_base": {
astrid/core/rendering/schemas/v1/result.json:94:        "video_profile": {
astrid/core/rendering/schemas/v1/result.json:102:        "video_level": {
astrid/core/rendering/schemas/v1/result.json:517:          "time_base": [
astrid/core/rendering/schemas/v1/result.json:523:          "video_profile": "high",
astrid/core/rendering/schemas/v1/result.json:524:          "video_level": "4.1",
astrid/core/rendering/contracts.py:458:    time_base: tuple[int, int]
astrid/core/rendering/contracts.py:461:    video_profile: str | None = None
astrid/core/rendering/contracts.py:462:    video_level: str | None = None
astrid/core/rendering/contracts.py:473:        object.__setattr__(self, "time_base", _require_rational(self.time_base, "time_base"))
astrid/core/rendering/contracts.py:478:            "video_profile",
astrid/core/rendering/contracts.py:479:            _require_optional_string(self.video_profile, "video_profile"),
astrid/core/rendering/contracts.py:483:            "video_level",
astrid/core/rendering/contracts.py:484:            _require_optional_string(self.video_level, "video_level"),
astrid/core/rendering/contracts.py:527:                "time_base": self.time_base,
astrid/core/rendering/contracts.py:530:                "video_profile": self.video_profile,
astrid/core/rendering/contracts.py:531:                "video_level": self.video_level,
astrid/core/rendering/contracts.py:547:            "time_base",
astrid/core/rendering/contracts.py:550:            "video_profile",
astrid/core/rendering/contracts.py:551:            "video_level",
astrid/core/rendering/contracts.py:561:            time_base=data["time_base"],
astrid/core/rendering/contracts.py:564:            video_profile=data["video_profile"],
astrid/core/rendering/contracts.py:565:            video_level=data["video_level"],

exec
/bin/zsh -lc "nl -ba tests/packs/rendering/test_ffmpeg_support.py | sed -n '1,560p'; nl -ba tests/packs/rendering/test_ffmpeg_backend.py | sed -n '1,330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	from __future__ import annotations
     2	
     3	import copy
     4	import importlib
     5	import json
     6	import subprocess
     7	from pathlib import Path
     8	from unittest import mock
     9	
    10	import pytest
    11	
    12	from astrid.core.media import MediaProbe
    13	from astrid.core.rendering.contracts import (
    14	    AudioOwnership,
    15	    FrameWindow,
    16	    RenderRequest,
    17	    RenderResult,
    18	    SCHEMA_VERSION,
    19	)
    20	from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
    21	from astrid.packs.rendering.backends.ffmpeg import command
    22	from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
    23	from astrid.packs.rendering.backends.ffmpeg.support import support as evaluate_support
    24	
    25	
    26	support_module = importlib.import_module(
    27	    "astrid.packs.rendering.backends.ffmpeg.support"
    28	)
    29	
    30	
    31	def _timeline(*, include_audio: bool = True, duration: float = 4.0) -> dict:
    32	    tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
    33	    clips = [
    34	        {
    35	            "id": "video",
    36	            "at": 0,
    37	            "track": "v",
    38	            "clipType": "media",
    39	            "asset": "video",
    40	            "from": 0,
    41	            "to": duration,
    42	            "speed": 1,
    43	            "volume": 0,
    44	        }
    45	    ]
    46	    if include_audio:
    47	        tracks.append(
    48	            {
    49	                "id": "a",
    50	                "kind": "audio",
    51	                "label": "Audio",
    52	                "volume": 0.5,
    53	            }
    54	        )
    55	        clips.append(
    56	            {
    57	                "id": "audio",
    58	                "at": 0,
    59	                "track": "a",
    60	                "clipType": "media",
    61	                "asset": "audio",
    62	                "from": 0,
    63	                "to": duration,
    64	                "speed": 1,
    65	                "volume": 0.4,
    66	            }
    67	        )
    68	    return {
    69	        "theme": "banodoco-default",
    70	        "theme_overrides": {
    71	            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
    72	        },
    73	        "tracks": tracks,
    74	        "clips": clips,
    75	    }
    76	
    77	
    78	def _assets(tmp_path: Path, *, duration: float = 4.0) -> dict:
    79	    return {
    80	        "assets": {
    81	            "video": {
    82	                "file": "video.mp4",
    83	                "type": "video/mp4",
    84	                "duration": duration,
    85	                "resolution": "640x360",
    86	                "fps": 30,
    87	            },
    88	            "audio": {
    89	                "file": "audio.wav",
    90	                "type": "audio/wav",
    91	                "duration": duration,
    92	            },
    93	        }
    94	    }
    95	
    96	
    97	def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
    98	    return MediaProbe(
    99	        duration_seconds=duration,
   100	        width=640,
   101	        height=360,
   102	        fps=30,
   103	        resolution="640x360",
   104	        video_codec="h264",
   105	        pixel_format="yuv420p",
   106	        audio_codec="aac" if audio else None,
   107	        video_stream_present=True,
   108	        audio_stream_present=audio,
   109	    )
   110	
   111	
   112	def _audio_probe(*, duration: float = 4.0, present: bool = True) -> MediaProbe:
   113	    return MediaProbe(
   114	        duration_seconds=duration,
   115	        audio_codec="pcm_s16le" if present else None,
   116	        video_stream_present=False,
   117	        audio_stream_present=present,
   118	    )
   119	
   120	
   121	def _request(
   122	    tmp_path: Path,
   123	    *,
   124	    audio: AudioOwnership | None = None,
   125	    window: FrameWindow | None = None,
   126	) -> RenderRequest:
   127	    return RenderRequest(
   128	        schema_version=SCHEMA_VERSION,
   129	        timeline_path=str(tmp_path / "timeline.json"),
   130	        assets_registry_path=str(tmp_path / "assets.json"),
   131	        output_name="result.mp4",
   132	        window=window,
   133	        audio=audio,
   134	        backend_config={ffmpeg.BACKEND_ID: {}},
   135	    )
   136	
   137	
   138	def _evaluate(
   139	    tmp_path: Path,
   140	    timeline_data: dict,
   141	    assets: dict,
   142	    *,
   143	    probes: dict[str, MediaProbe] | None = None,
   144	    missing_files: set[str] | None = None,
   145	    which=None,
   146	    request: RenderRequest | None = None,
   147	):
   148	    missing = missing_files or set()
   149	    for entry in assets.get("assets", {}).values():
   150	        file_value = entry.get("file")
   151	        if isinstance(file_value, str) and file_value not in missing:
   152	            (tmp_path / file_value).write_bytes(b"source")
   153	    (tmp_path / "timeline.json").write_text(
   154	        json.dumps(timeline_data),
   155	        encoding="utf-8",
   156	    )
   157	    (tmp_path / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
   158	    probe_map = probes or {
   159	        "video.mp4": _video_probe(),
   160	        "audio.wav": _audio_probe(),
   161	    }
   162	
   163	    return evaluate_support(
   164	        request or _request(tmp_path),
   165	        timeline_data,
   166	        assets,
   167	        probe=lambda path: probe_map[Path(path).name],
   168	        which=which or (lambda binary: f"/usr/bin/{binary}"),
   169	    )
   170	
   171	
   172	def _build_command(tmp_path: Path, timeline_data: dict, assets: dict) -> list[str]:
   173	    _evaluate(tmp_path, timeline_data, assets)
   174	    return command.build_render_command(_request(tmp_path), tmp_path)
   175	
   176	
   177	def test_supported_report_exposes_request_specific_evidence(tmp_path: Path) -> None:
   178	    report = _evaluate(tmp_path, _timeline(), _assets(tmp_path))
   179	
   180	    assert report.supported is True
   181	    assert report.reasons == []
   182	    assert report.alternatives == []
   183	    assert report.features["whole_media"] is True
   184	    assert report.features["stream_copy"] is True
   185	    assert report.features["audio_reactive_colour"] is False
   186	    assert report.features["audio_ownership"] == "rendered"
   187	
   188	
   189	@pytest.mark.parametrize(
   190	    ("case", "reason"),
   191	    [
   192	        ("unknown_track_kind", "unsupported kind"),
   193	        ("unknown_clip_kind", "unsupported clip kind"),
   194	        ("unknown_track", "unknown track"),
   195	        ("invalid_bounds", "positive source bounds"),
   196	        ("source_bound", "exceeds"),
   197	        ("visual_gap", "Visual gap"),
   198	        ("visual_overlap", "Visual overlap"),
   199	        ("speed", "unsupported speed"),
   200	        ("transform", "unsupported transforms"),
   201	        ("track_transform", "transform semantics"),
   202	        ("crop", "unsupported crop"),
   203	        ("effects", "unsupported effects"),
   204	        ("transition", "unsupported transition"),
   205	        ("opacity", "non-default opacity"),
   206	        ("discarded_visual_audio", "embedded audio"),
   207	        ("overlapping_audio", "Overlapping audio"),
   208	        ("fade", "audio fades"),
   209	        ("missing_source", "source is missing"),
   210	        ("missing_video_stream", "no video stream"),
   211	        ("missing_audio_stream", "no audio stream"),
   212	        ("missing_binary", "required binary is unavailable"),
   213	        ("window", "frame windows"),
   214	    ],
   215	)
   216	def test_support_fails_closed_for_every_unsupported_semantic(
   217	    tmp_path: Path,
   218	    case: str,
   219	    reason: str,
   220	) -> None:
   221	    timeline_data = _timeline()
   222	    assets = _assets(tmp_path)
   223	    probes = {
   224	        "video.mp4": _video_probe(),
   225	        "audio.wav": _audio_probe(),
   226	    }
   227	    missing_files: set[str] = set()
   228	    which = lambda binary: f"/usr/bin/{binary}"
   229	    request = _request(tmp_path)
   230	
   231	    if case == "unknown_track_kind":
   232	        timeline_data["tracks"][1]["kind"] = "captions"
   233	    elif case == "unknown_clip_kind":
   234	        timeline_data["clips"][0]["clipType"] = "text"
   235	    elif case == "unknown_track":
   236	        timeline_data["clips"][0]["track"] = "missing"
   237	    elif case == "invalid_bounds":
   238	        timeline_data["clips"][0]["to"] = 0
   239	    elif case == "source_bound":
   240	        timeline_data["clips"][0]["to"] = 5
   241	    elif case == "visual_gap":
   242	        timeline_data["clips"][0]["at"] = 0.25
   243	    elif case == "visual_overlap":
   244	        timeline_data["clips"][0]["to"] = 2
   245	        timeline_data["clips"].append(
   246	            {
   247	                **copy.deepcopy(timeline_data["clips"][0]),
   248	                "id": "video_2",
   249	                "at": 1.5,
   250	                "from": 2,
   251	                "to": 4,
   252	            }
   253	        )
   254	    elif case == "speed":
   255	        timeline_data["clips"][0]["speed"] = 1.25
   256	    elif case == "transform":
   257	        timeline_data["clips"][0]["x"] = 10
   258	    elif case == "track_transform":
   259	        timeline_data["tracks"][0]["scale"] = 1.2
   260	    elif case == "crop":
   261	        timeline_data["clips"][0]["cropTop"] = 10
   262	    elif case == "effects":
   263	        timeline_data["clips"][0]["effects"] = {"fade_in": 0.2}
   264	    elif case == "transition":
   265	        timeline_data["clips"][0]["transition"] = {"type": "fade"}
   266	    elif case == "opacity":
   267	        timeline_data["clips"][0]["opacity"] = 0.5
   268	    elif case == "discarded_visual_audio":
   269	        timeline_data["clips"][0]["volume"] = 1
   270	        probes["video.mp4"] = _video_probe(audio=True)
   271	    elif case == "overlapping_audio":
   272	        timeline_data["clips"][1]["to"] = 2
   273	        timeline_data["clips"].append(
   274	            {
   275	                **copy.deepcopy(timeline_data["clips"][1]),
   276	                "id": "audio_2",
   277	                "at": 1.5,
   278	                "from": 2,
   279	                "to": 4,
   280	            }
   281	        )
   282	    elif case == "fade":
   283	        timeline_data["clips"][1]["params"] = {"fadeIn": 0.2}
   284	    elif case == "missing_source":
   285	        missing_files.add("video.mp4")
   286	    elif case == "missing_video_stream":
   287	        probes["video.mp4"] = _audio_probe()
   288	    elif case == "missing_audio_stream":
   289	        probes["audio.wav"] = _audio_probe(present=False)
   290	    elif case == "missing_binary":
   291	        which = lambda binary: None if binary == "ffmpeg" else "/usr/bin/ffprobe"
   292	    elif case == "window":
   293	        request = _request(
   294	            tmp_path,
   295	            window=FrameWindow(
   296	                start_frame=0,
   297	                end_frame=30,
   298	                fps_rational=(30, 1),
   299	            ),
   300	        )
   301	
   302	    report = _evaluate(
   303	        tmp_path,
   304	        timeline_data,
   305	        assets,
   306	        probes=probes,
   307	        missing_files=missing_files,
   308	        which=which,
   309	        request=request,
   310	    )
   311	
   312	    assert report.supported is False
   313	    assert any(reason in item for item in report.reasons)
   314	    assert report.alternatives == ["rendering.remotion"]
   315	    assert all("." in backend for backend in report.alternatives)
   316	
   317	
   318	@pytest.mark.parametrize(
   319	    ("target", "value"),
   320	    [
   321	        ("track", -0.1),
   322	        ("track", 1.1),
   323	        ("clip", -0.1),
   324	        ("clip", 1.1),
   325	    ],
   326	)
   327	def test_support_rejects_malformed_gains(
   328	    tmp_path: Path,
   329	    target: str,
   330	    value: float,
   331	) -> None:
   332	    timeline_data = _timeline()
   333	    if target == "track":
   334	        timeline_data["tracks"][1]["volume"] = value
   335	    else:
   336	        timeline_data["clips"][1]["volume"] = value
   337	
   338	    report = _evaluate(tmp_path, timeline_data, _assets(tmp_path))
   339	
   340	    assert report.supported is False
   341	    assert any("between 0 and 1" in reason for reason in report.reasons)
   342	
   343	
   344	def test_track_and_clip_gain_multiply_into_filter(tmp_path: Path) -> None:
   345	    argv = _build_command(tmp_path, _timeline(), _assets(tmp_path))
   346	    filters = argv[argv.index("-filter_complex") + 1]
   347	
   348	    assert "volume=0.200000" in filters
   349	
   350	
   351	@pytest.mark.parametrize(("muted", "clip_volume"), [(True, 0.9), (False, 0.0)])
   352	def test_track_mute_and_clip_zero_force_silence(
   353	    tmp_path: Path,
   354	    muted: bool,
   355	    clip_volume: float,
   356	) -> None:
   357	    timeline_data = _timeline()
   358	    timeline_data["tracks"][1]["muted"] = muted
   359	    timeline_data["clips"][1]["volume"] = clip_volume
   360	
   361	    argv = _build_command(tmp_path, timeline_data, _assets(tmp_path))
   362	    filters = argv[argv.index("-filter_complex") + 1]
   363	
   364	    assert "volume=0.000000" in filters
   365	
   366	
   367	def test_non_overlapping_audio_clips_concat_with_positional_silence(
   368	    tmp_path: Path,
   369	) -> None:
   370	    timeline_data = _timeline()
   371	    timeline_data["clips"][1]["to"] = 1
   372	    timeline_data["clips"].append(
   373	        {
   374	            **copy.deepcopy(timeline_data["clips"][1]),
   375	            "id": "audio_2",
   376	            "at": 2,
   377	            "from": 1,
   378	            "to": 3,
   379	        }
   380	    )
   381	
   382	    report = _evaluate(tmp_path, timeline_data, _assets(tmp_path))
   383	    argv = command.build_render_command(_request(tmp_path), tmp_path)
   384	    filters = argv[argv.index("-filter_complex") + 1]
   385	
   386	    assert report.supported is True
   387	    assert "anullsrc=r=48000:cl=stereo,atrim=duration=1.000000" in filters
   388	    assert filters.count("volume=0.200000") == 2
   389	    assert "concat=n=3:v=0:a=1[aout]" in filters
   390	
   391	
   392	def test_visual_only_command_has_no_synthesized_audio_and_reports_none(
   393	    tmp_path: Path,
   394	) -> None:
   395	    timeline_data = _timeline(include_audio=False)
   396	    assets = _assets(tmp_path)
   397	    del assets["assets"]["audio"]
   398	
   399	    report = _evaluate(
   400	        tmp_path,
   401	        timeline_data,
   402	        assets,
   403	        probes={"video.mp4": _video_probe()},
   404	    )
   405	    argv = command.build_render_command(_request(tmp_path), tmp_path)
   406	
   407	    assert report.supported is True
   408	    assert report.features["audio_ownership"] == "none"
   409	    # Without probe evidence of whole-source compatibility, stream-copy must
   410	    # NOT be trusted from registry metadata: the builder re-encodes via
   411	    # filter_complex with no audio mapping (-an).
   412	    assert "-filter_complex" in argv
   413	    assert "-c:a" not in argv
   414	    assert "-an" in argv
   415	    assert argv[argv.index("-c:v") + 1] == "libx264"
   416	
   417	
   418	def test_visual_only_request_can_delegate_audio_as_passthrough(tmp_path: Path) -> None:
   419	    timeline_data = _timeline(include_audio=False)
   420	    assets = _assets(tmp_path)
   421	    del assets["assets"]["audio"]
   422	
   423	    report = _evaluate(
   424	        tmp_path,
   425	        timeline_data,
   426	        assets,
   427	        probes={"video.mp4": _video_probe()},
   428	        request=_request(tmp_path, audio=AudioOwnership.PASSTHROUGH),
   429	    )
   430	
   431	    assert report.supported is True
   432	    assert report.features["audio_ownership"] == "passthrough"
   433	
   434	
   435	def test_visual_only_protocol_result_declares_none(tmp_path: Path) -> None:
   436	    timeline_data = _timeline(include_audio=False)
   437	    assets = _assets(tmp_path)
   438	    del assets["assets"]["audio"]
   439	    _evaluate(
   440	        tmp_path,
   441	        timeline_data,
   442	        assets,
   443	        probes={"video.mp4": _video_probe()},
   444	    )
   445	    probe = MediaProbe(
   446	        duration_seconds=4,
   447	        width=640,
   448	        height=360,
   449	        fps=30,
   450	        fps_rational=(30, 1),
   451	        time_base=(1, 15360),
   452	        resolution="640x360",
   453	        video_codec="h264",
   454	        video_profile="High",
   455	        video_level="40",
   456	        pixel_format="yuv420p",
   457	        container="mp4",
   458	        duration_rational=(4, 1),
   459	        video_stream_present=True,
   460	        audio_stream_present=False,
   461	    )
   462	    seen: dict[str, list[str]] = {}
   463	
   464	    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
   465	        seen["argv"] = argv
   466	        output = Path(argv[-1])
   467	        output.parent.mkdir(parents=True, exist_ok=True)
   468	        output.write_bytes(b"video")
   469	        return subprocess.CompletedProcess(argv, 0)
   470	
   471	    with (
   472	        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
   473	        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", return_value=probe),
   474	        mock.patch.object(ffmpeg.subprocess, "run", side_effect=fake_run),
   475	        mock.patch.object(
   476	            ffmpeg.remotion_backend,
   477	            "_render_provenance_payload",
   478	            return_value={"engine": "ffmpeg"},
   479	        ),
   480	        mock.patch.object(ffmpeg, "validate_render_result"),
   481	    ):
   482	        result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)
   483	
   484	    assert result.audio_ownership is AudioOwnership.NONE
   485	    assert result.video.audio is AudioOwnership.NONE
   486	    assert result.video.profile.has_audio is False
   487	    assert "-an" in seen["argv"]
   488	    assert "-c:a" not in seen["argv"]
   489	
   490	
   491	def _reactive_timeline() -> dict:
   492	    return {
   493	        "theme": "banodoco-default",
   494	        "theme_overrides": {
   495	            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
   496	        },
   497	        "tracks": [
   498	            {"id": "v", "kind": "visual", "label": "Colour"},
   499	            {
   500	                "id": "a",
   501	                "kind": "audio",
   502	                "label": "Audio",
   503	                "volume": 0.5,
   504	            },
   505	        ],
   506	        "clips": [
   507	            {
   508	                "id": "colour",
   509	                "at": 0,
   510	                "track": "v",
   511	                "clipType": "audio-reactive-colour",
   512	                "hold": 1,
   513	                "params": {
   514	                    "schemaVersion": 1,
   515	                    "initialColor": "#102030",
   516	                    "events": [
   517	                        {"id": "one", "frame": 3, "color": "#D47795"},
   518	                        {"id": "two", "frame": 8, "color": "#26A7D0"},
   519	                    ],
   520	                },
   521	            },
   522	            {
   523	                "id": "audio",
   524	                "at": 0,
   525	                "track": "a",
   526	                "clipType": "media",
   527	                "asset": "audio",
   528	                "from": 0,
   529	                "to": 1,
   530	                "volume": 0.4,
   531	            },
   532	        ],
   533	    }
   534	
   535	
   536	def test_audio_reactive_support_gain_and_protocol_provenance_fragments(
   537	    tmp_path: Path,
   538	) -> None:
   539	    timeline_data = _reactive_timeline()
   540	    assets = {
   541	        "assets": {
   542	            "audio": {
   543	                "file": "audio.wav",
   544	                "type": "audio/wav",
   545	                "duration": 1,
   546	            }
   547	        }
   548	    }
   549	    report = _evaluate(
   550	        tmp_path,
   551	        timeline_data,
   552	        assets,
   553	        probes={"audio.wav": _audio_probe(duration=1)},
   554	    )
   555	    spec = audio_reactive_colour.match_and_validate(
   556	        timeline_data,
   557	        assets,
   558	        tmp_path / "assets.json",
   559	    )
   560	
     1	from __future__ import annotations
     2	
     3	import dataclasses
     4	import json
     5	import subprocess
     6	from pathlib import Path
     7	from unittest import mock
     8	
     9	import yaml
    10	
    11	from astrid.core.media import MediaProbe
    12	from astrid.core.rendering.contracts import (
    13	    AudioOwnership,
    14	    RenderProfile,
    15	    RenderRequest,
    16	    RenderResult,
    17	    RendererManifest,
    18	    SCHEMA_VERSION,
    19	    SupportReport,
    20	    VideoArtifact,
    21	)
    22	from astrid.core.rendering.transport import CommandTransport
    23	from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
    24	from astrid.packs.rendering.backends.ffmpeg import command
    25	from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
    26	from astrid.packs.rendering.executors.render import audio_reactive_colour as legacy_audio_reactive
    27	from astrid.packs.rendering.executors.render import run as facade
    28	
    29	
    30	ROOT = Path(__file__).resolve().parents[3]
    31	
    32	
    33	def _media_timeline(*, include_audio: bool = True) -> dict:
    34	    tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
    35	    clips = [
    36	        {
    37	            "id": "video",
    38	            "at": 0,
    39	            "track": "v",
    40	            "clipType": "media",
    41	            "asset": "main",
    42	            "from": 0,
    43	            "to": 2,
    44	            "speed": 1,
    45	            "volume": 0,
    46	        }
    47	    ]
    48	    if include_audio:
    49	        tracks.append({"id": "a", "kind": "audio", "label": "Audio"})
    50	        clips.append(
    51	            {
    52	                "id": "audio",
    53	                "at": 0,
    54	                "track": "a",
    55	                "clipType": "media",
    56	                "asset": "main",
    57	                "from": 0,
    58	                "to": 2,
    59	                "speed": 1,
    60	                "volume": 0.75,
    61	            }
    62	        )
    63	    return {
    64	        "theme": "banodoco-default",
    65	        "theme_overrides": {
    66	            "visual": {
    67	                "canvas": {"width": 1920, "height": 1080, "fps": 30}
    68	            }
    69	        },
    70	        "tracks": tracks,
    71	        "clips": clips,
    72	    }
    73	
    74	
    75	def _text_timeline() -> dict:
    76	    data = _media_timeline()
    77	    data["clips"].append(
    78	        {
    79	            "id": "title",
    80	            "at": 0.5,
    81	            "track": "v",
    82	            "clipType": "text-card",
    83	            "hold": 1,
    84	        }
    85	    )
    86	    return data
    87	
    88	
    89	def _write_inputs(
    90	    tmp_path: Path,
    91	    *,
    92	    timeline_data: dict | None = None,
    93	    registered: bool = True,
    94	    source_resolution: str = "1920x1080",
    95	) -> tuple[Path, Path]:
    96	    timeline_path = tmp_path / "timeline.json"
    97	    assets_path = tmp_path / "assets.json"
    98	    source_path = tmp_path / "source.mp4"
    99	    source_path.write_bytes(b"placeholder")
   100	    timeline_path.write_text(
   101	        json.dumps(timeline_data or _media_timeline()),
   102	        encoding="utf-8",
   103	    )
   104	    assets = (
   105	        {
   106	            "main": {
   107	                "file": source_path.name,
   108	                "type": "video/mp4",
   109	                "duration": 2,
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
   166	    assert manifest.required_permissions == ("project_files", "subprocess")
   167	    assert manifest.required_binaries == ("ffmpeg", "ffprobe")
   168	    assert manifest.capabilities["clip_types"] == ["media"]
   169	    assert (manifest_path.parents[2] / manifest.command[1]).is_file()
   170	
   171	    pack = yaml.safe_load(
   172	        (manifest_path.parents[2] / "pack.yaml").read_text(encoding="utf-8")
   173	    )
   174	    assert "backends/ffmpeg/renderer.yaml" in pack["extensions"]["rendering"][
   175	        "renderers"
   176	    ]
   177	
   178	
   179	def test_support_is_strict_while_legacy_facade_eligibility_is_preserved(
   180	    tmp_path: Path,
   181	) -> None:
   182	    timeline_path, assets_path = _write_inputs(tmp_path)
   183	    source_probe = MediaProbe(
   184	        duration_seconds=2,
   185	        width=1920,
   186	        height=1080,
   187	        fps=30,
   188	        video_codec="h264",
   189	        pixel_format="yuv420p",
   190	        audio_codec="aac",
   191	        video_stream_present=True,
   192	        audio_stream_present=True,
   193	    )
   194	
   195	    with mock.patch.object(
   196	        ffmpeg,
   197	        "ffprobe_metadata_strict",
   198	        return_value=source_probe,
   199	    ):
   200	        report = ffmpeg.support(
   201	            _request(timeline_path, assets_path),
   202	            workspace=tmp_path,
   203	        )
   204	
   205	    assert report.supported is True
   206	    assert report.reasons == []
   207	    assert report.backend == ffmpeg.BACKEND_ID
   208	    assert report.features["audio_ownership"] == "rendered"
   209	    assert report.features["whole_media"] is True
   210	    assert ffmpeg.can_render_with_ffmpeg_media(timeline_path, assets_path) is True
   211	
   212	
   213	def test_support_rejects_non_media_timeline(tmp_path: Path) -> None:
   214	    timeline_path, assets_path = _write_inputs(
   215	        tmp_path,
   216	        timeline_data=_text_timeline(),
   217	    )
   218	
   219	    report = ffmpeg.support(_request(timeline_path, assets_path), workspace=tmp_path)
   220	
   221	    assert report.supported is False
   222	    assert any("unsupported clip kind" in reason for reason in report.reasons)
   223	    assert ffmpeg.can_render_with_ffmpeg_media(timeline_path, assets_path) is False
   224	
   225	
   226	def test_raw_support_adapter_writes_authoritative_report(tmp_path: Path) -> None:
   227	    timeline_path, assets_path = _write_inputs(tmp_path, registered=False)
   228	    request_path = tmp_path / "request.json"
   229	    result_path = tmp_path / "result.json"
   230	    request_path.write_text(
   231	        json.dumps(_request(timeline_path, assets_path).to_dict()),
   232	        encoding="utf-8",
   233	    )
   234	
   235	    assert ffmpeg.main(
   236	        [
   237	            "support",
   238	            "--request",
   239	            str(request_path),
   240	            "--result",
   241	            str(result_path),
   242	        ]
   243	    ) == 0
   244	
   245	    report = SupportReport.from_dict(
   246	        json.loads(result_path.read_text(encoding="utf-8"))
   247	    )
   248	    assert report.supported is False
   249	    assert report.alternatives == ["rendering.remotion"]
   250	    assert report.backend == ffmpeg.BACKEND_ID
   251	
   252	
   253	def test_manifest_command_dispatches_from_pack_root(tmp_path: Path) -> None:
   254	    timeline_path, assets_path = _write_inputs(tmp_path, registered=False)
   255	    request_path = tmp_path / "transport-request.json"
   256	    result_path = tmp_path / "transport-result.json"
   257	    request_payload = _request(timeline_path, assets_path).to_dict()
   258	    request_payload["backend_config"] = {}
   259	    request_path.write_text(
   260	        json.dumps(request_payload),
   261	        encoding="utf-8",
   262	    )
   263	
   264	    report = CommandTransport(ffmpeg.BACKEND_ID).run(
   265	        "support",
   266	        ("python3", "run.py"),
   267	        request_path=request_path,
   268	        result_path=result_path,
   269	        cwd=ROOT / "astrid" / "packs" / "rendering",
   270	    )
   271	
   272	    assert isinstance(report, SupportReport)
   273	    assert report.backend == ffmpeg.BACKEND_ID
   274	    assert report.supported is False
   275	
   276	
   277	def test_build_render_command_is_pure_and_preserves_stream_copy(
   278	    tmp_path: Path,
   279	) -> None:
   280	    timeline_path, assets_path = _write_inputs(tmp_path)
   281	    request = _request(timeline_path, assets_path)
   282	    inputs = command.resolve_render_command_inputs(request, tmp_path)
   283	
   284	    # Stream-copy is gated on probe evidence; the pure builder emits the copy
   285	    # path only when the caller passes stream_copy_allowed=True. A placeholder
   286	    # source (no real probe) must default to re-encoding.
   287	    argv = command.build_render_command(request, tmp_path)
   288	    assert argv[argv.index("-c:v") + 1] == "libx264"
   289	
   290	    copy_argv = command.build_render_command_from_inputs(
   291	        dataclasses.replace(inputs, stream_copy_allowed=True)
   292	    )
   293	    assert copy_argv[copy_argv.index("-c:v") + 1] == "copy"
   294	    assert copy_argv[-1] == str((tmp_path / "outputs" / "result.mp4").resolve())
   295	    assert not (tmp_path / "outputs").exists()
   296	
   297	
   298	def test_build_render_command_encodes_visual_only_without_synthesizing_silence(
   299	    tmp_path: Path,
   300	) -> None:
   301	    timeline_path, assets_path = _write_inputs(
   302	        tmp_path,
   303	        timeline_data=_media_timeline(include_audio=False),
   304	        source_resolution="1280x720",
   305	    )
   306	
   307	    argv = command.build_render_command(
   308	        _request(timeline_path, assets_path),
   309	        tmp_path,
   310	    )
   311	
   312	    filters = argv[argv.index("-filter_complex") + 1]
   313	    assert (
   314	        "[0:v]trim=start=0.000000:end=2.000000,setpts=PTS-STARTPTS,"
   315	        "scale=1920:1080:force_original_aspect_ratio=decrease,"
   316	        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
   317	        "fps=30,format=yuv420p[v0]" in filters
   318	    )
   319	    assert "[v0]concat=n=1:v=1:a=0[vout]" in filters
   320	    assert "anullsrc" not in filters
   321	    assert "[aout]" not in argv
   322	    assert "-c:a" not in argv
   323	    assert "-an" in argv
   324	    assert argv[argv.index("-c:v") + 1] == "libx264"
   325	    assert argv[argv.index("-preset") + 1] == "veryfast"
   326	    assert argv[argv.index("-crf") + 1] == "20"
   327	
   328	
   329	def test_protocol_render_returns_explicit_rendered_audio_result(
   330	    tmp_path: Path,

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '400,700p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/rendering/artifacts.py | sed -n '260,470p'; nl -ba astrid/core/rendering/artifacts.py | sed -n '650,735p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/rendering/profile.py | sed -n '160,310p'; nl -ba astrid/core/media.py | sed -n '20,70p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '860,930p'; rg -n \"requested profile|video_profile|video_level|time_base|stream_copy\" tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 157ms:
   400	                }
   401	                for event in spec.events
   402	            ],
   403	            "event_count": len(spec.events),
   404	            "fps": spec.fps,
   405	            "frame_count": spec.total_frames,
   406	            "marker_sha256": spec.marker_sha256,
   407	        }
   408	        output = publish_render_result(
   409	            rendered_video,
   410	            provenance,
   411	            out_path=out_path,
   412	            sidecar_path=remotion_backend._render_provenance_sidecar_path(
   413	                out_path
   414	            ),
   415	            previous_outputs=previous_outputs,
   416	        )
   417	
   418	    audit = AuditContext.from_env()
   419	    if audit is not None:
   420	        timeline_id = audit.register_asset(
   421	            kind="timeline",
   422	            path=timeline_path,
   423	            label="Audio-reactive render timeline",
   424	            stage="render_ffmpeg_audio_reactive_colour",
   425	        )
   426	        assets_id = audit.register_asset(
   427	            kind="assets_registry",
   428	            path=assets_path,
   429	            label="Audio-reactive asset registry",
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
   621	                if key != "id"
   622	            }
   623	        video = VideoArtifact.from_file(
   624	            path=output_path,
   625	            workspace_root=workspace,
   626	            profile=declared_profile,
   627	            duration_frames=duration_frames,
   628	            audio=ownership,
   629	        )
   630	        result = RenderResult(
   631	            schema_version=SCHEMA_VERSION,
   632	            video=video,
   633	            audio_ownership=ownership,
   634	            backend_fragments={
   635	                BACKEND_ID: fragment
   636	            },
   637	            normalization=[],
   638	            logs=[],
   639	            metadata=request.metadata,
   640	        )
   641	        validate_render_result(
   642	            result,
   643	            expected_profile=declared_profile,
   644	            workspace_root=workspace,
   645	        )
   646	        return result
   647	    except BaseException:
   648	        output_path.unlink(missing_ok=True)
   649	        raise
   650	
   651	
   652	def _load_request(path: Path) -> RenderRequest:
   653	    payload = json.loads(path.read_text(encoding="utf-8"))
   654	    if not isinstance(payload, Mapping):
   655	        raise TypeError("render request must contain a JSON object")
   656	    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)
   657	
   658	
   659	def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
   660	    if isinstance(exc, RendererException):
   661	        error_kind = exc.error.kind
   662	        message = exc.error.message
   663	        recovery = exc.error.recovery_command
   664	        details = exc.error.details
   665	    else:
   666	        error_kind = kind
   667	        message = str(exc) or type(exc).__name__
   668	        recovery = None
   669	        details = {"error_type": type(exc).__name__}
   670	    error = make_renderer_error(
   671	        error_kind,
   672	        backend=BACKEND_ID,
   673	        message=message,
   674	        recovery_command=recovery,
   675	        details=details,
   676	    )
   677	    write_json_atomic(result_path, error.to_dict())
   678	
   679	
   680	def main(argv: Sequence[str] | None = None) -> int:
   681	    parser = argparse.ArgumentParser()
   682	    parser.add_argument("verb", choices=("render", "support"))
   683	    parser.add_argument("--request", type=Path, required=True)
   684	    parser.add_argument("--result", type=Path, required=True)
   685	    args = parser.parse_args(argv)
   686	
   687	    try:
   688	        request_path = args.request.resolve(strict=True)
   689	        result_path = args.result.resolve()
   690	        if request_path == result_path:
   691	            raise ValueError("--request and --result must be different paths")
   692	        request = _load_request(request_path)
   693	    except (
   694	        OSError,
   695	        ValueError,
   696	        TypeError,
   697	        json.JSONDecodeError,
   698	        RendererException,
   699	    ) as exc:
   700	        _write_failure(args.result.resolve(), exc, kind="protocol")

 succeeded in 419ms:
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

 succeeded in 559ms:
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
   650	    if not isinstance(ownership, AudioOwnership):
   651	        try:
   652	            ownership = AudioOwnership(ownership)
   653	        except (TypeError, ValueError):
   654	            _invalid(
   655	                "audio_ownership_mismatch",
   656	                "render result has an invalid audio_ownership value",
   657	                actual=str(result.audio_ownership),
   658	            )
   659	    if video.audio is not ownership:
   660	        _invalid(
   661	            "audio_ownership_mismatch",
   662	            "video.audio does not match result audio_ownership",
   663	            result_audio=ownership.value,
   664	            video_audio=video.audio.value if isinstance(video.audio, AudioOwnership) else None,
   665	        )
   666	    return video, ownership
   667	
   668	
   669	def validate_render_result(
   670	    result: RenderResult | Mapping[str, Any],
   671	    *,
   672	    expected_profile: RenderProfile | Mapping[str, Any],
   673	    workspace_root: str | Path,
   674	) -> RenderResult:
   675	    """Validate one renderer result before finalization or publication.
   676	
   677	    Every artifact path is resolved inside the invocation workspace, every
   678	    digest is recomputed, and the primary media is strictly probed.  On
   679	    success the same :class:`RenderResult` object is returned, preserving its
   680	    named attachments exactly as supplied.
   681	    """
   682	
   683	    render_result = _coerce_result(result)
   684	    expected = _coerce_expected_profile(expected_profile)
   685	    root = _workspace_root(workspace_root)
   686	    video, ownership = _validate_result_shape(render_result)
   687	    declared = _validate_declared_profile(video.profile)
   688	    _compare_declared_to_expected(declared, expected, ownership)
   689	
   690	    video_path = _contained_regular_file(video.path, root=root, label="primary video path")
   691	    try:
   692	        output_size = video_path.stat().st_size
   693	    except OSError as exc:
   694	        _invalid(
   695	            "missing_artifact",
   696	            "cannot inspect primary video size",
   697	            path=video.path,
   698	            error_type=type(exc).__name__,
   699	        )
   700	    if output_size <= 0:
   701	        _invalid(
   702	            "empty_artifact",
   703	            "renderer primary video is empty",
   704	            path=video.path,
   705	            size=output_size,
   706	        )
   707	    _verify_hash(video_path, video.sha256, label="primary video")
   708	
   709	    attachments = video.attachments
   710	    if not isinstance(attachments, Mapping):
   711	        _invalid(
   712	            "invalid_attachment",
   713	            "video attachments must be a named mapping",
   714	            received_type=type(attachments).__name__,
   715	        )
   716	    for name, attachment in attachments.items():
   717	        _validate_attachment(name, attachment, root=root)
   718	
   719	    try:
   720	        probe = ffprobe_metadata_strict(video_path)
   721	    except (MediaProbeError, OSError, RuntimeError, ValueError) as exc:
   722	        _invalid(
   723	            "probe_failed",
   724	            f"strict media probe failed for renderer output: {exc}",
   725	            path=video.path,
   726	            error_type=type(exc).__name__,
   727	        )
   728	    _probe_required_video(probe)
   729	    _compare_probe_to_profile(probe, declared, label="the declared profile", compare_audio=False)
   730	    _compare_probe_to_profile(probe, expected, label="the canonical profile", compare_audio=False)
   731	    _validate_audio(
   732	        probe,
   733	        ownership=ownership,
   734	        declared=declared,
   735	        expected=expected,

 succeeded in 510ms:
   860	    if min_free_value is None:
   861	        min_free_gb = None
   862	    elif isinstance(min_free_value, bool) or not isinstance(min_free_value, (int, float)):
   863	        raise TypeError("min_free_gb must be a number or null")
   864	    else:
   865	        min_free_gb = float(min_free_value)
   866	        if min_free_gb < 0:
   867	            raise ValueError("min_free_gb must not be negative")
   868	
   869	    return _RenderSettings(
   870	        project_dir=project_dir,
   871	        composition_id=composition_value,
   872	        theme_path=theme_path,
   873	        min_free_gb=min_free_gb,
   874	    )
   875	
   876	
   877	def _load_registry_mapping(path: Path | None) -> dict[str, Any]:
   878	    if path is None:
   879	        return {"assets": {}}
   880	    data = json.loads(path.read_text(encoding="utf-8"))
   881	    if not isinstance(data, dict) or not isinstance(data.get("assets"), dict):
   882	        raise ValueError("assets registry must be an object containing an assets object")
   883	    return data
   884	
   885	
   886	def _canonical_profile(
   887	    timeline_path: Path,
   888	    assets_data: Mapping[str, Any],
   889	    settings: _RenderSettings,
   890	) -> RenderProfile:
   891	    fallback_theme = settings.theme_path or (
   892	        WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
   893	    )
   894	    active_theme = _resolved_theme_for_render(timeline_path, fallback_theme)
   895	    return resolve_render_profile(
   896	        timeline_path,
   897	        assets_data,
   898	        theme=active_theme,
   899	        themes_root=REPO_ROOT / "themes",
   900	    )
   901	
   902	
   903	def _profile_mismatches(
   904	    requested: RenderProfile,
   905	    canonical: RenderProfile,
   906	) -> list[str]:
   907	    requested_data = requested.to_dict()
   908	    canonical_data = canonical.to_dict()
   909	    mismatches: list[str] = []
   910	    for field, expected in canonical_data.items():
   911	        if field == "duration_tolerance":
   912	            continue
   913	        actual = requested_data[field]
   914	        if actual != expected:
   915	            mismatches.append(f"{field}={actual!r} (requires {expected!r})")
   916	    return mismatches
   917	
   918	
   919	def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
   920	    """Return request-specific evidence for the timeline Remotion can render."""
   921	
   922	    reasons: list[str] = []
   923	    features: dict[str, bool | str] = {
   924	        "timeline_composition": True,
   925	        "full_timeline": True,
   926	        "windows": False,
   927	        "effects": True,
   928	        "asset_serving": "invocation-scoped",
   929	    }
   930	    try:
tests/packs/rendering/test_ffmpeg_support.py:184:    assert report.features["stream_copy"] is True
tests/packs/rendering/test_ffmpeg_support.py:451:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py:454:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:455:        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py:571:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py:573:        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py:574:        video_level="40",
tests/packs/rendering/test_ffmpeg_backend.py:136:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py:139:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:140:        video_level="4.0",
tests/packs/rendering/test_ffmpeg_backend.py:277:def test_build_render_command_is_pure_and_preserves_stream_copy(
tests/packs/rendering/test_ffmpeg_backend.py:285:    # path only when the caller passes stream_copy_allowed=True. A placeholder
tests/packs/rendering/test_ffmpeg_backend.py:291:        dataclasses.replace(inputs, stream_copy_allowed=True)
tests/packs/rendering/test_ffmpeg_backend.py:346:        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py:348:        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py:349:        video_level="40",

exec
/bin/zsh -lc "nl -ba tests/packs/rendering/test_ffmpeg_support.py | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'git show --stat --oneline 58473c3a && git show --format=fuller --no-patch 58473c3a' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 22ms:
     1	from __future__ import annotations
     2	
     3	import copy
     4	import importlib
     5	import json
     6	import subprocess
     7	from pathlib import Path
     8	from unittest import mock
     9	
    10	import pytest
    11	
    12	from astrid.core.media import MediaProbe
    13	from astrid.core.rendering.contracts import (
    14	    AudioOwnership,
    15	    FrameWindow,
    16	    RenderRequest,
    17	    RenderResult,
    18	    SCHEMA_VERSION,
    19	)
    20	from astrid.packs.rendering.backends.ffmpeg import audio_reactive_colour
    21	from astrid.packs.rendering.backends.ffmpeg import command
    22	from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg
    23	from astrid.packs.rendering.backends.ffmpeg.support import support as evaluate_support
    24	
    25	
    26	support_module = importlib.import_module(
    27	    "astrid.packs.rendering.backends.ffmpeg.support"
    28	)
    29	
    30	
    31	def _timeline(*, include_audio: bool = True, duration: float = 4.0) -> dict:
    32	    tracks = [{"id": "v", "kind": "visual", "label": "Video"}]
    33	    clips = [
    34	        {
    35	            "id": "video",
    36	            "at": 0,
    37	            "track": "v",
    38	            "clipType": "media",
    39	            "asset": "video",
    40	            "from": 0,
    41	            "to": duration,
    42	            "speed": 1,
    43	            "volume": 0,
    44	        }
    45	    ]
    46	    if include_audio:
    47	        tracks.append(
    48	            {
    49	                "id": "a",
    50	                "kind": "audio",
    51	                "label": "Audio",
    52	                "volume": 0.5,
    53	            }
    54	        )
    55	        clips.append(
    56	            {
    57	                "id": "audio",
    58	                "at": 0,
    59	                "track": "a",
    60	                "clipType": "media",
    61	                "asset": "audio",
    62	                "from": 0,
    63	                "to": duration,
    64	                "speed": 1,
    65	                "volume": 0.4,
    66	            }
    67	        )
    68	    return {
    69	        "theme": "banodoco-default",
    70	        "theme_overrides": {
    71	            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
    72	        },
    73	        "tracks": tracks,
    74	        "clips": clips,
    75	    }
    76	
    77	
    78	def _assets(tmp_path: Path, *, duration: float = 4.0) -> dict:
    79	    return {
    80	        "assets": {
    81	            "video": {
    82	                "file": "video.mp4",
    83	                "type": "video/mp4",
    84	                "duration": duration,
    85	                "resolution": "640x360",
    86	                "fps": 30,
    87	            },
    88	            "audio": {
    89	                "file": "audio.wav",
    90	                "type": "audio/wav",
    91	                "duration": duration,
    92	            },
    93	        }
    94	    }
    95	
    96	
    97	def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
    98	    return MediaProbe(
    99	        duration_seconds=duration,
   100	        width=640,
   101	        height=360,
   102	        fps=30,
   103	        resolution="640x360",
   104	        video_codec="h264",
   105	        pixel_format="yuv420p",
   106	        audio_codec="aac" if audio else None,
   107	        video_stream_present=True,
   108	        audio_stream_present=audio,
   109	    )
   110	
   111	
   112	def _audio_probe(*, duration: float = 4.0, present: bool = True) -> MediaProbe:
   113	    return MediaProbe(
   114	        duration_seconds=duration,
   115	        audio_codec="pcm_s16le" if present else None,
   116	        video_stream_present=False,
   117	        audio_stream_present=present,
   118	    )
   119	
   120	
   121	def _request(
   122	    tmp_path: Path,
   123	    *,
   124	    audio: AudioOwnership | None = None,
   125	    window: FrameWindow | None = None,
   126	) -> RenderRequest:
   127	    return RenderRequest(
   128	        schema_version=SCHEMA_VERSION,
   129	        timeline_path=str(tmp_path / "timeline.json"),
   130	        assets_registry_path=str(tmp_path / "assets.json"),
   131	        output_name="result.mp4",
   132	        window=window,
   133	        audio=audio,
   134	        backend_config={ffmpeg.BACKEND_ID: {}},
   135	    )
   136	
   137	
   138	def _evaluate(
   139	    tmp_path: Path,
   140	    timeline_data: dict,
   141	    assets: dict,
   142	    *,
   143	    probes: dict[str, MediaProbe] | None = None,
   144	    missing_files: set[str] | None = None,
   145	    which=None,
   146	    request: RenderRequest | None = None,
   147	):
   148	    missing = missing_files or set()
   149	    for entry in assets.get("assets", {}).values():
   150	        file_value = entry.get("file")
   151	        if isinstance(file_value, str) and file_value not in missing:
   152	            (tmp_path / file_value).write_bytes(b"source")
   153	    (tmp_path / "timeline.json").write_text(
   154	        json.dumps(timeline_data),
   155	        encoding="utf-8",
   156	    )
   157	    (tmp_path / "assets.json").write_text(json.dumps(assets), encoding="utf-8")
   158	    probe_map = probes or {
   159	        "video.mp4": _video_probe(),
   160	        "audio.wav": _audio_probe(),
   161	    }
   162	
   163	    return evaluate_support(
   164	        request or _request(tmp_path),
   165	        timeline_data,
   166	        assets,
   167	        probe=lambda path: probe_map[Path(path).name],
   168	        which=which or (lambda binary: f"/usr/bin/{binary}"),
   169	    )
   170	
   171	
   172	def _build_command(tmp_path: Path, timeline_data: dict, assets: dict) -> list[str]:
   173	    _evaluate(tmp_path, timeline_data, assets)
   174	    return command.build_render_command(_request(tmp_path), tmp_path)
   175	
   176	
   177	def test_supported_report_exposes_request_specific_evidence(tmp_path: Path) -> None:
   178	    report = _evaluate(tmp_path, _timeline(), _assets(tmp_path))
   179	
   180	    assert report.supported is True
   181	    assert report.reasons == []
   182	    assert report.alternatives == []
   183	    assert report.features["whole_media"] is True
   184	    assert report.features["stream_copy"] is True
   185	    assert report.features["audio_reactive_colour"] is False
   186	    assert report.features["audio_ownership"] == "rendered"
   187	
   188	
   189	@pytest.mark.parametrize(
   190	    ("case", "reason"),
   191	    [
   192	        ("unknown_track_kind", "unsupported kind"),
   193	        ("unknown_clip_kind", "unsupported clip kind"),
   194	        ("unknown_track", "unknown track"),
   195	        ("invalid_bounds", "positive source bounds"),
   196	        ("source_bound", "exceeds"),
   197	        ("visual_gap", "Visual gap"),
   198	        ("visual_overlap", "Visual overlap"),
   199	        ("speed", "unsupported speed"),
   200	        ("transform", "unsupported transforms"),
   201	        ("track_transform", "transform semantics"),
   202	        ("crop", "unsupported crop"),
   203	        ("effects", "unsupported effects"),
   204	        ("transition", "unsupported transition"),
   205	        ("opacity", "non-default opacity"),
   206	        ("discarded_visual_audio", "embedded audio"),
   207	        ("overlapping_audio", "Overlapping audio"),
   208	        ("fade", "audio fades"),
   209	        ("missing_source", "source is missing"),
   210	        ("missing_video_stream", "no video stream"),
   211	        ("missing_audio_stream", "no audio stream"),
   212	        ("missing_binary", "required binary is unavailable"),
   213	        ("window", "frame windows"),
   214	    ],
   215	)
   216	def test_support_fails_closed_for_every_unsupported_semantic(
   217	    tmp_path: Path,
   218	    case: str,
   219	    reason: str,
   220	) -> None:

exec
/bin/zsh -lc 'rg -n "build_render_command_from_data|TOCTOU|reload|mutation|transport_selected|ASTRID_RENDER_BACKEND|rendering.ffmpeg-finalizer" tests/packs/rendering tests/core/rendering | head -n 260' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba tests/packs/rendering/test_ffmpeg_support.py | sed -n '430,640p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 76ms:
   430	
   431	    assert report.supported is True
   432	    assert report.features["audio_ownership"] == "passthrough"
   433	
   434	
   435	def test_visual_only_protocol_result_declares_none(tmp_path: Path) -> None:
   436	    timeline_data = _timeline(include_audio=False)
   437	    assets = _assets(tmp_path)
   438	    del assets["assets"]["audio"]
   439	    _evaluate(
   440	        tmp_path,
   441	        timeline_data,
   442	        assets,
   443	        probes={"video.mp4": _video_probe()},
   444	    )
   445	    probe = MediaProbe(
   446	        duration_seconds=4,
   447	        width=640,
   448	        height=360,
   449	        fps=30,
   450	        fps_rational=(30, 1),
   451	        time_base=(1, 15360),
   452	        resolution="640x360",
   453	        video_codec="h264",
   454	        video_profile="High",
   455	        video_level="40",
   456	        pixel_format="yuv420p",
   457	        container="mp4",
   458	        duration_rational=(4, 1),
   459	        video_stream_present=True,
   460	        audio_stream_present=False,
   461	    )
   462	    seen: dict[str, list[str]] = {}
   463	
   464	    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
   465	        seen["argv"] = argv
   466	        output = Path(argv[-1])
   467	        output.parent.mkdir(parents=True, exist_ok=True)
   468	        output.write_bytes(b"video")
   469	        return subprocess.CompletedProcess(argv, 0)
   470	
   471	    with (
   472	        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
   473	        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", return_value=probe),
   474	        mock.patch.object(ffmpeg.subprocess, "run", side_effect=fake_run),
   475	        mock.patch.object(
   476	            ffmpeg.remotion_backend,
   477	            "_render_provenance_payload",
   478	            return_value={"engine": "ffmpeg"},
   479	        ),
   480	        mock.patch.object(ffmpeg, "validate_render_result"),
   481	    ):
   482	        result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)
   483	
   484	    assert result.audio_ownership is AudioOwnership.NONE
   485	    assert result.video.audio is AudioOwnership.NONE
   486	    assert result.video.profile.has_audio is False
   487	    assert "-an" in seen["argv"]
   488	    assert "-c:a" not in seen["argv"]
   489	
   490	
   491	def _reactive_timeline() -> dict:
   492	    return {
   493	        "theme": "banodoco-default",
   494	        "theme_overrides": {
   495	            "visual": {"canvas": {"width": 640, "height": 360, "fps": 30}}
   496	        },
   497	        "tracks": [
   498	            {"id": "v", "kind": "visual", "label": "Colour"},
   499	            {
   500	                "id": "a",
   501	                "kind": "audio",
   502	                "label": "Audio",
   503	                "volume": 0.5,
   504	            },
   505	        ],
   506	        "clips": [
   507	            {
   508	                "id": "colour",
   509	                "at": 0,
   510	                "track": "v",
   511	                "clipType": "audio-reactive-colour",
   512	                "hold": 1,
   513	                "params": {
   514	                    "schemaVersion": 1,
   515	                    "initialColor": "#102030",
   516	                    "events": [
   517	                        {"id": "one", "frame": 3, "color": "#D47795"},
   518	                        {"id": "two", "frame": 8, "color": "#26A7D0"},
   519	                    ],
   520	                },
   521	            },
   522	            {
   523	                "id": "audio",
   524	                "at": 0,
   525	                "track": "a",
   526	                "clipType": "media",
   527	                "asset": "audio",
   528	                "from": 0,
   529	                "to": 1,
   530	                "volume": 0.4,
   531	            },
   532	        ],
   533	    }
   534	
   535	
   536	def test_audio_reactive_support_gain_and_protocol_provenance_fragments(
   537	    tmp_path: Path,
   538	) -> None:
   539	    timeline_data = _reactive_timeline()
   540	    assets = {
   541	        "assets": {
   542	            "audio": {
   543	                "file": "audio.wav",
   544	                "type": "audio/wav",
   545	                "duration": 1,
   546	            }
   547	        }
   548	    }
   549	    report = _evaluate(
   550	        tmp_path,
   551	        timeline_data,
   552	        assets,
   553	        probes={"audio.wav": _audio_probe(duration=1)},
   554	    )
   555	    spec = audio_reactive_colour.match_and_validate(
   556	        timeline_data,
   557	        assets,
   558	        tmp_path / "assets.json",
   559	    )
   560	
   561	    assert report.supported is True
   562	    assert report.features["audio_reactive_colour"] is True
   563	    assert report.features["specialization"] == "audio-reactive-colour/v1"
   564	    assert spec is not None
   565	    assert spec.audio_volume == pytest.approx(0.2)
   566	
   567	    output_probe = MediaProbe(
   568	        width=640,
   569	        height=360,
   570	        fps_rational=(30, 1),
   571	        time_base=(1, 15360),
   572	        video_codec="h264",
   573	        video_profile="High",
   574	        video_level="40",
   575	        pixel_format="yuv420p",
   576	        audio_codec="aac",
   577	        audio_sample_rate=48000,
   578	        audio_channel_layout="stereo",
   579	        audio_channels=2,
   580	        container="mp4",
   581	        duration_rational=(1, 1),
   582	        video_stream_present=True,
   583	        audio_stream_present=True,
   584	    )
   585	
   586	    def fake_render(
   587	        _spec: audio_reactive_colour.AudioReactiveColourSpec,
   588	        output: Path,
   589	    ) -> Path:
   590	        output.parent.mkdir(parents=True, exist_ok=True)
   591	        output.write_bytes(b"video")
   592	        return output
   593	
   594	    def probe(path: Path) -> MediaProbe:
   595	        return (
   596	            _audio_probe(duration=1)
   597	            if Path(path).name == "audio.wav"
   598	            else output_probe
   599	        )
   600	
   601	    with (
   602	        mock.patch.object(support_module.shutil, "which", return_value="/usr/bin/tool"),
   603	        mock.patch.object(ffmpeg, "ffprobe_metadata_strict", side_effect=probe),
   604	        mock.patch.object(audio_reactive_colour, "render", side_effect=fake_render),
   605	        mock.patch.object(
   606	            ffmpeg.remotion_backend,
   607	            "_render_provenance_payload",
   608	            return_value={"engine": "ffmpeg"},
   609	        ),
   610	        mock.patch.object(ffmpeg, "validate_render_result"),
   611	    ):
   612	        result = ffmpeg._protocol_render(_request(tmp_path), workspace=tmp_path)
   613	
   614	    assert isinstance(result, RenderResult)
   615	    assert result.audio_ownership is AudioOwnership.RENDERED
   616	    fragment = result.backend_fragments[ffmpeg.BACKEND_ID]["specialization"]
   617	    assert fragment["id"] == "audio-reactive-colour/v1"
   618	    assert [marker["frame"] for marker in fragment["markers"]] == [3, 8]
   619	    assert fragment["event_count"] == 2
   620	    assert fragment["frame_count"] == 30
   621	    assert fragment["fps"] == 30
   622	    assert len(fragment["marker_sha256"]) == 64

 succeeded in 113ms:
tests/core/rendering/test_registry.py:214:    assert finalizers.get("rendering.ffmpeg-finalizer").manifest.name == "Fixture FFmpeg Finalizer"
tests/core/rendering/test_contracts.py:123:        id="rendering.ffmpeg-finalizer",
tests/core/rendering/test_contracts.py:126:        alias_chain=["ffmpeg-finalizer", "rendering.ffmpeg-finalizer"],
tests/core/rendering/test_contracts.py:129:        support_decision=_support("rendering.ffmpeg-finalizer"),
tests/core/rendering/test_contracts.py:216:        backend_config={"rendering.ffmpeg-finalizer": {"faststart": True}},
tests/core/rendering/test_contracts.py:671:        alias_chain=["finalizer", "rendering.ffmpeg-finalizer"],
tests/core/rendering/test_contracts.py:672:        override={"from": "acme.finalizer-2", "to": "rendering.ffmpeg-finalizer"},
tests/core/rendering/test_contracts.py:674:        support_decision=_support("rendering.ffmpeg-finalizer"),
tests/core/rendering/test_contracts.py:1123:    assert _finalizer().id == "rendering.ffmpeg-finalizer"
tests/packs/rendering/test_ffmpeg_finalizer.py:293:    assert manifest.id == "rendering.ffmpeg-finalizer"
tests/core/rendering/test_transport.py:107:        ("finalize", "result.json", "rendering.ffmpeg-finalizer", RenderResult),
tests/core/rendering/fixtures/v1/plan.json:60:    "id": "rendering.ffmpeg-finalizer",
tests/core/rendering/fixtures/v1/plan.json:77:      "backend": "rendering.ffmpeg-finalizer",
tests/core/rendering/fixtures/v1/finalize.json:62:      "id": "rendering.ffmpeg-finalizer",
tests/core/rendering/fixtures/v1/finalize.json:79:        "backend": "rendering.ffmpeg-finalizer",
tests/core/rendering/fixtures/v1/finalize.json:142:    "rendering.ffmpeg-finalizer": {}
tests/packs/rendering/test_builtin_registration.py:164:        ffmpeg_finalizer = finalizers.inspect("rendering.ffmpeg-finalizer")
tests/packs/rendering/test_builtin_registration.py:168:            finalizers.get("rendering.ffmpeg-finalizer"),
tests/packs/rendering/test_builtin_registration.py:178:        "rendering.ffmpeg-finalizer",

 succeeded in 177ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
58473c3a batch3-rework2: oracle re-review issues 1-6 (env-authoritative launcher routing, remotion full render-profile support + manifest audio, ffmpeg time_base support check, audio-reactive 48kHz, whole-source stream-copy gate incl codec/pixel + supported required, TOCTOU-free legacy facade via preloaded-data builder)
 .oracle/checkins/batch-3-r1.md                     | 20991 +++++++++++++++++++
 .../backends/ffmpeg/audio_reactive_colour.py       |     3 +-
 astrid/packs/rendering/backends/ffmpeg/command.py  |    33 +-
 astrid/packs/rendering/backends/ffmpeg/run.py      |     6 +-
 astrid/packs/rendering/backends/ffmpeg/support.py  |     3 +
 .../rendering/backends/remotion/renderer.yaml      |     1 -
 astrid/packs/rendering/backends/remotion/run.py    |     8 +-
 astrid/packs/rendering/run.py                      |     8 +-
 tests/packs/rendering/test_ffmpeg_backend.py       |     1 +
 tests/packs/rendering/test_ffmpeg_support.py       |     1 +
 10 files changed, 21047 insertions(+), 8 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 58473c3ae3390738771898127c73c09230a3cfd8
Author:     POM <peter@omalley.io>
AuthorDate: Wed Aug 12 14:00:27 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Wed Aug 12 14:00:27 2026 +0200

    batch3-rework2: oracle re-review issues 1-6 (env-authoritative launcher routing, remotion full render-profile support + manifest audio, ffmpeg time_base support check, audio-reactive 48kHz, whole-source stream-copy gate incl codec/pixel + supported required, TOCTOU-free legacy facade via preloaded-data builder)

exec
/bin/zsh -lc 'rg -n -C 6 "ASTRID_RENDER_BACKEND|finalizer namespace|backend_config.*ffmpeg-finalizer|transport.*authoritative|rendering.remotion.*finalizer" tests astrid | head -n 300' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'rg -n -C 8 "always-rendered|requested profile is not produced|audio_ownership.*rendered|90000|visual-only.*profile|audio_codec.*aac" tests/packs/rendering/test_remotion* | head -n 360' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 19ms:
tests/packs/rendering/test_remotion_backend.py-121-
tests/packs/rendering/test_remotion_backend.py-122-    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
tests/packs/rendering/test_remotion_backend.py-123-        report = remotion.support(request, workspace=tmp_path)
tests/packs/rendering/test_remotion_backend.py-124-
tests/packs/rendering/test_remotion_backend.py-125-    assert report.supported is True
tests/packs/rendering/test_remotion_backend.py-126-    assert report.reasons == []
tests/packs/rendering/test_remotion_backend.py-127-    assert report.backend == remotion.BACKEND_ID
tests/packs/rendering/test_remotion_backend.py-128-    assert report.features["timeline_composition"] is True
tests/packs/rendering/test_remotion_backend.py:129:    assert report.features["audio_ownership"] == "rendered"
tests/packs/rendering/test_remotion_backend.py-130-
tests/packs/rendering/test_remotion_backend.py-131-
tests/packs/rendering/test_remotion_backend.py-132-def test_support_rejects_native_window_with_actionable_reason(tmp_path: Path) -> None:
tests/packs/rendering/test_remotion_backend.py-133-    timeline_path, assets_path = _write_inputs(tmp_path)
tests/packs/rendering/test_remotion_backend.py-134-    project = _write_project(tmp_path)
tests/packs/rendering/test_remotion_backend.py-135-    request = _request(
tests/packs/rendering/test_remotion_backend.py-136-        timeline_path,
tests/packs/rendering/test_remotion_backend.py-137-        assets_path,

exec
/bin/zsh -lc 'rg -n -C 8 "from_data|strict support|mutat|reload|same mappings|TOCTOU|visual audio" tests/packs/rendering/test_ffmpeg* tests/packs/test_audio_render.py | head -n 400' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
exec
/bin/zsh -lc 'rg -n -C 8 "profile_support|requested profile|time_base.*not produced|video_profile.*not produced|video_level.*not produced|stream_copy.*codec|pixel_format" tests/packs/rendering/test_ffmpeg* | head -n 420' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 86ms:
tests/packs/rendering/test_ffmpeg_support.py-97-def _video_probe(*, audio: bool = False, duration: float = 4.0) -> MediaProbe:
tests/packs/rendering/test_ffmpeg_support.py-98-    return MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-99-        duration_seconds=duration,
tests/packs/rendering/test_ffmpeg_support.py-100-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-101-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-102-        fps=30,
tests/packs/rendering/test_ffmpeg_support.py-103-        resolution="640x360",
tests/packs/rendering/test_ffmpeg_support.py-104-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py:105:        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-106-        audio_codec="aac" if audio else None,
tests/packs/rendering/test_ffmpeg_support.py-107-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_support.py-108-        audio_stream_present=audio,
tests/packs/rendering/test_ffmpeg_support.py-109-    )
tests/packs/rendering/test_ffmpeg_support.py-110-
tests/packs/rendering/test_ffmpeg_support.py-111-
tests/packs/rendering/test_ffmpeg_support.py-112-def _audio_probe(*, duration: float = 4.0, present: bool = True) -> MediaProbe:
tests/packs/rendering/test_ffmpeg_support.py-113-    return MediaProbe(
--
tests/packs/rendering/test_ffmpeg_support.py-448-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-449-        fps=30,
tests/packs/rendering/test_ffmpeg_support.py-450-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py-451-        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-452-        resolution="640x360",
tests/packs/rendering/test_ffmpeg_support.py-453-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py-454-        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py-455-        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py:456:        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-457-        container="mp4",
tests/packs/rendering/test_ffmpeg_support.py-458-        duration_rational=(4, 1),
tests/packs/rendering/test_ffmpeg_support.py-459-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_support.py-460-        audio_stream_present=False,
tests/packs/rendering/test_ffmpeg_support.py-461-    )
tests/packs/rendering/test_ffmpeg_support.py-462-    seen: dict[str, list[str]] = {}
tests/packs/rendering/test_ffmpeg_support.py-463-
tests/packs/rendering/test_ffmpeg_support.py-464-    def fake_run(argv: list[str], **_kwargs) -> subprocess.CompletedProcess[str]:
--
tests/packs/rendering/test_ffmpeg_support.py-567-    output_probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_support.py-568-        width=640,
tests/packs/rendering/test_ffmpeg_support.py-569-        height=360,
tests/packs/rendering/test_ffmpeg_support.py-570-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_support.py-571-        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_support.py-572-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_support.py-573-        video_profile="High",
tests/packs/rendering/test_ffmpeg_support.py-574-        video_level="40",
tests/packs/rendering/test_ffmpeg_support.py:575:        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_support.py-576-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_support.py-577-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_support.py-578-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_support.py-579-        audio_channels=2,
tests/packs/rendering/test_ffmpeg_support.py-580-        container="mp4",
tests/packs/rendering/test_ffmpeg_support.py-581-        duration_rational=(1, 1),
tests/packs/rendering/test_ffmpeg_support.py-582-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_support.py-583-        audio_stream_present=True,
--
tests/packs/rendering/test_ffmpeg_backend.py-133-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-134-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-135-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_backend.py-136-        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-137-        container="mp4",
tests/packs/rendering/test_ffmpeg_backend.py-138-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py-139-        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py-140-        video_level="4.0",
tests/packs/rendering/test_ffmpeg_backend.py:141:        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-142-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-143-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_backend.py-144-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_backend.py-145-    )
tests/packs/rendering/test_ffmpeg_backend.py-146-
tests/packs/rendering/test_ffmpeg_backend.py-147-
tests/packs/rendering/test_ffmpeg_backend.py-148-def test_manifest_registers_static_raw_command_backend() -> None:
tests/packs/rendering/test_ffmpeg_backend.py-149-    manifest_path = (
--
tests/packs/rendering/test_ffmpeg_backend.py-181-) -> None:
tests/packs/rendering/test_ffmpeg_backend.py-182-    timeline_path, assets_path = _write_inputs(tmp_path)
tests/packs/rendering/test_ffmpeg_backend.py-183-    source_probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_backend.py-184-        duration_seconds=2,
tests/packs/rendering/test_ffmpeg_backend.py-185-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-186-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-187-        fps=30,
tests/packs/rendering/test_ffmpeg_backend.py-188-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py:189:        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-190-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-191-        video_stream_present=True,
tests/packs/rendering/test_ffmpeg_backend.py-192-        audio_stream_present=True,
tests/packs/rendering/test_ffmpeg_backend.py-193-    )
tests/packs/rendering/test_ffmpeg_backend.py-194-
tests/packs/rendering/test_ffmpeg_backend.py-195-    with mock.patch.object(
tests/packs/rendering/test_ffmpeg_backend.py-196-        ffmpeg,
tests/packs/rendering/test_ffmpeg_backend.py-197-        "ffprobe_metadata_strict",
--
tests/packs/rendering/test_ffmpeg_backend.py-342-    probe = MediaProbe(
tests/packs/rendering/test_ffmpeg_backend.py-343-        width=1920,
tests/packs/rendering/test_ffmpeg_backend.py-344-        height=1080,
tests/packs/rendering/test_ffmpeg_backend.py-345-        fps_rational=(30, 1),
tests/packs/rendering/test_ffmpeg_backend.py-346-        time_base=(1, 15360),
tests/packs/rendering/test_ffmpeg_backend.py-347-        video_codec="h264",
tests/packs/rendering/test_ffmpeg_backend.py-348-        video_profile="High",
tests/packs/rendering/test_ffmpeg_backend.py-349-        video_level="40",
tests/packs/rendering/test_ffmpeg_backend.py:350:        pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_backend.py-351-        audio_codec="aac",
tests/packs/rendering/test_ffmpeg_backend.py-352-        audio_sample_rate=48000,
tests/packs/rendering/test_ffmpeg_backend.py-353-        audio_channel_layout="stereo",
tests/packs/rendering/test_ffmpeg_backend.py-354-        audio_channels=2,
tests/packs/rendering/test_ffmpeg_backend.py-355-        container="mp4",
tests/packs/rendering/test_ffmpeg_backend.py-356-        format_name="mov,mp4",
tests/packs/rendering/test_ffmpeg_backend.py-357-        duration_rational=(2, 1),
tests/packs/rendering/test_ffmpeg_backend.py-358-        video_stream_present=True,
--
tests/packs/rendering/test_ffmpeg_finalizer.py-41-    *,
tests/packs/rendering/test_ffmpeg_finalizer.py-42-    fps: tuple[int, int] = (24, 1),
tests/packs/rendering/test_ffmpeg_finalizer.py-43-    time_base: tuple[int, int] | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py-44-    width: int = 1280,
tests/packs/rendering/test_ffmpeg_finalizer.py-45-    height: int = 720,
tests/packs/rendering/test_ffmpeg_finalizer.py-46-    video_codec: str = "h264",
tests/packs/rendering/test_ffmpeg_finalizer.py-47-    video_profile: str | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py-48-    video_level: str | None = None,
tests/packs/rendering/test_ffmpeg_finalizer.py:49:    pixel_format: str = "yuv420p",
tests/packs/rendering/test_ffmpeg_finalizer.py-50-    audio: bool = False,
tests/packs/rendering/test_ffmpeg_finalizer.py-51-    audio_codec: str = "aac",
tests/packs/rendering/test_ffmpeg_finalizer.py-52-    audio_sample_rate: int = 48_000,
tests/packs/rendering/test_ffmpeg_finalizer.py-53-    audio_channel_layout: str = "stereo",
tests/packs/rendering/test_ffmpeg_finalizer.py-54-) -> RenderProfile:
tests/packs/rendering/test_ffmpeg_finalizer.py-55-    if time_base is None:
tests/packs/rendering/test_ffmpeg_finalizer.py-56-        timescale = fps[0]
tests/packs/rendering/test_ffmpeg_finalizer.py-57-        while timescale < 10_000:
--
tests/packs/rendering/test_ffmpeg_finalizer.py-61-        width=width,
tests/packs/rendering/test_ffmpeg_finalizer.py-62-        height=height,
tests/packs/rendering/test_ffmpeg_finalizer.py-63-        fps_rational=fps,
tests/packs/rendering/test_ffmpeg_finalizer.py-64-        time_base=time_base,
tests/packs/rendering/test_ffmpeg_finalizer.py-65-        container="mp4",
tests/packs/rendering/test_ffmpeg_finalizer.py-66-        video_codec=video_codec,
tests/packs/rendering/test_ffmpeg_finalizer.py-67-        video_profile=video_profile,
tests/packs/rendering/test_ffmpeg_finalizer.py-68-        video_level=video_level,
tests/packs/rendering/test_ffmpeg_finalizer.py:69:        pixel_format=pixel_format,
tests/packs/rendering/test_ffmpeg_finalizer.py-70-        audio_codec=audio_codec if audio else None,
tests/packs/rendering/test_ffmpeg_finalizer.py-71-        audio_sample_rate=audio_sample_rate if audio else None,
tests/packs/rendering/test_ffmpeg_finalizer.py-72-        audio_channel_layout=audio_channel_layout if audio else None,
tests/packs/rendering/test_ffmpeg_finalizer.py-73-        duration_tolerance=1,
tests/packs/rendering/test_ffmpeg_finalizer.py-74-    )
tests/packs/rendering/test_ffmpeg_finalizer.py-75-
tests/packs/rendering/test_ffmpeg_finalizer.py-76-
tests/packs/rendering/test_ffmpeg_finalizer.py-77-def _support(backend: str) -> SupportReport:
--
tests/packs/rendering/test_ffmpeg_finalizer.py-228-        return MediaProbe(
tests/packs/rendering/test_ffmpeg_finalizer.py-229-            width=profile.width,
tests/packs/rendering/test_ffmpeg_finalizer.py-230-            height=profile.height,
tests/packs/rendering/test_ffmpeg_finalizer.py-231-            fps_rational=profile.fps_rational,
tests/packs/rendering/test_ffmpeg_finalizer.py-232-            time_base=profile.time_base,
tests/packs/rendering/test_ffmpeg_finalizer.py-233-            video_codec=profile.video_codec,
tests/packs/rendering/test_ffmpeg_finalizer.py-234-            video_profile=profile.video_profile or "High",
tests/packs/rendering/test_ffmpeg_finalizer.py-235-            video_level=profile.video_level or "40",
tests/packs/rendering/test_ffmpeg_finalizer.py:236:            pixel_format=profile.pixel_format,
tests/packs/rendering/test_ffmpeg_finalizer.py-237-            audio_codec=profile.audio_codec,
tests/packs/rendering/test_ffmpeg_finalizer.py-238-            audio_sample_rate=profile.audio_sample_rate,
tests/packs/rendering/test_ffmpeg_finalizer.py-239-            audio_channel_layout=profile.audio_channel_layout,
tests/packs/rendering/test_ffmpeg_finalizer.py-240-            container=profile.container,
tests/packs/rendering/test_ffmpeg_finalizer.py-241-            video_stream_present=True,
tests/packs/rendering/test_ffmpeg_finalizer.py-242-            audio_stream_present=profile.has_audio,
tests/packs/rendering/test_ffmpeg_finalizer.py-243-            audio_channels=2 if profile.has_audio else None,
tests/packs/rendering/test_ffmpeg_finalizer.py-244-        )
--
tests/packs/rendering/test_ffmpeg_finalizer.py-436-        ffmpeg_finalizer._profile_from_probe(
tests/packs/rendering/test_ffmpeg_finalizer.py-437-            MediaProbe(
tests/packs/rendering/test_ffmpeg_finalizer.py-438-                width=1280,
tests/packs/rendering/test_ffmpeg_finalizer.py-439-                height=720,
tests/packs/rendering/test_ffmpeg_finalizer.py-440-                fps_rational=(24, 1),
tests/packs/rendering/test_ffmpeg_finalizer.py-441-                time_base=(1, 12_288),
tests/packs/rendering/test_ffmpeg_finalizer.py-442-                container="mp4",
tests/packs/rendering/test_ffmpeg_finalizer.py-443-                video_codec="h264",
tests/packs/rendering/test_ffmpeg_finalizer.py:444:                pixel_format="yuv420p",
tests/packs/rendering/test_ffmpeg_finalizer.py-445-                video_stream_present=True,
tests/packs/rendering/test_ffmpeg_finalizer.py-446-                audio_stream_present=False,
tests/packs/rendering/test_ffmpeg_finalizer.py-447-            ),
tests/packs/rendering/test_ffmpeg_finalizer.py-448-            ownership=AudioOwnership.RENDERED,
tests/packs/rendering/test_ffmpeg_finalizer.py-449-            duration_tolerance=1,
tests/packs/rendering/test_ffmpeg_finalizer.py-450-        )
tests/packs/rendering/test_ffmpeg_finalizer.py-451-
tests/packs/rendering/test_ffmpeg_finalizer.py-452-

 succeeded in 209ms:
tests/core/rendering/test_contracts.py-210-    selected_plan = plan or _plan()
tests/core/rendering/test_contracts.py-211-    return FinalizeRequest(
tests/core/rendering/test_contracts.py-212-        schema_version=1,
tests/core/rendering/test_contracts.py-213-        plan=selected_plan,
tests/core/rendering/test_contracts.py-214-        artifacts=[_video()] if artifacts is None else artifacts,
tests/core/rendering/test_contracts.py-215-        output_name="preview.mp4",
tests/core/rendering/test_contracts.py:216:        backend_config={"rendering.ffmpeg-finalizer": {"faststart": True}},
tests/core/rendering/test_contracts.py-217-        metadata={"request_id": "render-001"},
tests/core/rendering/test_contracts.py-218-    )
tests/core/rendering/test_contracts.py-219-
tests/core/rendering/test_contracts.py-220-
tests/core/rendering/test_contracts.py-221-def test_dto_json_round_trip() -> None:
tests/core/rendering/test_contracts.py-222-    request = RenderRequest(
--
astrid/core/rendering/contracts.py-1751-            self.backend_config,
astrid/core/rendering/contracts.py-1752-            "backend_config",
astrid/core/rendering/contracts.py-1753-        )
astrid/core/rendering/contracts.py-1754-        unexpected_config = sorted(set(backend_config) - {plan.finalizer.id})
astrid/core/rendering/contracts.py-1755-        if unexpected_config:
astrid/core/rendering/contracts.py-1756-            raise ValueError(
astrid/core/rendering/contracts.py:1757:                "finalize backend_config may contain only the selected finalizer namespace "
astrid/core/rendering/contracts.py-1758-                f"{plan.finalizer.id!r}"
astrid/core/rendering/contracts.py-1759-            )
astrid/core/rendering/contracts.py-1760-        object.__setattr__(self, "backend_config", backend_config)
astrid/core/rendering/contracts.py-1761-        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))
astrid/core/rendering/contracts.py-1762-
astrid/core/rendering/contracts.py-1763-    @property
--
astrid/core/rendering/transport.py-143-            )
astrid/core/rendering/transport.py-144-
astrid/core/rendering/transport.py-145-        child_env = _build_environment(env)
astrid/core/rendering/transport.py-146-        # The pack-root launcher routes among sibling manifest commands by the
astrid/core/rendering/transport.py-147-        # transport-selected qualified backend id; empty backend_config in a
astrid/core/rendering/transport.py-148-        # request must never make it guess from timeline shape.
astrid/core/rendering/transport.py:149:        child_env["ASTRID_RENDER_BACKEND"] = selected_backend
astrid/core/rendering/transport.py-150-        argv_prefix[0] = _resolve_executable(
astrid/core/rendering/transport.py-151-            argv_prefix[0],
astrid/core/rendering/transport.py-152-            cwd=cwd_path,
astrid/core/rendering/transport.py-153-            child_env=child_env,
astrid/core/rendering/transport.py-154-            backend=selected_backend,
astrid/core/rendering/transport.py-155-        )
--
astrid/packs/rendering/run.py-29-
astrid/packs/rendering/run.py-30-def _selects_finalizer(argv: Sequence[str]) -> bool:
astrid/packs/rendering/run.py-31-    """Route finalize and explicitly-namespaced support operations."""
astrid/packs/rendering/run.py-32-
astrid/packs/rendering/run.py-33-    selected = _transport_selected_backend()
astrid/packs/rendering/run.py-34-    if selected is not None:
astrid/packs/rendering/run.py:35:        # The transport-selected backend id is authoritative over request
astrid/packs/rendering/run.py-36-        # content: a remotion invocation must never route to the finalizer
astrid/packs/rendering/run.py:37:        # merely because the request carries a finalizer namespace.
astrid/packs/rendering/run.py-38-        return selected == "rendering.ffmpeg-finalizer"
astrid/packs/rendering/run.py-39-    if argv and argv[0] == "finalize":
astrid/packs/rendering/run.py-40-        return True
astrid/packs/rendering/run.py-41-    if not argv or argv[0] != "support":
astrid/packs/rendering/run.py-42-        return False
astrid/packs/rendering/run.py-43-    request_path = _request_path(argv)
--
astrid/packs/rendering/run.py-53-    return isinstance(backend_config, Mapping) and (
astrid/packs/rendering/run.py-54-        "rendering.ffmpeg-finalizer" in backend_config
astrid/packs/rendering/run.py-55-    )
astrid/packs/rendering/run.py-56-
astrid/packs/rendering/run.py-57-
astrid/packs/rendering/run.py-58-def _transport_selected_backend() -> str | None:
astrid/packs/rendering/run.py:59:    """The transport sets ASTRID_RENDER_BACKEND to the qualified backend id
astrid/packs/rendering/run.py-60-    it selected; this is authoritative over any request content."""
astrid/packs/rendering/run.py:61:    value = __import__("os").environ.get("ASTRID_RENDER_BACKEND")
astrid/packs/rendering/run.py-62-    if isinstance(value, str) and value:
astrid/packs/rendering/run.py-63-        return value
astrid/packs/rendering/run.py-64-    return None
astrid/packs/rendering/run.py-65-
astrid/packs/rendering/run.py-66-
astrid/packs/rendering/run.py-67-def _selects_ffmpeg(argv: Sequence[str]) -> bool:

exec
/bin/zsh -lc "rg --files -g 'AGENTS.md' -g '"'!node_modules'"' -g '"'!vendor'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 6ms:
examples/packs/text_digest/AGENTS.md
AGENTS.md
examples/packs/text_review/AGENTS.md
examples/packs/file_summarizer/AGENTS.md
examples/packs/minimal/AGENTS.md
examples/packs/media/AGENTS.md

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '90,250p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   246	                "width",
   247	                "height",
   248	                "cropTop",
   249	                "cropBottom",
   250	                "cropLeft",

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '250,410p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py | sed -n '1,130p'; nl -ba astrid/packs/rendering/backends/ffmpeg/audio_reactive_colour.py | sed -n '260,390p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"""FFmpeg specialization for the audio-reactive-colour timeline element."""
     2	
     3	from __future__ import annotations
     4	
     5	import hashlib
     6	import json
     7	import re
     8	import subprocess
     9	from dataclasses import dataclass
    10	from pathlib import Path
    11	from tempfile import TemporaryDirectory
    12	from typing import Any, Sequence
    13	
    14	EFFECT_ID = "audio-reactive-colour"
    15	ADAPTER_ID = "audio-reactive-colour/v1"
    16	_HEX_COLOUR = re.compile(r"^#[0-9A-Fa-f]{6}$")
    17	_ALLOWED_PARAM_KEYS = frozenset({"schemaVersion", "initialColor", "events"})
    18	_ALLOWED_EVENT_KEYS = frozenset({"id", "frame", "color"})
    19	_DISALLOWED_VISUAL_KEYS = frozenset(
    20	    {
    21	        "asset",
    22	        "effects",
    23	        "transition",
    24	        "x",
    25	        "y",
    26	        "width",
    27	        "height",
    28	        "cropTop",
    29	        "cropBottom",
    30	        "cropLeft",
    31	        "cropRight",
    32	        "opacity",
    33	    }
    34	)
    35	
    36	
    37	@dataclass(frozen=True)
    38	class ColourEvent:
    39	    frame: int
    40	    color: str
    41	    event_id: str | None = None
    42	
    43	
    44	@dataclass(frozen=True)
    45	class AudioReactiveColourSpec:
    46	    width: int
    47	    height: int
    48	    fps: int
    49	    total_frames: int
    50	    initial_color: str
    51	    events: tuple[ColourEvent, ...]
    52	    audio_path: Path
    53	    audio_from: float
    54	    audio_to: float
    55	    audio_volume: float
    56	    audio_sample_rate: int = 48000
    57	
    58	    @property
    59	    def duration_seconds(self) -> float:
    60	        return self.total_frames / self.fps
    61	
    62	    @property
    63	    def marker_sha256(self) -> str:
    64	        payload = {
    65	            "initialColor": self.initial_color,
    66	            "events": [
    67	                {"frame": event.frame, "color": event.color, "id": event.event_id}
    68	                for event in self.events
    69	            ],
    70	        }
    71	        encoded = json.dumps(
    72	            payload, sort_keys=True, separators=(",", ":")
    73	        ).encode("utf-8")
    74	        return hashlib.sha256(encoded).hexdigest()
    75	
    76	
    77	def _number(value: Any, label: str) -> float:
    78	    if isinstance(value, bool) or not isinstance(value, (int, float)):
    79	        raise ValueError(f"{label} must be a number")
    80	    return float(value)
    81	
    82	
    83	def _positive_integer(value: Any, label: str) -> int:
    84	    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
    85	        raise ValueError(f"{label} must be a positive integer")
    86	    return value
    87	
    88	
    89	def _resolve_audio_path(
    90	    entry: dict[str, Any], assets_path: Path, asset_id: str
    91	) -> Path:
    92	    if entry.get("url"):
    93	        raise ValueError(
    94	            f"{EFFECT_ID} FFmpeg specialization requires a local audio asset"
    95	        )
    96	    file_value = entry.get("file")
    97	    if not isinstance(file_value, str) or not file_value:
    98	        raise ValueError(f"Audio asset {asset_id!r} has no local file")
    99	    path = Path(file_value)
   100	    if not path.is_absolute():
   101	        path = (assets_path.parent / path).resolve()
   102	    if not path.is_file():
   103	        raise FileNotFoundError(f"Audio asset missing: {path}")
   104	    return path
   105	
   106	
   107	def match_and_validate(
   108	    timeline_data: dict[str, Any],
   109	    registry: dict[str, Any],
   110	    assets_path: Path,
   111	) -> AudioReactiveColourSpec | None:
   112	    """Return a strict whole-timeline spec, or None when the effect is absent."""
   113	    clips = timeline_data.get("clips")
   114	    tracks = timeline_data.get("tracks")
   115	    if not isinstance(clips, list) or not isinstance(tracks, list):
   116	        return None
   117	    reactive = [
   118	        clip
   119	        for clip in clips
   120	        if isinstance(clip, dict) and clip.get("clipType") == EFFECT_ID
   121	    ]
   122	    if not reactive:
   123	        return None
   124	    if len(reactive) != 1:
   125	        raise ValueError(f"{EFFECT_ID} fast path requires exactly one effect clip")
   126	    if len(clips) != 2:
   127	        raise ValueError(
   128	            f"{EFFECT_ID} fast path requires one effect clip and one audio clip"
   129	        )
   130	
   260	    if not isinstance(assets, dict) or asset_id not in assets:
   261	        raise ValueError(f"Audio clip references unknown asset {asset_id!r}")
   262	    entry = assets[asset_id]
   263	    if not isinstance(entry, dict):
   264	        raise ValueError(f"Audio asset {asset_id!r} must be an object")
   265	    audio_path = _resolve_audio_path(entry, assets_path, asset_id)
   266	
   267	    return AudioReactiveColourSpec(
   268	        width=width,
   269	        height=height,
   270	        fps=fps,
   271	        total_frames=total_frames,
   272	        initial_color=initial_color.upper(),
   273	        events=tuple(events),
   274	        audio_path=audio_path,
   275	        audio_from=audio_from,
   276	        audio_to=audio_to,
   277	        audio_volume=audio_volume,
   278	    )
   279	
   280	
   281	def write_sendcmd(spec: AudioReactiveColourSpec, path: Path) -> None:
   282	    path.write_text(
   283	        "".join(
   284	            (
   285	                f"{(event.frame - 1) / spec.fps:.9f} "
   286	                f"drawbox@bg color 0x{event.color[1:]};\n"
   287	            )
   288	            for event in spec.events
   289	        ),
   290	        encoding="utf-8",
   291	    )
   292	
   293	
   294	def _escape_filter_path(path: Path) -> str:
   295	    return (
   296	        path.resolve()
   297	        .as_posix()
   298	        .replace("\\", "\\\\")
   299	        .replace(":", "\\:")
   300	        .replace("'", "\\'")
   301	    )
   302	
   303	
   304	def build_video_command(
   305	    spec: AudioReactiveColourSpec, sendcmd_path: Path, video_path: Path
   306	) -> list[str]:
   307	    initial = f"0x{spec.initial_color[1:]}"
   308	    video_filters: list[str] = []
   309	    if spec.events:
   310	        video_filters.append(
   311	            f"drawbox@bg=x=0:y=0:w=iw:h=ih:color={initial}:t=fill"
   312	        )
   313	        # sendcmd deliberately follows drawbox. A command delivered at the
   314	        # previous frame then affects drawbox on the next frame, making a
   315	        # semantic marker F visible at exactly F rather than F-1.
   316	        video_filters.append(f"sendcmd=f='{_escape_filter_path(sendcmd_path)}'")
   317	    video_filters.append("format=yuv420p")
   318	    return [
   319	        "ffmpeg",
   320	        "-hide_banner",
   321	        "-y",
   322	        "-f",
   323	        "lavfi",
   324	        "-i",
   325	        (
   326	            f"color=c={initial}:s={spec.width}x{spec.height}:"
   327	            f"r={spec.fps}:d={spec.duration_seconds:.9f}"
   328	        ),
   329	        "-vf",
   330	        ",".join(video_filters),
   331	        "-frames:v",
   332	        str(spec.total_frames),
   333	        "-an",
   334	        "-c:v",
   335	        "libx264",
   336	        "-preset",
   337	        "veryfast",
   338	        "-crf",
   339	        "20",
   340	        "-pix_fmt",
   341	        "yuv420p",
   342	        str(video_path),
   343	    ]
   344	
   345	
   346	def build_mux_command(
   347	    spec: AudioReactiveColourSpec, video_path: Path, out_path: Path
   348	) -> list[str]:
   349	    audio_filter = (
   350	        f"atrim=start={spec.audio_from:.9f}:end={spec.audio_to:.9f},"
   351	        "asetpts=PTS-STARTPTS,"
   352	        f"aformat=sample_rates={spec.audio_sample_rate}:channel_layouts=stereo,"
   353	        f"volume={spec.audio_volume:.9f}"
   354	    )
   355	    return [
   356	        "ffmpeg",
   357	        "-hide_banner",
   358	        "-y",
   359	        "-i",
   360	        str(video_path),
   361	        "-i",
   362	        str(spec.audio_path),
   363	        "-map",
   364	        "0:v:0",
   365	        "-map",
   366	        "1:a:0",
   367	        "-c:v",
   368	        "copy",
   369	        "-af",
   370	        audio_filter,
   371	        "-shortest",
   372	        "-c:a",
   373	        "aac",
   374	        "-b:a",
   375	        "192k",
   376	        "-movflags",
   377	        "+faststart",
   378	        str(out_path),
   379	    ]
   380	
   381	
   382	def render(
   383	    spec: AudioReactiveColourSpec,
   384	    out_path: Path,
   385	    *,
   386	    runner: Any = subprocess.run,
   387	) -> Path:
   388	    out_path = out_path.resolve()
   389	    out_path.parent.mkdir(parents=True, exist_ok=True)
   390	    with TemporaryDirectory(

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/transport.py | sed -n '100,190p'; nl -ba tests/core/rendering/test_transport.py | sed -n '1,170p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   146	        # The pack-root launcher routes among sibling manifest commands by the
   147	        # transport-selected qualified backend id; empty backend_config in a
   148	        # request must never make it guess from timeline shape.
   149	        child_env["ASTRID_RENDER_BACKEND"] = selected_backend
   150	        argv_prefix[0] = _resolve_executable(
   151	            argv_prefix[0],
   152	            cwd=cwd_path,
   153	            child_env=child_env,
   154	            backend=selected_backend,
   155	        )
   156	        for binary in required_binaries:
   157	            binary_name = os.fspath(binary)
   158	            _resolve_executable(
   159	                binary_name,
   160	                cwd=cwd_path,
   161	                child_env=child_env,
   162	                backend=selected_backend,
   163	            )
   164	
   165	        _remove_stale_result(result, backend=selected_backend)
   166	        argv = [
   167	            *argv_prefix,
   168	            verb,
   169	            "--request",
   170	            str(request),
   171	            "--result",
   172	            str(result),
   173	        ]
   174	        secret_values = _secret_environment_values(os.environ, env)
   175	
   176	        try:
   177	            process = subprocess.Popen(
   178	                argv,
   179	                shell=False,
   180	                cwd=str(cwd_path),
   181	                env=child_env,
   182	                stdin=subprocess.DEVNULL,
   183	                stdout=subprocess.PIPE,
   184	                stderr=subprocess.PIPE,
   185	                text=True,
   186	                encoding="utf-8",
   187	                errors="replace",
   188	                start_new_session=True,
   189	            )
   190	        except (FileNotFoundError, PermissionError) as exc:
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

exec
/bin/zsh -lc 'git log --oneline --decorate -5' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
58473c3a (HEAD -> oracle-run) batch3-rework2: oracle re-review issues 1-6 (env-authoritative launcher routing, remotion full render-profile support + manifest audio, ffmpeg time_base support check, audio-reactive 48kHz, whole-source stream-copy gate incl codec/pixel + supported required, TOCTOU-free legacy facade via preloaded-data builder)
72b70944 batch3-rework: oracle issues 1-8 (launcher backend-id routing, remotion support/render contract alignment + ffprobe binary, ffmpeg full-profile support + canonical 48kHz, probe-gated stream-copy, legacy path strict support, finalizer audio-presence + codec-anchor tests, lock test timeouts)
0c2733ed (tag: C3) batch3: Remotion/FFmpeg backend extraction + outer lock, strict FFmpeg support + audio semantics, ffmpeg-finalizer extraction, built-in registration + real render smoke + typecheck
3df2b858 (tag: C3-batch2-done) batch2-rework6: oracle re-review5 issues 1-2 (support rejects audio!=rendered regardless of profile presence, layout channel-count whitespace-strip)
3557792f batch2-rework5: oracle re-review4 issues 1-5 (OSError-safe drain + guaranteed direct-child reap, support rejects audio!=rendered, layout channel-count normalization, tight root-only macOS symlink exemption, committed-read guard before resolve)

exec
/bin/zsh -lc "git diff --unified=2 0c2733ed..72b70944 -- tests/packs/rendering | rg '"'^'"\\+def test_|"'^'"\\+@pytest|"'^'"\\+\\s*\\(\"|"'^'"\\+\\s*assert' | head -n 450" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
+        ("node", "npx", "ffprobe"),
+    assert argv[argv.index("-c:v") + 1] == "libx264"
+    assert copy_argv[copy_argv.index("-c:v") + 1] == "copy"
+    assert copy_argv[-1] == str((tmp_path / "outputs" / "result.mp4").resolve())
+    assert result.video.profile.audio_sample_rate == 48000
+    assert "-profile:v" not in commands[0]
+    assert "-level:v" not in commands[0]
+    assert normalize[normalize.index("-profile:v") + 1] == "high"
+    assert normalize[normalize.index("-level:v") + 1] == "4.0"
+def test_rendered_mode_normalizes_visual_only_segment_audio_presence(
+    assert any("anullsrc=" in value for value in normalize)
+    assert "-shortest" in normalize
+    assert "segment[1] audio_presence: absent -> present" in result.normalization
+    assert result.audio_ownership is AudioOwnership.RENDERED
+def test_real_ffmpeg_normalizes_rational_profile_and_emits_valid_media(
+    assert output_probe.fps_rational == (30_000, 1001)
+    assert output_probe.time_base == (1, 30_000)
+    assert output_probe.video_profile == "High"
+    assert ffmpeg_finalizer._level(
+    assert result.video.duration_frames == 30
+    assert any("fps_rational" in item for item in result.normalization)
+    assert not list((tmp_path / "outputs").glob(".rational.mp4.ffmpeg-finalizer-*"))
+    assert "anullsrc=r=48000:cl=stereo,atrim=duration=1.000000" in filters
+    assert "-filter_complex" in argv
+    assert argv[argv.index("-c:v") + 1] == "libx264"
+    assert manifest.required_binaries == ("node", "npx", "ffprobe")
+    assert report.features["audio_ownership"] == "rendered"
+        assert first_ready.wait(60)
+        assert first_entered.wait(60)
+        assert second_ready.wait(60)

exec
/bin/zsh -lc 'git diff --unified=4 0c2733ed..72b70944 -- tests/packs/rendering/test_ffmpeg_support.py tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_remotion_backend.py | rg -n -C 12 "profile|time_base|video_level|stream_copy|transport|ASTRID|TOCTOU|embedded audio|always" | head -n 640' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
1-diff --git a/tests/packs/rendering/test_ffmpeg_backend.py b/tests/packs/rendering/test_ffmpeg_backend.py
2-index 9a473e90..1c5c25d5 100644
3---- a/tests/packs/rendering/test_ffmpeg_backend.py
4-+++ b/tests/packs/rendering/test_ffmpeg_backend.py
5-@@ -1,6 +1,7 @@
6- from __future__ import annotations
7- 
8-+import dataclasses
9- import json
10- import subprocess
11- from pathlib import Path
12- from unittest import mock
13:@@ -138,9 +139,9 @@ def _profile() -> RenderProfile:
14:         video_profile="High",
15:         video_level="4.0",
16-         pixel_format="yuv420p",
17-         audio_codec="aac",
18--        audio_sample_rate=44100,
19-+        audio_sample_rate=48000,
20-         audio_channel_layout="stereo",
21-     )
22- 
23- 
24:@@ -276,30 +277,21 @@ def test_build_render_command_is_pure_and_preserves_stream_copy(
25-     tmp_path: Path,
26- ) -> None:
27-     timeline_path, assets_path = _write_inputs(tmp_path)
28-     request = _request(timeline_path, assets_path)
29-+    inputs = command.resolve_render_command_inputs(request, tmp_path)
30- 
31-+    # Stream-copy is gated on probe evidence; the pure builder emits the copy
32:+    # path only when the caller passes stream_copy_allowed=True. A placeholder
33-+    # source (no real probe) must default to re-encoding.
34-     argv = command.build_render_command(request, tmp_path)
35-+    assert argv[argv.index("-c:v") + 1] == "libx264"
36- 
37--    assert argv[:6] == [
38--        "ffmpeg",
39--        "-hide_banner",
40--        "-y",
41--        "-i",
42--        str((tmp_path / "source.mp4").resolve()),
43--        "-filter_complex",
44--    ]
45--    filters = argv[argv.index("-filter_complex") + 1]
46--    assert (
47--        "[0:a]atrim=start=0.000000:end=2.000000,"
48--        "asetpts=PTS-STARTPTS,"
49--        "aformat=sample_rates=44100:channel_layouts=stereo,"
50--        "volume=0.750000[a0]" in filters
51-+    copy_argv = command.build_render_command_from_inputs(
52:+        dataclasses.replace(inputs, stream_copy_allowed=True)
53-     )
54--    assert "[a0]concat=n=1:v=0:a=1[aout]" in filters
55--    assert argv[argv.index("-c:v") + 1] == "copy"
56--    assert "-preset" not in argv
57--    assert argv[-1] == str((tmp_path / "outputs" / "result.mp4").resolve())
58-+    assert copy_argv[copy_argv.index("-c:v") + 1] == "copy"
59-+    assert copy_argv[-1] == str((tmp_path / "outputs" / "result.mp4").resolve())
60-     assert not (tmp_path / "outputs").exists()
61- 
62- 
63- def test_build_render_command_encodes_visual_only_without_synthesizing_silence(
64-@@ -355,9 +347,9 @@ def test_protocol_render_returns_explicit_rendered_audio_result(
65:         video_profile="High",
66:         video_level="40",
67-         pixel_format="yuv420p",
68-         audio_codec="aac",
69--        audio_sample_rate=44100,
70-+        audio_sample_rate=48000,
71-         audio_channel_layout="stereo",
72-         audio_channels=2,
73-         container="mp4",
74-         format_name="mov,mp4",
75-@@ -388,9 +380,9 @@ def test_protocol_render_returns_explicit_rendered_audio_result(
76-     assert isinstance(result, RenderResult)
77-     assert result.video.path == "outputs/result.mp4"
78-     assert result.video.audio is AudioOwnership.RENDERED
79-     assert result.audio_ownership is AudioOwnership.RENDERED
80:-    assert result.video.profile.audio_sample_rate == 44100
81:+    assert result.video.profile.audio_sample_rate == 48000
82-     assert result.video.duration_frames == 60
83-     assert result.backend_fragments[ffmpeg.BACKEND_ID]["renderer"] == "ffmpeg"
84-     assert seen["argv"][-1] == str(tmp_path / "outputs" / "result.mp4")
85-     validate.assert_called_once()
86-diff --git a/tests/packs/rendering/test_ffmpeg_support.py b/tests/packs/rendering/test_ffmpeg_support.py
87-index 81d1ea4f..3f575b3c 100644
88---- a/tests/packs/rendering/test_ffmpeg_support.py
89-+++ b/tests/packs/rendering/test_ffmpeg_support.py
90-@@ -382,9 +382,9 @@ def test_non_overlapping_audio_clips_concat_with_positional_silence(
91-     argv = command.build_render_command(_request(tmp_path), tmp_path)
92-     filters = argv[argv.index("-filter_complex") + 1]
93- 
--
108-+    # NOT be trusted from registry metadata: the builder re-encodes via
109-+    # filter_complex with no audio mapping (-an).
110-+    assert "-filter_complex" in argv
111-     assert "-c:a" not in argv
112-     assert "-an" in argv
113--    assert argv[argv.index("-c:v") + 1] == "copy"
114-+    assert argv[argv.index("-c:v") + 1] == "libx264"
115- 
116- 
117- def test_visual_only_request_can_delegate_audio_as_passthrough(tmp_path: Path) -> None:
118-     timeline_data = _timeline(include_audio=False)
119-@@ -569,9 +572,9 @@ def test_audio_reactive_support_gain_and_protocol_provenance_fragments(
120:         video_profile="High",
121:         video_level="40",
122-         pixel_format="yuv420p",
123-         audio_codec="aac",
124--        audio_sample_rate=44100,
125-+        audio_sample_rate=48000,
126-         audio_channel_layout="stereo",
127-         audio_channels=2,
128-         container="mp4",
129-         duration_rational=(1, 1),
130-diff --git a/tests/packs/rendering/test_remotion_backend.py b/tests/packs/rendering/test_remotion_backend.py
131-index cb3b0d07..02538d0e 100644
132---- a/tests/packs/rendering/test_remotion_backend.py
133-+++ b/tests/packs/rendering/test_remotion_backend.py

exec
/bin/zsh -lc 'git diff --unified=4 0c2733ed..72b70944 -- tests | rg -n -C 10 "finalizer namespace|ASTRID_RENDER_BACKEND|backend_config.*finalizer|rendering.remotion" | head -n 480' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
293-+        width=64,
294-+        height=64,
295-+        video_profile="High",
296-+        video_level="4.0",
297-+    )
298-+    request = FinalizeRequest(
299-+        schema_version=SCHEMA_VERSION,
300-+        plan=_plan(canonical, [30]),
301-+        artifacts=[source],
302-+        output_name="rational.mp4",
303:+        backend_config={ffmpeg_finalizer.BACKEND_ID: {"faststart": True}},
304-+    )
305-+
306-+    result = ffmpeg_finalizer.finalize(request, workspace=tmp_path)
307-+
308-+    output = tmp_path / result.video.path
309-+    output_probe = ffprobe_metadata_strict(output)
310-+    assert output_probe.fps_rational == (30_000, 1001)
311-+    assert output_probe.time_base == (1, 30_000)
312-+    assert output_probe.video_profile == "High"
313-+    assert ffmpeg_finalizer._level(

exec
/bin/zsh -lc "rg -n \"def _require_rational\" astrid/core/rendering/contracts.py && nl -ba astrid/core/rendering/contracts.py | sed -n '80,145p'; rg -n \"def _rational\" astrid/core/rendering/artifacts.py | head" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 4ms:
231:def _rational(value: Any, *, label: str) -> Fraction:

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '295,325p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
Because this is the Astrid repository, I’m also applying its repository skill now; it determines whether any project-specific inspection step is required before the verdict.
exec
/bin/zsh -lc 'cat /Users/peteromalley/.codex/skills/astrid/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc 'cat astrid/packs/_core/skill/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc "sed -n '601,820p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 3ms:
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
/bin/zsh -lc "sed -n '201,400p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
/bin/zsh -lc 'wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md astrid/packs/_core/skill/SKILL.md && shasum /Users/peteromalley/.codex/skills/astrid/SKILL.md astrid/packs/_core/skill/SKILL.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "sed -n '1,200p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "sed -n '401,600p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

 succeeded in 62ms:
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

 succeeded in 215ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
     772 astrid/packs/_core/skill/SKILL.md
    1544 total
b310ab07698cec2bb5dd8a972fd78c3fb8e6aaf2  /Users/peteromalley/.codex/skills/astrid/SKILL.md
b310ab07698cec2bb5dd8a972fd78c3fb8e6aaf2  astrid/packs/_core/skill/SKILL.md

exec
/bin/zsh -lc "sed -n '501,600p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "sed -n '401,500p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

 succeeded in 0ms:
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

exec
/bin/zsh -lc "if test -f astrid/packs/rendering/skill/SKILL.md; then sed -n '1,1000p' astrid/packs/rendering/skill/SKILL.md; else echo 'NO_RENDERING_PACK_SKILL'; fi" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 732ms:
---
name: rendering
description: >
  Rendering pack: the Remotion compositor that turns a timeline, and
  optional assets registry, into hype.mp4 plus provenance; also includes
  escape-hatch element scaffolding for custom
  visual effects (html_canvas_effect, sprite_sheet).  Auto-starts an
  HTTP server with Range request support for Remotion media streaming.
---

# Rendering

The rendering pack turns assembled timelines, and optional media asset
registries, into finished video files through Remotion, FFmpeg, or the hybrid
renderer. It also provides element-system escape hatches for custom visual
effects and sprite sheet generation.

## Render flow

The core rendering path is:

```
timeline.json + optional assets.json  →  Remotion compositor  →  hype.mp4 + provenance
```

1. **Input**: `hype.timeline.json` (clip sequence, effects, animations,
   transitions) and, when the timeline references media files,
   `hype.assets.json` (asset registry with file paths).
2. **HTTP server start**: Before launching Remotion, the executor starts a
   local `ThreadingHTTPServer` on a randomly-chosen free port bound to
   `127.0.0.1`. Media asset paths are rewritten to
   `http://localhost:<port>/...` URLs so Remotion can stream them directly.
3. **Composition**: Remotion renders the timeline using the resolved theme
   and composition entry point (default: `HypeComposition`).
4. **Output**: `hype.mp4` and `hype.mp4.provenance.json`.

For the built-in `audio-reactive-colour` effect, the same normal render command
has a strict fast path: one full-duration frame-aligned effect plus one
coextensive local audio clip is compiled to FFmpeg `sendcmd`. The effect
parameters remain the single editable source of truth, and unsupported shapes
fall through to ordinary rendering.

## Auto-started HTTP server

The executor spins up a local HTTP server automatically before Remotion
renders. Key details:

- **Handler**: `_RangeHTTPRequestHandler` (extends `SimpleHTTPRequestHandler`)
- **Range request support**: Implements HTTP `Range` (byte-range) headers
  with proper `206 Partial Content` responses, `Content-Range`, and
  `Accept-Ranges: bytes` headers. This is essential — Remotion's media
  components seek into long source videos via byte-range requests. Without
  Range support, every seek would fully download the source video, causing
  timeouts or black/silent frames.
- **CORS**: Responds with `Access-Control-Allow-Origin: *` and allows
  `Range` and `Content-Type` headers.
- **Lifecycle**: Started as a daemon thread before Remotion and shut down
  in a `finally` block after Remotion exits.
- **Port**: Auto-picked via `_pick_free_port()` (binds to `127.0.0.1:0`
  and reads the assigned port).

When `assets_registry` is omitted, the runner supplies an empty media registry.
This is the normal path for timelines that contain only text, effects,
generated visuals, or other clips that do not reference media entries.

## Theme support

The executor resolves the timeline's theme slug against the workspace
themes directory (`themes/`), merges any per-run `theme_overrides` from
the timeline, and passes the merged `{id, visual}` dict to Remotion as
props. A fallback `banodoco-default` theme is used when no theme is
specified.

## Executors

| Executor | What it does |
|---|---|
| `rendering.render` | Render a hype timeline, with optional media assets, into `hype.mp4` and a provenance sidecar through Remotion, ffmpeg, or hybrid rendering. Pipeline step 12 — the terminal step before optional YouTube upload or Reigh publish. |
| `rendering.sprite_sheet` | Generate, slice, and preview GPT Image sprite sheets for batch image work. Produces a sprite atlas (`sprite_sheet.png`), alpha-processed variant, manifest, and MP4 preview. |
| `rendering.html_canvas_effect` | Scaffold a local Remotion HTML-in-canvas effect element. Creates a user-editable effect under `astrid/packs/local/elements/effects/<effect_id>/` with DOM content wrapped in Remotion's `HtmlInCanvas` for optional canvas/WebGL post-processing. |

## Escape hatch: element system

When the standard Remotion timeline rendering doesn't cover your needs,
the rendering pack provides two escape hatches into the element system:

### `rendering.html_canvas_effect`

Scaffolds a custom local effect element that renders DOM content inside
a Remotion `<HtmlInCanvas>` component. Useful for:

- Custom WebGL/shaders overlaid on video
- Glass product cards with HTML content
- Any effect that benefits from DOM content rendered into a canvas for
  post-processing

The scaffolded element lives under `astrid/packs/local/elements/effects/`
and can be freely edited. Once created, it integrates into the standard
Remotion render flow — you reference it by id in the timeline and render
via `rendering.render`.

Local effect, animation, and transition manifests may declare static files with
optional top-level syntax:

```yaml
assets:
  badge: assets/badge.png
  palette: assets/palette.json
```

Each value is a file path relative to the element root. During render, only
declared assets for elements used by the timeline are staged under
`remotion/public/astrid-effects/<render-hash>/<effect-id>/`, exposed to the
component as `params.__astridAssets`, and cleaned up after Remotion exits.

Requires Remotion ≥ 4.0.455.

### `rendering.sprite_sheet`

Generates a sprite sheet (atlas image) using OpenAI GPT Image models.
The sprite sheet is sliced into individual frames and can be used as an
animation source in Remotion compositions. Produces:

- `sprite_sheet.png` — the full sprite atlas
- `sprite_sheet_alpha.png` — alpha-processed variant
- `sprite_manifest.json` — per-frame metadata
- `sprite_preview.mp4` — animated preview of all frames

Requires `OPENAI_API_KEY` and `ffmpeg` on the system path.

## When to use

- Use `rendering.render` to produce the final video from a timeline and,
  only when needed, an asset registry. This is the standard rendering path.
- Use the `audio-reactive-colour` effect for frozen integer-frame colour
  markers. Keep one effect clip rather than expanding each state into a clip;
  `rendering.render` selects the fast final-export adapter automatically.
- Use `rendering.sprite_sheet` when you need to generate a batch of
  related images as a sprite atlas for animation.
- Use `rendering.html_canvas_effect` when you need a custom visual effect
  beyond the built-in element catalog — scaffolds a local Remotion effect
  that you can customize freely.

## Credentials

| Env var | Used by |
|---|---|
| `OPENAI_API_KEY` | sprite_sheet (GPT Image API) |

## CLI quick-start

```bash
# Render a timeline to video
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json

# Render a timeline with a media asset registry
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json

# Render with custom theme and backend
python3 -m astrid executors run rendering.render \
  --out ./out \
  --input timeline=./out/hype.timeline.json \
  --input assets_registry=./out/hype.assets.json \
  --input theme=./themes/my-theme \
  --input engine=hybrid
```

The normal executor CLI writes `./out/hype.mp4` and
`./out/hype.mp4.provenance.json`. Direct `run.py` execution is reserved for
debugging the executor itself:

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --assets ./out/hype.assets.json \
  --out ./out/hype.mp4
```

Omit `--assets` in direct debug runs only for asset-free timelines.

```bash
python3 -m astrid.packs.rendering.executors.render.run \
  --timeline ./out/hype.timeline.json \
  --out ./out/hype.mp4
```

```bash
# Generate a sprite sheet
python3 -m astrid executors run rendering.sprite_sheet -- \
  --animation "a character waving" \
  --subject "cartoon robot" \
  --reference-image ./robot_ref.png \
  --out-dir ./sprites

# Scaffold a custom HTML canvas effect
python3 -m astrid executors run rendering.html_canvas_effect -- \
  --effect-id glass-product-card --out ./out
```

## Dependencies

- **Remotion** (`npx remotion render`) — must be installed in the `remotion/` project directory
- **Node.js / npm** — `npm install` must have been run in the Remotion project
- **ffmpeg/ffprobe** — required by Remotion's render pipeline and `sprite_sheet` frame extraction

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c '
from astrid.core.media import MediaProbe
from astrid.core.rendering.contracts import RenderProfile, RenderRequest
from astrid.packs.rendering.backends.ffmpeg.support import support
timeline = {\"theme_overrides\": {\"visual\": {\"canvas\": {\"width\": 640, \"height\": 360, \"fps\": 30}}}, \"tracks\": [{\"id\": \"v\", \"kind\": \"visual\", \"label\": \"Video\"}], \"clips\": [{\"id\": \"video\", \"at\": 0, \"track\": \"v\", \"clipType\": \"media\", \"asset\": \"video\", \"from\": 0, \"to\": 4, \"speed\": 1, \"volume\": 0}]}
assets = {\"assets\": {\"video\": {\"file\": \"/bin/sh\", \"type\": \"video/mp4\", \"duration\": 4, \"resolution\": \"640x360\", \"fps\": 30}}}
profile = RenderProfile(width=640, height=360, fps_rational=(30, 1), time_base=(1, 15360), container=\"mp4\", video_codec=\"h264\", video_profile=\"High\", video_level=\"4.0\", pixel_format=\"yuv420p\")
request = RenderRequest(schema_version=1, timeline_path=\"/tmp/timeline.json\", assets_registry_path=\"/tmp/assets.json\", output_name=\"out.mp4\", profile=profile, backend_config={\"rendering.ffmpeg\": {}})
probe = MediaProbe(duration_seconds=4, duration_rational=(4,1), width=640, height=360, fps=30, fps_rational=(30,1), time_base=(1,90000), container=\"mp4\", video_codec=\"h264\", video_profile=\"Main\", video_level=\"3.1\", pixel_format=\"yuv420p\", video_stream_present=True, audio_stream_present=False)
report = support(request, timeline, assets, probe=lambda _: probe, which=lambda _: \"/usr/bin/tool\")
print({\"supported\": report.supported, \"reasons\": report.reasons, \"stream_copy\": report.features[\"stream_copy\"]})
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1470ms:
{'supported': True, 'reasons': [], 'stream_copy': True}

exec
/bin/zsh -lc "rg --files -g '*.mp4' -g '"'!node_modules'"' -g '"'!runs'"' | head -n 30" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/fixtures/reshape/hype_regression/main.mp4
tests/fixtures/reshape/hype_regression/broll.mp4

exec
/bin/zsh -lc 'ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,level,pix_fmt,time_base,r_frame_rate,width,height -of json tests/fixtures/reshape/hype_regression/main.mp4' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc 'ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,level,pix_fmt,time_base,r_frame_rate,width,height -of json tests/fixtures/reshape/hype_regression/broll.mp4' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 934ms:
{
    "programs": [

    ],
    "stream_groups": [

    ],
    "streams": [
        {
            "codec_name": "h264",
            "profile": "Constrained Baseline",
            "width": 1280,
            "height": 720,
            "pix_fmt": "yuv420p",
            "level": 31,
            "r_frame_rate": "24/1",
            "time_base": "1/12288"
        }
    ]
}

 succeeded in 942ms:
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
            "pix_fmt": "yuv420p",
            "level": 40,
            "r_frame_rate": "30/1",
            "time_base": "1/15360"
        }
    ]
}

codex
One independent review found a possible contract-level defect in the Remotion closure: the code declares that silent visual-only renders always contain AAC audio, but the render command may not actually force an audio track. I’m verifying that against the installed Remotion implementation and this repo’s configuration before counting it.
exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '620,755p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 6ms:
   620	            composition_id=composition_id,
   621	            theme_path=theme_path,
   622	            min_free_gb=min_free_gb,
   623	        )
   624	
   625	
   626	def _execute_remotion_locked(
   627	    timeline_path: Path,
   628	    assets_path: Path,
   629	    staged_video: Path,
   630	    *,
   631	    provenance_out_path: Path,
   632	    project_dir: Path,
   633	    composition_id: str,
   634	    theme_path: Path | None,
   635	    min_free_gb: float | None,
   636	) -> _ExecutionDetails:
   637	    """Execute one render while the caller owns the non-recursive outer lock."""
   638	
   639	    _validate_project_dir(project_dir)
   640	    _regenerate_element_registries(project_dir, theme_path)
   641	    registry_state = _effective_registry_state(theme_path)
   642	    _require_free_space(provenance_out_path.parent, min_free_gb)
   643	    props_path = (provenance_out_path.parent / ".remotion-props.json").resolve()
   644	    render_hash = _render_asset_stage_hash(
   645	        timeline_path,
   646	        assets_path,
   647	        provenance_out_path,
   648	    )
   649	    staged_public_root = project_dir / "public" / "astrid-effects" / render_hash
   650	    with ExitStack() as asset_lifecycle:
   651	        try:
   652	            materializer = asset_lifecycle.enter_context(AssetMaterializer(assets_path))
   653	            asset_server = None
   654	            if materializer.needs_server:
   655	                try:
   656	                    asset_server = asset_lifecycle.enter_context(
   657	                        InvocationAssetServer(materializer.staging_dir)
   658	                    )
   659	                except OSError as exc:
   660	                    raise RuntimeError(
   661	                        f"Permission denied (1100): local HTTP asset server blocked: {exc}"
   662	                    ) from exc
   663	            resolved_registry = materializer.resolved_registry(asset_server)
   664	            resolved_theme = theme_path or (
   665	                WORKSPACE_ROOT / "themes" / "banodoco-default" / "theme.json"
   666	            )
   667	            theme_for_props = _resolved_theme_for_render(timeline_path, resolved_theme)
   668	            merged_props = {
   669	                "timeline": _serialize_timeline(
   670	                    timeline_path,
   671	                    default_theme=str(
   672	                        theme_for_props.get("id") or "banodoco-default"
   673	                    ),
   674	                ),
   675	                "assets": resolved_registry,
   676	                "theme": theme_for_props,
   677	            }
   678	            stage_summary = _stage_effect_assets_for_timeline(
   679	                merged_props["timeline"],
   680	                project_dir=project_dir,
   681	                theme_path=theme_path,
   682	                render_hash=render_hash,
   683	            )
   684	            staged_video.parent.mkdir(parents=True, exist_ok=True)
   685	            props_path.write_text(json.dumps(merged_props), encoding="utf-8")
   686	            remotion_env_additions: dict[str, str] = {}
   687	            composition_src = _timeline_composition_src(project_dir)
   688	            if composition_src is not None:
   689	                remotion_env_additions["ASTRID_TIMELINE_COMPOSITION_SRC"] = str(
   690	                    composition_src
   691	                )
   692	            completed = subprocess.run(
   693	                [
   694	                    "npx",
   695	                    "remotion",
   696	                    "render",
   697	                    composition_id,
   698	                    "--props",
   699	                    str(props_path),
   700	                    "--output",
   701	                    str(staged_video),
   702	                    "--allow-html-in-canvas",
   703	                ],
   704	                cwd=str(project_dir),
   705	                env=build_child_subprocess_env(explicit_env=remotion_env_additions),
   706	                capture_output=True,
   707	                check=False,
   708	                text=True,
   709	            )
   710	            if completed.returncode != 0:
   711	                stderr_tail = _stderr_tail(completed.stderr)
   712	                message = f"Remotion render failed with exit code {completed.returncode}"
   713	                if stderr_tail:
   714	                    message = f"{message}\n{stderr_tail}"
   715	                raise RuntimeError(message)
   716	            if not staged_video.is_file() or staged_video.stat().st_size <= 0:
   717	                raise RuntimeError("Remotion render did not produce a non-empty video")
   718	            return _ExecutionDetails(
   719	                active_theme=theme_for_props,
   720	                registry_state=registry_state,
   721	                stage_summary=stage_summary,
   722	            )
   723	        finally:
   724	            props_path.unlink(missing_ok=True)
   725	            shutil.rmtree(staged_public_root, ignore_errors=True)
   726	
   727	
   728	def render(
   729	    timeline_path: Path,
   730	    assets_path: Path,
   731	    out_path: Path,
   732	    *,
   733	    project_dir: Path | None = None,
   734	    composition_id: str = DEFAULT_COMPOSITION_ID,
   735	    theme_path: Path | None = None,
   736	    min_free_gb: float | None = None,
   737	    previous_outputs: Sequence[Path] = (),
   738	) -> Path:
   739	    """Render privately, then publish the legacy video/provenance pair."""
   740	
   741	    timeline_path = Path(timeline_path)
   742	    assets_path = Path(assets_path)
   743	    out_path = Path(out_path)
   744	    project_dir = Path(project_dir) if project_dir is not None else REPO_ROOT / "remotion"
   745	    out_path.parent.mkdir(parents=True, exist_ok=True)
   746	    with TemporaryDirectory(
   747	        prefix=f".{out_path.name}.publication-",
   748	        dir=str(out_path.parent),
   749	    ) as publication_tmp:
   750	        staged_video = Path(publication_tmp) / out_path.name
   751	        details = _execute_remotion(
   752	            timeline_path,
   753	            assets_path,
   754	            staged_video,
   755	            provenance_out_path=out_path,

exec
/bin/zsh -lc "nl -ba remotion/remotion.config.ts | sed -n '1,180p'; rg -n \"enforce-audio|enforceAudio|audio track|audioTrack\" remotion/node_modules/@remotion remotion/node_modules/remotion -g '*.js' -g '*.d.ts' | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js | sed -n '1,120p'; rg -n \"enforce-audio-track|enforceAudioTrack\" remotion/node_modules/@remotion/cli -g '*.js' | head -n 120" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 41ms:
exec
/bin/zsh -lc 'rg -n "enforce-audio|audio-codec|codec|pixel-format|--fps|--height|--width|npx.*remotion|remotion.*render" astrid/packs/rendering/backends/remotion/run.py tests/packs/rendering/test_remotion* remotion/remotion.config.ts | head -n 360' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 50ms:
tests/packs/rendering/test_remotion_locking.py:79:def test_lock_is_held_during_registry_generation_and_remotion_render(
tests/packs/rendering/test_remotion_locking.py:85:    real_lock = remotion_lock.remotion_render_lock
tests/packs/rendering/test_remotion_locking.py:97:    monkeypatch.setattr(remotion_lock, "remotion_render_lock", observed_lock)
tests/packs/rendering/test_remotion_locking.py:103:        assert remotion_lock.remotion_render_lock_held()
tests/packs/rendering/test_remotion_locking.py:122:        assert remotion_lock.remotion_render_lock_held()
tests/packs/rendering/test_remotion_locking.py:128:            assert normalized[:3] == ["npx", "remotion", "render"]
tests/packs/rendering/test_remotion_locking.py:143:def test_two_concurrent_remotion_renders_serialize(
tests/packs/rendering/test_remotion_locking.py:188:def test_gen_types_entrypoint_uses_the_remotion_render_lock(
tests/packs/rendering/test_remotion_locking.py:199:        writer_lock_states.append(remotion_lock.remotion_render_lock_held())
tests/packs/rendering/test_remotion_locking.py:232:        assert remotion_lock.remotion_render_lock_held()
tests/packs/rendering/test_remotion_locking.py:242:    monkeypatch.setattr(remotion, "_execute_remotion_locked", render_with_internal_writer)
tests/packs/rendering/test_remotion_locking.py:250:def test_remotion_render_lock_releases_after_failure(
tests/packs/rendering/test_remotion_locking.py:269:    assert not remotion_lock.remotion_render_lock_held()
tests/packs/rendering/test_remotion_locking.py:270:    with remotion_lock.remotion_render_lock():
tests/packs/rendering/test_remotion_locking.py:271:        assert remotion_lock.remotion_render_lock_held()
tests/packs/rendering/test_remotion_locking.py:274:def test_remotion_render_lock_rejects_recursive_acquisition(
tests/packs/rendering/test_remotion_locking.py:284:    with remotion_lock.remotion_render_lock():
tests/packs/rendering/test_remotion_locking.py:286:            with remotion_lock.remotion_render_lock():
tests/packs/rendering/test_remotion_element_generation.py:36:        # (npx remotion render). The invariant we still enforce: AA's own
astrid/packs/rendering/backends/remotion/run.py:278:    if remotion_lock.remotion_render_lock_held():
astrid/packs/rendering/backends/remotion/run.py:281:    with remotion_lock.remotion_render_lock():
astrid/packs/rendering/backends/remotion/run.py:309:    env.update(remotion_lock.remotion_render_lock_child_env())
astrid/packs/rendering/backends/remotion/run.py:613:    with remotion_lock.remotion_render_lock():
astrid/packs/rendering/backends/remotion/run.py:1020:                    audio_codec=canonical.audio_codec or "aac",
astrid/packs/rendering/backends/remotion/run.py:1105:            audio_codec=declared_profile.audio_codec or "aac",
tests/packs/rendering/test_remotion_backend.py:219:        if normalized[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:238:        result = remotion.render(
tests/packs/rendering/test_remotion_backend.py:251:        remotion._render_provenance_sidecar_path(output_path).read_text(
tests/packs/rendering/test_remotion_backend.py:270:        video_codec="h264",
tests/packs/rendering/test_remotion_backend.py:298:        mock.patch.object(remotion, "validate_render_result"),
tests/packs/rendering/test_remotion_backend.py:300:        result = remotion._protocol_render(request, workspace=tmp_path)
tests/packs/rendering/test_remotion_backend.py:321:        "theme": remotion._resolved_theme_for_render(timeline_path, fallback_theme),
tests/packs/rendering/test_remotion_backend.py:559:                elif command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:570:                render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:580:                render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:592:                render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:602:                render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:613:                render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:637:                if command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:648:                result = render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:656:            provenance_path = render_remotion._render_provenance_sidecar_path(out_path.resolve())
tests/packs/rendering/test_remotion_backend.py:669:        self.assertEqual(remotion_cmd[:3], ["npx", "remotion", "render"])
tests/packs/rendering/test_remotion_backend.py:731:                if command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:751:                render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:760:                render_remotion._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
tests/packs/rendering/test_remotion_backend.py:807:                if command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:826:                    render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:839:            self.assertFalse(render_remotion._render_provenance_sidecar_path(out_path.resolve()).exists())
tests/packs/rendering/test_remotion_backend.py:860:                if command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:868:                result = render_remotion.render(
tests/packs/rendering/test_remotion_backend.py:876:            sidecar_path = render_remotion._render_provenance_sidecar_path(out_path.resolve())
tests/packs/rendering/test_remotion_backend.py:897:    def test_remotion_render_env_is_explicit_not_host_inherited(self) -> None:
tests/packs/rendering/test_remotion_backend.py:906:                if command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py:924:                render_remotion.render(

 succeeded in 150ms:
     1	"use strict";
     2	Object.defineProperty(exports, "__esModule", { value: true });
     3	exports.enforceAudioOption = void 0;
     4	const jsx_runtime_1 = require("react/jsx-runtime");
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
    19	                value: true,
    20	            };
    21	        }
    22	        if (enforceAudioTrackState !== DEFAULT_ENFORCE_AUDIO_TRACK) {
    23	            return {
    24	                source: 'config',
    25	                value: enforceAudioTrackState,
    26	            };
    27	        }
    28	        return {
    29	            source: 'default',
    30	            value: DEFAULT_ENFORCE_AUDIO_TRACK,
    31	        };
    32	    },
    33	    setConfig: (value) => {
    34	        enforceAudioTrackState = value;
    35	    },
    36	    id: cliFlag,
    37	};

exec
/bin/zsh -lc 'rg -n -C 12 "real.*remotion|smoke|skipif|fixture render|ffprobe_metadata_strict" tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py tests/packs/rendering/test_builtin_registration.py | tail -n 320' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n \"setCodec|setPixelFormat|setAudioCodec|setAudioBitrate|setEnforceAudioTrack|setVideoBitrate|setCrf|setSampleRate|audio.*rate\" remotion -g '*.ts' -g '*.tsx' -g '"'!node_modules'"' | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n \"DEFAULT_CODEC|default.*codec|codec.*default|pixelFormat.*default|audioCodec.*default|DEFAULT_PIXEL|DEFAULT_AUDIO\" remotion/node_modules/@remotion/renderer/dist remotion/node_modules/@remotion/cli/dist -g '*.js' | head -n 320" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n \"sample-rate|audio-sample|48000|44100|audio codec\" remotion/node_modules/@remotion/renderer/dist remotion/node_modules/@remotion/cli/dist -g '*.js' | head -n 320" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 161ms:
 succeeded in 249ms:
tests/packs/rendering/test_remotion_render_contract.py-39-        )
tests/packs/rendering/test_remotion_render_contract.py-40-        self.assertIsNotNone(match, "Root.tsx must import types from ./types.augmentations")
tests/packs/rendering/test_remotion_render_contract.py-41-        imported = {name.strip() for name in match.group(1).split(",") if name.strip()}
tests/packs/rendering/test_remotion_render_contract.py-42-
tests/packs/rendering/test_remotion_render_contract.py-43-        aug_src = aug_path.read_text(encoding="utf-8")
tests/packs/rendering/test_remotion_render_contract.py-44-        for name in imported:
tests/packs/rendering/test_remotion_render_contract.py-45-            self.assertRegex(
--
tests/packs/rendering/test_remotion_render_contract.py-58-            r"export default function \w+\(\)\s*\{\s*return null;\s*\}",
tests/packs/rendering/test_remotion_render_contract.py-59-        )
tests/packs/rendering/test_remotion_render_contract.py-60-        # It must render content via JSX markup keyed off the manifest params.
tests/packs/rendering/test_remotion_render_contract.py-61-        self.assertIn("content", src)
tests/packs/rendering/test_remotion_render_contract.py-62-        self.assertIn("AbsoluteFill", src)
tests/packs/rendering/test_remotion_render_contract.py-63-        self.assertIn("narrowParams", src)
tests/packs/rendering/test_remotion_render_contract.py-64-        self.assertRegex(src, r"<AbsoluteFill")
tests/packs/rendering/test_remotion_render_contract.py-65-
tests/packs/rendering/test_remotion_render_contract.py-66-
tests/packs/rendering/test_remotion_render_contract.py-67-class RemotionTypecheckSmokeTest(unittest.TestCase):
tests/packs/rendering/test_remotion_render_contract.py-68-    def test_remotion_typecheck_when_dependencies_present(self) -> None:
tests/packs/rendering/test_remotion_render_contract.py-69-        if not (REMOTION / "node_modules").is_dir():
tests/packs/rendering/test_remotion_render_contract.py:70:            self.skipTest("remotion/node_modules absent; typecheck smoke skipped")
tests/packs/rendering/test_remotion_render_contract.py-71-        # The typecheck depends on the generated augmentation surface
tests/packs/rendering/test_remotion_render_contract.py-72-        # (`types.augmentations.ts`, gitignored). A checkout that has not run
tests/packs/rendering/test_remotion_render_contract.py-73-        # the augmentation generation step cannot typecheck; skip rather than
tests/packs/rendering/test_remotion_render_contract.py-74-        # report a repo defect for a missing generated artifact.
tests/packs/rendering/test_remotion_render_contract.py-75-        if not (REMOTION / "src" / "types.augmentations.ts").is_file():
tests/packs/rendering/test_remotion_render_contract.py-76-            self.skipTest(
tests/packs/rendering/test_remotion_render_contract.py-77-                "remotion/src/types.augmentations.ts absent (gitignored generated artifact); "
tests/packs/rendering/test_remotion_render_contract.py:78:                "typecheck smoke skipped"
tests/packs/rendering/test_remotion_render_contract.py-79-            )
tests/packs/rendering/test_remotion_render_contract.py-80-        result = subprocess.run(
tests/packs/rendering/test_remotion_render_contract.py-81-            ["npm", "run", "typecheck"],
tests/packs/rendering/test_remotion_render_contract.py-82-            cwd=str(REMOTION),
tests/packs/rendering/test_remotion_render_contract.py-83-            capture_output=True,
tests/packs/rendering/test_remotion_render_contract.py-84-            text=True,
tests/packs/rendering/test_remotion_render_contract.py-85-            check=False,
tests/packs/rendering/test_remotion_render_contract.py-86-        )
tests/packs/rendering/test_remotion_render_contract.py-87-        self.assertEqual(
tests/packs/rendering/test_remotion_render_contract.py-88-            result.returncode,
tests/packs/rendering/test_remotion_render_contract.py-89-            0,
tests/packs/rendering/test_remotion_render_contract.py-90-            msg=f"remotion typecheck failed:\n{result.stdout}\n{result.stderr}",
--
tests/packs/rendering/test_builtin_registration.py-2-
tests/packs/rendering/test_builtin_registration.py-3-import builtins
tests/packs/rendering/test_builtin_registration.py-4-import importlib
tests/packs/rendering/test_builtin_registration.py-5-import json
tests/packs/rendering/test_builtin_registration.py-6-import shutil
tests/packs/rendering/test_builtin_registration.py-7-import subprocess
tests/packs/rendering/test_builtin_registration.py-8-import threading
tests/packs/rendering/test_builtin_registration.py-9-from pathlib import Path
tests/packs/rendering/test_builtin_registration.py-10-from unittest import mock
tests/packs/rendering/test_builtin_registration.py-11-
tests/packs/rendering/test_builtin_registration.py-12-import pytest
tests/packs/rendering/test_builtin_registration.py-13-
tests/packs/rendering/test_builtin_registration.py:14:from astrid.core.media import ffprobe_metadata_strict
tests/packs/rendering/test_builtin_registration.py-15-from astrid.core.pack.validate import validate_pack
tests/packs/rendering/test_builtin_registration.py-16-from astrid.core.rendering.contracts import RenderRequest, RenderResult, SCHEMA_VERSION
tests/packs/rendering/test_builtin_registration.py-17-from astrid.core.rendering.registry import load_default_registries
tests/packs/rendering/test_builtin_registration.py-18-from astrid.core.rendering.transport import CommandTransport
tests/packs/rendering/test_builtin_registration.py-19-
tests/packs/rendering/test_builtin_registration.py-20-
tests/packs/rendering/test_builtin_registration.py-21-ROOT = Path(__file__).resolve().parents[3]
tests/packs/rendering/test_builtin_registration.py-22-RENDERING_PACK = ROOT / "astrid" / "packs" / "rendering"
tests/packs/rendering/test_builtin_registration.py-23-REMOTION_PROJECT = ROOT / "remotion"
tests/packs/rendering/test_builtin_registration.py-24-BACKEND_MODULE_PREFIXES = (
tests/packs/rendering/test_builtin_registration.py-25-    "astrid.packs.rendering.backends.remotion",
tests/packs/rendering/test_builtin_registration.py-26-    "astrid.packs.rendering.backends.ffmpeg",
--
tests/packs/rendering/test_builtin_registration.py-183-        ("ffmpeg", "ffprobe"),
tests/packs/rendering/test_builtin_registration.py-184-    ]
tests/packs/rendering/test_builtin_registration.py-185-    for candidate in resolved:
tests/packs/rendering/test_builtin_registration.py-186-        assert candidate.pack_id == "rendering"
tests/packs/rendering/test_builtin_registration.py-187-        assert candidate.source_kind == "source"
tests/packs/rendering/test_builtin_registration.py-188-        assert candidate.execution_eligible is True
tests/packs/rendering/test_builtin_registration.py-189-        assert candidate.manifest.command == ("python3", "run.py")
tests/packs/rendering/test_builtin_registration.py-190-        assert (candidate.pack_root / candidate.manifest.command[1]).is_file()
tests/packs/rendering/test_builtin_registration.py-191-
tests/packs/rendering/test_builtin_registration.py-192-
tests/packs/rendering/test_builtin_registration.py-193-def test_real_ffmpeg_render_through_registered_backend(tmp_path: Path) -> None:
tests/packs/rendering/test_builtin_registration.py-194-    assert shutil.which("ffmpeg") is not None, (
tests/packs/rendering/test_builtin_registration.py:195:        "required FFmpeg smoke dependency is unavailable: ffmpeg executable"
tests/packs/rendering/test_builtin_registration.py-196-    )
tests/packs/rendering/test_builtin_registration.py-197-    assert shutil.which("ffprobe") is not None, (
tests/packs/rendering/test_builtin_registration.py:198:        "required FFmpeg smoke dependency is unavailable: ffprobe executable"
tests/packs/rendering/test_builtin_registration.py-199-    )
tests/packs/rendering/test_builtin_registration.py-200-    source_path = tmp_path / "source.mp4"
tests/packs/rendering/test_builtin_registration.py-201-    subprocess.run(
tests/packs/rendering/test_builtin_registration.py-202-        [
tests/packs/rendering/test_builtin_registration.py-203-            "ffmpeg",
tests/packs/rendering/test_builtin_registration.py-204-            "-hide_banner",
tests/packs/rendering/test_builtin_registration.py-205-            "-loglevel",
tests/packs/rendering/test_builtin_registration.py-206-            "error",
tests/packs/rendering/test_builtin_registration.py-207-            "-y",
tests/packs/rendering/test_builtin_registration.py-208-            "-f",
tests/packs/rendering/test_builtin_registration.py-209-            "lavfi",
tests/packs/rendering/test_builtin_registration.py-210-            "-i",
--
tests/packs/rendering/test_builtin_registration.py-222-    )
tests/packs/rendering/test_builtin_registration.py-223-    timeline_path, assets_path = _write_media_timeline(
tests/packs/rendering/test_builtin_registration.py-224-        tmp_path,
tests/packs/rendering/test_builtin_registration.py-225-        source_path,
tests/packs/rendering/test_builtin_registration.py-226-        duration=0.5,
tests/packs/rendering/test_builtin_registration.py-227-    )
tests/packs/rendering/test_builtin_registration.py-228-    request_path = tmp_path / "request.json"
tests/packs/rendering/test_builtin_registration.py-229-    result_path = tmp_path / "result.json"
tests/packs/rendering/test_builtin_registration.py-230-    request = _request(
tests/packs/rendering/test_builtin_registration.py-231-        timeline_path,
tests/packs/rendering/test_builtin_registration.py-232-        assets_path,
tests/packs/rendering/test_builtin_registration.py-233-        backend="rendering.ffmpeg",
tests/packs/rendering/test_builtin_registration.py:234:        output_name="ffmpeg-smoke.mp4",
tests/packs/rendering/test_builtin_registration.py-235-    )
tests/packs/rendering/test_builtin_registration.py-236-    _write_request(request_path, request)
tests/packs/rendering/test_builtin_registration.py-237-    renderers, _planners, _finalizers = _registries()
tests/packs/rendering/test_builtin_registration.py-238-    candidate = renderers.get("rendering.ffmpeg")
tests/packs/rendering/test_builtin_registration.py-239-
tests/packs/rendering/test_builtin_registration.py-240-    result = CommandTransport(candidate.id).run(
tests/packs/rendering/test_builtin_registration.py-241-        "render",
tests/packs/rendering/test_builtin_registration.py-242-        candidate.manifest.command,
tests/packs/rendering/test_builtin_registration.py-243-        request_path=request_path,
tests/packs/rendering/test_builtin_registration.py-244-        result_path=result_path,
tests/packs/rendering/test_builtin_registration.py-245-        cwd=candidate.pack_root,
tests/packs/rendering/test_builtin_registration.py-246-        required_binaries=candidate.manifest.required_binaries,
tests/packs/rendering/test_builtin_registration.py-247-    )
tests/packs/rendering/test_builtin_registration.py-248-
tests/packs/rendering/test_builtin_registration.py-249-    assert isinstance(result, RenderResult)
tests/packs/rendering/test_builtin_registration.py-250-    video_path = tmp_path / result.video.path
tests/packs/rendering/test_builtin_registration.py-251-    assert video_path.is_file()
tests/packs/rendering/test_builtin_registration.py-252-    assert video_path.stat().st_size > 0
tests/packs/rendering/test_builtin_registration.py-253-    assert result.video.duration_frames == 5
tests/packs/rendering/test_builtin_registration.py-254-    assert result.backend_fragments["rendering.ffmpeg"]["renderer"] == "ffmpeg"
tests/packs/rendering/test_builtin_registration.py:255:    probe = ffprobe_metadata_strict(video_path)
tests/packs/rendering/test_builtin_registration.py-256-    assert probe.has_video_stream is True
tests/packs/rendering/test_builtin_registration.py-257-    assert probe.width == 160
tests/packs/rendering/test_builtin_registration.py-258-    assert probe.height == 90
tests/packs/rendering/test_builtin_registration.py-259-    assert probe.duration_seconds is not None and probe.duration_seconds > 0
tests/packs/rendering/test_builtin_registration.py:260:    assert not list(tmp_path.glob(".ffmpeg-smoke.mp4.*"))
tests/packs/rendering/test_builtin_registration.py-261-
tests/packs/rendering/test_builtin_registration.py-262-
tests/packs/rendering/test_builtin_registration.py:263:def test_real_remotion_render_through_registered_backend(
tests/packs/rendering/test_builtin_registration.py-264-    tmp_path: Path,
tests/packs/rendering/test_builtin_registration.py-265-    monkeypatch: pytest.MonkeyPatch,
tests/packs/rendering/test_builtin_registration.py-266-) -> None:
tests/packs/rendering/test_builtin_registration.py-267-    missing = _missing_remotion_dependencies()
tests/packs/rendering/test_builtin_registration.py-268-    if missing:
tests/packs/rendering/test_builtin_registration.py-269-        pytest.skip(
tests/packs/rendering/test_builtin_registration.py:270:            "Remotion backend smoke skipped: missing optional dependencies: "
tests/packs/rendering/test_builtin_registration.py-271-            + ", ".join(missing)
tests/packs/rendering/test_builtin_registration.py-272-        )
tests/packs/rendering/test_builtin_registration.py-273-
tests/packs/rendering/test_builtin_registration.py-274-    ffmpeg = shutil.which("ffmpeg")
tests/packs/rendering/test_builtin_registration.py-275-    ffprobe = shutil.which("ffprobe")
tests/packs/rendering/test_builtin_registration.py-276-    if ffmpeg is None or ffprobe is None:
tests/packs/rendering/test_builtin_registration.py-277-        missing_media = [
tests/packs/rendering/test_builtin_registration.py-278-            f"{binary} executable"
tests/packs/rendering/test_builtin_registration.py-279-            for binary, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))
tests/packs/rendering/test_builtin_registration.py-280-            if path is None
tests/packs/rendering/test_builtin_registration.py-281-        ]
tests/packs/rendering/test_builtin_registration.py-282-        pytest.skip(
tests/packs/rendering/test_builtin_registration.py:283:            "Remotion backend smoke skipped: missing optional media dependencies: "
tests/packs/rendering/test_builtin_registration.py-284-            + ", ".join(missing_media)
tests/packs/rendering/test_builtin_registration.py-285-        )
tests/packs/rendering/test_builtin_registration.py-286-
tests/packs/rendering/test_builtin_registration.py-287-    source_path = tmp_path / "source.mp4"
tests/packs/rendering/test_builtin_registration.py-288-    subprocess.run(
tests/packs/rendering/test_builtin_registration.py-289-        [
tests/packs/rendering/test_builtin_registration.py-290-            ffmpeg,
tests/packs/rendering/test_builtin_registration.py-291-            "-hide_banner",
tests/packs/rendering/test_builtin_registration.py-292-            "-loglevel",
tests/packs/rendering/test_builtin_registration.py-293-            "error",
tests/packs/rendering/test_builtin_registration.py-294-            "-y",
tests/packs/rendering/test_builtin_registration.py-295-            "-f",
--
tests/packs/rendering/test_builtin_registration.py-307-        capture_output=True,
tests/packs/rendering/test_builtin_registration.py-308-        text=True,
tests/packs/rendering/test_builtin_registration.py-309-    )
tests/packs/rendering/test_builtin_registration.py-310-    timeline_path, assets_path = _write_media_timeline(
tests/packs/rendering/test_builtin_registration.py-311-        tmp_path,
tests/packs/rendering/test_builtin_registration.py-312-        source_path,
tests/packs/rendering/test_builtin_registration.py-313-        duration=0.5,
tests/packs/rendering/test_builtin_registration.py-314-    )
tests/packs/rendering/test_builtin_registration.py-315-    request = _request(
tests/packs/rendering/test_builtin_registration.py-316-        timeline_path,
tests/packs/rendering/test_builtin_registration.py-317-        assets_path,
tests/packs/rendering/test_builtin_registration.py-318-        backend="rendering.remotion",
tests/packs/rendering/test_builtin_registration.py:319:        output_name="remotion-smoke.mp4",
tests/packs/rendering/test_builtin_registration.py-320-        backend_settings={"project_dir": str(REMOTION_PROJECT)},
tests/packs/rendering/test_builtin_registration.py-321-    )
tests/packs/rendering/test_builtin_registration.py-322-    renderers, _planners, _finalizers = _registries()
tests/packs/rendering/test_builtin_registration.py-323-    candidate = renderers.get("rendering.remotion")
tests/packs/rendering/test_builtin_registration.py-324-
tests/packs/rendering/test_builtin_registration.py-325-    remotion_backend = importlib.import_module(
tests/packs/rendering/test_builtin_registration.py-326-        "astrid.packs.rendering.backends.remotion.run"
tests/packs/rendering/test_builtin_registration.py-327-    )
tests/packs/rendering/test_builtin_registration.py-328-    asset_servers: list[object] = []
tests/packs/rendering/test_builtin_registration.py:329:    real_server = remotion_backend.InvocationAssetServer
tests/packs/rendering/test_builtin_registration.py-330-
tests/packs/rendering/test_builtin_registration.py-331-    class TrackedAssetServer(real_server):
tests/packs/rendering/test_builtin_registration.py-332-        def __init__(self, staging_dir: str | Path) -> None:
tests/packs/rendering/test_builtin_registration.py-333-            super().__init__(staging_dir)
tests/packs/rendering/test_builtin_registration.py-334-            asset_servers.append(self)
tests/packs/rendering/test_builtin_registration.py-335-
tests/packs/rendering/test_builtin_registration.py-336-    monkeypatch.setattr(remotion_backend, "InvocationAssetServer", TrackedAssetServer)
tests/packs/rendering/test_builtin_registration.py-337-    before_threads = {
tests/packs/rendering/test_builtin_registration.py-338-        thread.ident
tests/packs/rendering/test_builtin_registration.py-339-        for thread in threading.enumerate()
tests/packs/rendering/test_builtin_registration.py-340-        if thread.name.startswith("astrid-asset-server-")
tests/packs/rendering/test_builtin_registration.py-341-    }
--
tests/packs/rendering/test_builtin_registration.py-366-            assert server.thread is None or not server.thread.is_alive()
tests/packs/rendering/test_builtin_registration.py-367-            assert not server.staging_dir.exists()
tests/packs/rendering/test_builtin_registration.py-368-
tests/packs/rendering/test_builtin_registration.py-369-    if render_error is not None:
tests/packs/rendering/test_builtin_registration.py-370-        message = str(render_error)
tests/packs/rendering/test_builtin_registration.py-371-        environment_failures = (
tests/packs/rendering/test_builtin_registration.py-372-            "Failed to launch the browser process",
tests/packs/rendering/test_builtin_registration.py-373-            "MachPortRendezvous",
tests/packs/rendering/test_builtin_registration.py-374-            "Permission denied (1100)",
tests/packs/rendering/test_builtin_registration.py-375-        )
tests/packs/rendering/test_builtin_registration.py-376-        if any(reason in message for reason in environment_failures):
tests/packs/rendering/test_builtin_registration.py-377-            pytest.skip(
tests/packs/rendering/test_builtin_registration.py:378:                "Remotion backend smoke skipped: local browser/runtime is unavailable: "
tests/packs/rendering/test_builtin_registration.py-379-                + message.splitlines()[-1]
tests/packs/rendering/test_builtin_registration.py-380-            )
tests/packs/rendering/test_builtin_registration.py-381-        raise render_error
tests/packs/rendering/test_builtin_registration.py-382-
tests/packs/rendering/test_builtin_registration.py-383-    assert isinstance(result, RenderResult)
tests/packs/rendering/test_builtin_registration.py-384-    video_path = tmp_path / result.video.path
tests/packs/rendering/test_builtin_registration.py-385-    assert video_path.is_file()
tests/packs/rendering/test_builtin_registration.py-386-    assert video_path.stat().st_size > 0
tests/packs/rendering/test_builtin_registration.py-387-    assert result.backend_fragments["rendering.remotion"]["renderer"] == "remotion"
--
tests/packs/rendering/test_remotion_backend.py-22-    RenderRequest,
tests/packs/rendering/test_remotion_backend.py-23-    RenderResult,
tests/packs/rendering/test_remotion_backend.py-24-    RendererManifest,
tests/packs/rendering/test_remotion_backend.py-25-    SCHEMA_VERSION,
tests/packs/rendering/test_remotion_backend.py-26-    SupportReport,
tests/packs/rendering/test_remotion_backend.py-27-)
tests/packs/rendering/test_remotion_backend.py-28-from astrid.core.rendering.transport import CommandTransport
tests/packs/rendering/test_remotion_backend.py-29-from astrid.packs.rendering.backends.remotion import run as remotion
tests/packs/rendering/test_remotion_backend.py-30-from astrid.packs.rendering.executors.render import run as facade
tests/packs/rendering/test_remotion_backend.py-31-
tests/packs/rendering/test_remotion_backend.py-32-
tests/packs/rendering/test_remotion_backend.py-33-ROOT = Path(__file__).resolve().parents[3]
tests/packs/rendering/test_remotion_backend.py:34:LOCAL_EFFECT_SMOKE_FIXTURE = ROOT / "tests" / "fixtures" / "local_effect_smoke"
tests/packs/rendering/test_remotion_backend.py-35-render_remotion = remotion
tests/packs/rendering/test_remotion_backend.py-36-
tests/packs/rendering/test_remotion_backend.py-37-
tests/packs/rendering/test_remotion_backend.py-38-def _write_fake_remotion_output(command: list[str]) -> Path:
tests/packs/rendering/test_remotion_backend.py-39-    output = Path(command[command.index("--output") + 1])
tests/packs/rendering/test_remotion_backend.py-40-    output.parent.mkdir(parents=True, exist_ok=True)
tests/packs/rendering/test_remotion_backend.py-41-    output.write_bytes(b"fake-remotion-video")
tests/packs/rendering/test_remotion_backend.py-42-    return output
tests/packs/rendering/test_remotion_backend.py-43-
tests/packs/rendering/test_remotion_backend.py-44-
tests/packs/rendering/test_remotion_backend.py-45-def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
tests/packs/rendering/test_remotion_backend.py-46-    timeline_path = tmp_path / "hype.timeline.json"
--
tests/packs/rendering/test_remotion_backend.py-420-            kind="effects",
tests/packs/rendering/test_remotion_backend.py-421-            root=root,
tests/packs/rendering/test_remotion_backend.py-422-            source="pack:test",
tests/packs/rendering/test_remotion_backend.py-423-            editable=False,
tests/packs/rendering/test_remotion_backend.py-424-            priority=50,
tests/packs/rendering/test_remotion_backend.py-425-            component=root / "component.tsx",
tests/packs/rendering/test_remotion_backend.py-426-            schema={},
tests/packs/rendering/test_remotion_backend.py-427-            defaults={},
tests/packs/rendering/test_remotion_backend.py-428-            metadata={},
tests/packs/rendering/test_remotion_backend.py-429-            assets=(ElementAsset(name="badge", path=Path("assets/badge.txt")),),
tests/packs/rendering/test_remotion_backend.py-430-        )
tests/packs/rendering/test_remotion_backend.py-431-
tests/packs/rendering/test_remotion_backend.py:432:    def _copy_local_effect_smoke_project(self, tmp: Path) -> tuple[Path, Path, Path, Path]:
tests/packs/rendering/test_remotion_backend.py-433-        project_root = tmp / "fixture-project"
tests/packs/rendering/test_remotion_backend.py-434-        shutil.copytree(LOCAL_EFFECT_SMOKE_FIXTURE, project_root)
tests/packs/rendering/test_remotion_backend.py-435-        project_dir, _composition_src = self._write_fake_remotion_project(tmp)
tests/packs/rendering/test_remotion_backend.py-436-        return (
tests/packs/rendering/test_remotion_backend.py-437-            project_root,
tests/packs/rendering/test_remotion_backend.py-438-            project_dir,
tests/packs/rendering/test_remotion_backend.py-439-            project_root / "hype.timeline.json",
tests/packs/rendering/test_remotion_backend.py-440-            project_root / "hype.assets.json",
tests/packs/rendering/test_remotion_backend.py-441-        )
tests/packs/rendering/test_remotion_backend.py-442-
tests/packs/rendering/test_remotion_backend.py-443-    def test_registry_generation_sets_theme_and_composition_env(self) -> None:
tests/packs/rendering/test_remotion_backend.py-444-        with tempfile.TemporaryDirectory(prefix="render-registry-") as tmp_text:
--
tests/packs/rendering/test_remotion_backend.py-832-                        theme_path=None,
tests/packs/rendering/test_remotion_backend.py-833-                    )
tests/packs/rendering/test_remotion_backend.py-834-
tests/packs/rendering/test_remotion_backend.py-835-            self.assertEqual(len(staged_roots_seen), 1)
tests/packs/rendering/test_remotion_backend.py-836-            self.assertFalse(staged_roots_seen[0].exists())
tests/packs/rendering/test_remotion_backend.py-837-            self.assertEqual(len(props_paths_seen), 1)
tests/packs/rendering/test_remotion_backend.py-838-            self.assertFalse(props_paths_seen[0].exists())
tests/packs/rendering/test_remotion_backend.py-839-            self.assertFalse(render_remotion._render_provenance_sidecar_path(out_path.resolve()).exists())
tests/packs/rendering/test_remotion_backend.py-840-
tests/packs/rendering/test_remotion_backend.py-841-    def test_render_provenance_matches_registry_and_local_overlay_discovery(self) -> None:
tests/packs/rendering/test_remotion_backend.py-842-        with tempfile.TemporaryDirectory(prefix="render-local-provenance-") as tmp_text:
tests/packs/rendering/test_remotion_backend.py-843-            tmp = Path(tmp_text)
tests/packs/rendering/test_remotion_backend.py:844:            project_root, project_dir, timeline_path, assets_path = self._copy_local_effect_smoke_project(tmp)
tests/packs/rendering/test_remotion_backend.py:845:            out_path = tmp / "fixture-smoke.mp4"
tests/packs/rendering/test_remotion_backend.py-846-            expected_pack_order = [
tests/packs/rendering/test_remotion_backend.py-847-                {
tests/packs/rendering/test_remotion_backend.py-848-                    "id": discovered.id,
tests/packs/rendering/test_remotion_backend.py-849-                    "source_kind": discovered.source_kind,
tests/packs/rendering/test_remotion_backend.py-850-                    "priority_index": discovered.priority_index,
tests/packs/rendering/test_remotion_backend.py-851-                    "root": str(discovered.pack_dir),
tests/packs/rendering/test_remotion_backend.py-852-                }
tests/packs/rendering/test_remotion_backend.py-853-                for discovered in discover_pack_metadata(project_root=project_root)
tests/packs/rendering/test_remotion_backend.py-854-            ]
tests/packs/rendering/test_remotion_backend.py-855-            expected_registry = render_remotion.load_default_registry(project_root=project_root)
tests/packs/rendering/test_remotion_backend.py:856:            expected_effect = expected_registry.get("effects", "fixture-smoke-effect")
tests/packs/rendering/test_remotion_backend.py-857-
tests/packs/rendering/test_remotion_backend.py-858-            def fake_run(cmd, **kwargs):
tests/packs/rendering/test_remotion_backend.py-859-                command = [str(part) for part in cmd]
tests/packs/rendering/test_remotion_backend.py-860-                if command[:3] == ["npx", "remotion", "render"]:
tests/packs/rendering/test_remotion_backend.py-861-                    _write_fake_remotion_output(command)
tests/packs/rendering/test_remotion_backend.py-862-                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
tests/packs/rendering/test_remotion_backend.py-863-
tests/packs/rendering/test_remotion_backend.py-864-            with (
tests/packs/rendering/test_remotion_backend.py-865-                mock.patch.object(render_remotion, "REPO_ROOT", project_root),
tests/packs/rendering/test_remotion_backend.py-866-                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
tests/packs/rendering/test_remotion_backend.py-867-            ):
tests/packs/rendering/test_remotion_backend.py-868-                result = render_remotion.render(

 succeeded in 229ms:
remotion/node_modules/@remotion/renderer/dist/validate-output-filename.js:29:        throw new TypeError(`When using the ${codec} codec with the ${resolvedAudioCodec} audio codec, the output filename must end in one of the following: ${acceptableExtensions.join(', ')}.`);
remotion/node_modules/@remotion/cli/dist/render-flows/still.js:129:        sampleRate: 48000,
remotion/node_modules/@remotion/renderer/dist/render-media.js:655:        sampleRate: (_d = sampleRate !== null && sampleRate !== void 0 ? sampleRate : composition.defaultSampleRate) !== null && _d !== void 0 ? _d : 48000,
remotion/node_modules/@remotion/renderer/dist/select-composition.js:40:        sampleRate: 48000,
remotion/node_modules/@remotion/renderer/dist/select-composition.js:128:            sampleRate: 48000,
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:5:const cliFlag = 'sample-rate';
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:6:let currentSampleRate = 48000;
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:10:    description: () => (jsx_runtime_1.jsxs(jsx_runtime_1.Fragment, { children: ["Controls the sample rate of the output audio. The default is", ' ', jsx_runtime_1.jsx("code", { children: "48000" }),
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:13:    docLink: 'https://www.remotion.dev/docs/sample-rate',
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:14:    type: 48000,
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:19:        if (currentSampleRate !== 48000) {
remotion/node_modules/@remotion/renderer/dist/options/sample-rate.js:28:        return { value: 48000, source: 'default' };
remotion/node_modules/@remotion/renderer/dist/assets/inline-audio-mixing.js:58: * results like 244799.99999999997 instead of 244800 (5.1 * 48000).
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:45:    throw new Error('unknown audio codec: ' + audioCodec);
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:110:    throw new Error(`Unsupported audio codec: ${audioCodec}`);
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:122:                    throw new Error(`The codec is ${codec} but the audio codec derived from --${separate_audio_1.separateAudioOption.cliFlag} is ${derivedFromSeparateAudioToExtension}. The only supported codecs are: ${exports.supportedAudioCodecs[codec].join(', ')}`);
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:132:            throw new Error(`The audio codec derived from --${separate_audio_1.separateAudioOption.cliFlag} is ${derivedFromSeparateAudioToExtension}, but does not match the audio codec derived from the "Prefer lossless" option (${selected}). Remove any conflicting options.`);
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:144:        throw new Error(`The audio codec derived from --${separate_audio_1.separateAudioOption.cliFlag} is ${derivedFromSeparateAudioToExtension}, but does not match the audio codec derived from your ${exports.audioCodecOption.name} setting (${setting}). Remove any conflicting options.`);
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:188:    description: () => `Set the format of the audio that is embedded in the video. Not all codec and audio codec combinations are supported and certain combinations require a certain file extension and container format. See the table in the docs to see possible combinations.`,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js:29:const sample_rate_1 = require("./sample-rate");
remotion/node_modules/@remotion/renderer/dist/options/index.js:78:const sample_rate_1 = require("./sample-rate");
remotion/node_modules/@remotion/renderer/dist/options/prefer-lossless.js:10:    description: () => (jsx_runtime_1.jsxs(jsx_runtime_1.Fragment, { children: ["Uses a lossless audio codec, if one is available for the codec. If you set",
remotion/node_modules/@remotion/renderer/dist/render-still.js:172:        sampleRate: 48000,
remotion/node_modules/@remotion/renderer/dist/render-still.js:273:            sampleRate: 48000,
remotion/node_modules/@remotion/renderer/dist/render-frames.js:419:        sampleRate: (_a = sampleRate !== null && sampleRate !== void 0 ? sampleRate : composition.defaultSampleRate) !== null && _a !== void 0 ? _a : 48000,
remotion/node_modules/@remotion/renderer/dist/combine-chunks.js:174:        sampleRate: (_k = options.sampleRate) !== null && _k !== void 0 ? _k : 48000,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:71:        throw new Error('The output format has neither audio nor video. This can happen if you are rendering an audio codec and the output file has no audio or the muted flag was passed.');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:149:            throw new TypeError('exporting audio but has no audio codec name. Report this in the Remotion repo.');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:349:        sampleRate: sampleRate !== null && sampleRate !== void 0 ? sampleRate : 48000,
remotion/node_modules/@remotion/renderer/dist/get-compositions.js:39:        sampleRate: 48000,
remotion/node_modules/@remotion/renderer/dist/get-compositions.js:120:            sampleRate: 48000,

 succeeded in 316ms:
remotion/node_modules/@remotion/renderer/dist/validate-output-filename.js:7:    if (!file_extensions_1.defaultFileExtensionMap[codec]) {
remotion/node_modules/@remotion/renderer/dist/validate-output-filename.js:8:        throw new TypeError(`The codec "${codec}" is not supported. Supported codecs are: ${Object.keys(file_extensions_1.defaultFileExtensionMap).join(', ')}`);
remotion/node_modules/@remotion/renderer/dist/validate-output-filename.js:10:    const map = file_extensions_1.defaultFileExtensionMap[codec];
remotion/node_modules/@remotion/renderer/dist/validate-output-filename.js:19:            throw new TypeError(`When using the ${codec} codec, the output filename must end in .${map.default}.`);
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js:124:        codec: defaultCodec !== null && defaultCodec !== void 0 ? defaultCodec : 'h264',
remotion/node_modules/@remotion/renderer/dist/render-media.js:60:    const pixelFormat = (_a = userPixelFormat !== null && userPixelFormat !== void 0 ? userPixelFormat : compositionWithPossibleUnevenDimensions.defaultPixelFormat) !== null && _a !== void 0 ? _a : pixel_format_1.DEFAULT_PIXEL_FORMAT;
remotion/node_modules/@remotion/renderer/dist/render-media.js:178:        ? node_path_1.default.join(workingDir, 'pre-encode.' + (0, get_extension_from_codec_1.getFileExtensionFromCodec)(codec, audioCodec))
remotion/node_modules/@remotion/renderer/dist/pixel-format.js:3:exports.validateSelectedPixelFormatAndCodecCombination = exports.validPixelFormatsForCodec = exports.DEFAULT_PIXEL_FORMAT = exports.validPixelFormats = void 0;
remotion/node_modules/@remotion/renderer/dist/pixel-format.js:14:exports.DEFAULT_PIXEL_FORMAT = 'yuv420p';
remotion/node_modules/@remotion/cli/dist/render-flows/render.js:281:        defaultExtension: renderer_1.RenderInternals.getFileExtensionFromCodec(codec, audioCodec),
remotion/node_modules/@remotion/renderer/dist/prespawn-ffmpeg.js:18:    const codec = (_b = options.codec) !== null && _b !== void 0 ? _b : codec_1.DEFAULT_CODEC;
remotion/node_modules/@remotion/renderer/dist/prespawn-ffmpeg.js:29:    const pixelFormat = (_c = options.pixelFormat) !== null && _c !== void 0 ? _c : pixel_format_1.DEFAULT_PIXEL_FORMAT;
remotion/node_modules/@remotion/renderer/dist/options/pixel-format.js:6:let currentPixelFormat = pixel_format_1.DEFAULT_PIXEL_FORMAT;
remotion/node_modules/@remotion/renderer/dist/options/pixel-format.js:15:    type: pixel_format_1.DEFAULT_PIXEL_FORMAT,
remotion/node_modules/@remotion/renderer/dist/options/pixel-format.js:23:        if (currentPixelFormat !== pixel_format_1.DEFAULT_PIXEL_FORMAT) {
remotion/node_modules/@remotion/renderer/dist/options/pixel-format.js:31:            value: pixel_format_1.DEFAULT_PIXEL_FORMAT,
remotion/node_modules/@remotion/renderer/dist/options/video-codec.js:29:        default: (_a = get_extension_from_codec_1.defaultCodecsForFileExtension[extension]) !== null && _a !== void 0 ? _a : null,
remotion/node_modules/@remotion/renderer/dist/options/video-codec.js:101:        return { value: codec_1.DEFAULT_CODEC, source: 'default' };
remotion/node_modules/@remotion/renderer/dist/options/browser-executable.js:10:    description: () => (jsx_runtime_1.jsx(jsx_runtime_1.Fragment, { children: "Set a custom Chrome or Chromium executable path. By default Remotion will try to find an existing version of Chrome on your system and if not found, it will download one. This flag is useful if you don't have Chrome installed in a standard location and you want to prevent downloading an additional browser or need support for the H264 codec." })),
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:3:exports.audioCodecOption = exports.getDefaultAudioCodec = exports.resolveAudioCodec = exports.getExtensionFromAudioCodec = exports.defaultAudioCodecs = exports.mapAudioCodecToFfmpegAudioCodecName = exports.supportedAudioCodecs = exports.validAudioCodecs = void 0;
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:150:    return exports.defaultAudioCodecs[codec][preferLossless ? 'lossless' : 'compressed'];
remotion/node_modules/@remotion/renderer/dist/client.js:39:    DEFAULT_PIXEL_FORMAT: pixel_format_1.DEFAULT_PIXEL_FORMAT,
remotion/node_modules/@remotion/renderer/dist/client.js:45:    defaultAudioCodecs: audio_codec_1.defaultAudioCodecs,
remotion/node_modules/@remotion/renderer/dist/client.js:46:    defaultCodecsForFileExtension: get_extension_from_codec_1.defaultCodecsForFileExtension,
remotion/node_modules/@remotion/renderer/dist/codec.js:3:exports.DEFAULT_CODEC = exports.validCodecs = void 0;
remotion/node_modules/@remotion/renderer/dist/codec.js:18:exports.DEFAULT_CODEC = 'h264';
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:81:        : node_path_1.default.join(assetsInfo.downloadMap.stitchFrames, `out.${(0, get_extension_from_codec_1.getFileExtensionFromCodec)(codec, resolvedAudioCodec)}`);
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:323:        codec: codec !== null && codec !== void 0 ? codec : codec_1.DEFAULT_CODEC,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:336:        pixelFormat: pixelFormat !== null && pixelFormat !== void 0 ? pixelFormat : pixel_format_1.DEFAULT_PIXEL_FORMAT,
remotion/node_modules/@remotion/renderer/dist/get-extension-from-codec.js:10:    const map = file_extensions_1.defaultFileExtensionMap[codec];
remotion/node_modules/@remotion/renderer/dist/get-extension-from-codec.js:18:    return map.forAudioCodec[audioCodec].default;
remotion/node_modules/@remotion/renderer/dist/get-extension-from-codec.js:23:    Object.keys(file_extensions_1.defaultFileExtensionMap).forEach((_codec) => {
remotion/node_modules/@remotion/renderer/dist/get-extension-from-codec.js:25:        const fileExtMap = file_extensions_1.defaultFileExtensionMap[codec];
remotion/node_modules/@remotion/renderer/dist/index.js:169:    DEFAULT_PIXEL_FORMAT: pixel_format_1.DEFAULT_PIXEL_FORMAT,
remotion/node_modules/@remotion/renderer/dist/index.js:172:    DEFAULT_CODEC: codec_1.DEFAULT_CODEC,
remotion/node_modules/@remotion/renderer/dist/index.js:186:    defaultCodecsForFileExtension: get_extension_from_codec_1.defaultCodecsForFileExtension,
remotion/node_modules/@remotion/renderer/dist/crf.js:20:    const val = defaultCrfMap[codec];

exec
/bin/zsh -lc "nl -ba tests/packs/rendering/test_builtin_registration.py | sed -n '263,400p'; nl -ba tests/packs/rendering/test_builtin_registration.py | sed -n '30,100p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   263	def test_real_remotion_render_through_registered_backend(
   264	    tmp_path: Path,
   265	    monkeypatch: pytest.MonkeyPatch,
   266	) -> None:
   267	    missing = _missing_remotion_dependencies()
   268	    if missing:
   269	        pytest.skip(
   270	            "Remotion backend smoke skipped: missing optional dependencies: "
   271	            + ", ".join(missing)
   272	        )
   273	
   274	    ffmpeg = shutil.which("ffmpeg")
   275	    ffprobe = shutil.which("ffprobe")
   276	    if ffmpeg is None or ffprobe is None:
   277	        missing_media = [
   278	            f"{binary} executable"
   279	            for binary, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))
   280	            if path is None
   281	        ]
   282	        pytest.skip(
   283	            "Remotion backend smoke skipped: missing optional media dependencies: "
   284	            + ", ".join(missing_media)
   285	        )
   286	
   287	    source_path = tmp_path / "source.mp4"
   288	    subprocess.run(
   289	        [
   290	            ffmpeg,
   291	            "-hide_banner",
   292	            "-loglevel",
   293	            "error",
   294	            "-y",
   295	            "-f",
   296	            "lavfi",
   297	            "-i",
   298	            "color=c=green:s=160x90:r=10:d=0.5",
   299	            "-c:v",
   300	            "libx264",
   301	            "-pix_fmt",
   302	            "yuv420p",
   303	            "-an",
   304	            str(source_path),
   305	        ],
   306	        check=True,
   307	        capture_output=True,
   308	        text=True,
   309	    )
   310	    timeline_path, assets_path = _write_media_timeline(
   311	        tmp_path,
   312	        source_path,
   313	        duration=0.5,
   314	    )
   315	    request = _request(
   316	        timeline_path,
   317	        assets_path,
   318	        backend="rendering.remotion",
   319	        output_name="remotion-smoke.mp4",
   320	        backend_settings={"project_dir": str(REMOTION_PROJECT)},
   321	    )
   322	    renderers, _planners, _finalizers = _registries()
   323	    candidate = renderers.get("rendering.remotion")
   324	
   325	    remotion_backend = importlib.import_module(
   326	        "astrid.packs.rendering.backends.remotion.run"
   327	    )
   328	    asset_servers: list[object] = []
   329	    real_server = remotion_backend.InvocationAssetServer
   330	
   331	    class TrackedAssetServer(real_server):
   332	        def __init__(self, staging_dir: str | Path) -> None:
   333	            super().__init__(staging_dir)
   334	            asset_servers.append(self)
   335	
   336	    monkeypatch.setattr(remotion_backend, "InvocationAssetServer", TrackedAssetServer)
   337	    before_threads = {
   338	        thread.ident
   339	        for thread in threading.enumerate()
   340	        if thread.name.startswith("astrid-asset-server-")
   341	    }
   342	
   343	    render_error: BaseException | None = None
   344	    result: RenderResult | None = None
   345	    try:
   346	        result = remotion_backend._protocol_render(
   347	            request.for_backend(candidate.id),
   348	            workspace=tmp_path,
   349	        )
   350	    except BaseException as exc:
   351	        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
   352	            raise
   353	        render_error = exc
   354	    finally:
   355	        assert not list(tmp_path.glob(".remotion-empty-assets-*"))
   356	        assert not list((tmp_path / "outputs").glob(".*.remotion-*"))
   357	        assert not (tmp_path / "outputs" / ".remotion-props.json").exists()
   358	        after_threads = {
   359	            thread.ident
   360	            for thread in threading.enumerate()
   361	            if thread.name.startswith("astrid-asset-server-")
   362	        }
   363	        assert after_threads == before_threads
   364	        for server in asset_servers:
   365	            assert server.port == 0
   366	            assert server.thread is None or not server.thread.is_alive()
   367	            assert not server.staging_dir.exists()
   368	
   369	    if render_error is not None:
   370	        message = str(render_error)
   371	        environment_failures = (
   372	            "Failed to launch the browser process",
   373	            "MachPortRendezvous",
   374	            "Permission denied (1100)",
   375	        )
   376	        if any(reason in message for reason in environment_failures):
   377	            pytest.skip(
   378	                "Remotion backend smoke skipped: local browser/runtime is unavailable: "
   379	                + message.splitlines()[-1]
   380	            )
   381	        raise render_error
   382	
   383	    assert isinstance(result, RenderResult)
   384	    video_path = tmp_path / result.video.path
   385	    assert video_path.is_file()
   386	    assert video_path.stat().st_size > 0
   387	    assert result.backend_fragments["rendering.remotion"]["renderer"] == "remotion"
    30	
    31	def _registries():
    32	    return load_default_registries(ROOT, include_installed=False)
    33	
    34	
    35	def _write_media_timeline(
    36	    root: Path,
    37	    source: Path,
    38	    *,
    39	    duration: float,
    40	    width: int = 160,
    41	    height: int = 90,
    42	    fps: int = 10,
    43	) -> tuple[Path, Path]:
    44	    timeline_path = root / "timeline.json"
    45	    assets_path = root / "assets.json"
    46	    timeline_path.write_text(
    47	        json.dumps(
    48	            {
    49	                "theme": "banodoco-default",
    50	                "theme_overrides": {
    51	                    "visual": {
    52	                        "canvas": {"width": width, "height": height, "fps": fps}
    53	                    }
    54	                },
    55	                "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
    56	                "clips": [
    57	                    {
    58	                        "id": "source",
    59	                        "at": 0,
    60	                        "track": "v",
    61	                        "clipType": "media",
    62	                        "asset": "source",
    63	                        "from": 0,
    64	                        "to": duration,
    65	                        "speed": 1,
    66	                        "volume": 0,
    67	                    }
    68	                ],
    69	            }
    70	        ),
    71	        encoding="utf-8",
    72	    )
    73	    assets_path.write_text(
    74	        json.dumps(
    75	            {
    76	                "assets": {
    77	                    "source": {
    78	                        "file": source.name,
    79	                        "type": "video/mp4",
    80	                        "duration": duration,
    81	                        "resolution": f"{width}x{height}",
    82	                        "fps": fps,
    83	                    }
    84	                }
    85	            }
    86	        ),
    87	        encoding="utf-8",
    88	    )
    89	    return timeline_path, assets_path
    90	
    91	
    92	def _request(
    93	    timeline_path: Path,
    94	    assets_path: Path,
    95	    *,
    96	    backend: str,
    97	    output_name: str,
    98	    backend_settings: dict[str, str] | None = None,
    99	) -> RenderRequest:
   100	    return RenderRequest(

exec
/bin/zsh -lc "rg -n -C 10 \"enforceAudioTrack\" remotion/node_modules/@remotion/cli/dist -g '*.js' | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n -C 12 \"enforceAudioTrack\" remotion/node_modules/@remotion/renderer/dist -g '*.js' | head -n 360" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n \"<OffthreadVideo|<Video|muted|volume\" remotion/src remotion/node_modules/@banodoco/timeline-composition/typescript/src -g '*.tsx' -g '*.ts' | head -n 360" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n \"audio assets|audioAssets|hasAudio|audio.*stream|video.*audio\" remotion/node_modules/@remotion/renderer/dist -g '*.js' | head -n 400" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 187ms:
remotion/node_modules/@remotion/cli/dist/benchmark.js-291-    const audioBitrate = audioBitrateOption.getValue({
remotion/node_modules/@remotion/cli/dist/benchmark.js-292-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/benchmark.js-293-    }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-294-    const configFileCrf = crfOption.getValue({ commandLine: parsed_cli_1.parsedCli }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-295-    const jpegQuality = jpegQualityOption.getValue({
remotion/node_modules/@remotion/cli/dist/benchmark.js-296-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/benchmark.js-297-    }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-298-    const videoBitrate = videoBitrateOption.getValue({
remotion/node_modules/@remotion/cli/dist/benchmark.js-299-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/benchmark.js-300-    }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js:301:    const enforceAudioTrack = enforceAudioOption.getValue({
remotion/node_modules/@remotion/cli/dist/benchmark.js-302-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/benchmark.js-303-    }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-304-    const muted = mutedOption.getValue({ commandLine: parsed_cli_1.parsedCli }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-305-    const disallowParallelEncoding = disallowParallelEncodingOption.getValue({
remotion/node_modules/@remotion/cli/dist/benchmark.js-306-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/benchmark.js-307-    }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-308-    const numberOfGifLoops = numberOfGifLoopsOption.getValue({
remotion/node_modules/@remotion/cli/dist/benchmark.js-309-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/benchmark.js-310-    }).value;
remotion/node_modules/@remotion/cli/dist/benchmark.js-311-    const encodingMaxRate = encodingMaxRateOption.getValue({
--
remotion/node_modules/@remotion/cli/dist/benchmark.js-367-                jpegQuality,
remotion/node_modules/@remotion/cli/dist/benchmark.js-368-                chromiumOptions,
remotion/node_modules/@remotion/cli/dist/benchmark.js-369-                timeoutInMilliseconds: delayRenderInMilliseconds,
remotion/node_modules/@remotion/cli/dist/benchmark.js-370-                scale,
remotion/node_modules/@remotion/cli/dist/benchmark.js-371-                port: (0, preview_server_1.getRendererPortFromConfigFileAndCliFlag)(),
remotion/node_modules/@remotion/cli/dist/benchmark.js-372-                numberOfGifLoops,
remotion/node_modules/@remotion/cli/dist/benchmark.js-373-                everyNthFrame,
remotion/node_modules/@remotion/cli/dist/benchmark.js-374-                logLevel,
remotion/node_modules/@remotion/cli/dist/benchmark.js-375-                muted,
remotion/node_modules/@remotion/cli/dist/benchmark.js-376-                sampleRate,
remotion/node_modules/@remotion/cli/dist/benchmark.js:377:                enforceAudioTrack,
remotion/node_modules/@remotion/cli/dist/benchmark.js-378-                browserExecutable,
remotion/node_modules/@remotion/cli/dist/benchmark.js-379-                ffmpegOverride,
remotion/node_modules/@remotion/cli/dist/benchmark.js-380-                serveUrl: bundleLocation,
remotion/node_modules/@remotion/cli/dist/benchmark.js-381-                codec: videoCodec,
remotion/node_modules/@remotion/cli/dist/benchmark.js-382-                audioBitrate,
remotion/node_modules/@remotion/cli/dist/benchmark.js-383-                videoBitrate,
remotion/node_modules/@remotion/cli/dist/benchmark.js-384-                encodingMaxRate,
remotion/node_modules/@remotion/cli/dist/benchmark.js-385-                encodingBufferSize,
remotion/node_modules/@remotion/cli/dist/benchmark.js-386-                puppeteerInstance,
remotion/node_modules/@remotion/cli/dist/benchmark.js-387-                concurrency: con,
--
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-29-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-30-    const offthreadVideoThreads = offthreadVideoThreadsOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-31-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-32-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-33-    const defaultScale = scaleOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-34-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-35-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-36-    const videoBitrate = videoBitrateOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-37-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-38-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js:39:    const enforceAudioTrack = enforceAudioOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-40-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-41-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-42-    const muted = mutedOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-43-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-44-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-45-    const colorSpace = colorSpaceOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-46-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-47-    }).value;
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-48-    const multiProcessOnLinux = enableMultiprocessOnLinuxOption.getValue({
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-49-        commandLine: parsed_cli_1.parsedCli,
--
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-121-        jpegQuality: defaultJpegQuality !== null && defaultJpegQuality !== void 0 ? defaultJpegQuality : renderer_1.RenderInternals.DEFAULT_JPEG_QUALITY,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-122-        scale: defaultScale !== null && defaultScale !== void 0 ? defaultScale : 1,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-123-        logLevel,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-124-        codec: defaultCodec !== null && defaultCodec !== void 0 ? defaultCodec : 'h264',
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-125-        concurrency,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-126-        maxConcurrency,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-127-        minConcurrency,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-128-        stillImageFormat: stillImageFormat !== null && stillImageFormat !== void 0 ? stillImageFormat : renderer_1.RenderInternals.DEFAULT_STILL_IMAGE_FORMAT,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-129-        videoImageFormat: videoImageFormat !== null && videoImageFormat !== void 0 ? videoImageFormat : renderer_1.RenderInternals.DEFAULT_VIDEO_IMAGE_FORMAT,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-130-        muted,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js:131:        enforceAudioTrack,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-132-        proResProfile,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-133-        x264Preset: x264Preset !== null && x264Preset !== void 0 ? x264Preset : 'medium',
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-134-        pixelFormat,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-135-        audioBitrate,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-136-        videoBitrate,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-137-        encodingBufferSize,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-138-        encodingMaxRate,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-139-        everyNthFrame,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-140-        delayRenderTimeout,
remotion/node_modules/@remotion/cli/dist/get-render-defaults.js-141-        audioCodec,
--
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-68-        shouldOutputImageSequence: job.type === 'sequence',
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-69-        addCleanupCallback,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-70-        outputLocationFromUI: job.outName,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-71-        uiCodec: job.type === 'video' ? job.codec : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-72-        uiImageFormat: job.imageFormat,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-73-        cancelSignal: job.cancelToken.cancelSignal,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-74-        crf: job.type === 'video' ? job.crf : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-75-        ffmpegOverride,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-76-        audioBitrate: job.type === 'video' ? job.audioBitrate : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-77-        muted: job.type === 'video' ? job.muted : true,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js:78:        enforceAudioTrack: job.type === 'video' ? job.enforceAudioTrack : false,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-79-        proResProfile: job.type === 'video' ? ((_b = job.proResProfile) !== null && _b !== void 0 ? _b : undefined) : undefined,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-80-        x264Preset: job.type === 'video' ? ((_c = job.x264Preset) !== null && _c !== void 0 ? _c : null) : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-81-        pixelFormat: job.type === 'video' ? job.pixelFormat : 'yuv420p',
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-82-        videoBitrate: job.type === 'video' ? job.videoBitrate : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-83-        encodingBufferSize: job.type === 'video' ? job.encodingBufferSize : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-84-        encodingMaxRate: job.type === 'video' ? job.encodingMaxRate : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-85-        numberOfGifLoops: job.type === 'video' ? job.numberOfGifLoops : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-86-        audioCodec: job.type === 'video' ? job.audioCodec : null,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-87-        disallowParallelEncoding: job.type === 'video' ? job.disallowParallelEncoding : false,
remotion/node_modules/@remotion/cli/dist/render-queue/process-video.js-88-        offthreadVideoCacheSizeInBytes: job.offthreadVideoCacheSizeInBytes,
--
remotion/node_modules/@remotion/cli/dist/render.js-72-    const offthreadVideoThreads = offthreadVideoThreadsOption.getValue({
remotion/node_modules/@remotion/cli/dist/render.js-73-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/render.js-74-    }).value;
remotion/node_modules/@remotion/cli/dist/render.js-75-    const scale = scaleOption.getValue({ commandLine: parsed_cli_1.parsedCli }).value;
remotion/node_modules/@remotion/cli/dist/render.js-76-    const jpegQuality = jpegQualityOption.getValue({
remotion/node_modules/@remotion/cli/dist/render.js-77-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/render.js-78-    }).value;
remotion/node_modules/@remotion/cli/dist/render.js-79-    const videoBitrate = videoBitrateOption.getValue({
remotion/node_modules/@remotion/cli/dist/render.js-80-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/render.js-81-    }).value;
remotion/node_modules/@remotion/cli/dist/render.js:82:    const enforceAudioTrack = enforceAudioOption.getValue({
remotion/node_modules/@remotion/cli/dist/render.js-83-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/render.js-84-    }).value;
remotion/node_modules/@remotion/cli/dist/render.js-85-    const muted = mutedOption.getValue({ commandLine: parsed_cli_1.parsedCli }).value;
remotion/node_modules/@remotion/cli/dist/render.js-86-    const colorSpace = colorSpaceOption.getValue({
remotion/node_modules/@remotion/cli/dist/render.js-87-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/render.js-88-    }).value;
remotion/node_modules/@remotion/cli/dist/render.js-89-    const disallowParallelEncoding = disallowParallelEncodingOption.getValue({
remotion/node_modules/@remotion/cli/dist/render.js-90-        commandLine: parsed_cli_1.parsedCli,
remotion/node_modules/@remotion/cli/dist/render.js-91-    }).value;
remotion/node_modules/@remotion/cli/dist/render.js-92-    const crf = shouldOutputImageSequence
--
remotion/node_modules/@remotion/cli/dist/render.js-203-            (0, cleanup_before_quit_1.registerCleanupJob)(label, c);
remotion/node_modules/@remotion/cli/dist/render.js-204-        },
remotion/node_modules/@remotion/cli/dist/render.js-205-        outputLocationFromUI: null,
remotion/node_modules/@remotion/cli/dist/render.js-206-        uiCodec: null,
remotion/node_modules/@remotion/cli/dist/render.js-207-        uiImageFormat: null,
remotion/node_modules/@remotion/cli/dist/render.js-208-        cancelSignal: null,
remotion/node_modules/@remotion/cli/dist/render.js-209-        crf,
remotion/node_modules/@remotion/cli/dist/render.js-210-        ffmpegOverride,
remotion/node_modules/@remotion/cli/dist/render.js-211-        audioBitrate,
remotion/node_modules/@remotion/cli/dist/render.js-212-        muted,
remotion/node_modules/@remotion/cli/dist/render.js:213:        enforceAudioTrack,
remotion/node_modules/@remotion/cli/dist/render.js-214-        proResProfile,
remotion/node_modules/@remotion/cli/dist/render.js-215-        x264Preset,
remotion/node_modules/@remotion/cli/dist/render.js-216-        pixelFormat,
remotion/node_modules/@remotion/cli/dist/render.js-217-        videoBitrate,
remotion/node_modules/@remotion/cli/dist/render.js-218-        encodingMaxRate,
remotion/node_modules/@remotion/cli/dist/render.js-219-        encodingBufferSize,
remotion/node_modules/@remotion/cli/dist/render.js-220-        numberOfGifLoops,
remotion/node_modules/@remotion/cli/dist/render.js-221-        audioCodec,
remotion/node_modules/@remotion/cli/dist/render.js-222-        disallowParallelEncoding,
remotion/node_modules/@remotion/cli/dist/render.js-223-        offthreadVideoCacheSizeInBytes,
--
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-55-const log_1 = require("../log");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-56-const make_on_download_1 = require("../make-on-download");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-57-const on_artifact_1 = require("../on-artifact");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-58-const parsed_cli_1 = require("../parsed-cli");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-59-const progress_bar_1 = require("../progress-bar");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-60-const setup_cache_1 = require("../setup-cache");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-61-const should_use_non_overlaying_logger_1 = require("../should-use-non-overlaying-logger");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-62-const truthy_1 = require("../truthy");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-63-const user_passed_output_location_1 = require("../user-passed-output-location");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-64-const add_log_to_aggregate_progress_1 = require("./add-log-to-aggregate-progress");
remotion/node_modules/@remotion/cli/dist/render-flows/render.js:65:const renderVideoFlow = async ({ remotionRoot, fullEntryPoint, indent, logLevel, browserExecutable, browser, chromiumOptions, scale, shouldOutputImageSequence, publicDir, envVariables, puppeteerTimeout, port, height, width, fps, durationInFrames, remainingArgs, compositionIdFromUi, entryPointReason, overwrite, quiet, concurrency, frameRange, everyNthFrame, outputLocationFromUI, jpegQuality, onProgress, addCleanupCallback, cancelSignal, crf, uiCodec, uiImageFormat, ffmpegOverride, audioBitrate, muted, enforceAudioTrack, proResProfile, x264Preset, pixelFormat, videoBitrate, encodingMaxRate, encodingBufferSize, numberOfGifLoops, audioCodec, serializedInputPropsWithCustomSchema, disallowParallelEncoding, offthreadVideoCacheSizeInBytes, offthreadVideoThreads, colorSpace, repro, binariesDirectory, forSeamlessAacConcatenation, separateAudioTo, publicPath, metadata, hardwareAcceleration, chromeMode, audioLatencyHint, imageSequencePattern, mediaCacheSizeInBytes, rspack, askAIEnabled, experimentalClientSideRenderingEnabled, experimentalVisualModeEnabled, keyboardShortcutsEnabled, shouldCache, sampleRate, }) => {
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-66-    var _a;
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-67-    renderer_1.RenderInternals.validateConcurrency({
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-68-        value: concurrency,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-69-        setting: 'concurrency',
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-70-        checkIfValidForCurrentMachine: true,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-71-    });
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-72-    let bundlingProgress = null;
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-73-    let renderingProgress = null;
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-74-    let stitchingProgress = null;
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-75-    let browserState = {
--
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-453-        x264Preset: x264Preset !== null && x264Preset !== void 0 ? x264Preset : null,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-454-        jpegQuality: jpegQuality !== null && jpegQuality !== void 0 ? jpegQuality : renderer_1.RenderInternals.DEFAULT_JPEG_QUALITY,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-455-        chromiumOptions,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-456-        timeoutInMilliseconds: puppeteerTimeout,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-457-        scale,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-458-        port,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-459-        numberOfGifLoops,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-460-        everyNthFrame,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-461-        logLevel,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-462-        muted,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js:463:        enforceAudioTrack,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-464-        browserExecutable,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-465-        ffmpegOverride,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-466-        concurrency,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-467-        serveUrl: urlOrBundle,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-468-        codec,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-469-        audioBitrate,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-470-        videoBitrate,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-471-        encodingMaxRate,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-472-        encodingBufferSize,
remotion/node_modules/@remotion/cli/dist/render-flows/render.js-473-        onProgress: (update) => {

 succeeded in 207ms:
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:43:  const baseVolume = track.muted
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:45:    : getSanitizedVolume(track.volume ?? 1) * getSanitizedVolume(clip.volume ?? 1);
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:52:  const volumeProp: number | ((frame: number) => number) =
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:77:      volume={volumeProp}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:54:  const effectiveVolume = track.muted
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:56:    : getSanitizedVolume(track.volume ?? 1) * getSanitizedVolume(clip.volume ?? 1);
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:75:      <Video
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:79:        volume={effectiveVolume}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:80:        muted={effectiveVolume <= 0}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:142:      <Video
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:146:        volume={effectiveVolume}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx:147:        muted={effectiveVolume <= 0}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/types.ts:37:  volume?: number;
remotion/node_modules/@banodoco/timeline-composition/typescript/src/types.ts:49:  muted?: boolean;
remotion/node_modules/@banodoco/timeline-composition/typescript/src/types.ts:52:  volume?: number;
remotion/node_modules/@banodoco/timeline-composition/typescript/src/lib/duration.ts:24:export const getSanitizedVolume = (volume: number | undefined, fallback = 1): number => {
remotion/node_modules/@banodoco/timeline-composition/typescript/src/lib/duration.ts:25:  return typeof volume === 'number' && Number.isFinite(volume)
remotion/node_modules/@banodoco/timeline-composition/typescript/src/lib/duration.ts:26:    ? Math.max(0, volume)

 succeeded in 178ms:
remotion/node_modules/@remotion/renderer/dist/guess-extension-for-media.js:29:    throw new Error(`The media file "${src}" has no file extension and the format could not be guessed. Tips: a) Ensure this is a valid video or audio file b) Add a file extension to the URL like ".mp4" c) Set a "Content-Type" or "Content-Disposition" header if possible.`);
remotion/node_modules/@remotion/renderer/dist/mux-video-and-audio.js:10:const muxVideoAndAudio = async ({ videoOutput, audioOutput, output, indent, logLevel, onProgress, binariesDirectory, fps, cancelSignal, addFaststart, metadata, numberOfGifLoops, }) => {
remotion/node_modules/@remotion/renderer/dist/mux-video-and-audio.js:13:    logger_1.Log.verbose({ indent, logLevel }, 'Muxing video and audio together');
remotion/node_modules/@remotion/renderer/dist/get-silent-parts.js:6: * @description Gets the silent parts of a video or audio in Node.js. Useful for cutting out silence from a video.
remotion/node_modules/@remotion/renderer/dist/render-media.js:58:const internalRenderMediaRaw = ({ proResProfile, x264Preset, crf, composition: compositionWithPossibleUnevenDimensions, serializedInputPropsWithCustomSchema, pixelFormat: userPixelFormat, codec, envVariables, frameRange, puppeteerInstance, outputLocation, onProgress, overwrite, onDownload, onBrowserLog, onStart, timeoutInMilliseconds, chromiumOptions, scale, browserExecutable, port, cancelSignal, muted, enforceAudioTrack, ffmpegOverride, audioBitrate, videoBitrate, encodingMaxRate, encodingBufferSize, audioCodec, concurrency, disallowParallelEncoding, everyNthFrame, imageFormat: provisionalImageFormat, indent, jpegQuality, numberOfGifLoops, onCtrlCExit, preferLossless, serveUrl, server: reusedServer, logLevel, serializedResolvedPropsWithCustomSchema, offthreadVideoCacheSizeInBytes, colorSpace, repro, binariesDirectory, separateAudioTo, forSeamlessAacConcatenation, compositionStart, onBrowserDownload, onArtifact, metadata, hardwareAcceleration, chromeMode, offthreadVideoThreads, mediaCacheSizeInBytes, onLog, licenseKey, isProduction, sampleRate, }) => {
remotion/node_modules/@remotion/renderer/dist/render-media.js:81:    (0, validate_videobitrate_1.validateBitrate)(audioBitrate, 'audioBitrate');
remotion/node_modules/@remotion/renderer/dist/render-media.js:475:                contentType: (0, mime_types_1.mimeLookup)('file.' + (0, get_extension_from_codec_1.getFileExtensionFromCodec)(codec, audioCodec)) || 'application/octet-stream',
remotion/node_modules/@remotion/renderer/dist/render-media.js:570: * @description Render a video or an audio programmatically.
remotion/node_modules/@remotion/renderer/dist/render-media.js:573:const renderMedia = ({ proResProfile, x264Preset, crf, composition, inputProps, pixelFormat, codec, envVariables, frameRange, puppeteerInstance, outputLocation, onProgress, overwrite, onDownload, onBrowserLog, onStart, timeoutInMilliseconds, chromiumOptions, scale, browserExecutable, port, cancelSignal, muted, enforceAudioTrack, ffmpegOverride, audioBitrate, videoBitrate, encodingMaxRate, encodingBufferSize, audioCodec, jpegQuality, concurrency, serveUrl, disallowParallelEncoding, everyNthFrame, imageFormat, numberOfGifLoops, dumpBrowserLogs, preferLossless, verbose, quality, logLevel: passedLogLevel, offthreadVideoCacheSizeInBytes, colorSpace, repro, binariesDirectory, separateAudioTo, forSeamlessAacConcatenation, onBrowserDownload, onArtifact, metadata, hardwareAcceleration, chromeMode, offthreadVideoThreads, compositionStart, mediaCacheSizeInBytes, isProduction, sampleRate, ...apiKeyOrLicenseKey }) => {
remotion/node_modules/@remotion/renderer/dist/extract-audio.js:6: * @description Extracts the audio from a video source and saves it to the specified output path. It does not convert the audio to a different format.
remotion/node_modules/@remotion/renderer/dist/combine-chunks.js:16:const mux_video_and_audio_1 = require("./mux-video-and-audio");
remotion/node_modules/@remotion/renderer/dist/combine-chunks.js:36:const internalCombineChunks = async ({ outputLocation: output, onProgress, codec, fps, numberOfGifLoops, audioBitrate, indent, logLevel, binariesDirectory, cancelSignal, metadata, audioFiles, videoFiles, framesPerChunk, audioCodec, preferLossless, everyNthFrame, frameRange, compositionDurationInFrames, sampleRate, }) => {
remotion/node_modules/@remotion/renderer/dist/combine-chunks.js:124:        await (0, mux_video_and_audio_1.muxVideoAndAudio)({
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:50:    (0, validate_videobitrate_1.validateBitrate)(audioBitrate, 'audioBitrate');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:71:        throw new Error('The output format has neither audio nor video. This can happen if you are rendering an audio codec and the output file has no audio or the muted flag was passed.');
remotion/node_modules/@remotion/renderer/dist/options/audio-codec.js:188:    description: () => `Set the format of the audio that is embedded in the video. Not all codec and audio codec combinations are supported and certain combinations require a certain file extension and container format. See the table in the docs to see possible combinations.`,
remotion/node_modules/@remotion/renderer/dist/options/audio-bitrate.js:12:            " parameter should be used. FFmpeg may encode the video in a way that will not result in the exact audio bitrate specified. Example values: ",

 succeeded in 225ms:
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-21-const logger_1 = require("./logger");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-22-const make_cancel_signal_1 = require("./make-cancel-signal");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-23-const make_metadata_args_1 = require("./make-metadata-args");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-24-const audio_codec_1 = require("./options/audio-codec");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-25-const color_space_1 = require("./options/color-space");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-26-const parse_ffmpeg_progress_1 = require("./parse-ffmpeg-progress");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-27-const pixel_format_1 = require("./pixel-format");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-28-const prores_profile_1 = require("./prores-profile");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-29-const render_has_audio_1 = require("./render-has-audio");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-30-const validate_1 = require("./validate");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-31-const validate_even_dimensions_with_codec_1 = require("./validate-even-dimensions-with-codec");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-32-const validate_videobitrate_1 = require("./validate-videobitrate");
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:33:const innerStitchFramesToVideo = async ({ assetsInfo, audioBitrate, audioCodec: audioCodecSetting, cancelSignal, codec, crf, enforceAudioTrack, ffmpegOverride, force, fps, height, indent, muted, onDownload, outputLocation, pixelFormat, preEncodedFileLocation, preferLossless, proResProfile, logLevel, videoBitrate, maxRate, bufferSize, width, numberOfGifLoops, onProgress, x264Preset, colorSpace, binariesDirectory, separateAudioTo, metadata, hardwareAcceleration, sampleRate, }, remotionRoot) => {
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-34-    var _a;
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-35-    (0, validate_1.validateDimension)(height, 'height', 'passed to `stitchFramesToVideo()`');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-36-    (0, validate_1.validateDimension)(width, 'width', 'passed to `stitchFramesToVideo()`');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-37-    (0, validate_even_dimensions_with_codec_1.validateEvenDimensionsWithCodec)({
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-38-        width,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-39-        height,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-40-        codec,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-41-        scale: 1,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-42-        wantsImageSequence: false,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-43-        indent,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-44-        logLevel,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-45-    });
--
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-50-    (0, validate_videobitrate_1.validateBitrate)(audioBitrate, 'audioBitrate');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-51-    (0, validate_videobitrate_1.validateBitrate)(videoBitrate, 'videoBitrate');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-52-    (0, validate_videobitrate_1.validateBitrate)(maxRate, 'maxRate');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-53-    // bufferSize is not a bitrate but need to be validated using the same format
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-54-    (0, validate_videobitrate_1.validateBitrate)(bufferSize, 'bufferSize');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-55-    (0, validate_1.validateFps)(fps, 'in `stitchFramesToVideo()`', false);
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-56-    assetsInfo.downloadMap.preventCleanup();
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-57-    const proResProfileName = (0, get_prores_profile_name_1.getProResProfileName)(codec, proResProfile);
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-58-    const mediaSupport = (0, codec_supports_media_1.codecSupportsMedia)(codec);
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-59-    const renderAudioEvaluation = (0, render_has_audio_1.getShouldRenderAudio)({
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-60-        assetsInfo,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-61-        codec,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:62:        enforceAudioTrack,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-63-        muted,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-64-    });
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-65-    if (renderAudioEvaluation === 'maybe') {
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-66-        throw new Error('Remotion is not sure whether to render audio. Please report this in the Remotion repo.');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-67-    }
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-68-    const shouldRenderAudio = renderAudioEvaluation === 'yes';
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-69-    const shouldRenderVideo = mediaSupport.video;
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-70-    if (!shouldRenderAudio && !shouldRenderVideo) {
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-71-        throw new Error('The output format has neither audio nor video. This can happen if you are rendering an audio codec and the output file has no audio or the muted flag was passed.');
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-72-    }
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-73-    const resolvedAudioCodec = (0, audio_codec_1.resolveAudioCodec)({
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-74-        codec,
--
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-303-            var _a;
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-304-            (_a = options.cancelSignal) === null || _a === void 0 ? void 0 : _a.call(options, () => {
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-305-                reject(new Error(make_cancel_signal_1.cancelErrorMessages.stitchFramesToVideo));
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-306-            });
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-307-        }),
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-308-    ]);
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-309-};
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-310-exports.internalStitchFramesToVideo = internalStitchFramesToVideo;
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-311-/*
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-312- * @description Takes a series of images and audio information generated by renderFrames() and encodes it to a video.
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-313- * @see [Documentation](https://www.remotion.dev/docs/renderer/stitch-frames-to-video)
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-314- */
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:315:const stitchFramesToVideo = ({ assetsInfo, force, fps, height, width, audioBitrate, audioCodec, cancelSignal, codec, crf, enforceAudioTrack, ffmpegOverride, muted, numberOfGifLoops, onDownload, onProgress, outputLocation, pixelFormat, proResProfile, verbose, videoBitrate, maxRate, bufferSize, x264Preset, colorSpace, binariesDirectory, separateAudioTo, metadata, hardwareAcceleration, sampleRate, }) => {
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-316-    return (0, exports.internalStitchFramesToVideo)({
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-317-        assetsInfo,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-318-        audioBitrate: audioBitrate !== null && audioBitrate !== void 0 ? audioBitrate : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-319-        maxRate: maxRate !== null && maxRate !== void 0 ? maxRate : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-320-        bufferSize: bufferSize !== null && bufferSize !== void 0 ? bufferSize : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-321-        audioCodec: audioCodec !== null && audioCodec !== void 0 ? audioCodec : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-322-        cancelSignal: cancelSignal !== null && cancelSignal !== void 0 ? cancelSignal : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-323-        codec: codec !== null && codec !== void 0 ? codec : codec_1.DEFAULT_CODEC,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-324-        crf: crf !== null && crf !== void 0 ? crf : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:325:        enforceAudioTrack: enforceAudioTrack !== null && enforceAudioTrack !== void 0 ? enforceAudioTrack : false,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-326-        ffmpegOverride: ffmpegOverride !== null && ffmpegOverride !== void 0 ? ffmpegOverride : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-327-        force: force !== null && force !== void 0 ? force : true,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-328-        fps,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-329-        height,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-330-        indent: false,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-331-        muted: muted !== null && muted !== void 0 ? muted : false,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-332-        numberOfGifLoops: numberOfGifLoops !== null && numberOfGifLoops !== void 0 ? numberOfGifLoops : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-333-        onDownload: onDownload !== null && onDownload !== void 0 ? onDownload : undefined,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-334-        onProgress,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-335-        outputLocation: outputLocation !== null && outputLocation !== void 0 ? outputLocation : null,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-336-        pixelFormat: pixelFormat !== null && pixelFormat !== void 0 ? pixelFormat : pixel_format_1.DEFAULT_PIXEL_FORMAT,
remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-337-        proResProfile,
--
remotion/node_modules/@remotion/renderer/dist/render-media.js-46-const succeed_or_cancel_1 = require("./succeed-or-cancel");
remotion/node_modules/@remotion/renderer/dist/render-media.js-47-const validate_1 = require("./validate");
remotion/node_modules/@remotion/renderer/dist/render-media.js-48-const validate_even_dimensions_with_codec_1 = require("./validate-even-dimensions-with-codec");
remotion/node_modules/@remotion/renderer/dist/render-media.js-49-const validate_every_nth_frame_1 = require("./validate-every-nth-frame");
remotion/node_modules/@remotion/renderer/dist/render-media.js-50-const validate_ffmpeg_override_1 = require("./validate-ffmpeg-override");
remotion/node_modules/@remotion/renderer/dist/render-media.js-51-const validate_number_of_gif_loops_1 = require("./validate-number-of-gif-loops");
remotion/node_modules/@remotion/renderer/dist/render-media.js-52-const validate_output_filename_1 = require("./validate-output-filename");
remotion/node_modules/@remotion/renderer/dist/render-media.js-53-const validate_scale_1 = require("./validate-scale");
remotion/node_modules/@remotion/renderer/dist/render-media.js-54-const validate_videobitrate_1 = require("./validate-videobitrate");
remotion/node_modules/@remotion/renderer/dist/render-media.js-55-const wrap_with_error_handling_1 = require("./wrap-with-error-handling");
remotion/node_modules/@remotion/renderer/dist/render-media.js-56-const SLOWEST_FRAME_COUNT = 10;
remotion/node_modules/@remotion/renderer/dist/render-media.js-57-const MAX_RECENT_FRAME_TIMINGS = 150;
remotion/node_modules/@remotion/renderer/dist/render-media.js:58:const internalRenderMediaRaw = ({ proResProfile, x264Preset, crf, composition: compositionWithPossibleUnevenDimensions, serializedInputPropsWithCustomSchema, pixelFormat: userPixelFormat, codec, envVariables, frameRange, puppeteerInstance, outputLocation, onProgress, overwrite, onDownload, onBrowserLog, onStart, timeoutInMilliseconds, chromiumOptions, scale, browserExecutable, port, cancelSignal, muted, enforceAudioTrack, ffmpegOverride, audioBitrate, videoBitrate, encodingMaxRate, encodingBufferSize, audioCodec, concurrency, disallowParallelEncoding, everyNthFrame, imageFormat: provisionalImageFormat, indent, jpegQuality, numberOfGifLoops, onCtrlCExit, preferLossless, serveUrl, server: reusedServer, logLevel, serializedResolvedPropsWithCustomSchema, offthreadVideoCacheSizeInBytes, colorSpace, repro, binariesDirectory, separateAudioTo, forSeamlessAacConcatenation, compositionStart, onBrowserDownload, onArtifact, metadata, hardwareAcceleration, chromeMode, offthreadVideoThreads, mediaCacheSizeInBytes, onLog, licenseKey, isProduction, sampleRate, }) => {
remotion/node_modules/@remotion/renderer/dist/render-media.js-59-    var _a, _b;
remotion/node_modules/@remotion/renderer/dist/render-media.js-60-    const pixelFormat = (_a = userPixelFormat !== null && userPixelFormat !== void 0 ? userPixelFormat : compositionWithPossibleUnevenDimensions.defaultPixelFormat) !== null && _a !== void 0 ? _a : pixel_format_1.DEFAULT_PIXEL_FORMAT;
remotion/node_modules/@remotion/renderer/dist/render-media.js-61-    if (repro) {
remotion/node_modules/@remotion/renderer/dist/render-media.js-62-        (0, repro_1.enableRepro)({
remotion/node_modules/@remotion/renderer/dist/render-media.js-63-            serveUrl,
remotion/node_modules/@remotion/renderer/dist/render-media.js-64-            compositionName: compositionWithPossibleUnevenDimensions.id,
remotion/node_modules/@remotion/renderer/dist/render-media.js-65-            serializedInputPropsWithCustomSchema,
remotion/node_modules/@remotion/renderer/dist/render-media.js-66-            serializedResolvedPropsWithCustomSchema,
remotion/node_modules/@remotion/renderer/dist/render-media.js-67-        });
remotion/node_modules/@remotion/renderer/dist/render-media.js-68-    }
remotion/node_modules/@remotion/renderer/dist/render-media.js-69-    else {
remotion/node_modules/@remotion/renderer/dist/render-media.js-70-        (0, repro_1.disableRepro)();
--
remotion/node_modules/@remotion/renderer/dist/render-media.js-441-                    if (encodedFrames === totalFramesToRender) {
remotion/node_modules/@remotion/renderer/dist/render-media.js-442-                        encodedDoneIn = Date.now() - stitchStart;
remotion/node_modules/@remotion/renderer/dist/render-media.js-443-                    }
remotion/node_modules/@remotion/renderer/dist/render-media.js-444-                    if (frame > 0) {
remotion/node_modules/@remotion/renderer/dist/render-media.js-445-                        callUpdate();
remotion/node_modules/@remotion/renderer/dist/render-media.js-446-                    }
remotion/node_modules/@remotion/renderer/dist/render-media.js-447-                },
remotion/node_modules/@remotion/renderer/dist/render-media.js-448-                onDownload,
remotion/node_modules/@remotion/renderer/dist/render-media.js-449-                numberOfGifLoops,
remotion/node_modules/@remotion/renderer/dist/render-media.js-450-                logLevel,
remotion/node_modules/@remotion/renderer/dist/render-media.js-451-                cancelSignal: cancelStitcher.cancelSignal,
remotion/node_modules/@remotion/renderer/dist/render-media.js-452-                muted: disableAudio,
remotion/node_modules/@remotion/renderer/dist/render-media.js:453:                enforceAudioTrack,
remotion/node_modules/@remotion/renderer/dist/render-media.js-454-                ffmpegOverride: ffmpegOverride !== null && ffmpegOverride !== void 0 ? ffmpegOverride : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-455-                audioBitrate,
remotion/node_modules/@remotion/renderer/dist/render-media.js-456-                videoBitrate,
remotion/node_modules/@remotion/renderer/dist/render-media.js-457-                bufferSize: encodingBufferSize,
remotion/node_modules/@remotion/renderer/dist/render-media.js-458-                maxRate: encodingMaxRate,
remotion/node_modules/@remotion/renderer/dist/render-media.js-459-                audioCodec,
remotion/node_modules/@remotion/renderer/dist/render-media.js-460-                x264Preset: x264Preset !== null && x264Preset !== void 0 ? x264Preset : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-461-                colorSpace,
remotion/node_modules/@remotion/renderer/dist/render-media.js-462-                binariesDirectory,
remotion/node_modules/@remotion/renderer/dist/render-media.js-463-                separateAudioTo,
remotion/node_modules/@remotion/renderer/dist/render-media.js-464-                metadata,
remotion/node_modules/@remotion/renderer/dist/render-media.js-465-                hardwareAcceleration,
--
remotion/node_modules/@remotion/renderer/dist/render-media.js-561-    });
remotion/node_modules/@remotion/renderer/dist/render-media.js-562-    return (0, succeed_or_cancel_1.succeedOrCancel)({
remotion/node_modules/@remotion/renderer/dist/render-media.js-563-        happyPath,
remotion/node_modules/@remotion/renderer/dist/render-media.js-564-        cancelSignal,
remotion/node_modules/@remotion/renderer/dist/render-media.js-565-        cancelMessage: make_cancel_signal_1.cancelErrorMessages.renderMedia,
remotion/node_modules/@remotion/renderer/dist/render-media.js-566-    });
remotion/node_modules/@remotion/renderer/dist/render-media.js-567-};
remotion/node_modules/@remotion/renderer/dist/render-media.js-568-exports.internalRenderMedia = (0, wrap_with_error_handling_1.wrapWithErrorHandling)(internalRenderMediaRaw);
remotion/node_modules/@remotion/renderer/dist/render-media.js-569-/*
remotion/node_modules/@remotion/renderer/dist/render-media.js-570- * @description Render a video or an audio programmatically.
remotion/node_modules/@remotion/renderer/dist/render-media.js-571- * @see [Documentation](https://www.remotion.dev/docs/renderer/render-media)
remotion/node_modules/@remotion/renderer/dist/render-media.js-572- */
remotion/node_modules/@remotion/renderer/dist/render-media.js:573:const renderMedia = ({ proResProfile, x264Preset, crf, composition, inputProps, pixelFormat, codec, envVariables, frameRange, puppeteerInstance, outputLocation, onProgress, overwrite, onDownload, onBrowserLog, onStart, timeoutInMilliseconds, chromiumOptions, scale, browserExecutable, port, cancelSignal, muted, enforceAudioTrack, ffmpegOverride, audioBitrate, videoBitrate, encodingMaxRate, encodingBufferSize, audioCodec, jpegQuality, concurrency, serveUrl, disallowParallelEncoding, everyNthFrame, imageFormat, numberOfGifLoops, dumpBrowserLogs, preferLossless, verbose, quality, logLevel: passedLogLevel, offthreadVideoCacheSizeInBytes, colorSpace, repro, binariesDirectory, separateAudioTo, forSeamlessAacConcatenation, onBrowserDownload, onArtifact, metadata, hardwareAcceleration, chromeMode, offthreadVideoThreads, compositionStart, mediaCacheSizeInBytes, isProduction, sampleRate, ...apiKeyOrLicenseKey }) => {
remotion/node_modules/@remotion/renderer/dist/render-media.js-574-    var _a, _b, _c, _d;
remotion/node_modules/@remotion/renderer/dist/render-media.js-575-    const indent = false;
remotion/node_modules/@remotion/renderer/dist/render-media.js-576-    const logLevel = verbose || dumpBrowserLogs ? 'verbose' : (passedLogLevel !== null && passedLogLevel !== void 0 ? passedLogLevel : 'info');
remotion/node_modules/@remotion/renderer/dist/render-media.js-577-    if (quality !== undefined) {
remotion/node_modules/@remotion/renderer/dist/render-media.js-578-        logger_1.Log.warn({ indent, logLevel }, `The "quality" option has been renamed. Please use "jpegQuality" instead.`);
remotion/node_modules/@remotion/renderer/dist/render-media.js-579-    }
remotion/node_modules/@remotion/renderer/dist/render-media.js-580-    const licenseKey = 'licenseKey' in apiKeyOrLicenseKey ? apiKeyOrLicenseKey.licenseKey : null;
remotion/node_modules/@remotion/renderer/dist/render-media.js-581-    const apiKey = 'apiKey' in apiKeyOrLicenseKey ? apiKeyOrLicenseKey.apiKey : null;
remotion/node_modules/@remotion/renderer/dist/render-media.js-582-    return (0, exports.internalRenderMedia)({
remotion/node_modules/@remotion/renderer/dist/render-media.js-583-        proResProfile: proResProfile !== null && proResProfile !== void 0 ? proResProfile : undefined,
remotion/node_modules/@remotion/renderer/dist/render-media.js-584-        x264Preset: x264Preset !== null && x264Preset !== void 0 ? x264Preset : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-585-        codec,
remotion/node_modules/@remotion/renderer/dist/render-media.js-586-        composition,
remotion/node_modules/@remotion/renderer/dist/render-media.js-587-        serveUrl,
remotion/node_modules/@remotion/renderer/dist/render-media.js-588-        audioBitrate: audioBitrate !== null && audioBitrate !== void 0 ? audioBitrate : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-589-        audioCodec: audioCodec !== null && audioCodec !== void 0 ? audioCodec : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-590-        browserExecutable: browserExecutable !== null && browserExecutable !== void 0 ? browserExecutable : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-591-        cancelSignal,
remotion/node_modules/@remotion/renderer/dist/render-media.js-592-        chromiumOptions: chromiumOptions !== null && chromiumOptions !== void 0 ? chromiumOptions : {},
remotion/node_modules/@remotion/renderer/dist/render-media.js-593-        concurrency: concurrency !== null && concurrency !== void 0 ? concurrency : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-594-        crf: crf !== null && crf !== void 0 ? crf : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-595-        disallowParallelEncoding: disallowParallelEncoding !== null && disallowParallelEncoding !== void 0 ? disallowParallelEncoding : false,
remotion/node_modules/@remotion/renderer/dist/render-media.js:596:        enforceAudioTrack: enforceAudioTrack !== null && enforceAudioTrack !== void 0 ? enforceAudioTrack : false,
remotion/node_modules/@remotion/renderer/dist/render-media.js-597-        envVariables: envVariables !== null && envVariables !== void 0 ? envVariables : {},
remotion/node_modules/@remotion/renderer/dist/render-media.js-598-        everyNthFrame: everyNthFrame !== null && everyNthFrame !== void 0 ? everyNthFrame : 1,
remotion/node_modules/@remotion/renderer/dist/render-media.js-599-        ffmpegOverride: ffmpegOverride !== null && ffmpegOverride !== void 0 ? ffmpegOverride : undefined,
remotion/node_modules/@remotion/renderer/dist/render-media.js-600-        frameRange: frameRange !== null && frameRange !== void 0 ? frameRange : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-601-        imageFormat: imageFormat !== null && imageFormat !== void 0 ? imageFormat : null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-602-        serializedInputPropsWithCustomSchema: no_react_1.NoReactInternals.serializeJSONWithSpecialTypes({
remotion/node_modules/@remotion/renderer/dist/render-media.js-603-            indent: undefined,
remotion/node_modules/@remotion/renderer/dist/render-media.js-604-            staticBase: null,
remotion/node_modules/@remotion/renderer/dist/render-media.js-605-            data: inputProps !== null && inputProps !== void 0 ? inputProps : {},
remotion/node_modules/@remotion/renderer/dist/render-media.js-606-        }).serializedString,
remotion/node_modules/@remotion/renderer/dist/render-media.js-607-        jpegQuality: (_a = jpegQuality !== null && jpegQuality !== void 0 ? jpegQuality : quality) !== null && _a !== void 0 ? _a : jpeg_quality_1.DEFAULT_JPEG_QUALITY,
remotion/node_modules/@remotion/renderer/dist/render-media.js-608-        muted: muted !== null && muted !== void 0 ? muted : false,
--
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-1-"use strict";
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-2-Object.defineProperty(exports, "__esModule", { value: true });
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-3-exports.getShouldRenderAudio = void 0;
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-4-const codec_supports_media_1 = require("./codec-supports-media");
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js:5:const getShouldRenderAudio = ({ codec, assetsInfo, enforceAudioTrack, muted, }) => {
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-6-    if (muted) {
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-7-        return 'no';
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-8-    }
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-9-    if (!(0, codec_supports_media_1.codecSupportsMedia)(codec).audio) {
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-10-        return 'no';
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-11-    }
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js:12:    if (enforceAudioTrack) {
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-13-        return 'yes';
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-14-    }
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-15-    if (assetsInfo === null) {
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-16-        return 'maybe';
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-17-    }
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-18-    return assetsInfo.assets.flat(1).length > 0 ? 'yes' : 'no';
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-19-};
remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-20-exports.getShouldRenderAudio = getShouldRenderAudio;
--
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-159-        offthreadVideoThreads: offthreadvideo_threads_1.offthreadVideoThreadsOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-160-        numberOfGifLoops: number_of_gif_loops_1.numberOfGifLoopsOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-161-        preferLossless: prefer_lossless_1.preferLosslessAudioOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-162-        colorSpace: color_space_1.colorSpaceOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-163-        audioBitrate: audio_bitrate_1.audioBitrateOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-164-        videoBitrate: video_bitrate_1.videoBitrateOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-165-        x264Preset: x264_preset_1.x264Option,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-166-        encodingMaxRate: encoding_max_rate_1.encodingMaxRateOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-167-        encodingBufferSize: encoding_buffer_size_1.encodingBufferSizeOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-168-        muted: mute_1.mutedOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-169-        logLevel: log_level_1.logLevelOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-170-        delayRenderTimeoutInMilliseconds: timeout_1.delayRenderTimeoutInMillisecondsOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js:171:        enforceAudioTrack: enforce_audio_1.enforceAudioOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-172-        scale: scale_1.scaleOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-173-        crf: crf_1.crfOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-174-        jpegQuality: jpeg_quality_1.jpegQualityOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-175-        sampleRate: sample_rate_1.sampleRateOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-176-    },
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-177-    renderStillOnCloudRun: {
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-178-        mediaCacheSizeInBytes: video_cache_size_1.mediaCacheSizeInBytesOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-179-        offthreadVideoCacheSizeInBytes: offthreadvideo_cache_size_1.offthreadVideoCacheSizeInBytesOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-180-        offthreadVideoThreads: offthreadvideo_threads_1.offthreadVideoThreadsOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-181-        logLevel: log_level_1.logLevelOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-182-        scale: scale_1.scaleOption,
remotion/node_modules/@remotion/renderer/dist/options/options-map.js-183-        jpegQuality: jpeg_quality_1.jpegQualityOption,
--
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-1-"use strict";
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-2-Object.defineProperty(exports, "__esModule", { value: true });
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-3-exports.enforceAudioOption = void 0;
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-4-const jsx_runtime_1 = require("react/jsx-runtime");
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-5-const DEFAULT_ENFORCE_AUDIO_TRACK = false;
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js:6:let enforceAudioTrackState = DEFAULT_ENFORCE_AUDIO_TRACK;
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-7-const cliFlag = 'enforce-audio-track';
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-8-exports.enforceAudioOption = {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-9-    name: 'Enforce Audio Track',
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-10-    cliFlag,
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-11-    description: () => (jsx_runtime_1.jsx(jsx_runtime_1.Fragment, { children: "Render a silent audio track if there would be none otherwise." })),
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js:12:    ssrName: 'enforceAudioTrack',
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-13-    docLink: 'https://www.remotion.dev/docs/config#setenforceaudiotrack-',
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-14-    type: false,
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-15-    getValue: ({ commandLine }) => {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-16-        if (commandLine[cliFlag]) {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-17-            return {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-18-                source: 'cli',
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-19-                value: true,
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-20-            };
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-21-        }
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js:22:        if (enforceAudioTrackState !== DEFAULT_ENFORCE_AUDIO_TRACK) {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-23-            return {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-24-                source: 'config',
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js:25:                value: enforceAudioTrackState,
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-26-            };
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-27-        }
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-28-        return {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-29-            source: 'default',
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-30-            value: DEFAULT_ENFORCE_AUDIO_TRACK,
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-31-        };
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-32-    },
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-33-    setConfig: (value) => {
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js:34:        enforceAudioTrackState = value;
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-35-    },
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-36-    id: cliFlag,
remotion/node_modules/@remotion/renderer/dist/options/enforce-audio.js-37-};

exec
/bin/zsh -lc "nl -ba remotion/node_modules/@remotion/renderer/dist/render-has-audio.js | sed -n '1,220p'; nl -ba remotion/node_modules/@banodoco/timeline-composition/typescript/src/VisualClip.tsx | sed -n '35,95p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     1	"use strict";
     2	Object.defineProperty(exports, "__esModule", { value: true });
     3	exports.getShouldRenderAudio = void 0;
     4	const codec_supports_media_1 = require("./codec-supports-media");
     5	const getShouldRenderAudio = ({ codec, assetsInfo, enforceAudioTrack, muted, }) => {
     6	    if (muted) {
     7	        return 'no';
     8	    }
     9	    if (!(0, codec_supports_media_1.codecSupportsMedia)(codec).audio) {
    10	        return 'no';
    11	    }
    12	    if (enforceAudioTrack) {
    13	        return 'yes';
    14	    }
    15	    if (assetsInfo === null) {
    16	        return 'maybe';
    17	    }
    18	    return assetsInfo.assets.flat(1).length > 0 ? 'yes' : 'no';
    19	};
    20	exports.getShouldRenderAudio = getShouldRenderAudio;
    35	
    36	export const VisualClip: FC<VisualClipProps> = ({clip, track, assetEntry, fps}) => {
    37	  const {width: compositionWidth, height: compositionHeight} = useVideoConfig();
    38	  const fileUrl = toRenderableFileUrl(assetEntry?.file);
    39	  if (!fileUrl || !assetEntry) {
    40	    return null;
    41	  }
    42	
    43	  const hasPositionOverride = (
    44	    clip.x !== undefined
    45	    || clip.y !== undefined
    46	    || clip.width !== undefined
    47	    || clip.height !== undefined
    48	    || clip.cropTop !== undefined
    49	    || clip.cropBottom !== undefined
    50	    || clip.cropLeft !== undefined
    51	    || clip.cropRight !== undefined
    52	  );
    53	  const useViewportLayout = (track.fit ?? 'contain') === 'manual' || hasPositionOverride;
    54	  const effectiveVolume = track.muted
    55	    ? 0
    56	    : getSanitizedVolume(track.volume ?? 1) * getSanitizedVolume(clip.volume ?? 1);
    57	  const opacity = useFadeOpacity(clip, fps) * (clip.opacity ?? 1);
    58	  const mixBlendMode = track.blendMode && track.blendMode !== 'normal' ? track.blendMode : undefined;
    59	  const isImage = assetEntry.type?.startsWith('image');
    60	
    61	  if (!useViewportLayout) {
    62	    const sharedStyle: CSSProperties = {
    63	      width: '100%',
    64	      height: '100%',
    65	      objectFit: track.fit === 'cover' ? 'cover' : 'contain',
    66	      opacity,
    67	      mixBlendMode,
    68	    };
    69	
    70	    if (isImage) {
    71	      return <Img src={fileUrl} style={sharedStyle} crossOrigin="anonymous" />;
    72	    }
    73	
    74	    return (
    75	      <Video
    76	        src={fileUrl}
    77	        {...computeMediaTrim(clip, fps)}
    78	        playbackRate={getSanitizedPlaybackRate(clip.speed)}
    79	        volume={effectiveVolume}
    80	        muted={effectiveVolume <= 0}
    81	        style={sharedStyle}
    82	      />
    83	    );
    84	  }
    85	
    86	  const fullBounds = {
    87	    x: clip.x ?? 0,
    88	    y: clip.y ?? 0,
    89	    width: clip.width ?? compositionWidth,
    90	    height: clip.height ?? compositionHeight,
    91	  };
    92	  const cropValues = normalizeRenderCropValues({
    93	    cropTop: clip.cropTop,
    94	    cropBottom: clip.cropBottom,
    95	    cropLeft: clip.cropLeft,

exec
/bin/zsh -lc "rg -n \"def _validate_project_dir|project_dir\" astrid/packs/rendering/backends/remotion/run.py | head -n 80; nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '760,875p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 11ms:
   760	        )
   761	        provenance = _render_provenance_payload(
   762	            out_path,
   763	            engine="remotion",
   764	            timeline_path=timeline_path,
   765	            assets_path=assets_path,
   766	            project_dir=project_dir,
   767	            composition_id=composition_id,
   768	            theme_path=theme_path,
   769	            active_theme=details.active_theme,
   770	            registry_state=details.registry_state,
   771	            stage_summary=details.stage_summary,
   772	        )
   773	        output = publish_render_result(
   774	            staged_video,
   775	            provenance,
   776	            out_path=out_path,
   777	            sidecar_path=_render_provenance_sidecar_path(out_path),
   778	            previous_outputs=previous_outputs,
   779	        )
   780	
   781	    audit = AuditContext.from_env()
   782	    if audit is not None:
   783	        timeline_id = audit.register_asset(
   784	            kind="timeline",
   785	            path=timeline_path,
   786	            label="Render timeline",
   787	            stage="render_remotion",
   788	        )
   789	        assets_id = audit.register_asset(
   790	            kind="assets_registry",
   791	            path=assets_path,
   792	            label="Render asset registry",
   793	            stage="render_remotion",
   794	        )
   795	        render_id = audit.register_asset(
   796	            kind="render",
   797	            path=output,
   798	            label="Rendered video",
   799	            parents=[timeline_id, assets_id],
   800	            stage="render_remotion",
   801	            metadata={"composition": composition_id},
   802	        )
   803	        audit.register_node(
   804	            stage="render_remotion",
   805	            label="Render Remotion timeline",
   806	            parents=[timeline_id, assets_id],
   807	            outputs=[render_id],
   808	            metadata={
   809	                "composition": composition_id,
   810	                "project_dir": str(project_dir),
   811	            },
   812	        )
   813	    return output
   814	
   815	
   816	def _input_path(raw_path: str, workspace: Path) -> Path:
   817	    candidate = Path(raw_path).expanduser()
   818	    return (candidate if candidate.is_absolute() else workspace / candidate).resolve()
   819	
   820	
   821	def _theme_setting_path(raw_path: str, workspace: Path) -> Path:
   822	    """Preserve legacy theme slugs while localizing actual request paths."""
   823	
   824	    candidate = Path(raw_path).expanduser()
   825	    if candidate.is_absolute():
   826	        return candidate.resolve()
   827	    localized = workspace / candidate
   828	    if localized.exists() or len(candidate.parts) > 1 or candidate.suffix:
   829	        return localized.resolve()
   830	    return candidate
   831	
   832	
   833	def _settings_from_request(request: RenderRequest, workspace: Path) -> _RenderSettings:
   834	    config = dict(request.backend_config.get(BACKEND_ID, {}))
   835	    unknown = sorted(set(config) - _CONFIG_KEYS)
   836	    if unknown:
   837	        raise ValueError(f"unknown {BACKEND_ID} configuration: {', '.join(unknown)}")
   838	
   839	    project_value = config.get("project_dir", REPO_ROOT / "remotion")
   840	    if not isinstance(project_value, (str, os.PathLike)):
   841	        raise TypeError("project_dir must be a path string")
   842	    project_dir = _input_path(os.fspath(project_value), workspace)
   843	
   844	    composition_value = config.get(
   845	        "composition_id",
   846	        config.get("composition", DEFAULT_COMPOSITION_ID),
   847	    )
   848	    if not isinstance(composition_value, str) or not composition_value.strip():
   849	        raise TypeError("composition_id must be a non-empty string")
   850	
   851	    theme_value = config.get("theme_path", config.get("theme"))
   852	    if theme_value is None:
   853	        theme_path = None
   854	    elif isinstance(theme_value, (str, os.PathLike)):
   855	        theme_path = _theme_setting_path(os.fspath(theme_value), workspace)
   856	    else:
   857	        raise TypeError("theme_path must be a path string or null")
   858	
   859	    min_free_value = config.get("min_free_gb")
   860	    if min_free_value is None:
   861	        min_free_gb = None
   862	    elif isinstance(min_free_value, bool) or not isinstance(min_free_value, (int, float)):
   863	        raise TypeError("min_free_gb must be a number or null")
   864	    else:
   865	        min_free_gb = float(min_free_value)
   866	        if min_free_gb < 0:
   867	            raise ValueError("min_free_gb must not be negative")
   868	
   869	    return _RenderSettings(
   870	        project_dir=project_dir,
   871	        composition_id=composition_value,
   872	        theme_path=theme_path,
   873	        min_free_gb=min_free_gb,
   874	    )
   875	

exec
/bin/zsh -lc "rg -n -C 8 \"assetsInfo\\.assets|assets:\" remotion/node_modules/@remotion/renderer/dist -g '*.js' | rg -n \"audio|assetsInfo|flat\" | head -n 420" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "rg -n -C 8 \"muted\" remotion/node_modules/remotion/dist -g '*.js' | rg \"audio|asset|Video\" | head -n 300" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 6ms:
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-87-    // nodes might still be used. Using rAF to ensure it's after other effects.
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-88-    effectToUse(() => {
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-89-        return () => {
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-90-            requestAnimationFrame(() => {
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-91-                sharedSource === null || sharedSource === void 0 ? void 0 : sharedSource.cleanup();
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-92-            });
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-93-        };
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-94-    }, [sharedSource]);
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js:95:    const { volume, muted, playbackRate, onlyWarnForMediaSeekingError, src, onDuration, 
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-96-    // @ts-expect-error
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-97-    acceptableTimeShift, acceptableTimeShiftInSeconds, toneFrequency, name, _remotionInternalNativeLoopPassed, _remotionInternalStack, style, pauseWhenBuffering, showInTimeline, loopVolumeCurveBehavior, onError, onAutoPlayError, onVideoFrame, crossOrigin, delayRenderRetries, delayRenderTimeoutInMilliseconds, allowAmplificationDuringRender, useWebAudioApi, audioStreamIndex, ...nativeProps } = props;
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-98-    const _propsValid = true;
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-99-    if (!_propsValid) {
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-100-        throw new Error('typecheck error');
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-101-    }
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-102-    const volumePropFrame = (0, use_audio_frame_js_1.useFrameForVolumeProp)(loopVolumeCurveBehavior !== null && loopVolumeCurveBehavior !== void 0 ? loopVolumeCurveBehavior : 'repeat');
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-103-    const { fps, durationInFrames } = (0, use_video_config_js_1.useVideoConfig)();
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-272-            opacity: isSequenceHidden ? 0 : ((_a = style === null || style === void 0 ? void 0 : style.opacity) !== null && _a !== void 0 ? _a : 1),
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-273-        };
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-274-    }, [isSequenceHidden, style]);
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-275-    const crossOriginValue = (0, get_cross_origin_value_js_1.getCrossOriginValue)({
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-276-        crossOrigin,
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-277-        requestsVideoFrame: Boolean(onVideoFrame),
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-278-        isClientSideRendering: false,
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-279-    });
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js:280:    return ((0, jsx_runtime_1.jsx)("video", { ref: videoRef, muted: muted || mediaMuted || isSequenceHidden || userPreferredVolume <= 0, playsInline: true, src: actualSrc, loop: _remotionInternalNativeLoopPassed, style: actualStyle, disableRemotePlayback: true, crossOrigin: crossOriginValue, ...nativeProps }));
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-281-};
remotion/node_modules/remotion/dist/cjs/video/VideoForPreview.js-282-exports.VideoForPreview = (0, react_1.forwardRef)(VideoForDevelopmentRefForwardingFunction);
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-40-    const { transparent, toneMapped, onAutoPlayError, onVideoFrame, crossOrigin, delayRenderRetries, delayRenderTimeoutInMilliseconds, ...propsForPreview } = otherProps;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-41-    return ((0, jsx_runtime_1.jsx)(VideoForPreview_js_1.VideoForPreview, { _remotionInternalStack: stack !== null && stack !== void 0 ? stack : null, onDuration: onDuration, onlyWarnForMediaSeekingError: true, pauseWhenBuffering: pauseWhenBuffering !== null && pauseWhenBuffering !== void 0 ? pauseWhenBuffering : false, showInTimeline: showInTimeline !== null && showInTimeline !== void 0 ? showInTimeline : true, onAutoPlayError: onAutoPlayError !== null && onAutoPlayError !== void 0 ? onAutoPlayError : undefined, onVideoFrame: onVideoFrame !== null && onVideoFrame !== void 0 ? onVideoFrame : null, crossOrigin: crossOrigin, ...propsForPreview, _remotionInternalNativeLoopPassed: false }));
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-42-};
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-43-exports.InnerOffthreadVideo = InnerOffthreadVideo;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-44-/*
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-45- * @description This method imports and displays a video, similar to <Html5Video />. During rendering, it extracts the exact frame from the video and displays it in an <img> tag
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-46- * @see [Documentation](https://www.remotion.dev/docs/offthreadvideo)
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-47- */
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js:48:const OffthreadVideo = ({ src, acceptableTimeShiftInSeconds, allowAmplificationDuringRender, audioStreamIndex, className, crossOrigin, delayRenderRetries, delayRenderTimeoutInMilliseconds, id, loopVolumeCurveBehavior, muted, name, onAutoPlayError, onError, onVideoFrame, pauseWhenBuffering, playbackRate, showInTimeline, style, toneFrequency, toneMapped, transparent, trimAfter, trimBefore, useWebAudioApi, volume, _remotionInternalNativeLoopPassed, endAt, stack, startFrom, imageFormat, }) => {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-49-    if (imageFormat) {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-50-        throw new TypeError(`The \`<OffthreadVideo>\` tag does no longer accept \`imageFormat\`. Use the \`transparent\` prop if you want to render a transparent video.`);
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-51-    }
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js:52:    return ((0, jsx_runtime_1.jsx)(exports.InnerOffthreadVideo, { acceptableTimeShiftInSeconds: acceptableTimeShiftInSeconds, allowAmplificationDuringRender: allowAmplificationDuringRender !== null && allowAmplificationDuringRender !== void 0 ? allowAmplificationDuringRender : true, audioStreamIndex: audioStreamIndex !== null && audioStreamIndex !== void 0 ? audioStreamIndex : 0, className: className, crossOrigin: crossOrigin, delayRenderRetries: delayRenderRetries, delayRenderTimeoutInMilliseconds: delayRenderTimeoutInMilliseconds, id: id, loopVolumeCurveBehavior: loopVolumeCurveBehavior !== null && loopVolumeCurveBehavior !== void 0 ? loopVolumeCurveBehavior : 'repeat', muted: muted !== null && muted !== void 0 ? muted : false, name: name, onAutoPlayError: onAutoPlayError !== null && onAutoPlayError !== void 0 ? onAutoPlayError : null, onError: onError, onVideoFrame: onVideoFrame, pauseWhenBuffering: pauseWhenBuffering !== null && pauseWhenBuffering !== void 0 ? pauseWhenBuffering : true, playbackRate: playbackRate !== null && playbackRate !== void 0 ? playbackRate : 1, toneFrequency: toneFrequency !== null && toneFrequency !== void 0 ? toneFrequency : 1, showInTimeline: showInTimeline !== null && showInTimeline !== void 0 ? showInTimeline : true, src: src, stack: stack, startFrom: startFrom, _remotionInternalNativeLoopPassed: _remotionInternalNativeLoopPassed !== null && _remotionInternalNativeLoopPassed !== void 0 ? _remotionInternalNativeLoopPassed : false, endAt: endAt, style: style, toneMapped: toneMapped !== null && toneMapped !== void 0 ? toneMapped : true, transparent: transparent !== null && transparent !== void 0 ? transparent : false, trimAfter: trimAfter, trimBefore: trimBefore, useWebAudioApi: useWebAudioApi !== null && useWebAudioApi !== void 0 ? useWebAudioApi : false, volume: volume }));
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-53-};
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-54-exports.OffthreadVideo = OffthreadVideo;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideo.js-55-(0, enable_sequence_stack_traces_js_1.addSequenceStackTraces)(exports.OffthreadVideo);
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-53-        mediaVolume: 1,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-54-    });
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-55-    (0, volume_safeguard_js_1.warnAboutTooHighVolume)(volume);
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-56-    (0, react_1.useEffect)(() => {
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-57-        var _a;
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-58-        if (!props.src) {
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-59-            throw new Error('No src passed');
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-60-        }
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js:61:        if (props.muted) {
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-62-            return;
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-63-        }
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-64-        if (volume <= 0) {
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-65-            return;
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-66-        }
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-67-        if (!window.remotion_audioEnabled) {
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-68-            return;
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-69-        }
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-76-            mediaFrame: frame,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-77-            playbackRate: playbackRate !== null && playbackRate !== void 0 ? playbackRate : 1,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-78-            toneFrequency: toneFrequency !== null && toneFrequency !== void 0 ? toneFrequency : 1,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-79-            audioStartFrame: Math.max(0, -((_a = sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.relativeFrom) !== null && _a !== void 0 ? _a : 0)),
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-80-            audioStreamIndex: audioStreamIndex !== null && audioStreamIndex !== void 0 ? audioStreamIndex : 0,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-81-        });
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-82-        return () => unregisterRenderAsset(id);
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-83-    }, [
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js:84:        props.muted,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-85-        props.src,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-86-        registerRenderAsset,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-87-        id,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-88-        unregisterRenderAsset,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-89-        volume,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-90-        frame,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-91-        absoluteFrame,
remotion/node_modules/remotion/dist/cjs/video/VideoForRendering.js-92-        playbackRate,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-15-const truthy_js_1 = require("../truthy.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-16-const use_current_frame_js_1 = require("../use-current-frame.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-17-const use_delay_render_js_1 = require("../use-delay-render.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-18-const use_unsafe_video_config_js_1 = require("../use-unsafe-video-config.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-19-const volume_prop_js_1 = require("../volume-prop.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-20-const volume_safeguard_js_1 = require("../volume-safeguard.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-21-const get_current_time_js_1 = require("./get-current-time.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-22-const offthread_video_source_js_1 = require("./offthread-video-source.js");
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js:23:const OffthreadVideoForRendering = ({ onError, volume: volumeProp, playbackRate, src, muted, allowAmplificationDuringRender, transparent, toneMapped, toneFrequency, name, loopVolumeCurveBehavior, delayRenderRetries, delayRenderTimeoutInMilliseconds, onVideoFrame, 
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-24-// Remove crossOrigin prop during rendering
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-25-// https://discord.com/channels/809501355504959528/844143007183667220/1311639632496033813
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-26-crossOrigin, audioStreamIndex, ...props }) => {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-27-    const absoluteFrame = (0, timeline_position_state_js_1.useTimelinePosition)();
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-28-    const frame = (0, use_current_frame_js_1.useCurrentFrame)();
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-29-    const volumePropsFrame = (0, use_audio_frame_js_1.useFrameForVolumeProp)(loopVolumeCurveBehavior);
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-30-    const videoConfig = (0, use_unsafe_video_config_js_1.useUnsafeVideoConfig)();
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-31-    const sequenceContext = (0, react_1.useContext)(SequenceContext_js_1.SequenceContext);
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-54-    (0, react_1.useEffect)(() => {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-55-        var _a;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-56-        if (!src) {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-57-            throw new Error('No src passed');
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-58-        }
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-59-        if (!window.remotion_audioEnabled) {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-60-            return;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-61-        }
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js:62:        if (muted) {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-63-            return;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-64-        }
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-65-        if (volume <= 0) {
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-66-            return;
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-67-        }
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-68-        registerRenderAsset({
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-69-            type: 'video',
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-70-            src: (0, absolute_src_js_1.getAbsoluteSrc)(src),
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-74-            mediaFrame: frame,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-75-            playbackRate,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-76-            toneFrequency,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-77-            audioStartFrame: Math.max(0, -((_a = sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.relativeFrom) !== null && _a !== void 0 ? _a : 0)),
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-78-            audioStreamIndex,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-79-        });
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-80-        return () => unregisterRenderAsset(id);
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-81-    }, [
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js:82:        muted,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-83-        src,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-84-        registerRenderAsset,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-85-        id,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-86-        unregisterRenderAsset,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-87-        volume,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-88-        frame,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-89-        absoluteFrame,
remotion/node_modules/remotion/dist/cjs/video/OffthreadVideoForRendering.js-90-        playbackRate,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-45-    (0, react_1.useEffect)(() => {
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-46-        var _a, _b;
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-47-        if (!props.src) {
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-48-            throw new Error('No src passed');
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-49-        }
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-50-        if (!window.remotion_audioEnabled) {
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-51-            return;
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-52-        }
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js:53:        if (props.muted) {
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-54-            return;
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-55-        }
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-56-        if (volume <= 0) {
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-57-            return;
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-58-        }
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-59-        registerRenderAsset({
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-60-            type: 'audio',
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-61-            src: (0, absolute_src_js_1.getAbsoluteSrc)(props.src),
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-65-            mediaFrame: frame,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-66-            playbackRate: (_a = props.playbackRate) !== null && _a !== void 0 ? _a : 1,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-67-            toneFrequency: toneFrequency !== null && toneFrequency !== void 0 ? toneFrequency : 1,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-68-            audioStartFrame: Math.max(0, -((_b = sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.relativeFrom) !== null && _b !== void 0 ? _b : 0)),
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-69-            audioStreamIndex: audioStreamIndex !== null && audioStreamIndex !== void 0 ? audioStreamIndex : 0,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-70-        });
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-71-        return () => unregisterRenderAsset(id);
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-72-    }, [
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js:73:        props.muted,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-74-        props.src,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-75-        registerRenderAsset,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-76-        absoluteFrame,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-77-        id,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-78-        unregisterRenderAsset,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-79-        volume,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-80-        volumePropFrame,
remotion/node_modules/remotion/dist/cjs/audio/AudioForRendering.js-81-        frame,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-53-const use_audio_frame_js_1 = require("./use-audio-frame.js");
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-54-const AudioForDevelopmentForwardRefFunction = (props, ref) => {
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-55-    var _a, _b, _c, _d;
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-56-    const [initialShouldPreMountAudioElements] = (0, react_1.useState)(props.shouldPreMountAudioTags);
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-57-    if (props.shouldPreMountAudioTags !== initialShouldPreMountAudioElements) {
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-58-        throw new Error('Cannot change the behavior for pre-mounting audio tags dynamically.');
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-59-    }
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-60-    const logLevel = (0, log_level_context_js_1.useLogLevel)();
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js:61:    const { volume, muted, playbackRate, shouldPreMountAudioTags, src, onDuration, acceptableTimeShiftInSeconds, _remotionInternalNeedsDurationCalculation, _remotionInternalNativeLoopPassed, _remotionInternalStack, allowAmplificationDuringRender, name, pauseWhenBuffering, showInTimeline, loopVolumeCurveBehavior, stack, crossOrigin, delayRenderRetries, delayRenderTimeoutInMilliseconds, toneFrequency, useWebAudioApi, onError, onNativeError, audioStreamIndex, ...nativeProps } = props;
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-62-    // Typecheck that we are not accidentially passing unrecognized props
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-63-    // to the DOM
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-64-    const _propsValid = true;
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-65-    if (!_propsValid) {
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-66-        throw new Error('typecheck error');
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-67-    }
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-68-    const [mediaVolume] = (0, volume_position_state_js_1.useMediaVolumeState)();
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-69-    const [mediaMuted] = (0, volume_position_state_js_1.useMediaMutedState)();
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-84-    (0, volume_safeguard_js_1.warnAboutTooHighVolume)(userPreferredVolume);
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-85-    const crossOriginValue = (0, get_cross_origin_value_js_1.getCrossOriginValue)({
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-86-        crossOrigin,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-87-        requestsVideoFrame: false,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-88-        isClientSideRendering: false,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-89-    });
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-90-    const propsToPass = (0, react_1.useMemo)(() => {
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-91-        return {
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js:92:            muted: muted || mediaMuted || isSequenceHidden || userPreferredVolume <= 0,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-93-            src: preloadedSrc,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-94-            loop: _remotionInternalNativeLoopPassed,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-95-            crossOrigin: crossOriginValue,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-96-            ...nativeProps,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-97-        };
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-98-    }, [
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-99-        _remotionInternalNativeLoopPassed,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-100-        isSequenceHidden,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-101-        mediaMuted,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js:102:        muted,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-103-        nativeProps,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-104-        preloadedSrc,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-105-        userPreferredVolume,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-106-        crossOriginValue,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-107-    ]);
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-108-    // Generate a string that's as unique as possible for this asset
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-109-    // but at the same time deterministic. We use it to combat strict mode issues.
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js:110:    const id = (0, react_1.useMemo)(() => `audio-${(0, random_js_1.random)(src !== null && src !== void 0 ? src : '')}-${sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.relativeFrom}-${sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.cumulatedFrom}-${sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.durationInFrames}-muted:${props.muted}-loop:${props.loop}`, [
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-111-        src,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-112-        sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.relativeFrom,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-113-        sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.cumulatedFrom,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-114-        sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.durationInFrames,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js:115:        props.muted,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-116-        props.loop,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-117-    ]);
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-118-    const { el: audioRef, mediaElementSourceNode, cleanupOnMediaTagUnmount, } = (0, shared_audio_tags_js_1.useSharedAudio)({
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-119-        aud: propsToPass,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-120-        audioId: id,
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-121-        premounting: Boolean(sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.premounting),
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-122-        postmounting: Boolean(sequenceContext === null || sequenceContext === void 0 ? void 0 : sequenceContext.postmounting),
remotion/node_modules/remotion/dist/cjs/audio/AudioForPreview.js-123-    });

 succeeded in 20ms:
2:remotion/node_modules/@remotion/renderer/dist/render-frame-with-option-to-reject.js-90-        .map((a) => a.audioAndVideoAssets)
3:remotion/node_modules/@remotion/renderer/dist/render-frame-with-option-to-reject.js-91-        .flat(2);
6:remotion/node_modules/@remotion/renderer/dist/render-frame-with-option-to-reject.js-94-        .flat(2);
7:remotion/node_modules/@remotion/renderer/dist/render-frame-with-option-to-reject.js-95-    const audioAndVideoAssets = (0, filter_asset_types_1.onlyAudioAndVideoAssets)(collectedAssets);
19:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-10-        return 'no';
20:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-11-    }
21:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-12-    if (enforceAudioTrack) {
22:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-13-        return 'yes';
23:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-14-    }
24:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-15-    if (assetsInfo === null) {
25:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-16-        return 'maybe';
26:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-17-    }
27:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js:18:    return assetsInfo.assets.flat(1).length > 0 ? 'yes' : 'no';
28:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-19-};
29:remotion/node_modules/@remotion/renderer/dist/render-has-audio.js-20-exports.getShouldRenderAudio = getShouldRenderAudio;
37:remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-119-    const audio = shouldRenderAudio && resolvedAudioCodec
38:remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-120-        ? await (0, create_audio_1.createAudio)({
39:remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:121:            assets: assetsInfo.assets,
42:remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js-124-            chunkLengthInSeconds: assetsInfo.chunkLengthInSeconds,
57:remotion/node_modules/@remotion/renderer/dist/stitch-frames-to-video.js:250:                if (parsed === assetsInfo.assets.length) {
110:remotion/node_modules/@remotion/renderer/dist/render-frames.js-186-        assetsInfo: {

exec
/bin/zsh -lc "rg -n \"enforceAudioTrack|enforce-audio-track\" remotion/node_modules/@remotion/renderer/dist/options/index.js remotion/node_modules/@remotion/renderer/dist/options/options-map.js remotion/node_modules/@remotion/cli/dist/parsed-cli.js remotion/node_modules/@remotion/cli/dist/config -g '*.js' | head -n 240" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
remotion/node_modules/@remotion/renderer/dist/options/options-map.js:171:        enforceAudioTrack: enforce_audio_1.enforceAudioOption,

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/run.py | sed -n '20,115p'; rg -n \"CommandTransport\\(|\\.run\\(.*backend=\" astrid/core/rendering astrid/packs/rendering | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    20	    sys.path.insert(0, str(_CHECKOUT_ROOT))
    21	
    22	def _request_path(argv: Sequence[str]) -> Path | None:
    23	    try:
    24	        index = argv.index("--request")
    25	        return Path(argv[index + 1])
    26	    except (ValueError, IndexError):
    27	        return None
    28	
    29	
    30	def _selects_finalizer(argv: Sequence[str]) -> bool:
    31	    """Route finalize and explicitly-namespaced support operations."""
    32	
    33	    selected = _transport_selected_backend()
    34	    if selected is not None:
    35	        # The transport-selected backend id is authoritative over request
    36	        # content: a remotion invocation must never route to the finalizer
    37	        # merely because the request carries a finalizer namespace.
    38	        return selected == "rendering.ffmpeg-finalizer"
    39	    if argv and argv[0] == "finalize":
    40	        return True
    41	    if not argv or argv[0] != "support":
    42	        return False
    43	    request_path = _request_path(argv)
    44	    if request_path is None:
    45	        return False
    46	    try:
    47	        payload = json.loads(request_path.read_text(encoding="utf-8"))
    48	    except (OSError, json.JSONDecodeError):
    49	        return False
    50	    if not isinstance(payload, Mapping):
    51	        return False
    52	    backend_config = payload.get("backend_config")
    53	    return isinstance(backend_config, Mapping) and (
    54	        "rendering.ffmpeg-finalizer" in backend_config
    55	    )
    56	
    57	
    58	def _transport_selected_backend() -> str | None:
    59	    """The transport sets ASTRID_RENDER_BACKEND to the qualified backend id
    60	    it selected; this is authoritative over any request content."""
    61	    value = __import__("os").environ.get("ASTRID_RENDER_BACKEND")
    62	    if isinstance(value, str) and value:
    63	        return value
    64	    return None
    65	
    66	
    67	def _selects_ffmpeg(argv: Sequence[str]) -> bool:
    68	    """Select FFmpeg from the transport-selected backend id or the request's
    69	    backend-config namespace.
    70	
    71	    The launcher never guesses from timeline shape: a shape guess can route a
    72	    Remotion request to FFmpeg or vice versa.  The legacy media-only
    73	    auto-route lives inside the Remotion backend's own support logic.
    74	    """
    75	
    76	    selected = _transport_selected_backend()
    77	    if selected is not None:
    78	        return selected == "rendering.ffmpeg"
    79	    request_path = _request_path(argv)
    80	    if request_path is None:
    81	        return False
    82	    try:
    83	        payload = json.loads(request_path.read_text(encoding="utf-8"))
    84	    except (OSError, json.JSONDecodeError):
    85	        return False
    86	    if not isinstance(payload, Mapping):
    87	        return False
    88	    backend_config = payload.get("backend_config")
    89	    if not isinstance(backend_config, Mapping):
    90	        return False
    91	    if "rendering.ffmpeg" in backend_config:
    92	        return True
    93	    return False
    94	
    95	
    96	def main(argv: Sequence[str] | None = None) -> int:
    97	    args = list(sys.argv[1:] if argv is None else argv)
    98	    if _selects_finalizer(args):
    99	        from astrid.packs.rendering.finalizers.ffmpeg.run import (
   100	            main as backend_main,
   101	        )
   102	    elif _selects_ffmpeg(args):
   103	        from astrid.packs.rendering.backends.ffmpeg.run import main as backend_main
   104	    else:
   105	        from astrid.packs.rendering.backends.remotion.run import main as backend_main
   106	
   107	    return backend_main(args)
   108	
   109	
   110	if __name__ == "__main__":
   111	    raise SystemExit(main())

exec
/bin/zsh -lc "cat astrid/packs/rendering/pack.yaml; find astrid/packs/rendering -maxdepth 4 -name '*.yaml' -print | sort | xargs rg -n \""'^(id|command|operations):|run.py"' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
schema_version: 1
id: rendering
name: Astrid Rendering
version: 1.0.0
origin: builtin
install_tier: core
pack_type: capability
domain: media
stability: stable
support: core
visibility: visible
permissions:
  - id: subprocess
    reason: Runs Remotion render process and ffmpeg sprite processing.
  - id: project_files
    reason: Reads timeline, asset, and theme files; writes rendered video.
  - id: network
    reason: Sprite sheet executor calls OpenAI GPT Image API.
description: Render timelines to video via Remotion, generate GPT-Image sprite sheets, and supply render-time animation/transition/effect elements.
keywords:
- render
- remotion
- video
- mp4
- timeline
- sprite-sheet
- gpt-image
- animation
capabilities:
- render_timeline
- generate_sprite_sheet
- scaffold_html_canvas_effect
agent:
  purpose: Choose this pack to turn a brief timeline into a finished video (hype.mp4) via Remotion, to generate/slice GPT Image sprite sheets, or to wrap content in a canvas/WebGL post-processing effect.
  do_not_use_for: Not for publishing the rendered output to the Reigh platform; use the reigh pack for handoff after rendering.
  normal_entrypoints:
  - rendering.render
  - rendering.sprite_sheet
content:
  executors: executors
  elements: elements
extensions:
  rendering:
    renderers:
      - backends/remotion/renderer.yaml
      - backends/ffmpeg/renderer.yaml
    finalizers:
      - finalizers/ffmpeg/finalizer.yaml
aliases:
- kind: executor
  alias: builtin.render
  canonical_id: rendering.render
  deprecated: true
  deprecation_message: Moved to rendering.render
- kind: executor
  alias: builtin.html_canvas_effect
  canonical_id: rendering.html_canvas_effect
  deprecated: true
  deprecation_message: Moved to rendering.html_canvas_effect
- kind: executor
  alias: builtin.sprite_sheet
  canonical_id: rendering.sprite_sheet
  deprecated: true
  deprecation_message: Moved to rendering.sprite_sheet
astrid/packs/rendering/backends/remotion/renderer.yaml:2:id: rendering.remotion
astrid/packs/rendering/backends/remotion/renderer.yaml:6:command:
astrid/packs/rendering/backends/remotion/renderer.yaml:8:  - run.py
astrid/packs/rendering/backends/remotion/renderer.yaml:9:operations:
astrid/packs/rendering/pack.yaml:2:id: rendering
astrid/packs/rendering/finalizers/ffmpeg/finalizer.yaml:2:id: rendering.ffmpeg-finalizer
astrid/packs/rendering/finalizers/ffmpeg/finalizer.yaml:6:command:
astrid/packs/rendering/finalizers/ffmpeg/finalizer.yaml:8:  - run.py
astrid/packs/rendering/finalizers/ffmpeg/finalizer.yaml:9:operations:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml:2:id: rendering.ffmpeg
astrid/packs/rendering/backends/ffmpeg/renderer.yaml:6:command:
astrid/packs/rendering/backends/ffmpeg/renderer.yaml:8:  - run.py
astrid/packs/rendering/backends/ffmpeg/renderer.yaml:9:operations:
astrid/packs/rendering/executors/timeline_storyboard/executor.yaml:90:    "runtime_file": "run.py",
astrid/packs/rendering/executors/sprite_sheet/executor.yaml:62:    "runtime_file": "run.py",
astrid/packs/rendering/executors/render/executor.yaml:133:    "runtime_file": "run.py",
astrid/packs/rendering/executors/html_canvas_effect/executor.yaml:70:    "runtime_file": "run.py",

exec
/bin/zsh -lc 'ffmpeg -hide_banner -loglevel error -f lavfi -i color=c=black:s=64x64:r=60:d=0.2 -an -c:v libx264 -pix_fmt yuv420p -movflags frag_keyframe+empty_moov -f mp4 pipe:1 | ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate,time_base,codec_name,profile,level,pix_fmt -of default=noprint_wrappers=1 pipe:0' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 71ms:
codec_name=h264
profile=High
pix_fmt=yuv420p
level=10
r_frame_rate=60/1
time_base=1/15360

exec
/bin/zsh -lc 'rg -n "''^def support'"\\(\" astrid/packs/rendering/backends/ffmpeg/run.py; nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '250,360p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
247:def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
   250	    timeline_path = _input_path(request.timeline_path, workspace)
   251	    if request.assets_registry_path is None:
   252	        return _support_load_failure("rendering.ffmpeg requires an assets registry")
   253	    assets_path = _input_path(request.assets_registry_path, workspace)
   254	    try:
   255	        timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   256	        if not isinstance(timeline_data, dict):
   257	            raise ValueError("timeline must contain a JSON object")
   258	        assets = timeline.load_registry(assets_path)
   259	    except Exception as exc:
   260	        return _support_load_failure(str(exc) or type(exc).__name__)
   261	
   262	    localized = replace(
   263	        request,
   264	        timeline_path=str(timeline_path),
   265	        assets_registry_path=str(assets_path),
   266	    )
   267	    return strict_support(
   268	        localized,
   269	        timeline_data,
   270	        assets,
   271	        probe=ffprobe_metadata_strict,
   272	    )
   273	
   274	
   275	def _support_load_failure(reason: str) -> SupportReport:
   276	    return SupportReport(
   277	        schema_version=SCHEMA_VERSION,
   278	        supported=False,
   279	        reasons=[reason],
   280	        features={
   281	            "media_only": False,
   282	            "full_timeline": True,
   283	            "windows": False,
   284	            "sequential_audio": True,
   285	            "audio_reactive_colour": False,
   286	            "whole_media": False,
   287	            "whole_media_optimization": False,
   288	            "stream_copy": False,
   289	            "audio_ownership": AudioOwnership.NONE.value,
   290	        },
   291	        alternatives=list(ALTERNATIVE_BACKENDS),
   292	        backend=BACKEND_ID,
   293	        backend_version=BACKEND_VERSION,
   294	    )
   295	
   296	
   297	def _audio_reactive_ffmpeg_element(
   298	    theme_path: Path | None,
   299	) -> Any | None:
   300	    effects, _aliases = remotion_backend._effect_registry_for_assets(theme_path)
   301	    element = effects.get(audio_reactive_colour.EFFECT_ID)
   302	    if (
   303	        element is None
   304	        or element.metadata.get("ffmpegAdapter")
   305	        != audio_reactive_colour.ADAPTER_ID
   306	    ):
   307	        return None
   308	    return element
   309	
   310	
   311	def render_audio_reactive_colour_if_supported(
   312	    timeline_path: Path,
   313	    assets_path: Path,
   314	    out_path: Path,
   315	    *,
   316	    project_dir: Path | None,
   317	    composition_id: str,
   318	    theme_path: Path | None,
   319	    previous_outputs: Sequence[Path] = (),
   320	    element_resolver: Any | None = None,
   321	) -> Path | None:
   322	    """Preserve the facade's early audio-reactive FFmpeg specialization."""
   323	
   324	    timeline_data = json.loads(Path(timeline_path).read_text(encoding="utf-8"))
   325	    clips = timeline_data.get("clips")
   326	    if (
   327	        not isinstance(clips, list)
   328	        or len(clips) != 2
   329	        or sum(
   330	            isinstance(clip, dict)
   331	            and clip.get("clipType") == audio_reactive_colour.EFFECT_ID
   332	            for clip in clips
   333	        )
   334	        != 1
   335	    ):
   336	        return None
   337	    resolve_element = _audio_reactive_ffmpeg_element
   338	    if element_resolver is not None:
   339	        resolve_element = element_resolver
   340	    element = resolve_element(theme_path)
   341	    if element is None:
   342	        return None
   343	    registry = timeline.load_registry(Path(assets_path))
   344	    spec = audio_reactive_colour.match_and_validate(
   345	        timeline_data,
   346	        registry,
   347	        Path(assets_path),
   348	    )
   349	    if spec is None:
   350	        return None
   351	
   352	    resolved_out = Path(out_path).resolve()
   353	    resolved_out.parent.mkdir(parents=True, exist_ok=True)
   354	    stage_summary = {
   355	        "root": None,
   356	        "effects": [
   357	            {
   358	                "effect_id": element.id,
   359	                "source_pack_id": remotion_backend._source_pack_id(element),
   360	                "source": element.source,

exec
/bin/zsh -lc "rg -n \"def validate_ffmpeg_media_timeline\" astrid/packs/rendering/backends/ffmpeg/command.py astrid/packs/rendering/backends/ffmpeg/support.py; nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '65,95p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/ffmpeg/command.py:75:def validate_ffmpeg_media_timeline(timeline_data: Mapping[str, Any]) -> None:
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

2026-08-12T12:11:23.284313Z ERROR codex_core::tools::router: error=timeout_ms must be at least 10000
collab: Wait
exec
/bin/zsh -lc "rg -n \"output_name|suffix|\\.mp4\" astrid/packs/rendering/backends/ffmpeg/run.py astrid/packs/rendering/backends/ffmpeg/support.py astrid/packs/rendering/backends/remotion/run.py astrid/core/rendering/contracts.py | head -n 260" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '1180,1330p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 731ms:
astrid/core/rendering/contracts.py:780:    output_name: str
astrid/core/rendering/contracts.py:803:        output_name = _require_string(self.output_name, "output_name")
astrid/core/rendering/contracts.py:804:        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
astrid/core/rendering/contracts.py:805:            raise ValueError("output_name must be a portable basename without path separators")
astrid/core/rendering/contracts.py:806:        object.__setattr__(self, "output_name", output_name)
astrid/core/rendering/contracts.py:827:                "output_name": self.output_name,
astrid/core/rendering/contracts.py:844:                "output_name",
astrid/core/rendering/contracts.py:853:                required={"schema_version", "timeline_path", "output_name"},
astrid/core/rendering/contracts.py:868:                output_name=data["output_name"],
astrid/core/rendering/contracts.py:894:            output_name=self.output_name,
astrid/core/rendering/contracts.py:1711:    output_name: str
astrid/core/rendering/contracts.py:1743:        output_name = _require_string(self.output_name, "output_name")
astrid/core/rendering/contracts.py:1744:        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
astrid/core/rendering/contracts.py:1745:            raise ValueError("output_name must be a portable basename without path separators")
astrid/core/rendering/contracts.py:1749:        object.__setattr__(self, "output_name", output_name)
astrid/core/rendering/contracts.py:1806:                "output_name": self.output_name,
astrid/core/rendering/contracts.py:1820:                "output_name",
astrid/core/rendering/contracts.py:1826:                required={"schema_version", "plan", "artifacts", "output_name"},
astrid/core/rendering/contracts.py:1835:                output_name=data["output_name"],
astrid/packs/rendering/backends/remotion/run.py:828:    if localized.exists() or len(candidate.parts) > 1 or candidate.suffix:
astrid/packs/rendering/backends/remotion/run.py:1081:    output_path = outputs_dir / request.output_name
astrid/packs/rendering/backends/remotion/run.py:1111:                prefix=f".{request.output_name}.remotion-",
astrid/packs/rendering/backends/remotion/run.py:1115:        staged_video = Path(private_tmp) / request.output_name
astrid/packs/rendering/backends/ffmpeg/run.py:103:        output_name=Path(out_path).name,
astrid/packs/rendering/backends/ffmpeg/run.py:557:    output_path = outputs_dir / request.output_name

 succeeded in 711ms:
  1180	            "manifest_digest",
  1181	            "alias_chain",
  1182	            "override",
  1183	            "support_decision",
  1184	            "trust_eligibility",
  1185	        }
  1186	        _validate_object_keys(data, required=required, allowed=required, label="renderer resolution")
  1187	        return cls(
  1188	            id=data["id"],
  1189	            source_pack=data["source_pack"],
  1190	            manifest_digest=data["manifest_digest"],
  1191	            alias_chain=data["alias_chain"],
  1192	            override=data["override"],
  1193	            support_decision=SupportReport.from_dict(data["support_decision"]),
  1194	            trust_eligibility=data["trust_eligibility"],
  1195	        )
  1196	
  1197	
  1198	@dataclass(frozen=True)
  1199	class FinalizerResolution:
  1200	    """Resolved finalizer identity pinned for standalone finalization."""
  1201	
  1202	    id: str
  1203	    source_pack: dict[str, Any]
  1204	    manifest_digest: str
  1205	    alias_chain: list[str] = field(default_factory=list)
  1206	    override: dict[str, Any] | None = None
  1207	    trust_eligibility: dict[str, Any] = field(default_factory=dict)
  1208	    support_decision: SupportReport | None = None
  1209	
  1210	    def __post_init__(self) -> None:
  1211	        object.__setattr__(self, "id", _require_qualified_id(self.id, "finalizer id"))
  1212	        object.__setattr__(
  1213	            self,
  1214	            "source_pack",
  1215	            _json_safe_mapping(self.source_pack, label="finalizer source_pack"),
  1216	        )
  1217	        object.__setattr__(
  1218	            self,
  1219	            "manifest_digest",
  1220	            _require_sha256(self.manifest_digest, "finalizer manifest_digest"),
  1221	        )
  1222	        object.__setattr__(
  1223	            self,
  1224	            "trust_eligibility",
  1225	            _json_safe_mapping(
  1226	                self.trust_eligibility,
  1227	                label="finalizer trust_eligibility",
  1228	            ),
  1229	        )
  1230	        object.__setattr__(
  1231	            self,
  1232	            "alias_chain",
  1233	            [
  1234	                _require_string(item, f"finalizer alias_chain[{index}]")
  1235	                for index, item in enumerate(_require_string_list(self.alias_chain, "finalizer alias_chain"))
  1236	            ],
  1237	        )
  1238	        if self.override is not None:
  1239	            object.__setattr__(
  1240	                self,
  1241	                "override",
  1242	                _require_override(
  1243	                    self.override,
  1244	                    capability_id=self.id,
  1245	                    label="finalizer override",
  1246	                ),
  1247	            )
  1248	        if self.support_decision is not None:
  1249	            support = (
  1250	                self.support_decision
  1251	                if isinstance(self.support_decision, SupportReport)
  1252	                else SupportReport.from_dict(
  1253	                    _require_mapping(
  1254	                        self.support_decision, "finalizer support_decision"
  1255	                    )
  1256	                )
  1257	            )
  1258	            if support.backend != self.id:
  1259	                raise ValueError("finalizer support_decision.backend must match finalizer id")
  1260	            object.__setattr__(self, "support_decision", support)
  1261	
  1262	    def to_dict(self) -> dict[str, Any]:
  1263	        return _json_safe_mapping(
  1264	            {
  1265	                "id": self.id,
  1266	                "source_pack": self.source_pack,
  1267	                "manifest_digest": self.manifest_digest,
  1268	                "alias_chain": list(self.alias_chain),
  1269	                "override": self.override,
  1270	                "trust_eligibility": self.trust_eligibility,
  1271	                "support_decision": self.support_decision,
  1272	            }
  1273	        )
  1274	
  1275	    @classmethod
  1276	    def from_dict(cls, payload: Mapping[str, Any]) -> FinalizerResolution:
  1277	        data = _require_mapping(payload, "finalizer resolution")
  1278	        required = {
  1279	            "id",
  1280	            "source_pack",
  1281	            "manifest_digest",
  1282	            "alias_chain",
  1283	            "override",
  1284	            "trust_eligibility",
  1285	            "support_decision",
  1286	        }
  1287	        _validate_object_keys(data, required=required, allowed=required, label="finalizer resolution")
  1288	        return cls(
  1289	            id=data["id"],
  1290	            source_pack=data["source_pack"],
  1291	            manifest_digest=data["manifest_digest"],
  1292	            alias_chain=data["alias_chain"],
  1293	            override=data["override"],
  1294	            trust_eligibility=data["trust_eligibility"],
  1295	            support_decision=data["support_decision"],
  1296	        )
  1297	
  1298	
  1299	def _normalize_requested_policy(value: Any, label: str = "requested_policy") -> str | dict[str, Any]:
  1300	    if isinstance(value, str):
  1301	        return _require_string(value, label)
  1302	    return _json_safe_mapping(value, label=label)
  1303	
  1304	
  1305	@dataclass(frozen=True)
  1306	class RenderSegment:
  1307	    """One complete temporal window assigned to one qualified backend."""
  1308	
  1309	    window: FrameWindow
  1310	    renderer: RendererResolution
  1311	    input_hashes: dict[str, str] = field(default_factory=dict)
  1312	
  1313	    def __post_init__(self) -> None:
  1314	        object.__setattr__(self, "window", _coerce_window(self.window, "segment window", nullable=False))
  1315	        renderer = (
  1316	            self.renderer
  1317	            if isinstance(self.renderer, RendererResolution)
  1318	            else RendererResolution.from_dict(_require_mapping(self.renderer, "segment renderer"))
  1319	        )
  1320	        object.__setattr__(self, "renderer", renderer)
  1321	        object.__setattr__(
  1322	            self,
  1323	            "input_hashes",
  1324	            _require_hash_mapping(self.input_hashes, "segment input_hashes"),
  1325	        )
  1326	
  1327	    @property
  1328	    def backend(self) -> str:
  1329	        """Compatibility accessor; ``renderer.id`` is authoritative."""
  1330	

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '760,875p'; cat astrid/packs/rendering/backends/ffmpeg/renderer.yaml; cat astrid/packs/rendering/backends/remotion/renderer.yaml" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
schema_version: 1
id: rendering.ffmpeg
name: FFmpeg Media Renderer
version: 1.0.0
protocol_version: 1
command:
  - python3
  - run.py
operations:
  - render
  - support
description: Render legacy media-only timelines with FFmpeg.
capabilities:
  clip_types:
    - media
  track_types:
    - visual
    - audio
  features:
    media_only: true
    stream_copy: true
    sequential_audio: true
  supports_full_timeline: true
  supports_windows: false
  output_profiles:
    - video/mp4
  audio_ownership:
    - rendered
    - passthrough
    - none
required_permissions:
  - project_files
  - subprocess
required_binaries:
  - ffmpeg
  - ffprobe
schema_version: 1
id: rendering.remotion
name: Remotion Timeline Renderer
version: 1.0.0
protocol_version: 1
command:
  - python3
  - run.py
operations:
  - render
  - support
description: Render complete Astrid timelines with TimelineComposition and Remotion.
capabilities:
  clip_types:
    - media
    - text
  track_types:
    - visual
    - audio
  features:
    timeline_composition: true
    merged_themes: true
    effects: true
    animations: true
    transitions: true
    html_in_canvas: true
  supports_full_timeline: true
  supports_windows: false
  output_profiles:
    - video/mp4
  audio_ownership:
    - rendered
required_permissions:
  - project_files
  - subprocess
required_binaries:
  - node
  - npx
  - ffprobe

exec
/bin/zsh -lc "find /tmp -maxdepth 4 -name 'remotion-smoke.mp4' -o -name '*remotion*smoke*.mp4' 2>/dev/null | head -n 30" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 518ms:
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c '
from astrid.core.media import MediaProbe
from astrid.core.rendering.contracts import RenderProfile, RenderRequest
from astrid.packs.rendering.backends.ffmpeg.support import support
timeline = {\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":60}}},\"tracks\":[{\"id\":\"v\",\"kind\":\"visual\",\"label\":\"Video\"}],\"clips\":[{\"id\":\"v1\",\"at\":0,\"track\":\"v\",\"clipType\":\"media\",\"asset\":\"video\",\"from\":0,\"to\":1,\"speed\":1,\"volume\":0}]}
assets={\"assets\":{\"video\":{\"file\":\"/bin/sh\",\"type\":\"video/mp4\",\"duration\":1,\"resolution\":\"640x360\",\"fps\":60}}}
profile=RenderProfile(width=640,height=360,fps_rational=(60,1),time_base=(1,15360),container=\"mp4\",video_codec=\"h264\",pixel_format=\"yuv420p\")
req=RenderRequest(schema_version=1,timeline_path=\"/tmp/t.json\",assets_registry_path=\"/tmp/a.json\",output_name=\"o.mp4\",profile=profile,backend_config={\"rendering.ffmpeg\":{}})
probe=MediaProbe(duration_seconds=1,width=640,height=360,fps=60,video_codec=\"h264\",pixel_format=\"yuv420p\",video_stream_present=True,audio_stream_present=False)
r=support(req,timeline,assets,probe=lambda _:probe,which=lambda _:\"/usr/bin/tool\")
print(r.supported); print(*r.reasons,sep=\"\\n\")
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 13576ms:
False
requested profile time_base=(1, 15360) is not produced by rendering.ffmpeg (produces (1, 30720))

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'from astrid.core.rendering.profile import _mp4_time_base; from fractions import Fraction; print(_mp4_time_base(Fraction(60,1)))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 2810ms:
(1, 15360)

collab: Wait
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'from astrid.core.rendering.contracts import RenderProfile,RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import _profile_support_reasons; t={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":30}}}}; p=RenderProfile(width=640,height=360,fps_rational=(30000,1001),time_base=(1,15360),container=\"mp4\",video_codec=\"h264\",pixel_format=\"yuv420p\"); r=RenderRequest(schema_version=1,timeline_path=\"t\",output_name=\"o.mp4\",profile=p); print(_profile_support_reasons(r,t))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 1070ms:
[]

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'from astrid.core.rendering.contracts import RenderProfile,RenderRequest; from astrid.packs.rendering.backends.ffmpeg.support import _profile_support_reasons; t={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":60}}}}; p=RenderProfile(width=640,height=360,fps_rational=(60,1),time_base=(1,15360),container=\"mp4\",video_codec=\"h264\",pixel_format=\"yuv420p\"); r=RenderRequest(schema_version=1,timeline_path=\"t\",output_name=\"o.mp4\",profile=p); print(_profile_support_reasons(r,t))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 310ms:
['requested profile time_base=(1, 15360) is not produced by rendering.ffmpeg (produces (1, 30720))']

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'from astrid.core.media import MediaProbe; from astrid.packs.rendering.backends.ffmpeg.support import _whole_media_optimization; t={\"theme_overrides\":{\"visual\":{\"canvas\":{\"width\":640,\"height\":360,\"fps\":30}}},\"tracks\":[{\"id\":\"v\",\"kind\":\"visual\"}],\"clips\":[{\"id\":\"v\",\"track\":\"v\",\"clipType\":\"media\",\"asset\":\"a\",\"at\":0,\"from\":0,\"to\":1,\"speed\":1}]}; a={\"assets\":{\"a\":{\"duration\":1,\"resolution\":\"640x360\",\"fps\":30}}}; p=MediaProbe(duration_seconds=31/30,width=640,height=360,fps=30,video_codec=\"h264\",pixel_format=\"yuv420p\",video_stream_present=True); print(_whole_media_optimization(t,a,{\"a\":p}))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 5604ms:
True

exec
/bin/zsh -lc "rg -n \"<Audio|AudioTrack|audio\" remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx remotion/node_modules/@banodoco/timeline-composition/typescript/src -g '*.tsx' | head -n 180; nl -ba remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 706ms:
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:10:import {AudioTrack} from './AudioTrack';
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:16:import {getAudioTracks, getVisualTracks} from './lib/tracks';
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:243:const renderAudioTrack = (
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:257:        <AudioTrack clip={clip} track={track} assetEntry={assetEntry} fps={fps} />
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:267:  const audioTracks = getAudioTracks(timeline);
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:283:          audioTracks={audioTracks}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:300:  audioTracks,
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:306:  audioTracks: TrackDefinition[];
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:318:      {audioTracks.map((track) => {
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:320:        return renderAudioTrack(track, clips, assets, fps);
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:10:import {AudioTrack} from './AudioTrack';
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:16:import {getAudioTracks, getVisualTracks} from './lib/tracks';
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:243:const renderAudioTrack = (
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:257:        <AudioTrack clip={clip} track={track} assetEntry={assetEntry} fps={fps} />
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:267:  const audioTracks = getAudioTracks(timeline);
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:283:          audioTracks={audioTracks}
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:300:  audioTracks,
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:306:  audioTracks: TrackDefinition[];
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:318:      {audioTracks.map((track) => {
remotion/node_modules/@banodoco/timeline-composition/typescript/src/TimelineComposition.tsx:320:        return renderAudioTrack(track, clips, assets, fps);
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:11:type AudioTrackProps = {
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:37:export const AudioTrack: FC<AudioTrackProps> = ({clip, track, assetEntry, fps}) => {
remotion/node_modules/@banodoco/timeline-composition/typescript/src/AudioTrack.tsx:73:    <Audio
     1	// Sprint 5: physically moved + renamed from
     2	// tools/remotion/src/HypeComposition.tsx → TimelineComposition.tsx.
     3	//
     4	// Composition id rename: `HypeComposition` → `TimelineComposition`.
     5	// Banodoco's CLI render path passes the new id; the in-tree shell at
     6	// tools/remotion/src/Root.tsx imports this composition from the package.
     7	
     8	import type {ReactElement} from 'react';
     9	import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
    10	import {AudioTrack} from './AudioTrack';
    11	import {CLIP_TYPE_ALIASES, EFFECT_REGISTRY, type EffectId} from './effects.generated';
    12	import {DEFAULT_THEME, ThemeProvider, useTheme} from './ThemeContext';
    13	import {VisualClip} from './VisualClip';
    14	import {resolveParams} from './lib/effect-params';
    15	import {getClipDurationInFrames} from './lib/duration';
    16	import {getAudioTracks, getVisualTracks} from './lib/tracks';
    17	import {
    18	  CrossFadeLayer,
    19	  TransitionSeries,
    20	  resolveTransitionReference,
    21	} from './lib/transitions';
    22	import type {
    23	  AssetRegistryEntry,
    24	  HypeCompositionProps,
    25	  TimelineClip,
    26	  TimelineCompositionProps,
    27	  TrackDefinition,
    28	} from './types';
    29	
    30	const sortClipsByAt = (clips: TimelineClip[]): TimelineClip[] => {
    31	  return [...clips].sort((left, right) => left.at - right.at);
    32	};
    33	
    34	const hasPositionOverride = (clip: TimelineClip): boolean => {
    35	  return (
    36	    clip.x !== undefined
    37	    || clip.y !== undefined
    38	    || clip.width !== undefined
    39	    || clip.height !== undefined
    40	    || clip.cropTop !== undefined
    41	    || clip.cropBottom !== undefined
    42	    || clip.cropLeft !== undefined
    43	    || clip.cropRight !== undefined
    44	  );
    45	};
    46	
    47	const getAssetEntry = (
    48	  clip: TimelineClip,
    49	  assets: TimelineCompositionProps['assets'],
    50	): AssetRegistryEntry | undefined => {
    51	  return clip.asset ? assets.assets[clip.asset] : undefined;
    52	};
    53	
    54	const renderVisualClipContent = (
    55	  track: TrackDefinition,
    56	  clip: TimelineClip,
    57	  assets: TimelineCompositionProps['assets'],
    58	  fps: number,
    59	  theme: ReturnType<typeof useTheme>,
    60	): ReactElement | null => {
    61	  if (clip.clipType === 'effect-layer') {
    62	    return null;
    63	  }
    64	
    65	  // Sprint 5 EFFECT_REGISTRY dispatch (the migration target cited at
    66	  // tools/remotion/src/HypeComposition.tsx:58-64). Same shape; the
    67	  // registry now lives inside the package.
    68	  const effectId = (
    69	    clip.clipType && clip.clipType in EFFECT_REGISTRY
    70	      ? clip.clipType as EffectId
    71	      : clip.clipType ? CLIP_TYPE_ALIASES[clip.clipType] : undefined
    72	  );
    73	  if (effectId) {
    74	    const EffectComponent = EFFECT_REGISTRY[effectId];
    75	    const assetEntry = getAssetEntry(clip, assets);
    76	    return (
    77	      <EffectComponent
    78	        clip={clip}
    79	        params={resolveParams(clip)}
    80	        theme={theme}
    81	        fps={fps}
    82	        assetEntry={assetEntry}
    83	      />
    84	    );
    85	  }
    86	
    87	  const assetEntry = getAssetEntry(clip, assets);
    88	  const baseVisual = (
    89	    <VisualClip clip={clip} track={track} assetEntry={assetEntry} fps={fps} />
    90	  );
    91	
    92	  if (hasPositionOverride(clip)) {
    93	    return baseVisual;
    94	  }
    95	
    96	  if ((track.scale ?? 1) !== 1) {
    97	    return (
    98	      <AbsoluteFill
    99	        style={{
   100	          transform: `scale(${track.scale})`,
   101	          transformOrigin: 'center center',
   102	          overflow: 'hidden',
   103	          isolation: 'isolate',
   104	        }}
   105	      >
   106	        {baseVisual}
   107	      </AbsoluteFill>
   108	    );
   109	  }
   110	
   111	  return baseVisual;
   112	};
   113	
   114	const renderVisualSequence = (
   115	  track: TrackDefinition,
   116	  clip: TimelineClip,
   117	  assets: TimelineCompositionProps['assets'],
   118	  fps: number,
   119	  theme: ReturnType<typeof useTheme>,
   120	): ReactElement | null => {
   121	  const content = renderVisualClipContent(track, clip, assets, fps, theme);
   122	  if (!content) {
   123	    return null;
   124	  }
   125	  return (
   126	    <Sequence
   127	      key={clip.id}
   128	      from={Math.round(clip.at * fps)}
   129	      durationInFrames={getClipDurationInFrames(clip, fps)}
   130	    >
   131	      {content}
   132	    </Sequence>
   133	  );
   134	};
   135	
   136	const renderTransitionGroup = (
   137	  track: TrackDefinition,
   138	  fromClip: TimelineClip,
   139	  toClip: TimelineClip,
   140	  assets: TimelineCompositionProps['assets'],
   141	  fps: number,
   142	  theme: ReturnType<typeof useTheme>,
   143	): ReactElement | null => {
   144	  const transition = resolveTransitionReference(fromClip.transition as never, theme, fps);
   145	  if (!transition) {
   146	    return null;
   147	  }
   148	  const fromDuration = getClipDurationInFrames(fromClip, fps);
   149	  const toDuration = getClipDurationInFrames(toClip, fps);
   150	  if (transition.durationFrames <= 0 || transition.durationFrames > fromDuration || transition.durationFrames > toDuration) {
   151	    return null;
   152	  }
   153	
   154	  const fromContent = renderVisualClipContent(track, fromClip, assets, fps, theme);
   155	  const toContent = renderVisualClipContent(track, toClip, assets, fps, theme);
   156	  if (!fromContent || !toContent) {
   157	    return null;
   158	  }
   159	
   160	  const groupFrom = Math.round(fromClip.at * fps);
   161	  const toOffset = Math.max(0, fromDuration - transition.durationFrames);
   162	  const groupDuration = toOffset + toDuration;
   163	  return (
   164	    <Sequence
   165	      key={`${fromClip.id}-${toClip.id}-transition`}
   166	      from={groupFrom}
   167	      durationInFrames={groupDuration}
   168	    >
   169	      <TransitionSeries>
   170	        <Sequence from={0} durationInFrames={fromDuration}>
   171	          <CrossFadeLayer
   172	            role="from"
   173	            durationFrames={fromDuration}
   174	            transitionDurationFrames={transition.durationFrames}
   175	          >
   176	            {fromContent}
   177	          </CrossFadeLayer>
   178	        </Sequence>
   179	        <Sequence from={toOffset} durationInFrames={toDuration}>
   180	          <CrossFadeLayer
   181	            role="to"
   182	            durationFrames={toDuration}
   183	            transitionDurationFrames={transition.durationFrames}
   184	          >
   185	            {toContent}
   186	          </CrossFadeLayer>
   187	        </Sequence>
   188	      </TransitionSeries>
   189	    </Sequence>
   190	  );
   191	};
   192	
   193	const clipsCanTransition = (fromClip: TimelineClip, toClip: TimelineClip, fps: number): boolean => {
   194	  if (!fromClip.transition || fromClip.clipType === 'effect-layer' || toClip.clipType === 'effect-layer') {
   195	    return false;
   196	  }
   197	  const fromStart = Math.round(fromClip.at * fps);
   198	  const fromEnd = fromStart + getClipDurationInFrames(fromClip, fps);
   199	  const toStart = Math.round(toClip.at * fps);
   200	  return toStart >= fromStart && toStart <= fromEnd;
   201	};
   202	
   203	const renderVisualTrack = (
   204	  track: TrackDefinition,
   205	  clips: TimelineClip[],
   206	  assets: TimelineCompositionProps['assets'],
   207	  fps: number,
   208	  theme: ReturnType<typeof useTheme>,
   209	): ReactElement | null => {
   210	  const sortedClips = sortClipsByAt(clips);
   211	  if (sortedClips.length === 0) {
   212	    return null;
   213	  }
   214	
   215	  const rendered: Array<ReactElement | null> = [];
   216	  for (let index = 0; index < sortedClips.length; index += 1) {
   217	    const clip = sortedClips[index];
   218	    const nextClip = sortedClips[index + 1];
   219	    if (nextClip && clipsCanTransition(clip, nextClip, fps)) {
   220	      const group = renderTransitionGroup(track, clip, nextClip, assets, fps, theme);

exec
/bin/zsh -lc 'ffmpeg -hide_banner -loglevel error -f lavfi -i color=c=black:s=64x64:r=30:d=0.2 -an -c:v libx264 -pix_fmt yuv420p -video_track_timescale 90000 -movflags frag_keyframe+empty_moov -f mp4 pipe:1 | ffmpeg -hide_banner -loglevel error -i pipe:0 -map 0:v:0 -c:v copy -an -movflags frag_keyframe+empty_moov -f mp4 pipe:1 | ffprobe -v error -select_streams v:0 -show_entries stream=time_base,codec_name,profile,level,pix_fmt,r_frame_rate -of default=noprint_wrappers=1 pipe:0' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 205ms:
codec_name=h264
profile=High
pix_fmt=yuv420p
level=10
r_frame_rate=30/1
time_base=1/90000

exec
/bin/zsh -lc "rg -n \"duration_tolerance|duration_frames\" astrid/core/rendering/artifacts.py | head -n 100; nl -ba astrid/core/rendering/artifacts.py | sed -n '560,650p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
577:    duration_frames: Any,
580:    if type(duration_frames) is not int or duration_frames <= 0:
583:            "video artifact duration_frames must be a positive integer",
584:            declared_duration_frames=duration_frames,
588:    delta = abs(actual_frames - duration_frames)
589:    if delta > expected.duration_tolerance:
593:            declared_duration_frames=duration_frames,
594:            actual_duration_frames=float(actual_frames),
595:            actual_duration_frames_rational=[actual_frames.numerator, actual_frames.denominator],
596:            tolerance_frames=expected.duration_tolerance,
737:    _validate_duration(probe, duration_frames=video.duration_frames, expected=expected)
   560	                "incomplete_probe",
   561	                "ffprobe returned an invalid duration",
   562	                actual=seconds,
   563	            )
   564	        duration = Fraction(str(seconds))
   565	    if duration < 0:
   566	        _invalid(
   567	            "incomplete_probe",
   568	            "ffprobe returned a negative duration",
   569	            actual=float(duration),
   570	        )
   571	    return duration
   572	
   573	
   574	def _validate_duration(
   575	    probe: MediaProbe,
   576	    *,
   577	    duration_frames: Any,
   578	    expected: RenderProfile,
   579	) -> None:
   580	    if type(duration_frames) is not int or duration_frames <= 0:
   581	        _invalid(
   582	            "invalid_duration",
   583	            "video artifact duration_frames must be a positive integer",
   584	            declared_duration_frames=duration_frames,
   585	        )
   586	    fps = Fraction(*expected.fps_rational)
   587	    actual_frames = _duration_fraction(probe) * fps
   588	    delta = abs(actual_frames - duration_frames)
   589	    if delta > expected.duration_tolerance:
   590	        _invalid(
   591	            "duration_mismatch",
   592	            "probed video duration is outside the canonical frame tolerance",
   593	            declared_duration_frames=duration_frames,
   594	            actual_duration_frames=float(actual_frames),
   595	            actual_duration_frames_rational=[actual_frames.numerator, actual_frames.denominator],
   596	            tolerance_frames=expected.duration_tolerance,
   597	        )
   598	
   599	
   600	def _validate_attachment(
   601	    key: Any,
   602	    attachment: Any,
   603	    *,
   604	    root: Path,
   605	) -> None:
   606	    if not isinstance(key, str) or not _OUTPUT_NAME_RE.fullmatch(key):
   607	        _invalid(
   608	            "invalid_attachment",
   609	            "attachment map key must be a portable name",
   610	            attachment_name=key if isinstance(key, str) else None,
   611	        )
   612	    if not isinstance(attachment, Attachment):
   613	        _invalid(
   614	            "invalid_attachment",
   615	            f"attachment {key!r} is not an Attachment",
   616	            attachment_name=key,
   617	            received_type=type(attachment).__name__,
   618	        )
   619	    if attachment.name != key or not _OUTPUT_NAME_RE.fullmatch(attachment.name):
   620	        _invalid(
   621	            "invalid_attachment",
   622	            f"attachment {key!r} has an invalid or mismatched name",
   623	            attachment_name=attachment.name,
   624	            map_key=key,
   625	        )
   626	    if not isinstance(attachment.kind, str) or not _KIND_RE.fullmatch(attachment.kind):
   627	        _invalid(
   628	            "invalid_attachment_kind",
   629	            f"attachment {key!r} has an invalid kind",
   630	            attachment_name=key,
   631	            kind=attachment.kind if isinstance(attachment.kind, str) else None,
   632	        )
   633	    path = _contained_regular_file(
   634	        attachment.path,
   635	        root=root,
   636	        label=f"attachment {key!r} path",
   637	    )
   638	    _verify_hash(path, attachment.sha256, label=f"attachment {key!r}")
   639	
   640	
   641	def _validate_result_shape(result: RenderResult) -> tuple[VideoArtifact, AudioOwnership]:
   642	    video = result.video
   643	    if not isinstance(video, VideoArtifact):
   644	        _invalid(
   645	            "malformed_artifact",
   646	            "render result video is not a VideoArtifact",
   647	            received_type=type(video).__name__,
   648	        )
   649	    ownership = result.audio_ownership
   650	    if not isinstance(ownership, AudioOwnership):

exec
/bin/zsh -lc 'rg -n "duration_frames|window.*duration|segment.*duration" astrid/packs/rendering/finalizers/ffmpeg/run.py | head -n 160' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
96:    duration_frames: int
848:def _duration_frames_from_probe(probe: MediaProbe, profile: RenderProfile) -> int:
927:                duration_frames=_duration_frames_from_probe(media_probe, source_profile),
1095:        artifact_seconds = Fraction(artifact.duration_frames, 1) / Fraction(
1098:        planned_seconds = Fraction(plan_segment.window.duration_frames, 1) / canonical_fps
1104:                    f"segment[{index}] duration does not match its planned frame window"
1109:                    "declared_duration_frames": artifact.duration_frames,
1110:                    "planned_duration_frames": plan_segment.window.duration_frames,
1140:                duration_frames=plan_segment.window.duration_frames,
1174:        duration_delta = abs(actual_frames - segment.duration_frames)
1179:                    f"normalized segment[{segment.index}] duration does not match "
1185:                    "expected_duration_frames": segment.duration_frames,
1186:                    "actual_duration_frames": [
1249:        segment.window.duration_frames for segment in request.plan.segments
1308:                        duration_frames=segment.duration_frames,
1347:            duration_frames=total_frames,

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '1075,1120p'; nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '1160,1190p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1075	        if artifact.audio is None:
  1076	            raise_invalid_artifact_error(
  1077	                backend=BACKEND_ID,
  1078	                message=f"segment[{index}] does not declare audio ownership",
  1079	                recovery_command="rerender the segment with explicit audio ownership",
  1080	                details={"segment_index": index},
  1081	            )
  1082	        segment_result = RenderResult(
  1083	            schema_version=SCHEMA_VERSION,
  1084	            video=artifact,
  1085	            audio_ownership=artifact.audio,
  1086	        )
  1087	        # Validate against the segment's own declared/probed profile.  Its
  1088	        # differences from the plan profile are legitimate normalization work.
  1089	        validate_render_result(
  1090	            segment_result,
  1091	            expected_profile=artifact.profile,
  1092	            workspace_root=workspace,
  1093	        )
  1094	
  1095	        artifact_seconds = Fraction(artifact.duration_frames, 1) / Fraction(
  1096	            *artifact.profile.fps_rational
  1097	        )
  1098	        planned_seconds = Fraction(plan_segment.window.duration_frames, 1) / canonical_fps
  1099	        delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
  1100	        if delta_frames > tolerance:
  1101	            raise_invalid_artifact_error(
  1102	                backend=BACKEND_ID,
  1103	                message=(
  1104	                    f"segment[{index}] duration does not match its planned frame window"
  1105	                ),
  1106	                recovery_command="rerender the exact planned segment window and retry",
  1107	                details={
  1108	                    "segment_index": index,
  1109	                    "declared_duration_frames": artifact.duration_frames,
  1110	                    "planned_duration_frames": plan_segment.window.duration_frames,
  1111	                    "canonical_delta_frames": [
  1112	                        delta_frames.numerator,
  1113	                        delta_frames.denominator,
  1114	                    ],
  1115	                    "tolerance_frames": tolerance,
  1116	                },
  1117	            )
  1118	
  1119	        try:
  1120	            media_probe = ffprobe_metadata_strict(_input_path(artifact.path, workspace))
  1160	                duration_tolerance=target_profile.duration_tolerance,
  1161	            )
  1162	        except (MediaProbeError, OSError, RuntimeError, TypeError, ValueError) as exc:
  1163	            raise_invalid_artifact_error(
  1164	                backend=BACKEND_ID,
  1165	                message=(
  1166	                    f"normalized segment[{segment.index}] could not be validated: {exc}"
  1167	                ),
  1168	                recovery_command="rerun finalization in a fresh invocation workspace",
  1169	                details={"segment_index": segment.index},
  1170	            )
  1171	        actual_frames = _duration_fraction(probe) * Fraction(
  1172	            *target_profile.fps_rational
  1173	        )
  1174	        duration_delta = abs(actual_frames - segment.duration_frames)
  1175	        if duration_delta > target_profile.duration_tolerance:
  1176	            raise_invalid_artifact_error(
  1177	                backend=BACKEND_ID,
  1178	                message=(
  1179	                    f"normalized segment[{segment.index}] duration does not match "
  1180	                    "its planned frame window"
  1181	                ),
  1182	                recovery_command="rerun finalization in a fresh invocation workspace",
  1183	                details={
  1184	                    "segment_index": segment.index,
  1185	                    "expected_duration_frames": segment.duration_frames,
  1186	                    "actual_duration_frames": [
  1187	                        actual_frames.numerator,
  1188	                        actual_frames.denominator,
  1189	                    ],
  1190	                    "delta_frames": [

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/backends/remotion/renderer.yaml | sed -n '25,45p'; nl -ba astrid/packs/rendering/backends/ffmpeg/support.py | sed -n '475,540p'; nl -ba astrid/packs/rendering/backends/ffmpeg/command.py | sed -n '250,270p'; nl -ba astrid/core/rendering/profile.py | sed -n '175,192p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
