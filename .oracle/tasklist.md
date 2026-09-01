# Canonical pack beta — authoritative execution tasklist

Status: **frozen for execution; E0 cloud preflight passed**

Authorities: `.oracle/agent_goal.md`, `.oracle/northstar.md`, and
`.oracle/implementation-ledger.md`.

This is the single remaining-work list for the canonical-pack goal created in
this conversation. It replaces unrelated storyboard residue and the overgrown
historical plan. A checked item means this worktree contains direct evidence;
**REUSE** means working base functionality to preserve, not progress delivered
by this run.

## Megado execution controls

- This is a **huge run** because the best estimate is 4–6 engineer-weeks.
- Every B1–B5 implementation task is classified **normal**, assigned to the
  user-selected GPT-5.6 Luna. No task currently satisfies the exceptional
  `[XHARD]` threshold. GPT-5.6 Sol owns oracle adjudication and any future
  exceptional task only after a written threshold finding.
- Each batch inherits the criteria and North Star alignment stated at its
  heading. Each execution brief embeds the complete North Star and digest.
- After each implementation candidate, freeze its artifact/diff identities and
  obtain three independent Luna verdicts. Any `REWORK` blocks progress. After
  Luna converges on `PASS`, obtain one Sol oracle disposition, then commit the
  reviewed batch as its checkpoint. No dependent work consumes an unpassed
  checkpoint.
- B2 and B3 checkpoints remain unshipped and legacy-active. They do not create
  an active dual reader; B4 is the only activation checkpoint.
- Huge-run cumulative gate 1 occurs after passed B3 and before B4 activation.
  It reviews B1–B3 together for contract, manifest, database-projection, and
  cutover readiness.
- Huge-run cumulative gate 2 occurs after passed B4 and before B5. It reviews
  B1–B4 together for the integrated hard cut and absence of dual authority.
- B5 routine/final review remains separate. Only its final passed checkpoint
  may be pushed; no checkpoint is merged, deployed, promoted, or released.

## P0 — project control and evidence baseline

- [x] P0.1 Prepare the canonical-pack packet in the dirty source checkout
  without changing product files.
- [x] P0.2 Create the isolated worktree and `megado/canonical-pack-beta` branch
  from exact base `7ac50c12`.
- [x] P0.3 Freeze the North Star and 15-criterion goal.
- [x] P0.4 Complete ten accepted Luna repository-exploration areas.
- [x] P0.5 Complete Sol planning/revision/stability work through revision 9.
- [x] P0.6 Complete seven three-Luna settled-plan waves and adjudicate the
  non-clean Wave 7 findings into the reduced beta scope.
- [x] P0.7 Verify zero product diff and the inherited behavior floor, including
  a 179-test focused substrate pass.
- [x] P0.8 Reconstruct the actual conversation/worktree history and create the
  implementation ledger and this tasklist.
- [x] P0.9 Apply the final independent clarity-oracle corrections and pass the
  repository/doc truth check.

P0 is planning, research, and custody. It satisfies none of the 15 final
product criteria by itself.

## E0 — execution-environment preflight

- [x] E0.1 Reclaim sufficient disk space before B1 implementation. The final
  truth check found only about 145 MiB free and a Python heredoc could not
  create its temporary file. Cleanup requires a separate, explicitly approved
  disk survey/action and is not canonical-pack product work.
- [x] E0.2 Prove at least **3 GiB free** on `/System/Volumes/Data`, successful
  creation/removal of an ordinary temporary file, and successful creation of
  an isolated Python environment directory. Record commands and results before
  dispatching B1.
- [x] E0.3 Complete cloud-venue custody: unique workspace/container/session,
  exact base bundle plus complete `.oracle` overlay with recorded SHA-256/file
  count/size, zero product diff after restoration, and registration in the
  canonical AgentBox durable operations ledger.
- [x] E0.4 Prove the isolated cloud container's Python/git/OMP tooling, Luna and
  Sol routes, push dry-run, dependency install, focused baseline behavior, disk
  capacity, and protection of every pre-existing container/workspace before
  dispatching B1.

## Inherited behavior floor — preserve, do not rebuild

- **REUSE:** the frozen-but-not-deeply-immutable `PackDefinition` shell, v1
  parser/validator/scaffolding, layered discovery, provenance, and typed
  executor/orchestrator/element/rendering/generation projections.
- **REUSE:** external capability install/update/rollback/uninstall, revision
  storage, locks, aliases/forks/overrides, and trust inspection.
- **REUSE:** strict schema-manifest validation, immutable collision registry,
  dependency ordering/cycle checks, exact-byte checksums, drift refusal,
  read-only probes, and per-migration transactions.
- **REUSE:** `DatabaseWriter`, `UnitOfWork`, typed repositories/services,
  events, receipts, hashes, and conformance patterns.
- **REUSE:** timeline, shots, references, and Runaway SQL/product behavior.
- **REUSE:** application/SDK/read wiring, doctor, backup/restore, and the
  installed-artifact test harness.
- **REUSE:** 17 direct product-pack skills and `_core` guidance.

## Cutover invariant

B1 is contract/fixture work only. It must not activate strict v2 against the
current v1 bundled tree. B2, B3, and B4 form **one unshipped atomic cutover
tranche**:

- before activation, only the legacy capability/schema authorities are active;
- during the tranche, new behavior is exercised through isolated fixture roots
  and explicit injection;
- activation happens only after all 22 bundled manifests and all consumers are
  ready; and
- after activation, only canonical v2 is active. There is no dual loader,
  compatibility shim, or shippable dual-database-authority checkpoint.

## B1 — freeze and prove the v2 contract in isolation

Goal criteria: 1, 2, 6, 12, 13.

Classification/alignment inherited by B1.1–B1.10: **normal — Luna**. Advance
one identity/grammar/parser/catalog, confined resources, bundled-only database
trust, direct hard cut, and reuse of typed machinery. Avoid shims, dual reads,
hidden schema-pack reuse, external SQL, and speculative lifecycle machinery.

- [x] B1.1 Freeze one strict JSON Schema with integer `schema_version: 2` and
  only `pack.yaml` as its filename.
- [x] B1.2 Evolve the existing model into one deeply immutable canonical entry
  containing identity, normalized definition, provenance/source/root,
  capabilities/extensions, optional database contribution, documentation, and
  confined resource handles.
- [x] B1.3 Make static validation and the new catalog use one strict
  read-normalize-validate path.
- [x] B1.4 Reject v1, alternate filenames, missing/defaulted identity, legacy
  flat mappings, unknown fields, traversal, and symlink escapes.
- [x] B1.5 Freeze the optional `database` grammar: explicit `default_enabled`,
  ownership/vocabulary, repositories/conformance/static mounts, migrations,
  and dependencies expressed as pack ID plus a **positive minimum migration
  head**. Detailed DDL remains in SQL.
- [x] B1.6 Freeze structured documentation and narrowly declared
  `runtime_resource` entries with owner-root confinement.
- [x] B1.7 Build a deterministic catalog over an explicitly supplied fixture
  root; parse each manifest once and expose narrow typed capability, database,
  resource, and documentation projections.
- [x] B1.8 Add golden capability-only, database-only, and combined v2 fixtures,
  plus invalid legacy/path/dependency fixtures.
- [x] B1.9 Add a positive external capability-only v2 pack that succeeds via
  each supported external discovery/install path. Add otherwise-equivalent
  external packs with `database` for local, extra, environment, and installed
  sources, and prove rejection occurs before SQL/resource resolution.
- [x] B1.10 Keep the production runtime pinned to the captured legacy baseline;
  add no temporary dual reader or compatibility code.

Gate B1: **PASS under user control
`babysit-c46-end-open-ended-b1-loop`**. Candidate 45's two unaffected Luna
passes plus candidate 46's sole erased-metadata custody delta pass accept the
isolated v2 contract with no finite blockers. The intervention prohibited
candidate 47, another three-review panel, and an additional oracle dispatch.
Reviewed B1 checkpoint: `14f1f7d5f77cb6bd384749941cff6e522b696590`.

## B2 — prepare all 22 canonical product packs

Goal criteria: 1, 3, 5, 8, 13. Begins the unshipped atomic tranche.

Classification/alignment inherited by B2.1–B2.9: **normal — Luna**. Advance
one canonical ownership declaration, complete structured docs/resources, the
direct cut, and proportionate beta scope. Avoid compatibility aliases,
unclassified surfaces, fake `_core` symmetry, and exhaustive ownership
machinery.

- [x] B2.1 Delete the empty `builtin` pack and all 59 deprecated alias shims.
- [x] B2.2 Convert the 18 retained capability manifests to v2 without losing
  any of 64 executors, 12 orchestrators, 10 elements, or the typed
  rendering/generation projections.
- [x] B2.3 Add v2 `pack.yaml` to `timeline`, `shots`, `references`, and
  `runaway`, merging their database declarations without changing SQL or
  product semantics.
- [x] B2.4 Preserve explicit defaults: timeline/shots/references enabled,
  Runaway disabled but explicitly composable.
- [x] B2.5 Make `references` the combined capability/database/SDK/CLI/docs
  exemplar while preserving its three-table and command/event behavior.
- [x] B2.6 Give **all 22 retained product packs** direct structured guidance.
  Add skills for blender, timeline, shots, references, and Runaway; use no
  bundled-pack documentation opt-out. The general grammar may retain a
  justified opt-out for a future truly internal pack.
- [x] B2.7 Generate the `_core` 22-pack census and links to every owning skill;
  keep `_core` as code-owned guidance/kernel, not a fake product pack.
- [x] B2.8 Produce a lightweight customization coverage ledger covering pack,
  capability/extension, database, CLI/SDK/bridge, documentation, operational,
  and `runtime_resource` ownership, ending with zero unclassified surfaces or
  unjustified kernel owners.
- [x] B2.9 Inventory the known typed component/rendering loaders and explicit
  pack-relative file reads. Every known runtime resource must be declared or
  justified as kernel-owned; do not attempt exhaustive all-file/Python
  ownership.

Gate B2: **PASS under user control
`babysit-b2-safe-concurrency-bounded-gates`**. One independent Luna
certification verified the 35-path frozen candidate, exact 22-pack/64/12/10
census, four database declarations, 22 direct skills, confined resources,
zero-unclassified coverage, 106 focused tests plus 78 subtests, and
legacy-active isolation. No blocking finding or recorded high-risk reason
requires another segment review. Reviewed B2 checkpoint:
`a293e4c416c0e716154c392c0dd43165344f870d`.

## B3 — project canonical databases through the existing engine

Goal criteria: 4, 5, 6. Continues the unshipped atomic tranche.

Classification/alignment inherited by B3.1–B3.9: **normal — Luna**. Advance
SQLite authority, SQL-owned DDL, existing migration/writer/UoW reuse, confined
resources, and manifest-derived composition. Avoid duplicate state, YAML DDL,
general SQL observers, project locks, and premature legacy deletion.

- [x] B3.1 Project canonical database declarations into the surviving
  immutable collision/migration machinery through explicit catalog injection;
  do not delete production legacy builders yet.
- [x] B3.2 Replace the code-created core `SchemaPackManifest` with an explicit
  irreducible kernel database/vocabulary projection; keep core non-unloadable.
- [x] B3.3 Carry owning pack, owner root, and confined migration resource handle
  on every migration descriptor instead of rebuilding `astrid/packs/<id>`.
- [x] B3.4 Enforce the B1 dependency grammar by comparing every declared
  positive minimum migration head with the dependency pack's available head.
- [x] B3.5 Derive default composition only from bundled entries with
  `database.default_enabled=true`; derive explicit Runaway composition through
  the same projection.
- [x] B3.6 Preserve `schema_migrations` as the sole applied-state record and
  preserve checksums, drift/order/transaction semantics, writer/UoW,
  repositories, and conformance behavior.
- [x] B3.7 Verify each bundled migration affects only declared owned tables
  with focused fresh-schema assertions, not a generalized SQL observer.
- [x] B3.8 Add fresh-default, existing-reopen, explicit-Runaway, read-only
  pending, dependency/head/cycle, collision, checksum/name drift, and rollback
  tests.
- [x] B3.9 Replace historical Runaway-demo dependencies with a deterministic
  temporary-project round trip; never restore or package the missing demo.

Gate B3: **PASS under bounded gate control**. Integrated closure and one
independent Luna certification verified the frozen six-path identity and each
passed 122 focused projection/registry/migration/Runaway tests. Production
remains legacy-active; there are no findings or recorded high-risk reasons for
an extra segment Sol review. Reviewed B3 checkpoint:
`cd4dc91a31e4c7127b4023a87dabfdebea276ff1`. Run cumulative gate 1 over
B1–B3 before B4 begins.

Cumulative gate 1: **PASS**. One independent Luna review confirmed linear
B1–B3 checkpoint ancestry, reused accepted frozen receipts, passed 70 bounded
integration tests, and found no cutover-readiness blockers. Production remains
legacy-active until B4's atomic activation.

## B4 — converge consumers and activate the atomic hard cut

Goal criteria: 2, 4, 7, 9.

Classification/alignment inherited by B4.1–B4.8: **normal — Luna**. Advance one
catalog-derived projection for all consumers and the direct deletion of
alternate authorities while preserving typed registries. Avoid a universal
service locator, dual reads, hidden schema-pack identity, dynamic factories,
or bypassing operational consumers.

- [x] B4.1 Construct the bundled catalog/database projection at a top-level
  application or operation seam and pass typed projections to consumers.
- [x] B4.2 Move all seven independent builder consumers: application, SDK
  invocation, kernel reads, timeline edit helpers, doctor, backup/restore, and
  rendering/media assets.
- [x] B4.3 Move the direct `domain_product` CLI mount reader; preserve explicit
  typed service/repository/static CLI/bridge factories.
- [x] B4.4 Preserve the single lock/writer, exact SDK registry propagation,
  read-only, backup/restore, and current product semantics.
- [x] B4.5 Extend pack inspect with stable text/JSON canonical identity/source,
  capability summary, database ownership/head, documentation, and declared
  resource closure.
- [x] B4.6 Extend doctor with the bundled census, docs/resource health, and
  expected/applied/pending migrations. Doctor must not consume the offline
  coverage ledger or scan Python ownership.
- [x] B4.7 At one atomic activation point, switch runtime admission to strict
  v2, delete all four `schema-pack.yaml` files, remove both
  `STANDARD_SCHEMA_PACKS` tuples and `_STANDARD_PACK_DIRS`/raw schema-manifest
  reads, and remove the separate schema-pack identity/parser/standard path
  after relocating reusable algorithms.
- [x] B4.8 Prove there is no active dual authority, no raw manifest reread, and
  no independent standard-registry build.

Gate B4: **PASS under bounded gate control**. Candidate 2's unaffected passes
plus candidate 3's independent finding-5 delta pass verified all 81 frozen
paths, one ordered operation-owned projection, strict-v2-only authority, and
zero finite blockers. Reviewed B4 checkpoint:
`81a64d64bd0ac0a920ceec69d75dd4ce9bbd1785`. Run cumulative gate 2 over
B1–B4 before B5 begins.

Cumulative gate 2: **PASS**. One bounded independent Luna integration review
confirmed linear B1–B4 ancestry, 81/81 B4 identities, strict-v2-only
authority, canonical composition/consumers, and external trust boundaries.
Its 279-pass command left only finite B5 packaging closure and the recorded
unavailable-`banodoco_timeline_schema` baseline lane.

## B5 — closure, wheel proof, and final review

Goal criteria: 3, 8, 10, 11, 12, 14, 15.

Classification/alignment inherited by B5.1–B5.9: **normal — Luna**. Advance
wheel-complete confined resources/docs, canonical inspection, zero legacy, and
evidence-backed completion. Avoid declaring success with bypasses, creating an
evidence platform, or reopening marketplace/lifecycle scope.

- [ ] B5.1 Verify zero v1/flat/alternate loaders, `schema-pack.yaml`, fixed
  tuples, raw identity reconstruction, alias shims, compatibility-only tests,
  or active docs teaching old forms remain. Legacy deletion occurred in B4;
  B5 does not defer it.
- [ ] B5.2 Update package data for all 22 v2 manifests, four migration trees,
  all 22 pack skills/docs, `_core` census, and every declared runtime resource.
- [ ] B5.3 Compare the declared runtime-resource set in source and wheel and
  prove every declared handle resolves within its owner root.
- [ ] B5.4 Update authoring, database, SDK/CLI, inspect, doctor, backup/restore,
  and agent-facing docs to teach only the final form.
- [ ] B5.5 Prove at least **5 GiB free**, create an isolated validation/build
  environment, install and record the version of `build`, then build one clean
  wheel. The current missing local `build` module is a preflight dependency,
  not a waived criterion.
- [ ] B5.6 Run clean outside-checkout wheel checks for help, catalog,
  docs/resources, fresh DB, doctor, default composition, and explicit Runaway.
  Re-run the positive external capability-only v2 install/discovery case from
  the installed-wheel lane.
- [ ] B5.7 Run focused pack/database/data-pack/consumer/docs tests and the full
  authoritative suite once; classify only reproducible unrelated baselines.
- [ ] B5.8 Produce a concise 15-row evidence matrix mapping each frozen goal
  criterion to commands, results, artifacts, and reviewer disposition.
- [ ] B5.9 Obtain three independent Luna final verdicts and the final
  independent Sol oracle disposition; commit the reviewed B5 checkpoint and
  push `HEAD:refs/heads/megado/canonical-pack-beta` only after the gate. Earlier
  passed batches already have their own reviewed commits. Do not merge, deploy,
  or release.

Gate B5: 22 canonical packs; zero legacy authority; three-pack default plus
explicit Runaway; complete source/wheel docs and resources; green tests; final
independent pass.

## Explicit exclusions

- per-project pack/revision composition lock;
- enable/disable/purge or database-aware uninstall lifecycle;
- third-party SQL/database packs;
- installed-record/revision-store redesign or Python byte attestation;
- operation-snapshot/TOCTOU/tamper-evidence program;
- marketplace, signing, sandbox, dependency solver, or permissions UI;
- dynamic repository/service/CLI/bridge factory framework;
- exhaustive all-file/Python ownership or runtime audit-ledger consumption;
- generalized SQL/table observer or bespoke evidence platform;
- compatibility shims or a dual-read period; and
- the follow-on `astrid update` project until this cutover passes.

## Progress truth

- Existing Astrid package/product foundation: **substantial and mostly built**.
  Eighteen of 22 target product directories already have v1 capability-pack
  manifests; all 64 executors, 12 orchestrators, and 10 elements are already
  domain-discovered; 17 of 22 product packs already have direct skills; all
  four database-backed slices and their migration engine are operational.
- Clarity/reconciliation control work: **P0 9/9 complete**.
- B1 implementation: **10/10 complete; checkpoint
  `14f1f7d5f77cb6bd384749941cff6e522b696590`**.
- B2 implementation: **9/9 complete; checkpoint
  `a293e4c416c0e716154c392c0dd43165344f870d`**.
- B3 implementation: **9/9 complete; checkpoint
  `cd4dc91a31e4c7127b4023a87dabfdebea276ff1`**.
- B4 implementation: **8/8 complete; checkpoint
  `81a64d64bd0ac0a920ceec69d75dd4ce9bbd1785`**.
- Canonical-v2 implementation checkpoints: **4/5 committed**.
- Frozen final criteria satisfied end to end: **0/15**; B1–B4 provide accepted
  implementation evidence, and production now uses canonical v2 only.

Next action: execute B5 source/wheel/docs/test closure.
