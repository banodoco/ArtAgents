from __future__ import annotations

import unittest

from astrid.core.executor.install import (
    build_executor_install_plan,
    executor_environment_path,
    executor_python_path,
)
from astrid.core.executor.registry import load_default_registry as load_executor_registry
from astrid.core.foundation.paths import REPO_ROOT


class ElementInstallTest(unittest.TestCase):

    def test_executor_install_paths_use_executor_cache_root_for_vibecomfy_and_moirae(self) -> None:
        registry = load_executor_registry()
        vibe_run = registry.get("vibecomfy.run")
        vibe_validate = registry.get("vibecomfy.validate")
        moirae = registry.get("moirae.moirae")

        self.assertEqual(executor_environment_path(vibe_run), executor_environment_path(vibe_validate))
        self.assertEqual(executor_python_path(vibe_run), executor_python_path(vibe_validate))
        self.assertEqual(executor_environment_path(vibe_run), REPO_ROOT / ".astrid" / "venvs" / "vibecomfy" / "venv")
        self.assertEqual(executor_environment_path(moirae), REPO_ROOT / ".astrid" / "venvs" / "moirae.moirae" / "venv")
        self.assertTrue(str(executor_environment_path(vibe_run)).endswith(".astrid/venvs/vibecomfy/venv"))
        self.assertTrue(str(executor_environment_path(moirae)).endswith(".astrid/venvs/moirae.moirae/venv"))

        vibe_plan = build_executor_install_plan(vibe_run)
        moirae_plan = build_executor_install_plan(moirae)
        self.assertEqual(vibe_plan.environment_path, executor_environment_path(vibe_run))
        self.assertEqual(moirae_plan.environment_path, executor_environment_path(moirae))
        self.assertIn("-r", vibe_plan.commands[1])
        self.assertIn("-r", moirae_plan.commands[1])


if __name__ == "__main__":
    unittest.main()
