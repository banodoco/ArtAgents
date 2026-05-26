"""Phase 9 author-test auto-approval mode (FLAG-P9-001 + FLAG-P9-002).

Behavior under test:
  * cmd_start succeeds with ASTRID_AUTHOR_TEST=1 (FLAG-P9-001 — no guard).
  * Without ASTRID_AUTHOR_TEST, an ack with --human mismatching
    ASTRID_ACTOR is rejected (existing self-ack-prep guard fires).
  * With ASTRID_AUTHOR_TEST=1, the same mismatched ack succeeds. The
    resulting step_attested event keeps the canonical attestor_kind='human'
    (NOT 'author_test' — FLAG-P9-002) and gains source='author_test' on the
    way through _dispatch_attested.

Run state is seeded via cmd_start (FLAG-P9-004); we never write
active_run.json/plan.json by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import bind_writer_session, setup_packs_and_compile  # noqa: E402

from astrid.core.task.env import ASTRID_ACTOR, ASTRID_AUTHOR_TEST
from astrid.core.task.events import read_events
from astrid.core.task.lifecycle import cmd_start
from astrid.core.task.lifecycle_ack import cmd_ack
from astrid.orchestrate.test_runner import _finish_code_step, run_fixture


_DEMO_PACK_BODY = '''from astrid.orchestrate import attested, orchestrator


@orchestrator("demo.app")
def app():
    return [
        attested(
            "review",
            command="review",
            instructions="approve",
            ack="human",
        ),
    ]
'''

_CODE_PACK_BODY = '''from astrid.orchestrate import code, orchestrator

@orchestrator("demo.code_once")
def app():
    return [code("write_once", argv=["python3", "-c", {script!r}])]
'''


def _make_demo_pack(tmp_path: Path) -> Path:
    packs = tmp_path / "packs"
    pack = packs / "demo"
    pack.mkdir(parents=True)
    (pack / "app.py").write_text(_DEMO_PACK_BODY, encoding="utf-8")
    return packs


def test_author_test_env_var_unlocks_attested_auto_approval(
    tmp_path: Path,
    tmp_projects_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs = _make_demo_pack(tmp_path)
    slug = "auto_approval_demo"

    # FLAG-P9-001: cmd_start must succeed even when ASTRID_AUTHOR_TEST=1.
    # Compile the demo pack first (cmd_start expects build/<orch>.json).
    from astrid.orchestrate.compile import compile_to_path
    from astrid.core.project.project import create_project
    from astrid.core.timeline.crud import create_timeline
    compile_to_path("demo.app", packs_root=packs)
    # cmd_start requires the project to be registered before it accepts --project.
    create_project(slug, root=tmp_projects_root, exist_ok=True)
    create_timeline(slug, "main", is_default=True, root=tmp_projects_root)
    bind_writer_session(tmp_projects_root, slug)

    monkeypatch.setenv(ASTRID_ACTOR, "alice")
    monkeypatch.setenv(ASTRID_AUTHOR_TEST, "1")
    rc_start = cmd_start(
        ["demo.app", "--project", slug, "--name", "r1"],
        packs_root=packs,
        projects_root=tmp_projects_root,
    )
    assert rc_start == 0, "cmd_start must not gate on ASTRID_AUTHOR_TEST (FLAG-P9-001)"

    # Without ASTRID_AUTHOR_TEST, --human mismatch must be rejected.
    monkeypatch.delenv(ASTRID_AUTHOR_TEST, raising=False)
    rc_reject = cmd_ack(
        [
            "review",
            "--project",
            slug,
            "--decision",
            "approve",
            "--human",
            "mallory",
        ],
        projects_root=tmp_projects_root,
    )
    assert rc_reject != 0, "human mismatch must be rejected without ASTRID_AUTHOR_TEST"

    events_path = tmp_projects_root / slug / "runs" / "r1" / "events.jsonl"
    events_before = read_events(events_path)
    assert not any(
        ev.get("kind") == "step_attested" for ev in events_before
    ), "rejected ack must not write step_attested"

    # With ASTRID_AUTHOR_TEST=1, the same mismatched --human is accepted.
    monkeypatch.setenv(ASTRID_AUTHOR_TEST, "1")
    rc_accept = cmd_ack(
        [
            "review",
            "--project",
            slug,
            "--decision",
            "approve",
            "--human",
            "mallory",
        ],
        projects_root=tmp_projects_root,
    )
    assert rc_accept == 0, "human mismatch must be accepted with ASTRID_AUTHOR_TEST=1"

    events = read_events(events_path)
    last = events[-1]
    assert last["kind"] == "step_attested"
    # FLAG-P9-002: kind enum stays canonical ('human'), NOT 'author_test'.
    assert last["attestor_kind"] == "human"
    assert last["attestor"] == "human:mallory"
    assert last["attestor_id"] == "mallory"
    # Provenance rides on a separate event['source'] field.
    assert last["source"] == "author_test"


def test_runner_dispatches_exactly_once(
    tmp_path: Path,
    tmp_projects_root: Path,
) -> None:
    count_path = tmp_path / "dispatch-count.json"
    script = (
        "import json\n"
        "from pathlib import Path\n"
        f"path = Path({str(count_path)!r})\n"
        "count = 0\n"
        "if path.exists():\n"
        "    count = json.loads(path.read_text())['count']\n"
        "path.write_text(json.dumps({'count': count + 1}))\n"
    )
    packs, _projects = setup_packs_and_compile(
        tmp_path,
        "demo",
        "code_once",
        _CODE_PACK_BODY.format(script=script),
        "demo.code_once",
    )

    with patch(
        "astrid.orchestrate.test_runner._run_fallback_subprocess",
        side_effect=AssertionError("adapter-dispatched steps must not hit subprocess fallback"),
    ):
        events_path = run_fixture(
            qualified_id="demo.code_once",
            fixture_dir=None,
            packs_root=packs,
            projects_root=tmp_projects_root,
        )

    assert json.loads(count_path.read_text(encoding="utf-8")) == {"count": 1}
    events = read_events(events_path)
    assert [event["kind"] for event in events] == [
        "plan_initialized",
        "run_started",
        "step_dispatched",
        "step_completed",
    ]


def test_finish_code_step_uses_subprocess_fallback_for_non_adapter_steps() -> None:
    class _Decision:
        adapter = None

    decision = _Decision()
    with patch(
        "astrid.orchestrate.test_runner._run_fallback_subprocess",
        return_value=type("_Completed", (), {"returncode": 7})(),
    ) as run_fallback, patch(
        "astrid.orchestrate.test_runner.record_dispatch_complete"
    ) as record_complete:
        _finish_code_step(decision, ["echo", "fallback"])

    run_fallback.assert_called_once_with(["echo", "fallback"])
    record_complete.assert_called_once_with(decision, 7)
