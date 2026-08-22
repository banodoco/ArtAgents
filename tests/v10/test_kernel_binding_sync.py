"""Kernel timeline binding seam: core<->pack stream-type sync + no pack imports."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.timeline import kernel_binding


def test_kernel_binding_stream_type_matches_pack() -> None:
    from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE

    assert kernel_binding.TIMELINE_STREAM_TYPE == TIMELINE_STREAM_TYPE


def test_kernel_binding_never_imports_packs() -> None:
    source = Path(kernel_binding.__file__).read_text(encoding="utf-8")
    # import lines only: docstring mentions are fine.
    imports = [
        line for line in source.splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("astrid.packs" in line for line in imports), imports
