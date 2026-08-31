"""Adversarial guards for pack consumers of runtime-materialized media."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from astrid.core.contracts.errors import AstridError
from astrid.packs.video_editing.executors.cut import attempt_assets


@pytest.mark.parametrize(
    "value",
    [
        "relative/clip.mp4",
        "file:///tmp/clip.mp4",
        "data:video/mp4;base64,AAAA",
        "https://example.invalid/clip.mp4",
    ],
)
def test_cut_rejects_non_materialized_asset_cli_values(value: str) -> None:
    args = argparse.Namespace(asset=[f"main={value}"], video=None, audio=None)
    with pytest.raises(AstridError, match="absolute runtime-materialized file"):
        attempt_assets.resolve_materialized_asset_paths(args)


def test_cut_rejects_missing_absolute_asset_cli_value(tmp_path: Path) -> None:
    args = argparse.Namespace(
        asset=[], video=str(tmp_path / "missing.mp4"), audio=None
    )
    with pytest.raises(AstridError, match="runtime materialization is unavailable"):
        attempt_assets.resolve_materialized_asset_paths(args)


def test_cut_revalidates_direct_registry_paths(tmp_path: Path) -> None:
    with pytest.raises(AstridError, match="absolute runtime-materialized file"):
        attempt_assets.build_attempt_registry(
            {"main": Path("relative/clip.mp4")}, {"assets": {}}, None
        )

