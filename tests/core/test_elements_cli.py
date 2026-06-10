import json
import os
import tempfile
import unittest
from pathlib import Path

from astrid.core.element import cli
from astrid.core.pack.override import OverrideStore
from tests.helpers.cli_runner import run_cli


class ElementsCliTest(unittest.TestCase):
    def capture(self, argv):
        r = run_cli(cli.main, argv)
        return r.exit_code, r.stdout, r.stderr

    def write_custom_pack(self, root: Path) -> Path:
        pack_root = root / "demo"
        pack_root.mkdir(parents=True)
        (pack_root / "pack.json").write_text(
            json.dumps(
                {
                    "id": "demo",
                    "name": "Demo Pack",
                    "version": "0.1.0",
                    "schema_version": "1",
                    "extensions": {
                        "elements": {
                            "kinds": [
                                {"id": "widgets", "singular": "widget"},
                            ]
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        element_root = pack_root / "elements" / "widgets" / "glow"
        element_root.mkdir(parents=True)
        (element_root / "component.tsx").write_text(
            "export default function Glow() { return null; }\n",
            encoding="utf-8",
        )
        (element_root / "element.yaml").write_text(
            json.dumps(
                {
                    "id": "glow",
                    "kind": "widget",
                    "pack_id": "demo",
                    "metadata": {"label": "Glow"},
                    "schema": {"type": "object"},
                    "defaults": {"enabled": True},
                    "dependencies": {"js_packages": [], "python_requirements": []},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        return root

    def test_list_inspect_and_validate(self) -> None:
        result, stdout, stderr = self.capture(["list", "--json", "--kind", "effects"])
        self.assertEqual(result, 0, stderr)
        payload = json.loads(stdout)
        self.assertIn("text-card", {item["id"] for item in payload["elements"]})

        result, stdout, stderr = self.capture(["inspect", "effects", "text-card", "--json"])
        self.assertEqual(result, 0, stderr)
        self.assertEqual(json.loads(stdout)["id"], "text-card")

        result, stdout, stderr = self.capture(["validate", "effects", "text-card"])
        self.assertEqual(result, 0, stderr)
        self.assertIn("effects/text-card: ok", stdout)

    def test_singular_kind_aliases_work_in_cli(self) -> None:
        result, stdout, stderr = self.capture(["list", "--json", "--kind", "effect"])
        self.assertEqual(result, 0, stderr)
        payload = json.loads(stdout)
        self.assertIn("text-card", {item["id"] for item in payload["elements"]})

        result, stdout, stderr = self.capture(["inspect", "effect", "text-card", "--json"])
        self.assertEqual(result, 0, stderr)
        inspected = json.loads(stdout)
        self.assertEqual(inspected["kind"], "effects")

    def test_pack_declared_kind_works_in_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self.write_custom_pack(Path(tmp))

            result, stdout, stderr = self.capture(
                ["--pack-root", str(pack_root), "list", "--json", "--kind", "widget"]
            )
            self.assertEqual(result, 0, stderr)
            payload = json.loads(stdout)
            self.assertEqual({item["id"] for item in payload["elements"]}, {"glow"})

            result, stdout, stderr = self.capture(
                ["--pack-root", str(pack_root), "inspect", "widget", "glow", "--json"]
            )
            self.assertEqual(result, 0, stderr)
            inspected = json.loads(stdout)
            self.assertEqual(inspected["kind"], "widgets")

    def test_pack_declared_kind_is_searchable_in_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self.write_custom_pack(Path(tmp))

            result, stdout, stderr = self.capture(
                ["--pack-root", str(pack_root), "search", "glow", "--json"]
            )

            self.assertEqual(result, 0, stderr)
            payload = json.loads(stdout)
            self.assertEqual(len(payload["hits"]), 1)
            self.assertEqual(payload["hits"][0]["id"], "glow")
            self.assertEqual(payload["hits"][0]["kind"], "widgets")

    def test_invalid_kind_error_lists_dynamic_valid_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_root = self.write_custom_pack(Path(tmp))

            result, stdout, stderr = self.capture(
                ["--pack-root", str(pack_root), "list", "--kind", "wigdet"]
            )

        self.assertEqual(result, 2)
        self.assertEqual(stdout, "")
        self.assertIn("element kind must be one of [effects, animations, transitions, widgets]", stderr)

    def test_non_repo_cwd_keeps_mutable_element_state_project_local(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(project)
            try:
                result, stdout, stderr = self.capture(["list", "--json", "--kind", "effects"])
                self.assertEqual(result, 0, stderr)
                payload = json.loads(stdout)
                self.assertIn("text-card", {item["id"] for item in payload["elements"]})

                # Set override via OverrideStore API (CLI override subcommand removed in S4).
                store = OverrideStore(project_root=project)
                store.set_override("effects", "text-card", "text-card")

                overrides = project / "astrid" / "packs" / "local" / ".overrides.json"
                self.assertTrue(overrides.is_file())
                override_payload = json.loads(overrides.read_text(encoding="utf-8"))
                self.assertEqual(override_payload["effects"]["text-card"], "text-card")

                result, stdout, stderr = self.capture(["list", "--json", "--kind", "effects", "--show-overrides"])
                self.assertEqual(result, 0, stderr)
                listed = {item["id"]: item for item in json.loads(stdout)["elements"]}
                self.assertEqual(listed["text-card"]["_override"], "text-card")
            finally:
                os.chdir(previous_cwd)



if __name__ == "__main__":
    unittest.main()
