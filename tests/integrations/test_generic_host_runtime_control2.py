"""Real-daemon conformance for the generated-client generic host boundary."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


RUNTIME = Path("/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime-stage1-convergence")
if RUNTIME.is_dir():
    sys.path.insert(0, str(RUNTIME / "packages/python"))
    sys.path.insert(0, str(RUNTIME))

runtime_protocol = pytest.importorskip("runtime_protocol")
from banodoco_workspace_client import WorkspaceClient  # noqa: E402
from runtime_protocol.daemon import RuntimeDaemon  # noqa: E402

from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient  # noqa: E402


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


def test_generated_host_echo_claim_cas_settlement_and_restart(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                # control2 seeds this neutral fixture capability on every
                # realm; the command body is the testing.echo actor.
                "id": "render.basic",
                "name": "Testing Echo",
                "kind": "external",
                "version": "1.0",
                "command": {
                    "argv": [
                        "{python_exec}",
                        "-c",
                        "from pathlib import Path; Path('{out}/answer.txt').write_text('hello')",
                    ]
                },
                "outputs": [
                    {
                        "name": "answer",
                        "type": "file",
                        "path_template": "{out}/answer.txt",
                        "artifact_type": "text/plain",
                    }
                ],
                "metadata": {"adapter_family": "cpu", "resource_keys": ["cpu"]},
            }
        ),
        encoding="utf-8",
    )

    # Use the daemon's seeded neutral fixture capability.  Capability
    # registration is intentionally not reimplemented through raw HTTP here.
    probe = GenericPackHost(pack_roots=[pack])
    record = probe.discover()[0]

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    try:
        generated = WorkspaceClient(daemon.endpoint, daemon.token)
        generated.handshake("astrid-generic-host-test", "0.1.0", ["projects:read", "worker:execute"])
        host = GenericPackHost(
            pack_roots=[pack],
            client=RuntimeProtocolClient(daemon.endpoint, daemon.token),
            executor_id="echo-host",
        )
        registration = host.register()
        assert registration["registration"]["executor_id"] == "echo-host"
        assert registration["registration"]["capability_digests"][record.id] == record.capability_digest

        task = generated.admit_task(
            capability_id=record.id,
            capability_digest="sha256:" + hashlib.sha256(record.id.encode()).hexdigest(),
            input_object_ids=[],
            idempotency_key="echo-task",
        )
        results = host.run(once=True)
        assert len(results) == 1 and results[0].state == "succeeded"
        output_digest = _digest("hello")
        assert generated.get_object(output_digest).data == b"hello"
        assert not list(tmp_path.glob("astrid-attempt-*"))

        daemon.stop()
        daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
        restarted = WorkspaceClient(daemon.endpoint, daemon.token)
        restarted.handshake("astrid-generic-host-test-reconnect", "0.1.0", ["projects:read", "worker:execute"])
        assert restarted.get_task(task.task_id).state == "succeeded"
        assert restarted.get_object(output_digest).data == b"hello"
    finally:
        daemon.stop()
