"""Contract tests: opaque `app` bags and v2 structural rules (plan-v5 B3).

- `app` bags on config/tracks/clips are opaque JSON: arbitrary nested content
  must validate and round-trip (extension parse failure = absence at the
  consumer, never a save/load failure).
- `tracks` is required; `clip_order` must be > 0.
- The real desert-plant-growth event log replays cleanly under v2 (all 36
  config events carry tracks).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from banodoco_timeline_schema import TimelineConfig, validate_timeline


class OpaqueAppBagsTest(unittest.TestCase):
    def test_config_app_bag_roundtrips_opaque(self) -> None:
        config: TimelineConfig = {
            "clips": [],
            "tracks": [{"id": "V1", "kind": "visual", "label": "V1"}],
            "app": {
                "com.reigh.scene-phase-markers": {
                    "sceneMarkers": [{"id": "m1", "time": 1.5}],
                },
                "com.example.extension": {"nested": {"any": [1, 2, 3]}},
            },
        }
        validate_timeline(config)

    def test_clip_app_bag_roundtrips_opaque(self) -> None:
        config: TimelineConfig = {
            "clips": [{
                "id": "c1",
                "at": 0,
                "track": "V1",
                "clipType": "hold",
                "hold": 1,
                "app": {
                    "reigh": {
                        "shader": {"shaderId": "chroma", "uniforms": {"hue": 0.3}},
                    },
                },
                "keyframes": {"opacity": [{"time": 0, "value": 1}]},
            }],
            "tracks": [{"id": "V1", "kind": "visual", "label": "V1"}],
        }
        validate_timeline(config)

    def test_malformed_app_bag_validates_and_roundtrips(self) -> None:
        """Extension parse failure = absence, never save/load failure (B3-S).

        The schema treats ``app`` bags as opaque JSON (``additionalProperties:
        {}``). Values no consumer could parse as extension data — deeply nested
        junk (JSON cannot self-reference, so 60 levels of nesting), wrong-typed
        scalars, a ~1MB blob, scalars/arrays where an object is expected, empty
        keys — must (a) validate fine (app is opaque) and (b) survive canonical
        round-trip byte-identically. Consumer contract: a consumer that cannot
        parse an extension value treats it as ABSENCE of that extension and
        never fails the surrounding save/load.
        """
        deep: dict = {"leaf": "x"}
        for _ in range(60):
            deep = {"nested": deep}
        config: TimelineConfig = {
            "clips": [],
            "tracks": [{"id": "V1", "kind": "visual", "label": "V1"}],
            "app": {
                "reigh.x": deep,
                "com.example.junk": {
                    "version": [1, 2, 3],
                    "flag": {"k": None},
                    "count": "not-a-number",
                },
                "com.example.blob": {"payload": "x" * (1024 * 1024)},
                "com.example.ambiguous": 42,
                "com.example.array": ["not", "an", "object"],
                "": {"empty-key": True},
            },
        }
        validate_timeline(config)  # (a) schema acceptance: app is opaque
        text = json.dumps(config, sort_keys=True, separators=(",", ":"))
        reparsed = json.loads(text)
        self.assertEqual(
            json.dumps(reparsed, sort_keys=True, separators=(",", ":")),
            text,
            "malformed app bag must round-trip byte-identically",
        )
        validate_timeline(reparsed)  # (b) canonical form still validates

    def test_tracks_required(self) -> None:
        with self.assertRaises(Exception):
            validate_timeline({"clips": []})

    def test_clip_order_must_be_positive(self) -> None:
        config: TimelineConfig = {
            "clips": [{"id": "c1", "at": 0, "track": "V1", "clipType": "hold", "clip_order": 0}],
            "tracks": [{"id": "V1", "kind": "visual", "label": "V1"}],
        }
        with self.assertRaises(Exception):
            validate_timeline(config)


class RealProjectReplayTest(unittest.TestCase):
    """The real desert-plant-growth event log must replay cleanly under v2."""

    # Workspace layout: banodoco-workspace is a sibling of reigh-workspace.
    _workspace = Path(__file__).resolve().parents[3]
    LOG = _workspace.parent / "reigh-workspace" / "Astrid" / "projects" / \
        "desert-plant-growth" / "timelines" / \
        "01KYPVKMW5STB4W6FE05ED8242" / "assembly.jsonl"

    @unittest.skipUnless(LOG.is_file(), "desert-plant-growth project not present")
    def test_all_config_events_replay_under_v2(self) -> None:
        config_events = 0
        for line in self.LOG.open(encoding="utf-8"):
            event = json.loads(line)
            if event.get("kind") == "timeline.config_replaced":
                config = event.get("payload", {}).get("config")
                if isinstance(config, dict):
                    config_events += 1
                    validate_timeline(config)
        self.assertGreater(config_events, 0)


class DesertSliceReplayTest(unittest.TestCase):
    """Replay the real desert_slice event log (159 events) through v2.

    Every ``timeline.config_replaced`` payload must validate against the v2
    schema. GOAL B3 acceptance names a 123-event replay; the slice fixture
    holds 159 events of which 37 carry config payloads — those are the
    config-shaped subset this replay covers (legacy payloads failing here
    would BE the dual-read finding; today all 37 pass).
    """

    # Sibling-repo layout: repos/ArtAgents/packages/timeline-schema/tests
    # and repos/Astrid (parents[4] = the repos dir).
    _log = (
        Path(__file__).resolve().parents[4]
        / "Astrid"
        / "tests"
        / "fixtures"
        / "timeline_visualize"
        / "desert_slice"
        / "assembly.jsonl"
    )

    @unittest.skipUnless(_log.is_file(), "Astrid desert_slice fixture not present")
    def test_all_config_events_replay_under_v2(self) -> None:
        total = config_events = passed = failed = 0
        failures: list[str] = []
        for line in self._log.open(encoding="utf-8"):
            event = json.loads(line)
            total += 1
            if event.get("kind") != "timeline.config_replaced":
                continue
            config = event.get("payload", {}).get("config")
            if not isinstance(config, dict):
                failed += 1
                failures.append("non-dict config payload")
                continue
            config_events += 1
            try:
                validate_timeline(config)
                passed += 1
            except Exception as exc:  # noqa: BLE001 — collect, don't abort
                failed += 1
                failures.append(f"{type(exc).__name__}: {exc}")
        self.assertEqual(total, 159, "desert_slice fixture drifted from 159 events")
        self.assertGreater(config_events, 0)
        self.assertEqual(
            failed, 0, f"{failed}/{config_events} config events failed v2: {failures[:3]}"
        )
        self.assertEqual(passed, config_events)


if __name__ == "__main__":
    unittest.main()
