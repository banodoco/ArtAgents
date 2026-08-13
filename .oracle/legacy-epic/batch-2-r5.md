Reading additional input from stdin...
2026-08-12T07:22:39.943539Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:22:39.943565Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T07:22:39.943570Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff4da-1106-7122-a85d-d8d388985264
--------
user
# Megado Checkpoint — Batch 2 fifth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-2.md (6), -r1 (5), -r2 (6), -r3 (5), -r4 (5). Fifth
rework committed as `3557792f` (prior head 9db48731). Incremental diff at
/tmp/batch2-r5.diff.

## How each of your 5 re-review4 issues was addressed (host-implemented)

1. **Post-SIGKILL drain omits OSError; deadline exit may not reap** →
   - The drain loop now catches OSError alongside TimeoutExpired; after the
     deadline break, the direct child is force-reaped (wait with timeout →
     kill → wait).
2. **support returns supported:true for audio="none"** →
   - `_support` now rejects any request `audio` other than `rendered` (the
     renderer always emits PCM stereo) with a structured unsupported result.
3. **Channels-only fallback bypasses layout normalization** →
   - `_layout_channel_count` lowercases the declared layout before lookup, so
     `"Stereo"` and `"stereo"` both map to 2 channels.
4. **Symlink exemption overbroad** →
   - Exemption now applies ONLY to root-level `/tmp|/var|/etc` →
     `/private/<name>` macOS redirects; any other symlink component (named
     tmp/var/etc elsewhere, or resolving under /private/ from a non-root
     path) is rejected.
5. **read_committed_provenance resolves before guard (symlink loop → RuntimeError)** →
   - The symlink guard runs on unresolved paths FIRST; resolving happens
     after, wrapped with RuntimeError → None (fail closed, never raises).
6. **audio_channels shifts positional MediaProbe fields** →
   - Moved to the END of the dataclass so existing positional construction
     is unaffected.

## Evidence

- Incremental diff: /tmp/batch2-r5.diff (6 files)
- Host-verified: transport (14) + fixture (6) + publication + artifacts +
  media + rendering (153 combined, 2 pre-existing env failures) pass; full
  consolidated acceptance = 746 passed, 2 failed (SAME 2 pre-existing), 3
  skipped.

## Verdict

Binary: `PASS` or a list of issues. Verify the five closures and the field
placement. If PASS, say exactly `PASS`.
codex
I’m using the `megado` skill because this is an explicit Megado checkpoint. I’ll inspect the incremental diff and relevant surrounding code read-only, then return only the required binary verdict.
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

exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show --stat --oneline --decorate --no-renames 3557792f && wc -l /tmp/batch2-r5.diff && sed -n '1,260p' /tmp/batch2-r5.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-2-r5.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3557792f931f224c5f8aea2611c901d0f16baa0f
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
3557792f (HEAD -> oracle-run) batch2-rework5: oracle re-review4 issues 1-5 (OSError-safe drain + guaranteed direct-child reap, support rejects audio!=rendered, layout channel-count normalization, tight root-only macOS symlink exemption, committed-read guard before resolve)
 .oracle/checkins/batch-2-r4.md                     | 20120 +++++++++++++++++++
 astrid/core/media.py                               |     3 +-
 astrid/core/rendering/artifacts.py                 |     2 +-
 astrid/core/rendering/publication.py               |    23 +-
 astrid/core/rendering/transport.py                 |    13 +-
 .../fixtures/renderer_packs/raw_command/backend.py |     7 +-
 6 files changed, 20155 insertions(+), 13 deletions(-)
   20271 /tmp/batch2-r5.diff
diff --git a/.oracle/checkins/batch-2-r4.md b/.oracle/checkins/batch-2-r4.md
new file mode 100644
index 00000000..d7843087
--- /dev/null
+++ b/.oracle/checkins/batch-2-r4.md
@@ -0,0 +1,20120 @@
+Reading additional input from stdin...
+2026-08-12T07:08:03.866098Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T07:08:03.866121Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T07:08:03.866126Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff4cc-b2ea-7441-977e-a994c0b72127
+--------
+user
+# Megado Checkpoint — Batch 2 fourth re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-2.md (6), -r1 (5), -r2 (6), -r3 (5). Fourth rework
+committed as `9db48731` (prior head 8c195bf0). Incremental diff at
+/tmp/batch2-r4.diff.
+
+## How each of your 5 re-review3 issues was addressed (host-implemented)
+
+1. **Transport cleanup unbounded/interruptible** →
+   - Drain `communicate()` now bounded (max(grace, 2.0)s) with
+     TimeoutExpired/KeyboardInterrupt/OSError all escalating to group
+     SIGKILL; the elif-drain branch is likewise bounded. No unguarded
+     communicate remains in cleanup.
+2. **chan atom malformed; layout inference masks** →
+   - chan atom now canonical FFmpeg movenc format: version(2)+revision(2)+
+     layout_tag(4, 0x00650002 stereo)+bitmap(4)+num_descriptions(4).
+   - media.py NO LONGER infers layout from channel count: it reports
+     `audio_channels` and leaves `audio_channel_layout` honest (None).
+   - artifacts.py compares declared layout's canonical channel count against
+     probed `audio_channels` when layout is unprobed (QuickTime sowt
+     limitation) — no guessed layouts; `incomplete_probe` accepts
+     channels-only probes.
+3. **support not profile-fail-closed** →
+   - `_support` now checks EVERY fixed profile field (dimensions, fps,
+     time base, container, codecs, pixel format, profile/level, sample
+     rate, layout); any deviation returns supported:false with reasons.
+4. **Output symlinks followed on ffmpeg/hybrid/audio-reactive routes** →
+   - All three helpers preserve the UNRESOLVED `publication_out` (resolved
+     path used only for temp-dir placement); publication symlink-guards the
+     unresolved path.
+5. **Ancestor symlinks unchecked (symlinked run dirs)** →
+   - `_contains_symlink_component` walks ALL path components, rejecting any
+     non-system symlink (macOS `/tmp`→`/private/tmp`, `/var`→`/private/var`
+     exempted); used in publish guard, committed-pair read, and cleanup.
+
+## Evidence
+
+- Incremental diff: /tmp/batch2-r4.diff (8 files)
+- Host-verified: transport (14) + fixture (6) + publication (7) + artifacts +
+  media (76 combined) pass; rendering tests 77 pass (2 pre-existing env
+  failures); full consolidated acceptance = 746 passed, 2 failed (SAME 2
+  pre-existing), 3 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Verify the five closures: the bounded
+cleanup (no unguarded communicate), the honest probe (channels vs layout),
+the full support fail-closed matrix, unresolved paths on all publish routes,
+and the ancestor-symlink guard (including that it does NOT false-positive on
+macOS system redirects). If PASS, say exactly `PASS`.
+codex
+I’m using the `megado` checkpoint workflow to inspect the incremental diff and verify each of the five claimed closures. I’ll keep the final response strictly to the requested verdict.
+exec
+/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
+
+codex
+The repository guidance also calls for context-minimized parallel review on multi-part checks. I’m applying that guidance by splitting the five independent invariants while I inspect the combined diff and integration points.

exec
/bin/zsh -lc 'git diff --no-ext-diff --unified=100 9db48731..3557792f -- astrid/core/media.py astrid/core/rendering/artifacts.py astrid/core/rendering/publication.py astrid/core/rendering/transport.py astrid/packs/renderer_pack/fixtures/renderer_packs/raw_command/backend.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/media.py b/astrid/core/media.py
index 15543e71..34361284 100644
--- a/astrid/core/media.py
+++ b/astrid/core/media.py
@@ -1,159 +1,160 @@
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
-    audio_channels: int | None = None
     container: str | None = None
     format_name: str | None = None
     duration_rational: tuple[int, int] | None = None
     video_stream_present: bool | None = None
     audio_stream_present: bool | None = None
+    # Appended last so existing positional construction is unaffected.
+    audio_channels: int | None = None
 
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
diff --git a/astrid/core/rendering/artifacts.py b/astrid/core/rendering/artifacts.py
index 92629b49..736bd7a5 100644
--- a/astrid/core/rendering/artifacts.py
+++ b/astrid/core/rendering/artifacts.py
@@ -383,201 +383,201 @@ def _probe_required_video(probe: MediaProbe) -> None:
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
             if field == "audio_channel_layout" and actual is None:
                 # Some containers (QuickTime sowt) expose channel COUNT but
                 # not a named layout. Compare channel count against the
                 # declared layout's canonical count instead of failing.
                 expected_channels = _layout_channel_count(expected)
                 if expected_channels is None or probe.audio_channels != expected_channels:
                     _invalid(
                         "audio_profile_mismatch",
                         f"probed audio channel layout/count does not match {label}",
                         field=field,
                         expected=expected,
                         actual=actual,
                         probed_channels=probe.audio_channels,
                     )
                 continue
             if not _same_profile_value(field, actual, expected):
                 _invalid(
                     "audio_profile_mismatch",
                     f"probed audio {field} does not match {label}",
                     field=field,
                     expected=expected,
                     actual=actual,
                 )
 
 
 def _layout_channel_count(layout: str | None) -> int | None:
     return {
         "mono": 1,
         "stereo": 2,
         "5.1": 6,
         "5.1(side)": 6,
         "7.1": 8,
         "7.1(wide)": 8,
-    }.get(layout or "")
+    }.get((layout or "").lower())
 
 
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
             for field in ("audio_codec", "audio_sample_rate")
             if getattr(probe, field) is None
         ]
         if probe.audio_channel_layout is None and probe.audio_channels is None:
             missing.append("audio_channel_layout/audio_channels")
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
diff --git a/astrid/core/rendering/publication.py b/astrid/core/rendering/publication.py
index 8a094907..fc427c51 100644
--- a/astrid/core/rendering/publication.py
+++ b/astrid/core/rendering/publication.py
@@ -1,284 +1,289 @@
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
 
 
 def _contains_symlink_component(path: str | Path) -> bool:
     """True if a non-system path component is a symbolic link.
 
-    macOS resolves ``/tmp`` -> ``/private/tmp`` and ``/var`` ->
-    ``/private/var``; those system redirects are not containment escapes.
+    Only the macOS system redirects (``/tmp`` -> ``/private/tmp``,
+    ``/var`` -> ``/private/var``, ``/etc`` -> ``/private/etc``) are exempt.
     Any other symlink component (e.g. a symlinked run directory) is treated
     as an escape and rejected.
     """
     current = Path(path).expanduser()
     parts = list(current.parts)
     for index in range(len(parts), 0, -1):
         candidate = Path(*parts[:index])
         try:
             if not candidate.is_symlink():
                 continue
         except OSError:
             return True
         try:
             resolved = candidate.resolve(strict=False)
         except (OSError, RuntimeError):
             return True
-        # System redirects: /tmp, /var, /etc, /private/* -> /private/*
-        if str(resolved).startswith("/private/"):
-            continue
-        if candidate.name in ("tmp", "var", "etc", "home", "usr") and str(resolved).startswith("/"):
+        # macOS system redirect: /<name> -> /private/<name> at the ROOT only.
+        if (
+            len(parts[:index]) == 2
+            and parts[0] == "/"
+            and candidate.name in ("tmp", "var", "etc")
+            and str(resolved) == f"/private/{candidate.name}"
+        ):
             continue
         return True
     return False
 
 
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
 
-    video = _resolved(video_path)
-    sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
     try:
         video_unresolved = Path(video_path).expanduser()
         sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
         if (
             _contains_symlink_component(video_unresolved)
             or _contains_symlink_component(sidecar_unresolved)
         ):
             return None
+        # Resolve only AFTER the symlink guard so a symlink loop cannot
+        # raise RuntimeError here — it must fail closed to None.
+        video = _resolved(video_path)
+        sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
         if video.is_symlink() or sidecar.is_symlink():
             return None
         if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
             return None
         payload = json.loads(sidecar.read_text(encoding="utf-8"))
-    except (OSError, ValueError, TypeError, json.JSONDecodeError):
+    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
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
             if _contains_symlink_component(raw_path):
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
             if _contains_symlink_component(raw_sidecar):
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
diff --git a/astrid/core/rendering/transport.py b/astrid/core/rendering/transport.py
index 74f0919a..12753138 100644
--- a/astrid/core/rendering/transport.py
+++ b/astrid/core/rendering/transport.py
@@ -401,216 +401,227 @@ def _resolve_executable(
 
 
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
                 captured = process.communicate(timeout=max(grace, 2.0))
                 break
-            except subprocess.TimeoutExpired:
+            except (subprocess.TimeoutExpired, OSError):
                 try:
                     _signal_process_group(process, signal.SIGKILL)
                 except (OSError, PermissionError):
                     pass
                 if time.monotonic() > drain_deadline:
                     break
                 continue
             except KeyboardInterrupt:
                 try:
                     _signal_process_group(process, signal.SIGKILL)
                 except (OSError, PermissionError):
                     pass
                 if time.monotonic() > drain_deadline:
                     break
                 continue
+        # Deadline exit still owes a reap of the direct child.
+        if process.returncode is None:
+            try:
+                process.wait(timeout=max(grace, 1.0))
+            except (subprocess.TimeoutExpired, OSError):
+                try:
+                    process.kill()
+                except OSError:
+                    pass
+                process.wait()
+            captured = captured or ("", "")
     elif captured is None:
         # ``poll`` may have reaped the child while checking the fallback path.
         # Its pipes still need to be drained; bound the drain so cleanup can
         # never block forever on a stuck pipe.
         try:
             captured = process.communicate(timeout=max(grace, 2.0))
         except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
             try:
                 _signal_process_group(process, signal.SIGKILL)
             except (OSError, PermissionError):
                 pass
             captured = ("", "")
 
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

exec
/bin/zsh -lc "git diff --name-only 9db48731..3557792f && git diff --no-ext-diff --unified=120 9db48731..3557792f -- '*/fixtures/renderer_packs/raw_command/backend.py'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-2-r4.md
astrid/core/media.py
astrid/core/rendering/artifacts.py
astrid/core/rendering/publication.py
astrid/core/rendering/transport.py
tests/fixtures/renderer_packs/raw_command/backend.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/fixtures/renderer_packs/raw_command/backend.py b/tests/fixtures/renderer_packs/raw_command/backend.py
index ffdc422d..04dc16b1 100644
--- a/tests/fixtures/renderer_packs/raw_command/backend.py
+++ b/tests/fixtures/renderer_packs/raw_command/backend.py
@@ -324,245 +324,250 @@ def _sample_tables(
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
+    mismatches: list[str] = []
+    # The renderer ALWAYS produces rendered PCM stereo audio; a request for
+    # no audio or passthrough contradicts the fixed output.
+    requested_audio = request.get("audio")
+    if requested_audio not in (None, "rendered"):
+        mismatches.append(f"audio={requested_audio!r} (fixed 'rendered')")
     profile = request.get("profile")
     if isinstance(profile, dict):
         # The renderer emits a fixed profile; ANY deviation is unsupported
         # (fail closed on every field, not just codecs/dimensions).
-        mismatches: list[str] = []
         expected = {
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
         }
         for field, fixed in expected.items():
             requested = profile.get(field)
             if requested is not None and requested != fixed:
                 mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
         if mismatches:
             _write_json(
                 result_path,
                 {
                     "schema_version": 1,
                     "supported": False,
                     "reasons": [
                         "profile not produced by " + BACKEND_ID + ": "
                         + "; ".join(mismatches)
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

exec
/bin/zsh -lc 'tail -n 220 .oracle/checkins/batch-2-r4.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The six targeted edits are present. I’m now checking their edge behavior against the surrounding contracts—especially cleanup boundedness and symlink-loop handling—before deciding whether they genuinely close the prior findings.
exec
/bin/zsh -lc "rg -n \"terminate_process_group|post.*SIGKILL|communicate|reap|symlink|_contains_symlink_component|read_committed_provenance|audio_channels|layout_channel_count|audio.*none|_support\" tests/core/rendering/test_transport.py tests/core/rendering/test_publication.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py tests/fixtures/renderer_packs -g '*.py' -g '*.json'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/util/test_media.py:206:        assert probe.audio_channels == 2
tests/core/rendering/test_artifacts.py:167:def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
tests/core/rendering/test_artifacts.py:172:    (workspace / "escape.mp4").symlink_to(outside)
tests/core/rendering/test_transport.py:163:def test_timeout_kills_process_group_and_reaps_direct_child(tmp_path: Path) -> None:
tests/core/rendering/test_transport.py:178:def test_sigterm_ignoring_child_is_escalated_and_reaped(tmp_path: Path) -> None:
tests/core/rendering/test_transport.py:179:    """A child tree that ignores SIGTERM must still be SIGKILLed and reaped."""
tests/core/rendering/test_transport.py:190:def test_sigint_kills_process_group_reaps_and_reraises(tmp_path: Path) -> None:
tests/core/rendering/test_publication.py:17:    read_committed_provenance,
tests/core/rendering/test_publication.py:62:    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
tests/core/rendering/test_publication.py:125:    payload = read_committed_provenance(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:136:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:147:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/fixtures/renderer_packs/raw_command/backend.py:443:def _support(request: dict, result_path: Path) -> int:
tests/fixtures/renderer_packs/raw_command/backend.py:482:                    "features": {"media": False, "audio_mode": "none"},
tests/fixtures/renderer_packs/raw_command/backend.py:621:        return _support(request, result_path)

exec
/bin/zsh -lc "sed -n '1,260p' tests/core/rendering/test_transport.py && sed -n '1,240p' tests/core/rendering/test_publication.py && sed -n '1,260p' tests/core/rendering/test_artifacts.py && sed -n '1,250p' tests/core/util/test_media.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from astrid.core.rendering import RenderPlan, RenderResult, SupportReport
from astrid.core.rendering.errors import (
    RendererBinaryMissingError,
    RendererInternalError,
    RendererInvalidArtifactError,
    RendererProtocolError,
    RendererTimeoutError,
)
from astrid.core.rendering.transport import CommandTransport


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
WIRE_FIXTURE_DIR = FIXTURE_DIR / "v1"
BACKEND_SCRIPT = FIXTURE_DIR / "transport_backend.py"
RENDERER_ID = "acme.visual"


def _wire_fixture(name: str) -> dict[str, Any]:
    return json.loads((WIRE_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _request(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(
    tmp_path: Path,
    payload: dict[str, Any],
    *,
    verb: str = "render",
    backend: str = RENDERER_ID,
    timeout: float = 5,
    env: dict[str, str] | None = None,
    transport: CommandTransport | None = None,
):
    selected = transport or CommandTransport(backend, termination_grace=0.15)
    result_path = tmp_path / "result.json"
    value = selected.run(
        verb,
        [sys.executable, BACKEND_SCRIPT],
        request_path=_request(tmp_path, payload),
        result_path=result_path,
        cwd=FIXTURE_DIR,
        env=env,
        timeout=timeout,
    )
    return selected, value


def _assert_pid_disappears(pid: int, *, timeout: float = 3) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    pytest.fail(f"process {pid} survived process-group cleanup")


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


def test_sigterm_ignoring_child_is_escalated_and_reaped(tmp_path: Path) -> None:
    """A child tree that ignores SIGTERM must still be SIGKILLed and reaped."""
    payload, parent_pid_path, child_pid_path = _tree_request(tmp_path)

    with pytest.raises(RendererTimeoutError) as caught:
        _run(tmp_path, payload, timeout=0.5)

    assert caught.value.error.kind == "timeout"
    parent_pid = int(parent_pid_path.read_text(encoding="utf-8"))
    _assert_pid_disappears(parent_pid)


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

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from astrid.core.foundation.atomic_io import AtomicWriteError, write_json_atomic
from astrid.core.foundation.hash import sha256_file
from astrid.core.rendering import publication
from astrid.core.rendering.errors import RendererInvalidArtifactError
from astrid.core.rendering.publication import (
    is_render_result_committed,
    publish_render_result,
    read_committed_provenance,
)


def _sidecar(video: Path) -> Path:
    return Path(f"{video}.provenance.json")


def _committed_pair(video: Path, *, contents: bytes, timeline: str) -> Path:
    video.parent.mkdir(parents=True, exist_ok=True)
    video.write_bytes(contents)
    sidecar = _sidecar(video)
    write_json_atomic(
        sidecar,
        {
            "schema_version": 1,
            "output": str(video.resolve()),
            "timeline": timeline,
            "sha256": sha256_file(video),
        },
    )
    return sidecar


def test_happy_path_publishes_video_then_hashed_sidecar(tmp_path: Path) -> None:
    source = tmp_path / "work" / "render.mp4"
    source.parent.mkdir()
    source.write_bytes(b"rendered-video")
    output = tmp_path / "runs" / "current" / "hype.mp4"
    sidecar = _sidecar(output)

    result = publish_render_result(
        source,
        {"schema_version": 2, "timeline": "/project/hype.timeline.json"},
        out_path=output,
        sidecar_path=sidecar,
        previous_outputs=(),
    )

    assert result == output.resolve()
    assert not source.exists()
    assert output.read_bytes() == b"rendered-video"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["output"] == str(output.resolve())
    assert payload["sha256"] == sha256_file(output)
    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
    assert is_render_result_committed(output, sidecar_path=sidecar)


def test_concurrent_publishers_serialize_without_interleaving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mp4"
    first.write_bytes(b"first-video")
    second.write_bytes(b"second-video")
    output = tmp_path / "hype.mp4"
    sidecar = _sidecar(output)

    first_in_sidecar_write = threading.Event()
    release_first = threading.Event()
    second_replaced = threading.Event()
    real_replace = publication.os.replace
    real_write_json_atomic = publication.write_json_atomic

    def observing_replace(source: str | Path, destination: str | Path) -> None:
        if Path(source) == second.resolve():
            second_replaced.set()
        real_replace(source, destination)

    def blocking_sidecar_write(path: str | Path, payload: object) -> None:
        if isinstance(payload, dict) and payload.get("publisher") == "first":
            first_in_sidecar_write.set()
            assert release_first.wait(timeout=5)
        real_write_json_atomic(path, payload)

    monkeypatch.setattr(publication.os, "replace", observing_replace)
    monkeypatch.setattr(publication, "write_json_atomic", blocking_sidecar_write)
    errors: list[BaseException] = []

    def worker(source: Path, publisher: str) -> None:
        try:
            publish_render_result(
                source,
                {"timeline": "timeline", "publisher": publisher},
                out_path=output,
                sidecar_path=sidecar,
                previous_outputs=(),
            )
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below.
            errors.append(exc)

    first_thread = threading.Thread(target=worker, args=(first, "first"))
    second_thread = threading.Thread(target=worker, args=(second, "second"))
    first_thread.start()
    assert first_in_sidecar_write.wait(timeout=5)
    second_thread.start()

    assert not second_replaced.wait(timeout=0.2)
    release_first.set()
    first_thread.join(timeout=5)
    second_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert errors == []
    assert second_replaced.is_set()
    assert output.read_bytes() == b"second-video"
    payload = read_committed_provenance(output, sidecar_path=sidecar)
    assert payload is not None
    assert payload["publisher"] == "second"
    assert payload["sha256"] == sha256_file(output)


def test_crash_orphans_are_not_committed_and_can_be_repaired(tmp_path: Path) -> None:
    output = tmp_path / "hype.mp4"
    sidecar = _sidecar(output)
    output.write_bytes(b"orphan")

    assert read_committed_provenance(output, sidecar_path=sidecar) is None
    assert not is_render_result_committed(output, sidecar_path=sidecar)

    write_json_atomic(
        sidecar,
        {
            "output": str(output.resolve()),
            "timeline": "timeline",
            "sha256": "0" * 64,
        },
    )
    assert read_committed_provenance(output, sidecar_path=sidecar) is None
    assert not is_render_result_committed(output, sidecar_path=sidecar)

    replacement = tmp_path / "replacement.mp4"
    replacement.write_bytes(b"replacement")
    publish_render_result(
        replacement,
        {"timeline": "timeline"},
        out_path=output,
        sidecar_path=sidecar,
        previous_outputs=(),
    )
    assert output.read_bytes() == b"replacement"
    assert is_render_result_committed(output, sidecar_path=sidecar)


def test_previous_output_cleanup_is_complete_matching_and_lock_safe(tmp_path: Path) -> None:
    timeline = str((tmp_path / "hype.timeline.json").resolve())
    other_timeline = str((tmp_path / "other.timeline.json").resolve())
    matching = tmp_path / "runs" / "matching" / "hype.mp4"
    nonmatching = tmp_path / "runs" / "nonmatching" / "hype.mp4"
    missing_marker = tmp_path / "runs" / "missing-marker" / "hype.mp4"
    wrong_hash = tmp_path / "runs" / "wrong-hash" / "hype.mp4"
    matching_sidecar = _committed_pair(matching, contents=b"old", timeline=timeline)
    nonmatching_sidecar = _committed_pair(
        nonmatching, contents=b"other", timeline=other_timeline
    )
    missing_marker.parent.mkdir(parents=True)
    missing_marker.write_bytes(b"orphan")
    wrong_hash.parent.mkdir(parents=True)
    wrong_hash.write_bytes(b"wrong")
    wrong_hash_sidecar = _sidecar(wrong_hash)
    write_json_atomic(
        wrong_hash_sidecar,
        {
            "output": str(wrong_hash.resolve()),
            "timeline": timeline,
            "sha256": "f" * 64,
        },
    )

    source = tmp_path / "new.mp4"
    source.write_bytes(b"new")
    live = tmp_path / "runs" / "live" / "hype.mp4"
    live_sidecar = _sidecar(live)
    publish_render_result(
        source,
        {"timeline": timeline},
        out_path=live,
        sidecar_path=live_sidecar,
        previous_outputs=[
            matching,
            nonmatching,
            missing_marker,
            wrong_hash,
            live,
        ],
    )

    assert not matching.exists()
    assert not matching_sidecar.exists()
    assert nonmatching.exists()
    assert nonmatching_sidecar.exists()
    assert missing_marker.exists()
    assert not _sidecar(missing_marker).exists()
    assert wrong_hash.exists()
    assert wrong_hash_sidecar.exists()
    assert live.exists()
    assert live_sidecar.exists()
    assert is_render_result_committed(live, sidecar_path=live_sidecar)


@pytest.mark.parametrize(
    ("write_source", "reason"),
    [
        (False, "missing_artifact"),
        (True, "empty_artifact"),
    ],
)
def test_missing_or_empty_video_fails_structurally_before_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_source: bool,
    reason: str,
) -> None:
    source = tmp_path / "render.mp4"
    if write_source:
        source.write_bytes(b"")
    output = tmp_path / "hype.mp4"
    replace = Mock(side_effect=AssertionError("must not rename"))
    monkeypatch.setattr(publication.os, "replace", replace)

    with pytest.raises(RendererInvalidArtifactError) as caught:
        publish_render_result(
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from astrid.core.foundation.hash import sha256_file
from astrid.core.media import MediaProbe
from astrid.core.rendering import artifacts
from astrid.core.rendering.artifacts import validate_render_result
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    Attachment,
    AudioOwnership,
    RenderProfile,
    RenderResult,
    VideoArtifact,
)
from astrid.core.rendering.errors import RendererInvalidArtifactError


def _profile(*, audio: bool = False, tolerance: int = 1) -> RenderProfile:
    return RenderProfile(
        width=1280,
        height=720,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        duration_tolerance=tolerance,
    )


def _probe(*, audio: bool = False, duration: tuple[int, int] = (2, 1)) -> MediaProbe:
    return MediaProbe(
        duration_seconds=float(duration[0] / duration[1]),
        fps=24.0,
        resolution="1280x720",
        width=1280,
        height=720,
        fps_rational=(24, 1),
        time_base=(1, 12288),
        video_codec="h264",
        pixel_format="yuv420p",
        audio_codec="aac" if audio else None,
        audio_sample_rate=48000 if audio else None,
        audio_channel_layout="stereo" if audio else None,
        container="mp4",
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        duration_rational=duration,
        video_stream_present=True,
        audio_stream_present=audio,
    )


def _result(
    root: Path,
    *,
    profile: RenderProfile | None = None,
    ownership: AudioOwnership = AudioOwnership.NONE,
    path: str = "outputs/video.mp4",
    contents: bytes = b"video-bytes",
    write: bool = True,
    attachments: dict[str, Attachment] | None = None,
) -> RenderResult:
    output = root / path
    if write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(contents)
    digest = sha256_file(output) if output.is_file() else "0" * 64
    video = VideoArtifact(
        path=path,
        profile=profile or _profile(audio=ownership is AudioOwnership.RENDERED),
        sha256=digest,
        duration_frames=48,
        audio=ownership,
        attachments=attachments or {},
    )
    return RenderResult(
        schema_version=SCHEMA_VERSION,
        video=video,
        audio_ownership=ownership,
    )


def _assert_invalid(callable_: object, *, reason: str | None = None) -> RendererInvalidArtifactError:
    with pytest.raises(RendererInvalidArtifactError) as caught:
        callable_()  # type: ignore[operator]
    error = caught.value.error
    assert error.kind == "invalid_artifact"
    assert error.backend == "astrid.core"
    assert error.recovery_command
    if reason is not None:
        assert error.details["reason"] == reason
    return caught.value


def test_happy_path_preserves_named_attachment_objects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attachment_path = tmp_path / "outputs" / "alpha.bin"
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_bytes(b"alpha")
    attachment = Attachment(
        name="alpha",
        path="outputs/alpha.bin",
        kind="alpha",
        sha256=sha256_file(attachment_path),
    )
    result = _result(tmp_path, attachments={attachment.name: attachment})
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    validated = validate_render_result(
        result,
        expected_profile=_profile(),
        workspace_root=tmp_path,
    )

    assert validated is result
    assert validated.attachments["alpha"] is attachment


def test_missing_primary_output_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, write=False)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="missing_artifact",
    )


def test_empty_primary_output_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path, contents=b"")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="empty_artifact",
    )


@pytest.mark.parametrize("bad_path", ["../video.mp4", "/tmp/video.mp4", "outputs/../video.mp4"])
def test_traversal_and_absolute_output_paths_are_rejected(
    tmp_path: Path, bad_path: str
) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video, "path", bad_path)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="escaped_path",
    )


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"video-bytes")
    (workspace / "escape.mp4").symlink_to(outside)
    result = _result(workspace, path="placeholder.mp4")
    object.__setattr__(result.video, "path", "escape.mp4")
    object.__setattr__(result.video, "sha256", sha256_file(outside))

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=workspace
        ),
        reason="escaped_path",
    )


def test_primary_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video, "sha256", "f" * 64)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="hash_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 1920),
        ("height", 1080),
        ("fps_rational", (25, 1)),
        ("time_base", (1, 12800)),
        ("container", "webm"),
        ("video_codec", "hevc"),
        ("pixel_format", "yuv444p"),
    ],
)
def test_probed_video_profile_mismatches_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: replace(_probe(), **{field: value}),
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="profile_mismatch",
    )


def test_declared_profile_mismatch_is_rejected_before_probe(tmp_path: Path) -> None:
    result = _result(tmp_path)
    object.__setattr__(result.video.profile, "width", 1920)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="profile_mismatch",
    )


def test_duration_outside_tolerance_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: _probe(duration=(13, 6)),  # 52 frames, declared 48
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        ),
        reason="duration_mismatch",
    )


def test_duration_at_tolerance_boundary_is_accepted(
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from astrid.core.media import (
    MediaProbeError,
    MediaProbe,
    ffprobe_duration_seconds,
    ffprobe_metadata,
    ffprobe_metadata_strict,
)
from astrid.packs.editorial.executors.editor_review.run import (
    _probe_duration as editor_probe_duration,
)
from astrid.core.verify.checks import ffprobe_duration_seconds as checks_ffprobe_duration_seconds


def test_ffprobe_duration_seconds_uses_duration_only_probe() -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")

    assert ffprobe_duration_seconds("clip.mp4", runner=runner) == 12.5

    cmd, kwargs = calls[0]
    assert cmd == [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        "clip.mp4",
    ]
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert "PATH" in kwargs["env"]
    assert "OPENAI_API_KEY" not in kwargs["env"]


def test_ffprobe_duration_seconds_accepts_explicit_env() -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="12.5\n", stderr="")

    assert (
        ffprobe_duration_seconds(
            "clip.mp4", runner=runner, env={"FFPROBE_DATADIR": "/tmp/ffprobe"}
        )
        == 12.5
    )

    assert calls[0][1]["env"]["FFPROBE_DATADIR"] == "/tmp/ffprobe"


def test_updated_duration_helpers_preserve_float_parsing(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"not-real-media")

    def fake_runner(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, stdout="7.25\n", stderr="")

    assert ffprobe_duration_seconds(media, runner=fake_runner) == 7.25
    assert editor_probe_duration(media, ffprobe_runner=fake_runner) == 7.25


def test_verify_uses_canonical_media_helper() -> None:
    assert checks_ffprobe_duration_seconds is ffprobe_duration_seconds


# ---------------------------------------------------------------------------
# MediaProbe and ffprobe_metadata tests (mocked subprocess, no real ffprobe)
# ---------------------------------------------------------------------------


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

    def test_channels_reported_without_inferred_layout(self) -> None:
        """Probes that report channel COUNT without channel_layout (e.g.
        QuickTime sowt) must stay honest: layout stays None, channels is
        reported, and validation compares counts (never guessed layouts)."""
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
        assert probe.audio_channel_layout is None
        assert probe.audio_channels == 2

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

exec
/bin/zsh -lc "sed -n '220,520p' tests/core/rendering/test_publication.py && sed -n '250,620p' tests/core/rendering/test_artifacts.py && sed -n '220,420p' tests/core/util/test_media.py && sed -n '1,180p' tests/fixtures/renderer_packs/raw_command/requests/support.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    ("write_source", "reason"),
    [
        (False, "missing_artifact"),
        (True, "empty_artifact"),
    ],
)
def test_missing_or_empty_video_fails_structurally_before_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    write_source: bool,
    reason: str,
) -> None:
    source = tmp_path / "render.mp4"
    if write_source:
        source.write_bytes(b"")
    output = tmp_path / "hype.mp4"
    replace = Mock(side_effect=AssertionError("must not rename"))
    monkeypatch.setattr(publication.os, "replace", replace)

    with pytest.raises(RendererInvalidArtifactError) as caught:
        publish_render_result(
            source,
            {"timeline": "timeline"},
            out_path=output,
            sidecar_path=_sidecar(output),
            previous_outputs=(),
        )

    assert caught.value.error.kind == "invalid_artifact"
    assert caught.value.error.details["reason"] == reason
    replace.assert_not_called()
    assert not output.exists()
    assert not _sidecar(output).exists()


def test_sidecar_write_failure_leaves_recoverable_uncommitted_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "render.mp4"
    source.write_bytes(b"complete-video")
    output = tmp_path / "hype.mp4"
    sidecar = _sidecar(output)

    def fail_sidecar(_path: str | Path, _payload: object) -> None:
        raise AtomicWriteError("synthetic sidecar failure")

    monkeypatch.setattr(publication, "write_json_atomic", fail_sidecar)
    with pytest.raises(AtomicWriteError, match="synthetic sidecar failure"):
        publish_render_result(
            source,
            {"timeline": "timeline"},
            out_path=output,
            sidecar_path=sidecar,
            previous_outputs=(),
        )

    assert not source.exists()
    assert output.read_bytes() == b"complete-video"
    assert not sidecar.exists()
    assert not is_render_result_committed(output, sidecar_path=sidecar)
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        ),
        reason="duration_mismatch",
    )


def test_duration_at_tolerance_boundary_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: _probe(duration=(49, 24)),  # exactly 49 frames
    )

    assert (
        validate_render_result(
            result, expected_profile=_profile(tolerance=1), workspace_root=tmp_path
        )
        is result
    )


def test_rendered_ownership_without_audio_stream_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile = _profile(audio=True)
    result = _result(
        tmp_path,
        profile=profile,
        ownership=AudioOwnership.RENDERED,
    )
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=profile, workspace_root=tmp_path
        ),
        reason="audio_ownership_mismatch",
    )


def test_none_ownership_with_audio_stream_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path)
    monkeypatch.setattr(
        artifacts, "ffprobe_metadata_strict", lambda _path: _probe(audio=True)
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="audio_ownership_mismatch",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("audio_codec", "opus"),
        ("audio_sample_rate", 44100),
        ("audio_channel_layout", "mono"),
    ],
)
def test_rendered_audio_profile_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    profile = _profile(audio=True)
    result = _result(tmp_path, profile=profile, ownership=AudioOwnership.RENDERED)
    monkeypatch.setattr(
        artifacts,
        "ffprobe_metadata_strict",
        lambda _path: replace(_probe(audio=True), **{field: value}),
    )

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=profile, workspace_root=tmp_path
        ),
        reason="audio_profile_mismatch",
    )


def test_passthrough_visual_artifact_may_target_canonical_audio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _result(tmp_path, ownership=AudioOwnership.PASSTHROUGH)
    monkeypatch.setattr(artifacts, "ffprobe_metadata_strict", lambda _path: _probe())

    assert (
        validate_render_result(
            result,
            expected_profile=_profile(audio=True),
            workspace_root=tmp_path,
        )
        is result
    )


def _attachment_result(tmp_path: Path) -> tuple[RenderResult, Attachment]:
    path = tmp_path / "attachments" / "data.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"attachment")
    attachment = Attachment(
        name="data",
        path="attachments/data.bin",
        kind="project",
        sha256=sha256_file(path),
    )
    return _result(tmp_path, attachments={"data": attachment}), attachment


def test_missing_attachment_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    (tmp_path / attachment.path).unlink()

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="missing_artifact",
    )


def test_invalid_attachment_path_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "path", "../data.bin")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="escaped_path",
    )


def test_invalid_attachment_kind_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "kind", "Bad Kind")

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="invalid_attachment_kind",
    )


def test_attachment_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    result, attachment = _attachment_result(tmp_path)
    object.__setattr__(attachment, "sha256", "a" * 64)

    _assert_invalid(
        lambda: validate_render_result(
            result, expected_profile=_profile(), workspace_root=tmp_path
        ),
        reason="hash_mismatch",
    )

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
            mock_run.return_value = subprocess.CompletedProcess(
                [], 1, stdout="", stderr="bad input"
            )
            with pytest.raises(MediaProbeError, match="ffprobe failed"):
                ffprobe_metadata_strict("video.mp4")

    def test_invalid_json(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout="not json", stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_timeout(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=[], timeout=1.0)
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_oserror(self) -> None:
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.side_effect = OSError("bad things")
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_missing_format_block(self) -> None:
        no_fmt = json.dumps({"streams": []})
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=no_fmt, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_non_numeric_duration(self) -> None:
        bad_dur = json.dumps(
            {"format": {"duration": "nope"}, "streams": []}
        )
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=bad_dur, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds is None

    def test_no_video_stream(self) -> None:
        no_video = json.dumps(
            {
                "format": {"duration": "3.0"},
                "streams": [{"codec_type": "audio"}],
            }
        )
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=no_video, stderr=""
            )
            probe = ffprobe_metadata("audio.aac")
        assert probe.duration_seconds == 3.0
        assert probe.fps is None
        assert probe.resolution is None

    def test_division_by_zero_fps(self) -> None:
        zero_den = json.dumps(
            {
                "format": {"duration": "1.0"},
                "streams": [
                    {
                        "codec_type": "video",
                        "width": 100,
                        "height": 100,
                        "r_frame_rate": "30/0",
                    }
                ],
            }
        )
        with patch("subprocess.run") as mock_run, patch(
            "shutil.which", return_value="/usr/bin/ffprobe"
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                [], 0, stdout=zero_den, stderr=""
            )
            probe = ffprobe_metadata("video.mp4")
        assert probe.duration_seconds == 1.0
        assert probe.resolution == "100x100"
        assert probe.fps is None  # division by zero swallowed
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

exec
/bin/zsh -lc "rg -n \"class RenderRequest|audio:\" astrid/core/rendering/contracts.py astrid/core/rendering/schemas/v1/request.schema.json docs/contracts/render-backend-v1.md && sed -n '260,430p' astrid/core/rendering/contracts.py && sed -n '1,220p' astrid/core/rendering/schemas/v1/request.schema.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
rg: astrid/core/rendering/schemas/v1/request.schema.json: No such file or directory (os error 2)
astrid/core/rendering/contracts.py:586:    if profile.has_audio:
astrid/core/rendering/contracts.py:674:    audio: AudioOwnership | None = None
astrid/core/rendering/contracts.py:735:        audio: AudioOwnership | None = None,
astrid/core/rendering/contracts.py:775:class RenderRequest:
astrid/core/rendering/contracts.py:783:    audio: AudioOwnership | None = None

exec
/bin/zsh -lc "sed -n '640,850p' astrid/core/rendering/contracts.py
rg --files astrid/core/rendering | rg 'schema|request'
rg -n 'audio|RenderRequest|render request' docs/contracts/render-backend-v1.md | head -100" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
        relative, resolved = _relative_file_path(path, workspace_root, "attachment path")
        return cls(name=name, path=relative, kind=kind, sha256=sha256_file(resolved))


def _coerce_attachment_mapping(value: Any, label: str) -> dict[str, Attachment]:
    mapping = _require_mapping(value, label)
    result: dict[str, Attachment] = {}
    seen_names: set[str] = set()
    for raw_key, raw_attachment in mapping.items():
        key = _require_string(raw_key, f"{label} key")
        attachment = (
            raw_attachment
            if isinstance(raw_attachment, Attachment)
            else Attachment.from_dict(_require_mapping(raw_attachment, f"{label}[{key!r}]"))
        )
        if attachment.name != key:
            raise ValueError(
                f"{label} key {key!r} must match attachment.name {attachment.name!r}"
            )
        if attachment.name in seen_names:
            raise ValueError(f"duplicate attachment name: {attachment.name}")
        seen_names.add(attachment.name)
        result[key] = attachment
    return result


@dataclass(frozen=True)
class VideoArtifact:
    """The required primary video produced by a renderer or finalizer."""

    path: str
    profile: RenderProfile
    sha256: str
    duration_frames: int
    audio: AudioOwnership | None = None
    attachments: dict[str, Attachment] = field(default_factory=dict)

    def __post_init__(self) -> None:
        profile = (
            self.profile
            if isinstance(self.profile, RenderProfile)
            else RenderProfile.from_dict(_require_mapping(self.profile, "video profile"))
        )
        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "video path"))
        object.__setattr__(self, "profile", profile)
        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
        object.__setattr__(
            self,
            "duration_frames",
            _require_int(self.duration_frames, "duration_frames", minimum=1),
        )
        audio = _coerce_audio_ownership(self.audio, "video audio", nullable=True)
        _validate_artifact_audio(profile, audio, "video artifact")
        object.__setattr__(self, "audio", audio)
        object.__setattr__(
            self,
            "attachments",
            _coerce_attachment_mapping(self.attachments, "video attachments"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "path": self.path,
                "profile": self.profile,
                "sha256": self.sha256,
                "duration_frames": self.duration_frames,
                "audio": self.audio,
                "attachments": self.attachments,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> VideoArtifact:
        data = _require_mapping(payload, "video artifact")
        required = {"path", "profile", "sha256", "duration_frames"}
        allowed = required | {"audio", "attachments"}
        _validate_object_keys(data, required=required, allowed=allowed, label="video artifact")
        return cls(
            path=data["path"],
            profile=RenderProfile.from_dict(data["profile"]),
            sha256=data["sha256"],
            duration_frames=data["duration_frames"],
            audio=data.get("audio"),
            attachments=data.get("attachments", {}),
        )

    @classmethod
    def from_file(
        cls,
        *,
        path: str | Path,
        workspace_root: str | Path,
        profile: RenderProfile,
        duration_frames: int,
        audio: AudioOwnership | None = None,
        attachments: Mapping[str, Attachment] | None = None,
    ) -> VideoArtifact:
        relative, resolved = _relative_file_path(path, workspace_root, "video path")
        return cls(
            path=relative,
            profile=profile,
            sha256=sha256_file(resolved),
            duration_frames=duration_frames,
            audio=audio,
            attachments=dict(attachments or {}),
        )


def _coerce_profile(value: Any, label: str, *, nullable: bool) -> RenderProfile | None:
    if value is None and nullable:
        return None
    if isinstance(value, RenderProfile):
        return value
    return RenderProfile.from_dict(_require_mapping(value, label))


def _coerce_window(value: Any, label: str, *, nullable: bool) -> FrameWindow | None:
    if value is None and nullable:
        return None
    if isinstance(value, FrameWindow):
        return value
    return FrameWindow.from_dict(_require_mapping(value, label))


def _coerce_namespaced_backend_config(value: Any, label: str) -> BackendConfig:
    mapping = _require_mapping(value, label)
    result: BackendConfig = {}
    for raw_backend, raw_config in mapping.items():
        backend = _require_qualified_id(raw_backend, f"{label} key")
        result[backend] = _json_safe_mapping(raw_config, label=f"{label}[{backend!r}]")
    return result


@dataclass(frozen=True)
class RenderRequest:
    """Backend-neutral request shared by render, support, and plan operations."""

    schema_version: int
    timeline_path: str
    output_name: str
    assets_registry_path: str | None = None
    window: FrameWindow | None = None
    audio: AudioOwnership | None = None
    profile: RenderProfile | None = None
    backend_config: BackendConfig = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != SCHEMA_VERSION:
            _protocol_failure(
                f"unknown or malformed render request schema_version "
                f"{self.schema_version!r}; expected integer {SCHEMA_VERSION}",
                details={"received": self.schema_version, "supported": [SCHEMA_VERSION]},
            )
        version = self.schema_version
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "timeline_path", _require_string(self.timeline_path, "timeline_path"))
        object.__setattr__(
            self,
            "assets_registry_path",
            _require_optional_string(self.assets_registry_path, "assets_registry_path"),
        )
        output_name = _require_string(self.output_name, "output_name")
        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
            raise ValueError("output_name must be a portable basename without path separators")
        object.__setattr__(self, "output_name", output_name)
        object.__setattr__(self, "window", _coerce_window(self.window, "window", nullable=True))
        audio = _coerce_audio_ownership(self.audio, "audio", nullable=True)
        profile = _coerce_profile(self.profile, "profile", nullable=True)
        if audio is not None and profile is not None:
            _validate_artifact_audio(profile, audio, "render request")
        object.__setattr__(self, "audio", audio)
        object.__setattr__(self, "profile", profile)
        object.__setattr__(
            self,
            "backend_config",
            _coerce_namespaced_backend_config(self.backend_config, "backend_config"),
        )
        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "timeline_path": self.timeline_path,
                "assets_registry_path": self.assets_registry_path,
                "output_name": self.output_name,
                "window": self.window,
                "audio": self.audio,
                "profile": self.profile,
                "backend_config": self.backend_config,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderRequest:
        try:
            data = _require_mapping(payload, "render request")
            allowed = {
                "schema_version",
                "timeline_path",
                "assets_registry_path",
                "output_name",
                "window",
                "audio",
                "profile",
                "backend_config",
                "metadata",
            }
astrid/core/rendering/schemas/v1/support.json
astrid/core/rendering/schemas/v1/finalize.json
astrid/core/rendering/schemas/v1/renderer-manifest.json
astrid/core/rendering/schemas/v1/planner-manifest.json
astrid/core/rendering/schemas/v1/result.json
astrid/core/rendering/schemas/v1/plan.json
astrid/core/rendering/schemas/v1/finalizer-manifest.json
astrid/core/rendering/schemas/v1/request.json
76:whole-timeline and window support, output-profile labels, and possible audio
78:Finalizer hints cover containers, attachment preservation, audio modes, and
100:  audio_ownership: [passthrough, none]
181:- the optional audio trio `audio_codec`, `audio_sample_rate`, and
182:  `audio_channel_layout`, either all populated or all omitted/`null`;
185:A visual-only profile omits all three audio fields or sets them all to `null`;
192:`RenderRequest` contains:
199:- nullable requested `audio` ownership (`null` means backend default);
239:## Primary video, media, and audio ownership
248:- artifact `audio` ownership (nullable only before it is wrapped in a successful
254:pixel format, and declared audio state before assembly or publication.
258:- `rendered`: the backend owns and returns final timeline audio in the video;
260:  or mux the canonical source/timeline audio;
261:- `none`: the intended output has no audio.
264:complete populated audio trio because the returned artifact contains audio.
266:host/finalizer to supply canonical audio later, while none declares that no
267:audio is intended. When a request supplies both non-null fields, it follows the
268:same relationship; it may leave audio or profile `null` for a backend/host
270:A successful `RenderResult.audio_ownership` is never null and must exactly
271:match its non-null `VideoArtifact.audio`. Visual-only renderers are valid and
279:`frames`, `audio-stem`, and `project`; the list is illustrative, not an enum.
295:`audio_ownership`, `normalization` descriptions, redacted `logs`, and string
344:`RenderRequest` payload (sorted keys, no whitespace) that produced this plan.
403:audio codec/sample rate/channel layout, and audio presence. Every performed
468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
515:`audio_reactive_colour`, in addition to the already core-owned
522:`audio_reactive_colour`) remain conditional on the applicable render path.
529:cannot replace routing, identity, inputs, segments, artifacts, audio,
561:`RenderRequest`, `SupportReport`, `RenderPlan`, `FinalizeRequest`, successful
613:    workspace allocation, output probing and normalization, audio

exec
/bin/zsh -lc "sed -n '850,930p' astrid/core/rendering/contracts.py
sed -n '170,285p' docs/contracts/render-backend-v1.md
sed -n '1,220p' astrid/core/rendering/schemas/v1/request.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
            }
            _validate_object_keys(
                data,
                required={"schema_version", "timeline_path", "output_name"},
                allowed=allowed,
                label="render request",
            )
            version = data["schema_version"]
            if type(version) is not int or version != SCHEMA_VERSION:
                _protocol_failure(
                    f"unknown or malformed render request schema_version {version!r}; "
                    f"expected integer {SCHEMA_VERSION}",
                    details={"received": version, "supported": [SCHEMA_VERSION]},
                )
            return cls(
                schema_version=version,
                timeline_path=data["timeline_path"],
                assets_registry_path=data.get("assets_registry_path"),
                output_name=data["output_name"],
                window=data.get("window"),
                audio=data.get("audio"),
                profile=data.get("profile"),
                backend_config=data.get("backend_config", {}),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed render request: {exc}",
                details={"error_type": type(exc).__name__},
            )

    def for_backend(self, backend: str) -> RenderRequest:
        """Return the request projection visible to one selected backend."""

        qualified = _require_qualified_id(backend, "backend")
        selected = self.backend_config.get(qualified)
        return RenderRequest(
            schema_version=self.schema_version,
            timeline_path=self.timeline_path,
            assets_registry_path=self.assets_registry_path,
            output_name=self.output_name,
            window=self.window,
            audio=self.audio,
            profile=self.profile,
            backend_config={qualified: selected} if selected is not None else {},
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class SupportReport:
    """Request-sensitive support evidence returned by an implementation."""

    schema_version: int
    supported: bool
    reasons: list[str]
    features: dict[str, bool | str]
    alternatives: list[str]
    backend: str
    backend_version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _require_schema_version(self.schema_version, "support report"),
        )
        if not isinstance(self.supported, bool):
            raise TypeError("supported must be a boolean")
        object.__setattr__(self, "reasons", _require_string_list(self.reasons, "reasons"))
        feature_mapping = _require_mapping(self.features, "features")
        features: dict[str, bool | str] = {}
        for raw_key, raw_value in feature_mapping.items():
            key = _require_string(raw_key, "feature key")
            if not isinstance(raw_value, (bool, str)):
                raise TypeError(f"features[{key!r}] must be a boolean or string")
            features[key] = raw_value

### Render profile

A `RenderProfile` describes the media that must actually be probed, not merely
the requested encoder flags:

- positive `width` and `height`;
- rational `fps_rational` and stream `time_base`;
- non-empty `container`, `video_codec`, and `pixel_format`;
- nullable `video_profile` and `video_level` when the codec does not expose
  them;
- the optional audio trio `audio_codec`, `audio_sample_rate`, and
  `audio_channel_layout`, either all populated or all omitted/`null`;
- `duration_tolerance`, a non-negative integer measured in **frames**.

A visual-only profile omits all three audio fields or sets them all to `null`;
canonical DTO output uses explicit nulls. One frame is the V1 default duration
tolerance. This tolerance never changes window bounds; it only controls
artifact acceptance.

## Render request and configuration namespacing

`RenderRequest` contains:

- `schema_version` (required integer `1`);
- `timeline_path` (required input path);
- optional nullable `assets_registry_path`;
- `output_name`, a portable basename with no separator or traversal;
- nullable `window` (`null` means the complete timeline);
- nullable requested `audio` ownership (`null` means backend default);
- nullable `profile` (`null` means the host resolves the canonical profile);
- `backend_config`, an object keyed only by qualified implementation IDs;
- string-to-string `metadata`, for correlation data such as project, run, or
  session IDs.

The timeline stays backend-neutral. No Remotion, FFmpeg, Blender, Unreal, or
other implementation field may appear at the request top level. Configuration
is scoped like this:

```json
{
  "backend_config": {
    "acme.example": {"quality": "preview"},
    "rendering.ffmpeg-finalizer": {"faststart": true}
  }
}
```

Before invoking an implementation, the host removes unrelated namespaces.
The renderer receives an empty mapping or only its own namespace. A finalize
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
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://astrid.local/schemas/rendering/v1/request.json",
  "title": "Astrid render request v1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "timeline_path",
    "output_name"
  ],
  "properties": {
    "schema_version": {
      "type": "integer",
      "const": 1
    },
    "timeline_path": {
      "type": "string",
      "minLength": 1,
      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
    },
    "assets_registry_path": {
      "type": [
        "string",
        "null"
      ],
      "minLength": 1,
      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
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
    "window": {
      "anyOf": [
        {
          "$ref": "#/definitions/frameWindow"
        },
        {
          "type": "null"
        }
      ]
    },
    "audio": {
      "anyOf": [
        {
          "$ref": "#/definitions/audioOwnership"
        },
        {
          "type": "null"
        }
      ]
    },
    "profile": {
      "anyOf": [
        {
          "$ref": "#/definitions/renderProfile"
        },
        {
          "type": "null"
        }
      ]
    },
    "backend_config": {
      "$ref": "#/definitions/backendConfig"
    },
    "metadata": {
      "$ref": "#/definitions/stringMap"
    }
  },
  "allOf": [
    {
      "if": {
        "required": [
          "audio",
          "profile"
        ],
        "properties": {
          "audio": {
            "const": "rendered"
          },
          "profile": {
            "type": "object"
          }
        }
      },
      "then": {
        "properties": {
          "profile": {
            "required": [
              "audio_codec",
              "audio_sample_rate",
              "audio_channel_layout"
            ],
            "properties": {
              "audio_codec": {
                "type": "string",
                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
              }
            }
          }
        }
      }
    },
    {
      "if": {
        "required": [
          "audio",
          "profile"
        ],
        "properties": {
          "audio": {
            "enum": [
              "passthrough",
              "none"
            ]
          },
          "profile": {
            "type": "object"
          }
        }
      },
      "then": {
        "properties": {
          "profile": {
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
          }
        }
      }
    }
  ],
  "definitions": {
    "qualifiedId": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
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

exec
/bin/zsh -lc "sed -n '1,560p' astrid/core/rendering/artifacts.py
sed -n '130,245p' astrid/core/media.py
sed -n '80,390p' astrid/core/rendering/publication.py
sed -n '420,535p' astrid/core/rendering/transport.py
sed -n '420,510p' tests/fixtures/renderer_packs/raw_command/backend.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
"""Strict validation for renderer and finalizer artifacts."""

from __future__ import annotations

import math
import re
import stat
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, NoReturn

from astrid.core.foundation.hash import sha256_file
from astrid.core.media import MediaProbe, MediaProbeError, ffprobe_metadata_strict

from .contracts import (
    Attachment,
    AudioOwnership,
    RenderProfile,
    RenderResult,
    VideoArtifact,
)
from .errors import raise_invalid_artifact_error, raise_protocol_error


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_ECMA_WHITESPACE = (
    " \t\n\r\f\v\u00a0\u1680"
    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
    "\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_BACKEND = "astrid.core"
_RECOVERY = (
    "rerun the renderer in a fresh invocation workspace and emit a contained, "
    "non-empty artifact matching the canonical render profile"
)


def _invalid(reason: str, message: str, **details: Any) -> NoReturn:
    raise_invalid_artifact_error(
        backend=_BACKEND,
        message=message,
        recovery_command=_RECOVERY,
        details={"reason": reason, **details},
    )


def _coerce_result(result: RenderResult | Mapping[str, Any]) -> RenderResult:
    if isinstance(result, RenderResult):
        return result
    if isinstance(result, Mapping):
        return RenderResult.from_dict(result)
    raise_protocol_error(
        backend=_BACKEND,
        message="render result must be a RenderResult or result mapping",
        details={"received_type": type(result).__name__},
    )


def _coerce_expected_profile(
    profile: RenderProfile | Mapping[str, Any],
) -> RenderProfile:
    try:
        if isinstance(profile, RenderProfile):
            candidate = profile
        elif isinstance(profile, Mapping):
            candidate = RenderProfile.from_dict(profile)
        else:
            raise_protocol_error(
                backend=_BACKEND,
                message="expected_profile must be a RenderProfile or profile mapping",
                details={"received_type": type(profile).__name__},
            )
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
    if candidate.is_symlink():
        _invalid(
            "escaped_path",
            f"{label} must not be a symbolic link: {relative}",
            path=relative,
        )
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
            actual=value,
        )
    return Fraction(value[0], value[1])


def _text(value: Any) -> str | None:
    return value.strip().lower() if isinstance(value, str) and value.strip() else None


def _level(value: Any) -> str | None:
    normalized = _text(value)
    if normalized is None:
        return None
    if normalized.isdigit() and len(normalized) >= 2:
        return f"{int(normalized[:-1])}.{normalized[-1]}"
    return normalized


def _container_matches(probe: MediaProbe, expected: str) -> bool:
    target = expected.lower().lstrip(".")
    probed_container = _text(probe.container)
    if probed_container is not None:
        return probed_container == target
    format_names = {
        item.strip().lower()
        for item in (probe.format_name or "").split(",")
        if item.strip()
    }
    return target in format_names


def _profile_value(profile: RenderProfile, field: str) -> Any:
    return getattr(profile, field)


def _same_profile_value(field: str, actual: Any, expected: Any) -> bool:
    if field in {"fps_rational", "time_base"}:
        try:
            return Fraction(*actual) == Fraction(*expected)
        except (TypeError, ValueError, ZeroDivisionError):
            return False
    if field == "video_level":
        return _level(actual) == _level(expected)
    if field in {
        "container",
        "video_codec",
        "video_profile",
        "pixel_format",
        "audio_codec",
        "audio_channel_layout",
    }:
        return _text(actual) == _text(expected)
    return actual == expected


def _compare_declared_to_expected(
    declared: RenderProfile,
    expected: RenderProfile,
    ownership: AudioOwnership,
) -> None:
    fields = (
        "width",
        "height",
        "fps_rational",
        "time_base",
        "container",
        "video_codec",
        "pixel_format",
    )
    for field in fields:
        actual_value = _profile_value(declared, field)
        expected_value = _profile_value(expected, field)
        if not _same_profile_value(field, actual_value, expected_value):
            _invalid(
                "profile_mismatch",
                f"renderer video profile has incompatible {field}",
                field=field,
                expected=expected_value,
                actual=actual_value,
            )
    for field in ("video_profile", "video_level"):
        expected_value = _profile_value(expected, field)
        if expected_value is not None and not _same_profile_value(
            field, _profile_value(declared, field), expected_value
        ):
            _invalid(
                "profile_mismatch",
                f"renderer video profile has incompatible {field}",
                field=field,
                expected=expected_value,
                actual=_profile_value(declared, field),
            )

    if ownership is AudioOwnership.RENDERED:
        if not expected.has_audio:
            _invalid(
                "audio_profile_mismatch",
                "renderer declared rendered audio for a visual-only canonical profile",
                expected_audio=False,
                actual_audio=True,
            )
        for field in ("audio_codec", "audio_sample_rate", "audio_channel_layout"):
            if not _same_profile_value(
                field, _profile_value(declared, field), _profile_value(expected, field)
            ):
                _invalid(
                    "audio_profile_mismatch",
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
            if field == "audio_channel_layout" and actual is None:
                # Some containers (QuickTime sowt) expose channel COUNT but
                # not a named layout. Compare channel count against the
                # declared layout's canonical count instead of failing.
                expected_channels = _layout_channel_count(expected)
                if expected_channels is None or probe.audio_channels != expected_channels:
                    _invalid(
                        "audio_profile_mismatch",
                        f"probed audio channel layout/count does not match {label}",
                        field=field,
                        expected=expected,
                        actual=actual,
                        probed_channels=probe.audio_channels,
                    )
                continue
            if not _same_profile_value(field, actual, expected):
                _invalid(
                    "audio_profile_mismatch",
                    f"probed audio {field} does not match {label}",
                    field=field,
                    expected=expected,
                    actual=actual,
                )


def _layout_channel_count(layout: str | None) -> int | None:
    return {
        "mono": 1,
        "stereo": 2,
        "5.1": 6,
        "5.1(side)": 6,
        "7.1": 8,
        "7.1(wide)": 8,
    }.get((layout or "").lower())


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
            for field in ("audio_codec", "audio_sample_rate")
            if getattr(probe, field) is None
        ]
        if probe.audio_channel_layout is None and probe.audio_channels is None:
            missing.append("audio_channel_layout/audio_channels")
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
        probe.audio_channels = _int_or_none(audio_stream.get("channels"), minimum=1)
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
    return _FcntlLock(lock_path)


def _default_sidecar_path(video_path: Path) -> Path:
    return Path(f"{video_path}.provenance.json")


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _contains_symlink_component(path: str | Path) -> bool:
    """True if a non-system path component is a symbolic link.

    Only the macOS system redirects (``/tmp`` -> ``/private/tmp``,
    ``/var`` -> ``/private/var``, ``/etc`` -> ``/private/etc``) are exempt.
    Any other symlink component (e.g. a symlinked run directory) is treated
    as an escape and rejected.
    """
    current = Path(path).expanduser()
    parts = list(current.parts)
    for index in range(len(parts), 0, -1):
        candidate = Path(*parts[:index])
        try:
            if not candidate.is_symlink():
                continue
        except OSError:
            return True
        try:
            resolved = candidate.resolve(strict=False)
        except (OSError, RuntimeError):
            return True
        # macOS system redirect: /<name> -> /private/<name> at the ROOT only.
        if (
            len(parts[:index]) == 2
            and parts[0] == "/"
            and candidate.name in ("tmp", "var", "etc")
            and str(resolved) == f"/private/{candidate.name}"
        ):
            continue
        return True
    return False


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

    try:
        video_unresolved = Path(video_path).expanduser()
        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
        if (
            _contains_symlink_component(video_unresolved)
            or _contains_symlink_component(sidecar_unresolved)
        ):
            return None
        # Resolve only AFTER the symlink guard so a symlink loop cannot
        # raise RuntimeError here — it must fail closed to None.
        video = _resolved(video_path)
        sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
        if video.is_symlink() or sidecar.is_symlink():
            return None
        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
            return None
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
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
            if _contains_symlink_component(raw_path):
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
            if _contains_symlink_component(raw_sidecar):
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
    if (
        _contains_symlink_component(source_unresolved)
        or _contains_symlink_component(output_unresolved)
        or _contains_symlink_component(sidecar_unresolved)
    ):
        raise_invalid_artifact_error(
            backend=_BACKEND,
            message="publication paths must not be symbolic links (or contain symlinked directories)",
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
                captured = process.communicate(timeout=max(grace, 2.0))
                break
            except (subprocess.TimeoutExpired, OSError):
                try:
                    _signal_process_group(process, signal.SIGKILL)
                except (OSError, PermissionError):
                    pass
                if time.monotonic() > drain_deadline:
                    break
                continue
            except KeyboardInterrupt:
                try:
                    _signal_process_group(process, signal.SIGKILL)
                except (OSError, PermissionError):
                    pass
                if time.monotonic() > drain_deadline:
                    break
                continue
        # Deadline exit still owes a reap of the direct child.
        if process.returncode is None:
            try:
                process.wait(timeout=max(grace, 1.0))
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                except OSError:
                    pass
                process.wait()
            captured = captured or ("", "")
    elif captured is None:
        # ``poll`` may have reaped the child while checking the fallback path.
        # Its pipes still need to be drained; bound the drain so cleanup can
        # never block forever on a stuck pipe.
        try:
            captured = process.communicate(timeout=max(grace, 2.0))
        except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
            try:


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
    mismatches: list[str] = []
    # The renderer ALWAYS produces rendered PCM stereo audio; a request for
    # no audio or passthrough contradicts the fixed output.
    requested_audio = request.get("audio")
    if requested_audio not in (None, "rendered"):
        mismatches.append(f"audio={requested_audio!r} (fixed 'rendered')")
    profile = request.get("profile")
    if isinstance(profile, dict):
        # The renderer emits a fixed profile; ANY deviation is unsupported
        # (fail closed on every field, not just codecs/dimensions).
        expected = {
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
        }
        for field, fixed in expected.items():
            requested = profile.get(field)
            if requested is not None and requested != fixed:
                mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
        if mismatches:
            _write_json(
                result_path,
                {
                    "schema_version": 1,
                    "supported": False,
                    "reasons": [
                        "profile not produced by " + BACKEND_ID + ": "
                        + "; ".join(mismatches)
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

exec
/bin/zsh -lc "rg -n \"def _require_string|class RenderProfile|audio_channel_layout\" astrid/core/rendering/contracts.py | head -80 && sed -n '80,160p' astrid/core/rendering/contracts.py && sed -n '410,610p' astrid/core/rendering/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
226:def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
273:def _require_string_list(value: Any, label: str) -> list[str]:
279:def _require_string_mapping(value: Any, label: str) -> dict[str, str]:
452:class RenderProfile:
466:    audio_channel_layout: str | None = None
490:            self.audio_channel_layout,
496:                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
508:                "audio_channel_layout",
509:                _require_string(self.audio_channel_layout, "audio_channel_layout"),
535:                "audio_channel_layout": self.audio_channel_layout,
555:        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
569:            audio_channel_layout=data.get("audio_channel_layout"),
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
    }
)

PROVENANCE_V1_ALWAYS_KEYS = frozenset(
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
    }
)

_RETIRED_PROVENANCE_V2_KEYS = frozenset(
    {
        "resolved_backend",
        "source_pack",
        "alias_chain",
        "override",
        "trust_eligibility",
        "manifest_digest",
        "support_decision",
        "input_hashes",
    }
)

RESERVED_BACKEND_FRAGMENT_KEYS = frozenset(
    RENDER_RESULT_CORE_KEYS
    | PROVENANCE_V2_CORE_KEYS
    | PROVENANCE_V1_COMPATIBILITY_KEYS
    | _RETIRED_PROVENANCE_V2_KEYS
)


def _json_safe(value: Any) -> Any:
    """Return a recursively JSON-safe copy, rejecting non-wire values."""

    if isinstance(value, Enum):
        return _json_safe(value.value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("JSON numbers must be finite")
        return value
    if isinstance(value, Path):
        return str(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
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
            data,
            required={"start_frame", "end_frame", "fps_rational"},
            allowed={"start_frame", "end_frame", "fps_rational", "source_range", "speed"},
            label="frame window",
        )
        return cls(
            start_frame=data["start_frame"],
            end_frame=data["end_frame"],
            fps_rational=data["fps_rational"],
            source_range=data.get("source_range"),
            speed=data.get("speed"),
        )


@dataclass(frozen=True)
class RenderProfile:
    """Resolved media profile used to validate and finalize artifacts."""

    width: int
    height: int
    fps_rational: tuple[int, int]
    time_base: tuple[int, int]
    video_codec: str
    pixel_format: str
    video_profile: str | None = None
    video_level: str | None = None
    container: str = "mp4"
    audio_codec: str | None = None
    audio_sample_rate: int | None = None
    audio_channel_layout: str | None = None
    duration_tolerance: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _require_int(self.width, "width", minimum=1))
        object.__setattr__(self, "height", _require_int(self.height, "height", minimum=1))
        object.__setattr__(self, "fps_rational", _require_rational(self.fps_rational, "fps_rational"))
        object.__setattr__(self, "time_base", _require_rational(self.time_base, "time_base"))
        object.__setattr__(self, "video_codec", _require_string(self.video_codec, "video_codec"))
        object.__setattr__(self, "pixel_format", _require_string(self.pixel_format, "pixel_format"))
        object.__setattr__(
            self,
            "video_profile",
            _require_optional_string(self.video_profile, "video_profile"),
        )
        object.__setattr__(
            self,
            "video_level",
            _require_optional_string(self.video_level, "video_level"),
        )
        object.__setattr__(self, "container", _require_string(self.container, "container"))
        audio_values = (
            self.audio_codec,
            self.audio_sample_rate,
            self.audio_channel_layout,
        )
        if any(value is not None for value in audio_values) and not all(
            value is not None for value in audio_values
        ):
            raise ValueError(
                "audio_codec, audio_sample_rate, and audio_channel_layout must be "
                "provided together or all omitted"
            )
        if self.audio_codec is not None:
            object.__setattr__(self, "audio_codec", _require_string(self.audio_codec, "audio_codec"))
            object.__setattr__(
                self,
                "audio_sample_rate",
                _require_int(self.audio_sample_rate, "audio_sample_rate", minimum=1),
            )
            object.__setattr__(
                self,
                "audio_channel_layout",
                _require_string(self.audio_channel_layout, "audio_channel_layout"),
            )
        object.__setattr__(
            self,
            "duration_tolerance",
            _require_int(self.duration_tolerance, "duration_tolerance", minimum=0),
        )

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "width": self.width,
                "height": self.height,
                "fps_rational": self.fps_rational,
                "time_base": self.time_base,
                "container": self.container,
                "video_codec": self.video_codec,
                "video_profile": self.video_profile,
                "video_level": self.video_level,
                "pixel_format": self.pixel_format,
                "audio_codec": self.audio_codec,
                "audio_sample_rate": self.audio_sample_rate,
                "audio_channel_layout": self.audio_channel_layout,
                "duration_tolerance": self.duration_tolerance,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderProfile:
        data = _require_mapping(payload, "render profile")
        required = {
            "width",
            "height",
            "fps_rational",
            "time_base",
            "container",
            "video_codec",
            "video_profile",
            "video_level",
            "pixel_format",
            "duration_tolerance",
        }
        allowed = required | {"audio_codec", "audio_sample_rate", "audio_channel_layout"}
        _validate_object_keys(data, required=required, allowed=allowed, label="render profile")
        return cls(
            width=data["width"],
            height=data["height"],
            fps_rational=data["fps_rational"],
            time_base=data["time_base"],
            container=data["container"],
            video_codec=data["video_codec"],
            video_profile=data["video_profile"],
            video_level=data["video_level"],
            pixel_format=data["pixel_format"],
            audio_codec=data.get("audio_codec"),
            audio_sample_rate=data.get("audio_sample_rate"),
            audio_channel_layout=data.get("audio_channel_layout"),
            duration_tolerance=data["duration_tolerance"],
        )


def _validate_artifact_audio(
    profile: RenderProfile,
    ownership: AudioOwnership | None,
    label: str,
) -> None:
    """Keep probed media audio and ownership semantically aligned.

    ``rendered`` means the artifact itself contains audio and therefore has a
    populated audio profile. ``passthrough`` and ``none`` describe visual-only
    artifacts; the former asks the host/finalizer to supply canonical audio.
    """

    if profile.has_audio:
        if ownership is not AudioOwnership.RENDERED:
            raise ValueError(f"{label} with an audio profile must declare audio='rendered'")
    elif ownership is AudioOwnership.RENDERED:
        raise ValueError(f"{label} with audio='rendered' must have an audio profile")


@dataclass(frozen=True)
class Attachment:
    """A named, opaque artifact preserved alongside the primary video."""

    name: str
    path: str
    kind: str
    sha256: str

    def __post_init__(self) -> None:
        name = _require_string(self.name, "attachment name")
        if not _OUTPUT_NAME_RE.fullmatch(name):
            raise ValueError("attachment name must be a portable basename")
        kind = _require_string(self.kind, "attachment kind")
        if not _KIND_RE.fullmatch(kind):
            raise ValueError("attachment kind must be a lowercase hyphenated token")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "path", _require_workspace_relative_path(self.path, "attachment path"))

exec
/bin/zsh -lc "sed -n '215,255p' astrid/core/rendering/contracts.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:

def compute_request_digest(request: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 of a canonical, JSON-normalized render request.

    Uses sorted keys and compact separators so the digest is stable across
    Python versions and dict insertion orders; replay verifies the request
    against this digest.
    """
    return canonical_json_digest(_json_safe_mapping(request, label="render request"))


def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    if "\x00" in value:
        raise ValueError(f"{label} must not contain NUL")
    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
        raise ValueError(f"{label} must not be empty")
    return value


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

exec
/bin/zsh -lc "rg -n \"publish_render_result\\(|read_committed_provenance\\(|is_render_result_committed\\(\" astrid tests | head -240" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_publication.py:48:    result = publish_render_result(
tests/core/rendering/test_publication.py:62:    assert read_committed_provenance(output, sidecar_path=sidecar) == payload
tests/core/rendering/test_publication.py:63:    assert is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:99:            publish_render_result(
tests/core/rendering/test_publication.py:125:    payload = read_committed_provenance(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:136:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:137:    assert not is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:147:    assert read_committed_provenance(output, sidecar_path=sidecar) is None
tests/core/rendering/test_publication.py:148:    assert not is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:152:    publish_render_result(
tests/core/rendering/test_publication.py:160:    assert is_render_result_committed(output, sidecar_path=sidecar)
tests/core/rendering/test_publication.py:192:    publish_render_result(
tests/core/rendering/test_publication.py:216:    assert is_render_result_committed(live, sidecar_path=live_sidecar)
tests/core/rendering/test_publication.py:240:        publish_render_result(
tests/core/rendering/test_publication.py:268:        publish_render_result(
tests/core/rendering/test_publication.py:279:    assert not is_render_result_committed(output, sidecar_path=sidecar)
astrid/packs/rendering/executors/render/run.py:467:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:715:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1234:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:1416:            output = publish_render_result(
astrid/core/rendering/publication.py:160:def read_committed_provenance(
astrid/core/rendering/publication.py:213:def is_render_result_committed(
astrid/core/rendering/publication.py:220:    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
astrid/core/rendering/publication.py:293:            provenance = read_committed_provenance(video, sidecar_path=sidecar)
astrid/core/rendering/publication.py:310:def publish_render_result(
astrid/core/rendering/publication.py:376:        if read_committed_provenance(output, sidecar_path=sidecar) is None:

exec
/bin/zsh -lc "sed -n '420,490p' astrid/packs/rendering/executors/render/run.py
sed -n '675,730p' astrid/packs/rendering/executors/render/run.py
sed -n '1200,1250p' astrid/packs/rendering/executors/render/run.py
sed -n '1380,1430p' astrid/packs/rendering/executors/render/run.py
rg -n \"publication_out|def .*publish|out_path =|out_path:\" astrid/packs/rendering/executors/render/run.py | head -160" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

    publication_out = out_path  # unresolved: publication symlink-guards it
    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=f".{resolved_out.name}.publication-",
        dir=str(resolved_out.parent),
    ) as publication_tmp:
        staged_video = Path(publication_tmp) / resolved_out.name
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
        prefix=f".{resolved_out.name}.publication-",
        dir=str(resolved_out.parent),
    ) as publication_tmp:
        staged_video = Path(publication_tmp) / resolved_out.name
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
298:def _render_ffmpeg_media_to_path(timeline_path: Path, assets_path: Path, out_path: Path) -> Path:
440:    out_path: Path,
446:    publication_out = out_path  # unresolved: publication symlink-guards it
612:def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
652:def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
662:    publication_out = out_path  # unresolved: publication symlink-guards it
676:            segment_out_path = segment_dir / "segment.mp4"
837:def _render_asset_stage_hash(timeline_path: Path, assets_path: Path, out_path: Path) -> str:
963:def _render_provenance_sidecar_path(out_path: Path) -> Path:
968:    out_path: Path,
978:    out_path = out_path.resolve()
1014:    out_path: Path,
1075:    out_path: Path,
1158:    out_path: Path,
1187:    publication_out = out_path  # unresolved: publication symlink-guards it
1285:    out_path: Path,
1293:    out_path = Path(out_path)
1451:    out_path: Path,
1462:    out_path = Path(out_path)

exec
/bin/zsh -lc "sed -n '438,476p' astrid/packs/rendering/executors/render/run.py
sed -n '648,724p' astrid/packs/rendering/executors/render/run.py
sed -n '1175,1244p' astrid/packs/rendering/executors/render/run.py
sed -n '1275,1335p' astrid/packs/rendering/executors/render/run.py
sed -n '1440,1495p' astrid/packs/rendering/executors/render/run.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    _previous_outputs: Sequence[Path] | None = None,
) -> Path:
    """Render FFmpeg output privately, then publish the committed pair."""

    publication_out = out_path  # unresolved: publication symlink-guards it
    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(
        prefix=f".{resolved_out.name}.publication-",
        dir=str(resolved_out.parent),
    ) as publication_tmp:
        staged_video = Path(publication_tmp) / resolved_out.name
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

    publication_out = out_path  # unresolved: publication symlink-guards it
    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
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

    publication_out = out_path  # unresolved: publication symlink-guards it
    resolved_out = out_path.resolve()
    resolved_out.parent.mkdir(parents=True, exist_ok=True)
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
        prefix=f".{resolved_out.name}.publication-",
        dir=str(resolved_out.parent),
    ) as publication_tmp:
        staged_video = Path(publication_tmp) / resolved_out.name
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

    out_path = Path(out_path)
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

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from pathlib import Path; from astrid.core.rendering.publication import _contains_symlink_component; paths=(\"/tmp/review.mp4\",\"/var/tmp/review.mp4\",\"/etc/review\",\"/private/tmp/review.mp4\"); [print(p,\"guard=\",_contains_symlink_component(Path(p)),\"resolved=\",Path(p).resolve(strict=False)) for p in paths]'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 122ms:
/tmp/review.mp4 guard= False resolved= /private/tmp/review.mp4
/var/tmp/review.mp4 guard= False resolved= /private/var/tmp/review.mp4
/etc/review guard= False resolved= /private/etc/review
/private/tmp/review.mp4 guard= False resolved= /private/tmp/review.mp4

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import copy,json,pathlib,runpy; m=runpy.run_path(\"tests/fixtures/renderer_packs/raw_command/backend.py\",run_name=\"review\"); base=json.loads(pathlib.Path(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\").read_text()); out=[]; m[\"_support\"].__globals__[\"_write_json\"]=lambda p,x:out.append(x); cases=[]; r=copy.deepcopy(base); r[\"audio\"]=\"none\"; r[\"profile\"]=None; cases.append((\"none/null-profile\",r)); r=copy.deepcopy(base); r[\"audio\"]=None; r[\"profile\"][\"audio_codec\"]=None; r[\"profile\"][\"audio_sample_rate\"]=None; r[\"profile\"][\"audio_channel_layout\"]=None; cases.append((\"default/visual-profile\",r)); [(out.clear(),m[\"_support\"](req,pathlib.Path(\"unused\")),print(name,out[-1][\"supported\"],out[-1][\"reasons\"])) for name,req in cases]'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
none/null-profile True []
default/visual-profile True []

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import copy,json,pathlib; from astrid.core.rendering.contracts import RenderRequest; base=json.loads(pathlib.Path(\"tests/fixtures/renderer_packs/raw_command/requests/support.json\").read_text()); r1=copy.deepcopy(base); r1[\"audio\"]=\"none\"; r1[\"profile\"]=None; r2=copy.deepcopy(base); r2[\"audio\"]=None; [r2[\"profile\"].__setitem__(k,None) for k in (\"audio_codec\",\"audio_sample_rate\",\"audio_channel_layout\")]; print(RenderRequest.from_dict(r1).audio,RenderRequest.from_dict(r1).profile); print(RenderRequest.from_dict(r2).audio,RenderRequest.from_dict(r2).profile.has_audio)'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 85ms:
AudioOwnership.NONE None
None False

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'from astrid.core.rendering.artifacts import _compare_declared_to_expected,_validate_audio; from astrid.core.rendering.contracts import RenderProfile,AudioOwnership; from astrid.core.media import MediaProbe; base=dict(width=1,height=1,fps_rational=(1,1),time_base=(1,1),video_codec=\"h264\",pixel_format=\"yuv420p\",container=\"mp4\",audio_codec=\"aac\",audio_sample_rate=48000,duration_tolerance=1); declared=RenderProfile(**base,audio_channel_layout=\" Stereo \"); expected=RenderProfile(**base,audio_channel_layout=\"stereo\"); _compare_declared_to_expected(declared,expected,AudioOwnership.RENDERED); print(\"declared-normalization=accepted\"); probe=MediaProbe(width=1,height=1,fps_rational=(1,1),time_base=(1,1),video_codec=\"h264\",pixel_format=\"yuv420p\",container=\"mp4\",audio_codec=\"aac\",audio_sample_rate=48000,audio_channel_layout=None,video_stream_present=True,audio_stream_present=True,audio_channels=2); _validate_audio(probe,ownership=AudioOwnership.RENDERED,declared=declared,expected=expected); print(\"channels-fallback=accepted\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 98ms:
declared-normalization=accepted
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
This review also touches Astrid’s own rendering/publication contracts, so I’m applying the repository’s `astrid` skill now to make sure the verdict follows its project-specific invariants.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
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

exec
/bin/zsh -lc "sed -n '261,520p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '521,772p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc "rg --files astrid/packs/rendering | rg '("'^|/)(SKILL'"\\.md|AGENTS\\.md)"'$'"'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/skill/SKILL.md

codex
Astrid’s core guidance routes rendering-specific work to the rendering pack skill, so I’m consulting that pack contract before finalizing the findings.
exec
/bin/zsh -lc "wc -l astrid/packs/rendering/skill/SKILL.md && sed -n '1,260p' astrid/packs/rendering/skill/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     209 astrid/packs/rendering/skill/SKILL.md
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
/bin/zsh -lc "nl -ba tests/fixtures/renderer_packs/raw_command/backend.py | sed -n '438,500p'
nl -ba astrid/core/rendering/artifacts.py | sed -n '440,495p'
nl -ba astrid/core/rendering/transport.py | sed -n '472,535p'
nl -ba astrid/core/media.py | sed -n '24,65p'
nl -ba astrid/core/rendering/publication.py | sed -n '88,205p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
   438	        start = window.get("start_frame", 0)
   439	        if not isinstance(end, int) or not isinstance(start, int) or end <= start:
   440	            raise ValueError("window must satisfy 0 <= start_frame < end_frame")
   441	
   442	
   443	def _support(request: dict, result_path: Path) -> int:
   444	    mismatches: list[str] = []
   445	    # The renderer ALWAYS produces rendered PCM stereo audio; a request for
   446	    # no audio or passthrough contradicts the fixed output.
   447	    requested_audio = request.get("audio")
   448	    if requested_audio not in (None, "rendered"):
   449	        mismatches.append(f"audio={requested_audio!r} (fixed 'rendered')")
   450	    profile = request.get("profile")
   451	    if isinstance(profile, dict):
   452	        # The renderer emits a fixed profile; ANY deviation is unsupported
   453	        # (fail closed on every field, not just codecs/dimensions).
   454	        expected = {
   455	            "width": WIDTH,
   456	            "height": HEIGHT,
   457	            "fps_rational": list(FPS_RATIONAL),
   458	            "time_base": list(TIME_BASE),
   459	            "container": CONTAINER,
   460	            "video_codec": VIDEO_CODEC,
   461	            "video_profile": None,
   462	            "video_level": None,
   463	            "pixel_format": PIXEL_FORMAT,
   464	            "audio_codec": AUDIO_CODEC,
   465	            "audio_sample_rate": AUDIO_SAMPLE_RATE,
   466	            "audio_channel_layout": AUDIO_CHANNEL_LAYOUT,
   467	        }
   468	        for field, fixed in expected.items():
   469	            requested = profile.get(field)
   470	            if requested is not None and requested != fixed:
   471	                mismatches.append(f"{field}={requested!r} (fixed {fixed!r})")
   472	        if mismatches:
   473	            _write_json(
   474	                result_path,
   475	                {
   476	                    "schema_version": 1,
   477	                    "supported": False,
   478	                    "reasons": [
   479	                        "profile not produced by " + BACKEND_ID + ": "
   480	                        + "; ".join(mismatches)
   481	                    ],
   482	                    "features": {"media": False, "audio_mode": "none"},
   483	                    "alternatives": [],
   484	                    "backend": BACKEND_ID,
   485	                    "backend_version": "1.0.0",
   486	                },
   487	            )
   488	            return 0
   489	    _write_json(
   490	        result_path,
   491	        {
   492	            "schema_version": 1,
   493	            "supported": True,
   494	            "reasons": [],
   495	            "features": {"media": True, "audio_mode": "rendered"},
   496	            "alternatives": [],
   497	            "backend": BACKEND_ID,
   498	            "backend_version": BACKEND_VERSION,
   499	        },
   500	    )
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
   483	    }.get((layout or "").lower())
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
   501	            except (subprocess.TimeoutExpired, OSError):
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
   517	        # Deadline exit still owes a reap of the direct child.
   518	        if process.returncode is None:
   519	            try:
   520	                process.wait(timeout=max(grace, 1.0))
   521	            except (subprocess.TimeoutExpired, OSError):
   522	                try:
   523	                    process.kill()
   524	                except OSError:
   525	                    pass
   526	                process.wait()
   527	            captured = captured or ("", "")
   528	    elif captured is None:
   529	        # ``poll`` may have reaped the child while checking the fallback path.
   530	        # Its pipes still need to be drained; bound the drain so cleanup can
   531	        # never block forever on a stuck pipe.
   532	        try:
   533	            captured = process.communicate(timeout=max(grace, 2.0))
   534	        except (subprocess.TimeoutExpired, KeyboardInterrupt, OSError):
   535	            try:
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
    88	    return Path(path).expanduser().resolve(strict=False)
    89	
    90	
    91	def _contains_symlink_component(path: str | Path) -> bool:
    92	    """True if a non-system path component is a symbolic link.
    93	
    94	    Only the macOS system redirects (``/tmp`` -> ``/private/tmp``,
    95	    ``/var`` -> ``/private/var``, ``/etc`` -> ``/private/etc``) are exempt.
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
   112	        # macOS system redirect: /<name> -> /private/<name> at the ROOT only.
   113	        if (
   114	            len(parts[:index]) == 2
   115	            and parts[0] == "/"
   116	            and candidate.name in ("tmp", "var", "etc")
   117	            and str(resolved) == f"/private/{candidate.name}"
   118	        ):
   119	            continue
   120	        return True
   121	    return False
   122	
   123	
   124	def _invalid_video(video_path: Path, *, reason: str, message: str) -> None:
   125	    raise_invalid_artifact_error(
   126	        backend=_BACKEND,
   127	        message=message,
   128	        recovery_command=_RECOVERY,
   129	        details={"reason": reason, "path": str(video_path)},
   130	    )
   131	
   132	
   133	def _validate_source_video(video_path: Path) -> None:
   134	    try:
   135	        exists = video_path.is_file()
   136	    except OSError:
   137	        exists = False
   138	    if not exists:
   139	        _invalid_video(
   140	            video_path,
   141	            reason="missing_artifact",
   142	            message=f"rendered video does not exist: {video_path}",
   143	        )
   144	    try:
   145	        size = video_path.stat().st_size
   146	    except OSError:
   147	        _invalid_video(
   148	            video_path,
   149	            reason="missing_artifact",
   150	            message=f"rendered video cannot be read: {video_path}",
   151	        )
   152	    if size <= 0:
   153	        _invalid_video(
   154	            video_path,
   155	            reason="empty_artifact",
   156	            message=f"rendered video is empty: {video_path}",
   157	        )
   158	
   159	
   160	def read_committed_provenance(
   161	    video_path: str | Path,
   162	    *,
   163	    sidecar_path: str | Path | None = None,
   164	) -> dict[str, Any] | None:
   165	    """Return provenance only when *video_path* and its marker form a valid pair.
   166	
   167	    This check intentionally fails closed for missing, malformed, empty, or
   168	    hash-mismatched pairs.  Callers can then re-render or leave the orphan for
   169	    conservative recovery without mistaking it for a successful publication.
   170	    """
   171	
   172	    try:
   173	        video_unresolved = Path(video_path).expanduser()
   174	        sidecar_unresolved = Path(sidecar_path or _default_sidecar_path(video_unresolved)).expanduser()
   175	        if (
   176	            _contains_symlink_component(video_unresolved)
   177	            or _contains_symlink_component(sidecar_unresolved)
   178	        ):
   179	            return None
   180	        # Resolve only AFTER the symlink guard so a symlink loop cannot
   181	        # raise RuntimeError here — it must fail closed to None.
   182	        video = _resolved(video_path)
   183	        sidecar = _resolved(sidecar_path or _default_sidecar_path(video))
   184	        if video.is_symlink() or sidecar.is_symlink():
   185	            return None
   186	        if not video.is_file() or video.stat().st_size <= 0 or not sidecar.is_file():
   187	            return None
   188	        payload = json.loads(sidecar.read_text(encoding="utf-8"))
   189	    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
   190	        return None
   191	    if not isinstance(payload, dict):
   192	        return None
   193	    recorded_output = payload.get("output")
   194	    if not isinstance(recorded_output, str):
   195	        return None
   196	    try:
   197	        recorded_output_path = _resolved(recorded_output)
   198	    except (OSError, RuntimeError, ValueError):
   199	        return None
   200	    if recorded_output_path != video:
   201	        return None
   202	    recorded_sha256 = payload.get("sha256")
   203	    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
   204	        return None
   205	    try:

codex
- `_support()` discards audio mismatches when `profile` is `null`; a valid request with `audio="none", profile=null` still returns `supported: true`. [backend.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:451)

- `_layout_channel_count()` lowercases but does not strip whitespace like normal profile normalization. A valid `" Stereo "` layout matches `"stereo"` normally but fails the channels-only fallback. [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:475)
tokens used
124,964
- `_support()` discards audio mismatches when `profile` is `null`; a valid request with `audio="none", profile=null` still returns `supported: true`. [backend.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/fixtures/renderer_packs/raw_command/backend.py:451)

- `_layout_channel_count()` lowercases but does not strip whitespace like normal profile normalization. A valid `" Stereo "` layout matches `"stereo"` normally but fails the channels-only fallback. [artifacts.py](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/artifacts.py:475)
