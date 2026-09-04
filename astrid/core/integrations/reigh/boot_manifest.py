"""Deterministic, secret-free B-6 profile boot manifest.

The manifest is a derived handoff, not an authority.  It is stamped by the
application composition root beside the runtime's ``astrid.sqlite3`` state.
The generic host only reads its hash for completion provenance; it never emits
or discovers profiles.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from astrid.core.receipts.canonical import canonical_json

BOOT_MANIFEST_FILENAME = "boot-manifest.json"
BOOT_MANIFEST_SCHEMA_VERSION = 1
_DEFAULT_PROFILE_ORDER = ("pip_embedded", "checkout_server")
_REGISTRY_ENTRY_FIELDS = ("definition_version", "binding", "output_policy", "probe")
_SECRET_WORDS = ("secret", "token", "password", "credential", "api_key", "private_key")


_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "profile_order",
        "profile_digests",
        "registry_digest",
        "conformance_digest",
        "fixture_digests",
    }
)


class BootManifestError(RuntimeError):
    """Base error for invalid or unsafe boot-manifest state."""


class BootManifestCorrupt(BootManifestError):
    """A stamped manifest cannot be trusted."""


class BootManifestDrift(BootManifestError):
    """Live registry/fixture identity differs from the stamped manifest."""

def _json_value(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _json_value(value.to_dict())
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_value(item) for item in value)
    return value


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(_json_value(value)).encode("utf-8")).hexdigest()


def _entry_identity(entry: Any) -> dict[str, Any]:
    raw = _json_value(entry)
    if not isinstance(raw, Mapping):
        raise BootManifestError("profile registry entries must be objects")
    if any(not isinstance(key, str) for key in raw):
        raise BootManifestError("profile registry entry keys must be strings")
    keys = set(raw)
    expected = set(_REGISTRY_ENTRY_FIELDS)
    unknown = keys - expected
    missing = expected - keys
    if unknown:
        raise BootManifestError(
            f"profile registry entry carries unknown fields: {sorted(unknown)!r}"
        )
    if missing:
        raise BootManifestError(
            f"profile registry entry is missing fields: {sorted(missing)!r}"
        )
    definition_version = raw["definition_version"]
    if isinstance(definition_version, bool) or not isinstance(definition_version, int):
        raise BootManifestError("profile registry definition_version must be an integer")
    identity: dict[str, Any] = {"definition_version": definition_version}
    for field in _REGISTRY_ENTRY_FIELDS[1:]:
        value = raw[field]
        if not isinstance(value, str) or not value:
            raise BootManifestError(
                f"profile registry field {field!r} must be a non-empty string"
            )
        identity[field] = value
    return identity


def registry_scope(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return the complete declarative registry identity."""
    if not isinstance(registry, Mapping):
        raise BootManifestError("profile registry must be an object")
    result: dict[str, Any] = {}
    for profile_id, entry in sorted(registry.items(), key=lambda item: str(item[0])):
        if not isinstance(profile_id, str) or not profile_id:
            raise BootManifestError("profile registry IDs must be non-empty strings")
        if profile_id in result:
            raise BootManifestError(f"duplicate profile registry ID {profile_id!r}")
        result[profile_id] = _entry_identity(entry)
    return result


def fixture_digest(fixture: Any) -> str:
    """Hash one complete profile fixture, including its accepted evidence."""
    return _sha256(fixture)


def _fixture_id(fixture: Any) -> str:
    value = _json_value(fixture)
    if not isinstance(value, Mapping):
        raise BootManifestError("profile fixtures must be objects")
    profile_id = value.get("profile_id", value.get("capability_id"))
    if not isinstance(profile_id, str) or not profile_id:
        raise BootManifestError("profile fixture requires profile_id")
    return profile_id


def fixture_scope(fixtures: Iterable[Any]) -> dict[str, str]:
    rows = tuple(fixtures)
    result: dict[str, str] = {}
    for fixture in rows:
        profile_id = _fixture_id(fixture)
        if profile_id in result:
            raise BootManifestError(f"duplicate profile fixture {profile_id!r}")
        result[profile_id] = fixture_digest(fixture)
    return {key: result[key] for key in sorted(result)}


def compute_registry_digest(registry: Mapping[str, Any], fixtures: Iterable[Any]) -> str:
    """Hash registry admission identity and fixture identity together."""
    return _sha256({"registry": registry_scope(registry), "fixtures": fixture_scope(fixtures)})


def compute_conformance_digest(fixtures: Iterable[Any]) -> str:
    """Hash the fixture scope independently for evidence and diagnostics."""
    return _sha256(fixture_scope(fixtures))


def _fixture_file_digests(fixtures: Iterable[Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for fixture in fixtures:
        raw = _json_value(fixture)
        if not isinstance(raw, Mapping):
            continue
        declared = raw.get("fixture_digests", {})
        if isinstance(declared, Mapping):
            for name, digest in declared.items():
                if str(name) in result and result[str(name)] != str(digest):
                    raise BootManifestError(f"fixture digest disagreement for {name!r}")
                result[str(name)] = str(digest)
    return {key: result[key] for key in sorted(result)}


def consume_profiles(
    fixtures: Iterable[Any],
    *,
    profile_order: Iterable[str] = _DEFAULT_PROFILE_ORDER,
) -> tuple[Any, ...]:
    """Consume explicit profile rows without selecting an engine route."""
    rows = tuple(fixtures)
    expected = tuple(str(item) for item in profile_order)
    actual = tuple(_fixture_id(row) for row in rows)
    if actual != expected:
        raise BootManifestError(
            f"profile fixtures must be consumed in frozen order: expected={expected!r} actual={actual!r}"
        )
    return rows


def build_manifest(
    *,
    registry: Mapping[str, Any] | None = None,
    fixtures: Iterable[Any] | None = None,
    profile_order: Iterable[str] = _DEFAULT_PROFILE_ORDER,
) -> dict[str, Any]:
    """Build the frozen manifest from explicit registry and fixture inputs."""
    if registry is None or fixtures is None:
        from astrid.packs.shots.conformance import VIBE_PROFILE_REGISTRY, vibe_profile_specs

        if registry is None:
            registry = VIBE_PROFILE_REGISTRY
        if fixtures is None:
            fixtures = vibe_profile_specs()
    fixture_rows = consume_profiles(fixtures, profile_order=profile_order)
    order = tuple(str(item) for item in profile_order)
    if len(order) != len(set(order)):
        raise BootManifestError("profile order contains duplicates")
    registry_ids = tuple(sorted(str(item) for item in registry))
    if set(order) != set(registry_ids):
        raise BootManifestError(
            f"profile order and registry disagree: order={order!r} registry={registry_ids!r}"
        )
    fixture_ids = set(fixture_scope(fixture_rows))
    if fixture_ids != set(order):
        raise BootManifestError(
            f"profile order and fixtures disagree: order={order!r} fixtures={sorted(fixture_ids)!r}"
        )
    profile_digests = fixture_scope(fixture_rows)
    manifest = {
        "schema_version": BOOT_MANIFEST_SCHEMA_VERSION,
        "profile_order": list(order),
        "profile_digests": {profile_id: profile_digests[profile_id] for profile_id in order},
        "registry_digest": compute_registry_digest(registry, fixture_rows),
        "conformance_digest": compute_conformance_digest(fixture_rows),
        "fixture_digests": _fixture_file_digests(fixture_rows),
    }
    assert_secret_free(manifest)
    return manifest


def manifest_hash(manifest: Mapping[str, Any]) -> str:
    """Return the canonical hash carried by completion provenance."""
    return _sha256(dict(manifest))


def assert_secret_free(manifest: Mapping[str, Any]) -> None:
    """Reject unknown fields and recursively reject credential-shaped data."""
    unknown = set(manifest) - _MANIFEST_FIELDS
    if unknown:
        raise BootManifestError(f"boot manifest carries unknown fields: {sorted(unknown)!r}")

    def walk(value: Any, path: str = "manifest") -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                lowered = str(key).lower()
                if any(word in lowered for word in _SECRET_WORDS):
                    raise BootManifestError(f"boot manifest is not secret-free at {path}.{key}")
                walk(item, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(manifest)
    if isinstance(manifest.get("schema_version"), bool) or not isinstance(manifest.get("schema_version"), int):
        raise BootManifestError("boot manifest schema_version must be an integer")
    for field in ("registry_digest", "conformance_digest"):
        value = manifest.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise BootManifestError(
                f"boot manifest field {field!r} must be a SHA-256 digest"
            )
    for field in ("profile_digests", "fixture_digests"):
        values = manifest.get(field)
        if not isinstance(values, Mapping):
            raise BootManifestError(f"boot manifest field {field!r} must be an object")
        for key, value in values.items():
            if (
                not isinstance(key, str)
                or not isinstance(value, str)
                or len(value) != 64
                or any(char not in "0123456789abcdef" for char in value)
            ):
                raise BootManifestError(
                    f"boot manifest field {field!r} contains an invalid digest"
                )

def validate_state_path(state_path: str | Path) -> Path:
    """Require an explicit, existing Astrid SQLite state file."""
    path = Path(state_path).expanduser()
    if path.name != "astrid.sqlite3":
        raise BootManifestError(f"Astrid state must be named astrid.sqlite3: {path}")
    if path.is_symlink() or not path.is_file():
        raise BootManifestError(
            f"Astrid state must be an existing regular, non-symlink file: {path}"
        )
    return path.resolve()


def validate_explicit_boot_manifest(path: str | Path) -> tuple[Path, Path]:
    """Validate an existing manifest and return it with its sibling state."""
    manifest = Path(path).expanduser()
    if manifest.name != BOOT_MANIFEST_FILENAME:
        raise BootManifestError(
            f"boot manifest must be named {BOOT_MANIFEST_FILENAME}: {manifest}"
        )
    if manifest.is_symlink() or not manifest.is_file():
        raise BootManifestError(
            f"boot manifest must be an existing regular, non-symlink file: {manifest}"
        )
    parent = manifest.parent
    if parent.name != ".astrid" or parent.is_symlink() or not parent.is_dir():
        raise BootManifestError(
            f"boot manifest must be in an existing non-symlink .astrid directory: {manifest}"
        )
    state = validate_state_path(parent / "astrid.sqlite3")
    return manifest.resolve(), state


def boot_manifest_path(state_path_or_root: str | Path) -> Path:
    """Resolve the manifest path from a validated state file."""
    path = Path(state_path_or_root).expanduser().resolve()
    if path.name != "astrid.sqlite3":
        raise BootManifestError(f"Astrid state must be named astrid.sqlite3: {path}")
    return path.with_name(BOOT_MANIFEST_FILENAME)


def _load_stored(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BootManifestCorrupt(f"stamped boot manifest unreadable at {path}: {exc}") from None
    if not isinstance(raw, dict):
        raise BootManifestCorrupt(f"stamped boot manifest at {path} must be an object")
    try:
        assert_secret_free(raw)
    except BootManifestError as exc:
        raise BootManifestCorrupt(str(exc)) from exc
    return raw


def stamp_boot_manifest(
    state_path_or_root: str | Path,
    *,
    registry: Mapping[str, Any] | None = None,
    fixtures: Iterable[Any] | None = None,
    profile_order: Iterable[str] = _DEFAULT_PROFILE_ORDER,
) -> dict[str, Any]:
    state_path = validate_state_path(state_path_or_root)
    current = build_manifest(
        registry=registry,
        fixtures=fixtures,
        profile_order=profile_order,
    )
    path = boot_manifest_path(state_path)
    if path.is_symlink():
        raise BootManifestCorrupt(
            f"stamped boot manifest must be a non-symlink regular file: {path}"
        )
    if path.exists() and not path.is_file():
        raise BootManifestCorrupt(
            f"stamped boot manifest must be a regular file: {path}"
        )
    if path.exists():
        stored = _load_stored(path)
        if stored != current:
            drift = sorted(set(stored) | set(current))
            details = "; ".join(f"key={key} stamped={stored.get(key)!r} live={current.get(key)!r}" for key in drift if stored.get(key) != current.get(key))
            raise BootManifestDrift(f"boot manifest disagrees with live registry/fixtures at {path}: {details}")
        return current
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".boot-manifest-", suffix=".tmp", delete=False)
    try:
        json.dump(current, handle, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    except BaseException:
        try:
            handle.close()
        finally:
            Path(handle.name).unlink(missing_ok=True)
        raise
    return current

def load_boot_manifest_hash(state_path_or_root: str | Path) -> str | None:
    raw_path = Path(state_path_or_root).expanduser()
    path = (
        raw_path.resolve()
        if raw_path.name == BOOT_MANIFEST_FILENAME
        else boot_manifest_path(raw_path)
    )
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise BootManifestCorrupt(
            f"stamped boot manifest must be a non-symlink regular file: {path}"
        )
    return manifest_hash(_load_stored(path))


__all__ = [
    "BOOT_MANIFEST_FILENAME",
    "BOOT_MANIFEST_SCHEMA_VERSION",
    "BootManifestCorrupt",
    "BootManifestDrift",
    "BootManifestError",
    "assert_secret_free",
    "validate_explicit_boot_manifest",
    "validate_state_path",
    "boot_manifest_path",
    "build_manifest",
    "compute_conformance_digest",
    "compute_registry_digest",
    "consume_profiles",
    "fixture_digest",
    "fixture_scope",
    "load_boot_manifest_hash",
    "manifest_hash",
    "registry_scope",
    "stamp_boot_manifest",
]
