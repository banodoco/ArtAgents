from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from astrid.sdk import autobootstrap
from astrid.sdk.client import AstridClient
from astrid.sdk.workspace_client import WorkspaceClientError


def _runtime_checkout(tmp_path: Path) -> Path:
    checkout = tmp_path / "runtime"
    (checkout / "banodoco_local").mkdir(parents=True)
    (checkout / "packages" / "python").mkdir(parents=True)
    return checkout


def test_neutral_launcher_is_invoked_with_ephemeral_profile(monkeypatch, tmp_path):
    runtime = _runtime_checkout(tmp_path)
    source = tmp_path / "source"
    source.mkdir()
    manifest_path = tmp_path / "source-profile.json"
    manifest_path.write_text(json.dumps({"profile": "astrid", "runtime_checkout": str(runtime), "source_checkout": str(source)}), encoding="utf-8")
    monkeypatch.setenv("BANODOCO_LOCAL_SOURCE_MANIFEST", str(manifest_path))
    monkeypatch.setenv("BANODOCO_LOCAL_LAUNCHER", "/usr/bin/banodoco-local")

    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        manifest = Path(command[command.index("--source-manifest") + 1])
        seen["manifest"] = json.loads(manifest.read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, '{"status":"started","realm_id":"realm-1"}\n', "")

    monkeypatch.setattr(autobootstrap.subprocess, "run", fake_run)
    result = autobootstrap.ensure_runtime()

    assert result["status"] == "started"
    command = seen["command"]
    assert command[1:4] == ["up", "--profile", "astrid"]
    assert "serve" not in command
    assert seen["manifest"] == {"profile": "astrid", "runtime_checkout": str(runtime), "source_checkout": str(source)}
    assert command[-1] == "--json"


def test_configured_manifest_does_not_require_editable_source_inference(monkeypatch, tmp_path):
    runtime = _runtime_checkout(tmp_path)
    manifest = tmp_path / "source-profile.json"
    manifest.write_text(
        json.dumps(
            {
                "profile": "astrid",
                "runtime_checkout": str(runtime),
                "source_checkout": str(tmp_path / "pack-source"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BANODOCO_LOCAL_SOURCE_MANIFEST", str(manifest))
    monkeypatch.setenv("BANODOCO_LOCAL_LAUNCHER", "/usr/bin/banodoco-local")
    monkeypatch.setattr(
        autobootstrap.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, '{"status":"reconnected","realm_id":"realm-1"}', ""
        ),
    )

    result = autobootstrap.ensure_runtime()
    assert result["status"] == "reconnected"


def test_missing_source_manifest_fails_closed_without_inference(monkeypatch, tmp_path):
    monkeypatch.delenv("BANODOCO_LOCAL_LAUNCHER", raising=False)
    monkeypatch.delenv("BANODOCO_LOCAL_SOURCE_MANIFEST", raising=False)
    monkeypatch.delenv("BANODOCO_ASTRID_SOURCE_CHECKOUT", raising=False)
    monkeypatch.delenv("ASTRID_SOURCE_CHECKOUT", raising=False)
    with pytest.raises(autobootstrap.AutoBootstrapError, match="manifest is not configured"):
        autobootstrap.ensure_runtime()


def test_sdk_open_uses_explicit_context_without_bootstrap(monkeypatch):
    calls: list[str] = []

    def resolve(endpoint, credential):
        assert endpoint == "http://127.0.0.1:1" and credential == "token"
        return endpoint, credential

    class FakeWorkspace:
        def __init__(self, endpoint, token):
            assert endpoint == "http://127.0.0.1:1"
            assert token == "token"

        def health(self):
            calls.append("health")
            return {"status": "ok"}

        def handshake(self, *args):
            calls.append("handshake")
            return {"realm_id": "realm", "actor_id": "actor"}

    monkeypatch.setattr("astrid.sdk.workspace_client.resolve_runtime_connection", resolve)
    monkeypatch.setattr("astrid.sdk.workspace_client.WorkspaceClient", FakeWorkspace)
    monkeypatch.setattr("astrid.sdk.autobootstrap.ensure_runtime", lambda: pytest.fail("ordinary SDK bootstrapped runtime"))

    client = AstridClient.open(endpoint="http://127.0.0.1:1", credential="token", realm_id="realm", actor_id="actor", client_name="test", client_version="1", protocol_version="workspace.v1")
    assert calls == ["health", "handshake"]


def test_diagnostics_can_remain_side_effect_free(monkeypatch):
    monkeypatch.setattr(
        "astrid.sdk.workspace_client.resolve_runtime_connection",
        lambda _endpoint, _credential: (_ for _ in ()).throw(WorkspaceClientError(0, "unavailable", "missing")),
    )
    monkeypatch.setattr(
        "astrid.sdk.autobootstrap.ensure_runtime",
        lambda: pytest.fail("diagnostic path unexpectedly bootstrapped the runtime"),
    )
    with pytest.raises(Exception, match="banodoco-local up --profile astrid"):
        AstridClient.open(endpoint="http://127.0.0.1:1", credential="token", realm_id="realm", actor_id="actor", client_name="test", client_version="1", protocol_version="workspace.v1")
