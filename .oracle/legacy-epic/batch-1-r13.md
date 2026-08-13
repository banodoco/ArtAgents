Reading additional input from stdin...
2026-08-12T03:23:59.156769Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:23:59.156808Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:23:59.156813Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3ff-8c85-7351-b2ab-685c48eef09f
--------
user
# Megado Checkpoint — Batch 1 thirteenth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1..-r12 (3 each; -r4 had 4). Thirteenth
rework committed as `670d5f8` (prior head 8e4f640). Incremental diff at
/tmp/batch1-r13.diff.

## How each of your 2 re-review12 issues was addressed (host-implemented)

1. **Sequence path check used Python strip** →
   - The emitted-lineage `raw_path.strip()` check now uses the shared
     `_ECMA_WHITESPACE` constant, so a valid ECMA path like `"\u0085"`
     emitted from a VideoArtifact replays identically (round-trip intact).
2. **Mapping form coerced non-string paths** →
   - Mapping KEYS must be strings (`isinstance` check, no `str()` coercion).
   - Embedded `path` in lineage records must be a string (TypeError, not
     coercion) and still must equal the map key.
   - Tests: numeric embedded path rejected, non-string mapping key rejected.

## Evidence

- Incremental diff: /tmp/batch1-r13.diff (3 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 13 review rounds. If
sound and STABLE, say exactly `PASS` so Batch 2 may begin.
codex
I’m using the `megado` skill because this is a formal Megado checkpoint. I’ll audit the incremental diff and the affected contract/tests read-only, then return only the requested binary verdict.
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

2026-08-12T03:24:22.700063Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:24:22.700300Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:24:22.700311Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:24:28.584198Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:24:28.584475Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:24:28.584489Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "sed -n '1,260p' /tmp/batch1-r13.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
diff --git a/.oracle/checkins/batch-1-r12.md b/.oracle/checkins/batch-1-r12.md
new file mode 100644
index 0000000..be7b1dd
--- /dev/null
+++ b/.oracle/checkins/batch-1-r12.md
@@ -0,0 +1,8482 @@
+Reading additional input from stdin...
+2026-08-12T03:13:20.184284Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T03:13:20.184311Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T03:13:20.184316Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff3f5-cc9b-7011-b9ef-e47dc0ce650c
+--------
+user
+# Megado Checkpoint — Batch 1 twelfth re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-1.md (9), -r1..-r11 (3 each; -r4 had 4). Twelfth rework
+committed as `8e4f640` (prior head 6afd558). Incremental diff at
+/tmp/batch1-r12.diff.
+
+## How each of your 3 re-review11 issues was addressed (host-implemented)
+
+1. **Sequence lineage missing/non-string paths** →
+   - Emitted-lineage records MUST carry a non-empty string `path`; missing,
+     `None`, and numeric paths are rejected (no `str()` coercion). Test added.
+2. **Python whitespace range malformed** →
+   - `_ECMA_WHITESPACE` module-level constant spells every character
+     explicitly (no `\u2000-\u200a` range); DTO `strip(_ECMA_WHITESPACE)`
+     now rejects `\u2001` correctly. Test added.
+3. **Single-component language-dependent whitespace** →
+   - `_require_string` emptiness check now uses `_ECMA_WHITESPACE`.
+   - Every standalone `\S` in all 8 schema files replaced with the explicit
+     ECMA-complement class `[^ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028
+     \u2029\u202f\u205f\u3000\ufeff]`; `[\s\S]` (any char) preserved.
+   - Cross-checked 21 workspacePath cases including single-component
+     `\u0085`/`\uFEFF` and `\u2001`: 0 mismatches.
+
+## Evidence
+
+- Incremental diff: /tmp/batch1-r12.diff (13 files)
+- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
+  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
+  failures), 3 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Batch 1 has passed 12 review rounds. If
+sound and STABLE, say exactly `PASS` so Batch 2 may begin.
+codex
+I’m using the Astrid core skill for this repository’s review protocol and the context-mining/subagent skill required by its AGENTS.md. I’ll keep the worktree read-only, inspect the incremental commit and relevant surrounding code/tests, and return only the binary verdict or concrete issues.
+exec
+/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
+---
+name: "astrid"
+short_description: "Astrid — file-based toolkit for agents to make video, image, and audio art alongside a human."
+description: "Use for the Astrid repo: a file-based toolkit for agents to make art and creative work alongside a human. Video edits, generative timelines, image/audio/video understanding and generation — all behind one CLI gateway."
+---
+
+# Astrid
+
+Astrid is a file-based toolkit for making video, image, and audio art alongside
+a human. `python3 -m astrid` is the only executable gateway.
+
+## When in doubt, run `astrid next`
+
+`astrid next` is the universal port-of-call. **It always prints exactly one
+legal action to take, regardless of where you are.** Type it whenever you're
+lost, when you forget what you were doing, or when you need to know what
+to do *first*:
+
+| Where you are | What `astrid next` tells you |
+|---|---|
+| No session bound | One legal bootstrap action, usually `astrid attach <slug>` or `astrid projects create <slug>` |
+| Session bound, no active run | `astrid start <orchestrator-id> --project <slug>` (suggests top orchestrators) |
+| In a run, mid-step | The exact `run: …` command or `astrid ack …` template to type |
+| Run rejected by verifier | The rejection reason + the retry command |
+| Run complete | "Run complete. Nothing to do." |
+
+Run it without flags. It derives the project from the bound session; if
+nothing is bound, it still prints one legal bootstrap action. **You don't need
+to remember which other verb to run** — `astrid next` is always the answer.
+
+For deeper context (recent events, run state, inbox count) `astrid status`
+remains the read-side breadcrumb; `next` is the action verb.
+
+## Start Here
+
+Astrid is session-gated. From the repository root, the canonical entry is
+`astrid next` (see above). When you need detail beyond the next action,
+`astrid status` prints the session breadcrumb and the exact recovery action.
+
+```bash
+git status --short
+python3 -m astrid --help
+python3 -m astrid next     # always-correct next action
+python3 -m astrid status   # detail breadcrumb when you need it
+```
+
+If status says `no session bound`, attach before running doctor, registry
+list/search/inspect, executor, orchestrator, element, or task-mode commands.
+The only legal unbound commands are help/version, `status`, `next`, `attach`,
+`packs ...`, `projects ls`, `projects create`, `projects default`,
+`sessions ls`, and `sessions takeover`. After binding, use `status` when you
+need to re-orient, not before every command.
+
+```bash
+python3 -m astrid attach [<project>] [--default] [--timeline <slug>] [--session <id>] [--as agent:<id>]
+python3 -m astrid status
+```
+
+Only after a session is bound should you run the usual registry and setup
+checks:
+
+```bash
+python3 -m astrid doctor
+python3 -m astrid orchestrators list
+python3 -m astrid executors list
+python3 -m astrid elements list
+python3 -m astrid setup
+```
+
+`setup` is dry-run by default; pass `--apply` to mutate.
+
+## Projects
+
+A project is the durable workspace for timelines, experiments, task runs,
+events, and generated artifacts. Every executor, orchestrator, scratch run,
+SDK generation, and timeline creation requires either an attached session or
+an explicit `--project <slug>`. This includes read-only executors and dry runs.
+Configured defaults are attach-time conveniences; they are never silently
+selected when a capability runs.
+
+Use `status` first: when no session is bound, it lists discovered projects and
+prints the exact attach and default-project commands to run.
+
+```bash
+python3 -m astrid status
+python3 -m astrid projects ls                   # names, descriptions, activity
+python3 -m astrid projects default
+python3 -m astrid projects default <slug>
+python3 -m astrid projects select <slug>
+python3 -m astrid attach [<project>] [--default]
+python3 -m astrid projects create <slug> --description "..." --attach
+python3 -m astrid timelines create <timeline> --project <slug> --default
+```
+
+If `attach` has no project argument, it uses the configured default project.
+That is an explicit attach action: the default is never selected merely because
+an executor, orchestrator, or timeline command was invoked.
+Use `projects create` only when the work needs a new durable project, not just a
+new run inside an existing project.
+
+## Choose The Mode
+
+- Use an **executor** for one concrete, independently runnable unit of work.
+- Use an **orchestrator** for a workflow that coordinates executors or child orchestrators.
+- Use an **element** for a reusable render building block: effect, animation, or transition.
+- Use task-mode verbs to continue a started plan: `status`, `next`, then the exact command or `ack` that `next` prints.
+- When creating new capability, search and compose existing tools first; only add new executors/elements/orchestrators for real gaps.
+
+## Pack-Specific Guidance
+
+This `_core` skill is the baseline. Custom packs can add their own guidance at
+`astrid/packs/<pack>/skill/SKILL.md`. When a task is clearly about one pack,
+read that pack skill after `_core` and before editing or running that pack's
+tools.
+
+To find every Astrid skill and what it does, attach to a project first, then
+list skills. The table shows each installable pack skill, its short
+description, and whether it is installed in Claude Code, Codex, and Hermes.
+Use `--json` when another agent or script needs to consume the list.
+
+```bash
+python3 -m astrid status
+python3 -m astrid attach [<project>]
+python3 -m astrid skills list
+python3 -m astrid skills list --json
+```
+
+If you create a custom pack whose conventions agents need to remember, add
+`astrid/packs/<pack>/skill/SKILL.md` and follow `docs/guides/skills-install.md`.
+
+## Shared Knowledge With Hivemind
+
+Hivemind is Astrid's default shared knowledge pack. Use `hivemind.search`
+before researching community best practices, model behavior, settings, known
+failures, or workflow precedents. Use `hivemind.get_item` when a search result
+needs its full body or citation context.
+
+Astrid project files remain the source of truth for raw runs, experiment
+reviews, and `conclusions.json`. Hivemind is the cross-project publication and
+retrieval layer for generalizable learnings:
+
+1. Record observations and evidence-backed inferences locally.
+2. Search Hivemind for an existing equivalent learning.
+3. Contribute a concise experiment report as a resource.
+4. Submit the reusable learning as a distillation citing that resource.
+5. Preserve the returned Hivemind IDs beside the local experiment.
+
+Hivemind writes are public publication, including pending distillations. Never
+publish automatically: dry-run or preview the payload, remove private paths,
+prompts, media, and URLs, and obtain explicit user confirmation before calling
+`hivemind.contribute`. If Hivemind is unavailable, install its pack and shared
+skill:
+
+```bash
+python3 -m astrid packs install https://github.com/banodoco/hivemind.git
+python3 -m astrid skills install hivemind --harness all
+```
+
+Read the Hivemind pack skill for its search, citation, contribution, and
+curation rules before using those executors.
+
+## Run A Tool
+
+Find an id before you run anything.
+
+```bash
+python3 -m astrid [executors|orchestrators|elements] list
+python3 -m astrid [executors|orchestrators|elements] search <terms>
+```
+
+If you don't know which tool to use, run `python3 -m astrid <kind> search
+<terms>` first. Do not guess from id alone.
+
+Inspect to see inputs, outputs, intent, folder root, and the relevant
+`STAGE.md`.
+
+```bash
+python3 -m astrid [executors|orchestrators|elements] inspect <id> --json
+```
+
+Read only that one `STAGE.md`; it is the source of truth for invocation details.
+Then run:
+
+```bash
+python3 -m astrid [executors|orchestrators] run <id> --project <slug> -- <args>
+```
+
+## Continue A Task Run
+
+Task lists are orchestrator plans tracked inside a project. Do not freelance:
+`next` is the control surface.
+
+```bash
+python3 -m astrid status
+python3 -m astrid next --project <slug>
+```
+

exec
/bin/zsh -lc "rg --files .oracle | sort | sed -n '1,240p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/baseline.md
.oracle/briefs/01-pack-discovery-trust.md
.oracle/briefs/02-schema-registry.md
.oracle/briefs/03-run-ownership-facade.md
.oracle/briefs/04-provenance-consumers.md
.oracle/briefs/05-hybrid-planner-canvas.md
.oracle/briefs/06-ffmpeg-media-audio.md
.oracle/briefs/07-serving-remotion-lifecycle.md
.oracle/briefs/08-callsites.md
.oracle/briefs/09-parity-fixtures-tests-ci.md
.oracle/briefs/10-sdk-cli-conventions.md
.oracle/briefs/11-errors-asset-cache-output.md
.oracle/briefs/12-pack-schema-permissions.md
.oracle/briefs/13-single-ledger-facade.md
.oracle/briefs/14-dynamic-outputs.md
.oracle/briefs/15-audio-semantics.md
.oracle/briefs/16-registry-lock.md
.oracle/briefs/batch-1-r1-t1.1.md
.oracle/briefs/batch-1-r1-t1.2.md
.oracle/briefs/batch-1-r1-t1.3.md
.oracle/briefs/batch-1-r1-t1.4.md
.oracle/briefs/batch-1-r2-t1.1.md
.oracle/briefs/batch-1-r2-t1.2.md
.oracle/briefs/batch-1-t1.1.md
.oracle/briefs/batch-1-t1.2.md
.oracle/briefs/batch-1-t1.3.md
.oracle/briefs/batch-1-t1.4.md
.oracle/briefs/batch-1-t1.5.md
.oracle/checkins/batch-1-r1.md
.oracle/checkins/batch-1-r10.md
.oracle/checkins/batch-1-r11.md
.oracle/checkins/batch-1-r12.md
.oracle/checkins/batch-1-r13.md
.oracle/checkins/batch-1-r2.md
.oracle/checkins/batch-1-r3.md
.oracle/checkins/batch-1-r4.md
.oracle/checkins/batch-1-r5.md
.oracle/checkins/batch-1-r6.md
.oracle/checkins/batch-1-r7.md
.oracle/checkins/batch-1-r8.md
.oracle/checkins/batch-1-r9.md
.oracle/checkins/batch-1.md
.oracle/findings/01-pack-discovery-trust.meta.json
.oracle/findings/01-pack-discovery-trust.txt
.oracle/findings/02-schema-registry.meta.json
.oracle/findings/02-schema-registry.txt
.oracle/findings/03-run-ownership-facade.meta.json
.oracle/findings/03-run-ownership-facade.txt
.oracle/findings/04-provenance-consumers.meta.json
.oracle/findings/04-provenance-consumers.txt
.oracle/findings/05-hybrid-planner-canvas.meta.json
.oracle/findings/05-hybrid-planner-canvas.txt
.oracle/findings/06-ffmpeg-media-audio.meta.json
.oracle/findings/06-ffmpeg-media-audio.txt
.oracle/findings/07-serving-remotion-lifecycle.meta.json
.oracle/findings/07-serving-remotion-lifecycle.txt
.oracle/findings/08-callsites.meta.json
.oracle/findings/08-callsites.txt
.oracle/findings/09-parity-fixtures-tests-ci.meta.json
.oracle/findings/09-parity-fixtures-tests-ci.txt
.oracle/findings/10-sdk-cli-conventions.meta.json
.oracle/findings/10-sdk-cli-conventions.txt
.oracle/findings/11-errors-asset-cache-output.meta.json
.oracle/findings/11-errors-asset-cache-output.txt
.oracle/findings/12-pack-schema-permissions.meta.json
.oracle/findings/12-pack-schema-permissions.txt
.oracle/findings/13-single-ledger-facade.meta.json
.oracle/findings/13-single-ledger-facade.txt
.oracle/findings/14-dynamic-outputs.meta.json
.oracle/findings/14-dynamic-outputs.txt
.oracle/findings/15-audio-semantics.meta.json
.oracle/findings/15-audio-semantics.txt
.oracle/findings/16-registry-lock.meta.json
.oracle/findings/16-registry-lock.txt
.oracle/findings/_report.json
.oracle/plan-v1.txt
.oracle/plan.md
.oracle/tasklist.md

exec
/bin/zsh -lc 'git status --short && git log -3 --oneline --decorate' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r13.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
670d5f8 (HEAD -> oracle-run) batch1-rework13: oracle re-review12 issues 1-2 (ECMA whitespace in sequence path check, no str() coercion of mapping keys or embedded paths)
8e4f640 batch1-rework12: oracle re-review11 issues 1-3 (strict string path in lineage records, explicit ECMA whitespace chars no range, ECMA-complement non-whitespace class in all schemas)
6afd558 batch1-rework11: oracle re-review10 issues 1-2 (lineage round-trip via dict-record acceptance, explicit ECMAScript whitespace class shared DTO+schema)

exec
/bin/zsh -lc "rg -n '"'^diff --git|''^@@'"' /tmp/batch1-r13.diff | tail -80 && git diff --stat 8e4f640..670d5f8 && git diff --name-status 8e4f640..670d5f8" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
1:diff --git a/.oracle/checkins/batch-1-r12.md b/.oracle/checkins/batch-1-r12.md
6:@@ -0,0 +1,8482 @@
8489:diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
8493:@@ -13,6 +13,7 @@ from .contracts import (
8501:@@ -116,8 +117,11 @@ def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
8515:@@ -163,7 +167,7 @@ def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
8524:@@ -210,7 +214,9 @@ def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[
8535:diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
8539:@@ -983,6 +983,26 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r12.md        | 8482 ++++++++++++++++++++++++++++++++
 astrid/core/rendering/provenance.py    |   14 +-
 tests/core/rendering/test_contracts.py |   20 +
 3 files changed, 8512 insertions(+), 4 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-1-r12.md
M	astrid/core/rendering/provenance.py
M	tests/core/rendering/test_contracts.py

exec
/bin/zsh -lc "sed -n '8480,8585p' /tmp/batch1-r13.diff && nl -ba astrid/core/rendering/provenance.py | sed -n '1,270p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '900,1040p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
+codex
+1. [provenance.py:166](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:166) uses Python’s default `raw_path.strip()`. A valid ECMA path `"\u0085"` emits successfully from `VideoArtifact` but fails when that emitted lineage is replayed, breaking the round-trip guarantee.
+
+2. Mapping-form lineage still coerces non-string paths via `str()` at [provenance.py:119](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:119) and [provenance.py:213](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:213). For example, `{"123": {"path": 123, ...}}` is accepted and emits `"123"`, contradicting the no-coercion contract. The new test’s missing-path entry raises first, so its numeric entry is never exercised.
+tokens used
+339,840
+1. [provenance.py:166](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:166) uses Python’s default `raw_path.strip()`. A valid ECMA path `"\u0085"` emits successfully from `VideoArtifact` but fails when that emitted lineage is replayed, breaking the round-trip guarantee.
+
+2. Mapping-form lineage still coerces non-string paths via `str()` at [provenance.py:119](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:119) and [provenance.py:213](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:213). For example, `{"123": {"path": 123, ...}}` is accepted and emits `"123"`, contradicting the no-coercion contract. The new test’s missing-path entry raises first, so its numeric entry is never exercised.
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index 6f6ebc3..7e16ede 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -13,6 +13,7 @@ from .contracts import (
     PROVENANCE_V1_ALWAYS_KEYS,
     PROVENANCE_V1_COMPATIBILITY_KEYS,
     PROVENANCE_V2_CORE_KEYS,
+    _ECMA_WHITESPACE,
     Attachment,
     AudioOwnership,
     RenderPlan,
@@ -116,8 +117,11 @@ def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
         result: dict[str, Any] = {}
         seen_attachment_names: set[str] = set()
         for key, profile in value.items():
-            path = _require_string(str(key), "artifact key")
-            path = _require_workspace_relative_path(path, "artifact key")
+            if not isinstance(key, str):
+                raise TypeError(
+                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
+                )
+            path = _require_workspace_relative_path(key, "artifact key")
             if isinstance(profile, VideoArtifact):
                 if path != profile.path:
                     raise ValueError(
@@ -163,7 +167,7 @@ def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
                 # Already-emitted lineage record: re-validate and re-key by
                 # its (validated) path so emitted provenance round-trips.
                 raw_path = raw_profile.get("path")
-                if not isinstance(raw_path, str) or not raw_path.strip():
+                if not isinstance(raw_path, str) or not raw_path.strip(_ECMA_WHITESPACE):
                     raise ValueError(
                         "emitted lineage record must carry a non-empty string path"
                     )
@@ -210,7 +214,9 @@ def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[
     if not isinstance(raw["sha256"], str):
         raise TypeError("artifact lineage sha256 must be a string")
     if "path" in raw:
-        embedded = _require_workspace_relative_path(str(raw["path"]), "artifact path")
+        if not isinstance(raw["path"], str):
+            raise TypeError("artifact lineage path must be a string")
+        embedded = _require_workspace_relative_path(raw["path"], "artifact path")
         if embedded != key:
             raise ValueError(
                 f"artifact lineage path {embedded!r} must equal its map key {key!r}"
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index b0dea2c..aa60712 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -983,6 +983,26 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
         )
     with pytest.raises(ValueError, match="whitespace-only path components"):
         _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
+    # Mapping-form records must not coerce non-string embedded paths.
+    with pytest.raises(TypeError, match="artifact lineage path must be a string"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={
+                "123": {
+                    "path": 123,
+                    "profile": _profile().to_dict(),
+                    "sha256": SHA_B,
+                    "attachments": {},
+                }
+            },
+        )
+    with pytest.raises(TypeError, match="mapping keys must be strings"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(),
+            artifact_profiles={123: {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
+        )
     with pytest.raises(ValueError, match="workspace path"):
         assemble_provenance_v2(
             **base,
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
    16	    _ECMA_WHITESPACE,
    17	    Attachment,
    18	    AudioOwnership,
    19	    RenderPlan,
    20	    RenderProfile,
    21	    RenderSegment,
    22	    VideoArtifact,
    23	    _json_safe_mapping,
    24	    _require_sha256,
    25	    _require_string,
    26	    _require_workspace_relative_path,
    27	    _validate_backend_fragments,
    28	)
    29	
    30	
    31	PROVENANCE_SCHEMA_VERSION = 2
    32	CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)
    33	
    34	
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
    63	            Attachment.from_dict(
    64	                {
    65	                    "name": raw_attachment.name,
    66	                    "path": raw_attachment.path,
    67	                    "kind": raw_attachment.kind,
    68	                    "sha256": raw_attachment.sha256,
    69	                }
    70	            )
    71	            if isinstance(raw_attachment, Attachment)
    72	            else Attachment.from_dict(raw_attachment)
    73	        )
    74	        if attachment.name != name:
    75	            raise ValueError(
    76	                f"attachment key {name!r} must match attachment.name {attachment.name!r}"
    77	            )
    78	        if name in result:
    79	            raise ValueError(f"duplicate attachment name: {name}")
    80	        result[name] = attachment.to_dict()
    81	    return result
    82	
    83	
    84	def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
    85	    """Derive one v1 segment projection from an authoritative v2 segment."""
    86	
    87	    numerator, denominator = segment.window.fps_rational
    88	    return {
    89	        "engine": segment.renderer.id.rsplit(".", 1)[-1],
    90	        "from": segment.window.start_frame * denominator / numerator,
    91	        "to": segment.window.end_frame * denominator / numerator,
    92	    }
    93	
    94	
    95	def _reject_duplicate_attachment_names(
    96	    lineage: Mapping[str, Any],
    97	    seen: set[str],
    98	) -> None:
    99	    """Reject attachment names repeated across segment artifacts."""
   100	    for name in (lineage.get("attachments") or {}):
   101	        if name in seen:
   102	            raise ValueError(
   103	                f"duplicate attachment name {name!r} across segment artifacts"
   104	            )
   105	        seen.add(name)
   106	
   107	
   108	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
   109	    if value is None:
   110	        value = {}
   111	    if isinstance(value, Mapping):
   112	        if segments and len(segments) > 1:
   113	            raise TypeError(
   114	                "mapping-form artifact_profiles is unordered; use sequence form "
   115	                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
   116	            )
   117	        result: dict[str, Any] = {}
   118	        seen_attachment_names: set[str] = set()
   119	        for key, profile in value.items():
   120	            if not isinstance(key, str):
   121	                raise TypeError(
   122	                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
   123	                )
   124	            path = _require_workspace_relative_path(key, "artifact key")
   125	            if isinstance(profile, VideoArtifact):
   126	                if path != profile.path:
   127	                    raise ValueError(
   128	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
   129	                        f"{profile.path!r}"
   130	                    )
   131	                profile = VideoArtifact.from_dict(
   132	                    _json_safe_mapping(profile.to_dict(), label="artifact")
   133	                )
   134	                lineage = _artifact_lineage(profile)
   135	            elif isinstance(profile, Mapping):
   136	                lineage = _artifact_lineage_from_mapping(profile, key=path)
   137	            else:
   138	                raise TypeError(
   139	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   140	                    "hashed lineage record {profile, sha256, attachments}; "
   141	                    "profile-only entries carry no output hash"
   142	                )
   143	            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
   144	            result[path] = lineage
   145	        # A positive plan must record exactly one hashed artifact per segment.
   146	        if segments:
   147	            if len(result) != len(segments):
   148	                raise ValueError(
   149	                    f"artifact_profiles must record exactly one hashed lineage entry "
   150	                    f"per segment: expected {len(segments)}, got {len(result)}"
   151	                )
   152	        return result
   153	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   154	        lineage: list[dict[str, Any]] = []
   155	        seen_paths: set[str] = set()
   156	        seen_attachment_names: set[str] = set()
   157	        for raw_profile in value:
   158	            if isinstance(raw_profile, VideoArtifact):
   159	                # Reconstruct through the DTO so mutation cannot smuggle
   160	                # invalid paths, profiles, or attachments past validation.
   161	                profile = VideoArtifact.from_dict(
   162	                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
   163	                )
   164	                path = profile.path
   165	                record = _artifact_lineage(profile)
   166	            elif isinstance(raw_profile, Mapping):
   167	                # Already-emitted lineage record: re-validate and re-key by
   168	                # its (validated) path so emitted provenance round-trips.
   169	                raw_path = raw_profile.get("path")
   170	                if not isinstance(raw_path, str) or not raw_path.strip(_ECMA_WHITESPACE):
   171	                    raise ValueError(
   172	                        "emitted lineage record must carry a non-empty string path"
   173	                    )
   174	                record = _artifact_lineage_from_mapping(
   175	                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
   176	                )
   177	                path = record["path"]
   178	            else:
   179	                raise TypeError(
   180	                    "sequence artifact_profiles entries must be VideoArtifacts "
   181	                    "or emitted lineage records"
   182	                )
   183	            if path in seen_paths:
   184	                raise ValueError(
   185	                    f"artifact_profiles sequence contains duplicate path "
   186	                    f"{path!r}"
   187	                )
   188	            seen_paths.add(path)
   189	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   190	            lineage.append(record)
   191	        if segments:
   192	            if len(lineage) != len(segments):
   193	                raise ValueError(
   194	                    f"artifact_profiles must record exactly one hashed lineage entry "
   195	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   196	                )
   197	        return lineage
   198	    raise TypeError("artifact_profiles must be an object or array")
   199	
   200	
   201	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   202	    raw_keys = set(raw)
   203	    allowed = {"profile", "sha256", "attachments", "path"}
   204	    unknown = sorted(raw_keys - allowed)
   205	    if unknown:
   206	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   207	    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
   208	    if missing:
   209	        raise ValueError(
   210	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   211	        )
   212	    if raw["sha256"] is None:
   213	        raise ValueError("artifact lineage sha256 is required and must not be null")
   214	    if not isinstance(raw["sha256"], str):
   215	        raise TypeError("artifact lineage sha256 must be a string")
   216	    if "path" in raw:
   217	        if not isinstance(raw["path"], str):
   218	            raise TypeError("artifact lineage path must be a string")
   219	        embedded = _require_workspace_relative_path(raw["path"], "artifact path")
   220	        if embedded != key:
   221	            raise ValueError(
   222	                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
   223	            )
   224	    profile = raw["profile"]
   225	    attachments: dict[str, Any] = {}
   226	    raw_attachments = raw["attachments"]
   227	    if raw_attachments is None:
   228	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   229	    if not isinstance(raw_attachments, Mapping):
   230	        raise TypeError("artifact lineage attachments must be an object")
   231	    for name, att in raw_attachments.items():
   232	        name = _require_string(name, "attachment name")
   233	        if isinstance(att, Attachment):
   234	            if att.name != name:
   235	                raise ValueError(
   236	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   237	                )
   238	            att = {
   239	                "path": att.path,
   240	                "kind": att.kind,
   241	                "sha256": att.sha256,
   242	            }
   243	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   244	        if att_unknown:
   245	            raise ValueError(
   246	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   247	            )
   248	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   249	        if att_missing:
   250	            raise ValueError(
   251	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   252	            )
   253	        if not isinstance(att["sha256"], str):
   254	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   255	        # Validate through the Attachment DTO so workspace-path containment and
   256	        # kind grammar are enforced uniformly for raw and dataclass values.
   257	        validated = Attachment(
   258	            name=name,
   259	            path=att["path"],
   260	            kind=att["kind"],
   261	            sha256=att["sha256"],
   262	        )
   263	        attachments[name] = {
   264	            "path": validated.path,
   265	            "kind": validated.kind,
   266	            "sha256": validated.sha256,
   267	        }
   268	    return {
   269	        "path": key,
   270	        "profile": RenderProfile.from_dict(
   900	        )
   901	    with pytest.raises(ValueError, match="attachment kind"):
   902	        assemble_provenance_v2(
   903	            **base,
   904	            plan=_plan(),
   905	            artifact_profiles={
   906	                "out/v.mp4": {
   907	                    "profile": _profile(),
   908	                    "sha256": SHA_B,
   909	                    "attachments": {
   910	                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
   911	                    },
   912	                },
   913	            },
   914	        )
   915	
   916	
   917	    with pytest.raises(ValueError, match="must equal Attachment.name"):
   918	        assemble_provenance_v2(
   919	            **base,
   920	            plan=_plan(),
   921	            artifact_profiles={
   922	                "out/v.mp4": {
   923	                    "profile": _profile(),
   924	                    "sha256": SHA_B,
   925	                    "attachments": {
   926	                        "different_key": Attachment(
   927	                            name="alpha",
   928	                            path="outputs/alpha.mp4",
   929	                            kind="alpha",
   930	                            sha256=SHA_C,
   931	                        )
   932	                    },
   933	                }
   934	            },
   935	        )
   936	    with pytest.raises(ValueError, match="duplicate attachment name"):
   937	        assemble_provenance_v2(
   938	            **base,
   939	            plan=_plan(
   940	                segments=[_segment(0, 24), _segment(24, 48)]
   941	            ),
   942	            artifact_profiles=[
   943	                VideoArtifact(
   944	                    path="outputs/v1.mp4",
   945	                    profile=_profile(),
   946	                    sha256=SHA_B,
   947	                    duration_frames=24,
   948	                    audio=AudioOwnership.RENDERED,
   949	                    attachments={
   950	                        "alpha": Attachment(
   951	                            name="alpha",
   952	                            path="outputs/a.mp4",
   953	                            kind="alpha",
   954	                            sha256=SHA_C,
   955	                        )
   956	                    },
   957	                ),
   958	                VideoArtifact(
   959	                    path="outputs/v2.mp4",
   960	                    profile=_profile(),
   961	                    sha256=SHA_D,
   962	                    duration_frames=24,
   963	                    audio=AudioOwnership.RENDERED,
   964	                    attachments={
   965	                        "alpha": Attachment(
   966	                            name="alpha",
   967	                            path="outputs/a2.mp4",
   968	                            kind="alpha",
   969	                            sha256=SHA_C,
   970	                        )
   971	                    },
   972	                ),
   973	            ],
   974	        )
   975	    with pytest.raises(ValueError, match="must carry a non-empty string path"):
   976	        assemble_provenance_v2(
   977	            **base,
   978	            plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
   979	            artifact_profiles=[
   980	                {"profile": _profile(audio=False).to_dict(), "sha256": SHA_B, "attachments": {}},
   981	                {"path": 123, "profile": _profile(audio=False).to_dict(), "sha256": SHA_C, "attachments": {}},
   982	            ],
   983	        )
   984	    with pytest.raises(ValueError, match="whitespace-only path components"):
   985	        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
   986	    # Mapping-form records must not coerce non-string embedded paths.
   987	    with pytest.raises(TypeError, match="artifact lineage path must be a string"):
   988	        assemble_provenance_v2(
   989	            **base,
   990	            plan=_plan(),
   991	            artifact_profiles={
   992	                "123": {
   993	                    "path": 123,
   994	                    "profile": _profile().to_dict(),
   995	                    "sha256": SHA_B,
   996	                    "attachments": {},
   997	                }
   998	            },
   999	        )
  1000	    with pytest.raises(TypeError, match="mapping keys must be strings"):
  1001	        assemble_provenance_v2(
  1002	            **base,
  1003	            plan=_plan(),
  1004	            artifact_profiles={123: {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
  1005	        )
  1006	    with pytest.raises(ValueError, match="workspace path"):
  1007	        assemble_provenance_v2(
  1008	            **base,
  1009	            plan=_plan(),
  1010	            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
  1011	        )
  1012	    # Emitted lineage records round-trip: re-passing the emitted sequence
  1013	    # (dictionary records) validates and reproduces the same output.
  1014	    first = assemble_provenance_v2(
  1015	        **base,
  1016	        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
  1017	        artifact_profiles=[
  1018	            VideoArtifact(
  1019	                path="outputs/a.mp4",
  1020	                profile=_profile(audio=False),
  1021	                sha256=SHA_B,
  1022	                duration_frames=24,
  1023	            ),
  1024	            VideoArtifact(
  1025	                path="outputs/b.mp4",
  1026	                profile=_profile(audio=False),
  1027	                sha256=SHA_C,
  1028	                duration_frames=24,
  1029	            ),
  1030	        ],
  1031	    )
  1032	    second = assemble_provenance_v2(
  1033	        **base,
  1034	        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
  1035	        artifact_profiles=first["artifact_profiles"],
  1036	    )
  1037	    assert second["artifact_profiles"] == first["artifact_profiles"]
  1038	    with pytest.raises(ValueError, match="duplicate path"):
  1039	        assemble_provenance_v2(
  1040	            **base,

codex
The patch is as scoped: two validation changes plus focused regression tests; the third changed file is the prior checkpoint transcript. I’m now checking the shared whitespace definition and both sequence/mapping round-trip paths for hidden type or compatibility asymmetries.
exec
/bin/zsh -lc "rg -n \"_ECMA_WHITESPACE|def _require_string|def _require_workspace_relative_path|class VideoArtifact|artifact_profiles\" astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py | sed -n '1,280p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_contracts.py:568:        "artifact_profiles": [
tests/core/rendering/test_contracts.py:702:        artifact_profiles=[
tests/core/rendering/test_contracts.py:775:        artifact_profiles={"outputs/visual.mp4": artifact},
tests/core/rendering/test_contracts.py:782:    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
tests/core/rendering/test_contracts.py:836:            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
tests/core/rendering/test_contracts.py:842:            artifact_profiles={
tests/core/rendering/test_contracts.py:850:            artifact_profiles={
tests/core/rendering/test_contracts.py:862:            artifact_profiles={
tests/core/rendering/test_contracts.py:877:            artifact_profiles=[
tests/core/rendering/test_contracts.py:891:            artifact_profiles={
tests/core/rendering/test_contracts.py:905:            artifact_profiles={
tests/core/rendering/test_contracts.py:921:            artifact_profiles={
tests/core/rendering/test_contracts.py:942:            artifact_profiles=[
tests/core/rendering/test_contracts.py:979:            artifact_profiles=[
tests/core/rendering/test_contracts.py:991:            artifact_profiles={
tests/core/rendering/test_contracts.py:1004:            artifact_profiles={123: {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:1010:            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
tests/core/rendering/test_contracts.py:1017:        artifact_profiles=[
tests/core/rendering/test_contracts.py:1035:        artifact_profiles=first["artifact_profiles"],
tests/core/rendering/test_contracts.py:1037:    assert second["artifact_profiles"] == first["artifact_profiles"]
tests/core/rendering/test_contracts.py:1044:            artifact_profiles=[
tests/core/rendering/test_contracts.py:1062:            artifact_profiles=[mutated],
tests/core/rendering/test_contracts.py:1070:            artifact_profiles=[],
astrid/core/rendering/contracts.py:44:_ECMA_WHITESPACE = (
astrid/core/rendering/contracts.py:74:        "artifact_profiles",
astrid/core/rendering/contracts.py:226:def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
astrid/core/rendering/contracts.py:231:    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
astrid/core/rendering/contracts.py:273:def _require_string_list(value: Any, label: str) -> list[str]:
astrid/core/rendering/contracts.py:279:def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
astrid/core/rendering/contracts.py:323:def _require_workspace_relative_path(value: Any, label: str) -> str:
astrid/core/rendering/contracts.py:336:    if any(not part.strip(_ECMA_WHITESPACE) for part in raw_parts):
astrid/core/rendering/contracts.py:667:class VideoArtifact:
astrid/core/rendering/provenance.py:16:    _ECMA_WHITESPACE,
astrid/core/rendering/provenance.py:108:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:114:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:122:                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
astrid/core/rendering/provenance.py:128:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:139:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:149:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:170:                if not isinstance(raw_path, str) or not raw_path.strip(_ECMA_WHITESPACE):
astrid/core/rendering/provenance.py:180:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:185:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:194:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:198:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:320:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:371:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:372:            artifact_profiles,

exec
/bin/zsh -lc "rg -n \"Batch 1|1\\.1|acceptance|provenance|schema\" .oracle/tasklist.md | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
3:## Batch 1 — Baseline, contracts, and discovery
5:**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.
9:- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
12:- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
20:- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
21:- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
22:- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
23:- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
24:- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.
39:- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.
43:- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
44:- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
45:- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
46:- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
47:- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
48:- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]
66:- [ ] **T3.1 — Extract `rendering.remotion`** Move Remotion helpers from `executors/render/run.py` into `astrid/packs/rendering/backends/remotion/`, add `renderer.yaml` and the raw-command adapter, and relocate private-helper tests while retaining a thin facade suite; acceptance: `pytest -q tests/packs/rendering/test_remotion_backend.py tests/packs/rendering/test_remotion_render_contract.py`.  [HARD]
67:- [ ] **T3.2 — Enforce the Remotion outer lock** Add `backends/remotion/lock.py::remotion_render_lock`, route registry generation and full renders through it, and update `scripts/gen_effect_registry.py`, `scripts/gen_remotion_types.py`, and `remotion/package.json` so `gen-types` uses the same non-recursive writer entrypoint; acceptance: `pytest -q tests/packs/rendering/test_remotion_locking.py tests/packs/rendering/test_render_remotion_registry.py`.  [HARD]
68:- [ ] **T3.3 — Extract the FFmpeg backend and pure builders** Move media rendering and `audio_reactive_colour.py` into `astrid/packs/rendering/backends/ffmpeg/`, add `renderer.yaml`, and expose pure support/command/filter builders; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_backend.py tests/packs/rendering/test_audio_reactive_colour.py`.  [HARD]
69:- [ ] **T3.4 — Implement strict FFmpeg support and audio semantics** Implement `backends/ffmpeg/support.py::support` and exact gain/mute/source-bound/stream/fade/transform rejection rules with request-sensitive optimization and specialization evidence; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_support.py tests/packs/test_audio_render.py`.  [HARD]
70:- [ ] **T3.5 — Extract `rendering.ffmpeg-finalizer`** Move `_concat_segments()` into `astrid/packs/rendering/finalizers/ffmpeg/`, add `finalizer.yaml`, and implement complete profile comparison, normalization, audio-mode handling, attachment preservation, and cleanup; acceptance: `pytest -q tests/packs/rendering/test_ffmpeg_finalizer.py`.  [HARD]
71:- [ ] **T3.6 — Register and smoke the built-ins** Update `astrid/packs/rendering/pack.yaml` and built-in manifest tests for static discovery, required binaries, no-import inspection, real FFmpeg rendering, Remotion cleanup, and optional dependency reporting; acceptance: `pytest -q tests/packs/rendering tests/packs/test_audio_render.py` and `cd remotion && npm run typecheck`.
73:## Batch 4 — Generic routing, provenance, and hybrid planning
75:**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.
85:- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.
89:- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
90:- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
91:- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
92:- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
93:- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.
102:- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
107:- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
112:- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
113:- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
114:- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
115:- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
116:- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
117:- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
118:- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.
126:- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
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
175:- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
178:- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '30,170p'; nl -ba astrid/core/rendering/contracts.py | sed -n '480,720p'; nl -ba astrid/core/rendering/provenance.py | sed -n '200,390p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
    41	# ECMAScript \s whitespace set, spelled as explicit characters so it is
    42	# identical in the DTO and the JSON Schemas (Python str.strip() has no
    43	# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
    44	_ECMA_WHITESPACE = (
    45	    " \t\n\r\f\v\u00a0\u1680"
    46	    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    47	    "\u2028\u2029\u202f\u205f\u3000\ufeff"
    48	)
    49	
    50	RENDER_RESULT_CORE_KEYS = frozenset(
    51	    {
    52	        "schema_version",
    53	        "video",
    54	        "backend_fragments",
    55	        "audio_ownership",
    56	        "normalization",
    57	        "logs",
    58	        "metadata",
    59	    }
    60	)
    61	
    62	PROVENANCE_V2_CORE_KEYS = frozenset(
    63	    {
    64	        "schema_version",
    65	        "engine",
    66	        "output",
    67	        "timeline",
    68	        "assets_registry",
    69	        "request_digest",
    70	        "requested_policy",
    71	        "planner",
    72	        "segments",
    73	        "segments_v2",
    74	        "artifact_profiles",
    75	        "audio_ownership",
    76	        "normalization",
    77	        "finalizer",
    78	        "attachments",
    79	        "backend_fragments",
    80	    }
    81	)
    82	
    83	PROVENANCE_V1_COMPATIBILITY_KEYS = frozenset(
    84	    {
    85	        "project_dir",
    86	        "composition_id",
    87	        "active_pack_order",
    88	        "active_theme",
    89	        "registry_hash",
    90	        "registry_state",
    91	        "resolved_effect_ids",
    92	        "resolved_effects",
    93	        "source_pack_ids",
    94	        "element_roots",
    95	        "staged_asset_ids",
    96	        "staged_asset_root",
    97	        "segment_provenance",
    98	        "ffmpeg_specialization",
    99	        "audio_reactive_colour",
   100	    }
   101	)
   102	
   103	PROVENANCE_V1_ALWAYS_KEYS = frozenset(
   104	    {
   105	        "project_dir",
   106	        "composition_id",
   107	        "active_pack_order",
   108	        "active_theme",
   109	        "registry_hash",
   110	        "registry_state",
   111	        "resolved_effect_ids",
   112	        "resolved_effects",
   113	        "source_pack_ids",
   114	        "element_roots",
   115	        "staged_asset_ids",
   116	        "staged_asset_root",
   117	    }
   118	)
   119	
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
   651	            raw_attachment
   652	            if isinstance(raw_attachment, Attachment)
   653	            else Attachment.from_dict(_require_mapping(raw_attachment, f"{label}[{key!r}]"))
   654	        )
   655	        if attachment.name != key:
   656	            raise ValueError(
   657	                f"{label} key {key!r} must match attachment.name {attachment.name!r}"
   658	            )
   659	        if attachment.name in seen_names:
   660	            raise ValueError(f"duplicate attachment name: {attachment.name}")
   661	        seen_names.add(attachment.name)
   662	        result[key] = attachment
   663	    return result
   664	
   665	
   666	@dataclass(frozen=True)
   667	class VideoArtifact:
   668	    """The required primary video produced by a renderer or finalizer."""
   669	
   670	    path: str
   671	    profile: RenderProfile
   672	    sha256: str
   673	    duration_frames: int
   674	    audio: AudioOwnership | None = None
   675	    attachments: dict[str, Attachment] = field(default_factory=dict)
   676	
   677	    def __post_init__(self) -> None:
   678	        profile = (
   679	            self.profile
   680	            if isinstance(self.profile, RenderProfile)
   681	            else RenderProfile.from_dict(_require_mapping(self.profile, "video profile"))
   682	        )
   683	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
   684	        object.__setattr__(self, "profile", profile)
   685	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
   686	        object.__setattr__(
   687	            self,
   688	            "duration_frames",
   689	            _require_int(self.duration_frames, "duration_frames", minimum=1),
   690	        )
   691	        audio = _coerce_audio_ownership(self.audio, "video audio", nullable=True)
   692	        _validate_artifact_audio(profile, audio, "video artifact")
   693	        object.__setattr__(self, "audio", audio)
   694	        object.__setattr__(
   695	            self,
   696	            "attachments",
   697	            _coerce_attachment_mapping(self.attachments, "video attachments"),
   698	        )
   699	
   700	    def to_dict(self) -> dict[str, Any]:
   701	        return _json_safe_mapping(
   702	            {
   703	                "path": self.path,
   704	                "profile": self.profile,
   705	                "sha256": self.sha256,
   706	                "duration_frames": self.duration_frames,
   707	                "audio": self.audio,
   708	                "attachments": self.attachments,
   709	            }
   710	        )
   711	
   712	    @classmethod
   713	    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
   714	        data = _require_mapping(payload, "video artifact")
   715	        required = {"path", "profile", "sha256", "duration_frames"}
   716	        allowed = required | {"audio", "attachments"}
   717	        _validate_object_keys(data, required=required, allowed=allowed, label="video artifact")
   718	        return cls(
   719	            path=data["path"],
   720	            profile=RenderProfile.from_dict(data["profile"]),
   200	
   201	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   202	    raw_keys = set(raw)
   203	    allowed = {"profile", "sha256", "attachments", "path"}
   204	    unknown = sorted(raw_keys - allowed)
   205	    if unknown:
   206	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   207	    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
   208	    if missing:
   209	        raise ValueError(
   210	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   211	        )
   212	    if raw["sha256"] is None:
   213	        raise ValueError("artifact lineage sha256 is required and must not be null")
   214	    if not isinstance(raw["sha256"], str):
   215	        raise TypeError("artifact lineage sha256 must be a string")
   216	    if "path" in raw:
   217	        if not isinstance(raw["path"], str):
   218	            raise TypeError("artifact lineage path must be a string")
   219	        embedded = _require_workspace_relative_path(raw["path"], "artifact path")
   220	        if embedded != key:
   221	            raise ValueError(
   222	                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
   223	            )
   224	    profile = raw["profile"]
   225	    attachments: dict[str, Any] = {}
   226	    raw_attachments = raw["attachments"]
   227	    if raw_attachments is None:
   228	        raise ValueError("artifact lineage attachments must be an object (may be empty)")
   229	    if not isinstance(raw_attachments, Mapping):
   230	        raise TypeError("artifact lineage attachments must be an object")
   231	    for name, att in raw_attachments.items():
   232	        name = _require_string(name, "attachment name")
   233	        if isinstance(att, Attachment):
   234	            if att.name != name:
   235	                raise ValueError(
   236	                    f"attachment map key {name!r} must equal Attachment.name {att.name!r}"
   237	                )
   238	            att = {
   239	                "path": att.path,
   240	                "kind": att.kind,
   241	                "sha256": att.sha256,
   242	            }
   243	        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
   244	        if att_unknown:
   245	            raise ValueError(
   246	                f"attachment {name!r} has unknown fields: {', '.join(att_unknown)}"
   247	            )
   248	        att_missing = sorted({"path", "kind", "sha256"} - set(att))
   249	        if att_missing:
   250	            raise ValueError(
   251	                f"attachment {name!r} is missing required fields: {', '.join(att_missing)}"
   252	            )
   253	        if not isinstance(att["sha256"], str):
   254	            raise TypeError(f"attachment {name!r} sha256 must be a string")
   255	        # Validate through the Attachment DTO so workspace-path containment and
   256	        # kind grammar are enforced uniformly for raw and dataclass values.
   257	        validated = Attachment(
   258	            name=name,
   259	            path=att["path"],
   260	            kind=att["kind"],
   261	            sha256=att["sha256"],
   262	        )
   263	        attachments[name] = {
   264	            "path": validated.path,
   265	            "kind": validated.kind,
   266	            "sha256": validated.sha256,
   267	        }
   268	    return {
   269	        "path": key,
   270	        "profile": RenderProfile.from_dict(
   271	            _json_safe_mapping(profile, label="artifact profile")
   272	        ).to_dict(),
   273	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   274	        "attachments": attachments,
   275	    }
   276	
   277	
   278	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   279	    """One hashed artifact lineage record: profile, sha256, attachments."""
   280	    return _artifact_lineage_from_mapping(
   281	        {
   282	            "profile": artifact.profile,
   283	            "sha256": artifact.sha256,
   284	            "attachments": artifact.attachments,
   285	        },
   286	        key=artifact.path,
   287	    )
   288	
   289	
   290	def _normalize_v1_compatibility(
   291	    fields: Mapping[str, Any] | None,
   292	) -> dict[str, Any]:
   293	    if fields is None:
   294	        raise ValueError(
   295	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   296	        )
   297	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   298	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   299	    if unknown:
   300	        raise ValueError(
   301	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   302	            + ", ".join(unknown)
   303	        )
   304	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   305	    if missing:
   306	        raise ValueError(
   307	            "v1 compatibility projection is missing always-emitted fields: "
   308	            + ", ".join(missing)
   309	        )
   310	    return compatibility
   311	
   312	
   313	def assemble_provenance_v2(
   314	    *,
   315	    engine: str,
   316	    output: str | Path,
   317	    timeline: str | Path,
   318	    assets_registry: str | Path | None,
   319	    plan: RenderPlan | Mapping[str, Any],
   320	    artifact_profiles: Any = None,
   321	    audio_ownership: AudioOwnership | str | None = None,
   322	    normalization: Sequence[str] = (),
   323	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   324	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   325	    v1_compatibility: Mapping[str, Any] | None = None,
   326	) -> dict[str, Any]:
   327	    """Assemble additive provenance v2 with protected ownership boundaries.
   328	
   329	    ``engine`` is intentionally the legacy request projection. Routing and
   330	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   331	    hybrid invocation cannot collapse multiple renderer identities. Optional
   332	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   333	    any v2 core field.
   334	    """
   335	
   336	    legacy_engine = _require_string(engine, "engine")
   337	    output_path = _require_string(str(output), "output")
   338	    timeline_path = _require_string(str(timeline), "timeline")
   339	    assets_path = None if assets_registry is None else _require_string(
   340	        str(assets_registry), "assets_registry"
   341	    )
   342	    normalized_plan = (
   343	        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
   344	        if isinstance(plan, RenderPlan)
   345	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   346	    )
   347	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   348	    legacy_segments = [
   349	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   350	    ]
   351	    normalized_normalization = [
   352	        _require_string(item, f"normalization[{index}]")
   353	        for index, item in enumerate(normalization)
   354	    ]
   355	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   356	
   357	    payload: dict[str, Any] = {
   358	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   359	        "engine": legacy_engine,
   360	        "output": output_path,
   361	        "timeline": timeline_path,
   362	        "assets_registry": assets_path,
   363	        "request_digest": normalized_plan.request_digest,
   364	        "requested_policy": normalized_plan.requested_policy,
   365	        "planner": normalized_plan.planner.to_dict(),
   366	        # V1-compatible segment projection: flat {engine, from, to} entries,
   367	        # exactly the shape legacy consumers read from `segments`.
   368	        "segments": legacy_segments,
   369	        # Additive normalized v2 segment records; never overwrite v1 fields.
   370	        "segments_v2": normalized_segments,
   371	        "artifact_profiles": _normalize_artifact_profiles(
   372	            artifact_profiles,
   373	            segments=normalized_plan.segments,
   374	        ),
   375	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   376	        "normalization": normalized_normalization,
   377	        "finalizer": normalized_plan.finalizer.to_dict(),
   378	        "attachments": _normalize_attachments(attachments),
   379	        "backend_fragments": validate_backend_fragments(backend_fragments),
   380	    }
   381	    payload.update(compatibility)
   382	    return _json_safe_mapping(payload, label="provenance")
   383	
   384	
   385	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   386	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   387	
   388	    return assemble_provenance_v2(**kwargs)
   389	
   390	

exec
/bin/zsh -lc "rg -n \"0085|FEFF|2001|round.trip|non-string|mapping keys|lineage path\" tests/core/rendering astrid | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_schema_roundtrip.py:85:        round_trip = dto.to_dict()
tests/core/rendering/test_schema_roundtrip.py:86:        validator.validate(round_trip)
tests/core/rendering/test_schema_roundtrip.py:87:        assert round_trip == example
tests/core/rendering/test_schema_roundtrip.py:91:def test_canonical_raw_fixture_validates_and_round_trips_identically(schema_name: str) -> None:
tests/core/rendering/test_contracts.py:221:def test_dto_json_round_trip() -> None:
tests/core/rendering/test_contracts.py:450:def test_finalize_round_trip_preserves_global_segment_attachments() -> None:
tests/core/rendering/test_contracts.py:461:    round_trip = FinalizeRequest.from_dict(request.to_dict())
tests/core/rendering/test_contracts.py:462:    assert round_trip.expected_attachments == {first.name: first, second.name: second}
tests/core/rendering/test_contracts.py:651:    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
tests/core/rendering/test_contracts.py:654:def test_resolution_evidence_survives_plan_round_trip_and_provenance() -> None:
tests/core/rendering/test_contracts.py:656:    plan wire round-trip and the final provenance sidecar."""
tests/core/rendering/test_contracts.py:685:    # Wire round-trip
tests/core/rendering/test_contracts.py:985:        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
tests/core/rendering/test_contracts.py:986:    # Mapping-form records must not coerce non-string embedded paths.
tests/core/rendering/test_contracts.py:987:    with pytest.raises(TypeError, match="artifact lineage path must be a string"):
tests/core/rendering/test_contracts.py:1000:    with pytest.raises(TypeError, match="mapping keys must be strings"):
tests/core/rendering/test_contracts.py:1012:    # Emitted lineage records round-trip: re-passing the emitted sequence
tests/core/rendering/test_contracts.py:1145:def test_manifest_round_trip() -> None:
astrid/core/session/binding.py:99:#   - tests/test_task_hook_stop.py (env-binding round-trip)
astrid/core/experiments/schema.py:8:- Unknown additive fields round-trip (preserved in passthrough).
astrid/core/experiments/normalize.py:326:    # Persist no provider URL strings at all.  Replace with safe non-string
astrid/core/experiments/capture.py:123:    prompt/label, CLI title/question/rubric, mapping keys, or any future
astrid/core/registry/base.py:140:        Subclasses that key on non-string types (e.g. ``tuple[str, str]``
astrid/core/integrations/worker/banodoco_worker.py:196:        logger.warning("baseline_snapshot did not round-trip into run record for %s", run_id)
astrid/core/integrations/reigh/timeline_io.py:60:def _round_trip(payload: Mapping[str, Any]) -> RawTimelinePayload:
astrid/core/integrations/reigh/timeline_io.py:74:    """Validate + round-trip config into Astrid's canonical timeline shape."""
astrid/core/integrations/reigh/timeline_io.py:147:    return _round_trip(raw_config), raw_version
astrid/core/integrations/arnold/session/records.py:186:    """Preserve any unrecognised fields so round-trips are lossless."""
astrid/core/task/validator.py:68:# ---- I1: schema re-validate (round-trip through _validate_plan) ----
astrid/core/orchestrate/compile.py:10:round-trips through ``astrid.core.plan.load_plan``), and writes the
astrid/core/orchestrate/cli.py:93:    # to_dict already round-trips through load_plan; re-parse to get the typed
astrid/core/rendering/provenance.py:122:                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
astrid/core/rendering/provenance.py:168:                # its (validated) path so emitted provenance round-trips.
astrid/core/rendering/provenance.py:218:            raise TypeError("artifact lineage path must be a string")
astrid/core/rendering/provenance.py:222:                f"artifact lineage path {embedded!r} must equal its map key {key!r}"
astrid/core/rendering/contracts.py:43:# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
astrid/core/rendering/contracts.py:46:    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
astrid/packs/iteration/executors/experiment_import/run.py:193:    ``manual-mappings.json`` shape, so that artifact must round-trip as a valid
astrid/packs/fal/tests/test_h3_video.py:46:    prompt_file.write_text("x" * 2001, encoding="utf-8")
astrid/packs/fal/tests/test_h3_video.py:64:    assert (tmp_path / "out" / "inputs" / "prompt.txt").read_text().strip() == "x" * 2001
astrid/packs/editorial/executors/human_notes/STAGE.md:24:editor_review.json, enabling a human-notes → rendered-video round-trip.

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/contracts.py | sed -n '210,365p'; nl -ba astrid/core/rendering/contracts.py | sed -n '660,755p'; nl -ba astrid/core/rendering/provenance.py | sed -n '260,390p'; nl -ba tests/core/rendering/test_contracts.py | sed -n '740,1095p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   331	        raise ValueError(f"{label} must not be a UNC path")
   332	    raw_parts = normalized.split("/")
   333	    parts = PurePosixPath(normalized).parts
   334	    if not parts or any(part in {"", ".", ".."} for part in raw_parts):
   335	        raise ValueError(f"{label} must be a normalized contained workspace path")
   336	    if any(not part.strip(_ECMA_WHITESPACE) for part in raw_parts):
   337	        raise ValueError(f"{label} must not contain empty or whitespace-only path components")
   338	    return raw
   339	
   340	
   341	def _relative_file_path(path: str | Path, workspace_root: str | Path, label: str) -> tuple[str, Path]:
   342	    root = Path(workspace_root).resolve()
   343	    candidate = Path(path)
   344	    if not candidate.is_absolute():
   345	        candidate = root / candidate
   346	    resolved = candidate.resolve(strict=True)
   347	    try:
   348	        relative = resolved.relative_to(root)
   349	    except ValueError as exc:
   350	        raise ValueError(f"{label} escapes invocation workspace {root}") from exc
   351	    return relative.as_posix(), resolved
   352	
   353	
   354	def _protocol_failure(message: str, *, details: Mapping[str, Any] | None = None) -> NoReturn:
   355	    from .errors import raise_protocol_error
   356	
   357	    raise_protocol_error(
   358	        backend="astrid.core",
   359	        message=message,
   360	        details=dict(details or {}),
   361	    )
   362	
   363	
   364	class AudioOwnership(str, Enum):
   365	    """Who is responsible for audio in a returned primary video."""
   660	            raise ValueError(f"duplicate attachment name: {attachment.name}")
   661	        seen_names.add(attachment.name)
   662	        result[key] = attachment
   663	    return result
   664	
   665	
   666	@dataclass(frozen=True)
   667	class VideoArtifact:
   668	    """The required primary video produced by a renderer or finalizer."""
   669	
   670	    path: str
   671	    profile: RenderProfile
   672	    sha256: str
   673	    duration_frames: int
   674	    audio: AudioOwnership | None = None
   675	    attachments: dict[str, Attachment] = field(default_factory=dict)
   676	
   677	    def __post_init__(self) -> None:
   678	        profile = (
   679	            self.profile
   680	            if isinstance(self.profile, RenderProfile)
   681	            else RenderProfile.from_dict(_require_mapping(self.profile, "video profile"))
   682	        )
   683	        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
   684	        object.__setattr__(self, "profile", profile)
   685	        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
   686	        object.__setattr__(
   687	            self,
   688	            "duration_frames",
   689	            _require_int(self.duration_frames, "duration_frames", minimum=1),
   690	        )
   691	        audio = _coerce_audio_ownership(self.audio, "video audio", nullable=True)
   692	        _validate_artifact_audio(profile, audio, "video artifact")
   693	        object.__setattr__(self, "audio", audio)
   694	        object.__setattr__(
   695	            self,
   696	            "attachments",
   697	            _coerce_attachment_mapping(self.attachments, "video attachments"),
   698	        )
   699	
   700	    def to_dict(self) -> dict[str, Any]:
   701	        return _json_safe_mapping(
   702	            {
   703	                "path": self.path,
   704	                "profile": self.profile,
   705	                "sha256": self.sha256,
   706	                "duration_frames": self.duration_frames,
   707	                "audio": self.audio,
   708	                "attachments": self.attachments,
   709	            }
   710	        )
   711	
   712	    @classmethod
   713	    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
   714	        data = _require_mapping(payload, "video artifact")
   715	        required = {"path", "profile", "sha256", "duration_frames"}
   716	        allowed = required | {"audio", "attachments"}
   717	        _validate_object_keys(data, required=required, allowed=allowed, label="video artifact")
   718	        return cls(
   719	            path=data["path"],
   720	            profile=RenderProfile.from_dict(data["profile"]),
   721	            sha256=data["sha256"],
   722	            duration_frames=data["duration_frames"],
   723	            audio=data.get("audio"),
   724	            attachments=data.get("attachments", {}),
   725	        )
   726	
   727	    @classmethod
   728	    def from_file(
   729	        cls,
   730	        *,
   731	        path: str | Path,
   732	        workspace_root: str | Path,
   733	        profile: RenderProfile,
   734	        duration_frames: int,
   735	        audio: AudioOwnership | None = None,
   736	        attachments: Mapping[str, Attachment] | None = None,
   737	    ) -> VideoArtifact:
   738	        relative, resolved = _relative_file_path(path, workspace_root, "video path")
   739	        return cls(
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
   260	            kind=att["kind"],
   261	            sha256=att["sha256"],
   262	        )
   263	        attachments[name] = {
   264	            "path": validated.path,
   265	            "kind": validated.kind,
   266	            "sha256": validated.sha256,
   267	        }
   268	    return {
   269	        "path": key,
   270	        "profile": RenderProfile.from_dict(
   271	            _json_safe_mapping(profile, label="artifact profile")
   272	        ).to_dict(),
   273	        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
   274	        "attachments": attachments,
   275	    }
   276	
   277	
   278	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   279	    """One hashed artifact lineage record: profile, sha256, attachments."""
   280	    return _artifact_lineage_from_mapping(
   281	        {
   282	            "profile": artifact.profile,
   283	            "sha256": artifact.sha256,
   284	            "attachments": artifact.attachments,
   285	        },
   286	        key=artifact.path,
   287	    )
   288	
   289	
   290	def _normalize_v1_compatibility(
   291	    fields: Mapping[str, Any] | None,
   292	) -> dict[str, Any]:
   293	    if fields is None:
   294	        raise ValueError(
   295	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   296	        )
   297	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   298	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   299	    if unknown:
   300	        raise ValueError(
   301	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   302	            + ", ".join(unknown)
   303	        )
   304	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   305	    if missing:
   306	        raise ValueError(
   307	            "v1 compatibility projection is missing always-emitted fields: "
   308	            + ", ".join(missing)
   309	        )
   310	    return compatibility
   311	
   312	
   313	def assemble_provenance_v2(
   314	    *,
   315	    engine: str,
   316	    output: str | Path,
   317	    timeline: str | Path,
   318	    assets_registry: str | Path | None,
   319	    plan: RenderPlan | Mapping[str, Any],
   320	    artifact_profiles: Any = None,
   321	    audio_ownership: AudioOwnership | str | None = None,
   322	    normalization: Sequence[str] = (),
   323	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   324	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   325	    v1_compatibility: Mapping[str, Any] | None = None,
   326	) -> dict[str, Any]:
   327	    """Assemble additive provenance v2 with protected ownership boundaries.
   328	
   329	    ``engine`` is intentionally the legacy request projection. Routing and
   330	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   331	    hybrid invocation cannot collapse multiple renderer identities. Optional
   332	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   333	    any v2 core field.
   334	    """
   335	
   336	    legacy_engine = _require_string(engine, "engine")
   337	    output_path = _require_string(str(output), "output")
   338	    timeline_path = _require_string(str(timeline), "timeline")
   339	    assets_path = None if assets_registry is None else _require_string(
   340	        str(assets_registry), "assets_registry"
   341	    )
   342	    normalized_plan = (
   343	        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
   344	        if isinstance(plan, RenderPlan)
   345	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   346	    )
   347	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   348	    legacy_segments = [
   349	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   350	    ]
   351	    normalized_normalization = [
   352	        _require_string(item, f"normalization[{index}]")
   353	        for index, item in enumerate(normalization)
   354	    ]
   355	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   356	
   357	    payload: dict[str, Any] = {
   358	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   359	        "engine": legacy_engine,
   360	        "output": output_path,
   361	        "timeline": timeline_path,
   362	        "assets_registry": assets_path,
   363	        "request_digest": normalized_plan.request_digest,
   364	        "requested_policy": normalized_plan.requested_policy,
   365	        "planner": normalized_plan.planner.to_dict(),
   366	        # V1-compatible segment projection: flat {engine, from, to} entries,
   367	        # exactly the shape legacy consumers read from `segments`.
   368	        "segments": legacy_segments,
   369	        # Additive normalized v2 segment records; never overwrite v1 fields.
   370	        "segments_v2": normalized_segments,
   371	        "artifact_profiles": _normalize_artifact_profiles(
   372	            artifact_profiles,
   373	            segments=normalized_plan.segments,
   374	        ),
   375	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   376	        "normalization": normalized_normalization,
   377	        "finalizer": normalized_plan.finalizer.to_dict(),
   378	        "attachments": _normalize_attachments(attachments),
   379	        "backend_fragments": validate_backend_fragments(backend_fragments),
   380	    }
   381	    payload.update(compatibility)
   382	    return _json_safe_mapping(payload, label="provenance")
   383	
   384	
   385	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   386	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   387	
   388	    return assemble_provenance_v2(**kwargs)
   389	
   390	
   740	        (_finalizer(), FinalizerResolution.from_dict),
   741	        (_renderer(), RendererResolution.from_dict),
   742	    )
   743	    for obj, parser in cases:
   744	        for missing in ("alias_chain", "override", "trust_eligibility", "support_decision"):
   745	            broken = obj.to_dict()
   746	            del broken[missing]
   747	            with pytest.raises(ValueError, match="missing required fields"):
   748	                parser(broken)
   749	
   750	
   751	def test_provenance_emits_hashed_artifact_lineage() -> None:
   752	    """Provenance records per-artifact sha256 and attachment hashes, not
   753	    just profiles — so replay can verify rendered outputs byte-for-byte."""
   754	    artifact = VideoArtifact(
   755	        path="outputs/visual.mp4",
   756	        profile=_profile(),
   757	        sha256=SHA_B,
   758	        duration_frames=48,
   759	        audio=AudioOwnership.RENDERED,
   760	        attachments={
   761	            "alpha": Attachment(
   762	                name="alpha",
   763	                path="outputs/alpha.mp4",
   764	                kind="alpha",
   765	                sha256=SHA_C,
   766	            )
   767	        },
   768	    )
   769	    payload = assemble_provenance_v2(
   770	        engine="hybrid",
   771	        output="/workspace/out/video.mp4",
   772	        timeline="/workspace/timeline.json",
   773	        assets_registry=None,
   774	        plan=_plan(),
   775	        artifact_profiles={"outputs/visual.mp4": artifact},
   776	        audio_ownership="rendered",
   777	        normalization=[],
   778	        attachments={},
   779	        backend_fragments={},
   780	        v1_compatibility=_compatibility(),
   781	    )
   782	    lineage = payload["artifact_profiles"]["outputs/visual.mp4"]
   783	    assert lineage["sha256"] == SHA_B
   784	    assert lineage["attachments"]["alpha"]["sha256"] == SHA_C
   785	    assert lineage["attachments"]["alpha"]["kind"] == "alpha"
   786	
   787	
   788	def test_planner_and_finalizer_reject_mismatched_support_backend() -> None:
   789	    """support_decision.backend must equal the resolution id for planner and
   790	    finalizer, exactly as it does for renderer."""
   791	    cases = (
   792	        (_planner, "planner"),
   793	        (_finalizer, "finalizer"),
   794	        (_renderer, "renderer"),
   795	    )
   796	    for factory, label in cases:
   797	        payload = factory().to_dict()
   798	        payload["support_decision"] = _support("other.backend").to_dict()
   799	        with pytest.raises(ValueError, match=f"{label} support_decision.backend"):
   800	            type(factory()).from_dict(payload)
   801	
   802	
   803	def test_resolutions_reject_incoherent_override_records() -> None:
   804	    """Override records must be {from, to} with to == resolution id."""
   805	    cases = (
   806	        (_planner, "planner"),
   807	        (_finalizer, "finalizer"),
   808	        (_renderer, "renderer"),
   809	    )
   810	    for factory, label in cases:
   811	        payload = factory().to_dict()
   812	        payload["override"] = {"from": "other.origin", "to": "not.the.id"}
   813	        with pytest.raises(ValueError, match=f"{label} override 'to'"):
   814	            type(factory()).from_dict(payload)
   815	        payload["override"] = {"only": "one"}
   816	        with pytest.raises(ValueError, match=f"{label} override"):
   817	            type(factory()).from_dict(payload)
   818	
   819	
   820	def test_provenance_rejects_spoofed_artifact_lineage() -> None:
   821	    """Artifact lineage must carry a real sha256; profile-only entries and
   822	    null hashes are rejected rather than stringified."""
   823	    base = dict(
   824	        engine="hybrid",
   825	        output="/workspace/out/video.mp4",
   826	        timeline="/workspace/timeline.json",
   827	        assets_registry=None,
   828	        audio_ownership="rendered",
   829	        normalization=[],
   830	        attachments={},
   831	        backend_fragments={},
   832	        v1_compatibility=_compatibility(),
   833	    )
   834	    with pytest.raises(TypeError, match="hashed lineage"):
   835	        assemble_provenance_v2(
   836	            **base, plan=_plan(), artifact_profiles={"out/v.mp4": _profile()}
   837	        )
   838	    with pytest.raises(ValueError, match="sha256"):
   839	        assemble_provenance_v2(
   840	            **base,
   841	            plan=_plan(),
   842	            artifact_profiles={
   843	                "out/v.mp4": {"profile": _profile(), "sha256": None, "attachments": {}}
   844	            },
   845	        )
   846	    with pytest.raises(ValueError, match="sha256"):
   847	        assemble_provenance_v2(
   848	            **base,
   849	            plan=_plan(),
   850	            artifact_profiles={
   851	                "out/v.mp4": {
   852	                    "profile": _profile(),
   853	                    "sha256": "not-a-hash",
   854	                    "attachments": {},
   855	                }
   856	            },
   857	        )
   858	    with pytest.raises(ValueError, match="unknown fields"):
   859	        assemble_provenance_v2(
   860	            **base,
   861	            plan=_plan(),
   862	            artifact_profiles={
   863	                "out/v.mp4": {
   864	                    "profile": _profile(),
   865	                    "sha256": SHA_B,
   866	                    "attachments": {},
   867	                    "spoof": 1,
   868	                }
   869	            },
   870	        )
   871	    with pytest.raises(ValueError, match="exactly one hashed lineage entry"):
   872	        assemble_provenance_v2(
   873	            **base,
   874	            plan=_plan(
   875	                segments=[_segment(0, 24), _segment(24, 48)]
   876	            ),
   877	            artifact_profiles=[
   878	                VideoArtifact(
   879	                    path="outputs/v.mp4",
   880	                    profile=_profile(),
   881	                    sha256=SHA_B,
   882	                    duration_frames=24,
   883	                    audio=AudioOwnership.RENDERED,
   884	                )
   885	            ],
   886	        )
   887	    with pytest.raises(ValueError, match="attachment path"):
   888	        assemble_provenance_v2(
   889	            **base,
   890	            plan=_plan(),
   891	            artifact_profiles={
   892	                "out/v.mp4": {
   893	                    "profile": _profile(),
   894	                    "sha256": SHA_B,
   895	                    "attachments": {
   896	                        "alpha": {"path": "../escape.mp4", "kind": "alpha", "sha256": SHA_C}
   897	                    },
   898	                },
   899	            },
   900	        )
   901	    with pytest.raises(ValueError, match="attachment kind"):
   902	        assemble_provenance_v2(
   903	            **base,
   904	            plan=_plan(),
   905	            artifact_profiles={
   906	                "out/v.mp4": {
   907	                    "profile": _profile(),
   908	                    "sha256": SHA_B,
   909	                    "attachments": {
   910	                        "alpha": {"path": "outputs/alpha.mp4", "kind": "Bad_Kind", "sha256": SHA_C}
   911	                    },
   912	                },
   913	            },
   914	        )
   915	
   916	
   917	    with pytest.raises(ValueError, match="must equal Attachment.name"):
   918	        assemble_provenance_v2(
   919	            **base,
   920	            plan=_plan(),
   921	            artifact_profiles={
   922	                "out/v.mp4": {
   923	                    "profile": _profile(),
   924	                    "sha256": SHA_B,
   925	                    "attachments": {
   926	                        "different_key": Attachment(
   927	                            name="alpha",
   928	                            path="outputs/alpha.mp4",
   929	                            kind="alpha",
   930	                            sha256=SHA_C,
   931	                        )
   932	                    },
   933	                }
   934	            },
   935	        )
   936	    with pytest.raises(ValueError, match="duplicate attachment name"):
   937	        assemble_provenance_v2(
   938	            **base,
   939	            plan=_plan(
   940	                segments=[_segment(0, 24), _segment(24, 48)]
   941	            ),
   942	            artifact_profiles=[
   943	                VideoArtifact(
   944	                    path="outputs/v1.mp4",
   945	                    profile=_profile(),
   946	                    sha256=SHA_B,
   947	                    duration_frames=24,
   948	                    audio=AudioOwnership.RENDERED,
   949	                    attachments={
   950	                        "alpha": Attachment(
   951	                            name="alpha",
   952	                            path="outputs/a.mp4",
   953	                            kind="alpha",
   954	                            sha256=SHA_C,
   955	                        )
   956	                    },
   957	                ),
   958	                VideoArtifact(
   959	                    path="outputs/v2.mp4",
   960	                    profile=_profile(),
   961	                    sha256=SHA_D,
   962	                    duration_frames=24,
   963	                    audio=AudioOwnership.RENDERED,
   964	                    attachments={
   965	                        "alpha": Attachment(
   966	                            name="alpha",
   967	                            path="outputs/a2.mp4",
   968	                            kind="alpha",
   969	                            sha256=SHA_C,
   970	                        )
   971	                    },
   972	                ),
   973	            ],
   974	        )
   975	    with pytest.raises(ValueError, match="must carry a non-empty string path"):
   976	        assemble_provenance_v2(
   977	            **base,
   978	            plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
   979	            artifact_profiles=[
   980	                {"profile": _profile(audio=False).to_dict(), "sha256": SHA_B, "attachments": {}},
   981	                {"path": 123, "profile": _profile(audio=False).to_dict(), "sha256": SHA_C, "attachments": {}},
   982	            ],
   983	        )
   984	    with pytest.raises(ValueError, match="whitespace-only path components"):
   985	        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
   986	    # Mapping-form records must not coerce non-string embedded paths.
   987	    with pytest.raises(TypeError, match="artifact lineage path must be a string"):
   988	        assemble_provenance_v2(
   989	            **base,
   990	            plan=_plan(),
   991	            artifact_profiles={
   992	                "123": {
   993	                    "path": 123,
   994	                    "profile": _profile().to_dict(),
   995	                    "sha256": SHA_B,
   996	                    "attachments": {},
   997	                }
   998	            },
   999	        )
  1000	    with pytest.raises(TypeError, match="mapping keys must be strings"):
  1001	        assemble_provenance_v2(
  1002	            **base,
  1003	            plan=_plan(),
  1004	            artifact_profiles={123: {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
  1005	        )
  1006	    with pytest.raises(ValueError, match="workspace path"):
  1007	        assemble_provenance_v2(
  1008	            **base,
  1009	            plan=_plan(),
  1010	            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
  1011	        )
  1012	    # Emitted lineage records round-trip: re-passing the emitted sequence
  1013	    # (dictionary records) validates and reproduces the same output.
  1014	    first = assemble_provenance_v2(
  1015	        **base,
  1016	        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
  1017	        artifact_profiles=[
  1018	            VideoArtifact(
  1019	                path="outputs/a.mp4",
  1020	                profile=_profile(audio=False),
  1021	                sha256=SHA_B,
  1022	                duration_frames=24,
  1023	            ),
  1024	            VideoArtifact(
  1025	                path="outputs/b.mp4",
  1026	                profile=_profile(audio=False),
  1027	                sha256=SHA_C,
  1028	                duration_frames=24,
  1029	            ),
  1030	        ],
  1031	    )
  1032	    second = assemble_provenance_v2(
  1033	        **base,
  1034	        plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
  1035	        artifact_profiles=first["artifact_profiles"],
  1036	    )
  1037	    assert second["artifact_profiles"] == first["artifact_profiles"]
  1038	    with pytest.raises(ValueError, match="duplicate path"):
  1039	        assemble_provenance_v2(
  1040	            **base,
  1041	            plan=_plan(
  1042	                segments=[_segment(0, 24), _segment(24, 48)]
  1043	            ),
  1044	            artifact_profiles=[
  1045	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_B, duration_frames=48),
  1046	                VideoArtifact(path="outputs/a.mp4", profile=_profile(audio=False), sha256=SHA_C, duration_frames=48),
  1047	            ],
  1048	        )
  1049	    # A mutated VideoArtifact instance is reconstructed at the boundary, so a
  1050	    # smuggled escaped path cannot pass validation.
  1051	    with pytest.raises(ValueError, match="workspace path"):
  1052	        mutated = VideoArtifact(
  1053	            path="outputs/a.mp4",
  1054	            profile=_profile(audio=False),
  1055	            sha256=SHA_B,
  1056	            duration_frames=48,
  1057	        )
  1058	        object.__setattr__(mutated, "path", "../escape.mp4")
  1059	        assemble_provenance_v2(
  1060	            **base,
  1061	            plan=_plan(),
  1062	            artifact_profiles=[mutated],
  1063	        )
  1064	    with pytest.raises(RendererProtocolError, match="positive-frame plan"):
  1065	        positive = _plan()
  1066	        object.__setattr__(positive, "segments", [])
  1067	        assemble_provenance_v2(
  1068	            **base,
  1069	            plan=positive,
  1070	            artifact_profiles=[],
  1071	        )
  1072	
  1073	
  1074	def test_plan_accepts_adjacent_segments_and_exact_window_coverage() -> None:
  1075	    plan = _plan(
  1076	        segments=[_segment(12, 24), _segment(24, 36)],
  1077	        total_frames=48,
  1078	        window=_window(12, 36),
  1079	    )
  1080	    assert plan.total_frames == 48
  1081	    assert plan.window == _window(12, 36)
  1082	
  1083	
  1084	@pytest.mark.parametrize(
  1085	    ("segments", "total_frames", "match"),
  1086	    [
  1087	        ([_segment(1, 48)], 48, "gap"),
  1088	        ([_segment(0, 47)], 48, "trailing gap"),
  1089	        ([_segment(0, 20), _segment(21, 48)], 48, "gap"),
  1090	        ([_segment(0, 25), _segment(24, 48)], 48, "overlaps"),
  1091	        ([_segment(24, 48), _segment(0, 24)], 48, "gap"),
  1092	    ],
  1093	)
  1094	def test_plan_rejects_gaps_overlaps_and_out_of_order_segments(
  1095	    segments: list[RenderSegment],

exec
/bin/zsh -lc "rg -n --fixed-strings '\\u0085' tests astrid/core/rendering astrid/packs || true; rg -n --fixed-strings '\\uFEFF' tests astrid/core/rendering astrid/packs || true; git show --format=fuller --stat --oneline 670d5f8; git diff --check 8e4f640..670d5f8" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
astrid/core/rendering/contracts.py:43:# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
astrid/core/rendering/contracts.py:43:# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
670d5f8 batch1-rework13: oracle re-review12 issues 1-2 (ECMA whitespace in sequence path check, no str() coercion of mapping keys or embedded paths)
 .oracle/checkins/batch-1-r12.md        | 8482 ++++++++++++++++++++++++++++++++
 astrid/core/rendering/provenance.py    |   14 +-
 tests/core/rendering/test_contracts.py |   20 +
 3 files changed, 8512 insertions(+), 4 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r12.md:303: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:304: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:306: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1202: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:1204: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:1206: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1208: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:1210: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:1212: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1214: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:1216: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:1218: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1220: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:1222: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:1224: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1226: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:1228: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:1230: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1232: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1234: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1236: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1238: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1240: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1242: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1244: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1246: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1248: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1250: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1252: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1254: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1256: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1258: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1260: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1262: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1264: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1266: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1268: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1270: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1272: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1274: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1276: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1278: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1280: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1282: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1284: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1286: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1288: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1290: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1292: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1294: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1296: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1298: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1300: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1302: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1304: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1306: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1308: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1310: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1312: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1314: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1316: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1318: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1320: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1322: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1324: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1326: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1328: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1330: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1332: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1334: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1336: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1338: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1340: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1342: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1344: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1346: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1348: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1350: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1352: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1354: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1356: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1358: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1360: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1362: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1364: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1366: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1368: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1370: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1372: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1374: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1376: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1378: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1380: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1382: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1384: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1386: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1388: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1390: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1392: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1394: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1396: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1398: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1400: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1402: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1404: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1406: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1408: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1410: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1412: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1414: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1416: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1418: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1420: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1422: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1424: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1426: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1428: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1430: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1432: trailing whitespace.
+++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:1434: trailing whitespace.
+++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:1436: trailing whitespace.
+++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:1438: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1440: trailing whitespace.
+++++   730	
.oracle/checkins/batch-1-r12.md:1442: trailing whitespace.
+++++   731	
.oracle/checkins/batch-1-r12.md:1444: trailing whitespace.
+++++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-1-r12.md:1446: trailing whitespace.
+++++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-1-r12.md:1448: trailing whitespace.
+++++   453	
.oracle/checkins/batch-1-r12.md:1450: trailing whitespace.
+++++   461	
.oracle/checkins/batch-1-r12.md:1452: trailing whitespace.
+++++   463	
.oracle/checkins/batch-1-r12.md:1454: trailing whitespace.
+++++   465	
.oracle/checkins/batch-1-r12.md:1456: trailing whitespace.
+++++   470	
.oracle/checkins/batch-1-r12.md:1458: trailing whitespace.
+++++   492	
.oracle/checkins/batch-1-r12.md:1460: trailing whitespace.
+++++   520	
.oracle/checkins/batch-1-r12.md:1462: trailing whitespace.
+++++   539	
.oracle/checkins/batch-1-r12.md:1464: trailing whitespace.
+++++   540	
.oracle/checkins/batch-1-r12.md:1466: trailing whitespace.
+++++   550	
.oracle/checkins/batch-1-r12.md:1468: trailing whitespace.
+++++   551	
.oracle/checkins/batch-1-r12.md:1470: trailing whitespace.
+++++   609	
.oracle/checkins/batch-1-r12.md:1472: trailing whitespace.
+++++   613	
.oracle/checkins/batch-1-r12.md:1474: trailing whitespace.
+++++   614	
.oracle/checkins/batch-1-r12.md:1476: trailing whitespace.
+++++   627	
.oracle/checkins/batch-1-r12.md:1478: trailing whitespace.
+++++   628	
.oracle/checkins/batch-1-r12.md:1480: trailing whitespace.
+++++   631	
.oracle/checkins/batch-1-r12.md:1482: trailing whitespace.
+++++   640	
.oracle/checkins/batch-1-r12.md:1484: trailing whitespace.
+++++   641	
.oracle/checkins/batch-1-r12.md:1486: trailing whitespace.
+++++   647	
.oracle/checkins/batch-1-r12.md:1488: trailing whitespace.
+++++   648	
.oracle/checkins/batch-1-r12.md:1490: trailing whitespace.
+++++   679	
.oracle/checkins/batch-1-r12.md:1492: trailing whitespace.
+++++   689	
.oracle/checkins/batch-1-r12.md:1494: trailing whitespace.
+++++   721	
.oracle/checkins/batch-1-r12.md:1496: trailing whitespace.
+++++   722	
.oracle/checkins/batch-1-r12.md:1498: trailing whitespace.
+++++   740	
.oracle/checkins/batch-1-r12.md:1500: trailing whitespace.
+++++   741	
.oracle/checkins/batch-1-r12.md:1502: trailing whitespace.
+++++   777	
.oracle/checkins/batch-1-r12.md:1504: trailing whitespace.
+++++   778	
.oracle/checkins/batch-1-r12.md:1506: trailing whitespace.
+++++   792	
.oracle/checkins/batch-1-r12.md:1508: trailing whitespace.
+++++   793	
.oracle/checkins/batch-1-r12.md:1510: trailing whitespace.
+++++   809	
.oracle/checkins/batch-1-r12.md:1512: trailing whitespace.
+++++   810	
.oracle/checkins/batch-1-r12.md:1514: trailing whitespace.
+++++   904	
.oracle/checkins/batch-1-r12.md:1516: trailing whitespace.
+++++   905	
.oracle/checkins/batch-1-r12.md:1518: trailing whitespace.
+++++   965	
.oracle/checkins/batch-1-r12.md:1520: trailing whitespace.
+++++   966	
.oracle/checkins/batch-1-r12.md:1522: trailing whitespace.
+++++   975	
.oracle/checkins/batch-1-r12.md:1524: trailing whitespace.
+++++   976	
.oracle/checkins/batch-1-r12.md:1526: trailing whitespace.
+++++     2	
.oracle/checkins/batch-1-r12.md:1528: trailing whitespace.
+++++     4	
.oracle/checkins/batch-1-r12.md:1530: trailing whitespace.
+++++     8	
.oracle/checkins/batch-1-r12.md:1532: trailing whitespace.
+++++    11	
.oracle/checkins/batch-1-r12.md:1534: trailing whitespace.
+++++    28	
.oracle/checkins/batch-1-r12.md:1536: trailing whitespace.
+++++    29	
.oracle/checkins/batch-1-r12.md:1538: trailing whitespace.
+++++    32	
.oracle/checkins/batch-1-r12.md:1540: trailing whitespace.
+++++    33	
.oracle/checkins/batch-1-r12.md:1542: trailing whitespace.
+++++    38	
.oracle/checkins/batch-1-r12.md:1544: trailing whitespace.
+++++    40	
.oracle/checkins/batch-1-r12.md:1546: trailing whitespace.
+++++    41	
.oracle/checkins/batch-1-r12.md:1548: trailing whitespace.
+++++    53	
.oracle/checkins/batch-1-r12.md:1550: trailing whitespace.
+++++    54	
.oracle/checkins/batch-1-r12.md:1552: trailing whitespace.
+++++    81	
.oracle/checkins/batch-1-r12.md:1554: trailing whitespace.
+++++    82	
.oracle/checkins/batch-1-r12.md:1556: trailing whitespace.
+++++    85	
.oracle/checkins/batch-1-r12.md:1558: trailing whitespace.
+++++    92	
.oracle/checkins/batch-1-r12.md:1560: trailing whitespace.
+++++    93	
.oracle/checkins/batch-1-r12.md:1562: trailing whitespace.
+++++   105	
.oracle/checkins/batch-1-r12.md:1564: trailing whitespace.
+++++   106	
.oracle/checkins/batch-1-r12.md:1566: trailing whitespace.
+++++   168	
.oracle/checkins/batch-1-r12.md:1568: trailing whitespace.
+++++   169	
.oracle/checkins/batch-1-r12.md:1570: trailing whitespace.
+++++   236	
.oracle/checkins/batch-1-r12.md:1572: trailing whitespace.
+++++   237	
.oracle/checkins/batch-1-r12.md:1574: trailing whitespace.
+++++   248	
.oracle/checkins/batch-1-r12.md:1576: trailing whitespace.
+++++   249	
.oracle/checkins/batch-1-r12.md:1578: trailing whitespace.
+++++   271	
.oracle/checkins/batch-1-r12.md:1580: trailing whitespace.
+++++   272	
.oracle/checkins/batch-1-r12.md:1582: trailing whitespace.
+++++   288	
.oracle/checkins/batch-1-r12.md:1584: trailing whitespace.
+++++   295	
.oracle/checkins/batch-1-r12.md:1586: trailing whitespace.
+++++   316	
.oracle/checkins/batch-1-r12.md:1588: trailing whitespace.
+++++   343	
.oracle/checkins/batch-1-r12.md:1590: trailing whitespace.
+++++   344	
.oracle/checkins/batch-1-r12.md:1592: trailing whitespace.
+++++   347	
.oracle/checkins/batch-1-r12.md:1594: trailing whitespace.
+++++   349	
.oracle/checkins/batch-1-r12.md:1596: trailing whitespace.
+++++   350	
.oracle/checkins/batch-1-r12.md:1598: trailing whitespace.
+++++   353	
.oracle/checkins/batch-1-r12.md:1600: trailing whitespace.
+++++   357	
.oracle/checkins/batch-1-r12.md:1602: trailing whitespace.
+++++   358	
.oracle/checkins/batch-1-r12.md:1604: trailing whitespace.
+++++   361	
.oracle/checkins/batch-1-r12.md:1606: trailing whitespace.
+++++   366	
.oracle/checkins/batch-1-r12.md:1608: trailing whitespace.
+++++   367	
.oracle/checkins/batch-1-r12.md:1610: trailing whitespace.
+++++   370	
.oracle/checkins/batch-1-r12.md:1612: trailing whitespace.
+++++     2	
.oracle/checkins/batch-1-r12.md:1614: trailing whitespace.
+++++     8	
.oracle/checkins/batch-1-r12.md:1616: trailing whitespace.
+++++    10	
.oracle/checkins/batch-1-r12.md:1618: trailing whitespace.
+++++    18	
.oracle/checkins/batch-1-r12.md:1620: trailing whitespace.
+++++    21	
.oracle/checkins/batch-1-r12.md:1622: trailing whitespace.
+++++    22	
.oracle/checkins/batch-1-r12.md:1624: trailing whitespace.
+++++    24	
.oracle/checkins/batch-1-r12.md:1626: trailing whitespace.
+++++    35	
.oracle/checkins/batch-1-r12.md:1628: trailing whitespace.
+++++    40	
.oracle/checkins/batch-1-r12.md:1630: trailing whitespace.
+++++    52	
.oracle/checkins/batch-1-r12.md:1632: trailing whitespace.
+++++    73	
.oracle/checkins/batch-1-r12.md:1634: trailing whitespace.
+++++    93	
.oracle/checkins/batch-1-r12.md:1636: trailing whitespace.
+++++   110	
.oracle/checkins/batch-1-r12.md:1638: trailing whitespace.
+++++   123	
.oracle/checkins/batch-1-r12.md:1640: trailing whitespace.
+++++   130	
.oracle/checkins/batch-1-r12.md:1642: trailing whitespace.
+++++   131	
.oracle/checkins/batch-1-r12.md:1644: trailing whitespace.
+++++   134	
.oracle/checkins/batch-1-r12.md:1646: trailing whitespace.
+++++   158	
.oracle/checkins/batch-1-r12.md:1648: trailing whitespace.
+++++   159	
.oracle/checkins/batch-1-r12.md:1650: trailing whitespace.
+++++   165	
.oracle/checkins/batch-1-r12.md:1652: trailing whitespace.
+++++   166	
.oracle/checkins/batch-1-r12.md:1654: trailing whitespace.
+++++   171	
.oracle/checkins/batch-1-r12.md:1656: trailing whitespace.
+++++   172	
.oracle/checkins/batch-1-r12.md:1658: trailing whitespace.
+++++   186	
.oracle/checkins/batch-1-r12.md:1660: trailing whitespace.
+++++   187	
.oracle/checkins/batch-1-r12.md:1662: trailing whitespace.
+++++   194	
.oracle/checkins/batch-1-r12.md:1664: trailing whitespace.
+++++   195	
.oracle/checkins/batch-1-r12.md:1666: trailing whitespace.
+++++   205	
.oracle/checkins/batch-1-r12.md:1668: trailing whitespace.
+++++   206	
.oracle/checkins/batch-1-r12.md:1670: trailing whitespace.
+++++   209	
.oracle/checkins/batch-1-r12.md:1672: trailing whitespace.
+++++   215	
.oracle/checkins/batch-1-r12.md:1674: trailing whitespace.
+++++   216	
.oracle/checkins/batch-1-r12.md:1676: trailing whitespace.
+++++   225	
.oracle/checkins/batch-1-r12.md:1678: trailing whitespace.
+++++   226	
.oracle/checkins/batch-1-r12.md:1680: trailing whitespace.
+++++   231	
.oracle/checkins/batch-1-r12.md:1682: trailing whitespace.
+++++   232	
.oracle/checkins/batch-1-r12.md:1684: trailing whitespace.
+++++   241	
.oracle/checkins/batch-1-r12.md:1686: trailing whitespace.
+++++   242	
.oracle/checkins/batch-1-r12.md:1688: trailing whitespace.
+++++   248	
.oracle/checkins/batch-1-r12.md:1690: trailing whitespace.
+++++   249	
.oracle/checkins/batch-1-r12.md:1692: trailing whitespace.
+++++   507	
.oracle/checkins/batch-1-r12.md:1694: trailing whitespace.
+++++   511	
.oracle/checkins/batch-1-r12.md:1696: trailing whitespace.
+++++   530	
.oracle/checkins/batch-1-r12.md:1698: trailing whitespace.
+++++   563	
.oracle/checkins/batch-1-r12.md:1700: trailing whitespace.
+++++   564	
.oracle/checkins/batch-1-r12.md:1702: trailing whitespace.
+++++   571	
.oracle/checkins/batch-1-r12.md:1704: trailing whitespace.
+++++   576	
.oracle/checkins/batch-1-r12.md:1706: trailing whitespace.
+++++   582	
.oracle/checkins/batch-1-r12.md:1708: trailing whitespace.
+++++   583	
.oracle/checkins/batch-1-r12.md:1710: trailing whitespace.
+++++   587	
.oracle/checkins/batch-1-r12.md:1712: trailing whitespace.
+++++   592	
.oracle/checkins/batch-1-r12.md:1714: trailing whitespace.
+++++   604	
.oracle/checkins/batch-1-r12.md:1716: trailing whitespace.
+++++   609	
.oracle/checkins/batch-1-r12.md:1718: trailing whitespace.
+++++   621	
.oracle/checkins/batch-1-r12.md:1720: trailing whitespace.
+++++   633	
.oracle/checkins/batch-1-r12.md:1722: trailing whitespace.
+++++   634	
.oracle/checkins/batch-1-r12.md:1724: trailing whitespace.
+++++   655	
.oracle/checkins/batch-1-r12.md:1726: trailing whitespace.
+++++   656	
.oracle/checkins/batch-1-r12.md:1728: trailing whitespace.
+++++   660	
.oracle/checkins/batch-1-r12.md:1730: trailing whitespace.
+++++   667	
.oracle/checkins/batch-1-r12.md:1732: trailing whitespace.
+++++   690	
.oracle/checkins/batch-1-r12.md:1734: trailing whitespace.
+++++   702	
.oracle/checkins/batch-1-r12.md:1736: trailing whitespace.
+++++   717	
.oracle/checkins/batch-1-r12.md:1738: trailing whitespace.
+++++  1662	
.oracle/checkins/batch-1-r12.md:1740: trailing whitespace.
+++++  1686	
.oracle/checkins/batch-1-r12.md:1742: trailing whitespace.
+++++  1693	
.oracle/checkins/batch-1-r12.md:1744: trailing whitespace.
+++++  1694	
.oracle/checkins/batch-1-r12.md:1746: trailing whitespace.
+++++  1698	
.oracle/checkins/batch-1-r12.md:1748: trailing whitespace.
+++++  1705	
.oracle/checkins/batch-1-r12.md:1750: trailing whitespace.
+++++  1753	
.oracle/checkins/batch-1-r12.md:1752: trailing whitespace.
+++++  1757	
.oracle/checkins/batch-1-r12.md:1754: trailing whitespace.
+++++  1763	
.oracle/checkins/batch-1-r12.md:1756: trailing whitespace.
+++++  1769	
.oracle/checkins/batch-1-r12.md:1758: trailing whitespace.
+++++  1773	
.oracle/checkins/batch-1-r12.md:1760: trailing whitespace.
+++++     2	
.oracle/checkins/batch-1-r12.md:1762: trailing whitespace.
+++++     8	
.oracle/checkins/batch-1-r12.md:1764: trailing whitespace.
+++++    11	
.oracle/checkins/batch-1-r12.md:1766: trailing whitespace.
+++++    20	
.oracle/checkins/batch-1-r12.md:1768: trailing whitespace.
+++++    21	
.oracle/checkins/batch-1-r12.md:1770: trailing whitespace.
+++++    48	
.oracle/checkins/batch-1-r12.md:1772: trailing whitespace.
+++++    49	
.oracle/checkins/batch-1-r12.md:1774: trailing whitespace.
+++++    52	
.oracle/checkins/batch-1-r12.md:1776: trailing whitespace.
+++++    53	
.oracle/checkins/batch-1-r12.md:1778: trailing whitespace.
+++++    56	
.oracle/checkins/batch-1-r12.md:1780: trailing whitespace.
+++++    57	
.oracle/checkins/batch-1-r12.md:1782: trailing whitespace.
+++++    60	
.oracle/checkins/batch-1-r12.md:1784: trailing whitespace.
+++++    61	
.oracle/checkins/batch-1-r12.md:1786: trailing whitespace.
+++++    72	
.oracle/checkins/batch-1-r12.md:1788: trailing whitespace.
+++++    73	
.oracle/checkins/batch-1-r12.md:1790: trailing whitespace.
+++++    81	
.oracle/checkins/batch-1-r12.md:1792: trailing whitespace.
+++++    88	
.oracle/checkins/batch-1-r12.md:1794: trailing whitespace.
+++++    89	
.oracle/checkins/batch-1-r12.md:1796: trailing whitespace.
+++++    96	
.oracle/checkins/batch-1-r12.md:1798: trailing whitespace.
+++++    97	
.oracle/checkins/batch-1-r12.md:1800: trailing whitespace.
+++++   105	
.oracle/checkins/batch-1-r12.md:1802: trailing whitespace.
+++++   106	
.oracle/checkins/batch-1-r12.md:1804: trailing whitespace.
+++++   113	
.oracle/checkins/batch-1-r12.md:1806: trailing whitespace.
+++++   114	
.oracle/checkins/batch-1-r12.md:1808: trailing whitespace.
+++++   312	
.oracle/checkins/batch-1-r12.md:1810: trailing whitespace.
+++++   313	
.oracle/checkins/batch-1-r12.md:1812: trailing whitespace.
+++++   324	
.oracle/checkins/batch-1-r12.md:1814: trailing whitespace.
+++++   325	
.oracle/checkins/batch-1-r12.md:1816: trailing whitespace.
+++++   338	
.oracle/checkins/batch-1-r12.md:1818: trailing whitespace.
+++++   339	
.oracle/checkins/batch-1-r12.md:1820: trailing whitespace.
+++++   356	
.oracle/checkins/batch-1-r12.md:1822: trailing whitespace.
+++++   357	
.oracle/checkins/batch-1-r12.md:1824: trailing whitespace.
+++++   375	
.oracle/checkins/batch-1-r12.md:1826: trailing whitespace.
+++++   376	
.oracle/checkins/batch-1-r12.md:1828: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1830: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1832: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1834: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1836: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1838: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1840: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1842: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1844: trailing whitespace.
+++++ 
.oracle/checkins/batch-1-r12.md:1846: trailing whitespace.
+++++   809	
.oracle/checkins/batch-1-r12.md:1848: trailing whitespace.
+++++   810	
.oracle/checkins/batch-1-r12.md:1850: trailing whitespace.
+++++   904	
.oracle/checkins/batch-1-r12.md:1852: trailing whitespace.
+++++   905	
.oracle/checkins/batch-1-r12.md:1854: trailing whitespace.
+++++   965	
.oracle/checkins/batch-1-r12.md:1856: trailing whitespace.
+++++   966	
.oracle/checkins/batch-1-r12.md:1858: trailing whitespace.
+++++     2	
.oracle/checkins/batch-1-r12.md:1860: trailing whitespace.
+++++     4	
.oracle/checkins/batch-1-r12.md:1862: trailing whitespace.
+++++     6	
.oracle/checkins/batch-1-r12.md:1864: trailing whitespace.
+++++     8	
.oracle/checkins/batch-1-r12.md:1866: trailing whitespace.
+++++    17	
.oracle/checkins/batch-1-r12.md:1868: trailing whitespace.
+++++    19	
.oracle/checkins/batch-1-r12.md:1870: trailing whitespace.
+++++    25	
.oracle/checkins/batch-1-r12.md:1872: trailing whitespace.
+++++    27	
.oracle/checkins/batch-1-r12.md:1874: trailing whitespace.
+++++    29	
.oracle/checkins/batch-1-r12.md:1876: trailing whitespace.
+++++    31	
.oracle/checkins/batch-1-r12.md:1878: trailing whitespace.
+++++    40	
.oracle/checkins/batch-1-r12.md:1880: trailing whitespace.
+++++    42	
.oracle/checkins/batch-1-r12.md:1882: trailing whitespace.
+++++    49	
.oracle/checkins/batch-1-r12.md:1884: trailing whitespace.
+++++    51	
.oracle/checkins/batch-1-r12.md:1886: trailing whitespace.
+++++    53	
.oracle/checkins/batch-1-r12.md:1888: trailing whitespace.
+++++    55	
.oracle/checkins/batch-1-r12.md:1890: trailing whitespace.
+++++    63	
.oracle/checkins/batch-1-r12.md:1892: trailing whitespace.
+++++    65	
.oracle/checkins/batch-1-r12.md:1894: trailing whitespace.
+++++    72	
.oracle/checkins/batch-1-r12.md:1896: trailing whitespace.
+++++    74	
.oracle/checkins/batch-1-r12.md:1898: trailing whitespace.
+++++    76	
.oracle/checkins/batch-1-r12.md:1900: trailing whitespace.
+++++    78	
.oracle/checkins/batch-1-r12.md:1902: trailing whitespace.
+++++   131	
.oracle/checkins/batch-1-r12.md:1904: trailing whitespace.
+++++   132	
.oracle/checkins/batch-1-r12.md:1906: trailing whitespace.
+++++   162	
.oracle/checkins/batch-1-r12.md:1908: trailing whitespace.
+++++   163	
.oracle/checkins/batch-1-r12.md:1910: trailing whitespace.
+++++   178	
.oracle/checkins/batch-1-r12.md:1912: trailing whitespace.
+++++   179	
.oracle/checkins/batch-1-r12.md:1914: trailing whitespace.
+++++   206	
.oracle/checkins/batch-1-r12.md:1916: trailing whitespace.
+++++   207	
.oracle/checkins/batch-1-r12.md:1918: trailing whitespace.
+++++   249	
.oracle/checkins/batch-1-r12.md:1920: trailing whitespace.
+++++   250	
.oracle/checkins/batch-1-r12.md:1922: trailing whitespace.
+++++   288	
.oracle/checkins/batch-1-r12.md:1924: trailing whitespace.
+++++   289	
.oracle/checkins/batch-1-r12.md:1926: trailing whitespace.
+++++   302	
.oracle/checkins/batch-1-r12.md:1928: trailing whitespace.
+++++   303	
.oracle/checkins/batch-1-r12.md:1930: trailing whitespace.
+++++   312	
.oracle/checkins/batch-1-r12.md:1932: trailing whitespace.
+++++   313	
.oracle/checkins/batch-1-r12.md:1934: trailing whitespace.
+++++   330	
.oracle/checkins/batch-1-r12.md:1936: trailing whitespace.
+++++   331	
.oracle/checkins/batch-1-r12.md:1938: trailing whitespace.
+++++   343	
.oracle/checkins/batch-1-r12.md:1940: trailing whitespace.
+++++   344	
.oracle/checkins/batch-1-r12.md:1942: trailing whitespace.
+++++   288	
.oracle/checkins/batch-1-r12.md:1944: trailing whitespace.
+++++    98	
.oracle/checkins/batch-1-r12.md:1946: trailing whitespace.
+++++   101	
.oracle/checkins/batch-1-r12.md:1948: trailing whitespace.
+++++   106	
.oracle/checkins/batch-1-r12.md:1950: trailing whitespace.
+++++   107	
.oracle/checkins/batch-1-r12.md:1952: trailing whitespace.
+++++   110	
.oracle/checkins/batch-1-r12.md:1954: trailing whitespace.
+++++   113	
.oracle/checkins/batch-1-r12.md:1956: trailing whitespace.
+++++  1349	
.oracle/checkins/batch-1-r12.md:1958: trailing whitespace.
+++++  1350	
.oracle/checkins/batch-1-r12.md:1960: trailing whitespace.
+++++  1354	
.oracle/checkins/batch-1-r12.md:1962: trailing whitespace.
+++++  1365	
.oracle/checkins/batch-1-r12.md:1964: trailing whitespace.
+++++  1444	
.oracle/checkins/batch-1-r12.md:1966: trailing whitespace.
+++++  1460	
.oracle/checkins/batch-1-r12.md:1968: trailing whitespace.
++++  1444	
.oracle/checkins/batch-1-r12.md:1970: trailing whitespace.
++++  1460	
.oracle/checkins/batch-1-r12.md:1972: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1974: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1976: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1978: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1980: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1982: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1984: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1986: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1988: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1990: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1992: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1994: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1996: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:1998: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2000: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2002: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2004: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2006: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2008: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2010: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2012: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2014: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2016: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2018: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2020: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2022: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2024: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2026: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2028: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2030: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2032: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2034: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2036: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2038: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2040: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2042: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2044: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2046: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2048: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2050: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2052: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2054: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2056: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2058: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2060: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2062: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2064: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2066: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2068: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2070: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2072: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2074: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2076: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2078: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2080: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2082: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2084: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2086: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2088: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2090: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2092: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2094: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2096: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2098: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2100: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2102: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2104: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2106: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2108: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2110: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2112: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2114: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2116: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2118: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2120: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2122: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2124: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2126: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2128: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2130: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2132: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2134: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2136: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2138: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2140: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2142: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2144: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2146: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2148: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2150: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2152: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2154: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2156: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2158: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2160: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2162: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2164: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2166: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2168: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2170: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2172: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2174: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2176: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2178: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2180: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2182: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2184: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2186: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2188: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2190: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2192: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2194: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2196: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2198: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2200: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2202: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2204: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r12.md:2206: trailing whitespace.
++++     4	
.oracle/checkins/batch-1-r12.md:2208: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r12.md:2210: trailing whitespace.
++++    11	
.oracle/checkins/batch-1-r12.md:2212: trailing whitespace.
++++    28	
.oracle/checkins/batch-1-r12.md:2214: trailing whitespace.
++++    29	
.oracle/checkins/batch-1-r12.md:2216: trailing whitespace.
++++    32	
.oracle/checkins/batch-1-r12.md:2218: trailing whitespace.
++++    33	
.oracle/checkins/batch-1-r12.md:2220: trailing whitespace.
++++    38	
.oracle/checkins/batch-1-r12.md:2222: trailing whitespace.
++++    40	
.oracle/checkins/batch-1-r12.md:2224: trailing whitespace.
++++    41	
.oracle/checkins/batch-1-r12.md:2226: trailing whitespace.
++++    53	
.oracle/checkins/batch-1-r12.md:2228: trailing whitespace.
++++    54	
.oracle/checkins/batch-1-r12.md:2230: trailing whitespace.
++++    81	
.oracle/checkins/batch-1-r12.md:2232: trailing whitespace.
++++    82	
.oracle/checkins/batch-1-r12.md:2234: trailing whitespace.
++++    85	
.oracle/checkins/batch-1-r12.md:2236: trailing whitespace.
++++    92	
.oracle/checkins/batch-1-r12.md:2238: trailing whitespace.
++++    93	
.oracle/checkins/batch-1-r12.md:2240: trailing whitespace.
++++   105	
.oracle/checkins/batch-1-r12.md:2242: trailing whitespace.
++++   106	
.oracle/checkins/batch-1-r12.md:2244: trailing whitespace.
++++   173	
.oracle/checkins/batch-1-r12.md:2246: trailing whitespace.
++++   174	
.oracle/checkins/batch-1-r12.md:2248: trailing whitespace.
++++   248	
.oracle/checkins/batch-1-r12.md:2250: trailing whitespace.
++++   249	
.oracle/checkins/batch-1-r12.md:2252: trailing whitespace.
++++   260	
.oracle/checkins/batch-1-r12.md:2254: trailing whitespace.
++++   261	
.oracle/checkins/batch-1-r12.md:2256: trailing whitespace.
++++   283	
.oracle/checkins/batch-1-r12.md:2258: trailing whitespace.
++++   284	
.oracle/checkins/batch-1-r12.md:2260: trailing whitespace.
++++   300	
.oracle/checkins/batch-1-r12.md:2262: trailing whitespace.
++++   307	
.oracle/checkins/batch-1-r12.md:2264: trailing whitespace.
++++   328	
.oracle/checkins/batch-1-r12.md:2266: trailing whitespace.
++++   355	
.oracle/checkins/batch-1-r12.md:2268: trailing whitespace.
++++   356	
.oracle/checkins/batch-1-r12.md:2270: trailing whitespace.
++++   359	
.oracle/checkins/batch-1-r12.md:2272: trailing whitespace.
++++   361	
.oracle/checkins/batch-1-r12.md:2274: trailing whitespace.
++++   362	
.oracle/checkins/batch-1-r12.md:2276: trailing whitespace.
++++   365	
.oracle/checkins/batch-1-r12.md:2278: trailing whitespace.
++++   369	
.oracle/checkins/batch-1-r12.md:2280: trailing whitespace.
++++   370	
.oracle/checkins/batch-1-r12.md:2282: trailing whitespace.
++++   373	
.oracle/checkins/batch-1-r12.md:2284: trailing whitespace.
++++   378	
.oracle/checkins/batch-1-r12.md:2286: trailing whitespace.
++++   379	
.oracle/checkins/batch-1-r12.md:2288: trailing whitespace.
++++   382	
.oracle/checkins/batch-1-r12.md:2290: trailing whitespace.
++++   384	
.oracle/checkins/batch-1-r12.md:2292: trailing whitespace.
++++   385	
.oracle/checkins/batch-1-r12.md:2294: trailing whitespace.
++++   651	
.oracle/checkins/batch-1-r12.md:2296: trailing whitespace.
++++   652	
.oracle/checkins/batch-1-r12.md:2298: trailing whitespace.
++++   683	
.oracle/checkins/batch-1-r12.md:2300: trailing whitespace.
++++   693	
.oracle/checkins/batch-1-r12.md:2302: trailing whitespace.
++++   729	
.oracle/checkins/batch-1-r12.md:2304: trailing whitespace.
++++   730	
.oracle/checkins/batch-1-r12.md:2306: trailing whitespace.
++++   748	
.oracle/checkins/batch-1-r12.md:2308: trailing whitespace.
++++   749	
.oracle/checkins/batch-1-r12.md:2310: trailing whitespace.
++++   785	
.oracle/checkins/batch-1-r12.md:2312: trailing whitespace.
++++   786	
.oracle/checkins/batch-1-r12.md:2314: trailing whitespace.
++++   800	
.oracle/checkins/batch-1-r12.md:2316: trailing whitespace.
++++   801	
.oracle/checkins/batch-1-r12.md:2318: trailing whitespace.
++++   817	
.oracle/checkins/batch-1-r12.md:2320: trailing whitespace.
++++   818	
.oracle/checkins/batch-1-r12.md:2322: trailing whitespace.
++++   914	
.oracle/checkins/batch-1-r12.md:2324: trailing whitespace.
++++   915	
.oracle/checkins/batch-1-r12.md:2326: trailing whitespace.
++++  1001	
.oracle/checkins/batch-1-r12.md:2328: trailing whitespace.
++++  1002	
.oracle/checkins/batch-1-r12.md:2330: trailing whitespace.
++++  1011	
.oracle/checkins/batch-1-r12.md:2332: trailing whitespace.
++++  1012	
.oracle/checkins/batch-1-r12.md:2334: trailing whitespace.
++++   285	
.oracle/checkins/batch-1-r12.md:2336: trailing whitespace.
++++   294	
.oracle/checkins/batch-1-r12.md:2338: trailing whitespace.
++++   295	
.oracle/checkins/batch-1-r12.md:2340: trailing whitespace.
++++   302	
.oracle/checkins/batch-1-r12.md:2342: trailing whitespace.
++++   303	
.oracle/checkins/batch-1-r12.md:2344: trailing whitespace.
++++   312	
.oracle/checkins/batch-1-r12.md:2346: trailing whitespace.
++++   313	
.oracle/checkins/batch-1-r12.md:2348: trailing whitespace.
++++   330	
.oracle/checkins/batch-1-r12.md:2350: trailing whitespace.
++++   331	
.oracle/checkins/batch-1-r12.md:2352: trailing whitespace.
++++   826	
.oracle/checkins/batch-1-r12.md:2354: trailing whitespace.
++++   868	
.oracle/checkins/batch-1-r12.md:2356: trailing whitespace.
++++   875	
.oracle/checkins/batch-1-r12.md:2358: trailing whitespace.
++++   878	
.oracle/checkins/batch-1-r12.md:2360: trailing whitespace.
++++   892	
.oracle/checkins/batch-1-r12.md:2362: trailing whitespace.
++++   893	
.oracle/checkins/batch-1-r12.md:2364: trailing whitespace.
++++   897	
.oracle/checkins/batch-1-r12.md:2366: trailing whitespace.
++++   905	
.oracle/checkins/batch-1-r12.md:2368: trailing whitespace.
++++   936	
.oracle/checkins/batch-1-r12.md:2370: trailing whitespace.
++++   949	
.oracle/checkins/batch-1-r12.md:2372: trailing whitespace.
++++   980	
.oracle/checkins/batch-1-r12.md:2374: trailing whitespace.
++++   987	
.oracle/checkins/batch-1-r12.md:2376: trailing whitespace.
++++   988	
.oracle/checkins/batch-1-r12.md:2378: trailing whitespace.
++++   992	
.oracle/checkins/batch-1-r12.md:2380: trailing whitespace.
++++  1000	
.oracle/checkins/batch-1-r12.md:2382: trailing whitespace.
++++   440	
.oracle/checkins/batch-1-r12.md:2384: trailing whitespace.
++++   441	
.oracle/checkins/batch-1-r12.md:2386: trailing whitespace.
++++   445	
.oracle/checkins/batch-1-r12.md:2388: trailing whitespace.
++++   459	
.oracle/checkins/batch-1-r12.md:2390: trailing whitespace.
++++   507	
.oracle/checkins/batch-1-r12.md:2392: trailing whitespace.
++++   511	
.oracle/checkins/batch-1-r12.md:2394: trailing whitespace.
++++   530	
.oracle/checkins/batch-1-r12.md:2396: trailing whitespace.
++++   563	
.oracle/checkins/batch-1-r12.md:2398: trailing whitespace.
++++   564	
.oracle/checkins/batch-1-r12.md:2400: trailing whitespace.
++++   571	
.oracle/checkins/batch-1-r12.md:2402: trailing whitespace.
++++   576	
.oracle/checkins/batch-1-r12.md:2404: trailing whitespace.
++++   582	
.oracle/checkins/batch-1-r12.md:2406: trailing whitespace.
++++   583	
.oracle/checkins/batch-1-r12.md:2408: trailing whitespace.
++++   587	
.oracle/checkins/batch-1-r12.md:2410: trailing whitespace.
++++   592	
.oracle/checkins/batch-1-r12.md:2412: trailing whitespace.
++++   604	
.oracle/checkins/batch-1-r12.md:2414: trailing whitespace.
++++   609	
.oracle/checkins/batch-1-r12.md:2416: trailing whitespace.
++++   621	
.oracle/checkins/batch-1-r12.md:2418: trailing whitespace.
++++   633	
.oracle/checkins/batch-1-r12.md:2420: trailing whitespace.
++++   634	
.oracle/checkins/batch-1-r12.md:2422: trailing whitespace.
++++   655	
.oracle/checkins/batch-1-r12.md:2424: trailing whitespace.
++++   656	
.oracle/checkins/batch-1-r12.md:2426: trailing whitespace.
++++   660	
.oracle/checkins/batch-1-r12.md:2428: trailing whitespace.
++++   667	
.oracle/checkins/batch-1-r12.md:2430: trailing whitespace.
++++   690	
.oracle/checkins/batch-1-r12.md:2432: trailing whitespace.
++++   702	
.oracle/checkins/batch-1-r12.md:2434: trailing whitespace.
++++   717	
.oracle/checkins/batch-1-r12.md:2436: trailing whitespace.
++++   225	
.oracle/checkins/batch-1-r12.md:2438: trailing whitespace.
++++   230	
.oracle/checkins/batch-1-r12.md:2440: trailing whitespace.
++++   238	
.oracle/checkins/batch-1-r12.md:2442: trailing whitespace.
++++   240	
.oracle/checkins/batch-1-r12.md:2444: trailing whitespace.
++++   243	
.oracle/checkins/batch-1-r12.md:2446: trailing whitespace.
++++   251	
.oracle/checkins/batch-1-r12.md:2448: trailing whitespace.
++++   255	
.oracle/checkins/batch-1-r12.md:2450: trailing whitespace.
++++   257	
.oracle/checkins/batch-1-r12.md:2452: trailing whitespace.
++++   262	
.oracle/checkins/batch-1-r12.md:2454: trailing whitespace.
++++   274	
.oracle/checkins/batch-1-r12.md:2456: trailing whitespace.
++++   276	
.oracle/checkins/batch-1-r12.md:2458: trailing whitespace.
++++   280	
.oracle/checkins/batch-1-r12.md:2460: trailing whitespace.
++++   290	
.oracle/checkins/batch-1-r12.md:2462: trailing whitespace.
++++   292	
.oracle/checkins/batch-1-r12.md:2464: trailing whitespace.
++++   461	
.oracle/checkins/batch-1-r12.md:2466: trailing whitespace.
++++   463	
.oracle/checkins/batch-1-r12.md:2468: trailing whitespace.
++++   465	
.oracle/checkins/batch-1-r12.md:2470: trailing whitespace.
++++   470	
.oracle/checkins/batch-1-r12.md:2472: trailing whitespace.
++++   492	
.oracle/checkins/batch-1-r12.md:2474: trailing whitespace.
++++   502	
.oracle/checkins/batch-1-r12.md:2476: trailing whitespace.
++++   504	
.oracle/checkins/batch-1-r12.md:2478: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r12.md:2480: trailing whitespace.
++++     4	
.oracle/checkins/batch-1-r12.md:2482: trailing whitespace.
++++     6	
.oracle/checkins/batch-1-r12.md:2484: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r12.md:2486: trailing whitespace.
++++    17	
.oracle/checkins/batch-1-r12.md:2488: trailing whitespace.
++++    19	
.oracle/checkins/batch-1-r12.md:2490: trailing whitespace.
++++    25	
.oracle/checkins/batch-1-r12.md:2492: trailing whitespace.
++++    27	
.oracle/checkins/batch-1-r12.md:2494: trailing whitespace.
++++    29	
.oracle/checkins/batch-1-r12.md:2496: trailing whitespace.
++++    31	
.oracle/checkins/batch-1-r12.md:2498: trailing whitespace.
++++    40	
.oracle/checkins/batch-1-r12.md:2500: trailing whitespace.
++++    42	
.oracle/checkins/batch-1-r12.md:2502: trailing whitespace.
++++    49	
.oracle/checkins/batch-1-r12.md:2504: trailing whitespace.
++++    51	
.oracle/checkins/batch-1-r12.md:2506: trailing whitespace.
++++    53	
.oracle/checkins/batch-1-r12.md:2508: trailing whitespace.
++++    55	
.oracle/checkins/batch-1-r12.md:2510: trailing whitespace.
++++    63	
.oracle/checkins/batch-1-r12.md:2512: trailing whitespace.
++++    65	
.oracle/checkins/batch-1-r12.md:2514: trailing whitespace.
++++    72	
.oracle/checkins/batch-1-r12.md:2516: trailing whitespace.
++++    74	
.oracle/checkins/batch-1-r12.md:2518: trailing whitespace.
++++    76	
.oracle/checkins/batch-1-r12.md:2520: trailing whitespace.
++++    78	
.oracle/checkins/batch-1-r12.md:2522: trailing whitespace.
++++    86	
.oracle/checkins/batch-1-r12.md:2524: trailing whitespace.
++++    88	
.oracle/checkins/batch-1-r12.md:2526: trailing whitespace.
++++    94	
.oracle/checkins/batch-1-r12.md:2528: trailing whitespace.
++++    96	
.oracle/checkins/batch-1-r12.md:2530: trailing whitespace.
++++    98	
.oracle/checkins/batch-1-r12.md:2532: trailing whitespace.
++++   100	
.oracle/checkins/batch-1-r12.md:2534: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2536: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2538: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2540: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2542: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2544: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r12.md:2546: trailing whitespace.
++++   105	
.oracle/checkins/batch-1-r12.md:2548: trailing whitespace.
++++   106	
.oracle/checkins/batch-1-r12.md:2550: trailing whitespace.
++++   168	
.oracle/checkins/batch-1-r12.md:2552: trailing whitespace.
++++   169	
.oracle/checkins/batch-1-r12.md:2554: trailing whitespace.
++++   236	
.oracle/checkins/batch-1-r12.md:2556: trailing whitespace.
++++   237	
.oracle/checkins/batch-1-r12.md:2558: trailing whitespace.
++++   248	
.oracle/checkins/batch-1-r12.md:2560: trailing whitespace.
++++   249	
.oracle/checkins/batch-1-r12.md:2562: trailing whitespace.
++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-1-r12.md:2564: trailing whitespace.
++++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-1-r12.md:2566: trailing whitespace.
++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-1-r12.md:2568: trailing whitespace.
++++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-1-r12.md:2570: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r12.md:2572: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r12.md:2574: trailing whitespace.
++++    11	
.oracle/checkins/batch-1-r12.md:2576: trailing whitespace.
++++    20	
.oracle/checkins/batch-1-r12.md:2578: trailing whitespace.
++++    21	
.oracle/checkins/batch-1-r12.md:2580: trailing whitespace.
++++    48	
.oracle/checkins/batch-1-r12.md:2582: trailing whitespace.
++++    49	
.oracle/checkins/batch-1-r12.md:2584: trailing whitespace.
++++    52	
.oracle/checkins/batch-1-r12.md:2586: trailing whitespace.
++++    53	
.oracle/checkins/batch-1-r12.md:2588: trailing whitespace.
++++    56	
.oracle/checkins/batch-1-r12.md:2590: trailing whitespace.
++++    57	
.oracle/checkins/batch-1-r12.md:2592: trailing whitespace.
++++    60	
.oracle/checkins/batch-1-r12.md:2594: trailing whitespace.
++++    61	
.oracle/checkins/batch-1-r12.md:2596: trailing whitespace.
++++    72	
.oracle/checkins/batch-1-r12.md:2598: trailing whitespace.
++++    73	
.oracle/checkins/batch-1-r12.md:2600: trailing whitespace.
++++    81	
.oracle/checkins/batch-1-r12.md:2602: trailing whitespace.
++++    88	
.oracle/checkins/batch-1-r12.md:2604: trailing whitespace.
++++    89	
.oracle/checkins/batch-1-r12.md:2606: trailing whitespace.
++++    96	
.oracle/checkins/batch-1-r12.md:2608: trailing whitespace.
++++    97	
.oracle/checkins/batch-1-r12.md:2610: trailing whitespace.
++++   105	
.oracle/checkins/batch-1-r12.md:2612: trailing whitespace.
++++   106	
.oracle/checkins/batch-1-r12.md:2614: trailing whitespace.
++++   113	
.oracle/checkins/batch-1-r12.md:2616: trailing whitespace.
++++   114	
.oracle/checkins/batch-1-r12.md:2618: trailing whitespace.
++++   122	
.oracle/checkins/batch-1-r12.md:2620: trailing whitespace.
++++   123	
.oracle/checkins/batch-1-r12.md:2622: trailing whitespace.
++++   131	
.oracle/checkins/batch-1-r12.md:2624: trailing whitespace.
++++   132	
.oracle/checkins/batch-1-r12.md:2626: trailing whitespace.
++++   162	
.oracle/checkins/batch-1-r12.md:2628: trailing whitespace.
++++   163	
.oracle/checkins/batch-1-r12.md:2630: trailing whitespace.
++++   178	
.oracle/checkins/batch-1-r12.md:2632: trailing whitespace.
++++   179	
.oracle/checkins/batch-1-r12.md:2634: trailing whitespace.
++++   206	
.oracle/checkins/batch-1-r12.md:2636: trailing whitespace.
++++   207	
.oracle/checkins/batch-1-r12.md:2638: trailing whitespace.
++++   249	
.oracle/checkins/batch-1-r12.md:2640: trailing whitespace.
++++   250	
.oracle/checkins/batch-1-r12.md:2642: trailing whitespace.
++++   288	
.oracle/checkins/batch-1-r12.md:2644: trailing whitespace.
++++   289	
.oracle/checkins/batch-1-r12.md:2646: trailing whitespace.
++++   312	
.oracle/checkins/batch-1-r12.md:2648: trailing whitespace.
++++   313	
.oracle/checkins/batch-1-r12.md:2650: trailing whitespace.
++++   324	
.oracle/checkins/batch-1-r12.md:2652: trailing whitespace.
++++   325	
.oracle/checkins/batch-1-r12.md:2654: trailing whitespace.
++++   338	
.oracle/checkins/batch-1-r12.md:2656: trailing whitespace.
++++   339	
.oracle/checkins/batch-1-r12.md:2658: trailing whitespace.
++++   356	
.oracle/checkins/batch-1-r12.md:2660: trailing whitespace.
++++   357	
.oracle/checkins/batch-1-r12.md:2662: trailing whitespace.
++++   375	
.oracle/checkins/batch-1-r12.md:2664: trailing whitespace.
++++   376	
.oracle/checkins/batch-1-r12.md:2666: trailing whitespace.
++++    35	
.oracle/checkins/batch-1-r12.md:2668: trailing whitespace.
++++    40	
.oracle/checkins/batch-1-r12.md:2670: trailing whitespace.
++++    52	
.oracle/checkins/batch-1-r12.md:2672: trailing whitespace.
++++    73	
.oracle/checkins/batch-1-r12.md:2674: trailing whitespace.
++++   205	
.oracle/checkins/batch-1-r12.md:2676: trailing whitespace.
++++   206	
.oracle/checkins/batch-1-r12.md:2678: trailing whitespace.
++++   209	
.oracle/checkins/batch-1-r12.md:2680: trailing whitespace.
++++   215	
.oracle/checkins/batch-1-r12.md:2682: trailing whitespace.
++++   216	
.oracle/checkins/batch-1-r12.md:2684: trailing whitespace.
++++   225	
.oracle/checkins/batch-1-r12.md:2686: trailing whitespace.
++++   226	
.oracle/checkins/batch-1-r12.md:2688: trailing whitespace.
++++   231	
.oracle/checkins/batch-1-r12.md:2690: trailing whitespace.
++++   232	
.oracle/checkins/batch-1-r12.md:2692: trailing whitespace.
++++   288	
.oracle/checkins/batch-1-r12.md:2694: trailing whitespace.
++++   289	
.oracle/checkins/batch-1-r12.md:2696: trailing whitespace.
++++   158	
.oracle/checkins/batch-1-r12.md:2698: trailing whitespace.
++++   159	
.oracle/checkins/batch-1-r12.md:2700: trailing whitespace.
++++   165	
.oracle/checkins/batch-1-r12.md:2702: trailing whitespace.
++++   166	
.oracle/checkins/batch-1-r12.md:2704: trailing whitespace.
++++   171	
.oracle/checkins/batch-1-r12.md:2706: trailing whitespace.
++++   172	
.oracle/checkins/batch-1-r12.md:2708: trailing whitespace.
++++   186	
.oracle/checkins/batch-1-r12.md:2710: trailing whitespace.
++++   187	
.oracle/checkins/batch-1-r12.md:2712: trailing whitespace.
++++   194	
.oracle/checkins/batch-1-r12.md:2714: trailing whitespace.
++++   195	
.oracle/checkins/batch-1-r12.md:2716: trailing whitespace.
++++   205	
.oracle/checkins/batch-1-r12.md:2718: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2720: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2722: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2724: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2726: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2728: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2730: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2732: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2734: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2736: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2738: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2740: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2742: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2744: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2746: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2748: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2750: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2752: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2754: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2756: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2758: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2760: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2762: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2764: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2766: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2768: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2770: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2772: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2774: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2776: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2778: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2780: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2782: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2784: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2786: trailing whitespace.
+++    92	
.oracle/checkins/batch-1-r12.md:2788: trailing whitespace.
+++    93	
.oracle/checkins/batch-1-r12.md:2790: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r12.md:2792: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r12.md:2794: trailing whitespace.
+++   181	
.oracle/checkins/batch-1-r12.md:2796: trailing whitespace.
+++   182	
.oracle/checkins/batch-1-r12.md:2798: trailing whitespace.
+++   285	
.oracle/checkins/batch-1-r12.md:2800: trailing whitespace.
+++   294	
.oracle/checkins/batch-1-r12.md:2802: trailing whitespace.
+++   295	
.oracle/checkins/batch-1-r12.md:2804: trailing whitespace.
+++   302	
.oracle/checkins/batch-1-r12.md:2806: trailing whitespace.
+++   303	
.oracle/checkins/batch-1-r12.md:2808: trailing whitespace.
+++   312	
.oracle/checkins/batch-1-r12.md:2810: trailing whitespace.
+++   313	
.oracle/checkins/batch-1-r12.md:2812: trailing whitespace.
+++   330	
.oracle/checkins/batch-1-r12.md:2814: trailing whitespace.
+++   331	
.oracle/checkins/batch-1-r12.md:2816: trailing whitespace.
+++   582	
.oracle/checkins/batch-1-r12.md:2818: trailing whitespace.
+++   583	
.oracle/checkins/batch-1-r12.md:2820: trailing whitespace.
+++   587	
.oracle/checkins/batch-1-r12.md:2822: trailing whitespace.
+++   592	
.oracle/checkins/batch-1-r12.md:2824: trailing whitespace.
+++   604	
.oracle/checkins/batch-1-r12.md:2826: trailing whitespace.
+++   609	
.oracle/checkins/batch-1-r12.md:2828: trailing whitespace.
+++   621	
.oracle/checkins/batch-1-r12.md:2830: trailing whitespace.
+++   633	
.oracle/checkins/batch-1-r12.md:2832: trailing whitespace.
+++   634	
.oracle/checkins/batch-1-r12.md:2834: trailing whitespace.
+++   655	
.oracle/checkins/batch-1-r12.md:2836: trailing whitespace.
+++   656	
.oracle/checkins/batch-1-r12.md:2838: trailing whitespace.
+++   660	
.oracle/checkins/batch-1-r12.md:2840: trailing whitespace.
+++   667	
.oracle/checkins/batch-1-r12.md:2842: trailing whitespace.
+++   690	
.oracle/checkins/batch-1-r12.md:2844: trailing whitespace.
+++   702	
.oracle/checkins/batch-1-r12.md:2846: trailing whitespace.
+++   717	
.oracle/checkins/batch-1-r12.md:2848: trailing whitespace.
+++   738	
.oracle/checkins/batch-1-r12.md:2850: trailing whitespace.
+++   739	
.oracle/checkins/batch-1-r12.md:2852: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2854: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2856: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2858: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:2860: trailing whitespace.
+++   520	
.oracle/checkins/batch-1-r12.md:2862: trailing whitespace.
+++   539	
.oracle/checkins/batch-1-r12.md:2864: trailing whitespace.
+++   540	
.oracle/checkins/batch-1-r12.md:2866: trailing whitespace.
+++   550	
.oracle/checkins/batch-1-r12.md:2868: trailing whitespace.
+++   551	
.oracle/checkins/batch-1-r12.md:2870: trailing whitespace.
+++   613	
.oracle/checkins/batch-1-r12.md:2872: trailing whitespace.
+++   617	
.oracle/checkins/batch-1-r12.md:2874: trailing whitespace.
+++   618	
.oracle/checkins/batch-1-r12.md:2876: trailing whitespace.
+++   631	
.oracle/checkins/batch-1-r12.md:2878: trailing whitespace.
+++   632	
.oracle/checkins/batch-1-r12.md:2880: trailing whitespace.
+++   635	
.oracle/checkins/batch-1-r12.md:2882: trailing whitespace.
+++   644	
.oracle/checkins/batch-1-r12.md:2884: trailing whitespace.
+++   645	
.oracle/checkins/batch-1-r12.md:2886: trailing whitespace.
+++   651	
.oracle/checkins/batch-1-r12.md:2888: trailing whitespace.
+++   652	
.oracle/checkins/batch-1-r12.md:2890: trailing whitespace.
+++   683	
.oracle/checkins/batch-1-r12.md:2892: trailing whitespace.
+++   693	
.oracle/checkins/batch-1-r12.md:2894: trailing whitespace.
+++   729	
.oracle/checkins/batch-1-r12.md:2896: trailing whitespace.
+++   730	
.oracle/checkins/batch-1-r12.md:2898: trailing whitespace.
+++   748	
.oracle/checkins/batch-1-r12.md:2900: trailing whitespace.
+++   749	
.oracle/checkins/batch-1-r12.md:2902: trailing whitespace.
+++   785	
.oracle/checkins/batch-1-r12.md:2904: trailing whitespace.
+++   786	
.oracle/checkins/batch-1-r12.md:2906: trailing whitespace.
+++   800	
.oracle/checkins/batch-1-r12.md:2908: trailing whitespace.
+++   801	
.oracle/checkins/batch-1-r12.md:2910: trailing whitespace.
+++   817	
.oracle/checkins/batch-1-r12.md:2912: trailing whitespace.
+++   818	
.oracle/checkins/batch-1-r12.md:2914: trailing whitespace.
+++   914	
.oracle/checkins/batch-1-r12.md:2916: trailing whitespace.
+++   915	
.oracle/checkins/batch-1-r12.md:2918: trailing whitespace.
+++  1014	
.oracle/checkins/batch-1-r12.md:2920: trailing whitespace.
+++  1015	
.oracle/checkins/batch-1-r12.md:2922: trailing whitespace.
+++  1024	
.oracle/checkins/batch-1-r12.md:2924: trailing whitespace.
+++  1025	
.oracle/checkins/batch-1-r12.md:2926: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r12.md:2928: trailing whitespace.
+++     4	
.oracle/checkins/batch-1-r12.md:2930: trailing whitespace.
+++     6	
.oracle/checkins/batch-1-r12.md:2932: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r12.md:2934: trailing whitespace.
+++    17	
.oracle/checkins/batch-1-r12.md:2936: trailing whitespace.
+++    19	
.oracle/checkins/batch-1-r12.md:2938: trailing whitespace.
+++    25	
.oracle/checkins/batch-1-r12.md:2940: trailing whitespace.
+++    27	
.oracle/checkins/batch-1-r12.md:2942: trailing whitespace.
+++    29	
.oracle/checkins/batch-1-r12.md:2944: trailing whitespace.
+++    31	
.oracle/checkins/batch-1-r12.md:2946: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r12.md:2948: trailing whitespace.
+++    42	
.oracle/checkins/batch-1-r12.md:2950: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r12.md:2952: trailing whitespace.
+++    51	
.oracle/checkins/batch-1-r12.md:2954: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r12.md:2956: trailing whitespace.
+++    55	
.oracle/checkins/batch-1-r12.md:2958: trailing whitespace.
+++    63	
.oracle/checkins/batch-1-r12.md:2960: trailing whitespace.
+++    65	
.oracle/checkins/batch-1-r12.md:2962: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r12.md:2964: trailing whitespace.
+++    74	
.oracle/checkins/batch-1-r12.md:2966: trailing whitespace.
+++    76	
.oracle/checkins/batch-1-r12.md:2968: trailing whitespace.
+++    78	
.oracle/checkins/batch-1-r12.md:2970: trailing whitespace.
+++    86	
.oracle/checkins/batch-1-r12.md:2972: trailing whitespace.
+++    88	
.oracle/checkins/batch-1-r12.md:2974: trailing whitespace.
+++    94	
.oracle/checkins/batch-1-r12.md:2976: trailing whitespace.
+++    96	
.oracle/checkins/batch-1-r12.md:2978: trailing whitespace.
+++    98	
.oracle/checkins/batch-1-r12.md:2980: trailing whitespace.
+++   100	
.oracle/checkins/batch-1-r12.md:2982: trailing whitespace.
+++   109	
.oracle/checkins/batch-1-r12.md:2984: trailing whitespace.
+++   111	
.oracle/checkins/batch-1-r12.md:2986: trailing whitespace.
+++   119	
.oracle/checkins/batch-1-r12.md:2988: trailing whitespace.
+++   121	
.oracle/checkins/batch-1-r12.md:2990: trailing whitespace.
+++   123	
.oracle/checkins/batch-1-r12.md:2992: trailing whitespace.
+++   125	
.oracle/checkins/batch-1-r12.md:2994: trailing whitespace.
+++   133	
.oracle/checkins/batch-1-r12.md:2996: trailing whitespace.
+++   135	
.oracle/checkins/batch-1-r12.md:2998: trailing whitespace.
+++   142	
.oracle/checkins/batch-1-r12.md:3000: trailing whitespace.
+++   144	
.oracle/checkins/batch-1-r12.md:3002: trailing whitespace.
+++   146	
.oracle/checkins/batch-1-r12.md:3004: trailing whitespace.
+++   148	
.oracle/checkins/batch-1-r12.md:3006: trailing whitespace.
+++   159	
.oracle/checkins/batch-1-r12.md:3008: trailing whitespace.
+++   161	
.oracle/checkins/batch-1-r12.md:3010: trailing whitespace.
+++   168	
.oracle/checkins/batch-1-r12.md:3012: trailing whitespace.
+++   170	
.oracle/checkins/batch-1-r12.md:3014: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r12.md:3016: trailing whitespace.
+++     4	
.oracle/checkins/batch-1-r12.md:3018: trailing whitespace.
+++     6	
.oracle/checkins/batch-1-r12.md:3020: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r12.md:3022: trailing whitespace.
+++    17	
.oracle/checkins/batch-1-r12.md:3024: trailing whitespace.
+++    19	
.oracle/checkins/batch-1-r12.md:3026: trailing whitespace.
+++    25	
.oracle/checkins/batch-1-r12.md:3028: trailing whitespace.
+++    27	
.oracle/checkins/batch-1-r12.md:3030: trailing whitespace.
+++    29	
.oracle/checkins/batch-1-r12.md:3032: trailing whitespace.
+++    31	
.oracle/checkins/batch-1-r12.md:3034: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r12.md:3036: trailing whitespace.
+++    42	
.oracle/checkins/batch-1-r12.md:3038: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r12.md:3040: trailing whitespace.
+++    51	
.oracle/checkins/batch-1-r12.md:3042: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r12.md:3044: trailing whitespace.
+++    55	
.oracle/checkins/batch-1-r12.md:3046: trailing whitespace.
+++    63	
.oracle/checkins/batch-1-r12.md:3048: trailing whitespace.
+++    65	
.oracle/checkins/batch-1-r12.md:3050: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r12.md:3052: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r12.md:3054: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r12.md:3056: trailing whitespace.
+++   173	
.oracle/checkins/batch-1-r12.md:3058: trailing whitespace.
+++   174	
.oracle/checkins/batch-1-r12.md:3060: trailing whitespace.
+++A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-1-r12.md:3062: trailing whitespace.
+++   186	
.oracle/checkins/batch-1-r12.md:3064: trailing whitespace.
+++   187	
.oracle/checkins/batch-1-r12.md:3066: trailing whitespace.
+++   194	
.oracle/checkins/batch-1-r12.md:3068: trailing whitespace.
+++   195	
.oracle/checkins/batch-1-r12.md:3070: trailing whitespace.
+++   205	
.oracle/checkins/batch-1-r12.md:3072: trailing whitespace.
+++   206	
.oracle/checkins/batch-1-r12.md:3074: trailing whitespace.
+++   209	
.oracle/checkins/batch-1-r12.md:3076: trailing whitespace.
+++   215	
.oracle/checkins/batch-1-r12.md:3078: trailing whitespace.
+++   216	
.oracle/checkins/batch-1-r12.md:3080: trailing whitespace.
+++   225	
.oracle/checkins/batch-1-r12.md:3082: trailing whitespace.
+++   226	
.oracle/checkins/batch-1-r12.md:3084: trailing whitespace.
+++   231	
.oracle/checkins/batch-1-r12.md:3086: trailing whitespace.
+++   232	
.oracle/checkins/batch-1-r12.md:3088: trailing whitespace.
+++   241	
.oracle/checkins/batch-1-r12.md:3090: trailing whitespace.
+++   242	
.oracle/checkins/batch-1-r12.md:3092: trailing whitespace.
+++   248	
.oracle/checkins/batch-1-r12.md:3094: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r12.md:3096: trailing whitespace.
+++   262	
.oracle/checkins/batch-1-r12.md:3098: trailing whitespace.
+++   263	
.oracle/checkins/batch-1-r12.md:3100: trailing whitespace.
+++   268	
.oracle/checkins/batch-1-r12.md:3102: trailing whitespace.
+++   269	
.oracle/checkins/batch-1-r12.md:3104: trailing whitespace.
+++   276	
.oracle/checkins/batch-1-r12.md:3106: trailing whitespace.
+++   277	
.oracle/checkins/batch-1-r12.md:3108: trailing whitespace.
+++   284	
.oracle/checkins/batch-1-r12.md:3110: trailing whitespace.
+++   285	
.oracle/checkins/batch-1-r12.md:3112: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r12.md:3114: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r12.md:3116: trailing whitespace.
+++    11	
.oracle/checkins/batch-1-r12.md:3118: trailing whitespace.
+++    20	
.oracle/checkins/batch-1-r12.md:3120: trailing whitespace.
+++    21	
.oracle/checkins/batch-1-r12.md:3122: trailing whitespace.
+++    48	
.oracle/checkins/batch-1-r12.md:3124: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r12.md:3126: trailing whitespace.
+++    52	
.oracle/checkins/batch-1-r12.md:3128: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r12.md:3130: trailing whitespace.
+++    56	
.oracle/checkins/batch-1-r12.md:3132: trailing whitespace.
+++    57	
.oracle/checkins/batch-1-r12.md:3134: trailing whitespace.
+++    60	
.oracle/checkins/batch-1-r12.md:3136: trailing whitespace.
+++    61	
.oracle/checkins/batch-1-r12.md:3138: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r12.md:3140: trailing whitespace.
+++    73	
.oracle/checkins/batch-1-r12.md:3142: trailing whitespace.
+++    81	
.oracle/checkins/batch-1-r12.md:3144: trailing whitespace.
+++    88	
.oracle/checkins/batch-1-r12.md:3146: trailing whitespace.
+++    89	
.oracle/checkins/batch-1-r12.md:3148: trailing whitespace.
+++    96	
.oracle/checkins/batch-1-r12.md:3150: trailing whitespace.
+++    97	
.oracle/checkins/batch-1-r12.md:3152: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r12.md:3154: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r12.md:3156: trailing whitespace.
+++   113	
.oracle/checkins/batch-1-r12.md:3158: trailing whitespace.
+++   114	
.oracle/checkins/batch-1-r12.md:3160: trailing whitespace.
+++   122	
.oracle/checkins/batch-1-r12.md:3162: trailing whitespace.
+++   123	
.oracle/checkins/batch-1-r12.md:3164: trailing whitespace.
+++   131	
.oracle/checkins/batch-1-r12.md:3166: trailing whitespace.
+++   132	
.oracle/checkins/batch-1-r12.md:3168: trailing whitespace.
+++   162	
.oracle/checkins/batch-1-r12.md:3170: trailing whitespace.
+++   163	
.oracle/checkins/batch-1-r12.md:3172: trailing whitespace.
+++   178	
.oracle/checkins/batch-1-r12.md:3174: trailing whitespace.
+++   179	
.oracle/checkins/batch-1-r12.md:3176: trailing whitespace.
+++   206	
.oracle/checkins/batch-1-r12.md:3178: trailing whitespace.
+++   207	
.oracle/checkins/batch-1-r12.md:3180: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r12.md:3182: trailing whitespace.
+++   250	
.oracle/checkins/batch-1-r12.md:3184: trailing whitespace.
+++   288	
.oracle/checkins/batch-1-r12.md:3186: trailing whitespace.
+++   289	
.oracle/checkins/batch-1-r12.md:3188: trailing whitespace.
+++   312	
.oracle/checkins/batch-1-r12.md:3190: trailing whitespace.
+++   313	
.oracle/checkins/batch-1-r12.md:3192: trailing whitespace.
+++   324	
.oracle/checkins/batch-1-r12.md:3194: trailing whitespace.
+++   325	
.oracle/checkins/batch-1-r12.md:3196: trailing whitespace.
+++   338	
.oracle/checkins/batch-1-r12.md:3198: trailing whitespace.
+++   339	
.oracle/checkins/batch-1-r12.md:3200: trailing whitespace.
+++   356	
.oracle/checkins/batch-1-r12.md:3202: trailing whitespace.
+++   357	
.oracle/checkins/batch-1-r12.md:3204: trailing whitespace.
+++   375	
.oracle/checkins/batch-1-r12.md:3206: trailing whitespace.
+++   376	
.oracle/checkins/batch-1-r12.md:3208: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:3210: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r12.md:3212: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3214: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3216: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3218: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3220: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3222: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3224: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3226: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3228: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3230: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3232: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3234: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3236: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3238: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3240: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3242: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3244: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3246: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3248: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3250: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3252: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3254: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3256: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3258: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3260: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3262: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3264: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3266: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3268: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3270: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3272: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3274: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3276: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3278: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3280: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3282: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3284: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3286: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3288: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3290: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3292: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3294: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3296: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3298: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3300: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3302: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3304: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3306: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3308: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3310: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3312: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3314: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3316: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3318: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3320: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3322: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3324: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3326: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3328: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3330: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3332: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3334: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3336: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3338: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3340: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3342: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3344: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3346: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3348: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3350: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3352: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3354: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3356: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3358: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3360: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3362: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3364: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3366: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3368: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3370: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3372: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3374: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3376: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3378: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3380: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3382: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3384: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3386: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3388: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3390: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3392: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3394: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3396: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3398: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3400: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3402: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3404: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3406: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3408: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3410: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3412: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3414: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3416: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3418: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3420: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3422: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3424: trailing whitespace.
++   190	
.oracle/checkins/batch-1-r12.md:3426: trailing whitespace.
++   191	
.oracle/checkins/batch-1-r12.md:3428: trailing whitespace.
++   215	
.oracle/checkins/batch-1-r12.md:3430: trailing whitespace.
++   216	
.oracle/checkins/batch-1-r12.md:3432: trailing whitespace.
++   225	
.oracle/checkins/batch-1-r12.md:3434: trailing whitespace.
++   226	
.oracle/checkins/batch-1-r12.md:3436: trailing whitespace.
++   231	
.oracle/checkins/batch-1-r12.md:3438: trailing whitespace.
++   232	
.oracle/checkins/batch-1-r12.md:3440: trailing whitespace.
++   241	
.oracle/checkins/batch-1-r12.md:3442: trailing whitespace.
++   242	
.oracle/checkins/batch-1-r12.md:3444: trailing whitespace.
++   248	
.oracle/checkins/batch-1-r12.md:3446: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r12.md:3448: trailing whitespace.
++   262	
.oracle/checkins/batch-1-r12.md:3450: trailing whitespace.
++   263	
.oracle/checkins/batch-1-r12.md:3452: trailing whitespace.
++   268	
.oracle/checkins/batch-1-r12.md:3454: trailing whitespace.
++   269	
.oracle/checkins/batch-1-r12.md:3456: trailing whitespace.
++   276	
.oracle/checkins/batch-1-r12.md:3458: trailing whitespace.
++   277	
.oracle/checkins/batch-1-r12.md:3460: trailing whitespace.
++   284	
.oracle/checkins/batch-1-r12.md:3462: trailing whitespace.
++   285	
.oracle/checkins/batch-1-r12.md:3464: trailing whitespace.
++   294	
.oracle/checkins/batch-1-r12.md:3466: trailing whitespace.
++   295	
.oracle/checkins/batch-1-r12.md:3468: trailing whitespace.
++   302	
.oracle/checkins/batch-1-r12.md:3470: trailing whitespace.
++   303	
.oracle/checkins/batch-1-r12.md:3472: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r12.md:3474: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r12.md:3476: trailing whitespace.
++   333	
.oracle/checkins/batch-1-r12.md:3478: trailing whitespace.
++   334	
.oracle/checkins/batch-1-r12.md:3480: trailing whitespace.
++   375	
.oracle/checkins/batch-1-r12.md:3482: trailing whitespace.
++   376	
.oracle/checkins/batch-1-r12.md:3484: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3486: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3488: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:3490: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:3492: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:3494: trailing whitespace.
++ 
.oracle/checkins/batch-1-r12.md:3506: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3512: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3514: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3522: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3525: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3526: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3528: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3539: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3544: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3565: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3586: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3606: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3623: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3651: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3652: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3658: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3659: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3664: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3665: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3679: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3680: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3687: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3688: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3698: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3699: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3702: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3708: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3709: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3719: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3720: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3725: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3726: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3735: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3736: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3742: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3743: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3756: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3757: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3762: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3763: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3770: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3771: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3778: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3779: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3788: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3789: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3796: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3797: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3806: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3807: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3828: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3829: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3841: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3842: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3845: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3851: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3852: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3855: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3859: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3860: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3874: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3875: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3879: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3885: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3911: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3918: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3919: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3931: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:3932: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4022: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4023: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4090: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4092: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4094: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4103: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4112: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4116: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4118: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4120: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4135: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4143: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4145: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4147: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4152: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4192: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4202: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4204: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4212: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4217: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4227: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4229: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4232: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4242: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4249: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4251: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4261: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4265: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4267: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4276: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4282: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4284: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4317: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4318: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4324: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4325: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4342: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4343: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4357: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4358: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4369: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4370: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4381: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4382: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4409: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4410: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4546: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4547: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4556: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4557: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4570: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4571: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4573: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4584: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4589: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4610: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4623: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4624: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4627: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4633: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4634: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4644: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4645: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4650: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4651: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4660: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4661: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4668: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4669: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4690: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4691: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4703: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4704: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4707: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4767: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4769: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4774: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4814: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4824: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4826: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4867: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4868: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4874: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:4875: trailing whitespace.
+ 
.oracle/checkins/batch-1-r12.md:7564: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r12.md:7565: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r12.md:7567: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r12.md:7619: trailing whitespace.
+ 

exec
/bin/zsh -lc 'for f in .oracle/checkins/batch-1.md .oracle/checkins/batch-1-r{1..12}.md; do echo "$f"; tail -n 18 "$f"; done' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/checkins/batch-1.md
7. **The frozen FFmpeg finalizer ID is contradicted and currently invalid.** The plan/tasklist require `rendering.ffmpeg-finalizer`, but the contract, fixtures, and tests freeze `rendering.ffmpeg_finalizer`; the qualified-ID regex in [contracts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:212) forbids the planned spelling.

   **Minimum rework:** resolve one canonical spelling and align every DTO, schema, document, fixture, and test. Under the frozen tasklist, use/support `rendering.ffmpeg-finalizer` unless the plan is formally amended.

8. **The new alias kinds crash public pack validation.** [validate.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:237) initializes resolver/capability maps only for executors and orchestrators, then indexes them using the newly accepted alias kind at [line 830](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:830). Running `validate_pack` on the committed rendering fixture raises `KeyError: 'renderer'`; consequently such a pack cannot follow the normal validation/install path.

   **Minimum rework:** integrate renderer/planner/finalizer manifests into static pack validation and capability-location registration, then add public `validate_pack` and install regressions.

9. **Alias eligibility filtering is only one hop.** [_alias_target_can_participate](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:950) drops a direct alias to a denied candidate but retains dangling intermediate aliases. A higher-precedence chain ending at an ineligible environment renderer can therefore overwrite a lower trusted alias and make resolution fail with `invalid_alias_target`. Existing coverage tests only direct targets.

   **Minimum rework:** evaluate alias participation transitively against the completed executable graph and fall through to the next-precedence declaration when a chain terminates missing or ineligible. Add two-hop denied and missing-terminal cases.

Judgments on the noted nuances:

- Lower `priority_index` winning is correct: it is discovery-order precedence and matches the shared registry semantics. The contrary T1.5 brief wording is the anomaly.
- Returning `unknown_capability` for an environment-only alias is acceptably fail-closed; inspection still uses the all-source resolver, and no frozen error-code requirement says otherwise.
- Executor and orchestrator default factories correctly construct `OverrideStore(project_root)`.
- The seven frozen error kinds are correct, and `hybrid` remains absent from the renderer registry.
.oracle/checkins/batch-1-r1.md

   Minimum rework: preserve both v1 projections unchanged; place normalized v2 segments under an additive field; use complete host-authoritative resolution evidence for all capability kinds; include artifact hashes; define and verify request-digest semantics.

3. **Schema/DTO parity remains false (prior issue 6).** For example, [request.json:165](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:165) accepts empty or whitespace-only metadata keys/values, while [contracts.py:244](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:244) rejects them. Result paths and profile strings have equivalent whitespace mismatches.

   Minimum rework: align schemas with every nonblank-string DTO constraint and add whitespace adversaries across requests, plans, results, finalization, support reports, and manifests.

4. **The underscore-compatible ID fix is absent, leaving pack validation broken (prior issues 7–8).** [contracts.py:35](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:35) and all rendering schemas remain hyphen-only. Consequently, the frozen [rendering.legacy_hybrid fixture](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/manifests/hybrid.planner.yaml:2) fails direct `validate_pack` and CLI validation. Tests conceal this by rewriting fixture IDs at runtime in [test_registry.py:39](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry.py:39).

   Allowing both `_` and `-` is correct given the locked planner ID and pack-ID conventions; `rendering.ffmpeg-finalizer` should remain canonical.

   Minimum rework: apply the compatible grammar consistently to DTOs, schemas, docs, and tests; restore `rendering.legacy_hybrid` everywhere; remove fixture rewriting; validate and install the real committed fixtures.

5. **Valid pack alias→override routes are dropped (new issue adjacent to prior issue 9).** [registry.py:1023](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/registry.py:1023) recognizes an override-routable missing canonical target only when the alias originates from `astrid.core`. Thus a trusted pack route such as `pack.alias → missing.canonical → override → executable.renderer` is discarded, violating the frozen alias→canonical→override ordering.

   Minimum rework: evaluate override-routable terminals for every eligible alias declaration, retain fail-closed behavior for invalid targets, and add a trusted-pack alias→absent canonical→executable override regression.

Issues 1, 3, and 5 are genuinely closed. The original KeyError portion of issue 8 and transitive-eligibility portion of issue 9 are fixed. No additional substantive non-rendering production scope creep was found.
.oracle/checkins/batch-1-r2.md
3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.

Confirmed closed: no remaining relevant fixture-ID rewriting was found; underscore-qualified IDs work; `segments` is genuinely V1-shaped; `segment_provenance` is value-preserved; and the exercised no-override registry path fails closed.
tokens used
513,128
## ISSUES

1. **Provenance resolution and artifact lineage remain incomplete.** `PlannerResolution.to_dict()` omits `alias_chain` and `override`, so they disappear from every serialized plan and from provenance, which calls that method directly ([contracts.py:1019](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1019), [provenance.py:182](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:182)). Additionally, the frozen rework required every capability resolution to carry trust and support evidence ([batch-1-r2-t1.2.md:61](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/.oracle/briefs/batch-1-r2-t1.2.md:61)); renderer lacks `trust_eligibility`, while planner/finalizer lack `support_decision`, and finalizer lacks trust ([contracts.py:1045](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1045), [contracts.py:1128](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1128)). Per-segment/output video hashes are also still absent: `artifact_profiles` contains only profiles, despite the documentation claiming hashes are there ([provenance.py:84](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:84), [render-backend-v1.md:472](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/docs/contracts/render-backend-v1.md:472)).

   Minimum rework: preserve planner alias/override during serialization, implement the agreed complete resolution records across DTOs/schemas/docs, add output/segment artifact hashes, and test non-default values through plan round-trip and final provenance.

2. **Schema/DTO parity is still false.** Whitespace-only strings remain schema-valid but DTO-invalid for, among others, `assets_registry_path` and nullable profile fields ([request.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:22)), `backend_version` ([support.json:51](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/support.json:51)), workspace paths and `recovery_command` ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [result.json:485](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:485)), manifest descriptions/metadata keys ([renderer-manifest.json:60](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:60)), alias-chain entries, feature keys, and input-hash keys. Conversely, planner/finalizer DTOs accept `"alias_chain": "abc"` and turn it into three entries, while the schemas correctly require an array ([contracts.py:1004](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1004), [plan.json:398](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:398)).

   There is also new reserved-name drift: runtime reserves `segments_v2`, but the result schema’s backend-fragment prohibition omits it, so schema validation accepts a fragment the DTO rejects ([contracts.py:53](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:53), [result.json:298](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:298)).

3. **The alias→override regression uses a statically invalid “real” fixture.** The committed source fixture declares `rendering.missing → rendering.absent` ([pack.yaml:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/discovery/source/rendering/pack.yaml:17)). `validate_pack` rejects it with `pack.aliases[2] points to unknown renderer id 'rendering.absent'` under the same-pack target rule ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)). The registry regression test loads the fixture without static validation ([test_registry_matrix.py:486](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486)), so it proves the in-memory route but not a valid/installable pack route. Use a statically valid cross-pack absent canonical—or deliberately reconcile validator semantics—and test validation/install plus both override success and no-override fail-closed behavior.

Confirmed closed: no remaining relevant fixture-ID rewriting was found; underscore-qualified IDs work; `segments` is genuinely V1-shaped; `segment_provenance` is value-preserved; and the exercised no-override registry path fails closed.
.oracle/checkins/batch-1-r3.md

   Minimum rework: require all seven resolution keys, validate support/override coherence, and emit one hashed `VideoArtifact` lineage record per segment—including attachment hashes—with adversarial round-trip/provenance tests.

2. **Schema/DTO parity remains false beyond the repaired nullable scalars.**

   - `workspacePath` accepts whitespace-only paths, while `_require_workspace_relative_path()` rejects them ([result.json:22](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:22), [contracts.py:300](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:300)).
   - Plan planner/finalizer alias entries lack `\S` constraints ([plan.json:403](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/plan.json:403)); the duplicated finalize definitions do constrain them.
   - Planner/finalizer DTOs still accept `"alias_chain": "abc"` and serialize it as `["a","b","c"]` ([contracts.py:1005](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:1005)); both schemas require arrays.
   - `hashMap`, support/manifest feature maps, and manifest metadata keys lack matching nonblank `propertyNames` constraints. The three manifest schemas still use `minLength` alone for metadata keys ([renderer-manifest.json:95](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/renderer-manifest.json:95)).
   - `_require_string()` universally rejects NUL, but generic `\S` schema constraints accept strings containing NUL ([contracts.py:217](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:217), [request.json:17](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/request.json:17)).

   Minimum rework: apply one shared nonblank/no-NUL constraint to scalar, array-item, and property-name strings across every duplicated schema; use `_require_string_list()` for every alias chain; add adversaries for these exact cases.

3. **The temp-fixture regression still exercises a statically invalid pack.** [`_write_alias_to_absent_pack()`](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:486) declares a same-pack alias to absent `alias_missing.absent`. `validate_pack` rejects precisely that case ([validate.py:908](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/pack/validate.py:908)), while the tests inject it directly into discovery ([test_registry_matrix.py:530](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_registry_matrix.py:530)). Moving the invalid fixture into `tmp_path` fixes the committed corpus but still does not prove a valid/installable pack route.

   Minimum rework: use a cross-pack absent canonical target, prove validation and installation succeed, then exercise override success and no-override fail-closed behavior through that valid pack.

Confirmed closed: `segments_v2` is reserved consistently, and the seven committed discovery fixtures are no longer statically invalid.
.oracle/checkins/batch-1-r4.md

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
.oracle/checkins/batch-1-r5.md
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
.oracle/checkins/batch-1-r6.md
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
.oracle/checkins/batch-1-r7.md

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
.oracle/checkins/batch-1-r8.md
'dir/ /video.mp4' True False
'dir/\t/video.mp4' True False
'dir/.\n' False True
'dir/..\n' False True

codex
1. **Per-segment lineage remains unbound and bypassable.** Sequence output drops `VideoArtifact.path`, accepts mutated escaped paths, and cannot round-trip. Multi-segment mapping remains unordered. A mutated positive `RenderPlan` with `segments.clear()` also accepts empty lineage. Reconstruct DTOs at the boundary and use one canonical ordered, path-bearing entry per segment; reject unordered multi-segment mappings. [provenance.py:107](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:107) [provenance.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:302)

2. **The JSON Schemas are no longer language-neutral.** All 124 patterns use Python-specific `\Z`; ECMAScript treats it as literal `Z` or rejects it, so canonical IDs and digests fail non-Python validation. Replace it with a portable absolute-end assertion such as `(?![\\s\\S])` and add ECMAScript conformance coverage. The new LF adversaries also target nonexistent top-level finalize fields, so they do not exercise the intended nested patterns. [result.json:16](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:16) [test_schema_roundtrip.py:283](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_schema_roundtrip.py:283)

3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
tokens used
192,998
1. **Per-segment lineage remains unbound and bypassable.** Sequence output drops `VideoArtifact.path`, accepts mutated escaped paths, and cannot round-trip. Multi-segment mapping remains unordered. A mutated positive `RenderPlan` with `segments.clear()` also accepts empty lineage. Reconstruct DTOs at the boundary and use one canonical ordered, path-bearing entry per segment; reject unordered multi-segment mappings. [provenance.py:107](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:107) [provenance.py:302](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:302)

2. **The JSON Schemas are no longer language-neutral.** All 124 patterns use Python-specific `\Z`; ECMAScript treats it as literal `Z` or rejects it, so canonical IDs and digests fail non-Python validation. Replace it with a portable absolute-end assertion such as `(?![\\s\\S])` and add ECMAScript conformance coverage. The new LF adversaries also target nonexistent top-level finalize fields, so they do not exercise the intended nested patterns. [result.json:16](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:16) [test_schema_roundtrip.py:283](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_schema_roundtrip.py:283)

3. **`workspacePath` schema/DTO parity still differs.** Schemas accept whitespace-only components such as `"dir/ /video.mp4"` while the DTO rejects them; residual inner `$` checks reject `"dir/.\n"` while the DTO accepts it. Align both duplicated schemas with the DTO’s per-component rule and portable exact-end semantics, with adversaries in both directions. [contracts.py:314](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:314) [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25)
.oracle/checkins/batch-1-r9.md
exec
/bin/zsh -lc "node -e 'const fs=require(\"fs\"); for(const n of [\"result.json\",\"finalize.json\"]){const s=JSON.parse(fs.readFileSync("'`astrid/core/rendering/schemas/v1/${n}`,"utf8")); const r=new RegExp(s.definitions.workspacePath.pattern); console.log(n,r.test(" /video.mp4"),r.test("dir/'"\\v/video.mp4\"),r.test(\"ok/video.mp4\"));} const s=JSON.parse(fs.readFileSync(\"astrid/core/rendering/schemas/v1/result.json\",\"utf8\")); console.log(\"sha\",new RegExp(s.definitions.sha256.pattern).test(\"a\".repeat(64)),new RegExp(s.definitions.sha256.pattern).test(\"a\".repeat(64)+\"\\n\"));'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
result.json true true true
finalize.json true true true
sha true false

collab: Wait
collab: Wait
codex
1. **`VideoArtifact` reconstruction remains bypassable.** [provenance.py:150](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150) never reconstructs sequence entries through `VideoArtifact.from_dict`; an artifact mutated to `path="../escape.mp4"` is accepted and emitted. Mapping lineage also validates `str(path)` but emits the original value, allowing an integer `path`. The emitted sequence still cannot round-trip because dictionary records are rejected.

2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
tokens used
174,264
1. **`VideoArtifact` reconstruction remains bypassable.** [provenance.py:150](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:150) never reconstructs sequence entries through `VideoArtifact.from_dict`; an artifact mutated to `path="../escape.mp4"` is accepted and emitted. Mapping lineage also validates `str(path)` but emits the original value, allowing an integer `path`. The emitted sequence still cannot round-trip because dictionary records are rejected.

2. **`workspacePath` is still not DTO-equivalent.** [result.json:25](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/result.json:25) and [finalize.json:68](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/schemas/v1/finalize.json:68) accept `" /video.mp4"` and `"dir/\v/video.mp4"`; the DTO rejects both as whitespace-only components at [contracts.py:323](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/contracts.py:323).
.oracle/checkins/batch-1-r10.md
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
.oracle/checkins/batch-1-r11.md
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
.oracle/checkins/batch-1-r12.md
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle']

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; m=runpy.run_path(\"tests/core/rendering/test_contracts.py\"); P=m[\"assemble_provenance_v2\"]; base=dict(engine=\"hybrid\", output=\"/workspace/out.mp4\", timeline=\"/workspace/timeline.json\", assets_registry=None, plan=m[\"_plan\"](), audio_ownership=\"rendered\", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=m[\"_compatibility\"]()); rec={\"path\":123,\"profile\":m[\"_profile\"]().to_dict(),\"sha256\":m[\"SHA_B\"],\"attachments\":{}}; print(P(**base,artifact_profiles={\"123\":rec})[\"artifact_profiles\"])'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 135ms:
{'123': {'path': '123', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}}

codex
1. [provenance.py:166](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:166) uses Python’s default `raw_path.strip()`. A valid ECMA path `"\u0085"` emits successfully from `VideoArtifact` but fails when that emitted lineage is replayed, breaking the round-trip guarantee.

2. Mapping-form lineage still coerces non-string paths via `str()` at [provenance.py:119](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:119) and [provenance.py:213](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:213). For example, `{"123": {"path": 123, ...}}` is accepted and emits `"123"`, contradicting the no-coercion contract. The new test’s missing-path entry raises first, so its numeric entry is never exercised.
tokens used
339,840
1. [provenance.py:166](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:166) uses Python’s default `raw_path.strip()`. A valid ECMA path `"\u0085"` emits successfully from `VideoArtifact` but fails when that emitted lineage is replayed, breaking the round-trip guarantee.

2. Mapping-form lineage still coerces non-string paths via `str()` at [provenance.py:119](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:119) and [provenance.py:213](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/provenance.py:213). For example, `{"123": {"path": 123, ...}}` is accepted and emits `"123"`, contradicting the no-coercion contract. The new test’s missing-path entry raises first, so its numeric entry is never exercised.

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c '
import runpy
m = runpy.run_path(\"tests/core/rendering/test_contracts.py\")
P = m[\"assemble_provenance_v2\"]
V = m[\"VideoArtifact\"]
base = dict(engine=\"hybrid\", output=\"/workspace/out.mp4\", timeline=\"/workspace/timeline.json\", assets_registry=None, audio_ownership=\"rendered\", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=m[\"_compatibility\"]())
plan2 = m[\"_plan\"](segments=[m[\"_segment\"](0, 24), m[\"_segment\"](24, 48)])
arts = [V(path=\"\\u0085\", profile=m[\"_profile\"](audio=False), sha256=m[\"SHA_B\"], duration_frames=24), V(path=\"outputs/b.mp4\", profile=m[\"_profile\"](audio=False), sha256=m[\"SHA_C\"], duration_frames=24)]
first = P(**base, plan=plan2, artifact_profiles=arts)
second = P(**base, plan=plan2, artifact_profiles=first[\"artifact_profiles\"])
assert second[\"artifact_profiles\"] == first[\"artifact_profiles\"]
assert first[\"artifact_profiles\"][0][\"path\"] == \"\\u0085\"
cases = [(\"nonstring key\", {123: {\"profile\": m[\"_profile\"](), \"sha256\": m[\"SHA_B\"], \"attachments\": {}}}, TypeError), (\"nonstring embedded\", {\"123\": {\"path\": 123, \"profile\": m[\"_profile\"](), \"sha256\": m[\"SHA_B\"], \"attachments\": {}}}, TypeError), (\"mismatched embedded\", {\"123\": {\"path\": \"456\", \"profile\": m[\"_profile\"](), \"sha256\": m[\"SHA_B\"], \"attachments\": {}}}, ValueError)]
for label, profiles, expected in cases:
    try:
        P(**base, plan=m[\"_plan\"](), artifact_profiles=profiles)
    except expected:
        pass
    else:
        raise AssertionError(label)
print(\"targeted edge checks: PASS\")
'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 355ms:
targeted edge checks: PASS

exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/test_contracts.py::test_provenance_rejects_spoofed_artifact_lineage' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 475ms:
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
/bin/zsh -lc "rg -n \"\\[tool\\.ruff|line-length|black\" pyproject.toml Makefile .github 2>/dev/null | sed -n '1,200p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
pyproject.toml:60:[tool.ruff]
pyproject.toml:62:line-length = 100
pyproject.toml:73:[tool.ruff.lint]

exec
/bin/zsh -lc 'ruff check --no-cache astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 256ms:
astrid/core/rendering/provenance.py:3:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 |   """Core-owned provenance v2 assembly for timeline renders."""
 2 |
 3 | / from __future__ import annotations
 4 | |
 5 | | from collections.abc import Mapping, Sequence
 6 | | from pathlib import Path
 7 | | from typing import Any
 8 | |
 9 | | from astrid.core.foundation.atomic_io import write_json_atomic
10 | | from astrid.core.foundation.hash import sha256_file
11 | |
12 | | from .contracts import (
13 | |     PROVENANCE_V1_ALWAYS_KEYS,
14 | |     PROVENANCE_V1_COMPATIBILITY_KEYS,
15 | |     PROVENANCE_V2_CORE_KEYS,
16 | |     _ECMA_WHITESPACE,
17 | |     Attachment,
18 | |     AudioOwnership,
19 | |     RenderPlan,
20 | |     RenderProfile,
21 | |     RenderSegment,
22 | |     VideoArtifact,
23 | |     _json_safe_mapping,
24 | |     _require_sha256,
25 | |     _require_string,
26 | |     _require_workspace_relative_path,
27 | |     _validate_backend_fragments,
28 | | )
   | |_^ I001
   |
   = help: Organize imports

tests/core/rendering/test_contracts.py:1:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 | / from __future__ import annotations
 2 | |
 3 | | from collections.abc import Callable
 4 | | from copy import deepcopy
 5 | | from dataclasses import FrozenInstanceError, replace
 6 | | from pathlib import Path
 7 | | from typing import Any
 8 | |
 9 | | import pytest
10 | |
11 | | from astrid.core.rendering import (
12 | |     Attachment,
13 | |     AudioOwnership,
14 | |     FrameWindow,
15 | |     RenderPlan,
16 | |     RenderProfile,
17 | |     RenderRequest,
18 | |     RenderResult,
19 | |     RendererError,
20 | |     SupportReport,
21 | |     VideoArtifact,
22 | | )
23 | | from astrid.core.rendering.contracts import (
24 | |     FinalizeRequest,
25 | |     FinalizerManifest,
26 | |     FinalizerResolution,
27 | |     PlannerManifest,
28 | |     PlannerResolution,
29 | |     PROVENANCE_V1_COMPATIBILITY_KEYS,
30 | |     RenderSegment,
31 | |     RendererManifest,
32 | |     RendererResolution,
33 | |     _require_workspace_relative_path,
34 | |     parse_wire_result,
35 | | )
36 | | from astrid.core.rendering.errors import RendererProtocolError
37 | | from astrid.core.rendering.provenance import (
38 | |     assemble_provenance_v2,
39 | |     hash_input_files,
40 | |     validate_backend_fragments,
41 | |     write_provenance_v2,
42 | | )
   | |_^ I001
   |
   = help: Organize imports

tests/core/rendering/test_contracts.py:735:5: F811 Redefinition of unused `test_resolution_records_require_all_seven_evidence_keys` from line 732
    |
733 |     """Every capability resolution requires the complete evidence set;
734 |     a missing key is a structural protocol failure."""
735 | def test_resolution_records_require_all_seven_evidence_keys() -> None:
    |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ F811
736 |     """Every capability resolution requires the complete evidence set;
737 |     a missing key is a structural protocol failure."""
    |
    = help: Remove definition: `test_resolution_records_require_all_seven_evidence_keys`

Found 3 errors.
[*] 2 fixable with the `--fix` option.

exec
/bin/zsh -lc "nl -ba pyproject.toml | sed -n '50,100p'; nl -ba Makefile | sed -n '1,180p'; git show 8e4f640:astrid/core/rendering/provenance.py | ruff check --no-cache --stdin-filename astrid/core/rendering/provenance.py -" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
    50	# Requires a configured private package index (e.g. local wheelhouse or git
    51	# source) because runpod-lifecycle is not published on public PyPI.
    52	# Install: pip install 'astrid[runpod]'
    53	runpod = [
    54	    "runpod-lifecycle>=0.3",
    55	]
    56	
    57	[tool.setuptools.packages.find]
    58	include = ["astrid*"]
    59	
    60	[tool.ruff]
    61	target-version = "py311"
    62	line-length = 100
    63	# Evidence: advisory lint scope was introduced in 7d343bc with only reshape/concurrency paths.
    64	# Inference: astrid/ was left out to keep the initial S0 gate narrow while known backlog remained.
    65	include = [
    66	    "astrid/**/*.py",
    67	    "scripts/reshape/**/*.py",
    68	    "tests/reshape/**/*.py",
    69	    "tests/concurrency/two_tab_harness.py",
    70	    "tests/concurrency/test_two_tab_harness_smoke.py",
    71	]
    72	
    73	[tool.ruff.lint]
    74	select = ["E4", "E7", "E9", "F", "I", "BLE"]
    75	
    76	[tool.coverage.run]
    77	source = ["astrid"]
    78	omit = [
    79	    ".megaplan/*",
    80	    "out/*",
    81	    "runs/*",
    82	    ".venv/*",
    83	    "venv/*",
    84	    "*/venv/*",
    85	    "*/.venv/*",
    86	    "remotion/*",
    87	    "tests/*",
    88	    "*/tests/*",
    89	    "scripts/*",
    90	    "*/site-packages/*",
    91	    "node_modules/*",
    92	    "build/*",
    93	    "dist/*",
    94	]
    95	
    96	[tool.coverage.report]
    97	show_missing = true
    98	fail_under = 0
    99	
   100	[tool.mypy]
     1	# Astrid local gate — run before pushing to catch CI/deploy failures locally.
     2	#
     3	#   make check   fast pre-deploy gates (structure, doctor, ruff, mypy, cycles) — seconds
     4	#   make ci      full mirror of the CI deploy job (adds wheel-install + pytest+coverage) — minutes
     5	#
     6	# `make check` green ≈ the CI "Python quality gates" deploy job will pass its fast gates.
     7	# These run the SAME scripts CI runs (see .github/workflows/ci.yml), so they stay in lockstep.
     8	
     9	PY ?= python3
    10	
    11	.PHONY: help check ci structure doctor ruff mypy cycles wheel ci-mirror editable
    12	
    13	help:
    14		@echo "make check   - fast pre-deploy gates: structure, doctor, ruff, mypy, cycles (seconds)"
    15		@echo "make ci      - full CI deploy mirror: check + editable + wheel-install + pytest/coverage (minutes)"
    16		@echo "make <gate>  - run one gate: structure | doctor | ruff | mypy | cycles | wheel | ci-mirror | editable"
    17	
    18	# --- Fast gates: catch the common deploy blockers in seconds. Run before every push. ---
    19	check: structure doctor ruff mypy cycles
    20		@echo "✅ make check: fast pre-deploy gates passed"
    21	
    22	structure:
    23		@$(PY) -c "import sys; from astrid.core.structure import validate_repo_structure as v; r=v(); [print('STRUCTURE ERROR:', e) for e in r.errors]; sys.exit(1 if r.errors else 0)"
    24		@echo "✓ repo structure (canonical top-level dirs)"
    25	
    26	doctor:
    27		@$(PY) -m astrid doctor --json >/dev/null
    28		@echo "✓ doctor (deploy health gate)"
    29	
    30	ruff:
    31		@$(PY) scripts/reshape/compare_ruff_baseline.py
    32		@echo "✓ ruff baseline (no lint regression)"
    33	
    34	mypy:
    35		@$(PY) scripts/reshape/compare_mypy_baseline.py
    36		@echo "✓ mypy baseline (no type regression)"
    37	
    38	cycles:
    39		@$(PY) -m scripts.reshape.import_cycles --baseline scripts/reshape/baselines/import_cycles.json
    40		@echo "✓ import cycles (no new cross-package cycle)"
    41	
    42	# --- Full mirror of the CI deploy job (slow). Run before a release / when in doubt. ---
    43	ci: check editable wheel ci-mirror
    44		@echo "✅ make ci: full CI deploy mirror passed — deploy should be green"
    45	
    46	editable:
    47		@$(PY) -c "import astrid; print('✓ editable install imports')"
    48	
    49	wheel:
    50		bash scripts/smoke_wheel_install.sh
    51	
    52	ci-mirror:
    53		bash scripts/reshape/run_ci_checks.sh
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
astrid/core/rendering/provenance.py:3:1: I001 [*] Import block is un-sorted or un-formatted
   |
 1 |   """Core-owned provenance v2 assembly for timeline renders."""
 2 |
 3 | / from __future__ import annotations
 4 | |
 5 | | from collections.abc import Mapping, Sequence
 6 | | from pathlib import Path
 7 | | from typing import Any
 8 | |
 9 | | from astrid.core.foundation.atomic_io import write_json_atomic
10 | | from astrid.core.foundation.hash import sha256_file
11 | |
12 | | from .contracts import (
13 | |     PROVENANCE_V1_ALWAYS_KEYS,
14 | |     PROVENANCE_V1_COMPATIBILITY_KEYS,
15 | |     PROVENANCE_V2_CORE_KEYS,
16 | |     Attachment,
17 | |     AudioOwnership,
18 | |     RenderPlan,
19 | |     RenderProfile,
20 | |     RenderSegment,
21 | |     VideoArtifact,
22 | |     _json_safe_mapping,
23 | |     _require_sha256,
24 | |     _require_string,
25 | |     _require_workspace_relative_path,
26 | |     _validate_backend_fragments,
27 | | )
   | |_^ I001
   |
   = help: Organize imports

Found 1 error.
[*] 1 fixable with the `--fix` option.

exec
/bin/zsh -lc "sed -n '1,260p' scripts/reshape/compare_ruff_baseline.py; rg -n \"provenance.py|test_contracts.py|I001|F811\" scripts/reshape/baselines -S | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
scripts/reshape/baselines/ruff_astrid.json:17:    "I001": 95,
scripts/reshape/baselines/ruff_astrid.json:24:    "F811": 29

collab: Wait
codex
PASS
tokens used
98,013
PASS
