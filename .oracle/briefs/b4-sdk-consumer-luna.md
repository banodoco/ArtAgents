# B4 consumer unit — SDK/client registry propagation

Model assignment: **normal implementation — GPT-5.6 Luna**. Repo: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; control HEAD `b918a6acbef0d443b86ed94106f5a0f103501394`. Group-1 seam is present but uncommitted: `StandardPackComposition` and `compose_standard_pack_database()` in canonical/application/bridge code. Read B4 tasklist, both accepted B4 map receipts, group-1 receipt, and changed seam source. Implement only SDK/client propagation. Do not commit/push, delete legacy authorities, activate strict loading, run tests, format, or lint. Before exported API changes attempt LSP references; if unavailable use bounded callsites.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:
- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains per-project authority; migration SQL owns DDL.
- Reuse typed registries, migration ordering/checksums/drift/transactions, DatabaseWriter, UnitOfWork, repositories, SDK behavior, and conformance tests.
- Trusted bundled packs may contribute schema; external packs remain capability-only.
- Pack-relative resources are confined/discoverable/wheel-present.
- Every user-facing pack ships structured docs; `_core` routes the canonical census.
- Hard cut; no alternate authorities/shims.
- Proportionate beta scope; no marketplace or variable composition lifecycle.

Anti-patterns: hidden schema-pack identity/parser/fixed lists; universal service locator; YAML DDL; pack lifecycle/project locks; external SQL; unloadable kernel; compatibility/dual reads/fallbacks; ownership/docs/resource/consumer bypass.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Contract

Modify only SDK/client consumer paths and dedicated SDK tests if needed: `astrid/sdk/invocation.py`, `astrid/sdk/client.py`, directly coupled SDK modules, and new/owned focused tests. `AstridClient` opened against a composed application must propagate the exact `app.catalog` and `app.registry` through `invoke`, `invoke_result`, `_kernel_invoke`, retries, and extended composition. Bound-root calls reuse the application's single writer/repositories/lock; standalone invocation creates exactly one short-lived `StandardPackComposition`, not a fixed/legacy builder. Preserve public SDK behavior, explicit Runaway registry composition, retries, receipts, and close semantics. Do not touch kernel/timeline/doctor/backup/rendering/inspect/CLI files or shared seam source unless a finite blocker requires it; report rather than overlap.

Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
PROPAGATION: <exact catalog/registry/writer result>
STANDALONE: <operation ownership result>
TESTS_NOT_RUN: <focused tests for integrated closure>
ISOLATION: <no activation/deletion>
BLOCKERS: <none or finite list>
```
