# Astrid-first two-week sprint plan

**Date:** 2026-08-13  
**Status:** executable delivery plan derived from `unified-data-model-plan-v10-20260813.md`  
**Planning unit:** two-week sprint  
**Base case:** four experienced engineers  
**Recommended forecast:** eight sprints to GA, with Sprints 9–10 held as conditional contingency

**Revision:** Revised 2026-08-14: folded in the plugin/generalizable kernel + packs architecture. The 10 review fixes from `astrid-first-sprint-plan-review-20260813.md` remain applied.

## Executive summary

The recommended base plan is eight two-week sprints. Sprint 1 deliberately spends most of the team on the load-bearing event, receipt, migration, and single-writer transaction core; it also establishes the agent-agnostic kernel + in-tree pack boundary and takes one thin repository-backed editor journey all the way from project creation to timeline save and reload. That early editor slice is a risk probe, not a shortcut around the core. Sprint 2 opens the first safe parallel lanes—executor lifecycle and managed media—after the transaction contract exists. Media is kernel infrastructure, so task outputs, source files, diffs, logs, and generated assets share the same exact-byte model. Sprint 3 closes v10 Phase 1 by completing the reference and shot packs and proving real generation and rendering, synchronous understanding as run evidence, direct-child fan-out, pack conformance, the five task races, contention, and crash atomicity.

Sprints 4–6 build the product around that core. Sprint 4 completes the frozen Reigh bridge and editor contract/provider lane while exposing the already-proven reference and shot repositories through editor/service journeys. Sprint 5 completes the reduced SDK, shared result envelope, and the five domain CLI families: `projects`, `timelines`, `media`, `tasks`, and `runs`. Sprint 6 adds the three operational families—`serve`, `backup`, and `doctor`—plus packaging, zero-secret local setup, and removal checks; only then does executable product help contain exactly eight families and v10 Phase 2 close. Sprint 7 dogfoods a representative fresh project and attacks process-kill, mutation, missing-media, contention, restore, and recovery behavior. Sprint 8 is release hardening against the actual packaged artifact and is the normal GA gate.

The earlier 32–46 person-week estimate implies a theoretical six-sprint capacity floor and an executable 8–10 sprint forecast. A four-engineer sprint contains eight gross person-weeks, but only about five to six are safely forecast as net feature work once pairing on the event core, review, integration, editor test work, release work, and defect absorption are included. Six sprints is not scheduled or committed because the producer/consumer gates do not have a dependency-preserving compressed map. The recommended eight-sprint plan preserves integration and hardening capacity; the 46 PW high case consumes one or both of Sprints 9–10. Those reserve sprints absorb repository/atomicity correctness or editor/platform/package surprises. They are not a license to defer ordinary acceptance work or weaken atomicity.

The critical path is:

`schema + writer queue + events + receipts` → `repositories` → `executor/media/timeline bridge` → `SDK/CLI` → `serve/package/backup/doctor` → `dogfood and GA`.

Parallel work opens only at proven seams: media runs alongside executor work after Sprint 1; run/evidence, references/shots, and capability adapters run alongside lifecycle hardening in Sprint 3; the full editor bridge and editorial service journeys proceed in Sprint 4; and packaging/removal work runs alongside operational hardening from Sprint 6 onward. Every sprint ends in a working vertical result or an explicit milestone gate. A sprint is not complete because code was merged.

## 1. Assumptions

### 1.1 Team and operating model

The base case is four experienced engineers who can work across Python, SQLite, the Reigh TypeScript editor, packaging, and test infrastructure. The plan assigns lanes, not permanent specialists. At least two engineers review and pair on the event/receipt and task-transition kernels because those contracts are global correctness boundaries. One engineer owns integration each sprint and rotates rather than becoming a fifth, invisible workstream.

The plan assumes:

- one shared product backlog and one integration branch or equivalent continuously integrated trunk;
- repository and bridge contract tests run on every merge;
- no production users or legacy data must be migrated, consistent with v10 §1, **Cut list**;
- useful existing code is treated as a parts bin—hashing, probing, atomic placement, manifests, capability contracts, and the current bridge envelope may be reused, but old semantic writers are not adapted;
- experiments, cloud sync, hosted workers, RunPod, publication, accounts, billing, editor rewrite, and compatibility aliases remain outside this milestone;
- forward migrations are allowed for layouts created during development, but no compatibility layer is built for unshipped schemas;
- code is factored from the outset as `core/` plus in-tree `packs/timeline`, `packs/shots`, and `packs/references`; each pack has a manifest, its own migrations, and one startup `register_pack()` call;
- pack manifests declare `id`, `version`, `depends_on`, `migrations`, `stream_types`, `event_kinds`, `command_kinds`, `repositories`, `conformance`, `cli_mounts`, and `bridge_mounts`;
- v10 builds the boundary and static in-tree registration only. A dynamic plugin loader and extraction of `core/` into a shared library wait until a second agent is real.

The three-engineer and solo variants are in §4. They preserve this order and these gates; they reduce concurrency rather than correctness.

### 1.2 Sprint length and definition of done

Each sprint is two calendar weeks. Planning, implementation, review, documentation, integration, and the named tests are inside the sprint. A story that lacks its repository tests, command-receipt behavior, error behavior, or cleanup of the authority it replaces is not done.

A sprint is done only when it produces either:

1. a shippable vertical slice exercised through the public service/bridge/CLI/SDK boundary named for that sprint; or
2. an explicit milestone gate whose evidence is checked into normal CI and whose failure blocks dependent work.

“Shippable” does not mean GA-polished. It means the result is integrated, restart-durable where applicable, has no hidden alternate semantic writer, and could be demonstrated from a fresh database. Feature-complete but unintegrated lanes carry over and consume buffer; the sprint gate does not turn green by exception.

### 1.3 Estimation and the executable 8–10 sprint range

The 32–46 person-week (PW) figure is focused engineering effort. Four people supply eight gross PW in a two-week sprint, but this program cannot use all eight as independent feature capacity. The event core is intentionally paired; repository changes need cross-lane review; Reigh tests and Python tests must be integrated; packaging and release testing consume real capacity; and crash/race defects are discovered only after vertical integration. The forecast therefore treats approximately five to six PW per sprint as dependable net delivery capacity.

That produces three useful cases:

| Case | Shape | Calendar interpretation |
| --- | --- | --- |
| Theoretical floor, about 32 PW | Gross capacity arithmetic only; no dependency-preserving compressed schedule is approved | **Six sprints** is a lower bound, not an executable forecast or commitment |
| Base | Normal integration cost and some discovered defects | **Eight sprints** is the working forecast and includes a real dogfood sprint plus a release sprint |
| High, about 46 PW | Core invariants, crash-safe media, editor drift, or packaging require rework | **Nine or ten sprints** by activating the reserve in §2; scope and gates remain unchanged |

The executable range is not calculated by blindly dividing PW by four. Dependencies serialize the first core, and the last release work must exercise integrated behavior. Six may be promoted to a forecast only after an approved compressed map names entry/exit criteria while preserving the Sprint 1 transaction gate, Sprint 3 Phase 1 gate, Sprint 6 Phase 2 gate, dogfood, and artifact proof. Adding headcount before Sprint 1 contracts stabilize would not shorten those gates.

### 1.4 Normative boundaries

This sprint plan sequences v10; it does not amend it. The normative scope remains:

- exactly the 20 Astrid tables and declared indexes in v10 §2.1–§2.2, layered as 14 kernel tables plus the installed timeline (1), shots (2), and references (3) pack tables;
- repository-enforced constraints and one short `BEGIN IMMEDIATE` command unit from v10 §2.3;
- the three phase gates in v10 §3;
- exactly eight top-level product CLI families from v10 §4.1;
- the reduced SDK and frozen bridge surface from v10 §4.2;
- the backup, doctor, and secrets behavior in v10 §4.3;
- every kept invariant and all twelve GA acceptance items in v10 §5.

The plugin laws are also normative: packs may FK into kernel tables but the kernel never FKs into a pack; cross-pack references use kernel currencies such as `media_id` and `task_id`; packs register repositories with the single kernel writer and never own transactions; every pack command passes the reusable kernel conformance kit; and stream, event, and command vocabularies are namespaced. The Astrid catalog is still 20 tables, but catalog expectations are derived from the 14-table core manifest plus installed pack manifests rather than a hardcoded global list.

No sprint may solve a delay by restoring plans, steps, session or thread state, file/JSONL semantic authority, Supabase/FSA writes, a multi-source importer, or legacy aliases.

## 2. Sprint map

### 2.1 Overview and critical path

| Sprint | Theme | Primary goal | Key deliverables | Gate |
| --- | --- | --- | --- | --- |
| **1** | Transaction foundation + early editor spike | Establish the only safe write boundary and the in-tree pack contract, then expose editor-contract risk immediately | Layered 20-table migration, pack-aware migration runner/catalog, writer queue, event/receipt kernel, pack registries, project and first timeline repositories, thin project → timeline save → reload bridge path | Installed core + pack catalog and receipt tests pass; pack laws/lints pass; retry is deterministic; stale save is mutation-free; crash shows old-or-complete; one real editor provider save test passes |
| **2** | Executor ∥ media foundations | Open independent execution and byte-management lanes on the proven core | Task/attempt/dependency lifecycle, claim/start/heartbeat skeleton, managed-media layout, hash/probe/stage/place/dedupe, media repositories, first lifecycle and media crash tests | Tasks have correct streams/fences; managed bytes dedupe by project SHA-256; no output can bypass repositories |
| **3** | Phase 1 vertical proof | Complete the core through real product journeys | Runs/evidence/fan-out, reference and shot repositories, generation and renderer adapters, ordered outputs, synchronous understanding, cancellation/retry, five races, full statement-boundary crash and contention suites | Full v10 §3 **Phase 1 gate**, including reference/shot §2.3 constraints, and GA items 1–5 at core level |
| **4** | Full editor bridge ∥ editorial integration | Make the existing editor work against repositories and expose exact-media editorial semantics | Frozen bridge routes/envelopes, CAS 409/422/404, restart and Range behavior, provider/persistence/draft/poll tests, editor/service reference and shot journeys over the S3 repositories | Editor list → load → edit → save → reload works; draft safety passes; editorial integration preserves the S3 exact-media/project constraints |
| **5** | Reduced SDK + five domain CLI families | Put domain user/developer actions through one service layer | Reduced SDK, shared stable result envelope, five executable domain families (`projects`, `timelines`, `media`, `tasks`, `runs`), typed errors, editorial commands, history/diff, group operations, clean local workflow smoke | Domain CLI/SDK use repositories only; reference and shot round trips pass; no operational placeholders, sixth domain family, or plan API appears |
| **6** | Productization and Phase 2 gate | Complete the operational surface and make the product installable, recoverable, and sole-authority | Executable `serve`, `backup create/restore`, and `doctor`; lazy initialization; package path; secret rules; FSA/Supabase/old-help removal; import lint | Full v10 §3 **Phase 2 gate**; clean install reaches an editable project with zero secrets; executable help contains exactly eight functional families |
| **7** | Dogfood and destructive hardening | Use the shipped surface for a representative fresh project and attack failure modes | Media import/relocate/verify, generation/render/fan-out/evidence/references/shots, kill/restart, two-writer contention, missing/mutated files, backup restore, five-race rerun | GA items 1–10 pass; item 11 has provisional source/build proof; dogfood uses no hidden tools or old authority |
| **8** | Release hardening and normal GA buffer | Prove the actual release artifact on the supported matrix | Forward-migration rehearsal, packaged clean-account tests, release help/import audit, focused core/editor suites, defect fixes, completion evidence | v10 §3 **Phase 3 gate** and all §5.3 checks green against the actual artifact |
| **9, conditional** | Repository/atomicity correctness reserve | Absorb any material repository or atomicity slip without weakening semantics | Root-cause repair for event/receipt, timeline, executor, media, references, shots, backup/restore, or systemic SQLite contention; expanded regression and crash/race/contention proof | Triggered defect is closed at its original gate; S8 evidence reruns green |
| **10, conditional** | Platform/editor/package reserve | Absorb supported-platform, browser, packaging, or editor-contract surprises | Targeted package/bridge fixes and clean-machine rerun | Supported matrix and actual artifact pass without scope exceptions |

The base commitment ends at Sprint 8. Sprints 9 and 10 are forecast reserve, not prefilled feature sprints. When they are unused, the project ships at Sprint 8. When a reserve sprint is activated, it contains only work required to satisfy an existing gate; deferred features do not enter merely because time was reserved.

### 2.2 Parallel lanes: when they open and close

- **Sprint 1 is intentionally constrained.** Two engineers pair on schema/events/receipts/writer ownership and the pack registration boundary; one builds project plus timeline-pack repositories; one maps the existing bridge contract and connects the thin editor slice. Executor or media semantic writes do not start on a provisional transaction API.
- **Executor ∥ media opens in Sprint 2.** Both consume the same receipt/event/repository transaction primitive. Their common integration point is task completion materialization, closed in Sprint 3.
- **Runs/evidence ∥ references/shots ∥ capability adapters opens in Sprint 3.** Direct child grouping and zero-task runs can develop beside generation/render adapters and the exact-media editorial repositories, but the Phase 1 gate joins all of them through registered events, heads, atomic receipts, and §2.3 constraints.
- **Editor bridge ∥ editorial integration opens in Sprint 4.** The bridge and editor contract/provider lane consumes stable timeline, media, reference, and shot repositories from Phase 1; Sprint 4 adds service/editor journeys rather than a second semantic implementation.
- **CLI/SDK work opens after repositories have real journeys.** Sprint 5 wraps services; it does not define domain semantics inside handlers.
- **Packaging ∥ removal/hardening opens in Sprint 6 and closes at GA.** Operational work can proceed beside authority cleanup, but both must be tested in the built artifact by Sprint 8.

### 2.3 GA acceptance coverage

| V10 §5.3 acceptance item | First meaningful proof | Completion sprint | Release rerun |
| --- | --- | --- | --- |
| 1. Astrid's 14 core + 6 installed-pack tables/indexes total exactly 20; pack-aware too-new schema behavior | S1 | S1 | S8 |
| 2. Real generation and render atomically traverse task/attempt/event/media/location/output/receipt | S3 | S3 | S7–S8 |
| 3. Synchronous understanding produces run + evidence without task | S3 | S3 | S7 |
| 4. Direct-child fan-out, dependencies, progress/cancel/retry, no step table | S3 | S3 | S7 |
| 5. Crash injection and five task races | S1 begins; S2 lifecycle cases | S3 | S7–S8 |
| 6. Timeline/editor list/load/save/409/422/restart/draft/Range | S1 thin save risk probe | S4 | S7–S8 |
| 7. Media dedupe, mutation and missing-location detection, byte identity | S2 | S3/S7 failure cases | S7–S8 |
| 8. References and shots exact-media round trip | S3 repository proof; S4 editor/service journey | S5 | S7 |
| 9. Backup/restore and doctor | S6 | S6 | S7–S8 |
| 10. Clean install, local use, zero secrets | S5 smoke | S6 | S8 |
| 11. Removed authorities/families absent | Continuous replacement | S6 source/build audit | S8 artifact audit |
| 12. Every pack passes the reusable conformance kit; deleting one leaves the kernel suite green; a second-agent sketch changes no kernel table | S1 harness; S3 real packs | S3 | S8 |

## 3. Per-sprint detail

### Sprint 1 — Transaction foundation and early editor spike

**Goal:** Build the event/receipt/repository kernel without rushing it, then prove that its first timeline save can satisfy the current editor contract.

**Work items and dependencies**

1. Implement v10 §2.2 **Full creation DDL** exactly: all 20 Astrid tables (14 kernel + 1 timeline + 2 shots + 3 references), declared unique and lookup indexes, `foreign_keys`, WAL, synchronous mode, and bounded busy timeout. `schema_migrations` has `pack TEXT NOT NULL DEFAULT 'core'` and `PRIMARY KEY (pack, version)`. Build the expected catalog from the core manifest plus installed pack manifests; fail on an extra/missing declared table or index, while absence of `run_steps`, `run_step_tasks`, plans, sessions, aliases, or importer tables remains affirmative evidence.
2. Build the dependency-ordered, forward-only migration runner with per-pack version/name/checksum validation, application-version compatibility, deterministic fresh creation, and the v10 §5.3(1) too-new behavior: open read-only where safe or fail clearly without mutation. Core and each pack version independently.
3. Establish the single kernel-owned repository write queue and short `BEGIN IMMEDIATE` unit of work. Pack repositories receive a unit-of-work handle containing the project-sequence allocator, stream-head CAS, event append, and receipt writer; they never open a connection or transaction. Add bounded busy retry/backpressure plus import-lint and fixtures that reject handler or pack direct writers and reject any kernel FK/import dependency on a pack.
4. Define kernel registries for stream types, event kinds, and command kinds. Remove the kernel DDL `event_streams.stream_type` closed-vocabulary `CHECK`; validate stream types in repositories against core and pack declarations registered by one startup `register_pack()` path. Register namespaced pack event kinds such as `timeline.saved`, `shot.item_added`, and `reference.primary_changed` and matching namespaced command kinds; implement consecutive `projects.event_head_seq` allocation, stream-head CAS, bounded `changes_json`, event schema versioning, and event ordering queries.
5. Implement canonical request serialization/hashing and `command_receipts`: identical key/request returns the stored full result; identical key/different bytes returns typed `idempotency_mismatch`; receipt event IDs and project sequence range match the transaction.
6. Implement kernel `ProjectRepository.create/list/show/update` and the first timeline-pack `TimelineRepository.create/list/show/save` methods. Creation owns streams; save atomically updates `document_json` and `asset_registry_json`, appends its event, advances the head, and writes the receipt.
7. Package the first §2.3 checks as the reusable kernel pack-conformance kit: stream aggregate ID/type/project agreement, timeline/project ownership, same-project assertions, idempotent replay, mismatched-key rejection, statement-boundary crash injection, and mutation-free rejection of stale timeline CAS.
8. Add statement-boundary crash injection for project create and timeline save, plus a concurrent two-save test. Each observation must be either pre-command or a mutually complete projection/event/head/receipt result.
9. Build a thin repository-backed bridge slice for `GET /health`, `GET /projects`, timeline list/load, and timeline save. Preserve the v10 §4.2 payload fields and hide the internal receipt from the unchanged editor response envelope.
10. Run a focused real `AstridBridgeDataProvider`/persistence test against that slice, including a successful save/reload and stale `expected_version` → 409 `timeline_version_conflict`. This is the earliest warning for wire-contract drift.
11. Create the required [v10 implementation decision artifact](astrid-v10-implementation-decisions.md). Before the Sprint 1 gate it fixes the managed media root/reference-in-place/staging policy; the exact allowed `media_relations.kind` values; the fan-out maximum child count, continuation envelope, expected-head/CAS fields, and receipt linkage; and the exact evidence kinds plus reference kinds/roles/link kinds. The same artifact names the supported OS/browser/package matrix owner and a Sprint 5 deadline, before Sprint 6 Phase 2 work begins.

**Parallel lanes:** Engineers A+B pair on migration, events, receipts, writer queue, pack registration, and crash harness. Engineer C builds the kernel project repository and timeline-pack repository against that kernel. Engineer D maps the frozen bridge fields/errors and connects only the thin save journey. D does not create a second storage adapter.

**Deliverable:** From a fresh checkout and database, create a project, create/list/load a timeline, save object `config` plus object `registry` at numeric `config_version`, reload it through the bridge, and observe a durable event/receipt chain after restart.

**Acceptance gate:** The manifest-derived catalog proves exactly 14 core and 6 installed-pack tables plus all declared indexes; per-pack migration and too-new handling are safe; startup registration rejects undeclared or duplicate stream/event/command kinds; FK-direction and no-direct-writer lints pass; idempotent replay and mismatch behavior pass; project/timeline stream association passes; a stale save returns 409 with no mutation; crash injection proves old-or-complete; one current editor provider/persistence save test passes. The decision artifact contains the frozen media layout/relation kinds, complete fan-out contract, exact evidence/reference vocabularies, and the Sprint 5 platform-matrix owner/deadline. Executor and media repository implementation stays blocked until this gate is green.

### Sprint 2 — Executor and media foundations

**Goal:** Build independently fenced executable tasks and crash-conscious media identity in parallel on the Sprint 1 transaction core.

**Work items and dependencies**

- Implement `TaskRepository` admission for bounded immutable specs, `spec_hash`, input manifests, task streams beginning with namespaced `task.created`, queued/blocked state, same-project acyclic `task_dependencies`, and stable `run_ordinal` preparation. A task is admitted only for independently claimable/attempt-fenced work.
- Implement internal claim/start/heartbeat/expiry primitives over `execution_attempts`. Heartbeats are the narrow non-event exception and advance `status_version`; claim, start, expiry, cancellation, retry, failure, and completion remain registered semantic events.
- Implement terminal immutability and winning-attempt ownership checks early. Add queued cancel versus claim and stale attempt versus transition tests before capability adapters depend on them.
- Validate task admission and continuation preparation against the frozen Sprint 1 fan-out maximum, envelope, expected run-stream head/CAS fields, ordinal rules, and receipt linkage. Sprint 2 may implement supporting validation, but it does not redesign or re-freeze the contract; transactional fan-out completes in Sprint 3.
- Implement the kernel `MediaRepository` over `media`, `media_locations`, and `media_relations`. Media is not a pack, and the portable `task_outputs.media_id` coupling remains deliberate: identity is project-scoped SHA-256 of verified bytes; path, URL, registry key, and display name are locators only.
- Reuse probe/hash/stream primitives behind a quarantine → hash/probe → fsync → atomic placement flow. Managed copy is default; reference-in-place is explicit `external_local`; stage cleanup never invents rows from files.
- Implement `media import` service behavior at repository level for files/folders, dedupe within a project, verified locations, MIME/ffprobe metadata, missing/mutation detection, relocation, the frozen relation kinds and constraints, and variant acyclicity. CLI wrapping waits until Sprint 5.
- For media import, relocate, and relate, assert registered event order, affected stream and project heads, and atomic projection/location/relation plus complete receipt. Identical request/key replay returns the original result; key reuse with different canonical bytes fails before mutation.
- Add representative statement-boundary failure injection for import, relocate, and relate, as well as stage, placement, and row commit; every reopened observation is old-or-complete across projection/location/relation, event(s), heads, and receipt. Add cross-project rejection and same-byte/different-path vectors. Prepare the output-manifest quarantine contract that capability adapters must use.
- Before the Sprint 2 gate, verify the Sprint 1 evidence kinds and reference kinds/roles/link kinds remain explicit and unchanged in the required [v10 implementation decision artifact](astrid-v10-implementation-decisions.md); any proposed change reopens the decision gate before Sprint 3 work can begin.

**Parallel lanes:** Two engineers own task/attempt lifecycle; one owns media/storage; one owns shared conformance, crash injection, and writer-contention infrastructure. Cross-review pairs task completion with media placement because Sprint 3 joins them.

**Deliverable:** A repository client can admit, claim, start, heartbeat, and fence a task, and can import the same bytes from two paths into one project media identity with verified managed storage. Neither journey uses a legacy session/lease file or semantic sidecar.

**Acceptance gate:** Task stream/project associations and dependency constraints pass; stale attempt versions cannot mutate lifecycle; terminal state cannot be reopened; identical bytes dedupe; changed or missing locations are reported; media import/relocate/relate pass ordered-event, head, atomic receipt, replay, mismatch, and statement-boundary old-or-complete tests; staged bytes cannot create partial semantic truth; writer contention is bounded. Evidence and reference vocabularies are fixed in the required decision artifact. The generation/render, evidence, and reference/shot lanes may begin only on these stable contracts.

### Sprint 3 — Phase 1 vertical proof

**Goal:** Close the core by completing exact-media reference/shot repositories, running real generation, rendering, understanding, and fan-out through atomic repositories, and proving race/crash safety.

**Work items and dependencies**

- Complete lifecycle transitions: cancel request/acknowledgement, expiry/requeue, failure, retry, completion, run progress updates or derived reads, and group cancel/retry expansion over eligible children.
- Implement `RunRepository` and `EvidenceRepository` for zero or many direct child tasks. Runs are query/group handles, never executable parents. Evidence may identify a direct child task and exact media, with §2.3 same-run/same-project constraints.
- Implement the references-pack `ReferenceRepository` for `project_references`, `media_references`, and `reference_links` using the frozen kinds/roles/link kinds: archive behavior, exact-media association, one primary canonical, canonical ordinal ordering, contextual-task rules, same-project enforcement, and canonical ordering for symmetric links.
- Implement the shots-pack `ShotRepository` for `shots` and `shot_items`: stable ordering, add/remove/reorder, exact media IDs, source frames, and same-project enforcement.
- For reference primary replacement, associate, link, and shot reorder, assert registered event order, affected stream/project heads, and atomic projection/association/order state plus complete receipt. Identical replay returns the original result, mismatched-key reuse fails before mutation, and representative statement-boundary failures reopen old-or-complete.
- Implement bounded one-transaction fan-out: run, run stream, child task streams/tasks with unique ordinals, dependency edges, creation events, and one receipt. Implement receipt-linked continuation CAS, ordinal allocation, replay/collision behavior, and terminal-run rejection. Prove no step records or plan cursor exist.
- Adapt one real generation capability and one real renderer to immutable task specs and file-side capability manifests. Capabilities write only quarantined outputs plus declared manifests; repository completion verifies and materializes media, locations, ordered `task_outputs`, relations, winning attempt, events, and receipt atomically.
- Implement synchronous understanding as a run plus `evidence_items`, optionally linked media, and no convenience task. Its receipt returns run/evidence/media IDs.
- Run all five normative races: queued cancel vs claim; running cancel vs completion; running cancel vs expiry/requeue; stale failure vs newer attempt; terminal task vs retry/later cancellation. Assert event order, attempt fences, output presence/absence, and no resurrection.
- Extend statement-boundary crash injection across fan-out and task completion, including media placement; run a concurrent editor save + heartbeat + CLI/repository mutation + completion test through the one writer queue.
- Run every timeline, shots, and references command through the reusable kernel conformance kit. Add the factoring test that removes one pack at a time from registration/source and proves the entire kernel suite remains green with a catalog consisting only of core plus the packs still installed. Sketch a second agent as core plus its own manifest/table pack and prove the sketch requires no kernel-table change.
- Delete or make unreachable the corresponding `Step`/`TaskPlan`, session, thread, lease-file, current-run, inbox, JSONL authority, and Supabase project-state paths as their replacements land. Preserve pack/manifests and optional immutable diagnostics only.

**Parallel lanes:** Run/evidence/fan-out; reference/shot repositories; generation/render adapters; lifecycle/race and crash/contention/authority deletion. All lanes converge at the complete Phase 1 conformance gate; capacity moves between lanes before any Phase 2 work begins.

**Deliverable:** One generation and one render traverse task → attempt → event → verified media/location → ordered output → receipt; synchronous understanding produces run evidence without a task; a multi-task run honors dependencies, reports progress, and supports eligible cancel/retry; repository clients construct exact-media reference and shot models with primary, association, link, and ordering invariants intact.

**Acceptance gate:** The complete v10 §3 **Phase 1 gate** passes: the Astrid installation has exactly 20 tables and constraints; all run/evidence and reference/shot same-project, exact-media, primary, ordering, contextual-task, and symmetric-link checks; real generation/render; zero-task understanding; direct-child fan-out; five races; bounded contention; and statement-boundary crash injection. Every pack command passes the reusable kernel conformance kit, and deleting any one pack leaves the entire kernel suite green without changing a kernel table. Reference primary/associate/link and shot reorder also pass event/head/atomic-receipt, replay, and mismatched-key conformance. Any failure in a repository, pack boundary, or atomicity invariant blocks Phase 2; no alternate semantics may be built.

### Sprint 4 — Full editor bridge and editorial integration

**Goal:** Make the current Reigh editor reliable on the repository bridge and expose the Phase 1 reference/shot semantics through editor and service journeys.

**Work items and dependencies**

- Complete the frozen v10 §4.2 routes: project list; timeline list/load/save addressed by UUID or supported ULID; asset `GET`/`HEAD`; health; and only required OPTIONS/CORS behavior.
- Preserve the consumed payload fields: `timeline_id`, `timeline_ulid`, `slug`, `name`, `is_default`, loose `config`, `registry.assets`, numeric opaque `config_version`. Derive the bridge save idempotency key from identity, expected version, and canonical payload while returning the unchanged editor envelope.
- Implement typed 404 envelopes, 409 `timeline_version_conflict`, 422 `schema_incompatible`, successful save payload, single-range 206, invalid-range 416, and restart durability. Do not pin incidental timing or headers unless the client consumes them.
- Run the existing `AstridBridgeDataProvider`, provider compatibility, IndexedDB timeline-draft, poll-sync, timeline persistence, and save utility lanes against repositories. Assert that failed saves do not acknowledge or erase recovery data, successful covering saves may clear it, polling cannot overwrite pending local work, and failed load disables persistence.
- Add the end-to-end editor test: list → load → edit → save → reload, stale save, invalid schema, process restart, draft recovery, and media Range playback.
- Integrate the Sprint 3 references- and shots-pack repositories into editor/service read and mutation journeys through their registered bridge/service mounts without duplicating their semantics. Rerun their exact-media, same-project, primary, association/link, stable ordering, event/head, receipt, replay, mismatch, and crash conformance suites through the integrated service boundary.

**Parallel lanes:** Two engineers on bridge/server and repository mapping; one on the editor contract/provider test lane and FSA removal; one on editorial service integration over the gated reference/shot repositories. The editor gate wins integration conflicts.

**Deliverable:** The current editor edits a repository timeline across restart with correct conflicts, drafts, polling, and byte-range assets; editor/service clients exercise the gated exact-media reference and shot models without a second writer.

**Acceptance gate:** GA item 6 passes in the editor contract/provider lane. All supported bridge mutations have internal receipts without changing response envelopes. FSA is not a fallback. Integrated reference/shot journeys preserve the Sprint 3 constraints and command conformance before public CLI commands wrap them.

### Sprint 5 — Reduced SDK, five domain CLI families, and semantic journeys

**Goal:** Expose the domain product through a thin service layer, reduced SDK, shared stable envelope, and the five functional domain CLI families.

**Work items and dependencies**

- Freeze shared service methods and result models so CLI and bridge handlers never implement SQL, hashing, lifecycle arbitration, or output materialization.
- Keep lazy manifest discovery, `get_capability`, typed `invoke`/`generate`/`render`, command receipts, result IDs, event reads/subscriptions where useful, and typed not-found/conflict/integrity/idempotency errors. Remove raw registry injection, storage adapters, thread/session/plan types, and ordered-export compatibility promises.
- Mount kernel-owned `projects create|list|show|update|select` and non-authoritative preference selection.
- Mount timeline-pack `timelines create|list|show|save|copy|archive|history|diff`, with the shots pack nested as `timelines shots list|create|add|remove|reorder` where the editor journey needs CLI access.
- Mount kernel-owned `media import|list|show|verify|relocate|relate`, with the references pack nested as `media references create|update|archive|associate|link|list|show`.
- Mount kernel-owned `tasks create|list|show|cancel|retry|events` and `runs list|show --evidence|cancel|retry-failed|events`. Claim/start/heartbeat stay internal; no plan/step/next/ack/skip/hook command appears.
- Establish one machine-readable envelope for this new API. Every mutation accepts an idempotency key or generates and returns one.
- Exercise exact-media journeys end to end: import → reference primary/association/link → generation input association; import → shot add/reorder/remove; run evidence lookup; multi-output primary uniqueness; timeline history/diff.
- Through the public SDK/CLI boundary, rerun media import/relocate/relate, reference primary/associate/link, and shot reorder conformance: registered order, stream/project heads, atomic projection/location/relation/association/order plus receipt, identical replay, mismatched-key rejection, and representative statement-boundary old-or-complete behavior.
- Wire executable command help and docs to the five completed domain families only. `serve`, `doctor`, and `backup` do not appear as product commands until their Sprint 6 implementations are functional; placeholders do not satisfy either sprint gate. Developer pack/element/model tools remain clearly outside the product family promise.

**Parallel lanes:** SDK/service models; project/timeline/media CLI; task/run CLI; reference/shot journeys and clean-local smoke. Shared conformance tests prevent handler-local behavior.

**Deliverable:** A user can create/select a fresh project, import/verify media, manage references and shots, create/save/history a timeline, invoke supported capability work, and inspect/cancel/retry tasks/runs through the reduced SDK and five domain CLI families, all using the shared envelope.

**Acceptance gate:** GA item 8 passes; all media and editorial command conformance cases pass through the public boundary; all mutation receipts and typed errors are stable; handlers use services/repositories only; top-level product help contains the five functional domain families and no placeholder operational command, sixth domain family, plan/session/thread/importer compatibility alias; a local project/media/reference/timeline smoke requires no account or provider secret. The supported OS/browser/package matrix is fixed in the [v10 implementation decision artifact](astrid-v10-implementation-decisions.md) before Sprint 6 begins.

### Sprint 6 — Productization, operations, and Phase 2 gate

**Goal:** Turn the integrated repositories and editor into a cleanly installable, recoverable, sole-authority local product.

**Work items and dependencies**

- Implement kernel-owned `serve` with lazy, dependency-ordered migration of the application database and installed packs plus data-directory setup, repository bridge startup, optional project/bind flags, and the chosen packaged/current editor path. Local create/edit/import works without Node as a user prerequisite if the package promise says so.
- Implement kernel-owned `backup create`: briefly pause semantic writes under the service writer lock, use SQLite online backup, copy managed media, exclude caches/staging/logs/packs/secrets/external-local media, and resume safely. Because every installed pack shares the database and kernel media root, backup needs no pack-specific path. It accepts or generates and returns an idempotency key in the shared stable envelope; identical request/key replay returns the original result, while mismatched canonical request reuse fails before mutation.
- Implement staged `backup restore`: validate quick check, foreign keys, schema compatibility, and referenced managed media before atomic activation. It obeys the same idempotency-key, replay/mismatch, and stable-envelope contract as every other mutation. Statement-boundary activation tests prove old-or-complete behavior; a failed or mismatched restore leaves the current installation untouched.
- Implement kernel-owned `doctor [--json]` as read-only quick check, foreign-key check, core/installed-pack schema version compatibility, and resolved data/media paths—no speculative repair framework.
- Enforce zero-secret core use and provider credential resolution: explicit option → process environment → supported OS keychain. Remove cross-agent/unrelated-workspace `.env` scavenging and prevent secrets entering specs, events, receipts, logs, backups, or unallowlisted child environments.
- Delete old semantic modules, fixtures, optional dependencies, CLI aliases/help, FSA writer, and Supabase product paths in replacement commits. Run the build/import lint that rejects removed FSA/Supabase authority imports, kernel-to-pack dependencies/FKs, and pack-owned writers.
- Run bridge contracts and editor provider/persistence suites from the packaged service layout; verify all supported editor mutations retain internal receipts.
- Apply and verify the supported OS/browser/package matrix already fixed at the Sprint 5 gate under v10 §7.
- Add the three completed operational families to product help only after their implementations pass conformance. The executable surface then contains exactly eight top-level families—the five S5 domain families plus functional `serve`, `doctor`, and `backup`—with no placeholder counted.

**Parallel lanes:** Serve/package; backup/restore/doctor; secrets and clean-account setup; authority deletion/import lint and packaged editor tests.

**Deliverable:** Install a release candidate into a clean user context, run `serve`, edit a fresh project, idempotently create and restore a backup through stable envelopes, and run `doctor`, all without accounts, cloud services, Docker, Node setup, or provider secrets for local functions. Executable help exposes exactly eight functional product families.

**Acceptance gate:** The full v10 §3 **Phase 2 gate** passes. The bridge and existing editor contract/provider test lanes are green; SDK/CLI use services; `serve`, `doctor`, and `backup` are functional and executable help contains exactly eight families; backup create/restore pass generated-or-accepted key, identical replay, mismatched-key rejection, stable-envelope, and restore old-or-complete tests; the clean install reaches an editable project; FSA/Supabase semantic writers are absent from the shipped path. Artifact tests prove secrets enter none of task specs, events, receipts, logs, or backups, and that child processes receive only explicitly allowlisted capability environment variables.

### Sprint 7 — Dogfood and destructive hardening

**Goal:** Complete a representative fresh project only through the shipped surface and turn every discovered failure into a regression.

**Work items and dependencies**

- Dogfood: create/select project; import real bytes; verify/relocate media; create references and shots; run real generation, rendering, multi-output selection, synchronous understanding, and dependent fan-out; edit timelines through the editor; inspect tasks/runs/evidence; backup, destroy the disposable installation, restore, and continue editing.
- Inject process kills around timeline save, task completion/media placement, fan-out, backup, and restore. Restart must show old-or-complete state and garbage-collect unreferenced staging without inventing rows.
- Exercise same-byte dedupe, path mutation, missing managed/external locations, corrupt bytes, and the user-facing external-local backup warning/relocate-to-managed journey.
- Exercise two-tab timeline saves plus heartbeat load, CLI mutation, and completion under bounded busy retry/backpressure.
- Rerun all five task races against production service wiring, including output absence/presence and terminal non-resurrection.
- Verify fan-out partial failure, hard/soft dependency gating, stable ordinals, continuation replay, terminal continuation rejection, group progress, cancel, and retry-failed.
- Restore a database plus managed-media backup, run `doctor`, open the editor, Range-play assets, and verify hashes.
- Audit the dogfood path for hidden developer tools, direct SQL/files, provider keys, old project semantics, or manually repaired state. Those are defects, not documented steps.

**Parallel lanes:** One rotating dogfood driver; media/crash hardening; executor/contention hardening; editor/restore/recovery hardening. Engineers fix across lanes from shared evidence rather than preserving ownership silos.

**Deliverable:** A representative completed project and a checked-in evidence checklist covering v10 §5.3 items 1–10 against the unpackaged release candidate, plus provisional source/build absence proof for item 11. Item 12 retains its Sprint 3 source/test proof and awaits the installed-artifact rerun in Sprint 8.

**Acceptance gate:** GA items 1–10 pass at least once in integrated form, item 11 has provisional source/build proof only, and item 12 retains the Sprint 3 factoring proof. Final installed-artifact proof for items 11–12 remains in Sprint 8. No open severity-one/two correctness defect remains. Lower-severity issues are explicitly dispositioned without violating v10. Failure here is what normally consumes Sprint 8 buffer or triggers Sprint 9; it is not solved by shrinking the acceptance matrix.

### Sprint 8 — Release artifact hardening and GA

**Goal:** Prove the supported release artifact, not the source tree, and close the normal GA gate.

**Work items and dependencies**

- Build/install the actual artifact on every supported OS/browser/package combination and a clean account. Run project, editor, timeline, media, references, backup, and doctor with zero secrets.
- Run the focused core repository, bridge contract, current editor provider/persistence/draft/poll, real generation/render, crash/race/contention, backup/restore, and import-lint suites from the artifact layout.
- From the artifact layout, remove each pack in turn and rerun the entire kernel suite; verify the remaining manifest-derived catalog and registrations contain no stale pack dependency.
- Rehearse one forward application migration and too-new-schema handling. Verify failure is clear and nonmutating; do not add compatibility for old Astrid authorities.
- Audit installed files, imports, entry points, help, dependencies, default directories, and network calls. No old authority or removed top-level family may ship; no dormant account/cloud/remote-worker/experiment/plan schema may appear.
- Fix release-candidate defects and rerun the smallest relevant gate immediately, then the full GA matrix before tagging.
- Publish the completion evidence: schema/index catalog, receipt/idempotency proof, capability journeys, zero-task evidence, fan-out, race/crash report, editor contract/provider lane, media verification, reference/shot round trip, restore/doctor, clean-install log, and artifact authority audit.

**Parallel lanes:** Packaging/platform matrix; final editor and bridge suite; core failure suites; artifact/help/import audit. A single release owner controls the candidate and evidence set.

**Deliverable:** A release candidate whose installed artifact has one semantic authority and passes v10 §5.3 plus the pack factoring/deletion proof without test skips or manual repair.

**Acceptance gate:** Full v10 §3 **Phase 3 gate** and all twelve §5.3 acceptance items pass against the artifact. Any material repository/atomicity failure—including timeline, executor, media, references, shots, backup/restore, or systemic contention—activates Sprint 9; a bridge/editor, supported-platform, or package/runtime failure activates Sprint 10. Otherwise ship.

### Sprint 9 — Conditional repository/atomicity correctness reserve

**Goal:** Repair any material repository or atomicity invariant defect discovered after integration without weakening the model, including event/receipt, timeline, executor/fencing, media, references, shots, backup/restore, and systemic SQLite contention.

**Work items:** Root-cause the triggered failure; repair it at the repository or operational atomicity boundary; expand statement-boundary/race/contention/fixture coverage; replay affected timeline, media, reference, shot, dogfood, backup, and restore journeys; check that the fix did not introduce a second writer, generic repair language, plan semantics, or schema dumping ground. If a forward migration is needed, rehearse it from every development schema that could exist in a release candidate.

**Parallel lanes:** Only independent remediation and regression lanes justified by the trigger. No feature lane opens.

**Deliverable:** The failed original sprint gate plus the complete Sprint 8 GA evidence rerun.

**Acceptance gate:** Root cause is closed, regression is deterministic, all v10 invariants remain intact, and the packaged artifact is green.

### Sprint 10 — Conditional editor/platform/package reserve

**Goal:** Repair only supported editor/bridge, browser/OS matrix, clean-install, or package/runtime failures that could not safely fit in the normal release sprint.

**Work items:** Fix only editor/bridge, declared-matrix, or package/runtime failures; rerun provider/draft/poll/persistence and Range behavior; repeat clean-account zero-secret setup, executable-help/import audit, and artifact tests; remove accidental runtime dependencies or old modules. Repository and backup/restore correctness defects route to Sprint 9. Do not expand the support matrix during this sprint.

**Parallel lanes:** Package/runtime and editor/bridge regression may proceed independently, converging on one artifact.

**Deliverable:** A clean installed artifact on the declared matrix with a complete GA evidence pack.

**Acceptance gate:** The Sprint 8 gate passes with no scope exception. Ship or explicitly replan; do not roll a known correctness failure forward as GA.

## 4. Team-sizing variants

### 4.1 Three engineers

Preserve the eight-sprint work order but forecast roughly eleven to thirteen sprints. The event core still gets two engineers in Sprint 1; the third owns project/timeline repositories and the thin bridge slice, so the slice may finish late in the sprint but must still gate executor/media work. In the next stage, executor and media no longer have full parallel teams: one engineer owns executor, one owns media, and one owns integration/constraints; capability adaptation follows rather than fully overlapping.

References/shots must complete inside Phase 1 before the full bridge/editor stage begins. SDK and CLI can overlap once their read models are stable, but packaging/backup/doctor should not compete with unfinished editor correctness. A practical mapping is: core foundation (2 sprints), executor/media (2), Phase 1 integration including references/shots (2–3), full bridge/editor contract/provider work (1), CLI/SDK (1–2), productization (1), dogfood/release (2): eleven to thirteen sprints. The conditional reserve remains available. What slows is concurrency, not the gates or product scope.

### 4.2 Solo engineer

Keep two-week review points but do not pretend each base sprint fits into one solo sprint. Forecast approximately 20–26 calendar sprints for 32–46 PW once integration and release work are included. The order becomes strictly vertical:

1. schema/migrations → writer/event/receipt kernel → project/timeline repository → thin bridge save;
2. task/attempt lifecycle and races;
3. media storage/import/crash consistency;
4. task completion plus real generation/render;
5. runs/evidence/fan-out;
6. media-reference and shot repositories as one exact-media editorial sequence, then the Phase 1 gate;
7. full bridge/editor contract/provider lane;
8. SDK, then the five domain CLI families;
9. `serve`, packaging, backup/restore, doctor, exact-eight help, and removal;
10. dogfood, destructive hardening, and release artifact proof.

For a solo engineer, “Sprint 3” in the base map is a milestone composed of several two-week iterations, not a request to squeeze multiple workstreams into one. Preserve an external review of the event core, transition/fencing logic, and final artifact because those are poor candidates for self-review only.

## 5. Risks and buffer policy

| Risk likely to blow a sprint | Early signal | Mitigation | Where the slip lands |
| --- | --- | --- | --- |
| Event/receipt core is under-specified or rushed | Handler-specific SQL appears; receipts omit IDs; crash tests expose partial heads/projections; idempotency semantics differ by repository | Pair two engineers for all of S1; freeze canonical request/event/receipt contracts; statement-boundary tests on the first two commands; block executor/media semantics on the gate | S1 has protected scope. Minor repair consumes S2 integration slack; material late defect activates S9 |
| SQLite contention exceeds bounded service behavior | Two-tab saves, completion, or CLI mutations leak busy errors, starve, or hold `BEGIN IMMEDIATE` across slow work | One in-process queue; short transactions; measured bounded retry/backpressure; concurrent editor + heartbeat + CLI + materialization tests in S3 and S7 | Local tuning stays in the owning sprint; systemic contention or transaction-boundary rework activates S9 |
| Editor wire contract drifts | Thin provider test cannot round-trip fields; numeric version or error envelope differs; internal receipt leaks into response | Exercise project → timeline save in S1; keep the frozen route/payload/error table beside bridge contracts; run current provider tests continuously | S4 owns full repair; S8 has ordinary regression buffer; declared-platform surprises activate S10 |
| Media placement is not crash-consistent | Orphan published bytes, rows pointing to absent files, staging treated as truth, mutation undetected | Quarantine/hash/probe/fsync/place; repository transaction owns rows; startup GC only deletes unreferenced staging; inject failure at placement/commit boundaries | S2–S3 absorb normal fixes; integrated defect activates S9 |
| Executor races resurrect or double-materialize work | Stale attempts complete; terminal retry mutates state; cancellation output differs nondeterministically | One transition service; `status_version` fences; terminal tombstones; five named races before and after real adapters; ordered output uniqueness | S3 cannot close Phase 1; S7 rerun catches wiring regressions; severe late issue activates S9 |
| Direct run grouping is too weak | Real fan-out cannot express dependency/partial failure/retry, or run status drifts | Prove a real multi-task journey in S3; add only measured run/task read fields; implement continuation CAS and derived progress; never restore steps | S3 integration slack, then S9 if found during dogfood |
| Capability code writes project files directly | A capability publishes outside quarantine/manifests, mutates project files, or bypasses repository materialization | Enforce quarantined outputs plus declared manifests with one real generator/renderer; reject direct project-file mutation in integration tests | Correct during S3 adaptation; any late materialization/authority violation activates S9 |
| JSON fields become dumping grounds | Payloads grow without bounds, handlers issue ad hoc JSON queries, or domain invariants hide in opaque blobs | Enforce S1 payload/event bounds and typed read models for current editor/CLI queries; promote only observed indexed fields and keep diagnostics file-side | Ordinary correction stays in the owning repository sprint; systemic late schema/read-model correction activates S9 |
| Packaging or clean-install assumptions are wrong | Source tests pass but artifact imports old modules, needs Node/provider key, or help exposes aliases | Begin package path in S6; test built artifact and clean user context; import/help/network audit; freeze supported matrix | S8 is normal package buffer; S10 is explicit platform/package reserve |
| Backup misses externally referenced media | Restored DB is valid but user assets are absent | Managed copy remains default; surface realms/missing risk; offer `media relocate` to managed before backup; document external-local exclusion | S6 behavior, S7 dogfood; no scope expansion to capture arbitrary external files |
| Scope regrows around deferred systems | Stories mention experiments, remote GPU, publication, old import/history, plans, or compatibility | Every story cites a v10 phase/table/family/acceptance owner; reject work without one | It does not consume buffer; it returns to the post-GA backlog |
| Pack boundary erodes into an Astrid-specific kernel | A kernel migration/FK imports a pack, a pack opens SQLite directly, vocabularies are unnamespaced, or kernel tests require all three packs | Enforce FK-direction and no-writer import lint in S1; register manifests through one path; run the reusable conformance and delete-a-pack tests in S3 and S8 | S1/S3 gates block dependent work; a late artifact violation activates S9 |

Buffer policy is explicit. Each sprint reserves integration/review capacity rather than planning all eight gross PW as feature work. Sprint 8 is a normal stabilization sprint, not optional polish. Sprints 9–10 exist for high-case variance. Buffer may close failures in existing gates; it may not add deferred features, broaden the support matrix, or substitute manual procedures for automated acceptance.

## 6. Sprint 1 concrete backlog

The following tickets are the starting backlog. Ticket order is dependency order; lanes may work in parallel only where the dependency column permits it.

| ID | Ticket | Concrete acceptance | Dependency / lane |
| --- | --- | --- | --- |
| **S1-01** | Land layered v10 creation migrations | `schema_migrations.pack` defaults to `core` with composite PK `(pack, version)`; fresh Astrid DB has 14 core + 6 installed-pack tables and every §2.2 named index; PRAGMAs are effective; forbidden plan/session/legacy tables are absent | First; A+B pair |
| **S1-02** | Build forward migration runner | Records pack/version/name/checksum; rejects changed checksum; applies core then packs in declared dependency order, each once; too-new core or installed pack fails clearly/read-only without mutation | S1-01; A |
| **S1-03** | Add pack-aware catalog/conformance fixture | CI derives the expected `sqlite_master`, FK, check, partial-index, and per-pack migration catalog from core + installed-pack manifests rather than a hardcoded 20; kernel FKs into packs fail lint | S1-01; B |
| **S1-04** | Implement kernel write queue/UoW | All semantic mutations enter one queue and one short `BEGIN IMMEDIATE`; pack repositories receive only the kernel UoW; busy handling is bounded; tests/import lint reject nested, parallel, or pack-owned direct writers | S1-01; A+B |
| **S1-05** | Register stream/event/command vocabularies and packs | Kernel DDL has no hardcoded `stream_type` enum; repository validation uses core and pack registries; one startup `register_pack()` installs manifests/repositories; namespaced project/timeline/shot/reference event and command kinds validate; project/task/run/timeline streams enforce aggregate/type/project; sequence allocation is gap-free per committed command | S1-04; B |
| **S1-06** | Implement canonical request hashing | Canonical equivalent requests hash equally; meaningfully different bytes hash differently; payload/event size limits are enforced | S1-04; A |
| **S1-07** | Implement command receipts and replay | One receipt captures transaction ID, stream sequence, project range, ordered event IDs, complete result JSON; same retry returns it; changed request/key pairing raises typed mismatch | S1-05/S1-06; A+B |
| **S1-08** | Project repository vertical command | `create/list/show/update` use project stream, event, projection, and receipt atomically; slug uniqueness and idempotent create behavior tested | S1-07; C |
| **S1-09** | Timeline-pack create/list/show repository | Registered pack repository creates the timeline stream and initial document/registry through the kernel UoW; UUID identity and supported ULID address are represented; list/load read models match bridge needs | S1-07/S1-08; C |
| **S1-10** | Timeline whole-document CAS save | `document_json` + `asset_registry_json` + event + head + receipt commit together; expected head is numeric version; stale request changes nothing | S1-09; C with A review |
| **S1-11** | Statement-boundary crash harness | Kill/fail at each statement boundary for project create and timeline save; reopen database and assert either no command effect or complete event/head/projection/receipt | S1-08/S1-10; B |
| **S1-12** | Initial writer-contention test | Two saves from same version produce one success/one 409; bounded busy handling does not leak 500 or partial state | S1-10/S1-11; B+C |
| **S1-13** | Thin frozen bridge routes | `/health`, `/projects`, timeline list/load/save preserve existing fields and envelopes; internal receipt remains internal; missing resource keeps current 404 form | S1-08–S1-10; D |
| **S1-14** | Early real editor-provider test | Current `AstridBridgeDataProvider` performs list/load/save/reload against repository bridge; stale save is 409 `timeline_version_conflict`; restart retains save | S1-13; D+C |
| **S1-15** | Remove/guard first replaced authority path | The thin routes cannot fall back to file/JSONL/FSA/Supabase semantic writes; regression test proves repository method invocation | S1-13; D |
| **S1-16a** | Freeze media layout and relation vocabulary | The [v10 implementation decision artifact](astrid-v10-implementation-decisions.md) names managed root, staging, reference-in-place/relocation policy, and every allowed media relation kind before S2 | Parallel discovery; whole team signs off before S1 gate |
| **S1-16b** | Freeze fan-out contract | The decision artifact fixes maximum child count, continuation envelope, expected-head/CAS fields, ordinal rules, and receipt linkage before S2 | Parallel discovery; A+B validate transaction fit |
| **S1-16c** | Freeze evidence and reference vocabularies | The decision artifact names every evidence kind and reference kind/role/link kind before S3 repository work; later changes reopen this gate | Parallel discovery; repository owners sign off |
| **S1-16d** | Schedule platform-matrix decision | The decision artifact names an owner and Sprint 5 deadline for exact OS/browser/package targets, before Sprint 6 Phase 2 work begins | Parallel discovery; release owner |
| **S1-17** | Sprint gate script/checklist | One command creates a fresh DB, verifies the manifest-derived layered catalog and pack-boundary lints, runs receipt/replay/crash/contention suites, starts the bridge, and runs the focused editor save test; output is retained in CI | All tickets; integration owner |

### Sprint 1 review checklist

The sprint review must answer “yes” to each item:

- Does every mutation shown use the same writer queue, event registry, receipt code, and repository transaction boundary?
- Can the team show the exact event IDs, project sequence range, stream head, projection, and receipt from a project create and timeline save?
- Does replay return the original result, and does mismatched key reuse fail before mutation?
- Does a stale editor save return 409 while leaving document, registry, heads, events, and receipts unchanged?
- Does every injected crash reopen to old-or-complete state?
- Does the editor provider test use the repository-backed bridge rather than a fake or old adapter?
- Are executor and media lanes consuming a stable kernel instead of copying provisional transaction logic?
- Do the 14-table kernel and three in-tree packs register through one startup path, with independent dependency-ordered migrations and no kernel FK/import into pack code?
- Does the reusable pack conformance kit cover replay, mismatched-key rejection, statement-boundary crash behavior, and same-project assertions, while lint rejects every pack-owned writer?
- Are the media layout/relation kinds, full fan-out contract, and evidence/reference vocabularies closed in the required decision artifact, with a named Sprint 5 platform-matrix owner/deadline?

If any answer is no, Sprint 1 is not complete. The correct response is to finish the foundation, not to start more dependent work and hope integration will clarify it later.
