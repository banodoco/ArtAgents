# Independent B3 frozen-candidate certification

Model assignment: **independent reviewer — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch/control HEAD: `megado/canonical-pack-beta` at `6d40ddf51c1b934ab76cf34a7ff2ba9708499105`
B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
B2 checkpoint: `a293e4c416c0e716154c392c0dd43165344f870d`
Frozen candidate identity: `.oracle/evidence/b3-candidate-1.sha256`
Frozen manifest SHA-256: `8f2140a6a79f3f591c04385f72bf3cd8ba7eedf299011ecf9ea7360d17a6f087`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B3, `.oracle/plan.md`, all B3 map/implementation/closure receipts, and the six frozen candidate files. This is a read-only independent certification: do not edit, commit, or push. Skip formatters, linters, and broad/full suites. First verify all six hashes and the manifest hash. If identity differs, return REWORK immediately.

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

## B3 criteria and evidence to certify

- B3.1 canonical database declarations enter existing immutable collision/freeze machinery through explicit injection; production legacy builders remain.
- B3.2 explicit reserved irreducible kernel database/vocabulary projection, not a product pack or legacy manifest reconstruction.
- B3.3 every canonical migration carries owner, root, relative identity, and confined `ResourceHandle`; canonical execution never rebuilds `astrid/packs/<id>`.
- B3.4 positive minimum dependency heads and selected availability/cycles/core reachability fail closed.
- B3.5 defaults derive only from manifest `default_enabled`; explicit Runaway uses the same projector.
- B3.6 schema_migrations, ordering/checksum/drift/read-only/transaction/writer/UoW/repository semantics remain.
- B3.7 exact fresh-schema table ownership assertions; no generalized SQL observer.
- B3.8 fresh/reopen/Runaway/read-only/dependency/collision/drift/rollback scenarios.
- B3.9 deterministic temporary Runaway project replaces the absent demo without packaging it.
- `ResourceProjection` and all intended new exports remain available.
- Production stays legacy-active until B4; no consumer activation or schema-manifest deletion.

Run only the bounded command if source review does not already reveal REWORK:
`python3 -m pytest tests/v10/test_b3_canonical_projection.py tests/v10/test_catalog_migrations.py tests/v10/test_registry.py tests/test_runaway_transitions.py`

Verdict policy: any concrete defect against the frozen B3 criteria is `REWORK`; otherwise `PASS`. Return exactly:
```text
VERDICT: PASS|REWORK
IDENTITY: <manifest and 6/6 hashes>
CRITERIA: <B3.1-B3.9 disposition>
TESTS: <command/exact result>
ISOLATION: <legacy-active result>
FINDINGS: <none or finite blocking list with file:line evidence>
```
