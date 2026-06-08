"""Regression for ErasedPayloadProjectionError.__str__ relocation.

Pre-fix bug: a ``__str__`` method was indented after the ``return`` in
``_validate_projected_timeline_boundary`` — unreachable dead code that
never customised the error message. Subclasses fell back to
``ProjectionError.__str__`` so the templated "erased payload cannot be
projected" wording was effectively lost.

The fix moves the method into the ``ErasedPayloadProjectionError`` class
body so ``str(err)`` carries event_id, kind, and reason in the erased-
payload-specific phrasing.
"""

from __future__ import annotations

import unittest

from astrid.core.timeline.projection import ErasedPayloadProjectionError


class ErasedPayloadProjectionErrorStrTest(unittest.TestCase):
    def test_str_includes_event_id_kind_and_reason(self) -> None:
        err = ErasedPayloadProjectionError(
            event_id="01HXEVENTIDXXXXXXXXXXXXXXX",
            kind="clip.added",
            reason="payload was erased before projection",
        )
        rendered = str(err)
        self.assertIn("erased payload cannot be projected", rendered)
        self.assertIn("01HXEVENTIDXXXXXXXXXXXXXXX", rendered)
        self.assertIn("clip.added", rendered)
        self.assertIn("payload was erased before projection", rendered)


if __name__ == "__main__":
    unittest.main()
