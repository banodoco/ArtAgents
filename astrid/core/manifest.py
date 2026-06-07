"""Compatibility shim — re-exports from astrid.core.pack.manifest.

After M2, the canonical location for the shared manifest parser is
``astrid.core.pack.manifest``.  This module exists so existing
``from astrid.core.manifest import ...`` statements continue
to work without changes.
"""

from astrid.core.pack.manifest import (  # noqa: F401
    JSON_MANIFEST_SUFFIXES,
    ManifestParseError,
    YAML_MANIFEST_SUFFIXES,
    dump_manifest_payload,
    load_manifest_mapping,
    load_manifest_payload,
    reconcile_runtime_module,
)

__all__ = [
    "JSON_MANIFEST_SUFFIXES",
    "ManifestParseError",
    "YAML_MANIFEST_SUFFIXES",
    "dump_manifest_payload",
    "load_manifest_mapping",
    "load_manifest_payload",
    "reconcile_runtime_module",
]
