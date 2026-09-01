# B1 candidate 45 independent validation

Model route: `codex:gpt-5.6-luna`. Read-only validation. Do not edit, commit, or push.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; branch `megado/canonical-pack-beta`; base/current HEAD `7ac50c12e8e4d90988fee603ffdb9896e5628792`.
Frozen manifest: `.oracle/evidence/b1-candidate-45.sha256`; SHA-256 `825cbd2e7a2b2fe4fd24594d65370a2fbfd3c3fb773a82076b71eaff5de8eca4`; 30 files. Verify every hash.
Accepted repair: `.oracle/receipts/b1-rework-45-luna.txt`. Blocking predecessors: `.oracle/receipts/b1-review-r43-luna-{1,2,3}.txt` and `.oracle/receipts/b1-review-r44-luna-{1,2,3}.txt`.

## Complete North Star

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

Enduring principles:

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

Anti-patterns:

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

## Validation

B1 covers B1.1–B1.10 and criteria 1, 2, 6, 12, and 13 in isolated roots; production remains legacy-active. Revalidate the complete strict contract/catalog/resources/docs/external-admission behavior and every prior lifecycle/custody repair.

Directly reproduce all three candidate-43 blockers: (1) installed discovery with canonical v2 bytes but paired record discriminators `1` or `1.0`; (2) rollback when the canonical active or target root lacks exact `pack.yaml` or has only an alternate manifest; (3) installed canonical manifest byte/identity drift—version, name/ID, capabilities, arbitrary bytes—while stored `manifest_digest` and metadata remain stale. Installed discovery, local/Git update and dry-run, and rollback active/target must reject record/root mismatch before external reads, enumeration where required, diff/staging, pointer/revision/store/publication mutation. Valid inherited legacy and canonical discovery/lifecycle remain green. Directly reproduce both candidate-44 blockers: a valid confined inactive direct `revisions/<pack_id>` target after timestamped rollback must succeed without weakening active-target checks; a canonical active record with empty `manifest_digest` and `trust_summary` plus missing or alternate-only exact `pack.yaml` must fail before enumeration or pointer/filesystem mutation. Reprobe every earlier malformed/contradictory metadata, strict manifest binding, pre-enumeration rollback, timestamped target, single-active publication, no fallback, relative stores, hostile metadata/path, external-database ordering, identity/provenance, and production isolation.

Run `python3 -m pytest -q tests/packs/test_git_pack_install.py tests/packs/test_pack_install.py tests/packs/test_pack_store_rollback.py tests/packs/test_pack_discovery.py tests/packs/test_pack_discovery_metadata.py tests/packs/test_canonical_pack_v2.py` plus extant B1 acceptance paths. No full suite; skip formatters/linters. A parallel independent Luna performs clean-base comparison.

Return exactly:
```text
VALIDATION: PASS|FAIL
IDENTITY: <digest and count>
TESTS: <commands/results>
PROBES: <latest repair and prior blocker coverage>
ISOLATION: <production disposition>
BLOCKERS: <none or defects>
```
