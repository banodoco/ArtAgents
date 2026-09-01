# B4 candidate-2 affected-criterion delta certification

Model assignment: **independent normal reviewer — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Frozen committed checkpoint beneath the candidate: `b918a6acbef0d443b86ed94106f5a0f103501394`
Frozen candidate identity: `.oracle/evidence/b4-candidate-2.sha256`
Candidate manifest SHA-256: `dc0db8395827fa2d825d5a66249c363862594c60a0a0edbcf645e73762b02da2`
Blocking predecessor review: `.oracle/receipts/b4-certification-luna.txt`
Correction attempt record: `.oracle/receipts/b4-rework-1-attempt1-luna.txt`
Accepted activation evidence: `.oracle/receipts/b4-atomic-activation-luna.txt`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, and the three evidence files above. This is the one allowed affected-criterion delta certification. Candidate-1's unaffected passes remain valid. Do not broaden into another panel, another B1 cycle, candidate 47, B5 packaging, a full suite, or a redesign. Read and test only; do not edit, format, commit, push, dispatch another model, or touch protected workspaces.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged and closed B1. Provider exhaustion is `provider-unavailable`, never a reason for repeated dispatch.

## North Star — verbatim

Astrid has one understandable pack concept. Every bundled product extension is owned by one strict `pack.yaml`; a pack may contribute capabilities, SQLite schema, agent documentation, or any combination. `timeline`, `shots`, `references`, and `runaway` are ordinary bundled packs rather than a second schema-pack species.

Opening a pack directory should reveal one authoritative declaration of its identity, resources, custom capabilities, database ownership, migrations, events, commands, CLI surface, and agent guidance. Runtime systems consume typed projections of that declaration instead of independently rediscovering or reinterpreting the pack. Every existing bundled customization is either owned by a canonical pack or explicitly classified as irreducible kernel behavior; nothing remains unclassified.

Enduring principles:

- One pack identity, manifest grammar, parser/validator, normalized definition, and bundled catalog.
- SQLite remains the per-project authority. Migration SQL owns columns, constraints, indexes, and transformations; YAML does not duplicate DDL.
- Reuse the strong machinery already present: typed registries, migration ordering/checksums/drift/transactions, `DatabaseWriter`, `UnitOfWork`, repositories, SDK behavior, and conformance tests.
- Bundled trusted packs may contribute database schema; external packs remain capability-only during beta.
- Every pack-relative resource is confined, discoverable, and present in the built wheel.
- Every user/agent-facing bundled pack ships structured agent documentation; the `_core` skill exposes a generated canonical pack census and routes agents to the owning pack documentation.
- With no users to migrate, cut directly to the final form and delete alternate authorities instead of maintaining shims.
- Keep beta scope proportionate: unify today's bundled system without prebuilding a marketplace or variable project-composition lifecycle.

Anti-patterns:

- Hiding the old schema-pack subsystem inside `pack.yaml` while retaining its parser, identity, discovery, or hard-coded standard list.
- Replacing useful typed registries with a giant universal service locator.
- Duplicating SQLite DDL or mutable runtime facts in YAML or skill prose.
- Per-project pack locks, enable/disable/purge state machines, dynamic database plugins, or migration ceremony without an observed beta need.
- Allowing external packs to execute SQL.
- Making the irreducible kernel dynamically unloadable for conceptual symmetry.
- Compatibility shims, dual reads, schema-less manifests, or legacy fallbacks.
- Declaring success while any bundled customization, documentation surface, operational consumer, or packaged resource bypasses canonical ownership.

North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`.

## Required delta review

First verify the candidate manifest digest and all 78 listed path identities, including `DELETED` entries. A mismatch is `REWORK` and stops review.

Judge only the predecessor's six finite findings and direct dependency closure:

1. `astrid/packs/rendering/backends/remotion/run.py` never references undefined staging state; the regression reproducer proves staging/hash/ownership behavior.
2. Bound `AstridClient` capability and rendering paths, `astrid/sdk/rendering.py`, and `sdk/discovery.py` use the operation-owned canonical catalog and frozen database registry without an independent rendering-registry fallback.
3. `CanonicalPackDefinition.to_dict()` retains canonical capabilities, and agent index plus `pack inspect --agent` expose declared generation capabilities through that one serializer.
4. Non-dry-run Git update verifies checkout commit before mutation/publication while preserving canonical manifest-byte custody.
5. `astrid/core/kernel/database.py` has no active legacy database fallback. The predecessor-named tests/tools/scripts now use canonical catalog/projection fixtures and no active import/read/teaching of deleted schema-pack identity remains.
6. `examples/packs/minimal/pack.yaml` and `scripts/reshape/authority_lint.py` are in the frozen candidate and enforce strict v2 only.

Run focused tests/reproductions only for those six areas and the smallest strict-authority/composition dependency closure. Do not rerun the predecessor's 210-test activation command or any broad/full suite. Classify only finite evidence-backed blockers; “find no more issues” is not a stopping condition.

Return exactly:

```text
VERDICT: PASS|REWORK
IDENTITY: <78/78 plus manifest digest, or mismatch>
FINDINGS: <1-6 disposition>
CATALOG_REGISTRY: <single-operation ownership result>
LEGACY: <strict-v2-only result>
TESTS: <commands and exact results>
BLOCKERS: <none or finite list>
```
