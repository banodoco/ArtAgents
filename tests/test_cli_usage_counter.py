"""Focused tests for the B1b CLI usage counter hook in gateway dispatch.

The counter lives at the single choke point ``astrid/core/gateway/dispatch.py:_dispatch``
(records one JSON line per invocation, before handler execution). These tests prove:

1. invoking dispatch writes exactly one usage line;
2. ``ASTRID_USAGE_LOG`` is honored (and the ``~/.astrid/cli-usage.jsonl`` default);
3. a logging failure never breaks dispatch.

Convention follows the gateway dispatch tests (``tests/test_pipeline_dispatch_aliases.py``,
``tests/v10/test_domain_cli_*.py``): direct import of ``astrid.core.gateway.dispatch`` and
monkeypatched handler tables so the parser path runs for real with no SDK side effects.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from astrid.core.gateway import dispatch as dispatch_mod


def _stub_dispatch(monkeypatch: pytest.MonkeyPatch, calls: list[list[str]]) -> None:
    """Replace the handler table with a recording stub that returns 0."""

    def handler(tail: list[str]) -> int:
        calls.append(tail)
        return 0

    monkeypatch.setattr(dispatch_mod, "_TOP_LEVEL_HANDLERS", {"projects": handler})


def test_dispatch_records_exactly_one_usage_line(tmp_path, monkeypatch) -> None:
    """One dispatch invocation -> exactly one JSON line with ts/day/family."""
    calls: list[list[str]] = []
    _stub_dispatch(monkeypatch, calls)
    log = tmp_path / "usage.jsonl"
    monkeypatch.setenv("ASTRID_USAGE_LOG", str(log))

    rc = dispatch_mod._dispatch(["projects", "list"])

    assert rc == 0
    assert calls == [["list"]], "handler still ran after the counter"
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, f"expected exactly one usage line, got {len(lines)}"
    record = json.loads(lines[0])
    assert set(record) == {"ts", "day", "family"}
    assert record["family"] == "projects"
    assert record["day"] == datetime.now(timezone.utc).date().isoformat()
    # ts is ISO-8601 and parseable
    parsed_ts = datetime.fromisoformat(record["ts"])
    assert parsed_ts.tzinfo is not None


def test_usage_log_honors_env_and_default_fallback(tmp_path, monkeypatch) -> None:
    """ASTRID_USAGE_LOG wins; unset -> $HOME/.astrid/cli-usage.jsonl."""
    calls: list[list[str]] = []
    _stub_dispatch(monkeypatch, calls)

    custom_log = tmp_path / "custom" / "usage.jsonl"
    monkeypatch.setenv("ASTRID_USAGE_LOG", str(custom_log))
    assert dispatch_mod._dispatch(["projects"]) == 0
    assert custom_log.exists()
    assert len(custom_log.read_text(encoding="utf-8").splitlines()) == 1

    # Unset env -> default under $HOME.
    monkeypatch.delenv("ASTRID_USAGE_LOG")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert dispatch_mod._dispatch(["projects", "list"]) == 0
    default_log = tmp_path / "home" / ".astrid" / "cli-usage.jsonl"
    assert default_log.exists()
    assert len(default_log.read_text(encoding="utf-8").splitlines()) == 1


def test_usage_log_failure_does_not_break_dispatch(tmp_path, monkeypatch) -> None:
    """A write failure (parent path is a file -> OSError) is swallowed."""
    calls: list[list[str]] = []
    _stub_dispatch(monkeypatch, calls)

    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("ASTRID_USAGE_LOG", str(blocker / "usage.jsonl"))

    rc = dispatch_mod._dispatch(["projects", "list"])

    assert rc == 0
    assert calls == [["list"]], "handler must run even when logging fails"
