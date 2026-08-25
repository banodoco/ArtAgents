"""Real render-export task execution through the kernel completion seam."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from astrid.core.events.registry import core_only_registry
from astrid.core.events.service import EventAppendService
from astrid.core.ids import generate_lowercase_ulid
from astrid.core.integrations.reigh import remotion_runtime
from astrid.core.integrations.reigh.remotion_runtime import (
    NODE_EXECUTABLE_ENV,
    REMOTION_CLI_RELATIVE_PATH,
    TIMELINE_SCHEMA_PYTHONPATH_ENV,
    remotion_runtime_status,
    resolve_remotion_runtime_tools,
)
from astrid.core.integrations.reigh.task_bridge import ReighTaskBridge
from astrid.core.io.media_import import managed_media_path, sha256_file_bytes
from astrid.core.project.project import create_project
from astrid.core.receipts import ReceiptService
from astrid.core.repositories import ProjectRepository
from astrid.core.repositories.media import MediaRepository
from astrid.core.repositories.tasks import TaskRepository
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter
from astrid.core.task_executor import ExecutionService
from astrid.packs.rendering.backends.remotion import run as remotion_run
from astrid.packs.rendering.executors.render import task_adapter as task_adapter_module
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
    create_project("render-project", name="Render Project", root=tmp_path)
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


def test_renderer_inputs_are_inode_isolated_and_cleaned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Renderer writes cannot mutate managed media or durable staging evidence."""

    create_project("render-project", name="Render Project", root=tmp_path)
    task = _task(root=tmp_path)
    digest = task.spec["timeline_snapshot"]["registry"]["assets"]["source"][
        "content_sha256"
    ].removeprefix("sha256:")
    managed = managed_media_path(tmp_path, digest)
    captured: dict[str, Path] = {}

    def fake_run_executor(request, _registry):
        owned_registry_path = Path(request.inputs["assets_registry"])
        owned_registry = json.loads(owned_registry_path.read_text(encoding="utf-8"))
        owned_asset = Path(owned_registry["assets"]["source"]["file"])
        staged_registry = json.loads(
            (tmp_path / "staging" / "render-inputs" / "assets.json").read_text(
                encoding="utf-8"
            )
        )
        staged_asset = Path(staged_registry["assets"]["source"]["file"])
        input_inodes = {
            managed.stat().st_ino,
            staged_asset.stat().st_ino,
            owned_asset.stat().st_ino,
        }
        assert len(input_inodes) == 3

        captured["owned_root"] = owned_registry_path.parent
        captured["staged_asset"] = staged_asset
        owned_asset.write_bytes(b"renderer mutated its private input")
        output = Path(request.out) / request.inputs["output_name"]
        output.write_bytes(b"\x00\x00\x00\x18ftyp")
        return SimpleNamespace(
            ok=True,
            error=None,
            payload={},
            outputs={"video": output},
        )

    monkeypatch.setattr(task_adapter_module, "run_executor", fake_run_executor)
    monkeypatch.setattr(task_adapter_module, "load_default_registry", lambda: object())

    RenderExportTaskAdapter(projects_root=tmp_path).execute(
        task=task,
        staging_dir=tmp_path / "staging",
    )

    assert sha256_file_bytes(managed) == digest
    assert sha256_file_bytes(captured["staged_asset"]) == digest
    assert not captured["owned_root"].exists()


def test_owned_input_setup_failure_is_cleaned(tmp_path: Path) -> None:
    create_project("render-project", name="Render Project", root=tmp_path)
    task = _task(root=tmp_path)
    task.spec["params"] = {
        **task.spec["params"],
        "output_filename": "../escape.mp4",
    }

    with pytest.raises(RenderExportRefused, match="plain .mp4 filename"):
        RenderExportTaskAdapter(projects_root=tmp_path).execute(
            task=task,
            staging_dir=tmp_path / "staging",
        )

    assert list((tmp_path / "render-project").glob(".render-inputs-*")) == []


def test_forced_caption_uses_server_owned_installed_remotion_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean deployment runtime, not the source ``remotion/`` checkout, renders text."""

    create_project("render-project", name="Render Project", root=tmp_path)
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
    cli = runtime / REMOTION_CLI_RELATIVE_PATH
    cli.parent.mkdir(parents=True)
    cli.write_text("// pinned local Remotion CLI\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "python3").symlink_to(Path(sys.executable).resolve())
    real_ffprobe = shutil.which("ffprobe")
    if real_ffprobe is None:
        pytest.fail("the installed ffprobe binary is required for this integration test")
    real_ffmpeg = shutil.which("ffmpeg")
    if real_ffmpeg is None:
        pytest.fail("the installed ffmpeg binary is required for this integration test")
    source_video = tmp_path / "source.mp4"
    source_video.write_bytes(FIXTURE_VIDEO.read_bytes())
    trusted_node = tmp_path / "trusted-node"
    trusted_node.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, subprocess, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('v20.19.4')\n"
        "    raise SystemExit(0)\n"
        "args = sys.argv[1:]\n"
        "out = pathlib.Path(args[args.index('--output') + 1])\n"
        f"subprocess.run([{str(real_ffmpeg)!r}, '-loglevel', 'error', '-y', '-i', {str(source_video)!r}, '-c', 'copy', '-video_track_timescale', '90000', str(out)], check=True)\n",
        encoding="utf-8",
    )
    (fake_bin / "npx").write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib\n"
        f"pathlib.Path({str(tmp_path / 'npx-used')!r}).write_text('unexpected npx')\n"
        "raise SystemExit(97)\n",
        encoding="utf-8",
    )
    # Keep the deployment-shaped PATH free of node while still exposing the
    # real media probe through an explicit, trusted binary path.
    (fake_bin / "ffprobe").write_text(
        f"#!/bin/sh\nexec {shlex.quote(real_ffprobe)} \"$@\"\n", encoding="utf-8"
    )
    for executable in (trusted_node, fake_bin / "npx", fake_bin / "ffprobe"):
        executable.chmod(0o755)
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(runtime))
    monkeypatch.setenv(NODE_EXECUTABLE_ENV, str(trusted_node))
    monkeypatch.setenv("PATH", str(fake_bin))
    assert shutil.which("python3") is not None
    assert shutil.which("ffprobe") is not None
    assert shutil.which("node") is None
    schema_spec = importlib.util.find_spec("banodoco_timeline_schema")
    if schema_spec is None or schema_spec.origin is None:
        pytest.fail("the pinned timeline-schema dependency is required for this integration test")
    schema_install = tmp_path / "installed-python"
    schema_package = schema_install / "banodoco_timeline_schema"
    shutil.copytree(Path(schema_spec.origin).parent, schema_package)
    # The clean readiness probe intentionally ignores ambient/user site
    # packages. Provision the small jsonschema dependency closure beside the
    # trusted schema so this test models an installed runtime rather than an
    # editable checkout.
    for dependency in (
        "jsonschema",
        "jsonschema_specifications",
        "referencing",
        "rpds",
        "attrs",
        "attr",
    ):
        dependency_spec = importlib.util.find_spec(dependency)
        if dependency_spec is None or dependency_spec.submodule_search_locations is None:
            pytest.fail(f"the pinned {dependency} dependency is required for this integration test")
        shutil.copytree(
            Path(next(iter(dependency_spec.submodule_search_locations))),
            schema_install / dependency,
        )
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
    # The fixture MP4 is 1280x720; keep the declared render profile aligned so
    # ffprobe validates the artifact produced by the trusted Node harness.
    config["theme_overrides"] = {
        **config["theme_overrides"],
        "visual": {
            **config["theme_overrides"]["visual"],
            "canvas": {"width": 1280, "height": 720, "fps": 24},
        },
    }
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
    assert not (tmp_path / "npx-used").exists()


def test_forced_caption_fails_before_renderer_without_server_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_project("render-project", name="Render Project", root=tmp_path)
    # Make the absence explicit: the source checkout may itself contain a
    # valid Remotion bundle during the pinned CI run.
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(tmp_path / "missing-remotion"))
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
    cli = runtime / REMOTION_CLI_RELATIVE_PATH
    cli.parent.mkdir(parents=True)
    cli.write_text("// pinned local Remotion CLI\n", encoding="utf-8")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    trusted_node = fake_bin / "node"
    trusted_node.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--version\" ]; then printf 'v20.19.4\\n'; fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    trusted_node.chmod(0o755)
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(runtime))
    monkeypatch.setenv(NODE_EXECUTABLE_ENV, str(trusted_node))
    monkeypatch.setenv(TIMELINE_SCHEMA_PYTHONPATH_ENV, str(schema_install))
    monkeypatch.setenv("PATH", f"{fake_bin}:{os.environ['PATH']}")
    status = remotion_runtime_status()
    assert not status.available
    assert missing_file in (status.reason or "")


def _runtime_with_locked_packages(tmp_path: Path) -> Path:
    runtime = tmp_path / "runtime"
    packages_root = runtime / "node_modules" / "@banodoco"
    for package in ("timeline-composition", "timeline-schema", "timeline-theme-2rp"):
        package_dir = packages_root / package
        package_dir.mkdir(parents=True)
        (package_dir / "package.json").write_text("{}", encoding="utf-8")
    (runtime / "package.json").write_text("{}", encoding="utf-8")
    return runtime


def _version_node(path: Path, *, marker: Path | None = None) -> None:
    marker_line = (
        f"pathlib.Path({str(marker)!r}).write_text('used')\n" if marker else ""
    )
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        "    print('v20.19.4')\n"
        "    raise SystemExit(0)\n"
        + marker_line
        + "raise SystemExit(97)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_remotion_readiness_requires_exact_locked_local_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime_with_locked_packages(tmp_path)
    node = tmp_path / "trusted-node"
    _version_node(node)
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(runtime))
    monkeypatch.setenv(NODE_EXECUTABLE_ENV, str(node))

    status = remotion_runtime_status()
    assert not status.available
    assert "locked Remotion CLI is missing" in (status.reason or "")

    wrong_cli = runtime / "node_modules" / "@remotion" / "cli" / "wrong.js"
    wrong_cli.parent.mkdir(parents=True)
    wrong_cli.write_text("// wrong entrypoint\n", encoding="utf-8")
    status = remotion_runtime_status()
    assert not status.available
    assert "locked Remotion CLI is missing" in (status.reason or "")


def test_remotion_runtime_uses_absolute_node_not_hostile_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = _runtime_with_locked_packages(tmp_path)
    cli = runtime / REMOTION_CLI_RELATIVE_PATH
    cli.parent.mkdir(parents=True)
    cli.write_text("// pinned local CLI\n", encoding="utf-8")
    trusted_node = tmp_path / "trusted-node"
    _version_node(trusted_node)
    fake_node = tmp_path / "fake-node"
    marker = tmp_path / "fake-node-used"
    _version_node(fake_node, marker=marker)
    monkeypatch.setenv("ASTRID_REMOTION_PROJECT_DIR", str(runtime))
    monkeypatch.setenv(NODE_EXECUTABLE_ENV, str(trusted_node))
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))

    tools, error = resolve_remotion_runtime_tools(runtime)
    assert error is None
    assert tools is not None
    assert tools.node_executable == trusted_node.resolve()
    assert tools.remotion_cli == cli.resolve()
    assert not marker.exists()


def test_remotion_node_version_probe_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 5)

    monkeypatch.setattr(remotion_runtime.subprocess, "run", timeout)
    version, error = remotion_runtime._probe_node(
        tmp_path / "trusted-node", cwd=tmp_path
    )
    assert version is None
    assert error is not None
    assert "version probe failed" in error


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
    create_project("render-project", name="Render Project", root=tmp_path)
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
    create_project("render-project", name="Render Project", root=tmp_path)
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
        create_project("render-project", name="Render Project", root=tmp_path, exist_ok=True)
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
