"""Skip the runpod pack tests when runpod_lifecycle isn't installed."""

from __future__ import annotations

import pytest

pytest.importorskip(
    "runpod_lifecycle",
    reason="requires runpod_lifecycle — install from /private/tmp/orch-baseline-check/runpod_lifecycle or pip install runpod-lifecycle",
)
