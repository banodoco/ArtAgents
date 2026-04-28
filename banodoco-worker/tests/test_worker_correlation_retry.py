"""SD-034 correlation_id retry semantics tests."""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import MagicMock

from worker_writes import (
    CORRELATION_ID_CONFIG_KEY,
    CORRELATION_ID_FIELD,
    apply_versioned_write_with_correlation_retry,
    embed_correlation_id,
    extract_correlation_id,
)


CORR_ID_A = "11111111-1111-1111-1111-111111111111"
CORR_ID_B = "22222222-2222-2222-2222-222222222222"
TIMELINE_ID = "00000000-0000-0000-0000-000000000001"


def _config(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = {"clips": [], "tracks": [{"id": "V1", "kind": "visual"}]}
    if extra:
        base.update(extra)
    return base


def test_embed_correlation_id_stamps_metadata():
    config = _config()
    stamped = embed_correlation_id(config, CORR_ID_A)
    assert stamped is not config  # never mutates input
    assert stamped[CORRELATION_ID_CONFIG_KEY][CORRELATION_ID_FIELD] == CORR_ID_A


def test_embed_correlation_id_idempotent():
    config = _config()
    once = embed_correlation_id(config, CORR_ID_A)
    twice = embed_correlation_id(once, CORR_ID_A)
    assert once == twice


def test_extract_correlation_id_returns_none_when_absent():
    assert extract_correlation_id(_config()) is None


def test_extract_correlation_id_round_trips():
    stamped = embed_correlation_id(_config(), CORR_ID_A)
    assert extract_correlation_id(stamped) == CORR_ID_A


def test_apply_versioned_write_completed_path():
    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = 8

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=TIMELINE_ID,
        expected_version=7,
        config=_config(),
        correlation_id=CORR_ID_A,
    )

    assert result.status == "completed"
    assert result.new_version == 8

    args, kwargs = rpc.update_timeline_config_versioned.call_args
    sent_config = kwargs["config"]
    assert sent_config[CORRELATION_ID_CONFIG_KEY][CORRELATION_ID_FIELD] == CORR_ID_A


def test_apply_versioned_write_409_with_same_correlation_id_treated_as_success():
    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = None  # 409
    rpc.fetch_current_config.return_value = embed_correlation_id(_config(), CORR_ID_A)

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=TIMELINE_ID,
        expected_version=7,
        config=_config(),
        correlation_id=CORR_ID_A,
    )

    assert result.status == "completed"
    # No new_version — predecessor wrote it; agent reports success without
    # the bump.
    assert result.new_version is None


def test_apply_versioned_write_409_with_different_correlation_id_returns_version_conflict():
    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = None
    # Existing config carries a *different* correlation_id (= the user's
    # surgical edit, or another agent's run).
    rpc.fetch_current_config.return_value = embed_correlation_id(_config(), CORR_ID_B)

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=TIMELINE_ID,
        expected_version=7,
        config=_config(),
        correlation_id=CORR_ID_A,
    )

    assert result.status == "version_conflict"
    assert "edits superseded" in result.message.lower()


def test_apply_versioned_write_409_with_no_correlation_id_in_existing_config():
    """If the racing writer was the user (no correlation_id stamped), the
    config-level metadata is missing — same outcome as a different id."""
    rpc = MagicMock()
    rpc.update_timeline_config_versioned.return_value = None
    rpc.fetch_current_config.return_value = _config()  # no _metadata

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=TIMELINE_ID,
        expected_version=7,
        config=_config(),
        correlation_id=CORR_ID_A,
    )

    assert result.status == "version_conflict"


def test_apply_versioned_write_rpc_raise_returns_rpc_failure():
    rpc = MagicMock()
    rpc.update_timeline_config_versioned.side_effect = RuntimeError("connection reset")

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=TIMELINE_ID,
        expected_version=7,
        config=_config(),
        correlation_id=CORR_ID_A,
    )

    assert result.status == "rpc_failure"
    assert "connection reset" in result.message


def test_apply_versioned_write_missing_correlation_id_is_programmer_error():
    rpc = MagicMock()

    result = apply_versioned_write_with_correlation_retry(
        rpc=rpc,
        timeline_id=TIMELINE_ID,
        expected_version=7,
        config=_config(),
        correlation_id="",
    )
    assert result.status == "rpc_failure"
    assert "correlation_id" in result.message
    rpc.update_timeline_config_versioned.assert_not_called()
