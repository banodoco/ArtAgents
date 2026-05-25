import re
from pathlib import Path


# Sprint 1 / T15 rewrite: the SKILL.md status-first paragraph replaced the
# old active-thread inspection mandate. As of #13/#14 the universal port-of-call
# is `astrid next` — it always prints one legal action regardless of bound /
# unbound state, including unbound discovery hints. ``status`` is the
# read-side breadcrumb (detail when needed). What we assert is the durable
# contract: agents who don't know what to do can always run `astrid next`.
SKILL_PARAGRAPH = (
    "When in doubt, run `astrid next`"
)


def test_threads_doc_covers_required_t11_sections_without_lock_repair_command() -> None:
    text = Path("docs/threads.md").read_text(encoding="utf-8")
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
    assert "python3 -m astrid.packs.builtin.orchestrators.iteration_video.run inspect <lineage-id-or-active>" in text
    assert "hype.timeline.json" in text and "hype.assets.json" in text and "iteration.mp4" in text
    assert "thread environment inheritance" in text
    assert "thread gc" not in text


def test_skill_includes_thread_session_guidance() -> None:
    text = Path("SKILL.md").read_text(encoding="utf-8")
    assert SKILL_PARAGRAPH in text
    assert "python3 -m astrid.packs.builtin.orchestrators.iteration_video.run inspect <thread>" in text


def test_stop_line_active_thread_runtime_and_guidance_are_retired() -> None:
    generic_runtime_paths = [
        Path("astrid/core/executor/cli.py"),
        Path("astrid/core/orchestrator/cli.py"),
    ]
    for path in generic_runtime_paths:
        text = path.read_text(encoding="utf-8")
        assert "--thread" not in text
        assert "active_thread:" not in text
        assert "python3 -m astrid thread" not in text

    skill_text = Path("SKILL.md").read_text(encoding="utf-8")
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


def test_historical_thread_plans_do_not_publish_retired_binding_guidance() -> None:
    forbidden = (
        "[thread]",
        "thread keep",
        "thread show @active",
        "active-thread",
        "active thread",
        "active_thread",
        "ASTRID_THREAD_ID",
        "ASTRID_RUN_ID",
        "--thread",
        "@active",
    )
    for path in (
        Path("docs/design-thread-layer.md"),
        Path("docs/sprint-thread-layer.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "Retired context:" in text
        assert "not current" in text or "not as current" in text
        for phrase in forbidden:
            assert phrase not in text
