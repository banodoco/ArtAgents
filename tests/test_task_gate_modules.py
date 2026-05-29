"""Direct module-level locks for the extracted ``gate_*`` helper modules.

These import from the extracted modules directly (not through the
``astrid.core.task.gate`` re-export) so each helper surface carved out of the
former monolithic ``gate.py`` has its own blocking coverage: ``gate_base`` leaf
types, ``gate_cursor`` cursor/path/frame helpers, ``gate_attestation`` command
parsing / identity, ``gate_checks`` inline-check guard, and ``gate_repeat``
iteration-state queries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.task.gate_base import (
    ITERATE_FEEDBACK_PREFIX,
    GateDecision,
    InlineCheckResult,
    TaskRunGateError,
    _reject,
)
from astrid.core.task.gate_cursor import (
    EXHAUST_OVERRIDE_ID,
    CursorPath,
    derive_cursor,
    _event_matches_dispatch_hash,
    _event_step_version,
    _make_exhaust_override_step,
    _path_str_from_event,
)
from astrid.core.task.gate_attestation import (
    AttestedArgs,
    _extract_iterate_feedback,
    match_attested_command,
)
from astrid.core.task.gate_checks import _run_inline_checks
from astrid.core.task.gate_repeat import (
    _count_iteration_failed,
    _has_iteration_exhausted,
    _json_field,
)
from astrid.core.task.plan import AckRule, Step, TaskPlan


# --- gate_base -----------------------------------------------------------------


def test_gate_base_error_carries_reason_and_recovery() -> None:
    err = TaskRunGateError(reason="nope", recovery="astrid next")
    assert err.reason == "nope"
    assert err.recovery == "astrid next"
    assert str(err) == "nope"


def test_gate_base_reject_builds_recovery_string() -> None:
    with pytest.raises(TaskRunGateError) as next_exc:
        _reject("demo", "bad", abort=False)
    assert next_exc.value.recovery == "astrid next --project demo"
    with pytest.raises(TaskRunGateError) as abort_exc:
        _reject("demo", "bad", abort=True)
    assert abort_exc.value.recovery == "astrid abort --project demo"


def test_gate_base_error_code_is_additive() -> None:
    # Catch sites that read only reason/recovery keep working: code defaults
    # to None when not supplied.
    err = TaskRunGateError(reason="nope", recovery="astrid next")
    assert err.code is None
    coded = TaskRunGateError(reason="nope", recovery="astrid next", code="x")
    assert coded.code == "x"


def test_gate_base_reject_surfaces_stable_non_null_code() -> None:
    with pytest.raises(TaskRunGateError) as exc:
        _reject("demo", "bad", abort=False)
    assert exc.value.code == "gate_rejected"
    with pytest.raises(TaskRunGateError) as custom:
        _reject("demo", "bad", abort=True, code="pinned_failure")
    assert custom.value.code == "pinned_failure"


def test_gate_base_decision_and_inline_defaults() -> None:
    decision = GateDecision(active=False)
    assert decision.active is False
    assert decision.plan_step_path == ()
    assert decision.step_version == 1
    assert InlineCheckResult(ok=True).events == ()
    assert ITERATE_FEEDBACK_PREFIX == "iterate_feedback="


# --- gate_cursor ----------------------------------------------------------------


def test_gate_cursor_empty_events_stays_at_root() -> None:
    plan = TaskPlan(plan_id="p", version=1, steps=(Step(id="a", command="echo a"),))
    cursor = derive_cursor(plan, [])
    assert isinstance(cursor, CursorPath)
    assert len(cursor.frames) == 1
    assert cursor.frames[0].child_index == 0
    assert cursor.top_exhausted is False


def test_gate_cursor_step_completed_advances_root() -> None:
    plan = TaskPlan(
        plan_id="p",
        version=1,
        steps=(Step(id="a", command="echo a"), Step(id="b", command="echo b")),
    )
    cursor = derive_cursor(plan, [{"kind": "step_attested", "plan_step_path": ["a"]}])
    assert cursor.frames[-1].child_index == 1


def test_gate_cursor_event_helpers() -> None:
    assert _path_str_from_event({"plan_step_path": ["host", "child"]}) == "host/child"
    assert _path_str_from_event({"plan_step_id": "solo"}) == "solo"
    assert _path_str_from_event({}) == ""
    assert _event_step_version({"step_version": 3}) == 3
    assert _event_step_version({"step_version": 0}) == 1  # invalid -> default
    assert _event_step_version({}) == 1
    assert _event_matches_dispatch_hash({}, "h") is True  # no event hash -> match
    assert _event_matches_dispatch_hash({"dispatch_event_hash": "h"}, "h") is True
    assert _event_matches_dispatch_hash({"dispatch_event_hash": "h"}, "x") is False


def test_gate_cursor_exhaust_override_step_shape() -> None:
    step = _make_exhaust_override_step("demo", "host")
    assert step.id == EXHAUST_OVERRIDE_ID
    assert step.ack.kind == "human"
    assert step.requires_ack is True
    assert "host/exhaust-override" in step.command


# --- gate_attestation -----------------------------------------------------------


def test_gate_attestation_match_strips_tokens() -> None:
    matched, args = match_attested_command(
        "astrid done --agent a1 --evidence e.txt --item it1", "astrid done"
    )
    assert matched is True
    assert args == AttestedArgs(agent="a1", evidence=("e.txt",), item="it1")


def test_gate_attestation_match_rejects_remainder_mismatch() -> None:
    matched, _ = match_attested_command("astrid done extra", "astrid done")
    assert matched is False


def test_gate_attestation_match_handles_malformed_shlex() -> None:
    matched, args = match_attested_command('astrid "unterminated', "astrid done")
    assert matched is False
    assert args == AttestedArgs(agent=None)


def test_gate_attestation_extract_iterate_feedback() -> None:
    assert _extract_iterate_feedback((f"{ITERATE_FEEDBACK_PREFIX}retry pls",)) == "retry pls"
    assert _extract_iterate_feedback(("e.txt",)) is None


# --- gate_checks ----------------------------------------------------------------


def test_gate_checks_returns_ok_when_decision_incomplete() -> None:
    # Missing events_path/run_id/etc. short-circuits to a no-op pass.
    result = _run_inline_checks(GateDecision(active=True), (), lambda ev: None)
    assert result.ok is True
    assert result.events == ()


# --- gate_repeat ----------------------------------------------------------------


def test_gate_repeat_count_iteration_failed_by_host() -> None:
    events = [
        {"kind": "iteration_failed", "plan_step_path": ["loop"]},
        {"kind": "iteration_failed", "plan_step_path": ["loop"]},
        {"kind": "iteration_failed", "plan_step_path": ["other"]},
        {"kind": "step_attested", "plan_step_path": ["loop"]},
    ]
    assert _count_iteration_failed(events, "loop") == 2


def test_gate_repeat_has_iteration_exhausted() -> None:
    events = [{"kind": "iteration_exhausted", "plan_step_path": ["loop"], "on_exhaust": "fail"}]
    found = _has_iteration_exhausted(events, "loop")
    assert found is not None and found["on_exhaust"] == "fail"
    assert _has_iteration_exhausted(events, "missing") is None


def test_gate_repeat_json_field_navigates_and_rejects() -> None:
    payload = {"a": {"b": 7}}
    assert _json_field(payload, ("a", "b"), Path("x.json")) == 7
    with pytest.raises(TaskRunGateError):
        _json_field(payload, ("a", "missing"), Path("x.json"))


def test_gate_repeat_direct_raise_sites_have_stable_code() -> None:
    # _json_field direct-raise path surfaces a non-null code slug
    with pytest.raises(TaskRunGateError) as exc:
        _json_field({}, ("missing_field",), Path("test.json"))
    assert exc.value.code == "repeat_until_json_field_missing"
