from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from astrid.core import timeline
from astrid.core.element.schema import ElementAsset, ElementDefinition
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.core.rendering.contracts import (
    AudioOwnership,
    FrameWindow,
    RenderProfile,
    RenderRequest,
    RenderResult,
    RendererManifest,
    SCHEMA_VERSION,
    SupportReport,
)
from astrid.core.rendering.transport import CommandTransport
from astrid.packs.rendering.backends.remotion import run as remotion
from astrid.packs.rendering.executors.render import run as facade


ROOT = Path(__file__).resolve().parents[3]
LOCAL_EFFECT_SMOKE_FIXTURE = ROOT / "tests" / "fixtures" / "local_effect_smoke"
render_remotion = remotion


def _write_fake_remotion_output(command: list[str]) -> Path:
    output = Path(command[command.index("--output") + 1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"fake-remotion-video")
    return output


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
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
    assert manifest.required_binaries == ("node", "npx", "ffprobe")
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


def test_render_preserves_props_command_cleanup_and_provenance(tmp_path: Path) -> None:
    timeline_path, assets_path = _write_inputs(tmp_path)
    project = _write_project(tmp_path)
    output_path = tmp_path / "output" / "hype.mp4"
    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        normalized = [str(part) for part in command]
        if normalized[:3] == ["npx", "remotion", "render"]:
            props_path = Path(normalized[normalized.index("--props") + 1])
            seen["props_path"] = props_path
            seen["props"] = json.loads(props_path.read_text(encoding="utf-8"))
            seen["command"] = normalized
            seen["env"] = kwargs["env"]
            video_path = Path(normalized[normalized.index("--output") + 1])
            video_path.write_bytes(b"fake-remotion-video")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with (
        mock.patch.object(remotion, "_regenerate_element_registries"),
        mock.patch.object(
            remotion,
            "_effective_registry_state",
            return_value={"version": 1, "hash": "registry-hash"},
        ),
        mock.patch.object(remotion.subprocess, "run", side_effect=fake_run),
    ):
        result = remotion.render(
            timeline_path,
            assets_path,
            output_path,
            project_dir=project,
        )

    assert result == output_path.resolve()
    assert seen["props"].keys() == {"timeline", "assets", "theme"}
    assert seen["command"][3] == "TimelineComposition"
    assert "--allow-html-in-canvas" in seen["command"]
    assert not Path(seen["props_path"]).exists()
    provenance = json.loads(
        remotion._render_provenance_sidecar_path(output_path).read_text(
            encoding="utf-8"
        )
    )
    assert provenance["engine"] == "remotion"
    assert provenance["composition_id"] == "TimelineComposition"
    assert provenance["registry_hash"] == "registry-hash"


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
    assert fragment["legacy_v1"]["registry_hash"] == "registry-hash"


def test_hype_merged_render_props_match_golden() -> None:
    timeline_path = ROOT / "examples" / "hype.timeline.json"
    assets_path = ROOT / "examples" / "hype.assets.json"
    fallback_theme = ROOT / "themes" / "banodoco-default" / "theme.json"
    assembled = {
        "assets": timeline.load_registry(assets_path),
        "theme": remotion._resolved_theme_for_render(timeline_path, fallback_theme),
        "timeline": remotion._serialize_timeline(
            timeline_path,
            default_theme="banodoco-default",
        ),
    }
    expected = json.loads(
        (ROOT / "tests" / "golden" / "hype" / "merged_render_props.json").read_text(
            encoding="utf-8"
        )
    )
    assert assembled == expected


def test_facade_delegates_complex_legacy_remotion_without_policy_drift(
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
            engine="remotion",
        )

    assert result == sentinel
    fake_service.render.assert_called_once()
    kwargs = fake_service.render.call_args.kwargs
    assert kwargs["selector"] == "remotion"


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

    def test_registry_generation_sets_theme_and_composition_env(self) -> None:
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
        self.assertEqual(cmd[2:], ["--theme", str(theme_path)])
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
                elif command[:3] == ["npx", "remotion", "render"]:
                    remotion_runs += 1
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion, "_effective_registry_state", side_effect=state_from_component),
                mock.patch.object(render_remotion, "_registry_output_paths", return_value=generated_outputs),
                mock.patch.object(render_remotion, "_active_theme_pointer_current", return_value=True),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                render_remotion.render(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(len(registry_hashes_seen), 1)

                render_remotion.render(
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
                render_remotion.render(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(registry_hashes_seen, [mock.ANY, edited_hash])

                render_remotion.render(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
                self.assertEqual(registry_hashes_seen, [mock.ANY, edited_hash])

                generated_outputs[0].unlink()
                render_remotion.render(
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
                if command[:3] == ["npx", "remotion", "render"]:
                    props_path = Path(command[command.index("--props") + 1])
                    props_paths.append(props_path)
                    props_payloads.append(json.loads(props_path.read_text(encoding="utf-8")))
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.dict(render_remotion.os.environ, {}, clear=True),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                result = render_remotion.render(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
            provenance_path = render_remotion._render_provenance_sidecar_path(out_path.resolve())
            self.assertTrue(provenance_path.exists())
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))

        self.assertEqual(result, out_path.resolve())
        self.assertEqual(len(calls), 2)
        registry_cmd, registry_kwargs = calls[0]
        remotion_cmd, remotion_kwargs = calls[1]

        self.assertEqual(Path(registry_cmd[1]), ROOT / "scripts" / "gen_effect_registry.py")
        self.assertNotIn("--theme", registry_cmd)
        self.assertEqual(registry_kwargs["cwd"], str(ROOT))

        self.assertEqual(remotion_cmd[:3], ["npx", "remotion", "render"])
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
        self.assertEqual(provenance["engine"], "remotion")
        self.assertEqual(provenance["output"], str(out_path.resolve()))
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
                if command[:3] == ["npx", "remotion", "render"]:
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
                render_remotion.render(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
            provenance = json.loads(
                render_remotion._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
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
                if command[:3] == ["npx", "remotion", "render"]:
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
                    render_remotion.render(
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
            self.assertFalse(render_remotion._render_provenance_sidecar_path(out_path.resolve()).exists())

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
                if command[:3] == ["npx", "remotion", "render"]:
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion, "REPO_ROOT", project_root),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                result = render_remotion.render(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=project_dir,
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
            sidecar_path = render_remotion._render_provenance_sidecar_path(out_path.resolve())
            sidecar_exists = sidecar_path.exists()
            provenance = json.loads(sidecar_path.read_text(encoding="utf-8"))

        self.assertEqual(result, out_path.resolve())
        self.assertTrue(sidecar_exists)
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
                if command[:3] == ["npx", "remotion", "render"]:
                    remotion_envs.append(dict(kwargs["env"]))
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            host_env = {
                "OPENAI_API_KEY": "sk-should-not-leak",
                "AWS_SECRET_ACCESS_KEY": "synthetic-secret",
                "RENDER_HOST_ONLY": "host-value",
                "PATH": "/usr/bin:/bin",
                "ASTRID_SESSION_ID": "sess-123",
                "ASTRID_TASK_RUN_ID": "task-run-9",
                "ASTRID_ACTOR": "human:peter",
            }
            with (
                mock.patch.dict(render_remotion.os.environ, host_env, clear=True),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
            ):
                render_remotion.render(
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
        self.assertEqual(env["ASTRID_SESSION_ID"], "sess-123")
        self.assertEqual(env["ASTRID_TASK_RUN_ID"], "task-run-9")
        # The Remotion-specific build-tool addition is the composition source.
        self.assertEqual(env["ASTRID_TIMELINE_COMPOSITION_SRC"], str(composition_src))
