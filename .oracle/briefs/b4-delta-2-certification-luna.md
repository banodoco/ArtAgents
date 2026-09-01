# B4 candidate-3 finding-5 delta certification

Model assignment: **independent normal reviewer — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
B4 base checkpoint: `b918a6acbef0d443b86ed94106f5a0f103501394`
Correction commit preserved in candidate: `f352422d`
Frozen complete B4 candidate: `.oracle/evidence/b4-candidate-3.sha256`
Candidate manifest SHA-256: `2e90aee2dd383f7eb4913a5cfd546b042221c89110a43f03b2e8e2d8d3c764d3`
Blocking predecessor: `.oracle/receipts/b4-delta-certification-luna.txt`
Correction receipt: `.oracle/receipts/b4-rework-2-luna.txt`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, and both receipts. This is one independent delta certification of only predecessor finding 5 after its finite correction. Findings 1, 2, 3, 4, and 6 retain their candidate-2 passes. Read/test only: do not edit, format, commit, push, dispatch another model, start B5, touch protected workspaces, rerun the 210-test activation command, or run any broad/full suite.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged; B1 remains closed. No candidate 47 or review panel.

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

## Required review

First verify the candidate-manifest digest and all 81 path identities, including deleted entries. A mismatch is `REWORK` and stops review.

Then judge only finding 5 and its four corrected test paths:

- `tests/v10/test_kernel_read_composition.py::test_kernel_reads_accept_standard_pack_migrations` writes the too-new row into canonical `.astrid/astrid.sqlite3` and still observes `MigrationTooNewError`.
- `tests/v10/test_standard_application.py` and `tests/v10/test_pack_factoring.py` contain no active deleted schema-pack tuple/parser/file contract while preserving canonical application/catalog/registry/writer/repository behavior.
- `tests/packs/test_b2_integrated_closure.py::test_v2_database_projection_matches_retained_schema_manifests` proves projection from canonical `pack.yaml` without reading deleted manifests.
- No active test imports deleted `astrid.core.schema_packs.manifest` or `.standard`, or opens a bundled `schema-pack.yaml`.

Run the four corrected files and only the smallest B3 projection/authority-lint dependency closure. Do not repeat unaffected candidate-2 checks.

Return exactly:

```text
VERDICT: PASS|REWORK
IDENTITY: <81/81 plus manifest digest, or mismatch>
FINDING_5: <three blocker dispositions>
STRICT_AUTHORITY: <zero stale import/read result>
TESTS: <commands and exact results>
BLOCKERS: <none or finite list>
```
