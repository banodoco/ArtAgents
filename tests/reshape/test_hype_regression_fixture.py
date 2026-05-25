from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from astrid import timeline

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "reshape" / "hype_regression"
REQUIRED_SMALL_FIXTURES = (
    "hype.timeline.json",
    "hype.assets.json",
    "hype.metadata.json",
    "media_manifest.json",
)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_deterministic_media(path: Path, *, duration: float, resolution: str, fps: float) -> None:
    if path.is_file():
        return
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip(f"ffmpeg is required to create deterministic fixture media: {path.name}")
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={resolution}:r={fps}:d={duration}",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=channel_layout=stereo:sample_rate=48000:d={duration}",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "35",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(path),
    ]
    result = subprocess.run(cmd, cwd=FIXTURE_ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, (
        f"failed to create deterministic fixture media {path.name}: {result.stderr.strip()}"
    )


def test_hype_regression_required_small_fixtures_exist_and_validate() -> None:
    missing = [name for name in REQUIRED_SMALL_FIXTURES if not (FIXTURE_ROOT / name).is_file()]
    assert missing == [], f"missing required hype regression fixture(s): {missing}"

    timeline_payload = _read_json(FIXTURE_ROOT / "hype.timeline.json")
    assets_payload = _read_json(FIXTURE_ROOT / "hype.assets.json")
    metadata_payload = _read_json(FIXTURE_ROOT / "hype.metadata.json")
    manifest = _read_json(FIXTURE_ROOT / "media_manifest.json")

    timeline.validate_timeline(timeline_payload)
    assert metadata_payload["pipeline"]["steps_run"] == ["cut"]

    assets = assets_payload["assets"]
    track_ids = {track["id"] for track in timeline_payload["tracks"]}
    for clip in timeline_payload["clips"]:
        assert clip["track"] in track_ids
        if clip.get("clipType") == "media":
            assert clip["asset"] in assets

    for name in ("hype.timeline.json", "hype.assets.json", "hype.metadata.json"):
        assert manifest["source_artifacts"][name]["sha256"] == _sha256(FIXTURE_ROOT / name)


def test_hype_regression_media_manifest_covers_optional_mp4_assets() -> None:
    assets_payload = _read_json(FIXTURE_ROOT / "hype.assets.json")
    manifest = _read_json(FIXTURE_ROOT / "media_manifest.json")
    media_by_asset = {entry["asset_id"]: entry for entry in manifest["media"]}

    missing_media: list[str] = []
    for asset_id, asset in assets_payload["assets"].items():
        media_entry = media_by_asset[asset_id]
        media_path = FIXTURE_ROOT / media_entry["path"]
        assert media_entry["path"] == asset["file"]
        assert media_entry["expected_duration_seconds"] == asset["duration"]
        assert media_entry["expected_resolution"] == asset["resolution"]
        assert media_entry["expected_fps"] == asset["fps"]
        if not media_path.is_file():
            _ensure_deterministic_media(
                media_path,
                duration=float(media_entry["expected_duration_seconds"]),
                resolution=str(media_entry["expected_resolution"]),
                fps=float(media_entry["expected_fps"]),
            )
        if not media_path.is_file():
            missing_media.append(media_entry["path"])

    assert missing_media == [], (
        "media-dependent hype regression checks require deterministic mp4 artifacts; "
        f"missing after creation attempt: {sorted(missing_media)}"
    )

    for media_entry in media_by_asset.values():
        digest = _sha256(FIXTURE_ROOT / media_entry["path"])
        if media_entry["sha256"] is not None:
            assert media_entry["sha256"] == digest
        else:
            assert len(digest) == 64
