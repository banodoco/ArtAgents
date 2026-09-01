"""Shared rendering test helpers (execution env, probes, source fixtures).

Shared by the three.js, Remotion, and FFmpeg backend tests so the duplicated
ffprobe/ffmpeg scaffolding lives in one
place.  The env-skip trios (``_missing_environment`` etc.) stay in their own
test modules on purpose: they are genuinely divergent.
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from astrid.core.foundation.project_paths import project_dir
from astrid.sdk.workspace_client import page_pair

_LOCAL_VISUALIZE_ATTEMPTS = 0

# The visualization pack is intentionally invoked directly in these tests,
# but frozen views now prove their owner through the workspace runtime.  Keep
# one disposable daemon per test process so a root view and its child views
# share real runtime admission/settlement evidence without making the
# production reader accept filesystem ``run.json`` as authority.
_RUNTIME_CONTEXT: dict[str, Any] | None = None
_RUNTIME_STORAGE_ROOT = Path(tempfile.mkdtemp(prefix="astrid-frozen-runtime-"))
_RUNTIME_CAPABILITY = "rendering.timeline_visualize"
_RUNTIME_WORKER = "astrid-frozen-test-worker"


def _stop_runtime() -> None:
    global _RUNTIME_CONTEXT
    if _RUNTIME_CONTEXT is not None:
        _RUNTIME_CONTEXT["daemon"].stop()
        _RUNTIME_CONTEXT = None


atexit.register(_stop_runtime)


def _runtime_for(slug: str) -> dict[str, Any]:
    """Start/configure the disposable runtime backing local pack tests."""
    global _RUNTIME_CONTEXT
    if _RUNTIME_CONTEXT is None:
        runtime_checkout = (
            Path(__file__).resolve().parents[4]
            / "banodoco-workspace-runtime-stage1-convergence"
        )
        if str(runtime_checkout) not in sys.path:
            sys.path.insert(0, str(runtime_checkout))
        from runtime_protocol.daemon import RuntimeDaemon
        from astrid.sdk.workspace_client import WorkspaceClient

        daemon = RuntimeDaemon(
            _RUNTIME_STORAGE_ROOT / "realm",
            support_root=_RUNTIME_STORAGE_ROOT / "support",
        ).start()
        os.environ["BANODOCO_RUNTIME_ENDPOINT"] = daemon.endpoint
        os.environ["BANODOCO_RUNTIME_CREDENTIAL"] = str(
            _RUNTIME_STORAGE_ROOT / "support" / "credentials" / "owner.token"
        )
        client = WorkspaceClient(daemon.endpoint, daemon.token)
        capability_digest = "sha256:" + hashlib.sha256(_RUNTIME_CAPABILITY.encode()).hexdigest()
        daemon.service.register_capability(
            {
                "capability_id": _RUNTIME_CAPABILITY,
                "definition_digest": capability_digest,
                "required_resource_keys": [],
                "status": "ready",
            }
        )
        epoch = daemon.service.store._current_runtime_epoch()
        daemon.service.register_worker(
            {
                "worker_id": _RUNTIME_WORKER,
                "capabilities": [_RUNTIME_CAPABILITY],
                "max_concurrency": 128,
                "resource_keys": [],
                "runtime_epoch": epoch,
            }
        )
        _RUNTIME_CONTEXT = {
            "daemon": daemon,
            "client": client,
            "project_ids": {},
            "capability_digest": capability_digest,
        }
    context = _RUNTIME_CONTEXT
    assert context is not None
    if slug not in context["project_ids"]:
        project_page = page_pair(context["client"].list_projects())
        if project_page is None or project_page[1] is not None:
            raise RuntimeError("runtime project listing returned an invalid page")
        projects, _project_cursor = project_page
        project = next((row for row in projects if row.get("slug") == slug), None)
        if project is None:
            project = context["client"].create_project(
                slug,
                idempotency_key=f"astrid-frozen-project-{slug}",
                slug=slug,
                metadata={"fixture": "timeline_visualize"},
            )
        context["project_ids"][slug] = project["project_id"]
    return context


def _runtime_request(context: dict[str, Any], path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        context["daemon"].endpoint + path,
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {context['daemon'].worker_token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def _admit_runtime_run(slug: str) -> tuple[dict[str, Any], str, str]:
    context = _runtime_for(slug)
    task = context["client"].admit_task(
        capability_id=_RUNTIME_CAPABILITY,
        capability_digest=context["capability_digest"],
        input_object_ids=[],
        idempotency_key=f"astrid-frozen-{slug}-{os.urandom(8).hex()}",
        project_id=context["project_ids"][slug],
        spec={"fixture": "timeline_visualize"},
    )
    return context, task["run_id"], task["task_id"]


def _settle_runtime_pack(
    context: dict[str, Any],
    *,
    task_id: str,
    pack_root: Path,
) -> None:
    epoch = context["daemon"].service.store._current_runtime_epoch()
    lease = f"astrid-frozen-lease-{task_id}"
    claimed = _runtime_request(
        context,
        f"/v1/tasks/{task_id}/claim",
        {"worker_id": _RUNTIME_WORKER, "lease_token": lease, "runtime_epoch": epoch},
    )
    if claimed.get("state") != "running":
        raise RuntimeError(f"fixture runtime task was not claimable: {claimed!r}")
    manifest = json.loads((pack_root / "manifest.json").read_text(encoding="utf-8"))
    outputs: list[dict[str, Any]] = []
    for record in manifest.get("outputs", []):
        relative = record["path"]
        path = pack_root / relative
        # Project-level visualization manifests declare child directories as
        # navigation outputs.  They have no byte identity of their own; the
        # child manifests are separate views and are never selected by this
        # run's frozen-owner preflight.
        if not path.is_file():
            continue
        outputs.append(
            {
                "path": f"agent-view/{relative}",
                "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    # ``manifest.json`` cannot truthfully carry its own hash in the manifest
    # contract; the reader binds the declared files plus the integrity ledger.
    for relative in ("pack-hashes.json",):
        path = pack_root / relative
        if not path.is_file():
            continue
        outputs.append(
            {
                "path": f"agent-view/{relative}",
                "digest": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
            }
        )
    _runtime_request(
        context,
        f"/v1/tasks/{task_id}/settle",
        {
            "lease_token": lease,
            "runtime_epoch": epoch,
            "result": {"outputs": outputs, "manifest_path": "agent-view/manifest.json"},
        },
    )


def admit_runtime_run(slug: str) -> tuple[dict[str, Any], str, str]:
    """Test fixture seam for a copied pack that needs a new run identity."""
    return _admit_runtime_run(slug)


def settle_runtime_pack(
    context: dict[str, Any], *, task_id: str, pack_root: Path
) -> None:
    """Settle the exact copied bytes for an already-admitted fixture run."""
    _settle_runtime_pack(context, task_id=task_id, pack_root=pack_root)


@contextmanager
def _execution_env():
    """Prepend the active python bin and node bin to PATH so transport-spawned
    children resolve the same node and the same python3 (with the banodoco
    timeline schema) as the test process."""
    node_bin = (
        str(Path(shutil.which("node")).resolve().parent)
        if shutil.which("node")
        else ""
    )
    # Do not resolve the interpreter symlink: in a virtual environment the
    # resolved binary lives in the base Python installation, while the
    # sibling ``python3`` we need is in the venv's own ``bin`` directory.
    python_bin = str(Path(sys.executable).parent)
    old_path = os.environ.get("PATH", "")
    schema_env = "ASTRID_TIMELINE_SCHEMA_PYTHONPATH"
    old_schema_root = os.environ.get(schema_env)
    # A test runner may import the canonical package from a venv/site-packages
    # path without exporting the install root.  Renderer commands use
    # ``python3`` from PATH, so make that dependency explicit for the child
    # instead of relying on whichever interpreter happens to be first there.
    if not old_schema_root:
        try:
            import banodoco_timeline_schema

            schema_root = Path(banodoco_timeline_schema.__file__).resolve().parent
        except (ImportError, AttributeError):
            schema_root = None
        if schema_root is not None:
            os.environ[schema_env] = str(schema_root.parent)
    os.environ["PATH"] = ":".join(
        [d for d in (python_bin, node_bin) if d] + [old_path]
    )
    try:
        yield
    finally:
        os.environ["PATH"] = old_path
        if old_schema_root is None:
            os.environ.pop(schema_env, None)
        else:
            os.environ[schema_env] = old_schema_root


def _probe(path: Path) -> dict:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,codec_type,width,height,pix_fmt,time_base,avg_frame_rate,nb_read_frames,duration",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def _frame_md5(path: Path, frame: int) -> str:
    out = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-frames:v",
            "1",
            "-f",
            "md5",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return out.strip().split("=")[-1].strip()


def _source_video(tmp_path: Path, *, audio: bool = False) -> Path:
    """A tiny real h264 (+aac when audio=True) source clip used by media clips."""
    source_path = tmp_path / "source.mp4"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=size=320x180:rate=24",
    ]
    if audio:
        command += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
    command += ["-frames:v", "24"]
    if audio:
        command += ["-shortest"]
    command += [
        "-c:v",
        "libx264",
        "-profile:v",
        "main",
        "-pix_fmt",
        "yuv420p",
    ]
    if audio:
        command += ["-c:a", "aac"]
    command += ["-video_track_timescale", "12288", str(source_path)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return source_path


class LocalVisualizationInvocation:
    """Small result adapter for direct, attempt-local pack execution."""

    def __init__(self, raw: dict[str, Any], out_root: Path) -> None:
        self.raw_result = raw
        self.ok = raw.get("returncode") == 0
        self.error = raw.get("error")
        self.manifest_path = raw.get("manifest_path")
        self.run_root = str(out_root)
        self.outputs = raw.get("outputs", {}) if self.ok else {}
        self.run_id = out_root.name
        self.kernel_run_id = raw.get("kernel_run_id", out_root.name)
        self.kernel_task_id = raw.get("kernel_task_id")
        self.kernel_attempt_id = None
        self.executor_version = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "run_id": self.run_id,
            "run_root": self.run_root,
            "manifest_path": self.manifest_path,
            "executor_version": self.executor_version,
            "outputs": self.outputs,
        }


def invoke_local_visualization(slug: str, *, run_module: Any, **extra_inputs: Any) -> LocalVisualizationInvocation:
    """Call the packaged visualization executor without the retired bridge.

    Every invocation gets a fresh attempt root.  Inputs are translated to the
    executor's explicit CLI protocol, preserving the same argument boundary
    used by the production task adapter.
    """
    inputs: dict[str, Any] = {
        "project_slug": slug,
        "layout": "time-scaled",
        "formats": ["md"],
        "filmstrip": "off",
        **extra_inputs,
    }
    global _LOCAL_VISUALIZE_ATTEMPTS
    _LOCAL_VISUALIZE_ATTEMPTS += 1
    runtime_context, runtime_run_id, runtime_task_id = _admit_runtime_run(slug)
    out_root = project_dir(slug) / "runs" / runtime_run_id
    out_root.mkdir(parents=True, exist_ok=False)
    argv = ["--out", str(out_root), "--project-slug", slug]
    scalar_flags = {
        "timeline_slug": "--timeline-slug", "scope": "--scope",
        "range": "--range", "at": "--at", "clip": "--clip",
        "asset": "--asset", "context": "--context", "neighbors": "--neighbors",
        "from_view": "--from-view", "focus": "--focus", "layout": "--layout",
        "filmstrip": "--filmstrip", "rendered_video": "--rendered-video",
    }
    for key, flag in scalar_flags.items():
        value = inputs.get(key)
        if value is not None:
            argv.extend([flag, str(value)])
    raw_sources = inputs.get("timeline_source")
    sources = raw_sources if isinstance(raw_sources, list) else [raw_sources]
    for source in sources:
        if source is not None:
            argv.extend(["--timeline-source", str(source)])
    for fmt in inputs.get("formats", []):
        argv.extend(["--format", str(fmt)])
    if inputs.get("select_all"):
        argv.append("--all")
    if inputs.get("refresh_root"):
        argv.append("--refresh-root")
    raw = run_module.run_sdk(argv)
    if raw.get("returncode") == 0:
        timeline_ids = raw.get("timeline_ids", [])
        record = {
            "schema_version": 1,
            "run_id": out_root.name,
            "project_slug": slug,
            "status": "completed",
            "tool_id": "rendering.timeline_visualize",
            "invocation": "sdk",
            "auto_bound": False,
            "out": f"runs/{out_root.name}",
            "manifest_path": f"runs/{out_root.name}/agent-view/manifest.json",
            "metadata": {"evidence": True, "timeline_ids": sorted(timeline_ids)},
            "artifacts": {},
        }
        (out_root / "run.json").write_text(
            json.dumps(record, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )
        _settle_runtime_pack(
            runtime_context,
            task_id=runtime_task_id,
            pack_root=out_root / "agent-view",
        )
    else:
        # Avoid leaving queued runtime tasks behind when the pack itself
        # rejected its inputs.  The failure result remains the test oracle.
        try:
            runtime_context["client"].cancel_task(
                runtime_task_id,
                idempotency_key=f"astrid-frozen-cancel-{runtime_task_id}",
            )
        except Exception:
            pass
    raw.setdefault("run_id", runtime_run_id)
    raw.setdefault("kernel_run_id", runtime_run_id)
    raw.setdefault("kernel_task_id", runtime_task_id)
    return LocalVisualizationInvocation(raw, out_root)
