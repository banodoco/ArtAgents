"""Regression for the runpod sweeper async/sync boundary (SD1).

Pre-fix bug: ``sweep()`` called ``asyncio.run()`` unconditionally, which
crashed with ``RuntimeError: asyncio.run() cannot be called from a running
event loop`` when invoked from an async caller.

The fix extracts :func:`sweep_async` as the canonical async API and makes
:func:`sweep` a sync wrapper that uses ``asyncio.run`` ONLY when no loop is
running. Inside a running loop it raises :class:`SweeperLoopError` so the
caller's threading model stays explicit.
"""

from __future__ import annotations

import asyncio
import unittest
from pathlib import Path

from astrid.core.integrations.runpod.sweeper import SweeperLoopError, sweep, sweep_async


class SweeperAsyncBoundaryTest(unittest.TestCase):
    def test_sync_sweep_succeeds_outside_loop(self) -> None:
        """Calling sync ``sweep()`` from a normal sync caller still works.

        Uses a non-existent projects_root: ``collect_handles`` short-circuits
        to an empty list, so the sweep completes immediately with totals=0.
        """
        result = sweep(Path("/tmp/sweeper-nonexistent-root-test"), mode="default", dry_run=True)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["terminated"], 0)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["errors"], 0)

    def test_sync_sweep_inside_running_loop_raises_typed_error(self) -> None:
        """Sync ``sweep()`` inside a running loop must raise SweeperLoopError.

        Specifically NOT raw ``RuntimeError`` from ``asyncio.run`` — the typed
        error signals to the caller that they must switch to ``await
        sweep_async(...)`` (SD1 — never silently create_task on caller loop).
        """

        async def _call_from_loop() -> None:
            # Inside this coroutine an event loop is running. The sync wrapper
            # must detect that and raise SweeperLoopError, not RuntimeError.
            sweep(Path("/tmp/sweeper-nonexistent-root-test"), mode="default", dry_run=True)

        with self.assertRaises(SweeperLoopError):
            asyncio.run(_call_from_loop())

    def test_async_sweep_works_inside_running_loop(self) -> None:
        """Awaiting ``sweep_async()`` inside a running loop is the supported path."""

        async def _call() -> dict:
            return await sweep_async(
                Path("/tmp/sweeper-nonexistent-root-test"),
                mode="default",
                dry_run=True,
            )

        result = asyncio.run(_call())
        self.assertIsInstance(result, dict)
        self.assertEqual(result["total"], 0)


if __name__ == "__main__":
    unittest.main()
