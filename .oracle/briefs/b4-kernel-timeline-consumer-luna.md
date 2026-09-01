# B4 consumer unit — kernel reads and timeline gateway injection

Model assignment: **normal implementation — GPT-5.6 Luna**. Repo: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; control HEAD `b918a6acbef0d443b86ed94106f5a0f103501394`. Group-1 uncommitted seam provides `StandardPackComposition` and exact catalog/registry ownership. Read B4 tasklist, accepted B4 map receipts, group-1 receipt/source. Implement only kernel read and timeline write-gateway injection. Do not commit/push, delete legacy authorities, activate strict loading, run tests, format, or lint. Attempt LSP references before exported changes; use bounded callsites if unavailable.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:
- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains per-project authority; migration SQL owns DDL.
- Reuse typed registries, ordering/checksums/drift/transactions, DatabaseWriter, UnitOfWork, repositories, SDK behavior, conformance tests.
- Trusted bundled schema only; external capability-only.
- Confined/discoverable/wheel-present resources.
- Structured docs and `_core` census routing.
- Hard cut without alternate authorities/shims.
- Proportionate beta scope.

Anti-patterns: hidden schema-pack subsystem; universal service locator; YAML DDL; project pack lifecycle/locks; external SQL; unloadable kernel; compatibility/dual reads/fallbacks; canonical bypasses.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Contract

Own `astrid/core/kernel/read.py`, `astrid/core/timeline/_edit_helpers.py`, `astrid/core/timeline/kernel_binding.py`, directly coupled gateway callers, and dedicated focused tests only. Replace `_composed_registry`/`_composed_registry_or_build` process cache or fixed builder with explicit/context-bound exact `FrozenSchemaPackRegistry` from the operation composition. `kernel_run_info`/`kernel_runs_for_project` preserve read-only opens and fail closed on incomplete migration state. `pack_write_gateway` validates canonical vocabulary using the injected registry before backend/append work and preserves writer/repository receipt ordering. Propagate registry through gateway kernel kwargs without a global service locator or independent rebuild. Preserve explicit registry injection and standalone operation ownership. Do not touch SDK/doctor/backup/rendering/inspect/CLI or shared seam files unless blocked.

Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
KERNEL_READS: <registry/read-only result>
TIMELINE_GATEWAY: <cache removal/injection/ordering result>
TESTS_NOT_RUN: <focused tests for integrated closure>
ISOLATION: <no activation/deletion>
BLOCKERS: <none or finite list>
```
