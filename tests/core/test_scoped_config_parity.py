"""Parity oracle for scoped-config theme resolution.

Captures expected outputs of ``resolve_style_scope`` as checked-in golden
data.  When ``ASTRID_REGENERATE_GOLDEN=1`` is set in the environment, the
test regenerates the golden dictionary from the current production resolver
and writes it back to this file — otherwise it asserts the resolver still
produces the same results.

This replaces the S0 spike-based parity test
(``test_spike_scoped_config_parity.py``) deleted at T12.  The spike itself
(``astrid.core._spike/``) is also deleted at T12 per RFC §3.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from astrid.core.contracts.scoped_config import ScopeRequest
from astrid.core.env_vars import HYPE_ACTIVE_THEME
from astrid.core.theme import resolve_themes_root
from astrid.core.theme.scope import resolve_style_scope

# ---------------------------------------------------------------------------
# Checked-in golden — regenerated when ASTRID_REGENERATE_GOLDEN=1
# ---------------------------------------------------------------------------
# Each key is a test-case name.  Values are {"input": ..., "expected": ...}
# where ``expected`` is either ``null`` or a relative path from THEMES_ROOT
# (e.g. ``"banodoco-default"`` meaning ``<THEMES_ROOT>/banodoco-default``).

GOLDEN: dict[str, dict[str, Any]] = {
    "explicit_theme_name": {
        "input": {"explicit": {"theme": "banodoco-default"}},
        "expected": "banodoco-default",
    },
    "all_none": {
        "input": {},
        "expected": None,
    },
    "explicit_none_falls_through_to_env": {
        "input": {
            "explicit": None,
            "env": {"HYPE_ACTIVE_THEME": "banodoco-default"},
        },
        "expected": "banodoco-default",
    },
    "explicit_without_theme_key_falls_through": {
        "input": {
            "explicit": {"other": "val"},
            "env": {"HYPE_ACTIVE_THEME": "banodoco-default"},
        },
        "expected": "banodoco-default",
    },
    "explicit_theme_none_falls_through": {
        "input": {
            "explicit": {"theme": None},
            "env": {"HYPE_ACTIVE_THEME": "banodoco-default"},
        },
        "expected": "banodoco-default",
    },
    "env_wins_over_project": {
        "input": {
            "env": {"HYPE_ACTIVE_THEME": "banodoco-default"},
            "project_slug": "demo",
        },
        "expected": "banodoco-default",
    },
    "project_slug_resolves": {
        "input": {"project_slug": "demo"},
        "expected": "banodoco-default",
    },
    "project_slug_none_theme": {
        "input": {"project_slug": "no-theme-project"},
        "expected": None,
    },
    "env_empty_falls_through": {
        "input": {
            "env": {"HYPE_ACTIVE_THEME": ""},
            "project_slug": "demo",
        },
        "expected": "banodoco-default",
    },
    "env_none_falls_through": {
        "input": {
            "env": None,
            "project_slug": "demo",
        },
        "expected": "banodoco-default",
    },
}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _themes_root() -> Path:
    """Return the resolved themes root directory."""
    return resolve_themes_root()


def _resolve_golden(expected: str | None) -> Path | None:
    """Resolve a golden expected value to an absolute path (or None)."""
    if expected is None:
        return None
    return (_themes_root() / expected).resolve()


# ---------------------------------------------------------------------------
# Regeneration gate
# ---------------------------------------------------------------------------

_GOLDEN_MARKER_BEGIN = "# --- GOLDEN BEGIN ---"
_GOLDEN_MARKER_END = "# --- GOLDEN END ---"


def _regenerate_golden() -> None:
    """Recompute GOLDEN from the live resolver and write this file back."""
    # Build the new golden dict.
    new_golden: dict[str, dict[str, Any]] = {}
    for case_name, case in GOLDEN.items():
        inp = case["input"]
        explicit = inp.get("explicit")
        env = inp.get("env")
        project_slug = inp.get("project_slug")

        scope_request = ScopeRequest(
            explicit=explicit,
            env=env,
            project_slug=project_slug,
        )

        # Patch get_project_theme for project-bound cases.
        patches: list[Any] = []
        if project_slug is not None:
            if project_slug == "no-theme-project":
                p = mock.patch(
                    "astrid.core.project.project.get_project_theme",
                    return_value=None,
                )
            else:
                p = mock.patch(
                    "astrid.core.project.project.get_project_theme",
                    return_value="banodoco-default",
                )
            patches.append(p)
            p.start()

        try:
            result = resolve_style_scope(scope_request)
            if result.theme_dir is None:
                expected = None
            else:
                # Store path relative to themes root.
                try:
                    expected = str(result.theme_dir.relative_to(_themes_root()))
                except ValueError:
                    expected = str(result.theme_dir)
        finally:
            for p in reversed(patches):
                p.stop()

        new_golden[case_name] = {"input": inp, "expected": expected}

    # Write back to this file.
    this_file = Path(__file__).resolve()
    lines = this_file.read_text().splitlines(keepends=True)

    begin_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        if _GOLDEN_MARKER_BEGIN in line:
            begin_idx = i
        if _GOLDEN_MARKER_END in line:
            end_idx = i
            break

    if begin_idx is None or end_idx is None:
        raise RuntimeError("Golden markers not found in this file")

    # Format the golden block as pretty Python.
    golden_lines = ["GOLDEN: dict[str, dict[str, Any]] = "]
    golden_lines.append(json.dumps(new_golden, indent=4).replace("true", "True").replace("false", "False").replace("null", "None"))
    golden_lines.append("\n")

    new_lines = (
        lines[: begin_idx + 1]
        + [f"{l}\n" if not l.endswith("\n") else l for l in golden_lines]
        + lines[end_idx:]
    )

    this_file.write_text("".join(new_lines))
    print(f"Golden regenerated: {len(new_golden)} test cases written to {this_file}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_env_hype_active_theme():
    """Remove HYPE_ACTIVE_THEME from os.environ so tests don't leak."""
    old = os.environ.pop(HYPE_ACTIVE_THEME, None)
    yield
    if old is not None:
        os.environ[HYPE_ACTIVE_THEME] = old


@pytest.mark.parametrize("case_name", sorted(GOLDEN.keys()))
def test_golden_parity(case_name: str) -> None:
    """Each golden case: production resolver matches the checked-in expected value."""
    case = GOLDEN[case_name]
    inp = case["input"]
    golden_expected = case["expected"]

    explicit = inp.get("explicit")
    env = inp.get("env")
    project_slug = inp.get("project_slug")

    scope_request = ScopeRequest(
        explicit=explicit,
        env=env,
        project_slug=project_slug,
    )

    patches: list[Any] = []
    if project_slug is not None:
        if project_slug == "no-theme-project":
            p = mock.patch(
                "astrid.core.project.project.get_project_theme",
                return_value=None,
            )
        else:
            p = mock.patch(
                "astrid.core.project.project.get_project_theme",
                return_value="banodoco-default",
            )
        patches.append(p)
        p.start()

    try:
        result = resolve_style_scope(scope_request)
        actual = result.theme_dir
    finally:
        for p in reversed(patches):
            p.stop()

    expected_path = _resolve_golden(golden_expected)

    if expected_path is None:
        assert actual is None, (
            f"[{case_name}] Expected None, got {actual!r}"
        )
    else:
        assert actual is not None, (
            f"[{case_name}] Expected {expected_path!r}, got None"
        )
        assert actual == expected_path, (
            f"[{case_name}] Expected {expected_path!r}, got {actual!r}"
        )


# ---------------------------------------------------------------------------
# Regeneration script (run directly, not via pytest)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if os.environ.get("ASTRID_REGENERATE_GOLDEN") == "1":
        _regenerate_golden()
    else:
        sys.exit(pytest.main([__file__, "-v"]))
