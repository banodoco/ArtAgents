# Cumulative gate 2 — B1 through B4

Model assignment: **independent normal integrated reviewer — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Exact base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
B1 product checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`
B2 product checkpoint: `a293e4c416c0e716154c392c0dd43165344f870d`
B3 product checkpoint: `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`
B4 product checkpoint: `81a64d64bd0ac0a920ceec69d75dd4ce9bbd1785`
Current control-record HEAD: `256f88eac959d5722737c647247eebff029139dd`
B4 frozen candidate: `.oracle/evidence/b4-candidate-3.sha256`
B4 candidate manifest SHA-256: `2e90aee2dd383f7eb4913a5cfd546b042221c89110a43f03b2e8e2d8d3c764d3`
Accepted B4 delta: `.oracle/receipts/b4-delta-2-certification-luna.txt`

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` through B4, `.oracle/implementation-ledger.md`, `.oracle/plan.md`, the B1–B4 candidate evidence, cumulative-gate-1 receipt, and accepted B4 receipts. This is the single bounded cumulative integration gate before B5, not a new segment panel. Read/test only. Do not edit, format, commit, push, dispatch another model, start B5, run the full suite, rerun every segment command, or touch protected workspaces.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged and B1 remains closed. Reuse accepted B1–B4 identities and receipts; no candidate 47, broad unchanged validation, or review reset.

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

## Gate questions

1. Verify linear ancestry base → B1 → B2 → B3 → B4 → control HEAD and match accepted candidate/checkpoint identities.
2. Confirm production admits exactly 22 strict-v2 bundled packs through one parsed catalog and one frozen database projection; no v1/flat/alternate loader or bundled schema-pack authority is active.
3. Confirm default core/timeline/shots/references composition and explicit Runaway composition derive from canonical manifests through existing migration/checksum/drift/transaction machinery.
4. Confirm application, SDK, kernel/timeline, doctor, backup/restore, rendering/media, inspect, and CLI/bridge seams use operation-owned typed projections without a universal service locator or independent standard builder.
5. Confirm external capability-only admission remains positive and external database declarations fail before SQL/resource resolution.
6. Confirm B4 left B5 with a finite closure task: packaging/docs/source-wheel/full-suite/evidence, not unresolved activation or dual authority.

Run one bounded integration command centered on canonical parsing/catalog, B3 projection/migrations, B4 composition/authority, application/kernel/SDK propagation, inspect/doctor, and external trust. Keep it proportionate; do not run wheel build or full suite. Record exact results and finite blockers only.

Return exactly:

```text
VERDICT: PASS|REWORK
ANCESTRY: <exact result>
AUTHORITY: <strict-v2-only result>
COMPOSITION: <default and Runaway result>
CONSUMERS: <operation-owned projection result>
EXTERNAL: <capability success/database rejection result>
TESTS: <command and exact result>
B5_READY: yes|no
BLOCKERS: <none or finite list>
```
