"""Local-edit detection for forked capabilities.

Uses git status when the capability lives inside a git worktree; falls back
to a ``.astrid_fork_state.json`` hash-based comparison otherwise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrid.core.contracts.schema import LocalEditState
from astrid.core.util.git import GitUtilError, git_status, is_git_worktree
from astrid.core.foundation.hash import sha256_file as _sha256_file

_FORK_STATE_FILENAME = ".astrid_fork_state.json"


def detect_local_edits(capability_root: str | Path, *, forked_from: str = "") -> LocalEditState:
    """Return the local edit state for a capability directory.

    * When *forked_from* is empty the capability is considered original
      (not forked) and always returns ``"clean"``.
    * When inside a git worktree, uses ``git status --porcelain`` to
      decide between ``"clean"`` and ``"dirty"``.
    * Otherwise falls back to a hash-based comparison via
      ``.astrid_fork_state.json``.
    """
    root = Path(capability_root).resolve()
    if not forked_from:
        return "clean"

    if is_git_worktree(root):
        try:
            status = git_status(root)
        except GitUtilError:
            # If git fails for any reason, fall through to hash fallback.
            pass
        else:
            return "dirty" if status.dirty else "clean"

    # Hash-based fallback: compare current file hashes against stored state.
    stored = read_fork_state(root)
    if stored is None:
        # No stored fork state — cannot determine, assume clean.
        return "clean"

    stored_hashes: dict[str, str] = stored.get("file_hashes", {})
    current_hashes = _compute_file_hashes(root)

    if stored_hashes != current_hashes:
        return "dirty"

    return "clean"


def write_fork_state(
    capability_root: str | Path,
    forked_from: str,
    upstream_version: str,
    file_hashes: dict[str, str] | None = None,
) -> None:
    """Persist the fork state to ``.astrid_fork_state.json``.

    *file_hashes* is a mapping of ``relative_path -> sha256_hex``.
    When ``None``, hashes are computed from the current contents of
    *capability_root*.
    """
    root = Path(capability_root).resolve()
    if file_hashes is None:
        file_hashes = _compute_file_hashes(root)

    state: dict[str, Any] = {
        "forked_from": forked_from,
        "upstream_version": upstream_version,
        "file_hashes": file_hashes,
    }

    fork_state_path = root / _FORK_STATE_FILENAME
    fork_state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def read_fork_state(capability_root: str | Path) -> dict[str, Any] | None:
    """Read the persisted fork state, or ``None`` if it does not exist."""
    fork_state_path = Path(capability_root).resolve() / _FORK_STATE_FILENAME
    if not fork_state_path.is_file():
        return None
    try:
        data = json.loads(fork_state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _compute_file_hashes(root: Path) -> dict[str, str]:
    """Walk *root* and compute a SHA-256 hex digest for every regular file.

    Returns a ``{relative_path: sha256_hex}`` dict, excluding the fork
    state file itself and any ``.git`` contents.
    """
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.name == _FORK_STATE_FILENAME:
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        hashes[rel] = _sha256_file(path)
    return hashes
__all__ = [
    "detect_local_edits",
    "read_fork_state",
    "write_fork_state",
]
