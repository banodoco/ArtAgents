"""Skip the runpod pack tests when runpod_lifecycle isn't installed."""

from __future__ import annotations

import importlib.util

import pytest

_RUNPOD_LIFECYCLE_AVAILABLE = importlib.util.find_spec("runpod_lifecycle") is not None

# NOTE: do NOT use pytest.importorskip at conftest module scope. When pytest
# loads a conftest during the INITIAL conftest discovery pass, a module-level
# skip/importorskip raises Skipped through the loader and aborts the whole run
# (exit 1, 0 collected) instead of skipping the pack's tests. Defer the skip to
# collection time instead.


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every runpod-pack test when the optional dependency is absent."""
    if _RUNPOD_LIFECYCLE_AVAILABLE:
        return
    skip = pytest.mark.skip(
        reason="requires runpod_lifecycle — install from /private/tmp/orch-baseline-check/runpod_lifecycle or pip install runpod-lifecycle"
    )
    for item in items:
        if "runpod" in str(item.path):
            item.add_marker(skip)
