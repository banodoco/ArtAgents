"""Shared pack discovery across executor, orchestrator, and element registries.

Each registry previously re-implemented the same four-layer discovery walk
(source-tree packs, the project-scoped ``local`` scratch pack, extra pack
roots, and installed packs). The duplication made it easy for the layers or
their ordering to drift apart. This module centralizes the walk and exposes a
``DiscoveredPack`` metadata shape so every registry — and, ahead of Step 13,
skills discovery — consumes one ordered list with identical priority semantics.

Fault tolerance: the ``extra`` / ``env`` / ``installed`` layers are
external by definition. A pack whose manifest fails to load — or an
installed pack that fails validation — is skipped individually with a
logged warning so one broken external pack cannot hide its valid
neighbors. The source-tree scan stays strict: first-party packs must
always load.
"""

from __future__ import annotations

import logging
import os

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from astrid.core.pack._common import SymlinkedPackPathError, reject_symlinked_path

from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.pack import (
    PackDefinition,
    discover_packs,
    ensure_local_pack_for_elements,
    iter_element_roots,
    iter_executor_roots,
    iter_orchestrator_roots,
)
from astrid.core.pack.canonical import (
    CanonicalPackEntry,
    CanonicalPackValidationError,
    ExternalPackSource,
    read_normalize_validate,
)

DiscoverPacksFn = Callable[..., "tuple[PackDefinition, ...]"]
CanonicalDiscoverPacksFn = Callable[..., "tuple[CanonicalPackEntry, ...]"]


@dataclass(frozen=True)
class CanonicalDiscoveredPack:
    """A canonical v2 pack admitted from an external source seam."""

    entry: CanonicalPackEntry
    source_kind: str
    priority_index: int

    @property
    def id(self) -> str:
        return self.entry.id

    @property
    def pack_dir(self) -> Path:
        return self.entry.root

# Source-kind labels in discovery (and therefore priority) order.
SOURCE_KINDS: tuple[str, ...] = ("source", "local", "extra", "env", "installed")
ASTRID_PACKS_PATH_ENV = "ASTRID_PACKS_PATH"


@dataclass(frozen=True)
class DiscoveredPack:
    """A pack located by discovery plus where it came from.

    ``priority_index`` is the position of this pack in the ordered discovery
    list; lower indices were discovered first. It encodes layer precedence
    (source < local < extra < installed) and is distinct from the per-content
    ``metadata["priority"]`` value that registries use to pick winners.
    """

    pack: PackDefinition
    source_kind: str
    priority_index: int

    @property
    def id(self) -> str:
        return self.pack.id

    @property
    def pack_dir(self) -> Path:
        return self.pack.root

    def executor_roots(self) -> tuple[Path, ...]:
        return iter_executor_roots(self.pack)

    def orchestrator_roots(self) -> tuple[Path, ...]:
        return iter_orchestrator_roots(self.pack)

    def element_roots(self, *, kind: str | None = None):
        return iter_element_roots(self.pack, kind=kind)

    def skill_roots(self) -> tuple[Path, ...]:
        """Candidate ``skill/`` directories: pack-level plus nested content.

        Mirrors the directories that ``astrid.skills.discovery`` scans, so
        skills discovery can consume this metadata in Step 13 without
        re-deriving roots.
        """
        roots: list[Path] = [self.pack_dir / "skill"]
        for content_root in (*self.executor_roots(), *self.orchestrator_roots()):
            roots.append(content_root / "skill")
        return tuple(roots)


def discover_pack_metadata(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    discover_packs_fn: DiscoverPacksFn | None = None,
) -> tuple[DiscoveredPack, ...]:
    """Return discovered packs in layered priority order.

    Layers, in order: source-tree packs (excluding ``local``), the
    project-scoped ``local`` scratch pack when *project_root* differs from the
    repository root, explicit extra pack roots (excluding ``local``),
    ``ASTRID_PACKS_PATH`` roots (excluding ``local``), and installed packs
    (excluding ``local``) when *include_installed* is set.

    *discover_packs_fn* overrides the source/local/extra layer scanner; callers
    pass their own module-level ``discover_packs`` so the historical per-registry
    test seam (``mock.patch("astrid.core.<x>.registry.discover_packs")``) keeps
    working. Defaults to :func:`astrid.core.pack.discover_packs`.
    """
    scan = discover_packs_fn if discover_packs_fn is not None else discover_packs
    repo_pack_root = (REPO_ROOT / "astrid" / "packs").resolve()
    project_root = Path(project_root).expanduser()
    project_pack_root = project_root / "astrid" / "packs"
    local_candidate = project_pack_root / "local"
    try:
        reject_symlinked_path(project_pack_root)
        reject_symlinked_path(local_candidate)
    except SymlinkedPackPathError:
        project_pack_root = None
        local_pack_root = None
    else:
        project_pack_root = project_pack_root.resolve()
        local_pack_root = ensure_local_pack_for_elements(project_root=project_root)
    discovered: list[DiscoveredPack] = []
    scanned_external_roots: set[Path] = set()

    def _add(pack: PackDefinition, source_kind: str) -> None:
        discovered.append(
            DiscoveredPack(
                pack=pack,
                source_kind=source_kind,
                priority_index=len(discovered),
            )
        )

    _LOGGER = logging.getLogger(__name__)

    def _scan_external_root(raw_root: str | Path, source_kind: str) -> None:
        """Scan one external root, isolating failures per pack manifest.

        A readable root contributes every loadable pack; one bad manifest
        skips only its own pack (with a warning), so valid neighbors in the
        same root survive. Only an unreadable root is skipped wholesale.
        """
        from astrid.core.pack import load_pack_manifest, pack_manifest_path

        try:
            resolved = _resolve_pack_root(raw_root)
        except SymlinkedPackPathError as exc:
            _LOGGER.warning(
                "skipping symlinked %s root %s: %s",
                source_kind,
                raw_root,
                exc,
            )
            return
        # An SDK caller may pass a root explicitly while the same canonical
        # root is also present in ASTRID_PACKS_PATH.  Scan it once, retaining
        # the higher-priority explicit ``extra`` provenance instead of
        # reporting the same pack twice (and potentially registering duplicate
        # renderer/element candidates).
        if resolved in scanned_external_roots:
            return
        scanned_external_roots.add(resolved)
        if not resolved.is_dir():
            return
        try:
            children = sorted(resolved.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            # An unreadable external root (e.g. chmod 000) is skipped
            # wholesale with a warning — one dead root must not abort
            # discovery and hide every valid neighbor.
            _LOGGER.warning(
                "skipping unreadable %s root %s: %s",
                source_kind,
                resolved,
                exc,
            )
            return
        seen: dict[str, Path] = {}
        for child in children:
            try:
                reject_symlinked_path(child)
            except SymlinkedPackPathError as exc:
                _LOGGER.warning(
                    "skipping symlinked %s pack %s: %s",
                    source_kind,
                    child,
                    exc,
                )
                continue
            try:
                if (
                    not child.is_dir()
                    or child.name.startswith(".")
                    or child.name == "__pycache__"
                ):
                    continue
                manifest_path = pack_manifest_path(child)
            except OSError as exc:
                # Per-child pre-scan failures (e.g. an unreadable pack
                # directory) skip only that child, matching the
                # per-manifest isolation below.
                _LOGGER.warning(
                    "skipping unreadable %s pack %s: %s",
                    source_kind,
                    child,
                    exc,
                )
                continue
            if manifest_path is None:
                continue
            try:
                pack = load_pack_manifest(manifest_path)
            except Exception as exc:  # noqa: BLE001 - external roots are fault-tolerant
                _LOGGER.warning(
                    "skipping %s pack %s: manifest failed to load: %s",
                    source_kind,
                    manifest_path,
                    exc,
                )
                continue
            if pack.id == "local":
                continue
            if pack.visibility == "hidden":
                continue
            if pack.id in seen:
                _LOGGER.warning(
                    "skipping duplicate pack id %r in %s root %s "
                    "(%s and %s)",
                    pack.id,
                    source_kind,
                    resolved,
                    seen[pack.id],
                    manifest_path,
                )
                continue
            seen[pack.id] = manifest_path
            _add(pack, source_kind)

    for pack in scan():
        if pack.id == "local":
            continue
        _add(pack, "source")

    if local_pack_root is not None and project_pack_root.is_dir():
        for pack in scan(project_pack_root):
            if pack.id == "local":
                _add(pack, "local")
    def _resolve_pack_root(raw_root: str | Path) -> Path:
        candidate = Path(raw_root).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        reject_symlinked_path(candidate)
        return candidate.resolve()

    raw_env_roots = os.environ.get(ASTRID_PACKS_PATH_ENV, "")
    if extra_pack_roots or raw_env_roots or include_installed:
        for extra_root in extra_pack_roots:
            _scan_external_root(extra_root, "extra")
        for env_root in raw_env_roots.split(os.pathsep):
            if env_root == "":
                continue
            _scan_external_root(env_root, "env")
        if include_installed:
            from astrid.core.pack import load_pack_manifest
            from astrid.core.pack import pack_manifest_path as _pmp
            from astrid.core.pack.store import installed_pack_roots



            for installed_root in installed_pack_roots():
                if not installed_root.is_dir():
                    continue
                mp = _pmp(installed_root)
                if mp is None:
                    continue
                try:
                    pack = load_pack_manifest(mp)
                except Exception as exc:  # noqa: BLE001 - installed packs are fault-tolerant
                    _LOGGER.warning(
                        "skipping installed pack %s: manifest failed to load: %s",
                        installed_root,
                        exc,
                    )
                    continue
                if pack.id == "local":
                    continue
                _add(pack, "installed")

    return tuple(discovered)
def discover_canonical_pack_metadata(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[CanonicalDiscoveredPack, ...]:
    """Admit canonical v2 packs through external discovery seams only.

    This is intentionally separate from :func:`discover_pack_metadata`, whose
    legacy source-tree behavior remains active during B1.  Unlike the
    fault-tolerant legacy walk, canonical admission propagates validation
    failures so an external database declaration cannot be silently dropped.
    """
    project_root = Path(project_root).expanduser()
    project_pack_root = project_root / "astrid" / "packs"
    local_candidate = project_pack_root / "local"
    try:
        reject_symlinked_path(project_pack_root)
        reject_symlinked_path(local_candidate)
    except SymlinkedPackPathError as exc:
        raise CanonicalPackValidationError(
            f"local pack root must not be a symlink or contain symlinked ancestors: "
            f"{project_pack_root}"
        ) from exc
    project_pack_root = project_pack_root.resolve()
    # Canonical discovery is strictly read-only: inspect an existing local
    # pack only and never materialize the legacy element-only manifest.
    local_pack_root = project_pack_root / "local"
    discovered: list[CanonicalDiscoveredPack] = []
    scanned_roots: set[Path] = set()
    seen_by_source: dict[tuple[str, str], Path] = {}

    def add(
        manifest_path: Path,
        source: ExternalPackSource,
        *,
        expected_pack_id: str | None = None,
    ) -> None:
        entry = read_normalize_validate(
            manifest_path,
            source=source,
            expected_pack_id=expected_pack_id,
        )
        if entry.id == "local" and source is not ExternalPackSource.LOCAL:
            return
        if entry.definition.visibility == "hidden":
            return
        key = (source.value, entry.id)
        prior = seen_by_source.get(key)
        if prior is not None:
            raise CanonicalPackValidationError(
                f"duplicate canonical pack ID {entry.id!r} in {source.value}: "
                f"{prior} and {manifest_path}"
            )
        seen_by_source[key] = manifest_path
        discovered.append(CanonicalDiscoveredPack(entry, source.value, len(discovered)))

    def canonical_manifest(root: Path) -> Path | None:
        try:
            reject_symlinked_path(root)
        except SymlinkedPackPathError as exc:
            raise CanonicalPackValidationError(
                f"external pack directory must not be a symlink or contain "
                f"symlinked ancestors: {root}"
            ) from exc
        candidate = root / "pack.yaml"
        return candidate if candidate.is_file() or candidate.is_symlink() else None

    def resolve_root(raw_root: str | Path) -> Path:
        candidate = Path(raw_root).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        try:
            candidate = reject_symlinked_path(candidate)
        except SymlinkedPackPathError as exc:
            raise CanonicalPackValidationError(
                f"external pack root must not be a symlink or contain symlinked "
                f"ancestors: {candidate}"
            ) from exc
        return candidate.resolve()

    def scan_external_root(raw_root: str | Path, source: ExternalPackSource) -> None:
        resolved = resolve_root(raw_root)
        if resolved in scanned_roots:
            return
        scanned_roots.add(resolved)
        if not resolved.is_dir():
            return
        for child in sorted(resolved.iterdir(), key=lambda path: path.name):
            if child.is_symlink():
                raise CanonicalPackValidationError(
                    f"external pack directory must not be a symlink: {child}"
                )
            if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
                continue
            manifest_path = canonical_manifest(child)
            if manifest_path is not None:
                add(manifest_path, source)

    if project_pack_root.is_dir():
        manifest_path = canonical_manifest(local_pack_root)
        if manifest_path is not None:
            add(manifest_path, ExternalPackSource.LOCAL)

    for extra_root in extra_pack_roots:
        scan_external_root(extra_root, ExternalPackSource.EXTRA)
    for env_root in os.environ.get(ASTRID_PACKS_PATH_ENV, "").split(os.pathsep):
        if env_root:
            scan_external_root(env_root, ExternalPackSource.ENV)

    if include_installed:
        from astrid.core.pack.store import installed_pack_roots

        for installed_root in installed_pack_roots():
            manifest_path = canonical_manifest(installed_root)
            if manifest_path is not None:
                # ``installed_pack_roots`` has already validated the custody
                # record.  The owning install directory, rather than the
                # revision directory (which may be timestamped), is the
                # installed identity authority.
                install_root = installed_root.parent.parent
                add(
                    manifest_path,
                    ExternalPackSource.INSTALLED,
                    expected_pack_id=install_root.name,
                )

    return tuple(discovered)


def discover_canonical_packs_ordered(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
) -> tuple[CanonicalPackEntry, ...]:
    """Return canonical v2 entries from the isolated external walk."""
    return tuple(
        item.entry
        for item in discover_canonical_pack_metadata(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
        )
    )


def discover_packs_ordered(
    *,
    project_root: str | Path = REPO_ROOT,
    extra_pack_roots: tuple[str, ...] = (),
    include_installed: bool = True,
    discover_packs_fn: DiscoverPacksFn | None = None,
) -> tuple[Any, ...]:
    """Convenience wrapper returning just the ``PackDefinition`` objects.

    Drop-in replacement for the per-registry ``_discover_*_packs`` helpers,
    preserving their exact ordering.
    """
    return tuple(
        dp.pack
        for dp in discover_pack_metadata(
            project_root=project_root,
            extra_pack_roots=extra_pack_roots,
            include_installed=include_installed,
            discover_packs_fn=discover_packs_fn,
        )
    )


__all__ = [
    "ASTRID_PACKS_PATH_ENV",
    "SOURCE_KINDS",
    "DiscoveredPack",
    "CanonicalDiscoveredPack",
    "discover_pack_metadata",
    "discover_canonical_pack_metadata",
    "discover_canonical_packs_ordered",
    "discover_packs_ordered",
]
