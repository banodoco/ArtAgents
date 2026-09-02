"""Pack-manifest loading/parsing, discovery, and the packs root."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from astrid.core.pack._common import (
    PackValidationError,
    _optional_string,
)
from astrid.core.pack.definition import PackDefinition
from astrid.core.pack.canonical import (
    CanonicalPackValidationError,
    LEGACY_MANIFEST_NAMES,
    canonical_manifest_path,
    validate_canonical_pack,
)
from astrid.core.pack.permissions import (
    _normalize_pack_permissions,
    _optional_pack_extensions,
)


def packs_root() -> Path:
    return Path(__file__).resolve().parents[2] / "packs"


DEFAULT_PACKS_ROOT = packs_root()


def discover_packs(
    root: str | Path | None = None,
    *,
    include_hidden: bool = False,
) -> tuple[PackDefinition, ...]:
    source_root = Path(root) if root is not None else packs_root()
    if not source_root.is_dir():
        return ()
    packs: list[PackDefinition] = []
    seen: dict[str, Path] = {}
    for child in sorted(source_root.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
            continue
        manifest_path = pack_manifest_path(child)
        if manifest_path is None:
            continue
        pack = load_pack_manifest(manifest_path)
        if pack.visibility == "hidden" and not include_hidden:
            continue
        if pack.id in seen:
            raise PackValidationError(f"duplicate pack id {pack.id!r}: {seen[pack.id]} and {manifest_path}")
        seen[pack.id] = manifest_path
        packs.append(pack)
    return tuple(packs)


def load_pack_manifest(path: str | Path) -> PackDefinition:
    """Load one strict-v2 capability manifest through the canonical parser."""
    manifest_path = Path(path).expanduser().resolve()
    if manifest_path.name != "pack.yaml" or not manifest_path.is_file():
        raise PackValidationError(
            f"canonical pack admission requires a regular pack.yaml, got {manifest_path}"
        )
    try:
        entry = validate_canonical_pack(manifest_path.parent)
    except CanonicalPackValidationError as exc:
        raise PackValidationError(str(exc)) from exc
    definition = entry.definition
    data = definition.to_dict()
    taxonomy = pack_taxonomy_from_manifest(data, status=definition.status)
    return PackDefinition(
        id=definition.id,
        name=definition.name,
        version=definition.version,
        root=entry.root,
        manifest_path=manifest_path,
        metadata={},
        description=definition.description,
        content=dict(definition.content),
        agent=dict(data["agent"]),
        status=definition.status,
        visibility=definition.visibility,
        schema_version="2",
        aliases=tuple(dict(alias) for alias in data["aliases"]),
        permissions=_normalize_pack_permissions(data["permissions"]),
        extensions=_optional_pack_extensions(data["extensions"], path="pack.extensions"),
        **taxonomy,
    )


def pack_taxonomy_from_manifest(data: dict[str, Any], *, status: str) -> dict[str, str]:
    """Return the deterministic taxonomy projection for a pack manifest.

    These defaults are the M1 taxonomy baseline for manifests that do not yet
    declare an explicit taxonomy block.
    """
    return {
        "origin": _optional_string(data, "origin", "pack.origin", default="unknown"),
        "install_tier": _optional_string(data, "install_tier", "pack.install_tier", default="default"),
        "pack_type": _optional_string(data, "pack_type", "pack.pack_type", default="capability"),
        "domain": _optional_string(data, "domain", "pack.domain", default="general"),
        "stability": _optional_string(
            data,
            "stability",
            "pack.stability",
            default=_default_stability_for_status(status),
        ),
        "support": _optional_string(data, "support", "pack.support", default="project"),
    }


def _default_stability_for_status(status: str) -> str:
    if status == "experimental":
        return "experimental"
    if status == "deprecated":
        return "deprecated"
    return "stable"


def pack_manifest_path(root: str | Path) -> Path | None:
    pack_root = Path(root)
    legacy = sorted(name for name in LEGACY_MANIFEST_NAMES if (pack_root / name).exists())
    if legacy and not (pack_root / "pack.yaml").exists():
        raise PackValidationError(
            f"canonical pack admission requires pack.yaml; found alternate manifest(s): {', '.join(legacy)}"
        )
    try:
        return canonical_manifest_path(pack_root)
    except CanonicalPackValidationError as exc:
        raise PackValidationError(str(exc)) from exc


def _load_manifest_payload(path: Path) -> dict[str, Any]:
    """Read a YAML mapping for internal static-inspection helpers.

    Pack admission remains strict in :func:`load_pack_manifest`; this helper
    also reads non-pack catalogs such as ``models.yaml`` and renderer
    manifests while building the capability ledger.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PackValidationError(f"manifest not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise PackValidationError(f"invalid YAML manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PackValidationError(f"manifest must contain a YAML object: {path}")
    return data
