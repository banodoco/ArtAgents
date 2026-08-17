"""Canonical request identity and receipt replay tests (m1 plan step 9, T20).

This suite proves the exactly-once contract of the receipt kernel:

- canonical JSON equivalence: semantically identical requests (key order and
  whitespace differences, unicode) hash identically;
- meaningful changes: any semantic difference changes the hash, and the
  command kind participates;
- invalid values and bounds: NaN/Infinity, invalid UTF-8, oversized inputs
  and outputs, non-string object keys, excessive nesting depth, non-JSON
  values, and malformed request arguments all raise the typed
  :class:`CanonicalizationError`;
- exact stored-result replay: an identical retry returns exactly the stored
  complete result without inserting a second receipt row;
- mismatch-before-mutation: reusing an idempotency key with a different
  request hash or command kind raises :class:`ReceiptMismatchError` before
  any sequence allocation or projection change (project head and receipt
  count stay unchanged);
- complete internal receipt fields: transaction ID, primary stream and
  resulting sequence, exact project sequence range, ordered event IDs,
  request hash, command kind, result JSON, and created_at are all persisted;
- generated values are not part of request identity: timestamps and
  transaction/event IDs are stripped recursively before hashing.

Plan-step-10 (T22) event-append semantics live in this file too: genesis-to-head
hash-chain recomputation, tamper rejection for domain data and both integrity
fields, canonical timestamps/IDs, cross-transaction chaining, and rollback that
leaves events, projections, heads, and receipts unchanged.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from astrid.core.events.service import (
    EventAppendResult,
    EventAppendService,
    EventChainError,
)
from astrid.core.receipts import (
    CanonicalizationError,
    MAX_CANONICAL_DEPTH,
    ReceiptMismatchError,
    ReceiptService,
    ReceiptValidationError,
    canonical_bytes,
    canonical_json,
    parse_json,
    request_hash,
    strip_generated_fields,
)
from astrid.core.store.uow import UnitOfWork
from astrid.core.store.writer import DatabaseWriter

TS = "2026-08-15T00:00:00.000000+00:00"


def _insert_project(executor, project_id: str) -> None:
    """Insert a minimal valid projects row through any typed executor."""
    executor.execute(
        "INSERT INTO projects (id, slug, name, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (project_id, project_id, project_id, TS, TS),
    )


def _insert_stream(executor, stream_id: str, project_id: str) -> None:
    """Insert a minimal valid core.project event_streams row."""
    executor.execute(
        "INSERT INTO event_streams "
        "(id, project_id, stream_type, aggregate_id, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (stream_id, project_id, "core.project", project_id, TS),
    )


@pytest.fixture
def writer(tmp_path, core_registry):
    """A fresh writer over a kernel-only database at ``<tmp>/receipts.sqlite3``."""
    db_path = tmp_path / "receipts.sqlite3"
    w = DatabaseWriter(db_path, core_registry)
    try:
        yield w
    finally:
        w.close()


# ---------------------------------------------------------------------------
# Equivalent encodings
# ---------------------------------------------------------------------------


def test_canonical_json_equivalent_encodings_are_identical() -> None:
    first = {
        "b": 1,
        "a": [2, 3],
        "nested": {"z": None, "y": "snowman: \u2603"},
    }
    reordered = {
        "a": [2, 3],
        "b": 1,
        "nested": {"y": "snowman: \u2603", "z": None},
    }
    assert canonical_json(first) == canonical_json(reordered)
    assert canonical_bytes(first) == canonical_bytes(reordered)
    # Sorted keys with compact separators and unicode preserved.
    assert canonical_json(first) == (
        '{"a":[2,3],"b":1,"nested":{"y":"snowman: \u2603","z":null}}'
    )
    # Whitespace / separator variants parse to the same canonical form.
    assert canonical_json(parse_json(' { "b" : 1 , "a" : [ 2 , 3 ] } ')) == (
        '{"a":[2,3],"b":1}'
    )


def test_request_hash_equivalent_encodings_match() -> None:
    base = {"project_id": "proj-1", "name": "Pilot", "fps": 24}
    reordered = {"fps": 24, "name": "Pilot", "project_id": "proj-1"}
    pretty = json.dumps(base, indent=4, sort_keys=False)
    assert request_hash("timeline.create", base) == request_hash(
        "timeline.create", reordered
    )
    assert request_hash("timeline.create", base) == request_hash(
        "timeline.create", parse_json(pretty)
    )
    # Unicode round-trips through parse_json without changing the hash.
    unicode_req = {"name": "S\u00e9ance", "tags": ["\u2603", "caf\u00e9"]}
    assert request_hash("timeline.create", unicode_req) == request_hash(
        "timeline.create", parse_json(json.dumps(unicode_req, ensure_ascii=True))
    )


# ---------------------------------------------------------------------------
# Meaningful changes
# ---------------------------------------------------------------------------


def test_request_hash_detects_meaningful_changes() -> None:
    base = {"project_id": "proj-1", "name": "Pilot", "fps": 24}
    changed = [
        {"project_id": "proj-2", "name": "Pilot", "fps": 24},
        {"project_id": "proj-1", "name": "Pilot 2", "fps": 24},
        {"project_id": "proj-1", "name": "Pilot", "fps": 25},
        {"project_id": "proj-1", "name": "Pilot", "fps": 24, "extra": 1},
        {"project_id": "proj-1", "name": "Pilot"},
    ]
    hashes = {request_hash("timeline.create", base)}
    for variant in changed:
        hashes.add(request_hash("timeline.create", variant))
    assert len(hashes) == 1 + len(changed)


def test_request_hash_includes_command_kind() -> None:
    request = {"project_id": "proj-1", "name": "Pilot"}
    assert request_hash("timeline.create", request) != request_hash(
        "timeline.save", request
    )
    assert request_hash("core.project.create", request) != request_hash(
        "timeline.create", request
    )


def test_strip_generated_fields_removes_nested_generated_values() -> None:
    value = {
        "project_id": "proj-1",
        "created_at": "2026-08-15T05:00:00Z",
        "meta": {"updated_at": "x", "keep": 1},
        "items": [{"txn_id": "t1", "v": 2}, {"v": 3}],
    }
    stripped = strip_generated_fields(value)
    assert stripped == {
        "project_id": "proj-1",
        "meta": {"keep": 1},
        "items": [{"v": 2}, {"v": 3}],
    }


# ---------------------------------------------------------------------------
# Invalid values and bounds
# ---------------------------------------------------------------------------


def test_parse_json_rejects_nan_infinity_and_invalid_json() -> None:
    for text in (
        "NaN",
        "Infinity",
        "-Infinity",
        "[1, NaN]",
        '{"x": Infinity}',
        "not json",
        "",
        "[1,]",
        "{",
    ):
        with pytest.raises(CanonicalizationError):
            parse_json(text)


def test_parse_json_rejects_oversized_and_non_utf8_input() -> None:
    with pytest.raises(CanonicalizationError, match="exceeds"):
        parse_json("[" + ",".join(["0"] * 1000) + "]", max_bytes=512)
    with pytest.raises(CanonicalizationError, match="exceeds"):
        parse_json(b"[" + b"0" * 513, max_bytes=512)
    with pytest.raises(CanonicalizationError, match="UTF-8"):
        parse_json(b"\xff\xfe\x00")


def test_canonical_json_rejects_non_json_values_and_keys() -> None:
    with pytest.raises(CanonicalizationError, match="not JSON-serializable"):
        canonical_json({"x": object()})
    with pytest.raises(CanonicalizationError, match="non-finite"):
        canonical_json(float("nan"))
    with pytest.raises(CanonicalizationError, match="non-finite"):
        canonical_json([float("inf")])
    with pytest.raises(CanonicalizationError, match="keys must be strings"):
        canonical_json({1: "one"})


def test_canonical_json_rejects_excessive_nesting_depth() -> None:
    deep: dict = {}
    current = deep
    for _ in range(MAX_CANONICAL_DEPTH + 2):
        current["next"] = {}
        current = current["next"]
    with pytest.raises(CanonicalizationError, match="nesting depth"):
        canonical_json(deep)


def test_canonical_json_rejects_oversized_output() -> None:
    with pytest.raises(CanonicalizationError, match="exceeds"):
        canonical_json({"data": "x" * 4096}, max_bytes=1024)


def test_request_hash_rejects_invalid_arguments_and_bounds() -> None:
    with pytest.raises(CanonicalizationError, match="command_kind"):
        request_hash("", {"a": 1})
    with pytest.raises(CanonicalizationError, match="command_kind"):
        request_hash(123, {"a": 1})
    with pytest.raises(CanonicalizationError, match="JSON object"):
        request_hash("timeline.create", [1, 2])
    with pytest.raises(CanonicalizationError, match="non-finite"):
        request_hash("timeline.create", {"a": float("nan")})
    with pytest.raises(CanonicalizationError, match="exceeds"):
        request_hash(
            "timeline.create", {"data": "x" * 4096}, max_bytes=1024
        )


# ---------------------------------------------------------------------------
# Generated values are absent from request identity
# ---------------------------------------------------------------------------


def test_request_hash_excludes_generated_timestamps_and_transaction_ids() -> None:
    semantic = {"project_id": "proj-1", "name": "Pilot"}
    with_generated = {
        "project_id": "proj-1",
        "name": "Pilot",
        "created_at": "2026-08-15T05:00:00Z",
        "updated_at": "2026-08-15T06:00:00Z",
        "txn_id": "txn-abc",
        "transaction_id": "txn-abc",
        "event_id": "ev-1",
        "receipt_id": "r-1",
    }
    assert request_hash("timeline.create", semantic) == request_hash(
        "timeline.create", with_generated
    )
    # The exclusion is recursive: nested generated fields are stripped too.
    nested = {"project_id": "proj-1", "details": {"created_at": "x", "name": "Pilot"}}
    semantic_nested = {"project_id": "proj-1", "details": {"name": "Pilot"}}
    assert request_hash("timeline.create", nested) == request_hash(
        "timeline.create", semantic_nested
    )
    # Only the configured names are excluded: a generated-looking value under
    # a different key still participates.
    kept = {"project_id": "proj-1", "name": "Pilot", "client_ts": "2026-08-15T05:00:00Z"}
    assert request_hash("timeline.create", semantic) != request_hash(
        "timeline.create", kept
    )


def test_request_hash_respects_custom_exclude_fields() -> None:
    base = {"name": "Pilot", "request_id": "abc"}
    custom = frozenset({"request_id"})
    assert request_hash("timeline.create", base, exclude_fields=custom) == (
        request_hash("timeline.create", {"name": "Pilot"}, exclude_fields=custom)
    )
    # The default exclusion set does not drop request_id.
    assert request_hash("timeline.create", base) != request_hash(
        "timeline.create", {"name": "Pilot"}
    )


# ---------------------------------------------------------------------------
# Receipt replay and mismatch-before-mutation (real database)
# ---------------------------------------------------------------------------


def _seed_project_and_stream(writer: DatabaseWriter) -> None:
    writer.submit(
        lambda session: (
            _insert_project(session, "proj-1"),
            _insert_stream(session, "stream-1", "proj-1"),
        )
    )


def _record(
    uow: UnitOfWork,
    service: ReceiptService,
    *,
    idempotency_key: str = "k-1",
    request_hash: str = "h-1",
    command_kind: str = "core.project.create",
    txn_id: str = "txn-1",
    result: dict | None = None,
) -> None:
    service.record(
        uow,
        project_id="proj-1",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        command_kind=command_kind,
        txn_id=txn_id,
        first_project_seq=1,
        last_project_seq=2,
        event_ids=["ev-1", "ev-2"],
        result=result if result is not None else {"id": "proj-1", "slug": "pilot"},
        primary_stream_id="stream-1",
        resulting_stream_seq=1,
    )


def test_receipt_check_returns_none_for_unknown_key(writer: DatabaseWriter) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()
    uow = UnitOfWork(writer)
    result = uow.run(
        lambda u: service.check(
            u,
            project_id="proj-1",
            idempotency_key="missing",
            request_hash="h-1",
            command_kind="core.project.create",
        )
    )
    assert result is None


def test_receipt_replay_returns_exact_stored_result(writer: DatabaseWriter) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()
    expected = {"id": "proj-1", "slug": "pilot", "settings": {"fps": 24}}

    UnitOfWork(writer).run(lambda u: _record(u, service, result=expected))

    # Identical retry in a fresh unit of work returns exactly the stored result.
    replayed = UnitOfWork(writer).run(
        lambda u: service.check(
            u,
            project_id="proj-1",
            idempotency_key="k-1",
            request_hash="h-1",
            command_kind="core.project.create",
        )
    )
    assert replayed == expected
    # Replay performs only a read: still exactly one receipt row.
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM command_receipts")[0]
    )
    assert count == 1


def test_receipt_mismatch_before_mutation_changes_zero_rows(
    writer: DatabaseWriter,
) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()
    UnitOfWork(writer).run(lambda u: _record(u, service))

    before = writer.submit(
        lambda session: (
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )
    assert before == (0, 1)

    # Different request hash with the same key: rejected before any mutation.
    with pytest.raises(ReceiptMismatchError, match="different request"):
        UnitOfWork(writer).run(
            lambda u: (
                service.check(
                    u,
                    project_id="proj-1",
                    idempotency_key="k-1",
                    request_hash="h-DIFFERENT",
                    command_kind="core.project.create",
                ),
                # Never reached: the mismatch raises before any allocation.
                u.next_project_seq("proj-1"),
            )
        )
    # Different command kind with the same key: rejected before any mutation.
    with pytest.raises(ReceiptMismatchError, match="different request"):
        UnitOfWork(writer).run(
            lambda u: (
                service.check(
                    u,
                    project_id="proj-1",
                    idempotency_key="k-1",
                    request_hash="h-1",
                    command_kind="timeline.save",
                ),
                u.next_project_seq("proj-1"),
            )
        )
    after = writer.submit(
        lambda session: (
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )
    assert after == before == (0, 1)


def test_receipt_persists_complete_internal_fields(writer: DatabaseWriter) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()
    created_at = "2026-08-15T05:00:00.000000Z"
    result = {"id": "proj-1", "slug": "pilot", "nested": {"a": [1, 2]}}
    UnitOfWork(writer).run(
        lambda u: service.record(
            u,
            project_id="proj-1",
            idempotency_key="k-full",
            request_hash="h-full",
            command_kind="timeline.create",
            txn_id="txn-full",
            first_project_seq=3,
            last_project_seq=5,
            event_ids=["ev-3", "ev-4", "ev-5"],
            result=result,
            primary_stream_id="stream-1",
            resulting_stream_seq=7,
            created_at=created_at,
        )
    )
    row = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM command_receipts "
            "WHERE project_id = 'proj-1' AND idempotency_key = 'k-full'"
        )
    )
    assert row["txn_id"] == "txn-full"
    assert row["request_hash"] == "h-full"
    assert row["command_kind"] == "timeline.create"
    assert row["primary_stream_id"] == "stream-1"
    assert row["resulting_stream_seq"] == 7
    assert row["first_project_seq"] == 3
    assert row["last_project_seq"] == 5
    assert json.loads(row["event_ids_json"]) == ["ev-3", "ev-4", "ev-5"]
    assert json.loads(row["result_json"]) == result
    assert row["created_at"] == created_at


def test_receipt_created_at_defaults_to_canonical_utc(writer: DatabaseWriter) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()
    UnitOfWork(writer).run(lambda u: _record(u, service))
    row = writer.submit(
        lambda session: session.query_one(
            "SELECT created_at FROM command_receipts "
            "WHERE project_id = 'proj-1' AND idempotency_key = 'k-1'"
        )
    )
    stamp = row["created_at"]
    assert stamp
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None


def test_receipt_validation_rejects_bad_values_with_zero_mutation(
    writer: DatabaseWriter,
) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()
    before = writer.submit(
        lambda session: (
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )

    def attempt(**overrides) -> None:
        args = {
            "project_id": "proj-1",
            "idempotency_key": "k-bad",
            "request_hash": "h-bad",
            "command_kind": "core.project.create",
            "txn_id": "txn-bad",
            "first_project_seq": 1,
            "last_project_seq": 1,
            "event_ids": ["ev-bad"],
            "result": {"ok": True},
        }
        args.update(overrides)
        UnitOfWork(writer).run(lambda u: service.record(u, **args))

    with pytest.raises(ReceiptValidationError, match="last_project_seq"):
        attempt(first_project_seq=5, last_project_seq=1)
    with pytest.raises(ReceiptValidationError, match="txn_id"):
        attempt(txn_id="")
    with pytest.raises(ReceiptValidationError, match="event_ids"):
        attempt(event_ids=["ev-bad", 7])
    with pytest.raises(ReceiptValidationError, match="project_id"):
        attempt(project_id="")
    with pytest.raises(ReceiptValidationError, match="cannot serialize"):
        attempt(result={"x": float("nan")})

    after = writer.submit(
        lambda session: (
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )
    assert after == before == (0, 0)


def test_receipt_rollback_discards_receipt_atomically(
    writer: DatabaseWriter,
) -> None:
    _seed_project_and_stream(writer)
    service = ReceiptService()

    def fail_after_record(u: UnitOfWork) -> None:
        _record(u, service, idempotency_key="k-rollback", txn_id="txn-rb")
        raise RuntimeError("abort")

    with pytest.raises(RuntimeError, match="abort"):
        UnitOfWork(writer).run(fail_after_record)
    count = writer.submit(
        lambda session: session.query_one("SELECT count(*) FROM command_receipts")[0]
    )
    assert count == 0


# ---------------------------------------------------------------------------
# Event append: genesis-to-head chain verification (m1 plan step 10, T22)
# ---------------------------------------------------------------------------


def _append_event(
    uow: UnitOfWork,
    service: EventAppendService,
    *,
    seq_no: int,
    name: str = "Pilot",
) -> EventAppendResult:
    """Append one registered core.project.created event on the seeded stream."""
    return service.append(
        uow,
        stream_id="stream-1",
        project_id="proj-1",
        event_kind="core.project.created",
        data={"name": name, "seq_no": seq_no},
        changes=["name"],
        idempotency_key=f"ev-k-{seq_no}",
        txn_id=f"txn-{seq_no}",
        actor_kind="local",
        command_kind="core.project.create",
    )


def test_event_append_chain_recomputes_from_genesis_to_head(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)

    results = UnitOfWork(writer).run(
        lambda u: [_append_event(u, service, seq_no=seq) for seq in (1, 2, 3)]
    )

    # Genesis event has no previous hash; later links chain to the prior
    # event's stored hash, and every hash is a 64-char lowercase hex digest.
    assert results[0].previous_event_hash is None
    assert results[0].project_seq == 1 and results[0].stream_seq == 1
    assert results[1].previous_event_hash == results[0].event_hash
    assert results[2].previous_event_hash == results[1].event_hash
    for result in results:
        assert re.fullmatch(r"[0-9a-f]{64}", result.event_hash)

    # Recomputing every link from genesis through the head passes and
    # reports the exact head hash of the final event.
    verification = service.verify_stream(writer, "stream-1")
    assert verification.event_count == 3
    assert verification.head_seq == 3
    assert verification.head_hash == results[-1].event_hash

    # Both heads advanced together: projects.event_head_seq and
    # event_streams.head_seq both reached 3 in the same transaction.
    heads = writer.submit(
        lambda session: (
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one(
                "SELECT head_seq FROM event_streams WHERE id = 'stream-1'"
            )[0],
        )
    )
    assert heads == (3, 3)


def test_event_chain_spans_committed_transactions(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)

    first = UnitOfWork(writer).run(
        lambda u: _append_event(u, service, seq_no=1)
    )
    second = UnitOfWork(writer).run(
        lambda u: _append_event(u, service, seq_no=2)
    )

    # The chain links across committed transactions: the second append
    # derives its previous_event_hash from the first event's committed hash.
    assert second.previous_event_hash == first.event_hash
    verification = service.verify_stream(writer, "stream-1")
    assert verification.event_count == 2
    assert verification.head_seq == 2
    assert verification.head_hash == second.event_hash


def test_verify_stream_rejects_domain_data_tampering(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)
    UnitOfWork(writer).run(
        lambda u: [_append_event(u, service, seq_no=seq) for seq in (1, 2, 3)]
    )

    # Tamper the middle event's domain data (still valid JSON, still shaped
    # like a payload): verification must fail at that event, not pass.
    def tamper(session) -> None:
        row = session.query_one(
            "SELECT payload_json FROM events "
            "WHERE stream_id = 'stream-1' AND seq = 2"
        )
        payload = json.loads(row["payload_json"])
        payload["data"]["name"] = "TAMPERED"
        session.execute(
            "UPDATE events SET payload_json = ? "
            "WHERE stream_id = 'stream-1' AND seq = 2",
            (json.dumps(payload, sort_keys=True),),
        )

    writer.submit(tamper)
    with pytest.raises(EventChainError) as excinfo:
        service.verify_stream(writer, "stream-1")
    assert excinfo.value.position == 1
    assert "mismatch" in excinfo.value.reason


def test_verify_stream_rejects_event_hash_tampering(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)
    UnitOfWork(writer).run(
        lambda u: [_append_event(u, service, seq_no=seq) for seq in (1, 2)]
    )

    # Tamper the integrity field itself: replace the genesis event's stored
    # event_hash. Verification fails at the genesis position.
    def tamper(session) -> None:
        row = session.query_one(
            "SELECT payload_json FROM events "
            "WHERE stream_id = 'stream-1' AND seq = 1"
        )
        payload = json.loads(row["payload_json"])
        payload["_integrity"]["event_hash"] = "0" * 64
        session.execute(
            "UPDATE events SET payload_json = ? "
            "WHERE stream_id = 'stream-1' AND seq = 1",
            (json.dumps(payload, sort_keys=True),),
        )

    writer.submit(tamper)
    with pytest.raises(EventChainError) as excinfo:
        service.verify_stream(writer, "stream-1")
    assert excinfo.value.position == 0
    assert "event_hash mismatch" in excinfo.value.reason


def test_verify_stream_rejects_previous_hash_tampering(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)
    UnitOfWork(writer).run(
        lambda u: [_append_event(u, service, seq_no=seq) for seq in (1, 2)]
    )

    # Rewrite the second event's previous_event_hash: the link from the
    # genesis event is broken, so verification fails at the second event.
    def tamper(session) -> None:
        row = session.query_one(
            "SELECT payload_json FROM events "
            "WHERE stream_id = 'stream-1' AND seq = 2"
        )
        payload = json.loads(row["payload_json"])
        payload["_integrity"]["previous_event_hash"] = "f" * 64
        session.execute(
            "UPDATE events SET payload_json = ? "
            "WHERE stream_id = 'stream-1' AND seq = 2",
            (json.dumps(payload, sort_keys=True),),
        )

    writer.submit(tamper)
    with pytest.raises(EventChainError) as excinfo:
        service.verify_stream(writer, "stream-1")
    assert excinfo.value.position == 1
    assert "previous_event_hash mismatch" in excinfo.value.reason


def test_verify_stream_rejects_valid_looking_envelope_with_wrong_hashes(
    writer: DatabaseWriter, core_registry
) -> None:
    """NSA-2: presence of the integrity fields is never proof by itself."""
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)
    UnitOfWork(writer).run(lambda u: _append_event(u, service, seq_no=1))

    # Replace the payload with a structurally complete envelope whose hashes
    # do not recompute. A check that only verified field presence would pass;
    # the executable gate must fail.
    forged = {
        "data": {"name": "Pilot", "seq_no": 1},
        "_integrity": {
            "previous_event_hash": None,
            "event_hash": "ab" * 32,
        },
    }
    writer.submit(
        lambda session: session.execute(
            "UPDATE events SET payload_json = ? "
            "WHERE stream_id = 'stream-1' AND seq = 1",
            (json.dumps(forged, sort_keys=True),),
        )
    )
    with pytest.raises(EventChainError, match="event_hash mismatch"):
        service.verify_stream(writer, "stream-1")


def test_event_append_generates_canonical_timestamps_and_ids(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)

    result = UnitOfWork(writer).run(
        lambda u: _append_event(u, service, seq_no=1)
    )

    # event_id is a 32-char lowercase hex uuid4; created_at is canonical
    # UTC ISO-8601 with a timezone.
    assert re.fullmatch(r"[0-9a-f]{32}", result.event_id)
    parsed = datetime.fromisoformat(result.created_at.replace("Z", "+00:00"))
    assert parsed.tzinfo is not None

    # The stored row carries the same canonical values, plus the registered
    # vocabulary (kind/actor) and the registry-derived subject of the
    # core.project aggregate.
    row = writer.submit(
        lambda session: session.query_one(
            "SELECT * FROM events WHERE stream_id = 'stream-1' AND seq = 1"
        )
    )
    assert row["event_id"] == result.event_id
    assert row["created_at"] == result.created_at
    assert row["payload_json"] == result.payload_json
    assert row["kind"] == "core.project.created"
    assert row["actor_kind"] == "local"
    assert row["subject_type"] == "project"
    assert row["subject_id"] == "proj-1"
    assert row["schema_version"] == 1


def test_event_rollback_leaves_events_projections_heads_and_receipts_unchanged(
    writer: DatabaseWriter, core_registry
) -> None:
    _seed_project_and_stream(writer)
    service = EventAppendService(core_registry)
    receipts = ReceiptService()

    def failing_command(u: UnitOfWork) -> None:
        _append_event(u, service, seq_no=1)
        # A projection update inside the same transaction (read model write).
        u.update_projection("projects", {"name": "Changed"}, {"id": "proj-1"})
        receipts.record(
            u,
            project_id="proj-1",
            idempotency_key="k-ev-rb",
            request_hash="h-ev-rb",
            command_kind="core.project.create",
            txn_id="txn-ev-rb",
            first_project_seq=1,
            last_project_seq=1,
            event_ids=["ev-rb"],
            result={"id": "proj-1"},
        )
        raise RuntimeError("abort command")

    with pytest.raises(RuntimeError, match="abort command"):
        UnitOfWork(writer).run(failing_command)

    # Rollback leaves events, the projection, both heads, and the receipt
    # exactly as they were before the command.
    state = writer.submit(
        lambda session: (
            session.query_one("SELECT count(*) FROM events")[0],
            session.query_one(
                "SELECT name FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one(
                "SELECT event_head_seq FROM projects WHERE id = 'proj-1'"
            )[0],
            session.query_one(
                "SELECT head_seq FROM event_streams WHERE id = 'stream-1'"
            )[0],
            session.query_one("SELECT count(*) FROM command_receipts")[0],
        )
    )
    assert state == (0, "proj-1", 0, 0, 0)
