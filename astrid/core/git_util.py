"""Read-only git utilities for pack-system capability edit detection."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GitUtilError(RuntimeError):
    """Raised when a git operation fails or the environment is not a git repo."""


@dataclass(frozen=True)
class GitStatus:
    """Structured result of `git status --porcelain`."""

    dirty: bool
    staged: tuple[str, ...]
    unstaged: tuple[str, ...]
    untracked: tuple[str, ...]
    raw_lines: tuple[str, ...]


def is_git_worktree(path: str | Path) -> bool:
    """Return True if *path* lives inside a git worktree.

    Walks up the directory tree looking for a ``.git`` file (worktree link)
    or directory (regular clone).
    """
    candidate = Path(path).resolve()
    for parent in (candidate, *candidate.parents):
        git_entry = parent / ".git"
        if git_entry.exists():
            return True
    return False


def git_root(path: str | Path) -> Path:
    """Return the absolute path of the git repository root for *path*."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=str(path),
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise GitUtilError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitUtilError(f"git rev-parse timed out after 10s") from exc

    if result.returncode != 0 or not result.stdout.strip():
        raise GitUtilError(f"not a git repository (or no git available): {result.stderr.strip()}")
    return Path(result.stdout.strip())


def git_status(path: str | Path) -> GitStatus:
    """Run ``git status --porcelain`` and return a structured result.

    Parses every status line in the XY format:
    - ``staged``: files where the index (column 0) changed.
    - ``unstaged``: files where the working tree (column 1) changed.
    - ``untracked``: files with ``??`` status.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(path),
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise GitUtilError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitUtilError(f"git status timed out after 10s") from exc

    if result.returncode != 0:
        raise GitUtilError(f"git status failed: {result.stderr.strip()}")

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []

    for line in lines:
        if len(line) < 3:
            continue
        xy = line[:2]
        filename = line[3:].rstrip()
        # Renames may show up as 'R  old -> new'
        if " -> " in filename:
            # For structured tracking, store the whole line
            filename = filename
        if xy == "??":
            untracked.append(filename)
        else:
            index_char = xy[0]
            worktree_char = xy[1]
            if index_char != " ":
                staged.append(filename)
            if worktree_char != " ":
                unstaged.append(filename)

    dirty = bool(staged or unstaged or untracked)

    return GitStatus(
        dirty=dirty,
        staged=tuple(staged),
        unstaged=tuple(unstaged),
        untracked=tuple(untracked),
        raw_lines=tuple(lines),
    )


def git_diff_file(path: str | Path, against: str = "HEAD") -> str:
    """Return the diff of a single file against *against* (default ``HEAD``).

    Returns an empty string when the file has no changes.
    """
    file_path = Path(path)
    try:
        result = subprocess.run(
            ["git", "diff", against, "--", str(file_path)],
            capture_output=True,
            text=True,
            cwd=str(file_path.parent),
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise GitUtilError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitUtilError(f"git diff timed out after 10s") from exc

    if result.returncode != 0:
        raise GitUtilError(f"git diff failed: {result.stderr.strip()}")
    return result.stdout


__all__ = [
    "GitUtilError",
    "GitStatus",
    "git_diff_file",
    "git_root",
    "git_status",
    "is_git_worktree",
]
