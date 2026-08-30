"""Process-only helpers for cancellation of an owned subprocess session."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from typing import Any


def popen_owned_group(argv: list[str], **kwargs: Any) -> subprocess.Popen:
    """Launch a command as a fresh process-group/session leader."""
    options = dict(kwargs)
    options["start_new_session"] = True
    process = subprocess.Popen(argv, **options)
    process._astrid_process_group_id = process.pid  # type: ignore[attr-defined]
    return process


def _group_id(process: subprocess.Popen) -> int:
    return int(getattr(process, "_astrid_process_group_id", process.pid))


def _snapshot_group(process: subprocess.Popen) -> dict[int, str]:
    """Capture member birth tokens before the session leader can disappear."""
    result = subprocess.run(
        ["ps", "-axo", "pid=,pgid=,lstart="],
        capture_output=True,
        text=True,
        check=False,
    )
    members: dict[int, str] = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) == 3:
            try:
                pid, pgid = int(fields[0]), int(fields[1])
            except ValueError:
                continue
            if pgid == _group_id(process):
                members[pid] = fields[2]
    return members


def _live_members(members: dict[int, str]) -> list[int]:
    """Return only PIDs whose birth token still matches the snapshot."""
    if not members:
        return []
    result = subprocess.run(
        ["ps", "-axo", "pid=,lstart="],
        capture_output=True,
        text=True,
        check=False,
    )
    live: list[int] = []
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) == 2:
            try:
                pid = int(fields[0])
            except ValueError:
                continue
            if members.get(pid) == fields[1]:
                live.append(pid)
    return live


def group_exists(process: subprocess.Popen) -> bool:
    """Report direct-process liveness; descendant checks use identity tokens."""
    return process.poll() is None


def signal_group(process: subprocess.Popen, sig: int) -> None:
    """Signal the group only while its original leader is still alive."""
    if process.poll() is None and hasattr(os, "killpg"):
        try:
            os.killpg(_group_id(process), sig)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    if process.poll() is None:
        try:
            process.send_signal(sig)
        except OSError:
            pass


def terminate_group(process: subprocess.Popen, *, grace_seconds: float = 1.0) -> None:
    """Terminate the session without signaling a reused leader PID."""
    members = _snapshot_group(process)
    signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + max(0.0, grace_seconds)
    while _live_members(members) and time.monotonic() < deadline:
        time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
    live = _live_members(members)
    if live:
        for pid in live:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        kill_deadline = time.monotonic() + max(1.0, grace_seconds)
        while _live_members(members) and time.monotonic() < kill_deadline:
            time.sleep(0.01)
    try:
        process.wait(timeout=max(1.0, grace_seconds))
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()


def release_group(process: subprocess.Popen) -> None:
    """Release a completed group, or contain it if an exception interrupted launch."""
    if process.poll() is None:
        terminate_group(process, grace_seconds=0.2)
