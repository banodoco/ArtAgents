# B3 canonical database projection implementation

Model assignment: **normal task — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Current HEAD: `6d40ddf51c1b934ab76cf34a7ff2ba9708499105`
B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
B2 checkpoint: `a293e4c416c0e716154c392c0dd43165344f870d`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B3, `.oracle/plan.md`, `.oracle/implementation-ledger.md`, and nearer instructions. B3 continues the unshipped tranche. Production legacy builders and active authority remain until B4. Do not commit, push, delete schema manifests/parser/standard builders, rewire operational consumers, or activate v2. Skip formatters, linters, and broad/full suites.

## Complete North Star

# North Star — one canonical Astrid pack

Astrid has one understandable pack concept. Every bundled product extension is
owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite
schema, agent documentation, or any combination. `timeline`, `shots`,
`references`, and `runaway` are ordinary bundled packs rather than a second
schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its
identity, resources, custom capabilities, database ownership, migrations,
events, commands, CLI surface, and agent guidance. Runtime systems consume
typed projections of that declaration instead of independently rediscovering
or reinterpreting the pack. Every existing bundled customization is either
owned by a canonical pack or explicitly classified as irreducible kernel
behavior; nothing remains unclassified.

## Enduring principles

- One pack identity, manifest grammar, parser/validator, normalized definition,
  and bundled catalog.
- SQLite remains the per-project authority. Migration SQL owns columns,
  constraints, indexes, and transformations; YAML does not duplicate DDL.
- Reuse the strong machinery already present: typed registries, migration
  ordering/checksums/drift/transactions, `DatabaseWriter`, `UnitOfWork`,
  repositories, SDK behavior, and conformance tests.
- Bundled trusted packs may contribute database schema; external packs remain
  capability-only during beta.
- Every pack-relative resource is confined, discoverable, and present in the
  built wheel.
- Every user/agent-facing bundled pack ships structured agent documentation;
  the `_core` skill exposes a generated canonical pack census and routes agents
  to the owning pack documentation.
- With no users to migrate, cut directly to the final form and delete alternate
  authorities instead of maintaining shims.
- Keep beta scope proportionate: unify today's bundled system without
  prebuilding a marketplace or variable project-composition lifecycle.

## Anti-patterns

- Hiding the old schema-pack subsystem inside `pack.yaml` while retaining its
  parser, identity, discovery, or hard-coded standard list.
- Replacing useful typed registries with a giant universal service locator.
- Duplicating SQLite DDL or mutable runtime facts in YAML or skill prose.
- Per-project pack locks, enable/disable/purge state machines, dynamic database
  plugins, or migration ceremony without an observed beta need.
- Allowing external packs to execute SQL.
- Making the irreducible kernel dynamically unloadable for conceptual symmetry.
- Compatibility shims, dual reads, schema-less manifests, or legacy fallbacks.
- Declaring success while any bundled customization, documentation surface,
  operational consumer, or packaged resource bypasses canonical ownership.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

User control `babysit-b2-safe-concurrency-bounded-gates` applies: independent safe work stays concurrent; dependencies and mutation conflicts wait; one Luna certification by default; smallest correction plus affected-criterion delta on blockers; no equivalent whole-cycle reset; final Sol integrated review remains.

## B3 main source and behavioral implementation

Read `.oracle/receipts/b3-architecture-map-luna.txt` and `.oracle/receipts/b3-validation-map-luna.txt`. Implement B3.1–B3.8 except the separately assigned Runaway historical-test file. Before changing exported symbols, use the language server for references. Own B3 source under `astrid/core/pack/canonical.py`, the surviving `astrid/core/schema_packs/**` algorithms/adapters, event/kernel projection paths, migration runner/order descriptors, and focused B3 tests under `tests/v10/**` or a new focused pack test. Do not edit `tests/test_runaway_transitions.py`; another disjoint unit owns it.

Required contract:
- immutable canonical database projections feed existing collision/freeze machinery by explicit `project_catalog_database(catalog, additional_pack_ids=()) -> FrozenSchemaPackRegistry` or the narrowest equivalent consistent with current types;
- synthetic reserved non-unloadable `core` kernel projection is explicit code, not a product pack or legacy manifest reconstruction;
- canonical registered migrations carry pack, owner root, relative identity, and confined `ResourceHandle`; canonical bytes load only from the handle, never `astrid/packs/<id>` rediscovery;
- dependency positive minimum heads are enforced against selected dependency available heads, with missing/self/duplicate/cycle/core-reachability rejection;
- default composition derives from `default_enabled` and explicit Runaway uses the same projector;
- `schema_migrations`, ordering, exact-byte checksum/name/too-new drift, read-only behavior, one transaction per migration, writer/UoW/repository/conformance remain unchanged;
- focused fresh-schema assertions prove each migration affects only declared owned tables; no generalized SQL observer.

Production legacy builders, parser, schema manifests, fixed standard paths, and operational consumers remain untouched and active until B4. Keep legacy adapters only for current production; do not make them the canonical projection path. Do not add project locks, lifecycle, external SQL, YAML DDL, down migrations, or service locator.

Run focused B3 registry/migration/canonical tests only. Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
PROJECTION: <catalog/kernel/default/Runaway result>
MIGRATIONS: <owner handles/head/order/drift/transaction result>
TABLES: <focused ownership result>
TESTS: <commands/exact results>
ISOLATION: <legacy-active result>
BLOCKERS: <none or finite list>
```
