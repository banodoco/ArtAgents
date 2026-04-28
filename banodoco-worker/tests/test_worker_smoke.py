"""End-to-end smoke test: synthetic task → mocked pipeline → mocked RPC write.

No network, no DB, no real pipeline — proves the wiring between the worker
modules holds.
"""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from worker_pipeline import PipelineResult
from worker_writes import apply_versioned_write_with_correlation_retry, WriteResult


CORR_ID = "33333333-3333-3333-3333-333333333333"
TIMELINE_ID = "00000000-0000-0000-0000-000000000099"


def _synthetic_task_payload() -> Dict[str, Any]:
    return {
        "intent": "extend the 2rp hype reel by 15 seconds",
        "brief_inputs": {
            "transcript": "First we built the timeline-ops package, then...",
            "sources": [{"id": "src-1", "duration": 90}],
        },
        "theme_id": "2rp",
        "expected_version": 4,
        "scope": "insert",
        "correlation_id": CORR_ID,
        "timeline_id": TIMELINE_ID,
        "project_id": "44444444-4444-4444-4444-444444444444",
        "user_jwt": "synthetic-jwt-not-verified-here",
        "current_timeline": {"clips": [], "tracks": []},
    }


def _synthetic_pipeline_result() -> PipelineResult:
    config = {
        "clips": [
            {
                "id": "clip-1",
                "at": 0,
                "from": 0,
                "to": 5,
                "track": "V1",
                "clipType": "media",
                "asset": "asset-a",
            },
            {
                "id": "clip-2",
                "at": 5,
                "from": 0,
                "to": 10,
                "track": "V1",
                "clipType": "media",
                "asset": "asset-b",
            },
        ],
        "tracks": [{"id": "V1", "kind": "visual"}],
        "theme": "2rp",
    }
    from pathlib import Path

    return PipelineResult(config=config, runs_dir=Path("/tmp/synthetic"))


def test_smoke_pipeline_to_versioned_write(monkeypatch: pytest.MonkeyPatch):
    """Synthetic task payload → pipeline (mocked) → produces TimelineConfig
    → mock RPC writes it. The contract here is:

      - The TimelineConfig coming out of the pipeline is shaped right.
      - The write helper stamps correlation_id and calls the RPC with the
        expected_version from the payload.
      - On success, the write helper reports completed + new version.
    """
    payload = _synthetic_task_payload()
    pipeline_result = _synthetic_pipeline_result()

    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = 5  # version was 4, now 5

    result: WriteResult = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=payload["timeline_id"],
        expected_version=payload["expected_version"],
        config=pipeline_result.config,
        correlation_id=payload["correlation_id"],
    )

    assert result.status == "completed"
    assert result.new_version == 5

    # Confirm the RPC saw the right primitives:
    _, kwargs = rpc.update_timeline_config_versioned.call_args
    assert kwargs["timeline_id"] == TIMELINE_ID
    assert kwargs["expected_version"] == 4
    sent_config = kwargs["config"]
    assert sent_config["clips"][0]["id"] == "clip-1"
    # And that the correlation_id was embedded BEFORE the write:
    assert sent_config["_metadata"]["correlation_id"] == CORR_ID
    # Pipeline output is unchanged (we didn't mutate the caller's config):
    assert "_metadata" not in pipeline_result.config


def test_smoke_pipeline_to_versioned_write_handles_409_retry():
    """Predecessor wrote with same correlation_id → second worker treats as success."""
    payload = _synthetic_task_payload()
    pipeline_result = _synthetic_pipeline_result()

    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = None  # 409
    # Predecessor stamped the same correlation_id
    rpc.fetch_current_config.return_value = {
        "clips": pipeline_result.config["clips"],
        "tracks": pipeline_result.config["tracks"],
        "_metadata": {"correlation_id": CORR_ID},
    }

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=payload["timeline_id"],
        expected_version=payload["expected_version"],
        config=pipeline_result.config,
        correlation_id=payload["correlation_id"],
    )

    assert result.status == "completed"


def test_smoke_pipeline_to_versioned_write_handles_user_edit_conflict():
    """User made a surgical edit during generation → version_conflict."""
    payload = _synthetic_task_payload()
    pipeline_result = _synthetic_pipeline_result()

    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = None
    # User's edit landed first; no _metadata field at all
    rpc.fetch_current_config.return_value = {
        "clips": [{"id": "user-edit", "at": 0}],
        "tracks": pipeline_result.config["tracks"],
    }

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=payload["timeline_id"],
        expected_version=payload["expected_version"],
        config=pipeline_result.config,
        correlation_id=payload["correlation_id"],
    )

    assert result.status == "version_conflict"
    assert "retry" in result.message.lower()
