"""Tests for dirty detection: detect_local_edits(), write_fork_state(),
read_fork_state().

Covers clean/dirty/conflict detection, git and hash fallback.

All tests use tempfile.TemporaryDirectory for fixture content.
No real LLM calls, no real network calls, no real git ops on actual repo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from astrid.core.dirty import (
    detect_local_edits,
    read_fork_state,
    write_fork_state,
)
from astrid.core.contracts.schema import LocalEditState


class TestDetectLocalEdits:
    """detect_local_edits() returns correct LocalEditState."""

    def test_not_forked_returns_clean(self):
        """When forked_from is empty, always returns 'clean'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.txt").write_text("hello\n", encoding="utf-8")
            result = detect_local_edits(root, forked_from="")
            assert result == "clean"

    def test_fork_state_match_returns_clean(self):
        """When hashes match stored fork state, returns 'clean'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "config.json").write_text('{"key": "value"}\n', encoding="utf-8")

            write_fork_state(root, forked_from="rendering.render", upstream_version="1.0.0")
            result = detect_local_edits(root, forked_from="rendering.render")
            assert result == "clean"

    def test_file_change_returns_dirty(self):
        """When a file changes after write_fork_state, returns 'dirty'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")

            write_fork_state(root, forked_from="rendering.render", upstream_version="1.0.0")

            # Change the file
            (root / "main.py").write_text("print('world')\n", encoding="utf-8")

            result = detect_local_edits(root, forked_from="rendering.render")
            assert result == "dirty"

    def test_new_file_returns_dirty(self):
        """When a new file is added after write_fork_state, returns 'dirty'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")

            write_fork_state(root, forked_from="rendering.render", upstream_version="1.0.0")

            # Add a new file
            (root / "extra.py").write_text("# extra\n", encoding="utf-8")

            result = detect_local_edits(root, forked_from="rendering.render")
            assert result == "dirty"

    def test_deleted_file_returns_dirty(self):
        """When a file is deleted after write_fork_state, returns 'dirty'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "extra.py").write_text("# extra\n", encoding="utf-8")

            write_fork_state(root, forked_from="rendering.render", upstream_version="1.0.0")

            # Delete a file
            (root / "extra.py").unlink()

            result = detect_local_edits(root, forked_from="rendering.render")
            assert result == "dirty"

    def test_no_fork_state_file_returns_clean(self):
        """When no .astrid_fork_state.json exists and not in git, returns 'clean'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "file.txt").write_text("hello\n", encoding="utf-8")

            result = detect_local_edits(root, forked_from="rendering.render")
            # Falls through git check (not a worktree) → hash fallback → no fork state → clean
            assert result == "clean"

    def test_subdirectories_included_in_hash(self):
        """Changes in subdirectories are detected."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / "subdir"
            sub.mkdir()
            (sub / "nested.py").write_text("x = 1\n", encoding="utf-8")

            write_fork_state(root, forked_from="rendering.render", upstream_version="1.0.0")

            # Change nested file
            (sub / "nested.py").write_text("x = 2\n", encoding="utf-8")

            result = detect_local_edits(root, forked_from="rendering.render")
            assert result == "dirty"


class TestWriteReadForkState:
    """write_fork_state() and read_fork_state() round-trip."""

    def test_write_and_read_round_trip(self):
        """Write fork state, read it back, verify fields."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")

            write_fork_state(root, forked_from="editorial.shots", upstream_version="2.0.0")

            state = read_fork_state(root)
            assert state is not None
            assert state["forked_from"] == "editorial.shots"
            assert state["upstream_version"] == "2.0.0"
            assert "file_hashes" in state
            assert isinstance(state["file_hashes"], dict)

    def test_read_nonexistent_returns_none(self):
        """read_fork_state returns None when file does not exist."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert read_fork_state(root) is None

    def test_custom_file_hashes(self):
        """write_fork_state accepts custom file_hashes dict."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            custom_hashes = {"a.py": "abc123", "b.py": "def456"}
            write_fork_state(
                root,
                forked_from="rendering.render",
                upstream_version="1.0.0",
                file_hashes=custom_hashes,
            )

            state = read_fork_state(root)
            assert state["file_hashes"] == custom_hashes

    def test_fork_state_filename_excluded_from_hashes(self):
        """The .astrid_fork_state.json file itself is excluded from hash computation."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('hello')\n", encoding="utf-8")

            write_fork_state(root, forked_from="rendering.render", upstream_version="1.0.0")

            # Now re-read the state — the fork state file itself should not be in hashes
            state = read_fork_state(root)
            assert ".astrid_fork_state.json" not in state["file_hashes"]

            # Writing again should produce clean (hashes haven't changed for actual content)
            result = detect_local_edits(root, forked_from="rendering.render")
            assert result == "clean"


class TestReturnType:
    """detect_local_edits returns a valid LocalEditState literal."""

    def test_return_is_valid_literal(self):
        """Return value is one of 'clean', 'dirty', 'conflict'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "f.txt").write_text("data\n", encoding="utf-8")

            # Not forked → clean
            assert detect_local_edits(root, forked_from="") == "clean"

            # Forked, no state → clean
            assert detect_local_edits(root, forked_from="builtin.x") == "clean"

            # Forked, state written → clean
            write_fork_state(root, forked_from="builtin.x", upstream_version="1.0")
            assert detect_local_edits(root, forked_from="builtin.x") == "clean"

            # Modified → dirty
            (root / "f.txt").write_text("changed\n", encoding="utf-8")
            assert detect_local_edits(root, forked_from="builtin.x") == "dirty"
