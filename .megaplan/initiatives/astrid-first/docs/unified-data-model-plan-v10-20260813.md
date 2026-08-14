# Unified data model plan v10: greenfield Astrid without plans or legacy tax

**Date:** 2026-08-13  
**Status:** decisive greenfield implementation plan; supersedes v9  
**Decision:** build the standalone local product directly on one 20-table SQLite authority, use the existing Reigh bridge wire shape, delete legacy authorities instead of importing them, and replace plan/step orchestration with runs that directly group immutable tasks  
**Foundation:** **tasks execute; everything else is an event; every exact asset is media; references add project semantics to media**

**Revision:** Revised 2026-08-14: plugin/generalizable layering (kernel + packs) folded in.

## Executive summary

V10 removes the preservation project that dominated v9. There are no existing-user, historical-parity, or legacy-data promises. Astrid starts from a fresh SQLite database. Old project, timeline, run, thread, session, plan, lease, event-chain, audit-ledger, Supabase, and editor FSA authorities are not migrated or conditionally supported; their modules and storage-specific tests are deleted as the replacement paths land. The only ingestion retained is ordinary media import: walk files, hash and probe their bytes, copy them into managed storage by default, and create `media` and `media_locations` rows through the normal repository transaction.

The schema falls from v7/v9's 22 tables to **20 tables** and is now explicitly layered as a 14-table agent-agnostic kernel plus six Astrid domain tables supplied by three in-tree packs: timeline, shots, and references. `run_steps` and `run_step_tasks` are removed because the user's replacement of plan/steps eliminates their only independent justification. A `run` is now a coordination and observation container: the receipt for one command returns a `run_id`, directly created child `task_id`s, and any evidence IDs. Child tasks carry nullable `run_id` and `run_ordinal`; `task_dependencies` expresses real execution ordering or DAG edges. Inline work can produce run evidence without creating a task. Fan-out creates one run and N independently fenced tasks, not a plan, a synthetic parent task, or a row per pseudo-step.

The hard foundations remain: task admission, task/event separation, atomic command receipts, project-ordered events, timeline whole-document CAS, byte-SHA-256 media identity, ordered task outputs, attempt fencing, terminal immutability, crash injection, and a single repository-owned writer. Media is explicitly kernel citizenship: source files, diffs, logs, reports, and generated assets all use the same exact-byte model, so the executor-to-media coupling in `task_outputs.media_id` is portable rather than Astrid-specific. References, media-first lineage, shots, and file-side manifest boundaries also remain. These are product semantics and correctness boundaries, not legacy accommodations.

The kernel is intended for reuse by other agents. Astrid is the kernel plus its timeline, shots, and references packs; a future software-engineering agent can use the same kernel with its own packs without changing any kernel table. V10 establishes that boundary with in-tree manifests, independent migrations, registries, import rules, and a reusable conformance kit. It deliberately does not build a dynamic plugin loader before a second agent exists.

The Reigh editor remains the frontend, so its existing bridge route and payload contract remains. What disappears is v9's five-boundary continuity program, frozen timing ceremony, golden-corpus migration suite, and parity veto. The ordinary gate is now the editor's provider/persistence tests plus Astrid bridge contract tests against the new repositories. Editor FSA persistence is deleted outright; there is only one backend mode.

Delivery has three phases: build the core, wire the editor and essential CLI, then dogfood and ship. The scope covers the actual product—schema/events, executor, media, timelines/bridge, runs/evidence, references/shots, SDK/CLI, packaging, tests, and release hardening—and excludes importer diversity, plan translation, API/CLI compatibility, five-phase continuity proof, 553-test classification, and teardown-tracing machinery.

## Changes vs v9

1. Replace v9's preservation posture with a clean-database, delete-old-code posture. There is no legacy project cutover, flip marker, rollback window, compatibility writer, or source authority classifier.
2. Delete the multi-source importer. `media import` is a product command, not migration machinery; it imports bytes and basic probe metadata only.
3. Delete `run_steps` and `run_step_tasks`; reduce the normative schema from 22 to 20 tables.
4. Replace all `Step`/`TaskPlan` group, repeat, `for_each`, supersede, cursor, acknowledgement, hook, and lease semantics. They are neither preserved nor translated.
5. Make `runs` direct group handles. `tasks.run_id` and `tasks.run_ordinal` represent membership; `task_dependencies` represents execution ordering.
6. Remove both old `run.json` dialects, audit-ledger import, timeline event-chain import, legacy aliases, parity reports, head-sidecar rebuilding, and all related migration tools.
7. Replace the nine-stage 0/A–I delivery sequence with three phases: core, editor plus CLI, dogfood plus ship.
8. Retain the existing editor bridge wire shape, but replace the five-lifecycle continuity harness with the editor's existing provider/persistence tests and focused bridge contract tests in normal CI.
9. Delete editor FSA mode unconditionally. There is no per-project authority switch or fallback.
10. Replace the 553-test migration/classification program with tests for new code plus a small, named set of valuable semantic tests.
11. Replace the 23-family product CLI with eight top-level families: `projects`, `timelines`, `media`, `tasks`, `runs`, `serve`, `doctor`, and `backup`.
12. Reduce backup to SQLite online backup plus a managed-media directory copy; reduce `doctor` to SQLite quick check and foreign-key validation.
13. Keep executable-distribution pack, component, element, model, and tool manifests file-side; do not add catalog tables for them. Database schema packs are also file-described, but their manifests explicitly own forward-only migrations and registration metadata.
14. Replace v9's preservation-release framing with direct product construction. Delete the "deep integration" scenario entirely.

## 1. Cut list

The review in OpenRouter chat message [3] is correct about the dominant cost: v9 was primarily a safe migration and compatibility program. V10 adopts that demolition with two deliberate modifications. First, the bridge wire contract stays because Reigh is the current client, not because old data deserves preservation. Second, references and shots remain in the schema because they are part of the media-first product model; their top-level CLI polish can wait or be nested under an essential family.

`CUT` means delete the behavior and its writer/tests rather than emulate it. `SIMPLIFY` means retain the product outcome through a smaller mechanism. `KEEP` means the element remains load-bearing in the greenfield product.

| V9 element or exact mechanism | Decision | V10 rationale and replacement |
|---|---|---|
| Multi-source importer and Stage G atomic cutover | **CUT** | No old authority is a supported input. There is no inspect/classify/verify/flip state machine. |
| Basic media import | **KEEP, SIMPLIFY** | `media import <path>` walks files, hashes/probes them, copies or explicitly references them, and creates normal rows/events. It imports no semantic history. |
| `project.json`, `sources.json`, per-source `source.json` semantic import | **CUT** | Old metadata and path-derived IDs are discarded. Import the underlying bytes if useful. |
| `assembly.jsonl`, head/checkpoint, `assembly.json`, identity/display, registry/assets, timeline manifest import | **CUT** | New timelines start in SQLite. No event-chain verification, projection recovery, alias resolver, or head-sidecar rebuilding. |
| Thread-era `runs/<id>/run.json` v1 and project `run.json` v2 | **CUT** | There is one new run dialect in the database and no dialect classifier. |
| Run `events.jsonl` and audit `ledger.jsonl` import | **CUT** | No legacy run/audit events are translated into new events or evidence. |
| Timeline/run audit hash-chain golden fixtures | **CUT** | New v10 events use the v7 project/stream ordering contract; no legacy hash reproduction is required. |
| `bootstrap inspect/import/verify`, `timelines migrate-events`, flip markers, parity reports | **CUT** | `bootstrap` ceases to be a family. The only ingestion command is `media import`. |
| Stage 0 authority census and frozen five-lifecycle continuity harness | **CUT** | There is no old/new lifecycle to compare and no cutover boundary. |
| Bridge wire contract in v9 §7.1 | **KEEP** | Reuse the working editor provider: routes, config/registry payload, numeric `config_version`, CAS conflicts, typed errors, and asset Range serving. |
| Exact v9 timing budget, ETag/Last-Modified pins, five boundary reruns, golden corpus program | **CUT** | Keep current client timings as implementation details. Test behavior the editor consumes, not accidental headers or migration phases. |
| Editor provider, draft recovery, polling, and persistence tests | **KEEP, SIMPLIFY** | They are normal current-client tests. Run them once against the repository bridge in CI, not as a special continuity program. |
| Editor FSA data-provider/write mode | **CUT** | Delete it unconditionally. The bridge is the sole semantic editor path; file selection may still provide bytes to media import. |
| 553-test inventory and case-by-case compatibility classification | **CUT** | New modules get new tests. Selectively port only task races, hash/probe vectors, bridge provider behavior, and capability/result contracts. |
| Importer-only legacy fixtures; task/session/thread storage layout tests | **CUT** | Delete with their implementations. A corpse does not retain a vote in CI. |
| Teardown static/runtime trace evidence pack | **CUT** | Delete old modules and their imports at repository level. Keep one cheap import-lint rule preventing new product imports of Supabase and removed FSA authorities and enforcing the kernel/pack dependency and writer boundary. |
| Nine-stage 0/A–I program | **CUT** | Replaced by the three outcome phases in §3. |
| Deep-integration scenario | **CUT** | Lossless legacy semantics are not an offered scope. |
| `run_steps` | **CUT** | Its ordered-stage model is plan semantics. Without plans, run status, child tasks, dependencies, events, and evidence cover the actual reads. |
| `run_step_tasks` | **CUT** | Direct `tasks.run_id`/`run_ordinal` gives indexed group membership with two fewer tables overall. |
| `Step`, `TaskPlan`, group/repeat/`for_each`/supersede, cursor, `next`, `ack`, `skip`, hooks | **CUT** | Do not preserve, translate, or import them. Repeated/fan-out work is explicit immutable tasks; ordering is dependencies; decisions are events/evidence. |
| Plan mutation creates a replacement task | **MODIFY** | There is no plan mutation. A changed executable request always creates a new immutable task; an event may record that the caller replaced an earlier task. |
| Runs separate from tasks | **KEEP, SIMPLIFY** | A run is a command's coordination/provenance container and group handle; it may contain zero or many tasks and evidence. It has no step graph. |
| Fan-out and group cancel/retry | **KEEP, SIMPLIFY** | One bounded command creates a run plus N tasks with unique ordinals. Progress is derived from child status; cancel/retry targets eligible children and returns receipts. |
| Task admission rule and attempt fencing | **KEEP** | Immutable, executable, independently claimable work remains the line between tasks and events. |
| Atomic events/projections/outputs/command receipts | **KEEP** | Retry determinism and crash safety are cheap to establish before use and expensive to retrofit. |
| Timeline whole-document config-plus-registry CAS | **KEEP** | It is the real editor concurrency boundary. Stale saves return 409 without mutation. |
| Media byte-hash identity and `media`/locations/relations/outputs | **KEEP** | This is the universal asset foundation, independent of legacy data. Path hashes never become identity. |
| References and shots schema | **KEEP** | They preserve project semantics over exact media and current storyboard placement. Top-level CLI families are unnecessary. |
| Evidence as a separate concept | **KEEP, SIMPLIFY** | Evidence remains queryable by run and may point at the task that produced it; it has no `run_step_id` and no top-level CLI family. |
| Project/timeline/event/task/media/run/reference repositories | **KEEP** | These are the single semantic writer boundary. CLI, SDK, bridge, and executor call them. |
| Project/source, timeline, task-plan, thread/session, old run/event subsystems | **CUT** | Do not adapt their storage engines. Delete them as their new repository journeys work. |
| Session, lease, `current_run.json`, inbox, thread/variant authorities | **CUT** | Attempts own execution leases; preferences select projects; typed commands own decisions; active state is queried. |
| Supabase append/timeline I/O, hosted worker, RunPod, publication, cloud sync | **CUT from local product / DEFER feature** | No code path or dormant schema in local GA. A future approved feature must target the shipped repositories and attempt fence. |
| Experiments product and its file-state machine | **DEFER** | Not imported or integrated. Existing files may remain outside Astrid; selected bytes can be imported as media. |
| Pack/component/element/model manifests and install state | **KEEP FILE-SIDE** | Confirm the chat review's exception: these are executable distribution inputs, not user-domain data. Snapshot selected IDs/digests into task/run JSON. |
| Run logs, debug captures, request/result and provenance attachments | **KEEP FILE-SIDE, SIMPLIFY** | They are optional immutable diagnostics. Anything product-critical becomes managed media or database state; backup need not inventory every scratch file. |
| `plan.md`, README, notes, exports | **KEEP FILE-SIDE** | Human-authored or explicit output files are not semantic database authorities. |
| V9's 23-family CLI and old 41 gateway verbs | **CUT** | Build the eight-family surface in §4. No compatibility aliases, migration notices, or stable JSON promises for developer tools. |
| Standalone `shots`, `references`, `evidence`, `events`, `executors`, `renderers`, `orchestrators`, `packs`, `elements`, `models`, `themes`, `skills`, `repair`, `bootstrap`, `setup`, `status` families | **CUT or FOLD** | Nest current product actions under essential families; keep authoring/distribution utilities as explicitly unsupported developer entry points. |
| Existing SDK lazy discovery, typed invoke/generate/render and errors | **KEEP, SIMPLIFY** | Preserve useful semantic contracts, not the ordered 32/35-name export list, raw registry injection, or storage adapters. |
| CLI/SDK compatibility and deprecation program | **CUT** | This is a major greenfield surface. Document the new API; do not emulate old names. |
| Backup manifests, verification catalog, restore choreography | **CUT** | Backup is an online database snapshot plus media-directory copy under the writer lock. No file-classification manifest. |
| `doctor` invariant catalog and generic `repair` family | **CUT** | `doctor` runs SQLite `quick_check` and `foreign_key_check` and reports paths/versions. Add a narrow repair only after observing a real failure mode. |
| Secrets resolver framework and cross-agent `.env` scavenging | **SIMPLIFY** | Delete scavenging. Resolution is explicit option, then process environment, then OS keychain if supported. Core use needs no secret. |
| Pack/media implementation primitives: SHA-256, probe, staged/atomic byte placement | **KEEP** | Reuse verified low-level code behind the new repository; replace only its disconnected indexes and unsafe semantic writers. |
| V9 disposition matrix as an ongoing 115-row program | **CUT** | This table is the final decision record. Old INTEGRATE rows either map to the new eight-family product or are deleted; KEEP-FILE-SIDE decisions remain; DEFER rows stay absent. |

The safe corner-cutting rule is now simple: preserve semantics that the new product actively uses; discard storage history and interface compatibility. If an old subsystem does not contribute executable capability code, proven byte handling, the current editor contract, or a file-side package definition, it does not cross into v10.

### 1.1 Complete v9 disposition-row ledger

For literal coverage, this compact ledger names every row from v9 §1.1–§1.3. Rows are grouped only when their v10 disposition and rationale are identical; the decision details above remain normative.

| V10 | Exact v9 matrix row names | One-line rationale |
|---|---|---|
| **SIMPLIFY** | Gateway/session gate; `projects create/ls/show/update/theme/source/register-source`; `projects select/default` | Keep repository CRUD/preferences; delete session gating and fold sources into media. |
| **CUT** | `projects cost`; `projects export`; `projects list/edit` remote Reigh mode; `attach`; `sessions ls/detach/takeover/prune`; `status` | Not in the eight-family v1 surface; remote/session behavior has no replacement obligation. |
| **SIMPLIFY** | `timelines ls/create/show/rename/finalize/tombstone/purge/set-default`; Timeline edit verbs (`clip`, `transition`, `effect`, `theme`, `track`, `audio`, `arrangement`); `timelines registry sync` | Keep current CRUD/save/edit outcomes through timeline repositories; cut old vocabulary and sidecar mechanics. |
| **MODIFY** | `timelines history/diff/audit/preview/who-edited` | Keep history/diff; omit audit/preview/who-edited until a current journey needs them. |
| **CUT** | `timelines export/cost`; `timelines migrate-events`; `timelines push/pull/sync`; `timelines branch/undo/mass-undo/erase/recover` | Export parity, migration, cloud sync, and rich legacy history commands are out. |
| **FOLD** | `start`; `abort`; `claim` / `unclaim`; `run`, `runs`, `step`, `next`, `ack`, `skip`, `hook`, `plan`, `events` | Direct runs/tasks keep start/cancel/internal claims/events; every step/plan control is deleted. |
| **SIMPLIFY** | `executors`; `renderers`; `orchestrators`; SDK `discover`/`get_capability`; SDK `invoke`/`generate`; SDK `render`/`support`/`RenderContext` | Keep manifest discovery and typed SDK invocation, without top-level product families or parity. |
| **CUT** | `scratch`; `audit --run`; SDK raw `run_executor`/`run_orchestrator`, `_registries` injection, private builders | No current product need justifies these public seams. |
| **FOLD** | `setup`; `serve`; `doctor` | `serve` owns lazy setup; `doctor` is reduced to quick/FK checks. |
| **KEEP FILE-SIDE / DEV** | `packs` list/search/inspect/install/update/uninstall/rollback; `orchestrate`; `author` / `test`; `elements` list/search/inspect/validate/override; `themes`; `modalities`; Model catalog and generation discovery; `replay`; `skills`; `update`, scaffold and authoring utilities | Executable distribution and authoring inputs stay outside the product database and compatibility surface. |
| **DEFER** | Experiment CLIs and human review; `runpod`; `worker` / `reigh-data`; `publish`, `publish-youtube`, `upload-youtube` | Experiments, remote execution/data, and publication are separate future milestones. |
| **SIMPLIFY** | SDK `read_events`/`subscribe_events`; Existing SDK contract | Query new repository events and preserve useful typed/lazy behavior, not old exports or JSONL adapters. |
| **CUT** | `project.json`; `sources.json`; `sources/<id>/source.json` and source media; Timeline `assembly.jsonl`; `assembly.head.json`; `assembly.checkpoint.json`; `assembly.json`; `assembly.identity.json`; `display.json`; Timeline `manifest.json` + lock; `registry.json`; Legacy `assets.json`; `.import_idem_<sha>.json` | Old project/timeline authorities are neither read nor migrated; useful bytes enter through media import. |
| **CUT** | Thread-era root `runs/<id>/run.json` v1; Project `runs/<id>/run.json` v2; Run `events.jsonl`; Run `audit/ledger.jsonl` | No run dialect, event-chain, or audit-ledger import survives. |
| **KEEP FILE-SIDE** | `plan.md`, README, user notes; Run logs, command/prompt, request/result, debug, `.capture`, manifests; `.provenance.json`, `brief.copy.txt`, generation/render manifests | Human prose and optional immutable diagnostics remain non-authoritative files. |
| **CUT** | `.astrid.variants.json`, `groups.json`, `selections.jsonl`; `.astrid/threads.json`, backup/locks/tags/cache; `identity.json`, session JSON, `.astrid-session`; `current_run.json`; `lease.json`; `plan.json` mutable plan authority; `AGENT.md`, step dirs, returncode and remote-state artifacts; `inbox/*.json` and consumed/rejected dirs | Variant/thread/session/plan/step/manual-control file state is deleted, not translated. |
| **SIMPLIFY** | User/workspace `config.json` | Keep only non-authoritative default project/UI preferences. |
| **KEEP / REBUILD INDEX** | `.cas/<sha256>` and `produces/` symlinks | Reuse verified byte primitives; database rows replace semantic indexes and output symlink authority. |
| **DEFER** | Experiment definitions/review/state/final/conclusions; RunPod `pod_handle.json` and `runpod_sweeper_audit.jsonl`; Arnold `arnold_run.json`, `state.json`, `session-manifest.json`, `lease.json`, `events.jsonl` | They remain outside local GA and are never imported. |
| **KEEP FILE-SIDE** | Capability pack/component manifests; Capability pack install store/records/symlinks; Element manifests/components and override store; `models.yaml` and generation taxonomy | Confirmed executable/package inputs; selected IDs/digests are snapshotted into tasks/runs. Schema-pack manifests are separately defined in §2 and remain file-described while their migrations create domain tables. |
| **CUT** | Dead `.astrid/elements/managed/**`; `~/.astrid/cli-usage.jsonl` | Dead corpus and unowned telemetry have no product role. |
| **KEEP FILE-SIDE** | Export `.tar.gz`, `MANIFEST.txt`, preview JSON/HTML; Tool manifests (`manifest.json`, `result.json`, storyboard/Discord outputs); Hivemind distillation/action batches; `.gitignore`, lock files, fork/update reports | Explicit exports and external/operational tool state remain outside domain authority. |
| **SIMPLIFY** | `.env*`, `this.env`, key/token fallback files | Delete scavenging; use option, process environment, then supported OS keychain. |
| **REBUILD** | Project/source subsystem; Timeline event/projection subsystem; Existing local bridge/server | Build repository-backed projects/timelines/media while retaining only the consumed bridge contract. |
| **CUT / DEFER** | Reigh append service/timeline I/O/data provider; Banodoco worker/task client; RunPod integrations; Arnold authoring/step/session integration | Hosted, remote, and plan/session integrations are absent from local GA. |
| **SIMPLIFY** | Pack runtime; Capability/artifact contracts | Capabilities receive immutable task/run context and return manifests; no direct semantic file writes. |
| **CUT** | Task-plan/run lifecycle; Thread/variant subsystem; Session/lease subsystem | Direct runs/tasks replace the useful outcomes; old lifecycle ontologies disappear. |
| **REBUILD** | Runs/provenance subsystem; Events subsystem; Media/probe/CAS subsystem | One run/event dialect and one media repository replace disconnected authorities without importing them. |
| **SIMPLIFY** | Audit/verify/doctor subsystem | Keep repository tests plus user-facing SQLite quick/FK checks; no audit import or repair catalog. |
| **CUT** | Editor local FSA mode | The repository bridge is the unconditional editor authority. |
| **KEEP CLIENT-SIDE** | Editor IndexedDB recovery drafts | Current unsaved-work protection remains browser-local and is tested normally. |
| **KEEP SELECTIVELY** | Timeline/bridge/concurrency tests; Pack/capability/SDK/render tests | Port current semantic/provider/race contracts only; do not preserve storage layout. |
| **CUT** | Task/session/thread storage tests; Retired fixtures/migrations | Delete with the old storage and legacy migration code. |

## 2. Normative 20-table schema

### Layered architecture: agent-agnostic kernel plus Astrid packs

The 20-table count does not change; the ownership boundary becomes explicit:

| Layer | Tables | Role |
|---|---|---|
| **Kernel (14)** | `schema_migrations`, `projects`, `event_streams`, `events`, `command_receipts`, `runs`, `evidence_items`, `tasks`, `task_dependencies`, `execution_attempts`, `task_outputs`, `media`, `media_locations`, `media_relations` | Reusable task/event/run/media substrate. Media includes source files, diffs, logs, reports, and generated assets; it is not a pack. |
| **Timeline pack (1)** | `timelines` | Timeline document, registry, per-aggregate stream, and whole-document CAS semantics. |
| **Shots pack (2)** | `shots`, `shot_items` | Project-scoped shot containers and ordered exact-media placements. |
| **References pack (3)** | `project_references`, `media_references`, `reference_links` | Named project semantics, canonical media, contextual roles, and typed links. |

Each pack is a manifest plus code, with this contract: `id`, `version`, `depends_on`, `migrations[]`, `stream_types[]`, `event_kinds[]`, `command_kinds[]`, `repositories[]`, `conformance[]`, `cli_mounts{}`, and `bridge_mounts[]`. V10 lays out the implementation as `core/` plus in-tree `packs/timeline`, `packs/shots`, and `packs/references`. Startup makes one explicit `register_pack()` call for the shipped pack set; registration installs each declared migration set in dependency order, validates namespaced vocabularies, and mounts repositories and surfaces.

This is a compile-time product composition, not a public or dynamic loader. There is no discovery, download, enable/disable, uninstall, third-party ABI, or runtime dependency solver at GA. When a second agent is real, `core/` can be extracted as a shared library and that agent can compose it with different in-tree packs; the stable manifest and registration boundary makes a loader a later implementation choice rather than v10 platform work.

The plugin laws are normative:

1. **Foreign keys point inward only.** A pack may FK to kernel tables. No kernel table may FK to a pack table. Kernel events may identify pack rows only through polymorphic `events.subject_type` and `events.subject_id`.
2. **Kernel currencies are the only cross-pack references.** Packs exchange `media_id`, `task_id`, or other explicitly kernel-owned IDs; they do not FK directly into another pack's tables. Manifest dependencies govern registration and migration order, not permission to bypass this rule.
3. **Packs never own a writer.** A pack repository registers with the single kernel write queue and receives a unit-of-work handle inside the kernel-owned `BEGIN IMMEDIATE`. The kernel provides idempotency lookup, `project_seq` allocation, stream-head CAS, event append, projection coordination, and receipt writing.
4. **Every pack command passes the kernel conformance kit.** At minimum it proves identical replay, mismatched-key rejection before mutation, statement-boundary old-or-complete behavior, and same-project assertions, plus its declared domain checks.
5. **Vocabularies are namespaced and registered.** Stream types, event kinds, and command kinds are validated against the composed registry rather than hardcoded into kernel DDL. Event examples include `timeline.saved`, `shot.item_added`, and `reference.primary_changed`; command examples include `timeline.save`, `shot.add_item`, and `reference.set_primary`.

The factoring test is two-sided: removing any Astrid pack and its registration must leave the entire kernel test suite green, and a second-agent schema sketch must require no change to a kernel table. This test concerns source composition, not destructive uninstall of tables from an existing database.

### 2.1 Inventory and run grouping

The standard Astrid composition contains the following 20 tables:

1. Kernel foundation/history: `schema_migrations`, `projects`, `event_streams`, `events`, `command_receipts`.
2. Kernel coordination/execution: `runs`, `evidence_items`, `tasks`, `task_dependencies`, `execution_attempts`, `task_outputs`.
3. Kernel universal media: `media`, `media_locations`, `media_relations`.
4. Timeline and shots packs: `timelines`, `shots`, `shot_items`.
5. References pack: `project_references`, `media_references`, `reference_links`.

The arithmetic from v7/v9 is exact:

```text
v7/v9 model                 22
delete run_steps            -1
delete run_step_tasks       -1
v10 model                   20
```

No replacement `plans`, `steps`, or generic join table is added. Instead:

- `tasks.run_id` makes a task a direct child of one run.
- `tasks.run_ordinal` provides deterministic display and fan-out order; it is unique within the run.
- `task_dependencies` expresses hard or soft execution edges between real tasks.
- `evidence_items.run_id` attaches observations to the group; optional `task_id` identifies the child that produced the evidence.
- the creating `command_receipts.result_json` returns the `run_id`, ordered task IDs, and evidence IDs. That receipt is the retry-safe command result; the run is the durable query/group handle.
- run progress is a read model over child task counts. A run with no tasks is valid for synchronous understanding or manual observation. A run with tasks never becomes an executable parent.

For bounded fan-out, one transaction creates the run, child task streams and tasks, dependency edges, creation events, and one receipt. A configured maximum prevents unbounded transactions. Larger fan-out is submitted in receipt-linked chunks to the same run. Every continuation supplies the expected run-stream head, allocates new ordinals atomically under that CAS, and fails if the run is terminal; concurrent or replayed chunks can neither collide nor extend a finished run. This is coordination, not a reintroduced plan: there is no mutable step cursor, group/repeat instruction, or step lifecycle.

### 2.2 Full creation DDL

This is the composed fresh creation DDL for standard Astrid. `schema_migrations` supports independent, forward-only core and pack upgrades applied in declared dependency order; it is not legacy-data migration or cutover tooling. Catalog conformance compares the kernel catalog plus the manifests of the installed packs, while the standard Astrid composition still resolves to exactly these 20 tables.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_migrations (
  pack          TEXT NOT NULL DEFAULT 'core' CHECK (length(trim(pack)) > 0),
  version       INTEGER NOT NULL CHECK (version > 0),
  name          TEXT NOT NULL,
  checksum      TEXT NOT NULL,
  applied_at    TEXT NOT NULL,
  PRIMARY KEY (pack, version),
  UNIQUE (pack, name)
);

CREATE TABLE projects (
  id             TEXT PRIMARY KEY,
  slug           TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  settings_json  TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(settings_json)),
  event_head_seq INTEGER NOT NULL DEFAULT 0 CHECK (event_head_seq >= 0),
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE TABLE event_streams (
  id           TEXT PRIMARY KEY,
  project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  stream_type  TEXT NOT NULL,
  aggregate_id TEXT NOT NULL,
  head_seq     INTEGER NOT NULL DEFAULT 0 CHECK (head_seq >= 0),
  created_at   TEXT NOT NULL,
  UNIQUE (project_id, stream_type, aggregate_id)
);

CREATE TABLE events (
  event_id        TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  project_seq     INTEGER NOT NULL CHECK (project_seq > 0),
  stream_id       TEXT NOT NULL REFERENCES event_streams(id) ON DELETE RESTRICT,
  seq             INTEGER NOT NULL CHECK (seq > 0),
  subject_type    TEXT NOT NULL,
  subject_id      TEXT NOT NULL,
  changes_json    TEXT NOT NULL CHECK
                  (json_valid(changes_json) AND json_type(changes_json) = 'array'),
  kind            TEXT NOT NULL,
  schema_version  INTEGER NOT NULL CHECK (schema_version > 0),
  idempotency_key TEXT NOT NULL,
  txn_id          TEXT NOT NULL,
  actor_kind      TEXT NOT NULL CHECK (actor_kind IN
                  ('local','system','executor')),
  payload_json    TEXT NOT NULL CHECK (json_valid(payload_json)),
  created_at      TEXT NOT NULL,
  UNIQUE (project_id, project_seq),
  UNIQUE (stream_id, seq),
  UNIQUE (stream_id, idempotency_key)
);

CREATE TABLE command_receipts (
  project_id           TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  idempotency_key      TEXT NOT NULL,
  request_hash         TEXT NOT NULL,
  command_kind         TEXT NOT NULL,
  txn_id               TEXT NOT NULL UNIQUE,
  primary_stream_id    TEXT REFERENCES event_streams(id) ON DELETE RESTRICT,
  resulting_stream_seq INTEGER,
  first_project_seq    INTEGER NOT NULL CHECK (first_project_seq > 0),
  last_project_seq     INTEGER NOT NULL CHECK (last_project_seq >= first_project_seq),
  event_ids_json       TEXT NOT NULL CHECK
                       (json_valid(event_ids_json) AND json_type(event_ids_json) = 'array'),
  result_json          TEXT NOT NULL CHECK (json_valid(result_json)),
  created_at           TEXT NOT NULL,
  PRIMARY KEY (project_id, idempotency_key)
);

CREATE TABLE runs (
  id              TEXT PRIMARY KEY,
  project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
  kind            TEXT NOT NULL,
  status          TEXT NOT NULL CHECK
                  (status IN ('running','succeeded','failed','cancelled')),
  title           TEXT,
  input_json      TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(input_json)),
  result_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(result_json)),
  started_at      TEXT NOT NULL,
  finished_at     TEXT,
  UNIQUE (id, project_id)
);

CREATE TABLE tasks (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id     TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
  run_id              TEXT,
  run_ordinal         INTEGER CHECK (run_ordinal >= 0),
  capability          TEXT NOT NULL,
  spec_json           TEXT NOT NULL CHECK (json_valid(spec_json)),
  spec_hash           TEXT NOT NULL,
  input_manifest_json TEXT NOT NULL DEFAULT '[]' CHECK
                      (json_valid(input_manifest_json) AND
                       json_type(input_manifest_json) = 'array'),
  status              TEXT NOT NULL CHECK
                      (status IN ('queued','blocked','running','succeeded','failed','cancelled')),
  priority            INTEGER NOT NULL DEFAULT 0,
  available_at        TEXT NOT NULL,
  max_attempts        INTEGER NOT NULL DEFAULT 1 CHECK (max_attempts > 0),
  winning_attempt_id  TEXT,
  cancel_request_id   TEXT,
  cancel_requested_at TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL,
  finished_at         TEXT,
  CHECK ((run_id IS NULL AND run_ordinal IS NULL) OR
         (run_id IS NOT NULL AND run_ordinal IS NOT NULL)),
  FOREIGN KEY (run_id, project_id)
    REFERENCES runs(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE task_dependencies (
  task_id            TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  depends_on_task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  kind               TEXT NOT NULL DEFAULT 'hard' CHECK (kind IN ('hard','soft')),
  ordinal            INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  PRIMARY KEY (task_id, depends_on_task_id),
  CHECK (task_id <> depends_on_task_id)
);

CREATE TABLE execution_attempts (
  id                TEXT PRIMARY KEY,
  task_id           TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  attempt_no        INTEGER NOT NULL CHECK (attempt_no > 0),
  executor_id       TEXT,
  status            TEXT NOT NULL CHECK
                    (status IN ('claimed','running','succeeded','failed','cancelled','expired')),
  status_version    INTEGER NOT NULL DEFAULT 1 CHECK (status_version > 0),
  lease_id          TEXT,
  lease_expires_at  TEXT,
  heartbeat_counter INTEGER NOT NULL DEFAULT 0 CHECK (heartbeat_counter >= 0),
  last_heartbeat_at TEXT,
  progress_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(progress_json)),
  error_json        TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(error_json)),
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  finished_at       TEXT,
  UNIQUE (task_id, attempt_no)
);

CREATE TABLE media (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  media_kind    TEXT NOT NULL CHECK
                (media_kind IN ('image','video','audio','text','document','data','other')),
  mime_type     TEXT NOT NULL,
  byte_size     INTEGER NOT NULL CHECK (byte_size >= 0),
  content_hash  TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  UNIQUE (project_id, content_hash)
);

CREATE TABLE media_locations (
  id          TEXT PRIMARY KEY,
  media_id    TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  realm       TEXT NOT NULL DEFAULT 'managed_local' CHECK
              (realm IN ('managed_local','external_local','remote')),
  locator     TEXT NOT NULL,
  verified_at TEXT,
  created_at  TEXT NOT NULL,
  UNIQUE (media_id, realm, locator)
);

CREATE TABLE media_relations (
  from_media_id TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  to_media_id   TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN
                ('derived_from','variant_of','uses_as_input','mask_for','audio_for')),
  ordinal       INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  PRIMARY KEY (from_media_id, to_media_id, kind, ordinal),
  CHECK (from_media_id <> to_media_id)
);

CREATE TABLE task_outputs (
  task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal     INTEGER NOT NULL CHECK (ordinal >= 0),
  role        TEXT NOT NULL,
  media_id    TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  is_primary  INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  params_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_json)),
  created_at  TEXT NOT NULL,
  PRIMARY KEY (task_id, ordinal),
  CHECK (role = 'result' OR is_primary = 0)
);

CREATE TABLE evidence_items (
  id        TEXT PRIMARY KEY,
  run_id    TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  task_id   TEXT REFERENCES tasks(id) ON DELETE SET NULL,
  kind      TEXT NOT NULL,
  summary   TEXT NOT NULL,
  data_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(data_json)),
  media_id  TEXT REFERENCES media(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE timelines (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id     TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
  name                TEXT NOT NULL,
  document_json       TEXT NOT NULL CHECK (json_valid(document_json)),
  asset_registry_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(asset_registry_json)),
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);

CREATE TABLE shots (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name          TEXT NOT NULL,
  sort_key      TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  UNIQUE (project_id, sort_key)
);

CREATE TABLE shot_items (
  id           TEXT PRIMARY KEY,
  shot_id      TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  media_id     TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  sort_key     TEXT NOT NULL,
  source_frame INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at   TEXT NOT NULL,
  UNIQUE (shot_id, sort_key)
);

CREATE TABLE project_references (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind          TEXT NOT NULL CHECK (kind IN
                ('character','place','object','clothing','other')),
  name          TEXT NOT NULL CHECK (length(trim(name)) > 0),
  description   TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  archived_at   TEXT
);

CREATE TABLE media_references (
  id              TEXT PRIMARY KEY,
  reference_id    TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  media_id        TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN
                  ('canonical','used_as_input','depicts','inspired_by')),
  context_task_id TEXT REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal         INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  is_primary      INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  metadata_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at      TEXT NOT NULL,
  CHECK (role = 'canonical' OR is_primary = 0),
  CHECK (role <> 'used_as_input' OR context_task_id IS NOT NULL),
  CHECK (context_task_id IS NULL OR role IN ('used_as_input','inspired_by'))
);

CREATE TABLE reference_links (
  from_reference_id TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  to_reference_id   TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  kind              TEXT NOT NULL CHECK (kind IN
                    ('belongs_to','wears','located_in','associated_with','related_to')),
  metadata_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at        TEXT NOT NULL,
  PRIMARY KEY (from_reference_id, to_reference_id, kind),
  CHECK (from_reference_id <> to_reference_id)
);

CREATE UNIQUE INDEX tasks_run_ordinal
  ON tasks(run_id, run_ordinal) WHERE run_id IS NOT NULL;
CREATE UNIQUE INDEX task_one_primary_result
  ON task_outputs(task_id) WHERE role = 'result' AND is_primary = 1;
CREATE UNIQUE INDEX reference_one_primary_canonical
  ON media_references(reference_id) WHERE role = 'canonical' AND is_primary = 1;
CREATE UNIQUE INDEX reference_canonical_ordinal
  ON media_references(reference_id, ordinal) WHERE role = 'canonical';
CREATE UNIQUE INDEX media_reference_global_unique
  ON media_references(reference_id, media_id, role)
  WHERE context_task_id IS NULL;
CREATE UNIQUE INDEX media_reference_context_unique
  ON media_references(reference_id, media_id, role, context_task_id)
  WHERE context_task_id IS NOT NULL;
CREATE INDEX events_project_changes ON events(project_id, project_seq);
CREATE INDEX events_stream_kind_seq ON events(stream_id, kind, seq);
CREATE INDEX events_subject
  ON events(project_id, subject_type, subject_id, project_seq);
CREATE INDEX tasks_claim_order
  ON tasks(status, available_at, priority DESC, id);
CREATE INDEX tasks_project_status
  ON tasks(project_id, status, created_at, id);
CREATE INDEX tasks_run_status
  ON tasks(run_id, status, run_ordinal) WHERE run_id IS NOT NULL;
CREATE INDEX task_dependencies_reverse
  ON task_dependencies(depends_on_task_id, task_id);
CREATE INDEX attempts_lease_expiry
  ON execution_attempts(status, lease_expires_at);
CREATE INDEX task_outputs_media ON task_outputs(media_id, task_id);
CREATE INDEX media_project_page ON media(project_id, created_at, id);
CREATE INDEX media_relations_to
  ON media_relations(to_media_id, kind, from_media_id);
CREATE UNIQUE INDEX media_one_variant_parent
  ON media_relations(from_media_id) WHERE kind = 'variant_of';
CREATE INDEX evidence_run_time ON evidence_items(run_id, created_at, id);
CREATE INDEX evidence_task ON evidence_items(task_id, id) WHERE task_id IS NOT NULL;
CREATE INDEX shot_items_media ON shot_items(media_id, shot_id);
CREATE INDEX references_project_kind
  ON project_references(project_id, kind, name, id);
CREATE INDEX media_references_media
  ON media_references(media_id, role, reference_id);
CREATE INDEX media_references_task
  ON media_references(context_task_id, role, reference_id)
  WHERE context_task_id IS NOT NULL;
CREATE INDEX reference_links_to
  ON reference_links(to_reference_id, kind, from_reference_id);
```

### 2.3 Repository-enforced constraints and atomicity

SQLite cannot conveniently express every cross-row invariant, and kernel DDL must not hardcode pack-owned vocabulary. The repository layer validates `event_streams.stream_type` against the startup registry: core registers `core.project`, `core.task`, and `core.run`; the timeline pack registers `timeline.timeline`; later packs may declare additional namespaced stream types. The same composed registry validates namespaced event and command kinds before mutation.

Repository conformance must enforce that stream aggregate IDs, registered types, and projects match their `projects`, `runs`, `tasks`, and `timelines`; a task and its run share a project; dependencies are same-project and acyclic; task outputs and attempts belong to their task's project; an evidence `task_id`, when present, names a direct child of that evidence row's `run_id`, and its media shares the run project; media relations, shot items, and reference associations never cross projects; `winning_attempt_id` belongs to the task; variant edges are acyclic; and symmetric reference links use canonical ordering. Pack repositories use the reusable kernel conformance kit and add their manifest-declared domain assertions.

Every eventful command, including a pack command, executes in one short kernel-owned `BEGIN IMMEDIATE` transaction. A pack receives only the unit-of-work handle for that transaction; it cannot open a semantic writer of its own:

```text
check idempotency key, canonical request hash, and expected stream/attempt versions
allocate consecutive project_seq values
append registered event(s) and advance affected stream heads
update current projections
for fan-out: insert the run, task streams, tasks, and dependencies
for completion: insert/reuse verified media, locations, ordered outputs, and relations
write one command receipt with ordered event IDs and complete result IDs
commit
```

An identical retry returns the stored receipt; reuse of an idempotency key with different canonical request bytes fails. Crash injection at each statement boundary must show either no visible effect or the complete unit. Heartbeats remain narrow non-event attempt updates fenced by `status_version`; expiry, retry, cancellation, failure, and completion are semantic events. Terminal tasks cannot resurrect, and stale attempts cannot materialize output.

Timeline saves atomically update `document_json` and `asset_registry_json`, append the registered event, advance the timeline stream head, and write the receipt. The expected stream head is the numeric `config_version`; a stale value returns 409 with no mutation. Media identity is project-scoped SHA-256 of verified bytes. Paths, URLs, source names, and registry keys are locators or aliases only.

## 3. Three-phase delivery path

### Phase 1 — build the core

Build the composed 20-table creation migration, dependency-ordered core/pack migration runner, repository-owned write queue, namespaced event/command/stream registries, project and timeline repositories, task lifecycle and local executor, run grouping, evidence, media storage, references, and shots. Structure the code as `core/` plus the three in-tree Astrid packs, each with its manifest, registered together by the single startup `register_pack()` call. Reuse proven SHA-256, probing, streaming, and atomic-placement code behind the kernel media repository. Adapt one real generation capability and one renderer through immutable task specs and output manifests. Delete `Step`/`TaskPlan`, session, thread, lease-file, current-run, inbox, JSONL authority, and Supabase project-state modules as their new path lands.

Tests are written for the new model. Selective carryovers are limited to:

- the five relevant task cancellation/expiry/completion races;
- SHA-256, MIME/ffprobe, staged placement, and multi-output vectors;
- capability invocation, rendering result, typed error, and manifest digest contracts that still describe the new product;
- repository contention, single-writer, pack conformance, and crash-injection cases.

**Phase 1 gate:** a fresh standard Astrid database has exactly 20 tables, and its catalog equals the 14 kernel tables plus all tables declared by the three installed pack manifests, with all indexes/constraints; independent migration versions and dependency order pass; project/run/task/timeline stream association and registry tests pass; every pack command passes the kernel conformance kit; one generation and one render complete through task → attempt → media → ordered outputs; synchronous understanding creates run evidence without a task; fan-out creates directly grouped tasks and dependencies with no step records; the race matrix, contention test, statement-boundary crash injection, and pack-deletion factoring test pass.

### Phase 2 — wire the editor and essential CLI

Replace the bridge's file/JSONL reads and writes with repository calls while keeping the existing wire contract. Delete editor FSA mode instead of detecting old and new projects. Implement the eight CLI families and the reduced SDK in §4. `serve` lazily initializes the application database and local data directories, starts the repository bridge, and opens the packaged/current editor path already chosen by the product. Local create/edit/import flows require no account, provider key, Supabase, Docker, or Node.

“Editor wiring” no longer means a continuity migration program. Its gate is:

1. Astrid bridge unit/contract tests cover the frozen routes and envelopes.
2. The editor's existing `AstridBridgeDataProvider`, provider compatibility, IndexedDB draft, poll-sync, timeline persistence, and save utility tests pass against the new bridge implementation.
3. A small end-to-end smoke test proves list → load → edit → save → reload, stale-version 409 behavior, restart durability, and asset byte-range playback.

There are no before-import, disposable-copy, post-flip, backup-restored parity runs; no old file adapter is retained to parameterize against; and ETag/Last-Modified or exact retry/debounce timings are tested only if the current editor actually consumes them.

**Phase 2 gate:** all supported editor mutations commit an internal durable receipt while returning the unchanged editor response envelope; bridge payload and error contracts pass; FSA and Supabase semantic writers are absent from the shipped path; the essential CLI and SDK exercise repository services rather than SQL/files; a clean install reaches an editable project without secrets.

### Phase 3 — dogfood and ship

Dogfood fresh projects only. Import useful existing bytes with `media import`, not old projects. Exercise generation, rendering, multi-output selection, run fan-out, references, shots, timeline saves/conflicts, process kill/restart, missing media, and backup/restore. Fix pre-release schema mistakes with forward migrations; do not add compatibility abstractions for unshipped layouts.

Remove old modules, fixtures, CLI aliases, help entries, and optional dependencies in the same commits as their replacements. One build/import-lint rule rejects shipped imports of removed Supabase and FSA domain-authority modules and rejects kernel-to-pack dependencies, pack-to-pack table dependencies, or pack-owned writer/transaction construction. No runtime tracing or exhaustive writer census is required. Package the actual release artifact and run its tests from a clean account.

**Phase 3 gate:** the release artifact passes the focused kernel, pack, and editor suites; deliberate crashes expose only old-or-complete transactions; a concurrent writer test shows bounded SQLite busy handling; database plus media backup restores to an editable, hash-consistent project; `doctor` passes; the pack-boundary import lint and deletion factoring test pass; no removed family appears in product help; and the team has completed a representative project using only the shipped surface.

## 4. Essential CLI and SDK surface

### 4.1 CLI

V10 has exactly eight top-level product families. The kernel owns `projects`, `media`, `tasks`, `runs`, `serve`, `doctor`, and `backup`; the timeline pack contributes `timelines`; the shots pack mounts under `timelines shots`; and the references pack mounts under `media references`. These are explicit in-tree `cli_mounts`, not dynamically discovered plugins, and they preserve the eight-family rule. Plural nouns own durable collections; `serve`, `doctor`, and `backup` are operational verbs/nouns already familiar to users. Every CLI/SDK mutation accepts an idempotency key or generates and returns one; machine-readable output uses one stable envelope for the new API only.

| Family | GA commands | Scope decision |
|---|---|---|
| `projects` | `create`, `list`, `show`, `update`, `select` | Kernel-owned project CRUD and preferences. First-run setup is automatic; no separate `setup` or `status` family. |
| `timelines` | `create`, `list`, `show`, `save`, `copy`, `archive`, `history`, `diff`; nested `shots list/create/add/remove/reorder` when the editor journey needs CLI access | Timeline-pack mount; the shots pack mounts beneath it. Timeline CAS/history stays. No legacy event migration, push/pull/sync, audit, erase, or repair catalog. |
| `media` | `import`, `list`, `show`, `verify`, `relocate`, `relate` | Kernel-owned. `import` accepts files/folders only and creates no old project/run semantics. The references pack mounts nested `references create/update/archive/associate/link/list/show` without a ninth top-level family. |
| `tasks` | `create` (advanced), `list`, `show`, `cancel`, `retry`, `events` | Kernel-owned. Executor claim/start/heartbeat remain internal. Generation/render invocation is SDK/capability driven and returns task IDs. |
| `runs` | `list`, `show [--evidence]`, `cancel`, `retry-failed`, `events` | Kernel-owned. `show` includes evidence and child task progress. No step/plan/next/ack/skip/hook commands. |
| `serve` | no mandatory subcommand; optional `--project` and bind flags | Kernel-owned. Lazily creates/migrates the database, registers the shipped packs, starts the bridge, and opens the editor. |
| `doctor` | default, `--json` | Kernel-owned, pack-aware catalog reporting plus read-only `PRAGMA quick_check`, `PRAGMA foreign_key_check`, migration versions, and resolved data/media paths. No generic mutation. |
| `backup` | `create`, `restore` | Kernel-owned. Online SQLite backup plus managed-media directory copy covers all installed packs because their state shares the same database. Restore verifies SQLite and FKs before activation. |

References and shots are not deferred as data concepts; only separate top-level families and exhaustive CLI polish are cut. They live primarily in the editor/SDK and, where useful, as nested `media references` and `timelines shots` commands. Evidence is returned from `runs show --evidence`. Events are inspected under their owning task, run, or timeline. Capability, renderer, executor, pack, element, model, theme, skill, authoring, replay, and test tools may remain behind a developer entry point, but they are not product CLI families and receive no legacy parity promise.

### 4.2 SDK and bridge

The SDK keeps lazy capability-manifest discovery, `get_capability`, typed `invoke`/`generate`/`render`, repository-backed services for the eight product families, command receipts, typed not-found/conflict/integrity errors, and result types that expose run/task/media IDs. Schema-pack registration remains an explicit startup composition and is not exposed as lazy discovery. The SDK drops ordered `__all__` compatibility, raw `run_executor`/`run_orchestrator` promises, caller-supplied registry injection, thread/session/plan types, and old storage adapters. CLI handlers and bridge handlers call this service layer; neither reimplements SQL, lifecycle arbitration, hashing, or output materialization.

The frozen bridge surface remains:

- `GET /health`;
- `GET /projects`;
- `GET /projects/:slug/timelines`;
- `GET /projects/:slug/timelines/:ref`;
- `POST /projects/:slug/timelines/:ref/save`;
- `GET` and `HEAD /projects/:slug/timelines/:ref/assets/:key`, with single-range 206 and invalid-range 416 behavior;
- existing OPTIONS/CORS behavior only where the chosen editor delivery mode needs it.

Load/save retains `timeline_id`, `timeline_ulid`, `slug`, `name`, `is_default`, loose `config`, `registry.assets`, and numeric opaque `config_version`. Save takes object `config`, object `registry`, and integer `expected_version`; success returns the committed payload, stale CAS returns 409 `timeline_version_conflict`, invalid schema returns 422 `schema_incompatible`, and missing resources return the existing 404 envelopes. The bridge derives an internal idempotency key from timeline identity, expected version, and the canonical save payload, commits the normal receipt, and returns no new receipt field; explicit keys and receipts remain CLI/SDK behavior. UUID remains canonical identity and ULID remains a supported route address. The server round-trips what the current editor sends; no broader third-party extension-compatibility promise is created.

Editor draft safety remains product correctness: failed saves never manufacture acknowledgement; dirty/recovery data remains after conflict/unavailable/crash; a covering successful save may clear its IndexedDB draft; poll adoption must not overwrite pending local work; and a failed load disables persistence rather than presenting an active-looking no-op editor. These rules are maintained by current editor tests, not a bespoke migration harness.

### 4.3 Backup, doctor, and secrets

Backup pauses semantic writes briefly under the service writer lock, creates a SQLite online backup, copies the managed-media directory into the backup destination, then resumes writes. This covers kernel and installed-pack tables without pack-specific backup code because they share one database. It does not enumerate source formats, classify attachments, generate a preservation manifest, include caches/staging/logs/pack code/secrets, or promise external-local media capture. Restore stages both components, runs SQLite quick/FK checks, verifies managed media referenced by the restored rows during the normal open path, and swaps them into place only after validation.

`doctor` is deliberately not a universal invariant framework. It reports `quick_check`, foreign-key violations, core and installed-pack migration-version compatibility, the composed catalog, and data/media paths. Repository, pack-conformance, and crash tests protect stream/task/media/domain invariants during development. If a real post-GA corruption mode appears, add one named, backup-first repair for that code; do not prebuild a generic repair language.

Local projects, timelines, media, references, backup, doctor, and editor use require zero provider secrets. Provider-backed invocation resolves credentials in this order: explicit command/API option, process environment, OS keychain where supported. Delete cross-agent and unrelated-workspace `.env` scanning; env files do not override process environment. Secrets never enter events, receipts, task specs, logs, backups, or child processes except for an explicitly allowlisted capability environment.

## 5. Invariants and release acceptance

### 5.1 Kept invariants

- **Task admission:** a task exists only for a bounded immutable executable spec with exclusive claim or independently fenced attempts and one selectable terminal winner.
- **Event universality:** every meaningful non-task mutation appends a registered, namespaced, ordered event; heartbeats and narrow attempt liveness are the deliberate exception.
- **Task stream:** every task has exactly one same-project task stream beginning with `task.created`; task lifecycle projection and stream head change atomically.
- **Atomic receipts:** events, heads, projections, runs/group membership, dependencies, attempts, media, outputs, associations, and the command receipt commit or roll back as one command unit.
- **Idempotency:** an identical request/key returns its receipt; the same key with different canonical bytes fails.
- **Terminal immutability and fencing:** terminal tasks never resurrect; stale attempts never complete, cancel, fail, or materialize over a newer attempt.
- **Honest grouping:** a run may contain zero or many direct child tasks. It is never an executable parent. Dependencies connect only real executable work.
- **No plan semantics:** no step, cursor, group/repeat/`for_each`, supersede plan, acknowledgement, or hook state exists in the database or public API.
- **Timeline CAS:** document and registry advance together against the timeline stream head; stale saves do not mutate state.
- **Media identity:** SHA-256 of verified bytes is identity within a project; locators and aliases are replaceable.
- **Exact associations:** task outputs, shot placements, media relations, and reference associations point to exact media IDs and do not inherit invisibly across variants.
- **One-way pack dependency:** pack tables may FK to kernel tables; kernel tables never FK to pack tables, and kernel events refer to pack subjects only through `subject_type`/`subject_id`.
- **Kernel-only cross-pack currency:** packs exchange kernel-owned IDs such as `media_id` and `task_id`; no pack table FKs to another pack table.
- **Single writer:** repositories are the only semantic writers. Bridge, CLI, SDK, executor, media import, and every pack repository use the kernel queue and unit of work; FSA, Supabase, and pack-owned connections do not.
- **Pack conformance:** every pack command passes reusable replay, mismatched-key, statement-boundary crash, and same-project checks before its domain-specific assertions.
- **Registered vocabulary:** stream types and namespaced event/command kinds come from the composed core/pack registry, never kernel DDL enums or handler-local allowlists.
- **Independent migrations:** core and each pack version forward-only migrations under `(pack, version)` and apply in declared dependency order.
- **File boundary:** schema-pack and capability/component/element/model manifests plus immutable non-critical diagnostics may remain files, but cannot become a second domain authority.
- **Boundary now, loader later:** GA ships only explicit in-tree pack registration; no dynamic discovery, installation, unloading, or third-party plugin ABI is built.
- **No dormant platform:** no accounts, billing, sharing, sync, remote-worker, experiment, legacy-alias, importer, plan schema, or speculative plugin platform ships.

### 5.2 Dropped invariants and gates

V10 intentionally makes no promise of old project readability, old timeline identity, event/hash continuity, old run history, audit graph retention, session/thread/plan semantics, CLI/SDK name compatibility, importer idempotency, old/new projection parity, rollback to file authority, or restoration of external-local/scratch files. The v9 invariants “import real plans without losing group/repeat/`for_each`,” “recognize both run dialects,” “preserve original chain evidence,” and “pass continuity before/after import/flip/restore” are deleted rather than weakened.

### 5.3 GA acceptance

1. Fresh standard Astrid creation produces exactly 20 tables and declared indexes, while the catalog assertion is computed as 14 kernel tables plus the tables of the three installed packs; core and pack migration versions are independent and a too-new schema opens read-only/fails clearly.
2. A real generation and render traverse task, attempt, event, media/location, ordered outputs, and receipt atomically.
3. Synchronous understanding produces a run and evidence with no convenience task.
4. Fan-out produces one run and direct child tasks with stable ordinals; dependencies gate execution; group progress/cancel/retry requires no step table.
5. Crash injection and the five relevant task races prove old-or-complete commands, terminal immutability, and stale-attempt exclusion.
6. Timeline list/load/save/reload, 409 conflict, 422 error, restart, draft recovery, and asset Range behavior pass the bridge and editor test lane.
7. Media import deduplicates identical bytes inside a project, detects mutation/missing locations, and never treats a path hash as content identity.
8. Reference and shot journeys round-trip exact media; primary selection and ordering constraints hold.
9. Online database plus managed-media backup restores a usable project; `doctor` quick/FK checks pass.
10. A clean release install supports editor, project, timeline, media, references, backup, and doctor without account, cloud service, or provider secret.
11. Removed old authorities and top-level CLI families are absent from the release artifact/help; import lint rejects removed authorities, kernel-to-pack dependencies, cross-pack table dependencies, and pack-owned writers.
12. Removing each pack in turn leaves the complete kernel suite green, and a software-engineering-agent schema can be sketched as the unchanged kernel plus different packs without changing a kernel table.

## 6. Risks and corrections

These are build risks, not migration risks.

| Risk | Proof | Correction |
|---|---|---|
| Direct run grouping is too weak for a real capability | Implement one multi-task generation/orchestration journey with dependencies, partial failure, cancel, and retry | Add only a measured field/read model to `runs` or `tasks`; do not restore generic plan steps. |
| Run status drifts from child tasks | Repository tests for child terminal transitions and zero-task runs | Update run projection/events in the same command or derive status in reads; `doctor` does not become a repair framework. |
| SQLite writer contention harms editor saves or executor completion | Concurrent two-tab saves, heartbeat load, CLI mutation, and materialization | Keep one in-process write queue, short transactions, bounded busy retry/backpressure; never add a second writer. |
| Crash leaves database rows and media bytes inconsistent | Stage bytes, hash/fsync, inject kills around placement and commit | Quarantine/stage bytes; publish atomically; on restart garbage-collect unreferenced staging, never invent rows from files. |
| Old capability code writes project files directly | Adapt one real generator/renderer and enforce repository/output-manifest boundary in tests | Quarantine capability outputs and let the repository materialize them; remove nonconforming capability from GA. |
| Bridge mapping drifts from the current editor | Run focused provider/persistence and bridge tests in CI | Fix the adapter to the current contract; do not restore the legacy backend or a parity harness. |
| Kernel and packs recouple during delivery | Catalog/FK lint finds a kernel FK or import into a pack, a cross-pack table FK, an unregistered vocabulary, or a pack-created transaction | Enforce manifest registration, dependency-ordered migrations, one-way FK/import lint, and the reusable command conformance kit in normal CI. |
| Pack factoring becomes only a directory convention | Removing timeline, shots, or references breaks kernel tests or requires a kernel schema edit | Run the pack-deletion factoring test and review a second-agent schema sketch before GA; move leaked domain assumptions back behind registries or pack repositories. |
| A speculative plugin platform consumes the greenfield build | Work appears for discovery, install/uninstall, hot reload, version negotiation, or a third-party ABI without a second agent consumer | Keep the single startup `register_pack()` composition explicit and in-tree at GA; extract the kernel and design a loader only when a real second composition supplies requirements. |
| JSON fields become dumping grounds | Require typed read models for current UI/CLI queries and bound payload/event sizes | Promote only observed indexed queries; keep logs/debug outside SQLite. |
| External-local media is omitted from backup | Surface realm and missing-file risk; managed copy remains default | Require users to opt into reference-in-place; offer relocate/copy-to-managed before backup. |
| Scope grows through deferred subsystems | Every story must map to a v10 phase and table/CLI owner | Reject or defer experiments, cloud, remote GPU, publish, editor rewrite, or compatibility work. |

## 7. Resolved decisions and remaining open questions

V10 resolves the questions that kept v9 broad:

| Question | V10 decision |
|---|---|
| Import old projects/history? | No. Import useful media bytes only. |
| Preserve two run dialects? | No. One new database run model. |
| Import audit or timeline chains? | No. No legacy event translation. |
| Translate plans, steps, groups, repeat, `for_each`, supersede? | No. Delete the concepts. |
| Keep `run_steps`/`run_step_tasks`? | No. Direct task membership makes the schema 20 tables. |
| How is fan-out grouped? | One run plus `tasks.run_id`/`run_ordinal`; execution edges use `task_dependencies`. |
| Keep editor FSA mode? | No. Delete it; bridge repositories are the only mode. |
| Preserve editor behavior? | Preserve the current bridge wire contract and draft-safety rules through ordinary editor/provider tests. |
| Classify/port all 553 tests? | No. New tests plus a small semantic carryover set. |
| Backup/doctor scope? | Online DB + managed media copy; SQLite quick/FK checks. |
| How is the schema generalized? | Fourteen kernel tables plus in-tree timeline, shots, and references packs; a second agent reuses the unchanged kernel with different packs. |
| Pack/element/model manifests in SQLite? | No. Manifests/install state stay file-side; schema-pack manifests declare the migrations whose domain tables live in the shared SQLite database. |
| Dynamic schema-pack loader at GA? | No. Boundary now, loader later: one explicit `register_pack()` call registers the shipped in-tree pack set at startup. |
| Deep legacy integration? | Not an offered scenario. |

Only four implementation choices remain, and none reopens the architecture:

1. **Managed media root and reference-in-place policy — before Phase 1 media fixtures.** Managed copy is the default; choose the exact OS path, staging layout, and relocation UX.
2. **Bounded fan-out limit — before Phase 1 receipt tests.** Set the maximum child tasks/events in one transaction and the chunked continuation envelope for larger runs.
3. **Closed vocabularies — before references/media repositories freeze.** Confirm relation kinds, reference kinds/roles/links, evidence kinds, and whether the current editor needs all of them at GA.
4. **Supported OS/browser/package matrix — before Phase 2 exit.** Test only declared release targets; do not recreate v6/v9's speculative browser ceremony.

## 8. Final recommendation and completion definition

Build the 20-table Astrid composition directly as a 14-table agent-agnostic kernel plus the timeline, shots, and references packs. Keep media in the kernel. Give every in-tree pack a manifest, independent forward migration sequence, namespaced registry declarations, repository registration through the kernel writer, and the shared conformance kit; do not build a dynamic loader. Treat current Astrid as a source-code parts bin, not a data source: retain its useful capability contracts, byte hashing/probing, atomic file-placement patterns, file-side manifests, and Reigh bridge shape; delete its storage authorities, histories, plans, sessions, threads, leases, legacy migrations, compatibility surfaces, and old tests. Runs are simple coordination records. Tasks are the only executable units. Evidence records observations. Dependencies order real tasks. Events record everything else.

V10 is complete when this document can be converted into three phase backlogs without another architecture decision; the standard Astrid creation composition produces exactly 20 tables from the kernel and installed-pack catalogs; each pack can be removed while the kernel suite stays green; a second agent can be sketched without changing a kernel table; run fan-out works without a step model; the eight-family CLI and reduced SDK are frozen; the current editor passes its focused repository-backed tests; a real generation/render/media/reference/timeline journey survives crash and restore; and the release artifact contains one semantic authority with none of v9's legacy preservation machinery.
