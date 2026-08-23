"""S4 rework-12 — Y2 batch atomicity pin (stage-then-commit)."""
from __future__ import annotations

import json

import pytest

from astrid.core.timeline.eventlog.turso import (
    DOCUMENT_REPLICA_COLUMNS,
    EVENT_REPLICA_COLUMNS,
    FakeTursoTransport,
    TursoError,
)


def _doc_params(timeline_id: str, version: int, doc_json: str, name: str = "My Timeline") -> tuple:
    # order matches DOCUMENT_REPLICA_COLUMNS
    row = {
        "timeline_id": timeline_id,
        "project_id": "proj-1",
        "event_stream_id": "sid-1",
        "name": name,
        "document_json": doc_json,
        "version": version,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    return tuple(row[c] for c in DOCUMENT_REPLICA_COLUMNS)


def _event_params(event_id: str, payload: str = '{"a":1}', seq: int = 1) -> tuple:
    row = {
        "event_id": event_id,
        "timeline_id": "tid-1",
        "project_id": "proj-1",
        "stream_id": "sid-1",
        "seq": seq,
        "kind": "evt",
        "payload_json": payload,
        "actor_kind": "user",
        "actor_id": "u1",
        "txn_id": "txn1",
        "idempotency_key": "ik1",
        "created_at": "2026-01-01T00:00:00Z",
    }
    return tuple(row[c] for c in EVENT_REPLICA_COLUMNS)


def _doc_sql() -> str:
    cols = ", ".join(DOCUMENT_REPLICA_COLUMNS)
    placeholders = ", ".join("?" for _ in DOCUMENT_REPLICA_COLUMNS)
    return f"INSERT INTO documents ({cols}) VALUES ({placeholders})"


def _event_sql() -> str:
    cols = ", ".join(EVENT_REPLICA_COLUMNS)
    placeholders = ", ".join("?" for _ in EVENT_REPLICA_COLUMNS)
    return f"INSERT INTO events ({cols}) VALUES ({placeholders})"


class TestY2BatchAtomicityDuplicateLeavesDocumentUnchanged:
    def test_duplicate_event_in_batch_does_not_mutate_document(self):
        tr = FakeTursoTransport()
        v1_json = json.dumps({"foo": 1}, sort_keys=True)
        v2_json = json.dumps({"foo": 2}, sort_keys=True)
        # seed v1 doc + E1
        tr.execute_batch([
            (_doc_sql(), _doc_params("tid-1", 1, v1_json)),
            (_event_sql(), _event_params("E1", '{"a":1}', seq=1)),
        ])
        # snapshot pre-batch
        pre_docs = {k: dict(v) for k, v in tr.documents.items()}
        pre_events = {k: dict(v) for k, v in tr.events.items()}
        assert pre_docs["tid-1"]["version"] == 1
        assert pre_docs["tid-1"]["document_json"] == v1_json
        assert len(pre_events) == 1

        # failing batch: v2 doc + duplicate E1
        with pytest.raises(TursoError, match="duplicate event_id"):
            tr.execute_batch([
                (_doc_sql(), _doc_params("tid-1", 2, v2_json)),
                (_event_sql(), _event_params("E1", '{"a":2}', seq=2)),
            ])

        # document byte-equal v1
        cur = tr.documents["tid-1"]
        assert cur["version"] == 1
        assert cur["document_json"] == v1_json
        assert cur["name"] == "My Timeline"
        assert tr.documents == pre_docs
        assert tr.events == pre_events
        assert len(tr.events) == 1

    def test_valid_batch_still_commits_doc_and_events(self):
        tr = FakeTursoTransport()
        v1_json = json.dumps({"foo": 1}, sort_keys=True)
        v2_json = json.dumps({"foo": 2}, sort_keys=True)
        tr.execute_batch([
            (_doc_sql(), _doc_params("tid-1", 1, v1_json)),
            (_event_sql(), _event_params("E1", '{"a":1}', seq=1)),
        ])
        # valid batch: v2 doc + new E2
        tr.execute_batch([
            (_doc_sql(), _doc_params("tid-1", 2, v2_json)),
            (_event_sql(), _event_params("E2", '{"a":2}', seq=2)),
        ])
        assert tr.documents["tid-1"]["version"] == 2
        assert tr.documents["tid-1"]["document_json"] == v2_json
        assert len(tr.events) == 2
        assert "E2" in tr.events
