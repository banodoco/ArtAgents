# OpenRouter chat — plugin-data / generalizable-structure feedback (2026-08-14)

_Source: /Users/peteromalley/Downloads/OpenRouter Chat Fri Aug 14 2026.json. User pasted the plans and asked for a plug-in data approach: core table primitives reusable across agents, domain bundles layered on top._



---

## [0] USER

Hey, so see the below plans I'm working towards. In short, I'm trying to figure out, I'd like for our approach to data to be kind of almost like a plug-in approach where we basically provide a basic structure here. but then you know these different kind of like table primitives but then others can add their own tables or we can kind of like reuse the same primitives here in other agents as well you know so I'm trying to figure out how to structure that for example like that I don't know like maybe like the there's like a bundle of tables here which is like the you know the shop basic package which is like the shots you know and the shot associations and stuff like that. But how would it work if we wanted to basically make it so that this is both a plug-in into this system, so that the tables approach this like a plug-in into this system and second of all that it could be applied to other agents with similar principles for example imagine and we had software engineering agents as well.
```plaintext
# Unified data model plan v10: greenfield Astrid without plans or legacy tax

**Date:** 2026-08-13  
**Status:** decisive greenfield implementation plan; supersedes v9  
**Decision:** build the standalone local product directly on one 20-table SQLite authority, use the existing Reigh bridge wire shape, delete legacy authorities instead of importing them, and replace plan/step orchestration with runs that directly group immutable tasks  
**Foundation:** **tasks execute; everything else is an event; every exact asset is media; references add project semantics to media**

## Executive summary

V10 removes the preservation project that dominated v9. There are no existing-user, historical-parity, or legacy-data promises. Astrid starts from a fresh SQLite database. Old project, timeline, run, thread, session, plan, lease, event-chain, audit-ledger, Supabase, and editor FSA authorities are not migrated or conditionally supported; their modules and storage-specific tests are deleted as the replacement paths land. The only ingestion retained is ordinary media import: walk files, hash and probe their bytes, copy them into managed storage by default, and create `media` and `media_locations` rows through the normal repository transaction.

The schema falls from v7/v9's 22 tables to **20 tables**. `run_steps` and `run_step_tasks` are removed because the user's replacement of plan/steps eliminates their only independent justification. A `run` is now a coordination and observation container: the receipt for one command returns a `run_id`, directly created child `task_id`s, and any evidence IDs. Child tasks carry nullable `run_id` and `run_ordinal`; `task_dependencies` expresses real execution ordering or DAG edges. Inline work can produce run evidence without creating a task. Fan-out creates one run and N independently fenced tasks, not a plan, a synthetic parent task, or a row per pseudo-step.

The hard foundations remain: task admission, task/event separation, atomic command receipts, project-ordered events, timeline whole-document CAS, byte-SHA-256 media identity, ordered task outputs, attempt fencing, terminal immutability, crash injection, and a single repository-owned writer. References, media-first lineage, shots, and pack/manifest file-side boundaries also remain. These are product semantics and correctness boundaries, not legacy accommodations.

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
13. Keep pack, component, element, model, and tool manifests file-side; do not add catalog tables or migration logic for them.
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
| Teardown static/runtime trace evidence pack | **CUT** | Delete old modules and their imports at repository level. Keep one cheap import-lint rule preventing new product imports of Supabase and removed FSA authorities. |
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
| **KEEP FILE-SIDE** | Pack/component manifests; Pack install store/records/symlinks; Element manifests/components and override store; `models.yaml` and generation taxonomy | Confirmed executable/package inputs; selected IDs/digests are snapshotted into tasks/runs. |
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

### 2.1 Inventory and run grouping

The 20 tables are:

1. Foundation/history: `schema_migrations`, `projects`, `event_streams`, `events`, `command_receipts`.
2. Coordination/execution: `runs`, `evidence_items`, `tasks`, `task_dependencies`, `execution_attempts`, `task_outputs`.
3. Universal media: `media`, `media_locations`, `media_relations`.
4. Editorial: `timelines`, `shots`, `shot_items`.
5. Project semantics: `project_references`, `media_references`, `reference_links`.

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

This is fresh creation DDL. `schema_migrations` supports ordinary forward application upgrades; it is not legacy-data migration or cutover tooling.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE schema_migrations (
  version       INTEGER PRIMARY KEY CHECK (version > 0),
  name          TEXT NOT NULL UNIQUE,
  checksum      TEXT NOT NULL,
  applied_at    TEXT NOT NULL
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
  stream_type  TEXT NOT NULL CHECK (stream_type IN
               ('project','task','run','timeline')),
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

SQLite cannot conveniently express every cross-row invariant. Repository conformance must enforce that stream aggregate IDs, types, and projects match their `projects`, `runs`, `tasks`, and `timelines`; a task and its run share a project; dependencies are same-project and acyclic; task outputs and attempts belong to their task's project; an evidence `task_id`, when present, names a direct child of that evidence row's `run_id`, and its media shares the run project; media relations, shot items, and reference associations never cross projects; `winning_attempt_id` belongs to the task; variant edges are acyclic; and symmetric reference links use canonical ordering.

Every eventful command executes in one short `BEGIN IMMEDIATE` transaction:

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

Build the 20-table creation migration, migration runner for future application versions, repository-owned write queue, event/receipt registry, project and timeline repositories, task lifecycle and local executor, run grouping, evidence, media storage, references, and shots. Reuse proven SHA-256, probing, streaming, and atomic-placement code behind the new media repository. Adapt one real generation capability and one renderer through immutable task specs and output manifests. Delete `Step`/`TaskPlan`, session, thread, lease-file, current-run, inbox, JSONL authority, and Supabase project-state modules as their new path lands.

Tests are written for the new model. Selective carryovers are limited to:

- the five relevant task cancellation/expiry/completion races;
- SHA-256, MIME/ffprobe, staged placement, and multi-output vectors;
- capability invocation, rendering result, typed error, and manifest digest contracts that still describe the new product;
- repository contention, single-writer, and crash-injection cases.

**Phase 1 gate:** a fresh database has exactly 20 tables and all indexes/constraints; project/run/task/timeline stream association tests pass; one generation and one render complete through task → attempt → media → ordered outputs; synchronous understanding creates run evidence without a task; fan-out creates directly grouped tasks and dependencies with no step records; the race matrix, contention test, and statement-boundary crash injection pass.

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

Remove old modules, fixtures, CLI aliases, help entries, and optional dependencies in the same commits as their replacements. One build/import-lint rule rejects shipped imports of removed Supabase and FSA domain-authority modules; no runtime tracing or exhaustive writer census is required. Package the actual release artifact and run its tests from a clean account.

**Phase 3 gate:** the release artifact passes the focused core and editor suites; deliberate crashes expose only old-or-complete transactions; a concurrent writer test shows bounded SQLite busy handling; database plus media backup restores to an editable, hash-consistent project; `doctor` passes; no removed family appears in product help; and the team has completed a representative project using only the shipped surface.

## 4. Essential CLI and SDK surface

### 4.1 CLI

V10 has exactly eight top-level product families. Plural nouns own durable collections; `serve`, `doctor`, and `backup` are operational verbs/nouns already familiar to users. Every CLI/SDK mutation accepts an idempotency key or generates and returns one; machine-readable output uses one stable envelope for the new API only.

| Family | GA commands | Scope decision |
|---|---|---|
| `projects` | `create`, `list`, `show`, `update`, `select` | Project CRUD and preferences. First-run setup is automatic; no separate `setup` or `status` family. |
| `timelines` | `create`, `list`, `show`, `save`, `copy`, `archive`, `history`, `diff`; nested `shots list/create/add/remove/reorder` when the editor journey needs CLI access | Timeline CAS/history stays. No legacy event migration, push/pull/sync, audit, erase, or repair catalog. |
| `media` | `import`, `list`, `show`, `verify`, `relocate`, `relate` | `import` accepts files/folders only and creates no old project/run semantics. Nested `references create/update/archive/associate/link/list/show` exposes reference work without a ninth top-level family. |
| `tasks` | `create` (advanced), `list`, `show`, `cancel`, `retry`, `events` | Executor claim/start/heartbeat remain internal. Generation/render invocation is SDK/capability driven and returns task IDs. |
| `runs` | `list`, `show [--evidence]`, `cancel`, `retry-failed`, `events` | `show` includes evidence and child task progress. No step/plan/next/ack/skip/hook commands. |
| `serve` | no mandatory subcommand; optional `--project` and bind flags | Lazily creates/migrates the database, starts the bridge, and opens the editor. |
| `doctor` | default, `--json` | Read-only `PRAGMA quick_check`, `PRAGMA foreign_key_check`, schema version, and resolved data/media paths. No generic mutation. |
| `backup` | `create`, `restore` | Online SQLite backup plus managed-media directory copy. Restore verifies SQLite and FKs before activation. |

References and shots are not deferred as data concepts; only separate top-level families and exhaustive CLI polish are cut. They live primarily in the editor/SDK and, where useful, as nested `media references` and `timelines shots` commands. Evidence is returned from `runs show --evidence`. Events are inspected under their owning task, run, or timeline. Capability, renderer, executor, pack, element, model, theme, skill, authoring, replay, and test tools may remain behind a developer entry point, but they are not product CLI families and receive no legacy parity promise.

### 4.2 SDK and bridge

The SDK keeps lazy manifest discovery, `get_capability`, typed `invoke`/`generate`/`render`, repository-backed services for the eight product domains, command receipts, typed not-found/conflict/integrity errors, and result types that expose run/task/media IDs. It drops ordered `__all__` compatibility, raw `run_executor`/`run_orchestrator` promises, caller-supplied registry injection, thread/session/plan types, and old storage adapters. CLI handlers and bridge handlers call this service layer; neither reimplements SQL, lifecycle arbitration, hashing, or output materialization.

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

Backup pauses semantic writes briefly under the service writer lock, creates a SQLite online backup, copies the managed-media directory into the backup destination, then resumes writes. It does not enumerate source formats, classify attachments, generate a preservation manifest, include caches/staging/logs/packs/secrets, or promise external-local media capture. Restore stages both components, runs SQLite quick/FK checks, verifies managed media referenced by the restored rows during the normal open path, and swaps them into place only after validation.

`doctor` is deliberately not a universal invariant framework. It reports `quick_check`, foreign-key violations, schema version compatibility, and data/media paths. Repository and crash tests protect stream/task/media invariants during development. If a real post-GA corruption mode appears, add one named, backup-first repair for that code; do not prebuild a generic repair language.

Local projects, timelines, media, references, backup, doctor, and editor use require zero provider secrets. Provider-backed invocation resolves credentials in this order: explicit command/API option, process environment, OS keychain where supported. Delete cross-agent and unrelated-workspace `.env` scanning; env files do not override process environment. Secrets never enter events, receipts, task specs, logs, backups, or child processes except for an explicitly allowlisted capability environment.

## 5. Invariants and release acceptance

### 5.1 Kept invariants

- **Task admission:** a task exists only for a bounded immutable executable spec with exclusive claim or independently fenced attempts and one selectable terminal winner.
- **Event universality:** every meaningful non-task mutation appends a registered ordered event; heartbeats and narrow attempt liveness are the deliberate exception.
- **Task stream:** every task has exactly one same-project task stream beginning with `task_created`; task lifecycle projection and stream head change atomically.
- **Atomic receipts:** events, heads, projections, runs/group membership, dependencies, attempts, media, outputs, associations, and the command receipt commit or roll back as one command unit.
- **Idempotency:** an identical request/key returns its receipt; the same key with different canonical bytes fails.
- **Terminal immutability and fencing:** terminal tasks never resurrect; stale attempts never complete, cancel, fail, or materialize over a newer attempt.
- **Honest grouping:** a run may contain zero or many direct child tasks. It is never an executable parent. Dependencies connect only real executable work.
- **No plan semantics:** no step, cursor, group/repeat/`for_each`, supersede plan, acknowledgement, or hook state exists in the database or public API.
- **Timeline CAS:** document and registry advance together against the timeline stream head; stale saves do not mutate state.
- **Media identity:** SHA-256 of verified bytes is identity within a project; locators and aliases are replaceable.
- **Exact associations:** task outputs, shot placements, media relations, and reference associations point to exact media IDs and do not inherit invisibly across variants.
- **Single writer:** repositories are the only semantic writers. Bridge, CLI, SDK, executor, and media import use them; FSA and Supabase do not.
- **File boundary:** pack/component/element/model manifests and immutable non-critical diagnostics may remain files, but cannot mutate domain truth.
- **No dormant platform:** no accounts, billing, sharing, sync, remote-worker, experiment, legacy-alias, importer, or plan schema ships.

### 5.2 Dropped invariants and gates

V10 intentionally makes no promise of old project readability, old timeline identity, event/hash continuity, old run history, audit graph retention, session/thread/plan semantics, CLI/SDK name compatibility, importer idempotency, old/new projection parity, rollback to file authority, or restoration of external-local/scratch files. The v9 invariants “import real plans without losing group/repeat/`for_each`,” “recognize both run dialects,” “preserve original chain evidence,” and “pass continuity before/after import/flip/restore” are deleted rather than weakened.

### 5.3 GA acceptance

1. Fresh creation produces exactly the 20 tables and declared indexes; too-new schema opens read-only/fails clearly.
2. A real generation and render traverse task, attempt, event, media/location, ordered outputs, and receipt atomically.
3. Synchronous understanding produces a run and evidence with no convenience task.
4. Fan-out produces one run and direct child tasks with stable ordinals; dependencies gate execution; group progress/cancel/retry requires no step table.
5. Crash injection and the five relevant task races prove old-or-complete commands, terminal immutability, and stale-attempt exclusion.
6. Timeline list/load/save/reload, 409 conflict, 422 error, restart, draft recovery, and asset Range behavior pass the bridge and editor test lane.
7. Media import deduplicates identical bytes inside a project, detects mutation/missing locations, and never treats a path hash as content identity.
8. Reference and shot journeys round-trip exact media; primary selection and ordering constraints hold.
9. Online database plus managed-media backup restores a usable project; `doctor` quick/FK checks pass.
10. A clean release install supports editor, project, timeline, media, references, backup, and doctor without account, cloud service, or provider secret.
11. Removed old authorities and top-level CLI families are absent from the release artifact/help; the import lint rule is green.

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
| Packs/elements/models in SQLite? | No. Manifests/install state stay file-side. |
| Deep legacy integration? | Not an offered scenario. |

Only four implementation choices remain, and none reopens the architecture:

1. **Managed media root and reference-in-place policy — before Phase 1 media fixtures.** Managed copy is the default; choose the exact OS path, staging layout, and relocation UX.
2. **Bounded fan-out limit — before Phase 1 receipt tests.** Set the maximum child tasks/events in one transaction and the chunked continuation envelope for larger runs.
3. **Closed vocabularies — before references/media repositories freeze.** Confirm relation kinds, reference kinds/roles/links, evidence kinds, and whether the current editor needs all of them at GA.
4. **Supported OS/browser/package matrix — before Phase 2 exit.** Test only declared release targets; do not recreate v6/v9's speculative browser ceremony.

## 8. Final recommendation and completion definition

Build the 20-table model directly. Treat current Astrid as a source-code parts bin, not a data source: retain its useful capability contracts, byte hashing/probing, atomic file-placement patterns, pack/manifests, and Reigh bridge shape; delete its storage authorities, histories, plans, sessions, threads, leases, migrations, compatibility surfaces, and old tests. Runs are simple coordination records. Tasks are the only executable units. Evidence records observations. Dependencies order real tasks. Events record everything else.

V10 is complete when this document can be converted into three phase backlogs without another architecture decision; the creation migration produces exactly 20 tables; run fan-out works without a step model; the eight-family CLI and reduced SDK are frozen; the current editor passes its focused repository-backed tests; a real generation/render/media/reference/timeline journey survives crash and restore; and the release artifact contains one semantic authority with none of v9's legacy preservation machinery.

```
```plaintext
# Astrid-first two-week sprint plan

**Date:** 2026-08-13  
**Status:** executable delivery plan derived from `unified-data-model-plan-v10-20260813.md`  
**Planning unit:** two-week sprint  
**Base case:** four experienced engineers  
**Recommended forecast:** eight sprints to GA, with Sprints 9–10 held as conditional contingency

**Revision:** Revised 2026-08-13: applied the 10 review fixes from `astrid-first-sprint-plan-review-20260813.md`.

## Executive summary

The recommended base plan is eight two-week sprints. Sprint 1 deliberately spends most of the team on the load-bearing event, receipt, migration, and single-writer transaction core; it also takes one thin repository-backed editor journey all the way from project creation to timeline save and reload. That early editor slice is a risk probe, not a shortcut around the core. Sprint 2 opens the first safe parallel lanes—executor lifecycle and managed media—after the transaction contract exists. Sprint 3 closes v10 Phase 1 by completing reference and shot repositories and proving real generation and rendering, synchronous understanding as run evidence, direct-child fan-out, the five task races, contention, and crash atomicity.

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
- forward migrations are allowed for layouts created during development, but no compatibility layer is built for unshipped schemas.

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

- exactly the 20 tables and declared indexes in v10 §2.1–§2.2;
- repository-enforced constraints and one short `BEGIN IMMEDIATE` command unit from v10 §2.3;
- the three phase gates in v10 §3;
- exactly eight top-level product CLI families from v10 §4.1;
- the reduced SDK and frozen bridge surface from v10 §4.2;
- the backup, doctor, and secrets behavior in v10 §4.3;
- every kept invariant and all eleven GA acceptance items in v10 §5.

No sprint may solve a delay by restoring plans, steps, session or thread state, file/JSONL semantic authority, Supabase/FSA writes, a multi-source importer, or legacy aliases.

## 2. Sprint map

### 2.1 Overview and critical path

| Sprint | Theme | Primary goal | Key deliverables | Gate |
| --- | --- | --- | --- | --- |
| **1** | Transaction foundation + early editor spike | Establish the only safe write boundary and expose editor-contract risk immediately | 20-table migration, migration runner, writer queue, event/receipt kernel, project and first timeline repositories, thin project → timeline save → reload bridge path | Exact catalog and receipt tests pass; retry is deterministic; stale save is mutation-free; crash shows old-or-complete; one real editor provider save test passes |
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

- **Sprint 1 is intentionally constrained.** Two engineers pair on schema/events/receipts/writer ownership; one builds project/timeline repositories; one maps the existing bridge contract and connects the thin editor slice. Executor or media semantic writes do not start on a provisional transaction API.
- **Executor ∥ media opens in Sprint 2.** Both consume the same receipt/event/repository transaction primitive. Their common integration point is task completion materialization, closed in Sprint 3.
- **Runs/evidence ∥ references/shots ∥ capability adapters opens in Sprint 3.** Direct child grouping and zero-task runs can develop beside generation/render adapters and the exact-media editorial repositories, but the Phase 1 gate joins all of them through registered events, heads, atomic receipts, and §2.3 constraints.
- **Editor bridge ∥ editorial integration opens in Sprint 4.** The bridge and editor contract/provider lane consumes stable timeline, media, reference, and shot repositories from Phase 1; Sprint 4 adds service/editor journeys rather than a second semantic implementation.
- **CLI/SDK work opens after repositories have real journeys.** Sprint 5 wraps services; it does not define domain semantics inside handlers.
- **Packaging ∥ removal/hardening opens in Sprint 6 and closes at GA.** Operational work can proceed beside authority cleanup, but both must be tested in the built artifact by Sprint 8.

### 2.3 GA acceptance coverage

| V10 §5.3 acceptance item | First meaningful proof | Completion sprint | Release rerun |
| --- | --- | --- | --- |
| 1. Exactly 20 tables/indexes; too-new schema behavior | S1 | S1 | S8 |
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

## 3. Per-sprint detail

### Sprint 1 — Transaction foundation and early editor spike

**Goal:** Build the event/receipt/repository kernel without rushing it, then prove that its first timeline save can satisfy the current editor contract.

**Work items and dependencies**

1. Implement v10 §2.2 **Full creation DDL** exactly: all 20 tables, declared unique and lookup indexes, `foreign_keys`, WAL, synchronous mode, and bounded busy timeout. Add a catalog test that fails on an extra/missing table or index; absence of `run_steps`, `run_step_tasks`, plans, sessions, aliases, or importer tables is affirmative evidence.
2. Build the forward-only `schema_migrations` runner with name/checksum validation, application-version compatibility, deterministic fresh creation, and the v10 §5.3(1) too-new behavior: open read-only where safe or fail clearly without mutation.
3. Establish the single repository-owned write queue and short `BEGIN IMMEDIATE` unit of work. Add bounded busy retry/backpressure and fixtures that forbid handlers from opening semantic write transactions directly.
4. Define the event registry and stream factory for `project`, `task`, `run`, and `timeline`; implement consecutive `projects.event_head_seq` allocation, stream-head CAS, bounded `changes_json`, event schema versioning, and event ordering queries.
5. Implement canonical request serialization/hashing and `command_receipts`: identical key/request returns the stored full result; identical key/different bytes returns typed `idempotency_mismatch`; receipt event IDs and project sequence range match the transaction.
6. Implement `ProjectRepository.create/list/show/update` and the first `TimelineRepository.create/list/show/save` methods. Creation owns streams; save atomically updates `document_json` and `asset_registry_json`, appends its event, advances the head, and writes the receipt.
7. Implement the first §2.3 conformance checks: stream aggregate ID/type/project agreement, timeline/project ownership, and mutation-free rejection of stale timeline CAS.
8. Add statement-boundary crash injection for project create and timeline save, plus a concurrent two-save test. Each observation must be either pre-command or a mutually complete projection/event/head/receipt result.
9. Build a thin repository-backed bridge slice for `GET /health`, `GET /projects`, timeline list/load, and timeline save. Preserve the v10 §4.2 payload fields and hide the internal receipt from the unchanged editor response envelope.
10. Run a focused real `AstridBridgeDataProvider`/persistence test against that slice, including a successful save/reload and stale `expected_version` → 409 `timeline_version_conflict`. This is the earliest warning for wire-contract drift.
11. Create the required [v10 implementation decision artifact](astrid-v10-implementation-decisions.md). Before the Sprint 1 gate it fixes the managed media root/reference-in-place/staging policy; the exact allowed `media_relations.kind` values; the fan-out maximum child count, continuation envelope, expected-head/CAS fields, and receipt linkage; and the exact evidence kinds plus reference kinds/roles/link kinds. The same artifact names the supported OS/browser/package matrix owner and a Sprint 5 deadline, before Sprint 6 Phase 2 work begins.

**Parallel lanes:** Engineers A+B pair on migration, events, receipts, writer queue, and crash harness. Engineer C builds project/timeline repositories against that kernel. Engineer D maps the frozen bridge fields/errors and connects only the thin save journey. D does not create a second storage adapter.

**Deliverable:** From a fresh checkout and database, create a project, create/list/load a timeline, save object `config` plus object `registry` at numeric `config_version`, reload it through the bridge, and observe a durable event/receipt chain after restart.

**Acceptance gate:** Exact schema and index assertions pass; too-new handling is safe; idempotent replay and mismatch behavior pass; project/timeline stream association passes; a stale save returns 409 with no mutation; crash injection proves old-or-complete; one current editor provider/persistence save test passes. The decision artifact contains the frozen media layout/relation kinds, complete fan-out contract, exact evidence/reference vocabularies, and the Sprint 5 platform-matrix owner/deadline. Executor and media repository implementation stays blocked until this gate is green.

### Sprint 2 — Executor and media foundations

**Goal:** Build independently fenced executable tasks and crash-conscious media identity in parallel on the Sprint 1 transaction core.

**Work items and dependencies**

- Implement `TaskRepository` admission for bounded immutable specs, `spec_hash`, input manifests, task streams beginning with `task_created`, queued/blocked state, same-project acyclic `task_dependencies`, and stable `run_ordinal` preparation. A task is admitted only for independently claimable/attempt-fenced work.
- Implement internal claim/start/heartbeat/expiry primitives over `execution_attempts`. Heartbeats are the narrow non-event exception and advance `status_version`; claim, start, expiry, cancellation, retry, failure, and completion remain registered semantic events.
- Implement terminal immutability and winning-attempt ownership checks early. Add queued cancel versus claim and stale attempt versus transition tests before capability adapters depend on them.
- Validate task admission and continuation preparation against the frozen Sprint 1 fan-out maximum, envelope, expected run-stream head/CAS fields, ordinal rules, and receipt linkage. Sprint 2 may implement supporting validation, but it does not redesign or re-freeze the contract; transactional fan-out completes in Sprint 3.
- Implement `MediaRepository` over `media`, `media_locations`, and `media_relations`. Identity is project-scoped SHA-256 of verified bytes; path, URL, registry key, and display name are locators only.
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
- Implement `ReferenceRepository` for `project_references`, `media_references`, and `reference_links` using the frozen kinds/roles/link kinds: archive behavior, exact-media association, one primary canonical, canonical ordinal ordering, contextual-task rules, same-project enforcement, and canonical ordering for symmetric links.
- Implement `ShotRepository` for `shots` and `shot_items`: stable ordering, add/remove/reorder, exact media IDs, source frames, and same-project enforcement.
- For reference primary replacement, associate, link, and shot reorder, assert registered event order, affected stream/project heads, and atomic projection/association/order state plus complete receipt. Identical replay returns the original result, mismatched-key reuse fails before mutation, and representative statement-boundary failures reopen old-or-complete.
- Implement bounded one-transaction fan-out: run, run stream, child task streams/tasks with unique ordinals, dependency edges, creation events, and one receipt. Implement receipt-linked continuation CAS, ordinal allocation, replay/collision behavior, and terminal-run rejection. Prove no step records or plan cursor exist.
- Adapt one real generation capability and one real renderer to immutable task specs and file-side capability manifests. Capabilities write only quarantined outputs plus declared manifests; repository completion verifies and materializes media, locations, ordered `task_outputs`, relations, winning attempt, events, and receipt atomically.
- Implement synchronous understanding as a run plus `evidence_items`, optionally linked media, and no convenience task. Its receipt returns run/evidence/media IDs.
- Run all five normative races: queued cancel vs claim; running cancel vs completion; running cancel vs expiry/requeue; stale failure vs newer attempt; terminal task vs retry/later cancellation. Assert event order, attempt fences, output presence/absence, and no resurrection.
- Extend statement-boundary crash injection across fan-out and task completion, including media placement; run a concurrent editor save + heartbeat + CLI/repository mutation + completion test through the one writer queue.
- Delete or make unreachable the corresponding `Step`/`TaskPlan`, session, thread, lease-file, current-run, inbox, JSONL authority, and Supabase project-state paths as their replacements land. Preserve pack/manifests and optional immutable diagnostics only.

**Parallel lanes:** Run/evidence/fan-out; reference/shot repositories; generation/render adapters; lifecycle/race and crash/contention/authority deletion. All lanes converge at the complete Phase 1 conformance gate; capacity moves between lanes before any Phase 2 work begins.

**Deliverable:** One generation and one render traverse task → attempt → event → verified media/location → ordered output → receipt; synchronous understanding produces run evidence without a task; a multi-task run honors dependencies, reports progress, and supports eligible cancel/retry; repository clients construct exact-media reference and shot models with primary, association, link, and ordering invariants intact.

**Acceptance gate:** The complete v10 §3 **Phase 1 gate** passes: exactly 20 tables and constraints; all run/evidence and reference/shot same-project, exact-media, primary, ordering, contextual-task, and symmetric-link checks; real generation/render; zero-task understanding; direct-child fan-out; five races; bounded contention; and statement-boundary crash injection. Reference primary/associate/link and shot reorder also pass event/head/atomic-receipt, replay, and mismatched-key conformance. Any failure in a repository or atomicity invariant blocks Phase 2; no alternate semantics may be built.

### Sprint 4 — Full editor bridge and editorial integration

**Goal:** Make the current Reigh editor reliable on the repository bridge and expose the Phase 1 reference/shot semantics through editor and service journeys.

**Work items and dependencies**

- Complete the frozen v10 §4.2 routes: project list; timeline list/load/save addressed by UUID or supported ULID; asset `GET`/`HEAD`; health; and only required OPTIONS/CORS behavior.
- Preserve the consumed payload fields: `timeline_id`, `timeline_ulid`, `slug`, `name`, `is_default`, loose `config`, `registry.assets`, numeric opaque `config_version`. Derive the bridge save idempotency key from identity, expected version, and canonical payload while returning the unchanged editor envelope.
- Implement typed 404 envelopes, 409 `timeline_version_conflict`, 422 `schema_incompatible`, successful save payload, single-range 206, invalid-range 416, and restart durability. Do not pin incidental timing or headers unless the client consumes them.
- Run the existing `AstridBridgeDataProvider`, provider compatibility, IndexedDB timeline-draft, poll-sync, timeline persistence, and save utility lanes against repositories. Assert that failed saves do not acknowledge or erase recovery data, successful covering saves may clear it, polling cannot overwrite pending local work, and failed load disables persistence.
- Add the end-to-end editor test: list → load → edit → save → reload, stale save, invalid schema, process restart, draft recovery, and media Range playback.
- Integrate the Sprint 3 `ReferenceRepository` and `ShotRepository` into editor/service read and mutation journeys without duplicating their semantics. Rerun their exact-media, same-project, primary, association/link, stable ordering, event/head, receipt, replay, mismatch, and crash conformance suites through the integrated service boundary.

**Parallel lanes:** Two engineers on bridge/server and repository mapping; one on the editor contract/provider test lane and FSA removal; one on editorial service integration over the gated reference/shot repositories. The editor gate wins integration conflicts.

**Deliverable:** The current editor edits a repository timeline across restart with correct conflicts, drafts, polling, and byte-range assets; editor/service clients exercise the gated exact-media reference and shot models without a second writer.

**Acceptance gate:** GA item 6 passes in the editor contract/provider lane. All supported bridge mutations have internal receipts without changing response envelopes. FSA is not a fallback. Integrated reference/shot journeys preserve the Sprint 3 constraints and command conformance before public CLI commands wrap them.

### Sprint 5 — Reduced SDK, five domain CLI families, and semantic journeys

**Goal:** Expose the domain product through a thin service layer, reduced SDK, shared stable envelope, and the five functional domain CLI families.

**Work items and dependencies**

- Freeze shared service methods and result models so CLI and bridge handlers never implement SQL, hashing, lifecycle arbitration, or output materialization.
- Keep lazy manifest discovery, `get_capability`, typed `invoke`/`generate`/`render`, command receipts, result IDs, event reads/subscriptions where useful, and typed not-found/conflict/integrity/idempotency errors. Remove raw registry injection, storage adapters, thread/session/plan types, and ordered-export compatibility promises.
- Implement `projects create|list|show|update|select` and non-authoritative preference selection.
- Implement `timelines create|list|show|save|copy|archive|history|diff`, plus nested `shots list|create|add|remove|reorder` where the editor journey needs CLI access.
- Implement `media import|list|show|verify|relocate|relate`, plus nested `references create|update|archive|associate|link|list|show`.
- Implement `tasks create|list|show|cancel|retry|events` and `runs list|show --evidence|cancel|retry-failed|events`. Claim/start/heartbeat stay internal; no plan/step/next/ack/skip/hook command appears.
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

- Implement `serve` with lazy creation/migration of the application database and data directories, repository bridge startup, optional project/bind flags, and the chosen packaged/current editor path. Local create/edit/import works without Node as a user prerequisite if the package promise says so.
- Implement `backup create`: briefly pause semantic writes under the service writer lock, use SQLite online backup, copy managed media, exclude caches/staging/logs/packs/secrets/external-local media, and resume safely. It accepts or generates and returns an idempotency key in the shared stable envelope; identical request/key replay returns the original result, while mismatched canonical request reuse fails before mutation.
- Implement staged `backup restore`: validate quick check, foreign keys, schema compatibility, and referenced managed media before atomic activation. It obeys the same idempotency-key, replay/mismatch, and stable-envelope contract as every other mutation. Statement-boundary activation tests prove old-or-complete behavior; a failed or mismatched restore leaves the current installation untouched.
- Implement `doctor [--json]` as read-only quick check, foreign-key check, schema version compatibility, and resolved data/media paths—no speculative repair framework.
- Enforce zero-secret core use and provider credential resolution: explicit option → process environment → supported OS keychain. Remove cross-agent/unrelated-workspace `.env` scavenging and prevent secrets entering specs, events, receipts, logs, backups, or unallowlisted child environments.
- Delete old semantic modules, fixtures, optional dependencies, CLI aliases/help, FSA writer, and Supabase product paths in replacement commits. Add the cheap build/import-lint rejection for removed FSA/Supabase authority imports.
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

**Deliverable:** A representative completed project and a checked-in evidence checklist covering v10 §5.3 items 1–10 against the unpackaged release candidate, plus provisional source/build absence proof for item 11.

**Acceptance gate:** GA items 1–10 pass at least once in integrated form, and item 11 has provisional source/build proof only. Final installed-artifact, executable-help, import, entry-point, and dependency proof for item 11 remains in Sprint 8. No open severity-one/two correctness defect remains. Lower-severity issues are explicitly dispositioned without violating v10. Failure here is what normally consumes Sprint 8 buffer or triggers Sprint 9; it is not solved by shrinking the acceptance matrix.

### Sprint 8 — Release artifact hardening and GA

**Goal:** Prove the supported release artifact, not the source tree, and close the normal GA gate.

**Work items and dependencies**

- Build/install the actual artifact on every supported OS/browser/package combination and a clean account. Run project, editor, timeline, media, references, backup, and doctor with zero secrets.
- Run the focused core repository, bridge contract, current editor provider/persistence/draft/poll, real generation/render, crash/race/contention, backup/restore, and import-lint suites from the artifact layout.
- Rehearse one forward application migration and too-new-schema handling. Verify failure is clear and nonmutating; do not add compatibility for old Astrid authorities.
- Audit installed files, imports, entry points, help, dependencies, default directories, and network calls. No old authority or removed top-level family may ship; no dormant account/cloud/remote-worker/experiment/plan schema may appear.
- Fix release-candidate defects and rerun the smallest relevant gate immediately, then the full GA matrix before tagging.
- Publish the completion evidence: schema/index catalog, receipt/idempotency proof, capability journeys, zero-task evidence, fan-out, race/crash report, editor contract/provider lane, media verification, reference/shot round trip, restore/doctor, clean-install log, and artifact authority audit.

**Parallel lanes:** Packaging/platform matrix; final editor and bridge suite; core failure suites; artifact/help/import audit. A single release owner controls the candidate and evidence set.

**Deliverable:** A release candidate whose installed artifact has one semantic authority and passes v10 §5.3 without test skips or manual repair.

**Acceptance gate:** Full v10 §3 **Phase 3 gate** and all eleven §5.3 acceptance items pass against the artifact. Any material repository/atomicity failure—including timeline, executor, media, references, shots, backup/restore, or systemic contention—activates Sprint 9; a bridge/editor, supported-platform, or package/runtime failure activates Sprint 10. Otherwise ship.

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

Buffer policy is explicit. Each sprint reserves integration/review capacity rather than planning all eight gross PW as feature work. Sprint 8 is a normal stabilization sprint, not optional polish. Sprints 9–10 exist for high-case variance. Buffer may close failures in existing gates; it may not add deferred features, broaden the support matrix, or substitute manual procedures for automated acceptance.

## 6. Sprint 1 concrete backlog

The following tickets are the starting backlog. Ticket order is dependency order; lanes may work in parallel only where the dependency column permits it.

| ID | Ticket | Concrete acceptance | Dependency / lane |
| --- | --- | --- | --- |
| **S1-01** | Land exact v10 creation migration | Fresh DB has exactly the 20 §2.1 tables and every §2.2 named index; PRAGMAs are effective; forbidden plan/session/legacy tables are absent | First; A+B pair |
| **S1-02** | Build forward migration runner | Records version/name/checksum; rejects changed checksum; applies once; too-new database fails clearly/read-only without mutation | S1-01; A |
| **S1-03** | Add catalog/conformance fixture | CI compares `sqlite_master`, FKs, checks, partial unique indexes, and migration version to an explicit expected manifest | S1-01; B |
| **S1-04** | Implement repository write queue/UoW | All semantic mutations enter one queue and one short `BEGIN IMMEDIATE`; busy handling is bounded; test rejects nested/parallel direct writers | S1-01; A+B |
| **S1-05** | Register base event vocabulary and streams | Project/timeline event types validate; project/task/run/timeline stream factory enforces aggregate/type/project; sequence allocation is gap-free per committed command | S1-04; B |
| **S1-06** | Implement canonical request hashing | Canonical equivalent requests hash equally; meaningfully different bytes hash differently; payload/event size limits are enforced | S1-04; A |
| **S1-07** | Implement command receipts and replay | One receipt captures transaction ID, stream sequence, project range, ordered event IDs, complete result JSON; same retry returns it; changed request/key pairing raises typed mismatch | S1-05/S1-06; A+B |
| **S1-08** | Project repository vertical command | `create/list/show/update` use project stream, event, projection, and receipt atomically; slug uniqueness and idempotent create behavior tested | S1-07; C |
| **S1-09** | Timeline create/list/show repository | Creates timeline stream and initial document/registry; UUID identity and supported ULID address are represented; list/load read models match bridge needs | S1-07/S1-08; C |
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
| **S1-17** | Sprint gate script/checklist | One command creates fresh DB, verifies catalog, runs receipt/replay/crash/contention suites, starts bridge, and runs focused editor save test; output is retained in CI | All tickets; integration owner |

### Sprint 1 review checklist

The sprint review must answer “yes” to each item:

- Does every mutation shown use the same writer queue, event registry, receipt code, and repository transaction boundary?
- Can the team show the exact event IDs, project sequence range, stream head, projection, and receipt from a project create and timeline save?
- Does replay return the original result, and does mismatched key reuse fail before mutation?
- Does a stale editor save return 409 while leaving document, registry, heads, events, and receipts unchanged?
- Does every injected crash reopen to old-or-complete state?
- Does the editor provider test use the repository-backed bridge rather than a fake or old adapter?
- Are executor and media lanes consuming a stable kernel instead of copying provisional transaction logic?
- Are the media layout/relation kinds, full fan-out contract, and evidence/reference vocabularies closed in the required decision artifact, with a named Sprint 5 platform-matrix owner/deadline?

If any answer is no, Sprint 1 is not complete. The correct response is to finish the foundation, not to start more dependent work and hope integration will clarify it later.

```


---

## [1] ASSISTANT

This maps really cleanly onto what you already have, because v10's foundation sentence is secretly a layering statement: **"tasks execute; everything else is an event; every exact asset is media; references add project semantics to media."** The first three clauses are agent-agnostic. Only the last one (and timelines/shots) is video-product-specific. So the plugin boundary already exists in your schema — you just need to name it and enforce it.

## 1. The layer split hiding in your 20 tables

| Layer | Tables | Portable to a SWE agent? |
|---|---|---|
| **Kernel (14 tables)** | `schema_migrations`, `projects`, `event_streams`, `events`, `command_receipts`, `runs`, `evidence_items`, `tasks`, `task_dependencies`, `execution_attempts`, `task_outputs`, `media`, `media_locations`, `media_relations` | Yes, unchanged. Source files, diffs, build logs, and test reports are all just bytes — `media` with `text`/`data` kinds covers them. Attempt fencing, receipts, fan-out, evidence: identical needs. |
| **Timeline pack (1)** | `timelines` | No — video-specific. |
| **Shot pack (2)** | `shots`, `shot_items` | No — but a SWE agent's analog ("changesets" grouping file media, "review threads" grouping diff media) follows the identical shape: a project-scoped container + ordered exact-media items. |
| **Reference pack (3)** | `project_references`, `media_references`, `reference_links` | Actually semi-portable — "named entity with canonical media, roles, and typed links" works for characters *or* for services/modules/APIs. You could reuse it with a different kind vocabulary. |

So "the shot basic package" you're describing is exactly `shots` + `shot_items` + its event kinds, repository, conformance checks, and nested CLI commands — as one unit.

## 2. The plugin laws (what makes a bundle a pack instead of a fork)

The reason this works without a framework is that your kernel already has exactly one extension currency: **project-scoped IDs plus polymorphic events**. Codify these rules:

1. **FK direction is one-way.** Packs may FK into kernel tables (`project_id`, `media_id`, `task_id`). The kernel **never** FKs into pack tables. Kernel rows refer to pack rows only via the already-polymorphic `events.subject_type`/`subject_id`. Check your DDL: this is already true — `shot_items → media`, `media_references → tasks`, and nothing in the kernel names a shot or reference. Keep it true by lint rule.
2. **Packs talk to each other only through kernel currencies.** Shots reference media IDs, not timeline rows. If a pack genuinely needs another pack's table, that's a declared dependency in its manifest, not an ambient import.
3. **No pack owns a writer.** Packs register repositories with the single write queue and get a unit-of-work handle *inside* the kernel's `BEGIN IMMEDIATE` — with the `project_seq` allocator, stream-head CAS, event append, and receipt writer provided by the kernel. A pack physically cannot open its own transaction.
4. **Every pack command must pass the kernel conformance kit**: idempotent replay, mismatched-key rejection, statement-boundary crash injection, same-project assertions. You already built this harness in Sprint 1 — packaging it as a reusable test kit is what makes third-party tables trustworthy.
5. **Namespaced vocabularies.** Event kinds become `shot.item_added`, `reference.primary_changed`, `timeline.saved`; command kinds and stream types likewise.

## 3. Three small schema/kernel changes to enable this

You need almost nothing, but these three are load-bearing and cheap to do *now* in Sprint 1:

1. **Namespace migrations.** `schema_migrations` gets a `pack TEXT NOT NULL DEFAULT 'core'` column with `PRIMARY KEY (pack, version)`. Core and each pack version independently, forward-only, applied in dependency order. Your catalog test then asserts "core tables + tables of installed packs," not a hardcoded 20.
2. **Un-hardcode `event_streams.stream_type`.** The `CHECK (stream_type IN ('project','task','run','timeline'))` bakes a pack ('timeline') into kernel DDL. Move that validation into the repository layer against a registry of pack-declared stream types (SQLite CHECKs can't be dynamic anyway). Packs then choose: hang events on the project stream, or register their own stream type (as timelines do, because they need per-aggregate CAS).
3. **Decide media's citizenship explicitly: it's kernel.** `task_outputs.media_id` couples the executor to media, and that's fine — "every exact asset is media" is the portable claim. Don't try to make media a pack; you'd just reinvent it in every agent.

## 4. What a pack actually is, concretely

A schema pack is a manifest plus code — deliberately shaped like your existing file-side capability pack manifests, but for the database side:

```yaml
id: shots
version: 3
depends_on: [core >= 1]        # media lives in core
migrations: [001_shots.sql, 002_shot_items.sql, 003_source_frame.sql]
stream_types: []               # events ride the project stream
event_kinds: [shot.created, shot.item_added, shot.item_reordered, ...]
command_kinds: [shot.create, shot.add_item, shot.reorder, ...]
repositories: [ShotRepository] # registered with the kernel writer
conformance: [same_project, exact_media, stable_sort_keys]
cli_mounts: {timelines: shots} # nested, per your eight-family rule
bridge_mounts: []              # none needed yet
```

Your eight CLI families then decompose as: kernel owns `projects`, `media`, `tasks`, `runs`, `serve`, `doctor`, `backup`; the timeline pack contributes `timelines`; shots and references mount nested (`timelines shots`, `media references`) — which is exactly what v10 §4.1 already does. A SWE agent ships the same seven kernel families plus, say, `changes` and `reviews` from its own packs. `backup` and `doctor` generalize for free because everything is still one SQLite file plus one managed-media directory regardless of installed packs.

## 5. The critical restraint: boundary now, loader later

Don't build a dynamic plugin loader in v10 — that would violate your own "no dormant platform" invariant and eat Sprint 1. Instead:

- **Now (fits inside your existing sprint plan):** structure the code as `core/` + in-tree `packs/timeline`, `packs/shots`, `packs/references`, each with a manifest, its own migrations, and registration through one `register_pack()` call at startup. Enforce the FK-direction and no-direct-writer rules with the same cheap import-lint mechanism you already planned for FSA/Supabase. The only sprint-plan deltas are in S1: the `pack` column on `schema_migrations`, the stream-type registry instead of the CHECK, and per-pack event/command registration — each of which is an hour-scale change to tickets S1-01, S1-03, and S1-05.
- **Later (when the second agent is real):** extract `core/` into a shared library, and the loader becomes trivial because every pack already speaks manifest + migrations + registration. The SWE agent is then `core` + its own packs, and your conformance kit is what makes its new tables trustworthy on day one.

The test of the design is your own dogfood rule, applied sideways: **a pack is correctly factored when you can delete it and the kernel's entire test suite still passes** — and when the SWE agent can be sketched without touching a single kernel table. By that test, your current schema is already ~90% there; the remaining 10% is the three Sprint-1 changes above and writing the plugin laws down so they survive contact with Sprint 4.

<details><summary>reasoning</summary>

The user wants to design an extensible architecture where core table primitives like events, receipts, tasks, and runs form the foundation, with domain-specific bundles layered on top as plugins. The goal is to make these core primitives reusable across different agents while keeping domain-specific tables isolated as swappable components.

Looking at their existing 20 tables, I can see they naturally stratify into a kernel layer (migrations, projects, event streams, events, receipts, runs, tasks, and their dependencies), a media pack that bridges kernel and domain concerns, and domain-specific packs for video workflows like timelines, shots, and references. The key challenge is decoupling the hardcoded constraints and foreign key assumptions that currently tie these layers together — for instance, the event_streams table has a CHECK constraint that only allows specific stream types, which would need to become extensible.

The real architectural moves are: make stream types and command kinds registrable through a plugin API rather than hardcoded; decide whether media belongs in the kernel or as a blessed pack; enforce the rule that packs can reference kernel tables but never the reverse (using polymorphic soft references in events where needed); namespace migrations per pack so they version independently; and ensure plugins register their repositories and event handlers with the kernel's writer queue rather than opening their own connections. The CLI and tooling would then need to discover and load packs dynamically. For the software-engineering agent, I'd map domain packs to repositories, branches, commits, or maybe workspaces and changesets — potentially adding a PR review pack and codebase index pack alongside a reusable references pack that generalizes the kind vocabulary. I'm sketching out a concrete pack manifest structure where each schema pack declares its id, version, dependencies, and migrations, establishing how these domain modules compose together.

The kernel contract with packs would provide a unit-of-work handle inside a transaction, a project sequence allocator, stream head compare-and-swap, event append, receipt writing, idempotency guarantees, and a media materialization hook. I'm also identifying schema changes needed — adding a pack column to schema_migrations with a composite primary key, and moving stream_type constraints to the repository level.

For event kinds, I'm leaning toward namespacing them like `pack.event_name` to avoid collisions. On media placement, I'm weighing whether to keep it as a separate tier-1 pack or include it in the kernel itself — given that the foundation treats every exact asset as media and the SWE agent needs media for source files and build logs, I think media belongs in the kernel as a core concept, maybe renamed to "assets" for clarity.

So the kernel becomes tasks, events, runs, and media as the foundation, with packs handling timelines, shots, and references as optional layers. That gives us 14 core tables plus 3 packs, each with their own tables — clean separation where a SWE agent could add workspace, changeset, and review packs on top of the same kernel.

Now I'm laying out the extension rules: packs can reference the kernel but the kernel never reaches into packs, except through polymorphic event subjects. Packs must go through the event system and pass the same conformance checks as the kernel — crash injection, idempotency, project scoping. Every pack table needs project_id or a foreign key to something project-scoped so the kernel can enforce isolation.

Event kinds, stream types, and vocabularies all get namespaced by pack. Migrations are forward-only and ordered by dependency; uninstall probably won't be supported at GA — the recommendation is to disable the code and leave the data behind. Cross-pack references only flow through kernel currencies like media IDs and task IDs, so if one pack needs to link to another, that dependency gets declared in the manifest.

I'm checking where pack aggregates get their event streams — shots and references don't have their own streams right now, so they'd use the project stream, but the stream_type enum only allows project, task, run, or timeline. The schema migration needs a pack column, stream type validation moves to the repository layer, and each pack registers its event and command types. The CLI uses nested mounts organized by family—kernel owns core families like projects and tasks, while packs contribute their own like timelines and media.

Since everything lives in a single SQLite database with a managed media directory, backup and doctor operations generalize automatically, and doctor can later run pack-declared checks. I should write this up with structure—headers, a layering table, a manifest sketch, maybe collapsible sections—keeping it substantial but focused, around 700-1000 words in markdown.

</details>