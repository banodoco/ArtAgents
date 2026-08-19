# Implementation Plan: m5 — CLI and SDK Completion

## Overview

### Goal
Complete the domain surface for the five product families: finish the reference and shot CLI verbs that are missing, freeze the batch retry policy, verify all vocabularies against frozen constants, and ensure the SDK contract tests are fully green.

### Current Repository Shape

The m4 milestone delivered the complete SDK service layer (seven services: projects, timelines, media, tasks, runs, references, shots) and the five product-family CLI parsers plus two manifest-declared nested mounts (shots beneath timelines, references beneath media). The conformance kits for references (5 specs: create/archive/associate/set_primary/link) and shots (4 specs: create/add_item/remove_item/reorder) are already implemented and tested.

**Gaps identified by source inspection:**

1. **Reference `set-primary` CLI verb is missing.** The SDK `ReferencesService.set_primary()` exists and the conformance kit exercises `reference.set_primary`, but the references CLI (`astrid/packs/references/cli.py`) exposes only 7 verbs (create/update/archive/associate/link/list/show). The existing test at `test_domain_cli_media_references.py:1150` explicitly asserts `set-primary` is a *usage error* (unknown verb). The brief lists "primary-canonical replacement" as IN scope.

2. **Shots `show` CLI verb is missing.** The SDK `ShotsService.show()` exists but the shots CLI (`astrid/packs/shots/cli.py`) exposes only 5 verbs (list/create/add/remove/reorder). The test at `test_domain_cli_projects_timelines.py:887` asserts exactly 5 verbs. The brief lists "primary selection" for shots, which maps to the `show` read-model verb (items in stable order, first item is the cover/primary).

3. **Batch retry policy is not frozen.** The `runs retry-failed` CLI already supports both modes (all-eligible by default, `--task` for subset selection), but the policy is not explicitly documented in help text or tested as a frozen decision. The brief says "freeze + implement chosen policy."

4. **Vocabulary verification is incomplete.** `test_m4_contracts.py` verifies `MEDIA_RELATION_KINDS` against the decision artifact but does not verify `REFERENCE_KINDS`, `MEDIA_REFERENCE_ROLES`, `REFERENCE_LINK_KINDS`, or `EVIDENCE_KINDS` against their repository constants and DDL. The brief says "vocabularies verified against real editor fixtures."

5. **Help text is stale.** `_product_help_text()` in `help.py` lists the old verb sets (7 reference verbs, 5 shot verbs) and doesn't mention the batch retry policy.

### Constraints
- No schema changes (DDL is frozen from m1/m3).
- No new top-level families beyond the five.
- No `serve`/`doctor`/`backup`/packaging/teardown (m6).
- Every CLI verb is argument parsing plus exactly one SDK call (no SQL, no repository logic, no domain rules in CLI modules).
- `set_primary` SDK method takes `media_reference_id` (association row id), not `media_id` — the CLI verb must take `--media-reference <id>` to preserve the one-call pattern.

## Main Phase

### Step 1: Add `set-primary` verb to references CLI (`astrid/packs/references/cli.py`)
**Scope:** Small — Complexity: 2

1. **Add** the `_cmd_set_primary` handler that calls `parsed.client.references.set_primary(project, ref, media_reference_id=..., idempotency_key=...)` and renders via `print_result`.
2. **Add** the `_configure_set_primary` parser config: `--project` (required), positional `ref`, `--media-reference` (required, dest=`media_reference`), `--idempotency-key`, `--json`.
3. **Add** `CommandSpec("set-primary", help="Replace the primary canonical media association (one SDK call).", configure=_configure_set_primary)` to the `COMMANDS` tuple — placed after `associate` and before `link` to match the lifecycle order.
4. **Update** the module docstring: "Verbs (exactly these eight...)" and add the `set-primary` line.
5. **Update** the `build_parser` docstring: "Exactly the eight verbs above are registered..."

The verb signature: `astrid media references set-primary --project <proj> <ref> --media-reference <assoc_id> [--idempotency-key <key>] [--json]`

### Step 2: Add `show` verb to shots CLI (`astrid/packs/shots/cli.py`)
**Scope:** Small — Complexity: 2

1. **Add** the `_cmd_show` handler that calls `parsed.client.shots.show(project, shot_id)` and renders via `print_result`.
2. **Add** the `_configure_show` parser config: `--project` (required), positional `shot`, `--json`. No idempotency key (read-only).
3. **Add** `CommandSpec("show", help="Show one shot's full read model with items in stable order.", configure=_configure_show)` to the `COMMANDS` tuple — placed after `list` (reads grouped together) or at the end.
4. **Update** the module docstring: "Verbs (exactly these six...)" and add the `show` line.
5. **Update** the `build_parser` docstring: "Exactly the six verbs above are registered..."

### Step 3: Update product help text (`astrid/core/gateway/help.py`)
**Scope:** Small — Complexity: 1

1. **Update** `_product_help_text()`:
   - Reference line: `media references` → add `set-primary` to the verb list.
   - Shots line: `timelines shots` → add `show` to the verb list.
   - Runs `retry-failed` line: add explicit note about the frozen batch retry policy: "retry-failed retries all eligible failed/expired children by default; use repeatable --task <id> to retry a selected subset."

### Step 4: Update references CLI tests (`tests/v10/test_domain_cli_media_references.py`)
**Scope:** Medium — Complexity: 3

1. **Update** `test_references_parser_has_exactly_seven_verbs_beneath_media` → rename to `_eight_verbs` and add `"set-primary"` to the expected tuple and set.
2. **Change** `test_references_unknown_verb_is_a_usage_error` to use a truly unknown verb (e.g. `"bogus-verb"`) instead of `"set-primary"`.
3. **Add** `set_primary` method to the `_RecordingReferences` fake client class — records the call and returns a `DomainResult.success` with a canned envelope and receipt.
4. **Add** `test_references_set_primary_is_one_sdk_call_with_exact_envelope` — verify one SDK call with correct args, exact envelope keys, receipt command kind.
5. **Add** `test_references_set_primary_forwards_caller_key` — verify `--idempotency-key` is forwarded.
6. **Add** `test_references_set_primary_typed_failure_exits_one` — verify a `terminal_state` or `not_found` error envelope exits 1.
7. **Add** `"references", "set-primary", "--help"` to the `test_media_references_help_is_executable` parametrize list.

### Step 5: Update shots CLI tests (`tests/v10/test_domain_cli_projects_timelines.py`)
**Scope:** Medium — Complexity: 3

1. **Update** `test_shots_parser_has_exactly_five_verbs_beneath_timelines` → rename to `_six_verbs` and add `"show"` to the expected tuple and set.
2. **Add** `show` method to the `_RecordingShots` fake client class — records the call and returns a `DomainResult.success` with a canned shot read model (including items list).
3. **Add** `test_shots_show_is_one_sdk_call_with_exact_envelope` — verify one SDK call with project + shot_id, exact envelope keys.
4. **Add** `test_shots_show_typed_failure_exits_one` — verify a `not_found` error envelope exits 1.
5. **Add** `"shots", "show", "--help"` to the `test_timelines_shots_help_is_executable` parametrize list.
6. **Update** `test_shots_unknown_verb_is_a_usage_error` if it uses a verb that is now valid (check current value).

### Step 6: Add vocabulary verification tests (`tests/v10/test_m5_vocabulary.py`)
**Scope:** Small — Complexity: 2

Create a new test file that verifies the frozen CLI vocabularies match the repository-level constants exactly — so a drift between CLI `choices=` and the repository vocabulary is caught:

1. **Test** `REFERENCE_KINDS` in the references CLI matches `astrid.packs.references.repository.REFERENCE_KINDS`.
2. **Test** `MEDIA_REFERENCE_ROLES` in the references CLI matches `astrid.packs.references.repository.MEDIA_REFERENCE_ROLES`.
3. **Test** `REFERENCE_LINK_KINDS` in the references CLI matches `astrid.packs.references.repository.REFERENCE_LINK_KINDS`.
4. **Test** `MEDIA_RELATION_KINDS` in the media CLI matches `astrid.core.cli.domain_media.MEDIA_RELATION_KINDS`.
5. **Test** `EVIDENCE_KINDS` is the frozen five-kind tuple (`observation/measurement/validation/decision/error`) from `astrid.core.repositories.evidence`.
6. **Test** CLI choices are non-empty tuples of non-empty strings (no accidental empty vocabulary).

### Step 7: Add batch retry policy tests (`tests/v10/test_domain_cli_tasks_runs.py`)
**Scope:** Small — Complexity: 2

1. **Add** `test_runs_retry_failed_default_is_all_failed_children` — verify that without `--task`, `selected_task_ids=None` is passed (all eligible).
2. **Add** `test_runs_retry_failed_subset_passes_selected_task_ids` — verify `--task` (repeatable) passes the correct list.
3. **Add** `test_runs_retry_failed_help_documents_batch_policy` — verify `--help` output mentions the all-failed default and subset option.
4. **Add** `test_tasks_retry_is_single_task_only` — verify `tasks retry` takes exactly one positional `task_id` and does not accept `--run` (the batch path is through `runs retry-failed`).

### Step 8: Run full v10 test suite and fix regressions
**Scope:** Small — Complexity: 2

1. **Run** `python -m pytest tests/v10/ -x --tb=short` to catch any regressions from the verb additions and test changes.
2. **Run** `python -m pytest tests/v10/test_domain_cli_surface.py tests/v10/test_domain_cli_media_references.py tests/v10/test_domain_cli_projects_timelines.py tests/v10/test_domain_cli_tasks_runs.py tests/v10/test_m5_vocabulary.py tests/v10/test_m4_contracts.py -v` for focused verification.
3. **Fix** any test that asserts a verb count or verb list that changed due to the new verbs.

## Execution Order
1. Steps 1–2: Add the two missing CLI verbs (can be done in parallel — they touch different files).
2. Step 3: Update help text to reflect the new verbs.
3. Steps 4–5: Update the CLI tests for the new verbs (must follow steps 1–2).
4. Steps 6–7: Add vocabulary and batch retry policy tests.
5. Step 8: Run the full suite and fix any regressions.

## Validation Order
1. Run the new vocabulary tests first (cheapest, no database needed).
2. Run the CLI verb tests (fake client, no database needed).
3. Run the full v10 suite (includes conformance and repository tests that use real databases).

## Questions

1. **`set-primary` argument: `--media-reference <assoc_id>` vs `--media <media_id>`?** The SDK `set_primary` takes `media_reference_id` (the association row id). Taking `--media <media_id>` would require a pre-read (two SDK calls), breaking the one-call-per-verb pattern. I assume `--media-reference <assoc_id>` is correct — the user calls `show` first to see association ids, then `set-primary` with the target association id. If the brief intends `--media <media_id>`, the SDK would need a convenience method (a scope change).

2. **Batch retry: extend `tasks retry` with `--run` or freeze `runs retry-failed` as canonical?** The brief says "freeze + implement chosen policy for `tasks retry` over a run group." The `runs retry-failed` CLI already implements both modes (all-eligible default, `--task` subset). I assume the "freeze" means documenting `runs retry-failed` as the canonical batch retry path and adding tests, NOT adding a `--run` mode to `tasks retry` (which would create an overlapping path and couple the tasks family to the runs service). If the brief intends a `--run` mode on `tasks retry`, this is a small additional change to `domain_tasks.py`.

3. **Shots "primary selection" interpretation.** The shots schema has no `is_primary` column. I interpret "primary selection" as the `show` read-model verb (the shot's items in stable order, where the first item is the primary/cover). If the brief intends a `set-primary` verb for shots (selecting a primary item), this would require a schema change (out of scope — no schema changes allowed). The `show` verb is the safe interpretation.

## Assumptions

1. The `set-primary` CLI verb takes `--media-reference <association_id>` (matching the SDK API), not `--media <media_id>`.
2. The batch retry policy is frozen as: `runs retry-failed` is the canonical batch retry path. Default = all eligible failed/expired children. Optional `--task <id>` (repeatable) = selected subset. The `tasks retry` verb stays single-task only.
3. "Primary selection" for shots maps to the `show` read-model verb, not a new mutation verb (no schema changes).
4. "Clean-machine docs examples" means the CLI `--help` output is complete and truthful for all five families — not that external markdown documentation needs to be created (m7 verifies docs).
5. The existing conformance suites (`test_reference_conformance.py`, `test_shot_conformance.py`) already pass and cover the editorial acceptance (event/head/receipt/replay/mismatch/crash). M5 does not need to re-prove conformance — it completes the CLI surface and vocabulary verification.

## Success Criteria

```json
[
  {
    "criterion": "References CLI exposes exactly 8 verbs: create/update/archive/associate/set-primary/link/list/show",
    "priority": "must",
    "requires": ["run_tests", "read_files"]
  },
  {
    "criterion": "Shots CLI exposes exactly 6 verbs: list/create/add/remove/reorder/show",
    "priority": "must",
    "requires": ["run_tests", "read_files"]
  },
  {
    "criterion": "references set-primary makes exactly one SDK call to client.references.set_primary with correct project/ref/media_reference_id/idempotency_key args",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "shots show makes exactly one SDK call to client.shots.show with correct project/shot_id args",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "All existing v10 tests pass after the new verbs are added (no regressions)",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "Product help text (_product_help_text) lists all verbs for all five families including set-primary and show",
    "priority": "must",
    "requires": ["run_tests", "read_files"]
  },
  {
    "criterion": "Vocabulary verification tests confirm CLI choices match repository constants for REFERENCE_KINDS, MEDIA_REFERENCE_ROLES, REFERENCE_LINK_KINDS, MEDIA_RELATION_KINDS, EVIDENCE_KINDS",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "Batch retry policy is frozen: runs retry-failed defaults to all-eligible; --task subset is optional; tasks retry is single-task only",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "Each new CLI verb's --help exits 0 and produces non-empty output",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "Typed error envelopes (not_found, terminal_state) for set-primary and show exit with code 1",
    "priority": "must",
    "requires": ["run_tests"]
  },
  {
    "criterion": "No schema changes, no new top-level families, no SQL in CLI modules",
    "priority": "should",
    "requires": ["read_files", "parse_diff"]
  },
  {
    "criterion": "Reference and shot conformance suites remain green (no conformance regressions)",
    "priority": "should",
    "requires": ["run_tests"]
  },
  {
    "criterion": "SDK contract tests (test_m4_contracts.py) remain green",
    "priority": "should",
    "requires": ["run_tests"]
  }
]
```

## Changed Surfaces

```
astrid/packs/references/cli.py
astrid/packs/shots/cli.py
astrid/core/gateway/help.py
tests/v10/test_domain_cli_media_references.py
tests/v10/test_domain_cli_projects_timelines.py
tests/v10/test_domain_cli_tasks_runs.py
tests/v10/test_m5_vocabulary.py
```

## Test Blast Radius

```json
{
  "strategy": "scoped",
  "selectors": [
    {
      "kind": "path",
      "value": "tests/v10/test_domain_cli_media_references.py",
      "reason": "Reference CLI tests — verb count, set-primary verb, help, unknown-verb test all change"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_domain_cli_projects_timelines.py",
      "reason": "Shots CLI tests — verb count, show verb, help parametrize list change"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_domain_cli_tasks_runs.py",
      "reason": "Batch retry policy tests added; existing retry tests verified"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_domain_cli_surface.py",
      "reason": "Product surface tests — help text references verb lists that changed"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_m5_vocabulary.py",
      "reason": "New vocabulary verification test file"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_m4_contracts.py",
      "reason": "SDK contract tests — verify no regressions from CLI changes"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_reference_conformance.py",
      "reason": "Reference conformance — verify set_primary conformance still green"
    },
    {
      "kind": "path",
      "value": "tests/v10/test_shot_conformance.py",
      "reason": "Shot conformance — verify no regressions"
    }
  ],
  "changed_surfaces": [
    "astrid/packs/references/cli.py",
    "astrid/packs/shots/cli.py",
    "astrid/core/gateway/help.py",
    "tests/v10/test_domain_cli_media_references.py",
    "tests/v10/test_domain_cli_projects_timelines.py",
    "tests/v10/test_domain_cli_tasks_runs.py",
    "tests/v10/test_m5_vocabulary.py"
  ],
  "full_suite_fallback": false,
  "rationale": "The changes are scoped to two CLI parser modules (references, shots), one help module, and their tests. The CLI modules are thin argparse+SDK-call adapters with no SQL or repository logic, so the blast radius is limited to the CLI test files and the surface/help tests. Conformance and contract tests are included as regression guards but are not expected to change."
}
```
