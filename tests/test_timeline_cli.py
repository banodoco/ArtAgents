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

from astrid.core.timeline import cli as timeline_cli, clip_edits
from astrid.core.timeline.events.schema import ClipAddedPayload, TimelineActor


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


def test_main_parses_set_default_and_dispatches_to_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_set_default(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_set_default", fake_set_default)

    rc = timeline_cli.main(["set-default", "primary"])
    assert rc == 0
    assert seen["args"].command == "set-default"
    assert seen["args"].slug == "primary"


# ---------------------------------------------------------------------------
# clip verb parsing tests
# ---------------------------------------------------------------------------


def test_clip_subcommands_appear_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "clip" in captured.out


def test_clip_add_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_add(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_add", fake_add)

    rc = timeline_cli.main(
        ["clip", "add", "my-slug", "--kind", "visual", "--asset", "img_001", "--at", "0"]
    )
    assert rc == 0
    args = seen["args"]
    assert args.slug == "my-slug"
    assert args.kind == "visual"
    assert args.asset == "img_001"
    assert args.at_index == 0


def test_clip_add_parses_after_position(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_add(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_add", fake_add)

    rc = timeline_cli.main(
        ["clip", "add", "my-slug", "--kind", "audio", "--asset", "snd_001", "--after", "clip-1"]
    )
    assert rc == 0
    assert seen["args"].after_id == "clip-1"
    assert seen["args"].at_index is None


def test_clip_add_parses_before_position(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_add(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_add", fake_add)

    rc = timeline_cli.main(
        ["clip", "add", "my-slug", "--kind", "text", "--asset", "txt_001", "--before", "clip-2"]
    )
    assert rc == 0
    assert seen["args"].before_id == "clip-2"


def test_clip_add_mutually_exclusive_position_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """--at, --after, --before are in a mutually exclusive group."""
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(
            ["clip", "add", "my-slug", "--kind", "visual", "--asset", "x", "--at", "0", "--after", "y"]
        )
    assert excinfo.value.code != 0


def test_clip_remove_parses_clip_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_remove(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_remove", fake_remove)

    rc = timeline_cli.main(["clip", "remove", "my-slug", "--clip-id", "c1"])
    assert rc == 0
    assert seen["args"].slug == "my-slug"
    assert seen["args"].clip_id == "c1"


def test_clip_move_parses_to_syntax(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_move(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_move", fake_move)

    rc = timeline_cli.main(
        ["clip", "move", "my-slug", "--clip-id", "c1", "--to", "after:c2"]
    )
    assert rc == 0
    assert seen["args"].clip_id == "c1"
    assert seen["args"].to_position == "after:c2"


def test_clip_retime_parses_start_and_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_retime(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_retime", fake_retime)

    rc = timeline_cli.main(
        ["clip", "retime", "my-slug", "--clip-id", "c1", "--start", "3.5", "--duration", "10.0"]
    )
    assert rc == 0
    assert seen["args"].clip_id == "c1"
    assert seen["args"].start == 3.5
    assert seen["args"].duration == 10.0


def test_clip_swap_parses_a_and_b(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_swap(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_swap", fake_swap)

    rc = timeline_cli.main(
        ["clip", "swap", "my-slug", "--a", "clip_a", "--b", "clip_b"]
    )
    assert rc == 0
    assert seen["args"].clip_a == "clip_a"
    assert seen["args"].clip_b == "clip_b"


def test_clip_replace_parses_with_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_replace(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_replace", fake_replace)

    rc = timeline_cli.main(
        ["clip", "replace", "my-slug", "--clip-id", "c1", "--with", "new_asset"]
    )
    assert rc == 0
    assert seen["args"].clip_id == "c1"
    assert seen["args"].with_asset_id == "new_asset"


def test_clip_set_text_parses_text_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_set_text(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_set_text", fake_set_text)

    rc = timeline_cli.main(
        ["clip", "set-text", "my-slug", "--clip-id", "c1", "--text", "Hello"]
    )
    assert rc == 0
    assert seen["args"].clip_id == "c1"
    assert seen["args"].text == "Hello"


def test_clip_annotate_parses_note_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_annotate(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_annotate", fake_annotate)

    rc = timeline_cli.main(
        ["clip", "annotate", "my-slug", "--clip-id", "c1", "--note", "A note"]
    )
    assert rc == 0
    assert seen["args"].clip_id == "c1"
    assert seen["args"].note == "A note"


def test_clip_add_missing_required_flags_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["clip", "add", "my-slug"])
    assert excinfo.value.code != 0


def test_clip_remove_missing_required_flags_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["clip", "remove", "my-slug"])
    assert excinfo.value.code != 0


def test_clip_handler_calls_clip_edits_not_direct_file_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify clip handlers call clip_edits functions (no direct file mutations)."""
    seen: dict = {}

    def fake_add(project_slug, slug, *, kind, asset_id, position=None, actor=None,
                 expected_version=None, txn_id=None, root=None):
        seen["called"] = "add_clip"
        seen["kind"] = kind
        seen["asset_id"] = asset_id
        from astrid.core.timeline.events.schema import TimelineEvent
        return TimelineEvent.new(
            timeline_id="00000000-0000-0000-0000-000000000000",
            ts="2026-05-20T12:00:00Z",
            actor=actor or TimelineActor(type="system", id="test"),
            kind="clip.added",
            payload=ClipAddedPayload(clip_id=asset_id, kind=kind, asset_id=asset_id),
        )

    session = SimpleNamespace(project="demo", agent_id="test", id="s1")

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: session)
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.clip_edits, "add_clip", fake_add)

    rc = timeline_cli.cmd_clip_add(
        argparse.Namespace(
            slug="primary",
            kind="visual",
            asset="img_001",
            at_index=None,
            after_id=None,
            before_id=None,
        )
    )
    assert rc == 0
    assert seen.get("called") == "add_clip"
    assert seen.get("kind") == "visual"
    assert seen.get("asset_id") == "img_001"


def test_clip_edit_error_returns_exit_code_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_add(args: argparse.Namespace) -> int:
        raise clip_edits.ClipEditError("test error")

    monkeypatch.setattr(timeline_cli, "cmd_clip_add", fake_add)

    rc = timeline_cli.main(
        ["clip", "add", "my-slug", "--kind", "visual", "--asset", "x"]
    )
    assert rc == 2
    captured = capsys.readouterr()
    assert "timelines: test error" in captured.err


def test_clip_subcommand_help_shows_all_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["clip", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    for verb in ("add", "remove", "move", "retime", "swap", "replace", "set-text", "annotate"):
        assert verb in captured.out
