"""Runtime-backed timeline selection tests."""

from __future__ import annotations

from pathlib import Path

from astrid.packs.rendering.executors.timeline_visualize.select import (
    select_from_manifest,
    select_kernel_timelines,
)

PROJECT_ID = "project-1"
UUID_A = "11111111-2222-4333-8444-555555555555"
UUID_B = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
ULID_A = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
ULID_B = "01ARZ3NDEKTSV4RRFFQ69G5FB0"


class _Runtime:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def list_projects(self):
        return [[
                {
                    "project_id": PROJECT_ID,
                    "slug": "demo",
                    "metadata": {"default_timeline_id": UUID_B},
                }
            ], None]

    def list_timelines(self, project_id: str):
        assert project_id == PROJECT_ID
        return [self.rows, None]


def _row(timeline_id: str, ulid: str, slug: str, *, state: str | None = None) -> dict:
    row = {
        "timeline_id": timeline_id,
        "timeline_ulid": ulid,
        "slug": slug,
        "config": {"tracks": [], "clips": []},
        "registry": {"assets": {}},
        "config_version": 3,
        "head_event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        "head_hash": "a" * 64,
        "head_created_at": "2026-01-01T00:00:00+00:00",
    }
    if state is not None:
        row["state"] = state
    return row


def test_runtime_selection_reads_rows_and_honors_default_and_slug() -> None:
    runtime = _Runtime([_row(UUID_A, ULID_A, "main"), _row(UUID_B, ULID_B, "alt")])

    selected, diagnostics = select_kernel_timelines(
        Path("/untrusted/project-tree"), project_slug="demo", runtime_client=runtime
    )
    assert diagnostics == []
    assert [item.slug for item in selected] == ["main", "alt"]

    selected, diagnostics = select_kernel_timelines(
        None, project_slug="demo", default=True, runtime_client=runtime
    )
    assert diagnostics == []
    assert [item.slug for item in selected] == ["alt"]

    selected, diagnostics = select_kernel_timelines(
        None, project_slug="demo", slug="main", runtime_client=runtime
    )
    assert diagnostics == []
    assert selected[0].timeline_id == UUID_A


def test_runtime_selection_excludes_archived_rows() -> None:
    runtime = _Runtime(
        [_row(UUID_A, ULID_A, "main"), _row(UUID_B, ULID_B, "gone", state="archived")]
    )
    selected, diagnostics = select_kernel_timelines(
        None, project_slug="demo", all=True, runtime_client=runtime
    )
    assert diagnostics == []
    assert [item.timeline_ulid for item in selected] == [ULID_A]


def test_runtime_selection_requires_generated_page_pairs() -> None:
    class BareListRuntime(_Runtime):
        def list_projects(self):
            return [{"project_id": PROJECT_ID, "slug": "demo"}]

    selected, diagnostics = select_kernel_timelines(
        None, project_slug="demo", runtime_client=BareListRuntime([])
    )
    assert selected == []
    assert diagnostics == ["workspace project listing returned an invalid page"]


def test_frozen_manifest_selection_is_detached_from_project_tree() -> None:
    identity = {
        "stable_id": "TL01",
        "qualified_ref": "TL01",
        "uuid": UUID_A,
        "ulid": ULID_A,
        "slug": "main",
    }
    selected = select_from_manifest(
        {"schema_version": 1, "kind": "timeline_visualize", "timeline": identity}
    )
    assert selected is not None
    assert selected.timeline_dir is None
    assert selected.is_frozen_manifest is True
