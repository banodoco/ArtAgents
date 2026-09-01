# B2 integrated closure unit

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

## Integrated B2 closure implementation

All prerequisite units are complete. Read these durable receipts before acting:
- `.oracle/receipts/b2-runtime-resource-audit-luna.txt`
- `.oracle/receipts/b2-customization-coverage-audit-luna.txt`
- `.oracle/receipts/b2-missing-skills-luna.txt`
- `.oracle/receipts/b2-existing-skills-census-luna.txt`
- `.oracle/receipts/b2-manifests-group-a-luna.txt`
- `.oracle/receipts/b2-manifests-group-b-luna.txt`
- `.oracle/receipts/b2-manifests-database-luna.txt`

Inspect the complete working-tree integration. You may make the smallest B2-scoped corrections across the 22 `pack.yaml` files, their `skill/**` docs, `_core/skill/**`, and focused B2 tests/evidence. Do not edit active loader/discovery/source consumers, delete `schema-pack.yaml`, or start B3 projection. Production must remain legacy-active.

Complete B2.1–B2.9 as an integrated candidate:
1. Exactly 22 retained product directories have strict v2 `pack.yaml`; `builtin` is absent; zero aliases.
2. Canonical explicit-root parsing/projection preserves exactly 64 executors, 12 orchestrators, 10 elements, eight rendering extensions, and the existing generation typed projections.
3. Four database declarations preserve exact tables/vocabulary/mounts/migrations/dependencies; timeline/shots/references default true, Runaway false; legacy schema manifests remain byte-unchanged.
4. All 22 direct `skill/SKILL.md` files validate; `_core` has deterministic sorted 22-pack routing and remains irreducible kernel guidance.
5. Declared runtime resources follow the accepted audit: only Blender has five standalone entries; content/extension/migration handles do not overlap and all resolve confined.
6. Create a lightweight final offline coverage ledger at `.oracle/evidence/b2-customization-coverage.md` with one row per pack across identity, capability/extensions, database, CLI/SDK/bridge, docs, operational surface, and runtime resources; record justified kernel owners and zero unclassified. It must be review evidence, not runtime authority.
7. Add or update focused behavioral tests following existing conventions to gate the exact B2 integrated contract. Tests must exercise canonical parsing and projections, not source-text trivia. Keep B1 isolated and existing behavior intact.

Run focused B2 pack/docs/resource/catalog checks only. Classify any existing environment failure against accepted baseline evidence; do not run the full suite, formatter, or linter. Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
CATALOG: <22/counts/aliases/builtin result>
DATABASE: <four declarations/defaults/semantics result>
DOCS: <22 skills/core census result>
RESOURCES: <confined closure result>
COVERAGE: <zero-unclassified ledger result>
TESTS: <commands/exact results>
ISOLATION: <legacy-active/schema-manifest result>
BLOCKERS: <none or finite list>
```
