import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from astrid.contracts.errors import AstridError
from astrid.core.element.schema import load_element_definition
from astrid.core.executor import cli as executors_cli
from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.packs.rendering.executors.html_canvas_effect.run import main, scaffold


class HtmlCanvasEffectExecutorTest(unittest.TestCase):
    def test_executor_is_discoverable(self) -> None:
        registry = load_executor_registry()
        executor = registry.get("rendering.html_canvas_effect")

        self.assertEqual(executor.metadata["runtime_module"], "astrid.packs.rendering.executors.html_canvas_effect.run")
        self.assertIn("HtmlInCanvas", executor.description)

    def test_scaffold_writes_local_effect_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            report_path = project / "runs" / "effect" / "report.json"

            report = scaffold(
                effect_id="glass-product-card",
                label="Glass Product Card",
                description="A test effect.",
                project_root=project,
                out_path=report_path,
            )

            element_root = project / "astrid" / "packs" / "local" / "elements" / "effects" / "glass-product-card"
            self.assertEqual(Path(report["element_root"]), element_root)
            self.assertTrue((element_root / "component.tsx").is_file())
            self.assertTrue((element_root / "element.yaml").is_file())
            self.assertTrue(report_path.is_file())

            component = (element_root / "component.tsx").read_text(encoding="utf-8")
            self.assertIn("HtmlInCanvas", component)
            self.assertIn("drawElementImage", component)

            manifest = json.loads((element_root / "element.yaml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], "glass-product-card")
            self.assertEqual(manifest["pack_id"], "local")
            self.assertTrue(manifest["metadata"]["render_requirements"]["uses_html_in_canvas"])
            self.assertEqual(manifest["metadata"]["render_requirements"]["final_renderer"], "rendering.render")

            element = load_element_definition(element_root, kind="effects", source="pack:local", editable=True, priority=10)
            self.assertEqual(element.id, "glass-product-card")
            self.assertEqual(element.metadata["pack_id"], "local")

    def test_scaffold_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            report_path = project / "report.json"
            scaffold(effect_id="canvas-card", label=None, description=None, project_root=project, out_path=report_path)

            with self.assertRaisesRegex(FileExistsError, "already exists"):
                scaffold(effect_id="canvas-card", label=None, description=None, project_root=project, out_path=report_path)

            scaffold(effect_id="canvas-card", label=None, description=None, project_root=project, out_path=report_path, force=True)

    def test_main_validates_effect_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(AstridError, "kebab-case"):
                main(["--effect-id", "Bad_ID", "--project-root", tmp, "--out", str(Path(tmp) / "report.json")])

    def test_main_writes_result_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            report_path = project / "runs" / "effect" / "report.json"
            timeline_path = project / "runs" / "effect" / "timeline.json"
            assets_path = project / "runs" / "effect" / "assets.json"

            result = main(
                [
                    "--effect-id", "glass-product-card",
                    "--label", "Glass Product Card",
                    "--description", "A test effect.",
                    "--project-root", str(project),
                    "--out", str(report_path),
                    "--timeline", str(timeline_path),
                    "--assets", str(assets_path),
                ]
            )

            self.assertEqual(result, 0)
            manifest_path = report_path.parent / "manifest.json"
            self.assertTrue(manifest_path.is_file(), f"manifest not found at {manifest_path}")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["kind"], "html_canvas_effect")
            self.assertEqual(manifest["schema_version"], 1)
            self.assertIsInstance(manifest["inputs"], dict)
            self.assertIn("effect_id", manifest["inputs"])
            self.assertEqual(manifest["inputs"]["effect_id"], "glass-product-card")
            self.assertIsInstance(manifest["outputs"], list)
            output_paths = {o["path"] for o in manifest["outputs"]}
            self.assertIn(report_path.name, output_paths)
            # element_root is relative to manifest dir, so it uses ../
            self.assertTrue(any("glass-product-card" in p for p in output_paths),
                            f"element_root path not found in {output_paths}")
            self.assertIsInstance(manifest["warnings"], list)

    def test_canonical_cli_dry_run_uses_executor_runtime(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = executors_cli.main(
                [
                    "run",
                    "rendering.html_canvas_effect",
                    "--input",
                    "effect_id=glass-product-card",
                    "--out",
                    "runs/html-canvas-effect",
                    "--dry-run",
                ]
            )

        self.assertEqual(result, 0, stderr.getvalue())
        # The dry-run command echo goes to stderr; stdout carries the JSON
        # payload (run echo moved off stdout so `--json` can own the stream).
        self.assertIn("astrid.packs.rendering.executors.html_canvas_effect.run", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
