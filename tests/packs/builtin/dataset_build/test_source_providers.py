from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from astrid.packs.builtin.dataset_build.source_providers import get_source_provider, iter_source_candidates
from astrid.packs.builtin.dataset_build.source_providers.local_folder import LocalFolderSourceProvider
from astrid.packs.builtin.dataset_build.source_providers.youtube import YouTubeSourceProvider, youtube_source_key


def _probe(path: Path) -> dict[str, Any]:
    return {
        "duration_s": 4.0,
        "resolution": {"width": 128, "height": 128},
        "fps": 24.0,
        "codec": "h264",
        "file_size_bytes": path.stat().st_size if path.exists() else 0,
    }


def test_local_folder_provider_creates_hashed_probed_candidates_without_network(tmp_path: Path) -> None:
    first = tmp_path / "first.mp4"
    second = tmp_path / "second.mov"
    ignored = tmp_path / "ignored.txt"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    ignored.write_text("nope", encoding="utf-8")

    provider = LocalFolderSourceProvider(prober=_probe)
    candidates = list(provider.acquire({"path": str(tmp_path), "recursive": False, "rights": {"rights_status": "verified"}}))

    assert [item["media_path"] for item in candidates] == [str(first.resolve()), str(second.resolve())]
    assert all(item["source_type"] == "local_folder" for item in candidates)
    assert all(item["content_hash"] for item in candidates)
    assert all(item["source_metadata"]["resolution"] == {"width": 128, "height": 128} for item in candidates)
    assert all(item["rights"]["rights_status"] == "verified" for item in candidates)


def test_source_provider_registry_dispatches_config_sources(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"clip")
    config = {"sources": [{"provider": "local_folder", "config": {"path": str(tmp_path)}}]}

    assert isinstance(get_source_provider("local_folder", prober=_probe), LocalFolderSourceProvider)
    candidates = list(iter_source_candidates(config, prober=_probe))
    assert len(candidates) == 1
    assert candidates[0]["source_id"].startswith("local_")


def test_youtube_provider_delegates_download_scene_split_and_internal_clip_extract(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if "astrid.packs.builtin.youtube_audio.run" in cmd:
            out_base = Path(cmd[cmd.index("--out") + 1])
            out_base.with_suffix(".mp4").write_bytes(b"video")
        elif "astrid.packs.builtin.scenes.run" in cmd:
            out_path = Path(cmd[cmd.index("--out") + 1])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(
                json.dumps(
                    [
                        {"start": 0.0, "end": 1.0},
                        {"start": 1.0, "end": 4.0},
                        {"start": 4.0, "end": 20.0},
                    ]
                ),
                encoding="utf-8",
            )
        elif cmd and cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    provider = YouTubeSourceProvider(runner=runner, prober=_probe)
    candidates = list(
        provider.acquire(
            {
                "out_dir": str(tmp_path / "yt"),
                "source_urls": ["https://youtube.example/watch?v=1"],
                "dataset_config": {"clip_config": {"min_duration_s": 2.0, "max_duration_s": 5.0}},
            }
        )
    )

    assert len(candidates) == 1
    assert candidates[0]["source_type"] == "youtube"
    assert candidates[0]["duration_s"] == 3.0
    assert candidates[0]["clip_start_s"] == 1.0
    assert candidates[0]["clip_end_s"] == 4.0
    assert any("astrid.packs.builtin.youtube_audio.run" in cmd for cmd in calls)
    assert any("astrid.packs.builtin.scenes.run" in cmd for cmd in calls)
    assert any(cmd and cmd[0] == "ffmpeg" for cmd in calls)
    assert not any(cmd and cmd[0] == "yt-dlp" for cmd in calls)


def test_youtube_provider_uses_bucket_search_queries_from_config(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if "astrid.packs.builtin.youtube_audio.run" in cmd:
            Path(cmd[cmd.index("--out") + 1]).with_suffix(".mp4").write_bytes(b"video")
        elif "astrid.packs.builtin.scenes.run" in cmd:
            Path(cmd[cmd.index("--out") + 1]).write_text(json.dumps([{"start": 0.0, "end": 3.0}]), encoding="utf-8")
        elif cmd and cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"clip")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    provider = YouTubeSourceProvider(runner=runner, prober=_probe)
    candidates = list(
        provider.acquire(
            {
                "out_dir": str(tmp_path / "yt"),
                "dataset_config": {
                    "buckets": {
                        "a": {"target_count": 1, "search_queries": ["query from bucket"]},
                    },
                    "clip_config": {"min_duration_s": 1.0, "max_duration_s": 5.0},
                },
            }
        )
    )

    assert len(candidates) == 1
    query_commands = [cmd for cmd in calls if "astrid.packs.builtin.youtube_audio.run" in cmd]
    assert query_commands[0][query_commands[0].index("--query") + 1] == "query from bucket"


def test_youtube_provider_skips_processed_source_before_download(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    source = {"kind": "url", "value": "https://youtube.example/watch?v=already"}

    def runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        raise AssertionError("processed YouTube source should skip before download")

    provider = YouTubeSourceProvider(runner=runner, prober=_probe)
    candidates = list(
        provider.acquire(
            {
                "out_dir": str(tmp_path / "yt"),
                "source_urls": [source["value"]],
                "processed_source_ids": [youtube_source_key(source)],
            }
        )
    )

    assert candidates == []
    assert calls == []
