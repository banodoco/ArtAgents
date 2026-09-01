"""B9.3/B9.4 coverage for external provider packs at the host boundary."""

from __future__ import annotations

import json
import hashlib
import textwrap
import os
import socket
import subprocess
import sys
import sysconfig
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost, HostError, RuntimeProtocolClient
from astrid.core.execution.network_broker import ObservableNetworkBroker

RUNTIME = Path("/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime-stage1-convergence")
if RUNTIME.is_dir():
    sys.path.insert(0, str(RUNTIME))
from banodoco_workspace_client import ApiError, WorkspaceClient
from runtime_protocol.daemon import RuntimeDaemon


def _run_provider(host: GenericPackHost, task: dict, *, lease_token: str = "fixture"):
    """Exercise the explicit provider grant request/consume seam."""
    grant = host.request_provider_route_grant(task)
    return host.run_task(task, lease_token=lease_token, provider_route_grant=grant)


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
                            "broker": {"host_managed": True},
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

        settled = _run_provider(
            host,
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
    assert "not a Git checkout" in host.capabilities[record.id].preflight["pack_source"]["reason"]


def test_unready_external_provider_is_not_claimed_by_runtime(tmp_path: Path) -> None:
    """Unavailable capabilities fail before admission and leave no ledger rows."""
    class ProviderHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            body = b"provider-ready"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    pack_root = tmp_path / "provider"
    executor_root = pack_root / "executors" / "fetch"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\n"
        "id: provider\nname: Provider\nversion: 1.0\n"
        "content:\n  executors: executors\n",
        encoding="utf-8",
    )
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1,
        "id": "provider.fetch",
        "name": "Provider Fetch",
        "kind": "external",
        "version": "1.0",
        "command": {"argv": ["{python_exec}", "-c", f"from urllib.request import urlopen; urlopen('http://127.0.0.1:{server.server_port}/ready', timeout=2).read()"]},
        "outputs": [],
        "isolation": {
            "mode": "subprocess",
            "network": True,
            "secrets_required": ["PROVIDER_KEY"],
        },
        "metadata": {
            "adapter_family": "provider",
            "required_env": ["PROVIDER_KEY"],
            "network_policy": {
                "allowed_protocols": ["dns", "tcp"],
                "allowed_destinations": ["127.0.0.1"],
                "broker": {"host_managed": True},
            },
        },
    }), encoding="utf-8")

    daemon = RuntimeDaemon(tmp_path / "realm", support_root=tmp_path / "support").start()
    try:
        generated = WorkspaceClient(daemon.endpoint, daemon.token)
        generated.handshake("provider-fixture", "0.1.0", ["projects:read", "worker:execute"])
        host = GenericPackHost(
            pack_roots=[pack_root],
            attempt_root=tmp_path / "attempt",
            credential_source={},
            client=RuntimeProtocolClient(daemon.endpoint, daemon.token),
            executor_id="provider-host",
        )
        record = host.discover()[0]
        registration = host.register()
        assert host.capabilities[record.id].ready is False
        assert registration["capabilities"][0]["ready"] is False
        project = generated.create_project("Provider fixture", slug="provider-fixture", idempotency_key="provider-project")
        with pytest.raises(ApiError, match="capability is not ready for admission"):
            generated.admit_task(
                capability_id=record.id,
                capability_digest=record.capability_digest,
                input_object_ids=[],
                project_id=project.project_id,
                idempotency_key="provider-unready-task",
            )

        # Admission rejection is pre-ledger: no task, run, or execution event
        # exists for the unavailable capability.
        assert generated.list_project_tasks(project.project_id)[0] == []
        assert generated.list_project_runs(project.project_id)[0] == []
        assert generated.list_events()[0] == []

        # Readiness changes only after the host receives the declared
        # credential; the same host registration then enables settlement.
        host.credential_source["PROVIDER_KEY"] = "fixture-provider-key"
        host.preflight()
        assert host.capabilities[record.id].ready is True
        host.register(deliberate=True)
        capability_page, capability_cursor = generated.list_capabilities()
        assert capability_cursor is None
        capability = next(item for item in capability_page if item.capability_id == record.id)
        assert capability.status == "ready"
        task = generated.admit_task(
            capability_id=record.id,
            capability_digest=record.capability_digest,
            input_object_ids=[],
            project_id=project.project_id,
            idempotency_key="provider-ready-task",
        )
        settled = host.run(once=True)
        assert len(settled) == 1 and settled[0].state == "succeeded"
        assert generated.get_task(task.task_id).state == "succeeded"
    finally:
        daemon.stop()
        server.shutdown()
        server.server_close()


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
        "metadata": {"adapter_family": "provider", "network_policy": {
            "allowed_protocols": ["dns", "tcp"], "allowed_destinations": [],
            "allow_redirects": False, "proxy": None,
            "broker": {"host_managed": True},
        }},
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
        _run_provider(host, {"task": {"id": "credential-task", "capability": record.id, "spec": {"inputs": {}}}})
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
                "broker": {"host_managed": True},
            }},
        }), encoding="utf-8")
        host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
        record = host.discover()[0]
        host.preflight()
        with pytest.raises(HostError, match="network policy denied redirect"):
            _run_provider(host, {"task": {"id": "network-task", "capability": record.id, "spec": {"inputs": {}}}})
        evidence = json.loads((tmp_path / "attempt" / "network-evidence.json").read_text(encoding="utf-8"))
        assert {event["kind"] for event in evidence["events"]} >= {"dns", "tcp", "redirect"}
        assert any(event["kind"] == "redirect" and not event["allowed"] for event in evidence["events"])
        assert evidence["limitations"]
    finally:
        server.shutdown()
        server.server_close()


def test_provider_network_policy_retires_unbrokered_quic_over_udp_fixture(tmp_path: Path) -> None:
    """UDP providers are unavailable until the host broker supports datagrams."""
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
        assert host.capabilities[record.id].ready is False
        assert "host-managed broker" in host.capabilities[record.id].preflight["network"]["reason"]
    finally:
        udp.close()


def test_provider_network_policy_retires_unbrokered_aioquic_handshake(tmp_path: Path) -> None:
    """A QUIC provider is unavailable until a host-owned datagram broker exists."""
    pytest.importorskip("aioquic")
    package_root = tmp_path / "quic_provider"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("\n", encoding="utf-8")
    (package_root / "run.py").write_text(textwrap.dedent("""
        import asyncio, datetime, ipaddress, sys
        from pathlib import Path
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from aioquic.asyncio import connect, serve
        from aioquic.quic.configuration import QuicConfiguration

        def certificate():
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
            now = datetime.datetime.now(datetime.timezone.utc)
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                    .public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now - datetime.timedelta(days=1))
                    .not_valid_after(now + datetime.timedelta(days=1))
                    .add_extension(x509.SubjectAlternativeName([
                        x509.DNSName('localhost'),
                        x509.IPAddress(ipaddress.ip_address('127.0.0.1')),
                    ]), critical=False).sign(key, hashes.SHA256()))
            cert_path = Path(sys.argv[2] + '.crt')
            key_path = Path(sys.argv[2] + '.key')
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption()))
            return cert_path, key_path

        async def echo(reader, writer):
            writer.write(await reader.read(1024))
            await writer.drain()
            writer.close()

        def stream_handler(reader, writer):
            asyncio.create_task(echo(reader, writer))

        async def main():
            cert_path, key_path = certificate()
            server_config = QuicConfiguration(is_client=False, alpn_protocols=['hq-29'])
            server_config.load_cert_chain(str(cert_path), str(key_path))
            server = await serve('127.0.0.1', 0, configuration=server_config,
                                 stream_handler=stream_handler)
            port = server._transport.get_extra_info('sockname')[1]
            client_config = QuicConfiguration(is_client=True, alpn_protocols=['hq-29'])
            client_config.verify_mode = 0
            message = b'astrid-real-quic-handshake'
            async with connect('127.0.0.1', port, configuration=client_config) as protocol:
                reader, writer = await protocol.create_stream()
                writer.write(message)
                await writer.drain()
                response = await asyncio.wait_for(reader.read(len(message)), 5)
                writer.close()
            server.close()
            if response != message:
                raise RuntimeError('QUIC stream echo did not complete')
            Path(sys.argv[1]).write_text('quic handshake complete', encoding='utf-8')

        asyncio.run(main())
    """), encoding="utf-8")
    pack_root = tmp_path / "quic_pack"
    executor_root = pack_root / "executors" / "handshake"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: quic_pack\nname: QUIC Pack\nversion: 1.0\n"
        "content:\n  executors: executors\n", encoding="utf-8"
    )
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "quic_pack.handshake", "name": "QUIC Handshake",
        "kind": "external", "version": "1.0",
            "command": {"argv": ["{python_exec}", "-m", "quic_provider.run", "{out}/proof.txt", str(tmp_path / "cert")], "env": {"PYTHONPATH": os.pathsep.join((sysconfig.get_paths()["purelib"], str(Path(__file__).resolve().parents[2])))}},
        "outputs": [{"name": "proof", "type": "file", "path_template": "{out}/proof.txt"}],
        "isolation": {"mode": "subprocess", "network": True},
        "metadata": {"adapter_family": "provider", "network_policy": {
            "allowed_protocols": ["dns", "udp"], "allowed_destinations": ["127.0.0.1"],
            "allow_redirects": False, "proxy": None,
        }},
    }), encoding="utf-8")
    host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].ready is False
    assert "host-managed broker" in host.capabilities[record.id].preflight["network"]["reason"]


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
    assert "host-managed broker" in host.capabilities[record.id].preflight["network"]["reason"]
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
        "metadata": {"adapter_family": "provider", "network_policy": {"allowed_protocols": ["dns", "tcp"], "allowed_destinations": [], "broker": {"host_managed": True}}},
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


def test_python_provider_cannot_spawn_unobserved_native_network_descendant(tmp_path: Path) -> None:
    """A curl/yt-dlp-shaped escape hatch fails closed inside the child."""
    pack_root = tmp_path / "native_escape_provider"
    executor_root = pack_root / "executors" / "escape"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: native_escape_provider\nname: Native Escape Provider\n"
        "version: 1.0\ncontent:\n  executors: executors\n", encoding="utf-8"
    )
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "native_escape_provider.fetch", "name": "Native Escape",
        "kind": "external", "version": "1.0",
        "command": {"argv": ["{python_exec}", "-c", "import subprocess; subprocess.run(['curl', 'https://example.invalid'], check=False)"]},
        "outputs": [], "isolation": {"mode": "subprocess", "network": True},
        "metadata": {"adapter_family": "provider", "network_policy": {
            "allowed_protocols": ["dns", "tcp"], "allowed_destinations": ["127.0.0.1:9"],
            "allow_redirects": False, "proxy": None,
            "broker": {"host_managed": True},
        }},
    }), encoding="utf-8")
    host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].ready
    with pytest.raises(HostError, match="exited"):
        _run_provider(host, {"task": {"id": "native-escape", "capability": record.id, "spec": {"inputs": {}}}})
    evidence = json.loads((tmp_path / "attempt" / "network-evidence.json").read_text(encoding="utf-8"))
    assert any(event["kind"] == "native_descendant" and not event["allowed"] for event in evidence["events"])


def test_live_observable_proxy_handshake_route_and_bypass_rejection(tmp_path: Path) -> None:
    """A provider must use the live broker and cannot bypass its route."""
    class ProviderHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib handler API
            body = b"brokered-response"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHandler)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    try:
        port = upstream.server_port
        pack_root = tmp_path / "broker_provider"
        executor_root = pack_root / "executors" / "fetch"
        executor_root.mkdir(parents=True)
        (pack_root / "pack.yaml").write_text(
            "schema_version: 1\nid: broker_provider\nname: Broker Provider\n"
            "version: 1.0\ncontent:\n  executors: executors\n", encoding="utf-8"
        )
        code = (
            "from pathlib import Path\n"
            "from urllib.request import urlopen, build_opener, ProxyHandler\n"
            f"body = urlopen('http://127.0.0.1:{port}/through-broker', timeout=2).read()\n"
            "Path('{out}/body').write_bytes(body)\n"
            "try:\n"
            "    build_opener(ProxyHandler({{}})).open('http://127.0.0.1:1/bypass', timeout=1)\n"
            "except Exception:\n"
            "    pass\n"
        ).format(out="{out}")
        (executor_root / "executor.yaml").write_text(json.dumps({
            "schema_version": 1, "id": "broker_provider.fetch", "name": "Broker Fetch",
            "kind": "external", "version": "1.0",
            "command": {"argv": ["{python_exec}", "-c", code]},
            "outputs": [{"name": "body", "type": "file", "path_template": "{out}/body"}],
            "isolation": {"mode": "subprocess", "network": True},
            "metadata": {"adapter_family": "provider", "network_policy": {
                "allowed_protocols": ["dns", "tcp"],
                "allowed_destinations": [f"127.0.0.1:{port}"],
                "allow_redirects": False,
                "broker": {"host_managed": True},
            }},
        }), encoding="utf-8")
        host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
        record = host.discover()[0]
        host.preflight()
        assert host.capabilities[record.id].ready
        _run_provider(host, {"task": {"id": "broker-task", "capability": record.id, "spec": {"inputs": {}}}})
        assert (tmp_path / "attempt" / "outputs" / "body").read_bytes() == b"brokered-response"
        evidence = json.loads((tmp_path / "attempt" / "network-evidence.json").read_text(encoding="utf-8"))
        assert any(event["kind"] == "broker_handshake" and event["allowed"] for event in evidence["events"])
        assert any(event["kind"] == "broker_route" and event["allowed"] for event in evidence["events"])
    finally:
        upstream.shutdown()
        upstream.server_close()


def test_host_rejects_child_forged_broker_evidence_without_upstream_route(tmp_path: Path) -> None:
    """A child cannot manufacture a successful broker route on its evidence path."""
    pack_root = tmp_path / "forging_provider"
    executor_root = pack_root / "executors" / "forge"
    executor_root.mkdir(parents=True)
    (pack_root / "pack.yaml").write_text(
        "schema_version: 1\nid: forging_provider\nname: Forging Provider\n"
        "version: 1.0\ncontent:\n  executors: executors\n", encoding="utf-8"
    )
    code = (
        "from pathlib import Path\n"
        "import json, os\n"
        "Path('<OUT>/proof').write_text('child completed', encoding='utf-8')\n"
        "Path(os.environ['ASTRID_NETWORK_BROKER_EVIDENCE']).write_text(json.dumps({\n"
        "  'schema_version': 1, 'admission': {}, 'events': [\n"
        "    {'kind': 'handshake', 'detail': 'forged|allowed=true'},\n"
        "    {'kind': 'route', 'detail': 'https://upstream.invalid:443/|allowed=true'}\n"
        "  ], 'signature_algorithm': 'hmac-sha256', 'signature': 'forged'\n"
        "}), encoding='utf-8')\n"
    ).replace("<OUT>", "{out}")
    (executor_root / "executor.yaml").write_text(json.dumps({
        "schema_version": 1, "id": "forging_provider.forge", "name": "Forging Provider",
        "kind": "external", "version": "1.0",
        "command": {"argv": ["{python_exec}", "-c", code]},
        "outputs": [{"name": "proof", "type": "file", "path_template": "{out}/proof"}],
        "isolation": {"mode": "subprocess", "network": True},
        "metadata": {"adapter_family": "provider", "network_policy": {
            "allowed_protocols": ["dns", "tcp"],
            "allowed_destinations": ["upstream.invalid:443"],
            "allow_redirects": False,
            "broker": {"host_managed": True},
        }},
    }), encoding="utf-8")
    host = GenericPackHost(pack_roots=[pack_root], attempt_root=tmp_path / "attempt")
    record = host.discover()[0]
    host.preflight()
    assert host.capabilities[record.id].ready
    with pytest.raises(HostError, match="incomplete broker route evidence"):
        _run_provider(host, {"task": {"id": "forge-task", "capability": record.id, "spec": {"inputs": {}}}})
