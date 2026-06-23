"""Startup smoke tests for Arnold host workflows.

These tests invoke ``astrid start --engine arnold`` for the event-talks
and thumbnail-maker compiled batch workflows against demo projects.  They
assert command success and validate the emitted ``pipeline.json`` and
``arnold_run.json`` outputs without requiring full runtime execution
parity.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from astrid.core.project import create_project
from astrid.core.project.current_run import read_current_run


def _clear_host_modules() -> None:
    for name in tuple(sys.modules):
        if name.startswith("astrid.core.integrations.arnold.host") or name.startswith(
            "astrid.core.integrations.arnold.session"
        ):
            sys.modules.pop(name, None)
    sys.modules.pop("astrid.core.integrations.arnold", None)


# Re-use the fake pipeline fixture from test_arnold_host_cli_start.
# We import the helper from its canonical location so we stay DRY.
from tests.core.integrations.test_arnold_host_cli_start import (  # noqa: E402
    _install_fake_pipeline,
)


@pytest.fixture(autouse=True)
def _clean_modules_fixture() -> None:
    _clear_host_modules()
    yield
    _clear_host_modules()


# ── Event Talks ────────────────────────────────────────────────────────────────


def test_arnold_start_event_talks_writes_valid_pipeline_and_run_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Smoke: ``astrid start event-talks --engine arnold`` succeeds and
    produces a well-formed ``pipeline.json`` and ``arnold_run.json``."""
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    create_project("demo")
    _install_fake_pipeline(monkeypatch)
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_start(
        [
            "event-talks",
            "--project",
            "demo",
            "--name",
            "run-ev-smoke",
            "--state",
            "{}",
        ]
    )

    run_root = tmp_path / "projects" / "demo" / "runs" / "run-ev-smoke"
    assert rc == 0
    assert read_current_run("demo") == "run-ev-smoke"

    # ── arnold_run.json ───────────────────────────────────────────────────
    arnold_run = json.loads((run_root / "arnold_run.json").read_text(encoding="utf-8"))
    assert arnold_run["engine"] == "arnold"
    assert arnold_run["workflow_id"] == "video_editing.event_talks"
    assert arnold_run["run_id"] == "run-ev-smoke"
    assert arnold_run["status"] == "prepared"
    assert isinstance(arnold_run.get("plan_hash"), str) and arnold_run["plan_hash"]

    # ── pipeline.json ─────────────────────────────────────────────────────
    pipeline = json.loads((run_root / "pipeline.json").read_text(encoding="utf-8"))
    assert pipeline["entry_stage_id"] == "ados-sunday-template"
    stage_ids = [s["stage_id"] for s in pipeline["stages"]]
    assert stage_ids == [
        "ados-sunday-template",
        "search-transcript",
        "find-holding-screens",
        "render",
        "halt",
    ]
    # Edges carry correct target and label.  source may be None here
    # because the fake Arnold module follows the sourceless real-Arnold
    # edge convention; pipeline.json faithfully records whatever is
    # available.  Full source fidelity requires a real Arnold runtime.
    edge_targets = [(e["target"], e["label"]) for e in pipeline["edges"]]
    assert edge_targets == [
        ("search-transcript", "next"),
        ("find-holding-screens", "next"),
        ("render", "next"),
        ("halt", "next"),
    ]


# ── Thumbnail Maker ───────────────────────────────────────────────────────────


def test_arnold_start_thumbnail_maker_writes_valid_pipeline_and_run_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Smoke: ``astrid start thumbnail-maker --engine arnold`` succeeds and
    produces a well-formed ``pipeline.json`` and ``arnold_run.json``."""
    monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(tmp_path / "projects"))
    create_project("demo")
    _install_fake_pipeline(monkeypatch)
    cli = importlib.import_module("astrid.core.integrations.arnold.host.cli")

    rc = cli.cmd_start(
        [
            "thumbnail-maker",
            "--project",
            "demo",
            "--name",
            "run-tm-smoke",
            "--state",
            "{}",
        ]
    )

    run_root = tmp_path / "projects" / "demo" / "runs" / "run-tm-smoke"
    assert rc == 0
    assert read_current_run("demo") == "run-tm-smoke"

    # ── arnold_run.json ───────────────────────────────────────────────────
    arnold_run = json.loads((run_root / "arnold_run.json").read_text(encoding="utf-8"))
    assert arnold_run["engine"] == "arnold"
    assert arnold_run["workflow_id"] == "video_editing.thumbnail_maker"
    assert arnold_run["run_id"] == "run-tm-smoke"
    assert arnold_run["status"] == "prepared"
    assert isinstance(arnold_run.get("plan_hash"), str) and arnold_run["plan_hash"]

    # ── pipeline.json ─────────────────────────────────────────────────────
    pipeline = json.loads((run_root / "pipeline.json").read_text(encoding="utf-8"))
    assert pipeline["entry_stage_id"] == "resolve-video"
    stage_ids = [s["stage_id"] for s in pipeline["stages"]]
    assert stage_ids == [
        "resolve-video",
        "plan-evidence",
        "discover-video-evidence",
        "build-reference-pack",
        "generate-thumbnails",
        "halt",
    ]
    # Edges carry correct target and label.  source may be None here
    # because the fake Arnold module follows the sourceless real-Arnold
    # edge convention; pipeline.json faithfully records whatever is
    # available.  Full source fidelity requires a real Arnold runtime.
    edge_targets = [(e["target"], e["label"]) for e in pipeline["edges"]]
    assert edge_targets == [
        ("plan-evidence", "next"),
        ("discover-video-evidence", "next"),
        ("build-reference-pack", "next"),
        ("generate-thumbnails", "next"),
        ("halt", "next"),
    ]
