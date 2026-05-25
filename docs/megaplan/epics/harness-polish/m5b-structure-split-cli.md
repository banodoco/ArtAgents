# m5b — God-Module Splits, CLI Unification & Deferred De-inversion

## Outcome
The two god modules are split along **named domain seams** (not by line count), the CLI has one
dispatch mechanism mirroring the existing good pattern, and the `lifecycle.py`/`pipeline.py`
pack-import de-inversion deferred from m4 lands here — so the de-inverted imports settle into the
correct sub-modules in one motion instead of being written twice. This is the cross-cutting,
premium-critique half of the old m5.

## Scope (IN)
**Split the god modules along NAMED seams (mirror the existing well-structured packages):**
`core/element/` (6 files: `__init__`/`cli`/`registry`/`schema`/`install`/`catalog`) and `core/orchestrator/`
(10 files: …/`runner`/`plan_template`/`runtime`/`folder`/`api`) show the right schema/registry/cli/runner seams.
- `astrid/core/task/lifecycle.py` (~2008 lines, 7 responsibilities) → split into e.g. `plan_builder.py`,
  `orchestrator_resolver.py`, `run_store.py`, `inbox.py` (lifecycle verbs stay in `lifecycle.py`). Each new module
  gets a one-line docstring stating its single responsibility and forbidden dependency directions.
- `astrid/timeline.py` (~1413 lines, self-described "Banodoco kitchen sink") → split into `timeline_model.py`
  (Pool/Arrangement/PipelineMetadata/AssetRegistry data types) and `banodoco_composer.py` (transition/effect-id
  registry checks, themes), behind a stable import surface.

**Absorb the deferred m4 de-inversion (do it DURING the split):**
- `astrid/core/task/lifecycle.py:230,245,259` — replace the hard imports of
  `astrid.packs.builtin.orchestrators.{hype,event_talks,thumbnail_maker}.plan_template` with resolution through
  the `PackResolver`/extended `OrchestratorRegistry` m4 built; the de-inverted call lands in the new
  `orchestrator_resolver.py` sub-module.
- `astrid/pipeline.py:268,272,340` — replace concrete pack-executor imports (`publish`, `youtube`, `reigh_data`)
  with dynamic resolution via `metadata.runtime_module` (already sufficient per the pack-boundary analysis) as part
  of the CLI dispatch rewrite below.
- After this lands, **remove the `lifecycle.py`/`pipeline.py` exemptions from m4's
  `structure.py:validate_import_layering()` contract** so it enforces `core ⊥ packs/orchestrate` with no holes.

**Unify CLI dispatch (mirror `core/element/cli.py:47-143` / `core/orchestrator/cli.py:57-183`):**
Pattern: `build_parser()` → `add_subparsers(dest=...)` → `add_parser()` → `set_defaults(handler=...)` →
`main()` dispatches `args.handler(...)`. Apply it to:
- `pipeline.py:382-488` (runs/events/sessions `raw[0]` string-matching) and `:510-522` (hand-rolled runpod flag loop).
- The parse→serialize-argv→re-parse double-parse anti-pattern (`packs/cli.py:1324-1335` → `install.py:1635`, and the
  sibling `_handle_*`→`cmd_*` pairs).
- Remove the duplicate `build_parser()` (`packs/cli.py:350` unreachable; `:1120` canonical) and dead `cmd_list()` (`:411-455`).
- **Fix the silent fallthrough-to-hype:** `pipeline.py:347` `_dispatch()` has no `else` — unknown subcommands run
  `builtin.hype` with raw args. Add an explicit "unknown command" error + nonzero exit (the real fix is the argparse
  unification, of which this is part).
- Fix `_print_entrypoint_help()` (`pipeline.py:770`) listing only 2 of 10 `packs` subcommands; align `--json` dest
  (`packs/cli.py:483` `json_output` vs `json` elsewhere); fix `guard_canonical_entrypoint` message
  (`_canonical_entrypoint.py:22-26`, says `astrid …` not `python3 -m astrid …`).
- Evaluate `orchestrate/cli.py` (the third argparse island) and `orchestrate/dsl.py` for absorption/seam — at minimum
  document whether they stay separate so the CLI layer isn't left half-unified.

## Scope (OUT / anti-scope)
- No taxonomy renames / dead-code / docs work (m5a, already merged before this runs).
- No pack logic changes; the `pipeline.py` de-inversion uses existing manifest metadata only.
- No runtime-behavior change — splits and dispatch unification are behavior- and import-surface-preserving;
  provide back-compat import shims only where an external caller would break, and update internal call sites instead.
- Don't redesign the event/cursor model (m3 owns runtime semantics).

## Locked decisions
- Split by NAMED domain seam with per-module single-responsibility docstrings + forbidden-dependency notes, not by line count.
- CLI uses one argparse-subparser-delegation mechanism (the existing `core/element/cli.py` pattern); unknown commands error loudly.
- The deferred de-inversion lands here; m4's contract exemptions are removed and it stays green.
- Behavior- and import-surface-preserving; prefer call-site updates over new compat aliases.

## Open questions (resolve in plan)
- Exact seam boundaries for `lifecycle.py`/`timeline.py` and which need a back-compat shim for external callers.
- Whether `orchestrate/cli.py`/`dsl.py` fold into the unified dispatch now or are documented as deliberately separate.

## Constraints
- Full (trustworthy post-m2/m3) suite green at end; m3's regression tests (written against stable interfaces) still pass.
- m4's import-linter/`validate_import_layering` contract green with the `lifecycle.py`/`pipeline.py` exemptions REMOVED.
- Every documented command still runs as written (re-run m5a's `verify_docs_commands.sh`).

## Done criteria (mechanically checkable)
- `wc -l astrid/timeline.py` ≤ 300 and `astrid/core/task/lifecycle.py` ≤ 500 post-split (or a justified, committed cap).
- `test_import_surface_stable` asserts every public name from the pre-split `__all__` is still importable from the original module path.
- `grep -rn "import astrid.packs" astrid/core/` and the `pipeline.py` equivalent return nothing except the single m4 sanctioned seam;
  m4's contract runs green with the two exemptions removed.
- One CLI dispatch path: `grep` finds no `raw[0] ==`/hand-rolled flag loops in `pipeline.py`; unknown subcommand exits nonzero with a clear message (named test).
- Duplicate `build_parser()` and `cmd_list()` are gone (grep empty).
- `_print_entrypoint_help()` lists all subcommands; `--json` dest is consistent; the canonical-entrypoint message says `python3 -m astrid`.

## Touchpoints
- `astrid/timeline.py`, `astrid/core/task/lifecycle.py` (split + absorb de-inversion at `:230,245,259`)
- `astrid/pipeline.py:268,272,340,347,382-488,510-522,770` (de-inversion + CLI unification)
- `astrid/packs/cli.py:350,411-455,483,1120,1324-1335`, `astrid/packs/install.py:1635`, `astrid/packs/_canonical_entrypoint.py:22-26`
- `astrid/core/element/cli.py:47-143`, `astrid/core/orchestrator/cli.py:57-183` (pattern to mirror — read), `astrid/orchestrate/cli.py`, `astrid/orchestrate/dsl.py` (evaluate)
- m4 artifacts: `PackResolver`/`OrchestratorRegistry`, `structure.py:validate_import_layering()` (remove exemptions)
