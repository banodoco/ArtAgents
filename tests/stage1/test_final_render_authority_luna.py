"""Final authority-boundary proofs for the rendering cutover."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from astrid.core.execution.generic_host import GenericPackHost
from astrid.sdk.exceptions import UnsupportedCapabilityError
import astrid.sdk.rendering as sdk_rendering


ROOT = Path(__file__).resolve().parents[2]


def test_live_render_graph_excludes_historical_filesystem_ingest() -> None:
    probe = """
import sys
import astrid.core.rendering.assets
import astrid.core.timeline.resolution
import astrid.packs.rendering.executors.render.managed_timeline
assert 'astrid.core.io.media_import' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == ""
    for relative in (
        "astrid/core/rendering/assets.py",
        "astrid/core/timeline/resolution.py",
        "astrid/packs/rendering/executors/render/managed_timeline.py",
    ):
        assert "astrid.core.io.media_import" not in (ROOT / relative).read_text()


def test_public_sdk_render_cannot_bypass_runtime_admission(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedCapabilityError, match="sdk.invoke"):
        sdk_rendering.render(
            tmp_path / "timeline.json",
            out_path=tmp_path / "output.mp4",
        )
    assert not list(tmp_path.iterdir())


def test_attached_render_source_has_no_unbound_service_fallback() -> None:
    source = (ROOT / "astrid/core/rendering/attached.py").read_text()
    assert "RenderService(" not in source
    assert "service:" not in source
    assert "runtime parent" in source


def test_stale_timeline_visualize_task_adapter_is_deleted() -> None:
    assert not (
        ROOT / "astrid/packs/rendering/executors/timeline_visualize/task_adapter.py"
    ).exists()


def test_generic_host_still_executes_a_pack_command_in_a_child_process(tmp_path: Path) -> None:
    """The supported generic-host process boundary remains executable."""

    pack_root = tmp_path / "pack"
    executor_root = pack_root / "executors" / "probe"
    executor_root.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "id": "probe.echo",
        "name": "Probe",
        "kind": "external",
        "version": "1.0",
        "command": {
            "argv": [
                "{python_exec}",
                "-c",
                "from pathlib import Path; Path('{out}/answer.txt').write_text('generic-host')",
            ]
        },
        "outputs": [
            {
                "name": "answer",
                "type": "file",
                "path_template": "{out}/answer.txt",
                "artifact_type": "text/plain",
            }
        ],
    }
    (executor_root / "executor.yaml").write_text(json.dumps(manifest), encoding="utf-8")

    host = GenericPackHost(pack_roots=[pack_root])
    record = host.discover()[0]
    attempt = tmp_path / "attempt"
    output_root = attempt / "outputs"
    output_root.mkdir(parents=True)

    result = host._run_command_definition(record, {}, output_root, attempt)

    assert result.outputs == {"answer": str(output_root / "answer.txt")}
    assert (output_root / "answer.txt").read_text() == "generic-host"
