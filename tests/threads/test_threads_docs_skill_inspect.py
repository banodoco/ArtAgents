import re
from pathlib import Path

import pytest


CORE_SKILL_PATH = Path("astrid/packs/_core/skill/SKILL.md")


def test_threads_doc_covers_required_t11_sections_without_lock_repair_command() -> None:
    doc_path = Path("docs/threads.md")
    if not doc_path.exists():
        pytest.skip("docs/threads.md was retired")
    text = doc_path.read_text(encoding="utf-8")
    for heading in (
        "## Model",
        "## Prefixes",
        "## Privacy & Redaction",
        "## Concurrent Variant Selection",
        "## Tier Firing Rules",
        "## Inspect Before Render",
        "## Stale Locks",
        "## Deferred",
    ):
        assert heading in text
    compact = re.sub(r"\s+", " ", text.lower())
    assert "selections are append-only; the most recent write is authoritative on read; prior selections are preserved as history" in compact
    assert "generic runtime prefix lines were retired in sprint 1" in compact
    assert "python3 -m astrid.packs.video_editing.orchestrators.iteration_video.run inspect <lineage-id-or-active>" in text
    assert "hype.timeline.json" in text and "hype.assets.json" in text and "iteration.mp4" in text
    assert "thread environment inheritance" in text
    assert "thread gc" not in text


def test_stop_line_active_thread_runtime_and_guidance_are_retired() -> None:
    generic_runtime_paths = [
        Path("astrid/core/executor/cli.py"),
        Path("astrid/core/orchestrator/cli.py"),
    ]
    for path in generic_runtime_paths:
        if not path.exists():
            pytest.skip(f"{path} was moved")
        text = path.read_text(encoding="utf-8")
        assert "--thread" not in text
        assert "active_thread:" not in text
        assert "python3 -m astrid thread" not in text

    skill_text = CORE_SKILL_PATH.read_text(encoding="utf-8")
    assert "active_thread:" not in skill_text
    assert "python3 -m astrid thread" not in skill_text
    assert "pack-level `--thread <id>` argument identifies a non-binding variant lineage" in skill_text
    assert "The only legal unbound commands are help/version" in skill_text
    assert "anonymous takeover is not a valid state" in skill_text
    assert "metadata survives takeover, orphan claim, and release" in skill_text

    for path in [
        Path("astrid/core/executor/runner.py"),
        Path("astrid/core/orchestrator/runner.py"),
    ]:
        text = path.read_text(encoding="utf-8")
        assert "thread_wrapper.begin_" not in text
        assert "thread_wrapper.finalize_" not in text
        assert ".subprocess_env()" not in text
        assert ".project_thread_env()" not in text


def test_retired_thread_plans_are_not_kept_as_current_docs() -> None:
    assert not Path("docs/archive/design-thread-layer.md").exists()
    assert not Path("docs/archive/sprint-thread-layer.md").exists()
