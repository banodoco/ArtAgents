Reading additional input from stdin...
2026-08-12T14:29:18.092351Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:18.093453Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:18.093463Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ff660-a736-7951-a3c4-45f054fe6cc7
--------
user
# Megado Checkpoint — Batch 4

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
Previous head C4-batch3-done (9bf9db88). Batch 4 committed as `a72729db`.
Incremental diff: `git diff C4-batch3-done..a72729db`.

## What Batch 4 was supposed to deliver (tasklist)

1. `RenderService` (core, `astrid/core/rendering/service.py`) with the FROZEN
   selection order: legacy translation → alias → override → winner →
   eligibility → support → invoke/validate → audio/finalize → publish.
   - `ffmpeg` → strict `rendering.ffmpeg`; `remotion` → characterized legacy
     policy (FFmpeg for eligible media/audio-specialized timelines else
     remotion, with auto-routing warning); `hybrid` → `rendering.legacy_hybrid`
     planner (NEVER a renderer id); qualified ids strict.
   - One video + one committed sidecar per success; failures clean temps.
2. Neutral facade (`astrid/packs/rendering/executors/render/run.py` delegates
   to `_default_service().render(...)`; `executor.yaml` neutral selector +
   namespaced config + `output_name` input with validation;
   `_normalize_render_command_compat` removed).
3. Additive provenance v2: routing lineage (requested engine → resolved
   backend + auto-route reason), all v1 projections preserved, core/backend
   fragment ownership, lock-aware cleanup, one sidecar per success.
4. `rendering.legacy_hybrid` planner port
   (`astrid/packs/rendering/planners/legacy_hybrid/`, planner.yaml + run.py):
   integer half-open `[start_frame,end_frame)` windows, transition/handle
   preservation, support-based assignment, explicit finalizer
   (`rendering.ffmpeg-finalizer`), non-recursive dispatch, aligned segment
   provenance.
5. Routing/hybrid matrix: strict/legacy selectors, alias/override/trust,
   output-name rejection + hype.mp4 sentinel, every built-in path (remotion,
   ffmpeg, optimized ffmpeg, audio-reactive, hybrid single + multi) → exactly
   one video + one sidecar, raw mixed-plan (deterministic fixture executes),
   audio control matrix, failure cleanup, attachments, crash recovery.

## Evidence

- `pytest -q tests/core/rendering/`: 367 passed.
- Full consolidated acceptance: 977 passed, 2 skipped, 1 failed
  (pre-existing env-dependent model-trends fixture test, documented in
  `.oracle/baseline.md`, unchanged).
- `tests/packs/rendering/test_builtin_registration.py` now asserts
  `rendering.legacy_hybrid` in the static planner registry (no backend import
  during inspection).
- Facade tests assert delegation to the service seam (`selector` passthrough),
  not backend internals.

## Verdict

Binary `PASS` or issues. On PASS, Batch 5 (caller migration + semantic
parity + M1 freeze) begins. Say exactly `PASS` if clean.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the `megado` checkpoint workflow and delegating independent diff review per the repository instructions. I’ll return exactly `PASS` only if the incremental change is clean.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
---
name: megado
description: "Megado: multi-model plan-explore-execute delivery pipeline. Codex (GPT-5.6 Sol, high reasoning) plans the whole project, DeepSeek V4 Flash subagents explore the areas it flags, Codex revises until stable, then the plan becomes a batched tasklist with formal check-ins where a GPT-5.6 Sol oracle reviews completed work until happy. DeepSeek V4 Flash executes normal tasks, GPT-5.6 Sol takes the extremely hard ones. Use when the user says 'get it megado' or wants a project planned exhaustively, explored in depth, executed end to end at high quality, and opened+synced when done."
---

# Megado

A delivery pipeline for a whole project: **Codex plans, DeepSeek explores, Codex revises, DeepSeek executes, Codex oracles** — all in a worktree, opened and synced when done. Two models only: **DeepSeek V4 Flash** and **GPT-5.6 Sol**.

The shape (from the original ask, normalized):

1. In a worktree, Codex (GPT-5.6 Sol, high reasoning) turns the project into a tasklist covering the **entirety** of it, and proposes **additional areas to explore** for full clarity.
2. A DeepSeek V4 Flash subagent explores **each** of those areas in depth (parallel fan-out).
3. Findings go back to Codex / the original plan: update it based on them, **bias toward elegance and simplicity**, surface any other elements to explore (potential issues, etc.). Repeat while there are material changes.
4. Once stable, Codex converts the plan into a **batched task list**: sensible batches with surveyor/check-in points, extremely hard tasks marked explicitly. It designs the check-in structure — send completed work since the last check-in for feedback, flag implementation issues; at formal check-ins, go back to what was just implemented until it's happy. GPT-5.6 Sol at high reasoning produces this structure.
5. Run through the list: **DeepSeek V4 Flash executes all tasks** except the extremely hard ones, which **GPT-5.6 Sol executes**. GPT-5.6 Sol acts as the **oracle** at the checkpoints until the whole thing is executed end to end and quality is confirmed.
6. Open it and sync.

## Roles

| Role | Model | Invocation | Tools |
| --- | --- | --- | --- |
| **Planner / Oracle** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | read-only for planning/review; `workspace-write` when it implements |
| **Explorer** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web` |
| **Executor** | DeepSeek V4 Flash | `launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"` | `file,web,terminal` |
| **Hard-task executor** | GPT-5.6 Sol | `codex exec -c model=gpt-5.6-sol -c model_reasoning_effort=high` | `workspace-write` |

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

Brief GPT-5.6 Sol at high reasoning. Demand three outputs, in order:

1. A tasklist covering the **entirety** of the project (not just the obvious path).
2. **Additional areas to explore** to get full clarity — unknowns, subsystems, risks, adjacent code that touches the plan.
3. Open questions / potential issues.

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
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

Feed `.oracle/plan.md` + all `.oracle/findings/*.txt` to Codex (GPT-5.6 Sol, high reasoning):

> Update the plan given these findings. Bias toward **elegance and simplicity** — cut scope that isn't pulling its weight. List any new areas to explore and potential issues. If nothing material changed, answer exactly `STABLE`.

- New material areas → re-run Phase 2 for those, then revise again.
- Repeat until Codex returns `STABLE` (or two consecutive rounds with no material change).
- The plan is a living doc during this loop; it freezes at Phase 4.

## Phase 4 — Batched tasklist with checkpoints (Codex)

Ask Codex (GPT-5.6 Sol, high reasoning) to convert the stable plan into an execution structure:

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
timeout 1800 codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high \
  "$(cat /tmp/hard-task-brief.md)" </dev/null
```

(Use `--sandbox danger-full-access` only when the Codex agent must itself orchestrate hermes subagents — those need outbound network.)

**2. Checkpoint — oracle review.** Send the batch's completed work to GPT-5.6 Sol (high reasoning):

```bash
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high \
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

# Phase 1 — initial plan (GPT-5.6 Sol, high reasoning)
timeout 1800 codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/plan-brief.md)" </dev/null

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
# [HARD] tasks: codex exec --sandbox workspace-write -c model=gpt-5.6-sol -c model_reasoning_effort=high
# checkpoint: codex exec --sandbox read-only -c model=gpt-5.6-sol -c model_reasoning_effort=high "$(cat /tmp/checkin-brief.md)" </dev/null

# Phase 6 — commit, push, open
git add -A && git commit -m "megado: <project>" && git push && open .
```

2026-08-12T14:29:32.225330Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:32.225790Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:32.225806Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:35.958529Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:35.958567Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:35.958575Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:39.957857Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:39.957901Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T14:29:39.957908Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git log --oneline --decorate -6 && git diff --stat C4-batch3-done..a72729db && git diff --name-status C4-batch3-done..a72729db && sed -n '1,260p' .oracle/tasklist.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-4.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
a72729db (HEAD -> oracle-run) batch4: generic RenderService, neutral facade, provenance v2 routing, legacy_hybrid planner, routing/hybrid matrix
9bf9db88 (tag: C4-batch3-done) batch3-rework4: oracle re-review3 issue 1 (ffmpeg support rejects unguaranteed pinned video_profile/level)
a7b7b080 batch3-rework3: oracle re-review2 issues 1-4 (remotion --enforce-audio-track, canonical MP4 time-base rule + rational-aware ffmpeg support, stream-copy time-base gate, frame-accurate whole-source tolerance)
58473c3a batch3-rework2: oracle re-review issues 1-6 (env-authoritative launcher routing, remotion full render-profile support + manifest audio, ffmpeg time_base support check, audio-reactive 48kHz, whole-source stream-copy gate incl codec/pixel + supported required, TOCTOU-free legacy facade via preloaded-data builder)
72b70944 batch3-rework: oracle issues 1-8 (launcher backend-id routing, remotion support/render contract alignment + ffprobe binary, ffmpeg full-profile support + canonical 48kHz, probe-gated stream-copy, legacy path strict support, finalizer audio-presence + codec-anchor tests, lock test timeouts)
0c2733ed (tag: C3) batch3: Remotion/FFmpeg backend extraction + outer lock, strict FFmpeg support + audio semantics, ffmpeg-finalizer extraction, built-in registration + real render smoke + typecheck
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/briefs/batch-4-t4.1.md                     |   61 +
 .oracle/briefs/batch-4-t4.2.md                     |   50 +
 .oracle/briefs/batch-4-t4.3.md                     |   52 +
 .oracle/briefs/batch-4-t4.4.md                     |   65 +
 .oracle/briefs/batch-4-t4.5.md                     |   46 +
 .oracle/checkins/batch-3-r4.md                     | 4957 ++++++++++++++++++++
 astrid/core/execution/executor/runner.py           |   25 -
 astrid/core/rendering/provenance.py                |   96 +-
 astrid/core/rendering/service.py                   | 1829 ++++++++
 .../packs/rendering/executors/render/executor.yaml |   52 +-
 astrid/packs/rendering/executors/render/run.py     |  362 +-
 astrid/packs/rendering/pack.yaml                   |    2 +
 .../rendering/planners/legacy_hybrid/__init__.py   |   24 +
 .../rendering/planners/legacy_hybrid/planner.yaml  |   25 +
 .../packs/rendering/planners/legacy_hybrid/run.py  |  891 ++++
 astrid/packs/rendering/run.py                      |   12 +-
 tests/core/rendering/test_legacy_hybrid.py         |  501 ++
 tests/core/rendering/test_output_name.py           |   68 +
 tests/core/rendering/test_provenance.py            |  604 +++
 tests/core/rendering/test_service.py               | 1840 ++++++++
 .../packs/rendering/test_audio_reactive_colour.py  |   24 +-
 tests/packs/rendering/test_builtin_registration.py |    2 +-
 tests/packs/rendering/test_ffmpeg_backend.py       |   53 +-
 .../test_legacy_renderer_characterization.py       |  171 +-
 tests/packs/rendering/test_remotion_backend.py     |   30 +-
 tests/packs/rendering/test_render_facade.py        |  199 +
 26 files changed, 11684 insertions(+), 357 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/briefs/batch-4-t4.1.md
A	.oracle/briefs/batch-4-t4.2.md
A	.oracle/briefs/batch-4-t4.3.md
A	.oracle/briefs/batch-4-t4.4.md
A	.oracle/briefs/batch-4-t4.5.md
A	.oracle/checkins/batch-3-r4.md
M	astrid/core/execution/executor/runner.py
M	astrid/core/rendering/provenance.py
A	astrid/core/rendering/service.py
M	astrid/packs/rendering/executors/render/executor.yaml
M	astrid/packs/rendering/executors/render/run.py
M	astrid/packs/rendering/pack.yaml
A	astrid/packs/rendering/planners/legacy_hybrid/__init__.py
A	astrid/packs/rendering/planners/legacy_hybrid/planner.yaml
A	astrid/packs/rendering/planners/legacy_hybrid/run.py
M	astrid/packs/rendering/run.py
A	tests/core/rendering/test_legacy_hybrid.py
A	tests/core/rendering/test_output_name.py
A	tests/core/rendering/test_provenance.py
A	tests/core/rendering/test_service.py
M	tests/packs/rendering/test_audio_reactive_colour.py
M	tests/packs/rendering/test_builtin_registration.py
M	tests/packs/rendering/test_ffmpeg_backend.py
M	tests/packs/rendering/test_legacy_renderer_characterization.py
M	tests/packs/rendering/test_remotion_backend.py
A	tests/packs/rendering/test_render_facade.py
# Renderer Tasklist

## Batch 1 — Baseline, contracts, and discovery

**Checkpoint:** The oracle reviews the characterized legacy behavior, all 18 frozen decisions, wire schemas, pack-extension loading, trust eligibility, precedence, aliases, overrides, and compatibility mappings. Batch 2 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `.oracle/baseline.md` records the dirty-tree snapshot, baseline failures/skips, production callsite inventory, empty Sprint 08 fixture state, all three legacy engines, nominal-Remotion FFmpeg routing, audio specialization, v1 provenance fields, transition units, and standalone versus attached run ownership.
- `docs/contracts/render-backend-v1.md` preserves locked decisions 1–18 from `.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md` and the resolved decisions in `.oracle/plan.md`.
- Python DTOs and versioned JSON fixtures round-trip identically; unknown versions, invalid half-open frame bounds, duplicate attachment names, traversal, and backend attempts to overwrite core fields fail structurally.
- `extensions.rendering` schema and runtime normalization agree exactly; manifests are containment-checked and statically inspectable without importing backend code.
- Renderer, planner, and finalizer registries use `DiscoveredPack.priority_index`; aliases resolve before overrides, ineligible candidates cannot shadow trusted implementations, and executor/orchestrator default registries receive `OverrideStore(project_root)`.
- Active trusted installs, corrupt/mismatched installs, inactive revisions, explicit-extra roots, environment denial, conflicts, cycles, and invalid override targets produce the specified inspectable/executable states.
- `ffmpeg`, `remotion`, qualified built-in IDs, and `hybrid` retain the frozen compatibility meaning; `hybrid` is never registered as a renderer.
- Existing rendering, pack, executor, iteration, Hype, and audio-reactive suites remain at the recorded baseline.

### Tasks

- [ ] **T1.1 — Characterize and record the baseline** Add `.oracle/baseline.md` and `tests/packs/rendering/test_legacy_renderer_characterization.py` covering legacy routing, props/theme/registry/staging/environment behavior, every v1 provenance key, transition units, run ownership, and the complete caller inventory; acceptance: `pytest -q tests/packs/rendering/test_legacy_renderer_characterization.py tests/packs/rendering tests/packs/test_audio_render.py`.
- [ ] **T1.2 — Freeze language-neutral contracts and schemas** Add `astrid/core/rendering/{__init__,contracts,errors,provenance}.py`, `astrid/core/rendering/schemas/v1/*.json`, raw JSON fixtures, and `docs/contracts/render-backend-v1.md` defining `RenderRequest`, `SupportReport`, `RenderPlan`, `FrameWindow`, profiles, audio ownership, artifacts, attachments, results, failures, and provenance v2; acceptance: `pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py`.  [HARD]
- [ ] **T1.3 — Add the exact rendering pack extension** Update `astrid/core/pack/schemas/v1/pack.json`, `permissions.py::_optional_pack_extensions`, `_common.py::{PACK_ALIAS_KINDS,PackAliasKind}`, `alias_resolver.py::extract_pack_aliases`, and `registry.py::pack_rendering_manifest_paths` for renderer/planner/finalizer manifests and aliases; acceptance: `pytest -q tests/packs/test_pack_yaml_schema.py tests/packs/test_pack_rendering_extensions.py tests/test_canonical_aliases.py`.  [HARD]
- [ ] **T1.4 — Build trusted rendering registries** Implement `astrid/core/rendering/registry.py::{RendererRegistry,PlannerRegistry,FinalizerRegistry,load_default_registries}` over `CapabilityRegistry`, `AliasResolver`, `OverrideStore`, `discover_pack_metadata()`, and derived execution eligibility; retrofit `execution/{executor,orchestrator}/registry.py::load_default_registry`; acceptance: `pytest -q tests/core/rendering/test_registry.py tests/test_override.py tests/packs/test_pack_discovery_metadata.py`.  [HARD]
- [ ] **T1.5 — Lock the discovery and eligibility matrix** Add static no-import, precedence, conflict, alias, override, cycle, permission, explicit-extra, active/inactive install, corrupt trust-record, and ineligible-shadowing cases under `tests/core/rendering/test_registry.py` and `tests/fixtures/renderer_packs/discovery/`; acceptance: that test module passes without executing fixture commands.

## Batch 2 — Command protocol and host-owned plumbing

**Checkpoint:** The oracle reviews the complete four-verb transport, raw non-SDK fixture, process cleanup, asset/cache behavior, canonical profile, artifact enforcement, and locked publication protocol. Batch 3 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- Commands execute as `<command> render|support|plan|finalize --request <absolute> --result <absolute>` with `shell=False`, pack-root `cwd`, sanitized environment, absolute paths, binary preflight, timeout, captured logs, and authoritative result-file parsing.
- Missing binaries, nonzero exits, timeout, interruption, absent/malformed results, absent/empty outputs, and incompatible protocol versions map to renderer-qualified structured failures; process groups are terminated and reaped on interruption.
- The raw fixture imports no Astrid SDK, produces a deterministic two-second artifact from generated media, works from an explicit extra root and trusted active install, and never creates `run.json`.
- Asset-cache layout, URL keys, resume/drift metadata, locking, and `EphemeralSession` behavior remain unchanged behind the compatibility wrapper.
- Only invocation-staged assets are served from `127.0.0.1` on port `0`; Range requests work and the server always shuts down, closes, and joins.
- The canonical resolved profile comes from the merged theme/timeline canvas and includes dimensions, rational FPS/time base, codecs, pixel format, audio rate/layout, and duration tolerance.
- Artifact validation rejects missing, empty, escaped, symlinked, hash-mismatched, profile-incompatible, duration-invalid, and audio-ownership-invalid outputs while preserving valid named attachments.
- Publication locks each output, renames the video first, and atomically writes its hashed provenance sidecar last; crash-orphan recovery never treats an incomplete pair as committed.

### Tasks

- [ ] **T2.1 — Implement command transport and process lifecycle** Add `astrid/core/rendering/transport.py::CommandTransport` with four protocol verbs, binary preflight, sanitized subprocess execution, timeouts, process sessions, process-group cleanup, result parsing, and structured failure mapping; acceptance: `pytest -q tests/core/rendering/test_transport.py`.  [HARD]
- [ ] **T2.2 — Add the raw protocol fixture pack** Create `tests/fixtures/renderer_packs/raw_command/{pack.yaml,renderer.yaml,backend.py}` plus versioned text-only and generated-media requests, without committed MP4s or SDK imports; acceptance: `pytest -q tests/core/rendering/test_raw_command_fixture.py tests/packs/test_git_pack_install.py`.
- [ ] **T2.3 — Extract the reusable asset cache** Move reusable code to `astrid/core/rendering/asset_cache.py` while retaining `astrid/packs/training/executors/asset_cache/run.py` as a compatible CLI wrapper; acceptance: `pytest -q tests/test_asset_cache.py tests/test_url_pipeline_smoke.py`.
- [ ] **T2.4 — Implement invocation-scoped asset materialization** Add `astrid/core/rendering/assets.py::{AssetMaterializer,InvocationAssetServer}` and replace `_classify_assets`, `_server_root_for`, and broad-root serving with contained hardlink/copy staging, remote-URL preservation, Range support, and deterministic cleanup; acceptance: `pytest -q tests/core/rendering/test_assets.py`.  [HARD]
- [ ] **T2.5 — Resolve profiles and validate artifacts** Add `astrid/core/rendering/{profile,artifacts}.py::{resolve_render_profile,validate_render_result}`, extend `astrid/core/media.py` probing fields, and cover audio ownership, attachments, hashes, duration, containment, and profile checks; acceptance: `pytest -q tests/core/rendering/test_profile.py tests/core/rendering/test_artifacts.py tests/core/util/test_media.py`.  [HARD]
- [ ] **T2.6 — Add locked video-plus-sidecar publication** Implement `astrid/core/rendering/publication.py::publish_render_result` with per-output locking, atomic sidecar commit marking, conservative previous-output handling, and orphan recovery; acceptance: `pytest -q tests/core/rendering/test_publication.py`.  [HARD]

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

## Batch 4 — Generic routing, provenance, and hybrid planning

**Checkpoint:** The oracle reviews the generic `RenderService`, facade/output behavior, additive provenance v2, and half-open-frame hybrid planner/dispatcher. The review explicitly searches generic code for concrete backend branches. Batch 5 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- `RenderService` performs legacy translation → alias → override → winner → eligibility → support → invoke/validate → audio/finalize → publish in that order.
- Qualified `rendering.remotion` and `rendering.ffmpeg` are strict; legacy `remotion` retains characterized policy, legacy `ffmpeg` is strict, and `hybrid` selects `rendering.legacy_hybrid`.
- `output_name` uses existing input placeholders and cache/CAS identity, rejects separators/traversal/non-MP4 extensions, preserves declared output names, and leaves Hype’s default `hype.mp4` sentinel unchanged.
- Every Remotion, FFmpeg, optimized FFmpeg, audio-reactive, hybrid, and single-segment path produces exactly one video and one committed sidecar.
- Provenance v2 records routing, aliases, overrides, trust, manifests, requests, support, alternatives, inputs, artifacts, profiles, audio, normalization, attachments, segments, and backend fragments while preserving every listed v1 top-level projection.
- Hybrid plans use integer `[start_frame,end_frame)` windows from the canonical profile, preserve characterized transition units/handles, use support reports for assignments, and never recursively call `render()`.
- Empty, single, multiple, all-FFmpeg, and mixed raw-fixture/built-in plans pass; failures clean temporary artifacts and maintain aligned segment provenance.

### Tasks

- [ ] **T4.1 — Implement the generic `RenderService`** Add `astrid/core/rendering/service.py::RenderService` with the frozen selection order, eligibility/support checks, invocation, artifact enforcement, audio completion, finalization, and publication; acceptance: `pytest -q tests/core/rendering/test_service.py`.  [HARD]
- [ ] **T4.2 — Make the facade neutral and output-name aware** Reduce `astrid/packs/rendering/executors/render/run.py` to a facade adapter, update `executor.yaml` with neutral selector/config/`output_name` inputs and placeholder outputs, make parsing order-independent, and remove `executor/runner.py::_normalize_render_command_compat` after its characterization passes; acceptance: `pytest -q tests/packs/rendering/test_render_facade.py tests/core/rendering/test_output_name.py`.
- [ ] **T4.3 — Emit additive provenance v2** Implement core-owned provenance assembly and namespaced backend fragments in `astrid/core/rendering/provenance.py`, retaining all v1 projections and lock-aware conservative cleanup; acceptance: `pytest -q tests/core/rendering/test_provenance.py`.  [HARD]
- [ ] **T4.4 — Port `rendering.legacy_hybrid`** Add `astrid/packs/rendering/planners/legacy_hybrid/{planner.yaml,run.py}` implementing canonical-profile frame windows, transition/handle behavior, support-based assignment, explicit renderer IDs/finalizer, non-recursive dispatch, and normalized segment provenance; acceptance: `pytest -q tests/core/rendering/test_legacy_hybrid.py`.  [HARD]
- [ ] **T4.5 — Lock the routing and hybrid matrix** Add strict/legacy selector, alias/override, trust denial, unsupported-alternative, output-name, every built-in path, raw mixed-plan, audio-control, failure-cleanup, attachment, sidecar, and crash-recovery cases; acceptance: `pytest -q tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_provenance.py`.

## Batch 5 — Caller migration, semantic parity, and M1 freeze

**Checkpoint:** The oracle reviews the attached-child helper, every production caller, override propagation, one-ledger guarantees, semantic parity fixtures, CI/package data, and the complete M1 verification matrix. M2 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- The attached-child helper requires a validated parent project/run and unique step, scopes and restores all three `ASTRID_TASK_*` variables, preserves caller-selected output, honors facade overrides, and falls back to public `RenderService` only without a project ledger.
- Iteration produces `iteration.mp4` and `iteration.mp4.provenance.json` directly; Hype retains `hype.mp4`; cut/resume preserve deprecated `--renderer`; every migrated path creates only its intended ledger.
- Executor overrides affect attached facade calls; renderer/planner/finalizer overrides affect facade and public-service calls; removal of the executor runtime cache prevents stale in-process resolution.
- Repository searches find no production concrete-renderer import or `-m ...render.run` spawn outside manifests, backend implementations, and explicitly allowlisted tests/debug tools.
- Semantic parity covers Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, audio controls, invalid artifacts, failures, standalone/attached ownership, and default/non-default output names.
- The normal parity suite fails on empty fixtures, has no environment self-skip, generates tiny media instead of committing MP4s, runs a real FFmpeg render, and treats Remotion typecheck as blocking.
- Contract, pack-author, skill, stage, bridge, compatibility, and audio-semantics documentation is complete; schemas, manifests, fixtures, and scaffold resources are present in installed wheels.
- Targeted suites, full non-opt-in pytest, semantic parity, real FFmpeg, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

### Tasks

- [ ] **T5.1 — Add attached-child render invocation** Implement `astrid/core/rendering/attached.py::invoke_attached_render` over existing task/executor primitives with validated ownership, unique step IDs, scoped environment restoration, retained outputs, overridden `rendering.render`, and public-service fallback only when unbound; acceptance: `pytest -q tests/core/rendering/test_attached_render.py tests/test_task_env_contract.py`.  [HARD]
- [ ] **T5.2 — Migrate iteration and cut callers** Update `iteration_video/{run.py,plan_template.py}` and `cut/{run.py,resume.py}` to use attached facade/public service as specified, declare the iteration sidecar, remove rename-only behavior and broken imports, and preserve the deprecated selector; acceptance: `pytest -q tests/packs/iteration/test_iteration_video.py tests/packs/video_editing/test_cut_render_migration.py`.  [HARD]
- [ ] **T5.3 — Migrate Hype, human-notes, and canonical callers** Update `hype/{steps.py,plan_template.py}` and `editorial/executors/human_notes/run.py`, preserve `tools/render_and_check.py`, and add override/single-ledger coverage; acceptance: `pytest -q tests/packs/hype tests/packs/editorial/test_human_notes_render.py tests/core/rendering/test_caller_overrides.py`.  [HARD]
- [ ] **T5.4 — Finish facade manifest and stale-resolution cleanup** Finalize `render/executor.yaml`, remove `@lru_cache` from `execution/executor/argv.py::resolve_executor_runtime_module`, and add a repository source-topology allowlist test; acceptance: `pytest -q tests/core/rendering/test_production_callers.py tests/core/test_executor_registry_snapshot.py`.
- [ ] **T5.5 — Replace the empty renderer parity gate** Populate repository-owned semantic timeline/assets/theme fixtures, rewrite `tests/packs/test_renderer_parity.py`, reuse generated black/silence media and existing Hype/audio-reactive goldens, and wire real FFmpeg plus Remotion typecheck into blocking CI; acceptance: `pytest -q -m renderer_parity tests/packs/test_renderer_parity.py`.  [HARD]
- [ ] **T5.6 — Complete the M1 contract and compatibility documentation** Finish `render-backend-v1.md` and update `docs/packs/{creating-packs,aliases-vs-forks-vs-overrides}.md`, rendering `SKILL.md`/`STAGE.md`, `_core/skill/SKILL.md`, `docs/reference/render-adapter.md`, `docs/guides/creating-tools.md`, and the asset-resolution bridge; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
- [ ] **T5.7 — Package and run the M1 gate** Update `pyproject.toml`, wheel smoke, CI lanes, and package-data tests for schemas/manifests/fixtures; run and record the full M1 matrix for the checkpoint; acceptance: `pytest -q`, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.

## Batch 6 — Python SDK, conformance, and scaffold

**Checkpoint:** The oracle first enforces the M1 handoff, then reviews wire-equivalent SDK serialization, `RenderContext`, shared conformance fixtures, public import behavior, and the exact four-file scaffold from source and an installed wheel. Batch 7 cannot begin until the oracle returns `PASS`.

**Acceptance criteria:**

- The frozen protocol, schemas, raw fixture, trusted discovery, built-ins, service, and conformance suite work from source and an installed wheel before SDK work proceeds.
- Any SDK/wire mismatch stops the batch and returns to M1 through the oracle; no SDK-only fields or semantics are introduced.
- `astrid/sdk/rendering.py` wraps canonical DTOs, preserves `_json_safe`, keeps heavy imports function-local, and maintains exact lazy public-export ordering and collision checks.
- `RenderContext` supplies allocated paths, descriptor path/URL access, permission checks, sanitized subprocesses, redacted logs/progress, interruption state, probing, hashing, audio completion, attachments, and cleanup while documenting that it is not an OS sandbox.
- Raw and SDK fixtures produce semantically identical wire fields for minimal rendering, request-sensitive support, passthrough audio, no audio, attachment, and intentional failure.
- `astrid renderers create acme.example` writes exactly `pack.yaml`, `renderer.yaml`, `render.py`, and `test_renderer.py`; generated glue is within 50 nonblank/non-comment lines and contains no placeholders.
- Scaffold collision, ownership, command-containment, static validation, trusted install, generated test, two-second smoke, and installed-wheel cases pass.

### Tasks

- [ ] **T6.1 — Enforce the M1 handoff** Run the frozen raw fixture, trusted discovery, built-in registration, `RenderService`, and conformance tests from source and an installed wheel; acceptance: `pytest -q tests/core/rendering tests/packs/rendering` plus `bash scripts/smoke_wheel_install.sh`, with any protocol defect returned to the prior oracle gate.
- [ ] **T6.2 — Add the public rendering SDK** Implement `astrid/sdk/rendering.py::{renderer_main,render,support}`, reuse core DTOs and `sdk.results._json_safe`, and update `astrid._SDK_EXPORTS`, `astrid/sdk/__init__.py::__all__`, and `tests/_sdk_contract.py::EXPECTED_PUBLIC_NAMES`; acceptance: `pytest -q tests/test_sdk_rendering.py tests/test_sdk_public_surface.py`.
- [ ] **T6.3 — Implement `RenderContext`** Add `astrid/sdk/rendering.py::RenderContext` conveniences for paths, assets, permissions, subprocesses, logs, interruption, probing, hashing, audio modes, attachments, and cleanup; acceptance: `pytest -q tests/test_sdk_render_context.py`.  [HARD]
- [ ] **T6.4 — Add shared raw/SDK conformance fixtures** Create `tests/fixtures/renderer_packs/sdk/` cases for minimal render, request-sensitive support, passthrough, no-audio, attachment, and failure, using one conformance harness for raw and SDK implementations; acceptance: `pytest -q tests/core/rendering/test_conformance.py`.
- [ ] **T6.5 — Add the exact four-file scaffold** Implement `astrid/core/rendering/scaffold.py::create_renderer_scaffold` and the initial `create` route in `astrid/core/rendering/cli.py::main`/`gateway/dispatch.py::_dispatch_renderers`, referencing packaged fixtures rather than generating a fifth file; acceptance: `pytest -q tests/core/rendering/test_scaffold.py`.
- [ ] **T6.6 — Prove the scaffold golden path** Add fresh-directory and installed-wheel tests for creation, static validation, generated test, trusted installation, and deterministic smoke output; acceptance: `pytest -q tests/core/rendering/test_scaffold_install.py` and `bash scripts/smoke_wheel_install.sh`.

## Batch 7 — CLI, replay, documentation, and epic freeze

**Checkpoint:** The oracle reviews Batch 7’s diff and the integrated epic: CLI contracts, replay ownership/redaction/drift behavior, author documentation, package contents, source-topology audit, ledger and sidecar invariants, and the complete verification matrix. Completion requires a final `PASS`.

**Acceptance criteria:**

- `astrid renderers create|list|inspect|validate|smoke|replay` is routed through `_TOP_LEVEL_HANDLERS`, appears in help, and remains unbound from project sessions.
- `list` and `inspect` perform static metadata parsing and report source kind, precedence, active revision, trust eligibility/reason, permissions, capabilities, aliases, conflicts, and overrides without importing backend code.
- `validate` is static by default and runs conformance only for execution-eligible candidates; `smoke` calls `RenderService` directly with a temporary output and creates no project run.
- Each CLI verb has a frozen raw-dictionary `--json` shape; expected errors exit 2, degraded bugs exit 1, and interruption cleans up before normal exit-130 behavior.
- Every backend failure emits a self-contained bundle under the owning project run or explicit smoke/output root with request, localized inputs, configuration, identity/digest, support, logs, result, hashes, and exact replay command.
- Bundles redact credentials, authorization headers, and signed URL queries; replay pins renderer and request hashes, reports implementation drift, and requires explicit acknowledgement before using a changed digest.
- Successful disposable workdirs are removed unless `--keep-workdir` is requested; no background TTL or cleanup daemon is introduced.
- Renderer-author documentation covers raw JSON, Python SDK, non-Python commands, trust, permissions, selection, configuration, assets, output/audio/attachments, diagnostics, replay, and legacy selectors while explicitly deferring async jobs, remote infrastructure, and layer compositing.
- Generic service/planner/dispatcher code contains no concrete Remotion/FFmpeg branches; every success has one validated video and committed sidecar, attached paths have one ledger, and every backend failure has a replay bundle.
- Full pytest, semantic parity, real FFmpeg, explicit optional-Remotion evidence, `make check`, `make ci`, wheel smoke, and Remotion typecheck pass.

### Tasks

- [ ] **T7.1 — Complete renderer CLI discovery and smoke** Extend `astrid/core/rendering/cli.py::main`, `gateway/dispatch.py::_dispatch_renderers`, `_TOP_LEVEL_HANDLERS`, and `gateway/help.py` with static `list`, `inspect`, `validate`, and direct-service `smoke`; acceptance: `pytest -q tests/core/rendering/test_cli.py`.
- [ ] **T7.2 — Freeze CLI JSON and error behavior** Add verb-specific JSON-key, session independence, conflict, trust denial, unsupported support, recovery, and interruption tests without introducing a universal envelope or independent exit-code layer; acceptance: `pytest -q tests/core/rendering/test_cli_contract.py tests/test_astrid_error_contract.py tests/test_exec_error_contract.py`.
- [ ] **T7.3 — Capture replay bundles on backend failure** Add `astrid/core/rendering/replay.py::{ReplayBundle,write_replay_bundle}` and service hooks for project-run versus explicit-root ownership, localized hashed inputs, logs/partial results, credential and URL redaction, and exact commands; acceptance: `pytest -q tests/core/rendering/test_replay_bundle.py`.  [HARD]
- [ ] **T7.4 — Implement pinned replay and drift acknowledgement** Add the `replay` CLI route, pin qualified renderer/request/manifest digests, refuse silent backend substitution, require explicit drift acknowledgement, and prove replay succeeds after an acknowledged fixture correction; acceptance: `pytest -q tests/core/rendering/test_replay.py`.  [HARD]
- [ ] **T7.5 — Finish renderer-author documentation** Write the create → implement → test → validate → trusted install → smoke → provenance golden path and separate advanced support/finalizer sections across the contract, pack-authoring, SDK, skill, stage, debugging, and compatibility docs; acceptance: `bash tests/verify_docs_commands.sh`.  [HARD]
- [ ] **T7.6 — Run the epic-wide verification and freeze** Add the generic-code backend-name audit and final success/failure/ledger/sidecar assertions, verify package data, run the complete matrix, and record evidence in `.oracle/verification.md`; acceptance: `pytest -q`, renderer parity, real FFmpeg, optional Remotion with explicit skip evidence, `make check`, `make ci`, `bash scripts/smoke_wheel_install.sh`, and `cd remotion && npm run typecheck`.

## Execution notes

- Persist this markdown exactly as `.oracle/tasklist.md` before implementation. It is frozen; any change requires an explicit oracle-reviewed plan revision.
- Record the pre-execution commit as `C0`. After each batch passes its local acceptance tests, commit the batch as `CN` before check-in. Submit the batch’s tasks, criteria, test evidence, known issues, and `git diff C(N-1)..CN` to the oracle.
- If the oracle reports issues, rework only the current batch, recommit, and resubmit the cumulative `C(N-1)..HEAD` range until `PASS`. Do not begin the next batch early.
- `[HARD]` tasks go to GPT-5.6 Sol at max reasoning. All other tasks go to DeepSeek V4 Flash with the named files, symbols, and acceptance command copied mechanically into its brief.
- Do not execute batches in parallel. Within batches, do not parallelize T1.2–T1.4, T2.4–T2.6, any T3 extraction, T4.1/T4.3/T4.4, T5.1–T5.4, T6.2–T6.5, or T7.1/T7.3/T7.4 because they share contracts, facade files, registries, provenance, or CLI routing.
- Preserve all pre-existing dirty work. Never reset, reformat, or absorb unrelated changes into a batch commit.
- Generate tiny media during tests; do not commit generated MP4 binaries. Real Remotion rendering may skip only for a precisely reported missing dependency, while Remotion typechecking remains blocking.
- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.
- At M2 handoff, any wire-contract defect returns to M1 through the oracle. Do not patch it with SDK-only behavior.

exec
/bin/zsh -lc 'rg -n "''^(class|def) |rendering'"\\.(remotion|ffmpeg)|legacy_hybrid|selector|override|support|publish|provenance|cleanup|output_name|finaliz\" astrid/core/rendering/service.py astrid/core/rendering/provenance.py astrid/packs/rendering/planners/legacy_hybrid/run.py astrid/packs/rendering/executors/render/run.py astrid/packs/rendering/executors/render/executor.yaml | head -n 500" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/provenance.py:1:"""Core-owned provenance v2 assembly for timeline renders."""
astrid/core/rendering/provenance.py:40:def validate_backend_fragments(
astrid/core/rendering/provenance.py:56:def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
astrid/core/rendering/provenance.py:69:def _normalize_attachments(
astrid/core/rendering/provenance.py:97:def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
astrid/core/rendering/provenance.py:108:def _resolution_request_id(segment: RenderSegment) -> str:
astrid/core/rendering/provenance.py:111:    Alias chains retain their requested id first.  An override without an
astrid/core/rendering/provenance.py:112:    alias retains its source in ``override.from``.  Otherwise the resolved id
astrid/core/rendering/provenance.py:121:    if renderer.override is not None:
astrid/core/rendering/provenance.py:122:        return renderer.override["from"]
astrid/core/rendering/provenance.py:126:def _resolved_policy(plan: RenderPlan) -> dict[str, Any]:
astrid/core/rendering/provenance.py:135:        "finalizer": plan.finalizer.id,
astrid/core/rendering/provenance.py:139:def _routing_record(
astrid/core/rendering/provenance.py:147:    first and emits a warning when that supported route wins.  The plan pins
astrid/core/rendering/provenance.py:151:    for aliases, overrides, trust, manifests, and support decisions.
astrid/core/rendering/provenance.py:159:        and _resolution_request_id(plan.segments[0]) == "rendering.ffmpeg"
astrid/core/rendering/provenance.py:164:            "legacy selector 'remotion' auto-routed the supported request to "
astrid/core/rendering/provenance.py:179:def _reject_duplicate_attachment_names(
astrid/core/rendering/provenance.py:192:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:252:                # its (validated) path so emitted provenance round-trips.
astrid/core/rendering/provenance.py:285:def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
astrid/core/rendering/provenance.py:362:def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
astrid/core/rendering/provenance.py:374:def _normalize_v1_compatibility(
astrid/core/rendering/provenance.py:397:def assemble_provenance_v2(
astrid/core/rendering/provenance.py:411:    """Assemble additive provenance v2 with protected ownership boundaries.
astrid/core/rendering/provenance.py:468:        "finalizer": normalized_plan.finalizer.to_dict(),
astrid/core/rendering/provenance.py:473:    return _json_safe_mapping(payload, label="provenance")
astrid/core/rendering/provenance.py:476:def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
astrid/core/rendering/provenance.py:477:    """Compatibility spelling for :func:`assemble_provenance_v2`."""
astrid/core/rendering/provenance.py:479:    return assemble_provenance_v2(**kwargs)
astrid/core/rendering/provenance.py:482:def write_provenance_v2(path: str | Path, **kwargs: Any) -> dict[str, Any]:
astrid/core/rendering/provenance.py:483:    """Assemble and atomically write a provenance v2 sidecar."""
astrid/core/rendering/provenance.py:485:    payload = assemble_provenance_v2(**kwargs)
astrid/core/rendering/provenance.py:490:def hash_input_files(paths: Mapping[str, str | Path]) -> dict[str, str]:
astrid/core/rendering/provenance.py:499:def digest_manifest(path: str | Path) -> str:
astrid/core/rendering/provenance.py:509:    "assemble_provenance",
astrid/core/rendering/provenance.py:510:    "assemble_provenance_v2",
astrid/core/rendering/provenance.py:514:    "write_provenance_v2",
astrid/core/rendering/service.py:4:renderer selector spellings.  Everything after that compatibility boundary is
astrid/core/rendering/service.py:49:    raise_unsupported_error,
astrid/core/rendering/service.py:51:from .provenance import assemble_provenance_v2
astrid/core/rendering/service.py:52:from .publication import publish_render_result
astrid/core/rendering/service.py:70:_DIRECT_FINALIZER_ID = "astrid.direct-finalizer"
astrid/core/rendering/service.py:72:    b"astrid.direct-finalizer/v1"
astrid/core/rendering/service.py:75:CapabilityKind = Literal["renderer", "planner", "finalizer"]
astrid/core/rendering/service.py:80:class LegacyRenderRoutingWarning(UserWarning):
astrid/core/rendering/service.py:81:    """A legacy selector selected a different qualified backend."""
astrid/core/rendering/service.py:85:class _SelectionPolicy:
astrid/core/rendering/service.py:93:class _ResolvedCapability:
astrid/core/rendering/service.py:96:    support: SupportReport
astrid/core/rendering/service.py:99:def _translate_legacy_selector(selector: str | None) -> _SelectionPolicy:
astrid/core/rendering/service.py:103:    policy: request-sensitive FFmpeg support gets the first opportunity, then
astrid/core/rendering/service.py:104:    Remotion.  Qualified selectors contain no fallback and are therefore
astrid/core/rendering/service.py:105:    strict (normal registry aliases and overrides still apply).
astrid/core/rendering/service.py:108:    if selector is None:
astrid/core/rendering/service.py:109:        selector = "remotion"
astrid/core/rendering/service.py:110:    if selector == "ffmpeg":
astrid/core/rendering/service.py:111:        return _SelectionPolicy(selector, "renderer", ("rendering.ffmpeg",))
astrid/core/rendering/service.py:112:    if selector == "remotion":
astrid/core/rendering/service.py:114:            selector,
astrid/core/rendering/service.py:116:            ("rendering.ffmpeg", "rendering.remotion"),
astrid/core/rendering/service.py:119:    if selector == "hybrid":
astrid/core/rendering/service.py:121:            selector,
astrid/core/rendering/service.py:123:            ("rendering.legacy_hybrid",),
astrid/core/rendering/service.py:125:    if isinstance(selector, str) and _QUALIFIED_ID_RE.fullmatch(selector):
astrid/core/rendering/service.py:126:        return _SelectionPolicy(selector, "renderer", (selector,))
astrid/core/rendering/service.py:127:    raise_unsupported_error(
astrid/core/rendering/service.py:129:        message=f"unknown renderer selector {selector!r}",
astrid/core/rendering/service.py:131:            "select a qualified renderer id or one of the legacy selectors: "
astrid/core/rendering/service.py:135:            "selector": selector if isinstance(selector, str) else repr(selector),
astrid/core/rendering/service.py:136:            "legacy_selectors": ["remotion", "ffmpeg", "hybrid"],
astrid/core/rendering/service.py:141:class RenderService:
astrid/core/rendering/service.py:142:    """Resolve, invoke, validate, finalize, and publish one timeline render.
astrid/core/rendering/service.py:153:        finalizer_registry: FinalizerRegistry | None = None,
astrid/core/rendering/service.py:165:        publisher: Callable[..., Path] = publish_render_result,
astrid/core/rendering/service.py:166:        provenance_builder: Callable[..., dict[str, Any]] = assemble_provenance_v2,
astrid/core/rendering/service.py:169:        finalizer_id: str | None = None,
astrid/core/rendering/service.py:174:            finalizer_registry,
astrid/core/rendering/service.py:191:        self.renderers, self.planners, self.finalizers = registries
astrid/core/rendering/service.py:194:        self.finalizer_registry = self.finalizers
astrid/core/rendering/service.py:198:        self._publisher = publisher
astrid/core/rendering/service.py:199:        self._provenance_builder = provenance_builder
astrid/core/rendering/service.py:202:        # Direct renders need no executable finalizer.  An embedding host may
astrid/core/rendering/service.py:203:        # nevertheless request a registered finalizer identity for direct-plan
astrid/core/rendering/service.py:204:        # provenance; otherwise a core no-op resolution is recorded.  Planned
astrid/core/rendering/service.py:205:        # renders always use the finalizer pinned by their RenderPlan.
astrid/core/rendering/service.py:206:        self.finalizer_id = finalizer_id
astrid/core/rendering/service.py:214:        selector: str | None = None,
astrid/core/rendering/service.py:233:        selected = self._one_selector(selector, engine, backend)
astrid/core/rendering/service.py:261:                    "output_name": destination_path.name,
astrid/core/rendering/service.py:282:            selector=selected,
astrid/core/rendering/service.py:293:        selector: str | None = None,
astrid/core/rendering/service.py:314:                sidecar_path or f"{output}.provenance.json"
astrid/core/rendering/service.py:319:                    message="video and provenance sidecar paths must be different",
astrid/core/rendering/service.py:320:                    recovery_command="choose a distinct .provenance.json sidecar path",
astrid/core/rendering/service.py:323:            policy = _translate_legacy_selector(selector)
astrid/core/rendering/service.py:326:                requested=selector,
astrid/core/rendering/service.py:374:    def _one_selector(
astrid/core/rendering/service.py:375:        selector: str | None,
astrid/core/rendering/service.py:379:        supplied = [item for item in (selector, engine, backend) if item is not None]
astrid/core/rendering/service.py:385:                message="selector, engine, and backend disagree",
astrid/core/rendering/service.py:386:                recovery_command="supply one renderer selector spelling and retry",
astrid/core/rendering/service.py:387:                details={"selectors": supplied},
astrid/core/rendering/service.py:420:            plan, segment_results, pinned_finalizer = self._execute_planner(
astrid/core/rendering/service.py:427:                raise_unsupported_error(
astrid/core/rendering/service.py:437:                pinned_finalizer=pinned_finalizer,
astrid/core/rendering/service.py:452:                output_name=request.output_name,
astrid/core/rendering/service.py:492:        provenance = self._provenance_builder(
astrid/core/rendering/service.py:506:            "publish",
astrid/core/rendering/service.py:513:        published = self._publisher(
astrid/core/rendering/service.py:515:            provenance,
astrid/core/rendering/service.py:520:        return Path(published)
astrid/core/rendering/service.py:540:                report = self._support(
astrid/core/rendering/service.py:549:                if exc.error.kind not in {"unsupported", "binary_missing"}:
astrid/core/rendering/service.py:553:            if not report.supported:
astrid/core/rendering/service.py:557:                self._unsupported_report(report, registry=registry)
astrid/core/rendering/service.py:560:                    f"legacy selector {policy.requested!r} auto-routed this supported "
astrid/core/rendering/service.py:569:        raise_unsupported_error(
astrid/core/rendering/service.py:571:            message=f"no renderer supports legacy selector {policy.requested!r}",
astrid/core/rendering/service.py:600:            raise_unsupported_error(
astrid/core/rendering/service.py:632:            raise_unsupported_error(
astrid/core/rendering/service.py:658:            "override",
astrid/core/rendering/service.py:660:            override=evidence.get("override"),
astrid/core/rendering/service.py:686:    def _support(
astrid/core/rendering/service.py:696:        self._observe("support", backend=candidate.id)
astrid/core/rendering/service.py:697:        if "support" in manifest.operations:
astrid/core/rendering/service.py:700:                "support",
astrid/core/rendering/service.py:708:                    message="support operation did not return a SupportReport",
astrid/core/rendering/service.py:714:                    message="support report names a different backend",
astrid/core/rendering/service.py:720:                    message="support report version does not match its manifest",
astrid/core/rendering/service.py:728:        return self._static_support(candidate, projected, registry=registry)
astrid/core/rendering/service.py:730:    def _static_support(
astrid/core/rendering/service.py:740:            support_key = (
astrid/core/rendering/service.py:741:                "supports_windows"
astrid/core/rendering/service.py:743:                else "supports_full_timeline"
astrid/core/rendering/service.py:745:            if capabilities.get(support_key) is not True:
astrid/core/rendering/service.py:748:                    f"renderer does not declare static support for {mode}"
astrid/core/rendering/service.py:755:                        "renderer does not declare static audio ownership support"
astrid/core/rendering/service.py:759:                        f"audio ownership {request.audio.value!r} is not statically supported"
astrid/core/rendering/service.py:772:                        f"output container {request.profile.container!r} is not statically supported"
astrid/core/rendering/service.py:783:                    reasons.append("finalizer does not declare static containers")
astrid/core/rendering/service.py:786:                        f"output container {request.profile.container!r} is not statically supported"
astrid/core/rendering/service.py:792:                        "finalizer does not declare static audio ownership support"
astrid/core/rendering/service.py:796:                        f"audio ownership {request.audio.value!r} is not statically supported"
astrid/core/rendering/service.py:799:                reasons.append("finalizer does not declare attachment preservation")
astrid/core/rendering/service.py:803:            supported=not reasons,
astrid/core/rendering/service.py:821:        A renderer without a ``support`` verb has only its manifest as
astrid/core/rendering/service.py:845:            return [f"timeline cannot be evaluated against static support: {exc}"]
astrid/core/rendering/service.py:856:                        "timeline uses statically unsupported clip types: "
astrid/core/rendering/service.py:867:                        "timeline uses statically unsupported track types: "
astrid/core/rendering/service.py:872:    def _unsupported_report(
astrid/core/rendering/service.py:881:        raise_unsupported_error(
astrid/core/rendering/service.py:883:            message=f"{report.backend} does not support this render request",
astrid/core/rendering/service.py:898:        output_name: str,
astrid/core/rendering/service.py:901:        backend_request = replace(request, output_name=output_name).for_backend(
astrid/core/rendering/service.py:943:        ``supports_windows: false`` receives an invocation-private sliced
astrid/core/rendering/service.py:949:        if candidate.manifest.capabilities.get("supports_windows") is not False:
astrid/core/rendering/service.py:1161:        # still carry the pre-alias/pre-override identity it was asked to
astrid/core/rendering/service.py:1178:                output_name=f"segment-{index:04d}.mp4",
astrid/core/rendering/service.py:1187:            report = self._support(
astrid/core/rendering/service.py:1193:            if not report.supported:
astrid/core/rendering/service.py:1194:                self._unsupported_report(report, registry=self.renderers)
astrid/core/rendering/service.py:1210:                output_name=segment_request.output_name,
astrid/core/rendering/service.py:1212:                # finalizer must normalize.  The artifact is first validated
astrid/core/rendering/service.py:1216:                # pinned finalizer.
astrid/core/rendering/service.py:1225:                defer_to_finalizer=len(response.segments) > 1,
astrid/core/rendering/service.py:1235:        finalizer, finalizer_evidence = self._resolve_candidate(
astrid/core/rendering/service.py:1236:            self.finalizers,
astrid/core/rendering/service.py:1237:            response.finalizer.id,
astrid/core/rendering/service.py:1238:            kind="finalizer",
astrid/core/rendering/service.py:1241:        finalizer_resolution = self._finalizer_resolution(
astrid/core/rendering/service.py:1242:            finalizer,
astrid/core/rendering/service.py:1243:            finalizer_evidence,
astrid/core/rendering/service.py:1244:            support=None,
astrid/core/rendering/service.py:1252:            finalizer=finalizer_resolution,
astrid/core/rendering/service.py:1254:        return plan, segment_results, (finalizer, finalizer_evidence)
astrid/core/rendering/service.py:1262:        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
astrid/core/rendering/service.py:1273:        candidate, evidence = pinned_finalizer
astrid/core/rendering/service.py:1281:        support_audio = (
astrid/core/rendering/service.py:1287:        support_request = RenderRequest(
astrid/core/rendering/service.py:1291:            output_name=request.output_name,
astrid/core/rendering/service.py:1292:            audio=support_audio,
astrid/core/rendering/service.py:1297:        report = self._support(
astrid/core/rendering/service.py:1299:            request=support_request,
astrid/core/rendering/service.py:1301:            registry=self.finalizers,
astrid/core/rendering/service.py:1303:        if not report.supported:
astrid/core/rendering/service.py:1304:            self._unsupported_report(report, registry=self.finalizers)
astrid/core/rendering/service.py:1305:        finalizer_resolution = self._finalizer_resolution(
astrid/core/rendering/service.py:1308:            support=report,
astrid/core/rendering/service.py:1310:        plan = replace(plan, finalizer=finalizer_resolution)
astrid/core/rendering/service.py:1311:        finalize_request = FinalizeRequest(
astrid/core/rendering/service.py:1315:            output_name=request.output_name,
astrid/core/rendering/service.py:1323:        self._observe("finalize", backend=candidate.id)
astrid/core/rendering/service.py:1326:            "finalize",
astrid/core/rendering/service.py:1327:            finalize_request,
astrid/core/rendering/service.py:1333:                message="finalize operation did not return a RenderResult",
astrid/core/rendering/service.py:1337:            response = finalize_request.validate_final_result(response)
astrid/core/rendering/service.py:1341:                message=f"finalizer returned an invalid result: {exc}",
astrid/core/rendering/service.py:1342:                recovery_command="rerun finalization in a fresh invocation workspace",
astrid/core/rendering/service.py:1360:            label="finalized artifact",
astrid/core/rendering/service.py:1390:        defer_to_finalizer: bool = False,
astrid/core/rendering/service.py:1413:        if defer_to_finalizer:
astrid/core/rendering/service.py:1414:            # A registered finalizer owns cross-segment compatibility: it may
astrid/core/rendering/service.py:1417:            # once on the finalized result below.
astrid/core/rendering/service.py:1436:                raise_unsupported_error(
astrid/core/rendering/service.py:1533:        finalizer_resolution = self._direct_finalizer_resolution()
astrid/core/rendering/service.py:1579:            finalizer=finalizer_resolution,
astrid/core/rendering/service.py:1586:    def _direct_finalizer_resolution(self) -> FinalizerResolution:
astrid/core/rendering/service.py:1587:        if self.finalizer_id is not None:
astrid/core/rendering/service.py:1589:                self.finalizers,
astrid/core/rendering/service.py:1590:                self.finalizer_id,
astrid/core/rendering/service.py:1591:                kind="finalizer",
astrid/core/rendering/service.py:1594:            return self._finalizer_resolution(candidate, evidence, support=None)
astrid/core/rendering/service.py:1630:            override=evidence.get("override"),
astrid/core/rendering/service.py:1631:            support_decision=selected.support,
astrid/core/rendering/service.py:1646:            override=evidence.get("override"),
astrid/core/rendering/service.py:1647:            support_decision=selected.support,
astrid/core/rendering/service.py:1650:    def _finalizer_resolution(
astrid/core/rendering/service.py:1655:        support: SupportReport | None,
astrid/core/rendering/service.py:1663:            override=evidence.get("override"),
astrid/core/rendering/service.py:1664:            support_decision=support,
astrid/core/rendering/service.py:1767:        segment_provenance: list[dict[str, Any]] = []
astrid/core/rendering/service.py:1773:                segment_provenance.append(dict(legacy))
astrid/core/rendering/service.py:1783:        if len(segment_provenance) > 1:
astrid/core/rendering/service.py:1784:            compatibility["segment_provenance"] = segment_provenance
astrid/core/rendering/service.py:1816:            "unsupported": "select a compatible renderer and retry",
astrid/packs/rendering/executors/render/executor.yaml:11:  "clip_kinds_supported": [
astrid/packs/rendering/executors/render/executor.yaml:27:      "{out}/{output_name}"
astrid/packs/rendering/executors/render/executor.yaml:57:        "input": "output_name",
astrid/packs/rendering/executors/render/executor.yaml:113:      "description": "Render selector. Legacy values (remotion, ffmpeg, hybrid) or a qualified backend id (e.g. rendering.remotion, rendering.ffmpeg).",
astrid/packs/rendering/executors/render/executor.yaml:120:      "description": "Neutral alias for engine: legacy selector or qualified backend id.",
astrid/packs/rendering/executors/render/executor.yaml:127:      "description": "JSON object keyed by qualified backend id with per-backend configuration (e.g. {\"rendering.remotion\": {\"theme_path\": \"/path/theme.json\"}}).",
astrid/packs/rendering/executors/render/executor.yaml:135:      "name": "output_name",
astrid/packs/rendering/executors/render/executor.yaml:142:      "description": "Preserve previous provenance-linked hype.mp4 outputs for the same timeline.",
astrid/packs/rendering/executors/render/executor.yaml:180:      "path_template": "{out}/{output_name}",
astrid/packs/rendering/executors/render/executor.yaml:185:      "description": "Render provenance sidecar for the video output.",
astrid/packs/rendering/executors/render/executor.yaml:187:      "name": "provenance",
astrid/packs/rendering/executors/render/executor.yaml:188:      "path_template": "{out}/{output_name}.provenance.json",
astrid/packs/rendering/executors/render/executor.yaml:190:      "artifact_type": "metadata/provenance"
astrid/packs/rendering/planners/legacy_hybrid/run.py:4:The planner owns only deterministic window construction and renderer support
astrid/packs/rendering/planners/legacy_hybrid/run.py:5:selection.  It never renders a segment or finalizes media; ``RenderService``
astrid/packs/rendering/planners/legacy_hybrid/run.py:44:    raise_unsupported_error,
astrid/packs/rendering/planners/legacy_hybrid/run.py:56:BACKEND_ID = "rendering.legacy_hybrid"
astrid/packs/rendering/planners/legacy_hybrid/run.py:58:FINALIZER_ID = "rendering.ffmpeg-finalizer"
astrid/packs/rendering/planners/legacy_hybrid/run.py:59:FFMPEG_ID = "rendering.ffmpeg"
astrid/packs/rendering/planners/legacy_hybrid/run.py:60:REMOTION_ID = "rendering.remotion"
astrid/packs/rendering/planners/legacy_hybrid/run.py:78:def _number(value: Any, label: str) -> Fraction:
astrid/packs/rendering/planners/legacy_hybrid/run.py:86:def _floor(value: Fraction) -> int:
astrid/packs/rendering/planners/legacy_hybrid/run.py:90:def _ceil(value: Fraction) -> int:
astrid/packs/rendering/planners/legacy_hybrid/run.py:94:def _clip_duration_seconds(clip: Mapping[str, Any]) -> Fraction:
astrid/packs/rendering/planners/legacy_hybrid/run.py:105:def _clip_timeline_end(clip: Mapping[str, Any]) -> Fraction:
astrid/packs/rendering/planners/legacy_hybrid/run.py:118:def _timeline_duration(timeline: Mapping[str, Any]) -> Fraction:
astrid/packs/rendering/planners/legacy_hybrid/run.py:141:def _base_visual_track(
astrid/packs/rendering/planners/legacy_hybrid/run.py:159:def _complex_frame_windows(
astrid/packs/rendering/planners/legacy_hybrid/run.py:267:def _segment_kinds(
astrid/packs/rendering/planners/legacy_hybrid/run.py:292:def _complex_clip_windows(
astrid/packs/rendering/planners/legacy_hybrid/run.py:309:def _hybrid_segments(
astrid/packs/rendering/planners/legacy_hybrid/run.py:326:def _structural_reasons(timeline: Mapping[str, Any]) -> list[str]:
astrid/packs/rendering/planners/legacy_hybrid/run.py:351:                f"Clip {clip.get('id')!r} uses unsupported speed {float(speed):g}; "
astrid/packs/rendering/planners/legacy_hybrid/run.py:368:def _load_inputs(
astrid/packs/rendering/planners/legacy_hybrid/run.py:389:def _input_path(raw: str, workspace: Path) -> Path:
astrid/packs/rendering/planners/legacy_hybrid/run.py:394:def _planner_config(request: RenderRequest) -> dict[str, Any]:
astrid/packs/rendering/planners/legacy_hybrid/run.py:402:def _string_list(value: Any, *, label: str, default: Sequence[str]) -> tuple[str, ...]:
astrid/packs/rendering/planners/legacy_hybrid/run.py:418:def _candidate_lists(config: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
astrid/packs/rendering/planners/legacy_hybrid/run.py:437:def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
astrid/packs/rendering/planners/legacy_hybrid/run.py:468:        supported=not reasons,
astrid/packs/rendering/planners/legacy_hybrid/run.py:473:            "support_based_assignment": True,
astrid/packs/rendering/planners/legacy_hybrid/run.py:474:            "explicit_finalizer": True,
astrid/packs/rendering/planners/legacy_hybrid/run.py:483:def _window_timeline(
astrid/packs/rendering/planners/legacy_hybrid/run.py:529:def _source_pack(candidate: RenderingCandidate[Any]) -> dict[str, Any]:
astrid/packs/rendering/planners/legacy_hybrid/run.py:537:def _renderer_resolution(
astrid/packs/rendering/planners/legacy_hybrid/run.py:549:            override=None,
astrid/packs/rendering/planners/legacy_hybrid/run.py:550:            support_decision=report,
astrid/packs/rendering/planners/legacy_hybrid/run.py:551:            trust_eligibility={"eligible": True, "method": "injected-support"},
astrid/packs/rendering/planners/legacy_hybrid/run.py:560:        override=evidence.get("override"),
astrid/packs/rendering/planners/legacy_hybrid/run.py:561:        support_decision=report,
astrid/packs/rendering/planners/legacy_hybrid/run.py:566:def _finalizer_resolution(registry: FinalizerRegistry | None) -> FinalizerResolution:
astrid/packs/rendering/planners/legacy_hybrid/run.py:573:            override=None,
astrid/packs/rendering/planners/legacy_hybrid/run.py:575:            support_decision=None,
astrid/packs/rendering/planners/legacy_hybrid/run.py:584:        override=evidence.get("override"),
astrid/packs/rendering/planners/legacy_hybrid/run.py:586:        support_decision=None,
astrid/packs/rendering/planners/legacy_hybrid/run.py:590:def _planner_resolution(report: SupportReport) -> PlannerResolution:
astrid/packs/rendering/planners/legacy_hybrid/run.py:598:        override=None,
astrid/packs/rendering/planners/legacy_hybrid/run.py:599:        support_decision=report,
astrid/packs/rendering/planners/legacy_hybrid/run.py:603:class _CommandSupportResolver:
astrid/packs/rendering/planners/legacy_hybrid/run.py:624:        if candidate.manifest.capabilities.get("supports_windows") is False:
astrid/packs/rendering/planners/legacy_hybrid/run.py:626:                raise ValueError("planned renderer support requires a frame window")
astrid/packs/rendering/planners/legacy_hybrid/run.py:627:            path = self.workspace / "planner-support" / f"{self.counter:04d}-timeline.json"
astrid/packs/rendering/planners/legacy_hybrid/run.py:631:        if "support" not in candidate.manifest.operations:
astrid/packs/rendering/planners/legacy_hybrid/run.py:632:            supports = candidate.manifest.capabilities.get(
astrid/packs/rendering/planners/legacy_hybrid/run.py:633:                "supports_windows" if projected.window is not None else "supports_full_timeline"
astrid/packs/rendering/planners/legacy_hybrid/run.py:637:                supported=supports,
astrid/packs/rendering/planners/legacy_hybrid/run.py:638:                reasons=[] if supports else ["renderer lacks static support for this window"],
astrid/packs/rendering/planners/legacy_hybrid/run.py:648:        request_path = self.workspace / "planner-support" / f"{self.counter:04d}-request.json"
astrid/packs/rendering/planners/legacy_hybrid/run.py:649:        result_path = self.workspace / "planner-support" / f"{self.counter:04d}-result.json"
astrid/packs/rendering/planners/legacy_hybrid/run.py:653:            "support",
astrid/packs/rendering/planners/legacy_hybrid/run.py:662:            raise TypeError(f"{candidate.id} support did not return a SupportReport")
astrid/packs/rendering/planners/legacy_hybrid/run.py:666:def plan(
astrid/packs/rendering/planners/legacy_hybrid/run.py:670:    support_resolver: SupportResolver | None = None,
astrid/packs/rendering/planners/legacy_hybrid/run.py:673:    report = support(request, workspace=workspace)
astrid/packs/rendering/planners/legacy_hybrid/run.py:674:    if not report.supported:
astrid/packs/rendering/planners/legacy_hybrid/run.py:675:        raise_unsupported_error(
astrid/packs/rendering/planners/legacy_hybrid/run.py:677:            message="legacy hybrid planner does not support this request",
astrid/packs/rendering/planners/legacy_hybrid/run.py:695:    finalizer_registry: FinalizerRegistry | None
astrid/packs/rendering/planners/legacy_hybrid/run.py:696:    if registries is None and support_resolver is None:
astrid/packs/rendering/planners/legacy_hybrid/run.py:703:        renderer_registry, _planners, finalizer_registry = load_default_registries(
astrid/packs/rendering/planners/legacy_hybrid/run.py:709:        finalizer_registry = None
astrid/packs/rendering/planners/legacy_hybrid/run.py:711:        renderer_registry, finalizer_registry = registries
astrid/packs/rendering/planners/legacy_hybrid/run.py:712:    if support_resolver is None:
astrid/packs/rendering/planners/legacy_hybrid/run.py:714:            raise RuntimeError("renderer registry is required for command support resolution")
astrid/packs/rendering/planners/legacy_hybrid/run.py:715:        support_resolver = _CommandSupportResolver(
astrid/packs/rendering/planners/legacy_hybrid/run.py:742:            output_name=f"segment-{index:04d}.mp4",
astrid/packs/rendering/planners/legacy_hybrid/run.py:750:                candidate_report = support_resolver(
astrid/packs/rendering/planners/legacy_hybrid/run.py:759:                attempts.append(f"{renderer_id}: support report named {candidate_report.backend}")
astrid/packs/rendering/planners/legacy_hybrid/run.py:761:            if candidate_report.supported:
astrid/packs/rendering/planners/legacy_hybrid/run.py:769:            raise_unsupported_error(
astrid/packs/rendering/planners/legacy_hybrid/run.py:771:                message=f"no renderer supports planned {kind} window [{start},{end})",
astrid/packs/rendering/planners/legacy_hybrid/run.py:772:                recovery_command="install or configure a renderer supporting the reported window",
astrid/packs/rendering/planners/legacy_hybrid/run.py:794:            f"{kind} legacy window assigned to {selected_id} by supported report"
astrid/packs/rendering/planners/legacy_hybrid/run.py:803:        finalizer=_finalizer_resolution(finalizer_registry),
astrid/packs/rendering/planners/legacy_hybrid/run.py:811:def _load_request(path: Path) -> RenderRequest:
astrid/packs/rendering/planners/legacy_hybrid/run.py:818:def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
astrid/packs/rendering/planners/legacy_hybrid/run.py:841:def main(argv: Sequence[str] | None = None) -> int:
astrid/packs/rendering/planners/legacy_hybrid/run.py:843:    parser.add_argument("verb", choices=("plan", "support"))
astrid/packs/rendering/planners/legacy_hybrid/run.py:859:        if args.verb == "support":
astrid/packs/rendering/planners/legacy_hybrid/run.py:860:            response = support(request, workspace=workspace)
astrid/packs/rendering/planners/legacy_hybrid/run.py:890:    "support",
astrid/packs/rendering/executors/render/run.py:26:from astrid.core.rendering.publication import publish_render_result
astrid/packs/rendering/executors/render/run.py:32:from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
astrid/packs/rendering/executors/render/run.py:33:from astrid.packs.rendering.planners.legacy_hybrid.run import (
astrid/packs/rendering/executors/render/run.py:62:_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
astrid/packs/rendering/executors/render/run.py:63:_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
astrid/packs/rendering/executors/render/run.py:64:_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
astrid/packs/rendering/executors/render/run.py:65:_render_provenance_payload = remotion_backend._render_provenance_payload
astrid/packs/rendering/executors/render/run.py:66:_write_render_provenance = remotion_backend._write_render_provenance
astrid/packs/rendering/executors/render/run.py:72:# an ``output_name`` input defaulting to this sentinel; non-default names are
astrid/packs/rendering/executors/render/run.py:82:    "hybrid_finalizer_profile",
astrid/packs/rendering/executors/render/run.py:89:def _default_service() -> RenderService:
astrid/packs/rendering/executors/render/run.py:93:    validation, audio completion, finalization, and publication all happen
astrid/packs/rendering/executors/render/run.py:95:    legacy argument surface onto the service call and returns the published
astrid/packs/rendering/executors/render/run.py:104:def validate_output_name(name: str) -> str:
astrid/packs/rendering/executors/render/run.py:105:    """Validate an ``output_name``: a plain ``.mp4`` file name.
astrid/packs/rendering/executors/render/run.py:114:        raise ValueError("output_name must not be empty")
astrid/packs/rendering/executors/render/run.py:117:            f"output_name must not traverse directories, got {name!r}"
astrid/packs/rendering/executors/render/run.py:121:            f"output_name must be a plain file name without path separators, got {name!r}"
astrid/packs/rendering/executors/render/run.py:125:            f"output_name must be a plain file name, got {name!r}"
astrid/packs/rendering/executors/render/run.py:129:            f"output_name must end with .mp4, got {name!r}"
astrid/packs/rendering/executors/render/run.py:134:def _legacy_backend_config(
astrid/packs/rendering/executors/render/run.py:144:    correspond to the historical selector spellings and scopes each legacy
astrid/packs/rendering/executors/render/run.py:159:        config["rendering.remotion"] = remotion
astrid/packs/rendering/executors/render/run.py:164:        config["rendering.legacy_hybrid"] = hybrid
astrid/packs/rendering/executors/render/run.py:168:def _parse_backend_config(value: str | None) -> dict[str, dict[str, Any]]:
astrid/packs/rendering/executors/render/run.py:190:def _swap_from_dump(clip: dict) -> dict:
astrid/packs/rendering/executors/render/run.py:197:def _write_empty_asset_registry(path: Path) -> None:
astrid/packs/rendering/executors/render/run.py:202:def _clip_timeline_end_seconds(clip: dict) -> float:
astrid/packs/rendering/executors/render/run.py:214:def _timeline_duration_seconds(timeline_data: dict) -> float:
astrid/packs/rendering/executors/render/run.py:224:def _round_frame_time(seconds: float, fps: int | Fraction, *, mode: str) -> float:
astrid/packs/rendering/executors/render/run.py:241:def _clip_overlaps(clip: dict, start: float, end: float) -> bool:
astrid/packs/rendering/executors/render/run.py:247:def _window_clip(clip: dict, start: float, end: float) -> dict | None:
astrid/packs/rendering/executors/render/run.py:269:def _window_timeline_data(timeline_data: dict, start: float, end: float, *, media_only: bool) -> dict:
astrid/packs/rendering/executors/render/run.py:296:def _render_ffmpeg_media_to_path(
astrid/packs/rendering/executors/render/run.py:308:def _render_ffmpeg_media(
astrid/packs/rendering/executors/render/run.py:328:def _can_render_with_ffmpeg_media(
astrid/packs/rendering/executors/render/run.py:338:def _concat_segments(segment_paths: list[Path], out_path: Path) -> None:
astrid/packs/rendering/executors/render/run.py:347:    ffmpeg_finalizer.concat_segment_files(
astrid/packs/rendering/executors/render/run.py:355:def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
astrid/packs/rendering/executors/render/run.py:384:        segment_provenance: list[dict[str, Any]] = []
astrid/packs/rendering/executors/render/run.py:397:                # finalizer normalize to the exact canonical rational rate.
astrid/packs/rendering/executors/render/run.py:402:                overrides = dict(segment_timeline.get("theme_overrides", {}))
astrid/packs/rendering/executors/render/run.py:403:                visual = dict(overrides.get("visual", {}))
astrid/packs/rendering/executors/render/run.py:407:                overrides["visual"] = visual
astrid/packs/rendering/executors/render/run.py:408:                segment_timeline["theme_overrides"] = overrides
astrid/packs/rendering/executors/render/run.py:425:                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
astrid/packs/rendering/executors/render/run.py:427:                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
astrid/packs/rendering/executors/render/run.py:436:        provenance = _render_provenance_payload(
astrid/packs/rendering/executors/render/run.py:448:            segment_provenance=segment_provenance,
astrid/packs/rendering/executors/render/run.py:450:        output = publish_render_result(
astrid/packs/rendering/executors/render/run.py:452:            provenance,
astrid/packs/rendering/executors/render/run.py:454:            sidecar_path=_render_provenance_sidecar_path(out_path),
astrid/packs/rendering/executors/render/run.py:480:def _previous_render_outputs_for_timeline(
astrid/packs/rendering/executors/render/run.py:487:    with the legacy cleanup call site.  Filtering now happens under each
astrid/packs/rendering/executors/render/run.py:506:def _parse_bool_arg(value: str | bool | None) -> bool:
astrid/packs/rendering/executors/render/run.py:519:def _audio_reactive_ffmpeg_element(
astrid/packs/rendering/executors/render/run.py:525:def _render_audio_reactive_colour_if_supported(
astrid/packs/rendering/executors/render/run.py:534:    return ffmpeg_backend.render_audio_reactive_colour_if_supported(
astrid/packs/rendering/executors/render/run.py:546:def render(
astrid/packs/rendering/executors/render/run.py:559:    """Render through :class:`RenderService` and publish one locked pair.
astrid/packs/rendering/executors/render/run.py:562:    dispatch (legacy engine translation, renderer/planner selection, support,
astrid/packs/rendering/executors/render/run.py:563:    invocation, validation, audio completion, finalization, publication)
astrid/packs/rendering/executors/render/run.py:568:    validate_output_name(out_path.name)
astrid/packs/rendering/executors/render/run.py:587:        selector=engine,
astrid/packs/rendering/executors/render/run.py:593:def main(argv: Sequence[str] | None = None) -> int:
astrid/packs/rendering/executors/render/run.py:601:        help="Legacy selector (remotion, ffmpeg, hybrid) or a qualified renderer id.",
astrid/packs/rendering/executors/render/run.py:606:        help="Neutral alias for --engine: legacy selector or qualified backend id.",
astrid/packs/rendering/executors/render/run.py:636:        if args.output_name is not None:
astrid/packs/rendering/executors/render/run.py:637:            validate_output_name(args.output_name)
astrid/packs/rendering/executors/render/run.py:638:            if Path(args.out).name != args.output_name:
astrid/packs/rendering/executors/render/run.py:641:                    f"--output-name {args.output_name!r}"
astrid/packs/rendering/executors/render/run.py:644:            validate_output_name(Path(args.out).name)
astrid/packs/rendering/executors/render/run.py:645:        selector = args.backend if args.backend is not None else args.engine
astrid/packs/rendering/executors/render/run.py:655:                    engine=selector,
astrid/packs/rendering/executors/render/run.py:668:                engine=selector,

exec
/bin/zsh -lc "sed -n '1,220p' astrid/core/rendering/service.py && sed -n '220,620p' astrid/core/rendering/service.py && sed -n '620,1040p' astrid/core/rendering/service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
"""Backend-neutral orchestration for one committed timeline render.

``RenderService`` is the only core component that understands the legacy
renderer selector spellings.  Everything after that compatibility boundary is
resolved through the rendering registries and invoked through protocol v1.
Backends write private artifacts in an invocation workspace; the service
validates them and performs exactly one locked publication at the end.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file

from .artifacts import validate_render_result
from .contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    FinalizeRequest,
    FinalizerResolution,
    FrameWindow,
    PlannerResolution,
    RenderPlan,
    RenderRequest,
    RenderResult,
    RendererResolution,
    RenderSegment,
    SupportReport,
    compute_request_digest,
)
from .errors import (
    RendererException,
    raise_internal_error,
    raise_invalid_artifact_error,
    raise_protocol_error,
    raise_renderer_error,
    raise_unsupported_error,
)
from .provenance import assemble_provenance_v2
from .publication import publish_render_result
from .registry import (
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
    RenderingCandidate,
    RenderingRegistryError,
    load_default_registries,
)
from .transport import CommandTransport


_QUALIFIED_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$"
)
_CORE_BACKEND_ID = "astrid.core"
_DIRECT_PLANNER_ID = "astrid.direct"
_DIRECT_PLANNER_DIGEST = hashlib.sha256(b"astrid.direct/v1").hexdigest()
_DIRECT_FINALIZER_ID = "astrid.direct-finalizer"
_DIRECT_FINALIZER_DIGEST = hashlib.sha256(
    b"astrid.direct-finalizer/v1"
).hexdigest()

CapabilityKind = Literal["renderer", "planner", "finalizer"]
StageObserver = Callable[[str, Mapping[str, Any]], None]
AudioCompleter = Callable[..., RenderResult]


class LegacyRenderRoutingWarning(UserWarning):
    """A legacy selector selected a different qualified backend."""


@dataclass(frozen=True)
class _SelectionPolicy:
    requested: str
    kind: Literal["renderer", "planner"]
    targets: tuple[str, ...]
    auto_route: bool = False


@dataclass(frozen=True)
class _ResolvedCapability:
    candidate: RenderingCandidate[Any]
    evidence: dict[str, Any]
    support: SupportReport


def _translate_legacy_selector(selector: str | None) -> _SelectionPolicy:
    """Translate the three historical names, and no other short names.

    The ordered pair for legacy ``remotion`` is its characterized compatibility
    policy: request-sensitive FFmpeg support gets the first opportunity, then
    Remotion.  Qualified selectors contain no fallback and are therefore
    strict (normal registry aliases and overrides still apply).
    """

    if selector is None:
        selector = "remotion"
    if selector == "ffmpeg":
        return _SelectionPolicy(selector, "renderer", ("rendering.ffmpeg",))
    if selector == "remotion":
        return _SelectionPolicy(
            selector,
            "renderer",
            ("rendering.ffmpeg", "rendering.remotion"),
            auto_route=True,
        )
    if selector == "hybrid":
        return _SelectionPolicy(
            selector,
            "planner",
            ("rendering.legacy_hybrid",),
        )
    if isinstance(selector, str) and _QUALIFIED_ID_RE.fullmatch(selector):
        return _SelectionPolicy(selector, "renderer", (selector,))
    raise_unsupported_error(
        backend=_CORE_BACKEND_ID,
        message=f"unknown renderer selector {selector!r}",
        recovery_command=(
            "select a qualified renderer id or one of the legacy selectors: "
            "remotion, ffmpeg, hybrid"
        ),
        details={
            "selector": selector if isinstance(selector, str) else repr(selector),
            "legacy_selectors": ["remotion", "ffmpeg", "hybrid"],
        },
    )


class RenderService:
    """Resolve, invoke, validate, finalize, and publish one timeline render.

    Registries and lifecycle functions are injectable so callers can embed the
    service without importing backend code, and so the orchestration order can
    be tested without spawning media tools.
    """

    def __init__(
        self,
        renderer_registry: RendererRegistry | None = None,
        planner_registry: PlannerRegistry | None = None,
        finalizer_registry: FinalizerRegistry | None = None,
        *,
        registries: tuple[
            RendererRegistry, PlannerRegistry, FinalizerRegistry
        ]
        | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        transport: Any | None = None,
        transport_factory: Callable[[str], Any] = CommandTransport,
        validator: Callable[..., RenderResult] = validate_render_result,
        publisher: Callable[..., Path] = publish_render_result,
        provenance_builder: Callable[..., dict[str, Any]] = assemble_provenance_v2,
        audio_completer: AudioCompleter | None = None,
        stage_observer: StageObserver | None = None,
        finalizer_id: str | None = None,
    ) -> None:
        supplied = (
            renderer_registry,
            planner_registry,
            finalizer_registry,
        )
        if registries is not None and any(item is not None for item in supplied):
            raise ValueError(
                "pass either registries= or individual rendering registries, not both"
            )
        if registries is None:
            if all(item is None for item in supplied):
                registries = load_default_registries(
                    project_root,
                    extra_pack_roots=extra_pack_roots,
                    include_installed=include_installed,
                )
            elif any(item is None for item in supplied):
                raise ValueError("all three rendering registries must be supplied together")
            else:
                registries = supplied  # type: ignore[assignment]
        self.renderers, self.planners, self.finalizers = registries
        self.renderer_registry = self.renderers
        self.planner_registry = self.planners
        self.finalizer_registry = self.finalizers
        self._transport = transport
        self._transport_factory = transport_factory
        self._validator = validator
        self._publisher = publisher
        self._provenance_builder = provenance_builder
        self._audio_completer = audio_completer
        self._stage_observer = stage_observer
        # Direct renders need no executable finalizer.  An embedding host may
        # nevertheless request a registered finalizer identity for direct-plan
        # provenance; otherwise a core no-op resolution is recorded.  Planned
        # renders always use the finalizer pinned by their RenderPlan.
        self.finalizer_id = finalizer_id

    def render(
        self,
        request: RenderRequest | Mapping[str, Any] | str | Path,
        assets_path: str | Path | None = None,
        out_path: str | Path | None = None,
        *,
        selector: str | None = None,
        engine: str | None = None,
        backend: str | None = None,
        output_path: str | Path | None = None,
        sidecar_path: str | Path | None = None,
        backend_config: Mapping[str, Mapping[str, Any]] | None = None,
        audio: AudioOwnership | str | None = None,
        audio: AudioOwnership | str | None = None,
        metadata: Mapping[str, str] | None = None,
        previous_outputs: Iterable[object] = (),
        v1_compatibility: Mapping[str, Any] | None = None,
    ) -> Path:
        """Render either a wire request or a timeline/assets path pair.

        For a wire request, the second positional argument may be the output
        path.  The path-pair form is a compatibility convenience used by the
        facade while it migrates to constructing :class:`RenderRequest`
        directly.
        """

        selected = self._one_selector(selector, engine, backend)
        destination = output_path or out_path
        if isinstance(request, (RenderRequest, Mapping)):
            if destination is None and assets_path is not None:
                destination = assets_path
                assets_path = None
            parsed = (
                request
                if isinstance(request, RenderRequest)
                else RenderRequest.from_dict(request)
            )
        else:
            if destination is None:
                raise_protocol_error(
                    backend=_CORE_BACKEND_ID,
                    message="out_path/output_path is required",
                    recovery_command="supply one output path and retry",
                )
            destination_path = Path(destination)
            parsed = RenderRequest.from_dict(
                {
                    "schema_version": SCHEMA_VERSION,
                    "timeline_path": str(Path(request).expanduser().resolve()),
                    "assets_registry_path": (
                        None
                        if assets_path is None
                        else str(Path(assets_path).expanduser().resolve())
                    ),
                    "output_name": destination_path.name,
                    "window": None,
                    "audio": (
                        audio.value if isinstance(audio, AudioOwnership) else audio
                    ),
                    "profile": None,
                    "backend_config": {
                        str(key): dict(value)
                        for key, value in (backend_config or {}).items()
                    },
                    "metadata": dict(metadata or {}),
                }
            )
        if destination is None:
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message="out_path/output_path is required",
                recovery_command="supply one output path and retry",
            )
        return self.render_request(
            parsed,
            selector=selected,
            out_path=destination,
            sidecar_path=sidecar_path,
            previous_outputs=previous_outputs,
            v1_compatibility=v1_compatibility,
        )

    def render_request(
        self,
        request: RenderRequest | Mapping[str, Any],
        *,
        selector: str | None = None,
        out_path: str | Path,
        sidecar_path: str | Path | None = None,
        previous_outputs: Iterable[object] = (),
        v1_compatibility: Mapping[str, Any] | None = None,
    ) -> Path:
        """Execute the frozen selection lifecycle for one protocol request."""

        try:
            parsed = (
                request
                if isinstance(request, RenderRequest)
                else RenderRequest.from_dict(request)
            )
            localized = self._absolute_input_paths(parsed)
            # Keep the caller's absolute-but-unresolved spellings for the
            # publication layer's symlink guard.  The private workspace uses
            # the resolved parent so its final move stays on the destination
            # filesystem.
            output = Path(out_path).expanduser().absolute()
            sidecar = Path(
                sidecar_path or f"{output}.provenance.json"
            ).expanduser().absolute()
            if sidecar == output:
                raise_protocol_error(
                    backend=_CORE_BACKEND_ID,
                    message="video and provenance sidecar paths must be different",
                    recovery_command="choose a distinct .provenance.json sidecar path",
                    details={"path": str(output)},
                )
            policy = _translate_legacy_selector(selector)
            self._observe(
                "legacy_translation",
                requested=selector,
                kind=policy.kind,
                targets=list(policy.targets),
                auto_route=policy.auto_route,
            )
            workspace_parent = output.resolve(strict=False).parent
            workspace_parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(
                prefix=f".{output.name}.render-service-",
                dir=str(workspace_parent),
            ) as workspace_text:
                return self._render_in_workspace(
                    localized,
                    policy=policy,
                    workspace=Path(workspace_text),
                    out_path=output,
                    sidecar_path=sidecar,
                    previous_outputs=tuple(previous_outputs),
                    v1_compatibility=v1_compatibility,
                )
        except RendererException as exc:
            if exc.error.recovery_command is None:
                raise_renderer_error(
                    replace(
                        exc.error,
                        recovery_command=self._default_error_recovery(
                            exc.error.kind
                        ),
                    )
                )
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except (TypeError, ValueError) as exc:
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message=f"render service received invalid data: {exc}",
                details={"error_type": type(exc).__name__},
            )
        except BaseException as exc:
            raise_internal_error(
                backend=_CORE_BACKEND_ID,
                message=f"render service failed: {exc or type(exc).__name__}",
                recovery_command="retry the render in a fresh invocation workspace",
                details={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _one_selector(
        selector: str | None,
        engine: str | None,
        backend: str | None,
    ) -> str | None:
        supplied = [item for item in (selector, engine, backend) if item is not None]
        if not supplied:
            return None
        if len(set(supplied)) != 1:
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message="selector, engine, and backend disagree",
                recovery_command="supply one renderer selector spelling and retry",
                details={"selectors": supplied},
            )
        return supplied[0]

    @staticmethod
    def _absolute_input_paths(request: RenderRequest) -> RenderRequest:
        timeline = Path(request.timeline_path).expanduser()
        assets = (
            None
            if request.assets_registry_path is None
            else Path(request.assets_registry_path).expanduser()
        )
        return replace(
            request,
            timeline_path=str(timeline.resolve(strict=False)),
            assets_registry_path=(
                None if assets is None else str(assets.resolve(strict=False))
            ),
        )

    def _render_in_workspace(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        workspace: Path,
        out_path: Path,
        sidecar_path: Path,
        previous_outputs: tuple[object, ...],
        v1_compatibility: Mapping[str, Any] | None,
    ) -> Path:
        selected = self._select(request, policy=policy, workspace=workspace)
        if policy.kind == "planner":
            plan, segment_results, pinned_finalizer = self._execute_planner(
                request,
                policy=policy,
                selected=selected,
                workspace=workspace,
            )
            if not segment_results:
                raise_unsupported_error(
                    backend=selected.candidate.id,
                    message="render planner produced no video segments",
                    recovery_command="use a non-empty timeline or select a direct renderer",
                    details={"total_frames": plan.total_frames},
                )
            final_result, plan = self._finish_plan(
                request,
                plan=plan,
                segment_results=segment_results,
                pinned_finalizer=pinned_finalizer,
                workspace=workspace,
            )
            artifact_lineage = [item.video for item in segment_results]
            compatibility_results = segment_results
            fragment_results = (
                segment_results
                if len(segment_results) == 1
                else [*segment_results, final_result]
            )
        else:
            final_result = self._invoke_renderer(
                request,
                selected=selected,
                workspace=workspace,
                output_name=request.output_name,
                expected_profile=request.profile,
            )
            plan = self._direct_plan(
                request,
                selected=selected,
                result=final_result,
                requested_policy=policy.requested,
            )
            final_result = self.complete_audio(
                final_result,
                request=request,
                plan=plan,
                workspace=workspace,
                backend=selected.candidate.id,
            )
            if final_result.video.profile != plan.profile or (
                final_result.video.duration_frames
                != (
                    plan.window.duration_frames
                    if plan.window is not None
                    else plan.total_frames
                )
            ):
                plan = self._direct_plan(
                    request,
                    selected=selected,
                    result=final_result,
                    requested_policy=policy.requested,
            )
            artifact_lineage = [final_result.video]
            compatibility_results = [final_result]
            fragment_results = [final_result]

        source_video = self._artifact_path(final_result, workspace)
        compatibility = self._v1_compatibility(
            compatibility_results,
            supplied=v1_compatibility,
        )
        fragments = self._merge_backend_fragments(fragment_results)
        provenance = self._provenance_builder(
            engine=policy.requested,
            output=out_path,
            timeline=request.timeline_path,
            assets_registry=request.assets_registry_path,
            plan=plan,
            artifact_profiles=artifact_lineage,
            audio_ownership=final_result.audio_ownership,
            normalization=final_result.normalization,
            attachments=final_result.attachments,
            backend_fragments=fragments,
            v1_compatibility=compatibility,
        )
        self._observe(
            "publish",
            backend=(
                plan.planner.id if policy.kind == "planner" else selected.candidate.id
            ),
            output=str(out_path),
            sidecar=str(sidecar_path),
        )
        published = self._publisher(
            source_video,
            provenance,
            out_path=out_path,
            sidecar_path=sidecar_path,
            previous_outputs=previous_outputs,
        )
        return Path(published)

    def _select(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        workspace: Path,
    ) -> _ResolvedCapability:
        registry: RendererRegistry | PlannerRegistry = (
            self.renderers if policy.kind == "renderer" else self.planners
        )
        rejected: list[dict[str, Any]] = []
        for index, target in enumerate(policy.targets):
            try:
                candidate, evidence = self._resolve_candidate(
                    registry,
                    target,
                    kind=policy.kind,
                )
                report = self._support(
                    candidate,
                    request=request,
                    workspace=workspace,
                    registry=registry,
                )
            except RendererException as exc:
                if not policy.auto_route or index == len(policy.targets) - 1:
                    raise
                if exc.error.kind not in {"unsupported", "binary_missing"}:
                    raise
                rejected.append(exc.error.to_dict())
                continue
            if not report.supported:
                rejected.append(report.to_dict())
                if policy.auto_route and index < len(policy.targets) - 1:
                    continue
                self._unsupported_report(report, registry=registry)
            if policy.auto_route and index == 0:
                warnings.warn(
                    f"legacy selector {policy.requested!r} auto-routed this supported "
                    f"timeline to {candidate.id}; select a qualified renderer "
                    "id for strict routing",
                    LegacyRenderRoutingWarning,
                    stacklevel=4,
                )
            return _ResolvedCapability(candidate, evidence, report)

        alternatives = self._alternatives(registry)
        raise_unsupported_error(
            backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
            message=f"no renderer supports legacy selector {policy.requested!r}",
            recovery_command=self._recovery_for(alternatives),
            details={"attempts": rejected, "alternatives": alternatives},
        )

    def _resolve_candidate(
        self,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
        requested_id: str,
        *,
        kind: CapabilityKind,
        observe: bool = True,
    ) -> tuple[RenderingCandidate[Any], dict[str, Any]]:
        try:
            candidate = registry.get(requested_id)
            evidence = registry.resolve_evidence(requested_id)
        except RenderingRegistryError as exc:
            evidence: dict[str, Any] = {}
            try:
                evidence = registry.resolve_evidence(requested_id)
            except RenderingRegistryError:
                evidence = dict(exc.details)
            if observe:
                self._observe_resolution(requested_id, evidence, candidate=None)
            alternatives = self._alternatives(registry)
            details = {
                "registry_error": exc.to_dict(),
                "alternatives": alternatives,
            }
            raise_unsupported_error(
                backend=(
                    requested_id
                    if _QUALIFIED_ID_RE.fullmatch(requested_id)
                    else _CORE_BACKEND_ID
                ),
                message=str(exc),
                recovery_command=self._recovery_for(alternatives),
                details=details,
            )
        if observe:
            self._observe_resolution(requested_id, evidence, candidate=candidate)
        if (
            evidence.get("resolved_id") != candidate.id
            or evidence.get("manifest_digest") != candidate.manifest_digest
            or evidence.get("priority_index", evidence.get("priority"))
            != candidate.priority_index
        ):
            raise_internal_error(
                backend=_CORE_BACKEND_ID,
                message=(
                message=(
                    f"{kind} registry changed while resolving {requested_id!r}"
                ),
                recovery_command="retry after renderer registry updates have completed",
                details={
                    "requested_id": requested_id,
                    "candidate": candidate.to_dict(),
                    "resolution_evidence": evidence,
                },
            )
        if not candidate.execution_eligible:
            alternatives = self._alternatives(registry)
            raise_unsupported_error(
                backend=candidate.id,
                message=f"{kind} {candidate.id!r} is not execution-eligible",
                recovery_command=self._recovery_for(alternatives),
                details={
                    "eligibility": candidate.eligibility.to_dict(),
                    "alternatives": alternatives,
                },
            )
        return candidate, evidence

    def _observe_resolution(
        self,
        requested_id: str,
        evidence: Mapping[str, Any],
        *,
        candidate: RenderingCandidate[Any] | None,
    ) -> None:
        alias_chain = list(evidence.get("alias_chain") or [])
        self._observe(
            "alias",
            requested_id=requested_id,
            canonical_id=evidence.get("canonical_id", requested_id),
            alias_chain=alias_chain,
        )
        self._observe(
            "override",
            requested_id=requested_id,
            override=evidence.get("override"),
        )
        self._observe(
            "winner",
            requested_id=requested_id,
            resolved_id=(
                candidate.id if candidate is not None else evidence.get("resolved_id")
            ),
            priority=evidence.get("priority_index", evidence.get("priority")),
        )
        eligibility = (
            candidate.eligibility.to_dict()
            if candidate is not None
            else evidence.get("eligibility", {})
        )
        self._observe(
            "eligibility",
            requested_id=requested_id,
            eligible=(
                candidate.execution_eligible
                if candidate is not None
                else evidence.get("execution_eligible", evidence.get("eligible", False))
            ),
            evidence=eligibility,
        )

    def _support(
        self,
        candidate: RenderingCandidate[Any],
        *,
        request: RenderRequest,
        workspace: Path,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
    ) -> SupportReport:
        manifest = candidate.manifest
        projected = request.for_backend(candidate.id)
        self._observe("support", backend=candidate.id)
        if "support" in manifest.operations:
            response = self._run_command(
                candidate,
                "support",
                projected,
                workspace=workspace,
                required_binaries=(),
            )
            if not isinstance(response, SupportReport):
                raise_protocol_error(
                    backend=candidate.id,
                    message="support operation did not return a SupportReport",
                    details={"received_type": type(response).__name__},
                )
            if response.backend != candidate.id:
                raise_protocol_error(
                    backend=candidate.id,
                    message="support report names a different backend",
                    details={"reported_backend": response.backend},
                )
            if response.backend_version != candidate.manifest.version:
                raise_protocol_error(
                    backend=candidate.id,
                    message="support report version does not match its manifest",
                    recovery_command="update the backend command and manifest as one versioned unit",
                    details={
                        "reported_version": response.backend_version,
                        "manifest_version": candidate.manifest.version,
                    },
                )
            return response
        return self._static_support(candidate, projected, registry=registry)

    def _static_support(
        self,
        candidate: RenderingCandidate[Any],
        request: RenderRequest,
        *,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
    ) -> SupportReport:
        capabilities = candidate.manifest.capabilities
        reasons: list[str] = []
        if isinstance(registry, RendererRegistry):
            support_key = (
                "supports_windows"
                if request.window is not None
                else "supports_full_timeline"
            )
            if capabilities.get(support_key) is not True:
                mode = "frame windows" if request.window is not None else "full timelines"
                reasons.append(
                    f"renderer does not declare static support for {mode}"
                )

            ownership = capabilities.get("audio_ownership")
            if request.audio is not None:
                if not isinstance(ownership, list):
                    reasons.append(
                        "renderer does not declare static audio ownership support"
                    )
                elif request.audio.value not in ownership:
                    reasons.append(
                        f"audio ownership {request.audio.value!r} is not statically supported"
                    )

            if request.profile is not None:
                profiles = capabilities.get("output_profiles")
                expected_profiles = {
                    request.profile.container,
                    f"video/{request.profile.container}",
                }
                if not isinstance(profiles, list):
                    reasons.append("renderer does not declare static output profiles")
                elif expected_profiles.isdisjoint(profiles):
                    reasons.append(
                        f"output container {request.profile.container!r} is not statically supported"
                    )

            reasons.extend(self._static_timeline_reasons(capabilities, request))
        elif isinstance(registry, PlannerRegistry):
            if not capabilities:
                reasons.append("planner does not declare static capability evidence")
        else:
            containers = capabilities.get("containers")
            if request.profile is not None:
                if not isinstance(containers, list):
                    reasons.append("finalizer does not declare static containers")
                elif request.profile.container not in containers:
                    reasons.append(
                        f"output container {request.profile.container!r} is not statically supported"
                    )
            ownership = capabilities.get("audio_ownership")
            if request.audio is not None:
                if not isinstance(ownership, list):
                    reasons.append(
                        "finalizer does not declare static audio ownership support"
                    )
                elif request.audio.value not in ownership:
                    reasons.append(
                        f"audio ownership {request.audio.value!r} is not statically supported"
                    )
            if capabilities.get("preserves_attachments") is not True:
                reasons.append("finalizer does not declare attachment preservation")
        alternatives = self._alternatives(registry, exclude=candidate.id) if reasons else []
        return SupportReport(
            schema_version=SCHEMA_VERSION,
            supported=not reasons,
            reasons=reasons,
            features={
                str(key): value
                for key, value in capabilities.get("features", {}).items()
                if isinstance(value, (bool, str))
            },
            alternatives=alternatives,
            backend=candidate.id,
            backend_version=candidate.manifest.version,
        )

    @staticmethod
    def _static_timeline_reasons(
        capabilities: Mapping[str, Any], request: RenderRequest
    ) -> list[str]:
        """Compare coarse renderer declarations with the concrete timeline.

        A renderer without a ``support`` verb has only its manifest as
        evidence, so omitted declarations are unknown and therefore fail
        closed when the request actually exercises them.
        """

        try:
            payload = json.loads(Path(request.timeline_path).read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise TypeError("timeline must contain a JSON object")
            raw_clips = payload.get("clips", [])
            raw_tracks = payload.get("tracks", [])
            if not isinstance(raw_clips, list) or not isinstance(raw_tracks, list):
                raise TypeError("timeline clips and tracks must be arrays")
            clip_types = {
                str(item.get("clipType", "media"))
                for item in raw_clips
                if isinstance(item, Mapping)
            }
            track_types = {
                str(item.get("kind"))
                for item in raw_tracks
                if isinstance(item, Mapping) and item.get("kind") is not None
            }
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return [f"timeline cannot be evaluated against static support: {exc}"]

        reasons: list[str] = []
        declared_clips = capabilities.get("clip_types")
        if clip_types:
            if not isinstance(declared_clips, list):
                reasons.append("renderer does not declare static clip types")
            else:
                missing = sorted(clip_types - set(declared_clips))
                if missing:
                    reasons.append(
                        "timeline uses statically unsupported clip types: "
                        + ", ".join(missing)
                    )
        declared_tracks = capabilities.get("track_types")
        if track_types:
            if not isinstance(declared_tracks, list):
                reasons.append("renderer does not declare static track types")
            else:
                missing = sorted(track_types - set(declared_tracks))
                if missing:
                    reasons.append(
                        "timeline uses statically unsupported track types: "
                        + ", ".join(missing)
                    )
        return reasons

    def _unsupported_report(
        self,
        report: SupportReport,
        *,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
    ) -> None:
        alternatives = list(report.alternatives) or self._alternatives(
            registry, exclude=report.backend
        )
        raise_unsupported_error(
            backend=report.backend,
            message=f"{report.backend} does not support this render request",
            recovery_command=self._recovery_for(alternatives),
            details={
                "reasons": list(report.reasons),
                "features": dict(report.features),
                "alternatives": alternatives,
            },
        )

    def _invoke_renderer(
        self,
        request: RenderRequest,
        *,
        selected: _ResolvedCapability,
        workspace: Path,
        output_name: str,
        expected_profile: Any,
    ) -> RenderResult:
        backend_request = replace(request, output_name=output_name).for_backend(
            selected.candidate.id
        )
        self._observe("invoke", backend=selected.candidate.id, verb="render")
        response = self._run_command(
            selected.candidate,
            "render",
            backend_request,
            workspace=workspace,
        )
        if not isinstance(response, RenderResult):
            raise_protocol_error(
                backend=selected.candidate.id,
                message="render operation did not return a RenderResult",
                details={"received_type": type(response).__name__},
            )
        # A null request profile deliberately leaves the backend's output
        # profile open (the DTO contract permits this).  Validation still
        # recomputes hashes, probes the media, and checks the probe against the
        # declared profile.  Planned renders are subsequently checked or
        # normalized against their canonical plan profile in _finish_plan.
        expected = expected_profile or response.video.profile
        self._observe("validate", backend=selected.candidate.id)
        return self._validator(
            response,
            expected_profile=expected,
            workspace_root=workspace,
        )

    def _segment_request(
        self,
        request: RenderRequest,
        *,
        candidate: RenderingCandidate[Any],
        segment: RenderSegment,
        index: int,
        workspace: Path,
    ) -> tuple[RenderRequest, dict[str, str]]:
        """Adapt a planned window for full-timeline-only renderers.

        Window-aware third-party renderers receive the canonical ``window``
        field unchanged.  A renderer that explicitly declares
        ``supports_windows: false`` receives an invocation-private sliced
        timeline and a null window, preserving the behavior of Astrid's
        existing full-timeline backends without teaching the service any
        concrete backend identities.
        """

        if candidate.manifest.capabilities.get("supports_windows") is not False:
            return request, {}
        timeline_path = Path(request.timeline_path)
        try:
            timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise_protocol_error(
                backend=candidate.id,
                message=f"cannot materialize planned timeline window: {exc}",
                recovery_command="repair the timeline JSON and retry the planned render",
                details={"timeline_path": str(timeline_path)},
            )
        if not isinstance(timeline_data, Mapping):
            raise_protocol_error(
                backend=candidate.id,
                message="cannot materialize a window from a non-object timeline",
                recovery_command="write the timeline as a JSON object and retry",
                details={"timeline_path": str(timeline_path)},
            )
        materialized = self._window_timeline(timeline_data, segment.window)
        materialized_path = (
            workspace / "segment-inputs" / f"{index:04d}-timeline.json"
        )
        write_json_atomic(materialized_path, materialized)
        return (
            replace(request, timeline_path=str(materialized_path), window=None),
            {"materialized_timeline": sha256_file(materialized_path)},
        )

    @classmethod
    def _window_timeline(
        cls,
        timeline_data: Mapping[str, Any],
        window: FrameWindow,
    ) -> dict[str, Any]:
        fps = Fraction(*window.fps_rational)
        start = Fraction(window.start_frame, 1) / fps
        end = Fraction(window.end_frame, 1) / fps
        raw_clips = timeline_data.get("clips", [])
        raw_tracks = timeline_data.get("tracks", [])
        if not isinstance(raw_clips, list) or not isinstance(raw_tracks, list):
            raise ValueError("timeline clips and tracks must be arrays")

        clips: list[dict[str, Any]] = []
        for raw_clip in raw_clips:
            if not isinstance(raw_clip, Mapping):
                raise TypeError("timeline clips must contain objects")
            clipped = cls._window_clip(raw_clip, start=start, end=end, window=window)
            if clipped is not None:
                clips.append(clipped)
        used_tracks = {clip.get("track") for clip in clips}
        tracks = [
            dict(track)
            for track in raw_tracks
            if isinstance(track, Mapping) and track.get("id") in used_tracks
        ]
        metadata = timeline_data.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        result = dict(timeline_data)
        result["tracks"] = tracks
        result["clips"] = clips
        result["metadata"] = {
            **dict(metadata),
            "source_window_start_seconds": float(start),
            "source_window_end_seconds": float(end),
            "duration_seconds": float(end - start),
        }
        return result

    @classmethod
    def _window_clip(
        cls,
        clip: Mapping[str, Any],
        *,
        start: Fraction,
        end: Fraction,
        window: FrameWindow,
    ) -> dict[str, Any] | None:
        clip_start = cls._timeline_number(clip.get("at", 0), "clip.at")
        clip_end = cls._clip_end(clip, clip_start=clip_start)
        visible_start = max(clip_start, start)
        visible_end = min(clip_end, end)
        if visible_end <= visible_start:
            return None

        result = dict(clip)
        result["at"] = float(visible_start - start)
        result["id"] = (
            f"{clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
        )
        if clip.get("clipType", "media") == "media":

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '204,235p;590,625p' && python -m py_compile astrid/core/rendering/service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 36ms:
[Errno 1] Operation not permitted: 'astrid/core/rendering/__pycache__/service.cpython-311.pyc.4303431344'
exec
/bin/zsh -lc "sed -n '400,620p' astrid/core/rendering/service.py && sed -n '1040,1425p' astrid/core/rendering/service.py && sed -n '1425,1835p' astrid/core/rendering/service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
            request,
            timeline_path=str(timeline.resolve(strict=False)),
            assets_registry_path=(
                None if assets is None else str(assets.resolve(strict=False))
            ),
        )

    def _render_in_workspace(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        workspace: Path,
        out_path: Path,
        sidecar_path: Path,
        previous_outputs: tuple[object, ...],
        v1_compatibility: Mapping[str, Any] | None,
    ) -> Path:
        selected = self._select(request, policy=policy, workspace=workspace)
        if policy.kind == "planner":
            plan, segment_results, pinned_finalizer = self._execute_planner(
                request,
                policy=policy,
                selected=selected,
                workspace=workspace,
            )
            if not segment_results:
                raise_unsupported_error(
                    backend=selected.candidate.id,
                    message="render planner produced no video segments",
                    recovery_command="use a non-empty timeline or select a direct renderer",
                    details={"total_frames": plan.total_frames},
                )
            final_result, plan = self._finish_plan(
                request,
                plan=plan,
                segment_results=segment_results,
                pinned_finalizer=pinned_finalizer,
                workspace=workspace,
            )
            artifact_lineage = [item.video for item in segment_results]
            compatibility_results = segment_results
            fragment_results = (
                segment_results
                if len(segment_results) == 1
                else [*segment_results, final_result]
            )
        else:
            final_result = self._invoke_renderer(
                request,
                selected=selected,
                workspace=workspace,
                output_name=request.output_name,
                expected_profile=request.profile,
            )
            plan = self._direct_plan(
                request,
                selected=selected,
                result=final_result,
                requested_policy=policy.requested,
            )
            final_result = self.complete_audio(
                final_result,
                request=request,
                plan=plan,
                workspace=workspace,
                backend=selected.candidate.id,
            )
            if final_result.video.profile != plan.profile or (
                final_result.video.duration_frames
                != (
                    plan.window.duration_frames
                    if plan.window is not None
                    else plan.total_frames
                )
            ):
                plan = self._direct_plan(
                    request,
                    selected=selected,
                    result=final_result,
                    requested_policy=policy.requested,
            )
            artifact_lineage = [final_result.video]
            compatibility_results = [final_result]
            fragment_results = [final_result]

        source_video = self._artifact_path(final_result, workspace)
        compatibility = self._v1_compatibility(
            compatibility_results,
            supplied=v1_compatibility,
        )
        fragments = self._merge_backend_fragments(fragment_results)
        provenance = self._provenance_builder(
            engine=policy.requested,
            output=out_path,
            timeline=request.timeline_path,
            assets_registry=request.assets_registry_path,
            plan=plan,
            artifact_profiles=artifact_lineage,
            audio_ownership=final_result.audio_ownership,
            normalization=final_result.normalization,
            attachments=final_result.attachments,
            backend_fragments=fragments,
            v1_compatibility=compatibility,
        )
        self._observe(
            "publish",
            backend=(
                plan.planner.id if policy.kind == "planner" else selected.candidate.id
            ),
            output=str(out_path),
            sidecar=str(sidecar_path),
        )
        published = self._publisher(
            source_video,
            provenance,
            out_path=out_path,
            sidecar_path=sidecar_path,
            previous_outputs=previous_outputs,
        )
        return Path(published)

    def _select(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        workspace: Path,
    ) -> _ResolvedCapability:
        registry: RendererRegistry | PlannerRegistry = (
            self.renderers if policy.kind == "renderer" else self.planners
        )
        rejected: list[dict[str, Any]] = []
        for index, target in enumerate(policy.targets):
            try:
                candidate, evidence = self._resolve_candidate(
                    registry,
                    target,
                    kind=policy.kind,
                )
                report = self._support(
                    candidate,
                    request=request,
                    workspace=workspace,
                    registry=registry,
                )
            except RendererException as exc:
                if not policy.auto_route or index == len(policy.targets) - 1:
                    raise
                if exc.error.kind not in {"unsupported", "binary_missing"}:
                    raise
                rejected.append(exc.error.to_dict())
                continue
            if not report.supported:
                rejected.append(report.to_dict())
                if policy.auto_route and index < len(policy.targets) - 1:
                    continue
                self._unsupported_report(report, registry=registry)
            if policy.auto_route and index == 0:
                warnings.warn(
                    f"legacy selector {policy.requested!r} auto-routed this supported "
                    f"timeline to {candidate.id}; select a qualified renderer "
                    "id for strict routing",
                    LegacyRenderRoutingWarning,
                    stacklevel=4,
                )
            return _ResolvedCapability(candidate, evidence, report)

        alternatives = self._alternatives(registry)
        raise_unsupported_error(
            backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
            message=f"no renderer supports legacy selector {policy.requested!r}",
            recovery_command=self._recovery_for(alternatives),
            details={"attempts": rejected, "alternatives": alternatives},
        )

    def _resolve_candidate(
        self,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
        requested_id: str,
        *,
        kind: CapabilityKind,
        observe: bool = True,
    ) -> tuple[RenderingCandidate[Any], dict[str, Any]]:
        try:
            candidate = registry.get(requested_id)
            evidence = registry.resolve_evidence(requested_id)
        except RenderingRegistryError as exc:
            evidence: dict[str, Any] = {}
            try:
                evidence = registry.resolve_evidence(requested_id)
            except RenderingRegistryError:
                evidence = dict(exc.details)
            if observe:
                self._observe_resolution(requested_id, evidence, candidate=None)
            alternatives = self._alternatives(registry)
            details = {
                "registry_error": exc.to_dict(),
                "alternatives": alternatives,
            }
            raise_unsupported_error(
                backend=(
                    requested_id
                    if _QUALIFIED_ID_RE.fullmatch(requested_id)
                    else _CORE_BACKEND_ID
                ),
                message=str(exc),
                recovery_command=self._recovery_for(alternatives),
                details=details,
            )
        if observe:
            self._observe_resolution(requested_id, evidence, candidate=candidate)
        if (
            evidence.get("resolved_id") != candidate.id
            or evidence.get("manifest_digest") != candidate.manifest_digest
            or evidence.get("priority_index", evidence.get("priority"))
            != candidate.priority_index
        ):
            raise_internal_error(
                backend=_CORE_BACKEND_ID,
                message=(
        if clip.get("clipType", "media") == "media":
            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
            if speed <= 0:
                raise ValueError("clip.speed must be positive")
            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
            source_from += (visible_start - clip_start) * speed
            result["from"] = float(source_from)
            result["to"] = float(
                source_from + (visible_end - visible_start) * speed
            )
        elif isinstance(clip.get("hold"), (int, float)) and not isinstance(
            clip.get("hold"), bool
        ):
            result["hold"] = float(visible_end - visible_start)
        return result

    @classmethod
    def _clip_end(
        cls, clip: Mapping[str, Any], *, clip_start: Fraction
    ) -> Fraction:
        if clip.get("clipType", "media") == "media":
            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
            if "to" not in clip:
                raise ValueError("media clip must declare a source to bound")
            source_to = cls._timeline_number(clip["to"], "clip.to")
            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
            if source_from < 0 or source_to <= source_from or speed <= 0:
                raise ValueError("media clip must have positive bounds and speed")
            return clip_start + (source_to - source_from) / speed
        hold = clip.get("hold")
        if isinstance(hold, (int, float)) and not isinstance(hold, bool):
            return clip_start + max(Fraction(0), cls._timeline_number(hold, "clip.hold"))
        if isinstance(clip.get("to"), (int, float)) and not isinstance(
            clip.get("to"), bool
        ):
            return cls._timeline_number(clip["to"], "clip.to")
        return clip_start

    @staticmethod
    def _timeline_number(value: Any, label: str) -> Fraction:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{label} must be a finite number")
        if not math.isfinite(float(value)):
            raise ValueError(f"{label} must be finite")
        return Fraction(str(value))

    @staticmethod
    def _validate_segment_duration(
        result: RenderResult,
        *,
        segment: RenderSegment,
        canonical_profile: Any,
        backend: str,
    ) -> None:
        RenderService._validate_planned_duration(
            result,
            planned_frames=segment.window.duration_frames,
            canonical_profile=canonical_profile,
            backend=backend,
            label="renderer artifact",
        )

    @staticmethod
    def _validate_planned_duration(
        result: RenderResult,
        *,
        planned_frames: int,
        canonical_profile: Any,
        backend: str,
        label: str,
    ) -> None:
        artifact_seconds = Fraction(
            result.video.duration_frames, 1
        ) / Fraction(*result.video.profile.fps_rational)
        canonical_fps = Fraction(*canonical_profile.fps_rational)
        planned_seconds = Fraction(planned_frames, 1) / canonical_fps
        delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
        if delta_frames <= canonical_profile.duration_tolerance:
            return
        raise_invalid_artifact_error(
            backend=backend,
            message=f"{label} duration does not match its planned frame window",
            recovery_command="rerender the exact planned segment window and retry",
            details={
                "planned_duration_frames": planned_frames,
                "artifact_duration_frames": result.video.duration_frames,
                "canonical_delta_frames": [
                    delta_frames.numerator,
                    delta_frames.denominator,
                ],
                "tolerance_frames": canonical_profile.duration_tolerance,
            },
        )

    def _execute_planner(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        selected: _ResolvedCapability,
        workspace: Path,
    ) -> tuple[
        RenderPlan,
        list[RenderResult],
        tuple[RenderingCandidate[Any], dict[str, Any]],
    ]:
        planner_request = request.for_backend(selected.candidate.id)
        self._observe("invoke", backend=selected.candidate.id, verb="plan")
        response = self._run_command(
            selected.candidate,
            "plan",
            planner_request,
            workspace=workspace,
        )
        if not isinstance(response, RenderPlan):
            raise_protocol_error(
                backend=selected.candidate.id,
                message="plan operation did not return a RenderPlan",
                details={"received_type": type(response).__name__},
            )
        # The registry selection is authoritative.  A planner response may
        # still carry the pre-alias/pre-override identity it was asked to
        # replace (notably during compatibility routing); normalize that
        # self-description to the selected candidate and its complete
        # resolution evidence below.
        planner_resolution = self._planner_resolution(selected)
        normalized_segments: list[RenderSegment] = []
        segment_results: list[RenderResult] = []
        input_hashes = self._input_hashes(request)
        for index, segment in enumerate(response.segments):
            candidate, evidence = self._resolve_candidate(
                self.renderers,
                segment.renderer.id,
                kind="renderer",
            )
            native_request = replace(
                request,
                window=segment.window,
                output_name=f"segment-{index:04d}.mp4",
            )
            segment_request, materialized_hashes = self._segment_request(
                native_request,
                candidate=candidate,
                segment=segment,
                index=index,
                workspace=workspace,
            )
            report = self._support(
                candidate,
                request=segment_request,
                workspace=workspace,
                registry=self.renderers,
            )
            if not report.supported:
                self._unsupported_report(report, registry=self.renderers)
            resolved = _ResolvedCapability(candidate, evidence, report)
            normalized_segment = replace(
                segment,
                renderer=self._renderer_resolution(resolved),
                input_hashes={
                    **segment.input_hashes,
                    **input_hashes,
                    **materialized_hashes,
                },
            )
            normalized_segments.append(normalized_segment)
            result = self._invoke_renderer(
                segment_request,
                selected=resolved,
                workspace=workspace,
                output_name=segment_request.output_name,
                # Segment renderers may emit a profile that the registered
                # finalizer must normalize.  The artifact is first validated
                # against its own declaration; a one-segment exact match is
                # checked against the plan in _finish_plan, while every
                # mismatch and every multi-segment plan goes through the
                # pinned finalizer.
                expected_profile=None,
            )
            completed = self.complete_audio(
                result,
                request=segment_request,
                plan=response,
                workspace=workspace,
                backend=candidate.id,
                defer_to_finalizer=len(response.segments) > 1,
            )
            self._validate_segment_duration(
                completed,
                segment=segment,
                canonical_profile=response.profile,
                backend=candidate.id,
            )
            segment_results.append(completed)

        finalizer, finalizer_evidence = self._resolve_candidate(
            self.finalizers,
            response.finalizer.id,
            kind="finalizer",
            observe=False,
        )
        finalizer_resolution = self._finalizer_resolution(
            finalizer,
            finalizer_evidence,
            support=None,
        )
        plan = replace(
            response,
            request_digest=compute_request_digest(request.to_dict()),
            requested_policy=policy.requested,
            planner=planner_resolution,
            segments=normalized_segments,
            finalizer=finalizer_resolution,
        )
        return plan, segment_results, (finalizer, finalizer_evidence)

    def _finish_plan(
        self,
        request: RenderRequest,
        *,
        plan: RenderPlan,
        segment_results: list[RenderResult],
        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
        workspace: Path,
    ) -> tuple[RenderResult, RenderPlan]:
        if len(segment_results) == 1:
            result = self._validator(
                segment_results[0],
                expected_profile=plan.profile,
                workspace_root=workspace,
            )
            return result, plan

        candidate, evidence = pinned_finalizer
        ownerships = {item.audio_ownership for item in segment_results}
        if ownerships == {AudioOwnership.PASSTHROUGH}:
            requested_audio = AudioOwnership.PASSTHROUGH
        elif plan.profile.has_audio:
            requested_audio = AudioOwnership.RENDERED
        else:
            requested_audio = AudioOwnership.NONE
        support_audio = (
            None
            if requested_audio is AudioOwnership.PASSTHROUGH
            and plan.profile.has_audio
            else requested_audio
        )
        support_request = RenderRequest(
            schema_version=SCHEMA_VERSION,
            timeline_path=request.timeline_path,
            assets_registry_path=request.assets_registry_path,
            output_name=request.output_name,
            audio=support_audio,
            profile=plan.profile,
            backend_config=request.backend_config,
            metadata=request.metadata,
        )
        report = self._support(
            candidate,
            request=support_request,
            workspace=workspace,
            registry=self.finalizers,
        )
        if not report.supported:
            self._unsupported_report(report, registry=self.finalizers)
        finalizer_resolution = self._finalizer_resolution(
            candidate,
            evidence,
            support=report,
        )
        plan = replace(plan, finalizer=finalizer_resolution)
        finalize_request = FinalizeRequest(
            schema_version=SCHEMA_VERSION,
            plan=plan,
            artifacts=[item.video for item in segment_results],
            output_name=request.output_name,
            backend_config={
                candidate.id: dict(request.backend_config.get(candidate.id, {}))
            }
            if candidate.id in request.backend_config
            else {},
            metadata=request.metadata,
        )
        self._observe("finalize", backend=candidate.id)
        response = self._run_command(
            candidate,
            "finalize",
            finalize_request,
            workspace=workspace,
        )
        if not isinstance(response, RenderResult):
            raise_protocol_error(
                backend=candidate.id,
                message="finalize operation did not return a RenderResult",
                details={"received_type": type(response).__name__},
            )
        try:
            response = finalize_request.validate_final_result(response)
        except (TypeError, ValueError) as exc:
            raise_invalid_artifact_error(
                backend=candidate.id,
                message=f"finalizer returned an invalid result: {exc}",
                recovery_command="rerun finalization in a fresh invocation workspace",
                details={"error_type": type(exc).__name__},
            )
        self._observe("validate", backend=candidate.id)
        validated = self._validator(
            response,
            expected_profile=plan.profile,
            workspace_root=workspace,
        )
        self._validate_planned_duration(
            validated,
            planned_frames=(
                plan.window.duration_frames
                if plan.window is not None
                else plan.total_frames
            ),
            canonical_profile=plan.profile,
            backend=candidate.id,
            label="finalized artifact",
        )
        completed = self.complete_audio(
            validated,
            request=request,
            plan=plan,
            workspace=workspace,
            backend=candidate.id,
        )
        self._validate_planned_duration(
            completed,
            planned_frames=(
                plan.window.duration_frames
                if plan.window is not None
                else plan.total_frames
            ),
            canonical_profile=plan.profile,
            backend=candidate.id,
            label="audio-completed artifact",
        )
        return completed, plan

    def complete_audio(
        self,
        result: RenderResult,
        *,
        request: RenderRequest,
        plan: RenderPlan,
        workspace: Path,
        backend: str = _CORE_BACKEND_ID,
        defer_to_finalizer: bool = False,
    ) -> RenderResult:
        """Apply host-owned completion semantics after renderer validation.

        ``rendered`` is already complete. ``none`` is an intentional
        visual-only result, while ``passthrough`` must be completed by the
        embedding host before publication.  A configured completer may also
        apply an optional compatibility policy to ``none`` without requiring
        arbitrary renderers to synthesize silence.
        """

        self._observe("audio", ownership=result.audio_ownership.value)
        if result.audio_ownership is AudioOwnership.RENDERED:
            return result
        if result.video.profile.has_audio:
            raise_invalid_artifact_error(
                backend=backend,
                message=(
                    f"audio_ownership={result.audio_ownership.value!r} requires "
                    "a visual-only renderer artifact"
                ),
                recovery_command="rerender with an audio/profile pair that agrees",
            )
        if defer_to_finalizer:
            # A registered finalizer owns cross-segment compatibility: it may
            # synthesize silence for NONE segments or preserve a uniform set
            # of PASSTHROUGH segments.  Completion, if still necessary, runs
            # once on the finalized result below.
            return result
        if (
            result.audio_ownership is AudioOwnership.NONE
            and (
                plan.profile.has_audio
                or (
                    request.profile is not None
                    and request.profile.has_audio
                    and request.profile.has_audio
                )
            )
        ):
            raise_invalid_artifact_error(
                backend=backend,
                message="audio_ownership='none' cannot satisfy a requested audio profile",
                recovery_command="request passthrough/rendered audio or a visual-only profile",
            )
        if self._audio_completer is None:
            if result.audio_ownership is AudioOwnership.PASSTHROUGH:
                raise_unsupported_error(
                    backend=backend,
                    message=(
                        "renderer requested passthrough audio but no host audio "
                        "completer is configured"
                    ),
                    recovery_command=(
                        "configure an audio completer or select a renderer that "
                        "returns rendered audio"
                    ),
                    details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
                )
            return result
        completed = self._audio_completer(
            result,
            request=request,
            plan=plan,
            workspace=workspace,
        )
        if not isinstance(completed, RenderResult):
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message="audio completer did not return a RenderResult",
                details={"received_type": type(completed).__name__},
            )
        if (
            completed.audio_ownership is AudioOwnership.PASSTHROUGH
            or (
                result.audio_ownership is AudioOwnership.PASSTHROUGH
                and completed.audio_ownership is not AudioOwnership.RENDERED
            )
        ):
            raise_invalid_artifact_error(
                backend=backend,
                message="host audio completer left passthrough audio incomplete",
                recovery_command="return a completed rendered-audio result",
                details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
            )
        missing_attachments = sorted(
            set(result.attachments) - set(completed.attachments)
        )
        changed_attachments = sorted(
            name
            for name, attachment in result.attachments.items()
            if name in completed.attachments
            and completed.attachments[name] != attachment
        )
        if missing_attachments or changed_attachments:
            raise_invalid_artifact_error(
                backend=backend,
                message="host audio completion did not preserve renderer attachments",
                recovery_command="preserve every named attachment while completing audio",
                details={
                    "missing": missing_attachments,
                    "changed": changed_attachments,
                },
            )
        original_profile = result.video.profile.to_dict()
        completed_profile = completed.video.profile.to_dict()
        audio_fields = {
            "audio_codec",
            "audio_sample_rate",
            "audio_channel_layout",
        }
        changed_video_fields = sorted(
            key
            for key, value in original_profile.items()
            if key not in audio_fields and completed_profile.get(key) != value
        )
        if (
            changed_video_fields
            or completed.video.duration_frames != result.video.duration_frames
        ):
            raise_invalid_artifact_error(
                backend=backend,
                message="host audio completion changed the renderer's video contract",
                recovery_command="complete audio without changing video profile or duration",
                details={
                    "changed_profile_fields": changed_video_fields,
                    "before_duration_frames": result.video.duration_frames,
                    "after_duration_frames": completed.video.duration_frames,
                },
            )
        return self._validator(
            completed,
            expected_profile=completed.video.profile,
            workspace_root=workspace,
        )

    def _direct_plan(
        self,
        request: RenderRequest,
        *,
        selected: _ResolvedCapability,
        result: RenderResult,
        requested_policy: str,
    ) -> RenderPlan:
        finalizer_resolution = self._direct_finalizer_resolution()
        if request.window is not None:
            if request.window.fps_rational != result.video.profile.fps_rational:
                raise_invalid_artifact_error(
                    backend=selected.candidate.id,
                    message="renderer artifact FPS does not match the requested frame window",
                    recovery_command="render the requested window at its declared rational FPS",
                    details={
                        "window_fps": list(request.window.fps_rational),
                        "artifact_fps": list(result.video.profile.fps_rational),
                    },
                )
            segment_window = request.window
            total_frames = request.window.end_frame
            plan_window = request.window
            self._validate_planned_duration(
                result,
                planned_frames=request.window.duration_frames,
                canonical_profile=result.video.profile,
                backend=selected.candidate.id,
                label="renderer artifact",
            )
        else:
            segment_window = FrameWindow(
                start_frame=0,
                end_frame=result.video.duration_frames,
                fps_rational=result.video.profile.fps_rational,
            )
            total_frames = result.video.duration_frames
            plan_window = None
        segment = RenderSegment(
            window=segment_window,
            renderer=self._renderer_resolution(selected),
            input_hashes=self._input_hashes(request),
        )
        return RenderPlan(
            schema_version=SCHEMA_VERSION,
            request_digest=compute_request_digest(request.to_dict()),
            requested_policy=requested_policy,
            planner=PlannerResolution(
                id=_DIRECT_PLANNER_ID,
                source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
                manifest_digest=_DIRECT_PLANNER_DIGEST,
                trust_eligibility={"eligible": True, "reason": "core direct plan"},
            ),
            segments=[segment],
            finalizer=finalizer_resolution,
            profile=result.video.profile,
            total_frames=total_frames,
            reasons={"0": "direct renderer selection"},
            window=plan_window,
        )

    def _direct_finalizer_resolution(self) -> FinalizerResolution:
        if self.finalizer_id is not None:
            candidate, evidence = self._resolve_candidate(
                self.finalizers,
                self.finalizer_id,
                kind="finalizer",
                observe=False,
            )
            return self._finalizer_resolution(candidate, evidence, support=None)
        return FinalizerResolution(
            id=_DIRECT_FINALIZER_ID,
            source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
            manifest_digest=_DIRECT_FINALIZER_DIGEST,
            trust_eligibility={"eligible": True, "reason": "core direct pass-through"},
        )

    @staticmethod
    def _source_pack(
        candidate: RenderingCandidate[Any], evidence: Mapping[str, Any]
    ) -> dict[str, Any]:
        source = {
            "id": candidate.pack_id,
            "source_kind": candidate.source_kind,
            "root": str(candidate.pack_root),
            "priority_index": candidate.priority_index,
        }
        revision = candidate.eligibility.active_revision
        if revision is not None:
            source["active_revision"] = revision
        manifest_path = evidence.get("manifest_path")
        if isinstance(manifest_path, str):
            source["manifest_path"] = manifest_path
        return source

    def _renderer_resolution(
        self, selected: _ResolvedCapability
    ) -> RendererResolution:
        candidate = selected.candidate
        evidence = selected.evidence
        return RendererResolution(
            id=candidate.id,
            source_pack=self._source_pack(candidate, evidence),
            manifest_digest=candidate.manifest_digest,
            alias_chain=list(evidence.get("alias_chain") or []),
            override=evidence.get("override"),
            support_decision=selected.support,
            trust_eligibility=candidate.eligibility.to_dict(),
        )

    def _planner_resolution(
        self, selected: _ResolvedCapability
    ) -> PlannerResolution:
        candidate = selected.candidate
        evidence = selected.evidence
        return PlannerResolution(
            id=candidate.id,
            source_pack=self._source_pack(candidate, evidence),
            manifest_digest=candidate.manifest_digest,
            trust_eligibility=candidate.eligibility.to_dict(),
            alias_chain=list(evidence.get("alias_chain") or []),
            override=evidence.get("override"),
            support_decision=selected.support,
        )

    def _finalizer_resolution(
        self,
        candidate: RenderingCandidate[Any],
        evidence: Mapping[str, Any],
        *,
        support: SupportReport | None,
    ) -> FinalizerResolution:
        return FinalizerResolution(
            id=candidate.id,
            source_pack=self._source_pack(candidate, evidence),
            manifest_digest=candidate.manifest_digest,
            trust_eligibility=candidate.eligibility.to_dict(),
            alias_chain=list(evidence.get("alias_chain") or []),
            override=evidence.get("override"),
            support_decision=support,
        )

    def _run_command(
        self,
        candidate: RenderingCandidate[Any],
        verb: str,
        payload: Any,
        *,
        workspace: Path,
        required_binaries: Sequence[str] | None = None,
    ) -> Any:
        token = hashlib.sha256(
            f"{candidate.id}:{verb}:{len(list(workspace.iterdir()))}".encode()
        ).hexdigest()[:12]
        request_path = workspace / f"{token}-{verb}-request.json"
        result_path = workspace / f"{token}-{verb}-result.json"
        write_json_atomic(request_path, payload.to_dict())
        transport = (
            self._transport
            if self._transport is not None
            else self._transport_factory(candidate.id)
        )
        return transport.run(
            verb,
            candidate.manifest.command,
            backend=candidate.id,
            request_path=request_path,
            result_path=result_path,
            cwd=candidate.pack_root,
            timeout=candidate.manifest.timeout_seconds,
            required_binaries=(
                candidate.manifest.required_binaries
                if required_binaries is None
                else required_binaries
            ),
        )

    @staticmethod
    def _artifact_path(result: RenderResult, workspace: Path) -> Path:
        candidate = (workspace / result.video.path).resolve(strict=False)
        try:
            candidate.relative_to(workspace.resolve())
        except ValueError:
            raise_invalid_artifact_error(
                backend=_CORE_BACKEND_ID,
                message="validated renderer artifact escaped its invocation workspace",
                recovery_command="rerun the renderer with a contained output path",
                details={"path": result.video.path},
            )
        return candidate

    @staticmethod
    def _input_hashes(request: RenderRequest) -> dict[str, str]:
        paths: dict[str, Path] = {"timeline": Path(request.timeline_path)}
        if request.assets_registry_path is not None:
            paths["assets_registry"] = Path(request.assets_registry_path)
        return {
            name: sha256_file(path)
            for name, path in paths.items()
            if path.is_file()
        }

    @staticmethod
    def _merge_backend_fragments(
        results: Sequence[RenderResult],
    ) -> dict[str, dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for result in results:
            for namespace, fragment in result.backend_fragments.items():
                current = merged.get(namespace)
                if current is None:
                    merged[namespace] = dict(fragment)
                elif current != fragment:
                    records = current.get("service_fragment_sequence")
                    if isinstance(records, list):
                        records.append(dict(fragment))
                    else:
                        merged[namespace] = {
                            "service_fragment_sequence": [current, dict(fragment)]
                        }
        return merged

    @staticmethod
    def _v1_compatibility(
        results: Sequence[RenderResult],
        *,
        supplied: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        compatibility: dict[str, Any] = {
            "project_dir": None,
            "composition_id": "TimelineComposition",
            "active_pack_order": [],
            "active_theme": None,
            "registry_hash": None,
            "registry_state": {},
            "resolved_effect_ids": [],
            "resolved_effects": [],
            "source_pack_ids": [],
            "element_roots": [],
            "staged_asset_ids": [],
            "staged_asset_root": None,
        }
        segment_provenance: list[dict[str, Any]] = []
        for result in results:
            for fragment in result.backend_fragments.values():
                legacy = fragment.get("legacy_v1")
                if not isinstance(legacy, Mapping):
                    continue
                segment_provenance.append(dict(legacy))
                for key in compatibility:
                    if key in legacy:
                        compatibility[key] = legacy[key]
                for key in (
                    "ffmpeg_specialization",
                    "audio_reactive_colour",
                ):
                    if key in legacy:
                        compatibility[key] = legacy[key]
        if len(segment_provenance) > 1:
            compatibility["segment_provenance"] = segment_provenance
        if supplied is not None:
            compatibility.update(dict(supplied))
        return compatibility

    @staticmethod
    def _alternatives(
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
        *,
        exclude: str | None = None,
    ) -> list[str]:
        try:
            return [
                candidate.id
                for candidate in registry.list()
                if candidate.id != exclude
            ]
        except RenderingRegistryError:
            return []

    @staticmethod
    def _recovery_for(alternatives: Sequence[str]) -> str:
        if alternatives:
            return "select one of these alternatives and retry: " + ", ".join(
                alternatives
            )
        return "install or select an execution-eligible compatible capability and retry"

    @staticmethod
    def _default_error_recovery(kind: str) -> str:
        return {
            "protocol": "regenerate the request with renderer protocol v1",
            "unsupported": "select a compatible renderer and retry",
            "binary_missing": "install the renderer's required binaries and retry",
            "timeout": "retry the render or increase the renderer timeout",
            "interrupted": "retry the render when interruption is no longer requested",
            "invalid_artifact": "rerender the artifact in a fresh invocation workspace",
            "internal": "retry the render in a fresh invocation workspace",
        }.get(kind, "retry the render after resolving the reported failure")

    def _observe(self, stage: str, **details: Any) -> None:
        if self._stage_observer is not None:
            self._stage_observer(stage, details)


__all__ = ["LegacyRenderRoutingWarning", "RenderService"]

exec
/bin/zsh -lc "rg -n \"class FinalizeRequest|class RenderResult|attachments\" astrid/core/rendering/contracts.py astrid/packs/rendering/finalizers/ffmpeg/run.py tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py | head -n 220 && sed -n '640,850p' astrid/core/rendering/contracts.py && sed -n '1,220p' astrid/core/rendering/provenance.py && sed -n '397,490p' astrid/core/rendering/provenance.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_service.py:139:                {"preserves_attachments": True}
tests/core/rendering/test_service.py:237:    att_dir = workspace / "attachments"
tests/core/rendering/test_service.py:259:        self.render_attachments: dict[
tests/core/rendering/test_service.py:262:        self.finalize_attachments: dict[str, bytes] = {}
tests/core/rendering/test_service.py:318:            attachments: dict[str, Attachment] = {}
tests/core/rendering/test_service.py:320:                for name, descriptor in (artifact.get("attachments") or {}).items():
tests/core/rendering/test_service.py:321:                    attachments[name] = Attachment.from_dict(descriptor)
tests/core/rendering/test_service.py:322:            for name, data in self.finalize_attachments.items():
tests/core/rendering/test_service.py:323:                attachments[name] = _attachment_file(workspace, name, data)
tests/core/rendering/test_service.py:346:            raw_attachments = self.render_attachments.get(backend, {})
tests/core/rendering/test_service.py:347:            if isinstance(raw_attachments, list):
tests/core/rendering/test_service.py:349:                named = raw_attachments.pop(0) if raw_attachments else {}
tests/core/rendering/test_service.py:351:                named = raw_attachments
tests/core/rendering/test_service.py:352:            attachments = {
tests/core/rendering/test_service.py:363:            attachments=attachments,
tests/core/rendering/test_service.py:1750:def test_renderer_attachments_survive_validation_into_committed_provenance(
tests/core/rendering/test_service.py:1754:    transport.render_attachments["rendering.ffmpeg"] = {
tests/core/rendering/test_service.py:1759:    output = tmp_path / "attachments.mp4"
tests/core/rendering/test_service.py:1766:    assert set(payload["attachments"]) == {"storyboard.png", "captions.srt"}
tests/core/rendering/test_service.py:1767:    assert payload["attachments"]["storyboard.png"]["sha256"] == hashlib.sha256(
tests/core/rendering/test_service.py:1770:    assert payload["attachments"]["storyboard.png"]["kind"] == "fixture"
tests/core/rendering/test_service.py:1771:    assert payload["attachments"]["storyboard.png"]["path"].endswith(
tests/core/rendering/test_service.py:1775:    assert set(payload["artifact_profiles"][0]["attachments"]) == {
tests/core/rendering/test_service.py:1781:def test_finalizer_preserves_segment_attachments_and_adds_its_own(
tests/core/rendering/test_service.py:1785:    transport.render_attachments["fixture.window"] = [
tests/core/rendering/test_service.py:1789:    transport.finalize_attachments = {"final-note.txt": b"final"}
tests/core/rendering/test_service.py:1797:    output = tmp_path / "finalized-attachments.mp4"
tests/core/rendering/test_service.py:1802:    assert set(payload["attachments"]) == {
tests/core/rendering/test_service.py:1808:    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
tests/core/rendering/test_service.py:1809:    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}
tests/core/rendering/test_service.py:1812:def test_audio_completer_dropping_attachments_is_rejected(tmp_path: Path) -> None:
tests/core/rendering/test_service.py:1814:    transport.render_attachments["rendering.ffmpeg"] = {"must-survive.txt": b"x"}
tests/core/rendering/test_service.py:1823:                attachments={},
tests/core/rendering/test_service.py:1829:    output = tmp_path / "dropped-attachments.mp4"
tests/core/rendering/test_service.py:1831:    with pytest.raises(RendererInvalidArtifactError, match="attachments"):
astrid/core/rendering/contracts.py:78:        "attachments",
astrid/core/rendering/contracts.py:675:    attachments: dict[str, Attachment] = field(default_factory=dict)
astrid/core/rendering/contracts.py:696:            "attachments",
astrid/core/rendering/contracts.py:697:            _coerce_attachment_mapping(self.attachments, "video attachments"),
astrid/core/rendering/contracts.py:708:                "attachments": self.attachments,
astrid/core/rendering/contracts.py:716:        allowed = required | {"audio", "attachments"}
astrid/core/rendering/contracts.py:724:            attachments=data.get("attachments", {}),
astrid/core/rendering/contracts.py:736:        attachments: Mapping[str, Attachment] | None = None,
astrid/core/rendering/contracts.py:745:            attachments=dict(attachments or {}),
astrid/core/rendering/contracts.py:1530:class RenderResult:
astrid/core/rendering/contracts.py:1568:    def attachments(self) -> dict[str, Attachment]:
astrid/core/rendering/contracts.py:1571:        return self.video.attachments
astrid/core/rendering/contracts.py:1705:class FinalizeRequest:
astrid/core/rendering/contracts.py:1736:            duplicates = sorted(attachment_names & set(artifact.attachments))
astrid/core/rendering/contracts.py:1742:            attachment_names.update(artifact.attachments)
astrid/core/rendering/contracts.py:1764:    def expected_attachments(self) -> dict[str, Attachment]:
astrid/core/rendering/contracts.py:1765:        """Return the globally unique attachments a finalizer must preserve."""
astrid/core/rendering/contracts.py:1770:            for name, attachment in artifact.attachments.items()
astrid/core/rendering/contracts.py:1779:        Finalizers may add new attachments, but every input attachment must be
astrid/core/rendering/contracts.py:1788:        missing = sorted(set(self.expected_attachments) - set(final_result.attachments))
astrid/core/rendering/contracts.py:1790:            raise ValueError("finalizer dropped attachments: " + ", ".join(missing))
astrid/core/rendering/contracts.py:1793:            for name, expected in self.expected_attachments.items()
astrid/core/rendering/contracts.py:1794:            if final_result.attachments[name] != expected
astrid/core/rendering/contracts.py:1797:            raise ValueError("finalizer changed attachments: " + ", ".join(changed))
astrid/core/rendering/contracts.py:2141:                {"containers", "preserves_attachments", "audio_ownership", "features"}
astrid/core/rendering/contracts.py:2147:        if "preserves_attachments" in capabilities:
astrid/core/rendering/contracts.py:2148:            result["preserves_attachments"] = _manifest_boolean(
astrid/core/rendering/contracts.py:2149:                capabilities["preserves_attachments"],
astrid/core/rendering/contracts.py:2150:                "preserves_attachments",
astrid/packs/rendering/finalizers/ffmpeg/run.py:1009:            "preserves_attachments": True,
astrid/packs/rendering/finalizers/ffmpeg/run.py:1349:            attachments=request.expected_attachments,
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
"""Core-owned provenance v2 assembly for timeline renders."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file

from .contracts import (
    PROVENANCE_V1_ALWAYS_KEYS,
    PROVENANCE_V1_COMPATIBILITY_KEYS,
    PROVENANCE_V2_CORE_KEYS,
    _ECMA_WHITESPACE,
    Attachment,
    AudioOwnership,
    RenderPlan,
    RenderProfile,
    RenderSegment,
    VideoArtifact,
    _json_safe_mapping,
    _require_sha256,
    _require_string,
    _require_workspace_relative_path,
    _validate_backend_fragments,
)


PROVENANCE_SCHEMA_VERSION = 2
ADDITIVE_PROVENANCE_V2_CORE_KEYS = frozenset({"resolved_policy", "routing"})
CORE_OWNED_KEYS = frozenset(
    PROVENANCE_V2_CORE_KEYS
    | PROVENANCE_V1_COMPATIBILITY_KEYS
    | ADDITIVE_PROVENANCE_V2_CORE_KEYS
)


def validate_backend_fragments(
    fragments: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Validate namespaces and reject top-level core-key collisions."""

    normalized = _validate_backend_fragments(fragments or {})
    for namespace, fragment in normalized.items():
        conflicts = sorted(set(fragment) & ADDITIVE_PROVENANCE_V2_CORE_KEYS)
        if conflicts:
            raise ValueError(
                f"backend fragment {namespace!r} attempts to overwrite core-owned "
                f"keys: {', '.join(conflicts)}"
            )
    return normalized


def _normalize_audio_ownership(value: AudioOwnership | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, AudioOwnership):
        return value.value
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


def _resolution_request_id(segment: RenderSegment) -> str:
    """Recover the registry id that selected one validated renderer.

    Alias chains retain their requested id first.  An override without an
    alias retains its source in ``override.from``.  Otherwise the resolved id
    was also the requested id.  This is enough to distinguish the legacy
    ``remotion`` policy's FFmpeg-first route without accepting parallel,
    caller-authored routing evidence.
    """

    renderer = segment.renderer
    if renderer.alias_chain:
        return renderer.alias_chain[0]
    if renderer.override is not None:
        return renderer.override["from"]
    return renderer.id


def _resolved_policy(plan: RenderPlan) -> dict[str, Any]:
    """Return the complete set of capability ids selected by one plan."""

    renderer_ids = list(
        dict.fromkeys(segment.renderer.id for segment in plan.segments)
    )
    return {
        "planner": plan.planner.id,
        "renderers": renderer_ids,
        "finalizer": plan.finalizer.id,
    }


def _routing_record(
    legacy_engine: str,
    plan: RenderPlan,
    resolved_policy: Mapping[str, Any],
) -> dict[str, Any]:
    """Derive selected-policy lineage and visible legacy translation.

    The service's legacy ``remotion`` policy tries the qualified FFmpeg route
    first and emits a warning when that supported route wins.  The plan pins
    the selected renderer but cannot by itself explain why its legacy
    ``engine`` projection still says ``remotion``.  Record that explanation
    additively while leaving the frozen nested resolution records authoritative
    for aliases, overrides, trust, manifests, and support decisions.
    """

    renderer_ids = list(resolved_policy["renderers"])
    resolved_backend = renderer_ids[0] if len(renderer_ids) == 1 else None
    auto_routed = (
        legacy_engine == "remotion"
        and len(plan.segments) == 1
        and _resolution_request_id(plan.segments[0]) == "rendering.ffmpeg"
    )
    auto_route_reason = None
    if auto_routed:
        auto_route_reason = (
            "legacy selector 'remotion' auto-routed the supported request to "
            f"{plan.segments[0].renderer.id}"
        )
    return {
        "requested_engine": legacy_engine,
        "requested_policy": plan.requested_policy,
        "resolved_policy": dict(resolved_policy),
        "resolved_backend": resolved_backend,
        "resolved_backends": renderer_ids,
        "auto_route": auto_routed,
        "auto_route_reason": auto_route_reason,
        "segment_reasons": dict(plan.reasons),
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
            if not isinstance(key, str):
                raise TypeError(
                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
                )
            path = _require_workspace_relative_path(key, "artifact key")
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
    resolved_policy = _resolved_policy(normalized_plan)

    payload: dict[str, Any] = {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "engine": legacy_engine,
        "output": output_path,
        "timeline": timeline_path,
        "assets_registry": assets_path,
        "request_digest": normalized_plan.request_digest,
        "requested_policy": normalized_plan.requested_policy,
        "resolved_policy": resolved_policy,
        "routing": _routing_record(
            legacy_engine,
            normalized_plan,
            resolved_policy,
        ),
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

exec
/bin/zsh -lc "sed -n '1,190p' astrid/packs/rendering/executors/render/run.py && sed -n '540,700p' astrid/packs/rendering/executors/render/run.py && sed -n '1,230p' astrid/packs/rendering/executors/render/executor.yaml && git diff C4-batch3-done..a72729db -- astrid/core/execution/executor/runner.py astrid/packs/rendering/run.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
#!/usr/bin/env python3

from __future__ import annotations

from astrid.core.pack.entrypoint import guard_canonical_entrypoint

guard_canonical_entrypoint('rendering.render')


import argparse
import ast
import json
import os
import sys
from contextvars import ContextVar
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from astrid.core import timeline
from astrid.core.audit import AuditContext
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import AudioOwnership, RenderProfile
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.publication import publish_render_result
from astrid.core.rendering.service import RenderService
from astrid.packs.rendering.backends.ffmpeg import command as ffmpeg_command
from astrid.packs.rendering.backends.ffmpeg import run as ffmpeg_backend
from astrid.packs.rendering.backends.remotion import run as remotion_backend
from astrid.packs.rendering.executors.render import audio_reactive_colour
from astrid.packs.rendering.finalizers.ffmpeg import run as ffmpeg_finalizer
from astrid.packs.rendering.planners.legacy_hybrid.run import (
    _complex_clip_windows,
    _hybrid_segments,
)


# Compatibility exports for callers that historically imported these private
# helpers from the facade.  Their implementation now lives with the backend.
_RangeHTTPRequestHandler = remotion_backend._RangeHTTPRequestHandler
_validate_project_dir = remotion_backend._validate_project_dir
_serialize_timeline = remotion_backend._serialize_timeline
_resolve_theme_path = remotion_backend._resolve_theme_path
_theme_for_props = remotion_backend._theme_for_props
_theme_slug_for_render_default = remotion_backend._theme_slug_for_render_default
_resolved_theme_for_render = remotion_backend._resolved_theme_for_render
_timeline_composition_src = remotion_backend._timeline_composition_src
_registry_output_paths = remotion_backend._registry_output_paths
_registry_outputs_exist = remotion_backend._registry_outputs_exist
_active_theme_pointer_current = remotion_backend._active_theme_pointer_current
_effective_registry_state = remotion_backend._effective_registry_state
_read_registry_state = remotion_backend._read_registry_state
_write_registry_state = remotion_backend._write_registry_state
_regenerate_element_registries = remotion_backend._regenerate_element_registries
_render_asset_stage_hash = remotion_backend._render_asset_stage_hash
_effect_registry_for_assets = remotion_backend._effect_registry_for_assets
_effect_id_for_clip = remotion_backend._effect_id_for_clip
_source_pack_id = remotion_backend._source_pack_id
_inject_clip_asset_params = remotion_backend._inject_clip_asset_params
_stage_effect_assets_for_timeline = remotion_backend._stage_effect_assets_for_timeline
_render_provenance_sidecar_path = remotion_backend._render_provenance_sidecar_path
_active_pack_order_for_provenance = remotion_backend._active_pack_order_for_provenance
_active_theme_for_provenance = remotion_backend._active_theme_for_provenance
_render_provenance_payload = remotion_backend._render_provenance_payload
_write_render_provenance = remotion_backend._write_render_provenance
_timeline_canvas = ffmpeg_command.timeline_canvas
_clip_duration_seconds = ffmpeg_command.clip_duration_seconds


# The Hype pipeline's default output file name.  The executor manifest exposes
# an ``output_name`` input defaulting to this sentinel; non-default names are
# validated (plain file name, ``.mp4`` extension) and flow through the same
# placeholder expansion and declared-output resolution as the default.
DEFAULT_OUTPUT_NAME = "hype.mp4"

_PUBLICATION_PREVIOUS_OUTPUTS: ContextVar[tuple[Path, ...]] = ContextVar(
    "render_publication_previous_outputs",
    default=(),
)
_HYBRID_FINALIZER_PROFILE: ContextVar[RenderProfile | None] = ContextVar(
    "hybrid_finalizer_profile",
    default=None,
)

_SERVICE: RenderService | None = None


def _default_service() -> RenderService:
    """Build (once) the backend-neutral service the facade delegates to.

    Legacy engine translation, renderer/planner selection, invocation,
    validation, audio completion, finalization, and publication all happen
    inside :class:`RenderService`.  The facade is a thin adapter: it maps the
    legacy argument surface onto the service call and returns the published
    output path.
    """
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = RenderService()
    return _SERVICE


def validate_output_name(name: str) -> str:
    """Validate an ``output_name``: a plain ``.mp4`` file name.

    Rejects empty names, path separators (``/`` and ``\\``), directory
    traversal (``.``, ``..``, or any ``..``-prefixed component), absolute
    paths, and anything that does not end in ``.mp4``.  The Hype default
    ``hype.mp4`` validates unchanged.
    """
    text = str(name)
    if text == "":
        raise ValueError("output_name must not be empty")
    if text in {".", ".."} or text.startswith(".."):
        raise ValueError(
            f"output_name must not traverse directories, got {name!r}"
        )
    if "/" in text or "\\" in text or text.startswith(os.sep):
        raise ValueError(
            f"output_name must be a plain file name without path separators, got {name!r}"
        )
    if Path(text).name != text:
        raise ValueError(
            f"output_name must be a plain file name, got {name!r}"
        )
    if not text.endswith(".mp4"):
        raise ValueError(
            f"output_name must end with .mp4, got {name!r}"
        )
    return text


def _legacy_backend_config(
    *,
    project_dir: Path | None,
    composition_id: str,
    theme_path: Path | None,
    min_free_gb: float | None,
) -> dict[str, dict[str, Any]]:
    """Map the legacy render kwargs onto namespaced backend configuration.

    The facade remains backend-neutral: it only knows the qualified ids that
    correspond to the historical selector spellings and scopes each legacy
    value under the backend that understands it.  The service forwards each
    candidate only its own namespace.
    """
    config: dict[str, dict[str, Any]] = {}
    remotion: dict[str, Any] = {}
    if project_dir is not None:
        remotion["project_dir"] = str(project_dir)
    if composition_id is not None:
        remotion["composition_id"] = composition_id
    if theme_path is not None:
        remotion["theme_path"] = str(theme_path)
    if min_free_gb is not None:
        remotion["min_free_gb"] = min_free_gb
    if remotion:
        config["rendering.remotion"] = remotion
    hybrid: dict[str, Any] = {}
    if theme_path is not None:
        hybrid["theme_path"] = str(theme_path)
    if hybrid:
        config["rendering.legacy_hybrid"] = hybrid
    return config


def _parse_backend_config(value: str | None) -> dict[str, dict[str, Any]]:
    """Parse the ``--backend-config`` CLI payload (JSON or Python literal)."""
    if value is None or value == "":
        return {}
    text = str(value).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(
                f"--backend-config must be a JSON object keyed by qualified "
                f"backend id, got {value!r}"
            ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"--backend-config must be a JSON object keyed by qualified backend id"
        )
    return {str(key): dict(item) for key, item in parsed.items() if item is not None}


def _swap_from_dump(clip: dict) -> dict:
        theme_path=theme_path,
        previous_outputs=_PUBLICATION_PREVIOUS_OUTPUTS.get(),
        element_resolver=_audio_reactive_ffmpeg_element,
    )


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
    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
) -> Path:
    """Render through :class:`RenderService` and publish one locked pair.

    The facade keeps the historical public signature and capability id.  All
    dispatch (legacy engine translation, renderer/planner selection, support,
    invocation, validation, audio completion, finalization, publication)
    happens in the service; the facade only adapts the legacy argument surface
    and the caller-selected output name.
    """
    out_path = Path(out_path)
    validate_output_name(out_path.name)
    previous_outputs = (
        ()
        if keep_previous_renders
        else _previous_render_outputs_for_timeline(out_path, timeline_path)
    )
    config = _legacy_backend_config(
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        min_free_gb=min_free_gb,
    )
    for key, value in (backend_config or {}).items():
        if value is not None:
            config[str(key)] = dict(value)
    return _default_service().render(
        timeline_path,
        assets_path,
        out_path,
        selector=engine,
        backend_config=config,
        previous_outputs=previous_outputs,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeline", type=Path, required=True)
    parser.add_argument("--assets", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--engine",
        default="remotion",
        help="Legacy selector (remotion, ffmpeg, hybrid) or a qualified renderer id.",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="Neutral alias for --engine: legacy selector or qualified backend id.",
    )
    parser.add_argument(
        "--backend-config",
        default=None,
        help="JSON object keyed by qualified backend id with per-backend configuration.",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help="Output file name (default hype.mp4); plain .mp4 file name only.",
    )
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
        if args.output_name is not None:
            validate_output_name(args.output_name)
            if Path(args.out).name != args.output_name:
                raise ValueError(
                    f"--out basename {Path(args.out).name!r} does not match "
                    f"--output-name {args.output_name!r}"
                )
        else:
            validate_output_name(Path(args.out).name)
        selector = args.backend if args.backend is not None else args.engine
        config = _parse_backend_config(args.backend_config)
        if args.assets is None:
            with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
                assets_path = Path(tmp_text) / "hype.assets.json"
                _write_empty_asset_registry(assets_path)
                output = render(
                    args.timeline,
                    assets_path,
                    args.out,
                    engine=selector,
                    project_dir=args.project_dir,
                    composition_id=args.composition,
                    theme_path=args.theme,
                    min_free_gb=args.min_free_gb,
                    keep_previous_renders=args.keep_previous_renders,
                    backend_config=config,
                )
        else:
            output = render(
                args.timeline,
                args.assets,
                args.out,
                engine=selector,
                project_dir=args.project_dir,
                composition_id=args.composition,
                theme_path=args.theme,
                min_free_gb=args.min_free_gb,
                keep_previous_renders=args.keep_previous_renders,
                backend_config=config,
            )
    except Exception as exc:  # pragma: no cover - CLI path
        print(str(exc), file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
{
  "schema_version": 1,
  "cache": {
    "always_run": false,
    "mode": "sentinel",
    "per_brief": true,
    "sentinels": [
      "hype.mp4"
    ]
  },
  "clip_kinds_supported": [
    "video",
    "image",
    "audio",
    "text",
    "effect"
  ],
  "conditions": [],
  "command": {
    "argv": [
      "{python_exec}",
      "-m",
      "astrid.packs.rendering.executors.render.run",
      "--timeline",
      "{timeline}",
      "--out",
      "{out}/{output_name}"
    ],
    "input_args": [
      {
        "input": "assets_registry",
        "flag": "--assets",
        "optional": true,
        "before": "--out"
      },
      {
        "input": "theme",
        "flag": "--theme",
        "optional": true
      },
      {
        "input": "engine",
        "flag": "--engine",
        "optional": true
      },
      {
        "input": "backend",
        "flag": "--backend",
        "optional": true
      },
      {
        "input": "backend_config",
        "flag": "--backend-config",
        "optional": true
      },
      {
        "input": "output_name",
        "flag": "--output-name",
        "optional": true
      },
      {
        "input": "keep_previous_renders",
        "flag": "--keep-previous-renders",
        "optional": true
      }
    ]
  },
  "description": "Render the brief timeline to an .mp4 output through the selected backend.",
  "graph": {
    "consumes": [],
    "depends_on": [
      "editorial.transcribe",
      "editorial.scenes",
      "editorial.quality_zones",
      "editorial.shots",
      "editorial.triage",
      "understanding.scene_describe",
      "editorial.quote_scout",
      "training.pool_build",
      "training.pool_merge",
      "editorial.arrange",
      "video_editing.cut",
      "editorial.refine"
    ],
    "provides": [
      "rendered_video"
    ]
  },
  "id": "rendering.render",
  "inputs": [
    {
      "description": "",
      "name": "timeline",
      "required": true,
      "type": "file",
      "artifact_type": "timeline"
    },
    {
      "description": "",
      "name": "assets_registry",
      "required": false,
      "type": "file",
      "artifact_type": "timeline/assets"
    },
    {
      "description": "",
      "name": "theme",
      "required": false,
      "type": "file",
      "artifact_type": null
    },
    {
      "description": "Render selector. Legacy values (remotion, ffmpeg, hybrid) or a qualified backend id (e.g. rendering.remotion, rendering.ffmpeg).",
      "name": "engine",
      "required": false,
      "type": "string",
      "artifact_type": null
    },
    {
      "description": "Neutral alias for engine: legacy selector or qualified backend id.",
      "name": "backend",
      "required": false,
      "type": "string",
      "artifact_type": null
    },
    {
      "description": "JSON object keyed by qualified backend id with per-backend configuration (e.g. {\"rendering.remotion\": {\"theme_path\": \"/path/theme.json\"}}).",
      "name": "backend_config",
      "required": false,
      "type": "json",
      "artifact_type": null
    },
    {
      "description": "Output file name. Plain .mp4 file name only: no path separators, no traversal, .mp4 extension required. Defaults to hype.mp4.",
      "name": "output_name",
      "required": false,
      "type": "string",
      "artifact_type": null,
      "default": "hype.mp4"
    },
    {
      "description": "Preserve previous provenance-linked hype.mp4 outputs for the same timeline.",
      "name": "keep_previous_renders",
      "required": false,
      "type": "boolean",
      "artifact_type": null
    }
  ],
  "isolation": {
    "binaries": [],
    "mode": "subprocess",
    "network": false,
    "requirements": []
  },
  "keywords": [
    "render",
    "video",
    "remotion",
    "ffmpeg",
    "timeline",
    "hype",
    "mp4"
  ],
  "kind": "built_in",
  "metadata": {
    "requires_timeline": false,
    "command_builder": "astrid.packs.video_editing.orchestrators.hype.run.build_pool_steps",
    "pipeline_step": "render",
    "pipeline_step_order": 12,
    "runtime_entrypoint": "main",
    "runtime_file": "run.py",
    "runtime_module": "astrid.packs.rendering.executors.render.run"
  },
  "name": "Render",
  "outputs": [
    {
      "description": "",
      "mode": "create_or_replace",
      "name": "video",
      "path_template": "{out}/{output_name}",
      "type": "file",
      "artifact_type": "clip/visual"
    },
    {
      "description": "Render provenance sidecar for the video output.",
      "mode": "create_or_replace",
      "name": "provenance",
      "path_template": "{out}/{output_name}.provenance.json",
      "type": "file",
      "artifact_type": "metadata/provenance"
    }
  ],
  "pipeline_requirements": [
    "timeline",
    "assets",
    "theme"
  ],
  "short_description": "Render a hype timeline to an .mp4 output through the selected backend.",
  "version": "1.0"
}
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/execution/executor/runner.py b/astrid/core/execution/executor/runner.py
index 8469dc01..aba0423d 100644
--- a/astrid/core/execution/executor/runner.py
+++ b/astrid/core/execution/executor/runner.py
@@ -799,7 +799,6 @@ def _expand_external_command(
     consumed = _consumed_input_names(executor)
     argv = _insert_input_arg_mappings(argv, executor, values)
     argv = (*argv, *_auto_forward_untemplated_inputs(executor, values, consumed))
-    argv = _normalize_render_command_compat(executor, values, argv)
     cwd = (
         _expand_placeholders(executor.command.cwd, placeholders, error_cls=ExecutorRunnerError)
         if executor.command.cwd
@@ -1237,30 +1236,6 @@ def _insert_input_arg_mappings(
     return tuple(result)
 
 
-def _normalize_render_command_compat(
-    executor: ExecutorDefinition,
-    values: Mapping[str, Any],
-    argv: tuple[str, ...],
-) -> tuple[str, ...]:
-    if executor.id != "rendering.render" or not _has_value(values.get("theme")):
-        return argv
-    try:
-        assets_index = argv.index("--assets")
-        out_index = argv.index("--out")
-    except ValueError:
-        return argv
-    if assets_index < out_index or assets_index + 1 >= len(argv):
-        return argv
-    assets_pair = list(argv[assets_index : assets_index + 2])
-    result = list(argv[:assets_index] + argv[assets_index + 2 :])
-    try:
-        out_index = result.index("--out")
-    except ValueError:
-        return argv
-    result[out_index:out_index] = assets_pair
-    return tuple(result)
-
-
 def _expand_one_input_arg_mapping(
     executor: ExecutorDefinition,
     values: Mapping[str, Any],
diff --git a/astrid/packs/rendering/run.py b/astrid/packs/rendering/run.py
index f0009b1f..009b43af 100644
--- a/astrid/packs/rendering/run.py
+++ b/astrid/packs/rendering/run.py
@@ -93,9 +93,19 @@ def _selects_ffmpeg(argv: Sequence[str]) -> bool:
     return False
 
 
+def _selects_planner() -> bool:
+    """Route the transport-selected hybrid planner without shape guessing."""
+
+    return _transport_selected_backend() == "rendering.legacy_hybrid"
+
+
 def main(argv: Sequence[str] | None = None) -> int:
     args = list(sys.argv[1:] if argv is None else argv)
-    if _selects_finalizer(args):
+    if _selects_planner():
+        from astrid.packs.rendering.planners.legacy_hybrid.run import (
+            main as backend_main,
+        )
+    elif _selects_finalizer(args):
         from astrid.packs.rendering.finalizers.ffmpeg.run import (
             main as backend_main,
         )

exec
/bin/zsh -lc 'rg -n "sentinels|output_name|cache.*identity|per_brief" astrid/core/execution tests/core/rendering/test_output_name.py tests/packs/rendering/test_render_facade.py tests | head -n 250' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_output_name.py:3:The executor manifest exposes ``output_name`` as an ordinary input defaulting
tests/core/rendering/test_output_name.py:15:    validate_output_name,
tests/core/rendering/test_output_name.py:28:def test_valid_output_names_preserved(name: str) -> None:
tests/core/rendering/test_output_name.py:29:    assert validate_output_name(name) == name
tests/core/rendering/test_output_name.py:50:def test_invalid_output_names_rejected(name: str) -> None:
tests/core/rendering/test_output_name.py:52:        validate_output_name(name)
tests/core/rendering/test_output_name.py:55:def test_default_output_name_is_hype_sentinel() -> None:
tests/core/rendering/test_output_name.py:57:    assert validate_output_name(DEFAULT_OUTPUT_NAME) == "hype.mp4"
tests/core/rendering/test_output_name.py:62:        validate_output_name("a/b.mp4")
tests/core/rendering/test_output_name.py:64:        validate_output_name("../evil.mp4")
tests/core/rendering/test_output_name.py:66:        validate_output_name("out.mov")
tests/core/rendering/test_output_name.py:68:        validate_output_name("")
tests/packs/rendering/test_render_facade.py:144:def test_render_validates_output_name_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
tests/packs/rendering/test_render_facade.py:152:def test_main_accepts_output_name_and_forward_parses_any_order(
tests/packs/rendering/test_render_facade.py:180:def test_main_rejects_traversal_output_name(
tests/test_pipeline_editor_loop.py:127:        def write_sentinels(step: pipeline.Step, args) -> None:
tests/test_pipeline_editor_loop.py:146:            write_sentinels(step, args)
astrid/core/execution/orchestrator/schema.py:322:    output_names = _validate_unique_named(orchestrator.outputs, "output")
astrid/core/execution/orchestrator/schema.py:323:    placeholders = set(input_names) | set(output_names)
astrid/core/execution/executor/schema.py:494:    output_names = _validate_unique_named(executor.outputs, "output")
astrid/core/execution/executor/schema.py:497:    placeholders.update(output_names)
tests/test_pipeline_caching.py:187:        return pipeline.Step("render", ("hype.mp4",), lambda args: [], per_brief=True)
tests/test_pipeline_caching.py:518:    def test_refine_reruns_when_cut_sentinels_newer(self) -> None:
astrid/core/execution/executor/cli_handlers.py:318:    if executor.cache.sentinels:
astrid/core/execution/executor/cli_handlers.py:319:        print(f"cache_sentinels: {', '.join(executor.cache.sentinels)}")
tests/core/rendering/test_contracts.py:215:        output_name="preview.mp4",
tests/core/rendering/test_contracts.py:226:        output_name="preview.mp4",
tests/core/rendering/test_contracts.py:267:            "output_name": "video.mp4",
tests/core/rendering/test_contracts.py:279:        output_name="video.mp4",
tests/core/rendering/test_contracts.py:294:        output_name="video.mp4",
tests/core/rendering/test_contracts.py:342:                "output_name": "video.mp4",
tests/core/rendering/test_contracts.py:404:            output_name="video.mp4",
tests/core/rendering/test_contracts.py:412:            output_name="video.mp4",
tests/core/rendering/test_contracts.py:420:        output_name="video.mp4",
tests/core/rendering/fixtures/v1/finalize.json:140:  "output_name": "video.mp4",
tests/core/rendering/fixtures/v1/request.json:5:  "output_name": "video.mp4",
tests/core/rendering/test_legacy_hybrid.py:61:        output_name="video.mp4",
tests/core/rendering/test_output_name.py:3:The executor manifest exposes ``output_name`` as an ordinary input defaulting
tests/core/rendering/test_output_name.py:15:    validate_output_name,
tests/core/rendering/test_output_name.py:28:def test_valid_output_names_preserved(name: str) -> None:
tests/core/rendering/test_output_name.py:29:    assert validate_output_name(name) == name
tests/core/rendering/test_output_name.py:50:def test_invalid_output_names_rejected(name: str) -> None:
tests/core/rendering/test_output_name.py:52:        validate_output_name(name)
tests/core/rendering/test_output_name.py:55:def test_default_output_name_is_hype_sentinel() -> None:
tests/core/rendering/test_output_name.py:57:    assert validate_output_name(DEFAULT_OUTPUT_NAME) == "hype.mp4"
tests/core/rendering/test_output_name.py:62:        validate_output_name("a/b.mp4")
tests/core/rendering/test_output_name.py:64:        validate_output_name("../evil.mp4")
tests/core/rendering/test_output_name.py:66:        validate_output_name("out.mov")
tests/core/rendering/test_output_name.py:68:        validate_output_name("")
tests/core/rendering/test_raw_command_fixture.py:316:                "output_name": "raw_command.mp4",
tests/core/rendering/test_service.py:301:        output = workspace / "outputs" / payload["output_name"]
tests/core/rendering/test_service.py:382:        output_name="video.mp4",
tests/core/rendering/test_service.py:1032:        output_name="video.mp4",
tests/core/rendering/test_service.py:1408:def test_separator_and_traversal_output_names_are_rejected_before_invocation(
tests/core/rendering/test_service.py:1415:    request["output_name"] = name
tests/core/rendering/test_service.py:1428:def test_facade_rejects_non_mp4_output_name_but_preserves_hype_default() -> None:
tests/core/rendering/test_service.py:1431:        validate_output_name,
tests/core/rendering/test_service.py:1435:    assert validate_output_name("hype.mp4") == "hype.mp4"
tests/core/rendering/test_service.py:1437:        validate_output_name("out.mov")
tests/core/rendering/test_service.py:1440:def test_hype_mp4_default_output_name_is_preserved(tmp_path: Path) -> None:
tests/core/rendering/test_service.py:1444:    request = replace(_request(tmp_path), output_name="hype.mp4")
tests/core/rendering/test_service.py:1456:    assert render_payloads[0]["output_name"] == "hype.mp4"
tests/packs/rendering/test_ffmpeg_finalizer.py:199:        output_name="video.mp4",
tests/packs/rendering/test_ffmpeg_finalizer.py:740:        output_name="rational.mp4",
tests/packs/rendering/test_builtin_registration.py:97:    output_name: str,
tests/packs/rendering/test_builtin_registration.py:104:        output_name=output_name,
tests/packs/rendering/test_builtin_registration.py:234:        output_name="ffmpeg-smoke.mp4",
tests/packs/rendering/test_builtin_registration.py:319:        output_name="remotion-smoke.mp4",
tests/fixtures/renderer_packs/raw_command/requests/support.json:5:  "output_name": "raw_command.mp4",
tests/fixtures/renderer_packs/raw_command/requests/render.json:5:  "output_name": "raw_command.mp4",
tests/packs/rendering/test_ffmpeg_support.py:133:        output_name="result.mp4",
tests/packs/rendering/test_ffmpeg_backend.py:126:        output_name="result.mp4",
tests/fixtures/renderer_packs/raw_command/backend.py:428:    output_name = request.get("output_name")
tests/fixtures/renderer_packs/raw_command/backend.py:429:    if not isinstance(output_name, str) or output_name in (".", ".."):
tests/fixtures/renderer_packs/raw_command/backend.py:430:        raise ValueError("output_name must be a non-empty portable basename")
tests/fixtures/renderer_packs/raw_command/backend.py:431:    if not _OUTPUT_NAME_RE.fullmatch(output_name):
tests/fixtures/renderer_packs/raw_command/backend.py:432:        raise ValueError("output_name must match [A-Za-z0-9][A-Za-z0-9._-]*")
tests/fixtures/renderer_packs/raw_command/backend.py:518:        output_name = request["output_name"]
tests/fixtures/renderer_packs/raw_command/backend.py:524:        video_rel = f"outputs/{output_name}"
tests/fixtures/renderer_packs/raw_command/backend.py:525:        video_path = out_dir / output_name
tests/packs/rendering/test_remotion_backend.py:84:        output_name="result.mp4",
tests/packs/rendering/test_render_facade.py:144:def test_render_validates_output_name_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
tests/packs/rendering/test_render_facade.py:152:def test_main_accepts_output_name_and_forward_parses_any_order(
tests/packs/rendering/test_render_facade.py:180:def test_main_rejects_traversal_output_name(

exec
/bin/zsh -lc "sed -n '1,370p' astrid/packs/rendering/planners/legacy_hybrid/run.py && sed -n '370,820p' astrid/packs/rendering/planners/legacy_hybrid/run.py && sed -n '820,910p' astrid/packs/rendering/planners/legacy_hybrid/run.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
#!/usr/bin/env python3
"""Legacy hybrid planner and rendering-protocol v1 command adapter.

The planner owns only deterministic window construction and renderer support
selection.  It never renders a segment or finalizes media; ``RenderService``
does both after independently resolving and rechecking every pinned capability.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    _CHECKOUT_ROOT = Path(__file__).resolve().parents[5]
    if str(_CHECKOUT_ROOT) not in sys.path:
        sys.path.insert(0, str(_CHECKOUT_ROOT))

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.rendering.contracts import (
    FinalizerResolution,
    FrameWindow,
    PlannerResolution,
    RenderPlan,
    RenderRequest,
    RenderSegment,
    RendererResolution,
    SCHEMA_VERSION,
    SupportReport,
    compute_request_digest,
)
from astrid.core.rendering.errors import (
    RendererException,
    make_renderer_error,
    raise_unsupported_error,
)
from astrid.core.rendering.profile import resolve_render_profile
from astrid.core.rendering.registry import (
    FinalizerRegistry,
    RendererRegistry,
    RenderingCandidate,
    load_default_registries,
)
from astrid.core.rendering.transport import CommandTransport


BACKEND_ID = "rendering.legacy_hybrid"
BACKEND_VERSION = "1.0.0"
FINALIZER_ID = "rendering.ffmpeg-finalizer"
FFMPEG_ID = "rendering.ffmpeg"
REMOTION_ID = "rendering.remotion"
_ZERO_DIGEST = "0" * 64
_HANDLE_SECONDS = Fraction(1, 4)
_PLANNER_CONFIG_KEYS = frozenset(
    {
        "simple_renderers",
        "complex_renderers",
        "renderers",
        "theme",
        "theme_path",
        "themes_root",
        "extra_pack_roots",
    }
)

SupportResolver = Callable[[str, RenderRequest, Mapping[str, Any]], SupportReport]


def _number(value: Any, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a finite number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{label} must be finite")
    return Fraction(str(value))


def _floor(value: Fraction) -> int:
    return value.numerator // value.denominator


def _ceil(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _clip_duration_seconds(clip: Mapping[str, Any]) -> Fraction:
    source_from = _number(clip.get("from", 0), "clip.from")
    if "to" not in clip:
        raise ValueError("media clip must declare a source to bound")
    source_to = _number(clip["to"], "clip.to")
    speed = _number(clip.get("speed", 1), "clip.speed")
    if source_from < 0 or source_to <= source_from or speed <= 0:
        raise ValueError("media clip must have positive bounds and speed")
    return (source_to - source_from) / speed


def _clip_timeline_end(clip: Mapping[str, Any]) -> Fraction:
    start = _number(clip.get("at", 0), "clip.at")
    if clip.get("clipType", "media") == "media":
        return start + _clip_duration_seconds(clip)
    hold = clip.get("hold")
    if isinstance(hold, (int, float)) and not isinstance(hold, bool):
        return start + max(Fraction(0), _number(hold, "clip.hold"))
    to_value = clip.get("to")
    if isinstance(to_value, (int, float)) and not isinstance(to_value, bool):
        return _number(to_value, "clip.to")
    return start


def _timeline_duration(timeline: Mapping[str, Any]) -> Fraction:
    metadata = timeline.get("metadata")
    explicit: Any = None
    if isinstance(metadata, Mapping):
        explicit = metadata.get("duration_seconds")
        if not isinstance(explicit, (int, float)) or isinstance(explicit, bool):
            explicit = metadata.get("expected_duration_seconds")
    if isinstance(explicit, (int, float)) and not isinstance(explicit, bool):
        duration = _number(explicit, "timeline duration")
        if duration < 0:
            raise ValueError("timeline duration must not be negative")
        return duration
    clips = timeline.get("clips", [])
    if not isinstance(clips, list):
        raise TypeError("timeline clips must be an array")
    ends = [
        _clip_timeline_end(clip)
        for clip in clips
        if isinstance(clip, Mapping)
    ]
    return max(ends, default=Fraction(0))


def _base_visual_track(
    timeline: Mapping[str, Any], tracks: Mapping[Any, Mapping[str, Any]]
) -> Any:
    visual_ids = {
        track_id for track_id, track in tracks.items() if track.get("kind") == "visual"
    }
    coverage: dict[Any, Fraction] = {}
    for clip in timeline.get("clips", []):
        if (
            isinstance(clip, Mapping)
            and clip.get("clipType", "media") == "media"
            and clip.get("track") in visual_ids
        ):
            track_id = clip.get("track")
            coverage[track_id] = coverage.get(track_id, Fraction(0)) + _clip_duration_seconds(clip)
    return max(coverage, key=coverage.get) if coverage else None


def _complex_frame_windows(
    timeline: Mapping[str, Any],
    fps: Fraction,
    *,
    handle_seconds: Fraction = _HANDLE_SECONDS,
) -> list[tuple[int, int]]:
    """Port the characterized legacy complexity/transition window rules."""

    duration = _timeline_duration(timeline)
    total_frames = _ceil(duration * fps)
    raw_tracks = timeline.get("tracks", [])
    raw_clips = timeline.get("clips", [])
    if not isinstance(raw_tracks, list) or not isinstance(raw_clips, list):
        raise TypeError("timeline tracks and clips must be arrays")
    tracks = {
        track.get("id"): track
        for track in raw_tracks
        if isinstance(track, Mapping)
    }
    base_visual_track = _base_visual_track(timeline, tracks)
    windows: list[tuple[int, int]] = []
    clips = [clip for clip in raw_clips if isinstance(clip, Mapping)]

    for index, clip in enumerate(clips):
        media = clip.get("clipType", "media") == "media"
        transition_window = False
        if media:
            track = tracks.get(clip.get("track"), {})
            params = clip.get("params") if isinstance(clip.get("params"), Mapping) else {}
            complex_media = (
                bool(clip.get("effects"))
                or bool(clip.get("transition"))
                or (
                    track.get("kind") == "visual"
                    and clip.get("track") != base_visual_track
                )
                or (
                    isinstance(clip.get("opacity"), (int, float))
                    and not isinstance(clip.get("opacity"), bool)
                    and float(clip.get("opacity") or 0) != 1.0
                )
                or (
                    track.get("kind") == "audio"
                    and (
                        isinstance(params.get("fadeIn"), (int, float))
                        or isinstance(params.get("fadeOut"), (int, float))
                    )
                )
            )
            if not complex_media:
                continue
            next_same_track = next(
                (
                    candidate
                    for candidate in clips[index + 1 :]
                    if candidate.get("track") == clip.get("track")
                ),
                None,
            )
            if clip.get("transition") and next_same_track is not None:
                transition = clip.get("transition")
                transition_seconds = Fraction(8, 1) / fps
                if isinstance(transition, Mapping):
                    if isinstance(transition.get("duration"), (int, float)):
                        transition_seconds = _number(
                            transition["duration"], "transition.duration"
                        )
                    elif isinstance(transition.get("durationFrames"), (int, float)):
                        transition_seconds = _number(
                            transition["durationFrames"], "transition.durationFrames"
                        ) / fps
                clip_end = _clip_timeline_end(clip)
                next_start = _number(
                    next_same_track.get("at", float(clip_end)), "clip.at"
                )
                start = max(
                    Fraction(0),
                    min(clip_end - transition_seconds, next_start) - handle_seconds,
                )
                end = min(
                    duration,
                    max(clip_end, next_start + transition_seconds) + handle_seconds,
                )
                if end > start:
                    windows.append(
                        (max(0, _floor(start * fps)), min(total_frames, _ceil(end * fps)))
                    )
                transition_window = True
        if transition_window:
            continue
        start = max(Fraction(0), _number(clip.get("at", 0), "clip.at") - handle_seconds)
        end = min(duration, _clip_timeline_end(clip) + handle_seconds)
        if end > start:
            windows.append(
                (max(0, _floor(start * fps)), min(total_frames, _ceil(end * fps)))
            )

    windows = [(start, end) for start, end in windows if end > start]
    windows.sort()
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _segment_kinds(
    timeline: Mapping[str, Any], fps: Fraction
) -> tuple[int, list[tuple[int, int, str]]]:
    total_frames = _ceil(_timeline_duration(timeline) * fps)
    if total_frames == 0:
        return 0, []
    complex_windows = _complex_frame_windows(timeline, fps)
    if not complex_windows:
        return total_frames, [(0, total_frames, "simple")]
    segments: list[tuple[int, int, str]] = []
    cursor = 0
    for start, end in complex_windows:
        start = max(0, min(start, total_frames))
        end = max(start, min(end, total_frames))
        if start > cursor:
            segments.append((cursor, start, "simple"))
        if end > start:
            segments.append((start, end, "complex"))
        cursor = max(cursor, end)
    if cursor < total_frames:
        segments.append((cursor, total_frames, "simple"))
    return total_frames, segments


# Compatibility projections retained for the characterized legacy facade.
def _complex_clip_windows(
    timeline_data: Mapping[str, Any],
    fps: int | Fraction,
    *,
    handle_seconds: float = 0.25,
) -> list[tuple[float, float]]:
    rate = fps if isinstance(fps, Fraction) else Fraction(fps, 1)
    return [
        (float(Fraction(start, 1) / rate), float(Fraction(end, 1) / rate))
        for start, end in _complex_frame_windows(
            timeline_data,
            rate,
            handle_seconds=Fraction(str(handle_seconds)),
        )
    ]


def _hybrid_segments(
    timeline_data: Mapping[str, Any], *, fps: Fraction | None = None
) -> list[dict[str, float | str]]:
    if fps is None:
        profile = resolve_render_profile(timeline_data, themes_root=REPO_ROOT / "themes")
        fps = Fraction(*profile.fps_rational)
    _total, kinds = _segment_kinds(timeline_data, fps)
    return [
        {
            "engine": "ffmpeg" if kind == "simple" else "remotion",
            "from": float(Fraction(start, 1) / fps),
            "to": float(Fraction(end, 1) / fps),
        }
        for start, end, kind in kinds
    ]


def _structural_reasons(timeline: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    tracks = timeline.get("tracks", [])
    clips = timeline.get("clips", [])
    if not isinstance(tracks, list) or not isinstance(clips, list):
        return ["timeline tracks and clips must be arrays"]
    track_by_id = {
        track.get("id"): track for track in tracks if isinstance(track, Mapping)
    }
    audio_ranges: list[tuple[Fraction, Fraction, Any]] = []
    for clip in clips:
        if not isinstance(clip, Mapping):
            reasons.append("timeline clips must contain objects")
            continue
        if clip.get("clipType", "media") != "media":
            continue
        try:
            speed = _number(clip.get("speed", 1), "clip.speed")
            start = _number(clip.get("at", 0), "clip.at")
            end = _clip_timeline_end(clip)
        except (TypeError, ValueError) as exc:
            reasons.append(str(exc))
            continue
        if speed != 1:
            reasons.append(
                f"Clip {clip.get('id')!r} uses unsupported speed {float(speed):g}; "
                "legacy hybrid planning requires 1.0"
            )
        track = track_by_id.get(clip.get("track"), {})
        if track.get("kind") == "audio":
            audio_ranges.append((start, end, clip.get("id")))
    audio_ranges.sort()
    cursor = Fraction(0)
    for start, end, clip_id in audio_ranges:
        if start < cursor:
            reasons.append(
                f"Overlapping audio at clip {clip_id!r}: starts before previous audio ends"
            )
        cursor = max(cursor, end)
    return list(dict.fromkeys(reasons))


def _load_inputs(
    request: RenderRequest, workspace: Path
) -> tuple[Path, dict[str, Any], Path | None, dict[str, Any]]:
) -> tuple[Path, dict[str, Any], Path | None, dict[str, Any]]:
    timeline_path = _input_path(request.timeline_path, workspace)
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    if not isinstance(timeline, dict):
        raise TypeError("timeline must contain a JSON object")
    assets_path = (
        None
        if request.assets_registry_path is None
        else _input_path(request.assets_registry_path, workspace)
    )
    if assets_path is None:
        assets = {"assets": {}}
    else:
        assets = json.loads(assets_path.read_text(encoding="utf-8"))
        if not isinstance(assets, dict) or not isinstance(assets.get("assets"), dict):
            raise TypeError("assets registry must contain an assets object")
    return timeline_path, timeline, assets_path, assets


def _input_path(raw: str, workspace: Path) -> Path:
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else workspace / path).resolve()


def _planner_config(request: RenderRequest) -> dict[str, Any]:
    config = dict(request.backend_config.get(BACKEND_ID, {}))
    unknown = sorted(set(config) - _PLANNER_CONFIG_KEYS)
    if unknown:
        raise ValueError(f"unknown {BACKEND_ID} configuration: {', '.join(unknown)}")
    return config


def _string_list(value: Any, *, label: str, default: Sequence[str]) -> tuple[str, ...]:
    if value is None:
        value = default
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{label} must be an array of qualified renderer ids")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or "." not in item:
            raise ValueError(f"{label} must contain qualified renderer ids")
        if item not in result:
            result.append(item)
    if not result:
        raise ValueError(f"{label} must not be empty")
    return tuple(result)


def _candidate_lists(config: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    common = config.get("renderers")
    if common is not None:
        candidates = _string_list(common, label="renderers", default=())
        return {"simple": candidates, "complex": candidates}
    return {
        "simple": _string_list(
            config.get("simple_renderers"),
            label="simple_renderers",
            default=(FFMPEG_ID, REMOTION_ID),
        ),
        "complex": _string_list(
            config.get("complex_renderers"),
            label="complex_renderers",
            default=(REMOTION_ID,),
        ),
    }


def support(request: RenderRequest, *, workspace: Path) -> SupportReport:
    reasons: list[str] = []
    try:
        _timeline_path, timeline, _assets_path, assets = _load_inputs(request, workspace)
        config = _planner_config(request)
        _candidate_lists(config)
        theme = config.get("theme_path", config.get("theme"))
        themes_root = config.get("themes_root", REPO_ROOT / "themes")
        profile = resolve_render_profile(
            timeline,
            assets,
            theme=theme,
            themes_root=themes_root,
            audio_ownership=request.audio,
        )
        reasons.extend(_structural_reasons(timeline))
        _segment_kinds(timeline, Fraction(*profile.fps_rational))
        if request.window is not None:
            if request.window.fps_rational != profile.fps_rational:
                reasons.append("request window FPS does not match the canonical render profile")
            else:
                total_frames = _ceil(
                    _timeline_duration(timeline) * Fraction(*profile.fps_rational)
                )
                if request.window.end_frame > total_frames:
                    reasons.append("request window extends beyond the timeline")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        reasons.append(str(exc) or type(exc).__name__)
    reasons = list(dict.fromkeys(reasons))
    return SupportReport(
        schema_version=SCHEMA_VERSION,
        supported=not reasons,
        reasons=reasons,
        features={
            "integer_frame_windows": True,
            "transition_handles": True,
            "support_based_assignment": True,
            "explicit_finalizer": True,
            "non_recursive_dispatch": True,
        },
        alternatives=[],
        backend=BACKEND_ID,
        backend_version=BACKEND_VERSION,
    )


def _window_timeline(
    timeline: Mapping[str, Any], window: FrameWindow
) -> dict[str, Any]:
    fps = Fraction(*window.fps_rational)
    start = Fraction(window.start_frame, 1) / fps
    end = Fraction(window.end_frame, 1) / fps
    clips: list[dict[str, Any]] = []
    for raw_clip in timeline.get("clips", []):
        if not isinstance(raw_clip, Mapping):
            continue
        clip_start = _number(raw_clip.get("at", 0), "clip.at")
        clip_end = _clip_timeline_end(raw_clip)
        visible_start = max(start, clip_start)
        visible_end = min(end, clip_end)
        if visible_end <= visible_start:
            continue
        clip = dict(raw_clip)
        clip["id"] = f"{raw_clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
        clip["at"] = float(visible_start - start)
        if raw_clip.get("clipType", "media") == "media":
            speed = _number(raw_clip.get("speed", 1), "clip.speed")
            source_from = _number(raw_clip.get("from", 0), "clip.from")
            source_from += (visible_start - clip_start) * speed
            clip["from"] = float(source_from)
            clip["to"] = float(source_from + (visible_end - visible_start) * speed)
        elif isinstance(raw_clip.get("hold"), (int, float)):
            clip["hold"] = float(visible_end - visible_start)
        clips.append(clip)
    used_tracks = {clip.get("track") for clip in clips}
    result = dict(timeline)
    result["clips"] = clips
    result["tracks"] = [
        dict(track)
        for track in timeline.get("tracks", [])
        if isinstance(track, Mapping) and track.get("id") in used_tracks
    ]
    metadata = timeline.get("metadata")
    result["metadata"] = {
        **(dict(metadata) if isinstance(metadata, Mapping) else {}),
        "source_window_start_seconds": float(start),
        "source_window_end_seconds": float(end),
        "duration_seconds": float(end - start),
    }
    return result


def _source_pack(candidate: RenderingCandidate[Any]) -> dict[str, Any]:
    return {
        "id": candidate.pack_id,
        "source_kind": candidate.source_kind,
        "pack_root": str(candidate.pack_root),
    }


def _renderer_resolution(
    renderer_id: str,
    report: SupportReport,
    *,
    registry: RendererRegistry | None,
) -> RendererResolution:
    if registry is None:
        return RendererResolution(
            id=renderer_id,
            source_pack={"id": renderer_id.split(".", 1)[0]},
            manifest_digest=_ZERO_DIGEST,
            alias_chain=[],
            override=None,
            support_decision=report,
            trust_eligibility={"eligible": True, "method": "injected-support"},
        )
    candidate = registry.get(renderer_id)
    evidence = registry.resolve_evidence(renderer_id)
    return RendererResolution(
        id=candidate.id,
        source_pack=_source_pack(candidate),
        manifest_digest=candidate.manifest_digest,
        alias_chain=list(evidence.get("alias_chain") or []),
        override=evidence.get("override"),
        support_decision=report,
        trust_eligibility=candidate.eligibility.to_dict(),
    )


def _finalizer_resolution(registry: FinalizerRegistry | None) -> FinalizerResolution:
    if registry is None:
        return FinalizerResolution(
            id=FINALIZER_ID,
            source_pack={"id": "rendering"},
            manifest_digest=_ZERO_DIGEST,
            alias_chain=[],
            override=None,
            trust_eligibility={"eligible": True},
            support_decision=None,
        )
    candidate = registry.get(FINALIZER_ID)
    evidence = registry.resolve_evidence(FINALIZER_ID)
    return FinalizerResolution(
        id=candidate.id,
        source_pack=_source_pack(candidate),
        manifest_digest=candidate.manifest_digest,
        alias_chain=list(evidence.get("alias_chain") or []),
        override=evidence.get("override"),
        trust_eligibility=candidate.eligibility.to_dict(),
        support_decision=None,
    )


def _planner_resolution(report: SupportReport) -> PlannerResolution:
    manifest = Path(__file__).with_name("planner.yaml")
    return PlannerResolution(
        id=BACKEND_ID,
        source_pack={"id": "rendering", "source_kind": "source"},
        manifest_digest=sha256_file(manifest) if manifest.is_file() else _ZERO_DIGEST,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        alias_chain=[],
        override=None,
        support_decision=report,
    )


class _CommandSupportResolver:
    def __init__(
        self,
        registry: RendererRegistry,
        *,
        workspace: Path,
    ) -> None:
        self.registry = registry
        self.workspace = workspace
        self.counter = 0

    def __call__(
        self,
        renderer_id: str,
        request: RenderRequest,
        timeline: Mapping[str, Any],
    ) -> SupportReport:
        candidate = self.registry.get(renderer_id)
        evidence = self.registry.resolve_evidence(renderer_id)
        del evidence
        projected = request.for_backend(candidate.id)
        if candidate.manifest.capabilities.get("supports_windows") is False:
            if projected.window is None:
                raise ValueError("planned renderer support requires a frame window")
            path = self.workspace / "planner-support" / f"{self.counter:04d}-timeline.json"
            self.counter += 1
            write_json_atomic(path, timeline)
            projected = replace(projected, timeline_path=str(path), window=None)
        if "support" not in candidate.manifest.operations:
            supports = candidate.manifest.capabilities.get(
                "supports_windows" if projected.window is not None else "supports_full_timeline"
            ) is True
            return SupportReport(
                schema_version=SCHEMA_VERSION,
                supported=supports,
                reasons=[] if supports else ["renderer lacks static support for this window"],
                features={
                    str(key): value
                    for key, value in candidate.manifest.capabilities.get("features", {}).items()
                    if isinstance(value, (bool, str))
                },
                alternatives=[],
                backend=candidate.id,
                backend_version=candidate.manifest.version,
            )
        request_path = self.workspace / "planner-support" / f"{self.counter:04d}-request.json"
        result_path = self.workspace / "planner-support" / f"{self.counter:04d}-result.json"
        self.counter += 1
        write_json_atomic(request_path, projected.to_dict())
        response = CommandTransport(candidate.id).run(
            "support",
            candidate.manifest.command,
            request_path=request_path,
            result_path=result_path,
            cwd=candidate.pack_root,
            required_binaries=(),
            timeout=candidate.manifest.timeout_seconds,
        )
        if not isinstance(response, SupportReport):
            raise TypeError(f"{candidate.id} support did not return a SupportReport")
        return response


def plan(
    request: RenderRequest,
    *,
    workspace: Path,
    support_resolver: SupportResolver | None = None,
    registries: tuple[RendererRegistry, FinalizerRegistry] | None = None,
) -> RenderPlan:
    report = support(request, workspace=workspace)
    if not report.supported:
        raise_unsupported_error(
            backend=BACKEND_ID,
            message="legacy hybrid planner does not support this request",
            recovery_command="resolve the reported timeline constraints and retry",
            details={"reasons": report.reasons},
        )
    timeline_path, timeline, assets_path, assets = _load_inputs(request, workspace)
    config = _planner_config(request)
    theme = config.get("theme_path", config.get("theme"))
    profile = resolve_render_profile(
        timeline,
        assets,
        theme=theme,
        themes_root=config.get("themes_root", REPO_ROOT / "themes"),
        audio_ownership=request.audio,
    )
    fps = Fraction(*profile.fps_rational)
    total_frames, raw_segments = _segment_kinds(timeline, fps)

    renderer_registry: RendererRegistry | None
    finalizer_registry: FinalizerRegistry | None
    if registries is None and support_resolver is None:
        raw_extra_roots = config.get("extra_pack_roots", ())
        if isinstance(raw_extra_roots, (str, bytes)) or not isinstance(
            raw_extra_roots, Sequence
        ):
            raise TypeError("extra_pack_roots must be an array of paths")
        extra_roots = tuple(str(item) for item in raw_extra_roots)
        renderer_registry, _planners, finalizer_registry = load_default_registries(
            REPO_ROOT,
            extra_pack_roots=extra_roots,
        )
    elif registries is None:
        renderer_registry = None
        finalizer_registry = None
    else:
        renderer_registry, finalizer_registry = registries
    if support_resolver is None:
        if renderer_registry is None:
            raise RuntimeError("renderer registry is required for command support resolution")
        support_resolver = _CommandSupportResolver(
            renderer_registry,
            workspace=workspace,
        )

    candidates = _candidate_lists(config)
    if request.window is not None:
        target_start = request.window.start_frame
        target_end = request.window.end_frame
        raw_segments = [
            (max(start, target_start), min(end, target_end), kind)
            for start, end, kind in raw_segments
            if min(end, target_end) > max(start, target_start)
        ]
    segments: list[RenderSegment] = []
    reasons: dict[str, str] = {}
    for index, (start, end, kind) in enumerate(raw_segments):
        window = FrameWindow(
            start_frame=start,
            end_frame=end,
            fps_rational=profile.fps_rational,
        )
        segment_timeline = _window_timeline(timeline, window)
        segment_request = replace(
            request,
            timeline_path=str(timeline_path),
            assets_registry_path=None if assets_path is None else str(assets_path),
            output_name=f"segment-{index:04d}.mp4",
            window=window,
        )
        attempts: list[str] = []
        selected_id: str | None = None
        selected_report: SupportReport | None = None
        for renderer_id in candidates[kind]:
            try:
                candidate_report = support_resolver(
                    renderer_id,
                    segment_request,
                    segment_timeline,
                )
            except Exception as exc:
                attempts.append(f"{renderer_id}: {exc}")
                continue
            if candidate_report.backend != renderer_id:
                attempts.append(f"{renderer_id}: support report named {candidate_report.backend}")
                continue
            if candidate_report.supported:
                selected_id = renderer_id
                selected_report = candidate_report
                break
            attempts.append(
                f"{renderer_id}: " + "; ".join(candidate_report.reasons)
            )
        if selected_id is None or selected_report is None:
            raise_unsupported_error(
                backend=BACKEND_ID,
                message=f"no renderer supports planned {kind} window [{start},{end})",
                recovery_command="install or configure a renderer supporting the reported window",
                details={"window": [start, end], "attempts": attempts},
            )
        segments.append(
            RenderSegment(
                window=window,
                renderer=_renderer_resolution(
                    selected_id,
                    selected_report,
                    registry=renderer_registry,
                ),
                input_hashes={
                    "timeline": sha256_file(timeline_path),
                    **(
                        {"assets_registry": sha256_file(assets_path)}
                        if assets_path is not None
                        else {}
                    ),
                },
            )
        )
        reasons[str(index)] = (
            f"{kind} legacy window assigned to {selected_id} by supported report"
        )

    return RenderPlan(
        schema_version=SCHEMA_VERSION,
        request_digest=compute_request_digest(request.to_dict()),
        requested_policy="hybrid",
        planner=_planner_resolution(report),
        segments=segments,
        finalizer=_finalizer_resolution(finalizer_registry),
        profile=profile,
        total_frames=total_frames,
        reasons=reasons,
        window=request.window,
    )


def _load_request(path: Path) -> RenderRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("render request must contain a JSON object")
    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)


def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
    if isinstance(exc, RendererException):
        error_kind = exc.error.kind
        error_kind = exc.error.kind
        message = exc.error.message
        recovery = exc.error.recovery_command
        details = exc.error.details
    else:
        error_kind = kind
        message = str(exc) or type(exc).__name__
        recovery = None
        details = {"error_type": type(exc).__name__}
    write_json_atomic(
        result_path,
        make_renderer_error(
            error_kind,
            backend=BACKEND_ID,
            message=message,
            recovery_command=recovery,
            details=details,
        ).to_dict(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("verb", choices=("plan", "support"))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request_path = args.request.resolve(strict=True)
        result_path = args.result.resolve()
        if request_path == result_path:
            raise ValueError("--request and --result must be different paths")
        request = _load_request(request_path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, RendererException) as exc:
        _write_failure(args.result.resolve(), exc, kind="protocol")
        return 0
    try:
        workspace = request_path.parent
        response: RenderPlan | SupportReport
        if args.verb == "support":
            response = support(request, workspace=workspace)
        else:
            response = plan(request, workspace=workspace)
        write_json_atomic(result_path, response.to_dict())
    except RendererException as exc:
        _write_failure(result_path, exc, kind=exc.error.kind)
    except FileNotFoundError as exc:
        _write_failure(result_path, exc, kind="binary_missing")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        _write_failure(result_path, exc, kind="protocol")
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _write_failure(result_path, exc, kind="internal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BACKEND_ID",
    "BACKEND_VERSION",
    "FINALIZER_ID",
    "_complex_clip_windows",
    "_complex_frame_windows",
    "_hybrid_segments",
    "main",
    "plan",
    "support",
]

exec
/bin/zsh -lc "rg -n \"class RenderPlan|total_frames|plan window|segments.*cover\" astrid/core/rendering/contracts.py | head -n 80 && sed -n '1420,1535p' astrid/core/rendering/contracts.py && nl -ba astrid/packs/rendering/planners/legacy_hybrid/run.py | sed -n '360,380p;808,832p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
1361:class RenderPlan:
1371:    total_frames: int
1414:        total_frames = _require_int(self.total_frames, "total_frames", minimum=0)
1415:        object.__setattr__(self, "total_frames", total_frames)
1416:        window = _coerce_window(self.window, "plan window", nullable=True)
1420:                raise ValueError("plan window FPS must exactly match the canonical profile FPS")
1421:            if window.end_frame > total_frames:
1422:                raise ValueError("plan window must not extend beyond total_frames")
1423:        if total_frames == 0:
1430:            target_end = window.end_frame if window is not None else total_frames
1464:                "total_frames": self.total_frames,
1482:                "total_frames",
1498:                total_frames=data["total_frames"],
1732:        if plan.total_frames == 0:
                raise ValueError("plan window FPS must exactly match the canonical profile FPS")
            if window.end_frame > total_frames:
                raise ValueError("plan window must not extend beyond total_frames")
        if total_frames == 0:
            if window is not None or segments:
                raise ValueError("a zero-frame plan must have no window or segments")
        else:
            if not segments:
                raise ValueError("a positive-frame plan must contain at least one segment")
            target_start = window.start_frame if window is not None else 0
            target_end = window.end_frame if window is not None else total_frames
            expected_start = target_start
            for index, segment in enumerate(segments):
                if segment.window.fps_rational != profile.fps_rational:
                    raise ValueError(
                        f"segments[{index}] FPS must exactly match the canonical profile FPS"
                    )
                actual_start = segment.window.start_frame
                if actual_start != expected_start:
                    relation = "overlaps or is out of order" if actual_start < expected_start else "leaves a gap"
                    raise ValueError(f"segments[{index}] {relation} at frame {expected_start}")
                if segment.window.end_frame > target_end:
                    raise ValueError(f"segments[{index}] extends beyond the plan target window")
                expected_start = segment.window.end_frame
            if expected_start != target_end:
                raise ValueError("plan segments leave a trailing gap")
        reasons = _require_string_mapping(self.reasons, "reasons")
        expected_reason_keys = {str(index) for index in range(len(segments))}
        if set(reasons) != expected_reason_keys:
            raise ValueError(
                "plan reasons must contain exactly one entry per segment, keyed by zero-based index"
            )
        object.__setattr__(self, "reasons", reasons)

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "request_digest": self.request_digest,
                "requested_policy": self.requested_policy,
                "planner": self.planner,
                "segments": self.segments,
                "finalizer": self.finalizer,
                "profile": self.profile,
                "total_frames": self.total_frames,
                "reasons": self.reasons,
                "window": self.window,
            }
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RenderPlan:
        try:
            data = _require_mapping(payload, "render plan")
            required = {
                "schema_version",
                "request_digest",
                "requested_policy",
                "planner",
                "segments",
                "finalizer",
                "profile",
                "total_frames",
                "reasons",
                "window",
            }
            _validate_object_keys(data, required=required, allowed=required, label="render plan")
            raw_segments = data["segments"]
            if isinstance(raw_segments, (str, bytes)) or not isinstance(raw_segments, Sequence):
                raise TypeError("segments must be an array")
            return cls(
                schema_version=data["schema_version"],
                request_digest=data["request_digest"],
                requested_policy=data["requested_policy"],
                planner=PlannerResolution.from_dict(data["planner"]),
                segments=[RenderSegment.from_dict(item) for item in raw_segments],
                finalizer=FinalizerResolution.from_dict(data["finalizer"]),
                profile=RenderProfile.from_dict(data["profile"]),
                total_frames=data["total_frames"],
                reasons=data["reasons"],
                window=FrameWindow.from_dict(data["window"]) if data["window"] is not None else None,
            )
        except Exception as exc:
            from .errors import RendererException

            if isinstance(exc, RendererException):
                raise
            _protocol_failure(
                f"malformed render plan: {exc}",
                details={"error_type": type(exc).__name__},
            )


def _validate_backend_fragments(value: Any) -> dict[str, dict[str, Any]]:
    mapping = _require_mapping(value, "backend_fragments")
    fragments: dict[str, dict[str, Any]] = {}
    for raw_namespace, raw_fragment in mapping.items():
        namespace = _require_qualified_id(raw_namespace, "backend fragment namespace")
        fragment = _json_safe_mapping(raw_fragment, label=f"backend_fragments[{namespace!r}]")
        conflicts = sorted(set(fragment) & RESERVED_BACKEND_FRAGMENT_KEYS)
        if conflicts:
            raise ValueError(
                f"backend fragment {namespace!r} attempts to overwrite core-owned keys: "
                f"{', '.join(conflicts)}"
            )
        fragments[namespace] = fragment
    return fragments


@dataclass(frozen=True)
class RenderResult:
    """Successful renderer/finalizer result written to the authoritative path."""

    schema_version: int
    video: VideoArtifact
    audio_ownership: AudioOwnership
   360	        if start < cursor:
   361	            reasons.append(
   362	                f"Overlapping audio at clip {clip_id!r}: starts before previous audio ends"
   363	            )
   364	        cursor = max(cursor, end)
   365	    return list(dict.fromkeys(reasons))
   366	
   367	
   368	def _load_inputs(
   369	    request: RenderRequest, workspace: Path
   370	) -> tuple[Path, dict[str, Any], Path | None, dict[str, Any]]:
   371	    timeline_path = _input_path(request.timeline_path, workspace)
   372	    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
   373	    if not isinstance(timeline, dict):
   374	        raise TypeError("timeline must contain a JSON object")
   375	    assets_path = (
   376	        None
   377	        if request.assets_registry_path is None
   378	        else _input_path(request.assets_registry_path, workspace)
   379	    )
   380	    if assets_path is None:
   808	    )
   809	
   810	
   811	def _load_request(path: Path) -> RenderRequest:
   812	    payload = json.loads(path.read_text(encoding="utf-8"))
   813	    if not isinstance(payload, Mapping):
   814	        raise TypeError("render request must contain a JSON object")
   815	    return RenderRequest.from_dict(payload).for_backend(BACKEND_ID)
   816	
   817	
   818	def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
   819	    if isinstance(exc, RendererException):
   820	        error_kind = exc.error.kind
   821	        message = exc.error.message
   822	        recovery = exc.error.recovery_command
   823	        details = exc.error.details
   824	    else:
   825	        error_kind = kind
   826	        message = str(exc) or type(exc).__name__
   827	        recovery = None
   828	        details = {"error_type": type(exc).__name__}
   829	    write_json_atomic(
   830	        result_path,
   831	        make_renderer_error(
   832	            error_kind,

exec
/bin/zsh -lc 'rg -n "hybrid|support.*assign|fallback|candidate" .oracle/plan.md docs/contracts/render-backend-v1.md .megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md | head -n 220' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
.oracle/plan.md:7:4. **Registry semantics:** build renderer/planner/finalizer registries over `CapabilityRegistry`, `AliasResolver`, and `OverrideStore`. Winner order comes directly from `DiscoveredPack.priority_index`; do not reinterpret executor `metadata["priority"]`. Only execution-eligible candidates enter the executable registry, so an ineligible higher-precedence candidate cannot shadow trusted code.
.oracle/plan.md:33:   - `hybrid` → `rendering.legacy_hybrid`, never a renderer ID.
.oracle/plan.md:35:   - Request-sensitive fallback is permitted only by an explicit planner/fallback policy.
.oracle/plan.md:37:9. **Provenance:** provenance v2 is additive. Preserve every currently emitted v1 top-level field for the whole epic, including Remotion, hybrid, and audio-specialization fields. Add authoritative routing, trust, support, artifact, normalization, and backend-fragment data. Do not remove v1 projections without a separate external-consumer audit.
.oracle/plan.md:110:  - Do not add a renderer component root, manifest walker, `runpy` fallback, or generic component-manifest kind.
.oracle/plan.md:114:  - For installed candidates, verify the active symlink’s revision and installation trust audit; deny execution for missing, corrupt, or mismatched records. Keep such candidates inspectable for diagnosis. Do not expose staging or inactive revisions through normal discovery.
.oracle/plan.md:118:  - Register `remotion`/`ffmpeg` legacy selectors programmatically and translate `hybrid` only to a planner policy.
.oracle/plan.md:222:  - Add backend-neutral planner, fallback, finalizer, and configuration inputs.
.oracle/plan.md:251:  - Ensure plain FFmpeg, FFmpeg fast paths, audio-reactive, Remotion, and single-segment hybrid produce exactly one sidecar.
.oracle/plan.md:255:- [ ] **M1-09 — Port hybrid to a generic planner/dispatcher**
.oracle/plan.md:257:  - Extract legacy complexity/window planning as `rendering.legacy_hybrid`.
.oracle/plan.md:268:  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
.oracle/plan.md:273:  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.
.oracle/plan.md:315:  - Cover Remotion, FFmpeg, nominal-Remotion→FFmpeg, all-FFmpeg hybrid, mixed hybrid, raw renderer, invalid artifacts, and failures.
.oracle/plan.md:400:  - `validate` is static by default. Explicit conformance execution requires an execution-eligible candidate.
.oracle/plan.md:427:  - Run the complete matrix for raw-wire and SDK fixtures, trusted/untrusted discovery, built-ins, strict IDs, legacy selectors, aliases, overrides, hybrid planning, audio modes, attachments, failures, and replay.
.oracle/plan.md:432:  - Review independently at the contract/discovery, built-in extraction, generic routing/hybrid, caller migration, SDK/scaffold, and CLI/replay/docs seams.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:16:renderer that handles an entire timeline or selected hybrid segments without
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:19:existing Remotion, FFmpeg, and hybrid invocations during migration.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:36:- `render()` branches directly on `remotion`, `ffmpeg`, and `hybrid`, and
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:66:Existing hybrid test coverage is narrow: the provenance test patches the
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:86:6. A deterministic legacy-hybrid planner that preserves today's segment
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:132:1. **Backend, planner, and finalizer are distinct concepts.** `hybrid` is a
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:148:   an explicit planner policy or ordered fallback list permits it.
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:155:    `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:296:4. M1 switches the facade to generic single-backend routing, ports hybrid
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:326:8. Full Remotion, FFmpeg-only, legacy hybrid, and third-party renders emit one
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:328:9. Existing `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` CLI and
.megaplan/initiatives/pluggable-timeline-renderers/briefs/pluggable-timeline-renderers.md:385:contract/discovery, built-in extraction, generic routing/hybrid, and
docs/contracts/render-backend-v1.md:17:such as `rendering.remotion`, `rendering.legacy_hybrid`, or the canonical
docs/contracts/render-backend-v1.md:21:translated by the host; `hybrid` names a planning policy and is never a
docs/contracts/render-backend-v1.md:40:execution-eligible discovered candidate may run:
docs/contracts/render-backend-v1.md:77:ownership modes. Planner hints cover named policies and fallback support.
docs/contracts/render-backend-v1.md:331:is evidence, not routing authority: fallback happens only when an explicit
docs/contracts/render-backend-v1.md:332:planner or fallback policy permits it. Static manifest capabilities never turn
docs/contracts/render-backend-v1.md:474:have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
docs/contracts/render-backend-v1.md:574:1. **Backend, planner, and finalizer are distinct concepts.** `hybrid` is a
docs/contracts/render-backend-v1.md:590:   an explicit planner policy or ordered fallback list permits it.
docs/contracts/render-backend-v1.md:597:    `engine=remotion`, `engine=ffmpeg`, and `engine=hybrid` behavior during the

exec
/bin/zsh -lc "sed -n '240,280p' .oracle/plan.md && sed -n '300,345p' docs/contracts/render-backend-v1.md && git show C4-batch3-done:astrid/packs/rendering/executors/render/run.py | rg -n \"def _render_hybrid|for segment|engine\" | head -n 80" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    - input and artifact hashes/profiles;
    - audio ownership/completion;
    - normalization and attachments;
    - backend-owned fragments.
  - Preserve all currently emitted optional v1 keys where applicable:
    `engine`, `output`, `timeline`, `assets_registry`, `project_dir`,
    `composition_id`, `active_pack_order`, `active_theme`, `registry_hash`,
    `registry_state`, `resolved_effect_ids`, `resolved_effects`,
    `source_pack_ids`, `element_roots`, `staged_asset_ids`,
    `staged_asset_root`, `segments`, `segment_provenance`,
    `ffmpeg_specialization`, and `audio_reactive_colour`.
  - Ensure plain FFmpeg, FFmpeg fast paths, audio-reactive, Remotion, and single-segment hybrid produce exactly one sidecar.
  - Make previous-output cleanup lock-aware and conservative around corrupt/orphaned pairs; never delete unrelated output solely because a sidecar is unreadable.
  - Gate: strict qualified IDs, legacy selectors, unknown/unsupported alternatives, trust denial, aliases/overrides, output-name handling, every built-in path, sidecar compatibility, and crash recovery pass.

- [ ] **M1-09 — Port hybrid to a generic planner/dispatcher**

  - Extract legacy complexity/window planning as `rendering.legacy_hybrid`.
  - Resolve canvas/FPS once from the canonical merged theme/timeline profile.
  - Represent every segment as integer half-open frames.
  - Preserve characterized transition `duration`/`durationFrames` and handle behavior.
  - Retain effects, transitions, overlays, opacity, and fades while closing fatal gaps:
    - speed changes;
    - overlapping audio;
    - unsupported non-media clips;
    - strict-FFmpeg-invalid visual gaps/overlaps;
    - controls rejected by the selected renderer’s support report.
  - Permit FFmpeg track mute/volume after M1-06 proves exact support; fades continue to route away from FFmpeg.
  - Use renderer support reports to validate assignments rather than relying only on duplicated feature predicates.
  - Emit qualified renderer IDs, support evidence, selection reasons, input hashes, and the finalizer/profile.
  - Remove recursive calls to `render()`. The dispatcher invokes plan entries only through `RenderService`.
  - Add a deterministic mixed plan using the raw fixture renderer for one window and a built-in renderer for another.
  - Preserve legacy `segments` and nested `segment_provenance` projections while adding normalized v2 segment records, including FFmpeg segments.
  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.

- [ ] **M1-10 — Migrate every production caller and remove stale resolution**

  - Add one small attached-child invocation helper over existing executor/task primitives. It must:
    - require a validated parent project/run ID and unique step ID;
    - preserve the caller-selected output when requested;
    - scope and restore all environment changes;

```json
{
  "backend_fragments": {
    "acme.example": {
      "renderer": "example",
      "quality": "preview"
    }
  }
}
```

A fragment cannot contain any core result key, provenance v2 key, or v1
compatibility key at its top level. Such a result is rejected rather than
merged. Nested backend-private names are opaque to core. Logs must be redacted
before they cross the wire; credentials, authorization headers, signed query
strings, and secret environment values are forbidden.

## Support reporting

`SupportReport` contains:

- required integer `schema_version: 1`;
- `supported`, the request-sensitive verdict;
- ordered human-readable `reasons`;
- `features`, a string-keyed map of boolean or string evidence;
- ordered unique qualified backend `alternatives`;
- the qualified `backend` making the decision;
- nullable `backend_version`.

An unsupported report should contain at least one actionable reason. Support
is evidence, not routing authority: fallback happens only when an explicit
planner or fallback policy permits it. Static manifest capabilities never turn
an unsupported report into support. Every segment's required report must name
the same backend as the segment.

## Planning

`RenderPlan` is itself a versioned response. It contains required integer
`schema_version: 1`, the SHA-256 `request_digest`, `requested_policy`, explicit
`planner`, ordered `segments`, explicit `finalizer`, one canonical output
`profile`, `total_frames`, `reasons`, and a nullable target `window`.

`request_digest` is the SHA-256 of the canonical, JSON-normalized
`RenderRequest` payload (sorted keys, no whitespace) that produced this plan.
It is computed once by the planner/service and carried unchanged into
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
321:        return [{"engine": "ffmpeg", "from": 0.0, "to": duration}]
328:            segments.append({"engine": "ffmpeg", "from": cursor, "to": start})
330:            segments.append({"engine": "remotion", "from": start, "to": end})
333:        segments.append({"engine": "ffmpeg", "from": cursor, "to": duration})
334:    return [segment for segment in segments if float(segment["to"]) > float(segment["from"])]
354:def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
373:        and segments[0]["engine"] == "ffmpeg"
385:            engine = str(segment["engine"])
388:            segment_dir = tmp_dir / f"{index:04d}-{engine}"
392:            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
409:            if engine == "ffmpeg":
421:                    engine="remotion",
437:            engine="hybrid",
467:            metadata={"engine": "hybrid", "segments": segments},
474:            metadata={"engine": "hybrid", "segments": segments},
550:    engine: str = "remotion",
567:    if engine == "hybrid":
577:    if engine == "ffmpeg":
579:    if engine != "remotion":
580:        raise ValueError(f"Unsupported render engine: {engine}")
600:    engine: str = "remotion",
621:            engine=engine,
636:    parser.add_argument("--engine", choices=("remotion", "ffmpeg", "hybrid"), default="remotion")
663:                    engine=args.engine,
675:                engine=args.engine,

exec
/bin/zsh -lc "rg -n \"alias|override|hybrid|backend mismatch|support report named|protocol\" tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py | head -n 260 && sed -n '520,760p' tests/core/rendering/test_legacy_hybrid.py && sed -n '520,900p' tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
tests/core/rendering/test_legacy_hybrid.py:13:from astrid.packs.rendering.planners.legacy_hybrid import run as legacy_hybrid
tests/core/rendering/test_legacy_hybrid.py:19:        "theme_overrides": {
tests/core/rendering/test_legacy_hybrid.py:63:            {} if config is None else {legacy_hybrid.BACKEND_ID: config}
tests/core/rendering/test_legacy_hybrid.py:73:            legacy_hybrid.FFMPEG_ID,
tests/core/rendering/test_legacy_hybrid.py:74:            legacy_hybrid.REMOTION_ID,
tests/core/rendering/test_legacy_hybrid.py:99:    return legacy_hybrid.plan(
tests/core/rendering/test_legacy_hybrid.py:154:def test_all_ffmpeg_hybrid(tmp_path: Path) -> None:
tests/core/rendering/test_legacy_hybrid.py:242:    assert legacy_hybrid._complex_frame_windows(
tests/core/rendering/test_legacy_hybrid.py:256:    report = legacy_hybrid.support(
tests/core/rendering/test_legacy_hybrid.py:264:        legacy_hybrid.plan(
tests/core/rendering/test_legacy_hybrid.py:271:def test_raw_support_adapter_and_registered_protocol(tmp_path: Path) -> None:
tests/core/rendering/test_legacy_hybrid.py:276:    report = CommandTransport(legacy_hybrid.BACKEND_ID).run(
tests/core/rendering/test_legacy_hybrid.py:281:        cwd=Path(legacy_hybrid.__file__).resolve().parents[2],
tests/core/rendering/test_legacy_hybrid.py:290:    assert planners.get(legacy_hybrid.BACKEND_ID).manifest.operations == (
tests/core/rendering/test_legacy_hybrid.py:304:        legacy_hybrid.plan(
tests/core/rendering/test_legacy_hybrid.py:342:# T4.5 — planner routing / hybrid matrix
tests/core/rendering/test_legacy_hybrid.py:429:    result = legacy_hybrid.plan(
tests/core/rendering/test_legacy_hybrid.py:451:    result = legacy_hybrid.plan(
tests/core/rendering/test_legacy_hybrid.py:470:    assert "unknown rendering.legacy_hybrid configuration: bogus" in (
tests/core/rendering/test_service.py:13:from astrid.core.pack.alias_resolver import AliasResolver
tests/core/rendering/test_service.py:14:from astrid.core.pack.override import OverrideStore
tests/core/rendering/test_service.py:41:from astrid.packs.rendering.planners.legacy_hybrid import run as legacy_hybrid
tests/core/rendering/test_service.py:109:        protocol_version=SCHEMA_VERSION,
tests/core/rendering/test_service.py:168:        alias_chain=[],
tests/core/rendering/test_service.py:169:        override=None,
tests/core/rendering/test_service.py:175:def _planner_resolution(backend: str = "rendering.legacy_hybrid") -> PlannerResolution:
tests/core/rendering/test_service.py:220:        requested_policy="hybrid",
tests/core/rendering/test_service.py:457:        "alias",
tests/core/rendering/test_service.py:458:        "override",
tests/core/rendering/test_service.py:572:def test_hybrid_selects_planner_and_executes_its_segment(tmp_path: Path) -> None:
tests/core/rendering/test_service.py:579:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:584:        selector="hybrid",
tests/core/rendering/test_service.py:585:        out_path=tmp_path / "hybrid.mp4",
tests/core/rendering/test_service.py:589:        ("support", "rendering.legacy_hybrid"),
tests/core/rendering/test_service.py:590:        ("plan", "rendering.legacy_hybrid"),
tests/core/rendering/test_service.py:615:        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
tests/core/rendering/test_service.py:628:    service.render_request(request, selector="hybrid", out_path=output)
tests/core/rendering/test_service.py:653:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:658:        service.render_request(_request(tmp_path), selector="hybrid", out_path=output)
tests/core/rendering/test_service.py:680:def test_alias_then_override_changes_resolved_winner(tmp_path: Path) -> None:
tests/core/rendering/test_service.py:681:    alias = AliasResolver()
tests/core/rendering/test_service.py:682:    alias.register_alias("acme.alias", "acme.original")
tests/core/rendering/test_service.py:683:    overrides = OverrideStore(tmp_path / "override-project")
tests/core/rendering/test_service.py:684:    overrides.set_override("renderer", "acme.original", "acme.winner")
tests/core/rendering/test_service.py:687:        alias_resolver=alias,
tests/core/rendering/test_service.py:688:        override_store=overrides,
tests/core/rendering/test_service.py:697:    output = tmp_path / "alias.mp4"
tests/core/rendering/test_service.py:700:        _request(tmp_path), selector="acme.alias", out_path=output
tests/core/rendering/test_service.py:706:    assert resolution["alias_chain"] == ["acme.alias", "acme.original"]
tests/core/rendering/test_service.py:707:    assert resolution["override"] == {
tests/core/rendering/test_service.py:861:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:866:        _request(tmp_path), selector="hybrid", out_path=output
tests/core/rendering/test_service.py:898:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:903:    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)
tests/core/rendering/test_service.py:924:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:933:    service.render_request(request, selector="hybrid", out_path=output)
tests/core/rendering/test_service.py:975:# T4.5 — routing / hybrid matrix
tests/core/rendering/test_service.py:983:def _hybrid_timeline(*, fps: int = 24) -> dict[str, Any]:
tests/core/rendering/test_service.py:987:        "theme_overrides": {
tests/core/rendering/test_service.py:1017:def _hybrid_request(
tests/core/rendering/test_service.py:1035:            {} if config is None else {"rendering.legacy_hybrid": config}
tests/core/rendering/test_service.py:1072:    timeline = _hybrid_timeline()
tests/core/rendering/test_service.py:1073:    request = _hybrid_request(tmp_path, timeline, config=config)
tests/core/rendering/test_service.py:1074:    transport.plan = legacy_hybrid.plan(
tests/core/rendering/test_service.py:1095:        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
tests/core/rendering/test_service.py:1174:        "hybrid_plan",
tests/core/rendering/test_service.py:1228:            "hybrid",
tests/core/rendering/test_service.py:1231:                ("support", "rendering.legacy_hybrid"),
tests/core/rendering/test_service.py:1232:                ("plan", "rendering.legacy_hybrid"),
tests/core/rendering/test_service.py:1236:            "hybrid",
tests/core/rendering/test_service.py:1248:        "hybrid",
tests/core/rendering/test_service.py:1254:    hybrid_plan: bool,
tests/core/rendering/test_service.py:1262:    if hybrid_plan:
tests/core/rendering/test_service.py:1268:            planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:1341:def test_alias_and_override_to_trust_denied_only_target_is_structured(
tests/core/rendering/test_service.py:1344:    alias = AliasResolver()
tests/core/rendering/test_service.py:1345:    alias.register_alias("acme.alias", "acme.original")
tests/core/rendering/test_service.py:1346:    overrides = OverrideStore(tmp_path / "override-project")
tests/core/rendering/test_service.py:1347:    overrides.set_override("renderer", "acme.original", "acme.denied")
tests/core/rendering/test_service.py:1350:        alias_resolver=alias,
tests/core/rendering/test_service.py:1351:        override_store=overrides,
tests/core/rendering/test_service.py:1364:            selector="acme.alias",
tests/core/rendering/test_service.py:1389:    assert error.details["legacy_selectors"] == ["remotion", "ffmpeg", "hybrid"]
tests/core/rendering/test_service.py:1420:    assert caught.value.error.kind == "protocol"
tests/core/rendering/test_service.py:1487:        ("hybrid", (10,), {}, False, "hybrid"),
tests/core/rendering/test_service.py:1488:        ("hybrid", (5, 5), {}, True, "hybrid"),
tests/core/rendering/test_service.py:1495:        "hybrid-single-segment",
tests/core/rendering/test_service.py:1496:        "hybrid-multi-segment",
tests/core/rendering/test_service.py:1514:            planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:1557:    service.render_request(request, selector="hybrid", out_path=output)
tests/core/rendering/test_service.py:1582:    assert payload["routing"]["requested_engine"] == "hybrid"
tests/core/rendering/test_service.py:1600:    service.render_request(request, selector="hybrid", out_path=output)
tests/core/rendering/test_service.py:1641:        ("hybrid", (10,), AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
tests/core/rendering/test_service.py:1642:        ("hybrid", (10,), AudioOwnership.NONE, AudioOwnership.NONE, False),
tests/core/rendering/test_service.py:1643:        ("hybrid", (10,), AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
tests/core/rendering/test_service.py:1652:        "hybrid-rendered",
tests/core/rendering/test_service.py:1653:        "hybrid-none",
tests/core/rendering/test_service.py:1654:        "hybrid-passthrough",
tests/core/rendering/test_service.py:1684:            planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:1704:        "hybrid" if plan_segments is not None else selector
tests/core/rendering/test_service.py:1718:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:1724:            _request(tmp_path), selector="hybrid", out_path=output
tests/core/rendering/test_service.py:1795:        planner_ids=("rendering.legacy_hybrid",),
tests/core/rendering/test_service.py:1799:    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
        service.render_request(
            _request(tmp_path),
            selector="remotion",
            out_path=tmp_path / "legacy-remotion.mp4",
        )

    assert ("render", "rendering.ffmpeg") in transport.calls
    assert ("render", "rendering.remotion") not in transport.calls


def test_legacy_remotion_falls_back_when_ffmpeg_declines_support(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.support["rendering.ffmpeg"] = _support(
        "rendering.ffmpeg",
        supported=False,
        alternatives=["rendering.remotion"],
    )
    service = _service(tmp_path, transport)

    service.render_request(
        _request(tmp_path),
        selector="remotion",
        out_path=tmp_path / "legacy-remotion-fallback.mp4",
    )

    assert transport.calls == [
        ("support", "rendering.ffmpeg"),
        ("support", "rendering.remotion"),
        ("render", "rendering.remotion"),
    ]


def test_legacy_ffmpeg_is_strict(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    service.render_request(
        _request(tmp_path),
        selector="ffmpeg",
        out_path=tmp_path / "legacy-ffmpeg.mp4",
    )

    assert transport.calls == [
        ("support", "rendering.ffmpeg"),
        ("render", "rendering.ffmpeg"),
    ]


def test_hybrid_selects_planner_and_executes_its_segment(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window")
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )

    service.render_request(
        _request(tmp_path),
        selector="hybrid",
        out_path=tmp_path / "hybrid.mp4",
    )

    assert transport.calls[:2] == [
        ("support", "rendering.legacy_hybrid"),
        ("plan", "rendering.legacy_hybrid"),
    ]
    assert ("render", "fixture.window") in transport.calls
    assert ("finalize", "rendering.ffmpeg-finalizer") not in transport.calls


def test_planned_window_is_materialized_for_full_timeline_renderer(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.full")
    renderers = RendererRegistry(
        [
            _candidate(
                tmp_path,
                "fixture.full",
                "renderer",
                capabilities={
                    "supports_full_timeline": True,
                    "supports_windows": False,
                },
            )
        ]
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    service = RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )
    output = tmp_path / "materialized-window.mp4"
    request = _request(tmp_path)

    service.render_request(request, selector="hybrid", out_path=output)

    renderer_payloads = [
        payload
        for verb, backend, payload in transport.payloads
        if backend == "fixture.full" and verb in {"support", "render"}
    ]
    assert len(renderer_payloads) == 2
    assert all(payload["window"] is None for payload in renderer_payloads)
    assert all(
        payload["timeline_path"] != request.timeline_path
        for payload in renderer_payloads
    )
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    assert "materialized_timeline" in sidecar["segments_v2"][0]["input_hashes"]


def test_planned_segment_duration_mismatch_is_rejected(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window")
    transport.render_frames["fixture.window"] = 3
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "wrong-duration.mp4"

    with pytest.raises(RendererInvalidArtifactError, match="planned frame window"):
        service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    assert not output.exists()
    assert not list(tmp_path.glob(".wrong-duration.mp4.render-service-*"))


def test_unknown_backend_is_structured_and_lists_alternatives(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="missing.renderer",
            out_path=tmp_path / "missing.mp4",
        )

    assert caught.value.error.kind == "unsupported"
    assert "rendering.remotion" in caught.value.error.details["alternatives"]
    assert caught.value.error.recovery_command


def test_alias_then_override_changes_resolved_winner(tmp_path: Path) -> None:
    alias = AliasResolver()
    alias.register_alias("acme.alias", "acme.original")
    overrides = OverrideStore(tmp_path / "override-project")
    overrides.set_override("renderer", "acme.original", "acme.winner")
    renderers = RendererRegistry(
        [_candidate(tmp_path, "acme.winner", "renderer")],
        alias_resolver=alias,
        override_store=overrides,
    )
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=(),
        renderer_registry=renderers,
    )
    output = tmp_path / "alias.mp4"

    service.render_request(
        _request(tmp_path), selector="acme.alias", out_path=output
    )

    assert ("render", "acme.winner") in transport.calls
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    resolution = sidecar["segments_v2"][0]["renderer"]
    assert resolution["alias_chain"] == ["acme.alias", "acme.original"]
    assert resolution["override"] == {
        "from": "acme.original",
        "to": "acme.winner",
    }


def test_execution_ineligible_candidate_is_denied(tmp_path: Path) -> None:
    renderers = RendererRegistry(
        [_candidate(tmp_path, "denied.renderer", "renderer", eligible=False)]
    )
    transport = FakeTransport()
    service = _service(
        tmp_path,
        transport,
        renderer_ids=(),
        renderer_registry=renderers,
    )

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="denied.renderer",
            out_path=tmp_path / "denied.mp4",
        )

    registry_error = caught.value.error.details["registry_error"]
    assert registry_error["code"] == "execution_ineligible"
    assert transport.calls == []


def test_unsupported_support_report_is_structured_with_reported_alternative(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.support["rendering.ffmpeg"] = _support(
        "rendering.ffmpeg",
        supported=False,
        alternatives=["rendering.remotion"],
    )
    service = _service(tmp_path, transport)

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="rendering.ffmpeg",
            out_path=tmp_path / "unsupported.mp4",
        )

    assert caught.value.error.details["alternatives"] == ["rendering.remotion"]
    assert caught.value.error.details["reasons"] == [
        "fixture timeline is unsupported"
    ]


def test_renderer_without_support_operation_fails_closed_on_missing_hints(
    tmp_path: Path,
) -> None:
    renderers = RendererRegistry(
        [
            _candidate(
                tmp_path,
                "fixture.static",
                "renderer",
                operations=("render",),
                capabilities={},
            )
        ]
    )
    transport = FakeTransport()
    service = RenderService(
        registries=(renderers, PlannerRegistry(), FinalizerRegistry()),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )

    with pytest.raises(RendererUnsupportedError) as caught:
        service.render_request(
            _request(tmp_path),
            selector="fixture.static",
            out_path=tmp_path / "static.mp4",
        )

    assert "full timelines" in " ".join(caught.value.error.details["reasons"])
    assert transport.calls == []


@pytest.mark.parametrize(
    "ownership", [AudioOwnership.PASSTHROUGH, AudioOwnership.NONE]
)
def test_host_audio_completion_handles_visual_only_modes(
    tmp_path: Path,
    ownership: AudioOwnership,
) -> None:
    transport = FakeTransport()
    completed: list[AudioOwnership] = []

    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        completed.append(result.audio_ownership)
        if result.audio_ownership is AudioOwnership.PASSTHROUGH:
            return replace(
                result,
                video=replace(
                    result.video,
                    profile=_profile(audio=True),
                    audio=AudioOwnership.RENDERED,
                ),
                audio_ownership=AudioOwnership.RENDERED,
            )
        return result

    service = _service(tmp_path, transport, audio_completer=audio_completer)
    output = tmp_path / f"{ownership.value}.mp4"

    service.render_request(
        _request(tmp_path, audio=ownership),
        selector="rendering.ffmpeg",
        out_path=output,
    )

    assert completed == [ownership]
    sidecar = json.loads(Path(f"{output}.provenance.json").read_text(encoding="utf-8"))
    expected = (
        AudioOwnership.RENDERED
        if ownership is AudioOwnership.PASSTHROUGH
        else AudioOwnership.NONE
    )
    assert sidecar["audio_ownership"] == expected.value


def test_passthrough_audio_cannot_publish_without_host_completion(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "incomplete-passthrough.mp4"

    with pytest.raises(RendererUnsupportedError, match="audio completer"):
        service.render_request(
            _request(tmp_path, audio=AudioOwnership.PASSTHROUGH),
            selector="rendering.ffmpeg",
            out_path=output,
        )

    assert not output.exists()
    assert not Path(f"{output}.provenance.json").exists()


def test_multiple_segments_run_registered_finalizer(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "finalized.mp4"

    service.render_request(
        _request(tmp_path), selector="hybrid", out_path=output
    )

    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")


def test_multiple_segments_defer_audio_completion_until_after_finalizer(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    transport.render_ownership["fixture.window"] = AudioOwnership.PASSTHROUGH
    transport.finalize_ownership = AudioOwnership.PASSTHROUGH
    completions: list[str] = []

    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        completions.append(result.video.path)
        return replace(
            result,
            video=replace(
                result.video,
                profile=_profile(audio=True),
                audio=AudioOwnership.RENDERED,
            ),
            audio_ownership=AudioOwnership.RENDERED,
        )

    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
        audio_completer=audio_completer,
    )

exec
/bin/zsh -lc "rg -n \"attachment\" docs/contracts/render-backend-v1.md .oracle/plan.md astrid/core/rendering/publication.py tests/core/rendering/test_publication.py | head -n 220 && sed -n '1700,1810p' astrid/core/rendering/contracts.py && sed -n '1740,1815p' tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
docs/contracts/render-backend-v1.md:78:Finalizer hints cover containers, attachment preservation, audio modes, and
docs/contracts/render-backend-v1.md:250:- optional named attachments (default `{}`).
docs/contracts/render-backend-v1.md:282:`VideoArtifact.attachments` is the one authoritative attachment surface;
docs/contracts/render-backend-v1.md:283:`RenderResult` has no second attachment map. Names must be globally unique
docs/contracts/render-backend-v1.md:286:input attachment's name, path, kind, and hash unchanged. A finalizer may add a
docs/contracts/render-backend-v1.md:287:new attachment, and a custom finalizer may interpret a kind only when its
docs/contracts/render-backend-v1.md:289:input attachment.
docs/contracts/render-backend-v1.md:294:attachments), qualified-ID-keyed `backend_fragments`, explicit
docs/contracts/render-backend-v1.md:297:`attachments` member is invalid rather than a compatibility alias.
docs/contracts/render-backend-v1.md:394:to finalizers. Before invocation, the host rejects any attachment name reused
docs/contracts/render-backend-v1.md:396:attachment map contains the unchanged union of all input attachments;
docs/contracts/render-backend-v1.md:397:additional globally unique finalizer-created attachments are permitted.
docs/contracts/render-backend-v1.md:405:attachments it does not understand. The first built-in finalizer uses FFmpeg;
docs/contracts/render-backend-v1.md:455:calling capability owns run attachment. Invocation workspaces, localized
docs/contracts/render-backend-v1.md:469:`attachments`, and `backend_fragments`.
docs/contracts/render-backend-v1.md:485:`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
docs/contracts/render-backend-v1.md:487:names across all segment artifacts. All plan, artifact, and attachment values
docs/contracts/render-backend-v1.md:490:duplicate attachment names, path escapes, invalid kinds, profile-only entries,
docs/contracts/render-backend-v1.md:622:18. **Primary video is required; attachments are extensible.** V1 planners and
docs/contracts/render-backend-v1.md:623:    finalizers operate on a validated primary video. Optional named attachments
.oracle/plan.md:9:5. **Aliases and overrides:** extend pack-schema and normalizer alias-kind allowlists for `renderer`, `planner`, and `finalizer`, while keeping bare legacy names programmatic. Resolution is alias → canonical ID → override target → registry winner. Wire `OverrideStore` during default registry construction rather than CLI-only post-attachment.
.oracle/plan.md:17:   - never invoke a bare nested `astrid executors run` without attachment context.
.oracle/plan.md:84:    - primary `VideoArtifact`, named attachments, and `RenderResult`;
.oracle/plan.md:89:  - Require one primary video. Preserve uniquely named, contained attachments without requiring the default finalizer to understand them.
.oracle/plan.md:102:  - Gate: Python DTOs and raw JSON fixtures round-trip identically; unknown versions, invalid frame bounds, duplicate attachments, traversal, and backend attempts to overwrite core fields fail structurally.
.oracle/plan.md:154:  - Gate: local/cached/remote assets, Range requests, expired URLs, restricted serving, server-start failure, cleanup, invalid artifacts, visual-only modes, attachments, and crash-orphan recovery pass.
.oracle/plan.md:207:  - Record every normalization and preserve named attachments unchanged.
.oracle/plan.md:242:    - normalization and attachments;
.oracle/plan.md:273:  - Gate: empty/single/multiple windows, handle merging, frame rounding, transition units, 24 FPS theme canvas, speed/audio overlap, track audio controls, non-media clips, all-FFmpeg hybrid, mixed fixture hybrid, segment failure cleanup, attachments, and final provenance alignment pass.
.oracle/plan.md:323:  - Complete `docs/contracts/render-backend-v1.md`: extension shape, trust eligibility, permission limitations, manifests, protocol, support, assets, media/audio, planning, finalization, run ownership, errors, attachments, provenance, cleanup, and versioning.
.oracle/plan.md:361:  - Provide allocated output/work paths, descriptor-based local path/URL access, declared-permission checks, sanitized subprocess execution, redacted logging/progress, read-only interruption state, probing, hashing, completion, attachments, and cleanup.
.oracle/plan.md:369:    - named attachment;
.oracle/plan.md:421:  - Document trust, disclosure-only permissions, selection, aliases/overrides, backend configuration, assets, output/audio/attachments, cleanup, diagnostics, replay/redaction, and legacy selectors.
.oracle/plan.md:427:  - Run the complete matrix for raw-wire and SDK fixtures, trusted/untrusted discovery, built-ins, strict IDs, legacy selectors, aliases, overrides, hybrid planning, audio modes, attachments, failures, and replay.
.oracle/plan.md:450:- Task attachment requires a matching project, run ID, and step ID. The helper must scope environment changes and avoid process-global mutation during concurrent in-process work.
.oracle/plan.md:451:- Preserving a caller-selected output during task attachment relies on the existing attached/auto-resolved request semantics; tests must prevent this from regressing into `--project`/`--out` rejection or a new run.
                details={"error_type": type(exc).__name__},
            )


@dataclass(frozen=True)
class FinalizeRequest:
    """Wire request consumed by the ``finalize`` operation."""

    schema_version: int
    plan: RenderPlan
    artifacts: list[VideoArtifact]
    output_name: str
    backend_config: BackendConfig = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        version = _require_schema_version(self.schema_version, "finalize request")
        plan = (
            self.plan
            if isinstance(self.plan, RenderPlan)
            else RenderPlan.from_dict(_require_mapping(self.plan, "plan"))
        )
        if isinstance(self.artifacts, (str, bytes)) or not isinstance(self.artifacts, Sequence):
            raise TypeError("artifacts must be an array")
        artifacts = [
            artifact
            if isinstance(artifact, VideoArtifact)
            else VideoArtifact.from_dict(_require_mapping(artifact, f"artifacts[{index}]"))
            for index, artifact in enumerate(self.artifacts)
        ]
        if len(artifacts) != len(plan.segments):
            raise ValueError("finalize artifacts must correspond one-for-one with plan segments")
        if plan.total_frames == 0:
            raise ValueError("an empty render plan must not be finalized")
        attachment_names: set[str] = set()
        for index, artifact in enumerate(artifacts):
            duplicates = sorted(attachment_names & set(artifact.attachments))
            if duplicates:
                raise ValueError(
                    "duplicate attachment names across segment artifacts at "
                    f"artifacts[{index}]: {', '.join(duplicates)}"
                )
            attachment_names.update(artifact.attachments)
        output_name = _require_string(self.output_name, "output_name")
        if not _OUTPUT_NAME_RE.fullmatch(output_name) or output_name in {".", ".."}:
            raise ValueError("output_name must be a portable basename without path separators")
        object.__setattr__(self, "schema_version", version)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "output_name", output_name)
        backend_config = _coerce_namespaced_backend_config(
            self.backend_config,
            "backend_config",
        )
        unexpected_config = sorted(set(backend_config) - {plan.finalizer.id})
        if unexpected_config:
            raise ValueError(
                "finalize backend_config may contain only the selected finalizer namespace "
                f"{plan.finalizer.id!r}"
            )
        object.__setattr__(self, "backend_config", backend_config)
        object.__setattr__(self, "metadata", _require_string_mapping(self.metadata, "metadata"))

    @property
    def expected_attachments(self) -> dict[str, Attachment]:
        """Return the globally unique attachments a finalizer must preserve."""

        return {
            name: attachment
            for artifact in self.artifacts
            for name, attachment in artifact.attachments.items()
        }

    def validate_final_result(
        self,
        result: RenderResult | Mapping[str, Any],
    ) -> RenderResult:
        """Validate attachment preservation on a standalone finalizer response.

        Finalizers may add new attachments, but every input attachment must be
        present under the same name with the exact same descriptor and digest.
        """

        final_result = (
            result
            if isinstance(result, RenderResult)
            else RenderResult.from_dict(_require_mapping(result, "final result"))
        )
        missing = sorted(set(self.expected_attachments) - set(final_result.attachments))
        if missing:
            raise ValueError("finalizer dropped attachments: " + ", ".join(missing))
        changed = sorted(
            name
            for name, expected in self.expected_attachments.items()
            if final_result.attachments[name] != expected
        )
        if changed:
            raise ValueError("finalizer changed attachments: " + ", ".join(changed))
        return final_result

    def to_dict(self) -> dict[str, Any]:
        return _json_safe_mapping(
            {
                "schema_version": self.schema_version,
                "plan": self.plan,
                "artifacts": self.artifacts,
                "output_name": self.output_name,
                "backend_config": self.backend_config,
                "metadata": self.metadata,
            }
        )
    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
        )

    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_renderer_attachments_survive_validation_into_committed_provenance(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.render_attachments["rendering.ffmpeg"] = {
        "storyboard.png": b"png-bytes",
        "captions.srt": b"srt-bytes",
    }
    service = _service(tmp_path, transport)
    output = tmp_path / "attachments.mp4"

    service.render_request(
        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
    )

    payload = _sidecar(output)
    assert set(payload["attachments"]) == {"storyboard.png", "captions.srt"}
    assert payload["attachments"]["storyboard.png"]["sha256"] == hashlib.sha256(
        b"png-bytes"
    ).hexdigest()
    assert payload["attachments"]["storyboard.png"]["kind"] == "fixture"
    assert payload["attachments"]["storyboard.png"]["path"].endswith(
        "storyboard.png"
    )
    assert len(payload["artifact_profiles"]) == 1
    assert set(payload["artifact_profiles"][0]["attachments"]) == {
        "storyboard.png",
        "captions.srt",
    }


def test_finalizer_preserves_segment_attachments_and_adds_its_own(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.render_attachments["fixture.window"] = [
        {"segment-a.txt": b"first-segment"},
        {"segment-b.txt": b"second-segment"},
    ]
    transport.finalize_attachments = {"final-note.txt": b"final"}
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "finalized-attachments.mp4"

    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)

    payload = _sidecar(output)
    assert set(payload["attachments"]) == {
        "segment-a.txt",
        "segment-b.txt",
        "final-note.txt",
    }
    assert len(payload["artifact_profiles"]) == 2
    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}


def test_audio_completer_dropping_attachments_is_rejected(tmp_path: Path) -> None:
    transport = FakeTransport()
    transport.render_attachments["rendering.ffmpeg"] = {"must-survive.txt": b"x"}


exec
/bin/zsh -lc "sed -n '440,505p' docs/contracts/render-backend-v1.md && sed -n '270,305p' docs/contracts/render-backend-v1.md && sed -n '1,300p' astrid/core/rendering/publication.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
sequence form (one VideoArtifact or emitted lineage record per segment, in
segment order); single-segment plans may use a path-keyed mapping. Emitted
lineage records round-trip (re-passing them validates identically) and every
record MUST carry a non-empty string `path` (missing, `None`, or numeric
paths are rejected). Every record carries `profile`, a validated 64-hex string
`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and globally unique
names across all segment artifacts. All plan, artifact, and attachment values
are reconstructed through their DTO validators at the provenance boundary
(mutated frozen instances cannot bypass validation); duplicate paths,
duplicate attachment names, path escapes, invalid kinds, profile-only entries,
null/malformed hashes, and cardinality mismatches are rejected. All JSON
Schema patterns are language-neutral (ECMAScript-valid; no Python-only
anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
by the DTO and schemas — Python and non-Python validators agree on every
character including `\u0085`, `\uFEFF`, and the `\u2000-\u200a` block. Replay
can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
only, never rendered outputs.

`engine` is only the legacy request projection. The `segments` key keeps the
V1-compatible flat projection: one `{engine, from, to}` entry per segment,
derived from `renderer.id` and the validated integer `FrameWindow` at its
rational FPS — exactly the shape legacy consumers read. The additive
`segments_v2` key carries the complete normalized v2 segment records
(`window`, `renderer` resolution, `input_hashes`); it never overwrites or
reshapes a V1 key. When the v1 `segment_provenance` top-level projection
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
input attachment's name, path, kind, and hash unchanged. A finalizer may add a
new attachment, and a custom finalizer may interpret a kind only when its
contract explicitly says so, but it may not silently drop, rename, or mutate an
input attachment.

## Successful render result

`RenderResult` has `schema_version: 1`, the primary `video` (including its
attachments), qualified-ID-keyed `backend_fragments`, explicit
`audio_ownership`, `normalization` descriptions, redacted `logs`, and string
`metadata`. Successful result fields are core-owned. A top-level result
`attachments` member is invalid rather than a compatibility alias.

Backend fragments are JSON objects beneath their qualified namespace:

```json
{
  "backend_fragments": {
    "acme.example": {
      "renderer": "example",
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

exec
/bin/zsh -lc "sed -n '130,330p' tests/core/rendering/test_legacy_hybrid.py && sed -n '342,510p' tests/core/rendering/test_legacy_hybrid.py && rg -n \"empty\" tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 0ms:
            _media(duration=10),
            {
                "id": "title",
                "at": 4,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )
    result = _plan(tmp_path, timeline)

    windows = [
        (item.window.start_frame, item.window.end_frame, item.renderer.id)
        for item in result.segments
    ]
    assert windows == [
        (0, 112, "rendering.ffmpeg"),
        (112, 158, "rendering.remotion"),
        (158, 300, "rendering.ffmpeg"),
    ]
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))


def test_all_ffmpeg_hybrid(tmp_path: Path) -> None:
    result = _plan(
        tmp_path,
        _timeline(clips=[_media(duration=3)]),
        config={"renderers": ["rendering.ffmpeg"]},
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "rendering.ffmpeg"
    ]


def test_mixed_raw_fixture_and_builtin_plan(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=6),
            {
                "id": "builtin-title",
                "at": 2,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )
    result = _plan(
        tmp_path,
        timeline,
        config={
            "simple_renderers": ["raw_command.renderer"],
            "complex_renderers": ["rendering.remotion"],
        },
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]


def test_frame_rounding_is_integer_and_exactly_tiles(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=2.01),
            {
                "id": "card",
                "at": 0.5,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ],
        fps=[30000, 1001],
    )
    result = _plan(tmp_path, timeline)

    assert result.total_frames == 61
    assert all(type(value) is int for segment in result.segments for value in (
        segment.window.start_frame,
        segment.window.end_frame,
    ))
    assert result.segments[0].window.start_frame == 0
    assert result.segments[-1].window.end_frame == result.total_frames
    assert all(
        left.window.end_frame == right.window.start_frame
        for left, right in zip(result.segments, result.segments[1:])
    )


@pytest.mark.parametrize(
    ("transition", "expected"),
    [
        ({"type": "crossfade"}, (44, 76)),
        ({"duration": 0.5, "durationFrames": 12}, (37, 83)),
        ({"durationFrames": 12}, (40, 80)),
    ],
)
def test_transition_units_and_handles_are_preserved(
    transition: dict, expected: tuple[int, int]
) -> None:
    timeline = _timeline(
        clips=[
            _media("left", duration=2, transition=transition),
            _media("right", at=2, duration=2),
        ]
    )

    assert legacy_hybrid._complex_frame_windows(
        timeline, Fraction(30, 1)
    ) == [expected]


def test_support_rejects_speed_and_overlapping_audio(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=4),
            _media("fast", at=0, duration=2, speed=2),
            _media("audio-a", at=0, duration=2, track="a"),
            _media("audio-b", at=1, duration=2, track="a"),
        ]
    )
    report = legacy_hybrid.support(
        _request(tmp_path, timeline), workspace=tmp_path
    )

    assert report.supported is False
    assert any("speed" in reason for reason in report.reasons)
    assert any("Overlapping audio" in reason for reason in report.reasons)
    with pytest.raises(RendererUnsupportedError):
        legacy_hybrid.plan(
            _request(tmp_path, timeline),
            workspace=tmp_path,
            support_resolver=_resolver(),
        )


def test_raw_support_adapter_and_registered_protocol(tmp_path: Path) -> None:
    request = _request(tmp_path, _timeline(clips=[_media(duration=1)]))
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")
    report = CommandTransport(legacy_hybrid.BACKEND_ID).run(
        "support",
        ["python3", "run.py"],
        request_path=request_path,
        result_path=result_path,
        cwd=Path(legacy_hybrid.__file__).resolve().parents[2],
    )

    assert isinstance(report, SupportReport)
    assert report.supported is True
    renderers, planners, finalizers = load_default_registries(
        Path(__file__).resolve().parents[3], include_installed=False
    )
    assert renderers.get("rendering.ffmpeg").id == "rendering.ffmpeg"
    assert planners.get(legacy_hybrid.BACKEND_ID).manifest.operations == (
        "plan",
        "support",
    )
    assert finalizers.get("rendering.ffmpeg-finalizer").id == (
        "rendering.ffmpeg-finalizer"
    )


def test_assignment_failure_is_structured_and_leaves_no_segment_artifacts(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, _timeline(clips=[_media(duration=1)]))
    with pytest.raises(RendererUnsupportedError) as caught:
        legacy_hybrid.plan(
            request,
            workspace=tmp_path,
            support_resolver=_resolver(set()),
        )

    assert caught.value.error.kind == "unsupported"
    assert not list(tmp_path.rglob("segment-*.mp4"))
    assert not list(tmp_path.glob("*.provenance.json"))


def test_segment_order_is_provenance_alignment_order(tmp_path: Path) -> None:
    result = _plan(
        tmp_path,
        _timeline(
            clips=[
                _media(duration=5),
                {
                    "id": "card",
                    "at": 2,
                    "track": "v",
                    "clipType": "text-card",
                    "hold": 1,
                },
            ]
        ),
    )
# T4.5 — planner routing / hybrid matrix
# ---------------------------------------------------------------------------


def _complex_timeline() -> dict:
    """Media plus an overlapping text-card: simple/complex/simple windows."""
    return _timeline(
        clips=[
            _media(duration=6),
            {
                "id": "title",
                "at": 2,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        # Defaults: ffmpeg for simple windows, remotion for complex.
        (
            None,
            ["rendering.ffmpeg", "rendering.remotion", "rendering.ffmpeg"],
        ),
        # A common renderers list applies to every window kind.
        (
            {"renderers": ["rendering.remotion"]},
            ["rendering.remotion", "rendering.remotion", "rendering.remotion"],
        ),
        # The raw fixture (Batch 2) is a simple renderer; remotion owns complex.
        (
            {
                "simple_renderers": ["raw_command.renderer"],
                "complex_renderers": ["rendering.remotion"],
            },
            ["raw_command.renderer", "rendering.remotion", "raw_command.renderer"],
        ),
        # First supported renderer in a list wins per window kind.
        (
            {
                "simple_renderers": ["rendering.ffmpeg", "raw_command.renderer"],
                "complex_renderers": ["rendering.remotion"],
            },
            ["rendering.ffmpeg", "rendering.remotion", "rendering.ffmpeg"],
        ),
    ],
    ids=[
        "defaults",
        "common-renderers",
        "raw-simple-remotion-complex",
        "first-supported-wins",
    ],
)
def test_planner_renderer_assignment_matrix(
    tmp_path: Path, config: dict | None, expected: list[str]
) -> None:
    result = _plan(tmp_path, _complex_timeline(), config=config)

    assert [segment.renderer.id for segment in result.segments] == expected
    windows = [
        (segment.window.start_frame, segment.window.end_frame)
        for segment in result.segments
    ]
    assert windows[0][0] == 0
    assert windows[-1][1] == result.total_frames
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
    assert all(
        segment.renderer.support_decision.supported is True
        for segment in result.segments
    )
    assert result.finalizer.id == "rendering.ffmpeg-finalizer"


def test_planner_falls_back_to_next_supported_simple_renderer(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        _timeline(clips=[_media(duration=2)]),
        config={
            "simple_renderers": ["rendering.ffmpeg", "raw_command.renderer"]
        },
    )
    result = legacy_hybrid.plan(
        request,
        workspace=tmp_path,
        support_resolver=_resolver(supported={"raw_command.renderer"}),
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "raw_command.renderer"
    ]


def test_planner_falls_back_to_next_supported_complex_renderer(
    tmp_path: Path,
) -> None:
    request = _request(
        tmp_path,
        _complex_timeline(),
        config={
            "simple_renderers": ["rendering.ffmpeg"],
            "complex_renderers": ["rendering.remotion", "rendering.ffmpeg"],
        },
    )
    result = legacy_hybrid.plan(
        request,
        workspace=tmp_path,
        support_resolver=_resolver(
            supported={"rendering.ffmpeg", "raw_command.renderer"}
        ),
    )

    assert [segment.renderer.id for segment in result.segments] == [
        "rendering.ffmpeg",
        "rendering.ffmpeg",
        "rendering.ffmpeg",
    ]


def test_planner_rejects_unknown_config_keys(tmp_path: Path) -> None:
    with pytest.raises(RendererUnsupportedError) as caught:
        _plan(tmp_path, _complex_timeline(), config={"bogus": True})

    assert "unknown rendering.legacy_hybrid configuration: bogus" in (
        caught.value.error.details["reasons"]
    )


def test_planner_rejects_empty_renderer_lists(tmp_path: Path) -> None:
    with pytest.raises(RendererUnsupportedError) as caught:
        _plan(tmp_path, _complex_timeline(), config={"renderers": []})
    assert "renderers must not be empty" in caught.value.error.details["reasons"]

    with pytest.raises(RendererUnsupportedError) as caught:
        _plan(
            tmp_path,
            _complex_timeline(),
            config={"simple_renderers": [], "complex_renderers": []},
        )
    assert "simple_renderers must not be empty" in caught.value.error.details["reasons"]


def test_planner_single_segment_is_one_full_timeline_window(
    tmp_path: Path,
) -> None:
    result = _plan(tmp_path, _timeline(clips=[_media(duration=3)]))

    assert len(result.segments) == 1
    segment = result.segments[0]
    assert (segment.window.start_frame, segment.window.end_frame) == (
        0,
        result.total_frames,
    )
    assert result.reasons == {"0": "simple legacy window assigned to rendering.ffmpeg by supported report"}
    assert result.window is None

exec
/bin/zsh -lc "sed -n '1,140p' tests/core/rendering/test_legacy_hybrid.py && rg -n \"zero|empty\" tests/core/rendering/test_legacy_hybrid.py tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from astrid.core.rendering.contracts import RenderPlan, RenderRequest, SupportReport
from astrid.core.rendering.errors import RendererUnsupportedError
from astrid.core.rendering.registry import load_default_registries
from astrid.core.rendering.transport import CommandTransport
from astrid.packs.rendering.planners.legacy_hybrid import run as legacy_hybrid


def _timeline(*, clips: list[dict] | None = None, fps: int | list[int] = 30) -> dict:
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": fps}}
        },
        "tracks": [
            {"id": "v", "kind": "visual"},
            {"id": "a", "kind": "audio"},
        ],
        "clips": clips or [],
    }


def _media(
    clip_id: str = "media",
    *,
    at: float = 0,
    duration: float = 4,
    track: str = "v",
    **extra: object,
) -> dict:
    return {
        "id": clip_id,
        "at": at,
        "track": track,
        "clipType": "media",
        "asset": "source",
        "from": 0,
        "to": duration,
        "speed": 1,
        "volume": 0,
        **extra,
    }


def _request(tmp_path: Path, timeline: dict, *, config: dict | None = None) -> RenderRequest:
    timeline_path = tmp_path / "timeline.json"
    assets_path = tmp_path / "assets.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    assets_path.write_text(json.dumps({"assets": {}}), encoding="utf-8")
    return RenderRequest(
        schema_version=1,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="video.mp4",
        backend_config=(
            {} if config is None else {legacy_hybrid.BACKEND_ID: config}
        ),
    )


def _resolver(
    supported: set[str] | None = None,
):
    accepted = (
        {
            legacy_hybrid.FFMPEG_ID,
            legacy_hybrid.REMOTION_ID,
            "raw_command.renderer",
        }
        if supported is None
        else supported
    )

    def resolve(
        renderer_id: str, _request: RenderRequest, _timeline: object
    ) -> SupportReport:
        ok = renderer_id in accepted
        return SupportReport(
            schema_version=1,
            supported=ok,
            reasons=[] if ok else ["fixture rejection"],
            features={"fixture": True},
            alternatives=[],
            backend=renderer_id,
            backend_version=None,
        )

    return resolve


def _plan(tmp_path: Path, timeline: dict, *, config: dict | None = None) -> RenderPlan:
    return legacy_hybrid.plan(
        _request(tmp_path, timeline, config=config),
        workspace=tmp_path,
        support_resolver=_resolver(),
    )


def test_empty_plan_is_valid_zero_frame_plan(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline())

    assert result.total_frames == 0
    assert result.segments == []
    assert result.reasons == {}
    assert result.window is None
    assert result.finalizer.id == "rendering.ffmpeg-finalizer"


def test_single_segment_uses_supported_qualified_renderer(tmp_path: Path) -> None:
    result = _plan(tmp_path, _timeline(clips=[_media(duration=2)]))

    assert [(item.window.start_frame, item.window.end_frame) for item in result.segments] == [
        (0, 60)
    ]
    assert result.segments[0].renderer.id == "rendering.ffmpeg"
    assert result.segments[0].renderer.support_decision.supported is True
    assert result.profile.fps_rational == (30, 1)


def test_multiple_segments_tile_the_timeline_exactly(tmp_path: Path) -> None:
    timeline = _timeline(
        clips=[
            _media(duration=10),
            {
                "id": "title",
                "at": 4,
                "track": "v",
                "clipType": "text-card",
                "hold": 1,
            },
        ]
    )
    result = _plan(tmp_path, timeline)
tests/core/rendering/test_legacy_hybrid.py:106:def test_empty_plan_is_valid_zero_frame_plan(tmp_path: Path) -> None:
tests/core/rendering/test_legacy_hybrid.py:475:def test_planner_rejects_empty_renderer_lists(tmp_path: Path) -> None:
tests/core/rendering/test_legacy_hybrid.py:478:    assert "renderers must not be empty" in caught.value.error.details["reasons"]
tests/core/rendering/test_legacy_hybrid.py:486:    assert "simple_renderers must not be empty" in caught.value.error.details["reasons"]

exec
/bin/zsh -lc "cat astrid/packs/rendering/planners/legacy_hybrid/planner.yaml && git diff C4-batch3-done..a72729db -- astrid/packs/rendering/pack.yaml astrid/packs/rendering/executors/render/executor.yaml | sed -n '1,300p' && sed -n '1,130p' astrid/packs/rendering/run.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 4ms:
#!/usr/bin/env python3
"""Pack-root launcher for rendering raw-command adapters.

Rendering protocol commands execute with their owning pack as the working
directory.  Built-in manifests intentionally keep the portable
``[python3, run.py]`` command, so this launcher bridges that lifecycle to the
implementation stored beside each manifest.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


_CHECKOUT_ROOT = Path(__file__).resolve().parents[3]
if str(_CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(_CHECKOUT_ROOT))

def _request_path(argv: Sequence[str]) -> Path | None:
    try:
        index = argv.index("--request")
        return Path(argv[index + 1])
    except (ValueError, IndexError):
        return None


def _selects_finalizer(argv: Sequence[str]) -> bool:
    """Route finalize and explicitly-namespaced support operations."""

    selected = _transport_selected_backend()
    if selected is not None:
        # The transport-selected backend id is authoritative over request
        # content: a remotion invocation must never route to the finalizer
        # merely because the request carries a finalizer namespace.
        return selected == "rendering.ffmpeg-finalizer"
    if argv and argv[0] == "finalize":
        return True
    if not argv or argv[0] != "support":
        return False
    request_path = _request_path(argv)
    if request_path is None:
        return False
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, Mapping):
        return False
    backend_config = payload.get("backend_config")
    return isinstance(backend_config, Mapping) and (
        "rendering.ffmpeg-finalizer" in backend_config
    )


def _transport_selected_backend() -> str | None:
    """The transport sets ASTRID_RENDER_BACKEND to the qualified backend id
    it selected; this is authoritative over any request content."""
    value = __import__("os").environ.get("ASTRID_RENDER_BACKEND")
    if isinstance(value, str) and value:
        return value
    return None


def _selects_ffmpeg(argv: Sequence[str]) -> bool:
    """Select FFmpeg from the transport-selected backend id or the request's
    backend-config namespace.

    The launcher never guesses from timeline shape: a shape guess can route a
    Remotion request to FFmpeg or vice versa.  The legacy media-only
    auto-route lives inside the Remotion backend's own support logic.
    """

    selected = _transport_selected_backend()
    if selected is not None:
        return selected == "rendering.ffmpeg"
    request_path = _request_path(argv)
    if request_path is None:
        return False
    try:
        payload = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, Mapping):
        return False
    backend_config = payload.get("backend_config")
    if not isinstance(backend_config, Mapping):
        return False
    if "rendering.ffmpeg" in backend_config:
        return True
    return False


def _selects_planner() -> bool:
    """Route the transport-selected hybrid planner without shape guessing."""

    return _transport_selected_backend() == "rendering.legacy_hybrid"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if _selects_planner():
        from astrid.packs.rendering.planners.legacy_hybrid.run import (
            main as backend_main,
        )
    elif _selects_finalizer(args):
        from astrid.packs.rendering.finalizers.ffmpeg.run import (
            main as backend_main,
        )
    elif _selects_ffmpeg(args):
        from astrid.packs.rendering.backends.ffmpeg.run import main as backend_main
    else:
        from astrid.packs.rendering.backends.remotion.run import main as backend_main

    return backend_main(args)


if __name__ == "__main__":
    raise SystemExit(main())

exec
/bin/zsh -lc "rg -n \"raw_command|extra_pack|include_installed|load_default_registries|CommandTransport\" tests/core/rendering/test_service.py tests/core/rendering/test_legacy_hybrid.py | sed -n '1,240p' && sed -n '1040,1185p' tests/core/rendering/test_service.py && sed -n '1185,1285p' tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 17ms:
tests/core/rendering/test_legacy_hybrid.py:11:from astrid.core.rendering.registry import load_default_registries
tests/core/rendering/test_legacy_hybrid.py:12:from astrid.core.rendering.transport import CommandTransport
tests/core/rendering/test_legacy_hybrid.py:75:            "raw_command.renderer",
tests/core/rendering/test_legacy_hybrid.py:183:            "simple_renderers": ["raw_command.renderer"],
tests/core/rendering/test_legacy_hybrid.py:189:        "raw_command.renderer",
tests/core/rendering/test_legacy_hybrid.py:191:        "raw_command.renderer",
tests/core/rendering/test_legacy_hybrid.py:276:    report = CommandTransport(legacy_hybrid.BACKEND_ID).run(
tests/core/rendering/test_legacy_hybrid.py:286:    renderers, planners, finalizers = load_default_registries(
tests/core/rendering/test_legacy_hybrid.py:287:        Path(__file__).resolve().parents[3], include_installed=False
tests/core/rendering/test_legacy_hybrid.py:378:                "simple_renderers": ["raw_command.renderer"],
tests/core/rendering/test_legacy_hybrid.py:381:            ["raw_command.renderer", "rendering.remotion", "raw_command.renderer"],
tests/core/rendering/test_legacy_hybrid.py:386:                "simple_renderers": ["rendering.ffmpeg", "raw_command.renderer"],
tests/core/rendering/test_legacy_hybrid.py:426:            "simple_renderers": ["rendering.ffmpeg", "raw_command.renderer"]
tests/core/rendering/test_legacy_hybrid.py:432:        support_resolver=_resolver(supported={"raw_command.renderer"}),
tests/core/rendering/test_legacy_hybrid.py:436:        "raw_command.renderer"
tests/core/rendering/test_legacy_hybrid.py:455:            supported={"rendering.ffmpeg", "raw_command.renderer"}
tests/core/rendering/test_service.py:1044:        {"raw_command.renderer", "rendering.remotion", "rendering.ffmpeg"}
tests/core/rendering/test_service.py:1087:        "raw_command.renderer",
tests/core/rendering/test_service.py:1111:    / "raw_command"
tests/core/rendering/test_service.py:1118:    ``raw_command.renderer`` invocations run the fixture's real stdlib
tests/core/rendering/test_service.py:1137:        if backend != "raw_command.renderer":
tests/core/rendering/test_service.py:1550:            "simple_renderers": ["raw_command.renderer"],
tests/core/rendering/test_service.py:1561:        "raw_command.renderer",
tests/core/rendering/test_service.py:1563:        "raw_command.renderer",
tests/core/rendering/test_service.py:1569:        "raw_command.renderer",
tests/core/rendering/test_service.py:1571:        "raw_command.renderer",
tests/core/rendering/test_service.py:1593:            "simple_renderers": ["raw_command.renderer"],
tests/core/rendering/test_service.py:1604:        "raw_command.renderer",
tests/core/rendering/test_service.py:1606:        "raw_command.renderer",
tests/core/rendering/test_service.py:1612:        "raw_command.renderer",
tests/core/rendering/test_service.py:1614:        "raw_command.renderer",
tests/core/rendering/test_service.py:1619:        if segment["renderer"]["id"] == "raw_command.renderer"
def _planner_support_resolver(
    accepted: set[str] | None = None,
):
    supported = (
        {"raw_command.renderer", "rendering.remotion", "rendering.ffmpeg"}
        if accepted is None
        else accepted
    )

    def resolve(
        renderer_id: str, _request: RenderRequest, _timeline: object
    ) -> SupportReport:
        ok = renderer_id in supported
        return SupportReport(
            schema_version=SCHEMA_VERSION,
            supported=ok,
            reasons=[] if ok else ["fixture rejection"],
            features={"fixture": True},
            alternatives=[],
            backend=renderer_id,
            backend_version="1.0.0",
        )

    return resolve


def _mixed_plan(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    config: dict[str, Any],
) -> RenderRequest:
    timeline = _hybrid_timeline()
    request = _hybrid_request(tmp_path, timeline, config=config)
    transport.plan = legacy_hybrid.plan(
        request,
        workspace=tmp_path,
        support_resolver=_planner_support_resolver(),
    )
    return request


def _mixed_service(
    tmp_path: Path,
    transport: FakeTransport,
    *,
    renderer_ids: tuple[str, ...] = (
        "raw_command.renderer",
        "rendering.remotion",
    ),
) -> RenderService:
    renderers = RendererRegistry(
        [_candidate(tmp_path, item, "renderer") for item in renderer_ids]
    )
    planners = PlannerRegistry(
        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
    )
    finalizers = FinalizerRegistry(
        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
    )
    return RenderService(
        registries=(renderers, planners, finalizers),
        transport=transport,
        validator=lambda result, **_kwargs: result,
    )


RAW_FIXTURE_PACK_ROOT = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "renderer_packs"
    / "raw_command"
)


class _RawFixtureTransport(FakeTransport):
    """FakeTransport that executes the deterministic Batch-2 raw fixture.

    ``raw_command.renderer`` invocations run the fixture's real stdlib
    ``backend.py`` subprocess; every other backend stays simulated.
    """

    def __init__(self, pack_root: Path = RAW_FIXTURE_PACK_ROOT) -> None:
        super().__init__()
        self.pack_root = Path(pack_root)

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        if backend != "raw_command.renderer":
            return super().run(
                verb,
                command,
                backend=backend,
                request_path=request_path,
                result_path=result_path,
                cwd=cwd,
                **kwargs,
            )
        self.calls.append((verb, backend))
        subprocess.run(
            [
                sys.executable,
                "backend.py",
                verb,
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ],
            cwd=self.pack_root,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        if verb == "support":
            return SupportReport.from_dict(payload)
        if verb == "render":
            return RenderResult.from_dict(payload)
        raise AssertionError(f"raw fixture backend has no {verb!r} verb")


@pytest.mark.parametrize(
    (
        "selector",
        "hybrid_plan",
        "expected_calls",
        "expected_engine",
        "expected_backend",
        "auto_route",
        "warning",
    ),
    [
        (
            "rendering.remotion",
            False,
            [("support", "rendering.remotion"), ("render", "rendering.remotion")],
            [("support", "rendering.remotion"), ("render", "rendering.remotion")],
            "rendering.remotion",
            "rendering.remotion",
            False,
            False,
        ),
        (
            "rendering.ffmpeg",
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "rendering.ffmpeg",
            "rendering.ffmpeg",
            False,
            False,
        ),
        (
            "remotion",
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "remotion",
            "rendering.ffmpeg",
            True,
            True,
        ),
        (
            None,
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "remotion",
            "rendering.ffmpeg",
            True,
            True,
        ),
        (
            "ffmpeg",
            False,
            [("support", "rendering.ffmpeg"), ("render", "rendering.ffmpeg")],
            "ffmpeg",
            "rendering.ffmpeg",
            False,
            False,
        ),
        (
            "hybrid",
            True,
            [
                ("support", "rendering.legacy_hybrid"),
                ("plan", "rendering.legacy_hybrid"),
                ("support", "fixture.window"),
                ("render", "fixture.window"),
            ],
            "hybrid",
            "fixture.window",
            False,
            False,
        ),
    ],
    ids=[
        "qualified-remotion",
        "qualified-ffmpeg",
        "legacy-remotion",
        "default-remotion",
        "legacy-ffmpeg",
        "hybrid",
    ],
)
def test_selector_routing_matrix(
    tmp_path: Path,
    selector: str | None,
    hybrid_plan: bool,
    expected_calls: list[tuple[str, str]],
    expected_engine: str,
    expected_backend: str,
    auto_route: bool,
    warning: bool,
) -> None:
    transport = FakeTransport()
    if hybrid_plan:
        transport.plan = _plan("fixture.window")
        service = _service(
            tmp_path,
            transport,
            renderer_ids=("fixture.window",),
            planner_ids=("rendering.legacy_hybrid",),
        )
    else:
        service = _service(tmp_path, transport)
    output = tmp_path / "routing.mp4"

    if warning:
        with pytest.warns(LegacyRenderRoutingWarning, match="auto-routed"):
            service.render_request(
                _request(tmp_path), selector=selector, out_path=output
            )
    else:
        service.render_request(
            _request(tmp_path), selector=selector, out_path=output
        )

    assert transport.calls == expected_calls
    assert not any(verb == "finalize" for verb, _backend in transport.calls)

exec
/bin/zsh -lc "sed -n '1525,1630p' tests/core/rendering/test_service.py && sed -n '1630,1745p' tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 111ms:
    assert sidecars == [Path(f"{output}.provenance.json")]
    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert payload["output"] == str(output.resolve())
    assert payload["routing"]["requested_engine"] == expected_engine
    assert payload["routing"]["auto_route"] is False
    assert payload["audio_ownership"] == "none"
    for _verb, backend, payload_data in transport.payloads:
        if backend in backend_config:
            assert payload_data["backend_config"][backend] == backend_config[backend]
    if expect_finalize:
        assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    else:
        assert not any(verb == "finalize" for verb, _backend in transport.calls)
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_raw_mixed_plan_routes_windows_and_aligns_segment_provenance(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    request = _mixed_plan(
        tmp_path,
        transport,
        config={
            "simple_renderers": ["raw_command.renderer"],
            "complex_renderers": ["rendering.remotion"],
        },
    )
    service = _mixed_service(tmp_path, transport)
    output = tmp_path / "mixed.mp4"

    service.render_request(request, selector="hybrid", out_path=output)

    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
    assert render_calls == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    payload = _sidecar(output)
    segments = payload["segments_v2"]
    assert [segment["renderer"]["id"] for segment in segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    windows = [
        (segment["window"]["start_frame"], segment["window"]["end_frame"])
        for segment in segments
    ]
    assert windows[0][0] == 0
    assert windows[-1][1] == transport.plan.total_frames
    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
    assert all("timeline" in segment["input_hashes"] for segment in segments)
    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"
    assert payload["routing"]["requested_engine"] == "hybrid"


def test_raw_mixed_plan_executes_deterministic_raw_fixture_window(
    tmp_path: Path,
) -> None:
    transport = _RawFixtureTransport()
    request = _mixed_plan(
        tmp_path,
        transport,
        config={
            "simple_renderers": ["raw_command.renderer"],
            "complex_renderers": ["rendering.remotion"],
        },
    )
    service = _mixed_service(tmp_path, transport)
    output = tmp_path / "mixed-real.mp4"

    service.render_request(request, selector="hybrid", out_path=output)

    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
    assert render_calls == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
    payload = _sidecar(output)
    segments = payload["segments_v2"]
    assert [segment["renderer"]["id"] for segment in segments] == [
        "raw_command.renderer",
        "rendering.remotion",
        "raw_command.renderer",
    ]
    raw_windows = [
        segment["window"]
        for segment in segments
        if segment["renderer"]["id"] == "raw_command.renderer"
    ]
    assert len(raw_windows) == 2
    assert all(
        segment["window"]["end_frame"] - segment["window"]["start_frame"] > 0
        for segment in segments
    )
    # The raw fixture really rendered its windows: real mp4 bytes with the
    # planned frame count in the committed artifact profile.
    assert output.is_file()
    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")



@pytest.mark.parametrize(
    ("selector", "plan_segments", "ownership", "expected", "completer"),
    [
        ("rendering.remotion", None, AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
        ("rendering.ffmpeg", None, AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
        ("rendering.remotion", None, AudioOwnership.NONE, AudioOwnership.NONE, False),
        ("rendering.ffmpeg", None, AudioOwnership.NONE, AudioOwnership.NONE, False),
        ("rendering.remotion", None, AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
        ("rendering.ffmpeg", None, AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
        ("hybrid", (10,), AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
        ("hybrid", (10,), AudioOwnership.NONE, AudioOwnership.NONE, False),
        ("hybrid", (10,), AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
    ],
    ids=[
        "remotion-rendered",
        "ffmpeg-rendered",
        "remotion-none",
        "ffmpeg-none",
        "remotion-passthrough",
        "ffmpeg-passthrough",
        "hybrid-rendered",
        "hybrid-none",
        "hybrid-passthrough",
    ],
)
def test_audio_ownership_matrix_across_backends(
    tmp_path: Path,
    selector: str,
    plan_segments: tuple[int, ...] | None,
    ownership: AudioOwnership,
    expected: AudioOwnership,
    completer: bool,
) -> None:
    transport = FakeTransport()

    def audio_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
        return replace(
            result,
            video=replace(
                result.video,
                profile=_profile(audio=True),
                audio=AudioOwnership.RENDERED,
            ),
            audio_ownership=AudioOwnership.RENDERED,
        )

    if plan_segments is not None:
        transport.plan = _plan("fixture.window", segment_frames=plan_segments)
        service = _service(
            tmp_path,
            transport,
            renderer_ids=("fixture.window",),
            planner_ids=("rendering.legacy_hybrid",),
            audio_completer=audio_completer if completer else None,
        )
    else:
        service = _service(
            tmp_path,
            transport,
            audio_completer=audio_completer if completer else None,
        )
    output = tmp_path / f"audio-{ownership.value}.mp4"

    service.render_request(
        replace(_request(tmp_path), audio=ownership),
        selector=selector,
        out_path=output,
    )

    payload = _sidecar(output)
    assert payload["audio_ownership"] == expected.value
    assert payload["routing"]["requested_engine"] == (
        "hybrid" if plan_segments is not None else selector
    )


def test_finalizer_failure_removes_workspace_and_commits_nothing(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.fail_finalize = "rendering.ffmpeg-finalizer"
    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
    service = _service(
        tmp_path,
        transport,
        renderer_ids=("fixture.window",),
        planner_ids=("rendering.legacy_hybrid",),
    )
    output = tmp_path / "failed-finalize.mp4"

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="hybrid", out_path=output
        )

    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_support_failure_removes_workspace_and_commits_nothing(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    transport.fail_support = "rendering.ffmpeg"
    service = _service(tmp_path, transport)
    output = tmp_path / "failed-support.mp4"

    with pytest.raises(RendererInternalError):
        service.render_request(
            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
        )

    assert not output.exists()

codex
The first pass found a risky seam in hybrid resolution: planner-selected renderer aliases/overrides may be compared against the pre-resolution ID. I’m validating that against the registry contract and targeted tests now.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider tests/core/rendering/' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 2772ms:
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
/bin/zsh -lc "rg -n \"def get\\(|def resolve_evidence|alias_chain|override\" astrid/core/rendering/registry.py | head -n 180 && sed -n '260,470p' astrid/core/rendering/registry.py && sed -n '1390,1460p' tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 719ms:
34:from astrid.core.pack.override import OverrideStore
182:        override_store: OverrideStore | None = None,
184:        super().__init__(alias_resolver=alias_resolver, override_store=override_store)
293:    def get(self, capability_id: str) -> RenderingCandidate[ManifestT]:
300:    def resolve_evidence(self, capability_id: str) -> dict[str, Any]:
301:        """Explain the complete alias/override/priority/trust resolution."""
316:                "alias_chain": tuple(exc.details.get("alias_chain", ())),
317:                "override": exc.details.get("override"),
330:            "alias_chain": list(resolution["alias_chain"]),
331:            "override": resolution["override"],
357:        canonical_id, alias_chain = self._resolve_alias(requested_id)
364:                details={"canonical_id": canonical_id, "alias_chain": list(alias_chain)},
367:        override_target = self._resolve_override_key(self.capability_kind, canonical_id)
368:        target_id = override_target or canonical_id
369:        override = (
371:            if override_target is None
372:            else {"from": canonical_id, "to": override_target}
376:                f"override target {_FACADE_EXECUTOR_ID!r} for {self.capability_kind} "
380:                details={"canonical_id": canonical_id, "override": override},
389:                "alias_chain": list(alias_chain),
390:                "override": override,
404:            if override_target is not None:
406:                    f"override target {target_id!r} for {self.capability_kind} "
408:                    code="invalid_override_target",
412:            if alias_chain:
429:            "alias_chain": alias_chain,
430:            "override": override,
473:                details={"alias_chain": chain},
516:    override_store = OverrideStore(root)
519:        override_store=override_store,
522:        override_store=override_store,
525:        override_store=override_store,
975:    explicit override.  That alias remains only as the routing key needed to
976:    apply the override; normal winner selection still enforces eligibility on
977:    the override target.
1012:    override_routing_aliases: set[str] = set()
1015:        override_routing_aliases = set()
1024:                registry._resolve_override_key(kind, target) is not None
1026:                override_routing_aliases.add(alias_name)
1042:            alias_name not in override_routing_aliases
1047:                override_routing_aliases=override_routing_aliases,
1065:    override_routing_aliases: set[str] | frozenset[str] = frozenset(),
1067:    """Return whether a chain reaches an executable or override-routed terminal."""
1075:        if target in override_routing_aliases:
1085:    # A missing canonical terminal is still reachable when an override
1087:    # override ordering is frozen).
1088:    return registry._resolve_override_key(registry.capability_kind, target) is not None
        *,
        eligible: bool | None = None,
    ) -> tuple[RenderingCandidate[ManifestT], ...]:
        """Return static candidates, including non-executable discoveries."""

        if capability_id is None:
            values = [
                candidate
                for candidate_id in sorted(self._discovered)
                for candidate in self._discovered[candidate_id]
            ]
        else:
            canonical_id, _ = self._resolve_alias(capability_id, for_inspection=True)
            values = list(self._discovered.get(canonical_id, ()))
        if eligible is not None:
            values = [
                candidate
                for candidate in values
                if candidate.execution_eligible is eligible
            ]
        return tuple(values)

    @property
    def discovered_candidates(self) -> tuple[RenderingCandidate[ManifestT], ...]:
        """Compatibility-friendly property for static inspection surfaces."""

        return self.candidates()

    def inspect(self, capability_id: str) -> tuple[RenderingCandidate[ManifestT], ...]:
        """Return every statically discovered candidate for an id."""

        return self.candidates(capability_id)

    def get(self, capability_id: str) -> RenderingCandidate[ManifestT]:
        candidate, _ = self._resolve(capability_id)
        return candidate

    def get_manifest(self, capability_id: str) -> ManifestT:
        return self.get(capability_id).manifest

    def resolve_evidence(self, capability_id: str) -> dict[str, Any]:
        """Explain the complete alias/override/priority/trust resolution."""

        resolution_error: dict[str, Any] | None = None
        try:
            candidate, resolution = self._resolve(capability_id)
        except RenderingRegistryError as exc:
            if exc.code != "execution_ineligible":
                raise
            target_id = exc.details.get("target_id")
            discovered = self._discovered.get(str(target_id), ())
            if not discovered:
                raise
            candidate = discovered[0]
            resolution = {
                "canonical_id": exc.details.get("canonical_id", capability_id),
                "alias_chain": tuple(exc.details.get("alias_chain", ())),
                "override": exc.details.get("override"),
            }
            resolution_error = exc.to_dict()
        eligibility = candidate.eligibility.to_dict()
        return {
            "requested_id": capability_id,
            "canonical_id": resolution["canonical_id"],
            "resolved_id": candidate.id,
            "source_kind": candidate.source_kind,
            "pack_id": candidate.pack_id,
            "pack_root": str(candidate.pack_root),
            "manifest_path": str(candidate.manifest_path),
            "manifest_digest": candidate.manifest_digest,
            "alias_chain": list(resolution["alias_chain"]),
            "override": resolution["override"],
            "priority": candidate.priority_index,
            "priority_index": candidate.priority_index,
            "eligible": candidate.execution_eligible,
            "execution_eligible": candidate.execution_eligible,
            "eligibility_reason": candidate.eligibility.reason,
            "trust_method": candidate.eligibility.trust_method,
            "eligibility": eligibility,
            "resolution_error": resolution_error,
        }

    def validate_all(self) -> tuple[RenderingCandidate[ManifestT], ...]:
        if self.alias_resolver is not None:
            try:
                self.alias_resolver.validate_no_cycles()
            except AliasResolutionError as exc:
                raise self._error(
                    str(exc),
                    code="alias_cycle",
                ) from exc
        return self.list()

    def _resolve(
        self,
        requested_id: str,
    ) -> tuple[RenderingCandidate[ManifestT], dict[str, Any]]:
        canonical_id, alias_chain = self._resolve_alias(requested_id)
        if self.rejects_facade and canonical_id == _FACADE_EXECUTOR_ID:
            raise self._error(
                f"{self.capability_kind} {requested_id!r} resolves back to the "
                f"facade executor {_FACADE_EXECUTOR_ID!r}",
                code="facade_recursion",
                requested_id=requested_id,
                details={"canonical_id": canonical_id, "alias_chain": list(alias_chain)},
            )

        override_target = self._resolve_override_key(self.capability_kind, canonical_id)
        target_id = override_target or canonical_id
        override = (
            None
            if override_target is None
            else {"from": canonical_id, "to": override_target}
        )
        if self.rejects_facade and target_id == _FACADE_EXECUTOR_ID:
            raise self._error(
                f"override target {_FACADE_EXECUTOR_ID!r} for {self.capability_kind} "
                f"{canonical_id!r} resolves back to the facade executor",
                code="facade_recursion",
                requested_id=requested_id,
                details={"canonical_id": canonical_id, "override": override},
            )

        winner = self._winner_for(target_id)
        if winner is None:
            discovered = self._discovered.get(target_id, ())
            details: dict[str, Any] = {
                "canonical_id": canonical_id,
                "target_id": target_id,
                "alias_chain": list(alias_chain),
                "override": override,
            }
            if discovered:
                details["candidates"] = [candidate.to_dict() for candidate in discovered]
                reasons = "; ".join(
                    dict.fromkeys(candidate.eligibility.reason for candidate in discovered)
                )
                raise self._error(
                    f"{self.capability_kind} {target_id!r} is discoverable but not "
                    f"execution-eligible: {reasons}",
                    code="execution_ineligible",
                    requested_id=requested_id,
                    details=details,
                )
            if override_target is not None:
                raise self._error(
                    f"override target {target_id!r} for {self.capability_kind} "
                    f"{canonical_id!r} not found in executable registry",
                    code="invalid_override_target",
                    requested_id=requested_id,
                    details=details,
                )
            if alias_chain:
                raise self._error(
                    f"alias {requested_id!r} points to missing {self.capability_kind} "
                    f"{target_id!r}",
                    code="invalid_alias_target",
                    requested_id=requested_id,
                    details=details,
                )
            raise self._error(
                f"unknown {self.capability_kind} id {requested_id!r}",
                code="unknown_capability",
                requested_id=requested_id,
                details=details,
            )

        return winner, {
            "canonical_id": canonical_id,
            "alias_chain": alias_chain,
            "override": override,
        }

    def _resolve_alias(
        self,
        requested_id: str,
        *,
        for_inspection: bool = False,
    ) -> tuple[str, tuple[str, ...]]:
        if not isinstance(requested_id, str) or not requested_id:
            raise self._error(
                f"{self.capability_kind} id must be a non-empty string",
                code="invalid_id",
                requested_id=requested_id if isinstance(requested_id, str) else None,
            )
        resolver = (
            self.inspection_alias_resolver
            if for_inspection
            else self.alias_resolver
        )
        if resolver is None or not resolver.is_alias(requested_id):
            return requested_id, ()

        chain: list[str] = [requested_id]
        seen = {requested_id}
        current = requested_id
        try:
            while resolver.is_alias(current):
                record = resolver.get_record(current)
                if record is None:  # defensive against a concurrently-mutated resolver
                    break
                current = record.canonical_id
                chain.append(current)
                if current in seen:
                    raise AliasResolutionError(
                        f"alias cycle detected while resolving {requested_id!r}"
                    )
                seen.add(current)
        except AliasResolutionError as exc:
            raise self._error(
                str(exc),
    assert "remotion" in error.recovery_command
    assert transport.calls == []


@pytest.mark.parametrize(
    "name",
    [
        "a/b.mp4",
        "a\\b.mp4",
        "sub/out.mp4",
        "/abs.mp4",
        "../evil.mp4",
        "..mp4",
        "..",
        ".",
        "",
    ],
)
def test_separator_and_traversal_output_names_are_rejected_before_invocation(
    tmp_path: Path, name: str
) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "never-written.mp4"
    request = _request(tmp_path).to_dict()
    request["output_name"] = name

    with pytest.raises(RendererProtocolError) as caught:
        service.render_request(request, selector="rendering.ffmpeg", out_path=output)

    assert caught.value.error.kind == "protocol"
    assert caught.value.error.recovery_command
    assert transport.calls == []
    assert not output.exists()
    assert not list(tmp_path.glob("*.provenance.json"))
    assert not list(tmp_path.glob(".*.render-service-*"))


def test_facade_rejects_non_mp4_output_name_but_preserves_hype_default() -> None:
    from astrid.packs.rendering.executors.render.run import (
        DEFAULT_OUTPUT_NAME,
        validate_output_name,
    )

    assert DEFAULT_OUTPUT_NAME == "hype.mp4"
    assert validate_output_name("hype.mp4") == "hype.mp4"
    with pytest.raises(ValueError, match=r"\.mp4"):
        validate_output_name("out.mov")


def test_hype_mp4_default_output_name_is_preserved(tmp_path: Path) -> None:
    transport = FakeTransport()
    service = _service(tmp_path, transport)
    output = tmp_path / "published" / "hype.mp4"
    request = replace(_request(tmp_path), output_name="hype.mp4")

    service.render_request(
        request, selector="rendering.ffmpeg", out_path=output
    )

    render_payloads = [
        payload
        for verb, backend, payload in transport.payloads
        if verb == "render" and backend == "rendering.ffmpeg"
    ]
    assert len(render_payloads) == 1
    assert render_payloads[0]["output_name"] == "hype.mp4"
    payload = _sidecar(output)
    assert payload["output"] == str(output.resolve())
    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '1198,1288p' && nl -ba astrid/packs/rendering/planners/legacy_hybrid/run.py | sed -n '602,675p;735,790p' && nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '590,675p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1198	                renderer=self._renderer_resolution(resolved),
  1199	                input_hashes={
  1200	                    **segment.input_hashes,
  1201	                    **input_hashes,
  1202	                    **materialized_hashes,
  1203	                },
  1204	            )
  1205	            normalized_segments.append(normalized_segment)
  1206	            result = self._invoke_renderer(
  1207	                segment_request,
  1208	                selected=resolved,
  1209	                workspace=workspace,
  1210	                output_name=segment_request.output_name,
  1211	                # Segment renderers may emit a profile that the registered
  1212	                # finalizer must normalize.  The artifact is first validated
  1213	                # against its own declaration; a one-segment exact match is
  1214	                # checked against the plan in _finish_plan, while every
  1215	                # mismatch and every multi-segment plan goes through the
  1216	                # pinned finalizer.
  1217	                expected_profile=None,
  1218	            )
  1219	            completed = self.complete_audio(
  1220	                result,
  1221	                request=segment_request,
  1222	                plan=response,
  1223	                workspace=workspace,
  1224	                backend=candidate.id,
  1225	                defer_to_finalizer=len(response.segments) > 1,
  1226	            )
  1227	            self._validate_segment_duration(
  1228	                completed,
  1229	                segment=segment,
  1230	                canonical_profile=response.profile,
  1231	                backend=candidate.id,
  1232	            )
  1233	            segment_results.append(completed)
  1234	
  1235	        finalizer, finalizer_evidence = self._resolve_candidate(
  1236	            self.finalizers,
  1237	            response.finalizer.id,
  1238	            kind="finalizer",
  1239	            observe=False,
  1240	        )
  1241	        finalizer_resolution = self._finalizer_resolution(
  1242	            finalizer,
  1243	            finalizer_evidence,
  1244	            support=None,
  1245	        )
  1246	        plan = replace(
  1247	            response,
  1248	            request_digest=compute_request_digest(request.to_dict()),
  1249	            requested_policy=policy.requested,
  1250	            planner=planner_resolution,
  1251	            segments=normalized_segments,
  1252	            finalizer=finalizer_resolution,
  1253	        )
  1254	        return plan, segment_results, (finalizer, finalizer_evidence)
  1255	
  1256	    def _finish_plan(
  1257	        self,
  1258	        request: RenderRequest,
  1259	        *,
  1260	        plan: RenderPlan,
  1261	        segment_results: list[RenderResult],
  1262	        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
  1263	        workspace: Path,
  1264	    ) -> tuple[RenderResult, RenderPlan]:
  1265	        if len(segment_results) == 1:
  1266	            result = self._validator(
  1267	                segment_results[0],
  1268	                expected_profile=plan.profile,
  1269	                workspace_root=workspace,
  1270	            )
  1271	            return result, plan
  1272	
  1273	        candidate, evidence = pinned_finalizer
  1274	        ownerships = {item.audio_ownership for item in segment_results}
  1275	        if ownerships == {AudioOwnership.PASSTHROUGH}:
  1276	            requested_audio = AudioOwnership.PASSTHROUGH
  1277	        elif plan.profile.has_audio:
  1278	            requested_audio = AudioOwnership.RENDERED
  1279	        else:
  1280	            requested_audio = AudioOwnership.NONE
  1281	        support_audio = (
  1282	            None
  1283	            if requested_audio is AudioOwnership.PASSTHROUGH
  1284	            and plan.profile.has_audio
  1285	            else requested_audio
  1286	        )
  1287	        support_request = RenderRequest(
  1288	            schema_version=SCHEMA_VERSION,
   602	
   603	class _CommandSupportResolver:
   604	    def __init__(
   605	        self,
   606	        registry: RendererRegistry,
   607	        *,
   608	        workspace: Path,
   609	    ) -> None:
   610	        self.registry = registry
   611	        self.workspace = workspace
   612	        self.counter = 0
   613	
   614	    def __call__(
   615	        self,
   616	        renderer_id: str,
   617	        request: RenderRequest,
   618	        timeline: Mapping[str, Any],
   619	    ) -> SupportReport:
   620	        candidate = self.registry.get(renderer_id)
   621	        evidence = self.registry.resolve_evidence(renderer_id)
   622	        del evidence
   623	        projected = request.for_backend(candidate.id)
   624	        if candidate.manifest.capabilities.get("supports_windows") is False:
   625	            if projected.window is None:
   626	                raise ValueError("planned renderer support requires a frame window")
   627	            path = self.workspace / "planner-support" / f"{self.counter:04d}-timeline.json"
   628	            self.counter += 1
   629	            write_json_atomic(path, timeline)
   630	            projected = replace(projected, timeline_path=str(path), window=None)
   631	        if "support" not in candidate.manifest.operations:
   632	            supports = candidate.manifest.capabilities.get(
   633	                "supports_windows" if projected.window is not None else "supports_full_timeline"
   634	            ) is True
   635	            return SupportReport(
   636	                schema_version=SCHEMA_VERSION,
   637	                supported=supports,
   638	                reasons=[] if supports else ["renderer lacks static support for this window"],
   639	                features={
   640	                    str(key): value
   641	                    for key, value in candidate.manifest.capabilities.get("features", {}).items()
   642	                    if isinstance(value, (bool, str))
   643	                },
   644	                alternatives=[],
   645	                backend=candidate.id,
   646	                backend_version=candidate.manifest.version,
   647	            )
   648	        request_path = self.workspace / "planner-support" / f"{self.counter:04d}-request.json"
   649	        result_path = self.workspace / "planner-support" / f"{self.counter:04d}-result.json"
   650	        self.counter += 1
   651	        write_json_atomic(request_path, projected.to_dict())
   652	        response = CommandTransport(candidate.id).run(
   653	            "support",
   654	            candidate.manifest.command,
   655	            request_path=request_path,
   656	            result_path=result_path,
   657	            cwd=candidate.pack_root,
   658	            required_binaries=(),
   659	            timeout=candidate.manifest.timeout_seconds,
   660	        )
   661	        if not isinstance(response, SupportReport):
   662	            raise TypeError(f"{candidate.id} support did not return a SupportReport")
   663	        return response
   664	
   665	
   666	def plan(
   667	    request: RenderRequest,
   668	    *,
   669	    workspace: Path,
   670	    support_resolver: SupportResolver | None = None,
   671	    registries: tuple[RendererRegistry, FinalizerRegistry] | None = None,
   672	) -> RenderPlan:
   673	    report = support(request, workspace=workspace)
   674	    if not report.supported:
   675	        raise_unsupported_error(
   735	            fps_rational=profile.fps_rational,
   736	        )
   737	        segment_timeline = _window_timeline(timeline, window)
   738	        segment_request = replace(
   739	            request,
   740	            timeline_path=str(timeline_path),
   741	            assets_registry_path=None if assets_path is None else str(assets_path),
   742	            output_name=f"segment-{index:04d}.mp4",
   743	            window=window,
   744	        )
   745	        attempts: list[str] = []
   746	        selected_id: str | None = None
   747	        selected_report: SupportReport | None = None
   748	        for renderer_id in candidates[kind]:
   749	            try:
   750	                candidate_report = support_resolver(
   751	                    renderer_id,
   752	                    segment_request,
   753	                    segment_timeline,
   754	                )
   755	            except Exception as exc:
   756	                attempts.append(f"{renderer_id}: {exc}")
   757	                continue
   758	            if candidate_report.backend != renderer_id:
   759	                attempts.append(f"{renderer_id}: support report named {candidate_report.backend}")
   760	                continue
   761	            if candidate_report.supported:
   762	                selected_id = renderer_id
   763	                selected_report = candidate_report
   764	                break
   765	            attempts.append(
   766	                f"{renderer_id}: " + "; ".join(candidate_report.reasons)
   767	            )
   768	        if selected_id is None or selected_report is None:
   769	            raise_unsupported_error(
   770	                backend=BACKEND_ID,
   771	                message=f"no renderer supports planned {kind} window [{start},{end})",
   772	                recovery_command="install or configure a renderer supporting the reported window",
   773	                details={"window": [start, end], "attempts": attempts},
   774	            )
   775	        segments.append(
   776	            RenderSegment(
   777	                window=window,
   778	                renderer=_renderer_resolution(
   779	                    selected_id,
   780	                    selected_report,
   781	                    registry=renderer_registry,
   782	                ),
   783	                input_hashes={
   784	                    "timeline": sha256_file(timeline_path),
   785	                    **(
   786	                        {"assets_registry": sha256_file(assets_path)}
   787	                        if assets_path is not None
   788	                        else {}
   789	                    ),
   790	                },
   590	    )
   591	
   592	
   593	def main(argv: Sequence[str] | None = None) -> int:
   594	    parser = argparse.ArgumentParser()
   595	    parser.add_argument("--timeline", type=Path, required=True)
   596	    parser.add_argument("--assets", type=Path)
   597	    parser.add_argument("--out", type=Path, required=True)
   598	    parser.add_argument(
   599	        "--engine",
   600	        default="remotion",
   601	        help="Legacy selector (remotion, ffmpeg, hybrid) or a qualified renderer id.",
   602	    )
   603	    parser.add_argument(
   604	        "--backend",
   605	        default=None,
   606	        help="Neutral alias for --engine: legacy selector or qualified backend id.",
   607	    )
   608	    parser.add_argument(
   609	        "--backend-config",
   610	        default=None,
   611	        help="JSON object keyed by qualified backend id with per-backend configuration.",
   612	    )
   613	    parser.add_argument(
   614	        "--output-name",
   615	        default=None,
   616	        help="Output file name (default hype.mp4); plain .mp4 file name only.",
   617	    )
   618	    parser.add_argument("--project-dir", type=Path, default=REPO_ROOT / "remotion")
   619	    parser.add_argument("--composition", default="TimelineComposition")
   620	    parser.add_argument("--min-free-gb", type=float, default=None, help="Abort before rendering unless this much free disk is available near --out.")
   621	    parser.add_argument(
   622	        "--keep-previous-renders",
   623	        nargs="?",
   624	        const=True,
   625	        default=False,
   626	        type=_parse_bool_arg,
   627	        help="Preserve previous sibling hype.mp4 outputs for the same timeline.",
   628	    )
   629	    parser.add_argument(
   630	        "--theme",
   631	        type=Path,
   632	        default=REPO_ROOT / "themes" / "banodoco-default" / "theme.json",
   633	    )
   634	    args = parser.parse_args(argv)
   635	    try:
   636	        if args.output_name is not None:
   637	            validate_output_name(args.output_name)
   638	            if Path(args.out).name != args.output_name:
   639	                raise ValueError(
   640	                    f"--out basename {Path(args.out).name!r} does not match "
   641	                    f"--output-name {args.output_name!r}"
   642	                )
   643	        else:
   644	            validate_output_name(Path(args.out).name)
   645	        selector = args.backend if args.backend is not None else args.engine
   646	        config = _parse_backend_config(args.backend_config)
   647	        if args.assets is None:
   648	            with TemporaryDirectory(prefix="astrid-render-assets-") as tmp_text:
   649	                assets_path = Path(tmp_text) / "hype.assets.json"
   650	                _write_empty_asset_registry(assets_path)
   651	                output = render(
   652	                    args.timeline,
   653	                    assets_path,
   654	                    args.out,
   655	                    engine=selector,
   656	                    project_dir=args.project_dir,
   657	                    composition_id=args.composition,
   658	                    theme_path=args.theme,
   659	                    min_free_gb=args.min_free_gb,
   660	                    keep_previous_renders=args.keep_previous_renders,
   661	                    backend_config=config,
   662	                )
   663	        else:
   664	            output = render(
   665	                args.timeline,
   666	                args.assets,
   667	                args.out,
   668	                engine=selector,
   669	                project_dir=args.project_dir,
   670	                composition_id=args.composition,
   671	                theme_path=args.theme,
   672	                min_free_gb=args.min_free_gb,
   673	                keep_previous_renders=args.keep_previous_renders,
   674	                backend_config=config,
   675	            )

exec
/bin/zsh -lc "sed -n '240,375p' tests/core/rendering/test_service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
    path.write_bytes(data)
    return Attachment.from_file(
        name=name,
        path=path,
        kind=kind,
        workspace_root=workspace,
    )


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.support: dict[str, SupportReport] = {}
        self.plan: RenderPlan | None = None
        self.fail_render: str | None = None
        self.fail_support: str | None = None
        self.fail_finalize: str | None = None
        self.render_frames: dict[str, int] = {}
        self.render_ownership: dict[str, AudioOwnership] = {}
        self.render_attachments: dict[
            str, dict[str, bytes] | list[dict[str, bytes]]
        ] = {}
        self.finalize_attachments: dict[str, bytes] = {}
        self.finalize_ownership: AudioOwnership = AudioOwnership.NONE
        self.payloads: list[tuple[str, str, dict[str, Any]]] = []

    def run(
        self,
        verb: str,
        command: Any,
        *,
        backend: str,
        request_path: Path,
        result_path: Path,
        cwd: Path,
        **kwargs: Any,
    ) -> Any:
        del command, result_path, cwd, kwargs
        self.calls.append((verb, backend))
        payload = json.loads(Path(request_path).read_text(encoding="utf-8"))
        self.payloads.append((verb, backend, payload))
        workspace = Path(request_path).parent
        if verb == "support":
            if self.fail_support == backend:
                (workspace / "partial.tmp").write_bytes(b"partial")
                raise_internal_error(
                    backend=backend,
                    message="fixture support crashed",
                    recovery_command="retry fixture support",
                )
            return self.support.get(backend, _support(backend))
        if verb == "plan":
            assert self.plan is not None
            return self.plan
        if verb == "render" and self.fail_render == backend:
            (workspace / "partial.tmp").write_bytes(b"partial")
            raise_internal_error(
                backend=backend,
                message="fixture renderer crashed",
                recovery_command="retry fixture renderer",
            )
        output = workspace / "outputs" / payload["output_name"]
        output.parent.mkdir(parents=True, exist_ok=True)
        if verb == "finalize":
            if self.fail_finalize == backend:
                (workspace / "partial.tmp").write_bytes(b"partial")
                raise_internal_error(
                    backend=backend,
                    message="fixture finalizer crashed",
                    recovery_command="retry fixture finalizer",
                )
            frames = payload["plan"]["total_frames"]
            ownership = self.finalize_ownership
            plan_profile = RenderProfile.from_dict(payload["plan"]["profile"])
            if plan_profile.has_audio is (ownership is AudioOwnership.RENDERED):
                profile = plan_profile
            else:
                profile = _profile(audio=ownership is AudioOwnership.RENDERED)
            attachments: dict[str, Attachment] = {}
            for artifact in payload.get("artifacts", []):
                for name, descriptor in (artifact.get("attachments") or {}).items():
                    attachments[name] = Attachment.from_dict(descriptor)
            for name, data in self.finalize_attachments.items():
                attachments[name] = _attachment_file(workspace, name, data)
        else:
            window = payload.get("window")
            frames = (
                self.render_frames[backend]
                if backend in self.render_frames
                else (
                    window["end_frame"] - window["start_frame"]
                    if window is not None
                    else 10
                )
            )
            ownership = self.render_ownership.get(
                backend,
                AudioOwnership(payload.get("audio") or "none"),
            )
            profile = _profile(audio=ownership is AudioOwnership.RENDERED)
            if window is not None:
                # Planned segments are validated against the canonical plan
                # profile; the simulated artifact must speak the window FPS.
                profile = replace(
                    profile, fps_rational=tuple(window["fps_rational"])
                )
            raw_attachments = self.render_attachments.get(backend, {})
            if isinstance(raw_attachments, list):
                # Per-invocation sequence: one attachment map per render call.
                named = raw_attachments.pop(0) if raw_attachments else {}
            else:
                named = raw_attachments
            attachments = {
                name: _attachment_file(workspace, name, data)
                for name, data in named.items()
            }
        output.write_bytes(f"{verb}:{backend}:{frames}".encode())
        video = VideoArtifact.from_file(
            path=output,
            workspace_root=workspace,
            profile=profile,
            duration_frames=frames,
            audio=ownership,
            attachments=attachments,
        )
        return RenderResult(
            schema_version=SCHEMA_VERSION,
            video=video,
            audio_ownership=ownership,
            backend_fragments={backend: {"fixture_backend": backend}},
        )


def _request(tmp_path: Path, *, audio: AudioOwnership | None = None) -> RenderRequest:
    timeline = tmp_path / "timeline.json"
    assets = tmp_path / "assets.json"

2026-08-12T14:34:07.453069Z ERROR codex_core::tools::router: error=timeout_ms must be at least 10000
collab: Wait
exec
/bin/zsh -lc "rg -n \"mismatch|normalize|one.segment|single.segment|expected_profile|finalizer\" tests/core/rendering/test_service.py | sed -n '1,260p' && rg -n \"_finish_plan|len\\(segment_results\\)\" .oracle/checkins/batch-4.md .oracle/briefs/batch-4-t4.1.md .oracle/briefs/batch-4-t4.4.md 2>/dev/null | head -n 120" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
185:def _finalizer_resolution(
186:    backend: str = "rendering.ffmpeg-finalizer",
223:        finalizer=_finalizer_resolution(),
308:                    message="fixture finalizer crashed",
309:                    recovery_command="retry fixture finalizer",
408:    finalizers = FinalizerRegistry(
409:        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
412:        registries=(renderers, planners, finalizers),
489:def test_direct_renderer_does_not_require_an_executable_finalizer(
593:    assert ("finalize", "rendering.ffmpeg-finalizer") not in transport.calls
617:    finalizers = FinalizerRegistry(
618:        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
621:        registries=(renderers, planners, finalizers),
645:def test_planned_segment_duration_mismatch_is_rejected(tmp_path: Path) -> None:
854:def test_multiple_segments_run_registered_finalizer(tmp_path: Path) -> None:
869:    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
870:    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")
873:def test_multiple_segments_defer_audio_completion_until_after_finalizer(
910:def test_multiple_segments_allow_finalizer_to_complete_silent_audio_segment(
935:    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
1097:    finalizers = FinalizerRegistry(
1098:        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
1101:        registries=(renderers, planners, finalizers),
1495:        "hybrid-single-segment",
1536:        assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
1565:    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
1581:    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"
1608:    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
1629:    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")
1708:def test_finalizer_failure_removes_workspace_and_commits_nothing(
1712:    transport.fail_finalize = "rendering.ffmpeg-finalizer"
1781:def test_finalizer_preserves_segment_attachments_and_adds_its_own(
.oracle/checkins/batch-4.md:1351:            final_result, plan = self._finish_plan(
.oracle/checkins/batch-4.md:1362:                if len(segment_results) == 1
.oracle/checkins/batch-4.md:1840:        # normalized against their canonical plan profile in _finish_plan.
.oracle/checkins/batch-4.md:2001:            final_result, plan = self._finish_plan(
.oracle/checkins/batch-4.md:2012:                if len(segment_results) == 1
.oracle/checkins/batch-4.md:2363:                # checked against the plan in _finish_plan, while every
.oracle/checkins/batch-4.md:2405:    def _finish_plan(
.oracle/checkins/batch-4.md:2414:        if len(segment_results) == 1:
.oracle/checkins/batch-4.md:8211:  1214	                # checked against the plan in _finish_plan, while every
.oracle/checkins/batch-4.md:8253:  1256	    def _finish_plan(
.oracle/checkins/batch-4.md:8262:  1265	        if len(segment_results) == 1:

exec
/bin/zsh -lc 'cat .oracle/briefs/batch-4-t4.1.md && cat .oracle/briefs/batch-4-t4.4.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
# Task T4.1 — Generic RenderService [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". Batches 1-3 froze the contracts,
transport, asset materialization, profile/artifact validation, publication,
and the Remotion/FFmpeg backends + FFmpeg finalizer. Your job: the generic
`RenderService` that ties them together with the frozen selection order.

## Change

Add `astrid/core/rendering/service.py::RenderService`:

1. Selection order (FROZEN): legacy translation → alias → override → winner →
   eligibility → support → invoke/validate → audio/finalize → publish.
2. Use the registries from Batch 1 (`RendererRegistry`, `PlannerRegistry`,
   `FinalizerRegistry`, `load_default_registries`) for resolution.
3. Legacy translation (the ONLY place that knows short names):
   - `ffmpeg` → strict `rendering.ffmpeg`;
   - `remotion` → characterized legacy policy (FFmpeg for eligible
     media/audio-specialized timelines via the Remotion backend's support,
     else `rendering.remotion`) with an auto-routing warning;
   - `hybrid` → `rendering.legacy_hybrid` planner (NEVER a renderer id);
   - qualified ids are strict.
4. Invoke the selected backend through `CommandTransport` (or in-process
   adapter — pick behavior-preserving), validate the artifact with
   `validate_render_result`, apply host audio completion (render
   passthrough/none handling), run the finalizer when the plan has multiple
   segments, publish via `publish_render_result`, and emit ONE provenance
   sidecar per success.
5. Every successful path → exactly one video + one committed sidecar.
6. Failures → structured `RendererError`s with recovery guidance; cleanup
   temporary artifacts.
7. Add `tests/core/rendering/test_service.py`:
   - full render through `rendering.remotion` (mock the backend, assert the
     service order via spies);
   - strict `rendering.ffmpeg`;
   - legacy `remotion` auto-route (media-only → ffmpeg) with warning;
   - legacy `ffmpeg` strict;
   - `hybrid` selects the planner;
   - unsupported backend → structured error with alternatives;
   - alias/override resolution affecting the winner;
   - eligibility denial;
   - audio completion (passthrough/none);
   - finalizer path (multi-segment);
   - failure cleanup (no temp leftovers);
   - exactly one sidecar per success.

## Acceptance

- `pytest -q tests/core/rendering/test_service.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `transport.py`,
`assets.py`, `publication.py`, `provenance.py` (T4.3 owns it), the backend
modules, or Batch-1 frozen files. Preserve all existing work. Report: files
changed, test results, the selection-order implementation.
# Task T4.4 — Port rendering.legacy_hybrid planner [HARD]

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`.
You have `workspace-write` permissions. Python: `PYENV_VERSION=3.11.11`.

## Context

Batch 4 of "Pluggable Timeline Renderers". T4.1's `RenderService` dispatches
via the frozen selection order. T4.3 handled provenance. Your job: port the
current hybrid planner from the render monolith into
`astrid/packs/rendering/planners/legacy_hybrid/` as a real planner behind
the planner contract, registered as `rendering.legacy_hybrid`. It must
produce a `RenderPlan` with integer half-open `[start_frame,end_frame)`
windows, qualified renderer ids, support-based assignment, an explicit
finalizer, and non-recursive dispatch (the service executes the plan).

## Change

1. Create `astrid/packs/rendering/planners/legacy_hybrid/`:
   - `__init__.py`, `run.py` (raw-command adapter for the `plan` verb:
     reads `--request`, writes a `RenderPlan`-shaped result), `planner.yaml`
     (id `rendering.legacy_hybrid`, protocol_version 1, command
     `[python3, run.py]`, operations `[plan, support]`, capabilities,
     required_permissions).
2. Port the current hybrid heuristics (from
   `astrid/packs/rendering/executors/render/run.py` — `_complex_clip_windows`,
   `_hybrid_segments`, handle/transition math) as the planner's core:
   - resolve the canonical canvas/FPS from the merged theme/timeline view
     (SAME source Remotion uses — profile.py `resolve_render_profile`);
   - convert every segment to integer half-open `[start_frame, end_frame)`;
   - preserve characterized transition units/handles;
   - assign renderers by SUPPORT REPORTS (a segment goes to a backend only
     if that backend's support says it can render the window) — qualified
     ids only;
   - emit an explicit finalizer (`rendering.ffmpeg-finalizer`) and the
     canonical output profile;
   - NEVER recursively call `render()` — the service executes the plan.
3. The `support` verb reports whether hybrid planning can handle the
   request.
4. Add `tests/core/rendering/test_legacy_hybrid.py`:
   - empty plan (zero-frame);
   - single segment;
   - multiple segments;
   - all-FFmpeg hybrid;
   - mixed raw-fixture/built-in plan (the deterministic fixture from Batch 2
     + a built-in);
   - frame rounding (integer windows, exact tiling);
   - transition/handle preservation;
   - speed/overlap rejection (moved to planner support);
   - segment failure cleanup + aligned segment provenance (with T4.3).
5. Register in `astrid/packs/rendering/pack.yaml`
   (`extensions.rendering.planners`).

## Acceptance

- `pytest -q tests/core/rendering/test_legacy_hybrid.py` passes.
- `pytest -q tests/core/rendering` has no NEW failures.
- The old `_hybrid_segments` in the monolith is removed or becomes a thin
  re-export.

Run ONLY those commands. Do NOT run the full suite, formatters, linters. Do
NOT modify `contracts.py`, `schemas/`, `docs/contracts/`, `service.py`
(T4.1), `provenance.py` (T4.3), the backends/finalizer, or Batch-1 frozen
files. Preserve all existing work. Report: files changed, test results, the
planner protocol.

collab: Wait
collab: Wait
collab: Wait
collab: Wait
collab: Wait
collab: Wait
exec
/bin/zsh -lc "sed -n '385,410p' docs/contracts/render-backend-v1.md && nl -ba astrid/core/rendering/service.py | sed -n '520,575p' && nl -ba astrid/core/rendering/provenance.py | sed -n '139,178p' && nl -ba astrid/packs/rendering/executors/render/run.py | sed -n '350,430p;568,585p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

   520	        return Path(published)
   521	
   522	    def _select(
   523	        self,
   524	        request: RenderRequest,
   525	        *,
   526	        policy: _SelectionPolicy,
   527	        workspace: Path,
   528	    ) -> _ResolvedCapability:
   529	        registry: RendererRegistry | PlannerRegistry = (
   530	            self.renderers if policy.kind == "renderer" else self.planners
   531	        )
   532	        rejected: list[dict[str, Any]] = []
   533	        for index, target in enumerate(policy.targets):
   534	            try:
   535	                candidate, evidence = self._resolve_candidate(
   536	                    registry,
   537	                    target,
   538	                    kind=policy.kind,
   539	                )
   540	                report = self._support(
   541	                    candidate,
   542	                    request=request,
   543	                    workspace=workspace,
   544	                    registry=registry,
   545	                )
   546	            except RendererException as exc:
   547	                if not policy.auto_route or index == len(policy.targets) - 1:
   548	                    raise
   549	                if exc.error.kind not in {"unsupported", "binary_missing"}:
   550	                    raise
   551	                rejected.append(exc.error.to_dict())
   552	                continue
   553	            if not report.supported:
   554	                rejected.append(report.to_dict())
   555	                if policy.auto_route and index < len(policy.targets) - 1:
   556	                    continue
   557	                self._unsupported_report(report, registry=registry)
   558	            if policy.auto_route and index == 0:
   559	                warnings.warn(
   560	                    f"legacy selector {policy.requested!r} auto-routed this supported "
   561	                    f"timeline to {candidate.id}; select a qualified renderer "
   562	                    "id for strict routing",
   563	                    LegacyRenderRoutingWarning,
   564	                    stacklevel=4,
   565	                )
   566	            return _ResolvedCapability(candidate, evidence, report)
   567	
   568	        alternatives = self._alternatives(registry)
   569	        raise_unsupported_error(
   570	            backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
   571	            message=f"no renderer supports legacy selector {policy.requested!r}",
   572	            recovery_command=self._recovery_for(alternatives),
   573	            details={"attempts": rejected, "alternatives": alternatives},
   574	        )
   575	
   139	def _routing_record(
   140	    legacy_engine: str,
   141	    plan: RenderPlan,
   142	    resolved_policy: Mapping[str, Any],
   143	) -> dict[str, Any]:
   144	    """Derive selected-policy lineage and visible legacy translation.
   145	
   146	    The service's legacy ``remotion`` policy tries the qualified FFmpeg route
   147	    first and emits a warning when that supported route wins.  The plan pins
   148	    the selected renderer but cannot by itself explain why its legacy
   149	    ``engine`` projection still says ``remotion``.  Record that explanation
   150	    additively while leaving the frozen nested resolution records authoritative
   151	    for aliases, overrides, trust, manifests, and support decisions.
   152	    """
   153	
   154	    renderer_ids = list(resolved_policy["renderers"])
   155	    resolved_backend = renderer_ids[0] if len(renderer_ids) == 1 else None
   156	    auto_routed = (
   157	        legacy_engine == "remotion"
   158	        and len(plan.segments) == 1
   159	        and _resolution_request_id(plan.segments[0]) == "rendering.ffmpeg"
   160	    )
   161	    auto_route_reason = None
   162	    if auto_routed:
   163	        auto_route_reason = (
   164	            "legacy selector 'remotion' auto-routed the supported request to "
   165	            f"{plan.segments[0].renderer.id}"
   166	        )
   167	    return {
   168	        "requested_engine": legacy_engine,
   169	        "requested_policy": plan.requested_policy,
   170	        "resolved_policy": dict(resolved_policy),
   171	        "resolved_backend": resolved_backend,
   172	        "resolved_backends": renderer_ids,
   173	        "auto_route": auto_routed,
   174	        "auto_route_reason": auto_route_reason,
   175	        "segment_reasons": dict(plan.reasons),
   176	    }
   177	
   178	
   350	        profile=profile,
   351	        audio=audio,
   352	    )
   353	
   354	
   355	def _render_hybrid(timeline_path: Path, assets_path: Path, out_path: Path, **remotion_kwargs) -> Path:
   356	    if not timeline_path.exists():
   357	        raise FileNotFoundError(f"Timeline missing: {timeline_path}")
   358	    if not assets_path.exists():
   359	        raise FileNotFoundError(f"Asset registry missing: {assets_path}")
   360	    timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
   361	    canonical_profile = resolve_render_profile(
   362	        timeline_data,
   363	        timeline.load_registry(assets_path),
   364	        theme=remotion_kwargs.get("theme_path"),
   365	        themes_root=REPO_ROOT / "themes",
   366	    )
   367	    segments = _hybrid_segments(
   368	        timeline_data,
   369	        fps=Fraction(*canonical_profile.fps_rational),
   370	    )
   371	    if (
   372	        canonical_profile.fps_rational[1] == 1
   373	        and len(segments) == 1
   374	        and segments[0]["engine"] == "ffmpeg"
   375	    ):
   376	        return _render_ffmpeg_media(timeline_path, assets_path, out_path)
   377	
   378	    publication_out = out_path  # unresolved: publication symlink-guards it
   379	    resolved_out = out_path.resolve()
   380	    resolved_out.parent.mkdir(parents=True, exist_ok=True)
   381	    with TemporaryDirectory(prefix="astrid-hybrid-", dir=str(resolved_out.parent)) as tmp:
   382	        tmp_dir = Path(tmp)
   383	        segment_paths: list[Path] = []
   384	        segment_provenance: list[dict[str, Any]] = []
   385	        for index, segment in enumerate(segments):
   386	            engine = str(segment["engine"])
   387	            start = float(segment["from"])
   388	            end = float(segment["to"])
   389	            segment_dir = tmp_dir / f"{index:04d}-{engine}"
   390	            segment_dir.mkdir(parents=True, exist_ok=True)
   391	            segment_timeline_path = segment_dir / "timeline.json"
   392	            segment_out_path = segment_dir / "segment.mp4"
   393	            segment_timeline = _window_timeline_data(timeline_data, start, end, media_only=(engine == "ffmpeg"))
   394	            if canonical_profile.fps_rational[1] != 1:
   395	                # Both extracted legacy renderers accept an integer canvas
   396	                # rate.  Render the window at the nearest rate, then let the
   397	                # finalizer normalize to the exact canonical rational rate.
   398	                render_rate = max(
   399	                    1,
   400	                    round(Fraction(*canonical_profile.fps_rational)),
   401	                )
   402	                overrides = dict(segment_timeline.get("theme_overrides", {}))
   403	                visual = dict(overrides.get("visual", {}))
   404	                canvas = dict(visual.get("canvas", {}))
   405	                canvas["fps"] = render_rate
   406	                visual["canvas"] = canvas
   407	                overrides["visual"] = visual
   408	                segment_timeline["theme_overrides"] = overrides
   409	            segment_timeline_path.write_text(json.dumps(segment_timeline, indent=2) + "\n", encoding="utf-8")
   410	            if engine == "ffmpeg":
   411	                _render_ffmpeg_media(
   412	                    segment_timeline_path,
   413	                    assets_path,
   414	                    segment_out_path,
   415	                    _previous_outputs=(),
   416	                )
   417	            else:
   418	                render(
   419	                    segment_timeline_path,
   420	                    assets_path,
   421	                    segment_out_path,
   422	                    engine="remotion",
   423	                    **remotion_kwargs,
   424	                )
   425	                sidecar_path = _render_provenance_sidecar_path(segment_out_path)
   426	                if sidecar_path.exists():
   427	                    segment_provenance.append(json.loads(sidecar_path.read_text(encoding="utf-8")))
   428	            segment_paths.append(segment_out_path)
   429	        staged_video = tmp_dir / "final" / out_path.name
   430	        staged_video.parent.mkdir(parents=True, exist_ok=True)
   568	    validate_output_name(out_path.name)
   569	    previous_outputs = (
   570	        ()
   571	        if keep_previous_renders
   572	        else _previous_render_outputs_for_timeline(out_path, timeline_path)
   573	    )
   574	    config = _legacy_backend_config(
   575	        project_dir=project_dir,
   576	        composition_id=composition_id,
   577	        theme_path=theme_path,
   578	        min_free_gb=min_free_gb,
   579	    )
   580	    for key, value in (backend_config or {}).items():
   581	        if value is not None:
   582	            config[str(key)] = dict(value)
   583	    return _default_service().render(
   584	        timeline_path,
   585	        assets_path,

collab: Wait
collab: Wait
codex
Issues:

- HIGH — [service.py:1265](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1265) bypasses the explicit finalizer for every single-segment plan. Normalizable profile mismatches fail, and audio completion runs prematurely at line 1219.

- HIGH — Hybrid alias/override routing is broken. The resolver returns the resolved backend, but [legacy_hybrid/run.py:758](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/planners/legacy_hybrid/run.py:758) compares it with the unresolved configured ID. Valid aliases and overrides are rejected or skipped.

- HIGH — Hybrid renderer/finalizer alias and override lineage is discarded when the service re-resolves emitted target IDs and replaces the planner’s resolution records at [service.py:1169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1169) and [service.py:1235](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1235).

- HIGH — Legacy `remotion` fallback provenance drops the rejected FFmpeg attempt. Rejection evidence accumulated at [service.py:532](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:532) is discarded when Remotion succeeds, so the sidecar lacks complete routing/support lineage.

- MEDIUM — The facade remains concrete and recursive: it imports backend implementations and retains `_render_hybrid()` with backend branching and recursive rendering at [run.py:355](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:355), contrary to the required neutral facade.

- MEDIUM — Explicit backend configuration replaces legacy settings rather than overlaying them at [run.py:580](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:580), silently dropping project/theme/composition values.

- MEDIUM — Conflicting `engine` and `backend` inputs silently prefer `backend` at [run.py:645](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:645), bypassing the service’s conflict validation.

- MEDIUM — The claimed every-built-in-path matrix uses `FakeTransport`; optimized/audio-reactive settings are not exercised by real backends, and hybrid uses a fixture renderer at [test_service.py:1462](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1462).
tokens used
279,659
Issues:

- HIGH — [service.py:1265](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1265) bypasses the explicit finalizer for every single-segment plan. Normalizable profile mismatches fail, and audio completion runs prematurely at line 1219.

- HIGH — Hybrid alias/override routing is broken. The resolver returns the resolved backend, but [legacy_hybrid/run.py:758](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/planners/legacy_hybrid/run.py:758) compares it with the unresolved configured ID. Valid aliases and overrides are rejected or skipped.

- HIGH — Hybrid renderer/finalizer alias and override lineage is discarded when the service re-resolves emitted target IDs and replaces the planner’s resolution records at [service.py:1169](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1169) and [service.py:1235](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:1235).

- HIGH — Legacy `remotion` fallback provenance drops the rejected FFmpeg attempt. Rejection evidence accumulated at [service.py:532](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:532) is discarded when Remotion succeeds, so the sidecar lacks complete routing/support lineage.

- MEDIUM — The facade remains concrete and recursive: it imports backend implementations and retains `_render_hybrid()` with backend branching and recursive rendering at [run.py:355](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:355), contrary to the required neutral facade.

- MEDIUM — Explicit backend configuration replaces legacy settings rather than overlaying them at [run.py:580](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:580), silently dropping project/theme/composition values.

- MEDIUM — Conflicting `engine` and `backend` inputs silently prefer `backend` at [run.py:645](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/rendering/executors/render/run.py:645), bypassing the service’s conflict validation.

- MEDIUM — The claimed every-built-in-path matrix uses `FakeTransport`; optimized/audio-reactive settings are not exercised by real backends, and hybrid uses a fixture renderer at [test_service.py:1462](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/tests/core/rendering/test_service.py:1462).
