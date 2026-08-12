Reading additional input from stdin...
2026-08-12T15:37:08.604567Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:37:08.604628Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:37:08.604642Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ff69e-c39c-7443-83c0-641ec6bc09b7
--------
user
# Megado Checkpoint — Batch 4 third re-review

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle`. Read-only.
Prior verdict batch-4-r2.md listed 1 issue (HIGH). Host-fixed. Rework
committed as `9d1dfd92` (prior head 907423f2). Incremental diff:
`git diff 907423f2..9d1dfd92`.

## How the issue was addressed

**HIGH — executable-finalizer provenance inconsistent**: the direct path
overwrote the renderer result and recorded only the finalizer artifact,
losing renderer lineage/fragments/v1 data; the single-segment planner path
recorded only renderer fragments, omitting the executed finalizer fragment.

- The direct branch now keeps `renderer_result` separate, runs
  `complete_audio` (deferred) on it, and when a finalizer is pinned routes
  through `_finish_plan` with `segment_results=[renderer_result]`.
  `artifact_lineage` stays one-per-segment (the renderer artifact), while
  `fragment_results`/`compatibility_results` include BOTH the renderer and
  the finalizer results.
- The planner branch now appends the executed finalizer result to
  `fragment_results` for single-segment plans that pin a real finalizer
  (previously only multi-segment plans did).
- `_merge_backend_fragments` therefore records renderer + finalizer
  fragments; `artifact_profiles` keeps exactly one hashed lineage entry per
  segment; the published output hash still covers the final artifact.
- Regression tests added:
  - `test_single_segment_plan_records_finalizer_fragment` — hybrid
    single-segment plan records BOTH `fixture.window` and
    `rendering.ffmpeg-finalizer` fragments; one artifact_profile entry.
  - `test_direct_render_with_pinned_finalizer_records_both_fragments` —
    `RenderService(finalizer_id=...)` direct render records the renderer
    fragment, the finalizer fragment, and the pinned finalizer identity.

## Evidence

- `pytest -q tests/core/rendering/` → 373 passed.
- `pytest -q tests/packs/rendering/test_render_facade.py
  tests/packs/rendering/test_legacy_renderer_characterization.py
  tests/packs/rendering/test_render_remotion_registry.py tests/packs/hype
  tests/packs/iteration tests/packs/editorial` → 234 passed, 1 failed
  (pre-existing model-trends env fixture).

## Verdict

Binary `PASS` or issues. On PASS, Batch 5 (caller migration + semantic
parity + M1 freeze) begins. Say exactly `PASS` if clean.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’m using the Astrid core skill because this repository explicitly routes review work through it. I’ll inspect the incremental diff and independently verify the provenance invariants; I’ll keep the worktree read-only.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
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

exec
/bin/zsh -lc "sed -n '241,520p' /Users/peteromalley/.codex/skills/astrid/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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

codex
The skill’s repository guidance makes this a provenance-focused rendering review, not an Astrid task-run action. I’m splitting off an independent adversarial diff review while I trace the direct and planner branches against the manifest contracts.
2026-08-12T15:37:33.515780Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:37:33.515869Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-12T15:37:33.516083Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
exec
/bin/zsh -lc "git status --short && git diff --stat 907423f2..9d1dfd92 && git diff --name-only 907423f2..9d1dfd92 && find astrid/packs/rendering -path '*/skill/SKILL.md' -o -path '*/AGENTS.md' | head -50" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 114ms:
?? .oracle/checkins/batch-4-r3.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
 .oracle/checkins/batch-4-r2.md       | 5394 ++++++++++++++++++++++++++++++++++
 astrid/core/rendering/service.py     |   21 +-
 tests/core/rendering/test_service.py |   66 +
 3 files changed, 5475 insertions(+), 6 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
.oracle/checkins/batch-4-r2.md
astrid/core/rendering/service.py
tests/core/rendering/test_service.py
astrid/packs/rendering/skill/SKILL.md

codex
A rendering-pack skill exists, so I’m applying its pack-specific contract before judging the implementation. The only pre-existing worktree change is an untracked checkpoint file; I will not touch it.
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
/bin/zsh -lc 'git diff --unified=100 907423f2..9d1dfd92 -- astrid/core/rendering/service.py tests/core/rendering/test_service.py' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/astrid/core/rendering/service.py b/astrid/core/rendering/service.py
index 4386e980..a8364722 100644
--- a/astrid/core/rendering/service.py
+++ b/astrid/core/rendering/service.py
@@ -341,267 +341,276 @@ class RenderService:
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
+            finalizer_ran = plan.finalizer.id != _DIRECT_FINALIZER_ID
             artifact_lineage = [item.video for item in segment_results]
             compatibility_results = segment_results
             fragment_results = (
-                segment_results
+                ([*segment_results, final_result] if finalizer_ran else segment_results)
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
+            renderer_result = final_result
             final_result = self.complete_audio(
                 final_result,
                 request=request,
                 plan=plan,
                 workspace=workspace,
                 backend=selected.candidate.id,
                 # The direct plan may pin an executable finalizer; defer
                 # completion to it so a normalizable profile/audio mismatch
                 # is normalized before publication.
                 defer_to_finalizer=(
                     plan.finalizer.id != _DIRECT_FINALIZER_ID
                 ),
             )
-            if plan.finalizer.id != _DIRECT_FINALIZER_ID:
+            finalizer_ran = plan.finalizer.id != _DIRECT_FINALIZER_ID
+            if finalizer_ran:
                 # An embedding host pinned a registered finalizer for direct
                 # renders; honor it exactly like planner-produced plans.
                 finalizer, finalizer_evidence = self._resolve_candidate(
                     self.finalizers,
                     plan.finalizer.id,
                     kind="finalizer",
                     observe=False,
                 )
                 final_result, plan = self._finish_plan(
                     request,
                     plan=plan,
-                    segment_results=[final_result],
+                    segment_results=[renderer_result],
                     pinned_finalizer=(finalizer, finalizer_evidence),
                     workspace=workspace,
                 )
             elif final_result.video.profile != plan.profile or (
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
-            artifact_lineage = [final_result.video]
-            compatibility_results = [final_result]
-            fragment_results = [final_result]
+            artifact_lineage = [renderer_result.video]
+            compatibility_results = (
+                [renderer_result] if finalizer_ran else [final_result]
+            )
+            fragment_results = (
+                [renderer_result, final_result]
+                if finalizer_ran
+                else [final_result]
+            )
 
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
             return _ResolvedCapability(
                 candidate,
                 evidence,
                 report,
                 rejected=list(rejected),
             )
 
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
diff --git a/tests/core/rendering/test_service.py b/tests/core/rendering/test_service.py
index 67c15345..ff230893 100644
--- a/tests/core/rendering/test_service.py
+++ b/tests/core/rendering/test_service.py
@@ -303,217 +303,219 @@ class FakeTransport:
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
     timeline.write_text('{"tracks": [], "clips": []}', encoding="utf-8")
     assets.write_text('{"assets": {}}', encoding="utf-8")
     return RenderRequest(
         schema_version=SCHEMA_VERSION,
         timeline_path=str(timeline),
         assets_registry_path=str(assets),
         output_name="video.mp4",
         audio=audio,
     )
 
 
 def _service(
     tmp_path: Path,
     transport: FakeTransport,
     *,
     renderer_ids: tuple[str, ...] = (
         "rendering.remotion",
         "rendering.ffmpeg",
     ),
     planner_ids: tuple[str, ...] = (),
     stage_observer: Any = None,
     audio_completer: Any = None,
     renderer_registry: RendererRegistry | None = None,
     validator: Any = None,
     publisher: Any = None,
+    finalizer_id: str | None = None,
 ) -> RenderService:
     renderers = renderer_registry or RendererRegistry(
         [_candidate(tmp_path, item, "renderer") for item in renderer_ids]
     )
     planners = PlannerRegistry(
         [_candidate(tmp_path, item, "planner") for item in planner_ids]
     )
     finalizers = FinalizerRegistry(
         [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
     )
     return RenderService(
         registries=(renderers, planners, finalizers),
         transport=transport,
         validator=validator or (lambda result, **_kwargs: result),
         publisher=publisher or publish_render_result,
         stage_observer=stage_observer,
         audio_completer=audio_completer,
+        finalizer_id=finalizer_id,
     )
 
 
 def test_full_qualified_remotion_render_observes_frozen_service_order(
     tmp_path: Path,
 ) -> None:
     transport = FakeTransport()
     calls: list[str] = []
 
     def validate(result: RenderResult, **_kwargs: Any) -> RenderResult:
         calls.append("validator")
         return result
 
     def publish(*args: Any, **kwargs: Any) -> Path:
         calls.append("publisher")
         return publish_render_result(*args, **kwargs)
 
     service = _service(
         tmp_path,
         transport,
         stage_observer=lambda stage, _details: calls.append(stage),
         validator=validate,
         publisher=publish,
     )
     output = tmp_path / "published" / "video.mp4"
 
     result = service.render_request(
         _request(tmp_path),
         selector="rendering.remotion",
         out_path=output,
     )
 
     assert result == output
     assert transport.calls == [
         ("support", "rendering.remotion"),
         ("render", "rendering.remotion"),
     ]
     assert calls == [
         "legacy_translation",
         "alias",
         "override",
         "winner",
         "eligibility",
         "support",
         "invoke",
         "validate",
         "validator",
         "audio",
         "publish",
         "publisher",
     ]
     assert output.is_file()
     assert Path(f"{output}.provenance.json").is_file()
 
 
 def test_qualified_ffmpeg_is_strict(tmp_path: Path) -> None:
     transport = FakeTransport()
     service = _service(tmp_path, transport)
 
     service.render_request(
         _request(tmp_path),
         selector="rendering.ffmpeg",
         out_path=tmp_path / "strict.mp4",
     )
 
     assert transport.calls == [
         ("support", "rendering.ffmpeg"),
         ("render", "rendering.ffmpeg"),
     ]
 
 
 def test_direct_renderer_does_not_require_an_executable_finalizer(
     tmp_path: Path,
 ) -> None:
     transport = FakeTransport()
     renderers = RendererRegistry(
         [_candidate(tmp_path, "fixture.direct", "renderer")]
     )
     service = RenderService(
         registries=(renderers, PlannerRegistry(), FinalizerRegistry()),
         transport=transport,
         validator=lambda result, **_kwargs: result,
     )
 
     output = service.render_request(
         _request(tmp_path),
         selector="fixture.direct",
         out_path=tmp_path / "direct.mp4",
     )
 
     assert output.is_file()
     assert transport.calls == [
         ("support", "fixture.direct"),
         ("render", "fixture.direct"),
     ]
 
 
 def test_legacy_remotion_auto_routes_supported_media_to_ffmpeg_with_warning(
     tmp_path: Path,
 ) -> None:
@@ -2082,100 +2084,164 @@ def _real_audio_reactive_inputs(tmp_path: Path) -> tuple[Path, Path]:
             "error",
             "-y",
             "-f",
             "lavfi",
             "-i",
             "sine=frequency=440:sample_rate=48000:duration=0.5",
             str(audio_path),
         ],
         check=True,
         capture_output=True,
         text=True,
     )
     timeline_path = root / "timeline.json"
     assets_path = root / "assets.json"
     timeline_path.write_text(
         json.dumps(
             {
                 "theme": "banodoco-default",
                 "theme_overrides": {
                     "visual": {"canvas": {"width": 640, "height": 360, "fps": 48}}
                 },
                 "tracks": [
                     {"id": "colour", "kind": "visual", "label": "Colour"},
                     {"id": "audio", "kind": "audio", "label": "Audio"},
                 ],
                 "clips": [
                     {
                         "id": "colour_map",
                         "at": 0,
                         "track": "colour",
                         "clipType": "audio-reactive-colour",
                         "hold": 0.5,
                         "params": {
                             "schemaVersion": 1,
                             "initialColor": "#102030",
                             "events": [
                                 {"id": "a", "frame": 3, "color": "#D47795"},
                                 {"id": "b", "frame": 8, "color": "#26A7D0"},
                                 {"id": "c", "frame": 17, "color": "#B59432"},
                             ],
                         },
                     },
                     {
                         "id": "source_audio",
                         "at": 0,
                         "track": "audio",
                         "clipType": "media",
                         "asset": "audio",
                         "from": 0,
                         "to": 0.5,
                     },
                 ],
             }
         ),
         encoding="utf-8",
     )
     assets_path.write_text(
         json.dumps(
             {
                 "assets": {
                     "audio": {
                         "file": str(audio_path),
                         "type": "audio/wav",
                         "duration": 0.5,
                     }
                 }
             }
         ),
         encoding="utf-8",
     )
     return timeline_path, assets_path
 
 
 def test_real_ffmpeg_audio_reactive_through_generic_service(
     tmp_path: Path,
 ) -> None:
     """The service drives the real FFmpeg backend through its audio-reactive
     colour specialization end to end (no fake transport)."""
     _require_ffmpeg()
     timeline_path, assets_path = _real_audio_reactive_inputs(tmp_path)
     service = _real_service(tmp_path)
     output = tmp_path / "real-reactive.mp4"
 
     service.render_request(
         replace(
             _request(tmp_path),
             timeline_path=str(timeline_path),
             assets_registry_path=str(assets_path),
         ),
         selector="rendering.ffmpeg",
         out_path=output,
     )
 
     assert output.is_file()
     assert output.stat().st_size > 0
     sidecars = list(tmp_path.glob("*.provenance.json"))
     assert sidecars == [Path(f"{output}.provenance.json")]
     payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
     assert payload["routing"]["requested_engine"] == "rendering.ffmpeg"
     assert payload["audio_ownership"] == "rendered"
+
+
+def test_single_segment_plan_records_finalizer_fragment(
+    tmp_path: Path,
+) -> None:
+    """A single-segment plan that pins the ffmpeg finalizer must record BOTH
+    the renderer fragment and the executed finalizer fragment in provenance."""
+    transport = FakeTransport()
+    transport.plan = _plan("fixture.window", segment_frames=(10,))
+    service = _service(
+        tmp_path,
+        transport,
+        renderer_ids=("fixture.window",),
+        planner_ids=("rendering.legacy_hybrid",),
+    )
+    output = tmp_path / "single-finalize.mp4"
+
+    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)
+
+    payload = _sidecar(output)
+    fragments = payload["backend_fragments"]
+    assert fragments["fixture.window"]["fixture_backend"] == "fixture.window"
+    assert (
+        fragments["rendering.ffmpeg-finalizer"]["fixture_backend"]
+        == "rendering.ffmpeg-finalizer"
+    )
+    # One hashed lineage entry per segment (the renderer artifact), while the
+    # finalizer's artifact is represented by the finalizer fragment.
+    assert len(payload["artifact_profiles"]) == 1
+    assert payload["artifact_profiles"][0]["path"].endswith("segment-0000.mp4")
+
+
+def test_direct_render_with_pinned_finalizer_records_both_fragments(
+    tmp_path: Path,
+) -> None:
+    """An embedding host pinning `finalizer_id` on a direct render gets the
+    renderer artifact lineage AND the executed finalizer fragment."""
+    transport = FakeTransport()
+    service = _service(
+        tmp_path,
+        transport,
+        renderer_ids=("rendering.remotion",),
+        planner_ids=(),
+        finalizer_id="rendering.ffmpeg-finalizer",
+    )
+    output = tmp_path / "direct-finalize.mp4"
+
+    service.render_request(
+        replace(_request(tmp_path), backend_config={}),
+        selector="rendering.remotion",
+        out_path=output,
+    )
+
+    payload = _sidecar(output)
+    fragments = payload["backend_fragments"]
+    assert (
+        fragments["rendering.remotion"]["fixture_backend"] == "rendering.remotion"
+    )
+    assert (
+        fragments["rendering.ffmpeg-finalizer"]["fixture_backend"]
+        == "rendering.ffmpeg-finalizer"
+    )
+    assert len(payload["artifact_profiles"]) == 1
+    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"

exec
/bin/zsh -lc 'rg -n "executable-finalizer|finalizer provenance|compatibility_results|v1_compatibility|fragment_results|artifact_lineage" .oracle/checkins/batch-4-r2.md astrid/core/rendering/service.py tests/core/rendering/test_service.py | head -160' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 103ms:
astrid/core/rendering/service.py:224:        v1_compatibility: Mapping[str, Any] | None = None,
astrid/core/rendering/service.py:287:            v1_compatibility=v1_compatibility,
astrid/core/rendering/service.py:298:        v1_compatibility: Mapping[str, Any] | None = None,
astrid/core/rendering/service.py:345:                    v1_compatibility=v1_compatibility,
astrid/core/rendering/service.py:417:        v1_compatibility: Mapping[str, Any] | None,
astrid/core/rendering/service.py:442:            artifact_lineage = [item.video for item in segment_results]
astrid/core/rendering/service.py:443:            compatibility_results = segment_results
astrid/core/rendering/service.py:444:            fragment_results = (
astrid/core/rendering/service.py:508:            artifact_lineage = [renderer_result.video]
astrid/core/rendering/service.py:509:            compatibility_results = (
astrid/core/rendering/service.py:512:            fragment_results = (
astrid/core/rendering/service.py:519:        compatibility = self._v1_compatibility(
astrid/core/rendering/service.py:520:            compatibility_results,
astrid/core/rendering/service.py:521:            supplied=v1_compatibility,
astrid/core/rendering/service.py:523:        fragments = self._merge_backend_fragments(fragment_results)
astrid/core/rendering/service.py:530:            artifact_profiles=artifact_lineage,
astrid/core/rendering/service.py:535:            v1_compatibility=compatibility,
astrid/core/rendering/service.py:1845:    def _v1_compatibility(
.oracle/checkins/batch-4-r2.md:425:         v1_compatibility: Mapping[str, Any] | None,
.oracle/checkins/batch-4-r2.md:449:             artifact_lineage = [item.video for item in segment_results]
.oracle/checkins/batch-4-r2.md:450:             compatibility_results = segment_results
.oracle/checkins/batch-4-r2.md:451:             fragment_results = (
.oracle/checkins/batch-4-r2.md:514:             artifact_lineage = [final_result.video]
.oracle/checkins/batch-4-r2.md:515:             compatibility_results = [final_result]
.oracle/checkins/batch-4-r2.md:516:             fragment_results = [final_result]
.oracle/checkins/batch-4-r2.md:519:         compatibility = self._v1_compatibility(
.oracle/checkins/batch-4-r2.md:520:             compatibility_results,
.oracle/checkins/batch-4-r2.md:521:             supplied=v1_compatibility,
.oracle/checkins/batch-4-r2.md:523:         fragments = self._merge_backend_fragments(fragment_results)
.oracle/checkins/batch-4-r2.md:530:             artifact_profiles=artifact_lineage,
.oracle/checkins/batch-4-r2.md:535:             v1_compatibility=compatibility,
.oracle/checkins/batch-4-r2.md:1516:         v1_compatibility: Mapping[str, Any] | None,
.oracle/checkins/batch-4-r2.md:1540:             artifact_lineage = [item.video for item in segment_results]
.oracle/checkins/batch-4-r2.md:1541:             compatibility_results = segment_results
.oracle/checkins/batch-4-r2.md:1542:             fragment_results = (
.oracle/checkins/batch-4-r2.md:1605:             artifact_lineage = [final_result.video]
.oracle/checkins/batch-4-r2.md:1606:             compatibility_results = [final_result]
.oracle/checkins/batch-4-r2.md:1607:             fragment_results = [final_result]
.oracle/checkins/batch-4-r2.md:1610:         compatibility = self._v1_compatibility(
.oracle/checkins/batch-4-r2.md:1611:             compatibility_results,
.oracle/checkins/batch-4-r2.md:1612:             supplied=v1_compatibility,
.oracle/checkins/batch-4-r2.md:1614:         fragments = self._merge_backend_fragments(fragment_results)
.oracle/checkins/batch-4-r2.md:1621:             artifact_profiles=artifact_lineage,
.oracle/checkins/batch-4-r2.md:1626:             v1_compatibility=compatibility,
.oracle/checkins/batch-4-r2.md:1951:astrid/core/rendering/service.py:521:            artifact_profiles=artifact_lineage,
.oracle/checkins/batch-4-r2.md:2040:   224	        v1_compatibility: Mapping[str, Any] | None = None,
.oracle/checkins/batch-4-r2.md:2103:   287	            v1_compatibility=v1_compatibility,
.oracle/checkins/batch-4-r2.md:2114:   298	        v1_compatibility: Mapping[str, Any] | None = None,
.oracle/checkins/batch-4-r2.md:2161:   345	                    v1_compatibility=v1_compatibility,
.oracle/checkins/batch-4-r2.md:2706:   218	                lineage = _artifact_lineage(profile)
.oracle/checkins/batch-4-r2.md:2708:   220	                lineage = _artifact_lineage_from_mapping(profile, key=path)
.oracle/checkins/batch-4-r2.md:2737:   249	                record = _artifact_lineage(profile)
.oracle/checkins/batch-4-r2.md:2746:   258	                record = _artifact_lineage_from_mapping(
.oracle/checkins/batch-4-r2.md:2773:   285	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
.oracle/checkins/batch-4-r2.md:2798:   409	    v1_compatibility: Mapping[str, Any] | None = None,
.oracle/checkins/batch-4-r2.md:2805:   416	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
.oracle/checkins/batch-4-r2.md:2828:   439	    compatibility = _normalize_v1_compatibility(v1_compatibility)
.oracle/checkins/batch-4-r2.md:4170:astrid/core/rendering/service.py:521:            artifact_profiles=artifact_lineage,
.oracle/checkins/batch-4-r2.md:4184:   441	            artifact_lineage = [item.video for item in segment_results]
.oracle/checkins/batch-4-r2.md:4185:   442	            compatibility_results = segment_results
.oracle/checkins/batch-4-r2.md:4186:   443	            fragment_results = (
.oracle/checkins/batch-4-r2.md:4226:   483	            artifact_lineage = [final_result.video]
.oracle/checkins/batch-4-r2.md:4227:   484	            compatibility_results = [final_result]
.oracle/checkins/batch-4-r2.md:4228:   485	            fragment_results = [final_result]
.oracle/checkins/batch-4-r2.md:4231:   488	        compatibility = self._v1_compatibility(
.oracle/checkins/batch-4-r2.md:4232:   489	            compatibility_results,
.oracle/checkins/batch-4-r2.md:4233:   490	            supplied=v1_compatibility,
.oracle/checkins/batch-4-r2.md:4648:/bin/zsh -lc "nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '1310,1385p' && nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '610,655p' && rg -n \"def _v1_compatibility|def _merge_backend_fragments\" astrid/core/rendering/service.py && nl -ba astrid/core/rendering/service.py | sed -n '1760,1870p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
.oracle/checkins/batch-4-r2.md:4773:1836:    def _v1_compatibility(
.oracle/checkins/batch-4-r2.md:4850:  1836	    def _v1_compatibility(
.oracle/checkins/batch-4-r2.md:5148:   505	            artifact_lineage = [final_result.video]
.oracle/checkins/batch-4-r2.md:5149:   506	            compatibility_results = [final_result]
.oracle/checkins/batch-4-r2.md:5150:   507	            fragment_results = [final_result]
.oracle/checkins/batch-4-r2.md:5153:   510	        compatibility = self._v1_compatibility(
.oracle/checkins/batch-4-r2.md:5154:   511	            compatibility_results,
.oracle/checkins/batch-4-r2.md:5155:   512	            supplied=v1_compatibility,
.oracle/checkins/batch-4-r2.md:5157:   514	        fragments = self._merge_backend_fragments(fragment_results)
.oracle/checkins/batch-4-r2.md:5164:   521	            artifact_profiles=artifact_lineage,
.oracle/checkins/batch-4-r2.md:5389:- HIGH — Executable-finalizer provenance is inconsistent. The direct path overwrites the renderer result, then records only the finalizer artifact/fragments at [service.py:505](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:505), losing renderer artifact lineage, backend fragments, and v1 compatibility data. Conversely, single-segment planner finalization records only the renderer fragments at [service.py:443](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:443), omitting the executed finalizer fragment. Preserve the segment result separately and merge both results’ fragments.
.oracle/checkins/batch-4-r2.md:5394:- HIGH — Executable-finalizer provenance is inconsistent. The direct path overwrites the renderer result, then records only the finalizer artifact/fragments at [service.py:505](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:505), losing renderer artifact lineage, backend fragments, and v1 compatibility data. Conversely, single-segment planner finalization records only the renderer fragments at [service.py:443](/Users/peteromalley/Documents/reigh-workspace/Astrid-oracle/astrid/core/rendering/service.py:443), omitting the executed finalizer fragment. Preserve the segment result separately and merge both results’ fragments.

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '1260,1510p'; nl -ba astrid/core/rendering/service.py | sed -n '1780,1895p'; rg -n \"def _finish_plan|def complete_audio|_direct_plan|finalizer_id\" astrid/core/rendering/service.py" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1260	            )
  1261	            normalized_segments.append(normalized_segment)
  1262	            result = self._invoke_renderer(
  1263	                segment_request,
  1264	                selected=resolved,
  1265	                workspace=workspace,
  1266	                output_name=segment_request.output_name,
  1267	                # Segment renderers may emit a profile that the registered
  1268	                # finalizer must normalize.  The artifact is first validated
  1269	                # against its own declaration; a one-segment exact match is
  1270	                # checked against the plan in _finish_plan, while every
  1271	                # mismatch and every multi-segment plan goes through the
  1272	                # pinned finalizer.
  1273	                expected_profile=None,
  1274	            )
  1275	            completed = self.complete_audio(
  1276	                result,
  1277	                request=segment_request,
  1278	                plan=response,
  1279	                workspace=workspace,
  1280	                backend=candidate.id,
  1281	                # The plan pins an explicit finalizer; segment audio is
  1282	                # deferred to it (single- and multi-segment alike) so a
  1283	                # normalizable profile/audio mismatch cannot fail the segment
  1284	                # before the finalizer can normalize it.
  1285	                defer_to_finalizer=response.finalizer.id != _DIRECT_FINALIZER_ID,
  1286	            )
  1287	            self._validate_segment_duration(
  1288	                completed,
  1289	                segment=segment,
  1290	                canonical_profile=response.profile,
  1291	                backend=candidate.id,
  1292	            )
  1293	            segment_results.append(completed)
  1294	
  1295	        finalizer, finalizer_evidence = self._resolve_candidate(
  1296	            self.finalizers,
  1297	            response.finalizer.id,
  1298	            kind="finalizer",
  1299	            observe=False,
  1300	        )
  1301	        finalizer_resolution = replace(
  1302	            response.finalizer,
  1303	            id=finalizer.id,
  1304	            source_pack=self._source_pack(finalizer, finalizer_evidence),
  1305	            manifest_digest=finalizer.manifest_digest,
  1306	            trust_eligibility=finalizer.eligibility.to_dict(),
  1307	            alias_chain=(
  1308	                response.finalizer.alias_chain
  1309	                or list(finalizer_evidence.get("alias_chain") or [])
  1310	            ),
  1311	            override=response.finalizer.override or finalizer_evidence.get("override"),
  1312	            # The planner's finalizer support_decision names its pre-alias
  1313	            # identity; _finish_plan re-evaluates support for the resolved
  1314	            # finalizer and records the authoritative decision.
  1315	            support_decision=None,
  1316	        )
  1317	        plan = replace(
  1318	            response,
  1319	            request_digest=compute_request_digest(request.to_dict()),
  1320	            requested_policy=policy.requested,
  1321	            planner=planner_resolution,
  1322	            segments=normalized_segments,
  1323	            finalizer=finalizer_resolution,
  1324	        )
  1325	        return plan, segment_results, (finalizer, finalizer_evidence)
  1326	
  1327	    def _finish_plan(
  1328	        self,
  1329	        request: RenderRequest,
  1330	        *,
  1331	        plan: RenderPlan,
  1332	        segment_results: list[RenderResult],
  1333	        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
  1334	        workspace: Path,
  1335	    ) -> tuple[RenderResult, RenderPlan]:
  1336	        candidate, evidence = pinned_finalizer
  1337	        if candidate.id == _DIRECT_FINALIZER_ID:
  1338	            # No executable finalizer pinned: the segment must already match
  1339	            # the canonical plan profile exactly.
  1340	            if len(segment_results) != 1:
  1341	                raise_internal_error(
  1342	                    backend=_CORE_BACKEND_ID,
  1343	                    message="direct finalizer received multiple segments",
  1344	                    recovery_command="select a planner that pins an executable finalizer",
  1345	                    details={"segment_count": len(segment_results)},
  1346	                )
  1347	            result = self._validator(
  1348	                segment_results[0],
  1349	                expected_profile=plan.profile,
  1350	                workspace_root=workspace,
  1351	            )
  1352	            return result, plan
  1353	
  1354	        ownerships = {item.audio_ownership for item in segment_results}
  1355	        if ownerships == {AudioOwnership.PASSTHROUGH}:
  1356	            requested_audio = AudioOwnership.PASSTHROUGH
  1357	        elif plan.profile.has_audio:
  1358	            requested_audio = AudioOwnership.RENDERED
  1359	        else:
  1360	            requested_audio = AudioOwnership.NONE
  1361	        support_audio = (
  1362	            None
  1363	            if requested_audio is AudioOwnership.PASSTHROUGH
  1364	            and plan.profile.has_audio
  1365	            else requested_audio
  1366	        )
  1367	        support_request = RenderRequest(
  1368	            schema_version=SCHEMA_VERSION,
  1369	            timeline_path=request.timeline_path,
  1370	            assets_registry_path=request.assets_registry_path,
  1371	            output_name=request.output_name,
  1372	            audio=support_audio,
  1373	            profile=plan.profile,
  1374	            backend_config=request.backend_config,
  1375	            metadata=request.metadata,
  1376	        )
  1377	        report = self._support(
  1378	            candidate,
  1379	            request=support_request,
  1380	            workspace=workspace,
  1381	            registry=self.finalizers,
  1382	        )
  1383	        if not report.supported:
  1384	            self._unsupported_report(report, registry=self.finalizers)
  1385	        prior_finalizer = plan.finalizer
  1386	        finalizer_resolution = replace(
  1387	            self._finalizer_resolution(
  1388	                candidate,
  1389	                evidence,
  1390	                support=report,
  1391	            ),
  1392	            alias_chain=(
  1393	                prior_finalizer.alias_chain
  1394	                or list(evidence.get("alias_chain") or [])
  1395	            ),
  1396	            override=prior_finalizer.override or evidence.get("override"),
  1397	        )
  1398	        plan = replace(plan, finalizer=finalizer_resolution)
  1399	        finalize_request = FinalizeRequest(
  1400	            schema_version=SCHEMA_VERSION,
  1401	            plan=plan,
  1402	            artifacts=[item.video for item in segment_results],
  1403	            output_name=request.output_name,
  1404	            backend_config={
  1405	                candidate.id: dict(request.backend_config.get(candidate.id, {}))
  1406	            }
  1407	            if candidate.id in request.backend_config
  1408	            else {},
  1409	            metadata=request.metadata,
  1410	        )
  1411	        self._observe("finalize", backend=candidate.id)
  1412	        response = self._run_command(
  1413	            candidate,
  1414	            "finalize",
  1415	            finalize_request,
  1416	            workspace=workspace,
  1417	        )
  1418	        if not isinstance(response, RenderResult):
  1419	            raise_protocol_error(
  1420	                backend=candidate.id,
  1421	                message="finalize operation did not return a RenderResult",
  1422	                details={"received_type": type(response).__name__},
  1423	            )
  1424	        try:
  1425	            response = finalize_request.validate_final_result(response)
  1426	        except (TypeError, ValueError) as exc:
  1427	            raise_invalid_artifact_error(
  1428	                backend=candidate.id,
  1429	                message=f"finalizer returned an invalid result: {exc}",
  1430	                recovery_command="rerun finalization in a fresh invocation workspace",
  1431	                details={"error_type": type(exc).__name__},
  1432	            )
  1433	        self._observe("validate", backend=candidate.id)
  1434	        validated = self._validator(
  1435	            response,
  1436	            expected_profile=plan.profile,
  1437	            workspace_root=workspace,
  1438	        )
  1439	        self._validate_planned_duration(
  1440	            validated,
  1441	            planned_frames=(
  1442	                plan.window.duration_frames
  1443	                if plan.window is not None
  1444	                else plan.total_frames
  1445	            ),
  1446	            canonical_profile=plan.profile,
  1447	            backend=candidate.id,
  1448	            label="finalized artifact",
  1449	        )
  1450	        completed = self.complete_audio(
  1451	            validated,
  1452	            request=request,
  1453	            plan=plan,
  1454	            workspace=workspace,
  1455	            backend=candidate.id,
  1456	        )
  1457	        self._validate_planned_duration(
  1458	            completed,
  1459	            planned_frames=(
  1460	                plan.window.duration_frames
  1461	                if plan.window is not None
  1462	                else plan.total_frames
  1463	            ),
  1464	            canonical_profile=plan.profile,
  1465	            backend=candidate.id,
  1466	            label="audio-completed artifact",
  1467	        )
  1468	        return completed, plan
  1469	
  1470	    def complete_audio(
  1471	        self,
  1472	        result: RenderResult,
  1473	        *,
  1474	        request: RenderRequest,
  1475	        plan: RenderPlan,
  1476	        workspace: Path,
  1477	        backend: str = _CORE_BACKEND_ID,
  1478	        defer_to_finalizer: bool = False,
  1479	    ) -> RenderResult:
  1480	        """Apply host-owned completion semantics after renderer validation.
  1481	
  1482	        ``rendered`` is already complete. ``none`` is an intentional
  1483	        visual-only result, while ``passthrough`` must be completed by the
  1484	        embedding host before publication.  A configured completer may also
  1485	        apply an optional compatibility policy to ``none`` without requiring
  1486	        arbitrary renderers to synthesize silence.
  1487	        """
  1488	
  1489	        self._observe("audio", ownership=result.audio_ownership.value)
  1490	        if result.audio_ownership is AudioOwnership.RENDERED:
  1491	            return result
  1492	        if result.video.profile.has_audio:
  1493	            raise_invalid_artifact_error(
  1494	                backend=backend,
  1495	                message=(
  1496	                    f"audio_ownership={result.audio_ownership.value!r} requires "
  1497	                    "a visual-only renderer artifact"
  1498	                ),
  1499	                recovery_command="rerender with an audio/profile pair that agrees",
  1500	            )
  1501	        if defer_to_finalizer:
  1502	            # A registered finalizer owns cross-segment compatibility: it may
  1503	            # synthesize silence for NONE segments or preserve a uniform set
  1504	            # of PASSTHROUGH segments.  Completion, if still necessary, runs
  1505	            # once on the finalized result below.
  1506	            return result
  1507	        if (
  1508	            result.audio_ownership is AudioOwnership.NONE
  1509	            and (
  1510	                plan.profile.has_audio
  1780	            self._transport
  1781	            if self._transport is not None
  1782	            else self._transport_factory(candidate.id)
  1783	        )
  1784	        return transport.run(
  1785	            verb,
  1786	            candidate.manifest.command,
  1787	            backend=candidate.id,
  1788	            request_path=request_path,
  1789	            result_path=result_path,
  1790	            cwd=candidate.pack_root,
  1791	            timeout=candidate.manifest.timeout_seconds,
  1792	            required_binaries=(
  1793	                candidate.manifest.required_binaries
  1794	                if required_binaries is None
  1795	                else required_binaries
  1796	            ),
  1797	        )
  1798	
  1799	    @staticmethod
  1800	    def _artifact_path(result: RenderResult, workspace: Path) -> Path:
  1801	        candidate = (workspace / result.video.path).resolve(strict=False)
  1802	        try:
  1803	            candidate.relative_to(workspace.resolve())
  1804	        except ValueError:
  1805	            raise_invalid_artifact_error(
  1806	                backend=_CORE_BACKEND_ID,
  1807	                message="validated renderer artifact escaped its invocation workspace",
  1808	                recovery_command="rerun the renderer with a contained output path",
  1809	                details={"path": result.video.path},
  1810	            )
  1811	        return candidate
  1812	
  1813	    @staticmethod
  1814	    def _input_hashes(request: RenderRequest) -> dict[str, str]:
  1815	        paths: dict[str, Path] = {"timeline": Path(request.timeline_path)}
  1816	        if request.assets_registry_path is not None:
  1817	            paths["assets_registry"] = Path(request.assets_registry_path)
  1818	        return {
  1819	            name: sha256_file(path)
  1820	            for name, path in paths.items()
  1821	            if path.is_file()
  1822	        }
  1823	
  1824	    @staticmethod
  1825	    def _merge_backend_fragments(
  1826	        results: Sequence[RenderResult],
  1827	    ) -> dict[str, dict[str, Any]]:
  1828	        merged: dict[str, dict[str, Any]] = {}
  1829	        for result in results:
  1830	            for namespace, fragment in result.backend_fragments.items():
  1831	                current = merged.get(namespace)
  1832	                if current is None:
  1833	                    merged[namespace] = dict(fragment)
  1834	                elif current != fragment:
  1835	                    records = current.get("service_fragment_sequence")
  1836	                    if isinstance(records, list):
  1837	                        records.append(dict(fragment))
  1838	                    else:
  1839	                        merged[namespace] = {
  1840	                            "service_fragment_sequence": [current, dict(fragment)]
  1841	                        }
  1842	        return merged
  1843	
  1844	    @staticmethod
  1845	    def _v1_compatibility(
  1846	        results: Sequence[RenderResult],
  1847	        *,
  1848	        supplied: Mapping[str, Any] | None,
  1849	    ) -> dict[str, Any]:
  1850	        compatibility: dict[str, Any] = {
  1851	            "project_dir": None,
  1852	            "composition_id": "TimelineComposition",
  1853	            "active_pack_order": [],
  1854	            "active_theme": None,
  1855	            "registry_hash": None,
  1856	            "registry_state": {},
  1857	            "resolved_effect_ids": [],
  1858	            "resolved_effects": [],
  1859	            "source_pack_ids": [],
  1860	            "element_roots": [],
  1861	            "staged_asset_ids": [],
  1862	            "staged_asset_root": None,
  1863	        }
  1864	        segment_provenance: list[dict[str, Any]] = []
  1865	        for result in results:
  1866	            for fragment in result.backend_fragments.values():
  1867	                legacy = fragment.get("legacy_v1")
  1868	                if not isinstance(legacy, Mapping):
  1869	                    continue
  1870	                segment_provenance.append(dict(legacy))
  1871	                for key in compatibility:
  1872	                    if key in legacy:
  1873	                        compatibility[key] = legacy[key]
  1874	                for key in (
  1875	                    "ffmpeg_specialization",
  1876	                    "audio_reactive_colour",
  1877	                ):
  1878	                    if key in legacy:
  1879	                        compatibility[key] = legacy[key]
  1880	        if len(segment_provenance) > 1:
  1881	            compatibility["segment_provenance"] = segment_provenance
  1882	        if supplied is not None:
  1883	            compatibility.update(dict(supplied))
  1884	        return compatibility
  1885	
  1886	    @staticmethod
  1887	    def _alternatives(
  1888	        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
  1889	        *,
  1890	        exclude: str | None = None,
  1891	    ) -> list[str]:
  1892	        try:
  1893	            return [
  1894	                candidate.id
  1895	                for candidate in registry.list()
170:        finalizer_id: str | None = None,
207:        self.finalizer_id = finalizer_id
457:            plan = self._direct_plan(
502:                plan = self._direct_plan(
1327:    def _finish_plan(
1470:    def complete_audio(
1613:    def _direct_plan(
1684:        if self.finalizer_id is not None:
1687:                self.finalizer_id,

exec
/bin/zsh -lc "nl -ba astrid/core/rendering/service.py | sed -n '1468,1745p'; git show 907423f2:astrid/core/rendering/service.py | nl -ba | sed -n '420,525p'; rg -n \"legacy_v1\" astrid/packs/rendering/finalizers astrid/core tests/core/rendering | head -100" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 65ms:
astrid/core/rendering/service.py:1867:                legacy = fragment.get("legacy_v1")

exec
/bin/zsh -lc 'rg -n "backend_fragments|artifact_profiles|segment_provenance|finalizer" tests/core/rendering/test_service.py | head -240; rg -n "backend_fragments|legacy_v1" astrid/packs/rendering/backends astrid/packs/rendering/finalizers | head -160; git show --stat --oneline --decorate 9d1dfd92 && git show --format=fuller --no-patch 9d1dfd92' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 38ms:
9d1dfd92 (HEAD -> oracle-run) batch4-rework3: oracle re-review2 issue 1 (executable-finalizer provenance preserves renderer lineage and merges finalizer fragments)
 .oracle/checkins/batch-4-r2.md       | 5394 ++++++++++++++++++++++++++++++++++
 astrid/core/rendering/service.py     |   21 +-
 tests/core/rendering/test_service.py |   66 +
 3 files changed, 5475 insertions(+), 6 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit 9d1dfd92f940f8353ebd14f7021c9428b6c19790
Author:     POM <peter@omalley.io>
AuthorDate: Wed Aug 12 17:36:46 2026 +0200
Commit:     POM <peter@omalley.io>
CommitDate: Wed Aug 12 17:36:46 2026 +0200

    batch4-rework3: oracle re-review2 issue 1 (executable-finalizer provenance preserves renderer lineage and merges finalizer fragments)

exec
/bin/zsh -lc "rg -n \"v1_compatibility|segment_provenance|backend_fragments|artifact_profiles\" docs astrid | head -240; nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '1328,1372p'; nl -ba astrid/packs/rendering/backends/remotion/run.py | sed -n '1138,1168p'; nl -ba astrid/packs/rendering/backends/ffmpeg/run.py | sed -n '580,645p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 109ms:
astrid/core/rendering/provenance.py:27:    _validate_backend_fragments,
astrid/core/rendering/provenance.py:40:def validate_backend_fragments(
astrid/core/rendering/provenance.py:45:    normalized = _validate_backend_fragments(fragments or {})
astrid/core/rendering/provenance.py:192:def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
astrid/core/rendering/provenance.py:198:                "mapping-form artifact_profiles is unordered; use sequence form "
astrid/core/rendering/provenance.py:206:                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
astrid/core/rendering/provenance.py:212:                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
astrid/core/rendering/provenance.py:223:                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
astrid/core/rendering/provenance.py:233:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:264:                    "sequence artifact_profiles entries must be VideoArtifacts "
astrid/core/rendering/provenance.py:269:                    f"artifact_profiles sequence contains duplicate path "
astrid/core/rendering/provenance.py:278:                    f"artifact_profiles must record exactly one hashed lineage entry "
astrid/core/rendering/provenance.py:282:    raise TypeError("artifact_profiles must be an object or array")
astrid/core/rendering/provenance.py:374:def _normalize_v1_compatibility(
astrid/core/rendering/provenance.py:379:            "v1_compatibility is required and must preserve all always-emitted v1 fields"
astrid/core/rendering/provenance.py:381:    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
astrid/core/rendering/provenance.py:404:    artifact_profiles: Any = None,
astrid/core/rendering/provenance.py:408:    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
astrid/core/rendering/provenance.py:409:    v1_compatibility: Mapping[str, Any] | None = None,
astrid/core/rendering/provenance.py:416:    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
astrid/core/rendering/provenance.py:439:    compatibility = _normalize_v1_compatibility(v1_compatibility)
astrid/core/rendering/provenance.py:462:        "artifact_profiles": _normalize_artifact_profiles(
astrid/core/rendering/provenance.py:463:            artifact_profiles,
astrid/core/rendering/provenance.py:470:        "backend_fragments": validate_backend_fragments(backend_fragments),
astrid/core/rendering/provenance.py:513:    "validate_backend_fragments",
astrid/core/rendering/contracts.py:54:        "backend_fragments",
astrid/core/rendering/contracts.py:74:        "artifact_profiles",
astrid/core/rendering/contracts.py:79:        "backend_fragments",
astrid/core/rendering/contracts.py:97:        "segment_provenance",
astrid/core/rendering/contracts.py:1513:def _validate_backend_fragments(value: Any) -> dict[str, dict[str, Any]]:
astrid/core/rendering/contracts.py:1514:    mapping = _require_mapping(value, "backend_fragments")
astrid/core/rendering/contracts.py:1518:        fragment = _json_safe_mapping(raw_fragment, label=f"backend_fragments[{namespace!r}]")
astrid/core/rendering/contracts.py:1536:    backend_fragments: dict[str, dict[str, Any]] = field(default_factory=dict)
astrid/core/rendering/contracts.py:1557:        object.__setattr__(self, "backend_fragments", _validate_backend_fragments(self.backend_fragments))
astrid/core/rendering/contracts.py:1578:                "backend_fragments": self.backend_fragments,
astrid/core/rendering/contracts.py:1602:                backend_fragments=data.get("backend_fragments", {}),
astrid/core/rendering/schemas/v1/result.json:306:              "backend_fragments",
astrid/core/rendering/schemas/v1/result.json:319:              "artifact_profiles",
astrid/core/rendering/schemas/v1/result.json:334:              "segment_provenance",
astrid/core/rendering/schemas/v1/result.json:385:        "backend_fragments": {
astrid/core/rendering/schemas/v1/result.json:543:      "backend_fragments": {
docs/contracts/render-backend-v1.md:294:attachments), qualified-ID-keyed `backend_fragments`, explicit
docs/contracts/render-backend-v1.md:303:  "backend_fragments": {
docs/contracts/render-backend-v1.md:468:`artifact_profiles`, `audio_ownership`, `normalization`, `finalizer`,
docs/contracts/render-backend-v1.md:469:`attachments`, and `backend_fragments`.
docs/contracts/render-backend-v1.md:478:are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
docs/contracts/render-backend-v1.md:505:reshapes a V1 key. When the v1 `segment_provenance` top-level projection
docs/contracts/render-backend-v1.md:514:optional `segment_provenance`, `ffmpeg_specialization`, and
docs/contracts/render-backend-v1.md:521:conditional fields (`segment_provenance`, `ffmpeg_specialization`, and
docs/contracts/render-backend-v1.md:524:Backend-owned data appears only under `backend_fragments[qualified_id]`. Before
astrid/core/rendering/service.py:224:        v1_compatibility: Mapping[str, Any] | None = None,
astrid/core/rendering/service.py:287:            v1_compatibility=v1_compatibility,
astrid/core/rendering/service.py:298:        v1_compatibility: Mapping[str, Any] | None = None,
astrid/core/rendering/service.py:345:                    v1_compatibility=v1_compatibility,
astrid/core/rendering/service.py:417:        v1_compatibility: Mapping[str, Any] | None,
astrid/core/rendering/service.py:519:        compatibility = self._v1_compatibility(
astrid/core/rendering/service.py:521:            supplied=v1_compatibility,
astrid/core/rendering/service.py:523:        fragments = self._merge_backend_fragments(fragment_results)
astrid/core/rendering/service.py:530:            artifact_profiles=artifact_lineage,
astrid/core/rendering/service.py:534:            backend_fragments=fragments,
astrid/core/rendering/service.py:535:            v1_compatibility=compatibility,
astrid/core/rendering/service.py:1825:    def _merge_backend_fragments(
astrid/core/rendering/service.py:1830:            for namespace, fragment in result.backend_fragments.items():
astrid/core/rendering/service.py:1845:    def _v1_compatibility(
astrid/core/rendering/service.py:1864:        segment_provenance: list[dict[str, Any]] = []
astrid/core/rendering/service.py:1866:            for fragment in result.backend_fragments.values():
astrid/core/rendering/service.py:1870:                segment_provenance.append(dict(legacy))
astrid/core/rendering/service.py:1880:        if len(segment_provenance) > 1:
astrid/core/rendering/service.py:1881:            compatibility["segment_provenance"] = segment_provenance
astrid/packs/rendering/finalizers/ffmpeg/run.py:1355:            backend_fragments={
astrid/packs/rendering/backends/remotion/run.py:496:    segment_provenance: list[dict[str, Any]] | None = None,
astrid/packs/rendering/backends/remotion/run.py:541:    if segment_provenance is not None:
astrid/packs/rendering/backends/remotion/run.py:542:        payload["segment_provenance"] = segment_provenance
astrid/packs/rendering/backends/remotion/run.py:559:    segment_provenance: list[dict[str, Any]] | None = None,
astrid/packs/rendering/backends/remotion/run.py:573:        segment_provenance=segment_provenance,
astrid/packs/rendering/backends/remotion/run.py:1154:            backend_fragments={
astrid/packs/rendering/executors/render/legacy_engine.py:270:        segment_provenance: list[dict[str, Any]] = []
astrid/packs/rendering/executors/render/legacy_engine.py:315:                segment_provenance.append(_json_loads(sidecar_path.read_text(encoding="utf-8")))
astrid/packs/rendering/executors/render/legacy_engine.py:336:            segment_provenance=segment_provenance,
astrid/packs/rendering/backends/ffmpeg/run.py:634:            backend_fragments={
  1328	                replace(segment, profile=effective_profile)
  1329	                for segment in normalized_prepared
  1330	            ]
  1331	            # The prepared list now has a uniform canonical profile, so this
  1332	            # call performs only the concat-demuxer stream-copy assembly.
  1333	            assembly_started = True
  1334	            extra_normalization = _assemble_prepared_segments(
  1335	                normalized_prepared,
  1336	                output_path,
  1337	                target_profile=effective_profile,
  1338	                faststart=faststart,
  1339	                runner=execute,
  1340	            )
  1341	            published = True
  1342	            normalization.extend(extra_normalization)
  1343	        video = VideoArtifact.from_file(
  1344	            path=output_path,
  1345	            workspace_root=workspace,
  1346	            profile=effective_profile,
  1347	            duration_frames=total_frames,
  1348	            audio=ownership,
  1349	            attachments=request.expected_attachments,
  1350	        )
  1351	        result = RenderResult(
  1352	            schema_version=SCHEMA_VERSION,
  1353	            video=video,
  1354	            audio_ownership=ownership,
  1355	            backend_fragments={
  1356	                BACKEND_ID: {
  1357	                    "finalizer_kind": "ffmpeg",
  1358	                    "finalizer_version": BACKEND_VERSION,
  1359	                    "segment_count": len(prepared),
  1360	                    "stream_copied_segments": [
  1361	                        segment.index
  1362	                        for segment in prepared
  1363	                        if not _profile_differences(segment.profile, assembly_profile)
  1364	                    ],
  1365	                    "normalized_segments": [
  1366	                        segment.index
  1367	                        for segment in prepared
  1368	                        if _profile_differences(segment.profile, assembly_profile)
  1369	                    ],
  1370	                    "audio_mode": ownership.value,
  1371	                }
  1372	            },
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

exec
/bin/zsh -lc "nl -ba docs/contracts/render-backend-v1.md | sed -n '440,545p'; nl -ba astrid/core/rendering/provenance.py | sed -n '180,295p'; nl -ba astrid/core/rendering/provenance.py | sed -n '360,480p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
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
   471	`request_digest`, `requested_policy`, `planner`, every segment's nested
   472	`renderer`, and `finalizer` are copied from the validated `RenderPlan`; the
   473	assembler accepts no parallel singular renderer identity. The nested records
   474	have exactly the resolution shapes defined in Planning, so a hybrid plan keeps
   475	distinct source pack, manifest, alias/override, support, and input-hash evidence
   476	for every renderer invocation. Planner and finalizer records carry the same
   477	alias/override/trust/support evidence as renderer records. Rendered artifacts
   478	are REQUIRED in `artifact_profiles` for any positive render plan: exactly one
   479	hashed lineage entry PER SEGMENT. Multi-segment plans MUST use the ordered
   480	sequence form (one VideoArtifact or emitted lineage record per segment, in
   481	segment order); single-segment plans may use a path-keyed mapping. Emitted
   482	lineage records round-trip (re-passing them validates identically) and every
   483	record MUST carry a non-empty string `path` (missing, `None`, or numeric
   484	paths are rejected). Every record carries `profile`, a validated 64-hex string
   485	`sha256`, and `attachments` — each attachment `{path, kind, sha256}` with a
   486	workspace-relative path, kind matching `[a-z][a-z0-9-]*`, and globally unique
   487	names across all segment artifacts. All plan, artifact, and attachment values
   488	are reconstructed through their DTO validators at the provenance boundary
   489	(mutated frozen instances cannot bypass validation); duplicate paths,
   490	duplicate attachment names, path escapes, invalid kinds, profile-only entries,
   491	null/malformed hashes, and cardinality mismatches are rejected. All JSON
   492	Schema patterns are language-neutral (ECMAScript-valid; no Python-only
   493	anchors), and whitespace is an explicit ECMAScript `\s` class shared verbatim
   494	by the DTO and schemas — Python and non-Python validators agree on every
   495	character including `\u0085`, `\uFEFF`, and the `\u2000-\u200a` block. Replay
   496	can verify rendered outputs byte-for-byte. `input_hashes` describe inputs
   497	only, never rendered outputs.
   498	
   499	`engine` is only the legacy request projection. The `segments` key keeps the
   500	V1-compatible flat projection: one `{engine, from, to}` entry per segment,
   501	derived from `renderer.id` and the validated integer `FrameWindow` at its
   502	rational FPS — exactly the shape legacy consumers read. The additive
   503	`segments_v2` key carries the complete normalized v2 segment records
   504	(`window`, `renderer` resolution, `input_hashes`); it never overwrites or
   505	reshapes a V1 key. When the v1 `segment_provenance` top-level projection
   506	applies, core passes it through VERBATIM from the caller's compatibility
   507	projection — it is never rewritten or re-derived.
   508	
   509	For the whole epic, core also preserves every current v1 top-level projection:
   510	
   511	`project_dir`, `composition_id`, `active_pack_order`, `active_theme`,
   512	`registry_hash`, `registry_state`, `resolved_effect_ids`, `resolved_effects`,
   513	`source_pack_ids`, `element_roots`, `staged_asset_ids`, `staged_asset_root`,
   514	optional `segment_provenance`, `ffmpeg_specialization`, and
   515	`audio_reactive_colour`, in addition to the already core-owned
   516	`schema_version`, `engine`, `output`, `timeline`, `assets_registry`, and
   517	`segments` names.
   518	
   519	The core assembler requires all historically always-emitted v1 fields on every
   520	call; it rejects a missing or partial compatibility projection. The three
   521	conditional fields (`segment_provenance`, `ffmpeg_specialization`, and
   522	`audio_reactive_colour`) remain conditional on the applicable render path.
   523	
   524	Backend-owned data appears only under `backend_fragments[qualified_id]`. Before
   525	assembly, core rejects a fragment whose top-level member collides with any v2
   526	or v1 core-owned name. Retired singular v2 names such as `resolved_backend`,
   527	`source_pack`, `manifest_digest`, `support_decision`, and `input_hashes` remain
   528	reserved so a fragment cannot revive an ambiguous authority surface. Backends
   529	cannot replace routing, identity, inputs, segments, artifacts, audio,
   530	finalization, or compatibility projections.
   531	Provenance JSON is written with Astrid's atomic JSON helper; file and manifest
   532	digests use the shared chunked SHA-256 helper.
   533	
   534	## Replay inputs and redaction
   535	
   536	A failed invocation can be replayed without rerunning the editorial pipeline.
   537	The retained bundle contains:
   538	
   539	- the resolved request or finalize request;
   540	- localized timeline, asset registry, and required inputs with hashes;
   541	- only the selected implementation's configuration namespace;
   542	- qualified implementation, source pack, version, manifest digest, trust and
   543	  resolution evidence;
   544	- support report and render plan, when present;
   545	- redacted captured logs;
   180	    lineage: Mapping[str, Any],
   181	    seen: set[str],
   182	) -> None:
   183	    """Reject attachment names repeated across segment artifacts."""
   184	    for name in (lineage.get("attachments") or {}):
   185	        if name in seen:
   186	            raise ValueError(
   187	                f"duplicate attachment name {name!r} across segment artifacts"
   188	            )
   189	        seen.add(name)
   190	
   191	
   192	def _normalize_artifact_profiles(value: Any, *, segments: Sequence[Any]) -> Any:
   193	    if value is None:
   194	        value = {}
   195	    if isinstance(value, Mapping):
   196	        if segments and len(segments) > 1:
   197	            raise TypeError(
   198	                "mapping-form artifact_profiles is unordered; use sequence form "
   199	                "(ordered VideoArtifacts, one per segment) for multi-segment plans"
   200	            )
   201	        result: dict[str, Any] = {}
   202	        seen_attachment_names: set[str] = set()
   203	        for key, profile in value.items():
   204	            if not isinstance(key, str):
   205	                raise TypeError(
   206	                    f"artifact_profiles mapping keys must be strings, got {type(key).__name__}"
   207	                )
   208	            path = _require_workspace_relative_path(key, "artifact key")
   209	            if isinstance(profile, VideoArtifact):
   210	                if path != profile.path:
   211	                    raise ValueError(
   212	                        f"artifact_profiles key {path!r} must equal VideoArtifact.path "
   213	                        f"{profile.path!r}"
   214	                    )
   215	                profile = VideoArtifact.from_dict(
   216	                    _json_safe_mapping(profile.to_dict(), label="artifact")
   217	                )
   218	                lineage = _artifact_lineage(profile)
   219	            elif isinstance(profile, Mapping):
   220	                lineage = _artifact_lineage_from_mapping(profile, key=path)
   221	            else:
   222	                raise TypeError(
   223	                    f"artifact_profiles[{path!r}] must be a VideoArtifact or a "
   224	                    "hashed lineage record {profile, sha256, attachments}; "
   225	                    "profile-only entries carry no output hash"
   226	                )
   227	            _reject_duplicate_attachment_names(lineage, seen_attachment_names)
   228	            result[path] = lineage
   229	        # A positive plan must record exactly one hashed artifact per segment.
   230	        if segments:
   231	            if len(result) != len(segments):
   232	                raise ValueError(
   233	                    f"artifact_profiles must record exactly one hashed lineage entry "
   234	                    f"per segment: expected {len(segments)}, got {len(result)}"
   235	                )
   236	        return result
   237	    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
   238	        lineage: list[dict[str, Any]] = []
   239	        seen_paths: set[str] = set()
   240	        seen_attachment_names: set[str] = set()
   241	        for raw_profile in value:
   242	            if isinstance(raw_profile, VideoArtifact):
   243	                # Reconstruct through the DTO so mutation cannot smuggle
   244	                # invalid paths, profiles, or attachments past validation.
   245	                profile = VideoArtifact.from_dict(
   246	                    _json_safe_mapping(raw_profile.to_dict(), label="artifact")
   247	                )
   248	                path = profile.path
   249	                record = _artifact_lineage(profile)
   250	            elif isinstance(raw_profile, Mapping):
   251	                # Already-emitted lineage record: re-validate and re-key by
   252	                # its (validated) path so emitted provenance round-trips.
   253	                raw_path = raw_profile.get("path")
   254	                if not isinstance(raw_path, str) or not raw_path.strip(_ECMA_WHITESPACE):
   255	                    raise ValueError(
   256	                        "emitted lineage record must carry a non-empty string path"
   257	                    )
   258	                record = _artifact_lineage_from_mapping(
   259	                    raw_profile, key=_require_workspace_relative_path(raw_path, "artifact path")
   260	                )
   261	                path = record["path"]
   262	            else:
   263	                raise TypeError(
   264	                    "sequence artifact_profiles entries must be VideoArtifacts "
   265	                    "or emitted lineage records"
   266	                )
   267	            if path in seen_paths:
   268	                raise ValueError(
   269	                    f"artifact_profiles sequence contains duplicate path "
   270	                    f"{path!r}"
   271	                )
   272	            seen_paths.add(path)
   273	            _reject_duplicate_attachment_names(record, seen_attachment_names)
   274	            lineage.append(record)
   275	        if segments:
   276	            if len(lineage) != len(segments):
   277	                raise ValueError(
   278	                    f"artifact_profiles must record exactly one hashed lineage entry "
   279	                    f"per segment: expected {len(segments)}, got {len(lineage)}"
   280	                )
   281	        return lineage
   282	    raise TypeError("artifact_profiles must be an object or array")
   283	
   284	
   285	def _artifact_lineage_from_mapping(raw: Mapping[str, Any], *, key: str) -> dict[str, Any]:
   286	    raw_keys = set(raw)
   287	    allowed = {"profile", "sha256", "attachments", "path"}
   288	    unknown = sorted(raw_keys - allowed)
   289	    if unknown:
   290	        raise ValueError(f"artifact lineage has unknown fields: {', '.join(unknown)}")
   291	    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
   292	    if missing:
   293	        raise ValueError(
   294	            f"artifact lineage is missing required fields: {', '.join(missing)}"
   295	        )
   360	
   361	
   362	def _artifact_lineage(artifact: VideoArtifact) -> dict[str, Any]:
   363	    """One hashed artifact lineage record: profile, sha256, attachments."""
   364	    return _artifact_lineage_from_mapping(
   365	        {
   366	            "profile": artifact.profile,
   367	            "sha256": artifact.sha256,
   368	            "attachments": artifact.attachments,
   369	        },
   370	        key=artifact.path,
   371	    )
   372	
   373	
   374	def _normalize_v1_compatibility(
   375	    fields: Mapping[str, Any] | None,
   376	) -> dict[str, Any]:
   377	    if fields is None:
   378	        raise ValueError(
   379	            "v1_compatibility is required and must preserve all always-emitted v1 fields"
   380	        )
   381	    compatibility = _json_safe_mapping(fields, label="v1_compatibility")
   382	    unknown = sorted(set(compatibility) - PROVENANCE_V1_COMPATIBILITY_KEYS)
   383	    if unknown:
   384	        raise ValueError(
   385	            "v1 compatibility projection contains non-v1 or core-owned keys: "
   386	            + ", ".join(unknown)
   387	        )
   388	    missing = sorted(PROVENANCE_V1_ALWAYS_KEYS - set(compatibility))
   389	    if missing:
   390	        raise ValueError(
   391	            "v1 compatibility projection is missing always-emitted fields: "
   392	            + ", ".join(missing)
   393	        )
   394	    return compatibility
   395	
   396	
   397	def assemble_provenance_v2(
   398	    *,
   399	    engine: str,
   400	    output: str | Path,
   401	    timeline: str | Path,
   402	    assets_registry: str | Path | None,
   403	    plan: RenderPlan | Mapping[str, Any],
   404	    artifact_profiles: Any = None,
   405	    audio_ownership: AudioOwnership | str | None = None,
   406	    normalization: Sequence[str] = (),
   407	    attachments: Mapping[str, Attachment | Mapping[str, Any]] | None = None,
   408	    backend_fragments: Mapping[str, Mapping[str, Any]] | None = None,
   409	    v1_compatibility: Mapping[str, Any] | None = None,
   410	) -> dict[str, Any]:
   411	    """Assemble additive provenance v2 with protected ownership boundaries.
   412	
   413	    ``engine`` is intentionally the legacy request projection. Routing and
   414	    replay lineage come exclusively from the validated ``RenderPlan`` so a
   415	    hybrid invocation cannot collapse multiple renderer identities. Optional
   416	    v1 fields are accepted only through ``v1_compatibility`` and cannot replace
   417	    any v2 core field.
   418	    """
   419	
   420	    legacy_engine = _require_string(engine, "engine")
   421	    output_path = _require_string(str(output), "output")
   422	    timeline_path = _require_string(str(timeline), "timeline")
   423	    assets_path = None if assets_registry is None else _require_string(
   424	        str(assets_registry), "assets_registry"
   425	    )
   426	    normalized_plan = (
   427	        RenderPlan.from_dict(_json_safe_mapping(plan.to_dict(), label="render plan"))
   428	        if isinstance(plan, RenderPlan)
   429	        else RenderPlan.from_dict(_json_safe_mapping(plan, label="render plan"))
   430	    )
   431	    normalized_segments = [segment.to_dict() for segment in normalized_plan.segments]
   432	    legacy_segments = [
   433	        _legacy_segment_projection(segment) for segment in normalized_plan.segments
   434	    ]
   435	    normalized_normalization = [
   436	        _require_string(item, f"normalization[{index}]")
   437	        for index, item in enumerate(normalization)
   438	    ]
   439	    compatibility = _normalize_v1_compatibility(v1_compatibility)
   440	    resolved_policy = _resolved_policy(normalized_plan)
   441	
   442	    payload: dict[str, Any] = {
   443	        "schema_version": PROVENANCE_SCHEMA_VERSION,
   444	        "engine": legacy_engine,
   445	        "output": output_path,
   446	        "timeline": timeline_path,
   447	        "assets_registry": assets_path,
   448	        "request_digest": normalized_plan.request_digest,
   449	        "requested_policy": normalized_plan.requested_policy,
   450	        "resolved_policy": resolved_policy,
   451	        "routing": _routing_record(
   452	            legacy_engine,
   453	            normalized_plan,
   454	            resolved_policy,
   455	        ),
   456	        "planner": normalized_plan.planner.to_dict(),
   457	        # V1-compatible segment projection: flat {engine, from, to} entries,
   458	        # exactly the shape legacy consumers read from `segments`.
   459	        "segments": legacy_segments,
   460	        # Additive normalized v2 segment records; never overwrite v1 fields.
   461	        "segments_v2": normalized_segments,
   462	        "artifact_profiles": _normalize_artifact_profiles(
   463	            artifact_profiles,
   464	            segments=normalized_plan.segments,
   465	        ),
   466	        "audio_ownership": _normalize_audio_ownership(audio_ownership),
   467	        "normalization": normalized_normalization,
   468	        "finalizer": normalized_plan.finalizer.to_dict(),
   469	        "attachments": _normalize_attachments(attachments),
   470	        "backend_fragments": validate_backend_fragments(backend_fragments),
   471	    }
   472	    payload.update(compatibility)
   473	    return _json_safe_mapping(payload, label="provenance")
   474	
   475	
   476	def assemble_provenance(**kwargs: Any) -> dict[str, Any]:
   477	    """Compatibility spelling for :func:`assemble_provenance_v2`."""
   478	
   479	    return assemble_provenance_v2(**kwargs)
   480	

exec
/bin/zsh -lc "rg -n \"def publish_render_result|output_sha|sha256\" astrid/core/rendering -g '*.py' | head -160; nl -ba astrid/core/rendering/publication.py | sed -n '1,300p' 2>/dev/null || true; nl -ba tests/core/rendering/test_service.py | sed -n '560,650p'; nl -ba tests/core/rendering/test_service.py | sed -n '1540,1665p'; nl -ba tests/core/rendering/test_service.py | sed -n '1760,1845p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 88ms:
astrid/core/rendering/publication.py:20:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/publication.py:202:    recorded_sha256 = payload.get("sha256")
astrid/core/rendering/publication.py:203:    if not isinstance(recorded_sha256, str) or _SHA256_RE.fullmatch(recorded_sha256) is None:
astrid/core/rendering/publication.py:206:        if sha256_file(video) != recorded_sha256:
astrid/core/rendering/publication.py:310:def publish_render_result(
astrid/core/rendering/publication.py:360:        digest = sha256_file(output)
astrid/core/rendering/publication.py:363:        committed_payload["sha256"] = digest
astrid/core/rendering/registry.py:19:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/registry.py:616:            digest = sha256_file(manifest_path)
astrid/core/rendering/registry.py:809:        current_digest = sha256_file(pack.manifest_path)
astrid/core/rendering/provenance.py:10:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/provenance.py:24:    _require_sha256,
astrid/core/rendering/provenance.py:81:                    "sha256": raw_attachment.sha256,
astrid/core/rendering/provenance.py:224:                    "hashed lineage record {profile, sha256, attachments}; "
astrid/core/rendering/provenance.py:287:    allowed = {"profile", "sha256", "attachments", "path"}
astrid/core/rendering/provenance.py:291:    missing = sorted({"profile", "sha256", "attachments"} - raw_keys)
astrid/core/rendering/provenance.py:296:    if raw["sha256"] is None:
astrid/core/rendering/provenance.py:297:        raise ValueError("artifact lineage sha256 is required and must not be null")
astrid/core/rendering/provenance.py:298:    if not isinstance(raw["sha256"], str):
astrid/core/rendering/provenance.py:299:        raise TypeError("artifact lineage sha256 must be a string")
astrid/core/rendering/provenance.py:325:                "sha256": att.sha256,
astrid/core/rendering/provenance.py:327:        att_unknown = sorted(set(att) - {"path", "kind", "sha256"})
astrid/core/rendering/provenance.py:332:        att_missing = sorted({"path", "kind", "sha256"} - set(att))
astrid/core/rendering/provenance.py:337:        if not isinstance(att["sha256"], str):
astrid/core/rendering/provenance.py:338:            raise TypeError(f"attachment {name!r} sha256 must be a string")
astrid/core/rendering/provenance.py:345:            sha256=att["sha256"],
astrid/core/rendering/provenance.py:350:            "sha256": validated.sha256,
astrid/core/rendering/provenance.py:357:        "sha256": _require_sha256(raw["sha256"], "artifact sha256"),
astrid/core/rendering/provenance.py:363:    """One hashed artifact lineage record: profile, sha256, attachments."""
astrid/core/rendering/provenance.py:367:            "sha256": artifact.sha256,
astrid/core/rendering/provenance.py:494:        _require_string(name, "input hash name"): sha256_file(Path(path))
astrid/core/rendering/provenance.py:502:    return sha256_file(Path(path))
astrid/core/rendering/service.py:25:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/service.py:69:_DIRECT_PLANNER_DIGEST = hashlib.sha256(b"astrid.direct/v1").hexdigest()
astrid/core/rendering/service.py:71:_DIRECT_FINALIZER_DIGEST = hashlib.sha256(
astrid/core/rendering/service.py:1012:            {"materialized_timeline": sha256_file(materialized_path)},
astrid/core/rendering/service.py:1773:        token = hashlib.sha256(
astrid/core/rendering/service.py:1819:            name: sha256_file(path)
astrid/core/rendering/artifacts.py:13:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/artifacts.py:205:            declared_sha256=value if isinstance(value, str) else None,
astrid/core/rendering/artifacts.py:213:        actual_hash = sha256_file(path)
astrid/core/rendering/artifacts.py:638:    _verify_hash(path, attachment.sha256, label=f"attachment {key!r}")
astrid/core/rendering/artifacts.py:707:    _verify_hash(video_path, video.sha256, label="primary video")
astrid/core/rendering/assets.py:114:    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
astrid/core/rendering/assets.py:415:                    fetch(url, expected_sha256=entry.get("content_sha256"))
astrid/core/rendering/contracts.py:19:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/contracts.py:252:def _require_sha256(value: Any, label: str) -> str:
astrid/core/rendering/contracts.py:290:        _require_string(key, f"{label} key"): _require_sha256(item, f"{label}[{key!r}]")
astrid/core/rendering/contracts.py:600:    sha256: str
astrid/core/rendering/contracts.py:612:        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "attachment sha256"))
astrid/core/rendering/contracts.py:616:            {"name": self.name, "path": self.path, "kind": self.kind, "sha256": self.sha256}
astrid/core/rendering/contracts.py:622:        required = {"name", "path", "kind", "sha256"}
astrid/core/rendering/contracts.py:628:            sha256=data["sha256"],
astrid/core/rendering/contracts.py:641:        return cls(name=name, path=relative, kind=kind, sha256=sha256_file(resolved))
astrid/core/rendering/contracts.py:672:    sha256: str
astrid/core/rendering/contracts.py:685:        object.__setattr__(self, "sha256", _require_sha256(self.sha256, "video sha256"))
astrid/core/rendering/contracts.py:705:                "sha256": self.sha256,
astrid/core/rendering/contracts.py:715:        required = {"path", "profile", "sha256", "duration_frames"}
astrid/core/rendering/contracts.py:721:            sha256=data["sha256"],
astrid/core/rendering/contracts.py:742:            sha256=sha256_file(resolved),
astrid/core/rendering/contracts.py:1020:            _require_sha256(self.manifest_digest, "planner manifest_digest"),
astrid/core/rendering/contracts.py:1131:            _require_sha256(self.manifest_digest, "renderer manifest_digest"),
astrid/core/rendering/contracts.py:1220:            _require_sha256(self.manifest_digest, "finalizer manifest_digest"),
astrid/core/rendering/contracts.py:1384:            _require_sha256(self.request_digest, "request_digest"),
astrid/core/rendering/asset_cache.py:7:``etag``, ``content_length``, ``content_sha256``, ``fetched_at``,
astrid/core/rendering/asset_cache.py:40:from astrid.core.foundation.hash import sha256_file
astrid/core/rendering/asset_cache.py:242:    message = f"Content drift for {path}: expected sha256 {expected}, got {actual}"
astrid/core/rendering/asset_cache.py:256:def _download_once(url: str, path: Path, expected_sha256: str | None, head_meta: dict[str, str]) -> Path:
astrid/core/rendering/asset_cache.py:268:    actual_sha256 = sha256_file(partial_path)
astrid/core/rendering/asset_cache.py:269:    if expected_sha256 and actual_sha256 != expected_sha256:
astrid/core/rendering/asset_cache.py:270:        raise ContentDriftError(f"Content drift for {url}: expected sha256 {expected_sha256}, got {actual_sha256}")
astrid/core/rendering/asset_cache.py:279:        "content_sha256": actual_sha256,
astrid/core/rendering/asset_cache.py:290:def fetch(url: str, *, expected_sha256: str | None = None, force: bool = False) -> Path:
astrid/core/rendering/asset_cache.py:298:            actual_sha256 = sha256_file(path) if expected_sha256 else None
astrid/core/rendering/asset_cache.py:299:            if expected_sha256 and actual_sha256 != expected_sha256:
astrid/core/rendering/asset_cache.py:300:                refetch = _handle_drift(path, expected_sha256, actual_sha256 or "", allow_refetch=True)
astrid/core/rendering/asset_cache.py:318:                    verify_sha256 = expected_sha256 if _drift_mode() == "strict" else None
astrid/core/rendering/asset_cache.py:319:                    downloaded = _download_once(url, path, verify_sha256, head_meta)
astrid/core/rendering/asset_cache.py:320:                    if expected_sha256:
astrid/core/rendering/asset_cache.py:321:                        actual_sha256 = sha256_file(downloaded)
astrid/core/rendering/asset_cache.py:322:                        if actual_sha256 != expected_sha256:
astrid/core/rendering/asset_cache.py:323:                            _handle_drift(downloaded, expected_sha256, actual_sha256, allow_refetch=False)
astrid/core/rendering/asset_cache.py:327:                    if expected_sha256:
astrid/core/rendering/asset_cache.py:329:                        actual_sha256 = sha256_file(partial_path) if partial_path.exists() else ""
astrid/core/rendering/asset_cache.py:330:                        if _handle_drift(path, expected_sha256, actual_sha256, allow_refetch=False):
astrid/core/rendering/asset_cache.py:337:            verify_sha256 = expected_sha256 if _drift_mode() == "strict" else None
astrid/core/rendering/asset_cache.py:338:            downloaded = _download_once(url, path, verify_sha256, head_meta)
astrid/core/rendering/asset_cache.py:339:            if expected_sha256:
astrid/core/rendering/asset_cache.py:340:                actual_sha256 = sha256_file(downloaded)
astrid/core/rendering/asset_cache.py:341:                if actual_sha256 != expected_sha256:
astrid/core/rendering/asset_cache.py:342:                    _handle_drift(downloaded, expected_sha256, actual_sha256, allow_refetch=False)
astrid/core/rendering/asset_cache.py:424:    if isinstance(entry.get("url"), str) and isinstance(entry.get("content_sha256"), str):
astrid/core/rendering/asset_cache.py:425:        path = fetch(entry["url"], expected_sha256=entry.get("content_sha256"))
astrid/core/rendering/asset_cache.py:431:        path = fetch(entry["url"], expected_sha256=entry.get("content_sha256"))
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
   206	        if sha256_file(video) != recorded_sha256:
   207	            return None
   208	    except OSError:
   209	        return None
   210	    return payload
   211	
   212	
   213	def is_render_result_committed(
   214	    video_path: str | Path,
   215	    *,
   216	    sidecar_path: str | Path | None = None,
   217	) -> bool:
   218	    """Return whether the video-plus-sidecar pair is committed."""
   219	
   220	    return read_committed_provenance(video_path, sidecar_path=sidecar_path) is not None
   221	
   222	
   223	def _previous_pair(candidate: object) -> tuple[Path, Path] | None:
   224	    if isinstance(candidate, Mapping):
   225	        raw_video = candidate.get("out_path", candidate.get("output"))
   226	        raw_sidecar = candidate.get("sidecar_path", candidate.get("sidecar"))
   227	        if raw_video is None:
   228	            return None
   229	        video = _resolved(raw_video)
   230	        return video, _resolved(raw_sidecar or _default_sidecar_path(video))
   231	    if isinstance(candidate, (list, tuple)) and len(candidate) == 2:
   232	        video = _resolved(candidate[0])
   233	        return video, _resolved(candidate[1])
   234	    if isinstance(candidate, (str, os.PathLike)):
   235	        video = _resolved(candidate)
   236	        return video, _resolved(_default_sidecar_path(video))
   237	    return None
   238	
   239	
   240	def _delete_previous_outputs(
   241	    previous_outputs: Iterable[object],
   242	    *,
   243	    live_output: Path,
   244	    timeline: object,
   245	) -> None:
   246	    if not isinstance(timeline, str):
   247	        return
   248	    seen: set[Path] = set()
   249	    for candidate in previous_outputs:
   250	        try:
   251	            pair = _previous_pair(candidate)
   252	        except (OSError, RuntimeError, TypeError, ValueError):
   253	            continue
   254	        if pair is None:
   255	            continue
   256	        video, sidecar = pair
   257	        # Never delete through a symlink: neither the raw video nor the raw
   258	        # sidecar path may be a link (the resolved pair may point elsewhere).
   259	        raw_candidate = candidate.get("out_path", candidate.get("output")) if isinstance(candidate, Mapping) else (candidate[0] if isinstance(candidate, (list, tuple)) and candidate else candidate)
   260	        raw_sidecar_candidate = candidate.get("sidecar_path", candidate.get("sidecar")) if isinstance(candidate, Mapping) else (candidate[1] if isinstance(candidate, (list, tuple)) and len(candidate) == 2 else None)
   261	        try:
   262	            raw_path = Path(raw_candidate).expanduser()
   263	            if _contains_symlink_component(raw_path):
   264	                continue
   265	        except (OSError, TypeError):
   266	            continue
   267	        try:
   268	            # For bare paths the default sidecar is derived from the raw
   269	            # video path; it must be checked unresolved like an explicit one.
   270	            raw_sidecar = (
   271	                Path(raw_sidecar_candidate).expanduser()
   272	                if raw_sidecar_candidate is not None
   273	                else _default_sidecar_path(raw_path)
   274	            )
   275	            if _contains_symlink_component(raw_sidecar):
   276	                continue
   277	        except (OSError, TypeError):
   278	            continue
   279	        if video == live_output or video in seen:
   280	            continue
   281	        seen.add(video)
   282	
   283	        # Never wait while holding the live output lock.  Two concurrent
   284	        # publications for sibling outputs can otherwise deadlock while each
   285	        # tries to clean the other, and a locked candidate is by definition a
   286	        # live render that cleanup must preserve.
   287	        candidate_lock = _lock_for(video)
   288	        try:
   289	            candidate_lock.acquire(timeout=0)
   290	        except (Timeout, OSError):
   291	            continue
   292	        try:
   293	            provenance = read_committed_provenance(video, sidecar_path=sidecar)
   294	            if provenance is None or provenance.get("timeline") != timeline:
   295	                continue
   296	            try:
   297	                # The marker disappears first.  A crash or failure between
   298	                # these unlinks leaves an orphan, never a false committed pair.
   299	                sidecar.unlink()
   300	            except (FileNotFoundError, OSError):
   560	    reason = routing["segment_reasons"]["0"]
   561	    assert "rendering.ffmpeg" in reason
   562	    assert "rejected" in reason
   563	
   564	
   565	def test_legacy_ffmpeg_is_strict(tmp_path: Path) -> None:
   566	    transport = FakeTransport()
   567	    service = _service(tmp_path, transport)
   568	
   569	    service.render_request(
   570	        _request(tmp_path),
   571	        selector="ffmpeg",
   572	        out_path=tmp_path / "legacy-ffmpeg.mp4",
   573	    )
   574	
   575	    assert transport.calls == [
   576	        ("support", "rendering.ffmpeg"),
   577	        ("render", "rendering.ffmpeg"),
   578	    ]
   579	
   580	
   581	def test_hybrid_selects_planner_and_executes_its_segment(tmp_path: Path) -> None:
   582	    transport = FakeTransport()
   583	    transport.plan = _plan("fixture.window")
   584	    service = _service(
   585	        tmp_path,
   586	        transport,
   587	        renderer_ids=("fixture.window",),
   588	        planner_ids=("rendering.legacy_hybrid",),
   589	    )
   590	
   591	    service.render_request(
   592	        _request(tmp_path),
   593	        selector="hybrid",
   594	        out_path=tmp_path / "hybrid.mp4",
   595	    )
   596	
   597	    assert transport.calls[:2] == [
   598	        ("support", "rendering.legacy_hybrid"),
   599	        ("plan", "rendering.legacy_hybrid"),
   600	    ]
   601	    assert ("render", "fixture.window") in transport.calls
   602	    # The plan pins the ffmpeg finalizer; even a single-segment hybrid plan
   603	    # runs it (profile/audio normalization is the finalizer's contract).
   604	    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
   605	
   606	
   607	def test_planned_window_is_materialized_for_full_timeline_renderer(
   608	    tmp_path: Path,
   609	) -> None:
   610	    transport = FakeTransport()
   611	    transport.plan = _plan("fixture.full")
   612	    renderers = RendererRegistry(
   613	        [
   614	            _candidate(
   615	                tmp_path,
   616	                "fixture.full",
   617	                "renderer",
   618	                capabilities={
   619	                    "supports_full_timeline": True,
   620	                    "supports_windows": False,
   621	                },
   622	            )
   623	        ]
   624	    )
   625	    planners = PlannerRegistry(
   626	        [_candidate(tmp_path, "rendering.legacy_hybrid", "planner")]
   627	    )
   628	    finalizers = FinalizerRegistry(
   629	        [_candidate(tmp_path, "rendering.ffmpeg-finalizer", "finalizer")]
   630	    )
   631	    service = RenderService(
   632	        registries=(renderers, planners, finalizers),
   633	        transport=transport,
   634	        validator=lambda result, **_kwargs: result,
   635	    )
   636	    output = tmp_path / "materialized-window.mp4"
   637	    request = _request(tmp_path)
   638	
   639	    service.render_request(request, selector="hybrid", out_path=output)
   640	
   641	    renderer_payloads = [
   642	        payload
   643	        for verb, backend, payload in transport.payloads
   644	        if backend == "fixture.full" and verb in {"support", "render"}
   645	    ]
   646	    assert len(renderer_payloads) == 2
   647	    assert all(payload["window"] is None for payload in renderer_payloads)
   648	    assert all(
   649	        payload["timeline_path"] != request.timeline_path
   650	        for payload in renderer_payloads
  1540	    sidecars = list(tmp_path.glob("*.provenance.json"))
  1541	    assert sidecars == [Path(f"{output}.provenance.json")]
  1542	    payload = json.loads(sidecars[0].read_text(encoding="utf-8"))
  1543	    assert payload["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
  1544	    assert payload["output"] == str(output.resolve())
  1545	    assert payload["routing"]["requested_engine"] == expected_engine
  1546	    assert payload["routing"]["auto_route"] is False
  1547	    assert payload["audio_ownership"] == "none"
  1548	    for _verb, backend, payload_data in transport.payloads:
  1549	        if backend in backend_config:
  1550	            assert payload_data["backend_config"][backend] == backend_config[backend]
  1551	    if expect_finalize:
  1552	        assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
  1553	    else:
  1554	        assert not any(verb == "finalize" for verb, _backend in transport.calls)
  1555	    assert not list(tmp_path.glob(".*.render-service-*"))
  1556	
  1557	
  1558	def test_raw_mixed_plan_routes_windows_and_aligns_segment_provenance(
  1559	    tmp_path: Path,
  1560	) -> None:
  1561	    transport = FakeTransport()
  1562	    request = _mixed_plan(
  1563	        tmp_path,
  1564	        transport,
  1565	        config={
  1566	            "simple_renderers": ["raw_command.renderer"],
  1567	            "complex_renderers": ["rendering.remotion"],
  1568	        },
  1569	    )
  1570	    service = _mixed_service(tmp_path, transport)
  1571	    output = tmp_path / "mixed.mp4"
  1572	
  1573	    service.render_request(request, selector="hybrid", out_path=output)
  1574	
  1575	    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
  1576	    assert render_calls == [
  1577	        "raw_command.renderer",
  1578	        "rendering.remotion",
  1579	        "raw_command.renderer",
  1580	    ]
  1581	    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
  1582	    payload = _sidecar(output)
  1583	    segments = payload["segments_v2"]
  1584	    assert [segment["renderer"]["id"] for segment in segments] == [
  1585	        "raw_command.renderer",
  1586	        "rendering.remotion",
  1587	        "raw_command.renderer",
  1588	    ]
  1589	    windows = [
  1590	        (segment["window"]["start_frame"], segment["window"]["end_frame"])
  1591	        for segment in segments
  1592	    ]
  1593	    assert windows[0][0] == 0
  1594	    assert windows[-1][1] == transport.plan.total_frames
  1595	    assert all(left[1] == right[0] for left, right in zip(windows, windows[1:]))
  1596	    assert all("timeline" in segment["input_hashes"] for segment in segments)
  1597	    assert payload["finalizer"]["id"] == "rendering.ffmpeg-finalizer"
  1598	    assert payload["routing"]["requested_engine"] == "hybrid"
  1599	
  1600	
  1601	def test_raw_mixed_plan_executes_deterministic_raw_fixture_window(
  1602	    tmp_path: Path,
  1603	) -> None:
  1604	    transport = _RawFixtureTransport()
  1605	    request = _mixed_plan(
  1606	        tmp_path,
  1607	        transport,
  1608	        config={
  1609	            "simple_renderers": ["raw_command.renderer"],
  1610	            "complex_renderers": ["rendering.remotion"],
  1611	        },
  1612	    )
  1613	    service = _mixed_service(tmp_path, transport)
  1614	    output = tmp_path / "mixed-real.mp4"
  1615	
  1616	    service.render_request(request, selector="hybrid", out_path=output)
  1617	
  1618	    render_calls = [backend for verb, backend in transport.calls if verb == "render"]
  1619	    assert render_calls == [
  1620	        "raw_command.renderer",
  1621	        "rendering.remotion",
  1622	        "raw_command.renderer",
  1623	    ]
  1624	    assert ("finalize", "rendering.ffmpeg-finalizer") in transport.calls
  1625	    payload = _sidecar(output)
  1626	    segments = payload["segments_v2"]
  1627	    assert [segment["renderer"]["id"] for segment in segments] == [
  1628	        "raw_command.renderer",
  1629	        "rendering.remotion",
  1630	        "raw_command.renderer",
  1631	    ]
  1632	    raw_windows = [
  1633	        segment["window"]
  1634	        for segment in segments
  1635	        if segment["renderer"]["id"] == "raw_command.renderer"
  1636	    ]
  1637	    assert len(raw_windows) == 2
  1638	    assert all(
  1639	        segment["window"]["end_frame"] - segment["window"]["start_frame"] > 0
  1640	        for segment in segments
  1641	    )
  1642	    # The raw fixture really rendered its windows: real mp4 bytes with the
  1643	    # planned frame count in the committed artifact profile.
  1644	    assert output.is_file()
  1645	    assert output.read_bytes().startswith(b"finalize:rendering.ffmpeg-finalizer")
  1646	
  1647	
  1648	@pytest.mark.parametrize(
  1649	    ("selector", "plan_segments", "ownership", "expected", "completer"),
  1650	    [
  1651	        ("rendering.remotion", None, AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
  1652	        ("rendering.ffmpeg", None, AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
  1653	        ("rendering.remotion", None, AudioOwnership.NONE, AudioOwnership.NONE, False),
  1654	        ("rendering.ffmpeg", None, AudioOwnership.NONE, AudioOwnership.NONE, False),
  1655	        ("rendering.remotion", None, AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
  1656	        ("rendering.ffmpeg", None, AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
  1657	        ("hybrid", (10,), AudioOwnership.RENDERED, AudioOwnership.RENDERED, False),
  1658	        ("hybrid", (10,), AudioOwnership.NONE, AudioOwnership.NONE, False),
  1659	        ("hybrid", (10,), AudioOwnership.PASSTHROUGH, AudioOwnership.RENDERED, True),
  1660	    ],
  1661	    ids=[
  1662	        "remotion-rendered",
  1663	        "ffmpeg-rendered",
  1664	        "remotion-none",
  1665	        "ffmpeg-none",
  1760	        service.render_request(
  1761	            _request(tmp_path), selector="rendering.ffmpeg", out_path=output
  1762	        )
  1763	
  1764	    assert not output.exists()
  1765	    assert not list(tmp_path.glob("*.provenance.json"))
  1766	    assert not list(tmp_path.glob(".*.render-service-*"))
  1767	
  1768	
  1769	def test_renderer_attachments_survive_validation_into_committed_provenance(
  1770	    tmp_path: Path,
  1771	) -> None:
  1772	    transport = FakeTransport()
  1773	    transport.render_attachments["rendering.ffmpeg"] = {
  1774	        "storyboard.png": b"png-bytes",
  1775	        "captions.srt": b"srt-bytes",
  1776	    }
  1777	    service = _service(tmp_path, transport)
  1778	    output = tmp_path / "attachments.mp4"
  1779	
  1780	    service.render_request(
  1781	        _request(tmp_path), selector="rendering.ffmpeg", out_path=output
  1782	    )
  1783	
  1784	    payload = _sidecar(output)
  1785	    assert set(payload["attachments"]) == {"storyboard.png", "captions.srt"}
  1786	    assert payload["attachments"]["storyboard.png"]["sha256"] == hashlib.sha256(
  1787	        b"png-bytes"
  1788	    ).hexdigest()
  1789	    assert payload["attachments"]["storyboard.png"]["kind"] == "fixture"
  1790	    assert payload["attachments"]["storyboard.png"]["path"].endswith(
  1791	        "storyboard.png"
  1792	    )
  1793	    assert len(payload["artifact_profiles"]) == 1
  1794	    assert set(payload["artifact_profiles"][0]["attachments"]) == {
  1795	        "storyboard.png",
  1796	        "captions.srt",
  1797	    }
  1798	
  1799	
  1800	def test_finalizer_preserves_segment_attachments_and_adds_its_own(
  1801	    tmp_path: Path,
  1802	) -> None:
  1803	    transport = FakeTransport()
  1804	    transport.render_attachments["fixture.window"] = [
  1805	        {"segment-a.txt": b"first-segment"},
  1806	        {"segment-b.txt": b"second-segment"},
  1807	    ]
  1808	    transport.finalize_attachments = {"final-note.txt": b"final"}
  1809	    transport.plan = _plan("fixture.window", segment_frames=(5, 5))
  1810	    service = _service(
  1811	        tmp_path,
  1812	        transport,
  1813	        renderer_ids=("fixture.window",),
  1814	        planner_ids=("rendering.legacy_hybrid",),
  1815	    )
  1816	    output = tmp_path / "finalized-attachments.mp4"
  1817	
  1818	    service.render_request(_request(tmp_path), selector="hybrid", out_path=output)
  1819	
  1820	    payload = _sidecar(output)
  1821	    assert set(payload["attachments"]) == {
  1822	        "segment-a.txt",
  1823	        "segment-b.txt",
  1824	        "final-note.txt",
  1825	    }
  1826	    assert len(payload["artifact_profiles"]) == 2
  1827	    assert set(payload["artifact_profiles"][0]["attachments"]) == {"segment-a.txt"}
  1828	    assert set(payload["artifact_profiles"][1]["attachments"]) == {"segment-b.txt"}
  1829	
  1830	
  1831	def test_audio_completer_dropping_attachments_is_rejected(tmp_path: Path) -> None:
  1832	    transport = FakeTransport()
  1833	    transport.render_attachments["rendering.ffmpeg"] = {"must-survive.txt": b"x"}
  1834	
  1835	    def bad_completer(result: RenderResult, **_kwargs: Any) -> RenderResult:
  1836	        return replace(
  1837	            result,
  1838	            video=replace(
  1839	                result.video,
  1840	                profile=_profile(audio=True),
  1841	                audio=AudioOwnership.RENDERED,
  1842	                attachments={},
  1843	            ),
  1844	            audio_ownership=AudioOwnership.RENDERED,
  1845	        )

exec
/bin/zsh -lc "rg -n \"output_name|output_path\" astrid/packs/rendering/backends/remotion/run.py astrid/packs/rendering/backends/ffmpeg/run.py astrid/packs/rendering/finalizers/ffmpeg/run.py | head -140; rg -n \"artifact_profiles.*sha|artifact_profiles.*path|segment-0000|direct-finalize|pinned.finalizer\" tests/core/rendering/test_service.py docs/contracts/render-backend-v1.md | head -160; nl -ba astrid/core/rendering/service.py | sed -n '1060,1160p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
astrid/packs/rendering/backends/ffmpeg/run.py:103:        output_name=Path(out_path).name,
astrid/packs/rendering/backends/ffmpeg/run.py:557:    output_path = outputs_dir / request.output_name
astrid/packs/rendering/backends/ffmpeg/run.py:559:    output_path.unlink(missing_ok=True)
astrid/packs/rendering/backends/ffmpeg/run.py:562:            audio_reactive_colour.render(specialization_spec, output_path)
astrid/packs/rendering/backends/ffmpeg/run.py:566:            probe = ffprobe_metadata_strict(output_path)
astrid/packs/rendering/backends/ffmpeg/run.py:580:            output_path,
astrid/packs/rendering/backends/ffmpeg/run.py:624:            path=output_path,
astrid/packs/rendering/backends/ffmpeg/run.py:648:        output_path.unlink(missing_ok=True)
astrid/packs/rendering/backends/remotion/run.py:210:def _registry_output_paths(project_dir: Path) -> list[Path]:
astrid/packs/rendering/backends/remotion/run.py:229:    return all(path.exists() for path in _registry_output_paths(project_dir))
astrid/packs/rendering/backends/remotion/run.py:1082:    output_path = outputs_dir / request.output_name
astrid/packs/rendering/backends/remotion/run.py:1112:                prefix=f".{request.output_name}.remotion-",
astrid/packs/rendering/backends/remotion/run.py:1116:        staged_video = Path(private_tmp) / request.output_name
astrid/packs/rendering/backends/remotion/run.py:1121:            provenance_out_path=output_path,
astrid/packs/rendering/backends/remotion/run.py:1127:        output_path.unlink(missing_ok=True)
astrid/packs/rendering/backends/remotion/run.py:1128:        os.replace(staged_video, output_path)
astrid/packs/rendering/backends/remotion/run.py:1132:            output_path,
astrid/packs/rendering/backends/remotion/run.py:1144:            path=output_path,
astrid/packs/rendering/backends/remotion/run.py:1147:            duration_frames=_duration_frames(output_path, declared_profile),
astrid/packs/rendering/backends/remotion/run.py:1173:        output_path.unlink(missing_ok=True)
astrid/packs/rendering/finalizers/ffmpeg/run.py:115:def _safe_protocol_output_path(workspace: Path, output_name: str) -> Path:
astrid/packs/rendering/finalizers/ffmpeg/run.py:153:    candidate = resolved_dir / output_name
astrid/packs/rendering/finalizers/ffmpeg/run.py:159:            details={"output": output_name},
astrid/packs/rendering/finalizers/ffmpeg/run.py:166:            details={"output": output_name},
astrid/packs/rendering/finalizers/ffmpeg/run.py:504:    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py:628:    argv.extend(["-f", "mp4", str(output_path)])
astrid/packs/rendering/finalizers/ffmpeg/run.py:634:    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py:668:    argv.extend(["-f", "mp4", str(output_path)])
astrid/packs/rendering/finalizers/ffmpeg/run.py:688:    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py:699:    output_path = output_path.absolute()
astrid/packs/rendering/finalizers/ffmpeg/run.py:700:    output_path.parent.mkdir(parents=True, exist_ok=True)
astrid/packs/rendering/finalizers/ffmpeg/run.py:704:        prefix=f".{output_path.name}.ffmpeg-finalizer-",
astrid/packs/rendering/finalizers/ffmpeg/run.py:705:        dir=str(output_path.parent),
astrid/packs/rendering/finalizers/ffmpeg/run.py:748:        staged_output = tmp_dir / "final" / output_path.name
astrid/packs/rendering/finalizers/ffmpeg/run.py:764:                details={"output": output_path.name},
astrid/packs/rendering/finalizers/ffmpeg/run.py:766:        os.replace(staged_output, output_path)
astrid/packs/rendering/finalizers/ffmpeg/run.py:855:    output_path: Path,
astrid/packs/rendering/finalizers/ffmpeg/run.py:936:            Path(output_path),
astrid/packs/rendering/finalizers/ffmpeg/run.py:942:        final_probe = inspect(Path(output_path))
astrid/packs/rendering/finalizers/ffmpeg/run.py:964:            Path(output_path).unlink(missing_ok=True)
astrid/packs/rendering/finalizers/ffmpeg/run.py:1247:    output_path = _safe_protocol_output_path(workspace, request.output_name)
astrid/packs/rendering/finalizers/ffmpeg/run.py:1252:        prefix=f".{output_path.name}.ffmpeg-finalizer-recovery-",
astrid/packs/rendering/finalizers/ffmpeg/run.py:1253:        dir=str(output_path.parent),
astrid/packs/rendering/finalizers/ffmpeg/run.py:1257:        if output_path.is_file()
astrid/packs/rendering/finalizers/ffmpeg/run.py:1264:            shutil.copy2(output_path, previous_output)
astrid/packs/rendering/finalizers/ffmpeg/run.py:1266:            prefix=f".{output_path.name}.ffmpeg-finalizer-normalize-",
astrid/packs/rendering/finalizers/ffmpeg/run.py:1267:            dir=str(output_path.parent),
astrid/packs/rendering/finalizers/ffmpeg/run.py:1336:                output_path,
astrid/packs/rendering/finalizers/ffmpeg/run.py:1344:            path=output_path,
astrid/packs/rendering/finalizers/ffmpeg/run.py:1387:                os.replace(previous_output, output_path)
astrid/packs/rendering/finalizers/ffmpeg/run.py:1388:            elif published or output_path.exists():
astrid/packs/rendering/finalizers/ffmpeg/run.py:1389:                output_path.unlink(missing_ok=True)
tests/core/rendering/test_service.py:2213:    assert payload["artifact_profiles"][0]["path"].endswith("segment-0000.mp4")
tests/core/rendering/test_service.py:2216:def test_direct_render_with_pinned_finalizer_records_both_fragments(
tests/core/rendering/test_service.py:2229:    output = tmp_path / "direct-finalize.mp4"
  1060	        *,
  1061	        start: Fraction,
  1062	        end: Fraction,
  1063	        window: FrameWindow,
  1064	    ) -> dict[str, Any] | None:
  1065	        clip_start = cls._timeline_number(clip.get("at", 0), "clip.at")
  1066	        clip_end = cls._clip_end(clip, clip_start=clip_start)
  1067	        visible_start = max(clip_start, start)
  1068	        visible_end = min(clip_end, end)
  1069	        if visible_end <= visible_start:
  1070	            return None
  1071	
  1072	        result = dict(clip)
  1073	        result["at"] = float(visible_start - start)
  1074	        result["id"] = (
  1075	            f"{clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
  1076	        )
  1077	        if clip.get("clipType", "media") == "media":
  1078	            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
  1079	            if speed <= 0:
  1080	                raise ValueError("clip.speed must be positive")
  1081	            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
  1082	            source_from += (visible_start - clip_start) * speed
  1083	            result["from"] = float(source_from)
  1084	            result["to"] = float(
  1085	                source_from + (visible_end - visible_start) * speed
  1086	            )
  1087	        elif isinstance(clip.get("hold"), (int, float)) and not isinstance(
  1088	            clip.get("hold"), bool
  1089	        ):
  1090	            result["hold"] = float(visible_end - visible_start)
  1091	        return result
  1092	
  1093	    @classmethod
  1094	    def _clip_end(
  1095	        cls, clip: Mapping[str, Any], *, clip_start: Fraction
  1096	    ) -> Fraction:
  1097	        if clip.get("clipType", "media") == "media":
  1098	            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
  1099	            if "to" not in clip:
  1100	                raise ValueError("media clip must declare a source to bound")
  1101	            source_to = cls._timeline_number(clip["to"], "clip.to")
  1102	            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
  1103	            if source_from < 0 or source_to <= source_from or speed <= 0:
  1104	                raise ValueError("media clip must have positive bounds and speed")
  1105	            return clip_start + (source_to - source_from) / speed
  1106	        hold = clip.get("hold")
  1107	        if isinstance(hold, (int, float)) and not isinstance(hold, bool):
  1108	            return clip_start + max(Fraction(0), cls._timeline_number(hold, "clip.hold"))
  1109	        if isinstance(clip.get("to"), (int, float)) and not isinstance(
  1110	            clip.get("to"), bool
  1111	        ):
  1112	            return cls._timeline_number(clip["to"], "clip.to")
  1113	        return clip_start
  1114	
  1115	    @staticmethod
  1116	    def _timeline_number(value: Any, label: str) -> Fraction:
  1117	        if isinstance(value, bool) or not isinstance(value, (int, float)):
  1118	            raise TypeError(f"{label} must be a finite number")
  1119	        if not math.isfinite(float(value)):
  1120	            raise ValueError(f"{label} must be finite")
  1121	        return Fraction(str(value))
  1122	
  1123	    @staticmethod
  1124	    def _validate_segment_duration(
  1125	        result: RenderResult,
  1126	        *,
  1127	        segment: RenderSegment,
  1128	        canonical_profile: Any,
  1129	        backend: str,
  1130	    ) -> None:
  1131	        RenderService._validate_planned_duration(
  1132	            result,
  1133	            planned_frames=segment.window.duration_frames,
  1134	            canonical_profile=canonical_profile,
  1135	            backend=backend,
  1136	            label="renderer artifact",
  1137	        )
  1138	
  1139	    @staticmethod
  1140	    def _validate_planned_duration(
  1141	        result: RenderResult,
  1142	        *,
  1143	        planned_frames: int,
  1144	        canonical_profile: Any,
  1145	        backend: str,
  1146	        label: str,
  1147	    ) -> None:
  1148	        artifact_seconds = Fraction(
  1149	            result.video.duration_frames, 1
  1150	        ) / Fraction(*result.video.profile.fps_rational)
  1151	        canonical_fps = Fraction(*canonical_profile.fps_rational)
  1152	        planned_seconds = Fraction(planned_frames, 1) / canonical_fps
  1153	        delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
  1154	        if delta_frames <= canonical_profile.duration_tolerance:
  1155	            return
  1156	        raise_invalid_artifact_error(
  1157	            backend=backend,
  1158	            message=f"{label} duration does not match its planned frame window",
  1159	            recovery_command="rerender the exact planned segment window and retry",
  1160	            details={

exec
/bin/zsh -lc "nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '1230,1405p'; nl -ba astrid/packs/rendering/finalizers/ffmpeg/run.py | sed -n '680,780p'; nl -ba astrid/core/rendering/service.py | sed -n '700,790p'" in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 0ms:
  1230	        raise ValueError(
  1231	            f"finalize request selects {request.plan.finalizer.id!r}, not {BACKEND_ID!r}"
  1232	        )
  1233	    faststart, config_reasons = _config(request.backend_config)
  1234	    if config_reasons:
  1235	        raise ValueError("; ".join(config_reasons))
  1236	
  1237	    # This loop completes in full before the first assembly subprocess starts.
  1238	    prepared = _preflight_segments(request, workspace=workspace)
  1239	    ownership = _final_audio_ownership(request)
  1240	    target_profile = (
  1241	        request.plan.profile
  1242	        if ownership is AudioOwnership.RENDERED
  1243	        else _profile_without_audio(request.plan.profile)
  1244	    )
  1245	    assembly_profile = _assembly_profile(target_profile, prepared)
  1246	    _validate_target_profile(assembly_profile)
  1247	    output_path = _safe_protocol_output_path(workspace, request.output_name)
  1248	    total_frames = sum(
  1249	        segment.window.duration_frames for segment in request.plan.segments
  1250	    )
  1251	    recovery_tmp = TemporaryDirectory(
  1252	        prefix=f".{output_path.name}.ffmpeg-finalizer-recovery-",
  1253	        dir=str(output_path.parent),
  1254	    )
  1255	    previous_output = (
  1256	        Path(recovery_tmp.name) / "previous-output.mp4"
  1257	        if output_path.is_file()
  1258	        else None
  1259	    )
  1260	    published = False
  1261	    assembly_started = False
  1262	    try:
  1263	        if previous_output is not None:
  1264	            shutil.copy2(output_path, previous_output)
  1265	        with TemporaryDirectory(
  1266	            prefix=f".{output_path.name}.ffmpeg-finalizer-normalize-",
  1267	            dir=str(output_path.parent),
  1268	        ) as normalized_tmp_text:
  1269	            normalized_tmp = Path(normalized_tmp_text)
  1270	            normalized_prepared: list[_PreparedSegment] = []
  1271	            normalization: list[str] = []
  1272	            for segment in prepared:
  1273	                differences = _profile_differences(segment.profile, assembly_profile)
  1274	                if not differences:
  1275	                    normalized_prepared.append(segment)
  1276	                    continue
  1277	                normalization.extend(
  1278	                    _normalization_record(segment.index, difference)
  1279	                    for difference in differences
  1280	                )
  1281	                normalized_path = normalized_tmp / f"segment-{segment.index:04d}.mp4"
  1282	                normalized_path.parent.mkdir(parents=True, exist_ok=True)
  1283	                _run_checked(
  1284	                    execute,
  1285	                    build_normalize_command(
  1286	                        segment,
  1287	                        normalized_path,
  1288	                        target_profile=assembly_profile,
  1289	                        differences=differences,
  1290	                        faststart=faststart,
  1291	                    ),
  1292	                )
  1293	                if not normalized_path.is_file() or normalized_path.stat().st_size <= 0:
  1294	                    raise_invalid_artifact_error(
  1295	                        backend=BACKEND_ID,
  1296	                        message=(
  1297	                            f"FFmpeg did not produce normalized segment[{segment.index}]"
  1298	                        ),
  1299	                        recovery_command="rerun finalization in a fresh invocation workspace",
  1300	                        details={"segment_index": segment.index},
  1301	                    )
  1302	                normalized_prepared.append(
  1303	                    _PreparedSegment(
  1304	                        index=segment.index,
  1305	                        path=normalized_path,
  1306	                        profile=assembly_profile,
  1307	                        audio=ownership,
  1308	                        duration_frames=segment.duration_frames,
  1309	                    )
  1310	                )
  1311	            effective_profile = _probe_normalized_segments(
  1312	                normalized_prepared,
  1313	                target_profile=assembly_profile,
  1314	            )
  1315	            for segment in prepared:
  1316	                if not _profile_differences(segment.profile, assembly_profile):
  1317	                    continue
  1318	                existing = set(normalization)
  1319	                for difference in _profile_differences(
  1320	                    segment.profile,
  1321	                    effective_profile,
  1322	                ):
  1323	                    record = _normalization_record(segment.index, difference)
  1324	                    if record not in existing:
  1325	                        normalization.append(record)
  1326	                        existing.add(record)
  1327	            normalized_prepared = [
  1328	                replace(segment, profile=effective_profile)
  1329	                for segment in normalized_prepared
  1330	            ]
  1331	            # The prepared list now has a uniform canonical profile, so this
  1332	            # call performs only the concat-demuxer stream-copy assembly.
  1333	            assembly_started = True
  1334	            extra_normalization = _assemble_prepared_segments(
  1335	                normalized_prepared,
  1336	                output_path,
  1337	                target_profile=effective_profile,
  1338	                faststart=faststart,
  1339	                runner=execute,
  1340	            )
  1341	            published = True
  1342	            normalization.extend(extra_normalization)
  1343	        video = VideoArtifact.from_file(
  1344	            path=output_path,
  1345	            workspace_root=workspace,
  1346	            profile=effective_profile,
  1347	            duration_frames=total_frames,
  1348	            audio=ownership,
  1349	            attachments=request.expected_attachments,
  1350	        )
  1351	        result = RenderResult(
  1352	            schema_version=SCHEMA_VERSION,
  1353	            video=video,
  1354	            audio_ownership=ownership,
  1355	            backend_fragments={
  1356	                BACKEND_ID: {
  1357	                    "finalizer_kind": "ffmpeg",
  1358	                    "finalizer_version": BACKEND_VERSION,
  1359	                    "segment_count": len(prepared),
  1360	                    "stream_copied_segments": [
  1361	                        segment.index
  1362	                        for segment in prepared
  1363	                        if not _profile_differences(segment.profile, assembly_profile)
  1364	                    ],
  1365	                    "normalized_segments": [
  1366	                        segment.index
  1367	                        for segment in prepared
  1368	                        if _profile_differences(segment.profile, assembly_profile)
  1369	                    ],
  1370	                    "audio_mode": ownership.value,
  1371	                }
  1372	            },
  1373	            normalization=normalization,
  1374	            logs=[],
  1375	            metadata=request.metadata,
  1376	        )
  1377	        request.validate_final_result(result)
  1378	        validate_render_result(
  1379	            result,
  1380	            expected_profile=request.plan.profile,
  1381	            workspace_root=workspace,
  1382	        )
  1383	        return result
  1384	    except BaseException:
  1385	        if assembly_started:
  1386	            if previous_output is not None and previous_output.is_file():
  1387	                os.replace(previous_output, output_path)
  1388	            elif published or output_path.exists():
  1389	                output_path.unlink(missing_ok=True)
  1390	        raise
  1391	    finally:
  1392	        recovery_tmp.cleanup()
  1393	
  1394	
  1395	def _load_finalize_request(path: Path) -> FinalizeRequest:
  1396	    payload = json.loads(path.read_text(encoding="utf-8"))
  1397	    if not isinstance(payload, Mapping):
  1398	        raise TypeError("finalize request must contain a JSON object")
  1399	    return FinalizeRequest.from_dict(payload)
  1400	
  1401	
  1402	def _load_support_request(path: Path) -> RenderRequest:
  1403	    payload = json.loads(path.read_text(encoding="utf-8"))
  1404	    if not isinstance(payload, Mapping):
  1405	        raise TypeError("support request must contain a JSON object")
   680	
   681	
   682	def _run_checked(runner: Runner, argv: list[str]) -> None:
   683	    runner(argv, check=True)
   684	
   685	
   686	def _assemble_prepared_segments(
   687	    segments: Sequence[_PreparedSegment],
   688	    output_path: Path,
   689	    *,
   690	    target_profile: RenderProfile,
   691	    faststart: bool,
   692	    runner: Runner,
   693	) -> list[str]:
   694	    """Normalize incompatible segments and atomically assemble the output."""
   695	
   696	    if not segments:
   697	        raise ValueError("at least one segment is required for finalization")
   698	    _validate_target_profile(target_profile)
   699	    output_path = output_path.absolute()
   700	    output_path.parent.mkdir(parents=True, exist_ok=True)
   701	    normalization: list[str] = []
   702	
   703	    with TemporaryDirectory(
   704	        prefix=f".{output_path.name}.ffmpeg-finalizer-",
   705	        dir=str(output_path.parent),
   706	    ) as tmp_text:
   707	        tmp_dir = Path(tmp_text)
   708	        concat_paths: list[Path] = []
   709	        for segment in segments:
   710	            differences = _profile_differences(segment.profile, target_profile)
   711	            if not differences:
   712	                concat_paths.append(segment.path)
   713	                continue
   714	            normalization.extend(
   715	                _normalization_record(segment.index, difference)
   716	                for difference in differences
   717	            )
   718	            normalized_path = (
   719	                tmp_dir / "normalized" / f"segment-{segment.index:04d}.mp4"
   720	            )
   721	            normalized_path.parent.mkdir(parents=True, exist_ok=True)
   722	            command = build_normalize_command(
   723	                segment,
   724	                normalized_path,
   725	                target_profile=target_profile,
   726	                differences=differences,
   727	                faststart=faststart,
   728	            )
   729	            _run_checked(runner, command)
   730	            if not normalized_path.is_file() or normalized_path.stat().st_size <= 0:
   731	                raise_invalid_artifact_error(
   732	                    backend=BACKEND_ID,
   733	                    message=(
   734	                        f"FFmpeg did not produce normalized segment[{segment.index}]"
   735	                    ),
   736	                    recovery_command="rerun finalization in a fresh invocation workspace",
   737	                    details={"segment_index": segment.index},
   738	                )
   739	            concat_paths.append(normalized_path)
   740	
   741	        list_path = tmp_dir / "segments.ffconcat"
   742	        list_path.write_text(
   743	            "ffconcat version 1.0\n"
   744	            + "\n".join(_concat_file_line(path) for path in concat_paths)
   745	            + "\n",
   746	            encoding="utf-8",
   747	        )
   748	        staged_output = tmp_dir / "final" / output_path.name
   749	        staged_output.parent.mkdir(parents=True, exist_ok=True)
   750	        _run_checked(
   751	            runner,
   752	            build_concat_command(
   753	                list_path,
   754	                staged_output,
   755	                target_profile=target_profile,
   756	                faststart=faststart,
   757	            ),
   758	        )
   759	        if not staged_output.is_file() or staged_output.stat().st_size <= 0:
   760	            raise_invalid_artifact_error(
   761	                backend=BACKEND_ID,
   762	                message="FFmpeg did not produce a finalized video",
   763	                recovery_command="rerun finalization in a fresh invocation workspace",
   764	                details={"output": output_path.name},
   765	            )
   766	        os.replace(staged_output, output_path)
   767	    return normalization
   768	
   769	
   770	def _duration_fraction(probe: MediaProbe) -> Fraction:
   771	    if probe.duration_rational is not None:
   772	        try:
   773	            duration = Fraction(*probe.duration_rational)
   774	        except (TypeError, ValueError, ZeroDivisionError) as exc:
   775	            raise MediaProbeError("ffprobe returned an invalid rational duration") from exc
   776	    elif probe.duration_seconds is not None:
   777	        try:
   778	            duration = Fraction(str(probe.duration_seconds))
   779	        except (ValueError, ZeroDivisionError) as exc:
   780	            raise MediaProbeError("ffprobe returned an invalid duration") from exc
   700	            "winner",
   701	            requested_id=requested_id,
   702	            resolved_id=(
   703	                candidate.id if candidate is not None else evidence.get("resolved_id")
   704	            ),
   705	            priority=evidence.get("priority_index", evidence.get("priority")),
   706	        )
   707	        eligibility = (
   708	            candidate.eligibility.to_dict()
   709	            if candidate is not None
   710	            else evidence.get("eligibility", {})
   711	        )
   712	        self._observe(
   713	            "eligibility",
   714	            requested_id=requested_id,
   715	            eligible=(
   716	                candidate.execution_eligible
   717	                if candidate is not None
   718	                else evidence.get("execution_eligible", evidence.get("eligible", False))
   719	            ),
   720	            evidence=eligibility,
   721	        )
   722	
   723	    def _support(
   724	        self,
   725	        candidate: RenderingCandidate[Any],
   726	        *,
   727	        request: RenderRequest,
   728	        workspace: Path,
   729	        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
   730	    ) -> SupportReport:
   731	        manifest = candidate.manifest
   732	        projected = request.for_backend(candidate.id)
   733	        self._observe("support", backend=candidate.id)
   734	        if "support" in manifest.operations:
   735	            response = self._run_command(
   736	                candidate,
   737	                "support",
   738	                projected,
   739	                workspace=workspace,
   740	                required_binaries=(),
   741	            )
   742	            if not isinstance(response, SupportReport):
   743	                raise_protocol_error(
   744	                    backend=candidate.id,
   745	                    message="support operation did not return a SupportReport",
   746	                    details={"received_type": type(response).__name__},
   747	                )
   748	            if response.backend != candidate.id:
   749	                raise_protocol_error(
   750	                    backend=candidate.id,
   751	                    message="support report names a different backend",
   752	                    details={"reported_backend": response.backend},
   753	                )
   754	            if response.backend_version != candidate.manifest.version:
   755	                raise_protocol_error(
   756	                    backend=candidate.id,
   757	                    message="support report version does not match its manifest",
   758	                    recovery_command="update the backend command and manifest as one versioned unit",
   759	                    details={
   760	                        "reported_version": response.backend_version,
   761	                        "manifest_version": candidate.manifest.version,
   762	                    },
   763	                )
   764	            return response
   765	        return self._static_support(candidate, projected, registry=registry)
   766	
   767	    def _static_support(
   768	        self,
   769	        candidate: RenderingCandidate[Any],
   770	        request: RenderRequest,
   771	        *,
   772	        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
   773	    ) -> SupportReport:
   774	        capabilities = candidate.manifest.capabilities
   775	        reasons: list[str] = []
   776	        if isinstance(registry, RendererRegistry):
   777	            support_key = (
   778	                "supports_windows"
   779	                if request.window is not None
   780	                else "supports_full_timeline"
   781	            )
   782	            if capabilities.get(support_key) is not True:
   783	                mode = "frame windows" if request.window is not None else "full timelines"
   784	                reasons.append(
   785	                    f"renderer does not declare static support for {mode}"
   786	                )
   787	
   788	            ownership = capabilities.get("audio_ownership")
   789	            if request.audio is not None:
   790	                if not isinstance(ownership, list):

codex
The core invariant now holds in both routes: segment artifact lineage comes from renderer results, while backend fragments add the executed finalizer result only when a real finalizer ran. I’m checking the edge cases around same-path finalization, v1 projections, and one-segment cardinality before issuing the binary verdict.
exec
/bin/zsh -lc 'git diff --check 907423f2..9d1dfd92; git diff --numstat 907423f2..9d1dfd92 -- astrid/core/rendering/service.py tests/core/rendering/test_service.py; git status --short' in /Users/peteromalley/Documents/reigh-workspace/Astrid-oracle
 succeeded in 29ms:
?? .oracle/checkins/batch-4-r3.md

collab: Wait
codex
PASS
tokens used
105,734
PASS
