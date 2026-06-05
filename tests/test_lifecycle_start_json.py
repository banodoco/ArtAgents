"""T7: ``cmd_start --json`` structured output and metadata tests.

Verifies:
- ``--json`` emits exactly one JSON object with shared lifecycle fields.
- ``--json`` includes run metadata (orchestrator_id, timeline_slug, plan_hash).
- ``--json`` includes next_command for agent workflow.
- Default mode keeps human stdout unchanged.
- Exactly-one-object-one-newline discipline in JSON mode.
- Active-run-rejected failure path unchanged by --json addition.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import bind_writer_session, setup_packs_and_compile  # noqa: E402

from astrid.core.project.project import create_project  # noqa: E402
from astrid.core.task.lifecycle import cmd_start  # noqa: E402
from astrid.core.task.plan import compute_plan_hash  # noqa: E402
from astrid.core.timeline.crud import create_timeline  # noqa: E402
from tests.helpers.current_run import read_seeded_current_run  # noqa: E402

_START_SHARED_KEYS = {
    "schema_version",
    "project",
    "run_id",
    "state",
}

_START_METADATA_KEYS = {
    "orchestrator_id",
    "timeline_slug",
    "plan_hash",
    "next_command",
}

_BODY_CODE = '''from astrid.orchestrate import orchestrator, code
@orchestrator("demo.app")
def app(): return [code("step_a", argv=["echo", "x"])]
'''


def _capture_all(*argv: str, packs: Path, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cmd_start(list(argv), packs_root=packs, projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _json_payload(*argv: str, packs: Path, projects: Path) -> dict:
    """Run cmd_start with --json, assert success, return parsed payload."""
    rc, stdout, stderr = _capture_all(*argv, packs=packs, projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


# ---------------------------------------------------------------------------
# JSON success: shared lifecycle fields
# ---------------------------------------------------------------------------


def test_start_json_has_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json on success emits shared lifecycle fields (schema_version, project, run_id, state)."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    payload = _json_payload(
        "demo.app", "--project", "p", "--name", "r1", "--json",
        packs=packs, projects=projects,
    )

    for key in _START_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == "p"
    assert payload["run_id"] == "r1"
    assert payload["state"] == "started"


# ---------------------------------------------------------------------------
# JSON success: run metadata
# ---------------------------------------------------------------------------


def test_start_json_includes_run_metadata(tmp_path: Path) -> None:
    """--json includes orchestrator_id, timeline_slug, plan_hash, next_command."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    payload = _json_payload(
        "demo.app", "--project", "p", "--name", "r2", "--json",
        packs=packs, projects=projects,
    )

    for key in _START_METADATA_KEYS:
        assert key in payload, f"missing metadata key {key!r}"
    assert payload["orchestrator_id"] == "demo.app"
    assert payload["timeline_slug"] == "main"
    assert isinstance(payload["plan_hash"], str)
    assert payload["plan_hash"].startswith("sha256:")
    assert payload["next_command"] == "astrid next --project p"


# ---------------------------------------------------------------------------
# JSON discipline
# ---------------------------------------------------------------------------


def test_start_json_exactly_one_object_one_newline(tmp_path: Path) -> None:
    """--json outputs exactly one JSON object followed by a single newline."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    rc, stdout, stderr = _capture_all(
        "demo.app", "--project", "p", "--name", "r3", "--json",
        packs=packs, projects=projects,
    )
    assert rc == 0
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    # No extraneous content on stdout beyond the JSON object + newline.
    stripped = stdout.strip()
    assert stripped.startswith("{") and stripped.endswith("}")


# ---------------------------------------------------------------------------
# Default mode unchanged
# ---------------------------------------------------------------------------


def test_start_default_mode_prints_human_stdout(tmp_path: Path) -> None:
    """Default mode (no --json) keeps the human-readable stdout unchanged."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    rc, stdout, stderr = _capture_all(
        "demo.app", "--project", "p", "--name", "r4",
        packs=packs, projects=projects,
    )
    assert rc == 0
    lines = stdout.splitlines()
    assert lines[0] == "started demo.app"
    assert "  project:   p" in stdout
    assert "  timeline:  main" in stdout
    assert "  run-id:    r4" in stdout
    assert "  plan-hash:" in stdout


# ---------------------------------------------------------------------------
# Active-run-rejected failure unchanged
# ---------------------------------------------------------------------------


def test_start_json_second_start_rejected_unchanged(tmp_path: Path) -> None:
    """Active-run rejection still returns 1 (unchanged) regardless of --json."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    # First start succeeds.
    cmd_start(
        ["demo.app", "--project", "p", "--name", "r5"],
        packs_root=packs, projects_root=projects,
    )

    # Second start with --json: active-run rejection still returns 1.
    rc, stdout, stderr = _capture_all(
        "demo.app", "--project", "p", "--json",
        packs=packs, projects=projects,
    )
    assert rc == 1
    assert "active run already exists" in stderr
    assert "astrid abort --project p" in stderr


# ---------------------------------------------------------------------------
# JSON success: plan_hash is correct
# ---------------------------------------------------------------------------


def test_start_json_plan_hash_matches_computed(tmp_path: Path) -> None:
    """--json plan_hash matches compute_plan_hash of the written plan."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    payload = _json_payload(
        "demo.app", "--project", "p", "--name", "r6", "--json",
        packs=packs, projects=projects,
    )

    expected_hash = compute_plan_hash(projects / "p" / "plan.json")
    assert payload["plan_hash"] == expected_hash


# ---------------------------------------------------------------------------
# JSON success: run is actually created (side effects preserved)
# ---------------------------------------------------------------------------


def test_start_json_creates_run_and_events(tmp_path: Path) -> None:
    """--json does not skip any side effects: run dir, events, AGENT.md all created."""
    packs, projects = setup_packs_and_compile(
        tmp_path, "demo", "app", _BODY_CODE, "demo.app"
    )
    create_project("p", root=projects)
    create_timeline("p", "main", root=projects, is_default=True)
    bind_writer_session(projects, "p")

    _json_payload(
        "demo.app", "--project", "p", "--name", "r7", "--json",
        packs=packs, projects=projects,
    )

    run_dir = projects / "p" / "runs" / "r7"
    assert run_dir.is_dir()
    assert (run_dir / "plan.json").is_file()
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "AGENT.md").is_file()
    events_path = run_dir / "events.jsonl"
    assert events_path.is_file()
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(events) >= 2
    assert events[0]["kind"] == "plan_initialized"
    assert events[1]["kind"] == "run_started"

    # Active run pointer is set.
    active = read_seeded_current_run("p", root=projects)
    assert active is not None
    assert active["run_id"] == "r7"
