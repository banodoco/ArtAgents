from __future__ import annotations

import sys
import types

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.gateway import dispatch


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


def test_dispatch_lifecycle_omitted_engine_preserves_task_route(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_start(args: list[str]) -> int:
        captured["args"] = list(args)
        return 17

    monkeypatch.setattr("astrid.core.task.lifecycle.cmd_start", fake_start)
    sys.modules.pop("astrid.core.integrations.arnold.host.cli", None)

    rc = dispatch._dispatch_lifecycle("cmd_start")(["--project", "demo"])

    assert rc == 17
    assert captured["args"] == ["--project", "demo"]
    assert "astrid.core.integrations.arnold.host.cli" not in sys.modules


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


def test_dispatch_skip_rejects_arnold_engine() -> None:
    with pytest.raises(AstridError, match="does not support '--engine arnold'"):
        dispatch._dispatch_lifecycle("cmd_skip")(["--project", "demo", "--engine", "arnold"])


def test_dispatch_status_with_project_arnold_routes_to_host_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake_cli = types.ModuleType("astrid.core.integrations.arnold.host.cli")

    def fake_status(args: list[str]) -> int:
        captured["args"] = list(args)
        return 29

    fake_cli.cmd_status = fake_status
    monkeypatch.setitem(sys.modules, "astrid.core.integrations.arnold.host.cli", fake_cli)
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
