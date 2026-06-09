from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OnboardingDocsTest(unittest.TestCase):
    def read_docs(self) -> str:
        return "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "astrid/packs/_core/skill/SKILL.md",
                "docs/reference/architecture.md",
                "docs/guides/creating-tools.md",
            )
        )

    def run_astrid(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "docs-command-smoke")}
        return subprocess.run(
            [sys.executable, "-m", "astrid", *args],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_onboarding_docs_name_canonical_terms_and_guardrails(self) -> None:
        text = self.read_docs()
        required = (
            "orchestrators",
            "executors",
            "elements",
            "git status --short",
            "python3 -m astrid doctor",
            "python3 -m astrid --help",
            "python3 -m astrid",
            "executable package gateway",
            "python3 -m astrid setup",
            "astrid/packs/local/elements",
            "python3 scripts/gen_effect_registry.py",
            "astrid/packs/moirae/executors/moirae/STAGE.md",
            "astrid/packs/vibecomfy/executors/run/STAGE.md",
            "astrid/packs/<pack>/<slug>/{executor.yaml,STAGE.md,run.py}",
            "astrid/packs/<pack>/<slug>/{orchestrator.yaml,STAGE.md,run.py}",
            "Top-level `astrid/*.py`",
            "examples/briefs/",
            "docs/guides/creating-tools.md",
            "docs/templates/executor/",
            "docs/templates/orchestrator/",
            "docs/templates/element/",
            "Create an **executor**",
            "Create an **orchestrator**",
            "Create an **element**",
            "Do not chain pipeline internals by hand",
            "brief-generation executor",
            "hype.assets.json",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        forbidden = (
            "python3 pipeline.py",
            "pipeline.py remains",
            "python3 -m astrid conductors list",
            "python3 -m astrid performers list",
            "python3 -m astrid instruments list",
            "python3 -m astrid primitives list",
            "astrid/performers/curated",
            "astrid/conductors/curated",
            "Legacy public alias",
            "Compatibility aliases",
            "astrid/event_talks.py",
            "astrid/thumbnail_maker.py",
            "astrid/understand.py",
            "astrid/skills/reigh-data",
        )
        for phrase in forbidden:
            with self.subTest(forbidden=phrase):
                self.assertNotIn(phrase, text)

    def test_docs_visible_unbound_commands_are_dispatchable(self) -> None:
        commands = (
            ("status",),
            ("next",),
            ("packs", "list", "--json"),
            ("projects", "ls", "--json"),
            ("sessions", "ls"),
        )
        for command in commands:
            with self.subTest(command=command):
                result = self.run_astrid(*command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(result.stdout.strip())

    def test_creation_templates_exist(self) -> None:
        required = (
            "docs/templates/executor/executor.yaml",
            "docs/templates/executor/run.py",
            "docs/templates/executor/STAGE.md",
            "docs/templates/orchestrator/orchestrator.yaml",
            "docs/templates/orchestrator/run.py",
            "docs/templates/orchestrator/STAGE.md",
            "docs/templates/element/component.tsx",
            "docs/templates/element/STAGE.md",
            "docs/templates/element/element.yaml",
        )
        for path in required:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())


if __name__ == "__main__":
    unittest.main()
