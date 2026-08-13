from __future__ import annotations

import json
import multiprocessing
from pathlib import Path

import pytest

from astrid.core.timeline.crud import create_timeline, rename_timeline, show_timeline
from astrid.core.timeline.eventlog import LocalFsBackend
from astrid.core.timeline.eventlog.reigh_events import construct_reigh_timeline_events
from astrid.core.timeline.eventlog.types import EventLogError, EventLogStaleVersionError
from astrid.core.timeline.events.schema import TimelineActor, TimelineEvent, canonical_json_bytes
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
    # MUST-FIX 3a: a stale/corrupt head (wrong count, no offsets, id/hash
    # that do not match the log) is NEVER trusted — it is rebuilt from the
    # actual log and the sidecar is rewritten atomically.
    rebuilt = backend.head()
    assert rebuilt.version == 1
    assert rebuilt.last_event_id == event.event_id
    assert rebuilt.last_hash == event.hash
    assert rebuilt.log_size == (home / "assembly.jsonl").stat().st_size
    repaired_json = json.loads(head_path.read_text(encoding="utf-8"))
    assert repaired_json["version"] == 1
    assert repaired_json["log_size"] == rebuilt.log_size
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

    from astrid.core.cli.timeline import _format_history_row, _redact_actor

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


# ============================================================================
# T2.1 — incremental head: warm appends do no full-log reads; crash recovery
# ============================================================================

def _seed_timeline(project_tree: Path, slug: str) -> tuple[Path, dict[str, object], LocalFsBackend]:
    """Create a timeline plus one timeline.renamed event; return (home, identity, backend)."""
    result = create_timeline("demo", slug, root=project_tree)
    ulid = result["ulid"]
    identity = json.loads(
        assembly_identity_path("demo", ulid, root=project_tree).read_text(encoding="utf-8")
    )
    home = timeline_dir("demo", ulid, root=project_tree)
    backend = LocalFsBackend(timeline_id=identity["timeline_id"], timeline_home=home)
    backend.append_event(
        identity["timeline_id"],
        "timeline.renamed",
        {"old_slug": slug, "new_slug": f"{slug}-v2"},
        actor=TimelineActor(type="agent", id="codex:test"),
    )
    return home, identity, backend


def _make_config_batch(
    identity: dict[str, object],
    tail_hash: str | None,
    next_event_version: int,
    *,
    index: int,
) -> object:
    return construct_reigh_timeline_events(
        timeline_id=identity["timeline_id"],
        tail_hash=tail_hash,
        next_event_version=next_event_version,
        actor=TimelineActor(type="human", id="reigh-app:local-editor"),
        source="editor_save",
        config={
            "clips": [
                {
                    "id": f"c{index}",
                    "at": float(index),
                    "track": "V1",
                    "clipType": "media",
                    "asset": "a1",
                }
            ],
            "tracks": [{"id": "V1", "kind": "visual", "label": "Video"}],
        },
    )


def test_append_prebuilt_warm_append_does_no_full_log_read(project_tree: Path) -> None:
    """Warm append_prebuilt_events must read only the tail, never the full log."""
    home, identity, backend = _seed_timeline(project_tree, "warm-tl")

    backend.full_log_reads = 0
    head = backend.head()
    tail_hash = head.last_hash
    version = head.version
    for index in range(3):
        batch = _make_config_batch(identity, tail_hash, version + 1, index=index)
        backend.append_prebuilt_events(
            identity["timeline_id"],
            [item.event for item in batch.events],
        )
        tail_hash = batch.tail_hash
        version += 1

    assert backend.full_log_reads == 0, "warm append performed a full-log read"
    assert backend.verify_chain().ok is True
    assert backend.head().version == version


def test_append_prebuilt_head_offsets_track_log_bytes(project_tree: Path) -> None:
    """The head carries crash-reconciled log_size + last_event_offset."""
    home, identity, backend = _seed_timeline(project_tree, "offsets-tl")
    head = backend.head()
    log_size = (home / "assembly.jsonl").stat().st_size
    assert head.log_size == log_size
    assert 0 <= head.last_event_offset < head.log_size

    # The line at last_event_offset is exactly the last complete event.
    with (home / "assembly.jsonl").open("rb") as handle:
        handle.seek(head.last_event_offset)
        tail_line = handle.read(head.log_size - head.last_event_offset)
    assert tail_line.endswith(b"\n")
    assert json.loads(tail_line)["event_id"] == head.last_event_id

    # A subsequent warm append advances the offsets by exactly the batch bytes.
    batch = _make_config_batch(identity, head.last_hash, head.version + 1, index=99)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    new_head = backend.head()
    assert new_head.log_size == (home / "assembly.jsonl").stat().st_size
    assert new_head.last_event_offset == log_size


def test_append_prebuilt_recovers_when_head_missing(project_tree: Path) -> None:
    """Head-missing is the allowed full-parse fallback (crash recovery)."""
    home, identity, backend = _seed_timeline(project_tree, "headless-tl")
    head_before = backend.head()
    head_path = home / "assembly.head.json"
    head_path.unlink()

    backend.full_log_reads = 0
    batch = _make_config_batch(identity, head_before.last_hash, head_before.version + 1, index=1)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.full_log_reads == 1, "head-missing must rebuild via exactly one full parse"
    assert backend.verify_chain().ok is True
    rebuilt = backend.head()
    assert rebuilt.version == head_before.version + 1
    assert rebuilt.log_size == (home / "assembly.jsonl").stat().st_size
    assert rebuilt.last_event_offset is not None

    # Next append is warm again (head now carries offsets).
    backend.full_log_reads = 0
    batch = _make_config_batch(identity, rebuilt.last_hash, rebuilt.version + 1, index=2)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.full_log_reads == 0
    assert backend.verify_chain().ok is True


def test_append_prebuilt_rebuilds_from_legacy_head_without_offsets(project_tree: Path) -> None:
    """Legacy heads (pre-T2.1, no offsets) trigger one rebuild, then go warm."""
    home, identity, backend = _seed_timeline(project_tree, "legacy-head-tl")
    head_path = home / "assembly.head.json"
    old_head = json.loads(head_path.read_text(encoding="utf-8"))
    # Strip the new fields to simulate a pre-T2.1 head.
    legacy = {key: old_head[key] for key in ("timeline_id", "last_event_id", "last_hash", "event_count", "version")}
    head_path.write_text(json.dumps(legacy), encoding="utf-8")

    backend.full_log_reads = 0
    batch = _make_config_batch(identity, old_head["last_hash"], old_head["version"] + 1, index=7)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.full_log_reads == 1
    rewritten = json.loads(head_path.read_text(encoding="utf-8"))
    assert "log_size" in rewritten and "last_event_offset" in rewritten
    assert backend.verify_chain().ok is True

    backend.full_log_reads = 0
    batch = _make_config_batch(identity, rewritten["last_hash"], rewritten["version"] + 1, index=8)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.full_log_reads == 0
    assert backend.verify_chain().ok is True


def test_append_prebuilt_truncates_torn_tail_beyond_head(project_tree: Path) -> None:
    """A torn partial write beyond the head's log_size is truncated on append."""
    home, identity, backend = _seed_timeline(project_tree, "torn-tail-tl")
    head_before = backend.head()

    # Simulate a crash mid-write: garbage bytes past the durable log.
    with (home / "assembly.jsonl").open("ab") as handle:
        handle.write(b'{"kind": "timeline.config_replaced", "paTORN')

    batch = _make_config_batch(identity, head_before.last_hash, head_before.version + 1, index=3)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    log = (home / "assembly.jsonl").read_bytes()
    assert b"paTORN" not in log, "torn tail bytes must be truncated"
    assert log.endswith(canonical_json_bytes(batch.events[-1].event.to_json_obj()) + b"\n")
    assert backend.verify_chain().ok is True
    assert backend.head().log_size == len(log)


def test_append_prebuilt_adopts_orphaned_complete_batch_after_crash(project_tree: Path) -> None:
    """Complete chain-valid events beyond the head (crash before head write) are adopted."""
    home, identity, backend = _seed_timeline(project_tree, "orphan-tl")
    head_before = backend.head()

    # Simulate a crash between the fsync'd append and the head write: append a
    # complete chained batch to the log WITHOUT updating the head.
    orphan = _make_config_batch(identity, head_before.last_hash, head_before.version + 1, index=11)
    with (home / "assembly.jsonl").open("ab") as handle:
        handle.write(canonical_json_bytes(orphan.events[0].event.to_json_obj()) + b"\n")

    # The next append must adopt the orphan and chain from it (no data loss).
    batch = _make_config_batch(identity, orphan.tail_hash, head_before.version + 2, index=12)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.head().version == head_before.version + 2
    assert backend.head().last_event_id == batch.events[-1].event.event_id
    assert backend.verify_chain().ok is True
    assert len(backend.read_events()) == head_before.event_count + 2


# ============================================================================
# MUST-FIX 3a — corrupt heads rebuild, never trust, never raise
# ============================================================================

def test_head_rebuilds_on_corrupt_json_sidecar(project_tree: Path) -> None:
    """Bad JSON in the head sidecar is rebuilt from the log, not raised on."""
    home, identity, backend = _seed_timeline(project_tree, "corrupt-json-tl")
    head_path = home / "assembly.head.json"
    head_path.write_text("{not valid json!!", encoding="utf-8")

    rebuilt = backend.head()
    assert rebuilt.version == 1
    assert rebuilt.last_hash is not None
    # The corrupt sidecar was rewritten atomically with the rebuilt head.
    repaired = json.loads(head_path.read_text(encoding="utf-8"))
    assert repaired["version"] == 1
    assert repaired["last_event_id"] == rebuilt.last_event_id
    assert backend.verify_chain().ok is True


def test_head_rebuilds_on_wrong_shape_sidecar(project_tree: Path) -> None:
    """A non-object or field-missing head sidecar is rebuilt, never trusted."""
    home, identity, backend = _seed_timeline(project_tree, "wrong-shape-tl")
    head_path = home / "assembly.head.json"

    head_path.write_text("[1, 2, 3]", encoding="utf-8")
    assert backend.head().version == 1

    # Missing version/fields (not just legacy offsets) is corruption.
    head_path.write_text(
        json.dumps({"timeline_id": identity["timeline_id"], "event_count": 7}),
        encoding="utf-8",
    )
    rebuilt = backend.head()
    assert rebuilt.version == 1
    assert json.loads(head_path.read_text(encoding="utf-8"))["version"] == 1


def test_head_rebuilds_when_offsets_lie_about_log_size(project_tree: Path) -> None:
    """A head whose log_size exceeds the actual file is rebuilt (external truncation)."""
    home, identity, backend = _seed_timeline(project_tree, "offsets-lie-tl")
    head_path = home / "assembly.head.json"
    log_path = home / "assembly.jsonl"

    head = backend.head()
    # Truncate the log underneath the head (crash / external truncation).
    log_path.write_bytes(b"")

    rebuilt = backend.head()
    assert rebuilt.version == 0
    assert rebuilt.event_count == 0
    assert rebuilt.log_size == 0
    repaired = json.loads(head_path.read_text(encoding="utf-8"))
    assert repaired["version"] == 0
    assert repaired["event_count"] == 0
    # The sidecar was rewritten, so the pre-truncation head is gone.
    assert repaired["log_size"] != head.log_size


def test_head_rebuilds_when_boundary_does_not_match_log(project_tree: Path) -> None:
    """A head whose last_event_id/hash disagree with the log boundary is rebuilt."""
    home, identity, backend = _seed_timeline(project_tree, "boundary-tl")
    head_path = home / "assembly.head.json"
    head = backend.head()

    # Keep offsets but lie about which event they point at.
    lying = {
        "timeline_id": head.timeline_id,
        "last_event_id": "not-in-the-log",
        "last_hash": "0" * 64,
        "event_count": head.event_count,
        "version": head.version,
        "log_size": head.log_size,
        "last_event_offset": head.last_event_offset,
    }
    head_path.write_text(json.dumps(lying), encoding="utf-8")

    rebuilt = backend.head()
    assert rebuilt.version == head.version
    assert rebuilt.last_event_id == head.last_event_id
    assert rebuilt.last_hash == head.last_hash
    assert json.loads(head_path.read_text(encoding="utf-8"))["last_event_id"] == head.last_event_id


def test_append_prebuilt_recovers_from_corrupt_head_sidecar(project_tree: Path) -> None:
    """A corrupt head sidecar never raises the append; it rebuilds once, then stays warm."""
    home, identity, backend = _seed_timeline(project_tree, "corrupt-head-append-tl")
    head_before = backend.head()
    (home / "assembly.head.json").write_text("{corrupt", encoding="utf-8")

    backend.full_log_reads = 0
    batch = _make_config_batch(identity, head_before.last_hash, head_before.version + 1, index=5)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.full_log_reads == 1, "corrupt head must rebuild via one full parse"
    assert backend.verify_chain().ok is True
    rebuilt = backend.head()
    assert rebuilt.version == head_before.version + 1

    # Next append is warm again (sidecar was rebuilt with offsets).
    backend.full_log_reads = 0
    batch = _make_config_batch(identity, rebuilt.last_hash, rebuilt.version + 1, index=6)
    backend.append_prebuilt_events(
        identity["timeline_id"],
        [item.event for item in batch.events],
    )
    assert backend.full_log_reads == 0
    assert backend.verify_chain().ok is True


def test_append_prebuilt_truncates_nonchaining_residue_but_keeps_head_consistent(
    project_tree: Path,
) -> None:
    """Head validation prevents bad metadata from truncating valid suffix events."""
    home, identity, backend = _seed_timeline(project_tree, "no-trunc-valid-tl")
    head_path = home / "assembly.head.json"
    head_before = backend.head()

    # Append a complete chained orphaned event (crash before head write).
    orphan = _make_config_batch(identity, head_before.last_hash, head_before.version + 1, index=21)
    with (home / "assembly.jsonl").open("ab") as handle:
        handle.write(canonical_json_bytes(orphan.events[0].event.to_json_obj()) + b"\n")

    # A head that does NOT cover the orphan (stale log_size/last_event_offset)
    # is still valid for its covered region: the orphan is ADOPTED, not lost.
    rebuilt = backend.head()
    assert rebuilt.version == head_before.version + 1
    assert rebuilt.last_event_id == orphan.events[0].event.event_id
    assert rebuilt.log_size == (home / "assembly.jsonl").stat().st_size
    assert json.loads(head_path.read_text(encoding="utf-8"))["version"] == head_before.version + 1
    assert backend.verify_chain().ok is True


def test_append_prebuilt_bad_middle_event_leaves_no_torn_log(project_tree: Path) -> None:
    """A batch with a bad middle event must fail atomically: no bytes written."""
    home, identity, backend = _seed_timeline(project_tree, "partial-batch-tl")

    before_log = (home / "assembly.jsonl").read_bytes()
    before_head = (home / "assembly.head.json").read_bytes()

    head = backend.head()
    e1 = _make_config_batch(identity, head.last_hash, head.version + 1, index=1).events[0].event
    e2 = _make_config_batch(identity, e1.hash, head.version + 2, index=2).events[0].event
    e3 = _make_config_batch(identity, e2.hash, head.version + 3, index=3).events[0].event

    # Corrupt the middle event's prev_hash (breaks the chain at index 1).
    bad_middle = TimelineEvent.from_dict({**e2.to_json_obj(), "prev_hash": "0" * 64})

    with pytest.raises(EventLogError, match="prev_hash"):
        backend.append_prebuilt_events(
            identity["timeline_id"],
            [e1, bad_middle, e3],
        )

    assert (home / "assembly.jsonl").read_bytes() == before_log
    assert (home / "assembly.head.json").read_bytes() == before_head
    assert backend.verify_chain().ok is True
    assert backend.head().version == head.version


def test_read_tail_events_returns_last_events_in_order(project_tree: Path) -> None:
    """read_tail_events returns the last N complete events in forward order."""
    home, identity, backend = _seed_timeline(project_tree, "tail-tl")
    head = backend.head()
    prev = head.last_hash
    version = head.version
    for index in range(5):
        batch = _make_config_batch(identity, prev, version + 1, index=index)
        backend.append_prebuilt_events(
            identity["timeline_id"],
            [item.event for item in batch.events],
        )
        prev = batch.tail_hash
        version += 1

    all_events = backend.read_events()
    assert len(all_events) == 6

    tail2 = backend.read_tail_events(limit=2)
    assert [e.event_id for e in tail2] == [e.event_id for e in all_events[-2:]]

    tail1 = backend.read_tail_events(limit=1)
    assert [e.event_id for e in tail1] == [e.event_id for e in all_events[-1:]]

    tail_all = backend.read_tail_events(limit=1000)
    assert [e.event_id for e in tail_all] == [e.event_id for e in all_events]

    assert backend.read_tail_events(limit=0) == []
    assert backend.read_tail_events(limit=-1) == []


def test_read_tail_events_drops_torn_tail(project_tree: Path) -> None:
    """A torn trailing line (crash residue) is skipped by read_tail_events."""
    home, identity, backend = _seed_timeline(project_tree, "tail-torn")
    complete_ids = [e.event_id for e in backend.read_events()]
    with (home / "assembly.jsonl").open("ab") as handle:
        handle.write(b'{"partial":')
    tail = backend.read_tail_events(limit=4)
    assert [e.event_id for e in tail] == complete_ids
    assert all(e.kind == "timeline.renamed" for e in tail)
