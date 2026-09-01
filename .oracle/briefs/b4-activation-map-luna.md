# B4 strict activation, inspection, doctor, and deletion map

Model assignment: **normal read-only research — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch/control HEAD: `megado/canonical-pack-beta` at `b918a6acbef0d443b86ed94106f5a0f103501394`
B3 checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`
Cumulative gate 1: PASS.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, B1 strict loader/catalog source, B2 manifests/docs, and B3 projection source. Map B4.5–B4.8 and the atomic activation/deletion boundary. Read-only: do not edit, commit, push, run tests, format, or lint. Use LSP definitions/references where available. Return a bounded implementation contract, not a broad audit or redesign.

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

## Map target

Trace:
- active runtime pack discovery/loading/validation and exact strict-v2 switch;
- package root/catalog construction and cache/lifetime concerns;
- pack inspect text/JSON current surfaces and extension points for identity, source, capabilities, database ownership/head, documentation, and resource closure;
- doctor current text/JSON/schema-health surfaces and extension points for bundled census, docs/resources, expected/applied/pending migrations without importing the offline coverage ledger;
- all four `schema-pack.yaml` files, separate schema-pack parser/identity/standard builders/exports/tests/docs, both `STANDARD_SCHEMA_PACKS` tuples, `_STANDARD_PACK_DIRS`, raw manifest rereads, v1/flat/alternate manifest admission, and compatibility-only tests that must disappear at the same activation checkpoint;
- existing focused tests for strict loader activation, inspect, doctor, no-legacy/no-dual-authority, and preserved external capability-only/database-fail-closed behavior.

Partition safe implementation write sets and dependencies relative to consumer convergence. Distinguish reusable algorithms/types that survive from obsolete schema-pack identity/parser/standard paths that are deleted. B4 must not defer alternate-authority deletion to B5. Do not broaden into packaging/docs closure reserved for B5 except tests necessary to prove B4 activation.

Return exactly:
```text
MAP: PASS|BLOCKED
ACTIVATION: <strict-v2 switch and construction seam>
INSPECT: <file:symbol/text+JSON contract>
DOCTOR: <file:symbol/text+JSON or current-format contract>
DELETE: <exact files/symbols/exports/tests/docs and retained algorithms>
WRITE_SETS: <parallel-safe groups and dependency order>
TESTS: <focused paths/scenarios, not commands run>
ATOMICITY: <how no dual authority exists before/after>
BLOCKERS: <none or finite list>
```
