"""Context-managed ``AstridClient`` lifecycle over the standard application.

(m4 plan step 18, task T19.) ``AstridClient.open()`` composes the standard
application (``astrid.application.compose_standard_application``) and binds
the client to it, exposing the seven typed application-owned services —
``projects``, ``timelines``, ``media``, ``tasks``, ``runs``,
``references``, and ``shots`` — as typed attributes. The client performs
**no service construction of its own**: every service is wired by the
application composition (plan step 17), and the client only surfaces the
already-composed instances.

Lazy capability APIs are preserved on the client exactly as on
``astrid.sdk``: ``discover``, ``get_capability``, typed ``invoke``,
``generate`` (the :class:`~astrid.sdk.generation.GenerationFacade`),
``render``, and the verified event reads (``read_events`` /
``subscribe_events``). Each delegates to the module-level SDK function at
call time, so the heavy capability machinery is imported only when a
capability API is actually used. Invocation results keep their result IDs
(``InvocationResult.run_id`` / ``run_root``) and outputs untouched.

Import behavior is deliberately lightweight: importing this module (or
``astrid``) opens no database, composes no registry, and imports no heavy
execution module. The application composition is imported lazily inside
:meth:`AstridClient.open` — the first moment a database is actually
required.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    from astrid.application import StandardApplication
    from astrid.sdk.media import MediaService
    from astrid.sdk.projects import ProjectsService
    from astrid.sdk.references import ReferencesService
    from astrid.sdk.runs import RunsService
    from astrid.sdk.shots import ShotsService
    from astrid.sdk.tasks import TasksService
    from astrid.sdk.timelines import TimelinesService

__all__ = ["AstridClient"]


class AstridClient:
    """Context-managed lifecycle owner for the seven application services.

    A client is always bound to exactly one composed standard application:
    one writer queue, one registry, the kernel and pack repositories, the
    read-only ordered event repository, and the seven typed services. It is
    a thin, stateless surface — all domain behavior lives in the services.

    Typical use::

        with AstridClient.open(projects_root=...) as client:
            project = client.projects.create(slug="demo", name="Demo")
            timeline = client.timelines.create(
                project="demo", slug="main", name="Main",
            )

    ``close()`` drains the writer queue, stops the writer thread, closes
    the database, and releases the exclusive-owner lock (idempotent; the
    context manager closes deterministically on exit).
    """

    def __init__(self, app: StandardApplication) -> None:
        """Bind the client to an already-composed *app* (no construction).

        ``app`` must be a :class:`~astrid.application.StandardApplication`
        produced by ``astrid.application.compose_standard_application`` (or
        an equivalent composition); the client never builds services.
        """
        self._app = app

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def open(
        cls,
        projects_root: str | Path | None = None,
        *,
        registry: Any | None = None,
        database_path: str | Path | None = None,
    ) -> Self:
        """Compose the standard application and return a bound client.

        Resolves the projects root (argument, ``ASTRID_PROJECTS_ROOT``, or
        the default), acquires the exclusive-owner lock, opens the single
        standard writer, wires every repository and the seven typed
        services, and binds them to the new client. A second owner fails
        closed with the typed ``unavailable`` contract. The application
        composition is imported here — never at module import time — so
        importing this module opens nothing.
        """
        from astrid.application import compose_standard_application

        app = compose_standard_application(
            projects_root,
            registry=registry,
            database_path=database_path,
        )
        return cls(app)

    def close(self) -> None:
        """Close the bound application (deterministic and idempotent)."""
        self._app.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- application access --------------------------------------------------

    @property
    def app(self) -> StandardApplication:
        """The bound standard application (repositories, events, writer)."""
        return self._app

    # -- the seven application-owned services --------------------------------

    @property
    def projects(self) -> ProjectsService:
        """Typed project service (create/list/show/update/select)."""
        return self._app.projects_service

    def selected_project_ref(self, *, cwd: str | Path | None = None) -> str | None:
        """Return the workspace/user-selected project ref for CLI routing.

        This reads only the non-authoritative preference. The target service
        still resolves the ref against the bound kernel, so stale selections
        fail closed and explicit ``--project`` remains authoritative.
        """
        from astrid.core.preferences import resolve_default_project

        return resolve_default_project(cwd)

    @property
    def timelines(self) -> TimelinesService:
        """Typed timeline service (create/list/show/save/archive/...)."""
        return self._app.timelines_service

    @property
    def media(self) -> MediaService:
        """Typed media service (import/verify/relocate/relate/...)."""
        return self._app.media_service

    @property
    def tasks(self) -> TasksService:
        """Typed task service (create/list/show/cancel/retry/...)."""
        return self._app.tasks_service

    @property
    def runs(self) -> RunsService:
        """Typed run service (list/show/cancel/retry_failed/...)."""
        return self._app.runs_service

    @property
    def references(self) -> ReferencesService:
        """Typed reference service (create/update/archive/associate/...)."""
        return self._app.references_service

    @property
    def shots(self) -> ShotsService:
        """Typed shot service (list/show/create/add/remove/reorder)."""
        return self._app.shots_service

    # -- lazy capability APIs ------------------------------------------------

    def _bound_root(self) -> str:
        """The client's bound projects root (resolved by the application)."""
        return str(self._app.projects_root)

    def discover(self, **kwargs: Any) -> Any:
        """Lazy ``astrid.sdk.discover`` bound to the client's projects root.

        The discovery machinery (registries, pack inventory) is imported
        only when this method is actually called. An explicit
        ``project_root`` keyword wins over the bound root.
        """
        from astrid.sdk import discover

        kwargs.setdefault("project_root", self._bound_root())
        return discover(**kwargs)

    def get_capability(self, capability_id: str, **kwargs: Any) -> Any:
        """Lazy ``astrid.sdk.get_capability`` bound to the client's root.

        Raises the typed ``CapabilityNotFoundError`` /
        ``CapabilityAmbiguousError`` family for failed lookups.
        """
        from astrid.sdk import get_capability

        kwargs.setdefault("project_root", self._bound_root())
        return get_capability(capability_id, **kwargs)

    def invoke(self, capability_id: str, **kwargs: Any) -> Any:
        """Lazy typed ``astrid.sdk.invoke`` bound to the client's root.

        Capability resolution AND run placement happen against the bound
        application's projects root — a run ledger (``run.json`` under the
        resolved project's ``runs/`` directory) lands beneath it, never
        under the process default. An explicit ``project_root`` keyword
        wins over the bound root. Returns an
        :class:`~astrid.sdk.results.InvocationResult` whose result IDs
        (``run_id``/``run_root``) and outputs are preserved.
        """
        from astrid.sdk import invoke

        kwargs.setdefault("project_root", self._bound_root())
        # Preserve the exact schema-pack composition that opened this client.
        # A long-lived client may intentionally include migrations beyond the
        # standard in-tree packs; rebuilding a standard registry at invoke
        # time would make the canonical DB unreadable to its own client.
        kwargs.setdefault("registry", self._app.registry)
        kwargs.setdefault("_client", self)
        return invoke(capability_id, **kwargs)

    def invoke_result(self, capability_id: str, **kwargs: Any) -> Any:
        """Lazy ``astrid.sdk.invoke_result`` with the bound projects root.

        This is the envelope-oriented sibling of :meth:`invoke`: typed
        preflight failures are returned as ``InvocationResult(ok=False)``
        instead of being raised, while the normal invoke API remains
        exception-oriented for callers that want typed branches.
        """
        from astrid.sdk import invoke_result

        kwargs.setdefault("project_root", self._bound_root())
        kwargs.setdefault("registry", self._app.registry)
        kwargs.setdefault("_client", self)
        return invoke_result(capability_id, **kwargs)

    @property
    def generate(self) -> Any:
        """The lazy generation facade (``astrid.sdk.generate``).

        ``client.generate.image(...)`` / ``client.generate.video(...)``
        resolve plugin-registered generation verbs on first use; nothing is
        imported until a generation call is made.
        """
        from astrid.sdk import generate

        return generate

    def render(self, *args: Any, **kwargs: Any) -> Any:
        """Lazy ``astrid.sdk.render``: render a timeline and return the path."""
        from astrid.sdk import render

        return render(*args, **kwargs)

    def read_events(self, *args: Any, **kwargs: Any) -> Any:
        """Lazy verified ``astrid.sdk.read_events`` for one run."""
        from astrid.sdk import read_events

        return read_events(*args, **kwargs)

    def subscribe_events(self, *args: Any, **kwargs: Any) -> Any:
        """Lazy verified ``astrid.sdk.subscribe_events`` event stream."""
        from astrid.sdk import subscribe_events

        return subscribe_events(*args, **kwargs)
