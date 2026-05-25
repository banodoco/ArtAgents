"""Sprint 1 CLI gate tests: the unbound allowlist and 'no session bound' error."""

from __future__ import annotations

import json
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from astrid import pipeline
from astrid.core.project import paths as project_paths
from astrid.core.project.project import create_project
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.identity import Identity, write_identity
from astrid.core.session.model import Session

# Settled Sprint 1 unbound contract. The implementation may temporarily carry
# compatibility exceptions during migration, but the final gate must match this
# list exactly: help/version, status, next, attach, pack management,
# projects ls/create/default, sessions ls, and sessions takeover.
EXPECTED_SPRINT1_UNBOUND_ALLOWLIST = (
    ("-h",),
    ("--help",),
    ("help",),
    ("--version",),
    ("status",),
    ("next",),
    ("attach",),
    ("projects", "ls"),
    ("projects", "create"),
    ("projects", "default"),
    ("sessions", "ls"),
    ("sessions", "takeover"),
    ("packs",),
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _run_pipeline(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    rc = -1
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = pipeline.main(argv)
        except SystemExit as exc:
            # Sub-CLIs (argparse) may sys.exit on bad args. For the gate
            # tests, the important signal is whether the SESSION gate
            # rejected the verb — not whether the downstream parser
            # accepted it. Capture and surface the exit code so the
            # asserts can still distinguish a 'no session bound' rejection
            # (rc==2 with the literal banner in stderr) from any other
            # outcome.
            rc = int(exc.code) if isinstance(exc.code, int) else 2
    return rc, out.getvalue(), err.getvalue()


def _action_lines(output: str) -> list[str]:
    return [
        line.strip()
        for line in output.splitlines()
        if line.strip().startswith("astrid ")
    ]


# ----- gated verbs error without a session ------------------------------


GATED_INVOCATIONS = [
    pytest.param(["doctor"], id="doctor"),
    pytest.param(["setup"], id="setup"),
    pytest.param(["start", "pack.thing", "--project", "demo"], id="start"),
    # `next` is intentionally NOT in this list as of #13 — it's the universal
    # port-of-call and ALWAYS returns rc=0 with a state-derived hint,
    # including when unbound. See `test_unbound_next_prints_discovery_hint`.
    pytest.param(["ack", "step", "--project", "demo", "--decision", "approve"], id="ack"),
    pytest.param(["abort", "--project", "demo"], id="abort"),
    pytest.param(["projects", "show", "--project", "demo"], id="projects-show"),
    pytest.param(["projects", "edit", "demo"], id="projects-edit"),
    pytest.param(["runs", "ls"], id="runs-ls"),
    pytest.param(["author", "describe", "pack.thing"], id="author-describe"),
    pytest.param(["executors", "list"], id="executors-list"),
    pytest.param(["orchestrators", "list"], id="orchestrators-list"),
    pytest.param(["elements", "list"], id="elements-list"),
    pytest.param(["audit", "--run", "x"], id="audit"),
]


@pytest.mark.parametrize("argv", GATED_INVOCATIONS)
def test_every_gated_verb_errors_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, _stdout, stderr = _run_pipeline(argv)
    assert rc == 2
    assert stderr.splitlines()[0] == "first recovery action: astrid status"
    assert "no session bound" in stderr
    assert "astrid status" in stderr
    assert "astrid attach" in stderr


def test_unbound_next_prints_discovery_hint(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`astrid next` (with or without --project) when unbound is rc=0 and
    prints a state-derived hint. Universal port-of-call (#13): `next` is
    never an error; it always tells the agent the single next action.
    """
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["next", "--project", "demo"])
    assert rc == 0
    assert stderr == ""
    assert "no session bound" in stdout
    assert _action_lines(stdout) == ["astrid attach demo"]

    rc2, stdout2, stderr2 = _run_pipeline(["next"])
    assert rc2 == 0
    assert stderr2 == ""
    assert "no session bound" in stdout2
    assert _action_lines(stdout2) == ["astrid projects create <slug>"]


def test_unbound_gate_uses_the_frozen_allowlist_table() -> None:
    assert pipeline.SPRINT1_UNBOUND_ALLOWLIST_CONTRACT == EXPECTED_SPRINT1_UNBOUND_ALLOWLIST
    for allowed in EXPECTED_SPRINT1_UNBOUND_ALLOWLIST:
        assert pipeline._verb_is_unbound_allowlisted(list(allowed))


def test_stop_line_unbound_gate_has_no_transitional_extras() -> None:
    transitional_extras = [
        ["init"],
        ["models", "validate"],
        ["models", "doctor"],
        ["runpod", "volumes", "ls"],
        ["author", "test", "pack.thing", "--project", "demo"],
        ["sessions", "detach"],
        ["executors", "inspect", "builtin.render"],
        ["orchestrators", "inspect", "builtin.hype"],
        ["elements", "inspect", "effects", "text-card"],
        ["timelines", "ls"],
    ]
    still_allowed = [
        argv for argv in transitional_extras if pipeline._verb_is_unbound_allowlisted(argv)
    ]
    assert still_allowed == []


# ----- unbound verbs -----------------------------------------------------


def test_allowlist_status_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["status"])
    assert rc == 0
    assert stderr == ""
    assert "no session bound" in stdout


def test_allowlist_attach_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    create_project("demo")

    # Seed a default timeline so Sprint 2 resolution works.
    from astrid import timeline as timeline_contract
    from astrid.core.session.ulid import generate_ulid

    timeline_ulid = generate_ulid()
    pdir = env["projects"] / "demo"
    tdir = pdir / "timelines" / timeline_ulid
    tdir.mkdir(parents=True)
    (tdir / "assembly.json").write_text(
        json.dumps(timeline_contract.canonical_empty_timeline()), encoding="utf-8"
    )
    (tdir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )
    (tdir / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "primary",
                "name": "Primary",
                "is_default": True,
            }
        ),
        encoding="utf-8",
    )
    # Update project.json with the default timeline id.
    from astrid.core.project.jsonio import read_json, write_json_atomic

    pp = pdir / "project.json"
    proj = read_json(pp)
    proj["default_timeline_id"] = timeline_ulid
    write_json_atomic(pp, proj)

    rc, stdout, stderr = _run_pipeline(["attach", "demo"])
    assert rc == 0
    assert stderr == "Using default timeline: primary. Use --timeline to override.\n"
    assert "export ASTRID_SESSION_ID=" in stdout


def test_allowlist_projects_ls_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, _stdout, stderr = _run_pipeline(["projects", "ls"])
    assert rc == 0
    assert stderr == ""


def test_allowlist_projects_default_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, _stdout, stderr = _run_pipeline(["projects", "default"])
    assert rc == 0
    assert stderr == ""


def test_allowlist_projects_create_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["projects", "create", "demo"])
    assert rc == 0
    assert stderr == ""
    assert "created: demo" in stdout


def test_allowlist_sessions_ls_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["sessions", "ls"])
    assert rc == 0
    assert stderr == ""
    assert stdout == "no sessions\n"


def test_allowlist_help_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["--help"])
    assert rc == 0
    assert stderr == ""
    assert "Astrid command gateway" in stdout


def test_allowlist_version_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["--version"])
    assert rc == 0
    assert stdout == "astrid\n"
    assert stderr == ""


def test_non_allowlisted_subcommand_help_is_blocked_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["projects", "--help"])
    assert rc == 2
    assert stdout == ""
    assert stderr.splitlines()[0] == "first recovery action: astrid status"
    assert "no session bound" in stderr


def test_status_help_runs_without_rendering_live_status(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["status", "--help"])
    assert rc == 0
    assert "no session bound" not in stdout
    assert "show this help message" in stdout
    assert stderr == ""


def test_unbound_sessions_takeover_reaches_takeover_handler(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from astrid.core.session import cli as session_cli

    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    def fake_takeover(args: object) -> int:
        assert getattr(args, "target") == "RUN-1"
        return 77

    monkeypatch.setattr(session_cli, "cmd_sessions_takeover", fake_takeover)
    rc, stdout, stderr = _run_pipeline(["sessions", "takeover", "RUN-1"])
    assert rc == 77
    assert stdout == ""
    assert stderr == ""


def test_author_test_with_project_is_blocked_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["author", "test", "pack.thing", "--project", "demo"])
    assert rc == 2
    assert stdout == ""
    assert stderr.splitlines()[0] == "first recovery action: astrid status"
    assert "no session bound" in stderr


def test_bound_session_lets_gated_verb_through(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mint a minimal session so resolve_current_session succeeds.
    sess = Session(
        id="S-CLI",
        project="demo",
        timeline=None,
        run_id=None,
        agent_id="claude-1",
        attached_at="2026-05-11T00:00:00Z",
        last_used_at="2026-05-11T00:00:00Z",
        role="writer",
    )
    sessions = env["home"] / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    sess.to_json(sessions / "S-CLI.json")
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, "S-CLI")

    # `executors list` is a gated verb; it should now pass the gate and
    # produce its own output (the test only cares the gate didn't reject).
    rc, _stdout, stderr = _run_pipeline(["executors", "list"])
    assert "no session bound" not in stderr


def test_bound_session_missing_file_errors_with_hint(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ASTRID_SESSION_ID_ENV, "S-DOES-NOT-EXIST")
    rc, _stdout, stderr = _run_pipeline(["executors", "list"])
    assert rc == 2
    # The SessionBindingError message is what surfaces, not the bare
    # "no session bound" gate hint.
    assert "no session file" in stderr or "session:" in stderr
