"""Strict canonical pack admission and bundled discovery helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from astrid.core.pack._common import (
    ELEMENT_MANIFEST_NAMES,
    PackValidationError,
)
from astrid.core.pack.canonical import (
    BundledCatalog,
    CanonicalPackEntry,
    CanonicalPackValidationError,
    ExternalPackSource,
    canonical_manifest_path,
    read_normalize_validate,
)
from astrid.core.pack.definition import PackDefinition
from astrid.core.pack.permissions import _normalize_pack_permissions


def _materialize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _materialize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_materialize(item) for item in value]
    return value


def _pack_definition_from_entry(entry: CanonicalPackEntry) -> PackDefinition:
    definition = entry.definition
    return PackDefinition(
        id=definition.id,
        name=definition.name,
        version=definition.version,
        root=entry.root,
        manifest_path=Path(entry.manifest.resolved),
        metadata={},
        description=definition.description,
        content=_materialize(definition.content),
        agent=_materialize(definition.agent),
        status=definition.status,
        visibility=definition.visibility,
        schema_version=str(definition.schema_version),
        aliases=tuple(_materialize(item) for item in definition.aliases),
        permissions=tuple(
            _normalize_pack_permissions(
                [
                    {
                        "id": permission.id,
                        "reason": permission.reason,
                        **(
                            {"access": permission.access}
                            if permission.access is not None
                            else {}
                        ),
                        **(
                            {"services": list(permission.services)}
                            if permission.services
                            else {}
                        ),
                    }
                    for permission in definition.permissions
                ]
            )
        ),
        extensions=_materialize(definition.extensions),
        origin=definition.origin if hasattr(definition, "origin") else "unknown",
        install_tier=definition.install_tier if hasattr(definition, "install_tier") else "default",
        pack_type=definition.pack_type if hasattr(definition, "pack_type") else "capability",
        domain=definition.domain,
        stability=definition.stability,
        support=definition.support,
    )


def packs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "packs"


DEFAULT_PACKS_ROOT = packs_root()


def ensure_local_pack(*, project_root: str | Path = None) -> Path:
    """Create or return the ``local`` scratch pack under *project_root*."""
    from astrid.core.foundation.paths import REPO_ROOT

    root = Path(project_root) if project_root is not None else REPO_ROOT
    pack_root = root / "astrid" / "packs" / "local"
    pack_root.mkdir(parents=True, exist_ok=True)
    manifest = pack_root / "pack.yaml"
    if not manifest.exists():
        manifest.write_text(
            "schema_version: 2\n"
            "id: local\n"
            "name: Local Scratch Pack\n"
            "version: 0.1.0\n"
            "capabilities: [local]\n",
            encoding="utf-8",
        )
    return pack_root


def ensure_local_pack_for_elements(*, project_root: str | Path = None) -> Path | None:
    """Materialize the local canonical manifest when local elements exist."""
    from astrid.core.foundation.paths import REPO_ROOT

    root = Path(project_root) if project_root is not None else REPO_ROOT
    pack_root = root / "astrid" / "packs" / "local"
    manifest = pack_root / "pack.yaml"
    if manifest.exists():
        return pack_root
    elements_root = pack_root / "elements"
    if not _has_local_element_manifest(elements_root):
        return None
    pack_root.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "schema_version: 2\n"
        "id: local\n"
        "name: Local Scratch Pack\n"
        "version: 0.1.0\n"
        "capabilities: [local]\n",
        encoding="utf-8",
    )
    return pack_root


def _has_local_element_manifest(elements_root: Path) -> bool:
    if not elements_root.is_dir():
        return False
    for candidate in elements_root.glob("*/*"):
        if candidate.is_dir() and any(
            (candidate / name).is_file() for name in ELEMENT_MANIFEST_NAMES
        ):
            return True
    return False


def _entry_for_manifest(manifest_path: str | Path) -> CanonicalPackEntry:
    path = Path(manifest_path).expanduser()
    if path.name != "pack.yaml":
        raise PackValidationError(
            f"canonical pack admission requires pack.yaml, got {path.name!r}"
        )
    try:
        if path.resolve().parent.parent == DEFAULT_PACKS_ROOT.resolve():
            catalog = BundledCatalog.from_root(DEFAULT_PACKS_ROOT)
            return catalog.get(path.resolve().parent.name)
        return read_normalize_validate(
            path,
            source=ExternalPackSource.LOCAL,
            resolve_resources=True,
        )
    except CanonicalPackValidationError as exc:
        raise PackValidationError(str(exc)) from exc


def discover_packs(
    root: str | Path | None = None,
    *,
    include_hidden: bool = False,
) -> tuple[PackDefinition, ...]:
    """Discover only strict canonical v2 ``pack.yaml`` entries."""
    source_root = Path(root) if root is not None else DEFAULT_PACKS_ROOT
    if not source_root.is_dir():
        return ()
    if source_root.resolve() == DEFAULT_PACKS_ROOT.resolve():
        entries = BundledCatalog.from_root(source_root).ordered_entries
    else:
        entries = []
        for child in sorted(source_root.iterdir(), key=lambda path: path.name):
            if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
                continue
            manifest = canonical_manifest_path(child)
            if manifest is not None:
                entries.append(_entry_for_manifest(manifest))
    packs = [
        _pack_definition_from_entry(entry)
        for entry in entries
        if include_hidden or entry.definition.visibility != "hidden"
    ]
    ids = [pack.id for pack in packs]
    if len(ids) != len(set(ids)):
        raise PackValidationError("duplicate canonical pack ID in discovery")
    return tuple(packs)


def load_pack_manifest(path: str | Path) -> PackDefinition:
    """Load one strict canonical v2 ``pack.yaml`` as a capability projection."""
    return _pack_definition_from_entry(_entry_for_manifest(path))


def pack_manifest_path(root: str | Path) -> Path | None:
    """Return only the canonical ``pack.yaml`` path, if present."""
    return canonical_manifest_path(root)


