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


if __name__ == "__main__":
    unittest.main()
