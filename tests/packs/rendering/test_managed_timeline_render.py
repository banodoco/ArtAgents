"""Contracts for canonical managed rendering through an explicit runtime client."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("banodoco_timeline_schema")

from astrid.packs.rendering.executors.render.managed_timeline import (
    ManagedRenderValidationError,
    materialize_managed_render_snapshot,
    resolve_managed_render_snapshot,
    validate_managed_render_snapshot,
)
from astrid.sdk.exceptions import CapabilityValidationError
from astrid.sdk.invocation import _prepare_managed_render_inputs


def _result(data: object = None, *, ok: bool = True) -> SimpleNamespace:
    return SimpleNamespace(ok=ok, data=data, error=None if ok else {"message": "not found"})


class _Runtime:
    def __init__(self, *, media: list[dict] | None = None, archived: bool = False) -> None:
        self.media_rows = media or []
        self.project = {"id": "project-demo", "project_id": "project-demo", "slug": "demo"}
        self.timeline = {
            "timeline_id": "timeline-1",
            "timeline_ulid": "01J00000000000000000000001",
            "project_id": "project-demo",
            "project_slug": "demo",
            "slug": "main",
            "config_version": 1,
            "config": {"tracks": [], "clips": []},
            "registry": {"assets": {}},
            "archived_at": "archived" if archived else None,
        }
        self.projects = SimpleNamespace(show=lambda _ref: _result(self.project))
        self.timelines = SimpleNamespace(
            show=lambda _project, _ref: _result(self.timeline),
            list=lambda _project, **_kwargs: _result(([self.timeline], None)),
        )
        self.media = SimpleNamespace(list=lambda _project: _result(self.media_rows))


def _snapshot(runtime: _Runtime, *, expected_version: int | None = None):
    return resolve_managed_render_snapshot(
        project_ref="demo",
        timeline_ref="main",
        expected_version=expected_version,
        client=runtime,
    )


def test_resolve_requires_explicit_runtime_client_and_pins_runtime_identity() -> None:
    runtime = _Runtime()
    snapshot = _snapshot(runtime, expected_version=1)
    assert snapshot.project_id == "project-demo"
    assert snapshot.timeline_id == "timeline-1"
    assert snapshot.registry == {"assets": {}}


def test_materialize_writes_deterministic_private_snapshot(tmp_path: Path) -> None:
    timeline_path, registry_path, authority = materialize_managed_render_snapshot(
        tmp_path, _snapshot(_Runtime())
    )
    assert json.loads(timeline_path.read_text()) == {"tracks": [], "clips": []}
    assert json.loads(registry_path.read_text()) == {"assets": {}}
    assert authority["authority"] == "kernel"
    assert authority["project_slug"] == "demo"
    assert timeline_path.parent.name == registry_path.parent.name


def test_runtime_admitted_media_stays_an_identity_not_a_local_cas_path(tmp_path: Path) -> None:
    digest = "a" * 64
    runtime = _Runtime(media=[{"media_id": "media-1", "digest": digest}])
    runtime.timeline["registry"] = {"assets": {"hero": {"media_id": "media-1", "content_sha256": digest}}}
    snapshot = _snapshot(runtime)
    asset = snapshot.registry["assets"]["hero"]
    assert asset["media_id"] == "media-1"
    assert asset["content_sha256"] == digest
    assert "file" not in asset
    assert ".astrid" not in json.dumps(snapshot.registry)


def test_runtime_media_identity_mismatch_fails_closed() -> None:
    runtime = _Runtime(media=[{"media_id": "media-1", "digest": "a" * 64}])
    runtime.timeline["registry"] = {"assets": {"hero": {"media_id": "media-1", "content_sha256": "b" * 64}}}
    with pytest.raises(ManagedRenderValidationError, match="does not match"):
        _snapshot(runtime)


def test_retired_locator_is_rejected_before_runtime_materialization() -> None:
    runtime = _Runtime()
    runtime.timeline["registry"] = {"assets": {"hero": {"file": "/tmp/hero.mp4", "media_id": "media-1"}}}
    with pytest.raises(ManagedRenderValidationError, match="retired media locator"):
        _snapshot(runtime)


def test_stale_and_archived_timelines_are_rejected() -> None:
    with pytest.raises(ValueError, match="stale timeline version"):
        _snapshot(_Runtime(), expected_version=2)
    with pytest.raises(ValueError, match="is archived"):
        _snapshot(_Runtime(archived=True))


def test_managed_preflight_requires_runtime_ref_and_rejects_file_mode(tmp_path: Path) -> None:
    with pytest.raises(CapabilityValidationError, match="requires timeline_ref"):
        _prepare_managed_render_inputs({}, project="demo", project_root=tmp_path)
    with pytest.raises(CapabilityValidationError, match="mutually exclusive"):
        _prepare_managed_render_inputs(
            {"timeline": "export.json", "timeline_ref": "main"},
            project="demo",
            project_root=tmp_path,
        )


def test_snapshot_validation_rejects_missing_registry_asset() -> None:
    runtime = _Runtime()
    runtime.timeline["config"] = {
        "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
        "clips": [{"id": "source", "at": 0, "track": "visual", "clipType": "video", "asset": "missing"}],
    }
    with pytest.raises(ValueError, match="missing registry asset"):
        validate_managed_render_snapshot(_snapshot(runtime))
