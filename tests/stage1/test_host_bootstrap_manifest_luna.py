from __future__ import annotations

import json
from pathlib import Path

from astrid.sdk import host_bootstrap


def test_host_bootstrap_binds_manifest_in_argv_and_reuses_exact_binding(
    tmp_path: Path, monkeypatch
) -> None:
    support = tmp_path / "support"
    credentials = support / "credentials"
    credentials.mkdir(parents=True)
    worker_file = credentials / "astrid-pack-host.token"
    worker_file.write_text("worker-token\n", encoding="utf-8")
    worker_file.chmod(0o600)
    source = Path(__file__).resolve().parents[2]
    captured: list[list[str]] = []

    class FakeRuntime:
        def __init__(self, *_args, **_kwargs):
            pass

        def health(self):
            return {
                "runtime_epoch": 7,
                "runtime_instance_id": "runtime-7",
                "schema_digest": "schema-7",
            }

    class FakeProcess:
        pid = 4242

        def poll(self):
            return None

    def fake_popen(argv, **_kwargs):
        captured.append(list(argv))
        ready = Path(argv[argv.index("--ready-file") + 1])
        manifest = Path(argv[argv.index("--boot-manifest-path") + 1])
        from astrid.core.integrations.reigh.boot_manifest import load_boot_manifest_hash

        expected = {
            "status": "ready",
            "pid": FakeProcess.pid,
            "process_birth_id": "birth-4242",
            "endpoint": "http://127.0.0.1:9999",
            "executor_id": "astrid-pack-host",
            "ready_file": str(ready),
            "credential_file": str(worker_file.resolve()),
            "support_root": str(support.resolve()),
            "source_checkout": str(source.resolve()),
            "source_checkout_digest": "source-digest",
            "runtime_instance_id": "runtime-7",
            "runtime_epoch": 7,
            "schema_digest": "schema-7",
            "boot_manifest_path": str(manifest),
            "boot_manifest_hash": load_boot_manifest_hash(manifest, support_root=support),
            "ready_capabilities": ["shots.example"],
        }
        ready.parent.mkdir(parents=True, exist_ok=True)
        ready.write_text(json.dumps(expected), encoding="utf-8")
        return FakeProcess()

    monkeypatch.setattr(host_bootstrap, "RuntimeProtocolClient", FakeRuntime, raising=False)
    monkeypatch.setattr(host_bootstrap.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(host_bootstrap, "_host_birth_identity", lambda _pid: "birth-4242")
    monkeypatch.setattr(host_bootstrap, "_host_identity_matches", lambda _state: True)
    monkeypatch.setattr(host_bootstrap, "_host_pid_alive", lambda _pid: True)
    monkeypatch.setattr(host_bootstrap, "_our_host", lambda _pid: True)
    monkeypatch.setattr(host_bootstrap, "source_checkout_digest", lambda _path: "source-digest", raising=False)

    # The bootstrap module imports these two symbols lazily in ensure_pack_host.
    monkeypatch.setattr(
        "astrid.core.execution.generic_host.RuntimeProtocolClient",
        FakeRuntime,
    )
    monkeypatch.setattr(
        "astrid.core.execution.generic_host.source_checkout_digest",
        lambda _path: "source-digest",
    )

    value = {
        "worker_credential_file": str(worker_file),
        "worker_actor": host_bootstrap.PACK_HOST_ACTOR,
        "worker_scopes": host_bootstrap.PACK_HOST_SCOPES,
        "source_checkout": str(source),
        "endpoint": "http://127.0.0.1:9999",
        "runtime_epoch": 7,
    }
    first = host_bootstrap.ensure_pack_host(value, reconfigure_action="reconfigure")
    manifest = support / "astrid-host" / "boot-manifest.json"
    assert manifest.is_file()
    assert "--boot-manifest-path" in captured[0]
    assert captured[0][captured[0].index("--boot-manifest-path") + 1] == str(manifest)
    assert "--boot-manifest-hash" in captured[0]
    assert captured[0][captured[0].index("--boot-manifest-hash") + 1] == first["host_boot_manifest_hash"]
    assert first["host_boot_manifest_path"] == str(manifest)
    assert first["host_boot_manifest_hash"]

    second = host_bootstrap.ensure_pack_host(value, reconfigure_action="reconfigure")
    assert second == first
    assert len(captured) == 1
    assert not (tmp_path / ".astrid" / "astrid.sqlite3").exists()
