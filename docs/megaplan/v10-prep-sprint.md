# Astrid v10-prep sprint — three-tier signal model + UX polish

**Profile:** `solo/light` (tier 1 DeepSeek end-to-end, light robustness — plan → critique → revise → finalize → execute).

## Outcome

Restructure the agentic test pipeline to separate three different jobs that are currently conflated into one pass/fail verdict: **contracts** (binary, gate the test), **quality** (scalar, graded by assessor), and **observations** (metadata, never gate). Plus three small discoverability fixes that close known gaps. After this lands, v10 dogfood will report each scenario along three axes — `outcome: passed/failed_contract/rejected`, `quality_score: 0.0–1.0`, and observation metadata — instead of a soft-aggregated pass/fail that mixes contract violations with pedantic proxies.

## Scope (~5 hours of mechanical multi-file work)

**IN:**
1. **Close canonical-bypass import gap**: move `guard_canonical_entrypoint()` call from inside each pack's `__main__` block to module-top (so `from astrid.packs.X import main` also triggers the guard).
2. **Discoverability triplet** (3 small UX fixes):
   - `astrid help` (no dashes) routes to `--help` instead of falling through to legacy `--video/--brief` argparse.
   - Top-level `--help` gains one-line descriptions per subcommand group ("orchestrators — multi-step pipelines", "executors — single-step CLI tools", "elements — reusable building blocks", etc.).
   - `astrid next` shows ALL available orchestrators after run completion (drop the "N more" truncation).
3. **Restructure rubrics**: add `assessment.enforced` / `assessment.graded` / `assessment.observed` sections to every scenario YAML; migrate existing questions into the right bucket.
4. **Auditor honors the new sections**: `outcome` field gated only by `acceptance` + `assessment.enforced`; `quality_score` scalar computed from `assessment.graded`; `assessment.observed` becomes pure metadata.
5. **Drop runner-side report-length re-prompt**: remove the soft enforcement that's been proven low-leverage; quality assessor questions replace it.
6. **Pattern_finder reports by section**: `run.md` gets three clear sections — *Contract failures*, *Quality patterns*, *Observations* — instead of one flat friction list.

**OUT (explicit anti-scope):**
- No new scenarios, no new universal_checks, no new pack run.py modules.
- No commits, no stashes, no resets — working tree has 150+ uncommitted files; preserve them.
- No tightening of the `_eval_tool_used` narrative fallback (still load-bearing until assessor reliability is proven).
- No stateful contract enforcement (e.g. `author check` cadence) — separate sprint.
- No `executors new` scaffolding enforcement — discoverability fix is better, deferred.
- No changes to `assessor.py` itself; only the YAML schema it reads.
- No fix to the `generate_image/executor.yaml` float-type bug (separately ticketed).
- No v10 dogfood — that's the user's separate kickoff.

## Locked design decisions

### Three-tier signal model (the framework)

Every signal in the rubric falls into one of three buckets:

| Bucket | Type | Source | Response when violated |
|---|---|---|---|
| **`acceptance`** + **`assessment.enforced`** | Contract | Mechanical or assessor | **Gate**: scenario fails or is rejected |
| **`assessment.graded`** | Quality | Assessor (semantic) | **Score**: contributes 0-1 to `quality_score`, never gates |
| **`assessment.observed`** | Telemetry | Mechanical | **Record**: metadata only, never gates |

The principle: a measurement is only as strict as its job demands. Contracts deserve hard rejection; quality deserves grading; telemetry deserves recording. Mixing them into one pass/fail destroys signal.

### Categorization rules for rubric migration (Fix #3)

Apply these when migrating each existing rubric question into its new bucket:

- **`enforced`** — load-bearing contracts. Only 1-3 questions per scenario. Examples: `invoked_via_canonical_cli`, `produced_required_artifact`, `did_not_invoke_forbidden_path`.
- **`graded`** — semantic quality the assessor can judge. Examples: `report_section_N_substantive`, `chose_right_tool_first`, `discovery_path_was_efficient`.
- **`observed`** — metadata, never gates. Examples: `report_line_count`, `shell_calls_count`, `discovery_steps_count`, `canonical_bypass_form` (the pattern, not the binary).

Specific migrations to perform across all 13 scenarios:

- Drop hard line-count thresholds (`report_too_short`, `deliverable_shape.line_count` ≥30 gates) → move to `observed` as `report_line_count` (integer only, no gate).
- Drop shell-call gates (`shell_calls_over_40`, `shell_calls_over_60`) → move to `observed` as `shell_calls_count`.
- Keep canonical-bypass detection gating, but split: `canonical_path_bypass: <bool>` → in `enforced` if scenario has a clear canonical path; `canonical_bypass_form: <string>` → in `observed` for forensics regardless.
- Substance/discoverability questions → split into `graded` (semantic quality) vs `observed` (mechanical counters).

If a scenario currently has only mechanical questions (no semantic ones), it's fine to land Phase 1 of rubric restructure with `graded` empty for that scenario — the assessor will produce `quality_score: null` and the runner will treat the scenario as "graded by enforced criteria only."

### Auditor's verdict logic (Fix #4)

```
outcome = (
    "rejected"     if runner wrote .rejected.txt marker (canonical-bypass re-prompt failed)
    "failed_contract" if any acceptance criterion failed OR any assessment.enforced returned False
    "passed"          if all acceptance + all assessment.enforced returned True
    "needs_review"    if any assessment.enforced returned ungraded (null)
)

quality_score = mean(verdict for verdict in assessment.graded if verdict is not null)
                or null if no graded questions

metadata = { ... assessment.observed values ... }
```

`summary.json` gains top-level `outcome`, `quality_score`, `metadata` fields per agent. Existing `passed: bool` field stays for backward compat but is now derived (`outcome == "passed"`).

### Pattern_finder output structure (Fix #6)

`run.md` becomes three sections:

```markdown
# v10 dogfood synthesis

**Outcomes:** X passed, Y failed_contract, Z rejected, W needs_review (of 13 scenarios).
**Mean quality score:** 0.NN (range 0.NN–0.NN).

## Contract failures
- [MAJOR] <pattern_name> — Z scenarios — <suggested fix>
  ...

## Quality patterns
- <pattern_name> (mean score 0.NN, N scenarios below 0.5) — <observation>
  ...

## Observations
- Median shell calls: NN (p90: NN).
- Median report lines: NN (range NN–NN).
- Canonical-bypass forms seen: <list>
  ...
```

Sorted by section: contract failures first (most actionable), then quality patterns, then observations.

### Discoverability fixes (Fix #2)

- `astrid help` route: add a no-arg subparser named `help` that internally calls the argparser's `print_help()`. ~5 lines in `astrid/__main__.py` or wherever the top-level argparse lives.
- One-line group descriptions: edit the `description=` strings on each subparser group in the top-level help block. Most groups already have docstrings in their module's CLI file — surface them. Format: `<group_name>   # one-line description`.
- `astrid next` truncation: locate the post-completion handoff in `astrid/core/task/lifecycle.py` (the `_print_post_completion_handoff` helper or similar). Currently shows top-N + "N more"; change to show all available orchestrators.

### Sprint A canonical-bypass closure (Fix #1)

In each pack's `run.py`, move:
```python
if __name__ == "__main__":
    from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
    guard_canonical_entrypoint("<pack_id>")
    main()
```
to module-top:
```python
from astrid.packs._canonical_entrypoint import guard_canonical_entrypoint
guard_canonical_entrypoint("<pack_id>")

# ... rest of module ...

if __name__ == "__main__":
    main()
```

The guard checks `ASTRID_INTERNAL_INVOCATION` env var and exits 2 if absent. Moving it to module-top means `from astrid.packs.X.run import main` also triggers it.

**Caveat**: this might break legitimate test imports that don't set the env var. Mitigation: tests that import pack run.py modules directly should set `ASTRID_INTERNAL_INVOCATION=1` in their fixture. Audit `tests/` for imports of `astrid.packs.<X>.run` and update fixtures as needed.

## Open questions (none — locked spec)

All design decisions resolved above. If the executor hits something undecided, it's a brief gap; flag and stop.

## Constraints

- Working tree has 150+ uncommitted files; do NOT stash, reset, checkout, or otherwise touch git state.
- No commit. The user owns staging.
- Tests must still pass: `pytest tests/ --ignore=tests/agentic/ -x` — pre-existing breakages (the `generate_image` float-type, `test_unbound_next_prints_discovery_hint`) are allowed.
- The brief tightening for report-length in v6 sprint can stay in the briefs (informational); just don't have the runner enforce it.

## Done criteria

1. All 65 pack `run.py` modules call `guard_canonical_entrypoint()` at module-top, not just under `__main__`. Verify: `python -c "from astrid.packs.builtin.hype.run import main"` exits 2 with the remediation message.
2. `astrid help` (no dashes) prints the same content as `astrid --help`.
3. Top-level `astrid --help` shows one-line descriptions per subcommand group.
4. `astrid next` after run-completion lists ALL available orchestrators (no "N more" truncation).
5. Every scenario YAML in `tests/agentic/scenarios/` has `assessment.enforced`, `assessment.graded`, `assessment.observed` sections (one or more may be empty per scenario).
6. `tests/agentic/auditor.py` produces summary.json with top-level `outcome`, `quality_score`, `metadata` fields; existing `passed: bool` derived from `outcome`.
7. `tests/agentic/runner.py` no longer dispatches re-prompts for report shape (`_check_report_shape` removed or its callsite removed); canonical-bypass re-prompt stays.
8. `tests/agentic/pattern_finder.py` produces three-section run.md (Contract failures / Quality patterns / Observations).
9. `pytest tests/ --ignore=tests/agentic/ -x` passes modulo pre-existing breakages.

## Touchpoints

- **Pack run.py module-top refactor (~65 files)**: `astrid/packs/**/run.py`
- **Help routing**: `astrid/__main__.py` (or wherever the top-level argparser is defined)
- **`astrid next` truncation**: `astrid/core/task/lifecycle.py` (look for `_print_post_completion_handoff` or similar, near `_list_orchestrator_ids`)
- **Rubric YAMLs (13 files)**: `tests/agentic/scenarios/*.yaml`
- **Auditor**: `tests/agentic/auditor.py` (extend `audit_scenario` to populate new fields)
- **Runner**: `tests/agentic/runner.py` (remove `_check_report_shape` and its re-prompt dispatch; keep `_check_canonical_bypass`)
- **Pattern_finder**: `tests/agentic/pattern_finder.py` (update prompt template to ask for three sections)
- **Schema**: `tests/agentic/scenarios/_schema.yaml` (document the new `assessment.enforced`/`graded`/`observed` shape)

## Anti-scope (do not do)

- No adding new rubric questions per scenario; only categorize existing ones.
- No changes to `assessor.py` (only the YAML it reads).
- No introduction of `pytest-fixtures` for the pack-import test breakage; only set the env var in existing fixture code.
- No refactoring of `lifecycle.py` beyond the `astrid next` list truncation change.
- No editing the briefs in `tests/agentic/briefs/`; v6 brief preamble stays informational.
- No new scenarios.
- No commits, no stashes, no resets.

## Why solo/light

- Multi-file mechanical work with stable patterns. Decisions all pre-resolved above.
- Critique pass earns ~$0.30 by catching cross-file consistency issues (did the YAML migration apply to ALL 13 scenarios? did the auditor wire all three new fields?). 6 fixes across ~80 files mean the planner can drop a file.
- No security, no migration, no public API. No premium phases needed.
- Brief is essentially the plan; planner mostly sequences and assigns.

Shorthand: **`solo/light`**.

## Tactical note on megaplan local install

`megaplan auto` has been intermittently buggy this session — Sprint A's plan phase got stuck for 50+ minutes with no progress before a direct sub-agent landed the same work in 11 min. The dispatching sub-agent has explicit fallback authority: if `megaplan auto` doesn't transition state within 15 minutes of init, kill the harness and complete the work directly. The brief is detailed enough that direct execution is reliable.
