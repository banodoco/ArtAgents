"""Offline local-folder source provider."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

from ..acquisition import limit_hint_from_config, record_acquisition_result, request_from_config, string_set
from ..items import deterministic_id, make_candidate_item
from ..media import ffprobe_metadata


DEFAULT_EXTENSIONS = (".mp4", ".mov")


class LocalFolderSourceProvider:
    provider_id = "local_folder"

    def __init__(self, *, prober: Callable[[Path], dict[str, Any]] = ffprobe_metadata, **_: Any) -> None:
        self._prober = prober

    def acquire(self, config: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        root = Path(str(config["path"])).expanduser().resolve()
        recursive = bool(config.get("recursive", False))
        extensions = tuple(str(ext).lower() for ext in config.get("extensions", DEFAULT_EXTENSIONS))
        request = request_from_config(config)
        exclude_candidate_ids = string_set(config.get("exclude_candidate_ids"), request.get("exclude_candidate_ids"))
        processed_source_ids = string_set(config.get("processed_source_ids"), request.get("processed_source_ids"))
        exclude_source_ids = string_set(config.get("exclude_source_ids"), request.get("exclude_source_ids"), processed_source_ids)
        exclude_media_hashes = string_set(config.get("exclude_media_hashes"), request.get("exclude_media_hashes"))
        limit_hint = limit_hint_from_config(config, request)
        considered = 0
        skipped_processed = 0
        skipped_excluded = 0
        skipped_duplicate_media = 0
        if limit_hint == 0:
            record_acquisition_result(
                self,
                config,
                provider_id=self.provider_id,
                request=request,
                considered=0,
                yielded=0,
            )
            return
        yielded = 0
        paths = root.rglob("*") if recursive else root.iterdir()
        try:
            media_paths = sorted(path for path in paths if path.is_file() and path.suffix.lower() in extensions)
            for media_path in media_paths:
                considered += 1
                source_id = str(
                    _source_id_for_path(config, media_path)
                    or deterministic_id(self.provider_id, media_path, prefix="local")
                )
                if source_id in processed_source_ids:
                    skipped_processed += 1
                    continue
                if source_id in exclude_source_ids or source_id in exclude_candidate_ids:
                    skipped_excluded += 1
                    continue
                metadata = dict(self._prober(media_path))
                candidate = make_candidate_item(
                    source_type=self.provider_id,
                    source_id=source_id,
                    source_url=media_path.as_uri(),
                    media_path=media_path,
                    media_type="video",
                    source_metadata=metadata,
                    duration_s=metadata.get("duration_s"),
                    rights=config.get("rights"),
                )
                if str(candidate.get("content_hash") or "") in exclude_media_hashes:
                    skipped_duplicate_media += 1
                    continue
                yield candidate
                yielded += 1
                if limit_hint is not None and yielded >= limit_hint:
                    break
        finally:
            record_acquisition_result(
                self,
                config,
                provider_id=self.provider_id,
                request=request,
                considered=considered,
                yielded=yielded,
                skipped_processed=skipped_processed,
                skipped_excluded=skipped_excluded,
                skipped_duplicate_media=skipped_duplicate_media,
            )


def _source_id_for_path(config: Mapping[str, Any], media_path: Path) -> str | None:
    template = config.get("source_id_template")
    if isinstance(template, str) and template:
        return template.format(
            stem=media_path.stem,
            name=media_path.name,
            suffix=media_path.suffix.lstrip("."),
        )
    source_id = config.get("source_id")
    return str(source_id) if source_id else None
