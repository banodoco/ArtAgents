# B4 consumer-wave integration closure

Model assignment: **normal implementation/validation — GPT-5.6 Luna**. Repository `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; control HEAD `b918a6acbef0d443b86ed94106f5a0f103501394`. The group-1 seam and six parallel consumer units are uncommitted. Read B4 tasklist, both accepted map receipts, seam receipt, and all six consumer receipts. Inspect the complete current product diff; reconcile only B4.1–B4.6 consumer integration before atomic activation. Do not commit/push, delete legacy files/symbols, or activate strict loading in this unit. Skip formatters, linters, and broad/full suites.

One known coordination issue: the backup unit edited `astrid/packs/__init__.py` despite the group-1 seam ownership boundary. Preserve intended backup registry threading but reconcile that shared file against the seam contract; do not blindly revert either accepted implementation. Verify every reported changed path exists and no consumer independently rebuilds a fixed registry.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:
- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains per-project authority; migration SQL owns DDL.
- Reuse typed registries, ordering/checksums/drift/transactions, DatabaseWriter, UnitOfWork, repositories, SDK behavior, conformance tests.
- Trusted bundled schema only; external capability-only.
- Confined/discoverable/packaged resources and structured docs/census.
- Direct hard cut, no shims/alternate authorities.
- Proportionate beta scope.

Anti-patterns: hidden schema-pack identity/parser/fixed list; universal locator; YAML DDL; project lifecycle/locks; external SQL; unloadable kernel; compatibility/dual reads/fallbacks; bypasses.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Integration contract

- One immutable operation-owned `StandardPackComposition` feeds application/bridge and exact catalog/registry identity reaches SDK, kernel/timeline, backup/restore, rendering/assets, doctor, inspect, and product mounts.
- Exactly one writer/lock per writable composition; read consumers remain read-only; no process-global registry cache or independent fixed builder.
- Default composition and explicit Runaway use the same projector; schema_migrations/drift/checksum/transaction/repository behavior remain.
- Backup/restore staging/journal/media atomicity, rendering hash/ownership, SDK retries/receipts, timeline receipt ordering, doctor text/JSON envelope, inspect canonical text/JSON, and static CLI/bridge factories remain.
- All legacy symbols/files may still exist for the next unit, but changed consumers must no longer depend on them.
- Fix actual integration/test failures only; no packaging/docs/B5 scope.

Run a bounded combined set covering the changed surfaces. Start with:
`python3 -m pytest tests/v10/test_b4_composition.py tests/sdk/test_extended_composition.py tests/v10/test_kernel_read_composition.py tests/timeline/test_edit_helpers.py tests/v10/test_backup_restore.py tests/core/rendering/test_assets.py tests/packs/rendering/test_remotion_locking.py tests/packs/runpod/test_doctor_integration.py tests/v10/test_domain_cli_surface.py tests/test_packs_cli.py`
If an exact path is absent, use the nearest mapped existing focused path and report the substitution. Do not run broad/full suites.

Return exactly:
```text
CLOSURE: PASS|BLOCKED
CHANGED: <complete reconciled product/test paths>
IDENTITY: <single catalog/registry/writer result>
CONSUMERS: <SDK/kernel/timeline/backup/rendering/doctor/inspect/CLI result>
TESTS: <commands/exact results and baseline-only classifications>
LEGACY_BOUNDARY: <all consumers moved; deletion still pending>
BLOCKERS: <none or finite list>
```
