"""Public Astrid SDK client backed exclusively by the workspace runtime.

The client is deliberately only a transport composition root. It does not
open a database, acquire a store lock, load repositories, or construct a
local application. Runtime discovery and credentials are resolved by
``workspace_client`` and product families are exposed by ``remote``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self

__all__ = ["AstridClient"]


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
            WorkspaceClientError,
            resolve_runtime_connection,
        )

        if protocol_version != "workspace.v1":
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
            return ServiceUnavailableError(
                "runtime unavailable; run `banodoco-local up --profile astrid`",
                details={
                    "next_action": "banodoco-local up --profile astrid",
                    "reason": exc.__dict__.get("code", "unavailable"),
                },
            )

        def connect(endpoint_value: str, token: str) -> Any:
            workspace = WorkspaceClient(endpoint_value, token)
            workspace.health()
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
            if handshake is None or handshake.get("realm_id") != realm_id or handshake.get("actor_id") != actor_id:
                raise WorkspaceClientError(0, "identity_mismatch", "runtime realm or actor identity does not match the explicit client context")
            return workspace

        try:
            endpoint_value, token = resolve_runtime_connection(endpoint, credential)
            workspace = connect(endpoint_value, token)
            return cls(remote=RemoteAstridClient(workspace))
        except WorkspaceClientError as exc:
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
        credential_value: str | Path = (
            credential
            if credential is not None
            else os.environ.get("BANODOCO_RUNTIME_CREDENTIAL", "")
        )
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
