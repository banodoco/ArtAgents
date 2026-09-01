"""Fail-closed checks for the explicit Astrid runtime handshake boundary."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from astrid.sdk import autobootstrap
from astrid.sdk.client import AstridClient
from astrid.sdk.exceptions import ServiceUnavailableError
from astrid.sdk.workspace_client import (
    PROTOCOL,
    SCHEMA_DIGEST,
    WorkspaceClientError,
    resolve_runtime_connection,
)


class _Workspace:
    def __init__(self, health: object, handshake: object) -> None:
        self._health = health
        self._handshake = handshake

    def health(self) -> object:
        return self._health

    def handshake(self, *_args: object) -> object:
        return self._handshake


def _health(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "status": "ok",
        "protocol": PROTOCOL,
        "schema_digest": SCHEMA_DIGEST,
        "runtime_epoch": 1,
    }
    value.update(overrides)
    return value


def _handshake(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "protocol": PROTOCOL,
        "schema_digest": SCHEMA_DIGEST,
        "session_id": "session-1",
        "actor_id": "actor-1",
        "realm_id": "realm-1",
        "scopes": [
            "projects:read",
            "projects:write",
            "objects:read",
            "objects:write",
            "tasks:read",
            "tasks:write",
        ],
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    "response",
    [
        _health(protocol="workspace.v999"),
        _health(schema_digest="sha256:" + "0" * 64),
        _health(status="degraded"),
        _health(extra="tampered"),
    ],
)
def test_open_rejects_tampered_health(monkeypatch: pytest.MonkeyPatch, response: object) -> None:
    monkeypatch.setattr(
        "astrid.sdk.workspace_client.WorkspaceClient",
        lambda *_args: _Workspace(response, _handshake()),
    )
    with pytest.raises(ServiceUnavailableError) as error:
        AstridClient.open(
            endpoint="http://127.0.0.1:1",
            credential="token",
            realm_id="realm-1",
            actor_id="actor-1",
            client_name="test",
            client_version="1",
            protocol_version=PROTOCOL,
        )
    assert error.value.details["reason"] in {"protocol_error", "identity_mismatch"}
    assert error.value.details["next_action"] == "banodoco-local up --profile astrid"


@pytest.mark.parametrize(
    "response",
    [
        _handshake(protocol="workspace.v999"),
        _handshake(schema_digest="sha256:" + "0" * 64),
        _handshake(session_id=""),
        _handshake(actor_id="attacker"),
        _handshake(realm_id="wrong-realm"),
        _handshake(scopes=["projects:read"]),
        _handshake(scopes=[
            "projects:read", "projects:write", "objects:read", "objects:write",
            "tasks:read", "tasks:write", "admin",
        ]),
    ],
)
def test_open_rejects_tampered_handshake(monkeypatch: pytest.MonkeyPatch, response: object) -> None:
    monkeypatch.setattr(
        "astrid.sdk.workspace_client.WorkspaceClient",
        lambda *_args: _Workspace(_health(), response),
    )
    with pytest.raises(ServiceUnavailableError) as error:
        AstridClient.open(
            endpoint="http://127.0.0.1:1",
            credential="token",
            realm_id="realm-1",
            actor_id="actor-1",
            client_name="test",
            client_version="1",
            protocol_version=PROTOCOL,
        )
    assert error.value.details["reason"] in {"protocol_error", "identity_mismatch"}


def test_connection_rejects_non_loopback_and_symlinked_credentials(
    tmp_path: Path,
) -> None:
    credential = tmp_path / "credential.json"
    credential.write_text('{"token":"secret"}', encoding="utf-8")
    symlink = tmp_path / "credential-link.json"
    symlink.symlink_to(credential)
    with pytest.raises(WorkspaceClientError, match="loopback"):
        resolve_runtime_connection("https://runtime.example", credential)
    with pytest.raises(WorkspaceClientError, match="symlink"):
        resolve_runtime_connection("http://127.0.0.1:1", symlink)


def test_launcher_rejects_symlinked_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_manifest = tmp_path / "real-manifest.json"
    real_manifest.write_text('{"profile":"astrid"}', encoding="utf-8")
    link = tmp_path / "manifest-link.json"
    link.symlink_to(real_manifest)
    monkeypatch.setenv("BANODOCO_LOCAL_SOURCE_MANIFEST", str(link))
    with pytest.raises(autobootstrap.AutoBootstrapError, match="source manifest is unsafe"):
        autobootstrap.ensure_runtime()


def test_launcher_rejects_non_loopback_advertisement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"profile":"astrid"}', encoding="utf-8")
    monkeypatch.setenv("BANODOCO_LOCAL_SOURCE_MANIFEST", str(manifest))
    monkeypatch.setenv("BANODOCO_LOCAL_LAUNCHER", "/bin/true")
    monkeypatch.setattr(
        autobootstrap.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            '{"status":"started","realm_id":"realm","actor_id":"actor","endpoint":"https://runtime.example"}',
            "",
        ),
    )
    with pytest.raises(autobootstrap.AutoBootstrapError, match="unsafe endpoint"):
        autobootstrap.ensure_runtime()


def test_launcher_credential_environment_is_read_as_a_safe_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    credential = tmp_path / "owner.token"
    credential.write_text("secret-token\n", encoding="utf-8")
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(credential))
    monkeypatch.setattr(
        autobootstrap,
        "ensure_runtime",
        lambda: {
            "status": "reconnected",
            "realm_id": "realm-1",
            "endpoint": "http://127.0.0.1:1",
            "actor_id": "actor-1",
            "credential_file": "",
        },
    )
    def fake_workspace(endpoint: str, token: str) -> _Workspace:
        assert endpoint == "http://127.0.0.1:1"
        assert token == "secret-token"
        return _Workspace(_health(), _handshake())

    monkeypatch.setattr("astrid.sdk.workspace_client.WorkspaceClient", fake_workspace)
    AstridClient.open_from_launcher(
        client_name="test", client_version="1", protocol_version=PROTOCOL
    )
