from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from astrid.application import compose_standard_application
from astrid.core import doctor
from astrid.core.gateway import setup as setup_cli
from astrid.core.structure import TOP_LEVEL_ASTRID_DIRS, validate_repo_structure

V10_CHECK_NAMES = {
    "python_version",
    "data_paths",
    "media_paths",
    "sqlite_quick_check",
    "fk_integrity",
    "schema_versions",
}

V10_CHECK_ORDER = [
    "python_version",
    "data_paths",
    "media_paths",
    "sqlite_quick_check",
    "fk_integrity",
    "schema_versions",
]


class DoctorSetupTest(unittest.TestCase):
    def capture(self, fn, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = fn(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def _fresh_project(self, root: Path) -> None:
        """Create a migrated database plus managed dirs under *root*."""
        with compose_standard_application(projects_root=root) as app:
            created = app.projects_service.create(
                slug="demo", name="Demo", idempotency_key="p1"
            )
        self.assertTrue(created.ok, created.error)

    def test_doctor_reports_exactly_six_v10_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fresh_project(root)
            checks = doctor.run_checks(projects_root=root)

        self.assertEqual([c.name for c in checks], V10_CHECK_ORDER)
        self.assertEqual({c.name for c in checks}, V10_CHECK_NAMES)
        for check in checks:
            self.assertEqual(check.status, "ok", check)
        media = next(c for c in checks if c.name == "media_paths")
        # A fresh project with no managed media tree is an optional "ok".
        self.assertFalse(media.required)

    def test_doctor_json_shape_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fresh_project(root)
            result, stdout, stderr = self.capture(
                doctor.main, ["--json", "--projects-root", str(root)]
            )

        self.assertEqual(result, 0, stderr)
        payload = json.loads(stdout)
        self.assertEqual(set(payload), {"ok", "checks"})
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["checks"]), 6)
        for item in payload["checks"]:
            self.assertEqual(set(item), {"name", "status", "detail", "required"})
            self.assertIn(item["name"], V10_CHECK_NAMES)

    def test_doctor_text_output_lists_v10_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fresh_project(root)
            result, stdout, stderr = self.capture(
                doctor.main, ["--projects-root", str(root)]
            )

        self.assertEqual(result, 0, stderr)
        self.assertIn("Astrid doctor", stdout)
        for name in V10_CHECK_NAMES:
            self.assertIn(f"[ok] {name}:", stdout)

    def test_doctor_fails_closed_on_missing_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".astrid").mkdir()
            checks = doctor.run_checks(projects_root=root)
            result, stdout, stderr = self.capture(
                doctor.main, ["--json", "--projects-root", str(root)]
            )

        by_name = {c.name: c for c in checks}
        for name in ("sqlite_quick_check", "fk_integrity", "schema_versions"):
            self.assertEqual(by_name[name].status, "fail", by_name[name])
        self.assertEqual(result, 1)
        payload = json.loads(stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["checks"]), 6)

    def test_doctor_fails_closed_on_corrupt_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".astrid").mkdir()
            (root / ".astrid" / "astrid.sqlite3").write_bytes(
                b"not a sqlite database"
            )
            checks = doctor.run_checks(projects_root=root)
            result, stdout, stderr = self.capture(
                doctor.main, ["--json", "--projects-root", str(root)]
            )

        by_name = {c.name: c for c in checks}
        for name in ("sqlite_quick_check", "fk_integrity", "schema_versions"):
            self.assertEqual(by_name[name].status, "fail", by_name[name])
        self.assertEqual(result, 1)
        payload = json.loads(stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(len(payload["checks"]), 6)

    def test_doctor_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._fresh_project(root)
            db_path = root / ".astrid" / "astrid.sqlite3"
            before = db_path.read_bytes()
            doctor.run_checks(projects_root=root)
            doctor.main(["--json", "--projects-root", str(root)])
            after = db_path.read_bytes()

        self.assertEqual(before, after)

    def test_setup_dry_run_does_not_mutate_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with mock.patch.object(setup_cli, "REPO_ROOT", project_root):
                result, stdout, stderr = self.capture(setup_cli.main, [])

            self.assertEqual(result, 0, stderr)
            self.assertIn("Astrid setup", stdout)
            self.assertIn("dry-run: pass --apply", stdout)
            self.assertNotIn("elements sync", stdout)
            self.assertFalse((project_root / ".astrid" / "elements" / "managed").exists())
            self.assertFalse((project_root / "astrid" / "packs" / "local").exists())

    def test_setup_json_dry_run_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            with mock.patch.object(setup_cli, "REPO_ROOT", project_root):
                result, stdout, stderr = self.capture(setup_cli.main, ["--json"])

        self.assertEqual(result, 0, stderr)
        payload = json.loads(stdout)
        self.assertFalse(payload["applied"])
        self.assertIn("dry-run", {step["status"] for step in payload["steps"]})

    def test_setup_apply_does_not_create_root_skill_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            core_skill = project_root / "astrid" / "packs" / "_core" / "skill" / "SKILL.md"
            core_skill.parent.mkdir(parents=True)
            core_skill.write_text("---\nname: astrid\n---\n", encoding="utf-8")

            with mock.patch.object(setup_cli, "REPO_ROOT", project_root):
                result, stdout, stderr = self.capture(setup_cli.main, ["--apply"])

            self.assertEqual(result, 0, stderr)
            for name in ("AGENTS.md", "SKILL.md"):
                path = project_root / name
                self.assertFalse(path.exists(), name)
                self.assertFalse(path.is_symlink(), name)
            self.assertNotIn("root skill symlinks", stdout)
            self.assertNotIn("AGENTS.md", stdout)
            self.assertNotIn("SKILL.md", stdout)

    def test_top_level_dirs_are_collapsed_to_canonical_roots(self) -> None:
        self.assertEqual(TOP_LEVEL_ASTRID_DIRS, {"core", "packs", "sdk", "skills"})

    def test_repo_structure_guard_rejects_legacy_and_misplaced_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "astrid" / "conductors").mkdir(parents=True)
            (root / "astrid" / "tools" / "reigh-data").mkdir(parents=True)
            external_pack_dir = root / "astrid" / "packs" / "external"
            external_pack_dir.mkdir(parents=True)
            (external_pack_dir / "pack.yaml").write_text("id: external\n", encoding="utf-8")
            mixed_orchestrator = external_pack_dir / "vibecomfy"
            mixed_orchestrator.mkdir(parents=True)
            (mixed_orchestrator / "STAGE.md").write_text("# stage\n", encoding="utf-8")
            (mixed_orchestrator / "run.py").write_text("", encoding="utf-8")
            (mixed_orchestrator / "orchestrator.yaml").write_text(
                "\n".join(
                    [
                        "id: external.vibecomfy",
                        "name: VibeComfy",
                        "kind: external",
                        "version: '1.0'",
                        "runtime:",
                        "  kind: command",
                        "  command:",
                        "    argv: [\"echo\", \"vibe\"]",
                    ]
                ),
                encoding="utf-8",
            )
            (mixed_orchestrator / "executor.yaml").write_text(
                "\n".join(
                    [
                        "id: vibecomfy.run",
                        "name: VibeComfy Run",
                        "kind: external",
                        "version: '1.0'",
                        "command:",
                        "  argv: [\"echo\", \"run\"]",
                    ]
                ),
                encoding="utf-8",
            )
            misplaced_executor = external_pack_dir / "render"
            misplaced_executor.mkdir(parents=True)
            (misplaced_executor / "STAGE.md").write_text("# stage\n", encoding="utf-8")
            (misplaced_executor / "run.py").write_text("", encoding="utf-8")
            (misplaced_executor / "executor.yaml").write_text(
                "\n".join(
                    [
                        "id: rendering.render",
                        "name: Render",
                        "kind: built_in",
                        "version: '1.0'",
                        "command:",
                        "  argv: [\"echo\", \"render\"]",
                    ]
                ),
                encoding="utf-8",
            )

            report = validate_repo_structure(root)

        self.assertFalse(report.ok)
        detail = "\n".join(report.errors)
        self.assertIn("legacy public package must not exist: astrid/conductors", detail)
        self.assertIn("top-level astrid directory is not a canonical concept: astrid/tools", detail)
        self.assertIn(
            "orchestrator folder contains executor metadata: astrid/packs/external/vibecomfy",
            detail,
        )
        self.assertIn("executor 'rendering.render' must live in pack 'rendering' but was found in pack 'external'", detail)


if __name__ == "__main__":
    unittest.main()
