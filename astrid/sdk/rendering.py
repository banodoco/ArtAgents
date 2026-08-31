"""Public rendering SDK surface.

This module wraps the canonical core rendering DTOs
(:class:`RenderRequest`, :class:`RenderResult`, :class:`SupportReport`)
with three public entrypoints:

* ``renderer_main`` — a thin protocol-v1 command entrypoint that mirrors the
  raw-command backend's file protocol exactly::

      python -m astrid.sdk.rendering render|support --request <abs.json> --result <abs.json>

  It reads the request JSON, dispatches through the rendering registries and
  the command transport (the same public backend machinery the
  :class:`~astrid.core.rendering.service.RenderService` uses), validates the
  result, and writes the frozen result JSON shape to ``--result``.
* ``render`` — a convenience that builds a :class:`RenderRequest` from
  friendly arguments and delegates to the shared
  :class:`~astrid.core.rendering.service.RenderService`, returning the
  published output path.
* ``support`` — a convenience that resolves a qualified backend and returns
  its :class:`SupportReport`.
* :class:`RenderContext` — the convenience facade a third-party ``render.py``
  author gets for the duration of one invocation: workspace-validated path
  allocation, asset descriptor resolution from a trusted attempt-local
  object-id/digest handoff (host-staged files and a derived invocation asset
  server URL),
  permission checks, a sanitized subprocess runner,
  redacted logs, a cooperative interruption flag, media probing, hashing,
  audio completion, and named attachments.

RenderContext is not an OS sandbox; it enforces workspace conventions, not
process isolation.

The module stays lightweight: importing it never imports the rendering
service, transport, registries, assets materializer, or any pack backend.
Those are loaded function-locally, on first use.

Wire equivalence is a hard contract: every JSON payload this module writes is
the ``to_dict()`` of a frozen core DTO.  There are no SDK-only wire fields and
no semantics drift from the raw fixture/backend path.

Worked example (scaffold → SDK renderer):

1. Scaffold the four-file pack, then point the manifest command at this
   module's entrypoint instead of the generated ``render.py``::

       python3 -m astrid.core.rendering.cli create wave acme_wave
       # acme_wave/renderer.yaml: command: [python3, -m, astrid.sdk.rendering]

2. From Python, render through the shared service — the SDK builds a frozen
   :class:`RenderRequest`, dispatches through :class:`RenderService`, and
   returns the published output path::

       import astrid
       out = astrid.render(
           "out/hype.timeline.json",
           assets_registry_path="out/hype.assets.json",
           backend="acme_wave.wave",
           backend_config={"acme_wave.wave": {"quality": "preview"}},
           out_path="out/hype.mp4",
       )
       # out/hype.mp4 + out/hype.mp4.provenance.json

3. Ask a qualified backend whether it supports a specific request::

       report = astrid.support("acme_wave.wave", timeline_path="out/hype.timeline.json")
       assert report.supported

4. Inside ``render.py``, use :class:`RenderContext` for workspace-validated
   paths, sanitized subprocesses, redacted logs, probing/hashing, audio
   completion, and attachments (see ``docs/reference/sdk.md`` for the full
   worked example)::

       from astrid import RenderContext
       from astrid.core.rendering.contracts import RenderRequest, RenderResult

       def render(workspace, request: RenderRequest) -> RenderResult:
           with RenderContext(workspace, backend="acme_wave.wave") as ctx:
               out = ctx.output_path(request.output_name)
               ctx.run(["vendor-tool", "--out", out])
               return RenderResult(...)  # frozen DTO, validated by the host

The user-facing walkthrough lives in ``docs/reference/sdk.md``; the wire
contract is ``docs/contracts/render-backend-v1.md``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from astrid.core.foundation.hash import sha256_file
from astrid.core.rendering.contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    FrameWindow,
    RenderProfile,
    RenderRequest,
    RenderResult,
    SupportReport,
    _require_qualified_id,
)

from .results import _json_safe

__all__ = ["RenderContext", "render", "renderer_main", "support"]

_CORE_BACKEND_ID = "astrid.core"
_TRANSPORT_BACKEND_ENV = "ASTRID_RENDER_BACKEND"
_SUPPORT_DEFAULT_OUTPUT_NAME = "video.mp4"


# ---------------------------------------------------------------------------
# renderer_main — protocol v1 command entrypoint
# ---------------------------------------------------------------------------


def renderer_main(
    argv: Sequence[str] | None = None,
    *,
    service: Any = None,
    registries: Any = None,
    transport: Any = None,
    transport_factory: Any = None,
    validator: Any = None,
) -> int:
    """Execute one v1 render/support command and write its result file.

    Mirrors the raw-command backend's file protocol exactly::

        renderer_main(["render", "--request", req.json, "--result", res.json])
        renderer_main(["support", "--request", req.json, "--result", res.json])

    The request JSON is parsed and validated as a :class:`RenderRequest`.
    ``render`` dispatches through the rendering registry and command
    transport (the public backend path), validates the returned
    :class:`RenderResult` with the core artifact validator, and writes its
    ``to_dict()`` to the result path.  ``support`` resolves the qualified
    backend and writes the :class:`SupportReport` ``to_dict()``.  Failures
    are written as the frozen :class:`RendererError` JSON shape and the
    function returns ``0``; ``KeyboardInterrupt`` and ``SystemExit`` are
    re-raised.

    The selected backend is resolved from ``ASTRID_RENDER_BACKEND`` (set by
    the command transport when this entrypoint runs as a manifest command),
    then from the request's ``backend_config`` namespace (exactly one), and
    never from timeline shape.

    ``service``, ``registries``, ``transport``, ``transport_factory``, and
    ``validator`` are injectable for embedding and testing; when omitted the
    production defaults are loaded lazily.
    """
    from astrid.core.rendering.errors import RendererException

    parser = argparse.ArgumentParser(
        prog="astrid.sdk.rendering.renderer_main",
        description="Astrid rendering protocol v1 command entrypoint.",
    )
    parser.add_argument("verb", choices=("render", "support"))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        request_path = args.request.resolve(strict=True)
        result_path = args.result.resolve()
        if request_path == result_path:
            raise ValueError("--request and --result must be different paths")
        request = _load_request(request_path)
    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
        RendererException,
    ) as exc:
        _write_failure(args.result.resolve(), exc, kind="protocol")
        return 0

    try:
        workspace = request_path.parent
        if args.verb == "support":
            response: SupportReport | RenderResult = _support_report(
                request,
                service=service,
                registries=registries,
                transport=transport,
                transport_factory=transport_factory,
                workspace=workspace,
            )
        else:
            response = _backend_render(
                request,
                workspace=workspace,
                registries=registries,
                transport=transport,
                transport_factory=transport_factory,
                validator=validator,
            )
        _write_result(result_path, response)
    except RendererException as exc:
        _write_failure(result_path, exc, kind=exc.error.kind)
    except FileNotFoundError as exc:
        _write_failure(result_path, exc, kind="binary_missing")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        _write_failure(result_path, exc, kind="protocol")
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _write_failure(result_path, exc, kind="internal")
    return 0


def _load_request(path: Path) -> RenderRequest:
    """Read and validate one v1 render/support request file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("render request must contain a JSON object")
    return RenderRequest.from_dict(payload)


def _write_result(result_path: Path, response: SupportReport | RenderResult) -> None:
    """Write the frozen result JSON shape (``to_dict`` of the core DTO)."""
    from astrid.core.foundation.atomic_io import write_json_atomic

    write_json_atomic(result_path, response.to_dict())


def _write_failure(result_path: Path, exc: BaseException, *, kind: str) -> None:
    """Write the frozen :class:`RendererError` JSON shape for *exc*."""
    from astrid.core.foundation.atomic_io import write_json_atomic
    from astrid.core.rendering.errors import RendererException, make_renderer_error

    if isinstance(exc, RendererException):
        error_kind = exc.error.kind
        message = exc.error.message
        recovery = exc.error.recovery_command
        details = dict(exc.error.details)
        backend = exc.error.backend
        # The command transport appends its own redacted stdout/stderr
        # diagnostics when it parses a backend error; those are
        # transport-layer diagnostics, not backend wire fields, so the
        # relayed error carries only the backend's own details (matching the
        # raw-command backend's result file exactly).
        if isinstance(details.get("stdout"), str) and isinstance(
            details.get("stderr"), str
        ):
            details.pop("stdout", None)
            details.pop("stderr", None)
    else:
        error_kind = kind
        message = str(exc) or type(exc).__name__
        recovery = None
        details = {"error_type": type(exc).__name__}
        backend = _CORE_BACKEND_ID
    error = make_renderer_error(
        error_kind,
        backend=backend,
        message=message,
        recovery_command=recovery,
        details=details,
    )
    write_json_atomic(result_path, error.to_dict())


def _backend_render(
    request: RenderRequest,
    *,
    workspace: Path,
    registries: Any = None,
    transport: Any = None,
    transport_factory: Any = None,
    validator: Any = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
) -> RenderResult:
    """Dispatch one render through the public backend path and validate it.

    The request is projected to the selected backend's namespace and run
    through the command transport with the invocation workspace as the
    request file's parent (the raw-command backend convention).  The returned
    :class:`RenderResult` is validated against the request profile and the
    workspace, then serialized unchanged — so the written wire JSON matches
    the raw fixture/backend path field for field.
    """
    from astrid.core.foundation.atomic_io import write_json_atomic
    from astrid.core.rendering.artifacts import validate_render_result
    from astrid.core.rendering.errors import raise_protocol_error
    from astrid.core.rendering.registry import RenderingRegistryError
    from astrid.core.rendering.transport import CommandTransport

    renderers, _planners, _finalizers = _resolve_registries(
        registries=registries,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
    )
    backend = _resolve_backend(request)
    candidate = _resolve_candidate(renderers, backend)

    projected = request.for_backend(candidate.id)
    request_path = workspace / "render-request.json"
    result_path = workspace / "render-result.json"
    write_json_atomic(request_path, projected.to_dict())

    selected_transport = transport or (transport_factory or CommandTransport)(
        candidate.id
    )
    response = selected_transport.run(
        "render",
        candidate.manifest.command,
        backend=candidate.id,
        request_path=request_path,
        result_path=result_path,
        cwd=candidate.pack_root,
        timeout=candidate.manifest.timeout_seconds,
        required_binaries=candidate.manifest.required_binaries,
    )
    if not isinstance(response, RenderResult):
        raise_protocol_error(
            backend=candidate.id,
            message="render operation did not return a RenderResult",
            details={"received_type": type(response).__name__},
        )
    expected = request.profile or response.video.profile
    validate = validator or validate_render_result
    validated = validate(
        response,
        expected_profile=expected,
        workspace_root=workspace,
    )
    # The command transport appends its own captured stdout/stderr onto
    # RenderResult.logs (prefixed "stdout:" / "stderr:") when the child is
    # noisy.  Those are transport-layer diagnostics, not backend wire
    # fields; the raw backend's result file carries only the backend's own
    # authored logs.  Strip the appended suffix (trailing entries matching
    # the transport's stream prefix) WITHOUT touching backend-authored
    # entries, so the success file stays wire-identical to the raw path.
    if isinstance(validated, RenderResult) and validated.logs:
        authored = list(validated.logs)
        while authored and (
            authored[-1].startswith("stdout:\n")
            or authored[-1].startswith("stderr:\n")
        ):
            authored.pop()
        if len(authored) != len(validated.logs):
            validated = replace(validated, logs=authored)
    return validated


# ---------------------------------------------------------------------------
# render — public convenience
# ---------------------------------------------------------------------------


def render(
    timeline_path: str | Path,
    *,
    output_name: str | None = None,
    assets_registry_path: str | Path | None = None,
    out_path: str | Path | None = None,
    selector: str | None = None,
    window: FrameWindow | Mapping[str, Any] | None = None,
    audio: AudioOwnership | str | None = None,
    profile: RenderProfile | Mapping[str, Any] | None = None,
    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
    metadata: Mapping[str, str] | None = None,
    sidecar_path: str | Path | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    transport: Any = None,
    transport_factory: Any = None,
    validator: Any = None,
    materialized_root: str | Path | None = None,
    materialized_objects: Mapping[str, str] | None = None,
) -> Path:
    """Reject the retired direct render convenience path.

    Rendering is a product operation, so admission, materialization, leases,
    and settlement must come from ``sdk.invoke`` and the neutral generic host.
    The protocol-only ``renderer_main`` entrypoint below remains available to
    a host-launched renderer backend; it is not a second product execution
    route.
    """

    del (
        timeline_path,
        output_name,
        assets_registry_path,
        out_path,
        selector,
        window,
        audio,
        profile,
        backend_config,
        metadata,
        sidecar_path,
        project_root,
        extra_pack_roots,
        transport,
        transport_factory,
        validator,
        materialized_root,
        materialized_objects,
    )
    from astrid.sdk.exceptions import UnsupportedCapabilityError

    raise UnsupportedCapabilityError(
        "direct SDK rendering is retired; admit rendering.render through "
        "sdk.invoke(..., kind='executor', project=...)"
    )


# ---------------------------------------------------------------------------
# support — public convenience
# ---------------------------------------------------------------------------


def support(
    backend: str,
    *,
    request: RenderRequest | Mapping[str, Any] | None = None,
    timeline_path: str | Path | None = None,
    output_name: str | None = None,
    assets_registry_path: str | Path | None = None,
    window: FrameWindow | Mapping[str, Any] | None = None,
    audio: AudioOwnership | str | None = None,
    profile: RenderProfile | Mapping[str, Any] | None = None,
    backend_config: Mapping[str, Mapping[str, Any]] | None = None,
    metadata: Mapping[str, str] | None = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
    service: Any = None,
    registries: Any = None,
    transport: Any = None,
    transport_factory: Any = None,
    materialized_root: str | Path | None = None,
    materialized_objects: Mapping[str, str] | None = None,
) -> SupportReport:
    """Resolve the qualified *backend* and return its :class:`SupportReport`.

    Accepts either a frozen ``request`` (a :class:`RenderRequest` or a v1
    wire mapping) or friendly path/audio/profile arguments.  The backend is
    resolved through the rendering registry and the support verb is dispatched
    through the shared :class:`RenderService` (injectable via ``service``),
    so the returned report is exactly what the public backend path produces.
    """
    if request is None:
        if timeline_path is None:
            raise ValueError("request or timeline_path is required")
        request = RenderRequest(
            schema_version=SCHEMA_VERSION,
            timeline_path=str(Path(timeline_path).expanduser().resolve()),
            assets_registry_path=(
                None
                if assets_registry_path is None
                else str(Path(assets_registry_path).expanduser().resolve())
            ),
            output_name=output_name or _SUPPORT_DEFAULT_OUTPUT_NAME,
            window=window,
            audio=(audio.value if isinstance(audio, AudioOwnership) else audio),
            profile=profile,
            backend_config=_json_safe(dict(backend_config or {})),
            metadata=_json_safe(dict(metadata or {})),
            materialized_root=(None if materialized_root is None else str(Path(materialized_root).expanduser().resolve())),
            materialized_objects=_json_safe(dict(materialized_objects or {})),
        )
    parsed = (
        request if isinstance(request, RenderRequest) else RenderRequest.from_dict(request)
    )
    # The invocation workspace is the timeline's directory — the same
    # convention raw backends use (the request file's parent).  Sibling
    # assets resolve relative to it.
    workspace = Path(parsed.timeline_path).expanduser().resolve().parent
    return _support_report(
        parsed,
        backend=backend,
        service=service,
        registries=registries,
        transport=transport,
        transport_factory=transport_factory,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        workspace=workspace,
    )


# ---------------------------------------------------------------------------
# Shared dispatch helpers
# ---------------------------------------------------------------------------


def _support_report(
    request: RenderRequest,
    *,
    backend: str | None = None,
    workspace: Path | None = None,
    service: Any = None,
    registries: Any = None,
    transport: Any = None,
    transport_factory: Any = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
) -> SupportReport:
    """Resolve *backend* and dispatch its support verb via the service.

    When *backend* is omitted it is resolved from the request exactly like
    the render dispatch (transport-selected environment variable, then the
    request's ``backend_config`` namespace).
    """
    selected_backend = _resolve_backend(request, explicit=backend)
    resolved_registries = _resolve_registries(
        registries=registries,
        service=service,
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
    )
    renderers, _planners, _finalizers = resolved_registries
    candidate = _resolve_candidate(renderers, selected_backend)
    if workspace is None:
        raise ValueError("support requires an invocation workspace")
    projected = request.for_backend(candidate.id)
    from astrid.core.foundation.atomic_io import write_json_atomic
    from astrid.core.rendering.errors import raise_protocol_error
    from astrid.core.rendering.transport import CommandTransport

    # Support is a read-only protocol probe.  Run the backend in a disposable
    # child process directly, without constructing a product render service or
    # opening any local storage authority.
    with tempfile.TemporaryDirectory(
        prefix="astrid-render-support-", dir=str(workspace)
    ) as support_root:
        support_workspace = Path(support_root)
        request_path = support_workspace / "support-request.json"
        result_path = support_workspace / "support-result.json"
        write_json_atomic(request_path, projected.to_dict())
        selected_transport = transport or (transport_factory or CommandTransport)(
            candidate.id
        )
        response = selected_transport.run(
            "support",
            candidate.manifest.command,
            backend=candidate.id,
            request_path=request_path,
            result_path=result_path,
            cwd=candidate.pack_root,
            timeout=candidate.manifest.timeout_seconds,
            required_binaries=(),
        )
    if not isinstance(response, SupportReport):
        raise_protocol_error(
            backend=candidate.id,
            message="support operation did not return a SupportReport",
            details={"received_type": type(response).__name__},
        )
    if response.backend != candidate.id:
        raise_protocol_error(
            backend=candidate.id,
            message="support report names a different backend",
            details={"reported_backend": response.backend},
        )
    if response.backend_version != candidate.manifest.version:
        raise_protocol_error(
            backend=candidate.id,
            message="support report version does not match its manifest",
            recovery_command="update the backend command and manifest as one versioned unit",
            details={
                "reported_version": response.backend_version,
                "manifest_version": candidate.manifest.version,
            },
        )
    return response


def _resolve_registries(
    *,
    registries: Any = None,
    service: Any = None,
    project_root: str | Path | None = None,
    extra_pack_roots: tuple[str, ...] = (),
) -> Any:
    """Return ``(renderers, planners, finalizers)`` registries lazily.

    When no registries/service are injected, the owning pack root is added as
    an explicit extra pack root: the command transport executes manifest
    commands from the owning pack's root, and that pack must be
    execution-eligible (the same trust an explicit ``extra_pack_roots`` entry
    grants).  ``ASTRID_PACKS_PATH``-discovered packs alone are inspectable but
    not executable.
    """
    if registries is not None:
        return registries
    if service is not None:
        return (service.renderers, service.planners, service.finalizers)
    from astrid.core.rendering.registry import load_default_registries

    return load_default_registries(
        project_root,
        extra_pack_roots=(*extra_pack_roots, *_owning_pack_roots()),
    )


_PACK_MANIFEST_NAMES = ("pack.yaml", "pack.yml", "pack.json")


def _owning_pack_roots() -> tuple[str, ...]:
    """Return the owning pack collection root when the process runs from a
    pack root (the command-transport convention for manifest commands)."""
    cwd = Path.cwd().resolve()
    if any((cwd / name).is_file() for name in _PACK_MANIFEST_NAMES):
        return (str(cwd.parent),)
    return ()


def _resolve_candidate(renderers: Any, backend: str) -> Any:
    """Resolve a renderer candidate, mapping registry failures to the frozen
    unsupported error kind (mirroring :class:`RenderService`)."""
    from astrid.core.rendering.errors import raise_unsupported_error
    from astrid.core.rendering.registry import RenderingRegistryError

    try:
        return renderers.get(backend)
    except RenderingRegistryError as exc:
        raise_unsupported_error(
            backend=backend,
            message=str(exc),
            recovery_command=(
                "select an execution-eligible renderer and retry"
            ),
            details=dict(getattr(exc, "details", {}) or {}),
        )


def _resolve_backend(request: RenderRequest, *, explicit: str | None = None) -> str:
    """Select the qualified backend for a raw-command dispatch.

    Precedence: the transport-selected ``ASTRID_RENDER_BACKEND`` environment
    variable (authoritative when this entrypoint runs as a manifest command),
    then an explicit argument, then the request's ``backend_config``
    namespace — exactly one.  Never guesses from timeline shape.
    """
    if explicit is not None:
        return _require_qualified_id(explicit, "backend")
    env_backend = os.environ.get(_TRANSPORT_BACKEND_ENV)
    if env_backend:
        return _require_qualified_id(env_backend, _TRANSPORT_BACKEND_ENV)
    namespaces = [str(key) for key in request.backend_config]
    qualified = [key for key in namespaces if _is_qualified_id(key)]
    if not qualified:
        raise ValueError(
            "render request does not select a qualified backend; set "
            f"{_TRANSPORT_BACKEND_ENV}, or include a backend_config namespace"
        )
    if len(qualified) > 1:
        raise ValueError(
            "render request selects multiple backends; select exactly one "
            "backend_config namespace"
        )
    return qualified[0]


def _is_qualified_id(value: str) -> bool:
    try:
        _require_qualified_id(value, "backend")
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------------------
# RenderContext — convenience facade for third-party render.py authors
# ---------------------------------------------------------------------------

_MAX_CAPTURE_CHARS = 64 * 1024
_OUTPUTS_DIR_NAME = "outputs"
_TEMP_ROOT_NAME = ".astrid-tmp"
_ATTACHMENTS_DIR_NAME = "attachments"
_OUTPUT_NAME_RE = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
_TRUNCATED_MARKER = "\n[truncated]"


@dataclass(frozen=True)
class SubprocessResult:
    """Bounded, redacted result of one sanitized subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str


class RenderContext:
    """Per-invocation convenience facade for third-party renderer code.

    A ``render.py`` receives one :class:`RenderContext` for the lifetime of a
    render invocation.  It allocates workspace-validated output and scratch
    paths, resolves object-id/digest registry entries to host-staged files and
    a derived invocation asset server URL, checks permissions, runs sanitized
    subprocesses, emits redacted logs, exposes a cooperative interruption
    flag, probes media, hashes inputs, completes audio through the core
    helper, carries named attachments, and cleans up on exit.

    RenderContext is not an OS sandbox; it enforces workspace conventions, not
    process isolation.

    Everything here delegates to the canonical core primitives — the
    :class:`~astrid.core.rendering.assets.AssetMaterializer` and
    :class:`~astrid.core.rendering.assets.InvocationAssetServer`,
    :func:`astrid.core.subprocess_env.build_child_subprocess_env`, the
    transport log scrubbers, :func:`astrid.core.media.ffprobe_metadata_strict`,
    :func:`astrid.core.foundation.hash.sha256_file`,
    :class:`~astrid.core.rendering.service.RenderService.complete_audio`, and
    the frozen :class:`~astrid.core.rendering.contracts.Attachment` contract.
    It introduces no new security boundary.
    """

    def __init__(
        self,
        workspace: str | Path,
        *,
        backend: str = _CORE_BACKEND_ID,
        allowed_roots: Sequence[str | Path] = (),
        materializer: Any = None,
        asset_server: Any = None,
        interrupt_check: Callable[[], bool] | None = None,
        service: Any = None,
        audio_completer: Callable[..., Any] | None = None,
        secret_values: Sequence[str] = (),
    ) -> None:
        """Bind *workspace* as the invocation root for this render.

        ``allowed_roots`` are additional directories (outside the workspace)
        the renderer may read or write; every other path must resolve inside
        the workspace.  ``materializer``/``asset_server`` are the invocation's
        :class:`AssetMaterializer` and :class:`InvocationAssetServer` when the
        host materialized assets.  ``interrupt_check`` is a cooperative cancel
        flag polled by :meth:`raise_if_interrupted`.  ``service`` (a
        :class:`~astrid.core.rendering.service.RenderService`) or
        ``audio_completer`` provides the core ``complete_audio`` helper, and
        ``secret_values`` are additional values scrubbed from logs on top of
        secret-named environment variables.
        """
        _require_qualified_id(backend, "backend")
        self.backend = backend
        self.workspace = Path(workspace).expanduser().resolve(strict=False)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.allowed_roots = tuple(
            Path(root).expanduser().resolve(strict=False) for root in allowed_roots
        )
        self._materializer = materializer
        self._asset_server = asset_server
        self._owns_materializer = materializer is None
        self._owns_asset_server = asset_server is None
        self._interrupt_check = interrupt_check
        self._service = service
        self._child_process: subprocess.Popen[str] | None = None
        self._audio_completer = audio_completer
        self._explicit_secret_values = tuple(str(value) for value in secret_values)
        self._temp_dirs: list[Path] = []
        self._temp_files: list[Path] = []
        self._attachments: dict[str, Any] = {}
        self.logs: list[str] = []
        self._closed = False

    # ------------------------------------------------------------------
    # Paths — allocated and validated workspace-relative
    # ------------------------------------------------------------------

    @property
    def outputs_dir(self) -> Path:
        """The canonical ``outputs/`` directory inside the workspace."""
        return self.workspace / _OUTPUTS_DIR_NAME

    def workspace_path(self, relative: str | os.PathLike[str]) -> Path:
        """Allocate and return an absolute path inside the workspace.

        *relative* must be a normalized workspace-relative path (no absolute
        prefix, no ``..``, no backslashes, no empty or NUL components).  The
        parent directories are created and the resolved absolute path is
        returned.
        """
        path = self._validate_workspace_relative(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def output_path(self, name: str) -> Path:
        """Allocate and return ``outputs/<name>`` for a render artifact.

        *name* must be a single portable basename (letters, digits, ``.``,
        ``_``, ``-``); subdirectories are not allowed here.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("output name must be a non-empty string")
        if len(name) > 255 or re.match(_OUTPUT_NAME_RE, name) is None:
            raise ValueError(
                "output name must be a portable basename using letters, digits, "
                "'.', '_', or '-'"
            )
        return self.workspace_path(f"{_OUTPUTS_DIR_NAME}/{name}")

    def temp_dir(self, prefix: str = "astrid-tmp-") -> Path:
        """Allocate a scratch directory inside the workspace.

        The directory is removed by :meth:`cleanup` (and therefore by the
        context manager) even when the render body raises.
        """
        if self._closed:
            raise RuntimeError("RenderContext is closed")
        if not isinstance(prefix, str) or not prefix:
            raise ValueError("temp dir prefix must be a non-empty string")
        root = self.workspace / _TEMP_ROOT_NAME
        root.mkdir(parents=True, exist_ok=True)
        candidate = root / f"{prefix}{uuid.uuid4().hex}"
        candidate.mkdir()
        self._temp_dirs.append(candidate)
        return candidate

    def _validate_workspace_relative(self, relative: str | os.PathLike[str]) -> Path:
        raw = os.fspath(relative)
        if not isinstance(raw, str) or not raw:
            raise ValueError("workspace path must be a non-empty string")
        if "\x00" in raw or "\\" in raw:
            raise ValueError(
                "workspace path must be normalized with forward slashes and no NUL"
            )
        normalized = raw.replace("\\", "/")
        if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
            raise ValueError("workspace path must be relative to the invocation workspace")
        parts = normalized.split("/")
        if any(part in {"", ".", ".."} for part in parts):
            raise ValueError("workspace path must not contain empty, '.', or '..' components")
        return (self.workspace / normalized).resolve()

    # ------------------------------------------------------------------
    # Permissions — reject paths outside the workspace unless allowed
    # ------------------------------------------------------------------

    def check_path(self, path: str | os.PathLike[str]) -> Path:
        """Resolve *path* and require it inside the workspace or an allowed root.

        Returns the resolved absolute path.  Raises :class:`ValueError` when
        the path escapes the workspace and no explicitly allowed root contains
        it.  This is a workspace-convention check, not an OS sandbox.
        """
        resolved = Path(path).expanduser().resolve(strict=False)
        if self._contained(resolved, self.workspace):
            return resolved
        for root in self.allowed_roots:
            if self._contained(resolved, root):
                return resolved
        raise ValueError(
            f"path {resolved} is outside the invocation workspace {self.workspace} "
            "and not covered by an explicitly allowed root"
        )

    @staticmethod
    def _contained(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
        except ValueError:
            return False
        return True

    # ------------------------------------------------------------------
    # Assets — registry entries to absolute files or server URLs
    # ------------------------------------------------------------------

    def _require_materializer(self) -> Any:
        if self._materializer is None:
            raise ValueError(
                "no asset materializer is bound to this RenderContext; the host "
                "must provide one to resolve asset descriptors"
            )
        return self._materializer

    def _require_asset(self, key: str) -> Any:
        materializer = self._require_materializer()
        try:
            return materializer.assets[key]
        except KeyError as exc:
            raise ValueError(f"unknown asset key: {key!r}") from exc

    def asset_path(self, key: str) -> Path:
        """Return the absolute staged file for registry asset *key*."""
        asset = self._require_asset(key)
        if asset.local_path is None:
            raise ValueError(f"asset {key!r} is not materialized to a local file")
        return Path(asset.local_path).resolve(strict=True)

    def asset_url(self, key: str) -> str:
        """Return the consumable URL for registry asset *key*.

        Live registries never carry remote URLs. Host-materialized assets are
        served from the invocation asset server.
        """
        asset = self._require_asset(key)
        server = self._asset_server
        if server is None:
            raise ValueError(
                "no invocation asset server is bound to this RenderContext; "
                "local asset URLs are unavailable"
            )
        if asset.local_path is None:
            raise ValueError(f"asset {key!r} has no local path to serve")
        return server.local_url(asset.local_path)

    def resolved_registry(self) -> dict[str, Any]:
        """Return the cloned asset registry with consumable ``file`` values."""
        materializer = self._require_materializer()
        return materializer.resolved_registry(self._asset_server)

    # ------------------------------------------------------------------
    # Sanitized subprocess runner
    # ------------------------------------------------------------------

    def run(
        self,
        argv: Sequence[str | os.PathLike[str]],
        *,
        timeout: float | None = None,
        env: Mapping[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        check: bool = True,
        passthrough: Sequence[str] = (),
    ) -> SubprocessResult:
        """Run *argv* with a scrubbed environment and bounded, redacted output.

        The command is always executed without a shell (``shell=False``) from
        an argv sequence.  The child environment is built by
        :func:`astrid.core.subprocess_env.build_child_subprocess_env`, so only
        known-safe base variables, Astrid invariants, ``env`` entries, and
        declared ``passthrough`` names reach the child — secret-named host
        variables never do.  Captured stdout/stderr are truncated to 64 KiB
        and scrubbed of secret values.  ``timeout`` enforces a hard deadline
        and raises the frozen ``timeout`` renderer error.  With ``check=True``
        (the default) a non-zero exit raises the frozen ``internal`` renderer
        error carrying the redacted output.  A ``KeyboardInterrupt``
        terminates the child and re-raises with the frozen ``interrupted``
        error attached.
        """
        from astrid.core.rendering.errors import (
            make_renderer_error,
            raise_internal_error,
            raise_timeout_error,
        )
        from astrid.core.subprocess_env import build_child_subprocess_env

        if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
            raise TypeError("command must be a non-empty argv sequence")
        command: list[str] = []
        for index, value in enumerate(argv):
            if not isinstance(value, (str, os.PathLike)):
                raise TypeError(f"command argument {index} must be a path string")
            item = os.fspath(value)
            if not item or "\x00" in item:
                raise ValueError(
                    f"command argument {index} must be non-empty and contain no NUL"
                )
            command.append(item)
        if not command:
            raise ValueError("command must contain at least one argument")

        selected_cwd = self.workspace if cwd is None else self.check_path(cwd)
        child_env = build_child_subprocess_env(
            base=dict(os.environ),
            parent=dict(os.environ),
            explicit_env=env,
            passthrough=tuple(passthrough),
            declared_passthrough=tuple(passthrough),
        )
        try:
            process = subprocess.Popen(
                command,
                shell=False,
                cwd=str(selected_cwd),
                env=child_env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                # Own process group so teardown can reach grandchildren that
                # keep the pipes open (typical FFmpeg pattern); a bare
                # process.kill() would leave them holding stdout/stderr and
                # communicate() would hang forever.
                start_new_session=True,
            )
        except OSError as exc:
            raise_internal_error(
                backend=self.backend,
                message=f"failed to start renderer subprocess {command[0]!r}: {exc}",
                details={"error_type": type(exc).__name__},
            )

        self._child_process = process

        stdout: str = ""
        stderr: str = ""
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if isinstance(exc.output, str):
                stdout = exc.output
            if isinstance(exc.stderr, str):
                stderr = exc.stderr
            self._kill_process_group(process)
            logs = self._bounded_logs(stdout, stderr, overlay=env)
            raise_timeout_error(
                backend=self.backend,
                message=f"renderer subprocess timed out after {timeout:g} seconds",
                details={
                    "timeout_seconds": timeout,
                    "returncode": process.returncode,
                    **logs,
                },
            )
        except KeyboardInterrupt:
            self._kill_process_group(process)
            logs = self._bounded_logs(stdout, stderr, overlay=env)
            error = make_renderer_error(
                "interrupted",
                backend=self.backend,
                message="renderer subprocess was interrupted",
                details={"returncode": process.returncode, **logs},
            )
            exc = KeyboardInterrupt("renderer subprocess was interrupted")
            exc.renderer_error = error  # type: ignore[attr-defined]
            exc.error = error  # type: ignore[attr-defined]
            raise exc

        result = SubprocessResult(
            returncode=process.returncode,
            stdout=self.redact(stdout),
            stderr=self.redact(stderr),
        )
        if check and process.returncode != 0:
            raise_internal_error(
                backend=self.backend,
                message=f"renderer subprocess exited with status {process.returncode}",
                details={
                    "returncode": process.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
            )
        return result

    @staticmethod
    def _kill_process_group(process: subprocess.Popen[str]) -> None:
        """SIGKILL the child's whole process group and reap it bounded.

        ``start_new_session=True`` makes the child's PID its process-group
        ID; killing the group reaches grandchildren that keep the pipes open
        (typical FFmpeg pattern), so the subsequent bounded communicate()
        cannot hang.  Mirrors ``astrid.core.rendering.transport``.
        """
        import signal

        if hasattr(os, "killpg"):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except (PermissionError, OSError):
                try:
                    process.kill()
                except OSError:
                    pass
        else:
            try:
                process.kill()
            except OSError:
                pass
        with contextlib.suppress(Exception):
            process.communicate(timeout=5)

    def _bounded_logs(
        self,
        stdout: str,
        stderr: str,
        *,
        overlay: Mapping[str, str] | None,
    ) -> dict[str, str]:
        return {
            "stdout": self._bounded(self.redact(stdout, overlay=overlay)),
            "stderr": self._bounded(self.redact(stderr, overlay=overlay)),
        }

    @staticmethod
    def _bounded(value: str) -> str:
        if len(value) > _MAX_CAPTURE_CHARS:
            return value[:_MAX_CAPTURE_CHARS] + _TRUNCATED_MARKER
        return value

    # ------------------------------------------------------------------
    # Redacted logs / progress
    # ------------------------------------------------------------------

    def _secret_values(self, overlay: Mapping[str, str] | None) -> tuple[str, ...]:
        from astrid.core.rendering.transport import _secret_environment_values

        host_values = _secret_environment_values(os.environ, overlay)
        return tuple(
            sorted(
                {*host_values, *self._explicit_secret_values},
                key=len,
                reverse=True,
            )
        )

    def redact(self, text: str, *, overlay: Mapping[str, str] | None = None) -> str:
        """Scrub secret values and registry tokens from *text*."""
        from astrid.core.rendering.transport import _redact_log

        return _redact_log(text or "", secret_values=self._secret_values(overlay))

    def log(self, message: str) -> None:
        """Append *message* to ``logs`` with secret values scrubbed."""
        self.logs.append(self.redact(message))

    def progress(self, message: str) -> None:
        """Emit a redacted progress line, recorded in ``logs``."""
        self.log(message)

    # ------------------------------------------------------------------
    # Interruption state
    # ------------------------------------------------------------------

    @property
    def interrupt_requested(self) -> bool:
        """Whether the cooperative cancel flag is currently set."""
        if self._interrupt_check is None:
            return False
        return bool(self._interrupt_check())

    def raise_if_interrupted(self) -> None:
        """Raise the frozen ``interrupted`` renderer error when cancelled.

        Renderers should call this between long-running steps so the host can
        stop a render cooperatively.
        """
        if self.interrupt_requested:
            from astrid.core.rendering.errors import raise_interrupted_error

            raise_interrupted_error(
                backend=self.backend,
                message="render was interrupted by the host",
            )

    # ------------------------------------------------------------------
    # Media probing, hashing, audio completion, attachments
    # ------------------------------------------------------------------

    def probe_media(self, path: str | os.PathLike[str]) -> Any:
        """Probe *path* with :func:`astrid.core.media.ffprobe_metadata_strict`.

        Raises :class:`~astrid.core.media.MediaProbeError` when ffprobe is
        unavailable or the metadata is invalid.
        """
        from astrid.core.media import ffprobe_metadata_strict

        return ffprobe_metadata_strict(path)

    def sha256(self, path: str | os.PathLike[str]) -> str:
        """Return the SHA-256 hex digest of *path* (1 MB chunked reads)."""
        return sha256_file(Path(path))

    def complete_audio(
        self,
        result: RenderResult,
        *,
        request: RenderRequest,
        plan: Any = None,
        workspace: str | os.PathLike[str] | None = None,
        backend: str | None = None,
        defer_to_finalizer: bool = False,
    ) -> RenderResult:
        """Complete audio through the core ``complete_audio`` helper.

        Delegates to the bound :class:`RenderService` (``service``) or the
        injected ``audio_completer`` callable exactly like
        :class:`~astrid.core.rendering.service.RenderService.complete_audio`
        does, so the frozen audio/attachment preservation contract applies.
        Raises the frozen ``unsupported`` renderer error when no completer is
        configured.
        """
        selected_backend = backend or self.backend
        selected_workspace = self.workspace if workspace is None else self.check_path(workspace)
        if self._audio_completer is not None:
            return self._audio_completer(
                result,
                request=request,
                plan=plan,
                workspace=selected_workspace,
            )
        if self._service is not None:
            return self._service.complete_audio(
                result,
                request=request,
                plan=plan,
                workspace=selected_workspace,
                backend=selected_backend,
                defer_to_finalizer=defer_to_finalizer,
            )
        from astrid.core.rendering.errors import raise_unsupported_error

        raise_unsupported_error(
            backend=selected_backend,
            message=(
                "no audio completer is configured for this RenderContext; bind "
                "a RenderService or an audio_completer to complete audio"
            ),
            details={"audio_ownership": result.audio_ownership.value},
        )

    def add_attachment(
        self,
        name: str,
        payload: bytes,
        *,
        kind: str = "attachment",
    ) -> Any:
        """Write *payload* as a named attachment validated by the frozen contract.

        The bytes are stored under ``attachments/<name>`` inside the workspace
        and returned as a frozen
        :class:`~astrid.core.rendering.contracts.Attachment` (portable
        basename, lowercase-hyphenated kind, workspace-relative path, and
        SHA-256 are all validated by the contract).
        """
        if not isinstance(payload, bytes):
            raise TypeError("attachment payload must be bytes")
        if not isinstance(name, str) or not name:
            raise ValueError("attachment name must be a non-empty string")
        if re.fullmatch(_OUTPUT_NAME_RE, name) is None:
            raise ValueError(
                "attachment name must be a portable basename using letters, "
                "digits, '.', '_', or '-'"
            )
        directory = self.workspace / _ATTACHMENTS_DIR_NAME
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_bytes(payload)
        attachment = self._attachment_from_file(name=name, path=path, kind=kind)
        self._attachments[attachment.name] = attachment
        return attachment

    def _attachment_from_file(self, *, name: str, path: Path, kind: str) -> Any:
        from astrid.core.rendering.contracts import Attachment

        return Attachment.from_file(
            name=name,
            path=path,
            kind=kind,
            workspace_root=self.workspace,
        )

    @property
    def attachments(self) -> dict[str, Any]:
        """Named attachments added via :meth:`add_attachment`."""
        return dict(self._attachments)

    # ------------------------------------------------------------------
    # Cleanup — context manager, crash-safe
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Remove temp artifacts and close owned resources.

        Best-effort: temp directories and files created by this context are
        removed, and the materializer/asset server are closed only when this
        context created them.  Errors are collected and reported rather than
        masking the render outcome.
        """
        if self._closed:
            return
        # Reap any subprocess still owned by this context so __exit__ cannot
        # leave a zombie or a pipe-holding grandchild behind.
        child = self._child_process
        if child is not None and child.poll() is None:
            try:
                child.kill()
            except OSError:
                pass
            with contextlib.suppress(Exception):
                child.communicate(timeout=5)
        errors: list[BaseException] = []
        for directory in self._temp_dirs:
            try:
                shutil.rmtree(directory)
            except FileNotFoundError:
                pass
            except BaseException as exc:  # pragma: no cover - defensive
                errors.append(exc)
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except BaseException as exc:  # pragma: no cover - defensive
                errors.append(exc)
        # Remove the now-empty temp root so a completed invocation leaves no
        # scratch residue; rmdir only succeeds when the directory is empty.
        with contextlib.suppress(OSError):
            (self.workspace / _TEMP_ROOT_NAME).rmdir()
        if self._owns_materializer and self._materializer is not None:
            try:
                self._materializer.close()
            except BaseException as exc:  # pragma: no cover - defensive
                errors.append(exc)
        if self._owns_asset_server and self._asset_server is not None:
            try:
                self._asset_server.close()
            except BaseException as exc:  # pragma: no cover - defensive
                errors.append(exc)
        self._temp_dirs.clear()
        self._temp_files.clear()
        self._closed = True
        if errors:
            raise RuntimeError(
                "RenderContext cleanup failed: "
                + "; ".join(str(error) for error in errors)
            )

    def __enter__(self) -> "RenderContext":
        if self._closed:
            raise RuntimeError("RenderContext is closed")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        with contextlib.suppress(Exception):
            self.cleanup()


__all__ = ["RenderContext", "render", "renderer_main", "support"]
