"""Shared universal result-manifest helpers."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from astrid.core.project.jsonio import write_json_atomic
from astrid.core.util.hash import sha256_file

_REQUIRED_FIELDS = frozenset(
    {"schema_version", "kind", "inputs", "outputs", "created", "warnings"}
)
_KIND_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return value


def _prefixed_hash(value: str) -> str:
    if value.startswith("sha256:"):
        return value
    return f"sha256:{value}"


def _resolve_hash(entry: Mapping[str, Any], *, path: Path) -> tuple[str, str | None]:
    content_hash = entry.get("content_hash")
    if isinstance(content_hash, str) and content_hash:
        return content_hash, None

    sha256_value = entry.get("sha256")
    if isinstance(sha256_value, str) and sha256_value:
        return _prefixed_hash(sha256_value), sha256_value

    digest = sha256_file(path)
    return f"sha256:{digest}", None


def _directory_children(path: Path) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    for child in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        rel_path = child.relative_to(path).as_posix()
        digest = sha256_file(child)
        children.append(
            {
                "path": rel_path,
                "bytes": child.stat().st_size,
                "content_hash": f"sha256:{digest}",
            }
        )
    return children


def _tree_hash(children: Sequence[Mapping[str, Any]]) -> str:
    canonical = json.dumps(list(children), sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _resolve_output_path(root_dir: Path, entry: Mapping[str, Any]) -> tuple[str, Path]:
    raw_path = entry.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("outputs[].path must be a non-empty string")
    candidate = Path(raw_path)
    resolved = candidate if candidate.is_absolute() else root_dir / candidate
    return raw_path, resolved


def complete_output_metadata(
    outputs: Sequence[Mapping[str, Any]],
    *,
    root_dir: str | Path,
) -> list[dict[str, Any]]:
    """Populate deterministic metadata for file and directory outputs."""

    completed: list[dict[str, Any]] = []
    base_dir = Path(root_dir)
    for entry in outputs:
        output = dict(_require_mapping(entry, "outputs[]"))
        raw_path, resolved_path = _resolve_output_path(base_dir, output)
        is_optional = bool(output.get("optional"))

        if not resolved_path.exists():
            if is_optional:
                output["path"] = raw_path
                output["missing"] = True
                completed.append(output)
                continue
            raise FileNotFoundError(f"required output missing: {resolved_path}")

        output["path"] = raw_path
        output.pop("missing", None)

        if resolved_path.is_dir():
            children = _directory_children(resolved_path)
            output["entries"] = children
            output["bytes"] = int(output.get("bytes", sum(item["bytes"] for item in children)))
            output.setdefault("type", "directory")
            if not isinstance(output.get("content_hash"), str) or not output.get("content_hash"):
                output["content_hash"] = _tree_hash(children)
            completed.append(output)
            continue

        content_hash, sha256_value = _resolve_hash(output, path=resolved_path)
        output["content_hash"] = content_hash
        output["bytes"] = int(output.get("bytes", resolved_path.stat().st_size))
        output.setdefault("type", "file")
        if sha256_value is not None:
            output.setdefault("sha256", sha256_value)
        completed.append(output)

    return completed


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    missing_fields = sorted(_REQUIRED_FIELDS.difference(manifest))
    if missing_fields:
        raise ValueError(f"manifest missing required fields: {', '.join(missing_fields)}")

    schema_version = manifest["schema_version"]
    if not isinstance(schema_version, int):
        raise ValueError("schema_version must be an integer")

    kind = manifest["kind"]
    if not isinstance(kind, str) or not _KIND_RE.fullmatch(kind):
        raise ValueError("kind must be a lowercase slug-like string")

    if not isinstance(manifest["warnings"], list):
        raise ValueError("warnings must be a list")

    if not isinstance(manifest["outputs"], list):
        raise ValueError("outputs must be a list")

    _require_mapping(manifest["inputs"], "inputs")


def write_manifest(path: str | Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Validate, enrich, and atomically write a universal result manifest."""

    _validate_manifest(manifest)
    manifest_payload = dict(manifest)
    manifest_path = Path(path)
    manifest_payload["outputs"] = complete_output_metadata(
        manifest_payload["outputs"],
        root_dir=manifest_path.parent,
    )
    write_json_atomic(manifest_path, manifest_payload)
    return manifest_payload


__all__ = ["complete_output_metadata", "write_manifest"]
