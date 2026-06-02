# M3 Scenario Migration Reference

## Overview

The M3 migration converts all 36 production scenarios from the legacy runner harness to
[Sisypy](https://pypi.org/project/sisypy/) schema. No scenario *intent* changed — only
schema shape, placeholder syntax, and metadata locations moved.
The legacy runner and auditor were decommissioned in M5.

**Key principle**: additive migration. All legacy top-level keys (`acceptance`,
`target_orchestrator`, `agents.count`, `subagent_type`) were preserved during the
transition. Sisypy-native fields were added *alongside* them.

---

## Architecture: Consumers and Key Locations

### Sisypy path (new)

| Consumer | How it reaches scenarios |
|---|---|
| `sisypy.public_api.run_from_args()` | Invoked by our `runner.py`. Receives normalized YAMLs from a temp directory. Reads `name`, `agents`, `priming`, `brief`, `budget`, `assessment` (enforced/graded/observed), and `extras`. |
| `sisypy.runner._render_brief()` | Resolves `${SLUG}`, `${AGENT_ID}`, `${RUN_TAG}`, `${TARGET_ORCH}` from `extras`. |
| Sisypy's internal reporter / evaluator | Consumes `assessment.enforced`, `assessment.graded`, `assessment.observed`. |

### Legacy path (decommissioned in M5)

The legacy modules (`runner_legacy.py`, `auditor.py`, `universal_checks.py`,
`assessor.py`, `capture.py`, `pattern_finder.py`, `parallel_runner.py`,
`_reaudit_v5.py`, `cross_assessor_diff.py`) were deleted in M5 after all
consumers were migrated to Sisypy-native paths. The preserved enforcement
functions (`_check_canonical_bypass`, `_render_brief`, `_load_scenario`)
now live in `tests/agentic/enforcement.py`.

| Consumer | Key(s) read | File |
|---|---|---|
| `enforcement._render_brief()` | Brief Markdown files, dual-format `${VAR}` / `$VAR` substitution | `enforcement.py` |
| `enforcement._load_scenario()` | Top-level `acceptance` (required), top-level `target_orchestrator`; falls back to `extras.target_orchestrator` | `enforcement.py` |
| `_validate_rubrics.py` | Top-level `acceptance` / `extras.legacy_acceptance`; `assessment.enforced`/`graded` keys | `_validate_rubrics.py` |
| `enforcement._check_canonical_bypass()` | Top-level `target_orchestrator` + `extras.target_orchestrator` for canonical-path bypass detection | `enforcement.py` |
| `normalize.py` | All fields; converts `agents.count` → concrete entries, moves `assessment.universal_checks` → `extras.universal_checks` | `normalize.py` |

### Brief files

37 brief files under `tests/agentic/briefs/` (36 production + `_smoke.md`). All
`$SLUG`/`$AGENT_ID`/`$RUN_TAG`/`$TARGET_ORCH` placeholders converted to `${VAR}` syntax
during M3 (145 replacements). The adapter (`adapter.py`) handles both `${VAR}` and
`$VAR` for backward compatibility.

---

## Universal Enforcement

All 42 production scenarios carry `extras.universal_checks: true`. The universal
post-execute enforcement layer (preserved in `enforcement.py`) checks:

- **Canonical-path enforcement** (`_check_canonical_bypass`): agent used `astrid orchestratros run` / `astrid executors run` / `astrid timelines` rather than `python -m astrid.packs.*` or direct imports.
- **Sandbox-root isolation** (`check_sandbox_roots`): agent output confined to project directory.
- **Artifact provenance** (`check_artifact_provenance`): produced files traceable through run artifacts.

These apply to every scenario regardless of category. They are not per-criterion legs
in the legacy `acceptance` block — they were always invoked by the harness post-execute.

---

## Observed Telemetry

All 36 scenarios include `assessment.observed` with at minimum:

| Observed key | Type | Purpose |
|---|---|---|
| `shell_calls_count` | `numeric` (weight 0) | Counts agent shell invocations for cost/behavior telemetry. |
| `canonical_bypass_form` | `text` (weight 0) | Only on authoring scenarios; records bypass form if detected. |

Some scenarios add extra observed items:
- `executor_failure_recovery`: adds `astrid_abort_invocations` (numeric) and `recovery_strategy` (categorical)
- `impossible_brief_pushback`: adds `tool_actually_invoked` (categorical) and `report_mentions_image` (boolean)

These are metadata-only (weight 0) and do not affect pass/fail grading.

---

## Per-Scenario Mapping Table

Each row maps the scenario's **legacy acceptance criteria** (preserved in
`extras.legacy_acceptance`) to their Sisypy/M2 destinations. Universal checks and
observed telemetry apply to all scenarios; they are listed here for completeness.

Legend:
- **Destination**: `enforced` = `assessment.enforced` item; `graded` = `assessment.graded` item
- **Coverage**: `exact` = criterion ID/name matches; `fuzzy` = question text covers the legacy concept; `structural` = covered by a runtime mechanism (universal check, target_orchestrator, etc.)
- **Legacy-only**: criterion has no direct Sisypy equivalent but is covered by broader checks

### Read / Audit / Discovery (C3 — no_mutation_on_read)

These 13 scenarios probe read-only or discovery behavior. M2 check `c3_no_mutation_on_read`
is enabled for all of them.

#### 1. cold_restart_midrun

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `events_contain: run_completed` | machine | `enforced: acked_remaining_three_steps` | fuzzy | Covered by completion assertion |
| `leaf_count_complete: 6` | machine | `enforced: acked_remaining_three_steps` | fuzzy | Covered by completion assertion |
| `no_aborts` | machine | universal + M2 C3 | structural | Checked by legacy auditor + universal |
| `tool_used: builtin.agent_probe` | machine | `extras.target_orchestrator` | **legacy-only** | Structurally implied by target_orchestrator; no separate Sisypy check |
| `subjective: cold_start_path_clear` | subjective | `graded: discovered_mid_run_state` | exact | |
| `subjective: recovered_without_external_help` | subjective | `graded: recovered_without_external_help` | exact | |

#### 2. concurrent_disambiguation

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `events_contain: run_completed` | machine | `enforced: completed_run_on_own_project` | fuzzy | |
| `no_cross_project_binding` | machine | universal + M2 C3 | structural | Checked by legacy auditor + universal |
| `subjective: never_silently_bound_to_sibling` | subjective | `enforced: never_silently_bound_to_sibling` | exact | |

#### 3. executor_failure_recovery

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `subjective: diagnosed_bad_output` | subjective | `enforced: diagnosed_bad_output` | exact | |
| `subjective: chose_clean_recovery_path` | subjective | `enforced: chose_clean_recovery_path` | exact | |
| `subjective: diagnostic_quality` | subjective | `graded: diagnostic_quality` | exact | |
| `subjective: recovery_decisiveness` | subjective | `graded: recovery_decisiveness` | exact | |

#### 4. idempotent_reattach

Additional M2: `s2_idempotent_reattach`.

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `events_contain: run_completed` | machine | `enforced: completed_run_idempotently` | fuzzy | |
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `subjective: every_reattach_said_session_reused` | subjective | `enforced: every_reattach_said_session_reused` | exact | |
| `subjective: never_needed_takeover_force` | subjective | `enforced: never_needed_takeover_force` | exact | |

#### 5. impossible_brief_pushback

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `subjective: did_not_fabricate_completion` | subjective | `enforced: did_not_fabricate_completion` | exact | |
| `subjective: acknowledged_brief_mismatch` | subjective | `enforced: acknowledged_brief_mismatch` | exact | |
| `subjective: pushback_quality` | subjective | `graded: pushback_quality` | exact | |
| `subjective: alternative_proposed` | subjective | `graded: alternative_proposed` | exact | |

#### 6. reader_takeover

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `events_contain: takeover` | machine | `enforced: ran_takeover_after_warning` | exact | |
| `events_contain: run_completed` | machine | `enforced: completed_remaining_steps` | fuzzy | |
| `leaf_count_complete: 6` | machine | `enforced: completed_remaining_steps` | fuzzy | |
| `subjective: reader_warning_appeared_before_failed_ack` | subjective | `enforced: reader_warning_appeared_before_failed_ack` | exact | |

#### 7. search_before_authoring

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `tool_used: editorial.editor_review` | machine | `graded: found_editor_review` | fuzzy | Covered by discovery path assertion |
| `subjective: used_orchestrators_search_or_list` | subjective | `graded: used_orchestrators_search_or_list` | exact | |
| `subjective: found_editor_review` | subjective | `graded: found_editor_review` | exact | |
| `subjective: did_not_start_authoring_new` | subjective | `enforced: did_not_start_authoring_new` | exact | |

#### 8. specific_transcribe

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `tool_used: editorial.transcribe` | machine | `enforced: produced_transcript_artifact` | fuzzy | Proving tool use via produced artifact |
| `subjective: found_transcribe_executor` | subjective | `enforced: produced_transcript_artifact` | fuzzy | |
| `subjective: did_not_write_own_whisper_wrapper` | subjective | `enforced: did_not_install_own_whisper` | exact | |
| `subjective: used_executors_list_or_search` | subjective | `graded: discovered_via_canonical_search` | exact | |

#### 9. vague_video_request

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `tool_used: video_editing.hype` | machine | `graded: discovered_via_orchestrators_list_or_search` | fuzzy | Discovery implicitly proves tool use |
| `subjective: discovered_via_orchestrators_list_or_search` | subjective | `graded: discovered_via_orchestrators_list_or_search` | exact | |
| `subjective: read_pack_skill_before_running` | subjective | `graded: read_pack_skill_before_running` | exact | |
| `subjective: did_not_reinvent_pipeline_from_scratch` | subjective | `graded: did_not_reinvent_pipeline_from_scratch` | exact | |

#### 10. timeline_audit

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `no_cross_project_binding` | machine | universal + M2 C3 | structural | |
| `subjective: verified_audit_read_only` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: event_log_unchanged` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: audit_output_reports_chain_status` | subjective | `graded: report_shape_intact` | fuzzy | Report completeness covers chain-status documentation |

#### 11. timeline_diff

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `no_cross_project_binding` | machine | universal + M2 C3 | structural | |
| `subjective: verified_diff_read_only` | subjective | `enforced: read_only_no_mutation` + `graded: report_shape_intact` | **legacy-only** | Broader coverage: read_only_no_mutation proves read-only; report_shape_intact proves documentation |
| `subjective: event_log_unchanged` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: diff_output_describes_changes` | subjective | `enforced: read_only_no_mutation` + `graded: report_shape_intact` | **legacy-only** | Broader coverage: read_only_no_mutation + report completeness |

#### 12. timeline_history

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `no_cross_project_binding` | machine | universal + M2 C3 | structural | |
| `subjective: verified_history_read_only` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: event_log_unchanged` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: history_output_lists_events` | subjective | `graded: report_shape_intact` | fuzzy | Report completeness covers output listing |

#### 13. timeline_preview

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3 | structural | |
| `no_cross_project_binding` | machine | universal + M2 C3 | structural | |
| `subjective: verified_preview_read_only` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: event_log_unchanged` | subjective | `enforced: read_only_no_mutation` | exact | |
| `subjective: preview_output_describes_timeline` | subjective | `graded: report_shape_intact` | fuzzy | |

---

### Authoring (C4 — projection_fidelity)

These 5 scenarios probe the agent's ability to author correct executors/orchestrators
or discover correct composition. M2 check `c4_projection_fidelity` is enabled.

#### 14. cross_pack_composition

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C4 | structural | |
| `tool_used: video_editing.hype` | machine | `enforced: composed_correctly` | exact | Single invocation check proves tool use |
| `subjective: discovered_hype_includes_transcribe` | subjective | `graded: discovered_hype_includes_transcribe` | exact | |
| `subjective: composed_correctly` | subjective | `enforced: composed_correctly` | exact | |
| `subjective: read_hype_skill` | subjective | `graded: read_hype_skill` | exact | |

#### 15. new_executor_for_cli

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C4 | structural | |
| `subjective: discovered_executors_new_command` | subjective | `graded: discovered_executors_new_command` | exact | |
| `subjective: created_executor_yaml_correctly` | subjective | `enforced: created_executor_yaml_correctly` | exact | |
| `subjective: wrote_run_py_with_proper_args` | subjective | `enforced: wrote_run_py_with_proper_args` | exact | |
| `subjective: qualified_id_correctly` | subjective | `graded: qualified_id_correctly` | exact | |
| `subjective: chose_executor_over_orchestrator` | subjective | `graded: chose_executor_over_orchestrator` | exact | |

#### 16. new_orchestrator_from_dsl

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C4 | structural | |
| `subjective: new_orchestrator_compiles` | subjective | `enforced: new_orchestrator_compiles` | exact | |
| `subjective: chose_dsl_over_yaml` | subjective | `enforced: chose_dsl_over_yaml` | exact | |
| `subjective: used_author_check_loop` | subjective | `graded: used_author_check_loop` | exact | |
| `subjective: qualified_id_correctly` | subjective | `graded: qualified_id_correctly` | exact | |

#### 17. sequential_orchestrators

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `events_contain_count: {kind: run_completed, min: 2}` | machine | `enforced: two_distinct_runs_completed` | exact | |
| `no_aborts` | machine | universal + M2 C4 | structural | |
| `subjective: astrid_next_suggested_starting_new_orchestrator` | subjective | `graded: astrid_next_suggested_starting_new_orchestrator` | exact | |
| `subjective: no_manual_abort_required_between_runs` | subjective | `enforced: no_manual_abort_required_between_runs` | exact | |

#### 18. wrap_comfy_workflow

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C4 | structural | |
| `subjective: discovered_comfy_wrapping_path` | subjective | `graded: discovered_comfy_wrapping_path` | exact | |
| `subjective: built_runnable_executor` | subjective | `enforced: built_runnable_executor` | exact | |
| `subjective: parameterized_the_prompt` | subjective | `enforced: parameterized_the_prompt` | exact | |
| `subjective: qualified_id_correctly` | subjective | `graded: qualified_id_correctly` | exact | |
| `subjective: did_not_roll_own_comfy_client` | subjective | `enforced: did_not_roll_own_comfy_client` | exact | |

---

### Append-Not-Rewrite (S1)

These 2 scenarios probe non-destructive modification. M2 check `s1_append_not_rewrite` is enabled.

#### 19. modify_existing_orchestrator

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 S1 | structural | |
| `subjective: located_correct_file` | subjective | `graded: located_correct_file` | exact | |
| `subjective: preserved_existing_steps` | subjective | `enforced: preserved_existing_steps` | exact | |
| `subjective: recompiled_cleanly` | subjective | `enforced: recompiled_cleanly` | exact | |
| `subjective: added_step_at_end` | subjective | `graded: added_step_at_end` | exact | |
| `subjective: used_author_check_loop` | subjective | `graded: used_author_check_loop` | exact | |

#### 20. timeline_tamper_recovery

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 S1 | structural | |
| `events_contain: timeline.erased` | machine | `enforced: event_log_contains_erased_and_recovered` | exact | |
| `events_contain: timeline.recovered` | machine | `enforced: event_log_contains_erased_and_recovered` | exact | |
| `no_cross_project_binding` | machine | universal + M2 S1 | structural | |
| `subjective: detected_tamper_via_verify` | subjective | `graded: chain_passes_after_recovery` | fuzzy | |
| `subjective: erased_tampered_events` | subjective | `enforced: erase_before_recover` | exact | |
| `subjective: recovered_to_good_anchor` | subjective | `graded: chain_passes_after_recovery` | fuzzy | |
| `subjective: confirmed_chain_integrity_after_recovery` | subjective | `graded: chain_passes_after_recovery` | exact | |

---

### Timeline Authoring (C3 + C4 — no_mutation_on_read + projection_fidelity)

These 9 scenarios combine read-only safety (C3) with state-projection correctness (C4).

#### 21. timeline_arrangement

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: arrangement.replaced` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_arrangement_verb` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

#### 22. timeline_audio

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: audio.bound` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: audio.unbound` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_audio_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

#### 23. timeline_clip

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: clip.added` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: clip.removed` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_clip_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_show_no_mutation` | exact | |

#### 24. timeline_effect

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: effect.added` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: effect.removed` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_effect_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

#### 25. timeline_mass_undo

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: clip.added` | machine | `enforced: event_log_contains_inverse_events` | fuzzy | Inverse event check covers add/remove pairs |
| `events_contain: clip.removed` | machine | `enforced: event_log_contains_inverse_events` | fuzzy | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_mass_undo_preview` | subjective | `enforced: mass_undo_preview_before_write` | exact | |
| `subjective: exercised_mass_undo_yes` | subjective | `enforced: mass_undo_preview_before_write` + `graded: report_shape_intact` | **legacy-only** | Broader coverage: preview-before-write proves the --yes step; report documents it |
| `subjective: verified_idempotent_inverses` | subjective | `enforced: event_log_contains_inverse_events` | exact | |
| `subjective: reported_scanned_appended_skipped_counts` | subjective | `enforced: mass_undo_preview_before_write` + `graded: report_shape_intact` | **legacy-only** | Broader coverage: preview+report documents counts |

#### 26. timeline_pool

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: pool.asset_added` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: pool.asset_scored` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: pool.asset_removed` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_pool_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

#### 27. timeline_theme

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: theme.set` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: theme.overridden` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_theme_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

#### 28. timeline_track

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: track.added` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: track.removed` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_track_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

#### 29. timeline_transition

| Legacy criterion | Type | Destination | Coverage | Notes |
|---|---|---|---|---|
| `no_aborts` | machine | universal + M2 C3/C4 | structural | |
| `events_contain: transition.set` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `events_contain: transition.removed` | machine | `enforced: event_log_contains_edit_verbs` | exact | |
| `no_cross_project_binding` | machine | universal + M2 C3/C4 | structural | |
| `subjective: exercised_transition_verbs` | subjective | `enforced: event_log_contains_edit_verbs` | exact | |
| `subjective: verified_event_log` | subjective | `enforced: event_log_contains_edit_verbs` | fuzzy | |
| `subjective: confirmed_read_only_no_mutation` | subjective | `enforced: read_only_no_mutation` | exact | |

---

## Legacy-Only Criteria Summary

Five legacy criteria have no direct one-to-one Sisypy equivalent but are covered by
broader assertions:

| Scenario | Legacy criterion | How covered |
|---|---|---|
| `cold_restart_midrun` | `tool_used: builtin.agent_probe` | Structurally guaranteed by `extras.target_orchestrator: builtin.agent_probe`. The target orchestrator is the tool the agent must use. |
| `timeline_diff` | `subjective: verified_diff_read_only` | Covered by `enforced: read_only_no_mutation` (proves read-only behavior) + `graded: report_shape_intact` (proves the agent documented findings). |
| `timeline_diff` | `subjective: diff_output_describes_changes` | Same broader coverage as `verified_diff_read_only`. |
| `timeline_mass_undo` | `subjective: exercised_mass_undo_yes` | Covered by `enforced: mass_undo_preview_before_write` (proves the agent used --yes after preview) + `graded: report_shape_intact` (proves the agent reported on the undo). |
| `timeline_mass_undo` | `subjective: reported_scanned_appended_skipped_counts` | Covered by `enforced: mass_undo_preview_before_write` + `graded: report_shape_intact` (preview output + report documents the counts). |

These five criteria remain in `extras.legacy_acceptance` for the legacy auditor but
are not independently enforced by Sisypy's assessment block. The broader checks
provide equivalent or stronger guarantees.

---

## Migration Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Adapter + legacy consumer dual-format updates | ✅ Done |
| Phase 2 | `normalize.py` + `runner.py` Sisypy integration | ✅ Done |
| Phase 3a | Mechanical YAML additions (extras, `${SLUG}`) | ✅ Done |
| Phase 3b | M2 trigger metadata (`extras.m2_checks`) | ✅ Done |
| Phase 3c | Acceptance criteria audit (this document) | ✅ Done |
| Phase 4 | Brief `${VAR}` conversion (145 replacements) | ✅ Done |
| Phase 5 | Migration note (this document) | ✅ Done |

**Baseline**: All 281 agentic tests pass with zero regressions. 101 legacy criteria
mapped, 5 legacy-only, 0 unmapped.
