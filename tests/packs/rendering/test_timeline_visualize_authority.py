"""Authority-boundary checks for the managed visualization readers."""

from __future__ import annotations

import inspect
from pathlib import Path

from astrid.packs.rendering.executors.timeline_visualize import frozen, select


class _Runtime:
    def list_projects(self):
        return {"items": [{"project_id": "project-1", "slug": "demo", "metadata": {}}]}

    def list_timelines(self, project_id):
        assert project_id == "project-1"
        return {
            "items": [
                {
                    "timeline_id": "timeline-1",
                    "timeline_ulid": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
                    "slug": "main",
                    "name": "Main",
                    "version": 3,
                    "config": {"tracks": []},
                    "registry": {"assets": {}},
                    "head_event_id": "event-3",
                    "head_hash": "hash-3",
                    "updated_at": "2026-08-30T00:00:00Z",
                }
            ]
        }


def test_managed_selection_reads_generated_runtime_client():
    timelines, diagnostics = select.select_kernel_timelines(
        Path("/not-an-authority"), project_slug="demo", runtime_client=_Runtime(), default=True
    )

    assert diagnostics == []
    assert [item.slug for item in timelines] == ["main"]
    assert timelines[0].config_version == 3


def test_managed_visualization_readers_have_no_local_store_authority():
    select_source = inspect.getsource(select)
    frozen_source = inspect.getsource(frozen)
    for source in (select_source, frozen_source):
        assert "import sqlite3" not in source
        assert "astrid.core.kernel.read" not in source
        assert "astrid.core.store" not in source


def test_frozen_run_info_uses_generated_runtime_client(monkeypatch):
    class Runtime:
        def get_run(self, run_id):
            assert run_id == "run-1"
            return {"status": "completed", "capability": "rendering.timeline_visualize", "timeline_ids": ["timeline-1"]}

    monkeypatch.setattr(frozen, "_workspace_runtime_client", lambda: Runtime())
    assert frozen._kernel_frozen_run_info("demo", "run-1", Path("/unused")) == {
        "status": "completed",
        "capability": "rendering.timeline_visualize",
        "timeline_ids": ["timeline-1"],
    }
