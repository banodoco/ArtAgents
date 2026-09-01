# B4 candidate-1 finite rework

Model assignment: **normal implementation/validation — GPT-5.6 Luna**.

Repository: `/workspace/astrid-canonical-pack-beta-20260831-a1/Astrid`
Branch: `megado/canonical-pack-beta`
Base: `7ac50c12e8e4d90988fee603ffdb9896e5628792`
Frozen candidate 1: `.oracle/evidence/b4-candidate-1.sha256`, manifest SHA-256 `e88b14aa4133570d181ecedb58eb56d8e29c72837769937f3cae7e5dbc2d107f`.
Blocking certification: `.oracle/receipts/b4-certification-luna.txt`.

Read `.oracle/agent_goal.md`, `.oracle/tasklist.md` B4, `.oracle/plan.md`, the activation receipt, and the blocking certification. Inspect and correct exactly its six finite findings and their direct dependency closure. Preserve all unaffected B4 implementation and passing evidence. Do not restart activation, revert another worker's edits, commit, push, start B5 packaging/wheel/full-suite work, dispatch another model, or touch protected workspaces. Skip formatters, linters, and broad/full tests.

User control `babysit-c46-end-open-ended-b1-loop` is acknowledged and closed B1. Do not reopen B1, create candidate 47, or run a review panel.

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

## Finite corrections

1. Fix `astrid/packs/rendering/backends/remotion/run.py` staging so the render path never references undefined `staged_video`; preserve exact staging/hash/ownership behavior and reproduce then close the reviewer’s NameError.
2. Thread the operation-owned catalog and frozen database registry through `AstridClient` direct capability/rendering paths and `astrid/sdk/rendering.py`. Remove independent rendering-registry fallback. Inspect `sdk/discovery.py` and get-capability callsites identified by the review; no bound SDK operation may bypass the application composition.
3. Make `CanonicalPackDefinition.to_dict()` retain canonical capabilities so agent index and `pack inspect --agent` expose the declared generation capabilities. Do not add a second serializer authority.
4. Restore `_verify_git_checkout_commit()` on the non-dry-run Git update path before mutation/publication; preserve existing canonical manifest-byte custody.
5. Remove the remaining active legacy database fallback in `astrid/core/kernel/database.py`. Rewrite active tests and tooling that import/read/teach deleted schema-pack modules/files onto canonical catalog/projection fixtures: at minimum the paths named in the certification (`tests/v10/test_m8_packaging.py`, `tests/v10/test_registry.py`, `tests/v10/test_m8_installed_contract.py`, `tests/test_runaway_transitions.py`, `tests/v10/test_conformance.py`, `scripts/migrations/runaway_v1_migrate.py`, `scripts/reshape/m4_gate.py`, `scripts/reshape/check_pack_factoring.py`, `scripts/smoke_wheel_install.sh`). Delete compatibility-only assertions only when they have no canonical contract; preserve behavioral migration/repository tests.
6. Treat `examples/packs/minimal/pack.yaml` and `scripts/reshape/authority_lint.py` as part of the activation candidate. Ensure both teach/check strict v2 only. Report every changed/deleted path so the owner can freeze a complete candidate 2.

Use LSP references before changing exported symbols if the configured server supports them; if it returns method-not-supported, record that and use bounded repository searches.

## Verification

Run focused tests/reproductions only for the six affected criteria and direct dependencies:

- remotion staging regression;
- SDK bound catalog/registry identity and rendering/capability dispatch without an independent registry;
- agent index plus inspect-agent generation capability output;
- Git update checkout-commit verification and canonical custody;
- canonical registry/conformance/Runaway/m8 packaging/import closure for rewritten legacy-dependent paths;
- authority lint and minimal example strict-v2 validation.

Also rerun the smallest B4 composition/strict-authority checks needed to prove the fixes did not reintroduce dual authority. Do not rerun the 210-test implementation command or any full suite.

Return exactly:

```text
REWORK: PASS|BLOCKED
CHANGED: <complete product/test/tool/example paths>
FIXES: <1-6 result>
IDENTITY: <single catalog/registry/SDK result>
LEGACY: <zero active schema-pack/fallback result>
TESTS: <commands and exact results>
BLOCKERS: <none or finite list>
```
