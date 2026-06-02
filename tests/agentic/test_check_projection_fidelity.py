from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.agentic.checks.projection_fidelity import c4_projection_fidelity
from tests.agentic.checks.triggers import TriggerRecord, resolve_trigger_records


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_timeline_assembly_jsonl(
    evidence_dir: Path, timeline_id: str, rows: list[dict]
) -> Path:
    dir_path = evidence_dir / "timelines" / timeline_id
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / "assembly.jsonl"
    path.write_text(
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )
    return path


def _write_timeline_assembly_json(
    evidence_dir: Path, timeline_id: str, data: dict
) -> Path:
    dir_path = evidence_dir / "timelines" / timeline_id
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / "assembly.json"
    path.write_text(
        json.dumps(data, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _make_timeline_created_event(
    *,
    timeline_id: str = "00000000-0000-0000-0000-000000000001",
    event_id: str = "01AAAAAAAAAAAAAAAAAAAAAA00",
    slug: str = "test-timeline",
    name: str = "Test Timeline",
) -> dict:
    return {
        "event_id": event_id,
        "timeline_id": timeline_id,
        "ts": "2026-01-01T00:00:00Z",
        "actor": {"type": "system", "id": "test"},
        "prev_hash": None,
        "hash": event_id + "0",
        "kind": "timeline.created",
        "payload": {
            "timeline_id": timeline_id,
            "slug": slug,
            "name": name,
        },
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
    }


def _c4_enabled() -> TriggerRecord:
    records = resolve_trigger_records(
        scenario_extras={
            "m2_checks": {
                "c4_projection_fidelity": {"enabled": True},
            }
        }
    )
    return records["C4"]


def _c4_disabled() -> TriggerRecord:
    records = resolve_trigger_records()
    return records["C4"]


# ---------------------------------------------------------------------------
# na — trigger not declared or no snapshot
# ---------------------------------------------------------------------------

def test_c4_returns_na_when_trigger_not_declared(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_disabled())

    assert result["id"] == "C4"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "trigger not declared"


def test_c4_returns_na_when_no_timeline_dirs(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "no frozen assembly.json snapshot in any timeline"


def test_c4_returns_na_when_timeline_dir_has_no_snapshot(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    # Create timeline dir but no assembly.json
    (evidence_dir / "timelines" / "tl-1").mkdir(parents=True)
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "na"
    assert result["detail"]["reason"] == "no frozen assembly.json snapshot in any timeline"


def test_c4_returns_na_when_trigger_none_provided_and_no_snapshot(tmp_path: Path) -> None:
    """When no trigger_record is provided, check should still gate on snapshot presence."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    result = c4_projection_fidelity(evidence_dir)

    assert result["id"] == "C4"
    assert result["status"] == "na"
    assert "no frozen assembly.json snapshot" in result["detail"]["reason"]


# ---------------------------------------------------------------------------
# pass — projection matches snapshot
# ---------------------------------------------------------------------------

def test_c4_passes_when_empty_stream_matches_empty_snapshot(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "pass"
    assert result["detail"]["timelines_checked"] == ["tl-1"]
    assert result["detail"]["mismatches"] == []


def test_c4_passes_when_single_timeline_projection_matches(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    events = [_make_timeline_created_event()]
    # Empty events produce {"tracks": [], "clips": []}
    # timeline.created is metadata_noop, so projection is still empty
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", events)
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "pass"
    assert result["detail"]["timelines_checked"] == ["tl-1"]
    assert result["detail"]["mismatches"] == []


def test_c4_passes_when_multiple_timelines_all_match(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    for tl_id in ("tl-1", "tl-2", "tl-3"):
        _write_timeline_assembly_jsonl(evidence_dir, tl_id, [])
        _write_timeline_assembly_json(evidence_dir, tl_id, {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "pass"
    assert set(result["detail"]["timelines_checked"]) == {"tl-1", "tl-2", "tl-3"}
    assert result["detail"]["mismatches"] == []


def test_c4_passes_when_some_timelines_have_no_snapshot_but_others_match(
    tmp_path: Path,
) -> None:
    """Only timelines with snapshots are checked; those without are silently skipped."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # tl-1 has snapshot and matches
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})
    # tl-2 has no snapshot (should be skipped, not cause na)
    (evidence_dir / "timelines" / "tl-2").mkdir(parents=True)
    _write_timeline_assembly_jsonl(evidence_dir, "tl-2", [])

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "pass"
    assert result["detail"]["timelines_checked"] == ["tl-1"]
    assert result["detail"]["mismatches"] == []


# ---------------------------------------------------------------------------
# fail — projection mismatch
# ---------------------------------------------------------------------------

def test_c4_fails_when_projection_differs_from_snapshot(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    # Projection is {"tracks": [], "clips": []} but snapshot is different
    _write_timeline_assembly_json(
        evidence_dir, "tl-1", {"tracks": [{"id": "extra"}], "clips": []}
    )

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["timelines_failed"] == ["tl-1"]
    assert len(result["detail"]["mismatches"]) == 1
    assert result["detail"]["mismatches"][0]["kind"] == "projection_mismatch"


def test_c4_fails_when_snapshot_has_extra_keys(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    _write_timeline_assembly_json(
        evidence_dir, "tl-1", {"tracks": [], "clips": [], "extra_field": True}
    )

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["mismatches"][0]["kind"] == "projection_mismatch"


def test_c4_fails_when_stream_missing_but_snapshot_present(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Snapshot exists but no assembly.jsonl
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["mismatches"][0]["kind"] == "stream_missing_or_unparseable"


def test_c4_fails_when_stream_is_unparseable(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    tl_dir = evidence_dir / "timelines" / "tl-1"
    tl_dir.mkdir(parents=True)
    (tl_dir / "assembly.jsonl").write_text("not valid json\n", encoding="utf-8")
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["mismatches"][0]["kind"] == "stream_missing_or_unparseable"


def test_c4_fails_when_snapshot_is_unparseable(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    tl_dir = evidence_dir / "timelines" / "tl-1"
    (tl_dir / "assembly.json").write_text("not json", encoding="utf-8")

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["mismatches"][0]["kind"] == "snapshot_unparseable"


def test_c4_fails_when_events_have_schema_errors(tmp_path: Path) -> None:
    """Events that fail TimelineEvent.from_dict() should cause a fail."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # Bad event: missing required fields
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [
        {"event_id": "bad", "kind": "invalid.kind"},
    ])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["mismatches"][0]["kind"] == "stream_schema_error"


def test_c4_fails_when_events_have_payload_coercion_errors(tmp_path: Path) -> None:
    """Events whose payloads fail coercion during from_dict should be caught."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # clip.added requires specific payload fields — empty payload triggers coercion error
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [
        {
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAA00",
            "timeline_id": "00000000-0000-0000-0000-000000000001",
            "ts": "2026-01-01T00:00:00Z",
            "actor": {"type": "system", "id": "test"},
            "prev_hash": None,
            "hash": "01AAAAAAAAAAAAAAAAAAAAAA000",
            "kind": "clip.added",
            "payload": {},  # missing required clip fields
            "expected_version": None,
            "schema_version": 2,
            "txn_id": None,
        },
    ])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["mismatches"][0]["kind"] == "stream_schema_error"


def test_c4_fails_when_some_timelines_pass_and_others_fail(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # tl-1: matches
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})
    # tl-2: mismatches
    _write_timeline_assembly_jsonl(evidence_dir, "tl-2", [])
    _write_timeline_assembly_json(
        evidence_dir, "tl-2", {"tracks": [{"id": "bad"}], "clips": []}
    )

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "fail"
    assert result["detail"]["timelines_passed"] == ["tl-1"]
    assert result["detail"]["timelines_failed"] == ["tl-2"]
    assert len(result["detail"]["mismatches"]) == 1
    assert result["detail"]["mismatches"][0]["timeline"] == "tl-2"


# ---------------------------------------------------------------------------
# evidence_refs
# ---------------------------------------------------------------------------

def test_c4_returns_evidence_refs_in_result(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert len(result["evidence_refs"]) == 2
    refs_set = set(result["evidence_refs"])
    assert "timelines/tl-1/assembly.json" in refs_set
    assert "timelines/tl-1/assembly.jsonl" in refs_set


# ---------------------------------------------------------------------------
# edge case: multiple timelines with mixed snapshot presence
# ---------------------------------------------------------------------------

def test_c4_skips_timelines_without_snapshot_and_checks_those_with(
    tmp_path: Path,
) -> None:
    """Multiple timelines; only those with snapshots are projected and compared."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    # tl-1: has snapshot + stream, matches
    _write_timeline_assembly_jsonl(evidence_dir, "tl-1", [])
    _write_timeline_assembly_json(evidence_dir, "tl-1", {"tracks": [], "clips": []})
    # tl-2: has stream but NO snapshot (skipped)
    _write_timeline_assembly_jsonl(evidence_dir, "tl-2", [])
    # tl-3: has snapshot + stream, matches
    _write_timeline_assembly_jsonl(evidence_dir, "tl-3", [])
    _write_timeline_assembly_json(evidence_dir, "tl-3", {"tracks": [], "clips": []})

    result = c4_projection_fidelity(evidence_dir, trigger_record=_c4_enabled())

    assert result["id"] == "C4"
    assert result["status"] == "pass"
    assert set(result["detail"]["timelines_checked"]) == {"tl-1", "tl-3"}
