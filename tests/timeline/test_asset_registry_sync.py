"""Tests for ``astrid.core.timeline.asset_registry_edits`` — sync_asset_registry."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.core.foundation.project_paths import project_dir, sources_dir
from astrid.core.timeline.asset_registry_edits import (
    _entry_from_source_ref,
    _resolve_file_under_sources,
    sync_asset_registry,
)
from astrid.core.timeline.crud import create_timeline
from astrid.core.timeline.paths import timeline_dir


# ── helpers ──────────────────────────────────────────────────────────────────


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_registry(assets: dict | None = None) -> dict:
    return {"assets": assets or {}}


# ── _entry_from_source_ref ──────────────────────────────────────────────────


class TestEntryFromSourceRef:
    def test_source_id_lookup(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        proj_dir = tmp_path / "proj"
        proj_dir.mkdir(parents=True)
        _write_json(proj_dir / "sources.json", {
            "version": 1,
            "sources": {
                "src-1": {
                    "file": "clip.mp4",
                    "url": "https://cdn.example.com/clip.mp4",
                    "type": "video/mp4",
                    "duration": 10.5,
                },
            },
        })

        with mock.patch(
            "astrid.core.timeline.asset_registry_edits.project_dir",
            return_value=proj_dir,
        ):
            result = _entry_from_source_ref(
                asset_key="my-asset",
                source_ref={"source_id": "src-1"},
                project_slug="demo",
                sources_root=sources_root,
            )

        assert result["file"] == "clip.mp4"
        assert result["url"] == "https://cdn.example.com/clip.mp4"
        assert result["type"] == "video/mp4"
        assert result["duration"] == 10.5

    def test_source_id_falls_back_to_per_source_source_json(self, tmp_path: Path) -> None:
        """`astrid projects source add` writes sources/<id>/source.json (media
        fields under `asset`) and NOT the flat project sources.json — the sync
        must resolve source_id from that per-source sidecar."""
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        per_source = sources_root / "toccata-fugue"
        per_source.mkdir(parents=True)
        _write_json(per_source / "source.json", {
            "source_id": "toccata-fugue",
            "kind": "audio",
            "asset": {
                "file": "toccata-fugue/toccata-fugue.mp3",
                "type": "audio/mpeg",
                "duration": 97.5,
            },
        })
        # Flat project sources.json does NOT contain the source.
        proj_dir = tmp_path / "proj"
        proj_dir.mkdir(parents=True)
        _write_json(proj_dir / "sources.json", {"version": 1, "sources": {}})

        with mock.patch(
            "astrid.core.timeline.asset_registry_edits.project_dir",
            return_value=proj_dir,
        ):
            result = _entry_from_source_ref(
                asset_key="music",
                source_ref={"source_id": "toccata-fugue"},
                project_slug="demo",
                sources_root=sources_root,
            )

        assert result["file"] == "toccata-fugue/toccata-fugue.mp3"
        assert result["type"] == "audio/mpeg"
        assert result["duration"] == 97.5

    def test_file_containment_ok(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        (sources_root / "clip.mp4").write_text("fake", encoding="utf-8")

        result = _entry_from_source_ref(
            asset_key="my-asset",
            source_ref={"file": "clip.mp4"},
            project_slug="demo",
            sources_root=sources_root,
        )
        assert result["file"] == "clip.mp4"
        assert result.get("type") is not None

    def test_file_outside_sources_rejected(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)

        with pytest.raises(AstridError, match="not under the project sources"):
            _entry_from_source_ref(
                asset_key="my-asset",
                source_ref={"file": "../evil.txt"},
                project_slug="demo",
                sources_root=sources_root,
            )

    def test_file_missing_rejected(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)

        with pytest.raises(AstridError, match="does not exist"):
            _entry_from_source_ref(
                asset_key="my-asset",
                source_ref={"file": "nonexistent.mp4"},
                project_slug="demo",
                sources_root=sources_root,
            )

    def test_both_source_id_and_file_rejected(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        with pytest.raises(AstridError, match="exactly one"):
            _entry_from_source_ref(
                asset_key="my-asset",
                source_ref={"source_id": "s1", "file": "x.mp4"},
                project_slug="demo",
                sources_root=sources_root,
            )

    def test_neither_source_id_nor_file_rejected(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        with pytest.raises(AstridError, match="must provide source_id or file"):
            _entry_from_source_ref(
                asset_key="my-asset",
                source_ref={},
                project_slug="demo",
                sources_root=sources_root,
            )

    def test_unknown_source_id_rejected(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        proj_dir = tmp_path / "proj"
        proj_dir.mkdir(parents=True)
        _write_json(proj_dir / "sources.json", {"version": 1, "sources": {}})

        with mock.patch(
            "astrid.core.timeline.asset_registry_edits.project_dir",
            return_value=proj_dir,
        ):
            with pytest.raises(AstridError, match="not found in project sources"):
                _entry_from_source_ref(
                    asset_key="my-asset",
                    source_ref={"source_id": "unknown"},
                    project_slug="demo",
                    sources_root=sources_root,
                )


# ── _resolve_file_under_sources ──────────────────────────────────────────────


class TestResolveFileUnderSources:
    def test_file_inside_sources(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        (sources_root / "f.mp4").write_text("x", encoding="utf-8")
        result = _resolve_file_under_sources("f.mp4", sources_root)
        assert result is not None
        assert result.name == "f.mp4"

    def test_file_outside_sources(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        result = _resolve_file_under_sources("../outside.txt", sources_root)
        assert result is None

    def test_file_absolute_rejected(self, tmp_path: Path) -> None:
        sources_root = tmp_path / "sources"
        sources_root.mkdir(parents=True)
        result = _resolve_file_under_sources("/etc/passwd", sources_root)
        assert result is None


# ── sync_asset_registry integration ──────────────────────────────────────────


class TestSyncAssetRegistry:
    def test_sync_adds_new_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Asset key ≠ source id mapping works."""
        from astrid.core.project.project import create_project as _create_project

        projects_root = tmp_path / "asset-sync-projects"
        projects_root.mkdir(parents=True)
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

        _create_project("demo", root=projects_root)

        # Create a timeline
        tl_result = create_timeline("demo", "main", is_default=True, root=projects_root)
        tl_ulid = tl_result["ulid"]
        tl_dir = timeline_dir("demo", tl_ulid, root=projects_root)

        # Set up sources
        proj_dir = project_dir("demo", root=projects_root)
        _write_json(proj_dir / "sources.json", {
            "version": 1,
            "sources": {
                "src-abc": {
                    "file": "music.mp3",
                    "type": "audio/mpeg",
                    "duration": 180.0,
                },
            },
        })

        # Create a source file
        src_dir = sources_dir("demo", root=projects_root)
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "music.mp3").write_text("fake audio data", encoding="utf-8")

        # Write registry sidecar for existing lookup
        _write_json(tl_dir / "registry.json", {"assets": {"existing": {"file": "old.mp4", "type": "video/mp4"}}})

        # Create manifest
        manifest_path = tmp_path / "manifest.json"
        _write_json(manifest_path, {
            "assets": {
                "my-key": {"source_id": "src-abc"},
            },
        })

        event = sync_asset_registry(
            "demo",
            "main",
            manifest_path=manifest_path,
            root=projects_root,
        )

        assert event is not None
        assert event.kind == "timeline.asset_registry_replaced"
        assert event.payload.source == "other"  # type: ignore[union-attr]

        registry = event.payload.registry  # type: ignore[union-attr]
        assets = registry["assets"]
        assert "existing" in assets  # merge preserves unrelated entries
        assert "my-key" in assets
        assert assets["my-key"]["file"] == "music.mp3"
        assert assets["my-key"]["type"] == "audio/mpeg"
        assert assets["my-key"]["duration"] == 180.0

        # registry.json sidecar updated
        persisted = json.loads((tl_dir / "registry.json").read_text(encoding="utf-8"))
        assert "my-key" in persisted["assets"]

    def test_merge_preserves_unrelated_entries(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Merge preserves unrelated entries; no implicit pruning."""
        from astrid.core.project.project import create_project as _create_project

        projects_root = tmp_path / "asset-sync-projects"
        projects_root.mkdir(parents=True)
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

        _create_project("demo", root=projects_root)
        tl_result = create_timeline("demo", "main", is_default=True, root=projects_root)
        tl_ulid = tl_result["ulid"]
        tl_dir = timeline_dir("demo", tl_ulid, root=projects_root)

        proj_dir = project_dir("demo", root=projects_root)
        _write_json(proj_dir / "sources.json", {
            "version": 1,
            "sources": {
                "src-1": {"file": "a.mp4", "type": "video/mp4", "duration": 10},
            },
        })
        src_dir = sources_dir("demo", root=projects_root)
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "a.mp4").write_text("a", encoding="utf-8")

        _write_json(tl_dir / "registry.json", {
            "assets": {
                "unrelated": {"file": "old.mp4", "type": "video/mp4"},
                "also-here": {"url": "https://example.com/x.mp4"},
            },
        })

        manifest_path = tmp_path / "manifest.json"
        _write_json(manifest_path, {
            "assets": {"new-one": {"source_id": "src-1"}},
        })

        event = sync_asset_registry("demo", "main", manifest_path=manifest_path, root=projects_root)
        assert event is not None
        assets = event.payload.registry["assets"]  # type: ignore[union-attr]
        assert "unrelated" in assets
        assert "also-here" in assets
        assert "new-one" in assets
        assert len(assets) == 3  # no implicit pruning

    def test_noop_when_registry_unchanged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """No-op skipped when merged registry equals current."""
        from astrid.core.project.project import create_project as _create_project

        projects_root = tmp_path / "asset-sync-projects"
        projects_root.mkdir(parents=True)
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

        _create_project("demo", root=projects_root)
        tl_result = create_timeline("demo", "main", is_default=True, root=projects_root)
        tl_ulid = tl_result["ulid"]
        tl_dir = timeline_dir("demo", tl_ulid, root=projects_root)

        proj_dir = project_dir("demo", root=projects_root)
        _write_json(proj_dir / "sources.json", {
            "version": 1,
            "sources": {
                "src-1": {"file": "a.mp4", "type": "video/mp4", "duration": 10},
            },
        })
        src_dir = sources_dir("demo", root=projects_root)
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "a.mp4").write_text("a", encoding="utf-8")

        existing = {"assets": {"k1": {"file": "a.mp4", "type": "video/mp4"}}}
        _write_json(tl_dir / "registry.json", existing)

        manifest_path = tmp_path / "manifest.json"
        _write_json(manifest_path, {"assets": {"k1": {"file": "a.mp4"}}})

        event = sync_asset_registry("demo", "main", manifest_path=manifest_path, root=projects_root)
        assert event is None  # no-op

    def test_stale_cas_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Stale CAS (EventLogStaleVersionError)."""
        from astrid.core.project.project import create_project as _create_project
        from astrid.core.timeline.eventlog import EventLogStaleVersionError

        projects_root = tmp_path / "asset-sync-projects"
        projects_root.mkdir(parents=True)
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

        _create_project("demo", root=projects_root)
        tl_result = create_timeline("demo", "main", is_default=True, root=projects_root)
        tl_ulid = tl_result["ulid"]
        tl_dir = timeline_dir("demo", tl_ulid, root=projects_root)

        proj_dir = project_dir("demo", root=projects_root)
        _write_json(proj_dir / "sources.json", {
            "version": 1,
            "sources": {
                "src-1": {"file": "a.mp4", "type": "video/mp4", "duration": 10},
            },
        })
        src_dir = sources_dir("demo", root=projects_root)
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "a.mp4").write_text("a", encoding="utf-8")

        _write_json(tl_dir / "registry.json", {"assets": {}})

        manifest_path = tmp_path / "manifest.json"
        _write_json(manifest_path, {"assets": {"k1": {"source_id": "src-1"}}})

        # expected_version=999 should fail since current version is < 999
        with pytest.raises(EventLogStaleVersionError):
            sync_asset_registry("demo", "main", manifest_path=manifest_path, expected_version=999, root=projects_root)

    def test_containment_rejection_in_sync(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Containment rejection: file outside sources/ root."""
        from astrid.core.project.project import create_project as _create_project

        projects_root = tmp_path / "asset-sync-projects"
        projects_root.mkdir(parents=True)
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

        _create_project("demo", root=projects_root)
        create_timeline("demo", "main", is_default=True, root=projects_root)

        manifest_path = tmp_path / "manifest.json"
        _write_json(manifest_path, {"assets": {"k1": {"file": "../evil.txt"}}})

        with pytest.raises(AstridError, match="not under the project sources"):
            sync_asset_registry("demo", "main", manifest_path=manifest_path, root=projects_root)

    def test_url_mapping(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """URL and local mappings work."""
        from astrid.core.project.project import create_project as _create_project

        projects_root = tmp_path / "asset-sync-projects"
        projects_root.mkdir(parents=True)
        monkeypatch.setenv("ASTRID_PROJECTS_ROOT", str(projects_root))

        _create_project("demo", root=projects_root)
        tl_result = create_timeline("demo", "main", is_default=True, root=projects_root)
        tl_ulid = tl_result["ulid"]
        tl_dir = timeline_dir("demo", tl_ulid, root=projects_root)

        proj_dir = project_dir("demo", root=projects_root)
        _write_json(proj_dir / "sources.json", {
            "version": 1,
            "sources": {
                "src-url": {
                    "url": "https://cdn.example.com/song.mp3",
                    "type": "audio/mpeg",
                    "duration": 240,
                },
            },
        })

        _write_json(tl_dir / "registry.json", {"assets": {}})

        manifest_path = tmp_path / "manifest.json"
        _write_json(manifest_path, {"assets": {"song": {"source_id": "src-url"}}})

        event = sync_asset_registry("demo", "main", manifest_path=manifest_path, root=projects_root)
        assert event is not None
        assets = event.payload.registry["assets"]  # type: ignore[union-attr]
        assert assets["song"]["url"] == "https://cdn.example.com/song.mp3"
        assert assets["song"]["type"] == "audio/mpeg"
        assert assets["song"]["duration"] == 240
