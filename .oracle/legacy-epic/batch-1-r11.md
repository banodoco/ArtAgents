Reading additional input from stdin...
2026-08-12T03:03:45.380438Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:03:45.380472Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:03:45.380477Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3ed-072e-73f3-859f-549ea04ccb84
--------
user
# Megado Checkpoint — Batch 1 eleventh re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1..-r10 (3 each; -r4 had 4). Eleventh rework
committed as `6afd558` (prior head 6acd4be). Incremental diff at
/tmp/batch1-r11.diff.

## How each of your 2 re-review10 issues was addressed (host-implemented)

1. **Multi-segment lineage cannot round-trip** →
   - Sequence form now accepts BOTH VideoArtifacts and already-emitted
     lineage records (dicts); records are re-validated via
     `_artifact_lineage_from_mapping` and re-keyed by their validated path.
   - Round-trip test: emitted `artifact_profiles` re-passed reproduces the
     identical output.
2. **workspacePath cross-language whitespace** →
   - DTO and schema now share an EXPLICIT ECMAScript `\s` whitespace class
     (space, tab, LF, CR, FF, VT, NBSP, and Unicode spaces through \u3000,
     \ufeff) instead of Python `str.strip()` semantics — so Python and
     non-Python validators agree on `\u0085` (accepted by both) and
     `\uFEFF` (rejected by both) components.
   - Cross-checked 19 DTO-vs-schema cases including \u0085/\uFEFF/\u00a0: 0
     mismatches.

## Evidence

- Incremental diff: /tmp/batch1-r11.diff (7 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 11 review rounds. If
sound and STABLE, say exactly `PASS` so Batch 2 may begin.
codex
I’m using the repository’s context-mining and subagent-launcher guidance for this checkpoint: I’ll keep the main review focused, delegate independent scrutiny of the two fixes, then personally verify the incremental diff and relevant tests. I’ll keep the final response strictly to `PASS` if no concrete issue survives review.
codex
I’m also applying Astrid’s core repository skill, since this is a review inside the Astrid project; it governs how I inspect project state without mutating it.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md astrid/packs/_core/skill/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,360p' astrid/packs/_core/skill/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
     772 astrid/packs/_core/skill/SKILL.md
    1088 total
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


exec
/bin/zsh -lc "sed -n '361,772p' astrid/packs/_core/skill/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

2026-08-12T03:04:18.926655Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:18.926680Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:18.926684Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:23.502841Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:23.503646Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:23.503710Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:28.362878Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:28.362948Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:04:28.362954Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
codex
The independent reviews are now running on lineage, Unicode/schema parity, and the full seven-file change. I’m verifying the exact commit delta and tracing both validators through their real call sites, not just accepting the new unit cases.
exec
/bin/zsh -lc 'git status --short && git rev-parse HEAD && git show --no-ext-diff --stat --oneline --decorate 6afd558 && git diff --no-ext-diff --check 6acd4be 6afd558 && git diff --no-ext-diff --name-status 6acd4be 6afd558 && shasum -a 256 /tmp/batch1-r11.diff && git diff --no-ext-diff 6acd4be 6afd558' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r11.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6afd558b80898d9892346f9505f229beb476004a
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6afd558 (HEAD -> oracle-run) batch1-rework11: oracle re-review10 issues 1-2 (lineage round-trip via dict-record acceptance, explicit ECMAScript whitespace class shared DTO+schema)
 .oracle/checkins/batch-1-r10.md                | 5755 ++++++++++++++++++++++++
 astrid/core/rendering/contracts.py             |    5 +-
 astrid/core/rendering/provenance.py            |   31 +-
 astrid/core/rendering/schemas/v1/finalize.json |    2 +-
 astrid/core/rendering/schemas/v1/result.json   |    2 +-
 docs/contracts/render-backend-v1.md            |   28 +-
 tests/core/rendering/test_contracts.py         |   26 +
 7 files changed, 5823 insertions(+), 26 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r10.md:243: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r10.md:244: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r10.md:246: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r10.md:585: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r10.md:587: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r10.md:589: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r10.md:591: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r10.md:593: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r10.md:595: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r10.md:597: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r10.md:599: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r10.md:601: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r10.md:603: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:605: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:607: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:609: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:611: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:613: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:615: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:617: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:619: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:621: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:623: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:625: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:627: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:629: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:631: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:633: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:635: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:637: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:639: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:641: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:643: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:645: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:647: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:649: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:651: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:653: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:655: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:657: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:659: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:661: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:663: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:665: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:667: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:669: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:671: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:673: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:675: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:677: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:679: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:681: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:683: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:685: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:687: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:689: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:691: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:693: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:695: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:697: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:699: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:701: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:703: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:705: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:707: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:709: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:711: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:713: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:715: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:717: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:719: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:721: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:723: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:725: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:727: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:729: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:731: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:733: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:735: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:737: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:739: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:741: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:743: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:745: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:747: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:749: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:751: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:753: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:755: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:757: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:759: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:761: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:763: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:765: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:767: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:769: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:771: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:773: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:775: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:777: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:779: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:781: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:783: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:785: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:787: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:789: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:791: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:793: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:795: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:797: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:799: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:801: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:803: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r10.md:805: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r10.md:807: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r10.md:809: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:811: trailing whitespace.
+++   730	
.oracle/checkins/batch-1-r10.md:813: trailing whitespace.
+++   731	
.oracle/checkins/batch-1-r10.md:815: trailing whitespace.
+++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-1-r10.md:817: trailing whitespace.
+++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-1-r10.md:819: trailing whitespace.
+++   453	
.oracle/checkins/batch-1-r10.md:821: trailing whitespace.
+++   461	
.oracle/checkins/batch-1-r10.md:823: trailing whitespace.
+++   463	
.oracle/checkins/batch-1-r10.md:825: trailing whitespace.
+++   465	
.oracle/checkins/batch-1-r10.md:827: trailing whitespace.
+++   470	
.oracle/checkins/batch-1-r10.md:829: trailing whitespace.
+++   492	
.oracle/checkins/batch-1-r10.md:831: trailing whitespace.
+++   520	
.oracle/checkins/batch-1-r10.md:833: trailing whitespace.
+++   539	
.oracle/checkins/batch-1-r10.md:835: trailing whitespace.
+++   540	
.oracle/checkins/batch-1-r10.md:837: trailing whitespace.
+++   550	
.oracle/checkins/batch-1-r10.md:839: trailing whitespace.
+++   551	
.oracle/checkins/batch-1-r10.md:841: trailing whitespace.
+++   609	
.oracle/checkins/batch-1-r10.md:843: trailing whitespace.
+++   613	
.oracle/checkins/batch-1-r10.md:845: trailing whitespace.
+++   614	
.oracle/checkins/batch-1-r10.md:847: trailing whitespace.
+++   627	
.oracle/checkins/batch-1-r10.md:849: trailing whitespace.
+++   628	
.oracle/checkins/batch-1-r10.md:851: trailing whitespace.
+++   631	
.oracle/checkins/batch-1-r10.md:853: trailing whitespace.
+++   640	
.oracle/checkins/batch-1-r10.md:855: trailing whitespace.
+++   641	
.oracle/checkins/batch-1-r10.md:857: trailing whitespace.
+++   647	
.oracle/checkins/batch-1-r10.md:859: trailing whitespace.
+++   648	
.oracle/checkins/batch-1-r10.md:861: trailing whitespace.
+++   679	
.oracle/checkins/batch-1-r10.md:863: trailing whitespace.
+++   689	
.oracle/checkins/batch-1-r10.md:865: trailing whitespace.
+++   721	
.oracle/checkins/batch-1-r10.md:867: trailing whitespace.
+++   722	
.oracle/checkins/batch-1-r10.md:869: trailing whitespace.
+++   740	
.oracle/checkins/batch-1-r10.md:871: trailing whitespace.
+++   741	
.oracle/checkins/batch-1-r10.md:873: trailing whitespace.
+++   777	
.oracle/checkins/batch-1-r10.md:875: trailing whitespace.
+++   778	
.oracle/checkins/batch-1-r10.md:877: trailing whitespace.
+++   792	
.oracle/checkins/batch-1-r10.md:879: trailing whitespace.
+++   793	
.oracle/checkins/batch-1-r10.md:881: trailing whitespace.
+++   809	
.oracle/checkins/batch-1-r10.md:883: trailing whitespace.
+++   810	
.oracle/checkins/batch-1-r10.md:885: trailing whitespace.
+++   904	
.oracle/checkins/batch-1-r10.md:887: trailing whitespace.
+++   905	
.oracle/checkins/batch-1-r10.md:889: trailing whitespace.
+++   965	
.oracle/checkins/batch-1-r10.md:891: trailing whitespace.
+++   966	
.oracle/checkins/batch-1-r10.md:893: trailing whitespace.
+++   975	
.oracle/checkins/batch-1-r10.md:895: trailing whitespace.
+++   976	
.oracle/checkins/batch-1-r10.md:897: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r10.md:899: trailing whitespace.
+++     4	
.oracle/checkins/batch-1-r10.md:901: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r10.md:903: trailing whitespace.
+++    11	
.oracle/checkins/batch-1-r10.md:905: trailing whitespace.
+++    28	
.oracle/checkins/batch-1-r10.md:907: trailing whitespace.
+++    29	
.oracle/checkins/batch-1-r10.md:909: trailing whitespace.
+++    32	
.oracle/checkins/batch-1-r10.md:911: trailing whitespace.
+++    33	
.oracle/checkins/batch-1-r10.md:913: trailing whitespace.
+++    38	
.oracle/checkins/batch-1-r10.md:915: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r10.md:917: trailing whitespace.
+++    41	
.oracle/checkins/batch-1-r10.md:919: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r10.md:921: trailing whitespace.
+++    54	
.oracle/checkins/batch-1-r10.md:923: trailing whitespace.
+++    81	
.oracle/checkins/batch-1-r10.md:925: trailing whitespace.
+++    82	
.oracle/checkins/batch-1-r10.md:927: trailing whitespace.
+++    85	
.oracle/checkins/batch-1-r10.md:929: trailing whitespace.
+++    92	
.oracle/checkins/batch-1-r10.md:931: trailing whitespace.
+++    93	
.oracle/checkins/batch-1-r10.md:933: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r10.md:935: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r10.md:937: trailing whitespace.
+++   168	
.oracle/checkins/batch-1-r10.md:939: trailing whitespace.
+++   169	
.oracle/checkins/batch-1-r10.md:941: trailing whitespace.
+++   236	
.oracle/checkins/batch-1-r10.md:943: trailing whitespace.
+++   237	
.oracle/checkins/batch-1-r10.md:945: trailing whitespace.
+++   248	
.oracle/checkins/batch-1-r10.md:947: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r10.md:949: trailing whitespace.
+++   271	
.oracle/checkins/batch-1-r10.md:951: trailing whitespace.
+++   272	
.oracle/checkins/batch-1-r10.md:953: trailing whitespace.
+++   288	
.oracle/checkins/batch-1-r10.md:955: trailing whitespace.
+++   295	
.oracle/checkins/batch-1-r10.md:957: trailing whitespace.
+++   316	
.oracle/checkins/batch-1-r10.md:959: trailing whitespace.
+++   343	
.oracle/checkins/batch-1-r10.md:961: trailing whitespace.
+++   344	
.oracle/checkins/batch-1-r10.md:963: trailing whitespace.
+++   347	
.oracle/checkins/batch-1-r10.md:965: trailing whitespace.
+++   349	
.oracle/checkins/batch-1-r10.md:967: trailing whitespace.
+++   350	
.oracle/checkins/batch-1-r10.md:969: trailing whitespace.
+++   353	
.oracle/checkins/batch-1-r10.md:971: trailing whitespace.
+++   357	
.oracle/checkins/batch-1-r10.md:973: trailing whitespace.
+++   358	
.oracle/checkins/batch-1-r10.md:975: trailing whitespace.
+++   361	
.oracle/checkins/batch-1-r10.md:977: trailing whitespace.
+++   366	
.oracle/checkins/batch-1-r10.md:979: trailing whitespace.
+++   367	
.oracle/checkins/batch-1-r10.md:981: trailing whitespace.
+++   370	
.oracle/checkins/batch-1-r10.md:983: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r10.md:985: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r10.md:987: trailing whitespace.
+++    10	
.oracle/checkins/batch-1-r10.md:989: trailing whitespace.
+++    18	
.oracle/checkins/batch-1-r10.md:991: trailing whitespace.
+++    21	
.oracle/checkins/batch-1-r10.md:993: trailing whitespace.
+++    22	
.oracle/checkins/batch-1-r10.md:995: trailing whitespace.
+++    24	
.oracle/checkins/batch-1-r10.md:997: trailing whitespace.
+++    35	
.oracle/checkins/batch-1-r10.md:999: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r10.md:1001: trailing whitespace.
+++    52	
.oracle/checkins/batch-1-r10.md:1003: trailing whitespace.
+++    73	
.oracle/checkins/batch-1-r10.md:1005: trailing whitespace.
+++    93	
.oracle/checkins/batch-1-r10.md:1007: trailing whitespace.
+++   110	
.oracle/checkins/batch-1-r10.md:1009: trailing whitespace.
+++   123	
.oracle/checkins/batch-1-r10.md:1011: trailing whitespace.
+++   130	
.oracle/checkins/batch-1-r10.md:1013: trailing whitespace.
+++   131	
.oracle/checkins/batch-1-r10.md:1015: trailing whitespace.
+++   134	
.oracle/checkins/batch-1-r10.md:1017: trailing whitespace.
+++   158	
.oracle/checkins/batch-1-r10.md:1019: trailing whitespace.
+++   159	
.oracle/checkins/batch-1-r10.md:1021: trailing whitespace.
+++   165	
.oracle/checkins/batch-1-r10.md:1023: trailing whitespace.
+++   166	
.oracle/checkins/batch-1-r10.md:1025: trailing whitespace.
+++   171	
.oracle/checkins/batch-1-r10.md:1027: trailing whitespace.
+++   172	
.oracle/checkins/batch-1-r10.md:1029: trailing whitespace.
+++   186	
.oracle/checkins/batch-1-r10.md:1031: trailing whitespace.
+++   187	
.oracle/checkins/batch-1-r10.md:1033: trailing whitespace.
+++   194	
.oracle/checkins/batch-1-r10.md:1035: trailing whitespace.
+++   195	
.oracle/checkins/batch-1-r10.md:1037: trailing whitespace.
+++   205	
.oracle/checkins/batch-1-r10.md:1039: trailing whitespace.
+++   206	
.oracle/checkins/batch-1-r10.md:1041: trailing whitespace.
+++   209	
.oracle/checkins/batch-1-r10.md:1043: trailing whitespace.
+++   215	
.oracle/checkins/batch-1-r10.md:1045: trailing whitespace.
+++   216	
.oracle/checkins/batch-1-r10.md:1047: trailing whitespace.
+++   225	
.oracle/checkins/batch-1-r10.md:1049: trailing whitespace.
+++   226	
.oracle/checkins/batch-1-r10.md:1051: trailing whitespace.
+++   231	
.oracle/checkins/batch-1-r10.md:1053: trailing whitespace.
+++   232	
.oracle/checkins/batch-1-r10.md:1055: trailing whitespace.
+++   241	
.oracle/checkins/batch-1-r10.md:1057: trailing whitespace.
+++   242	
.oracle/checkins/batch-1-r10.md:1059: trailing whitespace.
+++   248	
.oracle/checkins/batch-1-r10.md:1061: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r10.md:1063: trailing whitespace.
+++   507	
.oracle/checkins/batch-1-r10.md:1065: trailing whitespace.
+++   511	
.oracle/checkins/batch-1-r10.md:1067: trailing whitespace.
+++   530	
.oracle/checkins/batch-1-r10.md:1069: trailing whitespace.
+++   563	
.oracle/checkins/batch-1-r10.md:1071: trailing whitespace.
+++   564	
.oracle/checkins/batch-1-r10.md:1073: trailing whitespace.
+++   571	
.oracle/checkins/batch-1-r10.md:1075: trailing whitespace.
+++   576	
.oracle/checkins/batch-1-r10.md:1077: trailing whitespace.
+++   582	
.oracle/checkins/batch-1-r10.md:1079: trailing whitespace.
+++   583	
.oracle/checkins/batch-1-r10.md:1081: trailing whitespace.
+++   587	
.oracle/checkins/batch-1-r10.md:1083: trailing whitespace.
+++   592	
.oracle/checkins/batch-1-r10.md:1085: trailing whitespace.
+++   604	
.oracle/checkins/batch-1-r10.md:1087: trailing whitespace.
+++   609	
.oracle/checkins/batch-1-r10.md:1089: trailing whitespace.
+++   621	
.oracle/checkins/batch-1-r10.md:1091: trailing whitespace.
+++   633	
.oracle/checkins/batch-1-r10.md:1093: trailing whitespace.
+++   634	
.oracle/checkins/batch-1-r10.md:1095: trailing whitespace.
+++   655	
.oracle/checkins/batch-1-r10.md:1097: trailing whitespace.
+++   656	
.oracle/checkins/batch-1-r10.md:1099: trailing whitespace.
+++   660	
.oracle/checkins/batch-1-r10.md:1101: trailing whitespace.
+++   667	
.oracle/checkins/batch-1-r10.md:1103: trailing whitespace.
+++   690	
.oracle/checkins/batch-1-r10.md:1105: trailing whitespace.
+++   702	
.oracle/checkins/batch-1-r10.md:1107: trailing whitespace.
+++   717	
.oracle/checkins/batch-1-r10.md:1109: trailing whitespace.
+++  1662	
.oracle/checkins/batch-1-r10.md:1111: trailing whitespace.
+++  1686	
.oracle/checkins/batch-1-r10.md:1113: trailing whitespace.
+++  1693	
.oracle/checkins/batch-1-r10.md:1115: trailing whitespace.
+++  1694	
.oracle/checkins/batch-1-r10.md:1117: trailing whitespace.
+++  1698	
.oracle/checkins/batch-1-r10.md:1119: trailing whitespace.
+++  1705	
.oracle/checkins/batch-1-r10.md:1121: trailing whitespace.
+++  1753	
.oracle/checkins/batch-1-r10.md:1123: trailing whitespace.
+++  1757	
.oracle/checkins/batch-1-r10.md:1125: trailing whitespace.
+++  1763	
.oracle/checkins/batch-1-r10.md:1127: trailing whitespace.
+++  1769	
.oracle/checkins/batch-1-r10.md:1129: trailing whitespace.
+++  1773	
.oracle/checkins/batch-1-r10.md:1131: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r10.md:1133: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r10.md:1135: trailing whitespace.
+++    11	
.oracle/checkins/batch-1-r10.md:1137: trailing whitespace.
+++    20	
.oracle/checkins/batch-1-r10.md:1139: trailing whitespace.
+++    21	
.oracle/checkins/batch-1-r10.md:1141: trailing whitespace.
+++    48	
.oracle/checkins/batch-1-r10.md:1143: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r10.md:1145: trailing whitespace.
+++    52	
.oracle/checkins/batch-1-r10.md:1147: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r10.md:1149: trailing whitespace.
+++    56	
.oracle/checkins/batch-1-r10.md:1151: trailing whitespace.
+++    57	
.oracle/checkins/batch-1-r10.md:1153: trailing whitespace.
+++    60	
.oracle/checkins/batch-1-r10.md:1155: trailing whitespace.
+++    61	
.oracle/checkins/batch-1-r10.md:1157: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r10.md:1159: trailing whitespace.
+++    73	
.oracle/checkins/batch-1-r10.md:1161: trailing whitespace.
+++    81	
.oracle/checkins/batch-1-r10.md:1163: trailing whitespace.
+++    88	
.oracle/checkins/batch-1-r10.md:1165: trailing whitespace.
+++    89	
.oracle/checkins/batch-1-r10.md:1167: trailing whitespace.
+++    96	
.oracle/checkins/batch-1-r10.md:1169: trailing whitespace.
+++    97	
.oracle/checkins/batch-1-r10.md:1171: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r10.md:1173: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r10.md:1175: trailing whitespace.
+++   113	
.oracle/checkins/batch-1-r10.md:1177: trailing whitespace.
+++   114	
.oracle/checkins/batch-1-r10.md:1179: trailing whitespace.
+++   312	
.oracle/checkins/batch-1-r10.md:1181: trailing whitespace.
+++   313	
.oracle/checkins/batch-1-r10.md:1183: trailing whitespace.
+++   324	
.oracle/checkins/batch-1-r10.md:1185: trailing whitespace.
+++   325	
.oracle/checkins/batch-1-r10.md:1187: trailing whitespace.
+++   338	
.oracle/checkins/batch-1-r10.md:1189: trailing whitespace.
+++   339	
.oracle/checkins/batch-1-r10.md:1191: trailing whitespace.
+++   356	
.oracle/checkins/batch-1-r10.md:1193: trailing whitespace.
+++   357	
.oracle/checkins/batch-1-r10.md:1195: trailing whitespace.
+++   375	
.oracle/checkins/batch-1-r10.md:1197: trailing whitespace.
+++   376	
.oracle/checkins/batch-1-r10.md:1199: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1201: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1203: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1205: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1207: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1209: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1211: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1213: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1215: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r10.md:1217: trailing whitespace.
+++   809	
.oracle/checkins/batch-1-r10.md:1219: trailing whitespace.
+++   810	
.oracle/checkins/batch-1-r10.md:1221: trailing whitespace.
+++   904	
.oracle/checkins/batch-1-r10.md:1223: trailing whitespace.
+++   905	
.oracle/checkins/batch-1-r10.md:1225: trailing whitespace.
+++   965	
.oracle/checkins/batch-1-r10.md:1227: trailing whitespace.
+++   966	
.oracle/checkins/batch-1-r10.md:1229: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r10.md:1231: trailing whitespace.
+++     4	
.oracle/checkins/batch-1-r10.md:1233: trailing whitespace.
+++     6	
.oracle/checkins/batch-1-r10.md:1235: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r10.md:1237: trailing whitespace.
+++    17	
.oracle/checkins/batch-1-r10.md:1239: trailing whitespace.
+++    19	
.oracle/checkins/batch-1-r10.md:1241: trailing whitespace.
+++    25	
.oracle/checkins/batch-1-r10.md:1243: trailing whitespace.
+++    27	
.oracle/checkins/batch-1-r10.md:1245: trailing whitespace.
+++    29	
.oracle/checkins/batch-1-r10.md:1247: trailing whitespace.
+++    31	
.oracle/checkins/batch-1-r10.md:1249: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r10.md:1251: trailing whitespace.
+++    42	
.oracle/checkins/batch-1-r10.md:1253: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r10.md:1255: trailing whitespace.
+++    51	
.oracle/checkins/batch-1-r10.md:1257: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r10.md:1259: trailing whitespace.
+++    55	
.oracle/checkins/batch-1-r10.md:1261: trailing whitespace.
+++    63	
.oracle/checkins/batch-1-r10.md:1263: trailing whitespace.
+++    65	
.oracle/checkins/batch-1-r10.md:1265: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r10.md:1267: trailing whitespace.
+++    74	
.oracle/checkins/batch-1-r10.md:1269: trailing whitespace.
+++    76	
.oracle/checkins/batch-1-r10.md:1271: trailing whitespace.
+++    78	
.oracle/checkins/batch-1-r10.md:1273: trailing whitespace.
+++   131	
.oracle/checkins/batch-1-r10.md:1275: trailing whitespace.
+++   132	
.oracle/checkins/batch-1-r10.md:1277: trailing whitespace.
+++   162	
.oracle/checkins/batch-1-r10.md:1279: trailing whitespace.
+++   163	
.oracle/checkins/batch-1-r10.md:1281: trailing whitespace.
+++   178	
.oracle/checkins/batch-1-r10.md:1283: trailing whitespace.
+++   179	
.oracle/checkins/batch-1-r10.md:1285: trailing whitespace.
+++   206	
.oracle/checkins/batch-1-r10.md:1287: trailing whitespace.
+++   207	
.oracle/checkins/batch-1-r10.md:1289: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r10.md:1291: trailing whitespace.
+++   250	
.oracle/checkins/batch-1-r10.md:1293: trailing whitespace.
+++   288	
.oracle/checkins/batch-1-r10.md:1295: trailing whitespace.
+++   289	
.oracle/checkins/batch-1-r10.md:1297: trailing whitespace.
+++   302	
.oracle/checkins/batch-1-r10.md:1299: trailing whitespace.
+++   303	
.oracle/checkins/batch-1-r10.md:1301: trailing whitespace.
+++   312	
.oracle/checkins/batch-1-r10.md:1303: trailing whitespace.
+++   313	
.oracle/checkins/batch-1-r10.md:1305: trailing whitespace.
+++   330	
.oracle/checkins/batch-1-r10.md:1307: trailing whitespace.
+++   331	
.oracle/checkins/batch-1-r10.md:1309: trailing whitespace.
+++   343	
.oracle/checkins/batch-1-r10.md:1311: trailing whitespace.
+++   344	
.oracle/checkins/batch-1-r10.md:1313: trailing whitespace.
+++   288	
.oracle/checkins/batch-1-r10.md:1315: trailing whitespace.
+++    98	
.oracle/checkins/batch-1-r10.md:1317: trailing whitespace.
+++   101	
.oracle/checkins/batch-1-r10.md:1319: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r10.md:1321: trailing whitespace.
+++   107	
.oracle/checkins/batch-1-r10.md:1323: trailing whitespace.
+++   110	
.oracle/checkins/batch-1-r10.md:1325: trailing whitespace.
+++   113	
.oracle/checkins/batch-1-r10.md:1327: trailing whitespace.
+++  1349	
.oracle/checkins/batch-1-r10.md:1329: trailing whitespace.
+++  1350	
.oracle/checkins/batch-1-r10.md:1331: trailing whitespace.
+++  1354	
.oracle/checkins/batch-1-r10.md:1333: trailing whitespace.
+++  1365	
.oracle/checkins/batch-1-r10.md:1335: trailing whitespace.
+++  1444	
.oracle/checkins/batch-1-r10.md:1337: trailing whitespace.
+++  1460	
.oracle/checkins/batch-1-r10.md:1339: trailing whitespace.
++  1444	
.oracle/checkins/batch-1-r10.md:1341: trailing whitespace.
++  1460	
.oracle/checkins/batch-1-r10.md:1343: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1345: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1347: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1349: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1351: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1353: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1355: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1357: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1359: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1361: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1363: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1365: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1367: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1369: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1371: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1373: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1375: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1377: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1379: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1381: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1383: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1385: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1387: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1389: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1391: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1393: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1395: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1397: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1399: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1401: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1403: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1405: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1407: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1409: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1411: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1413: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1415: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1417: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1419: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1421: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1423: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1425: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1427: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1429: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1431: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1433: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1435: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1437: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1439: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1441: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1443: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1445: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1447: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1449: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1451: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1453: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1455: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1457: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1459: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1461: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1463: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1465: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1467: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1469: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1471: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1473: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1475: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1477: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1479: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1481: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1483: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1485: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1487: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1489: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1491: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1493: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1495: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1497: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1499: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1501: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1503: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1505: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1507: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1509: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1511: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1513: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1515: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1517: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1519: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1521: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1523: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1525: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1527: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1529: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1531: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1533: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1535: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1537: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1539: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1541: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1543: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1545: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1547: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1549: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1551: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1553: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1555: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1557: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1559: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1561: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1563: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1565: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1567: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1569: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1571: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1573: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1575: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r10.md:1577: trailing whitespace.
++     4	
.oracle/checkins/batch-1-r10.md:1579: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r10.md:1581: trailing whitespace.
++    11	
.oracle/checkins/batch-1-r10.md:1583: trailing whitespace.
++    28	
.oracle/checkins/batch-1-r10.md:1585: trailing whitespace.
++    29	
.oracle/checkins/batch-1-r10.md:1587: trailing whitespace.
++    32	
.oracle/checkins/batch-1-r10.md:1589: trailing whitespace.
++    33	
.oracle/checkins/batch-1-r10.md:1591: trailing whitespace.
++    38	
.oracle/checkins/batch-1-r10.md:1593: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r10.md:1595: trailing whitespace.
++    41	
.oracle/checkins/batch-1-r10.md:1597: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r10.md:1599: trailing whitespace.
++    54	
.oracle/checkins/batch-1-r10.md:1601: trailing whitespace.
++    81	
.oracle/checkins/batch-1-r10.md:1603: trailing whitespace.
++    82	
.oracle/checkins/batch-1-r10.md:1605: trailing whitespace.
++    85	
.oracle/checkins/batch-1-r10.md:1607: trailing whitespace.
++    92	
.oracle/checkins/batch-1-r10.md:1609: trailing whitespace.
++    93	
.oracle/checkins/batch-1-r10.md:1611: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r10.md:1613: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r10.md:1615: trailing whitespace.
++   173	
.oracle/checkins/batch-1-r10.md:1617: trailing whitespace.
++   174	
.oracle/checkins/batch-1-r10.md:1619: trailing whitespace.
++   248	
.oracle/checkins/batch-1-r10.md:1621: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r10.md:1623: trailing whitespace.
++   260	
.oracle/checkins/batch-1-r10.md:1625: trailing whitespace.
++   261	
.oracle/checkins/batch-1-r10.md:1627: trailing whitespace.
++   283	
.oracle/checkins/batch-1-r10.md:1629: trailing whitespace.
++   284	
.oracle/checkins/batch-1-r10.md:1631: trailing whitespace.
++   300	
.oracle/checkins/batch-1-r10.md:1633: trailing whitespace.
++   307	
.oracle/checkins/batch-1-r10.md:1635: trailing whitespace.
++   328	
.oracle/checkins/batch-1-r10.md:1637: trailing whitespace.
++   355	
.oracle/checkins/batch-1-r10.md:1639: trailing whitespace.
++   356	
.oracle/checkins/batch-1-r10.md:1641: trailing whitespace.
++   359	
.oracle/checkins/batch-1-r10.md:1643: trailing whitespace.
++   361	
.oracle/checkins/batch-1-r10.md:1645: trailing whitespace.
++   362	
.oracle/checkins/batch-1-r10.md:1647: trailing whitespace.
++   365	
.oracle/checkins/batch-1-r10.md:1649: trailing whitespace.
++   369	
.oracle/checkins/batch-1-r10.md:1651: trailing whitespace.
++   370	
.oracle/checkins/batch-1-r10.md:1653: trailing whitespace.
++   373	
.oracle/checkins/batch-1-r10.md:1655: trailing whitespace.
++   378	
.oracle/checkins/batch-1-r10.md:1657: trailing whitespace.
++   379	
.oracle/checkins/batch-1-r10.md:1659: trailing whitespace.
++   382	
.oracle/checkins/batch-1-r10.md:1661: trailing whitespace.
++   384	
.oracle/checkins/batch-1-r10.md:1663: trailing whitespace.
++   385	
.oracle/checkins/batch-1-r10.md:1665: trailing whitespace.
++   651	
.oracle/checkins/batch-1-r10.md:1667: trailing whitespace.
++   652	
.oracle/checkins/batch-1-r10.md:1669: trailing whitespace.
++   683	
.oracle/checkins/batch-1-r10.md:1671: trailing whitespace.
++   693	
.oracle/checkins/batch-1-r10.md:1673: trailing whitespace.
++   729	
.oracle/checkins/batch-1-r10.md:1675: trailing whitespace.
++   730	
.oracle/checkins/batch-1-r10.md:1677: trailing whitespace.
++   748	
.oracle/checkins/batch-1-r10.md:1679: trailing whitespace.
++   749	
.oracle/checkins/batch-1-r10.md:1681: trailing whitespace.
++   785	
.oracle/checkins/batch-1-r10.md:1683: trailing whitespace.
++   786	
.oracle/checkins/batch-1-r10.md:1685: trailing whitespace.
++   800	
.oracle/checkins/batch-1-r10.md:1687: trailing whitespace.
++   801	
.oracle/checkins/batch-1-r10.md:1689: trailing whitespace.
++   817	
.oracle/checkins/batch-1-r10.md:1691: trailing whitespace.
++   818	
.oracle/checkins/batch-1-r10.md:1693: trailing whitespace.
++   914	
.oracle/checkins/batch-1-r10.md:1695: trailing whitespace.
++   915	
.oracle/checkins/batch-1-r10.md:1697: trailing whitespace.
++  1001	
.oracle/checkins/batch-1-r10.md:1699: trailing whitespace.
++  1002	
.oracle/checkins/batch-1-r10.md:1701: trailing whitespace.
++  1011	
.oracle/checkins/batch-1-r10.md:1703: trailing whitespace.
++  1012	
.oracle/checkins/batch-1-r10.md:1705: trailing whitespace.
++   285	
.oracle/checkins/batch-1-r10.md:1707: trailing whitespace.
++   294	
.oracle/checkins/batch-1-r10.md:1709: trailing whitespace.
++   295	
.oracle/checkins/batch-1-r10.md:1711: trailing whitespace.
++   302	
.oracle/checkins/batch-1-r10.md:1713: trailing whitespace.
++   303	
.oracle/checkins/batch-1-r10.md:1715: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r10.md:1717: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r10.md:1719: trailing whitespace.
++   330	
.oracle/checkins/batch-1-r10.md:1721: trailing whitespace.
++   331	
.oracle/checkins/batch-1-r10.md:1723: trailing whitespace.
++   826	
.oracle/checkins/batch-1-r10.md:1725: trailing whitespace.
++   868	
.oracle/checkins/batch-1-r10.md:1727: trailing whitespace.
++   875	
.oracle/checkins/batch-1-r10.md:1729: trailing whitespace.
++   878	
.oracle/checkins/batch-1-r10.md:1731: trailing whitespace.
++   892	
.oracle/checkins/batch-1-r10.md:1733: trailing whitespace.
++   893	
.oracle/checkins/batch-1-r10.md:1735: trailing whitespace.
++   897	
.oracle/checkins/batch-1-r10.md:1737: trailing whitespace.
++   905	
.oracle/checkins/batch-1-r10.md:1739: trailing whitespace.
++   936	
.oracle/checkins/batch-1-r10.md:1741: trailing whitespace.
++   949	
.oracle/checkins/batch-1-r10.md:1743: trailing whitespace.
++   980	
.oracle/checkins/batch-1-r10.md:1745: trailing whitespace.
++   987	
.oracle/checkins/batch-1-r10.md:1747: trailing whitespace.
++   988	
.oracle/checkins/batch-1-r10.md:1749: trailing whitespace.
++   992	
.oracle/checkins/batch-1-r10.md:1751: trailing whitespace.
++  1000	
.oracle/checkins/batch-1-r10.md:1753: trailing whitespace.
++   440	
.oracle/checkins/batch-1-r10.md:1755: trailing whitespace.
++   441	
.oracle/checkins/batch-1-r10.md:1757: trailing whitespace.
++   445	
.oracle/checkins/batch-1-r10.md:1759: trailing whitespace.
++   459	
.oracle/checkins/batch-1-r10.md:1761: trailing whitespace.
++   507	
.oracle/checkins/batch-1-r10.md:1763: trailing whitespace.
++   511	
.oracle/checkins/batch-1-r10.md:1765: trailing whitespace.
++   530	
.oracle/checkins/batch-1-r10.md:1767: trailing whitespace.
++   563	
.oracle/checkins/batch-1-r10.md:1769: trailing whitespace.
++   564	
.oracle/checkins/batch-1-r10.md:1771: trailing whitespace.
++   571	
.oracle/checkins/batch-1-r10.md:1773: trailing whitespace.
++   576	
.oracle/checkins/batch-1-r10.md:1775: trailing whitespace.
++   582	
.oracle/checkins/batch-1-r10.md:1777: trailing whitespace.
++   583	
.oracle/checkins/batch-1-r10.md:1779: trailing whitespace.
++   587	
.oracle/checkins/batch-1-r10.md:1781: trailing whitespace.
++   592	
.oracle/checkins/batch-1-r10.md:1783: trailing whitespace.
++   604	
.oracle/checkins/batch-1-r10.md:1785: trailing whitespace.
++   609	
.oracle/checkins/batch-1-r10.md:1787: trailing whitespace.
++   621	
.oracle/checkins/batch-1-r10.md:1789: trailing whitespace.
++   633	
.oracle/checkins/batch-1-r10.md:1791: trailing whitespace.
++   634	
.oracle/checkins/batch-1-r10.md:1793: trailing whitespace.
++   655	
.oracle/checkins/batch-1-r10.md:1795: trailing whitespace.
++   656	
.oracle/checkins/batch-1-r10.md:1797: trailing whitespace.
++   660	
.oracle/checkins/batch-1-r10.md:1799: trailing whitespace.
++   667	
.oracle/checkins/batch-1-r10.md:1801: trailing whitespace.
++   690	
.oracle/checkins/batch-1-r10.md:1803: trailing whitespace.
++   702	
.oracle/checkins/batch-1-r10.md:1805: trailing whitespace.
++   717	
.oracle/checkins/batch-1-r10.md:1807: trailing whitespace.
++   225	
.oracle/checkins/batch-1-r10.md:1809: trailing whitespace.
++   230	
.oracle/checkins/batch-1-r10.md:1811: trailing whitespace.
++   238	
.oracle/checkins/batch-1-r10.md:1813: trailing whitespace.
++   240	
.oracle/checkins/batch-1-r10.md:1815: trailing whitespace.
++   243	
.oracle/checkins/batch-1-r10.md:1817: trailing whitespace.
++   251	
.oracle/checkins/batch-1-r10.md:1819: trailing whitespace.
++   255	
.oracle/checkins/batch-1-r10.md:1821: trailing whitespace.
++   257	
.oracle/checkins/batch-1-r10.md:1823: trailing whitespace.
++   262	
.oracle/checkins/batch-1-r10.md:1825: trailing whitespace.
++   274	
.oracle/checkins/batch-1-r10.md:1827: trailing whitespace.
++   276	
.oracle/checkins/batch-1-r10.md:1829: trailing whitespace.
++   280	
.oracle/checkins/batch-1-r10.md:1831: trailing whitespace.
++   290	
.oracle/checkins/batch-1-r10.md:1833: trailing whitespace.
++   292	
.oracle/checkins/batch-1-r10.md:1835: trailing whitespace.
++   461	
.oracle/checkins/batch-1-r10.md:1837: trailing whitespace.
++   463	
.oracle/checkins/batch-1-r10.md:1839: trailing whitespace.
++   465	
.oracle/checkins/batch-1-r10.md:1841: trailing whitespace.
++   470	
.oracle/checkins/batch-1-r10.md:1843: trailing whitespace.
++   492	
.oracle/checkins/batch-1-r10.md:1845: trailing whitespace.
++   502	
.oracle/checkins/batch-1-r10.md:1847: trailing whitespace.
++   504	
.oracle/checkins/batch-1-r10.md:1849: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r10.md:1851: trailing whitespace.
++     4	
.oracle/checkins/batch-1-r10.md:1853: trailing whitespace.
++     6	
.oracle/checkins/batch-1-r10.md:1855: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r10.md:1857: trailing whitespace.
++    17	
.oracle/checkins/batch-1-r10.md:1859: trailing whitespace.
++    19	
.oracle/checkins/batch-1-r10.md:1861: trailing whitespace.
++    25	
.oracle/checkins/batch-1-r10.md:1863: trailing whitespace.
++    27	
.oracle/checkins/batch-1-r10.md:1865: trailing whitespace.
++    29	
.oracle/checkins/batch-1-r10.md:1867: trailing whitespace.
++    31	
.oracle/checkins/batch-1-r10.md:1869: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r10.md:1871: trailing whitespace.
++    42	
.oracle/checkins/batch-1-r10.md:1873: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r10.md:1875: trailing whitespace.
++    51	
.oracle/checkins/batch-1-r10.md:1877: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r10.md:1879: trailing whitespace.
++    55	
.oracle/checkins/batch-1-r10.md:1881: trailing whitespace.
++    63	
.oracle/checkins/batch-1-r10.md:1883: trailing whitespace.
++    65	
.oracle/checkins/batch-1-r10.md:1885: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r10.md:1887: trailing whitespace.
++    74	
.oracle/checkins/batch-1-r10.md:1889: trailing whitespace.
++    76	
.oracle/checkins/batch-1-r10.md:1891: trailing whitespace.
++    78	
.oracle/checkins/batch-1-r10.md:1893: trailing whitespace.
++    86	
.oracle/checkins/batch-1-r10.md:1895: trailing whitespace.
++    88	
.oracle/checkins/batch-1-r10.md:1897: trailing whitespace.
++    94	
.oracle/checkins/batch-1-r10.md:1899: trailing whitespace.
++    96	
.oracle/checkins/batch-1-r10.md:1901: trailing whitespace.
++    98	
.oracle/checkins/batch-1-r10.md:1903: trailing whitespace.
++   100	
.oracle/checkins/batch-1-r10.md:1905: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1907: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1909: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1911: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1913: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1915: trailing whitespace.
++ 
.oracle/checkins/batch-1-r10.md:1917: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r10.md:1919: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r10.md:1921: trailing whitespace.
++   168	
.oracle/checkins/batch-1-r10.md:1923: trailing whitespace.
++   169	
.oracle/checkins/batch-1-r10.md:1925: trailing whitespace.
++   236	
.oracle/checkins/batch-1-r10.md:1927: trailing whitespace.
++   237	
.oracle/checkins/batch-1-r10.md:1929: trailing whitespace.
++   248	
.oracle/checkins/batch-1-r10.md:1931: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r10.md:1933: trailing whitespace.
++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-1-r10.md:1935: trailing whitespace.
++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-1-r10.md:1937: trailing whitespace.
++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-1-r10.md:1939: trailing whitespace.
++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-1-r10.md:1941: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r10.md:1943: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r10.md:1945: trailing whitespace.
++    11	
.oracle/checkins/batch-1-r10.md:1947: trailing whitespace.
++    20	
.oracle/checkins/batch-1-r10.md:1949: trailing whitespace.
++    21	
.oracle/checkins/batch-1-r10.md:1951: trailing whitespace.
++    48	
.oracle/checkins/batch-1-r10.md:1953: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r10.md:1955: trailing whitespace.
++    52	
.oracle/checkins/batch-1-r10.md:1957: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r10.md:1959: trailing whitespace.
++    56	
.oracle/checkins/batch-1-r10.md:1961: trailing whitespace.
++    57	
.oracle/checkins/batch-1-r10.md:1963: trailing whitespace.
++    60	
.oracle/checkins/batch-1-r10.md:1965: trailing whitespace.
++    61	
.oracle/checkins/batch-1-r10.md:1967: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r10.md:1969: trailing whitespace.
++    73	
.oracle/checkins/batch-1-r10.md:1971: trailing whitespace.
++    81	
.oracle/checkins/batch-1-r10.md:1973: trailing whitespace.
++    88	
.oracle/checkins/batch-1-r10.md:1975: trailing whitespace.
++    89	
.oracle/checkins/batch-1-r10.md:1977: trailing whitespace.
++    96	
.oracle/checkins/batch-1-r10.md:1979: trailing whitespace.
++    97	
.oracle/checkins/batch-1-r10.md:1981: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r10.md:1983: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r10.md:1985: trailing whitespace.
++   113	
.oracle/checkins/batch-1-r10.md:1987: trailing whitespace.
++   114	
.oracle/checkins/batch-1-r10.md:1989: trailing whitespace.
++   122	
.oracle/checkins/batch-1-r10.md:1991: trailing whitespace.
++   123	
.oracle/checkins/batch-1-r10.md:1993: trailing whitespace.
++   131	
.oracle/checkins/batch-1-r10.md:1995: trailing whitespace.
++   132	
.oracle/checkins/batch-1-r10.md:1997: trailing whitespace.
++   162	
.oracle/checkins/batch-1-r10.md:1999: trailing whitespace.
++   163	
.oracle/checkins/batch-1-r10.md:2001: trailing whitespace.
++   178	
.oracle/checkins/batch-1-r10.md:2003: trailing whitespace.
++   179	
.oracle/checkins/batch-1-r10.md:2005: trailing whitespace.
++   206	
.oracle/checkins/batch-1-r10.md:2007: trailing whitespace.
++   207	
.oracle/checkins/batch-1-r10.md:2009: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r10.md:2011: trailing whitespace.
++   250	
.oracle/checkins/batch-1-r10.md:2013: trailing whitespace.
++   288	
.oracle/checkins/batch-1-r10.md:2015: trailing whitespace.
++   289	
.oracle/checkins/batch-1-r10.md:2017: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r10.md:2019: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r10.md:2021: trailing whitespace.
++   324	
.oracle/checkins/batch-1-r10.md:2023: trailing whitespace.
++   325	
.oracle/checkins/batch-1-r10.md:2025: trailing whitespace.
++   338	
.oracle/checkins/batch-1-r10.md:2027: trailing whitespace.
++   339	
.oracle/checkins/batch-1-r10.md:2029: trailing whitespace.
++   356	
.oracle/checkins/batch-1-r10.md:2031: trailing whitespace.
++   357	
.oracle/checkins/batch-1-r10.md:2033: trailing whitespace.
++   375	
.oracle/checkins/batch-1-r10.md:2035: trailing whitespace.
++   376	
.oracle/checkins/batch-1-r10.md:2037: trailing whitespace.
++    35	
.oracle/checkins/batch-1-r10.md:2039: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r10.md:2041: trailing whitespace.
++    52	
.oracle/checkins/batch-1-r10.md:2043: trailing whitespace.
++    73	
.oracle/checkins/batch-1-r10.md:2045: trailing whitespace.
++   205	
.oracle/checkins/batch-1-r10.md:2047: trailing whitespace.
++   206	
.oracle/checkins/batch-1-r10.md:2049: trailing whitespace.
++   209	
.oracle/checkins/batch-1-r10.md:2051: trailing whitespace.
++   215	
.oracle/checkins/batch-1-r10.md:2053: trailing whitespace.
++   216	
.oracle/checkins/batch-1-r10.md:2055: trailing whitespace.
++   225	
.oracle/checkins/batch-1-r10.md:2057: trailing whitespace.
++   226	
.oracle/checkins/batch-1-r10.md:2059: trailing whitespace.
++   231	
.oracle/checkins/batch-1-r10.md:2061: trailing whitespace.
++   232	
.oracle/checkins/batch-1-r10.md:2063: trailing whitespace.
++   288	
.oracle/checkins/batch-1-r10.md:2065: trailing whitespace.
++   289	
.oracle/checkins/batch-1-r10.md:2067: trailing whitespace.
++   158	
.oracle/checkins/batch-1-r10.md:2069: trailing whitespace.
++   159	
.oracle/checkins/batch-1-r10.md:2071: trailing whitespace.
++   165	
.oracle/checkins/batch-1-r10.md:2073: trailing whitespace.
++   166	
.oracle/checkins/batch-1-r10.md:2075: trailing whitespace.
++   171	
.oracle/checkins/batch-1-r10.md:2077: trailing whitespace.
++   172	
.oracle/checkins/batch-1-r10.md:2079: trailing whitespace.
++   186	
.oracle/checkins/batch-1-r10.md:2081: trailing whitespace.
++   187	
.oracle/checkins/batch-1-r10.md:2083: trailing whitespace.
++   194	
.oracle/checkins/batch-1-r10.md:2085: trailing whitespace.
++   195	
.oracle/checkins/batch-1-r10.md:2087: trailing whitespace.
++   205	
.oracle/checkins/batch-1-r10.md:2104: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2105: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2132: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2133: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2136: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2143: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2144: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2156: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2157: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2234: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2235: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2310: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2311: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2322: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2323: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2345: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2346: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2362: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2369: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2657: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2658: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2759: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2760: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2769: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2770: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2788: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2789: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2795: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2796: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2807: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2808: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2824: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2825: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:2830: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:3057: trailing whitespace.
+    92	
.oracle/checkins/batch-1-r10.md:3058: trailing whitespace.
+    93	
.oracle/checkins/batch-1-r10.md:3070: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r10.md:3071: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r10.md:3146: trailing whitespace.
+   181	
.oracle/checkins/batch-1-r10.md:3147: trailing whitespace.
+   182	
.oracle/checkins/batch-1-r10.md:3201: trailing whitespace.
+   285	
.oracle/checkins/batch-1-r10.md:3210: trailing whitespace.
+   294	
.oracle/checkins/batch-1-r10.md:3211: trailing whitespace.
+   295	
.oracle/checkins/batch-1-r10.md:3218: trailing whitespace.
+   302	
.oracle/checkins/batch-1-r10.md:3219: trailing whitespace.
+   303	
.oracle/checkins/batch-1-r10.md:3228: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r10.md:3229: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r10.md:3246: trailing whitespace.
+   330	
.oracle/checkins/batch-1-r10.md:3247: trailing whitespace.
+   331	
.oracle/checkins/batch-1-r10.md:3254: trailing whitespace.
+   582	
.oracle/checkins/batch-1-r10.md:3255: trailing whitespace.
+   583	
.oracle/checkins/batch-1-r10.md:3259: trailing whitespace.
+   587	
.oracle/checkins/batch-1-r10.md:3264: trailing whitespace.
+   592	
.oracle/checkins/batch-1-r10.md:3276: trailing whitespace.
+   604	
.oracle/checkins/batch-1-r10.md:3281: trailing whitespace.
+   609	
.oracle/checkins/batch-1-r10.md:3293: trailing whitespace.
+   621	
.oracle/checkins/batch-1-r10.md:3305: trailing whitespace.
+   633	
.oracle/checkins/batch-1-r10.md:3306: trailing whitespace.
+   634	
.oracle/checkins/batch-1-r10.md:3327: trailing whitespace.
+   655	
.oracle/checkins/batch-1-r10.md:3328: trailing whitespace.
+   656	
.oracle/checkins/batch-1-r10.md:3332: trailing whitespace.
+   660	
.oracle/checkins/batch-1-r10.md:3339: trailing whitespace.
+   667	
.oracle/checkins/batch-1-r10.md:3362: trailing whitespace.
+   690	
.oracle/checkins/batch-1-r10.md:3374: trailing whitespace.
+   702	
.oracle/checkins/batch-1-r10.md:3389: trailing whitespace.
+   717	
.oracle/checkins/batch-1-r10.md:3410: trailing whitespace.
+   738	
.oracle/checkins/batch-1-r10.md:3411: trailing whitespace.
+   739	
.oracle/checkins/batch-1-r10.md:3469: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:3470: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:3479: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:3480: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:3720: trailing whitespace.
+   520	
.oracle/checkins/batch-1-r10.md:3739: trailing whitespace.
+   539	
.oracle/checkins/batch-1-r10.md:3740: trailing whitespace.
+   540	
.oracle/checkins/batch-1-r10.md:3750: trailing whitespace.
+   550	
.oracle/checkins/batch-1-r10.md:3751: trailing whitespace.
+   551	
.oracle/checkins/batch-1-r10.md:3813: trailing whitespace.
+   613	
.oracle/checkins/batch-1-r10.md:3817: trailing whitespace.
+   617	
.oracle/checkins/batch-1-r10.md:3818: trailing whitespace.
+   618	
.oracle/checkins/batch-1-r10.md:3831: trailing whitespace.
+   631	
.oracle/checkins/batch-1-r10.md:3832: trailing whitespace.
+   632	
.oracle/checkins/batch-1-r10.md:3835: trailing whitespace.
+   635	
.oracle/checkins/batch-1-r10.md:3844: trailing whitespace.
+   644	
.oracle/checkins/batch-1-r10.md:3845: trailing whitespace.
+   645	
.oracle/checkins/batch-1-r10.md:3851: trailing whitespace.
+   651	
.oracle/checkins/batch-1-r10.md:3852: trailing whitespace.
+   652	
.oracle/checkins/batch-1-r10.md:3883: trailing whitespace.
+   683	
.oracle/checkins/batch-1-r10.md:3893: trailing whitespace.
+   693	
.oracle/checkins/batch-1-r10.md:3929: trailing whitespace.
+   729	
.oracle/checkins/batch-1-r10.md:3930: trailing whitespace.
+   730	
.oracle/checkins/batch-1-r10.md:3948: trailing whitespace.
+   748	
.oracle/checkins/batch-1-r10.md:3949: trailing whitespace.
+   749	
.oracle/checkins/batch-1-r10.md:3985: trailing whitespace.
+   785	
.oracle/checkins/batch-1-r10.md:3986: trailing whitespace.
+   786	
.oracle/checkins/batch-1-r10.md:4000: trailing whitespace.
+   800	
.oracle/checkins/batch-1-r10.md:4001: trailing whitespace.
+   801	
.oracle/checkins/batch-1-r10.md:4023: trailing whitespace.
+   817	
.oracle/checkins/batch-1-r10.md:4024: trailing whitespace.
+   818	
.oracle/checkins/batch-1-r10.md:4120: trailing whitespace.
+   914	
.oracle/checkins/batch-1-r10.md:4121: trailing whitespace.
+   915	
.oracle/checkins/batch-1-r10.md:4220: trailing whitespace.
+  1014	
.oracle/checkins/batch-1-r10.md:4221: trailing whitespace.
+  1015	
.oracle/checkins/batch-1-r10.md:4230: trailing whitespace.
+  1024	
.oracle/checkins/batch-1-r10.md:4231: trailing whitespace.
+  1025	
.oracle/checkins/batch-1-r10.md:4233: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r10.md:4235: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r10.md:4237: trailing whitespace.
+     6	
.oracle/checkins/batch-1-r10.md:4239: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r10.md:4248: trailing whitespace.
+    17	
.oracle/checkins/batch-1-r10.md:4250: trailing whitespace.
+    19	
.oracle/checkins/batch-1-r10.md:4256: trailing whitespace.
+    25	
.oracle/checkins/batch-1-r10.md:4258: trailing whitespace.
+    27	
.oracle/checkins/batch-1-r10.md:4260: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r10.md:4262: trailing whitespace.
+    31	
.oracle/checkins/batch-1-r10.md:4271: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r10.md:4273: trailing whitespace.
+    42	
.oracle/checkins/batch-1-r10.md:4280: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r10.md:4282: trailing whitespace.
+    51	
.oracle/checkins/batch-1-r10.md:4284: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r10.md:4286: trailing whitespace.
+    55	
.oracle/checkins/batch-1-r10.md:4294: trailing whitespace.
+    63	
.oracle/checkins/batch-1-r10.md:4296: trailing whitespace.
+    65	
.oracle/checkins/batch-1-r10.md:4303: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r10.md:4305: trailing whitespace.
+    74	
.oracle/checkins/batch-1-r10.md:4307: trailing whitespace.
+    76	
.oracle/checkins/batch-1-r10.md:4309: trailing whitespace.
+    78	
.oracle/checkins/batch-1-r10.md:4317: trailing whitespace.
+    86	
.oracle/checkins/batch-1-r10.md:4319: trailing whitespace.
+    88	
.oracle/checkins/batch-1-r10.md:4325: trailing whitespace.
+    94	
.oracle/checkins/batch-1-r10.md:4327: trailing whitespace.
+    96	
.oracle/checkins/batch-1-r10.md:4329: trailing whitespace.
+    98	
.oracle/checkins/batch-1-r10.md:4331: trailing whitespace.
+   100	
.oracle/checkins/batch-1-r10.md:4340: trailing whitespace.
+   109	
.oracle/checkins/batch-1-r10.md:4342: trailing whitespace.
+   111	
.oracle/checkins/batch-1-r10.md:4350: trailing whitespace.
+   119	
.oracle/checkins/batch-1-r10.md:4352: trailing whitespace.
+   121	
.oracle/checkins/batch-1-r10.md:4354: trailing whitespace.
+   123	
.oracle/checkins/batch-1-r10.md:4356: trailing whitespace.
+   125	
.oracle/checkins/batch-1-r10.md:4364: trailing whitespace.
+   133	
.oracle/checkins/batch-1-r10.md:4366: trailing whitespace.
+   135	
.oracle/checkins/batch-1-r10.md:4373: trailing whitespace.
+   142	
.oracle/checkins/batch-1-r10.md:4375: trailing whitespace.
+   144	
.oracle/checkins/batch-1-r10.md:4377: trailing whitespace.
+   146	
.oracle/checkins/batch-1-r10.md:4379: trailing whitespace.
+   148	
.oracle/checkins/batch-1-r10.md:4390: trailing whitespace.
+   159	
.oracle/checkins/batch-1-r10.md:4392: trailing whitespace.
+   161	
.oracle/checkins/batch-1-r10.md:4399: trailing whitespace.
+   168	
.oracle/checkins/batch-1-r10.md:4401: trailing whitespace.
+   170	
.oracle/checkins/batch-1-r10.md:4416: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r10.md:4418: trailing whitespace.
+     4	
.oracle/checkins/batch-1-r10.md:4420: trailing whitespace.
+     6	
.oracle/checkins/batch-1-r10.md:4422: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r10.md:4431: trailing whitespace.
+    17	
.oracle/checkins/batch-1-r10.md:4433: trailing whitespace.
+    19	
.oracle/checkins/batch-1-r10.md:4439: trailing whitespace.
+    25	
.oracle/checkins/batch-1-r10.md:4441: trailing whitespace.
+    27	
.oracle/checkins/batch-1-r10.md:4443: trailing whitespace.
+    29	
.oracle/checkins/batch-1-r10.md:4445: trailing whitespace.
+    31	
.oracle/checkins/batch-1-r10.md:4454: trailing whitespace.
+    40	
.oracle/checkins/batch-1-r10.md:4456: trailing whitespace.
+    42	
.oracle/checkins/batch-1-r10.md:4463: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r10.md:4465: trailing whitespace.
+    51	
.oracle/checkins/batch-1-r10.md:4467: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r10.md:4469: trailing whitespace.
+    55	
.oracle/checkins/batch-1-r10.md:4477: trailing whitespace.
+    63	
.oracle/checkins/batch-1-r10.md:4479: trailing whitespace.
+    65	
.oracle/checkins/batch-1-r10.md:4486: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r10.md:5024: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r10.md:5025: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r10.md:5092: trailing whitespace.
+   173	
.oracle/checkins/batch-1-r10.md:5093: trailing whitespace.
+   174	
.oracle/checkins/batch-1-r10.md:5182: trailing whitespace.
+A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-1-r10.md:5198: trailing whitespace.
+   186	
.oracle/checkins/batch-1-r10.md:5199: trailing whitespace.
+   187	
.oracle/checkins/batch-1-r10.md:5206: trailing whitespace.
+   194	
.oracle/checkins/batch-1-r10.md:5207: trailing whitespace.
+   195	
.oracle/checkins/batch-1-r10.md:5217: trailing whitespace.
+   205	
.oracle/checkins/batch-1-r10.md:5218: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r10.md:5221: trailing whitespace.
+   209	
.oracle/checkins/batch-1-r10.md:5227: trailing whitespace.
+   215	
.oracle/checkins/batch-1-r10.md:5228: trailing whitespace.
+   216	
.oracle/checkins/batch-1-r10.md:5237: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r10.md:5238: trailing whitespace.
+   226	
.oracle/checkins/batch-1-r10.md:5243: trailing whitespace.
+   231	
.oracle/checkins/batch-1-r10.md:5244: trailing whitespace.
+   232	
.oracle/checkins/batch-1-r10.md:5253: trailing whitespace.
+   241	
.oracle/checkins/batch-1-r10.md:5254: trailing whitespace.
+   242	
.oracle/checkins/batch-1-r10.md:5260: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r10.md:5261: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r10.md:5274: trailing whitespace.
+   262	
.oracle/checkins/batch-1-r10.md:5275: trailing whitespace.
+   263	
.oracle/checkins/batch-1-r10.md:5280: trailing whitespace.
+   268	
.oracle/checkins/batch-1-r10.md:5281: trailing whitespace.
+   269	
.oracle/checkins/batch-1-r10.md:5288: trailing whitespace.
+   276	
.oracle/checkins/batch-1-r10.md:5289: trailing whitespace.
+   277	
.oracle/checkins/batch-1-r10.md:5296: trailing whitespace.
+   284	
.oracle/checkins/batch-1-r10.md:5297: trailing whitespace.
+   285	
.oracle/checkins/batch-1-r10.md:5313: trailing whitespace.
+     2	
.oracle/checkins/batch-1-r10.md:5319: trailing whitespace.
+     8	
.oracle/checkins/batch-1-r10.md:5322: trailing whitespace.
+    11	
.oracle/checkins/batch-1-r10.md:5331: trailing whitespace.
+    20	
.oracle/checkins/batch-1-r10.md:5332: trailing whitespace.
+    21	
.oracle/checkins/batch-1-r10.md:5359: trailing whitespace.
+    48	
.oracle/checkins/batch-1-r10.md:5360: trailing whitespace.
+    49	
.oracle/checkins/batch-1-r10.md:5363: trailing whitespace.
+    52	
.oracle/checkins/batch-1-r10.md:5364: trailing whitespace.
+    53	
.oracle/checkins/batch-1-r10.md:5367: trailing whitespace.
+    56	
.oracle/checkins/batch-1-r10.md:5368: trailing whitespace.
+    57	
.oracle/checkins/batch-1-r10.md:5371: trailing whitespace.
+    60	
.oracle/checkins/batch-1-r10.md:5372: trailing whitespace.
+    61	
.oracle/checkins/batch-1-r10.md:5383: trailing whitespace.
+    72	
.oracle/checkins/batch-1-r10.md:5384: trailing whitespace.
+    73	
.oracle/checkins/batch-1-r10.md:5392: trailing whitespace.
+    81	
.oracle/checkins/batch-1-r10.md:5399: trailing whitespace.
+    88	
.oracle/checkins/batch-1-r10.md:5400: trailing whitespace.
+    89	
.oracle/checkins/batch-1-r10.md:5407: trailing whitespace.
+    96	
.oracle/checkins/batch-1-r10.md:5408: trailing whitespace.
+    97	
.oracle/checkins/batch-1-r10.md:5416: trailing whitespace.
+   105	
.oracle/checkins/batch-1-r10.md:5417: trailing whitespace.
+   106	
.oracle/checkins/batch-1-r10.md:5424: trailing whitespace.
+   113	
.oracle/checkins/batch-1-r10.md:5425: trailing whitespace.
+   114	
.oracle/checkins/batch-1-r10.md:5433: trailing whitespace.
+   122	
.oracle/checkins/batch-1-r10.md:5434: trailing whitespace.
+   123	
.oracle/checkins/batch-1-r10.md:5442: trailing whitespace.
+   131	
.oracle/checkins/batch-1-r10.md:5443: trailing whitespace.
+   132	
.oracle/checkins/batch-1-r10.md:5473: trailing whitespace.
+   162	
.oracle/checkins/batch-1-r10.md:5474: trailing whitespace.
+   163	
.oracle/checkins/batch-1-r10.md:5489: trailing whitespace.
+   178	
.oracle/checkins/batch-1-r10.md:5490: trailing whitespace.
+   179	
.oracle/checkins/batch-1-r10.md:5517: trailing whitespace.
+   206	
.oracle/checkins/batch-1-r10.md:5518: trailing whitespace.
+   207	
.oracle/checkins/batch-1-r10.md:5560: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r10.md:5561: trailing whitespace.
+   250	
.oracle/checkins/batch-1-r10.md:5599: trailing whitespace.
+   288	
.oracle/checkins/batch-1-r10.md:5600: trailing whitespace.
+   289	
.oracle/checkins/batch-1-r10.md:5623: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r10.md:5624: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r10.md:5635: trailing whitespace.
+   324	
.oracle/checkins/batch-1-r10.md:5636: trailing whitespace.
+   325	
.oracle/checkins/batch-1-r10.md:5649: trailing whitespace.
+   338	
.oracle/checkins/batch-1-r10.md:5650: trailing whitespace.
+   339	
.oracle/checkins/batch-1-r10.md:5667: trailing whitespace.
+   356	
.oracle/checkins/batch-1-r10.md:5668: trailing whitespace.
+   357	
.oracle/checkins/batch-1-r10.md:5686: trailing whitespace.
+   375	
.oracle/checkins/batch-1-r10.md:5687: trailing whitespace.
+   376	
.oracle/checkins/batch-1-r10.md:5743: trailing whitespace.
+ 
.oracle/checkins/batch-1-r10.md:5744: trailing whitespace.
+ 

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 6acd4be 6afd558 -- astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/result.json docs/contracts/render-backend-v1.md tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/contracts.py b/astrid/core/rendering/contracts.py
index 62166f6..7771b5f 100644
--- a/astrid/core/rendering/contracts.py
+++ b/astrid/core/rendering/contracts.py
@@ -227,201 +227,204 @@ def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str
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
 
 
 def _require_override(value: Any, *, capability_id: str, label: str) -> dict[str, Any]:
     """Validate an override record: ``{from, to}`` with ``to`` equal to the
     resolution id (the override is what selected this implementation)."""
     mapping = _json_safe_mapping(value, label=label)
     required = {"from", "to"}
     if set(mapping) != required:
         raise ValueError(f"{label} must contain exactly 'from' and 'to'")
     _require_qualified_id(mapping["from"], f"{label} 'from'")
     resolved = _require_qualified_id(mapping["to"], f"{label} 'to'")
     if resolved != capability_id:
         raise ValueError(f"{label} 'to' must equal the resolved capability id {capability_id!r}")
     return mapping
 
 
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
-    if any(not part.strip() for part in raw_parts):
+    # ECMAScript \s whitespace set, used so DTO and schema agree across
+    # languages (Python str.strip() would diverge on \u0085 and \uFEFF).
+    _WS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
+    if any(not part.strip(_WS) for part in raw_parts):
         raise ValueError(f"{label} must not contain empty or whitespace-only path components")
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
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 3a363c1..d037a65 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -54,217 +54,226 @@ def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None
 
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
                 profile = VideoArtifact.from_dict(
                     _json_safe_mapping(profile.to_dict(), label="artifact")
                 )
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
         for raw_profile in value:
-            if not isinstance(raw_profile, VideoArtifact):
+            if isinstance(raw_profile, VideoArtifact):
+                # Reconstruct through the DTO so mutation cannot smuggle
+                # invalid paths, profiles, or attachments past validation.
+                profile = VideoArtifact.from_dict(
+                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
+                )
+                path = profile.path
+                record = _artifact_lineage(profile)
+            elif isinstance(raw_profile, Mapping):
+                # Already-emitted lineage record: re-validate and re-key by
+                # its (validated) path so emitted provenance round-trips.
+                record = _artifact_lineage_from_mapping(
+                    raw_profile, key=str(raw_profile.get("path", ""))
+                )
+                path = record["path"]
+            else:
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
-                    "so lineage records stay path-keyed"
+                    "or emitted lineage records"
                 )
-            # Reconstruct through the DTO so mutation cannot smuggle invalid
-            # paths, profiles, or attachments past validation.
-            profile = VideoArtifact.from_dict(
-                _json_safe_mapping(raw_profile.to_dict(), label="artifact")
-            )
-            if profile.path in seen_paths:
+            if path in seen_paths:
                 raise ValueError(
                     f"artifact_profiles sequence contains duplicate path "
-                    f"{profile.path!r}"
+                    f"{path!r}"
                 )
-            seen_paths.add(profile.path)
-            record = _artifact_lineage(profile)
+            seen_paths.add(path)
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
         "path": key,
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
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index eff7c06..ee90481 100644
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
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\s]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\s]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
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
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index c4acc91..990f33f 100644
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
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\s]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\s]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
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
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
           "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 88d822e..6c40136 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -380,212 +380,216 @@ every subsequent start equals the preceding end, and the last end equals the
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
 are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
 hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
-sequence form (one VideoArtifact per segment); single-segment plans may use a
-path-keyed mapping. Every record carries its `path`, `profile`, a validated
-64-hex string `sha256`, and `attachments` — each attachment `{path, kind,
-sha256}` with a workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and
-globally unique names across all segment artifacts. All plan, artifact, and
-attachment values are reconstructed through their DTO validators at the
-provenance boundary (mutated frozen instances cannot bypass validation);
-duplicate paths, duplicate attachment names, path escapes, invalid kinds,
-profile-only entries, null/malformed hashes, and cardinality mismatches are
-rejected. All JSON Schema patterns are language-neutral (ECMAScript-valid;
-no Python-only anchors). Replay can verify rendered outputs byte-for-byte.
-`input_hashes` describe inputs only, never rendered outputs.
+sequence form (one VideoArtifact or emitted lineage record per segment, in
+segment order); single-segment plans may use a path-keyed mapping. Emitted
+lineage records round-trip (re-passing them validates identically). Every
+record carries its `path`, `profile`, a validated 64-hex string `sha256`, and
+`attachments` — each attachment `{path, kind, sha256}` with a workspace-relative
+path, kind matching `[a-z][a-z0-9-]*`, and globally unique names across all
+segment artifacts. All plan, artifact, and attachment values are reconstructed
+through their DTO validators at the provenance boundary (mutated frozen
+instances cannot bypass validation); duplicate paths, duplicate attachment
+names, path escapes, invalid kinds, profile-only entries, null/malformed
+hashes, and cardinality mismatches are rejected. All JSON Schema patterns are
+language-neutral (ECMAScript-valid; no Python-only anchors), and workspacePath
+uses an explicit ECMAScript `\s` whitespace class shared with the DTO so
+Python and non-Python validators agree on whitespace-only components. Replay
+can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
+only, never rendered outputs.
 
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
index 3a87be3..14ecc19 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -880,200 +880,226 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
                     sha256=SHA_B,
                     duration_frames=24,
                     audio=AudioOwnership.RENDERED,
                 )
             ],
         )
     with pytest.raises(ValueError, match="attachment path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {
                         "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
                     },
                 },
             },
         )
     with pytest.raises(ValueError, match="attachment kind"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={
                 "out/v.mp4": {
                     "profile": _profile(),
                     "sha256": SHA_B,
                     "attachments": {
                         "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
                     },
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
+    # Emitted lineage records round-trip: re-passing the emitted sequence
+    # (dictionary records) validates and reproduces the same output.
+    first = assemble_provenance_v2(
+        **base,
+        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+        artifact_profiles=[
+            VideoArtifact(
+                path="outputs/a.mp4",
+                profile=_profile(audio=False),
+                sha256=SHA_B,
+                duration_frames=24,
+            ),
+            VideoArtifact(
+                path="outputs/b.mp4",
+                profile=_profile(audio=False),
+                sha256=SHA_C,
+                duration_frames=24,
+            ),
+        ],
+    )
+    second = assemble_provenance_v2(
+        **base,
+        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+        artifact_profiles=first["artifact_profiles"],
+    )
+    assert second["artifact_profiles"] == first["artifact_profiles"]
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
     # A mutated VideoArtifact instance is reconstructed at the boundary, so a
     # smuggled escaped path cannot pass validation.
     with pytest.raises(ValueError, match="workspace path"):
         mutated = VideoArtifact(
             path="outputs/a.mp4",
             profile=_profile(audio=False),
             sha256=SHA_B,
             duration_frames=48,
         )
         object.__setattr__(mutated, "path", "../escape.mp4")
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles=[mutated],
         )
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
 

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=25 6acd4be 6afd558 -- astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/result.json tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/contracts.py b/astrid/core/rendering/contracts.py
index 62166f6..7771b5f 100644
--- a/astrid/core/rendering/contracts.py
+++ b/astrid/core/rendering/contracts.py
@@ -302,51 +302,54 @@ def _require_rational(value: Any, label: str) -> tuple[int, int]:
 
 
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
-    if any(not part.strip() for part in raw_parts):
+    # ECMAScript \s whitespace set, used so DTO and schema agree across
+    # languages (Python str.strip() would diverge on \u0085 and \uFEFF).
+    _WS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
+    if any(not part.strip(_WS) for part in raw_parts):
         raise ValueError(f"{label} must not contain empty or whitespace-only path components")
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
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 3a363c1..d037a65 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -129,67 +129,76 @@ def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
                 )
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
         for raw_profile in value:
-            if not isinstance(raw_profile, VideoArtifact):
+            if isinstance(raw_profile, VideoArtifact):
+                # Reconstruct through the DTO so mutation cannot smuggle
+                # invalid paths, profiles, or attachments past validation.
+                profile = VideoArtifact.from_dict(
+                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
+                )
+                path = profile.path
+                record = _artifact_lineage(profile)
+            elif isinstance(raw_profile, Mapping):
+                # Already-emitted lineage record: re-validate and re-key by
+                # its (validated) path so emitted provenance round-trips.
+                record = _artifact_lineage_from_mapping(
+                    raw_profile, key=str(raw_profile.get("path", ""))
+                )
+                path = record["path"]
+            else:
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
-                    "so lineage records stay path-keyed"
+                    "or emitted lineage records"
                 )
-            # Reconstruct through the DTO so mutation cannot smuggle invalid
-            # paths, profiles, or attachments past validation.
-            profile = VideoArtifact.from_dict(
-                _json_safe_mapping(raw_profile.to_dict(), label="artifact")
-            )
-            if profile.path in seen_paths:
+            if path in seen_paths:
                 raise ValueError(
                     f"artifact_profiles sequence contains duplicate path "
-                    f"{profile.path!r}"
+                    f"{path!r}"
                 )
-            seen_paths.add(profile.path)
-            record = _artifact_lineage(profile)
+            seen_paths.add(path)
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
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index eff7c06..ee90481 100644
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
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\s]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\s]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
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
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index c4acc91..990f33f 100644
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
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![\\s]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\s]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
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
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 3a87be3..14ecc19 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -955,50 +955,76 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
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
+    # Emitted lineage records round-trip: re-passing the emitted sequence
+    # (dictionary records) validates and reproduces the same output.
+    first = assemble_provenance_v2(
+        **base,
+        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+        artifact_profiles=[
+            VideoArtifact(
+                path="outputs/a.mp4",
+                profile=_profile(audio=False),
+                sha256=SHA_B,
+                duration_frames=24,
+            ),
+            VideoArtifact(
+                path="outputs/b.mp4",
+                profile=_profile(audio=False),
+                sha256=SHA_C,
+                duration_frames=24,
+            ),
+        ],
+    )
+    second = assemble_provenance_v2(
+        **base,
+        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+        artifact_profiles=first["artifact_profiles"],
+    )
+    assert second["artifact_profiles"] == first["artifact_profiles"]
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
     # A mutated VideoArtifact instance is reconstructed at the boundary, so a
     # smuggled escaped path cannot pass validation.
     with pytest.raises(ValueError, match="workspace path"):
         mutated = VideoArtifact(
             path="outputs/a.mp4",
             profile=_profile(audio=False),
             sha256=SHA_B,
             duration_frames=48,
         )
         object.__setattr__(mutated, "path", "../escape.mp4")
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles=[mutated],

exec
/bin/zsh -lc 'rg -n "workspacePath|Draft7Validator|jsonschema|_require_workspace_relative_path|_WS =" astrid/core/rendering tests/core/rendering pyproject.toml requirements* 2>/dev/null | head -240' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
zsh:1: no matches found: requirements*

exec
/bin/zsh -lc 'rg -n "workspacePath|Draft7Validator|jsonschema|_require_workspace_relative_path|_WS =" astrid/core/rendering tests/core/rendering pyproject.toml' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
pyproject.toml:13:    "jsonschema>=4.0",
astrid/core/rendering/provenance.py:25:    _require_workspace_relative_path,
astrid/core/rendering/provenance.py:120:            path = _require_workspace_relative_path(path, "artifact key")
astrid/core/rendering/provenance.py:208:        embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
tests/core/rendering/test_schema_roundtrip.py:9:import jsonschema
tests/core/rendering/test_schema_roundtrip.py:77:    jsonschema.Draft7Validator.check_schema(schema)
tests/core/rendering/test_schema_roundtrip.py:78:    validator = jsonschema.Draft7Validator(schema)
tests/core/rendering/test_schema_roundtrip.py:93:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:342:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:374:    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
astrid/core/rendering/contracts.py:314:def _require_workspace_relative_path(value: Any, label: str) -> str:
astrid/core/rendering/contracts.py:329:    _WS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
astrid/core/rendering/contracts.py:604:        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))
astrid/core/rendering/contracts.py:677:        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
astrid/core/rendering/schemas/v1/finalize.json:651:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/finalize.json:682:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
astrid/core/rendering/schemas/v1/result.json:196:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/result.json:227:          "$ref": "#/definitions/workspacePath"

exec
/bin/zsh -lc "sed -n '1,130p' tests/core/rendering/test_schema_roundtrip.py && sed -n '320,390p' tests/core/rendering/test_schema_roundtrip.py && rg -n \"0085|FEFF|00a0|200[0-9aA]|whitespace|workspace path|workspacePath\" tests/core/rendering .oracle/checkins/batch-1-r10.md | tail -120" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from astrid.core.rendering import RenderPlan, RenderRequest, RenderResult, SupportReport
from astrid.core.rendering.contracts import (
    FinalizeRequest,
    FinalizerManifest,
    PlannerManifest,
    RendererManifest,
    parse_wire_result,
)


SCHEMA_DIR = (
    Path(__file__).resolve().parents[3]
    / "astrid"
    / "core"
    / "rendering"
    / "schemas"
    / "v1"
)
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "v1"
SCHEMA_NAMES = (
    "request.json",
    "result.json",
    "support.json",
    "plan.json",
    "finalize.json",
    "renderer-manifest.json",
    "planner-manifest.json",
    "finalizer-manifest.json",
)
WIRE_SCHEMA_NAMES = (
    "request.json",
    "result.json",
    "support.json",
    "plan.json",
    "finalize.json",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_schema(name: str) -> dict[str, Any]:
    return _load_json(SCHEMA_DIR / name)


def _load_fixture(name: str) -> dict[str, Any]:
    return _load_json(FIXTURE_DIR / name)


PARSERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "request.json": RenderRequest.from_dict,
    "result.json": parse_wire_result,
    "support.json": SupportReport.from_dict,
    "plan.json": RenderPlan.from_dict,
    "finalize.json": FinalizeRequest.from_dict,
    "renderer-manifest.json": RendererManifest.from_dict,
    "planner-manifest.json": PlannerManifest.from_dict,
    "finalizer-manifest.json": FinalizerManifest.from_dict,
}


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_every_schema_and_example_is_valid_and_parses(schema_name: str) -> None:
    schema = _load_schema(schema_name)
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    examples = schema.get("examples")
    assert isinstance(examples, list) and examples, f"{schema_name} must carry examples"

    for example in examples:
        validator.validate(example)
        dto = PARSERS[schema_name](example)
        round_trip = dto.to_dict()
        validator.validate(round_trip)
        assert round_trip == example


@pytest.mark.parametrize("schema_name", WIRE_SCHEMA_NAMES)
def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
    payload = _load_fixture(schema_name)
    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
    validator.validate(payload)
    assert PARSERS[schema_name](payload).to_dict() == payload


def test_every_duplicated_profile_definition_is_identical() -> None:
    profile_definitions = {
        name: _load_schema(name)["definitions"]["renderProfile"]
        for name in ("request.json", "plan.json", "result.json", "finalize.json")
    }
    reference = profile_definitions["request.json"]
    assert all(definition == reference for definition in profile_definitions.values())


def _accepted(parser: Callable[[dict[str, Any]], Any], payload: dict[str, Any]) -> bool:
    try:
        parser(payload)
    except Exception:
        return False
    return True


def _set(payload: dict[str, Any], path: tuple[str | int, ...], value: Any) -> dict[str, Any]:
    result = deepcopy(payload)
    target: Any = result
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    return result


def _delete(payload: dict[str, Any], path: tuple[str | int, ...]) -> dict[str, Any]:
    result = deepcopy(payload)
    target: Any = result
    for part in path[:-1]:
        target = target[part]
    del target[path[-1]]
    return result
        ("boolean version", _set(base, ("schema_version",), True)),
        ("malformed version", _set(base, ("schema_version",), "1")),
        ("unknown version", _set(base, ("schema_version",), 2)),
    ]


CASE_BUILDERS: dict[str, Callable[[], list[tuple[str, dict[str, Any]]]]] = {
    "request.json": _request_cases,
    "support.json": _support_cases,
    "plan.json": _plan_cases,
    "result.json": _result_cases,
    "finalize.json": _finalize_cases,
    "renderer-manifest.json": lambda: _manifest_cases("renderer-manifest.json", "render"),
    "planner-manifest.json": lambda: _manifest_cases("planner-manifest.json", "plan"),
    "finalizer-manifest.json": lambda: _manifest_cases(
        "finalizer-manifest.json", "finalize"
    ),
}


@pytest.mark.parametrize("schema_name", SCHEMA_NAMES)
def test_adversarial_schema_and_dto_parity(schema_name: str) -> None:
    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
    parser = PARSERS[schema_name]
    for label, payload in CASE_BUILDERS[schema_name]():
        schema_accepts = validator.is_valid(payload)
        dto_accepts = _accepted(parser, payload)
        expected = label.startswith("valid ")
        assert schema_accepts is expected, (
            f"{schema_name} unexpected schema result for {label}: "
            f"expected={expected}, actual={schema_accepts}"
        )
        assert dto_accepts == schema_accepts, (
            f"{schema_name} parity mismatch for {label}: "
            f"schema={schema_accepts}, dto={dto_accepts}"
        )


@pytest.mark.parametrize(
    "path",
    [
        "../escape.mp4",
        "outputs/./escape.mp4",
        "outputs//escape.mp4",
        "outputs/",
        "/tmp/escape.mp4",
        "C:escape.mp4",
        r"C:\\temp\\escape.mp4",
        r"dir\\escape.mp4",
    ],
)
def test_result_schema_rejects_uncontained_artifact_paths(path: str) -> None:
    result = _load_fixture("result.json")
    result["video"]["path"] = path
    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)


def test_python_result_type_annotation_remains_the_success_dto() -> None:
    payload = _load_fixture("result.json")
    parsed = parse_wire_result(payload)
    assert isinstance(parsed, RenderResult)
.oracle/checkins/batch-1-r10.md:1978:.oracle/checkins/batch-1-r9.md:8603: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1980:.oracle/checkins/batch-1-r9.md:8611: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1982:.oracle/checkins/batch-1-r9.md:8612: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1984:.oracle/checkins/batch-1-r9.md:8619: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1986:.oracle/checkins/batch-1-r9.md:8620: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1988:.oracle/checkins/batch-1-r9.md:8628: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1990:.oracle/checkins/batch-1-r9.md:8629: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1992:.oracle/checkins/batch-1-r9.md:8637: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1994:.oracle/checkins/batch-1-r9.md:8638: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1996:.oracle/checkins/batch-1-r9.md:8668: trailing whitespace.
.oracle/checkins/batch-1-r10.md:1998:.oracle/checkins/batch-1-r9.md:8669: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2000:.oracle/checkins/batch-1-r9.md:8684: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2002:.oracle/checkins/batch-1-r9.md:8685: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2004:.oracle/checkins/batch-1-r9.md:8712: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2006:.oracle/checkins/batch-1-r9.md:8713: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2008:.oracle/checkins/batch-1-r9.md:8755: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2010:.oracle/checkins/batch-1-r9.md:8756: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2012:.oracle/checkins/batch-1-r9.md:8794: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2014:.oracle/checkins/batch-1-r9.md:8795: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2016:.oracle/checkins/batch-1-r9.md:8818: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2018:.oracle/checkins/batch-1-r9.md:8819: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2020:.oracle/checkins/batch-1-r9.md:8830: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2022:.oracle/checkins/batch-1-r9.md:8831: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2024:.oracle/checkins/batch-1-r9.md:8844: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2026:.oracle/checkins/batch-1-r9.md:8845: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2028:.oracle/checkins/batch-1-r9.md:8862: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2030:.oracle/checkins/batch-1-r9.md:8863: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2032:.oracle/checkins/batch-1-r9.md:8881: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2034:.oracle/checkins/batch-1-r9.md:8882: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2036:.oracle/checkins/batch-1-r9.md:8920: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2038:.oracle/checkins/batch-1-r9.md:8925: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2040:.oracle/checkins/batch-1-r9.md:8937: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2042:.oracle/checkins/batch-1-r9.md:8958: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2044:.oracle/checkins/batch-1-r9.md:8980: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2046:.oracle/checkins/batch-1-r9.md:8981: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2048:.oracle/checkins/batch-1-r9.md:8984: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2050:.oracle/checkins/batch-1-r9.md:8990: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2052:.oracle/checkins/batch-1-r9.md:8991: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2054:.oracle/checkins/batch-1-r9.md:9000: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2056:.oracle/checkins/batch-1-r9.md:9001: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2058:.oracle/checkins/batch-1-r9.md:9006: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2060:.oracle/checkins/batch-1-r9.md:9007: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2062:.oracle/checkins/batch-1-r9.md:9057: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2064:.oracle/checkins/batch-1-r9.md:9058: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2066:.oracle/checkins/batch-1-r9.md:9096: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2068:.oracle/checkins/batch-1-r9.md:9097: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2070:.oracle/checkins/batch-1-r9.md:9103: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2072:.oracle/checkins/batch-1-r9.md:9104: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2074:.oracle/checkins/batch-1-r9.md:9109: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2076:.oracle/checkins/batch-1-r9.md:9110: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2078:.oracle/checkins/batch-1-r9.md:9124: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2080:.oracle/checkins/batch-1-r9.md:9125: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2082:.oracle/checkins/batch-1-r9.md:9132: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2084:.oracle/checkins/batch-1-r9.md:9133: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2086:.oracle/checkins/batch-1-r9.md:9143: trailing whitespace.
.oracle/checkins/batch-1-r10.md:2090:/bin/zsh -lc "git diff --no-ext-diff --unified=80 788501c..6acd4be -- astrid/core/rendering/provenance.py astrid/core/rendering/schemas/v1/finalize.json astrid/core/rendering/schemas/v1/result.json tests/core/rendering/test_contracts.py && rg -n -C 8 'VideoArtifact reconstruction|workspacePath still|bypassable|DTO-equivalent|"'^PASS$|''^1'"\\.|"'^2'"\\.' .oracle/checkins/batch-1-r9.md | tail -n 220" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r10.md:2453:     "workspacePath": {
.oracle/checkins/batch-1-r10.md:2564:     "workspacePath": {
.oracle/checkins/batch-1-r10.md:2717:     with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:2738:+    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:2980:3317:788501c (HEAD -> oracle-run) batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
.oracle/checkins/batch-1-r10.md:2982:3319-ab486f9 batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)
.oracle/checkins/batch-1-r10.md:3002:3436-3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
.oracle/checkins/batch-1-r10.md:3009:3443-3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
.oracle/checkins/batch-1-r10.md:3025:6899:    batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
.oracle/checkins/batch-1-r10.md:3045:9179:2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
.oracle/checkins/batch-1-r10.md:3050:9184:2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
.oracle/checkins/batch-1-r10.md:3233:   317	        raise ValueError(f"{label} must be a normalized workspace path using forward slashes")
.oracle/checkins/batch-1-r10.md:3242:   326	        raise ValueError(f"{label} must be a normalized contained workspace path")
.oracle/checkins/batch-1-r10.md:3244:   328	        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
.oracle/checkins/batch-1-r10.md:3427:     with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:3448:+    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:3850:   650	    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
.oracle/checkins/batch-1-r10.md:4180:   974	    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:4199:   993	    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:4413:/bin/zsh -lc "nl -ba .oracle/tasklist.md | sed -n '1,72p'; rg -n \"artifact_profiles|provenance|lineage|round.trip|workspacePath|workspace path\" .oracle/plan.md .oracle/briefs .oracle/findings docs astrid tests -g '*.md' -g '*.py' -g '*.json' | head -n 400" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r10.md:4545:docs/reference/architecture.md:123:| `astrid/core/paths.py` | Shared library | Repository and workspace path resolution. |
.oracle/checkins/batch-1-r10.md:4624:tests/core/rendering/test_contracts.py:974:    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:4629:tests/core/rendering/test_contracts.py:993:    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:4727:docs/architecture/timeline-event-sourcing/m1-schema.md:141:3. **Canonical JSON authoritative form.** Python-side canonicalization is authoritative. Rules: sorted keys, UTF-8 bytes, compact separators `","` and `":"`, no trailing whitespace, no NaN/Inf, numbers preserve their parsed source form (integers as int, floats as float, no `1.0` to `1` coercion), `null` values are omitted from canonical form, and the `hash` field itself is excluded. Postgres-side hashing in m6's RPC must use a stored procedure that produces the byte-identical form, either PL/pgSQL or a small extension. Cross-backend hash parity is enforced by m8 round-trip tests against shared golden fixtures introduced in m4.
.oracle/checkins/batch-1-r10.md:4766:docs/architecture/repo-shape.md:152:| `astrid/core/paths.py` | **Shared library** | Repository and workspace path resolution. |
.oracle/checkins/batch-1-r10.md:5006:6acd4be (HEAD -> oracle-run) batch1-rework10: oracle re-review9 issues 1-2 (VideoArtifact reconstruction via from_dict in both lineage forms, validated path emission, workspacePath \s whitespace components + leading-component rejection)
.oracle/checkins/batch-1-r10.md:5007:788501c batch1-rework9: oracle re-review8 issues 1-3 (plan/artifact/attachment DTO reconstruction at boundary, ordered per-segment lineage + sequence-form requirement for multi-segment, ECMAScript-portable end assertions, DTO-equivalent workspacePath)
.oracle/checkins/batch-1-r10.md:5009:ab486f9 batch1-rework7: oracle re-review6 issues 1-3 (per-segment path-keyed lineage cardinality, attachment contract validation via Attachment DTO + name==key, supportReport features propertyNames, workspacePath multiline containment)
.oracle/checkins/batch-1-r10.md:5010:086d692 batch1-rework6: oracle re-review5 issues 1-3 (lineage required+shape-bound+path-bound, NUL-after-newline, hashMap/feature propertyNames, workspacePath newlines)
.oracle/checkins/batch-1-r10.md:5012:808030e batch1-rework4: oracle re-review3 issues 1-3 (required 7-key resolution records, support coherence, hashed artifact lineage, anchored NUL/whitespace parity, cross-pack installable override fixture)
.oracle/checkins/batch-1-r10.md:5014:88c75f3 batch1-rework2: oracle re-review issues 1-5 (real-fixture deconcealment, underscore-compatible ids, provenance v1 preservation + v2 additive, whitespace parity, transitive override routing, baseline C0 evidence)
.oracle/checkins/batch-1-r10.md:5137:The incremental code is small, but one prior concern was broader than the host summary: ordered lineage emitted as JSON must remain consumable, and `\s` must mean the same thing outside Python. I’m probing those two exact boundaries now, including ECMAScript’s Unicode whitespace set.
.oracle/checkins/batch-1-r10.md:5139:/bin/zsh -lc "python -c 'print(\"python_whitespace\", \" \".join(f\"U+{cp:04X}\" for cp in range(0x10000) if chr(cp).isspace())); print(\"python_strip_special\", [(f\"U+{cp:04X}\", bool(chr(cp).strip())) for cp in (0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff)])'
.oracle/checkins/batch-1-r10.md:5140:node -e 'const cps=[]; for(let cp=0;cp<0x10000;cp++){if(/"'^'"\\s"'$/u.test(String.fromCodePoint(cp)))cps.push("U+"+cp.toString(16).toUpperCase().padStart(4,"0"));} console.log("ecmascript_whitespace",cps.join(" ")); for(const cp of [0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff]) console.log("U+"+cp.toString(16).toUpperCase().padStart(4,"0"),/''^'"\\s"'$/u.test(String.fromCodePoint(cp)));'"'
.oracle/checkins/batch-1-r10.md:5142:for cp in (0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff):
.oracle/checkins/batch-1-r10.md:5147:node -e 'const fs=require(\"fs\"); for(const fn of [\"result.json\",\"finalize.json\"]){const schema=JSON.parse(fs.readFileSync(\"astrid/core/rendering/schemas/v1/\"+fn,\"utf8\")); const re=new RegExp(schema.definitions.workspacePath.pattern,\"u\"); console.log(fn); for(const cp of [0x001c,0x001d,0x001e,0x001f,0x0085,0xfeff]){const s=\"dir/\"+String.fromCodePoint(cp)+\"/v.mp4\"; console.log(\"U+\"+cp.toString(16).toUpperCase().padStart(4,\"0\"),re.test(s));}}'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r10.md:5149:python_whitespace U+0009 U+000A U+000B U+000C U+000D U+001C U+001D U+001E U+001F U+0020 U+0085 U+00A0 U+1680 U+2000 U+2001 U+2002 U+2003 U+2004 U+2005 U+2006 U+2007 U+2008 U+2009 U+200A U+2028 U+2029 U+202F U+205F U+3000
.oracle/checkins/batch-1-r10.md:5150:python_strip_special [('U+001C', False), ('U+001D', False), ('U+001E', False), ('U+001F', False), ('U+0085', False), ('U+FEFF', True)]
.oracle/checkins/batch-1-r10.md:5151:ecmascript_whitespace U+0009 U+000A U+000B U+000C U+000D U+0020 U+00A0 U+1680 U+2000 U+2001 U+2002 U+2003 U+2004 U+2005 U+2006 U+2007 U+2008 U+2009 U+200A U+2028 U+2029 U+202F U+205F U+3000 U+FEFF
.oracle/checkins/batch-1-r10.md:5156:U+0085 false
.oracle/checkins/batch-1-r10.md:5157:U+FEFF true
.oracle/checkins/batch-1-r10.md:5162:U+0085 REJECT ValueError 'dir/\x85/v.mp4'
.oracle/checkins/batch-1-r10.md:5163:U+FEFF ACCEPT 'dir/\ufeff/v.mp4'
.oracle/checkins/batch-1-r10.md:5169:U+0085 true
.oracle/checkins/batch-1-r10.md:5170:U+FEFF false
.oracle/checkins/batch-1-r10.md:5176:U+0085 true
.oracle/checkins/batch-1-r10.md:5177:U+FEFF false
.oracle/checkins/batch-1-r10.md:5190:/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '180,285p'; rg -n \"def _require_string|_STRING\" astrid/core/rendering/contracts.py | head -n 30; rg -n -C 3 \"workspacePath\" tests/core/rendering/test_schema_roundtrip.py tests/core/rendering/test_contracts.py | head -n 200" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r10.md:5303:/bin/zsh -lc "rg -n '\"workspacePath\"|\\\\\\\\s\\\\\\\\\\]\\*/|must not contain empty or whitespace-only' astrid/core/rendering tests/fixtures docs/contracts/render-backend-v1.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-1-r10.md:5305:astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
.oracle/checkins/batch-1-r10.md:5306:astrid/core/rendering/contracts.py:328:        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
.oracle/checkins/batch-1-r10.md:5307:astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
.oracle/checkins/batch-1-r10.md:5465:   154	        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
.oracle/checkins/batch-1-r10.md:5466:   155	        ("whitespace metadata key", _set(base, ("metadata",), {"   ": "demo"})),
.oracle/checkins/batch-1-r10.md:5468:   157	        ("whitespace assets path", _set(base, ("assets_registry_path",), "   ")),
.oracle/checkins/batch-1-r10.md:5480:   169	        ("whitespace reason", _set(base, ("reasons",), ["   "])),
.oracle/checkins/batch-1-r10.md:5481:   170	        ("whitespace backend version", _set(base, ("backend_version",), "   ")),
.oracle/checkins/batch-1-r10.md:5529:   218	        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
.oracle/checkins/batch-1-r10.md:5530:   219	        ("whitespace log", _set(base, ("logs",), ["   "])),
.oracle/checkins/batch-1-r10.md:5532:   221	        ("whitespace video path", _set(base, ("video", "path"), "   ")),
.oracle/checkins/batch-1-r10.md:5572:   261	        ("whitespace metadata value", _set(base, ("metadata",), {"project_id": "   "})),
.oracle/checkins/batch-1-r10.md:5722:+    with pytest.raises(ValueError, match="workspace path"):
.oracle/checkins/batch-1-r10.md:5750:2. `workspacePath` remains non-equivalent across languages. Python `str.strip()` and ECMAScript `\s` have different character sets: `"dir/\u0085/v.mp4"` is DTO-rejected but schema-accepted; `"dir/\uFEFF/v.mp4"` is DTO-accepted but schema-rejected. [contracts.py:327](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:327) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68)
.oracle/checkins/batch-1-r10.md:5755:2. `workspacePath` remains non-equivalent across languages. Python `str.strip()` and ECMAScript `\s` have different character sets: `"dir/\u0085/v.mp4"` is DTO-rejected but schema-accepted; `"dir/\uFEFF/v.mp4"` is DTO-accepted but schema-rejected. [contracts.py:327](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:327) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68)

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'import json,re; from pathlib import Path; from astrid.core.rendering.contracts import _require_workspace_relative_path as dto; p=json.loads(Path(\"astrid/core/rendering/schemas/v1/result.json\").read_text())[\"definitions\"][\"workspacePath\"][\"pattern\"]; cases=[\"dir/\\u2001/v.mp4\",\"dir/\\u2009/v.mp4\",\"\\u0085\",\"dir/\\u0085/v.mp4\",\"\\ufeff\",\"dir/\\ufeff/v.mp4\"]; print(\"python\");
for s in cases:
  try: dto(s,\"path\"); d=True
  except Exception: d=False
  print(ascii(s),\"dto\",d,\"schema_re\",bool(re.search(p,s)))'
node -e 'const fs=require(\"fs\"); const p=JSON.parse(fs.readFileSync(\"astrid/core/rendering/schemas/v1/result.json\",\"utf8\")).definitions.workspacePath.pattern; const r=new RegExp(p,\"u\"); const cases=[\"dir/\\u2001/v.mp4\",\"dir/\\u2009/v.mp4\",\"\\u0085\",\"dir/\\u0085/v.mp4\",\"\\ufeff\",\"dir/\\ufeff/v.mp4\"]; console.log(\"ecmascript\"); for(const s of cases) console.log(JSON.stringify(s),r.test(s));'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 175ms:
python
'dir/\u2001/v.mp4' dto True schema_re False
'dir/\u2009/v.mp4' dto True schema_re False
'\x85' dto False schema_re False
'dir/\x85/v.mp4' dto True schema_re True
'\ufeff' dto False schema_re True
'dir/\ufeff/v.mp4' dto False schema_re False
ecmascript
"dir/ /v.mp4" false
"dir/ /v.mp4" false
"" true
"dir//v.mp4" true
"﻿" false
"dir/﻿/v.mp4" false

exec
/bin/zsh -lc "sed -n '1,120p' tests/core/rendering/fixtures/v1/result.json && nl -ba astrid/core/rendering/provenance.py | sed -n '130,235p' && nl -ba astrid/core/rendering/contracts.py | sed -n '210,340p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
{
  "schema_version": 1,
  "video": {
    "path": "outputs/visual.mp4",
    "profile": {
      "width": 1280,
      "height": 720,
      "fps_rational": [24, 1],
      "time_base": [1, 12288],
      "container": "mp4",
      "video_codec": "h264",
      "video_profile": null,
      "video_level": null,
      "pixel_format": "yuv420p",
      "audio_codec": null,
      "audio_sample_rate": null,
      "audio_channel_layout": null,
      "duration_tolerance": 1
    },
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "duration_frames": 1,
    "audio": "none",
    "attachments": {}
  },
  "backend_fragments": {},
  "audio_ownership": "none",
  "normalization": [],
  "logs": [],
  "metadata": {}
}
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
   154	            if isinstance(raw_profile, VideoArtifact):
   155	                # Reconstruct through the DTO so mutation cannot smuggle
   156	                # invalid paths, profiles, or attachments past validation.
   157	                profile = VideoArtifact.from_dict(
   158	                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
   159	                )
   160	                path = profile.path
   161	                record = _artifact_lineage(profile)
   162	            elif isinstance(raw_profile, Mapping):
   163	                # Already-emitted lineage record: re-validate and re-key by
   164	                # its (validated) path so emitted provenance round-trips.
   165	                record = _artifact_lineage_from_mapping(
   166	                    raw_profile, key=str(raw_profile.get("path", ""))
   167	                )
   168	                path = record["path"]
   169	            else:
   170	                raise TypeError(
   171	                    "sequence artifact_profiles entries must be VideoArtifacts "
   172	                    "or emitted lineage records"
   173	                )
   174	            if path in seen_paths:
   175	                raise ValueError(
   176	                    f"artifact_profiles sequence contains duplicate path "
   177	                    f"{path!r}"
   178	                )
   179	            seen_paths.add(path)
   180	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   181	            lineage.append(record)
   182	        if segments:
   183	            if len(lineage) != len(segments):
   184	                raise ValueError(
   185	                    f"artifact_profiles must record exactly one hashed lineage entry "
   186	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   187	                )
   188	        return lineage
   189	    raise TypeError("artifact_profiles must be an object or array")
   190	
   191	
   192	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   193	    raw_keys = set(raw)
   194	    allowed = {"profile", "sha256", "attachments", "path"}
   195	    unknown = sorted(raw_keys - allowed)
   196	    if unknown:
   197	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   198	    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
   199	    if missing:
   200	        raise ValueError(
   201	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   202	        )
   203	    if raw["sha256"] is None:
   204	        raise ValueError("artifact lineage sha256 is required and must not be null")
   205	    if not isinstance(raw["sha256"], str):
   206	        raise TypeError("artifact lineage sha256 must be a string")
   207	    if "path" in raw:
   208	        embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
   209	        if embedded != key:
   210	            raise ValueError(
   211	                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
   212	            )
   213	    profile = raw["profile"]
   214	    attachments: dict[str, Any] = {}
   215	    raw_attachments = raw["attachments"]
   216	    if raw_attachments is None:
   217	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   218	    if not isinstance(raw_attachments, Mapping):
   219	        raise TypeError("artifact lineage attachments must be an object")
   220	    for name, att in raw_attachments.items():
   221	        name = _require_string(name, "attachment name")
   222	        if isinstance(att, Attachment):
   223	            if att.name != name:
   224	                raise ValueError(
   225	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   226	                )
   227	            att = {
   228	                "path": att.path,
   229	                "kind": att.kind,
   230	                "sha256": att.sha256,
   231	            }
   232	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   233	        if att_unknown:
   234	            raise ValueError(
   235	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
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
   327	    # ECMAScript \s whitespace set, used so DTO and schema agree across
   328	    # languages (Python str.strip() would diverge on \u0085 and \uFEFF).
   329	    _WS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
   330	    if any(not part.strip(_WS) for part in raw_parts):
   331	        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
   332	    return raw
   333	
   334	
   335	def _relative_file_path(path: str | Path, workspace_root: str | Path, label: str) -> tuple[str, Path]:
   336	    root = Path(workspace_root).resolve()
   337	    candidate = Path(path)
   338	    if not candidate.is_absolute():
   339	        candidate = root / candidate
   340	    resolved = candidate.resolve(strict=True)

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'import json; from pathlib import Path; from astrid.core.rendering.provenance import _normalize_artifact_profiles; fixture=json.loads(Path(\"tests/core/rendering/fixtures/v1/result.json\").read_text()); base={\"profile\": fixture[\"video\"][\"profile\"], \"sha256\": fixture[\"video\"][\"sha256\"], \"attachments\": {}}; cases=[(\"missing\",dict(base)),(\"integer\",dict(base,path=123)),(\"none\",dict(base,path=None)),(\"empty\",dict(base,path=\"\"))];
for label,record in cases:
  try: print(label,\"ACCEPT\",_normalize_artifact_profiles([record],segments=[object()]))
  except Exception as e: print(label,\"REJECT\",type(e).__name__,str(e))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 115ms:
missing ACCEPT [{'path': '', 'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}]
integer ACCEPT [{'path': '123', 'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}]
none ACCEPT [{'path': 'None', 'profile': {'width': 1280, 'height': 720, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': None, 'video_level': None, 'pixel_format': 'yuv420p', 'audio_codec': None, 'audio_sample_rate': None, 'audio_channel_layout': None, 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}]
empty REJECT ValueError artifact path must not be empty

exec
/bin/zsh -lc "rg -n \"def assemble_provenance_v2|artifact_profiles\" astrid/core/rendering/provenance.py astrid/core/rendering -g '*.py' | head -160 && sed -n '300,470p' astrid/core/rendering/provenance.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/provenance.py:107:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:113:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:124:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:135:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:145:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:171:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:176:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:185:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:189:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:302:def assemble_provenance_v2(
astrid/core/rendering/provenance.py:309:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:360:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:361:            artifact_profiles,
astrid/core/rendering/provenance.py:107:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:113:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:124:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:135:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:145:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:171:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:176:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:185:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:189:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:302:def assemble_provenance_v2(
astrid/core/rendering/provenance.py:309:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:360:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:361:            artifact_profiles,
astrid/core/rendering/contracts.py:65:        "artifact_profiles",


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
        # V1-compatible segment projection: flat {engine, from, to} entries,
        # exactly the shape legacy consumers read from `segments`.
        "segments": legacy_segments,
        # Additive normalized v2 segment records; never overwrite v1 fields.
        "segments_v2": normalized_segments,
        "artifact_profiles": _normalize_artifact_profiles(
            artifact_profiles,
            segments=normalized_plan.segments,
        ),
        "audio_ownership": _normalize_audio_ownership(audio_ownership),
        "normalization": normalized_normalization,
        "finalizer": normalized_plan.finalizer.to_dict(),
        "attachments": _normalize_attachments(attachments),
        "backend_fragments": validate_backend_fragments(backend_fragments),
    }
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

exec
/bin/zsh -lc "tail -n 80 .oracle/checkins/batch-1-r10.md && sed -n '1,220p' .oracle/checkins/batch-1-r11.md 2>/dev/null" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
Reading additional input from stdin...
2026-08-12T03:03:45.380438Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:03:45.380472Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:03:45.380477Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3ed-072e-73f3-859f-549ea04ccb84
--------
user
# Megado Checkpoint — Batch 1 eleventh re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1..-r10 (3 each; -r4 had 4). Eleventh rework
committed as `6afd558` (prior head 6acd4be). Incremental diff at
/tmp/batch1-r11.diff.

## How each of your 2 re-review10 issues was addressed (host-implemented)

1. **Multi-segment lineage cannot round-trip** →
   - Sequence form now accepts BOTH VideoArtifacts and already-emitted
     lineage records (dicts); records are re-validated via
     `_artifact_lineage_from_mapping` and re-keyed by their validated path.
   - Round-trip test: emitted `artifact_profiles` re-passed reproduces the
     identical output.
2. **workspacePath cross-language whitespace** →
   - DTO and schema now share an EXPLICIT ECMAScript `\s` whitespace class
     (space, tab, LF, CR, FF, VT, NBSP, and Unicode spaces through \u3000,
     \ufeff) instead of Python `str.strip()` semantics — so Python and
     non-Python validators agree on `\u0085` (accepted by both) and
     `\uFEFF` (rejected by both) components.
   - Cross-checked 19 DTO-vs-schema cases including \u0085/\uFEFF/\u00a0: 0
     mismatches.

## Evidence

- Incremental diff: /tmp/batch1-r11.diff (7 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 11 review rounds. If
sound and STABLE, say exactly `PASS` so Batch 2 may begin.
codex
I’m using the repository’s context-mining and subagent-launcher guidance for this checkpoint: I’ll keep the main review focused, delegate independent scrutiny of the two fixes, then personally verify the incremental diff and relevant tests. I’ll keep the final response strictly to `PASS` if no concrete issue survives review.
codex
I’m also applying Astrid’s core repository skill, since this is a review inside the Astrid project; it governs how I inspect project state without mutating it.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md astrid/packs/_core/skill/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,360p' astrid/packs/_core/skill/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
     772 astrid/packs/_core/skill/SKILL.md
    1088 total
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

codex
Two concrete gaps have reproduced despite the green suite: malformed sequence lineage records can emit an empty/coerced path, and the “explicit” Python whitespace set treats `\u2000-\u200a` as three literal strip characters rather than a range. I’m checking whether either is contained elsewhere before finalizing the gate.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/test_contracts.py::test_provenance_rejects_spoofed_artifact_lineage tests/core/rendering/test_schema_roundtrip.py::test_adversarial_schema_and_dto_parity' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 594ms:
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
/bin/zsh -lc "git diff --no-ext-diff 6acd4be 6afd558 | shasum -a 256 && shasum -a 256 /tmp/batch1-r11.diff && sed -n '1,80p' /tmp/batch1-r11.diff && tail -n 80 /tmp/batch1-r11.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
fa1ef4c05c06054e9d745902aa5e1eb7a6a2550470280c9ea126fa4dc4ae69c5  -
fa1ef4c05c06054e9d745902aa5e1eb7a6a2550470280c9ea126fa4dc4ae69c5  /tmp/batch1-r11.diff
diff --git a/.oracle/checkins/batch-1-r10.md b/.oracle/checkins/batch-1-r10.md
new file mode 100644
index 0000000..3a1e8bc
--- /dev/null
+++ b/.oracle/checkins/batch-1-r10.md
@@ -0,0 +1,5755 @@
+Reading additional input from stdin...
+2026-08-12T02:53:35.069924Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T02:53:35.070866Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T02:53:35.070871Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff3e3-b68c-7d73-9011-1311018369ea
+--------
+user
+# Megado Checkpoint — Batch 1 tenth re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-1.md (9), -r1..-r9 (3 each; -r4 had 4). Tenth rework
+committed as `6acd4be` (prior head 788501c). Incremental diff at
+/tmp/batch1-r10.diff.
+
+## How each of your 2 re-review9 issues was addressed (host-implemented)
+
+1. **VideoArtifact reconstruction bypassable** →
+   - Sequence entries now reconstructed through `VideoArtifact.from_dict` at
+     the boundary — a mutated artifact with smuggled `path="../escape.mp4"`
+     is rejected (regression test added).
+   - Mapping-form VideoArtifacts likewise reconstructed.
+   - Lineage records always emit the VALIDATED workspace path (`key`), never
+     the raw value — integer or mutated paths cannot leak into output.
+2. **workspacePath still not DTO-equivalent** →
+   - Whitespace-only-component checks now use `\s` (covers `\v`, `\f`, and
+     Unicode spaces), and a leading whitespace-only component (`" /v.mp4"`)
+     is rejected via a dedicated lookahead.
+   - Cross-checked 16 DTO-vs-schema cases: 0 mismatches (includes `" /v.mp4"`,
+     `dir/\v/v.mp4`, `dir/\f/v.mp4`, leading/trailing spaces, newlines,
+     backslashes, `//`, `..`, drive letters, absolute paths).
+
+## Evidence
+
+- Incremental diff: /tmp/batch1-r10.diff (5 files)
+- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
+  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
+  failures), 3 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Batch 1 has passed 10 review rounds. The
+contract is heavily validated and language-neutral. If sound and STABLE, say
+exactly `PASS` so Batch 2 may begin.
+warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
+codex
+I’m using the `megado` checkpoint guidance and the repository’s context-minimizing workflow. I’ll inspect only the incremental commit/diff and targeted contract tests, then independently verify the two claimed fixes before returning the binary verdict.
+exec
+/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
     },
     "portableName": {
       "type": "string",
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 88d822e..6c40136 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -477,18 +477,22 @@ for every renderer invocation. Planner and finalizer records carry the same
 alias/override/trust/support evidence as renderer records. Rendered artifacts
 are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
 hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
-sequence form (one VideoArtifact per segment); single-segment plans may use a
-path-keyed mapping. Every record carries its `path`, `profile`, a validated
-64-hex string `sha256`, and `attachments` — each attachment `{path, kind,
-sha256}` with a workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and
-globally unique names across all segment artifacts. All plan, artifact, and
-attachment values are reconstructed through their DTO validators at the
-provenance boundary (mutated frozen instances cannot bypass validation);
-duplicate paths, duplicate attachment names, path escapes, invalid kinds,
-profile-only entries, null/malformed hashes, and cardinality mismatches are
-rejected. All JSON Schema patterns are language-neutral (ECMAScript-valid;
-no Python-only anchors). Replay can verify rendered outputs byte-for-byte.
-`input_hashes` describe inputs only, never rendered outputs.
+sequence form (one VideoArtifact or emitted lineage record per segment, in
+segment order); single-segment plans may use a path-keyed mapping. Emitted
+lineage records round-trip (re-passing them validates identically). Every
+record carries its `path`, `profile`, a validated 64-hex string `sha256`, and
+`attachments` — each attachment `{path, kind, sha256}` with a workspace-relative
+path, kind matching `[a-z][a-z0-9-]*`, and globally unique names across all
+segment artifacts. All plan, artifact, and attachment values are reconstructed
+through their DTO validators at the provenance boundary (mutated frozen
+instances cannot bypass validation); duplicate paths, duplicate attachment
+names, path escapes, invalid kinds, profile-only entries, null/malformed
+hashes, and cardinality mismatches are rejected. All JSON Schema patterns are
+language-neutral (ECMAScript-valid; no Python-only anchors), and workspacePath
+uses an explicit ECMAScript `\s` whitespace class shared with the DTO so
+Python and non-Python validators agree on whitespace-only components. Replay
+can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
+only, never rendered outputs.
 
 `engine` is only the legacy request projection. The `segments` key keeps the
 V1-compatible flat projection: one `{engine, from, to}` entry per segment,
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 3a87be3..14ecc19 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -977,6 +977,32 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
             plan=_plan(),
             artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
         )
+    # Emitted lineage records round-trip: re-passing the emitted sequence
+    # (dictionary records) validates and reproduces the same output.
+    first = assemble_provenance_v2(
+        **base,
+        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+        artifact_profiles=[
+            VideoArtifact(
+                path="outputs/a.mp4",
+                profile=_profile(audio=False),
+                sha256=SHA_B,
+                duration_frames=24,
+            ),
+            VideoArtifact(
+                path="outputs/b.mp4",
+                profile=_profile(audio=False),
+                sha256=SHA_C,
+                duration_frames=24,
+            ),
+        ],
+    )
+    second = assemble_provenance_v2(
+        **base,
+        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+        artifact_profiles=first["artifact_profiles"],
+    )
+    assert second["artifact_profiles"] == first["artifact_profiles"]
     with pytest.raises(ValueError, match="duplicate path"):
         assemble_provenance_v2(
             **base,

codex
Because this is explicitly a Megado checkpoint, I’m now applying Megado’s oracle gate rules as well: concrete contract failures block the batch even when the existing acceptance suite remains green.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,360p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     178 /Users/peteromalley/.codex/skills/megado/SKILL.md
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

Applying Megado’s formal oracle checkpoint discipline to the read-only Batch 1 re-review.
  ✓ Inspect the exact 6acd4be..6afd558 incremental diff and prior issues
  → Independently review lineage and cross-language whitespace fixes
  ✓ Reproduce suspected contract edge cases without modifying the worktree
  • Return PASS or only concrete blocking issues
exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python3 -c 'import copy,json; from pathlib import Path; import jsonschema; from astrid.core.rendering.contracts import parse_wire_result; root=Path(\"astrid/core/rendering/schemas/v1\"); schema=json.loads((root/\"result.json\").read_text()); fixture=json.loads(Path(\"tests/core/rendering/fixtures/v1/result.json\").read_text()); v=jsonschema.Draft7Validator(schema); cases=[\"dir/\\u2001/v.mp4\",\"\\ufeff\",\"\\u0085\"];
for s in cases:
 p=copy.deepcopy(fixture); p[\"video\"][\"path\"]=s
 try: parse_wire_result(p); dto=True
 except Exception: dto=False
 print(ascii(s),\"dto\",dto,\"draft7_python\",v.is_valid(p))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 153ms:
'dir/\u2001/v.mp4' dto True draft7_python False
'\ufeff' dto False draft7_python True
'\x85' dto False draft7_python False

collab: Wait
collab: Wait
codex
All three independent reviews converged on the same blockers, and the direct probes reproduced them against the real DTO/schema paths. I’m closing the checkpoint as a rework verdict.
The checkpoint cannot pass: both fixes have reproducible contract violations not covered by the green tests.
  ✓ Inspect the exact 6acd4be..6afd558 incremental diff and prior issues
  ✓ Independently review lineage and cross-language whitespace fixes
  ✓ Reproduce suspected contract edge cases without modifying the worktree
  ✓ Return PASS or only concrete blocking issues
codex
1. Sequence lineage mappings still accept missing or non-string paths. Missing `path` emits `""`; `None` and `123` become `"None"` and `"123"` due `str()` coercion, violating the validated workspace-path contract. [provenance.py:162](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:162)

2. The Python whitespace range is malformed: `str.strip("\u2000-\u200a")` treats `-` literally. Thus `"dir/\u2001/v.mp4"` is DTO-accepted/schema-rejected, while `"dir/-/v.mp4"` is DTO-rejected/schema-accepted. [contracts.py:329](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:329)

3. Single-component paths retain language-dependent semantics: `"\u0085"` is DTO-rejected but ECMAScript-accepted, while `"\uFEFF"` is DTO-rejected but accepted by Python’s Draft7 schema validator because the schemas still use `\S`. [contracts.py:222](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:222) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68)
tokens used
116,348
1. Sequence lineage mappings still accept missing or non-string paths. Missing `path` emits `""`; `None` and `123` become `"None"` and `"123"` due `str()` coercion, violating the validated workspace-path contract. [provenance.py:162](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:162)

2. The Python whitespace range is malformed: `str.strip("\u2000-\u200a")` treats `-` literally. Thus `"dir/\u2001/v.mp4"` is DTO-accepted/schema-rejected, while `"dir/-/v.mp4"` is DTO-rejected/schema-accepted. [contracts.py:329](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:329)

3. Single-component paths retain language-dependent semantics: `"\u0085"` is DTO-rejected but ECMAScript-accepted, while `"\uFEFF"` is DTO-rejected but accepted by Python’s Draft7 schema validator because the schemas still use `\S`. [contracts.py:222](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:222) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68)
