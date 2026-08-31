"""Permanent guards for runtime-only timeline-adjacent pack boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.packs.editorial.executors.arrange import run as arrange
from astrid.packs.editorial.executors.refine import run as refine
from astrid.packs.editorial.executors.refine.src.reviewers import audio_boundary
from astrid.packs.video_editing.executors.cut import resume
from astrid.packs.video_editing.orchestrators.hype import parser as hype_parser
from astrid.packs.video_editing.orchestrators.hype import runner as hype_runner


def test_hype_requires_materialized_files_and_has_no_theme_default(tmp_path: Path) -> None:
    brief = tmp_path / "brief.txt"
    brief.write_text("Make a video.\n", encoding="utf-8")
    with pytest.raises(AstridError, match="runtime-materialized.*not a URL"):
        hype_parser.resolve_args(
            ["--video", "https://example.invalid/video.mp4", "--brief", str(brief), "--out", str(tmp_path / "out")]
        )

    args = hype_parser.resolve_args(
        ["--brief", str(brief), "--out", str(tmp_path / "out"), "--target-duration", "75"]
    )
    assert args.theme is None

    with pytest.raises(AstridError, match="runtime-materialized theme.json"):
        hype_parser._resolve_theme_arg("banodoco-default")


def test_arrange_does_not_search_workspace_for_theme() -> None:
    with pytest.raises(AstridError, match="workspace theme fallback"):
        arrange._resolve_theme_path("not-a-file-or-directory")


@pytest.mark.parametrize("entry", [
    {"url": "https://example.invalid/audio.wav"},
    {"file": "relative/audio.wav"},
    {"cache": "asset-cache-key"},
])
def test_refine_and_audio_reviewer_reject_non_materialized_locators(tmp_path: Path, entry: dict[str, str]) -> None:
    registry = {"assets": {"main": entry}}
    with pytest.raises((AstridError, ValueError), match="(locator|materialized)"):
        refine._resolve_asset_path(tmp_path / "hype.assets.json", registry, "main")
    with pytest.raises(ValueError, match="(locator|materialized)"):
        audio_boundary._resolve_asset_path(tmp_path, registry, "main")


def test_refine_and_audio_reviewer_accept_only_existing_absolute_materialized_file(tmp_path: Path) -> None:
    source = tmp_path / "managed-object"
    source.write_bytes(b"audio")
    registry = {"assets": {"main": {"file": str(source)}}}
    assert refine._resolve_asset_path(tmp_path / "hype.assets.json", registry, "main") == source
    assert audio_boundary._resolve_asset_path(tmp_path, registry, "main") == source


@pytest.mark.parametrize("entry", [
    {"url": "https://example.invalid/video.mp4"},
    {"file": "relative/video.mp4"},
    {"cache": "asset-cache-key"},
])
def test_cut_resume_requires_materialized_registry_entries(tmp_path: Path, entry: dict[str, str]) -> None:
    with pytest.raises(AstridError, match="(locator|materialized)"):
        resume._require_materialized_registry({"assets": {"main": entry}})


def test_cut_resume_accepts_existing_absolute_materialized_registry_entry(tmp_path: Path) -> None:
    source = tmp_path / "managed-object"
    source.write_bytes(b"video")
    resume._require_materialized_registry({"assets": {"main": {"file": str(source)}}})


def test_hype_no_longer_contains_url_cache_or_project_plan_authority() -> None:
    source = Path(hype_parser.__file__).parents[0]
    runner = (source / "runner.py").read_text(encoding="utf-8")
    run = (source / "run.py").read_text(encoding="utf-8")
    assert "asset_cache" not in runner
    assert "asset_cache" not in run
    assert "project_dir(" not in runner
    assert 'args.out / "plan.json"' not in runner


def test_hype_publishes_only_attempt_local_result_manifest(tmp_path: Path) -> None:
    out = tmp_path / "attempt"
    (out / "briefs").mkdir(parents=True)
    args = argparse.Namespace(
        out=out,
        video=tmp_path / "video.mp4",
        audio=None,
        brief=tmp_path / "brief.txt",
        theme=None,
    )
    hype_runner._write_result_manifest(args)
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "video_editing.hype"
    assert {output["path"] for output in manifest["outputs"]} == {"briefs"}
    assert not (tmp_path / "plan.json").exists()
