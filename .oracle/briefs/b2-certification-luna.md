# B2 independent bounded certification

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

## Independent B2 bounded certification

Read-only. Do not edit, commit, or push. User control `babysit-b2-safe-concurrency-bounded-gates` requires one independent Luna certification by default; a blocker receives only the smallest correction and affected-criterion delta verification. No whole-cycle reset.

Frozen candidate: `.oracle/evidence/b2-candidate-1.sha256`; manifest SHA-256 `db527ea94373db32a34c67fbb0d1bcea0799d18b6253f8206ad92e1e1f2a4eb5`; 35 paths including one required deletion. Verify 34 content hashes and that `astrid/packs/builtin/pack.yaml` is absent. Base control HEAD is `c966b4b79fbca08e5bb30bc152a2b8467d0a7e74`; reviewed B1 checkpoint is `14f1f7d5f77cb6bd384749941cff6e522b696590`.

Evidence:
- `.oracle/receipts/b2-runtime-resource-audit-luna.txt`
- `.oracle/receipts/b2-customization-coverage-audit-luna.txt`
- `.oracle/receipts/b2-missing-skills-luna.txt`
- `.oracle/receipts/b2-existing-skills-census-luna.txt`
- `.oracle/receipts/b2-manifests-group-a-luna.txt`
- `.oracle/receipts/b2-manifests-group-b-luna.txt`
- `.oracle/receipts/b2-manifests-database-luna.txt`
- `.oracle/receipts/b2-integrated-closure-luna.txt`

Independently certify B2.1–B2.9 and criteria 1, 3, 5, 8, 13 in this unshipped tranche:
- exactly 22 strict v2 product manifests; builtin absent; zero aliases;
- canonical explicit-root projections retain 64 executors, 12 orchestrators, 10 elements, 8 rendering extensions, and generation 29/14/4 typed projections;
- four database declarations preserve source schema-manifest tables, vocabulary, migrations, dependencies, mounts, references semantics, defaults true/true/true/false; the four legacy files are unchanged and production remains legacy-active;
- 22 direct structured skills and deterministic `_core` routing resolve; `_core` is not a product pack;
- only five standalone Blender resources, with no overlap and owner confinement;
- offline coverage ledger has 22 rows, justified kernel owners, zero unclassified, and is not runtime-consumed;
- focused behavioral tests actually exercise the integrated contract.

Run focused checks only, including the integrated B2 test and directly relevant canonical/docs tests. Reproduce the reported `test_m7_docs` failure only if needed to confirm exact-base unrelatedness; do not broaden scope. Skip formatter, linter, and full suite.

Return exactly:
```text
VERDICT: PASS|REWORK
IDENTITY: <35-path verification and deletion>
CATALOG: <counts/aliases/builtin>
DATABASE: <four-pack semantics/defaults/isolation>
DOCS_RESOURCES: <22 skills/core census/confined closure>
COVERAGE: <zero-unclassified disposition>
VALIDATION: <commands/results and baseline disposition>
FINDINGS: <none or finite blocking defects>
```
