"""B9.3/B9.4 coverage for external provider packs at the host boundary."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost


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
                    "env_passthrough": ["HIVEMIND_API_URL", "HIVEMIND_ANON_KEY"],
                },
                "metadata": {"adapter_family": "provider"},
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
