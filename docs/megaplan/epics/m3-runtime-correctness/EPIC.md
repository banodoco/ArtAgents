# m3 Runtime Correctness

This artifact records the prep conclusions that batch 1 depends on before the
runtime-correctness code changes land.

## Threads Liveness Verdict

Verdict: keep the current cross-process file-lock model; do not take on an
in-process lock rewrite in m3.

Evidence:

- `docs/threads.md` already narrows threads to lineage compatibility state, not
  a generic runtime binding contract.
- The surviving runtime surface is file-backed (`.astrid/threads.json`,
  selections, groups) and the live guarantees are about cross-process safety,
  not multi-threaded in-process mutation.
- `tests/test_threads_index.py` provides multiprocessing-style coverage for the
  file-locking path. No prep evidence showed a live in-process concurrent caller
  that would justify replacing `ThreadIndexStore` with an internal mutex layer.

Implication:

- m3 treats thread liveness as a documented handoff decision, not an
  implementation task. If later work finds a real in-process concurrent caller,
  that becomes a new scoped follow-up.

## Scope Decision

m3 does not introduce a global terminal-event framework. The scope is narrower:

- Add one gate-local finalization choke-point in `astrid/core/task/gate.py` for
  the six replayable step/item terminal kinds:
  `step_completed`, `step_failed`, `step_awaiting_fetch`, `item_completed`,
  `step_attested`, and `item_attested`.
- Keep `iteration_failed` retry markers, `run_started`, `run_completed`,
  `run_aborted`, inbox mutations, and lifecycle retry-fetch behavior outside
  that six-event invariant unless a later task explicitly moves them.

## Terminal Emitter Map

Primary m3 terminal emitters and callers:

| Surface | Current role | m3 decision |
| --- | --- | --- |
| `gate._dispatch_attested` | Emits `step_attested` or `item_attested`, then may trigger inline checks and for-each autoclose. | Route the terminal event through gate-local finalization in active-writer mode. |
| `gate.record_dispatch_complete` | Emits code-step terminal events after `adapter.complete()` or raw return codes. | Route terminal construction through gate-local finalization in decision-writer mode; keep the `returncode == -1` early return outside the finalizer. |
| `gate._evaluate_exhausted_repeat_until_frame` | Traversal-side completion for exhausted repeat frames. | May call the gate-local finalizer with `_gate_append`; repeat-condition evaluation and cursor mutation stay in traversal code. |
| `gate._maybe_autoclose_for_each_host` | Today can append host `step_attested`. | Split into a non-emitting context builder or compatibility wrapper around that builder plus the finalizer. |
| `gate._maybe_autocomplete_for_each_host` | Today can append host `step_completed`. | Split into a non-emitting context builder or compatibility wrapper around that builder plus the finalizer. |
| `lifecycle.cmd_step_retry_fetch` | Emits retry-fetch completion/failure outside `gate.py`. | Explicitly out of the gate-only choke-point; keep inventoried and regression-tested nearby, but do not fold into a global framework. |

Known `record_dispatch_complete(decision, returncode)` compatibility callers:

- `astrid/pipeline.py`
- `astrid/orchestrate/test_runner.py`
- `astrid/core/task/lifecycle_ack.py`
- `astrid/packs/video_editing/thumbnail_maker/run.py`
- `astrid/packs/video_editing/event_talks/run.py`

The contract for batch 1 is documentation-only: preserve that signature and do
not expand pack-side edits unless a later core interface change makes them
unavoidable.

## Append-Mode Contract

The prep decision is to document exactly two append modes, both local to
gate-side finalization:

- Active-writer append mode: the caller supplies the append callable. Traversal
  code uses `_gate_append` so the in-memory `events_view` stays synced for
  replay-correct cursor derivation. Attested dispatch uses the already-open
  writer's raw `append`.
- Decision-writer append mode: the finalizer opens the same
  `writer_context_from_decision(...)` path that `_append_via_decision` uses
  today.

What this does not mean:

- `astrid/core/task/events.py` remains a session-free transport layer.
- `WriterContext.append()` remains the normal production write boundary.
- m3 is not authorizing new ad hoc raw appends from lifecycle code.

## Inline-Check and Result Contract

`_run_inline_checks` is the one helper allowed to append inline-check follow-up
events during finalization, but it needs a narrower contract:

- Input: an injected append callable plus the produces declarations.
- Output: an explicit `InlineCheckResult`-style value describing whether checks
  passed and, on failure, the produces name, the reason, and which retry marker
  was emitted.
- Append responsibility: `_run_inline_checks` appends
  `produces_check_passed`, `produces_check_failed`, and then either
  `cursor_rewind` or the inline-check `iteration_failed` through the supplied
  append strategy.
- Non-goal: no event-log tail scanning inside `_run_inline_checks`, and no
  hidden `_append_via_decision` dependency.

Read-path implication:

- Attested paths may surface the failure synchronously through the returned
  result.
- Code-step failures remain event-driven and are surfaced through lifecycle read
  paths after the fact, not through a synchronous `GateDecision` field.

## Parent Finalization and Cursor Replay

The required event ordering is:

1. Append the leaf or item terminal event first.
2. Run inline checks if the step has produces checks.
3. If inline checks fail, append the failure markers and stop. Do not finalize
   the for-each parent.
4. Only if checks pass may parent autoclose/autocomplete finalize the host.

This guard exists because cursor replay is event-derived. A failed inline check
must cause replay to revisit the same item or leaf even when the log already
contains `item_completed` or `item_attested`. The replay contract therefore
depends on both:

- the failure markers being appended immediately after the item/leaf terminal
  event, and
- parent finalization being skipped when those failure markers are present.

For non-iteration failures the retry marker is `cursor_rewind`. For per-item
iteration inline-check failures the retry marker is `iteration_failed`. Both are
part of the replay/read-path contract, but only the six terminal event kinds are
inside the finalizer invariant.

## Lifecycle Read-Path Scope

Lifecycle work in m3 is read-path surfacing, not a second terminal framework.

The required scope is:

- `cmd_next` tail-dispatch must surface a useful produces name/reason when
  `produces_check_failed` is followed by either `cursor_rewind` or inline-check
  `iteration_failed`.
- `cmd_status` must be checked for duplicate formatting logic; if it formats the
  same tail states independently, it must be brought into parity.
- `cmd_step_retry_fetch` remains outside the gate-only finalizer scope. It stays
  nearby in focused validation because writer-context and terminal-event changes
  are adjacent, but it is not evidence for a global terminal abstraction.

## Autoclose Helper Touchpoints

Prep found four direct or monkeypatch test seams that later refactors must keep
alive or intentionally replace in one slice:

- `tests/test_for_each_autoclose.py`
- `tests/test_agent_probe_regression.py`
- `tests/test_cmd_next_tail_dispatch.py`
- `tests/test_sprint3_contract_regressions.py`

The prep expectation is to prefer a compatibility wrapper named
`_maybe_autoclose_for_each_host` if that keeps the invariant clear. If not, the
refactor must update those tests together and explain the seam move in review.

## Autocomplete Data Flow

Parent autocomplete must preserve the child completion metadata produced in
`record_dispatch_complete`:

- `adapter.complete()` computes the child `returncode`, status, reason, and
  optional cost.
- The autocomplete builder carries the completed return code and cost dict into
  a parent-finalization request.
- The gate-local finalizer constructs the parent `step_completed` from that
  request without recomputing or dropping those fields.

Documented risk: if this flow is not explicit, the host event can silently lose
cost or return-code information while still appearing replay-correct.

## Event-Order Notes

Prep decisions that later tests should pin:

- Attested steps are already terminal at `step_attested` or `item_attested`; no
  extra `step_completed` companion event is required for replay.
- Inline-check failures intentionally occur after the terminal item/leaf event,
  not before it.
- Parent terminal events, when they happen, come after inline checks and only on
  the success branch.
- `run_completed` is managed in lifecycle through
  `_emit_run_completed_if_needed`, not by the gate-local finalizer.

## Schema Keyword Strategy

The prep schema decision is explicit:

- Keep supporting the legacy in-tree subset already used by current callers:
  `type`, object `required`, nested `properties`, `enum`, string `pattern`,
  single-schema array `items`, `minItems`, `maxItems`, and numeric `minimum`.
- `pattern` follows JSON Schema search semantics. Full-string matching requires
  anchors from the caller.
- Tuple-validation `items: [...]` is out of scope and should fail closed with a
  clear reason.
- Unsupported keys should fail closed instead of being silently ignored.

## External Terminal-Emitter Notes

There is one explicit nearby non-gate emitter to keep in view:

- `astrid/core/task/lifecycle.py::cmd_step_retry_fetch`

This is not part of the six-event gate finalization invariant. The point of
documenting it here is to keep scope honest: m3 fixes runtime correctness around
the gate and its read paths without claiming that every terminal event in the
codebase now flows through one global framework.

## Implementation Notes

- The gate-local `_finalize_step` architecture landed only in
  `astrid/core/task/gate.py` and the adjacent lifecycle read-paths in
  `astrid/core/task/lifecycle.py`; m3 did not broaden into a repo-wide terminal
  event framework.
- Parent autoclose/autocomplete now build non-emitting contexts first and route
  the eventual host `step_attested` / `step_completed` events back through the
  gate-local finalizer.
- Audit report generation now verifies ledgers by default; `--no-verify`
  remains the explicit opt-out.
- The no-dependency `json_schema` subset now covers the approved recursive
  object/array/enum/pattern/minimum surface and fails closed on unsupported
  shapes.
- The runtime assert conversions called out in the inventory are complete in
  `astrid/core/executor/install.py`, `astrid/core/session/cli.py`, and
  `astrid/core/runpod/sweeper.py`.

## Pack Edit Exceptions

- None. The approved runtime-correctness implementation stayed in core/docs/test
  surfaces and did not require edits under `astrid/packs/**`.

## Validation Command Log

- `python3 -m py_compile astrid/core/task/gate.py astrid/core/task/lifecycle.py astrid/core/task/lifecycle_ack.py`
  Result: passed during the gate/lifecycle slices.
- `python3 -m py_compile astrid/audit/cli.py astrid/audit/report.py`
  Result: passed during the audit verification-default slice.
- `python3 -m py_compile astrid/verify/checks.py`
  Result: passed during the `json_schema` subset slice.
- `pytest tests/task/test_sprint3_contract_regressions.py`
  Result: passed after the gate/lifecycle/repeat/for-each fixes landed.
- `pytest tests/audit/test_sprint3_ledger_transport_contract.py`
  Result: passed after the audit verification-default changes landed.
- `pytest tests/test_verify_helpers.py`
  Result: passed after the `json_schema` subset implementation landed.
- `pytest tests/test_runtime_correctness_inventory.py`
  Result: passed after inventory synchronization in the implementation batches
  and again after the final doc refresh in batch 15.
- `python3 - <<'PY' ... AST inventory regeneration ... PY`
  Result: rewrote `docs/runtime-correctness-m3-inventory.md` against current
  non-pack `astrid/` source; summary now matches 557 AST sites and 567 lexical
  grep hits.
- `pytest`
  Result: passed at the end of batch 14 with `3361 passed, 13 skipped, 4
  xfailed`; rerun again in batch 15 after the documentation refresh to confirm
  the docs-only batch did not introduce regressions.
- `pytest tests/test_sprint3_contract_regressions.py`
  Result: path is stale in this checkout; pytest exited 4 with
  `file or directory not found`. The current regression module is
  `tests/task/test_sprint3_contract_regressions.py`.
- `pytest tests/test_lifecycle_ack.py tests/test_task_repeat_until.py tests/test_for_each_autoclose.py tests/test_inline_check_ack.py tests/test_verify_helpers.py tests/test_audit.py tests/audit/test_sprint3_ledger_transport_contract.py tests/task/test_step_retry_fetch.py tests/test_agent_probe_regression.py tests/test_cmd_next_tail_dispatch.py tests/task/test_sprint3_contract_regressions.py tests/test_runtime_correctness_inventory.py tests/adapter/test_sprint3_adapter_fail_closed_contract.py tests/adapter/test_sprint3_remote_artifact_quarantine_contract.py tests/reshape/test_hype_regression_fixture.py tests/test_sprint1_regression.py`
  Result: passed in batch 16 with `152 passed`.
- `pytest`
  Result: passed in batch 16 with `3361 passed, 13 skipped, 4 xfailed`.
- `pytest tests`
  Result: initial batch 18 broad run exposed a still-open cursor replay
  regression through the temporary reproduction script work; after the targeted
  fix and inventory/test synchronization, the final broad run passed with
  `3351 passed, 13 skipped, 4 xfailed`.
- `python3 .megaplan/plans/m3-runtime-correctness-20260526-0310/tmp_cursor_replay_repro.py`
  Result: first run reproduced the m3 bug path: after `item_attested` plus a
  failing per-item inline check, cursor replay advanced from item `a` to `b`.
  After the fix, the script passed with `ok: inline-check failure after
  item_attested replays item a`. The throwaway script was deleted after the
  successful run.
- `python3 -m py_compile astrid/core/task/gate.py`
  Result: passed after the final cursor replay fix.
- `pytest tests/test_runtime_correctness_inventory.py tests/task/test_sprint3_contract_regressions.py`
  Result: passed after final source-invariant, inventory, and cursor replay
  synchronization with `31 passed`.
