#!/usr/bin/env python3
"""Compatibility wrapper for the canonical Sprint 0 multi-root inventory."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.reshape.inventory_state import main


if __name__ == "__main__":
    raise SystemExit(main())
