# M4 - Giant File Decomposition

## Outcome
The largest modules become navigable, focused modules with thin routers and
domain helpers. Behavior stays stable; the code simply becomes easier to read,
test, and change.

## Scope - IN
- Split the largest files identified in M0, prioritizing:
  `astrid/core/timeline/cli.py`, relocated pack machinery such as
  `astrid/core/pack/install.py`, `astrid/sdk.py`,
  `astrid/core/pack/cli.py`, `astrid/gateway.py`,
  `astrid/core/session/cli.py`, `astrid/core/task/gate.py`,
  `astrid/core/task/operator_view.py`, and large executor/orchestrator `run.py`
  files where a split is clearly beneficial.
- For CLI-heavy files, separate parser construction, command handlers,
  rendering/output, and business logic.
- For pack-heavy files such as `astrid/core/pack/install.py` and
  `astrid/core/pack/cli.py` after M2 relocation, perform the split inside the
  canonical `astrid/core/pack/` home. If M2 has not completed cleanly, coordinate
  the handoff rather than splitting pre-move paths and relocating the same large
  surface again.
- Establish one documented CLI command-registration/dispatch convention and
  migrate split CLI code toward it; add a conformance test so future subcommands
  do not recreate ad-hoc dispatch patterns.
- For SDK/facade-heavy files, separate public facade definitions from
  validation, dispatch, DTO/result handling, and compatibility glue.
- For executor/orchestrator `run.py` files, keep `run.py` as adapter glue and
  move reusable domain logic into focused modules.
- Add characterization tests before splitting any file whose behavior is not
  already well-covered.
- Before splitting `astrid/gateway.py`, characterize names accessible through
  `astrid.core.gateway` and scan test `mock.patch("astrid.core.gateway...")` targets.
  Post-split gateway facades must preserve those attribute-level compatibility
  paths.

## Scope - OUT
- Do not redesign APIs.
- Do not change command output unless characterization proves existing output is
  already unstable and docs/tests are updated deliberately.
- Do not split files just to hit a line-count number; split where it clarifies
  responsibilities.
- Timeline/render-adjacent modules may only be split after characterization and
  must keep roadmap M11 golden/public-surface gates passing.

## Locked Decisions
- Routers should be thin.
- Business logic should not live in CLI parser construction.
- Executor `run.py` files should not become domain engines.
- Splits must reduce cognitive load, not create arbitrary fragments.
- Every source file over roughly 1,200 lines is either split or carries a short
  documented reason it is irreducible, such as schema/table-driven code.

## Evidence Classifications
- Classify giant files that are acceptable because their complexity is
  inherently schema/table-driven, and record the irreducible reason.
- Defer a split only when M0 or an active roadmap record shows a near-term
  subsystem rewrite that would make the split throwaway churn.
- For timeline, threads, docs-naming, and compatibility-shim surfaces, classify
  whether the change improves the completed roadmap shape or merely reopens a
  settled roadmap contract. Reopening settled roadmap contracts is out of scope.

## Constraints
- Characterize first, then split.
- Keep import paths compatible where public.
- Keep cycle count and import complexity from worsening.

## Done Criteria
- The selected giant files are split into named, focused modules.
- The largest file, `astrid/core/timeline/cli.py`, is either split behind M11
  characterization/golden gates or has a written, reviewer-accepted reason it
  cannot be split in this epic.
- A CLI command-registration convention exists and is enforced by a test or
  structure check.
- Public behavior and tests remain green.
- New module names match the M0 architecture contract.
- No new broad compatibility debt is introduced without documentation.

## Touchpoints
Largest source files under `astrid/`, affected tests, public surface tests,
CLI tests, pack execution tests.

## Anti-Scope
No feature additions, no identity unification, no new SDK design, no roadmap
contract breakage.
