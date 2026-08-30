"""Public Astrid SDK client backed exclusively by the workspace runtime.

The client is deliberately only a transport composition root. It does not
open a database, acquire a store lock, load repositories, or construct a
local application. Runtime discovery and credentials are resolved by
``workspace_client`` and product families are exposed by ``remote``.
"""

from __future__ import annotations

from typing import Any, Self

__all__ = ["AstridClient"]


class AstridClient:
    """Context-managed client for the remote workspace product contract."""

    def __init__(self, *, remote: Any) -> None:
        self._remote = remote

    @classmethod
    def open(cls) -> Self:
        """Discover and connect to the selected workspace runtime."""
        from astrid.sdk.exceptions import ServiceUnavailableError
        from astrid.sdk.remote import RemoteAstridClient
        from astrid.sdk.workspace_client import (
            WorkspaceClient,
            WorkspaceClientError,
            resolve_runtime_connection,
        )

        try:
            endpoint, token = resolve_runtime_connection()
            return cls(remote=RemoteAstridClient(WorkspaceClient(endpoint, token)))
        except WorkspaceClientError as exc:
            raise ServiceUnavailableError(
                "runtime unavailable; run `banodoco-local up --profile astrid`",
                details={
                    "next_action": "banodoco-local up --profile astrid",
                    "reason": exc.code,
                },
            ) from exc

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

    def handshake(self, **kwargs: Any) -> Any:
        return self._remote.handshake(**kwargs)

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
