# B1 candidate 46 erased-metadata custody delta verification

Model route: `codex:gpt-5.6-luna`. One independent read-only delta gate. Do not edit, commit, or push. Do not run a broad unchanged validation or a three-review panel.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Base/current HEAD: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
Frozen candidate: `.oracle/evidence/b1-candidate-46.sha256`; manifest SHA-256 `6f17c1f0adbe4620aa81a081e9a309b99b7fe412e5cad3786da4fc77dee6403e`; 30 paths. Verify every hash.
Accepted repair: `.oracle/receipts/b1-rework-46-luna.txt`.
Blocking predecessor: `.oracle/receipts/b1-review-r45-luna-3.txt`.
Unaffected passing evidence to reuse: `.oracle/receipts/b1-review-r45-luna-{1,2}.txt`, `.oracle/receipts/b1-validation-r45-luna.txt`, and `.oracle/receipts/b1-baseline-comparison-r45-luna.txt`.
User control: `/workspace/runs/astrid-canonical-pack-beta-20260831-a1/operator-message-c46.md`. This is the sole final delta gate; no candidate 47 and no whole-cycle reset.

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

## Delta criterion

Verify only erased canonical custody metadata and its direct dependency closure:

- canonical v2 records with empty `manifest_digest`, empty `trust_summary`, or both must fail closed when the active manifest has modified capabilities or arbitrary bytes;
- installed discovery and rollback must reject before root enumeration, source reads, staging, pointer/revision/store/publication or filesystem mutation;
- exact manifest-byte custody still succeeds for valid canonical records;
- legitimate inherited v1 records without canonical digest metadata still succeed;
- candidate-44 missing/alternate-manifest and valid inactive-direct rollback behavior remains green because it is directly adjacent to this fix.

Inspect the focused diff in `astrid/core/pack/store.py`, `astrid/core/pack/install_local.py`, `tests/packs/test_canonical_pack_v2.py`, and `tests/packs/test_pack_store_rollback.py`. Run only the narrow erased-metadata tests and directly adjacent lifecycle tests needed for this criterion; skip broad suites, formatters, and linters.

Return exactly:

```text
DELTA_VERDICT: PASS|BLOCKED
IDENTITY: <30-file manifest verification>
CUSTODY: <erased metadata and byte-drift disposition>
LEGACY: <valid legacy disposition>
ADJACENT: <candidate-44 direct dependency closure>
TESTS: <commands and exact results>
BLOCKERS: <none or finite list>
```
