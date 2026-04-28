"""Asset resolution for `banodoco_render_timeline` (Sprint 8).

For each entry in the task's `assets` registry the worker needs a local
file path that Remotion's local HTTP server can serve from. Two cases:

  * HTTP/HTTPS URL — pass through. The Remotion render path keeps the
    URL because Remotion can stream from `http(s)://` directly (Range
    request support is on the upstream's responsibility).
  * Storage key (e.g. `<user_id>/<timeline_id>/asset.mp4`) — download
    from Reigh's `timeline-assets` bucket via service-role to a local
    temp dir.

Cache (in-process):

  * Keyed by sha256 of the resolved bytes (not the storage key — same
    bytes referenced twice in a timeline shouldn't redownload).
  * Lifetime: this Python process. No disk persistence in v1; LRU disk
    eviction is the Sprint 9 follow-on.
  * `cache_get` / `cache_put` are split out so tests can poke at them
    without going through `resolve_asset`.

Environment used:
  REIGH_SUPABASE_URL                 — for the storage REST endpoint.
  REIGH_SUPABASE_SERVICE_ROLE_KEY    — service-role for downloads.
  BANODOCO_RENDER_ASSETS_BUCKET      — defaults to `timeline-assets`.

The worker still treats the user_jwt as the identity; the service-role
download is a SD-022 path-3 service call, audited via the worker's task
logs (the task itself records the verified user_id from worker_jwt).
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


DEFAULT_ASSETS_BUCKET = "timeline-assets"


# ---------------------------------------------------------------------------
# In-process cache
# ---------------------------------------------------------------------------

# sha256 hex string -> Path (already-downloaded file we can reuse).
_CACHE: Dict[str, Path] = {}


def cache_get(sha256: str) -> Optional[Path]:
    """Return a cached file path for a sha256, or None if not cached.

    Verifies the file still exists; a stale cache entry (e.g. tempdir
    cleanup elsewhere) is treated as a miss and dropped.
    """
    path = _CACHE.get(sha256)
    if path is None:
        return None
    if not path.exists():
        _CACHE.pop(sha256, None)
        return None
    return path


def cache_put(sha256: str, file_path: Path) -> None:
    """Register an existing file under its sha256 hash."""
    _CACHE[sha256] = file_path


def cache_clear() -> None:
    """Drop the cache. Test helper; not used at runtime."""
    _CACHE.clear()


def sha256_of_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Asset entry shape utilities
# ---------------------------------------------------------------------------


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _entry_field(entry: Any, *names: str) -> Optional[str]:
    if not isinstance(entry, dict):
        return None
    for name in names:
        value = entry.get(name)
        if isinstance(value, str) and value.strip():
            return value
    return None


# ---------------------------------------------------------------------------
# Storage download (service-role)
# ---------------------------------------------------------------------------


def _supabase_storage_download_url(bucket: str, object_path: str) -> str:
    base = os.getenv("REIGH_SUPABASE_URL", "").rstrip("/")
    if not base:
        raise RuntimeError(
            "REIGH_SUPABASE_URL must be set for banodoco render asset downloads"
        )
    # Service-role (no signed-URL roundtrip needed) hits the storage REST
    # path directly with the service key as Authorization.
    return f"{base}/storage/v1/object/{bucket}/{object_path}"


def _download_storage_object(
    bucket: str,
    object_path: str,
    target: Path,
    *,
    http: Optional[httpx.Client] = None,
) -> None:
    url = _supabase_storage_download_url(bucket, object_path)
    service_role = os.getenv("REIGH_SUPABASE_SERVICE_ROLE_KEY", "")
    if not service_role:
        raise RuntimeError(
            "REIGH_SUPABASE_SERVICE_ROLE_KEY is required for asset downloads"
        )
    headers = {
        "Authorization": f"Bearer {service_role}",
        "apikey": service_role,
    }

    client = http or httpx.Client(timeout=120)
    try:
        with client.stream("GET", url, headers=headers) as resp:
            resp.raise_for_status()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as fh:
                for chunk in resp.iter_bytes():
                    if chunk:
                        fh.write(chunk)
    finally:
        if http is None:
            client.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_asset(
    asset_entry: Dict[str, Any],
    *,
    user_id: str,  # noqa: ARG001 — surfaced for SD-022 audit/logging callers
    work_dir: Path,
    bucket: Optional[str] = None,
    http: Optional[httpx.Client] = None,
) -> Tuple[str, Optional[Path]]:
    """Resolve a single asset registry entry.

    Returns (final_url_or_local, optional_local_path):
      - HTTP/HTTPS URL passthrough returns ``(url, None)``.
      - Storage-key download returns ``(local_url_substitute, local_path)``.
        Callers wire the local file into Remotion via its props.

    The asset entry shape mirrors the rest of the pipeline:
      { "url": "...", "file": "...", "storage_path": "...",
        "content_sha256": "..." }

    Lookup order: ``url`` (if HTTP) -> ``storage_path``/``key`` -> ``file``.
    """
    bucket = bucket or os.getenv("BANODOCO_RENDER_ASSETS_BUCKET", DEFAULT_ASSETS_BUCKET)

    url = _entry_field(asset_entry, "url")
    if url and _is_http_url(url):
        return url, None

    # Storage key path: we expect either an explicit storage key or a non-http
    # `url` (treated as a key). Prefer explicit fields.
    storage_key = (
        _entry_field(asset_entry, "storage_path", "storage_key", "key")
        or (url if url and not _is_http_url(url) else None)
    )

    if storage_key:
        sha256 = _entry_field(asset_entry, "content_sha256", "sha256")
        if sha256:
            cached = cache_get(sha256)
            if cached is not None:
                logger.info("[ASSETS] cache hit sha256=%s -> %s", sha256[:12], cached)
                return cached.as_uri(), cached

        target = work_dir / storage_key.replace("/", "__")
        _download_storage_object(bucket, storage_key, target, http=http)

        actual_sha = sha256_of_file(target)
        if sha256 and actual_sha != sha256:
            logger.warning(
                "[ASSETS] sha256 mismatch for %s (expected %s got %s)",
                storage_key, sha256[:12], actual_sha[:12],
            )
        cache_put(actual_sha, target)
        return target.as_uri(), target

    # Local path fallback (test fixtures or already-resolved entries).
    file_value = _entry_field(asset_entry, "file")
    if file_value:
        path = Path(file_value)
        if path.exists():
            return path.as_uri(), path

    raise ValueError(
        f"Cannot resolve asset entry: no http url, storage key, or existing file. "
        f"entry keys={sorted((asset_entry or {}).keys())}"
    )


def resolve_asset_registry(
    registry: Dict[str, Any],
    *,
    user_id: str,
    work_dir: Path,
    bucket: Optional[str] = None,
    http: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """Resolve every asset in the registry to a Remotion-friendly form.

    Returns a copy of the registry where each entry's ``file`` is set to a
    URL (http(s) passthrough or local file:// for downloaded entries).
    """
    if not isinstance(registry, dict):
        raise ValueError("registry must be a dict")

    assets_block = registry.get("assets")
    if not isinstance(assets_block, dict):
        # Caller may have passed a flat {key: entry} map.
        assets_block = registry
        registry_out: Dict[str, Any] = {"assets": {}}
        out_block = registry_out["assets"]
    else:
        registry_out = {**registry, "assets": {}}
        out_block = registry_out["assets"]

    for key, entry in assets_block.items():
        if not isinstance(entry, dict):
            out_block[key] = entry
            continue
        final_url, _local = resolve_asset(
            entry, user_id=user_id, work_dir=work_dir, bucket=bucket, http=http,
        )
        new_entry = dict(entry)
        new_entry["file"] = final_url
        out_block[key] = new_entry
    return registry_out


def make_render_workdir(prefix: str = "banodoco-render-") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


__all__ = [
    "DEFAULT_ASSETS_BUCKET",
    "cache_clear",
    "cache_get",
    "cache_put",
    "make_render_workdir",
    "resolve_asset",
    "resolve_asset_registry",
    "sha256_of_file",
]
