from __future__ import annotations

import json
import multiprocessing
from pathlib import Path
from uuid import UUID

import pytest

from astrid.core.timeline.crud import create_timeline, rename_timeline, show_timeline
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.eventlog.types import EventLogError, EventLogStaleVersionError
from astrid.core.timeline.events.schema import TimelineActor
from astrid.core.timeline.model import Display
from astrid.core.timeline.paths import (
    assembly_head_path,
    assembly_identity_path,
    load_display_json_with_repair,
    timeline_dir,
)


@pytest.fixture
def project_tree(tmp_projects_root: Path) -> Path:
    slug = "demo"
    pdir = tmp_projects_root / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "runs").mkdir()
    (pdir / "sources").mkdir()
    (pdir / "project.json").write_text(
        json.dumps(
            {
                "created_at": "2026-05-11T00:00:00Z",
                "name": slug,
                "schema_version": 1,
                "slug": slug,
                "updated_at": "2026-05-11T00:00:00Z",
                "default_timeline_id": None,
            }
        ),
        encoding="utf-8",
    )
    return tmp_projects_root


def test_local_fs_backend_appends_and_updates_head(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    backend = LocalFsBackend(
        timeline_id=identity["timeline_id"],
        timeline_home=timeline_dir("demo", ulid, root=project_tree),
    )

    event = backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": "primary", "new_slug": "primary-v2"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )

    assert event.kind == "timeline.renamed"
    assert event.prev_hash is None
    assert event.hash is not None
    assert backend.read_events()[-1].event_id == event.event_id
    head = backend.head()
    assert head.last_event_id == event.event_id
    assert head.last_hash == event.hash
    assert head.event_count == 1
    assert head.version == 1
    assert json.loads(assembly_head_path("demo", ulid, root=project_tree).read_text())["version"] == 1


def test_local_fs_backend_rebuilds_head_when_cache_is_missing_or_stale(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    event = backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": "primary", "new_slug": "primary-v2"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )

    head_path = assembly_head_path("demo", ulid, root=project_tree)
    head_path.unlink()
    rebuilt = backend.head()
    assert rebuilt.last_event_id == event.event_id
    assert rebuilt.version == 1

    head_path.write_text(
        json.dumps(
            {
                "timeline_id": identity["timeline_id"],
                "last_event_id": "stale",
                "last_hash": "stale",
                "event_count": 999,
                "version": 999,
            }
        ),
        encoding="utf-8",
    )
    still_cached = backend.head()
    assert still_cached.version == 999
    head_path.unlink()
    repaired = backend.head()
    assert repaired.last_event_id == event.event_id
    assert repaired.last_hash == event.hash


def test_local_fs_backend_bootstraps_legacy_with_imported_event(project_tree: Path) -> None:
    legacy_home = timeline_dir("demo", "01J00000000000000000000000", root=project_tree)
    legacy_home.mkdir(parents=True, exist_ok=True)
    (legacy_home / "assembly.json").write_text(
        json.dumps({"schema_version": 1, "assembly": {}}), encoding="utf-8"
    )
    (legacy_home / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )
    (legacy_home / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "legacy",
                "name": "Legacy",
                "is_default": False,
            }
        ),
        encoding="utf-8",
    )

    backend = LocalFsBackend(timeline_id="00000000-0000-0000-0000-000000000000", timeline_home=legacy_home)
    backend.append_event(
        "00000000-0000-0000-0000-000000000000",
        "timeline.renamed",
        {"old_slug": "legacy", "new_slug": "legacy-v2"},
        actor=TimelineActor(type="system", id="migration:test"),
    )

    events = backend.read_events()
    assert [event.kind for event in events] == ["timeline.imported", "timeline.renamed"]
    identity = json.loads((legacy_home / "assembly.identity.json").read_text(encoding="utf-8"))
    assert identity["provenance"] == "imported"
    assert str(UUID(identity["timeline_id"])) == identity["timeline_id"]


def test_local_fs_backend_verify_chain_detects_tampering(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": "primary", "new_slug": "after"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )

    lines = (home / "assembly.jsonl").read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"]["new_slug"] = "tampered"
    (home / "assembly.jsonl").write_text(json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n")

    verification = backend.verify_chain()
    assert verification.ok is False
    assert "hash mismatch" in (verification.error or "")


def test_local_fs_backend_rejects_append_after_deleted(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    backend = LocalFsBackend(
        timeline_id=identity["timeline_id"],
        timeline_home=timeline_dir("demo", ulid, root=project_tree),
    )
    backend.append_event(
        identity["timeline_id"],
        "timeline.deleted",
        {},
        actor=TimelineActor(type="system", id="cleanup:test"),
    )

    with pytest.raises(EventLogError, match="rejects appends"):
        backend.append_event(
            identity["timeline_id"],
            "timeline.renamed",
            {"old_slug": "primary", "new_slug": "after"},
            actor=TimelineActor(type="agent", id="codex:test"),
        )


def test_local_fs_backend_rejects_stale_expected_version_without_mutating_files(
    project_tree: Path,
) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": "primary", "new_slug": "primary-v2"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )

    before_log = (home / "assembly.jsonl").read_text(encoding="utf-8")
    before_head = assembly_head_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")

    with pytest.raises(EventLogStaleVersionError) as excinfo:
        backend.append_event(
            identity["timeline_id"],
            "timeline.renamed",
            {"old_slug": "primary-v2", "new_slug": "primary-v3"},
            actor=TimelineActor(type="agent", id="codex:test"),
            expected_version=0,
        )

    conflict = excinfo.value.conflict
    assert conflict.timeline_id == identity["timeline_id"]
    assert conflict.expected_version == 0
    assert conflict.current_version == 1
    assert conflict.last_event_kind == "timeline.renamed"
    assert conflict.last_event_id is not None
    assert conflict.last_event_summary is not None

    assert (home / "assembly.jsonl").read_text(encoding="utf-8") == before_log
    assert assembly_head_path("demo", ulid, root=project_tree).read_text(encoding="utf-8") == before_head
    assert backend.head().version == 1


def _append_in_process(timeline_id: str, home: str, index: int) -> None:
    backend = LocalFsBackend(timeline_id=timeline_id, timeline_home=home)
    backend.append_event(
        timeline_id,
        "timeline.renamed",
        {"old_slug": f"before-{index}", "new_slug": f"after-{index}"},
        actor=TimelineActor(type="agent", id=f"worker:{index}"),
    )


def test_local_fs_backend_serializes_concurrent_process_appends(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)

    ctx = multiprocessing.get_context("fork")
    procs = [
        ctx.Process(target=_append_in_process, args=(identity["timeline_id"], str(home), index))
        for index in range(4)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(5)
        assert proc.exitcode == 0

    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    events = backend.read_events()
    assert len(events) == 4
    assert backend.verify_chain().ok is True
    assert backend.head().event_count == 4


def test_local_fs_backend_serializes_concurrent_first_write_bootstrap(project_tree: Path) -> None:
    legacy_home = timeline_dir("demo", "01J00000000000000000000001", root=project_tree)
    legacy_home.mkdir(parents=True, exist_ok=True)
    (legacy_home / "assembly.json").write_text(
        json.dumps({"schema_version": 1, "assembly": {}}), encoding="utf-8"
    )
    (legacy_home / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "contributing_runs": [],
                "final_outputs": [],
                "tombstoned_at": None,
            }
        ),
        encoding="utf-8",
    )
    (legacy_home / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "legacy",
                "name": "Legacy",
                "is_default": False,
            }
        ),
        encoding="utf-8",
    )

    ctx = multiprocessing.get_context("fork")
    procs = [
        ctx.Process(
            target=_append_in_process,
            args=("00000000-0000-0000-0000-000000000000", str(legacy_home), index),
        )
        for index in range(2)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(5)
        assert proc.exitcode == 0

    backend = LocalFsBackend(
        timeline_id="00000000-0000-0000-0000-000000000000",
        timeline_home=legacy_home,
    )
    events = backend.read_events()
    assert [event.kind for event in events].count("timeline.imported") == 1
    assert [event.kind for event in events].count("timeline.renamed") == 2
    identity = json.loads((legacy_home / "assembly.identity.json").read_text(encoding="utf-8"))
    assert identity["provenance"] == "imported"


def test_show_timeline_repairs_missing_display_from_eventlog(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": "primary", "new_slug": "repaired"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )
    (home / "display.json").unlink()

    data = show_timeline("demo", "repaired", root=project_tree)
    assert data is not None
    assert data["display"].slug == "repaired"
    repaired = json.loads((home / "display.json").read_text(encoding="utf-8"))
    assert repaired["slug"] == "repaired"


def test_show_timeline_refuses_deleted_projection(project_tree: Path) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "timeline.deleted",
        {},
        actor=TimelineActor(type="system", id="cleanup:test"),
    )
    (home / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "primary",
                "name": "Primary",
                "is_default": False,
            }
        ),
        encoding="utf-8",
    )

    assert show_timeline("demo", "primary", root=project_tree) is None


def test_load_display_stays_fail_closed_when_eventlog_exists_without_identity(
    project_tree: Path,
) -> None:
    result = create_timeline("demo", "primary", root=project_tree)
    ulid = result["ulid"]
    home = timeline_dir("demo", ulid, root=project_tree)
    identity_path = assembly_identity_path("demo", ulid, root=project_tree)
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": "primary", "new_slug": "after"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )
    identity_path.unlink()

    assert load_display_json_with_repair(home) is None
    assert show_timeline("demo", "after", root=project_tree) is None


def test_next_read_repairs_display_after_post_append_projection_failure(
    project_tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_timeline("demo", "alpha", root=project_tree)
    original_write = Display.write
    state = {"calls": 0}

    def flaky_write(self: Display, path: str | Path) -> None:
        state["calls"] += 1
        if state["calls"] == 1:
            raise OSError("simulated display write failure")
        original_write(self, path)

    monkeypatch.setattr(Display, "write", flaky_write)

    with pytest.raises(OSError, match="simulated display write failure"):
        rename_timeline(
            "demo",
            "alpha",
            "beta",
            actor=TimelineActor(type="agent", id="codex:test"),
            root=project_tree,
        )

    repaired = show_timeline("demo", "beta", root=project_tree)
    assert repaired is not None
    assert repaired["display"].slug == "beta"
