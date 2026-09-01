# B2 bounded Luna unit

Model assignment: **normal task — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Current HEAD: `c966b4b79fbca08e5bb30bc152a2b8467d0a7e74`
Reviewed B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B2, `.oracle/plan.md`, `.oracle/implementation-ledger.md`, and every nearer instruction for paths you inspect or edit. B2 is unshipped and production must remain legacy-active. Do not commit, push, delete `schema-pack.yaml`, switch active loaders, or rewire consumers. Skip formatters, linters, and project-wide test suites.

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

## Bounded research target — runtime resources

Read-only. Inventory B2.9: known typed component/rendering loaders and explicit pack-relative runtime file reads for the 22 retained product packs. Inspect the strict v2 schema/model and current pack trees. Return an exact per-pack declaration plan for `runtime_resources`, including path, purpose/kind, loader/callsite, and any justified irreducible kernel owner. Distinguish runtime resources from tests, authoring examples, migrations, and structured agent docs. Identify traversal/symlink/package-closure risks. Do not edit or run tests.

Return exactly:
```text
AUDIT: PASS|BLOCKED
PACK_RESOURCES: <22-pack concise table/list>
KERNEL_OWNERS: <justified list>
UNCLASSIFIED: <none or finite list>
MANIFEST_ACTIONS: <exact paths/fields>
BLOCKERS: <none or exact blocker>
```
