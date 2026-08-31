"""Cross-process-shaped proof that iteration-video reads runtime runs."""

from __future__ import annotations

import json
import os
from contextlib import nullcontext
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace

import pytest

RUNTIME = Path(
    os.environ.get("BANODOCO_RUNTIME_CHECKOUT")
    or "/Users/peteromalley/Documents/reigh-workspace/banodoco-workspace-runtime-stage1-convergence"
)
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(RUNTIME / "packages" / "python"))
pytest.importorskip("runtime_protocol.daemon")

from runtime_protocol.daemon import RuntimeDaemon  # noqa: E402
from banodoco_workspace_client import WorkspaceClient as GeneratedRuntimeClient  # noqa: E402

from astrid.packs.video_editing.orchestrators.iteration_video import run as iteration_video  # noqa: E402
from astrid.sdk.client import AstridClient  # noqa: E402
import astrid.sdk.workspace_client as workspace_client  # noqa: E402

workspace_client.GeneratedWorkspaceClient = GeneratedRuntimeClient


def _open_client(daemon: RuntimeDaemon) -> AstridClient:
    return AstridClient.open(
        endpoint=daemon.endpoint,
        credential=daemon.credential_path,
        realm_id=daemon.service.realm["id"],
        actor_id="owner",
        client_name="astrid-stage1-iteration-video",
        client_version="stage1",
        protocol_version="workspace.v1",
    )


def test_runtime_execution_imports_do_not_reach_retired_project_run() -> None:
    root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import astrid.core.execution.executor.runner; "
                "import astrid.core.execution.orchestrator.runner; "
                "print('astrid.core.project.run' in sys.modules); "
                "print('astrid.core.contracts.run_record' in sys.modules)"
            ),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.splitlines() == ["False", "False"]


def test_public_iteration_video_uses_explicit_runtime_project_and_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    support = tmp_path / "support"
    daemon = RuntimeDaemon(tmp_path / "realm", support_root=support).start()
    monkeypatch.setenv("BANODOCO_RUNTIME_ENDPOINT", daemon.endpoint)
    monkeypatch.setenv("BANODOCO_RUNTIME_CREDENTIAL", str(support / "credentials" / "owner.token"))
    try:
        with _open_client(daemon) as client:
            created = client.projects.create(slug="demo", name="Demo", idempotency_key="project")
            assert created.ok
            admitted = client.tasks.create(
                project_id="demo",
                capability="render.basic",
                spec={},
                idempotency_key="iteration-run",
            )
            assert admitted.ok
            runtime_run_id = admitted.data["run_id"]
            observed_quality: dict[str, object] = {}

            def fake_assemble(**kwargs):
                out = kwargs["out_path"]
                observed_quality.update(kwargs["input_quality"])
                out.mkdir(parents=True, exist_ok=True)
                for name, payload in (
                    ("iteration.manifest.json", {"runs": [], "quality": kwargs["input_quality"]}),
                    ("iteration.quality.json", kwargs["input_quality"]),
                    ("hype.timeline.json", {}),
                    ("hype.assets.json", {}),
                ):
                    (out / name).write_text(json.dumps(payload), encoding="utf-8")
                return {"manifest_path": str(out / "iteration.manifest.json")}

            def fake_render(_timeline, _assets, output, **_kwargs):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"runtime-backed-video")
                Path(f"{output}.provenance.json").write_text("{}", encoding="utf-8")
                return output

            monkeypatch.setattr(iteration_video.assemble, "assemble_iteration", fake_assemble)
            monkeypatch.setattr(iteration_video, "invoke_attached_render", fake_render)
            monkeypatch.setattr(iteration_video, "_runtime_client_context", lambda _client=None: nullcontext(client))
            result = iteration_video.run_orchestrator(
                SimpleNamespace(
                    out=tmp_path / "out",
                    orchestrator_args=("--repo-root", str(tmp_path)),
                    inputs={"target_run_id": runtime_run_id},
                    # Public iteration-video requires an explicit runtime
                    # project and runtime-issued target run.
                    project="demo",
                    run_root=None,
                    dry_run=False,
                ),
                SimpleNamespace(id="video_editing.iteration_video", kind="orchestrator"),
            )

            assert result["returncode"] == 0, result
        assert result["outputs"]["iteration.mp4"]
        assert result["planned_commands"][0][0] == "runtime.runs.list/show"
        assert result["planned_commands"][0][2] == runtime_run_id
        assert result["planned_commands"][0][1] == "demo"
        assert result["outputs"]["iteration.mp4"]
        assert float(observed_quality["data_quality"]) < 1.0
        assert "missing_evidence" in observed_quality
        assert (tmp_path / "out" / "iteration.mp4").read_bytes() == b"runtime-backed-video"
        assert not list(tmp_path.glob("**/run.json"))
    finally:
        daemon.stop()
