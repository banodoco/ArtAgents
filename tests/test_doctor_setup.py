from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from astrid.core import doctor, setup_cli
from astrid.core.element.registry import load_default_registry as load_element_registry
from astrid.core.project.project import create_project
from astrid.core.structure import TOP_LEVEL_ASTRID_DIRS, validate_repo_structure


class DoctorSetupTest(unittest.TestCase):
    def capture(self, fn, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = fn(argv)
        return result, stdout.getvalue(), stderr.getvalue()

    def _stable_env_template_check(self) -> doctor.DoctorCheck:
        return doctor.DoctorCheck(
            name="env template",
            status="ok",
            detail="test-provisioned env template",
            required=False,
        )

    def test_doctor_text_and_json_reports_required_checks(self) -> None:
        with mock.patch.object(doctor, "_check_env_template", side_effect=self._stable_env_template_check):
            result, stdout, stderr = self.capture(doctor.main, [])

        self.assertEqual(result, 0, stderr)
        self.assertIn("Astrid doctor", stdout)
        self.assertIn("[ok] python:", stdout)
        self.assertIn("[ok] dependency audit:", stdout)
        self.assertIn("[ok] env template:", stdout)
        self.assertIn("[ok] executor registry:", stdout)
        self.assertIn("[ok] orchestrator registry:", stdout)
        self.assertIn("[ok] element registry:", stdout)
        self.assertIn("[ok] repo structure:", stdout)
        self.assertIn("[ok] vibecomfy metadata:", stdout)
        self.assertIn("[ok] remotion config:", stdout)
        self.assertIn("[ok] timeline catalog:", stdout)
        self.assertIn("stale project runs:", stdout)
        self.assertIn("runpod stale handles:", stdout)

        with mock.patch.object(doctor, "_check_env_template", side_effect=self._stable_env_template_check):
            result, stdout, stderr = self.capture(doctor.main, ["--json"])
        self.assertEqual(result, 0, stderr)
        payload = json.loads(stdout)
        self.assertTrue(payload["ok"])
        self.assertIn("repo structure", {item["name"] for item in payload["checks"]})
        self.assertIn("vibecomfy metadata", {item["name"] for item in payload["checks"]})
        self.assertIn("dependency audit", {item["name"] for item in payload["checks"]})
        self.assertIn("env template", {item["name"] for item in payload["checks"]})
        self.assertIn("stale project runs", {item["name"] for item in payload["checks"]})

    def test_doctor_required_check_failure_returns_nonzero(self) -> None:
        with mock.patch.object(doctor, "load_executor_registry", side_effect=RuntimeError("registry exploded")):
            result, stdout, stderr = self.capture(doctor.main, [])

        self.assertEqual(result, 1)
        self.assertEqual(stderr, "")
        self.assertIn("[fail] executor registry: registry exploded", stdout)

    def test_doctor_optional_binaries_warn_by_default_and_can_be_strict(self) -> None:
        with mock.patch.object(doctor.shutil, "which", return_value=None), mock.patch.object(
            doctor,
            "_check_env_template",
            side_effect=self._stable_env_template_check,
        ):
            result, stdout, stderr = self.capture(doctor.main, [])
            strict_result, strict_stdout, strict_stderr = self.capture(doctor.main, ["--strict-optional"])

        self.assertEqual(result, 0, stderr)
        self.assertIn("[warn] optional binary ffmpeg: not found on PATH", stdout)
        self.assertEqual(strict_result, 1, strict_stderr)
        self.assertIn("[warn] optional binary ffmpeg: not found on PATH", strict_stdout)

    def test_dependency_audit_and_env_template_succeed_for_minimal_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "astrid").mkdir()
            (root / "astrid" / "app.py").write_text("import requests\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "tmp"',
                        'version = "0.0.0"',
                        "dependencies = [",
                        '  "requests>=2",',
                        "]",
                    ]
                ),
                encoding="utf-8",
            )
            (root / ".env.example").write_text(
                "\n".join(
                    [
                        "# Required: populate for API calls",
                        "OPENAI_API_KEY=",
                        "# Optional: only for alternate providers",
                        "GEMINI_API_KEY=",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = root / ".env"
            env_file.write_text("OPENAI_API_KEY=test-value\n", encoding="utf-8")

            dependency_check = doctor._check_dependency_audit(repo_root=root)
            env_check = doctor._check_env_template(repo_root=root, environ={}, env_candidates=[env_file])

        self.assertEqual(dependency_check.status, "ok")
        self.assertIn("third-party import", dependency_check.detail)
        self.assertEqual(env_check.status, "ok")
        self.assertIn("required key(s) present", env_check.detail)

    def test_env_template_check_fails_for_missing_required_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.example").write_text(
                "\n".join(
                    [
                        "# Required: populate for API calls",
                        "OPENAI_API_KEY=",
                        "# Optional: alternate provider",
                        "GEMINI_API_KEY=",
                    ]
                ),
                encoding="utf-8",
            )
            env_file = root / ".env"
            env_file.write_text("GEMINI_API_KEY=unused\n", encoding="utf-8")

            check = doctor._check_env_template(repo_root=root, environ={}, env_candidates=[env_file])

        self.assertEqual(check.status, "fail")
        self.assertIn("OPENAI_API_KEY", check.detail)

    def test_dependency_audit_fails_for_undeclared_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "astrid").mkdir()
            (root / "astrid" / "app.py").write_text("import requests\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "tmp"',
                        'version = "0.0.0"',
                        "dependencies = [",
                        '  "filelock>=3.13",',
                        "]",
                    ]
                ),
                encoding="utf-8",
            )

            check = doctor._check_dependency_audit(repo_root=root)

        self.assertEqual(check.status, "fail")
        self.assertIn("requests", check.detail)

    def test_dependency_audit_ignores_pack_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "astrid" / "packs" / "demo").mkdir(parents=True)
            (root / "astrid" / "core").mkdir(parents=True)
            (root / "astrid" / "core" / "app.py").write_text("import json\n", encoding="utf-8")
            (root / "astrid" / "packs" / "demo" / "run.py").write_text("import requests\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "tmp"',
                        'version = "0.0.0"',
                        "dependencies = [",
                        '  "filelock>=3.13",',
                        "]",
                    ]
                ),
                encoding="utf-8",
            )

            check = doctor._check_dependency_audit(repo_root=root)

        self.assertEqual(check.status, "ok")

    def test_dependency_audit_warns_for_missing_private_runpod_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "astrid").mkdir()
            (root / "astrid" / "app.py").write_text("import runpod_lifecycle\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                "\n".join(
                    [
                        "[project]",
                        'name = "tmp"',
                        'version = "0.0.0"',
                        "dependencies = [",
                        '  "filelock>=3.13",',
                        "]",
                    ]
                ),
                encoding="utf-8",
            )

            real_find_spec = doctor.importlib.util.find_spec

            def fake_find_spec(name: str):
                if name == "runpod_lifecycle":
                    return None
                return real_find_spec(name)

            with mock.patch.object(doctor.importlib.util, "find_spec", side_effect=fake_find_spec), mock.patch.object(
                doctor.importlib.metadata,
                "packages_distributions",
                return_value={"filelock": ["filelock"]},
            ):
                check = doctor._check_dependency_audit(repo_root=root)

        self.assertEqual(check.status, "warn")
        self.assertFalse(check.required)
        self.assertIn("runpod-lifecycle", check.detail)

    def test_doctor_repairs_confidently_dead_project_run_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            projects_root = Path(tmp)
            create_project("demo", root=projects_root)
            run_dir = projects_root / "demo" / "runs" / "01ARZ3NDEKTSV4RRFFQ69G5FAA"
            run_dir.mkdir(parents=True)
            run_json = run_dir / "run.json"
            run_json.write_text(
                json.dumps(
                    {
                        "artifacts": {},
                        "created_at": "2026-06-04T00:00:00Z",
                        "kind": "executor",
                        "metadata": {
                            "pid": 424242,
                            "prepared_at": "2026-06-04T00:00:00Z",
                            "process_platform": sys.platform,
                        },
                        "out": str(run_dir),
                        "project_slug": "demo",
                        "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAA",
                        "schema_version": 1,
                        "status": "running",
                        "updated_at": "2026-06-04T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(doctor, "_probe_pid_liveness", return_value="dead"), mock.patch(
                "astrid.core.project.paths.resolve_projects_root",
                return_value=projects_root,
            ):
                check = doctor._check_stale_project_runs()

            repaired = json.loads(run_json.read_text(encoding="utf-8"))

        self.assertEqual(check.status, "warn")
        self.assertIn("repaired 1 stale RUNNING project run", check.detail)
        self.assertEqual(repaired["status"], "failed")
        self.assertEqual(repaired["metadata"]["doctor_repair"]["kind"], "stale_running")
        self.assertEqual(repaired["metadata"]["doctor_repair"]["liveness"], "dead")
        self.assertIn("astrid doctor repaired stale RUNNING record", repaired["metadata"]["error"])

    def test_doctor_leaves_running_record_untouched_when_liveness_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            projects_root = Path(tmp)
            create_project("demo", root=projects_root)
            run_dir = projects_root / "demo" / "runs" / "01ARZ3NDEKTSV4RRFFQ69G5FAB"
            run_dir.mkdir(parents=True)
            run_json = run_dir / "run.json"
            original = {
                "artifacts": {},
                "created_at": "2026-06-04T00:00:00Z",
                "kind": "executor",
                "metadata": {
                    "pid": 424243,
                    "prepared_at": "2026-06-04T00:00:00Z",
                    "process_platform": "different-platform",
                },
                "out": str(run_dir),
                "project_slug": "demo",
                "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAB",
                "schema_version": 1,
                "status": "running",
                "updated_at": "2026-06-04T00:00:00Z",
            }
            run_json.write_text(json.dumps(original), encoding="utf-8")

            with mock.patch(
                "astrid.core.project.paths.resolve_projects_root",
                return_value=projects_root,
            ):
                check = doctor._check_stale_project_runs()

            unchanged = json.loads(run_json.read_text(encoding="utf-8"))

        self.assertEqual(check.status, "warn")
        self.assertIn("liveness was unknown", check.detail)
        self.assertEqual(unchanged, original)

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

    def test_setup_apply_delegates_to_install_helpers(self) -> None:
        registry = load_element_registry()
        element = registry.get("effects", "text-card")
        fake_registry = SimpleNamespace(list=lambda: (element,))
        fake_plan = SimpleNamespace(noop_reason="no dependencies declared", command_lines=lambda: ())
        fake_result = SimpleNamespace(plan=fake_plan)

        with mock.patch.object(
            setup_cli, "load_element_registry", return_value=fake_registry
        ) as load_registry, mock.patch.object(setup_cli, "install_element", return_value=fake_result) as install:
            result, stdout, stderr = self.capture(setup_cli.main, ["--apply"])

        self.assertEqual(result, 0, stderr)
        load_registry.assert_called_once_with(project_root=setup_cli.REPO_ROOT)
        install.assert_called_once_with(element, project_root=setup_cli.REPO_ROOT, dry_run=False)
        self.assertNotIn("elements sync", stdout)
        self.assertIn("[skipped] elements install: effects/text-card: no dependencies declared", stdout)

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
