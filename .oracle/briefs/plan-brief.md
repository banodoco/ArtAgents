# PLAN BRIEF — Astrid: shots as sub-timelines (Phase A) + ffmpeg text rendering

You are the planner. Produce a plan covering the ENTIRETY of the frozen agent goal below.
The plan is a spec, not a memo: tasklist, additional areas to explore, open questions,
an explicit check that the plan advances the North Star without reproducing its
anti-patterns, and a best-effort estimate of total implementation effort with a clear
`>2 weeks` huge-run determination.

BIAS TOWARD ELEGANCE AND SIMPLICITY. KISS, YAGNI, cut scope that isn't pulling its weight.

============================================================
COMPLETE NORTH STAR (normative; do not violate)
============================================================

---
type: anchor
anchor_type: north_star
slug: astrid-first
title: 'North Star: Astrid First'
created_at: '2026-08-13T20:01:16.984884+00:00'
---

Normative source of truth: `docs/unified-data-model-plan-v10-20260813.md` (in this initiative's `docs/`). Plugin/generalization feedback source: `docs/openrouter-chat-20260814-plugin-data.md`. Vision anchor (the long-term destination this milestone serves, including the kernel-audit and promotion-candidate logic): `docs/unified-data-master-plan-20260814.md`. This North Star distills the durable end-state every milestone must preserve; milestone briefs narrow local scope without redefining this destination.

## End State

A standalone, local-first creative product named Astrid: one Python process owns one SQLite database (exactly the v10 20-table Astrid catalog) plus a managed media root, and is the single semantic writer for projects, tasks, runs, media, timelines, references, and shots. The catalog is deliberately layered: an agent-agnostic 14-table kernel (schema_migrations, projects, events/streams/receipts, runs/evidence, tasks/dependencies/attempts/outputs, and media/locations/relations) plus in-tree timeline (1 table), shots (2 tables), and references (3 tables) packs. Core table primitives are reusable; the domain data acts like a plug-in, so a future software-engineering agent can use the unchanged kernel with its own packs. The reigh web editor remains the frontend and talks to Astrid over the existing bridge wire contract (loopback; CAS timeline saves; asset Range serving), which must keep working through and after the milestone. Zero-config setup: install, `astrid serve`, open the editor, pair, work — no accounts, billing, cloud services, or provider secrets required for the core journey.

The model's one-sentence foundation: **tasks execute; everything else is an event; every exact asset is media; references add project semantics to media.**

**Vision anchor.** The master plan (above) is the durable vision: a plug-in data substrate reusable across agents — this milestone is its first, proving composition. Kernel citizenship is audited, not assumed: each of the 14 kernel tables earns its keep as an agent-agnostic primitive (migration bookkeeping, project scope, events/receipts, runs/evidence, tasks/dependencies/attempts/outputs, media/locations/relations — provenance and observation, not domain semantics). The six pack tables (timeline, shots, references) are deliberately NOT kernel today; their *patterns* (whole-document CAS; ordered exact-media containers) are promotion candidates that move into the kernel only when at least two real compositions prove the common need (kernel-evolution rule) — then the generalized primitive is promoted and Astrid's packs become thin aliases over it. Promotion is earned by a second composition's requirement, never assumed from resemblance.

## Non-Negotiables

- Exactly the v10 20-table Astrid schema: kernel 14 + timeline 1 + shots 2 + references 3; no plan/step tables, no legacy/session/thread/lease tables, no dormant platform tables (accounts, billing, sharing, sync, remote worker). Catalog tests assert the core tables plus the tables declared by installed packs, rather than hardcoding 20 as a universal kernel catalog.
- `schema_migrations` is pack-aware from creation: `pack TEXT NOT NULL DEFAULT 'core'` and `PRIMARY KEY (pack, version)`. Core and packs migrate independently, forward-only, in declared dependency order.
- Kernel DDL does not hardcode pack vocabulary: `event_streams.stream_type` has no closed `CHECK`; repositories validate stream types against the startup registry populated by `register_pack()`. Event and command kinds are registered and namespaced (`timeline.saved`, `shot.item_added`, `reference.primary_changed`).
- Media is kernel citizenship, including the `task_outputs.media_id` coupling. Source files, diffs, logs, and creative assets share the same exact-byte primitive; media must not be demoted into a domain pack.
- Plugin laws: packs may FK into kernel tables, but kernel tables never FK into pack tables and refer to pack subjects only through `events.subject_type`/`subject_id`; cross-pack references use only kernel currencies such as `media_id` and `task_id`.
- Packs never own a writer. Each registers repositories with the one kernel write queue and receives a UoW handle inside the kernel's `BEGIN IMMEDIATE`, including project-sequence allocation, stream-head CAS, event append, and receipt writing.
- Kernel-evolution rule: a table enters the kernel only when at least two real compositions prove the same semantic need and implementing it separately would break atomicity or interoperability. The current 14 kernel tables are the audited, earned set; timeline/shots/references stay packs until promotion is earned by a second composition.
- Every pack command passes the reusable kernel conformance kit: idempotent replay, mismatched-key rejection, statement-boundary crash injection, and same-project assertions. In-tree packs have manifests declaring ID/version/dependencies, migrations, stream/event/command kinds, repositories, conformance, and CLI/bridge mounts.
- Task/event principle: a task exists only for immutable executable work with exclusive claim or fenced attempts; every other meaningful mutation is an append-only, hash-chained, project-ordered event. Events, heads, projections, outputs, associations, and the command receipt commit or roll back atomically (one writer queue, `BEGIN IMMEDIATE`).
- Terminal immutability and attempt fencing: terminal tasks never resurrect; stale attempts never win; materialization is exactly-once (receipts, idempotent replay, mismatched-key rejection).
- Timeline whole-document CAS: document + asset registry advance together against the stream head; stale saves return 409 with no mutation. The current editor's provider/persistence tests must pass against the repository-backed bridge (the "editor contract/provider" lane).
- Media identity is verified byte SHA-256; paths/URLs/source IDs are replaceable locations/aliases, never identity. Exact placements and reference associations never inherit invisibly across variants.
- Single writer: repositories are the only semantic writers; bridge, CLI, SDK, executor, media import all route through them. FSA and Supabase do not exist as authorities.
- The Reigh timeline-sync requirement stays live: the existing editor↔Astrid bridge contract keeps working through the milestone (ordinary editor tests as the gate — no continuity ceremony).
- References (characters/places/objects/clothing) are project-scoped, media-associated (canonical/used_as_input/depicts/inspired_by), linkable, event-backed projections.

## Explicit Non-Goals

- No legacy data import beyond `media import` (bytes only). No project/history/run-dialect/timeline-chain/audit import, no aliases, no parity/cutover machinery.
- No plan/step/orchestration machinery (group/repeat/for_each/supersede, run_steps, fake parent tasks) — replaced by runs that directly group immutable tasks + `task_dependencies`.
- No editor FSA persistence; no Supabase; no remote GPU execution; no hosting/Turso; no experiments/publish/accounts/billing/tenancy/sync/replication.
- No new editor features; no `scheduling`/duration commitments in documents.
- No speculative catalog tables; packs/components/elements/models stay file-side manifests.
- No dynamic plugin discovery/loader at GA and no third-party install/uninstall platform. Establish `core/` + in-tree `packs/{timeline,shots,references}` boundaries and one explicit startup registration path now; extract/share the kernel and add a loader only when a second agent is real (boundary now, loader later).

## Allowed Temporary Bridges

- During m1–m3, the existing file-backed timeline code may remain in the tree for reference, but no supported write path may use it once its repository route lands; delete the old authority in m6 (teardown).
- A bounded "editor contract adapter" may translate repository errors to the frozen wire shapes (409/422/404) — it is a thin mapping, not a second backend.
- Decision artifacts (media root/layout, fan-out limits, closed vocabularies, platform matrix) may be recorded in the initiative's docs before the milestone that consumes them; they are prep, not scope changes.

## Drift Signals

- Any table added beyond the 20 (especially plan/step/legacy/catalog/dormant-platform tables) without a v10 amendment.
- A receipt/event that can be lost or duplicated on retry; an idempotency mismatch that mutates state; a crash path that yields neither old nor complete.
- The editor's provider tests failing against the repository bridge, or a save path that bypasses repositories.
- Media referenced by path/URL instead of media ID; path hashes treated as content identity.
- A kernel table foreign-keying into a pack table; a pack reaching directly into another pack instead of using kernel currencies or a declared dependency; hardcoded pack stream-type/event-kind/command-kind enums in kernel DDL.
- A pack opening a transaction or owning a writer instead of using the kernel UoW; a pack command bypassing the kernel conformance kit; deleting a pack breaks the kernel test suite.
- Work that "preserves" old Astrid data, dialects, threads, sessions, or plans; a second writer; a browser-required acceptance item (except the frozen editor test lane).
- "It works locally" accepted without crash injection, backup/restore proof, or the GA acceptance items 1–12 in v10 §5.3.

============================================================
FROZEN AGENT GOAL (contract; plan must satisfy exactly this)
============================================================

# Agent Goal — shots as sub-timelines (Phase A) + ffmpeg text rendering

[North Star](./northstar.md). This run advances the ONE-store kernel principle by making
storyboard sections first-class kernel citizens: real `shots` rows owning their own
`timelines` documents, parent timeline referencing them as composite `shot` clips, and
render-prep expansion producing byte-equivalent flat output — proven by re-rendering the
Astrid intro through the extended ffmpeg backend (no Remotion in the path).

## Context

- Plan doc: `docs/storyboard-pipeline.md` — "Shots projection & sub-timeline plan" (Phases A/B/C).
- Verified facts from Phase 2 exploration (`.oracle/findings/`):
  - `shots`/`shot_items` tables + `ShotsService` (idempotency keys, metadata_json, item positions, multi-item shots) exist and are renderer-neutral (`astrid/packs/shots/`, `astrid/sdk/shots.py`).
  - Plugin law: shots pack must never FK/import the timeline pack; shot↔timeline-document link lives in `shots.metadata_json` (data, not FK).
  - Timeline clip schema has no children; a `shot` clip type is required.
  - The current intro render is static slides + text overlay + VO with hard cuts; **zero** animation (fade effects declared but unimplemented in Remotion). Entirely ffmpeg-replicable.
  - `rendering.ffmpeg` backend exists, currently `media_only`; `rendering.remotion` selector is an ffmpeg-first auto-routing pair. Extend ffmpeg's capabilities (text clip support) rather than add a new backend.
  - Render routing: `_translate_legacy_selector` in `astrid/core/rendering/service.py`; per-candidate `support()` checks.
- In-flight (protect, not part of this run): Remotion self-hosted fonts fix (`remotion/src/fonts.ts`).

## Objective

Deliver Phase A of the shots projection + sub-timeline plan, plus the ffmpeg text-rendering
extension, so the storyboard pipeline renders end-to-end without Remotion.

Deliverables
- A1 **Shot registration**: storyboard sections → `shots` rows + `shot_items` via `ShotsService` with deterministic idempotency keys (`<project>:shot:<slug>`, items `:image`/`:vo`); metadata carries slug, nav, prompt.
- A2 **Shot sub-timelines**: per shot, a `timelines` row whose document is the section composition (broll plate + caption text + VO audio, 3 clips); `timeline_document_id` recorded in the shot's `metadata_json` (data, not FK — plugin law).
- A3 **Parent compiled as shot clips**: compiler emits 25 `shot` clips (+ brand wordmark) instead of 75 flat clips; each `params.shot_id` → real kernel shot id; `at`/`hold` placement in parent document.
- A4 **Render-prep expansion** in the kernel timeline layer: resolve `shot` clips via `timeline_document_id`, splice sub-clips at the shot's `at` window (offset + clamp to hold). Expanded document byte-equivalent (modulo clip ids) to today's flat compile output — the existing golden parity test becomes the expansion test.
- A5 **ffmpeg text extension**: `rendering.ffmpeg` accepts text clips — rasterize text to transparent PNG (PIL), overlay with `enable=` timing + fade envelope; update `renderer.yaml` capabilities (clip_types: media+text, text_overlay, fade_envelope) and `support.py`. Intro renders via ffmpeg: seconds, no Chrome/webpack/CDN.
- A6 **End-to-end proof**: storyboard → compile (shots + shot-clip parent) → save to kernel → render via ffmpeg → open. Golden parity maintained: 76 clips / 50 assets / 177.53s ±0.5 (from expansion).

Non-goals
- Phase B (Reigh editor integration onto shot documents) — separate future run; exploration finding `.oracle/findings/reigh-app-shot-structures.md` preserved as input.
- Phase C (renderer-native nested compositing) — explicitly deferred until Phase A green + concrete limitation hit.
- No UI editor changes; no kernel core schema changes; no `pinnedShotGroups` changes; no storyboard v1 schema changes.
- No Remotion work beyond preserving the in-flight font fix.

## Model policy (user-pinned)

- Oracle / planner / [XHARD]: **grok-4.6** (grok CLI, `--reasoning-effort high`). Fallback if unavailable: GPT-5.6 Sol via `codex exec`. No automatic routing.
- Explorer / normal executor: **DeepSeek V4 Flash 0731** (`launch_hermes_agent.py --model="deepseek:deepseek-v4-flash"`, toolsets file,web,terminal). No automatic routing.
- Pinned models authoritative unless evidence shows unavailability (then report + fall back as declared above).

## Done criteria

1. Shot registration idempotent: running the compiler twice yields the same 25 shots / 50 items (no duplicates, receipts replay-safe).
2. Each shot's `metadata_json` carries `timeline_document_id` resolving to a real `timelines` row (25 sub-documents).
3. Parent timeline = 25 `shot` clips + wordmark; `timelines show` reports counts consistent with the golden test (76 clips / 50 assets post-expansion, 177.53s ±0.5).
4. Render-prep expansion test: expanded document byte-equivalent (modulo clip ids) to current flat compile output — golden parity test green.
5. Intro renders through ffmpeg text extension: `astrid timelines render ... --backend rendering.ffmpeg` succeeds; output ≈177±3s, 3 spot-check frames show captions; no Remotion invocation in the path.
6. Evidence matrix maps every criterion → command/path/result. grok oracle PASS per batch + final review (≤3 passes).

## Validation commands

- `python3 scripts/build_storyboard.py validate --story storyboards/astrid-intro.storyboard.json`
- compile with shots projection enabled (project astrid-intro)
- `python3 -m pytest tests/ -k storyboard -x -q` (schema + compiler golden/expansion)
- `astrid timelines show main --project astrid-intro` counts
- `ASTRID_PROJECTS_ROOT=... astrid timelines render main --project astrid-intro --backend rendering.ffmpeg --output-name shot-pipeline.mp4`
- `ffprobe` duration; frame extraction spot-checks

## Sync/authorization

- Commit batches on branch `megado/oracle-run-storyboard` (this worktree).
- Push that branch to origin authorized at finish. Never merge to main.
- Opening local videos/files authorized. Local-only: no deploy, no Supabase, no remote.
- The in-flight Remotion fonts fix (`remotion/*`, `remotion/public/`) is protected: do not revert or commit it as part of this run's batches unless required by a batch's own scope.

## Stop conditions

- Blocked if grok AND codex both unavailable for oracle (report + halt after safe checkpoint).
- Escalate scope expansion beyond A1–A6 (e.g. Phase B/C asked mid-run).
- Failed if a done criterion is reproducible-unmet after rework; `undetermined` if evidence insufficient.

============================================================
PHASE 2 EXPLORATION EVIDENCE (verified facts, file:line)
============================================================

## Area 1 — Shots mount (finder verifies: full)
- `shots` table: id (PK), project_id (FK→projects, CASCADE), name, sort_key (UNIQUE per project), metadata_json, created_at, updated_at — `astrid/packs/shots/migrations/0001_initial.sql:17-26`
- `shot_items`: id (PK), shot_id (FK→shots, CASCADE), media_id (FK→media, ON DELETE RESTRICT), sort_key (UNIQUE per shot), source_frame, metadata_json, created_at — `0001_initial.sql:28-37`
- Read models at `astrid/packs/shots/repository.py:260-326`; position domain `0..count` (`repository.py:30-31`)
- `ShotsService` API: `create(*, project, name, metadata=None, idempotency_key=None)` (:86), `add_item(project, shot_id, *, media_id, position=None, source_frame=None, metadata=None, idempotency_key=None)` (:141), `remove_item` (:201), `reorder` (exact permutation, :246), `list` (:291), `show` (:314) — `astrid/sdk/shots.py`
- No shots→clips bridge: pack "never FK's to or imports the timeline pack" (`repository.py:8-10`), `pinnedShotGroups` in timeline JSON is a different embedded concept (`timeline_visualize/model.py:432-489`, `timeline_storyboard/run.py:291-351`)
- Items are media-kind-agnostic; any kernel media qualifies; multiple items per shot yes
- Render executor ignores shots; reads timeline config + asset registry only (`render/managed_timeline.py:235-232`)
- Tables live in each project's `.astrid/astrid.sqlite3` (`managed_timeline.py:244`); shots is one of three standard schema packs (`core/schema_packs/standard.py:27`); stream type `shot.shot` registered (`core/events/registry.py:298-301`); CLI: `astrid timelines shots` with six verbs (`packs/timeline/cli.py:14-19`)

## Area 2 — ffmpeg capabilities (finder verifies: full)
- Current render: static slide PNGs + text overlay + VO, hard cuts — frames at t=10.0/t=10.4 md5-identical; zero `fade|interpolate|spring` matches in `remotion/src/`; declared fade effects unimplemented
- Text = `ThreeTimelineComposition.tsx` offscreen canvas → three.js plane; drawtext replicable; word wrap needs manual `\n` insertion
- Existing ffmpeg renderers: `scripts/render_2rp_launch_ffmpeg.py` (PIL frames + ffmpeg encode), production compositor `astrid/packs/rendering/finalizers/compositor/run.py` (z-layer overlay filtergraph), `blender/render_core.py`
- Single-section command shape: `-loop 1 -t N -i slide.png -i vo.wav -filter_complex "[0:v]scale=1920:1080,drawtext=fontfile=...:x=(w-text_w)/2:y=h-text_h-56:text='Caption',format=yuv420p[v]" -map "[v]" -map 1:a -c:v libx264 -r 30 -c:a aac -shortest out.mp4`
- Full timeline: per-segment `-t` inputs + `concat=n=2[v]` + `adelay` per audio + `amix=inputs=2:normalize=0[a]`
- Verdict: entire current output is ffmpeg-replicable; Remotion adds nothing used today except browser text layout

## Area 3 — render routing (finder verifies: full)
- `timelines render --backend X` (`packs/timeline/cli.py:515-519`) → `inputs["backend"]` → `RenderService`; selection in `_translate_legacy_selector` (`astrid/core/rendering/service.py:152-209`)
- Backend registry: `load_default_registries` (`registry.py:497-503`) from manifests in `astrid/packs/rendering/pack.yaml:46-58`
- `rendering.ffmpeg` exists: `backends/ffmpeg/renderer.yaml:2`, currently `clip_types: [media]`, `features: media_only: true` (lines 14-22)
- `.legacy` remotion selector = ordered pair `("rendering.ffmpeg", "rendering.remotion")` with `auto_route=True` (`service.py:171-177`); `None` defaults to remotion (`service.py:167-168`)
- Auto-route falls through only on `unsupported`/`binary_missing` (`service.py:718-721`) + `LegacyRenderRoutingWarning` (:730-735); media-only → ffmpeg; text/effect/transition → Remotion
- Also `rendering.threejs` renderer; planners `rendering.legacy_hybrid`, `rendering.threejs-hybrid`, `rendering.layer_stack`; finalizers `rendering.ffmpeg-finalizer`, `rendering.ffmpeg-compositor`; no blender backend; html-canvas = deprecated executor alias
- Backend interface: protocol v1 (`contracts.py:23`): `renderer.yaml` manifest (`RendererManifest`, `contracts.py:2163` — id, protocol_version, command, operations [render, support], capabilities, permissions, binaries) + subprocess `run.py` reading `RenderRequest` writing `RenderResult`/`RendererError` (`parse_wire_result`, `contracts.py:2267`)
- Extend `rendering.ffmpeg` capabilities; do not add a new backend

## reigh-app (Phase B input, NOT in this run's scope)
- No nested timelines; `PinnedShotGroup` = soft-tag overlay {shotId, trackId, clipIds[], mode, videoAssetKey, imageClipSnapshot[]}; EffectLayerSequence = only clip-contains-children pattern; Sequence = single procedural Remotion clip type; keyframes clip-local; effects per-clip + timeline-wide shader
- 3 candidate nesting mechanisms for a future run (extend PinnedShotGroup, composition clipType, EffectLayerSequence wrap)
- Full record: `.oracle/findings/reigh-app-shot-structures.md`

============================================================
YOUR TASK
============================================================

1. Produce a complete tasklist covering EVERYTHING in the agent goal (A1–A6 + validation), organized into sensible batches that end at natural seams, each batch with ONE checkpoint and acceptance criteria the oracle will verify.
2. List additional areas to explore for full clarity before the tasklist freezes (only if genuinely needed — much of the picture is known).
3. List open questions that need answering before or during execution.
4. Explicitly state how the plan advances the North Star and which North Star anti-patterns/drift signals it must avoid (e.g. pack FK violations, second writers, path-as-identity, tables beyond 20).
5. Best-effort estimate of total implementation effort with a clear `>2 weeks` huge-run determination.
6. Recommend normal vs [XHARD] classification per task. [XHARD] is EXCEPTIONAL: sustained subtle reasoning across tightly coupled concerns where a plausible mistake survives local validation AND neither DeepSeek V4 Flash nor GPT-5.6 Luna can execute reliably from a mechanical brief. Default: normal.

Reply with the plan as structured markdown. Be concrete: file paths, function names, wiring points, test names. Mechanical brevity over essay.