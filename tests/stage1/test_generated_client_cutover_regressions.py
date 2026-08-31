"""Pass-ready regression tests for the remaining generated-client cutover gaps.

These tests intentionally remain uncommitted until the generated runtime
operations and raw transport seam are implemented.
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

from astrid.sdk.remote import RemoteAstridClient, RemoteProjects, RemoteTasks


class _RecordingClient:
    def __init__(self) -> None:
        self.project_call: tuple[tuple[object, ...], dict[str, object]] | None = None
        self.task_call: dict[str, object] | None = None

    def create_project(self, *args: object, **kwargs: object) -> dict[str, str]:
        self.project_call = (args, kwargs)
        return {"project_id": "project-1"}

    def list_capabilities(self) -> list[dict[str, str]]:
        return [{"capability_id": "capability-1", "definition_digest": "digest-1"}]

    def admit_task(self, **kwargs: object) -> dict[str, str]:
        self.task_call = kwargs
        return {"task_id": "task-1"}


class _ReceiptClient(_RecordingClient):
    def admit_task(self, **kwargs: object) -> dict[str, object]:
        self.task_call = kwargs
        return {
            "data": {"task_id": "task-1"},
            "receipt": {
                "receipt_id": "txn-1",
                "command_kind": "task.create",
                "idempotency_key": str(kwargs["idempotency_key"]),
                "request_hash": "hash-1",
                "project_id": "project-1",
                "project_seq": [1, 1],
                "event_ids": ["event-1"],
                "result": {"task_id": "task-1"},
                "created_at": "2026-01-01T00:00:00Z",
            },
        }


class GeneratedClientCutoverRegressionTest(unittest.TestCase):
    def test_project_create_forwards_slug_and_metadata(self) -> None:
        client = _RecordingClient()
        result = RemoteProjects(client).create(
            slug="demo",
            name="Demo",
            metadata={"theme": "dark"},
            idempotency_key="project-key",
        )

        self.assertTrue(result.ok)
        assert client.project_call is not None
        args, kwargs = client.project_call
        self.assertEqual(args, ("Demo",))
        self.assertEqual(kwargs["slug"], "demo")
        self.assertEqual(kwargs["metadata"], {"theme": "dark"})
        self.assertEqual(kwargs["idempotency_key"], "project-key")

    def test_task_create_forwards_spec(self) -> None:
        client = _RecordingClient()
        spec = {"prompt": "a generated client regression"}
        result = RemoteTasks(client).create(
            project_id="project-1",
            capability="capability-1",
            spec=spec,
            input_manifest=["sha256:input"],
            idempotency_key="task-key",
        )

        self.assertTrue(result.ok)
        assert client.task_call is not None
        self.assertEqual(client.task_call["spec"], spec)
        self.assertEqual(client.task_call["capability_id"], "capability-1")
        self.assertEqual(client.task_call["input_object_ids"], ["sha256:input"])

    def test_generic_invoke_forwards_server_receipt(self) -> None:
        result = RemoteAstridClient(_ReceiptClient()).invoke(
            "capability-1", project_id="project-1", spec={}, idempotency_key="task-key"
        )
        self.assertTrue(result.ok)
        assert result.receipt is not None
        self.assertEqual(result.receipt.receipt_id, "txn-1")
        self.assertEqual(result.receipt.event_ids, ("event-1",))

    def test_product_sdk_has_no_raw_request_seam(self) -> None:
        sdk_root = Path(__file__).resolve().parents[2] / "astrid" / "sdk"
        offenders: list[str] = []
        for path in sorted(sdk_root.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "request":
                    offenders.append(f"{path.name}:{node.lineno}: request()")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "request"
                ):
                    offenders.append(f"{path.name}:{node.lineno}: .request")
        self.assertEqual(offenders, [], "raw transport seams remain: " + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
