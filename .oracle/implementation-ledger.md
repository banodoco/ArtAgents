# Canonical pack beta — implementation ledger

Last reconciled: 2026-08-31

## Cloud execution addendum — 2026-09-01

This addendum supersedes current-status assertions below while retaining their
base census and design evidence. B1.1–B1.10 are committed as the isolated
strict-v2 contract. Strict schema/model/catalog, confined resources and
documentation, golden forms, external capability admission, early external
database rejection, and legacy-active isolation have focused evidence.
Candidate 46 closed erased canonical custody metadata after 185 focused
lifecycle tests and 104 subtests. Per user control
`babysit-c46-end-open-ended-b1-loop`, the independent erased-metadata delta
gate reused unaffected candidate-45 passes; there was no candidate 47 or whole
review reset. B1 checkpoint:
`14f1f7d5f77cb6bd384749941cff6e522b696590`.

### B2 addendum

B2.1–B2.9 are committed over the B1 checkpoint. Exactly 22 strict v2
manifests preserve the 64/12/10 capability census and typed rendering/
generation projections; `builtin` and 59 aliases are gone. Four canonical
database declarations preserve existing semantics and defaults. All 22 packs
have direct skills; `_core` routes a deterministic 22-pack census. Five
standalone Blender resources are confined, the offline 22-row coverage ledger
has zero unclassified surfaces, and production remains legacy-active with four
byte-unchanged schema manifests. One independent Luna certification passed 106
focused tests plus 78 subtests with no findings. B2 checkpoint:
`a293e4c416c0e716154c392c0dd43165344f870d`.

### B3 addendum

B3.1–B3.9 passed the bounded gate in a frozen six-path candidate. One explicit
catalog projection now feeds the existing immutable collision/migration
machinery, with a reserved synthetic kernel projection, manifest-derived
defaults, explicit Runaway composition, positive dependency-head enforcement,
and confined owner-relative migration handles. The deterministic Runaway
fixture replaces the absent historical demo without packaging it. Integrated
closure and one independent Luna certification each passed 122 focused tests;
all six hashes matched and there were no findings. Production remains
legacy-active until B4. B3 checkpoint:
`cd4dc91a31e4c7127b4023a87dabfdebea276ff1`.

### B4 addendum

B4.1–B4.8 are committed as the atomic production cutover. One operation-owned
bundled catalog and frozen database projection now feed application, SDK,
kernel/timeline reads, doctor, backup/restore, rendering/media, inspect, and
CLI/bridge seams. Production admits exactly 22 strict-v2 packs. Four schema
manifests, the separate manifest/parser/standard authorities, fixed composition
tuples, raw rereads, and the active legacy fallback are deleted. The bounded
gate accepted an 81-path candidate from candidate 2's unaffected passes plus
candidate 3's independent finding-5 delta pass. B4 checkpoint:
`81a64d64bd0ac0a920ceec69d75dd4ce9bbd1785`.

Worktree: `/Users/peteromalley/Documents/reigh-workspace/Astrid-canonical-pack-beta`

Branch: `megado/canonical-pack-beta`

Product base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`; current
reviewed checkpoint: `81a64d64bd0ac0a920ceec69d75dd4ce9bbd1785`

This is the authoritative answer to: **what already exists, what this project
run actually completed, and what remains to reach the one-canonical-pack beta
end state?**

It intentionally distinguishes three different things that earlier status
updates blurred together:

1. mature Astrid functionality already present at the captured base;
2. planning and research completed by this canonical-pack run; and
3. the canonical v2 product cutover, now active through B4.

## Executive determination

Astrid already has most of the hard product and SQLite machinery that a
canonical pack needs. The remaining project is a consolidation and authority
cutover, not a rewrite.

The canonical-pack run has committed B1 through B4. The B3 projection reuses
the existing migration, collision, checksum, drift, transaction, writer/UoW,
repository, and conformance machinery. B4 threads that projection through
every named operational consumer and activates strict v2 atomically.

The current product is therefore the **active canonical cutover awaiting B5
closure**:

- exactly 22 bundled packs load from strict v2 `pack.yaml`;
- database ownership projects through one catalog with no separate
  `schema-pack.yaml` species or fixed standard tuple;
- migration, repository, SDK, doctor, backup, restore, inspect, CLI, and
  rendering/media consumers share operation-owned canonical composition; and
- B5 must still prove final source/wheel/docs/resources/full-suite closure.

## Authority for execution

Use these authorities in this order:

1. The user's direction in this thread — complete the prior canonical-pack
   goal directly, preserve all existing custom behavior, package its agent
   documentation, and add no compatibility shims.
2. `northstar.md` — durable end state and anti-patterns.
3. `agent_goal.md` — frozen scope and exact 15 done criteria.
4. `custody.md` and source `7ac50c12` — the implementation baseline and
   behavior floor.
5. this `implementation-ledger.md` — evidence-backed current state and reusable
   foundation.
6. `tasklist.md` — the authoritative remaining-work sequence traced to the
   frozen goal.

The original proportional architecture remains useful at
`/Users/peteromalley/Documents/reigh-workspace/Astrid/.oracle/prep/canonical-pack-beta/plan.md`.

The former 2,317-line plan is retained at
`.oracle/prior-runs/canonical-pack-overgrown-plan.md` as planning history. It
is not the execution authority: later review loops expanded it into
installed-revision lifecycle, exhaustive Python/file ownership, and evidence
machinery beyond the beta goal. Do not resume another general planning loop.
Carry forward only its narrow useful findings explicitly represented in
`tasklist.md` and the concise `.oracle/plan.md`.

The reduced beta contract intentionally supersedes the early broad
"core-as-pack" direction: `_core` remains code-owned guidance/kernel, and the
beta adds neither a per-project composition lock nor a database-aware pack
lifecycle. Those are later accepted scope reductions, not verbatim wording
from the user's first request.

The following surviving top-level artifacts are also **non-authoritative
historical residue** and must not be counted as canonical-pack execution
evidence: `.oracle/evidence/final-matrix.md`,
`.oracle/checkins/batch-1.md`, `.oracle/checkins/batch-2.md`,
`.oracle/checkins/batch-2-rework.md`, `.oracle/briefs/pre-exec-review.md`, and
`.oracle/execution.log`. They belong to prior storyboard/run-ledger activity;
only the authorities listed above control this project.

## Conversation decision trace

This table ties the final scope back to the actual decisions made in this
thread, in chronological order. Later rows supersede the broader early ideas.

| Conversation decision | Final interpretation | Where it is captured |
| --- | --- | --- |
| Packs should be able to add database tables or columns | A trusted bundled pack owns and evolves its own SQLite tables through migration SQL. YAML declares ownership and migration identity; SQL remains the column/constraint/index authority. Packs do not mutate core or another pack's owned tables. | North Star principles; tasklist B1/B3 |
| Database and capability contributions should be part of one pack | Exactly one `pack.yaml` and one canonical identity/object/catalog; capability and database registries remain typed projections. | Agent goal decisions 1–7; B1 |
| Skip directly to the end state because there are no users | Hard cut to v2; no compatibility readers, shims, dual manifests, or migration period. | North Star; goal decisions 1–2; B1/B5 |
| Astrid already has a proper pack package | Reuse `PackDefinition`, discovery, typed registries, install/update/rollback/trust, schema registry, migration runner, writer/UoW, repositories, and operations. Do not rebuild them. | Inherited behavior floor; every batch's reuse constraints |
| The later beta discussion rejected a per-project composition lock as OTT | The accepted reduced contract keeps fixed bundled beta composition derived from manifest `default_enabled`; `schema_migrations` remains the sole applied-state record. It adds no enable/disable/purge lifecycle or external database packs. This supersedes the earlier broader core-as-pack/lifecycle exploration. | Goal decisions 9–14 and non-goals; B1/B3 |
| `references` is already real functionality | Preserve its three tables, repository, commands/events, SDK and `media references` CLI; only move architectural custody into the canonical manifest. | Goal decision 17; B2.6 |
| All existing custom functionality must use the canonical path | Inventory every bundled extension/database/CLI/SDK/bridge/docs/operational surface and assign it to one pack or an explicit kernel owner. Static factories may remain; ownership cannot bypass the catalog. | Goal decisions 8 and 14; B2.9/B4 |
| All of it should be documented in skill packages | Every retained product pack gets declared, packaged structured guidance; `_core` provides the generated pack census and routes to the owner. | Goal decisions 15–16; B2.7–B2.8/B5.4 |
| Add the easy high-value closure work | Keep lightweight coverage, useful inspect/doctor output, three golden forms, docs/resource/legacy/duplicate-authority CI gates, and `references` as exemplar. | Goal in-scope list and criteria 3, 8–10, 13; B1/B2/B4/B5 |
| Execute in an isolated worktree with Luna and Sol | This worktree/custody was created and planning/research ran under that policy. Product execution never began. | Custody; P0 ledger |
| Build a proper `astrid update` command afterward with Luna and Sol | It is a second dependent project whose base is the completed canonical-pack result. It must preserve user changes and pack-applied database migrations, and it must not be mixed into this task. | Status and explicit exclusions |

### Why this looked “mostly executed”

The user's memory was directionally correct about the **underlying pack work**:
most concrete capabilities had already been moved into 18 domain pack
directories, the empty `builtin` pack contains no capability implementation,
and the runtime already discovers 64 executors, 12 orchestrators, and 10
elements. The four SQLite-backed slices and the pack lifecycle also already
work. That is substantial prior implementation.

What had not been executed was the **new canonical-authority goal**: replacing
the v1/`schema-pack.yaml` split with one v2 object/catalog and moving all
consumers, docs, resources, packaging, and legacy deletion onto it. This
distinction explains both facts without calling existing work unfinished or
calling the canonical cutover complete.

## Current repository census

The retained beta target is **22 product packs plus irreducible `_core`
guidance**:

- 24 direct directories currently exist under `astrid/packs`;
- 19 directories have v1 `pack.yaml`, including deprecated empty `builtin`;
- four directories have `schema-pack.yaml` only: `timeline`, `shots`,
  `references`, and `runaway`;
- deleting `builtin` and retaining the other 18 capability packs plus the four
  data packs gives the intended 22 product packs;
- `_core` remains kernel guidance, not a dynamically unloadable product pack;
- current source discovery exposes 64 executors, 12 orchestrators, 10 elements,
  three element kinds, 29 generation features, and 14 generation modes;
- generation also exposes four built-in typed backend taxonomy/adapter
  descriptors; these are not manifest-discovered extension entries;
- the manifests contain 59 deprecated aliases, 49 of them in the old
  `builtin.*` namespace; and
- 17 of the 22 retained product packs have a direct `skill/SKILL.md`. The five
  missing pack skills are `blender`, `timeline`, `shots`, `references`, and
  `runaway`. `_core` has its own skill, and generation has one additional
  component-level skill.

## Pack-by-pack ledger

`Existing behavior` describes functionality already present at the base. It
must be preserved, not rebuilt. `Canonical delta` is the ownership/convergence
work still required.

| Retained pack | Existing behavior at base | Current declaration/docs | Canonical delta |
| --- | --- | --- | --- |
| `blender` | 1 executor for local/cloud Blender rendering | v1 `pack.yaml`; no pack skill | Convert to v2; add pack skill; retain permissions/runtime resources |
| `comfy_wrap` | 1 executor wrapping VibeComfy workflows | v1 `pack.yaml`; skill present | Mechanical v2 conversion and declared-resource closure |
| `editorial` | 15 executors spanning transcription, scenes/shots, arrangement, review, refinement, scripts, and validation | v1 `pack.yaml`; skill present; old aliases | Convert to v2; remove deprecated aliases; preserve all executor ownership |
| `fal` | 2 fal.ai generation/Foley executors | v1 `pack.yaml`; skill present | Mechanical v2 conversion; preserve external-service/secrets declarations |
| `foley` | 2 executors and 1 spatial-Foley orchestrator | v1 `pack.yaml`; skill present | Mechanical v2 conversion and alias removal |
| `generation` | 4 image/video/audio executors plus four typed generation backends and feature/mode registries | v1 `pack.yaml`; pack and component skill | Convert manifest; keep typed generation projections rather than making the catalog a service locator |
| `iteration` | 5 executors and 1 review-session orchestrator | v1 `pack.yaml`; skill present | Mechanical v2 conversion and resource declaration |
| `media` | 3 clip/speech/GIF executors; also parent CLI family for references | v1 `pack.yaml`; skill present | Convert manifest; retain static nested mount while sourcing ownership from catalog |
| `moirae` | 1 terminal-demo renderer executor | v1 `pack.yaml`; skill present | Mechanical v2 conversion and alias removal |
| `references` | Three SQLite tables; `ReferenceRepository`; lifecycle/media/link commands and events; SDK facade; `media references` CLI; conformance | strict `schema-pack.yaml` only; no skill | Create combined v2 `pack.yaml` with `database`; preserve exact SQL/product semantics; add skill; make the exemplar combined pack |
| `reigh` | 4 Reigh bridge/data/publish executors | v1 `pack.yaml`; skill present | Mechanical v2 conversion; preserve integration boundary/resources |
| `rendering` | 5 executors, 10 discovered elements, typed renderer/planner/finalizer extensions | v1 `pack.yaml`; skill present | Convert manifest; project existing typed rendering extensions; close element assets/resources |
| `runaway` | One `runaway_transitions` table; `RunawayRepository`; receipt-backed `runaway.create`; sharded transition behavior | strict `schema-pack.yaml` only; no skill; no default app mount | Create database-only v2 pack; add skill; keep non-default composition and existing semantics; replace stale historical-demo tests with temporary fixtures |
| `runpod` | 5 GPU pod lifecycle executors | v1 `pack.yaml`; skill present | Mechanical v2 conversion and resource closure |
| `shots` | Two SQLite tables; `ShotRepository`; create/add/remove/reorder commands/events; `timelines shots` CLI; conformance | strict `schema-pack.yaml` only; no skill | Create combined v2 pack; preserve exact SQL/product behavior; add skill |
| `stream_content` | 2 executors and 1 distillation orchestrator | v1 `pack.yaml`; skill present | Mechanical v2 conversion and resource closure |
| `timeline` | One SQLite table; `TimelineRepository`; create/save/archive/unarchive/history/diff/render/visualize product behavior; CLI/bridge mount | strict `schema-pack.yaml` only; no skill | Create combined v2 pack; preserve exact SQL/repository/CLI/SDK behavior; add skill |
| `training` | 4 executors and 2 dataset/training orchestrators | v1 `pack.yaml`; skill present | Mechanical v2 conversion and alias removal |
| `understanding` | 5 audio/visual/video understanding executors | v1 `pack.yaml`; skill present | Mechanical v2 conversion and alias removal |
| `vibecomfy` | 2 workflow run/validate executors | v1 `pack.yaml`; skill present | Mechanical v2 conversion; preserve external capability behavior |
| `video_editing` | 1 cut executor and 7 production orchestrators | v1 `pack.yaml`; skill present | Mechanical v2 conversion and alias removal |
| `youtube` | 2 YouTube acquire/upload executors | v1 `pack.yaml`; skill present | Mechanical v2 conversion and alias removal |

`_core` already provides the root agent-facing Astrid skill and CLI/capability
census. It remains an explicit irreducible kernel/documentation owner. It needs
to route to a generated 22-pack census, but it should not be disguised as a
normal unloadable product pack.

## Existing implementation to reuse

### Capability-pack machinery — implemented

- `PackDefinition` is already a useful frozen dataclass shell that normalizes
  identity, root/manifest paths, content, agent metadata, aliases, permissions,
  extensions, and taxonomy. Its nested mappings remain mutable, so it is not
  yet a deeply immutable canonical object.
- Shared discovery already layers source, local, explicit extra,
  environment-provided, and installed packs with provenance and deterministic
  precedence.
- Typed executor, orchestrator, element, rendering, generation, skill/search,
  and agent-index projections already exist.
- Validation, layout checks, scaffolding, entrypoint guards, aliases, forks,
  and overrides already exist.
- Install, update, rollback, uninstall, revision directories, active pointers,
  per-pack locks, and trust inspection already exist for capability packs.
- The existing pack management CLI already has `validate`, `new`, `list`,
  `inspect`, `status`, `install`, `update`, `uninstall`, `rollback`,
  `agent-index`, and `search`. The final work should extend the existing
  inspect/index surfaces to canonical data/docs/resources, not invent a second
  pack CLI.

What is missing here is not another pack framework. The current runtime loader
accepts `pack.yaml`, `pack.yml`, and `pack.json`, defaults missing values, and
supports legacy flat forms. Static validation and runtime loading are not one
complete authority. There is no v2 `CanonicalPack` or immutable bundled
catalog containing the optional database contribution.

### SQLite and schema machinery — implemented

- The separate `SchemaPackManifest` parser is strict and immutable.
- `SchemaPackRegistry` already rejects collisions atomically across pack IDs,
  tables, migrations, stream/event/command vocabulary, repositories, and CLI/
  bridge mounts, then freezes deterministic projections.
- The migration runner already provides dependency ordering and cycle checks,
  exact-byte checksums, name/checksum/too-new drift refusal, read-only probes,
  and one transaction per migration.
- `open_database` probes before write, never migrates read-only opens, and
  applies trusted pending migrations only on writable opens.
- `DatabaseWriter` provides the single SQLite writer boundary; `UnitOfWork`
  owns repository transactions.
- Typed repositories, event streams, hash chains, idempotency receipts,
  services, and conformance patterns are already real.
- Doctor, backup, restore, SDK registry propagation, and read compatibility
  checks are already database-aware.

The database cutover should reuse those algorithms. It must remove the old
schema-pack identity/parser and project equivalent immutable descriptors from
the canonical pack catalog.

Two bounded correctness gaps remain within the reusable migration layer:

1. parsed dependency minimum versions are not currently compared with the
   dependency pack's available migration head; and
2. migration bytes are rediscovered from a hard-coded `astrid/packs/<id>`
   layout rather than carried as owner-relative resolved resources.

### Product database slices — implemented

The four data packs are not hypothetical schemas:

- `timeline` owns `timelines` and five command/event families around the
  canonical whole-document timeline.
- `shots` owns `shots` and `shot_items`, a `shot.shot` stream, and four
  receipt-backed mutation families.
- `references` owns `project_references`, `media_references`, and
  `reference_links`, a `reference.reference` stream, seven event kinds, seven
  command kinds, repository/SDK/CLI behavior, and conformance.
- `runaway` owns `runaway_transitions`, its typed repository and idempotent
  create command; it intentionally has no stream/events/CLI/SDK mount.

The end-state change is architectural custody: move these declarations into
their ordinary `pack.yaml` without rewriting their tables or product behavior.

### Application and operational behavior — implemented but duplicated

- Standard application composition already creates one owner lock, one
  writer, and typed project/timeline/shots/references/tasks/media/runs/evidence
  repositories and services.
- `AstridClient` can retain and propagate an explicitly supplied schema
  registry through later invocations.
- kernel read helpers can accept/context-bind a registry.
- doctor already reports schema health; backup/restore already provides staged
  validation, online SQLite backup, external-media custody, journaling, crash
  recovery, and atomic publication.
- the installed-artifact packaging harness and wheel-oriented tests already
  exist and should be adapted.

The missing convergence is that application, SDK invocation, doctor, restore,
and managed-media reads can each build or reread standard database state.
There are **three fixed authorities** for the default
`("timeline", "shots", "references")` composition:

1. `astrid/packs/__init__.py`: `STANDARD_SCHEMA_PACKS`;
2. `astrid/core/schema_packs/standard.py`: `STANDARD_SCHEMA_PACKS`; and
3. `astrid/core/cli/domain_product.py`: `_STANDARD_PACK_DIRS`, plus direct
   schema-manifest rereads for static CLI mounts.

Seven independent builder consumers must converge: `astrid/application.py`,
`astrid/sdk/invocation.py`, `astrid/core/kernel/read.py`,
`astrid/core/timeline/_edit_helpers.py`, `astrid/core/doctor.py`,
`astrid/core/backup/operations.py`, and
`astrid/core/rendering/assets.py`. The CLI mount reader is an eighth direct
consumer. All must receive the same catalog-derived database projection.

### Agent documentation — mostly present, not canonically closed

Seventeen of 22 retained product packs already have direct skill packages, and
their manifests generally contain purpose, entrypoint, permission, and
capability metadata. `_core` already has a large agent-facing skill and a
generated capability index.

The final gap is specific:

- add skills for `blender`, `timeline`, `shots`, `references`, and `runaway`;
- declare and validate each pack's documentation in v2;
- package declared skills/docs in the wheel (current package rules exclude
  `skill/` trees);
- generate an authoritative pack census in `_core` that routes to the owning
  skill; and
- make the zero-unclassified coverage ledger an offline build/review gate, not
  a second runtime authority.

## What this canonical-pack run completed

The run did real project-control work, but no implementation work:

1. Prepared the original six-file packet under
   `Astrid/.oracle/prep/canonical-pack-beta/`.
2. Captured the dirty source checkout and created this isolated worktree and
   branch from the exact base SHA.
3. Re-established and froze `northstar.md`, `agent_goal.md`, and `custody.md`.
4. Ran one initial read-only Sol planning pass.
5. Ran ten accepted Luna exploration areas; packaging E7 required one
   replacement attempt, so there are eleven raw exploration outputs.
6. Repeatedly revised and stability-checked the plan through numbered revision
   9, including one disk-full failure and one host-rejected stale result.
7. Ran seven settled-plan waves of three Luna critics each. Wave 7 is proven by
   `findings/settled7/_report.json`: three successes, zero failures, 434.376
   aggregate agent-seconds. It produced five narrow issue groups and was not
   clean. No Wave 7 receipt was added to the old receipt stream; this later
   reconciliation records its disposition.
8. The original Megado execution stopped before a canonical tasklist,
   pre-execution review, implementation, commits, push, or the follow-on
   Astrid application-update command. This later reconciliation created the
   present ledger, tasklist, concise plan, and status.

The Wave 7 findings do **not** justify another broad planning cycle. Their
useful beta dispositions are:

- keep Python-ownership and table-effect audits offline and non-duplicative;
- do not force runtime doctor to import an audit ledger;
- use ordinary wheel build provenance rather than adding a Python-byte
  attestation system;
- do not redesign installed revision custody or external payload policy in
  this bundled-database cutover; and
- use a simple final evidence matrix followed by review, without a
  self-referential digest protocol.

## Exact done-criteria status

| Goal criterion | Status now | Evidence-based interpretation |
| --- | --- | --- |
| 1. Every bundled product pack loads from v2 `pack.yaml` | **B4 active; wheel proof pending B5** | Exactly 22 retained packs production-load from strict v2 with 64 executors, 12 orchestrators, and 10 elements |
| 2. One parsed authority feeds consumers | **B4 complete** | One operation-owned catalog and frozen database projection feed every named consumer; no independent production parser/registry builder remains |
| 3. Zero-unclassified customization ledger | **B2 complete** | Offline 22-row ledger maps capability/database/CLI/SDK/bridge/docs/operations/resources, justifies kernel owners, and reports zero unclassified |
| 4. Manifest-derived standard DB composition | **B4 complete** | Default core/timeline/shots/references and explicit Runaway composition derive from canonical manifests; fixed production authorities are deleted |
| 5. Four data-pack semantics preserved | **B4 focused evidence green** | Fresh/reopen/Runaway/read-only/drift/rollback, registry/writer/repository, and exact table-ownership behavior pass through active canonical composition |
| 6. Owner-relative migrations and dependencies | **B3 complete** | Canonical migrations carry confined owner handles; positive minimum heads, availability, cycles, core reachability, ordering, checksums, drift, and transactions pass |
| 7. Operational consumers agree | **B4 complete** | application/SDK/kernel/timeline/doctor/backup/restore/rendering/media/inspect/CLI share the operation-owned projection |
| 8. Packaged agent docs and `_core` census | **B2 source docs complete; wheel proof pending B5** | 22/22 direct skills validate and deterministic `_core` routing resolves all 22 |
| 9. Canonical inspect/doctor output | **B4 source behavior complete; final proof pending B5** | inspect and doctor expose canonical identity, capability, database, docs, resources, and migration state |
| 10. Clean wheel contains all declared resources | **B2 source closure complete; wheel proof pending B5** | Five standalone Blender resources and all content/extension/migration handles resolve confined with no overlap |
| 11. Legacy authorities deleted | **B4 complete; final absence audit pending B5** | Four schema manifests, separate parser/standard path, fixed tuples, raw rereads, fallback, and stale active tests/tooling are removed |
| 12. External capability works; external DB fails | **B1 behavior active; installed-wheel rerun pending B5** | External capability admission and pre-resolution external database rejection use the strict path |
| 13. Three golden pack forms validate | **B1 complete** | Capability-only, database-only, and combined fixtures validate under the strict path |
| 14. Focused and broad tests pass after cutover | **B4 focused evidence green; B5 suites pending** | Activation passed focused consumer/authority suites; full authoritative suite remains B5 |
| 15. Final evidence and independent review | **B1–B4 checkpoints complete; final matrix pending B5** | B4 checkpoint `81a64d64` contains the 81-path accepted activation candidate |

## Direct execution plan

The next work is five implementation batches. No additional general planning
wave is required.

### B1 — strict v2 canonical definition and bundled catalog

- Evolve the existing pack loader/model rather than creating a parallel pack
  framework.
- Freeze integer `schema_version: 2`, consistent with the existing integer v1
  convention. This intentionally resolves the original prep example's quoted
  `"2"` spelling.
- Add the optional database declaration, explicit `default_enabled`, agent-doc
  declaration, normalized dependencies, provenance, and confined pack-relative
  resources to one complete immutable consumer-facing canonical object.
- Parse/validate explicit golden fixture roots into one deterministic catalog;
  do not activate strict v2 against the current v1 bundled tree in B1.
- Project existing typed capability registries and the database registry from
  that object.
- Freeze dependency grammar now as pack ID plus a positive minimum migration
  head, ready for B3 enforcement.
- Reject alternate filenames, missing/defaulted identity, legacy flat forms,
  and external manifests containing `database` before resolving SQL/resources.
- Add capability-only, database-only, combined, invalid-legacy, path-escape,
  and external-database fixtures. Prove a positive external capability-only v2
  pack through local/extra/environment/installed admission.

Gate: one isolated v2 parsing authority and final grammar; the active legacy
runtime remains unchanged; no shim, project lock, marketplace, or installed-
record redesign.

### B2 — convert the complete 22-pack bundled set

- Delete empty `builtin` and all deprecated aliases.
- Convert the 18 retained capability manifests to v2.
- Add combined/database-only v2 manifests for timeline, shots, references, and
  Runaway, preserving current declarations and SQL.
- Preserve current default behavior with `timeline`, `shots`, and `references`
  default-enabled and `runaway` non-default. Runaway remains explicitly
  composable and fully canonical without silently changing every project's
  schema.
- Add the five missing pack skills and declare all 22 skill/doc roots; no
  bundled pack uses a documentation opt-out in this beta.
- Generate the `_core` pack census and complete an offline ownership/coverage
  ledger with zero unclassified bundled custom surfaces. Its bounded resource
  dimension inventories known typed component/rendering loaders and explicit
  pack-relative reads; every known runtime resource is declared or justified
  as kernel-owned.

Gate: exactly 22 product packs load from v2; all 64 executors, 12
orchestrators, typed extensions, elements, database declarations, and docs
have canonical owners.

### B3 — database projection into the existing engine

- Move the schema registry's useful collision/freeze algorithms behind the
  canonical database projection through explicit injection. Do not delete the
  production legacy builders in this batch.
- Carry owner/root/resource identity on migration descriptors.
- Enforce the B1 dependency grammar by comparing declared positive minimum
  migration heads with dependency pack heads.
- Derive default composition from `database.default_enabled`, not a fixed
  tuple.
- Preserve `schema_migrations` as the only applied-state record; add no
  project composition lock.

Gate: fresh default DB, existing DB reopen, explicit Runaway-extended DB,
read-only pending behavior, checksum/name drift, rollback, collision, and
dependency tests all pass.

### B4 — converge all operational consumers

- Construct one bundled catalog/database projection at the top-level operation
  seam and thread typed projections to application, SDK/client/invocation,
  kernel reads, rendering/media reads, doctor, backup, restore, and static CLI/
  bridge mount construction.
- Preserve explicit typed service/repository/CLI factories.
- Extend the existing pack inspect command and doctor output to report
  canonical identity, source, capabilities, database ownership/head, docs,
  and declared resource health in text/JSON where those surfaces already
  support it.
- Preserve current backup/restore, lock, writer, transaction, and read-only
  semantics.
- Treat B2–B4 as one unshipped atomic tranche. After all seven builder
  consumers and the direct CLI mount reader have moved, activate strict v2 and
  simultaneously delete the four `schema-pack.yaml` files, both
  `STANDARD_SCHEMA_PACKS` tuples, `_STANDARD_PACK_DIRS`/raw schema rereads, and
  the separate schema-pack identity/parser/standard path. Before activation
  only legacy is active; afterward only canonical v2 is active.

Gate: every operational path agrees on the same expected default composition
and ownership without turning the catalog into a runtime service locator.

### B5 — hard deletion, packaging, docs, and validation

- Verify the B4 activation left no `schema-pack.yaml`, v1/flat/alternate
  manifest form, duplicate fixed list, raw identity reconstruction, alias shim,
  compatibility-only test, or active doc teaching the old system.
- Replace Runaway's absent historical-demo tests with deterministic temporary
  fixtures; do not restore/package the demo.
- Make package data include all v2 manifests, four migration trees, all 22 pack
  skills/docs, and every declared runtime resource; compare declared resource
  closure in source and wheel.
- Create an isolated validation/build environment, install and record the
  `build` version, and only then build the clean wheel.
- Run focused pack/database/consumer tests, clean outside-checkout wheel smoke,
  the broad suite once, then a concise criterion evidence matrix and final Sol
  review. Re-run the positive external capability-only v2 admission case in
  the installed-wheel lane.
- Commit reviewed checkpoints and push only after the final gate. Do not merge,
  deploy, or release.

Gate: no active legacy authority; source and wheel load all 22 packs; default
composition remains the three current product DB packs; Runaway explicitly
composes; all declared docs/resources resolve; final tests and review pass.

## Explicitly not part of this beta cutover

- per-project pack/revision composition locks;
- enable/disable/purge or database-aware uninstall lifecycle;
- third-party SQL/database packs;
- installed-record v2 redesign, revision byte attestation, or execution-time
  revalidation machinery;
- marketplace, signing, sandbox, dependency solver, or permissions UI;
- dynamic repository/service/CLI/bridge factories;
- runtime consumption of the offline customization coverage ledger;
- exhaustive classification/digests for every Python or authoring file;
- a new evidence platform or self-referential receipt protocol; and
- the separately requested `astrid update` command, which is the next project
  after this cutover and has not started.

## Verification evidence for this ledger

- B1 checkpoint `14f1f7d5f77cb6bd384749941cff6e522b696590`
  contains the frozen 30-path product candidate and accepted control evidence.
- Candidate 45 independent validation passed 214 focused tests plus 102
  subtests and matched all three inherited clean-base failures; two unaffected
  independent Luna reviewers passed it.
- Candidate 46's bounded erased-metadata repair passed 185 focused lifecycle
  tests plus 104 subtests while preserving 19 legacy production manifests,
  four `schema-pack.yaml` manifests, and zero production v2 manifests.
- The sole user-directed independent custody delta passed: 30/30 hashes, five
  erased-custody tests plus 12 subtests, 30 adjacent lifecycle tests, valid
  canonical and legacy behavior, and no blockers.
- B2 checkpoint `a293e4c416c0e716154c392c0dd43165344f870d`
  contains the reviewed 35-path canonical bundled-pack conversion.
- B3 candidate manifest
  `.oracle/evidence/b3-candidate-1.sha256` has SHA-256
  `8f2140a6a79f3f591c04385f72bf3cd8ba7eedf299011ecf9ea7360d17a6f087`;
  integrated closure and independent certification each passed 122 tests with
  6/6 hashes and no findings.
- Cumulative gate 1 independently confirmed linear B1–B3 ancestry, accepted
  checkpoint evidence, production legacy isolation, and B4 cutover readiness;
  its bounded integration command passed 70 tests with no blockers.
- B4 candidate 3 manifest
  `.oracle/evidence/b4-candidate-3.sha256` has SHA-256
  `2e90aee2dd383f7eb4913a5cfd546b042221c89110a43f03b2e8e2d8d3c764d3`;
  81/81 identities matched. Candidate 2 findings 1, 2, 3, 4, and 6 passed;
  the bounded finding-5 correction passed 32 plus 43 focused tests, and its
  independent delta passed with `AUTHORITY LINT OK` and no blockers.
- Cumulative gate 2 independently confirmed exact B1–B4/control ancestry,
  B4 digest plus 81/81 identities, strict-v2-only authority, canonical default
  and Runaway composition, operation-owned consumers, and external trust
  boundaries. Its bounded command passed 279 tests plus 78 subtests; two
  installed-artifact failures are finite B5 packaging work and the SDK
  rendering failure is the recorded unavailable dependency lane.

## Honest progress assessment

- **Inherited product foundation:** substantial and mostly built. Eighteen of
  22 target product directories already have capability-pack manifests; all
  discovered executors/orchestrators/elements already live in domain packs;
  17 of 22 product packs have direct skills; all four SQLite product slices and
  their migration/repository/operational machinery work.
- **Canonical v2 product cutover:** B1–B4 checkpoints complete. Production now
  uses one strict-v2 catalog/database authority across every named consumer;
  alternate schema-pack identity and fixed authorities are deleted.
- **Clarity/reconciliation:** complete; control documents reflect B1–B4 gate
  truth.
- **Frozen final criteria:** 0/15 complete end to end; B1–B4 provide accepted
  implementation evidence, while B5 final closure remains.
- **Remaining sequence:** B5 closure.

The correct next action is B5 source/wheel/docs/test/evidence closure.
Cloud capacity and tooling preflight are green.
