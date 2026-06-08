# M5 - Boundary Enforcement And Final Polish

## Outcome
The architecture conventions from M0-M4 become enforceable and visible. The
final repo should feel intentional: clear boundaries, clean navigation, fewer
compatibility ambiguities, and no obvious layout drift.

## Scope - IN
- Re-run the M0 inventories and compare the post-cleanup tree against the target
  repo-shape contract.
- Add or strengthen import-boundary tests:
  packs do not import pack implementations through core, core does not depend
  on concrete first-party pack implementations except through registries, CLI
  modules do not own domain logic, public facades do not reach into unstable
  internals unnecessarily.
- Add structural gates for the cleaned pack tree: top-level `astrid/packs/`
  contains no Python machinery files except sanctioned compatibility shims with
  dated rationale; pack-root `__init__.py` files are absent or documented as
  importable-code exceptions; generated `__pycache__/`, `.DS_Store`, and
  non-golden `build/` debris are absent.
- Confirm roadmap-derived contracts still hold: timeline compatibility exports,
  internal threads lineage, public compatibility shims, and docs/current-vs-
  historical framing.
- Migrate all first-party internal importers off compatibility shim paths such
  as `astrid._paths`, `astrid._media`, `astrid.core.search`,
  `astrid.core.gateway`, and `astrid.timeline` where a canonical module exists.
- Remove migration escape hatches that M2 classifies as no-longer-needed, such
  as `ASTRID_AUTHOR_TEST_LEGACY`, `ASTRID_ALLOW_LEGACY_APPEND_EVENT`,
  migration-only legacy decoders, and `LEGACY_ASSIGNEES`, after confirming no
  CI/scripts/tests/public docs still depend on them.
- Preserve user-facing CLI aliases such as `astrid run` and `astrid author`
  only if they have explicit tests, visible deprecation messaging, and a dated
  sunset or compatibility rationale.
- Add tests asserting first-party internals do not import those shim paths.
  Public-facing shims that must remain get a dated removal ticket and a SemVer-
  tied deprecation note, not open-ended retention.
- Retire temporary compatibility shims only where tests and docs prove safe;
  otherwise document their retention with an owner, removal condition, and
  target release.
- Add a concise contributor-facing "where does new code go?" section to the
  architecture docs or AGENTS/core skill docs.
- Run `desloppify status` or equivalent health checks and record remaining
  structural debt that belongs outside this epic.
- Clean any generated debris produced during the chain.
- Audit M2-to-M4 handoff surfaces such as `astrid/core/pack/install.py`,
  `astrid/core/pack/cli.py`, `astrid/core/pack/validate.py`, and
  `astrid/gateway.py` for stale pre-move paths, temporary compatibility comments,
  and facade exports that no longer match the final split module shape.

## Scope - OUT
- Do not chase all possible code quality issues.
- Do not start identity unification.
- Do not alter product behavior to satisfy an aesthetic preference.

## Locked Decisions
- Beauty means clear shape plus enforced boundaries, not arbitrary renames.
- Remaining debt is acceptable if it is named, bounded, and not misleading.
- Compatibility shims stay if removal would create avoidable risk.

## Evidence Classifications
- Move remaining debt to follow-up tickets rather than expanding this epic when
  it is named, bounded, and no longer misleading in the repo layout.
- Keep a boundary rule as a documented convention only when a test would be too
  brittle; otherwise enforce it with a layout/import check.

## Constraints
- Main must finish clean and green.
- The epic should not leave local worktrees, stale branches, generated outputs,
  or untracked artifacts.
- Keep compatibility with existing public imports and CLI commands unless an
  explicit deprecation path exists.

## Done Criteria
- M0 inventories show the target shape has been substantially achieved.
- Boundary/layout tests pass.
- First-party internal shim-import tests pass; any remaining public shim has a
  dated deprecation/removal record.
- Migration-only escape hatches are either removed or documented with an owner,
  active caller, and removal trigger.
- Import-layering tests assert `astrid/core/*` does not import concrete
  `astrid/packs/<pack>` implementations except through registries, and CLI
  modules do not own domain logic.
- Docs explain the source, pack, test, and docs layout.
- `git status` is clean.
- The checkout is clean within the dedicated `astrid-beauty` worktree, with no
  stale branches, loose worktrees, or generated debris left by this chain.
- Remaining structural debt is recorded as follow-up issues or docs, not left
  implicit.

## Touchpoints
`docs/architecture/`, `AGENTS.md`, `astrid/packs/_core/skill/SKILL.md`,
boundary tests, source layout tests, `.gitignore`, generated artifacts.

## Anti-Scope
No identity unification, no marketplace/trust-system implementation, no feature
work, no product-surface redesign.
