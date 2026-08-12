Reading additional input from stdin...
2026-08-12T03:13:20.184284Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:13:20.184311Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:13:20.184316Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: max
reasoning summaries: none
session id: 019ff3f5-cc9b-7011-b9ef-e47dc0ce650c
--------
user
# Megado Checkpoint — Batch 1 twelfth re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.

Prior verdicts: batch-1.md (9), -r1..-r11 (3 each; -r4 had 4). Twelfth rework
committed as `8e4f640` (prior head 6afd558). Incremental diff at
/tmp/batch1-r12.diff.

## How each of your 3 re-review11 issues was addressed (host-implemented)

1. **Sequence lineage missing/non-string paths** →
   - Emitted-lineage records MUST carry a non-empty string `path`; missing,
     `None`, and numeric paths are rejected (no `str()` coercion). Test added.
2. **Python whitespace range malformed** →
   - `_ECMA_WHITESPACE` module-level constant spells every character
     explicitly (no `\u2000-\u200a` range); DTO `strip(_ECMA_WHITESPACE)`
     now rejects `\u2001` correctly. Test added.
3. **Single-component language-dependent whitespace** →
   - `_require_string` emptiness check now uses `_ECMA_WHITESPACE`.
   - Every standalone `\S` in all 8 schema files replaced with the explicit
     ECMA-complement class `[^ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028
     \u2029\u202f\u205f\u3000\ufeff]`; `[\s\S]` (any char) preserved.
   - Cross-checked 21 workspacePath cases including single-component
     `\u0085`/`\uFEFF` and `\u2001`: 0 mismatches.

## Evidence

- Incremental diff: /tmp/batch1-r12.diff (13 files)
- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
  failures), 3 skipped.

## Verdict

Binary: `PASS` or a list of issues. Batch 1 has passed 12 review rounds. If
sound and STABLE, say exactly `PASS` so Batch 2 may begin.
codex
I’m using the Astrid core skill for this repository’s review protocol and the context-mining/subagent skill required by its AGENTS.md. I’ll keep the worktree read-only, inspect the incremental commit and relevant surrounding code/tests, and return only the binary verdict or concrete issues.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/astrid/SKILL.md && sed -n '1,280p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/astrid/SKILL.md /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '241,520p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     772 /Users/peteromalley/.codex/skills/astrid/SKILL.md
      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
     847 total
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

exec
/bin/zsh -lc "sed -n '521,800p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The repository’s context policy calls for independent delegated validation, so I’m applying its subagent-launcher guidance now. I’ll split the review into focused checks while I independently verify the final diff and invariants.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
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

2026-08-12T03:14:07.010522Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:07.010598Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:07.010611Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:12.721298Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:12.721407Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:12.721440Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:16.966642Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:16.966720Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T03:14:16.966773Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git rev-parse HEAD && git show --no-patch --format='%H%n%P%n%s' 8e4f640 && git diff --stat 6afd558..8e4f640 && git diff --check 6afd558..8e4f640 && wc -l /tmp/batch1-r12.diff && sed -n '1,260p' /tmp/batch1-r12.diff" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 2 in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
?? .oracle/checkins/batch-1-r12.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8e4f6404f47ee246f9ec616e0b996cce9b0c9df7
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
8e4f6404f47ee246f9ec616e0b996cce9b0c9df7
6afd558b80898d9892346f9505f229beb476004a
batch1-rework12: oracle re-review11 issues 1-3 (strict string path in lineage records, explicit ECMA whitespace chars no range, ECMA-complement non-whitespace class in all schemas)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-1-r11.md                    | 6336 ++++++++++++++++++++
 astrid/core/rendering/contracts.py                 |   16 +-
 astrid/core/rendering/provenance.py                |    7 +-
 astrid/core/rendering/schemas/v1/finalize.json     |   44 +-
 .../rendering/schemas/v1/finalizer-manifest.json   |   20 +-
 astrid/core/rendering/schemas/v1/plan.json         |   36 +-
 .../rendering/schemas/v1/planner-manifest.json     |   20 +-
 .../rendering/schemas/v1/renderer-manifest.json    |   24 +-
 astrid/core/rendering/schemas/v1/request.json      |   28 +-
 astrid/core/rendering/schemas/v1/result.json       |   32 +-
 astrid/core/rendering/schemas/v1/support.json      |    6 +-
 docs/contracts/render-backend-v1.md                |   26 +-
 tests/core/rendering/test_contracts.py             |   12 +
 13 files changed, 6484 insertions(+), 123 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-1-r11.md:69: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:70: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:72: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:1187: trailing whitespace.
++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:1189: trailing whitespace.
++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:1191: trailing whitespace.
++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:1193: trailing whitespace.
+++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:1195: trailing whitespace.
+++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:1197: trailing whitespace.
+++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:1199: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:1201: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:1203: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:1205: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:1207: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:1209: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:1211: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1213: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1215: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1217: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1219: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1221: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1223: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1225: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1227: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1229: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1231: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1233: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1235: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1237: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1239: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1241: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1243: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1245: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1247: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1249: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1251: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1253: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1255: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1257: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1259: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1261: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1263: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1265: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1267: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1269: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1271: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1273: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1275: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1277: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1279: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1281: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1283: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1285: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1287: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1289: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1291: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1293: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1295: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1297: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1299: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1301: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1303: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1305: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1307: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1309: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1311: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1313: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1315: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1317: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1319: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1321: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1323: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1325: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1327: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1329: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1331: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1333: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1335: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1337: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1339: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1341: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1343: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1345: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1347: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1349: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1351: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1353: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1355: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1357: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1359: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1361: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1363: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1365: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1367: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1369: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1371: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1373: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1375: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1377: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1379: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1381: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1383: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1385: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1387: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1389: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1391: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1393: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1395: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1397: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1399: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1401: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1403: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1405: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1407: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1409: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1411: trailing whitespace.
++++  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:1413: trailing whitespace.
++++  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:1415: trailing whitespace.
++++  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:1417: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1419: trailing whitespace.
++++   730	
.oracle/checkins/batch-1-r11.md:1421: trailing whitespace.
++++   731	
.oracle/checkins/batch-1-r11.md:1423: trailing whitespace.
++++04767bfb (POM 2026-08-12 02:49:29 +0200 721) 
.oracle/checkins/batch-1-r11.md:1425: trailing whitespace.
++++04767bfb (POM 2026-08-12 02:49:29 +0200 722) 
.oracle/checkins/batch-1-r11.md:1427: trailing whitespace.
++++   453	
.oracle/checkins/batch-1-r11.md:1429: trailing whitespace.
++++   461	
.oracle/checkins/batch-1-r11.md:1431: trailing whitespace.
++++   463	
.oracle/checkins/batch-1-r11.md:1433: trailing whitespace.
++++   465	
.oracle/checkins/batch-1-r11.md:1435: trailing whitespace.
++++   470	
.oracle/checkins/batch-1-r11.md:1437: trailing whitespace.
++++   492	
.oracle/checkins/batch-1-r11.md:1439: trailing whitespace.
++++   520	
.oracle/checkins/batch-1-r11.md:1441: trailing whitespace.
++++   539	
.oracle/checkins/batch-1-r11.md:1443: trailing whitespace.
++++   540	
.oracle/checkins/batch-1-r11.md:1445: trailing whitespace.
++++   550	
.oracle/checkins/batch-1-r11.md:1447: trailing whitespace.
++++   551	
.oracle/checkins/batch-1-r11.md:1449: trailing whitespace.
++++   609	
.oracle/checkins/batch-1-r11.md:1451: trailing whitespace.
++++   613	
.oracle/checkins/batch-1-r11.md:1453: trailing whitespace.
++++   614	
.oracle/checkins/batch-1-r11.md:1455: trailing whitespace.
++++   627	
.oracle/checkins/batch-1-r11.md:1457: trailing whitespace.
++++   628	
.oracle/checkins/batch-1-r11.md:1459: trailing whitespace.
++++   631	
.oracle/checkins/batch-1-r11.md:1461: trailing whitespace.
++++   640	
.oracle/checkins/batch-1-r11.md:1463: trailing whitespace.
++++   641	
.oracle/checkins/batch-1-r11.md:1465: trailing whitespace.
++++   647	
.oracle/checkins/batch-1-r11.md:1467: trailing whitespace.
++++   648	
.oracle/checkins/batch-1-r11.md:1469: trailing whitespace.
++++   679	
.oracle/checkins/batch-1-r11.md:1471: trailing whitespace.
++++   689	
.oracle/checkins/batch-1-r11.md:1473: trailing whitespace.
++++   721	
.oracle/checkins/batch-1-r11.md:1475: trailing whitespace.
++++   722	
.oracle/checkins/batch-1-r11.md:1477: trailing whitespace.
++++   740	
.oracle/checkins/batch-1-r11.md:1479: trailing whitespace.
++++   741	
.oracle/checkins/batch-1-r11.md:1481: trailing whitespace.
++++   777	
.oracle/checkins/batch-1-r11.md:1483: trailing whitespace.
++++   778	
.oracle/checkins/batch-1-r11.md:1485: trailing whitespace.
++++   792	
.oracle/checkins/batch-1-r11.md:1487: trailing whitespace.
++++   793	
.oracle/checkins/batch-1-r11.md:1489: trailing whitespace.
++++   809	
.oracle/checkins/batch-1-r11.md:1491: trailing whitespace.
++++   810	
.oracle/checkins/batch-1-r11.md:1493: trailing whitespace.
++++   904	
.oracle/checkins/batch-1-r11.md:1495: trailing whitespace.
++++   905	
.oracle/checkins/batch-1-r11.md:1497: trailing whitespace.
++++   965	
.oracle/checkins/batch-1-r11.md:1499: trailing whitespace.
++++   966	
.oracle/checkins/batch-1-r11.md:1501: trailing whitespace.
++++   975	
.oracle/checkins/batch-1-r11.md:1503: trailing whitespace.
++++   976	
.oracle/checkins/batch-1-r11.md:1505: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r11.md:1507: trailing whitespace.
++++     4	
.oracle/checkins/batch-1-r11.md:1509: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r11.md:1511: trailing whitespace.
++++    11	
.oracle/checkins/batch-1-r11.md:1513: trailing whitespace.
++++    28	
.oracle/checkins/batch-1-r11.md:1515: trailing whitespace.
++++    29	
.oracle/checkins/batch-1-r11.md:1517: trailing whitespace.
++++    32	
.oracle/checkins/batch-1-r11.md:1519: trailing whitespace.
++++    33	
.oracle/checkins/batch-1-r11.md:1521: trailing whitespace.
++++    38	
.oracle/checkins/batch-1-r11.md:1523: trailing whitespace.
++++    40	
.oracle/checkins/batch-1-r11.md:1525: trailing whitespace.
++++    41	
.oracle/checkins/batch-1-r11.md:1527: trailing whitespace.
++++    53	
.oracle/checkins/batch-1-r11.md:1529: trailing whitespace.
++++    54	
.oracle/checkins/batch-1-r11.md:1531: trailing whitespace.
++++    81	
.oracle/checkins/batch-1-r11.md:1533: trailing whitespace.
++++    82	
.oracle/checkins/batch-1-r11.md:1535: trailing whitespace.
++++    85	
.oracle/checkins/batch-1-r11.md:1537: trailing whitespace.
++++    92	
.oracle/checkins/batch-1-r11.md:1539: trailing whitespace.
++++    93	
.oracle/checkins/batch-1-r11.md:1541: trailing whitespace.
++++   105	
.oracle/checkins/batch-1-r11.md:1543: trailing whitespace.
++++   106	
.oracle/checkins/batch-1-r11.md:1545: trailing whitespace.
++++   168	
.oracle/checkins/batch-1-r11.md:1547: trailing whitespace.
++++   169	
.oracle/checkins/batch-1-r11.md:1549: trailing whitespace.
++++   236	
.oracle/checkins/batch-1-r11.md:1551: trailing whitespace.
++++   237	
.oracle/checkins/batch-1-r11.md:1553: trailing whitespace.
++++   248	
.oracle/checkins/batch-1-r11.md:1555: trailing whitespace.
++++   249	
.oracle/checkins/batch-1-r11.md:1557: trailing whitespace.
++++   271	
.oracle/checkins/batch-1-r11.md:1559: trailing whitespace.
++++   272	
.oracle/checkins/batch-1-r11.md:1561: trailing whitespace.
++++   288	
.oracle/checkins/batch-1-r11.md:1563: trailing whitespace.
++++   295	
.oracle/checkins/batch-1-r11.md:1565: trailing whitespace.
++++   316	
.oracle/checkins/batch-1-r11.md:1567: trailing whitespace.
++++   343	
.oracle/checkins/batch-1-r11.md:1569: trailing whitespace.
++++   344	
.oracle/checkins/batch-1-r11.md:1571: trailing whitespace.
++++   347	
.oracle/checkins/batch-1-r11.md:1573: trailing whitespace.
++++   349	
.oracle/checkins/batch-1-r11.md:1575: trailing whitespace.
++++   350	
.oracle/checkins/batch-1-r11.md:1577: trailing whitespace.
++++   353	
.oracle/checkins/batch-1-r11.md:1579: trailing whitespace.
++++   357	
.oracle/checkins/batch-1-r11.md:1581: trailing whitespace.
++++   358	
.oracle/checkins/batch-1-r11.md:1583: trailing whitespace.
++++   361	
.oracle/checkins/batch-1-r11.md:1585: trailing whitespace.
++++   366	
.oracle/checkins/batch-1-r11.md:1587: trailing whitespace.
++++   367	
.oracle/checkins/batch-1-r11.md:1589: trailing whitespace.
++++   370	
.oracle/checkins/batch-1-r11.md:1591: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r11.md:1593: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r11.md:1595: trailing whitespace.
++++    10	
.oracle/checkins/batch-1-r11.md:1597: trailing whitespace.
++++    18	
.oracle/checkins/batch-1-r11.md:1599: trailing whitespace.
++++    21	
.oracle/checkins/batch-1-r11.md:1601: trailing whitespace.
++++    22	
.oracle/checkins/batch-1-r11.md:1603: trailing whitespace.
++++    24	
.oracle/checkins/batch-1-r11.md:1605: trailing whitespace.
++++    35	
.oracle/checkins/batch-1-r11.md:1607: trailing whitespace.
++++    40	
.oracle/checkins/batch-1-r11.md:1609: trailing whitespace.
++++    52	
.oracle/checkins/batch-1-r11.md:1611: trailing whitespace.
++++    73	
.oracle/checkins/batch-1-r11.md:1613: trailing whitespace.
++++    93	
.oracle/checkins/batch-1-r11.md:1615: trailing whitespace.
++++   110	
.oracle/checkins/batch-1-r11.md:1617: trailing whitespace.
++++   123	
.oracle/checkins/batch-1-r11.md:1619: trailing whitespace.
++++   130	
.oracle/checkins/batch-1-r11.md:1621: trailing whitespace.
++++   131	
.oracle/checkins/batch-1-r11.md:1623: trailing whitespace.
++++   134	
.oracle/checkins/batch-1-r11.md:1625: trailing whitespace.
++++   158	
.oracle/checkins/batch-1-r11.md:1627: trailing whitespace.
++++   159	
.oracle/checkins/batch-1-r11.md:1629: trailing whitespace.
++++   165	
.oracle/checkins/batch-1-r11.md:1631: trailing whitespace.
++++   166	
.oracle/checkins/batch-1-r11.md:1633: trailing whitespace.
++++   171	
.oracle/checkins/batch-1-r11.md:1635: trailing whitespace.
++++   172	
.oracle/checkins/batch-1-r11.md:1637: trailing whitespace.
++++   186	
.oracle/checkins/batch-1-r11.md:1639: trailing whitespace.
++++   187	
.oracle/checkins/batch-1-r11.md:1641: trailing whitespace.
++++   194	
.oracle/checkins/batch-1-r11.md:1643: trailing whitespace.
++++   195	
.oracle/checkins/batch-1-r11.md:1645: trailing whitespace.
++++   205	
.oracle/checkins/batch-1-r11.md:1647: trailing whitespace.
++++   206	
.oracle/checkins/batch-1-r11.md:1649: trailing whitespace.
++++   209	
.oracle/checkins/batch-1-r11.md:1651: trailing whitespace.
++++   215	
.oracle/checkins/batch-1-r11.md:1653: trailing whitespace.
++++   216	
.oracle/checkins/batch-1-r11.md:1655: trailing whitespace.
++++   225	
.oracle/checkins/batch-1-r11.md:1657: trailing whitespace.
++++   226	
.oracle/checkins/batch-1-r11.md:1659: trailing whitespace.
++++   231	
.oracle/checkins/batch-1-r11.md:1661: trailing whitespace.
++++   232	
.oracle/checkins/batch-1-r11.md:1663: trailing whitespace.
++++   241	
.oracle/checkins/batch-1-r11.md:1665: trailing whitespace.
++++   242	
.oracle/checkins/batch-1-r11.md:1667: trailing whitespace.
++++   248	
.oracle/checkins/batch-1-r11.md:1669: trailing whitespace.
++++   249	
.oracle/checkins/batch-1-r11.md:1671: trailing whitespace.
++++   507	
.oracle/checkins/batch-1-r11.md:1673: trailing whitespace.
++++   511	
.oracle/checkins/batch-1-r11.md:1675: trailing whitespace.
++++   530	
.oracle/checkins/batch-1-r11.md:1677: trailing whitespace.
++++   563	
.oracle/checkins/batch-1-r11.md:1679: trailing whitespace.
++++   564	
.oracle/checkins/batch-1-r11.md:1681: trailing whitespace.
++++   571	
.oracle/checkins/batch-1-r11.md:1683: trailing whitespace.
++++   576	
.oracle/checkins/batch-1-r11.md:1685: trailing whitespace.
++++   582	
.oracle/checkins/batch-1-r11.md:1687: trailing whitespace.
++++   583	
.oracle/checkins/batch-1-r11.md:1689: trailing whitespace.
++++   587	
.oracle/checkins/batch-1-r11.md:1691: trailing whitespace.
++++   592	
.oracle/checkins/batch-1-r11.md:1693: trailing whitespace.
++++   604	
.oracle/checkins/batch-1-r11.md:1695: trailing whitespace.
++++   609	
.oracle/checkins/batch-1-r11.md:1697: trailing whitespace.
++++   621	
.oracle/checkins/batch-1-r11.md:1699: trailing whitespace.
++++   633	
.oracle/checkins/batch-1-r11.md:1701: trailing whitespace.
++++   634	
.oracle/checkins/batch-1-r11.md:1703: trailing whitespace.
++++   655	
.oracle/checkins/batch-1-r11.md:1705: trailing whitespace.
++++   656	
.oracle/checkins/batch-1-r11.md:1707: trailing whitespace.
++++   660	
.oracle/checkins/batch-1-r11.md:1709: trailing whitespace.
++++   667	
.oracle/checkins/batch-1-r11.md:1711: trailing whitespace.
++++   690	
.oracle/checkins/batch-1-r11.md:1713: trailing whitespace.
++++   702	
.oracle/checkins/batch-1-r11.md:1715: trailing whitespace.
++++   717	
.oracle/checkins/batch-1-r11.md:1717: trailing whitespace.
++++  1662	
.oracle/checkins/batch-1-r11.md:1719: trailing whitespace.
++++  1686	
.oracle/checkins/batch-1-r11.md:1721: trailing whitespace.
++++  1693	
.oracle/checkins/batch-1-r11.md:1723: trailing whitespace.
++++  1694	
.oracle/checkins/batch-1-r11.md:1725: trailing whitespace.
++++  1698	
.oracle/checkins/batch-1-r11.md:1727: trailing whitespace.
++++  1705	
.oracle/checkins/batch-1-r11.md:1729: trailing whitespace.
++++  1753	
.oracle/checkins/batch-1-r11.md:1731: trailing whitespace.
++++  1757	
.oracle/checkins/batch-1-r11.md:1733: trailing whitespace.
++++  1763	
.oracle/checkins/batch-1-r11.md:1735: trailing whitespace.
++++  1769	
.oracle/checkins/batch-1-r11.md:1737: trailing whitespace.
++++  1773	
.oracle/checkins/batch-1-r11.md:1739: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r11.md:1741: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r11.md:1743: trailing whitespace.
++++    11	
.oracle/checkins/batch-1-r11.md:1745: trailing whitespace.
++++    20	
.oracle/checkins/batch-1-r11.md:1747: trailing whitespace.
++++    21	
.oracle/checkins/batch-1-r11.md:1749: trailing whitespace.
++++    48	
.oracle/checkins/batch-1-r11.md:1751: trailing whitespace.
++++    49	
.oracle/checkins/batch-1-r11.md:1753: trailing whitespace.
++++    52	
.oracle/checkins/batch-1-r11.md:1755: trailing whitespace.
++++    53	
.oracle/checkins/batch-1-r11.md:1757: trailing whitespace.
++++    56	
.oracle/checkins/batch-1-r11.md:1759: trailing whitespace.
++++    57	
.oracle/checkins/batch-1-r11.md:1761: trailing whitespace.
++++    60	
.oracle/checkins/batch-1-r11.md:1763: trailing whitespace.
++++    61	
.oracle/checkins/batch-1-r11.md:1765: trailing whitespace.
++++    72	
.oracle/checkins/batch-1-r11.md:1767: trailing whitespace.
++++    73	
.oracle/checkins/batch-1-r11.md:1769: trailing whitespace.
++++    81	
.oracle/checkins/batch-1-r11.md:1771: trailing whitespace.
++++    88	
.oracle/checkins/batch-1-r11.md:1773: trailing whitespace.
++++    89	
.oracle/checkins/batch-1-r11.md:1775: trailing whitespace.
++++    96	
.oracle/checkins/batch-1-r11.md:1777: trailing whitespace.
++++    97	
.oracle/checkins/batch-1-r11.md:1779: trailing whitespace.
++++   105	
.oracle/checkins/batch-1-r11.md:1781: trailing whitespace.
++++   106	
.oracle/checkins/batch-1-r11.md:1783: trailing whitespace.
++++   113	
.oracle/checkins/batch-1-r11.md:1785: trailing whitespace.
++++   114	
.oracle/checkins/batch-1-r11.md:1787: trailing whitespace.
++++   312	
.oracle/checkins/batch-1-r11.md:1789: trailing whitespace.
++++   313	
.oracle/checkins/batch-1-r11.md:1791: trailing whitespace.
++++   324	
.oracle/checkins/batch-1-r11.md:1793: trailing whitespace.
++++   325	
.oracle/checkins/batch-1-r11.md:1795: trailing whitespace.
++++   338	
.oracle/checkins/batch-1-r11.md:1797: trailing whitespace.
++++   339	
.oracle/checkins/batch-1-r11.md:1799: trailing whitespace.
++++   356	
.oracle/checkins/batch-1-r11.md:1801: trailing whitespace.
++++   357	
.oracle/checkins/batch-1-r11.md:1803: trailing whitespace.
++++   375	
.oracle/checkins/batch-1-r11.md:1805: trailing whitespace.
++++   376	
.oracle/checkins/batch-1-r11.md:1807: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1809: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1811: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1813: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1815: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1817: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1819: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1821: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1823: trailing whitespace.
++++ 
.oracle/checkins/batch-1-r11.md:1825: trailing whitespace.
++++   809	
.oracle/checkins/batch-1-r11.md:1827: trailing whitespace.
++++   810	
.oracle/checkins/batch-1-r11.md:1829: trailing whitespace.
++++   904	
.oracle/checkins/batch-1-r11.md:1831: trailing whitespace.
++++   905	
.oracle/checkins/batch-1-r11.md:1833: trailing whitespace.
++++   965	
.oracle/checkins/batch-1-r11.md:1835: trailing whitespace.
++++   966	
.oracle/checkins/batch-1-r11.md:1837: trailing whitespace.
++++     2	
.oracle/checkins/batch-1-r11.md:1839: trailing whitespace.
++++     4	
.oracle/checkins/batch-1-r11.md:1841: trailing whitespace.
++++     6	
.oracle/checkins/batch-1-r11.md:1843: trailing whitespace.
++++     8	
.oracle/checkins/batch-1-r11.md:1845: trailing whitespace.
++++    17	
.oracle/checkins/batch-1-r11.md:1847: trailing whitespace.
++++    19	
.oracle/checkins/batch-1-r11.md:1849: trailing whitespace.
++++    25	
.oracle/checkins/batch-1-r11.md:1851: trailing whitespace.
++++    27	
.oracle/checkins/batch-1-r11.md:1853: trailing whitespace.
++++    29	
.oracle/checkins/batch-1-r11.md:1855: trailing whitespace.
++++    31	
.oracle/checkins/batch-1-r11.md:1857: trailing whitespace.
++++    40	
.oracle/checkins/batch-1-r11.md:1859: trailing whitespace.
++++    42	
.oracle/checkins/batch-1-r11.md:1861: trailing whitespace.
++++    49	
.oracle/checkins/batch-1-r11.md:1863: trailing whitespace.
++++    51	
.oracle/checkins/batch-1-r11.md:1865: trailing whitespace.
++++    53	
.oracle/checkins/batch-1-r11.md:1867: trailing whitespace.
++++    55	
.oracle/checkins/batch-1-r11.md:1869: trailing whitespace.
++++    63	
.oracle/checkins/batch-1-r11.md:1871: trailing whitespace.
++++    65	
.oracle/checkins/batch-1-r11.md:1873: trailing whitespace.
++++    72	
.oracle/checkins/batch-1-r11.md:1875: trailing whitespace.
++++    74	
.oracle/checkins/batch-1-r11.md:1877: trailing whitespace.
++++    76	
.oracle/checkins/batch-1-r11.md:1879: trailing whitespace.
++++    78	
.oracle/checkins/batch-1-r11.md:1881: trailing whitespace.
++++   131	
.oracle/checkins/batch-1-r11.md:1883: trailing whitespace.
++++   132	
.oracle/checkins/batch-1-r11.md:1885: trailing whitespace.
++++   162	
.oracle/checkins/batch-1-r11.md:1887: trailing whitespace.
++++   163	
.oracle/checkins/batch-1-r11.md:1889: trailing whitespace.
++++   178	
.oracle/checkins/batch-1-r11.md:1891: trailing whitespace.
++++   179	
.oracle/checkins/batch-1-r11.md:1893: trailing whitespace.
++++   206	
.oracle/checkins/batch-1-r11.md:1895: trailing whitespace.
++++   207	
.oracle/checkins/batch-1-r11.md:1897: trailing whitespace.
++++   249	
.oracle/checkins/batch-1-r11.md:1899: trailing whitespace.
++++   250	
.oracle/checkins/batch-1-r11.md:1901: trailing whitespace.
++++   288	
.oracle/checkins/batch-1-r11.md:1903: trailing whitespace.
++++   289	
.oracle/checkins/batch-1-r11.md:1905: trailing whitespace.
++++   302	
.oracle/checkins/batch-1-r11.md:1907: trailing whitespace.
++++   303	
.oracle/checkins/batch-1-r11.md:1909: trailing whitespace.
++++   312	
.oracle/checkins/batch-1-r11.md:1911: trailing whitespace.
++++   313	
.oracle/checkins/batch-1-r11.md:1913: trailing whitespace.
++++   330	
.oracle/checkins/batch-1-r11.md:1915: trailing whitespace.
++++   331	
.oracle/checkins/batch-1-r11.md:1917: trailing whitespace.
++++   343	
.oracle/checkins/batch-1-r11.md:1919: trailing whitespace.
++++   344	
.oracle/checkins/batch-1-r11.md:1921: trailing whitespace.
++++   288	
.oracle/checkins/batch-1-r11.md:1923: trailing whitespace.
++++    98	
.oracle/checkins/batch-1-r11.md:1925: trailing whitespace.
++++   101	
.oracle/checkins/batch-1-r11.md:1927: trailing whitespace.
++++   106	
.oracle/checkins/batch-1-r11.md:1929: trailing whitespace.
++++   107	
.oracle/checkins/batch-1-r11.md:1931: trailing whitespace.
++++   110	
.oracle/checkins/batch-1-r11.md:1933: trailing whitespace.
++++   113	
.oracle/checkins/batch-1-r11.md:1935: trailing whitespace.
++++  1349	
.oracle/checkins/batch-1-r11.md:1937: trailing whitespace.
++++  1350	
.oracle/checkins/batch-1-r11.md:1939: trailing whitespace.
++++  1354	
.oracle/checkins/batch-1-r11.md:1941: trailing whitespace.
++++  1365	
.oracle/checkins/batch-1-r11.md:1943: trailing whitespace.
++++  1444	
.oracle/checkins/batch-1-r11.md:1945: trailing whitespace.
++++  1460	
.oracle/checkins/batch-1-r11.md:1947: trailing whitespace.
+++  1444	
.oracle/checkins/batch-1-r11.md:1949: trailing whitespace.
+++  1460	
.oracle/checkins/batch-1-r11.md:1951: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1953: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1955: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1957: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1959: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1961: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1963: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1965: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1967: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1969: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1971: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1973: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1975: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1977: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1979: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1981: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1983: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1985: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1987: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1989: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1991: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1993: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1995: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1997: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:1999: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2001: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2003: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2005: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2007: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2009: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2011: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2013: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2015: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2017: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2019: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2021: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2023: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2025: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2027: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2029: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2031: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2033: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2035: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2037: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2039: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2041: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2043: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2045: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2047: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2049: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2051: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2053: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2055: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2057: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2059: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2061: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2063: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2065: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2067: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2069: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2071: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2073: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2075: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2077: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2079: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2081: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2083: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2085: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2087: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2089: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2091: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2093: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2095: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2097: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2099: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2101: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2103: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2105: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2107: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2109: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2111: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2113: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2115: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2117: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2119: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2121: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2123: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2125: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2127: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2129: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2131: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2133: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2135: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2137: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2139: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2141: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2143: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2145: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2147: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2149: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2151: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2153: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2155: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2157: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2159: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2161: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2163: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2165: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2167: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2169: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2171: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2173: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2175: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2177: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2179: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2181: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2183: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r11.md:2185: trailing whitespace.
+++     4	
.oracle/checkins/batch-1-r11.md:2187: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r11.md:2189: trailing whitespace.
+++    11	
.oracle/checkins/batch-1-r11.md:2191: trailing whitespace.
+++    28	
.oracle/checkins/batch-1-r11.md:2193: trailing whitespace.
+++    29	
.oracle/checkins/batch-1-r11.md:2195: trailing whitespace.
+++    32	
.oracle/checkins/batch-1-r11.md:2197: trailing whitespace.
+++    33	
.oracle/checkins/batch-1-r11.md:2199: trailing whitespace.
+++    38	
.oracle/checkins/batch-1-r11.md:2201: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r11.md:2203: trailing whitespace.
+++    41	
.oracle/checkins/batch-1-r11.md:2205: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r11.md:2207: trailing whitespace.
+++    54	
.oracle/checkins/batch-1-r11.md:2209: trailing whitespace.
+++    81	
.oracle/checkins/batch-1-r11.md:2211: trailing whitespace.
+++    82	
.oracle/checkins/batch-1-r11.md:2213: trailing whitespace.
+++    85	
.oracle/checkins/batch-1-r11.md:2215: trailing whitespace.
+++    92	
.oracle/checkins/batch-1-r11.md:2217: trailing whitespace.
+++    93	
.oracle/checkins/batch-1-r11.md:2219: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r11.md:2221: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r11.md:2223: trailing whitespace.
+++   173	
.oracle/checkins/batch-1-r11.md:2225: trailing whitespace.
+++   174	
.oracle/checkins/batch-1-r11.md:2227: trailing whitespace.
+++   248	
.oracle/checkins/batch-1-r11.md:2229: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r11.md:2231: trailing whitespace.
+++   260	
.oracle/checkins/batch-1-r11.md:2233: trailing whitespace.
+++   261	
.oracle/checkins/batch-1-r11.md:2235: trailing whitespace.
+++   283	
.oracle/checkins/batch-1-r11.md:2237: trailing whitespace.
+++   284	
.oracle/checkins/batch-1-r11.md:2239: trailing whitespace.
+++   300	
.oracle/checkins/batch-1-r11.md:2241: trailing whitespace.
+++   307	
.oracle/checkins/batch-1-r11.md:2243: trailing whitespace.
+++   328	
.oracle/checkins/batch-1-r11.md:2245: trailing whitespace.
+++   355	
.oracle/checkins/batch-1-r11.md:2247: trailing whitespace.
+++   356	
.oracle/checkins/batch-1-r11.md:2249: trailing whitespace.
+++   359	
.oracle/checkins/batch-1-r11.md:2251: trailing whitespace.
+++   361	
.oracle/checkins/batch-1-r11.md:2253: trailing whitespace.
+++   362	
.oracle/checkins/batch-1-r11.md:2255: trailing whitespace.
+++   365	
.oracle/checkins/batch-1-r11.md:2257: trailing whitespace.
+++   369	
.oracle/checkins/batch-1-r11.md:2259: trailing whitespace.
+++   370	
.oracle/checkins/batch-1-r11.md:2261: trailing whitespace.
+++   373	
.oracle/checkins/batch-1-r11.md:2263: trailing whitespace.
+++   378	
.oracle/checkins/batch-1-r11.md:2265: trailing whitespace.
+++   379	
.oracle/checkins/batch-1-r11.md:2267: trailing whitespace.
+++   382	
.oracle/checkins/batch-1-r11.md:2269: trailing whitespace.
+++   384	
.oracle/checkins/batch-1-r11.md:2271: trailing whitespace.
+++   385	
.oracle/checkins/batch-1-r11.md:2273: trailing whitespace.
+++   651	
.oracle/checkins/batch-1-r11.md:2275: trailing whitespace.
+++   652	
.oracle/checkins/batch-1-r11.md:2277: trailing whitespace.
+++   683	
.oracle/checkins/batch-1-r11.md:2279: trailing whitespace.
+++   693	
.oracle/checkins/batch-1-r11.md:2281: trailing whitespace.
+++   729	
.oracle/checkins/batch-1-r11.md:2283: trailing whitespace.
+++   730	
.oracle/checkins/batch-1-r11.md:2285: trailing whitespace.
+++   748	
.oracle/checkins/batch-1-r11.md:2287: trailing whitespace.
+++   749	
.oracle/checkins/batch-1-r11.md:2289: trailing whitespace.
+++   785	
.oracle/checkins/batch-1-r11.md:2291: trailing whitespace.
+++   786	
.oracle/checkins/batch-1-r11.md:2293: trailing whitespace.
+++   800	
.oracle/checkins/batch-1-r11.md:2295: trailing whitespace.
+++   801	
.oracle/checkins/batch-1-r11.md:2297: trailing whitespace.
+++   817	
.oracle/checkins/batch-1-r11.md:2299: trailing whitespace.
+++   818	
.oracle/checkins/batch-1-r11.md:2301: trailing whitespace.
+++   914	
.oracle/checkins/batch-1-r11.md:2303: trailing whitespace.
+++   915	
.oracle/checkins/batch-1-r11.md:2305: trailing whitespace.
+++  1001	
.oracle/checkins/batch-1-r11.md:2307: trailing whitespace.
+++  1002	
.oracle/checkins/batch-1-r11.md:2309: trailing whitespace.
+++  1011	
.oracle/checkins/batch-1-r11.md:2311: trailing whitespace.
+++  1012	
.oracle/checkins/batch-1-r11.md:2313: trailing whitespace.
+++   285	
.oracle/checkins/batch-1-r11.md:2315: trailing whitespace.
+++   294	
.oracle/checkins/batch-1-r11.md:2317: trailing whitespace.
+++   295	
.oracle/checkins/batch-1-r11.md:2319: trailing whitespace.
+++   302	
.oracle/checkins/batch-1-r11.md:2321: trailing whitespace.
+++   303	
.oracle/checkins/batch-1-r11.md:2323: trailing whitespace.
+++   312	
.oracle/checkins/batch-1-r11.md:2325: trailing whitespace.
+++   313	
.oracle/checkins/batch-1-r11.md:2327: trailing whitespace.
+++   330	
.oracle/checkins/batch-1-r11.md:2329: trailing whitespace.
+++   331	
.oracle/checkins/batch-1-r11.md:2331: trailing whitespace.
+++   826	
.oracle/checkins/batch-1-r11.md:2333: trailing whitespace.
+++   868	
.oracle/checkins/batch-1-r11.md:2335: trailing whitespace.
+++   875	
.oracle/checkins/batch-1-r11.md:2337: trailing whitespace.
+++   878	
.oracle/checkins/batch-1-r11.md:2339: trailing whitespace.
+++   892	
.oracle/checkins/batch-1-r11.md:2341: trailing whitespace.
+++   893	
.oracle/checkins/batch-1-r11.md:2343: trailing whitespace.
+++   897	
.oracle/checkins/batch-1-r11.md:2345: trailing whitespace.
+++   905	
.oracle/checkins/batch-1-r11.md:2347: trailing whitespace.
+++   936	
.oracle/checkins/batch-1-r11.md:2349: trailing whitespace.
+++   949	
.oracle/checkins/batch-1-r11.md:2351: trailing whitespace.
+++   980	
.oracle/checkins/batch-1-r11.md:2353: trailing whitespace.
+++   987	
.oracle/checkins/batch-1-r11.md:2355: trailing whitespace.
+++   988	
.oracle/checkins/batch-1-r11.md:2357: trailing whitespace.
+++   992	
.oracle/checkins/batch-1-r11.md:2359: trailing whitespace.
+++  1000	
.oracle/checkins/batch-1-r11.md:2361: trailing whitespace.
+++   440	
.oracle/checkins/batch-1-r11.md:2363: trailing whitespace.
+++   441	
.oracle/checkins/batch-1-r11.md:2365: trailing whitespace.
+++   445	
.oracle/checkins/batch-1-r11.md:2367: trailing whitespace.
+++   459	
.oracle/checkins/batch-1-r11.md:2369: trailing whitespace.
+++   507	
.oracle/checkins/batch-1-r11.md:2371: trailing whitespace.
+++   511	
.oracle/checkins/batch-1-r11.md:2373: trailing whitespace.
+++   530	
.oracle/checkins/batch-1-r11.md:2375: trailing whitespace.
+++   563	
.oracle/checkins/batch-1-r11.md:2377: trailing whitespace.
+++   564	
.oracle/checkins/batch-1-r11.md:2379: trailing whitespace.
+++   571	
.oracle/checkins/batch-1-r11.md:2381: trailing whitespace.
+++   576	
.oracle/checkins/batch-1-r11.md:2383: trailing whitespace.
+++   582	
.oracle/checkins/batch-1-r11.md:2385: trailing whitespace.
+++   583	
.oracle/checkins/batch-1-r11.md:2387: trailing whitespace.
+++   587	
.oracle/checkins/batch-1-r11.md:2389: trailing whitespace.
+++   592	
.oracle/checkins/batch-1-r11.md:2391: trailing whitespace.
+++   604	
.oracle/checkins/batch-1-r11.md:2393: trailing whitespace.
+++   609	
.oracle/checkins/batch-1-r11.md:2395: trailing whitespace.
+++   621	
.oracle/checkins/batch-1-r11.md:2397: trailing whitespace.
+++   633	
.oracle/checkins/batch-1-r11.md:2399: trailing whitespace.
+++   634	
.oracle/checkins/batch-1-r11.md:2401: trailing whitespace.
+++   655	
.oracle/checkins/batch-1-r11.md:2403: trailing whitespace.
+++   656	
.oracle/checkins/batch-1-r11.md:2405: trailing whitespace.
+++   660	
.oracle/checkins/batch-1-r11.md:2407: trailing whitespace.
+++   667	
.oracle/checkins/batch-1-r11.md:2409: trailing whitespace.
+++   690	
.oracle/checkins/batch-1-r11.md:2411: trailing whitespace.
+++   702	
.oracle/checkins/batch-1-r11.md:2413: trailing whitespace.
+++   717	
.oracle/checkins/batch-1-r11.md:2415: trailing whitespace.
+++   225	
.oracle/checkins/batch-1-r11.md:2417: trailing whitespace.
+++   230	
.oracle/checkins/batch-1-r11.md:2419: trailing whitespace.
+++   238	
.oracle/checkins/batch-1-r11.md:2421: trailing whitespace.
+++   240	
.oracle/checkins/batch-1-r11.md:2423: trailing whitespace.
+++   243	
.oracle/checkins/batch-1-r11.md:2425: trailing whitespace.
+++   251	
.oracle/checkins/batch-1-r11.md:2427: trailing whitespace.
+++   255	
.oracle/checkins/batch-1-r11.md:2429: trailing whitespace.
+++   257	
.oracle/checkins/batch-1-r11.md:2431: trailing whitespace.
+++   262	
.oracle/checkins/batch-1-r11.md:2433: trailing whitespace.
+++   274	
.oracle/checkins/batch-1-r11.md:2435: trailing whitespace.
+++   276	
.oracle/checkins/batch-1-r11.md:2437: trailing whitespace.
+++   280	
.oracle/checkins/batch-1-r11.md:2439: trailing whitespace.
+++   290	
.oracle/checkins/batch-1-r11.md:2441: trailing whitespace.
+++   292	
.oracle/checkins/batch-1-r11.md:2443: trailing whitespace.
+++   461	
.oracle/checkins/batch-1-r11.md:2445: trailing whitespace.
+++   463	
.oracle/checkins/batch-1-r11.md:2447: trailing whitespace.
+++   465	
.oracle/checkins/batch-1-r11.md:2449: trailing whitespace.
+++   470	
.oracle/checkins/batch-1-r11.md:2451: trailing whitespace.
+++   492	
.oracle/checkins/batch-1-r11.md:2453: trailing whitespace.
+++   502	
.oracle/checkins/batch-1-r11.md:2455: trailing whitespace.
+++   504	
.oracle/checkins/batch-1-r11.md:2457: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r11.md:2459: trailing whitespace.
+++     4	
.oracle/checkins/batch-1-r11.md:2461: trailing whitespace.
+++     6	
.oracle/checkins/batch-1-r11.md:2463: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r11.md:2465: trailing whitespace.
+++    17	
.oracle/checkins/batch-1-r11.md:2467: trailing whitespace.
+++    19	
.oracle/checkins/batch-1-r11.md:2469: trailing whitespace.
+++    25	
.oracle/checkins/batch-1-r11.md:2471: trailing whitespace.
+++    27	
.oracle/checkins/batch-1-r11.md:2473: trailing whitespace.
+++    29	
.oracle/checkins/batch-1-r11.md:2475: trailing whitespace.
+++    31	
.oracle/checkins/batch-1-r11.md:2477: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r11.md:2479: trailing whitespace.
+++    42	
.oracle/checkins/batch-1-r11.md:2481: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r11.md:2483: trailing whitespace.
+++    51	
.oracle/checkins/batch-1-r11.md:2485: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r11.md:2487: trailing whitespace.
+++    55	
.oracle/checkins/batch-1-r11.md:2489: trailing whitespace.
+++    63	
.oracle/checkins/batch-1-r11.md:2491: trailing whitespace.
+++    65	
.oracle/checkins/batch-1-r11.md:2493: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r11.md:2495: trailing whitespace.
+++    74	
.oracle/checkins/batch-1-r11.md:2497: trailing whitespace.
+++    76	
.oracle/checkins/batch-1-r11.md:2499: trailing whitespace.
+++    78	
.oracle/checkins/batch-1-r11.md:2501: trailing whitespace.
+++    86	
.oracle/checkins/batch-1-r11.md:2503: trailing whitespace.
+++    88	
.oracle/checkins/batch-1-r11.md:2505: trailing whitespace.
+++    94	
.oracle/checkins/batch-1-r11.md:2507: trailing whitespace.
+++    96	
.oracle/checkins/batch-1-r11.md:2509: trailing whitespace.
+++    98	
.oracle/checkins/batch-1-r11.md:2511: trailing whitespace.
+++   100	
.oracle/checkins/batch-1-r11.md:2513: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2515: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2517: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2519: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2521: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2523: trailing whitespace.
+++ 
.oracle/checkins/batch-1-r11.md:2525: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r11.md:2527: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r11.md:2529: trailing whitespace.
+++   168	
.oracle/checkins/batch-1-r11.md:2531: trailing whitespace.
+++   169	
.oracle/checkins/batch-1-r11.md:2533: trailing whitespace.
+++   236	
.oracle/checkins/batch-1-r11.md:2535: trailing whitespace.
+++   237	
.oracle/checkins/batch-1-r11.md:2537: trailing whitespace.
+++   248	
.oracle/checkins/batch-1-r11.md:2539: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r11.md:2541: trailing whitespace.
+++f8af4b20 (POM 2026-08-12 00:38:06 +0200 173) 
.oracle/checkins/batch-1-r11.md:2543: trailing whitespace.
+++f8af4b20 (POM 2026-08-12 00:38:06 +0200 174) 
.oracle/checkins/batch-1-r11.md:2545: trailing whitespace.
+++91f0fe3f (POM 2026-08-12 03:23:56 +0200 248) 
.oracle/checkins/batch-1-r11.md:2547: trailing whitespace.
+++91f0fe3f (POM 2026-08-12 03:23:56 +0200 249) 
.oracle/checkins/batch-1-r11.md:2549: trailing whitespace.
+++     2	
.oracle/checkins/batch-1-r11.md:2551: trailing whitespace.
+++     8	
.oracle/checkins/batch-1-r11.md:2553: trailing whitespace.
+++    11	
.oracle/checkins/batch-1-r11.md:2555: trailing whitespace.
+++    20	
.oracle/checkins/batch-1-r11.md:2557: trailing whitespace.
+++    21	
.oracle/checkins/batch-1-r11.md:2559: trailing whitespace.
+++    48	
.oracle/checkins/batch-1-r11.md:2561: trailing whitespace.
+++    49	
.oracle/checkins/batch-1-r11.md:2563: trailing whitespace.
+++    52	
.oracle/checkins/batch-1-r11.md:2565: trailing whitespace.
+++    53	
.oracle/checkins/batch-1-r11.md:2567: trailing whitespace.
+++    56	
.oracle/checkins/batch-1-r11.md:2569: trailing whitespace.
+++    57	
.oracle/checkins/batch-1-r11.md:2571: trailing whitespace.
+++    60	
.oracle/checkins/batch-1-r11.md:2573: trailing whitespace.
+++    61	
.oracle/checkins/batch-1-r11.md:2575: trailing whitespace.
+++    72	
.oracle/checkins/batch-1-r11.md:2577: trailing whitespace.
+++    73	
.oracle/checkins/batch-1-r11.md:2579: trailing whitespace.
+++    81	
.oracle/checkins/batch-1-r11.md:2581: trailing whitespace.
+++    88	
.oracle/checkins/batch-1-r11.md:2583: trailing whitespace.
+++    89	
.oracle/checkins/batch-1-r11.md:2585: trailing whitespace.
+++    96	
.oracle/checkins/batch-1-r11.md:2587: trailing whitespace.
+++    97	
.oracle/checkins/batch-1-r11.md:2589: trailing whitespace.
+++   105	
.oracle/checkins/batch-1-r11.md:2591: trailing whitespace.
+++   106	
.oracle/checkins/batch-1-r11.md:2593: trailing whitespace.
+++   113	
.oracle/checkins/batch-1-r11.md:2595: trailing whitespace.
+++   114	
.oracle/checkins/batch-1-r11.md:2597: trailing whitespace.
+++   122	
.oracle/checkins/batch-1-r11.md:2599: trailing whitespace.
+++   123	
.oracle/checkins/batch-1-r11.md:2601: trailing whitespace.
+++   131	
.oracle/checkins/batch-1-r11.md:2603: trailing whitespace.
+++   132	
.oracle/checkins/batch-1-r11.md:2605: trailing whitespace.
+++   162	
.oracle/checkins/batch-1-r11.md:2607: trailing whitespace.
+++   163	
.oracle/checkins/batch-1-r11.md:2609: trailing whitespace.
+++   178	
.oracle/checkins/batch-1-r11.md:2611: trailing whitespace.
+++   179	
.oracle/checkins/batch-1-r11.md:2613: trailing whitespace.
+++   206	
.oracle/checkins/batch-1-r11.md:2615: trailing whitespace.
+++   207	
.oracle/checkins/batch-1-r11.md:2617: trailing whitespace.
+++   249	
.oracle/checkins/batch-1-r11.md:2619: trailing whitespace.
+++   250	
.oracle/checkins/batch-1-r11.md:2621: trailing whitespace.
+++   288	
.oracle/checkins/batch-1-r11.md:2623: trailing whitespace.
+++   289	
.oracle/checkins/batch-1-r11.md:2625: trailing whitespace.
+++   312	
.oracle/checkins/batch-1-r11.md:2627: trailing whitespace.
+++   313	
.oracle/checkins/batch-1-r11.md:2629: trailing whitespace.
+++   324	
.oracle/checkins/batch-1-r11.md:2631: trailing whitespace.
+++   325	
.oracle/checkins/batch-1-r11.md:2633: trailing whitespace.
+++   338	
.oracle/checkins/batch-1-r11.md:2635: trailing whitespace.
+++   339	
.oracle/checkins/batch-1-r11.md:2637: trailing whitespace.
+++   356	
.oracle/checkins/batch-1-r11.md:2639: trailing whitespace.
+++   357	
.oracle/checkins/batch-1-r11.md:2641: trailing whitespace.
+++   375	
.oracle/checkins/batch-1-r11.md:2643: trailing whitespace.
+++   376	
.oracle/checkins/batch-1-r11.md:2645: trailing whitespace.
+++    35	
.oracle/checkins/batch-1-r11.md:2647: trailing whitespace.
+++    40	
.oracle/checkins/batch-1-r11.md:2649: trailing whitespace.
+++    52	
.oracle/checkins/batch-1-r11.md:2651: trailing whitespace.
+++    73	
.oracle/checkins/batch-1-r11.md:2653: trailing whitespace.
+++   205	
.oracle/checkins/batch-1-r11.md:2655: trailing whitespace.
+++   206	
.oracle/checkins/batch-1-r11.md:2657: trailing whitespace.
+++   209	
.oracle/checkins/batch-1-r11.md:2659: trailing whitespace.
+++   215	
.oracle/checkins/batch-1-r11.md:2661: trailing whitespace.
+++   216	
.oracle/checkins/batch-1-r11.md:2663: trailing whitespace.
+++   225	
.oracle/checkins/batch-1-r11.md:2665: trailing whitespace.
+++   226	
.oracle/checkins/batch-1-r11.md:2667: trailing whitespace.
+++   231	
.oracle/checkins/batch-1-r11.md:2669: trailing whitespace.
+++   232	
.oracle/checkins/batch-1-r11.md:2671: trailing whitespace.
+++   288	
.oracle/checkins/batch-1-r11.md:2673: trailing whitespace.
+++   289	
.oracle/checkins/batch-1-r11.md:2675: trailing whitespace.
+++   158	
.oracle/checkins/batch-1-r11.md:2677: trailing whitespace.
+++   159	
.oracle/checkins/batch-1-r11.md:2679: trailing whitespace.
+++   165	
.oracle/checkins/batch-1-r11.md:2681: trailing whitespace.
+++   166	
.oracle/checkins/batch-1-r11.md:2683: trailing whitespace.
+++   171	
.oracle/checkins/batch-1-r11.md:2685: trailing whitespace.
+++   172	
.oracle/checkins/batch-1-r11.md:2687: trailing whitespace.
+++   186	
.oracle/checkins/batch-1-r11.md:2689: trailing whitespace.
+++   187	
.oracle/checkins/batch-1-r11.md:2691: trailing whitespace.
+++   194	
.oracle/checkins/batch-1-r11.md:2693: trailing whitespace.
+++   195	
.oracle/checkins/batch-1-r11.md:2695: trailing whitespace.
+++   205	
.oracle/checkins/batch-1-r11.md:2697: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2699: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2701: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2703: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2705: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2707: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2709: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2711: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2713: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2715: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2717: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2719: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2721: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2723: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2725: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2727: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2729: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2731: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2733: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2735: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2737: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2739: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2741: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2743: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2745: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2747: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2749: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2751: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2753: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2755: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2757: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2759: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2761: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2763: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2765: trailing whitespace.
++    92	
.oracle/checkins/batch-1-r11.md:2767: trailing whitespace.
++    93	
.oracle/checkins/batch-1-r11.md:2769: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r11.md:2771: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r11.md:2773: trailing whitespace.
++   181	
.oracle/checkins/batch-1-r11.md:2775: trailing whitespace.
++   182	
.oracle/checkins/batch-1-r11.md:2777: trailing whitespace.
++   285	
.oracle/checkins/batch-1-r11.md:2779: trailing whitespace.
++   294	
.oracle/checkins/batch-1-r11.md:2781: trailing whitespace.
++   295	
.oracle/checkins/batch-1-r11.md:2783: trailing whitespace.
++   302	
.oracle/checkins/batch-1-r11.md:2785: trailing whitespace.
++   303	
.oracle/checkins/batch-1-r11.md:2787: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r11.md:2789: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r11.md:2791: trailing whitespace.
++   330	
.oracle/checkins/batch-1-r11.md:2793: trailing whitespace.
++   331	
.oracle/checkins/batch-1-r11.md:2795: trailing whitespace.
++   582	
.oracle/checkins/batch-1-r11.md:2797: trailing whitespace.
++   583	
.oracle/checkins/batch-1-r11.md:2799: trailing whitespace.
++   587	
.oracle/checkins/batch-1-r11.md:2801: trailing whitespace.
++   592	
.oracle/checkins/batch-1-r11.md:2803: trailing whitespace.
++   604	
.oracle/checkins/batch-1-r11.md:2805: trailing whitespace.
++   609	
.oracle/checkins/batch-1-r11.md:2807: trailing whitespace.
++   621	
.oracle/checkins/batch-1-r11.md:2809: trailing whitespace.
++   633	
.oracle/checkins/batch-1-r11.md:2811: trailing whitespace.
++   634	
.oracle/checkins/batch-1-r11.md:2813: trailing whitespace.
++   655	
.oracle/checkins/batch-1-r11.md:2815: trailing whitespace.
++   656	
.oracle/checkins/batch-1-r11.md:2817: trailing whitespace.
++   660	
.oracle/checkins/batch-1-r11.md:2819: trailing whitespace.
++   667	
.oracle/checkins/batch-1-r11.md:2821: trailing whitespace.
++   690	
.oracle/checkins/batch-1-r11.md:2823: trailing whitespace.
++   702	
.oracle/checkins/batch-1-r11.md:2825: trailing whitespace.
++   717	
.oracle/checkins/batch-1-r11.md:2827: trailing whitespace.
++   738	
.oracle/checkins/batch-1-r11.md:2829: trailing whitespace.
++   739	
.oracle/checkins/batch-1-r11.md:2831: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2833: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2835: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2837: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:2839: trailing whitespace.
++   520	
.oracle/checkins/batch-1-r11.md:2841: trailing whitespace.
++   539	
.oracle/checkins/batch-1-r11.md:2843: trailing whitespace.
++   540	
.oracle/checkins/batch-1-r11.md:2845: trailing whitespace.
++   550	
.oracle/checkins/batch-1-r11.md:2847: trailing whitespace.
++   551	
.oracle/checkins/batch-1-r11.md:2849: trailing whitespace.
++   613	
.oracle/checkins/batch-1-r11.md:2851: trailing whitespace.
++   617	
.oracle/checkins/batch-1-r11.md:2853: trailing whitespace.
++   618	
.oracle/checkins/batch-1-r11.md:2855: trailing whitespace.
++   631	
.oracle/checkins/batch-1-r11.md:2857: trailing whitespace.
++   632	
.oracle/checkins/batch-1-r11.md:2859: trailing whitespace.
++   635	
.oracle/checkins/batch-1-r11.md:2861: trailing whitespace.
++   644	
.oracle/checkins/batch-1-r11.md:2863: trailing whitespace.
++   645	
.oracle/checkins/batch-1-r11.md:2865: trailing whitespace.
++   651	
.oracle/checkins/batch-1-r11.md:2867: trailing whitespace.
++   652	
.oracle/checkins/batch-1-r11.md:2869: trailing whitespace.
++   683	
.oracle/checkins/batch-1-r11.md:2871: trailing whitespace.
++   693	
.oracle/checkins/batch-1-r11.md:2873: trailing whitespace.
++   729	
.oracle/checkins/batch-1-r11.md:2875: trailing whitespace.
++   730	
.oracle/checkins/batch-1-r11.md:2877: trailing whitespace.
++   748	
.oracle/checkins/batch-1-r11.md:2879: trailing whitespace.
++   749	
.oracle/checkins/batch-1-r11.md:2881: trailing whitespace.
++   785	
.oracle/checkins/batch-1-r11.md:2883: trailing whitespace.
++   786	
.oracle/checkins/batch-1-r11.md:2885: trailing whitespace.
++   800	
.oracle/checkins/batch-1-r11.md:2887: trailing whitespace.
++   801	
.oracle/checkins/batch-1-r11.md:2889: trailing whitespace.
++   817	
.oracle/checkins/batch-1-r11.md:2891: trailing whitespace.
++   818	
.oracle/checkins/batch-1-r11.md:2893: trailing whitespace.
++   914	
.oracle/checkins/batch-1-r11.md:2895: trailing whitespace.
++   915	
.oracle/checkins/batch-1-r11.md:2897: trailing whitespace.
++  1014	
.oracle/checkins/batch-1-r11.md:2899: trailing whitespace.
++  1015	
.oracle/checkins/batch-1-r11.md:2901: trailing whitespace.
++  1024	
.oracle/checkins/batch-1-r11.md:2903: trailing whitespace.
++  1025	
.oracle/checkins/batch-1-r11.md:2905: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r11.md:2907: trailing whitespace.
++     4	
.oracle/checkins/batch-1-r11.md:2909: trailing whitespace.
++     6	
.oracle/checkins/batch-1-r11.md:2911: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r11.md:2913: trailing whitespace.
++    17	
.oracle/checkins/batch-1-r11.md:2915: trailing whitespace.
++    19	
.oracle/checkins/batch-1-r11.md:2917: trailing whitespace.
++    25	
.oracle/checkins/batch-1-r11.md:2919: trailing whitespace.
++    27	
.oracle/checkins/batch-1-r11.md:2921: trailing whitespace.
++    29	
.oracle/checkins/batch-1-r11.md:2923: trailing whitespace.
++    31	
.oracle/checkins/batch-1-r11.md:2925: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r11.md:2927: trailing whitespace.
++    42	
.oracle/checkins/batch-1-r11.md:2929: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r11.md:2931: trailing whitespace.
++    51	
.oracle/checkins/batch-1-r11.md:2933: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r11.md:2935: trailing whitespace.
++    55	
.oracle/checkins/batch-1-r11.md:2937: trailing whitespace.
++    63	
.oracle/checkins/batch-1-r11.md:2939: trailing whitespace.
++    65	
.oracle/checkins/batch-1-r11.md:2941: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r11.md:2943: trailing whitespace.
++    74	
.oracle/checkins/batch-1-r11.md:2945: trailing whitespace.
++    76	
.oracle/checkins/batch-1-r11.md:2947: trailing whitespace.
++    78	
.oracle/checkins/batch-1-r11.md:2949: trailing whitespace.
++    86	
.oracle/checkins/batch-1-r11.md:2951: trailing whitespace.
++    88	
.oracle/checkins/batch-1-r11.md:2953: trailing whitespace.
++    94	
.oracle/checkins/batch-1-r11.md:2955: trailing whitespace.
++    96	
.oracle/checkins/batch-1-r11.md:2957: trailing whitespace.
++    98	
.oracle/checkins/batch-1-r11.md:2959: trailing whitespace.
++   100	
.oracle/checkins/batch-1-r11.md:2961: trailing whitespace.
++   109	
.oracle/checkins/batch-1-r11.md:2963: trailing whitespace.
++   111	
.oracle/checkins/batch-1-r11.md:2965: trailing whitespace.
++   119	
.oracle/checkins/batch-1-r11.md:2967: trailing whitespace.
++   121	
.oracle/checkins/batch-1-r11.md:2969: trailing whitespace.
++   123	
.oracle/checkins/batch-1-r11.md:2971: trailing whitespace.
++   125	
.oracle/checkins/batch-1-r11.md:2973: trailing whitespace.
++   133	
.oracle/checkins/batch-1-r11.md:2975: trailing whitespace.
++   135	
.oracle/checkins/batch-1-r11.md:2977: trailing whitespace.
++   142	
.oracle/checkins/batch-1-r11.md:2979: trailing whitespace.
++   144	
.oracle/checkins/batch-1-r11.md:2981: trailing whitespace.
++   146	
.oracle/checkins/batch-1-r11.md:2983: trailing whitespace.
++   148	
.oracle/checkins/batch-1-r11.md:2985: trailing whitespace.
++   159	
.oracle/checkins/batch-1-r11.md:2987: trailing whitespace.
++   161	
.oracle/checkins/batch-1-r11.md:2989: trailing whitespace.
++   168	
.oracle/checkins/batch-1-r11.md:2991: trailing whitespace.
++   170	
.oracle/checkins/batch-1-r11.md:2993: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r11.md:2995: trailing whitespace.
++     4	
.oracle/checkins/batch-1-r11.md:2997: trailing whitespace.
++     6	
.oracle/checkins/batch-1-r11.md:2999: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r11.md:3001: trailing whitespace.
++    17	
.oracle/checkins/batch-1-r11.md:3003: trailing whitespace.
++    19	
.oracle/checkins/batch-1-r11.md:3005: trailing whitespace.
++    25	
.oracle/checkins/batch-1-r11.md:3007: trailing whitespace.
++    27	
.oracle/checkins/batch-1-r11.md:3009: trailing whitespace.
++    29	
.oracle/checkins/batch-1-r11.md:3011: trailing whitespace.
++    31	
.oracle/checkins/batch-1-r11.md:3013: trailing whitespace.
++    40	
.oracle/checkins/batch-1-r11.md:3015: trailing whitespace.
++    42	
.oracle/checkins/batch-1-r11.md:3017: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r11.md:3019: trailing whitespace.
++    51	
.oracle/checkins/batch-1-r11.md:3021: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r11.md:3023: trailing whitespace.
++    55	
.oracle/checkins/batch-1-r11.md:3025: trailing whitespace.
++    63	
.oracle/checkins/batch-1-r11.md:3027: trailing whitespace.
++    65	
.oracle/checkins/batch-1-r11.md:3029: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r11.md:3031: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r11.md:3033: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r11.md:3035: trailing whitespace.
++   173	
.oracle/checkins/batch-1-r11.md:3037: trailing whitespace.
++   174	
.oracle/checkins/batch-1-r11.md:3039: trailing whitespace.
++A=m[\"VideoArtifact\"]; P=m[\"assemble_provenance_v2\"]; plan=m[\"_plan\"](segments=[m[\"_segment\"](0,24),m[\"_segment\"](24,48)]); arts=[A(path=\"outputs/a.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_B\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED),A(path=\"outputs/b.mp4\",profile=m[\"_profile\"](),sha256=m[\"SHA_C\"],duration_frames=24,audio=m[\"AudioOwnership\"].RENDERED)]; base=dict(engine=\"hybrid\",output=\"/workspace/out.mp4\",timeline=\"/workspace/timeline.json\",assets_registry=None,plan=plan,audio_ownership=\"rendered\",normalization=[],attachments={},backend_fragments={},v1_compatibility=m[\"_compatibility\"]()); first=P(**base,artifact_profiles=arts); print(\"emitted\",type(first[\"artifact_profiles\"]).__name__,[type(x).__name__ for x in first[\"artifact_profiles\"]],first[\"artifact_profiles\"]); 
.oracle/checkins/batch-1-r11.md:3041: trailing whitespace.
++   186	
.oracle/checkins/batch-1-r11.md:3043: trailing whitespace.
++   187	
.oracle/checkins/batch-1-r11.md:3045: trailing whitespace.
++   194	
.oracle/checkins/batch-1-r11.md:3047: trailing whitespace.
++   195	
.oracle/checkins/batch-1-r11.md:3049: trailing whitespace.
++   205	
.oracle/checkins/batch-1-r11.md:3051: trailing whitespace.
++   206	
.oracle/checkins/batch-1-r11.md:3053: trailing whitespace.
++   209	
.oracle/checkins/batch-1-r11.md:3055: trailing whitespace.
++   215	
.oracle/checkins/batch-1-r11.md:3057: trailing whitespace.
++   216	
.oracle/checkins/batch-1-r11.md:3059: trailing whitespace.
++   225	
.oracle/checkins/batch-1-r11.md:3061: trailing whitespace.
++   226	
.oracle/checkins/batch-1-r11.md:3063: trailing whitespace.
++   231	
.oracle/checkins/batch-1-r11.md:3065: trailing whitespace.
++   232	
.oracle/checkins/batch-1-r11.md:3067: trailing whitespace.
++   241	
.oracle/checkins/batch-1-r11.md:3069: trailing whitespace.
++   242	
.oracle/checkins/batch-1-r11.md:3071: trailing whitespace.
++   248	
.oracle/checkins/batch-1-r11.md:3073: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r11.md:3075: trailing whitespace.
++   262	
.oracle/checkins/batch-1-r11.md:3077: trailing whitespace.
++   263	
.oracle/checkins/batch-1-r11.md:3079: trailing whitespace.
++   268	
.oracle/checkins/batch-1-r11.md:3081: trailing whitespace.
++   269	
.oracle/checkins/batch-1-r11.md:3083: trailing whitespace.
++   276	
.oracle/checkins/batch-1-r11.md:3085: trailing whitespace.
++   277	
.oracle/checkins/batch-1-r11.md:3087: trailing whitespace.
++   284	
.oracle/checkins/batch-1-r11.md:3089: trailing whitespace.
++   285	
.oracle/checkins/batch-1-r11.md:3091: trailing whitespace.
++     2	
.oracle/checkins/batch-1-r11.md:3093: trailing whitespace.
++     8	
.oracle/checkins/batch-1-r11.md:3095: trailing whitespace.
++    11	
.oracle/checkins/batch-1-r11.md:3097: trailing whitespace.
++    20	
.oracle/checkins/batch-1-r11.md:3099: trailing whitespace.
++    21	
.oracle/checkins/batch-1-r11.md:3101: trailing whitespace.
++    48	
.oracle/checkins/batch-1-r11.md:3103: trailing whitespace.
++    49	
.oracle/checkins/batch-1-r11.md:3105: trailing whitespace.
++    52	
.oracle/checkins/batch-1-r11.md:3107: trailing whitespace.
++    53	
.oracle/checkins/batch-1-r11.md:3109: trailing whitespace.
++    56	
.oracle/checkins/batch-1-r11.md:3111: trailing whitespace.
++    57	
.oracle/checkins/batch-1-r11.md:3113: trailing whitespace.
++    60	
.oracle/checkins/batch-1-r11.md:3115: trailing whitespace.
++    61	
.oracle/checkins/batch-1-r11.md:3117: trailing whitespace.
++    72	
.oracle/checkins/batch-1-r11.md:3119: trailing whitespace.
++    73	
.oracle/checkins/batch-1-r11.md:3121: trailing whitespace.
++    81	
.oracle/checkins/batch-1-r11.md:3123: trailing whitespace.
++    88	
.oracle/checkins/batch-1-r11.md:3125: trailing whitespace.
++    89	
.oracle/checkins/batch-1-r11.md:3127: trailing whitespace.
++    96	
.oracle/checkins/batch-1-r11.md:3129: trailing whitespace.
++    97	
.oracle/checkins/batch-1-r11.md:3131: trailing whitespace.
++   105	
.oracle/checkins/batch-1-r11.md:3133: trailing whitespace.
++   106	
.oracle/checkins/batch-1-r11.md:3135: trailing whitespace.
++   113	
.oracle/checkins/batch-1-r11.md:3137: trailing whitespace.
++   114	
.oracle/checkins/batch-1-r11.md:3139: trailing whitespace.
++   122	
.oracle/checkins/batch-1-r11.md:3141: trailing whitespace.
++   123	
.oracle/checkins/batch-1-r11.md:3143: trailing whitespace.
++   131	
.oracle/checkins/batch-1-r11.md:3145: trailing whitespace.
++   132	
.oracle/checkins/batch-1-r11.md:3147: trailing whitespace.
++   162	
.oracle/checkins/batch-1-r11.md:3149: trailing whitespace.
++   163	
.oracle/checkins/batch-1-r11.md:3151: trailing whitespace.
++   178	
.oracle/checkins/batch-1-r11.md:3153: trailing whitespace.
++   179	
.oracle/checkins/batch-1-r11.md:3155: trailing whitespace.
++   206	
.oracle/checkins/batch-1-r11.md:3157: trailing whitespace.
++   207	
.oracle/checkins/batch-1-r11.md:3159: trailing whitespace.
++   249	
.oracle/checkins/batch-1-r11.md:3161: trailing whitespace.
++   250	
.oracle/checkins/batch-1-r11.md:3163: trailing whitespace.
++   288	
.oracle/checkins/batch-1-r11.md:3165: trailing whitespace.
++   289	
.oracle/checkins/batch-1-r11.md:3167: trailing whitespace.
++   312	
.oracle/checkins/batch-1-r11.md:3169: trailing whitespace.
++   313	
.oracle/checkins/batch-1-r11.md:3171: trailing whitespace.
++   324	
.oracle/checkins/batch-1-r11.md:3173: trailing whitespace.
++   325	
.oracle/checkins/batch-1-r11.md:3175: trailing whitespace.
++   338	
.oracle/checkins/batch-1-r11.md:3177: trailing whitespace.
++   339	
.oracle/checkins/batch-1-r11.md:3179: trailing whitespace.
++   356	
.oracle/checkins/batch-1-r11.md:3181: trailing whitespace.
++   357	
.oracle/checkins/batch-1-r11.md:3183: trailing whitespace.
++   375	
.oracle/checkins/batch-1-r11.md:3185: trailing whitespace.
++   376	
.oracle/checkins/batch-1-r11.md:3187: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:3189: trailing whitespace.
++ 
.oracle/checkins/batch-1-r11.md:3204: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3205: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3214: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3215: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3221: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3222: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3235: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3236: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3241: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3242: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3249: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3250: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3257: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3258: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3267: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3268: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3275: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3276: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3285: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3286: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3307: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3308: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3320: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3321: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3324: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3330: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3331: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3334: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3338: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3339: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3353: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3354: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3358: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3364: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3385: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3389: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3400: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3410: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3437: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3438: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3441: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3448: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3449: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3461: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3462: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3557: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3558: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3632: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3633: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3644: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3645: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3960: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3964: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3966: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3975: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3985: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3987: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3989: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:3998: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4007: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4011: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4013: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4015: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4030: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4038: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4040: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4042: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4047: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4085: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4095: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4097: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4105: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4110: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4120: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4122: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4125: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4135: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4142: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4144: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4154: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4158: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4160: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4224: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4225: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4350: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4351: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4360: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4361: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4379: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4380: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4386: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4387: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4398: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4399: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4415: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4426: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4427: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4436: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4437: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4458: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4459: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4471: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4472: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4475: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4558: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:4559: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:5228: trailing whitespace.
+   190	
.oracle/checkins/batch-1-r11.md:5229: trailing whitespace.
+   191	
.oracle/checkins/batch-1-r11.md:5279: trailing whitespace.
+   215	
.oracle/checkins/batch-1-r11.md:5280: trailing whitespace.
+   216	
.oracle/checkins/batch-1-r11.md:5289: trailing whitespace.
+   225	
.oracle/checkins/batch-1-r11.md:5290: trailing whitespace.
+   226	
.oracle/checkins/batch-1-r11.md:5295: trailing whitespace.
+   231	
.oracle/checkins/batch-1-r11.md:5296: trailing whitespace.
+   232	
.oracle/checkins/batch-1-r11.md:5305: trailing whitespace.
+   241	
.oracle/checkins/batch-1-r11.md:5306: trailing whitespace.
+   242	
.oracle/checkins/batch-1-r11.md:5312: trailing whitespace.
+   248	
.oracle/checkins/batch-1-r11.md:5313: trailing whitespace.
+   249	
.oracle/checkins/batch-1-r11.md:5326: trailing whitespace.
+   262	
.oracle/checkins/batch-1-r11.md:5327: trailing whitespace.
+   263	
.oracle/checkins/batch-1-r11.md:5332: trailing whitespace.
+   268	
.oracle/checkins/batch-1-r11.md:5333: trailing whitespace.
+   269	
.oracle/checkins/batch-1-r11.md:5340: trailing whitespace.
+   276	
.oracle/checkins/batch-1-r11.md:5341: trailing whitespace.
+   277	
.oracle/checkins/batch-1-r11.md:5348: trailing whitespace.
+   284	
.oracle/checkins/batch-1-r11.md:5349: trailing whitespace.
+   285	
.oracle/checkins/batch-1-r11.md:5358: trailing whitespace.
+   294	
.oracle/checkins/batch-1-r11.md:5359: trailing whitespace.
+   295	
.oracle/checkins/batch-1-r11.md:5366: trailing whitespace.
+   302	
.oracle/checkins/batch-1-r11.md:5367: trailing whitespace.
+   303	
.oracle/checkins/batch-1-r11.md:5376: trailing whitespace.
+   312	
.oracle/checkins/batch-1-r11.md:5377: trailing whitespace.
+   313	
.oracle/checkins/batch-1-r11.md:5397: trailing whitespace.
+   333	
.oracle/checkins/batch-1-r11.md:5398: trailing whitespace.
+   334	
.oracle/checkins/batch-1-r11.md:5574: trailing whitespace.
+   375	
.oracle/checkins/batch-1-r11.md:5575: trailing whitespace.
+   376	
.oracle/checkins/batch-1-r11.md:5631: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:5632: trailing whitespace.
+ 
.oracle/checkins/batch-1-r11.md:5712: trailing whitespace.
+  save state to markdown, and compact - write .md docs to make sure you don't lose 
.oracle/checkins/batch-1-r11.md:5713: trailing whitespace.
+  valuable context (2) subagent maxxing — before doing work yourself, ask whether 
.oracle/checkins/batch-1-r11.md:5715: trailing whitespace.
+  validate, or execute it so the verbose work never lands in your context. Use on 
.oracle/checkins/batch-1-r11.md:6072: trailing whitespace.
+ 

exec
/bin/zsh -lc 'git diff --unified=80 6afd558..8e4f640 -- astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py docs/contracts/render-backend-v1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/contracts.py b/astrid/core/rendering/contracts.py
index 7771b5f..97d6f53 100644
--- a/astrid/core/rendering/contracts.py
+++ b/astrid/core/rendering/contracts.py
@@ -1,120 +1,129 @@
 """Language-neutral rendering protocol data transfer objects.
 
 The JSON Schemas in :mod:`astrid.core.rendering.schemas.v1` are the wire
 source of truth.  These frozen dataclasses are the small Python projection of
 that contract; they deliberately contain no discovery, transport, or backend
 execution behavior.
 """
 
 from __future__ import annotations
 
 import math
 import re
 from collections.abc import Mapping, Sequence
 from dataclasses import dataclass, field, fields, is_dataclass
 from enum import Enum
 from pathlib import Path, PurePosixPath
 from typing import Any, ClassVar, Literal, NoReturn, TypeAlias
 
 from astrid.core.foundation.hash import sha256_file
 from astrid.core.io.cas import canonical_json_digest
 
 
 SCHEMA_VERSION = 1
 
 BackendConfig: TypeAlias = dict[str, dict[str, Any]]
 RendererErrorKind: TypeAlias = Literal[
     "protocol",
     "unsupported",
     "binary_missing",
     "timeout",
     "interrupted",
     "invalid_artifact",
     "internal",
 ]
 
 _QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
 _SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
 _OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
 _KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
 
+# ECMAScript \s whitespace set, spelled as explicit characters so it is
+# identical in the DTO and the JSON Schemas (Python str.strip() has no
+# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
+_ECMA_WHITESPACE = (
+    " \t\n\r\f\v\u00a0\u1680"
+    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
+    "\u2028\u2029\u202f\u205f\u3000\ufeff"
+)
+
 RENDER_RESULT_CORE_KEYS = frozenset(
     {
         "schema_version",
         "video",
         "backend_fragments",
         "audio_ownership",
         "normalization",
         "logs",
         "metadata",
     }
 )
 
 PROVENANCE_V2_CORE_KEYS = frozenset(
     {
         "schema_version",
         "engine",
         "output",
         "timeline",
         "assets_registry",
         "request_digest",
         "requested_policy",
         "planner",
         "segments",
         "segments_v2",
         "artifact_profiles",
         "audio_ownership",
         "normalization",
         "finalizer",
         "attachments",
         "backend_fragments",
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
@@ -142,269 +151,266 @@ def _json_safe(value: Any) -> Any:
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
     if is_dataclass(value):
         return {
             dataclass_field.name: _json_safe(getattr(value, dataclass_field.name))
             for dataclass_field in fields(value)
         }
     raise TypeError(f"value of type {type(value).__name__} is not JSON-safe")
 
 
 def _json_safe_mapping(value: Any, *, label: str = "value") -> dict[str, Any]:
     payload = _json_safe(value)
     if not isinstance(payload, dict):
         raise TypeError(f"{label} must be a JSON object")
     return payload
 
 
 def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
     if not isinstance(value, Mapping):
         raise TypeError(f"{label} must be an object")
     return value
 
 
 def _validate_object_keys(
     payload: Mapping[str, Any],
     *,
     required: set[str] | frozenset[str],
     allowed: set[str] | frozenset[str],
     label: str,
 ) -> None:
     missing = sorted(required - payload.keys())
     if missing:
         raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
     unknown = sorted(payload.keys() - allowed)
     if unknown:
         raise ValueError(f"{label} has unknown fields: {', '.join(unknown)}")
 
 
 def _require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
     if type(value) is not int:
         raise TypeError(f"{label} must be an integer")
     if minimum is not None and value < minimum:
         raise ValueError(f"{label} must be >= {minimum}")
     return value
 
 
 def _require_number(value: Any, label: str, *, exclusive_minimum: float | None = None) -> float:
     if isinstance(value, bool) or not isinstance(value, (int, float)):
         raise TypeError(f"{label} must be a number")
     number = float(value)
     if not math.isfinite(number):
         raise ValueError(f"{label} must be finite")
     if exclusive_minimum is not None and number <= exclusive_minimum:
         raise ValueError(f"{label} must be > {exclusive_minimum:g}")
     return number
 
 
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
-    if not allow_empty and not value.strip():
+    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
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
-    # ECMAScript \s whitespace set, used so DTO and schema agree across
-    # languages (Python str.strip() would diverge on \u0085 and \uFEFF).
-    _WS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
-    if any(not part.strip(_WS) for part in raw_parts):
+    if any(not part.strip(_ECMA_WHITESPACE) for part in raw_parts):
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
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index d037a65..6f6ebc3 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -85,162 +85,167 @@ def _legacy_segment_projection(segment: RenderSegment) -> dict[str, Any]:
 
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
             if isinstance(raw_profile, VideoArtifact):
                 # Reconstruct through the DTO so mutation cannot smuggle
                 # invalid paths, profiles, or attachments past validation.
                 profile = VideoArtifact.from_dict(
                     _json_safe_mapping(raw_profile.to_dict(), label="artifact")
                 )
                 path = profile.path
                 record = _artifact_lineage(profile)
             elif isinstance(raw_profile, Mapping):
                 # Already-emitted lineage record: re-validate and re-key by
                 # its (validated) path so emitted provenance round-trips.
+                raw_path = raw_profile.get("path")
+                if not isinstance(raw_path, str) or not raw_path.strip():
+                    raise ValueError(
+                        "emitted lineage record must carry a non-empty string path"
+                    )
                 record = _artifact_lineage_from_mapping(
-                    raw_profile, key=str(raw_profile.get("path", ""))
+                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
                 )
                 path = record["path"]
             else:
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
                     "or emitted lineage records"
                 )
             if path in seen_paths:
                 raise ValueError(
                     f"artifact_profiles sequence contains duplicate path "
                     f"{path!r}"
                 )
             seen_paths.add(path)
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
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 6c40136..0fad036 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -402,172 +402,174 @@ segments may stream-copy. Otherwise the finalizer normalizes dimensions,
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
 sequence form (one VideoArtifact or emitted lineage record per segment, in
 segment order); single-segment plans may use a path-keyed mapping. Emitted
-lineage records round-trip (re-passing them validates identically). Every
-record carries its `path`, `profile`, a validated 64-hex string `sha256`, and
-`attachments` — each attachment `{path, kind, sha256}` with a workspace-relative
-path, kind matching `[a-z][a-z0-9-]*`, and globally unique names across all
-segment artifacts. All plan, artifact, and attachment values are reconstructed
-through their DTO validators at the provenance boundary (mutated frozen
-instances cannot bypass validation); duplicate paths, duplicate attachment
-names, path escapes, invalid kinds, profile-only entries, null/malformed
-hashes, and cardinality mismatches are rejected. All JSON Schema patterns are
-language-neutral (ECMAScript-valid; no Python-only anchors), and workspacePath
-uses an explicit ECMAScript `\s` whitespace class shared with the DTO so
-Python and non-Python validators agree on whitespace-only components. Replay
+lineage records round-trip (re-passing them validates identically) and every
+record MUST carry a non-empty string `path` (missing, `None`, or numeric
+paths are rejected). Every record carries `profile`, a validated 64-hex string
+`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
+workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and globally unique
+names across all segment artifacts. All plan, artifact, and attachment values
+are reconstructed through their DTO validators at the provenance boundary
+(mutated frozen instances cannot bypass validation); duplicate paths,
+duplicate attachment names, path escapes, invalid kinds, profile-only entries,
+null/malformed hashes, and cardinality mismatches are rejected. All JSON
+Schema patterns are language-neutral (ECMAScript-valid; no Python-only
+anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
+by the DTO and schemas — Python and non-Python validators agree on every
+character including `\u0085`, `\uFEFF`, and the `\u2000-\u200a` block. Replay
 can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
 only, never rendered outputs.
 
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
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 14ecc19..b0dea2c 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -1,112 +1,113 @@
 from __future__ import annotations
 
 from collections.abc import Callable
 from copy import deepcopy
 from dataclasses import FrozenInstanceError, replace
 from pathlib import Path
 from typing import Any
 
 import pytest
 
 from astrid.core.rendering import (
     Attachment,
     AudioOwnership,
     FrameWindow,
     RenderPlan,
     RenderProfile,
     RenderRequest,
     RenderResult,
     RendererError,
     SupportReport,
     VideoArtifact,
 )
 from astrid.core.rendering.contracts import (
     FinalizeRequest,
     FinalizerManifest,
     FinalizerResolution,
     PlannerManifest,
     PlannerResolution,
     PROVENANCE_V1_COMPATIBILITY_KEYS,
     RenderSegment,
     RendererManifest,
     RendererResolution,
+    _require_workspace_relative_path,
     parse_wire_result,
 )
 from astrid.core.rendering.errors import RendererProtocolError
 from astrid.core.rendering.provenance import (
     assemble_provenance_v2,
     hash_input_files,
     validate_backend_fragments,
     write_provenance_v2,
 )
 
 
 SHA_A = "a" * 64
 SHA_B = "b" * 64
 SHA_C = "c" * 64
 SHA_D = "d" * 64
 SHA_E = "e" * 64
 
 
 def _profile(*, audio: bool = True, fps: tuple[int, int] = (24, 1)) -> RenderProfile:
     return RenderProfile(
         width=1920,
         height=1080,
         fps_rational=fps,
         time_base=(1, 12288),
         container="mp4",
         video_codec="h264",
         video_profile="high",
         video_level="4.1",
         pixel_format="yuv420p",
         audio_codec="aac" if audio else None,
         audio_sample_rate=48000 if audio else None,
         audio_channel_layout="stereo" if audio else None,
         duration_tolerance=1,
     )
 
 
 def _window(
     start: int = 0,
     end: int = 48,
     *,
     fps: tuple[int, int] = (24, 1),
 ) -> FrameWindow:
     return FrameWindow(
         start_frame=start,
         end_frame=end,
         fps_rational=fps,
         source_range=(10 + start, 10 + end),
         speed=1.0,
     )
 
 
 def _support(backend: str = "acme.example") -> SupportReport:
     return SupportReport(
         schema_version=1,
         supported=True,
         reasons=[],
         features={"media": True, "audio_mode": "rendered"},
         alternatives=[],
         backend=backend,
         backend_version="1.0.0",
     )
 
 
 def _planner() -> PlannerResolution:
     return PlannerResolution(
         id="rendering.legacy_hybrid",
         source_pack={"id": "rendering"},
         manifest_digest=SHA_C,
         trust_eligibility={"eligible": True, "method": "source-tree"},
         alias_chain=["legacy-hybrid", "rendering.legacy_hybrid"],
         override=None,
         support_decision=_support("rendering.legacy_hybrid"),
     )
 
 
 def _renderer(backend: str = "acme.example", *, digest: str = SHA_B) -> RendererResolution:
     return RendererResolution(
         id=backend,
         source_pack={"id": backend.split(".", 1)[0]},
         manifest_digest=digest,
@@ -894,160 +895,171 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
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
+    with pytest.raises(ValueError, match="must carry a non-empty string path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+            artifact_profiles=[
+                {"profile": _profile(audio=False).to_dict(), "sha256": SHA_B, "attachments": {}},
+                {"path": 123, "profile": _profile(audio=False).to_dict(), "sha256": SHA_C, "attachments": {}},
+            ],
+        )
+    with pytest.raises(ValueError, match="whitespace-only path components"):
+        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
     with pytest.raises(ValueError, match="workspace path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
         )
     # Emitted lineage records round-trip: re-passing the emitted sequence
     # (dictionary records) validates and reproduces the same output.
     first = assemble_provenance_v2(
         **base,
         plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
         artifact_profiles=[
             VideoArtifact(
                 path="outputs/a.mp4",
                 profile=_profile(audio=False),
                 sha256=SHA_B,
                 duration_frames=24,
             ),
             VideoArtifact(
                 path="outputs/b.mp4",
                 profile=_profile(audio=False),
                 sha256=SHA_C,
                 duration_frames=24,
             ),
         ],
     )
     second = assemble_provenance_v2(
         **base,
         plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
         artifact_profiles=first["artifact_profiles"],
     )
     assert second["artifact_profiles"] == first["artifact_profiles"]
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

exec
/bin/zsh -lc 'git diff --unified=20 6afd558..8e4f640 -- astrid/core/rendering/contracts.py astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py docs/contracts/render-backend-v1.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/contracts.py b/astrid/core/rendering/contracts.py
index 7771b5f..97d6f53 100644
--- a/astrid/core/rendering/contracts.py
+++ b/astrid/core/rendering/contracts.py
@@ -21,40 +21,49 @@ from astrid.core.io.cas import canonical_json_digest
 
 
 SCHEMA_VERSION = 1
 
 BackendConfig: TypeAlias = dict[str, dict[str, Any]]
 RendererErrorKind: TypeAlias = Literal[
     "protocol",
     "unsupported",
     "binary_missing",
     "timeout",
     "interrupted",
     "invalid_artifact",
     "internal",
 ]
 
 _QUALIFIED_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$")
 _SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
 _OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
 _KIND_RE = re.compile(r"^[a-z][a-z0-9-]*$")
 
+# ECMAScript \s whitespace set, spelled as explicit characters so it is
+# identical in the DTO and the JSON Schemas (Python str.strip() has no
+# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
+_ECMA_WHITESPACE = (
+    " \t\n\r\f\v\u00a0\u1680"
+    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
+    "\u2028\u2029\u202f\u205f\u3000\ufeff"
+)
+
 RENDER_RESULT_CORE_KEYS = frozenset(
     {
         "schema_version",
         "video",
         "backend_fragments",
         "audio_ownership",
         "normalization",
         "logs",
         "metadata",
     }
 )
 
 PROVENANCE_V2_CORE_KEYS = frozenset(
     {
         "schema_version",
         "engine",
         "output",
         "timeline",
         "assets_registry",
         "request_digest",
@@ -202,41 +211,41 @@ def _require_number(value: Any, label: str, *, exclusive_minimum: float | None =
     if exclusive_minimum is not None and number <= exclusive_minimum:
         raise ValueError(f"{label} must be > {exclusive_minimum:g}")
     return number
 
 
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
-    if not allow_empty and not value.strip():
+    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
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
 
 
@@ -307,44 +316,41 @@ def _require_frame_range(value: Any, label: str) -> tuple[int, int]:
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
-    # ECMAScript \s whitespace set, used so DTO and schema agree across
-    # languages (Python str.strip() would diverge on \u0085 and \uFEFF).
-    _WS = " \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
-    if any(not part.strip(_WS) for part in raw_parts):
+    if any(not part.strip(_ECMA_WHITESPACE) for part in raw_parts):
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
 
diff --git a/astrid/core/rendering/provenance.py b/astrid/core/rendering/provenance.py
index d037a65..6f6ebc3 100644
--- a/astrid/core/rendering/provenance.py
+++ b/astrid/core/rendering/provenance.py
@@ -145,42 +145,47 @@ def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
                     f"artifact_profiles must record exactly one hashed lineage entry "
                     f"per segment: expected {len(segments)}, got {len(result)}"
                 )
         return result
     if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
         lineage: list[dict[str, Any]] = []
         seen_paths: set[str] = set()
         seen_attachment_names: set[str] = set()
         for raw_profile in value:
             if isinstance(raw_profile, VideoArtifact):
                 # Reconstruct through the DTO so mutation cannot smuggle
                 # invalid paths, profiles, or attachments past validation.
                 profile = VideoArtifact.from_dict(
                     _json_safe_mapping(raw_profile.to_dict(), label="artifact")
                 )
                 path = profile.path
                 record = _artifact_lineage(profile)
             elif isinstance(raw_profile, Mapping):
                 # Already-emitted lineage record: re-validate and re-key by
                 # its (validated) path so emitted provenance round-trips.
+                raw_path = raw_profile.get("path")
+                if not isinstance(raw_path, str) or not raw_path.strip():
+                    raise ValueError(
+                        "emitted lineage record must carry a non-empty string path"
+                    )
                 record = _artifact_lineage_from_mapping(
-                    raw_profile, key=str(raw_profile.get("path", ""))
+                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
                 )
                 path = record["path"]
             else:
                 raise TypeError(
                     "sequence artifact_profiles entries must be VideoArtifacts "
                     "or emitted lineage records"
                 )
             if path in seen_paths:
                 raise ValueError(
                     f"artifact_profiles sequence contains duplicate path "
                     f"{path!r}"
                 )
             seen_paths.add(path)
             _reject_duplicate_attachment_names(record, seen_attachment_names)
             lineage.append(record)
         if segments:
             if len(lineage) != len(segments):
                 raise ValueError(
                     f"artifact_profiles must record exactly one hashed lineage entry "
                     f"per segment: expected {len(segments)}, got {len(lineage)}"
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 6c40136..0fad036 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -462,52 +462,54 @@ claiming an incomplete artifact; the sidecar is the publication commit marker.
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
-lineage records round-trip (re-passing them validates identically). Every
-record carries its `path`, `profile`, a validated 64-hex string `sha256`, and
-`attachments` — each attachment `{path, kind, sha256}` with a workspace-relative
-path, kind matching `[a-z][a-z0-9-]*`, and globally unique names across all
-segment artifacts. All plan, artifact, and attachment values are reconstructed
-through their DTO validators at the provenance boundary (mutated frozen
-instances cannot bypass validation); duplicate paths, duplicate attachment
-names, path escapes, invalid kinds, profile-only entries, null/malformed
-hashes, and cardinality mismatches are rejected. All JSON Schema patterns are
-language-neutral (ECMAScript-valid; no Python-only anchors), and workspacePath
-uses an explicit ECMAScript `\s` whitespace class shared with the DTO so
-Python and non-Python validators agree on whitespace-only components. Replay
+lineage records round-trip (re-passing them validates identically) and every
+record MUST carry a non-empty string `path` (missing, `None`, or numeric
+paths are rejected). Every record carries `profile`, a validated 64-hex string
+`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
+workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and globally unique
+names across all segment artifacts. All plan, artifact, and attachment values
+are reconstructed through their DTO validators at the provenance boundary
+(mutated frozen instances cannot bypass validation); duplicate paths,
+duplicate attachment names, path escapes, invalid kinds, profile-only entries,
+null/malformed hashes, and cardinality mismatches are rejected. All JSON
+Schema patterns are language-neutral (ECMAScript-valid; no Python-only
+anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
+by the DTO and schemas — Python and non-Python validators agree on every
+character including `\u0085`, `\uFEFF`, and the `\u2000-\u200a` block. Replay
 can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
 only, never rendered outputs.
 
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
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 14ecc19..b0dea2c 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -13,40 +13,41 @@ from astrid.core.rendering import (
     AudioOwnership,
     FrameWindow,
     RenderPlan,
     RenderProfile,
     RenderRequest,
     RenderResult,
     RendererError,
     SupportReport,
     VideoArtifact,
 )
 from astrid.core.rendering.contracts import (
     FinalizeRequest,
     FinalizerManifest,
     FinalizerResolution,
     PlannerManifest,
     PlannerResolution,
     PROVENANCE_V1_COMPATIBILITY_KEYS,
     RenderSegment,
     RendererManifest,
     RendererResolution,
+    _require_workspace_relative_path,
     parse_wire_result,
 )
 from astrid.core.rendering.errors import RendererProtocolError
 from astrid.core.rendering.provenance import (
     assemble_provenance_v2,
     hash_input_files,
     validate_backend_fragments,
     write_provenance_v2,
 )
 
 
 SHA_A = "a" * 64
 SHA_B = "b" * 64
 SHA_C = "c" * 64
 SHA_D = "d" * 64
 SHA_E = "e" * 64
 
 
 def _profile(*, audio: bool = True, fps: tuple[int, int] = (24, 1)) -> RenderProfile:
     return RenderProfile(
@@ -954,40 +955,51 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
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
+    with pytest.raises(ValueError, match="must carry a non-empty string path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+            artifact_profiles=[
+                {"profile": _profile(audio=False).to_dict(), "sha256": SHA_B, "attachments": {}},
+                {"path": 123, "profile": _profile(audio=False).to_dict(), "sha256": SHA_C, "attachments": {}},
+            ],
+        )
+    with pytest.raises(ValueError, match="whitespace-only path components"):
+        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
     with pytest.raises(ValueError, match="workspace path"):
         assemble_provenance_v2(
             **base,
             plan=_plan(),
             artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
         )
     # Emitted lineage records round-trip: re-passing the emitted sequence
     # (dictionary records) validates and reproduces the same output.
     first = assemble_provenance_v2(
         **base,
         plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
         artifact_profiles=[
             VideoArtifact(
                 path="outputs/a.mp4",
                 profile=_profile(audio=False),
                 sha256=SHA_B,
                 duration_frames=24,
             ),
             VideoArtifact(
                 path="outputs/b.mp4",

codex
One cross-language edge remains especially important: the new lineage guard must not quietly reintroduce Python’s broader whitespace semantics before the shared path validator runs. I’m checking that round-trip boundary directly, along with the exact schema regexes.
exec
/bin/zsh -lc 'git diff --unified=8 6afd558..8e4f640 -- astrid/core/rendering/schemas/v1/*.json' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/schemas/v1/finalize.json b/astrid/core/rendering/schemas/v1/finalize.json
index ee90481..f47ae06 100644
--- a/astrid/core/rendering/schemas/v1/finalize.json
+++ b/astrid/core/rendering/schemas/v1/finalize.json
@@ -60,34 +60,34 @@
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
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
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
@@ -189,66 +189,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -269,26 +269,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
@@ -309,29 +309,29 @@
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "alternatives": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "$ref": "#/definitions/qualifiedId"
           }
@@ -340,17 +340,17 @@
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
@@ -373,17 +373,17 @@
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -426,17 +426,17 @@
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -473,17 +473,17 @@
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -507,17 +507,17 @@
       }
     },
     "hashMap": {
       "type": "object",
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "renderSegment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "window",
         "renderer",
@@ -583,17 +583,17 @@
         "reasons": {
           "type": "object",
           "propertyNames": {
             "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
           },
           "additionalProperties": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "window": {
           "anyOf": [
             {
               "$ref": "#/definitions/frameWindow"
             },
             {
@@ -711,17 +711,17 @@
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
@@ -753,21 +753,21 @@
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "overrideRecord": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "from",
         "to"
diff --git a/astrid/core/rendering/schemas/v1/finalizer-manifest.json b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
index 724ba56..49f9462 100644
--- a/astrid/core/rendering/schemas/v1/finalizer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/finalizer-manifest.json
@@ -18,33 +18,33 @@
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
     },
     "command": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,54 +59,54 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "capabilities": {
       "$ref": "#/definitions/finalizerCapabilities",
       "default": {}
     },
     "required_permissions": {
       "$ref": "#/definitions/permissions",
       "default": []
     },
     "required_binaries": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "uniqueItems": true,
       "default": []
     },
     "timeout_seconds": {
       "type": [
         "integer",
         "null"
       ],
       "minimum": 1,
       "default": null
     },
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
@@ -130,17 +130,17 @@
     "finalizerCapabilities": {
       "type": "object",
       "properties": {
         "containers": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "preserves_attachments": {
           "type": "boolean"
         },
         "audio_ownership": {
           "type": "array",
@@ -158,22 +158,22 @@
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
diff --git a/astrid/core/rendering/schemas/v1/plan.json b/astrid/core/rendering/schemas/v1/plan.json
index f741238..16a07c9 100644
--- a/astrid/core/rendering/schemas/v1/plan.json
+++ b/astrid/core/rendering/schemas/v1/plan.json
@@ -50,17 +50,17 @@
     "reasons": {
       "type": "object",
       "propertyNames": {
         "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "window": {
       "anyOf": [
         {
           "$ref": "#/definitions/frameWindow"
         },
         {
@@ -109,17 +109,17 @@
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "requestedPolicy": {
       "oneOf": [
         {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         {
           "type": "object"
         }
       ]
     },
     "audioOwnership": {
       "type": "string",
@@ -221,66 +221,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -301,26 +301,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
     },
     "supportReport": {
       "type": "object",
       "additionalProperties": false,
@@ -341,29 +341,29 @@
         "supported": {
           "type": "boolean"
         },
         "reasons": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "type": [
               "boolean",
               "string"
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "alternatives": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "$ref": "#/definitions/qualifiedId"
           }
@@ -372,17 +372,17 @@
           "$ref": "#/definitions/qualifiedId"
         },
         "backend_version": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         }
       }
     },
     "plannerResolution": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "id",
@@ -405,17 +405,17 @@
         },
         "trust_eligibility": {
           "type": "object"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -458,17 +458,17 @@
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "uniqueItems": true,
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -505,17 +505,17 @@
         },
         "manifest_digest": {
           "$ref": "#/definitions/sha256"
         },
         "alias_chain": {
           "type": "array",
           "items": {
             "type": "string",
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "override": {
           "anyOf": [
             {
               "$ref": "#/definitions/overrideRecord"
             },
             {
@@ -539,17 +539,17 @@
       }
     },
     "hashMap": {
       "type": "object",
       "additionalProperties": {
         "$ref": "#/definitions/sha256"
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "renderSegment": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "window",
         "renderer",
diff --git a/astrid/core/rendering/schemas/v1/planner-manifest.json b/astrid/core/rendering/schemas/v1/planner-manifest.json
index fd436e7..d226fed 100644
--- a/astrid/core/rendering/schemas/v1/planner-manifest.json
+++ b/astrid/core/rendering/schemas/v1/planner-manifest.json
@@ -18,33 +18,33 @@
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
     },
     "command": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,54 +59,54 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "capabilities": {
       "$ref": "#/definitions/plannerCapabilities",
       "default": {}
     },
     "required_permissions": {
       "$ref": "#/definitions/permissions",
       "default": []
     },
     "required_binaries": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "uniqueItems": true,
       "default": []
     },
     "timeout_seconds": {
       "type": [
         "integer",
         "null"
       ],
       "minimum": 1,
       "default": null
     },
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
@@ -130,38 +130,38 @@
     "plannerCapabilities": {
       "type": "object",
       "properties": {
         "policies": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "supports_fallback": {
           "type": "boolean"
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         }
       },
       "additionalProperties": false
     }
   },
   "examples": [
     {
diff --git a/astrid/core/rendering/schemas/v1/renderer-manifest.json b/astrid/core/rendering/schemas/v1/renderer-manifest.json
index b735227..79e1861 100644
--- a/astrid/core/rendering/schemas/v1/renderer-manifest.json
+++ b/astrid/core/rendering/schemas/v1/renderer-manifest.json
@@ -18,33 +18,33 @@
       "const": 1
     },
     "id": {
       "$ref": "#/definitions/qualifiedId"
     },
     "name": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "version": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "protocol_version": {
       "type": "integer",
       "const": 1
     },
     "command": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "minItems": 1
     },
     "operations": {
       "type": "array",
       "items": {
         "type": "string",
         "enum": [
@@ -59,54 +59,54 @@
     },
     "description": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
       "default": null,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "capabilities": {
       "$ref": "#/definitions/rendererCapabilities",
       "default": {}
     },
     "required_permissions": {
       "$ref": "#/definitions/permissions",
       "default": []
     },
     "required_binaries": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "uniqueItems": true,
       "default": []
     },
     "timeout_seconds": {
       "type": [
         "integer",
         "null"
       ],
       "minimum": 1,
       "default": null
     },
     "metadata": {
       "type": "object",
       "propertyNames": {
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "default": {}
     }
   },
   "additionalProperties": false,
   "definitions": {
     "qualifiedId": {
       "type": "string",
@@ -130,58 +130,58 @@
     "rendererCapabilities": {
       "type": "object",
       "properties": {
         "clip_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "track_types": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "features": {
           "type": "object",
           "additionalProperties": {
             "oneOf": [
               {
                 "type": "boolean"
               },
               {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
               }
             ]
           },
           "propertyNames": {
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           }
         },
         "supports_full_timeline": {
           "type": "boolean"
         },
         "supports_windows": {
           "type": "boolean"
         },
         "output_profiles": {
           "type": "array",
           "items": {
             "type": "string",
             "minLength": 1,
-            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
           },
           "uniqueItems": true
         },
         "audio_ownership": {
           "type": "array",
           "items": {
             "type": "string",
             "enum": [
diff --git a/astrid/core/rendering/schemas/v1/request.json b/astrid/core/rendering/schemas/v1/request.json
index ebfcba1..dbdc4c7 100644
--- a/astrid/core/rendering/schemas/v1/request.json
+++ b/astrid/core/rendering/schemas/v1/request.json
@@ -12,25 +12,25 @@
   "properties": {
     "schema_version": {
       "type": "integer",
       "const": 1
     },
     "timeline_path": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "assets_registry_path": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "output_name": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
       "not": {
         "enum": [
           ".",
           ".."
@@ -96,17 +96,17 @@
             "required": [
               "audio_codec",
               "audio_sample_rate",
               "audio_channel_layout"
             ],
             "properties": {
               "audio_codec": {
                 "type": "string",
-                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
               }
             }
           }
         }
       }
     },
     {
       "if": {
@@ -250,66 +250,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -330,26 +330,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
     },
     "backendConfig": {
       "type": "object",
       "propertyNames": {
@@ -357,21 +357,21 @@
       },
       "additionalProperties": {
         "type": "object"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     }
   },
   "examples": [
     {
       "schema_version": 1,
       "timeline_path": "/workspace/timeline.json",
       "assets_registry_path": "/workspace/assets.json",
diff --git a/astrid/core/rendering/schemas/v1/result.json b/astrid/core/rendering/schemas/v1/result.json
index 990f33f..97d6aba 100644
--- a/astrid/core/rendering/schemas/v1/result.json
+++ b/astrid/core/rendering/schemas/v1/result.json
@@ -17,17 +17,17 @@
     },
     "sha256": {
       "type": "string",
       "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
     },
     "workspacePath": {
       "type": "string",
       "minLength": 1,
-      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     },
     "portableName": {
       "type": "string",
       "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
       "not": {
         "enum": [
           ".",
           ".."
@@ -79,66 +79,66 @@
           "$ref": "#/definitions/positiveRational"
         },
         "time_base": {
           "$ref": "#/definitions/positiveRational"
         },
         "container": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_codec": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_profile": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "video_level": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "pixel_format": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_codec": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "audio_sample_rate": {
           "type": [
             "integer",
             "null"
           ],
           "minimum": 1
         },
         "audio_channel_layout": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "duration_tolerance": {
           "type": "integer",
           "minimum": 0
         }
       },
       "oneOf": [
         {
@@ -159,26 +159,26 @@
             "audio_codec",
             "audio_sample_rate",
             "audio_channel_layout"
           ],
           "properties": {
             "audio_codec": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             },
             "audio_sample_rate": {
               "type": "integer",
               "minimum": 1
             },
             "audio_channel_layout": {
               "type": "string",
               "minLength": 1,
-              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
             }
           }
         }
       ]
     },
     "attachment": {
       "type": "object",
       "additionalProperties": false,
@@ -256,17 +256,17 @@
             "properties": {
               "profile": {
                 "required": [
                   "audio_codec"
                 ],
                 "properties": {
                   "audio_codec": {
                     "type": "string",
-                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
                   }
                 }
               }
             }
           },
           "then": {
             "required": [
               "audio"
@@ -348,27 +348,27 @@
         }
       }
     },
     "stringArray": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "stringMap": {
       "type": "object",
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       },
       "additionalProperties": {
         "type": "string",
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "success": {
       "type": "object",
       "additionalProperties": false,
       "required": [
         "schema_version",
         "video",
@@ -481,25 +481,25 @@
           ]
         },
         "backend": {
           "$ref": "#/definitions/qualifiedId"
         },
         "message": {
           "type": "string",
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "recovery_command": {
           "type": [
             "string",
             "null"
           ],
           "minLength": 1,
-          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
         },
         "details": {
           "type": "object"
         }
       }
     }
   },
   "examples": [
diff --git a/astrid/core/rendering/schemas/v1/support.json b/astrid/core/rendering/schemas/v1/support.json
index 3df7cbd..7e58e90 100644
--- a/astrid/core/rendering/schemas/v1/support.json
+++ b/astrid/core/rendering/schemas/v1/support.json
@@ -21,29 +21,29 @@
     "supported": {
       "type": "boolean"
     },
     "reasons": {
       "type": "array",
       "items": {
         "type": "string",
         "minLength": 1,
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "features": {
       "type": "object",
       "additionalProperties": {
         "type": [
           "boolean",
           "string"
         ]
       },
       "propertyNames": {
-        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "alternatives": {
       "type": "array",
       "uniqueItems": true,
       "items": {
         "$ref": "#/definitions/qualifiedId"
       }
@@ -52,17 +52,17 @@
       "$ref": "#/definitions/qualifiedId"
     },
     "backend_version": {
       "type": [
         "string",
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     }
   },
   "definitions": {
     "qualifiedId": {
       "type": "string",
       "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
     }
   },

exec
/bin/zsh -lc "rg -n '"'^def assemble_provenance_v2|''^def _plan|''^def _segment|''^def _compatibility|''^def _profile|raw_path|strip'"\\(' astrid/core/rendering/provenance.py tests/core/rendering/test_contracts.py astrid/core/rendering/contracts.py | sed -n '1,220p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/provenance.py:165:                raw_path = raw_profile.get("path")
astrid/core/rendering/provenance.py:166:                if not isinstance(raw_path, str) or not raw_path.strip():
astrid/core/rendering/provenance.py:171:                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
astrid/core/rendering/provenance.py:307:def assemble_provenance_v2(
tests/core/rendering/test_contracts.py:52:def _profile(*, audio: bool = True, fps: tuple[int, int] = (24, 1)) -> RenderProfile:
tests/core/rendering/test_contracts.py:97:def _planner() -> PlannerResolution:
tests/core/rendering/test_contracts.py:133:def _segment(
tests/core/rendering/test_contracts.py:149:def _plan(
tests/core/rendering/test_contracts.py:522:def _compatibility() -> dict[str, Any]:
astrid/core/rendering/contracts.py:42:# identical in the DTO and the JSON Schemas (Python str.strip() has no
astrid/core/rendering/contracts.py:231:    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
astrid/core/rendering/contracts.py:336:    if any(not part.strip(_ECMA_WHITESPACE) for part in raw_parts):

exec
/bin/zsh -lc "sed -n '120,185p' tests/core/rendering/test_contracts.py && sed -n '500,550p' tests/core/rendering/test_contracts.py && sed -n '300,385p' astrid/core/rendering/provenance.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:

def _finalizer() -> FinalizerResolution:
    return FinalizerResolution(
        id="rendering.ffmpeg-finalizer",
        source_pack={"id": "rendering"},
        manifest_digest=SHA_E,
        alias_chain=["ffmpeg-finalizer", "rendering.ffmpeg-finalizer"],
        override=None,
        trust_eligibility={"eligible": True, "method": "source-tree"},
        support_decision=_support("rendering.ffmpeg-finalizer"),
    )


def _segment(
    start: int = 0,
    end: int = 48,
    *,
    backend: str = "acme.example",
    fps: tuple[int, int] = (24, 1),
    digest: str = SHA_B,
    renderer: RendererResolution | None = None,
) -> RenderSegment:
    return RenderSegment(
        window=_window(start, end, fps=fps),
        renderer=renderer or _renderer(backend, digest=digest),
        input_hashes={"timeline": SHA_A},
    )


def _plan(
    *,
    segments: list[RenderSegment] | None = None,
    total_frames: int = 48,
    profile: RenderProfile | None = None,
    window: FrameWindow | None = None,
    planner: PlannerResolution | None = None,
    finalizer: FinalizerResolution | None = None,
) -> RenderPlan:
    selected = [_segment()] if segments is None else segments
    return RenderPlan(
        schema_version=1,
        request_digest=SHA_D,
        requested_policy="hybrid",
        planner=planner or _planner(),
        segments=selected,
        finalizer=finalizer or _finalizer(),
        profile=profile or _profile(),
        total_frames=total_frames,
        reasons={str(index): "the request is supported" for index in range(len(selected))},
        window=window,
    )


def _video(
    *,
    path: str = "outputs/video.mp4",
    duration_frames: int = 48,
    profile: RenderProfile | None = None,
    audio: AudioOwnership = AudioOwnership.RENDERED,
    attachments: dict[str, Attachment] | None = None,
) -> VideoArtifact:
    return VideoArtifact(
        path=path,
        profile=profile or _profile(),
        sha256=SHA_A,
        duration_frames=duration_frames,
        "../escape.mp4",
        "outputs/../../escape.mp4",
        "outputs/./escape.mp4",
        "outputs//escape.mp4",
        "outputs/",
        "/tmp/escape.mp4",
        "C:escape.mp4",
        r"C:\\temp\\escape.mp4",
        r"\\\\server\\share\\escape.mp4",
    ],
)
def test_artifact_path_traversal_and_windows_drives_rejected(path: str) -> None:
    with pytest.raises(ValueError, match="workspace|contained|relative"):
        _video(path=path)


def test_backend_fragment_cannot_overwrite_current_or_retired_core_keys() -> None:
    for key in ("output", "planner", "resolved_backend", "request_digest"):
        with pytest.raises(ValueError, match=f"core-owned keys: {key}"):
            validate_backend_fragments({"acme.example": {key: "stolen"}})


def _compatibility() -> dict[str, Any]:
    return {
        "project_dir": "/workspace/remotion",
        "composition_id": "TimelineComposition",
        "active_pack_order": [],
        "active_theme": None,
        "registry_hash": SHA_B,
        "registry_state": {},
        "resolved_effect_ids": [],
        "resolved_effects": [],
        "source_pack_ids": [],
        "element_roots": [],
        "staged_asset_ids": [],
        "staged_asset_root": None,
        "segment_provenance": [{"engine": "spoofed", "from": -1, "to": -1}],
        "ffmpeg_specialization": None,
        "audio_reactive_colour": None,
    }


def test_provenance_requires_always_emitted_v1_projection() -> None:
    with pytest.raises(ValueError, match="v1_compatibility is required"):
        assemble_provenance_v2(
            engine="remotion",
            output="/workspace/video.mp4",
            timeline="/workspace/timeline.json",
            assets_registry=None,
            plan=_plan(),
        )
        raise ValueError(
            "v1 compatibility projection is missing always-emitted fields: "
            + ", ".join(missing)
        )
    return compatibility


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

exec
/bin/zsh -lc "rg -n 'workspacePath|ECMA|0085|FEFF|2001|jsonschema|Ajv|ajv' tests/core/rendering astrid/core/rendering | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/contracts.py:41:# ECMAScript \s whitespace set, spelled as explicit characters so it is
astrid/core/rendering/contracts.py:43:# range syntax and differs from ECMAScript on \u0085 and \uFEFF).
astrid/core/rendering/contracts.py:44:_ECMA_WHITESPACE = (
astrid/core/rendering/contracts.py:46:    "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
astrid/core/rendering/contracts.py:231:    if not allow_empty and not value.strip(_ECMA_WHITESPACE):
astrid/core/rendering/contracts.py:336:    if any(not part.strip(_ECMA_WHITESPACE) for part in raw_parts):
astrid/core/rendering/schemas/v1/finalize.json:65:    "workspacePath": {
astrid/core/rendering/schemas/v1/finalize.json:651:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/finalize.json:682:          "$ref": "#/definitions/workspacePath"
tests/core/rendering/test_schema_roundtrip.py:9:import jsonschema
tests/core/rendering/test_schema_roundtrip.py:77:    jsonschema.Draft7Validator.check_schema(schema)
tests/core/rendering/test_schema_roundtrip.py:78:    validator = jsonschema.Draft7Validator(schema)
tests/core/rendering/test_schema_roundtrip.py:93:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:342:    validator = jsonschema.Draft7Validator(_load_schema(schema_name))
tests/core/rendering/test_schema_roundtrip.py:374:    assert not jsonschema.Draft7Validator(_load_schema("result.json")).is_valid(result)
tests/core/rendering/test_contracts.py:651:    assert hashes["timeline"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
tests/core/rendering/test_contracts.py:985:        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
astrid/core/rendering/schemas/v1/result.json:22:    "workspacePath": {
astrid/core/rendering/schemas/v1/result.json:196:          "$ref": "#/definitions/workspacePath"
astrid/core/rendering/schemas/v1/result.json:227:          "$ref": "#/definitions/workspacePath"

exec
/bin/zsh -lc "sed -n '1,140p' tests/core/rendering/test_schema_roundtrip.py && sed -n '300,400p' tests/core/rendering/test_schema_roundtrip.py && rg -n '\\\\S' astrid/core/rendering/schemas/v1/*.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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


def _request_cases() -> list[tuple[str, dict[str, Any]]]:
    base = _load_fixture("request.json")
    profile = _load_fixture("plan.json")["profile"]
    partial_audio = deepcopy(profile)
    partial_audio["audio_codec"] = "aac"
    rendered_visual = _set(_set(base, ("profile",), profile), ("audio",), "rendered")
    none_with_audio = _set(
        _set(base, ("profile",), _load_schema("request.json")["examples"][0]["profile"]),
        ("boolean version", _set(base, ("schema_version",), True)),
        ("unknown version", _set(base, ("schema_version",), 2)),
        ("malformed protocol version", _set(base, ("protocol_version",), "1")),
        ("empty command", _set(base, ("command",), [])),
        ("missing required operation", _set(base, ("operations",), ["support"])),
        (
            "duplicate operation",
            _set(base, ("operations",), [required_operation, required_operation]),
        ),
        ("unknown permission", _set(base, ("required_permissions",), ["root"])),
        ("unknown capability", _set(base, ("capabilities",), {"unknown": True})),
    ]


def _with_version_adversaries(
    base: dict[str, Any],
    cases: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    return cases + [
        ("missing version", _delete(base, ("schema_version",))),
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
astrid/core/rendering/schemas/v1/support.json:29:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/support.json:41:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/support.json:60:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/support.json:66:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:16:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:20:      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:25:      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:29:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/result.json:87:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:92:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:100:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:108:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:113:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:121:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:136:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:167:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:176:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:200:          "pattern": "^[a-z][a-z0-9-]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:264:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:356:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:362:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:366:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:489:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:497:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:20:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:28:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:32:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/request.json:104:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:151:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:258:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:271:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:279:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:284:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:292:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:307:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:338:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:347:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:365:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:369:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:147:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:160:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:165:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:179:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:41:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/finalize.json:59:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:63:      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:68:      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:72:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/finalize.json:85:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:197:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:202:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:210:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:218:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:223:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:231:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:246:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:277:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:286:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:317:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:329:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:348:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:381:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:434:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:481:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:515:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:586:            "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:591:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:655:          "pattern": "^[a-z][a-z0-9-]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:719:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:761:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:765:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:53:        "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:58:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:106:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:110:      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:117:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:229:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:234:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:242:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:250:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:255:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:278:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:309:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:318:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:349:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:361:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:380:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:413:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:466:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:513:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:547:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:154:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:159:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:166:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:171:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; m=runpy.run_path(\"tests/core/rendering/test_contracts.py\"); P=m[\"assemble_provenance_v2\"]; A=m[\"VideoArtifact\"]; O=m[\"AudioOwnership\"]; base=dict(engine=\"hybrid\", output=\"/workspace/out.mp4\", timeline=\"/workspace/timeline.json\", assets_registry=None, plan=m[\"_plan\"](), audio_ownership=\"rendered\", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=m[\"_compatibility\"]()); a=A(path=\"\\u0085\", profile=m[\"_profile\"](), sha256=m[\"SHA_B\"], duration_frames=48, audio=O.RENDERED); first=P(**base, artifact_profiles=[a]); print(\"first_path\", ascii(first[\"artifact_profiles\"][0][\"path\"])); print(\"python_default_strip\", ascii(\"\\u0085\".strip())); print(\"dto_path\", ascii(m[\"_require_workspace_relative_path\"](\"\\u0085\", \"path\")));\\ntry: P(**base, artifact_profiles=first[\"artifact_profiles\"]); print(\"roundtrip\", \"accepted\")\\nexcept Exception as e: print(\"roundtrip\", type(e).__name__, str(e))'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 6ms:
  File "<string>", line 1
    import runpy; m=runpy.run_path("tests/core/rendering/test_contracts.py"); P=m["assemble_provenance_v2"]; A=m["VideoArtifact"]; O=m["AudioOwnership"]; base=dict(engine="hybrid", output="/workspace/out.mp4", timeline="/workspace/timeline.json", assets_registry=None, plan=m["_plan"](), audio_ownership="rendered", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=m["_compatibility"]()); a=A(path="\u0085", profile=m["_profile"](), sha256=m["SHA_B"], duration_frames=48, audio=O.RENDERED); first=P(**base, artifact_profiles=[a]); print("first_path", ascii(first["artifact_profiles"][0]["path"])); print("python_default_strip", ascii("\u0085".strip())); print("dto_path", ascii(m["_require_workspace_relative_path"]("\u0085", "path")));\ntry: P(**base, artifact_profiles=first["artifact_profiles"]); print("roundtrip", "accepted")\nexcept Exception as e: print("roundtrip", type(e).__name__, str(e))
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         ^
SyntaxError: unexpected character after line continuation character

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; m=runpy.run_path(\"tests/core/rendering/test_contracts.py\"); P=m[\"assemble_provenance_v2\"]; A=m[\"VideoArtifact\"]; O=m[\"AudioOwnership\"]; base=dict(engine=\"hybrid\", output=\"/workspace/out.mp4\", timeline=\"/workspace/timeline.json\", assets_registry=None, plan=m[\"_plan\"](), audio_ownership=\"rendered\", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=m[\"_compatibility\"]()); a=A(path=\"\\u0085\", profile=m[\"_profile\"](), sha256=m[\"SHA_B\"], duration_frames=48, audio=O.RENDERED); first=P(**base, artifact_profiles=[a]); print(\"first_path\", ascii(first[\"artifact_profiles\"][0][\"path\"])); print(\"python_default_strip\", ascii(\"\\u0085\".strip())); print(\"dto_path\", ascii(m[\"_require_workspace_relative_path\"](\"\\u0085\", \"path\"))); exec(\"try:\\n    P(**base, artifact_profiles=first[\\\"artifact_profiles\\\"])\\n    print(\\\"roundtrip accepted\\\")\\nexcept Exception as exc:\\n    print(\\\"roundtrip\\\", type(exc).__name__, str(exc))\")'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 193ms:
first_path '\x85'
python_default_strip ''
dto_path '\x85'
roundtrip ValueError emitted lineage record must carry a non-empty string path

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/provenance.py | sed -n '154,178p' && nl -ba tests/core/rendering/test_contracts.py | sed -n '968,992p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   165	                raw_path = raw_profile.get("path")
   166	                if not isinstance(raw_path, str) or not raw_path.strip():
   167	                    raise ValueError(
   168	                        "emitted lineage record must carry a non-empty string path"
   169	                    )
   170	                record = _artifact_lineage_from_mapping(
   171	                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
   172	                )
   173	                path = record["path"]
   174	            else:
   175	                raise TypeError(
   176	                    "sequence artifact_profiles entries must be VideoArtifacts "
   177	                    "or emitted lineage records"
   178	                )
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
   986	    with pytest.raises(ValueError, match="workspace path"):
   987	        assemble_provenance_v2(
   988	            **base,
   989	            plan=_plan(),
   990	            artifact_profiles={"../escape.mp4": {"profile": _profile(), "sha256": SHA_B, "attachments": {}}},
   991	        )
   992	    # Emitted lineage records round-trip: re-passing the emitted sequence

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json, pathlib; files=sorted(pathlib.Path(\"astrid/core/rendering/schemas/v1\").glob(\"*.json\")); walk=lambda x: [(k,v) for k,v in x.items()] if isinstance(x,dict) else list(enumerate(x)) if isinstance(x,list) else []; bad=[]; stack=[]; [(stack.append((f.name,(),json.loads(f.read_text())))) for f in files];
while stack:
 f,p,x=stack.pop()
 if isinstance(x,dict):
  [stack.append((f,p+(k,),v)) for k,v in x.items()]
 elif isinstance(x,list):
  [stack.append((f,p+(i,),v)) for i,v in enumerate(x)]
 elif p and p[-1]==\"pattern\" and isinstance(x,str) and r\"\\S\" in x.replace(r\"[\\s\\S]\",\"\"): bad.append((f,p,x))
print(\"standalone_S\",len(bad)); [print(*z) for z in bad]'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
standalone_S 0

exec
/bin/zsh -lc "sed -n '1,210p' astrid/core/rendering/provenance.py && rg -n 'def _artifact_lineage_from_mapping|def _artifact_lineage|artifact_profiles' astrid/core/rendering/provenance.py astrid/core/rendering/contracts.py astrid/core/rendering/schemas/v1/*.json docs/contracts/render-backend-v1.md | sed -n '1,260p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
CORE_OWNED_KEYS = frozenset(PROVENANCE_V2_CORE_KEYS | PROVENANCE_V1_COMPATIBILITY_KEYS)


def validate_backend_fragments(
    fragments: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Validate namespaces and reject top-level core-key collisions."""

    return _validate_backend_fragments(fragments or {})


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
            if isinstance(raw_profile, VideoArtifact):
                # Reconstruct through the DTO so mutation cannot smuggle
                # invalid paths, profiles, or attachments past validation.
                profile = VideoArtifact.from_dict(
                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
                )
                path = profile.path
                record = _artifact_lineage(profile)
            elif isinstance(raw_profile, Mapping):
                # Already-emitted lineage record: re-validate and re-key by
                # its (validated) path so emitted provenance round-trips.
                raw_path = raw_profile.get("path")
                if not isinstance(raw_path, str) or not raw_path.strip():
                    raise ValueError(
                        "emitted lineage record must carry a non-empty string path"
                    )
                record = _artifact_lineage_from_mapping(
                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
                )
                path = record["path"]
            else:
                raise TypeError(
                    "sequence artifact_profiles entries must be VideoArtifacts "
                    "or emitted lineage records"
                )
            if path in seen_paths:
                raise ValueError(
                    f"artifact_profiles sequence contains duplicate path "
                    f"{path!r}"
                )
            seen_paths.add(path)
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
astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
astrid/core/rendering/provenance.py:107:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:113:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:124:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:135:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:145:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:176:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:181:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:190:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:194:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:197:def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
astrid/core/rendering/provenance.py:272:def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
astrid/core/rendering/provenance.py:314:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:365:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:366:            artifact_profiles,
docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
astrid/core/rendering/contracts.py:74:        "artifact_profiles",

exec
/bin/zsh -lc "sed -n '190,290p' astrid/core/rendering/provenance.py && sed -n '300,340p' astrid/core/rendering/schemas/v1/result.json" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
    fields: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if fields is None:
        raise ValueError(
            "v1_compatibility is required and must preserve all always-emitted v1 fields"
        )
        "type": "object",
        "propertyNames": {
          "not": {
            "enum": [
              "schema_version",
              "video",
              "backend_fragments",
              "audio_ownership",
              "normalization",
              "logs",
              "metadata",
              "engine",
              "output",
              "timeline",
              "assets_registry",
              "request_digest",
              "requested_policy",
              "planner",
              "segments",
              "artifact_profiles",
              "finalizer",
              "attachments",
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
              "resolved_backend",
              "source_pack",
              "alias_chain",
              "override",

exec
/bin/zsh -lc "sed -n '1,80p' /tmp/batch1-r12.diff && tail -80 /tmp/batch1-r12.diff && git show --format= --name-status 8e4f640" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
diff --git a/.oracle/checkins/batch-1-r11.md b/.oracle/checkins/batch-1-r11.md
new file mode 100644
index 0000000..3e2f156
--- /dev/null
+++ b/.oracle/checkins/batch-1-r11.md
@@ -0,0 +1,6336 @@
+Reading additional input from stdin...
+2026-08-12T03:03:45.380438Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T03:03:45.380472Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+2026-08-12T03:03:45.380477Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
+OpenAI Codex v0.147.0
+--------
+workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+model: gpt-5.6-sol
+provider: openai
+approval: never
+sandbox: read-only
+reasoning effort: max
+reasoning summaries: none
+session id: 019ff3ed-072e-73f3-859f-549ea04ccb84
+--------
+user
+# Megado Checkpoint — Batch 1 eleventh re-review
+
+Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
+
+Prior verdicts: batch-1.md (9), -r1..-r10 (3 each; -r4 had 4). Eleventh rework
+committed as `6afd558` (prior head 6acd4be). Incremental diff at
+/tmp/batch1-r11.diff.
+
+## How each of your 2 re-review10 issues was addressed (host-implemented)
+
+1. **Multi-segment lineage cannot round-trip** →
+   - Sequence form now accepts BOTH VideoArtifacts and already-emitted
+     lineage records (dicts); records are re-validated via
+     `_artifact_lineage_from_mapping` and re-keyed by their validated path.
+   - Round-trip test: emitted `artifact_profiles` re-passed reproduces the
+     identical output.
+2. **workspacePath cross-language whitespace** →
+   - DTO and schema now share an EXPLICIT ECMAScript `\s` whitespace class
+     (space, tab, LF, CR, FF, VT, NBSP, and Unicode spaces through \u3000,
+     \ufeff) instead of Python `str.strip()` semantics — so Python and
+     non-Python validators agree on `\u0085` (accepted by both) and
+     `\uFEFF` (rejected by both) components.
+   - Cross-checked 19 DTO-vs-schema cases including \u0085/\uFEFF/\u00a0: 0
+     mismatches.
+
+## Evidence
+
+- Incremental diff: /tmp/batch1-r11.diff (7 files)
+- Host-verified: tests/core/rendering = 149 passed; full consolidated Batch 1
+  acceptance = 639 passed, 2 failed (SAME 2 pre-existing env-dependent
+  failures), 3 skipped.
+
+## Verdict
+
+Binary: `PASS` or a list of issues. Batch 1 has passed 11 review rounds. If
+sound and STABLE, say exactly `PASS` so Batch 2 may begin.
+codex
+I’m using the repository’s context-mining and subagent-launcher guidance for this checkpoint: I’ll keep the main review focused, delegate independent scrutiny of the two fixes, then personally verify the incremental diff and relevant tests. I’ll keep the final response strictly to `PASS` if no concrete issue survives review.
+codex
+I’m also applying Astrid’s core repository skill, since this is a review inside the Astrid project; it governs how I inspect project state without mutating it.
+exec
+/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md astrid/packs/_core/skill/SKILL.md && sed -n '1,260p' /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md && sed -n '1,320p' /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md && sed -n '1,360p' astrid/packs/_core/skill/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
+ succeeded in 0ms:
+      75 /Users/peteromalley/.codex/skills/contextminning-subagentmaxxing/SKILL.md
+     241 /Users/peteromalley/.codex/skills/subagent-launcher/SKILL.md
+     772 astrid/packs/_core/skill/SKILL.md
+    1088 total
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
+        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
       }
     },
     "alternatives": {
@@ -57,7 +57,7 @@
         "null"
       ],
       "minLength": 1,
-      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*\\S[\\s\\S]*(?![\\s\\S])"
+      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
     }
   },
   "definitions": {
diff --git a/docs/contracts/render-backend-v1.md b/docs/contracts/render-backend-v1.md
index 6c40136..0fad036 100644
--- a/docs/contracts/render-backend-v1.md
+++ b/docs/contracts/render-backend-v1.md
@@ -479,18 +479,20 @@ are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
 hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
 sequence form (one VideoArtifact or emitted lineage record per segment, in
 segment order); single-segment plans may use a path-keyed mapping. Emitted
-lineage records round-trip (re-passing them validates identically). Every
-record carries its `path`, `profile`, a validated 64-hex string `sha256`, and
-`attachments` — each attachment `{path, kind, sha256}` with a workspace-relative
-path, kind matching `[a-z][a-z0-9-]*`, and globally unique names across all
-segment artifacts. All plan, artifact, and attachment values are reconstructed
-through their DTO validators at the provenance boundary (mutated frozen
-instances cannot bypass validation); duplicate paths, duplicate attachment
-names, path escapes, invalid kinds, profile-only entries, null/malformed
-hashes, and cardinality mismatches are rejected. All JSON Schema patterns are
-language-neutral (ECMAScript-valid; no Python-only anchors), and workspacePath
-uses an explicit ECMAScript `\s` whitespace class shared with the DTO so
-Python and non-Python validators agree on whitespace-only components. Replay
+lineage records round-trip (re-passing them validates identically) and every
+record MUST carry a non-empty string `path` (missing, `None`, or numeric
+paths are rejected). Every record carries `profile`, a validated 64-hex string
+`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
+workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and globally unique
+names across all segment artifacts. All plan, artifact, and attachment values
+are reconstructed through their DTO validators at the provenance boundary
+(mutated frozen instances cannot bypass validation); duplicate paths,
+duplicate attachment names, path escapes, invalid kinds, profile-only entries,
+null/malformed hashes, and cardinality mismatches are rejected. All JSON
+Schema patterns are language-neutral (ECMAScript-valid; no Python-only
+anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
+by the DTO and schemas — Python and non-Python validators agree on every
+character including `\u0085`, `\uFEFF`, and the `\u2000-\u200a` block. Replay
 can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
 only, never rendered outputs.
 
diff --git a/tests/core/rendering/test_contracts.py b/tests/core/rendering/test_contracts.py
index 14ecc19..b0dea2c 100644
--- a/tests/core/rendering/test_contracts.py
+++ b/tests/core/rendering/test_contracts.py
@@ -30,6 +30,7 @@ from astrid.core.rendering.contracts import (
     RenderSegment,
     RendererManifest,
     RendererResolution,
+    _require_workspace_relative_path,
     parse_wire_result,
 )
 from astrid.core.rendering.errors import RendererProtocolError
@@ -971,6 +972,17 @@ def test_provenance_rejects_spoofed_artifact_lineage() -> None:
                 ),
             ],
         )
+    with pytest.raises(ValueError, match="must carry a non-empty string path"):
+        assemble_provenance_v2(
+            **base,
+            plan=_plan(segments=[_segment(0, 24), _segment(24, 48)]),
+            artifact_profiles=[
+                {"profile": _profile(audio=False).to_dict(), "sha256": SHA_B, "attachments": {}},
+                {"path": 123, "profile": _profile(audio=False).to_dict(), "sha256": SHA_C, "attachments": {}},
+            ],
+        )
+    with pytest.raises(ValueError, match="whitespace-only path components"):
+        _require_workspace_relative_path("dir/\u2001/v.mp4", "path")
     with pytest.raises(ValueError, match="workspace path"):
         assemble_provenance_v2(
             **base,
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-1-r11.md
M	astrid/core/rendering/contracts.py
M	astrid/core/rendering/provenance.py
M	astrid/core/rendering/schemas/v1/finalize.json
M	astrid/core/rendering/schemas/v1/finalizer-manifest.json
M	astrid/core/rendering/schemas/v1/plan.json
M	astrid/core/rendering/schemas/v1/planner-manifest.json
M	astrid/core/rendering/schemas/v1/renderer-manifest.json
M	astrid/core/rendering/schemas/v1/request.json
M	astrid/core/rendering/schemas/v1/result.json
M	astrid/core/rendering/schemas/v1/support.json
M	docs/contracts/render-backend-v1.md
M	tests/core/rendering/test_contracts.py

exec
/bin/zsh -lc 'tail -220 .oracle/checkins/batch-1-r11.md' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
Because this is explicitly a Megado checkpoint, I’m also applying the Megado oracle gate: the verdict remains binary, and any reproducible contract violation blocks the next batch. A direct round-trip probe has now reproduced one such edge; I’m finishing the independent cross-check before issuing the verdict.
exec
/bin/zsh -lc "wc -l /Users/peteromalley/.codex/skills/megado/SKILL.md && sed -n '1,240p' /Users/peteromalley/.codex/skills/megado/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc "readlink /Users/peteromalley/.codex/skills/astrid || true; cmp -s /Users/peteromalley/.codex/skills/astrid/SKILL.md astrid/packs/_core/skill/SKILL.md; printf '%s\\n' "'$?' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/packs/_core/skill
0

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import runpy; m=runpy.run_path(\"tests/core/rendering/test_contracts.py\"); P=m[\"assemble_provenance_v2\"]; base=dict(engine=\"hybrid\", output=\"/workspace/out.mp4\", timeline=\"/workspace/timeline.json\", assets_registry=None, plan=m[\"_plan\"](), audio_ownership=\"rendered\", normalization=[], attachments={}, backend_fragments={}, v1_compatibility=m[\"_compatibility\"]()); profile=m[\"_profile\"]().to_dict();
for value in (123,None):
 data={value:{\"path\":value,\"profile\":profile,\"sha256\":m[\"SHA_B\"],\"attachments\":{}}}
 try: print(repr(value), P(**base,artifact_profiles=data)[\"artifact_profiles\"])
 except Exception as e: print(repr(value),type(e).__name__,str(e))' " in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 152ms:
123 {'123': {'path': '123', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}}
None {'None': {'path': 'None', 'profile': {'width': 1920, 'height': 1080, 'fps_rational': [24, 1], 'time_base': [1, 12288], 'container': 'mp4', 'video_codec': 'h264', 'video_profile': 'high', 'video_level': '4.1', 'pixel_format': 'yuv420p', 'audio_codec': 'aac', 'audio_sample_rate': 48000, 'audio_channel_layout': 'stereo', 'duration_tolerance': 1}, 'sha256': 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 'attachments': {}}}

exec
/bin/zsh -lc "rg -n '\\.strip\\(\\)|\\.isspace\\(|\\\\S' astrid/core/rendering tests/core/rendering --glob '*.py' --glob '*.json' | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/core/rendering/provenance.py:166:                if not isinstance(raw_path, str) or not raw_path.strip():
astrid/core/rendering/contracts.py:42:# identical in the DTO and the JSON Schemas (Python str.strip() has no
astrid/core/rendering/schemas/v1/support.json:29:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/support.json:41:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/support.json:60:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/support.json:66:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:53:        "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:58:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:106:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:110:      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:117:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:229:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:234:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:242:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:250:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:255:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:278:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:309:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:318:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:349:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:361:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:380:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:413:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:466:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:513:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/plan.json:547:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:41:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/finalize.json:59:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:63:      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:68:      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:72:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/finalize.json:85:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:197:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:202:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:210:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:218:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:223:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:231:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:246:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:277:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:286:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:317:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:329:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:348:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:381:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:434:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:481:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:515:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:586:            "pattern": "^(0|[1-9][0-9]*)(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:591:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:655:          "pattern": "^[a-z][a-z0-9-]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:719:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:761:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalize.json:765:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:166:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/finalizer-manifest.json:171:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:147:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:160:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:165:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/renderer-manifest.json:179:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:20:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:28:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:32:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/request.json:104:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:151:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:258:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:263:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:271:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:279:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:284:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:292:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:307:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:338:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:347:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:365:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/request.json:369:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:26:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:31:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:42:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:67:      "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:82:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:99:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:104:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:113:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:138:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:154:                "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/planner-manifest.json:159:            "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/registry.py:818:    if not isinstance(record.trust_method, str) or not record.trust_method.strip():
astrid/core/rendering/registry.py:822:    if not isinstance(record.trust_actor, str) or not record.trust_actor.strip():
astrid/core/rendering/registry.py:843:    if not isinstance(value, str) or not value.strip():
astrid/core/rendering/schemas/v1/result.json:16:      "pattern": "^[a-z0-9][a-z0-9_-]*(?:\\.[a-z0-9][a-z0-9_-]*)+(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:20:      "pattern": "^[0-9a-f]{64}(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:25:      "pattern": "^(?![A-Za-z]:)(?!/)(?![\\s\\S]*//)(?![ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*/)(?![\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[\\.]{1,2}(?:/|(?![\\s\\S])))(?![\\s\\S]*/[ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]*(?:/|(?![\\s\\S])))(?![\\s\\S]*\\\\)(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:29:      "pattern": "^[A-Za-z0-9][A-Za-z0-9._-]*(?![\\s\\S])",
astrid/core/rendering/schemas/v1/result.json:87:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:92:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:100:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:108:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:113:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:121:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:136:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:167:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:176:              "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:200:          "pattern": "^[a-z][a-z0-9-]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:264:                    "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:356:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:362:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:366:        "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:489:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"
astrid/core/rendering/schemas/v1/result.json:497:          "pattern": "^(?![\\s\\S]*\\u0000)[\\s\\S]*[^ \\t\\n\\r\\f\\v\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff][\\s\\S]*(?![\\s\\S])"

2026-08-12T03:19:29.207344Z ERROR codex_core::tools::router: error=timeout_ms must be at least 10000
collab: Wait
exec
/bin/zsh -lc "rg -n 'Batch 1|workspacePath|artifact_profiles|lineage|whitespace' .oracle/tasklist.md .oracle/plan.md docs/contracts/render-backend-v1.md | sed -n '1,320p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
docs/contracts/render-backend-v1.md:344:`RenderRequest` payload (sorted keys, no whitespace) that produced this plan.
docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
docs/contracts/render-backend-v1.md:479:hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
docs/contracts/render-backend-v1.md:480:sequence form (one VideoArtifact or emitted lineage record per segment, in
docs/contracts/render-backend-v1.md:482:lineage records round-trip (re-passing them validates identically) and every
docs/contracts/render-backend-v1.md:493:anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
.oracle/plan.md:160:  - Preserve `TimelineComposition`, merged-theme behavior, registry hashes/state, source-pack/effect lineage, resolved effects, and sanitized environment.
.oracle/tasklist.md:3:## Batch 1 — Baseline, contracts, and discovery
.oracle/tasklist.md:57:- Remotion preserves `TimelineComposition`, merged themes, props, registry state/hashes, source-pack and effect lineage, effect staging, sanitized environment, cleanup, and output validation.
.oracle/tasklist.md:178:- Batch 1 must freeze all 18 decisions from the canonical epic brief; `.oracle/plan.md` restates only decisions 4–12.

exec
/bin/zsh -lc "sed -n '1,82p' .oracle/tasklist.md && sed -n '450,505p' docs/contracts/render-backend-v1.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -c 'import json,pathlib,re; files=sorted(pathlib.Path(\"astrid/core/rendering/schemas/v1\").glob(\"*.json\")); vals=[];
for f in files:
 o=json.loads(f.read_text()); st=[((),o)]
 while st:
  p,x=st.pop()
  if isinstance(x,dict): st.extend((p+(k,),v) for k,v in x.items())
  elif isinstance(x,list): st.extend((p+(i,),v) for i,v in enumerate(x))
  elif p and p[-1]==\"pattern\" and isinstance(x,str): vals.append((f.name,p,x))
old=[z for z in vals if r\"\\S\" in z[2].replace(r\"[\\s\\S]\",\"\")]; print(\"schemas\",len(files),\"patterns\",len(vals),\"standalone\",len(old)); print(\"new complement\",sum(\"["'^ '"\\\\t\\\\n\\\\r\\\\f\\\\v\\\\u00a0\" in z[2] for z in vals))' && PYTHONDONTWRITEBYTECODE=1 pytest -q tests/core/rendering/test_contracts.py tests/core/rendering/test_schema_roundtrip.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 exited 1 in 553ms:
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
