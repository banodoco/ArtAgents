# Agent goal — canonical pack beta hard cut

Status: **frozen**.

[North Star](./northstar.md)

This run advances the North Star by replacing Astrid's split and partially
duplicated pack authorities with one complete canonical bundled-pack path,
covering all existing bundled custom functionality and its packaged agent
documentation without adding post-beta composition machinery.

## Objective

Implement the direct beta end state in which every bundled Astrid product pack
uses strict `pack.yaml` v2, every existing bundled customization is mapped to a
canonical pack or explicitly justified kernel owner, database-bearing packs
declare an optional `database` contribution, all existing typed systems consume
projections of one complete canonical definition, and every user/agent-facing
pack ships validated agent documentation discoverable from the `_core` skill.

Convert the four current schema packs (`timeline`, `shots`, `references`, and
`runaway`), derive standard database composition from bundled manifests, make
resources pack-relative and wheel-complete, rewire every relevant operational
consumer, expose useful inspection/doctor output, and delete obsolete manifest
forms and alternate authorities. Preserve existing feature semantics.

## Authoritative inputs and immutable source

- [North Star](./northstar.md).
- This frozen agent goal.
- Source ref: `7ac50c12e8e4d90988fee603ffdb9896e5628792`.
- Source branch at custody: `codex/live-ux-pre-phase-b-20260824`.
- Worktree branch: `megado/canonical-pack-beta`.
- [Custody baseline](./custody.md).
- Existing source and tests, except tests intentionally enforcing forms named
  for deletion below.

## Settled decisions

1. Exactly one canonical manifest filename: `pack.yaml`.
2. Schema version 2 is a hard cut. No `pack.yml`, `pack.json`, schema-less/flat
   YAML, or `schema-pack.yaml` compatibility.
3. A pack may contribute capabilities, SQLite schema, agent documentation, or
   a combination.
4. Database contribution is an optional `database` block; detailed DDL remains
   authoritative in migration SQL.
5. Migrations/resources resolve relative to the owning pack root/revision.
6. Parse/normalize/validate once into one complete immutable canonical object.
7. Existing typed registry/database mechanics remain subordinate projections.
8. Every existing bundled customization gets a canonical pack owner or an
   explicit kernel classification recorded in a coverage ledger.
9. Standard beta composition is derived from bundled manifests, not duplicated
   fixed tuples.
10. Existing `schema_migrations` remains the sole applied database-state record.
    No per-project composition lock in beta.
11. Standard writable open may continue applying trusted bundled migrations;
    read-only paths probe compatibility. No enable/disable/purge lifecycle.
12. External packs remain capability-only; external `database` declarations
    fail closed.
13. The irreducible kernel stays code; `_core` is not dynamically unloadable.
14. Static typed application/service/CLI/bridge wiring may remain where dynamic
    factories add no beta value, but ownership and documentation cannot bypass
    the canonical catalog.
15. Every user/agent-facing bundled pack has structured `AGENTS.md` or
    `skill/SKILL.md`; intentional opt-outs require a manifest reason and must be
    limited to non-user-facing internal utility packs.
16. The `_core` skill contains or links a generated canonical pack census.
17. `references` becomes the exemplar combined data/SDK/CLI/documentation pack
    without changing its three-table model or semantics.
18. Application, doctor, backup, restore, inspect, validation, and packaging
    consume the same canonical ownership/resource data.

## In scope

- V2 schema, complete canonical model, single loader/validator, deterministic
  bundled catalog, root confinement, and resource closure.
- Capability-only, database-only, and combined golden fixtures/scaffolds.
- Conversion of every bundled pack manifest and the four schema manifests.
- Database projection into existing collision/migration mechanics.
- Pack-relative migration/resource loading and enforced dependency semantics.
- One standard bundled composition path used by application, doctor, backup,
  restore, SDK/read probes, and package validation.
- Canonical customization coverage ledger and a zero-unclassified-surface gate.
- Pack inspection output in text and JSON for identity, source, capabilities,
  database ownership/head, agent docs, and resource closure.
- Doctor canonical pack census and migration status.
- Structured pack agent documentation, `_core` census/routing, and wheel
  inclusion/validation of declared skills and docs.
- CI gates for legacy authorities, path escapes, missing/undeclared resources,
  missing documentation, and clean-wheel closure.
- Focused documentation and end-to-end examples, with `references` as exemplar.
- Deletion of obsolete schema-pack and legacy manifest paths after cutover.

## Non-goals

- Per-project pack locks or variable project composition.
- Enable/disable/purge/database-aware uninstall lifecycle.
- Third-party database packs or arbitrary external SQL.
- Marketplace, sandbox, signing, dependency solver, remote activation, or UI.
- General dynamic repository/service/CLI/bridge factory framework.
- Moving every global model/LoRA/type/taxonomy or kernel primitive into packs
  unless source evidence shows it is existing pack-owned customization required
  by the zero-unclassified gate.
- Down migrations, data rollback, or compatibility shims.
- Merge to main, deployment, or promotion.

## Authorization

Authorized:

- create and mutate the dedicated worktree/branch above;
- run the full Megado plan/explore/revise/execute/oracle/validation process;
- invoke GPT-5.6 Luna and GPT-5.6 Sol under the declared routing policy;
- edit code, tests, docs, and run artifacts within goal scope;
- commit reviewed checkpoints;
- push the reviewed final branch to `origin` using explicit refspec
  `HEAD:refs/heads/megado/canonical-pack-beta`;
- open the completed worktree.

Not authorized:

- modify, clean, stage, or restore the original dirty checkout;
- merge, rebase onto a moving branch, deploy, promote, publish a release, or
  mutate any other worktree;
- switch pinned models without user approval;
- widen the frozen goal under cover of the North Star or review findings.

## Model policy

- Planner: GPT-5.6 Sol, high reasoning.
- Normal explorer/executor/sense-check work: **GPT-5.6 Luna**, user-selected.
- Oracle and exceptional `[XHARD]` work: **GPT-5.6 Sol**, user-selected.
- Automatic switching: not authorized.

Normal is presumed. Cross-cutting size or importance is not `[XHARD]` evidence.
Every proposed `[XHARD]` task must satisfy the skill's full exceptional test.

## Exact done criteria

1. Every bundled product pack loads from one v2 `pack.yaml` into the complete
   canonical object; no shipped `schema-pack.yaml` remains.
2. No active consumer independently reparses or reconstructs canonical pack
   identity; typed capability/database projections share the same catalog.
3. A reviewed coverage ledger maps every existing bundled custom surface to a
   canonical pack/projection or justified kernel owner, with none unclassified.
4. Standard database composition derives from bundled manifests with no
   duplicate `("timeline", "shots", "references")` authority.
5. `timeline`, `shots`, `references`, and `runaway` preserve migration,
   repository, event, command, CLI, SDK, and conformance behavior.
6. Migrations resolve from owner roots and preserve collision/order/checksum/
   drift/transaction guarantees; dependency declarations are enforced.
7. Application, SDK/read probes, doctor, backup, restore, inspect, and package
   validation agree on canonical ownership and expected composition.
8. Every user/agent-facing bundled pack has valid packaged agent docs; every
   opt-out is explicit and justified; `_core` exposes the canonical census.
9. Pack inspection and doctor expose useful canonical pack/database/resource/
   documentation state in stable text and JSON where applicable.
10. A clean wheel contains and can load every declared bundled resource,
    migration, skill, and agent document.
11. Legacy manifest/schema-pack parsers, standard builders, duplicate authority,
    and compatibility tests/docs are deleted or clearly historical/non-active.
12. External capability-only packs still work; external `database` fails closed.
13. Golden capability-only/database-only/combined examples validate.
14. Focused suites and full authoritative test suite pass, or any unrelated
    baseline failure is proven with reproducible before/after evidence.
15. Final evidence matrix maps every criterion to commands, artifacts, results,
    and independent reviewer disposition; final oracle review passes.

## Validation contract

The stable plan must discover exact project commands and may refine this list,
but final validation includes:

```bash
python3 -m pytest tests/packs tests/v10/test_catalog_migrations.py \
  tests/v10/test_m8_packaging.py tests/v10/test_pack_factoring.py \
  tests/v10/test_reference_repository.py tests/sdk/test_references.py \
  tests/sdk/test_extended_composition.py
python3 -m astrid doctor
python3 -m build
```

Also required: fresh and existing SQLite scenarios; checksum drift rejection;
complete `references` round trip; external capability success/database failure;
clean-wheel load/resource audit; agent-doc/census audit; pack inspect text/JSON;
and zero-legacy/zero-unclassified checks. One authoritative owner runs the full
suite and each expensive validation once.

## Stop and sync policy

- Stop for user reconciliation if the source ref, model policy, North Star,
  scope, or authorization must change.
- Treat implementation blockers as owned work until genuinely exhausted.
- Commit only paths reviewed at each checkpoint.
- Push only after the final evidence matrix and oracle gate pass.
- Never merge, deploy, or promote.
