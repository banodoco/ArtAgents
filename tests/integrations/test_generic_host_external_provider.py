"""B9.3/B9.4 coverage for external provider packs at the host boundary."""

from __future__ import annotations

import json
import hashlib
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost, HostError, RuntimeProtocolClient

RUNTIME = Path("/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime-stage1-convergence")
if RUNTIME.is_dir():
    sys.path.insert(0, str(RUNTIME / "packages/python"))
    sys.path.insert(0, str(RUNTIME))
from banodoco_workspace_client import WorkspaceClient
from runtime_protocol.daemon import RuntimeDaemon


def test_external_pack_command_imports_from_its_admitted_pack_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command-pack provider must execute through the generic host.

    This is deliberately a local provider fixture: it proves the same
    subprocess/import boundary used by Hivemind without contacting a provider
    or carrying credentials.  The package lives beside its pack root, so the
    test fails if the host forgets to propagate the external pack import root.
    """
    pack_root = tmp_path / "fixture_provider"
    executor_root = pack_root / "executors" / "echo"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: fixture_provider\nname: Fixture Provider\n"
        "version: 1.0\ncapabilities: [echo]\ncontent:\n  executors: executors\n",
        encoding="utf-8",
    )
    (pack_root / "__init__.py").write_text("\n", encoding="utf-8")
    (pack_root / "emit.py").write_text(
        "from pathlib import Path\n"
        "import os\n"
        "import sys\n"
        "from urllib.request import urlopen\n"
        "url = os.environ.get('FIXTURE_PROVIDER_URL')\n"
        "body = urlopen(url, timeout=2).read().decode('utf-8') if url else 'provider-fixture-response'\n"
        "Path(sys.argv[1]).write_text(body, encoding='utf-8')\n",
        encoding="utf-8",
    )
    (executor_root / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "fixture_provider.echo",
                "name": "Fixture Provider Echo",
                "kind": "external",
                "version": "1.0",
                "command": {
                    "argv": [
                        "{python_exec}",
                        "-m",
                        "fixture_provider.emit",
                        "{out}/response.txt",
                    ]
                },
                "outputs": [
                    {
                        "name": "response",
                        "type": "file",
                        "path_template": "{out}/response.txt",
                    }
                ],
                "isolation": {
                    "mode": "subprocess",
                    "network": True,
                    "env_passthrough": ["FIXTURE_PROVIDER_URL"],
                },
                "metadata": {
                    "adapter_family": "provider",
                    "resource_keys": ["provider"],
                        "network_policy": {
                            "allowed_protocols": ["dns", "tcp"],
                            "allowed_destinations": ["127.0.0.1"],
                        },
                },
            }
        ),
        encoding="utf-8",
    )

    class ProviderHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            body = b"provider-http-response"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "FIXTURE_PROVIDER_URL",
        f"http://127.0.0.1:{server.server_port}/response",
    )
    try:
        host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
        record = host.discover()[0]
        assert record.definition.metadata["source_pack"] == "fixture_provider"
        assert Path(record.definition.metadata["pack_root"]) == pack_root
        host.preflight()
        assert record.adapter.family == "provider"
        assert host.capabilities[record.id].ready

        settled = host.run_task(
            {"task": {"id": "provider-task", "capability": record.id, "spec": {"inputs": {}}}},
            lease_token="fixture-lease",
        )
    finally:
        server.shutdown()
        server.server_close()
    assert settled["output_objects"][0]["name"] == "response"
    assert (tmp_path / "attempt" / "outputs" / "response.txt").read_text(encoding="utf-8") == "provider-http-response"


def test_hivemind_without_clean_pinned_source_is_optional_unavailable(tmp_path: Path) -> None:
    """B9.3 must expose an unavailable Hivemind row, never silently advertise it."""
    pack_root = tmp_path / "hivemind"
    executor_root = pack_root / "executors" / "search"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: hivemind\nname: Hivemind\nversion: 2.0\n"
        "content:\n  executors: executors\n",
        encoding="utf-8",
    )
    (executor_root / "executor.yaml").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "hivemind.search",
                "name": "Hivemind Search",
                "kind": "external",
                "version": "2.0",
                "command": {"argv": ["{python_exec}", "-c", "pass"]},
                "outputs": [],
                "isolation": {
                    "mode": "subprocess",
                    "network": True,
                    "secrets_required": ["HIVEMIND_ANON_KEY"],
                },
                "metadata": {"adapter_family": "provider", "required_env": ["HIVEMIND_API_URL"]},
            }
        ),
        encoding="utf-8",
    )
    host = GenericPackHost(pack_roots=[pack_root])
    record = host.discover()[0]
    assert record.definition.metadata["source_pack"] == "hivemind"
    host.preflight()
    assert host.capabilities[record.id].ready is False
    assert host.capabilities[record.id].preflight["pack_source"]["ok"] is False
    assert "not pinned" in host.capabilities[record.id].preflight["pack_source"]["reason"]


@pytest.mark.parametrize("provider_env", ["FAL_KEY", "GIPHY_API_KEY", "OPENAI_API_KEY"])
def test_provider_credentials_are_manifest_scoped_and_redacted(tmp_path: Path, provider_env: str) -> None:
    """FAL/GIPHY/OpenAI-shaped provider children see only declared secrets."""
    pack_root = tmp_path / "credential_provider"
    executor_root = pack_root / "executors" / "echo"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: credential_provider\nname: Credential Provider\n"
        "version: 1.0\ncontent:\n  executors: executors\n", encoding="utf-8"
    )
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "credential_provider.echo", "name": "Credential Echo",
        "kind": "external", "version": "1.0",
        "command": {"argv": [
            "{python_exec}", "-c",
            "import os,sys; print(os.getenv('%s'), os.getenv('FAL_KEY'), os.getenv('OPENAI_API_KEY'), file=sys.stderr); raise SystemExit(2)" % provider_env,
        ]},
        "outputs": [],
        "isolation": {"mode": "subprocess", "network": True, "secrets_required": [provider_env]},
        "metadata": {"adapter_family": "provider"},
    }), encoding="utf-8")
    credential_source = {"FAL_KEY": "fal-ambient-secret", "GIPHY_API_KEY": "giphy-ambient-secret", "OPENAI_API_KEY": "openai-ambient-secret"}
    credential_source[provider_env] = "declared-fixture-secret"
    host = GenericPackHost(
        pack_roots=[pack_root], attempt_root=tmp_path / "attempt",
        credential_source=credential_source,
    )
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].ready
    with pytest.raises(HostError) as caught:
        host.run_task({"task": {"id": "credential-task", "capability": record.id, "spec": {"inputs": {}}}}, lease_token="fixture")
    assert "declared-fixture-secret" not in str(caught.value)
    assert "ambient-secret" not in str(caught.value)
    assert "<redacted>" in str(caught.value)


def test_provider_network_policy_records_hermetic_dns_tcp_and_denies_redirect(
    tmp_path: Path,
) -> None:
    """A local provider fixture proves bounded network enforcement/observability."""
    class ProviderHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            self.send_response(302 if self.path == "/" else 200)
            if self.path == "/":
                self.send_header("Location", "http://127.0.0.1:%d/redirected" % server.server_port)
            self.end_headers()
            self.wfile.write(b"fixture")

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        pack_root = tmp_path / "network_provider"
        executor_root = pack_root / "executors" / "fetch"
        executor_root.mkdir(parents=True)
        (pack_root / "pack.yaml").write_text(
            "schema_version: 1\nid: network_provider\nname: Network Provider\n"
            "version: 1.0\ncontent:\n  executors: executors\n", encoding="utf-8"
        )
        url = "http://127.0.0.1:%d/" % server.server_port
        (executor_root / "executor.yaml").write_text(json.dumps({
            "schema_version": 1, "id": "network_provider.fetch", "name": "Network Fetch",
            "kind": "external", "version": "1.0",
            "command": {"argv": [
                "{python_exec}", "-c",
                "from pathlib import Path; from urllib.request import urlopen; Path('{out}/body').write_bytes(urlopen('%s').read())" % url,
            ]},
            "outputs": [{"name": "body", "type": "file", "path_template": "{out}/body"}],
            "isolation": {"mode": "subprocess", "network": True},
            "metadata": {"adapter_family": "provider", "network_policy": {
                "allowed_protocols": ["dns", "tcp"],
                "allowed_destinations": ["127.0.0.1:%d" % server.server_port],
                "allow_redirects": False,
            }},
        }), encoding="utf-8")
        host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
        record = host.discover()[0]
        host.preflight()
        with pytest.raises(HostError, match="network policy denied redirect"):
            host.run_task({"task": {"id": "network-task", "capability": record.id, "spec": {"inputs": {}}}}, lease_token="fixture")
        evidence = json.loads((tmp_path / "attempt" / "network-evidence.json").read_text(encoding="utf-8"))
        assert {event["kind"] for event in evidence["events"]} >= {"dns", "tcp", "redirect"}
        assert any(event["kind"] == "redirect" and not event["allowed"] for event in evidence["events"])
        assert evidence["limitations"]
    finally:
        server.shutdown()
        server.server_close()


def test_provider_network_policy_records_and_allows_quic_over_udp_fixture(tmp_path: Path) -> None:
    """UDP/QUIC-shaped provider traffic is explicitly admitted and evidenced."""
    received: list[bytes] = []
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.1", 0))
    udp.settimeout(2)

    def receive() -> None:
        try:
            data, _ = udp.recvfrom(1024)
            received.append(data)
        except socket.timeout:
            pass

    thread = threading.Thread(target=receive, daemon=True)
    thread.start()
    try:
        pack_root = tmp_path / "quic_provider"
        executor_root = pack_root / "executors" / "quic"
        executor_root.mkdir(parents=True)
        (pack_root / "pack.yaml").write_text(
            "schema_version: 1\nid: quic_provider\nname: QUIC Provider\nversion: 1.0\ncontent:\n  executors: executors\n",
            encoding="utf-8",
        )
        port = udp.getsockname()[1]
        (executor_root / "executor.yaml").write_text(json.dumps({
            "schema_version": 1, "id": "quic_provider.fetch", "name": "QUIC UDP Fixture",
            "kind": "external", "version": "1.0",
            "command": {"argv": ["{python_exec}", "-c", "import socket; s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.sendto(b'quic-fixture', ('127.0.0.1', %d))" % port]},
            "outputs": [], "isolation": {"mode": "subprocess", "network": True},
            "metadata": {"adapter_family": "provider", "network_policy": {
                "allowed_protocols": ["dns", "udp"], "allowed_destinations": ["127.0.0.1:%d" % port],
            }},
        }), encoding="utf-8")
        host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
        record = host.discover()[0]
        host.preflight()
        assert host.capabilities[record.id].ready
        host.run_task({"task": {"id": "quic-task", "capability": record.id, "spec": {"inputs": {}}}}, lease_token="fixture")
        thread.join(timeout=2)
        evidence = json.loads((tmp_path / "attempt" / "network-evidence.json").read_text(encoding="utf-8"))
        assert b"quic-fixture" in received
        assert any(event["kind"] == "udp" and event["allowed"] for event in evidence["events"])
        assert evidence["signature_algorithm"] == "hmac-sha256"
        assert evidence["admission"]["capability_digest"] == record.capability_digest
    finally:
        udp.close()


def test_native_network_command_is_unready_without_enforceable_observable_gateway(tmp_path: Path) -> None:
    pack_root = tmp_path / "native_provider"
    executor_root = pack_root / "executors" / "native"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: native_provider\nname: Native Provider\nversion: 1.0\ncontent:\n  executors: executors\n",
        encoding="utf-8",
    )
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "native_provider.fetch", "name": "Native Fetch",
        "kind": "external", "version": "1.0",
        "command": {"argv": ["curl", "https://example.invalid/"]}, "outputs": [],
        "isolation": {"mode": "subprocess", "network": True},
        "metadata": {"adapter_family": "provider", "native": True,
                      "network_policy": {"allowed_protocols": ["tcp"], "allowed_destinations": ["example.invalid:443"]}},
    }), encoding="utf-8")
    host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].ready is False
    assert "enforceable observable proxy or broker" in host.capabilities[record.id].preflight["network"]["reason"]
    with pytest.raises(HostError, match="capability .* unavailable"):
        host.run_task({"task": {"id": "native-task", "capability": record.id, "spec": {"inputs": {}}}}, lease_token="fixture")


def test_clean_pinned_hivemind_pack_publishes_through_real_runtime(tmp_path: Path) -> None:
    """A committed local Hivemind-style pack is admitted by digest and settles via CAS."""
    checkout = tmp_path / "hivemind-checkout"
    executor_root = checkout / "packs" / "hivemind" / "executors" / "search"
    executor_root.mkdir(parents=True)
    pack_root = checkout / "packs" / "hivemind"
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: hivemind\nname: Hivemind\nversion: 2.0\ncontent:\n  executors: executors\n",
        encoding="utf-8",
    )
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "hivemind.search", "name": "Hivemind Search",
        "kind": "external", "version": "2.0",
        "command": {"argv": ["{python_exec}", "-c", "import json; from pathlib import Path; Path('{out}/result.json').write_text(json.dumps({'hits': []}), encoding='utf-8')"]},
        "outputs": [{"name": "result", "type": "file", "path_template": "{out}/result.json", "artifact_type": "application/json"}],
        "isolation": {"mode": "subprocess", "network": True, "secrets_required": ["HIVEMIND_ANON_KEY"]},
        "metadata": {"adapter_family": "provider", "network_policy": {"allowed_protocols": ["dns", "tcp"], "allowed_destinations": []}},
    }), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "config", "user.email", "fixture@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(checkout), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(checkout), "add", "packs"], check=True)
    subprocess.run(["git", "-C", str(checkout), "commit", "-qm", "pin hivemind fixture"], check=True)
    host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt", credential_source={"HIVEMIND_ANON_KEY": "fixture-key"})
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].preflight["pack_source"]["ok"]
    revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    assert host.capabilities[record.id].preflight["pack_source"]["revision"] == revision

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    try:
        generated = WorkspaceClient(daemon.endpoint, daemon.token)
        generated.handshake("hivemind-fixture", "0.1.0", ["projects:read", "worker:execute"])
        runtime_host = GenericPackHost(
            pack_roots=[pack_root], attempt_root=tmp_path / "attempt-runtime",
            credential_source={"HIVEMIND_ANON_KEY": "fixture-key"},
            client=RuntimeProtocolClient(daemon.endpoint, daemon.token), executor_id="hivemind-host",
        )
        registration = runtime_host.register()
        assert registration["registration"]["capability_digests"][record.id] == record.capability_digest
        task = generated.admit_task(capability_id=record.id, capability_digest=record.capability_digest, input_object_ids=[], idempotency_key="hivemind-fixture-task")
        settled = runtime_host.run(once=True)
        assert len(settled) == 1 and settled[0].state == "succeeded"
        payload = b'{"hits": []}'
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        assert generated.get_object(digest).data == payload
        assert generated.get_task(task.task_id).state == "succeeded"
    finally:
        daemon.stop()
