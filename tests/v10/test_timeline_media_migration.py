"""Regression coverage for v10 managed-media timeline registries."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    path = ROOT / "scripts" / "migrations" / "v10" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migrate_timelines():
    return _load_script("migrate_timelines")


@pytest.fixture(scope="module")
def repair_timeline_assets():
    return _load_script("repair_timeline_assets")


def test_build_registry_adds_media_id_without_destroying_source_locator(
    tmp_path: Path, migrate_timelines
) -> None:
    registry_path = tmp_path / "registry.json"
    original = {
        "assets": {
            "source_audio": {
                "file": "audio/runaway.mp3",
                "type": "audio/mpeg",
                "duration": 168.437007,
            }
        }
    }
    registry_path.write_text(json.dumps(original), encoding="utf-8")
    timeline = {
        "kind": "container",
        "registry_path": "registry.json",
        "media_refs": [{"key": "source_audio", "resolved": "audio/runaway.mp3"}],
    }
    result = migrate_timelines.build_registry(
        timeline,
        root=tmp_path,
        files_map={
            "audio/runaway.mp3": {
                "media_id": "media-123",
                "rel_path": "audio/runaway.mp3",
            }
        },
    )

    assert result == {
        "assets": {
            "source_audio": {
                "file": "audio/runaway.mp3",
                "media_id": "media-123",
                "type": "audio/mpeg",
                "duration": 168.437007,
            }
        }
    }
    assert json.loads(registry_path.read_text(encoding="utf-8")) == original


def test_build_registry_does_not_add_identity_for_unresolved_or_remote_assets(
    tmp_path: Path, migrate_timelines
) -> None:
    registry_path = tmp_path / "registry.json"
    original = {"assets": {"remote": {"file": "https://example.test/a.mp3"}}}
    registry_path.write_text(json.dumps(original), encoding="utf-8")
    timeline = {
        "kind": "container",
        "registry_path": "registry.json",
        "media_refs": [
            {"key": "remote", "resolved": None},
            {"key": "missing", "resolved": "missing.mp3"},
        ],
    }

    result = migrate_timelines.build_registry(
        timeline,
        root=tmp_path,
        files_map={"other.mp3": {"media_id": "unused"}},
    )

    assert result == original


def test_repair_registry_removes_only_the_known_bad_uuid_file_alias(
    repair_timeline_assets,
) -> None:
    registry = {
        "assets": {
            "source_audio": {"file": "media-123", "type": "audio/mpeg"},
            "video": {"file": "shots/intro.mp4", "type": "video/mp4"},
        }
    }

    repaired = repair_timeline_assets.repair_registry(
        registry, asset_key="source_audio", media_id="media-123"
    )

    assert repaired == {
        "assets": {
            "source_audio": {"type": "audio/mpeg", "media_id": "media-123"},
            "video": {"file": "shots/intro.mp4", "type": "video/mp4"},
        }
    }
    assert registry["assets"]["source_audio"] == {
        "file": "media-123",
        "type": "audio/mpeg",
    }


def test_repair_registry_preserves_legitimate_file_locator(
    repair_timeline_assets,
) -> None:
    registry = {"assets": {"audio": {"file": "audio/runaway.mp3"}}}
    repaired = repair_timeline_assets.repair_registry(
        registry, asset_key="audio", media_id="media-123"
    )
    assert repaired == {
        "assets": {"audio": {"file": "audio/runaway.mp3", "media_id": "media-123"}}
    }


def test_repair_registry_rejects_conflicting_existing_identity(
    repair_timeline_assets,
) -> None:
    with pytest.raises(ValueError, match="different media_id"):
        repair_timeline_assets.repair_registry(
            {"assets": {"audio": {"media_id": "media-old"}}},
            asset_key="audio",
            media_id="media-new",
        )


def test_repair_timeline_uses_versioned_save_and_is_receipted(
    tmp_path: Path, repair_timeline_assets
) -> None:
    """The repair path is an auditable SDK CAS save, not a SQL projection edit."""
    from astrid.sdk.client import AstridClient

    source = tmp_path / "clip.mp4"
    source.write_bytes(
        (ROOT / "tests" / "fixtures" / "reshape" / "hype_regression" / "main.mp4").read_bytes()
    )
    with AstridClient.open(projects_root=tmp_path) as client:
        project = client.projects.create(slug="demo", name="Demo", idempotency_key="p1")
        assert project.ok, project.error
        imported = client.media.import_file(
            project="demo", path=source, idempotency_key="media-1"
        )
        assert imported.ok, imported.error
        media_id = imported.data["id"]
        timeline = client.timelines.create(
            project="demo",
            slug="main",
            name="Main",
            registry={"assets": {"clip": {"file": media_id}}},
            idempotency_key="timeline-1",
        )
        assert timeline.ok, timeline.error

    evidence = repair_timeline_assets.repair_timeline(
        root=tmp_path,
        project="demo",
        timeline="main",
        asset_key="clip",
        media_id=media_id,
        apply=True,
    )
    assert evidence["action"] == "apply"
    assert evidence["expected_version"] == 1
    assert evidence["resulting_version"] == 2

    with AstridClient.open(projects_root=tmp_path) as client:
        shown = client.timelines.show("demo", "main")
        assert shown.ok, shown.error
        assert shown.data["registry"] == {"assets": {"clip": {"media_id": media_id}}}
        events = client._app.event_log.list_events(
            project_id=project.data["id"], limit=10
        )
        saved = [event for event in events if event.kind == "timeline.saved"]
        assert len(saved) == 1
        assert saved[0].data["registry"] == shown.data["registry"]
