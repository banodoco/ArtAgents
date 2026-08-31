"""Adversarial proof for the runtime-managed media-only live lane."""

from __future__ import annotations

import hashlib
import json
import ast
import inspect
from pathlib import Path

import pytest

from astrid.core.rendering.assets import AssetMaterializer
from astrid.core.timeline.resolution import classify_asset
from astrid.core.timeline.resolution import AssetIntegrity


def _registry(path: Path, entry: dict) -> Path:
    path.write_text(json.dumps({"assets": {"main": entry}}), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "entry",
    [
        {"url": "https://example.invalid/asset.mp4"},
        {"file": "/tmp/asset.mp4"},
        {"path": "../asset.mp4"},
        {"locator": "external-local:///asset.mp4", "realm": "external_local"},
    ],
)
def test_live_classifier_rejects_url_file_path_and_external_local(entry: dict, tmp_path: Path) -> None:
    result = classify_asset("main", entry, project_ref="main")
    assert result.state == "unsupported"
    assert "retired" in result.reason


def test_live_classifier_requires_project_scoped_runtime_admission(tmp_path: Path) -> None:
    payload = b"runtime bytes"
    digest = hashlib.sha256(payload).hexdigest()
    entry = {"object_id": "obj-a", "content_sha256": digest}
    admitted = [{"object_id": "obj-a", "digest": digest}]
    assert classify_asset("main", entry, project_ref="main", media_snapshot=admitted).state == "verified_original"
    foreign = [{"object_id": "obj-a", "digest": hashlib.sha256(b"foreign").hexdigest()}]
    assert classify_asset("main", entry, project_ref="main", media_snapshot=foreign).state == "unsupported"
    cross_project = [{"object_id": "obj-a", "digest": digest, "project_ref": "other"}]
    assert classify_asset("main", entry, project_ref="main", media_snapshot=cross_project).state == "unsupported"


@pytest.mark.parametrize("snapshot", [
    {"items": [{"object_id": "obj-a", "digest": "a" * 64}]},
    {"obj-a": {"digest": "a" * 64}},
    [[{"object_id": "obj-a", "digest": "a" * 64}], "cursor-1"],
])
def test_live_classifier_rejects_mapping_or_incomplete_media_snapshots(snapshot) -> None:
    entry = {"object_id": "obj-a", "content_sha256": "a" * 64}
    assert classify_asset(
        "main", entry, project_ref="main", media_snapshot=snapshot
    ).state == "unsupported"


def test_materializer_stages_only_verified_runtime_object_bytes(tmp_path: Path) -> None:
    payload = b"runtime bytes"
    digest = hashlib.sha256(payload).hexdigest()
    source = tmp_path / "attempt-object"
    source.write_bytes(payload)
    registry = _registry(tmp_path / "assets.json", {"object_id": "obj-a", "digest": digest})
    with AssetMaterializer(registry, materialized_objects={"obj-a": source}, materialized_root=tmp_path) as materializer:
        staged = materializer.assets["main"].local_path
        assert staged is not None and staged.read_bytes() == payload
        assert materializer.assets["main"].kind == "managed"


def test_materializer_rejects_tampered_or_foreign_materialization(tmp_path: Path) -> None:
    payload = b"runtime bytes"
    digest = hashlib.sha256(payload).hexdigest()
    registry = _registry(tmp_path / "assets.json", {"object_id": "obj-a", "digest": digest})
    foreign_root = tmp_path.parent / f"foreign-{tmp_path.name}"
    foreign_root.mkdir()
    source = foreign_root / "object"
    source.write_bytes(payload)
    with pytest.raises(ValueError, match="materialized_root"):
        AssetMaterializer(registry, materialized_objects={"obj-a": source})
    with pytest.raises(ValueError, match="outside"):
        AssetMaterializer(registry, materialized_objects={"obj-a": source}, materialized_root=tmp_path)


def test_live_media_modules_have_no_locator_fetch_or_resolution_authority() -> None:
    root = Path(__file__).parents[2]
    resolution = (root / "astrid/core/timeline/resolution.py").read_text(encoding="utf-8")
    assets = (root / "astrid/core/rendering/assets.py").read_text(encoding="utf-8")
    task_adapter = (root / "astrid/packs/rendering/executors/render/task_adapter.py").read_text(encoding="utf-8")
    assert "urllib.request" not in assets
    assert "asset_cache" not in assets
    assert "original_reference" not in assets
    assert "remote_url" not in assets
    assert "mode" not in assets
    assert "managed_media_path" not in task_adapter
    assert ".astrid" not in task_adapter
    assert "materialized_objects" in task_adapter
    assert "resolve_asset_local_path" not in resolution
    assert "resolve_asset_authorized_path" not in resolution
    assert "managed_locator_digest" not in resolution
    assert "project_root" not in resolution
    assert "path:" not in resolution
    assert "path" not in {field.name for field in AssetIntegrity.__dataclass_fields__.values()}
    managed_timeline = (root / "astrid/packs/rendering/executors/render/managed_timeline.py").read_text(encoding="utf-8")
    assert "client is None" not in managed_timeline
    assert "AstridClient.open" not in managed_timeline
    assert "projects_root" not in str(inspect.signature(__import__(
        "astrid.packs.rendering.executors.render.managed_timeline",
        fromlist=["resolve_managed_render_snapshot"],
    ).resolve_managed_render_snapshot))
    assert not (root / "astrid/core/io/managed_media_resolver.py").exists()
    assert not (root / "astrid/core/io/media_import.py").exists()
    assert not (root / "astrid/core/migrations").exists()
    tree = ast.parse(resolution)
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "resolve" for node in ast.walk(tree))
