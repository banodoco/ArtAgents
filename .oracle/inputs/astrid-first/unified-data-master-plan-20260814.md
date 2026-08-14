# Unified data master plan: a plug-in substrate for Astrid and future agents

**Date:** 2026-08-14  
**Status:** vision document for the unified-data area  
**Current implementation baseline:** [Unified data model plan v10](unified-data-model-plan-v10-20260813.md)  
**Current execution plan:** [Astrid-first two-week sprint plan](astrid-first-sprint-plan-20260813.md) and [Astrid-first megaplan North Star](../.megaplan/initiatives/astrid-first/NORTHSTAR.md)

## Executive summary

The aim of this area is larger than one database for one creative product. We want a small, durable data kernel that gives an agent the hard primitives it repeatedly needs—projects, ordered events, atomic command receipts, runs, evidence, executable tasks, fenced attempts, exact assets, and schema evolution—and lets product-specific domains arrive as packs. Astrid is the first composition: the same 14-table kernel plus an in-tree timeline pack, shots pack, and references pack. A later software-engineering agent should be another composition of that unchanged kernel, with workspaces, changesets, and reviews as its own packs. The data should act like a plug-in: one trustworthy substrate, different domain components, different agents.

The portable claim is intentionally narrow and strong: **tasks execute; everything else is an event; every exact asset is media**. An image generation, a source edit, a render, and a test run differ in domain meaning, but they need the same admission boundary, retry identity, attempt fencing, causal history, grouped execution, evidence, and exact-byte provenance. Generated video is media; so are a source file, diff, compiler log, test report, and screenshot. A run may mean a generation batch or a CI-style operation. An evidence item may mean a visual quality observation or a failed-test summary. These meanings differ without requiring the kernel tables to differ.

A pack is more than optional tables. It is a manifest plus migrations, registered stream/event/command kinds, repositories, domain checks, conformance tests, and CLI or bridge mounts. Packs depend inward on the kernel and trade only in kernel-owned currencies such as `project_id`, `task_id`, and `media_id`. The kernel never foreign-keys into a pack. Packs never open their own semantic writer. Every pack command executes through the same kernel-owned transaction and proves the same replay, mismatch, crash-atomicity, and project-isolation guarantees. This is how domain data becomes composable without becoming less trustworthy.

Three v10 choices make that architecture real rather than rhetorical. `schema_migrations` is scoped by pack, so the kernel and each pack evolve independently and forward-only. Stream types and namespaced event/command kinds come from a startup registry rather than kernel DDL that knows Astrid vocabulary. Media remains in the kernel because exact assets and task outputs are universal. Together these are the extension seams around which later products can compose.

This master plan is the vision, not a new implementation program. The near-term deliverable remains exactly the Astrid-first v10 composition: one local SQLite authority, one managed-media root, one repository-owned writer, and exactly 20 tables—14 kernel tables plus timeline (1), shots (2), and references (3). The packs are in-tree and registered explicitly with `register_pack()`. There is no dynamic loader, marketplace, third-party ABI, or shared-library extraction in the current milestone. The eight-sprint base plan and the Astrid-first megaplan epic remain the execution mechanism. The sequence is **boundary now, loader later**: first prove the factoring inside a real product; extract only when a second real agent supplies requirements.

The test of the vision is concrete. Delete a pack and the entire kernel suite must remain green. Compose an illustrative software-engineering agent and it must need no kernel-table change. If either test fails, the factoring is wrong. If both pass, the architecture can expand without turning the current Astrid build into speculative platform work.

## 1. Vision statement

### 1.1 North star

Build a general, local-first data substrate on which agent products can be assembled from a small trusted kernel and a set of domain packs. The kernel owns identity, ordered change, atomic command results, executable work, attempts, grouping, evidence, and exact assets. Packs add the nouns, relationships, projections, and interfaces that make a particular product useful. Each product is a deliberate composition: the same rules of truth and failure, combined with the domains appropriate to that agent.

In human terms, we should not have to redesign reliability every time we build a new agent. A filmmaker should be able to organize shots and reference characters; a software engineer should be able to organize workspaces, changesets, and reviews. Those are different products, but both need to know what was requested, whether a retry is the same request, what actually ran, which attempt won, which exact files were produced, what evidence was observed, and how the current projection follows from ordered changes. The kernel should answer those questions once. Packs should answer the product-specific questions.

This produces a useful separation of ambition:

- **One kernel, many compositions.** The kernel is a reusable contract, not the union of every future domain.
- **One product, several packs.** Astrid can grow coherent domains without turning its kernel into an Astrid schema.
- **One authority per product instance.** Modularity does not fragment truth. The composed product still has one database, one media root, one transaction boundary, and one semantic writer.
- **Proof travels with extension.** New domains do not inherit trust by convention; their commands pass the same conformance suite as kernel commands.

### 1.2 Relationship to Astrid, Reigh, and future agents

Astrid is the first proof of the architecture and the current product priority. It composes the kernel with three domain packs:

- timeline, for the editor document, asset registry, per-timeline event stream, and whole-document compare-and-swap;
- shots, for project-scoped storyboard containers and ordered placements of exact media;
- references, for named project entities, canonical and contextual media associations, and typed relationships.

The Reigh editor remains Astrid's frontend. It is not itself the kernel and it does not become a general plug-in host in this plan. Its existing bridge is a mounted Astrid-facing surface over the timeline and media capabilities of the composition. The current route and payload contract, timeline CAS behavior, asset Range serving, and draft-safety guarantees remain part of the near-term product. The general architecture sits behind that contract; it does not require an editor rewrite.

Future agents sit beside Astrid, not inside it. A software-engineering agent, for example, would reuse the same kernel contract and supply its own domain composition. Its source files and diffs would use kernel media. Its tool calls and edits would use tasks and fenced attempts. Its multi-step verification would use runs, dependencies, and evidence. Workspaces, changesets, and reviews would be domain packs. That future product would be trusted by the same receipt and conformance machinery, while remaining free to expose a different CLI, bridge, and user experience.

### 1.3 What the vision is—and is not

The vision is a direction for factoring decisions made now. It says where domain assumptions may live, what contracts must be stable, and what must remain reusable. It does not claim that a public plug-in ecosystem exists. It does not promise that arbitrary third-party tables can be installed safely. It does not make all agents identical. It does not turn every JSON field into an extension point or every current abstraction into a permanent public API.

The current milestone is successful if Astrid ships cleanly and its internal boundaries make a second composition possible. The future architecture becomes real when a second agent actually composes the kernel without modifying it and the conformance kit catches the same categories of error there. Until then, the architectural boundary is intentional but the loader remains hypothetical.

## 2. Architecture of the vision

### 2.1 The 14-table agent kernel

The kernel is the smallest set of relational primitives that v10 considers portable across agent products. The inventory below restates v10 §2, **Normative 20-table schema**, especially §2.1, **Inventory and run grouping**; v10 §2.2 remains authoritative for exact DDL. The kernel is not merely a shared schema; it includes the repository rules, transaction semantics, registries, and tests that give those tables meaning.

| Kernel table | Role in the general model |
| --- | --- |
| `schema_migrations` | Records forward-only schema evolution independently for `core` and each pack, keyed by `(pack, version)`. It makes a composed database evolvable without one global version number or legacy cutover machinery. |
| `projects` | Provides the top-level data namespace, settings boundary, and project-wide event sequence. “Project” is the kernel term for the bounded body of work owned by one local composition; future products can present it as a workspace without renaming the table. |
| `event_streams` | Registers ordered streams for aggregates, carrying a registered stream type, aggregate identity, and compare-and-swap head. It gives both kernel and pack projections a common concurrency boundary. |
| `events` | Stores the immutable record of meaningful semantic change—including task lifecycle change—ordered per stream and across the project. Polymorphic subjects let events describe pack-owned rows without a kernel foreign key to those rows; heartbeats and narrow attempt liveness are the deliberate non-event exception. |
| `command_receipts` | Makes a command retry-safe and its result durable. It binds a canonical request hash and idempotency key to one atomic transaction, its event range, and the complete result IDs. |
| `runs` | Groups and observes zero or many direct tasks and associated evidence. A run is coordination and provenance, not an executable parent and not a hidden plan graph. |
| `evidence_items` | Captures queryable observations for a run, optionally tied to the direct child task and exact media that produced them. Evidence can represent creative assessment, tool output, validation, or review findings. |
| `tasks` | Represents bounded, immutable, independently executable work. It owns the durable lifecycle projection, direct run membership, and stable fan-out ordinal. |
| `task_dependencies` | Expresses hard or soft DAG edges between real executable tasks. It provides ordering without generic plans, steps, mutable cursors, or pseudo-work. |
| `execution_attempts` | Fences claims and retries so stale workers cannot win. It records attempt identity, status version, lease and heartbeat state, progress, errors, and terminal outcome. |
| `task_outputs` | Orders and labels the exact media produced by a task and identifies the primary result where applicable. It is the durable bridge from execution to exact assets. |
| `media` | Gives every exact byte sequence a project-scoped SHA-256 identity with kind, MIME type, size, and metadata. “Media” is deliberately broad: creative assets, source, diffs, logs, reports, and data are all exact assets. |
| `media_locations` | Separates replaceable location from identity. Managed-local, external-local, and remote locators may change or fail while the exact media identity remains stable and verifiable. |
| `media_relations` | Records exact-asset lineage and typed relationships such as derivation, variants, inputs, masks, and audio association without relying on path or display-name inference. |

The kernel's foundation remains: **tasks execute; everything else is an event; every exact asset is media**. Each clause excludes a common failure mode. Tasks are admitted only when there is actual bounded work to claim and fence, so observations and user decisions do not masquerade as jobs. Events cover meaningful state transitions, so packs cannot create silent side channels. Media is based on verified bytes, so provenance does not collapse when files move or names change.

Runs and evidence complete this model without reintroducing plans. A fan-out command creates a run and direct child tasks with stable ordinals; `task_dependencies` describes real execution edges. A synchronous understanding command may create a zero-task run plus evidence. The receipt returns the `run_id`, ordered task IDs, and evidence IDs. Grouping, observation, and execution stay distinct.

### 2.2 The pack model

A schema pack is **tables plus behavior and proof**. Its manifest declares:

- `id` and `version`;
- `depends_on` for registration and migration order;
- `migrations[]` for its forward-only schema changes;
- `stream_types[]`, `event_kinds[]`, and `command_kinds[]` for registered vocabulary;
- `repositories[]` for domain reads and writes;
- `conformance[]` for reusable and domain-specific checks;
- `cli_mounts{}` and `bridge_mounts[]` for its product-facing surfaces.

In the current source composition this means `core/` plus `packs/timeline`, `packs/shots`, and `packs/references`. Startup explicitly calls `register_pack()` with the shipped set. Registration validates dependencies and namespaced vocabulary, applies migrations in declared order, registers repositories with the kernel writer, and mounts the CLI or bridge surfaces selected by Astrid.

The manifest is an internal composition contract in v10, not a stable third-party ABI. A pack cannot execute arbitrary SQL through an ambient connection. It receives a unit-of-work handle inside the kernel-owned `BEGIN IMMEDIATE` transaction. The kernel supplies idempotency lookup, canonical request checking, consecutive project-sequence allocation, stream-head CAS, event append, projection coordination, and receipt writing. A pack repository supplies its domain validation and projection updates inside that command unit.

Every eventful command therefore has one shape:

1. Resolve the idempotency key, canonical request hash, and expected stream or attempt versions.
2. Reject a mismatched replay before mutation, or return the existing receipt for an identical replay.
3. Allocate ordered project and stream sequence numbers.
4. Append registered event kinds and advance the relevant heads.
5. Update kernel and/or pack projections.
6. Materialize runs, tasks, evidence, media, outputs, or domain associations as required.
7. Write one complete command receipt.
8. Commit, exposing either the old state or the complete new state across a crash.

The conformance kit applies this shape to every pack command, consistent with v10 §2.3, **Repository-enforced constraints and atomicity**. At minimum it proves identical replay, mismatched-key rejection, statement-boundary old-or-complete behavior, and same-project assertions. Packs add their own domain checks—for example timeline CAS, shot ordering and exact-media placement, or reference primary-selection rules—but they do not weaken the common guarantees.

CLI and bridge mounts are composition surfaces, not evidence of a dynamic platform. In Astrid, the kernel owns `projects`, `media`, `tasks`, `runs`, `serve`, `doctor`, and `backup`; the timeline pack contributes `timelines`; shots mount under `timelines shots`; references mount under `media references`. That preserves v10 §4.1's exact eight top-level product families. Another agent may mount different pack surfaces while reusing the kernel services. Backup and doctor stay broadly reusable because all installed pack state shares the database and writer boundary.

### 2.3 Plugin laws

Five laws determine whether a domain is a pack rather than a fork of the kernel.

**1. Foreign keys point inward only.** Pack tables may reference kernel tables. Kernel tables never reference pack tables. When a kernel event describes a pack aggregate, it uses `events.subject_type` and `events.subject_id`, not a pack-specific foreign key. This keeps the kernel physically removable from any one domain vocabulary.

**2. Kernel currencies are the only cross-pack references.** Packs exchange explicitly kernel-owned IDs such as `project_id`, `task_id`, and `media_id`. A shots row can identify exact media without knowing the timeline schema. A review pack can identify a task or diff media without reaching into a changeset table. Manifest dependencies order composition; they are not permission for pack-table foreign keys to form a new monolith.

**3. Packs never own a writer.** There is one semantic writer per product instance. Pack repositories join the kernel queue and unit of work; bridge handlers, CLI handlers, SDK services, executors, media importers, and pack code do not open alternate transactions or mutate authoritative files. Modularity must not recreate multi-authority synchronization.

**4. Every pack command passes the kernel conformance kit.** A new domain earns trust through repeatable proof: idempotent replay, mismatch rejection before mutation, crash atomicity at statement boundaries, project isolation, registered vocabulary, and the same writer. Domain tests are additive, not substitutes.

**5. Vocabularies are namespaced and registered.** Core and packs declare stream, event, and command kinds through the composed registry. Names such as `timeline.saved`, `shot.item_added`, and `reference.primary_changed` do not collide and do not appear as hardcoded pack knowledge in kernel DDL or handler-local allowlists.

Two supporting rules follow. First, schema packs and executable capability/component/element/model manifests remain file-described, while authoritative pack data lives in the shared database. A manifest describes composition; it is not a second domain authority. Second, removal is a source-factoring test in v10, not a promise of destructive uninstall from an existing database. Deleting a pack from a build must leave kernel tests green; it need not drop live tables or reverse migrations.

### 2.4 The three extension seams

The v10 baseline contains three load-bearing deltas that let the kernel generalize.

**Pack-scoped migrations.** `schema_migrations` is keyed by `(pack, version)`, with names unique within a pack. The kernel and each installed pack migrate independently, forward-only, in declared dependency order. Astrid's fresh composition still produces exactly 20 tables, but the catalog assertion is derived from the 14-table kernel catalog plus the installed pack manifests. “Twenty” is an Astrid composition fact, not the universal size of every agent database.

**Registered stream and command vocabulary.** `event_streams.stream_type` is text validated against the startup registry. Core registers its project, task, and run streams; timeline registers its timeline stream. Event and command kinds follow the same namespaced rule. This prevents a domain aggregate from leaking into kernel DDL while retaining validation before any mutation.

**Media as kernel citizenship.** The executor-to-asset link in `task_outputs.media_id` is portable. Attempts across domains produce exact bytes; domain meaning is layered on top. Keeping `media`, `media_locations`, and `media_relations` in the kernel avoids every agent reinventing identity, location, verification, lineage, and output ordering. Product copy may say “asset” where helpful, but the v10 table and contract names remain `media`.

These seams are sufficient for the current vision. They do not require runtime discovery, install/uninstall semantics, version negotiation across third-party code, or a universal extension API.

## 3. Generalization map

### 3.1 The kernel across agents

The following map is illustrative on the software-engineering side. It demonstrates that meaning can vary while the kernel contract remains unchanged; it does not add SWE scope to the Astrid milestone.

| Kernel part | Astrid / creative-video meaning now | Illustrative software-engineering meaning |
| --- | --- | --- |
| `schema_migrations` | Evolves core plus the timeline, shots, and references packs. | Evolves the same core plus workspace, changeset, and review packs. |
| `projects` | A film, sequence, campaign, or other creative body of work with local settings. | A bounded engineering workspace or initiative presented in the product UI as a workspace while retaining kernel project identity. |
| `event_streams` | Orders project, task, run, and timeline aggregate changes; timeline heads provide save CAS. | Orders project, task, run, and pack aggregates such as a workspace or review where independent CAS is warranted. |
| `events` | Records timeline saves, shot edits, reference changes, task lifecycle, and other meaningful mutations. | Records workspace changes, changeset revisions, review decisions, task lifecycle, and tool-observed state changes. |
| `command_receipts` | Makes saves, imports, generation, reference changes, and group operations retry-safe. | Makes edits, refactors, test launches, review submissions, and agent tool commands retry-safe. |
| `runs` | Groups a generation batch, render operation, fan-out exploration, or synchronous understanding result. | Groups a CI-style run, code search, refactor campaign, test matrix, or investigation. |
| `evidence_items` | Stores visual-quality findings, understanding summaries, warnings, or render observations. | Stores test outcomes, lint findings, review observations, benchmark results, or investigation conclusions. |
| `tasks` | Executes generation, rendering, analysis, probing, or other bounded capabilities. | Executes file edits, code generation, tests, builds, searches, or deployment checks. |
| `task_dependencies` | Orders real generation/render work or gates a task on prerequisite assets. | Expresses build/test prerequisites, edit-before-verify edges, or a matrix of independently executable checks. |
| `execution_attempts` | Fences local or provider-backed workers and prevents an expired generation attempt from materializing. | Fences coding or CI-style workers and prevents stale retries from publishing edits or results. |
| `task_outputs` | Orders generated images, videos, audio, manifests, reports, and selected primary results. | Orders patches, source files, logs, reports, binaries, screenshots, and a selected primary artifact. |
| `media` | Identifies imported footage, generated video, images, audio, prompts-as-text, logs, reports, and other exact bytes. | Identifies source files, diffs, patches, build logs, test reports, binaries, coverage data, and screenshots by exact bytes. |
| `media_locations` | Locates managed assets, explicitly referenced local footage, or remote provider results. | Locates files in a managed snapshot, an explicitly referenced checkout, or a remote artifact store without treating paths as identity. |
| `media_relations` | Expresses derivation, variants, inputs, masks, and audio relationships between exact assets. | Expresses generated-from, patch/version, input, report-for, or other lineage using the existing registered relation vocabulary where it fits; observed new semantics would be added deliberately, not speculatively. |

The important equivalences are structural, not linguistic. A generation batch and a CI-style run are both durable coordination records over direct executable tasks and evidence. A rendered clip and a patch are both exact outputs with byte identity and replaceable locations. A visual assessment and a failed-test summary are both queryable evidence. The kernel does not need to know which domain story the UI tells.

### 3.2 Existing packs and their analogues

| Pack | Astrid role | How the pattern generalizes |
| --- | --- | --- |
| **Timeline** | Owns `timelines`: an editor document plus asset registry, per-aggregate stream, and whole-document CAS. | It is an example of a document/projection pack whose aggregate needs independent concurrency. A SWE product may have an analogous editable domain document, but it should create its own pack rather than rename or stretch `timelines`. |
| **Shots** | Owns `shots` and `shot_items`: project-scoped containers with ordered exact-media placements. | The pattern “container plus ordered exact assets” can inform a changeset or review presentation. The SWE agent should use its own domain pack and vocabulary; it need not import the Astrid shot schema merely because the shape is similar. |
| **References** | Owns `project_references`, `media_references`, and `reference_links`: named entities, canonical/contextual media, roles, and typed relationships. | This may generalize as a named-entity registry. Astrid entities are characters, places, objects, and clothing; a SWE composition could describe services, modules, APIs, repositories, or components, but v10's kinds, roles, and link kinds are closed DDL vocabularies. Reuse would require a deliberate forward migration or a separately generalized pack, proven by the second composition. |

This distinction matters. Generalization does not mean forcing every domain into Astrid nouns. The timeline and shots packs prove patterns; another agent may have analogues with different invariants. The references pack is a stronger candidate for direct reuse because “named entity plus canonical exact media plus typed links” is itself cross-domain, but even that remains a hypothesis until real SWE journeys validate its vocabulary and queries.

### 3.3 Illustrative second-agent composition

An illustrative software-engineering agent would be composed as:

```text
unchanged 14-table kernel
+ workspace pack
+ changeset pack
+ review pack
```

The **workspace pack** would own software-specific context and repository/worktree semantics while using the kernel project as its isolation boundary. The **changeset pack** would group the domain meaning of proposed source changes and refer to exact source and diff media, task IDs, and events through kernel currencies. The **review pack** would own comments, decisions, and review state while attaching evidence and exact diff/report assets through the kernel.

A typical journey could be:

1. A user command creates a run and a bounded edit task under one atomic receipt.
2. A fenced attempt reads exact source media and produces exact changed-source and diff media.
3. A verification fan-out creates test and lint tasks with explicit dependencies and stable ordinals.
4. Test logs and reports become task-output media; summarized findings become evidence on the run.
5. The changeset pack projects the proposed change using `task_id` and `media_id`; the review pack records review decisions as registered events.
6. An identical retry returns the original receipt; a conflicting retry fails before mutation; a stale attempt cannot publish over the winner.

Nothing in this journey requires a new kernel column or foreign key. The pack-specific state remains in pack tables; the kernel continues to own execution, exact assets, ordered history, atomicity, and evidence. That is the generalization story in operational terms.

The sketch is deliberately not a commitment to SWE product scope, table DDL, pack APIs, or a loader. Its purpose is to test the abstraction. If a real SWE implementation needs to change a kernel table for an essentially domain-specific concept, the concept belongs in a pack. If it reveals a genuinely universal missing primitive, that should be demonstrated across at least two compositions and considered as a kernel evolution through the same migration discipline.

### 3.4 Definition of correct factoring

The factoring test is two-sided and non-negotiable:

> Delete a pack and its registration: the complete kernel suite stays green. Compose a second agent: no kernel table changes.

The first half catches upward dependencies, hardcoded vocabulary, cross-pack foreign keys, handler-local assumptions, and pack-owned writers. It does not require destructive uninstall of a live database; it tests source and composition independence. The second half catches a kernel that is merely “Astrid common code” rather than agent-agnostic infrastructure.

A pack is not correctly factored if removing it breaks core migrations, core repository tests, backup, doctor, tasks, events, receipts, runs, evidence, or media. A second agent is not correctly composed if it must add a domain column to `tasks`, a pack-specific foreign key to `events`, or a new asset table beside `media`. Conversely, not every similar-looking domain must reuse an existing pack. Creating a new pack over the unchanged kernel is a successful outcome.

## 4. Honest roadmap

The architecture needs two clocks: the product clock, which must deliver Astrid, and the platform clock, which should advance only when reuse is real. Treating them as one clock would either under-design the boundary or overbuild machinery with no second consumer. The plan therefore separates **now**, **later**, and **never/not yet**.

### 4.1 NOW: ship the Astrid-first composition

The current deliverable remains the one defined by v10 and sequenced by the sprint plan:

- one standalone, local-first Astrid product;
- one Python process owning one SQLite database and one managed-media root;
- one repository-owned semantic writer and short `BEGIN IMMEDIATE` command units;
- exactly 20 Astrid tables, derived as the 14-table kernel plus timeline (1), shots (2), and references (3);
- `core/` plus three in-tree pack directories;
- one explicit startup `register_pack()` composition;
- the existing Reigh bridge wire shape and editor safety behavior;
- exactly eight top-level product CLI families;
- fresh projects and byte-oriented `media import`, with no legacy semantic migration;
- crash, race, contention, restore, pack-conformance, and deletion-factoring proof.

The immediate architecture work is not “build a plug-in system.” It is to keep the implementation honest about ownership. Pack migrations are separate. Pack vocabularies register. Pack repositories receive the kernel unit of work. Import and FK lint prevent dependencies from pointing outward. Catalog tests derive Astrid's 20 tables from the kernel and installed manifests. The conformance kit runs against all three packs. Those choices make the future possible while being directly useful to the current product.

The execution sequence is unchanged from v10 §3, **Three-phase delivery path**, and the sprint plan. Sprint 1 builds schema, writer queue, events, receipts, registries, project and first timeline repositories, plus a thin editor save path. Sprint 2 builds executor and media foundations. Sprint 3 completes runs, evidence, references, shots, real generation/rendering, fan-out, and Phase 1 proof. Sprints 4–6 wire the editor, SDK, five domain CLI families, then `serve`, `backup`, and `doctor` and close Phase 2. Sprint 7 dogfoods failure modes. Sprint 8 proves the installed artifact and closes Phase 3. Sprints 9–10 remain conditional correctness or packaging reserve, not a place for future-platform features.

The current artifacts have distinct authority:

| Artifact | Role | What it controls |
| --- | --- | --- |
| **This master plan** | Vision | The long-range product direction, factoring model, durable principles, generalization test, and strategic questions. |
| **[Unified data model plan v10](unified-data-model-plan-v10-20260813.md)** | Normative implementation baseline | The exact 20-table Astrid schema, repository semantics, plugin laws, CLI/SDK/bridge contract, phase gates, invariants, and GA acceptance. If this document and v10 appear to differ on current behavior, v10 controls. |
| **[Astrid-first sprint plan](astrid-first-sprint-plan-20260813.md)** | Delivery sequence | The eight-sprint base forecast, dependencies, lane openings, sprint gates, team variants, and contingency policy. It sequences v10; it does not amend it. |
| **[Astrid-first megaplan North Star](../.megaplan/initiatives/astrid-first/NORTHSTAR.md), [chain](../.megaplan/initiatives/astrid-first/chain.yaml), and milestone briefs** | Executable implementation program | The ordered m1–m8 work, stop-on-failure gates, and reviewed reconciliation. It operationalizes the sprint plan without redefining the destination. |

This hierarchy protects both ambition and focus. The master plan can describe a future SWE composition without putting workspace or review work into an Astrid sprint. V10 can freeze exact DDL without pretending every future agent has 20 tables. The sprint plan can allocate engineering time without becoming an architecture referendum. The epic can execute milestones without silently widening their scope.

### 4.2 LATER: extract when a second agent is real

The trigger for the next architectural stage is not the passage of time and not an abstract desire for extensibility. It is a second agent with funded product scope, concrete domain journeys, and a team ready to consume the same kernel.

At that point, the likely sequence is:

1. Build the second composition against the existing internal boundary, initially in-tree or in the same repository if that keeps feedback fast.
2. Run the factoring test in both directions: Astrid without each pack, and the second agent without Astrid packages.
3. Record real friction: imports that cannot separate, manifest fields actually needed, product-facing naming conflicts, pack upgrade needs, and conformance gaps.
4. Extract `core/` into a shared library only after two compositions agree on the contract through use.
5. Version the shared kernel contract and conformance kit together.
6. Consider a loader only if independent release cadence, deployment, or ownership makes explicit static composition insufficient.

A loader at that stage may still be small. It could load an application-declared set of trusted packs at startup rather than discover arbitrary third-party code. Dynamic discovery, external installation, enable/disable controls, and ABI stability are separate decisions, each justified by an observed consumer. “Loader later” does not mean “marketplace eventually”; it means the implementation mechanism follows real composition needs.

The second agent also provides the first credible opportunity to revisit naming without changing the stored v10 contract casually. The shared service API could present “asset” while the schema retains `media`, or “workspace” while the kernel retains `projects`. Such aliases should be product-language adapters, not duplicate tables. A rename is justified only if both compositions show persistent conceptual harm that adapters cannot solve.

### 4.3 NEVER for the kernel—or explicitly not yet

Some concerns are real product concerns but do not belong in the reusable kernel. Others may someday exist as packs or surrounding services. They must not arrive as dormant schema now.

**No dormant platform machinery.** The kernel does not pre-allocate accounts, billing, subscription, sharing, organization, marketplace, plug-in installation, or generic policy tables. These are business and deployment domains, not prerequisites for ordered events or fenced tasks.

**No dynamic loader before a real second agent.** There is no discovery, download, enable/disable, uninstall, hot reload, third-party dependency solver, or public ABI in the Astrid milestone. Static in-tree registration is a feature, not a temporary embarrassment: it keeps composition observable while contracts are still learning.

**No accounts, billing, tenancy, sharing, or sync in the kernel.** When identity and tenancy arrive, they should live in an application shell or dedicated domain pack/service unless cross-agent evidence proves a primitive is universal. Local `projects` remain the data-isolation unit. Cloud synchronization and replication are protocols over an authority; they are not columns to sprinkle into every table.

**No remote-worker or provider platform in the kernel.** Attempt fencing is portable and remains kernel-owned. Fleet scheduling, provider accounts, remote GPU routing, deployment, and cost policy are products or packs around that primitive.

**No return of plan/step machinery.** Real ordering is expressed by direct tasks and `task_dependencies`; grouping and observation use runs and evidence. A future domain may add a domain workflow pack if it has demonstrated semantics, but it must not smuggle generic pseudo-work back into the kernel.

**No generic repair or importer framework.** `doctor` reports the checks justified by the shipped system; repair is added only for observed corruption modes and is backup-first. `media import` imports bytes, not semantic histories. Future product importers belong at product boundaries and write through normal repositories.

**No pack-specific shortcuts around authority.** A pack never earns an exception to the single-writer, receipt, event, and conformance laws because its data seems local or its UI needs speed. Caches and immutable diagnostics may be file-side; domain truth may not.

## 5. Vision principles

The following principles restate and elevate the implementation invariants in v10 §5.1, **Kept invariants**. They are intended to survive changes in language, packaging, UI, and product domain and form the durable contract of the vision.

### 5.1 A command has one atomic truth

Every meaningful mutation has one retry identity and one durable receipt. Its events, stream heads, projections, run membership, dependencies, attempts, media, outputs, associations, and result IDs commit together or do not become visible. An identical request and idempotency key returns the original result. Reusing the key for different canonical bytes fails before mutation.

This is more than an API convenience. Agents retry under uncertainty. Processes crash after performing work but before returning. Users double-submit. Without atomic receipts, every domain pack invents its own deduplication and eventually diverges. The receipt is therefore a kernel primitive and a conformance requirement for pack commands.

### 5.2 Events are the universal language of meaningful change

A task exists only for bounded executable work. Every other meaningful mutation is expressed through a registered event and its projection. This gives creative edits, review decisions, associations, cancellations, and domain state transitions a common ordered history without pretending they are jobs.

Events are ordered both within an aggregate stream and across the project. Pack vocabularies are namespaced and registered, so extension does not weaken validation. Heartbeats and narrow attempt liveness remain the deliberate exception because recording every pulse as product history would confuse operational noise with semantic change.

### 5.3 Exact bytes, not paths, are asset identity

Media identity is the SHA-256 of verified bytes within a project. Paths, URLs, names, source IDs, and registry keys are locations or aliases. They may be changed, lost, or duplicated without changing what the asset is. Task outputs, shot placements, reference associations, evidence attachments, and lineage point to exact media IDs and do not inherit silently across variants.

This principle is what makes the media model portable. Generated video and source code are different kinds of content but have the same provenance problem. A file path is not stable enough to be the answer in either domain.

### 5.4 One semantic writer per instance

All semantic mutation passes through repositories on one kernel-owned queue and transaction boundary. Bridge, CLI, SDK, executor, media import, and every pack repository are clients of that writer. A pack may own domain logic, not an authority.

The single-writer rule is architectural, not merely a SQLite optimization. It prevents file sidecars, direct pack connections, editor storage, remote services, and legacy stores from becoming competing truths. A future storage engine may change the implementation, but not the requirement that one command unit owns sequencing, validation, projection, and receipt.

### 5.5 Attempts are fenced and terminal outcomes stay terminal

Tasks are immutable executable requests. Attempts have identities and versions; a stale attempt cannot complete, cancel, fail, or materialize over a newer one. Terminal tasks do not resurrect. There is one selectable winning attempt and ordered exact outputs.

This principle applies equally to a slow renderer and a coding worker that returns after its lease expired. Generalization must not reduce execution safety to accommodate a domain runtime.

### 5.6 ULID route identity is explicit and canonical storage identity stays stable

Identity contracts must distinguish canonical storage identity from supported public addressing. In v10's current timeline bridge, UUID remains canonical timeline identity and ULID remains a supported route address. This is not a kernel-wide ULID scheme. Products may present domain-friendly names and slugs, but they do not derive durable identity from mutable paths, display names, or ordering positions.

The broader principle is that domain presentation may vary while kernel identity remains opaque, stable within its declared scope, and suitable for events and receipts. A future cross-agent identity convention must be proposed and migrated explicitly; it cannot be inferred from the current timeline route contract.

### 5.7 Trust comes from a reusable conformance kit

A pack is trusted because its commands pass the same behavioral proof as the kernel: replay, mismatch rejection, statement-boundary crash injection, same-project enforcement, writer ownership, registered vocabulary, and declared domain constraints. A manifest without conformance is packaging, not architecture.

The kit must be easy for a second agent to adopt and hard for a pack to bypass. Its failures should point to violated laws, not only implementation-specific snapshots. As the kernel becomes shared, the conformance kit and kernel contract version together.

### 5.8 Dependency direction preserves substitutability

Kernel tables and code never depend on pack tables or imports. Pack tables point inward; cross-pack exchange uses kernel currencies. Polymorphic event subjects let the kernel record a domain mutation without acquiring domain schema knowledge.

This one-way relationship is what lets a product remove, replace, or omit a pack. It also protects the kernel from becoming a catalog of every aggregate any agent might ever invent. The deletion test is the executable form of this principle.

### 5.9 Generalize from demonstrated sameness

The kernel contains semantics already shown to be portable: execution, attempts, events, receipts, grouping, evidence, exact assets, and project isolation. Similar shapes in two domains are clues, not automatic abstractions. Timeline and changeset documents may both use CAS but still deserve separate packs. References may be reusable, but the second agent must prove it.

This principle keeps the kernel small and the packs expressive. Moving a concept downward is a deliberate evolution backed by multiple compositions, not a reward for designing an elegant type hierarchy.

### 5.10 Modularity must simplify operation

The composed product remains understandable as one authority: one database, one media root, one backup, one doctor, one writer, one registered catalog. Adding a pack must not require another synchronization protocol, backup path, secrets subsystem, or transaction owner.

The architecture succeeds when different domains can compose without multiplying failure modes. If a plug-in mechanism makes recovery, observability, or consistency harder before it enables a real product, it is premature.

## 6. Open questions for the vision

These are strategic questions, not blockers for the current v10 delivery. Each should be answered when its trigger is real; the stated lean preserves a coherent direction in the meantime.

### 6.1 When does the second agent arrive, and what qualifies it as real?

**Options:** treat an internal prototype as the second consumer; require a funded roadmap and named team; or wait for an external integration request.

**Lean:** require a funded product milestone, an accountable owner, and at least two end-to-end journeys that use execution, media, events, and one domain pack. A throwaway schema sketch is useful for factoring tests but should not trigger shared-library extraction. The purpose of a second consumer is to supply constraints strong enough to distinguish reusable contract from imagined flexibility.

### 6.2 Does the kernel become a published library or only an internal contract?

**Options:** keep copied/in-tree core code per product; publish a privately versioned internal library; or offer a public package and compatibility promise.

**Lean:** extract a privately versioned shared library when the second composition is being implemented. Publish publicly only after two products have shipped on it and the manifest, repository, migration, and conformance APIs have survived independent evolution. A public contract creates support and security obligations that static source factoring does not.

### 6.3 What triggers a loader, and how dynamic should it be?

**Options:** retain explicit compile-time composition indefinitely; load an application-declared trusted pack set at startup; or support discovery and third-party install/uninstall.

**Lean:** explicit composition now. If two products need independently released packs, move first to an application-declared trusted startup set. Do not build discovery, hot loading, or third-party installation until there is a concrete distribution and ownership requirement. A shared library and a dynamic loader are separate decisions.

### 6.4 Where do identity, accounts, and tenancy live when they arrive?

**Options:** add them to the kernel; create application-shell services; or provide dedicated identity/tenancy packs that reference kernel projects.

**Lean:** keep the local kernel identity-agnostic. Put authentication and account policy in the application shell or an external service; model domain tenancy in a dedicated pack only if it must participate in local atomic commands. Preserve `projects` as the kernel isolation boundary and avoid account foreign keys throughout core tables. If hosted multi-tenancy later requires stronger partitioning, design it from observed threat and deployment models rather than dormant columns.

### 6.5 Does `media` stay in the kernel at larger scale?

**Options:** keep metadata and identity in the kernel while locations point to scalable stores; extract media into a blessed foundational service/pack; or split creative assets from software artifacts.

**Lean:** keep `media`, locations, relations, and task-output identity in the kernel. Scale bytes through location realms and external storage, not by fragmenting exact-asset truth. Reconsider only if two shipped compositions demonstrate materially different consistency, retention, or throughput requirements that cannot be served behind the existing location/repository boundary. Even then, preserve one logical exact-asset contract and atomic output registration.

### 6.6 Is “media” the permanent cross-agent term?

**Options:** retain `media` everywhere; rename schema and API to `assets`; or retain the v10 schema while allowing product/API language to say “asset.”

**Lean:** retain the table names and kernel contract from v10. Use “exact asset” in architectural explanation and let product adapters say “file” or “artifact” where natural. Consider an API-level alias after the second composition proves that “media” causes genuine developer confusion. Avoid a physical rename without substantial benefit.

### 6.7 Is the references pack reusable as-is?

**Options:** keep it Astrid-only; reuse the code with pack-supplied vocabularies; or promote a generic entity/reference primitive into the kernel.

**Lean:** keep it an Astrid pack for the current milestone and test reuse in the second agent. Its shape—named entity, canonical exact media, contextual roles, typed links—is promising for services and modules, but current kinds and relationships are creative-specific. Prefer another pack composition or a carefully generalized pack over promotion into the kernel. It should move downward only after two real domains share semantics and query needs.

### 6.8 Which pack aggregates deserve their own event stream and CAS?

**Options:** give every pack row its own stream; put all pack events on the project stream; or choose per aggregate based on concurrency and history requirements.

**Lean:** choose per aggregate. A timeline warrants its own stream because whole-document saves need independent CAS and history. Shots and references can use the project stream unless real concurrent-edit or aggregate-history requirements justify more. The registry makes extension possible; it should not encourage stream proliferation.

### 6.9 What are pack disable, upgrade, and uninstall semantics?

**Options:** support reversible install/uninstall; allow code disable while retaining tables; or treat every shipped composition as fixed and migrations as forward-only.

**Lean:** for v10, the composition is fixed, migrations are forward-only, and destructive uninstall is unsupported. A source build may omit a pack, which is what the factoring test covers. If later products need disabling, leave data in place and make availability explicit before considering table removal. Reverse migrations and dependency-aware data deletion should be built only under a real lifecycle requirement.

### 6.10 How stable is the manifest contract?

**Options:** freeze it as a public ABI now; version it as an internal interface; or treat it as source-local structure with no compatibility guarantee.

**Lean:** treat the v10 manifest as an explicit internal contract and validate it rigorously, but do not promise third-party compatibility. Version it when `core/` is extracted for the second agent. Stability should concentrate first on behavioral laws and conformance outcomes; field-level ABI commitments can follow real independent releases.

### 6.11 How do pack CLI and bridge mounts coexist with product-specific surfaces?

**Options:** make all packs top-level commands; force every product into the Astrid eight-family layout; or let each composition declare mounts under product-owned surface rules.

**Lean:** composition-owned mounts. Astrid retains exactly eight top-level product families, with shots and references nested as v10 specifies. A SWE agent may expose different top-level families without changing the kernel. The manifest declares what a pack can mount; the product composition decides where that capability appears and detects conflicts at startup.

### 6.12 When may packs depend on one another?

**Options:** prohibit dependencies entirely; allow dependencies but still forbid cross-pack table foreign keys; or permit direct pack-table coupling when declared.

**Lean:** allow manifest dependencies for registration, migration order, and service availability, while preserving kernel currencies as the only table-level exchange. If two packs repeatedly require direct relational integrity, first ask whether they are really one pack. A narrowly demonstrated exception would require an explicit architectural revision because it weakens independent composition.

### 6.13 When should the kernel itself evolve?

**Options:** freeze the 14 tables permanently; add any primitive requested by a pack; or evolve only when multiple compositions prove a common need.

**Lean:** evolve conservatively when at least two real compositions need the same semantic primitive and implementing it separately would break atomicity or interoperability. Kernel evolution remains forward-migrated and conformance-tested. A domain convenience, reporting query, or similar table shape is not enough.

## Conclusion

The long-range destination is a family of agent products that share one small, trustworthy data substrate while owning their domain meaning in packs. Astrid is the first composition and the proving ground, not a detour on the way to a platform. Its current work stays concrete: 14 kernel tables, three in-tree packs adding six tables, one SQLite authority, one writer, one Reigh bridge, one managed-media root, and the exact v10 acceptance gates.

The architectural promise is likewise concrete. Tasks execute. Meaningful change is evented. Exact assets are identified by bytes. Commands have atomic receipts. Attempts are fenced. Packs point inward, use kernel currencies, join the one writer, register their vocabularies, and carry their proof. Remove a pack and the kernel remains sound; add a second agent and the kernel tables remain unchanged.

That is enough vision to guide today's factoring and enough restraint to protect today's delivery. Build the boundary in Astrid now. Let a real second agent earn the shared library and loader later.
