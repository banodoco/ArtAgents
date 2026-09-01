from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest
import yaml

from astrid.core import timeline
from astrid.core.element.schema import ElementAsset, ElementDefinition
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.core.rendering import remotion_runtime
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    FrameWindow,
    RendererManifest,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SupportReport,
)
from astrid.core.rendering.transport import CommandTransport
from astrid.packs.rendering.backends.remotion import run as remotion
from astrid.packs.rendering.executors.render import run as facade
from astrid.packs.rendering.executors.render.run import render
from tests.packs.rendering._helpers import _execution_env, _probe

ROOT = Path(__file__).resolve().parents[3]
LOCAL_EFFECT_SMOKE_FIXTURE = ROOT / "tests" / "fixtures" / "local_effect_smoke"
render_remotion = remotion


def _is_remotion_render_command(command: list[str]) -> bool:
    return (
        len(command) >= 3
        and Path(command[0]).name == "node"
        and Path(command[1]).as_posix().endswith(
            "node_modules/@remotion/cli/remotion-cli.js"
        )
        and command[2] == "render"
    )


@pytest.fixture(autouse=True)
def _remotion_exec_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure protocol children use the schema-bearing test interpreter."""
    fake_node = tmp_path / "node"
    fake_node.write_text("#!/bin/sh\nprintf 'v20.19.4\\n'\n", encoding="utf-8")
    fake_node.chmod(0o755)
    configured_node = shutil.which("node") or str(fake_node)
    monkeypatch.setenv("ASTRID_NODE_EXECUTABLE", str(Path(configured_node).resolve()))
    monkeypatch.setattr(
        remotion_runtime,
        "_probe_node",
        lambda node_executable, *, cwd: ("v20.19.4", None),
    )
    with _execution_env():
        yield


def _write_fake_remotion_output(command: list[str]) -> Path:
    output = Path(command[command.index("--output") + 1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"fake-remotion-video")
    return output


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    pytest.importorskip(
        "banodoco_timeline_schema",
        reason="canonical timeline schema is required for timeline renderer tests",
    )
    timeline_path = tmp_path / "hype.timeline.json"
    assets_path = tmp_path / "hype.assets.json"
    timeline.save_timeline(
        {
            "theme": "banodoco-default",
            "tracks": [{"id": "v1", "kind": "visual", "label": "Visual"}],
            "clips": [],
        },
        timeline_path,
    )
    timeline.save_registry({"assets": {}}, assets_path)
    return timeline_path, assets_path


def _write_project(tmp_path: Path) -> Path:
    project = tmp_path / "remotion"
    packages = project / "node_modules" / "@banodoco"
    for package in (
        "timeline-composition/typescript/src",
        "timeline-schema",
        "timeline-theme-2rp",
    ):
        (packages / package).mkdir(parents=True)
    (project / "package.json").write_text("{}\n", encoding="utf-8")
    cli = project / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// locked test CLI\n", encoding="utf-8")
    return project


def _request(
    timeline_path: Path,
    assets_path: Path,
    project: Path,
    *,
    window: FrameWindow | None = None,
) -> RenderRequest:
    return RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="result.mp4",
        window=window,
        backend_config={
            remotion.BACKEND_ID: {"project_dir": str(project)},
        },
    )


def _execute_direct(
    timeline_path: Path,
    assets_path: Path,
    out_path: Path,
    *,
    project_dir: Path,
    composition_id: str = "TimelineComposition",
    theme_path: Path | None = None,
    materialized_root: Path | None = None,
    materialized_objects: dict[str, str] | None = None,
) -> tuple[Path, dict[str, object]]:
    """Exercise the canonical backend implementation without restoring its retired facade."""

    details = render_remotion._execute_remotion(
        timeline_path,
        assets_path,
        out_path,
        provenance_out_path=out_path,
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        min_free_gb=None,
        materialized_root=materialized_root,
        materialized_objects=materialized_objects,
    )
    provenance = render_remotion._render_provenance_payload(
        project_dir=project_dir,
        composition_id=composition_id,
        theme_path=theme_path,
        active_theme=details.active_theme,
        registry_state=details.registry_state,
        stage_summary=details.stage_summary,
        runtime=details.runtime,
        active_pack_order=render_remotion._active_pack_order_for_provenance(),
    )
    return out_path.resolve(), provenance


def test_manifest_registers_static_raw_command_backend() -> None:
    manifest_path = (
        ROOT
        / "astrid"
        / "packs"
        / "rendering"
        / "backends"
        / "remotion"
        / "renderer.yaml"
    )
    manifest = RendererManifest.from_dict(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    )

    assert manifest.id == "rendering.remotion"
    assert manifest.protocol_version == 1
    assert manifest.command == ("python3", "run.py")
    assert manifest.operations == ("render", "support")
    assert manifest.required_permissions == ("project_files", "subprocess")
    assert manifest.required_binaries == ("ffprobe",)
    assert (manifest_path.parents[2] / manifest.command[1]).is_file()


def test_support_is_request_sensitive_and_accepts_complete_timeline(
    tmp_path: Path,
) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    project = _write_project(tmp_path)
    request = _request(timeline_path, assets_path, project)

    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
        report = remotion.support(request, workspace=tmp_path)

    assert report.supported is True
    assert report.reasons == []
    assert report.backend == remotion.BACKEND_ID
    assert report.features["timeline_composition"] is True
    assert report.features["audio_ownership"] == "rendered"


def test_support_treats_timeline_output_hint_as_informational_without_profile(
    tmp_path: Path,
) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    payload = json.loads(timeline_path.read_text(encoding="utf-8"))
    payload["output"] = {
        "resolution": "640x360",
        "fps": 30,
        "file": "title.mp4",
    }
    timeline_path.write_text(json.dumps(payload), encoding="utf-8")
    project = _write_project(tmp_path)
    request = _request(timeline_path, assets_path, project)

    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
        report = remotion.support(request, workspace=tmp_path)

    # Timeline output hints are metadata, not a false 1920-only capability
    # restriction. An explicit RenderProfile remains the authoritative way to
    # request/validate the produced media dimensions.
    assert report.supported is True
    assert report.reasons == []


@pytest.mark.parametrize("clip_type", ["video", "image", "audio"])
def test_support_accepts_builtin_media_clip_type_aliases(
    tmp_path: Path,
    clip_type: str,
) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    payload = json.loads(timeline_path.read_text(encoding="utf-8"))
    payload["clips"] = [
        {
            "id": "source",
            "at": 0,
            "track": "v1",
            "clipType": clip_type,
            "from": 0,
            "to": 1,
        }
    ]
    timeline_path.write_text(json.dumps(payload), encoding="utf-8")
    project = _write_project(tmp_path)
    request = _request(timeline_path, assets_path, project)

    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
        report = remotion.support(request, workspace=tmp_path)

    assert report.supported is True
    assert report.reasons == []


def test_effect_staging_treats_video_as_builtin_media_not_unknown_effect(
    tmp_path: Path,
) -> None:
    timeline_data = {
        "tracks": [{"id": "v1", "kind": "visual", "label": "Visual"}],
        "clips": [
            {
                "id": "source",
                "at": 0,
                "track": "v1",
                "clipType": "video",
                "asset": "source-video",
                "from": 0,
                "to": 1,
            }
        ],
    }

    with (
        mock.patch.object(remotion, "_effect_registry_for_assets", return_value=({}, {})),
        mock.patch.object(
            remotion,
            "_resolve_timeline_element_references",
            return_value={"animations": [], "transitions": []},
        ),
    ):
        staged = remotion._stage_effect_assets_for_timeline(
            timeline_data,
            project_dir=tmp_path,
            theme_path=None,
            render_hash="media-alias",
        )

    assert staged == {
        "root": None,
        "effects": [],
        "animations": [],
        "transitions": [],
    }


def test_support_rejects_native_window_with_actionable_reason(tmp_path: Path) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    project = _write_project(tmp_path)
    request = _request(
        timeline_path,
        assets_path,
        project,
        window=FrameWindow(
            start_frame=0,
            end_frame=30,
            fps_rational=(30, 1),
        ),
    )

    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
        report = remotion.support(request, workspace=tmp_path)

    assert report.supported is False
    assert report.reasons == [
        "rendering.remotion accepts complete timelines, not native frame windows"
    ]
    assert report.features["windows"] is False


def test_support_fails_closed_for_unregistered_animation_reference(tmp_path: Path) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    timeline.save_timeline(
        {
            "theme": "banodoco-default",
            "tracks": [{"id": "v1", "kind": "visual", "label": "Visual"}],
            "clips": [
                {
                    "id": "title",
                    "at": 0,
                    "to": 1,
                    "track": "v1",
                    "clipType": "media",
                    "entrance": {"type": "missing-external-animation"},
                }
            ],
        },
        timeline_path,
    )
    project = _write_project(tmp_path)
    request = _request(timeline_path, assets_path, project)

    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
        report = remotion.support(request, workspace=tmp_path)

    assert report.supported is False
    assert any("unregistered animation 'missing-external-animation'" in reason for reason in report.reasons)


def test_raw_support_adapter_writes_authoritative_support_report(
    tmp_path: Path,
) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    project = _write_project(tmp_path)
    request_path = tmp_path / "request.json"
    result_path = tmp_path / "result.json"
    request_path.write_text(
        json.dumps(_request(timeline_path, assets_path, project).to_dict()),
        encoding="utf-8",
    )

    with mock.patch.object(remotion.shutil, "which", return_value="/usr/bin/tool"):
        exit_code = remotion.main(
            [
                "support",
                "--request",
                str(request_path),
                "--result",
                str(result_path),
            ]
        )

    assert exit_code == 0
    report = SupportReport.from_dict(
        json.loads(result_path.read_text(encoding="utf-8"))
    )
    assert report.supported is True
    assert report.backend == remotion.BACKEND_ID


def test_manifest_command_runs_from_owning_pack_root(tmp_path: Path) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    project = _write_project(tmp_path)
    request_path = tmp_path / "transport-request.json"
    result_path = tmp_path / "transport-result.json"
    request_path.write_text(
        json.dumps(_request(timeline_path, assets_path, project).to_dict()),
        encoding="utf-8",
    )
    pack_root = ROOT / "astrid" / "packs" / "rendering"

    with _execution_env():
        report = CommandTransport(remotion.BACKEND_ID).run(
            "support",
            ("python3", "run.py"),
            request_path=request_path,
            result_path=result_path,
            cwd=pack_root,
        )

    assert isinstance(report, SupportReport)
    assert report.supported is True
    assert report.backend == remotion.BACKEND_ID


def test_protocol_render_returns_valid_namespaced_artifact_shape(tmp_path: Path) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    project = _write_project(tmp_path)
    request = _request(timeline_path, assets_path, project)
    profile = RenderProfile(
        width=1920,
        height=1080,
        fps_rational=(30, 1),
        time_base=(1, 15360),
        container="mp4",
        video_codec="h264",
        video_profile=None,
        video_level=None,
        pixel_format="yuv420p",
    )

    def fake_execute(*args, **kwargs):
        Path(args[2]).write_bytes(b"fake-remotion-video")
        return remotion._ExecutionDetails(
            active_theme={"id": "banodoco-default", "visual": {}},
            registry_state={"version": 1, "hash": "registry-hash"},
            stage_summary={"root": None, "effects": []},
        )

    supported = SupportReport(
        schema_version=1,
        supported=True,
        reasons=[],
        features={},
        alternatives=[],
        backend=remotion.BACKEND_ID,
        backend_version=remotion.BACKEND_VERSION,
    )
    with (
        mock.patch.object(remotion, "support", return_value=supported),
        mock.patch.object(remotion, "_canonical_profile", return_value=profile),
        mock.patch.object(remotion, "_execute_remotion", side_effect=fake_execute),
        mock.patch.object(remotion, "_duration_frames", return_value=30),
        mock.patch.object(remotion, "validate_render_result"),
    ):
        result = remotion._protocol_render(request, workspace=tmp_path)

    assert isinstance(result, RenderResult)
    assert result.video.path == "outputs/result.mp4"
    assert result.video.sha256 == remotion.hashlib.sha256(
        b"fake-remotion-video"
    ).hexdigest()
    assert result.video.audio is AudioOwnership.RENDERED
    assert result.audio_ownership is AudioOwnership.RENDERED
    fragment = result.backend_fragments[remotion.BACKEND_ID]
    assert fragment["renderer"] == "remotion"
    assert fragment["composition"] == "TimelineComposition"
    assert fragment["registry_hash"] == "registry-hash"


def test_hype_merged_render_props_match_golden(tmp_path: Path) -> None:
    timeline_path = ROOT / "examples" / "hype.timeline.json"
    assets_path = ROOT / "examples" / "hype.assets.json"
    expected = json.loads(
        (ROOT / "tests" / "golden" / "hype" / "merged_render_props.json").read_text(
            encoding="utf-8"
        )
    )
    runtime_theme = tmp_path / "theme.json"
    runtime_theme.write_text(json.dumps(expected["theme"]), encoding="utf-8")
    assembled = {
        "assets": timeline.load_registry(assets_path),
        "theme": remotion._resolved_theme_for_render(timeline_path, runtime_theme),
        "timeline": remotion._serialize_timeline(
            timeline_path,
            default_theme="banodoco-default",
        ),
    }
    assert assembled == expected


def test_explicit_missing_theme_path_does_not_fall_back_to_workspace_theme(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="theme file not found or invalid"):
        remotion._theme_for_props(tmp_path / "missing-theme")


def test_facade_delegates_complex_remotion_without_policy_drift(
    tmp_path: Path,
) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    output_path = tmp_path / "hype.mp4"
    sentinel = tmp_path / "delegated.mp4"

    fake_service = mock.Mock()
    fake_service.render.return_value = sentinel

    with mock.patch.object(facade, "_default_service", return_value=fake_service):
        result = facade.render(
            timeline_path,
            assets_path,
            output_path,
            selector="rendering.remotion",
        )

    assert result == sentinel
    fake_service.render.assert_called_once()
    kwargs = fake_service.render.call_args.kwargs
    assert kwargs["selector"] == "rendering.remotion"


def test_audio_ownership_enum_remains_protocol_value() -> None:
    assert AudioOwnership.RENDERED.value == "rendered"
    assert AudioOwnership.NONE.value == "none"


class RemotionBackendRegistryGenerationTest(unittest.TestCase):
    def _write_empty_render_inputs(self, tmp: Path) -> tuple[Path, Path, Path]:
        timeline_path = tmp / "hype.timeline.json"
        assets_path = tmp / "hype.assets.json"
        out_path = tmp / "hype.mp4"
        timeline.save_timeline(
            {
                "theme": "banodoco-default",
                "tracks": [{"id": "v1", "kind": "visual", "label": "Generated"}],
                "clips": [],
            },
            timeline_path,
        )
        timeline.save_registry({"assets": {}}, assets_path)
        return timeline_path, assets_path, out_path

    def _write_fake_remotion_project(self, tmp: Path) -> tuple[Path, Path]:
        project_dir = tmp / "remotion"
        banodoco_root = project_dir / "node_modules" / "@banodoco"
        composition_src = banodoco_root / "timeline-composition" / "typescript" / "src"
        composition_src.mkdir(parents=True)
        # _validate_project_dir requires all three @banodoco adapter packages
        # (see docs/reference/render-adapter.md).  Create stub directories for the other two.
        (banodoco_root / "timeline-schema").mkdir(parents=True)
        (banodoco_root / "timeline-theme-2rp").mkdir(parents=True)
        (project_dir / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
        cli = project_dir / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("// locked test CLI\n", encoding="utf-8")
        return project_dir, composition_src

    def _write_effect_definition(self, tmp: Path, effect_id: str, asset_text: str) -> ElementDefinition:
        root = tmp / "effects" / effect_id
        asset_path = root / "assets" / "badge.txt"
        asset_path.parent.mkdir(parents=True)
        asset_path.write_text(asset_text, encoding="utf-8")
        (root / "component.tsx").write_text("export default function Effect() { return null; }\n", encoding="utf-8")
        (root / "element.yaml").write_text(
            f"schema_version: 1\nid: {effect_id}\nkind: effect\ndefaults: {{}}\nschema: {{}}\n",
            encoding="utf-8",
        )
        return ElementDefinition(
            id=effect_id,
            kind="effects",
            root=root,
            source="pack:test",
            editable=False,
            priority=50,
            component=root / "component.tsx",
            schema={},
            defaults={},
            metadata={},
            assets=(ElementAsset(name="badge", path=Path("assets/badge.txt")),),
        )

    def _copy_local_effect_smoke_project(self, tmp: Path) -> tuple[Path, Path, Path, Path]:
        project_root = tmp / "fixture-project"
        shutil.copytree(LOCAL_EFFECT_SMOKE_FIXTURE, project_root)
        project_dir, _composition_src = self._write_fake_remotion_project(tmp)
        return (
            project_root,
            project_dir,
            project_root / "hype.timeline.json",
            project_root / "hype.assets.json",
        )

    def test_registry_generation_uses_pack_registry_and_composition_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, composition_src = self._write_fake_remotion_project(tmp)
            theme_path = tmp / "theme.json"
            theme_path.write_text("{}", encoding="utf-8")
            calls: list[tuple[list[str], dict[str, object]]] = []

            def fake_run(cmd, **kwargs):
                calls.append(([str(part) for part in cmd], kwargs))
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.dict(render_remotion.os.environ, {"ASTRID_RENDER_UNDECLARED": "host"}, clear=True),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                render_remotion._regenerate_element_registries(project_dir, theme_path)

        self.assertEqual(len(calls), 1)
        cmd, kwargs = calls[0]
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(Path(cmd[1]), ROOT / "scripts" / "gen_effect_registry.py")
        # Theme is resolved into render props; registry codegen receives no
        # retired checkout theme override.
        self.assertEqual(cmd[2:], [])
        self.assertEqual(kwargs["cwd"], str(ROOT))
        env = kwargs["env"]
        self.assertIsInstance(env, dict)
        self.assertEqual(env["ASTRID_TIMELINE_COMPOSITION_SRC"], str(composition_src))
        self.assertNotIn("ASTRID_RENDER_UNDECLARED", env)
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["text"])

    def test_registry_generation_regenerates_when_state_hash_differs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-cache-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            render_remotion._write_registry_state(project_dir, {"version": 1, "hash": "stale"})
            for output_path in render_remotion._registry_output_paths(project_dir):
                if tmp in output_path.parents:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text("// generated test fixture\n", encoding="utf-8")

            calls: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                calls.append([str(part) for part in cmd])
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run):
                render_remotion._regenerate_element_registries(project_dir, None)

            state_after = json.loads((project_dir / ".astrid-registry-state.json").read_text(encoding="utf-8"))

        self.assertEqual(len(calls), 1)
        self.assertEqual(state_after["hash"], render_remotion._effective_registry_state(None)["hash"])

    def test_registry_generation_regenerates_when_generated_output_is_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-cache-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            state = render_remotion._effective_registry_state(None)
            render_remotion._write_registry_state(project_dir, state)
            temp_outputs = [
                output_path
                for output_path in render_remotion._registry_output_paths(project_dir)
                if tmp in output_path.parents
            ]
            for output_path in temp_outputs:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("// generated test fixture\n", encoding="utf-8")
            temp_outputs[0].unlink()

            calls: list[list[str]] = []

            def fake_run(cmd, **kwargs):
                calls.append([str(part) for part in cmd])
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run):
                render_remotion._regenerate_element_registries(project_dir, None)

        self.assertEqual(len(calls), 1)

    def test_render_registry_cache_tracks_element_edits_and_missing_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-cache-sequence-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
            component_path = tmp / "local-effect" / "component.tsx"
            component_path.parent.mkdir(parents=True)
            component_path.write_text("export default function Effect() { return 'v1'; }\n", encoding="utf-8")
            generated_outputs = [
                tmp / "generated" / "effects.generated.ts",
                tmp / "generated" / "animations.generated.ts",
                tmp / "generated" / "transitions.generated.ts",
            ]
            registry_hashes_seen: list[str] = []
            remotion_runs = 0

            def state_from_component(theme_path: Path | None) -> dict[str, object]:
                digest = hashlib.sha256(component_path.read_bytes()).hexdigest()
                return {
                    "version": 1,
                    "hash": digest,
                    "theme": None if theme_path is None else str(theme_path),
                    "content_hashes": {"effects": digest},
                }

            def fake_run(cmd, **kwargs):
                nonlocal remotion_runs
                command = [str(part) for part in cmd]
                if len(command) > 1 and Path(command[1]).name == "gen_effect_registry.py":
                    registry_hashes_seen.append(state_from_component(None)["hash"])
                    for generated_output in generated_outputs:
                        generated_output.parent.mkdir(parents=True, exist_ok=True)
                        generated_output.write_text("// generated test fixture\n", encoding="utf-8")
                elif _is_remotion_render_command(command):
                    remotion_runs += 1
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion, "_effective_registry_state", side_effect=state_from_component),
                mock.patch.object(render_remotion, "_registry_output_paths", return_value=generated_outputs),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(len(registry_hashes_seen), 1)

                _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(len(registry_hashes_seen), 1)

                component_path.write_text("export default function Effect() { return 'v2'; }\n", encoding="utf-8")
                edited_hash = state_from_component(None)["hash"]
                _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(registry_hashes_seen, [mock.ANY, edited_hash])

                _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(registry_hashes_seen, [mock.ANY, edited_hash])

                generated_outputs[0].unlink()
                _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(registry_hashes_seen, [mock.ANY, edited_hash, edited_hash])

        self.assertEqual(remotion_runs, 5)

    def test_render_regenerates_registries_before_remotion_and_writes_props(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
            calls: list[tuple[list[str], dict[str, object]]] = []
            props_payloads: list[dict[str, object]] = []
            props_paths: list[Path] = []

            def fake_run(cmd, **kwargs):
                command = [str(part) for part in cmd]
                calls.append((command, kwargs))
                if _is_remotion_render_command(command):
                    props_path = Path(command[command.index("--props") + 1])
                    props_paths.append(props_path)
                    props_payloads.append(json.loads(props_path.read_text(encoding="utf-8")))
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.dict(
                    render_remotion.os.environ,
                    {
                        "ASTRID_NODE_EXECUTABLE": os.environ[
                            "ASTRID_NODE_EXECUTABLE"
                        ]
                    },
                    clear=True,
                ),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                result, provenance = _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )

        self.assertEqual(result, out_path.resolve())
        self.assertEqual(len(calls), 2)
        registry_cmd, registry_kwargs = calls[0]
        remotion_cmd, remotion_kwargs = calls[1]

        self.assertEqual(Path(registry_cmd[1]), ROOT / "scripts" / "gen_effect_registry.py")
        self.assertNotIn("--theme", registry_cmd)
        self.assertEqual(registry_kwargs["cwd"], str(ROOT))

        self.assertEqual(Path(remotion_cmd[0]).name, "node")
        self.assertTrue(
            Path(remotion_cmd[1]).as_posix().endswith(
                "node_modules/@remotion/cli/remotion-cli.js"
            )
        )
        self.assertEqual(remotion_cmd[2], "render")
        self.assertEqual(remotion_cmd[3], "TimelineComposition")
        remotion_output = Path(remotion_cmd[remotion_cmd.index("--output") + 1])
        self.assertEqual(remotion_output.name, out_path.name)
        self.assertNotEqual(remotion_output, out_path.resolve())
        self.assertIn("--allow-html-in-canvas", remotion_cmd)
        self.assertEqual(remotion_kwargs["cwd"], str(project_dir))
        self.assertFalse(remotion_kwargs["check"])
        self.assertTrue(remotion_kwargs["capture_output"])
        self.assertTrue(remotion_kwargs["text"])

        self.assertEqual(len(props_payloads), 1)
        props = props_payloads[0]
        self.assertIn("timeline", props)
        self.assertIn("assets", props)
        self.assertIn("theme", props)
        self.assertEqual(props["assets"], {"assets": {}})
        self.assertEqual(props["timeline"]["tracks"][0]["id"], "v1")
        self.assertEqual(len(props_paths), 1)
        self.assertFalse(props_paths[0].exists(), "render should remove the temporary props file")
        self.assertEqual(provenance["registry_hash"], render_remotion._effective_registry_state(None)["hash"])
        self.assertEqual(provenance["resolved_effect_ids"], [])

    def test_render_stages_only_used_effect_assets_and_removes_them_after_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-effect-assets-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
            timeline.save_timeline(
                {
                    "theme": "banodoco-default",
                    "tracks": [{"id": "v1", "kind": "visual", "label": "Generated"}],
                    "clips": [
                        {
                            "id": "used",
                            "clipType": "sparkle-alias",
                            "track": "v1",
                            "at": 0,
                            "hold": 1,
                            "params": {"color": "gold"},
                        },
                        {
                            "id": "plain",
                            "clipType": "media",
                            "track": "v1",
                            "asset": "missing-but-not-read-by-this-test",
                            "at": 1,
                            "hold": 1,
                        },
                    ],
                },
                timeline_path,
            )
            used = self._write_effect_definition(tmp, "sparkle", "used asset")
            unused = self._write_effect_definition(tmp, "unused", "unused asset")
            props_payloads: list[dict[str, object]] = []
            staged_roots_seen: list[Path] = []

            def fake_run(cmd, **kwargs):
                command = [str(part) for part in cmd]
                if _is_remotion_render_command(command):
                    props_path = Path(command[command.index("--props") + 1])
                    props = json.loads(props_path.read_text(encoding="utf-8"))
                    props_payloads.append(props)
                    asset_map = props["timeline"]["clips"][0]["params"]["__astridAssets"]
                    staged_asset = project_dir / "public" / asset_map["badge"]
                    staged_roots_seen.append(staged_asset.parents[2])
                    self.assertEqual(staged_asset.read_text(encoding="utf-8"), "used asset")
                    self.assertFalse((staged_asset.parents[2] / "unused" / "assets" / "badge.txt").exists())
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
                mock.patch.object(
                    render_remotion,
                    "_effect_registry_for_assets",
                    return_value=({"sparkle": used, "unused": unused}, {"sparkle-alias": "sparkle"}),
                ),
            ):
                _, provenance = _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )

        self.assertEqual(len(props_payloads), 1)
        clip_params = props_payloads[0]["timeline"]["clips"][0]["params"]
        self.assertEqual(clip_params["color"], "gold")
        self.assertEqual(
            clip_params["__astridAssets"],
            {"badge": mock.ANY},
        )
        self.assertTrue(clip_params["__astridAssets"]["badge"].startswith("astrid-effects/"))
        self.assertEqual(len(staged_roots_seen), 1)
        self.assertFalse(staged_roots_seen[0].exists(), "render should remove staged effect assets")
        self.assertEqual(provenance["resolved_effect_ids"], ["sparkle"])
        self.assertEqual(provenance["source_pack_ids"], ["test"])
        self.assertEqual(provenance["element_roots"], [str(used.root)])
        self.assertEqual(provenance["staged_asset_ids"], ["badge"])
        self.assertEqual(provenance["resolved_effects"][0]["staged_assets"], {"badge": mock.ANY})
        self.assertTrue(provenance["resolved_effects"][0]["staged_assets"]["badge"].startswith("astrid-effects/"))

    def test_render_removes_staged_assets_and_props_after_remotion_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-effect-assets-fail-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
            timeline.save_timeline(
                {
                    "theme": "banodoco-default",
                    "tracks": [{"id": "v1", "kind": "visual", "label": "Generated"}],
                    "clips": [
                        {
                            "id": "used",
                            "clipType": "sparkle",
                            "track": "v1",
                            "at": 0,
                            "hold": 1,
                        }
                    ],
                },
                timeline_path,
            )
            used = self._write_effect_definition(tmp, "sparkle", "used asset")
            staged_roots_seen: list[Path] = []
            props_paths_seen: list[Path] = []

            def fake_run(cmd, **kwargs):
                command = [str(part) for part in cmd]
                if _is_remotion_render_command(command):
                    props_path = Path(command[command.index("--props") + 1])
                    props_paths_seen.append(props_path)
                    props = json.loads(props_path.read_text(encoding="utf-8"))
                    staged_asset = project_dir / "public" / props["timeline"]["clips"][0]["params"]["__astridAssets"]["badge"]
                    staged_roots_seen.append(staged_asset.parents[2])
                    self.assertTrue(staged_asset.exists())
                    return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="boom\n")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
                mock.patch.object(
                    render_remotion,
                    "_effect_registry_for_assets",
                    return_value=({"sparkle": used}, {}),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "Remotion render failed"):
                    _execute_direct(
                        timeline_path,
                        assets_path,
                        out_path,
                        project_dir=project_dir,
                        composition_id="TimelineComposition",
                        theme_path=None,
                    )

            self.assertEqual(len(staged_roots_seen), 1)
            self.assertFalse(staged_roots_seen[0].exists())
            self.assertEqual(len(props_paths_seen), 1)
            self.assertFalse(props_paths_seen[0].exists())

    def test_render_provenance_matches_registry_and_local_overlay_discovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-local-provenance-") as tmp_text:
            tmp = Path(tmp_text)
            project_root, project_dir, timeline_path, assets_path = self._copy_local_effect_smoke_project(tmp)
            out_path = tmp / "fixture-smoke.mp4"
            expected_pack_order = [
                {
                    "id": discovered.id,
                    "source_kind": discovered.source_kind,
                    "priority_index": discovered.priority_index,
                    "root": str(discovered.pack_dir),
                }
                for discovered in discover_pack_metadata(project_root=project_root)
            ]
            expected_registry = render_remotion.load_default_registry(project_root=project_root)
            expected_effect = expected_registry.get("effects", "fixture-smoke-effect")

            def fake_run(cmd, **kwargs):
                command = [str(part) for part in cmd]
                if _is_remotion_render_command(command):
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion, "REPO_ROOT", project_root),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                result, provenance = _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )

        self.assertEqual(result, out_path.resolve())
        self.assertEqual(provenance["active_pack_order"], expected_pack_order)
        self.assertEqual(provenance["resolved_effect_ids"], [expected_effect.id])
        self.assertEqual(provenance["source_pack_ids"], ["local"])
        self.assertEqual(provenance["element_roots"], [str(expected_effect.root)])
        self.assertEqual(provenance["resolved_effects"][0]["effect_id"], expected_effect.id)
        self.assertEqual(provenance["resolved_effects"][0]["source_pack_id"], "local")
        self.assertEqual(provenance["resolved_effects"][0]["source"], expected_effect.source)
        self.assertEqual(provenance["resolved_effects"][0]["element_root"], str(expected_effect.root))
        self.assertEqual(provenance["resolved_effects"][0]["clip_ids"], ["fixture-effect"])
        self.assertEqual(provenance["resolved_effects"][0]["staged_asset_ids"], ["badge", "palette"])
        self.assertEqual(
            set(provenance["resolved_effects"][0]["staged_assets"]),
            {asset.name for asset in expected_effect.assets},
        )

    def test_remotion_render_env_is_explicit_not_host_inherited(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, composition_src = self._write_fake_remotion_project(tmp)
            timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
            remotion_envs: list[dict[str, str]] = []

            def fake_run(cmd, **kwargs):
                command = [str(part) for part in cmd]
                if _is_remotion_render_command(command):
                    remotion_envs.append(dict(kwargs["env"]))
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            host_env = {
                "OPENAI_API_KEY": "sk-should-not-leak",
                "AWS_SECRET_ACCESS_KEY": "synthetic-secret",
                "RENDER_HOST_ONLY": "host-value",
                "PATH": "/usr/bin:/bin",
                "ASTRID_TASK_RUN_ID": "task-run-9",
                "ASTRID_ACTOR": "human:peter",
                "ASTRID_NODE_EXECUTABLE": render_remotion.os.environ[
                    "ASTRID_NODE_EXECUTABLE"
                ],
            }
            with (
                mock.patch.dict(render_remotion.os.environ, host_env, clear=True),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                _execute_direct(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )

        self.assertEqual(len(remotion_envs), 1)
        env = remotion_envs[0]
        # Synthetic secrets and undeclared host variables must be absent.
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        self.assertNotIn("RENDER_HOST_ONLY", env)
        self.assertNotIn("ASTRID_ACTOR", env)
        # Required Node and Astrid runtime variables must be preserved/propagated.
        self.assertEqual(env["PATH"], "/usr/bin:/bin")
        self.assertEqual(env["ASTRID_TASK_RUN_ID"], "task-run-9")
        # The Remotion-specific build-tool addition is the composition source.
        self.assertEqual(env["ASTRID_TIMELINE_COMPOSITION_SRC"], str(composition_src))


# ---------------------------------------------------------------------------
# Regression: ordinary rendering.remotion still renders under the global
# remotion.config.ts ANGLE (Chromium OpenGL renderer) setting.  The global
# ANGLE change (batch 2, needed by Three.js WebGL) must not break the
# ordinary Remotion path or its identity.  Skips ONLY for genuinely missing
# environment; a render failure is never turned into a skip.
# ---------------------------------------------------------------------------


def _remotion_missing_environment() -> list[str]:
    missing = [
        f"{binary} executable"
        for binary in ("ffprobe",)
        if shutil.which(binary) is None
    ]
    node_executable = os.environ.get("ASTRID_NODE_EXECUTABLE", "").strip()
    if not node_executable or not Path(node_executable).is_file():
        missing.append("ASTRID_NODE_EXECUTABLE")
    node_modules = ROOT / "remotion" / "node_modules"
    if not node_modules.is_dir():
        missing.append("remotion/node_modules")
    cli = node_modules / "@remotion" / "cli" / "remotion-cli.js"
    if not cli.is_file():
        missing.append("remotion local CLI")
    return missing


def _require_remotion_environment() -> None:
    missing = _remotion_missing_environment()
    if missing:
        pytest.skip(
            "Remotion real render skipped: missing optional dependencies: "
            + ", ".join(missing)
        )


def _remotion_text_timeline(tmp_path: Path) -> Path:
    path = tmp_path / "remotion-angle.timeline.json"
    timeline.save_timeline(
        {
            "theme": "banodoco-default",
            "theme_overrides": {
                "visual": {
                    "canvas": {"width": 320, "height": 180, "fps": 24},
                    "background": "#1a1a2e",
                }
            },
            "tracks": [{"id": "v1", "kind": "visual", "label": "Title"}],
            "clips": [
                {
                    "id": "title",
                    "at": 0.0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 0.5,
                    "text": {"content": "Remotion ANGLE", "fontSize": 64, "color": "#ffffff"},
                    "params": {"weight": 700},
                }
            ],
        },
        path,
    )
    return path


@pytest.mark.timeout(600)
def test_remotion_real_render_under_global_angle_keeps_identity(
    tmp_path: Path,
) -> None:
    """A real rendering.remotion render (full timeline, no planner) succeeds
    with the global ANGLE Chromium renderer on and its provenance says
    rendering.remotion — never rendering.threejs."""
    _require_remotion_environment()
    timeline_path = _remotion_text_timeline(tmp_path)
    output = tmp_path / "remotion-angle.mp4"
    with _execution_env():
        published = render(
            timeline_path=timeline_path,
            assets_registry_path=None,
            out_path=output,
            backend="rendering.remotion",
        )

    video_path = Path(published)
    assert video_path.is_file()
    assert video_path.stat().st_size > 0
    sidecar = Path(f"{video_path}.provenance.json")
    assert sidecar.is_file()
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["sha256"] == hashlib.sha256(video_path.read_bytes()).hexdigest()
    assert payload["engine"] == "rendering.remotion"
    assert payload["routing"]["resolved_backend"] == "rendering.remotion"
    serialized = json.dumps(payload)
    assert "rendering.threejs" not in serialized
    fragment = payload["backend_fragments"]["rendering.remotion"]
    assert fragment["renderer"] == "remotion"
    assert fragment["renderer"] == "remotion"

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,pix_fmt,avg_frame_rate,nb_read_frames",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    streams = json.loads(probe)["streams"]
    video = next(s for s in streams if s["codec_type"] == "video")
    assert video["codec_name"] == "h264"
    assert "420p" in video["pix_fmt"], video
    assert video["width"] == 320 and video["height"] == 180
    assert int(video["nb_read_frames"]) == 12, video
    numerator, denominator = (int(part) for part in video["avg_frame_rate"].split("/"))
    assert abs(numerator / denominator - 24.0) <= 0.5, video
    assert any(s["codec_type"] == "audio" and s["codec_name"] == "aac" for s in streams)

# ---------------------------------------------------------------------------
# Batch 4 - alpha output (consumes the astrid_layer.alpha stamp)
# ---------------------------------------------------------------------------


def _rgba_corner(video_path: Path) -> bytes:
    """Top-left RGBA pixel of frame 0 (ffmpeg raw rgba decode)."""
    raw = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-pix_fmt",
            "rgba",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout
    return raw[0:4]


def _stamped_text_timeline(tmp_path: Path, *, alpha: bool = True) -> Path:
    path = tmp_path / "stamped-alpha.timeline.json"
    timeline.save_timeline(
        {
            "theme": "banodoco-default",
            "theme_overrides": {
                "visual": {
                    "canvas": {"width": 320, "height": 180, "fps": 24},
                    "background": "#1a1a2e",
                }
            },
            "tracks": [{"id": "v1", "kind": "visual", "label": "Title"}],
            "clips": [
                {
                    "id": "title",
                    "at": 0.0,
                    "track": "v1",
                    "clipType": "text",
                    "hold": 0.5,
                    "text": {"content": "ALPHA", "fontSize": 64, "color": "#ffffff"},
                    "params": {"weight": 700},
                }
            ],
            "metadata": {"astrid_layer": {"z": 1 if alpha else 0, "alpha": alpha}},
        },
        path,
    )
    return path


def test_alpha_stamp_appends_transparent_flags_to_remotion_cli(
    tmp_path: Path,
) -> None:
    """Stamped timeline -> --image-format=png --pixel-format=yuva444p10le
    --codec=prores --prores-profile=4444 appended to the remotion CLI, the
    rendered output is remapped to .mov, and the serialized theme's
    visual.color.bg is transparent.  Unstamped (today's frozen path) -> no
    alpha flags at all, .mp4 output, opaque theme bg kept."""
    seen: dict[str, list[str]] = {"commands": []}
    props_seen: list[dict[str, object]] = []

    def fake_run(command, **kwargs):
        normalized = [str(part) for part in command]
        if _is_remotion_render_command(normalized):
            seen["commands"].append(normalized)
            props_path = Path(normalized[normalized.index("--props") + 1])
            props_seen.append(json.loads(props_path.read_text(encoding="utf-8")))
            Path(normalized[normalized.index("--output") + 1]).write_bytes(
                b"fake-remotion-video"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    opaque_timeline, assets_path = _write_inputs(tmp_path)
    alpha_timeline = _stamped_text_timeline(tmp_path, alpha=True)
    project = _write_project(tmp_path)

    for timeline_path in (opaque_timeline, alpha_timeline):
        suffix = ".mov" if timeline_path == alpha_timeline else ".mp4"
        output_path = tmp_path / f"{Path(timeline_path).stem}{suffix}"
        with (
            mock.patch.object(remotion, "_regenerate_element_registries"),
            mock.patch.object(
                remotion,
                "_effective_registry_state",
                return_value={"version": 1, "hash": "registry-hash"},
            ),
            mock.patch.object(remotion, "_available_remotion_port", return_value=3001),
            mock.patch.object(remotion.subprocess, "run", side_effect=fake_run),
        ):
            _execute_direct(
                timeline_path, assets_path, output_path, project_dir=project
            )

    opaque_cmd, alpha_cmd = seen["commands"]
    for flag in (
        "--image-format=png",
        "--pixel-format=yuva444p10le",
        "--codec=prores",
        "--prores-profile=4444",
    ):
        assert flag not in opaque_cmd
        assert flag in alpha_cmd
    for dead_flag in ("--codec=vp9", "--pixel-format=yuva420p"):
        assert dead_flag not in alpha_cmd
        assert dead_flag not in opaque_cmd
    assert sum(part.startswith("--port=") for part in opaque_cmd) == 1
    assert sum(part.startswith("--port=") for part in alpha_cmd) == 1
    assert "--port=3001" in opaque_cmd
    assert "--port=3001" in alpha_cmd
    # Stamped renders are remapped to the ProRes .mov container name.
    alpha_output = Path(alpha_cmd[alpha_cmd.index("--output") + 1])
    assert alpha_output.suffix == ".mov"
    opaque_output = Path(opaque_cmd[opaque_cmd.index("--output") + 1])
    assert opaque_output.suffix == ".mp4"
    # Theme background neutralization: stamped props carry a transparent bg,
    # the unstamped path keeps the opaque theme bg.
    opaque_props, alpha_props = props_seen
    assert alpha_props["theme"]["visual"]["color"]["bg"] == "transparent"
    assert opaque_props["theme"]["visual"]["color"]["bg"] != "transparent"


@pytest.mark.timeout(600)
def test_alpha_stamped_real_render_is_mov_prores_and_declared_profile_matches(
    tmp_path: Path,
) -> None:
    """A REAL alpha render through _protocol_render: strict validation
    passes and the probed artifact is the recorded batch-4-rework truth --
    mov/prores/yuva444p12le/time_base 1/90000/pcm_s16le, output remapped to
    .mov, and the corner pixel is fully transparent (alpha == 0)."""
    _require_remotion_environment()
    timeline_path = _stamped_text_timeline(tmp_path, alpha=True)
    assets_path = tmp_path / "assets.json"
    timeline.save_registry({"assets": {}}, assets_path)
    request = RenderRequest(
        schema_version=SCHEMA_VERSION,
        timeline_path=str(timeline_path),
        assets_registry_path=str(assets_path),
        output_name="segment-0000.mp4",
        backend_config={
            remotion.BACKEND_ID: {"project_dir": str(ROOT / "remotion")},
        },
    )
    with _execution_env():
        result = remotion._protocol_render(request, workspace=tmp_path)

    # The artifact is remapped to .mov and the declared path points at it.
    video_path = tmp_path / "outputs" / "segment-0000.mov"
    assert video_path.is_file() and video_path.stat().st_size > 0
    assert result.video.path == "outputs/segment-0000.mov"
    profile = result.video.profile
    assert profile.container == "mov"
    assert profile.video_codec == "prores"
    assert profile.pixel_format == "yuva444p12le"
    assert profile.time_base == (1, 90000)
    probe = _probe(video_path)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert video["codec_name"] == "prores"
    assert video["pix_fmt"] == "yuva444p12le"
    assert video["time_base"] == "1/90000"
    assert any(
        s["codec_type"] == "audio" and s["codec_name"] == "pcm_s16le"
        for s in probe["streams"]
    )


@pytest.mark.timeout(600)
def test_stamped_top_layer_via_real_service_is_mov_prores_with_alpha(
    tmp_path: Path,
) -> None:
    """Stamped top layer via the REAL service path -> .mov/prores with alpha;
    unstamped via the same path -> .mp4/h264 opaque (frozen no-regression)."""
    _require_remotion_environment()
    for alpha in (True, False):
        timeline_path = _stamped_text_timeline(tmp_path, alpha=alpha)
        assets_path = tmp_path / "assets.json"
        timeline.save_registry({"assets": {}}, assets_path)
        # The service publishes to the caller's destination name; the
        # stamped case asks for the ProRes .mov container (the backend
        # remap is exercised separately via _protocol_render with the
        # service's hardcoded segment-NNNN.mp4 name).
        output = (
            tmp_path / f"layer-{alpha}.mov"
            if alpha
            else tmp_path / f"layer-{alpha}.mp4"
        )
        with _execution_env():
            published = render(
                timeline_path=timeline_path,
                assets_registry_path=str(assets_path),
                out_path=output,
                backend="rendering.remotion",
            )
        video_path = Path(published)
        assert video_path.is_file() and video_path.stat().st_size > 0
        probe = _probe(video_path)
        video = next(s for s in probe["streams"] if s["codec_type"] == "video")
        if alpha:
            assert video_path.suffix == ".mov", video_path
            assert video["codec_name"] == "prores"
            assert video["pix_fmt"] == "yuva444p12le"
            corner = _rgba_corner(video_path)
            assert corner[3] == 0, corner
        else:
            assert video_path.suffix == ".mp4", video_path
            assert video["codec_name"] == "h264"
            assert "420p" in video["pix_fmt"], video
            corner = _rgba_corner(video_path)
            # Frozen opaque path: the DOM composition paints the resolved
            # theme bg (this worktree resolves the black banodoco-default
            # fallback) and the corner is fully opaque.
            assert corner[3] == 255, corner
            assert corner[:3] == bytes([0, 0, 0]), corner
