"""Phase 2 Step 7 — tail-dispatch tests for ``cmd_next._dispatch_from_tail``.

Each branch is exercised with a hand-rolled ``events.jsonl`` tail so the
test doesn't depend on driving the gate end-to-end through ``run_fixture``:

(a) rewind-with-reason: tail = produces_check_failed, cursor_rewind. The
    printed message must echo ``produces_check_failed.reason`` from
    ``events[-2]`` (FLAG-S1-002 / SD-002 — single ``cursor_rewind``-keyed
    branch reads the prior event for context).

(b) host-close hint: tail = item_attested for every item of a for_each
    host but no host ``step_attested``. The defensive belt fires when
    Phase 1's autoclose is missing (e.g. an old replay) and instructs the
    operator to close the host.

(c) run-complete: tail shows all leaves terminal. ``cmd_next`` must emit
    exactly ONE ``run_completed`` even when invoked twice — locks in the
    centralized ``_emit_run_completed_if_needed`` helper.

(d) exhausted-but-incomplete: tail has the cursor walked past every step
    yet ``_run_is_complete`` returns False (the latest event for the leaf
    is ``step_dispatched``, not a terminal kind). The state-derived
    "cursor parked at <path> with no legal action" message must print to
    stderr; no ``run_completed`` may land.

Negative (monkeypatch-only, SD-005 / FLAG-S1-006): neutralize
``_dispatch_from_tail`` to ``None`` and confirm the rewind branch's
canonical "Previous attempt rejected" message disappears — proving the
tail-dispatch is the sole producer of that text.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task import lifecycle
from tests.conftest import seed_event
from astrid.core.task.events import (
    make_cursor_rewind_event,
    make_for_each_expanded_event,
    make_item_attested_event,
    make_produces_check_failed_event,
    make_produces_check_passed_event,
    make_step_attested_event,
    make_step_completed_event,
    make_step_dispatched_event,
    read_events,
)
from astrid.core.task.lifecycle import cmd_next


_BODY_PRODUCES = '''from astrid.core.orchestrate import orchestrator, attested
from astrid.core.verify import json_file
@orchestrator("demo.with_produces")
def main(): return [attested("review", command="review.sh", instructions="check", ack="human", produces={"out": json_file()})]
'''

_BODY_FE = '''from astrid.core.orchestrate import orchestrator, attested, repeat_for_each
@orchestrator("demo.fe")
def main(): return [attested("review_each", command="r.sh", instructions="check", ack="human",
    repeat=repeat_for_each(items=["a","b","c"]))]
'''

_BODY_CODE = '''from astrid.core.orchestrate import orchestrator, code
@orchestrator("demo.code")
def main(): return [code("step_a", argv=["echo","x"])]
'''


def _capture(projects: Path) -> tuple[int, str, str]:
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = cmd_next(["--project", "p"], projects_root=projects)
    return rc, buf.getvalue(), err.getvalue()


def test_a_rewind_with_reason_echoes_produces_check_failed(tmp_path: Path) -> None:
    """Branch (1): cursor_rewind tail with produces_check_failed at [-2].
    The printed retry message echoes the failed-check ``reason``.
    """
    packs, projects = setup_run(
        tmp_path, "demo", "with_produces", _BODY_PRODUCES, "demo.with_produces", run_id="ra",
    )
    events_path = projects / "p" / "runs" / "ra" / "events.jsonl"
    rejection_reason = "required key 'why' missing"
    seed_event(
        events_path,
        make_produces_check_failed_event(
            ("review",), "out", check_id="json_file:v1", reason=rejection_reason,
        ),
    )
    seed_event(
        events_path,
        make_cursor_rewind_event(("review",), reason="produces_check_failed"),
    )

    rc, out, err = _capture(projects)
    assert rc == 0, f"out={out!r} err={err!r}"
    assert "Previous attempt rejected" in out
    assert rejection_reason in out, (
        f"rewind message must echo produces_check_failed.reason from events[-2]; got {out!r}"
    )


def test_b_host_close_hint_when_items_complete_without_host_attested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Branch (2): tail = item_attested with all items closed but no host
    step_attested. Phase-1 autoclose is neutralized so this fires.
    """
    monkeypatch.setattr(
        "astrid.core.task.gate._maybe_autoclose_for_each_host",
        lambda *a, **k: None,
    )
    packs, projects = setup_run(
        tmp_path, "demo", "fe", _BODY_FE, "demo.fe", run_id="rb",
    )
    events_path = projects / "p" / "runs" / "rb" / "events.jsonl"
    seed_event(events_path, make_for_each_expanded_event(("review_each",), ("a", "b", "c")))
    for item in ("a", "b", "c"):
        seed_event(
            events_path,
            make_item_attested_event(
                ("review_each",), item, attestor_kind="human", attestor_id="alice",
            ),
        )

    rc, out, err = _capture(projects)
    assert rc == 0, f"out={out!r} err={err!r}"
    assert "All items complete" in out, out
    assert "omit --item" in out, out


def test_c_run_complete_emits_run_completed_exactly_once(tmp_path: Path) -> None:
    """Branch (3): all leaves terminal → emit run_completed exactly once
    AND release the active-run pointer so the project is ready for the
    next orchestrator (#25). The second cmd_next call goes into the
    no-active-run discovery branch (because current_run.json was cleared),
    not the run-complete branch — which is the correct UX for sequential
    orchestrators (seq probe finding).

    What the test still asserts:
      - The first cmd_next prints "Run complete".
      - The second cmd_next does NOT emit a second run_completed event
        (centralized helper guard + cleared pointer both prevent it).
      - Exactly one run_completed event lands on disk.
    """
    packs, projects = setup_run(
        tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="rc",
    )
    events_path = projects / "p" / "runs" / "rc" / "events.jsonl"
    seed_event(events_path, make_step_completed_event("step_a", returncode=0))

    rc1, out1, _ = _capture(projects)
    assert rc1 == 0
    assert "Run complete" in out1, out1

    rc2, out2, _ = _capture(projects)
    # Second call: current_run.json was cleared on first emission, so
    # cmd_next goes into the no-active-run hint. Still rc=0 (universal
    # port-of-call never errors).
    assert rc2 == 0
    assert "Run complete" not in out2, (
        f"second cmd_next must NOT re-print 'Run complete' once the pointer is cleared; got: {out2!r}"
    )

    events = read_events(events_path)
    run_completed = [e for e in events if isinstance(e, dict) and e.get("kind") == "run_completed"]
    assert len(run_completed) == 1, (
        f"run_completed must be emitted exactly once across two cmd_next calls; "
        f"got {len(run_completed)}: {run_completed!r}"
    )


def test_c2_real_world_event_order_after_attested(tmp_path: Path) -> None:
    """C2 regression — real-world event order after a successful attested ack.

    Reproduces the 12-DeepSeek probe finding: when an attested step's final
    ack succeeds and the gate's inline produces-check passes, the event
    sequence is ``step_attested`` THEN ``produces_check_passed`` — the
    produces-check event is the absolute tail, not ``step_attested``. The
    previous ``_run_is_complete`` shadowed the lifecycle event with the
    advisory one and returned False, so ``run_completed`` never fired.

    This test uses a pack with a ``produces``-bearing attested step and
    asserts that even when the produces-check event is the tail, the run
    is recognised as complete and ``run_completed`` lands.
    """
    packs, projects = setup_run(
        tmp_path, "demo", "with_produces", _BODY_PRODUCES, "demo.with_produces", run_id="rc2",
    )
    events_path = projects / "p" / "runs" / "rc2" / "events.jsonl"
    # Real-world event order from _dispatch_attested + _run_inline_checks:
    seed_event(events_path, make_step_attested_event("review", "human", "tester", evidence=()))
    seed_event(
        events_path,
        make_produces_check_passed_event(
            ("review",), "out", check_id="json_file", cas_sha256=None,
        ),
    )

    rc, out, _ = _capture(projects)
    assert rc == 0
    assert "Run complete" in out, (
        f"After step_attested → produces_check_passed (real-world order), "
        f"cmd_next must recognise run as complete. Got out={out!r}"
    )
    events = read_events(events_path)
    run_completed = [e for e in events if isinstance(e, dict) and e.get("kind") == "run_completed"]
    assert len(run_completed) == 1, (
        f"run_completed must fire exactly once; got {len(run_completed)}"
    )


def test_d_exhausted_but_incomplete_state_derived_message(tmp_path: Path) -> None:
    """Branch (4) fall-through: cursor exhausted yet _run_is_complete is
    False (latest event for leaf is step_dispatched, not terminal). The
    state-derived 'cursor parked at <path>' message must reach stderr; no
    run_completed may land.
    """
    packs, projects = setup_run(
        tmp_path, "demo", "code", _BODY_CODE, "demo.code", run_id="rd",
    )
    events_path = projects / "p" / "runs" / "rd" / "events.jsonl"
    # step_completed advances the cursor → peek.exhausted=True.
    seed_event(events_path, make_step_completed_event("step_a", returncode=0))
    # …then a later step_dispatched flips the latest-kind for the leaf back
    # to a non-terminal value so _run_is_complete returns False.
    seed_event(
        events_path,
        make_step_dispatched_event("step_a", command="echo x", adapter="local"),
    )

    rc, out, err = _capture(projects)
    assert rc == 0, f"out={out!r} err={err!r}"
    assert "cursor parked at" in err, f"expected state-derived message on stderr; got err={err!r}"
    assert "no legal action" in err, err
    # Old misleading "awaiting_fetch or in-flight" wording must NOT reappear.
    assert "awaiting_fetch" not in err, err
    events = read_events(events_path)
    assert not any(
        isinstance(e, dict) and e.get("kind") == "run_completed" for e in events
    ), "run_completed must NOT land in exhausted-but-incomplete state"


def test_negative_neutralize_dispatch_from_tail_reverts_to_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monkeypatch-only negative (SD-005 / FLAG-S1-006): with
    ``_dispatch_from_tail`` forced to return ``None``, the rewind branch's
    canonical 'Previous attempt rejected' message must NOT appear — proving
    tail-dispatch is the sole producer of that text and the audit's negative
    coverage has bite.
    """
    monkeypatch.setattr(lifecycle, "_dispatch_from_tail", lambda *a, **k: None)

    packs, projects = setup_run(
        tmp_path, "demo", "with_produces", _BODY_PRODUCES, "demo.with_produces", run_id="rn",
    )
    events_path = projects / "p" / "runs" / "rn" / "events.jsonl"
    seed_event(
        events_path,
        make_produces_check_failed_event(
            ("review",), "out", check_id="json_file:v1", reason="rejected",
        ),
    )
    seed_event(
        events_path,
        make_cursor_rewind_event(("review",), reason="produces_check_failed"),
    )

    rc, out, err = _capture(projects)
    assert "Previous attempt rejected" not in out, (
        f"with _dispatch_from_tail neutralized, the rewind message must disappear; "
        f"out={out!r}"
    )
