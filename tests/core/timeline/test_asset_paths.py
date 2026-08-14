from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from astrid.core.timeline.events.schema import TimelineEvent, with_event_hash
from astrid.core.timeline.resolution import (
    classify_asset,
    resolve_asset_local_path,
    resolve_asset_local_path_contained,
    resolve_asset_path,
)
from astrid.core.timeline.snapshot import acquire_snapshot

FIXTURE_ROOT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "timeline_visualize"
)
SLICE_DIR = FIXTURE_ROOT / "desert_slice"
PROJECT_SLUG = "asset-path-contract"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_minimal_timeline(
    project_root: Path,
    registry: dict[str, object],
) -> Path:
    """Build a valid two-event timeline from the read-only desert fixture."""

    timeline_dir = project_root / "timelines" / "asset-paths"
    timeline_dir.mkdir(parents=True)
    for name in ("assembly.identity.json", "display.json"):
        shutil.copy2(SLICE_DIR / name, timeline_dir / name)

    raw_events = [
        json.loads(line)
        for line in (SLICE_DIR / "assembly.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[:2]
    ]
    assert raw_events[1]["kind"] == "timeline.asset_registry_replaced"
    raw_events[1]["payload"]["registry"] = registry

    events: list[dict[str, object]] = []
    previous_hash: str | None = None
    for raw_event in raw_events:
        unhashed = TimelineEvent.from_dict({**raw_event, "hash": None})
        event = with_event_hash(unhashed, prev_hash=previous_hash)
        events.append(event.to_json_obj())
        previous_hash = event.hash

    (timeline_dir / "assembly.jsonl").write_text(
        "".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            for event in events
        ),
        encoding="utf-8",
    )
    return timeline_dir


def test_r4_and_r5_share_one_asset_path_normalization_rule(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    sources_root = project_root / "sources"
    sources_root.mkdir(parents=True)
    data = b"one canonical local asset"
    asset_path = sources_root / "foo.png"
    asset_path.write_bytes(data)
    expected_hash = _sha256(data)

    outside = project_root / "README.md"
    outside.write_text("outside sources", encoding="utf-8")
    symlink = sources_root / "outside-link.png"
    symlink.symlink_to(outside)
    non_file = sources_root / "folder"
    non_file.mkdir()

    entries = {
        "bare": {"file": "foo.png", "content_sha256": expected_hash},
        "sources-prefixed": {
            "file": "sources/foo.png",
            "content_sha256": expected_hash,
        },
        "backslash-prefixed": {
            "file": "sources\\foo.png",
            "content_sha256": expected_hash,
        },
        "absolute": {
            "file": str(asset_path.resolve()),
            "content_sha256": expected_hash,
        },
        "double-prefixed": {
            "file": "sources/sources/foo.png",
            "content_sha256": expected_hash,
        },
        "parent-escape": {
            "file": "../README.md",
            "content_sha256": expected_hash,
        },
        "symlink-escape": {
            "file": "outside-link.png",
            "content_sha256": expected_hash,
        },
        "non-file": {"file": "folder"},
    }
    registry = {"assets": entries}
    timeline_dir = _write_minimal_timeline(project_root, registry)

    snapshot = acquire_snapshot(
        timeline_dir,
        project_slug=PROJECT_SLUG,
        project_root=project_root,
    )

    verified_keys = {
        "bare",
        "sources-prefixed",
        "backslash-prefixed",
        "absolute",
    }
    assert snapshot.media_hashes == {
        key: expected_hash for key in sorted(verified_keys)
    }
    for key in verified_keys:
        entry = entries[key]
        assert resolve_asset_local_path(
            entry["file"], project_root=project_root
        ) == asset_path.resolve()
        assert resolve_asset_local_path_contained(
            entry["file"], project_root=project_root
        ) == asset_path.resolve()
        integrity = classify_asset(key, entry, project_root=project_root)
        assert integrity.state == "verified_original"
        assert Path(integrity.path) == asset_path.resolve()

    doubled = entries["double-prefixed"]
    doubled_path = sources_root / "sources" / "foo.png"
    assert resolve_asset_local_path(
        doubled["file"], project_root=project_root
    ) is None
    assert resolve_asset_local_path_contained(
        doubled["file"], project_root=project_root
    ) == doubled_path.resolve()
    assert resolve_asset_path(
        "double-prefixed", doubled, project_root=project_root
    ) == doubled_path.resolve()
    assert classify_asset(
        "double-prefixed", doubled, project_root=project_root
    ).state == "missing"

    for key in ("parent-escape", "symlink-escape"):
        entry = entries[key]
        assert resolve_asset_local_path(
            entry["file"], project_root=project_root
        ) is None
        assert resolve_asset_local_path_contained(
            entry["file"], project_root=project_root
        ) is None
        assert classify_asset(key, entry, project_root=project_root).state == "unsupported"
        assert key not in snapshot.media_hashes

    non_file_entry = entries["non-file"]
    assert resolve_asset_local_path(
        non_file_entry["file"], project_root=project_root
    ) is None
    assert resolve_asset_local_path_contained(
        non_file_entry["file"], project_root=project_root
    ) == non_file.resolve()
    assert classify_asset(
        "non-file", non_file_entry, project_root=project_root
    ).state == "missing"
    assert "non-file" not in snapshot.media_hashes
