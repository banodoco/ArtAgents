"""S1 zero-loss invariant suite for the SQLite-cutover backfill.

Covers the reusable checker (a)-(e) plus the marker discipline (f):

a. source event count == kernel event count for the mapped stream;
b. head continuity: source ``assembly.head.json`` version ==
   ``event_streams.head_seq`` after import;
c. content projection: canonical equality of every preserved field
   (kind, payload data, actor_kind, created_at, event_id);
d. idempotency: the same import twice yields ZERO new kernel events and an
   unchanged head;
e. unknown-kind pass-through: per-kind counts preserved, including kinds the
   timeline schema does not register;
f. marker written only after all checks pass; a failed import writes no
   marker and leaves no partial authority claim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from astrid.core.receipts.canonical import canonical_json
from astrid.packs.timeline.backfill import (
    BackfillAuthorityError,
    BackfillDiscrepancyError,
    BackfillError,
    backfill_timeline,
    verify_backfill,
)
from astrid.packs.timeline.repository import TIMELINE_STREAM_TYPE

from ._backfill_helpers import (
    head_seq,
    kernel_event_rows,
    make_backfill_deps,
    make_project,
    make_source_timeline,
    make_writer,
    marker_json,
    marker_state,
    project_root_with_timeline,
)


def _import(
    tmp_path: Path,
    *,
    project_slug: str = "proj",
    events_spec=None,
    dry_run: bool = False,
    on_before_append=None,
):
    """One complete import: fresh DB + project + source -> backfill report.

    The writer is left open for follow-up assertions; callers close it.
    """
    projects_root, home, timeline_id, timeline_ulid = project_root_with_timeline(
        tmp_path, project_slug=project_slug, events_spec=events_spec
    )
    writer = make_writer(projects_root / ".astrid" / "astrid.sqlite3")
    make_project(writer, slug=project_slug)
    projects, receipts, _timelines = make_backfill_deps(writer)
    from astrid.packs.timeline.backfill import load_local_fs_source

    source = load_local_fs_source(home)
    report = backfill_timeline(
        writer=writer,
        projects=projects,
        receipts=receipts,
        project_slug=project_slug,
        source=source,
        projects_root=projects_root,
        dry_run=dry_run,
        on_before_append=on_before_append,
    )
    stream_id = f"{timeline_id}:{TIMELINE_STREAM_TYPE}"
    return report, source, writer, projects_root, stream_id, timeline_id


# ---------------------------------------------------------------------------
# (a) count, (b) head, (e) kinds — the numbers a judge quotes
# ---------------------------------------------------------------------------


def test_invariants_count_head_kinds_quote_numbers(tmp_path: Path) -> None:
    report, source, _writer, _root, _stream, timeline_id = _import(tmp_path)
    body = report.to_dict()
    assert body["source"] == "local_fs"
    assert body["source_event_count"] == 6 == body["kernel_event_count"]
    assert body["source_head_version"] == 6 == body["kernel_head_seq"]
    assert body["checks"] == {
        "count": True,
        "head": True,
        "content": True,
        "kinds": True,
    }
    # (e) per-kind counts preserved, including the unregistered kind.
    assert body["kinds"]["timeline.custom_note"] == 1
    assert body["kinds"]["clip.added"] == 1
    assert body["kinds"]["timeline.config_replaced"] == 1
    assert body["kinds"]["timeline.asset_registry_replaced"] == 1
    assert body["written"] is True
    assert body["replayed"] is False
    _writer.close()


def test_verify_backfill_reusable_checker(tmp_path: Path) -> None:
    report, source, writer, _root, stream_id, _tid = _import(tmp_path)
    verification = verify_backfill(source, stream_id=stream_id, writer=writer)
    assert verification.ok is True
    assert verification.source_event_count == 6
    assert verification.kernel_event_count == 6
    assert verification.source_head_version == 6
    assert verification.kernel_head_seq == 6
    assert verification.source_kinds == verification.kernel_kinds
    assert verification.checks_dict() == {
        "count": True,
        "head": True,
        "content": True,
        "kinds": True,
    }
    writer.close()


# ---------------------------------------------------------------------------
# (c) content projection — canonical equality of every preserved field
# ---------------------------------------------------------------------------


def test_content_projection_canonical_equality(tmp_path: Path) -> None:
    report, source, writer, _root, stream_id, _tid = _import(tmp_path)
    rows = kernel_event_rows(writer, stream_id)
    assert len(rows) == len(source.events)
    for index, (source_event, row) in enumerate(
        zip(source.events, rows), start=1
    ):
        assert row["seq"] == index
        assert row["kind"] == source_event.kind
        assert row["event_id"] == source_event.event_id
        assert row["actor_kind"] == {
            "agent": "executor",
            "human": "local",
            "system": "system",
        }[source_event.actor.type]
        assert row["created_at"] == source_event.ts
        from astrid.packs.timeline.backfill import map_source_event

        mapped = map_source_event(
            source_event, timeline_ulid=source.timeline_ulid
        )
        assert canonical_json(row["data"]) == canonical_json(
            mapped.expected_kernel_data
        )
    writer.close()


def test_created_event_enriched_with_timeline_ulid(tmp_path: Path) -> None:
    report, source, writer, _root, stream_id, _tid = _import(tmp_path)
    rows = kernel_event_rows(writer, stream_id)
    created = rows[0]
    assert created["kind"] == "timeline.created"
    # The conversion adds exactly timeline_ulid from the identity sidecar
    # (module-documented enrichment); every source field stays verbatim.
    assert created["data"]["timeline_ulid"] == source.timeline_ulid
    assert created["data"]["slug"] == "main"
    assert created["data"]["name"] == "Main"
    assert created["data"]["timeline_id"] == source.timeline_id
    writer.close()


def test_unknown_kind_passes_through_as_raw_dict(tmp_path: Path) -> None:
    report, source, writer, _root, stream_id, _tid = _import(tmp_path)
    rows = kernel_event_rows(writer, stream_id)
    custom = [row for row in rows if row["kind"] == "timeline.custom_note"]
    assert len(custom) == 1
    # The unregistered kind's payload survives as a raw dict, verbatim.
    assert custom[0]["data"] == {"note": "raw dict pass-through"}
    assert report.to_dict()["kinds"]["timeline.custom_note"] == 1
    writer.close()


# ---------------------------------------------------------------------------
# (d) idempotency — same import twice: zero new events, unchanged head
# ---------------------------------------------------------------------------


def test_idempotent_reimport_zero_new_events_unchanged_head(
    tmp_path: Path,
) -> None:
    report1, source, writer, projects_root, stream_id, timeline_id = _import(
        tmp_path
    )
    projects, receipts, _ = make_backfill_deps(writer)
    before_rows = kernel_event_rows(writer, stream_id)
    before_head = head_seq(writer, stream_id)

    report2 = backfill_timeline(
        writer=writer,
        projects=projects,
        receipts=receipts,
        project_slug="proj",
        source=source,
        projects_root=projects_root,
    )
    assert report2.replayed is True
    assert report2.to_dict()["kernel_event_count"] == 6
    assert head_seq(writer, stream_id) == before_head
    after_rows = kernel_event_rows(writer, stream_id)
    assert len(after_rows) == len(before_rows) == 6
    assert [row["event_id"] for row in after_rows] == [
        row["event_id"] for row in before_rows
    ]
    # The marker entry survives the replay untouched.
    assert marker_state(projects_root)[timeline_id]["events_sha256"] == (
        source.events_sha256
    )
    writer.close()


# ---------------------------------------------------------------------------
# (f) marker discipline
# ---------------------------------------------------------------------------


def test_marker_written_only_after_checks_pass(tmp_path: Path) -> None:
    report, source, _writer, projects_root, _stream, timeline_id = _import(
        tmp_path
    )
    assert report.marker_written is True
    state = marker_state(projects_root)
    assert state[timeline_id] == {
        "backfilled_at": state[timeline_id]["backfilled_at"],
        "source": "local_fs",
        "source_head_version": 6,
        "events_sha256": source.events_sha256,
    }
    assert set(state[timeline_id].keys()) == {
        "backfilled_at",
        "source",
        "source_head_version",
        "events_sha256",
    }
    _writer.close()


def test_failed_import_writes_no_marker_and_rolls_back(tmp_path: Path) -> None:
    def _explode(_index: int) -> None:
        raise RuntimeError("simulated process kill mid-transaction")

    # The unit of work propagates the callback exception unchanged after a
    # rollback, exactly like a killed process leaves no partial transaction.
    with pytest.raises(RuntimeError, match="simulated process kill"):
        _import(tmp_path, on_before_append=_explode)
    # Nothing of the backfill committed: no timeline stream, no timeline
    # events, no backfill receipt, no marker. (The project's own
    # core.project stream/event/receipt exist — that is expected.)
    projects_root = tmp_path / "projects"
    writer_path = projects_root / ".astrid" / "astrid.sqlite3"
    import sqlite3

    conn = sqlite3.connect(writer_path)
    try:
        timeline_streams = conn.execute(
            "SELECT COUNT(*) FROM event_streams "
            "WHERE stream_type = 'timeline.timeline'"
        ).fetchone()[0]
        timeline_events = conn.execute(
            "SELECT COUNT(*) FROM events e "
            "JOIN event_streams s ON s.id = e.stream_id "
            "WHERE s.stream_type = 'timeline.timeline'"
        ).fetchone()[0]
        backfill_receipts = conn.execute(
            "SELECT COUNT(*) FROM command_receipts "
            "WHERE command_kind = 'timeline.backfill'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert timeline_streams == 0
    assert timeline_events == 0
    assert backfill_receipts == 0
    assert marker_json(projects_root) == {}


# ---------------------------------------------------------------------------
# Authority mixing (R5): no later request mixes authorities per timeline
# ---------------------------------------------------------------------------


def test_authority_marker_refuses_mixed_source(tmp_path: Path) -> None:
    _report, _source, _w, projects_root, _stream, timeline_id = _import(
        tmp_path
    )
    # A different source export for the SAME timeline identity (different
    # content -> different sha/head) must be refused before any write.
    changed_home, _tid, _ulid = make_source_timeline(
        tmp_path / "changed",
        timeline_id=timeline_id,
        timeline_ulid="01J00000000000000000000009",
        slug="main",
        events_spec=[
            (
                "timeline.created",
                {"timeline_id": "X", "slug": "main", "name": "Main"},
                "human",
            ),
            (
                "timeline.config_replaced",
                {"config": {"tracks": [], "clips": []}},
                "human",
            ),
        ],
    )
    from astrid.packs.timeline.backfill import load_local_fs_source

    changed_source = load_local_fs_source(changed_home)
    writer = make_writer(projects_root / ".astrid" / "astrid.sqlite3")
    try:
        projects, receipts, _ = make_backfill_deps(writer)
        with pytest.raises(BackfillAuthorityError):
            backfill_timeline(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                source=changed_source,
                projects_root=projects_root,
            )
    finally:
        writer.close()
    _w.close()


# ---------------------------------------------------------------------------
# Discrepancy detection fails closed
# ---------------------------------------------------------------------------


def test_discrepancy_fails_closed(tmp_path: Path) -> None:
    """A checker mismatch (tampered kernel rows) surfaces as a typed error."""
    report, source, writer, projects_root, stream_id, _tid = _import(tmp_path)
    # Tamper one kernel row's payload after import (simulating an external
    # corruption); re-verification must fail closed.
    writer.submit(
        lambda session: session.execute(
            "UPDATE events SET payload_json = json_set("
            "payload_json, '$.data.note', 'tampered') "
            "WHERE stream_id = ? AND kind = 'timeline.custom_note'",
            (stream_id,),
        )
    )
    projects, receipts, _ = make_backfill_deps(writer)
    # An identical re-import replays the receipt, then re-verifies and must
    # fail closed (no marker rewrite happens on a failed verification).
    try:
        with pytest.raises(BackfillDiscrepancyError):
            backfill_timeline(
                writer=writer,
                projects=projects,
                receipts=receipts,
                project_slug="proj",
                source=source,
                projects_root=projects_root,
            )
    finally:
        writer.close()


# ---------------------------------------------------------------------------
# dry-run: checks WITHOUT writing markers or events
# ---------------------------------------------------------------------------


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    projects_root, _home, timeline_id, _ulid = project_root_with_timeline(
        tmp_path
    )
    writer = make_writer(projects_root / ".astrid" / "astrid.sqlite3")
    try:
        make_project(writer)
        projects, receipts, _ = make_backfill_deps(writer)
        from astrid.packs.timeline.backfill import load_local_fs_source

        source = load_local_fs_source(_home)
        report = backfill_timeline(
            writer=writer,
            projects=projects,
            receipts=receipts,
            project_slug="proj",
            source=source,
            projects_root=projects_root,
            dry_run=True,
        )
        body = report.to_dict()
        assert body["dry_run"] is True
        assert body["written"] is False
        assert body["marker_written"] is False
        assert body["kernel_event_count"] == 0
        assert body["kernel_head_seq"] == 0
        assert body["source_event_count"] == 6
        assert body["source_head_version"] == 6
        assert body["checks"]["kinds"] is True
        assert "no events, receipts, or markers written" in body["detail"]
        # Nothing exists in the database or beside it.
        import sqlite3

        conn = sqlite3.connect(
            projects_root / ".astrid" / "astrid.sqlite3"
        )
        try:
            # The project's own core.project stream/event/receipt exist (the
            # project row was created); NOTHING of the backfill may exist.
            assert conn.execute(
                "SELECT COUNT(*) FROM events e "
                "JOIN event_streams s ON s.id = e.stream_id "
                "WHERE s.stream_type = 'timeline.timeline'"
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT COUNT(*) FROM event_streams "
                "WHERE stream_type = 'timeline.timeline'"
            ).fetchone()[0] == 0
            assert conn.execute(
                "SELECT COUNT(*) FROM command_receipts "
                "WHERE command_kind = 'timeline.backfill'"
            ).fetchone()[0] == 0
        finally:
            conn.close()
        assert marker_json(projects_root) == {}
    finally:
        writer.close()
