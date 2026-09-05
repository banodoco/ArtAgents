"""Real-daemon conformance for the generated-client generic host boundary."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


RUNTIME = Path("/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime-fi6-identity-20260905")
if RUNTIME.is_dir():
    sys.path.insert(0, str(RUNTIME))

runtime_protocol = pytest.importorskip("runtime_protocol")
from banodoco_workspace_client import ApiError, WorkspaceClient  # noqa: E402
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
                # The runtime fixture is updated by the host registration below;
                # admission must use the exact discovered definition digest.
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

    # The host registers this discovered capability through the generated
    # client; admission then pins the same definition digest.
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
        assert registration["registration"].executor_id == "echo-host"
        capability = next(
            item
            for item in registration["registration"].capabilities
            if item.capability_id == record.id
        )
        assert capability.definition_digest == record.capability_digest

        project = generated.create_project(
            "Generic host", slug="generic-host", idempotency_key="generic-host-project"
        )
        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
            project_id=project.project_id,
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


def test_provider_fixture_is_credential_gated_then_settles_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Provider admission is honest without making a real network request."""
    monkeypatch.delenv("ASTRID_TEST_PROVIDER_KEY", raising=False)
    pack = tmp_path / "provider-pack"
    pack.mkdir()
    (pack / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "provider.echo",
                "name": "Offline Provider Echo",
                "kind": "external",
                "version": "1.0",
                "command": {
                    "argv": [
                        "{python_exec}",
                        "-c",
                        "from pathlib import Path; Path('{out}/answer.txt').write_text('offline-provider')",
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
                "isolation": {"mode": "subprocess", "network": True},
                "metadata": {
                    "adapter_family": "provider",
                    "resource_keys": ["provider"],
                    "network_policy": {
                        "allowed_protocols": ["dns", "tcp"],
                        "allowed_destinations": [],
                        "broker": {
                            "host_managed": True,
                            "kind": "broker",
                            "enforced": True,
                            "observable": True,
                            "route": "fixture",
                            "wrapper": "astrid-generic-host",
                        },
                        "descendant_enforcement": {
                            "kind": "broker",
                            "validated": True,
                            "observable": True,
                            "route": "fixture",
                            "wrapper": "astrid-generic-host",
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    matrix = tmp_path / "provider-matrix.json"
    matrix.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "capabilities": [
                    {
                        "id": "provider.echo",
                        "disposition": "required",
                        "evidence_reason": "Offline provider fixture",
                        "adapter_family": "provider",
                        "required_env": ["ASTRID_TEST_PROVIDER_KEY"],
                        "required_binaries": [],
                        "required_packages": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    try:
        generated = WorkspaceClient(daemon.endpoint, daemon.token)
        generated.handshake("provider-fixture-test", "0.1.0", ["projects:read", "worker:execute"])
        host = GenericPackHost(
            pack_roots=[pack],
            capability_matrix=matrix,
            client=RuntimeProtocolClient(daemon.endpoint, daemon.token),
            executor_id="provider-fixture-host",
        )
        record = host.discover()[0]
        host.preflight()
        assert host.capabilities[record.id].ready is False
        assert host.capabilities[record.id].preflight["network"] == {"ok": True}
        assert host.capabilities[record.id].preflight["credentials"]["missing"] == [
            "ASTRID_TEST_PROVIDER_KEY"
        ]

        host.register()
        capability_page, capability_cursor = generated.list_capabilities()
        assert capability_cursor is None
        capability = next(item for item in capability_page if item.capability_id == record.id)
        assert capability.status == "unavailable"
        assert capability.unavailable_reason == "credentials:missing=ASTRID_TEST_PROVIDER_KEY"
        with pytest.raises(ApiError, match="capability is not ready for admission"):
            generated.admit_task(
                capability_id=record.id,
                capability_digest=record.capability_digest,
                input_object_ids=[],
                idempotency_key="provider-fixture-task",
            )

        # Readiness changes only after the explicit credential is supplied;
        # the fixture command itself remains entirely offline.
        monkeypatch.setenv("ASTRID_TEST_PROVIDER_KEY", "fixture-secret")
        host.preflight()
        assert host.capabilities[record.id].ready is True
        host.register(deliberate=True)
        capability_page, capability_cursor = generated.list_capabilities()
        assert capability_cursor is None
        capability = next(item for item in capability_page if item.capability_id == record.id)
        assert capability.status == "ready"
        project = generated.create_project(
            "Provider fixture", slug="provider-fixture", idempotency_key="provider-fixture-project"
        )
        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
            project_id=project.project_id,
            idempotency_key="provider-fixture-ready-task",
        )
        settled = host.run(once=True)
        assert len(settled) == 1 and settled[0].state == "succeeded"
        digest = "sha256:" + hashlib.sha256(b"offline-provider").hexdigest()
        assert generated.get_object(digest).data == b"offline-provider"
    finally:
        daemon.stop()
