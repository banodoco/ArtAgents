from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("banodoco_timeline_schema")

from astrid.core import timeline
from astrid.packs.training.executors.pool_merge import run as pool_merge
from astrid.packs.video_editing.executors.cut import resume as cut_resume
from astrid.packs.video_editing.executors.cut import run as cut_run


def test_cut_render_uses_attached_facade_and_forwards_canonical_selector(
    tmp_path: Path, monkeypatch
) -> None:
    inputs = _write_visual_only_cut_inputs(tmp_path)
    out_dir = tmp_path / "cut-out"
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_render(*args, **kwargs):
        calls.append((args, kwargs))
        output = Path(args[2])
        output.write_bytes(b"cut-render")
        Path(f"{output}.provenance.json").write_text("{}\n", encoding="utf-8")
        return output

    monkeypatch.setattr(cut_run, "invoke_attached_render", fake_render)

    assert cut_run.main(
        [
            "--pool",
            str(inputs["pool"]),
            "--arrangement",
            str(inputs["arrangement"]),
            "--brief",
            str(inputs["brief"]),
            "--out",
            str(out_dir),
            "--renderer",
            "rendering.remotion",
            "--render",
        ]
    ) == 0

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert Path(args[0]).name == "hype.timeline.json"
    assert Path(args[1]).name == "hype.assets.json"
    assert Path(args[2]) == out_dir / "hype.mp4"
    assert kwargs["selector"] == "rendering.remotion"
    assert "rendering.remotion" in kwargs["backend_config"]
    assert "step_id" not in kwargs
    assert (out_dir / "hype.mp4").read_bytes() == b"cut-render"
    assert (out_dir / "hype.mp4.provenance.json").is_file()
    manifest_outputs = {
        item["path"] for item in _read_json(out_dir / "manifest.json")["outputs"]
    }
    assert {"hype.mp4", "hype.mp4.provenance.json"} <= manifest_outputs
    assert not list(tmp_path.rglob("run.json"))


def test_cut_resume_uses_attached_facade_and_task_step_without_extra_ledger(
    tmp_path: Path, monkeypatch
) -> None:
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
    out_dir = tmp_path / "resume-out"
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_render(*args, **kwargs):
        calls.append((args, kwargs))
        output = Path(args[2])
        output.write_bytes(b"resume-render")
        Path(f"{output}.provenance.json").write_text("{}\n", encoding="utf-8")
        return output

    monkeypatch.setenv("ASTRID_TASK_PROJECT", "demo")
    monkeypatch.setenv("ASTRID_TASK_RUN_ID", "parent-run")
    monkeypatch.setenv("ASTRID_TASK_STEP_ID", "cut")
    monkeypatch.setattr(cut_resume, "invoke_attached_render", fake_render)

    args = cut_run.build_parser().parse_args(
        [
            "--timeline",
            str(source / "hype.timeline.json"),
            "--out",
            str(out_dir),
            "--renderer",
            "rendering.remotion",
            "--render",
        ]
    )
    result = cut_resume.execute_resume_mode(args)

    assert result.rendered_path == out_dir / "hype.mp4"
    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs["selector"] == "rendering.remotion"
    assert kwargs["step_id"] == "cut-resume-render"
    assert (out_dir / "hype.mp4.provenance.json").is_file()
    assert _read_json(out_dir / "hype.metadata.json")["pipeline"]["config_snapshot"][
        "renderer"
    ] == "rendering.remotion"
    manifest_outputs = {
        item["path"] for item in _read_json(out_dir / "manifest.json")["outputs"]
    }
    assert {"hype.mp4", "hype.mp4.provenance.json"} <= manifest_outputs
    assert not list(tmp_path.rglob("run.json"))


def test_cut_sources_do_not_import_concrete_renderer() -> None:
    for module_path in (
        Path("astrid/packs/video_editing/executors/cut/run.py"),
        Path("astrid/packs/video_editing/executors/cut/resume.py"),
    ):
        source = module_path.read_text(encoding="utf-8")
        assert "from ..render.run" not in source
        assert "astrid.packs.rendering.executors.render" not in source
        assert "astrid.packs.rendering.backends" not in source
        assert "invoke_attached_render" in source


def _write_visual_only_cut_inputs(root: Path) -> dict[str, Path]:
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
    return {"pool": pool_path, "arrangement": arrangement_path, "brief": brief_path}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
