# B1 Luna execution brief — isolated canonical v2 contract

Model assignment: **normal task — user-selected GPT-5.6 Luna**.

Worktree: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`

Immutable product base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`

Do not begin unless `.oracle/tasklist.md` records E0 passed and the corrected
pre-execution contract is frozen. Read `.oracle/agent_goal.md`, `.oracle/plan.md`,
and `.oracle/tasklist.md` before editing. The agent goal is the scope authority.

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

### Enduring principles

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

### Anti-patterns

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

North Star digest:
`c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Task and alignment

Implement only B1.1–B1.10. Advance one identity/grammar/parser/catalog,
confined resources, bundled-only database trust, direct hard cut, and reuse of
typed machinery. Avoid shims, dual reads, hidden schema-pack reuse, external
SQL, speculative lifecycle machinery, or activation against the bundled v1
tree.

B1 is contract/fixture work only:

1. Add strict v2 JSON Schema with integer `schema_version: 2`; canonical
   filename is exactly `pack.yaml`.
2. Add one deeply immutable canonical entry retaining identity, normalized
   definition, source/provenance/root, capabilities/extensions, optional
   database contribution, docs, and confined resource handles.
3. Use one read-normalize-validate function for the isolated catalog and B1
   static validation.
4. Reject v1, alternate filenames, missing/defaulted identity, flat legacy
   mappings, unknown fields, traversal, absolute escapes, and symlink escapes.
5. Freeze the optional database grammar: explicit `default_enabled`, ownership,
   vocabulary, repositories/conformance/static mounts, migrations, and
   dependencies expressed as pack ID plus positive minimum migration head.
   SQL remains the DDL authority.
6. Freeze structured docs and declared `runtime_resource` entries with
   owner-root confinement.
7. Add an explicit-root deterministic catalog that parses each manifest once
   and exposes narrow immutable capability/database/resource/docs projections.
8. Add golden capability-only, database-only, combined, and invalid legacy/
   path/dependency fixtures.
9. Prove positive external capability-only v2 admission across local, extra,
   environment, and installed seams. Prove otherwise-equivalent external
   database manifests reject before SQL/resource resolution.
10. Prove the active bundled runtime remains v1 and current default database
    behavior is unchanged.

## Mechanical boundaries

Expected new production files are narrowly centered on:

- `astrid/core/pack/schemas/v2/pack.json`;
- `astrid/core/pack/canonical.py`;
- `astrid/core/pack/catalog.py`; and
- exports from `astrid/core/pack/__init__.py` only if useful.

Expected tests/fixtures are centered on
`tests/packs/test_canonical_pack_v2.py` and
`tests/fixtures/canonical_pack_v2/`.

Reuse common pack validation/normalization and provenance/store primitives
where doing so does not import legacy admission semantics. The existing strict
schema-pack grammar may be read as a behavior reference but must not become a
dependency of the canonical model.

Do **not** change active behavior in:

- bundled `astrid/packs/*/pack.yaml` or any `schema-pack.yaml`;
- `astrid/core/pack/loader.py`, `discovery.py`, or `validate.py`;
- `astrid/core/schema_packs/**`;
- production installer/discovery wiring; or
- application/SDK/doctor/backup/rendering consumers.

Do not create a compatibility reader, dual loader, second service locator,
project lock, lifecycle redesign, generalized resource framework, SQL parser,
or new evidence platform. Do not commit or push; the host owns checkpoints.

## Acceptance and validation

- New focused B1 tests pass.
- Existing pack schema/discovery/install/layout/external-contract tests pass:
  `tests/packs/test_pack_yaml_schema.py`,
  `tests/packs/test_pack_discovery.py`,
  `tests/packs/test_pack_discovery_metadata.py`,
  `tests/packs/test_pack_install.py`,
  `tests/packs/test_git_pack_install.py`,
  `tests/test_external_pack_contract.py`,
  `tests/packs/test_packs_validate.py`,
  `tests/packs/test_pack_layout_contract.py`, and
  `tests/test_m2_pack_machinery.py` where those paths exist.
- The product diff contains no bundled manifest conversion, schema-pack
  deletion, consumer rewiring, or active loader switch.
- Resource and symlink escape tests are real filesystem tests.
- External database rejection is demonstrated before any declared migration or
  SQL resource is read.
- Return a concise list of changed files, tests/results, and any genuine
  blocker. Do not return a speculative redesign memo.
