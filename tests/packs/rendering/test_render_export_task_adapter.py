"""Real render-export task execution through the kernel completion seam."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.integrations.reigh.remotion_runtime import (
    TIMELINE_SCHEMA_PYTHONPATH_ENV,
    remotion_runtime_status,
)
from astrid.core.integrations.reigh.task_bridge import ReighTaskBridge
from astrid.core.io.media_import import managed_media_path, sha256_file_bytes
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.task_executor import ExecutionService
from astrid.packs.rendering.backends.remotion import run as remotion_run
from astrid.packs.rendering.executors.render.task_adapter import (
    RenderExportExecutionContext,
    RenderExportRefused,
    RenderExportTaskAdapter,
    execute_render_export_task,
)

FIXTURE_VIDEO = Path(__file__).resolve().parents[2] / "fixtures" / "reshape" / "hype_regression" / "broll.mp4"
TS = "2026-08-25T00:00:00.000000+00:00"


def _timeline_config() -> dict:
    return {
        "theme": "banodoco-default",
        "theme_overrides": {
            "visual": {"canvas": {"width": 1920, "height": 1080, "fps": 30}}
        },
        "tracks": [{"id": "v", "kind": "visual", "label": "Video"}],
        "clips": [
            {
                "id": "source-clip",
                "at": 0,
                "track": "v",
                "clipType": "media",
                "asset": "source",
                "from": 0,
                "to": 2,
                "speed": 1,
                "volume": 0,
            }
        ],
    }


def _task(*, root: Path, project_slug: str = "render-project") -> SimpleNamespace:
    digest = sha256_file_bytes(FIXTURE_VIDEO)
    managed = managed_media_path(root, digest)
    managed.parent.mkdir(parents=True, exist_ok=True)
    if not managed.exists():
        managed.write_bytes(FIXTURE_VIDEO.read_bytes())
    return SimpleNamespace(
        id="render-task-1",
        created_at=TS,
        spec={
            "family": "render_export",
            "project_slug": project_slug,
            "params": {
                "timeline_ref": "timeline-1",
                "expected_version": 1,
                "output_filename": "requested-render.mp4",
            },
            "timeline_snapshot": {
                "timeline_id": "timeline-id",
                "timeline_ulid": "timeline-1",
                "config": _timeline_config(),
                "registry": {
                    "assets": {
                        "source": {
                            "media_id": "media-source",
                            "content_sha256": f"sha256:{digest}",
                            "file": "clips/source.mp4",
                            "type": "video/mp4",
                        }
                    }
                },
                "config_version": 1,
            },
        },
    )


def test_render_export_adapter_writes_real_mp4_and_is_callable(tmp_path: Path) -> None:
    (tmp_path / "render-project").mkdir()
    task = _task(root=tmp_path)
    manifest = execute_render_export_task(
        task=task,
        staging_dir=tmp_path / "staging",
        projects_root=tmp_path,
    )
    output = tmp_path / "staging" / manifest["outputs"][0]["path"]
    assert manifest["outputs"][0]["path"] == "requested-render.mp4"
    staged_registry = json.loads(
        (tmp_path / "staging" / "render-inputs" / "assets.json").read_text()
    )
    staged_asset = staged_registry["assets"]["source"]
    assert "media_id" not in staged_asset
    assert Path(staged_asset["file"]).is_relative_to(
        (tmp_path / "staging" / "render-inputs" / "assets").resolve()
    )
    raw = output.read_bytes()
    assert raw[4:8] == b"ftyp"
    assert manifest["outputs"][0]["role"] == "result"
    assert manifest["outputs"][0]["content_hash"] == f"sha256:{hashlib.sha256(raw).hexdigest()}"


def test_forced_caption_uses_server_owned_installed_remotion_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean deployment runtime, not the source ``remotion/`` checkout, renders text."""

    (tmp_path / "render-project").mkdir()
    runtime = tmp_path / "installed-remotion"
    (runtime / "node_modules" / "@banodoco").mkdir(parents=True)
    for package in ("timeline-composition", "timeline-schema", "timeline-theme-2rp"):
        package_dir = runtime / "node_modules" / "@banodoco" / package
        package_dir.mkdir()
        package_dir.joinpath("package.json").write_text(
            json.dumps({"name": f"@banodoco/{package}", "version": "0.0.0"}),
            encoding="utf-8",
        )
    generated_src = runtime / "node_modules" / "@banodoco" / "timeline-composition" / "typescript" / "src"
    generated_src.mkdir(parents=True)
    generated_runtime_src = runtime / "src"
    generated_runtime_src.mkdir()
    for kind in ("effects", "animations", "transitions"):
        (generated_src / f"{kind}.generated.ts").write_text("export {};\n", encoding="utf-8")
        for extension in (".ts", ".js", ".d.ts", ".js.map", ".d.ts.map"):
            (generated_runtime_src / f"{kind}.generated{extension}").write_text(
                "export {};\n", encoding="utf-8"
            )
    (runtime / "package.json").write_text('{"private":true}\n', encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python3").symlink_to(Path(sys.executable).resolve())
    (fake_bin / "node").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(FIXTURE_VIDEO.read_bytes())
    (fake_bin / "npx").write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, subprocess, sys\n"
        "args = sys.argv[1:]\n"
        "out = pathlib.Path(args[args.index('--output') + 1])\n"
        f"subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', {str(source_video)!r}, '-vf', 'scale=1920:1080', '-r', '30', '-video_track_timescale', '90000', str(out)], check=True)\n",
        encoding="utf-8",
    )
    for executable in (fake_bin / "node", fake_bin / "npx"):
        executable.chmod(0o755)
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(runtime))
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ['PATH']}")
    schema_spec = importlib.util.find_spec("banodoco_timeline_schema")
    if schema_spec is None or schema_spec.origin is None:
        pytest.fail("the pinned timeline-schema dependency is required for this integration test")
    schema_install = tmp_path / "installed-python"
    schema_package = schema_install / "banodoco_timeline_schema"
    shutil.copytree(Path(schema_spec.origin).parent, schema_package)
    monkeypatch.setenv(TIMELINE_SCHEMA_PYTHONPATH_ENV, str(schema_install))
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            path for path in (str(schema_install), os.environ.get("PYTHONPATH")) if path
        ),
    )
    probe_env = os.environ.copy()
    probe_env.pop("PYTHONPATH", None)
    schema_origin = subprocess.check_output(
        [
            sys.executable,
            "-c",
            "import astrid.core.timeline.banodoco_schema; "
            "import banodoco_timeline_schema; "
            "print(banodoco_timeline_schema.__file__)",
        ],
        text=True,
        env=probe_env,
    ).strip()
    assert Path(schema_origin).resolve().is_relative_to(schema_package.resolve())
    import banodoco_timeline_schema as ambient_schema

    ambient_origin = Path(ambient_schema.__file__).resolve()
    assert not ambient_origin.is_relative_to(schema_package.resolve())
    assert remotion_runtime_status().available
    # This simulates the installed wheel, where authoring-only
    # scripts/gen_effect_registry.py is deliberately not packaged.  The
    # release-installed Remotion bundle must provide generated registries.
    monkeypatch.setattr(remotion_run, "gen_effect_registry", None)

    task = _task(root=tmp_path)
    snapshot = dict(task.spec["timeline_snapshot"])
    config = dict(snapshot["config"])
    config["clips"] = [
        {
            "id": "caption",
            "at": 0,
            "track": "v",
            "clipType": "text-card",
            "hold": 1,
            "params": {"content": "Installed runtime"},
        }
    ]
    snapshot["config"] = config
    task.spec = {**task.spec, "timeline_snapshot": snapshot}

    manifest = execute_render_export_task(
        task=task,
        staging_dir=tmp_path / "staging",
        projects_root=tmp_path,
    )
    output = tmp_path / "staging" / manifest["outputs"][0]["path"]
    assert output.read_bytes()[4:8] == b"ftyp"
    assert manifest["inputs"]["engine"] == "remotion"


def test_forced_caption_fails_before_renderer_without_server_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "render-project").mkdir()
    monkeypatch.delenv("ASTRID_REMOTION_PROJECT_DIR", raising=False)
    task = _task(root=tmp_path)
    snapshot = dict(task.spec["timeline_snapshot"])
    config = dict(snapshot["config"])
    config["clips"] = [{"id": "caption", "clipType": "text-card", "at": 0, "hold": 1}]
    snapshot["config"] = config
    task.spec = {**task.spec, "timeline_snapshot": snapshot}
    with pytest.raises(RenderExportRefused, match="server-owned Remotion runtime unavailable"):
        RenderExportTaskAdapter(projects_root=tmp_path).execute(
            task=task, staging_dir=tmp_path / "staging"
        )


@pytest.mark.parametrize(
    "missing_file",
    ("__init__.py", "generated.py", "materialize.py", "theme.py", "timeline.schema.json", "validate.py"),
)
def test_trusted_schema_readiness_requires_complete_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing_file: str,
) -> None:
    import banodoco_timeline_schema

    schema_install = tmp_path / "installed-python"
    schema_package = schema_install / "banodoco_timeline_schema"
    schema_package.mkdir(parents=True)
    source_package = Path(banodoco_timeline_schema.__file__).resolve().parent
    for source in source_package.iterdir():
        if source.name != missing_file and source.is_file():
            shutil.copy2(source, schema_package / source.name)
    runtime = tmp_path / "installed-remotion"
    (runtime / "node_modules" / "@banodoco").mkdir(parents=True)
    for package in ("timeline-composition", "timeline-schema", "timeline-theme-2rp"):
        package_dir = runtime / "node_modules" / "@banodoco" / package
        package_dir.mkdir()
        package_dir.joinpath("package.json").write_text("{}", encoding="utf-8")
    (runtime / "package.json").write_text("{}", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for executable in ("node", "npx"):
        path = fake_bin / executable
        path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(runtime))
    monkeypatch.setenv(TIMELINE_SCHEMA_PYTHONPATH_ENV, str(schema_install))
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ['PATH']}")
    status = remotion_runtime_status()
    assert not status.available
    assert missing_file in (status.reason or "")


def test_render_export_adapter_fails_closed_without_snapshot_or_project(tmp_path: Path) -> None:
    task = _task(root=tmp_path)
    task.spec = dict(task.spec)
    task.spec.pop("timeline_snapshot")
    with pytest.raises(RenderExportRefused, match="timeline snapshot"):
        RenderExportTaskAdapter(projects_root=tmp_path).execute(
            task=task, staging_dir=tmp_path / "staging"
        )


def test_render_export_adapter_has_cooperative_cancel_and_progress_seam(
    tmp_path: Path,
) -> None:
    (tmp_path / "render-project").mkdir()
    task = _task(root=tmp_path)
    seen: list[dict] = []
    context = RenderExportExecutionContext.bounded(
        cancelled=lambda: True,
        progress=seen.append,
    )
    with pytest.raises(RenderExportRefused, match="cancelled"):
        RenderExportTaskAdapter(projects_root=tmp_path).execute(
            task=task,
            staging_dir=tmp_path / "staging",
            context=context,
        )
    assert seen == []
    task = _task(root=tmp_path, project_slug="missing")
    with pytest.raises(RenderExportRefused, match="project is missing"):
        RenderExportTaskAdapter(projects_root=tmp_path).execute(
            task=task, staging_dir=tmp_path / "staging"
        )


@pytest.mark.parametrize(
    "change, expected",
    [
        ("missing_asset", "managed media .* missing"),
        ("missing_renderer", "server-owned"),
    ],
)
def test_render_export_adapter_fails_closed_on_missing_asset_or_renderer(
    tmp_path: Path, change: str, expected: str
) -> None:
    (tmp_path / "render-project").mkdir()
    task = _task(root=tmp_path)
    task.spec = dict(task.spec)
    snapshot = dict(task.spec["timeline_snapshot"])
    snapshot["registry"] = {
        "assets": {
            "source": {
                "media_id": "missing-media",
                "content_sha256": "sha256:" + "0" * 64,
                "file": "clips/source.mp4",
                "type": "video/mp4",
            }
        }
    }
    task.spec["timeline_snapshot"] = snapshot
    if change == "missing_renderer":
        task.spec["params"] = {**task.spec["params"], "engine": "rendering.not-installed"}
    with pytest.raises(RenderExportRefused, match=expected):
        RenderExportTaskAdapter(projects_root=tmp_path).execute(
            task=task, staging_dir=tmp_path / "staging"
        )

def test_render_export_round_trip_materializes_mp4_media_id(tmp_path: Path) -> None:
    db_path = tmp_path / ".astrid" / "astrid.sqlite3"
    db_path.parent.mkdir()
    core_registry = core_only_registry()
    writer = DatabaseWriter(db_path, core_registry)
    try:
        events = EventAppendService(core_registry)
        receipts = ReceiptService()
        projects = ProjectRepository(events=events, receipts=receipts)
        tasks = TaskRepository(events=events, receipts=receipts)
        media = MediaRepository(events=events, receipts=receipts, projects_root=tmp_path)
        project_id = generate_lowercase_ulid()
        UnitOfWork(writer).run(
            lambda u: projects.create(
                u,
                project_id=project_id,
                slug="render-project",
                name="Render Project",
                settings={},
                idempotency_key="project-render-k",
                created_at=TS,
            )
        )
        (tmp_path / "render-project").mkdir(exist_ok=True)
        task = _task(root=tmp_path)
        admitted = UnitOfWork(writer).run(
            lambda u: tasks.create(
                u,
                project_id=project_id,
                task_id=task.id,
                capability="rendering.render",
                spec=task.spec,
                input_manifest=[],
                idempotency_key="render-admit-k",
                max_attempts=1,
                created_at=TS,
            )
        )
        claim = UnitOfWork(writer).run(
            lambda u: tasks.claim(
                u,
                project_id=project_id,
                idempotency_key="render-claim-k",
                executor_id="render-worker",
                now=TS,
            )
        )
        assert claim is not None
        service = ExecutionService(projects_root=tmp_path, task_repo=tasks)
        prepared = service.execute(
            UnitOfWork(writer),
            project_id=project_id,
            task_id=admitted.id,
            attempt_id=claim.attempt.id,
            lease_id=claim.attempt.lease_id,
            expected_status_version=claim.attempt.status_version,
            idempotency_key="render-exec-k",
            handler=RenderExportTaskAdapter(projects_root=tmp_path),
            now=TS,
        )
        assert prepared.outcome == "prepared"
        assert prepared.prepared is not None
        completed = service.complete(
            UnitOfWork(writer),
            prepared=prepared.prepared,
            media_repo=media,
            idempotency_key="render-complete-k",
            now=TS,
        )
        assert completed.outcome == "completed"
        output = completed.completed.outputs[0]
        assert output.role == "result"
        assert output.media_id
        managed = media.show(writer, output.media_id)
        assert managed.content_hash == output.params["content_hash"]
        assert managed.mime_type == "video/mp4"
        assert Path(managed.locations[0].locator).is_file()
        detail = ReighTaskBridge(
            writer=writer, registry=core_registry, projects_root=tmp_path
        ).task_detail(slug="render-project", task_id=admitted.id)
        assert detail["task"]["outputs"][0]["media_id"] == output.media_id
    finally:
        writer.close()
