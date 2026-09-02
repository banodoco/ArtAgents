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

Folder-backed orchestrators and executors include metadata such as
`orchestrator_root`, `executor_root`, and `stage_file`; agents should load the
top-level Astrid skill first, then open only the specific folder-level
`STAGE.md` needed for the selected registry item. Do not package every
executor and orchestrator stage into one merged runtime prompt.

Content ships in **packs** at `astrid/packs/<pack>/`. Each bundled pack carries
one strict-v2 `pack.yaml` with `schema_version: 2`, identity, contribution
declarations, documentation, and pack-relative resources. The bundled catalog
contains 22 product packs: `blender`, `comfy_wrap`, `editorial`, `fal`,
`foley`, `generation`, `iteration`, `media`, `moirae`, `references`, `reigh`,
`rendering`, `runaway`, `runpod`, `shots`, `stream_content`, `timeline`,
`training`, `understanding`, `vibecomfy`, `video_editing`, and `youtube`.
`_core` is code-owned guidance/kernel, not a product pack. A gitignored
`local` pack may hold user-owned forks.

Executor and orchestrator ids are always qualified — `<pack>.<name>`. Element
ids stay bare and are scoped by kind (`effects`, `animations`, `transitions`).
Pack identity and database ownership come from the canonical catalog, never
from filename conventions or a fixed registry list.

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

Orchestrators coordinate pack capabilities and are loaded from the content root
declared by their owning v2 manifest. The principal shipped workflow
orchestrators live in `editorial`, `foley`, `iteration`, `stream_content`,
`training`, and `video_editing`.

## Executors

Every runnable tool is an executor exposed from exactly one canonical folder
under `astrid/packs/<pack>/<name>/`. The pack id is the first segment of its
qualified id. Domain grouping and external-service ownership are manifest
metadata, not alternate namespaces.

| Executor group | Canonical location | Notes |
| --- | --- | --- |
| Editorial and editing | `astrid/packs/{editorial,video_editing}/*` | Transcript, arrangement, cut, review, and validation capabilities. |
| Media and rendering | `astrid/packs/{media,rendering,understanding,foley}/*` | Media preparation, rendering, understanding, and Foley capabilities. |
| Generation and training | `astrid/packs/{generation,training,iteration}/*` | Generation, dataset, and iteration capabilities. |
| Integrations | `astrid/packs/{moirae,vibecomfy,fal,runpod,youtube,reigh}/*` | Adapters whose permissions and external services are declared in v2 manifests. |

Executor-owned complexity stays in the executor folder. Generic plumbing
belongs in shared `astrid/core` libraries.


## Element Support

| Module or path | Classification | Notes |
| --- | --- | --- |
| `astrid/core/element/registry.py` | Element support | Pack-driven resolution: active theme → user-owned `local` pack → bundled rendering pack. |
| `astrid/packs/rendering/elements/{effects,animations,transitions}` | Element support | Default elements shipped in the rendering pack; `kind`-scoped folders prevent collisions. |
| `astrid/packs/local/elements/<kind>/<id>` | Element support | Gitignored scratch pack where forked element copies land; its `pack.yaml` is strict v2. |
| `astrid/core/element/catalog.py` | Element support | Effect, animation, and transition catalog support used by render validation. |
| `scripts/gen_effect_registry.py` | Element support | Generates Remotion registries from the element registry; emits `@pack-<pack>-elements-<kind>/...` imports. |
| `scripts/gen_capability_index.py` | Capability discovery | Regenerates the capability index block in `astrid/packs/_core/skill/SKILL.md` from executor, orchestrator, and element manifests. |
| `astrid/timeline.py` | Shared library and element validator | Reigh-compatible timeline schema and effect/animation/transition validation. |
| `remotion/*` | Element runtime support | TypeScript renderer consuming generated element registries via bundled-pack and local-pack aliases. |

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
