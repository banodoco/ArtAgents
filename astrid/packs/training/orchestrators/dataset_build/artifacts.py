"""Shared artifact hash and sidecar cache helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .items import sha256_file, stable_json_sha256

HASHES_KEY = "hashes"
_RUNTIME_CONFIG_KEYS = {
    "artifact_helpers",
    "budget_tracker",
    "clock",
    "sleep",
}


def prompt_hash(prompt: str) -> str:
    return stable_json_sha256({"prompt": prompt})


def schema_hash(schema: str | Path | Mapping[str, Any] | None) -> str | None:
    if schema is None:
        return None
    if isinstance(schema, Mapping):
        return stable_json_sha256(schema)
    path = Path(str(schema)).expanduser()
    if path.is_file():
        return sha256_file(path)
    return stable_json_sha256({"schema": str(schema)})


def media_hash(item_or_path: Mapping[str, Any] | str | Path) -> str:
    if isinstance(item_or_path, Mapping):
        content_hash = item_or_path.get("content_hash")
        if isinstance(content_hash, str) and content_hash:
            return content_hash
        media_path = item_or_path.get("media_path")
        if isinstance(media_path, str) and media_path:
            return sha256_file(media_path)
        return stable_json_sha256(item_or_path)
    return sha256_file(item_or_path)


def config_hash(config: Mapping[str, Any] | None) -> str | None:
    if not config:
        return None
    serializable = {
        str(key): value
        for key, value in config.items()
        if str(key) not in _RUNTIME_CONFIG_KEYS and _is_json_serializable(value)
    }
    return stable_json_sha256(serializable)


def sidecar_hashes(
    *,
    prompt: str,
    schema: str | Path | Mapping[str, Any] | None,
    media: Mapping[str, Any] | str | Path,
    config: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    hashes = {
        "prompt_hash": prompt_hash(prompt),
        "media_hash": media_hash(media),
    }
    schema_digest = schema_hash(schema)
    if schema_digest is not None:
        hashes["schema_hash"] = schema_digest
    config_digest = config_hash(config)
    if config_digest is not None:
        hashes["config_hash"] = config_digest
    return hashes


def load_valid_cached_sidecar(
    path: str | Path,
    expected_hashes: Mapping[str, str],
    *,
    fixture_mode: bool = False,
) -> dict[str, Any] | None:
    sidecar = Path(path)
    if not sidecar.is_file():
        return None
    raw = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return None
    actual_hashes = raw.get(HASHES_KEY)
    if not isinstance(actual_hashes, Mapping):
        return raw if fixture_mode else None
    for key, expected in expected_hashes.items():
        if expected and actual_hashes.get(key) != expected:
            return None
    return raw


def unlink_stale_sidecar(path: str | Path) -> None:
    sidecar = Path(path)
    if sidecar.is_file():
        sidecar.unlink()


def write_hashed_sidecar(
    path: str | Path,
    payload: Mapping[str, Any],
    hashes: Mapping[str, str],
) -> dict[str, Any]:
    sidecar = Path(path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    document = dict(payload)
    document[HASHES_KEY] = dict(sorted((str(key), str(value)) for key, value in hashes.items() if value))
    sidecar.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def _is_json_serializable(value: Any) -> bool:
    try:
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    except (TypeError, ValueError):
        return False
    return True
