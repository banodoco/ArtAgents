"""S1 backfill CLI wiring test.

Proves the ``astrid timelines backfill`` product verb parses through the
family parser, dispatches through the product boundary
(``run_product_family``), and makes exactly one SDK call
(``client.timelines.backfill``) with the expected arguments — the same
one-call-per-handler rule as the other seven verbs. Also pins the help text:
``backfill`` is the NEW cutover verb, distinct from the retired legacy
migration/push/pull/sync verbs, which stay absent.
"""

from __future__ import annotations

import argparse
import pytest

from astrid.core.cli.domain_product import run_product_family
from astrid.sdk.contracts import DomainResult


class _RecordingBackfillClient:
    """Minimal recording fake: only the backfill service method is used."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    class _Timelines:
        def __init__(self, owner: "_RecordingBackfillClient") -> None:
            self._owner = owner

        def backfill(
            self,
            project: str,
            *,
            timeline: str | None = None,
            from_supabase_export: str | None = None,
            dry_run: bool = False,
            run_ts: str | None = None,
        ) -> DomainResult:
            self._owner.calls.append(
                (
                    "timelines.backfill",
                    {
                        "project": project,
                        "timeline": timeline,
                        "from_supabase_export": from_supabase_export,
                        "dry_run": dry_run,
                        "run_ts": run_ts,
                    },
                )
            )
            return DomainResult.success(
                {
                    "project": project,
                    "dry_run": dry_run,
                    "run_ts": run_ts or "",
                    "timelines": {},
                }
            )

    @property
    def timelines(self) -> "_RecordingBackfillClient._Timelines":
        return self._Timelines(self)


def _run(*args: str) -> tuple[int, _RecordingBackfillClient]:
    client = _RecordingBackfillClient()
    code = run_product_family(
        "timelines", list(args), client=client
    )
    return code, client


def test_backfill_dispatch_default_source() -> None:
    code, client = _run("backfill", "--project", "demo")
    assert code == 0
    # H: the CLI now allocates the ACTIVE run_ts BEFORE the SDK call so a
    # SIGKILL mid-run leaves an id on stdout. The dispatched run_ts is the
    # freshly allocated "<epoch>-<32 hex>" (not None), and the SDK will not
    # allocate a second dir.
    assert len(client.calls) == 1
    assert client.calls[0][0] == "timelines.backfill"
    assert set(client.calls[0][1]) == {"project", "timeline", "from_supabase_export", "dry_run", "run_ts"}
    assert client.calls[0][1]["project"] == "demo"
    assert client.calls[0][1]["timeline"] is None
    assert client.calls[0][1]["from_supabase_export"] is None
    assert client.calls[0][1]["dry_run"] is False
    import re as _re

    dispatched = client.calls[0][1]["run_ts"] or ""
    assert _re.fullmatch(r"[0-9]+-[0-9a-f]{32}", dispatched)
    # filesystem artifact (the fake client does not have a real project).
    try:
        from pathlib import Path as _Path

        from astrid.core.foundation.project_paths import resolve_projects_root as _resolve
        from astrid.core.timeline.migration import checkpoint_path_for_run as _cp

        _cp_path = _cp("demo", root=_resolve(None), run_ts=dispatched)
        _run_dir = _cp_path.parent
        if _run_dir.is_dir():
            import shutil as _shutil

            _shutil.rmtree(_run_dir, ignore_errors=True)
            # Also clean demo/runs if empty
            try:
                (_run_dir.parent).rmdir()
            except Exception:
                pass
    except Exception:
        pass

def test_backfill_dispatch_timeline_ref() -> None:
    code, client = _run(
        "backfill", "--project", "demo", "--timeline", "01KYPVKMW5STB4W6FE05ED8242"
    )
    assert code == 0
    assert client.calls[0][1]["timeline"] == "01KYPVKMW5STB4W6FE05ED8242"


def test_backfill_dispatch_supabase_export() -> None:
    code, client = _run(
        "backfill",
        "--project",
        "demo",
        "--from",
        "supabase-export",
        "/tmp/export.jsonl",
    )
    assert code == 0
    assert client.calls[0][1]["from_supabase_export"] == "/tmp/export.jsonl"
    assert client.calls[0][1]["dry_run"] is False


def test_backfill_dispatch_dry_run() -> None:
    code, client = _run("backfill", "--project", "demo", "--dry-run", "--json")
    assert code == 0
    assert client.calls[0][1]["dry_run"] is True


def test_backfill_dispatch_run_ts_resume_flag() -> None:
    """P3#2: the CLI accepts ``--run-ts`` and passes it through as the
    explicit resume id — an interrupted run is resumable verbatim."""
    code, client = _run(
        "backfill",
        "--project",
        "demo",
        "--run-ts",
        "1750000000-0123456789abcdef0123456789abcdef",
    )
    assert code == 0
    assert client.calls[0][1]["run_ts"] == (
        "1750000000-0123456789abcdef0123456789abcdef"
    )
    assert client.calls[0][1]["timeline"] is None
    assert client.calls[0][1]["dry_run"] is False


def test_backfill_echoes_active_run_ts(capsys: pytest.CaptureFixture) -> None:
    """P3#2: the CLI echoes the ACTIVE run_ts from the SDK response so an
    interrupted fresh run can be resumed verbatim."""
    code, client = _run(
        "backfill",
        "--project",
        "demo",
        "--run-ts",
        "1750000000-0123456789abcdef0123456789abcdef",
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "backfill run_ts: 1750000000-0123456789abcdef0123456789abcdef" in out


def test_backfill_rejects_unknown_source() -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run("backfill", "--project", "demo", "--from", "local", "/tmp/x.jsonl")
    assert excinfo.value.code == 2  # argparse usage error


def test_backfill_requires_project() -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run("backfill")
    assert excinfo.value.code == 2


def test_backfill_help_names_cutover_and_legacy_distinction() -> None:
    from astrid.packs.timeline.cli import build_parser

    parser = build_parser(_RecordingBackfillClient())
    help_text = parser.format_help()
    assert "backfill" in help_text
    assert "SQLite-cutover" in help_text
    sub = parser._subparsers._group_actions[0]
    for action in sub.choices:
        if action == "backfill":
            subparser = sub.choices[action]
            sub_help = subparser.format_help()
            assert "--dry-run" in sub_help
            assert "supabase-export" in sub_help
            assert "--timeline" in sub_help
            assert "--run-ts" in sub_help  # P3#2: explicit resume id
            # The legacy verbs stay absent from this product parser.
            for legacy in ("migration", "push", "pull", "sync", "audit",
                           "erase", "repair"):
                assert legacy not in sub.choices


def test_seven_existing_verbs_still_parse() -> None:
    from astrid.packs.timeline.cli import build_parser

    parser = build_parser(_RecordingBackfillClient())
    sub = parser._subparsers._group_actions[0]
    assert set(sub.choices) == {
        "create",
        "list",
        "show",
        "save",
        "archive",
        "history",
        "diff",
        "backfill",
        "shots",
    }
    # Each pre-existing verb still parses with its required args.
    parser.parse_args(["show", "--project", "p", "ref"])
    parser.parse_args(["history", "--project", "p", "ref"])
    parser.parse_args(["diff", "--project", "p", "ref"])
