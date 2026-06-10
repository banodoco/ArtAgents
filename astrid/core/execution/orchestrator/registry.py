"""Registry and discovery helpers for Astrid orchestrators."""

from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterable

from astrid.core.dirty import detect_local_edits, read_fork_state, write_fork_state
from astrid.core.execution.executor.registry import ExecutorRegistry
from astrid.core.execution.executor.registry import (
    load_default_registry as load_default_executor_registry,
)
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.pack import (
    discover_packs,
    ensure_local_pack,
    iter_orchestrator_roots,
    validate_content_id_in_pack,
)
from astrid.core.pack.alias_resolver import (
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)
from astrid.core.pack.discovery import discover_packs_ordered
from astrid.core.pack.manifest import (
    ManifestParseError,
    dump_manifest_payload,
    load_manifest_mapping,
)
from astrid.core.registry import CapabilityRegistry

from .folder import load_folder_orchestrators
from .schema import (
    OrchestratorDefinition,
    OrchestratorValidationError,
    validate_orchestrator_definition,
)

if TYPE_CHECKING:
    from astrid.core.pack.override import OverrideStore

logger = logging.getLogger(__name__)


class OrchestratorRegistryError(OrchestratorValidationError):
    """Raised when an orchestrator registry is inconsistent."""


class OrchestratorRegistry(CapabilityRegistry[str, OrchestratorDefinition]):
    """Small in-memory registry keyed by orchestrator id.

    Inherits generic storage, conflict detection, and override-key
    resolution from :class:`CapabilityRegistry`.
    """

    def __init__(
        self,
        orchestrators: Iterable[OrchestratorDefinition | dict[str, Any]] = (),
        *,
        executor_registry: ExecutorRegistry | None = None,
        alias_resolver: AliasResolver | None = None,
        override_store: "OverrideStore | None" = None,
    ) -> None:
        super().__init__(alias_resolver=alias_resolver, override_store=override_store)
        self._executor_registry = executor_registry
        #: Nested map: orchestrator_id → child_capability_id → frozenset of output artifact_type values.
        self._child_output_types: dict[str, dict[str, frozenset[str]]] = {}
        for orchestrator in orchestrators:
            self.register(orchestrator)

    # ------------------------------------------------------------------
    # Backward-compat alias for pre-migration direct ``_orchestrators`` access
    # (e.g. ``test_orchestrator_runner_errors.py`` bypasses ``register()``).
    # ------------------------------------------------------------------

    @property
    def _orchestrators(self) -> dict[str, list[OrchestratorDefinition] | OrchestratorDefinition]:
        """Legacy alias for ``_entries`` — supports direct scalar writes."""
        return self._entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_requested_id(self, orchestrator_id: str) -> str:
        """Resolve *orchestrator_id* to a canonical registry key."""
        resolver = self.alias_resolver
        canonical_id = resolver.resolve(orchestrator_id) if resolver else orchestrator_id
        if canonical_id in self._entries:
            return canonical_id
        if resolver is not None and orchestrator_id != canonical_id and resolver.is_alias(orchestrator_id):
            raise KeyError(
                f"alias {orchestrator_id!r} points to missing orchestrator {canonical_id!r}"
            )
        raise KeyError(f"unknown orchestrator id {orchestrator_id!r}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, orchestrator: OrchestratorDefinition | dict[str, Any]) -> OrchestratorDefinition:
        definition = validate_orchestrator_definition(orchestrator)
        self._register_impl(
            definition.id,
            definition,
            priority_key=lambda d: int(d.metadata.get("priority", 30)),
        )
        return definition

    def get(self, orchestrator_id: str) -> OrchestratorDefinition:
        canonical_id = self._resolve_requested_id(orchestrator_id)
        definition = self._resolve_entry(self._entries[canonical_id])

        target_id = self._resolve_override_key("orchestrator", canonical_id)
        if target_id is not None and target_id != canonical_id:
            if target_id not in self._entries:
                raise OrchestratorRegistryError(
                    f"override target {target_id!r} for orchestrator {canonical_id!r} not found in registry"
                )
            return self._resolve_entry(self._entries[target_id])

        return definition

    def _iter_all(self) -> Iterable[OrchestratorDefinition]:
        """Yield every registered definition (including shadowed)."""
        for entry in self._entries.values():
            yield from self._iter_entries(entry)

    def list(self, kind: str | None = None) -> tuple[OrchestratorDefinition, ...]:
        if kind is not None and kind not in {"built_in", "external"}:
            raise OrchestratorRegistryError("kind must be one of ['built_in', 'external']")
        # Winners only (first entry per id after priority sort).
        orchestrators = (self._resolve_entry(entry) for entry in self._entries.values())
        if kind is not None:
            orchestrators = [orchestrator for orchestrator in orchestrators if orchestrator.kind == kind]
        return tuple(sorted(orchestrators, key=lambda orchestrator: orchestrator.id))

    def validate_all(
        self,
        *,
        executor_registry: ExecutorRegistry | None = None,
    ) -> tuple[OrchestratorDefinition, ...]:
        # Validate winners only — shadowed entries intentionally not validated.
        for orchestrator in (self._resolve_entry(entry) for entry in self._entries.values()):
            validate_orchestrator_definition(orchestrator)
        self._validate_child_executors(
            executor_registry=executor_registry,
            alias_resolver=self.alias_resolver,
        )
        self._validate_child_orchestrators(alias_resolver=self.alias_resolver)
        self._strict_child_type_check()
        if self.alias_resolver is not None:
            self.alias_resolver.validate_no_cycles()
            # Cross-check: every alias must resolve to a known orchestrator.
            # Skip aliases whose resolved target is a known executor — those
            # were registered as executor aliases (not orchestrator aliases)
            # and live in this resolver only via test scaffolding or shared
            # resolver setups.
            exec_reg = executor_registry or self._executor_registry
            exec_known = set(exec_reg.as_mapping()) if exec_reg else set()
            for alias, record in self.alias_resolver._aliases.items():
                target = self.alias_resolver.resolve(alias)
                if target not in self._entries:
                    if target not in exec_known:
                        raise OrchestratorRegistryError(
                            f"alias {alias!r} resolves to unknown orchestrator {target!r}"
                        )
        return self.list()

    def to_dict(self, kind: str | None = None) -> dict[str, Any]:
        return {"orchestrators": [orchestrator.to_dict() for orchestrator in self.list(kind=kind)]}

    def to_json(self, *, kind: str | None = None, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(kind=kind), indent=indent, sort_keys=True)

    def as_mapping(self) -> MappingProxyType[str, OrchestratorDefinition]:
        # Winners only.
        return MappingProxyType(
            {oid: self._resolve_entry(entry) for oid, entry in self._entries.items()}
        )

    def child_output_artifact_types(self, orchestrator_id: str) -> dict[str, frozenset[str]]:
        """Return a map of ``{child_capability_id: {output_artifact_types}}`` for *orchestrator_id*.

        Each child capability (executor or orchestrator) that declares at
        least one ``artifact_type`` on its outputs is included in the
        result.  Returns an empty dict when the orchestrator has no
        annotated children or the id is unknown.
        """
        canonical_id = self._resolve_requested_id(orchestrator_id)
        return dict(self._child_output_types.get(canonical_id, {}))

    def _validate_child_executors(
        self,
        *,
        executor_registry: ExecutorRegistry | None,
        alias_resolver: AliasResolver | None = None,
    ) -> None:
        registry = executor_registry or self._executor_registry or load_default_executor_registry()
        known_executor_ids = set(registry.as_mapping())
        # Resolve child executor references through the *executor* alias resolver
        # when it is populated (the orchestrator's own alias resolver maps
        # orchestrator ids, not executor ids).  Fall back to the orchestrator
        # resolver when the executor resolver carries no aliases, which can
        # happen in tests that register executor aliases on a shared resolver.
        exec_alias_resolver: AliasResolver | None = getattr(registry, 'alias_resolver', None)
        if exec_alias_resolver is not None and not exec_alias_resolver._aliases:
            exec_alias_resolver = None
        resolver = exec_alias_resolver or alias_resolver or self.alias_resolver
        # Build executor mapping for artifact_type collection.
        executor_mapping = registry.as_mapping()
        # Winners only.
        for orchestrator in (self._resolve_entry(entry) for entry in self._entries.values()):
            for child_executor in orchestrator.child_executors:
                resolved = resolver.resolve(child_executor) if resolver else child_executor
                if resolved not in known_executor_ids:
                    raise OrchestratorRegistryError(
                        f"orchestrator {orchestrator.id!r} references unknown child executor {resolved!r}"
                    )
            # Collect child executor output artifact types.
            child_map: dict[str, frozenset[str]] = {}
            for child_executor in orchestrator.child_executors:
                resolved = resolver.resolve(child_executor) if resolver else child_executor
                if resolved in executor_mapping:
                    exec_def = executor_mapping[resolved]
                    output_types: set[str] = set()
                    for output in exec_def.outputs:
                        if output.artifact_type:
                            output_types.add(output.artifact_type)
                    if output_types:
                        child_map[resolved] = frozenset(output_types)
            if child_map:
                self._child_output_types[orchestrator.id] = child_map

    def _validate_child_orchestrators(
        self,
        alias_resolver: AliasResolver | None = None,
    ) -> None:
        known_orchestrator_ids = set(self._entries)  # keys are strings
        resolver = alias_resolver or self.alias_resolver
        graph: dict[str, tuple[str, ...]] = {}
        # Winners only.
        for orchestrator in (self._resolve_entry(entry) for entry in self._entries.values()):
            children: list[str] = []
            for child_orchestrator in orchestrator.child_orchestrators:
                resolved = resolver.resolve(child_orchestrator) if resolver else child_orchestrator
                if resolved not in known_orchestrator_ids:
                    raise OrchestratorRegistryError(
                        f"orchestrator {orchestrator.id!r} references unknown child orchestrator {resolved!r}"
                    )
                if resolved == orchestrator.id:
                    raise OrchestratorRegistryError(f"orchestrator {orchestrator.id!r} cannot reference itself")
                children.append(resolved)
            graph[orchestrator.id] = tuple(children)
            # Collect child orchestrator output artifact types.
            child_map = self._child_output_types.get(orchestrator.id, {})
            for child_orchestrator in orchestrator.child_orchestrators:
                resolved = resolver.resolve(child_orchestrator) if resolver else child_orchestrator
                child_def = self._resolve_entry(self._entries[resolved])
                output_types: set[str] = set()
                for output in child_def.outputs:
                    if output.artifact_type:
                        output_types.add(output.artifact_type)
                if output_types:
                    child_map[resolved] = frozenset(output_types)
            if child_map:
                self._child_output_types[orchestrator.id] = child_map
        self._validate_no_cycles(graph)

    def _validate_no_cycles(self, graph: dict[str, tuple[str, ...]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []

        def visit(orchestrator_id: str) -> None:
            if orchestrator_id in visited:
                return
            if orchestrator_id in visiting:
                cycle = stack[stack.index(orchestrator_id) :] + [orchestrator_id]
                raise OrchestratorRegistryError(f"orchestrator cycle detected: {' -> '.join(cycle)}")
            visiting.add(orchestrator_id)
            stack.append(orchestrator_id)
            for child in graph.get(orchestrator_id, ()):
                visit(child)
            stack.pop()
            visiting.remove(orchestrator_id)
            visited.add(orchestrator_id)

        for orchestrator_id in sorted(graph):
            visit(orchestrator_id)

    def _strict_child_type_check(self) -> None:
        """Warn when ASTRID_STRICT_CHILD_TYPES is set and an orchestrator's
        input artifact_type is not produced by any child capability.

        This is a best-effort development aid — orchestrators often
        receive inputs from external sources (e.g. user-supplied files),
        so missing matches are warnings, not errors.
        """
        if not os.environ.get("ASTRID_STRICT_CHILD_TYPES"):
            return

        for orchestrator in (self._resolve_entry(entry) for entry in self._entries.values()):
            child_types = self._child_output_types.get(orchestrator.id, {})
            if not child_types:
                continue
            # Union of all child output artifact types.
            all_child_output_types: set[str] = set()
            for typeset in child_types.values():
                all_child_output_types.update(typeset)

            for port in orchestrator.inputs:
                if port.artifact_type and port.artifact_type not in all_child_output_types:
                    logger.warning(
                        "ASTRID_STRICT_CHILD_TYPES: orchestrator %r input %r has "
                        "artifact_type=%r not found in any child's output types. "
                        "Child output types: %s",
                        orchestrator.id,
                        port.name,
                        port.artifact_type,
                        sorted(all_child_output_types),
                    )

    def fork(
        self,
        orchestrator_id: str,
        *,
        project_root: str | Path,
        overwrite: bool = False,
        deep: bool = False,
    ) -> Path:
        """Fork *orchestrator_id* into the local scratch pack under *project_root*.

        Returns the absolute path to the forked orchestrator directory.

        When *deep* is ``True``, also recursively forks every child executor
        (via the attached ``ExecutorRegistry``) and child orchestrator.
        """
        definition = self.get(orchestrator_id)
        local_id = orchestrator_id.split(".", 1)[1] if "." in orchestrator_id else orchestrator_id
        target = (Path(project_root) / "astrid" / "packs" / "local" / "orchestrators" / local_id).resolve()

        ensure_local_pack(project_root=project_root)

        if target.exists() and not overwrite:
            raise OrchestratorRegistryError(
                f"orchestrator fork target already exists: {target}"
            )

        # Resolve content_root: prefer content_root (set by _attach_pack_metadata),
        # fall back to orchestrator_root (set by _attach_folder_metadata).
        content_root_str = definition.metadata.get("content_root") or definition.metadata.get("orchestrator_root")
        if not content_root_str:
            raise OrchestratorRegistryError(
                f"cannot fork orchestrator {orchestrator_id!r}: no content_root or orchestrator_root in metadata"
            )
        content_root = Path(content_root_str)
        if not content_root.is_dir():
            raise OrchestratorRegistryError(
                f"cannot fork orchestrator {orchestrator_id!r}: content_root {content_root} is not a directory"
            )

        # Copy the content root to the target.
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(content_root, target)

        # Rewrite the manifest id and add fork provenance.
        _rewrite_orchestrator_manifest_fork(
            target, local_id, forked_from=orchestrator_id, upstream_version=definition.version
        )

        # Persist fork state for local-edit detection.
        write_fork_state(target, forked_from=orchestrator_id, upstream_version=definition.version)

        # Deep fork: recursively fork child executors and child orchestrators.
        if deep:
            already_forked_orchestrators: set[str] = {orchestrator_id}
            already_forked_executors: set[str] = set()

            # Fork child executors via the attached ExecutorRegistry.
            executor_registry = self._executor_registry
            if executor_registry is not None and definition.child_executors:
                resolver = self.alias_resolver
                for child_id in definition.child_executors:
                    resolved = resolver.resolve(child_id) if resolver else child_id
                    if resolved not in already_forked_executors:
                        already_forked_executors.add(resolved)
                        try:
                            executor_registry.fork(
                                resolved, project_root=project_root, overwrite=overwrite, deep=True,
                            )
                        except Exception:
                            # If a child executor cannot be forked (e.g. it is already
                            # forked by another path), skip it gracefully.
                            pass

            # Fork child orchestrators recursively through this registry.
            if definition.child_orchestrators:
                resolver = self.alias_resolver
                for child_id in definition.child_orchestrators:
                    resolved = resolver.resolve(child_id) if resolver else child_id
                    if resolved not in already_forked_orchestrators:
                        already_forked_orchestrators.add(resolved)
                        try:
                            self.fork(resolved, project_root=project_root, overwrite=overwrite, deep=True)
                        except Exception:
                            pass

        return target


def load_default_registry(
    *,
    executor_registry: ExecutorRegistry | None = None,
    banodoco_config: Any | None = None,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> OrchestratorRegistry:
    active_executor_registry = executor_registry
    packs = _discover_orchestrator_packs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, extract_pack_aliases(packs, kind="orchestrator"))
    registry = OrchestratorRegistry(
        executor_registry=active_executor_registry,
        alias_resolver=resolver,
    )
    for orchestrator in _load_pack_orchestrators_from_packs(packs):
        registry.register(orchestrator)
    registry.validate_all(executor_registry=active_executor_registry)
    return registry


def load_pack_orchestrators(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[OrchestratorDefinition, ...]:
    packs = _discover_orchestrator_packs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    return _load_pack_orchestrators_from_packs(packs)


def _discover_orchestrator_packs(
    *,
    project_root: str | Path,
    extra_pack_roots: tuple[str, ...],
    include_installed: bool,
) -> tuple[Any, ...]:
    return discover_packs_ordered(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
        discover_packs_fn=discover_packs,
    )


def _load_pack_orchestrators_from_packs(
    packs: Iterable[Any],
) -> tuple[OrchestratorDefinition, ...]:
    orchestrators: list[OrchestratorDefinition] = []
    for pack in packs:
        for root in iter_orchestrator_roots(pack):
            for orchestrator in load_folder_orchestrators(root):
                validate_content_id_in_pack(orchestrator.id, pack, content_type="orchestrator")
                orchestrators.append(_attach_pack_metadata(orchestrator, pack.id, content_root=root))
    return tuple(orchestrators)


def _attach_pack_metadata(
    orchestrator: OrchestratorDefinition,
    pack_id: str,
    *,
    content_root: Path | None = None,
) -> OrchestratorDefinition:
    metadata = dict(orchestrator.metadata)
    metadata["source"] = "pack"
    metadata["source_pack"] = pack_id
    metadata["priority"] = 10 if pack_id == "local" else 30
    if content_root is not None:
        metadata["content_root"] = str(content_root)
    # SD5: detect local edits and merge fork state for local pack only
    if pack_id == "local" and content_root is not None:
        fork_state = read_fork_state(content_root)
        if fork_state is not None:
            for key in ("forked_from", "upstream_version", "compatibility_token"):
                if key in fork_state:
                    metadata.setdefault(key, fork_state[key])
        metadata["local_edit_state"] = detect_local_edits(
            content_root, forked_from=metadata.get("forked_from", "")
        )
    return validate_orchestrator_definition(replace(orchestrator, metadata=metadata))


def _rewrite_orchestrator_manifest_fork(
    target: Path,
    local_id: str,
    *,
    forked_from: str,
    upstream_version: str,
) -> None:
    """Rewrite the orchestrator manifest in *target* with the forked identity."""
    ORCHESTRATOR_MANIFEST_NAMES = ("orchestrator.yaml", "orchestrator.yml", "orchestrator.json")
    manifest_path = None
    for name in ORCHESTRATOR_MANIFEST_NAMES:
        candidate = target / name
        if candidate.is_file():
            manifest_path = candidate
            break

    if manifest_path is None:
        return  # No manifest to rewrite — orchestrator was loaded via orchestrator.py

    try:
        data = load_manifest_mapping(manifest_path, manifest_kind="orchestrator")
    except ManifestParseError:
        return  # Cannot parse, leave as-is

    new_id = f"local.{local_id}"
    data["id"] = new_id

    # Merge fork provenance into metadata.
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        data["metadata"] = metadata
    metadata["forked_from"] = forked_from
    metadata["upstream_version"] = upstream_version

    dump_manifest_payload(manifest_path, data)


__all__ = [
    "OrchestratorRegistry",
    "OrchestratorRegistryError",
    "load_pack_orchestrators",
    "load_default_registry",
]
