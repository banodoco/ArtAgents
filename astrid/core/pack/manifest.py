"""Shared manifest parser for Astrid component manifests."""

from __future__ import annotations

import json
from collections.abc import Hashable
from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, SequenceNode

YAML_MANIFEST_SUFFIXES = frozenset({".yaml", ".yml"})
JSON_MANIFEST_SUFFIXES = frozenset({".json"})


class ManifestParseError(ValueError):
    """Raised when a manifest cannot be parsed with the canonical policy."""

    
class _DuplicateKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys after merge expansion."""

    def construct_mapping(self, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
        if isinstance(node, MappingNode):
            self.flatten_mapping(node)
        if not isinstance(node, MappingNode):
            raise ConstructorError(
                None, None, f"expected a mapping node, but found {node.id}", node.start_mark
            )
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                )
            if key in mapping:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key, value in pairs:
        if key in mapping:
            raise ValueError(f"found duplicate key {key!r}")
        mapping[key] = value
    return mapping


def _mapping_repeats(node: Any, key: str, ancestors: set[int]) -> bool:
    identity = id(node)
    if identity in ancestors or not isinstance(node, MappingNode):
        return False
    names: set[str] = set()
    merge_sources: list[Any] = []
    nested_nodes: list[tuple[Any, Any]] = []
    for key_node, value_node in node.value:
        key_value = getattr(key_node, "value", None)
        if key_value == "<<":
            merge_sources.extend(
                value_node.value if isinstance(value_node, SequenceNode) else [value_node]
            )
        elif key_value == key:
            if key_value in names:
                return True
        if isinstance(key_value, str):
            names.add(key_value)
        nested_nodes.append((key_node, value_node))

    next_ancestors = ancestors | {identity}
    merged_names: set[str] = set()
    for source in merge_sources:
        if not isinstance(source, MappingNode):
            continue
        if _mapping_repeats(source, key, next_ancestors):
            return True
        for source_key, _source_value in source.value:
            source_name = getattr(source_key, "value", None)
            if source_name == "<<":
                continue
            if isinstance(source_name, str):
                if source_name == key and source_name in merged_names:
                    return True
                merged_names.add(source_name)
                if source_name == key and source_name in names:
                    return True
    return any(_mapping_repeats(child, key, next_ancestors) for child in nested_nodes)


def manifest_has_duplicate_mapping_key(path: str | Path, key: str) -> bool:
    """Return whether a parsed manifest mapping repeats *key*.

    Dispatch must inspect legacy manifests with the historical permissive
    loader, but ``schema_version`` is itself dispatch authority and cannot be
    ambiguous. This narrow preflight detects that one key without imposing
    strict duplicate rejection on legacy v1 mappings.
    """
    manifest_path = Path(path)
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError:
        return False
    suffix = manifest_path.suffix.lower()
    if suffix in JSON_MANIFEST_SUFFIXES:
        duplicate = False

        def track_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            nonlocal duplicate
            seen: set[str] = set()
            result: dict[str, Any] = {}
            for pair_key, value in pairs:
                if pair_key == key and pair_key in seen:
                    duplicate = True
                seen.add(pair_key)
                result[pair_key] = value
            return result

        try:
            json.loads(text, object_pairs_hook=track_pairs)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
        return duplicate
    if suffix in YAML_MANIFEST_SUFFIXES:
        try:
            root = yaml.compose(text, Loader=yaml.SafeLoader)
        except yaml.YAMLError:
            return False
        return root is not None and _mapping_repeats(root, key, set())
    return False


def load_manifest_payload(
    path: str | Path,
    *,
    manifest_kind: str = "manifest",
    reject_duplicate_keys: bool = False,
) -> Any:
    """Load a JSON or YAML manifest with one parser policy."""
    manifest_path = Path(path)
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestParseError(f"cannot read {manifest_kind} manifest {manifest_path}: {exc}") from exc

    suffix = manifest_path.suffix.lower()
    if suffix in JSON_MANIFEST_SUFFIXES:
        try:
            return json.loads(
                text,
                object_pairs_hook=_strict_json_object if reject_duplicate_keys else None,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            message = getattr(exc, "msg", str(exc))
            raise ManifestParseError(
                f"invalid JSON {manifest_kind} manifest {manifest_path}: {message}"
            ) from exc

    if suffix in YAML_MANIFEST_SUFFIXES:
        try:
            data = (
                yaml.load(text, Loader=_DuplicateKeySafeLoader)
                if reject_duplicate_keys
                else yaml.safe_load(text)
            )
        except yaml.YAMLError as exc:
            raise ManifestParseError(
                f"invalid YAML {manifest_kind} manifest {manifest_path}: {exc}"
            ) from exc
        if data is None:
            raise ManifestParseError(f"empty YAML {manifest_kind} manifest {manifest_path}")
        return data

    raise ManifestParseError(
        f"unsupported {manifest_kind} manifest extension {suffix!r}: {manifest_path}"
    )


def load_manifest_mapping(
    path: str | Path,
    *,
    manifest_kind: str = "manifest",
    reject_duplicate_keys: bool = False,
) -> dict[str, Any]:
    """Load a manifest and require a top-level object/mapping."""
    payload = load_manifest_payload(
        path,
        manifest_kind=manifest_kind,
        reject_duplicate_keys=reject_duplicate_keys,
    )
    if not isinstance(payload, dict):
        raise ManifestParseError(
            f"{manifest_kind} manifest {Path(path)} must contain a mapping object, got {type(payload).__name__}"
        )
    return payload


def load_manifest_for_dispatch(
    path: str | Path, *, manifest_kind: str = "manifest"
) -> dict[str, Any]:
    """Load a manifest while refusing ambiguous schema-version authority."""
    manifest_path = Path(path)
    payload = load_manifest_mapping(
        manifest_path,
        manifest_kind=manifest_kind,
        reject_duplicate_keys=False,
    )
    if manifest_has_duplicate_mapping_key(manifest_path, "schema_version"):
        raise ManifestParseError(
            f"invalid {manifest_kind} manifest {manifest_path}: "
            "found duplicate key 'schema_version'"
        )
    return payload


def _runtime_block_module(runtime_raw: Any) -> str | None:
    """Return the module a ``runtime`` block declares, if any.

    Only the python-kind runtime block names a runtime module (``runtime.module``).
    Command / python-cli blocks declare argv or an entrypoint, not an import path,
    so they never collide with ``metadata.runtime_module``.
    """
    if not isinstance(runtime_raw, dict):
        return None
    if runtime_raw.get("kind") == "python":
        module = runtime_raw.get("module")
        if isinstance(module, str) and module:
            return module
    return None


def reconcile_runtime_module(
    runtime_raw: Any,
    metadata: dict[str, Any],
    error_cls: type[Exception],
    component: str,
) -> dict[str, Any]:
    """Fold a ``runtime.module`` declaration into ``metadata.runtime_module``.

    ``metadata.runtime_module`` is the single canonical runtime declaration the
    loaders read (SD2). A manifest may legacy-declare the same module inside a
    python ``runtime`` block; fold it into metadata so the module is declared
    exactly once, and reject a double-declaration that conflicts.
    """
    block_module = _runtime_block_module(runtime_raw)
    if block_module is None:
        return metadata
    meta_module = metadata.get("runtime_module")
    if isinstance(meta_module, str) and meta_module:
        if meta_module != block_module:
            raise error_cls(
                f"{component} declares its runtime module twice with conflicting "
                f"values: metadata.runtime_module={meta_module!r} vs "
                f"runtime.module={block_module!r}; declare it once via "
                f"metadata.runtime_module"
            )
        return metadata
    return {**metadata, "runtime_module": block_module}


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
    "load_manifest_for_dispatch",
    "load_manifest_mapping",
    "load_manifest_payload",
    "manifest_has_duplicate_mapping_key",
    "reconcile_runtime_module",
]
