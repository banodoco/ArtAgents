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

from astrid.core import timeline
from astrid.core.element.schema import ElementAsset, ElementDefinition
from astrid.core.pack.discovery import discover_pack_metadata
from astrid.packs.rendering.executors.render import run as render_remotion

ROOT = Path(__file__).resolve().parents[3]
LOCAL_EFFECT_SMOKE_FIXTURE = ROOT / "tests" / "fixtures" / "local_effect_smoke"


def _write_fake_remotion_output(command: list[str]) -> Path:
    output = Path(command[command.index("--output") + 1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"fake-remotion-video")
    return output


class RenderRemotionRegistryGenerationTest(unittest.TestCase):
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

    def test_registry_generation_skips_when_state_and_outputs_are_current(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-registry-cache-") as tmp_text:
            tmp = Path(tmp_text)
            project_dir, _composition_src = self._write_fake_remotion_project(tmp)
            state = render_remotion._effective_registry_state(None)
            render_remotion._write_registry_state(project_dir, state)
            for output_path in render_remotion._registry_output_paths(project_dir):
                if tmp in output_path.parents:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text("// generated test fixture\n", encoding="utf-8")

            with mock.patch.object(render_remotion.subprocess, "run") as run_mock:
                render_remotion._regenerate_element_registries(project_dir, None)

        run_mock.assert_not_called()

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

    def test_render_discovers_fixture_local_effect_assets_without_real_local_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-local-effect-smoke-") as tmp_text:
            tmp = Path(tmp_text)
            project_root, project_dir, timeline_path, assets_path = self._copy_local_effect_smoke_project(tmp)
            out_path = tmp / "fixture-smoke.mp4"
            real_local_effect = ROOT / "astrid" / "packs" / "local" / "elements" / "effects" / "model-trends"
            self.assertTrue(real_local_effect.exists(), "test assumes the developer checkout has real local effects")
            discovered_effect_ids: list[str] = []
            registry_project_roots: list[Path] = []
            props_payloads: list[dict[str, object]] = []
            staged_asset_paths_seen: list[Path] = []

            real_load_default_registry = render_remotion.load_default_registry

            def capturing_load_default_registry(**kwargs):
                registry_project_roots.append(Path(kwargs["project_root"]).resolve())
                registry = real_load_default_registry(**kwargs)
                discovered_effect_ids.extend(element.id for element in registry.list(kind="effects"))
                return registry

            def fake_run(cmd, **kwargs):
                command = [str(part) for part in cmd]
                if command[:3] == ["npx", "remotion", "render"]:
                    props_path = Path(command[command.index("--props") + 1])
                    props = json.loads(props_path.read_text(encoding="utf-8"))
                    props_payloads.append(props)
                    clip = props["timeline"]["clips"][0]
                    staged_assets = clip["params"]["__astridAssets"]
                    self.assertEqual(set(staged_assets), {"badge", "palette"})
                    staged_badge = project_dir / "public" / staged_assets["badge"]
                    staged_palette = project_dir / "public" / staged_assets["palette"]
                    staged_asset_paths_seen.extend([staged_badge, staged_palette])
                    self.assertEqual(staged_badge.read_text(encoding="utf-8"), "fixture badge asset\n")
                    self.assertEqual(staged_palette.read_text(encoding="utf-8"), '{"accent":"cyan"}\n')
                    _write_fake_remotion_output(command)
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with (
                mock.patch.object(render_remotion, "REPO_ROOT", project_root),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
                mock.patch.object(render_remotion, "load_default_registry", side_effect=capturing_load_default_registry),
            ):
                result = render_remotion.render(
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

        self.assertEqual(result, out_path.resolve())
        self.assertEqual(registry_project_roots, [project_root.resolve()])
        self.assertIn("fixture-smoke-effect", discovered_effect_ids)
        self.assertNotIn("model-trends", discovered_effect_ids)
        self.assertEqual(len(props_payloads), 1)
        clip = props_payloads[0]["timeline"]["clips"][0]
        self.assertEqual(clip["clipType"], "fixture-smoke-effect")
        self.assertEqual(clip["params"]["label"], "Fixture smoke")
        self.assertTrue(clip["params"]["__astridAssets"]["badge"].startswith("astrid-effects/"))
        self.assertEqual(len(staged_asset_paths_seen), 2)
        for staged_asset_path in staged_asset_paths_seen:
            self.assertFalse(staged_asset_path.exists(), "render should clean fixture-staged assets")
        self.assertFalse((project_root / "astrid" / "packs" / "local" / "elements" / "effects" / "model-trends").exists())
        self.assertEqual(provenance["resolved_effect_ids"], ["fixture-smoke-effect"])
        self.assertEqual(provenance["source_pack_ids"], ["local"])
        self.assertEqual(provenance["staged_asset_ids"], ["badge", "palette"])
        self.assertIn("local", [pack["id"] for pack in provenance["active_pack_order"]])

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

    def test_hybrid_render_writes_final_sidecar_with_remotion_segment_provenance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-hybrid-provenance-") as tmp_text:
            tmp = Path(tmp_text)
            timeline_path, assets_path, out_path = self._write_empty_render_inputs(tmp)
            remotion_segment_payload = {
                "schema_version": 1,
                "engine": "remotion",
                "output": "segment.mp4",
                "resolved_effect_ids": ["sparkle"],
            }

            def fake_render(timeline_arg, assets_arg, out_arg, **kwargs):
                Path(out_arg).write_text("segment", encoding="utf-8")
                render_remotion._render_provenance_sidecar_path(Path(out_arg)).write_text(
                    json.dumps(remotion_segment_payload) + "\n",
                    encoding="utf-8",
                )
                return Path(out_arg)

            def fake_concat(segment_paths, final_out):
                final_out.write_text("hybrid", encoding="utf-8")

            with (
                mock.patch.object(
                    render_remotion,
                    "_hybrid_segments",
                    return_value=[{"engine": "remotion", "from": 0.0, "to": 1.0}],
                ),
                mock.patch.object(render_remotion, "render", side_effect=fake_render),
                mock.patch.object(render_remotion, "_concat_segments", side_effect=fake_concat),
                mock.patch.object(render_remotion, "_effective_registry_state", return_value={"hash": "registry-hash"}),
            ):
                result = render_remotion._render_hybrid(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=tmp / "remotion",
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
            provenance = json.loads(
                render_remotion._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
            )

        self.assertEqual(result, out_path.resolve())
        self.assertEqual(provenance["engine"], "hybrid")
        self.assertEqual(provenance["registry_hash"], "registry-hash")
        self.assertEqual(provenance["segments"], [{"engine": "remotion", "from": 0.0, "to": 1.0}])
        self.assertEqual(provenance["segment_provenance"], [remotion_segment_payload])

    def test_main_synthesizes_empty_asset_registry_when_assets_are_absent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-main-assets-") as tmp_text:
            tmp = Path(tmp_text)
            timeline_path, _assets_path, out_path = self._write_empty_render_inputs(tmp)
            seen: dict[str, object] = {}

            def fake_render(timeline_arg, assets_arg, out_arg, **kwargs):
                assets_arg = Path(assets_arg)
                seen["timeline"] = timeline_arg
                seen["assets"] = assets_arg
                seen["assets_payload"] = json.loads(assets_arg.read_text(encoding="utf-8"))
                seen["out"] = out_arg
                seen["kwargs"] = kwargs
                return out_arg

            with mock.patch.object(render_remotion, "render", side_effect=fake_render):
                result = render_remotion.main(
                    [
                        "--timeline",
                        str(timeline_path),
                        "--out",
                        str(out_path),
                    ]
                )

        self.assertEqual(result, 0)
        self.assertEqual(seen["timeline"], timeline_path)
        self.assertEqual(seen["assets_payload"], {"assets": {}})
        self.assertEqual(seen["out"], out_path)
        self.assertFalse(Path(seen["assets"]).exists())

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


if __name__ == "__main__":
    unittest.main()
