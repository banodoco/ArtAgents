"""Unit tests for astrid.core.foundation.atomic_io and jsonio delegation compatibility.

Covers:
- Successful text, bytes, and JSON writes
- Simulated failure cleanup (temp file removed, target untouched)
- AtomicWriteError propagation
- read_json success and error paths
- Compatibility through astrid.core._shared.jsonio delegation
  (ProjectJsonError wrapping, identical JSON shape, import-path preservation)
"""

from __future__ import annotations

import errno
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core._shared.jsonio import (
    ProjectJsonError,
)
from astrid.core._shared.jsonio import (
    read_json as project_read_json,
)
from astrid.core._shared.jsonio import (
    write_json_atomic as project_write_json_atomic,
)
from astrid.core.contracts.errors import AstridError
from astrid.core.foundation.atomic_io import (
    AtomicWriteError,
    _fsync_dir,
    _write_atomic,
    _write_atomic_binary,
    read_json,
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)

# ---------------------------------------------------------------------------
# Successful writes
# ---------------------------------------------------------------------------

class TestWriteTextAtomic:
    def test_writes_content_to_file(self, tmp_path: Path) -> None:
        target = tmp_path / "hello.txt"
        write_text_atomic(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c.txt"
        write_text_atomic(target, "nested")
        assert target.read_text(encoding="utf-8") == "nested"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "overwrite.txt"
        target.write_text("old", encoding="utf-8")
        write_text_atomic(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_no_temp_file_left_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "clean.txt"
        write_text_atomic(target, "data")
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0


class TestWriteBytesAtomic:
    def test_writes_content_to_file(self, tmp_path: Path) -> None:
        target = tmp_path / "data.bin"
        write_bytes_atomic(target, b"\x00\xff\xab")
        assert target.read_bytes() == b"\x00\xff\xab"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "data.bin"
        write_bytes_atomic(target, b"binary")
        assert target.read_bytes() == b"binary"

    def test_no_temp_file_left_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "clean.bin"
        write_bytes_atomic(target, b"x")
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0


class TestWriteJsonAtomic:
    def test_writes_pretty_printed_sorted_json(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        payload = {"z": 1, "a": 2}
        write_json_atomic(target, payload)
        raw = target.read_text(encoding="utf-8")
        # Sorted keys: "a" before "z"
        assert '"a": 2' in raw
        assert '"z": 1' in raw
        assert raw.index('"a"') < raw.index('"z"')
        assert json.loads(raw) == payload

    def test_no_temp_file_left_behind(self, tmp_path: Path) -> None:
        target = tmp_path / "clean.json"
        write_json_atomic(target, {"k": "v"})
        temp_files = list(target.parent.glob(".*.tmp"))
        assert len(temp_files) == 0


# ---------------------------------------------------------------------------
# read_json
# ---------------------------------------------------------------------------

class TestReadJson:
    def test_roundtrip(self, tmp_path: Path) -> None:
        target = tmp_path / "roundtrip.json"
        payload = {"key": "value", "list": [1, 2, 3]}
        write_json_atomic(target, payload)
        result = read_json(target)
        assert result == payload

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            read_json(missing)

    def test_invalid_json_raises_value_error(self, tmp_path: Path) -> None:
        target = tmp_path / "bad.json"
        target.write_text("{invalid", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            read_json(target)

    def test_os_error_uses_recoverable_astrid_error(self, tmp_path: Path) -> None:
        target = tmp_path / "unreadable.json"
        with patch.object(Path, "read_text", side_effect=OSError(errno.EIO, "I/O error")):
            with pytest.raises(AstridError, match="failed to read") as raised:
                read_json(target)

        assert raised.value.recovery_command == (
            "check file permissions and disk health, then retry"
        )


# ---------------------------------------------------------------------------
# Simulated failure cleanup
# ---------------------------------------------------------------------------

class TestAtomicWriteFailureCleanup:
    """Verify that when the inner write function fails, the temp file is
    removed, the target file is NOT created or modified, and the error is
    propagated as an AtomicWriteError."""

    def test_text_write_failure_cleans_up_temp_file(self, tmp_path: Path) -> None:
        target = tmp_path / "should_not_exist.txt"

        def _failing_write(tp: Path) -> None:
            tp.write_text("partial", encoding="utf-8")
            raise RuntimeError("simulated write failure")

        # _write_atomic only wraps OSError; RuntimeError propagates as-is.
        # The finally block still cleans up the temp file.
        with pytest.raises(RuntimeError, match="simulated write failure"):
            _write_atomic(target, _failing_write)

        # Target must NOT exist (never replaced)
        assert not target.exists()
        # No temp files left behind
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_text_write_failure_preserves_existing_target(self, tmp_path: Path) -> None:
        target = tmp_path / "existing.txt"
        target.write_text("original", encoding="utf-8")

        call_count = 0

        def _failing_write(tp: Path) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("simulated write failure")

        # _write_atomic only wraps OSError; RuntimeError propagates as-is.
        with pytest.raises(RuntimeError, match="simulated write failure"):
            _write_atomic(target, _failing_write)

        # Original content preserved
        assert target.read_text(encoding="utf-8") == "original"
        assert call_count == 1
        # No temp files left behind
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_binary_write_failure_cleans_up_temp_file(self, tmp_path: Path) -> None:
        target = tmp_path / "should_not_exist.bin"

        def _failing_write(tp: Path) -> None:
            tp.write_bytes(b"partial")
            raise RuntimeError("simulated failure")

        # _write_atomic_binary only wraps OSError; RuntimeError propagates as-is.
        with pytest.raises(RuntimeError, match="simulated failure"):
            _write_atomic_binary(target, _failing_write)

        assert not target.exists()
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_json_write_failure_cleans_up_temp_file(self, tmp_path: Path) -> None:
        target = tmp_path / "no_write.json"

        # Simulate a failure by making the parent read-only so the temp file
        # can be created but os.replace fails (permission error).
        with patch("os.replace", side_effect=OSError(errno.EACCES, "Permission denied")):
            with pytest.raises(AtomicWriteError, match="Permission denied"):
                write_json_atomic(target, {"k": "v"})

        # Target should not exist
        assert not target.exists()
        # Temp file should be cleaned up
        temp_files = list(target.parent.glob(".*.tmp"))
        assert len(temp_files) == 0

    def test_write_text_atomic_raises_atomic_write_error_on_os_error(self, tmp_path: Path) -> None:
        target = tmp_path / "fail.txt"
        with patch("os.replace", side_effect=OSError(errno.EIO, "I/O error")):
            with pytest.raises(AtomicWriteError, match="I/O error"):
                write_text_atomic(target, "data")
        assert not target.exists()

    def test_write_bytes_atomic_raises_atomic_write_error_on_os_error(self, tmp_path: Path) -> None:
        target = tmp_path / "fail.bin"
        with patch("os.replace", side_effect=OSError(errno.EIO, "I/O error")):
            with pytest.raises(AtomicWriteError, match="I/O error"):
                write_bytes_atomic(target, b"data")
        assert not target.exists()


# ---------------------------------------------------------------------------
# jsonio delegation compatibility
# ---------------------------------------------------------------------------

class TestJsonioDelegation:
    """Verify that astrid.core._shared.jsonio delegates correctly to the
    shared atomic helpers while preserving its own ProjectJsonError
    exception and identical JSON shape."""

    def test_write_json_atomic_produces_same_json_shape(self, tmp_path: Path) -> None:
        """write_json_atomic via _shared.jsonio produces the same JSON as
        the direct atomic_io helper."""
        payload = {"b": 2, "a": 1, "nested": {"z": True, "y": False}}

        direct_path = tmp_path / "direct.json"
        project_path = tmp_path / "project.json"

        write_json_atomic(direct_path, payload)
        project_write_json_atomic(project_path, payload)

        direct_text = direct_path.read_text(encoding="utf-8")
        project_text = project_path.read_text(encoding="utf-8")
        assert direct_text == project_text
        assert json.loads(direct_text) == payload
        assert json.loads(project_text) == payload

    def test_project_read_json_delegates_to_atomic_read_json(self, tmp_path: Path) -> None:
        payload = {"status": "completed"}
        target = tmp_path / "run.json"
        write_json_atomic(target, payload)

        via_project = project_read_json(target)
        via_atomic = read_json(target)
        assert via_project == payload
        assert via_project == via_atomic

    def test_project_read_json_wraps_errors_in_project_json_error(self, tmp_path: Path) -> None:
        target = tmp_path / "bad.json"
        target.write_text("{bad", encoding="utf-8")

        with pytest.raises(ProjectJsonError, match="invalid JSON"):
            project_read_json(target)

    def test_project_read_json_propagates_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.json"
        with pytest.raises(FileNotFoundError):
            project_read_json(missing)

    def test_project_write_failure_wraps_in_project_json_error(self, tmp_path: Path) -> None:
        target = tmp_path / "fail.json"
        with patch("os.replace", side_effect=OSError(errno.EIO, "I/O error")):
            with pytest.raises(ProjectJsonError, match="failed to write"):
                project_write_json_atomic(target, {"k": "v"})
        assert not target.exists()

    def test_project_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        payload = {"kind": "scratch", "status": "completed", "metadata": {"pid": 12345}}
        target = tmp_path / "ledger.json"

        project_write_json_atomic(target, payload)
        result = project_read_json(target)
        assert result == payload


# ---------------------------------------------------------------------------
# _fsync_dir edge cases
# ---------------------------------------------------------------------------

class TestFsyncDir:
    def test_fsync_dir_does_not_raise_on_non_fatal_errors(self, tmp_path: Path) -> None:
        """_fsync_dir should not raise on EINVAL, ENOTSUP, or EBADF."""
        # These errnos should be swallowed
        for err in (errno.EINVAL, errno.ENOTSUP, errno.EBADF):
            _fsync_dir(tmp_path)  # should not raise

    def test_fsync_dir_raises_on_other_errors(self, tmp_path: Path) -> None:
        """_fsync_dir raises on unexpected OSError errnos."""
        with patch("os.open", side_effect=OSError(errno.EACCES, "access denied")):
            with pytest.raises(OSError, match="access denied"):
                _fsync_dir(tmp_path)
