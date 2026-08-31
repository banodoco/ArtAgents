"""Registry and discovery helpers for Astrid executors."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Iterable

from astrid.core.dirty import detect_local_edits, read_fork_state, write_fork_state
from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.pack import (
    discover_packs,
    ensure_local_pack,
    iter_executor_roots,
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
from astrid.core.pack.override import OverrideStore
from astrid.core.pack.resolver import PackResolver
from astrid.core.registry import CapabilityRegistry

if TYPE_CHECKING:
    from .banodoco_catalog import BanodocoCatalogConfig
from .folder import load_folder_executors
from .schema import ExecutorDefinition, ExecutorValidationError, validate_executor_definition

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


_LOGGER = logging.getLogger(__name__)


class ExecutorRegistry(CapabilityRegistry[str, ExecutorDefinition]):
    """Small in-memory registry keyed by executor id.

    Inherits generic storage, conflict detection, and override-key
    resolution from :class:`CapabilityRegistry`.
    """

    def __init__(
        self,
        executors: Iterable[ExecutorDefinition | dict[str, Any]] = (),
        *,
        alias_resolver: AliasResolver | None = None,
        override_store: "OverrideStore | None" = None,
    ) -> None:
        super().__init__(alias_resolver=alias_resolver, override_store=override_store)
        for executor in executors:
            self.register(executor)

    # ------------------------------------------------------------------
    # Backward-compat alias for pre-migration direct ``_executors`` access
    # (e.g. ``test_executor_runner_errors.py`` bypasses ``register()``).
    # ------------------------------------------------------------------

    @property
    def _executors(self) -> dict[str, list[ExecutorDefinition] | ExecutorDefinition]:
        """Legacy alias for ``_entries`` — supports direct scalar writes."""
        return self._entries

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_requested_id(self, executor_id: str) -> str:
        """Resolve *executor_id* to a canonical registry key."""
        resolver = self.alias_resolver
        canonical_id = resolver.resolve(executor_id) if resolver else executor_id
        if canonical_id in self._entries:
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
        self._register_impl(
            definition.id,
            definition,
            priority_key=lambda d: int(d.metadata.get("priority", 30)),
        )
        return definition

    def get(self, executor_id: str) -> ExecutorDefinition:
        canonical_id = self._resolve_requested_id(executor_id)
        definition = self._resolve_entry(self._entries[canonical_id])

        target_id = self._resolve_override_key("executor", canonical_id)
        if target_id is not None and target_id != canonical_id:
            if target_id not in self._entries:
                raise ExecutorRegistryError(
                    f"override target {target_id!r} for executor {canonical_id!r} not found in registry"
                )
            return self._resolve_entry(self._entries[target_id])

        return definition

    def _iter_all(self) -> Iterable[ExecutorDefinition]:
        """Yield every registered definition (including shadowed)."""
        for entry in self._entries.values():
            yield from self._iter_entries(entry)

    def list(self, kind: str | None = None) -> tuple[ExecutorDefinition, ...]:
        if kind is not None and kind not in {"built_in", "external"}:
            raise ExecutorRegistryError("kind must be one of ['built_in', 'external']")
        # Winners only (first entry per id after priority sort).
        executors = (self._resolve_entry(entry) for entry in self._entries.values())
        if kind is not None:
            executors = [executor for executor in executors if executor.kind == kind]
        return tuple(sorted(executors, key=lambda executor: executor.id))

    def validate_all(self) -> tuple[ExecutorDefinition, ...]:
        # Validate winners only — shadowed entries intentionally not validated.
        for executor in (self._resolve_entry(entry) for entry in self._entries.values()):
            validate_executor_definition(executor)
        self._validate_graph_references()
        if self.alias_resolver is not None:
            self.alias_resolver.validate_no_cycles()
            # Cross-check: every alias must resolve to a known executor.
            for alias, record in self.alias_resolver._aliases.items():
                target = self.alias_resolver.resolve(alias)
                if target not in self._entries:
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
            {eid: self._resolve_entry(entry) for eid, entry in self._entries.items()}
        )

    def _validate_graph_references(self) -> None:
        known_ids = set(self._entries)  # keys are strings, unchanged
        resolver = self.alias_resolver
        # Winners only.
        for executor in (self._resolve_entry(entry) for entry in self._entries.values()):
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
    banodoco_config: "BanodocoCatalogConfig | None" = None,
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
) -> ExecutorRegistry:
    packs = _discover_executor_packs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
    )
    resolver = create_shared_alias_resolver()
    _register_pack_aliases(resolver, extract_pack_aliases(packs, kind="executor"))
    registry = ExecutorRegistry(
        alias_resolver=resolver,
        override_store=OverrideStore(project_root),
    )
    for executor in _load_pack_executors_from_packs(packs):
        registry.register(executor)
    if banodoco_config is not None and banodoco_config.enabled:
        from .banodoco_catalog import load_banodoco_catalog_executors

        for executor in load_banodoco_catalog_executors(banodoco_config):
            registry.register(executor)
    registry.validate_all()
    return registry


def load_pack_executors(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
) -> tuple[ExecutorDefinition, ...]:
    packs = _discover_executor_packs(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
    )
    return _load_pack_executors_from_packs(packs)


def _discover_executor_packs(
    *,
    project_root: str | Path,
    extra_pack_roots: tuple[str, ...],
) -> tuple[Any, ...]:
    return discover_packs_ordered(
        project_root=project_root,
        extra_pack_roots=extra_pack_roots,
        discover_packs_fn=discover_packs,
    )


def _load_pack_executors_from_packs(
    packs: Iterable[Any],
) -> tuple[ExecutorDefinition, ...]:
    executors: list[ExecutorDefinition] = []
    for pack in packs:
        # Per-pack fault tolerance: one broken content manifest (e.g. an
        # external pack whose executor.yaml fails schema
        # validation) must not abort the whole discovery/invoke. The pack is
        # skipped with a warning; pack-alignment failures
        # (``PackValidationError`` from ``validate_content_id_in_pack``)
        # still propagate — a misplaced id is a packaging contract breach,
        # not a bad manifest.
        try:
            for root in iter_executor_roots(pack):
                for executor in load_folder_executors(root):
                    validate_content_id_in_pack(executor.id, pack, content_type="executor")
                    executors.append(_attach_pack_metadata(executor, pack.id, pack_root=pack.root, content_root=root))
        except (ExecutorValidationError, ManifestParseError) as exc:
            _LOGGER.warning(
                "skipping pack %r: executor manifests failed validation: %s",
                getattr(pack, "id", pack),
                exc,
            )
            continue
    return tuple(executors)


def _attach_pack_metadata(
    executor: ExecutorDefinition,
    pack_id: str,
    *,
    pack_root: Path | None = None,
    content_root: Path | None = None,
) -> ExecutorDefinition:
    metadata = dict(executor.metadata)
    metadata["source"] = "pack"
    metadata["source_pack"] = pack_id
    if pack_root is not None:
        metadata["pack_root"] = str(pack_root)
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


def __getattr__(name: str):
    """Resolve the optional Banodoco catalog type only for explicit callers."""

    if name == "BanodocoCatalogConfig":
        from .banodoco_catalog import BanodocoCatalogConfig

        return BanodocoCatalogConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BUILTIN_STEP_ORDER",
    "ExecutorRegistry",
    "ExecutorRegistryError",
    "BanodocoCatalogConfig",
    "load_pack_executors",
    "load_default_registry",
    "resolve_executor_callable",
]
