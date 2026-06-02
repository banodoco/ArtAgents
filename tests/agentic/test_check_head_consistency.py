from __future__ import annotations

import json
from pathlib import Path

from tests.agentic.checks.head_consistency import c1_head_sidecar_consistency


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_head_json(
    *,
    timeline_id: str = "00000000-0000-0000-0000-000000000001",
    last_event_id: str | None = None,
    last_hash: str | None = None,
    event_count: int = 0,
    version: int = 0,
) -> str:
    return json.dumps(
        {
            "timeline_id": timeline_id,
            "last_event_id": last_event_id,
            "last_hash": last_hash,
            "event_count": event_count,
            "version": version,
        }
    ) + "\n"


def _make_jsonl_event(
    *,
    event_id: str,
    timeline_id: str = "00000000-0000-0000-0000-000000000001",
    hash_val: str,
    ts: str = "2025-01-01T00:00:00.000Z",
    kind: str = "timeline.created",
) -> dict:
    return {
        "event_id": event_id,
        "timeline_id": timeline_id,
        "ts": ts,
        "actor": {"type": "agent", "id": "test:agent"},
        "prev_hash": None,
        "hash": hash_val,
        "kind": kind,
        "payload": {},
        "expected_version": None,
        "schema_version": 2,
        "txn_id": None,
    }


def _write_jsonl(path: Path, events: list[dict]) -> None:
    lines = "\n".join(json.dumps(ev, separators=(",", ":")) for ev in events) + "\n"
    path.write_text(lines, encoding="utf-8")


# ---------------------------------------------------------------------------
# NA — no head sidecar
# ---------------------------------------------------------------------------


def test_c1_na_when_no_head_sidecar_in_any_timeline(tmp_path: Path) -> None:
    """No timeline has an assembly.head.json → na."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)
    _write_jsonl(
        timeline_dir / "assembly.jsonl",
        [_make_jsonl_event(event_id="EV01", hash_val="a" * 64)],
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "na"
    assert result["id"] == "C1"


def test_c1_na_when_no_timeline_dir_exists(tmp_path: Path) -> None:
    """No timelines/ directory at all → na."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir(parents=True)

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "na"
    assert result["id"] == "C1"


# ---------------------------------------------------------------------------
# PASS — consistent head/sidecar
# ---------------------------------------------------------------------------


def test_c1_pass_single_timeline_consistent(tmp_path: Path) -> None:
    """One timeline with matching head and stream → pass."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    events = [
        _make_jsonl_event(event_id="EV01", hash_val="a" * 64),
        _make_jsonl_event(event_id="EV02", hash_val="b" * 64, kind="clip.added"),
    ]
    # Set prev_hash on second event
    events[1]["prev_hash"] = "a" * 64

    _write_jsonl(timeline_dir / "assembly.jsonl", events)
    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(
            event_count=2,
            version=2,
            last_event_id="EV02",
            last_hash="b" * 64,
        ),
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "pass"
    assert result["id"] == "C1"
    assert result["detail"]["timelines_checked"] == 1
    assert result["detail"]["mismatches"] == []


def test_c1_pass_empty_stream_consistent(tmp_path: Path) -> None:
    """Empty stream with null last_hash and event_count=0 → pass."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    _write_jsonl(timeline_dir / "assembly.jsonl", [])
    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(
            event_count=0,
            version=0,
            last_event_id=None,
            last_hash=None,
        ),
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "pass"
    assert result["id"] == "C1"


def test_c1_pass_multiple_timelines_all_consistent(tmp_path: Path) -> None:
    """Multiple timelines, all consistent → pass."""
    evidence_dir = tmp_path / "evidence"

    for name in ("t1", "t2"):
        td = evidence_dir / "timelines" / name
        td.mkdir(parents=True)
        events = [
            _make_jsonl_event(event_id=f"{name}-EV01", hash_val="c" * 64),
        ]
        _write_jsonl(td / "assembly.jsonl", events)
        (td / "assembly.head.json").write_text(
            _make_head_json(
                event_count=1,
                version=1,
                last_event_id=f"{name}-EV01",
                last_hash="c" * 64,
            ),
            encoding="utf-8",
        )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "pass"
    assert result["detail"]["timelines_checked"] == 2
    assert result["detail"]["mismatches"] == []


# ---------------------------------------------------------------------------
# FAIL — event_count mismatch
# ---------------------------------------------------------------------------


def test_c1_fail_event_count_mismatch(tmp_path: Path) -> None:
    """Head says 3 events, stream has 2 → fail."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    events = [
        _make_jsonl_event(event_id="EV01", hash_val="a" * 64),
    ]
    _write_jsonl(timeline_dir / "assembly.jsonl", events)
    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(
            event_count=3,
            version=3,
            last_event_id="EV03",
            last_hash="z" * 64,
        ),
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"
    assert len(result["detail"]["mismatches"]) == 1
    mismatch = result["detail"]["mismatches"][0]
    assert "event_count mismatch" in mismatch["issues"][0]


# ---------------------------------------------------------------------------
# FAIL — last_hash mismatch
# ---------------------------------------------------------------------------


def test_c1_fail_last_hash_mismatch(tmp_path: Path) -> None:
    """Head.last_hash differs from last event's hash → fail."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    events = [
        _make_jsonl_event(event_id="EV01", hash_val="a" * 64),
    ]
    _write_jsonl(timeline_dir / "assembly.jsonl", events)
    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(
            event_count=1,
            version=1,
            last_event_id="EV01",
            last_hash="b" * 64,  # wrong hash
        ),
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert any("last_hash mismatch" in issue for issue in mismatch["issues"])


# ---------------------------------------------------------------------------
# FAIL — version mismatch
# ---------------------------------------------------------------------------


def test_c1_fail_version_mismatch(tmp_path: Path) -> None:
    """Head.version differs from stream event count → fail."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    events = [
        _make_jsonl_event(event_id="EV01", hash_val="a" * 64),
    ]
    _write_jsonl(timeline_dir / "assembly.jsonl", events)
    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(
            event_count=1,
            version=5,  # wrong version
            last_event_id="EV01",
            last_hash="a" * 64,
        ),
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert any("version mismatch" in issue for issue in mismatch["issues"])


# ---------------------------------------------------------------------------
# FAIL — head exists but stream is missing
# ---------------------------------------------------------------------------


def test_c1_fail_head_exists_stream_missing(tmp_path: Path) -> None:
    """Head.json present but assembly.jsonl absent → fail."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(event_count=5, version=5, last_hash="a" * 64),
        encoding="utf-8",
    )
    # No assembly.jsonl written

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"
    mismatch = result["detail"]["mismatches"][0]
    assert "missing" in mismatch["error"]


# ---------------------------------------------------------------------------
# FAIL — head exists but stream is unparseable
# ---------------------------------------------------------------------------


def test_c1_fail_head_exists_stream_unparseable(tmp_path: Path) -> None:
    """Head.json present but assembly.jsonl is not valid JSONL → fail."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(event_count=1, version=1, last_hash="a" * 64),
        encoding="utf-8",
    )
    (timeline_dir / "assembly.jsonl").write_text("not valid json\n", encoding="utf-8")

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# FAIL — head is not a JSON object
# ---------------------------------------------------------------------------


def test_c1_fail_head_not_json_object(tmp_path: Path) -> None:
    """Head.json is valid JSON but not an object → fail."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    (timeline_dir / "assembly.head.json").write_text("[1, 2, 3]\n", encoding="utf-8")
    _write_jsonl(
        timeline_dir / "assembly.jsonl",
        [_make_jsonl_event(event_id="EV01", hash_val="a" * 64)],
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# FAIL — multiple timelines, one inconsistent
# ---------------------------------------------------------------------------


def test_c1_fail_one_of_many_inconsistent(tmp_path: Path) -> None:
    """Two timelines, one consistent and one inconsistent → fail."""
    evidence_dir = tmp_path / "evidence"

    # Consistent timeline
    td1 = evidence_dir / "timelines" / "t1"
    td1.mkdir(parents=True)
    events = [_make_jsonl_event(event_id="EV01", hash_val="a" * 64)]
    _write_jsonl(td1 / "assembly.jsonl", events)
    (td1 / "assembly.head.json").write_text(
        _make_head_json(event_count=1, version=1, last_hash="a" * 64),
        encoding="utf-8",
    )

    # Inconsistent timeline (hash mismatch)
    td2 = evidence_dir / "timelines" / "t2"
    td2.mkdir(parents=True)
    events2 = [_make_jsonl_event(event_id="EV02", hash_val="d" * 64)]
    _write_jsonl(td2 / "assembly.jsonl", events2)
    (td2 / "assembly.head.json").write_text(
        _make_head_json(event_count=1, version=1, last_hash="e" * 64),  # wrong
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "fail"
    assert result["detail"]["timelines_checked"] == 2
    assert len(result["detail"]["mismatches"]) == 1


# ---------------------------------------------------------------------------
# evidence_refs populated
# ---------------------------------------------------------------------------


def test_c1_evidence_refs_populated(tmp_path: Path) -> None:
    """Evidence refs include both head.json and assembly.jsonl paths."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)

    events = [_make_jsonl_event(event_id="EV01", hash_val="a" * 64)]
    _write_jsonl(timeline_dir / "assembly.jsonl", events)
    (timeline_dir / "assembly.head.json").write_text(
        _make_head_json(event_count=1, version=1, last_hash="a" * 64),
        encoding="utf-8",
    )

    result = c1_head_sidecar_consistency(evidence_dir)

    refs = result["evidence_refs"]
    assert "timelines/t1/assembly.head.json" in refs
    assert "timelines/t1/assembly.jsonl" in refs


# ---------------------------------------------------------------------------
# NA — timeline dir exists but no head.json
# ---------------------------------------------------------------------------


def test_c1_na_timeline_dir_without_head_json(tmp_path: Path) -> None:
    """Timeline dir exists with assembly.jsonl but no head → na (head is the trigger)."""
    evidence_dir = tmp_path / "evidence"
    timeline_dir = evidence_dir / "timelines" / "t1"
    timeline_dir.mkdir(parents=True)
    _write_jsonl(
        timeline_dir / "assembly.jsonl",
        [_make_jsonl_event(event_id="EV01", hash_val="a" * 64)],
    )
    # No head.json

    result = c1_head_sidecar_consistency(evidence_dir)

    assert result["status"] == "na"
    assert result["id"] == "C1"
