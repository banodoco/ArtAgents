"""Cross-process ownership for Remotion's shared generated state.

The lock is deliberately non-recursive.  Callers that already own it must
route nested writer work through the explicit held-lock path instead of
acquiring it again.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator

from astrid.core.foundation.paths import REPO_ROOT

try:
    import fcntl
except ImportError:  # pragma: no cover - filelock is the Windows path.
    fcntl = None  # type: ignore[assignment]

try:
    from filelock import FileLock, Timeout
except ImportError:  # pragma: no cover - exercised only without optional dep.
    FileLock = None  # type: ignore[assignment]

    class Timeout(Exception):
        pass


REMOTION_LOCK_PATH = REPO_ROOT / "remotion" / ".astrid-registry.lock"
REMOTION_LOCK_OWNER_ENV = "ASTRID_REMOTION_LOCK_OWNER"

_LOCAL_LOCK_PATH: ContextVar[str | None] = ContextVar(
    "remotion_render_lock_path",
    default=None,
)


class _FcntlLock:
    """Small ``filelock``-compatible fallback mirroring the asset cache."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle: Any | None = None

    def acquire(self, timeout: float | None = None) -> _FcntlLock:
        if fcntl is None:  # pragma: no cover - requires Windows without filelock.
            raise RuntimeError("Remotion rendering requires filelock or fcntl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        deadline = None if timeout is None or timeout < 0 else time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError as exc:
                if timeout == 0 or (
                    deadline is not None and time.monotonic() >= deadline
                ):
                    self._handle.close()
                    self._handle = None
                    raise Timeout(str(self.path)) from exc
                time.sleep(0.05)

    def release(self) -> None:
        if self._handle is None:
            return
        if fcntl is None:  # pragma: no cover - guarded by acquire().
            raise RuntimeError("Remotion rendering requires filelock or fcntl")
        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        self._handle.close()
        self._handle = None


def _lock_for(path: Path) -> Any:
    """Return a cross-process lock for the exact path supplied."""

    if FileLock is not None:
        return FileLock(str(path))
    return _FcntlLock(path)


def _resolved_lock_path() -> Path:
    return Path(REMOTION_LOCK_PATH).resolve(strict=False)


def _inherited_lock_path() -> str | None:
    """Return the inherited lock path only for a direct child of its owner."""

    raw_owner = os.environ.get(REMOTION_LOCK_OWNER_ENV)
    if not raw_owner:
        return None
    parent_pid, separator, raw_path = raw_owner.partition(":")
    if not separator or not parent_pid.isdigit() or int(parent_pid) != os.getppid():
        return None
    inherited_path = str(Path(raw_path).resolve(strict=False))
    if inherited_path != str(_resolved_lock_path()):
        return None
    return inherited_path


def remotion_render_lock_held() -> bool:
    """Whether this context, or its direct parent process, owns the lock."""

    return _LOCAL_LOCK_PATH.get() is not None or _inherited_lock_path() is not None


def remotion_render_lock_child_env() -> dict[str, str]:
    """Return the marker that lets one direct child use the held writer path."""

    lock_path = _LOCAL_LOCK_PATH.get() or _inherited_lock_path()
    if lock_path is None:
        raise RuntimeError("cannot delegate Remotion writer work without owning the lock")
    return {REMOTION_LOCK_OWNER_ENV: f"{os.getpid()}:{lock_path}"}


@contextmanager
def remotion_render_lock() -> Iterator[None]:
    """Hold the one non-recursive Remotion registry/render file lock."""

    if remotion_render_lock_held():
        raise RuntimeError("Remotion render lock is non-recursive")

    lock_path = _resolved_lock_path()
    lock = _lock_for(lock_path)
    lock.acquire()
    token = _LOCAL_LOCK_PATH.set(str(lock_path))
    try:
        yield
    finally:
        try:
            lock.release()
        finally:
            _LOCAL_LOCK_PATH.reset(token)


__all__ = [
    "REMOTION_LOCK_OWNER_ENV",
    "REMOTION_LOCK_PATH",
    "remotion_render_lock",
    "remotion_render_lock_child_env",
    "remotion_render_lock_held",
]
