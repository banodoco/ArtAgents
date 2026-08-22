"""Ten-fixture parity corpus (plan-v5 B3-S).

The corpus pins:
- every fixture is a minimal (<2KB), pairwise-distinct TimelineConfig,
- each v2 fixture validates against the canonical schema, and its stable
  canonical serialization (``json.dumps(sort_keys=True)``) round-trips
  identically (fixed point) and re-validates,
- ``10-v1-era.json`` is a v1-era document (``clips`` only, no ``tracks``):
  it is NOT readable under v2 validation directly — it is readable only via
  the explicit upgrade path (``setdefault("tracks", [])`` /
  ``setdefault("clips", [])``, mirroring Astrid
  ``astrid/core/integrations/reigh/timeline_io.py:73-79``
  ``_canonicalize_config``). After upgrade it re-validates with ``tracks``.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from banodoco_timeline_schema import validate_timeline

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "parity"
V1_FIXTURE = "10-v1-era.json"
MAX_FIXTURE_BYTES = 2 * 1024


def _canonical(obj: object) -> str:
    """Stable canonical serialization (plan-v5 B3): sort_keys + compact."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _upgrade_v1(config: dict) -> dict:
    """Mirror Astrid timeline_io._canonicalize_config: inject tracks/clips
    defaults at save time. In-test mirror only; S ships no upgrade helper."""
    upgraded = dict(config)
    upgraded.setdefault("tracks", [])
    upgraded.setdefault("clips", [])
    return upgraded


class ParityCorpusTests(unittest.TestCase):
    def test_corpus_has_ten_tiny_distinct_fixtures(self) -> None:
        docs: dict[str, dict] = {}
        for path in sorted(FIXTURES.glob("*.json")):
            self.assertLess(
                path.stat().st_size,
                MAX_FIXTURE_BYTES,
                f"{path.name} exceeds 2KB parity limit",
            )
            docs[path.name] = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(docs), 10, "parity corpus must hold exactly 10 fixtures")
        canonicals = [
            _canonical(_upgrade_v1(doc) if name == V1_FIXTURE else doc)
            for name, doc in docs.items()
        ]
        self.assertEqual(
            len(set(canonicals)), 10, "fixtures must be pairwise distinct"
        )

    def test_v2_fixtures_validate_and_roundtrip(self) -> None:
        for path in sorted(FIXTURES.glob("*.json")):
            if path.name == V1_FIXTURE:
                continue
            config = json.loads(path.read_text(encoding="utf-8"))
            validate_timeline(config)
            text = _canonical(config)
            reparsed = json.loads(text)
            self.assertEqual(
                _canonical(reparsed),
                text,
                f"{path.name}: canonical serialization not a fixed point",
            )
            validate_timeline(reparsed)

    def test_v1_fixture_dual_read_only_via_upgrade(self) -> None:
        config = json.loads((FIXTURES / V1_FIXTURE).read_text(encoding="utf-8"))
        self.assertNotIn("tracks", config, "v1-era fixture must lack tracks")
        with self.assertRaises(Exception):
            validate_timeline(config)  # not readable under v2 directly
        upgraded = _upgrade_v1(config)
        validate_timeline(upgraded)  # readable only after the explicit upgrade
        self.assertIn("tracks", upgraded)
        self.assertEqual(upgraded["tracks"], [])
        text = _canonical(upgraded)
        self.assertEqual(_canonical(json.loads(text)), text)


if __name__ == "__main__":
    unittest.main()
