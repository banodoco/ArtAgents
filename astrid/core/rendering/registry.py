"""Static, trust-aware registries for timeline rendering capabilities.

Rendering manifests are data, not Python entrypoints.  Discovery in this
module only reads pack and renderer YAML/JSON files; backend code is not
imported until the transport layer (which deliberately lives elsewhere)
chooses to invoke a command.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, ClassVar, Generic, TypeVar

from astrid.core.foundation.hash import sha256_file
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.pack import (
    PackDefinition,
    discover_packs,
    pack_rendering_manifest_paths,
    validate_content_id_in_pack,
)
from astrid.core.pack.alias_resolver import (
    AliasResolutionError,
    AliasResolver,
    create_shared_alias_resolver,
)
from astrid.core.pack.discovery import DiscoveredPack, discover_pack_metadata
from astrid.core.pack.manifest import load_manifest_mapping
from astrid.core.pack.override import OverrideStore
from astrid.core.registry import CapabilityRegistry, RegistryError

from .contracts import FinalizerManifest, PlannerManifest, RendererManifest


ManifestT = TypeVar("ManifestT", RendererManifest, PlannerManifest, FinalizerManifest)

_FACADE_EXECUTOR_ID = "rendering.render"
_PROGRAMMATIC_RENDERER_ALIASES: tuple[tuple[str, str], ...] = (
    ("remotion", "rendering.remotion"),
    ("ffmpeg", "rendering.ffmpeg"),
)
_INSTALL_WARNING_VERSION = 1
_INSTALL_TRUST_METHODS = frozenset({"interactive", "cli_flag", "api", "test"})


class RenderingRegistryError(RegistryError):
    """A registry failure with stable, machine-readable context."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "registry_error",
        capability_kind: str = "rendering",
        requested_id: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.capability_kind = capability_kind
        self.requested_id = requested_id
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "capability_kind": self.capability_kind,
            "requested_id": self.requested_id,
            "message": str(self),
            "details": dict(self.details),
        }


class RendererRegistryError(RenderingRegistryError):
    """Renderer lookup or registration failed."""


class PlannerRegistryError(RenderingRegistryError):
    """Planner lookup or registration failed."""


class FinalizerRegistryError(RenderingRegistryError):
    """Finalizer lookup or registration failed."""


@dataclass(frozen=True)
class ExecutionEligibility:
    """Derived permission to execute one statically discovered candidate."""

    eligible: bool
    reason: str
    trust_method: str | None = None
    required_permissions: tuple[str, ...] = ()
    declared_permissions: tuple[str, ...] = ()
    accepted_permissions: tuple[str, ...] = ()
    active_revision: str | None = None

    @property
    def executable(self) -> bool:
        return self.eligible

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "reason": self.reason,
            "trust_method": self.trust_method,
            "required_permissions": list(self.required_permissions),
            "declared_permissions": list(self.declared_permissions),
            "accepted_permissions": list(self.accepted_permissions),
            "active_revision": self.active_revision,
        }


# Descriptive alias retained for callers that prefer the rendering-specific
# name while the evidence payload uses the shorter ``ExecutionEligibility``.
RenderingEligibility = ExecutionEligibility


@dataclass(frozen=True)
class RenderingCandidate(Generic[ManifestT]):
    """A parsed manifest plus immutable discovery and trust evidence."""

    manifest: ManifestT
    source_kind: str
    pack_id: str
    pack_root: Path
    manifest_path: Path
    manifest_digest: str
    priority_index: int
    eligibility: ExecutionEligibility

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def execution_eligible(self) -> bool:
        return self.eligibility.eligible

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "source_kind": self.source_kind,
            "pack_id": self.pack_id,
            "pack_root": str(self.pack_root),
            "manifest_path": str(self.manifest_path),
            "manifest_digest": self.manifest_digest,
            "priority_index": self.priority_index,
            "eligibility": self.eligibility.to_dict(),
        }


@dataclass(frozen=True)
class _PackTrust:
    eligible: bool
    reason: str
    trust_method: str | None = None
    accepted_permissions: tuple[str, ...] = ()
    active_revision: str | None = None


class _RenderingRegistry(CapabilityRegistry[str, RenderingCandidate[ManifestT]], Generic[ManifestT]):
    """Shared implementation for renderer, planner, and finalizer registries."""

    capability_kind: ClassVar[str]
    manifest_type: ClassVar[type[Any]]
    error_type: ClassVar[type[RenderingRegistryError]]
    rejects_facade: ClassVar[bool] = False

    def __init__(
        self,
        candidates: Iterable[RenderingCandidate[ManifestT]] = (),
        *,
        alias_resolver: AliasResolver | None = None,
        inspection_alias_resolver: AliasResolver | None = None,
        override_store: OverrideStore | None = None,
    ) -> None:
        super().__init__(alias_resolver=alias_resolver, override_store=override_store)
        self.inspection_alias_resolver = inspection_alias_resolver or alias_resolver
        self._discovered: dict[str, list[RenderingCandidate[ManifestT]]] = {}
        for candidate in candidates:
            self.register(candidate)

    def _error(
        self,
        message: str,
        *,
        code: str,
        requested_id: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> RenderingRegistryError:
        return self.error_type(
            message,
            code=code,
            capability_kind=self.capability_kind,
            requested_id=requested_id,
            details=details,
        )

    def register(
        self,
        candidate: RenderingCandidate[ManifestT],
    ) -> RenderingCandidate[ManifestT]:
        if not isinstance(candidate, RenderingCandidate):
            raise self._error(
                f"{self.capability_kind} registry entries must be RenderingCandidate objects",
                code="invalid_candidate",
            )
        if not isinstance(candidate.manifest, self.manifest_type):
            raise self._error(
                f"{self.capability_kind} candidate {candidate.id!r} has manifest type "
                f"{type(candidate.manifest).__name__}; expected {self.manifest_type.__name__}",
                code="invalid_candidate",
                requested_id=candidate.id,
            )
        if self.rejects_facade and candidate.id == _FACADE_EXECUTOR_ID:
            raise self._error(
                f"renderer id {_FACADE_EXECUTOR_ID!r} is reserved for the public "
                "facade executor and cannot be registered as a backend",
                code="facade_recursion",
                requested_id=candidate.id,
            )

        discovered = self._discovered.setdefault(candidate.id, [])
        discovered.append(candidate)
        discovered.sort(key=_candidate_priority_key)

        # The executable registry is intentionally a strict subset of static
        # discovery.  This is what prevents an untrusted, higher-precedence
        # declaration from shadowing trusted code.
        if candidate.execution_eligible:
            self._register_impl(
                candidate.id,
                candidate,
                priority_key=_candidate_priority_key,
            )
        return candidate

    def list(self) -> tuple[RenderingCandidate[ManifestT], ...]:
        winners = (self._resolve_entry(entry) for entry in self._entries.values())
        return tuple(sorted(winners, key=lambda candidate: candidate.id))

    def as_mapping(self) -> MappingProxyType[str, RenderingCandidate[ManifestT]]:
        return MappingProxyType(
            {
                capability_id: self._resolve_entry(entry)
                for capability_id, entry in self._entries.items()
            }
        )

    def candidates(
        self,
        capability_id: str | None = None,
        *,
        eligible: bool | None = None,
    ) -> tuple[RenderingCandidate[ManifestT], ...]:
        """Return static candidates, including non-executable discoveries."""

        if capability_id is None:
            values = [
                candidate
                for candidate_id in sorted(self._discovered)
                for candidate in self._discovered[candidate_id]
            ]
        else:
            canonical_id, _ = self._resolve_alias(capability_id, for_inspection=True)
            values = list(self._discovered.get(canonical_id, ()))
        if eligible is not None:
            values = [
                candidate
                for candidate in values
                if candidate.execution_eligible is eligible
            ]
        return tuple(values)

    @property
    def discovered_candidates(self) -> tuple[RenderingCandidate[ManifestT], ...]:
        """Compatibility-friendly property for static inspection surfaces."""

        return self.candidates()

    def inspect(self, capability_id: str) -> tuple[RenderingCandidate[ManifestT], ...]:
        """Return every statically discovered candidate for an id."""

        return self.candidates(capability_id)

    def get(self, capability_id: str) -> RenderingCandidate[ManifestT]:
        candidate, _ = self._resolve(capability_id)
        return candidate

    def get_manifest(self, capability_id: str) -> ManifestT:
        return self.get(capability_id).manifest

    def resolve_evidence(self, capability_id: str) -> dict[str, Any]:
        """Explain the complete alias/override/priority/trust resolution."""

        resolution_error: dict[str, Any] | None = None
        try:
            candidate, resolution = self._resolve(capability_id)
        except RenderingRegistryError as exc:
            if exc.code != "execution_ineligible":
                raise
            target_id = exc.details.get("target_id")
            discovered = self._discovered.get(str(target_id), ())
            if not discovered:
                raise
            candidate = discovered[0]
            resolution = {
                "canonical_id": exc.details.get("canonical_id", capability_id),
                "alias_chain": tuple(exc.details.get("alias_chain", ())),
                "override": exc.details.get("override"),
            }
            resolution_error = exc.to_dict()
        eligibility = candidate.eligibility.to_dict()
        return {
            "requested_id": capability_id,
            "canonical_id": resolution["canonical_id"],
            "resolved_id": candidate.id,
            "source_kind": candidate.source_kind,
            "pack_id": candidate.pack_id,
            "pack_root": str(candidate.pack_root),
            "manifest_path": str(candidate.manifest_path),
            "manifest_digest": candidate.manifest_digest,
            "alias_chain": list(resolution["alias_chain"]),
            "override": resolution["override"],
            "priority": candidate.priority_index,
            "priority_index": candidate.priority_index,
            "eligible": candidate.execution_eligible,
            "execution_eligible": candidate.execution_eligible,
            "eligibility_reason": candidate.eligibility.reason,
            "trust_method": candidate.eligibility.trust_method,
            "eligibility": eligibility,
            "resolution_error": resolution_error,
        }

    def validate_all(self) -> tuple[RenderingCandidate[ManifestT], ...]:
        if self.alias_resolver is not None:
            try:
                self.alias_resolver.validate_no_cycles()
            except AliasResolutionError as exc:
                raise self._error(
                    str(exc),
                    code="alias_cycle",
                ) from exc
        return self.list()

    def _resolve(
        self,
        requested_id: str,
    ) -> tuple[RenderingCandidate[ManifestT], dict[str, Any]]:
        canonical_id, alias_chain = self._resolve_alias(requested_id)
        if self.rejects_facade and canonical_id == _FACADE_EXECUTOR_ID:
            raise self._error(
                f"{self.capability_kind} {requested_id!r} resolves back to the "
                f"facade executor {_FACADE_EXECUTOR_ID!r}",
                code="facade_recursion",
                requested_id=requested_id,
                details={"canonical_id": canonical_id, "alias_chain": list(alias_chain)},
            )

        override_target = self._resolve_override_key(self.capability_kind, canonical_id)
        target_id = override_target or canonical_id
        override = (
            None
            if override_target is None
            else {"from": canonical_id, "to": override_target}
        )
        if self.rejects_facade and target_id == _FACADE_EXECUTOR_ID:
            raise self._error(
                f"override target {_FACADE_EXECUTOR_ID!r} for {self.capability_kind} "
                f"{canonical_id!r} resolves back to the facade executor",
                code="facade_recursion",
                requested_id=requested_id,
                details={"canonical_id": canonical_id, "override": override},
            )

        winner = self._winner_for(target_id)
        if winner is None:
            discovered = self._discovered.get(target_id, ())
            details: dict[str, Any] = {
                "canonical_id": canonical_id,
                "target_id": target_id,
                "alias_chain": list(alias_chain),
                "override": override,
            }
            if discovered:
                details["candidates"] = [candidate.to_dict() for candidate in discovered]
                reasons = "; ".join(
                    dict.fromkeys(candidate.eligibility.reason for candidate in discovered)
                )
                raise self._error(
                    f"{self.capability_kind} {target_id!r} is discoverable but not "
                    f"execution-eligible: {reasons}",
                    code="execution_ineligible",
                    requested_id=requested_id,
                    details=details,
                )
            if override_target is not None:
                raise self._error(
                    f"override target {target_id!r} for {self.capability_kind} "
                    f"{canonical_id!r} not found in executable registry",
                    code="invalid_override_target",
                    requested_id=requested_id,
                    details=details,
                )
            if alias_chain:
                raise self._error(
                    f"alias {requested_id!r} points to missing {self.capability_kind} "
                    f"{target_id!r}",
                    code="invalid_alias_target",
                    requested_id=requested_id,
                    details=details,
                )
            raise self._error(
                f"unknown {self.capability_kind} id {requested_id!r}",
                code="unknown_capability",
                requested_id=requested_id,
                details=details,
            )

        return winner, {
            "canonical_id": canonical_id,
            "alias_chain": alias_chain,
            "override": override,
        }

    def _resolve_alias(
        self,
        requested_id: str,
        *,
        for_inspection: bool = False,
    ) -> tuple[str, tuple[str, ...]]:
        if not isinstance(requested_id, str) or not requested_id:
            raise self._error(
                f"{self.capability_kind} id must be a non-empty string",
                code="invalid_id",
                requested_id=requested_id if isinstance(requested_id, str) else None,
            )
        resolver = (
            self.inspection_alias_resolver
            if for_inspection
            else self.alias_resolver
        )
        if resolver is None or not resolver.is_alias(requested_id):
            return requested_id, ()

        chain: list[str] = [requested_id]
        seen = {requested_id}
        current = requested_id
        try:
            while resolver.is_alias(current):
                record = resolver.get_record(current)
                if record is None:  # defensive against a concurrently-mutated resolver
                    break
                current = record.canonical_id
                chain.append(current)
                if current in seen:
                    raise AliasResolutionError(
                        f"alias cycle detected while resolving {requested_id!r}"
                    )
                seen.add(current)
        except AliasResolutionError as exc:
            raise self._error(
                str(exc),
                code="alias_cycle",
                requested_id=requested_id,
                details={"alias_chain": chain},
            ) from exc
        return current, tuple(chain)


class RendererRegistry(_RenderingRegistry[RendererManifest]):
    capability_kind = "renderer"
    manifest_type = RendererManifest
    error_type = RendererRegistryError
    rejects_facade = True


class PlannerRegistry(_RenderingRegistry[PlannerManifest]):
    capability_kind = "planner"
    manifest_type = PlannerManifest
    error_type = PlannerRegistryError


class FinalizerRegistry(_RenderingRegistry[FinalizerManifest]):
    capability_kind = "finalizer"
    manifest_type = FinalizerManifest
    error_type = FinalizerRegistryError


def load_default_registries(
    project_root: str | Path | None = None,
    *,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[RendererRegistry, PlannerRegistry, FinalizerRegistry]:
    """Discover static rendering manifests and build the three registries."""

    root = REPO_ROOT if project_root is None else Path(project_root).resolve()
    discovered = discover_pack_metadata(
        project_root=root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        discover_packs_fn=discover_packs,
    )
    pack_trust = {
        item.priority_index: _derive_pack_trust(item)
        for item in discovered
    }
    override_store = OverrideStore(root)

    renderers = RendererRegistry(
        override_store=override_store,
    )
    planners = PlannerRegistry(
        override_store=override_store,
    )
    finalizers = FinalizerRegistry(
        override_store=override_store,
    )

    for item in discovered:
        renderer_paths, planner_paths, finalizer_paths = pack_rendering_manifest_paths(
            item.pack
        )
        _load_candidates(
            renderers,
            item,
            renderer_paths,
            RendererManifest,
            pack_trust[item.priority_index],
        )
        _load_candidates(
            planners,
            item,
            planner_paths,
            PlannerManifest,
            pack_trust[item.priority_index],
        )
        _load_candidates(
            finalizers,
            item,
            finalizer_paths,
            FinalizerManifest,
            pack_trust[item.priority_index],
        )

    renderer_resolver, renderer_inspection_resolver = _build_alias_resolvers(
        discovered,
        kind="renderer",
        pack_trust=pack_trust,
        registry=renderers,
        programmatic_aliases=_PROGRAMMATIC_RENDERER_ALIASES,
        error_type=RendererRegistryError,
    )
    planner_resolver, planner_inspection_resolver = _build_alias_resolvers(
        discovered,
        kind="planner",
        pack_trust=pack_trust,
        registry=planners,
        error_type=PlannerRegistryError,
    )
    finalizer_resolver, finalizer_inspection_resolver = _build_alias_resolvers(
        discovered,
        kind="finalizer",
        pack_trust=pack_trust,
        registry=finalizers,
        error_type=FinalizerRegistryError,
    )
    renderers.alias_resolver = renderer_resolver
    renderers.inspection_alias_resolver = renderer_inspection_resolver
    planners.alias_resolver = planner_resolver
    planners.inspection_alias_resolver = planner_inspection_resolver
    finalizers.alias_resolver = finalizer_resolver
    finalizers.inspection_alias_resolver = finalizer_inspection_resolver

    renderers.validate_all()
    planners.validate_all()
    finalizers.validate_all()
    return renderers, planners, finalizers


def _candidate_priority_key(candidate: RenderingCandidate[Any]) -> tuple[int, str, str]:
    return (
        candidate.priority_index,
        str(candidate.manifest_path),
        candidate.manifest_digest,
    )


def _load_candidates(
    registry: _RenderingRegistry[Any],
    discovered: DiscoveredPack,
    manifest_paths: Iterable[Path],
    manifest_type: type[ManifestT],
    trust: _PackTrust,
) -> None:
    for manifest_path in manifest_paths:
        try:
            payload = load_manifest_mapping(
                manifest_path,
                manifest_kind=registry.capability_kind,
            )
            manifest = manifest_type.from_dict(payload)
            validate_content_id_in_pack(
                manifest.id,
                discovered.pack,
                content_type=registry.capability_kind,
            )
            digest = sha256_file(manifest_path)
        except Exception as exc:
            if isinstance(exc, RenderingRegistryError):
                raise
            raise registry._error(
                f"invalid {registry.capability_kind} manifest {manifest_path}: {exc}",
                code="invalid_manifest",
                details={
                    "pack_id": discovered.id,
                    "manifest_path": str(manifest_path),
                },
            ) from exc

        eligibility = _candidate_eligibility(
            discovered.pack,
            manifest.required_permissions,
            trust,
        )
        registry.register(
            RenderingCandidate(
                manifest=manifest,
                source_kind=discovered.source_kind,
                pack_id=discovered.id,
                pack_root=discovered.pack_dir.resolve(),
                manifest_path=manifest_path.resolve(),
                manifest_digest=digest,
                priority_index=discovered.priority_index,
                eligibility=eligibility,
            )
        )


def _candidate_eligibility(
    pack: PackDefinition,
    required_permissions: Iterable[str],
    trust: _PackTrust,
) -> ExecutionEligibility:
    required = tuple(required_permissions)
    declared = tuple(permission.id for permission in pack.permissions)
    common = {
        "trust_method": trust.trust_method,
        "required_permissions": required,
        "declared_permissions": declared,
        "accepted_permissions": trust.accepted_permissions,
        "active_revision": trust.active_revision,
    }
    if not trust.eligible:
        return ExecutionEligibility(False, trust.reason, **common)

    missing_declarations = sorted(set(required) - set(declared))
    if missing_declarations:
        return ExecutionEligibility(
            False,
            "manifest requires permissions not declared by its pack: "
            + ", ".join(missing_declarations),
            **common,
        )

    if trust.active_revision is not None:
        missing_acceptance = sorted(set(required) - set(trust.accepted_permissions))
        if missing_acceptance:
            return ExecutionEligibility(
                False,
                "installed pack permissions were not accepted: "
                + ", ".join(missing_acceptance),
                **common,
            )

    return ExecutionEligibility(True, trust.reason, **common)


def _derive_pack_trust(discovered: DiscoveredPack) -> _PackTrust:
    source_kind = discovered.source_kind
    if source_kind == "source":
        return _PackTrust(
            True,
            "source-tree pack is execution-eligible",
            trust_method="source_tree",
        )
    if source_kind == "local":
        return _PackTrust(
            True,
            "project-local pack is execution-eligible",
            trust_method="project_local",
        )
    if source_kind == "extra":
        return _PackTrust(
            True,
            "pack root was explicitly supplied by the operator",
            trust_method="explicit_extra_pack_root",
        )
    if source_kind == "env":
        return _PackTrust(
            False,
            "environment-discovered packs are inspectable but not executable",
        )
    return _PackTrust(False, f"unknown pack source kind {source_kind!r}")


def _installed_pack_trust(pack: PackDefinition) -> _PackTrust:
    root = pack.root.resolve()
    revision_name = root.name
    if root.parent.name != "revisions":
        return _PackTrust(False, "installed pack revision is outside the revisions directory")
    install_root = root.parent.parent.resolve()
    if install_root.name != pack.id:
        return _PackTrust(False, "installed pack root does not match its pack id")

    active_link = install_root / "active"
    if not active_link.is_symlink():
        return _PackTrust(False, "installed pack has no active revision symlink")
    try:
        active_revision = active_link.resolve(strict=True)
    except OSError:
        return _PackTrust(False, "installed pack active revision symlink is broken")
    if active_revision != root:
        return _PackTrust(False, "discovered installed revision is not the active revision")

    record_path = root / ".astrid" / "install.json"
    if not record_path.is_file():
        return _PackTrust(False, "active installed revision is missing its install record")
    try:
        raw_record = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(raw_record, dict):
            raise TypeError("install record must be a JSON object")
        record = InstallRecord.from_dict(raw_record)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return _PackTrust(False, f"active installed revision has a corrupt install record: {exc}")

    try:
        mismatch = _install_record_mismatch(
            pack,
            record,
            install_root=install_root,
            revision_name=revision_name,
        )
    except Exception as exc:
        return _PackTrust(
            False,
            "active installed revision has a malformed install audit: "
            f"{type(exc).__name__}: {exc}",
        )
    if mismatch is not None:
        return _PackTrust(False, mismatch)

    try:
        accepted, acceptance_error = _accepted_permission_ids(pack, record)
    except Exception as exc:
        return _PackTrust(
            False,
            "active installed revision has malformed accepted permissions: "
            f"{type(exc).__name__}: {exc}",
        )
    if acceptance_error is not None:
        return _PackTrust(False, acceptance_error)

    return _PackTrust(
        True,
        "active installed revision has a valid trust audit and accepted permissions",
        trust_method=record.trust_method,
        accepted_permissions=accepted,
        active_revision=revision_name,
    )


def _install_record_mismatch(
    pack: PackDefinition,
    record: InstallRecord,
    *,
    install_root: Path,
    revision_name: str,
) -> str | None:
    if record.pack_id != pack.id:
        return "install record pack id does not match the discovered pack"
    if record.version != pack.version:
        return "install record version does not match the discovered pack"
    if pack.schema_version and str(record.schema_version) != pack.schema_version:
        return "install record schema version does not match the discovered pack"
    if record.active is not True:
        return "install record does not mark the active revision active"
    if record.revision != revision_name:
        return "install record revision does not match the active revision"
    try:
        recorded_install_root = Path(record.install_root).expanduser().resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return "install record contains an invalid install root"
    if recorded_install_root != install_root:
        return "install record root does not match the active installation"
    if not record.manifest_digest:
        return "install record is missing its pack manifest digest"
    try:
        current_digest = sha256_file(pack.manifest_path)
    except OSError:
        return "installed pack manifest cannot be hashed"
    if record.manifest_digest != current_digest:
        return "install record manifest digest does not match the installed pack"
    if not _valid_audit_timestamp(record.trust_acknowledged_at):
        return "install record is missing a valid trust acknowledgement timestamp"
    if not _valid_audit_timestamp(record.last_validation_time):
        return "install record is missing a valid validation timestamp"
    if not isinstance(record.trust_method, str) or not record.trust_method.strip():
        return "install record is missing its trust acknowledgement method"
    if record.trust_method not in _INSTALL_TRUST_METHODS:
        return "install record contains an unknown trust acknowledgement method"
    if not isinstance(record.trust_actor, str) or not record.trust_actor.strip():
        return "install record is missing its trust acknowledgement actor"
    if record.no_sandbox_warning_version != _INSTALL_WARNING_VERSION:
        return "install record does not contain the current no-sandbox acknowledgement"
    if not isinstance(record.trust_summary, dict) or not record.trust_summary:
        return "install record is missing its trust summary"
    if record.trust_summary.get("pack_id") != pack.id:
        return "install trust summary does not match the discovered pack"
    trust_block = record.trust_summary.get("trust")
    if not isinstance(trust_block, dict):
        return "install trust summary is missing its trust disclosure"
    if (
        trust_block.get("sandbox") != "none"
        or trust_block.get("runs_with_user_process_permissions") is not True
        or trust_block.get("permission_enforcement") != "disclosure_only"
    ):
        return "install trust summary contains an invalid trust disclosure"
    return None


def _valid_audit_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _accepted_permission_ids(
    pack: PackDefinition,
    record: InstallRecord,
) -> tuple[tuple[str, ...], str | None]:
    accepted_raw = record.permissions_accepted
    if not isinstance(accepted_raw, list):
        return (), "install record permissions_accepted must be an array"
    if any(not isinstance(item, dict) for item in accepted_raw):
        return (), "install record contains a malformed accepted permission"

    expected = [permission.to_dict() for permission in pack.permissions]
    if accepted_raw != expected:
        return (), "install record accepted permissions do not match the installed pack"
    if record.trust_summary.get("permissions") != accepted_raw:
        return (), "install trust summary permissions do not match the accepted permissions"

    accepted_ids = tuple(str(item["id"]) for item in accepted_raw)
    if len(accepted_ids) != len(set(accepted_ids)):
        return (), "install record contains duplicate accepted permissions"
    return accepted_ids, None


def _build_alias_resolvers(
    discovered: tuple[DiscoveredPack, ...],
    *,
    kind: str,
    pack_trust: Mapping[int, _PackTrust],
    registry: _RenderingRegistry[Any],
    error_type: type[RenderingRegistryError],
    programmatic_aliases: Iterable[tuple[str, str]] = (),
) -> tuple[AliasResolver, AliasResolver]:
    # Validate every discovered alias graph, including inspect-only packs.  A
    # separate trusted resolver is then built so environment/corrupt install
    # metadata cannot redirect executable capability resolution.
    try:
        inspection_resolver = create_shared_alias_resolver()
        _populate_alias_resolver(
            inspection_resolver,
            discovered,
            kind=kind,
            eligible_only=False,
            pack_trust=pack_trust,
            registry=registry,
            programmatic_aliases=programmatic_aliases,
        )
        resolver = create_shared_alias_resolver()
        _populate_alias_resolver(
            resolver,
            discovered,
            kind=kind,
            eligible_only=True,
            pack_trust=pack_trust,
            registry=registry,
            programmatic_aliases=programmatic_aliases,
        )
        inspection_resolver.validate_no_cycles()
        resolver.validate_no_cycles()
        return resolver, inspection_resolver
    except AliasResolutionError as exc:
        raise error_type(
            str(exc),
            code="alias_cycle",
            capability_kind=kind,
        ) from exc


def _populate_alias_resolver(
    resolver: AliasResolver,
    discovered: tuple[DiscoveredPack, ...],
    *,
    kind: str,
    eligible_only: bool,
    pack_trust: Mapping[int, _PackTrust],
    registry: _RenderingRegistry[Any],
    programmatic_aliases: Iterable[tuple[str, str]] = (),
) -> None:
    if eligible_only:
        _populate_executable_alias_resolver(
            resolver,
            discovered,
            kind=kind,
            pack_trust=pack_trust,
            registry=registry,
            programmatic_aliases=programmatic_aliases,
        )
        return

    # Alias collisions follow the same precedence as candidates.  Register
    # lowest-precedence packs first so a lower priority_index wins last.
    for item in reversed(discovered):
        aliases = [
            alias
            for alias in item.pack.aliases
            if alias.get("kind") == kind
        ]
        if aliases:
            resolver.register_pack_aliases(item.id, aliases)
    for alias, canonical_id in programmatic_aliases:
        resolver.register_alias(
            alias,
            canonical_id,
            source_pack_id="astrid.core",
        )


def _populate_executable_alias_resolver(
    resolver: AliasResolver,
    discovered: tuple[DiscoveredPack, ...],
    *,
    kind: str,
    pack_trust: Mapping[int, _PackTrust],
    registry: _RenderingRegistry[Any],
    programmatic_aliases: Iterable[tuple[str, str]],
) -> None:
    """Register the highest-precedence executable declaration per alias.

    Candidates are retained in their real registration order so that a
    declaration whose chain ends outside the executable graph can fall back
    to the declaration it would otherwise have overwritten.  Peeling the
    deepest dangling hop first preserves upstream aliases when an
    intermediate alias has a usable lower-precedence declaration.

    A core compatibility alias may also terminate at a canonical id with an
    explicit override.  That alias remains only as the routing key needed to
    apply the override; normal winner selection still enforces eligibility on
    the override target.
    """

    declarations: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for item in reversed(discovered):
        if not pack_trust[item.priority_index].eligible:
            continue
        for alias in item.pack.aliases:
            if alias.get("kind") != kind:
                continue
            alias_name = alias.get("alias")
            canonical_id = alias.get("canonical_id")
            if not alias_name or not canonical_id:
                raise AliasResolutionError(
                    f"pack {item.id!r}: alias entry missing 'alias' or 'canonical_id'"
                )
            declarations.setdefault(str(alias_name), []).append((item.id, alias))

    for alias_name, canonical_id in programmatic_aliases:
        declarations.setdefault(alias_name, []).append(
            (
                "astrid.core",
                {"alias": alias_name, "canonical_id": canonical_id},
            )
        )

    selected_indexes = {
        alias_name: len(candidates) - 1
        for alias_name, candidates in declarations.items()
    }
    selected = {
        alias_name: candidates[-1]
        for alias_name, candidates in declarations.items()
    }

    override_routing_aliases: set[str] = set()
    while True:
        blocked: list[str] = []
        override_routing_aliases = set()
        for alias_name, (source_pack_id, declaration) in selected.items():
            target = declaration.get("canonical_id")
            if not isinstance(target, str):
                blocked.append(alias_name)
                continue
            if target in selected or target in registry._entries:
                continue
            if (
                registry._resolve_override_key(kind, target) is not None
            ):
                override_routing_aliases.add(alias_name)
                continue
            blocked.append(alias_name)
        if not blocked:
            break

        for alias_name in blocked:
            next_index = selected_indexes[alias_name] - 1
            selected_indexes[alias_name] = next_index
            if next_index < 0:
                del selected[alias_name]
            else:
                selected[alias_name] = declarations[alias_name][next_index]

    for alias_name, (source_pack_id, declaration) in selected.items():
        if (
            alias_name not in override_routing_aliases
            and not _alias_target_can_participate(
                declaration,
                registry,
                aliases=selected,
                override_routing_aliases=override_routing_aliases,
            )
        ):
            continue
        resolver.register_alias(
            alias_name,
            str(declaration["canonical_id"]),
            deprecated=bool(declaration.get("deprecated", False)),
            deprecation_message=str(declaration.get("deprecation_message", "")),
            source_pack_id=source_pack_id,
        )


def _alias_target_can_participate(
    alias: Mapping[str, Any],
    registry: _RenderingRegistry[Any],
    *,
    aliases: Mapping[str, tuple[str, Mapping[str, Any]]],
    override_routing_aliases: set[str] | frozenset[str] = frozenset(),
) -> bool:
    """Return whether a chain reaches an executable or override-routed terminal."""

    target = alias.get("canonical_id")
    if not isinstance(target, str):
        return False

    seen: set[str] = set()
    while target in aliases:
        if target in override_routing_aliases:
            return True
        if target in seen:
            raise AliasResolutionError(f"alias cycle detected while resolving {target!r}")
        seen.add(target)
        target = aliases[target][1].get("canonical_id")
        if not isinstance(target, str):
            return False
    if target in registry._entries:
        return True
    # A missing canonical terminal is still reachable when an override
    # routes it to an executable implementation (alias -> canonical ->
    # override ordering is frozen).
    return registry._resolve_override_key(registry.capability_kind, target) is not None


__all__ = [
    "ExecutionEligibility",
    "FinalizerRegistry",
    "FinalizerRegistryError",
    "PlannerRegistry",
    "PlannerRegistryError",
    "RendererRegistry",
    "RendererRegistryError",
    "RenderingCandidate",
    "RenderingRegistryError",
    "load_default_registries",
]
