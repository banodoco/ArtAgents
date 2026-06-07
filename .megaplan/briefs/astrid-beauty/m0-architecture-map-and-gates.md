# M0 - Architecture Map And Gates

## Outcome
Freeze a concrete repo-shape contract for Astrid and add the minimum objective
gates needed to make later behavior-preserving cleanup safe. A reviewer should
be able to open the repo and understand which directories are public API,
kernel internals, packs, tests, docs, and operational history.

## Scope - IN
- Produce `docs/architecture/repo-shape.md` describing the intended layout:
  public entrypoints, core subsystems, pack contract, test layout, docs layout,
  compatibility shim policy, and anti-coupling rules.
- Add a "relationship to `astrid-roadmap`" section to that document. It must
  explain that the roadmap chain is complete and identify the contracts it left
  behind: timeline compatibility re-exports, internal threads lineage, and
  public compatibility shims.
- Inventory current top-level modules under `astrid/` and classify each as:
  public facade, CLI entrypoint, core/internal module, compatibility shim,
  domain subsystem, or migration candidate.
- Inventory top-level directories under `astrid/`, not just root `.py` files.
- Inventory pack layout variants under `astrid/packs/` and record the canonical
  structure later milestones must enforce.
- Inventory root-level tests and map each to the domain folder it should move
  to in M3.
- Inventory the largest source files and pick the M4 split candidates, starting
  from current line-count offenders such as `astrid/core/timeline/cli.py`,
  `astrid/packs/install.py`, `astrid/sdk.py`, `astrid/packs/cli.py`,
  `astrid/gateway.py`, and large executor/orchestrator `run.py` files.
- Add lightweight automated gates where possible:
  import-boundary checks for packs/core, source-layout smoke checks,
  compatibility/public-surface characterization where later moves depend on it,
  and a Reigh import smoke that proves public cleanup does not break
  `astrid.core.reigh` imports.

## Scope - OUT
- Do not move large amounts of code in this milestone.
- Do not change behavior, CLI output, SDK contracts, pack execution semantics,
  timeline semantics, project/session identity, or Reigh integration behavior.
- Do not do identity unification.
- Do not break roadmap-owned contracts: timeline/render goldens,
  contract-locked internal threads lineage, public compatibility shims, or
  documented public import behavior.

## Locked Decisions
- The beauty epic is behavior-preserving. Any behavior change belongs in a
  separate product or correctness milestone.
- `astrid/packs` remains the capability surface. This epic normalizes it; it
  does not replace the pack model.
- `astrid/core` remains the kernel/internal home. Public consumers should reach
  stable facades/contracts, not arbitrary internals.
- Compatibility shims are allowed only when they are named, documented, and
  covered by tests.

## Evidence Classifications
- Classify which top-level subsystems have existing public-surface evidence and
  should remain stable facades versus moved/thinned under `astrid/core`.
- Apply immediately enforceable import-boundary rules from observed dependency
  shape. Boundary rules that would cause excessive churn start as documented
  conventions with the narrowest useful testable gate.
- Prioritize giant-file splits before test relocation when they are large,
  coupled, and already characterized enough to split without behavior risk.

## Constraints
- Start from clean `origin/main`.
- Keep CI green.
- Preserve all public API behavior unless a deprecation shim and test prove the
  old path still works.
- Use repo-local patterns and existing helpers.

## Done Criteria
- `docs/architecture/repo-shape.md` exists and names canonical homes for the
  major code categories.
- A machine-readable or test-readable inventory exists for top-level modules,
  pack layout variants, root-level test relocation targets, and giant-file split
  targets.
- At least one objective layout/boundary gate is added and passing.
- Packs/core boundary, public-import, and Reigh-import smoke gates are either
  added and passing or explicitly documented as impossible with a narrower
  replacement gate.
- Later milestone briefs are updated if the inventory proves their scope should
  change.
- Full relevant test/lint gates used by this repo are green or documented with
  existing baseline exceptions.

## Touchpoints
`docs/architecture/`, `astrid/`, `astrid/core/`, `astrid/packs/`, `tests/`,
`pyproject.toml`, `scripts/`, existing validation tests.

## Anti-Scope
No identity unification, no SDK redesign, no pack-system replacement, no Reigh
or RunPod product work, no broad runtime refactor, no roadmap contract breakage.
