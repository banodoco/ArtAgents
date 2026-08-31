from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from astrid.packs.rendering.executors.timeline_visualize import run as run_module


class _PagedRuntime:
    def __init__(self, pages: dict[str | None, tuple[list[Any], str | None]]) -> None:
        self.pages = pages
        self.calls: list[tuple[str, str | None, int]] = []

    def list_projects(self) -> list[Any]:
        return [[{"slug": "demo", "project_id": "project-1"}], None]

    def list_project_objects(
        self, project_id: str, *, cursor: str | None = None, limit: int = 50
    ) -> list[Any]:
        self.calls.append((project_id, cursor, limit))
        items, next_cursor = self.pages[cursor]
        return [items, next_cursor]


def _row(number: int) -> dict[str, str]:
    return {
        "object_id": f"object-{number:03d}",
        "content_hash": f"sha256:{number:064x}",
        "media_type": "image/png",
    }


def _patch_runtime(monkeypatch, runtime: _PagedRuntime) -> None:
    monkeypatch.setattr(
        "astrid.sdk.workspace_client.WorkspaceClient", lambda *_args: runtime
    )
    monkeypatch.setattr(
        "astrid.sdk.workspace_client.resolve_runtime_connection",
        lambda: ("http://runtime", "token"),
    )


def test_runtime_media_snapshot_paginates_beyond_first_page_and_deduplicates(
    monkeypatch,
) -> None:
    first_page = [_row(number) for number in range(50)]
    duplicate = dict(first_page[7])
    target = _row(50)
    runtime = _PagedRuntime(
        {
            None: (first_page, "cursor-1"),
            "cursor-1": ([duplicate, target], None),
        }
    )
    _patch_runtime(monkeypatch, runtime)

    snapshot = run_module._runtime_media_snapshot("demo")

    assert snapshot is not None
    assert len(snapshot) == 51
    assert snapshot[-1]["object_id"] == "object-050"
    assert runtime.calls == [
        ("project-1", None, 50),
        ("project-1", "cursor-1", 50),
    ]


def test_runtime_media_snapshot_rejects_page_larger_than_requested_limit(
    monkeypatch,
) -> None:
    runtime = _PagedRuntime(
        {
            None: ([_row(number) for number in range(51)], None),
        }
    )
    _patch_runtime(monkeypatch, runtime)

    assert run_module._runtime_media_snapshot("demo") is None
    assert runtime.calls == [("project-1", None, 50)]


def test_runtime_media_snapshot_rejects_mapping_page_without_explicit_cursor(
    monkeypatch,
) -> None:
    # An omitted cursor is not the terminal ``null`` marker.  In particular,
    # a full first page must not be accepted as a complete snapshot.
    first_page = [_row(number) for number in range(50)]

    class MissingCursorRuntime(_PagedRuntime):
        def list_project_objects(self, project_id: str, *, cursor=None, limit=50):
            self.calls.append((project_id, cursor, limit))
            return {"items": first_page}

    runtime = MissingCursorRuntime({})
    _patch_runtime(monkeypatch, runtime)

    assert run_module._runtime_media_snapshot("demo") is None
    assert runtime.calls == [("project-1", None, 50)]


def test_runtime_media_page_rejects_bare_item_lists() -> None:
    assert run_module._runtime_media_page([_row(1)]) is None
    assert run_module._runtime_media_page({"items": [_row(1)], "next_cursor": None}) is None


def test_runtime_media_snapshot_continues_after_empty_page(monkeypatch) -> None:
    runtime = _PagedRuntime(
        {
            None: ([], "cursor-empty"),
            "cursor-empty": ([_row(1)], None),
        }
    )
    _patch_runtime(monkeypatch, runtime)

    assert run_module._runtime_media_snapshot("demo") == [_row(1)]


def test_runtime_media_snapshot_fails_closed_on_repeated_cursor(monkeypatch) -> None:
    runtime = _PagedRuntime(
        {
            None: ([_row(1)], "cursor-1"),
            "cursor-1": ([_row(2)], "cursor-1"),
        }
    )
    _patch_runtime(monkeypatch, runtime)

    assert run_module._runtime_media_snapshot("demo") is None


@pytest.mark.parametrize("next_cursor", ["", "   ", "cursor\t1", "cursor\x001"])
def test_runtime_media_snapshot_rejects_malformed_next_cursor(
    monkeypatch, next_cursor: str
) -> None:
    runtime = _PagedRuntime(
        {
            None: ([_row(1)], next_cursor),
        }
    )
    _patch_runtime(monkeypatch, runtime)

    assert run_module._runtime_media_snapshot("demo") is None


def test_runtime_media_snapshot_fails_closed_on_project_mismatch(monkeypatch) -> None:
    runtime = _PagedRuntime(
        {
            None: ([{**_row(1), "project_id": "foreign-project"}], None),
        }
    )
    _patch_runtime(monkeypatch, runtime)

    assert run_module._runtime_media_snapshot("demo") is None


def test_runtime_media_snapshot_does_not_open_sqlite() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = """
import sys
from types import ModuleType

module = ModuleType("astrid.sdk.workspace_client")
class Client:
    def __init__(self, *_args): pass
    def list_projects(self): return [[{"slug": "demo", "project_id": "project-1"}], None]
    def list_project_objects(self, project_id, *, cursor=None, limit=50):
        return [[], None]
module.WorkspaceClient = Client
module.resolve_runtime_connection = lambda: ("http://runtime", "token")
module.page_pair = lambda value: (
    (value[0], value[1])
    if isinstance(value, list)
    and len(value) == 2
    and isinstance(value[0], list)
    and (value[1] is None or isinstance(value[1], str))
    else None
)
sys.modules[module.__name__] = module

from astrid.packs.rendering.executors.timeline_visualize.run import _runtime_media_snapshot
assert _runtime_media_snapshot("demo") == []
assert "sqlite3" not in sys.modules
"""
    env = dict(os.environ)
    env.pop("BANODOCO_RUNTIME_ENDPOINT", None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
