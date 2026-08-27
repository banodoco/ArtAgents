"""Transport-neutral one-shot worker for the real render-export task.

The paired verifier and a production HTTP worker can share this lifecycle:
claim one fenced task, run the pack-owned adapter, heartbeat bounded progress,
and settle the result through the existing multipart completion route.  This
module intentionally does not poll or own a database writer.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import logging
import math
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlsplit

from astrid.core.subprocess_env import build_child_subprocess_env

_LOG = logging.getLogger(__name__)
_MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024
_PROCESS_POLL_SECONDS = 0.25
_PROCESS_TERM_GRACE_SECONDS = 3.0
_CHILD_DIAGNOSTIC_TAIL_BYTES = 64 * 1024
_CHILD_FAILURE_MESSAGE_CHARS = 3_500


class _BoundedByteTail:
    """Continuously drain a byte stream while retaining only its bounded tail."""

    def __init__(self, max_bytes: int = _CHILD_DIAGNOSTIC_TAIL_BYTES) -> None:
        self._max_bytes = max(1, int(max_bytes))
        self._data = bytearray()

    def append(self, chunk: bytes) -> None:
        self._data.extend(chunk)
        overflow = len(self._data) - self._max_bytes
        if overflow > 0:
            del self._data[:overflow]

    def text(self) -> str:
        return bytes(self._data).decode("utf-8", errors="replace").strip()


def _drain_child_stream(stream: Any, tail: _BoundedByteTail) -> None:
    if stream is None:
        return
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            tail.append(chunk)
    finally:
        stream.close()


def _bounded_child_failure(returncode: int, stdout: str, stderr: str) -> str:
    """Format actionable child diagnostics within the bridge error contract."""

    parts = [f"render_export child exited with code {returncode}"]
    if stderr:
        parts.append(f"stderr tail:\n{stderr[-2_700:]}")
    if stdout:
        parts.append(f"stdout tail:\n{stdout[-500:]}")
    message = "\n".join(parts)
    if len(message) <= _CHILD_FAILURE_MESSAGE_CHARS:
        return message
    return message[:120] + "\n…diagnostic tail truncated…\n" + message[-3_300:]


class RenderExportWorkerTransport(Protocol):
    def get_json(self, path: str) -> tuple[int, Any]: ...

    def post_json(
        self, path: str, body: Mapping[str, Any], *, key: str | None = None
    ) -> tuple[int, Any]: ...

    def post_multipart(
        self,
        path: str,
        body: bytes,
        boundary: str,
        *,
        key: str | None = None,
    ) -> tuple[int, Any]: ...

    def post_multipart_file(
        self,
        path: str,
        manifest: Mapping[str, Any],
        output_path: Path,
        boundary: str,
        *,
        key: str | None = None,
        on_chunk: Callable[[int], None] | None = None,
    ) -> tuple[int, Any]: ...


class HttpRenderExportWorkerTransport:
    """Bounded loopback HTTP transport for the serve-owned worker.

    The worker uses the same bridge routes as an external executor.  Keeping
    this transport in Astrid (rather than in a Reigh release script) means a
    normal ``astrid serve`` process owns the complete task lifecycle.
    """

    def __init__(
        self,
        base_url: str,
        token: str = "",
        *,
        protocol_version: str = "v1",
        timeout_seconds: float = 15.0,
        require_auth: bool = True,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path not in ("", "/")
            or parsed.port is None
            or not 1 <= parsed.port <= 65535
        ):
            raise ValueError(
                "worker base_url must be an authenticated http://127.0.0.1:<port> URL"
            )
        if require_auth and (not isinstance(token, str) or not token.strip()):
            raise ValueError("worker HTTP transport requires a non-empty bearer token")
        if timeout_seconds <= 0:
            raise ValueError("worker HTTP timeout must be positive")
        self._host = parsed.hostname
        self._port = parsed.port
        self._token = token
        self._protocol_version = protocol_version
        self._timeout_seconds = float(timeout_seconds)
        self._require_auth = require_auth

    def _headers(self, content_type: str, key: str | None) -> dict[str, str]:
        headers = {
            "Content-Type": content_type,
            "X-Astrid-Bridge-Version": self._protocol_version,
        }
        if self._token or self._require_auth:
            headers["Authorization"] = f"Bearer {self._token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        return headers

    @staticmethod
    def _decode(response: Any) -> Any:
        raw = response.read()
        return json.loads(raw) if raw else {}

    def _send(self, request: urllib.request.Request) -> tuple[int, Any]:
        try:
            with urllib.request.urlopen(  # noqa: S310 - loopback URL is serve-owned
                request, timeout=self._timeout_seconds
            ) as response:
                return response.status, self._decode(response)
        except urllib.error.HTTPError as error:
            return error.code, self._decode(error)

    def get_json(self, path: str) -> tuple[int, Any]:
        return self._send(
            urllib.request.Request(
                f"http://{self._host}:{self._port}{path}",
                headers=self._headers("application/json", None),
            )
        )

    def post_json(
        self, path: str, body: Mapping[str, Any], *, key: str | None = None
    ) -> tuple[int, Any]:
        return self._send(
            urllib.request.Request(
                f"http://{self._host}:{self._port}{path}",
                data=json.dumps(body, sort_keys=True).encode("utf-8"),
                method="POST",
                headers=self._headers("application/json", key),
            )
        )

    def post_multipart(
        self,
        path: str,
        body: bytes,
        boundary: str,
        *,
        key: str | None = None,
    ) -> tuple[int, Any]:
        return self._send(
            urllib.request.Request(
                f"http://{self._host}:{self._port}{path}",
                data=body,
                method="POST",
                headers=self._headers(
                    f"multipart/form-data; boundary={boundary}", key
                ),
            )
        )

    def post_multipart_file(
        self,
        path: str,
        manifest: Mapping[str, Any],
        output_path: Path,
        boundary: str,
        *,
        key: str | None = None,
        on_chunk: Callable[[int], None] | None = None,
    ) -> tuple[int, Any]:
        """Upload a multipart result in bounded chunks without buffering it."""
        filename = output_path.name.replace('"', "_")
        manifest_bytes = json.dumps(
            dict(manifest), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        prefix = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="manifest"\r\n\r\n'
        ).encode() + manifest_bytes + b"\r\n" + (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="out0"; '
            f'filename="{filename}"\r\n\r\n'
        ).encode()
        suffix = f"\r\n--{boundary}--\r\n".encode()
        size = output_path.stat().st_size
        if size > _MAX_OUTPUT_BYTES:
            raise RenderExportWorkerError("render_export output exceeds the bounded upload limit")
        headers = self._headers(
            f"multipart/form-data; boundary={boundary}", key
        )
        headers["Content-Length"] = str(len(prefix) + size + len(suffix))
        connection = http.client.HTTPConnection(
            self._host, self._port, timeout=self._timeout_seconds
        )
        try:
            connection.connect()
            connection.putrequest("POST", path)
            for name, value in headers.items():
                connection.putheader(name, value)
            connection.endheaders()
            connection.send(prefix)
            sent = 0
            with output_path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    connection.send(chunk)
                    sent += len(chunk)
                    if on_chunk is not None:
                        on_chunk(sent)
            connection.send(suffix)
            response = connection.getresponse()
            raw = response.read()
            return response.status, json.loads(raw) if raw else {}
        finally:
            connection.close()

class RenderExportWorkerError(RuntimeError):
    """Raised when a one-shot render worker cannot settle its claim."""


class _CompletionUncertain(RenderExportWorkerError):
    """Completion was attempted; retry/reconcile instead of issuing ``/fail``."""


class _CompletionDefinitive(RenderExportWorkerError):
    """The bridge definitively rejected completion; normal failure is safe."""


def _stream_digest(
    path: Path, *, on_chunk: Callable[[int], None] | None = None
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            size += len(chunk)
            if size > _MAX_OUTPUT_BYTES:
                raise RenderExportWorkerError(
                    "render_export output exceeds the bounded upload limit"
                )
            digest.update(chunk)
            if on_chunk is not None:
                on_chunk(size)
    return digest.hexdigest(), size


@dataclass(frozen=True, slots=True)
class RenderExportClaim:
    task_id: str
    attempt_id: str
    attempt_no: int
    lease_id: str
    status_version: int
    spec: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class _ProcessInfo:
    pid: int
    ppid: int
    pgid: int
    sid: int


def _process_snapshot() -> dict[int, _ProcessInfo]:
    """Read a small process census without invoking a shell."""
    ps = next(
        (candidate for candidate in ("/bin/ps", "/usr/bin/ps") if Path(candidate).is_file()),
        None,
    )
    if ps is None:
        return {}
    session_keyword = "sess" if platform.system() == "Darwin" else "sid"
    try:
        raw = subprocess.check_output(
            [ps, "-axo", f"pid=,ppid=,pgid=,{session_keyword}="],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=1,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    result: dict[int, _ProcessInfo] = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != 4:
            continue
        try:
            pid, ppid, pgid, sid = (int(field) for field in fields)
        except ValueError:
            continue
        result[pid] = _ProcessInfo(pid, ppid, pgid, sid)
    return result


class _ProcessContainment:
    """Track a renderer and descendants, including detached sessions seen live."""

    def __init__(self, root_pid: int) -> None:
        self._root_pid = root_pid
        self._observed_pids: set[int] = {root_pid}
        self._observed_groups: set[int] = set()

    def refresh(self) -> None:
        snapshot = _process_snapshot()
        children: dict[int, list[_ProcessInfo]] = {}
        for info in snapshot.values():
            children.setdefault(info.ppid, []).append(info)
        pending = [self._root_pid, *self._observed_pids]
        seen: set[int] = set()
        while pending:
            parent = pending.pop()
            if parent in seen:
                continue
            seen.add(parent)
            for info in children.get(parent, ()):
                self._observed_pids.add(info.pid)
                pending.append(info.pid)
        # Continue following a process that reparented after it detached: the
        # PID and process-group/session were recorded in an earlier census.
        for pid in tuple(self._observed_pids):
            current = snapshot.get(pid)
            if current is not None:
                self._observed_groups.add(current.pgid)

    def terminate(self) -> None:
        self.refresh()
        own_group = os.getpgrp()
        groups = sorted(
            {
                *self._observed_groups,
                # The outer worker always starts the root in its own session;
                # this fallback remains safe even if process enumeration is
                # unavailable on a constrained host.
                self._root_pid,
            }
            - {own_group}
            - {group for group in self._observed_groups if group <= 1}
        )
        for group in groups:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except PermissionError as exc:
                _LOG.warning("unable to terminate renderer process group %s: %s", group, exc)
        deadline = time.monotonic() + _PROCESS_TERM_GRACE_SECONDS
        while time.monotonic() < deadline:
            self.refresh()
            live = [pid for pid in self._observed_pids if pid != self._root_pid and pid in _process_snapshot()]
            if not live:
                break
            time.sleep(0.05)
        self.refresh()
        for group in groups:
            try:
                os.killpg(group, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        for pid in sorted(self._observed_pids, reverse=True):
            if pid == self._root_pid:
                continue
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def _claim(body: Mapping[str, Any]) -> RenderExportClaim:
    task = body.get("task") or {}
    attempt = body.get("attempt") or {}
    return RenderExportClaim(
        task_id=str(task["id"]),
        attempt_id=str(attempt["id"]),
        attempt_no=int(attempt["attempt_no"]),
        lease_id=str(attempt["lease_id"]),
        status_version=int(attempt["status_version"]),
        spec=dict(task.get("spec") or {}),
    )


class RenderExportWorker:
    """Run at most one claimed ``rendering.render`` task over any transport."""

    def __init__(
        self,
        transport: RenderExportWorkerTransport,
        *,
        projects_root: str | Path,
        executor_id: str,
        lease_seconds: int = 1800,
        deadline_seconds: float = 30 * 60,
        stop_requested: Any = None,
    ) -> None:
        self._transport = transport
        self._projects_root = Path(projects_root)
        self._executor_id = executor_id
        self._lease_seconds = max(
            int(lease_seconds), int(math.ceil(float(deadline_seconds))) + 120
        )
        self._deadline_seconds = deadline_seconds
        self._stop_requested = stop_requested or (lambda: False)
        self._run_deadline_at: float | None = None

    def _run_child(
        self,
        *,
        claim: RenderExportClaim,
        staging_dir: Path,
        heartbeat: Any,
        cancelled: Any,
    ) -> Mapping[str, Any]:
        task_json = staging_dir / "task.json"
        task_json.write_text(
            json.dumps(
                {"id": claim.task_id, "created_at": "", "spec": dict(claim.spec)},
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        command = [
            sys.executable,
            "-m",
            "astrid.packs.rendering.executors.render.task_adapter",
            "--task-json",
            str(task_json),
            "--staging-dir",
            str(staging_dir),
            "--projects-root",
            str(self._projects_root),
            "--deadline-seconds",
            str(self._deadline_seconds),
        ]
        # Use the canonical child environment allowlist. In particular, a
        # renderer must not inherit ambient API keys/tokens merely because the
        # serve process has them; diagnostics can therefore be surfaced safely.
        child_env = build_child_subprocess_env(base=os.environ, parent=os.environ)
        schema_pythonpath = child_env.get("ASTRID_TIMELINE_SCHEMA_PYTHONPATH")
        if schema_pythonpath:
            child_env["PYTHONPATH"] = schema_pythonpath
        # The renderer child has no bridge authority and must not inherit the
        # serve bearer token.  It receives only the frozen task JSON and the
        # validated projects-root argument.
        child_env.pop("ASTRID_BRIDGE_TOKEN", None)
        child = subprocess.Popen(  # noqa: S603 - fixed module and validated paths
            command,
            cwd=str(Path(__file__).resolve().parents[4]),
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout_tail = _BoundedByteTail()
        stderr_tail = _BoundedByteTail()
        diagnostic_threads = (
            threading.Thread(
                target=_drain_child_stream,
                args=(child.stdout, stdout_tail),
                name="astrid-render-export-stdout",
                daemon=True,
            ),
            threading.Thread(
                target=_drain_child_stream,
                args=(child.stderr, stderr_tail),
                name="astrid-render-export-stderr",
                daemon=True,
            ),
        )
        for thread in diagnostic_threads:
            thread.start()
        containment = _ProcessContainment(child.pid)
        deadline = time.monotonic() + float(self._deadline_seconds)
        if self._run_deadline_at is not None:
            deadline = min(deadline, self._run_deadline_at)
        next_heartbeat = time.monotonic()
        try:
            while child.poll() is None:
                containment.refresh()
                now = time.monotonic()
                if now >= deadline:
                    raise RenderExportWorkerError("render_export child deadline exceeded")
                if self._stop_requested() or cancelled():
                    raise RenderExportWorkerError("render_export task was cancelled")
                if now >= next_heartbeat:
                    heartbeat({"phase": "render", "percent": 10})
                    next_heartbeat = now + 5.0
                time.sleep(_PROCESS_POLL_SECONDS)
            returncode = int(child.returncode or 0)
            # Descendants may inherit the pipes after the direct child exits.
            # Terminate the complete observed scope before joining drainers so
            # a detached renderer cannot hold diagnostics open forever.
            containment.terminate()
            for thread in diagnostic_threads:
                thread.join(timeout=_PROCESS_TERM_GRACE_SECONDS)
            if any(thread.is_alive() for thread in diagnostic_threads):
                raise RenderExportWorkerError(
                    "render_export child diagnostics did not drain after containment"
                )
            if returncode != 0:
                raise RenderExportWorkerError(
                    _bounded_child_failure(
                        returncode,
                        stdout_tail.text(),
                        stderr_tail.text(),
                    )
                )
        except BaseException:  # noqa: BLE001 - clear deadline on interruption too
            containment.terminate()
            try:
                child.wait(timeout=_PROCESS_TERM_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                # The containment pass has already escalated all observed
                # groups and descendants; this final direct reap is only for
                # a process that disappeared from the census.
                try:
                    child.kill()
                except ProcessLookupError:
                    pass
                child.wait(timeout=_PROCESS_TERM_GRACE_SECONDS)
            for thread in diagnostic_threads:
                thread.join(timeout=_PROCESS_TERM_GRACE_SECONDS)
            raise
        # A renderer may report success while a descendant it spawned is
        # still alive (or has detached into another session).  The containment
        # pass is therefore mandatory on the success path too, before the
        # staging directory is read/removed and the claim can be settled.
        manifest = json.loads((staging_dir / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, Mapping):
            raise RenderExportWorkerError("render_export child manifest is invalid")
        return manifest

    def run_once(self, *, progress: bool = True) -> dict[str, Any] | None:
        run_deadline = time.monotonic() + float(self._deadline_seconds)
        self._run_deadline_at = run_deadline
        try:
            status, body = self._transport.post_json(
                "/queue/claim",
                {
                    "executor_id": self._executor_id,
                    "capabilities": ["rendering.render"],
                    "lease_seconds": self._lease_seconds,
                },
            )
        except BaseException:
            self._run_deadline_at = None
            raise
        if status == 204:
            self._run_deadline_at = None
            return None
        if status != 200 or not isinstance(body, Mapping):
            self._run_deadline_at = None
            raise RenderExportWorkerError(f"render_export claim refused ({status})")
        claim = _claim(body)
        fence = {
            "attempt_id": claim.attempt_id,
            "lease_id": claim.lease_id,
            "status_version": claim.status_version,
        }
        next_control_check = time.monotonic()
        next_heartbeat = time.monotonic()
        next_cancel_check = time.monotonic()
        completion_started = False

        def heartbeat(payload: Mapping[str, Any]) -> None:
            nonlocal fence
            if not progress:
                return
            h_status, h_body = self._transport.post_json(
                f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/heartbeat",
                {
                    **fence,
                    "lease_seconds": self._lease_seconds,
                    "progress": dict(payload),
                },
            )
            if h_status != 200 or not isinstance(h_body, Mapping):
                raise RenderExportWorkerError(
                    f"render_export heartbeat refused ({h_status})"
                )
            attempt = h_body.get("attempt") or {}
            fence["status_version"] = int(attempt["status_version"])

        def cancelled() -> bool:
            detail_status, detail = self._transport.get_json(
                f"/projects/{claim.spec.get('project_slug', '')}/tasks/{claim.task_id}"
            )
            return detail_status == 200 and str((detail.get("task") or {}).get("status")) == "cancelled"

        def tick(*, force_heartbeat: bool = False) -> None:
            nonlocal next_control_check, next_heartbeat
            now = time.monotonic()
            if now >= run_deadline:
                raise RenderExportWorkerError("render_export global deadline exceeded")
            if self._stop_requested():
                raise RenderExportWorkerError("render_export worker is stopping")
            if now >= next_control_check:
                detail_status, detail = self._transport.get_json(
                    f"/projects/{claim.spec.get('project_slug', '')}/tasks/{claim.task_id}"
                )
                if detail_status == 200 and str((detail.get("task") or {}).get("status")) == "cancelled":
                    raise RenderExportWorkerError("render_export task was cancelled")
                next_control_check = now + 1.0
            if progress and (force_heartbeat or now >= next_heartbeat):
                heartbeat({"phase": "settle", "percent": 95})
                next_heartbeat = now + 5.0

        def check_settlement_control() -> None:
            nonlocal next_cancel_check
            now = time.monotonic()
            if now >= run_deadline:
                raise RenderExportWorkerError(
                    "render_export global deadline exceeded during settlement"
                )
            if self._stop_requested():
                raise RenderExportWorkerError("render_export worker is stopping")
            if now >= next_cancel_check:
                try:
                    detail_status, detail = self._transport.get_json(
                        f"/projects/{claim.spec.get('project_slug', '')}/tasks/{claim.task_id}"
                    )
                    if detail_status == 200 and str((detail.get("task") or {}).get("status")) == "cancelled":
                        raise RenderExportWorkerError("render_export task was cancelled")
                except RenderExportWorkerError:
                    raise
                except Exception:  # noqa: BLE001 - retry transport observation
                    pass
                next_cancel_check = now + 1.0

        def reconcile() -> tuple[str | None, dict[str, Any] | None]:
            try:
                detail_status, detail = self._transport.get_json(
                    f"/projects/{claim.spec.get('project_slug', '')}/tasks/{claim.task_id}"
                )
            except Exception:  # noqa: BLE001 - ambiguity is retried, never failed
                return None, None
            if detail_status != 200 or not isinstance(detail, Mapping):
                return None, None
            task_detail = detail.get("task")
            if not isinstance(task_detail, Mapping):
                return None, None
            return str(task_detail.get("status")), dict(detail)

        def settle_stopping() -> dict[str, Any]:
            """Reconcile and fenced-fail a claim interrupted by serve shutdown."""
            state, detail = reconcile()
            if state == "succeeded" and detail is not None:
                return detail
            if state is not None and state != "running" and detail is not None:
                return detail
            fail_status, fail_body = self._transport.post_json(
                f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/fail",
                {
                    **fence,
                    "error": {
                        "code": "render_export_worker_stopping",
                        "message": "render_export worker stopped during completion",
                        "retryable": True,
                    },
                },
                key=f"reigh.render.fail:{claim.task_id}:{claim.attempt_no}",
            )
            if fail_status == 200 and isinstance(fail_body, Mapping):
                return dict(fail_body)
            state, detail = reconcile()
            if detail is not None:
                return detail
            raise _CompletionUncertain(
                "render_export stopping claim could not be settled"
            )

        def complete_with_replay(
            *,
            manifest: Mapping[str, Any],
            output_path: Path,
            boundary: str,
            key: str,
        ) -> dict[str, Any]:
            uploader = getattr(self._transport, "post_multipart_file", None)
            if not callable(uploader):
                raise RenderExportWorkerError(
                    "render_export transport lacks bounded multipart-file upload"
                )
            last_error: BaseException | None = None
            while True:
                try:
                    complete_status, complete_body = uploader(
                        f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/complete",
                        manifest,
                        output_path,
                        boundary,
                        key=key,
                        on_chunk=lambda _sent: check_settlement_control(),
                    )
                    if complete_status == 200:
                        return dict(complete_body) if isinstance(complete_body, Mapping) else {}
                    if 400 <= complete_status < 500 and complete_status != 409:
                        raise _CompletionDefinitive(
                            f"render_export completion rejected ({complete_status})"
                        )
                    last_error = RenderExportWorkerError(
                        f"render_export completion refused ({complete_status})"
                    )
                except _CompletionDefinitive:
                    raise
                except Exception as exc:  # noqa: BLE001 - ACK may be ambiguous
                    last_error = exc
                state, detail = reconcile()
                if state == "succeeded" and detail is not None:
                    return detail
                if state is not None and state != "running":
                    raise _CompletionUncertain(
                        f"render_export completion settled as {state}"
                    ) from last_error
                if time.monotonic() >= run_deadline:
                    raise _CompletionUncertain(
                        "render_export completion acknowledgement remained ambiguous"
                    ) from last_error
                check_settlement_control()
                time.sleep(min(0.25, max(0.01, run_deadline - time.monotonic())))

        try:
            with TemporaryDirectory(prefix="astrid-render-export-") as tmp:
                manifest = self._run_child(
                    claim=claim,
                    staging_dir=Path(tmp),
                    heartbeat=heartbeat,
                    cancelled=cancelled,
                )
                outputs = manifest.get("outputs") if isinstance(manifest, Mapping) else None
                if not isinstance(outputs, list) or len(outputs) != 1:
                    raise RenderExportWorkerError("render_export must produce one MP4 output")
                output = outputs[0]
                relative = output.get("path") if isinstance(output, Mapping) else None
                if not isinstance(relative, str):
                    raise RenderExportWorkerError("render_export output path is invalid")
                output_path = (Path(tmp) / relative).resolve()
                output_path.relative_to(Path(tmp).resolve())
                digest, byte_size = _stream_digest(
                    output_path, on_chunk=lambda _size: check_settlement_control()
                )
                if digest != str(output.get("content_hash", "")).removeprefix("sha256:"):
                    raise RenderExportWorkerError("render_export output digest changed before upload")
                # Extend the lease once immediately before serializing the
                # completion body.  The resulting fence is immutable for the
                # whole upload and every idempotent replay.
                tick(force_heartbeat=True)
                boundary = "astrid-render-export"
                multipart_manifest = {
                    **fence,
                    "outputs": [
                        {
                            "key": "out0",
                            "is_primary": True,
                            "sha256": digest,
                            "size": byte_size,
                        }
                    ],
                }
                completion_started = True
                return complete_with_replay(
                    manifest=multipart_manifest,
                    output_path=output_path,
                    boundary=boundary,
                    key=f"reigh.render.complete:{claim.task_id}:{claim.attempt_no}",
                )
        except _CompletionUncertain:
            if self._stop_requested():
                return settle_stopping()
            raise
        except Exception as exc:  # noqa: BLE001 - worker boundary routes failure
            if completion_started and not isinstance(exc, _CompletionDefinitive):
                if self._stop_requested():
                    return settle_stopping()
                raise _CompletionUncertain(
                    "render_export completion acknowledgement was ambiguous"
                ) from exc
            fail_status, fail_body = self._transport.post_json(
                f"/tasks/{claim.task_id}/attempts/{claim.attempt_no}/fail",
                {
                    **fence,
                    "error": {
                        "code": "render_export_failed",
                        "message": str(exc)[:4000],
                        "retryable": False,
                    },
                },
                key=f"reigh.render.fail:{claim.task_id}:{claim.attempt_no}",
            )
            if fail_status != 200:
                raise RenderExportWorkerError(
                    f"render_export failure settlement refused ({fail_status})"
                ) from exc
            return dict(fail_body) if isinstance(fail_body, Mapping) else {}
        finally:
            self._run_deadline_at = None


class RenderExportServeWorker:
    """Serve-owned bounded poller for ``rendering.render`` tasks.

    The poller owns no database or filesystem authority.  It owns only its
    worker thread and asks the injected bridge transport to claim and settle
    one task at a time.  ``stop()`` is deliberately synchronous: the child
    process group is terminated before the caller closes the HTTP server or
    the composition's writer.
    """

    def __init__(
        self,
        transport: RenderExportWorkerTransport,
        *,
        projects_root: str | Path,
        executor_id: str,
        poll_interval_seconds: float = 1.0,
        lease_seconds: int = 1800,
        deadline_seconds: float = 30 * 60,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("render worker poll interval must be positive")
        self._stop_event = threading.Event()
        self._poll_interval_seconds = float(poll_interval_seconds)
        self._worker = RenderExportWorker(
            transport,
            projects_root=projects_root,
            executor_id=executor_id,
            lease_seconds=lease_seconds,
            deadline_seconds=deadline_seconds,
            stop_requested=self._stop_event.is_set,
        )
        self._thread = threading.Thread(
            target=self._run,
            name="astrid-render-export-worker",
            daemon=True,
        )
        self._health_lock = threading.Lock()
        self._last_error: str | None = None
        self._error_count = 0

    @property
    def thread(self) -> threading.Thread:
        """Expose the thread for bounded lifecycle assertions and diagnostics."""
        return self._thread

    @property
    def health(self) -> dict[str, Any]:
        """Return bounded, non-secret poller health for serve diagnostics."""
        with self._health_lock:
            return {
                "running": self._thread.is_alive(),
                "error_count": self._error_count,
                "last_error": self._last_error,
            }

    def start(self) -> None:
        self._thread.start()

    def stop(self, *, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("render worker stop timeout must be positive")
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout_seconds)
        if self._thread.is_alive():
            raise RenderExportWorkerError(
                "render_export worker did not stop within its bounded timeout"
            )

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._worker.run_once()
            except Exception as exc:  # noqa: BLE001 - retry after bounded worker failure
                message = str(exc)[:400]
                with self._health_lock:
                    self._error_count += 1
                    self._last_error = message or type(exc).__name__
                _LOG.warning("serve render worker iteration failed: %s", message)
            self._stop_event.wait(self._poll_interval_seconds)


__all__ = [
    "RenderExportClaim",
    "HttpRenderExportWorkerTransport",
    "RenderExportWorker",
    "RenderExportWorkerError",
    "RenderExportServeWorker",
    "RenderExportWorkerTransport",
]
