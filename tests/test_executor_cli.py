"""Tests for executor UUID mode and handoff metadata — m3.5 T15.

Proves:
1. UUID mode skips non-producing runs successfully (returns 0 when
   hype.timeline.json is absent).
2. Timeline-producing UUID runs emit handoff metadata without calling
   SupabaseDataProvider.save_timeline().
3. _emit_uuid_handoff_metadata produces valid JSON with all required fields.
4. _push_run_to_supabase is fully removed (no remaining references).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ExecutorUUIDHandoffTest(unittest.TestCase):
    """Prove UUID-mode handoff metadata emission."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="exec-uuid-", dir=ROOT))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_emit_uuid_handoff_metadata_skip_when_no_timeline(self):
        """Non-producing runs: hype.timeline.json absent → returns 0, logs to stderr."""
        from astrid.core.executor.cli import _emit_uuid_handoff_metadata

        out_dir = self.tmp_dir / "empty-out"
        out_dir.mkdir(parents=True, exist_ok=True)

        # No hype.timeline.json in out_dir.
        rc = _emit_uuid_handoff_metadata(
            project_id="00000000-0000-0000-0000-000000000001",
            timeline_id="00000000-0000-0000-0000-000000000002",
            out_dir=out_dir,
        )
        self.assertEqual(rc, 0, "non-producing UUID runs should return 0")

    def test_emit_uuid_handoff_metadata_produces_valid_json(self):
        """Timeline-producing UUID runs emit valid bridge JSON."""
        from astrid.core.executor.cli import _emit_uuid_handoff_metadata

        out_dir = self.tmp_dir / "producing-out"
        out_dir.mkdir(parents=True, exist_ok=True)
        timeline_path = out_dir / "hype.timeline.json"
        timeline_path.write_text('{"theme":"test","clips":[]}', encoding="utf-8")

        # Capture stdout.
        import io
        import sys

        captured = io.StringIO()
        with patch.object(sys, "stdout", captured):
            rc = _emit_uuid_handoff_metadata(
                project_id="11111111-1111-1111-1111-111111111111",
                timeline_id="22222222-2222-2222-2222-222222222222",
                out_dir=out_dir,
            )

        self.assertEqual(rc, 0)
        output = captured.getvalue().strip()
        handoff = json.loads(output)

        # Verify required fields.
        self.assertEqual(handoff["bridge"], "executor-uuid-mode")
        self.assertEqual(handoff["schema_version"], 1)
        self.assertEqual(handoff["project_id"], "11111111-1111-1111-1111-111111111111")
        self.assertEqual(handoff["timeline_id"], "22222222-2222-2222-2222-222222222222")
        self.assertIn("out_dir", handoff)
        self.assertIn("timeline_path", handoff)
        self.assertIn("note", handoff)
        self.assertIn("m6", handoff["note"].lower())
        self.assertIn("replay", handoff["note"].lower())
        self.assertIn("emitted_at", handoff)

    def test_push_run_to_supabase_is_removed(self):
        """_push_run_to_supabase must not exist in cli.py."""
        from astrid.core.executor import cli as executor_cli

        self.assertFalse(
            hasattr(executor_cli, "_push_run_to_supabase"),
            "_push_run_to_supabase must be removed from executor/cli.py",
        )

    def test_no_supabase_save_timeline_call_in_uuid_path(self):
        """UUID-mode execution path must not call SupabaseDataProvider.save_timeline()."""
        import astrid.core.executor.cli as cli_mod

        source = Path(cli_mod.__file__).read_text(encoding="utf-8")
        # Check for actual calls to .save_timeline(), not just mentions in
        # help text, comments, or docstrings.
        lines = source.splitlines()
        in_docstring = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Track triple-quoted docstrings (simple state machine).
            if stripped.startswith('"""') or stripped.endswith('"""'):
                in_docstring = not in_docstring
                continue
            if in_docstring:
                continue
            # Skip comments.
            if stripped.startswith("#"):
                continue
            if ".save_timeline(" in stripped:
                self.fail(
                    f"SupabaseDataProvider.save_timeline() call found at line {i}: {stripped}"
                )

    def test_project_uuid_or_none_rejects_slugs(self):
        """_project_uuid_or_none returns None for non-UUID values like slugs."""
        from astrid.core.executor.cli import _project_uuid_or_none

        self.assertIsNone(_project_uuid_or_none(None))
        self.assertIsNone(_project_uuid_or_none(""))
        self.assertIsNone(_project_uuid_or_none("my-slug"))
        self.assertIsNone(_project_uuid_or_none("not-a-uuid"))

        # Valid UUIDs.
        self.assertEqual(
            _project_uuid_or_none("12345678-1234-1234-1234-123456789abc"),
            "12345678-1234-1234-1234-123456789abc",
        )


if __name__ == "__main__":
    unittest.main()
