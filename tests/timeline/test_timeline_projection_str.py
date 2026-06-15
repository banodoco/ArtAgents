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

from astrid.core.timeline.events.schema import TimelineEvent
from astrid.core.timeline.projection import ErasedPayloadProjectionError, apply_event_to_assembly


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


class UnknownKindProjectionNoopTest(unittest.TestCase):
    """Prove that unknown event kinds are treated as metadata no-ops during
    assembly projection, including when the payload is an erased envelope."""

    def _make_event(self, kind: str, payload: dict) -> TimelineEvent:
        return TimelineEvent.from_dict({
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAA00",
            "timeline_id": "00000000-0000-0000-0000-000000000001",
            "ts": "2026-01-01T00:00:00Z",
            "actor": {"type": "system", "id": "test", "display": "Test"},
            "prev_hash": None,
            "hash": None,
            "kind": kind,
            "payload": payload,
            "expected_version": None,
            "schema_version": 2,
            "txn_id": None,
        })

    def test_unknown_event_kind_is_projected_as_metadata_noop(self) -> None:
        """An event with a kind not in PROJECTOR_EVENT_CLASSIFICATION
        is a no-op and leaves the assembly state unchanged."""
        state = {
            "tracks": [{"id": "v1", "kind": "visual", "label": "Video"}],
            "clips": [{"id": "c1", "at": 0.0, "track": "v1", "clipType": "media", "asset": "a1"}],
        }
        event = self._make_event(
            "completely.unknown.future.kind",
            {"assets": {"a1": {"kind": "image"}}},
        )

        result = apply_event_to_assembly(state, event)

        self.assertEqual(result, state)
        self.assertIs(result, state)

    def test_unknown_erased_event_kind_is_projected_as_metadata_noop(self) -> None:
        """An erased event with an unknown kind is also a no-op — the
        erased-payload check runs first, sees an ErasedPayload, finds
        the kind not in _ERASED_SAFE_KINDS, and since the kind is also
        not in PROJECTOR_EVENT_CLASSIFICATION it returns state unchanged."""
        state = {
            "tracks": [{"id": "v1", "kind": "visual", "label": "Video"}],
            "clips": [{"id": "c1", "at": 0.0, "track": "v1", "clipType": "media", "asset": "a1"}],
        }
        event = self._make_event(
            "completely.unknown.future.kind",
            {
                "erased": True,
                "reason": "policy",
                "erased_at": "2026-01-01T00:00:00Z",
                "erased_by": "system:test",
            },
        )

        result = apply_event_to_assembly(state, event)

        self.assertEqual(result, state)
        self.assertIs(result, state)

    def test_unknown_kind_preserves_payload_as_raw_dict(self) -> None:
        """An unknown event kind preserves its payload as a raw dict
        (not coerced to a typed payload model)."""
        raw_payload = {"surprise": {"nested": [1, 2, 3]}, "source": "db"}
        event = self._make_event("completely.unknown.future.kind", raw_payload)

        self.assertEqual(event.kind, "completely.unknown.future.kind")
        self.assertIsInstance(event.payload, dict)
        self.assertNotIsInstance(event.payload, (type(None),))
        self.assertEqual(event.payload, raw_payload)
        self.assertIsNot(event.payload, raw_payload)  # defensive copy


if __name__ == "__main__":
    unittest.main()
