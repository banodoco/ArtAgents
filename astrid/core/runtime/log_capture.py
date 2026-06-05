"""Shared stdout/stderr capture helpers for project runs."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Mapping, Sequence

ASTRID_LOG_MAX_BYTES = "ASTRID_LOG_MAX_BYTES"
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024


class RotatingTextLog:
    """Append text to a UTF-8 log file with a soft byte cap."""

    def __init__(self, path: str | Path, *, max_bytes: int | None = None) -> None:
        self.path = Path(path)
        self.max_bytes = log_max_bytes() if max_bytes is None else max_bytes
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_if_capped()
        self._fh = self.path.open("a", encoding="utf-8", errors="replace")

    def write(self, text: str) -> int:
        chunk = str(text)
        with self._lock:
            self._rotate_if_capped()
            written = self._fh.write(chunk)
            self._fh.flush()
            return written

    def flush(self) -> None:
        with self._lock:
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            self._fh.close()

    def __enter__(self) -> "RotatingTextLog":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def _rotate_if_capped(self) -> None:
        if self.max_bytes <= 0 or not self.path.exists():
            return
        try:
            size = self.path.stat().st_size
        except OSError:
            return
        if size < self.max_bytes:
            return
        if hasattr(self, "_fh") and not self._fh.closed:
            self._fh.close()
        old_path = self.path.with_name(f"{self.path.name}.old")
        old_path.unlink(missing_ok=True)
        self.path.replace(old_path)
        if hasattr(self, "_fh"):
            self._fh = self.path.open("a", encoding="utf-8", errors="replace")


class TeeWriter:
    """Text writer that mirrors output to a live stream and an optional log."""

    def __init__(
        self,
        live_stream: IO[str],
        log: RotatingTextLog | IO[str] | None = None,
    ) -> None:
        self.live_stream = live_stream
        self.log = log

    def write(self, text: str) -> int:
        chunk = str(text)
        written = self.live_stream.write(chunk)
        self.live_stream.flush()
        if self.log is not None:
            self.log.write(chunk)
            self.log.flush()
        return len(chunk) if written is None else written

    def flush(self) -> None:
        self.live_stream.flush()
        if self.log is not None:
            self.log.flush()


@dataclass
class RunLogCapture:
    """Open stdout/stderr log writers for a project run directory."""

    run_root: Path
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        logs_dir = self.run_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.stdout = RotatingTextLog(logs_dir / "stdout.log", max_bytes=self.max_bytes)
        self.stderr = RotatingTextLog(logs_dir / "stderr.log", max_bytes=self.max_bytes)

    def __enter__(self) -> "RunLogCapture":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def close(self) -> None:
        self.stdout.close()
        self.stderr.close()


def open_run_log_capture(
    run_root: str | Path,
    *,
    max_bytes: int | None = None,
) -> RunLogCapture:
    return RunLogCapture(Path(run_root), max_bytes=max_bytes)


def run_subprocess_with_capture(
    argv: Sequence[str],
    *,
    cwd: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    stdout_log: RotatingTextLog | IO[str] | None = None,
    stderr_log: RotatingTextLog | IO[str] | None = None,
    live_stdout: IO[str] | None = None,
    live_stderr: IO[str] | None = None,
) -> int:
    """Run a subprocess while concurrently teeing stdout and stderr."""

    process = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stdout_target = TeeWriter(live_stdout or sys.stdout, stdout_log)
    stderr_target = TeeWriter(live_stderr or sys.stderr, stderr_log)
    threads = (
        threading.Thread(
            target=_drain_pipe,
            args=(process.stdout, stdout_target),
            daemon=True,
        ),
        threading.Thread(
            target=_drain_pipe,
            args=(process.stderr, stderr_target),
            daemon=True,
        ),
    )
    for thread in threads:
        thread.start()
    returncode = process.wait()
    for thread in threads:
        thread.join()
    return returncode


def log_max_bytes(env: Mapping[str, str] | None = None) -> int:
    value = (os.environ if env is None else env).get(ASTRID_LOG_MAX_BYTES)
    if value is None or not value.strip():
        return DEFAULT_LOG_MAX_BYTES
    try:
        parsed = int(value)
    except ValueError:
        return DEFAULT_LOG_MAX_BYTES
    return parsed if parsed > 0 else DEFAULT_LOG_MAX_BYTES


def _drain_pipe(pipe: IO[str] | None, target: TeeWriter) -> None:
    if pipe is None:
        return
    try:
        while True:
            chunk = pipe.readline()
            if chunk == "":
                break
            target.write(chunk)
    finally:
        pipe.close()
        target.flush()
