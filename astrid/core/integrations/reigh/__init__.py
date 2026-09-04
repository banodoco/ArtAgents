"""Generic B-6 profile handoff helpers."""

from .boot_manifest import (
    BootManifestCorrupt,
    BootManifestDrift,
    BootManifestError,
    build_manifest,
    compute_registry_digest,
    load_boot_manifest_hash,
    manifest_hash,
    stamp_boot_manifest,
    validate_manifest_path,
    validate_support_root,
)

__all__ = [
    "BootManifestCorrupt",
    "BootManifestDrift",
    "BootManifestError",
    "build_manifest",
    "compute_registry_digest",
    "load_boot_manifest_hash",
    "manifest_hash",
    "stamp_boot_manifest",
    "validate_manifest_path",
    "validate_support_root",
]
