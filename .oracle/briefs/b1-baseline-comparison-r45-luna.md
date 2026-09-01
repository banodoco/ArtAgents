# B1 candidate 45 clean-base comparison

Model route: `codex:gpt-5.6-luna`. Read-only baseline comparison. Do not edit, commit, or push.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`; branch `megado/canonical-pack-beta`; exact base/current HEAD `7ac50c12e8e4d90988fee603ffdb9896e5628792`.
Frozen manifest: `.oracle/evidence/b1-candidate-45.sha256`; SHA-256 `825cbd2e7a2b2fe4fd24594d65370a2fbfd3c3fb773a82076b71eaff5de8eca4`; 30 files. Verify every hash before comparison.
Accepted repair: `.oracle/receipts/b1-rework-45-luna.txt`. Prior comparison: `.oracle/receipts/b1-baseline-comparison-r44-luna.txt`.

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

## Comparison

Verify all 30 hashes. In a temporary local Git worktree at exact base, run base and candidate for the three known failing nodes named in `.oracle/briefs/b1-baseline-comparison-r31-luna.md`. Normalize only lane paths, temporary names, and timing. Record return codes, nodes, diagnostics, and normalized signature. Verify dependencies and the Runaway manifest are identical. Any candidate-only delta is FAIL. Clean up. Do not run broad/full suites; skip formatters and linters.

Return exactly:
```text
BASELINE_PROOF: PASS|FAIL
IDENTITY: <manifest result>
BASE: <result/signature>
CANDIDATE: <result/signature>
DELTA: <none or difference>
CLEANUP: <result>
```
