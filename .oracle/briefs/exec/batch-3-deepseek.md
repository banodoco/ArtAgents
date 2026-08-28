# EXECUTOR BRIEF — BATCH 3 (A1–A3): compiler shot projection + `--shots`

You are the normal-pool executor (DeepSeek V4 Flash). Execute batch 3 of a settled plan in repo root = this project dir. Mechanical work, no architecture decisions: the design is frozen below. Skip formatters, linters, and project-wide test suites; run ONLY your batch's focused tests.

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

===== DESIGN (frozen; do not relitigate) =====
- The compiler (`scripts/build_storyboard.py`) stays the FLAT 76-clip emitter by DEFAULT. `--shots` flag adds kernel writes + a parent sidecar compiled as `shot` clips.
- Shot↔timeline link is DATA: `shots.metadata_json.timeline_document_id` + parent clip `params: {shot_id, timeline_document_id}`. NO FK, NO import of the timeline pack from shots (plugin law), NO `shot.update` (create hash includes metadata).
- Idempotency keys (deterministic, replay-safe):
  * timeline slug: `shot-{section_id with _ → -}`
  * timeline create key: `{project}:shot-timeline:{section_id}`
  * shot create key: `{project}:shot:{section_id}`
  * item keys: `{project}:shot-item:{section_id}:image` / `:vo`
- Order per section: create-or-save sub-timeline → create shot with COMPLETE metadata (incl. timeline_document_id) → add_item image → add_item vo.

===== BATCH 3 TASKS (frozen; acceptance is binding) =====

T8 — Image resolution + extract `_section_clips`.
  - `scripts/build_storyboard.py`: resolve `image.path` XOR active variant (use the existing `_variant_import_path` helper — currently dead code — for variants; intro uses path). Extract the per-section clip-emission into a helper `_section_clips(section, ...) -> list[dict]` (vo/cap/broll), preserving EXACT clip dicts (ids, at, track, hold, from/to, text style, params, fades, generation) so the flat output is unchanged.
  - Both intro JSON (path) and golden fixture (variants) compile. No schema change. Dead leftover `_variant_import_path` becomes live.

T9 — Sub-doc builder.
  - New helper: per section build the SHOT sub-timeline document: 3 clips (vo a1 / cap captions / broll broll) with LOCAL `at=0`; hold/to match flat per-section durations; 2-asset registry (image + vo); NO brand clip.
  - idempotency keys per DESIGN above.

T10 — `project_shots` projection via SDK.
  - Use `ShotsService` (astrid/sdk/shots.py: create/add_item) and `TimelinesService` (create/save) — repositories are the ONLY writers; never raw SQL from the compiler.
  - Metadata on shot create: `{slug, nav, prompt, timeline_document_id}`.
  - NEW `tests/test_compiler_shots.py` using the existing temp-project harness (reuse `tests/sdk/test_shots.py` / `tests/v10/_m7_fixture.py` patterns; NO third helper): 2-section fixture → 2 shots / 4 items / 2 sub-timelines; COMPILE TWICE → same shot ids, same 25 timeline rows, NO extra rows on the second run (receipt replay-safe) [AG1][AG2]; each metadata `timeline_document_id` resolves to a real timelines row; shots pack still has no timeline import (conformance test stays green).

T11 — Parent emitter + CLI `--shots`.
  - Parent doc: brand wordmark (text, hold=total) + 25 `clipType:"shot"` clips on `broll`: `{id: shot_<slug>, at, track: broll, clipType: shot, hold, params: {shot_id, timeline_document_id}}`.
  - Full 50-asset registry. `--shots` flag on compile CLI defaulting OFF (flat stays default). Sidecar written via existing `_write_outputs`.
  - `--shots` runs kernel writes (imports media, creates sub-timelines, creates shots/items, saves parent).

T12 — Golden becomes the expansion test.
  - `tests/test_compiler_golden.py`: keep flat 76/50/177.53±0.5 asserts. NEW: compile the intro storyboard with `--shots` into a TEMP project, then `expand_shot_clips(parent)` == flat compile output **byte-equivalent modulo clip ids** [AG3][AG4].
  - `expand_shot_clips` comes from B2 (`astrid/core/timeline/expand_shots.py`); it will exist (parallel batch). Import it once available; if B2's commit isn't present when you finish, note the dependency in the report and stub the test to run once B2 lands (do NOT implement expansion yourself).

===== CONTRACT (parallel batches) =====
- You own ONLY: scripts/build_storyboard.py, tests/test_compiler_shots.py (new), tests/test_compiler_golden.py, tests/fixtures/* (only if needed for the temp-project shots test).
- NEVER touch: remotion/*, remotion/public/* (protected), astrid/packs/*, astrid/core/*, astrid/sdk/* (read-only), astrid/packs/timeline/cli.py (B2), astrid/packs/rendering/backends/ffmpeg/* (B1).
- Do NOT add tables, do NOT add a `shot.update`, do NOT FK shots↔timeline.

===== VERIFY (focused only) =====
- `python3 -m pytest tests/test_compiler_shots.py tests/test_compiler_golden.py tests/test_storyboard_schema.py -x -q` green.
- `git diff HEAD --stat` shows NO changes to astrid/packs/*, astrid/core/*, remotion/*.

===== COMMIT =====
`git add -- <exact files you created/changed>` then `git commit -m "megado B3: compiler shot projection + --shots (A1-A3)"`.
NEVER `git add -A` / `git add .` / `git commit -am`. Never stage .oracle deletions or remotion/*.

Report: files changed, test results (pass counts), commit sha, any deviation (with reason).
