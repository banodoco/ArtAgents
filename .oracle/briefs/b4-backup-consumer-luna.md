# B4 consumer unit — backup/restore projection injection

Model assignment: **normal implementation — GPT-5.6 Luna**. Repo `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; control HEAD `b918a6acbef0d443b86ed94106f5a0f103501394`. Group-1 seam provides operation-owned catalog/registry. Read B4 tasklist, accepted map receipts, group-1 receipt/source. Implement only backup/restore projection threading. Do not commit/push, delete/activate legacy authorities, run tests, format, or lint. Attempt LSP references before exported changes; bounded callsites if unavailable.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles: one identity/grammar/parser/model/catalog; SQLite and migration SQL authority; reuse typed registries/migrations/writer/UoW/repositories/SDK/conformance; bundled schema only and external capability-only; confined packaged resources; structured docs/census; hard cut without shims; proportionate beta.

Anti-patterns: hidden schema-pack parser/identity/fixed list; universal locator; YAML DDL; project pack lifecycle/locks; external SQL; unloadable kernel; dual reads/fallbacks; canonical bypasses.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Contract

Own `astrid/core/backup/operations.py`, directly coupled backup/restore data types/callers, and dedicated focused tests only. Thread the exact operation `FrozenSchemaPackRegistry` through `_validate_staged_database`, `_restore_new_state`, `_recover_restore_transaction`, `recover_restore_staging`, and `restore_backup`; remove independent fixed standard-builder calls from this path. Preserve staged validation, read-only quick/FK/migration probes, external-media custody/rebase, journal recovery, crash cleanup, overwrite protection, lock ordering, byte preservation, and atomic publication. Public callers without injected composition may create exactly one short-lived canonical standard composition, not rebuild through legacy lists. Do not touch SDK/kernel/timeline/doctor/rendering/inspect/CLI/shared seam files unless blocked.

Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
REGISTRY: <threading/fallback ownership result>
RESTORE: <staging/recovery/atomicity preservation>
TESTS_NOT_RUN: <focused tests for integrated closure>
ISOLATION: <no activation/deletion>
BLOCKERS: <none or finite list>
```
