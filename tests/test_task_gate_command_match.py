"""Blocking invariant locks for task-gate command matching and attested identity.

These cover the pure command-matching / identity-validation surface of
`astrid/core/task/gate.py` directly, so the contract is pinned before the gate
module is extracted. Targets `match_attested_command`, `validate_attested_identity`,
`command_for_argv`, and `TaskRunGateError` recovery wiring.
"""

from __future__ import annotations

import pytest

from astrid.core.subprocess_env import ASTRID_ACTOR, ASTRID_AUTHOR_TEST
from astrid.core.task.gate import (
    AttestedArgs,
    TaskRunGateError,
    command_for_argv,
    match_attested_command,
    validate_attested_identity,
)
from astrid.core.task.plan import AckRule, Step


def _agent_step() -> Step:
    return Step(id="s1", command="echo hi", requires_ack=True, ack=AckRule(kind="agent"))


def _human_step() -> Step:
    return Step(id="s1", command="echo hi", requires_ack=True, ack=AckRule(kind="human"))


# --- command matching (token stripping + canonical remainder) -----------------


def test_strips_identity_evidence_item_tokens_and_matches_remainder() -> None:
    matched, args = match_attested_command(
        "astrid done --agent a1 --human bob --item it7 --evidence e.txt",
        "astrid done",
    )
    assert matched is True
    assert args.agent == "a1"
    assert args.human == "bob"
    assert args.item == "it7"
    assert args.evidence == ("e.txt",)


def test_multiple_evidence_flags_accumulate() -> None:
    matched, args = match_attested_command(
        "astrid done --evidence a.txt --evidence b.txt",
        "astrid done",
    )
    assert matched is True
    assert args.evidence == ("a.txt", "b.txt")


def test_remainder_mismatch_does_not_match() -> None:
    matched, _ = match_attested_command("astrid abort --agent a1", "astrid done")
    assert matched is False


def test_malformed_shlex_incoming_returns_no_match() -> None:
    matched, args = match_attested_command('astrid done --agent "unterminated', "astrid done")
    assert matched is False
    assert args.agent is None


def test_quoting_canonicalized_on_both_sides() -> None:
    matched, _ = match_attested_command("astrid 'done'", "astrid done")
    assert matched is True


def test_command_for_argv_round_trips_through_match() -> None:
    cmd = command_for_argv(["astrid", "done", "--agent", "a 1"])
    matched, args = match_attested_command(cmd, "astrid done")
    assert matched is True
    assert args.agent == "a 1"


# --- attested identity validation ---------------------------------------------


def test_agent_step_requires_agent_flag() -> None:
    with pytest.raises(TaskRunGateError):
        validate_attested_identity(
            slug="p",
            step=_agent_step(),
            args=AttestedArgs(agent=None, human="bob"),
            run_started_actor=None,
        )


def test_agent_step_accepts_agent_identity() -> None:
    kind, ident = validate_attested_identity(
        slug="p",
        step=_agent_step(),
        args=AttestedArgs(agent="a1"),
        run_started_actor=None,
    )
    assert (kind, ident) == ("agent", "a1")


def test_zero_identity_flags_rejected() -> None:
    with pytest.raises(TaskRunGateError):
        validate_attested_identity(
            slug="p",
            step=_human_step(),
            args=AttestedArgs(agent=None, human=None),
            run_started_actor=None,
        )


def test_multiple_identity_flags_rejected() -> None:
    with pytest.raises(TaskRunGateError):
        validate_attested_identity(
            slug="p",
            step=_human_step(),
            args=AttestedArgs(agent="a1", human="bob"),
            run_started_actor=None,
        )


def test_human_step_actor_env_mismatch_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ASTRID_AUTHOR_TEST, raising=False)
    monkeypatch.setenv(ASTRID_ACTOR, "alice")
    with pytest.raises(TaskRunGateError):
        validate_attested_identity(
            slug="p",
            step=_human_step(),
            args=AttestedArgs(agent=None, human="bob"),
            run_started_actor=None,
        )


def test_human_step_actor_env_match_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ASTRID_AUTHOR_TEST, raising=False)
    monkeypatch.setenv(ASTRID_ACTOR, "bob")
    kind, ident = validate_attested_identity(
        slug="p",
        step=_human_step(),
        args=AttestedArgs(agent=None, human="bob"),
        run_started_actor=None,
    )
    assert (kind, ident) == ("human", "bob")


def test_human_self_ack_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ASTRID_AUTHOR_TEST, raising=False)
    monkeypatch.setenv(ASTRID_ACTOR, "bob")
    with pytest.raises(TaskRunGateError):
        validate_attested_identity(
            slug="p",
            step=_human_step(),
            args=AttestedArgs(agent=None, human="bob"),
            run_started_actor="bob",
        )


def test_author_test_mode_bypasses_actor_and_self_ack_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ASTRID_AUTHOR_TEST, "1")
    monkeypatch.setenv(ASTRID_ACTOR, "alice")
    kind, ident = validate_attested_identity(
        slug="p",
        step=_human_step(),
        args=AttestedArgs(agent=None, human="bob"),
        run_started_actor="bob",
    )
    assert (kind, ident) == ("human", "bob")


# --- recovery wiring on the error type ----------------------------------------


def test_identity_rejection_recovery_uses_next_verb_with_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ASTRID_AUTHOR_TEST, raising=False)
    with pytest.raises(TaskRunGateError) as excinfo:
        validate_attested_identity(
            slug="myproj",
            step=_human_step(),
            args=AttestedArgs(agent=None, human=None),
            run_started_actor=None,
        )
    assert excinfo.value.recovery == "astrid next --project myproj"
