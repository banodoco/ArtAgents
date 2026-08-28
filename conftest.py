"""Pytest bootstrap for the megado worktree.

The canonical timeline-schema Python module (``banodoco_timeline_schema``)
lives in the sibling banodoco workspace and is normally resolved through an
editable ``astrid`` finder that maps to the main checkout. In this worktree
that finder points at the main repo's astrid, so the schema module is not
importable. Add the sibling schema package to the import path so timeline
validation (``canonical_timeline_config``) works in tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

_CANDIDATES = (
    Path.home()
    / "Documents"
    / "banodoco-workspace"
    / "packages"
    / "timeline-schema"
    / "python",
    Path.home()
    / "Documents"
    / "reigh-workspace"
    / "reigh-app-extension-rc"
    / "vendor"
    / "timeline-schema"
    / "python",
)


def _install_schema_path() -> None:
    for candidate in _CANDIDATES:
        if (candidate / "banodoco_timeline_schema").is_dir():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            return


_install_schema_path()