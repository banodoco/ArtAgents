# B4 activation map replacement — return the actual contract

Model assignment: **normal read-only research — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Control HEAD: `b918a6acbef0d443b86ed94106f5a0f103501394`
B3 checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`; cumulative gate 1 PASS.

The first wrapper returned only “contract is complete” and no requested map. That output is invalid and unaccepted. Perform the read-only repository mapping now and return every required field with concrete file:symbol evidence. Do not edit, commit, push, run tests, format, or lint. Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, B1 strict loader/catalog, B2 bundled manifests, and B3 projection source. Use LSP definitions/references where available; record an unavailable operation and use bounded callsite searches if the server lacks references.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:
- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains the per-project authority. Migration SQL owns columns, constraints, indexes, and transformations; YAML does not duplicate DDL.
- Reuse typed registries, migration ordering/checksums/drift/transactions, `DatabaseWriter`, `UnitOfWork`, repositories, SDK behavior, and conformance tests.
- Bundled trusted packs may contribute database schema; external packs remain capability-only during beta.
- Every pack-relative resource is confined, discoverable, and present in the built wheel.
- Every user/agent-facing bundled pack ships structured agent documentation; `_core` exposes a generated canonical census and routes agents to owning docs.
- With no users to migrate, cut directly to final form and delete alternate authorities rather than keep shims.
- Keep beta scope proportionate; do not prebuild a marketplace or variable composition lifecycle.

Anti-patterns:
- Hiding old schema-pack identity, parser, discovery, or fixed lists behind `pack.yaml`.
- Replacing typed registries with a universal service locator.
- YAML DDL or mutable runtime facts in manifests/docs.
- Project locks/lifecycle, external SQL, unloadable kernel, shims, dual reads, schema-less fallbacks.
- Success while customization, docs, consumers, or resources bypass canonical ownership.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Required repository map

Trace and report concrete file:symbol paths for:
1. the current active runtime pack discovery/loading/validation and exact strict-v2 activation switch;
2. bundled catalog construction/lifetime without a global mutable service locator;
3. pack inspect text and JSON extension points for identity/source/capabilities/database head/docs/resources;
4. doctor current output/data model and extension points for bundled census, docs/resource health, expected/applied/pending migrations without the offline coverage ledger;
5. all four `schema-pack.yaml` files; separate schema-pack identity/parser/standard builders/exports; both `STANDARD_SCHEMA_PACKS` tuples; `_STANDARD_PACK_DIRS`; raw schema manifest rereads; v1/flat/alternate filename admission; compatibility tests/docs that must be deleted or rewritten atomically;
6. reusable collision/migration registry algorithms/types that survive after legacy identity/parser/standard deletion;
7. focused existing tests for strict activation, inspect, doctor, zero legacy/dual authority, external capability success/database rejection, and behavior preservation.

Partition exact safe write sets and dependency order relative to consumer convergence. B4 must activate strict v2 and delete all alternate authorities in the same candidate; B5 cannot inherit active legacy deletion work. Do not include B5 packaging/docs/wheel scope except tests necessary to prove B4.

A response merely asserting completion is invalid. Return exactly:
```text
MAP: PASS|BLOCKED
ACTIVATION: <strict-v2 switch and construction seam with file:symbol evidence>
INSPECT: <file:symbol and text/JSON contract>
DOCTOR: <file:symbol and current-format contract>
DELETE: <exact files/symbols/exports/tests/docs; name retained algorithms>
WRITE_SETS: <parallel-safe groups and dependency order>
TESTS: <focused paths/scenarios, no commands run>
ATOMICITY: <before legacy-only; after canonical-only proof>
BLOCKERS: <none or finite list>
```
