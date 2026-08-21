from __future__ import annotations

import contextlib
import io
import unittest

from astrid.core.contracts.errors import AstridError, render_astrid_error
from astrid.core.execution.executor.schema import ExecutorValidationError, validate_executor_definition
from astrid.core.execution.orchestrator.schema import OrchestratorValidationError, validate_orchestrator_definition


def _capture(fn, argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            result = fn(argv)
        except AstridError as exc:
            result = render_astrid_error(exc)
    return result, stdout.getvalue(), stderr.getvalue()


class QualifiedIdEnforcementTest(unittest.TestCase):
    def test_executor_schema_rejects_bare_ids(self) -> None:
        with self.assertRaisesRegex(ExecutorValidationError, "executor.id must be qualified"):
            validate_executor_definition(
                {
                    "id": "cut",
                    "name": "Cut",
                    "kind": "built_in",
                    "version": "1.0",
                }
            )

    def test_executor_schema_rejects_bare_dependencies(self) -> None:
        with self.assertRaisesRegex(ExecutorValidationError, "graph.depends_on"):
            validate_executor_definition(
                {
                    "id": "video_editing.cut",
                    "name": "Cut",
                    "kind": "built_in",
                    "version": "1.0",
                    "graph": {"depends_on": ["transcribe"]},
                }
            )

    def test_orchestrator_schema_rejects_bare_ids_and_children(self) -> None:
        with self.assertRaisesRegex(OrchestratorValidationError, "orchestrator.id must be qualified"):
            validate_orchestrator_definition(
                {
                    "id": "hype",
                    "name": "Hype",
                    "kind": "built_in",
                    "version": "1.0",
                    "runtime": {"kind": "command", "command": {"argv": ["echo", "ok"]}},
                }
            )

        with self.assertRaisesRegex(OrchestratorValidationError, "orchestrator.child_executors"):
            validate_orchestrator_definition(
                {
                    "id": "video_editing.hype",
                    "name": "Hype",
                    "kind": "built_in",
                    "version": "1.0",
                    "runtime": {"kind": "command", "command": {"argv": ["echo", "ok"]}},
                    "child_executors": ["cut"],
                }
            )

if __name__ == "__main__":
    unittest.main()
