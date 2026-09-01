# B4 candidate-2 finite stale-test correction

Model assignment: **normal implementation/validation — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Committed checkpoint beneath candidate: `b918a6acbef0d443b86ed94106f5a0f103501394`
Frozen candidate 2: `.oracle/evidence/b4-candidate-2.sha256`
Candidate manifest SHA-256: `dc0db8395827fa2d825d5a66249c363862594c60a0a0edbcf645e73762b02da2`
Blocking delta receipt: `.oracle/receipts/b4-delta-certification-luna.txt`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, and the blocking receipt. Correct exactly its three finite finding-5 blocker groups and direct fixture closure. Preserve findings 1, 2, 3, 4, and 6 and all unaffected candidate-1/candidate-2 passes. Do not restart B4, alter production behavior unless a focused reproducer proves a product bug, commit, push, start B5, run a broad/full suite, dispatch another model, or touch protected workspaces. Skip formatters and linters.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged and B1 remains closed. Do not create candidate 47 or run a review panel.

## North Star — verbatim

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

## Finite corrections

1. Update `tests/v10/test_kernel_read_composition.py::test_kernel_reads_accept_standard_pack_migrations` so its too-new migration is inserted into the canonical project database authority at `.astrid/astrid.sqlite3`, preserving the observable `MigrationTooNewError` contract.
2. Remove or migrate active legacy contracts in `tests/v10/test_standard_application.py` and `tests/v10/test_pack_factoring.py` to the canonical bundled catalog/database projection. Delete compatibility-only assertions only where the deleted schema-pack authority has no canonical contract; preserve application/registry/writer/repository behavior tests.
3. Remove or convert `tests/packs/test_b2_integrated_closure.py::test_v2_database_projection_matches_retained_schema_manifests` so it proves the same ownership/vocabulary/migration projection from canonical `pack.yaml` without opening deleted `schema-pack.yaml` files.

Use LSP references before exported-symbol changes if a server supports them. Expected edits are tests/fixtures only. If a production defect is proven, stop with the finite reproducer rather than silently widening scope.

## Verification

Run only the named tests/files and their smallest canonical projection/strict-authority dependency closure. Confirm no active test imports deleted `astrid.core.schema_packs.manifest` or `standard`, and no test opens a bundled `schema-pack.yaml`. Do not rerun the 210-test activation command, the candidate-2 delta command, or any full suite.

Return exactly:

```text
REWORK: PASS|BLOCKED
CHANGED: <complete paths>
BLOCKERS_1_3: <each result>
STRICT_AUTHORITY: <zero stale imports/reads result>
TESTS: <commands and exact results>
BLOCKERS: <none or finite list>
```
