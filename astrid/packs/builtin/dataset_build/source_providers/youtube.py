"""Generic YouTube source provider using existing Astrid executors."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

from ..acquisition import limit_hint_from_config, record_acquisition_result, request_from_config, string_set
from ..items import deterministic_id, make_candidate_item
from ..media import extract_clip_ffmpeg, ffprobe_metadata


Runner = Callable[..., subprocess.CompletedProcess[str]]


class YouTubeSourceProvider:
    provider_id = "youtube"

    def __init__(
        self,
        *,
        runner: Runner = subprocess.run,
        prober: Callable[[Path], dict[str, Any]] = ffprobe_metadata,
        **_: Any,
    ) -> None:
        self._runner = runner
        self._prober = prober

    def acquire(self, config: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        out_dir = Path(str(config.get("out_dir", "runs/dataset-build/youtube"))).expanduser().resolve()
        downloads_dir = out_dir / "downloads"
        scenes_dir = out_dir / "scenes"
        clips_dir = out_dir / "clips"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        scenes_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

        dataset_config = config.get("dataset_config") if isinstance(config.get("dataset_config"), Mapping) else {}
        clip_config = dataset_config.get("clip_config", {}) if isinstance(dataset_config, Mapping) else {}
        min_duration = float(config.get("min_duration_s", clip_config.get("min_duration_s", 0)))
        max_duration = float(config.get("max_duration_s", clip_config.get("max_duration_s", 60)))
        max_scenes = int(config.get("max_scenes_per_source", clip_config.get("max_scenes_per_source", 20)))

        request = request_from_config(config)
        processed_source_ids = string_set(config.get("processed_source_ids"), request.get("processed_source_ids"))
        exclude_source_ids = string_set(config.get("exclude_source_ids"), request.get("exclude_source_ids"))
        exclude_candidate_ids = string_set(config.get("exclude_candidate_ids"), request.get("exclude_candidate_ids"))
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

        try:
            for source in _configured_sources(config, dataset_config):
                considered += 1
                source_id = youtube_source_key(source)
                if source_id in processed_source_ids:
                    skipped_processed += 1
                    continue
                if source_id in exclude_source_ids:
                    skipped_excluded += 1
                    continue
                video_path = self._download_source(source, source_id=source_id, downloads_dir=downloads_dir)
                scenes = self._detect_scenes(video_path, scenes_dir / f"{video_path.stem}.scenes.json")
                if not scenes:
                    scenes = [{"start": 0.0, "end": _duration_or_zero(video_path, self._prober)}]
                for scene_index, scene in enumerate(scenes[:max_scenes]):
                    start_s, end_s = _scene_bounds(scene)
                    duration = end_s - start_s
                    if duration < min_duration or duration > max_duration:
                        continue
                    clip_id = deterministic_id(self.provider_id, source["kind"], source["value"], scene_index, prefix="yt")
                    if clip_id in exclude_candidate_ids:
                        skipped_excluded += 1
                        continue
                    clip_path = clips_dir / f"{clip_id}.mp4"
                    extract_clip_ffmpeg(
                        video_path,
                        start_s=start_s,
                        end_s=end_s,
                        out_path=clip_path,
                        runner=self._runner,
                    )
                    metadata = dict(self._prober(clip_path))
                    candidate = make_candidate_item(
                        source_type=self.provider_id,
                        source_id=clip_id,
                        source_url=source["value"] if source["kind"] == "url" else f"ytsearch:{source['value']}",
                        media_path=clip_path,
                        media_type="video",
                        source_metadata=metadata,
                        duration_s=duration,
                        clip_start_s=start_s,
                        clip_end_s=end_s,
                        scene_index=scene_index,
                        derived_from={
                            "source_id": source_id,
                            "source_type": self.provider_id,
                            "transformation": "scene_extract",
                        },
                        rights=config.get("rights"),
                    )
                    if str(candidate.get("content_hash") or "") in exclude_media_hashes:
                        skipped_duplicate_media += 1
                        continue
                    yield candidate
                    yielded += 1
                    if limit_hint is not None and yielded >= limit_hint:
                        return
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

    def _download_source(self, source: Mapping[str, str], *, source_id: str, downloads_dir: Path) -> Path:
        out_base = downloads_dir / source_id
        cmd = [
            sys.executable,
            "-m",
            "astrid.packs.builtin.youtube_audio.run",
            "--mode",
            "video",
            "--out",
            str(out_base),
        ]
        if source["kind"] == "url":
            cmd.extend(["--url", source["value"]])
        else:
            cmd.extend(["--query", source["value"]])
        self._runner(cmd, capture_output=True, text=True, check=True)
        return out_base.with_suffix(".mp4")

    def _detect_scenes(self, video_path: Path, out_path: Path) -> list[dict[str, Any]]:
        self._runner(
            [
                sys.executable,
                "-m",
                "astrid.packs.builtin.scenes.run",
                "--video",
                str(video_path),
                "--out",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        if not out_path.is_file():
            return []
        raw = json.loads(out_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, list) else raw.get("scenes", [])


def _configured_sources(config: Mapping[str, Any], dataset_config: Mapping[str, Any]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for key in ("source_urls", "urls"):
        for url in config.get(key, []) or []:
            sources.append({"kind": "url", "value": str(url)})
    for query in config.get("search_queries", []) or []:
        sources.append({"kind": "query", "value": str(query)})
    buckets = dataset_config.get("buckets", {}) if isinstance(dataset_config, Mapping) else {}
    for bucket in buckets.values():
        if isinstance(bucket, Mapping):
            for query in bucket.get("search_queries", []) or []:
                sources.append({"kind": "query", "value": str(query)})
    return sources


def youtube_source_key(source: Mapping[str, str]) -> str:
    return deterministic_id("youtube", source.get("kind", ""), source.get("value", ""), prefix="yt_source")


def _scene_bounds(scene: Mapping[str, Any]) -> tuple[float, float]:
    start = scene.get("start", scene.get("start_s", scene.get("start_time", 0)))
    end = scene.get("end", scene.get("end_s", scene.get("end_time", 0)))
    return float(start), float(end)


def _duration_or_zero(video_path: Path, prober: Callable[[Path], dict[str, Any]]) -> float:
    try:
        return float(prober(video_path).get("duration_s", 0.0))
    except Exception:  # noqa: BLE001 - fallback lets caller skip zero-duration full-source candidate
        return 0.0
