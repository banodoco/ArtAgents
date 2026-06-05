from __future__ import annotations

import io
import sys
from pathlib import Path

from astrid.core.runtime.log_capture import (
    DEFAULT_LOG_MAX_BYTES,
    RotatingTextLog,
    TeeWriter,
    log_max_bytes,
    open_run_log_capture,
    run_subprocess_with_capture,
)


def test_log_max_bytes_uses_default_and_env_override() -> None:
    assert log_max_bytes({}) == DEFAULT_LOG_MAX_BYTES
    assert log_max_bytes({"ASTRID_LOG_MAX_BYTES": "17"}) == 17
    assert log_max_bytes({"ASTRID_LOG_MAX_BYTES": "0"}) == DEFAULT_LOG_MAX_BYTES
    assert log_max_bytes({"ASTRID_LOG_MAX_BYTES": "not-an-int"}) == DEFAULT_LOG_MAX_BYTES


def test_rotating_text_log_rotates_existing_capped_file(tmp_path: Path) -> None:
    log_path = tmp_path / "stdout.log"
    log_path.write_text("old-data", encoding="utf-8")

    with RotatingTextLog(log_path, max_bytes=4) as log:
        log.write("new")

    assert (tmp_path / "stdout.log.old").read_text(encoding="utf-8") == "old-data"
    assert log_path.read_text(encoding="utf-8") == "new"


def test_rotating_text_log_rotates_before_write_after_soft_cap(tmp_path: Path) -> None:
    log_path = tmp_path / "stderr.log"

    with RotatingTextLog(log_path, max_bytes=5) as log:
        log.write("12345")
        log.write("678")

    assert (tmp_path / "stderr.log.old").read_text(encoding="utf-8") == "12345"
    assert log_path.read_text(encoding="utf-8") == "678"


def test_tee_writer_mirrors_partial_writes_to_live_stream_and_log(tmp_path: Path) -> None:
    live = io.StringIO()
    log_path = tmp_path / "stdout.log"

    with RotatingTextLog(log_path, max_bytes=100) as log:
        tee = TeeWriter(live, log)
        assert tee.write("partial") == len("partial")
        tee.write("-line\n")
        tee.flush()

    assert live.getvalue() == "partial-line\n"
    assert log_path.read_text(encoding="utf-8") == "partial-line\n"


def test_open_run_log_capture_creates_stdout_and_stderr_logs(tmp_path: Path) -> None:
    with open_run_log_capture(tmp_path, max_bytes=100) as logs:
        logs.stdout.write("out")
        logs.stderr.write("err")

    assert (tmp_path / "logs" / "stdout.log").read_text(encoding="utf-8") == "out"
    assert (tmp_path / "logs" / "stderr.log").read_text(encoding="utf-8") == "err"


def test_run_subprocess_with_capture_drains_stdout_and_stderr_concurrently(tmp_path: Path) -> None:
    stdout_live = io.StringIO()
    stderr_live = io.StringIO()
    stdout_log = tmp_path / "stdout.log"
    stderr_log = tmp_path / "stderr.log"
    child_code = (
        "import sys\n"
        "chunk = 'x' * 8192\n"
        "for index in range(32):\n"
        "    sys.stdout.write(f'OUT-{index}-' + chunk + '\\n')\n"
        "    sys.stdout.flush()\n"
        "    sys.stderr.write(f'ERR-{index}-' + chunk + '\\n')\n"
        "    sys.stderr.flush()\n"
    )

    with RotatingTextLog(stdout_log, max_bytes=1024 * 1024) as out_log, RotatingTextLog(
        stderr_log, max_bytes=1024 * 1024
    ) as err_log:
        returncode = run_subprocess_with_capture(
            [sys.executable, "-c", child_code],
            stdout_log=out_log,
            stderr_log=err_log,
            live_stdout=stdout_live,
            live_stderr=stderr_live,
        )

    assert returncode == 0
    assert "OUT-0-" in stdout_live.getvalue()
    assert "OUT-31-" in stdout_live.getvalue()
    assert "ERR-0-" in stderr_live.getvalue()
    assert "ERR-31-" in stderr_live.getvalue()
    assert stdout_log.read_text(encoding="utf-8") == stdout_live.getvalue()
    assert stderr_log.read_text(encoding="utf-8") == stderr_live.getvalue()

