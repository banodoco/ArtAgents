from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from astrid.core import timeline
from astrid.core.integrations.reigh import remotion_runtime
from astrid.packs.rendering.backends.remotion import run as render_remotion
from astrid.packs.rendering.executors.render import legacy_engine
from astrid.packs.rendering.executors.render import run as render_facade

ROOT = Path(__file__).resolve().parents[3]
LOCAL_EFFECT_SMOKE_FIXTURE = ROOT / "tests" / "fixtures" / "local_effect_smoke"


@pytest.fixture(autouse=True)
def _trusted_node_for_render_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    node = tmp_path / "node"
    node.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then printf 'v20.19.4\\n'; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    node.chmod(0o755)
    configured_node = shutil.which("node") or str(node)
    monkeypatch.setenv("ASTRID_NODE_EXECUTABLE", str(Path(configured_node).resolve()))
    monkeypatch.setattr(
        remotion_runtime,
        "_probe_node",
        lambda node_executable, *, cwd: ("v20.19.4", None),
    )


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
        cli = project_dir / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("// locked test CLI\n", encoding="utf-8")
        return project_dir, composition_src

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

    def test_render_discovers_fixture_local_effect_assets_without_real_local_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="render-local-effect-smoke-") as tmp_text:
            tmp = Path(tmp_text)
            project_root, project_dir, timeline_path, assets_path = self._copy_local_effect_smoke_project(tmp)
            out_path = tmp / "fixture-smoke.mp4"
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
                if (
                    len(command) >= 3
                    and Path(command[0]).name == "node"
                    and command[1].endswith(
                        "node_modules/@remotion/cli/remotion-cli.js"
                    )
                    and command[2] == "render"
                ):
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
                legacy_engine._render_provenance_sidecar_path(Path(out_arg)).write_text(
                    json.dumps(remotion_segment_payload) + "\n",
                    encoding="utf-8",
                )
                return Path(out_arg)

            def fake_concat(segment_paths, final_out):
                final_out.write_text("hybrid", encoding="utf-8")

            with (
                mock.patch.object(
                    legacy_engine,
                    "_hybrid_segments",
                    return_value=[{"engine": "remotion", "from": 0.0, "to": 1.0}],
                ),
                mock.patch.object(render_facade, "render", side_effect=fake_render),
                mock.patch.object(legacy_engine, "_concat_segments", side_effect=fake_concat),
                mock.patch.object(legacy_engine, "_effective_registry_state", return_value={"hash": "registry-hash"}),
            ):
                result = legacy_engine._render_hybrid(
                    timeline_path,
                    assets_path,
                    out_path,
                    project_dir=tmp / "remotion",
                    composition_id="TimelineComposition",
                    theme_path=None,
                )
            provenance = json.loads(
                legacy_engine._render_provenance_sidecar_path(out_path.resolve()).read_text(encoding="utf-8")
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

            with mock.patch.object(render_facade, "render", side_effect=fake_render):
                result = render_facade.main(
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

if __name__ == "__main__":
    unittest.main()
