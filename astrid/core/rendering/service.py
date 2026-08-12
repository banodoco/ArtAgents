"""Backend-neutral orchestration for one committed timeline render.

``RenderService`` is the only core component that understands the legacy
renderer selector spellings.  Everything after that compatibility boundary is
resolved through the rendering registries and invoked through protocol v1.
Backends write private artifacts in an invocation workspace; the service
validates them and performs exactly one locked publication at the end.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import warnings
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal

from astrid.core.foundation.atomic_io import write_json_atomic
from astrid.core.foundation.hash import sha256_file

from .artifacts import validate_render_result
from .contracts import (
    SCHEMA_VERSION,
    AudioOwnership,
    FinalizeRequest,
    FinalizerResolution,
    FrameWindow,
    PlannerResolution,
    RenderPlan,
    RenderRequest,
    RenderResult,
    RendererResolution,
    RenderSegment,
    SupportReport,
    compute_request_digest,
)
from .errors import (
    RendererException,
    raise_internal_error,
    raise_invalid_artifact_error,
    raise_protocol_error,
    raise_renderer_error,
    raise_unsupported_error,
)
from .provenance import assemble_provenance_v2
from .publication import publish_render_result
from .registry import (
    FinalizerRegistry,
    PlannerRegistry,
    RendererRegistry,
    RenderingCandidate,
    RenderingRegistryError,
    load_default_registries,
)
from .transport import CommandTransport


_QUALIFIED_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9_-]*(?:\.[a-z0-9][a-z0-9_-]*)+$"
)
_CORE_BACKEND_ID = "astrid.core"
_DIRECT_PLANNER_ID = "astrid.direct"
_DIRECT_PLANNER_DIGEST = hashlib.sha256(b"astrid.direct/v1").hexdigest()
_DIRECT_FINALIZER_ID = "astrid.direct-finalizer"
_DIRECT_FINALIZER_DIGEST = hashlib.sha256(
    b"astrid.direct-finalizer/v1"
).hexdigest()

CapabilityKind = Literal["renderer", "planner", "finalizer"]
StageObserver = Callable[[str, Mapping[str, Any]], None]
AudioCompleter = Callable[..., RenderResult]


class LegacyRenderRoutingWarning(UserWarning):
    """A legacy selector selected a different qualified backend."""


@dataclass(frozen=True)
class _SelectionPolicy:
    requested: str
    kind: Literal["renderer", "planner"]
    targets: tuple[str, ...]
    auto_route: bool = False


@dataclass(frozen=True)
class _ResolvedCapability:
    candidate: RenderingCandidate[Any]
    evidence: dict[str, Any]
    support: SupportReport
    rejected: list[dict[str, Any]] = field(default_factory=list)


def _translate_legacy_selector(selector: str | None) -> _SelectionPolicy:
    """Translate the three historical names, and no other short names.

    The ordered pair for legacy ``remotion`` is its characterized compatibility
    policy: request-sensitive FFmpeg support gets the first opportunity, then
    Remotion.  Qualified selectors contain no fallback and are therefore
    strict (normal registry aliases and overrides still apply).
    """

    if selector is None:
        selector = "remotion"
    if selector == "ffmpeg":
        return _SelectionPolicy(selector, "renderer", ("rendering.ffmpeg",))
    if selector == "remotion":
        return _SelectionPolicy(
            selector,
            "renderer",
            ("rendering.ffmpeg", "rendering.remotion"),
            auto_route=True,
        )
    if selector == "hybrid":
        return _SelectionPolicy(
            selector,
            "planner",
            ("rendering.legacy_hybrid",),
        )
    if isinstance(selector, str) and _QUALIFIED_ID_RE.fullmatch(selector):
        return _SelectionPolicy(selector, "renderer", (selector,))
    raise_unsupported_error(
        backend=_CORE_BACKEND_ID,
        message=f"unknown renderer selector {selector!r}",
        recovery_command=(
            "select a qualified renderer id or one of the legacy selectors: "
            "remotion, ffmpeg, hybrid"
        ),
        details={
            "selector": selector if isinstance(selector, str) else repr(selector),
            "legacy_selectors": ["remotion", "ffmpeg", "hybrid"],
        },
    )


class RenderService:
    """Resolve, invoke, validate, finalize, and publish one timeline render.

    Registries and lifecycle functions are injectable so callers can embed the
    service without importing backend code, and so the orchestration order can
    be tested without spawning media tools.
    """

    def __init__(
        self,
        renderer_registry: RendererRegistry | None = None,
        planner_registry: PlannerRegistry | None = None,
        finalizer_registry: FinalizerRegistry | None = None,
        *,
        registries: tuple[
            RendererRegistry, PlannerRegistry, FinalizerRegistry
        ]
        | None = None,
        project_root: str | Path | None = None,
        extra_pack_roots: tuple[str, ...] = (),
        include_installed: bool = True,
        transport: Any | None = None,
        transport_factory: Callable[[str], Any] = CommandTransport,
        validator: Callable[..., RenderResult] = validate_render_result,
        publisher: Callable[..., Path] = publish_render_result,
        provenance_builder: Callable[..., dict[str, Any]] = assemble_provenance_v2,
        audio_completer: AudioCompleter | None = None,
        stage_observer: StageObserver | None = None,
        finalizer_id: str | None = None,
    ) -> None:
        supplied = (
            renderer_registry,
            planner_registry,
            finalizer_registry,
        )
        if registries is not None and any(item is not None for item in supplied):
            raise ValueError(
                "pass either registries= or individual rendering registries, not both"
            )
        if registries is None:
            if all(item is None for item in supplied):
                registries = load_default_registries(
                    project_root,
                    extra_pack_roots=extra_pack_roots,
                    include_installed=include_installed,
                )
            elif any(item is None for item in supplied):
                raise ValueError("all three rendering registries must be supplied together")
            else:
                registries = supplied  # type: ignore[assignment]
        self.renderers, self.planners, self.finalizers = registries
        self.renderer_registry = self.renderers
        self.planner_registry = self.planners
        self.finalizer_registry = self.finalizers
        self._transport = transport
        self._transport_factory = transport_factory
        self._validator = validator
        self._publisher = publisher
        self._provenance_builder = provenance_builder
        self._audio_completer = audio_completer
        self._stage_observer = stage_observer
        # Direct renders need no executable finalizer.  An embedding host may
        # nevertheless request a registered finalizer identity for direct-plan
        # provenance; otherwise a core no-op resolution is recorded.  Planned
        # renders always use the finalizer pinned by their RenderPlan.
        self.finalizer_id = finalizer_id

    def render(
        self,
        request: RenderRequest | Mapping[str, Any] | str | Path,
        assets_path: str | Path | None = None,
        out_path: str | Path | None = None,
        *,
        selector: str | None = None,
        engine: str | None = None,
        backend: str | None = None,
        output_path: str | Path | None = None,
        sidecar_path: str | Path | None = None,
        backend_config: Mapping[str, Mapping[str, Any]] | None = None,
        audio: AudioOwnership | str | None = None,
        metadata: Mapping[str, str] | None = None,
        previous_outputs: Iterable[object] = (),
        v1_compatibility: Mapping[str, Any] | None = None,
    ) -> Path:
        """Render either a wire request or a timeline/assets path pair.

        For a wire request, the second positional argument may be the output
        path.  The path-pair form is a compatibility convenience used by the
        facade while it migrates to constructing :class:`RenderRequest`
        directly.
        """

        selected = self._one_selector(selector, engine, backend)
        destination = output_path or out_path
        if isinstance(request, (RenderRequest, Mapping)):
            if destination is None and assets_path is not None:
                destination = assets_path
                assets_path = None
            parsed = (
                request
                if isinstance(request, RenderRequest)
                else RenderRequest.from_dict(request)
            )
        else:
            if destination is None:
                raise_protocol_error(
                    backend=_CORE_BACKEND_ID,
                    message="out_path/output_path is required",
                    recovery_command="supply one output path and retry",
                )
            destination_path = Path(destination)
            parsed = RenderRequest.from_dict(
                {
                    "schema_version": SCHEMA_VERSION,
                    "timeline_path": str(Path(request).expanduser().resolve()),
                    "assets_registry_path": (
                        None
                        if assets_path is None
                        else str(Path(assets_path).expanduser().resolve())
                    ),
                    "output_name": destination_path.name,
                    "window": None,
                    "audio": (
                        audio.value if isinstance(audio, AudioOwnership) else audio
                    ),
                    "profile": None,
                    "backend_config": {
                        str(key): dict(value)
                        for key, value in (backend_config or {}).items()
                    },
                    "metadata": dict(metadata or {}),
                }
            )
        if destination is None:
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message="out_path/output_path is required",
                recovery_command="supply one output path and retry",
            )
        return self.render_request(
            parsed,
            selector=selected,
            out_path=destination,
            sidecar_path=sidecar_path,
            previous_outputs=previous_outputs,
            v1_compatibility=v1_compatibility,
        )

    def render_request(
        self,
        request: RenderRequest | Mapping[str, Any],
        *,
        selector: str | None = None,
        out_path: str | Path,
        sidecar_path: str | Path | None = None,
        previous_outputs: Iterable[object] = (),
        v1_compatibility: Mapping[str, Any] | None = None,
    ) -> Path:
        """Execute the frozen selection lifecycle for one protocol request."""

        try:
            parsed = (
                request
                if isinstance(request, RenderRequest)
                else RenderRequest.from_dict(request)
            )
            localized = self._absolute_input_paths(parsed)
            # Keep the caller's absolute-but-unresolved spellings for the
            # publication layer's symlink guard.  The private workspace uses
            # the resolved parent so its final move stays on the destination
            # filesystem.
            output = Path(out_path).expanduser().absolute()
            sidecar = Path(
                sidecar_path or f"{output}.provenance.json"
            ).expanduser().absolute()
            if sidecar == output:
                raise_protocol_error(
                    backend=_CORE_BACKEND_ID,
                    message="video and provenance sidecar paths must be different",
                    recovery_command="choose a distinct .provenance.json sidecar path",
                    details={"path": str(output)},
                )
            policy = _translate_legacy_selector(selector)
            self._observe(
                "legacy_translation",
                requested=selector,
                kind=policy.kind,
                targets=list(policy.targets),
                auto_route=policy.auto_route,
            )
            workspace_parent = output.resolve(strict=False).parent
            workspace_parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(
                prefix=f".{output.name}.render-service-",
                dir=str(workspace_parent),
            ) as workspace_text:
                return self._render_in_workspace(
                    localized,
                    policy=policy,
                    workspace=Path(workspace_text),
                    out_path=output,
                    sidecar_path=sidecar,
                    previous_outputs=tuple(previous_outputs),
                    v1_compatibility=v1_compatibility,
                )
        except RendererException as exc:
            if exc.error.recovery_command is None:
                raise_renderer_error(
                    replace(
                        exc.error,
                        recovery_command=self._default_error_recovery(
                            exc.error.kind
                        ),
                    )
                )
            raise
        except (KeyboardInterrupt, SystemExit):
            raise
        except (TypeError, ValueError) as exc:
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message=f"render service received invalid data: {exc}",
                details={"error_type": type(exc).__name__},
            )
        except BaseException as exc:
            raise_internal_error(
                backend=_CORE_BACKEND_ID,
                message=f"render service failed: {exc or type(exc).__name__}",
                recovery_command="retry the render in a fresh invocation workspace",
                details={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _one_selector(
        selector: str | None,
        engine: str | None,
        backend: str | None,
    ) -> str | None:
        supplied = [item for item in (selector, engine, backend) if item is not None]
        if not supplied:
            return None
        if len(set(supplied)) != 1:
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message="selector, engine, and backend disagree",
                recovery_command="supply one renderer selector spelling and retry",
                details={"selectors": supplied},
            )
        return supplied[0]

    @staticmethod
    def _absolute_input_paths(request: RenderRequest) -> RenderRequest:
        timeline = Path(request.timeline_path).expanduser()
        assets = (
            None
            if request.assets_registry_path is None
            else Path(request.assets_registry_path).expanduser()
        )
        return replace(
            request,
            timeline_path=str(timeline.resolve(strict=False)),
            assets_registry_path=(
                None if assets is None else str(assets.resolve(strict=False))
            ),
        )

    def _render_in_workspace(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        workspace: Path,
        out_path: Path,
        sidecar_path: Path,
        previous_outputs: tuple[object, ...],
        v1_compatibility: Mapping[str, Any] | None,
    ) -> Path:
        selected = self._select(request, policy=policy, workspace=workspace)
        if policy.kind == "planner":
            plan, segment_results, pinned_finalizer = self._execute_planner(
                request,
                policy=policy,
                selected=selected,
                workspace=workspace,
            )
            if not segment_results:
                raise_unsupported_error(
                    backend=selected.candidate.id,
                    message="render planner produced no video segments",
                    recovery_command="use a non-empty timeline or select a direct renderer",
                    details={"total_frames": plan.total_frames},
                )
            final_result, plan = self._finish_plan(
                request,
                plan=plan,
                segment_results=segment_results,
                pinned_finalizer=pinned_finalizer,
                workspace=workspace,
            )
            finalizer_ran = plan.finalizer.id != _DIRECT_FINALIZER_ID
            artifact_lineage = [item.video for item in segment_results]
            compatibility_results = segment_results
            fragment_results = (
                ([*segment_results, final_result] if finalizer_ran else segment_results)
                if len(segment_results) == 1
                else [*segment_results, final_result]
            )
        else:
            final_result = self._invoke_renderer(
                request,
                selected=selected,
                workspace=workspace,
                output_name=request.output_name,
                expected_profile=request.profile,
            )
            plan = self._direct_plan(
                request,
                selected=selected,
                result=final_result,
                requested_policy=policy.requested,
            )
            renderer_result = final_result
            final_result = self.complete_audio(
                final_result,
                request=request,
                plan=plan,
                workspace=workspace,
                backend=selected.candidate.id,
                # The direct plan may pin an executable finalizer; defer
                # completion to it so a normalizable profile/audio mismatch
                # is normalized before publication.
                defer_to_finalizer=(
                    plan.finalizer.id != _DIRECT_FINALIZER_ID
                ),
            )
            finalizer_ran = plan.finalizer.id != _DIRECT_FINALIZER_ID
            if finalizer_ran:
                # An embedding host pinned a registered finalizer for direct
                # renders; honor it exactly like planner-produced plans.
                finalizer, finalizer_evidence = self._resolve_candidate(
                    self.finalizers,
                    plan.finalizer.id,
                    kind="finalizer",
                    observe=False,
                )
                final_result, plan = self._finish_plan(
                    request,
                    plan=plan,
                    segment_results=[renderer_result],
                    pinned_finalizer=(finalizer, finalizer_evidence),
                    workspace=workspace,
                )
            elif final_result.video.profile != plan.profile or (
                final_result.video.duration_frames
                != (
                    plan.window.duration_frames
                    if plan.window is not None
                    else plan.total_frames
                )
            ):
                plan = self._direct_plan(
                    request,
                    selected=selected,
                    result=final_result,
                    requested_policy=policy.requested,
            )
            artifact_lineage = [renderer_result.video]
            compatibility_results = (
                [renderer_result] if finalizer_ran else [final_result]
            )
            fragment_results = (
                [renderer_result, final_result]
                if finalizer_ran
                else [final_result]
            )

        source_video = self._artifact_path(final_result, workspace)
        compatibility = self._v1_compatibility(
            compatibility_results,
            supplied=v1_compatibility,
        )
        fragments = self._merge_backend_fragments(fragment_results)
        provenance = self._provenance_builder(
            engine=policy.requested,
            output=out_path,
            timeline=request.timeline_path,
            assets_registry=request.assets_registry_path,
            plan=plan,
            artifact_profiles=artifact_lineage,
            audio_ownership=final_result.audio_ownership,
            normalization=final_result.normalization,
            attachments=final_result.attachments,
            backend_fragments=fragments,
            v1_compatibility=compatibility,
        )
        self._observe(
            "publish",
            backend=(
                plan.planner.id if policy.kind == "planner" else selected.candidate.id
            ),
            output=str(out_path),
            sidecar=str(sidecar_path),
        )
        published = self._publisher(
            source_video,
            provenance,
            out_path=out_path,
            sidecar_path=sidecar_path,
            previous_outputs=previous_outputs,
        )
        return Path(published)

    def _select(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        workspace: Path,
    ) -> _ResolvedCapability:
        registry: RendererRegistry | PlannerRegistry = (
            self.renderers if policy.kind == "renderer" else self.planners
        )
        rejected: list[dict[str, Any]] = []
        for index, target in enumerate(policy.targets):
            try:
                candidate, evidence = self._resolve_candidate(
                    registry,
                    target,
                    kind=policy.kind,
                )
                report = self._support(
                    candidate,
                    request=request,
                    workspace=workspace,
                    registry=registry,
                )
            except RendererException as exc:
                if not policy.auto_route or index == len(policy.targets) - 1:
                    raise
                if exc.error.kind not in {"unsupported", "binary_missing"}:
                    raise
                rejected.append(exc.error.to_dict())
                continue
            if not report.supported:
                rejected.append(report.to_dict())
                if policy.auto_route and index < len(policy.targets) - 1:
                    continue
                self._unsupported_report(report, registry=registry)
            if policy.auto_route and index == 0:
                warnings.warn(
                    f"legacy selector {policy.requested!r} auto-routed this supported "
                    f"timeline to {candidate.id}; select a qualified renderer "
                    "id for strict routing",
                    LegacyRenderRoutingWarning,
                    stacklevel=4,
                )
            return _ResolvedCapability(
                candidate,
                evidence,
                report,
                rejected=list(rejected),
            )

        alternatives = self._alternatives(registry)
        raise_unsupported_error(
            backend=(policy.targets[-1] if policy.targets else _CORE_BACKEND_ID),
            message=f"no renderer supports legacy selector {policy.requested!r}",
            recovery_command=self._recovery_for(alternatives),
            details={"attempts": rejected, "alternatives": alternatives},
        )

    def _resolve_candidate(
        self,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
        requested_id: str,
        *,
        kind: CapabilityKind,
        observe: bool = True,
    ) -> tuple[RenderingCandidate[Any], dict[str, Any]]:
        try:
            candidate = registry.get(requested_id)
            evidence = registry.resolve_evidence(requested_id)
        except RenderingRegistryError as exc:
            evidence: dict[str, Any] = {}
            try:
                evidence = registry.resolve_evidence(requested_id)
            except RenderingRegistryError:
                evidence = dict(exc.details)
            if observe:
                self._observe_resolution(requested_id, evidence, candidate=None)
            alternatives = self._alternatives(registry)
            details = {
                "registry_error": exc.to_dict(),
                "alternatives": alternatives,
            }
            raise_unsupported_error(
                backend=(
                    requested_id
                    if _QUALIFIED_ID_RE.fullmatch(requested_id)
                    else _CORE_BACKEND_ID
                ),
                message=str(exc),
                recovery_command=self._recovery_for(alternatives),
                details=details,
            )
        if observe:
            self._observe_resolution(requested_id, evidence, candidate=candidate)
        if (
            evidence.get("resolved_id") != candidate.id
            or evidence.get("manifest_digest") != candidate.manifest_digest
            or evidence.get("priority_index", evidence.get("priority"))
            != candidate.priority_index
        ):
            raise_internal_error(
                backend=_CORE_BACKEND_ID,
                message=(
                    f"{kind} registry changed while resolving {requested_id!r}"
                ),
                recovery_command="retry after renderer registry updates have completed",
                details={
                    "requested_id": requested_id,
                    "candidate": candidate.to_dict(),
                    "resolution_evidence": evidence,
                },
            )
        if not candidate.execution_eligible:
            alternatives = self._alternatives(registry)
            raise_unsupported_error(
                backend=candidate.id,
                message=f"{kind} {candidate.id!r} is not execution-eligible",
                recovery_command=self._recovery_for(alternatives),
                details={
                    "eligibility": candidate.eligibility.to_dict(),
                    "alternatives": alternatives,
                },
            )
        return candidate, evidence

    def _observe_resolution(
        self,
        requested_id: str,
        evidence: Mapping[str, Any],
        *,
        candidate: RenderingCandidate[Any] | None,
    ) -> None:
        alias_chain = list(evidence.get("alias_chain") or [])
        self._observe(
            "alias",
            requested_id=requested_id,
            canonical_id=evidence.get("canonical_id", requested_id),
            alias_chain=alias_chain,
        )
        self._observe(
            "override",
            requested_id=requested_id,
            override=evidence.get("override"),
        )
        self._observe(
            "winner",
            requested_id=requested_id,
            resolved_id=(
                candidate.id if candidate is not None else evidence.get("resolved_id")
            ),
            priority=evidence.get("priority_index", evidence.get("priority")),
        )
        eligibility = (
            candidate.eligibility.to_dict()
            if candidate is not None
            else evidence.get("eligibility", {})
        )
        self._observe(
            "eligibility",
            requested_id=requested_id,
            eligible=(
                candidate.execution_eligible
                if candidate is not None
                else evidence.get("execution_eligible", evidence.get("eligible", False))
            ),
            evidence=eligibility,
        )

    def _support(
        self,
        candidate: RenderingCandidate[Any],
        *,
        request: RenderRequest,
        workspace: Path,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
    ) -> SupportReport:
        manifest = candidate.manifest
        projected = request.for_backend(candidate.id)
        self._observe("support", backend=candidate.id)
        if "support" in manifest.operations:
            response = self._run_command(
                candidate,
                "support",
                projected,
                workspace=workspace,
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
        return self._static_support(candidate, projected, registry=registry)

    def _static_support(
        self,
        candidate: RenderingCandidate[Any],
        request: RenderRequest,
        *,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
    ) -> SupportReport:
        capabilities = candidate.manifest.capabilities
        reasons: list[str] = []
        if isinstance(registry, RendererRegistry):
            support_key = (
                "supports_windows"
                if request.window is not None
                else "supports_full_timeline"
            )
            if capabilities.get(support_key) is not True:
                mode = "frame windows" if request.window is not None else "full timelines"
                reasons.append(
                    f"renderer does not declare static support for {mode}"
                )

            ownership = capabilities.get("audio_ownership")
            if request.audio is not None:
                if not isinstance(ownership, list):
                    reasons.append(
                        "renderer does not declare static audio ownership support"
                    )
                elif request.audio.value not in ownership:
                    reasons.append(
                        f"audio ownership {request.audio.value!r} is not statically supported"
                    )

            if request.profile is not None:
                profiles = capabilities.get("output_profiles")
                expected_profiles = {
                    request.profile.container,
                    f"video/{request.profile.container}",
                }
                if not isinstance(profiles, list):
                    reasons.append("renderer does not declare static output profiles")
                elif expected_profiles.isdisjoint(profiles):
                    reasons.append(
                        f"output container {request.profile.container!r} is not statically supported"
                    )

            reasons.extend(self._static_timeline_reasons(capabilities, request))
        elif isinstance(registry, PlannerRegistry):
            if not capabilities:
                reasons.append("planner does not declare static capability evidence")
        else:
            containers = capabilities.get("containers")
            if request.profile is not None:
                if not isinstance(containers, list):
                    reasons.append("finalizer does not declare static containers")
                elif request.profile.container not in containers:
                    reasons.append(
                        f"output container {request.profile.container!r} is not statically supported"
                    )
            ownership = capabilities.get("audio_ownership")
            if request.audio is not None:
                if not isinstance(ownership, list):
                    reasons.append(
                        "finalizer does not declare static audio ownership support"
                    )
                elif request.audio.value not in ownership:
                    reasons.append(
                        f"audio ownership {request.audio.value!r} is not statically supported"
                    )
            if capabilities.get("preserves_attachments") is not True:
                reasons.append("finalizer does not declare attachment preservation")
        alternatives = self._alternatives(registry, exclude=candidate.id) if reasons else []
        return SupportReport(
            schema_version=SCHEMA_VERSION,
            supported=not reasons,
            reasons=reasons,
            features={
                str(key): value
                for key, value in capabilities.get("features", {}).items()
                if isinstance(value, (bool, str))
            },
            alternatives=alternatives,
            backend=candidate.id,
            backend_version=candidate.manifest.version,
        )

    @staticmethod
    def _static_timeline_reasons(
        capabilities: Mapping[str, Any], request: RenderRequest
    ) -> list[str]:
        """Compare coarse renderer declarations with the concrete timeline.

        A renderer without a ``support`` verb has only its manifest as
        evidence, so omitted declarations are unknown and therefore fail
        closed when the request actually exercises them.
        """

        try:
            payload = json.loads(Path(request.timeline_path).read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise TypeError("timeline must contain a JSON object")
            raw_clips = payload.get("clips", [])
            raw_tracks = payload.get("tracks", [])
            if not isinstance(raw_clips, list) or not isinstance(raw_tracks, list):
                raise TypeError("timeline clips and tracks must be arrays")
            clip_types = {
                str(item.get("clipType", "media"))
                for item in raw_clips
                if isinstance(item, Mapping)
            }
            track_types = {
                str(item.get("kind"))
                for item in raw_tracks
                if isinstance(item, Mapping) and item.get("kind") is not None
            }
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return [f"timeline cannot be evaluated against static support: {exc}"]

        reasons: list[str] = []
        declared_clips = capabilities.get("clip_types")
        if clip_types:
            if not isinstance(declared_clips, list):
                reasons.append("renderer does not declare static clip types")
            else:
                missing = sorted(clip_types - set(declared_clips))
                if missing:
                    reasons.append(
                        "timeline uses statically unsupported clip types: "
                        + ", ".join(missing)
                    )
        declared_tracks = capabilities.get("track_types")
        if track_types:
            if not isinstance(declared_tracks, list):
                reasons.append("renderer does not declare static track types")
            else:
                missing = sorted(track_types - set(declared_tracks))
                if missing:
                    reasons.append(
                        "timeline uses statically unsupported track types: "
                        + ", ".join(missing)
                    )
        return reasons

    def _unsupported_report(
        self,
        report: SupportReport,
        *,
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
    ) -> None:
        alternatives = list(report.alternatives) or self._alternatives(
            registry, exclude=report.backend
        )
        raise_unsupported_error(
            backend=report.backend,
            message=f"{report.backend} does not support this render request",
            recovery_command=self._recovery_for(alternatives),
            details={
                "reasons": list(report.reasons),
                "features": dict(report.features),
                "alternatives": alternatives,
            },
        )

    def _invoke_renderer(
        self,
        request: RenderRequest,
        *,
        selected: _ResolvedCapability,
        workspace: Path,
        output_name: str,
        expected_profile: Any,
    ) -> RenderResult:
        backend_request = replace(request, output_name=output_name).for_backend(
            selected.candidate.id
        )
        self._observe("invoke", backend=selected.candidate.id, verb="render")
        response = self._run_command(
            selected.candidate,
            "render",
            backend_request,
            workspace=workspace,
        )
        if not isinstance(response, RenderResult):
            raise_protocol_error(
                backend=selected.candidate.id,
                message="render operation did not return a RenderResult",
                details={"received_type": type(response).__name__},
            )
        # A null request profile deliberately leaves the backend's output
        # profile open (the DTO contract permits this).  Validation still
        # recomputes hashes, probes the media, and checks the probe against the
        # declared profile.  Planned renders are subsequently checked or
        # normalized against their canonical plan profile in _finish_plan.
        expected = expected_profile or response.video.profile
        self._observe("validate", backend=selected.candidate.id)
        return self._validator(
            response,
            expected_profile=expected,
            workspace_root=workspace,
        )

    def _segment_request(
        self,
        request: RenderRequest,
        *,
        candidate: RenderingCandidate[Any],
        segment: RenderSegment,
        index: int,
        workspace: Path,
    ) -> tuple[RenderRequest, dict[str, str]]:
        """Adapt a planned window for full-timeline-only renderers.

        Window-aware third-party renderers receive the canonical ``window``
        field unchanged.  A renderer that explicitly declares
        ``supports_windows: false`` receives an invocation-private sliced
        timeline and a null window, preserving the behavior of Astrid's
        existing full-timeline backends without teaching the service any
        concrete backend identities.
        """

        if candidate.manifest.capabilities.get("supports_windows") is not False:
            return request, {}
        timeline_path = Path(request.timeline_path)
        try:
            timeline_data = json.loads(timeline_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise_protocol_error(
                backend=candidate.id,
                message=f"cannot materialize planned timeline window: {exc}",
                recovery_command="repair the timeline JSON and retry the planned render",
                details={"timeline_path": str(timeline_path)},
            )
        if not isinstance(timeline_data, Mapping):
            raise_protocol_error(
                backend=candidate.id,
                message="cannot materialize a window from a non-object timeline",
                recovery_command="write the timeline as a JSON object and retry",
                details={"timeline_path": str(timeline_path)},
            )
        materialized = self._window_timeline(timeline_data, segment.window)
        materialized_path = (
            workspace / "segment-inputs" / f"{index:04d}-timeline.json"
        )
        write_json_atomic(materialized_path, materialized)
        return (
            replace(request, timeline_path=str(materialized_path), window=None),
            {"materialized_timeline": sha256_file(materialized_path)},
        )

    @classmethod
    def _window_timeline(
        cls,
        timeline_data: Mapping[str, Any],
        window: FrameWindow,
    ) -> dict[str, Any]:
        fps = Fraction(*window.fps_rational)
        start = Fraction(window.start_frame, 1) / fps
        end = Fraction(window.end_frame, 1) / fps
        raw_clips = timeline_data.get("clips", [])
        raw_tracks = timeline_data.get("tracks", [])
        if not isinstance(raw_clips, list) or not isinstance(raw_tracks, list):
            raise ValueError("timeline clips and tracks must be arrays")

        clips: list[dict[str, Any]] = []
        for raw_clip in raw_clips:
            if not isinstance(raw_clip, Mapping):
                raise TypeError("timeline clips must contain objects")
            clipped = cls._window_clip(raw_clip, start=start, end=end, window=window)
            if clipped is not None:
                clips.append(clipped)
        used_tracks = {clip.get("track") for clip in clips}
        tracks = [
            dict(track)
            for track in raw_tracks
            if isinstance(track, Mapping) and track.get("id") in used_tracks
        ]
        metadata = timeline_data.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        result = dict(timeline_data)
        result["tracks"] = tracks
        result["clips"] = clips
        result["metadata"] = {
            **dict(metadata),
            "source_window_start_seconds": float(start),
            "source_window_end_seconds": float(end),
            "duration_seconds": float(end - start),
        }
        return result

    @classmethod
    def _window_clip(
        cls,
        clip: Mapping[str, Any],
        *,
        start: Fraction,
        end: Fraction,
        window: FrameWindow,
    ) -> dict[str, Any] | None:
        clip_start = cls._timeline_number(clip.get("at", 0), "clip.at")
        clip_end = cls._clip_end(clip, clip_start=clip_start)
        visible_start = max(clip_start, start)
        visible_end = min(clip_end, end)
        if visible_end <= visible_start:
            return None

        result = dict(clip)
        result["at"] = float(visible_start - start)
        result["id"] = (
            f"{clip.get('id', 'clip')}_{window.start_frame}_{window.end_frame}"
        )
        if clip.get("clipType", "media") == "media":
            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
            if speed <= 0:
                raise ValueError("clip.speed must be positive")
            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
            source_from += (visible_start - clip_start) * speed
            result["from"] = float(source_from)
            result["to"] = float(
                source_from + (visible_end - visible_start) * speed
            )
        elif isinstance(clip.get("hold"), (int, float)) and not isinstance(
            clip.get("hold"), bool
        ):
            result["hold"] = float(visible_end - visible_start)
        return result

    @classmethod
    def _clip_end(
        cls, clip: Mapping[str, Any], *, clip_start: Fraction
    ) -> Fraction:
        if clip.get("clipType", "media") == "media":
            source_from = cls._timeline_number(clip.get("from", 0), "clip.from")
            if "to" not in clip:
                raise ValueError("media clip must declare a source to bound")
            source_to = cls._timeline_number(clip["to"], "clip.to")
            speed = cls._timeline_number(clip.get("speed", 1), "clip.speed")
            if source_from < 0 or source_to <= source_from or speed <= 0:
                raise ValueError("media clip must have positive bounds and speed")
            return clip_start + (source_to - source_from) / speed
        hold = clip.get("hold")
        if isinstance(hold, (int, float)) and not isinstance(hold, bool):
            return clip_start + max(Fraction(0), cls._timeline_number(hold, "clip.hold"))
        if isinstance(clip.get("to"), (int, float)) and not isinstance(
            clip.get("to"), bool
        ):
            return cls._timeline_number(clip["to"], "clip.to")
        return clip_start

    @staticmethod
    def _timeline_number(value: Any, label: str) -> Fraction:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{label} must be a finite number")
        if not math.isfinite(float(value)):
            raise ValueError(f"{label} must be finite")
        return Fraction(str(value))

    @staticmethod
    def _validate_segment_duration(
        result: RenderResult,
        *,
        segment: RenderSegment,
        canonical_profile: Any,
        backend: str,
    ) -> None:
        RenderService._validate_planned_duration(
            result,
            planned_frames=segment.window.duration_frames,
            canonical_profile=canonical_profile,
            backend=backend,
            label="renderer artifact",
        )

    @staticmethod
    def _validate_planned_duration(
        result: RenderResult,
        *,
        planned_frames: int,
        canonical_profile: Any,
        backend: str,
        label: str,
    ) -> None:
        artifact_seconds = Fraction(
            result.video.duration_frames, 1
        ) / Fraction(*result.video.profile.fps_rational)
        canonical_fps = Fraction(*canonical_profile.fps_rational)
        planned_seconds = Fraction(planned_frames, 1) / canonical_fps
        delta_frames = abs(artifact_seconds - planned_seconds) * canonical_fps
        if delta_frames <= canonical_profile.duration_tolerance:
            return
        raise_invalid_artifact_error(
            backend=backend,
            message=f"{label} duration does not match its planned frame window",
            recovery_command="rerender the exact planned segment window and retry",
            details={
                "planned_duration_frames": planned_frames,
                "artifact_duration_frames": result.video.duration_frames,
                "canonical_delta_frames": [
                    delta_frames.numerator,
                    delta_frames.denominator,
                ],
                "tolerance_frames": canonical_profile.duration_tolerance,
            },
        )

    def _execute_planner(
        self,
        request: RenderRequest,
        *,
        policy: _SelectionPolicy,
        selected: _ResolvedCapability,
        workspace: Path,
    ) -> tuple[
        RenderPlan,
        list[RenderResult],
        tuple[RenderingCandidate[Any], dict[str, Any]],
    ]:
        planner_request = request.for_backend(selected.candidate.id)
        self._observe("invoke", backend=selected.candidate.id, verb="plan")
        response = self._run_command(
            selected.candidate,
            "plan",
            planner_request,
            workspace=workspace,
        )
        if not isinstance(response, RenderPlan):
            raise_protocol_error(
                backend=selected.candidate.id,
                message="plan operation did not return a RenderPlan",
                details={"received_type": type(response).__name__},
            )
        # The registry selection is authoritative.  A planner response may
        # still carry the pre-alias/pre-override identity it was asked to
        # replace (notably during compatibility routing); normalize that
        # self-description to the selected candidate and its complete
        # resolution evidence below.
        planner_resolution = self._planner_resolution(selected)
        normalized_segments: list[RenderSegment] = []
        segment_results: list[RenderResult] = []
        input_hashes = self._input_hashes(request)
        for index, segment in enumerate(response.segments):
            candidate, evidence = self._resolve_candidate(
                self.renderers,
                segment.renderer.id,
                kind="renderer",
            )
            # The planner already resolved aliases/overrides itself and
            # recorded that lineage on the segment.  Re-resolving the emitted
            # id from scratch would discard the alias chain, so merge: the
            # service's resolution is authoritative for identity/trust while
            # the planner's recorded lineage survives when present.
            planner_renderer = segment.renderer
            native_request = replace(
                request,
                window=segment.window,
                output_name=f"segment-{index:04d}.mp4",
            )
            segment_request, materialized_hashes = self._segment_request(
                native_request,
                candidate=candidate,
                segment=segment,
                index=index,
                workspace=workspace,
            )
            report = self._support(
                candidate,
                request=segment_request,
                workspace=workspace,
                registry=self.renderers,
            )
            if not report.supported:
                self._unsupported_report(report, registry=self.renderers)
            resolved = _ResolvedCapability(candidate, evidence, report)
            merged_renderer = replace(
                planner_renderer,
                id=candidate.id,
                source_pack=self._source_pack(candidate, evidence),
                manifest_digest=candidate.manifest_digest,
                trust_eligibility=candidate.eligibility.to_dict(),
                alias_chain=(
                    planner_renderer.alias_chain
                    or list(evidence.get("alias_chain") or [])
                ),
                override=planner_renderer.override or evidence.get("override"),
                support_decision=report,
            )
            normalized_segment = replace(
                segment,
                renderer=merged_renderer,
                input_hashes={
                    **segment.input_hashes,
                    **input_hashes,
                    **materialized_hashes,
                },
            )
            normalized_segments.append(normalized_segment)
            result = self._invoke_renderer(
                segment_request,
                selected=resolved,
                workspace=workspace,
                output_name=segment_request.output_name,
                # Segment renderers may emit a profile that the registered
                # finalizer must normalize.  The artifact is first validated
                # against its own declaration; a one-segment exact match is
                # checked against the plan in _finish_plan, while every
                # mismatch and every multi-segment plan goes through the
                # pinned finalizer.
                expected_profile=None,
            )
            completed = self.complete_audio(
                result,
                request=segment_request,
                plan=response,
                workspace=workspace,
                backend=candidate.id,
                # The plan pins an explicit finalizer; segment audio is
                # deferred to it (single- and multi-segment alike) so a
                # normalizable profile/audio mismatch cannot fail the segment
                # before the finalizer can normalize it.
                defer_to_finalizer=response.finalizer.id != _DIRECT_FINALIZER_ID,
            )
            self._validate_segment_duration(
                completed,
                segment=segment,
                canonical_profile=response.profile,
                backend=candidate.id,
            )
            segment_results.append(completed)

        finalizer, finalizer_evidence = self._resolve_candidate(
            self.finalizers,
            response.finalizer.id,
            kind="finalizer",
            observe=False,
        )
        finalizer_resolution = replace(
            response.finalizer,
            id=finalizer.id,
            source_pack=self._source_pack(finalizer, finalizer_evidence),
            manifest_digest=finalizer.manifest_digest,
            trust_eligibility=finalizer.eligibility.to_dict(),
            alias_chain=(
                response.finalizer.alias_chain
                or list(finalizer_evidence.get("alias_chain") or [])
            ),
            override=response.finalizer.override or finalizer_evidence.get("override"),
            # The planner's finalizer support_decision names its pre-alias
            # identity; _finish_plan re-evaluates support for the resolved
            # finalizer and records the authoritative decision.
            support_decision=None,
        )
        plan = replace(
            response,
            request_digest=compute_request_digest(request.to_dict()),
            requested_policy=policy.requested,
            planner=planner_resolution,
            segments=normalized_segments,
            finalizer=finalizer_resolution,
        )
        return plan, segment_results, (finalizer, finalizer_evidence)

    def _finish_plan(
        self,
        request: RenderRequest,
        *,
        plan: RenderPlan,
        segment_results: list[RenderResult],
        pinned_finalizer: tuple[RenderingCandidate[Any], dict[str, Any]],
        workspace: Path,
    ) -> tuple[RenderResult, RenderPlan]:
        candidate, evidence = pinned_finalizer
        if candidate.id == _DIRECT_FINALIZER_ID:
            # No executable finalizer pinned: the segment must already match
            # the canonical plan profile exactly.
            if len(segment_results) != 1:
                raise_internal_error(
                    backend=_CORE_BACKEND_ID,
                    message="direct finalizer received multiple segments",
                    recovery_command="select a planner that pins an executable finalizer",
                    details={"segment_count": len(segment_results)},
                )
            result = self._validator(
                segment_results[0],
                expected_profile=plan.profile,
                workspace_root=workspace,
            )
            return result, plan

        ownerships = {item.audio_ownership for item in segment_results}
        if ownerships == {AudioOwnership.PASSTHROUGH}:
            requested_audio = AudioOwnership.PASSTHROUGH
        elif plan.profile.has_audio:
            requested_audio = AudioOwnership.RENDERED
        else:
            requested_audio = AudioOwnership.NONE
        support_audio = (
            None
            if requested_audio is AudioOwnership.PASSTHROUGH
            and plan.profile.has_audio
            else requested_audio
        )
        support_request = RenderRequest(
            schema_version=SCHEMA_VERSION,
            timeline_path=request.timeline_path,
            assets_registry_path=request.assets_registry_path,
            output_name=request.output_name,
            audio=support_audio,
            profile=plan.profile,
            backend_config=request.backend_config,
            metadata=request.metadata,
        )
        report = self._support(
            candidate,
            request=support_request,
            workspace=workspace,
            registry=self.finalizers,
        )
        if not report.supported:
            self._unsupported_report(report, registry=self.finalizers)
        prior_finalizer = plan.finalizer
        finalizer_resolution = replace(
            self._finalizer_resolution(
                candidate,
                evidence,
                support=report,
            ),
            alias_chain=(
                prior_finalizer.alias_chain
                or list(evidence.get("alias_chain") or [])
            ),
            override=prior_finalizer.override or evidence.get("override"),
        )
        plan = replace(plan, finalizer=finalizer_resolution)
        finalize_request = FinalizeRequest(
            schema_version=SCHEMA_VERSION,
            plan=plan,
            artifacts=[item.video for item in segment_results],
            output_name=request.output_name,
            backend_config={
                candidate.id: dict(request.backend_config.get(candidate.id, {}))
            }
            if candidate.id in request.backend_config
            else {},
            metadata=request.metadata,
        )
        self._observe("finalize", backend=candidate.id)
        response = self._run_command(
            candidate,
            "finalize",
            finalize_request,
            workspace=workspace,
        )
        if not isinstance(response, RenderResult):
            raise_protocol_error(
                backend=candidate.id,
                message="finalize operation did not return a RenderResult",
                details={"received_type": type(response).__name__},
            )
        try:
            response = finalize_request.validate_final_result(response)
        except (TypeError, ValueError) as exc:
            raise_invalid_artifact_error(
                backend=candidate.id,
                message=f"finalizer returned an invalid result: {exc}",
                recovery_command="rerun finalization in a fresh invocation workspace",
                details={"error_type": type(exc).__name__},
            )
        self._observe("validate", backend=candidate.id)
        # The finalizer validates its stream-copied concat internally with
        # frame-count authority (see _validate_concat_output); the strict
        # probe-based validator would reject the output on the concat's
        # AAC-grid timestamp rounding alone (avg fps 9.98 vs 10/1).
        self._validate_planned_duration(
            response,
            planned_frames=(
                plan.window.duration_frames
                if plan.window is not None
                else plan.total_frames
            ),
            canonical_profile=plan.profile,
            backend=candidate.id,
            label="finalized artifact",
        )
        completed = self.complete_audio(
            response,
            request=request,
            plan=plan,
            workspace=workspace,
            backend=candidate.id,
        )
        self._validate_planned_duration(
            completed,
            planned_frames=(
                plan.window.duration_frames
                if plan.window is not None
                else plan.total_frames
            ),
            canonical_profile=plan.profile,
            backend=candidate.id,
            label="audio-completed artifact",
        )
        return completed, plan

    def complete_audio(
        self,
        result: RenderResult,
        *,
        request: RenderRequest,
        plan: RenderPlan,
        workspace: Path,
        backend: str = _CORE_BACKEND_ID,
        defer_to_finalizer: bool = False,
    ) -> RenderResult:
        """Apply host-owned completion semantics after renderer validation.

        ``rendered`` is already complete. ``none`` is an intentional
        visual-only result, while ``passthrough`` must be completed by the
        embedding host before publication.  A configured completer may also
        apply an optional compatibility policy to ``none`` without requiring
        arbitrary renderers to synthesize silence.
        """

        self._observe("audio", ownership=result.audio_ownership.value)
        if result.audio_ownership is AudioOwnership.RENDERED:
            return result
        if result.video.profile.has_audio:
            raise_invalid_artifact_error(
                backend=backend,
                message=(
                    f"audio_ownership={result.audio_ownership.value!r} requires "
                    "a visual-only renderer artifact"
                ),
                recovery_command="rerender with an audio/profile pair that agrees",
            )
        if defer_to_finalizer:
            # A registered finalizer owns cross-segment compatibility: it may
            # synthesize silence for NONE segments or preserve a uniform set
            # of PASSTHROUGH segments.  Completion, if still necessary, runs
            # once on the finalized result below.
            return result
        if (
            result.audio_ownership is AudioOwnership.NONE
            and (
                plan.profile.has_audio
                or (
                    request.profile is not None
                    and request.profile.has_audio
                )
            )
        ):
            raise_invalid_artifact_error(
                backend=backend,
                message="audio_ownership='none' cannot satisfy a requested audio profile",
                recovery_command="request passthrough/rendered audio or a visual-only profile",
            )
        if self._audio_completer is None:
            if result.audio_ownership is AudioOwnership.PASSTHROUGH:
                raise_unsupported_error(
                    backend=backend,
                    message=(
                        "renderer requested passthrough audio but no host audio "
                        "completer is configured"
                    ),
                    recovery_command=(
                        "configure an audio completer or select a renderer that "
                        "returns rendered audio"
                    ),
                    details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
                )
            return result
        completed = self._audio_completer(
            result,
            request=request,
            plan=plan,
            workspace=workspace,
        )
        if not isinstance(completed, RenderResult):
            raise_protocol_error(
                backend=_CORE_BACKEND_ID,
                message="audio completer did not return a RenderResult",
                details={"received_type": type(completed).__name__},
            )
        if (
            completed.audio_ownership is AudioOwnership.PASSTHROUGH
            or (
                result.audio_ownership is AudioOwnership.PASSTHROUGH
                and completed.audio_ownership is not AudioOwnership.RENDERED
            )
        ):
            raise_invalid_artifact_error(
                backend=backend,
                message="host audio completer left passthrough audio incomplete",
                recovery_command="return a completed rendered-audio result",
                details={"audio_ownership": AudioOwnership.PASSTHROUGH.value},
            )
        missing_attachments = sorted(
            set(result.attachments) - set(completed.attachments)
        )
        changed_attachments = sorted(
            name
            for name, attachment in result.attachments.items()
            if name in completed.attachments
            and completed.attachments[name] != attachment
        )
        if missing_attachments or changed_attachments:
            raise_invalid_artifact_error(
                backend=backend,
                message="host audio completion did not preserve renderer attachments",
                recovery_command="preserve every named attachment while completing audio",
                details={
                    "missing": missing_attachments,
                    "changed": changed_attachments,
                },
            )
        original_profile = result.video.profile.to_dict()
        completed_profile = completed.video.profile.to_dict()
        audio_fields = {
            "audio_codec",
            "audio_sample_rate",
            "audio_channel_layout",
        }
        changed_video_fields = sorted(
            key
            for key, value in original_profile.items()
            if key not in audio_fields and completed_profile.get(key) != value
        )
        if (
            changed_video_fields
            or completed.video.duration_frames != result.video.duration_frames
        ):
            raise_invalid_artifact_error(
                backend=backend,
                message="host audio completion changed the renderer's video contract",
                recovery_command="complete audio without changing video profile or duration",
                details={
                    "changed_profile_fields": changed_video_fields,
                    "before_duration_frames": result.video.duration_frames,
                    "after_duration_frames": completed.video.duration_frames,
                },
            )
        return self._validator(
            completed,
            expected_profile=completed.video.profile,
            workspace_root=workspace,
        )

    def _direct_plan(
        self,
        request: RenderRequest,
        *,
        selected: _ResolvedCapability,
        result: RenderResult,
        requested_policy: str,
    ) -> RenderPlan:
        finalizer_resolution = self._direct_finalizer_resolution()
        reasons: dict[str, str] = {"0": "direct renderer selection"}
        if selected.rejected:
            # A legacy auto-route selector rejects earlier candidates before
            # the winning backend succeeds; record that rejection evidence so
            # provenance explains why this backend rendered the timeline.
            reasons["0"] = (
                "direct renderer selection; rejected candidates: "
                + json.dumps(selected.rejected, sort_keys=True)
            )
        if request.window is not None:
            if request.window.fps_rational != result.video.profile.fps_rational:
                raise_invalid_artifact_error(
                    backend=selected.candidate.id,
                    message="renderer artifact FPS does not match the requested frame window",
                    recovery_command="render the requested window at its declared rational FPS",
                    details={
                        "window_fps": list(request.window.fps_rational),
                        "artifact_fps": list(result.video.profile.fps_rational),
                    },
                )
            segment_window = request.window
            total_frames = request.window.end_frame
            plan_window = request.window
            self._validate_planned_duration(
                result,
                planned_frames=request.window.duration_frames,
                canonical_profile=result.video.profile,
                backend=selected.candidate.id,
                label="renderer artifact",
            )
        else:
            segment_window = FrameWindow(
                start_frame=0,
                end_frame=result.video.duration_frames,
                fps_rational=result.video.profile.fps_rational,
            )
            total_frames = result.video.duration_frames
            plan_window = None
        segment = RenderSegment(
            window=segment_window,
            renderer=self._renderer_resolution(selected),
            input_hashes=self._input_hashes(request),
        )
        return RenderPlan(
            schema_version=SCHEMA_VERSION,
            request_digest=compute_request_digest(request.to_dict()),
            requested_policy=requested_policy,
            planner=PlannerResolution(
                id=_DIRECT_PLANNER_ID,
                source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
                manifest_digest=_DIRECT_PLANNER_DIGEST,
                trust_eligibility={"eligible": True, "reason": "core direct plan"},
            ),
            segments=[segment],
            finalizer=finalizer_resolution,
            profile=result.video.profile,
            total_frames=total_frames,
            reasons=reasons,
            window=plan_window,
        )

    def _direct_finalizer_resolution(self) -> FinalizerResolution:
        if self.finalizer_id is not None:
            candidate, evidence = self._resolve_candidate(
                self.finalizers,
                self.finalizer_id,
                kind="finalizer",
                observe=False,
            )
            return self._finalizer_resolution(candidate, evidence, support=None)
        return FinalizerResolution(
            id=_DIRECT_FINALIZER_ID,
            source_pack={"id": _CORE_BACKEND_ID, "source_kind": "core"},
            manifest_digest=_DIRECT_FINALIZER_DIGEST,
            trust_eligibility={"eligible": True, "reason": "core direct pass-through"},
        )

    @staticmethod
    def _source_pack(
        candidate: RenderingCandidate[Any], evidence: Mapping[str, Any]
    ) -> dict[str, Any]:
        source = {
            "id": candidate.pack_id,
            "source_kind": candidate.source_kind,
            "root": str(candidate.pack_root),
            "priority_index": candidate.priority_index,
        }
        revision = candidate.eligibility.active_revision
        if revision is not None:
            source["active_revision"] = revision
        manifest_path = evidence.get("manifest_path")
        if isinstance(manifest_path, str):
            source["manifest_path"] = manifest_path
        return source

    def _renderer_resolution(
        self, selected: _ResolvedCapability
    ) -> RendererResolution:
        candidate = selected.candidate
        evidence = selected.evidence
        return RendererResolution(
            id=candidate.id,
            source_pack=self._source_pack(candidate, evidence),
            manifest_digest=candidate.manifest_digest,
            alias_chain=list(evidence.get("alias_chain") or []),
            override=evidence.get("override"),
            support_decision=selected.support,
            trust_eligibility=candidate.eligibility.to_dict(),
        )

    def _planner_resolution(
        self, selected: _ResolvedCapability
    ) -> PlannerResolution:
        candidate = selected.candidate
        evidence = selected.evidence
        return PlannerResolution(
            id=candidate.id,
            source_pack=self._source_pack(candidate, evidence),
            manifest_digest=candidate.manifest_digest,
            trust_eligibility=candidate.eligibility.to_dict(),
            alias_chain=list(evidence.get("alias_chain") or []),
            override=evidence.get("override"),
            support_decision=selected.support,
        )

    def _finalizer_resolution(
        self,
        candidate: RenderingCandidate[Any],
        evidence: Mapping[str, Any],
        *,
        support: SupportReport | None,
    ) -> FinalizerResolution:
        return FinalizerResolution(
            id=candidate.id,
            source_pack=self._source_pack(candidate, evidence),
            manifest_digest=candidate.manifest_digest,
            trust_eligibility=candidate.eligibility.to_dict(),
            alias_chain=list(evidence.get("alias_chain") or []),
            override=evidence.get("override"),
            support_decision=support,
        )

    def _run_command(
        self,
        candidate: RenderingCandidate[Any],
        verb: str,
        payload: Any,
        *,
        workspace: Path,
        required_binaries: Sequence[str] | None = None,
    ) -> Any:
        token = hashlib.sha256(
            f"{candidate.id}:{verb}:{len(list(workspace.iterdir()))}".encode()
        ).hexdigest()[:12]
        request_path = workspace / f"{token}-{verb}-request.json"
        result_path = workspace / f"{token}-{verb}-result.json"
        write_json_atomic(request_path, payload.to_dict())
        transport = (
            self._transport
            if self._transport is not None
            else self._transport_factory(candidate.id)
        )
        return transport.run(
            verb,
            candidate.manifest.command,
            backend=candidate.id,
            request_path=request_path,
            result_path=result_path,
            cwd=candidate.pack_root,
            timeout=candidate.manifest.timeout_seconds,
            required_binaries=(
                candidate.manifest.required_binaries
                if required_binaries is None
                else required_binaries
            ),
        )

    @staticmethod
    def _artifact_path(result: RenderResult, workspace: Path) -> Path:
        candidate = (workspace / result.video.path).resolve(strict=False)
        try:
            candidate.relative_to(workspace.resolve())
        except ValueError:
            raise_invalid_artifact_error(
                backend=_CORE_BACKEND_ID,
                message="validated renderer artifact escaped its invocation workspace",
                recovery_command="rerun the renderer with a contained output path",
                details={"path": result.video.path},
            )
        return candidate

    @staticmethod
    def _input_hashes(request: RenderRequest) -> dict[str, str]:
        paths: dict[str, Path] = {"timeline": Path(request.timeline_path)}
        if request.assets_registry_path is not None:
            paths["assets_registry"] = Path(request.assets_registry_path)
        return {
            name: sha256_file(path)
            for name, path in paths.items()
            if path.is_file()
        }

    @staticmethod
    def _merge_backend_fragments(
        results: Sequence[RenderResult],
    ) -> dict[str, dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for result in results:
            for namespace, fragment in result.backend_fragments.items():
                current = merged.get(namespace)
                if current is None:
                    merged[namespace] = dict(fragment)
                elif current != fragment:
                    records = current.get("service_fragment_sequence")
                    if isinstance(records, list):
                        records.append(dict(fragment))
                    else:
                        merged[namespace] = {
                            "service_fragment_sequence": [current, dict(fragment)]
                        }
        return merged

    @staticmethod
    def _v1_compatibility(
        results: Sequence[RenderResult],
        *,
        supplied: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        compatibility: dict[str, Any] = {
            "project_dir": None,
            "composition_id": "TimelineComposition",
            "active_pack_order": [],
            "active_theme": None,
            "registry_hash": None,
            "registry_state": {},
            "resolved_effect_ids": [],
            "resolved_effects": [],
            "source_pack_ids": [],
            "element_roots": [],
            "staged_asset_ids": [],
            "staged_asset_root": None,
        }
        segment_provenance: list[dict[str, Any]] = []
        for result in results:
            for fragment in result.backend_fragments.values():
                legacy = fragment.get("legacy_v1")
                if not isinstance(legacy, Mapping):
                    continue
                segment_provenance.append(dict(legacy))
                for key in compatibility:
                    if key in legacy:
                        compatibility[key] = legacy[key]
                for key in (
                    "ffmpeg_specialization",
                    "audio_reactive_colour",
                ):
                    if key in legacy:
                        compatibility[key] = legacy[key]
        if len(segment_provenance) > 1:
            compatibility["segment_provenance"] = segment_provenance
        if supplied is not None:
            compatibility.update(dict(supplied))
        return compatibility

    @staticmethod
    def _alternatives(
        registry: RendererRegistry | PlannerRegistry | FinalizerRegistry,
        *,
        exclude: str | None = None,
    ) -> list[str]:
        try:
            return [
                candidate.id
                for candidate in registry.list()
                if candidate.id != exclude
            ]
        except RenderingRegistryError:
            return []

    @staticmethod
    def _recovery_for(alternatives: Sequence[str]) -> str:
        if alternatives:
            return "select one of these alternatives and retry: " + ", ".join(
                alternatives
            )
        return "install or select an execution-eligible compatible capability and retry"

    @staticmethod
    def _default_error_recovery(kind: str) -> str:
        return {
            "protocol": "regenerate the request with renderer protocol v1",
            "unsupported": "select a compatible renderer and retry",
            "binary_missing": "install the renderer's required binaries and retry",
            "timeout": "retry the render or increase the renderer timeout",
            "interrupted": "retry the render when interruption is no longer requested",
            "invalid_artifact": "rerender the artifact in a fresh invocation workspace",
            "internal": "retry the render in a fresh invocation workspace",
        }.get(kind, "retry the render after resolving the reported failure")

    def _observe(self, stage: str, **details: Any) -> None:
        if self._stage_observer is not None:
            self._stage_observer(stage, details)


__all__ = ["LegacyRenderRoutingWarning", "RenderService"]
