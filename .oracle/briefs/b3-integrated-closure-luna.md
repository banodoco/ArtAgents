# B3 integrated implementation closure

Model assignment: **normal task — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch/control HEAD: `megado/canonical-pack-beta` at `6d40ddf51c1b934ab76cf34a7ff2ba9708499105`
B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
B2 checkpoint: `a293e4c416c0e716154c392c0dd43165344f870d`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B3, `.oracle/plan.md`, the B3 map receipts, `.oracle/receipts/b3-main-continuation-luna.txt`, and `.oracle/receipts/b3-runaway-fixtures-luna.txt`. Reconcile the complete six-path product candidate: `astrid/core/migrations/runner.py`, `astrid/core/pack/__init__.py`, `astrid/core/pack/canonical.py`, `astrid/core/schema_packs/registry.py`, `tests/v10/test_b3_canonical_projection.py`, and `tests/test_runaway_transitions.py`. Do not commit or push. Skip formatters, linters, and broad/full suites.

The owner found one concrete reconciliation issue: `astrid/core/pack/__init__.py` is modified but omitted from the prior changed-path receipt, and its `__all__` edit appears to have replaced the existing `ResourceProjection` export with `project_catalog_database`. Use LSP references before changing exports if the server supports them; if references are unavailable, record that and use bounded import/search evidence. Preserve the old public `ResourceProjection` export unless source evidence proves deliberate deletion. Ensure all intended new B3 exports are present exactly once. Inspect the other five paths for integration defects; make only necessary B3 corrections.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:

- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains the per-project authority. Migration SQL owns columns, constraints, indexes, and transformations; YAML does not duplicate DDL.
- Reuse the strong machinery already present: typed registries, migration ordering/checksums/drift/transactions, `DatabaseWriter`, `UnitOfWork`, repositories, SDK behavior, and conformance tests.
- Bundled trusted packs may contribute database schema; external packs remain capability-only during beta.
- Every pack-relative resource is confined, discoverable, and present in the built wheel.
- Every user/agent-facing bundled pack ships structured agent documentation; the `_core` skill exposes a generated canonical pack census and routes agents to the owning pack documentation.
- With no users to migrate, cut directly to the final form and delete alternate authorities instead of maintaining shims.
- Keep beta scope proportionate: unify today's bundled system without prebuilding a marketplace or variable project-composition lifecycle.

Anti-patterns:

- Hiding the old schema-pack subsystem inside `pack.yaml` while retaining its parser, identity, discovery, or hard-coded standard list.
- Replacing useful typed registries with a giant universal service locator.
- Duplicating SQLite DDL or mutable runtime facts in YAML or skill prose.
- Per-project pack locks, enable/disable/purge state machines, dynamic database plugins, or migration ceremony without an observed beta need.
- Allowing external packs to execute SQL.
- Making the irreducible kernel dynamically unloadable for conceptual symmetry.
- Compatibility shims, dual reads, schema-less manifests, or legacy fallbacks.
- Declaring success while any bundled customization, documentation surface, operational consumer, or packaged resource bypasses canonical ownership.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## B3 closure contract

- Explicit catalog injection projects immutable canonical database entries through existing collision/freeze machinery.
- Explicit synthetic non-unloadable `core`; no fake product pack or legacy manifest reconstruction.
- Canonical migrations retain owner root, relative identity, and confined `ResourceHandle`; execution uses handles, not pack-ID root rediscovery.
- Dependency positive minimum heads, selected availability, cycles, and core reachability fail closed.
- Default composition is manifest-derived; explicit Runaway uses the same projector.
- Preserve schema_migrations/checksum/drift/read-only/transaction/writer/UoW/repository behavior.
- Preserve production legacy builders/parser/schema manifests/fixed consumers until B4.
- Keep the deterministic Runaway temporary fixture and its observed behavior.

Run the combined focused command:
`python3 -m pytest tests/v10/test_b3_canonical_projection.py tests/v10/test_catalog_migrations.py tests/v10/test_registry.py tests/test_runaway_transitions.py`

Return exactly:
```text
CLOSURE: PASS|BLOCKED
CHANGED: <complete six-path or corrected path list>
EXPORTS: <ResourceProjection/new API result and evidence>
PROJECTION: <default/Runaway/kernel/dependency result>
MIGRATIONS: <resource/order/drift/read-only/transaction result>
RUNAWAY: <fixture/round-trip result>
TESTS: <command/exact result>
ISOLATION: <legacy-active result>
BLOCKERS: <none or finite list>
```
