"""Smoke tests for Fix A post-actor enforcement helpers.

Tests the two new functions added to runner.py:
  - _check_canonical_bypass
  - _reprompt_actor  (not tested in smoke — requires a live agent)
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tests.agentic.runner import _check_canonical_bypass


# ---------------------------------------------------------------------------
# _check_canonical_bypass
# ---------------------------------------------------------------------------


def test_check_canonical_bypass_no_false_positive_on_read(tmp_path: Path) -> None:
    """File-read mentions ('📖 read ./astrid/packs/video_editing/orchestrators/hype/run.py')
    must NOT trigger bypass detection.  Only execution-context patterns
    (python/python3 prefix + module or path) should match."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "📖 read ./astrid/packs/video_editing/orchestrators/hype/run.py\n"
        "Checked astrid/packs/video_editing/orchestrators/hype/orchestrator.yaml\n"
        "Looking at astrid.packs.video_editing.orchestrators.hype.run module docs\n"
    )
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


def test_check_canonical_bypass_detects_execution_python3_m(tmp_path: Path) -> None:
    """Direct 'python3 -m astrid.packs.video_editing.orchestrators.hype.run' must trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "Starting...\n"
        "python3 -m astrid.packs.video_editing.orchestrators.hype.run --some-flag\n"
        "Done.\n"
    )
    result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert result is not None
    assert "python3 -m astrid.packs.video_editing.orchestrators.hype.run" in result


def test_check_canonical_bypass_detects_execution_python_path(tmp_path: Path) -> None:
    """'python /path/to/astrid/packs/video_editing/orchestrators/hype/run.py' must trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "python /home/user/astrid/packs/video_editing/orchestrators/hype/run.py --verbose\n"
    )
    result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert result is not None
    assert "python /home/user/astrid/packs/video_editing/orchestrators/hype/run.py" in result


def test_check_canonical_bypass_detects_execution_python3_space(tmp_path: Path) -> None:
    """'python3  ./astrid/packs/video_editing/orchestrators/hype/run.py' must trigger
    (path with leading ./ still matches /astrid/packs/ pattern)."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "python3  ./astrid/packs/video_editing/orchestrators/hype/run.py\n"
    )
    result = _check_canonical_bypass(stderr, scenario_cfg=None)
    assert result is not None
    assert "python3" in result


def test_check_canonical_bypass_no_filter_on_launcher(tmp_path: Path) -> None:
    """The hermes launcher itself uses python3 — but with
    launch_hermes_agent.py (not astrid/packs/...), so it must NOT trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text(
        "python3 launch_hermes_agent.py --model=deepseek:deepseek-v4-pro\n"
    )
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


def test_check_canonical_bypass_no_filter_on_plain_python(tmp_path: Path) -> None:
    """'python3 script.py' without astrid.packs must NOT trigger."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text("python3 my_script.py --help\n")
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None


def test_check_canonical_bypass_from_offset_skips_old_content(tmp_path: Path) -> None:
    """Re-check with from_offset past an old bypass + marker line
    must return None (only new content is scanned)."""
    stderr = tmp_path / "stderr.log"
    old_content = "python3 -m astrid.packs.video_editing.orchestrators.hype.run\n"
    marker = "--- REPROMPT: canonical CLI bypass detected ---\n"
    new_content = "astrid author run hype --check\n"  # canonical, no bypass
    stderr.write_text(old_content + marker + new_content)

    # from_offset past old_content + marker
    offset = len(old_content.encode("utf-8")) + len(marker.encode("utf-8"))
    result = _check_canonical_bypass(stderr, scenario_cfg=None, from_offset=offset)
    assert result is None


def test_check_canonical_bypass_from_offset_zero_finds_bypass(tmp_path: Path) -> None:
    """With from_offset=0, old bypass is scanned and detected."""
    stderr = tmp_path / "stderr.log"
    old_content = "python3 -m astrid.packs.video_editing.orchestrators.hype.run\n"
    marker = "--- REPROMPT: canonical CLI bypass detected ---\n"
    new_content = "astrid author run hype --check\n"
    stderr.write_text(old_content + marker + new_content)

    result = _check_canonical_bypass(stderr, scenario_cfg=None, from_offset=0)
    assert result is not None
    assert "python3 -m astrid.packs.video_editing" in result


def test_check_canonical_bypass_bypass_exempt(tmp_path: Path) -> None:
    """Scenario with bypass_exempt: true returns None regardless."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text("python3 -m astrid.packs.video_editing.orchestrators.hype.run\n")

    scenario_cfg = {"assessment": {"bypass_exempt": True}}
    assert _check_canonical_bypass(stderr, scenario_cfg=scenario_cfg) is None


def test_check_canonical_bypass_missing_file(tmp_path: Path) -> None:
    """Non-existent stderr returns None."""
    assert _check_canonical_bypass(tmp_path / "nope.log", scenario_cfg=None) is None


def test_check_canonical_bypass_empty_file(tmp_path: Path) -> None:
    """Empty stderr returns None."""
    stderr = tmp_path / "stderr.log"
    stderr.write_text("")
    assert _check_canonical_bypass(stderr, scenario_cfg=None) is None
