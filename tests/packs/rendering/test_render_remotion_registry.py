from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.core import timeline
from astrid.packs.rendering.executors.render import run as render_remotion

ROOT = Path(__file__).resolve().parents[3]


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
        # (see docs/render-adapter.md).  Create stub directories for the other two.
        (banodoco_root / "timeline-schema").mkdir(parents=True)
        (banodoco_root / "timeline-theme-2rp").mkdir(parents=True)
        (project_dir / "package.json").write_text('{"scripts":{}}\n', encoding="utf-8")
        return project_dir, composition_src

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
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            class FakeServer:
                def __init__(self, address, handler) -> None:
                    self.address = address
                    self.handler = handler
                    self.shutdown_called = False
                    self.server_close_called = False

                def serve_forever(self) -> None:
                    return None

                def shutdown(self) -> None:
                    self.shutdown_called = True

                def server_close(self) -> None:
                    self.server_close_called = True

            with (
                mock.patch.dict(render_remotion.os.environ, {}, clear=True),
                mock.patch.object(render_remotion.subprocess, "run", side_effect=fake_run),
                mock.patch.object(render_remotion, "_pick_free_port", return_value=49152),
                mock.patch.object(render_remotion, "ThreadingHTTPServer", FakeServer),
            ):
                result = render_remotion.render(
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

        self.assertEqual(remotion_cmd[:3], ["npx", "remotion", "render"])
        self.assertEqual(remotion_cmd[3], "TimelineComposition")
        self.assertEqual(remotion_cmd[remotion_cmd.index("--output") + 1], str(out_path.resolve()))
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
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            class FakeServer:
                def __init__(self, address, handler) -> None:
                    pass

                def serve_forever(self) -> None:
                    return None

                def shutdown(self) -> None:
                    return None

                def server_close(self) -> None:
                    return None

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
                mock.patch.object(render_remotion, "_pick_free_port", return_value=49152),
                mock.patch.object(render_remotion, "ThreadingHTTPServer", FakeServer),
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
