"""Negative coverage for the retired thread and local-selection authorities."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from astrid.core.contracts.identifiers import generate_run_id, is_ulid
from astrid.core.project.guidance import selected_project

ROOT = Path(__file__).resolve().parents[2]


def test_retired_thread_package_and_preferences_are_not_importable() -> None:
    assert importlib.util.find_spec("astrid.core.threads") is None
    assert importlib.util.find_spec("astrid.core.preferences") is None
    # The empty session package is retired as a whole.  Asking importlib for
    # a child of a missing parent raises ModuleNotFoundError, so assert the
    # package boundary directly.
    assert importlib.util.find_spec("astrid.core.session") is None


def test_lineage_ids_live_in_neutral_contracts() -> None:
    value = generate_run_id()
    assert is_ulid(value)


def test_guidance_ignores_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRID_PROJECT_SLUG", "ambient-project")
    assert selected_project(None) == (None, "missing")


@pytest.mark.parametrize(
    "relative",
    (
        "astrid/packs/iteration/executors/experiment_import/run.py",
        "astrid/packs/iteration/executors/experiment_prepare/run.py",
    ),
)
def test_iteration_does_not_write_run_sidecars(relative: str) -> None:
    source = (ROOT / relative).read_text(encoding="utf-8")
    assert '"run.json"' not in source
    assert ".astrid/threads" not in source
