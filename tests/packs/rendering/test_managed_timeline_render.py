"""Focused contracts for the explicit canonical managed render mode."""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.packs.rendering.executors.render.managed_timeline import (
    materialize_managed_render_snapshot,
    resolve_managed_render_snapshot,
    validate_managed_render_snapshot,
)
from astrid.packs.rendering.executors.render.run import (
    _rewrite_provenance_output_path,
)
from astrid.sdk import invoke_result
from astrid.sdk.client import AstridClient
from astrid.sdk.exceptions import CapabilityValidationError
from astrid.sdk.invocation import _prepare_managed_render_inputs, _render_profile_guidance


def test_managed_snapshot_uses_runtime_client_without_local_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The resolver may materialize under a local root, but reads use runtime.

    ``AstridClient.open`` intentionally has no ``projects_root`` argument after
    the local-application cutover.  Keep this seam explicit so a renderer
    cannot accidentally recreate local kernel authority.
    """

    timeline_id = "11111111-1111-4111-8111-111111111111"
    timeline = {
        "timeline_id": timeline_id,
        "timeline_ulid": "01J00000000000000000000000",
        "slug": "main",
        "config_version": 1,
        "config": {"tracks": [], "clips": []},
        "registry": {"assets": {}},
    }
    response = lambda data: SimpleNamespace(ok=True, data=data)

    class _RuntimeClient:
        projects = SimpleNamespace(show=lambda _ref: response({"id": "p1", "slug": "demo"}))
        timelines = SimpleNamespace(
            show=lambda _project, _ref: response(timeline),
            list=lambda _project, **_kwargs: response([timeline]),
        )

        def close(self) -> None:
            pass

        def __enter__(self) -> "_RuntimeClient":
            return self

        def __exit__(self, *_exc: object) -> None:
            self.close()

    calls: list[tuple[object, ...]] = []

    def _open(cls, *args: object, **kwargs: object) -> _RuntimeClient:
        calls.append(args)
        assert not kwargs
        return _RuntimeClient()

    monkeypatch.setattr(AstridClient, "open", classmethod(_open))
    snapshot = resolve_managed_render_snapshot(
        tmp_path, project_ref="demo", timeline_ref="main", expected_version=1
    )

    assert snapshot.timeline_id == timeline_id
    assert calls == [()]


def _managed_timeline(projects: Path) -> dict:
    with AstridClient.open(projects_root=projects) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="main",
            name="Main",
            config={"tracks": [], "clips": []},
            registry={"assets": {}},
            set_default=True,
        )
        assert created.ok and created.data is not None
        return created.data


def _explicit_remotion_profile() -> dict:
    return {
        "width": 1920,
        "height": 1080,
        "fps_rational": [30, 1],
        "time_base": [1, 90000],
        "container": "mp4",
        "video_codec": "h264",
        "video_profile": None,
        "video_level": None,
        "pixel_format": "yuv420p",
        "audio_codec": "aac",
        "audio_sample_rate": 48000,
        "audio_channel_layout": "stereo",
        "duration_tolerance": 1,
    }


def _alpha_timeline(projects: Path, *, slug: str = "alpha") -> dict:
    with AstridClient.open(projects_root=projects) as client:
        if not (projects / "demo" / "project.json").is_file():
            assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug=slug,
            name="Alpha",
            config={
                "metadata": {"astrid_layer": {"z": 1, "alpha": True}},
                "tracks": [],
                "clips": [],
            },
            registry={"assets": {}},
        )
        assert created.ok and created.data is not None
        return created.data


def test_managed_render_snapshot_pins_kernel_authority_and_materializes(tmp_path: Path) -> None:
    created = _managed_timeline(tmp_path)

    snapshot = resolve_managed_render_snapshot(
        tmp_path, project_ref="demo", timeline_ref="main", expected_version=1
    )
    timeline, registry, authority = materialize_managed_render_snapshot(
        tmp_path, snapshot
    )

    assert authority["authority"] == "kernel"
    assert authority["timeline_id"] == created["timeline_id"]
    assert authority["config_version"] == 1
    assert len(authority["head_hash"]) == 64
    assert len(authority["config_hash"]) == 64
    assert len(authority["registry_hash"]) == 64
    assert len(authority["materialized_registry_hash"]) == 64
    assert json.loads(timeline.read_text()) == {"tracks": [], "clips": []}
    assert json.loads(registry.read_text()) == {"assets": {}}
    assert timeline.parent == registry.parent
    assert timeline.parent.parent.name == "render-snapshots"
    for ref in (created["timeline_id"], created["timeline_ulid"]):
        resolved = resolve_managed_render_snapshot(
            tmp_path, project_ref="demo", timeline_ref=ref, expected_version=1
        )
        assert resolved.timeline_id == created["timeline_id"]


def test_managed_render_snapshot_rejects_stale_and_archived_before_admission(
    tmp_path: Path,
) -> None:
    _managed_timeline(tmp_path)
    with AstridClient.open(projects_root=tmp_path) as client:
        saved = client.timelines.save(
            "demo",
            "main",
            config={"tracks": [], "clips": []},
            registry={"assets": {}},
            expected_version=1,
        )
        assert saved.ok

    with pytest.raises(ValueError, match="stale timeline version"):
        resolve_managed_render_snapshot(
            tmp_path, project_ref="demo", timeline_ref="main", expected_version=1
        )

    with AstridClient.open(projects_root=tmp_path) as client:
        archived = client.timelines.archive("demo", "main")
        assert archived.ok
    with pytest.raises(ValueError, match="is archived"):
        resolve_managed_render_snapshot(
            tmp_path, project_ref="demo", timeline_ref="main"
        )


def test_canonical_provenance_stamp_fails_closed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ASTRID_INTERNAL_INVOCATION", "1")
    output = tmp_path / "video.mp4"
    output.write_bytes(b"video")

    with pytest.raises(RuntimeError, match="required to stamp"):
        _rewrite_provenance_output_path(
            output, timeline_authority={"authority": "kernel"}
        )


def test_render_requires_exactly_one_explicit_input_mode(tmp_path: Path) -> None:
    with pytest.raises(CapabilityValidationError, match="exactly one input mode"):
        _prepare_managed_render_inputs({}, project="demo", project_root=tmp_path)
    with pytest.raises(CapabilityValidationError, match="mutually exclusive"):
        _prepare_managed_render_inputs(
            {"timeline": "export.json", "timeline_ref": "main"},
            project="demo",
            project_root=tmp_path,
        )


def test_managed_render_rejects_incomplete_output_before_materialization(
    tmp_path: Path,
) -> None:
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="draft",
            name="Draft",
            config={
                "tracks": [],
                "clips": [],
                "output": {"file": "draft.mp4"},
            },
            registry={"assets": {}},
        )
        assert created.ok

    with pytest.raises(
        CapabilityValidationError,
        match=r"config\.output is incomplete; missing required field\(s\): resolution, fps",
    ):
        _prepare_managed_render_inputs(
            {"timeline_ref": "draft", "expected_version": 1},
            project="demo",
            project_root=tmp_path,
        )

    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_managed_render_preflight_rejects_missing_registry_asset(tmp_path: Path) -> None:
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="missing-asset",
            name="Missing asset",
            config={
                "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
                "clips": [
                    {
                        "id": "source",
                        "at": 0,
                        "track": "visual",
                        "clipType": "video",
                        "asset": "not-registered",
                        "from": 0,
                        "to": 1,
                    }
                ],
            },
            registry={"assets": {}},
        )
        assert created.ok

    snapshot = resolve_managed_render_snapshot(
        tmp_path,
        project_ref="demo",
        timeline_ref="missing-asset",
        expected_version=1,
    )
    with pytest.raises(ValueError, match="missing registry asset id.*not-registered"):
        validate_managed_render_snapshot(snapshot)


def test_failed_exact_replay_preserves_actionable_handler_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _managed_timeline(tmp_path)

    def fail_with_detail(self, *, task, staging_dir):  # noqa: ANN001
        raise RuntimeError("actionable renderer failure")

    monkeypatch.setattr(
        "astrid.core.task_executor.CapabilityTaskHandler.execute",
        fail_with_detail,
    )

    kwargs = {
        "kind": "executor",
        "project": "demo",
        "project_root": tmp_path,
        "inputs": {"timeline_ref": "main", "expected_version": 1},
    }
    first = invoke_result("rendering.render", **kwargs)
    replay = invoke_result("rendering.render", **kwargs)

    assert first.ok is False
    assert replay.ok is False
    assert first.kernel_run_id == replay.kernel_run_id
    assert first.kernel_task_id == replay.kernel_task_id
    assert first.kernel_attempt_id == replay.kernel_attempt_id
    assert first.error is not None
    assert replay.error is not None
    assert first.error["message"] == "actionable renderer failure"
    assert replay.error["message"] == "actionable renderer failure"
    assert replay.error["sdk_category"] == "runtime"


def test_nested_render_profile_reports_missing_and_unknown_before_materialization(
    tmp_path: Path,
) -> None:
    _managed_timeline(tmp_path)

    with pytest.raises(CapabilityValidationError) as exc_info:
        _prepare_managed_render_inputs(
            {
                "timeline_ref": "main",
                "expected_version": 1,
                "profile": {
                    "video": {"width": 320, "height": 180, "codec": "h264"},
                    "audio": {"codec": "aac", "sample_rate": 48000},
                },
            },
            project="demo",
            project_root=tmp_path,
        )

    message = str(exc_info.value)
    assert "missing required field(s): width, height, fps_rational" in message
    assert "unknown field(s): audio, video" in message
    assert "flat RenderProfile v1 object (no video/audio nesting)" in message
    assert "Complete Remotion MP4 example" in message
    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_render_profile_guidance_matches_default_canvas() -> None:
    guidance = _render_profile_guidance()

    assert '"width":1920' in guidance
    assert '"height":1080' in guidance
    assert "match the authoritative theme canvas" in guidance


def test_managed_render_rejects_profile_canvas_mismatch_before_materialization(
    tmp_path: Path,
) -> None:
    _managed_timeline(tmp_path)
    profile = _explicit_remotion_profile()
    profile.update(width=320, height=180, fps_rational=[24, 1])

    with pytest.raises(
        CapabilityValidationError,
        match="authoritative theme canvas",
    ) as exc_info:
        _prepare_managed_render_inputs(
            {"timeline_ref": "main", "expected_version": 1, "profile": profile},
            project="demo",
            project_root=tmp_path,
        )

    message = str(exc_info.value)
    assert "fps_rational=[24, 1]" in message
    assert "authoritative theme canvas produces [30, 1]" in message
    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_render_profile_type_error_is_actionable_before_materialization(
    tmp_path: Path,
) -> None:
    _managed_timeline(tmp_path)
    profile = _explicit_remotion_profile()
    profile["width"] = "320"

    with pytest.raises(CapabilityValidationError, match="width must be an integer"):
        _prepare_managed_render_inputs(
            {"timeline_ref": "main", "expected_version": 1, "profile": profile},
            project="demo",
            project_root=tmp_path,
        )

    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_complete_flat_render_profile_reaches_managed_snapshot(tmp_path: Path) -> None:
    _managed_timeline(tmp_path)
    profile = _explicit_remotion_profile()

    prepared, authority = _prepare_managed_render_inputs(
        {"timeline_ref": "main", "expected_version": 1, "profile": profile},
        project="demo",
        project_root=tmp_path,
    )

    assert prepared["profile"] == profile
    assert Path(prepared["timeline"]).is_file()
    assert Path(prepared["assets_registry"]).is_file()
    assert authority is not None
    assert authority["timeline_slug"] == "main"


def test_managed_render_expands_registered_shot_from_sdk_snapshot(tmp_path: Path) -> None:
    """Composite parents are flattened from client reads before admission."""
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        child = client.timelines.create(
            project="demo",
            slug="child",
            name="Child",
            config={"tracks": [], "clips": []},
            registry={"assets": {}},
            idempotency_key="child-create",
        )
        assert child.ok and child.data
        shot = client.shots.create(
            project="demo",
            name="Shot",
            idempotency_key="shot-create",
        )
        assert shot.ok and shot.data
        parent = client.timelines.create(
            project="demo",
            slug="composite",
            name="Composite",
            config={
                "tracks": [],
                "clips": [
                    {
                        "id": "shot-1",
                        "at": 0,
                        "hold": 2,
                        "clipType": "shot",
                        "params": {
                            "shot_id": shot.data["id"],
                            "timeline_document_id": child.data["timeline_id"],
                        },
                    }
                ],
            },
            registry={"assets": {}},
            idempotency_key="parent-create",
        )
        assert parent.ok
        prepared, authority = _prepare_managed_render_inputs(
            {"timeline_ref": "composite", "expected_version": 1},
            project="demo",
            project_root=tmp_path,
            _client=client,
        )

    rendered = json.loads(Path(prepared["timeline"]).read_text())
    assert all(clip.get("clipType") != "shot" for clip in rendered["clips"])
    assert authority is not None
    assert authority["expansion"]["children"][0]["timeline_id"] == child.data["timeline_id"]
    assert len(authority["expansion"]["expanded_config_hash"]) == 64


def test_managed_render_rejects_unregistered_shot_before_expansion(tmp_path: Path) -> None:
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        parent = client.timelines.create(
            project="demo",
            slug="bad-composite",
            name="Bad composite",
            config={
                "tracks": [],
                "clips": [
                    {
                        "id": "shot-1",
                        "at": 0,
                        "hold": 1,
                        "clipType": "shot",
                        "params": {"shot_id": "missing", "timeline_document_id": "missing"},
                    }
                ],
            },
            registry={"assets": {}},
            idempotency_key="bad-parent-create",
        )
        assert parent.ok
        with pytest.raises(CapabilityValidationError, match="unregistered shot"):
            _prepare_managed_render_inputs(
                {"timeline_ref": "bad-composite", "expected_version": 1},
                project="demo",
                project_root=tmp_path,
                _client=client,
            )


def test_alpha_mov_reaches_managed_snapshot_before_admission(tmp_path: Path) -> None:
    _alpha_timeline(tmp_path)

    prepared, authority = _prepare_managed_render_inputs(
        {
            "timeline_ref": "alpha",
            "expected_version": 1,
            "output_name": "alpha.mov",
        },
        project="demo",
        project_root=tmp_path,
    )

    assert prepared["output_name"] == "alpha.mov"
    assert Path(prepared["timeline"]).is_file()
    assert authority is not None
    assert authority["config_version"] == 1


def test_unstamped_mov_rejects_with_null_kernel_ids_before_materialization(
    tmp_path: Path,
) -> None:
    _managed_timeline(tmp_path)

    result = invoke_result(
        "rendering.render",
        kind="executor",
        project="demo",
        project_root=tmp_path,
        inputs={
            "timeline_ref": "main",
            "expected_version": 1,
            "output_name": "opaque.mov",
        },
    )

    assert result.ok is False
    assert result.kernel_run_id is None
    assert result.kernel_task_id is None
    assert result.kernel_attempt_id is None
    assert result.error is not None
    assert result.error["sdk_category"] == "validation"
    assert "not stamped" in result.error["message"]
    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()
    with AstridClient.open(projects_root=tmp_path) as client:
        listed = client.runs.list("demo")
        assert listed.ok and listed.data == []


def test_incompatible_explicit_alpha_mov_rejects_before_materialization(
    tmp_path: Path,
) -> None:
    _alpha_timeline(tmp_path)
    profile = _explicit_remotion_profile()
    profile["container"] = "mov"

    with pytest.raises(
        CapabilityValidationError,
        match="incompatible explicit render profile",
    ) as exc_info:
        _prepare_managed_render_inputs(
            {
                "timeline_ref": "alpha",
                "expected_version": 1,
                "output_name": "alpha.mov",
                "profile": profile,
            },
            project="demo",
            project_root=tmp_path,
        )

    assert "video_codec='h264'" in str(exc_info.value)
    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_compatible_explicit_alpha_mov_profile_reaches_snapshot(tmp_path: Path) -> None:
    _alpha_timeline(tmp_path)
    profile = _explicit_remotion_profile()
    profile.update(
        container="mov",
        video_codec="prores",
        pixel_format="yuva444p12le",
        audio_codec="pcm_s16le",
    )

    prepared, authority = _prepare_managed_render_inputs(
        {
            "timeline_ref": "alpha",
            "expected_version": 1,
            "output_name": "alpha.mov",
            "profile": profile,
        },
        project="demo",
        project_root=tmp_path,
    )

    assert prepared["profile"] == profile
    assert authority is not None


def test_managed_render_rejects_unregistered_effect_clip_before_materialization(
    tmp_path: Path,
) -> None:
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="unknown-effect",
            name="Unknown effect",
            config={
                "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
                "clips": [
                    {
                        "id": "unknown",
                        "at": 0,
                        "track": "visual",
                        "clipType": "definitely-missing-effect",
                        "hold": 1,
                        "params": {"vendor_metadata": {"keep": True}},
                    }
                ],
            },
            registry={"assets": {}},
        )
        assert created.ok

    with pytest.raises(CapabilityValidationError) as exc_info:
        _prepare_managed_render_inputs(
            {"timeline_ref": "unknown-effect", "expected_version": 1},
            project="demo",
            project_root=tmp_path,
        )

    assert "$.clips[0].clipType" in str(exc_info.value)
    assert "unregistered reusable visual element id" in str(exc_info.value)
    assert exc_info.value.details["validator"] == "registered_element_reference"
    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_managed_render_schema_error_is_concise_structured_and_actionable(
    tmp_path: Path,
) -> None:
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="bad-effects-envelope",
            name="Bad effects envelope",
            config={
                "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
                "clips": [
                    {
                        "id": "title",
                        "at": 0,
                        "track": "visual",
                        "clipType": "text",
                        "hold": 1,
                        "text": {"content": "Title"},
                        "effects": [{"id": "missing", "params": {"amount": 1}}],
                    }
                ],
            },
            registry={"assets": {}},
        )
        assert created.ok

    with pytest.raises(CapabilityValidationError) as exc_info:
        _prepare_managed_render_inputs(
            {"timeline_ref": "bad-effects-envelope", "expected_version": 1},
            project="demo",
            project_root=tmp_path,
        )

    message = str(exc_info.value)
    assert "Recovery:" in message
    assert "clipType:<effect-id>" in message
    assert "Failed validating" not in message
    assert "On instance" not in message
    assert exc_info.value.details["path"].startswith("$.clips[0].effects")
    assert exc_info.value.details["recovery"].startswith("Use clip.effects")
    assert not (tmp_path / "demo" / ".astrid" / "render-snapshots").exists()


def test_managed_render_does_not_treat_opaque_params_as_element_references(
    tmp_path: Path,
) -> None:
    with AstridClient.open(projects_root=tmp_path) as client:
        assert client.projects.create(slug="demo", name="Demo").ok
        created = client.timelines.create(
            project="demo",
            slug="opaque-params",
            name="Opaque params",
            config={
                "tracks": [{"id": "visual", "kind": "visual", "label": "Visual"}],
                "clips": [
                    {
                        "id": "opaque",
                        "at": 0,
                        "track": "visual",
                        "clipType": "video",
                        "hold": 1,
                        "params": {
                            "vendor": {
                                "effect": "definitely-not-an-element-reference",
                                "nested": [1, 2, 3],
                            }
                        },
                    }
                ],
            },
            registry={"assets": {}},
        )
        assert created.ok

    prepared, authority = _prepare_managed_render_inputs(
        {"timeline_ref": "opaque-params", "expected_version": 1},
        project="demo",
        project_root=tmp_path,
    )

    assert Path(prepared["timeline"]).is_file()
    assert authority is not None


def test_raw_file_render_warns_but_managed_timeline_ref_does_not(tmp_path: Path) -> None:
    raw_timeline = tmp_path / "hype.timeline.json"
    raw_timeline.write_text(json.dumps({"tracks": [], "clips": []}), encoding="utf-8")

    with pytest.warns(RuntimeWarning) as raw_recorded:
        values, authority = _prepare_managed_render_inputs(
            {"timeline": str(raw_timeline)},
            project=None,
            project_root=None,
        )
    assert authority is None
    assert "idempotency" in str(raw_recorded[0].message).lower()
    assert "stale" in str(raw_recorded[0].message)

    _managed_timeline(tmp_path)
    with warnings.catch_warnings(record=True) as managed_recorded:
        warnings.simplefilter("always")
        prepared, managed_authority = _prepare_managed_render_inputs(
            {"timeline_ref": "main"},
            project="demo",
            project_root=tmp_path,
        )
    assert managed_authority is not None
    stale = [
        warning
        for warning in managed_recorded
        if issubclass(warning.category, RuntimeWarning)
        and "idempotency" in str(warning.message)
    ]
    assert stale == []
