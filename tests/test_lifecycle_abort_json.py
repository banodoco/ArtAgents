"""T5: ``cmd_abort --json`` structured output and idempotency tests.

Verifies:
- ``--json`` emits exactly one JSON object with shared lifecycle fields.
- ``--json`` works for both active abort and no-active-run idempotency.
- Lease-release behavior (clear_current_run, release_writer_lease) unchanged.
- Default mode keeps human "aborted <run_id>" on stdout.
- Exactly-one-object-one-newline discipline in JSON mode.
"""

from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lifecycle_fixtures import setup_run  # noqa: E402

from astrid.core.task.lifecycle import cmd_abort  # noqa: E402
from tests.helpers.current_run import read_seeded_current_run  # noqa: E402

_ABORT_SHARED_KEYS = {
    "schema_version",
    "project",
    "run_id",
    "state",
}

_BODY = '''from astrid.orchestrate import orchestrator, code
@orchestrator("demo.app")
def app(): return [code("step_a", argv=["echo", "x"])]
'''


def _capture_all(*argv: str, projects: Path) -> tuple[int, str, str]:
    """Return (rc, stdout, stderr)."""
    import io as _io
    from contextlib import redirect_stderr as _redirect_stderr
    out = _io.StringIO()
    err = _io.StringIO()
    with redirect_stdout(out), _redirect_stderr(err):
        rc = cmd_abort(list(argv), projects_root=projects)
    return rc, out.getvalue(), err.getvalue()


def _json_payload(*argv: str, projects: Path) -> dict:
    rc, stdout, stderr = _capture_all(*argv, projects=projects)
    assert rc == 0, f"rc={rc} stderr={stderr!r}"
    assert stdout.count("\n") == 1, f"expected exactly one newline, got {stdout!r}"
    payload = json.loads(stdout)
    assert isinstance(payload, dict)
    return payload


def test_abort_json_has_shared_lifecycle_fields(tmp_path: Path) -> None:
    """--json on an active run emits shared lifecycle fields (schema_version, project, run_id, state)."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r1")
    assert read_seeded_current_run("p", root=projects) is not None

    payload = _json_payload("--project", "p", "--json", projects=projects)

    for key in _ABORT_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"
    assert payload["schema_version"] == 1
    assert payload["project"] == "p"
    assert payload["run_id"] == "r1"
    assert payload["state"] == "aborted"

    # Verify run_aborted event was appended.
    events = [
        json.loads(line)
        for line in (projects / "p" / "runs" / "r1" / "events.jsonl").read_text().splitlines()
    ]
    assert events[-1]["kind"] == "run_aborted"
    assert events[-1]["run_id"] == "r1"


def test_abort_json_clears_active_run_and_releases_lease(tmp_path: Path) -> None:
    """--json preserves the lease-release behavior: active_run.json cleared, lease released."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r2")
    assert read_seeded_current_run("p", root=projects) is not None

    rc, stdout, stderr = _capture_all("--project", "p", "--json", projects=projects)
    assert rc == 0

    # Active run pointer is cleared.
    assert read_seeded_current_run("p", root=projects) is None

    # Lease file is removed (lease path is .astrid-writer-lease inside the run dir).
    lease_path = projects / "p" / "runs" / "r2" / ".astrid-writer-lease"
    assert not lease_path.exists(), f"lease file still exists at {lease_path}"


def test_abort_json_idempotent_no_active_run(tmp_path: Path) -> None:
    """--json on a project with no active run returns state=no_active_run and rc=0."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r3")
    # First abort: active run exists.
    rc1, _, _ = _capture_all("--project", "p", "--json", projects=projects)
    assert rc1 == 0
    assert read_seeded_current_run("p", root=projects) is None

    # Second abort (idempotent): no active run.
    payload = _json_payload("--project", "p", "--json", projects=projects)
    assert payload["state"] == "no_active_run"
    assert payload["project"] == "p"
    assert payload["run_id"] is None
    for key in _ABORT_SHARED_KEYS:
        assert key in payload, f"missing shared key {key!r}"


def test_abort_json_idempotent_returns_zero(tmp_path: Path) -> None:
    """Second --json abort call (no active run) still returns 0 and JSON."""
    projects = tmp_path / "projects"
    projects.mkdir()

    # Directly call abort on a project with no runs at all.
    rc, stdout, stderr = _capture_all("--project", "missing_proj", "--json", projects=projects)
    assert rc == 0
    payload = json.loads(stdout.strip())
    assert payload["state"] == "no_active_run"
    assert payload["project"] == "missing_proj"
    assert payload["run_id"] is None


def test_abort_default_mode_prints_human_message(tmp_path: Path) -> None:
    """Default mode prints 'aborted <run_id>' to stdout (no --json)."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r5")
    assert read_seeded_current_run("p", root=projects) is not None

    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cmd_abort(["--project", "p"], projects_root=projects)
    assert rc == 0
    assert "aborted r5" in buf.getvalue()

    # Active run was still cleared.
    assert read_seeded_current_run("p", root=projects) is None


def test_abort_json_one_object_one_newline(tmp_path: Path) -> None:
    """--json emits exactly one JSON object terminated by exactly one newline."""
    packs, projects = setup_run(tmp_path, "demo", "app", _BODY, "demo.app", run_id="r7")
    rc, stdout, stderr = _capture_all("--project", "p", "--json", projects=projects)
    assert rc == 0
    assert stdout.count("\n") == 1, f"expected exactly 1 newline, got {stdout.count(chr(10))} in {stdout!r}"
    obj = json.loads(stdout)
    assert isinstance(obj, dict)
