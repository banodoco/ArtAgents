"""Direct argparse tests for ``astrid.core.timeline.cli``.

These tests invoke ``timeline_cli.main(argv=[...])`` directly (no subprocess)
so the assertions point at argparse configuration, not unrelated I/O.

The downstream handlers are monkeypatched at the boundary so we exercise
only the parser glue — happy-path business logic for timeline CRUD is
covered separately by ``tests/timeline/test_crud.py``.
"""

from __future__ import annotations

import argparse
from types import SimpleNamespace

import pytest

from astrid.core.timeline import cli as timeline_cli
from astrid.core.timeline.events.schema import TimelineActor


# ---------------------------------------------------------------------------
# Help and discovery
# ---------------------------------------------------------------------------


def test_help_exits_zero_and_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    # Prog string from build_parser().
    assert "python3 -m astrid timelines" in captured.out
    # Subcommands should be advertised.
    for sub in ("ls", "create", "show", "rename", "finalize", "tombstone", "purge", "set-default", "export", "cost"):
        assert sub in captured.out


def test_subcommand_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["create", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Timeline slug" in captured.out
    assert "--default" in captured.out


# ---------------------------------------------------------------------------
# Invalid input branches
# ---------------------------------------------------------------------------


def test_no_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main([])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    # argparse prints to stderr for parse errors.
    assert "required" in captured.err.lower() or "command" in captured.err.lower()


def test_unknown_subcommand_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["wat"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "invalid choice" in captured.err.lower() or "wat" in captured.err


def test_create_missing_slug_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["create"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "slug" in captured.err.lower()
    assert "required" in captured.err.lower()


def test_finalize_missing_required_output_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["finalize", "my-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    # --output is required for finalize.
    assert "--output" in captured.err
    assert "required" in captured.err.lower()


def test_export_missing_required_out_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["export", "my-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--out" in captured.err
    assert "required" in captured.err.lower()


def test_rename_missing_new_slug_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["rename", "old-only"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "required" in captured.err.lower()


# ---------------------------------------------------------------------------
# Valid invocations — mock the handler at the boundary so we test parsing,
# not business logic.
# ---------------------------------------------------------------------------


def test_ls_with_project_flag_dispatches_to_cmd_ls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_ls(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_ls", fake_ls)

    rc = timeline_cli.main(["ls", "--project", "my-proj"])
    assert rc == 0
    assert "args" in seen
    assert seen["args"].project == "my-proj"
    assert seen["args"].command == "ls"


def test_create_dispatches_to_legacy_crud_without_eventlog_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    session = SimpleNamespace(project="demo")

    def fake_require_session(slug: str | None = None) -> object:
        return session

    def fake_create(
        project: str,
        slug: str,
        *,
        name: str | None = None,
        is_default: bool = False,
        root: object = None,
    ) -> dict[str, str]:
        seen["project"] = project
        seen["slug"] = slug
        seen["name"] = name
        seen["is_default"] = is_default
        seen["root"] = root
        return {"slug": slug, "ulid": "01J00000000000000000000000"}

    monkeypatch.setattr(timeline_cli, "_require_session", fake_require_session)
    monkeypatch.setattr(timeline_cli.crud, "create_timeline", fake_create)

    rc = timeline_cli.cmd_create(
        argparse.Namespace(slug="fresh", name="Fresh Timeline", is_default=True)
    )
    assert rc == 0
    assert seen == {
        "project": "demo",
        "slug": "fresh",
        "name": "Fresh Timeline",
        "is_default": True,
        "root": None,
    }


def test_show_parses_json_and_verify_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_show(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_show", fake_show)

    rc = timeline_cli.main(["show", "my-slug", "--verify", "--json"])
    assert rc == 0
    assert seen["args"].slug == "my-slug"
    assert seen["args"].verify is True
    assert seen["args"].json_out is True


def test_finalize_parses_all_optional_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_finalize(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_finalize", fake_finalize)

    rc = timeline_cli.main(
        [
            "finalize",
            "my-slug",
            "--output",
            "/tmp/out.mp4",
            "--kind",
            "mp4",
            "--from-run",
            "run-123",
            "--recorded-by",
            "agent:tester",
        ]
    )
    assert rc == 0
    args = seen["args"]
    assert args.slug == "my-slug"
    assert args.output == "/tmp/out.mp4"
    assert args.kind == "mp4"
    assert args.from_run == "run-123"
    assert args.recorded_by == "agent:tester"


def test_purge_yes_really_flag_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_purge(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_purge", fake_purge)

    rc = timeline_cli.main(["purge", "doomed", "--yes-really"])
    assert rc == 0
    assert seen["args"].slug == "doomed"
    assert seen["args"].yes_really is True


# ---------------------------------------------------------------------------
# main() error envelope: domain exceptions become exit code 2 + stderr.
# ---------------------------------------------------------------------------


def test_main_wraps_crud_error_as_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from astrid.core.timeline import crud as crud_module

    def raising_ls(args: argparse.Namespace) -> int:
        raise crud_module.TimelineCrudError("boom")

    monkeypatch.setattr(timeline_cli, "cmd_ls", raising_ls)

    rc = timeline_cli.main(["ls", "--project", "p"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "timelines: boom" in captured.err


def test_main_wraps_value_error_as_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raising_ls(args: argparse.Namespace) -> int:
        raise ValueError("bad value")

    monkeypatch.setattr(timeline_cli, "cmd_ls", raising_ls)

    rc = timeline_cli.main(["ls", "--project", "p"])
    assert rc == 2
    captured = capsys.readouterr()
    assert "timelines: bad value" in captured.err


def test_cmd_rename_passes_explicit_actor_from_session(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    session = SimpleNamespace(project="demo", agent_id="claude-code", id="session-123")

    def fake_require_session(slug: str | None = None) -> object:
        return session

    def fake_rename(project: str, old_slug: str, new_slug: str, *, actor: TimelineActor, root: object = None) -> dict[str, str]:
        seen["project"] = project
        seen["old_slug"] = old_slug
        seen["new_slug"] = new_slug
        seen["actor"] = actor
        return {"slug": new_slug}

    monkeypatch.setattr(timeline_cli, "_require_session", fake_require_session)
    monkeypatch.setattr(timeline_cli.crud, "rename_timeline", fake_rename)

    rc = timeline_cli.cmd_rename(argparse.Namespace(old_slug="before", new_slug="after"))
    assert rc == 0
    actor = seen["actor"]
    assert isinstance(actor, TimelineActor)
    assert actor.type == "agent"
    assert actor.id == "claude-code:session-123"
    assert actor.display == "claude-code"


def test_set_default_dispatches_to_legacy_crud_without_eventlog_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    session = SimpleNamespace(project="demo")

    def fake_require_session(slug: str | None = None) -> object:
        return session

    def fake_set_default(
        project: str,
        slug: str,
        *,
        root: object = None,
    ) -> dict[str, str]:
        seen["project"] = project
        seen["slug"] = slug
        seen["root"] = root
        return {"slug": slug}

    monkeypatch.setattr(timeline_cli, "_require_session", fake_require_session)
    monkeypatch.setattr(timeline_cli.crud, "set_default", fake_set_default)

    rc = timeline_cli.cmd_set_default(argparse.Namespace(slug="primary"))
    assert rc == 0
    assert seen == {"project": "demo", "slug": "primary", "root": None}
