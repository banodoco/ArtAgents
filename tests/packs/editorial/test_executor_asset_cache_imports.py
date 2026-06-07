from __future__ import annotations

import importlib
from pathlib import Path

import pytest


EXECUTOR_MODULES = (
    "astrid.packs.editorial.executors.transcribe.run",
    "astrid.packs.editorial.executors.scenes.run",
    "astrid.packs.editorial.executors.shots.run",
    "astrid.packs.understanding.executors.scene_describe.run",
)


@pytest.mark.parametrize("module_name", EXECUTOR_MODULES)
def test_executor_modules_import_and_use_absolute_asset_cache(module_name: str) -> None:
    module = importlib.import_module(module_name)

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "from ..asset_cache" not in source
    assert "from .asset_cache" not in source
    assert (
        "from astrid.packs.training.executors.asset_cache import run as asset_cache"
        in source
    )
