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

from typing import Generic, Protocol, TypeVar

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

    # -- command building --------------------------------------------------

    def build_command(self, request: RequestT, registry: object | None = None) -> tuple[str, ...]:
        raise NotImplementedError

    # -- gating ------------------------------------------------------------

    def maybe_gate(self, request: RequestT) -> None:
        """Gate the call when it is part of an active task run (no-op otherwise)."""

    # -- project run context -----------------------------------------------

    def prepare_project(self, request: RequestT, definition: DefinitionT) -> tuple[object | None, RequestT]:
        raise NotImplementedError

    def finalize_project(
        self,
        context: object,
        request: RequestT,
        *,
        status: str,
        returncode: int | None,
        error: BaseException | str | None = None,
    ) -> None:
        raise NotImplementedError

    def status_for_result(self, result: ResultT) -> str:
        raise NotImplementedError

    def result_returncode(self, result: ResultT) -> int | None:
        raise NotImplementedError

    # -- inner execution ---------------------------------------------------

    def run_inner(self, request: RequestT, definition: DefinitionT) -> ResultT:
        raise NotImplementedError

    # -- shared control flow ----------------------------------------------

    def run(self, request: RequestT, registry: _CapabilityRegistry[DefinitionT] | None = None) -> ResultT:
        self.maybe_gate(request)
        active_registry = registry if registry is not None else self.load_default_registry()
        definition = active_registry.get(self.request_id(request))
        project_context, effective_request = self.prepare_project(request, definition)
        try:
            result = self.run_inner(effective_request, definition)
        except Exception as exc:
            if project_context is not None:
                self.finalize_project(
                    project_context, effective_request, status="error", returncode=-1, error=exc
                )
            raise
        if project_context is not None:
            self.finalize_project(
                project_context,
                effective_request,
                status=self.status_for_result(result),
                returncode=self.result_returncode(result),
            )
        return result


__all__ = ["CapabilityRunner"]
