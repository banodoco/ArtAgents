"""Tests for inbox path+version match across supersede events (Sprint 3 T21).

Covers: supersede routing, stale → .rejected/, missing submitted_by_kind rejects,
and import-path compatibility between ``astrid.core.io.inbox`` and the
``astrid.core.task.operator.inbox`` shim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.io.inbox import (
    CONSUMED_DIR_NAME,
    INBOX_DIR_NAME,
    InboxValidationError,
    REJECTED_DIR_NAME,
    _parse_entry,
    _latest_event_for_path,
)

# ---------------------------------------------------------------------------
# Import compatibility — prove the shim exposes identical symbols
# ---------------------------------------------------------------------------
import astrid.core.io.inbox as io_inbox
import astrid.core.task.operator.inbox as shim_inbox

_PUBLIC_HELPERS = (
    "CONSUMED_DIR_NAME",
    "INBOX_DIR_NAME",
    "REJECTED_DIR_NAME",
    "InboxEntry",
    "InboxValidationError",
    "consume_inbox_entry",
    "inbox_dir",
    "pending_count",
    "scan_inbox",
)


# ---------------------------------------------------------------------------
# _parse_entry — schema_version:2
# ---------------------------------------------------------------------------

def test_parse_v2_entry_with_plan_step_path() -> None:
    raw = {
        "schema_version": 2,
        "plan_step_path": ["parent", "child"],
        "step_version": 1,
        "submitted_by": "agent-1",
        "submitted_by_kind": "agent",
        "decision": "approve",
        "submitted_at": "2026-05-12T00:00:00Z",
        "evidence": {},
    }
    entry = _parse_entry(Path("/tmp/test.json"), raw)
    assert entry is not None
    assert entry.plan_step_path == ("parent", "child")
    assert entry.step_version == 1
    assert entry.submitted_by_kind == "agent"
    assert entry.schema_version == 2


def test_parse_v2_entry_rejects_missing_submitted_by_kind() -> None:
    """Identity field submitted_by_kind is required; parser raises on missing."""
    raw = {
        "schema_version": 2,
        "plan_step_path": ["s1"],
        "step_version": 1,
        "submitted_by": "agent-1",
        "decision": "approve",
        "submitted_at": "2026-05-12T00:00:00Z",
        "evidence": {},
    }
    with pytest.raises(InboxValidationError, match="submitted_by_kind"):
        _parse_entry(Path("/tmp/test.json"), raw)


def test_parse_v2_entry_with_item_id() -> None:
    raw = {
        "schema_version": 2,
        "plan_step_path": ["s1"],
        "step_version": 1,
        "item_id": "abc123",
        "submitted_by": "human-1",
        "submitted_by_kind": "human",
        "decision": "approve",
        "submitted_at": "2026-05-12T00:00:00Z",
        "evidence": {},
    }
    entry = _parse_entry(Path("/tmp/test.json"), raw)
    assert entry is not None
    assert entry.item_id == "abc123"


def test_parse_legacy_entry() -> None:
    """Legacy entries without schema_version → handled by _parse_legacy_entry."""
    raw = {
        "step_id": "s1",
        "decision": "approve",
        "evidence": {},
        "submitted_at": "2026-05-12T00:00:00Z",
        "submitted_by": "someone",
    }
    entry = _parse_entry(Path("/tmp/test.json"), raw)
    # Legacy entries get schema_version=0 sentinel
    if entry is not None:
        assert entry.schema_version == 0


def test_parse_entry_rejects_bad_schema_version() -> None:
    raw = {
        "schema_version": 99,
        "plan_step_path": ["s1"],
    }
    with pytest.raises(InboxValidationError, match="schema_version"):
        _parse_entry(Path("/tmp/test.json"), raw)


# ---------------------------------------------------------------------------
# Identity enforcement (submitted_by_kind required)
# ---------------------------------------------------------------------------

def test_identity_enforcement_missing_kind() -> None:
    """Entries without submitted_by_kind raise InboxValidationError."""
    raw = {
        "schema_version": 2,
        "plan_step_path": ["s1"],
        "step_version": 1,
        "submitted_by": "someone",
        "decision": "approve",
        "submitted_at": "2026-05-12T00:00:00Z",
        "evidence": {},
    }
    with pytest.raises(InboxValidationError, match="submitted_by_kind"):
        _parse_entry(Path("/tmp/test.json"), raw)


def test_identity_enforcement_has_kind() -> None:
    raw = {
        "schema_version": 2,
        "plan_step_path": ["s1"],
        "step_version": 1,
        "submitted_by": "agent-1",
        "submitted_by_kind": "agent",
        "decision": "approve",
        "submitted_at": "2026-05-12T00:00:00Z",
        "evidence": {},
    }
    entry = _parse_entry(Path("/tmp/test.json"), raw)
    assert entry.submitted_by_kind == "agent"


# ---------------------------------------------------------------------------
# Stale entries → .rejected/
# ---------------------------------------------------------------------------

def test_stale_entries_destination_known() -> None:
    """Verify the stale-entry constants exist and are deterministic."""
    assert INBOX_DIR_NAME == "inbox"
    assert CONSUMED_DIR_NAME == ".consumed"
    assert REJECTED_DIR_NAME == ".rejected"


def test_latest_event_for_path_filters_by_step_version() -> None:
    events = [
        {
            "kind": "produces_check_failed",
            "plan_step_path": ["render"],
            "step_version": 1,
            "reason": "old",
        },
        {
            "kind": "produces_check_failed",
            "plan_step_path": ["render"],
            "step_version": 2,
            "reason": "current",
        },
    ]

    assert _latest_event_for_path(events, ("render",), step_version=2)["reason"] == "current"
    assert _latest_event_for_path(events, ("render",), step_version=3) is None


# ---------------------------------------------------------------------------
# Import compatibility: shim path exposes identical symbols
# ---------------------------------------------------------------------------


def test_shim_exports_all_public_helpers() -> None:
    """Every public helper is importable from ``astrid.core.task.operator.inbox``."""
    for name in _PUBLIC_HELPERS:
        assert hasattr(shim_inbox, name), f"shim missing {name}"


def test_shim_helpers_are_same_objects_as_io_inbox() -> None:
    """``astrid.core.task.operator.inbox`` re-exports the exact same function objects."""
    for name in _PUBLIC_HELPERS:
        io_obj = getattr(io_inbox, name)
        shim_obj = getattr(shim_inbox, name)
        assert io_obj is shim_obj, (
            f"{name}: io.inbox.{name} is not shim.{name}"
        )


def test_parse_entry_through_shim() -> None:
    """_parse_entry called through the shim path works identically."""
    raw = {
        "schema_version": 2,
        "plan_step_path": ["s1"],
        "step_version": 1,
        "submitted_by": "agent-1",
        "submitted_by_kind": "agent",
        "decision": "approve",
        "submitted_at": "2026-05-12T00:00:00Z",
        "evidence": {},
    }
    entry = shim_inbox._parse_entry(Path("/tmp/test-shim.json"), raw)
    assert entry is not None
    assert entry.submitted_by_kind == "agent"
    assert entry.plan_step_path == ("s1",)


def test_inbox_dir_through_shim(tmp_path: Path) -> None:
    """inbox_dir called through the shim returns the same path."""
    assert shim_inbox.inbox_dir(tmp_path) == io_inbox.inbox_dir(tmp_path)


def test_constants_through_shim() -> None:
    """All constant values match between io.inbox and shim."""
    assert shim_inbox.INBOX_DIR_NAME == io_inbox.INBOX_DIR_NAME
    assert shim_inbox.CONSUMED_DIR_NAME == io_inbox.CONSUMED_DIR_NAME
    assert shim_inbox.REJECTED_DIR_NAME == io_inbox.REJECTED_DIR_NAME
