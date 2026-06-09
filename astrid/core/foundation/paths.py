"""Canonical root-path constants.

This module is the public surface for PACKAGE_ROOT, REPO_ROOT, and WORKSPACE_ROOT.
"""

from __future__ import annotations

from pathlib import Path

# This module lives at astrid/core/foundation/paths.py; parents[2] is the
# astrid package root (PACKAGE_ROOT).
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PACKAGE_ROOT.parent
WORKSPACE_ROOT = REPO_ROOT.parent
