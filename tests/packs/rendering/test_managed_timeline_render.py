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
        self.extra_timelines: dict[str, dict] = {}
        self.shot_rows: dict[str, dict] = {}
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
        self.timelines = SimpleNamespace(show=self._show_timeline, list=self._list_timelines)
        self.media = SimpleNamespace(list=lambda _project: _result(self.media_rows))
        self.shots = SimpleNamespace(show=self._show_shot)

    def _show_timeline(self, _project: str, ref: str):
        row = self.extra_timelines.get(ref)
        if row is None and ref not in {
            self.timeline["timeline_id"], self.timeline["timeline_ulid"], self.timeline["slug"],
            "11111111-1111-4111-8111-111111111111",
        }:
            row = next((item for item in self.extra_timelines.values() if ref in {
                item.get("timeline_id"), item.get("timeline_ulid"), item.get("slug")
            }), None)
        return _result(row or self.timeline)

    def _list_timelines(self, _project: str, **_kwargs: object):
        return _result([self.timeline, *self.extra_timelines.values()])

    def _show_shot(self, _project: str, ref: str):
        row = self.shot_rows.get(ref)
        return _result(row, ok=row is not None)


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


@pytest.mark.parametrize("timeline_ref", [
    "main",
    "11111111-1111-4111-8111-111111111111",
    "01J00000000000000000000001",
])
def test_resolve_accepts_slug_uuid_and_ulid_runtime_references(timeline_ref: str) -> None:
    runtime = _Runtime()
    snapshot = resolve_managed_render_snapshot(
        project_ref="demo", timeline_ref=timeline_ref, client=runtime
    )
    assert snapshot.timeline_id == "timeline-1"
    assert snapshot.timeline_slug == "main"


def test_materialization_records_authority_and_content_hashes(tmp_path: Path) -> None:
    snapshot = _snapshot(_Runtime())
    timeline_path, registry_path, authority = materialize_managed_render_snapshot(tmp_path, snapshot)
    assert timeline_path.is_file() and registry_path.is_file()
    assert authority["head_event_id"] == "timeline:timeline-1:1"
    for field in ("head_hash", "config_hash", "registry_hash", "materialized_registry_hash"):
        assert len(authority[field]) == 64
    assert authority["config_hash"] == snapshot.config_hash
    assert authority["registry_hash"] == snapshot.registry_hash


def test_authority_uses_runtime_event_head_hash_when_available() -> None:
    runtime = _Runtime()
    runtime.app = SimpleNamespace(event_log=SimpleNamespace(list_events=lambda **_kwargs: [
        SimpleNamespace(subject_id="timeline-1", seq=1, event_id="event-1", event_hash="f" * 64)
    ]))
    snapshot = _snapshot(runtime)
    assert snapshot.head_event_id == "event-1"
    assert snapshot.head_hash == "f" * 64


def test_unadmitted_and_foreign_runtime_media_fail_closed() -> None:
    timeline = _Runtime()
    timeline.timeline["registry"] = {"assets": {"hero": {"media_id": "m1", "content_sha256": "a" * 64}}}
    with pytest.raises(ManagedRenderValidationError, match="not admitted"):
        _snapshot(timeline)

    foreign = _Runtime(media=[{"media_id": "m1", "digest": "a" * 64, "project_slug": "other"}])
    foreign.timeline["registry"] = timeline.timeline["registry"]
    with pytest.raises(ManagedRenderValidationError, match="not admitted"):
        _snapshot(foreign)


def test_conflicting_runtime_media_aliases_fail_closed() -> None:
    runtime = _Runtime(media=[{"media_id": "m1", "digest": "a" * 64}])
    runtime.timeline["registry"] = {"assets": {
        "one": {"media_id": "m1", "content_sha256": "a" * 64},
        "two": {"media_id": "m1", "content_sha256": "b" * 64},
    }}
    with pytest.raises(ManagedRenderValidationError, match="conflicting entries"):
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


def test_snapshot_validation_rejects_incomplete_config_output() -> None:
    runtime = _Runtime()
    runtime.timeline["config"] = {"tracks": [], "clips": [], "output": {"resolution": [1920, 1080]}}
    with pytest.raises(ValueError, match="config.output is incomplete.*fps.*file"):
        validate_managed_render_snapshot(_snapshot(runtime))


def _profile() -> dict[str, object]:
    return {
        "width": 1920, "height": 1080, "fps_rational": [30, 1],
        "time_base": [1, 90000], "container": "mp4", "video_codec": "h264",
        "video_profile": None, "video_level": None, "pixel_format": "yuv420p",
        "audio_codec": "aac", "audio_sample_rate": 48000,
        "audio_channel_layout": "stereo", "duration_tolerance": 1,
    }


def test_render_profile_shape_type_and_canvas_mismatch_are_actionable(tmp_path: Path) -> None:
    runtime = _Runtime()
    with pytest.raises(CapabilityValidationError, match="flat RenderProfile v1"):
        _prepare_managed_render_inputs({"timeline_ref": "main", "profile": {"video": {}}}, project="demo", project_root=tmp_path, _client=runtime)
    bad_type = _profile(); bad_type["width"] = "1920"
    with pytest.raises(CapabilityValidationError, match="width must be an integer"):
        _prepare_managed_render_inputs({"timeline_ref": "main", "profile": bad_type}, project="demo", project_root=tmp_path, _client=runtime)
    bad_canvas = _profile(); bad_canvas.update(width=320, height=180, fps_rational=[24, 1])
    with pytest.raises(CapabilityValidationError, match="authoritative theme canvas"):
        _prepare_managed_render_inputs({"timeline_ref": "main", "profile": bad_canvas}, project="demo", project_root=tmp_path, _client=runtime)


def test_registered_shot_expands_and_unknown_shot_rejects(tmp_path: Path) -> None:
    runtime = _Runtime()
    runtime.shot_rows["shot-1"] = {"shot_id": "shot-1", "project_id": "project-demo"}
    runtime.extra_timelines["child"] = {
        "timeline_id": "child-1", "timeline_ulid": "01J00000000000000000000002", "slug": "child",
        "config_version": 1, "config": {"tracks": [], "clips": []}, "registry": {}, "archived_at": None,
    }
    runtime.timeline["config"] = {"tracks": [], "clips": [{
        "id": "shot", "at": 0, "hold": 1, "clipType": "shot",
        "params": {"shot_id": "shot-1", "timeline_document_id": "child"},
    }]}
    prepared, authority = _prepare_managed_render_inputs(
        {"timeline_ref": "main"}, project="demo", project_root=tmp_path, _client=runtime
    )
    assert all(item.get("clipType") != "shot" for item in json.loads(Path(prepared["timeline"]).read_text())["clips"])
    assert authority and authority["expansion"]["children"][0]["timeline_id"] == "child-1"

    runtime.shot_rows.clear()
    with pytest.raises(CapabilityValidationError, match="unregistered shot"):
        _prepare_managed_render_inputs({"timeline_ref": "main"}, project="demo", project_root=tmp_path, _client=runtime)


def test_unknown_effect_structured_schema_and_opaque_params_contracts() -> None:
    runtime = _Runtime()
    runtime.timeline["config"] = {"tracks": [{"id": "v", "kind": "visual", "label": "Visual"}], "clips": [{
        "id": "unknown", "at": 0, "track": "v", "clipType": "missing-effect", "hold": 1,
        "params": {"vendor": {"effect": "not-an-element"}},
    }]}
    with pytest.raises(ManagedRenderValidationError, match="unregistered reusable visual element"):
        validate_managed_render_snapshot(_snapshot(runtime))

    runtime.timeline["config"]["clips"][0]["clipType"] = "text"
    runtime.timeline["config"]["clips"][0]["effects"] = [{"id": "bad", "params": {"amount": 1}}]
    with pytest.raises(ManagedRenderValidationError) as error:
        validate_managed_render_snapshot(_snapshot(runtime))
    assert error.value.details["path"].startswith("$.clips[0].effects")

    runtime.timeline["config"]["clips"][0].pop("effects")
    validate_managed_render_snapshot(_snapshot(runtime))


def test_alpha_mov_compatibility_requires_matching_profile(tmp_path: Path) -> None:
    runtime = _Runtime()
    runtime.timeline["config"] = {"metadata": {"astrid_layer": {"alpha": True}}, "tracks": [], "clips": []}
    with pytest.raises(CapabilityValidationError, match="incompatible explicit render profile"):
        profile = _profile(); profile["container"] = "mov"
        _prepare_managed_render_inputs({"timeline_ref": "main", "output_name": "alpha.mov", "profile": profile}, project="demo", project_root=tmp_path, _client=runtime)
    profile = _profile(); profile.update(container="mov", video_codec="prores", pixel_format="yuva444p12le", audio_codec="pcm_s16le")
    prepared, _authority = _prepare_managed_render_inputs({"timeline_ref": "main", "output_name": "alpha.mov", "profile": profile}, project="demo", project_root=tmp_path, _client=runtime)
    assert prepared["profile"] == profile
