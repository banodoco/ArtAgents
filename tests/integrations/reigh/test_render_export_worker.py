"""Transport-neutral render-export worker lifecycle tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

import astrid.core.integrations.reigh.render_export_worker as worker_module
from astrid.core.integrations.reigh.render_export_worker import (
    HttpRenderExportWorkerTransport,
    RenderExportServeWorker,
    RenderExportWorker,
    _ProcessContainment,
    _stream_digest,
)


class _Transport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def post_json(self, path: str, body: dict, *, key: str | None = None):
        self.calls.append((path, {"body": body, "key": key}))
        if path == "/queue/claim":
            return 200, {
                "task": {
                    "id": "task-render",
                    "spec": {"family": "render_export", "project_slug": "demo"},
                },
                "attempt": {
                    "id": "attempt-render",
                    "attempt_no": 1,
                    "lease_id": "lease-render",
                    "status_version": 1,
                },
            }
        if "/heartbeat" in path:
            return 200, {"attempt": {"status_version": body["status_version"] + 1}}
        if "/fail" in path:
            raise AssertionError(f"unexpected failure settlement: {body!r}")
        raise AssertionError(path)

    def get_json(self, path: str):
        self.calls.append((path, None))
        return 200, {"task": {"status": "running"}}

    def post_multipart_file(
        self,
        path: str,
        manifest: dict,
        output_path: Path,
        boundary: str,
        *,
        key: str | None = None,
        on_chunk=None,
    ):
        body = json.dumps(manifest, sort_keys=True).encode() + output_path.read_bytes()
        if on_chunk is not None:
            on_chunk(output_path.stat().st_size)
        self.calls.append((path, {"body": body, "boundary": boundary, "key": key}))
        return 200, {"task": {"status": "succeeded"}}


def test_worker_child_result_settles_through_multipart(monkeypatch, tmp_path: Path) -> None:
    transport = _Transport()

    def fake_child(*, claim, staging_dir, heartbeat, cancelled):
        heartbeat({"phase": "render", "percent": 10})
        output = staging_dir / "requested.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        import hashlib

        return {
            "outputs": [
                {
                    "path": output.name,
                    "content_hash": "sha256:" + hashlib.sha256(output.read_bytes()).hexdigest(),
                }
            ]
        }

    worker = RenderExportWorker(
        transport,
        projects_root=tmp_path,
        executor_id="render-worker",
        deadline_seconds=5,
    )
    monkeypatch.setattr(worker, "_run_child", fake_child)
    result = worker.run_once()
    assert result == {"task": {"status": "succeeded"}}
    complete = next(body for path, body in transport.calls if path.endswith("/complete"))
    assert complete["key"] == "reigh.render.complete:task-render:1"
    assert b'"key": "out0"' in complete["body"]
    assert b"ftyp" in complete["body"]
    heartbeats = [body["body"] for path, body in transport.calls if "/heartbeat" in path]
    assert heartbeats
    assert all(body["lease_seconds"] >= 125 for body in heartbeats)


def test_completion_replays_same_fence_body_after_lost_ack(
    monkeypatch, tmp_path: Path
) -> None:
    class ReplayTransport(_Transport):
        def __init__(self) -> None:
            super().__init__()
            self.uploads: list[tuple[str | None, dict]] = []
            self.detail_reads = 0
            self.lost_reconcile = True

        def get_json(self, path: str):
            self.detail_reads += 1
            self.calls.append((path, None))
            if self.uploads and self.lost_reconcile:
                self.lost_reconcile = False
                raise ConnectionError("detail ACK observation lost")
            return 200, {"task": {"status": "running"}}

        def post_multipart_file(
            self,
            path: str,
            manifest: dict,
            output_path: Path,
            boundary: str,
            *,
            key: str | None = None,
            on_chunk=None,
        ):
            self.uploads.append((key, dict(manifest)))
            if on_chunk is not None:
                on_chunk(output_path.stat().st_size)
            if len(self.uploads) == 1:
                raise ConnectionError("completion ACK lost")
            return 200, {"task": {"status": "succeeded"}}

    transport = ReplayTransport()

    def fake_child(*, claim, staging_dir, heartbeat, cancelled):
        output = staging_dir / "requested.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return {
            "outputs": [
                {
                    "path": output.name,
                    "content_hash": "sha256:"
                    + __import__("hashlib").sha256(output.read_bytes()).hexdigest(),
                }
            ]
        }

    worker = RenderExportWorker(
        transport,
        projects_root=tmp_path,
        executor_id="render-worker",
        deadline_seconds=5,
    )
    monkeypatch.setattr(worker, "_run_child", fake_child)
    result = worker.run_once()
    assert result == {"task": {"status": "succeeded"}}
    assert len(transport.uploads) == 2
    assert transport.uploads[0][0] == transport.uploads[1][0]
    assert transport.uploads[0][1] == transport.uploads[1][1]
    assert not any(path.endswith("/fail") for path, _ in transport.calls)


def test_definitive_413_completion_rejects_without_replay(
    monkeypatch, tmp_path: Path
) -> None:
    class TooLargeTransport(_Transport):
        def post_multipart_file(self, *args, **kwargs):
            self.calls.append(("/complete", {"key": kwargs.get("key")}))
            return 413, {"error": "payload_too_large"}

        def post_json(self, path: str, body: dict, *, key: str | None = None):
            if path.endswith("/fail"):
                self.calls.append((path, {"body": body, "key": key}))
                return 200, {"task": {"status": "failed"}}
            return super().post_json(path, body, key=key)

    transport = TooLargeTransport()

    def fake_child(*, claim, staging_dir, heartbeat, cancelled):
        output = staging_dir / "requested.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return {
            "outputs": [
                {
                    "path": output.name,
                    "content_hash": "sha256:"
                    + __import__("hashlib").sha256(output.read_bytes()).hexdigest(),
                }
            ]
        }

    worker = RenderExportWorker(
        transport,
        projects_root=tmp_path,
        executor_id="render-worker",
        deadline_seconds=5,
    )
    monkeypatch.setattr(worker, "_run_child", fake_child)
    result = worker.run_once()
    assert result == {"task": {"status": "failed"}}
    assert len([path for path, _ in transport.calls if path.endswith("/complete")]) == 1
    assert len([path for path, _ in transport.calls if path.endswith("/fail")]) == 1


def test_409_after_lease_loss_stops_replay_for_queued_task(
    monkeypatch, tmp_path: Path
) -> None:
    class QueuedTransport(_Transport):
        def __init__(self) -> None:
            super().__init__()
            self.detail_reads = 0
            self.uploads = 0

        def get_json(self, path: str):
            self.detail_reads += 1
            self.calls.append((path, None))
            status = "running" if self.detail_reads == 1 else "queued"
            return 200, {"task": {"status": status}}

        def post_multipart_file(self, *args, **kwargs):
            self.uploads += 1
            return 409, {"error": "attempt_not_live"}

    transport = QueuedTransport()

    def fake_child(*, claim, staging_dir, heartbeat, cancelled):
        output = staging_dir / "requested.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return {
            "outputs": [
                {
                    "path": output.name,
                    "content_hash": "sha256:"
                    + __import__("hashlib").sha256(output.read_bytes()).hexdigest(),
                }
            ]
        }

    worker = RenderExportWorker(
        transport,
        projects_root=tmp_path,
        executor_id="render-worker",
        deadline_seconds=5,
    )
    monkeypatch.setattr(worker, "_run_child", fake_child)
    with pytest.raises(RuntimeError, match="queued"):
        worker.run_once()
    assert transport.uploads == 1
    assert not any(path.endswith("/fail") for path, _ in transport.calls)


def test_stream_digest_honors_bounded_control_callback(tmp_path: Path) -> None:
    output = tmp_path / "large.mp4"
    output.write_bytes(b"x" * (3 * 1024 * 1024))
    seen: list[int] = []

    def stop_after_first_chunk(size: int) -> None:
        seen.append(size)
        if size >= 1024 * 1024:
            raise RuntimeError("deadline")

    with pytest.raises(RuntimeError, match="deadline"):
        _stream_digest(output, on_chunk=stop_after_first_chunk)
    assert seen == [1024 * 1024]


def test_shutdown_during_upload_fenced_failure_clears_running_claim(
    monkeypatch, tmp_path: Path
) -> None:
    class BlockingUploadTransport(_Transport):
        def __init__(self) -> None:
            super().__init__()
            self.state = "running"
            self.upload_started = threading.Event()

        def get_json(self, path: str):
            self.calls.append((path, None))
            return 200, {"task": {"status": self.state}}

        def post_multipart_file(
            self,
            path: str,
            manifest: dict,
            output_path: Path,
            boundary: str,
            *,
            key: str | None = None,
            on_chunk=None,
        ):
            self.upload_started.set()
            while True:
                if on_chunk is not None:
                    on_chunk(1)
                time.sleep(0.01)

        def post_json(self, path: str, body: dict, *, key: str | None = None):
            if path.endswith("/fail"):
                self.state = "failed"
                self.calls.append((path, {"body": body, "key": key}))
                return 200, {"task": {"status": "failed"}}
            return super().post_json(path, body, key=key)

    transport = BlockingUploadTransport()

    def fake_child(*, claim, staging_dir, heartbeat, cancelled):
        output = staging_dir / "requested.mp4"
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return {
            "outputs": [
                {
                    "path": output.name,
                    "content_hash": "sha256:"
                    + __import__("hashlib").sha256(output.read_bytes()).hexdigest(),
                }
            ]
        }

    worker = RenderExportServeWorker(
        transport,
        projects_root=tmp_path,
        executor_id="serve-test-render",
        poll_interval_seconds=0.01,
        deadline_seconds=30,
    )
    monkeypatch.setattr(worker._worker, "_run_child", fake_child)
    worker.start()
    assert transport.upload_started.wait(timeout=2)
    worker.stop(timeout_seconds=3)
    assert not worker.thread.is_alive()
    assert transport.state == "failed", transport.calls
    assert any(path.endswith("/fail") for path, _ in transport.calls)


class _IdleTransport:
    def __init__(self) -> None:
        self.claims = 0

    def post_json(self, path: str, body: dict, *, key: str | None = None):
        assert path == "/queue/claim"
        self.claims += 1
        return 204, {}

    def get_json(self, path: str):
        raise AssertionError(path)

    def post_multipart(
        self,
        path: str,
        body: bytes,
        boundary: str,
        *,
        key: str | None = None,
    ):
        raise AssertionError(path)


def test_serve_worker_has_bounded_stop_lifecycle(tmp_path: Path) -> None:
    transport = _IdleTransport()
    worker = RenderExportServeWorker(
        transport,
        projects_root=tmp_path,
        executor_id="serve-test-render",
        poll_interval_seconds=0.01,
        deadline_seconds=1,
    )
    worker.start()
    deadline = time.monotonic() + 1
    while transport.claims == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    worker.stop(timeout_seconds=1)
    assert transport.claims > 0
    assert not worker.thread.is_alive()


def test_darwin_process_census_tracks_and_kills_detached_grandchild(tmp_path: Path) -> None:
    marker = tmp_path / "detached-marker"
    grandchild = (
        "import pathlib,sys,time\n"
        "p=pathlib.Path(sys.argv[1])\n"
        "while True:\n"
        "    p.write_text(str(time.monotonic()))\n"
        "    time.sleep(.03)\n"
    )
    root_code = (
        "import subprocess,sys,time\n"
        f"subprocess.Popen([sys.executable,'-c',{grandchild!r},{str(marker)!r}], "
        "start_new_session=True)\n"
        "time.sleep(30)\n"
    )
    root = subprocess.Popen(
        [sys.executable, "-c", root_code],
        start_new_session=True,
    )
    containment = None
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        assert marker.exists()
        containment = _ProcessContainment(root.pid)
        containment.refresh()
        observed = set(containment._observed_pids)
        assert len(observed) >= 2
        time.sleep(0.1)
        containment.terminate()
        root.wait(timeout=5)
        time.sleep(0.15)
        after = marker.stat().st_mtime_ns
        time.sleep(0.2)
        assert marker.stat().st_mtime_ns == after
    finally:
        if root.poll() is None:
            (containment or _ProcessContainment(root.pid)).terminate()
            root.kill()
            root.wait()


def test_run_child_cleans_descendants_after_successful_parent_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "normal-exit-descendant-marker"
    pid_file = tmp_path / "normal-exit-descendant.pid"
    real_popen = worker_module.subprocess.Popen

    def fake_popen(command, **kwargs):
        if "--staging-dir" not in command:
            return real_popen(command, **kwargs)
        staging = Path(command[command.index("--staging-dir") + 1])
        output = staging / "requested.mp4"
        grandchild = (
            "import pathlib,sys,time,os\n"
            "p=pathlib.Path(sys.argv[1]); pathlib.Path(sys.argv[2]).write_text(str(os.getpid()))\n"
            "while True: p.write_text(str(time.monotonic())); time.sleep(.03)\n"
        )
        root_code = (
            "import hashlib,json,pathlib,subprocess,sys,time\n"
            f"marker={str(marker)!r}; pid_file={str(pid_file)!r}; output={str(output)!r}\n"
            f"subprocess.Popen([sys.executable,'-c',{grandchild!r},marker,pid_file], start_new_session=True)\n"
            "pathlib.Path(output).write_bytes(b'\\x00\\x00\\x00\\x18ftypmp42')\n"
            "digest=hashlib.sha256(pathlib.Path(output).read_bytes()).hexdigest()\n"
            "pathlib.Path(output).parent.joinpath('manifest.json').write_text(json.dumps({'outputs':[{'path':'requested.mp4','content_hash':'sha256:'+digest}]}))\n"
            "time.sleep(.35)\n"
        )
        return real_popen([sys.executable, "-c", root_code], **kwargs)

    monkeypatch.setattr(worker_module.subprocess, "Popen", fake_popen)
    worker = RenderExportWorker(
        _IdleTransport(),
        projects_root=tmp_path,
        executor_id="render-worker",
        deadline_seconds=5,
    )
    claim = type("Claim", (), {"task_id": "task", "spec": {}})()
    staging = tmp_path / "staging"
    staging.mkdir()
    worker._run_child(
        claim=claim,
        staging_dir=staging,
        heartbeat=lambda _payload: None,
        cancelled=lambda: False,
    )
    assert marker.exists()
    assert pid_file.exists()
    stable = marker.stat().st_mtime_ns
    time.sleep(0.2)
    assert marker.stat().st_mtime_ns == stable
    descendant_pid = int(pid_file.read_text())
    for _ in range(20):
        try:
            os.kill(descendant_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.03)
    else:
        pytest.fail("successful child cleanup left detached renderer descendant alive")


@pytest.mark.parametrize(
    "url",
    (
        "https://127.0.0.1:1234",
        "http://localhost:1234",
        "http://[::1]:1234",
        "http://127.0.0.1:1234/path",
        "http://user:pass@127.0.0.1:1234",
    ),
)
def test_worker_http_transport_requires_authenticated_ipv4_loopback(url: str) -> None:
    with pytest.raises(ValueError):
        HttpRenderExportWorkerTransport(url, token="secret")
    with pytest.raises(ValueError):
        HttpRenderExportWorkerTransport("http://127.0.0.1:1234", token="")


def test_worker_poll_health_exposes_transient_errors(tmp_path: Path) -> None:
    class FailingTransport(_IdleTransport):
        def post_json(self, path: str, body: dict, *, key: str | None = None):
            raise OSError("bridge unavailable")

    worker = RenderExportServeWorker(
        FailingTransport(),
        projects_root=tmp_path,
        executor_id="serve-test-render",
        poll_interval_seconds=0.01,
        deadline_seconds=1,
    )
    worker.start()
    deadline = time.monotonic() + 1
    while worker.health["error_count"] == 0 and time.monotonic() < deadline:
        time.sleep(0.005)
    worker.stop(timeout_seconds=1)
    assert worker.health["error_count"] > 0
    assert worker.health["last_error"] == "bridge unavailable"
