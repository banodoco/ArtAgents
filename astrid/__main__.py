"""Run Astrid as an executable package."""

from __future__ import annotations

import os

os.environ.setdefault("ASTRID_INTERNAL_INVOCATION", "1")

from .gateway import main

if __name__ == "__main__":
    raise SystemExit(main())
