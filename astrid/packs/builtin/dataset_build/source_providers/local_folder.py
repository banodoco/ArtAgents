"""Offline local-folder source provider."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

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
        paths = root.rglob("*") if recursive else root.iterdir()
        for media_path in sorted(path for path in paths if path.is_file() and path.suffix.lower() in extensions):
            metadata = dict(self._prober(media_path))
            source_id = str(
                _source_id_for_path(config, media_path)
                or deterministic_id(self.provider_id, media_path, prefix="local")
            )
            yield make_candidate_item(
                source_type=self.provider_id,
                source_id=source_id,
                source_url=media_path.as_uri(),
                media_path=media_path,
                media_type="video",
                source_metadata=metadata,
                duration_s=metadata.get("duration_s"),
                rights=config.get("rights"),
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
