# M1 - Pack Layout Normalization

## Outcome
Every first-party pack follows one recognizable physical convention, and any
exception is explicit, documented, and validated. The pack tree should become
the easiest part of the repo to understand.

## Scope - IN
- Enforce a canonical pack structure:
  `pack.yaml`, optional `skill/SKILL.md`, `executors/<name>/executor.yaml`,
  `executors/<name>/run.py`, `orchestrators/<name>/orchestrator.yaml`,
  `orchestrators/<name>/run.py`, optional `fixtures/`, optional `golden/`,
  optional `elements/`, optional `build/` only when generated and ignored.
- Reconcile pack docs with the actual canonical convention. If `skill/SKILL.md`
  is the standard pack-facing instruction surface, update the docs that still
  imply root `AGENTS.md` / `README.md` / `STAGE.md` is required; if root docs
  are required, migrate the pack fleet consistently.
- Normalize pack docs naming and placement across first-party packs.
- Normalize executor/orchestrator metadata placement and file naming.
- Remove or relocate duplicate local/scaffold pack artifacts that do not belong
  in the canonical tree.
- Declare pack directories as pure data by default. Remove stray `__init__.py`
  files from first-party packs unless a specific pack is explicitly documented
  and tested as importable implementation code.
- Before removing any pack-tree `__init__.py`, inventory code and tests that
  import `astrid.packs.<pack>...` modules. Executor/orchestrator package files
  needed for relative imports or cross-pack imports are infrastructure, not
  stray scaffolding, and must either stay or receive compatibility coverage.
- Normalize legacy-flat pack shapes such as single-file pack modules into the
  canonical executor/orchestrator structure, or document them as named,
  validated exceptions with a reason that is domain-real rather than drift.
- Flag pack-root `.py` files that are legacy shims, domain modules, or
  machinery, such as `video_editing/hype.py`, `text_analysis/summarize.py`, and
  `builtin/agent_probe.py`. Do not delete them casually; classify each as an M1
  layout migration, an M2 machinery/public-shim relocation, or a named
  validated exception.
- Ensure `astrid/packs/` contains pack data only. Validation schemas and other
  pack-system machinery belong in the canonical machinery home, not beside pack
  directories.
- Treat pack schemas as a special contract surface during relocation. If
  schemas move from `astrid/packs/schemas/v1/` to `astrid/core/pack/schemas/`,
  update `docs/creating-packs.md` and validation path resolution in the same
  milestone; if they remain, document why they are a public contract exception
  inside the pack data tree.
- Add or strengthen pack validation tests so future packs drift less.
- Keep generated pack build artifacts, `__pycache__/`, and `.DS_Store` files
  out of the source tree unless there is a deliberately tracked golden fixture.

## Scope - OUT
- Do not change executor/orchestrator behavior.
- Do not change pack IDs or public capability IDs unless the old ID remains an
  alias with characterization coverage.
- Do not redesign pack discovery, install semantics, or external pack trust.

## Locked Decisions
- The canonical source home for text-analysis style packs is
  `astrid/packs/<pack_id>/`, not a duplicate top-level directory.
- The previous loose-work cleanup already removed the top-level
  `text_analysis/` duplicate on `origin/main`; this milestone should verify
  that state rather than redoing the removal.
- Generated `build/` output is not source unless explicitly named as a golden
  fixture.
- Pack layout should be conventional enough that agents can author new packs
  without reading implementation internals.
- `astrid/packs/` is a data surface. A contributor listing that directory
  should see pack directories, not validation/install/CLI implementation files
  or schemas.

## Evidence Classifications
- Classify current pack directories that need documented exceptions because the
  exception is domain-real rather than drift.
- Classify non-manifest pack-tree directories such as `_core`, `external`, and
  any referenced-but-absent shell packs. Preserve skill-discovery behavior and
  pack IDs while deciding whether each is pack data, skill documentation,
  compatibility shell, or stale debris.
- Pack validation should present one agent-friendly layout-contract failure
  surface where possible, with separate schema/layout detail underneath when
  useful for debugging. Tests must cover the selected presentation.

## Constraints
- Preserve capability discovery results unless intentionally covered by alias
  tests.
- Keep author tests and pack validation green.
- Prefer mechanical moves with import shims over rewrites.

## Done Criteria
- Pack layout validation passes for every first-party pack.
- The canonical layout is documented in the pack docs or architecture doc.
- Current docs and the checked-in pack fleet agree on one canonical docs/layout
  convention.
- Duplicate/scaffold-only pack copies are removed or explicitly ignored.
- No pack-system machinery, schemas, committed build output, or `.DS_Store`
  files remain mixed into the first-party pack data listing.
- Existing pack execution tests pass.
- `git status` is clean at the end of the milestone.

## Touchpoints
`astrid/packs/`, `astrid/core/pack/`, pack schema tests, pack discovery tests,
author tests, `.gitignore` where generated pack outputs are involved.

## Anti-Scope
No new packs, no new pack marketplace, no sandbox/signing implementation, no
identity unification.
