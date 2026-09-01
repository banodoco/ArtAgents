# Astrid Architecture

Astrid has three canonical public concepts:

- **Orchestrators** coordinate multi-step workflows.
- **Executors** run concrete work.
- **Elements** are render/custom building blocks such as effects, animations, and transitions.

Canonical packages and commands are first-class. `python3 -m astrid` is the
executable package gateway for the eight families (projects, timelines, media,
tasks, runs, serve, doctor, backup) and the two nested mounts (`timelines
shots`, `media references`). Capabilities (executors, orchestrators, elements)
are not gateway commands; they run through the SDK
(`astrid.sdk.invoke` / `astrid.sdk.client.AstridClient`).

## Onboarding Commands

From a cold checkout the gateway census and health check come first:

```bash
python3 -m astrid --help          # the complete eight-family census
python3 -m astrid doctor --json   # read-only health check
python3 -m astrid projects list --json
```

There is no session-binding step and no `setup` command: product commands run
directly against the local SQLite kernel at
`$ASTRID_PROJECTS_ROOT/.astrid/astrid.sqlite3` (created lazily by the first
product command).

Canonical discovery is the SDK; the `--json` CLI reads are the shell
equivalents:

```python
import astrid.sdk as sdk
result = sdk.discover()                       # every capability, pack by pack
cap = sdk.get_capability("rendering.render")  # typed lookup of one capability
```

## Timeline text binding boundary

The Timeline skill coordinates authored text while the Shots pack owns the
shot-facing data. A `shot_text_binding` is a stable typed identity over
immutable Core text media for `prompt`, `voiceover_script`, or `transcript`;
it is shot-owned and intentionally has no timeline relation. The nested
`timelines text` mount exposes bounded `list`, `checkout`, `status`, `diff`,
`apply`, `set`, and `rebind` commands. These are receipt-backed domain
commands in the active UnitOfWork, not capability invocations, runs, or a
second ledger.

Checkout projections freeze bounded UTF-8 caller bytes before mutation and
delay temporary materialization until an absent digest is known in the
transaction. Current/base media must be text; persisted malformed text is an
integrity error, while caller encoding failures and desired candidate
conflicts retain their public validation taxonomy. The binding path reads
Core media through the active-UoW repository, does not call
`prepare_media_file()`, and does not add direct Core-media SQL. No-op keys are
not consumed; changed commands replay from receipts. `set` is the only
creation path and `rebind` is existing-only. Canonical managed digest paths
are mandatory.

Generation and rendering retain literal task inputs and do not hydrate text
bindings. Voiceover synthesis and WAV promotion are explicit. Caption plates
are baked derived media and record output-to-input lineage: the plate
`uses_as_input` the transcript text. The approved push-3s opening, including
its embedded ASTRID logo pixels, remains in the media-only FFmpeg composition;
there is no separate wordmark/text overlay. Source-tree/default skill sync is
supported; wheel packaging and HTTP bridge routes for this workstream are
deferred.

Folder-backed orchestrators and executors include metadata such as
`orchestrator_root`, `executor_root`, and `stage_file`; agents should load the
top-level Astrid skill first, then open only the specific folder-level
`STAGE.md` needed for the selected registry item. Do not package every
executor and orchestrator stage into one merged runtime prompt.

Content ships in **packs** at `astrid/packs/<pack>/`. Each pack carries a `pack.yaml` with `id`, `name`, and `version`, and contains executor folders, orchestrator folders, and an `elements/<kind>/<id>/` tree. The shipped packs are `rendering`, `understanding`, `generation`, `editorial`, `video_editing`, `foley`, `training`, `reigh`, `youtube`, `fal`, `vibecomfy`, `runpod`, `moirae`, `iteration`, `media`, `stream_content`, `comfy_wrap`, `blender`, `discord_local`, and `seedance_local`. The deprecated `builtin` pack is a thin shell; legacy `external` and `upload` pack definitions were removed, and backward compatibility is via pack-level aliases declared in the canonical packs. A gitignored `local` pack at `astrid/packs/local/` holds user-edited element forks. Default orchestrators include `video_editing.hype`, `video_editing.event_talks`, and `video_editing.thumbnail_maker` (legacy aliases: `builtin.hype`, `builtin.event_talks`, `builtin.thumbnail_maker`). Default executors include every `STEP_ORDER` capability, upload/action executors, `understanding.understand` (audio/visual/video dispatcher), `generation.generate_image_openai` (with a `saint-peter-of-banodoco` onboarding preset), `moirae.moirae`, and `vibecomfy.run`/`vibecomfy.validate`.

Executor and orchestrator ids are always qualified — `<pack>.<name>` (for example `video_editing.cut`, `vibecomfy.run`). Bare lookups such as `cut` are rejected at the schema and CLI boundaries. Element ids stay bare and are scoped by `kind`, so `animation/fade` and `transition/fade` coexist without collision.

Each runnable orchestrator has exactly one canonical implementation location:
`astrid/packs/<pack>/<name>/{orchestrator.yaml,STAGE.md,run.py}` with
optional local `src/` modules. Each runnable executor has exactly one canonical
implementation location:
`astrid/packs/<pack>/<name>/{executor.yaml,STAGE.md,run.py}` with optional local
`src/` modules. Each element has exactly one canonical layout:
`astrid/packs/<pack>/elements/<kind>/<id>/{component.tsx,element.yaml}`.
Top-level `astrid/*.py` modules are shared libraries or
system commands only; they are not alternate executor or orchestrator
implementations.

For creation decisions, use `docs/guides/creating-tools.md` and the templates under
`docs/templates/`. Add an executor for one concrete action, an orchestrator for
a workflow, and an element for a reusable render primitive. Agents should avoid
manual chains of low-level stage artifacts unless they are debugging a specific
executor.

For a step-by-step tutorial on building your first agentic UX, see
[docs/build-your-first-agentic-ux.md](../guides/build-your-first-agentic-ux.md).

## Orchestrators

| Module or entry point | Classification | Notes |
| --- | --- | --- |
| `python3 -m astrid`, `astrid/__main__.py` | System entry point | Executable package gateway for the eight CLI families. |
| `astrid/core/gateway/` | System command and dispatcher | Routes the eight families and the two nested mounts; one verb = one SDK call. No capability dispatch. |
| `astrid/packs/video_editing/orchestrators/hype/` | Orchestrator | Canonical hype video editing orchestrator. |
| `astrid/packs/video_editing/orchestrators/event_talks/` | Orchestrator | Canonical event-talk discovery and rendering workflow. |
| `astrid/packs/video_editing/orchestrators/thumbnail_maker/` | Orchestrator | Canonical source-evidence thumbnail workflow. |
| `astrid/core/execution/orchestrator/{runner,registry,schema,folder}.py` | Orchestrator framework | SDK-invoked runner (subprocess, `ASTRID_INTERNAL_INVOCATION=1`), pack-discovery registry, schema, and folder loader. |

## Executors

Every runnable tool is a built-in or external executor exposed from exactly one canonical folder under `astrid/packs/<pack>/<name>/`. The pack's id is the first segment of the executor's qualified id.

| Executor group | Canonical location | Notes |
| --- | --- | --- |
| Hype pipeline stages | `astrid/packs/{editorial,video_editing,rendering,understanding,foley}/*` | `STEP_ORDER` stages used by `video_editing.hype` (legacy alias: `builtin.hype`). |
| Understanding tools | `astrid/packs/understanding/{audio_understand,visual_understand,video_understand,understand}` | Concrete media understanding tools, plus a thin `understand` dispatcher executor that selects modality via `--mode`. |
| Standalone/service tools | `astrid/packs/{training,editorial,reigh,generation,rendering}/*` | Standalone executor capabilities across domain packs. `generate_image` is the multi-backend (local + cloud) image executor in `generation`; `generate_image_openai` is the OpenAI DALL-E executor, also in `generation`. |
| External tools | `astrid/packs/{moirae,vibecomfy,fal,runpod,youtube,reigh}/*` | `moirae.moirae`, `vibecomfy.run`, `vibecomfy.validate`, `fal.fal_foley`, `runpod.*`, `youtube.*`, `reigh.*`. Each adapter pack wraps a third-party substrate. Legacy `external.*` ids are deprecated pack-level aliases. |
| Iteration tools | `astrid/packs/iteration/{prepare,assemble}` | `iteration.prepare` and `iteration.assemble` for the iteration_video orchestrator. |
| Upload tools | `astrid/packs/youtube/` | `youtube.upload` and `youtube.youtube_audio`. Legacy `upload.youtube` is a deprecated alias. |

Executor-owned complexity stays in the executor folder, usually under optional local `src/` modules. Hype/editing domain logic belongs with its owning pack under `astrid/packs/editorial/hype`; generic plumbing belongs in `astrid/utilities`.

## Element Support

| Module or path | Classification | Notes |
| --- | --- | --- |
| `astrid/core/element/schema.py` | Element support | `element.yaml` schema (`id`, singular `kind`, `pack_id`, `metadata`, `schema`, `defaults`, `dependencies`) and dependency dataclasses. |
| `astrid/core/element/registry.py` | Element support | Pack-driven resolution: active theme → `pack:local` (priority 10) → `pack:builtin` (priority 30). Fork copies into the local pack and rewrites `pack_id`. |
| `astrid/packs/rendering/elements/{effects,animations,transitions}` | Element support | Default elements shipped in the rendering pack; `kind`-scoped folders so `animations/fade` and `transitions/fade` coexist. |
| `astrid/packs/local/elements/<kind>/<id>` | Element support | Gitignored scratch pack where forked element copies land (auto-creates `astrid/packs/local/pack.yaml`). |
| `astrid/core/element/catalog.py` | Element support | Effect, animation, and transition catalog support used by render validation. |
| `scripts/gen_effect_registry.py` | Element support | Generates Remotion registries from the element registry; emits `@pack-<pack>-elements-<kind>/...` imports. |
| `scripts/gen_capability_index.py` | Capability discovery | Regenerates the capability index block in `astrid/packs/_core/skill/SKILL.md` from executor, orchestrator, and element manifests. |
| `astrid/timeline.py` | Shared library and element validator | Reigh-compatible timeline schema and effect/animation/transition validation. |
| `remotion/*` | Element runtime support | TypeScript renderer consuming generated element registries via `@pack-builtin-elements-*` and `@pack-local-elements-*` aliases. |

## Shared Libraries

| Module or package | Classification | Notes |
| --- | --- | --- |
| `astrid/core/contracts/*` | Shared library | Common schema dataclasses for ports, outputs, cache, commands, and isolation. |
| `astrid/packs/editorial/hype/*` | Pack-owned domain library | Hype-cut/editing concepts such as arrangement rules, enriched arrangements, and text matching. |
| `astrid/core/util/llm_clients.py` | Utility library | Generic LLM client construction and environment handling. |
| `astrid/core/audit/*` | Shared library | Run-local provenance ledger, graph, and HTML report. |
| `astrid/core/theme/` | Shared library | Theme resolution, CLI, and schema validation helpers. |
| `astrid/core/paths.py` | Shared library | Repository and workspace path resolution. |
| `astrid/packs/editorial/executors/refine/src/reviewers/*` | Executor-owned library | Focused review heuristics used only by `editorial.refine`. |
| `astrid/packs/youtube/executors/upload/src/social_publish.py` | Executor-owned library | Social publishing client logic used by `youtube.upload`. |

This classification keeps only retained root and bin launchers; executor-owned public metadata and entrypoints live in canonical executor folders, and orchestrator-owned public metadata and entrypoints live in canonical orchestrator folders.

## Structure Enforcement

Repository structure enforcement, import layering rules, exemption lists, and
the `validate_repo_structure()` machinery are documented in
[docs/architecture/repo-shape.md](../architecture/repo-shape.md).

## Retired Concepts

**Task-mode CLI** is retired. The legacy `attach` / `next` / `start` / `ack`
verbs, the `executors run` / `orchestrators run` invocation surface, and the
old filesystem task-run store no longer exist; the eight-family CLI and the
SDK are the whole surface. The `astrid/core/task/` runtime and the
`text_analysis.summarize` and `builtin.agent_probe` orchestrators were
removed with it. Kernel task execution now lives in
`astrid/core/task_executor/` (the injected `TaskHandler` boundary for
pack-owned task-mode adapters).

**Threads** are retired as a user-facing concept. The `astrid thread` CLI
surface no longer exists. Threads are retained only as an internal lineage
model for iteration-video provenance; no current `astrid` command binds to
them at runtime.

## Generated Files and Dirty Worktrees

Normal generated outputs belong under `runs/` or another ignored directory. Do not commit source media, rendered videos, local dependency environments, or secrets.

Element changes may require generated Remotion registry updates. Keep `.ts`, `.js`, `.d.ts`, and `.map` siblings synchronized in `remotion/src`, then scan for stale element aliases:

```bash
python3 scripts/gen_effect_registry.py
rg "@workspace-|workspace-effects|workspace-animations|workspace-transitions" remotion/src scripts remotion -n
```

Always inspect `git status --short` before editing. Preserve unrelated user changes, especially dirty curated executor stage files such as `astrid/packs/moirae/executors/moirae/STAGE.md` and `astrid/packs/vibecomfy/executors/run/STAGE.md`.
