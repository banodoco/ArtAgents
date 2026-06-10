"""Phase 1 regression — for_each host autoclose (FLAG-S1-001 / SD-001 / SD-004).

(a) Positive replay of ``builtin.agent_probe`` through ``run_fixture`` asserts
    exactly one ``step_attested`` for the ``per_item`` host path with
    ``attestor_kind == 'system'`` and ``attestor_id == 'gate.autoclose'``.

(b) Monkeypatch-only negative test that neutralizes
    ``gate._maybe_autoclose_for_each_host``, replays, and asserts the host
    ``step_attested`` is absent.

(c) Optional-body guard test that calls the helper directly against a
    synthesized for_each host with ``optional=True`` and asserts
    ``AssertionError`` per SD-004.

No ``.patch`` fixtures (SD-005 / FLAG-S1-006).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrid.core.task import gate
from astrid.core.task.gate import repeat as gate_repeat
from tests.conftest import seed_event
from astrid.core.task.events import (
    make_item_skipped_event,
    make_produces_check_passed_event,
    read_events,
)
from astrid.core.task.plan import (
    STEP_PATH_SEP,
    RepeatForEach,
    Step,
    TaskPlan,
)
from astrid.core.orchestrate.test_runner import run_fixture
from astrid.core.pack import packs_root as _packs_root


PER_ITEM_PATH = ("per_item",)
PER_ITEM_PATH_LIST = list(PER_ITEM_PATH)
PER_ITEM_ID = STEP_PATH_SEP.join(PER_ITEM_PATH)


def _replay_agent_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # agent_probe's attested steps declare produces files that run_fixture
    # never writes (it auto-acks but does not author artifacts). Swap the
    # inline produces check for a stub that emits produces_check_passed for
    # every declared produces entry — that's the signal derive_cursor needs
    # to advance past produces-bearing attested steps. This keeps the test
    # focused on the autoclose surface without coupling it to artifact
    # authoring details.
    def _stub_inline_checks(decision, produces, append_fn):
        emitted = []
        for entry in produces:
            if decision.events_path is None or not decision.plan_step_path:
                continue
            event = make_produces_check_passed_event(
                decision.plan_step_path,
                entry.name,
                check_id=entry.check.check_id,
                cas_sha256=None,
            )
            emitted.append(event)
            append_fn(event)
        return gate.InlineCheckResult(ok=True, events=tuple(emitted))
    monkeypatch.setattr(gate, "_run_inline_checks", _stub_inline_checks)
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    return run_fixture(
        qualified_id="builtin.agent_probe",
        fixture_dir=None,
        packs_root=_packs_root(),
        projects_root=projects_root,
    )


def _host_step_attested(events) -> list[dict]:
    out = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("kind") != "step_attested":
            continue
        if ev.get("plan_step_id") == PER_ITEM_ID:
            out.append(ev)
    return out


def test_for_each_autoclose_positive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive replay: exactly one host step_attested with system/gate.autoclose."""
    events_path = _replay_agent_probe(tmp_path, monkeypatch)
    events = read_events(events_path)
    matches = _host_step_attested(events)
    assert len(matches) == 1, (
        f"expected exactly one host step_attested for {PER_ITEM_ID}; "
        f"got {len(matches)}: {matches!r}"
    )
    ev = matches[0]
    assert ev.get("attestor_kind") == "system", ev
    assert ev.get("attestor_id") == "gate.autoclose", ev


def test_for_each_autoclose_negative_monkeypatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Negative: neutralize the autoclose helper and the host step_attested
    must NOT appear (locks in that the helper is the only producer)."""
    monkeypatch.setattr(
        gate, "_maybe_autoclose_for_each_host", lambda *a, **k: None
    )
    events_path = _replay_agent_probe(tmp_path, monkeypatch)
    events = read_events(events_path)
    matches = _host_step_attested(events)
    assert matches == [], (
        f"host step_attested should be absent when autoclose is neutralized; "
        f"got {matches!r}"
    )


def test_for_each_autoclose_optional_body_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Optional-body guard (SD-004): optional=True for_each host raises."""
    host_step = Step(
        id="per_item_opt",
        adapter="local",
        command="echo x",
        optional=True,
        repeat=RepeatForEach(
            items_source="static",
            items=("a", "b", "c"),
        ),
    )
    fake_plan = TaskPlan(plan_id="fake", version=2, steps=(host_step,))

    project_root = tmp_path / "proj"
    project_root.mkdir()
    events_path = project_root / "events.jsonl"
    # Also add a fake item_skipped event for the same path so the test
    # exercises both halves of the SD-004 guard surface (optional flag is
    # checked first; item_skipped would also trigger AssertionError on a
    # non-optional host).
    skipped = make_item_skipped_event(
        ("per_item_opt",),
        item_id="a",
        actor_kind="agent",
        actor_id="author_test",
    )
    events_path.write_text(json.dumps(skipped) + "\n")

    monkeypatch.setattr(gate_repeat, "load_plan", lambda _p: fake_plan)

    with pytest.raises(AssertionError, match="optional"):
        gate._maybe_autoclose_for_each_host(
            events_path=events_path,
            path_tuple=("per_item_opt",),
            project_root=project_root,
            slug="probe",
            run_id="r1",
            append_fn=lambda _event: _event,
        )
