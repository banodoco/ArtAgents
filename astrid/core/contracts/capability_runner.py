"""Generic execution skeleton shared by Astrid capability runners.

The executor and orchestrator runners historically carried a byte-for-byte copy
of the same ``run`` control flow: gate the call when inside a task run, resolve
the definition from a registry, prepare an optional project run context, execute
the inner runner, then finalize the project context on success or failure. They
differ only in four axes:

* the **result type** they produce (``ExecutorRunResult`` /
  ``OrchestratorRunResult``),
* how they **build a command** for the capability,
* how they perform **registry lookup** (which default registry to load and how
  to extract the requested id from a request), and
* the domain-specific gate / project-finalize hooks.

:class:`CapabilityRunner` captures the common control flow once and exposes the
varying pieces as hooks. The executor runner derives from it today; the
orchestrator runner can adopt it later without changing this skeleton.
"""

from __future__ import annotations

import sys
from typing import Generic, Protocol, TypeVar

from astrid.core.contracts.run_status import RunStatus

RequestT = TypeVar("RequestT")
ResultT = TypeVar("ResultT")
DefinitionT = TypeVar("DefinitionT")


class _CapabilityRegistry(Protocol[DefinitionT]):
    def get(self, capability_id: str) -> DefinitionT: ...


class CapabilityRunner(Generic[RequestT, ResultT, DefinitionT]):
    """Template for capability execution, parameterized over result type.

    Subclasses implement the registry-lookup, command-building, gating, and
    project-finalize hooks; :meth:`run` ties them together with the shared
    control flow so behavior stays identical across capability domains.
    """

    # -- registry lookup ---------------------------------------------------

    def load_default_registry(self) -> _CapabilityRegistry[DefinitionT]:
        raise NotImplementedError

    def request_id(self, request: RequestT) -> str:
        raise NotImplementedError

    def validate_definition(self, request: RequestT, definition: DefinitionT) -> None:
        """Fence an admitted request to the registry definition it selected."""

    # -- command building --------------------------------------------------

    def build_command(self, request: RequestT, registry: object | None = None) -> tuple[str, ...]:
        raise NotImplementedError

    # -- gating ------------------------------------------------------------

    def maybe_gate(self, request: RequestT) -> None:
        """Gate the call when it is part of an active task run (no-op otherwise)."""

    # -- project run context -----------------------------------------------

    def resolve_project_request(self, request: RequestT, definition: DefinitionT) -> RequestT:
        return request

    def is_dry_run(self, request: RequestT, definition: DefinitionT) -> bool:
        return False

    def prepare_dry_run_request(self, request: RequestT, definition: DefinitionT) -> RequestT:
        return request

    def prepare_project(self, request: RequestT, definition: DefinitionT) -> tuple[object | None, RequestT]:
        raise NotImplementedError

    def finalize_project(
        self,
        context: object,
        request: RequestT,
        *,
        status: RunStatus,
        returncode: int | None,
        error: BaseException | str | None = None,
    ) -> None:
        raise NotImplementedError

    def status_for_result(self, result: ResultT) -> RunStatus:
        raise NotImplementedError

    def result_returncode(self, result: ResultT) -> int | None:
        raise NotImplementedError

    def mark_finalize_failed(
        self, context: object, request: RequestT, finalize_error: BaseException
    ) -> None:
        """Best-effort secondary write after success-path finalize failure."""

    # -- inner execution ---------------------------------------------------

    def run_inner(self, request: RequestT, definition: DefinitionT) -> ResultT:
        raise NotImplementedError

    # -- shared control flow ----------------------------------------------

    def run(self, request: RequestT, registry: _CapabilityRegistry[DefinitionT] | None = None) -> ResultT:
        self.maybe_gate(request)
        active_registry = registry if registry is not None else self.load_default_registry()
        definition = active_registry.get(self.request_id(request))
        self.validate_definition(request, definition)
        resolved_request = self.resolve_project_request(request, definition)
        if self.is_dry_run(resolved_request, definition):
            return self.run_inner(
                self.prepare_dry_run_request(resolved_request, definition),
                definition,
            )
        project_context, effective_request = self.prepare_project(resolved_request, definition)
        try:
            result = self.run_inner(effective_request, definition)
        except Exception as exc:
            if project_context is not None:
                try:
                    self.finalize_project(
                        project_context,
                        effective_request,
                        status=RunStatus.FAILED,
                        returncode=-1,
                        error=exc,
                    )
                except Exception as finalize_exc:
                    _attach_exception_note(
                        exc,
                        "finalize after execution failure also failed: "
                        f"{finalize_exc.__class__.__name__}: {finalize_exc}",
                    )
            raise
        if project_context is not None:
            try:
                self.finalize_project(
                    project_context,
                    effective_request,
                    status=self.status_for_result(result),
                    returncode=self.result_returncode(result),
                )
            except Exception as finalize_exc:
                try:
                    self.mark_finalize_failed(project_context, effective_request, finalize_exc)
                except Exception as mark_exc:
                    _attach_exception_note(
                        finalize_exc,
                        "mark_finalize_failed also failed: "
                        f"{mark_exc.__class__.__name__}: {mark_exc}",
                    )
                raise
        return result


def _attach_exception_note(exc: BaseException, note: str) -> None:
    add_note = getattr(exc, "add_note", None)
    if callable(add_note):
        add_note(note)
        return
    print(note, file=sys.stderr)


__all__ = ["CapabilityRunner"]
