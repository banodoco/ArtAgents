# Cumulative gate 1 — B1 through B3 cutover readiness

Model assignment: **independent cumulative reviewer — user-selected GPT-5.6 Luna**.
Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Exact base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
B2 checkpoint: `a293e4c416c0e716154c392c0dd43165344f870d`
B3 checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`
Control HEAD: `2018f8a7e3be743060f9737ea1e814a0376efd3f`
North Star SHA-256: `c938f081f463bfda44a93d9215cbaa6ff08c37bf0f431cf4be95655ee2b45c6d`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B1–B4 cutover invariant, `.oracle/plan.md`, `.oracle/implementation-ledger.md`, the accepted B1 delta receipt, B2 certification receipt, B3 certification receipt, and the B1/B2/B3 candidate manifests. Review current committed source at the exact identities above. This is read-only: do not edit, commit, or push. Skip formatters, linters, and broad/full suites. Do not reopen candidate 46, launch candidate 47, or reset B1's accepted review cycle. Reuse the accepted frozen checkpoint receipts; this gate asks only whether B1–B3 together are ready for B4's atomic activation.

## Complete North Star

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

## Cumulative gate questions

1. B1 still provides one strict isolated v2 grammar/model/catalog with hard external-database rejection, confined resources/docs, immutable projections, and production legacy isolation.
2. B2 provides exactly 22 strict manifests, 64 executors, 12 orchestrators, 10 elements, four preserved database declarations/defaults, 22 skills, confined resources, and zero unclassified surfaces without activating production.
3. B3 projects those database declarations through the existing immutable collision/migration machinery with explicit kernel ownership, owner-relative handles, dependency heads, manifest-derived default/Runaway composition, and preserved schema_migrations/drift/read-only/transaction semantics.
4. B1–B3 contain no compatibility shim, active dual reader, external SQL, per-project lock/lifecycle, YAML DDL, service locator, premature schema-manifest deletion, or production consumer activation.
5. The committed state is internally consistent and ready for B4 to converge all consumers and delete alternate authorities atomically. Any blocker must be a finite evidence-backed defect in B1–B3, not a request to find more issues or widen scope.

Run only this bounded integration command if source review does not already prove REWORK:
`python3 -m pytest tests/packs/test_canonical_pack_v2.py tests/packs/test_b2_integrated_closure.py tests/v10/test_b3_canonical_projection.py`

Verdict policy: `PASS` only if B1–B3 are ready for B4; otherwise `REWORK` with a finite blocker list. Return exactly:
```text
VERDICT: PASS|REWORK
IDENTITIES: <base/B1/B2/B3/control ancestry result>
B1: <disposition>
B2: <disposition>
B3: <disposition>
CUTOVER_READINESS: <legacy-active and B4 readiness result>
TESTS: <command/exact result>
BLOCKERS: <none or finite file:line list>
```
