"""B13.1 provider journey through the generic host and real runtime."""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from banodoco_workspace_client import WorkspaceClient
from runtime_protocol.daemon import RuntimeDaemon

from astrid.core.execution.generic_host import GenericPackHost, RuntimeProtocolClient


def test_provider_journey_is_brokered_settled_and_cannot_bypass_upstream(tmp_path: Path) -> None:
    """Exercise provider readiness, live route ownership, CAS, and bypass denial."""

    class ProviderHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            body = b"provider-output-v1"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    upstream_url = f"http://127.0.0.1:{upstream.server_port}/result"

    pack = tmp_path / "provider-pack"
    executor = pack / "executors" / "fetch"
    executor.mkdir(parents=True)
    (pack / "pack.yaml").write_text(
        "schema_version: 1\n"
        "id: b13_provider\nname: B13 Provider\nversion: 1.0\n"
        "content:\n  executors: executors\n",
        encoding="utf-8",
    )
    command = (
        "import atexit, json, os, socket; from pathlib import Path; from urllib.request import urlopen, ProxyHandler, build_opener\n"
        "Path('{out}/signing-key-absent').write_text(str('ASTRID_NETWORK_AUTH_TOKEN' not in os.environ), encoding='utf-8')\n"
        f"url = {upstream_url!r}\n"
        "body = urlopen(url, timeout=3).read()\n"
        "Path('{out}/result').write_bytes(body)\n"
        "try:\n"
        "    build_opener(ProxyHandler({})).open(url, timeout=2).read()\n"
        "except Exception as exc:\n"
        "    Path('{out}/bypass-denied').write_text(type(exc).__name__, encoding='utf-8')\n"
        "try:\n"
        "    from astrid.core.execution import network_policy\n"
        "    original = network_policy._ORIGINALS[(socket.socket, 'connect')]\n"
        f"    raw = socket.socket(); original(raw, ('127.0.0.1', {upstream.server_port})); raw.close()\n"
        "    Path('{out}/primitive-bypass-allowed').write_text('allowed', encoding='utf-8')\n"
        "except Exception as exc:\n"
        "    Path('{out}/primitive-bypass-denied').write_text(type(exc).__name__, encoding='utf-8')\n"
        "try:\n"
        "    originals = next(cell.cell_contents for cell in (socket.socket.connect.__closure__ or ()) if isinstance(cell.cell_contents, dict))\n"
        f"    raw = socket.socket(); originals[(socket.socket, 'connect')](raw, ('127.0.0.1', {upstream.server_port})); raw.close()\n"
        "    Path('{out}/closure-bypass-allowed').write_text('allowed', encoding='utf-8')\n"
        "except Exception as exc:\n"
        "    Path('{out}/closure-bypass-denied').write_text(type(exc).__name__, encoding='utf-8')\n"
        "def forge_outer_evidence():\n"
        "    Path(os.environ['ASTRID_NETWORK_EVIDENCE']).write_text(json.dumps({'admission': {}, 'events': [{'kind': 'evil', 'allowed': True}]}), encoding='utf-8')\n"
        "atexit.register(forge_outer_evidence)\n"
    )
    (executor / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "b13_provider.fetch",
                "name": "B13 Provider Fetch",
                "kind": "external",
                "version": "1.0",
                "command": {"argv": ["{python_exec}", "-c", command]},
                "outputs": [
                    {
                        "name": "result",
                        "type": "file",
                        "path_template": "{out}/result",
                        "artifact_type": "application/octet-stream",
                    }
                ],
                "isolation": {
                    "mode": "subprocess",
                    "network": True,
                    "secrets_required": ["B13_PROVIDER_KEY"],
                },
                "metadata": {
                    "adapter_family": "provider",
                    "resource_keys": ["provider"],
                    "network_policy": {
                        "allowed_protocols": ["dns", "tcp"],
                        "allowed_destinations": [f"127.0.0.1:{upstream.server_port}"],
                        "allow_redirects": False,
                        "broker": {"host_managed": True},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    try:
        generated = WorkspaceClient(daemon.endpoint, daemon.token)
        generated.handshake("b13-provider-journey", "0.1.0", ["projects:read", "worker:execute"])
        host = GenericPackHost(
            pack_roots=[pack],
            attempt_root=tmp_path / "attempt",
            credential_source={"B13_PROVIDER_KEY": "provider-secret"},
            client=RuntimeProtocolClient(daemon.endpoint, daemon.token),
            executor_id="b13-provider-host",
        )
        record = host.discover()[0]
        host.preflight()
        assert host.capabilities[record.id].ready
        registration = host.register()
        assert registration["registration"]["capability_digests"][record.id] == record.capability_digest

        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
            idempotency_key="b13-provider-task",
        )
        settled = host.run(once=True)
        assert len(settled) == 1 and settled[0].state == "succeeded"
        assert generated.get_task(task.task_id).state == "succeeded"
        digest = "sha256:" + hashlib.sha256(b"provider-output-v1").hexdigest()
        assert generated.get_object(digest).data == b"provider-output-v1"
        assert (tmp_path / "attempt" / "outputs" / "bypass-denied").read_text(encoding="utf-8")
        assert not (tmp_path / "attempt" / "outputs" / "primitive-bypass-allowed").exists()
        assert (tmp_path / "attempt" / "outputs" / "primitive-bypass-denied").read_text(encoding="utf-8") == "AttributeError"
        assert not (tmp_path / "attempt" / "outputs" / "closure-bypass-allowed").exists()
        assert (tmp_path / "attempt" / "outputs" / "closure-bypass-denied").read_text(encoding="utf-8") == "PermissionError"
        assert (tmp_path / "attempt" / "outputs" / "signing-key-absent").read_text(encoding="utf-8") == "True"

        evidence = json.loads((tmp_path / "attempt" / "network-evidence.json").read_text(encoding="utf-8"))
        assert evidence["broker_evidence"]["events"]
        assert any(event["kind"] == "broker_handshake" and event["allowed"] for event in evidence["events"])
        assert evidence["signature_algorithm"] == "hmac-sha256"
        assert not any(event["kind"] == "evil" for event in evidence["events"])
    finally:
        daemon.stop()
        upstream.shutdown()
        upstream.server_close()
