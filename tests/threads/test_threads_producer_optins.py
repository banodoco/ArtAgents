"""Retired thread-sidecar producer contract checks.

Generation and video-editing producers now publish runtime-owned outputs; they
must not opt back into the deleted thread variant sidecar writer.
"""

from __future__ import annotations

from pathlib import Path


def test_live_producers_do_not_opt_into_retired_variant_sidecars() -> None:
    repo = Path(__file__).resolve().parents[2]
    producer_paths = (
        repo / "astrid/packs/generation/executors/generate_image_openai/run.py",
        repo / "astrid/packs/video_editing/orchestrators/logo_ideas/run.py",
        repo / "astrid/packs/video_editing/orchestrators/event_talks/run.py",
        repo / "astrid/packs/video_editing/orchestrators/thumbnail_maker/run.py",
    )
    for producer in producer_paths:
        source = producer.read_text(encoding="utf-8")
        assert "write_variant_sidecar" not in source
        assert "variant_meta" not in source
