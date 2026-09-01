# Independent B4 frozen-candidate certification

Model assignment: **independent read-only review — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
Prior reviewed checkpoints: B1 `14f1f7d5f77cb6bd384749941cff6e522b696590`; B2 `a293e4c416c0e716154c392c0dd43165344f870d`; B3 `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`.
Frozen B4 candidate: `.oracle/evidence/b4-candidate-1.sha256`, exactly 65 product/test paths.
Candidate-manifest SHA-256: `e88b14aa4133570d181ecedb58eb56d8e29c72837769937f3cae7e5dbc2d107f`.
Implementation receipts: `.oracle/receipts/b4-consumer-integration-luna.txt` and `.oracle/receipts/b4-atomic-activation-luna.txt`.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, the candidate manifest, both receipts, and the full B4 diff. Verify every candidate hash/deletion before judging. Read-only: do not edit, commit, push, start B5, dispatch another model, or run a broad/full suite. Skip formatters and linters.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged and closed B1. Do not reopen B1, launch candidate 47, or require another B1 panel. This is one bounded independent B4 certification only.

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

## Binary decision

Certify B4.1–B4.8 and goal criteria 2, 4, 7, and 9 against the frozen identity:

- one operation-owned canonical catalog/database projection reaches application, SDK, kernel/timeline, doctor, backup/restore, rendering/media, inspect, product CLI, and bridge seams;
- one lock/writer and exact registry propagation remain; read consumers remain read-only;
- strict v2 `pack.yaml` is the sole active admission path;
- all four schema manifests, fixed tuples/builders, raw rereads, separate schema-pack identity/parser/standard path, process registry cache, and compatibility fallbacks are absent;
- default core/timeline/shots/references and explicit Runaway composition preserve migration/repository/SDK/CLI semantics;
- doctor and inspect expose canonical identity/database/docs/resource state without consuming the offline coverage ledger or creating a service locator.

The implementation lane reports: 210 focused passes plus 78 subtests; 44 authority/writer/service passes; serve and doctor smokes pass. It classifies one SDK failure plus nine timeline-helper failures as the inherited unavailable `banodoco_timeline_schema`, four Runpod cases as optional skips, and two installed-artifact authority cases as B5 packaging/fixture closure. Check that classification against source/evidence. Any candidate hash mismatch, active legacy path, identity/writer split, product regression, or unjustified failure is `REWORK` with a finite affected-criterion finding. Do not use “find no more issues” as a stopping condition.

Run only the smallest commands needed to verify the frozen hashes and disputed/high-risk boundaries. Reuse the implementation results for unchanged bounded tests; do not duplicate the 210-test command unless evidence is internally inconsistent.

Return exactly:

```text
VERDICT: PASS|REWORK
IDENTITY: <65/65 hashes/deletions and manifest digest result>
CRITERIA: <B4.1-B4.8 and criteria 2/4/7/9 result>
LEGACY: <zero-active-authority result>
PRESERVATION: <writer/read-only/database/product result>
EVIDENCE: <commands and exact results/reused receipts>
FINDINGS: <none or finite blocking list with paths/symbols>
```
