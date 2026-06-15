from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.core.integrations.arnold_parity import (
    APPROVED_ARTIFACT_IGNORE_PATHS,
    DURATION_PLACEHOLDER,
    ENGINE_PLACEHOLDER,
    PATH_PLACEHOLDER,
    RUN_ID_PLACEHOLDER,
    SESSION_ID_PLACEHOLDER,
    TIMESTAMP_PLACEHOLDER,
    ParityNormalizationError,
    assert_allowed_artifact_ignores,
    load_artifact_for_parity,
    normalize_for_parity,
)


def test_parity_normalization_contract_only_allows_explicit_entropy_fields(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "projects" / "demo"
    run_root = project_root / "runs" / "run-123"

    payload = {
        "run_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
        "engine": "arnold",
        "created_at": "2026-06-13T12:00:00Z",
        "duration_ms": 913,
        "artifact_root": str(run_root),
        "session": {
            "session_id": "session-123",
            "attached_session_id": "session-123",
        },
        "artifacts": {
            "summary.json": {
                "summary": "keep this exact",
                "score": 0.91,
                "source_path": str(project_root / "content.txt"),
            }
        },
        "events": [
            {
                "ts": "2026-06-13T12:00:01Z",
                "engine_name": "task",
                "details": f"artifact at {run_root / 'summary.json'}",
            }
        ],
    }

    normalized = normalize_for_parity(
        payload,
        path_roots=[project_root, run_root],
    )

    assert normalized["run_id"] == RUN_ID_PLACEHOLDER
    assert normalized["engine"] == ENGINE_PLACEHOLDER
    assert normalized["created_at"] == TIMESTAMP_PLACEHOLDER
    assert normalized["duration_ms"] == DURATION_PLACEHOLDER
    assert normalized["session"]["session_id"] == SESSION_ID_PLACEHOLDER
    assert normalized["session"]["attached_session_id"] == SESSION_ID_PLACEHOLDER
    assert normalized["artifacts"]["summary.json"]["summary"] == "keep this exact"
    assert normalized["artifacts"]["summary.json"]["score"] == 0.91
    assert normalized["artifacts"]["summary.json"]["source_path"] == (
        f"{PATH_PLACEHOLDER}/content.txt"
    )
    assert normalized["events"][0]["ts"] == TIMESTAMP_PLACEHOLDER
    assert normalized["events"][0]["engine_name"] == ENGINE_PLACEHOLDER
    assert normalized["events"][0]["details"] == (
        f"artifact at {PATH_PLACEHOLDER}/summary.json"
    )


def test_parity_harness_rejects_unapproved_artifact_ignore_paths() -> None:
    assert APPROVED_ARTIFACT_IGNORE_PATHS == frozenset()

    with pytest.raises(ParityNormalizationError, match="not approved"):
        assert_allowed_artifact_ignores(
            [
                "artifacts.summary.json.summary",
                "artifacts.verdict.json.model",
            ]
        )

    with pytest.raises(ParityNormalizationError, match="not approved"):
        normalize_for_parity(
            {"artifacts": {"summary.json": {"summary": "text"}}},
            artifact_ignore_paths=["artifacts.summary.json.summary"],
        )


def test_load_artifact_for_parity_normalizes_common_fixture_shapes(
    tmp_path: Path,
) -> None:
    json_path = tmp_path / "artifact.json"
    json_path.write_text(json.dumps({"ok": True, "count": 2}), encoding="utf-8")

    jsonl_path = tmp_path / "events.jsonl"
    jsonl_path.write_text(
        "\n".join(
            [
                json.dumps({"kind": "run_started", "ts": "2026-06-13T12:00:00Z"}),
                json.dumps({"kind": "run_completed", "ts": "2026-06-13T12:00:01Z"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    text_path = tmp_path / "summary.txt"
    text_path.write_text("hello parity\n", encoding="utf-8")

    binary_path = tmp_path / "artifact.bin"
    binary_path.write_bytes(b"\x00\x01raw")

    assert load_artifact_for_parity(json_path) == {"ok": True, "count": 2}
    assert load_artifact_for_parity(jsonl_path) == [
        {"kind": "run_started", "ts": "2026-06-13T12:00:00Z"},
        {"kind": "run_completed", "ts": "2026-06-13T12:00:01Z"},
    ]
    assert load_artifact_for_parity(text_path) == "hello parity\n"
    assert load_artifact_for_parity(binary_path) == b"\x00\x01raw"
