"""Shared pack discovery across executor, orchestrator, and element registries.

Each registry consumes the same manifest-ledger discovery walk. The walk is
read-only: it can see source-tree packs, an already-materialized project
``local`` pack, explicit extra roots, and read-only roots named by
``ASTRID_PACKS_PATH``. It never creates a project pack and never consults an
installed-pack store.

Fault tolerance: the ``extra`` / ``env`` layers are
external by definition. A pack whose manifest fails to load is skipped
individually with a logged warning so one broken external pack cannot hide its
valid neighbors. The source-tree scan stays strict: first-party packs must
always load.
"""

from __future__ import annotations

import logging
import os

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from astrid.core.foundation.paths import REPO_ROOT
from astrid.core.pack import (
    PackDefinition,
    discover_packs,
    iter_element_roots,
    iter_executor_roots,
    iter_orchestrator_roots,
)

DiscoverPacksFn = Callable[..., "tuple[PackDefinition, ...]"]

# Source-kind labels in discovery (and therefore priority) order.
SOURCE_KINDS: tuple[str, ...] = ("source", "local", "extra", "env")
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

    Layers, in order: source-tree packs (excluding ``local``), an existing
    project-scoped ``local`` pack, explicit extra pack roots (excluding
    ``local``), and ``ASTRID_PACKS_PATH`` roots (excluding ``local``).
    ``include_installed`` is retained as a source-compatible keyword but is
    intentionally ignored; installed packs are not a discovery authority.

    *discover_packs_fn* overrides the source/local/extra layer scanner; callers
    pass their own module-level ``discover_packs`` so the historical per-registry
    test seam (``mock.patch("astrid.core.<x>.registry.discover_packs")``) keeps
    working. Defaults to :func:`astrid.core.pack.discover_packs`.
    """
    scan = discover_packs_fn if discover_packs_fn is not None else discover_packs
    repo_pack_root = (REPO_ROOT / "astrid" / "packs").resolve()
    project_pack_root = (Path(project_root) / "astrid" / "packs").resolve()
    # Discovery is observational. Do not materialize a project-local pack just
    # because a registry was loaded; only an explicitly-authored manifest is
    # eligible for the local layer.
    local_pack_root = project_pack_root / "local"
    if not any(
        (local_pack_root / name).is_file()
        for name in ("pack.yaml", "pack.yml", "pack.json")
    ):
        local_pack_root = None

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

        resolved = _resolve_pack_root(raw_root)
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
            candidate = Path(project_root) / candidate
        return candidate.resolve()

    raw_env_roots = os.environ.get(ASTRID_PACKS_PATH_ENV, "")
    if extra_pack_roots or raw_env_roots:
        for extra_root in extra_pack_roots:
            _scan_external_root(extra_root, "extra")
        for env_root in raw_env_roots.split(os.pathsep):
            if env_root == "":
                continue
            _scan_external_root(env_root, "env")

    return tuple(discovered)


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
    "discover_pack_metadata",
    "discover_packs_ordered",
]
