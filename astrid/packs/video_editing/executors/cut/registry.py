"""Asset registry construction helpers for the cut executor.

Extracted from ``run.py`` during M4 giant-file decomposition (T78).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrid.core.contracts.errors import AstridError
from astrid.core.timeline import CARRY_FORWARD_SOURCE_FIELDS, AssetRegistry
from astrid.packs.training.executors.asset_cache import run as asset_cache

from .probe import _FFPROBE_VERBOSE


def _lookup_probe_asset():
    """Late-bound lookup for ``probe_asset`` through the run.py facade.

    Tests monkeypatch ``run.probe_asset`` and need that seam to reach
    the probe calls inside ``build_registry``.  Looking up the function
    at call time through the facade preserves that contract.
    """
    run_module = sys.modules.get("astrid.packs.video_editing.executors.cut.run")
    if run_module is not None:
        return run_module.probe_asset
    # Fallback: import directly (no monkeypatching in play).
    from .probe import probe_asset as _direct

    return _direct


def _url_cache_meta(url: str) -> dict[str, Any]:
    cache_path = asset_cache._path_for(url)
    if not cache_path.exists():
        return {}
    return asset_cache._read_meta(cache_path)


def resolve_asset_paths(args: Any) -> tuple[dict[str, Path], dict[str, str]]:
    asset_paths: dict[str, Path] = {}
    asset_urls: dict[str, str] = {}
    raw_assets = getattr(args, "asset", None) or []
    for raw_entry in raw_assets:
        if not isinstance(raw_entry, str) or "=" not in raw_entry:
            raise AstridError(f"Invalid --asset value {raw_entry!r}: expected KEY=PATH")
        key, raw_path = raw_entry.split("=", 1)
        if not key or not raw_path:
            raise AstridError(f"Invalid --asset value {raw_entry!r}: expected KEY=PATH")
        if key in asset_paths or key in asset_urls:
            raise AstridError(f"Duplicate asset key {key!r} in --asset")
        if asset_cache.is_url(raw_path):
            asset_urls[key] = raw_path
        else:
            asset_paths[key] = Path(raw_path).resolve()

    video_path = getattr(args, "video", None)
    if video_path is not None:
        if "main" in asset_paths or "main" in asset_urls:
            raise AstridError("Duplicate asset key 'main': provided by both --asset and --video")
        if asset_cache.is_url(video_path):
            asset_urls["main"] = video_path
        else:
            asset_paths["main"] = Path(video_path).resolve()
    audio_path = getattr(args, "audio", None)
    if audio_path is not None and video_path is None:
        if "rant" in asset_paths or "rant" in asset_urls:
            raise AstridError("Duplicate asset key 'rant': provided by both --asset and --audio")
        if asset_cache.is_url(audio_path):
            asset_urls["rant"] = audio_path
        else:
            asset_paths["rant"] = Path(audio_path).resolve()
    return asset_paths, asset_urls


def build_registry(
    asset_paths: dict[str, Path],
    asset_urls: dict[str, str],
    existing_registry: AssetRegistry,
    prior_meta: dict[str, Any] | None,
) -> tuple[AssetRegistry, dict[str, dict[str, Any]]]:
    registry: AssetRegistry = {"assets": {}}
    sources_meta: dict[str, dict[str, Any]] = {}
    existing_assets = existing_registry.get("assets", {})
    prior_sources = (prior_meta or {}).get("sources", {})
    for key, url in asset_urls.items():
        existing_entry = existing_assets.get(key) if isinstance(existing_assets, dict) else None
        cache_hit = isinstance(existing_entry, dict) and existing_entry.get("url") == url and (
            (
                existing_entry.get("type") == "audio"
                and existing_entry.get("duration") is not None
            )
            or (
                existing_entry.get("duration") is not None
                and existing_entry.get("resolution") not in (None, "")
                and existing_entry.get("fps") is not None
            )
        )
        prior_source = prior_sources.get(key, {}) if isinstance(prior_sources, dict) else {}
        if not isinstance(prior_source, dict):
            prior_source = {}
        carried = {field: prior_source[field] for field in CARRY_FORWARD_SOURCE_FIELDS if field in prior_source}
        sources_meta[key] = dict(carried)
        cache_meta = _url_cache_meta(url)

        if cache_hit:
            if _FFPROBE_VERBOSE:
                print(f"ffprobe SKIP {key}")
            entry: dict[str, Any] = {
                "url": url,
                "duration": existing_entry["duration"],
                "type": existing_entry.get("type", "video"),
            }
            if entry["type"] != "audio":
                entry["resolution"] = existing_entry["resolution"]
                entry["fps"] = existing_entry["fps"]
            for field in ("content_sha256", "etag"):
                value = cache_meta.get(field, existing_entry.get(field))
                if isinstance(value, str) and value:
                    entry[field] = value
            registry["assets"][key] = entry
            continue

        if _FFPROBE_VERBOSE:
            print(f"ffprobe RUN {key}")
        probed = _lookup_probe_asset()(url)
        probed_type = probed.get("type", "video")
        entry = {
            "url": url,
            "duration": probed["duration"],
            "type": probed_type,
        }
        if probed_type != "audio":
            entry["resolution"] = probed["resolution"]
            entry["fps"] = probed["fps"]
        for field in ("content_sha256", "etag"):
            value = cache_meta.get(field)
            if isinstance(value, str) and value:
                entry[field] = value
        registry["assets"][key] = entry
        sources_meta[key]["codec"] = probed["codec"]

    for key, path in asset_paths.items():
        resolved_path = path.resolve()
        existing_entry = existing_assets.get(key) if isinstance(existing_assets, dict) else None
        cache_hit = (
            isinstance(existing_entry, dict)
            and existing_entry.get("file") == str(resolved_path)
            and existing_entry.get("duration") is not None
            and (
                existing_entry.get("type") == "audio"
                or (existing_entry.get("resolution") not in (None, "") and existing_entry.get("fps") is not None)
            )
        )
        prior_source = prior_sources.get(key, {}) if isinstance(prior_sources, dict) else {}
        if not isinstance(prior_source, dict):
            prior_source = {}
        carried = {field: prior_source[field] for field in CARRY_FORWARD_SOURCE_FIELDS if field in prior_source}
        sources_meta[key] = dict(carried)

        if cache_hit:
            if _FFPROBE_VERBOSE:
                print(f"ffprobe SKIP {key}")
            registry["assets"][key] = {
                "file": str(resolved_path),
                "duration": existing_entry["duration"],
                "type": existing_entry.get("type", "video"),
            }
            if registry["assets"][key]["type"] != "audio":
                registry["assets"][key]["resolution"] = existing_entry["resolution"]
                registry["assets"][key]["fps"] = existing_entry["fps"]
            continue

        if _FFPROBE_VERBOSE:
            print(f"ffprobe RUN {key}")
        probed = _lookup_probe_asset()(resolved_path)
        probed_type = probed.get("type", "video")
        registry["assets"][key] = {
            "file": str(resolved_path),
            "duration": probed["duration"],
            "type": probed_type,
        }
        if probed_type != "audio":
            registry["assets"][key]["resolution"] = probed["resolution"]
            registry["assets"][key]["fps"] = probed["fps"]
        sources_meta[key]["codec"] = probed["codec"]
    return registry, sources_meta


def rebase_registry_paths(registry: AssetRegistry, assets_dir: Path) -> AssetRegistry:
    rebased_assets: dict[str, dict[str, Any]] = {}
    for key, entry in registry["assets"].items():
        rebased_entry = dict(entry)
        file_value = rebased_entry.get("file")
        if isinstance(file_value, str):
            resolved = Path(file_value)
            if not resolved.is_absolute():
                rebased_entry["file"] = str((assets_dir / file_value).resolve())
        rebased_assets[key] = rebased_entry
    return {"assets": rebased_assets}
