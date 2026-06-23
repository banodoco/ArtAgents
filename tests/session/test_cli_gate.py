"""Sprint 1 CLI gate tests: the unbound allowlist and 'no session bound' error."""

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import pytest

from astrid.core import gateway
from astrid.core.foundation import project_paths
from astrid.core.project.project import create_project
from astrid.core.session import paths as session_paths
from astrid.core.session.binding import ASTRID_SESSION_ID_ENV
from astrid.core.session.identity import Identity, write_identity

# Settled Sprint 1 unbound contract. The implementation may temporarily carry
# compatibility exceptions during migration, but the final gate must match this
# list exactly: help/version, status, next, attach, pack management,
# projects ls/create/default/theme, themes ls, sessions ls, sessions takeover,
# doctor, and serve.
# `doctor` is a diagnostic that must run before any session exists (you run it
# precisely to debug an unconfigured workspace), so it is unbound-allowlisted.
# `serve` starts the local read bridge for local effect asset serving.
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
    ("projects", "theme"),
    ("themes", "ls"),
    ("sessions", "ls"),
    ("sessions", "takeover"),
    ("packs",),
    ("test",),
    ("doctor",),
    ("serve",),
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    monkeypatch.setenv(session_paths.ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    monkeypatch.setenv("ASTRID_NO_NUDGE", "1")
    (tmp_path / "home").mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    return {"home": tmp_path / "home", "projects": tmp_path / "projects"}


def _run_pipeline(argv: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    rc = -1
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = gateway.main(argv)
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
    assert stderr.splitlines()[0].startswith("no session bound")
    assert "no session bound" in stderr
    # After T5 fix: recovery is 'astrid attach <project>' when --project is in
    # argv, else 'astrid status'. Both forms start with 'astrid'.
    assert "recovery: astrid" in stderr
    assert "astrid attach" in stderr


def test_gate_does_not_resolve_stray_projects_root(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The gate must only scan ASTRID_PROJECTS_ROOT, not any other directory.

    Plants a valid .astrid-session under a *separate* stray root (standing in
    for what DEFAULT_PROJECTS_ROOT would be on disk) while ASTRID_PROJECTS_ROOT
    is already set to the env fixture's isolated tmp dir. The gated verb must
    still return rc=2 because gateway.py passes projects_root=resolve_projects_root()
    explicitly, so the stray root is never walked.
    """
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    # Build a stray root that looks like a real projects root with a bound session.
    stray_root = tmp_path / "stray_default_root"
    stray_project = stray_root / "demo"
    stray_project.mkdir(parents=True)
    (stray_project / "project.json").write_text('{"schema_version": 1}', encoding="utf-8")
    (stray_project / ".astrid-session").write_text("stray-session-id", encoding="utf-8")
    # ASTRID_PROJECTS_ROOT is already set to env["projects"] (an empty tmp dir)
    # by the env fixture — the stray_root is completely separate.
    rc, _stdout, stderr = _run_pipeline(["runs", "ls"])
    assert rc == 2
    assert "no session bound" in stderr


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
    assert gateway.SPRINT1_UNBOUND_ALLOWLIST_CONTRACT == EXPECTED_SPRINT1_UNBOUND_ALLOWLIST
    for allowed in EXPECTED_SPRINT1_UNBOUND_ALLOWLIST:
        assert gateway._verb_is_unbound_allowlisted(list(allowed))


def test_file_scoped_executor_run_infers_project_from_out_path(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    create_project("demo")
    monkeypatch.chdir(env["projects"].parent)

    slug = gateway._extract_project_slug_from_run_paths(
        [
            "executors",
            "run",
            "rendering.render",
            "--out",
            "projects/demo/runs/render",
        ]
    )

    assert slug == "demo"


def test_file_scoped_executor_run_infers_project_from_input_path(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    create_project("demo")
    monkeypatch.chdir(env["projects"].parent)

    slug = gateway._extract_project_slug_from_run_paths(
        [
            "executors",
            "run",
            "rendering.render",
            "--input",
            "timeline=projects/demo/runs/render/hype.timeline.json",
        ]
    )

    assert slug == "demo"


def test_file_scoped_executor_run_refuses_ambiguous_project_paths(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    create_project("demo")
    create_project("other")
    monkeypatch.chdir(env["projects"].parent)

    slug = gateway._extract_project_slug_from_run_paths(
        [
            "executors",
            "run",
            "rendering.render",
            "--out",
            "projects/demo/runs/render",
            "--input",
            "timeline=projects/other/runs/render/hype.timeline.json",
        ]
    )

    assert slug is None


def test_file_scoped_executor_run_errors_on_ambiguous_project_paths(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    create_project("demo")
    create_project("other")
    monkeypatch.chdir(env["projects"].parent)

    rc, _stdout, stderr = _run_pipeline(
        [
            "executors",
            "run",
            "rendering.render",
            "--out",
            "projects/demo/runs/render",
            "--input",
            "timeline=projects/other/runs/render/hype.timeline.json",
        ]
    )

    assert rc == 2
    assert "ambiguous project context" in stderr
    assert "pass --project <slug> explicitly" in stderr


def test_stop_line_unbound_gate_has_no_transitional_extras() -> None:
    transitional_extras = [
        ["init"],
        ["models", "validate"],
        ["models", "doctor"],
        ["runpod", "volumes", "ls"],
        ["author", "test", "pack.thing", "--project", "demo"],
        ["sessions", "detach"],
        ["executors", "inspect", "rendering.render"],
        ["orchestrators", "inspect", "video_editing.hype"],
        ["elements", "inspect", "effects", "text-card"],
        ["timelines", "ls"],
    ]
    still_allowed = [
        argv for argv in transitional_extras if gateway._verb_is_unbound_allowlisted(argv)
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
    from astrid.core import timeline as timeline_contract
    from astrid.core.threads.ids import generate_ulid

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
    from astrid.core._shared.jsonio import read_json, write_json_atomic

    pp = pdir / "project.json"
    proj = read_json(pp)
    proj["default_timeline_id"] = timeline_ulid
    write_json_atomic(pp, proj)

    rc, stdout, stderr = _run_pipeline(["attach", "demo"])
    assert rc == 0
    assert stderr == ""
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


def test_subcommand_help_runs_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--help` (or `-h`) anywhere in argv prints usage and exits 0 regardless
    of session state. Help text is just usage documentation; requiring a bound
    session to read it serves no purpose and breaks docs-command verification
    in a fresh checkout (e.g. CI). The session gate still applies to the real
    invocation of any non-allowlisted verb."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    rc, stdout, stderr = _run_pipeline(["projects", "--help"])
    assert rc == 0
    assert "no session bound" not in stdout
    assert "no session bound" not in stderr
    assert "usage:" in stdout


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
    from astrid.core.cli import session as session_cli

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
    assert stderr.splitlines()[0].startswith("no session bound")
    assert "no session bound" in stderr


def test_bound_session_lets_gated_verb_through(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mint a minimal session so resolve_current_session succeeds.
    from tests.conftest import make_session

    sess = make_session(id="S-CLI", run_id=None)
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


# ----- onboarding ceremony: stateless run auto-binds a default project ----


def test_stateless_executor_run_auto_binds_default_project_without_attach(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """A stateless `executors run --out` invocation must NOT require a prior
    `astrid attach`: the gate auto-binds a default project (creating it on
    first use) and sets ASTRID_SESSION_ID, then the run proceeds."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    out_dir = env["projects"].parent / "out"

    rc, _stdout, stderr = _run_pipeline(
        [
            "executors",
            "run",
            "generation.generate_image",
            "--out",
            str(out_dir),
            "--input",
            "model=flux-dev",
            "--input",
            "mode=t2i",
            "--input",
            "execution=cloud",
            "--input",
            "prompt=hello",
            "--dry-run",
        ]
    )

    assert "no session bound" not in stderr
    assert rc == 0
    assert "auto-bound default project 'default'" in capfd.readouterr().err
    # Default project was created on first use under the isolated projects root.
    assert (env["projects"] / "default" / "project.json").is_file()
    # A session pointer was written and the process is now bound for the run.
    import os

    assert (env["projects"] / "default" / ".astrid-session").is_file()
    assert os.environ.get(ASTRID_SESSION_ID_ENV)


def test_render_executor_run_accepts_asset_free_timeline_input(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    timeline_path = tmp_path / "asset-free.timeline.json"
    timeline_path.write_text(
        json.dumps(
            {
                "theme": "banodoco-default",
                "tracks": [{"id": "v1", "kind": "visual", "label": "Generated"}],
                "clips": [],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "render-out"
    commands: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        commands.append([str(part) for part in cmd])
        return subprocess.CompletedProcess(cmd, 0)

    from astrid.core.execution.executor import runner as executor_runner

    monkeypatch.setattr(executor_runner.subprocess, "run", fake_run)

    rc, stdout, stderr = _run_pipeline(
        [
            "executors",
            "run",
            "rendering.render",
            "--out",
            str(out_dir),
            "--input",
            f"timeline={timeline_path}",
        ]
    )

    assert rc == 0
    assert json.loads(stdout)["returncode"] == 0
    assert "no session bound" not in stderr
    assert len(commands) == 1
    command = commands[0]
    assert command[:3] == [
        sys.executable,
        "-m",
        "astrid.packs.rendering.executors.render.run",
    ]
    assert command[command.index("--timeline") + 1] == str(timeline_path)
    assert command[command.index("--out") + 1] == str(out_dir.resolve() / "hype.mp4")
    assert "--assets" not in command


def test_auto_bind_honors_configured_workspace_default_project(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """When a workspace/user default project is configured, auto-bind uses it
    instead of the literal ``default`` slug."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)
    from astrid.core.session.config import set_default_project

    set_default_project("scratch", scope="user")
    out_dir = env["projects"].parent / "out2"

    rc, _stdout, stderr = _run_pipeline(
        [
            "executors",
            "run",
            "understanding.understand",
            "--out",
            str(out_dir),
            "--input",
            "mode=describe",
            "--dry-run",
        ]
    )

    assert "no session bound" not in stderr
    assert "auto-bound default project 'scratch'" in capfd.readouterr().err
    # Auto-bind created the *configured* default ("scratch"), not the literal
    # fallback slug.
    assert (env["projects"] / "scratch" / "project.json").is_file()
    assert not (env["projects"] / "default").exists()


def test_gated_executors_list_still_errors_without_session(
    env: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auto-bind is scoped to `run` verbs only — non-run executor verbs (and
    any `--project`-explicit run) keep the documented `no session bound`
    error, so the feature does not silently widen the unbound allowlist."""
    monkeypatch.delenv(ASTRID_SESSION_ID_ENV, raising=False)

    rc, _stdout, stderr = _run_pipeline(["executors", "list"])
    assert rc == 2
    assert stderr.splitlines()[0].startswith("no session bound")

    # An explicit --project run is left to the dispatched command's own project
    # resolution; the gate does not auto-bind over it.
    rc2, _stdout2, stderr2 = _run_pipeline(
        ["executors", "run", "generation.generate_image", "--project", "demo", "--dry-run"]
    )
    assert "no session bound" in stderr2
