"""Cut remains a result-only task worker after timeline-authority cutover."""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core import timeline
from astrid.packs.training.executors.pool_merge import run as pool_merge
from astrid.packs.video_editing.executors.cut import resume as cut_resume
from astrid.packs.video_editing.executors.cut import run as cut_run


def test_cut_cli_emits_only_attempt_outputs(tmp_path: Path) -> None:
    pytest.importorskip("banodoco_timeline_schema")
    inputs = _write_visual_only_inputs(tmp_path)
    out = tmp_path / "out"

    assert cut_run.main(
        [
            "--pool", str(inputs["pool"]),
            "--arrangement", str(inputs["arrangement"]),
            "--brief", str(inputs["brief"]),
            "--out", str(out),
        ]
    ) == 0

    assert (out / "hype.timeline.json").is_file()
    assert (out / "hype.assets.json").is_file()
    assert not list(tmp_path.rglob("assembly.json"))
    assert not list(tmp_path.rglob("events.jsonl"))


def test_cut_resume_copies_materialized_artifacts_without_workspace_lookup(
    tmp_path: Path,
) -> None:
    pytest.importorskip("banodoco_timeline_schema")
    source = tmp_path / "source"
    source.mkdir()
    (source / "hype.timeline.json").write_text(
        Path("examples/hype.timeline.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (source / "hype.assets.json").write_text(
        Path("examples/hype.assets.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    args = cut_run.build_parser().parse_args(
        ["--timeline", str(source / "hype.timeline.json"), "--out", str(out)]
    )

    result = cut_resume.execute_resume_mode(args)

    assert result.timeline_path == out / "hype.timeline.json"
    assert result.assets_path == out / "hype.assets.json"
    assert not list(tmp_path.rglob("assembly.json"))
    assert not list(tmp_path.rglob("events.jsonl"))


def test_cut_sources_have_no_workspace_mutation_gateway() -> None:
    for module_path in (
        Path("astrid/packs/video_editing/executors/cut/run.py"),
        Path("astrid/packs/video_editing/executors/cut/resume.py"),
        Path("astrid/packs/video_editing/executors/cut/timeline_build.py"),
    ):
        source = module_path.read_text(encoding="utf-8")
        assert "pack_write_gateway" not in source
        assert "append_event" not in source
        assert "regenerate_projection" not in source
        assert "managed_binding" not in source


def _write_visual_only_inputs(root: Path) -> dict[str, Path]:
    pool = pool_merge.merge_pool(
        {
            "version": timeline.POOL_VERSION,
            "generated_at": "2026-04-21T12:00:00Z",
            "entries": [],
        }
    )
    arrangement = {
        "version": timeline.ARRANGEMENT_VERSION,
        "generated_at": "2026-04-21T12:00:00Z",
        "brief_text": "Make a quote card.",
        "target_duration_sec": 4.0,
        "clips": [
            {
                "uuid": "a3f4b21c",
                "order": 1,
                "audio_source": None,
                "visual_source": {
                    "pool_id": "pool_g_text_card",
                    "role": "primary",
                    "params": {"content": "Hello"},
                },
                "text_overlay": None,
                "rationale": "Use a generated quote card.",
            }
        ],
    }
    pool_path = root / "pool.json"
    arrangement_path = root / "arrangement.json"
    brief_path = root / "brief.txt"
    timeline.save_pool(pool, pool_path)
    timeline.save_arrangement(
        arrangement,
        arrangement_path,
        {entry["id"] for entry in pool["entries"]},
    )
    brief_path.write_text("Make a quote card.\n", encoding="utf-8")
    return {
        "pool": pool_path,
        "arrangement": arrangement_path,
        "brief": brief_path,
    }
