from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

import pytest

import astrid.core.timeline.snapshot as snapshot_module
from astrid.core._shared import jsonio
from astrid.core.integrations.reigh import local_bridge
from astrid.core.timeline import paths, projection
from astrid.core.timeline.eventlog.local_fs import LocalFsBackend
from astrid.core.timeline.events.schema import TimelineEvent, with_event_hash
from astrid.core.timeline.snapshot import (
    ConcurrentAppendError,
    acquire_snapshot,
    snapshot_from_events,
    verify_frozen,
)

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "timeline_visualize"
)
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
PROJECT_SLUG = "desert-plant-growth"
TIMELINE_ID = "ed70ef66-43da-4182-9f14-69361c6c5e10"
TIMELINE_ULID = "01KYPVKMW5STB4W6FE05ED8242"
LAST_EVENT_ID = "01KZS6CCD73SYEC924B5XR12XG"
LAST_HASH = "6f6de92702ef683d44b6bd52da32383f34488ea44db4113cadf95ec60ef8535d"
ASSEMBLY_SHA256 = "d126b04632412bc9e85c4e7d2218d08172e34a15007c6c39b5fa5beb6fb231d0"
REGISTRY_SHA256 = "514e6020af06a289764f6d1ab282619f49b0021e45a0bfa48034a0cc7106fb37"
SNS = "SNS:ef2ce1bd0e2e67f0b07cf5e13b1530aca362b6d9c03b9d83c9abd4f548c6b377"


def _copy_slice(tmp_path: Path) -> Path:
    destination = tmp_path / "timeline"
    shutil.copytree(SLICE_DIR, destination)
    return destination


def _events(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (path / "assembly.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def _append_hashed_event(
    events: list[dict],
    *,
    event_id: str,
    kind: str,
    payload: dict,
) -> None:
    previous_hash = events[-1]["hash"] if events else None
    event = TimelineEvent.from_dict(
        {
            "schema_version": 2,
            "event_id": event_id,
            "timeline_id": TIMELINE_ID,
            "ts": "2026-07-29T12:00:00Z",
            "actor": {"type": "system", "id": "snapshot-test"},
            "prev_hash": previous_hash,
            "hash": None,
            "kind": kind,
            "payload": payload,
            "expected_version": len(events),
        }
    )
    events.append(with_event_hash(event, prev_hash=previous_hash).to_json_obj())


def _file_state(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_portable_slice_acquisition_is_event_sourced_and_byte_stable(
    tmp_path: Path,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    before = _file_state(timeline_dir)

    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    assert snapshot.timeline_id == TIMELINE_ID
    assert snapshot.timeline_ulid == TIMELINE_ULID
    assert snapshot.slug == "plant-growth-storyboard"
    assert snapshot.head_version == 159
    assert snapshot.last_event_id == LAST_EVENT_ID
    assert snapshot.last_hash == LAST_HASH
    assert len(snapshot.assembly["clips"]) == 5
    assert "toccata-fugue" in snapshot.registry["assets"]
    assert snapshot.assembly_sha256 == ASSEMBLY_SHA256
    assert snapshot.registry_sha256 == REGISTRY_SHA256
    assert snapshot.media_hashes == {}
    assert snapshot.transcript_sha256 is None
    assert snapshot.sns() == SNS
    assert snapshot.diagnostics == ()
    assert _file_state(timeline_dir) == before


def test_display_json_is_plain_fallback_when_log_has_no_display_events(
    tmp_path: Path,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    fallback = {
        "schema_version": 1,
        "slug": "plain-file-fallback",
        "name": "Plain file fallback",
        "is_default": False,
    }
    (timeline_dir / "display.json").write_text(
        json.dumps(fallback),
        encoding="utf-8",
    )

    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    assert snapshot.display == fallback
    assert snapshot.slug == "plain-file-fallback"


def test_display_events_replay_from_identity_root_not_live_display(
    tmp_path: Path,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    identity_path = timeline_dir / "assembly.identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["display"] = {
        "schema_version": 1,
        "slug": "plant-growth-storyboard",
        "name": "Frozen creation name",
        "is_default": False,
    }
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    (timeline_dir / "display.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "slug": "future-live-slug",
                "name": "Future live name",
                "is_default": True,
            }
        ),
        encoding="utf-8",
    )
    events = _events(timeline_dir)
    _append_hashed_event(
        events,
        event_id="01KZS6CCD73SYEC924B5XR12XH",
        kind="timeline.renamed",
        payload={
            "old_slug": "plant-growth-storyboard",
            "new_slug": "captured-event-slug",
        },
    )

    snapshot = snapshot_from_events(
        events,
        timeline_dir=timeline_dir,
        project_slug=PROJECT_SLUG,
    )

    assert snapshot.display == {
        "schema_version": 1,
        "slug": "captured-event-slug",
        "name": "Frozen creation name",
        "is_default": False,
    }
    assert snapshot.slug == "captured-event-slug"


def test_acquisition_never_calls_mutating_or_repair_apis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    before = _file_state(timeline_dir)
    calls: list[str] = []

    def forbidden(name: str) -> Callable[..., None]:
        def fail(*_args: object, **_kwargs: object) -> None:
            calls.append(name)
            raise AssertionError(f"mutating API called: {name}")

        return fail

    monkeypatch.setattr(
        paths,
        "load_assembly_json_with_repair",
        forbidden("load_assembly_json_with_repair"),
    )
    monkeypatch.setattr(
        paths,
        "load_display_json_with_repair",
        forbidden("load_display_json_with_repair"),
    )
    monkeypatch.setattr(
        projection,
        "regenerate_projection",
        forbidden("regenerate_projection"),
    )
    monkeypatch.setattr(LocalFsBackend, "head", forbidden("LocalFsBackend.head"))
    monkeypatch.setattr(
        LocalFsBackend,
        "append_event",
        forbidden("LocalFsBackend.append_event"),
    )
    monkeypatch.setattr(
        local_bridge,
        "_ensure_bridge_registry",
        forbidden("_ensure_bridge_registry"),
    )
    monkeypatch.setattr(
        jsonio,
        "write_json_atomic",
        forbidden("write_json_atomic"),
    )

    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    assert snapshot.head_version == 159
    assert calls == []
    assert _file_state(timeline_dir) == before


def test_stale_head_sidecar_is_diagnostic_not_authority(tmp_path: Path) -> None:
    timeline_dir = _copy_slice(tmp_path)
    head_path = timeline_dir / "assembly.head.json"
    head = json.loads(head_path.read_text(encoding="utf-8"))
    head["version"] = 100
    head_path.write_text(json.dumps(head), encoding="utf-8")

    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    assert snapshot.head_version == 159
    assert snapshot.last_event_id == LAST_EVENT_ID
    assert any(
        diagnostic.startswith("HEAD_SIDECAR_STALE: version is 100")
        for diagnostic in snapshot.diagnostics
    )
    assert verify_frozen(snapshot) == list(snapshot.diagnostics)


def test_ahead_head_sidecar_is_diagnostic_and_does_not_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    head_path = timeline_dir / "assembly.head.json"
    head = json.loads(head_path.read_text(encoding="utf-8"))
    head["version"] = 160
    head["event_count"] = 160
    head_path.write_text(json.dumps(head), encoding="utf-8")
    original = snapshot_module._read_event_dicts
    calls = 0

    def counted_read(path: Path) -> list[dict]:
        nonlocal calls
        calls += 1
        return original(path)

    monkeypatch.setattr(snapshot_module, "_read_event_dicts", counted_read)

    snapshot = acquire_snapshot(
        timeline_dir,
        project_slug=PROJECT_SLUG,
        retries=2,
    )

    assert calls == 1
    assert snapshot.head_version == 159
    assert snapshot.last_event_id == LAST_EVENT_ID
    assert sum(
        diagnostic.startswith("HEAD_SIDECAR_AHEAD:")
        for diagnostic in snapshot.diagnostics
    ) == 2


def test_jsonl_fingerprint_change_retries_and_returns_stable_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    original = snapshot_module._read_event_dicts
    read_calls = 0
    first = (1, 2, 3, 4)
    second = (1, 2, 4, 5)
    fingerprints = iter([first, second, second, second])

    def counted_read(path: Path) -> list[dict]:
        nonlocal read_calls
        read_calls += 1
        return original(path)

    monkeypatch.setattr(snapshot_module, "_read_event_dicts", counted_read)
    monkeypatch.setattr(
        snapshot_module,
        "_event_file_fingerprint",
        lambda _path: next(fingerprints),
    )

    snapshot = acquire_snapshot(
        timeline_dir,
        project_slug=PROJECT_SLUG,
        retries=1,
    )

    assert read_calls == 2
    assert snapshot.head_version == 159
    assert snapshot.last_event_id == LAST_EVENT_ID


def test_jsonl_fingerprint_change_exhaustion_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    original = snapshot_module._read_event_dicts
    read_calls = 0
    fingerprints = iter(
        [
            (1, 2, 3, 4),
            (1, 2, 4, 5),
            (1, 2, 5, 6),
            (1, 2, 6, 7),
        ]
    )

    def counted_read(path: Path) -> list[dict]:
        nonlocal read_calls
        read_calls += 1
        return original(path)

    monkeypatch.setattr(snapshot_module, "_read_event_dicts", counted_read)
    monkeypatch.setattr(
        snapshot_module,
        "_event_file_fingerprint",
        lambda _path: next(fingerprints),
    )

    with pytest.raises(ConcurrentAppendError, match="after 2 attempt"):
        acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG, retries=1)
    assert read_calls == 2


def test_stable_event_read_error_is_integrity_failure_without_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    calls = 0

    def malformed_read(_path: Path) -> list[dict]:
        nonlocal calls
        calls += 1
        raise snapshot_module._EventReadError("stable malformed JSONL")

    monkeypatch.setattr(snapshot_module, "_read_event_dicts", malformed_read)

    with pytest.raises(
        snapshot_module.SnapshotIntegrityError,
        match="stable malformed JSONL",
    ):
        acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG, retries=3)
    assert calls == 1


@pytest.mark.parametrize("sidecar_state", ["deleted", "tampered"])
def test_registry_is_derived_only_from_latest_event(
    tmp_path: Path,
    sidecar_state: str,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    registry_path = timeline_dir / "registry.json"
    expected = json.loads(registry_path.read_text(encoding="utf-8"))
    if sidecar_state == "deleted":
        registry_path.unlink()
    else:
        registry_path.write_text(
            json.dumps({"assets": {"sidecar-only": {"file": "wrong.mp4"}}}),
            encoding="utf-8",
        )

    snapshot = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    assert snapshot.registry == expected
    assert "sidecar-only" not in snapshot.registry["assets"]
    assert snapshot.registry_sha256 == REGISTRY_SHA256


def test_two_acquisitions_are_deterministic(tmp_path: Path) -> None:
    timeline_dir = _copy_slice(tmp_path)

    first = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)
    second = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)

    assert first.sns() == second.sns() == SNS
    assert first.assembly == second.assembly
    assert first.registry == second.registry
    assert first.events == second.events


def test_verify_frozen_reports_corrupt_event_hash_without_live_reread(
    tmp_path: Path,
) -> None:
    timeline_dir = _copy_slice(tmp_path)
    valid = acquire_snapshot(timeline_dir, project_slug=PROJECT_SLUG)
    assert verify_frozen(valid) == []

    corrupted_events = _events(timeline_dir)
    corrupted_events[79]["hash"] = "0" * 64
    corrupted = snapshot_from_events(
        corrupted_events,
        timeline_dir=timeline_dir,
        project_slug=PROJECT_SLUG,
    )

    diagnostics = verify_frozen(corrupted, expect_version=159)
    assert any(item.startswith("EVENT_HASH_MISMATCH:") for item in diagnostics)


def test_media_hashes_are_observed_only_from_contained_project_sources(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    timeline_dir = _copy_slice(project_root)
    music = project_root / "sources" / "toccata-fugue" / "toccata-fugue.mp3"
    music.parent.mkdir(parents=True)
    music.write_bytes(b"portable music bytes")

    snapshot = acquire_snapshot(
        timeline_dir,
        project_slug=PROJECT_SLUG,
        project_root=project_root,
    )

    assert snapshot.media_hashes == {
        "toccata-fugue": hashlib.sha256(b"portable music bytes").hexdigest()
    }
    assert sum(item.startswith("MEDIA_MISSING:") for item in snapshot.diagnostics) == 4
