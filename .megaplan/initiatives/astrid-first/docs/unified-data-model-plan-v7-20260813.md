# Unified data model plan v7: media first, references built in

**Date:** 2026-08-13  
**Status:** greenfield implementation plan; supersedes v6 as the target architecture  
**Decision:** build the local product directly on a 22-table SQLite model centered on hash-identified media  
**Foundation:** **tasks execute; everything else is an event**

## Executive summary

V7 keeps v6's greenfield posture and execution ontology, but applies its own simplicity rule more rigorously. The shipped database falls from **27 to 22 tables even after adding the complete references feature**. Eight v6 tables disappear: `actors`, `command_receipt_events`, `change_bookmarks`, `execution_submissions`, `materialization_receipts`, `timeline_references`, `generations`, and `generation_variants`. Three current-feature tables are added: `project_references`, `media_references`, and `reference_links`. Three artifact tables are renamed around the chosen domain concept: `media_artifacts` becomes `media`, `artifact_locations` becomes `media_locations`, and `artifact_links` is narrowed and renamed `media_relations`.

The definitive modeling decision is **media-first**. `media` is the universal byte-bearing entity for imported files, generated images/video/audio, understanding outputs, reference sheets, and timeline assets. It is called media rather than files because paths and URLs are replaceable locations, never identity. A generation is not another kind of stored object. It is a product read model over a managed generation task, its immutable prompt/model/parameter specification, and its ordered `task_outputs` pointing at media. Sibling variants are the result outputs of the same task; their current primary selection lives on `task_outputs`. Cross-task derivation lives in `media_relations`. This preserves provenance, ordering, variant grouping, lineage, and selection without duplicating the media in `generations` and `generation_variants`.

References are semantic records shared across every timeline in one project. A character, place, object, clothing item, or other recurring subject has a `project_references` row. Its character sheets or other canonical images are ordinary `media` rows connected through `media_references` with role `canonical`; the same join associates any generated or imported media using roles `used_as_input`, `depicts`, or `inspired_by`. `reference_links` represents semantic relationships such as an outfit belonging to a character or a character being associated with a place. Because every generation variant is now media, references attach directly and unambiguously to the exact output, while a command can apply an association to all outputs of a generation task when that is the user's intent.

References, media imports, primary selections, shot changes, settings changes, and other non-task operations are event-backed projections on the project stream. References do not become tasks. Managed generation, rendering, or transcoding remains a task only when it has an immutable executable specification and a claim or independently fenced attempt. The task stream and task projection still commit atomically with outputs and command receipts, but v7 removes bookkeeping that duplicated those facts: attempts point straight at tasks, task completion plus ordered outputs proves materialization, receipts carry their ordered event IDs as bounded JSON, and project-scoped event sequence supplies `/changes` without a second bookmark table.

Setup also becomes simpler. `astrid serve` serves the packaged editor from its loopback origin and opens a short-lived capability URL. Same-origin loopback removes public-origin pairing, CORS, mixed-content, browser local-network permission, the public-site fragment handoff, and most DNS-rebinding complexity from the default path. The user still needs no account, email, Docker, Node, Supabase, database setup, environment variables, or provider key to open the editor, import media, manage characters/places, and edit a timeline.

### Changes vs v6

1. Commits to a media-first model and renames `media_artifacts` to `media`; “file” remains a location concern.
2. Deletes `generations` and `generation_variants`. Generation provenance is `tasks` plus `task_outputs`; variants are media outputs grouped by task; cross-task lineage is `media_relations`.
3. Adds project-scoped `project_references`, one unified `media_references` association for canonical images and usage/depiction semantics, and directed `reference_links`. The domain/API name remains “reference”; the physical prefix avoids SQLite's `REFERENCES` keyword.
4. Deletes the v5 holdover `execution_submissions`; immutable input manifests live on `tasks`, and `execution_attempts` references `task_id` directly.
5. Deletes `materialization_receipts`; exactly-once completion is proved by the terminal event, `tasks.winning_attempt_id`, immutable terminal status, and the unique ordered `task_outputs` committed in one transaction.
6. Deletes `command_receipt_events`; a command receipt stores its bounded ordered event-ID list and project sequence range as JSON/scalars.
7. Deletes `change_bookmarks`; `events.project_seq` is the durable per-project change cursor, and every meaningful change is an event.
8. Deletes `timeline_references`; the timeline document/asset registry names media IDs, while relational media/reference associations provide current reverse lookup. A separate extracted-usage projection is added only if safe-delete or usage search ships and measurements require it.
9. Deletes `actors`; events carry a small validated `actor_kind` because local GA has only local, system, executor, and importer attribution and no mutable actor registry.
10. Narrows six stream types to four: project, task, run, and timeline. Media, references, shots, and selections use the project stream because they do not need independent claim/CAS heads.
11. Drops event hash chaining and redundant aggregate `row_version`/`projected_event_seq` columns. Stream `head_seq` is the semantic CAS token; attempt `status_version` remains the independent executor fence.
12. Replaces integer shot-position uniqueness with lexicographically sortable keys to make reordering an ordinary atomic update.
13. Makes the locally served editor the default and removes the two pairing endpoints and pairing confirmation.
14. Trims local-GA release SLOs to the four outcomes that protect user experience and correctness; lower-level query budgets remain observed diagnostics.

## 1. Simplification pass

### 1.1 Disposition of the streamlining review

The review was directionally correct: v6 had completed the strategic teardown but had not applied “no projection without a current read, constraint, or lifecycle” consistently. V7 accepts its strongest cuts, rejects cuts that would erase a shipping query or integrity boundary, and modifies suggestions when the new references/media decision changes the answer.

| Review suggestion | Disposition | V7 judgment |
|---|---|---|
| Serve the editor bundle from loopback by default | **ACCEPT** | This removes the most fragile setup subsystem. The public `reigh.art` handoff can return later as an optional enhancement, not the local authority's bootstrap path. |
| Cut `execution_submissions` | **ACCEPT** | Its `UNIQUE(task_id)` made it a 1:1 wrapper and its realm abstraction anticipated a deferred cloud service. `tasks.input_manifest_json` freezes current inputs; attempts reference tasks directly. |
| Fold `materialization_receipts` | **ACCEPT** | The row restated facts already protected by one terminal event, one winning attempt, terminal immutability, ordered outputs, and a single SQLite transaction. Completion returns the ordinary command receipt. |
| Defer `timeline_references` | **ACCEPT** | No separate current feature needs an extracted JSON-pointer index. Timeline asset registry entries use media IDs and optional reference IDs; `media_references` serves character/place usages. Add an extraction table only when a measured safe-delete/usage feature requires it. |
| Defer `artifact_links` | **MODIFY** | Generic speculative lineage is rejected, but media-first needs a narrow current derivation read. Rename it `media_relations`, constrain its kinds, and exercise it in the media detail/source UI. |
| Cut `command_receipt_events` | **ACCEPT** | Local commands emit a bounded event list. Store ordered IDs in `command_receipts.event_ids_json`; event idempotency still derives as `<command-key>#<ordinal>`. Batch grouping stays relational through `run_step_tasks`. |
| Derive `change_bookmarks` | **ACCEPT** | Add a per-project monotonic `events.project_seq`. A primary subject plus bounded `changes_json` tells clients every projection invalidated by a multi-entity command. This also removes v6's contradiction that a change bookmark could have no event. |
| Collapse redundant version counters | **ACCEPT** | Client semantic CAS uses the aggregate stream head. Remove projection parity copies and aggregate row versions. Keep `execution_attempts.status_version`, because liveness/ownership updates intentionally do not advance history. |
| Reduce generation/shot streams | **MODIFY** | Go further: generations cease to be persisted aggregates. Shots, media, references, and selections use the project stream. Tasks, timelines, and durable runs keep independent streams because their lifecycle or conflict boundary is real. |
| Drop event hash chaining | **ACCEPT** | A tamper-evident chain has no current threat model in a single-user local database and complicates canonicalization. Keep hashes that perform identity/idempotency work: content, spec, request, and output-manifest hashes. SQLite checks, backups, and `doctor` cover corruption. |
| Change shot ordering away from a unique integer | **ACCEPT** | Stable lexicographic `sort_key` values allow insertion/reorder without temporary uniqueness violations. Occasional compaction is one project event and transaction. |
| Default WAL to `NORMAL` instead of `FULL` | **MODIFY** | Use WAL + `NORMAL` as the packaged default, measure crash/power-loss behavior, and expose a documented durability mode that selects `FULL`; do not pretend one setting fits every filesystem/risk preference. |
| Reduce numeric SLO gates | **ACCEPT** | Gate first-run, restart, mutation latency, and recovery correctness. Track other query sizes/latencies as budgets, not release vetoes before usage shows their importance. |
| Merge batch cancel/retry endpoints | **REJECT** | Two typed commands are clearer and do not add schema or authority. A generic command endpoint would save little while weakening generated contracts. |
| Fold `run_step_tasks` into JSON | **REJECT** | Batch progress/cancel/retry is a current feature that needs indexed child-task membership, order, and foreign-key integrity. JSON would move real relational work into application scans. |

V7 also makes one cut the review did not name directly: `actors` is unnecessary for a product with no user/accounts feature. A validated `actor_kind` on each event retains useful attribution without a mutable identity table. If hosted multi-user attribution becomes real, identity/grants are designed together rather than stretching this local enum into authorization.

### 1.2 Table count and exact disposition

The arithmetic is explicit:

```text
v6 baseline                                      27
cut actors                                       -1
cut command_receipt_events                       -1
cut change_bookmarks                             -1
cut execution_submissions                        -1
cut materialization_receipts                     -1
cut timeline_references                          -1
cut generations                                  -1
cut generation_variants                          -1
add project_references                           +1
add media_references                             +1
add reference_links                              +1
v7 total                                         22
```

Renaming `media_artifacts` → `media`, `artifact_locations` → `media_locations`, and `artifact_links` → `media_relations` does not change the count.

### 1.3 Every remaining table earns its place

| # | V7 table | Current shipped feature that justifies it |
|---:|---|---|
| 1 | `schema_migrations` | Transactional first-run creation, upgrades, checksum validation, and recovery. |
| 2 | `projects` | Project picker/create flow, current settings, and allocation of the durable project change cursor. |
| 3 | `event_streams` | Task lifecycle ordering, timeline save CAS, durable run ordering, and the project command stream. |
| 4 | `events` | Task history, reference/media/timeline decision history, idempotent event append, and `/changes`. |
| 5 | `command_receipts` | Deterministic mutation retry, result recovery after network loss, and group-command handles. |
| 6 | `runs` | Current understanding invocation history, outcomes, provenance display, and batch group status. |
| 7 | `run_steps` | Ordered stages/results in understanding and agent runs shown by the run detail UI. |
| 8 | `run_step_tasks` | Indexed fan-out child membership used by batch progress, cancel, and retry. |
| 9 | `evidence_items` | Queryable captions, observations, scores, decisions, and understanding output media. |
| 10 | `tasks` | Queue/task pane and the managed execution lifecycle for generation/render/transcode work. |
| 11 | `task_dependencies` | Current blocked/unblocked execution DAG and dependency ordering. |
| 12 | `execution_attempts` | Claim ownership, retries, leases, heartbeat runtime state, cancellation races, and stale-executor fencing. |
| 13 | `task_outputs` | Ordered multi-output results, generation grouping, per-output parameters, and current primary variant selection. |
| 14 | `media` | Universal media library for imports, generated outputs, reference images, understanding artifacts, and timeline assets. |
| 15 | `media_locations` | Managed file playback/serving, relocation, missing-file diagnosis, and future remote object locators without changing identity. |
| 16 | `media_relations` | Current media detail/source view for derived-from, variant-of, mask, and input lineage across tasks. |
| 17 | `timelines` | Authoritative editor document and asset registry with whole-document CAS. |
| 18 | `shots` | Current storyboard/shot list, names, ordering, and shot metadata. |
| 19 | `shot_items` | Ordered placement of exact media items in shots. |
| 20 | `project_references` | Project-wide character/place/object/clothing registry used by the editor. |
| 21 | `media_references` | Canonical character sheets plus used-as-input/depicts/inspired-by associations for exact media. |
| 22 | `reference_links` | Current semantic relationships such as outfit-belongs-to-character and character-associated-with-place. |

### 1.4 Where each cut function went

| V6 table cut | Function in v7 |
|---|---|
| `actors` | `events.actor_kind`; future real identities are a trigger-gated hosted feature. |
| `command_receipt_events` | Ordered `command_receipts.event_ids_json` plus `first_project_seq`/`last_project_seq`. |
| `change_bookmarks` | `events.project_seq`, allocated through `projects.event_head_seq`; `/changes` pages events directly. |
| `execution_submissions` | Immutable `tasks.spec_json`, `spec_hash`, and `input_manifest_json`; attempts point to `task_id`. |
| `materialization_receipts` | `task_completed` event payload, `tasks.winning_attempt_id`, terminal immutability, `task_outputs`, and the command receipt in one transaction. |
| `timeline_references` | Timeline `asset_registry_json` names media IDs; semantic subject associations live in `media_references`; no unshipped safe-delete index. |
| `generations` | A generation card is a read model grouped by a generation-capability `tasks` row and its outputs. Imported media simply has no producing task. |
| `generation_variants` | Each variant is a `media` row; task membership/order/primary selection is in `task_outputs`; cross-task derivation is in `media_relations`. |

No table remains because hosting, collaboration, billing, sync, public sharing, remote workers, or a future provenance browser might someday exist.

## 2. References: project semantics over universal media

### 2.1 Entity model and scope

A reference is a recurring semantic subject, not a file and not a task. The first-class kinds are `character`, `place`, `object`, `clothing`, and `other`. The row owns a stable project-scoped identity, human name, description, optional structured metadata, and archive state. It is shared by every timeline, shot, run, and media item in the project; copying a timeline does not duplicate references.

Canonical reference images are ordinary media. A character sheet, turn-around, face crop, location plate, or costume board is inserted once in `media`, stored at one or more `media_locations`, and associated through `media_references` with role `canonical`. Multiple canonical images are ordered; at most one is the primary thumbnail. The reference row is therefore the semantic layer, while media remains the byte/provenance layer.

The same `media_references` table handles the full association vocabulary:

- `canonical`: this media is part of the curated definition/reference pack;
- `used_as_input`: the reference or its canonical media informed the producing generation occurrence; `context_task_id` names that task so hash deduplication cannot blur two different production histories;
- `depicts`: the resulting/imported media visibly contains the subject;
- `inspired_by`: the media is semantically influenced by the reference without asserting exact depiction; it may carry `context_task_id` when the inspiration belongs to one production occurrence rather than the deduplicated bytes globally.

These roles can coexist for the same pair. For example, an image may be both a canonical character portrait and depict the character. Associations attach to exact media, so individual variants may differ: output 0 can depict Ada in the red coat while output 1 does not. A UI convenience command may apply the same association to every result output of one task, but it expands to explicit `media_references` rows; there is no hidden group-level inheritance.

`reference_links` represents directed semantic relationships between references. Initial kinds are `belongs_to`, `wears`, `located_in`, `associated_with`, and `related_to`. Direction is meaningful: a clothing reference `belongs_to` a character; a character `wears` clothing; an object may be `located_in` a place. `related_to` is the symmetric UI concept but is stored in canonical ID order to avoid duplicate inverse rows. New kinds require event-schema and UI support, not arbitrary user strings that no feature understands.

### 2.2 Reference DDL

The following three tables are included in the complete DDL in §3.4; they are repeated here because this is the feature contract.

```sql
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
  id            TEXT PRIMARY KEY,
  reference_id  TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  media_id      TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  role          TEXT NOT NULL CHECK (role IN
                ('canonical','used_as_input','depicts','inspired_by')),
  context_task_id TEXT REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal       INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  is_primary    INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  CHECK (role = 'canonical' OR is_primary = 0),
  CHECK (role <> 'used_as_input' OR context_task_id IS NOT NULL),
  CHECK (context_task_id IS NULL OR role IN ('used_as_input','inspired_by'))
);

CREATE UNIQUE INDEX media_reference_global_unique
  ON media_references(reference_id, media_id, role)
  WHERE context_task_id IS NULL;
CREATE UNIQUE INDEX media_reference_context_unique
  ON media_references(reference_id, media_id, role, context_task_id)
  WHERE context_task_id IS NOT NULL;
CREATE UNIQUE INDEX reference_one_primary_canonical
  ON media_references(reference_id)
  WHERE role = 'canonical' AND is_primary = 1;
CREATE UNIQUE INDEX reference_canonical_ordinal
  ON media_references(reference_id, ordinal)
  WHERE role = 'canonical';

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
```

The repository rejects cross-project media/reference joins and cross-project reference links. It also proves every non-null `context_task_id` exists, belongs to the same project, and produced the named media through `task_outputs`. For symmetric `related_to`, it stores `min(id)` as `from_reference_id` and `max(id)` as `to_reference_id`. An active reference must have at least one canonical image; create and last-canonical replacement enforce that aggregate rule in one transaction and `doctor` verifies it. Archiving a reference hides it from normal pickers but retains associations and history; `DELETE` is therefore an archive command in local GA. Physical deletion is limited to an explicit maintenance operation for a never-used reference and is not a normal editor route.

### 2.3 Events and transactional behavior

References are event-backed projections on the owning project stream. They never acquire task rows or attempts. The v1 event registry adds:

| Event kind | Projection effect |
|---|---|
| `reference_created` | Insert `project_references`; payload contains kind, name, description, and bounded metadata. |
| `reference_updated` | Update mutable semantic fields and `updated_at`; changing kind is explicit in the payload. |
| `reference_archived` / `reference_restored` | Set or clear `archived_at`. |
| `reference_media_associated` | Insert/upsert one `media_references` edge, including association ID, role, optional context task, ordinal, and primary flag. |
| `reference_media_disassociated` | Delete the exact association ID/context; historical fact remains in events. |
| `reference_linked` | Insert/upsert a typed `reference_links` edge. |
| `reference_unlinked` | Delete the named current edge. |

Creating a reference from an uploaded character sheet can be one command and transaction: commit the upload to `media`, append `media_imported` and `reference_created`, append `reference_media_associated`, insert both projections, advance the project stream/project sequence, and write one command receipt containing all ordered event IDs. A retry returns that receipt. A failure leaves neither a half-reference nor a dangling association.

Updating the primary canonical image is also one command: append a disambiguated association/selection event, clear the former `is_primary`, set the new one, and commit the receipt atomically. Disassociation never deletes media bytes. Archiving a reference never deletes its canonical media or associations; the user can still inspect history and restore it.

### 2.4 API surface

Reference APIs are typed commands, not table CRUD passthrough and not generic event append:

| Contract | Purpose |
|---|---|
| `GET /api/astrid/v2/projects/{p}/references` | Page/filter the character/place/object/clothing registry; include primary thumbnail and usage counts. |
| `POST /api/astrid/v2/projects/{p}/references` | Create an active reference with one or more already-uploaded canonical image media IDs in the same command. |
| `GET /api/astrid/v2/projects/{p}/references/{r}` | Read semantic fields, ordered canonical media, other media associations, and reference links. |
| `PATCH /api/astrid/v2/projects/{p}/references/{r}` | Update name, description, kind, metadata, or restore an archived reference. |
| `DELETE /api/astrid/v2/projects/{p}/references/{r}` | Archive with a durable receipt; never silently delete media. |
| `GET /api/astrid/v2/projects/{p}/references/{r}/associations` | Page media usages and reference links for detail/search UI. |
| `POST /api/astrid/v2/projects/{p}/references/{r}/associations` | Typed `associate_media`, `disassociate_media`, `link_reference`, `unlink_reference`, or `make_primary_canonical` command. |

All mutation requests require an idempotency key. Association commands name an exact media ID and role, or an exact other reference and link kind. `used_as_input` requires its producing `context_task_id`; occurrence-scoped `inspired_by` supplies it too. A task-output convenience form may provide `task_id`, role, and an explicit output selector (`all`, ordinals, or media IDs); the service resolves it to exact rows before committing and returns the association IDs and context in the receipt.

### 2.5 Editor, timeline, and asset registry implications

The editor gains a project-level **References** registry with kind tabs/filters, search, thumbnails, archive visibility, and detail views for canonical images, usages, and links. Media pickers and generation forms can select one or more references with an intended role. After generation, the result grid can confirm, remove, or vary per-output `depicts` associations instead of assuming every variant contains every prompt subject.

Timeline asset registry entries identify `media_id`, not generation or file path. A clip that depicts a character gets that fact through `media_references(media_id, reference_id, 'depicts')`; the timeline can display character/place badges by joining through its asset registry media IDs. A clip placement may cache selected `reference_ids` in the timeline document for rendering convenience, but the cache is validated/refreshed from `media_references` and is not a second semantic authority. Copying or reordering a timeline changes no reference associations. The same reference is naturally shared across all timelines in the project.

This is also why media-first is the forcing case. Under v6, a reference sheet was a `media_artifact`, a generated image was a `generation_variant` wrapping a `media_artifact`, and a timeline clip could name either layer. V7 removes that ambiguity: every exact visual/audio item is media; reference, task output, evidence, shot item, and timeline placement are roles or relationships around it.

## 3. Definitive media-first decision

### 3.1 What v6 generations added

V6's `generations` plus `generation_variants` contributed four useful concepts beyond bare artifacts:

1. a gallery-level group for one creative request;
2. a link to producing task/run and therefore prompt/model/parameter provenance;
3. ordered variants and one current primary selection;
4. a stable object for shot/timeline placement and generation-specific status/title.

Those are real product needs, but two dedicated tables are not the minimal way to meet them. The group already exists as the immutable generation task. Provenance already exists in `tasks.spec_json`, `spec_hash`, `input_manifest_json`, attempts, and ordered outputs. Each variant already has byte identity in `media`. Selection can live on task-output membership. Shot and timeline placement should point at the exact media the user sees, not at a wrapper that must then resolve a primary variant. A failed task belongs in the task pane/history and has no phantom generation row. A user-facing title can live in bounded task specification/result metadata or be a media title field only when the media library actually supports naming.

Keeping both models would create multiple answers to basic questions: Is a character sheet an artifact or a generation? Does a timeline clip follow a generation's changing primary variant or pin a specific variant? Does imported media need a fake generation? Which ID should reference associations use? V7 answers each once.

### 3.2 Why `media`, not `files`

The universal entity is named `media`, not `files`. A file is a physical location/representation: a managed path, an in-place path, a future object-store key, or a cache. The stable entity is verified content with media semantics. `media.content_hash` and project scope define deduplication identity; `media_locations` records replaceable locators. URLs and absolute paths never appear in domain foreign keys, event subjects, timeline registries, or reference associations.

This model gains:

- one identity for imports, task results, canonical references, evidence outputs, shots, and timeline assets;
- direct reference association to exact variants;
- no wrapper rows or polymorphic timeline IDs;
- deduplication before semantics, so one byte object can have several legitimate roles;
- simpler missing-file relocation and future local-to-host copy;
- a gallery that can include generated and imported media without unioning unrelated tables.

The principal loss is a dedicated generation ID. V7 deliberately accepts that loss: the producing task ID is the generation-group ID for managed generation, and individual media IDs identify exact outputs. API/UI code may expose a computed `generation_card` structure, but it is a view/response, not persisted authority. If a future creative-session feature genuinely groups outputs from several tasks, it must earn a named collection aggregate from that feature's queries; it must not resurrect `generations` as a universal media wrapper.

### 3.3 Provenance, variants, lineage, and placement

The complete story is:

```text
generation intent and parameters   -> tasks(spec_json, spec_hash, input_manifest_json)
managed execution                  -> execution_attempts
exact produced bytes               -> media
ordered sibling output membership  -> task_outputs(task_id, ordinal, role)
current sibling primary            -> task_outputs.is_primary
cross-task/source lineage          -> media_relations
character/place semantics          -> media_references
understanding semantics            -> evidence_items.media_id
storyboard placement               -> shot_items.media_id
timeline placement                 -> timelines.asset_registry_json -> media_id
physical path/URL                  -> media_locations
```

`media_relations` is intentionally small. `derived_from` links an output to source media; `variant_of` links an output to one immediate prior creative result across tasks; `uses_as_input` records a material input when the relation is worth querying; `mask_for` relates a mask to its target; `audio_for` relates audio to a video. Cross-task `variant_of` is lineage only: it does not merge two producing tasks into one generation card, create a transitive family, or share a primary selection. Each media row has at most one immediate `variant_of` parent, cycles are rejected, and each task remains its own sibling-output group and primary scope. Relation metadata may capture frame/time range or transformation role. Prompt/model/seed parameters do not belong on these edges: they stay in the immutable task spec and per-output `task_outputs.params_json` when providers return output-specific values.

Primary selection is scoped to the result outputs of one task. The repository enforces exactly one `is_primary=1` when a succeeded generation-capability task has result outputs; non-generation tasks may have none. The initial `selection_project_seq` is the `task_completed` event's project sequence, because that event creates the output set and initial primary. Changing it later appends `task_output_primary_selected` to the project stream and advances the token because it is a user decision, not a task lifecycle transition; the terminal task stream remains immutable. Task lifecycle responses expose `task_stream_seq`, while gallery/output responses separately expose this `selection_project_seq` and require it as the selection command's expected version. Thus a task's execution CAS never pretends to version mutable gallery choice. Shot items and timeline assets always pin a media ID, so changing a gallery primary never silently changes an edit.

### 3.4 Normative SQLite DDL (22 tables)

This is fresh creation DDL, not an `ALTER` appendix. Generated migration files may split it, but the result must be equivalent.

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
  id              TEXT PRIMARY KEY,
  slug            TEXT NOT NULL UNIQUE,
  name            TEXT NOT NULL,
  settings_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(settings_json)),
  event_head_seq  INTEGER NOT NULL DEFAULT 0 CHECK (event_head_seq >= 0),
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE event_streams (
  id            TEXT PRIMARY KEY,
  project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  stream_type   TEXT NOT NULL CHECK (stream_type IN
                ('project','task','run','timeline')),
  aggregate_id  TEXT NOT NULL,
  head_seq      INTEGER NOT NULL DEFAULT 0 CHECK (head_seq >= 0),
  created_at    TEXT NOT NULL,
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
                  ('local','system','executor','importer')),
  payload_json    TEXT NOT NULL CHECK (json_valid(payload_json)),
  created_at      TEXT NOT NULL,
  UNIQUE (project_id, project_seq),
  UNIQUE (stream_id, seq),
  UNIQUE (stream_id, idempotency_key)
);

CREATE TABLE command_receipts (
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  idempotency_key     TEXT NOT NULL,
  request_hash        TEXT NOT NULL,
  command_kind        TEXT NOT NULL,
  txn_id              TEXT NOT NULL UNIQUE,
  primary_stream_id   TEXT REFERENCES event_streams(id) ON DELETE RESTRICT,
  resulting_stream_seq INTEGER,
  first_project_seq   INTEGER NOT NULL CHECK (first_project_seq > 0),
  last_project_seq    INTEGER NOT NULL CHECK (last_project_seq >= first_project_seq),
  event_ids_json      TEXT NOT NULL CHECK
                      (json_valid(event_ids_json) AND json_type(event_ids_json) = 'array'),
  result_json         TEXT NOT NULL CHECK (json_valid(result_json)),
  created_at          TEXT NOT NULL,
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
  finished_at     TEXT
);

CREATE TABLE run_steps (
  id              TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  ordinal         INTEGER NOT NULL CHECK (ordinal >= 0),
  kind            TEXT NOT NULL,
  status          TEXT NOT NULL CHECK
                  (status IN ('pending','running','succeeded','failed','skipped')),
  input_json      TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(input_json)),
  result_json     TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(result_json)),
  started_at      TEXT,
  finished_at     TEXT,
  UNIQUE (run_id, ordinal)
);

CREATE TABLE tasks (
  id                  TEXT PRIMARY KEY,
  project_id          TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  event_stream_id     TEXT NOT NULL UNIQUE REFERENCES event_streams(id) ON DELETE RESTRICT,
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
  finished_at         TEXT
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
  task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal       INTEGER NOT NULL CHECK (ordinal >= 0),
  role          TEXT NOT NULL,
  media_id      TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  is_primary    INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  params_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(params_json)),
  created_at    TEXT NOT NULL,
  PRIMARY KEY (task_id, ordinal),
  CHECK (role = 'result' OR is_primary = 0)
);

CREATE TABLE run_step_tasks (
  run_step_id TEXT NOT NULL REFERENCES run_steps(id) ON DELETE CASCADE,
  task_id     TEXT NOT NULL REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal     INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  PRIMARY KEY (run_step_id, task_id),
  UNIQUE (run_step_id, ordinal)
);

CREATE TABLE evidence_items (
  id          TEXT PRIMARY KEY,
  run_id      TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  run_step_id TEXT REFERENCES run_steps(id) ON DELETE SET NULL,
  kind        TEXT NOT NULL,
  summary     TEXT NOT NULL,
  data_json   TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(data_json)),
  media_id    TEXT REFERENCES media(id) ON DELETE SET NULL,
  created_at  TEXT NOT NULL
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
  id            TEXT PRIMARY KEY,
  shot_id       TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  media_id      TEXT NOT NULL REFERENCES media(id) ON DELETE RESTRICT,
  sort_key      TEXT NOT NULL,
  source_frame  INTEGER,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
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
  id            TEXT PRIMARY KEY,
  reference_id  TEXT NOT NULL REFERENCES project_references(id) ON DELETE CASCADE,
  media_id      TEXT NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  role          TEXT NOT NULL CHECK (role IN
                ('canonical','used_as_input','depicts','inspired_by')),
  context_task_id TEXT REFERENCES tasks(id) ON DELETE RESTRICT,
  ordinal       INTEGER NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  is_primary    INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at    TEXT NOT NULL,
  CHECK (role = 'canonical' OR is_primary = 0),
  CHECK (role <> 'used_as_input' OR context_task_id IS NOT NULL),
  CHECK (context_task_id IS NULL OR role IN ('used_as_input','inspired_by'))
);

CREATE UNIQUE INDEX media_reference_global_unique
  ON media_references(reference_id, media_id, role)
  WHERE context_task_id IS NULL;
CREATE UNIQUE INDEX media_reference_context_unique
  ON media_references(reference_id, media_id, role, context_task_id)
  WHERE context_task_id IS NOT NULL;

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

CREATE UNIQUE INDEX task_one_primary_result
  ON task_outputs(task_id)
  WHERE role = 'result' AND is_primary = 1;
CREATE UNIQUE INDEX reference_one_primary_canonical
  ON media_references(reference_id)
  WHERE role = 'canonical' AND is_primary = 1;
CREATE UNIQUE INDEX reference_canonical_ordinal
  ON media_references(reference_id, ordinal)
  WHERE role = 'canonical';
CREATE INDEX events_project_changes ON events(project_id, project_seq);
CREATE INDEX events_stream_kind_seq ON events(stream_id, kind, seq);
CREATE INDEX events_subject ON events(project_id, subject_type, subject_id, project_seq);
CREATE INDEX tasks_claim_order ON tasks(status, available_at, priority DESC, id);
CREATE INDEX tasks_project_status ON tasks(project_id, status, created_at, id);
CREATE INDEX attempts_lease_expiry ON execution_attempts(status, lease_expires_at);
CREATE INDEX task_outputs_media ON task_outputs(media_id, task_id);
CREATE INDEX media_project_page ON media(project_id, created_at, id);
CREATE INDEX media_relations_to ON media_relations(to_media_id, kind, from_media_id);
CREATE UNIQUE INDEX media_one_variant_parent
  ON media_relations(from_media_id)
  WHERE kind = 'variant_of';
CREATE INDEX run_step_tasks_task ON run_step_tasks(task_id, run_step_id);
CREATE INDEX shot_items_media ON shot_items(media_id, shot_id);
CREATE INDEX references_project_kind ON project_references(project_id, kind, name, id);
CREATE INDEX media_references_media ON media_references(media_id, role, reference_id);
CREATE INDEX media_references_task
  ON media_references(context_task_id, role, reference_id)
  WHERE context_task_id IS NOT NULL;
CREATE INDEX reference_links_to ON reference_links(to_reference_id, kind, from_reference_id);
```

The repository and `astrid doctor` enforce cross-row constraints SQLite cannot express cleanly: stream aggregate/project/type matches for tasks, runs, timelines, and projects; every stream begins with its registered genesis event; task `winning_attempt_id` belongs to that task; all task outputs and dependencies share the task project; both sides of media/reference/relation/shot joins share a project; media derivation/variant edges are acyclic; symmetric links use canonical order; project sequence is gap-free under supported writes; and primary changes satisfy their partial unique indexes without transiently exposing two primaries.

All IDs are lowercase ULIDs generated by the service. Timestamps are canonical UTC text. JSON used in `request_hash`, `spec_hash`, or output-manifest hashing is canonicalized by one versioned library. Media content uses SHA-256 over verified bytes. Hashes serve identity and idempotency only; there is no dormant audit chain.

## 4. Task/event principle, unchanged at the foundation

### 4.1 Admission rule

A `tasks` row is legal only when all three statements are true:

1. The work has a bounded immutable execution specification an executor can perform.
2. It is exclusively claimable or has a separately identified attempt whose ownership and terminal result are fenced from duplicate or stale executors.
3. The service can select one winning terminal transition under retry, cancellation, duplicate delivery, and executor loss.

Cost, latency, an HTTP call, a progress spinner, a provider SDK retry, media relevance, or the word “generation” does not qualify by itself. Managed GPU generation, queued rendering, and attempt-tracked transcoding are tasks. Inline image understanding is a run plus evidence. Media import, reference creation, changing a primary result, placing media in a shot, timeline save, and settings change are events with current projections.

Every task has exactly one task stream with the same project and aggregate ID. Sequence 1 is `task_created`. The row is the current execution projection; the stream is the ordered lifecycle history and CAS boundary. Supported code never updates lifecycle state without advancing both. Removing `projected_event_seq` does not weaken this rule: a task query returns its joined stream `head_seq`, and repository conformance proves the task row and head were updated in the same transaction. Mutable output selection is deliberately outside that lifecycle aggregate and carries its own project-sequence token as defined in §3.3.

The v6 semantic lifecycle vocabulary remains: `task_created`, queued/blocked/unblocked decisions, `task_claimed`, `attempt_started`, optional product-visible `task_progressed`, `cancel_requested`, `cancel_acknowledged`, `attempt_expired`, `attempt_failed`, `task_requeued`, `materialization_requested`, and the immutable `task_completed`/`task_failed`/`task_cancelled` decisions. Heartbeats remain narrow runtime updates to `execution_attempts`; they update `status_version`, counter, time, lease, and bounded progress but append no event. Expiry is an event because it is a semantic arbitration decision.

### 4.2 Atomic commands, outputs, and receipts

An eventful command runs in one `BEGIN IMMEDIATE` transaction:

```text
check idempotency key + canonical request hash
validate expected stream head and, where applicable, attempt status_version
allocate consecutive project_seq values from projects.event_head_seq
append registered event(s), each with deterministic idempotency key and bounded
  changes_json naming every projection invalidated by that event
advance each affected event_streams.head_seq
update the task/run/timeline/project/media/reference/shot projections
on completion: insert verified media, locations, task_outputs, relations,
               and declared reference associations
write one command receipt with ordered event IDs and project sequence range
COMMIT
```

The identical retry returns the stored receipt. Reusing a key with different canonical request bytes returns `idempotency_mismatch`. Event keys derive as `<command-key>#<zero-based-ordinal>`. Each event has one primary `subject_type`/`subject_id`, but `changes_json` contains the complete bounded list of `{entity_type, entity_id, operation}` invalidations caused by that event. A task completion therefore invalidates the task, every created/reused media occurrence, outputs, relations, reference associations, and affected run/shot views without inventing bookmark rows. The bounded JSON event list is appropriate here because one local command has a configured maximum number of events; larger fan-out is chunked into receipt-linked child commands rather than constructing an unbounded SQLite transaction.

Exactly-once output materialization no longer needs a second receipt type. The completion CAS requires the current attempt fence and nonterminal task; the transaction appends `task_completed`, sets `winning_attempt_id`, inserts the complete ordered output set, and returns the command receipt. Unique task/ordinal output keys and terminal immutability make a second materialization fail or replay. Crash injection at every statement boundary must expose only nothing, or the mutually complete terminal event, task state, media, outputs, associations, stream heads, project sequences, and receipt.

The five v6 cancellation races stay normative: queued cancellation versus claim; running cancellation versus completion; running cancellation versus expiry/requeue; stale failure versus a newer attempt; and terminal task versus retry or later cancellation. Tests assert event order, attempt fences, output absence/presence, and impossibility of terminal resurrection.

### 4.3 Runs, understanding, and batches

Inline understanding creates or advances a run stream, projects `runs` and ordered `run_steps`, and stores observations in `evidence_items`. If it emits an image, audio, text document, or other byte artifact, that output is ordinary media linked from evidence. The response contains a command receipt, run ID, evidence IDs, and media IDs; it never invents a task ID. If the feature later becomes queued and independently attempt-fenced, that is a different advertised asynchronous capability.

One command may fan out to N real tasks. The run is the group handle; `run_step_tasks` indexes and orders its child tasks. Group progress is derived from children, and typed batch cancel/retry expands to eligible child commands. There is no convenience parent task unless an executor genuinely claims and attempts the parent work. This is why the two run-step tables survive the simplification pass: the editor ships both ordered run detail and relational fan-out control.

## 5. Greenfield posture and setup ease

### 5.1 Tear down, do not migrate

V7 remains a destructive greenfield rebuild. There are no production users, balances, subscriptions, shared workspaces, or customer projects to preserve. New schema creation starts from an empty SQLite application database. The editor calls only `/api/astrid/v2`; Astrid repositories are the only semantic writers. Old Supabase tables, RPCs, edge functions, RLS policies, direct `.from()` calls, Realtime subscriptions, account/billing/sharing surfaces, FSA state writes, JSONL authorities, and bridge sidecars are deleted as replacement routes land. There is no dual-write, shadow-read, parity, backfill, snapshot/tail, legacy alias, billing reconciliation, or rollback-observation phase.

An optional disposable `astrid bootstrap import <project-path>` may import known timeline documents, reachable media, and recognizable character/place boards into ordinary v7 events and projections. It is strict about malformed files, lossy about old history, transactional, and idempotent by an input-manifest request hash. It records `project_bootstrapped` with a human-readable source summary. It does not import old task status, claims, heartbeats, credits, users, service keys, or source-table identity, and it can be removed after the useful local corpus has been bootstrapped.

### 5.2 Zero to a working editor

The supported path is now:

```text
1. Install the signed Astrid desktop/CLI package.
2. Run: astrid serve
3. The locally served editor opens with the seeded blank project.
4. Import media, create references, or edit immediately.
```

On first run, `astrid serve` creates the OS-standard application-data and managed-media directories with restrictive permissions, creates the database, applies checksummed migrations, seeds a blank project and project stream, acquires the single-process lock, binds `127.0.0.1` on an OS-assigned port, serves the packaged editor bundle, and opens it. A high-entropy one-use launch capability is placed in the URL fragment, consumed by same-origin bundled JavaScript, exchanged for a short local session, and cleared from history. There is no human pairing code, public-origin fragment handoff, port scan, CORS allowlist, mixed-content request, or browser Local Network Access prompt in the default flow. Exact loopback Host validation, token expiry/rotation, no-log handling, and bundle/service version handshake still apply.

The local baseline requires no login, email, internet connection after installation, credit, Stripe, Docker, Node, Supabase CLI, database command, port choice, configuration file, environment variable, or provider key. OpenAI, Fal, RunPod, or another capability provider prompts for its credential only when invoked; credentials live in the OS keychain and never in project data, exports, logs, or API responses.

Operational defaults carry forward: managed copy plus verified SHA-256 for imports; “reference in place” only as an advanced option with visible missing-file risk; automatic port selection; one writer/process lock; verified online backup before schema upgrades; fail-closed read-only behavior for a too-new schema or failed quick check; uninstall preserves data; and unsaved browser drafts are keyed by project/timeline/base stream head and cleared only by a covering receipt.

### 5.3 Local GA gates

Only four outcome-level metrics block local GA:

1. From an installed package on a clean supported macOS account, `astrid serve` opens an editable seeded project in one command and under two minutes p95.
2. Restart returns to the same projects and editor in under ten seconds p95, with no manual port/configuration recovery.
3. Ordinary eventful mutations remain below 250 ms p95 on the representative project while executor heartbeats and two editor tabs are active, with bounded `SQLITE_BUSY` recovery and no starvation.
4. Kill injection at backup/migration/command/materialization boundaries yields either the old intact database or the complete new state; restored projects reopen with matching media hashes and references.

Gallery pages, timeline document size, `/meta`, `/changes`, Range/ETag seeking, event growth, and backup duration retain measured budgets and dashboards, but become release blockers only when a declared user journey misses its outcome. Browser coverage still includes supported Safari, Chrome, Firefox, and Edge for the same-origin loopback editor, media playback/seeking, offline-after-load, hostile Host requests, stale/replayed launch capabilities, two tabs, service restart, and bundle/API version mismatch.

### 5.4 Public API shape

The v6 generation routes are replaced by media routes; reference contracts are those in §2.4. The local-GA surface has typed families for meta/session bootstrap, projects, timelines, tasks/commands, runs/evidence, media/uploads/provenance, shots, references, changes, settings, and operations. Important changed contracts are:

- `GET /projects/{p}/media` with media kind, producing task, and reference filters;
- `GET /projects/{p}/media/{m}` returning locations safe for the client, provenance, relations, task occurrences, and reference badges;
- resumable upload start/put/commit under `/projects/{p}/uploads`;
- `POST /projects/{p}/tasks/{t}/outputs/{ordinal}/make-primary` for unambiguous sibling-result selection, with expected `selection_project_seq`;
- typed add/remove `media_relations` commands from media detail;
- shot items that accept `media_id`, never generation/variant IDs;
- `GET /projects/{p}/changes?after=<project_seq>` reading `events` and their complete `changes_json` invalidation lists directly;
- task creation accepting frozen `reference_inputs` with explicit modes.

A generic public `POST /events`, arbitrary table CRUD, SQL/PostgREST filters, locators as identity, and polymorphic generation-or-artifact IDs are forbidden. Account, billing, sharing, sync, PAT, public upload, hosted worker administration, and rate-limit administration routes remain absent.

## 6. Delivery path

### Stage 1 — build the clean local system

1. Land the 22-table creation migration, migration runner, backup/restore, `doctor`, repository write queue, event registry, and generated validators.
2. Implement project-sequence event append, stream CAS, command receipts, task admission/transitions, direct task attempts, runtime heartbeat, ordered media output materialization, and the five cancellation races.
3. Implement media import/serving/locations/relations, runs/steps/evidence, timeline CAS, media-based shots, and reference CRUD/associations/links.
4. Serve the version-matched editor bundle from loopback with one-use launch capability, limits, timeouts, graceful drain, Range/ETag, and exact Host checks.
5. Build the optional file-project importer and static rules forbidding shipped Supabase domain imports and direct project-state filesystem writers.

**Stage 1 gate:** every table has an exercised owner/query; invalid task/stream/project/media/reference combinations fail conformance; inline understanding creates no task; generation creates one task and ordered media outputs without a generation row; exact variant reference associations round-trip; active references keep canonical image media; crash tests prove atomic completion and associations; importer retry/rollback and single-writer contention pass.

### Stage 2 — local editor GA

Route the editor exclusively through v7 and remove the old authorities and UI. Ship the media gallery, task pane, run/evidence detail, timeline editor, shots, project reference registry, reference chips/filters/badges, setup/restart/upgrade flows, browser drafts, and missing-media recovery. Dogfood fresh projects and imported Astrid folders. Fix pre-GA schema mistakes with forward migrations, not compatibility abstractions.

**Local GA gate:** §5.3 passes; every mutation returns a durable receipt and appears in `/changes`; task/event/media/reference/timeline invariants pass; production bundles contain no Supabase domain writer or semantic FSA writer; work without accounts/cloud/providers is complete; and backup/restore preserves bytes, hashes, associations, and editability.

### Stage 3 — host the same thing later

Only after a product decision to host Astrid, run the same logical migrations/repository suite against pinned Turso/libSQL. Add the smallest fired requirements: public-service identity, project grants when multiple humans exist, remote media locations and scoped executor credentials, abuse controls for internet endpoints, and a separate money ledger before charging. Local-to-host movement begins as an explicit copy/export designed then. Postgres is not an intermediate destination; the abandoned Supabase estate is not migrated; sync, offline merge, public sharing, and billing are independent milestones.

## 7. Invariants

- **Task exclusivity:** only immutable executable work with a claim or fenced attempt has a task row.
- **Event universality:** every meaningful non-task mutation appends one ordered idempotent event to the narrowest current stream.
- **Task association:** every task has one matched task stream beginning with `task_created`; detached rows or event-only lifecycle transitions are invalid.
- **Atomic command:** events, stream heads, project sequence, projections, outputs/associations, and command receipt commit or roll back together.
- **Version separation:** stream head fences semantic history; attempt `status_version` fences ownership/liveness; heartbeat is not history.
- **Terminal immutability:** no stale executor, retry, cancel, or failure can overwrite or resurrect a terminal task.
- **Run/task independence and batch honesty:** runs may have zero tasks; group UX derives from real linked child tasks, never a fake parent.
- **Single writer:** browser, CLI, importer, and executor all use Astrid repositories; filesystems store bytes, not semantic authority.
- **Timeline authority:** the document and asset registry advance with the timeline stream in one whole-document CAS; assets name media IDs.
- **Universal media identity:** one project-scoped media row plus verified content hash identifies bytes across imports, outputs, references, evidence, shots, and timelines; locations are replaceable.
- **Generation provenance:** immutable task spec/inputs plus ordered task outputs and events answer how media was generated; no parallel generation identity exists.
- **Exact placement:** shots and timelines pin exact media. Primary selection changes never silently change an edit.
- **Reference separation:** reference rows carry semantics; canonical images remain media; archiving a reference never deletes bytes.
- **Reference integrity:** active references have canonical image media; every media association and reference link is same-project and event-backed; contextual input associations name a task that produced the media.
- **No invisible inheritance:** bulk “all variants” commands expand to explicit per-media associations; later outputs inherit only from their own frozen task input.
- **No dormant platform:** no account, money, sharing, tenancy, sync, legacy-migration, remote-worker, or generic catalog schema ships unused.

## 8. Risks, experiments, and fallbacks

| Risk | Proof before release | Fallback or correction |
|---|---|---|
| Folding generations loses a real query | Fixtures for gallery grouping, prompt/model display, primary selection, failed tasks, lineage, reference filtering, and timeline placement | Add a computed repository read model/index first; add a table only after a measured query/constraint proves it necessary. |
| Media relation vocabulary becomes a junk drawer | Direction/cardinality/cycle fixtures for every registered kind | Reject unknown kinds; from-media is always the derived/using subject and to-media the source/target. Add a typed kind only with UI/API behavior. |
| Hash dedupe blurs production occurrences | Same bytes produced by two tasks with different reference inputs or inspiration | `task_outputs` retains both occurrences; nullable, foreign-keyed `media_references.context_task_id` retains occurrence-specific `used_as_input`/`inspired_by`. Do not duplicate media bytes/identity. |
| Reference roles become ambiguous | Examples for canonical, used-as-input, depicts, and inspired-by across divergent variants | Closed enum, explicit UI labels, per-media rows, source event metadata, and no automatic depicts inference. |
| Reference archive/delete breaks edits | Timeline/shot/media fixtures with archived and missing canonical media | Archive by default, preserve IDs/edges/history, make purge offline and proof-driven, and keep bytes independent. |
| SQLite contention | Two tabs, heartbeat, importer, reference bulk association, and completion load | One in-process write queue, short transactions, batch bounds, backpressure; never add a second writer. |
| Local launch capability leaks or bundle mismatches | Browser history/log/referrer tests and old/new bundle matrix | Fragment exchange and immediate clearing, expiry/rotation, exact Host, no token logging, fail closed on API version mismatch. |
| Missing/corrupt media | Delete/mutate managed and in-place bytes, then run editor and `doctor` | Surface missing/corrupt state, relocate or re-import with hash verification; never reassociate by filename. |
| Schema upgrade interruption | Kill at every backup/migration boundary | Restore verified backup; older binary refuses writes to newer schema. |
| Event/project sequence drift | Raw-SQL adversarial fixtures and replay | `doctor` detects gaps/mismatches; supported writer refuses further mutations pending explicit repair/restore. |
| Hidden old authority survives teardown | Production dependency scan and filesystem tracing | Delete the path or implement its repository route before GA. |
| Hosted dialect differs later | Run the complete local conformance/crash suite on pinned libSQL before Stage 3 | Do not host until semantics conform; do not insert Postgres as a workaround. |

## 9. Vendor verification and decisions

### 9.1 Load-bearing verification

Ship-time proofs cover pinned SQLite WAL/`BEGIN IMMEDIATE`/foreign keys/JSON/partial indexes/backup/crash/locking; Python repository behavior under threads/process attempts and abnormal termination; macOS application-data, package signing, keychain, filesystem durability, and browser opening; and supported Safari/Chrome/Firefox/Edge same-origin loopback behavior including Range/ETag playback. Optional OpenAI, Fal, and RunPod capability checks are isolated behind user-provided credentials and do not block editing. Turso/libSQL conformance begins only with Stage 3.

Supabase, Postgres, Stripe, RLS, historical worker RPCs/pricing, native replicas, and public-origin-to-loopback pairing are removed from the load-bearing list. They are out of scope, not unanswered.

### 9.2 Resolved decisions

| Question | V7 answer |
|---|---|
| Media, files, or generations at the center? | `media`; files are locations and generation is task-output provenance. |
| Reference scope? | Project-scoped and shared by all timelines. |
| Canonical reference images? | One or more image media associations; one may be primary. |
| Generation/reference association? | Exact media association, with task context for `used_as_input`; bulk commands expand explicitly. |
| Reference concurrency? | Project stream and single-writer ordering; no per-reference stream/table version until concurrent editing proves a need. |
| Timeline usage index? | No table at GA; use media joins and bounded document scans until a real reverse-usage feature earns a projection. |
| Users/login/billing/tenancy/sharing/sync? | None in local GA; each is added only after its product trigger. |
| Heartbeat history? | Runtime attempt state only; expiry/retry/cancel/failure/completion are events. |
| Editor delivery? | Version-matched locally served bundle by default; public handoff is a later optional feature. |
| Database family? | SQLite locally; Turso/libSQL only if hosted; no Postgres phase. |

### 9.3 Remaining decisions with deadlines

1. Freeze the supported OS/browser matrix before Stage 2 setup testing.
2. Freeze the managed media root, copy-versus-reference default, backup/project packaging, and importer-recognized reference manifests before the importer lands.
3. Freeze closed `media_relations`, reference kind, media-reference role, and reference-link vocabularies against real editor fixtures before schema freeze; additions remain versioned later.
4. Decide whether remote GPU execution is in local GA before Stage 1 executor freeze. The default is no; if yes, design the smallest separate adapter without automatically adding accounts, billing, tenancy, or a submission table.
5. Freeze batch partial retry semantics—every failed child versus an explicit selected subset—before the task-pane UX is complete.
6. Freeze editor bundle update/signing and service/API compatibility policy before packaging GA.

## 10. Final recommendation and completion definition

Build v7 directly. Do not preserve the old Supabase estate, retain v5 execution wrappers, or keep parallel media/generation identities. The product model should be easy to say in one breath: **tasks execute; everything else is an event; every exact asset is media; references add project semantics to media**.

The plan is complete when these artifacts pass together: the 22-table creation migration; event/lifecycle/reference schema registry; repository and generated API contracts; task-stream and five-race fixtures; understanding/run/evidence fixtures; media import/dedupe/location/lineage fixtures; multi-output generation fixtures with no generation rows; canonical and per-variant reference fixtures; timeline/shot media fixtures; importer fixture; same-origin local launch/security suite; setup and recovery report; representative performance report; and a production-bundle scan proving no Supabase domain writer or FSA project-state writer remains.

The intended end state is deliberately ordinary to operate: install Astrid, run `astrid serve`, and work. One process owns one SQLite database and managed media root. The editor sees one media library, one task history, and one project-wide registry for characters, places, objects, and clothing. Hosting later runs the same logical model and must earn every additional platform table from a real feature.
