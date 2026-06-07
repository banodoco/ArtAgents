# M3 - Test And Doc Layout

## Outcome
Tests and docs mirror the post-split source architecture. The repo should feel
curated rather than accumulated.

## Scope - IN
- Move root-level `tests/test_*.py` files into domain folders that mirror source:
  `tests/core/project/`, `tests/core/timeline/`, `tests/core/task/`,
  `tests/packs/<pack>/`, `tests/sdk/`, `tests/cli/`, and similar.
- Consolidate pack tests under one mirrored home such as `tests/packs/runtime/`,
  `tests/packs/install/`, `tests/packs/validate/`, `tests/packs/authoring/`,
  and per-pack `tests/packs/<pack_id>/`; remove duplicate pack resolver test
  files or merge them into the canonical pack runtime test home.
- Remove or relocate stale pack-test fixture directories that no longer map to
  current pack IDs, preserving only fixtures with an active assertion.
- Run after M4's giant-file decomposition so tests relocate once, to the final
  module shape, rather than mirroring pre-split files and moving again.
- Preserve test names and behavior unless a rename improves clarity and does
  not hide coverage.
- Update imports, fixtures, `pytest` collection config, and docs references.
- Separate user/product docs from operational history:
  product docs under `docs/`, architecture/reference under `docs/architecture/`
  or `docs/reference/`, historical megaplan material under `docs/megaplan/`.
- Move the canonical pack contract out of historical megaplan material into
  current docs, for example `docs/packs/contract.md`, and leave a short pointer
  in the historical location rather than making user docs depend on the ops
  archive for the source of truth.
- Add a short docs index if needed so a new contributor can find the current
  product docs before operational archaeology.

## Scope - OUT
- Do not rewrite docs content beyond navigation, current/legacy labeling, and
  relocation notes.
- Do not re-litigate roadmap M13's README/product-framing rewrite, retired-thread
  terminology, CLI migration notes, or naming cleanup. Improve navigation and
  layout around the completed docs only where it is behavior-neutral.
- Do not change product behavior.
- Do not delete historical megaplan artifacts just because they are verbose.

## Locked Decisions
- Test layout should mirror source layout where practical.
- Operational history is valuable but should not be confused with current user
  documentation.
- Moving tests must not reduce coverage or weaken assertions.

## Evidence Classifications
- Classify legacy docs as current, updated, relocated, or labeled history based
  on whether they describe present behavior.
- Identify intentionally cross-cutting test files that should remain in a shared
  folder, with the reason recorded in the test-layout map.

## Constraints
- Use mechanical moves where possible.
- Keep pytest collection stable.
- Avoid changing assertions unless necessary for path updates.
- Do not relocate tests for a module immediately before that module is split;
  either split first or include that test relocation inside M4.

## Done Criteria
- Root-level test clutter is materially reduced.
- Test folders mirror the source architecture documented in M0.
- Docs have a clear current-docs path and a separate operational-history path.
- Pack docs have a current canonical contract path, and pack tests no longer
  have split duplicate resolver coverage or stale pack-id fixture folders.
- Full test suite or the repo's accepted full-suite gate passes.

## Touchpoints
`tests/`, `docs/`, `docs/architecture/`, `pyproject.toml`, fixture imports,
docs tests.

## Anti-Scope
No runtime behavior changes, no identity unification, no roadmap contract
breakage, no deletion of useful history without replacement or explicit archive
rationale.
