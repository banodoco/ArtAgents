# Agentic state-mutation coverage sprint

## Outcome

Add 5 new agentic test scenarios that exercise Astrid's durable-state surfaces (plan mutation, timeline lifecycle, project/source persistence, inbox/ack, abort/restart) — bringing total scenario count from 15 → 20. After this sprint, the agentic harness can detect when an agent is competent at finding/authoring packs but unsafe at handling durable user state.

## Scope (IN)

Five new scenario YAMLs in `tests/agentic/scenarios/`:

1. **`midrun_plan_mutation`** — agent receives changed requirements during an active run and uses `astrid plan add-step` / `edit-step` / `remove-step` (pre-dispatch) and `supersede-step` (post-dispatch) instead of editing `plan.json` by hand. Continues via `next`.
2. **`timeline_lifecycle_integrity`** — agent creates two timelines, picks one as default, finalizes a small output, verifies the sha via `timelines show --json --verify`, renames one, and tombstones the other (without `--yes-really` purge).
3. **`project_source_bootstrap`** — agent creates a brand-new project, sets it as default, adds a local media source via `projects source add`, and shows the project — proving the source is registered.
4. **`inbox_external_ack_and_retry`** — primer writes a valid inbox JSON file (simulating external approval) and a malformed one. Agent runs `next` to consume the valid one (producing `step_attested` / `item_attested`); the malformed one must move to `.rejected`. One step's `produces` check fails and must be acked with `retry` or `iterate`, not `approve`.
5. **`clean_abort_and_restart`** — agent aborts an active run with `abort --reason`, observes `run_aborted` in events, sees `current_run.json` cleared and lease released, then starts a second run on the same project without manual cleanup.

Supporting harness changes:

- **Priming logic** — a new `tests/agentic/priming.py` (or extension of `runner.py`, whichever is lighter-touch) that runs scenario-specific setup before the actor starts. Three of the 5 scenarios need pre-existing state:
  - `midrun_plan_mutation` needs an active run with a small plan and at least one dispatched step
  - `inbox_external_ack_and_retry` needs a dispatched step + inbox files (one valid, one malformed)
  - `clean_abort_and_restart` needs an active run mid-execution
- **Targeted rubric extensions** ONLY where a failure mode escapes the existing 3 universal checks. Likely candidates:
  - Detect `plan.json` was hand-edited (no corresponding `plan_mutated` event)
  - Verify finalized timeline artifacts carry valid sha256 + size in their manifest

Prefer **per-scenario rubric questions** (in the scenario YAML) over new universal checks. Only add a universal check if the same failure mode plausibly applies across multiple scenarios.

## Scope (OUT — anti-scope)

- Do NOT modify the auditor (`tests/agentic/auditor.py`)
- Do NOT change the three-tier signal taxonomy in `pattern_finder.py`
- Do NOT change the cross-assessor diff (`cross_assessor_diff.py`)
- Do NOT refactor `runner.py` beyond adding priming hooks
- Do NOT change the canonical-bypass detector
- Do NOT add `claim`/`unclaim`, element fork, events corruption, or skills install scenarios (next sprint)
- Do NOT touch any non-test code in `astrid/` — these scenarios run against the existing CLI as-is. Read-only access for understanding behavior is fine.

## Locked decisions

- Scenario YAML format follows existing files (see `tests/agentic/scenarios/idempotent_reattach.yaml` and `cross_pack_composition.yaml` for shape)
- Rubric uses the 3-tier taxonomy: `assessment.enforced` (contract — gates outcome), `assessment.graded` (quality — scalar score), `assessment.observed` (telemetry only)
- Actor model is DeepSeek V4 Pro (unchanged); auditor model is unchanged
- Scenarios run via existing `parallel_runner.py` with per-scenario `ASTRID_HOME` + `ASTRID_PROJECTS_ROOT` isolation
- Total scenario count after this sprint: 20
- Each new scenario gets a `target_orchestrator` or `target_executor` field where applicable, so the canonical-bypass detector applies correctly. For scenarios where the agent is exercising CLI verbs (not running a pack), use `assessment.bypass_exempt: true`.

## Open questions for the planner

1. **Priming infrastructure placement.** Read `tests/agentic/runner.py` and `tests/agentic/parallel_runner.py` to decide whether priming belongs as a new method on the runner, a separate `priming.py` module the runner calls, or a per-scenario shell script the YAML points to. Pick the lighter-touch option that doesn't require touching the runner's core path.
2. **Plan-mutation event sub-types.** Read `astrid/core/task/plan.py` and `astrid/core/task/events.py` to enumerate the exact `plan_mutated` event ops (`add`, `edit`, `remove`, `supersede`) and what fields each carries. The rubric for `midrun_plan_mutation` should reference these by name.
3. **Inbox JSON shape.** Read `astrid/core/task/lifecycle.py` and `astrid/core/task/lifecycle_ack.py` to find the canonical inbox file format. The primer must write valid JSON the runtime will accept.
4. **Abort observability.** Read `astrid/core/task/lifecycle.py` for the `abort` verb's side effects. Confirm what gets cleared (`current_run.json`, lease, etc.) so the rubric can verify each.
5. **Timeline finalize sha.** Read `astrid/core/timeline/` to find where finalize writes the sha256 and how `timelines show --json --verify` exposes the integrity check. Rubric must check the right field.

## Constraints

- Each scenario must complete in ≤ 10 minutes when run solo
- Each scenario must be runnable as `python3 -m tests.agentic.parallel_runner --scenario <name>`
- Rubric questions must be answerable from the captured evidence pack alone — no live system inspection at grading time
- No external network dependencies (no runpod calls, no Supabase live calls). For `project_source_bootstrap`, the local source can be a small fixture file checked into the test scaffolding.
- Each scenario must declare its priming requirements in the YAML (so the runner knows what to set up). New YAML key: `priming:` with sub-fields for what state to create.

## Done criteria

1. 5 new YAML files exist in `tests/agentic/scenarios/` with rubrics covering enforced/graded/observed checks
2. Each scenario runs end-to-end via `parallel_runner --scenario <name>` and produces a complete evidence pack (`stderr.log`, `events.jsonl`, `report.md`, `tree.txt`, `plan.json`, `outcome.json`, `assessment.json`)
3. v14 dogfood (`parallel_runner --all`) completes with 20 scenarios
4. The 5 new scenarios produce verdicts that are EITHER correctly passing OR correctly failing — not vacuous (the rubric must have evaluated meaningful evidence, not all-null verdicts). Sanity-check this by reading `assessment.json` for each new scenario and confirming at least one enforced + one graded question has a non-null answer with a quoted citation.
5. No regression in the existing 15 scenarios' v14 outcomes compared to v13. If a previously-passing scenario fails in v14, investigate and fix or document.
6. Run cross-assessor diff (`cross_assessor_diff.py`) on the v14 run. New scenarios should not introduce new credulity gaps (no DeepSeek-passes / Kimi-flags-evidence-missing patterns).

## Touchpoints

**New files:**
- `tests/agentic/scenarios/midrun_plan_mutation.yaml`
- `tests/agentic/scenarios/timeline_lifecycle_integrity.yaml`
- `tests/agentic/scenarios/project_source_bootstrap.yaml`
- `tests/agentic/scenarios/inbox_external_ack_and_retry.yaml`
- `tests/agentic/scenarios/clean_abort_and_restart.yaml`
- Possibly `tests/agentic/priming.py`

**Files that may be extended (minimal touch only):**
- `tests/agentic/runner.py` — wire priming hook
- `tests/agentic/parallel_runner.py` — pass priming through
- `tests/agentic/universal_checks.py` — only if a check applies across multiple new scenarios

**Reference reads only (no edits):**
- `astrid/core/task/plan.py`, `astrid/core/task/lifecycle.py`, `astrid/core/task/lifecycle_ack.py`, `astrid/core/task/events.py`
- `astrid/core/timeline/`, `astrid/core/project/`
- `tests/agentic/scenarios/idempotent_reattach.yaml`, `tests/agentic/scenarios/cross_pack_composition.yaml`

## Working-tree constraint

The user has substantial uncommitted work in the tree (see `git status`). **Do NOT stash, reset, or checkout anything.** Build on top of the existing working state. Commit the new scenarios + harness changes as a single coherent diff at the end. Respect `.gitignore` — don't add the regenerated `tests/agentic/reports/` artifacts to the commit.
