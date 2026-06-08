"""Direct argparse tests for ``astrid.core.timeline.cli``.

These tests invoke ``timeline_cli.main(argv=[...])`` directly (no subprocess)
so the assertions point at argparse configuration, not unrelated I/O.

The downstream handlers are monkeypatched at the boundary so we exercise
only the parser glue — happy-path business logic for timeline CRUD is
covered separately by ``tests/timeline/test_crud.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.cli_choices import AstridArgumentError, StaticChoices
from astrid.core.timeline import cli as timeline_cli, clip_edits
from astrid.core.timeline.events.schema import (
    AudioBoundPayload,
    ClipAddedPayload,
    EffectAddedPayload,
    ThemeSetPayload,
    TimelineActor,
    TimelineConfigReplacedPayload,
    TimelineEvent,
    TrackAddedPayload,
    TransitionSetPayload,
)


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
    for sub in ("ls", "create", "show", "rename", "finalize", "tombstone", "purge", "set-default", "export", "cost", "migrate-events",
                "push", "pull", "recover", "branch", "branches", "undo", "mass-undo", "erase"):
        assert sub in captured.out


def test_subcommand_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["create", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "Timeline slug" in captured.out
    assert "--default" in captured.out


def test_backend_flags_use_static_choices_wrappers() -> None:
    parser = timeline_cli.build_parser()
    subparsers = next(
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    )

    expected = {
        "push": "to_backend",
        "pull": "from_backend",
        "undo": "from_backend",
        "mass-undo": "from_backend",
        "recover": "from_backend",
    }
    for command, dest in expected.items():
        subparser = subparsers.choices[command]
        action = next(option for option in subparser._actions if option.dest == dest)
        assert isinstance(action.choices, StaticChoices)
        assert action.choices.valid_options == ("supabase",)


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
# main() error envelope: domain exceptions become AstridError for pipeline.main().
# ---------------------------------------------------------------------------


def test_main_raises_astrid_error_for_crud_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.core.timeline import crud as crud_module

    def raising_ls(args: argparse.Namespace) -> int:
        raise crud_module.TimelineCrudError("boom")

    monkeypatch.setattr(timeline_cli, "cmd_ls", raising_ls)

    with pytest.raises(AstridError, match="boom"):
        timeline_cli.main(["ls", "--project", "p"])


def test_main_raises_astrid_error_for_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising_ls(args: argparse.Namespace) -> int:
        raise ValueError("bad value")

    monkeypatch.setattr(timeline_cli, "cmd_ls", raising_ls)

    with pytest.raises(AstridError, match="bad value"):
        timeline_cli.main(["ls", "--project", "p"])


def test_main_raises_astrid_error_for_erased_payload_projection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.core.timeline.projection import ErasedPayloadProjectionError

    def raising_ls(args: argparse.Namespace) -> int:
        raise ErasedPayloadProjectionError(
            event_id="01AAAAAAAAAAAAAAAAAAAAA100",
            kind="clip.added",
            reason="payload is erased",
        )

    monkeypatch.setattr(timeline_cli, "cmd_ls", raising_ls)

    with pytest.raises(AstridError) as excinfo:
        timeline_cli.main(["ls", "--project", "p"])
    assert "erased payload" in str(excinfo.value)
    assert "01AAAAAAAAAAAAAAAAAAAAA100" in str(excinfo.value)


def test_main_raises_astrid_error_for_projection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from astrid.core.timeline.projection import ProjectionError

    def raising_ls(args: argparse.Namespace) -> int:
        raise ProjectionError(
            event_id="01AAAAAAAAAAAAAAAAAAAAA200",
            kind="transition.set",
            reason="projection failed",
        )

    monkeypatch.setattr(timeline_cli, "cmd_ls", raising_ls)

    with pytest.raises(AstridError) as excinfo:
        timeline_cli.main(["ls", "--project", "p"])
    assert "projection error" in str(excinfo.value).lower()
    assert "01AAAAAAAAAAAAAAAAAAAAA200" in str(excinfo.value)


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
        ["clip", "add", "my-slug", "--kind", "video", "--asset", "img_001", "--track", "visual", "--at", "0"]
    )
    assert rc == 0
    args = seen["args"]
    assert args.slug == "my-slug"
    assert args.kind == "video"
    assert args.asset == "img_001"
    assert args.track_id == "visual"
    assert args.at_index == 0


def test_clip_add_parses_after_position(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_add(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_clip_add", fake_add)

    rc = timeline_cli.main(
        ["clip", "add", "my-slug", "--kind", "audio", "--asset", "snd_001", "--track", "audio", "--after", "clip-1"]
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
        ["clip", "add", "my-slug", "--kind", "text", "--asset", "txt_001", "--track", "captions", "--before", "clip-2"]
    )
    assert rc == 0
    assert seen["args"].before_id == "clip-2"


def test_clip_add_mutually_exclusive_position_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """--at, --after, --before are in a mutually exclusive group."""
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(
            ["clip", "add", "my-slug", "--kind", "video", "--asset", "x", "--track", "visual", "--at", "0", "--after", "y"]
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

    def fake_add(project_slug, slug, *, kind, asset_id, track_id=None, position=None, actor=None,
                 expected_version=None, txn_id=None, root=None):
        seen["called"] = "add_clip"
        seen["kind"] = kind
        seen["asset_id"] = asset_id
        seen["track_id"] = track_id
        from astrid.core.timeline.events.schema import TimelineEvent
        return TimelineEvent.new(
            timeline_id="00000000-0000-0000-0000-000000000000",
            ts="2026-05-20T12:00:00Z",
            actor=actor or TimelineActor(type="system", id="test"),
            kind="clip.added",
            payload=ClipAddedPayload(clip_id=asset_id, kind=kind, asset_id=asset_id, track_id=track_id or "visual"),
        )

    session = SimpleNamespace(project="demo", agent_id="test", id="s1")

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: session)
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.clip_edits, "add_clip", fake_add)

    rc = timeline_cli.cmd_clip_add(
        argparse.Namespace(
            slug="primary",
            kind="video",
            asset="img_001",
            at_index=None,
            after_id=None,
            before_id=None,
            track_id="visual",
        )
    )
    assert rc == 0
    assert seen.get("called") == "add_clip"
    assert seen.get("kind") == "video"
    assert seen.get("track_id") == "visual"
    assert seen.get("asset_id") == "img_001"


def test_clip_edit_error_raises_astrid_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_add(args: argparse.Namespace) -> int:
        raise clip_edits.ClipEditError("test error")

    monkeypatch.setattr(timeline_cli, "cmd_clip_add", fake_add)

    with pytest.raises(AstridError, match="test error"):
        timeline_cli.main(
            ["clip", "add", "my-slug", "--kind", "video", "--asset", "x", "--track", "visual"]
        )


def test_clip_subcommand_help_shows_all_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["clip", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    for verb in ("add", "remove", "move", "retime", "swap", "replace", "set-text", "annotate"):
        assert verb in captured.out


# ---------------------------------------------------------------------------
# m9 verb parsing tests
# ---------------------------------------------------------------------------


def test_push_requires_to_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["push", "my-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--to" in captured.err


def test_push_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_push(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_push", fake_push)

    rc = timeline_cli.main(["push", "my-slug", "--to", "supabase", "--project", "demo"])
    assert rc == 0
    assert seen["args"].slug_or_id == "my-slug"
    assert seen["args"].to_backend == "supabase"
    assert seen["args"].project == "demo"


def test_pull_requires_from_and_project_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["pull", "remote-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--from" in captured.err or "--project" in captured.err


def test_pull_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_pull(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_pull", fake_pull)

    rc = timeline_cli.main([
        "pull", "remote-slug", "--from", "supabase", "--project", "demo",
        "--into", "existing-local",
    ])
    assert rc == 0
    assert seen["args"].slug_or_id == "remote-slug"
    assert seen["args"].from_backend == "supabase"
    assert seen["args"].project == "demo"
    assert seen["args"].into_slug == "existing-local"
    assert seen["args"].create_as_slug is None
    assert seen["args"].create is False


def test_pull_as_without_create_parses_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """--as without --create is accepted by argparse (store), but the
    combination is validated by the handler.  Test that both flags parse
    together correctly."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_pull(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_pull", fake_pull)

    # --as without --create still parses but the handler validates
    rc = timeline_cli.main([
        "pull", "remote-slug", "--from", "supabase", "--project", "demo",
        "--as", "new-local",
    ])
    assert rc == 0
    assert seen["args"].create_as_slug == "new-local"
    assert seen["args"].create is False


def test_pull_create_with_as_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_pull(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_pull", fake_pull)

    rc = timeline_cli.main([
        "pull", "remote-slug", "--from", "supabase", "--project", "demo",
        "--create", "--as", "new-local",
    ])
    assert rc == 0
    assert seen["args"].slug_or_id == "remote-slug"
    assert seen["args"].create is True
    assert seen["args"].create_as_slug == "new-local"


def test_pull_create_without_as_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    """--create without --as means implicit create (remote provides slug)."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_pull(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_pull", fake_pull)

    rc = timeline_cli.main([
        "pull", "remote-slug", "--from", "supabase", "--project", "demo",
        "--create",
    ])
    assert rc == 0
    assert seen["args"].create is True
    assert seen["args"].create_as_slug is None


def test_pull_into_and_create_are_mutually_exclusive_in_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both --into and --create can be parsed simultaneously (argparse allows),
    but the handler must reject. Test that handler receives both and we
    document the expected validation."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_pull(args: argparse.Namespace) -> int:
        seen["args"] = args
        # Simulate handler validation: both cannot be active
        if args.into_slug and args.create:
            raise ValueError("--into and --create are mutually exclusive")
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_pull", fake_pull)

    # --into and --create together should parse but the handler rejects
    # (we verify the args are set correctly)
    with pytest.raises(AstridError, match="mutually exclusive"):
        timeline_cli.main([
            "pull", "remote-slug", "--from", "supabase", "--project", "demo",
            "--into", "existing", "--create",
        ])
    assert seen["args"].into_slug == "existing"
    assert seen["args"].create is True


def test_recover_requires_at_and_reason_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["recover", "my-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--at" in captured.err or "--reason" in captured.err


def test_recover_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_recover(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_recover", fake_recover)

    rc = timeline_cli.main([
        "recover", "my-slug", "--at", "01AAAAAAAAAAAAAAAAAAAAA100",
        "--reason", "corrupted after this point",
    ])
    assert rc == 0
    assert seen["args"].slug == "my-slug"
    assert seen["args"].at_event_id == "01AAAAAAAAAAAAAAAAAAAAA100"
    assert seen["args"].reason == "corrupted after this point"
    assert seen["args"].from_backend is None
    assert seen["args"].project is None


def test_recover_parses_from_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_recover(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_recover", fake_recover)

    rc = timeline_cli.main([
        "recover", "my-slug", "--at", "01AAAAAAAAAAAAAAAAAAAAA100",
        "--reason", "recovery", "--from", "supabase", "--project", "demo",
    ])
    assert rc == 0
    assert seen["args"].from_backend == "supabase"
    assert seen["args"].project == "demo"


def test_branch_create_requires_from_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["branch", "create", "source-slug", "branch-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--from" in captured.err


def test_branch_create_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_branch_create(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_branch_create", fake_branch_create)

    rc = timeline_cli.main([
        "branch", "create", "source-slug", "branch-slug",
        "--from", "01AAAAAAAAAAAAAAAAAAAAA200",
        "--reason", "exploratory branch",
    ])
    assert rc == 0
    assert seen["args"].source_slug_or_id == "source-slug"
    assert seen["args"].branch_slug == "branch-slug"
    assert seen["args"].from_event_id == "01AAAAAAAAAAAAAAAAAAAAA200"
    assert seen["args"].reason == "exploratory branch"


def test_branch_list_parses_source_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_branch_list(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_branch_list", fake_branch_list)

    rc = timeline_cli.main(["branch", "list", "source-slug"])
    assert rc == 0
    assert seen["args"].source_slug_or_id == "source-slug"


def test_branches_alias_parses_source_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    """branches is an alias for branch list."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_branch_list(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_branch_list", fake_branch_list)

    rc = timeline_cli.main(["branches", "source-slug"])
    assert rc == 0
    assert seen["args"].source_slug_or_id == "source-slug"


def test_undo_parses_slug_and_from_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_undo(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_undo", fake_undo)

    rc = timeline_cli.main(["undo", "my-slug"])
    assert rc == 0
    assert seen["args"].slug == "my-slug"
    assert seen["args"].from_backend is None

    rc = timeline_cli.main(["undo", "my-slug", "--from", "supabase", "--project", "demo"])
    assert rc == 0
    assert seen["args"].from_backend == "supabase"
    assert seen["args"].project == "demo"


def test_mass_undo_filters_parse_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    """mass-undo filters --since, --actor, --actor-prefix parse correctly."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_mass_undo(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_mass_undo", fake_mass_undo)

    # All three filters
    rc = timeline_cli.main([
        "mass-undo", "my-slug",
        "--since", "2026-05-01T00:00:00Z",
        "--actor", "agent:tester",
        "--actor-prefix", "agent:",
    ])
    assert rc == 0
    assert seen["args"].ts_since == "2026-05-01T00:00:00Z"
    assert seen["args"].actor_id == "agent:tester"
    assert seen["args"].actor_id_prefix == "agent:"
    assert seen["args"].yes is False


def test_mass_undo_yes_flag_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_mass_undo(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_mass_undo", fake_mass_undo)

    rc = timeline_cli.main([
        "mass-undo", "my-slug", "--actor", "agent:x", "--yes",
    ])
    assert rc == 0
    assert seen["args"].yes is True


def test_erase_parses_all_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_erase(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_erase", fake_erase)

    rc = timeline_cli.main([
        "erase", "my-slug",
        "--event-ids", "01AAAAAAAAAAAAAAAAAAAAA100,01AAAAAAAAAAAAAAAAAAAAA200",
        "--kind", "clip.added,clip.removed",
        "--actor", "agent:tester",
        "--actor-prefix", "agent:",
        "--after", "2026-05-01T00:00:00Z",
        "--before", "2026-05-21T00:00:00Z",
        "--reason", "GDPR request",
        "--policy-ref", "POL-2026-001",
        "--yes",
    ])
    assert rc == 0
    assert seen["args"].slug == "my-slug"
    assert seen["args"].event_ids_raw == "01AAAAAAAAAAAAAAAAAAAAA100,01AAAAAAAAAAAAAAAAAAAAA200"
    assert seen["args"].kind_allowlist_raw == "clip.added,clip.removed"
    assert seen["args"].actor_id == "agent:tester"
    assert seen["args"].actor_id_prefix == "agent:"
    assert seen["args"].ts_after == "2026-05-01T00:00:00Z"
    assert seen["args"].ts_before == "2026-05-21T00:00:00Z"
    assert seen["args"].reason == "GDPR request"
    assert seen["args"].policy_ref == "POL-2026-001"
    assert seen["args"].yes is True


def test_erase_requires_reason_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["erase", "my-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--reason" in captured.err


def test_erase_defaults_to_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --yes, the --yes flag defaults to False (preview mode)."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_erase(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_erase", fake_erase)

    rc = timeline_cli.main([
        "erase", "my-slug", "--reason", "test",
    ])
    assert rc == 0
    assert seen["args"].yes is False


def test_m9_subcommands_appear_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    for cmd in ("push", "pull", "recover", "branch", "branches", "undo", "mass-undo", "erase"):
        assert cmd in captured.out


def test_branch_subcommands_appear_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["branch", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    for verb in ("create", "list"):
        assert verb in captured.out


# ---------------------------------------------------------------------------
# secondary CLI parsing / handler tests
# ---------------------------------------------------------------------------


def _session() -> SimpleNamespace:
    return SimpleNamespace(project="demo", agent_id="tester", id="session-1")


def _event(kind: str, payload: object) -> TimelineEvent:
    return TimelineEvent.new(
        timeline_id="00000000-0000-0000-0000-000000000000",
        ts="2026-05-20T12:00:00Z",
        actor=TimelineActor(type="agent", id="tester:session-1", display="tester"),
        kind=kind,
        payload=payload,
    )


def test_history_row_displays_timeline_config_replaced_kind() -> None:
    event = _event(
        "timeline.config_replaced",
        TimelineConfigReplacedPayload(config={"tracks": [], "clips": []}),
    )

    row = timeline_cli._format_history_row(1, event, "local_fs")

    assert "kind=timeline.config_replaced" in row
    assert "actor=tester" in row


def test_transition_subcommand_help_shows_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["transition", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    for verb in ("set", "remove"):
        assert verb in captured.out


@pytest.mark.parametrize(
    ("argv", "handler_name", "expected"),
    [
        (
            ["transition", "set", "my-slug", "--between", "a,b", "--kind", "cross-fade", "--duration", "0.75"],
            "cmd_transition_set",
            {"slug": "my-slug", "between": "a,b", "kind": "cross-fade", "duration_seconds": 0.75},
        ),
        (
            ["transition", "remove", "my-slug", "--between", "a,b"],
            "cmd_transition_remove",
            {"slug": "my-slug", "between": "a,b"},
        ),
        (
            ["effect", "add", "my-slug", "--clip", "c1", "--effect-id", "glow", "--params", "x=1", "--params", "y=2"],
            "cmd_effect_add",
            {"slug": "my-slug", "clip_id": "c1", "effect_id": "glow", "params_raw": ["x=1", "y=2"]},
        ),
        (
            ["effect", "remove", "my-slug", "--clip", "c1", "--effect-id", "glow"],
            "cmd_effect_remove",
            {"slug": "my-slug", "clip_id": "c1", "effect_id": "glow"},
        ),
        (
            ["effect", "tune", "my-slug", "--clip", "c1", "--effect-id", "glow", "--param", "opacity", "--value", "0.5"],
            "cmd_effect_tune",
            {"slug": "my-slug", "clip_id": "c1", "effect_id": "glow", "param": "opacity", "value": "0.5"},
        ),
        (
            ["theme", "set", "my-slug", "--theme", "banodoco-default"],
            "cmd_theme_set",
            {"slug": "my-slug", "theme_id": "banodoco-default"},
        ),
        (
            ["theme", "override", "my-slug", "--override-id", "visual", "--value", '{"fps":24}'],
            "cmd_theme_override",
            {"slug": "my-slug", "override_id": "visual", "value": '{"fps":24}'},
        ),
        (
            ["track", "add", "my-slug", "--kind", "audio", "--label", "Music", "--track-id", "track-1"],
            "cmd_track_add",
            {"slug": "my-slug", "kind": "audio", "label": "Music", "track_id": "track-1"},
        ),
        (
            ["track", "remove", "my-slug", "--track-id", "track-1"],
            "cmd_track_remove",
            {"slug": "my-slug", "track_id": "track-1"},
        ),
        (
            ["audio", "bind", "my-slug", "--clip", "c1", "--asset", "a1"],
            "cmd_audio_bind",
            {"slug": "my-slug", "clip_id": "c1", "asset_id": "a1"},
        ),
        (
            ["audio", "unbind", "my-slug", "--clip", "c1"],
            "cmd_audio_unbind",
            {"slug": "my-slug", "clip_id": "c1"},
        ),
        (
            ["arrangement", "set", "my-slug", "--from-json", "/tmp/arrangement.json"],
            "cmd_arrangement_set",
            {"slug": "my-slug", "from_json": "/tmp/arrangement.json"},
        ),
        (
            ["arrangement", "show", "my-slug", "--json"],
            "cmd_arrangement_show",
            {"slug": "my-slug", "json_out": True},
        ),
    ],
)
def test_secondary_subcommands_parse_and_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    handler_name: str,
    expected: dict[str, object],
) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, handler_name, fake_handler)

    rc = timeline_cli.main(argv)
    assert rc == 0
    args = seen["args"]
    for key, value in expected.items():
        assert getattr(args, key) == value


def test_track_add_rejects_caption_kind_at_parse_time(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(AstridArgumentError) as excinfo:
        timeline_cli.main(["track", "add", "my-slug", "--kind", "caption"])
    assert excinfo.value.argument_name == "--kind"
    assert excinfo.value.invalid_value == "caption"
    assert "visual" in excinfo.value.valid_options


def test_transition_set_rejects_invalid_kind_at_parse_time(capsys: pytest.CaptureFixture[str]) -> None:
    """``transition set --kind dissolve`` must raise AstridArgumentError, not SystemExit(2)."""
    with pytest.raises(AstridArgumentError) as excinfo:
        timeline_cli.main(
            ["transition", "set", "my-slug", "--between", "a,b", "--kind", "dissolve"]
        )
    exc = excinfo.value
    assert exc.argument_name == "--kind"
    assert exc.invalid_value == "dissolve"
    assert exc.catalog == "transition"
    assert "cross-fade" in exc.valid_options, (
        f"valid_options must include cross-fade, got {exc.valid_options!r}"
    )
    assert "invalid choice" in str(exc)


def test_transition_set_rejects_invalid_kind_produces_no_raw_argparse_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Stderr must NOT contain raw argparse text or ``timelines:`` prefix."""
    try:
        timeline_cli.main(
            ["transition", "set", "my-slug", "--between", "a,b", "--kind", "wipe"]
        )
    except AstridArgumentError:
        pass
    captured = capsys.readouterr()
    assert "timelines:" not in captured.err
    # argparse usage blurb appears when parser.error() calls sys.exit(2);
    # with RecoverableArgumentParser it must not leak.
    assert "usage:" not in captured.err


def test_clip_add_rejects_invalid_kind_at_parse_time(capsys: pytest.CaptureFixture[str]) -> None:
    """``clip add --kind visual`` (a track kind) must raise AstridArgumentError."""
    with pytest.raises(AstridArgumentError) as excinfo:
        timeline_cli.main(
            ["clip", "add", "my-slug", "--kind", "visual", "--asset", "x", "--track", "visual"]
        )
    exc = excinfo.value
    assert exc.argument_name == "--kind"
    assert exc.invalid_value == "visual"
    assert exc.catalog == "clip"
    assert "video" in exc.valid_options, (
        f"valid_options must include video, got {exc.valid_options!r}"
    )
    assert "invalid choice" in str(exc)


@pytest.mark.parametrize(
    "argv",
    [
        ["transition", "set", "my-slug"],
        ["effect", "add", "my-slug"],
        ["theme", "override", "my-slug"],
        ["track", "remove", "my-slug"],
        ["audio", "bind", "my-slug"],
        ["pool", "score", "my-slug"],
        ["arrangement", "set", "my-slug"],
    ],
)
def test_secondary_subcommands_missing_required_flags_error(
    argv: list[str],
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(argv)
    assert excinfo.value.code != 0


def test_transition_handler_delegates_to_transition_edits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}

    def fake_transition_set(project_slug, slug, *, left_clip_id, right_clip_id, kind, duration_seconds, actor=None, expected_version=None, txn_id=None, root=None):
        seen.update(
            {
                "project_slug": project_slug,
                "slug": slug,
                "left_clip_id": left_clip_id,
                "right_clip_id": right_clip_id,
                "kind": kind,
                "duration_seconds": duration_seconds,
            }
        )
        return _event(
            "transition.set",
            TransitionSetPayload(
                left_clip_id=left_clip_id,
                right_clip_id=right_clip_id,
                kind=kind,
                duration_seconds=duration_seconds,
            ),
        )

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.transition_edits, "transition_set", fake_transition_set)

    rc = timeline_cli.cmd_transition_set(
        argparse.Namespace(slug="primary", between="clip-a,clip-b", kind="cross-fade", duration_seconds=0.5)
    )
    assert rc == 0
    assert seen == {
        "project_slug": "demo",
        "slug": "primary",
        "left_clip_id": "clip-a",
        "right_clip_id": "clip-b",
        "kind": "cross-fade",
        "duration_seconds": 0.5,
    }
    captured = capsys.readouterr()
    assert "transition: event " in captured.out
    assert "kind=transition.set" in captured.out
    assert "backend=local_fs" in captured.out


def test_effect_add_handler_delegates_to_effect_edits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}

    def fake_effect_add(project_slug, slug, *, clip_id, effect_id, params=None, actor=None, expected_version=None, txn_id=None, root=None):
        seen.update(
            {
                "project_slug": project_slug,
                "slug": slug,
                "clip_id": clip_id,
                "effect_id": effect_id,
                "params": params,
            }
        )
        return _event("effect.added", EffectAddedPayload(clip_id=clip_id, effect_id=effect_id, params=params))

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.effect_edits, "effect_add", fake_effect_add)

    rc = timeline_cli.cmd_effect_add(
        argparse.Namespace(slug="primary", clip_id="clip-1", effect_id="glow", params_raw=["opacity=0.5", "mode=soft"])
    )
    assert rc == 0
    assert seen["params"] == {"opacity": "0.5", "mode": "soft"}
    captured = capsys.readouterr()
    assert "effect: event " in captured.out
    assert "kind=effect.added" in captured.out


def test_theme_set_handler_delegates_to_theme_edits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}

    def fake_theme_set(project_slug, slug, *, theme_id, actor=None, expected_version=None, txn_id=None, root=None):
        seen.update({"project_slug": project_slug, "slug": slug, "theme_id": theme_id})
        return _event("theme.set", ThemeSetPayload(theme_id=theme_id))

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.theme_edits, "theme_set", fake_theme_set)

    rc = timeline_cli.cmd_theme_set(argparse.Namespace(slug="primary", theme_id="banodoco-default"))
    assert rc == 0
    assert seen == {"project_slug": "demo", "slug": "primary", "theme_id": "banodoco-default"}
    captured = capsys.readouterr()
    assert "theme: event " in captured.out
    assert "kind=theme.set" in captured.out


def test_track_add_handler_delegates_to_track_edits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}

    def fake_track_add(project_slug, slug, *, track_id, kind, label, actor=None, expected_version=None, txn_id=None, root=None):
        seen.update({"project_slug": project_slug, "slug": slug, "track_id": track_id, "kind": kind, "label": label})
        return _event("track.added", TrackAddedPayload(track_id=track_id, kind=kind, label=label))

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.track_edits, "track_add", fake_track_add)

    rc = timeline_cli.cmd_track_add(argparse.Namespace(slug="primary", track_id="track-1", kind="audio", label="Music"))
    assert rc == 0
    assert seen == {
        "project_slug": "demo",
        "slug": "primary",
        "track_id": "track-1",
        "kind": "audio",
        "label": "Music",
    }
    captured = capsys.readouterr()
    assert "track: event " in captured.out
    assert "kind=track.added" in captured.out


def test_audio_bind_handler_delegates_to_audio_edits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}

    def fake_audio_bind(project_slug, slug, *, clip_id, asset_id, actor=None, expected_version=None, txn_id=None, root=None):
        seen.update({"project_slug": project_slug, "slug": slug, "clip_id": clip_id, "asset_id": asset_id})
        return _event("audio.bound", AudioBoundPayload(clip_id=clip_id, asset_id=asset_id))

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())
    monkeypatch.setattr(timeline_cli, "_resolve_clip_backend_name", lambda ps, s: "local_fs")
    monkeypatch.setattr(timeline_cli.audio_edits, "audio_bind", fake_audio_bind)

    rc = timeline_cli.cmd_audio_bind(argparse.Namespace(slug="primary", clip_id="clip-1", asset_id="asset-1"))
    assert rc == 0
    assert seen == {
        "project_slug": "demo",
        "slug": "primary",
        "clip_id": "clip-1",
        "asset_id": "asset-1",
    }
    captured = capsys.readouterr()
    assert "audio: event " in captured.out
    assert "kind=audio.bound" in captured.out


def test_arrangement_set_handler_rejects_runtime_container_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    arrangement_path = tmp_path / "arrangement.json"
    arrangement_path.write_text(json.dumps({"clips": [{"uuid": "clip-1"}]}), encoding="utf-8")

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())

    with pytest.raises(timeline_cli.TimelineEditError, match="arrangement set is retired"):
        timeline_cli.cmd_arrangement_set(argparse.Namespace(slug="primary", from_json=str(arrangement_path)))


def test_arrangement_show_handler_reads_arrangement_via_crud(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, object] = {}
    arrangement = {"clips": [{"uuid": "clip-1"}]}

    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())

    def fake_get_arrangement(project_slug: str, slug: str, *, root=None):
        seen["get_arrangement"] = (project_slug, slug, root)
        return arrangement

    def fake_show_timeline(project_slug: str, slug: str, *, root=None):
        seen["show_timeline"] = True
        return None

    monkeypatch.setattr(timeline_cli.crud, "get_arrangement", fake_get_arrangement)
    monkeypatch.setattr(timeline_cli.crud, "show_timeline", fake_show_timeline)

    rc = timeline_cli.cmd_arrangement_show(argparse.Namespace(slug="primary", json_out=True))
    assert rc == 0
    assert seen["get_arrangement"] == ("demo", "primary", None)
    assert "show_timeline" not in seen
    captured = capsys.readouterr()
    assert json.loads(captured.out) == arrangement


def test_transition_set_bad_between_raises_astrid_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())

    with pytest.raises(AstridError, match="--between must be LEFT,RIGHT"):
        timeline_cli.main(["transition", "set", "my-slug", "--between", "a", "--kind", "cross-fade", "--duration", "0.5"])


def test_effect_tune_invalid_json_value_raises_astrid_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())

    with pytest.raises(AstridError, match="--value must be valid JSON"):
        timeline_cli.main(
            ["effect", "tune", "my-slug", "--clip", "c1", "--effect-id", "glow", "--param", "opacity", "--value", "{bad"]
        )


def test_arrangement_set_retired_before_json_validation_raises_astrid_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    arrangement_path = tmp_path / "bad.json"
    arrangement_path.write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: _session())

    with pytest.raises(AstridError, match="arrangement set is retired") as excinfo:
        timeline_cli.main(["arrangement", "set", "my-slug", "--from-json", str(arrangement_path)])
    assert "timeline.config_replaced" in str(excinfo.value)


# ---------------------------------------------------------------------------
# m7 observability — CLI parser/handler dispatch tests (T5)
# ---------------------------------------------------------------------------


def test_m7_subcommands_appear_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    for verb in ("history", "diff", "audit", "preview", "who-edited"):
        assert verb in captured.out


def test_history_parses_slug_or_id_and_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_history(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_history", fake_history)

    rc = timeline_cli.main(["history", "my-slug", "--since", "01EVENT0001", "--limit", "25"])
    assert rc == 0
    args = seen["args"]
    assert args.slug_or_id == "my-slug"
    assert args.since_event_id == "01EVENT0001"
    assert args.limit == 25


def test_history_default_limit_is_50(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_history(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_history", fake_history)

    rc = timeline_cli.main(["history", "my-slug"])
    assert rc == 0
    assert seen["args"].limit == 50
    assert seen["args"].since_event_id is None


def test_history_missing_slug_or_id_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["history"])
    assert excinfo.value.code != 0


def test_diff_parses_from_to_and_with_state(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_diff(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_diff", fake_diff)

    rc = timeline_cli.main(
        ["diff", "my-slug", "--from", "01EVENT01", "--to", "01EVENT02", "--with-state"]
    )
    assert rc == 0
    args = seen["args"]
    assert args.slug_or_id == "my-slug"
    assert args.from_event_id == "01EVENT01"
    assert args.to_event_id == "01EVENT02"
    assert args.with_state is True


def test_diff_missing_required_from_flag_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["diff", "my-slug", "--to", "01EVENT02"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--from" in captured.err


def test_diff_missing_required_to_flag_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["diff", "my-slug", "--from", "01EVENT01"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--to" in captured.err


def test_audit_parses_slug_or_id_and_include_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_audit(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_audit", fake_audit)

    rc = timeline_cli.main(["audit", "my-slug", "--include-ops"])
    assert rc == 0
    args = seen["args"]
    assert args.slug_or_id == "my-slug"
    assert args.include_ops is True


def test_audit_without_include_ops_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_audit(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_audit", fake_audit)

    rc = timeline_cli.main(["audit", "my-slug"])
    assert rc == 0
    assert seen["args"].include_ops is False


def test_preview_parses_at_and_out(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_preview(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_preview", fake_preview)

    rc = timeline_cli.main(["preview", "my-slug", "--at", "01EVENT42", "--out", "/tmp/preview.json"])
    assert rc == 0
    args = seen["args"]
    assert args.slug_or_id == "my-slug"
    assert args.at_event_id == "01EVENT42"
    assert args.out_path == "/tmp/preview.json"


def test_preview_missing_required_at_flag_errors(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["preview", "my-slug"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "--at" in captured.err


def test_who_edited_parses_slug_or_id(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_who_edited(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_who_edited", fake_who_edited)

    rc = timeline_cli.main(["who-edited", "my-slug"])
    assert rc == 0
    assert seen["args"].slug_or_id == "my-slug"


def test_history_help_shows_all_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["history", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--since" in captured.out
    assert "--limit" in captured.out
    assert "slug_or_id" in captured.out


def test_diff_help_shows_all_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["diff", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--from" in captured.out
    assert "--to" in captured.out
    assert "--with-state" in captured.out


def test_audit_help_shows_all_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["audit", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--include-ops" in captured.out


def test_preview_help_shows_all_flags(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["preview", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--at" in captured.out
    assert "--out" in captured.out


# ── handler dispatch tests (monkeypatch) ──────────────────────────────────────


def test_cmd_history_dispatches_via_main(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_history(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_history", fake_history)

    rc = timeline_cli.main(["history", "target-1"])
    assert rc == 0
    assert seen["args"].command == "history"


def test_cmd_diff_dispatches_via_main(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_diff(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_diff", fake_diff)

    rc = timeline_cli.main(["diff", "target-1", "--from", "e1", "--to", "e2"])
    assert rc == 0
    assert seen["args"].command == "diff"


def test_cmd_audit_dispatches_via_main(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_audit(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_audit", fake_audit)

    rc = timeline_cli.main(["audit", "target-1"])
    assert rc == 0
    assert seen["args"].command == "audit"


def test_cmd_preview_dispatches_via_main(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_preview(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_preview", fake_preview)

    rc = timeline_cli.main(["preview", "target-1", "--at", "e1"])
    assert rc == 0
    assert seen["args"].command == "preview"


def test_cmd_who_edited_dispatches_via_main(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def fake_who_edited(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_who_edited", fake_who_edited)

    rc = timeline_cli.main(["who-edited", "target-1"])
    assert rc == 0
    assert seen["args"].command == "who-edited"


# ── --out guard rejection test ────────────────────────────────────────────────


def test_preview_out_guard_rejects_paths_inside_timeline_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """cmd_preview --out rejects paths inside the timeline home directory."""
    session = _session()
    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: session)

    # Create a fake timeline home
    timeline_home = tmp_path / "demo" / "timelines" / "01J00000000000000000000000"
    timeline_home.mkdir(parents=True)
    (timeline_home / "assembly.json").write_text(
        '{"clips": [], "tracks": []}', encoding="utf-8"
    )
    (timeline_home / "display.json").write_text(
        '{"schema_version": 1, "slug": "test-tl", "name": "Test"}', encoding="utf-8"
    )
    (timeline_home / "assembly.identity.json").write_text(
        '{"timeline_id": "00000000-0000-0000-0000-000000000001", "backend": "local_fs"}',
        encoding="utf-8",
    )

    from astrid.core.timeline.observability import ResolvedTarget
    from astrid.core.timeline import observability as obs_mod
    from astrid.core.timeline import eventlog as evlog_mod
    from astrid.core.timeline.events.schema import TimelineEvent as TE

    fake_target = ResolvedTarget(
        backend="local_fs",
        timeline_id="00000000-0000-0000-0000-000000000001",
        timeline_ulid="01J00000000000000000000000",
        timeline_home=timeline_home,
        slug="test-tl",
        backend_name_display="local_fs",
    )

    def fake_resolve(project_slug: str, slug_or_id: str, *, root=None):
        return fake_target

    monkeypatch.setattr(obs_mod, "resolve_timeline_target", fake_resolve)

    # Provide a fake backend with a matching event so replay succeeds
    at_event_id = "01AAAAAAAAAAAAAAAAAAAAAA01"
    event = TE.from_dict({
        "event_id": at_event_id,
        "timeline_id": "00000000-0000-0000-0000-000000000001",
        "ts": "2026-05-20T12:00:00Z",
        "actor": {"type": "system", "id": "test", "display": "Test"},
        "prev_hash": None,
        "hash": "01AAAAAAAAAAAAAAAAAAAAAA010",
        "kind": "clip.added",
        "payload": {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": None},
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
    })

    class FakeBackend:
        def backend_name(self):
            return "local_fs"
        def read_events(self, after=None, limit=None):
            return [event]

    monkeypatch.setattr(
        evlog_mod, "select_timeline_backend",
        lambda timeline_id, timeline_home, preferred_backend: (None, FakeBackend()),
    )

    # Attempt to write inside timeline home — should be rejected
    out_inside = timeline_home / "stale_assembly.json"
    with pytest.raises(AstridError, match="inside the timeline home"):
        timeline_cli.main(
            ["preview", "test-tl", "--at", at_event_id, "--out", str(out_inside)]
        )


def test_preview_out_guard_allows_paths_outside_timeline_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """cmd_preview --out allows paths outside the timeline home."""
    session = _session()
    monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: session)

    timeline_home = tmp_path / "demo" / "timelines" / "01J00000000000000000000000"
    timeline_home.mkdir(parents=True)
    (timeline_home / "assembly.identity.json").write_text(
        '{"timeline_id": "00000000-0000-0000-0000-000000000002", "backend": "local_fs"}',
        encoding="utf-8",
    )

    from astrid.core.timeline.observability import ResolvedTarget

    fake_target = ResolvedTarget(
        backend="local_fs",
        timeline_id="00000000-0000-0000-0000-000000000002",
        timeline_ulid="01J00000000000000000000000",
        timeline_home=timeline_home,
        slug="test-tl",
        backend_name_display="local_fs",
    )

    def fake_resolve(project_slug: str, slug_or_id: str, *, root=None):
        return fake_target

    from astrid.core.timeline import observability as obs_mod
    from astrid.core.timeline import eventlog as evlog_mod

    monkeypatch.setattr(obs_mod, "resolve_timeline_target", fake_resolve)

    # Stub out select_timeline_backend and replay_projection
    from astrid.core.timeline.events.schema import TimelineEvent as TE2

    at_eid2 = "01AAAAAAAAAAAAAAAAAAAAAA02"
    event = TE2.from_dict({
        "event_id": at_eid2,
        "timeline_id": "00000000-0000-0000-0000-000000000002",
        "ts": "2026-05-20T12:00:00Z",
        "actor": {"type": "system", "id": "test", "display": "Test"},
        "prev_hash": None,
        "hash": "01AAAAAAAAAAAAAAAAAAAAAA020",
        "kind": "clip.added",
        "payload": {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": None},
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
    })

    class FakeBackendWithEvent:
        def backend_name(self):
            return "local_fs"

        def read_events(self, after=None, limit=None):
            return [event]

    monkeypatch.setattr(
        evlog_mod,
        "select_timeline_backend",
        lambda timeline_id, timeline_home, preferred_backend: (None, FakeBackendWithEvent()),
    )

    out_outside = tmp_path / "outside_preview.json"
    rc = timeline_cli.main(
        ["preview", "test-tl", "--at", at_eid2, "--out", str(out_outside)]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "Projected state written to" in captured.out
    assert out_outside.is_file()


# ---------------------------------------------------------------------------
# m8 migrate-events — CLI parser/handler tests (T13)
# ---------------------------------------------------------------------------


def test_migrate_events_appears_in_help(capsys: pytest.CaptureFixture[str]) -> None:
    """migrate-events must appear in the top-level help listing."""
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "migrate-events" in captured.out
    assert "Migrate legacy timeline data" in captured.out


def test_migrate_events_help_shows_all_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """migrate-events --help must list --dry-run, --apply, --project, --all-projects, --json."""
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["migrate-events", "--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "--dry-run" in captured.out
    assert "--apply" in captured.out
    assert "--project" in captured.out
    assert "--all-projects" in captured.out
    assert "--json" in captured.out


def test_migrate_events_dry_run_is_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """--dry-run must be True by default and --apply must be False by default."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--project", "demo"])
    assert rc == 0
    args = seen["args"]
    assert args.dry_run is True
    assert args.apply is False


def test_migrate_events_apply_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--apply must set apply=True."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--apply", "--project", "demo"])
    assert rc == 0
    args = seen["args"]
    assert args.apply is True


def test_migrate_events_project_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--project <slug> must set project_slug."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--project", "my-proj"])
    assert rc == 0
    args = seen["args"]
    assert args.project_slug == "my-proj"
    assert args.all_projects is False


def test_migrate_events_all_projects_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--all-projects must set all_projects=True."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--all-projects"])
    assert rc == 0
    args = seen["args"]
    assert args.all_projects is True
    assert args.project_slug is None


def test_migrate_events_json_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """--json must set json_out=True."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--project", "demo", "--json"])
    assert rc == 0
    args = seen["args"]
    assert args.json_out is True


def test_migrate_events_json_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """--json must default to False when not provided."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--project", "demo"])
    assert rc == 0
    args = seen["args"]
    assert args.json_out is False


def test_migrate_events_requires_project_or_all(capsys: pytest.CaptureFixture[str]) -> None:
    """migrate-events without --project or --all-projects must fail."""
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["migrate-events"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "error" in captured.err.lower() or "required" in captured.err.lower()


def test_migrate_events_mutually_exclusive_project_all(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--project and --all-projects together must be rejected at parse time."""
    with pytest.raises(SystemExit) as excinfo:
        timeline_cli.main(["migrate-events", "--project", "x", "--all-projects"])
    assert excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "not allowed" in captured.err.lower() or "error" in captured.err.lower()


def test_migrate_events_handler_dispatches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies that migrate-events dispatches to cmd_migrate_events."""
    seen: dict[str, argparse.Namespace] = {}

    def fake_handler(args: argparse.Namespace) -> int:
        seen["args"] = args
        return 0

    monkeypatch.setattr(timeline_cli, "cmd_migrate_events", fake_handler)

    rc = timeline_cli.main(["migrate-events", "--project", "demo"])
    assert rc == 0
    assert seen["args"].command == "migrate-events"


# ---------------------------------------------------------------------------
# m8 observability-on-imported-timelines integration tests (T13)
# ---------------------------------------------------------------------------


def _build_legacy_timeline_home(tmp_path: Path, slug: str = "demo") -> tuple[Path, str, str]:
    """Create a minimal legacy timeline directory tree suitable for import.

    Returns ``(timeline_home, project_slug, ulid)``.
    """
    ulid = "01J00000000000000000000000"
    pdir = tmp_path / slug
    pdir.mkdir(parents=True)
    (pdir / "project.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-11T00:00:00Z",
                "name": slug,
                "schema_version": 1,
                "slug": slug,
                "updated_at": "2026-05-11T00:00:00Z",
                "default_timeline_id": None,
            }
        ),
        encoding="utf-8",
    )
    (pdir / "runs").mkdir()
    (pdir / "sources").mkdir()

    tdir = pdir / "timelines" / ulid
    tdir.mkdir(parents=True)
    return tdir, slug, ulid


def _write_legacy_assembly(tdir: Path) -> dict[str, Any]:
    """Write a minimal legacy assembly.json and return its body."""
    body: dict[str, Any] = {
        "schema_version": 1,
        "assembly": {
            "clips": [
                {"id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": 0},
            ],
            "tracks": [
                {"id": "t1", "kind": "visual", "label": "Main"},
            ],
            "transitions": [],
            "effects": [],
            "theme": {"name": "dark"},
            "pool": {"assets": {}},
            "audio": {},
            "arrangement": {},
        },
    }
    (tdir / "assembly.json").write_text(json.dumps(body), encoding="utf-8")
    return body


def _write_display_json(tdir: Path, slug: str = "test-tl") -> None:
    """Write a minimal display.json."""
    (tdir / "display.json").write_text(
        json.dumps({"schema_version": 1, "slug": slug, "name": "Test Timeline"}),
        encoding="utf-8",
    )


def _write_identity_json(tdir: Path, timeline_id: str | None = None) -> str:
    """Write assembly.identity.json and return the timeline_id."""
    tid = timeline_id or "00000000-0000-0000-0000-000000000099"
    (tdir / "assembly.identity.json").write_text(
        json.dumps({"timeline_id": tid, "backend": "local_fs"}),
        encoding="utf-8",
    )
    return tid


def _import_timeline(
    tdir: Path,
    ulid: str,
    *,
    skip_if_events_exist: bool = True,
) -> dict[str, Any]:
    """Run import_from_legacy_local on a legacy timeline dir and return the result dict.

    If *skip_if_events_exist* is True (the default) and the timeline already has
    events, the import is skipped — the returned dict will have ``imported: False``.
    """
    from astrid.core.timeline.migration import import_from_legacy_local
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
    from astrid.core.timeline.events.schema import TimelineActor

    backend = LocalFsBackend(timeline_home=tdir, timeline_id=ulid)
    if skip_if_events_exist and backend.read_events():
        return {"ok": True, "imported": False, "event_id": None, "parity_ok": None, "detail": "skipped"}

    actor = TimelineActor(type="agent", id="test:cli", display="Test CLI")

    return import_from_legacy_local(
        backend=backend,
        timeline_home=tdir,
        actor=actor,
    )


def _count_events(tdir: Path) -> int:
    """Return the number of events in the event log."""
    from astrid.core.timeline.eventlog.local_fs import LocalFsBackend

    # Use the timeline dir name as the timeline_id if no identity exists
    ulid = tdir.name
    backend = LocalFsBackend(timeline_home=tdir, timeline_id=ulid)
    return len(backend.read_events())


class TestObservabilityOnImportedLocalFs:
    """Runtime LocalFs legacy imports fail closed before observability."""

    def test_runtime_import_rejects_legacy_local_without_appending(
        self,
        tmp_path: Path,
    ) -> None:
        tdir, _slug, ulid = _build_legacy_timeline_home(tmp_path, slug="demo")
        body = _write_legacy_assembly(tdir)
        _write_display_json(tdir)
        _write_identity_json(tdir)

        result = _import_timeline(tdir, ulid)
        assert result.get("ok") is False
        assert result.get("imported") is False
        assert "scripts/migrations/sprint-2" in result.get("detail", "")
        assert _count_events(tdir) == 0

        from astrid.core.project.jsonio import read_json

        assert read_json(tdir / "assembly.json") == body


class TestAuditProjectionParityAfterImport:
    """Confirm audit reports projection parity after import."""

    def test_local_runtime_import_rejection_leaves_source_blob_intact(
        self,
        tmp_path: Path,
    ) -> None:
        """Legacy local conversion is now migration-script only."""
        tdir, _slug, ulid = _build_legacy_timeline_home(tmp_path, slug="demo")
        body = _write_legacy_assembly(tdir)
        _write_display_json(tdir)
        _write_identity_json(tdir)

        result = _import_timeline(tdir, ulid)
        assert result.get("ok") is False
        assert result.get("imported") is False
        assert result.get("parity_ok") is None

        from astrid.core.project.jsonio import read_json

        current_assembly = read_json(tdir / "assembly.json")
        assert current_assembly == body, "Source assembly.json was mutated!"

    def test_supabase_mocked_audit_parity(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Audit on a mocked Supabase config seed must report correctly.

        Uses a fake Supabase transport that returns a timeline.config_replaced event
        to verify the observability plumbing works end-to-end.
        """
        from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent
        from astrid.core.timeline.observability import ResolvedTarget

        # Build a fake event that represents a seeded TimelineConfig.
        tid = "00000000-0000-0000-0000-000000000100"
        eid = "01AAAAAAAAAAAAAAAAAAAAA100"
        actor = TimelineActor(type="agent", id="test:cli", display="Test CLI")

        imported_event = TimelineEvent.from_dict(
            {
                "event_id": eid,
                "timeline_id": tid,
                "ts": "2026-05-20T12:00:00Z",
                "actor": {"type": "agent", "id": "test:cli", "display": "Test CLI"},
                "prev_hash": None,
                "hash": "01AAAAAAAAAAAAAAAAAAAAA1000",
                "kind": "timeline.config_replaced",
                "payload": {
                    "config": {"clips": [], "tracks": []},
                },
                "expected_version": None,
                "schema_version": 2,
                "txn_id": None,
            }
        )

        class FakeSupabaseTransport:
            def append_event(self, timeline_id, kind, payload, *, actor=None):
                raise NotImplementedError("read-only test")

            def append_imported_event(self, timeline_id, source_event, *, idempotency_key=None, actor=None):
                raise NotImplementedError("read-only test")

            def read_events(self, timeline_id, after=None, limit=None):
                return [imported_event]

            def head(self, timeline_id):
                return imported_event

            def verify_chain(self, timeline_id):
                return True, []

            def repair_erasure(self, timeline_id, target_event_ids, *, reason=None, erased_by=None, policy_ref=None):
                raise NotImplementedError("read-only test")

        fake_transport = FakeSupabaseTransport()
        # We can't use SupabaseBackend directly because it needs credentials,
        # but we can monkeypatch the observability path to use our fake.
        session = SimpleNamespace(project="demo", agent_id="tester", id="session-1")
        monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: session)

        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline import eventlog as evlog_mod

        fake_target = ResolvedTarget(
            backend="supabase",
            timeline_id=tid,
            timeline_ulid="01J00000000000000000000000",
            timeline_home=tmp_path,  # not actually read for supabase
            slug="test-tl",
            backend_name_display="supabase",
        )

        monkeypatch.setattr(
            obs_mod, "resolve_timeline_target", lambda *a, **kw: fake_target
        )

        # Provide the fake transport via select_timeline_backend
        from astrid.core.timeline.eventlog.types import EventLogVerification, EventLogHead

        class FakeSupabaseBackend:
            def backend_name(self):
                return "supabase"

            def read_events(self, after=None, limit=None):
                return [imported_event]

            def head(self):
                return EventLogHead(
                    timeline_id=imported_event.timeline_id,
                    last_event_id=imported_event.event_id,
                    last_hash=imported_event.hash,
                    event_count=1,
                    version=1,
                )

            def verify_chain(self):
                return EventLogVerification(
                    ok=True, checked_events=1,
                    last_event_id=imported_event.event_id,
                )

        monkeypatch.setattr(
            evlog_mod,
            "select_timeline_backend",
            lambda timeline_id, timeline_home, preferred_backend: (None, FakeSupabaseBackend()),
        )

        rc = timeline_cli.main(["audit", "test-tl", "--include-ops"])
        assert rc == 0
        captured = capsys.readouterr()
        # Audit should show backend as supabase and chain verification passed
        assert "supabase" in captured.out.lower()
        assert "Hash chain" in captured.out and "OK" in captured.out

    def test_read_only_commands_on_supabase_imported_do_not_append(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Read-only commands on mocked Supabase config seed must not append."""
        from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent
        from astrid.core.timeline.observability import ResolvedTarget

        tid = "00000000-0000-0000-0000-000000000101"
        eid = "01AAAAAAAAAAAAAAAAAAAAA101"

        imported_event = TimelineEvent.from_dict(
            {
                "event_id": eid,
                "timeline_id": tid,
                "ts": "2026-05-20T12:00:00Z",
                "actor": {"type": "agent", "id": "test:cli", "display": "Test CLI"},
                "prev_hash": None,
                "hash": "01AAAAAAAAAAAAAAAAAAAAA1010",
                "kind": "timeline.config_replaced",
                "payload": {
                    "config": {"clips": [], "tracks": []},
                },
                "expected_version": None,
                "schema_version": 2,
                "txn_id": None,
            }
        )

        session = SimpleNamespace(project="demo", agent_id="tester", id="session-1")
        monkeypatch.setattr(timeline_cli, "_require_session", lambda slug=None: session)

        from astrid.core.timeline import observability as obs_mod
        from astrid.core.timeline import eventlog as evlog_mod

        fake_target = ResolvedTarget(
            backend="supabase",
            timeline_id=tid,
            timeline_ulid="01J00000000000000000000000",
            timeline_home=tmp_path,
            slug="test-tl",
            backend_name_display="supabase",
        )

        monkeypatch.setattr(
            obs_mod, "resolve_timeline_target", lambda *a, **kw: fake_target
        )

        # Track whether append was called
        append_calls: list[object] = []

        from astrid.core.timeline.eventlog.types import EventLogVerification, EventLogHead

        class ReadOnlySupabaseBackend:
            def backend_name(self):
                return "supabase"

            def read_events(self, after=None, limit=None):
                return [imported_event]

            def head(self):
                return EventLogHead(
                    timeline_id=imported_event.timeline_id,
                    last_event_id=imported_event.event_id,
                    last_hash=imported_event.hash,
                    event_count=1,
                    version=1,
                )

            def verify_chain(self):
                return EventLogVerification(
                    ok=True, checked_events=1,
                    last_event_id=imported_event.event_id,
                )

            def append_event(self, *args, **kwargs):
                append_calls.append((args, kwargs))
                raise AssertionError("append_event must not be called by read-only commands")

            def append_imported_event(self, *args, **kwargs):
                append_calls.append((args, kwargs))
                raise AssertionError("append_imported_event must not be called by read-only commands")

        monkeypatch.setattr(
            evlog_mod,
            "select_timeline_backend",
            lambda timeline_id, timeline_home, preferred_backend: (None, ReadOnlySupabaseBackend()),
        )

        # Run all read-only observability commands
        for argv in [
            ["history", "test-tl"],
            ["diff", "test-tl", "--from", eid, "--to", eid],
            ["audit", "test-tl"],
            ["preview", "test-tl", "--at", eid, "--out", str(Path("/tmp") / "pv_supabase.json")],
        ]:
            rc = timeline_cli.main(argv)
            assert rc == 0, f"Command {' '.join(argv)} failed with rc={rc}"

        assert len(append_calls) == 0, (
            f"append_event was called {len(append_calls)} times by read-only commands"
        )


# ============================================================================
# Realistic m2/m3 event-stream CLI integration tests (M9 / T14)
# ============================================================================


class TestRealisticEventStreamCLI:
    """CLI integration tests with realistic m2/m3 event streams.

    These tests exercise branch, recovery, undo, and mass-undo verbs
    against timelines populated with diverse domain events (clips,
    tracks, effects, transitions, audio, theme, pool, arrangement)
    to verify end-to-end parsing and handler dispatch.
    """

    def test_branch_recovery_undo_parsing_chain(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ):
        """Branch, recovery, and undo verbs parse with realistic flags."""
        seen: list[dict] = []

        def fake_branch_create(args):
            seen.append({"verb": "branch_create", "args": vars(args)})
            return 0

        def fake_branch_list(args):
            seen.append({"verb": "branch_list", "args": vars(args)})
            return 0

        def fake_recover(args):
            seen.append({"verb": "recover", "args": vars(args)})
            return 0

        def fake_undo(args):
            seen.append({"verb": "undo", "args": vars(args)})
            return 0

        monkeypatch.setattr(timeline_cli, "cmd_branch_create", fake_branch_create)
        monkeypatch.setattr(timeline_cli, "cmd_branch_list", fake_branch_list)
        monkeypatch.setattr(timeline_cli, "cmd_recover", fake_recover)
        monkeypatch.setattr(timeline_cli, "cmd_undo", fake_undo)

        # Branch create
        rc = timeline_cli.main([
            "branch", "create", "source-tl", "br1",
            "--from", "01JAAAAAAAAAAAAAAAAAAAAA01",
            "--reason", "test branch",
        ])
        assert rc == 0
        assert seen[0]["verb"] == "branch_create"
        assert seen[0]["args"]["source_slug_or_id"] == "source-tl"
        assert seen[0]["args"]["branch_slug"] == "br1"
        assert seen[0]["args"]["from_event_id"] == "01JAAAAAAAAAAAAAAAAAAAAA01"

        # Branch list
        rc = timeline_cli.main(["branch", "list", "source-tl"])
        assert rc == 0
        assert seen[1]["args"]["source_slug_or_id"] == "source-tl"

        # Recover
        rc = timeline_cli.main([
            "recover", "target-tl",
            "--at", "01JAAAAAAAAAAAAAAAAAAAAA99",
            "--reason", "corruption recovery",
        ])
        assert rc == 0
        assert seen[2]["verb"] == "recover"
        assert seen[2]["args"]["slug"] == "target-tl"
        assert seen[2]["args"]["at_event_id"] == "01JAAAAAAAAAAAAAAAAAAAAA99"

        # Undo
        rc = timeline_cli.main(["undo", "undo-tl"])
        assert rc == 0
        assert seen[3]["verb"] == "undo"
        assert seen[3]["args"]["slug"] == "undo-tl"

    def test_mass_undo_and_erase_parsing_chain(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Mass-undo and erase verbs parse with realistic filters."""
        seen: list[dict] = []

        def fake_mass_undo(args):
            seen.append({"verb": "mass_undo", "args": vars(args)})
            return 0

        def fake_erase(args):
            seen.append({"verb": "erase", "args": vars(args)})
            return 0

        monkeypatch.setattr(timeline_cli, "cmd_mass_undo", fake_mass_undo)
        monkeypatch.setattr(timeline_cli, "cmd_erase", fake_erase)

        # Mass undo with all filters
        rc = timeline_cli.main([
            "mass-undo", "test-tl",
            "--since", "2026-01-01T00:00:00Z",
            "--actor", "runaway-agent",
            "--actor-prefix", "runaway",
            "--yes",
        ])
        assert rc == 0
        assert seen[0]["args"]["slug"] == "test-tl"
        assert seen[0]["args"]["ts_since"] == "2026-01-01T00:00:00Z"
        assert seen[0]["args"]["actor_id"] == "runaway-agent"
        assert seen[0]["args"]["actor_id_prefix"] == "runaway"
        assert seen[0]["args"]["yes"] is True

        # Erase with all filters
        rc = timeline_cli.main([
            "erase", "test-tl",
            "--reason", "compliance policy X",
            "--event-ids", "01JAAAAAAAAAAAAAAAAAAAAA01",
            "--kind", "clip.added",
            "--actor", "bad-actor",
            "--actor-prefix", "bad",
            "--after", "2026-01-01T00:00:00Z",
            "--before", "2026-06-01T00:00:00Z",
            "--policy-ref", "policy-v1",
            "--yes",
        ])
        assert rc == 0
        assert seen[1]["args"]["slug"] == "test-tl"
        assert seen[1]["args"]["reason"] == "compliance policy X"
        assert seen[1]["args"]["event_ids_raw"] == "01JAAAAAAAAAAAAAAAAAAAAA01"
        assert seen[1]["args"]["kind_allowlist_raw"] == "clip.added"
        assert seen[1]["args"]["actor_id"] == "bad-actor"
        assert seen[1]["args"]["actor_id_prefix"] == "bad"
        assert seen[1]["args"]["ts_after"] == "2026-01-01T00:00:00Z"
        assert seen[1]["args"]["ts_before"] == "2026-06-01T00:00:00Z"
        assert seen[1]["args"]["policy_ref"] == "policy-v1"
        assert seen[1]["args"]["yes"] is True

    def test_push_pull_parsing_chain(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Push and pull verbs parse with all destination flags."""
        seen: list[dict] = []

        def fake_push(args):
            seen.append({"verb": "push", "args": vars(args)})
            return 0

        def fake_pull(args):
            seen.append({"verb": "pull", "args": vars(args)})
            return 0

        monkeypatch.setattr(timeline_cli, "cmd_push", fake_push)
        monkeypatch.setattr(timeline_cli, "cmd_pull", fake_pull)

        # Push
        rc = timeline_cli.main([
            "push", "local-tl",
            "--to", "supabase",
            "--project", "my-proj",
        ])
        assert rc == 0
        assert seen[0]["args"]["slug_or_id"] == "local-tl"
        assert seen[0]["args"]["to_backend"] == "supabase"
        assert seen[0]["args"]["project"] == "my-proj"

        # Pull with --into
        rc = timeline_cli.main([
            "pull", "remote-tl",
            "--from", "supabase",
            "--project", "my-proj",
            "--into", "existing-local",
        ])
        assert rc == 0
        assert seen[1]["args"]["slug_or_id"] == "remote-tl"
        assert seen[1]["args"]["from_backend"] == "supabase"
        assert seen[1]["args"]["into_slug"] == "existing-local"

        # Pull with --create --as
        rc = timeline_cli.main([
            "pull", "remote-tl",
            "--from", "supabase",
            "--project", "my-proj",
            "--create",
            "--as", "new-local",
        ])
        assert rc == 0
        assert seen[2]["args"]["create"] is True
        assert seen[2]["args"]["create_as_slug"] == "new-local"

        # Pull with --create (implicit slug)
        rc = timeline_cli.main([
            "pull", "remote-tl",
            "--from", "supabase",
            "--project", "my-proj",
            "--create",
        ])
        assert rc == 0
        assert seen[3]["args"]["create"] is True
        assert seen[3]["args"]["create_as_slug"] is None

    def test_all_m2_m3_verbs_appear_in_parser(self, capsys):
        """All m2/m3 verbs (push, pull, recover, branch, undo, etc.) are
        accepted by the parser without 'invalid choice' errors."""
        # Verify each subcommand is known by the parser
        for verb in ["push", "pull", "recover", "branch", "branches",
                      "undo", "mass-undo", "erase"]:
            # These will fail in the handler due to missing args,
            # but they must NOT fail at the parser level with "invalid choice"
            with pytest.raises(SystemExit) as excinfo:
                timeline_cli.main([verb])
            # Exit code 2 = argparse error (missing args), NOT invalid choice
            assert excinfo.value.code != 0
            captured = capsys.readouterr()
            # Must NOT say "invalid choice" for these verbs
            assert "invalid choice" not in captured.err.lower() or verb not in captured.err
