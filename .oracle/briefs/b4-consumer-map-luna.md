# B4 operational-consumer convergence map

Model assignment: **normal read-only research — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch/control HEAD: `megado/canonical-pack-beta` at `b918a6acbef0d443b86ed94106f5a0f103501394`
B3 checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`
Cumulative gate 1: PASS.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, and B3 projection source/tests. Map B4.1–B4.4 and the direct CLI mount reader. Read-only: do not edit, commit, push, run tests, format, or lint. Use LSP definitions/references where available. Return an implementation contract, not a redesign.

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

Trace the top-level bundled catalog/database projection seam and every callsite/build path in:
- `astrid/application.py`
- `astrid/sdk/invocation.py` and client propagation
- `astrid/core/kernel/read.py`
- `astrid/core/timeline/_edit_helpers.py`
- `astrid/core/doctor.py`
- `astrid/core/backup/operations.py` and restore path
- `astrid/core/rendering/assets.py` and managed media reads
- `astrid/core/cli/domain_product.py` static CLI/bridge mounts

Identify both `STANDARD_SCHEMA_PACKS` authorities and `_STANDARD_PACK_DIRS`/raw manifest rereads. Determine the narrow injected catalog/projection API, ownership/lifetime, optional explicit Runaway composition, and how to preserve one writer/lock, SDK registry propagation, read-only, backup/restore, repository/service/CLI factories. Partition safe implementation write sets and dependency order; note exported symbols requiring LSP references. Identify focused existing tests for each consumer and integrated behavior. Do not propose a service locator or dynamic factories.

Return exactly:
```text
MAP: PASS|BLOCKED
SEAM: <top-level catalog/projection construction and injection contract>
CONSUMERS: <file:symbol -> required change>
CLI_BRIDGE: <static mount convergence>
PRESERVED: <writer/lock/SDK/read-only/backup semantics>
WRITE_SETS: <parallel-safe groups and dependencies>
TESTS: <focused paths/scenarios, not commands run>
DELETIONS_LATER: <fixed authorities/raw rereads this map proves removable at atomic activation>
BLOCKERS: <none or finite list>
```
