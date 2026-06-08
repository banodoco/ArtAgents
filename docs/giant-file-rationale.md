# Giant File Rationale — M4 Inventory

Baseline inventory of every `astrid/**/*.py` file exceeding the M4 1,200 physical-line
threshold (counted with `wc -l`, includes blank lines and comments).

All 8 entries below are **required split targets** for M4.  Files at or below the
1,200-line threshold (e.g. `astrid/core/pack/__init__.py` at 1,171) are watch-only
and do not require rationale entries.

## Inventory (descending by line count)

> **Fully decomposed:** `astrid/core/timeline/cli.py` (originally 3,266 lines) has been
> split into six focused modules during M4 batches 3-9:
> `cli_parser.py` (T4), `cli_crud.py` (T6), `cli_output.py` (T6), `cli_edits.py` (T8),
> `cli_events.py` (T10), `cli_backends.py` (T10).  The original module is now a thin
> 255-line facade and is below the 1,200-line threshold — no longer listed here.
>
> **Fully decomposed:** `astrid/core/pack/cli.py` (originally 1,226 lines) has been
> split into four focused modules during M4 batches 14 and 15:
> `cli_parser.py` (T14, 276 lines), `cli_basic.py` (T14, 484 lines),
> `cli_inspect.py` (T16, 825 lines), `cli_search.py` (T16, 215 lines).
> The original module is now a thin 249-line facade and is below the 1,200-line
> threshold — no longer listed here.
>
> **Fully decomposed:** `astrid/core/pack/install.py` (originally 1,946 lines) has
> been fully decomposed across five focused modules during M4 batches 18-24:
> `install_trust.py` (T18, 223 lines), `install_local.py` (T20, 1,039 lines),
> `install_git.py` (T22, 567 lines), `install_cli.py` (T24, 235 lines).
> The original module is now a thin 109-line facade containing only re-exports —
> no longer listed here.
>
> **Fully decomposed:** `astrid/core/pack/validate.py` (originally 1,614 lines) has
> been split into two focused modules during M4 batch 25 (T26):
> `validate_layout.py` (464 lines) — layout contract types and validation functions,
> `validate_first_party.py` (178 lines) — first-party packs root validation.
> The original module is now 1,117 lines and is below the 1,200-line threshold —
> no longer listed here.
>
> **Fully decomposed:** `astrid/sdk.py` (originally 1,530 lines) was split during
> M4 and has since been folded into the `astrid/sdk/` package:
> `exceptions.py`, `results.py`, `generation.py`, `discovery.py`,
> `invocation.py`, `dto.py`, and `events.py`.
> The monolithic module no longer exists and is no longer listed here.
>
> **Fully decomposed:** `astrid/gateway.py` (originally 1,215 lines) was split
> during M4 and has since been folded into the `astrid/gateway/` package:
> `__init__.py`, `dispatch.py`, `help.py`, `project.py`, and `wait.py`.
> The monolithic module no longer exists and is no longer listed here.

| # | File | Lines | Classification | Rationale |
|---|------|-------|----------------|-----------|
> **Fully decomposed:** `astrid/packs/rendering/executors/sprite_sheet/run.py`
> (originally 1,411 lines) has been split into four focused modules during M4
> batches 68–72 (T68–T72):
> `png_io.py` (170 lines) — PNG read/write and alpha analysis helpers.
> `sheet.py` (233 lines) — layout selection/validation, guide rendering,
> and dimension validation (pure Python helpers).
> `web_outputs.py` (T72, 394 lines) — ffmpeg subprocess wrapper, chroma key
> removal, frame slicing, video assembly (review/ProRes/web), WebP conversion,
> animated WebP, sprite sheet reassembly, web output orchestration,
> and frame normalization.
> `upscale.py` (415 lines) — FAL AI upscaling, OpenAI image generation/edit
> API calls, sprite prompt builder, and ffmpeg upscale helpers.
> The original module is now a thin 516-line facade — **fully decomposed** and
> below the 1,200-line threshold.  Not listed in table below.

> **Fully decomposed:** `astrid/packs/training/orchestrators/dataset_build/run.py`
> (originally 1,327 lines) has been split during M4: service dataclasses
> extracted to `services.py` (T74, 62 lines), and all phase implementations
> (acquisition, filtering, captioning, review, finalization) extracted to
> `phases.py` (T76, 650+ lines). The original module is now a thin 803-line
> orchestrator facade — **fully decomposed** and below the 1,200-line threshold.
> Not listed in table below.

> **Fully decomposed:** `astrid/packs/video_editing/executors/cut/run.py`
> (originally 1,374 lines) has been split into four focused modules during M4:
> batch 77 (T78): `probe.py` (98 lines) — ffprobe media-probing helpers
> (`parse_ffprobe_fps`, `probe_asset`, `probe_video_duration`, and
> `_FFPROBE_VERBOSE` state), `registry.py` (201 lines) — asset registry
> construction (`resolve_asset_paths`, `_url_cache_meta`, `build_registry`,
> `rebase_registry_paths`).
> batch 79 (T80): `timeline_build.py` (613 lines) — timeline, metadata, and
> EDL builders (`build_multitrack_timeline`, `build_metadata_from_arrangement`,
> `arrangement_edl_rows`, `write_edl`, `_register_cut_outputs`,
> `_emit_cut_managed_events`, plus private helpers), `resume.py` (184 lines) —
> resume-mode helpers (`ensure_resume_mode_args`, `build_resume_metadata`,
> `run_resume_mode`).  The original module is now a thin 429-line parser/main
> glue facade — **fully decomposed** and no longer listed in the table below.

> **Fully decomposed:** `astrid/core/timeline/events/schema/types.py` (1,220 → 1,180 lines)
> during M4 batch 81 (T82): ULID generation and validation helpers
> (`generate_event_ulid`, `is_event_ulid`) extracted to `ulid.py` (42 lines).
> The original module is now below the 1,200-line threshold —
> no longer listed here.
>
> <!-- M4-complete: all astrid/**/*.py files are now at or below the 1,200-line threshold -->

> **Fully decomposed:** `astrid/packs/video_editing/orchestrators/hype/run.py`
> (originally 1,838 lines) has been split into four focused modules during M4
> batches 61-62: `config.py` (T62, 132 lines), `parser.py` (T62, 248 lines),
> `steps.py` (T64, 539 lines), `runner.py` (T64, 711 lines). The original
> module is now a thin 324-line facade — no longer listed here.

> **Hype run.py decomposition (T62 + T64):** `astrid/packs/video_editing/orchestrators/hype/run.py`
> (1,838 → 1,509 → 324 lines) during M4 batches 61-62 (T62–T64):
> `parser.py` (248 lines) — argument parser construction (`build_parser`) and
> argument resolution (`resolve_args`), including theme resolution helper.
> `config.py` (132 lines) — pipeline constants (`STEP_ORDER`), config
> loading/normalization (`load_config`, `normalize_config`), asset entry
> parsing (`parse_asset_entry`), and list/dict normalization helpers
> (`normalize_many`, `normalize_extra_args`, `usage_error`).
> **T64 (batch 63):** Step definitions, command builders, and sentinels extracted
> to `steps.py` (539 lines); run-loop helpers, editor-review iteration, and
> audit registration extracted to `runner.py` (711 lines). All extracted names
> are re-exported from `run.py` so callers importing through
> `astrid.packs.video_editing.orchestrators.hype.run` continue to work.
> `run.py` is now a thin 324-line facade — **fully decomposed** and below the
> 1,200-line threshold.
>
> **T66 (batch 65):** Project-run and gate environment adapter helpers extracted
> to `project_adapter.py` (137 lines): `_project_slug_for_gate`,
> `_prepare_project_main`, `_set_project_env`, `_restore_project_env`,
> `_system_exit_code`, `_project_hype_metadata`, and
> `_project_hype_artifact_roots`. `_prepare_project_main` uses a late import
> through the `run.py` facade for `prepare_project_run` to preserve the
> monkeypatch seam exercised by `test_task_env_contract.py`. `run.py` is now a
> 235-line facade (down from 324 lines) — well below the 1,200-line threshold.
>
> **Below-threshold decomposition:** `astrid/core/session/cli.py` (991 → 665 lines)
> has been partially decomposed during M4 batches 43-45:
> `cli_attach.py` (T44, 375 lines) — attach command and helpers,
> `cli_sessions.py` (T46, 414 lines) — ls, detach, takeover, and prune handlers.
> The original module remains the session CLI facade (now 665 lines) with
> shared helpers, status rendering, and parser wiring — well below the
> 1,200-line threshold.
>
> **Further decomposition:** `astrid/core/session/cli.py` (665 → 328 lines)
> during M4 batch 47 (T48):
> `cli_status.py` (413 lines) — status JSON/text rendering,
> `cmd_status` entrypoint, templates, and helpers.
> The original module is now a thin 328-line facade with shared helpers,
> parser wiring, and re-exports from the four split modules.
>
> **Parser extraction (T50):** `astrid/core/session/cli.py` (328 → 262 lines)
> during M4 batch 49 (T50):
> `cli_parser.py` (151 lines) — parser construction via ``CommandSpec`` /
> ``register_commands`` with late imports from ``.cli`` to preserve
> monkeypatch seams (``cli.cmd_attach``, ``cli.cmd_status``, etc.).
> The original module is now a thin 262-line facade — well below the
> 1,200-line threshold.
>
> **Gate dispatch extraction (T54):** `astrid/core/task/gate.py` (1,232 → 844 lines)
> during M4 batch 53 (T54):
> `gate_dispatch.py` (450 lines) — adapter resolution, code dispatch,
> attested dispatch, and supporting helpers (`_resolve_adapter`, `_make_run_ctx`,
> `_dispatch_code`, `_adapter_dispatch`, `_code_decision`, `_latest_event_for_step`,
> `_dispatch_attested`). All seven names are re-exported from `gate.py` to preserve
> `task_gate._dispatch_code` / `_dispatch_attested` monkeypatch and
> `inspect.getsource` seams. `gate.py` remains the lifecycle entrypoint
> (`gate_command`, `command_for_argv`) and event-finalization owner
> (`_finalize_step`, `record_dispatch_complete`).
>
> **Gate finalization extraction (T56):** `astrid/core/task/gate.py` (844 → 568 lines)
> during M4 batch 55 (T56):
> `gate_finalize.py` (310 lines) — terminal-event finalization, dispatch-complete
> recording, nested dispatch recording, and supporting helpers
> (`_finalize_step`, `_load_step_for_decision`, `record_dispatch_complete`,
> `record_nested_entered`, `record_nested_exited`). These names remain re-exported
> from `gate.py` so lifecycle callers, monkeypatch seams, and
> `inspect.getsource(task_gate.record_dispatch_complete)` continue to work through
> the facade.
>
> **Operator status JSON extraction (T58):** `astrid/core/task/operator_view.py`
> (1,311 → 1,215 lines) during M4 batch 57 (T58):
> `operator_status_json.py` (135 lines) — ``_status_json`` payload construction,
> inline-failure helpers (``_inline_failure_tail``, ``_format_inline_failure_tail``,
> ``_path_tuple_from_event``), and the ``_InlineFailureTail`` dataclass.  All five
> names are re-exported from ``operator_view.py`` so ``cmd_status``,
> ``_dispatch_from_tail``, and test monkeypatch seams continue to work through
> the ``astrid.core.task.operator_view`` namespace.
>
> **Operator render extraction (T60):** `astrid/core/task/operator_view.py`
> (1,215 → 839 lines) during M4 batch 59 (T60):
> `operator_render.py` (483 lines) — human-readable rendering, audit helpers,
> tail-dispatch, ack templates, and post-completion handoff.  All names
> (``render_step_instructions``, ``_dispatch_from_tail``, ``_leaf_progress``,
> ``_emit_for_each_autoclose_audit``, ``_RewindRetry``, ``_HostCloseHint``,
> ``_RunComplete``, ``_AckTemplate``, ``_print_post_completion_handoff``,
> ``_format_claim_line``, ``_format_schema_requirements``, ``_ack_template_parts``,
> and others) are re-exported from ``operator_view.py`` so ``lifecycle.py``,
> ``lifecycle_ack.py``, and test monkeypatch seams continue to work through
> the ``astrid.core.task.operator_view`` namespace.  ``operator_view.py`` is
> now a thin command adapter (839 lines, below threshold) containing only
> ``cmd_status``, ``cmd_next``, and backward-compatibility re-exports.

## Measurement

- **Threshold:** 1,200 physical lines (blank lines and comments included)
- **Method:** `wc -l` on each `astrid/**/*.py` file
- **Timestamp:** 2026-06-08 (M4-complete: all files now at or below 1,200 lines)

## Watch-Only (below threshold, no entry required)

Files at or below 1,200 lines are excluded from this rationale. The closest
under-threshold file is `astrid/core/pack/__init__.py` at 1,171 lines.
