# B1 bounded rework 46 — canonical lifecycle custody

Model assignment: **normal task — user-selected GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Base/current HEAD: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
Rejected candidate: `.oracle/evidence/b1-candidate-45.sha256`; manifest SHA-256 `825cbd2e7a2b2fe4fd24594d65370a2fbfd3c3fb773a82076b71eaff5de8eca4`; 30 files.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B1, `.oracle/briefs/batch-b1-luna.md`, and `.oracle/receipts/b1-review-r45-luna-{1,2,3}.txt`. Read all nearer instructions for edited paths. Candidate 45 is rejected because one independent Luna review found the exact blocker below. Implement only the bounded source fix and focused regression coverage. Do not commit or push. Skip formatter, linter, and project-wide test suite.

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

## Blocking defect

1. **Erased custody metadata permits canonical byte drift.** Clearing a canonical record's `manifest_digest` and `trust_summary` lets installed discovery admit modified capabilities or arbitrary manifest bytes, and lets rollback mutate the active pointer. `_validate_installed_manifest_digest` accepts an empty digest while canonical identity checks do not bind capabilities or arbitrary bytes. Canonical records/roots must fail closed when required byte-custody metadata is absent, before discovery admission, enumeration, external reads, diff/staging, pointer/revision/store/publication mutation. Preserve valid inherited legacy records that legitimately lack canonical digest metadata. Do not infer safety from partial identity fields, add a fallback, or redesign the installed store.

## Boundaries and acceptance

- Expected source focus: `astrid/core/pack/store.py`, `astrid/core/pack/install_local.py`; touch only directly necessary lifecycle callers.
- Add focused regression tests in the existing B1/lifecycle suites for the exact erased-custody probe across discovery and rollback, including before/after pointer and filesystem mutation assertions.
- Preserve all candidate-43 blocker repairs: paired `1`/`1.0` discriminators, missing/alternate manifests, canonical manifest bytes/identity drift, local/Git update/dry-run, active and target rollback custody.
- Preserve positive legacy and canonical discovery/install/update/rollback behavior.
- Production remains legacy-active: do not convert bundled manifests, delete schema packs, or rewire consumers.
- Run the narrow new tests plus the existing candidate lifecycle-focused suites needed to prove no regression. Do not run the broad suite.
- Return exactly:

```text
REWORK: PASS|BLOCKED
CHANGED: <paths>
FIXES: <disposition of erased-custody blocker>
TESTS: <commands and exact results>
ISOLATION: <legacy-active proof>
BLOCKER: <none or exact blocker>
```
