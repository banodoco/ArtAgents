# B4 consumer unit — canonical inspect and projection-backed product mounts

Model assignment: **normal implementation — GPT-5.6 Luna**. Repo `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; control HEAD `b918a6acbef0d443b86ed94106f5a0f103501394`. Group-1 seam provides operation-owned catalog/registry. Read B4 tasklist, accepted maps, group-1 receipt/source. Implement B4.3 and B4.5 only: canonical inspect plus product CLI/bridge mount projection. Do not commit/push, delete/activate legacy authorities, run tests, format, or lint. Attempt LSP references before exported changes; bounded callsites if unavailable.

## Complete North Star

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles: one identity/grammar/parser/model/catalog; SQLite/migration SQL authority; reuse typed registries/migrations/writer/UoW/repositories/SDK/conformance; bundled schema only; confined packaged resources; structured docs/census; hard cut; proportionate beta.

Anti-patterns: hidden schema-pack subsystem; universal locator; YAML DDL; project pack lifecycle; external SQL; unloadable kernel; shims/dual reads/fallbacks; bypasses.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Contract

Own `astrid/core/pack/cli_inspect.py`, `_cli_shared.py` only if required, `astrid/core/cli/domain_product.py`, direct CLI wiring, and dedicated inspect/domain CLI tests. Inspect bundled/discovered canonical entries without raw manifest rereads and expose stable text/JSON identity, source/root, capability summary, database ownership/head/default, documentation, and resource closure from `CanonicalPackEntry`/projections. Preserve installed trust/status/component information where it is still real and canonical; do not keep a legacy fallback. Product family mounts derive from injected `FrozenSchemaPackRegistry.cli_mounts`, not `_STANDARD_PACK_DIRS` or `schema-pack.yaml` reads. Keep `PRODUCT_FAMILIES`, parser modules, `REQUIRED_MANIFEST_MOUNTS`, `TimelineBridgeAdapter`, and explicit typed factories. Help remains static/session-free; normal dispatch may use `client.app.registry`. Do not delete obsolete mount symbols/files yet—final activation unit does that after all consumers move—or touch other consumer groups.

Return exactly:
```text
IMPLEMENTATION: PASS|BLOCKED
CHANGED: <paths>
INSPECT: <text/JSON canonical fields result>
MOUNTS: <registry projection/static factory result>
TESTS_NOT_RUN: <focused tests for integrated closure>
ISOLATION: <no activation/deletion>
BLOCKERS: <none or finite list>
```
