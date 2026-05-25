"""Shared manifest parser for Astrid component manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

YAML_MANIFEST_SUFFIXES = frozenset({".yaml", ".yml"})
JSON_MANIFEST_SUFFIXES = frozenset({".json"})


class ManifestParseError(ValueError):
    """Raised when a manifest cannot be parsed with the canonical policy."""


def load_manifest_payload(path: str | Path, *, manifest_kind: str = "manifest") -> Any:
    """Load a JSON or YAML manifest with one parser policy.

    ``.json`` files are strict JSON. ``.yaml`` and ``.yml`` files use
    ``yaml.safe_load``. Runtime loaders and pack validation should share this
    function for component manifests so authoring syntax is accepted or rejected
    consistently.
    """
    manifest_path = Path(path)
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestParseError(f"cannot read {manifest_kind} manifest {manifest_path}: {exc}") from exc

    suffix = manifest_path.suffix.lower()
    if suffix in JSON_MANIFEST_SUFFIXES:
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestParseError(
                f"invalid JSON {manifest_kind} manifest {manifest_path}: {exc.msg}"
            ) from exc

    if suffix in YAML_MANIFEST_SUFFIXES:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ManifestParseError(
                f"invalid YAML {manifest_kind} manifest {manifest_path}: {exc}"
            ) from exc
        if data is None:
            raise ManifestParseError(f"empty YAML {manifest_kind} manifest {manifest_path}")
        return data

    raise ManifestParseError(
        f"unsupported {manifest_kind} manifest extension {suffix!r} for {manifest_path}"
    )


def load_manifest_mapping(path: str | Path, *, manifest_kind: str = "manifest") -> dict[str, Any]:
    """Load a manifest and require a top-level object/mapping."""
    payload = load_manifest_payload(path, manifest_kind=manifest_kind)
    if not isinstance(payload, dict):
        raise ManifestParseError(
            f"{manifest_kind} manifest {Path(path)} must contain a mapping object, got {type(payload).__name__}"
        )
    return payload


def dump_manifest_payload(path: str | Path, payload: dict[str, Any]) -> None:
    """Write a deterministic JSON-compatible manifest.

    Fork writers historically rewrote ``*.yaml`` manifests as JSON-compatible
    text. Keep that stable; the loading policy remains YAML-aware.
    """
    manifest_path = Path(path)
    suffix = manifest_path.suffix.lower()
    if suffix not in JSON_MANIFEST_SUFFIXES and suffix not in YAML_MANIFEST_SUFFIXES:
        raise ManifestParseError(
            f"unsupported manifest extension {suffix!r} for {manifest_path}"
        )
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(text, encoding="utf-8")


__all__ = [
    "JSON_MANIFEST_SUFFIXES",
    "ManifestParseError",
    "YAML_MANIFEST_SUFFIXES",
    "dump_manifest_payload",
    "load_manifest_mapping",
    "load_manifest_payload",
]
