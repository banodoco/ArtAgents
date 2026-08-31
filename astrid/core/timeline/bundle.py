"""Fail-closed validation for the Astrid TimelineBundle wire envelope.

The editor owns the canonical TypeScript schema.  Astrid mirrors its small,
stable v1 vocabulary here so the bridge can reject malformed or future data
before a CAS transaction starts, while retaining opaque authored payloads and
unknown envelope-level fields byte-for-byte.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

TIMELINE_BUNDLE_SCHEMA_VERSION = 1
BUNDLE_MISSING = object()


class TimelineBundleValidationError(ValueError):
    """A bundle issue suitable for the typed 422 envelope."""

    def __init__(self, pointer: str, message: str) -> None:
        self.pointer = pointer
        self.message = message
        super().__init__(message)


def _string(value: Any, pointer: str) -> str:
    if not isinstance(value, str) or not value:
        raise TimelineBundleValidationError(pointer, "must be a non-empty string")
    return value


def _number(value: Any, pointer: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TimelineBundleValidationError(pointer, "must be a number")


def _item(value: Any, pointer: str) -> None:
    if not isinstance(value, Mapping):
        raise TimelineBundleValidationError(pointer, "must be an object")
    allowed = {
        "id", "shape", "domain", "extent", "schemaRef", "payload",
        "sourceArtifactRef", "provenance",
    }
    unknown = sorted(set(value).difference(allowed))
    if unknown:
        raise TimelineBundleValidationError(
            pointer,
            f"contains unsupported item field(s): {', '.join(unknown)}",
        )
    _string(value.get("id"), f"{pointer}/id")
    if value.get("shape") not in {"point", "interval", "series"}:
        raise TimelineBundleValidationError(f"{pointer}/shape", "unsupported data shape")
    if value.get("domain") not in {
        "timeline_seconds", "source_seconds", "frames", "samples",
        "ticks", "ordinal", "char_offset", "token_offset",
    }:
        raise TimelineBundleValidationError(f"{pointer}/domain", "unsupported coordinate domain")
    extent = value.get("extent")
    if not isinstance(extent, Mapping):
        raise TimelineBundleValidationError(f"{pointer}/extent", "must be an object")
    _number(extent.get("start"), f"{pointer}/extent/start")
    if "end" in extent:
        _number(extent["end"], f"{pointer}/extent/end")
    _string(value.get("schemaRef"), f"{pointer}/schemaRef")
    artifact = value.get("sourceArtifactRef")
    if not isinstance(artifact, Mapping):
        raise TimelineBundleValidationError(
            f"{pointer}/sourceArtifactRef", "must be an object"
        )
    _string(artifact.get("assetId"), f"{pointer}/sourceArtifactRef/assetId")
    if "artifactHash" in artifact:
        _string(artifact["artifactHash"], f"{pointer}/sourceArtifactRef/artifactHash")
    provenance = value.get("provenance")
    if not isinstance(provenance, Mapping):
        raise TimelineBundleValidationError(f"{pointer}/provenance", "must be an object")
    _string(provenance.get("adapterId"), f"{pointer}/provenance/adapterId")
    _string(provenance.get("adapterVersion"), f"{pointer}/provenance/adapterVersion")
    if "recordedAt" in provenance:
        _string(provenance["recordedAt"], f"{pointer}/provenance/recordedAt")


def validate_timeline_bundle(value: Any) -> dict[str, Any]:
    """Validate and return a lossless v1 bundle copy.

    Top-level envelope keys are intentionally opaque for same-version forward
    compatibility. Item keys are strict: derived view chrome must never enter
    the persisted source lane.
    """
    if not isinstance(value, Mapping):
        raise TimelineBundleValidationError("/bundle", "must be an object")
    version = value.get("schema_version")
    if version != TIMELINE_BUNDLE_SCHEMA_VERSION:
        raise TimelineBundleValidationError(
            "/bundle/schema_version",
            f"unsupported schema_version {version!r}; supported: {TIMELINE_BUNDLE_SCHEMA_VERSION}",
        )
    items = value.get("itemsBySchemaRef")
    if not isinstance(items, Mapping):
        raise TimelineBundleValidationError(
            "/bundle/itemsBySchemaRef", "must be an object"
        )
    for schema_ref, entries in items.items():
        if not isinstance(schema_ref, str) or not schema_ref:
            raise TimelineBundleValidationError(
                "/bundle/itemsBySchemaRef", "schema references must be non-empty strings"
            )
        if not isinstance(entries, list):
            raise TimelineBundleValidationError(
                f"/bundle/itemsBySchemaRef/{schema_ref}", "must be an array"
            )
        for index, entry in enumerate(entries):
            _item(entry, f"/bundle/itemsBySchemaRef/{schema_ref}/{index}")
    return dict(value)


__all__ = [
    "TIMELINE_BUNDLE_SCHEMA_VERSION",
    "BUNDLE_MISSING",
    "TimelineBundleValidationError",
    "validate_timeline_bundle",
]
