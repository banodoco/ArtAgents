"""Stage1 regressions for retired session state and truthful gateway help."""

from __future__ import annotations

from pathlib import Path

from astrid.core.gateway.help import _print_entrypoint_help, _product_help_text
from astrid.core.subprocess_env import build_child_subprocess_env


ROOT = Path(__file__).resolve().parents[2]


def test_retired_session_facade_and_user_paths_are_absent() -> None:
    assert not (ROOT / "astrid" / "core" / "session").exists()
    assert not (ROOT / "astrid" / "core" / "foundation" / "user_paths.py").exists()

    source_files = list((ROOT / "astrid").rglob("*.py"))
    residue = [
        str(path.relative_to(ROOT))
        for path in source_files
        if "ASTRID_SESSION_ID" in path.read_text(encoding="utf-8")
        or "astrid.core.session" in path.read_text(encoding="utf-8")
    ]
    assert residue == []


def test_child_environment_does_not_propagate_retired_session_id() -> None:
    child = build_child_subprocess_env(
        base={"PATH": "/usr/bin", "ASTRID_SESSION_ID": "retired"},
        parent={"ASTRID_SESSION_ID": "retired", "ASTRID_PROJECT_SLUG": "demo"},
    )
    assert "ASTRID_SESSION_ID" not in child
    assert child["ASTRID_PROJECT_SLUG"] == "demo"


def test_gateway_help_describes_live_backup_routes_and_json_truthfully(capsys) -> None:
    _print_entrypoint_help()
    entrypoint = capsys.readouterr().out
    product = _product_help_text()
    combined = entrypoint + product

    assert "backup emits its runtime result object" in combined
    assert "create,restore,export,tombstone,recover,purge" in combined
    assert "backup has no --json flag" not in combined
    assert "backup is unavailable until a runtime route exists" not in combined
