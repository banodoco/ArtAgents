from __future__ import annotations

import json
import logging
import sys
import types
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.gateway import dispatch
from astrid.core.project.current_run import read_current_run
from tests.helpers.current_run import seed_current_run


def test_extract_lifecycle_engine_defaults_to_task() -> None:
    engine, stripped = dispatch._extract_lifecycle_engine(["--project", "demo"])

    assert engine == "task"
    assert stripped == ["--project", "demo"]


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["--engine", "task", "--project", "demo"], ["--project", "demo"]),
        (["--project", "demo", "--engine=task"], ["--project", "demo"]),
    ],
)
def test_extract_lifecycle_engine_strips_task_flags(args: list[str], expected: list[str]) -> None:
    engine, stripped = dispatch._extract_lifecycle_engine(args)

    assert engine == "task"
    assert stripped == expected


def test_extract_lifecycle_engine_rejects_unknown_values() -> None:
    with pytest.raises(AstridError, match="unknown lifecycle engine 'bogus'"):
        dispatch._extract_lifecycle_engine(["--engine", "bogus"])


def test_extract_lifecycle_engine_honors_abort_default_override() -> None:
    engine, stripped = dispatch._extract_lifecycle_engine(
        ["--project", "demo"],
        default_engine="arnold",
    )

    assert engine == "arnold"
    assert stripped == ["--project", "demo"]


@pytest.mark.parametrize(
    "command",
    ["cmd_start", "cmd_next", "cmd_ack"],
)
def test_dispatch_lifecycle_omitted_engine_routes_to_arnold(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    """Omitted --engine now defaults to Arnold for all supported lifecycle verbs."""
    captured: dict[str, object] = {}
    fake_cli = types.ModuleType("astrid.core.integrations.arnold.host.cli")

    def fake_handler(args: list[str]) -> int:
        captured["args"] = list(args)
        return 17

    setattr(fake_cli, command, fake_handler)
    monkeypatch.setitem(sys.modules, "astrid.core.integrations.arnold.host.cli", fake_cli)
    monkeypatch.setattr(f"astrid.core.task.lifecycle.{command}", lambda args: 101)

    rc = dispatch._dispatch_lifecycle(command)(["--project", "demo"])

    assert rc == 17
    assert captured["args"] == ["--project", "demo"]


@pytest.mark.parametrize(
    "args",
    [
        ["--engine", "task", "--project", "demo"],
        ["--project", "demo", "--engine=task"],
    ],
)
def test_dispatch_lifecycle_task_engine_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    args: list[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_next(passed_args: list[str]) -> int:
        captured["args"] = list(passed_args)
        return 19

    monkeypatch.setattr("astrid.core.task.lifecycle.cmd_next", fake_next)

    rc = dispatch._dispatch_lifecycle("cmd_next")(args)

    assert rc == 19
    assert captured["args"] == ["--project", "demo"]


def test_dispatch_lifecycle_arnold_engine_lazy_imports_host_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    fake_cli = types.ModuleType("astrid.core.integrations.arnold.host.cli")

    def fake_ack(args: list[str]) -> int:
        captured["args"] = list(args)
        return 23

    fake_cli.cmd_ack = fake_ack
    monkeypatch.setitem(sys.modules, "astrid.core.integrations.arnold.host.cli", fake_cli)
    monkeypatch.setattr("astrid.core.task.lifecycle.cmd_ack", lambda args: 99)

    rc = dispatch._dispatch_lifecycle("cmd_ack")(["--project", "demo", "--engine=arnold"])

    assert rc == 23
    assert captured["args"] == ["--project", "demo"]


def test_dispatch_lifecycle_start_routes_explicit_arnold_engine_to_host_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake_cli = types.ModuleType("astrid.core.integrations.arnold.host.cli")

    def fake_start(args: list[str]) -> int:
        captured["args"] = list(args)
        return 37

    fake_cli.cmd_start = fake_start
    monkeypatch.setitem(sys.modules, "astrid.core.integrations.arnold.host.cli", fake_cli)
    monkeypatch.setattr("astrid.core.task.lifecycle.cmd_start", lambda args: 101)

    rc = dispatch._dispatch_lifecycle("cmd_start")(
        ["summarize", "--project", "demo", "--engine=arnold"]
    )

    assert rc == 37
    assert captured["args"] == ["summarize", "--project", "demo"]


def _seed_project_with_active_arnold_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    slug: str = "demo",
    run_id: str = "arnold-run-1",
) -> str:
    from astrid.core.foundation import project_paths
    from astrid.core.project import create_project
    from astrid.core.session.identity import Identity, write_identity
    from astrid.core.session.paths import ASTRID_HOME_ENV

    home = tmp_path / "home"
    projects = tmp_path / "projects"
    monkeypatch.setenv(ASTRID_HOME_ENV, str(home))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(projects))
    home.mkdir()
    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project(slug)
    seed_current_run(slug, run_id=run_id, plan_hash="plan-arnold", root=projects)
    run_root = projects / slug / "runs" / run_id
    (run_root / "arnold_run.json").write_text(
        json.dumps(
            {
                "engine": "arnold",
                "workflow_id": "we.refine_image",
                "run_id": run_id,
                "status": "running",
            }
        ),
        encoding="utf-8",
    )
    return run_id


def test_dispatch_abort_without_engine_rejects_and_leaves_arnold_run_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = _seed_project_with_active_arnold_run(monkeypatch, tmp_path)

    rc = dispatch._dispatch_lifecycle("cmd_abort")(["--project", "demo"])
    captured = capsys.readouterr()

    assert rc == 1
    assert read_current_run("demo") == run_id
    assert captured.out == ""
    assert "cannot yet verify cleanup of active Arnold state" in captured.err
    assert "recovery: astrid abort --engine task --project demo" in captured.err


def test_dispatch_abort_explicit_arnold_rejects_and_leaves_arnold_run_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_id = _seed_project_with_active_arnold_run(monkeypatch, tmp_path)

    rc = dispatch._dispatch_lifecycle("cmd_abort")(["--project", "demo", "--engine", "arnold"])
    captured = capsys.readouterr()

    assert rc == 1
    assert read_current_run("demo") == run_id
    assert captured.out == ""
    assert f"active_run: {run_id}" in captured.err
    assert "recovery: astrid abort --engine task --project demo" in captured.err


def test_dispatch_abort_task_engine_still_routes_to_task_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_abort(args: list[str]) -> int:
        captured["args"] = list(args)
        return 41

    monkeypatch.setattr("astrid.core.task.lifecycle.cmd_abort", fake_abort)
    sys.modules.pop("astrid.core.integrations.arnold.host.cli", None)

    rc = dispatch._dispatch_lifecycle("cmd_abort")(
        ["--engine", "task", "--project", "demo"]
    )

    assert rc == 41
    assert captured["args"] == ["--project", "demo"]
    assert "astrid.core.integrations.arnold.host.cli" not in sys.modules


def test_dispatch_skip_rejects_arnold_engine() -> None:
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_lifecycle("cmd_skip")(["--project", "demo", "--engine", "arnold"])


def test_dispatch_status_with_project_arnold_routes_to_host_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    captured: dict[str, object] = {}
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")
    def fake_status(args: list[str]) -> int:
        captured["args"] = list(args)
        return 29

    monkeypatch.setattr(cli, "cmd_status", fake_status)
    monkeypatch.setattr("astrid.core.task.lifecycle.cmd_status", lambda args: 101)

    rc = dispatch._dispatch_status(["--project", "demo", "--engine", "arnold", "--json"])

    assert rc == 29
    assert captured["args"] == ["--project", "demo", "--json"]


def test_dispatch_status_without_project_keeps_session_status_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyParser:
        def parse_args(self, args: list[str]) -> types.SimpleNamespace:
            captured["parse_args"] = list(args)
            return types.SimpleNamespace(command="status", json=True)

    monkeypatch.setattr(dispatch._session_cli, "build_parser", lambda: DummyParser())
    monkeypatch.setattr(dispatch._session_cli, "cmd_status", lambda parsed: 31)
    sys.modules.pop("astrid.core.integrations.arnold.host.cli", None)

    rc = dispatch._dispatch_status(["--engine", "arnold", "--json"])

    assert rc == 31
    assert captured["parse_args"] == ["status", "--json"]
    assert "astrid.core.integrations.arnold.host.cli" not in sys.modules


# ── Arnold cmd_status no-active-run behaviour (T4) ──────────────────────


def test_arnold_cmd_status_no_active_run_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``cmd_status --project X --json`` returns no_active_run JSON when
    no Arnold run is active."""
    import importlib

    from astrid.core.foundation import project_paths
    from astrid.core.project import create_project
    from astrid.core.session.paths import ASTRID_HOME_ENV

    monkeypatch.setenv(ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    from astrid.core.session.identity import Identity, write_identity

    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")

    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")
    rc = cli.cmd_status(["--project", "demo", "--json"])
    stdout = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(stdout)
    assert payload["state"] == "no_active_run"
    assert payload["project"] == "demo"
    assert payload["run_id"] is None
    assert payload["schema_version"] == 1
    assert "has no active Arnold run" in payload["error"]


def test_arnold_cmd_status_no_active_run_prose(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``cmd_status --project X`` (no --json) prints no-active-run prose
    to stderr when no Arnold run is active."""
    import importlib

    from astrid.core.foundation import project_paths
    from astrid.core.project import create_project
    from astrid.core.session.paths import ASTRID_HOME_ENV

    monkeypatch.setenv(ASTRID_HOME_ENV, str(tmp_path / "home"))
    monkeypatch.setenv(project_paths.PROJECTS_ROOT_ENV, str(tmp_path / "projects"))
    (tmp_path / "home").mkdir()
    from astrid.core.session.identity import Identity, write_identity

    write_identity(Identity(agent_id="claude-1", created_at="2026-05-11T00:00:00Z"))
    create_project("demo")

    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")
    rc = cli.cmd_status(["--project", "demo"])
    captured = capsys.readouterr()

    assert rc == 1
    assert "has no active Arnold run" in captured.err
    assert captured.out == ""


# ── T7: FALLBACK_ENGINE_TASK warning logging ────────────────────────────


@pytest.mark.parametrize(
    "command",
    ["cmd_start", "cmd_next", "cmd_ack", "cmd_abort"],
)
def test_fallback_engine_task_warning_emitted_for_explicit_task_engine(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    command: str,
) -> None:
    """Explicit ``--engine task`` on an Arnold-default verb emits
    FALLBACK_ENGINE_TASK warning."""
    monkeypatch.setattr(
        f"astrid.core.task.lifecycle.{command}",
        lambda args: 42,
    )
    sys.modules.pop("astrid.core.integrations.arnold.host.cli", None)

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_lifecycle(command)(
            ["--engine", "task", "--project", "demo", "extra-arg"]
        )

    assert rc == 42
    assert any(
        "FALLBACK_ENGINE_TASK" in r.message and f"verb={command}" in r.message
        for r in caplog.records
    )


def test_fallback_engine_task_warning_absent_for_arnold_default(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` on an Arnold-default verb does NOT emit
    FALLBACK_ENGINE_TASK."""
    import importlib

    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")
    monkeypatch.setattr(cli, "cmd_start", lambda args: 99)

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_lifecycle("cmd_start")(["--project", "demo"])

    assert rc == 99
    assert not any(
        "FALLBACK_ENGINE_TASK" in r.message for r in caplog.records
    )


def test_fallback_engine_task_warning_absent_for_explicit_arnold(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` does NOT emit FALLBACK_ENGINE_TASK."""
    import importlib

    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")
    monkeypatch.setattr(cli, "cmd_next", lambda args: 77)

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_lifecycle("cmd_next")(
            ["--engine", "arnold", "--project", "demo"]
        )

    assert rc == 77
    assert not any(
        "FALLBACK_ENGINE_TASK" in r.message for r in caplog.records
    )


def test_fallback_engine_task_warning_includes_project_and_release(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FALLBACK_ENGINE_TASK log includes project, sanitized argv, and
    release identifier."""
    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_ack",
        lambda args: 13,
    )
    sys.modules.pop("astrid.core.integrations.arnold.host.cli", None)

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_lifecycle("cmd_ack")(
            ["--engine=task", "--project", "myproj", "positional"]
        )

    assert rc == 13
    records = [r for r in caplog.records if "FALLBACK_ENGINE_TASK" in r.message]
    assert len(records) == 1
    msg = records[0].message
    assert "verb=cmd_ack" in msg
    assert "project=myproj" in msg
    assert "argv=" in msg
    assert "positional" in msg
    assert "--engine" not in msg  # engine flag already stripped
    assert "release=release-n" in msg


def test_fallback_engine_task_warning_not_emitted_for_skip_task_default(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``cmd_skip`` defaults to task — explicit ``--engine task`` is NOT a
    fallback and must not emit FALLBACK_ENGINE_TASK."""
    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_skip",
        lambda args: 55,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_lifecycle("cmd_skip")(
            ["--engine", "task", "--project", "demo"]
        )

    assert rc == 55
    assert not any(
        "FALLBACK_ENGINE_TASK" in r.message for r in caplog.records
    )


# ── T8: task-only verb engine handling for runs / run ──────────────────


def test_dispatch_runs_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``runs`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_runs_ls(tail: list[str]) -> int:
        captured["tail"] = list(tail)
        return 71

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_runs_ls",
        fake_runs_ls,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_runs(["ls", "--project", "demo"])

    assert rc == 71
    assert captured["tail"] == ["--project", "demo"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=runs" in r.message
        for r in caplog.records
    )


def test_dispatch_runs_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``runs`` emits TASK_ONLY_VERB_DEPRECATED,
    strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_runs_ls(tail: list[str]) -> int:
        captured["tail"] = list(tail)
        return 73

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_runs_ls",
        fake_runs_ls,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_runs(
            ["--engine", "task", "ls", "--project", "demo"]
        )

    assert rc == 73
    assert captured["tail"] == ["--project", "demo"]  # --engine flag stripped
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=runs" in r.message
        for r in caplog.records
    )


def test_dispatch_runs_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``runs`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_runs(["ls", "--engine", "arnold", "--project", "demo"])


def test_dispatch_run_omitted_engine_emits_both_warnings_and_works(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``run`` emits both deprecation alias and
    TASK_ONLY_VERB_DEPRECATED, then delegates to ``_dispatch_runs``."""
    captured: dict[str, object] = {}

    def fake_runs_ls(tail: list[str]) -> int:
        captured["tail"] = list(tail)
        return 79

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_runs_ls",
        fake_runs_ls,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_run(["ls", "--project", "demo"])

    assert rc == 79
    assert captured["tail"] == ["--project", "demo"]
    stderr = capsys.readouterr().err
    assert "'astrid run' is deprecated" in stderr
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=run" in r.message
        for r in caplog.records
    )


def test_dispatch_run_explicit_arnold_rejects_before_deprecation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Explicit ``--engine arnold`` for ``run`` rejects before emitting
    the deprecation alias warning."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_run(
            ["ls", "--engine", "arnold", "--project", "demo"]
        )
    stderr = capsys.readouterr().err
    assert "'astrid run' is deprecated" not in stderr


def test_dispatch_runs_task_only_deprecated_includes_project_and_release(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TASK_ONLY_VERB_DEPRECATED for ``runs`` includes project and release."""
    def fake_runs_ls(tail: list[str]) -> int:
        return 83

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_runs_ls",
        fake_runs_ls,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_runs(
            ["ls", "--project", "myproj", "positional"]
        )

    assert rc == 83
    records = [
        r for r in caplog.records if "TASK_ONLY_VERB_DEPRECATED" in r.message
    ]
    assert len(records) == 1
    msg = records[0].message
    assert "verb=runs" in msg
    assert "project=myproj" in msg
    assert "argv=" in msg
    assert "positional" in msg
    assert "release=release-n" in msg


def test_dispatch_runs_engine_flag_not_leaked_to_sub_verb_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so the sub-verb argparse never sees it."""
    captured: dict[str, object] = {}

    def fake_runs_ls(tail: list[str]) -> int:
        captured["tail"] = list(tail)
        return 89

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_runs_ls",
        fake_runs_ls,
    )

    rc = dispatch._dispatch_runs(
        ["ls", "--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 89
    assert captured["tail"] == ["--project", "demo", "extra"]


# ── T9: task-only verb engine handling for step / hook / plan ──────────

# ── step retry-fetch ─────────────────────────────────────────────────────

def test_dispatch_step_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``step`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_step_retry_fetch(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 91

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_step_retry_fetch",
        fake_step_retry_fetch,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_step(
            ["retry-fetch", "--project", "demo", "--run-id", "r1"]
        )

    assert rc == 91
    assert captured["args"] == ["--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=step" in r.message
        for r in caplog.records
    )


def test_dispatch_step_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``step`` emits TASK_ONLY_VERB_DEPRECATED,
    strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_step_retry_fetch(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 93

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_step_retry_fetch",
        fake_step_retry_fetch,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_step(
            ["--engine", "task", "retry-fetch", "--project", "demo"]
        )

    assert rc == 93
    assert captured["args"] == ["--project", "demo"]  # --engine flag stripped
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=step" in r.message
        for r in caplog.records
    )


def test_dispatch_step_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``step`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_step(
            ["retry-fetch", "--engine", "arnold", "--project", "demo"]
        )


def test_dispatch_step_engine_flag_not_leaked_to_sub_verb_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so the sub-verb argparse never sees it."""
    captured: dict[str, object] = {}

    def fake_step_retry_fetch(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 95

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_step_retry_fetch",
        fake_step_retry_fetch,
    )

    rc = dispatch._dispatch_step(
        ["retry-fetch", "--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 95
    assert captured["args"] == ["--project", "demo", "extra"]


# ── hook stop ────────────────────────────────────────────────────────────

def test_dispatch_hook_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``hook`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_hook_stop(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 97

    monkeypatch.setattr(
        "astrid.core.task.hook.cmd_hook_stop",
        fake_hook_stop,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_hook(["stop", "--project", "demo"])

    assert rc == 97
    assert captured["args"] == ["--project", "demo"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=hook" in r.message
        for r in caplog.records
    )


def test_dispatch_hook_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``hook`` emits TASK_ONLY_VERB_DEPRECATED,
    strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_hook_stop(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 99

    monkeypatch.setattr(
        "astrid.core.task.hook.cmd_hook_stop",
        fake_hook_stop,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_hook(
            ["--engine", "task", "stop", "--project", "demo"]
        )

    assert rc == 99
    assert captured["args"] == ["--project", "demo"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=hook" in r.message
        for r in caplog.records
    )


def test_dispatch_hook_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``hook`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_hook(
            ["stop", "--engine", "arnold", "--project", "demo"]
        )


def test_dispatch_hook_engine_flag_not_leaked_to_sub_verb_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so the sub-verb argparse never sees it."""
    captured: dict[str, object] = {}

    def fake_hook_stop(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 101

    monkeypatch.setattr(
        "astrid.core.task.hook.cmd_hook_stop",
        fake_hook_stop,
    )

    rc = dispatch._dispatch_hook(
        ["stop", "--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 101
    assert captured["args"] == ["--project", "demo", "extra"]


# ── plan ─────────────────────────────────────────────────────────────────

def test_dispatch_plan_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``plan`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_cmd_plan(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 103

    monkeypatch.setattr(
        "astrid.core.task.plan.verbs.cmd_plan",
        fake_cmd_plan,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_plan_verbs(
            ["add-step", "--project", "demo", "--run-id", "r1"]
        )

    assert rc == 103
    assert captured["args"] == ["add-step", "--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=plan" in r.message
        for r in caplog.records
    )


def test_dispatch_plan_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``plan`` emits TASK_ONLY_VERB_DEPRECATED,
    strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_cmd_plan(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 105

    monkeypatch.setattr(
        "astrid.core.task.plan.verbs.cmd_plan",
        fake_cmd_plan,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_plan_verbs(
            ["--engine", "task", "add-step", "--project", "demo"]
        )

    assert rc == 105
    assert captured["args"] == ["add-step", "--project", "demo"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=plan" in r.message
        for r in caplog.records
    )


def test_dispatch_plan_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``plan`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_plan_verbs(
            ["add-step", "--engine", "arnold", "--project", "demo"]
        )


def test_dispatch_plan_engine_flag_not_leaked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so cmd_plan never sees it."""
    captured: dict[str, object] = {}

    def fake_cmd_plan(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 107

    monkeypatch.setattr(
        "astrid.core.task.plan.verbs.cmd_plan",
        fake_cmd_plan,
    )

    rc = dispatch._dispatch_plan_verbs(
        ["add-step", "--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 107
    assert captured["args"] == ["add-step", "--project", "demo", "extra"]


def test_dispatch_step_task_only_deprecated_includes_project_and_release(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TASK_ONLY_VERB_DEPRECATED for ``step`` includes project and release."""
    def fake_step_retry_fetch(argv: list[str]) -> int:
        return 109

    monkeypatch.setattr(
        "astrid.core.task.lifecycle.cmd_step_retry_fetch",
        fake_step_retry_fetch,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_step(
            ["retry-fetch", "--project", "myproj", "positional"]
        )

    assert rc == 109
    records = [
        r for r in caplog.records if "TASK_ONLY_VERB_DEPRECATED" in r.message
    ]
    assert len(records) == 1
    msg = records[0].message
    assert "verb=step" in msg
    assert "project=myproj" in msg
    assert "argv=" in msg
    assert "positional" in msg
    assert "release=release-n" in msg


def test_dispatch_hook_task_only_deprecated_includes_project_and_release(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TASK_ONLY_VERB_DEPRECATED for ``hook`` includes project and release."""
    def fake_hook_stop(argv: list[str]) -> int:
        return 111

    monkeypatch.setattr(
        "astrid.core.task.hook.cmd_hook_stop",
        fake_hook_stop,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_hook(
            ["stop", "--project", "myproj", "positional"]
        )

    assert rc == 111
    records = [
        r for r in caplog.records if "TASK_ONLY_VERB_DEPRECATED" in r.message
    ]
    assert len(records) == 1
    msg = records[0].message
    assert "verb=hook" in msg
    assert "project=myproj" in msg
    assert "argv=" in msg
    assert "positional" in msg
    assert "release=release-n" in msg


def test_dispatch_plan_task_only_deprecated_includes_project_and_release(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """TASK_ONLY_VERB_DEPRECATED for ``plan`` includes project and release."""
    def fake_cmd_plan(argv: list[str]) -> int:
        return 113

    monkeypatch.setattr(
        "astrid.core.task.plan.verbs.cmd_plan",
        fake_cmd_plan,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_plan_verbs(
            ["add-step", "--project", "myproj", "positional"]
        )

    assert rc == 113
    records = [
        r for r in caplog.records if "TASK_ONLY_VERB_DEPRECATED" in r.message
    ]
    assert len(records) == 1
    msg = records[0].message
    assert "verb=plan" in msg
    assert "project=myproj" in msg
    assert "argv=" in msg
    assert "positional" in msg
    assert "release=release-n" in msg


# ── T10: task-only verb engine handling for events / claim / unclaim ────

# ── events tail ───────────────────────────────────────────────────────────

def test_dispatch_events_tail_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``events tail`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_events_tail(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 115

    monkeypatch.setattr(
        "astrid.core.task.run.audit.cmd_events_tail",
        fake_events_tail,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_events(
            ["tail", "--project", "demo", "--run-id", "r1"]
        )

    assert rc == 115
    assert captured["args"] == ["--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=events" in r.message
        for r in caplog.records
    )


def test_dispatch_events_tail_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``events tail`` emits
    TASK_ONLY_VERB_DEPRECATED, strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_events_tail(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 117

    monkeypatch.setattr(
        "astrid.core.task.run.audit.cmd_events_tail",
        fake_events_tail,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_events(
            ["--engine", "task", "tail", "--project", "demo"]
        )

    assert rc == 117
    assert captured["args"] == ["--project", "demo"]  # --engine flag stripped
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=events" in r.message
        for r in caplog.records
    )


def test_dispatch_events_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``events`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_events(
            ["tail", "--engine", "arnold", "--project", "demo"]
        )


def test_dispatch_events_engine_flag_not_leaked_to_sub_verb_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so the sub-verb argparse never sees it."""
    captured: dict[str, object] = {}

    def fake_events_tail(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 119

    monkeypatch.setattr(
        "astrid.core.task.run.audit.cmd_events_tail",
        fake_events_tail,
    )

    rc = dispatch._dispatch_events(
        ["tail", "--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 119
    assert captured["args"] == ["--project", "demo", "extra"]


# ── claim ─────────────────────────────────────────────────────────────────

def test_dispatch_claim_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``claim`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_cmd_claim(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 121

    monkeypatch.setattr(
        "astrid.core.task.claim.cmd_claim",
        fake_cmd_claim,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_claim(
            ["--project", "demo", "--run-id", "r1"]
        )

    assert rc == 121
    assert captured["args"] == ["--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=claim" in r.message
        for r in caplog.records
    )


def test_dispatch_claim_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``claim`` emits
    TASK_ONLY_VERB_DEPRECATED, strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_cmd_claim(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 123

    monkeypatch.setattr(
        "astrid.core.task.claim.cmd_claim",
        fake_cmd_claim,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_claim(
            ["--engine", "task", "--project", "demo", "--run-id", "r1"]
        )

    assert rc == 123
    assert captured["args"] == ["--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=claim" in r.message
        for r in caplog.records
    )


def test_dispatch_claim_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``claim`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_claim(
            ["--engine", "arnold", "--project", "demo"]
        )


def test_dispatch_claim_engine_flag_not_leaked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so cmd_claim never sees it."""
    captured: dict[str, object] = {}

    def fake_cmd_claim(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 125

    monkeypatch.setattr(
        "astrid.core.task.claim.cmd_claim",
        fake_cmd_claim,
    )

    rc = dispatch._dispatch_claim(
        ["--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 125
    assert captured["args"] == ["--project", "demo", "extra"]


# ── unclaim ───────────────────────────────────────────────────────────────

def test_dispatch_unclaim_omitted_engine_emits_deprecated_and_works(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitted ``--engine`` for ``unclaim`` emits TASK_ONLY_VERB_DEPRECATED
    and delegates to task."""
    captured: dict[str, object] = {}

    def fake_cmd_unclaim(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 127

    monkeypatch.setattr(
        "astrid.core.task.claim.cmd_unclaim",
        fake_cmd_unclaim,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_unclaim(
            ["--project", "demo", "--run-id", "r1"]
        )

    assert rc == 127
    assert captured["args"] == ["--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=unclaim" in r.message
        for r in caplog.records
    )


def test_dispatch_unclaim_explicit_task_emits_deprecated_and_strips_flags(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine task`` for ``unclaim`` emits
    TASK_ONLY_VERB_DEPRECATED, strips the engine flag, and delegates to task."""
    captured: dict[str, object] = {}

    def fake_cmd_unclaim(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 129

    monkeypatch.setattr(
        "astrid.core.task.claim.cmd_unclaim",
        fake_cmd_unclaim,
    )

    with caplog.at_level(logging.WARNING, logger="astrid.core.gateway.dispatch"):
        rc = dispatch._dispatch_unclaim(
            ["--engine", "task", "--project", "demo", "--run-id", "r1"]
        )

    assert rc == 129
    assert captured["args"] == ["--project", "demo", "--run-id", "r1"]
    assert any(
        "TASK_ONLY_VERB_DEPRECATED" in r.message and "verb=unclaim" in r.message
        for r in caplog.records
    )


def test_dispatch_unclaim_explicit_arnold_rejects(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Explicit ``--engine arnold`` for ``unclaim`` raises AstridError."""
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_unclaim(
            ["--engine", "arnold", "--project", "demo"]
        )


def test_dispatch_unclaim_engine_flag_not_leaked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--engine task`` is stripped so cmd_unclaim never sees it."""
    captured: dict[str, object] = {}

    def fake_cmd_unclaim(argv: list[str]) -> int:
        captured["args"] = list(argv)
        return 131

    monkeypatch.setattr(
        "astrid.core.task.claim.cmd_unclaim",
        fake_cmd_unclaim,
    )

    rc = dispatch._dispatch_unclaim(
        ["--project", "demo", "--engine=task", "extra"]
    )

    assert rc == 131
    assert captured["args"] == ["--project", "demo", "extra"]