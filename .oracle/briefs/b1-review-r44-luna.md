# B1 candidate 44 independent gate review

Model route: `codex:gpt-5.6-luna`. Independent read-only gate review. Do not edit, commit, or push. Return binary `PASS` or `REWORK`.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; branch `megado/canonical-pack-beta`; base/current HEAD `7ac50c12e8e4d90988fee603ffdb9896e5628792`.
Frozen candidate: `.oracle/evidence/b1-candidate-44.sha256`; manifest SHA-256 `89d404a3c9ee1214ea36d9ec0ae6774af2f67e7b87941ff823cb03ee5edfbb00`; 30 files. Verify every hash.
Accepted repair: `.oracle/receipts/b1-rework-44-luna.txt`. Blocking predecessors: `.oracle/receipts/b1-review-r43-luna-{1,2,3}.txt`.
Validation: `.oracle/receipts/b1-validation-r44-luna.txt` PASS; 30/30 hashes, 212 focused passes plus 100 subtests, 396 acceptance passes plus 244 subtests with three exact-base/environment failures, 27 lifecycle-custody passes plus 32 subtests, direct probes for all three candidate-43 blockers pass.
Baseline: `.oracle/receipts/b1-baseline-comparison-r44-luna.txt` PASS; no candidate-only delta.
Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B1, `.oracle/briefs/batch-b1-luna.md`, named receipts, frozen source/tests. Independently inspect and probe; do not accept prior verdicts on authority.

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

## Frozen goal criteria and B1 batch

B1 advances frozen criteria 1, 2, 6, 12, and 13 only in isolated roots: strict integer `schema_version: 2`; exact filename `pack.yaml`; one deeply immutable complete canonical object and one strict read-normalize-validate path; rejection of v1, alternate names, missing/defaulted identity, flat legacy, unknown fields, traversal and symlink escape; optional bundled database grammar with explicit defaults, ownership/vocabulary/repositories/conformance/static mounts/migrations and positive minimum migration heads; structured docs and confined runtime resources; deterministic explicit-root catalog with narrow immutable projections; golden capability-only/database-only/combined and invalid fixtures; positive external capability v2 admission through local/extra/environment/installed seams; external database rejection before SQL/resource resolution; production remains legacy-active. No compatibility reader, dual loader, schema-pack dependency, project lock, marketplace, or bundled activation.

## Adversarial focus

Directly reproduce all three candidate-43 blockers: (1) installed discovery with canonical v2 bytes but paired record discriminators `1` or `1.0`; (2) rollback with canonical active or target exact `pack.yaml` missing or replaced only by an alternate manifest; (3) installed canonical manifest byte/identity drift—version, name/ID, capabilities, arbitrary bytes—while stored manifest digest and metadata remain stale. Installed discovery, local/Git update and dry-run, and rollback active/target must reject every record/root mismatch before external reads, enumeration where required, diff/staging, pointer/revision/store/publication mutation. Verify valid inherited legacy and canonical discovery/lifecycle remain green. Reprobe strict manifest binding, malformed/contradictory metadata, pre-enumeration rollback, timestamped targets, single-active publication, no fallback, relative stores, hostile metadata/path, external-database ordering, identity/provenance, and production isolation. Review the full B1 contract/catalog/resource/docs/external admission, not only the latest repair. Reject weakening, scope expansion, compatibility, dual authority, or production activation.

Commands/evidence already run are in the named validation and baseline receipts. You may run focused probes/tests only; no formatter, linter, broad suite, commit, or edits.

Return exactly:
```text
VERDICT: PASS|REWORK
IDENTITY: <hash verification>
FINDINGS: <none or numbered blocking defects>
SCOPE: <B1 isolation disposition>
VALIDATION: <evidence disposition>
```
