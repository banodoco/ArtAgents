"""Process-only helpers for cancellation of owned subprocesses."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class _ProcessInfo:
    pid: int
    ppid: int
    pgid: int
    birth: str


def _process_snapshot() -> dict[int, _ProcessInfo]:
    """Read a process census without invoking a shell."""
    ps = next(
        (candidate for candidate in ("/bin/ps", "/usr/bin/ps") if os.path.isfile(candidate)),
        "ps",
    )
    try:
        result = subprocess.run(
            [ps, "-axo", "pid=,ppid=,pgid=,lstart="],
            capture_output=True,
            text=True,
            check=False,
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    entries: dict[int, _ProcessInfo] = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 3)
        if len(fields) != 4:
            continue
        try:
            pid, ppid, pgid = (int(value) for value in fields[:3])
        except ValueError:
            continue
        entries[pid] = _ProcessInfo(pid, ppid, pgid, fields[3])
    return entries


def popen_owned_group(argv: list[str], **kwargs: Any) -> subprocess.Popen:
    """Launch a command as a fresh process-group/session leader."""
    options = dict(kwargs)
    options["start_new_session"] = True
    process = subprocess.Popen(argv, **options)
    process._astrid_process_group_id = process.pid  # type: ignore[attr-defined]
    info = _process_snapshot().get(process.pid)
    if info is not None:
        process._astrid_process_birth = info.birth  # type: ignore[attr-defined]
    return process


def _group_id(process: subprocess.Popen) -> int:
    return int(getattr(process, "_astrid_process_group_id", process.pid))


def _leader_birth(process: subprocess.Popen, snapshot: dict[int, _ProcessInfo]) -> str | None:
    birth = getattr(process, "_astrid_process_birth", None)
    if isinstance(birth, str):
        return birth
    info = snapshot.get(process.pid)
    if info is not None:
        birth = info.birth
        process._astrid_process_birth = birth  # type: ignore[attr-defined]
        return birth
    return None


def _snapshot_group(process: subprocess.Popen) -> dict[int, str]:
    """Capture current group members as ``pid -> birth token``."""
    group_id = _group_id(process)
    return {
        info.pid: info.birth
        for info in _process_snapshot().values()
        if info.pgid == group_id
    }


def _live_members(members: dict[int, str]) -> list[int]:
    """Return only PIDs whose birth token still matches a snapshot."""
    if not members:
        return []
    snapshot = _process_snapshot()
    return [
        pid
        for pid, birth in members.items()
        if (info := snapshot.get(pid)) is not None and info.birth == birth
    ]


def _group_members_owned(
    process: subprocess.Popen,
    known: dict[int, str],
    snapshot: dict[int, _ProcessInfo] | None = None,
) -> tuple[dict[int, str], bool]:
    """Refresh group members while rejecting a reused leader/group id."""
    snapshot = _process_snapshot() if snapshot is None else snapshot
    group_id = _group_id(process)
    birth = _leader_birth(process, snapshot)
    leader = snapshot.get(group_id)
    if leader is not None and birth is not None and leader.birth != birth:
        return {}, False
    if leader is not None and birth is None:
        if process.poll() is not None:
            return {}, False
        birth = leader.birth
        process._astrid_process_birth = birth  # type: ignore[attr-defined]
    members = {
        pid: info.birth
        for pid, info in snapshot.items()
        if info.pgid == group_id
    }
    known.update(members)
    return members, True


def group_exists(process: subprocess.Popen) -> bool:
    """Report direct-process liveness; group cleanup uses its own census."""
    return process.poll() is None


def signal_group(process: subprocess.Popen, sig: int) -> None:
    """Signal an owned group only while its leader identity is validated."""
    known: dict[int, str] = {}
    snapshot = _process_snapshot()
    members, owned = _group_members_owned(process, known, snapshot)
    if not owned:
        return
    leader = snapshot.get(_group_id(process))
    if process.poll() is None and leader is not None and hasattr(os, "killpg"):
        # Re-read the census immediately before signalling.  The first
        # snapshot establishes ownership, while this one closes the small
        # PID/PGID reuse window between census and killpg.
        latest = _process_snapshot()
        latest_leader = latest.get(_group_id(process))
        if (
            latest_leader is None
            or latest_leader.birth != leader.birth
            or process.poll() is not None
        ):
            return
        try:
            os.killpg(_group_id(process), sig)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass
    _signal_valid_group_members(process, members, sig, snapshot)


def terminate_group(process: subprocess.Popen, *, grace_seconds: float = 1.0) -> None:
    """Terminate an owned session, repeatedly discovering late descendants."""
    known: dict[int, str] = {}
    initial = _process_snapshot()
    members, owned = _group_members_owned(process, known, initial)
    if not owned:
        try:
            process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            pass
        return

    leader = initial.get(_group_id(process))
    if process.poll() is None and leader is not None and hasattr(os, "killpg"):
        # Revalidate the original leader immediately before killpg; an exited
        # leader's numeric PGID may already belong to another process group.
        latest = _process_snapshot()
        signal_snapshot = latest
        latest_leader = latest.get(_group_id(process))
        if (
            latest_leader is None
            or latest_leader.birth != leader.birth
            or process.poll() is not None
        ):
            latest_leader = None
        if latest_leader is None:
            members, owned = _group_members_owned(process, known, latest)
            if not owned:
                members = {}
        else:
            members = {
                info.pid: info.birth
                for info in latest.values()
                if info.pgid == _group_id(process)
            }
        try:
            if latest_leader is not None:
                os.killpg(_group_id(process), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        if members:
            _signal_valid_group_members(process, members, signal.SIGTERM, signal_snapshot)
    elif members:
        _signal_valid_group_members(process, members, signal.SIGTERM, initial)

    deadline = time.monotonic() + max(0.0, grace_seconds)
    while time.monotonic() < deadline:
        snapshot = _process_snapshot()
        members, owned = _group_members_owned(process, known, snapshot)
        if not owned or not members:
            break
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))

    kill_deadline = time.monotonic() + max(1.0, grace_seconds)
    while time.monotonic() < kill_deadline:
        snapshot = _process_snapshot()
        members, owned = _group_members_owned(process, known, snapshot)
        if not owned or not members:
            break
        _signal_valid_group_members(process, known, signal.SIGKILL, snapshot)
        time.sleep(0.02)

    try:
        process.wait(timeout=max(1.0, grace_seconds))
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()


def _signal_valid_group_members(
    process: subprocess.Popen,
    members: dict[int, str],
    sig: int,
    snapshot: dict[int, _ProcessInfo] | None = None,
) -> None:
    snapshot = _process_snapshot() if snapshot is None else snapshot
    group_id = _group_id(process)
    for pid, birth in tuple(members.items()):
        info = snapshot.get(pid)
        if info is None or info.birth != birth or info.pgid != group_id:
            continue
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _tree_members(
    process: subprocess.Popen,
    known: dict[int, str],
    snapshot: dict[int, _ProcessInfo] | None = None,
) -> dict[int, str]:
    """Refresh a process tree rooted at *process*, validating identities."""
    snapshot = _process_snapshot() if snapshot is None else snapshot
    root_birth = _leader_birth(process, snapshot)
    if root_birth is None:
        return {}
    root = snapshot.get(process.pid)
    if root is not None and root.birth != root_birth:
        return {}
    known[process.pid] = root_birth
    children: dict[int, list[_ProcessInfo]] = {}
    for info in snapshot.values():
        children.setdefault(info.ppid, []).append(info)
    pending = [process.pid, *known]
    while pending:
        parent = pending.pop()
        for info in children.get(parent, ()):
            prior = known.get(info.pid)
            if prior is not None and prior != info.birth:
                continue
            if prior is None:
                known[info.pid] = info.birth
            pending.append(info.pid)
    return {
        pid: birth
        for pid, birth in known.items()
        if (info := snapshot.get(pid)) is not None and info.birth == birth
    }


def terminate_tree(process: subprocess.Popen, *, grace_seconds: float = 1.0) -> None:
    """Terminate only *process* and descendants inside an inherited session."""
    known: dict[int, str] = {}
    _tree_members(process, known)
    _signal_valid_tree_members(process, known, signal.SIGTERM)
    deadline = time.monotonic() + max(0.0, grace_seconds)
    while time.monotonic() < deadline:
        snapshot = _process_snapshot()
        live = _tree_members(process, known, snapshot)
        if not live:
            break
        time.sleep(min(0.02, max(0.0, deadline - time.monotonic())))
    kill_deadline = time.monotonic() + max(1.0, grace_seconds)
    while time.monotonic() < kill_deadline:
        snapshot = _process_snapshot()
        live = _tree_members(process, known, snapshot)
        if not live:
            break
        _signal_valid_tree_members(process, known, signal.SIGKILL, snapshot)
        time.sleep(0.02)
    try:
        process.wait(timeout=max(1.0, grace_seconds))
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()


def _signal_valid_tree_members(
    process: subprocess.Popen,
    members: dict[int, str],
    sig: int,
    snapshot: dict[int, _ProcessInfo] | None = None,
) -> None:
    snapshot = _process_snapshot() if snapshot is None else snapshot
    for pid, birth in tuple(members.items()):
        info = snapshot.get(pid)
        if info is None or info.birth != birth:
            continue
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def release_group(process: subprocess.Popen) -> None:
    """Release a completed group, including descendants after leader exit."""
    terminate_group(process, grace_seconds=0.2)
