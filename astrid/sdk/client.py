"""Public Astrid SDK client backed exclusively by the workspace runtime.

The client is deliberately only a transport composition root. It does not
open a database, acquire a store lock, load repositories, or construct a
local application. Runtime discovery and credentials are resolved by
``workspace_client`` and product families are exposed by ``remote``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

from banodoco_workspace_client.contract_metadata import PROTOCOL, SCHEMA_DIGEST

__all__ = ["AstridClient"]


_REQUIRED_SCOPES = frozenset(
    {
        "projects:read",
        "projects:write",
        "objects:read",
        "objects:write",
        "tasks:read",
        "tasks:write",
    }
)
_HEALTH_KEYS = frozenset({"status", "protocol", "schema_digest", "runtime_epoch"})
_HANDSHAKE_KEYS = frozenset(
    {"protocol", "schema_digest", "session_id", "actor_id", "realm_id", "scopes"}
)


def _protocol_error(field: str, message: str) -> Any:
    from astrid.sdk.workspace_client import WorkspaceClientError

    return WorkspaceClientError(
        0,
        "protocol_error",
        message,
        {
            "field": field,
            "next_action": "reconfigure the Astrid runtime with `banodoco-local up --profile astrid`",
        },
    )


def _identity_error(field: str, message: str) -> Any:
    from astrid.sdk.workspace_client import WorkspaceClientError

    return WorkspaceClientError(
        0,
        "identity_mismatch",
        message,
        {
            "field": field,
            "next_action": "reconfigure the Astrid runtime with `banodoco-local up --profile astrid`",
        },
    )


def _require_mapping(value: Any, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _protocol_error(field, f"runtime {field} response must be an object")
    return value


def _validate_health(value: Any, *, expected_protocol: str, expected_digest: str) -> None:
    health = _require_mapping(value, field="health")
    if frozenset(health) != _HEALTH_KEYS:
        raise _protocol_error("health", "runtime health response has an unexpected schema")
    if health.get("status") != "ok":
        raise _protocol_error("health.status", "runtime health status is not ok")
    if health.get("protocol") != expected_protocol:
        raise _protocol_error("health.protocol", "runtime health protocol does not match workspace.v1")
    if health.get("schema_digest") != expected_digest:
        raise _protocol_error("health.schema_digest", "runtime health schema digest does not match the client")
    epoch = health.get("runtime_epoch")
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 1:
        raise _protocol_error("health.runtime_epoch", "runtime health runtime_epoch is invalid")


def _validate_handshake(
    value: Any,
    *,
    expected_protocol: str,
    expected_digest: str,
    expected_realm: str,
    expected_actor: str,
) -> None:
    handshake = _require_mapping(value, field="handshake")
    if frozenset(handshake) != _HANDSHAKE_KEYS:
        raise _protocol_error("handshake", "runtime handshake response has an unexpected schema")
    if handshake.get("protocol") != expected_protocol:
        raise _protocol_error("handshake.protocol", "runtime handshake protocol does not match workspace.v1")
    if handshake.get("schema_digest") != expected_digest:
        raise _protocol_error("handshake.schema_digest", "runtime handshake schema digest does not match the client")
    session_id = handshake.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise _protocol_error("handshake.session_id", "runtime handshake session_id is missing")
    if handshake.get("realm_id") != expected_realm:
        raise _identity_error("handshake.realm_id", "runtime handshake realm_id does not match the explicit client context")
    if handshake.get("actor_id") != expected_actor:
        raise _identity_error("handshake.actor_id", "runtime handshake actor_id does not match the explicit client context")
    scopes = handshake.get("scopes")
    if not isinstance(scopes, (list, tuple)) or any(
        not isinstance(scope, str) or not scope.strip() for scope in scopes
    ):
        raise _protocol_error("handshake.scopes", "runtime handshake scopes must be non-empty strings")
    if len(set(scopes)) != len(scopes) or frozenset(scopes) != _REQUIRED_SCOPES:
        raise _protocol_error("handshake.scopes", "runtime handshake did not grant exactly the required scopes")


class AstridClient:
    """Context-managed client for the remote workspace product contract."""

    def __init__(self, *, remote: Any) -> None:
        self._remote = remote

    @classmethod
    def open(
        cls,
        *,
        endpoint: str | None = None,
        credential: str | Path | None = None,
        realm_id: str | None = None,
        actor_id: str | None = None,
        client_name: str | None = None,
        client_version: str | None = None,
        protocol_version: str | None = None,
    ) -> Self:
        """Connect using a fully explicit, validated runtime context.

        Cold launch belongs to the explicit Astrid launcher boundary. An
        ordinary SDK construction never retries by invoking a process.
        """
        from astrid.sdk.exceptions import ServiceUnavailableError
        from astrid.sdk.remote import RemoteAstridClient
        from astrid.sdk.workspace_client import (
            WorkspaceClient,
            resolve_runtime_connection,
        )

        if protocol_version != PROTOCOL:
            raise ServiceUnavailableError(
                "unsupported runtime protocol; run `banodoco-local up --profile astrid`",
                details={"next_action": "banodoco-local up --profile astrid"},
            )
        if not all(isinstance(value, str) and value.strip() for value in (endpoint, realm_id, actor_id, client_name, client_version)) or not isinstance(credential, (str, Path)) or (isinstance(credential, str) and not credential.strip()):
            raise ServiceUnavailableError(
                "runtime realm, actor, and client identity are required; run `banodoco-local up --profile astrid`",
                details={"next_action": "banodoco-local up --profile astrid"},
            )

        def unavailable(exc: Exception) -> ServiceUnavailableError:
            fields = getattr(exc, "details", {})
            reason = getattr(exc, "code", "unavailable")
            return ServiceUnavailableError(
                "runtime rejected the explicit client context; reconfigure the Astrid runtime with `banodoco-local up --profile astrid`",
                details={
                    "reason": reason,
                    **(fields if isinstance(fields, dict) else {}),
                    "next_action": "banodoco-local up --profile astrid",
                },
            )

        def connect(endpoint_value: str, token: str) -> Any:
            workspace = WorkspaceClient(endpoint_value, token)
            _validate_health(workspace.health(), expected_protocol=PROTOCOL, expected_digest=SCHEMA_DIGEST)
            handshake = workspace.handshake(
                client_name,
                client_version,
                [
                    "projects:read",
                    "projects:write",
                    "objects:read",
                    "objects:write",
                    "tasks:read",
                    "tasks:write",
                ],
            )
            _validate_handshake(
                handshake,
                expected_protocol=PROTOCOL,
                expected_digest=SCHEMA_DIGEST,
                expected_realm=realm_id,
                expected_actor=actor_id,
            )
            return workspace

        try:
            endpoint_value, token = resolve_runtime_connection(endpoint, credential)
            workspace = connect(endpoint_value, token)
            return cls(remote=RemoteAstridClient(workspace))
        except Exception as exc:
            raise unavailable(exc) from exc

    @classmethod
    def open_from_launcher(
        cls,
        *,
        credential: str | Path | None = None,
        client_name: str = "astrid",
        client_version: str = "stage1",
        protocol_version: str = "workspace.v1",
    ) -> Self:
        """Launch the neutral runtime at Astrid's explicit CLI boundary.

        The credential is still explicit: the launcher may supply it as a
        path/token, or the caller may opt into the documented
        ``BANODOCO_RUNTIME_CREDENTIAL`` setting.  No SDK operation invokes
        this method implicitly.
        """
        import os

        from astrid.sdk.autobootstrap import AutoBootstrapError, ensure_runtime
        from astrid.sdk.exceptions import ServiceUnavailableError

        try:
            result = ensure_runtime()
        except AutoBootstrapError as exc:
            raise ServiceUnavailableError(
                str(exc), details={"next_action": "banodoco-local up --profile astrid"}
            ) from exc
        if credential is not None:
            credential_value: str | Path = credential
        else:
            # The environment variable is a launcher-issued path, not an
            # ambient bearer token. Keep it typed as a Path so the explicit
            # credential boundary rejects symlinks before reading it.
            credential_env = os.environ.get("BANODOCO_RUNTIME_CREDENTIAL", "").strip()
            credential_value = Path(credential_env) if credential_env else ""
        if not credential_value:
            # `up --json` deliberately hands off a file path, not the secret.
            # Let the explicit client boundary read that owner-only file.
            credential_file = result.get("credential_file", "")
            credential_value = Path(str(credential_file)) if credential_file else ""
        if not credential_value:
            raise ServiceUnavailableError(
                "runtime credential is required; run `banodoco-local up --profile astrid`",
                details={"next_action": "banodoco-local up --profile astrid"},
            )
        return cls.open(
            endpoint=str(result.get("endpoint", "")),
            credential=credential_value,
            realm_id=str(result.get("realm_id", "")),
            actor_id=str(result.get("actor_id", "")),
            client_name=client_name,
            client_version=client_version,
            protocol_version=protocol_version,
        )

    def invoke_result(self, capability_id: str, *, kind: str, **kwargs: Any) -> Any:
        """Invoke through this explicit runtime-bound client as a result.

        The module-level helper owns the typed preflight/result conversion;
        this method supplies the already-authenticated client so admission
        cannot silently compose a second local authority.
        """
        from astrid.sdk.invocation import invoke_result

        kwargs.setdefault("client", self)
        return invoke_result(capability_id, kind=kind, **kwargs)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    @property
    def projects(self) -> Any:
        return self._remote.projects

    @property
    def timelines(self) -> Any:
        return self._remote.timelines

    @property
    def media(self) -> Any:
        return self._remote.media

    @property
    def tasks(self) -> Any:
        return self._remote.tasks

    @property
    def runs(self) -> Any:
        return self._remote.runs

    @property
    def references(self) -> Any:
        return self._remote.references

    @property
    def shots(self) -> Any:
        return self._remote.shots

    @property
    def generations(self) -> Any:
        return self._remote.generations

    def handshake(self, client_name: str, client_version: str, requested_scopes: list[str]) -> Any:
        return self._remote.handshake(client_name, client_version, requested_scopes)

    def doctor(self) -> Any:
        return self._remote.doctor()

    def create_backup(self, destination: str) -> Any:
        return self._remote.create_backup(destination)

    def restore_backup(self, backup: str, destination: str) -> Any:
        return self._remote.restore_backup(backup, destination)

    def export_realm(self) -> Any:
        return self._remote.export_realm()

    def tombstone_realm(self, *, reason: str | None = None, expected_version: int | None = None) -> Any:
        return self._remote.tombstone_realm(reason=reason, expected_version=expected_version)

    def recover_realm(self, *, expected_realm_id: str, expected_version: int, confirmation: str | None = None, noninteractive: bool = False) -> Any:
        return self._remote.recover_realm(expected_realm_id=expected_realm_id, expected_version=expected_version, confirmation=confirmation, noninteractive=noninteractive)

    def purge_realm(self, confirmation: str) -> Any:
        return self._remote.purge_realm(confirmation)

    def health(self) -> Any:
        from astrid.sdk.exceptions import ServiceUnavailableError
        from astrid.sdk.workspace_client import WorkspaceClientError

        try:
            return self._remote.health()
        except WorkspaceClientError as exc:
            raise ServiceUnavailableError(
                "runtime unavailable; run `banodoco-local up --profile astrid`",
                details={
                    "next_action": "banodoco-local up --profile astrid",
                    "reason": exc.code,
                },
            ) from exc

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return self._remote.invoke(*args, **kwargs)
