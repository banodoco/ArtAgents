# B2 customization coverage ledger

Offline review evidence only. This file is not a runtime authority and is not
read by the catalog, doctor, CLI, SDK, or packaging checks. The canonical
manifests and SQL remain authoritative for declarations and database shape.

## Retained product-pack coverage

| Pack | Identity | Capability / extensions | Database | CLI / SDK / bridge | Documentation | Operational surface | Runtime resources |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `blender` | `pack.yaml` v2 owns `blender` | 1 executor: `render_scene` | — | SDK executor invocation; deployment bridge remains pack-owned | `skill/SKILL.md` | render admission and subprocess/cloud execution | Five standalone entries: `render_core.py`, `mesh_fetch.py`, `renders/wink_turn.py`, `server/blender_render_server.py`, `server/blender-render-api.service` |
| `comfy_wrap` | `pack.yaml` v2 owns `comfy_wrap` | 1 executor | — | SDK executor invocation | `skill/SKILL.md` | typed capability runner | Declared executor content root; no standalone entries |
| `editorial` | `pack.yaml` v2 owns `editorial` | 13 executors | — | SDK executor invocation; static editorial workflows | `skill/SKILL.md` | transcription, scene/shot, arrangement, review, refinement, script, and validation operations | Declared executor content root; presets remain under owned content |
| `fal` | `pack.yaml` v2 owns `fal` | 2 executors | — | SDK executor invocation; external-service boundary | `skill/SKILL.md` | fal.ai generation/Foley execution and secret handling | Declared executor content root; no standalone entries |
| `foley` | `pack.yaml` v2 owns `foley` | 4 capabilities: 3 executors and 1 orchestrator | — | SDK executor/orchestrator invocation | `skill/SKILL.md` | spatial-Foley orchestration | Declared executor/orchestrator roots |
| `generation` | `pack.yaml` v2 owns `generation` | 4 executors; generation typed taxonomy remains kernel projection | — | SDK generation facade and executor invocation | `skill/SKILL.md` | generation admission, model registry, and backend adapters | Declared executor root; model catalog remains typed kernel data |
| `iteration` | `pack.yaml` v2 owns `iteration` | 9 capabilities: 8 executors and 1 orchestrator | — | SDK executor/orchestrator invocation | `skill/SKILL.md` | iteration and experiment review sessions | Declared executor/orchestrator roots |
| `media` | `pack.yaml` v2 owns `media` | 5 executors | — | SDK media facade; parent `media` CLI family | `skill/SKILL.md` | media import, probing, managed storage, and relation operations | Declared executor root; project/external inputs stay outside pack |
| `moirae` | `pack.yaml` v2 owns `moirae` | 2 executors | — | SDK executor invocation | `skill/SKILL.md` | terminal-demo rendering | Declared executor root |
| `references` | `pack.yaml` v2 owns `references` | Combined database/SDK/CLI pack; no executor declaration | 3 tables: `project_references`, `media_references`, `reference_links`; migration `1/initial` | `ReferenceRepository`; `media references` CLI mount; SDK facade; reference bridge vocabulary | `skill/SKILL.md` | reference lifecycle, media association, linking, receipts, and conformance | Migration and skill handles only; no standalone entries |
| `reigh` | `pack.yaml` v2 owns `reigh` | 4 executors | — | SDK executor invocation; Reigh bridge/data boundary | `skill/SKILL.md` | Reigh data, publish, and spatial-audio integration | Declared executor root |
| `rendering` | `pack.yaml` v2 owns `rendering` | 5 executors, 10 elements, 8 typed rendering extensions | — | SDK rendering facade; renderer/planner/finalizer typed projections | `skill/SKILL.md` | timeline render/visualize and renderer asset admission | Content-root schemas/fonts/templates; eight extension handles; no duplicate standalone entries |
| `runaway` | `pack.yaml` v2 owns `runaway` | Database-only pack | 1 table: `runaway_transitions`; migration `1/initial`; default disabled | `RunawayRepository`; `runaway.create`; no CLI/SDK/bridge mount | `skill/SKILL.md` | optional explicit composition and sharded transition persistence | Migration and skill handles only; no standalone entries |
| `runpod` | `pack.yaml` v2 owns `runpod` | 5 executors | — | SDK executor invocation; GPU pod lifecycle boundary | `skill/SKILL.md` | provision, execute, pull, teardown, and session operations | Declared executor root |
| `shots` | `pack.yaml` v2 owns `shots` | Combined database/CLI pack; no executor declaration | 2 tables: `shots`, `shot_items`; migration `1/initial` | `ShotRepository`; `timelines shots` CLI mount; shot command/event vocabulary | `skill/SKILL.md` | timeline shot mutation, receipts, and conformance | Migration and skill handles only; no standalone entries |
| `stream_content` | `pack.yaml` v2 owns `stream_content` | 3 capabilities: 2 executors and 1 orchestrator | — | SDK executor/orchestrator invocation | `skill/SKILL.md` | stream mapping, candidate scoring, and distillation | Declared executor/orchestrator roots |
| `timeline` | `pack.yaml` v2 owns `timeline` | Combined database/CLI/bridge pack; no executor declaration | 1 table: `timelines`; migration `1/initial` | `TimelineRepository`; `timelines` CLI and bridge mount; timeline SDK/service behavior | `skill/SKILL.md` | timeline lifecycle, history/diff, visualization, and rendering coordination | Migration and skill handles only; no standalone entries |
| `training` | `pack.yaml` v2 owns `training` | 6 capabilities: 4 executors and 2 orchestrators | — | SDK executor/orchestrator invocation | `skill/SKILL.md` | dataset, training, clip-pool, LoRA, and asset-cache operations | Declared content roots; schemas/review UI remain under owned roots |
| `understanding` | `pack.yaml` v2 owns `understanding` | 5 executors | — | SDK executor invocation | `skill/SKILL.md` | audio, image, video, scene, and general media understanding | Declared executor root |
| `vibecomfy` | `pack.yaml` v2 owns `vibecomfy` | 2 executors | — | SDK executor invocation; external local workflow boundary | `skill/SKILL.md` | workflow run and validation | Declared executor root |
| `video_editing` | `pack.yaml` v2 owns `video_editing` | 8 capabilities: 1 executor and 7 orchestrators | — | SDK executor/orchestrator invocation | `skill/SKILL.md` | production orchestration and cut rendering | Declared content roots; speaker data remains under owned orchestrator content |
| `youtube` | `pack.yaml` v2 owns `youtube` | 3 executors | — | SDK executor invocation; YouTube service boundary | `skill/SKILL.md` | acquire and upload operations | Declared executor root |

## Kernel classifications

These are explicit irreducible owners, not bundled product-pack omissions:

- Canonical v2 grammar, parser/validator, provenance, resource-handle
  confinement, and catalog admission: `astrid.core.pack`.
- Shared SQLite tables and vocabulary, `DatabaseWriter`, `UnitOfWork`, event
  infrastructure, migration runner, and generic typed registries/loaders:
  `astrid.core`.
- Generation model catalog, feature/mode taxonomy, and four built-in backend
  descriptors: `astrid.core.model_catalog` and `astrid.core.generation`.
- Core product families, operational transport, locks, backup/restore, doctor,
  and application wiring: `astrid.core` / `astrid.application`.
- `_core` guidance and the deterministic 22-pack census:
  `astrid/packs/_core/skill/SKILL.md`; `_core` is not a product pack.

## Closure result

- Product packs: **22** (`18` capability-bearing plus `4` database-bearing).
- Capability projection floor: **64 executors**, **12 orchestrators**, **10
  elements**, **8 rendering extensions**; generation typed projection remains
  **29 features**, **14 modes**, and **4** built-in backend descriptors.
- Database declarations: exactly `timeline`, `shots`, `references`, and
  `runaway`; the first three default enabled and Runaway explicitly disabled.
- Direct pack guidance: **22/22** `skill/SKILL.md` files; `_core` census has
  deterministic sorted routes for all 22.
- Standalone runtime resources: **5**, all owned by `blender`; content-root,
  extension, and migration handles are distinct and confined to their owner.
- Unclassified surfaces: **0**. Every listed surface has a product-pack owner
  or one of the justified kernel owners above.
