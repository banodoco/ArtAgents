from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

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


def test_local_fs_backend_rejects_legacy_bootstrap(project_tree: Path) -> None:
    legacy_home = timeline_dir("demo", "01J00000000000000000000000", root=project_tree)
    legacy_home.mkdir(parents=True, exist_ok=True)
    (legacy_home / "assembly.json").write_text(
        json.dumps({"clips": [], "tracks": []}), encoding="utf-8"
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
    with pytest.raises(EventLogError, match="legacy bootstrap is disabled"):
        backend.append_event(
            "00000000-0000-0000-0000-000000000000",
            "timeline.renamed",
            {"old_slug": "legacy", "new_slug": "legacy-v2"},
            actor=TimelineActor(type="system", id="migration:test"),
        )

    assert backend.read_events() == []
    assert not (legacy_home / "assembly.identity.json").exists()


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


def test_local_fs_backend_concurrent_legacy_first_write_rejects_without_bootstrap(project_tree: Path) -> None:
    legacy_home = timeline_dir("demo", "01J00000000000000000000001", root=project_tree)
    legacy_home.mkdir(parents=True, exist_ok=True)
    (legacy_home / "assembly.json").write_text(
        json.dumps({"clips": [], "tracks": []}), encoding="utf-8"
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
        assert proc.exitcode != 0

    backend = LocalFsBackend(
        timeline_id="00000000-0000-0000-0000-000000000000",
        timeline_home=legacy_home,
    )
    events = backend.read_events()
    assert events == []
    assert not (legacy_home / "assembly.identity.json").exists()


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


# ============================================================================
# m7 observability — integration/behavior tests (T6)
# ============================================================================


def test_history_formatting_includes_backend_timeline_version_event_actor_kind(
    project_tree: Path,
) -> None:
    """History rows include backend, timeline_id, version, event_id, actor (redacted), kind."""
    result = create_timeline("demo", "history-tl", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "clip.added",
        {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": None},
        actor=TimelineActor(type="agent", id="alice:session-1", display="alice"),
    )

    from astrid.core.timeline.cli import _format_history_row, _redact_actor

    events = backend.read_events()
    assert len(events) == 1
    row = _format_history_row(1, events[0], "local_fs")
    assert "v1" in row
    assert events[0].event_id in row
    assert "kind=clip.added" in row
    actor_str = _redact_actor(events[0].actor)
    assert actor_str == "alice"
    assert "actor=" in row


def test_who_edited_actor_rollup_aggregation(project_tree: Path) -> None:
    """Actor rollup groups events by actor.id and counts per kind."""
    result = create_timeline("demo", "who-tl", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)

    alice = TimelineActor(type="agent", id="alice:session-1", display="alice")
    bob = TimelineActor(type="agent", id="bob:session-2", display="bob")

    backend.append_event(
        identity["timeline_id"], "clip.added",
        {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": None},
        actor=alice,
    )
    backend.append_event(
        identity["timeline_id"], "clip.added",
        {"clip_id": "c2", "kind": "audio", "track_id": "audio", "asset_id": "a2", "position": None},
        actor=bob,
    )
    backend.append_event(
        identity["timeline_id"], "clip.removed", {"clip_id": "c1"},
        actor=alice,
    )

    events = backend.read_events()
    # Manual rollup (mirrors cmd_who_edited logic)
    rollup: dict[str, dict] = {}
    for event in events:
        actor_key = event.actor.id
        if actor_key not in rollup:
            rollup[actor_key] = {"kinds": {}, "total": 0, "actor_display": event.actor.display}
        rollup[actor_key]["kinds"][event.kind] = rollup[actor_key]["kinds"].get(event.kind, 0) + 1
        rollup[actor_key]["total"] += 1

    assert len(rollup) == 2
    assert rollup["alice:session-1"]["total"] == 2
    assert rollup["alice:session-1"]["kinds"]["clip.added"] == 1
    assert rollup["alice:session-1"]["kinds"]["clip.removed"] == 1
    assert rollup["bob:session-2"]["total"] == 1
    assert rollup["bob:session-2"]["kinds"]["clip.added"] == 1


def test_verify_chain_tamper_detection_on_localfs(project_tree: Path) -> None:
    """verify_chain() detects tampering in the LocalFs event stream."""
    result = create_timeline("demo", "tamper-tl", root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)

    backend.append_event(
        identity["timeline_id"],
        "clip.added",
        {"clip_id": "c1", "kind": "visual", "track_id": "visual", "asset_id": "a1", "position": None},
        actor=TimelineActor(type="agent", id="test"),
    )

    # Tamper: modify the payload in the jsonl file
    jsonl_path = home / "assembly.jsonl"
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["payload"]["kind"] = "audio"  # changed kind
    jsonl_path.write_text(json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n")

    verification = backend.verify_chain()
    assert verification.ok is False
    assert verification.error is not None
    assert "hash mismatch" in verification.error


def test_ops_log_graceful_absence_no_file(project_tree: Path) -> None:
    """read_ops_log returns None when events_ops.jsonl does not exist."""
    from astrid.core.timeline.observability import read_ops_log

    result = create_timeline("demo", "ops-none-tl", root=project_tree)
    ulid = result["ulid"]
    home = timeline_dir("demo", ulid, root=project_tree)

    entries = read_ops_log(home)
    assert entries is None


def test_ops_log_with_synthetic_data(project_tree: Path) -> None:
    """read_ops_log returns parsed entries when events_ops.jsonl exists."""
    from astrid.core.timeline.observability import read_ops_log

    result = create_timeline("demo", "ops-synthetic-tl", root=project_tree)
    ulid = result["ulid"]
    home = timeline_dir("demo", ulid, root=project_tree)

    ops_path = home / "events_ops.jsonl"
    ops_path.write_text(
        json.dumps({
            "ts": "2026-05-20T12:00:00Z",
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAA01",
            "kind": "clip.added",
            "error": "simulated materialization failure",
        }) + "\n" +
        json.dumps({
            "ts": "2026-05-20T12:01:00Z",
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAA02",
            "kind": "clip.removed",
            "error": "disk full",
        }) + "\n",
        encoding="utf-8",
    )

    entries = read_ops_log(home)
    assert entries is not None
    assert len(entries) == 2
    assert entries[0].kind == "clip.added"
    assert "simulated materialization failure" in entries[0].error
    assert entries[1].kind == "clip.removed"
    assert "disk full" in entries[1].error
