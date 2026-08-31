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
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BANODOCO_RUNTIME_CHECKOUT", str(runtime))
    monkeypatch.delenv("BANODOCO_LOCAL_SOURCE_MANIFEST", raising=False)
    monkeypatch.delenv("BANODOCO_LOCAL_HOME", raising=False)

    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["env"] = kwargs["env"]
        manifest = Path(command[command.index("--source-manifest") + 1])
        seen["manifest"] = json.loads(manifest.read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, '{"status":"started","realm_id":"realm-1"}\n', "")

    monkeypatch.setattr(autobootstrap.subprocess, "run", fake_run)
    result = autobootstrap.ensure_runtime()

    assert result["status"] == "started"
    command = seen["command"]
    assert command[1:5] == ["-m", "banodoco_local", "up", "--profile"]
    assert "serve" not in command
    assert seen["manifest"] == {
        "profile": "astrid",
        "runtime_checkout": str(runtime.resolve()),
        "source_checkout": str(Path(__file__).parents[2].resolve()),
        "protocol_version": "workspace.v1",
        "schema_version": "workspace-schema-v1",
    }
    assert seen["env"]["BANODOCO_LOCAL_HOME"] == str(home.resolve())
    assert not Path(command[command.index("--source-manifest") + 1]).exists()


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
    monkeypatch.delenv("BANODOCO_RUNTIME_CHECKOUT", raising=False)
    monkeypatch.setattr(
        autobootstrap.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, '{"status":"reconnected","realm_id":"realm-1"}', ""
        ),
    )

    result = autobootstrap.ensure_runtime()
    assert result["status"] == "reconnected"


def test_persisted_source_profile_relaunches_without_environment(monkeypatch, tmp_path):
    runtime = _runtime_checkout(tmp_path)
    source = tmp_path / "astrid-source"
    source.mkdir()
    home = tmp_path / "home"
    catalog = home / "Library" / "Application Support" / "Banodoco" / "runtime" / "catalog.json"
    catalog.parent.mkdir(parents=True)
    catalog.write_text(json.dumps({"source_profiles": {"astrid": {
        "profile": "astrid", "runtime_checkout": str(runtime), "source_checkout": str(source),
    }}}), encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("BANODOCO_RUNTIME_CHECKOUT", raising=False)
    monkeypatch.delenv("BANODOCO_LOCAL_RUNTIME_CHECKOUT", raising=False)
    monkeypatch.delenv("BANODOCO_LOCAL_SOURCE_MANIFEST", raising=False)
    monkeypatch.delenv("BANODOCO_ASTRID_SOURCE_CHECKOUT", raising=False)
    monkeypatch.delenv("ASTRID_SOURCE_CHECKOUT", raising=False)
    seen = {}

    def fake_run(command, **kwargs):
        manifest = Path(command[command.index("--source-manifest") + 1])
        seen["manifest"] = json.loads(manifest.read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(command, 0, '{"status":"reconnected","realm_id":"realm-1"}', "")

    monkeypatch.setattr(autobootstrap.subprocess, "run", fake_run)
    assert autobootstrap.ensure_runtime()["status"] == "reconnected"
    assert seen["manifest"]["runtime_checkout"] == str(runtime.resolve())
    assert seen["manifest"]["source_checkout"] == str(source.resolve())


def test_sdk_open_bootstraps_once_then_retries(monkeypatch):
    attempts = iter(
        [
            WorkspaceClientError(0, "unavailable", "missing"),
            ("http://127.0.0.1:1", "token"),
        ]
    )
    calls: list[str] = []

    def resolve():
        value = next(attempts)
        if isinstance(value, Exception):
            raise value
        return value

    class FakeWorkspace:
        def __init__(self, endpoint, token):
            assert endpoint == "http://127.0.0.1:1"
            assert token == "token"

        def health(self):
            calls.append("health")
            return {"status": "ok"}

        def handshake(self, *args):
            calls.append("handshake")
            return {"protocol": "workspace.v1"}

    monkeypatch.setattr("astrid.sdk.workspace_client.resolve_runtime_connection", resolve)
    monkeypatch.setattr("astrid.sdk.workspace_client.WorkspaceClient", FakeWorkspace)
    monkeypatch.setattr("astrid.sdk.autobootstrap.ensure_runtime", lambda: calls.append("bootstrap"))

    client = AstridClient.open()
    client.close()
    assert calls == ["bootstrap", "health", "handshake"]


def test_diagnostics_can_remain_side_effect_free(monkeypatch):
    monkeypatch.setattr(
        "astrid.sdk.workspace_client.resolve_runtime_connection",
        lambda: (_ for _ in ()).throw(WorkspaceClientError(0, "unavailable", "missing")),
    )
    monkeypatch.setattr(
        "astrid.sdk.autobootstrap.ensure_runtime",
        lambda: pytest.fail("diagnostic path unexpectedly bootstrapped the runtime"),
    )
    with pytest.raises(Exception, match="banodoco-local up --profile astrid"):
        AstridClient.open(auto_bootstrap=False)
