"""Scratchpad of render presets.

Each module here is ONE render and exposes ``build(settings: dict) -> str``
returning a self-contained Blender Python script. The script may use the
placeholders ``__MESH_FILE__`` and ``__OUTPUT__`` (filled by the render runner
with the resolved mesh path and output directory). Adding a render = dropping a
new module in this package. See ``README.md``.

This package is intentionally OUTSIDE the core engine (``render_core.py``):
core = reusable machinery; ``renders/`` = specific, creative, disposable scenes.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Any, Callable

# name -> build(settings: dict) -> str
PRESETS: dict[str, Callable[[dict[str, Any] | None], str]] = {}


def _load() -> None:
    for mod_info in pkgutil.iter_modules(__path__):
        if mod_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{mod_info.name}")
        build = getattr(module, "build", None)
        if callable(build):
            PRESETS[mod_info.name] = build


_load()


def get_builder(name: str) -> Callable[[dict[str, Any] | None], str]:
    if name not in PRESETS:
        raise KeyError(
            f"unknown render preset {name!r}; available: {sorted(PRESETS)}"
        )
    return PRESETS[name]


def list_presets() -> list[str]:
    return sorted(PRESETS)
