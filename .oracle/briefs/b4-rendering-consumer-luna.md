# B4 consumer unit — rendering/managed-media projection injection

Model assignment: **normal implementation — GPT-5.6 Luna**. Repo `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; control HEAD `b918a6acbef0d443b86ed94106f5a0f103501394`. Group-1 seam provides operation-owned catalog/registry. Read B4 tasklist, accepted maps, group-1 receipt/source. Implement only rendering/assets and managed-media registry propagation. Do not commit/push, delete/activate legacy authorities, run tests, format, or lint. Attempt LSP references before exported changes; bounded callsites if unavailable.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles: one identity/grammar/parser/model/catalog; SQLite/migration SQL authority; reuse typed registries/migrations/writer/UoW/repositories/SDK/conformance; bundled schema only; confined packaged resources; structured docs/census; hard cut; proportionate beta.

Anti-patterns: hidden schema-pack subsystem; universal locator; YAML DDL; project pack lifecycle; external SQL; unloadable kernel; shims/dual reads/fallbacks; bypasses.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Contract

Own `astrid/core/rendering/assets.py`, direct rendering/materializer operation boundaries and backend propagation, and dedicated focused tests only. `_owned_managed_locators` and `AssetMaterializer` receive the exact operation registry/catalog projection; managed-media DB reads remain read-only and reject incomplete/drifted schema. Carry that registry through Remotion/render boundaries without fixed standard builders or global cache. Preserve project ownership, exact hash/byte validation, managed snapshot behavior, resolver semantics, and no second writer. Do not touch SDK/kernel/timeline/doctor/backup/inspect/CLI/shared seam files unless blocked.

Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
MATERIALIZER: <registry propagation result>
READS: <read-only/ownership/hash result>
TESTS_NOT_RUN: <focused tests for integrated closure>
ISOLATION: <no activation/deletion>
BLOCKERS: <none or finite list>
```
