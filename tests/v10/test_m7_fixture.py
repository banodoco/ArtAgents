"""Sprint 7 deterministic dogfood fixture contract (T3)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tests.v10._m7_fixture import build_m7_fixture


def test_fresh_fixtures_have_identical_cross_surface_snapshots(tmp_path: Path) -> None:
    first = build_m7_fixture(tmp_path / "first")
    second = build_m7_fixture(tmp_path / "second")

    assert first.snapshot == second.snapshot
    assert first.snapshot["fixture_identity"]["fixture_id"] == "m7-representative-v1"
    assert first.spec["provenance"]["credential_free"] is True
    assert first.spec["baseline"]["status"] == "provisional"
    assert first.spec["baseline"]["reason"] == "no approved m6 baseline exists"

    counts = first.snapshot["counts"]
    assert counts["projects"] == 1
    assert counts["timelines"] == 1
    assert counts["media"] == 4
    assert counts["media_locations"] == 4
    assert counts["runs"] == 2
    assert counts["tasks"] == 2
    assert counts["task_dependencies"] == 1
    assert counts["evidence_items"] == 5
    assert counts["project_references"] == 2
    assert counts["media_references"] == 4
    assert counts["shots"] == 1
    assert counts["shot_items"] == 2
    assert counts["reference_links"] == 1

    media = first.snapshot["reads"]["media"]
    assert {entry["locations"][0]["realm"] for entry in media} == {
        "managed_local",
        "external_local",
    }
    assert first.snapshot["reads"]["timeline_history"]
    assert first.snapshot["reads"]["timeline_diff"]
    assert first.snapshot["reads"]["change_feed"]
    assert first.snapshot["reads"]["verification_reads"]["events"] > 0
    assert first.snapshot["reads"]["tasks"][1]["dependencies"] == [
        {"depends_on_task_id": "m7-fanout-parent", "kind": "hard", "ordinal": 0}
    ]

    byte_records = first.snapshot["bytes"]
    for entry in first.spec["media"]:
        data = bytes.fromhex(entry["bytes_hex"])
        assert byte_records[entry["key"]] == {
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    assert byte_records["gallery"]["bytes"] > 0
