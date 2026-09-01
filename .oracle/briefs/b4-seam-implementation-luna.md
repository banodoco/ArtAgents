# B4 group 1 — canonical composition seam and application/bridge ownership

Model assignment: **normal implementation — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch/control HEAD: `megado/canonical-pack-beta` at `b918a6acbef0d443b86ed94106f5a0f103501394`
B3 checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`; cumulative gate 1 PASS.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, `.oracle/receipts/b4-consumer-map-luna.txt`, `.oracle/receipts/b4-activation-map-r2-luna.txt`, and B3 projection source/tests. Implement only B4 dependency group 1: the narrow operation-owned bundled catalog/database projection seam plus application and bridge composition ownership/lifetime. Do not commit or push. Do not activate/delete legacy loaders/schema manifests/parser/standard builders yet; that final atomic deletion waits until all consumers have moved. Skip formatters, linters, and broad/full suites.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:
- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains the per-project authority. Migration SQL owns columns, constraints, indexes, and transformations; YAML does not duplicate DDL.
- Reuse typed registries, migration ordering/checksums/drift/transactions, `DatabaseWriter`, `UnitOfWork`, repositories, SDK behavior, and conformance tests.
- Bundled trusted packs may contribute database schema; external packs remain capability-only during beta.
- Every pack-relative resource is confined, discoverable, and present in the built wheel.
- Every user/agent-facing bundled pack ships structured agent documentation; `_core` exposes a generated census and routes agents to owning docs.
- Hard cut directly to final form; no alternate authorities or shims survive.
- Keep beta scope proportionate; no marketplace or variable composition lifecycle.

Anti-patterns: old schema-pack identity hidden behind canonical manifests; universal service locator; YAML DDL; project pack lifecycle/locks; external SQL; unloadable kernel; shims/dual reads/legacy fallbacks; bypassing canonical ownership/docs/resources/consumers.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Required contract

- Define the narrowest existing-pattern operation composition for `BundledCatalog.from_root(DEFAULT_PACKS_ROOT)` plus `project_catalog_database(catalog, additional_pack_ids=())`. Do not create a mutable global cache or service locator.
- `compose_standard_application()` constructs/accepts and retains one immutable catalog plus exact `FrozenSchemaPackRegistry`; explicit registry/catalog injection remains supported for focused composition and Runaway.
- `StandardApplication` owns one `DatabaseOwnerLock`, one writable `DatabaseWriter`, typed repositories/services, and the exact registry/catalog for client/consumer propagation. Shutdown and failure cleanup preserve current ordering.
- `compose_standard_bridge()` and `StandardBridgeComposition` reuse that operation pair through restore recovery, writer, services, and bridge construction without rebuilding a fixed registry.
- Preserve static typed repository/service/bridge factories and current feature semantics.
- The seam must be ready for later SDK/kernel/doctor/backup/rendering/CLI injection, but do not migrate those consumer groups in this unit.
- Before modifying exported symbols, attempt LSP references; if unavailable, use bounded callsite evidence and report it.
- Do not delete or activate alternate authorities in this unit.

Add or adapt focused application/bridge tests for exact catalog+registry identity, default core/timeline/shots/references composition, explicit Runaway injection, one lock/writer, cleanup, and no operation-local rebuild. Run only those focused tests.

Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
SEAM: <API and ownership result>
APPLICATION: <catalog/registry/writer/lock result>
BRIDGE: <composition result>
TESTS: <focused commands/exact results>
ISOLATION: <legacy deletion not yet performed>
BLOCKERS: <none or finite list>
```
