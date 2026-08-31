"""Stage1 regressions for the final canonical timeline authority cutover."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_timeline_has_no_parity_or_session_shim_modules() -> None:
    assert not (ROOT / "astrid/core/timeline/validators/_parity.py").exists()
    assert not (ROOT / "astrid/core/timeline/_shared.py").exists()

    source_files = tuple((ROOT / "astrid/core/timeline").rglob("*.py"))
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_files)
    assert "ASTRID_TIMELINE_TYPECHECK" not in source
    assert "_effect_ids" not in source
    assert "_resolve_optional_session" not in source
    assert "_require_session" not in source


def test_timeline_validation_uses_canonical_type_resolver() -> None:
    timeline_source = (
        ROOT / "astrid/core/timeline/validators/timeline.py"
    ).read_text(encoding="utf-8")
    composer_source = (
        ROOT / "astrid/core/timeline/banodoco_composer.py"
    ).read_text(encoding="utf-8")
    pool_source = (
        ROOT / "astrid/core/timeline/validators/pool.py"
    ).read_text(encoding="utf-8")
    for source in (timeline_source, composer_source, pool_source):
        assert "is_visual_clip_element" in source
        assert "validators._parity" not in source


def test_projects_selection_help_does_not_claim_cwd_authority(capsys: pytest.CaptureFixture[str]) -> None:
    from astrid.core.cli.domain_projects import build_parser

    parser = build_parser(None)
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["select", "demo", "--help"])
    assert exc_info.value.code == 0
    select_help = capsys.readouterr().out
    assert "--cwd" not in select_help
    assert "ASTRID_PROJECTS_ROOT" not in select_help

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["current", "--help"])
    assert exc_info.value.code == 0
    current_help = capsys.readouterr().out
    assert "--cwd" not in current_help
    assert "ASTRID_PROJECTS_ROOT" not in current_help


def test_architecture_docs_describe_ephemeral_audit() -> None:
    for relative in ("docs/architecture/repo-shape.md", "docs/reference/architecture.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "Run-local provenance ledger, graph, and HTML report" not in text
        assert "ephemeral" in text.lower()
