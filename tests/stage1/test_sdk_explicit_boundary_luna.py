from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest

from astrid.sdk import autobootstrap
from astrid.sdk.client import AstridClient
from astrid.sdk.remote import RemoteAstridClient, RemoteTimelines
from astrid.sdk.workspace_client import WorkspaceClientError, resolve_runtime_connection


def test_open_requires_explicit_context_and_never_bootstraps(monkeypatch):
    monkeypatch.setattr(
        "astrid.sdk.autobootstrap.ensure_runtime",
        lambda: pytest.fail("ordinary SDK open invoked the launcher"),
    )
    with pytest.raises(Exception, match="banodoco-local up --profile astrid"):
        AstridClient.open()


def test_connection_resolution_does_not_guess_a_checkout_or_catalog(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", "http://wrong")
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(tmp_path / "wrong-token"))
    with pytest.raises(WorkspaceClientError):
        resolve_runtime_connection("", "")
    assert resolve_runtime_connection("https://runtime.example/", "Bearer token") == (
        "https://runtime.example",
        "token",
    )


def test_timeline_creation_has_only_atomic_generated_route():
    class Client:
        def create_timeline_document(self, *args, **kwargs):
            assert kwargs["config"] == {"tracks": []}
            assert kwargs["registry"] == {"assets": {}}
            return {"timeline_id": args[1], "receipt": {"receipt_id": "r"}}

    remote = RemoteTimelines(Client())
    result = remote.create(
        project="project-1",
        config={"tracks": []},
        registry={"assets": {}},
        slug="main",
        idempotency_key="timeline-1",
    )
    assert result.ok
    assert not hasattr(remote, "create_timeline")


def test_remote_has_no_retired_alias_surface():
    names = {
        "selected_project_ref",
        "read_events",
        "subscribe_events",
        "render",
        "close",
    }
    assert names.isdisjoint(vars(RemoteAstridClient))


def test_top_level_sdk_has_no_event_aliases():
    import astrid

    assert not hasattr(astrid, "read_events")
    assert not hasattr(astrid, "subscribe_events")


def test_launcher_uses_installed_command_and_explicit_manifest(monkeypatch, tmp_path: Path):
    manifest = tmp_path / "source-manifest.json"
    manifest.write_text(json.dumps({"profile": "astrid"}), encoding="utf-8")
    monkeypatch.setenv("BANODOCO_LOCAL_SOURCE_MANIFEST", str(manifest))
    monkeypatch.setenv("BANODOCO_LOCAL_LAUNCHER", "/usr/local/bin/banodoco-local")
    seen: dict[str, object] = {}

    def run(command, **kwargs):
        seen["command"] = command
        assert "env" not in kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"status": "started", "realm_id": "realm", "endpoint": "http://127.0.0.1:1", "actor_id": "actor"}),
            "",
        )

    monkeypatch.setattr(autobootstrap.subprocess, "run", run)
    result = autobootstrap.ensure_runtime()
    assert result["status"] == "started"
    assert seen["command"][:5] == ["/usr/local/bin/banodoco-local", "up", "--profile", "astrid", "--source-manifest"]


def test_public_open_signature_has_no_auto_bootstrap_keyword():
    assert "auto_bootstrap" not in inspect.signature(AstridClient.open).parameters


def test_sdk_boundary_has_no_checkout_or_dynamic_import_injection():
    root = Path(__file__).resolve().parents[2] / "astrid" / "sdk"
    workspace_source = (root / "workspace_client.py").read_text(encoding="utf-8")
    bootstrap_source = (root / "autobootstrap.py").read_text(encoding="utf-8")
    assert "sys.path" not in workspace_source
    assert "importlib" not in workspace_source
    assert "BANODOCO_RUNTIME_CHECKOUT" not in workspace_source
    assert "source_checkout" not in bootstrap_source
    assert "PYTHONPATH" not in bootstrap_source
