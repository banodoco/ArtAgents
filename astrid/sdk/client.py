"""Public Astrid SDK client backed exclusively by the workspace runtime.

The client is deliberately only a transport composition root. It does not
open a database, acquire a store lock, load repositories, or construct a
local application. Runtime discovery and credentials are resolved by
``workspace_client`` and product families are exposed by ``remote``.
"""

from __future__ import annotations

import os
from typing import Any, Self

__all__ = ["AstridClient"]


class AstridClient:
    """Context-managed client for the remote workspace product contract."""

    def __init__(self, *, remote: Any) -> None:
        self._remote = remote

    @classmethod
    def open(cls, *, auto_bootstrap: bool = True) -> Self:
        """Discover, ensure, and connect to the selected workspace runtime.

        Product commands and SDK callers get the normal beta behavior: when
        the endpoint is absent or unhealthy, the configured neutral
        ``banodoco-local`` launcher is invoked and the connection is retried.
        Operational read-only routes such as ``doctor`` can pass
        ``auto_bootstrap=False`` to preserve their side-effect-free contract.
        """
        from astrid.sdk.exceptions import ServiceUnavailableError
        from astrid.sdk.remote import RemoteAstridClient
        from astrid.sdk.workspace_client import (
            WorkspaceClient,
            WorkspaceClientError,
            resolve_runtime_connection,
        )

        def unavailable(exc: Exception) -> ServiceUnavailableError:
            return ServiceUnavailableError(
                "runtime unavailable; run `banodoco-local up --profile astrid`",
                details={
                    "next_action": "banodoco-local up --profile astrid",
                    "reason": getattr(exc, "code", "unavailable"),
                },
            )

        def connect(endpoint: str, token: str) -> Any:
            workspace = WorkspaceClient(endpoint, token)
            workspace.health()
            workspace.handshake(
                "astrid-sdk",
                "0.1.0",
                [
                    "projects:read",
                    "projects:write",
                    "objects:read",
                    "objects:write",
                    "tasks:read",
                    "tasks:write",
                ],
            )
            return workspace

        try:
            endpoint, token = resolve_runtime_connection()
            workspace = connect(endpoint, token)
            return cls(remote=RemoteAstridClient(workspace))
        except WorkspaceClientError as exc:
            if not auto_bootstrap or os.environ.get("BANODOCO_ASTRID_AUTO_BOOTSTRAP", "1").strip().lower() in {"0", "false", "no", "off"}:
                raise unavailable(exc) from exc
            try:
                from astrid.sdk.autobootstrap import ensure_runtime

                ensure_runtime()
                endpoint, token = resolve_runtime_connection()
                workspace = connect(endpoint, token)
                return cls(remote=RemoteAstridClient(workspace))
            except Exception as retry_exc:
                raise unavailable(retry_exc) from retry_exc

    def close(self) -> None:
        self._remote.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def selected_project_ref(self, **kwargs: Any) -> str | None:
        """Runtime selection is resolved by the host, not local preferences."""
        return self._remote.selected_project_ref(**kwargs)

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

    def handshake(self, **kwargs: Any) -> Any:
        return self._remote.handshake(**kwargs)

    def doctor(self) -> Any:
        return self._remote.doctor()

    def create_backup(self, destination: str) -> Any:
        return self._remote.create_backup(destination)

    def restore_backup(self, backup: str, destination: str) -> Any:
        return self._remote.restore_backup(backup, destination)

    def export_realm(self) -> Any:
        return self._remote.export_realm()

    def tombstone_realm(self, **kwargs: Any) -> Any:
        return self._remote.tombstone_realm(**kwargs)

    def recover_realm(self, **kwargs: Any) -> Any:
        return self._remote.recover_realm(**kwargs)

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

    def read_events(self, *args: Any, **kwargs: Any) -> Any:
        return self._remote.read_events(*args, **kwargs)

    def subscribe_events(self, *args: Any, **kwargs: Any) -> Any:
        return self._remote.subscribe_events(*args, **kwargs)

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return self._remote.invoke(*args, **kwargs)

    def render(self, *args: Any, **kwargs: Any) -> Any:
        return self._remote.render(*args, **kwargs)
