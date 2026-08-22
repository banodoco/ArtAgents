"""Dual-read v1 → upgrade-on-next-save contract pin (plan-v5 B3-S).

v1-era documents (only ``clips`` required; ``tracks`` optional — see the v1
artifact in git history, e.g. commit 632a4ba) are NOT readable under v2
validation directly: the v2 schema requires ``tracks``.

S has no upgrade helper. The upgrade lives on the A side of the bridge:
``astrid/core/integrations/reigh/timeline_io.py:73-79``
(``_canonicalize_config``) injects ``tracks: []`` / ``clips: []`` via
``setdefault`` on the save path. This file pins THAT contract from the S
side; the local mirror exists only to make the contract executable and is
not production upgrade logic. A's ``save_timeline`` re-validates the
canonicalized config before persisting, so the upgraded doc must pass v2.
"""

from __future__ import annotations

import unittest

from banodoco_timeline_schema import validate_timeline

_V1_DOC = {
    "theme": "banodoco-default",
    "clips": [{"id": "legacy1", "at": 0.0, "track": "V1", "clipType": "hold", "hold": 1.0}],
}


def _upgrade_v1(config: dict) -> dict:
    """Mirror Astrid timeline_io._canonicalize_config setdefault semantics."""
    upgraded = dict(config)
    upgraded.setdefault("tracks", [])
    upgraded.setdefault("clips", [])
    return upgraded


class DualReadV1UpgradePinTests(unittest.TestCase):
    def test_v1_doc_not_readable_under_v2_without_upgrade(self) -> None:
        self.assertNotIn("tracks", _V1_DOC, "v1-era shape has no tracks")
        with self.assertRaises(Exception) as ctx:
            validate_timeline(_V1_DOC)
        self.assertIn("tracks", str(ctx.exception))

    def test_upgraded_v1_doc_revalidates_with_tracks(self) -> None:
        upgraded = _upgrade_v1(_V1_DOC)
        validate_timeline(upgraded)
        self.assertIn("tracks", upgraded)
        self.assertEqual(upgraded["tracks"], [])
        self.assertIn("clips", upgraded)

    def test_upgrade_never_invents_content(self) -> None:
        upgraded = _upgrade_v1(_V1_DOC)
        added = {k: v for k, v in upgraded.items() if k not in _V1_DOC}
        self.assertEqual(
            added,
            {"tracks": []},
            "upgrade must only add the missing tracks container key",
        )
        self.assertEqual(
            {k: v for k, v in upgraded.items() if k in _V1_DOC},
            _V1_DOC,
            "upgrade must not alter existing content",
        )


if __name__ == "__main__":
    unittest.main()
