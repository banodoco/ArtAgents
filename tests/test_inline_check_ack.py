"""Phase 3 Step 8 — cmd_ack exits non-zero with the rejection reason on
stderr when the inline produces-check rejects, AND the asymmetry contract
holds: code-step rewinds emitted by ``record_dispatch_complete`` MUST NOT
populate ``GateDecision.inline_check_result`` and MUST NOT surface through
``cmd_ack``'s 'ack accepted but produces check failed' branch (FLAG-S1-005
/ correctness-2 / callers-2).

(a) Positive: an attested step with a missing produces artifact. The first
    ``cmd_ack`` call returns exit 2 and stderr contains both the produces
    name and a rejection reason.

(b) Asymmetry: a CODE step's ``record_dispatch_complete`` runs the same
    inline-checks plumbing internally (gate.py:1415) but MUST NOT set
    ``decision.inline_check_result`` (the field is only populated in
    ``_dispatch_attested``). The matching ``cmd_ack`` invocation is a
    category error for code steps anyway, so the canonical 'ack accepted,
    but produces check failed' line must NEVER appear regardless.
"""

from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from tests.conftest import seed_event as append_event
from astrid.core.task.events import (
    make_produces_check_failed_event,
    make_step_dispatched_event,
    read_events,
)
from astrid.core.task.gate import (
    GateDecision,
    gate_command,
    record_dispatch_complete,
)
from astrid.core.task.lifecycle import cmd_ack


_ATTESTED_PRODUCES = '''from astrid.core.orchestrate import orchestrator, attested
from astrid.core.verify import json_file
@orchestrator("demo.attested_with_produces")
def main(): return [attested("review", command="review.sh", instructions="check", ack="agent", produces={"out": json_file()})]
'''

_CODE_WITH_PRODUCES = '''from astrid.core.orchestrate import orchestrator, code
from astrid.core.verify import json_file
@orchestrator("demo.code_with_produces")
def main(): return [code("step_a", argv=["python3", "-m", "astrid", "next", "--project", "p"], produces={"out": json_file()})]
'''


def _ack(projects: Path, *args: str) -> tuple[int, str, str]:
    buf, err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf), redirect_stderr(err):
        rc = cmd_ack(list(args), projects_root=projects)
    return rc, buf.getvalue(), err.getvalue()


def test_a_attested_inline_check_rejects_exit_2_with_reason(tmp_path: Path) -> None:
    """Positive — schema_strict-shaped failure mode: artifact is absent so
    the inline ``json_file`` check rejects on first ack. cmd_ack must
    surface name + reason on stderr and exit 2.
    """
    packs, projects = setup_run(
        tmp_path, "demo", "attested_with_produces", _ATTESTED_PRODUCES,
        "demo.attested_with_produces", run_id="ra",
    )
    os.environ["ASTRID_ACTOR"] = "alice"
    rc, out, err = _ack(
        projects, "review", "--project", "p", "--decision", "approve",
        "--agent", "test-agent",
    )
    assert rc == 2, (
        f"cmd_ack must exit 2 (distinct from generic 1) when inline check rejects; "
        f"rc={rc} out={out!r} err={err!r}"
    )
    assert "ack accepted, but produces check failed" in err, err
    assert "out" in err, f"stderr must include produces name 'out'; got {err!r}"
    # Event log proves the rewind landed.
    events = read_events(projects / "p" / "runs" / "ra" / "events.jsonl")
    assert any(
        e.get("kind") == "produces_check_failed" and e.get("produces_name") == "out"
        for e in events
    ), events
    assert any(e.get("kind") == "cursor_rewind" for e in events), events


def test_b_code_step_record_dispatch_complete_does_not_set_inline_check_result(
    tmp_path: Path,
) -> None:
    """Asymmetry contract (FLAG-S1-005 / callers-2): a CODE step whose
    produces fails the inline check emits ``produces_check_failed`` +
    ``cursor_rewind`` through ``record_dispatch_complete`` — but the
    ``GateDecision`` returned by ``gate_command`` keeps
    ``inline_check_result is None``. ``cmd_ack`` rejects code-step approve
    anyway, but the canonical 'ack accepted, but produces check failed'
    line must NEVER appear for the code-step rewind surface.
    """
    packs, projects = setup_run(
        tmp_path, "demo", "code_with_produces", _CODE_WITH_PRODUCES,
        "demo.code_with_produces", run_id="rb",
    )
    incoming = "python3 -m astrid next --project p"
    decision = gate_command(
        "p", incoming, ["python3", "-m", "astrid", "next", "--project", "p"],
        root=projects,
    )
    assert decision.active
    assert decision.step_kind == "code"
    # Pre-condition: the dispatch path itself MUST NOT populate
    # inline_check_result — only _dispatch_attested does.
    assert decision.inline_check_result is None, (
        f"gate_command on a code step must leave inline_check_result None; "
        f"got {decision.inline_check_result!r}"
    )

    # record_dispatch_complete will run inline checks (gate.py:1415);
    # artifact is missing so produces_check_failed + cursor_rewind land.
    record_dispatch_complete(decision, 0)
    events = read_events(projects / "p" / "runs" / "rb" / "events.jsonl")
    assert any(e.get("kind") == "produces_check_failed" for e in events), events
    assert any(e.get("kind") == "cursor_rewind" for e in events), events

    # The decision instance itself was returned BEFORE record_dispatch_complete
    # ran, so its inline_check_result must still be None — record_dispatch_complete
    # intentionally does not mutate the field (asymmetry per FLAG-S1-005).
    assert decision.inline_check_result is None

    # cmd_ack approve on a code step is rejected (category error). The
    # canonical inline-check rejection line must NOT appear — that surface
    # is reserved for the attested path.
    os.environ["ASTRID_ACTOR"] = "alice"
    rc, out, err = _ack(
        projects, "step_a", "--project", "p", "--decision", "approve",
        "--human", "alice",
    )
    assert "ack accepted, but produces check failed" not in err, (
        f"code-step rewinds must never surface through cmd_ack's rejection branch; "
        f"err={err!r}"
    )
