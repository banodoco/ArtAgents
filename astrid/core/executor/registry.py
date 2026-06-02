"""Registry and discovery helpers for Astrid executors."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterable

from astrid._paths import REPO_ROOT
from astrid.core.alias_resolver import (
    AliasResolver,
    _register_pack_aliases,
    create_shared_alias_resolver,
    extract_pack_aliases,
)
from astrid.core.dirty import detect_local_edits, read_fork_state, write_fork_state
from astrid.core.manifest import ManifestParseError, dump_manifest_payload, load_manifest_mapping
from astrid.core.pack import (
    discover_packs,
    ensure_local_pack,
    iter_executor_roots,
    validate_content_id_in_pack,
)
from astrid.core.pack_discovery import discover_packs_ordered
from astrid.core.pack_resolver import PackResolver

from .banodoco_catalog import BanodocoCatalogConfig, load_banodoco_catalog_executors
from .folder import load_folder_executors
from .schema import ExecutorDefinition, ExecutorValidationError, validate_executor_definition

if TYPE_CHECKING:
    from astrid.core.override import OverrideStore

BUILTIN_STEP_ORDER: tuple[str, ...] = (
    "transcribe",
    "scenes",
    "quality_zones",
    "shots",
    "triage",
    "scene_describe",
    "quote_scout",
    "pool_build",
    "pool_merge",
    "arrange",
    "cut",
    "refine",
    "render",
    "editor_review",
    "validate",
)


class ExecutorRegistryError(ExecutorValidationError):
    """Raised when a executor registry is inconsistent."""


class ExecutorRegistry:
    """Small in-memory registry keyed by executor id."""

    def __init__(
        self,
        executors: Iterable[ExecutorDefinition | dict[str, Any]] = (),
        *,
        alias_resolver: AliasResolver | None = None,
        override_store: "OverrideStore | None" = None,
    ) -> None:
        self._executors: dict[str, list[ExecutorDefinition]] = {}
        self.alias_resolver = alias_resolver
        self.override_store = override_store
        for executor in executors:
            self.register(executor)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_entry(entry: list[ExecutorDefinition] | ExecutorDefinition) -> ExecutorDefinition:
        """Return the winning definition from a storage entry.

        Handles both list entries (from ``register()``) and scalar values
        (from legacy code that assigns directly to ``_executors[id]``).
        """
        if isinstance(entry, list):
            return entry[0]
        return entry

    @staticmethod
    def _iter_entries(entry: list[ExecutorDefinition] | ExecutorDefinition) -> Iterable[ExecutorDefinition]:
        """Yield all definitions from a storage entry (winner + shadowed)."""
        if isinstance(entry, list):
            yield from entry
        else:
            yield entry

    def _resolve_requested_id(self, executor_id: str) -> str:
        """Resolve *executor_id* to a canonical registry key."""
        resolver = self.alias_resolver
        canonical_id = resolver.resolve(executor_id) if resolver else executor_id
        if canonical_id in self._executors:
            return canonical_id
        if resolver is not None and executor_id != canonical_id and resolver.is_alias(executor_id):
            raise KeyError(
                f"alias {executor_id!r} points to missing executor {canonical_id!r}"
            )
        raise KeyError(f"unknown executor id {executor_id!r}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, executor: ExecutorDefinition | dict[str, Any]) -> ExecutorDefinition:
        definition = validate_executor_definition(executor)
        if definition.id not in self._executors:
            self._executors[definition.id] = []
        self._executors[definition.id].append(definition)
        self._executors[definition.id].sort(
            key=lambda d: int(d.metadata.get("priority", 30))
        )
        return definition

    def get(self, executor_id: str) -> ExecutorDefinition:
        canonical_id = self._resolve_requested_id(executor_id)
        definition = self._resolve_entry(self._executors[canonical_id])

        if self.override_store is not None:
            target_id = self.override_store.resolve("executor", canonical_id)
            if target_id is not None and target_id != canonical_id:
                if target_id not in self._executors:
                    raise ExecutorRegistryError(
                        f"override target {target_id!r} for executor {canonical_id!r} not found in registry"
                    )
                return self._resolve_entry(self._executors[target_id])

        return definition

    def _iter_all(self) -> Iterable[ExecutorDefinition]:
        """Yield every registered definition (including shadowed)."""
        for entry in self._executors.values():
            yield from self._iter_entries(entry)

    def list(self, kind: str | None = None) -> tuple[ExecutorDefinition, ...]:
        if kind is not None and kind not in {"built_in", "external"}:
            raise ExecutorRegistryError("kind must be one of ['built_in', 'external']")
        # Winners only (first entry per id after priority sort).
        executors = (self._resolve_entry(entry) for entry in self._executors.values())
        if kind is not None:
            executors = [executor for executor in executors if executor.kind == kind]
        return tuple(sorted(executors, key=lambda executor: executor.id))

    def validate_all(self) -> tuple[ExecutorDefinition, ...]:
        # Validate winners only — shadowed entries intentionally not validated.
        for executor in (self._resolve_entry(entry) for entry in self._executors.values()):
            validate_executor_definition(executor)
        self._validate_graph_references()
        if self.alias_resolver is not None:
            self.alias_resolver.validate_no_cycles()
            # Cross-check: every alias must resolve to a known executor.
            for alias, record in self.alias_resolver._aliases.items():
                target = self.alias_resolver.resolve(alias)
                if target not in self._executors:
                    raise ExecutorRegistryError(
                        f"alias {alias!r} resolves to unknown executor {target!r}"
                    )
        return self.list()

    def to_dict(self, kind: str | None = None) -> dict[str, Any]:
        return {"executors": [executor.to_dict() for executor in self.list(kind=kind)]}

    def to_json(self, *, kind: str | None = None, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(kind=kind), indent=indent, sort_keys=True)

    def as_mapping(self) -> MappingProxyType[str, ExecutorDefinition]:
        # Winners only.
        return MappingProxyType(
            {eid: self._resolve_entry(entry) for eid, entry in self._executors.items()}
        )

    def _validate_graph_references(self) -> None:
        known_ids = set(self._executors)  # keys are strings, unchanged
        resolver = self.alias_resolver
        # Winners only.
        for executor in (self._resolve_entry(entry) for entry in self._executors.values()):
            for dependency in executor.graph.depends_on:
                resolved = resolver.resolve(dependency) if resolver else dependency
                if resolved not in known_ids:
                    raise ExecutorRegistryError(f"executor {executor.id!r} depends on unknown executor {resolved!r}")
                if resolved == executor.id:
                    raise ExecutorRegistryError(f"executor {executor.id!r} cannot depend on itself")

    def fork(
        self,
        executor_id: str,
        *,
        project_root: str | Path,
        overwrite: bool = False,
        deep: bool = False,
    ) -> Path:
        """Fork *executor_id* into the local scratch pack under *project_root*.

        Returns the absolute path to the forked executor directory.
        """
        definition = self.get(executor_id)
        local_id = executor_id.split(".", 1)[1] if "." in executor_id else executor_id
        target = (Path(project_root) / "astrid" / "packs" / "local" / "executors" / local_id).resolve()

        ensure_local_pack(project_root=project_root)

        if target.exists() and not overwrite:
            raise ExecutorRegistryError(
                f"executor fork target already exists: {target}"
            )

        # Resolve content_root: prefer content_root (set by _attach_pack_metadata),
        # fall back to executor_root (set by _attach_folder_metadata).
        content_root_str = definition.metadata.get("content_root") or definition.metadata.get("executor_root")
        if not content_root_str:
            raise ExecutorRegistryError(
                f"cannot fork executor {executor_id!r}: no content_root or executor_root in metadata"
            )
        content_root = Path(content_root_str)
        if not content_root.is_dir():
            raise ExecutorRegistryError(
                f"cannot fork executor {executor_id!r}: content_root {content_root} is not a directory"
            )

        # Copy the content root to the target.
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(content_root, target)

        # Rewrite the manifest id and add fork provenance.
        _rewrite_executor_manifest_fork(target, local_id, forked_from=executor_id, upstream_version=definition.version)

        # Persist fork state for local-edit detection.
        write_fork_state(target, forked_from=executor_id, upstream_version=definition.version)

        # Deep fork: recursively fork all depends_on executors.
        if deep:
            resolver = self.alias_resolver
            already_forked: set[str] = {executor_id}
            for dep_id in definition.graph.depends_on:
                resolved = resolver.resolve(dep_id) if resolver else dep_id
                if resolved not in already_forked:
                    already_forked.add(resolved)
                    self.fork(resolved, project_root=project_root, overwrite=overwrite, deep=True)

        return target


def load_default_registry(
    banodoco_config: BanodocoCatalogConfig | None = None,
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> ExecutorRegistry:
    packs = _discover_executor_packs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, extract_pack_aliases(packs, kind="executor"))
    registry = ExecutorRegistry(alias_resolver=resolver)
    for executor in _load_pack_executors_from_packs(packs):
        registry.register(executor)
    if banodoco_config is not None and banodoco_config.enabled:
        for executor in load_banodoco_catalog_executors(banodoco_config):
            registry.register(executor)
    registry.validate_all()
    return registry


def load_pack_executors(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[ExecutorDefinition, ...]:
    packs = _discover_executor_packs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        include_installed=include_installed,
    )
    return _load_pack_executors_from_packs(packs)


def _discover_executor_packs(
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


def _load_pack_executors_from_packs(
    packs: Iterable[Any],
) -> tuple[ExecutorDefinition, ...]:
    executors: list[ExecutorDefinition] = []
    for pack in packs:
        for root in iter_executor_roots(pack):
            for executor in load_folder_executors(root):
                validate_content_id_in_pack(executor.id, pack, content_type="executor")
                executors.append(_attach_pack_metadata(executor, pack.id, content_root=root))
    return tuple(executors)


def _attach_pack_metadata(
    executor: ExecutorDefinition,
    pack_id: str,
    *,
    content_root: Path | None = None,
) -> ExecutorDefinition:
    metadata = dict(executor.metadata)
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
    return validate_executor_definition(replace(executor, metadata=metadata))


def _rewrite_executor_manifest_fork(
    target: Path,
    local_id: str,
    *,
    forked_from: str,
    upstream_version: str,
) -> None:
    """Rewrite the executor manifest in *target* with the forked identity."""
    EXECUTOR_MANIFEST_NAMES = ("executor.yaml", "executor.yml", "executor.json")
    manifest_path = None
    for name in EXECUTOR_MANIFEST_NAMES:
        candidate = target / name
        if candidate.is_file():
            manifest_path = candidate
            break

    if manifest_path is None:
        return  # No manifest to rewrite — executor was loaded via executor.py

    try:
        data = load_manifest_mapping(manifest_path, manifest_kind="executor")
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


def resolve_executor_callable(executor: ExecutorDefinition):
    """Resolve an executor's manifest-declared Python runtime callable."""

    return PackResolver().resolve(executor.metadata, owner_id=executor.id)


__all__ = [
    "BUILTIN_STEP_ORDER",
    "ExecutorRegistry",
    "ExecutorRegistryError",
    "BanodocoCatalogConfig",
    "load_pack_executors",
    "load_default_registry",
    "resolve_executor_callable",
]
