# EXECUTOR BRIEF — BATCH 2 (A4): render-prep expansion

You are the normal-pool executor (DeepSeek V4 Flash). Execute batch 2 of a settled plan in repo root = this project dir. Mechanical work, no architecture decisions: the design is frozen below. Skip formatters, linters, and project-wide test suites; run ONLY your batch's focused tests.

===== COMPLETE NORTH STAR (normative; preserve it) =====
---
type: anchor
anchor_type: north_star
slug: astrid-first
title: 'North Star: Astrid First'
created_at: '2026-08-13T20:01:16.984884+00:00'
---

# North Star: Astrid First

Normative source of truth: `docs/unified-data-model-plan-v10-20260813.md` (in this initiative's `docs/`). Plugin/generalization feedback source: `docs/openrouter-chat-20260814-plugin-data.md`. Vision anchor (the long-term destination this milestone serves, including the kernel-audit and promotion-candidate logic): `docs/unified-data-master-plan-20260814.md`. This North Star distills the durable end-state every milestone must preserve; milestone briefs narrow local scope without redefining this destination.

## End State

A standalone, local-first creative product named Astrid: one Python process owns one SQLite database (exactly the v10 20-table Astrid catalog) plus a managed media root, and is the single semantic writer for projects, tasks, runs, media, timelines, references, and shots. The catalog is deliberately layered: an agent-agnostic 14-table kernel (`schema_migrations`, projects, events/streams/receipts, runs/evidence, tasks/dependencies/attempts/outputs, and media/locations/relations) plus in-tree timeline (1 table), shots (2 tables), and references (3 tables) packs. Core table primitives are reusable; the domain data acts like a plug-in, so a future software-engineering agent can use the unchanged kernel with its own packs. The reigh web editor remains the frontend and talks to Astrid over the existing bridge wire contract (loopback; CAS timeline saves; asset Range serving), which must keep working through and after the milestone. Zero-config setup: install, `astrid serve`, open the editor, pair, work — no accounts, billing, cloud services, or provider secrets required for the core journey.

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

===== PLUGIN LAW (absolute, non-negotiable) =====
- The shots pack does NOT import or FK the timeline pack. The timeline/core MUST NOT import the shots pack. Expansion NEVER `SELECT`s from `shots`.
- The shot↔timeline-document link is DATA: parent clip `params: {shot_id, timeline_document_id}` (parent CAS doc is the authority). Shot metadata `timeline_document_id` is the shot-side record (Phase B).
- Expansion is MEMORY-ONLY: the stored sqlite timeline document is NEVER written back. `timelines show` keeps reporting the stored parent.

===== BATCH 2 TASKS (frozen; acceptance is binding) =====

T5 — NEW `astrid/core/timeline/expand_shots.py`, pure function:
  `def expand_shot_clips(config, registry, *, load_timeline) -> tuple[dict, dict]`
  - For each clip with `clipType == "shot"`: require `params.shot_id` and `params.timeline_document_id`; load sub-doc via `load_timeline(timeline_document_id)` → (sub_config, sub_registry).
  - Offset every sub-clip: `new_at = parent.at + sub.at`; clamp sub-clip into the parent's `at`+`hold` window; drop sub-clips with non-positive remainder; preserve sub-clip ids.
  - Merge sub_registry assets into the parent registry (registry union, no clobber; parent wins on conflict).
  - Nested `shot` clip inside a sub-doc → fail closed. Missing params → fail closed. Unknown timeline_document_id → fail closed (raise).
  - NEW `tests/core/timeline/test_expand_shots.py`: offset/clamp/drop; nested/missing fail; byte-equivalent output to a canned flat doc **modulo clip ids**; registry union; memory-only (input dicts untouched).

T6 — Hook expand before render admission.
  - In the managed render path: `resolve_managed_render_snapshot` (astrid/packs/timeline/.../managed_timeline.py:235) → `_prepare_managed_render_inputs` (invocation.py:612, validate ~715). Insert expand BETWEEN resolve and validate: after `resolve_managed_render_snapshot`, before `validate_managed_render_snapshot`, call `expand_shot_clips(snapshot_config, snapshot_registry, load_timeline=...)`.
  - `load_timeline` reads `SELECT document_json, asset_registry_json FROM timelines WHERE id=?` from the SAME connection used by the snapshot resolver (reuse; no second connection).
  - File-mode renders: no expansion; leftover `shot` clips fail closed (existing behavior of render admission).
  - Bridge load / editor / stored docs: NOT expanded (never touch stored doc).
  - Extend `tests/packs/rendering/test_managed_timeline_render.py` (or a sibling): a timeline with `shot` clips renders after expansion; stored sqlite doc byte-unchanged; file-mode with `shot` clip fails closed.

T7 — CLI `astrid timelines show` derived expanded counts.
  - `astrid/packs/timeline/cli.py` show handler: additionally print `expanded: {clips, assets, duration}` (derived by running `expand_shot_clips` with the same loader, NOT by reading the stored doc differently).
  - `TimelineReadModel` UNCHANGED. Do not change stored-doc semantics.

===== CONTRACT (parallel batches) =====
- You own ONLY: astrid/core/timeline/expand_shots.py (new), the managed render hook (invocation.py + managed_timeline.py as needed), astrid/packs/timeline/cli.py (show), + your new/extended tests.
- NEVER touch: remotion/*, remotion/public/* (protected), astrid/packs/shots/*, astrid/sdk/shots.py, scripts/build_storyboard.py (B3), astrid/packs/rendering/backends/ffmpeg/* (B1), renderer.yaml.
- Do NOT add tables, do NOT add a `shot.update`, do NOT add a timeline↔shots FK, do NOT import the shots pack anywhere.

===== VERIFY (focused only) =====
- `python3 -m pytest tests/core/timeline/test_expand_shots.py tests/packs/rendering/test_managed_timeline_render.py -x -q` green (plus files you added).
- `git diff HEAD --stat` shows NO changes to remotion/*, astrid/packs/shots/*, scripts/*.

===== COMMIT =====
`git add -- <exact files you created/changed>` then `git commit -m "megado B2: render-prep shot expansion (A4)"`.
NEVER `git add -A` / `git add .` / `git commit -am`. Never stage .oracle deletions or remotion/*.

Report: files changed, test results (pass counts), commit sha, any deviation (with reason).
