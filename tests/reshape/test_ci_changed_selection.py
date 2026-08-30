"""Step 7c (Phase 3): Verify the --changed test-selection heuristic.

Simulates a diff touching a nested module with a directly name-mapped test
file (astrid/core/contracts/capability_schema.py → tests/test_capability_schema.py,
Rule 3a) and asserts the selection INCLUDES the mapped test and EXCLUDES a
clearly unrelated file (tests/timeline/test_model.py).

Uses a mock git wrapper so the test is fast and deterministic — no real
git history manipulation is needed.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_SCRIPT = _REPO_ROOT / "scripts" / "reshape" / "run_ci_checks.sh"

# The name-mapped pair: changing astrid/core/contracts/capability_schema.py should
# select tests/test_capability_schema.py (Rule 3a in the heuristic — direct
# test_<mod>.py match for nested modules).
_CHANGED_MODULE = "astrid/core/contracts/capability_schema.py"
_EXPECTED_TEST = "tests/test_capability_schema.py"
_UNRELATED_TEST = "tests/timeline/test_model.py"
_LOCAL_FONT_FIXTURE = "tests/fixtures/remotion-local-font-probe.json"
_LOCAL_FONT_TEST = "tests/test_remotion_local_fonts.py"


def _create_mock_git(
    tmp_path: Path, changed_paths: tuple[str, ...] = (_CHANGED_MODULE,)
) -> Path:
    """Create a mock ``git`` wrapper that intercepts ``diff --name-only``
    and forwards everything else to the real git.

    The mock returns *changed_paths* so the --changed heuristic can be tested
    without mutating the repository's real history.
    """
    mock_git = tmp_path / "git"
    changed_output = "\n".join(
        f'        printf \'%s\\n\' "{path}"' for path in changed_paths
    )
    mock_git.write_text(
        f"""#!/bin/bash
# Mock git: intercept diff --name-only, forward everything else.
    for arg in "$@"; do
    if [ "$arg" = "--name-only" ]; then
{changed_output}
        exit 0
    fi
done
exec /usr/bin/git "$@"
"""
    )
    mock_git.chmod(mock_git.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return mock_git


def test_ci_changed_selection_includes_mapped_test(tmp_path: Path) -> None:
    """Run --changed with a mock git diff; verify selection heuristic."""

    # ── Verify the source files actually exist ─────────────────────────
    assert (_REPO_ROOT / _CHANGED_MODULE).is_file(), (
        f"Changed module {_CHANGED_MODULE} does not exist — "
        f"the --changed heuristic requires [ -f ] to pass"
    )
    assert (_REPO_ROOT / _EXPECTED_TEST).is_file(), (
        f"Expected test {_EXPECTED_TEST} does not exist — "
        f"name-mapping cannot select a missing file"
    )
    assert (_REPO_ROOT / _UNRELATED_TEST).is_file(), (
        f"Unrelated test {_UNRELATED_TEST} does not exist — "
        f"cannot verify exclusion"
    )

    # ── Build environment with mock git on PATH ────────────────────────
    _create_mock_git(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + ":" + env["PATH"]

    # ── Run CI script in --changed mode (non-JSON, human output) ──────
    result = subprocess.run(
        ["bash", str(_CI_SCRIPT), "--changed"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
        timeout=180,
    )

    combined_output = result.stdout + "\n" + result.stderr

    # ── The expected test MUST be selected ─────────────────────────────
    assert _EXPECTED_TEST in combined_output, (
        f"Expected --changed to select {_EXPECTED_TEST} "
        f"(name-mapped from {_CHANGED_MODULE}), "
        f"but it was not found in output.\n\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # ── The unrelated test MUST NOT be selected ────────────────────────
    # Parse the "Selected tests:" line to get the actual selection list.
    selected_line = ""
    for line in combined_output.splitlines():
        if "Selected tests:" in line:
            selected_line = line
            break

    if selected_line:
        assert _UNRELATED_TEST not in selected_line, (
            f"--changed selected unrelated test {_UNRELATED_TEST}.\n"
            f"Selected tests: {selected_line}"
        )
    else:
        # If we can't find the "Selected tests:" line (e.g., the output
        # format changed), fall back to checking the full output.
        # The unrelated file should not appear as a pytest target.
        assert _UNRELATED_TEST not in combined_output, (
            f"--changed appears to have selected unrelated test "
            f"{_UNRELATED_TEST}.\n\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}"
        )

    # ── The test should actually run (non-empty selection) ─────────────
    # If the selection fell back to TARGETED_BLOCKING_TESTS we'd see a
    # fallback message, not the expected test.
    assert "falling back to TARGETED_BLOCKING_TESTS" not in combined_output, (
        f"--changed selection was empty and fell back to "
        f"TARGETED_BLOCKING_TESTS. Mock git diff may have failed.\n\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def test_ci_changed_selection_excludes_unrelated_when_only_structure_changes(
    tmp_path: Path,
) -> None:
    """Same mock-diff scenario with tighter exclusion assertion.

    When ONLY astrid/core/contracts/capability_schema.py changes, the selection
    should NOT include any test file from tests/timeline/ (the
    directory-fallback would need a changed file under astrid/timeline/
    to trigger that).
    """
    _create_mock_git(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + ":" + env["PATH"]

    result = subprocess.run(
        ["bash", str(_CI_SCRIPT), "--changed"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
        timeout=180,
    )

    combined_output = result.stdout + "\n" + result.stderr

    # The expected file must be in the output.
    assert _EXPECTED_TEST in combined_output, (
        f"Expected {_EXPECTED_TEST} in selection output"
    )

    # Parse "Selected tests:" line.
    selected_line = ""
    for line in combined_output.splitlines():
        if "Selected tests:" in line:
            selected_line = line
            break

    if selected_line:
        # No test from tests/timeline/ should appear in the selection.
        timeline_tests = [
            t.strip()
            for t in selected_line.replace("Selected tests:", "").split()
            if t.strip()
        ]
        timeline_selected = [t for t in timeline_tests if "tests/timeline/" in t]
        assert len(timeline_selected) == 0, (
            f"--changed unexpectedly selected timeline tests: {timeline_selected}\n"
            f"Full selection: {selected_line}"
        )


def test_ci_changed_json_fixture_maps_to_owner_without_pytest_json_target(
    tmp_path: Path,
) -> None:
    """A changed fixture selects its owning Python test, never the JSON file."""
    _create_mock_git(tmp_path, (_LOCAL_FONT_FIXTURE, _LOCAL_FONT_TEST))
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + ":" + env["PATH"]

    result = subprocess.run(
        ["bash", str(_CI_SCRIPT), "--changed", "--json"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
        timeout=180,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["lanes"]["changed"]["passed"] == 4
    assert _LOCAL_FONT_TEST in result.stderr
    assert _LOCAL_FONT_FIXTURE not in result.stderr


def test_ci_changed_without_tests_falls_back_without_passing_data_to_pytest(
    tmp_path: Path,
) -> None:
    """Non-test-only changes keep the blocking fallback and select no data files."""
    _create_mock_git(tmp_path, ("docs/local-runtime-note.md",))
    fake_python = tmp_path / "python"
    real_python = sys.executable
    fake_python.write_text(
        f"""#!/bin/bash
if [ "$1" = "-m" ] && [ "$2" = "pytest" ]; then
  printf 'FAKE_PYTEST %s\\n' "$*"
  exit 0
fi
exec "{real_python}" "$@"
"""
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + ":" + env["PATH"]
    env["PYTHON_BIN"] = str(fake_python)

    result = subprocess.run(
        ["bash", str(_CI_SCRIPT), "--changed"],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
        timeout=180,
    )
    combined = result.stdout + "\n" + result.stderr

    assert result.returncode == 0, combined
    assert "falling back to TARGETED_BLOCKING_TESTS" in combined
    assert "FAKE_PYTEST" in combined
    assert _LOCAL_FONT_FIXTURE not in combined
    assert "docs/local-runtime-note.md" not in combined
