"""Final authority-boundary proofs for the rendering cutover."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from astrid.core.execution.generic_host import GenericPackHost
import astrid.sdk.rendering as sdk_rendering


ROOT = Path(__file__).resolve().parents[2]


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, bytes | str], ...]:
    """Capture fixture-root entries so route side effects are measurable."""
    records: list[tuple[str, str, bytes | str]] = []
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        if path.is_symlink():
            records.append(("symlink", relative, str(path.readlink())))
        elif path.is_dir():
            records.append(("dir", relative, b""))
        elif path.is_file():
            records.append(("file", relative, path.read_bytes()))
    return tuple(records)


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


def test_public_sdk_has_no_direct_render_compatibility_surface() -> None:
    source = (ROOT / "astrid/sdk/rendering.py").read_text()
    assert not hasattr(sdk_rendering, "render")
    assert "def render(\n    timeline_path" not in source
    assert "sdk.invoke(" in source and "rendering.render" in source


def test_managed_adapters_have_no_project_root_or_implicit_client_fallback() -> None:
    render_source = (
        ROOT / "astrid/packs/rendering/executors/render/task_adapter.py"
    ).read_text(encoding="utf-8")
    generation_source = (
        ROOT / "astrid/packs/generation/executors/generate_image/task_adapter.py"
    ).read_text(encoding="utf-8")
    invocation_source = (ROOT / "astrid/sdk/invocation.py").read_text(encoding="utf-8")
    events_source = (ROOT / "astrid/sdk/events.py").read_text(encoding="utf-8")
    assert "ASTRID_PROJECTS_ROOT" not in render_source
    assert "ASTRID_PROJECTS_ROOT" not in generation_source
    assert "AstridClient.open()" not in invocation_source
    assert "AstridClient.open()" not in events_source


def test_generic_host_materializes_managed_snapshot_inside_attempt(tmp_path: Path) -> None:
    """A managed snapshot reaches a real child command via attempt-local files."""

    pack_root = tmp_path / "pack"
    executor_root = pack_root / "executors" / "probe"
    executor_root.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "id": "probe.snapshot",
        "name": "Snapshot probe",
        "kind": "external",
        "version": "1.0",
        "command": {
            "argv": [
                "{python_exec}",
                "-c",
                (
                    "from pathlib import Path; p=Path('{out}').parent/'inputs'/'timeline.json'; "
                    "assert p.is_relative_to(Path('{out}').parent); "
                    "Path('{out}/seen.json').write_text(p.read_text())"
                ),
            ]
        },
        "outputs": [
            {
                "name": "seen",
                "type": "file",
                "path_template": "{out}/seen.json",
                "artifact_type": "application/json",
            }
        ],
    }
    (executor_root / "executor.yaml").write_text(json.dumps(manifest), encoding="utf-8")

    host = GenericPackHost(pack_roots=[pack_root])
    record = host.discover()[0]
    attempt = tmp_path / "attempt"
    inputs = host._materialize_inputs(
        {
            "spec": {"inputs": {
                "timeline_snapshot": {
                    "config": {"tracks": [], "clips": []},
                    "registry": {"assets": {}},
                }
            }}
        },
        attempt,
    )
    assert Path(inputs["timeline"]).is_relative_to(attempt.resolve())
    assert Path(inputs["assets_registry"]).is_relative_to(attempt.resolve())
    output_root = attempt / "outputs"
    output_root.mkdir(parents=True)
    result = host._run_command_definition(record, inputs, output_root, attempt)
    assert result.outputs == {"seen": str(attempt / "outputs" / "seen.json")}
    assert json.loads((attempt / "outputs" / "seen.json").read_text()) == {
        "tracks": [],
        "clips": [],
    }


def test_renderer_authoring_cli_has_no_unadmitted_smoke_render_route() -> None:
    source = (ROOT / "astrid/core/rendering/cli.py").read_text()
    assert "RenderService" not in source
    assert "_cmd_smoke" not in source
    assert 'sub.add_parser("smoke"' not in source


def test_attached_render_module_and_nested_runner_are_deleted() -> None:
    assert not (ROOT / "astrid/core/rendering/attached.py").exists()
    for path in (
        ROOT / "astrid/packs/editorial/executors/human_notes/run.py",
        ROOT / "astrid/packs/video_editing/executors/cut/run.py",
        ROOT / "astrid/packs/video_editing/executors/cut/resume.py",
        ROOT / "astrid/packs/video_editing/orchestrators/hype/steps.py",
        ROOT / "astrid/packs/video_editing/orchestrators/iteration_video/run.py",
    ):
        source = path.read_text()
        assert "invoke_attached_render" not in source
        assert "run_executor" not in source


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
