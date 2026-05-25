"""Resolver-backed runtime resolution for manifest-backed orchestrators.

Maps a qualified orchestrator id through the registry → component root →
manifest-declared runtime file and entrypoint, providing one canonical path
for runtime import.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrid.core.pack import discover_packs, packs_root

from .registry import OrchestratorRegistry
from .schema import OrchestratorDefinition


class OrchestratorRuntimeResolutionError(RuntimeError):
    """Raised when an orchestrator runtime cannot be resolved."""


def resolve_orchestrator_runtime(
    orchestrator_id: str,
    *,
    registry: OrchestratorRegistry | None = None,
    extra_pack_roots: tuple[str, ...] = (),
) -> tuple[str, str]:
    """Resolve an orchestrator's runtime module path and entrypoint name.

    Resolution chain:
      1. ``orchestrator_id`` → registry lookup → :class:`OrchestratorDefinition`
      2. ``metadata.orchestrator_root`` → component root directory
      3. component root + ``metadata.runtime_file`` → absolute runtime file path
      4. :func:`resolve_python_module_from_file` → importable dotted module name
      5. ``metadata.runtime_entrypoint`` (default ``"main"``) → entrypoint name

    Uses pack-system's canonical discovery (``discover_packs``) instead of
    PR #8's ``PackResolver``.

    Args:
        orchestrator_id: Qualified id, e.g. ``"video_editing.hype"``.
        registry: Optional pre-built registry.  When *None* a default
            registry is constructed using *extra_pack_roots*.
        extra_pack_roots: Extra pack root directories forwarded to the
            registry.

    Returns:
        ``(module_path, entrypoint_name)`` where *module_path* is a dotted
        Python import path and *entrypoint_name* is a callable attribute name.

    Raises:
        OrchestratorRuntimeResolutionError: If any step of the resolution
            chain fails.
    """
    # 1. Resolve the orchestrator definition.
    if registry is None:
        from .registry import load_default_registry

        registry = load_default_registry(extra_pack_roots=extra_pack_roots)

    orchestrator = registry.get(orchestrator_id)

    # 2. Find the component root for this orchestrator.
    component_root = _find_component_root(orchestrator)

    # 3. Resolve the runtime file.
    runtime_file = orchestrator.metadata.get("runtime_file", "run.py")
    if not isinstance(runtime_file, str) or not runtime_file:
        raise OrchestratorRuntimeResolutionError(
            f"orchestrator {orchestrator_id!r} has no metadata.runtime_file"
        )
    runtime_path = (component_root / runtime_file).resolve()
    if not runtime_path.is_file():
        raise OrchestratorRuntimeResolutionError(
            f"runtime file not found for {orchestrator_id!r}: {runtime_path}"
        )

    # 4. Convert the file path to an importable Python module path.
    module_path = resolve_python_module_from_file(runtime_path)
    if module_path is None:
        raise OrchestratorRuntimeResolutionError(
            f"cannot resolve Python module path for {runtime_path}"
        )

    # 5. Determine the entrypoint name.
    entrypoint = orchestrator.metadata.get("runtime_entrypoint", "main")
    if not isinstance(entrypoint, str) or not entrypoint:
        raise OrchestratorRuntimeResolutionError(
            f"orchestrator {orchestrator_id!r} has invalid metadata.runtime_entrypoint"
        )

    return module_path, entrypoint


def resolve_python_module_from_file(file_path: Path) -> str | None:
    """Convert a ``.py`` file path to a dotted Python module path.

    Returns *None* when the file cannot be mapped to the current
    ``sys.path``.  The longest-matching prefix wins (most specific).
    """
    resolved = file_path.resolve()

    # If the file is a .py, strip the extension for the module name.
    if resolved.suffix == ".py":
        module_stem = resolved.with_suffix("")
    else:
        module_stem = resolved

    # Find the longest sys.path prefix that contains this file.
    best: tuple[int, str] | None = None
    for path_entry in sys.path:
        pe = Path(path_entry).resolve()
        try:
            relative = module_stem.relative_to(pe)
        except ValueError:
            continue
        depth = len(pe.parts)
        if best is None or depth > best[0]:
            best = (depth, ".".join(relative.parts))

    if best is not None:
        return best[1]

    return None


def _find_component_root(
    orchestrator: OrchestratorDefinition,
) -> Path:
    """Find the filesystem directory that contains *orchestrator*'s manifest.

    Uses pack-system's canonical approach: checks ``metadata.orchestrator_root``
    first (set by the folder loader), then falls back to discovering packs
    and scanning their orchestrator roots.
    """
    short_name = orchestrator.id.split(".", 1)[-1]

    # Check the orchestrator_root from metadata first (set by folder loader).
    orchestrator_root = orchestrator.metadata.get("orchestrator_root")
    if orchestrator_root:
        candidate = Path(orchestrator_root)
        if candidate.is_dir():
            return candidate

    # Fall back: discover packs and scan for the orchestrator's component root.
    source_pack = orchestrator.metadata.get("source_pack")
    if source_pack:
        all_packs = {
            pack.id: pack
            for pack in discover_packs()
        }
        # Also discover from installed pack roots if available.
        try:
            from astrid.core.pack_store import installed_pack_roots

            for installed_root in installed_pack_roots():
                for pack in discover_packs(installed_root):
                    all_packs[pack.id] = pack
        except ImportError:
            pass

        pack = all_packs.get(source_pack)
        if pack is not None:
            from astrid.core.pack import iter_orchestrator_roots

            for root in iter_orchestrator_roots(pack):
                candidate = root / short_name
                if candidate.is_dir():
                    return candidate
                if root.name == short_name:
                    return root

    raise OrchestratorRuntimeResolutionError(
        f"cannot find component root for orchestrator {orchestrator.id!r}"
    )


__all__ = [
    "OrchestratorRuntimeResolutionError",
    "resolve_orchestrator_runtime",
    "resolve_python_module_from_file",
]
