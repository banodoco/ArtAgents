# B4 atomic strict-v2 activation

Model assignment: **normal implementation/validation — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Control branch: `megado/canonical-pack-beta`
Immutable product base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`

This is a continuation, not a new activation attempt. The first exact-Luna
wrapper reached its 1800-second deadline after changing the activation paths
and returned no final receipt. Preserve and inspect every current edit and
deletion; finish or repair that exact candidate. Do not restart from HEAD or
discard another worker's changes.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, `.oracle/receipts/b4-activation-map-r2-luna.txt`, and the completed `.oracle/receipts/b4-consumer-integration-luna.txt`. Inspect the complete current B4 diff. The consumer-integration closure is a prerequisite: if its durable receipt is absent or not `CLOSURE: PASS`, stop with `ACTIVATION: BLOCKED` without editing. Do not commit, push, start B5, run the full suite, or touch protected workspaces. Skip formatters, linters, and project-wide tests.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged and closed B1. Do not launch, recreate, or discuss candidate 47 or any B1 review cycle. This unit is only B4.7–B4.8 atomic activation and its bounded dependency closure.

## North Star — embed verbatim

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

## Atomic change

Complete B4.7–B4.8 as one candidate. Reuse the consumer convergence already present; fix only activation-caused integration defects.

1. Switch all production pack admission/discovery/install/validation paths to exactly one strict v2 `pack.yaml` canonical path. Remove v1/flat/alternate-filename loading and compatibility fallback while retaining tests that prove those forms fail closed.
2. Delete the four bundled `schema-pack.yaml` files. Their canonical `pack.yaml` database declarations and migration SQL already exist and must remain authoritative.
3. Delete both `STANDARD_SCHEMA_PACKS` tuples, `_STANDARD_PACK_DIRS`, raw schema-manifest rereads, separate schema-pack manifest/parser/standard identity path, pack-level legacy builder/registration exports, legacy core `SchemaPackManifest` construction, and the registry migration-resource fallback. Retain and relocate only reusable typed collision/freeze/migration algorithms needed by canonical projections.
4. Ensure every B4 consumer imports only canonical catalog/projection/registry interfaces. No active raw manifest reread, fixed standard builder, process-global registry cache, dual reader, compatibility alias, or independent identity reconstruction may survive.
5. Preserve the explicit kernel database/vocabulary projection, `schema_migrations` authority, migration ordering/checksums/drift/transactions, one writer/lock, repositories/UoW, SDK retries/receipts, read-only probes, doctor/inspect envelopes, backup/restore atomicity, rendering ownership/hashes, and static typed CLI/bridge factories.
6. Rewrite or delete only tests/docs that actively enforce the removed authority and are required for B4 bounded closure. Do not perform B5 package-data, wheel, broad docs, final matrix, or full-suite work.

Use symbol-aware LSP references before deleting exported symbols when the server supports it. If the configured server returns method-not-supported, record that and use bounded repository callsite searches.

## Bounded verification

Run the smallest integrated set that proves strict admission, canonical projection, four data-pack semantics, consumer convergence, and zero legacy authority. It must include available focused tests covering:

- `tests/packs/test_canonical_pack_v2.py`
- `tests/v10/test_b3_canonical_projection.py`
- `tests/v10/test_catalog_migrations.py`
- `tests/v10/test_b4_composition.py`
- `tests/sdk/test_extended_composition.py`
- `tests/v10/test_kernel_read_composition.py`
- `tests/timeline/test_edit_helpers.py`
- `tests/v10/test_backup_restore.py`
- `tests/core/rendering/test_assets.py`
- `tests/packs/runpod/test_doctor_integration.py`
- `tests/v10/test_domain_cli_surface.py`
- `tests/test_packs_cli.py`
- zero-authority/structure tests under `tests/v10/`.

If an exact path is absent, substitute the nearest existing focused test and report it. Do not run the broad/full authoritative suite.

Return exactly:

```text
ACTIVATION: PASS|BLOCKED
CHANGED: <complete product/test/doc paths, including deletions>
STRICT_AUTHORITY: <one v2 admission/catalog/projection result; legacy absence>
CONSUMERS: <application/SDK/kernel/timeline/backup/rendering/doctor/inspect/CLI result>
PRESERVED: <database/product/operational invariants>
TESTS: <commands and exact results>
BLOCKERS: <none or finite list>
```
