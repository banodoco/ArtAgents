"""Sprint 8: Remotion subprocess wrapper tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from worker_remotion import RemotionRenderError, render_timeline_to_mp4


def _write_mp4_stub(args, **kwargs):  # noqa: ANN001 - subprocess.run shim
    # Find --output and create a small file there to mimic Remotion's job.
    cmd = args
    output_idx = cmd.index("--output") + 1
    out_path = Path(cmd[output_idx])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"fake-mp4-bytes")
    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")


def test_render_passes_props_to_remotion(tmp_path: Path):
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")
        # Read the props json before pipeline cleans it up.
        props_idx = args.index("--props") + 1
        captured["props_text"] = Path(args[props_idx]).read_text()
        return _write_mp4_stub(args, **kwargs)

    timeline = {"clips": [{"id": "c-1"}], "tracks": [], "theme": "2rp"}
    assets = {"assets": {"a": {"file": "https://cdn.example.com/a.mp4"}}}

    result = render_timeline_to_mp4(
        timeline=timeline,
        assets=assets,
        theme_id="2rp",
        output_path=tmp_path / "out.mp4",
        project_dir=tmp_path / "project",
        runner=runner,
    )
    assert result.output_path.exists()
    assert result.sha256, "sha256 must be populated for SD-034 audit"

    args = captured["args"]
    assert args[0] == "npx"
    assert args[1] == "remotion"
    assert args[2] == "render"
    assert args[3] == "TimelineComposition"
    assert "--props" in args
    assert "--output" in args

    import json
    props = json.loads(captured["props_text"])
    assert props["timeline"]["clips"][0]["id"] == "c-1"
    assert props["assets"]["assets"]["a"]["file"].startswith("https://")
    assert props["theme"]["id"] == "2rp"


def test_render_propagates_subprocess_failure(tmp_path: Path):
    def runner(args, **kwargs):
        return subprocess.CompletedProcess(
            args=args, returncode=1, stdout="", stderr="boom: chrome crashed",
        )

    with pytest.raises(RemotionRenderError) as exc:
        render_timeline_to_mp4(
            timeline={},
            assets={"assets": {}},
            theme_id="2rp",
            output_path=tmp_path / "out.mp4",
            project_dir=tmp_path / "project",
            runner=runner,
        )
    assert "code 1" in str(exc.value)
    assert "chrome crashed" in str(exc.value)


def test_render_raises_when_output_missing_after_success(tmp_path: Path):
    def runner(args, **kwargs):
        # Returncode is 0 but no MP4 lands — Remotion claimed success but
        # something silently swallowed the file. Defend in depth.
        return subprocess.CompletedProcess(
            args=args, returncode=0, stdout="", stderr="",
        )

    with pytest.raises(RemotionRenderError) as exc:
        render_timeline_to_mp4(
            timeline={},
            assets={"assets": {}},
            theme_id="2rp",
            output_path=tmp_path / "missing.mp4",
            project_dir=tmp_path / "project",
            runner=runner,
        )
    assert "does not exist" in str(exc.value)
