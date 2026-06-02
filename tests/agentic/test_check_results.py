from __future__ import annotations

import json

import pytest

from tests.agentic.checks.results import (
    ScoredCheckResult,
    build_check_result,
    status_passes,
)


def test_build_check_result_serializes_exact_four_contract_keys() -> None:
    result = build_check_result(
        "m2.u3.chain_integrity",
        "pass",
        evidence_refs=("report.md", "runs/run-1/events.jsonl"),
        detail={"checked": 2},
    )

    assert isinstance(result, ScoredCheckResult)
    assert list(result.keys()) == ["id", "status", "evidence_refs", "detail"]
    assert result == {
        "id": "m2.u3.chain_integrity",
        "status": "pass",
        "evidence_refs": ["report.md", "runs/run-1/events.jsonl"],
        "detail": {"checked": 2},
    }
    assert "passed" not in result
    assert "undetermined" not in result


def test_scored_check_result_json_shape_excludes_boundary_scoring_keys() -> None:
    result = ScoredCheckResult(
        id="m2.c3.no_mutation_on_read",
        status="fail",
        evidence_refs=["git_diff.patch"],
        detail="unexpected mutation",
    )

    payload = json.loads(json.dumps(result))

    assert payload == {
        "id": "m2.c3.no_mutation_on_read",
        "status": "fail",
        "evidence_refs": ["git_diff.patch"],
        "detail": "unexpected mutation",
    }
    assert "passed" not in payload
    assert "undetermined" not in payload


@pytest.mark.parametrize(
    ("status", "expected"),
    [("pass", True), ("na", True), ("fail", False)],
)
def test_status_scoring_maps_pass_fail_and_na(status: str, expected: bool) -> None:
    result = ScoredCheckResult(id="m2.example", status=status, detail=None)

    assert status_passes(status) is expected
    assert result.get("passed") is expected
    assert result.get("passed", False) is expected
    assert result.get("undetermined") is False
    assert result.get("undetermined", True) is False
