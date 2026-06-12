"""Focused CAS import compatibility tests.

Proves both ``astrid.core.io.cas`` and ``astrid.core.task.cas`` import
paths expose the expected public helpers after the T1 module move.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# ---------------------------------------------------------------------------
# All three import paths under test
# ---------------------------------------------------------------------------
import astrid.core.io.cas as io_cas
import astrid.core.task.cas as task_cas
import astrid.core.io as io_pkg

_EXPECTED_HELPERS = ("cas_dir", "cas_path", "hash_file", "intern", "link_into_produces")


# ---------------------------------------------------------------------------
# Symbol presence
# ---------------------------------------------------------------------------

def test_io_cas_exports_all_helpers() -> None:
    """Every expected helper is importable from ``astrid.core.io.cas``."""
    for name in _EXPECTED_HELPERS:
        assert hasattr(io_cas, name), f"astrid.core.io.cas missing {name}"


def test_task_cas_exports_all_helpers() -> None:
    """Every expected helper is importable from ``astrid.core.task.cas``."""
    for name in _EXPECTED_HELPERS:
        assert hasattr(task_cas, name), f"astrid.core.task.cas missing {name}"


def test_io_pkg_exports_all_helpers() -> None:
    """Every expected helper is importable from ``astrid.core.io`` (convenience re-export)."""
    for name in _EXPECTED_HELPERS:
        assert hasattr(io_pkg, name), f"astrid.core.io missing {name}"


# ---------------------------------------------------------------------------
# Identity — task.cas must be a transparent shim, not a fork
# ---------------------------------------------------------------------------

def test_task_cas_helpers_are_same_objects_as_io_cas() -> None:
    """``astrid.core.task.cas`` re-exports the exact same function objects."""
    for name in _EXPECTED_HELPERS:
        io_obj = getattr(io_cas, name)
        task_obj = getattr(task_cas, name)
        assert io_obj is task_obj, (
            f"{name}: astrid.core.io.cas.{name} is not astrid.core.task.cas.{name}"
        )


def test_io_pkg_helpers_are_same_objects_as_io_cas() -> None:
    """``astrid.core.io`` re-exports the exact same function objects as ``io.cas``."""
    for name in _EXPECTED_HELPERS:
        io_obj = getattr(io_cas, name)
        pkg_obj = getattr(io_pkg, name)
        assert io_obj is pkg_obj, (
            f"{name}: astrid.core.io.cas.{name} is not astrid.core.io.{name}"
        )


# ---------------------------------------------------------------------------
# Smoke: call through each path to prove the shim isn't just symbols
# ---------------------------------------------------------------------------

def test_cas_dir_through_task_cas(tmp_path: Path) -> None:
    assert task_cas.cas_dir(tmp_path) == tmp_path / ".cas"


def test_cas_path_through_task_cas(tmp_path: Path) -> None:
    sha = "a" * 64
    assert task_cas.cas_path(tmp_path, sha) == tmp_path / ".cas" / sha


def test_hash_file_through_task_cas(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"smoke")
    assert task_cas.hash_file(p) == hashlib.sha256(b"smoke").hexdigest()


def test_intern_through_task_cas(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    src = project_dir / "a.bin"
    payload = b"intern via task.cas"
    src.write_bytes(payload)

    result = task_cas.intern(project_dir, src)
    sha = hashlib.sha256(payload).hexdigest()
    assert result == task_cas.cas_path(project_dir, sha)
    assert result.read_bytes() == payload


def test_link_into_produces_through_task_cas(tmp_path: Path) -> None:
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    src = project_dir / "a.bin"
    src.write_bytes(b"link smoke")
    cas_target = task_cas.intern(project_dir, src)

    produces_dir = tmp_path / "produces"
    produces_dir.mkdir()
    link = produces_dir / "a.bin"
    task_cas.link_into_produces(cas_target, link)
    assert link.is_symlink()
    assert link.resolve() == cas_target.resolve()


# ---------------------------------------------------------------------------
# Smoke through io_pkg convenience path
# ---------------------------------------------------------------------------

def test_hash_file_through_io_pkg(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"io pkg smoke")
    assert io_pkg.hash_file(p) == hashlib.sha256(b"io pkg smoke").hexdigest()
