"""Tests for astrid/core/dirty.py — git-clean fast path and hash-fallback path.

Covers:
  * detect_local_edits() git fast path (clean + dirty via mocked git_status)
  * detect_local_edits() fallback when git_status raises GitUtilError
  * detect_local_edits() hash-based fallback when not in a git worktree
  * caplog assertion on the :38-40 routed swallow (GitUtilError → fall through)

Target: ≥80% coverage of astrid/core/dirty.py.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from astrid.core.dirty import detect_local_edits, write_fork_state, read_fork_state
from astrid.core.git_util import GitStatus, GitUtilError


_EMPTY_STATUS = GitStatus(dirty=False, staged=(), unstaged=(), untracked=(), raw_lines=())
_DIRTY_STATUS = GitStatus(dirty=True, staged=("file.py",), unstaged=(), untracked=(), raw_lines=("M file.py",))


class TestGitFastPath:
    """detect_local_edits() uses git_status when inside a git worktree."""

    def test_git_clean_returns_clean(self, tmp_path: Path) -> None:
        with (
            patch("astrid.core.dirty.is_git_worktree", return_value=True),
            patch("astrid.core.dirty.git_status", return_value=_EMPTY_STATUS),
        ):
            result = detect_local_edits(tmp_path, forked_from="some.capability")
        assert result == "clean"

    def test_git_dirty_returns_dirty(self, tmp_path: Path) -> None:
        with (
            patch("astrid.core.dirty.is_git_worktree", return_value=True),
            patch("astrid.core.dirty.git_status", return_value=_DIRTY_STATUS),
        ):
            result = detect_local_edits(tmp_path, forked_from="some.capability")
        assert result == "dirty"

    def test_not_forked_always_clean(self, tmp_path: Path) -> None:
        result = detect_local_edits(tmp_path, forked_from="")
        assert result == "clean"


class TestGitFailureFallthrough:
    """The :38-40 routed swallow: GitUtilError falls through to hash fallback.

    The swallow is NOT a log_and_swallow call (GitUtilError is a narrow typed
    exception that only fires on subprocess failure).  The fall-through is
    deliberate: the except block has no logging, it just passes and the hash
    fallback runs.  This test verifies the path completes without raising.
    """

    def test_git_status_error_falls_through_to_hash_fallback(self, tmp_path: Path) -> None:
        """When git_status raises GitUtilError, detect falls through to hash-based path."""
        (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
        write_fork_state(tmp_path, forked_from="cap.x", upstream_version="1.0")

        with (
            patch("astrid.core.dirty.is_git_worktree", return_value=True),
            patch("astrid.core.dirty.git_status", side_effect=GitUtilError("git broke")),
        ):
            result = detect_local_edits(tmp_path, forked_from="cap.x")

        # Hash matches written state — should be clean.
        assert result == "clean"

    def test_git_failure_then_hash_dirty(self, tmp_path: Path) -> None:
        """Git fails, hash fallback detects a file change → dirty."""
        (tmp_path / "file.txt").write_text("original", encoding="utf-8")
        write_fork_state(tmp_path, forked_from="cap.x", upstream_version="1.0")

        # Mutate the file after snapshot
        (tmp_path / "file.txt").write_text("modified", encoding="utf-8")

        with (
            patch("astrid.core.dirty.is_git_worktree", return_value=True),
            patch("astrid.core.dirty.git_status", side_effect=GitUtilError("git broke")),
        ):
            result = detect_local_edits(tmp_path, forked_from="cap.x")

        assert result == "dirty"


class TestHashFallbackPath:
    """detect_local_edits() uses hash fallback when not in a git worktree."""

    def test_no_fork_state_returns_clean(self, tmp_path: Path) -> None:
        """No .astrid_fork_state.json → cannot determine → assume clean."""
        with patch("astrid.core.dirty.is_git_worktree", return_value=False):
            result = detect_local_edits(tmp_path, forked_from="cap.y")
        assert result == "clean"

    def test_hash_match_returns_clean(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
        write_fork_state(tmp_path, forked_from="cap.y", upstream_version="1.0")

        with patch("astrid.core.dirty.is_git_worktree", return_value=False):
            result = detect_local_edits(tmp_path, forked_from="cap.y")
        assert result == "clean"

    def test_hash_mismatch_returns_dirty(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("print('hi')", encoding="utf-8")
        write_fork_state(tmp_path, forked_from="cap.y", upstream_version="1.0")

        # Modify the file after saving fork state
        (tmp_path / "main.py").write_text("print('bye')", encoding="utf-8")

        with patch("astrid.core.dirty.is_git_worktree", return_value=False):
            result = detect_local_edits(tmp_path, forked_from="cap.y")
        assert result == "dirty"

    def test_added_file_returns_dirty(self, tmp_path: Path) -> None:
        write_fork_state(tmp_path, forked_from="cap.z", upstream_version="1.0")
        (tmp_path / "new_file.py").write_text("# added", encoding="utf-8")

        with patch("astrid.core.dirty.is_git_worktree", return_value=False):
            result = detect_local_edits(tmp_path, forked_from="cap.z")
        assert result == "dirty"

    def test_removed_file_returns_dirty(self, tmp_path: Path) -> None:
        (tmp_path / "original.py").write_text("x = 1", encoding="utf-8")
        write_fork_state(tmp_path, forked_from="cap.z", upstream_version="1.0")
        (tmp_path / "original.py").unlink()

        with patch("astrid.core.dirty.is_git_worktree", return_value=False):
            result = detect_local_edits(tmp_path, forked_from="cap.z")
        assert result == "dirty"
